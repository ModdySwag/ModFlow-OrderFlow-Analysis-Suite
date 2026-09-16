"""Search service tests (plan Phase 4 — T31, T34, T36, T38).

Everything here is offline: the asset list, the clock and the live prices are
injected, so the ranking, the honest-degradation path and the batcher are pinned
without a network or an engine.
"""

from __future__ import annotations

import time


from orderflow_system.desktop.search_service import (
    RowBatcher,
    SymbolUniverse,
    chain_rows,
    feed_label,
    market_status,
    normalize_expiries,
    score_row,
    sort_rows,
    with_greeks_summary,
)

ASSETS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "class": "us_equity", "exchange": "NASDAQ", "tradable": True},
    {"symbol": "AAPL.WS", "name": "Apple Inc. Warrants", "class": "us_equity", "exchange": "NASDAQ"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "class": "us_equity", "exchange": "NASDAQ"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "class": "etf", "exchange": "ARCA"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "class": "us_equity", "exchange": "NASDAQ"},
]

CONFIG = {
    "instruments": [
        {"symbol": "BTCUSDT", "asset_class": "Crypto", "enabled": True},
        {"symbol": "ETHUSDT", "asset_class": "Crypto", "enabled": True},
        {"symbol": "NAS100USDT", "asset_class": "Indices", "enabled": False},
    ],
    "alpaca": {"key_id": "PK1", "secret": "s", "paper": True, "feed": "iex"},
    "search": {"recents": ["SPY", "BTCUSDT"], "pins": ["NVDA"]},
    "watchlist": ["AAPL", "BTCUSDT"],
}

LIVE = {
    "BTCUSDT": {"last": 78_500.0, "chg_pct": 0.4, "volume": 1200.0, "subscribed": True,
                "spark": [1, 2, 3]},
    "NVDA": {"last": 138.5, "chg_pct": -1.2, "volume": 90.0, "subscribed": False},
}


def universe(**kw) -> SymbolUniverse:
    kwargs = dict(
        config=CONFIG,
        assets_provider=lambda: ASSETS,
        clock_provider=lambda: {"is_open": True, "next_close": "2026-09-15T20:00:00Z"},
        live_provider=lambda symbol: LIVE.get(symbol, {}),
        alpaca_linked=True,
        alpaca_feed="iex",
        alpaca_symbols={"BTCUSDT": "BTC/USD", "ETHUSDT": "ETH/USD"},
        local_feeds={"BTCUSDT": "alpaca_crypto", "ETHUSDT": "alpaca_crypto", "NAS100USDT": "mt5"},
    )
    kwargs.update(kw)
    return SymbolUniverse(**kwargs)


# ── ranking ─────────────────────────────────────────────────────────────

def test_ranking_exact_beats_prefix_beats_fuzzy():
    exact = score_row("AAPL", "AAPL", "Apple Inc.")
    prefix = score_row("AAP", "AAPL", "Apple Inc.")
    substring = score_row("PP", "AAPL", "Apple Inc.")
    fuzzy = score_row("AL", "AAPL", "Apple Inc.")          # a subsequence, not a substring
    assert exact > prefix > substring
    assert fuzzy > 0 and fuzzy < substring, "a subsequence hit ranks below a real substring"


def test_ranking_ignores_punctuation_and_case():
    assert score_row("btc/usd", "BTC/USD") == 1000.0
    assert score_row("btcusd", "BTC/USD") == 1000.0
    assert score_row("Apple", "AAPL", "Apple Inc.") >= 300.0


def test_search_exact_symbol_first_and_pins_boosted():
    u = universe()
    payload = u.search("NVDA")
    assert payload["ok"] and payload["rows"]
    assert payload["rows"][0]["symbol"] == "NVDA"
    assert payload["rows"][0]["source"] == "pin", "the pinned row is the one that wins"
    assert payload["rows"][0]["feed_label"] == "IEX"


def test_search_prefix_and_fuzzy_reach_the_assets():
    u = universe()
    assert [r["symbol"] for r in u.search("MSF")["rows"]][:2] == ["MSFT"]
    assert "SPY" in {r["symbol"] for r in u.search("spy")["rows"]}
    fuzzy = {r["symbol"] for r in u.search("NVD")["rows"]}
    assert "NVDA" in fuzzy


def test_fuzzy_alias_finds_the_local_instrument():
    """A broker spelling (USTEC) should still surface NAS100USDT — the alias hits."""
    u = universe()
    rows = {r.symbol: r for r in u.build_rows()}
    assert "NAS100USDT" in rows
    assert score_row("USTEC", "NAS100USDT", "USTEC") > 0


