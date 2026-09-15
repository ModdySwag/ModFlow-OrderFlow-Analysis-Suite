"""Alpaca account linking — probe stages, masking, rate limiting.

The probe is the piece that talks to a real brokerage, so it is tested in stages the way
a user experiences it: nothing typed, wrong keys, unreachable host, and a full account
with its entitlement report. A stub transport stands in for Alpaca so the tests never
need live credentials.
"""

from __future__ import annotations

import json

import pytest

from orderflow_system.desktop import alpaca as al


def _transport(routes: dict[str, tuple[int, object]]):
    """Build a stub transport from path fragments → (status, body)."""

    def transport(method: str, url: str, headers: dict, params: dict | None, timeout: float):
        # most specific fragment wins: '/v2/account' must not shadow '/v2/account/portfolio/history'
        for frag, (status, body) in sorted(routes.items(), key=lambda kv: -len(kv[0])):
            if frag in url:
                payload = body if isinstance(body, str) else json.dumps(body)
                return status, {}, payload
        return 404, {}, json.dumps({"message": "not found"})

    return transport


ACCOUNT = {
    "status": "ACTIVE", "currency": "USD", "account_number": "PA3TESTNUMBER12345",
    "cash": "12000.50", "equity": "15000.75", "buying_power": "48000",
    "portfolio_value": "15000.75", "pattern_day_trader": False, "daytrade_count": 0,
    "trading_blocked": False, "shorting_enabled": True, "options_approved_level": 2,
    "created_at": "2026-01-02T00:00:00Z",
}


def test_probe_without_keys_names_the_first_step():
    out = al.probe({})
    assert out["ok"] is False and out["stage"] == "keys"
    assert "paper-trading account" in out["message"]
    assert out["help"].startswith("https://app.alpaca.markets")


def test_probe_maps_a_rejected_pair_and_names_the_likely_cause():
    """The classic mistake: paper keys against the live host (or the reverse)."""
    t = _transport({"/v2/account": (401, {"message": "unauthorized."})})
    out = al.probe({"key_id": "PKTESTKEY1234567", "secret": "s3cret-value"}, transport=t)
    assert out["ok"] is False and out["stage"] == "auth"
    assert "rejected these keys" in out["message"]
    assert "live" in out["message"], "must name the other environment as the likely cause"
    assert out["key_masked"].startswith("PKTE") and "s3cret" not in json.dumps(out)


def test_probe_reports_an_unreachable_api_distinctly():
    t = _transport({"/v2/account": (0, "URLError: getaddrinfo failed")})
    out = al.probe({"key_id": "PKTESTKEY1234567", "secret": "x"}, transport=t)
    assert out["stage"] == "api" and "HTTP 0" in out["message"]


def test_probe_ready_reports_account_and_entitlements_without_depth():
    t = _transport({
        "/v2/account": (200, ACCOUNT),
        "/v2/clock": (200, {"is_open": True, "next_open": "2026-09-16T13:30:00Z", "next_close": "2026-09-15T20:00:00Z"}),
        "/v2/assets": (200, [{"symbol": "AAPL", "tradable": True, "fractionable": True},
                             {"symbol": "MSFT", "tradable": True, "fractionable": True},
                             {"symbol": "XYZ", "tradable": False, "fractionable": False}]),
        "/trades/latest": (200, {"symbol": "AAPL", "trade": {"p": 231.4, "s": 100}}),
        "/v1beta1/news": (200, {"news": [{"headline": "Test headline", "symbols": ["AAPL"], "source": "benzinga"}]}),
        "/v1beta1/options/trades": (403, {"message": "forbidden"}),
        "/v2/positions": (200, [{"symbol": "AAPL", "qty": "3"}]),
        "/v2/orders": (200, [{"id": "1", "status": "new"}, {"id": "2", "status": "filled"}]),
        "/account/portfolio/history": (200, {"equity": [10000, 15000.75], "timeframe": "1D"}),
        "/crypto/us/bars": (200, {"bars": {"BTC/USD": [{"c": 76815.4}]}}),
        "/stocks/AAPL/bars": (200, {"bars": {"AAPL": [{"c": 230.0}]}}),
    })
    out = al.probe({"key_id": "PKTESTKEY1234567", "secret": "s", "paper": True}, transport=t)
    assert out["ok"] is True and out["stage"] == "ready"
    acct = out["account"]
    assert acct["status"] == "ACTIVE" and acct["equity"] == 15000.75
    assert acct["account_number_masked"].startswith("PA3T") and "TESTNUMBER" not in acct["account_number_masked"]
    assert acct["environment"] == "paper"
    caps = out["capabilities"]
    assert caps["equities_realtime_iex"] is True and caps["equities_sip_delayed"] is True
    assert caps["news"] is True and caps["options_data"] is False
    assert caps["positions"] is True and out["position_count"] == 1 and out["open_order_count"] == 1
    assert caps["portfolio_history"] is True and out["portfolio"]["points"] == 2
    assert caps["crypto_history_keyless"] is True
    assert out["depth_available"] is False
    assert any("No order book" in n for n in out["entitlement_notes"]), \
        "the report must say plainly that Alpaca has no depth"


def test_mask_key_never_reveals_the_secret_material():
    assert al.mask_key("PKABCDEFGHIJKLMNOP") == "PKAB…OP (18 chars)"
    assert al.mask_key("short") == "sh…"
    assert al.mask_key("") == ""


def test_rate_limiter_holds_the_app_under_alpacas_free_ceiling():
    limiter = al._RateLimiter(per_minute=3)
    waits = [limiter.take() for _ in range(4)]
    assert waits[:3] == [0.0, 0.0, 0.0]
    assert waits[3] > 0, "the fourth call inside the window must be told to wait"
    assert al.MAX_CALLS_PER_MIN <= 200, "never plan to exceed Alpaca's Basic-plan ceiling"
