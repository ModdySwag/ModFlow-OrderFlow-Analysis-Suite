"""Extrapolated analytics: correlation, dot map, cross-venue BBO, and the Numbers-Bars pack.

Three of these rebuild the *function* of a the reference platform add-on and one the function of the DTC platform
Chart's Numbers Bars study (see docs/PLATFORM_BRIDGES.md §4). They are arithmetic over data
this build already has, so they are testable without any vendor software running.
"""

from __future__ import annotations

import math

import pytest

from orderflow_system.analytics.footprint import FootprintEngine, analyse_levels
from orderflow_system.atlas.correlation import CorrelationTracker
from orderflow_system.atlas.crossvenue import VenueTop, build
from orderflow_system.atlas.dots import DotMap
from orderflow_system.data.models import Side, Tick


def _tick(price: float, size: float, ts_ms: int, buy: bool = True) -> Tick:
    return Tick(timestamp_ms=ts_ms, price=price, size=size, side=Side.BUY if buy else Side.SELL)


# ── correlation ────────────────────────────────────────────────────────────────────
def _series(n: int = 30) -> list[float]:
    """A deterministic price path with *varying* returns (a constant-rate path has no
    dispersion, which the tracker correctly refuses to score)."""
    prices, level = [], 100.0
    for i in range(n):
        level *= 1.0 + (0.01 if i % 3 else -0.015) + (0.002 if i % 5 == 0 else 0.0)
        prices.append(round(level, 6))
    return prices


def test_identical_series_correlate_perfectly():
    tracker = CorrelationTracker(bucket_ms=60_000, window=100, min_samples=5)
    for i, price in enumerate(_series(30)):
        tracker.on_tick("A", price, i * 60_000)
        tracker.on_tick("B", price * 3.0, i * 60_000)      # same shape, different level
    pair = tracker.pair("A", "B")
    assert pair["ok"] and pair["r"] == pytest.approx(1.0, abs=1e-6)
    assert pair["n"] == 29


def test_opposite_series_correlate_negatively():
    """An inverted price path (C / price) has exactly negated log returns."""
    tracker = CorrelationTracker(min_samples=5)
    for i, price in enumerate(_series(30)):
        tracker.on_tick("A", price, i * 60_000)
        tracker.on_tick("B", 10_000.0 / price, i * 60_000)
    assert tracker.pair("A", "B")["r"] == pytest.approx(-1.0, abs=1e-6)


def test_a_constant_rate_move_is_not_a_correlation():
    """Every bucket up 1% has identical returns: dispersion is float noise, so Pearson over
    it is meaningless (it measured 0.73 on a perfectly in-phase pair). Refuse, don't guess."""
    tracker = CorrelationTracker(min_samples=5)
    for i in range(30):
        tracker.on_tick("A", 100.0 * (1.01 ** i), i * 60_000)
        tracker.on_tick("B", 100.0 * (1.02 ** i), i * 60_000)
    pair = tracker.pair("A", "B")
    assert pair["ok"] is False and pair["r"] is None
    assert "no dispersion" in pair["reason"]


def test_insufficient_overlap_is_reported_not_guessed():
    tracker = CorrelationTracker(min_samples=10)
    for i in range(30):
        tracker.on_tick("A", 100 + i, i * 60_000)
    for i in range(4):
        tracker.on_tick("B", 50 + i, i * 60_000)
    pair = tracker.pair("A", "B")
    assert pair["ok"] is False and pair["r"] is None and pair["n"] == 3
    assert "shared buckets" in pair["reason"]


def test_a_flat_series_has_no_correlation_to_report():
    """Zero variance is not "perfectly correlated" — it is undefined, and must say so."""
    tracker = CorrelationTracker(min_samples=3)
    for i in range(10):
        tracker.on_tick("FLAT", 100.0, i * 60_000)
        tracker.on_tick("MOVES", 100.0 + i, i * 60_000)
    pair = tracker.pair("FLAT", "MOVES")
    assert pair["ok"] is False and "no dispersion" in pair["reason"]


def test_matrix_is_symmetric_with_unit_diagonal_and_counts():
    tracker = CorrelationTracker(min_samples=3)
    for i in range(12):
        tracker.on_tick("A", 100 + i, i * 60_000)
        tracker.on_tick("B", 200 + 2 * i, i * 60_000)
        tracker.on_tick("C", 50 - i, i * 60_000)
    grid = tracker.matrix()
    assert grid["symbols"] == ["A", "B", "C"]
    m = grid["matrix"]
    for i in range(3):
        assert m[i][i] == 1.0
        for j in range(3):
            assert m[i][j] == pytest.approx(m[j][i])
    assert grid["samples"][0][1] > 0 and grid["ready"] is True
    top = tracker.pairs(limit=2)
    assert len(top) == 2 and abs(top[0]["r"]) >= abs(top[1]["r"])


