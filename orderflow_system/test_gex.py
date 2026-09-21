"""
Tests for the GEX engine — pure functions, no network, no config, no UI.

Calibrate against Senzoukria's published NQ option chain example where possible.
"""

from __future__ import annotations

import pytest

from orderflow_system.atlas.gex import (
    Strike,
    compute_gex,
    from_deribit_ladder,
    _side_gamma,
    _side_delta,
)


# ── helpers ──────────────────────────────────────────────────────────────────────

def _strike(price, gamma, oi, side, **kwargs):
    return Strike(price=price, gamma=gamma, oi=oi, side=side, **kwargs)


# ── _side_gamma ──────────────────────────────────────────────────────────────────

class TestSideGamma:
    def test_call_is_negative(self):
        assert _side_gamma("call", 0.05) == -0.05
        assert _side_gamma("call", 0.0) == 0.0

    def test_put_is_positive(self):
        assert _side_gamma("put", 0.05) == 0.05

    def test_bad_side_defaults_to_call(self):
        assert _side_gamma("unknown", 0.05) == -0.05

    def test_nan_gamma_is_zero(self):
        assert _side_gamma("call", float("nan")) == 0.0
        assert _side_gamma("put", float("nan")) == 0.0


# ── _side_delta ──────────────────────────────────────────────────────────────────

class TestSideDelta:
    def test_atm_call_is_half(self):
        assert abs(_side_delta("call", 100.0, 100.0) - 0.5) < 1e-6

    def test_deep_itm_call_is_near_one(self):
        assert _side_delta("call", 50.0, 100.0) > 0.9

    def test_deep_otm_call_is_under_half(self):
        assert _side_delta("call", 150.0, 100.0) < 0.5

    def test_atm_put_is_minus_half(self):
        assert abs(_side_delta("put", 100.0, 100.0) + 0.5) < 1e-6

    def test_deep_itm_put_is_under_minus_half(self):
        assert _side_delta("put", 150.0, 100.0) < -0.5


# ── empty chain ──────────────────────────────────────────────────────────────────

class TestEmptyChain:
    def test_empty_returns_zeros(self):
        r = compute_gex([], spot=100.0, multiplier=1.0)
        assert r.n_strikes == 0
        assert r.zero_gamma_level is None
        assert r.call_walls == []
        assert r.put_walls == []
        assert r.total_dex == 0.0
        assert r.put_call_oi == 0.0
        assert r.n_strikes == 0
        assert r.note == "empty chain"


# ── single strike ────────────────────────────────────────────────────────────────

class TestSingleStrike:
    def test_one_call_above_spot(self):
        r = compute_gex([_strike(105.0, 0.02, 1000, "call")], spot=100.0, multiplier=1.0)
        assert r.n_strikes == 1
        assert r.call_oi == 1000.0
        assert r.put_oi == 0.0
        assert r.put_call_oi == 0.0
        # Dealer gamma for a call is negative.
        assert r.per_strike[0]["dealer_gamma"] == -0.02
        assert r.per_strike[0]["gamma_exp"] == -20.0   # -0.02 * 1000 * 1

    def test_one_put_below_spot(self):
        r = compute_gex([_strike(95.0, 0.03, 2000, "put")], spot=100.0, multiplier=1.0)
        assert r.put_oi == 2000.0
        assert r.call_oi == 0.0
        # Dealer gamma for a put is positive.
        assert r.per_strike[0]["dealer_gamma"] == 0.03
        assert r.per_strike[0]["gamma_exp"] == 60.0    # 0.03 * 2000 * 1

    def test_zero_gamma_level_with_one_strike(self):
        r = compute_gex([_strike(105.0, 0.02, 1000, "call")], spot=100.0, multiplier=1.0)
        # Entirely negative cumulative gamma → zero line at the edge (lowest strike).
        assert r.zero_gamma_level == 105.0

    def test_multiplier_scales_dex(self):
        r1 = compute_gex([_strike(105.0, 0.02, 1000, "call")], spot=100.0, multiplier=1.0)
        r100 = compute_gex([_strike(105.0, 0.02, 1000, "call")], spot=100.0, multiplier=100.0)
        assert r1.per_strike[0]["dex"] == pytest.approx(r100.per_strike[0]["dex"] / 100.0)


# ── balanced chain ───────────────────────────────────────────────────────────────

