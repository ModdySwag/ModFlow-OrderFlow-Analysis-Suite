"""P1-5's gate: the session clock and the roll calendar answer offline, and both refuse politely.

The clock lives in `atlas/sessions.py` as pure functions over an injected `now_ms`, so the whole
state machine is pinned here at chosen instants — including the DST-crossing ones (a 09:30 ET open is
14:30 UTC in winter and 13:30 UTC in summer, and the local clock reads 09:30 both times). The roll
calendar is convention arithmetic (equity index = third Friday, energy = three business days before
the 25th of the month before delivery, metals = third-to-last business day), pinned for two roots
against the module's own documented rules — not against a data feed, because there is not one.

The panel's decisions are shelled out to `sessions.selftest.js` (keys.selftest-style), and the two
tables the two halves share — the phase names — are pinned EQUAL so neither side can drift alone.

Deliberately dumb: plain data in, assertions out, no browser, no clock of its own.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
SESSIONS_JS = UI / "sessions.js"
SELFTEST = UI / "sessions.selftest.js"
MODULE = ROOT / "orderflow_system" / "atlas" / "sessions.py"

from orderflow_system.atlas import sessions  # noqa: E402


def ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    """One UTC instant in milliseconds — the only clock any test here uses."""
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


def utc(instant: int) -> datetime:
    return datetime.fromtimestamp(instant / 1000, tz=timezone.utc)


def rth() -> dict:
    return sessions.clean_template(sessions.BUILTINS["us-equities-rth"])


def globex() -> dict:
    return sessions.clean_template(sessions.BUILTINS["cme-globex-index"])


def tokyo() -> dict:
    return sessions.clean_template(sessions.BUILTINS["jp-equities"])


# ── clean(): coercion, clamping, and never raising ──────────────────────────────────────────────

def test_clean_answers_the_defaults_for_anything_at_all():
    for junk in (None, 5, "nope", [], {"unknown": 1}, {"templates": 7, "roots": "ES", "months": "x"}):
        block = sessions.clean(junk)
        assert set(sessions.DEFAULTS) <= set(block), f"clean({junk!r}) lost a key"
        assert isinstance(block["templates"], list) and isinstance(block["roots"], list)
        assert block["roots"], "a block with no roots could not answer a roll table"


def test_clean_clamps_numbers_and_drops_names_it_cannot_resolve():
    block = sessions.clean({"months": 999, "holidays_ahead": -4, "roots": ["ES", "ZZ", "es"],
                            "symbols": {"spy": "us-equities-rth", "junk": "no-such-template"},
                            "active": "not-a-template"})
    assert block["months"] == 24 and block["holidays_ahead"] == 0
    assert block["roots"] == ["ES"], "an unknown root is dropped, and the duplicate is not kept"
    assert block["symbols"] == {"SPY": "us-equities-rth"}
    assert block["active"] == "", "an active name that matches nothing reads as 'the first one'"
    assert sessions.clean({"months": 3})["months"] == 3
    assert sessions.clean({"months": 0})["months"] == 1


def test_clean_coerces_templates_from_a_list_or_a_mapping():
    listed = sessions.clean({"templates": [{"name": "Mine!", "open": "8:00", "close": "17:00",
                                            "days": "mon-fri", "symbols": ["spy", "spx"]}]})
    assert [tpl["name"] for tpl in listed["templates"]] == ["mine"]
    mapped = sessions.clean({"templates": {"My Hours": {"open": "8:00", "close": "17:00"}}})
    assert [tpl["name"] for tpl in mapped["templates"]] == ["my-hours"], \
        "a mapping's key names the template"
    assert mapped["templates"][0]["title"] == "my hours"


def test_clean_template_normalises_every_field():
    tpl = sessions.clean_template({
        "name": "  Test Session ", "title": "", "exchange": "X" * 200, "timezone": "  america/new_york ",
        "days": ["Mon", "fri", 7, "mon"], "open": "930", "close": "16:00",
        "breaks": ["12:00-13:00", {"start": "09:00", "end": "09:00"}, "junk", ["14:00", "14:30"]],
        "holidays": ["2026-07-03 Independence Day", {"date": "2026/11/27", "name": "half day",
                                                     "closed": False, "close": "13:00"}],
        "holiday_rule": "us-market", "symbols": ["spy", "SPY", "q" * 40], "note": "n" * 400,
        "unknown_key": "dropped",
    })
    assert tpl["name"] == "test-session" and tpl["title"] == "test session"
    assert sessions.canonical_zone(tpl["timezone"]) == "America/New_York", "whitespace and case"
    assert tpl["days"] == [1, 5, 7]
    assert tpl["open"] == "09:30" and tpl["close"] == "16:00"
    assert [row["start"] for row in tpl["breaks"]] == ["12:00", "14:00"], "a zero-length break is dropped"
    assert [row["date"] for row in tpl["holidays"]] == ["2026-07-03", "2026-11-27"]
    assert tpl["holidays"][1]["close"] == "13:00" and tpl["holidays"][1]["closed"] is False
    assert tpl["holidays"][0]["name"] == "Independence Day"
    assert tpl["symbols"] == ["SPY", "Q" * 16]
    assert len(tpl["note"]) == 200 and len(tpl["exchange"]) == 60
    assert "unknown_key" not in tpl


def test_clean_template_never_raises_on_hostile_shapes():
    for junk in (None, "sess", 12, [1, 2], {"open": [], "close": {}, "days": {"mon": 1},
                                            "breaks": 5, "holidays": {"x": "y"}, "symbols": 3}):
        tpl = sessions.clean_template(junk)
        assert set(sessions.TEMPLATE_KEYS) == set(tpl), f"clean_template({junk!r}) is not a template"
        assert sessions.session_span_minutes(tpl) > 0


def test_an_unknown_timezone_is_kept_but_flagged_and_says_so():
    tpl = sessions.clean_template({"name": "typo", "timezone": "Europe/Berling", "open": "09:00",
                                   "close": "17:00"})
    assert tpl["timezone"] == "Europe/Berling", "the user's own words are never thrown away"
    assert sessions.zone_known(tpl["timezone"]) is False
    assert sessions.zone_offset_minutes(tpl["timezone"], ms(2026, 9, 21, 12)) == 0
    problems = sessions.validate(tpl)
    assert any("timezone" in line and "UTC" in line for line in problems), problems
    assert sessions.session_state(tpl, ms(2026, 9, 21, 12))["timezone_known"] is False


def test_validate_names_what_would_misbehave():
    never = sessions.validate({"name": "never", "open": "09:00", "close": "09:00"})
    assert any("same time" in line for line in never)
    outside = sessions.validate({"name": "b", "open": "09:00", "close": "17:00",
                                 "breaks": [{"start": "03:00", "end": "04:00"}]})
    assert any("outside the session" in line for line in outside)
    contradictory = sessions.validate({"name": "c", "open": "09:00", "close": "17:00",
                                       "holidays": [{"date": "2026-11-27", "closed": True, "close": "13:00"}]})
    assert any("ignored" in line for line in contradictory)
    early = sessions.validate({"name": "d", "open": "09:00", "close": "17:00",
                               "holidays": [{"date": "2026-11-27", "closed": False, "close": "08:00"}]})
    assert any("at or before the open" in line for line in early)
    assert sessions.validate(rth()) == [], "a built-in must be clean"


def test_the_built_in_library_is_every_one_a_usable_template():
    built = sessions.library()
    assert len(built) >= 8, "the library is the copy-paste surface; it cannot be thin"
    names = [tpl["name"] for tpl in built]
    assert len(names) == len(set(names))
    for tpl in built:
        assert tpl["builtin"] is True
        assert tpl["note"], f"{tpl['name']} has no note explaining what it is an example of"
        assert sessions.zone_known(tpl["timezone"]), tpl["name"]
        assert sessions.session_span_minutes(tpl) > 0
        assert sessions.validate(tpl) == [], (tpl["name"], sessions.validate(tpl))
    assert sessions.templates_of({"templates": [{"name": "mine", "open": "08:00", "close": "09:00"}]})[-1]["name"] == "mine"
    assert sessions.templates_of({})[0]["builtin"] is True


# ── times, days, zones ─────────────────────────────────────────────────────────────────────────

def test_parse_minutes_takes_the_shapes_a_config_loses_by():
    assert sessions.parse_minutes("09:30") == 570
    assert sessions.parse_minutes("9:30") == 570
    assert sessions.parse_minutes("0930") == 570
    assert sessions.parse_minutes(570) == 570
    assert sessions.parse_minutes("24:00") == 1440, "the end of the day is a real time"
    assert sessions.parse_minutes("00:00") == 0
    assert sessions.parse_minutes("9") == 540
    for junk in (None, "", "junk", "9:75", "25:00", "12345", -1, True, 2000):
        assert sessions.parse_minutes(junk) is None, f"{junk!r} must be unknown, never midnight"
    assert sessions.fmt_minutes(570) == "09:30" and sessions.fmt_minutes(1440) == "24:00"
    assert sessions.fmt_minutes(None) == "00:00"


def test_parse_days_reads_names_numbers_and_ranges():
    assert sessions.parse_days("mon-fri") == [1, 2, 3, 4, 5]
    assert sessions.parse_days("mon, wed, fri") == [1, 3, 5]
    assert sessions.parse_days(["Mon", "tue"]) == [1, 2]
    assert sessions.parse_days("1-5") == [1, 2, 3, 4, 5]
    assert sessions.parse_days("sun-thu") == [1, 2, 3, 4, 7], "a range across the week wraps"
    assert sessions.parse_days("everyday") == [1, 2, 3, 4, 5, 6, 7]
    assert sessions.parse_days(0) == [7], "0 is the other Sunday convention"
    assert sessions.parse_days(5) == [5]
    assert sessions.parse_days("nonsense") == []


def test_the_zone_table_handles_the_three_dst_rules_and_the_fixed_ones():
    # US: 02:00 local on the second Sunday in March, back on the first Sunday in November.
    assert sessions.zone_offset_minutes("America/New_York", ms(2026, 3, 6, 12)) == -300
    assert sessions.zone_offset_minutes("America/New_York", ms(2026, 3, 9, 12)) == -240
    assert sessions.zone_offset_minutes("America/New_York", ms(2026, 11, 2, 12)) == -300
    # EU: last Sunday in March / October, at 01:00 UTC.
    assert sessions.zone_offset_minutes("Europe/London", ms(2026, 3, 29, 0, 30)) == 0
    assert sessions.zone_offset_minutes("Europe/London", ms(2026, 3, 29, 2, 0)) == 60
    assert sessions.zone_offset_minutes("Europe/London", ms(2026, 10, 26, 12)) == 0
    # Australia: first Sunday in October / April, 16:00 UTC the Saturday before.
    assert sessions.zone_offset_minutes("Australia/Sydney", ms(2026, 4, 3, 12)) == 660
    assert sessions.zone_offset_minutes("Australia/Sydney", ms(2026, 4, 6, 12)) == 600
    assert sessions.zone_offset_minutes("Australia/Sydney", ms(2026, 10, 5, 12)) == 660
    # Fixed offsets never move.
    for month in (1, 7):
        assert sessions.zone_offset_minutes("Asia/Tokyo", ms(2026, month, 15, 12)) == 540
        assert sessions.zone_offset_minutes("Asia/Kolkata", ms(2026, month, 15, 12)) == 330
    assert sessions.canonical_zone("us/eastern") == "America/New_York"
    assert sessions.canonical_zone("New York") == "America/New_York"
    assert sessions.canonical_zone("Mars/Olympus") == ""


def test_the_dst_edges_are_each_zone_own_wall_time():
    """§148: every US zone switches at 02:00 ITS OWN local time, and Australia's stamp was a day late.

    Cross-checked against zoneinfo at 30-minute steps across the whole of 2026 before the fix:
    Chicago 4 disagreements, Denver 8, Los Angeles 12, Sydney 96 (a full day late at both ends).
    Season-interior samples cannot see any of it — these are the edges, 30 minutes either side.
    """
    edges = [
        ("America/New_York", (2026, 3, 8, 6, 30), (2026, 3, 8, 7, 30), -300, -240),
        ("America/New_York", (2026, 11, 1, 5, 30), (2026, 11, 1, 6, 30), -240, -300),
        ("America/Chicago", (2026, 3, 8, 7, 30), (2026, 3, 8, 8, 30), -360, -300),
        ("America/Chicago", (2026, 11, 1, 6, 30), (2026, 11, 1, 7, 30), -300, -360),
        ("America/Denver", (2026, 3, 8, 8, 30), (2026, 3, 8, 9, 30), -420, -360),
        ("America/Los_Angeles", (2026, 3, 8, 9, 30), (2026, 3, 8, 10, 30), -480, -420),
        ("America/Los_Angeles", (2026, 11, 1, 8, 30), (2026, 11, 1, 9, 30), -420, -480),
        ("Australia/Sydney", (2026, 10, 3, 15, 30), (2026, 10, 3, 16, 30), 600, 660),
        ("Australia/Sydney", (2026, 4, 4, 15, 30), (2026, 4, 4, 16, 30), 660, 600),
    ]
    for zone, before, after, off_before, off_after in edges:
        assert sessions.zone_offset_minutes(zone, ms(*before)) == off_before, (zone, before)
        assert sessions.zone_offset_minutes(zone, ms(*after)) == off_after, (zone, after)


# ── the session clock: every phase, at its own boundary ─────────────────────────────────────────

def test_the_state_machine_across_the_regular_session():
    tpl = rth()
    assert sessions.session_state(tpl, ms(2026, 9, 21, 12, 0))["phase"] == "pre-open"
    assert sessions.session_state(tpl, ms(2026, 9, 21, 13, 30))["phase"] == "open"
    assert sessions.session_state(tpl, ms(2026, 9, 21, 19, 59))["phase"] == "open"
    assert sessions.session_state(tpl, ms(2026, 9, 21, 20, 0))["phase"] == "post-close"
    saturday = sessions.session_state(tpl, ms(2026, 9, 19, 16, 0))
    assert saturday["phase"] == "closed" and saturday["reason"] == "the weekend"
    assert saturday["state"] == "closed"
    holiday = sessions.session_state(tpl, ms(2026, 7, 3, 14, 0))
    assert holiday["phase"] == "holiday" and holiday["holiday"] == "Independence Day (observed)"
    assert holiday["reason"] == "Independence Day (observed)"
    # The phase ladder only ever reports the six phases, with the state in step with it.
    for when in (ms(2026, 9, 21, 12), ms(2026, 9, 21, 13, 30), ms(2026, 9, 21, 20, 30),
                 ms(2026, 9, 19, 16), ms(2026, 7, 3, 14)):
        state = sessions.session_state(tpl, when)
        assert state["phase"] in sessions.PHASES, state["phase"]
        assert state["state"] == ("open" if state["phase"] == "open" else "closed")
        assert state["ok"] is True


def test_the_boundaries_are_the_stamps_not_the_words():
    tpl = rth()
    at_open = sessions.session_state(tpl, ms(2026, 9, 21, 13, 30))
    assert at_open["state"] == "open" and at_open["minutes_to_open"] == 0
    assert utc(at_open["open_ms"]).strftime("%H:%M") == "13:30", "09:30 New York = 13:30 UTC"
    assert utc(at_open["open_ms"]).strftime("%Y-%m-%d") == "2026-09-21"
    at_close = sessions.session_state(tpl, ms(2026, 9, 21, 20, 0))
    assert at_close["state"] == "closed" and at_close["phase"] == "post-close"
    just_before = sessions.session_state(tpl, ms(2026, 9, 21, 19, 59))
    assert just_before["state"] == "open" and just_before["minutes_to_close"] == 1, \
        "the countdown rounds up, so it never reads 0 while the bell is still ahead"


def test_the_minute_arithmetic_of_one_session():
    tpl = rth()
    state = sessions.session_state(tpl, ms(2026, 9, 21, 19, 0))     # 15:00 New York
    assert state["close_ms"] == ms(2026, 9, 21, 20, 0)
    assert state["minutes_to_close"] == 60
    assert state["minutes_to_open"] == 0
    assert state["session_minutes"] == 390 and state["trade_minutes"] == 390
    assert state["elapsed_minutes"] == 330
    assert state["elapsed_share"] == round(330 / 390, 3)
    assert state["progress_pct"] == 85
    assert state["hours"] == "09:30 → 16:00 America/New_York"
    assert state["local"]["time"] == "15:00" and state["local"]["weekday_name"] == "mon"
    assert state["local"]["offset_minutes"] == -240, "September is daylight time"
    # Nothing is invented about a session that is not running.
    closed = sessions.session_state(tpl, ms(2026, 9, 21, 21, 0))
    assert closed["elapsed_share"] is None and closed["elapsed_minutes"] is None


def test_the_countdown_to_the_next_open_on_a_weekend():
    tpl = rth()
    friday_evening = sessions.session_state(tpl, ms(2026, 9, 18, 21, 0))     # Fri 17:00 ET
    assert friday_evening["phase"] == "post-close"
    assert friday_evening["minutes_to_open"] ==         (ms(2026, 9, 21, 13, 30) - ms(2026, 9, 18, 21, 0)) // 60000, "17:00 ET Friday → 09:30 ET Monday"
    assert utc(friday_evening["next_open_ms"]).strftime("%a %Y-%m-%d %H:%M") == "Mon 2026-09-21 13:30"
    assert utc(friday_evening["next_close_ms"]).strftime("%a %H:%M") == "Mon 20:00"
    assert friday_evening["open_ms"] is None and friday_evening["close_ms"] is None


def test_a_break_is_its_own_phase_and_reopens_to_the_minute():
    tpl = tokyo()                                                    # 09:00-15:00, break 11:30-12:30
    assert tpl["breaks"] == [{"start": "11:30", "end": "12:30", "label": "lunch"}]
    assert sessions.session_state(tpl, ms(2026, 9, 22, 2, 0))["phase"] == "open"          # 11:00 JST
    inside = sessions.session_state(tpl, ms(2026, 9, 22, 2, 30))                         # 11:30 JST
    assert inside["phase"] == "break" and inside["state"] == "closed"
    assert inside["minutes_to_open"] == 60, "the break's end is the next open"
    assert inside["minutes_to_close"] == 210, "11:30 JST is 210 minutes from the 15:00 close"
    assert inside["trade_minutes"] == 300 and inside["break_minutes"] == 60
    assert inside["session_minutes"] == 360
    reopened = sessions.session_state(tpl, ms(2026, 9, 22, 3, 30))                       # 12:30 JST
    assert reopened["phase"] == "open" and reopened["minutes_to_open"] == 0
    assert [row["start"] for row in reopened["breaks"]] == ["11:30"], "the panel draws the band"


def test_a_break_outside_the_session_is_not_a_break_of_it():
    # Globex closes at 16:00 and reopens at 17:00; that hour is a GAP between sessions, not a break.
    tpl = sessions.clean_template({**globex(), "breaks": [{"start": "16:00", "end": "17:00"}]})
    assert sessions.break_windows(tpl) == []
    assert any("outside the session" in line for line in sessions.validate(tpl))
    weekdays = sessions.clean_template({**tokyo(), "breaks": [{"start": "12:00", "end": "13:00"}]})
    assert [row["start"] for row in sessions.break_windows(weekdays)] == ["12:00"]


def test_a_session_that_wraps_midnight_belongs_to_the_day_it_opened():
    tpl = globex()                                                   # 17:00 CT → 16:00 CT next day
    assert sessions.wraps_midnight(tpl) is True
    sunday = sessions.session_state(tpl, ms(2026, 9, 20, 23, 0))     # Sun 18:00 CT
    assert sunday["phase"] == "open" and sunday["session_date"] == "2026-09-20"
    monday = sessions.session_state(tpl, ms(2026, 9, 21, 14, 0))     # Mon 09:00 CT
    assert monday["phase"] == "open" and monday["session_date"] == "2026-09-20", \
        "Monday morning is still Sunday's session"
    assert utc(monday["close_ms"]).strftime("%a %H:%M") == "Mon 21:00", "16:00 CT = 21:00 UTC"
    assert monday["local"]["time"] == "09:00" and monday["local"]["offset_minutes"] == -300
    assert monday["elapsed_minutes"] == 16 * 60 and monday["session_minutes"] == 23 * 60
    friday = sessions.session_state(tpl, ms(2026, 9, 25, 22, 0))     # Fri 17:00 CT
    assert friday["phase"] == "closed" and friday["reason"] == "this template does not trade today"
    assert friday["minutes_to_open"] == 48 * 60, "Friday 17:00 CT → Sunday 17:00 CT"
    saturday = sessions.session_state(tpl, ms(2026, 9, 26, 17, 0))
    assert saturday["phase"] == "closed" and saturday["reason"] == "the weekend"
    assert sessions.session_state(tpl, ms(2026, 9, 20, 15, 0))["phase"] == "pre-open"


def test_a_24_hour_market_is_always_open_and_never_invents_a_break():
    tpl = sessions.clean_template(sessions.BUILTINS["crypto-247"])
    state = sessions.session_state(tpl, ms(2026, 9, 20, 12, 0))
    assert state["phase"] == "open" and state["state"] == "open"
    assert state["session_minutes"] == 1440 and state["minutes_to_close"] == 720
    assert state["elapsed_share"] == 0.5 and state["session_date"] == "2026-09-20"
    assert state["breaks"] == [] and state["days"] == [1, 2, 3, 4, 5, 6, 7]


def test_an_early_close_shortens_the_session_and_then_it_is_closed():
    tpl = sessions.clean_template({
        "name": "half-day", "timezone": "America/New_York", "days": "mon-fri",
        "open": "09:30", "close": "16:00",
        "holidays": [{"date": "2026-11-27", "name": "day after Thanksgiving", "closed": False,
                      "close": "13:00"}],
    })
    open_state = sessions.session_state(tpl, ms(2026, 11, 27, 16, 0))          # 11:00 ET
    assert open_state["phase"] == "open" and open_state["minutes_to_close"] == 120
    assert open_state["close_ms"] == ms(2026, 11, 27, 18, 0), "13:00 ET = 18:00 UTC"
    assert open_state["session_minutes"] == 210
    assert sessions.session_state(tpl, ms(2026, 11, 27, 18, 30))["phase"] == "post-close"
    assert sessions.session_state(tpl, ms(2026, 11, 25, 17, 0))["minutes_to_close"] == 240, \
        "an ordinary day keeps the template's own close"


def test_the_dst_crossing_moves_the_utc_stamp_and_not_the_wall_clock():
    tpl = rth()
    before = sessions.session_state(tpl, ms(2026, 3, 6, 14, 31))       # Fri 09:31 ET, EST
    after = sessions.session_state(tpl, ms(2026, 3, 9, 13, 31))        # Mon 09:31 ET, EDT
    assert utc(before["open_ms"]).strftime("%H:%M") == "14:30" and before["local"]["offset_minutes"] == -300
    assert utc(after["open_ms"]).strftime("%H:%M") == "13:30" and after["local"]["offset_minutes"] == -240
    assert before["local"]["time"] == after["local"]["time"] == "09:31"
    assert sessions.session_state(tpl, ms(2026, 3, 9, 13, 29))["phase"] == "pre-open", \
        "the open is still 09:30 on the wall clock of the day the clock moved"
    # The southern rule: a Sydney FX day keeps its 07:00 local open across its own change.
    sydney = sessions.clean_template(sessions.BUILTINS["fx-sydney"])
    winter = sessions.session_state(sydney, ms(2026, 6, 15, 2, 0))      # 12:00 AEST, standard time
    summer = sessions.session_state(sydney, ms(2026, 10, 6, 2, 0))     # 13:00 AEDT, daylight time
    assert winter["local"]["offset_minutes"] == 600 and summer["local"]["offset_minutes"] == 660
    assert winter["local"]["time"] == "12:00" and summer["local"]["time"] == "13:00"
    assert utc(winter["open_ms"]).strftime("%Y-%m-%d %H:%M") == "2026-06-14 21:00", "07:00 AEST"
    assert utc(summer["open_ms"]).strftime("%Y-%m-%d %H:%M") == "2026-10-05 20:00", "07:00 AEDT"
    assert winter["hours"] == summer["hours"], "a template's own hours do not move with DST"


def test_a_holiday_rule_answers_by_rule_and_never_by_a_hardcoded_list():
    tpl = rth()
    assert sessions.holiday_on(tpl, "2026-07-03")["name"] == "Independence Day (observed)"
    assert sessions.holiday_on(tpl, "2027-12-31")["name"] == "New Year's Day (observed)", \
        "the 2028 observance lands on 2027-12-31"
    assert sessions.holiday_on(tpl, "2028-01-01") is None, "the actual date is not the holiday"
    assert sessions.holiday_on(tpl, "2026-03-06") is None
    rules = {row["date"]: row["name"] for row in sessions.us_market_holidays(2026)}
    assert rules["2026-01-01"] == "New Year's Day"
    assert rules["2026-01-19"] == "Martin Luther King Jr. Day"
    assert rules["2026-02-16"] == "Presidents' Day"
    assert rules["2026-04-03"] == "Good Friday"
    assert rules["2026-05-25"] == "Memorial Day"
    assert rules["2026-06-19"] == "Juneteenth"
    assert rules["2026-09-07"] == "Labor Day"
    assert rules["2026-11-26"] == "Thanksgiving"
    assert rules["2026-12-25"] == "Christmas"
    assert len(rules) == 10, "the rule set is exactly the exchange's ten"
    # A template's own entry wins, so a user can correct a rule date by writing it down.
    corrected = sessions.clean_template({**tpl, "holidays": [
        {"date": "2026-11-26", "name": "closed for the parade", "closed": True}]})
    assert sessions.holiday_on(corrected, "2026-11-26")["name"] == "closed for the parade"
    assert sessions.holiday_on(tpl, "2026-11-26")["name"] == "Thanksgiving"
    upcoming = sessions.upcoming_holidays(tpl, ms(2026, 9, 20, 12), 4)
    assert [row["date"] for row in upcoming] == ["2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18"]
    assert all(row["days_away"] > 0 for row in upcoming)
    assert sessions.upcoming_holidays(tpl, ms(2026, 9, 20, 12), 0) == []


def test_the_state_carries_the_template_s_own_problems_for_the_panel_to_print():
    broken = sessions.clean_template({"name": "broken", "timezone": "Nowhere/Nothing",
                                      "open": "09:00", "close": "17:00"})
    state = sessions.session_state(broken, ms(2026, 9, 21, 12, 0))
    assert state["problems"] and "Nowhere/Nothing" in state["problems"][0]
    assert state["state"] == "open", "an unknown zone is read as UTC, and 12:00 UTC is inside 09:00-17:00"


def test_session_state_never_raises_on_a_missing_clock_or_symbol():
    for when in (None, 0, "junk", -1, 1e18):
        state = sessions.session_state(rth(), when)
        assert state["ok"] is True and state["phase"] in sessions.PHASES
    assert sessions.session_state(None, ms(2026, 9, 21, 14, 0))["template"] == "template"


# ── the roll calendar ───────────────────────────────────────────────────────────────────────────

def test_the_equity_index_expires_on_the_third_friday():
    # Documented convention: third Friday, quarterly cycle (H, M, U, Z), roll the business day before.
    assert sessions.expiry_date("ES", 2026, 12).isoformat() == "2026-12-18"
    assert sessions.expiry_date("NQ", 2026, 9).isoformat() == "2026-09-18"
    table = sessions.roll_calendar("ES", ms(2026, 9, 20, 12), 4)
    assert table["ok"] is True and table["kind"] == "index" and table["venue"] == "CME"
    assert table["rule"] == "the third Friday of the contract month"
    assert table["months_rule"] == "H, M, U, Z"
    assert table["front"] == "ESZ26" and table["next_expiry"] == "2026-12-18"
    assert table["next_roll"] == "2026-12-17" and table["days_to_roll"] == 88
    assert [row["month"] for row in table["contracts"]] == ["2026-12", "2027-03", "2027-06", "2027-09"]
    assert table["contracts"][0]["front"] is True
    assert all(row["days_to_roll"] >= 0 for row in table["contracts"])
    assert all(row["expiry"] > row["roll"] for row in table["contracts"])


def test_the_energy_contract_expires_three_business_days_before_the_25th():
    # Documented convention: three business days before the 25th of the month before delivery, every
    # month; the front month's volume leaves early, so the roll is three business days before that.
    assert sessions.expiry_date("CL", 2026, 12).isoformat() == "2026-11-20"
    # CLX26's reference 25th is a Sunday, so CME's non-business-day clause starts the count from the
    # Friday: 2026-10-20. This line read 2026-10-21 until §148 T4-F6 (the module's own arithmetic,
    # not the rule) — corrected, declared in the register.
    assert sessions.expiry_date("CL", 2026, 11).isoformat() == "2026-10-20"
    assert sessions.expiry_date("NG", 2027, 1).isoformat() == "2026-12-22", \
        "the 25th of December is a Friday, so three business days back is the 22nd"
    table = sessions.roll_calendar("CL", ms(2026, 9, 20, 12), 3)
    assert table["ok"] is True and table["kind"] == "energy"
    assert table["front"] == "CLX26" and table["next_expiry"] == "2026-10-20"
    # both follow the corrected expiry (three business days before it): §148 T4-F6
    assert table["next_roll"] == "2026-10-15" and table["days_to_roll"] == 25
    december = [row for row in table["contracts"] if row["month"] == "2026-12"][0]
    assert december["expiry"] == "2026-11-20" and december["roll"] == "2026-11-17"
    assert [row["month"] for row in table["contracts"]] == ["2026-11", "2026-12", "2027-01"]


def test_the_metals_contract_terminates_on_the_third_to_last_business_day():
    assert sessions.expiry_date("GC", 2026, 12).isoformat() == "2026-12-29"
    assert sessions.expiry_date("SI", 2026, 12).isoformat() == "2026-12-29"
    table = sessions.roll_calendar("GC", ms(2026, 9, 20, 12), 2)
    assert table["kind"] == "metal" and table["contracts"][0]["expiry"] == "2026-09-28"
    assert table["contracts"][1]["roll"] == "2026-10-27"


def test_a_contract_that_has_rolled_leaves_the_front():
    # ESZ26's roll is 2026-12-17: the next day the front month is the March contract.
    before = sessions.roll_calendar("ES", ms(2026, 12, 17, 12), 2)
    after = sessions.roll_calendar("ES", ms(2026, 12, 18, 12), 2)
    assert before["front"] == "ESZ26" and before["days_to_roll"] == 0
    assert after["front"] == "ESH27" and after["days_to_roll"] > 0
    assert all(row["days_to_roll"] >= 0 for row in after["contracts"])


def test_the_contract_label_carries_the_month_code_and_the_two_digit_year():
    assert sessions.contract_label("ES", 2026, 12) == "ESZ26"
    assert sessions.contract_label("CL", 2027, 1) == "CLF27"
    assert sessions.contract_code(datetime(2026, 3, 3, tzinfo=timezone.utc)) == "H"
    assert sessions.parse_symbol("ESZ26") == {"symbol": "ESZ26", "root": "ES", "code": "Z", "year": 2026}
    assert sessions.parse_symbol("GCQ2026")["year"] == 2026
    assert sessions.parse_symbol("ESH6")["year"] == 2006, "no clock to anchor a one-digit year"
    assert sessions.parse_symbol("ESH6", ms(2026, 9, 20, 12))["year"] == 2026, \
        "the decade the caller is standing in, not the one it was written in"
    assert sessions.parse_symbol("BTCUSDT")["root"] == "BTCUSDT"
    assert sessions.parse_symbol("ESZ26")["root"] == sessions.root_of("ESZ26") == "ES"
    assert sessions.root_of("NQZ26") == "NQ"
    assert sessions.root_of("SPY") == "SPY"
    assert sessions.root_of("BTCUSDT") == "BTC", "a venue's perpetual names its root in front"


def test_a_perpetual_has_no_roll_and_funding_instead():
    table = sessions.roll_calendar("BTC", ms(2026, 9, 20, 12, 0), 6)
    assert table["ok"] is True and table["kind"] == "perpetual"
    assert table["contracts"] == [] and table["days_to_roll"] is None
    assert table["rule"] == "no expiry — a perpetual has no roll"
    stamps = [row["at"] for row in table["funding"]]
    assert stamps[:3] == ["2026-09-20 16:00 UTC", "2026-09-21 00:00 UTC", "2026-09-21 08:00 UTC"]
    assert [row["minutes_away"] for row in table["funding"]] == sorted(
        row["minutes_away"] for row in table["funding"]), "nearest first"
    assert all(row["minutes_away"] > 0 for row in table["funding"])
    assert table["hours_to_funding"] == 4.0
    assert sessions.funding_schedule("ES", ms(2026, 9, 20, 12)) == [], "a future has no funding"


def test_an_unknown_root_is_refused_in_a_sentence():
    table = sessions.roll_calendar("ZZZ", ms(2026, 9, 20, 12))
    assert table["ok"] is False and table["kind"] == "unknown"
    assert table["detail"].startswith("no roll rule for ZZZ") and "ES" in table["detail"]
    assert table["contracts"] == []
    assert sessions.contract_months("ZZZ", ms(2026, 9, 20, 12)) == []


def test_the_roll_table_answers_the_configured_roots_in_order():
    settings = sessions.clean({"roots": ["CL", "GC", "ES"], "months": 2})
    tables = sessions.roll_table(settings, ms(2026, 9, 20, 12))
    assert [table["root"] for table in tables] == ["CL", "GC", "ES"]
    assert [len(table["contracts"]) for table in tables] == [2, 2, 2]
    one = sessions.roll_table(settings, ms(2026, 9, 20, 12), root="GC")
    assert [table["root"] for table in one] == ["GC"]
    clamped = sessions.roll_table(sessions.clean({"months": 99}), ms(2026, 9, 20, 12), root="ES")
    assert len(clamped[0]["contracts"]) == 11, \
        "the search runs three years ahead, and the ES cycle is quarterly"


# ── resolution and the route ────────────────────────────────────────────────────────────────────

def test_resolution_prefers_the_symbol_map_then_the_template_s_own_list():
    cfg = {"symbols": {"BTCUSDT": "us-equities-rth"}, "active": "crypto-247"}
    found, how = sessions.template_for("BTCUSDT", cfg)
    assert found["name"] == "us-equities-rth" and "symbol map" in how, "the map is the user's word"
    found, how = sessions.template_for("ESZ26", cfg)
    assert found["name"] == "cme-globex-index" and "symbol list" in how
    found, how = sessions.template_for("spy", cfg)
    assert found["name"] == "us-equities-rth"
    assert sessions.template_for("", cfg) == (None, "")
    assert sessions.template_for("ZQX9", cfg) == (None, "")
    picked, how = sessions.pick_template(cfg, symbol="ZQX9")
    assert picked is None and how == sessions.NO_TEMPLATE % "ZQX9"
    assert "add one in Settings or copy a built-in" in how
    picked, how = sessions.pick_template(cfg)
    assert picked["name"] == "crypto-247" and "active" in how
    picked, how = sessions.pick_template({"templates": [], "active": ""}, template="nothing")
    assert picked is None and "no session template is named nothing" in how


def test_the_payload_answers_the_clock_and_the_roll_table():
    cfg = {"active": "us-equities-rth", "roots": ["ES"], "months": 2, "holidays_ahead": 2}
    data = sessions.payload(symbol="ESZ26", cfg=cfg, at_ms=ms(2026, 9, 21, 14, 0))
    assert data["ok"] is True and data["template"]["name"] == "cme-globex-index"
    assert data["root"] == "ES" and "symbol list" in data["how"]
    assert data["state"]["phase"] == "open" and data["state"]["session_date"] == "2026-09-20"
    assert data["rolls"][0]["root"] == "ES" and data["rolls"][0]["front"] == "ESZ26"
    assert len(data["rolls"][0]["contracts"]) == 2
    assert data["holidays"] == [], \
        "the Globex template carries no holiday rule, so the list is honestly empty"
    assert data["settings"]["active"] == "us-equities-rth"
    assert {row["name"] for row in data["templates"]} >= {"cme-globex-index", "us-equities-rth"}
    assert all(set(sessions.TEMPLATE_KEYS) <= set(row) for row in data["templates"]), \
        "the picker's rows are whole templates, so a copy is a copy"
    cme = [row for row in data["templates"] if row["name"] == "cme-globex-index"][0]
    assert cme["builtin"] is True and cme["active"] is False


def test_the_payload_refuses_a_symbol_with_no_template_and_still_offers_the_library():
    data = sessions.payload(symbol="ZZQQX99", cfg={"active": "crypto-247"}, at_ms=ms(2026, 9, 21, 14))
    assert data["ok"] is False
    assert data["detail"] == "no session template matches ZZQQX99 — add one in Settings or copy a built-in"
    assert data["state"] == {} and data["rolls"] == []
    assert data["templates"], "the list beside the sentence is where the user does it"
    assert data["symbol"] == "ZZQQX99"


def test_the_payload_answers_without_a_symbol_and_by_template_name():
    quiet = sessions.payload(cfg={"active": "crypto-247"}, at_ms=ms(2026, 9, 21, 14))
    assert quiet["ok"] is True and quiet["template"]["name"] == "crypto-247"
    assert [table["root"] for table in quiet["rolls"]] == ["ES", "NQ", "CL", "GC"]
    named = sessions.payload(template="fx-sydney", cfg={}, at_ms=ms(2026, 9, 21, 14))
    assert named["template"]["name"] == "fx-sydney" and "named in the request" in named["how"]
    unknown = sessions.payload(template="nope", cfg={}, at_ms=ms(2026, 9, 21, 14))
    assert unknown["ok"] is False and "no session template is named nope" in unknown["detail"]


def test_the_get_route_answers_the_panel(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(sessions.router)
    monkeypatch.setattr(sessions, "now_ms", lambda: ms(2026, 9, 21, 14, 0))
    monkeypatch.setattr(sessions, "_config", lambda: sessions.clean({"active": "us-equities-rth",
                                                                     "roots": ["ES"], "months": 2}))
    client = TestClient(app)
    answer = client.get("/api/atlas/sessions", params={"symbol": "SPY"})
    assert answer.status_code == 200
    data = answer.json()
    assert data["ok"] is True and data["template"]["name"] == "us-equities-rth"
    assert data["state"]["phase"] == "open" and data["state"]["at_ms"] == ms(2026, 9, 21, 14, 0)
    assert data["rolls"][0]["root"] == "ES"
    refusal = client.get("/api/atlas/sessions", params={"symbol": "ZZQQX99"}).json()
    assert refusal["ok"] is False and refusal["detail"].startswith("no session template matches")


def test_the_route_reads_settings_and_never_writes_them():
    text = MODULE.read_text(encoding="utf-8", errors="replace")
    assert "load_config" in text
    for writer in ("save_config", "merge_config", "default_config"):
        assert writer not in text, f"a GET must never reach {writer}"
    assert '@router.get("/sessions")' in text, "the route the panel calls is gone"
    assert '@router.post' not in text, "this feature declares no write route of its own"


# ── the panel ───────────────────────────────────────────────────────────────────────────────────

def test_the_panel_and_its_selftest_exist_and_parse():
    assert SESSIONS_JS.is_file() and SELFTEST.is_file()
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    for path in (SESSIONS_JS, SELFTEST):
        proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 0, proc.stderr


def test_the_panel_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"sessions selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 20, f"only {found.group(1)} checks ran — the selftest shrank"


def test_the_panel_has_words_for_every_phase_the_server_can_report():
    text = SESSIONS_JS.read_text(encoding="utf-8", errors="replace")
    found = re.search(r"var PHASE_WORDS = \{([^}]*)\}", text)
    assert found, "sessions.js lost its PHASE_WORDS table"
    words = set(re.findall(r"'?([a-z-]+)'?\s*:", found.group(1)))
    assert words == set(sessions.PHASES), (
        f"the panel's phases drifted from atlas/sessions.py: {sorted(words)} != {sorted(sessions.PHASES)}")


def test_the_panel_declares_no_write_route_of_its_own():
    text = SESSIONS_JS.read_text(encoding="utf-8", errors="replace")
    assert "api('/api/atlas/sessions'" in text, "the panel's own GET must be a literal the audit reads"
    posts = re.findall(r"api\('(/api/[^']+)',\s*\{", text)
    assert posts and set(posts) == {"/api/control/config"}, f"the panel posts somewhere new: {posts}"
    assert len(posts) == 2, "two write buttons: activate the template, copy a built-in into my list"


# ── §148 T4-F2/F3/F5: the non-finite number, the shadowing copy, the labelled break ────────────

def test_a_non_finite_number_reads_as_unreadable_never_as_a_crash():
    """A hand-edited `Infinity` must not take the panel down.

    json.loads accepts bare `Infinity`, so `sessions.months` in config.json can hold one. Measured
    before the fix: `clean({"months": float("inf")})` raised OverflowError out of `int()` and every
    GET /api/atlas/sessions answered 500 until the file was hand-edited back. The module's own
    contract — `clean()` never raises — reads an unreadable number as unreadable.
    """
    assert sessions.clean({"months": float("inf")})["months"] == sessions.DEFAULTS["months"]
    assert sessions.clean({"months": float("-inf")})["months"] == sessions.DEFAULTS["months"]
    assert sessions.clean({"holidays_ahead": float("inf")})["holidays_ahead"] == sessions.DEFAULTS["holidays_ahead"]
    assert sessions._clock(float("inf")) == 0, "a clock that cannot be read is the epoch, not a raise"
    assert sessions._int(float("inf"), 7) == 7
    assert sessions.parse_minutes(float("inf")) is None
    assert sessions.parse_minutes(float("nan")) is None
    assert sessions.parse_days(float("inf")) == []
    assert sessions.parse_days([float("inf"), "mon"]) == [1]
    assert sessions.fmt_minutes(float("inf")) == "00:00"
    poisoned = {"active": "crypto-247", "months": float("inf"), "roots": ["ES"],
                "templates": [{"name": "mine", "open": float("inf"), "close": "17:00",
                               "days": float("inf")}]}
    assert sessions.payload(cfg=poisoned)["ok"] is True, "the whole read must survive the poison"


def test_a_break_label_after_the_end_time_is_kept():
    """The documented "12:00-13:00 lunch" shape keeps the break and the label.

    Measured before the fix: the string branch split on maxsplit=1, handed "13:00 lunch" to
    parse_minutes (None) and dropped the whole break — silently; the `len(parts) == 3` label
    branch below it could never run.
    """
    assert sessions.parse_breaks(["12:00-13:00 lunch"]) == [
        {"start": "12:00", "end": "13:00", "label": "lunch"}]
    assert sessions.parse_breaks(["9:00-9:30 pre-open"]) == [
        {"start": "09:00", "end": "09:30", "label": "pre-open"}]
    assert sessions.parse_breaks(["12:00 to 13:00 lunch"]) == [
        {"start": "12:00", "end": "13:00", "label": "lunch"}]
    assert sessions.parse_breaks(["12:00-13:00"]) == [{"start": "12:00", "end": "13:00"}]
    long_label = sessions.parse_breaks(["12:00-13:00 " + "x" * 60])
    assert long_label and len(long_label[0]["label"]) == 40, "the label is bounded like every other"
    assert sessions.parse_breaks(["12:00-noon"]) == [], "an unreadable end is still dropped"


def test_a_user_copy_that_shadows_a_builtin_stays_a_user_row():
    """The panel posts only its non-built-in rows; a shadowing copy must not be flagged built-in.

    Measured before the fix: a config copy named "jp-equities" came back `builtin: True`, so the
    copy flow's filter dropped it and the POST wrote the user's copy out of config.json — with a
    "copied" message and no mention of the loss.
    """
    mine = {"name": "jp-equities", "title": "My own jp-equities", "timezone": "Asia/Tokyo",
            "days": "mon-fri", "open": "09:00", "close": "15:00"}
    rows = sessions.templates_of({"templates": [mine]})
    shadow = next(row for row in rows if row["name"] == "jp-equities")
    assert shadow["builtin"] is False, "the user's copy must not inherit the library row's flag"
    assert shadow["title"] == "My own jp-equities" and shadow["open"] == "09:00"
    assert all(row["builtin"] is True for row in rows if row["name"] != "jp-equities")
    # the panel's own filter (sessions.js templateBlockWith) keeps rows that are not built-ins:
    both = sessions.payload(cfg={"templates": [mine, {"name": "my-hours", "open": "08:00",
                                                      "close": "20:00"}]})
    posted = [row["name"] for row in both["templates"] if row.get("builtin") is not True]
    assert posted == ["jp-equities", "my-hours"], "the copy body must carry the user's rows"


# ── §148 T4-F6/F7/F10: the energy clause, the day letters, the docs' count ──────────────────────

def test_an_energy_expiry_on_a_non_business_day_steps_back_first():
    """§148 T4-F6 — CME Ch.200: when the 25th is not a business day the count starts from the last
    business day before it. CLX26's 25th is a Sunday, so the expiry is 2026-10-20, not the 21st."""
    assert datetime(2026, 10, 25).weekday() == 6, "the clause's premise: that 25th is a Sunday"
    assert datetime(2027, 4, 25).weekday() == 6
    assert sessions.expiry_date("CL", 2026, 11).isoformat() == "2026-10-20"
    assert sessions.expiry_date("CL", 2027, 5).isoformat() == "2027-04-20"      # CLK27
    assert sessions.expiry_date("CL", 2026, 12).isoformat() == "2026-11-20", \
        "a weekday 25th is unchanged by the clause"


