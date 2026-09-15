"""
WebSocket Connection Manager
Manages connected clients and broadcasts real-time data from the orderflow system.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class Channel(str, Enum):
    """WebSocket broadcast channels."""
    TICK = "tick"
    CANDLE = "candle"
    SIGNAL = "signal"
    TRADE_STATE = "trade_state"
    VOLUME_PROFILE = "volume_profile"
    BIAS = "bias"
    ORDERBOOK = "orderbook"
    DELTA = "delta"
    STATS = "stats"
    SEARCH = "search"          # batched palette rows (see desktop/search_service.py)


def _serialize(obj: Any) -> Any:
    """Recursively serialize dataclasses, enums, and other types to JSON-safe dicts."""
    if obj is None:
        return None
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for k, v in asdict(obj).items():
            result[k] = _serialize(v)
        return result
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, float):
        if obj != obj:  # NaN check
            return 0.0
        return round(obj, 6)
    return obj


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts data to all connected clients.
    Thread-safe via asyncio — all operations run on the event loop.
    """

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

        # Throttle: channel → {symbol → last_broadcast_time}
        self._last_broadcast: dict[str, dict[str, float]] = {}
        self._throttle_ms: dict[str, int] = {
            Channel.TICK: 200,           # Max 5 ticks/sec per symbol
            Channel.CANDLE: 0,           # No throttle — only on close
            Channel.SIGNAL: 0,           # Never throttle signals
            Channel.TRADE_STATE: 0,
            Channel.VOLUME_PROFILE: 0,
            Channel.BIAS: 0,
            Channel.ORDERBOOK: 500,      # Max 2 book updates/sec
            Channel.DELTA: 200,
            Channel.STATS: 5000,         # Max every 5s
            # The palette sends one batched message per window (300 ms) rather than a
            # message per tick, so the channel throttle stays out of the way: the
            # batching is the pacing mechanism, and it protects the stream from the
            # slow-client disconnect (Alpaca code 407).
            Channel.SEARCH: 0,
        }

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket):
        """Accept and register a new WebSocket client."""
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info(f"Dashboard client connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket):
        """Remove a disconnected client."""
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info(f"Dashboard client disconnected. Total: {len(self._connections)}")

    async def broadcast(
        self,
        channel: str | Channel,
        data: Any,
        symbol: str = "",
    ):
        """
        Broadcast a message to all connected clients.
        Automatically serializes dataclasses, enums, etc.
        Applies per-channel throttling.
        """
        if not self._connections:
            return

        # Throttle check
        ch = channel.value if isinstance(channel, Channel) else channel
        throttle = self._throttle_ms.get(ch, 0)
        if throttle > 0 and symbol:
            now = time.time() * 1000
            ch_times = self._last_broadcast.setdefault(ch, {})
            last = ch_times.get(symbol, 0)
            if now - last < throttle:
                return
            ch_times[symbol] = now

        # Serialize
        payload = {
            "channel": ch,
            "symbol": symbol,
            "data": _serialize(data),
            "ts": int(time.time() * 1000),
        }

        message = json.dumps(payload)

        # Broadcast to all, collect dead connections
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self._connections.remove(ws)

        if dead:
            logger.debug(f"Removed {len(dead)} dead WebSocket connection(s)")

    async def broadcast_tick(self, symbol: str, price: float, size: float, side: str):
        """Broadcast a tick update (throttled)."""
        await self.broadcast(
            Channel.TICK,
            {"price": price, "size": size, "side": side},
            symbol=symbol,
        )

    async def broadcast_candle(self, symbol: str, candle_data: dict):
        """Broadcast a closed candle."""
        await self.broadcast(Channel.CANDLE, candle_data, symbol=symbol)

    async def broadcast_signal(self, symbol: str, signal_data: Any):
        """Broadcast a new aggregated signal (never throttled)."""
        await self.broadcast(Channel.SIGNAL, signal_data, symbol=symbol)

    async def broadcast_trade_state(self, symbol: str, trade_data: Any):
        """Broadcast trade state update."""
        await self.broadcast(Channel.TRADE_STATE, trade_data, symbol=symbol)

    async def broadcast_volume_profile(self, symbol: str, vp_data: Any):
        """Broadcast volume profile update."""
        await self.broadcast(Channel.VOLUME_PROFILE, vp_data, symbol=symbol)

    async def broadcast_bias(self, symbol: str, bias_data: Any):
        """Broadcast daily bias update."""
        await self.broadcast(Channel.BIAS, bias_data, symbol=symbol)

    async def broadcast_orderbook(self, symbol: str, book_data: dict):
        """Broadcast orderbook snapshot (throttled)."""
        await self.broadcast(Channel.ORDERBOOK, book_data, symbol=symbol)

    async def broadcast_delta(self, symbol: str, delta_data: dict):
        """Broadcast delta update (throttled)."""
        await self.broadcast(Channel.DELTA, delta_data, symbol=symbol)

    async def broadcast_stats(self, stats_data: dict):
        """Broadcast system stats."""
        await self.broadcast(Channel.STATS, stats_data)

    async def broadcast_search_rows(self, rows: list[dict]) -> None:
        """One batched palette update (already coalesced by RowBatcher)."""
        if rows:
            await self.broadcast(Channel.SEARCH, {"rows": rows})