class TestBalancedChain:
    def test_two_strikes_opposite_signs(self):
        """A call above spot (dealer short gamma) and a put below spot (dealer long gamma)."""
        r = compute_gex([
            _strike(95.0, 0.03, 2000, "put"),
            _strike(105.0, 0.02, 1000, "call"),
        ], spot=100.0, multiplier=1.0)
        assert r.n_strikes == 2
        assert r.call_oi == 1000.0
        assert r.put_oi == 2000.0
        assert r.put_call_oi == 2.0
        # Cumulative gamma starts at +60 (put) then -20 (call) = +40 net.
        assert r.per_strike[0]["dealer_gamma"] == 0.03   # put
        assert r.per_strike[1]["dealer_gamma"] == -0.02  # call

    def test_zero_gamma_level_between_strikes(self):
        r = compute_gex([
            _strike(95.0, 0.04, 1000, "put"),
            _strike(105.0, 0.04, 1000, "call"),
        ], spot=100.0, multiplier=1.0)
        # Cum starts at +40 (put), then +40 - 40 = 0 at the call strike.
        assert r.zero_gamma_level == 105.0

    def test_wall_detection(self):
        r = compute_gex([
            _strike(90.0, 0.01, 100, "put"),
            _strike(95.0, 0.05, 2000, "put"),   # big put gamma below spot → put wall
            _strike(100.0, 0.01, 100, "call"),
            _strike(105.0, 0.05, 2000, "call"), # big call gamma above spot → call wall
            _strike(110.0, 0.01, 100, "call"),
        ], spot=100.0, multiplier=1.0, wall_quantile=0.8)
        assert len(r.put_walls) >= 1
        assert len(r.call_walls) >= 1
        # The 0.05-gamma strikes should be the walls.
        put_wall_prices = [ps["strike"] for ps in r.put_walls]
        call_wall_prices = [ps["strike"] for ps in r.call_walls]
        assert 95.0 in put_wall_prices
        assert 105.0 in call_wall_prices


# ── IV / skew / ATM ──────────────────────────────────────────────────────────────

class TestIVMetrics:
    def test_atm_iv(self):
        r = compute_gex([
            _strike(95.0, 0.02, 1000, "put", iv=0.20),
            _strike(100.0, 0.03, 2000, "call", iv=0.15),  # ATM
            _strike(105.0, 0.02, 1000, "put", iv=0.18),
        ], spot=100.0, multiplier=1.0)
        assert r.atm_iv == 0.15

    def test_skew_25d(self):
        r = compute_gex([
            _strike(80.0, 0.01, 500, "put", iv=0.22),     # ~25Δ put (deep OTM)
            _strike(85.0, 0.03, 1500, "put", iv=0.18),
            _strike(100.0, 0.03, 2000, "call", iv=0.14),  # ATM
            _strike(115.0, 0.03, 1500, "call", iv=0.12),  # ~25Δ call (deep OTM)
            _strike(120.0, 0.01, 500, "call", iv=0.10),
        ], spot=100.0, multiplier=1.0)
        assert r.skew_25d is not None
        # 25Δ put IV (~0.18) - 25Δ call IV (~0.12) ≈ +0.06 (positive skew = puts richer)
        assert r.skew_25d > 0.0
        assert r.skew_25d < 0.15

    def test_skew_none_without_both_sides(self):
        r = compute_gex([
            _strike(100.0, 0.03, 2000, "call", iv=0.15),
            _strike(105.0, 0.02, 1000, "call", iv=0.13),
        ], spot=100.0, multiplier=1.0)
        assert r.skew_25d is None


# ── from_deribit_ladder ──────────────────────────────────────────────────────────

