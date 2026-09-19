"""Boundary guards in the analytics family (audit C-06 / C-10).

C-06: `CvdTracker.detect_divergence` ran `min()` over an empty sequence when a bucket carried a
zero/missing price — `ValueError` instead of the `None` every other implausible input returns.
C-10: the volume-profile fallback (an OHLC-only candle, no footprint) sized its price loop by
range ÷ tick with no cap — ~1 M iterations and ~1.2 s of main thread for one candle at a fine
tick. The API route has always capped the same loop at 500; the engine now matches it.
"""
from __future__ import annotations

import time

from orderflow_system.atlas.cvd import CvdTracker
from orderflow_system.data.models import Candle, Side, Tick
from orderflow_system.config.settings import VolumeProfileConfig
from orderflow_system.analytics.volume_profile import VolumeProfileEngine


def _tick(ts: int, price: float, size: float = 1.0) -> Tick:
    return Tick(timestamp_ms=ts, price=price, size=size, side=Side.BUY)


def test_zero_priced_ticks_answer_no_divergence_instead_of_raising():
    tracker = CvdTracker("TEST", tick_size=0.25, bucket_ms=1000,
                         divergence_lookback=3, divergence_min_ticks=2.0, absorption_ticks=1.0)
    for i in range(40):
        tracker.on_tick(_tick(1_000_000 + i * 1000, 0.0, 5.0))     # a missing/zero price
    assert tracker.detect_divergence() is None, "a zero price is a malformed reading, not a divergence"


def test_a_normal_series_does_not_raise():
    tracker = CvdTracker("TEST", tick_size=0.25, bucket_ms=1000,
                         divergence_lookback=3, divergence_min_ticks=2.0)
    price = 100.0
    for i in range(40):
        price += 0.5 if i % 2 else -0.25
        tracker.on_tick(_tick(2_000_000 + i * 1000, price, 3.0))
    tracker.detect_divergence()          # may be None for this series; it must not raise


def test_the_volume_profile_fallback_loop_is_capped():
    engine = VolumeProfileEngine(VolumeProfileConfig(tick_size=0.01))
    candle = Candle(timestamp_ms=0, open=1.0, high=1000.0, low=0.0, close=999.0, volume=1000.0)

    started = time.perf_counter()
    profile = engine.compute_from_candles([candle], "2026-09-18")
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, "the fallback loop is uncapped again (took %.2fs for one candle)" % elapsed
    rows = getattr(profile, "levels", None) or getattr(profile, "volume_at_price", None) or []
    assert len(rows) <= 500, "the level count must be capped like the API route (got %d)" % len(rows)
