"""Broadcast backpressure — the gate for sweep R2.

The failure this pins: a broadcast used to hold the manager's lock across every `send_text`, so one
client that stopped reading stalled every other client and the producer with them. These tests drive
the real manager with fake sockets: a fast reader, a stalled one, a wedged one.
"""

from __future__ import annotations

import asyncio
import json


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
        self.closed = 0

    async def accept(self) -> None:
        self._accepted = True

    async def close(self) -> None:
        self.closed += 1

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
        # delivery is slower than production here, so wait for the drain rather than guess a sleep.
        # The budget is a hang guard, not a pace: Windows timer granularity stretches each 1 ms
        # write to the platform tick (~15.6 ms), so the full drain runs ~5 s on a loaded runner —
        # the 3.11 job crossed a 5 s deadline once (2026-09-18). The assertion below is unchanged:
        # every signal, in order, or the test fails.
        deadline = asyncio.get_running_loop().time() + 30.0
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


def test_a_timed_out_client_is_closed_not_just_forgotten(monkeypatch):
    """MEM-A1-02: the writer closes the socket it gave up on, so the endpoint's `receive_text()`
    raises and its finally runs `disconnect()` — `_forget` alone parked the endpoint forever."""

    async def scenario():
        manager = WebSocketManager()
        wedged = FakeWS(hang=True)
        await manager.connect(wedged)
        await manager.broadcast(Channel.TICK, {"i": 1}, symbol="BTCUSDT")
        await asyncio.sleep(wm.WRITE_TIMEOUT_S + 0.3)
        assert manager.client_count == 0, "the writer removed the client it could not talk to"
        assert wedged.closed >= 1, "and closed its socket, so the endpoint cannot stay parked"

        # the endpoint's own disconnect path stays harmless afterwards (idempotent)
        await manager.disconnect(wedged)
        assert manager.client_count == 0
        assert wedged.closed == 1, "one close per dropped socket"

    monkeypatch.setattr(wm, "WRITE_TIMEOUT_S", 0.05)
    _run(scenario())


def test_a_must_arrive_broadcast_never_waits_the_old_ten_seconds(monkeypatch):
    """MEM-A1-05: a stalled client's full queue bounds the producer at MUST_ARRIVE_WAIT_S,
    not at WRITE_TIMEOUT_S * 2 — and the miss is counted instead of hidden."""

    async def scenario():
        manager = WebSocketManager()
        wedged = FakeWS(hang=True)
        await manager.connect(wedged)
        await manager.broadcast(Channel.TICK, {"i": 0}, symbol="BTCUSDT")   # parks the writer
        client = manager._connections[0]
        await asyncio.sleep(0.05)            # let the writer take its message and hang in send_text
        while not client.queue.full():
            client.queue.put_nowait("x")     # a full, never-draining queue
        started = asyncio.get_running_loop().time()
        await manager.broadcast(Channel.SIGNAL, {"s": 1})
        elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 1.0, f"the producer waited {elapsed:.2f}s on a stalled client"
        assert manager.delivery_stats()["dropped"] >= 1, "the miss is counted, not silent"

    monkeypatch.setattr(wm, "MUST_ARRIVE_WAIT_S", 0.2)
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


def test_a_cancelled_writer_dies_even_when_its_write_just_finished():
    """The 3.11 shutdown hang, pinned (handoff §65).

    asyncio.run's exit cancels the tasks still alive with the loop stopped, then gathers them.
    A writer parked in its write-timeout whose write had *just* completed is the state that made
    that gather wait forever on 3.11: wait_for answered the cancellation with the finished
    write's result, and the writer looped back to queue.get() instead of dying. The manager's
    deadline is asyncio.timeout, which never eats a cancellation — this builds the state on a
    stopped loop and requires the writer to finish.
    """

    loop = asyncio.new_event_loop()
    manager = WebSocketManager()
    manager._throttle_ms[Channel.TICK] = 0
    gate = asyncio.Event()

    class GatedWS(FakeWS):
        async def send_text(self, message: str) -> None:
            await gate.wait()
            await super().send_text(message)

    ws = GatedWS()

    async def settle() -> None:
        """One loop cycle that yields once — stops the loop one batch after the write completes."""
        await asyncio.sleep(0)

    async def open_up() -> None:
        await manager.connect(ws)
        await manager.broadcast(Channel.TICK, {"i": 0}, symbol="BTCUSDT")
        await asyncio.sleep(0)              # the writer parks inside its write-timeout

    async def bounded_shutdown(writer) -> None:
        """asyncio.run's exit, bounded: cancel the survivor, then gather it — so a regression
        fails this test instead of hanging the suite."""
        shutdown = asyncio.ensure_future(asyncio.gather(writer, return_exceptions=True))
        _, pending = await asyncio.wait({shutdown}, timeout=2)
        if shutdown in pending:
            shutdown.cancel()
            await asyncio.wait({shutdown}, timeout=2)     # let the unwind finish, still bounded
            try:
                shutdown.exception()                       # retrieved, so the log stays clean
            except asyncio.CancelledError:
                pass
            raise AssertionError(
                "the cancelled writer never finished — asyncio.run's shutdown gather would hang "
                "here (the 3.11 wait_for cancellation swallow; see handoff §65)")

    writer = None
    try:
        loop.run_until_complete(open_up())
        loop.call_later(0, gate.set)            # the write completes while the loop is stopped...
        loop.run_until_complete(settle())       # ...and the loop stops with the writer's wake-up queued
        writer = manager._connections[0].task
        assert not writer.done(), "the writer is still parked in its write-timeout"
        assert len(ws.sent) == 1, "the write itself completed"

        writer.cancel()                          # what asyncio.run's exit does to a survivor
        loop.run_until_complete(bounded_shutdown(writer))
        assert writer.done(), "the writer died on cancellation"
    finally:
        if writer is not None and not writer.done():
            writer.cancel()                      # never leave a live writer behind
            loop.run_until_complete(asyncio.sleep(0))
        loop.close()
