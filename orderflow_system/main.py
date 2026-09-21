"""
Main Orchestrator — Wires all components together and runs the system.

Architecture:
  Data Source (MT5 or Bybit) → Ticks → CandleBuilder → Analytics Engines → Pattern Detectors
       ↓                              ↓                        ↓
  OrderbookTracker              DeltaEngine              Profile Framing
       ↓                              ↓                        ↓
                       Signal Aggregator (State Machine)
                                    ↓
                       Telegram Alert Bot + Database Logging

Data Sources:
  - MT5 (default): Real NAS100/XAUUSD data from MetaTrader 5 terminal
  - Bybit: Free perpetual futures data via WebSocket
  - Both: Run both feeds simultaneously
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from orderflow_system.analytics.session import session_window
from orderflow_system.config import settings as runtime_settings
from orderflow_system.config.settings import (
    InstrumentConfig,
    DataSource,
    get_all_configs,
    TELEGRAM,
    DB_PATH,
    LOG_LEVEL,
    DATA_SOURCE,
    MT5,
    NINJATRADER,
    ALPACA,
    TRADIER,
    MARKETDATA,
    FINNHUB,
    DASHBOARD,
)
from orderflow_system.data.models import (
    Tick, Candle, Signal, OrderbookSnapshot,
)
from orderflow_system.data.bybit_feed import BybitFeed
from orderflow_system.data.binance_feed import BinanceFeed
from orderflow_system.data.hyperliquid_feed import HyperliquidFeed
from orderflow_system.data.okx_feed import OkxFeed
from orderflow_system.data.mt5_feed import MT5Feed
from orderflow_system.data.candle_builder import CandleBuilder
from orderflow_system.data.database import Database
from orderflow_system.analytics.volume_profile import VolumeProfileEngine
from orderflow_system.analytics.delta import DeltaEngine
from orderflow_system.analytics.footprint import FootprintEngine
from orderflow_system.analytics.orderbook import OrderbookTracker
from orderflow_system.patterns.absorption import AbsorptionDetector
from orderflow_system.patterns.initiative import InitiativeDetector
from orderflow_system.patterns.sweep import SweepDetector
from orderflow_system.patterns.exhaustion import ExhaustionDetector
from orderflow_system.patterns.divergence import DivergenceDetector
from orderflow_system.signals.profile_framing import ProfileFramingEngine
from orderflow_system.signals.aggregator import SignalAggregator
from orderflow_system.alerts.telegram_bot import TelegramAlertBot
from orderflow_system.dashboard.websocket_manager import WebSocketManager
from orderflow_system.dashboard.app import app as dashboard_app, set_system, ws_manager

logger = logging.getLogger("orderflow_system")


class InstrumentPipeline:
    """
    Full processing pipeline for a single instrument.
    Ticks → Candles → Analytics → Patterns → Signals → Alerts.
    """

    def __init__(self, config: InstrumentConfig):
        self.config = config
        self.symbol = config.instrument.value

        # Analytics engines
        self.candle_builder = CandleBuilder(
            interval_seconds=60,
            tick_size=config.tick_size,
            on_candle_close=self._on_candle_close,
        )
        self.vp_engine = VolumeProfileEngine(config.volume_profile)
        self.delta_engine = DeltaEngine(tick_size=config.tick_size)
        self.footprint_engine = FootprintEngine(
            tick_size=config.tick_size,
            min_print_size=float(getattr(runtime_settings, "FOOTPRINT_MIN_PRINT_SIZE", 0.0) or 0.0),
        )
        self.orderbook_tracker = OrderbookTracker(
            thin_threshold=config.sweep.thin_book_threshold
        )

        # Pattern detectors
        self.absorption = AbsorptionDetector(config.absorption, tick_size=config.tick_size)
        self.initiative = InitiativeDetector(config.initiative, tick_size=config.tick_size)
        self.sweep = SweepDetector(config.sweep)
        self.exhaustion = ExhaustionDetector(config.exhaustion)
        self.divergence = DivergenceDetector(config.divergence)

        # Profile framing
        self.profile_framing = ProfileFramingEngine()

        # Current price tracker
        self._current_price: float = 0.0
        self._tick_count: int = 0
        # Callback for routing candle-close signals to the system
        self._on_signals_callback = None
        # Callback for handing the closed candle itself to the system
        # (persistence + WS broadcast). Wired by OrderflowSystem.
        self._on_candle_closed_callback = None
        self._candle_count: int = 0

    async def process_tick(self, tick: Tick):
        """Process a single tick through the pipeline."""
        self._current_price = tick.price
        self._tick_count += 1
        await self.candle_builder.process_tick(tick)

    async def process_orderbook(self, snapshot: OrderbookSnapshot):
        """Process an orderbook update."""
        self.orderbook_tracker.update(snapshot)

        # Check for sweep on every book update
        current_candle = self.candle_builder.current_candle
        if current_candle and self.footprint_engine.history:
            fp = self.footprint_engine.history[-1]
            signal = self.sweep.check(
                self.orderbook_tracker, current_candle, fp
            )
            if signal:
                return signal
        return None

    async def _on_candle_close(self, candle: Candle) -> list[Signal]:
        """
        Called when a candle closes. Run all analytics and pattern checks.
        This is the main processing pipeline for each candle.
        """
        self._candle_count += 1
        signals: list[Signal] = []

        # 1. Compute delta
        delta = self.delta_engine.compute_from_candle(candle)

        # 2. Build footprint
        footprint = self.footprint_engine.build_from_candle(candle)

        # 3. Check each pattern detector
        # Absorption
        abs_signal = self.absorption.check_candle(
            candle, footprint, delta, self._current_price
        )
        if abs_signal:
            signals.append(abs_signal)
            logger.info(f"[{self.symbol}] {abs_signal}")

        # Initiative
        init_signal = self.initiative.check_candle(candle, delta, footprint)
        if init_signal:
            signals.append(init_signal)
            logger.info(f"[{self.symbol}] {init_signal}")

        # Exhaustion (needs candle history)
        recent = self.candle_builder.get_recent_candles(10)
        exh_signal = self.exhaustion.check_candle(
            candle, delta, self.delta_engine, footprint, recent
        )
        if exh_signal:
            signals.append(exh_signal)
            logger.info(f"[{self.symbol}] {exh_signal}")

        # Divergence
        div_signal = self.divergence.check_candle(candle, self.delta_engine)
        if div_signal:
            signals.append(div_signal)
            logger.info(f"[{self.symbol}] {div_signal}")

        # Route signals to the system if callback is set
        if signals and self._on_signals_callback:
            await self._on_signals_callback(self.symbol, signals)

        # Hand the closed candle itself to the system (persist + broadcast).
        # Runs AFTER the analytics pass, so it never re-runs analytics.
        if self._on_candle_closed_callback:
            await self._on_candle_closed_callback(self.symbol, candle)

        return signals

    @property
    def current_price(self) -> float:
        return self._current_price

    @property
    def stats(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self._current_price,
            "ticks": self._tick_count,
            "candles": self._candle_count,
            "cum_delta": self.delta_engine.cumulative_delta,
            "late_prints": self.candle_builder.late_prints,
            # SEC-06/SEC-16: the refused-print counters are system-level — one feed per run, gated
            # before dispatch — gathered in engine.live_status()'s `quality` block, so they
            # deliberately do not appear in this per-pipeline dict.
        }


def db_path_for_this_process() -> str:
    """The database path this process should actually use.

    The desktop launcher repoints ``settings.DB_PATH`` at the per-user data directory, so the
    value is read at call time (a module-load copy would silently ignore it). When the setting is
    still the bare default name — the standalone collector — the per-user directory wins too:
    handing SQLite a relative name deposits a live database (and its WAL) in whatever directory
    the process started from, which for this project is a repo checkout. A genuinely absolute
    ``DB_PATH`` is an explicit choice and is honoured as written.
    """
    configured = str(getattr(runtime_settings, "DB_PATH", "") or "")
    if configured and os.path.isabs(configured):
        return configured
    try:                                           # the per-user location, legacy-safe
        from orderflow_system.desktop import config_store

        return str(config_store.db_path())
    except Exception:                              # pragma: no cover - desktop package absent
        return configured or str(DB_PATH)


async def _run_owned(awaitables) -> None:
    """Run the engine's concurrent group with an owner (MEM-A1-01).

    ``asyncio.gather`` propagates the first exception but leaves the surviving members
    running, and once it has raised, cancelling the finished gather task cannot reach
    them (verified with a stdlib probe). The result was that one transient error could
    orphan a fully live engine — feeds still streaming and still writing to the database
    — while the UI showed "error" and the operator's next Start built a second engine
    over it. Here the group is explicit: on the first failure (or on cancellation) every
    pending member is cancelled and awaited before the exception leaves, so whoever
    catches it owns a dead group and can dispose the system safely.
    """
    tasks = [asyncio.ensure_future(item) for item in awaitables]
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


class OrderflowSystem:
    """
    Main system orchestrator.
    Manages multiple instruments, coordinates between pipelines,
    and routes signals to alerts.
    """

    def __init__(
        self,
        instruments: Optional[list[InstrumentConfig]] = None,
        data_source: DataSource = DATA_SOURCE,
        feed_symbols: Optional[dict[str, list[str]]] = None,
    ):
        if instruments is None:
            instruments = get_all_configs()

        self.data_source = data_source
        #: engine.partition_instruments(): {venue: [symbols]} for `both`/`all`. None keeps the
        #: historical single-source behaviour (every pipeline symbol on the one feed).
        self._feed_symbols = dict(feed_symbols or {}) or None
        self.pipelines: dict[str, InstrumentPipeline] = {}
        for cfg in instruments:
            self.pipelines[cfg.instrument.value] = InstrumentPipeline(cfg)

        # Standalone-pipeline defaults only: the desktop engine (desktop/engine.py) overrides
        # BOTH values from the user's config `risk` block right after construction, and that is
        # the cooldown/score a GUI user actually runs with. These numbers matter solely for a
        # bare OrderflowSystem instantiation (tests, embedding). Pinned end-to-end by
        # test_engine_wiring.py so the config knob can never silently stop working again.
        self.aggregator = SignalAggregator(
            min_composite_score=40.0,
            signal_cooldown_seconds=30.0,
        )

        # Wire candle-close signals from each pipeline back to the system
        for _sym, pipeline in self.pipelines.items():
            pipeline._on_signals_callback = self._on_candle_signals
            pipeline._on_candle_closed_callback = self._on_candle_closed
        self.telegram = TelegramAlertBot(
            bot_token=TELEGRAM.bot_token,
            chat_id=TELEGRAM.chat_id,
        )
        # Read the path at call time: the desktop launcher repoints settings.DB_PATH at the
        # per-user data directory, and a copy imported at module load would silently ignore
        # that and write into the repo. With no repoint at all (the standalone collector) the
        # per-user directory still wins — the working directory never holds the database.
        self.db = Database(db_path_for_this_process())
        self.feed: Optional[BybitFeed] = None
        self.mt5_feed: Optional[MT5Feed] = None
        self.alpaca_feed = None            # AlpacaFeed when that source is on
        self.nt_feed = None                # NinjaTraderFeed when that source is on
        # Options-data REST feeds (poll on demand, not tick streams).
        self.tradier_feed = None           # TradierFeed when that source is on
        self.marketdata_feed = None        # MarketDataFeed when that source is on
        self.finnhub_feed = None           # FinnhubFeed when that source is on
        self.ws_manager: WebSocketManager = ws_manager
        self._running = False
        self._tick_batch_size = 100
        self._tick_buffers: dict[str, list[Tick]] = {}
        #: Buffered writes that failed (a locked disk, a full volume). Counted so a persistent
        #: problem is visible in the log without one warning per tick.
        self._db_write_failures = 0
        # Bounded per-symbol tape buffer (dashboard initial fill + burst reads).
        # deque(maxlen=N) = O(1) append, fixed memory, no list copies on trim.
        self._recent_ticks_max = 500
        self._recent_ticks: dict[str, deque[Tick]] = {}
        # Most recent closed candle per symbol (live /api/footprint + microstructure).
        self._last_candles: dict[str, Candle] = {}
        # Most recent signals per symbol, newest last (live /api/microstructure).
        self._recent_signals_max = 50
        self._recent_signals: dict[str, deque[Signal]] = {}

    async def start(self):
        """Start the complete system."""
        logger.info("=" * 60)
        logger.info("  ORDERFLOW TRADING ALERT SYSTEM")
        logger.info("  Based on Fabio's Orderflow Methodology")
        logger.info("=" * 60)

        # Initialize database
        await self.db.connect()
        logger.info("Database connected")

        # Initialize Telegram
        await self.telegram.initialize()

        # Load historical profiles (if available) into profile framing engines
        for symbol, pipeline in self.pipelines.items():
            profiles = await self.db.get_volume_profiles(symbol, days=5)
            for vp in profiles:
                pipeline.profile_framing.add_profile(vp)
            if profiles:
                bias = pipeline.profile_framing.analyze(pipeline.current_price)
                logger.info(
                    f"[{symbol}] Loaded {len(profiles)} historical profiles. "
                    f"Bias: {bias.direction.value} ({bias.confidence:.0f}%)"
                )
                await self.telegram.send_daily_bias_update(symbol, bias)

        # Start data feed(s) based on configured source
        symbols = list(self.pipelines.keys())
        feed_tasks = []
        # `both`/`all` legs use the engine's per-venue partition: one instrument, one venue. Each
        # leg starts only when it has symbols — an empty leg is announced, not silently blank.
        partition = (self._feed_symbols
                     if self.data_source in (DataSource.BOTH, DataSource.ALL) else None)

        if self.data_source in (DataSource.MT5, DataSource.BOTH, DataSource.ALL):
            # ── MetaTrader 5 Feed ──
            if partition is not None:
                mt5_syms = {s: MT5.symbols.get(s, s) for s in partition["mt5"]}
            else:
                mt5_syms = dict(MT5.symbols)
            if not mt5_syms:
                logger.info("MT5 leg skipped — no enabled instrument belongs to the broker")
            else:
                self.mt5_feed = MT5Feed(
                    symbols=mt5_syms,
                    on_tick=self._on_tick,
                    on_orderbook=self._on_orderbook,
                    poll_interval_ms=MT5.poll_interval_ms,
                    enable_book=MT5.enable_book,
                )
                feed_tasks.append(self.mt5_feed.start())
                logger.info(
                    f"MT5 feed configured: {len(mt5_syms)} symbols "
                    f"(poll: {MT5.poll_interval_ms}ms, book: {MT5.enable_book})"
                )

                # Connect to MT5 early so symbol validation happens before feeds start
                if not self.mt5_feed.connect():
                    logger.error("MT5 connection failed — skipping history download")
                elif MT5.download_history_days > 0:
                    # Download M1 bars synchronously BEFORE starting feeds/dashboard
                    self._download_mt5_history_sync()

        if self.data_source in (DataSource.BYBIT, DataSource.BOTH, DataSource.ALL):
            # ── Bybit WebSocket Feed ──
            bybit_syms = list(partition["bybit"]) if partition is not None else symbols
            if bybit_syms:
                self.feed = BybitFeed(
                    symbols=bybit_syms,
                    on_tick=self._on_tick,
                    on_orderbook=self._on_orderbook,
                )
                feed_tasks.append(self.feed.start())
                logger.info(f"Bybit feed configured: {bybit_syms}")
            else:
                logger.info("Bybit leg skipped — no enabled instrument belongs to the exchange")

        if self.data_source in (DataSource.BINANCE,):
            # ── Binance USDⓈ-M futures Feed ──
            # Same callback contract as the Bybit feed (trades + L2 book), so every downstream
            # consumer — pipelines, the atlas hub, the heatmap — is source-agnostic.
            self.feed = BinanceFeed(
                symbols=symbols,
                on_tick=self._on_tick,
                on_orderbook=self._on_orderbook,
            )
            feed_tasks.append(self.feed.start())
            logger.info(f"Binance feed configured: {symbols}")

        if self.data_source in (DataSource.HYPERLIQUID,):
            # ── Hyperliquid perpetuals Feed ──
            # Same callback contract as the Bybit and Binance feeds (trades + book snapshots), so
            # every downstream consumer — pipelines, the atlas hub, the heatmap — is source-agnostic.
            self.feed = HyperliquidFeed(
                symbols=symbols,
                on_tick=self._on_tick,
                on_orderbook=self._on_orderbook,
            )
            feed_tasks.append(self.feed.start())
            logger.info(f"Hyperliquid feed configured: {symbols}")

        if self.data_source in (DataSource.OKX,):
            # ── OKX USDT swaps Feed ──
            self.feed = OkxFeed(
                symbols=symbols,
                on_tick=self._on_tick,
                on_orderbook=self._on_orderbook,
            )
            feed_tasks.append(self.feed.start())
            logger.info(f"OKX feed configured: {symbols}")

        if self.data_source in (DataSource.ALPACA, DataSource.ALL):
            # ── Alpaca Markets Feed (US equities/ETFs/options + crypto) ──
            from orderflow_system.data.alpaca_feed import AlpacaFeed

            candidates = list(partition["alpaca"]) if partition is not None else symbols
            mapped = {s: ALPACA.symbols[s] for s in candidates if s in ALPACA.symbols}
            if mapped:
                self.alpaca_feed = AlpacaFeed(
                    symbols=mapped,
                    on_tick=self._on_tick,
                    on_bar=self._on_alpaca_bar,
                    key_id=ALPACA.key_id,
                    secret=ALPACA.secret,
                    paper=ALPACA.paper,
                    feed=ALPACA.feed,
                    snapshot_seconds=ALPACA.snapshot_seconds,
                    history_minutes=ALPACA.history_minutes,
                    stock_cap=ALPACA.stock_cap,
                    option_cap=ALPACA.option_cap,
                )
                feed_tasks.append(self._run_alpaca_feed())
                logger.info("Alpaca feed configured: %s (feed=%s, paper=%s)",
                            mapped, ALPACA.feed, ALPACA.paper)
            else:
                logger.warning("Alpaca source selected but no enabled instrument is mapped "
                               "to an Alpaca symbol — nothing to stream"
                               if self.data_source is DataSource.ALPACA else
                               "Alpaca leg skipped — no enabled instrument is mapped to an "
                               "Alpaca symbol")

        if self.data_source in (DataSource.NINJATRADER, DataSource.ALL):
            # ── NinjaTrader 8 feed (through the shipped read-only bridge add-on) ──
            # Same callback contract as every other adapter (trades + book snapshots), so the
            # pipelines, the atlas hub and the heatmap stay source-agnostic.
            from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

            nt_wanted = set(partition["ninjatrader"]) if partition is not None else None
            mapped = {s: v for s, v in dict(NINJATRADER.symbols).items()
                      if nt_wanted is None or s in nt_wanted}
            if mapped:
                self.nt_feed = NinjaTraderFeed(
                    symbols=mapped,
                    on_tick=self._on_tick,
                    on_orderbook=self._on_orderbook,
                    host=NINJATRADER.host,
                    port=NINJATRADER.port,
                )
                feed_tasks.append(self.nt_feed.start())
                logger.info("NinjaTrader feed configured: %s (bridge %s:%s)",
                            mapped, NINJATRADER.host, NINJATRADER.port)
            else:
                logger.warning("NinjaTrader source selected but no enabled instrument is mapped — "
                               "nothing to stream (add one from the Instruments panel)")

        # ── Tradier REST feed (OPRA options chains) ──────────────────────────────
        # Not a tick stream — created when selected, polled on demand by the options/gex panels.
        if self.data_source in (DataSource.TRADIER, DataSource.ALL):
            from orderflow_system.data.tradier_feed import TradierFeed
            self.tradier_feed = TradierFeed(
                key_id=TRADIER.key_id,
                secret=TRADIER.secret,
                chain_width=TRADIER.chain_width,
                sandbox=TRADIER.sandbox,
            )
            logger.info("Tradier feed configured (chain_width=%d, sandbox=%s)",
                        TRADIER.chain_width, TRADIER.sandbox)

        # ── Market Data REST feed (OPRA chains with greeks) ─────────────────────
        if self.data_source in (DataSource.MARKETDATA, DataSource.ALL):
            from orderflow_system.data.marketdata_feed import MarketDataFeed
            self.marketdata_feed = MarketDataFeed(api_key=MARKETDATA.api_key)
            logger.info("Market Data feed configured")

        # ── Finnhub REST feed (economic calendar + news headlines) ──────────────
        if self.data_source in (DataSource.FINNHUB, DataSource.ALL):
            from orderflow_system.data.finnhub_feed import FinnhubFeed
            self.finnhub_feed = FinnhubFeed(api_key=FINNHUB.api_key)
            logger.info("Finnhub feed configured (calendar=%s, news=%s)",
                        FINNHUB.calendar_category, FINNHUB.news_category)

        self._running = True
        source_name = self.data_source.value.upper()
        logger.info(f"Starting live feed [{source_name}] for: {', '.join(symbols)}")

        # ── Dashboard (FastAPI + Uvicorn) ──
        if DASHBOARD.enabled:
            import uvicorn
            set_system(self)
            uvi_config = uvicorn.Config(
                dashboard_app,
                host=DASHBOARD.host,
                port=DASHBOARD.port,
                log_level=DASHBOARD.log_level,
                loop="none",
            )
            uvi_server = uvicorn.Server(uvi_config)
            feed_tasks.append(uvi_server.serve())
            logger.info(f"Dashboard enabled at http://{DASHBOARD.host}:{DASHBOARD.port}")

        # Run feed(s) + periodic tasks + dashboard concurrently. MEM-A1-01: an owned group —
        # a failed member cancels its siblings before the error leaves this frame, so a crash
        # can never orphan a live engine (gather propagates the exception but leaves the
        # survivors running with nothing holding a cancellable handle).
        await _run_owned([*feed_tasks, self._periodic_tasks()])

    async def stop(self):
        """Gracefully shut down."""
        logger.info("Shutting down...")
        self._running = False
        try:
            if self.feed:
                await self.feed.stop()
            if self.mt5_feed:
                await self.mt5_feed.stop()
            if self.alpaca_feed:
                await self.alpaca_feed.stop()
            if self.nt_feed:
                await self.nt_feed.stop()
            # Options-data REST feeds have no persistent connection to close.
            self.tradier_feed = None
            self.marketdata_feed = None
            self.finnhub_feed = None
        finally:
            # MEM-A1-07: the last batch and the database close are not optional — this block
            # runs even when a feed hangs and the engine's 15 s watchdog cancels this
            # coroutine mid-cleanup (a cancelled stop used to leave the store open and the
            # final tick batch lost). Each step is bounded so a stuck handle cannot pin it.
            try:
                await asyncio.wait_for(self._drain_tick_buffers(), timeout=10)
            except Exception as exc:                  # noqa: BLE001 — timeout included
                logger.warning("final tick flush did not finish: %s", exc)
            try:
                await asyncio.wait_for(self.db.close(), timeout=10)
            except Exception as exc:                  # noqa: BLE001
                logger.warning("database close did not finish: %s", exc)
        logger.info("System stopped.")

    async def _drain_tick_buffers(self) -> None:
        """Persist whatever the last batch left behind, before the database closes.

        The periodic flusher checks ``_running`` before its body, so stopping skipped exactly the
        final, unsent batch — measured 35 ticks lost in one stop/restart cycle (audit A-03).
        """
        for symbol in list(self._tick_buffers.keys()):
            batch = self._tick_buffers[symbol]
            if not batch:
                continue
            try:
                await self.db.insert_ticks_batch(symbol, batch)
            except Exception as exc:                 # noqa: BLE001
                self._db_write_failures += 1
                logger.warning("final tick flush failed for %s: %s", symbol, exc)
            finally:
                self._tick_buffers[symbol] = []

    def _download_mt5_history_sync(self):
        """
        Download historical 1-minute bars from MT5 and inject into candle builders.
        Runs synchronously before the event loop starts so candles are always available.
        """
        if not self.mt5_feed or not self.mt5_feed._mt5:
            logger.warning("No MT5 connection — skipping history download")
            return

        mt5_mod = self.mt5_feed._mt5   # already-initialized MetaTrader5 module
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        from_date = now - timedelta(days=MT5.download_history_days)

        logger.info(
            f"Downloading M1 bars for {len(MT5.symbols)} instruments "
            f"({MT5.download_history_days}d)..."
        )

        total_added = 0
        for internal, mt5_sym in MT5.symbols.items():
            pipeline = self.pipelines.get(internal)
            if not pipeline:
                continue

            try:
                rates = mt5_mod.copy_rates_range(
                    mt5_sym, mt5_mod.TIMEFRAME_M1, from_date, now
                )

                if rates is None or len(rates) == 0:
                    logger.warning(f"[{internal}] No M1 bars for {mt5_sym}")
                    continue

                # Convert to Candle objects
                candles = []
                for r in rates:
                    candles.append(Candle(
                        timestamp_ms=int(r['time']) * 1000,
                        open=float(r['open']),
                        high=float(r['high']),
                        low=float(r['low']),
                        close=float(r['close']),
                        volume=float(
                            r['real_volume'] if r['real_volume'] > 0
                            else r['tick_volume']
                        ),
                        buy_volume=0.0,
                        sell_volume=0.0,
                        tick_count=int(r['tick_volume']),
                    ))

                added = pipeline.candle_builder.load_historical_candles(candles)
                total_added += added

                # Build VP from candle history
                today = now.strftime("%Y-%m-%d")
                all_candles = pipeline.candle_builder.history
                if all_candles:
                    vp = pipeline.vp_engine.compute_from_candles(
                        all_candles, session_date=today
                    )
                    if vp.total_volume > 0:
                        pipeline.profile_framing.add_profile(vp)

                logger.info(
                    f"[{internal}] +{added} M1 bars (total {len(all_candles)})"
                )

            except Exception as e:
                logger.error(
                    f"[{internal}] History download failed: {e}",
                    exc_info=True,
                )

        logger.info(
            f"History download complete: {total_added} total candles loaded"
        )

    async def _on_tick(self, symbol: str, tick: Tick):
        """Handle incoming tick."""
        pipeline = self.pipelines.get(symbol)
        if not pipeline:
            return

        await pipeline.process_tick(tick)

        # Broadcast to dashboard (throttled by ws_manager)
        await self.ws_manager.broadcast_tick(
            symbol, tick.price, tick.size, tick.side.value
        )

        # Bounded tape buffer for the dashboard's initial fill (/api/tape)
        self._recent_ticks.setdefault(
            symbol, deque(maxlen=self._recent_ticks_max)
        ).append(tick)

        # Buffer ticks for batch DB insert
        if symbol not in self._tick_buffers:
            self._tick_buffers[symbol] = []
        self._tick_buffers[symbol].append(tick)

        if len(self._tick_buffers[symbol]) >= self._tick_batch_size:
            # Guarded: this runs inside the venue's frame handler, and an escape from here is read
            # as a dead socket by the feed session — a transient "database is locked" used to tear
            # the whole websocket down (and every other symbol with it). The ticks were already
            # broadcast and buffered for the panels; the failed batch is counted and dropped.
            batch = self._tick_buffers[symbol]
            try:
                await self.db.insert_ticks_batch(symbol, batch)
            except Exception as exc:                 # noqa: BLE001
                self._db_write_failures += 1
                if self._db_write_failures in (1, 10, 100):
                    logger.warning("tick persistence failed (%d so far): %s",
                                   self._db_write_failures, exc)
            finally:
                batch.clear()
                self._tick_buffers[symbol] = []

    def recent_ticks(self, symbol: str, count: int = 200) -> list[Tick]:
        """Newest-last slice of the bounded tape buffer for *symbol*.

        Feeds `/api/tape` (initial tape fill) and burst metrics. Returns an empty
        list — never demo data — when nothing has streamed yet; the endpoint is
        responsible for the demo fallback and the `source` field.
        """
        if count <= 0:
            return []
        buf = self._recent_ticks.get(symbol)
        if not buf:
            return []
        return list(buf)[-count:]

    def recent_signals(self, symbol: str, count: int = 10) -> list[Signal]:
        """Most recent pattern signals for *symbol*, newest last."""
        if count <= 0:
            return []
        buf = self._recent_signals.get(symbol)
        if not buf:
            return []
        return list(buf)[-count:]

    async def _on_orderbook(self, symbol: str, snapshot: OrderbookSnapshot):
        """Handle orderbook update."""
        pipeline = self.pipelines.get(symbol)
        if not pipeline:
            return

        sweep_signal = await pipeline.process_orderbook(snapshot)

        # Broadcast orderbook to dashboard (throttled)
        await self.ws_manager.broadcast_orderbook(symbol, {
            "best_bid": snapshot.best_bid,
            "best_ask": snapshot.best_ask,
            "spread": snapshot.spread,
            "imbalance": round(snapshot.imbalance_ratio(), 4),
        })

        if sweep_signal:
            await self._handle_signal(symbol, pipeline, sweep_signal)

    async def _on_candle_signals(self, symbol: str, signals: list[Signal]):
        """Called by InstrumentPipeline callback when candle-close produces signals."""
        pipeline = self.pipelines.get(symbol)
        if not pipeline:
            return

        self._recent_signals.setdefault(
            symbol, deque(maxlen=self._recent_signals_max)
        ).extend(signals)

        for sig in signals:
            await self._handle_signal(symbol, pipeline, sig)

    async def _on_candle_closed(self, symbol: str, candle: Candle):
        """Persist + broadcast a closed candle. Called BY the pipeline.

        The pipeline invokes this AFTER its analytics pass; signals have already
        been routed through ``_on_signals_callback``. It deliberately does NOT
        call ``pipeline._on_candle_close`` again — doing so would run the
        analytics twice per candle (the historical wiring bug this replaces).
        """
        pipeline = self.pipelines.get(symbol)
        if not pipeline:
            return

        self._last_candles[symbol] = candle

        try:
            # Store candle
            await self.db.insert_candle(symbol, "1m", candle)

            # Broadcast candle to dashboard
            await self.ws_manager.broadcast_candle(symbol, {
                "time": candle.timestamp_ms / 1000,
                "open": round(candle.open, 6),
                "high": round(candle.high, 6),
                "low": round(candle.low, 6),
                "close": round(candle.close, 6),
                "volume": round(candle.volume, 2),
                "delta": round(candle.delta, 2),
            })

            # Broadcast cumulative delta
            await self.ws_manager.broadcast_delta(symbol, {
                "time": candle.timestamp_ms / 1000,
                "value": round(pipeline.delta_engine.cumulative_delta, 2),
                "bar_delta": round(candle.delta, 2),
            })
        except Exception:
            # A dashboard/DB hiccup must never take the feed down.
            logger.exception("candle persistence/broadcast failed for %s", symbol)

        # Level reads (fold-in plan §3): the closed bar feeds the atlas trackers — unfinished
        # auctions and node runs dispatch as events, so alert rules and the history see them
        # exactly like every other detection. Never let a tracker fault take the feed down.
        hub = getattr(self, "_atlas_hub", None)
        if hub is not None:
            try:
                history = getattr(pipeline.footprint_engine, "history", None) or []
                fp = history[-1] if history else None
                if fp is not None:
                    levels = {p: (lv.bid_volume, lv.ask_volume) for p, lv in fp.levels.items()}
                    hub.feed_bar(symbol, fp.timestamp_ms, levels,
                                 tick_size=getattr(pipeline.config, "tick_size", 0.0) or 0.0)
            except Exception:
                logger.exception("atlas level feed failed for %s", symbol)

    def _on_radar_level(self, symbol: str, level: object, price: float) -> None:
        """Every new radar level is offered to the signals machine (fold-in plan U3).

        Behind ``atlas.radar.feed_signals``: the machine's WATCHING pathway widens from profile
        qualifiers to nodes, unfinished magnets, virgin / HTF POCs, area POCs, VWAP bands and
        stacked zones — one level pipeline, not a second machine. Direction is the level's side:
        below price reads as support (buy the hold), above as resistance.
        """
        from orderflow_system.data.models import Side
        from orderflow_system.signals.profile_framing import LevelType, QualifiedLevel
        try:
            from orderflow_system.desktop import config_store

            cfg = config_store.load_config() or {}
        except Exception:
            cfg = {}
        radar_cfg = (cfg.get("atlas") or {}).get("radar") or {}
        if not bool(radar_cfg.get("feed_signals", True)):
            return
        kind = {"unfinished": LevelType.UNFINISHED, "node": LevelType.NODE,
                "virgin_poc": LevelType.VIRGIN_POC, "htf_poc": LevelType.HTF_POC,
                "area_poc": LevelType.AREA_POC, "vwap_band": LevelType.VWAP_BAND,
                "stacked": LevelType.STACKED}.get(str(getattr(level, "source", "")), None)
        if kind is None:
            return
        px = float(getattr(level, "price", 0.0) or 0.0)
        if not px:
            return
        ref = float(price or px)
        direction = Side.BUY if px <= ref else Side.SELL
        self.aggregator.set_watching(
            symbol,
            QualifiedLevel(price=px, level_type=kind, direction=direction,
                           strength=min(100.0, float(getattr(level, "strength", 0.0) or 0.0)),
                           notes="radar:" + str(getattr(level, "source", ""))),
            direction)

    async def _handle_signal(
        self, symbol: str, pipeline: InstrumentPipeline, signal: Signal
    ):
        """Route a signal through the aggregator and send alerts.

        MEM-A1-09: both halves are guarded with the same rule as the tick path (:671-685) —
        this runs inside the venue's frame handler (orderbook sweeps) and the candle-close
        callback, and one transient persistence or alert error must not escape into the feed
        loop (the tick path was hardened for exactly this; the signal path was not).
        """
        # Store raw signal
        try:
            await self.db.insert_signal(symbol, signal)
        except Exception as exc:                     # noqa: BLE001
            self._db_write_failures += 1
            if self._db_write_failures in (1, 10, 100):
                logger.warning("signal persistence failed (%d so far): %s",
                               self._db_write_failures, exc)

        # Get current bias
        bias = pipeline.profile_framing.current_bias

        try:
            # Aggregate with context
            agg = self.aggregator.process_signal(
                instrument=symbol,
                signal=signal,
                bias=bias,
                current_price=pipeline.current_price,
                recent_candles=pipeline.candle_builder.get_recent_candles(5),
            )

            if agg:
                trade = self.aggregator.get_active_trade(symbol)
                await self.telegram.send_signal_alert(symbol, agg, bias, trade)

                # Broadcast signal + trade state to dashboard
                await self.ws_manager.broadcast_signal(symbol, agg)
                if trade:
                    await self.ws_manager.broadcast_trade_state(symbol, trade)
        except Exception as exc:                     # noqa: BLE001
            self._db_write_failures += 1
            logger.warning("signal handling failed for %s: %s", symbol, exc)

    def _on_alpaca_bar(self, symbol: str, candle) -> None:
        """Seeded REST bars feed the chart's own bar series — never the tick store (audit D-07)."""
        pipeline = self.pipelines.get(symbol)
        if pipeline is not None:
            pipeline.candle_builder.load_historical_candles([candle])

    async def _run_alpaca_feed(self):
        """Seed the history, then start the streams (a fresh chart reads as broken)."""
        try:
            bars = await self.alpaca_feed.seed_history()
            logger.info("Alpaca history seeded: %d bars", bars)
        except Exception as exc:                      # noqa: BLE001 — history is a bonus
            logger.warning("Alpaca history seeding failed: %s", exc)
        await self.alpaca_feed.start()
        # keep the task alive with the feed's own lifetime
        while self._running:
            await asyncio.sleep(1.0)

    async def _periodic_tasks(self):
        """Run periodic tasks: VP rebuild, bias update, stats logging."""
        profile_interval = 3600       # Rebuild VP every hour
        stats_interval = 15           # Broadcast stats every 15 sec
        # R6: retention and the backup job re-read the config each pass, so a number typed in
        # Settings ▸ Storage is in force within a minute — not at the next restart.
        from orderflow_system.desktop import config_store as _config_store
        from orderflow_system.desktop.engine import clamp_data_settings as _clamp_data

        _sh, _rd, _ph = _clamp_data(_config_store.load_config())
        prune_interval = max(1, _ph) * 3600
        storage_interval = 1800        # a usage sample + the due-backup check every 30 min
        calendar_interval = 300        # R11: event alerts are checked every 5 min
        last_calendar = 0
        last_profile = 0
        last_stats = 0
        last_prune = -prune_interval   # R5: the first pass prunes (when retention is enabled)
        last_storage = -storage_interval   # R6: so the first pass samples as soon as it can

        while self._running:
            await asyncio.sleep(10)
            now = asyncio.get_event_loop().time()
            # G-05: re-clamp inside the loop — the comment above claims a number typed in Settings
            # is in force within a minute, but the interval was bound once at loop entry.
            try:
                _sh, _rd, _ph = _clamp_data(_config_store.load_config())
                prune_interval = max(1, _ph) * 3600
            except Exception:                        # noqa: BLE001 — keep the last good interval
                pass

            # Flush remaining tick buffers. Guarded per symbol: this loop also rebuilds the volume
            # profiles, runs retention and broadcasts stats, and one failing write must not end it
            # (an unhandled raise here stopped all of that silently for the rest of the session).
            for symbol in list(self._tick_buffers.keys()):
                if not self._tick_buffers[symbol]:
                    continue
                try:
                    await self.db.insert_ticks_batch(symbol, self._tick_buffers[symbol])
                except Exception as exc:             # noqa: BLE001
                    self._db_write_failures += 1
                    logger.warning("buffered tick flush failed for %s: %s", symbol, exc)
                finally:
                    self._tick_buffers[symbol] = []

            # Periodic VP rebuild. MEM-A1-01: guarded per symbol like every other job in
            # this loop — this call was the one unguarded path (a locked/read-only DB here
            # used to end the periodic loop), and it is what a transient DB error hits first.
            if now - last_profile > profile_interval:
                last_profile = now
                for symbol, pipeline in self.pipelines.items():
                    try:
                        await self._rebuild_volume_profile(symbol, pipeline)
                    except Exception as exc:          # noqa: BLE001
                        logger.warning("volume-profile rebuild failed for %s: %s", symbol, exc)

            # R11: the economic calendar's event alerts (off unless switched on in the panel)
            if now - last_calendar > calendar_interval:
                last_calendar = now
                try:
                    await self._calendar_tick()
                except Exception as exc:                   # noqa: BLE001
                    logger.debug("calendar alert check failed: %s", exc)

            # R6: storage management — the usage sample, the size budget and the scheduled backup
            if now - last_storage > storage_interval:
                last_storage = now
                try:
                    await self._storage_tick()
                except Exception as exc:                   # noqa: BLE001
                    logger.warning("storage job failed: %s", exc)

            # R5: storage retention — prune on its own interval; never kill the loop over it
            if now - last_prune > prune_interval:
                last_prune = now
                try:
                    await self._prune_storage()
                except Exception as exc:                   # noqa: BLE001
                    logger.warning("storage retention prune failed: %s", exc)

            # Stats logging
            if now - last_stats > stats_interval:
                last_stats = now
                all_stats = []
                for symbol, pipeline in self.pipelines.items():
                    stats = pipeline.stats
                    logger.info(
                        f"[{symbol}] price={stats['price']:.2f} "
                        f"ticks={stats['ticks']} candles={stats['candles']} "
                        f"cum_delta={stats['cum_delta']:.1f}"
                    )
                    all_stats.append(stats)

                # Broadcast system-wide stats
                await self.ws_manager.broadcast_stats({
                    "data_source": self.data_source.value,
                    "ws_clients": self.ws_manager.client_count,
                    "instruments": all_stats,
                })

                # Broadcast per-symbol stats so dashboard updates per tab
                for symbol, pipeline in self.pipelines.items():
                    await self.ws_manager.broadcast(
                        "stats", pipeline.stats, symbol=symbol
                    )

    async def _prune_storage(self) -> dict:
        """R5: delete ticks older than the retention window, vacuum incrementally, and report
        the numbers (rows deleted, bytes before/after) — the same summary the API returns."""
        # Live, not boot-time: a window typed in Settings ▸ Storage takes effect on the next pass.
        from orderflow_system.desktop import config_store
        from orderflow_system.desktop.engine import clamp_data_settings

        _sh, days, _ph = clamp_data_settings(config_store.load_config())
        if days <= 0:
            return {"skipped": "retention_days=0 — nothing pruned"}
        cutoff_ms = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
        before = await self.db.storage_snapshot()
        instruments = await self.db.tick_instruments() or list(self.pipelines.keys())
        deleted = await self.db.prune_ticks(cutoff_ms, instruments)
        others = await self.db.prune_other_tables(cutoff_ms)
        # Free pages are worth converting for even when nothing was deleted today: until
        # `auto_vacuum=INCREMENTAL` is set (a one-time conversion, guarded by the database against
        # a full volume) `incremental_vacuum` is a documented no-op, so every page a prune or a
        # profile rewrite frees stays in the file for good — measured on this machine as a
        # file-only-ever-grows store.
        reclaimable = int(before.get("freelist_pages") or 0) * int(before.get("page_size") or 0)
        vacuum = await self.db.ensure_incremental_autovacuum() if (deleted or reclaimable) else "skipped"
        if deleted or reclaimable:
            await self.db.vacuum_incremental()
        else:
            # MEM-A2-10: a pass that deleted nothing still checkpoints what it can, so the WAL
            # does not grow between the passes that do truncate.
            await self.db.checkpoint_passive()
        after = await self.db.storage_snapshot()
        summary = {
            "at_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "retention_days": days, "cutoff_ms": cutoff_ms, "deleted": deleted,
            "other_deleted": others,
            "vacuum": vacuum,
            "bytes_before": before["bytes"] + before.get("wal_bytes", 0),
            "bytes_after": after["bytes"] + after.get("wal_bytes", 0),
            "rows_before": before["tables"].get("ticks", 0),
            "rows_after": after["tables"].get("ticks", 0),
        }
        self._last_prune = summary
        try:                                       # survives the restart the panel would forget
            from orderflow_system.desktop import config_store

            config_store.save_last_prune(summary)
        except Exception:                          # noqa: BLE001 - a summary is not worth a failure
            logger.debug("could not persist the prune summary", exc_info=True)
        logger.info(
            "[storage] retention %d d: deleted %d tick rows (%d -> %d rows, %.1f -> %.1f MB), "
            "other=%s, vacuum=%s",
            days, deleted, summary["rows_before"], summary["rows_after"],
            summary["bytes_before"] / 1e6, summary["bytes_after"] / 1e6, others, vacuum,
        )
        return summary

    async def _storage_tick(self) -> dict:
        """R6: sample usage, hold the size budget, then run the scheduled backup if it is due.

        The backup target is whatever path the user set — folder, UNC share, removable drive,
        synced folder — and it is validated by writing, so an unreachable share ends up as a log
        line with the operating system's reason instead of a silent gap in the history.
        """
        import json
        import time as _time

        from orderflow_system.desktop import config_store, storage as storage_mod

        cfg = config_store.load_config()
        settings = storage_mod.clamp_storage_settings(cfg)
        config_dir = config_store.config_dir()
        db_path = config_store.db_path()
        target = storage_mod.resolved_target(settings, config_dir)

        usage = await asyncio.to_thread(storage_mod.usage_snapshot, db_path,
                                        config_dir=config_dir, target=target)
        store_path = storage_mod.usage_store_path(config_dir)
        store = storage_mod.record_sample(store_path, usage["db_bytes"] + usage["wal_bytes"])
        now_epoch = _time.time()

        message = storage_mod.threshold_message(usage, settings)
        if message and now_epoch - float(store.get("last_threshold_warn") or 0) > 86400:
            store["last_threshold_warn"] = now_epoch
            try:                                       # at most one budget alert a day
                store_path.write_text(json.dumps(store, separators=(",", ":")), encoding="utf-8")
            except OSError:
                pass
            await self._send_storage_alert(message, settings, cfg)

        backups = await asyncio.to_thread(storage_mod.list_backups, target)
        due = bool(settings["auto_backup"]) and (
            not backups
            or storage_mod.backup_age_seconds(backups[0], target, now=now_epoch)
            >= int(settings["backup_interval_hours"]) * 3600)
        if due:
            try:
                manifest = await asyncio.to_thread(storage_mod.run_backup, db_path, target,
                                                   fmt=settings["backup_format"],
                                                   keep=int(settings["backup_keep"]))
                logger.info("[storage] scheduled backup: %s (%.1f MB, kept %d)",
                            manifest["folder"], manifest["bytes"] / 1e6, settings["backup_keep"])
                if manifest.get("removed"):
                    logger.info("[storage] rotated out: %s", ", ".join(manifest["removed"]))
                if settings["email_report"]:
                    result = await self._email_storage_report(cfg, settings)
                    logger.info("[storage] report email: %s", "sent" if result.get("ok") else result.get("error"))
            except storage_mod.StorageError as exc:
                logger.warning("[storage] scheduled backup failed: %s", exc)
        return {"usage_db_bytes": usage["db_bytes"] + usage["wal_bytes"],
                "backups": len(backups), "backup_due": bool(due)}

    async def _calendar_tick(self) -> None:
        """R11: alert ahead of high-impact events, through the channels already configured.

        Once per event, ever: the key is remembered on the instance, so a restart re-arms the lead
        window but an event that already fired an alert never fires another.
        """
        import time as _time
        from pathlib import Path as _Path

        from orderflow_system.desktop import calendar as calendar_mod
        from orderflow_system.desktop import config_store

        cfg = config_store.load_config()
        block = dict(cfg.get("calendar") or {})
        if not block.get("alerts"):
            return
        try:
            lead = max(1, min(240, int(block.get("lead_minutes") or 15)))
        except (TypeError, ValueError):
            lead = 15
        wanted = {c.strip().upper() for c in str(block.get("currencies") or "").split(",") if c.strip()}
        alerted: set = getattr(self, "_calendar_alerted", None)
        if alerted is None:
            alerted = set()
            self._calendar_alerted = alerted
        payload = await asyncio.to_thread(calendar_mod.fetch_events_cached,
                                          _Path(config_store.config_dir()) / "calendar-cache.json",
                                          ttl_s=4 * 3600)
        events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
        due = calendar_mod.due_alerts(events, now_ms=int(_time.time() * 1000), lead_minutes=lead,
                                      alerted_keys=alerted)
        for event in due:
            key = calendar_mod.event_key(event)
            if key in alerted:
                continue
            if wanted and str(event.get("currency") or "").upper() not in wanted:
                continue
            alerted.add(key)
            if len(alerted) > 2000:                    # a week of events, with room to spare
                self._calendar_alerted = set(list(alerted)[-1000:])
                alerted = self._calendar_alerted
            await self._send_storage_alert(
                {"kind": "calendar", "severity": "warning", "symbol": "",
                 "channels": ["ui", "telegram", "ntfy", "email"],
                 "message": calendar_mod.event_message(event)},
                {"email_threshold": False}, cfg)

    async def _send_storage_alert(self, message: dict, settings: dict, cfg: dict) -> None:
        """One alert about storage, to the channels the user already configured.

        The email branch is the report itself (a graph beats a sentence); telegram/ntfy get the
        one-line message, so a full mailbox never costs the alert entirely.
        """
        logger.warning("[storage] %s", message.get("message", ""))
        hub = getattr(self, "_atlas_hub", None)
        notifier = getattr(hub, "notifier", None)
        sent: list[str] = []
        for name in list(getattr(notifier, "channels", {}) or {}):
            if name == "email" and settings.get("email_threshold"):
                continue                               # the report email below is the better message
            try:
                if (await notifier.send_one(name, message)).get("ok"):
                    sent.append(name)
            except Exception as exc:                   # noqa: BLE001 - an alert is never worth a raise
                logger.debug("storage alert via %s failed: %s", name, exc)
        if settings.get("email_threshold"):
            result = await self._email_storage_report(cfg, settings, extra_line=str(message.get("message") or ""))
            if result.get("ok"):
                sent.append("email")
        logger.info("[storage] size-budget alert reached: %s", ", ".join(sent) or "the log only")

    async def _email_storage_report(self, cfg: dict, settings: dict, *, extra_line: str = "") -> dict:
        """Email the storage report: plain text + a one-metric-per-row CSV attachment."""
        from orderflow_system.desktop import config_store, storage as storage_mod

        config_dir = config_store.config_dir()
        target = storage_mod.resolved_target(settings, config_dir)
        usage = await asyncio.to_thread(storage_mod.usage_snapshot, config_store.db_path(),
                                        config_dir=config_dir, target=target)
        store = storage_mod.load_usage_store(storage_mod.usage_store_path(config_dir))
        days = int(getattr(runtime_settings, "RETENTION_DAYS", 0) or 0)
        growth = storage_mod.growth_report(store.get("samples", []),
                                           usage["db_bytes"] + usage["wal_bytes"], retention_days=days)
        subject, body, csv_text = storage_mod.build_report(
            usage, growth,
            {"days": days, "prune_interval_hours": getattr(runtime_settings, "PRUNE_INTERVAL_HOURS", 0),
             "session_start_hour": getattr(runtime_settings, "SESSION_START_HOUR", 0)},
            await asyncio.to_thread(storage_mod.list_backups, target),
            getattr(self, "_last_prune", None))
        if extra_line:
            subject = "[OrderFlow] storage over budget"
            body = extra_line + "\n\n" + body
        return await storage_mod.email_report(cfg, subject, body, attachments=[
            ("storage-summary.csv", csv_text.encode("utf-8"), "text/csv")])

    async def _rebuild_volume_profile(
        self, symbol: str, pipeline: InstrumentPipeline
    ):
        """Rebuild volume profile from recent candle data."""
        # Get today's candles from DB
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        # R4: the profile covers the CONFIGURED SESSION, not a rolling 24 h wearing a date
        # label — at the UTC boundary the old window mixed two sessions into "today's" value area.
        start_ms, _end_ms, session_label = session_window(
            now_ms, int(getattr(runtime_settings, "SESSION_START_HOUR", 0) or 0)
        )

        candles = await self.db.get_candles(symbol, "1m", start_ms, now_ms)
        if len(candles) < 10:
            return

        vp = pipeline.vp_engine.compute_from_candles(candles, session_date=session_label)

        if vp.total_volume > 0:
            pipeline.profile_framing.add_profile(vp)
            await self.db.insert_volume_profile(symbol, vp)
            bias = pipeline.profile_framing.analyze(pipeline.current_price)
            logger.info(
                f"[{symbol}] VP rebuilt: POC={vp.poc:.2f} "
                f"VAH={vp.vah:.2f} VAL={vp.val:.2f} "
                f"Shape={vp.shape} | Bias={bias.direction.value}"
                + (f" | derived: {vp.derived_candles} candles without footprint" if vp.derived_candles else "")
            )

            # Broadcast VP + bias to dashboard
            await self.ws_manager.broadcast_volume_profile(symbol, {
                "poc": vp.poc,
                "vah": vp.vah,
                "val": vp.val,
                "shape": vp.shape,
                "total_volume": vp.total_volume,
                "lvn_levels": vp.lvn_levels,
                "derived_candles": int(vp.derived_candles or 0),   # SEC-14: fabricated share, on the wire
                "volume_at_price": {
                    str(p): v for p, v in sorted(vp.volume_at_price.items())
                },
            })
            await self.ws_manager.broadcast_bias(symbol, bias)

            # Auto-watch qualified levels
            for level in bias.qualified_levels:
                if level.strength >= 50:
                    self.aggregator.set_watching(
                        symbol, level, level.direction
                    )

            # Level radar (fold-in plan §4 / G1): the stored profiles' virgin POCs and the
            # weekly / monthly POC ladder register as tracked levels — the same sources the
            # levels endpoint serves, so the radar and the endpoint cannot disagree. Each new
            # registration rides the level hook into the signals machine (U3), behind config.
            hub = getattr(self, "_atlas_hub", None)
            if hub is not None:
                try:
                    profiles = await self.db.get_volume_profiles(symbol, days=30)
                    from orderflow_system.atlas.profiles import period_pocs, virgin_pocs

                    import time as _time

                    feats = hub.ensure(symbol)
                    now_ms = int(_time.time() * 1000)
                    for row in virgin_pocs(profiles, current_price=pipeline.current_price):
                        hub._radar_register(symbol, feats, row.get("poc"), "virgin_poc", now_ms, 70.0)
                    for row in period_pocs(profiles, "week"):
                        hub._radar_register(symbol, feats, row.get("poc"), "htf_poc", now_ms, 75.0)
                    for row in period_pocs(profiles, "month"):
                        hub._radar_register(symbol, feats, row.get("poc"), "htf_poc", now_ms, 80.0)
                except Exception:
                    logger.debug("radar profile registration failed for %s", symbol, exc_info=True)


