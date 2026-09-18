"""The feed-session rule — reader never cancelled, per-venue heartbeats, ladder resets on data.

These tests drive the shared helper (`data/feed_session.py`) with fake sockets, and pin the two
behaviours that were ported into `bybit_feed.py` from it: the ladder resets only on a decoded
frame, and every reconnect sleep carries jitter.
"""

from __future__ import annotations

import asyncio
import json
import random

import pytest

from orderflow_system.data.feed_session import (
    FeedSession,
    HeartbeatPolicy,
    ReconnectBackoff,
    VENUE_POLICIES,
)
from orderflow_system.data.bybit_feed import BybitFeed


# ── fixtures: fake connections ────────────────────────────────────────────────────────────────
class FakeConn:
    """An async-iterable socket: frames arrive after a small delay, sends are recorded.

    ``cancelled`` counts CancelledError delivered *to the reader* — the whole point of the
    design is that a heartbeat never does that.
    """

    def __init__(self, frames, *, gap=0.02, fail_after=None, then_silent=False):
        self.frames = list(frames)
        self.gap = gap
        self.fail_after = fail_after
        self.then_silent = then_silent
        self.sent: list[object] = []
        self.closed = False
        self.cancelled = 0
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.fail_after is not None and self._i >= self.fail_after:
            raise ConnectionResetError("socket died")
        if self._i >= len(self.frames):
            if self.then_silent:
                # A quiet socket: the read stays pending until the session closes it — which is
                # exactly how a real websocket's reader exits when close() is called.
                while not self.closed:
                    await asyncio.sleep(0.005)
                raise StopAsyncIteration
            raise StopAsyncIteration
        try:
            await asyncio.sleep(self.gap)
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        frame = self.frames[self._i]
        self._i += 1
        return frame

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.closed = True


def _run(coro):
    return asyncio.run(coro)


class VirtualClock:
    """Monotonic seconds that advance by `step` on every read — the heartbeat is a virtual-time
    contract, so these tests never wait on real seconds."""

    def __init__(self, start: float = 1000.0, step: float = 0.05) -> None:
        self.t = float(start)
        self.step = float(step)

    def __call__(self) -> float:
        value = self.t
        self.t += self.step
        return value


async def _instant(_delay: float) -> None:
    """A sleep that never sleeps — used for the session's own waits in virtual-time tests."""
    await asyncio.sleep(0)


# ── policies are data, per venue ──────────────────────────────────────────────────────────────
def test_policies_are_per_venue_data():
    bybit = VENUE_POLICIES["bybit"]
    assert bybit.mode == "client_ping" and bybit.ping_every_s == 20.0 and bybit.silence_budget_s == 60.0

    binance = VENUE_POLICIES["binance"]
    assert binance.mode == "server_driven" and binance.ping_every_s == 0.0
    # the futures stream may legitimately be quiet for minutes: a 60 s budget would kill it
    assert binance.silence_budget_s >= 240.0

    assert VENUE_POLICIES["okx"].mode == "ping_after_idle"
    assert VENUE_POLICIES["okx"].silence_budget_s > 60.0, \
        "OKX keeps a quiet instrument alive at a ~60 s cadence — the budget must outlast it"
    assert VENUE_POLICIES["hyperliquid"].mode == "ping_after_idle"
    assert VENUE_POLICIES["mexc"].mode == "client_ping"


def test_an_invalid_policy_is_refused():
    with pytest.raises(ValueError):
        HeartbeatPolicy("carrier_pigeon")
    with pytest.raises(ValueError):
        HeartbeatPolicy("client_ping", ping_every_s=0.0)
    with pytest.raises(ValueError):
        HeartbeatPolicy("server_driven", silence_budget_s=0.0)


# ── the ladder ────────────────────────────────────────────────────────────────────────────────
def test_backoff_escalates_and_caps():
    back = ReconnectBackoff(base=1.0, factor=2.0, cap=8.0, jitter=0.0)
    assert [back.next_delay() for _ in range(5)] == [1.0, 2.0, 4.0, 8.0, 8.0]


def test_backoff_resets_only_on_parsed_data():
    back = ReconnectBackoff(jitter=0.0)
    back.next_delay(); back.next_delay()
    assert back.current == 4.0
    back.record_parsed()
    assert back.current == 1.0 and back.attempts == 0 and back.reset_count == 1


def test_backoff_jitter_stays_within_bounds():
    back = ReconnectBackoff(base=1.0, factor=1.0, cap=1.0, jitter=0.25,
                            rng=random.Random(7))
    for _ in range(200):
        assert 0.75 <= back.next_delay() <= 1.25


