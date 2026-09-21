"""W6's gate: the data-quality cockpit — the scorecard arithmetic, the refusal, and the panel.

Everything decision-shaped in `atlas/dataquality.py` is pure, so this file pins it offline on small
fixtures: coverage over a window, gap detection (threshold, merging, ranges, biggest first),
duplicates, out-of-order stamps, the verdict ladder at its boundaries, the capped-read rule, and the
refusal sentence a symbol with nothing stored gets. The route half is exercised twice: with no store
at all (the polite no) and against a real temporary SQLite file through the app's own stored-history
accessors, so the glue between `Database.get_recent_ticks` and the scorecard is pinned too.

The panel's own behaviour is `node --check` + `data-quality.selftest.js` (55 checks, the same pattern
`test_freshness.py` uses), plus the two mirror pins: the routes and the verdict letters the JS wires
must be the ones this module declares.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
PANEL = UI / "data-quality.js"
SELFTEST = UI / "data-quality.selftest.js"

from orderflow_system.atlas import dataquality as dq  # noqa: E402

#: A fixed instant so every fixture below is arithmetic, not "whatever time it is now".
DAY_MS = 86_400_000
START = int(datetime(2026, 9, 20, 3, 0, tzinfo=timezone.utc).timestamp() * 1000)


def hourly(start_ms: int, count: int, cadence_ms: int = 1000) -> list[int]:
    """`count` samples one cadence apart, starting at `start_ms` — the plainest history there is."""
    return [start_ms + index * cadence_ms for index in range(count)]


def two_hours_with_a_hole(start_ms: int = START, slots: int = 7200, hole_at: int = 252,
                          hole_slots: int = 251, duplicate_at: int = 1000) -> list[int]:
    """A second-by-second two-hour history with one hole and a tripled stamp, in stored order.

    The hole is 251 empty seconds between two stored stamps, so the wall-clock hole between them is
    252 s = 4 m 12 s, and the duplicated stamp sits inside the sequence where a re-read would put it
    (a duplicate append at the end is also an out-of-order stamp, which is a different finding).
    """
    out: list[int] = []
    for index in range(slots):
        if hole_at <= index < hole_at + hole_slots:
            continue
        stamp = start_ms + index * 1000
        out.append(stamp)
        if index == duplicate_at:
            out.extend([stamp, stamp, stamp])
    return out


# ══════════════════════════════════════════════════════════════
# Settings: the block, the ladder, the tables
# ══════════════════════════════════════════════════════════════

def test_defaults_are_the_documented_ones():
    assert dq.DEFAULTS["window_h"] == 24.0
    assert dq.DEFAULTS["rows_window_h"] == 6.0
    assert dq.DEFAULTS["gap_mult"] == 3 and dq.DEFAULTS["merge_present"] == 2
    assert dq.DEFAULTS["cadence_s"]["crypto"] == 1 and dq.DEFAULTS["cadence_s"]["stocks"] == 5
    assert dq.DEFAULTS["candle_cadence_s"] == 60
    assert dq.DEFAULTS["min_coverage_pct"] == 99.0 and dq.DEFAULTS["floor_coverage_pct"] == 50.0
    assert dq.DEFAULTS["symbols"] == []
    assert set(dq.CLASSES) == {"crypto", "forex", "indices", "metals", "energy", "stocks", "other"}


def test_clean_coerces_junk_onto_the_defaults():
    block = dq.clean({"window_h": "x", "gap_mult": "nope", "kind": "bananas", "enabled": 0,
                      "max_samples": -5, "keep_gaps": 10_000, "unknown_key": 7})
    assert block["window_h"] == dq.DEFAULTS["window_h"]
    assert block["gap_mult"] == dq.DEFAULTS["gap_mult"]
    assert block["kind"] == "ticks"                      # an unknown series is not a series
    assert block["enabled"] is False
    assert block["max_samples"] == 100                   # clamped to the floor, not defaulted away
    assert block["keep_gaps"] == 500
    assert "unknown_key" not in block                    # unknown keys are dropped, not carried
    assert set(block) == set(dq.DEFAULTS)
    for junk in (None, 5, "text", [], {"cadence_s": "no"}, {"sessions": 3}):
        assert set(dq.clean(junk)) == set(dq.DEFAULTS)


def test_clean_rebuilds_the_cadence_and_session_tables_per_class():
    block = dq.clean({"cadence_s": {"crypto": "2", "stocks": 0}, "sessions": {"stocks": {"open_h_per_day": 99}}})
    assert block["cadence_s"] == {"crypto": 2, "forex": 1, "indices": 1, "metals": 1, "energy": 1,
                                  "stocks": 1, "other": 5}
    assert block["sessions"]["stocks"] == {"open_utc_h": 13.5, "open_h_per_day": 24.0,
                                           "weekend_open": False}
    assert block["sessions"]["crypto"] == {"open_utc_h": 0.0, "open_h_per_day": 24.0,
                                           "weekend_open": True}


def test_clean_keeps_the_coverage_ladder_in_order():
    """A hand-edited config cannot invert the bars: min >= warn >= low >= floor, always."""
    block = dq.clean({"min_coverage_pct": 10, "warn_coverage_pct": 99, "low_coverage_pct": 95,
                      "floor_coverage_pct": 95})
    assert block["min_coverage_pct"] == 10.0
    assert block["warn_coverage_pct"] == 10.0
    assert block["low_coverage_pct"] == 10.0
    assert block["floor_coverage_pct"] == 10.0
    block2 = dq.clean({"gap_a_s": 900, "gap_b_s": 60, "stale_a_s": 4000, "stale_b_s": 10})
    assert block2["gap_b_s"] == 900 and block2["stale_b_s"] == 4000


def test_clean_normalises_symbols_and_is_idempotent():
    block = dq.clean({"symbols": [" btcusdt ", "BTCUSDT", 5, "", None, "ethusdt"], "max_symbols": 1})
    assert block["symbols"] == ["BTCUSDT"]
    again = dq.clean(block)
    assert again == block, "clean() must be idempotent — the route re-cleans what it stored"


# ══════════════════════════════════════════════════════════════
# The expectation: cadence, the venue's hours, the class
# ══════════════════════════════════════════════════════════════

def test_cadence_per_asset_class_and_series():
    assert dq.cadence_ms_for("crypto") == 1000
    assert dq.cadence_ms_for("stocks") == 5000
    assert dq.cadence_ms_for("Crypto") == 1000                 # case is not a class of its own
    assert dq.cadence_ms_for("unknown-venue") == 5000          # "other" → the default row
    assert dq.cadence_ms_for("crypto", "candles") == 60_000    # a candle series is judged per bar
    assert dq.cadence_ms_for("stocks", "candles") == 60_000
    assert dq.cadence_ms_for("crypto", "candles", {"candle_cadence_s": 300}) == 300_000
    assert dq.cadence_ms_for("crypto", "ticks", {"candle_cadence_s": 300}) == 1000


def test_the_capped_hint_points_at_the_setting_that_can_help():
    """§148 T5-F-11: the routes accept `hours`/`kind`/`symbols`, but the panel sends none of them —
    so the old advice ("narrow the window") named an action no control could take, and the hint
    offered a prune route beside it. The hint now names the setting the user can actually change,
    and that setting really exists in the registry the Settings view renders."""
    from orderflow_system.desktop import param_registry

    row = {"symbol": "BTCUSDT", "coverage_pct": 99.0, "capped": True, "verdict": "B",
           "configured_window_s": 21_600, "window_s": 21_600, "stale_ms": 0, "gaps": [],
           "duplicates": {}, "out_of_order": {}, "future_n": 0}
    hints = dq.repairs_for(row, None, sample_cap=20_000)
    trim = [hint for hint in hints if hint.get("action") == "trim"]
    assert len(trim) == 1, hints
    label = str(trim[0].get("label") or "")
    assert "Settings" in label and "Data-quality window" in label
    assert {param.path for param in param_registry.PARAMS} >= {"data_quality.window_h"}


def test_the_capped_hint_says_why_a_prune_cannot_uncap_it():
    """§148 T5-F-12: the old label offered "let retention prune older rows" and pointed the hint at
    `POST /api/control/storage/prune` — but a prune trims the OLD end while a capped read counts
    from the newest one, so the offered repair could not change what the row says."""
    row = {"symbol": "ETHUSDT", "coverage_pct": 99.0, "capped": True, "verdict": "B",
           "configured_window_s": 86_400, "window_s": 86_400, "stale_ms": 0, "gaps": [],
           "duplicates": {}, "out_of_order": {}, "future_n": 0}
    trim = [hint for hint in dq.repairs_for(row, None, sample_cap=20_000)
            if hint.get("action") == "trim"][0]
    why = str(trim.get("why") or "")
    assert trim.get("available") is False and trim.get("route") == ""
    assert "prune" in why and "old end" in why and "newest" in why
    assert "ROUTE_PRUNE" not in dir(dq), "the constant went with its only user"


def test_the_header_names_the_reads_it_actually_makes():
    """§148 T5-F-13: the module header listed `Database.count_ticks` among this route's reads — it
    never calls it; that read belongs to `GET /api/control/trades` — and called the hint set "the
    four repairs" while `repairs_for` can emit six actions, only two of them routable."""
    import inspect

    source = inspect.getsource(dq)
    header = " ".join((dq.__doc__ or "").split())
    assert ".count_ticks(" not in source
    assert ".get_recent_ticks(" in source and ".get_candles(" in source
    assert "count_ticks" in header and "not to this read" in header
    row = {"symbol": "SOLUSDT", "coverage_pct": 10.0, "capped": True, "verdict": "F",
           "configured_window_s": 3_600, "window_s": 3_600, "stale_ms": 99_999_999,
           "gaps": [{"gap_ms": 600_000, "from_utc": "2026-09-20 03:04"}], "n_gaps_total": 3,
           "duplicates": {"extra": 2}, "out_of_order": {"n": 2}, "future_n": 1}
    hints = dq.repairs_for(row, None, sample_cap=1_000)
    emitted = {hint["action"] for hint in hints}
    assert emitted == {"refetch", "backfill", "dedupe", "order", "clock", "trim"}, emitted
    for action in sorted(emitted):
        assert action in header, f"the header must name every action it can emit ({action})"
    assert "The four repairs" not in header
    routable = {hint["action"] for hint in hints if hint.get("route")}
    assert routable == {"refetch", "backfill"}, routable


