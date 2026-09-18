"""Unfinished business — the exact convention, the resolution rule and the live tracker, pinned.

The convention (atlas/unfinished.py): a high is unfinished when its top row trades *any* volume
on the BID side (the zero-on-bid completion never happened), a low when its bottom row trades any
volume on the ASK side. A magnet resolves when a later bar reaches or trades through the level
(never its own bar), or the moment a tick does — "price returns and fixes it".

``arms`` counts lifetime occurrences: a price left unfinished again after a revisit gets
``arms = 2`` — a level that keeps failing to auction is the stronger read.
"""

from __future__ import annotations

from orderflow_system.atlas.unfinished import (
    KIND_DETECTED,
    KIND_FIXED,
    UnfinishedTracker,
    classify_extremes,
    unfinished_from_bars,
)


def _lvl(price: float, bid: float = 0.0, ask: float = 0.0) -> dict:
    return {"price": price, "bid": bid, "ask": ask}


def test_convention_zero_on_bid_and_zero_on_ask():
    # bottom row carries ask volume -> unfinished low; top row carries bid volume -> unfinished high
    ext = classify_extremes({100.0: (5.0, 2.0), 100.5: (1.0, 4.0), 101.0: (3.0, 6.0)})
    assert ext["high"]["unfinished"] is True and ext["high"]["price"] == 101.0
    assert ext["low"]["unfinished"] is True and ext["low"]["price"] == 100.0

    # zero on bid at the top, zero on ask at the bottom -> both extremes properly auctioned
    ext = classify_extremes({100.0: (5.0, 0.0), 100.5: (1.0, 4.0), 101.0: (0.0, 6.0)})
    assert ext["high"]["unfinished"] is False
    assert ext["low"]["unfinished"] is False

    assert classify_extremes({}) == {"high": None, "low": None}


def test_from_bars_resolves_by_later_bar_reach():
    bars = [
        {"time": 1000.0, "levels": [_lvl(99.0, 2.0, 0.0), _lvl(100.0, 3.0, 5.0)]},   # unfinished high at 100
        {"time": 1060.0, "levels": [_lvl(99.5, 1.0, 0.0), _lvl(99.8, 0.0, 1.0)]},   # never reaches 100
        {"time": 1120.0, "levels": [_lvl(99.9, 1.0, 0.0), _lvl(100.0, 0.0, 2.0)]},   # reaches 100 -> fixed
    ]
    out = unfinished_from_bars(bars, tick_size=0.1)
    assert len(out) == 1
    lv = out[0]
    assert lv.side == "above" and lv.price == 100.0
    assert lv.active is False and lv.resolved_ts_ms == 1_120_000


def test_low_magnet_resolves_when_price_returns():
    bars = [
        {"time": 0.0, "levels": [_lvl(98.0, 0.0, 1.5), _lvl(99.0, 0.0, 0.0)]},       # unfinished low at 98
        {"time": 60.0, "levels": [_lvl(98.6, 0.0, 0.0), _lvl(98.8, 0.0, 0.0)]},      # above it, no touch
        {"time": 120.0, "levels": [_lvl(97.95, 0.0, 0.0), _lvl(98.05, 0.0, 0.0)]},   # back to 98 -> fixed
    ]
    out = unfinished_from_bars(bars, tick_size=0.1)
    assert len(out) == 1
    assert out[0].side == "below" and out[0].active is False
    assert out[0].resolved_ts_ms == 120_000


def test_bar_never_resolves_its_own_magnet():
    bars = [{"time": 0.0, "levels": [_lvl(100.0, 4.0, 1.0), _lvl(101.0, 3.0, 3.0)]}]
    out = unfinished_from_bars(bars, tick_size=0.1)
    assert len(out) == 2 and all(lv.active for lv in out)


def test_tracker_lifecycle_detect_fix_rearm():
    tr = UnfinishedTracker(tick_size=0.1)
    first = tr.on_bar(1000, {100.0: (1.0, 0.0), 101.0: (2.0, 0.5)})
    assert [e["kind"] for e in first] == [KIND_DETECTED]
    assert first[0]["price"] == 101.0 and first[0]["arms"] == 1

    second = tr.on_bar(2000, {100.0: (1.0, 0.0), 101.0: (3.0, 0.5)})
    assert [e["kind"] for e in second] == [KIND_FIXED, KIND_DETECTED]
    snap = tr.snapshot()
    assert [lv["arms"] for lv in snap["open"]] == [2]

    third = tr.on_tick(101.03, 3000)
    assert [e["kind"] for e in third] == [KIND_FIXED]
    assert tr.snapshot()["open"] == []


def test_bar_range_reaching_the_level_fixes_it():
    tr = UnfinishedTracker(tick_size=0.1)
    tr.on_bar(1000, {100.0: (1.0, 0.0), 101.0: (2.0, 0.5)})
    ev = tr.on_bar(1060, {101.0: (0.0, 2.0), 102.0: (0.0, 0.0)})
    assert KIND_FIXED in [e["kind"] for e in ev]


def test_same_side_drift_neighbour_merges_when_configured():
    tr = UnfinishedTracker(tick_size=0.1, merge_ticks=1.0)
    tr.on_bar(1000, {100.0: (1.0, 0.0), 101.0: (2.0, 0.5)})
    ev = tr.on_bar(2000, {100.0: (1.0, 0.0), 100.92: (3.0, 0.5)})
    assert ev == []
    assert tr.snapshot()["open"][0]["price"] == 101.0