# ── the session ───────────────────────────────────────────────────────────────────────────────
def test_every_frame_arrives_while_heartbeats_run():
    """The reader is never cancelled: heartbeats fire beside it and every frame lands, in order."""
    frames = [f"frame-{i}" for i in range(5)]
    seen: list[str] = []
    conns: list[FakeConn] = []

    async def connect():
        conn = FakeConn(list(frames), gap=0.005)
        conns.append(conn)
        return conn

    async def on_frame(raw):
        seen.append(raw)

    async def main():
        session = FeedSession(
            "bybit", connect, on_frame,
            policy=HeartbeatPolicy("client_ping", ping_every_s=0.05, silence_budget_s=1000.0),
            sleep=_instant, clock=VirtualClock(), heartbeat_tick_s=0.05,
        )
        task = asyncio.create_task(session.run())
        for _ in range(4000):
            await asyncio.sleep(0)
            if len(seen) >= len(frames):
                break
        stats = session.stats()
        await session.stop()
        await asyncio.wait_for(task, timeout=2)
        return stats

    stats = _run(main())
    assert seen[:len(frames)] == frames, f"the reader lost frames: {seen}"
    assert conns[0].cancelled == 0, "a heartbeat cancelled the reader mid-frame"
    assert stats["heartbeats"] >= 1, "the heartbeat never fired"
    assert stats["frames"] >= len(frames)


def test_a_dropped_socket_reconnects_and_the_ladder_resets_on_parsed_data():
    """A dead socket escalates; the first parsed frame on the new socket resets the ladder."""
    seen: list[str] = []
    conns: list[FakeConn] = []
    attempts = {"n": 0}

    async def connect():
        attempts["n"] += 1
        # first socket: dies after one frame; second: a frame, then it stays open
        conn = FakeConn(["one"] if attempts["n"] == 1 else ["two"],
                        gap=0.005, fail_after=1 if attempts["n"] == 1 else None,
                        then_silent=attempts["n"] != 1)
        conns.append(conn)
        return conn

    async def on_frame(raw):
        seen.append(raw)

    async def main():
        session = FeedSession(
            "bybit", connect, on_frame,
            policy=HeartbeatPolicy("client_ping", ping_every_s=10.0, silence_budget_s=1000.0),
            backoff=ReconnectBackoff(base=0.05, factor=2.0, cap=0.05, jitter=0.0),
            sleep=_instant, clock=VirtualClock(), heartbeat_tick_s=0.05,
        )
        task = asyncio.create_task(session.run())
        for _ in range(4000):
            await asyncio.sleep(0)
            if len(seen) >= 2:
                break
        await session.stop()
        await asyncio.wait_for(task, timeout=2)
        return session

    session = _run(main())
    assert seen[:2] == ["one", "two"], seen
    assert attempts["n"] >= 2, "the session never reconnected"
    assert session._backoff.current == 0.05, "the ladder did not reset after a parsed frame"
    assert session.stats()["reconnects"] >= 1


def test_a_silent_socket_trips_the_silence_budget():
    """No frames inside the budget → the socket is treated as dead and the session reconnects."""
    conns: list[FakeConn] = []

    async def connect():
        conn = FakeConn(["hello"], gap=0.005, then_silent=True)
        conns.append(conn)
        return conn

    async def on_frame(_raw):
        return None

    async def main():
        session = FeedSession(
            "hyperliquid", connect, on_frame,
            policy=HeartbeatPolicy("ping_after_idle", ping_after_idle_s=0.05, silence_budget_s=0.2),
            backoff=ReconnectBackoff(base=0.0, factor=1.0, cap=0.0, jitter=0.0),
            sleep=_instant, clock=VirtualClock(), heartbeat_tick_s=0.05,
        )
        task = asyncio.create_task(session.run())
        for _ in range(4000):
            await asyncio.sleep(0)
            if len(conns) >= 2:
                break
        stats = session.stats()
        await session.stop()
        await asyncio.wait_for(task, timeout=2)
        return stats

    stats = _run(main())
    assert len(conns) >= 2, "a silent socket was not treated as dead"
    assert conns[0].closed, "the dead socket was not closed before reconnecting"
    assert stats["heartbeats"] >= 1, "ping_after_idle never pinged an idle socket"
    assert stats["reconnects"] >= 1


def test_server_driven_sends_no_pings_but_watches_the_budget():
    """Binance pings us; sending our own pings would be noise — but the budget still applies."""
    conns: list[FakeConn] = []

    async def connect():
        conn = FakeConn(["one"], gap=0.005, then_silent=True)
        conns.append(conn)
        return conn

    async def on_frame(_raw):
        return None

    async def main():
        session = FeedSession(
            "binance", connect, on_frame,
            policy=HeartbeatPolicy("server_driven", silence_budget_s=0.2),
            backoff=ReconnectBackoff(base=0.0, factor=1.0, cap=0.0, jitter=0.0),
            sleep=_instant, clock=VirtualClock(), heartbeat_tick_s=0.05,
        )
        task = asyncio.create_task(session.run())
        for _ in range(4000):
            await asyncio.sleep(0)
            if len(conns) >= 2:
                break
        await session.stop()
        await asyncio.wait_for(task, timeout=2)

    _run(main())
    assert len(conns) >= 2, "a server-driven silence budget did not fire"
    assert all(not c.sent for c in conns), "a server-driven venue must not be pinged"