def test_limit_and_count_are_honest():
    u = universe()
    payload = u.search("A", limit=2)
    assert len(payload["rows"]) <= 2
    assert payload["total"] >= len(payload["rows"])
    payload = u.search("", limit=5)
    assert payload["rows"][0]["source"] == "pin", "an empty query lists the user's own symbols first"


def test_no_keys_degrades_to_recents_crypto_and_local():
    """Without an account the universe is recents + crypto + local instruments — and
    it says so; it does not silently pretend the asset list is empty because broken."""
    def boom():
        raise AssertionError("the asset list must not be fetched without keys")

    u = universe(alpaca_linked=False, assets_provider=boom)
    payload = u.search("SPY")
    assert payload["linked"] is False
    assert "SPY" in {r["symbol"] for r in payload["rows"]}, "a recent still resolves without an account"
    assert "AAPL" not in {r["symbol"] for r in u.search("AAPL")["rows"]}, \
        "an unknown ticker is honestly absent when the asset list is unreachable"
    # crypto and local instruments are always there
    assert "BTC/USD" in {r["symbol"] for r in u.search("BTC")["rows"]}
    assert "NAS100USDT" in {r["symbol"] for r in u.search("NAS100")["rows"]}
    # and the feed label stays honest
    assert u.search("BTC")["rows"][0]["feed_label"] in ("Crypto · Bybit", "Crypto · Alpaca")


def test_assets_are_cached_between_calls():
    calls = {"n": 0}

    def assets():
        calls["n"] += 1
        return ASSETS

    u = universe(assets_provider=assets)
    u.search("AA")
    u.search("AA")
    assert calls["n"] == 1, "the asset list is cached for a minute, then reused"


def test_types_filter():
    u = universe()
    crypto = u.search("BTC", types=["crypto"])["rows"]
    assert crypto and all(("/" in r["symbol"]) or r["asset_class"] == "crypto" for r in crypto)
    stocks = u.search("AAP", types=["stock"])["rows"]
    assert stocks and all("/" not in r["symbol"] for r in stocks)


def test_sorting_variants():
    u = universe()
    rows = u.build_rows()
    by_symbol = sort_rows(rows, "symbol")
    assert by_symbol == sorted(rows, key=lambda r: r.symbol)
    by_chg = sort_rows(rows, "chg")
    assert by_chg[0].chg_pct is not None and by_chg[-1].chg_pct is None, "missing values sink"
    empty_first = sort_rows(rows, "last")
    assert empty_first[0].last is not None


# ── market status + feed labels ─────────────────────────────────────────

def test_market_status_from_clock():
    assert market_status({"is_open": True})[0] == "open"
    status, help_text = market_status({"is_open": False, "next_open": "2030-01-01T14:30:00Z"})
    assert status == "closed" and "next open" in help_text.lower()
    soon = market_status({"is_open": False, "next_open": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                      time.gmtime(time.time() + 3600))})
    assert soon[0] == "pre"
    assert market_status(None)[0] == "unknown"
    assert market_status({"is_open": False})[0] == "closed"


def test_feed_labels_are_specific():
    assert feed_label("iex") == "IEX"
    assert feed_label("delayed_sip") == "Delayed SIP"
    assert feed_label("indicative") == "Indicative"
    assert feed_label("bybit") == "Crypto · Bybit"


def test_basic_account_is_never_offered_sip():
    u = universe(alpaca_feed="iex")
    feeds = {r.feed for r in u.build_rows()}
    assert "sip" not in feeds
    # and an entitled account does get the real feed key through
    u2 = universe(alpaca_feed="sip")
    assert u2.search("MSFT")["rows"][0]["feed"] == "sip"


# ── the batcher ─────────────────────────────────────────────────────────

def test_batcher_coalesces_within_the_window():
    b = RowBatcher(window_ms=300)
    for i in range(50):
        b.offer("AAPL", {"last": 100.0 + i}, now_ms=1000)
    rows = b.drain(now_ms=1100)                     # inside the window
    assert rows == [], "nothing is sent before the window closes"
    rows = b.drain(now_ms=1400)
    assert len(rows) == 1, "50 updates on one symbol collapse into one row"
    assert rows[0]["last"] == 149.0, "the newest value wins"
    counters = b.counters()
    assert counters["seen"] == 50 and counters["coalesced"] == 49 and counters["batches"] == 1