def test_a_one_letter_day_is_never_guessed():
    """§148 T4-F7 — "t" resolved to Thursday and "s" to Sunday by the order the names were added."""
    assert sessions.parse_days("t") == [] and sessions.parse_days("s") == []
    assert sessions.parse_days("m,w,f") == [1, 3, 5], "the unambiguous letters still read"
    assert sessions.parse_days("tue") == [2] and sessions.parse_days("thu") == [4]
    assert sessions.parse_days("sat") == [6] and sessions.parse_days("sun") == [7]
    assert sessions.parse_days("m,t,w,th,f") == [1, 3, 4, 5], "and no Thursday for a lone t"


def test_the_upgrade_docs_root_count_matches_the_table():
    """§148 T4-F10 — the doc claimed "17 roots" for a table that carries 18 futures + three perps."""
    doc = (ROOT / "docs" / "UPGRADE_PACKAGE_2026-09.md").read_text(encoding="utf-8", errors="replace")
    futures = [root for root, row in sessions.ROOTS.items() if row.get("family") != "perpetual"]
    perps = [root for root, row in sessions.ROOTS.items() if row.get("family") == "perpetual"]
    assert len(futures) == 18 and perps == ["BTC", "ETH", "SOL"], "the table changed: re-derive the line"
    assert f"{len(futures)} futures roots + the BTC/ETH/SOL perpetuals" in doc
    assert "17 roots" not in doc
