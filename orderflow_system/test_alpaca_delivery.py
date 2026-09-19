"""Alpaca tick delivery: one consumer, arrival order, bounded queue (audit D-01).

The stream callbacks are synchronous; scheduling one task per tick let N overlapping ``on_tick``
coroutines close the same candle N times and write N rows. Deliveries now go through one bounded
queue drained by ``_drain_ticks``; the overflow policy is oldest-dropped and counted, and the
counters are visible in ``status()``. A synchronous consumer is still called inline.
"""
from __future__ import annotations

import asyncio

from orderflow_system.data.alpaca_feed import TICK_QUEUE_MAX, AlpacaData, AlpacaFeed


def test_async_deliveries_are_serialised_in_arrival_order():
    seen: list[int] = []
    inflight = 0
    peak = 0

    async def on_tick(_symbol, tick):
        nonlocal inflight, peak
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0)              # a suspension point on every delivery
        seen.append(tick)
        inflight -= 1

    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=on_tick, data=AlpacaData("k", "s"))

    async def driver():
        drain = asyncio.ensure_future(feed._drain_ticks())
        for i in range(50):
            feed._deliver("AAPL", i)
        await asyncio.sleep(0.05)
        drain.cancel()
        try:
            await drain
        except asyncio.CancelledError:
            pass

    asyncio.run(driver())
    assert seen == list(range(50)), f"delivery order broken: {seen[:8]}..."
    assert peak == 1, f"deliveries overlapped (peak in-flight = {peak})"


def test_a_full_queue_drops_the_oldest_tick_and_counts_it():
    async def on_tick(_symbol, _tick):      # pragma: no cover - no consumer runs in this test
        pass

    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=on_tick, data=AlpacaData("k", "s"))
    for i in range(TICK_QUEUE_MAX + 5):
        feed._deliver("AAPL", i)

    status = feed.status()
    assert status["ticks_dropped"] == 5
    assert status["tick_queue_depth"] == TICK_QUEUE_MAX


def test_a_synchronous_consumer_is_still_called_inline():
    ticks: list[tuple[str, int]] = []
    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=lambda s, t: ticks.append((s, t)),
                      data=AlpacaData("k", "s"))

    feed._deliver("AAPL", 7)

    assert ticks == [("AAPL", 7)], "a sync consumer must see the tick without a running loop"
    assert feed.status()["tick_queue_depth"] == 0