def test_backfill_from_candles_replaces_the_series():
    tracker = CorrelationTracker(min_samples=3)
    tracker.on_tick("A", 1.0, 0)
    n = tracker.backfill("A", [(i * 60_000, 100 + i) for i in range(8)])
    assert n == 8
    assert tracker.stats()["buckets"]["A"] == 8


def test_window_evicts_old_buckets():
    tracker = CorrelationTracker(bucket_ms=1_000, window=5, min_samples=3)
    for i in range(20):
        tracker.on_tick("A", 100 + i, i * 1_000)
    assert tracker.stats()["buckets"]["A"] <= 6            # window + the in-flight bucket


# ── volume-dot cluster map ─────────────────────────────────────────────────────────
def test_nearby_prints_merge_into_one_bubble():
    dots = DotMap("BTCUSDT", tick_size=0.1, window_ms=60_000, cluster_ms=250)
    for i in range(5):
        dots.on_tick(_tick(100.0, 1.0, 1_000 + i * 40))
    snap = dots.snapshot()
    assert snap["shown"] == 1
    assert snap["dots"][0]["count"] == 5 and snap["dots"][0]["size"] == 5.0
    assert dots.stats()["merged_prints"] == 4


def test_prints_beyond_the_cluster_window_start_a_new_bubble():
    dots = DotMap("BTCUSDT", tick_size=0.1, window_ms=60_000, cluster_ms=100)
    dots.on_tick(_tick(100.0, 1.0, 1_000))
    dots.on_tick(_tick(100.0, 2.0, 1_500))
    assert dots.snapshot()["shown"] == 2


def test_sides_never_merge():
    """A buy and a sell at the same price a tick apart are a flip, not one bubble."""
    dots = DotMap("BTCUSDT", tick_size=0.1, cluster_ms=1_000)
    dots.on_tick(_tick(100.0, 1.0, 1_000, buy=True))
    dots.on_tick(_tick(100.0, 1.0, 1_100, buy=False))
    snap = dots.snapshot()
    assert [d["side"] for d in snap["dots"]] == ["buy", "sell"]


def test_min_size_filters_before_clustering():
    dots = DotMap("BTCUSDT", tick_size=0.1, cluster_ms=10_000, min_size=5.0)
    for _ in range(4):
        dots.on_tick(_tick(100.0, 1.0, 1_000))
    dots.on_tick(_tick(100.0, 6.0, 1_050))
    snap = dots.snapshot()
    assert snap["shown"] == 1 and snap["dots"][0]["count"] == 1 and snap["dots"][0]["size"] == 6.0
    assert dots.stats()["dropped_small"] == 4


def test_window_eviction_and_payload_cap():
    dots = DotMap("BTCUSDT", tick_size=1.0, window_ms=1_000, cluster_ms=0, max_dots=50)
    for i in range(200):
        dots.on_tick(_tick(100.0 + i, 1.0, i * 10))
    snap = dots.snapshot(max_dots=10)
    assert snap["shown"] == 10 and len(snap["dots"]) <= 10
    assert dots.stats()["evicted"] > 0
    assert snap["legend"]["max"] >= snap["legend"]["min"]


def test_empty_dot_map_is_an_empty_payload():
    snap = DotMap("NOPE").snapshot()
    assert snap["dots"] == [] and snap["shown"] == 0 and snap["legend"] == {"min": 0.0, "max": 0.0}


# ── cross-venue BBO ────────────────────────────────────────────────────────────────
def test_two_venues_produce_a_consolidated_best():
    result = build([
        VenueTop("bybit", "Bybit", "depth", bid=100.0, bid_size=2.0, ask=100.5, ask_size=3.0, ts_ms=1_000),
        VenueTop("alpaca", "Alpaca (BTC/USD)", "quote", bid=100.2, bid_size=1.0,
                 ask=100.4, ask_size=4.0, ts_ms=1_000),
    ], now_ms=1_200, stale_ms=5_000)
    cons = result["consolidated"]
    assert cons["available"] and cons["bid"] == 100.2 and cons["bid_venue"] == "alpaca"
    assert cons["ask"] == 100.4 and cons["ask_venue"] == "alpaca"
    assert cons["spread"] == pytest.approx(0.2)
    assert set(cons["venues_used"]) == {"bybit", "alpaca"}
    assert result["kind"] == "top_of_book"          # only one venue publishes depth
    assert "only one venue publishes depth" in result["note"]


