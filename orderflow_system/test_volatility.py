
"""
Tests for the volatility surface engine — pure functions, no network.
"""

from __future__ import annotations


from orderflow_system.atlas.volatility import (
    IVStrike,
    compute_volatility,
)


def _ivstrike(price, iv, side, **kwargs):
    return IVStrike(price=price, iv=iv, side=side, **kwargs)


class TestEmptyChain:
    def test_empty_returns_zeros(self):
        r = compute_volatility([], spot=100.0)
        assert r.n_strikes == 0
        assert r.n_expiries == 0
        assert r.atm_iv is None
        assert r.skew_25d is None
        assert r.smile == []
        assert r.note == "empty chain"


class TestATMIV:
    def test_single_strike_is_atm(self):
        r = compute_volatility([_ivstrike(100.0, 0.1387, "call")], spot=100.0)
        assert r.atm_iv == 0.1387

    def test_nearest_strike_is_atm(self):
        r = compute_volatility([
            _ivstrike(90.0, 0.12, "put"),
            _ivstrike(105.0, 0.14, "call"),   # closer to 100 than 90
            _ivstrike(110.0, 0.15, "call"),
        ], spot=100.0)
        assert r.atm_iv == 0.14

    def test_atm_is_zero_when_no_iv(self):
        """No valid IV → clamped to 0.0 → atm_iv is 0.0."""
        r = compute_volatility([_ivstrike(100.0, None, "call")], spot=100.0)
        assert r.atm_iv == 0.0


class TestSmileCurve:
    def test_smile_is_ordered_by_price(self):
        r = compute_volatility([
            _ivstrike(90.0, 0.20, "put"),
            _ivstrike(100.0, 0.14, "call"),
            _ivstrike(110.0, 0.12, "call"),
        ], spot=100.0)
        strikes = [p["strike"] for p in r.smile]
        assert strikes == [90.0, 100.0, 110.0]

    def test_smile_has_iv_per_strike(self):
        r = compute_volatility([
            _ivstrike(90.0, 0.20, "put"),
            _ivstrike(100.0, 0.14, "call"),
        ], spot=100.0)
        assert r.smile[0]["iv"] == 0.20
        assert r.smile[1]["iv"] == 0.14

    def test_malformed_entries_skipped(self):
        r = compute_volatility([
            {"price": 100.0, "iv": 0.14, "side": "call"},
            "not a dict",
            None,
            42,
        ], spot=100.0)
        assert r.n_strikes == 1
        assert r.smile[0]["iv"] == 0.14


class TestSkew:
    def test_skew_requires_both_sides(self):
        r = compute_volatility([
            _ivstrike(100.0, 0.14, "call"),
            _ivstrike(105.0, 0.13, "call"),
        ], spot=100.0)
        assert r.skew_25d is None

    def test_skew_is_put_minus_call(self):
        r = compute_volatility([
            _ivstrike(80.0, 0.22, "put"),    # deep OTM put, high IV
            _ivstrike(100.0, 0.14, "call"),  # ATM
            _ivstrike(120.0, 0.10, "call"),  # deep OTM call, low IV
        ], spot=100.0)
        assert r.skew_25d is not None
        # Put IV (0.22) > call IV (0.10) → positive skew
        assert r.skew_25d > 0.0

    def test_negative_skew_when_puts_cheap(self):
        r = compute_volatility([
            _ivstrike(80.0, 0.10, "put"),    # cheap puts
            _ivstrike(100.0, 0.14, "call"),
            _ivstrike(120.0, 0.22, "call"),  # rich calls
        ], spot=100.0)
        assert r.skew_25d is not None
        assert r.skew_25d < 0.0   # negative skew

    def test_a_proxy_picked_wing_says_so_where_a_measured_wing_is_silent(self):
        """§148 / T7-F10: "25-delta" is a selection, not a measurement.

        When the chain arrives without deltas the wings are picked by the moneyness proxy
        (volatility._delta_prox), and the row has to say so — the why card promises the disclosure.
        A chain that carries real deltas says nothing, because nothing was assumed.
        """
        proxied = compute_volatility([
            _ivstrike(80.0, 0.22, "put"),
            _ivstrike(100.0, 0.14, "call"),
            _ivstrike(120.0, 0.10, "call"),
        ], spot=100.0)
        assert proxied.skew_25d is not None
        assert "moneyness proxy" in proxied.note, proxied.note

        measured = compute_volatility([
            _ivstrike(80.0, 0.22, "put", delta=-0.25),
            _ivstrike(100.0, 0.14, "call", delta=0.5),
            _ivstrike(120.0, 0.10, "call", delta=0.25),
        ], spot=100.0)
        assert measured.skew_25d is not None
        assert measured.note == "", measured.note


class TestTermStructure:
    def test_multiple_expiries(self):
        r = compute_volatility([
            _ivstrike(100.0, 0.14, "call", expiry_ms=1693555200000),   # Sep 2023
            _ivstrike(100.0, 0.15, "put", expiry_ms=1693555200000),
            _ivstrike(100.0, 0.16, "call", expiry_ms=1696147200000),   # Oct 2023
            _ivstrike(100.0, 0.17, "put", expiry_ms=1696147200000),
            _ivstrike(100.0, 0.18, "call", expiry_ms=1698825600000),   # Nov 2023
            _ivstrike(100.0, 0.19, "put", expiry_ms=1698825600000),
        ], spot=100.0)
        assert r.n_expiries == 3
        assert len(r.term_structure) == 3
        assert r.term_structure[0]["expiry_ms"] == 1693555200000
        assert r.term_structure[0]["atm_iv"] == 0.14   # Sep ATM
        assert r.term_structure[2]["expiry_ms"] == 1698825600000
        assert r.term_structure[2]["atm_iv"] == 0.18   # Nov ATM

    def test_single_expiry_has_one_entry(self):
        r = compute_volatility([
            _ivstrike(100.0, 0.14, "call", expiry_ms=1693555200000),
            _ivstrike(105.0, 0.13, "call", expiry_ms=1693555200000),
        ], spot=100.0)
        assert r.n_expiries == 1
        assert len(r.term_structure) == 1


class TestNonFiniteGuards:
    def test_nan_iv_is_zero(self):
        r = compute_volatility([_ivstrike(100.0, float("nan"), "call")], spot=100.0)
        assert r.smile[0]["iv"] == 0.0
        assert r.atm_iv == 0.0

    def test_inf_price_is_clamped(self):
        r = compute_volatility([_ivstrike(float("inf"), 0.14, "call")], spot=100.0)
        assert r.n_strikes == 1
        assert r.smile[0]["strike"] == 0.0

    def test_none_iv_is_zero(self):
        r = compute_volatility([_ivstrike(100.0, None, "call")], spot=100.0)
        assert r.smile[0]["iv"] == 0.0