def test_the_weekend_rule_lives_at_its_only_live_reader():
    """§148 T5-F-15: `weekend_days` was dead in production — no module called it, only this file's
    old test did — while `session_open_ms` inlined the same weekday rule. The counter is gone, the
    rule is documented where it is read, and a weekend stock window still expects nothing."""
    import inspect

    assert not hasattr(dq, "weekend_days"), "the dead counter is gone"
    body = " ".join(inspect.getsource(dq.session_open_ms).split())
    assert "(day + 3) % 7" in body and "Epoch day 0" in body and "Saturday" in body
    saturday = int(datetime(2026, 9, 19, 12, tzinfo=timezone.utc).timestamp() * 1000)
    assert dq.session_open_ms(saturday - 3_600_000, saturday, "stocks") == 0
    assert dq.session_factor(saturday - 3_600_000, saturday, "stocks") == pytest.approx(0.02)


def test_the_session_factor_scales_to_the_venue_hours():
    stamp = int(datetime(2026, 9, 16, 12, tzinfo=timezone.utc).timestamp() * 1000)   # a Wednesday
    assert dq.session_factor(stamp, stamp + DAY_MS, "crypto") == 1.0
    assert dq.session_factor(stamp, stamp + DAY_MS, "other") == 1.0
    assert dq.session_factor(stamp, stamp + DAY_MS, "stocks") == pytest.approx(6.5 / 24, abs=1e-6)
    assert dq.session_factor(stamp, stamp + DAY_MS, "nonsense") == 1.0
    weekend = int(datetime(2026, 9, 19, 12, tzinfo=timezone.utc).timestamp() * 1000)  # a Saturday
    assert dq.session_factor(weekend, weekend + DAY_MS, "stocks") == pytest.approx(0.02)  # the floor
    assert dq.session_note("crypto") == ""
    assert "6.5 h" in dq.session_note("stocks") and "weekends are closed" in dq.session_note("stocks")