def test_stale_venue_is_excluded_and_flagged():
    result = build([
        VenueTop("bybit", "Bybit", "depth", bid=100.0, bid_size=1.0, ask=100.5, ask_size=1.0, ts_ms=1_000),
        VenueTop("alpaca", "Alpaca", "quote", bid=200.0, bid_size=1.0, ask=200.5, ask_size=1.0, ts_ms=0),
    ], now_ms=100_000, stale_ms=5_000)
    rows = {r["venue"]: r for r in result["venues"]}
    assert rows["bybit"]["stale"] is True and rows["bybit"]["ok"] is False
    assert rows["alpaca"]["ts_ms"] == 0 and rows["alpaca"]["stale"] is False      # unknown age is not stale
    assert result["consolidated"]["ask_venue"] == "alpaca"


def test_no_venue_can_answer_says_why():
    result = build([
        VenueTop("bybit", "Bybit", "depth", ok=False, note="engine not running"),
        VenueTop("alpaca", "Alpaca", "quote", ok=False, note="no Alpaca symbol mapped"),
    ])
    assert result["consolidated"]["available"] is False
    assert "engine not running" in result["consolidated"]["reason"]
    assert "no Alpaca symbol mapped" in result["consolidated"]["reason"]


def test_crossed_market_is_reported_not_hidden():
    result = build([
        VenueTop("bybit", "Bybit", "depth", bid=100.4, bid_size=1.0, ask=100.6, ask_size=1.0, ts_ms=1_000),
        VenueTop("alpaca", "Alpaca", "quote", bid=100.9, bid_size=1.0, ask=100.95, ask_size=1.0, ts_ms=1_000),
    ], now_ms=1_100)
    assert result["consolidated"]["crossed"] is True
    assert result["consolidated"]["spread"] < 0


def test_a_quote_feed_may_be_slower_than_a_depth_feed():
    """Alpaca's crypto quotes update a few times a minute; calling a 14-second-old quote
    stale threw away a usable top of book. The policy is per kind, and each row says which
    window it was measured against."""
    fresh_by_quote_rule = build([
        VenueTop("bybit", "Bybit", "depth", bid=100.0, bid_size=1.0, ask=100.5, ask_size=1.0, ts_ms=1_000),
        VenueTop("alpaca", "Alpaca", "quote", bid=100.2, bid_size=1.0, ask=100.4, ask_size=1.0, ts_ms=1_000),
    ], now_ms=1_000 + 14_000)
    rows = {r["venue"]: r for r in fresh_by_quote_rule["venues"]}
    assert rows["bybit"]["ok"] is False and rows["bybit"]["stale_after_ms"] == 5_000
    assert rows["alpaca"]["ok"] is True and rows["alpaca"]["stale_after_ms"] == 60_000
    assert fresh_by_quote_rule["consolidated"]["available"] is True
    assert fresh_by_quote_rule["stale_policy"]["quote_ms"] == 60_000


def test_unknown_age_is_reported_as_unknown_not_stale():
    """A venue whose clock is not comparable (ts_ms == 0) is not called stale — that would
    be inventing an age."""
    result = build([VenueTop("bybit", "Bybit", "depth", bid=100.0, bid_size=1.0,
                             ask=100.5, ask_size=1.0, ts_ms=0)])
    row = result["venues"][0]
    assert row["age_known"] is False and row["stale"] is False and row["ok"] is True
    assert result["consolidated"]["available"] is True


def test_invalid_rows_are_not_used():
    result = build([VenueTop("bybit", "Bybit", "depth", bid=0.0, ask=0.0, ts_ms=1_000)], now_ms=1_100)
    assert result["consolidated"]["available"] is False
    assert result["venues"][0]["ok"] is False


# ── Numbers-Bars pack ──────────────────────────────────────────────────────────────
ROWS = {100.0: (10.0, 30.0),      # ask-heavy at the level  → buy imbalance (3:1)
        101.0: (2.0, 8.0),        # ask-heavy, but the row below has 10 bid → not diagonal
        102.0: (5.0, 5.0)}        # equal sides


def test_same_price_and_diagonal_imbalance_differ_where_the_convention_matters():
    same = analyse_levels(ROWS, 1.0, threshold=3.0, mode="same_price")
    diag = analyse_levels(ROWS, 1.0, threshold=3.0, mode="diagonal")
    assert [i["price"] for i in same["imbalances"]] == [100.0, 101.0]
    assert [i["price"] for i in diag["imbalances"]] == [100.0]
    assert same["imbalance_counts"] == {"buy": 2, "sell": 0}
    assert diag["imbalance_counts"] == {"buy": 1, "sell": 0}


def test_diagonal_mode_infers_the_tick_from_the_rows_it_has():
    rows = {100.0: (10.0, 30.0), 100.25: (2.0, 8.0), 100.5: (5.0, 5.0)}
    out = analyse_levels(rows, 0.0, threshold=3.0, mode="diagonal")
    assert [i["price"] for i in out["imbalances"]] == [100.0]


