"""Alpaca REST/session/subscription tests (plan T22 + T24) — stub transport, no network.

Pinned here, because each one is a bug the user would otherwise feel:
  * the client-side budget can never exceed the window (a self-inflicted 429 looks
    like an outage and burns the account's real allowance);
  * a closed market does not poll snapshots in a hot loop;
  * a clock failure degrades soft instead of stopping the feed;
  * the assets cache round-trips through disk within its 24 h window;
  * subscription caps trim with a visible warning, and add/remove are idempotent.
"""

from __future__ import annotations

import json

import pytest

from orderflow_system.data.alpaca_feed import (
    AlpacaData,
    AlpacaFeed,
    RateBudget,
    SubscriptionSet,
)


class StubTransport:
    """Routes by URL substring; records every call."""

    def __init__(self, routes: dict[str, tuple[int, object]]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, method, url, headers, params, timeout):
        self.calls.append((method, url, params or {}))
        for needle, (status, payload) in self.routes.items():
            if needle in url:
                body = payload if isinstance(payload, str) else json.dumps(payload)
                return status, {}, body
        return 404, {}, json.dumps({"message": "no stub route", "url": url})

    def urls(self) -> str:
        return "\n".join(call[1] for call in self.calls)


CLOCK_OPEN = {"is_open": True, "timestamp": "2026-09-15T13:30:00Z", "next_close": "2026-09-15T20:00:00Z"}
CLOCK_CLOSED = {"is_open": False, "timestamp": "2026-09-15T23:30:00Z", "next_open": "2026-09-16T13:30:00Z"}
SNAPSHOT_AAPL = {
    "latestTrade": {"T": "t", "S": "AAPL", "p": 182.42, "s": 100, "t": "2026-09-15T13:30:00Z", "i": 5},
    "latestQuote": {"T": "q", "S": "AAPL", "bp": 182.40, "bs": 1, "ap": 182.44, "as": 2,
                    "t": "2026-09-15T13:30:00.500Z"},
}


# ── budget ──────────────────────────────────────────────────────────────

def test_budget_never_exceeds_the_window():
    now = {"t": 1000.0}
    budget = RateBudget(per_minute=150, clock=lambda: now["t"])
    allowed = sum(1 for _ in range(300) if budget.take() == 0.0)
    assert allowed == 150, "the client must stop at its own limit, not Alpaca's"
    assert budget.blocked == 150
    assert budget.used == 150

    now["t"] += 61.0                                     # the window slides
    assert budget.take() == 0.0
    assert budget.blocked == 150 and budget.used == 1


def test_budget_reports_a_wait_instead_of_dropping_the_call():
    now = {"t": 0.0}
    budget = RateBudget(per_minute=2, clock=lambda: now["t"])
    assert budget.take() == 0.0 and budget.take() == 0.0
    wait = budget.take()
    assert wait == pytest.approx(60.0), "the caller is told exactly how long to wait"
    assert budget.snapshot()["limit"] == 2


# ── REST client ─────────────────────────────────────────────────────────

def test_429_backs_off_then_succeeds():
    calls = {"n": 0}

    def transport(method, url, headers, params, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {"Retry-After": "0"}, json.dumps({"message": "rate limited"})
        return 200, {}, json.dumps({"is_open": True})

    data = AlpacaData("k", "s", transport=transport)
    status, body = data.call("https://api.alpaca.markets/v2/clock")
    assert status == 200 and body == {"is_open": True} and calls["n"] == 2


def test_clock_failure_degrades_soft():
    transport = StubTransport({"clock": (500, {"message": "boom"})})
    data = AlpacaData("k", "s", transport=transport)
    assert data.clock() is None
    assert data.is_open() is None
    assert "clock" in (data.last_error or "")


def test_closed_market_skips_snapshot_polling():
    transport = StubTransport({"clock": (200, CLOCK_CLOSED),
                               "snapshots": (200, {"AAPL": SNAPSHOT_AAPL})})
    data = AlpacaData("k", "s", transport=transport)
    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=lambda *a: None, data=data)
    report = __import__("asyncio").run(feed.poll_once())
    assert report["market_open"] is False
    assert report["equities"] == 0
    assert "snapshots" not in transport.urls(), "a closed market must not be polled for quotes"


def test_open_market_polls_batched_snapshots_once():
    import asyncio
    transport = StubTransport({"clock": (200, CLOCK_OPEN),
                               "snapshots": (200, {"AAPL": SNAPSHOT_AAPL, "MSFT": SNAPSHOT_AAPL})})
    data = AlpacaData("k", "s", transport=transport)
    ticks: list[tuple[str, object]] = []
    feed = AlpacaFeed({"AAPL": "AAPL", "MSFT": "MSFT"}, on_tick=lambda s, t: ticks.append((s, t)), data=data)
    report = asyncio.run(feed.poll_once())
    assert report["market_open"] is True and report["equities"] == 2
    assert [s for s, _t in ticks] == ["AAPL", "MSFT"]
    snap_calls = [u for u in transport.urls().splitlines() if "snapshots" in u]
    assert len(snap_calls) == 1, "one batched call, not one per symbol"


