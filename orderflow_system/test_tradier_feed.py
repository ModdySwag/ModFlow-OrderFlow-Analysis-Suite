"""
Tests for Tradier feed — transport injection makes these offline-safe.
"""

from __future__ import annotations


from orderflow_system.data.tradier_feed import (
    TradierFeed,
    RateBudget,
    _map_status,
)


# ── RateBudget ───────────────────────────────────────────────────────────────────

class TestRateBudget:
    def test_take_returns_zero_when_under_limit(self):
        b = RateBudget(per_day=10)
        assert b.take() == 0.0
        assert b.used == 1

    def test_take_blocks_when_at_limit(self):
        b = RateBudget(per_day=2)
        b.take()
        b.take()
        wait = b.take()
        assert wait > 0
        assert b.blocked == 1

    def test_used_counts_hits_in_window(self):
        b = RateBudget(per_day=5, window_s=60.0)
        for _ in range(5):
            b.take()
        assert b.used == 5


# ── TradierError ─────────────────────────────────────────────────────────────────

class TestTradierError:
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


def _mock_transport(status, body):
    def transport(method, url, headers, params, timeout):
        return (status, {}, body)
    return transport


# ── TradierFeed ──────────────────────────────────────────────────────────────────

class TestTradierFeed:
    def test_empty_symbol_returns_error(self):
        feed = TradierFeed(key_id="k", secret="s",
                           transport=_mock_transport(200, "[]"))
        r = feed.chains("")
        assert r.error == "empty symbol"
        assert r.chains == []

    def test_no_keys_returns_empty_auth(self):
        feed = TradierFeed(key_id="", secret="",
                           transport=_mock_transport(200, "[]"))
        r = feed.chains("SPY")
        assert r.error is None or r.error == ""

    def test_401_is_fatal(self):
        feed = TradierFeed(key_id="bad", secret="bad",
                           transport=_mock_transport(401, "Unauthorized"))
        r = feed.chains("SPY")
        assert r.error is not None
        assert "credentials" in r.error.lower()

    def test_429_returns_error(self):
        feed = TradierFeed(key_id="k", secret="s",
                           transport=_mock_transport(429, "Rate limited"))
        r = feed.chains("SPY")
        assert r.error is not None
        assert "rate" in r.error.lower()

    def test_malformed_json_returns_error(self):
        feed = TradierFeed(key_id="k", secret="s",
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
                        "expiration_date": "2026-09-18",
                        "strikes": [
                            {
                                "strike": 450.0,
                                "call": {"bid": 5.0, "ask": 5.5, "last": 5.2, "mark": 5.1,
                                         "implied_volatility": 0.22, "open_interest": 1000,
                                         "volume": 200, "option_symbol": "SPY260918C00450000"},
                                "put": {"bid": 2.0, "ask": 2.5, "last": 2.2, "mark": 2.1,
                                        "implied_volatility": 0.18, "open_interest": 800,
                                        "volume": 150, "option_symbol": "SPY260918P00450000"}
                            },
                            {
                                "strike": 460.0,
                                "call": {"bid": 2.0, "ask": 2.5, "last": 2.2, "mark": 2.1,
                                         "implied_volatility": 0.20, "open_interest": 500,
                                         "volume": 100, "option_symbol": "SPY260918C00460000"},
                                "put": {"bid": 5.0, "ask": 5.5, "last": 5.2, "mark": 5.1,
                                        "implied_volatility": 0.24, "open_interest": 1200,
                                        "volume": 300, "option_symbol": "SPY260918P00460000"}
                            }
                        ]
                    },
                    {
                        "expiration_date": "2026-09-25",
                        "strikes": [
                            {
                                "strike": 455.0,
                                "call": {"bid": 3.0, "ask": 3.5, "last": 3.2, "mark": 3.1,
                                         "implied_volatility": 0.21, "open_interest": 600,
                                         "volume": 80, "option_symbol": "SPY260925C004550000"},
                                "put": {"bid": 4.0, "ask": 4.5, "last": 4.2, "mark": 4.1,
                                        "implied_volatility": 0.23, "open_interest": 900,
                                        "volume": 120, "option_symbol": "SPY260925P004550000"}
                            }
                        ]
                    }
                ]
            }
        })
        feed = TradierFeed(key_id="k", secret="s",
                           transport=_mock_transport(200, body))
        r = feed.chains("SPY")
        assert r.error is None
        assert len(r.chains) == 2
        assert r.chains[0].symbol == "SPY"
        assert r.chains[0].expiry == "2026-09-18"
        assert len(r.chains[0].legs) == 4  # 2 strikes x 2 sides
        assert r.chains[1].expiry == "2026-09-25"
        assert len(r.chains[1].legs) == 2  # 1 strike x 2 sides

        legs = r.chains[0].legs
        calls = [l for l in legs if l.side == "call"]
        puts = [l for l in legs if l.side == "put"]
        assert len(calls) == 2
        assert len(puts) == 2

        c450 = [l for l in calls if l.strike == 450.0][0]
        assert c450.bid == 5.0
        assert c450.ask == 5.5
        assert c450.iv == 0.22
        assert c450.oi == 1000

        p460 = [l for l in puts if l.strike == 460.0][0]
        assert p460.bid == 5.0
        assert p460.iv == 0.24
        assert p460.oi == 1200

    def test_parse_skips_nonfinite_strike(self):
        body = (
            '{"options": {"expirations": ['
            '{"expiration_date": "2026-09-18", "strikes": ['
            '{"strike": 450.0, "call": {}, "put": {}},'
            '{"strike": null, "call": {}, "put": {}},'
            '{"strike": "inf", "call": {}, "put": {}}'
            ']}'
            ']'
            '}}'
        )
        feed = TradierFeed(key_id="k", secret="s",
                           transport=_mock_transport(200, body))
        r = feed.chains("SPY")
        assert len(r.chains) == 1
        assert len(r.chains[0].legs) == 2  # only the valid 450.0 strike

    def test_status(self):
        feed = TradierFeed(key_id="k", secret="s",
                           transport=_mock_transport(200, "[]"))
        feed.chains("SPY")
        s = feed.status()
        assert s["source"] == "tradier"
        assert s["key_configured"] is True
        assert s["used"] >= 1


# ── _num helper ──────────────────────────────────────────────────────────────────

class TestNum:
    def test_float(self):
        assert TradierFeed._num(1.5) == 1.5

    def test_int(self):
        assert TradierFeed._num(42) == 42.0

    def test_none(self):
        assert TradierFeed._num(None) is None

    def test_nan(self):
        assert TradierFeed._num(float("nan")) is None

    def test_inf(self):
        assert TradierFeed._num(float("inf")) is None

    def test_string(self):
        assert TradierFeed._num("1.5") == 1.5

    def test_bad_string(self):
        assert TradierFeed._num("not a number") is None