def test_the_session_is_placed_at_the_right_hour_of_the_day_not_smeared_over_it():
    """A stock window that sits inside the session is FULL coverage; a smeared day-share said 27%."""
    inside = int(datetime(2026, 9, 17, 15, tzinfo=timezone.utc).timestamp() * 1000)   # 15:00 Thu
    assert dq.session_open_ms(inside - 3_600_000, inside, "stocks") == 3_600_000
    assert dq.session_factor(inside - 3_600_000, inside, "stocks") == 1.0
    card = dq.scorecard("AAPL", [inside - 3_600_000 + 5_000 * step for step in range(721)],
                        asset_class="stocks", now_ms=inside, window_h=1.0)
    assert card["expected_slots"] == 720 and card["coverage_pct"] == 100.0
    assert card["verdict"] == "A", "a complete session hour is an A, not a data fault"
    straddle = int(datetime(2026, 9, 17, 14, tzinfo=timezone.utc).timestamp() * 1000)  # 14:00 Thu
    assert dq.session_open_ms(straddle - 3_600_000, straddle, "stocks") == 1_800_000
    assert dq.session_factor(straddle - 3_600_000, straddle, "stocks") == pytest.approx(0.5), \
        "13:00-14:00 straddles the 13:30 open: half the window, half the expectation"
    assert dq.session_open_ms(inside, inside, "stocks") == 0
    assert dq.session_open_ms(inside, inside - 1, "stocks") == 0


def test_asset_class_inference_prefers_the_config_table_then_a_name_shape():
    table = {"NAS100USDT": "Indices", "BTCUSDT": "Crypto"}
    assert dq.infer_asset_class("nAS100usdt", table) == "indices"
    assert dq.infer_asset_class("BTC/USD") == "crypto"
    assert dq.infer_asset_class("ETHUSDT") == "crypto"
    assert dq.infer_asset_class("EURUSD") == "forex"
    assert dq.infer_asset_class("ES") == "other", "a two-letter root is not guessed at"
    assert dq.infer_asset_class("") == "other"


# ══════════════════════════════════════════════════════════════
# Coverage arithmetic (small fixtures, exact numbers)
# ══════════════════════════════════════════════════════════════

def test_a_complete_hour_of_second_samples_is_a_hundred_percent():
    now = START + 3_600_000
    card = dq.scorecard("BTCUSDT", hourly(START, 3601), asset_class="crypto", now_ms=now, window_h=1.0)
    assert card["ok"] is True
    assert card["expected_slots"] == 3600 and card["present_slots"] == 3601
    assert card["coverage_pct"] == 100.0
    assert card["n_gaps"] == 0 and card["verdict"] == "A"
    assert card["window_s"] == 3600 and card["configured_window_s"] == 3600
    assert card["cadence_ms"] == 1000 and card["samples"] == 3601


def test_history_that_starts_late_reads_as_partial_coverage():
    """The window is the question; a store that holds a third of it covers a third of it."""
    now = START + 3_600_000
    late = hourly(now - 1_200_000, 1_201)                 # the newest 20 minutes only
    card = dq.scorecard("BTCUSDT", late, asset_class="crypto", now_ms=now, window_h=1.0)
    assert card["coverage_pct"] == pytest.approx(33.4, abs=0.1)
    assert card["history_share_pct"] == pytest.approx(33.4, abs=0.1)
    assert any("of history inside the" in note for note in card["notes"])
    assert card["verdict"] in ("D", "F")
    assert any(hint["action"] == "refetch" for hint in card["repairs"])


def test_the_newest_sample_carries_the_staleness_read():
    now = START + 3_600_000
    card = dq.scorecard("BTCUSDT", hourly(START, 3_001), asset_class="crypto", now_ms=now, window_h=1.0)
    assert card["stale_ms"] == pytest.approx(600_000, abs=1000)      # ten minutes of silence
    assert card["fresh"] is False                                    # the live chip's 5 s window
    assert card["fresh_window_ms"] == 5_000
    assert "nothing has arrived for" in card["sentence"]
    candles = dq.scorecard("BTCUSDT", hourly(START, 3_001), asset_class="crypto", kind="candles",
                           now_ms=now, window_h=1.0)
    assert candles["fresh_window_ms"] == 60_000 and candles["cadence_ms"] == 60_000


def test_tick_bursts_count_one_slot_not_one_sample_each():
    """A burst of prints inside one second is ONE second of coverage — the slot is the unit."""
    now = START + 10_000
    burst = [START + 0, START + 100, START + 200, START + 300, START + 400, START + 9000]
    card = dq.scorecard("BTCUSDT", burst, asset_class="crypto", now_ms=now, window_h=0.005)
    assert card["samples"] == 6 and card["distinct_samples"] == 6
    assert card["expected_slots"] == 18                    # an 18 s window at one slot a second
    assert card["present_slots"] == 2                      # second 0 and second 9 of it
    assert card["coverage_pct"] == pytest.approx(11.1, abs=0.1)
    assert card["cadence_ms"] == 1000


def test_the_coverage_window_is_the_one_that_was_asked_for():
    now = START + 3_600_000
    two_hours = hourly(now - 7_200_000, 7_201)
    hour = dq.scorecard("BTCUSDT", two_hours, asset_class="crypto", now_ms=now, window_h=1.0)
    assert hour["window_s"] == 3600 and hour["coverage_pct"] == 100.0
    both = dq.scorecard("BTCUSDT", two_hours, asset_class="crypto", now_ms=now, window_h=2.0)
    assert both["window_s"] == 7200 and both["coverage_pct"] == 100.0


# ══════════════════════════════════════════════════════════════
# Gaps: the threshold, the merging, the ranges
# ══════════════════════════════════════════════════════════════

def test_gaps_are_reported_for_holes_wider_than_the_threshold_only():
    """The threshold is in cadence steps: a hole narrower than it is counted, never listed."""
    narrow = [0, 1000, 2000, 3000, 5000, 6000]             # 3000 → 5000: one empty slot
    gaps, holes, total = dq.detect_gaps(narrow, 1000, min_slots=3, merge_present=2)
    assert gaps == [] and total == 0 and holes == 1         # counted, not listed
    wide = [0, 1000, 2000, 3000, 6000, 7000]                # 3000 → 6000: two empty slots, 3 s wide
    gaps, holes, total = dq.detect_gaps(wide, 1000, min_slots=3, merge_present=2)
    assert holes == 0 and total == 1
    assert gaps[0] == {"from_ms": 3000, "to_ms": 6000, "gap_ms": 3000, "missing_slots": 2,
                       "missing_ms": 2000, "samples_inside": 0, "from_utc": "1970-01-01 00:00"}


def test_a_lone_print_inside_a_hole_does_not_split_it():
    stamps = [0, 1000, 2000, 9000, 10_000, 20_000]
    merged, _, total = dq.detect_gaps(stamps, 1000, min_slots=3, merge_present=2)
    assert total == 1
    assert merged[0]["from_ms"] == 2000 and merged[0]["to_ms"] == 20_000
    assert merged[0]["gap_ms"] == 18_000
    assert merged[0]["samples_inside"] == 2                 # 9000 and 10 000 sit inside the hole
    assert merged[0]["missing_slots"] == 15
    split, _, total = dq.detect_gaps(stamps, 1000, min_slots=3, merge_present=1)
    assert total == 2 and [g["gap_ms"] for g in split] == [10_000, 7000]


