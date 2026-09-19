"""
MetaTrader 5 Data Feed — connects to MT5 terminal for real NAS100 & Gold tick data.

Provides:
  - Real-time tick polling from MT5 terminal (bid/ask/last, volume, buy/sell flags)
  - Historical tick/bar download for backtesting & VP computation
  - Book of market (DOM) data for orderbook analysis
  - Symbol info (tick size, contract size, session times)

Requirements:
  - MetaTrader 5 terminal installed and running on Windows
  - pip install MetaTrader5
  - Broker account connected in MT5

MT5 Symbol Mapping (broker-dependent, adjust in config):
  - NAS100: "NAS100", "USTEC", "US100", "NAS100.cash", "USTEC.cash"
  - Gold:   "XAUUSD", "GOLD", "XAUUSD.cash"
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

from orderflow_system.data.models import (
    Tick, Side, OrderbookSnapshot, OrderbookLevel, Candle,
)

logger = logging.getLogger(__name__)

# MT5 tick flags (from MetaTrader5 module constants)
TICK_FLAG_BID = 0x02
TICK_FLAG_ASK = 0x04
TICK_FLAG_LAST = 0x08
TICK_FLAG_VOLUME = 0x10
TICK_FLAG_BUY = 0x20
TICK_FLAG_SELL = 0x40


def _book_quantity(entry) -> float:
    """Quantity for one DOM entry, across MetaTrader5 package builds.

    Measured against a live terminal (MetaQuotes-Demo, package 5.0.6180, 2026-09-17):
    ``BookInfo`` exposes ``type, price, volume, volume_dbl`` — the feed's original
    ``volume_real`` read raised on every poll and killed DOM entirely. ``volume_dbl``
    (current), ``volume_real`` (older documented builds) and integer ``volume`` are all
    tried; the first positive one wins.
    """
    for attr in ("volume_dbl", "volume_real", "volume"):
        try:
            q = float(getattr(entry, attr, 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if q > 0:
            return q
    return 0.0


class MT5Feed:
    """
    Real-time and historical data feed from MetaTrader 5 terminal.

    Polling-based: MT5 Python API is synchronous, so we poll ticks in an
    async loop with configurable interval. For orderflow, we need the
    LAST price + BUY/SELL flags, not just bid/ask.

    Usage:
        feed = MT5Feed(
            symbols={"NAS100USDT": "USTEC", "XAUUSDT": "XAUUSD"},
            on_tick=my_tick_handler,
            on_orderbook=my_book_handler,
        )
        await feed.start()
    """

    def __init__(
        self,
        symbols: dict[str, str],  # {internal_name: mt5_symbol}
        on_tick: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
        poll_interval_ms: int = 100,
        enable_book: bool = True,
    ):
        self.symbols = symbols  # e.g., {"NAS100USDT": "USTEC", "XAUUSDT": "XAUUSD"}
        self.on_tick = on_tick
        self.on_orderbook = on_orderbook
        self.poll_interval_ms = poll_interval_ms
        self.enable_book = enable_book
        self._running = False
        self._mt5 = None
        self._last_tick_time: dict[str, int] = {}  # Track last seen tick per symbol
        self._initialized = False
        #: Broker server clocks run offset from UTC (a MetaQuotes demo measured +3 h) and MT5
        #: stamps ticks with the SERVER clock, so storing `time_msc` raw would put every MT5 row
        #: hours into the future — skewing candle buckets, session windows and the freshness
        #: ages. The offset is learned from the freshest tick visible and applied on the way in.
        self._clock_offset_ms: Optional[int] = None
        #: Prints that carried no volume at all and were recorded as 1 lot (order flow cannot use a
        #: zero-size fill). Counted so the substitution is visible, and warned about once.
        self._volume_defaulted = 0
        #: SEC-06: prints refused for a non-finite / non-positive price (the other feeds gate too).
        self._rejected_ticks = 0
        self._volume_defaulted_warned = False

    def connect(self) -> bool:
        """Initialize MT5 connection (call before download_historical_ticks)."""
        if self._initialized:
            return True
        return self._initialize_mt5()

    async def start(self):
        """Initialize MT5 connection and begin polling."""
        if not self._initialized and not self._initialize_mt5():
            logger.error("Failed to initialize MT5. Make sure MT5 terminal is running.")
            return

        self._running = True

        # Enable market book for each symbol (DOM data)
        if self.enable_book:
            for _internal, mt5_sym in self.symbols.items():
                if self._mt5.market_book_add(mt5_sym):
                    logger.info(f"Market book enabled for {mt5_sym}")
                else:
                    logger.warning(
                        f"Market book unavailable for {mt5_sym} — no DOM from this broker"
                    )

        logger.info(
            f"MT5 feed started. Polling {len(self.symbols)} symbols "
            f"every {self.poll_interval_ms}ms"
        )

        try:
            while self._running:
                await self._poll_cycle()
                await asyncio.sleep(self.poll_interval_ms / 1000.0)
        finally:
            await self.stop()

    async def stop(self):
        """Disconnect from MT5."""
        self._running = False
        if self._mt5 and self._initialized:
            if self.enable_book:
                for mt5_sym in self.symbols.values():
                    try:
                        self._mt5.market_book_release(mt5_sym)
                    except Exception:
                        pass
            self._mt5.shutdown()
            self._initialized = False
            logger.info("MT5 disconnected")

    def _initialize_mt5(self) -> bool:
        """Initialize MT5 connection."""
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            logger.error(
                "MetaTrader5 package not installed. Install with: "
                "pip install MetaTrader5"
            )
            return False

        if not mt5.initialize():
            error = mt5.last_error()
            logger.error(f"MT5 initialize() failed: {error}")
            return False

        self._initialized = True

        # Log account info
        account = mt5.account_info()
        if account:
            logger.info(
                f"MT5 connected: {account.server} | "
                f"Account: {account.login} | Balance: {account.balance}"
            )

        # Validate symbols exist
        for internal, mt5_sym in list(self.symbols.items()):
            info = mt5.symbol_info(mt5_sym)
            if info is None:
                logger.warning(
                    f"Symbol '{mt5_sym}' not found in MT5. "
                    f"Trying alternatives..."
                )
                # Try common alternatives
                found = self._find_symbol_alternative(mt5_sym, internal)
                if not found:
                    logger.error(
                        f"Could not find any matching symbol for {internal}. "
                        f"Available symbols can be listed with mt5.symbols_get()"
                    )
            else:
                if not info.visible:
                    mt5.symbol_select(mt5_sym, True)
                logger.info(
                    f"Symbol {mt5_sym} ({internal}): "
                    f"tick_size={info.trade_tick_size}, "
                    f"digits={info.digits}, "
                    f"spread={info.spread}"
                )

        # One cheap probe so even the first tick batch is stamped in UTC
        self._note_clock(self._newest_visible_tick_ms())

        return True

    # ── Server clock ─────────────────────────────────────────────────────────
    #: Brokers offset their server clock in whole/half hours; rounding the measured offset to
    #: 15 minutes absorbs network latency, a candidate beyond 14 h is not a broker offset at all.
    _CLOCK_ROUND_MS = 15 * 60 * 1000
    _CLOCK_MAX_MS = 14 * 60 * 60 * 1000

    def _newest_visible_tick_ms(self) -> int:
        """The newest ``time_msc`` the subscribed symbols report right now (0 when none)."""
        newest = 0
        for mt5_sym in self.symbols.values():
            try:
                tick = self._mt5.symbol_info_tick(mt5_sym)
            except Exception:                          # one bad symbol must not stop the probe
                continue
            if tick is not None:
                newest = max(newest, int(tick.time_msc))
        return newest

    def _note_clock(self, newest_server_ms: int) -> None:
        """Learn the server↔UTC offset from the newest live tick stamp seen.

        Only ever RAISED within a session: a candidate from a tick that arrived on time equals
        the broker's offset, while a quiet symbol's stale print understates it — so the maximum
        observation is the honest one. Called from the live paths only (a historical download's
        newest stamp is old by construction and would understate the offset).
        """
        try:
            newest = int(newest_server_ms or 0)
        except (TypeError, ValueError):
            return
        if not newest:
            return
        now_ms = int(time.time() * 1000)
        candidate = int(round((newest - now_ms) / self._CLOCK_ROUND_MS)) * self._CLOCK_ROUND_MS
        if abs(candidate) > self._CLOCK_MAX_MS:
            return
        if self._clock_offset_ms is None or candidate > self._clock_offset_ms:
            self._clock_offset_ms = candidate
            logger.info(
                "MT5 server clock offset %+.2f h (server %s) — ticks are stored in UTC",
                candidate / 3_600_000.0,
                "+ ahead of UTC" if candidate >= 0 else "behind UTC",
            )

    def to_utc_ms(self, server_ms: int) -> int:
        """A server-time stamp as a true UTC epoch ms (unchanged until an offset is learned)."""
        try:
            return int(server_ms) - int(self._clock_offset_ms or 0)
        except (TypeError, ValueError):
            return int(server_ms)

    # Known alternative symbol names per asset class (broker-dependent)
    _SYMBOL_ALTERNATIVES: dict[str, list[str]] = {
        # Indices
        "USTEC": ["USTEC", "USTECm", "NAS100", "US100", "USTEC.cash", "NAS100.cash", "USTECH100", "#NAS100", "NASDAQ"],
        "US500": ["US500", "US500m", "SP500", "SPX500", "US500.cash", "#SP500", "SP500m"],
        "US30":  ["US30", "US30m", "DJ30", "DJI30", "US30.cash", "#DJ30", "DJ30m"],
        "UK100": ["UK100", "UK100m", "FTSE100", "UK100.cash", "#UK100"],
        "DE30":  ["DE30", "DE30m", "DE40", "DE40m", "DAX40", "GER40", "GER30", "DE30.cash"],
        "JP225": ["JP225", "JP225m", "NI225", "NIKKEI225", "JP225.cash"],
        "FR40":  ["FR40", "FR40m", "CAC40", "FRA40", "FR40.cash"],
        "AUS200":["AUS200", "AUS200m", "AU200", "ASX200", "AUS200.cash"],
        "HK50":  ["HK50", "HK50m", "HSI50", "HK50.cash"],
        # Metals
        "XAUUSD":["XAUUSD", "XAUUSDm", "GOLD", "GOLDm", "XAUUSD.cash", "#XAUUSD"],
        "XAGUSD":["XAGUSD", "XAGUSDm", "SILVER", "SILVERm", "XAGUSD.cash"],
        # Energy
        "USOIL": ["USOIL", "USOILm", "WTI", "XTIUSD", "XTIUSDm", "CrudeOIL", "USCrude"],
        "UKOIL": ["UKOIL", "UKOILm", "BRENT", "XBRUSD", "XBRUSDm", "BrentOIL"],
        # Forex Majors
        "EURUSD":["EURUSD", "EURUSDm", "EURUSD.cash"],
        "GBPUSD":["GBPUSD", "GBPUSDm"],
        "USDJPY":["USDJPY", "USDJPYm"],
        "AUDUSD":["AUDUSD", "AUDUSDm"],
        "USDCAD":["USDCAD", "USDCADm"],
        "USDCHF":["USDCHF", "USDCHFm"],
        "NZDUSD":["NZDUSD", "NZDUSDm"],
        # Forex Crosses
        "EURGBP":["EURGBP", "EURGBPm"],
        "EURJPY":["EURJPY", "EURJPYm"],
        "GBPJPY":["GBPJPY", "GBPJPYm"],
        # Stocks
        "AAPL":  ["AAPL", "AAPLm", "#AAPL", "AAPL.US"],
        "TSLA":  ["TSLA", "TSLAm", "#TSLA", "TSLA.US"],
        "AMZN":  ["AMZN", "AMZNm", "#AMZN", "AMZN.US"],
        "MSFT":  ["MSFT", "MSFTm", "#MSFT", "MSFT.US"],
        "NVDA":  ["NVDA", "NVDAm", "#NVDA", "NVDA.US"],
        "META":  ["META", "METAm", "#META", "META.US"],
        "GOOGL": ["GOOGL", "GOOGLm", "#GOOGL", "GOOGL.US", "GOOG", "GOOGm"],
        # Crypto
        "BTCUSD":["BTCUSD", "BTCUSDm", "BTCUSDT"],
    }

    def _find_symbol_alternative(self, mt5_sym: str, internal: str) -> bool:
        """Try to find alternative symbol names for common instruments."""
        mt5 = self._mt5
        base = mt5_sym.upper().replace(".CASH", "").replace(".", "").rstrip("M")

        # Find matching alternatives list
        alternatives = []
        for key, alts in self._SYMBOL_ALTERNATIVES.items():
            if base == key.upper() or mt5_sym.upper().rstrip("M") == key.upper():
                alternatives = alts
                break

        # Fallback: try plain name with/without 'm' suffix
        if not alternatives:
            alternatives = [mt5_sym, mt5_sym.rstrip('m'), mt5_sym + 'm']

        for alt in alternatives:
            info = mt5.symbol_info(alt)
            if info is not None:
                if not info.visible:
                    mt5.symbol_select(alt, True)
                self.symbols[internal] = alt
                logger.info(f"Found alternative symbol: {alt} for {internal}")
                return True

        return False

    async def _poll_cycle(self):
        """Poll MT5 for new ticks and book data for all symbols."""

        for internal, mt5_sym in self.symbols.items():
            try:
                # ── Poll ticks ──
                await self._poll_ticks(internal, mt5_sym)

                # ── Poll orderbook (DOM) ──
                if self.enable_book and self.on_orderbook:
                    await self._poll_book(internal, mt5_sym)

            except Exception as e:
                logger.error(f"Error polling {mt5_sym}: {e}", exc_info=True)

    async def _poll_ticks(self, internal: str, mt5_sym: str):
        """
        Poll new ticks since last check.
        MT5 ticks have flags indicating BUY or SELL direction.
        """
        mt5 = self._mt5
        now = datetime.now(timezone.utc)

        if internal not in self._last_tick_time:
            # First poll — get ticks from last 2 seconds
            from_dt = now - timedelta(seconds=2)
        else:
            # Get ticks since last poll
            from_dt = datetime.fromtimestamp(
                self._last_tick_time[internal] / 1000.0, tz=timezone.utc
            )

        # copy_ticks_from returns numpy array of ticks
        ticks_data = mt5.copy_ticks_from(mt5_sym, from_dt, 1000, mt5.COPY_TICKS_ALL)

        if ticks_data is None or len(ticks_data) == 0:
            return

        # Learn the server clock from this batch BEFORE stamping it: the newest stamp of a live
        # batch is the honest observation (a quiet symbol's stale print only understates it).
        self._note_clock(int(ticks_data[-1]['time_msc']))

        for t in ticks_data:
            # Skip if we already processed this tick (stamps stay server-time here — the poll
            # window is server-time too; only the stored Tick is converted to UTC).
            tick_time_ms = int(t['time_msc'])
            if internal in self._last_tick_time and tick_time_ms <= self._last_tick_time[internal]:
                continue

            # Determine aggressor side from tick flags
            flags = int(t['flags'])
            if flags & TICK_FLAG_BUY:
                side = Side.BUY
            elif flags & TICK_FLAG_SELL:
                side = Side.SELL
            else:
                # No buy/sell flag — use price vs previous bid/ask heuristic
                last_price = float(t['last'])
                bid = float(t['bid'])
                ask = float(t['ask'])
                if last_price >= ask:
                    side = Side.BUY
                elif last_price <= bid:
                    side = Side.SELL
                else:
                    side = Side.BUY  # Default to buy if ambiguous

            # Use 'last' price (actual trade price) when available,
            # fall back to mid of bid/ask
            last_price = float(t['last'])
            if last_price == 0:
                last_price = (float(t['bid']) + float(t['ask'])) / 2.0

            # SEC-06: this feed was the only live one that let a NaN/zero/negative price through
            # — the others refuse non-finite values at the door. A NaN price poisoned the live
            # bar (and 500'd the routes) after the fact.
            if not (math.isfinite(last_price) and last_price > 0):
                self._rejected_ticks += 1
                continue

            volume = float(t['volume_real']) if t['volume_real'] > 0 else float(t['volume'])
            if not (math.isfinite(volume) and volume > 0):
                # Neither real volume nor tick volume: a zero-size fill is unusable for order
                # flow, so the print is carried as 1 lot — and COUNTED, because an invented 1 is
                # otherwise indistinguishable from a real one on the tape.
                volume = 1.0
                self._volume_defaulted += 1

            tick = Tick(
                timestamp_ms=self.to_utc_ms(tick_time_ms),
                price=last_price,
                size=volume,
                side=side,
                trade_id=f"mt5_{tick_time_ms}",
            )

            if self.on_tick:
                await self.on_tick(internal, tick)

        if self._volume_defaulted and not self._volume_defaulted_warned:
            self._volume_defaulted_warned = True
            logger.warning(
                "MT5: %d print(s) carried no volume (real or tick) and were recorded as 1 lot each "
                "— this broker may not publish volume for these symbols",
                self._volume_defaulted,
            )

        # Update last tick time
        self._last_tick_time[internal] = int(ticks_data[-1]['time_msc'])

    async def _poll_book(self, internal: str, mt5_sym: str):
        """
        Poll the order book (DOM / Market Depth) from MT5.
        Converts MT5 book entries to our OrderbookSnapshot model.
        """
        mt5 = self._mt5
        book = mt5.market_book_get(mt5_sym)

        if book is None or len(book) == 0:
            return

        bids = []
        asks = []
        now_ms = int(time.time() * 1000)

        for entry in book:
            level = OrderbookLevel(
                price=entry.price,
                quantity=_book_quantity(entry),
            )
            # MT5 book type: 1 = SELL (ask side), 2 = BUY (bid side)
            if entry.type == 1:  # BOOK_TYPE_SELL
                asks.append(level)
            elif entry.type == 2:  # BOOK_TYPE_BUY
                bids.append(level)

        snapshot = OrderbookSnapshot(
            timestamp_ms=now_ms,
            bids=sorted(bids, key=lambda x: -x.price),
            asks=sorted(asks, key=lambda x: x.price),
        )

        if self.on_orderbook:
            await self.on_orderbook(internal, snapshot)

    # ── Historical Data Methods ──

    async def download_historical_ticks(
        self,
        mt5_sym: str,
        from_date: datetime,
        to_date: datetime,
    ) -> list[Tick]:
        """
        Download historical ticks from MT5 for backtesting.
        Uses copy_ticks_range() which can return millions of ticks.
        """
        mt5 = self._mt5
        if not self._initialized:
            self._initialize_mt5()

        logger.info(f"Downloading ticks for {mt5_sym} from {from_date} to {to_date}")

        ticks_data = mt5.copy_ticks_range(
            mt5_sym, from_date, to_date, mt5.COPY_TICKS_ALL
        )

        if ticks_data is None or len(ticks_data) == 0:
            logger.warning(f"No ticks returned for {mt5_sym}")
            return []

        ticks = []
        for t in ticks_data:
            flags = int(t['flags'])
            if flags & TICK_FLAG_BUY:
                side = Side.BUY
            elif flags & TICK_FLAG_SELL:
                side = Side.SELL
            else:
                last_price = float(t['last'])
                ask = float(t['ask'])
                side = Side.BUY if last_price >= ask else Side.SELL

            last_price = float(t['last'])
            if last_price == 0:
                last_price = (float(t['bid']) + float(t['ask'])) / 2.0

            # SEC-06: the same gate as the live path — a NaN/zero/negative price out of history
            # must not become a stored tick either.
            if not (math.isfinite(last_price) and last_price > 0):
                self._rejected_ticks += 1
                continue

            volume = float(t['volume_real']) if t['volume_real'] > 0 else float(t['volume'])
            if not (math.isfinite(volume) and volume > 0):
                volume = 1.0                          # see _poll_ticks: carried as 1 lot
                self._volume_defaulted += 1

            ticks.append(Tick(
                timestamp_ms=self.to_utc_ms(int(t['time_msc'])),
                price=last_price,
                size=volume,
                side=side,
                trade_id=f"mt5_{t['time_msc']}",
            ))

        logger.info(f"Downloaded {len(ticks)} ticks for {mt5_sym}")
        return ticks

    async def download_historical_candles(
        self,
        mt5_sym: str,
        timeframe: int,  # MT5 timeframe constant (e.g., mt5.TIMEFRAME_M1)
        from_date: datetime,
        to_date: datetime,
    ) -> list[Candle]:
        """
        Download historical OHLCV bars from MT5.
        Note: MT5 bars don't have buy/sell volume split — only total.
        """
        mt5 = self._mt5
        if not self._initialized:
            self._initialize_mt5()

        rates = mt5.copy_rates_range(mt5_sym, timeframe, from_date, to_date)

        if rates is None or len(rates) == 0:
            logger.warning(f"No bars returned for {mt5_sym}")
            return []

        candles = []
        for r in rates:
            candles.append(Candle(
                timestamp_ms=self.to_utc_ms(int(r['time']) * 1000),
                open=float(r['open']),
                high=float(r['high']),
                low=float(r['low']),
                close=float(r['close']),
                volume=float(r['real_volume'] if r['real_volume'] > 0 else r['tick_volume']),
                buy_volume=0.0,   # MT5 bars don't split buy/sell
                sell_volume=0.0,
                tick_count=int(r['tick_volume']),
            ))

        logger.info(f"Downloaded {len(candles)} bars for {mt5_sym}")
        return candles

    def get_symbol_info(self, mt5_sym: str) -> Optional[dict]:
        """Get symbol properties from MT5."""
        mt5 = self._mt5
        info = mt5.symbol_info(mt5_sym)
        if info is None:
            return None
        return {
            "name": info.name,
            "description": info.description,
            "tick_size": info.trade_tick_size,
            "tick_value": info.trade_tick_value,
            "digits": info.digits,
            "spread": info.spread,
            "contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "currency_base": info.currency_base,
            "currency_profit": info.currency_profit,
        }

    def list_available_symbols(self, filter_text: str = "") -> list[str]:
        """List available symbols in MT5 matching a filter."""
        mt5 = self._mt5
        if filter_text:
            symbols = mt5.symbols_get(filter_text)
        else:
            symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s.name for s in symbols]
