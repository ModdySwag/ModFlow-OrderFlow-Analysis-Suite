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


# One client's backlog, bounded. Big enough for a burst, small enough that a stalled socket is
# noticed within seconds instead of growing without limit.
QUEUE_MAX = 256
# A write that has not completed in this long means the socket is wedged (half-open, or a client that
# stopped reading). The client is dropped; the producer never waits for it.
WRITE_TIMEOUT_S = 5.0
# Channels whose backlog may be trimmed under pressure: for these, the newest state is what matters and
# an old message is worth less than a new one. Everything else must arrive — a dropped signal is a lie.
DROPPABLE = {Channel.TICK.value, Channel.ORDERBOOK.value, Channel.DELTA.value, Channel.STATS.value}

# MEM-A1-05: how long a must-arrive channel may wait for a stalled client's queue. The old bound
# was WRITE_TIMEOUT_S * 2 = 10 s *per stalled client, in series* inside the producer — a bubble on
# the candle-close path repeated every candle. A few hundred milliseconds bounds it; a message that
# still cannot be placed is counted (client.dropped) rather than stalling the feed that produces it.
MUST_ARRIVE_WAIT_S = 0.5


class _Client:
    """A connected client: its socket, its queue, the task draining it, and what it missed."""

    __slots__ = ("ws", "queue", "task", "dropped")

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self.task: Optional[asyncio.Task] = None
        self.dropped = 0


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts data to all connected clients.
    Thread-safe via asyncio — all operations run on the event loop.

    Broadcasts never write to a socket: they offer the message to each client's queue and return, and
    one writer task per client does the writing. That is what keeps a slow reader from being everyone
    else's problem, and what keeps `_lock` out of the delivery path entirely.
    """

    def __init__(self):
        self._connections: list[_Client] = []
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
        """Accept a client, give it a queue, and start its writer. Nothing is sent from here on."""
        await ws.accept()
        client = _Client(ws)
        async with self._lock:
            self._connections.append(client)
        client.task = asyncio.create_task(self._writer(client))
        logger.info(f"Dashboard client connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket):
        """Remove a client (and stop its writer) because the socket closed."""
        client = None
        async with self._lock:
            for candidate in self._connections:
                if candidate.ws is ws:
                    client = candidate
                    self._connections.remove(candidate)
                    break
        if client is not None and client.task:
            client.task.cancel()
        logger.info(f"Dashboard client disconnected. Total: {len(self._connections)}")

    async def _writer(self, client: _Client) -> None:
        """Drain one client's queue. Outside every lock, so a wedged socket hurts only itself."""
        try:
            while True:
                message = await client.queue.get()
                try:
                    # asyncio.timeout, never asyncio.wait_for: 3.11's wait_for answers a
                    # cancellation with the finished write's result (`if fut.done(): return
                    # fut.result()`), so a shutdown cancel was swallowed and this loop went
                    # back to queue.get() forever — the 3.11 suite hang (handoff §65). 3.12's
                    # wait_for is built on this same timeout context.
                    async with asyncio.timeout(WRITE_TIMEOUT_S):
                        await client.ws.send_text(message)
                except asyncio.TimeoutError:
                    logger.warning(
                        "WebSocket client write timed out after %.1fs, dropping it (%d message(s) "
                        "already trimmed from its queue)",
                        WRITE_TIMEOUT_S, client.dropped)
                    break
                except Exception:
                    break
        except asyncio.CancelledError:
            raise
        finally:
            self._forget(client)
            # MEM-A1-02: close the socket on the writer's own exit paths too (write timeout,
            # error). `_forget` alone removed the client from the fan-out while the endpoint
            # coroutine stayed parked in `receive_text()` with a live socket — one leaked task
            # per event, invisible in client_count. Closing it makes receive_text() raise
            # WebSocketDisconnect, so the endpoint's finally runs disconnect() normally.
            try:
                await client.ws.close()
            except Exception:                       # already gone, or never accepted
                logger.debug("closing a dropped client's socket did not complete", exc_info=True)

    def _forget(self, client: _Client) -> None:
        """Synchronous removal: safe from a writer's finally block, which cannot await."""
        if client in self._connections:
            self._connections.remove(client)

    async def _offer(self, client: _Client, message: str, droppable: bool) -> None:
        """Hand a message to one client's queue — the whole delivery path, and it does not block on
        the socket. A full queue trims the oldest message for a throttleable channel (freshness beats
        completeness there); for a channel that must arrive, it waits — bounded, because a producer
        that never returns is worse than a client that missed one update."""
        try:
            client.queue.put_nowait(message)
            return
        except asyncio.QueueFull:
            pass
        if droppable:
            try:
                client.queue.get_nowait()
                client.dropped += 1
            except asyncio.QueueEmpty:
                pass
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                client.dropped += 1
            return
        try:
            # the same reason as the writer: a plain deadline, not wait_for (handoff §65)
            async with asyncio.timeout(MUST_ARRIVE_WAIT_S):
                await client.queue.put(message)
        except asyncio.TimeoutError:
            client.dropped += 1
            logger.warning("WebSocket client queue stayed full for %.1fs, one message was not delivered",
                           MUST_ARRIVE_WAIT_S)

    def delivery_stats(self) -> dict:
        """What the queues are doing — the numbers a test (or a status line) can hold the design to."""
        return {
            "clients": len(self._connections),
            "dropped": sum(c.dropped for c in self._connections),
            "max_queue": max((c.queue.qsize() for c in self._connections), default=0),
            "queue_max": QUEUE_MAX,
        }

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

        # Offer it to every client's queue. No lock, no socket write, no waiting on a slow reader —
        # the snapshot is taken because a writer may remove itself (and its client) at any await.
        droppable = ch in DROPPABLE
        for client in list(self._connections):
            await self._offer(client, message, droppable)

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
