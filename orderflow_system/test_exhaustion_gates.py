"""Exhaustion fire/no-fire bins, pinned (v0.1b audit Tier 1.3 — fix REJECTED, behaviour kept).

The audit read the bearish gate as "inverted" and proposed
``if vol_trend >= 0 or delta_roc >= 0: return None``. That change is deliberately NOT applied,
because it is wrong on the sign convention: in a down-trend the delta is negative and
"sellers exhausted / less selling conviction" means delta rising toward zero — delta_roc > 0.
The audit's form (require delta_roc < 0) would demand STRENGTHENING selling for a bearish
exhaustion signal, and would additionally silence the textbook dry-up bin below (volume down,
delta weakening). These tests pin the live bins so neither reading can drift silently.

Synthetics: the DeltaEngine gets three history candles (deltas and volumes chosen to set the
vol_trend / delta_roc signs); the detector gets four recent candles with descending lows
(bearish) or ascending highs (bullish) and a >= 30% volume decline, the current candle last.
"""

from __future__ import annotations

from orderflow_system.analytics.delta import DeltaEngine
from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.config.settings import ExhaustionConfig
from orderflow_system.data.models import Candle
from orderflow_system.patterns.exhaustion import ExhaustionDetector


def candle(ts, high, low, close, vol, buy, sell):
    return Candle(timestamp_ms=ts, open=close, high=high, low=low, close=close,
                  volume=vol, buy_volume=buy, sell_volume=sell, tick_count=5)


def _check(seed, recent):
    cfg = ExhaustionConfig(requires_contrarian_imbalance=False)
    det = ExhaustionDetector(cfg)
    eng = DeltaEngine(tick_size=0.1)
    last_delta = None
    for c in seed:
        last_delta = eng.compute_from_candle(c)
    fp = FootprintBar(timestamp_ms=recent[-1].timestamp_ms, levels={})
    return det.check_candle(recent[-1], last_delta, eng, fp, recent), eng


BEAR = [
    candle(1000, 11.0, 10.0, 10.2, 300, 150, 150),
    candle(2000, 10.6, 9.6, 9.8, 250, 120, 130),
    candle(3000, 10.0, 9.0, 9.2, 150, 90, 60),
    candle(4000, 9.4, 8.4, 8.6, 90, 60, 30),
]
BULL = [
    candle(1000, 10.0, 9.0, 9.8, 300, 150, 150),
    candle(2000, 10.6, 9.6, 10.4, 250, 130, 120),
    candle(3000, 11.2, 10.2, 11.0, 150, 90, 60),
    candle(4000, 11.8, 10.8, 11.6, 90, 60, 30),
]
# deltas -100, -20, +40 (rising); volumes 300, 220, 140 (falling) — the textbook bearish dry-up
SEED_BEAR_DRYUP = [
    candle(1000, 11.0, 10.0, 10.2, 300, 100, 200),
    candle(2000, 10.6, 9.6, 9.8, 220, 100, 120),
    candle(3000, 10.0, 9.0, 9.2, 140, 90, 50),
]
# deltas +40, -20, -100 (falling = selling STRENGTHENING); volumes rising
SEED_BEAR_STRENGTHENING = [
    candle(1000, 11.0, 10.0, 10.2, 100, 70, 30),
    candle(2000, 10.6, 9.6, 9.8, 200, 90, 110),
    candle(3000, 10.0, 9.0, 9.2, 300, 100, 200),
]
# deltas +100, +20, -40 (falling = buying fading); volumes 300, 220, 140 (falling)
SEED_BULL_FADE = [
    candle(1000, 10.0, 9.0, 9.8, 300, 200, 100),
    candle(2000, 10.6, 9.6, 10.4, 220, 120, 100),
    candle(3000, 11.2, 10.2, 11.0, 140, 50, 90),
]


def test_bearish_fires_when_sellers_weaken_on_declining_volume():
    sig, eng = _check(SEED_BEAR_DRYUP, BEAR)
    assert sig is not None and sig.details["type"] == "bearish_exhaustion"
    assert eng.get_delta_roc(lookback=3) > 0, "sellers weakening = delta rising toward zero"


def test_bearish_does_not_fire_while_selling_strengthens():
    """The audit's 'should NOT fire' bin — the live code already passes it."""
    sig, eng = _check(SEED_BEAR_STRENGTHENING, BEAR)
    assert sig is None
    assert eng.get_delta_roc(lookback=3) < 0


def test_bullish_fires_when_buying_fades():
    sig, eng = _check(SEED_BULL_FADE, BULL)
    assert sig is not None and sig.details["type"] == "bullish_exhaustion"
    assert eng.get_delta_roc(lookback=3) < 0, "buying fading = delta falling from its positive base"


def test_the_two_branches_never_cross_wire():
    """Sellers weakening must read as bearish, buyers fading as bullish — never swapped."""
    bear_sig, _ = _check(SEED_BEAR_DRYUP, BEAR)
    bull_sig, _ = _check(SEED_BULL_FADE, BULL)
    assert bear_sig.details["type"] == "bearish_exhaustion"
    assert bull_sig.details["type"] == "bullish_exhaustion"
    assert bear_sig.direction.value == "buy"      # exhausted sellers → bullish reversal
    assert bull_sig.direction.value == "sell"     # exhausted buyers → bearish reversal
