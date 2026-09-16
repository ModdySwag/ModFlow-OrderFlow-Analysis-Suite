"""Displacement is measured in TRUE tick steps — one unit for every instrument class.

The v0.1b sweep found this calibration defect: `patterns/absorption.py` (the "price
displaced little" gate) and `patterns/initiative.py` (the candle-body gate) divided
displacement by `max(tick_size, 0.01)`. That floor was inert for every instrument with
tick >= 0.01 — i.e. the tool has always run on true tick steps for indices, stocks and
major crypto — but for the 25 instruments with tick < 0.01 it silently redefined the
unit: on EURUSD "2 ticks" meant 0.02 = 2,000 real ticks (absorption's gate vacuous at
candle scale) and initiative's body requirement became a ~300-pip move (so it could
never fire). These tests pin the single unit, fine-tick and coarse-tick alike:

    a level N ticks from the current price is N footprint levels away;
    a candle body of N ticks spans N price levels.

Written before the fix and proven to bite: the fine-tick cases fail on the clamped
divisor, the coarse-tick and fallback cases pass on both sides (they pin what must NOT
move).
"""

from __future__ import annotations

from orderflow_system.analytics.delta import DeltaResult
from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.config.settings import (
    AbsorptionConfig,
    InitiativeConfig,
    Instrument,
    get_config_for,
)
from orderflow_system.data.models import Candle, FootprintLevel, SignalType
from orderflow_system.patterns.absorption import AbsorptionDetector
from orderflow_system.patterns.initiative import InitiativeDetector

ABS_CFG = AbsorptionConfig(min_aggressive_volume=10.0, big_trade_filter=1.0,
                           min_attempts=2, max_price_displacement_ticks=2.0)
INI_CFG = InitiativeConfig(min_delta_threshold=1.0, volume_acceleration_min=0.5,
                           min_price_displacement_ticks=3.0, delta_price_alignment=True)
DELTA_BUY = DeltaResult(vertical_delta=5.0, buy_volume=70.0, sell_volume=65.0)


def _bar(*prices: float) -> FootprintBar:
    return FootprintBar(timestamp_ms=0, levels={
        p: FootprintLevel(price=p, bid_volume=20.0, ask_volume=5.0) for p in prices})


def _candle(ts: int, open_: float, close: float, vol: float = 100.0) -> Candle:
    pad = abs(close - open_) * 0.1 + 1e-9
    return Candle(timestamp_ms=ts, open=open_, high=max(open_, close) + pad,
                  low=min(open_, close) - pad, close=close, volume=vol,
                  buy_volume=vol * 0.7, sell_volume=vol * 0.3)


def _event_prices(det: AbsorptionDetector) -> list[float]:
    return sorted(ev.price for ev in det._active_absorptions.values())


# ── absorption gate ──────────────────────────────────────────────────────────────────

def test_absorption_gate_is_true_tick_steps_on_a_fine_tick_instrument():
    """EURUSD-like: 0-, 1- and 5-tick levels offered; only the true-tick set may qualify."""
    det = AbsorptionDetector(ABS_CFG, tick_size=0.00001)
    candle = _candle(0, 1.08500, 1.08500)

    det._check_level_absorption(candle, _bar(1.08500, 1.08501, 1.08505), current_price=1.08500)

    prices = _event_prices(det)
    assert len(prices) == 2, f"expected the 0- and 1-tick levels only, got {prices}"
    assert all(abs(p - 1.08505) > 1e-7 for p in prices), "a 5-tick level is not 'little displacement'"


def test_absorption_gate_unchanged_on_a_coarse_tick_instrument():
    """The shipped unit for tick >= 0.01 instruments — must be identical before/after."""
    det = AbsorptionDetector(ABS_CFG, tick_size=0.1)
    candle = _candle(0, 18500.0, 18500.0)

    det._check_level_absorption(candle, _bar(18500.0, 18500.1, 18500.5), current_price=18500.0)

    prices = _event_prices(det)
    assert len(prices) == 2, f"expected the 0- and 1-tick levels only, got {prices}"
    assert all(abs(p - 18500.5) > 1e-6 for p in prices)


# ── initiative body gate ─────────────────────────────────────────────────────────────

def test_initiative_body_gate_is_true_tick_steps_on_a_fine_tick_instrument():
    """A 4-tick body qualifies on EURUSD-like ticks; a 2-tick body does not."""
    det = InitiativeDetector(INI_CFG, tick_size=0.00001)
    sig = det.check_candle(_candle(1000, 1.08500, 1.08504), DELTA_BUY, FootprintBar())
    assert sig is not None, "a 4-tick body on a fine-tick instrument is a real displacement now"
    assert sig.signal_type == SignalType.INITIATIVE
    assert sig.details["body_ticks"] == 4.0

    det2 = InitiativeDetector(INI_CFG, tick_size=0.00001)
    assert det2.check_candle(_candle(1000, 1.08500, 1.08502), DELTA_BUY, FootprintBar()) is None


def test_initiative_body_gate_unchanged_on_a_coarse_tick_instrument():
    det = InitiativeDetector(INI_CFG, tick_size=0.1)
    assert det.check_candle(_candle(1000, 18500.0, 18500.4), DELTA_BUY, FootprintBar()) is not None
    det2 = InitiativeDetector(INI_CFG, tick_size=0.1)
    assert det2.check_candle(_candle(1000, 18500.0, 18500.2), DELTA_BUY, FootprintBar()) is None


# ── the real configuration this was found on ─────────────────────────────────────────

def test_eurusd_config_now_reads_true_ticks_end_to_end():
    """The exact finding, pinned on the shipped config: 2 ticks means 2 ticks on EURUSD."""
    cfg = get_config_for(Instrument.EURUSD)
    assert cfg.tick_size == 0.00001
    assert cfg.absorption.max_price_displacement_ticks == 2.0

    det = AbsorptionDetector(cfg.absorption, tick_size=cfg.tick_size)
    candle = _candle(0, 1.08500, 1.08500)
    det._check_level_absorption(candle, _bar(1.08500, 1.08501, 1.08505), current_price=1.08500)

    prices = _event_prices(det)
    assert len(prices) == 2, f"EURUSD must read true ticks now (got {prices})"
    assert all(abs(p - 1.08505) > 1e-7 for p in prices)

    assert cfg.initiative.min_price_displacement_ticks == 3.0
    ini = InitiativeDetector(cfg.initiative, tick_size=cfg.tick_size)
    # Warm the volume window so the EURUSD bank's 1.4x acceleration gate can pass.
    ini.check_candle(_candle(900, 1.08500, 1.08500, vol=20.0), DELTA_BUY, FootprintBar())
    delta_eur = DeltaResult(vertical_delta=20.0, buy_volume=80.0, sell_volume=60.0)
    sig = ini.check_candle(_candle(1000, 1.08500, 1.08504, vol=100.0), delta_eur, FootprintBar())
    assert sig is not None, "initiative on EURUSD must be reachable again under true ticks"


def test_a_degenerate_zero_tick_falls_back_instead_of_dividing_by_zero():
    """A non-positive tick cannot come from config, but must never crash the pipeline."""
    det = AbsorptionDetector(ABS_CFG, tick_size=0)
    candle = _candle(0, 1.0, 1.0)
    det._check_level_absorption(candle, _bar(1.0), current_price=1.0)   # no exception

    ini = InitiativeDetector(INI_CFG, tick_size=0)
    ini.check_candle(_candle(1000, 1.0, 1.0004), DELTA_BUY, FootprintBar())  # no exception
