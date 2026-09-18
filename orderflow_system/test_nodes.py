"""Node persistence — consecutive bars sharing one HVN price, pinned.

A run is *consecutive* bars whose POC sits within tol_ticks of the run's anchor price; a bar
without a POC (or one whose POC moved away) ends it. The tracker fires only at threshold
crossings (2 = double, 3 = triple) and never re-fires while the run keeps growing.
"""

from __future__ import annotations

from orderflow_system.atlas.nodes import KIND_NODE, NodeTracker, node_runs


def test_runs_require_consecutive_bars():
    bars = [(0, 100.0), (60_000, 100.0), (120_000, 100.0), (180_000, 101.0), (240_000, 100.0)]
    runs = node_runs(bars, tick_size=0.1)
    assert len(runs) == 1
    r = runs[0]
    assert r.count == 3 and r.start_ts_ms == 0 and r.last_ts_ms == 120_000


def test_tolerance_absorbs_drift_within_half_tick():
    bars = [(0, 100.00), (1, 100.04), (2, 100.05)]
    runs = node_runs(bars, tick_size=0.1)          # 0.05 tolerance
    assert len(runs) == 1 and runs[0].count == 3


def test_a_missing_poc_breaks_the_run():
    assert node_runs([(0, 100.0), (1, None), (2, 100.0)]) == []


def test_payload_bars_carry_poc_row_volume():
    bars = [
        {"time": 0.0, "poc": 100.0, "levels": [{"price": 100.0, "bid": 2.0, "ask": 3.0}]},
        {"time": 60.0, "poc": 100.0, "levels": [{"price": 100.0, "bid": 1.0, "ask": 2.0}]},
    ]
    runs = node_runs(bars)
    assert len(runs) == 1 and runs[0].count == 2
    assert abs(runs[0].volume - 8.0) < 1e-9


def test_tracker_fires_at_crossings_only():
    tr = NodeTracker(tick_size=0.1)
    assert tr.on_bar(0, 100.0) == []
    ev = tr.on_bar(1, 100.0)
    assert [e["kind"] for e in ev] == [KIND_NODE] and ev[0]["count"] == 2
    ev = tr.on_bar(2, 100.0)
    assert [e["count"] for e in ev] == [3]
    assert tr.on_bar(3, 100.0) == []               # a growing run never re-fires
    assert tr.snapshot()["current"]["count"] == 4


def test_break_completes_the_run():
    tr = NodeTracker(tick_size=0.1)
    tr.on_bar(0, 100.0)
    tr.on_bar(1, 100.0)
    tr.on_bar(2, 101.0)
    snap = tr.snapshot()
    assert snap["completed"][-1]["count"] == 2 and snap["completed"][-1]["completed"] is True
    assert snap["current"]["count"] == 1
