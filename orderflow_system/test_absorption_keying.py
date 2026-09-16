"""Absorption events key on the instrument's tick, not a fixed 4-decimal round (Tier 1.4).

Two levels one tick apart on a fine-tick instrument (forex 1e-5, DOGE/TRX) both collapsed to
the same ``round(price, 4)`` key, so a single candle could "confirm" absorption across two
distinct prices and fire with the attempts counter already at threshold. The key now uses the
footprint/volume-profile convention: ``round(round(price / tick) * tick, 10)``.
"""

from __future__ import annotations

from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.config.settings import AbsorptionConfig
from orderflow_system.data.models import Candle, FootprintLevel
from orderflow_system.patterns.absorption import AbsorptionDetector

CFG = AbsorptionConfig(min_aggressive_volume=10.0, big_trade_filter=1.0,
                       min_attempts=2, max_price_displacement_ticks=2.0)
CANDLE = Candle(timestamp_ms=0, open=1.0850, high=1.0851, low=1.0849, close=1.0850,
                volume=100.0, buy_volume=10.0, sell_volume=90.0)


def _bar(levels: dict[float, dict[str, float]]) -> FootprintBar:
    return FootprintBar(timestamp_ms=0, levels={
        p: FootprintLevel(price=p, **v) for p, v in levels.items()})


def test_two_adjacent_fine_tick_levels_stay_two_events():
    det = AbsorptionDetector(CFG, tick_size=0.00001)
    bar = _bar({1.08501: {"bid_volume": 20.0, "ask_volume": 5.0},
                1.08502: {"bid_volume": 20.0, "ask_volume": 5.0}})

    signal = det._check_level_absorption(CANDLE, bar, current_price=1.08501)

    assert signal is None, "two distinct one-attempt levels must not fire repeated absorption"
    assert len(det._active_absorptions) == 2, det._active_absorptions
    assert all(ev.attempts == 1 for ev in det._active_absorptions.values())

    # A second pass over the same levels IS a genuine repeat: that one may fire.
    signal2 = det._check_level_absorption(CANDLE, bar, current_price=1.08501)
    assert signal2 is not None and signal2.details["type"] == "level_absorption"


def test_coarse_tick_levels_stay_distinct():
    """For tick >= 1e-4 (every non-fine instrument) the new key equals the old one."""
    det = AbsorptionDetector(CFG, tick_size=0.1)
    bar = _bar({18500.0: {"bid_volume": 20.0, "ask_volume": 5.0},
                18500.1: {"bid_volume": 20.0, "ask_volume": 5.0}})

    det._check_level_absorption(CANDLE, bar, current_price=18500.0)

    assert len(det._active_absorptions) == 2, det._active_absorptions


def test_same_level_repeated_fires_after_min_attempts():
    det = AbsorptionDetector(CFG, tick_size=0.00001)
    bar = _bar({1.08501: {"bid_volume": 20.0, "ask_volume": 5.0}})

    assert det._check_level_absorption(CANDLE, bar, current_price=1.08501) is None
    signal = det._check_level_absorption(CANDLE, bar, current_price=1.08501)
    assert signal is not None
    assert signal.details["attempts"] == 2