def test_gaps_come_back_biggest_first_and_the_list_is_capped():
    base = 60_000                                            # stamp 0 itself is not a usable stamp
    stamps = [base + step for step in (0, 5000, 20_000, 25_000, 100_000)]
    gaps, holes, total = dq.detect_gaps(stamps, 1000, min_slots=3, merge_present=1, keep=10)
    assert holes == 0 and total == 4, "merge_present = 1 lists every hole on its own"
    assert [gap["gap_ms"] for gap in gaps] == [75_000, 15_000, 5000, 5000]     # biggest first
    capped, _, total = dq.detect_gaps(stamps, 1000, min_slots=3, merge_present=1, keep=1)
    assert total == 4 and len(capped) == 1 and capped[0]["gap_ms"] == 75_000
    merged, _, total = dq.detect_gaps(stamps, 1000, min_slots=3, merge_present=2, keep=10)
    assert total == 1 and merged[0]["gap_ms"] == 100_000, "sparse samples never come back in a row"
    assert merged[0]["samples_inside"] == 3 and merged[0]["missing_slots"] == 96


def test_gap_detection_survives_junk_and_tiny_inputs():
    assert dq.detect_gaps([], 1000) == ([], 0, 0)
    assert dq.detect_gaps([5000], 1000) == ([], 0, 0)
    assert dq.detect_gaps([0, 1000], 0) == ([], 0, 0), "a zero cadence is read as the default 1 s"
    assert dq.detect_gaps([9000, 0, 1000, 9000, None], 1000, min_slots=3)[2] == 1
    assert dq.detect_gaps("junk", 1000) == ([], 0, 0)


# ══════════════════════════════════════════════════════════════
# Duplicates, ordering, the future
# ══════════════════════════════════════════════════════════════

def test_duplicates_are_counted_as_rows_beyond_the_first():
    assert dq.count_duplicates([1000, 1000, 1000, 2000]) == {"n": 1, "extra": 2, "first_ms": 1000}
    assert dq.count_duplicates([1, 2, 3]) == {"n": 0, "extra": 0, "first_ms": 0}
    assert dq.count_duplicates([]) == {"n": 0, "extra": 0, "first_ms": 0}


def test_out_of_order_stamps_are_measured_in_the_order_they_arrived():
    assert dq.count_disorder([1000, 2000, 3000]) == {"n": 0, "first_ms": 0}
    assert dq.count_disorder([3000, 2000, 1000]) == {"n": 2, "first_ms": 2000}
    now = START + 3_600_000
    stamps = hourly(START, 600)
    card = dq.scorecard("BTCUSDT", list(reversed(stamps)), asset_class="crypto", now_ms=now, window_h=1.0)
    assert card["out_of_order"]["n"] == 599
    assert any(hint["action"] == "order" and hint["available"] is False for hint in card["repairs"])
    assert card["verdict"] != "A", "an out-of-order store is not a clean one"


def test_stamps_dated_in_the_future_are_reported_and_left_out_of_the_maths():
    now = START + 3_600_000
    stamps = hourly(START, 600) + [now + 600_000, now + 700_000]
    card = dq.scorecard("BTCUSDT", stamps, asset_class="crypto", now_ms=now, window_h=1.0)
    assert card["future_n"] == 2
    assert card["samples"] == 600 and card["last_ms"] <= now
    assert any(hint["action"] == "clock" for hint in card["repairs"])


# ══════════════════════════════════════════════════════════════
# The verdict ladder
# ══════════════════════════════════════════════════════════════

def test_the_verdict_ladder_at_its_boundaries():
    clean = {"coverage_pct": 99.0, "biggest_gap_ms": 60_000, "stale_ms": 300_000,
             "duplicates_extra": 0, "out_of_order": 0}
    assert dq.verdict_for(**clean) == "A"
    assert dq.verdict_for(**{**clean, "coverage_pct": 98.9}) == "B"
    assert dq.verdict_for(**{**clean, "biggest_gap_ms": 60_001}) == "B"
    assert dq.verdict_for(**{**clean, "stale_ms": 300_001}) == "B"
    assert dq.verdict_for(**{**clean, "duplicates_extra": 1}) == "B"
    assert dq.verdict_for(**{**clean, "out_of_order": 1}) == "B"
    assert dq.verdict_for(**{**clean, "coverage_pct": 95.0}) == "B"
    assert dq.verdict_for(**{**clean, "coverage_pct": 94.9}) == "C"
    assert dq.verdict_for(**{**clean, "coverage_pct": 94.9, "stale_ms": 1_800_001}) == "D"
    assert dq.verdict_for(**{**clean, "coverage_pct": 80.0}) == "C"
    assert dq.verdict_for(**{**clean, "coverage_pct": 79.9}) == "D"
    assert dq.verdict_for(**{**clean, "coverage_pct": 50.0}) == "D"
    assert dq.verdict_for(**{**clean, "coverage_pct": 49.9}) == "F"
    assert dq.verdict_for(**{**clean, "coverage_pct": 0.0, "stale_ms": 10 * DAY_MS}) == "F"
    assert dq.verdict_for(**{**clean, "coverage_pct": 99.9,
                             "biggest_gap_ms": 60_000}, settings={"gap_a_s": 30}) == "B"


def test_the_letter_carries_a_plain_note():
    for note in dq.VERDICT_NOTES.values():
        assert note and not note.endswith(".")
        assert "coming soon" not in note.lower()
    assert set(dq.VERDICT_NOTES) == {"A", "B", "C", "D", "F"}


def test_a_capped_read_cannot_earn_a_clean_letter():
    now = START + DAY_MS
    stamps = hourly(now - 120_000, 121)                    # the newest two minutes, as a cap would take
    card = dq.scorecard("BTCUSDT", stamps, asset_class="crypto", now_ms=now, window_h=24.0, capped=True)
    assert card["capped"] is True
    assert card["window_s"] == 120, "a capped read judges the window it took"
    assert card["configured_window_s"] == 86_400
    assert card["verdict"] == "B"
    assert any("capped" in note for note in card["notes"])
    assert any(hint["action"] == "trim" for hint in card["repairs"])
    assert str(dq.DEFAULTS["max_samples"]) in card["sentence"] or "capped" in card["sentence"]


