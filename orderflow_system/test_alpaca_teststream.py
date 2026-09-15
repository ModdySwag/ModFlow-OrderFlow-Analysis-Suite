"""Alpaca test-stream integration test (plan T27) — opt-in, needs the network.

Two live facts this file pins, both learned by running it:

1. Alpaca's sandbox stream (``wss://stream.data.alpaca.markets/v2/test``, symbol
   ``FAKEPACA``) **does** require authentication — a keyless connect is refused with
   error 401. That is asserted here so the behaviour is documented, not folklore.
2. With a key pair it delivers FAKEPACA trades, which is the cheapest end-to-end
   check of auth → subscribe → normalise. Set ``ALPACA_TEST_KEY`` / ``ALPACA_TEST_SECRET``
   (any linked account's paper keys) to run that half:

    RUN_ALPACA_TESTSTREAM=1 ALPACA_TEST_KEY=PK… ALPACA_TEST_SECRET=… \\
        .venv/Scripts/python.exe -m pytest orderflow_system/test_alpaca_teststream.py -q -s

Skipped by default: CI has no business opening sockets, and a flaky network must not
read as a broken build.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from orderflow_system.data.alpaca_feed import TEST_STREAM_SYMBOL, AlpacaStream, SubscriptionSet

RUN = os.environ.get("RUN_ALPACA_TESTSTREAM") == "1"
KEY = os.environ.get("ALPACA_TEST_KEY", "")
SECRET = os.environ.get("ALPACA_TEST_SECRET", "")

pytestmark = pytest.mark.skipif(
    not RUN, reason="opt-in live test — set RUN_ALPACA_TESTSTREAM=1 to run it")

TEST_URL = "wss://stream.data.alpaca.markets/v2/test"


def _run_for(stream, seconds, stop_when=None):
    ticks: list[tuple[str, object]] = []

    async def run():
        task = asyncio.ensure_future(stream.run())
        try:
            for _ in range(int(seconds * 2)):
                await asyncio.sleep(0.5)
                if stop_when and stop_when():
                    break
        finally:
            stream._stop = True
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    asyncio.run(run())
    return ticks


def test_keyless_connect_is_refused_with_401():
    """No keys → Alpaca says 401. The client must surface that instead of looping."""
    subs = SubscriptionSet(stock_cap=30)
    subs.add("trades", [TEST_STREAM_SYMBOL])
    stream = AlpacaStream("", "", url=TEST_URL, feed="test", subscriptions=subs, label="test")
    _run_for(stream, 12, stop_when=lambda: stream.state == "error")
    assert stream.state == "error", stream.status()
    assert "401" in (stream.last_error or "")
    assert stream.reconnects == 0, "a refused connection is fatal, not a retry loop"


@pytest.mark.skipif(not (KEY and SECRET), reason="set ALPACA_TEST_KEY/SECRET for the live stream half")
def test_test_stream_delivers_a_fake_paca_trade():
    ticks: list[tuple[str, object]] = []
    subs = SubscriptionSet(stock_cap=30)
    subs.add("trades", [TEST_STREAM_SYMBOL])
    stream = AlpacaStream(KEY, SECRET, url=TEST_URL, feed="test", subscriptions=subs, label="test",
                          on_tick=lambda sym, tick: ticks.append((sym, tick)))

    async def run():
        task = asyncio.ensure_future(stream.run())
        try:
            for _ in range(60):                     # up to 30 s
                await asyncio.sleep(0.5)
                if ticks:
                    break
        finally:
            stream._stop = True
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    asyncio.run(run())
    assert ticks, f"no FAKEPACA trade within 30 s — stream status: {stream.status()}"
    symbol, tick = ticks[0]
    assert symbol == TEST_STREAM_SYMBOL
    assert tick.price > 0 and tick.side is not None