class TestFromDeribitLadder:
    def test_empty_ladder(self):
        assert from_deribit_ladder({}) == []

    def test_single_strike_both_sides(self):
        ladder = {
            "strikes": [{
                "strike": 65000.0,
                "call": {"instrument": "BTC-16SEP26-65000-C", "gamma": 0.0001, "oi": 500,
                         "iv": 0.1387, "vega": 0.05, "theta": -0.02, "state": "active"},
                "put": {"instrument": "BTC-16SEP26-65000-P", "gamma": 0.00015, "oi": 300,
                        "iv": 0.1420, "vega": 0.06, "theta": -0.025, "state": "active"},
            }]
        }
        result = from_deribit_ladder(ladder)
        assert len(result) == 2
        calls = [r for r in result if r["side"] == "call"]
        puts = [r for r in result if r["side"] == "put"]
        assert len(calls) == 1
        assert len(puts) == 1
        assert calls[0]["price"] == 65000.0
        assert calls[0]["gamma"] == 0.0001
        assert calls[0]["oi"] == 500
        assert puts[0]["gamma"] == 0.00015

    def test_inactive_strike_skipped(self):
        ladder = {
            "strikes": [{
                "strike": 65000.0,
                "call": {"instrument": "BTC-16SEP26-65000-C", "gamma": 0.0, "oi": 0,
                         "state": "inactive"},
                "put": {"instrument": "BTC-16SEP26-65000-P", "gamma": 0.0001, "oi": 100,
                        "state": "active"},
            }]
        }
        result = from_deribit_ladder(ladder)
        # Only the active put should appear.
        assert len(result) == 1
        assert result[0]["side"] == "put"


# ── integration: full GEX from Deribit-shaped ladder ────────────────────────────

class TestFullGEXFromDeribit:
    def test_compute_from_ladder(self):
        ladder = {
            "strikes": [
                {"strike": 63000.0, "call": {"gamma": 0.0, "oi": 0, "state": "inactive"},
                 "put": {"gamma": 0.0002, "oi": 1000, "iv": 0.16, "vega": 0.08,
                         "theta": -0.03, "state": "active"}},
                {"strike": 64000.0, "call": {"gamma": 0.0001, "oi": 500, "iv": 0.15,
                                              "vega": 0.06, "theta": -0.02, "state": "active"},
                 "put": {"gamma": 0.00015, "oi": 800, "iv": 0.155, "vega": 0.07,
                         "theta": -0.025, "state": "active"}},
                {"strike": 65000.0, "call": {"gamma": 0.00012, "oi": 1200, "iv": 0.1387,
                                              "vega": 0.05, "theta": -0.02, "state": "active"},
                 "put": {"gamma": 0.0001, "oi": 400, "iv": 0.14, "vega": 0.04,
                         "theta": -0.018, "state": "active"}},
                {"strike": 66000.0, "call": {"gamma": 0.00008, "oi": 600, "iv": 0.13,
                                              "vega": 0.03, "theta": -0.015, "state": "active"},
                 "put": {"gamma": 0.00005, "oi": 200, "iv": 0.135, "vega": 0.02,
                         "theta": -0.012, "state": "active"}},
                {"strike": 67000.0, "call": {"gamma": 0.00003, "oi": 100, "iv": 0.12,
                                              "vega": 0.01, "theta": -0.01, "state": "active"},
                 "put": {"gamma": 0.00002, "oi": 50, "iv": 0.125, "vega": 0.01,
                         "theta": -0.008, "state": "active"}},
            ]
        }
        chain = from_deribit_ladder(ladder)
        r = compute_gex(chain, spot=641.0, multiplier=1.0)
        assert r.n_strikes == 9  # 5 strikes × 2 sides, minus 1 inactive call at 63000
        assert r.spot == 641.0
        assert r.zero_gamma_level is not None
        assert r.total_dex > 0
        assert r.put_call_oi > 0


# ── NaN / non-finite guards ──────────────────────────────────────────────────────

class TestNonFiniteGuards:
    def test_nan_oi_is_zero(self):
        r = compute_gex([_strike(100.0, 0.02, float("nan"), "call")], spot=100.0)
        assert r.call_oi == 0.0
        assert r.n_strikes == 1  # strike is kept, OI is 0

    def test_nan_gamma_is_zero(self):
        r = compute_gex([_strike(100.0, float("nan"), 1000, "call")], spot=100.0)
        assert r.per_strike[0]["gamma"] == 0.0
        assert r.per_strike[0]["dealer_gamma"] == 0.0

    def test_infinite_price_is_clamped(self):
        r = compute_gex([_strike(float("inf"), 0.02, 1000, "call")], spot=100.0)
        assert r.n_strikes == 1
        assert r.per_strike[0]["strike"] == 0.0  # _finite(inf) → None → 0.0

    def test_malformed_entry_skipped(self):
        r = compute_gex([
            {"price": 100.0, "gamma": 0.02, "oi": 1000, "side": "call"},
            "not a dict",
            42,
            None,
        ], spot=100.0)
        assert r.n_strikes == 1
