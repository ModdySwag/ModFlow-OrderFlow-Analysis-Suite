"""Late and racing prints in the candle builder (audit D-01 / D-02).

D-02: a print older than the live interval used to be folded into the open bar, rewriting the
wrong interval's OHLCV, footprint and delta. It is now counted (``late_prints``) and dropped.
D-01: the close callback used to clear ``current_candle`` only after it returned, so two racing
callers could close — and emit — the same candle twice.
"""
from __future__ import annotations

import asyncio

from orderflow_system.data.candle_builder import CandleBuilder
from orderflow_system.data.models import Side, Tick


def _tick(ts: int, price: float = 100.0, size: float = 1.0, side: Side = Side.BUY) -> Tick:
    return Tick(timestamp_ms=ts, price=price, size=size, side=side)


def test_a_late_print_is_counted_and_never_rewrites_the_live_bar():
    builder = CandleBuilder(interval_seconds=60, tick_size=0.1)

    async def run():
        await builder.process_tick(_tick(60_000, 100.0, 5.0))
        await builder.process_tick(_tick(60_500, 101.0, 2.0))
        live = builder.current_candle
        await builder.process_tick(_tick(30_000, 50.0, 99.0))       # a minute older
        return live

    live = asyncio.run(run())
    assert builder.late_prints == 1
    assert builder.current_candle is live, "the late print must not replace the open candle"
    assert live.low == 100.0 and live.volume == 7.0, "the open bar's OHLCV must be untouched"
    assert builder.stats()["late_prints"] == 1


def test_the_in_order_path_is_unchanged():
    builder = CandleBuilder(interval_seconds=60, tick_size=0.1)
    closed: list = []

    async def on_close(candle):
        closed.append(candle)

    builder.on_candle_close = on_close

    async def run():
        await builder.process_tick(_tick(60_000, 100.0, 1.0, Side.BUY))
        await builder.process_tick(_tick(60_100, 99.5, 2.0, Side.SELL))
        await builder.process_tick(_tick(120_200, 101.0, 3.0, Side.BUY))

    asyncio.run(run())
    assert len(closed) == 1
    candle = closed[0]
    assert (candle.timestamp_ms, candle.open, candle.high, candle.low, candle.close, candle.volume) \
        == (60_000, 100.0, 100.0, 99.5, 99.5, 3.0)
    assert candle.buy_volume == 1.0 and candle.sell_volume == 2.0
    assert sorted(candle.footprint) == [99.5, 100.0]
    assert builder.late_prints == 0


def test_a_racing_second_tick_cannot_close_the_same_candle_twice():
    closes: list = []

    async def on_close(candle):
        closes.append(candle)
        await asyncio.sleep(0.02)               # hold the callback open

    builder = CandleBuilder(interval_seconds=60, tick_size=0.1, on_candle_close=on_close)

    async def run():
        await builder.process_tick(_tick(60_100))
        await asyncio.gather(builder.process_tick(_tick(120_100)),
                             builder.process_tick(_tick(120_200)))

    asyncio.run(run())
    assert len(closes) == 1, f"one interval closed {len(closes)} times"
    assert builder.late_prints == 0


# ── MEM-A2-03: footprints are released on the old tail, OHLCV survives ───────────────────────
def test_footprints_are_released_beyond_the_keep_window():
    """5,000 candles each carrying a footprint dict measured 45-255 MiB per instrument; the
    window stays for the chart/VP/delta readers, the footprint dicts do not."""
    from orderflow_system.data.candle_builder import FOOTPRINT_KEEP

    builder = CandleBuilder(interval_seconds=60, tick_size=0.1)

    async def run():
        total = FOOTPRINT_KEEP + 60
        for i in range(total):
            await builder.process_tick(_tick(i * 60_000 + 1_000, 100.0 + (i % 5), 1.0))
        return builder.get_recent_candles(10_000)

    candles = asyncio.run(run())
    assert len(candles) == FOOTPRINT_KEEP + 59
    with_footprint = [c for c in candles if c.footprint]
    assert len(with_footprint) == FOOTPRINT_KEEP, len(with_footprint)
    assert all(c.volume > 0 and c.high >= c.low for c in candles), "OHLCV survives on the tail"
