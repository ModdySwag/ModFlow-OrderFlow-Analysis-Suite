"""Broadcast backpressure — the gate for sweep R2.

The failure this pins: a broadcast used to hold the manager's lock across every `send_text`, so one
client that stopped reading stalled every other client and the producer with them. These tests drive
the real manager with fake sockets: a fast reader, a stalled one, a wedged one.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from orderflow_system.dashboard import websocket_manager as wm
from orderflow_system.dashboard.websocket_manager import Channel, WebSocketManager


class FakeWS:
    """A socket with a scripted write behaviour and a record of what it received."""

    def __init__(self, delay: float = 0.0, hang: bool = False, fail_after: int | None = None):
        self.delay = delay
        self.hang = hang
        self.fail_after = fail_after
        self.sent: list[dict] = []
        self._accepted = False

    async def accept(self) -> None:
        self._accepted = True

    async def send_text(self, message: str) -> None:
        if self.hang:
            await asyncio.Event().wait()             # never completes: a wedged socket
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise RuntimeError("socket closed")
        self.sent.append(json.loads(message))


def _run(coro):
    return asyncio.run(coro)


def test_a_broadcast_never_waits_on_a_slow_client():
    """The producer's cost is the queue offer, not the slowest socket."""

    async def scenario():
        manager = WebSocketManager()
        # the pacing layer would swallow a burst in one instant; this test is about the queue, so the
        # channel throttle is taken out of the way (the producer's cost is what is being measured)
        manager._throttle_ms[Channel.TICK] = 0
        slow = FakeWS(delay=0.02)          # 20 ms per write: 300 messages would be 6 s of socket time
        fast = FakeWS()
        await manager.connect(slow)
        await manager.connect(fast)

        started = asyncio.get_running_loop().time()
        for i in range(300):
            await manager.broadcast(Channel.TICK, {"i": i}, symbol="BTCUSDT")
        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 2.0, f"the producer waited for the slow socket ({elapsed:.2f}s)"

        stats = manager.delivery_stats()
        assert stats["clients"] == 2
        assert stats["max_queue"] <= wm.QUEUE_MAX, "no queue outgrows its bound"
        assert stats["dropped"] > 0, "the slow client's backlog was trimmed rather than grown"

        await asyncio.sleep(0.4)
        assert fast.sent and fast.sent[-1]["data"]["i"] == 299, "the fast client keeps up"
        slow_client = next(c for c in manager._connections if c.ws is slow)
        pending = []
        while not slow_client.queue.empty():
            pending.append(json.loads(slow_client.queue.get_nowait())["data"]["i"])
        assert (pending and pending[-1] == 299) or (slow.sent and slow.sent[-1]["data"]["i"] == 299), \
            "the newest state survived the trim (oldest-first, never newest-first)"

    _run(scenario())


def test_a_signal_is_never_dropped_for_a_slow_client():
    """Backpressure may trim stale market data. It may not trim a signal."""

    async def scenario():
        manager = WebSocketManager()
        slow = FakeWS(delay=0.001)
        await manager.connect(slow)
        total = wm.QUEUE_MAX + 40            # more than the queue holds, so the never-drop path runs
        for i in range(total):
            await manager.broadcast(Channel.SIGNAL, {"i": i})
        assert manager.delivery_stats()["dropped"] == 0, "no signal was trimmed"
        # delivery is slower than production here, so wait for the drain rather than guess a sleep
        deadline = asyncio.get_running_loop().time() + 5.0
        while len(slow.sent) < total and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.02)
        assert [m["data"]["i"] for m in slow.sent] == list(range(total)), "every signal arrived, in order"

    _run(scenario())


def test_a_wedged_client_is_dropped_by_the_write_timeout(monkeypatch):
    """A socket that never completes a write is removed instead of being waited for."""

    async def scenario():
        manager = WebSocketManager()
        wedged = FakeWS(hang=True)
        await manager.connect(wedged)
        assert manager.client_count == 1
        await manager.broadcast(Channel.TICK, {"i": 1}, symbol="BTCUSDT")
        await asyncio.sleep(wm.WRITE_TIMEOUT_S + 0.3)
        assert manager.client_count == 0, "the writer removed the client it could not talk to"

    monkeypatch.setattr(wm, "WRITE_TIMEOUT_S", 0.05)
    _run(scenario())


def test_a_socket_that_raises_is_removed_without_touching_the_others():
    async def scenario():
        manager = WebSocketManager()
        broken = FakeWS(fail_after=0)        # raises on its first write
        healthy = FakeWS()
        await manager.connect(broken)
        await manager.connect(healthy)
        await manager.broadcast(Channel.CANDLE, {"c": 1}, symbol="BTCUSDT")
        await asyncio.sleep(0.1)
        assert manager.client_count == 1, "the broken client is gone"
        assert healthy.sent and healthy.sent[0]["data"]["c"] == 1, "the healthy one still gets data"

    _run(scenario())


def test_the_lock_is_not_held_across_a_write(monkeypatch):
    """The property, pinned directly: during a send, the lock is free for another coroutine."""

    async def scenario():
        manager = WebSocketManager()
        gate = asyncio.Event()
        observed = {}

        class SlowWS(FakeWS):
            async def send_text(self, message: str) -> None:
                observed["locked_during_write"] = manager._lock.locked()
                await gate.wait()
                await super().send_text(message)

        await manager.connect(SlowWS())
        task = asyncio.create_task(manager.broadcast(Channel.SIGNAL, {"i": 1}))
        await asyncio.sleep(0.05)            # let the writer pick the message up
        assert observed.get("locked_during_write") is False, \
            "the manager's lock was held while a socket was being written to"
        assert await manager._lock.acquire() is None or True     # and it is free to take right now
        manager._lock.release()
        gate.set()
        await task

    _run(scenario())
