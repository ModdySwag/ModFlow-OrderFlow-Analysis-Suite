"""
Bybit WebSocket data feed — connects to public aggTrade + orderbook depth streams.
Free, no API key needed for public data.
Provides tick-by-tick trades with aggressor side and L2 orderbook updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable, Optional

import websockets

from orderflow_system.data.models import Tick, Side, OrderbookSnapshot, OrderbookLevel

logger = logging.getLogger(__name__)

BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"


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
        self._tick_buffer: dict[str, list[Tick]] = {s: [] for s in symbols}
        self._reconnect_delay = 1.0

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
            logger.info(f"Connected to Bybit WebSocket")

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
            tick = Tick(
                timestamp_ms=trade.get("T", int(time.time() * 1000)),
                price=float(trade.get("p", 0)),
                size=float(trade.get("v", 0)),
                side=Side.BUY if side_str == "Buy" else Side.SELL,
                trade_id=trade.get("i", ""),
            )

            self._tick_buffer[symbol].append(tick)

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
            bids = [
                OrderbookLevel(price=float(b[0]), quantity=float(b[1]))
                for b in data.get("b", [])
            ]
            asks = [
                OrderbookLevel(price=float(a[0]), quantity=float(a[1]))
                for a in data.get("a", [])
            ]
            self._orderbooks[symbol] = OrderbookSnapshot(
                timestamp_ms=ts,
                bids=sorted(bids, key=lambda x: -x.price),
                asks=sorted(asks, key=lambda x: x.price),
            )
        elif msg_type == "delta":
            book = self._orderbooks.get(symbol)
            if book is None:
                return
            self._apply_delta(book, data)
            book.timestamp_ms = ts

        if symbol in self._orderbooks and self.on_orderbook:
            await self.on_orderbook(symbol, self._orderbooks[symbol])

    def _apply_delta(self, book: OrderbookSnapshot, data: dict):
        """Apply incremental orderbook updates."""
        # Update bids
        for b in data.get("b", []):
            price, qty = float(b[0]), float(b[1])
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
        for a in data.get("a", []):
            price, qty = float(a[0]), float(a[1])
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

    def flush_tick_buffer(self, symbol: str) -> list[Tick]:
        """Return and clear buffered ticks for batch DB insert."""
        ticks = self._tick_buffer.get(symbol, [])
        self._tick_buffer[symbol] = []
        return ticks