def setup_logging():
    """Configure logging for the system.

    The log lives in the per-user config directory with the database, never beside the code: this
    entry point is spawned by the app's own "Run → CLI" button with the working directory set to
    the checkout, and a relative path had been depositing an unbounded log — and, through the
    relative DB_PATH, a stray database — into the repo. Rotation matches the desktop's:
    2 MB a file, four kept, so a collector left running can never fill the disk.
    """
    from logging.handlers import RotatingFileHandler

    try:
        from orderflow_system.desktop import config_store

        log_file = os.path.join(str(config_store.config_dir()), "orderflow_system.log")
    except Exception:                              # pragma: no cover - desktop package absent
        log_file = "orderflow_system.log"
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=4, encoding="utf-8"),
        ],
    )


def main():
    """Entry point."""
    setup_logging()

    logger.info(f"Data source: {DATA_SOURCE.value.upper()}")
    if DATA_SOURCE in (DataSource.MT5, DataSource.BOTH):
        logger.info(f"MT5 symbols: {MT5.symbols}")
        logger.info(
            "Make sure MetaTrader 5 is running and logged into your broker account."
        )

    system = OrderflowSystem(data_source=DATA_SOURCE)

    # Handle Ctrl+C gracefully
    loop = asyncio.new_event_loop()

    def shutdown_handler():
        logger.info("Received shutdown signal...")
        loop.create_task(system.stop())

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown_handler)

    try:
        loop.run_until_complete(system.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        loop.run_until_complete(system.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