# ── the two behaviours ported into the Bybit feed itself ──────────────────────────────────────
def test_bybit_ladder_resets_on_a_decoded_frame_only():
    """A JSON frame resets the ladder; a socket that dies without one does not."""
    feed = BybitFeed(symbols=["BTCUSDT"])
    feed._running = True                            # `start()` sets this; the loop checks it
    feed._reconnect_delay = 8.0                     # mid-ladder, as if it had been failing

    class DeadWS:
        def __init__(self):
            self.sent = []

        async def send(self, payload):
            self.sent.append(payload)

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionResetError("handshake accepted, then died")

    class LiveWS(DeadWS):
        def __init__(self):
            super().__init__()
            self._n = 0

        async def __anext__(self):
            self._n += 1
            if self._n > 1:
                raise StopAsyncIteration
            return json.dumps({"topic": "publicTrade.BTCUSDT", "data": []})

    import orderflow_system.data.bybit_feed as mod

    class FakeConnect:
        def __init__(self, ws):
            self.ws = ws

        def __call__(self, *_a, **_k):
            ws = self.ws

            class Ctx:
                async def __aenter__(self):
                    return ws

                async def __aexit__(self, *exc):
                    return False

            return Ctx()

    original = mod.websockets.connect

    async def drive(ws):
        mod.websockets.connect = FakeConnect(ws)
        try:
            await asyncio.wait_for(feed._connect_and_listen(), timeout=2)
        finally:
            mod.websockets.connect = original

    # a dead socket: the ladder must NOT reset (the exception leaves it untouched)
    feed._reconnect_delay = 8.0
    try:
        _run(drive(DeadWS()))
    except ConnectionResetError:
        pass
    assert feed._reconnect_delay == 8.0, "the ladder reset on a socket that never delivered data"

    # a decoded frame: the ladder resets
    _run(drive(LiveWS()))
    assert feed._reconnect_delay == 1.0, "a decoded frame did not reset the ladder"


def test_bybit_reconnect_delay_carries_jitter_and_escalates(monkeypatch):
    """The sleep that follows a drop is the ladder value × (1 ± 25 %), then the ladder doubles.

    Pinned with a recording sleep: the naive `asyncio.sleep(self._reconnect_delay)` (no jitter) and
    a ladder reset on connect are the two regressions this guards.
    """
    import orderflow_system.data.bybit_feed as mod

    slept: list[float] = []

    class Stop(Exception):
        pass

    async def fake_sleep(delay):
        slept.append(delay)
        if len(slept) >= 2:
            raise Stop()

    class DeadConnect:
        def __call__(self, *_a, **_k):
            class Ctx:
                async def __aenter__(self):
                    raise ConnectionRefusedError("handshake refused")

                async def __aexit__(self, *_exc):
                    return False

            return Ctx()

    monkeypatch.setattr(mod.websockets, "connect", DeadConnect())
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(mod.random, "uniform", lambda _a, _b: 0.25)     # a fixed +25 %

    feed = BybitFeed(symbols=["BTCUSDT"])
    feed._reconnect_delay = 2.0
    with pytest.raises(Stop):
        asyncio.run(feed.start())

    assert slept == [pytest.approx(2.5), pytest.approx(5.0)], slept        # 2.0 × 1.25, then 4.0 × 1.25
    assert feed._reconnect_delay == 4.0, "the ladder did not escalate after a connect-and-die"
def test_a_non_data_frame_does_not_reset_the_ladder():
    """A handler that answers False (acks, pongs) is not proof the feed works: only market data
    resets the ladder, so a venue that accepts, acks and then stalls keeps escalating."""
    attempts = {"n": 0}

    async def connect():
        attempts["n"] += 1
        return FakeConn(["ack-%d" % attempts["n"]], gap=0.005, fail_after=1, then_silent=False)

    async def on_frame(_raw):
        return False                          # a control frame, never data

    async def main():
        session = FeedSession(
            "bybit", connect, on_frame,
            policy=HeartbeatPolicy("client_ping", ping_every_s=10.0, silence_budget_s=1000.0),
            backoff=ReconnectBackoff(base=0.05, factor=2.0, cap=0.4, jitter=0.0),
            sleep=_instant, clock=VirtualClock(), heartbeat_tick_s=0.05,
        )
        task = asyncio.create_task(session.run())
        for _ in range(4000):
            await asyncio.sleep(0)
            if attempts["n"] >= 2:
                break
        await session.stop()
        await asyncio.wait_for(task, timeout=2)
        return session

    session = _run(main())
    assert attempts["n"] >= 2, "the session never reconnected"
    assert session._backoff.current > 0.05, "an ack frame must not reset the ladder"