def test_batcher_stress_5000_messages_stay_bounded():
    b = RowBatcher(window_ms=300, max_symbols=200)
    symbols = [f"SYM{i:03d}" for i in range(500)]
    t = 0
    batch_sizes: list[int] = []
    for i in range(5000):
        t += 1
        b.offer(symbols[i % len(symbols)], {"last": float(i)}, now_ms=t)
        rows = b.drain(now_ms=t)
        if rows:
            batch_sizes.append(len(rows))
    rows = b.drain(now_ms=t + 1000)          # flush the open window
    if rows:
        batch_sizes.append(len(rows))

    counters = b.counters()
    assert counters["seen"] == 5000
    assert counters["dropped"] > 0, "symbols beyond the cap are dropped, visibly"
    assert b.pending() == 0
    assert max(batch_sizes) <= b.max_symbols, "a batch can never exceed the cap"
    assert sum(batch_sizes) == counters["rows_sent"]
    assert len(batch_sizes) == counters["batches"]
    assert counters["seen"] >= counters["rows_sent"] + counters["coalesced"], \
        "every message is accounted for: rows out + coalesced + dropped"


def test_batcher_cap_report_is_actionable():
    b = RowBatcher(window_ms=300, max_symbols=3)
    for i, sym in enumerate(("A", "B", "C", "D", "E")):
        b.offer(sym, {"last": 1.0}, now_ms=i)
    counters = b.counters()
    assert counters["dropped"] == 2 and counters["seen"] == 5
    assert b.pending() == 3


def test_batcher_ignores_empty_offers():
    b = RowBatcher()
    assert b.offer("", {"last": 1.0}) is False
    assert b.offer("AAPL", {}) is False
    assert b.counters()["seen"] == 0


# ── option chain ────────────────────────────────────────────────────────

CHAIN = {
    "snapshots": {
        "AAPL260116C00200000": {"latestQuote": {"bp": 5.1, "ap": 5.3, "bs": 3, "as": 4},
                                "latestTrade": {"p": 5.2}, "impliedVolatility": 0.31},
        "AAPL260116P00200000": {"latestQuote": {"bp": 4.1, "ap": 4.3}, "latestTrade": {"p": 4.2}},
        "AAPL260220C00210000": {"latestQuote": {"bp": 6.1, "ap": 6.3}},
        "AAPL260220C00180000": {"latestQuote": {"bp": 9.1, "ap": 9.9}},
    }
}


def test_expiries_are_sorted_and_unique():
    assert normalize_expiries(CHAIN) == ["2026-01-16", "2026-02-20"]
    assert normalize_expiries({"contracts": [{"expiration_date": "2026-03-20"}]}) == ["2026-03-20"]
    assert normalize_expiries(None) == []


def test_chain_rows_map_and_sort():
    rows = chain_rows(CHAIN)
    assert len(rows) == 4
    assert rows[0]["expiry"] == "2026-01-16"
    assert {r["type"] for r in rows} == {"call", "put"}
    call = next(r for r in rows if r["contract"].endswith("C00200000"))
    assert call["strike"] == 200.0 and call["bid"] == 5.1 and call["ask"] == 5.3
    assert call["feed_label"] == "Indicative", "options on the free plan are indicative"


def test_chain_filters_expiry_type_and_strike_bounds():
    assert {r["expiry"] for r in chain_rows(CHAIN, expiry="2026-02-20")} == {"2026-02-20"}
    assert {r["type"] for r in chain_rows(CHAIN, option_type="put")} == {"put"}
    strikes = {r["strike"] for r in chain_rows(CHAIN, strike_min=190, strike_max=205)}
    assert strikes == {200.0}
    assert chain_rows(CHAIN, strike_min=500) == []
    assert len(chain_rows(CHAIN, limit=2)) == 2


def test_chain_summary_is_truthful():
    summary = with_greeks_summary(chain_rows(CHAIN))
    assert summary["contracts"] == 4 and summary["strikes"] == 3      # 180, 200, 210
    assert summary["calls"] == 3 and summary["puts"] == 1
    assert summary["strike_min"] == 180.0 and summary["strike_max"] == 210.0
    assert summary["expiries"] == ["2026-01-16", "2026-02-20"]


def test_junk_chain_payload_is_ignored_not_guessed():
    assert chain_rows({}) == []
    assert chain_rows({"snapshots": {"NOT AN OCC": {}}}) == []
    assert chain_rows(None) == []
    assert chain_rows({"snapshots": {"AAPL260116C00200000": "not a dict"}}) == []