def test_assets_cache_round_trips_through_disk(tmp_path):
    transport = StubTransport({"assets": (200, [{"symbol": "AAPL", "tradable": True}])})
    data = AlpacaData("k", "s", transport=transport, cache_dir=str(tmp_path))
    first = data.assets()
    second = data.assets()
    assert first == second == [{"symbol": "AAPL", "tradable": True}]
    assert len([u for u in transport.urls().splitlines() if "assets" in u]) == 1, "the second read is cached"
    data.assets(force=True)
    assert len([u for u in transport.urls().splitlines() if "assets" in u]) == 2, "force bypasses the cache"


def test_crypto_bars_work_without_keys():
    transport = StubTransport({"crypto/us/bars": (200, {"bars": {"BTC/USD": [
        {"t": "2026-09-15T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]}})})
    data = AlpacaData("", "", transport=transport)
    rows = data.crypto_bars("BTC/USD", limit=5)
    assert rows and rows[0]["c"] == 1.5
    method, url, params = transport.calls[0]
    assert "apca-api-key-id" not in {k.lower() for k in (transport.calls[0][2] or {})}


# ── subscriptions ───────────────────────────────────────────────────────

def test_subscription_caps_trim_oldest_with_a_visible_warning():
    warnings: list[str] = []
    subs = SubscriptionSet(stock_cap=3, on_warn=warnings.append)
    subs.add("trades", ["AAPL", "MSFT", "NVDA"])
    subs.add("trades", ["TSLA"])
    assert subs.trades == ["MSFT", "NVDA", "TSLA"], "the oldest symbol is the one that goes"
    assert warnings and "TSLA" in warnings[0] and "allows 3" in warnings[0]
    assert subs.as_dict()["warnings"], "warnings must reach the UI payload"


def test_subscription_add_remove_are_idempotent():
    subs = SubscriptionSet(stock_cap=30)
    assert subs.add("trades", ["AAPL", "AAPL", "", None]) == ["AAPL"]
    assert subs.add("trades", ["AAPL"]) == []
    assert subs.remove("trades", ["AAPL", "NOPE"]) == ["AAPL"]
    assert subs.remove("trades", ["AAPL"]) == []
    assert subs.frame("trades") == {}
    with pytest.raises(ValueError):
        subs.add("nonsense", ["AAPL"])


def test_quotes_have_their_own_cap():
    subs = SubscriptionSet(stock_cap=2, option_cap=4)
    subs.add("quotes", ["AAPL"])
    subs.add("quotes", ["SPY260116C00450000"])
    assert subs.quotes == ["AAPL", "SPY260116C00450000"], "option quotes are not capped with equities"


# ── the feed ────────────────────────────────────────────────────────────

def test_capability_block_describes_the_free_plan():
    from orderflow_system.desktop.engine import alpaca_capability_block
    cfg = {"alpaca": {"key_id": "PK1", "secret": "s", "paper": True, "feed": "iex", "enabled": True},
           "instruments": [{"symbol": "AAPL", "enabled": True},
                           {"symbol": "MSFT", "enabled": False},
                           {"symbol": "BTCUSDT", "enabled": True}]}
    block = alpaca_capability_block(cfg, {"capabilities": {"equities_sip_delayed": False},
                                          "limits": {"rest_per_min": 200, "websocket_symbols": 30}})
    assert block["linked"] is True
    assert block["feeds"] == ["iex"], "a Basic account must not be offered SIP"
    assert block["symbol_limit"] == 30 and block["rest_budget"] == 150
    assert block["symbols"] == {"AAPL": "AAPL", "BTCUSDT": "BTC/USD"}, "only enabled instruments"
    assert block["depth"] is False and "no order book" in block["depth_reason"]


def test_capability_block_offers_sip_to_an_entitled_account():
    from orderflow_system.desktop.engine import alpaca_capability_block
    cfg = {"alpaca": {"key_id": "PK1", "secret": "s", "enabled": True},
           "instruments": [{"symbol": "AAPL", "enabled": True, "alpaca_symbol": "AAPL"}]}
    block = alpaca_capability_block(cfg, {"capabilities": {"equities_sip_delayed": True},
                                          "limits": {"rest_per_min": 10000, "websocket_symbols": 10000}})
    assert block["feeds"] == ["iex", "delayed_sip", "sip"]
    assert block["symbol_limit"] == 10000


def test_capability_block_without_a_probe_is_honest():
    from orderflow_system.desktop.engine import alpaca_capability_block
    block = alpaca_capability_block({"instruments": []}, None)
    assert block["linked"] is False
    assert block["feeds"] == ["iex"]
    assert block["depth"] is False


def test_feed_awaits_an_async_on_tick():
    """`OrderflowSystem._on_tick` is a coroutine. A synchronous call returns a coroutine
    object that never runs — every tick is lost while the log says "seeded"."""
    import asyncio
    got: list[tuple[str, object]] = []

    async def on_tick(symbol, tick):
        got.append((symbol, tick))

    transport = StubTransport({"v1beta3/crypto/us/bars": (200, {"bars": {"BTC/USD": [
        {"t": "2026-09-15T13:30:00Z", "o": 60000, "h": 60100, "l": 59900, "c": 60050, "v": 3}]}})})
    feed = AlpacaFeed({"BTCUSDT": "BTC/USD"}, on_tick=on_tick,
                      data=AlpacaData("k", "s", transport=transport))

    async def run():
        await feed.start()                     # captures the loop
        await feed.seed_history()
        await asyncio.sleep(0.05)              # let the scheduled deliveries run
        await feed.stop()
        return len(got)

    assert asyncio.run(run()) > 0, "seeded ticks must actually reach the async callback"


def test_keyless_feed_does_not_poll_rest():
    """Without keys every call is a 401: poll nothing, and say so in the status."""
    import asyncio
    transport = StubTransport({"clock": (200, CLOCK_OPEN), "snapshots": (200, {"AAPL": SNAPSHOT_AAPL})})
    data = AlpacaData("", "", transport=transport)
    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=lambda *a: None, data=data)
    report = asyncio.run(feed.poll_once())
    assert report["equities"] == 0 and "no keys" in report["note"]
    assert transport.calls == [], "nothing may be requested without credentials"
    assert feed.status()["needs_keys"] is True


def test_feed_history_asks_for_the_recent_window():
    """Alpaca pages forward from `start`: without one, `limit` yields the OLDEST bars
    (the first live smoke seeded yesterday's tape instead of the last four hours)."""
    import asyncio
    from datetime import datetime, timedelta, timezone

    transport = StubTransport({"v1beta3/crypto/us/bars": (200, {"bars": {"BTC/USD": []}})})
    data = AlpacaData("k", "s", transport=transport)
    feed = AlpacaFeed({"BTCUSDT": "BTC/USD"}, on_tick=lambda *a: None, data=data, history_minutes=240)
    asyncio.run(feed.seed_history())

    _method, url, params = transport.calls[0]
    assert "start" in params and "end" in params, "the window must be explicit"
    start = datetime.strptime(params["start"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end = datetime.strptime(params["end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert end - start == pytest.approx(timedelta(minutes=240), abs=timedelta(seconds=2))
    assert end >= datetime.now(timezone.utc) - timedelta(minutes=2), "history ends now, not yesterday"
    assert params["limit"] == "240"


def test_feed_status_declares_no_depth():
    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=lambda *a: None, data=AlpacaData(transport=StubTransport({})))
    status = feed.status()
    assert status["depth"] is False
    assert "no order book" in status["depth_reason"]
    assert status["symbols"] == {"AAPL": "AAPL"}


def test_feed_history_seeding_emits_ticks_mapped_to_the_app_symbol():
    import asyncio
    bars = {"bars": [{"t": "2026-09-15T13:30:00Z", "o": 10, "h": 11, "l": 9.5, "c": 10.5, "v": 300},
                     {"t": "2026-09-15T13:31:00Z", "o": 10.5, "h": 12, "l": 10.2, "c": 11.8, "v": 400}]}
    transport = StubTransport({"stocks/AAPL/bars": (200, bars),
                               "v1beta3/crypto/us/bars": (200, {"bars": {"BTC/USD": [
                                   {"t": "2026-09-15T13:30:00Z", "o": 60000, "h": 60100, "l": 59900,
                                    "c": 60050, "v": 3}]}})})
    data = AlpacaData("k", "s", transport=transport)
    got: list[tuple[str, object]] = []
    feed = AlpacaFeed({"AAPL": "AAPL", "BTCUSDT": "BTC/USD"}, on_tick=lambda s, t: got.append((s, t)), data=data)
    total = asyncio.run(feed.seed_history())
    assert total > 0
    assert {s for s, _t in got} == {"AAPL", "BTCUSDT"}, "history lands on the app's own symbols"
    stamp = got[0][1].timestamp_ms
    assert stamp == 1789479000000 and all(t.timestamp_ms >= stamp for _s, t in got)
def test_a_repeated_snapshot_print_is_delivered_once():
    """A REST snapshot repeats its `latestTrade` until a new print exists; re-delivering it as a
    fresh tick counted the same fill over and over into volume and delta."""
    import asyncio
    transport = StubTransport({"clock": (200, CLOCK_OPEN),
                               "snapshots": (200, {"AAPL": SNAPSHOT_AAPL})})
    data = AlpacaData("k", "s", transport=transport)
    ticks: list[tuple[str, object]] = []
    feed = AlpacaFeed({"AAPL": "AAPL"}, on_tick=lambda s, t: ticks.append((s, t)), data=data)

    first = asyncio.run(feed.poll_once())
    second = asyncio.run(feed.poll_once())

    assert first["equities"] == 1 and len(ticks) == 1
    assert second["equities"] == 0 and second["unchanged"] == 1, second
    assert len(ticks) == 1, "the same print must not be delivered twice"
