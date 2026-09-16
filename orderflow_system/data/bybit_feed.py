"""
Bybit WebSocket data feed — connects to public aggTrade + orderbook depth streams.
Free, no API key needed for public data.
Provides tick-by-tick trades with aggressor side and L2 orderbook updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from typing import Any, Callable, Optional

import websockets

from orderflow_system.data.models import Tick, Side, OrderbookSnapshot, OrderbookLevel

logger = logging.getLogger(__name__)

BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"


def _update_id(data: dict) -> int:
    """Bybit's `u` — the update id deltas must arrive consecutively against. Absent means 0, which no
    real delta carries, so a malformed message cannot advance the sequence."""
    try:
        return int(data.get("u") or 0)
    except (TypeError, ValueError):
        return 0


def _finite(value: Any) -> Optional[float]:
    """A JSON number that is safe to carry, or None.

    ``json`` accepts the bare tokens ``NaN``/``Infinity``, and every comparison with NaN is
    False — so `float(x) <= 0` cannot catch one and the value would sail into the aggregates
    unguarded. This is the one gate every venue value passes first.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _level(pair: Any) -> Optional["OrderbookLevel"]:
    """One venue ``[price, qty]`` pair → OrderbookLevel, or None when the value is unusable."""
    try:
        price, qty = _finite(pair[0]), _finite(pair[1])
    except (TypeError, IndexError, KeyError):
        return None
    if price is None or qty is None or price <= 0 or qty < 0:
        return None
    return OrderbookLevel(price=price, quantity=qty)