# ══════════════════════════════════════════════════════════════
# The sentence, the hints, the refusal
# ══════════════════════════════════════════════════════════════

def test_the_one_plain_sentence():
    """The shape the brief asked for: coverage first, then the biggest gap, then the stamp problems."""
    now = START + 7_200_000
    stamps = two_hours_with_a_hole()
    card = dq.scorecard("BTC-USD", stamps, asset_class="crypto", now_ms=now, window_h=2.0)
    assert card["coverage_pct"] == 96.5
    assert card["biggest_gap"]["gap_ms"] == 252_000
    assert card["duplicates"] == {"n": 1, "extra": 3, "first_ms": START + 1_000_000}
    assert card["out_of_order"]["n"] == 0
    assert card["sentence"] == (
        "history for BTC-USD is 96.5% complete over the last 2 h; the largest gap is 4 m 12 s at "
        "03:04 and there were 3 duplicate stamps")


def test_a_clean_window_says_so_without_a_tail():
    now = START + 3_600_000
    card = dq.scorecard("BTCUSDT", hourly(START, 3601), asset_class="crypto", now_ms=now, window_h=1.0)
    assert card["sentence"] == "history for BTCUSDT is 100% complete over the last 1 h"
    assert card["repairs"] == []
    assert card["verdict_note"] == dq.VERDICT_NOTES["A"]


def test_repair_hints_name_the_apps_real_paths_and_admit_the_ones_it_lacks():
    now = START + 7_200_000
    card = dq.scorecard("BTC-USD", two_hours_with_a_hole(), asset_class="crypto", now_ms=now,
                        window_h=2.0)
    hints = {hint["action"]: hint for hint in card["repairs"]}
    assert set(hints) == {"refetch", "backfill", "dedupe"}
    assert hints["backfill"]["route"] == "/api/control/backfill" and hints["backfill"]["available"]
    assert hints["backfill"]["label"].startswith("backfill the 4 m 12 s hole from 2026-09-20 03:04")
    assert hints["refetch"]["route"] == "/api/control/backfill"
    assert hints["dedupe"]["available"] is False and hints["dedupe"]["route"] == ""
    assert "duplicate" in hints["dedupe"]["label"]
    from orderflow_system.desktop.api import router as control_router
    paths = {getattr(route, "path", "") for route in control_router.routes}
    for hint in card["repairs"]:
        if hint["available"]:
            assert hint["route"] in paths, f"{hint['action']} points at a route that is not there"


def test_a_symbol_with_nothing_stored_gets_the_refusal_sentence():
    card = dq.scorecard("btc-usd", [], now_ms=START, window_h=1.0)
    assert card["ok"] is False
    assert card["detail"] == "no stored history for BTC-USD yet — open a chart and let it load"
    assert card["error"] == card["detail"] and card["sentence"] == card["detail"]
    assert card["coverage_pct"] == 0.0 and card["gaps"] == [] and card["repairs"] == []
    assert dq.refusal("ethusdt")["detail"].startswith("no stored history for ETHUSDT yet")
    # a window that holds no stamps at all (everything older than the window) refuses the same way
    old = dq.scorecard("BTCUSDT", hourly(START, 10), now_ms=START + 10 * DAY_MS, window_h=1.0)
    assert old["ok"] is False and "no stored history" in old["detail"]


def test_a_count_without_spacings_reads_coarsely_and_says_so():
    """A capped read falls back to a count — and the session expectation still judges it."""
    session = int(datetime(2026, 9, 17, 14, 0, tzinfo=timezone.utc).timestamp() * 1000)
    card = dq.scorecard("AAPL", None, count=100, first_ms=session - 3_600_000, last_ms=session,
                        asset_class="stocks", now_ms=session, window_h=1.0)
    assert card["ok"] is True and card["coarse"] is True
    assert card["samples"] == 100 and card["gaps"] == [] and card["n_gaps_total"] == 0
    assert any("count only" in note for note in card["notes"])
    assert card["coverage_pct"] == 27.8, "100 bars against a half hour of session, one bar a minute"
    assert card["repairs"] and card["repairs"][0]["action"] == "refetch"


def test_the_scorecard_never_raises_on_junk():
    junk = [None, "x", {}, {"ts_ms": "nope"}, float("nan"), True, [], object()]
    for samples in (junk, "not a list", 5, None):
        card = dq.scorecard("BTCUSDT", samples, now_ms=START, window_h=1.0)
        assert isinstance(card, dict) and "ok" in card
    for value in (None, "x", {}, -1, float("inf")):
        assert isinstance(dq.scorecard("BTCUSDT", [START], now_ms=value, window_h=1.0), dict)
    assert dq.to_timestamp({"ts": 5000}) == 5000
    assert dq.to_timestamp(type("Tick", (), {"timestamp_ms": 7000})()) == 7000
    assert dq.to_timestamp(True) == 0 and dq.to_timestamp(None) == 0


def test_row_of_keeps_what_a_cockpit_row_needs():
    now = START + 3_600_000
    card = dq.scorecard("BTCUSDT", hourly(START, 3601), asset_class="crypto", now_ms=now, window_h=1.0)
    row = dq.row_of(card, keep_gaps=0)
    assert row["ok"] is True and row["symbol"] == "BTCUSDT" and row["verdict"] == "A"
    assert row["sentence"] == card["sentence"] and row["gaps"] == []
    refused = dq.row_of(dq.refusal("ETHUSDT"))
    assert refused["ok"] is False and refused["detail"].startswith("no stored history for ETHUSDT")


# ══════════════════════════════════════════════════════════════
# The route
# ══════════════════════════════════════════════════════════════

