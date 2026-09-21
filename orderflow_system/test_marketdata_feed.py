"""
Tests for Market Data feed — transport injection makes these offline-safe.
"""

from __future__ import annotations


from orderflow_system.data.marketdata_feed import (
    MarketDataFeed,
    RateBudget,
    _map_status,
)


def _mock_transport(status, body):
    def transport(method, url, headers, params, timeout):
        return (status, {}, body)
    return transport


# ── RateBudget ───────────────────────────────────────────────────────────────────

class TestRateBudget:
    def test_take_returns_zero_when_under_limit(self):
        b = RateBudget(per_minute=10)
        assert b.take() == 0.0
        assert b.used == 1

    def test_take_blocks_when_at_limit(self):
        b = RateBudget(per_minute=2)
        b.take()
        b.take()
        wait = b.take()
        assert wait > 0
        assert b.blocked == 1


# ── MarketDataError ──────────────────────────────────────────────────────────────

class TestMarketDataError:
    def test_401_is_fatal(self):
        err = _map_status(401)
        assert err.fatal is True

    def test_429_is_not_fatal(self):
        err = _map_status(429)
        assert err.fatal is False


# ── _map_status ──────────────────────────────────────────────────────────────────

class TestMapStatus:
    def test_401(self):
        err = _map_status(401)
        assert err.status == 401
        assert err.fatal is True

    def test_429(self):
        err = _map_status(429)
        assert err.status == 429
        assert err.fatal is False

    def test_500(self):
        err = _map_status(500)
        assert err.fatal is True


# ── MarketDataFeed ───────────────────────────────────────────────────────────────

class TestMarketDataFeed:
    def test_empty_symbol_returns_error(self):
        feed = MarketDataFeed(api_key="k",
                              transport=_mock_transport(200, "[]"))
        r = feed.chains("")
        assert r.error == "empty symbol"

    def test_401_is_fatal(self):
        feed = MarketDataFeed(api_key="bad",
                              transport=_mock_transport(401, "Unauthorized"))
        r = feed.chains("SPY")
        assert r.error is not None
        assert "key" in r.error.lower()

    def test_429_returns_error(self):
        feed = MarketDataFeed(api_key="k",
                              transport=_mock_transport(429, "Rate limited"))
        r = feed.chains("SPY")
        assert r.error is not None
        assert "rate" in r.error.lower()

    def test_malformed_json_returns_error(self):
        feed = MarketDataFeed(api_key="k",
                              transport=_mock_transport(200, "not json"))
        r = feed.chains("SPY")
        assert r.error is not None
        assert "malformed" in r.error.lower()

    def test_chains_parses_valid_response(self):
        import json
        body = json.dumps({
            "options": {
                "expirations": [
                    {
                        "expiration": "2026-09-18",
                        "strikes": [
                            {
                                "strike": 450.0,
                                "type": "call",
                                "bid": 5.0, "ask": 5.5, "last": 5.2,
                                "iv": 0.22, "open_interest": 1000, "volume": 200,
                                "delta": 0.65, "gamma": 0.02, "theta": -0.05, "vega": 0.10,
                                "symbol": "SPY260918C00450000"
                            },
                            {
                                "strike": 450.0,
                                "type": "put",
                                "bid": 2.0, "ask": 2.5, "last": 2.2,
                                "iv": 0.18, "open_interest": 800, "volume": 150,
                                "delta": -0.35, "gamma": 0.02, "theta": -0.03, "vega": 0.08,
                                "symbol": "SPY260918P00450000"
                            }
                        ]
                    },
                    {
                        "expiration": "2026-09-25",
                        "strikes": [
                            {
                                "strike": 455.0,
                                "type": "call",
                                "bid": 3.0, "ask": 3.5, "last": 3.2,
                                "iv": 0.21, "open_interest": 600, "volume": 80,
                                "delta": 0.55, "gamma": 0.015, "theta": -0.04, "vega": 0.09,
                                "symbol": "SPY260925C004550000"
                            },
                            {
                                "strike": 455.0,
                                "type": "put",
                                "bid": 4.0, "ask": 4.5, "last": 4.2,
                                "iv": 0.23, "open_interest": 900, "volume": 120,
                                "delta": -0.45, "gamma": 0.015, "theta": -0.03, "vega": 0.07,
                                "symbol": "SPY260925P004550000"
                            }
                        ]
                    }
                ]
            }
        })
        feed = MarketDataFeed(api_key="k",
                              transport=_mock_transport(200, body))
        r = feed.chains("SPY")
        assert r.error is None
        assert len(r.chains) == 2

        call_leg = r.chains[0].legs[0]
        assert call_leg.side == "call"
        assert call_leg.strike == 450.0
        assert call_leg.delta == 0.65
        assert call_leg.gamma == 0.02
        assert call_leg.theta == -0.05
        assert call_leg.vega == 0.10

        put_leg = r.chains[0].legs[1]
        assert put_leg.side == "put"
        assert put_leg.delta == -0.35

    def test_status(self):
        feed = MarketDataFeed(api_key="k",
                              transport=_mock_transport(200, "[]"))
        feed.chains("SPY")
        s = feed.status()
        assert s["source"] == "marketdata"
        assert s["key_configured"] is True
        assert s["used"] >= 1


# ── _num helper ──────────────────────────────────────────────────────────────────

class TestNum:
    def test_float(self):
        assert MarketDataFeed._num(1.5) == 1.5

    def test_int(self):
        assert MarketDataFeed._num(42) == 42.0

    def test_none(self):
        assert MarketDataFeed._num(None) is None

    def test_nan(self):
        assert MarketDataFeed._num(float("nan")) is None

    def test_inf(self):
        assert MarketDataFeed._num(float("inf")) is None

    def test_string(self):
        assert MarketDataFeed._num("1.5") == 1.5

    def test_bad_string(self):
        assert MarketDataFeed._num("not a number") is None