class BybitFeed:
    """
    Real-time data feed from Bybit perpetual futures.
    Subscribes to:
      - publicTrade.<symbol>  → Tick data with aggressor side
      - orderbook.50.<symbol> → 50-level L2 orderbook snapshots + deltas
    """

    def __init__(
        self,
        symbols: list[str],
        on_tick: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
    ):
        self.symbols = symbols
        self.on_tick = on_tick
        self.on_orderbook = on_orderbook
        self._ws = None
        self._running = False
        self._orderbooks: dict[str, OrderbookSnapshot] = {}
        self._reconnect_delay = 1.0
        # Sequence integrity: Bybit's `u` is an update id, and the local book is only valid while the
        # deltas are consecutive. Tracked per symbol, with counters the status line can quote.
        self._book_seq: dict[str, int] = {}
        self._book_stale: set[str] = set()
        self._book_gaps = 0
        self._deltas_dropped = 0
        # Venue values refused as unusable (NaN/Infinity/negative — json carries the bare
        # tokens and comparisons cannot catch them). Counted so a bad socket is visible.
        self._junk_values = 0
        # One warning per connection when a trade arrives without the venue's own T stamp
        self._ts_fallback_warned = False

    async def start(self):
        """Connect and begin receiving data."""
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except (
                websockets.ConnectionClosed,
                ConnectionRefusedError,
                OSError,
            ) as e:
                logger.warning(f"WebSocket disconnected: {e}. Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)
            except Exception as e:
                logger.error(f"Unexpected error in feed: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_listen(self):
        async with websockets.connect(BYBIT_WS_URL, ping_interval=20) as ws:
            self._ws = ws
            self._reconnect_delay = 1.0
            self._ts_fallback_warned = False          # a fresh connection may say it again
            logger.info("Connected to Bybit WebSocket")

            # Subscribe to trades + orderbook for each symbol
            subscribe_args = []
            for sym in self.symbols:
                subscribe_args.append(f"publicTrade.{sym}")
                subscribe_args.append(f"orderbook.50.{sym}")

            subscribe_msg = {
                "op": "subscribe",
                "args": subscribe_args,
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to: {subscribe_args}")

            async for raw_msg in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw_msg)
                    await self._handle_message(msg)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {raw_msg[:100]}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)

    async def _handle_message(self, msg: dict):
        topic = msg.get("topic", "")

        if topic.startswith("publicTrade."):
            await self._handle_trades(msg)
        elif topic.startswith("orderbook."):
            await self._handle_orderbook(msg)

    async def _handle_trades(self, msg: dict):
        """
        Parse Bybit public trade messages.
        Each trade has: price, size, side (Buy/Sell), timestamp.
        The 'side' from Bybit = the TAKER side = the aggressor.
        """
        data_list = msg.get("data", [])
        symbol = msg.get("topic", "").replace("publicTrade.", "")

        for trade in data_list:
            side_str = trade.get("S", "")
            price = _finite(trade.get("p"))
            size = _finite(trade.get("v"))
            if price is None or price <= 0 or size is None or size < 0:
                # One malformed print (NaN/Infinity/negative/zero price) would poison the
                # footprint, delta and CVD aggregates downstream without ever raising, so it
                # is dropped here and counted — never substituted with something plausible.
                self._junk_values += 1
                continue
            ts = trade.get("T")
            if ts is None:
                # Defensive, not expected: Bybit stamps publicTrade with T. A silent
                # wall-clock substitution would drift session boundaries and the VP session
                # window, so say it once per connection instead of pretending the venue
                # clock agreed.
                if not self._ts_fallback_warned:
                    self._ts_fallback_warned = True
                    logger.warning(
                        "Bybit trade without T (venue time) — falling back to the local clock; "
                        "timestamps are loose until the next reconnect")
                ts = int(time.time() * 1000)
            tick = Tick(
                timestamp_ms=int(ts),
                price=price,
                size=size,
                side=Side.BUY if side_str == "Buy" else Side.SELL,
                trade_id=trade.get("i", ""),
            )

            if self.on_tick:
                await self.on_tick(symbol, tick)

    async def _handle_orderbook(self, msg: dict):
        """
        Parse Bybit orderbook messages.
        Type 'snapshot' = full book replacement.
        Type 'delta' = incremental update.
        """
        data = msg.get("data", {})
        msg_type = msg.get("type", "")
        topic = msg.get("topic", "")
        symbol = topic.split(".")[-1] if "." in topic else ""
        ts = data.get("u", int(time.time() * 1000))

        if msg_type == "snapshot":
            raw_bids = data.get("b") or []
            raw_asks = data.get("a") or []
            bids = [lv for lv in map(_level, raw_bids) if lv is not None]
            asks = [lv for lv in map(_level, raw_asks) if lv is not None]
            self._junk_values += (len(raw_bids) - len(bids)) + (len(raw_asks) - len(asks))
            self._orderbooks[symbol] = OrderbookSnapshot(
                timestamp_ms=ts,
                bids=sorted(bids, key=lambda x: -x.price),
                asks=sorted(asks, key=lambda x: x.price),
            )
            # A snapshot is the only thing that makes the book trustworthy again, so it is what
            # clears the stale mark and re-seeds the sequence.
            self._book_seq[symbol] = _update_id(data)
            self._book_stale.discard(symbol)
        elif msg_type == "delta":
            book = self._orderbooks.get(symbol)
            if book is None:
                return
            if symbol in self._book_stale:
                self._deltas_dropped += 1
                return                          # waiting for the snapshot; nothing to apply onto
            u = _update_id(data)
            seq = self._book_seq.get(symbol)
            if seq is None:
                return
            if u <= seq:
                # A duplicate or a late delta: applying it would write an old state over a newer one.
                self._deltas_dropped += 1
                return
            if u > seq + 1:
                # A gap. The local book no longer reflects the venue: mark it, drop what follows until
                # a fresh snapshot arrives, and ask for one. A wrong book is worse than no book.
                self._book_stale.add(symbol)
                self._book_gaps += 1
                book.stale = True
                logger.warning(
                    "orderbook %s: sequence gap (%s → %s) — marked stale and re-subscribed for a "
                    "fresh snapshot", symbol, seq, u)
                await self._resubscribe_book(symbol)
                if self.on_orderbook:
                    await self.on_orderbook(symbol, book)
                return
            self._apply_delta(book, data)
            self._book_seq[symbol] = u
            book.timestamp_ms = ts

        if symbol in self._orderbooks and self.on_orderbook:
            await self.on_orderbook(symbol, self._orderbooks[symbol])

    async def _resubscribe_book(self, symbol: str) -> bool:
        """Ask the venue for a fresh snapshot for one book.

        Bybit answers a re-subscribe with a new snapshot for the topic, which is the only thing that
        makes the local book trustworthy again. A dead socket is not an error here: the reconnect path
        subscribes everything anyway.
        """
        ws = self._ws
        if ws is None:
            return False
        try:
            await ws.send(json.dumps({"op": "subscribe", "args": [f"orderbook.50.{symbol}"]}))
            return True
        except Exception as exc:                              # pragma: no cover - socket errors
            logger.warning("orderbook %s: re-subscribe failed (%s) — waiting for the reconnect",
                           symbol, exc)
            return False

    def book_health(self) -> dict:
        """Sequence health per symbol — what a status line needs to say 'stale' honestly."""
        return {
            "stale": sorted(self._book_stale),
            "gaps": self._book_gaps,
            "dropped_deltas": self._deltas_dropped,
            "junk_values": self._junk_values,
            "seq": dict(self._book_seq),
        }

    def _apply_delta(self, book: OrderbookSnapshot, data: dict):
        """Apply incremental orderbook updates (non-finite or negative values are refused)."""
        # Update bids
        for b in data.get("b") or []:
            lv = _level(b)
            if lv is None:
                self._junk_values += 1
                continue
            price, qty = lv.price, lv.quantity
            if qty == 0:
                book.bids = [lv for lv in book.bids if lv.price != price]
            else:
                found = False
                for lv in book.bids:
                    if lv.price == price:
                        lv.quantity = qty
                        found = True
                        break
                if not found:
                    book.bids.append(OrderbookLevel(price=price, quantity=qty))
                book.bids.sort(key=lambda x: -x.price)

        # Update asks
        for a in data.get("a") or []:
            lv = _level(a)
            if lv is None:
                self._junk_values += 1
                continue
            price, qty = lv.price, lv.quantity
            if qty == 0:
                book.asks = [lv for lv in book.asks if lv.price != price]
            else:
                found = False
                for lv in book.asks:
                    if lv.price == price:
                        lv.quantity = qty
                        found = True
                        break
                if not found:
                    book.asks.append(OrderbookLevel(price=price, quantity=qty))
                book.asks.sort(key=lambda x: x.price)

    def get_orderbook(self, symbol: str) -> Optional[OrderbookSnapshot]:
        return self._orderbooks.get(symbol)
