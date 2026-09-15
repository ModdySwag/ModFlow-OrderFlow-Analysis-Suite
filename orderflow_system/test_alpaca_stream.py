"""Alpaca stream-client tests (plan T23) — scripted frames, no network.

These pin the three things that decide whether a live socket is trustworthy:
  * every documented error code maps to an actionable message, and credential/plan
    errors (401/402/403) are fatal instead of reconnect-looping forever;
  * auth goes out before anything else, and a reconnect re-authenticates;
  * subscribe/unsubscribe are idempotent — the UI can call them on every poll.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from orderflow_system.data.alpaca_feed import (
    STREAM_ERRORS,
    AlpacaError,
    AlpacaStream,
    SubscriptionSet,
    map_stream_error,
)
from orderflow_system.data.models import Side


class FakeSocket:
    """An async-iterable socket: scripted frames in, sent frames recorded."""

    def __init__(self, frames=None, hang=False):
        self.frames = [json.dumps(f) if not isinstance(f, str) else f for f in (frames or [])]
        self.sent: list[dict] = []
        self.closed = False
        self.hang = hang

    async def send(self, payload):
        self.sent.append(json.loads(payload))

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.frames:
            await asyncio.sleep(0)
            return self.frames.pop(0)
        if self.hang:
            await asyncio.sleep(3600)
        raise StopAsyncIteration

    async def close(self):
        self.closed = True


def factory_for(sockets):
    """A connect factory handing out sockets in order (then the last one again)."""
    queue = list(sockets)

    def factory(_url):
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]

    return factory


SUCCESS_CONNECTED = {"T": "success", "msg": "connected"}
SUCCESS_AUTHED = {"T": "success", "msg": "authenticated"}
SUBSCRIBED = {"T": "subscription", "trades": ["AAPL"], "quotes": ["AAPL"]}


def make_stream(**kw):
    kwargs = dict(key_id="PKTEST", secret="s", url="wss://example.invalid/v2/iex",
                  connect_factory=factory_for([FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED], hang=True)]))
    kwargs.update(kw)
    return AlpacaStream(**kwargs)


async def _run_briefly(stream, seconds=0.2):
    task = asyncio.ensure_future(stream.run())
    await asyncio.sleep(seconds)
    stream._stop = True
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


# ── error mapping ───────────────────────────────────────────────────────

def test_every_documented_error_code_maps_to_an_actionable_message():
    for code, message in STREAM_ERRORS.items():
        err = map_stream_error(code, "detail")
        assert err.code == code
        assert len(err.args[0]) > 20, f"code {code} needs a real explanation"
    assert map_stream_error(401).fatal is True
    assert map_stream_error(402).fatal is True
    assert map_stream_error(403).fatal is True
    assert map_stream_error(405).fatal is False
    assert map_stream_error(407).fatal is False
    unknown = map_stream_error(999)
    assert unknown.code == 999 and "unexpected error code 999" in str(unknown)


def test_fatal_auth_error_stops_instead_of_looping():
    sock = FakeSocket([{"T": "error", "code": 401, "msg": "not authenticated"}], hang=True)
    stream = make_stream(connect_factory=factory_for([sock]))

    async def run():
        await stream.run()

    asyncio.run(run())
    assert stream.state == "error"
    assert stream.reconnects == 0, "a wrong key pair must not be retried forever"
    assert "401" in (stream.last_error or "")


# ── auth + subscriptions ────────────────────────────────────────────────

def test_auth_is_sent_before_subscribing():
    sock = FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED, SUBSCRIBED], hang=True)
    subs = SubscriptionSet(stock_cap=30)
    subs.add("trades", ["AAPL"])
    stream = make_stream(connect_factory=factory_for([sock]), subscriptions=subs)

    async def run():
        await _run_briefly(stream)

    asyncio.run(run())
    assert sock.sent[0]["action"] == "auth", "auth must be the first frame"
    assert sock.sent[0]["key"] == "PKTEST"
    assert sock.sent[1] == {"action": "subscribe", "trades": ["AAPL"]}
    assert stream.authenticated is True
    assert stream.state == "live"
    assert stream.messages >= 3


def test_reconnect_reauthenticates_on_a_fresh_socket():
    first = FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED])          # ends → drop
    second = FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED], hang=True)
    subs = SubscriptionSet()
    subs.add("trades", ["AAPL"])
    stream = make_stream(connect_factory=factory_for([first, second]), subscriptions=subs)

    async def run():
        task = asyncio.ensure_future(stream.run())
        for _ in range(40):
            await asyncio.sleep(0.05)
            if stream.reconnects:
                break
        await asyncio.sleep(1.3)                                     # let the backoff elapse
        stream._stop = True
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(run())
    assert stream.reconnects >= 1
    assert second.sent and second.sent[0]["action"] == "auth", "the new socket authenticates too"
    assert any(frame.get("trades") == ["AAPL"] for frame in second.sent)


def test_subscribe_and_unsubscribe_are_idempotent():
    sock = FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED], hang=True)
    stream = make_stream(connect_factory=factory_for([sock]))

    async def run():
        task = asyncio.ensure_future(stream.run())
        for _ in range(40):
            await asyncio.sleep(0.05)
            if stream.authenticated:
                break
        assert await stream.subscribe("trades", ["AAPL"]) == ["AAPL"]
        assert await stream.subscribe("trades", ["AAPL"]) == [], "already subscribed"
        assert await stream.unsubscribe("trades", ["AAPL"]) == ["AAPL"]
        assert await stream.unsubscribe("trades", ["AAPL"]) == []
        assert await stream.unsubscribe("trades", []) == []
        stream._stop = True
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(run())
    actions = [frame.get("action") for frame in sock.sent]
    assert actions.count("subscribe") == 1
    assert actions.count("unsubscribe") == 1


# ── data frames ─────────────────────────────────────────────────────────

def test_trades_and_quotes_reach_the_callback_with_the_venue_symbol():
    frames = [
        SUCCESS_CONNECTED, SUCCESS_AUTHED,
        {"T": "q", "S": "AAPL", "bp": 182.40, "bs": 1, "ap": 182.44, "as": 2,
         "t": "2026-09-15T13:30:00.500Z"},
        {"T": "t", "S": "AAPL", "p": 182.44, "s": 100, "t": "2026-09-15T13:30:01Z", "i": 1},
        {"T": "t", "S": "AAPL", "p": 182.10, "s": 50, "t": "2026-09-15T13:30:02Z", "i": 2},
    ]
    sock = FakeSocket(frames, hang=True)
    ticks: list[tuple[str, object]] = []
    quotes: list[str] = []
    stream = make_stream(connect_factory=factory_for([sock]),
                         on_tick=lambda s, t: ticks.append((s, t)),
                         on_quote=lambda s, q: quotes.append(s))

    async def run():
        await _run_briefly(stream)

    asyncio.run(run())
    assert quotes == ["AAPL"]
    assert [s for s, _t in ticks] == ["AAPL", "AAPL"]
    # the quote set the mid, so the tick rule classifies the prints
    assert ticks[0][1].side == Side.BUY          # 182.44 >= mid 182.42
    assert ticks[1][1].side == Side.SELL         # 182.10 < mid
    assert ticks[1][1].timestamp_ms == 1789479002000


def test_non_json_and_unknown_frames_do_not_kill_the_stream():
    sock = FakeSocket(["not json at all", {"T": "banana", "S": "AAPL"}, SUCCESS_CONNECTED, SUCCESS_AUTHED],
                      hang=True)
    stream = make_stream(connect_factory=factory_for([sock]))

    async def run():
        await _run_briefly(stream)

    asyncio.run(run())
    assert stream.state == "live"
    assert stream.last_error is None


def test_stream_status_is_reportable():
    sock = FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED], hang=True)
    stream = make_stream(connect_factory=factory_for([sock]), label="stocks", feed="iex")

    async def run():
        await _run_briefly(stream)
        return stream.status()

    status = asyncio.run(run())
    assert status["label"] == "stocks" and status["state"] == "live"
    assert status["authenticated"] is True
    assert status["subscriptions"]["count"] == 0
    assert status["last_message_age_s"] is not None


def test_the_test_stream_can_skip_auth():
    """Alpaca's sandbox stream (FAKEPACA) does not need keys — used by the opt-in test."""
    sock = FakeSocket([SUCCESS_CONNECTED, SUCCESS_AUTHED], hang=True)
    stream = AlpacaStream("", "", url="wss://stream.data.alpaca.markets/v2/test", feed="test",
                          connect_factory=factory_for([sock]), label="test")

    async def run():
        await _run_briefly(stream)

    asyncio.run(run())
    assert stream.require_auth is False
    assert not any(frame.get("action") == "auth" for frame in sock.sent), "no keys, no auth frame"
