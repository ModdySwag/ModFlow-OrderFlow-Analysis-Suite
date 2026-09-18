"""HTF POC aggregation, the confluence scorer, and the shape-story pin.

Pinned claims:

1. ``period_pocs`` sums stored ``volume_at_price`` maps per ISO week / month and recomputes the
   POC and value area on the aggregate (the engine's own expansion rule); unusable sessions are
   excluded and the used set is named in ``sessions``.
2. ``find_confluences`` clusters level refs within a tolerance and ranks by distinct sources.
3. Every shape ``_classify_shape`` can return has words in ``SHAPE_STORIES`` — source-scanned,
   so the badge can never fall behind the maths.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from types import SimpleNamespace

from orderflow_system.analytics.volume_profile import SHAPE_STORIES, shape_story
from orderflow_system.atlas.confluence import LevelRef, find_confluences
from orderflow_system.atlas.profiles import period_pocs


def _p(session_date: str, vap: dict) -> SimpleNamespace:
    return SimpleNamespace(session_date=session_date, poc=0.0, vah=0.0, val=0.0,
                           total_volume=0.0, volume_at_price=vap)


def test_weekly_poc_is_the_aggregate_mode():
    profiles = [
        _p("2026-09-07", {100.0: 5.0, 101.0: 1.0}),
        _p("2026-09-08", {100.0: 2.0, 101.0: 4.0}),
        _p("2026-09-14", {100.0: 1.0, 101.0: 9.0}),
        _p("not-a-date", {100.0: 1.0}),
        _p("2026-09-09", {}),                       # no levels -> excluded, not invented
    ]
    out = period_pocs(profiles, period="week")
    wk = dt.date(2026, 9, 7).isocalendar()
    assert out[0]["period"] == f"{wk[0]}-W{wk[1]:02d}"
    assert out[0]["poc"] == 100.0                   # 7 at 100 vs 5 at 101 across the week
    assert out[0]["total_volume"] == 12.0
    assert out[0]["sessions"] == ["2026-09-07", "2026-09-08"]
    assert out[1]["poc"] == 101.0 and out[1]["sessions"] == ["2026-09-14"]


def test_weekly_value_area_expands_from_the_aggregate_poc():
    profiles = [
        _p("2026-09-07", {100.0: 5.0, 101.0: 1.0}),
        _p("2026-09-08", {100.0: 2.0, 101.0: 4.0}),
    ]
    out = period_pocs(profiles, period="week")
    assert out[0]["poc"] == 100.0
    assert out[0]["val"] == 100.0 and out[0]["vah"] == 101.0   # 7/12 < 68% -> include the 101 side


def test_month_grouping():
    out = period_pocs([_p("2026-09-07", {100.0: 1.0}), _p("2026-09-28", {100.0: 1.0}),
                       _p("2026-10-01", {100.0: 1.0})], period="month")
    assert [p["period"] for p in out] == ["2026-09", "2026-10"]


def test_confluence_clusters_and_ranks():
    refs = [
        LevelRef(100.00, "poc"),
        LevelRef(100.04, "vwap_band"),
        LevelRef(100.02, "unfinished"),
        LevelRef(101.50, "wall"),
        LevelRef(101.52, "node"),
    ]
    groups = find_confluences(refs, tol=0.05)
    assert len(groups) == 2
    assert groups[0]["count"] == 3 and groups[0]["distinct_sources"] == 3
    assert abs(groups[0]["price"] - 100.02) < 1e-9
    assert "unfinished" in groups[0]["sources"] and "wall" in groups[1]["sources"]


def test_min_distinct_demands_independent_sources():
    same = [LevelRef(1.00, "poc"), LevelRef(1.01, "poc")]
    assert find_confluences(same, tol=0.05, min_distinct=2) == []
    assert len(find_confluences(same, tol=0.05, min_distinct=1)) == 1


def test_empty_or_zero_tolerance():
    assert find_confluences([], tol=0.1) == []
    assert find_confluences([LevelRef(1.0, "poc")], tol=0.0) == []


def test_every_classified_shape_has_a_story():
    src = (Path(__file__).resolve().parent / "analytics" / "volume_profile.py").read_text(encoding="utf-8")
    fn = src[src.index("def _classify_shape"):src.index("# ── Shape stories")]
    found = set(re.findall(r'return\s+"([a-z_]+)"', fn))
    assert found == {"unknown", "double_dist", "p_shape", "b_shape", "d_shape"}, found
    assert found <= set(SHAPE_STORIES)
    assert shape_story("P_SHAPE")["label"] == "P-shape"
    assert shape_story("what?")["label"] == SHAPE_STORIES["unknown"]["label"]