def _client():
    """A tiny app carrying just this router — the route half, exercised over HTTP."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(dq.router)
    return TestClient(app)


def test_the_router_declares_both_paths():
    paths = {getattr(route, "path", "") for route in dq.router.routes}
    assert paths == {"/api/atlas/data-quality", "/api/atlas/data-quality/{symbol}"}
    assert getattr(dq.router, "prefix", "") == "/api/atlas"


def test_the_routes_refuse_politely_with_no_store_at_all(monkeypatch):
    from orderflow_system.desktop import config_store

    async def no_db():
        return None, False

    async def no_instruments():
        return [], {}

    monkeypatch.setattr(dq, "_open_db", no_db)
    monkeypatch.setattr(dq, "_configured_instruments", no_instruments)
    monkeypatch.setattr(config_store, "load_config", lambda: {"instruments": []})
    client = _client()

    card = client.get("/api/atlas/data-quality/BTCUSDT").json()
    assert card["ok"] is False and card["detail"].startswith("no stored history for BTCUSDT yet")
    assert card["detail"].endswith("open a chart and let it load")
    rows = client.get("/api/atlas/data-quality").json()
    assert rows["ok"] is False and "no instruments to check yet" in rows["detail"]
    assert rows["rows"] == [] and rows["count"] == 0
    trailing = client.get("/api/atlas/data-quality/", follow_redirects=False)
    assert trailing.status_code in (307, 308), "a trailing slash is a redirect, not a 500"


def test_the_route_reads_a_real_store_through_the_apps_own_accessors(tmp_path, monkeypatch):
    """Build a small SQLite store, then ask the route for a scorecard — the glue, not the maths."""
    from orderflow_system.data.database import Database
    from orderflow_system.data.models import Side, Tick
    from orderflow_system.desktop import config_store
    from orderflow_system.desktop import engine as engine_mod

    path = tmp_path / "orderflow.db"
    now = int(datetime.now(timezone.utc).timestamp() * 1000)

    async def build():
        db = Database(str(path))
        await db.connect()
        ticks = [Tick(timestamp_ms=now - 120_000 + index * 1000, price=100.0, size=1.0, side=Side.BUY)
                 for index in range(121)]
        await db.insert_ticks_batch("BTCUSDT", ticks)
        await db.close()

    asyncio.run(build())

    monkeypatch.setattr(config_store, "db_path", lambda: path)
    monkeypatch.setattr(engine_mod.engine, "_system", None, raising=False)
    monkeypatch.setattr(config_store, "load_config", lambda: {
        "instruments": [{"symbol": "BTCUSDT", "asset_class": "Crypto", "enabled": True},
                        {"symbol": "ETHUSDT", "asset_class": "Crypto", "enabled": True}],
        "data_quality": {"window_h": 1, "max_samples": 5_000},
    })
    client = _client()

    card = client.get("/api/atlas/data-quality/BTCUSDT?hours=1").json()
    assert card["ok"] is True and card["symbol"] == "BTCUSDT"
    assert card["asset_class"] == "crypto" and card["cadence_ms"] == 1000
    assert card["samples"] == 121 and card["last_ms"] == now, "the newest stored stamp is the last"
    assert isinstance(card["sentence"], str) and card["sentence"].startswith("history for BTCUSDT")
    assert card["verdict"] in dq.VERDICT_NOTES and card["settings"]["window_h"] == 1.0

    missing = client.get("/api/atlas/data-quality/ETHUSDT?hours=1").json()
    assert missing["ok"] is False and missing["detail"].startswith("no stored history for ETHUSDT")

    rows = client.get("/api/atlas/data-quality?hours=1").json()
    assert rows["ok"] is True and rows["kind"] == "ticks" and rows["window_h"] == 1.0
    assert [row["symbol"] for row in rows["rows"]] == ["ETHUSDT", "BTCUSDT"], "worst instrument first"
    assert rows["rows"][0]["ok"] is False and rows["rows"][1]["ok"] is True
    assert "no stored history" in rows["rows"][0]["detail"]


def test_the_rows_route_respects_the_symbol_list_and_the_read_budget(monkeypatch):
    from orderflow_system.desktop import config_store
    from orderflow_system.desktop import engine as engine_mod

    seen: list[int] = []

    class FakeDb:
        async def get_recent_ticks(self, instrument, start_ms, end_ms, limit=5_000):
            seen.append(int(limit))
            return []

        async def get_candles(self, instrument, timeframe, start_ms, end_ms):
            return []

    async def fake_open():
        return FakeDb(), False

    monkeypatch.setattr(dq, "_open_db", fake_open)
    monkeypatch.setattr(engine_mod.engine, "_system", None, raising=False)
    monkeypatch.setattr(config_store, "load_config", lambda: {
        "instruments": [{"symbol": sym, "asset_class": "Crypto", "enabled": True}
                        for sym in ("AAAUSDT", "BBBUSDT", "CCCUSDT")],
        "data_quality": {"max_samples": 9_000, "max_symbols": 2},
    })
    client = _client()
    payload = client.get("/api/atlas/data-quality?hours=1").json()
    assert payload["count"] == 2, "max_symbols is the cockpit's own bound"
    assert seen == [4_501, 4_501], seen       # 9000 shared across two instruments; the read probes one past it (§148 T5-F-05)
    assert payload["settings"]["max_samples"] == 9_000
    named = client.get("/api/atlas/data-quality?symbols=AAAUSDT,+BBBUSDT+,,&hours=1").json()
    assert [row["symbol"] for row in named["rows"]] == ["AAAUSDT", "BBBUSDT"]


def test_a_read_failure_is_a_sentence_for_that_symbol_not_a_500(monkeypatch):
    from orderflow_system.desktop import config_store
    from orderflow_system.desktop import engine as engine_mod

    class AngryDb:
        async def get_recent_ticks(self, *args, **kwargs):
            raise RuntimeError("database is locked")

    async def fake_open():
        return AngryDb(), False

    monkeypatch.setattr(dq, "_open_db", fake_open)
    monkeypatch.setattr(engine_mod.engine, "_system", None, raising=False)
    monkeypatch.setattr(config_store, "load_config", lambda: {
        "instruments": [{"symbol": "BTCUSDT", "asset_class": "Crypto", "enabled": True}],
    })
    client = _client()
    payload = client.get("/api/atlas/data-quality?hours=1").json()
    assert payload["ok"] is True and payload["count"] == 1
    assert payload["rows"][0]["ok"] is False
    assert payload["rows"][0]["detail"].startswith("no stored history for BTCUSDT yet")


# ══════════════════════════════════════════════════════════════
# The panel: node --check, the selftest, and the mirror pins
# ══════════════════════════════════════════════════════════════

def test_the_panel_and_its_selftest_exist_and_parse():
    assert PANEL.is_file() and SELFTEST.is_file()
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    for source in (PANEL, SELFTEST):
        proc = subprocess.run([node, "--check", str(source)], capture_output=True, text=True,
                              encoding="utf-8")
        assert proc.returncode == 0, proc.stderr


def test_the_panel_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8",
                          timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"data-quality selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0", out
    assert int(found.group(1)) >= 40, f"only {found.group(1)} checks ran — the selftest shrank"


def test_the_panel_paints_a_real_payload_from_this_module(tmp_path):
    """The cross-language gate: the JSON this module emits, painted by the panel under plain node.

    A rename of any key on either side has to fail here rather than in the browser — the panel and
    the scorecard are written in different languages and this is the only place they meet.
    """
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:                                               # pragma: no cover - CI without node
        pytest.skip("node is not on PATH")

    now = START + 7_200_000
    card = dq.scorecard("BTC-USD", two_hours_with_a_hole(), asset_class="crypto", now_ms=now,
                        window_h=2.0)
    assert card["ok"] is True and card["repairs"] and card["gaps"]
    rows_payload = {"ok": True, "at": now, "kind": "ticks", "window_h": 2.0, "count": 1,
                    "settings": dq.clean(None), "rows": [dq.row_of(card, keep_gaps=5)],
                    "card": card}
    good = tmp_path / "rows.json"
    good.write_text(json.dumps(rows_payload), encoding="utf-8")

    missing = dq.refusal("ETHUSDT", kind="ticks", asset_class="crypto")
    empty_payload = {"ok": True, "at": now, "kind": "ticks", "window_h": 2.0, "count": 1,
                     "settings": dq.clean(None), "rows": [dq.row_of(missing)], "card": missing}
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps(empty_payload), encoding="utf-8")

    for label, path in (("a scorecard", good), ("a refusal", empty)):
        proc = subprocess.run([node, str(SELFTEST), "--payload", str(path)],
                              cwd=str(SELFTEST.parent), capture_output=True, text=True, encoding="utf-8", timeout=60)
        output = (proc.stdout or "") + (proc.stderr or "")
        match = re.search(r"data-quality selftest:\s*(\d+)\s*ok,\s*(\d+)\s*failed", output)
        assert match, f"the selftest printed no summary for {label}:\n{output}"
        ok, failed = int(match.group(1)), int(match.group(2))
        assert proc.returncode == 0 and failed == 0, f"{label} painted badly:\n{output}"
        assert ok >= 55, "the live payload run must include the whole standing suite"


def test_the_selftest_passes_on_its_own():
    """The panel's own gate, run the way the contract asks for it: plain node, no DOM."""
    import re as _re
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:                                               # pragma: no cover - CI without node
        pytest.skip("node is not on PATH")
    proc = subprocess.run([node, str(SELFTEST)], cwd=str(SELFTEST.parent),
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    output = (proc.stdout or "") + (proc.stderr or "")
    match = _re.search(r"data-quality selftest:\s*(\d+)\s*ok,\s*(\d+)\s*failed", output)
    assert match, f"the selftest printed no summary:\n{output}"
    assert proc.returncode == 0 and int(match.group(2)) == 0, output


def test_the_panel_mirrors_the_module():
    """The JS formats what the server computed, so the routes and the letters must be the same ones."""
    text = PANEL.read_text(encoding="utf-8", errors="replace")
    assert "var ROWS_URL = '/api/atlas/data-quality';" in text
    assert "var SYMBOL_URL = '/api/atlas/data-quality/';" in text
    letters = re.search(r"var LETTERS = \[([^\]]+)\];", text)
    assert letters, "the panel lost its verdict letters"
    assert re.findall(r"'([A-F])'", letters.group(1)) == sorted(dq.VERDICT_NOTES), \
        "the panel's letters drifted from the module's verdict notes"
    assert "open a chart and let it load" not in text, "the refusal is the server's sentence"
    assert "no stored history for" not in text, "and the panel never rebuilds it by hand"
    created = set(re.findall(r"make\('[a-z]+', '([A-Za-z0-9_-]+)'", text))
    read = set(re.findall(r"el\('([A-Za-z0-9_-]+)'\)", text))
    shell = {"symbolSelect"}                 # the shell's own watchlist select, read not owned
    markup = {"dataQualitySub", "dataQualitySince", "dataQualityDetail", "dataQualitySummary",
              "dataQualityRecheck"}          # index.html owes the panel these five ids
    assert created, "the panel builds no elements at all"
    assert all(name.startswith("dataQuality") for name in created | markup), sorted(created | markup)
    assert read <= created | markup | shell, f"unexpected element ids: {sorted(read - created - markup - shell)}"
    assert text.count("setInterval(") == 1 and "OFAPPause.register" in text


# ── §148 T5-F05..F10: the exact-budget read, the quoted cap, the sort order, the half-second ────

def test_an_exact_budget_read_is_not_called_capped():
    """A store holding exactly the budget was read in full; only a longer one is a capped read.

    Measured before the fix: the ticks read asked for exactly ``limit`` rows and answered ``capped``
    with ``len(stamps) >= limit``, so an exact-budget store was reported as capped — the letter
    dropped to B and a trim hint appeared for a store with nothing to trim (the candle branch
    already used ``>``).
    """
    class ExactDb:
        def __init__(self, available: int) -> None:
            self.available = available
            self.asked: list[int] = []

        async def get_recent_ticks(self, instrument, start_ms, end_ms, limit=5_000):
            self.asked.append(int(limit))
            count = min(int(limit), self.available)
            return [{"ts_ms": 1_000_000 + index * 1_000} for index in range(count)]

    exact = ExactDb(5)
    stamps, capped = asyncio.run(
        dq._read_stamps(exact, "BTCUSDT", "ticks", "1m", 0, 9_999_999_999_999, 5))
    assert capped is False, "exactly the budget is a full read, not a cap"
    assert len(stamps) == 5 and exact.asked == [6], "the probe asks one past the budget"

    over = ExactDb(9)
    stamps, capped = asyncio.run(
        dq._read_stamps(over, "BTCUSDT", "ticks", "1m", 0, 9_999_999_999_999, 5))
    assert capped is True and over.asked == [6], "more than the budget is a capped read"
    assert len(stamps) == 5, "a capped read keeps the newest end, at the budget"


def test_the_capped_note_and_hint_quote_the_reads_own_budget():
    """The cap that bit is the read's budget, not the whole-store setting.

    Measured before the fix: the note and the trim hint both printed ``max_samples`` (60 000 by
    default) while the rows route reads ``max(2_000, max_samples // instruments)`` per instrument —
    2 500 with 24 instruments — so every row's note and hint quoted a cap nobody read with.
    """
    card = dq.scorecard("BTCUSDT", [], capped=True, count=2_500, sample_cap=2_500)
    assert card["ok"] is True
    assert "stopped at 2500 samples" in " ".join(card["notes"])
    trims = [hint for hint in dq.repairs_for(card, None, sample_cap=2_500)
             if hint["action"] == "trim"]
    assert trims and "capped at 2500 samples" in trims[0]["why"]

    # with no measured budget both halves keep their honest fallback: the setting itself
    plain = dq.scorecard("BTCUSDT", [], capped=True, count=2_500)
    assert f"stopped at {dq.DEFAULTS['max_samples']} samples" in " ".join(plain["notes"])
    plain_trims = [hint for hint in dq.repairs_for(plain, None) if hint["action"] == "trim"]
    assert plain_trims and f"capped at {dq.DEFAULTS['max_samples']} samples" in plain_trims[0]["why"]


def test_the_route_hands_the_scorecard_the_budget_it_read_with(monkeypatch):
    """The rows route reads ``budget`` rows per instrument and must tell the scorecard that number.

    Measured before the fix: the route read with ``budget`` but called ``scorecard(...)`` without it,
    so every row's capped note and trim hint quoted the whole-store setting instead.
    """
    from orderflow_system.desktop import config_store
    from orderflow_system.desktop import engine as engine_mod

    passed: list = []
    real_scorecard = dq.scorecard

    def spy(symbol, samples=None, **kwargs):
        passed.append(kwargs.get("sample_cap"))
        return real_scorecard(symbol, samples, **kwargs)

    class FakeDb:
        async def get_recent_ticks(self, instrument, start_ms, end_ms, limit=5_000):
            return []

    async def fake_open():
        return FakeDb(), False

    monkeypatch.setattr(dq, "_open_db", fake_open)
    monkeypatch.setattr(dq, "scorecard", spy)
    monkeypatch.setattr(engine_mod.engine, "_system", None, raising=False)
    monkeypatch.setattr(config_store, "load_config", lambda: {
        "instruments": [{"symbol": sym, "asset_class": "Crypto", "enabled": True}
                        for sym in ("AAAUSDT", "BBBUSDT", "CCCUSDT")],
        "data_quality": {"max_samples": 6_000, "max_symbols": 3},
    })
    payload = _client().get("/api/atlas/data-quality?hours=1").json()
    assert payload["count"] == 3
    assert passed == [2_000, 2_000, 2_000], passed   # 6 000 shared across three instruments


def test_the_worst_instrument_leads_the_list_not_by_accident(monkeypatch):
    """The panel sorts worst-first; the server must agree by the ranking itself.

    Measured before the fix: the route sorted by the raw letter (``"A" < "F"``, best first) while
    the panel re-sorted its own way, so the list opened with the healthiest instrument. The older
    route test passed by accident — both of its instruments ranked F, so the coverage tie-break
    happened to order them the way the test expected.
    """
    ranked = dq.sort_rows([
        {"symbol": "AAAUSDT", "verdict": "A", "coverage_pct": 100.0},
        {"symbol": "ZZZUSDT", "verdict": "F", "coverage_pct": 0.6},
        {"symbol": "MIDUSDT", "verdict": "B", "coverage_pct": 42.0},
    ])
    assert [row["symbol"] for row in ranked] == ["ZZZUSDT", "MIDUSDT", "AAAUSDT"]
    # a letter this build cannot read leads even the Fs — the panel ranks it the same way
    ranked = dq.sort_rows([{"symbol": "FUSDT", "verdict": "F", "coverage_pct": 9.0},
                           {"symbol": "REFUSED", "verdict": "", "coverage_pct": 0.0}])
    assert [row["symbol"] for row in ranked] == ["REFUSED", "FUSDT"]

    from orderflow_system.desktop import config_store
    from orderflow_system.desktop import engine as engine_mod

    class HalfDb:
        async def get_recent_ticks(self, instrument, start_ms, end_ms, limit=5_000):
            if instrument != "AAAUSDT":
                return []
            return [{"ts_ms": end_ms - index * 1_000} for index in range(3_600)]

    async def fake_open():
        return HalfDb(), False

    monkeypatch.setattr(dq, "_open_db", fake_open)
    monkeypatch.setattr(engine_mod.engine, "_system", None, raising=False)
    monkeypatch.setattr(config_store, "load_config", lambda: {
        "instruments": [{"symbol": "AAAUSDT", "asset_class": "Crypto", "enabled": True},
                        {"symbol": "ZZZUSDT", "asset_class": "Crypto", "enabled": True}],
        "data_quality": {"max_samples": 8_000, "max_symbols": 2},
    })
    rows = _client().get("/api/atlas/data-quality?hours=1").json()["rows"]
    assert [row["symbol"] for row in rows] == ["ZZZUSDT", "AAAUSDT"], rows
    assert rows[1]["verdict"] == "A", "the healthy row really is an A, not two refusals"


def test_the_durations_the_panel_repeats_round_half_up():
    """The panel renders raw milliseconds with ``Math.round``; the server's words must match.

    Measured before the fix: ``fmt_duration(2500)`` said "2 s" beside the panel's "3 s" (Python's
    ``round`` is half-to-even), and 62 500 / 90 500 disagreed by a second the same way.
    """
    assert dq.fmt_duration(2_500) == "3 s"
    assert dq.fmt_duration(62_500) == "1 m 03 s"
    assert dq.fmt_duration(90_500) == "1 m 31 s"
    assert dq.fmt_duration(4_500) == "5 s", "half-to-even would say 4 s"
    assert dq.fmt_duration(1_500) == "2 s", "the half every rule sends up"
    assert dq.fmt_duration(42_000) == "42 s" and dq.fmt_duration(0) == "0 s"


def test_the_id_audit_checks_every_module_and_every_page():
    """§148 T5-F-17: the audit's element-id check scanned three files' lookups, so no §147 panel id
    was ever verified against the page. It now walks JS_FILES and every UI page — and the widened
    scan is what surfaced the stale `logBody`, `inCard` and `monStatus` references this batch fixed
    (162 ids was the three-file baseline)."""
    import sys

    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(repo / "scripts" / "audit_ui_refs.py")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(repo), timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    found = re.search(r"ids used by modules: (\d+)", proc.stdout)
    assert found, proc.stdout
    assert int(found.group(1)) > 162, ("162 is the old three-file baseline — the scan must walk "
                                       "every module in JS_FILES")


def test_the_depth_panel_docs_name_the_view_it_mounts_in():
    """§148 T5-F-17's cascade: the guide placed Depth executions in the Overview, but the only
    Participants'-intent card — the detector's mount anchor — lives in the Trackers view."""
    guide = (Path(__file__).resolve().parents[1] / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
    flat = " ".join(guide.split())
    assert "Depth executions** (Trackers, under Participants' intent)" in flat