def test_calculated_values_row():
    out = analyse_levels(ROWS, 1.0)
    assert out["volume"] == 60.0 and out["buy"] == 43.0 and out["sell"] == 17.0
    assert out["delta"] == 26.0 and out["dominant"] == "buy"
    assert out["poc"]["price"] == 100.0
    assert out["poc"]["share_pct"] == pytest.approx(66.6667, abs=1e-3)
    assert out["poc"]["delta"] == 20.0
    assert out["max_bid"]["price"] == 100.0 and out["max_bid"]["volume"] == 10.0
    assert out["max_ask"]["price"] == 100.0 and out["max_ask"]["volume"] == 30.0
    assert out["extremes"]["max"]["price"] == 100.0 and out["extremes"]["min"]["price"] == 102.0
    assert [e["price"] for e in out["equal"]] == [102.0]


def test_equal_tolerance_is_relative_and_off_by_default():
    rows = {100.0: (100.0, 102.0)}
    assert analyse_levels(rows)["equal"] == []
    assert [e["price"] for e in analyse_levels(rows, equal_tolerance=0.05)["equal"]] == [100.0]


def test_empty_levels_are_an_empty_pack():
    out = analyse_levels({})
    assert out["volume"] == 0.0 and out["poc"] is None and out["imbalances"] == []
    assert out["dominant"] == "flat"


def test_one_sided_rows_are_flagged_in_both_modes():
    out = analyse_levels({100.0: (0.0, 5.0)}, mode="same_price")
    assert out["imbalances"][0]["side"] == "buy" and out["imbalances"][0]["ratio"] is None


def test_print_size_filter_applies_while_building():
    engine = FootprintEngine(tick_size=1.0, min_print_size=10.0)
    bar = engine.build_from_ticks([
        _tick(100.0, 5.0, 1_000), _tick(100.0, 25.0, 1_001, buy=True), _tick(100.0, 50.0, 1_002, buy=False),
    ])
    assert engine.filtered_prints == 1
    level = bar.levels[100.0]
    assert level.ask_volume == 25.0 and level.bid_volume == 50.0
    assert bar.calculated_values(tick_size=1.0)["volume"] == 75.0


def test_all_prints_filtered_yields_an_empty_bar_not_a_crash():
    engine = FootprintEngine(tick_size=1.0, min_print_size=99.0)
    bar = engine.build_from_ticks([_tick(100.0, 1.0, 1_000)])
    assert bar.levels == {} and engine.filtered_prints == 1


def test_bar_calculated_values_delegates_to_the_pack():
    engine = FootprintEngine(tick_size=0.5)
    bar = engine.build_from_ticks([
        _tick(100.0, 4.0, 1_000, buy=True), _tick(100.0, 1.0, 1_001, buy=False),
        _tick(100.5, 9.0, 1_002, buy=True),
    ])
    calc = bar.calculated_values(tick_size=0.5)
    assert calc["volume"] == 14.0 and calc["buy"] == 13.0 and calc["sell"] == 1.0
    assert calc["imbalance_counts"]["buy"] >= 1


# ── endpoint wiring (the payload the panels actually receive) ──────────────────────
def _bar() -> dict:
    return {"time": 1.0, "open": 100.0, "high": 101.0, "low": 100.0, "close": 101.0, "poc": 100.0,
            "levels": [{"price": 100.0, "bid": 10.0, "ask": 30.0},
                       {"price": 101.0, "bid": 2.0, "ask": 8.0}]}


def test_footprint_payload_carries_the_pack_in_the_requested_mode():
    from orderflow_system.dashboard.app import _annotate_footprint_bars

    same = _annotate_footprint_bars([_bar()], mode="same_price")
    diag = _annotate_footprint_bars([_bar()], mode="diagonal")
    assert same[0]["calc"]["imbalance_counts"]["buy"] == 2
    assert diag[0]["calc"]["imbalance_counts"]["buy"] == 1
    assert same[0]["calc"]["mode"] == "same_price" and diag[0]["calc"]["mode"] == "diagonal"
    assert same[0]["calc"]["poc"]["price"] == 100.0


def test_footprint_handler_tolerates_direct_invocation():
    """Regression: with `Query(...)` defaults in the signature, calling the handler directly
    (as the tests and the replay path do) used to push a Query object into the maths."""
    import asyncio

    from orderflow_system.dashboard.app import get_footprint

    bars = asyncio.run(get_footprint("BTCUSDT"))          # no engine → demo path
    assert bars and isinstance(bars, list)
    assert all("calc" in bar for bar in bars)
    assert bars[0]["calc"]["mode"] == "same_price"
