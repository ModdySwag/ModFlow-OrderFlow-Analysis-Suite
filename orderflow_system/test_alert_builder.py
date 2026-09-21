"""The alert condition builder: several readings per rule, and the evidence snapshot on the delivery.

Three things are pinned here, in the order a rule travels.

*The reading* — `conditions` on a rule are evaluated by `evaluate_conditions()`, combined by `match`
('all' | 'any'), and the whole thing is deliberately conservative: a rule with no conditions is met
(that is what keeps every rule written before this existed working), an unknown reading is never met,
a reading the event and the snapshot do not carry is never met, and nothing raises — a market event
arriving mid-tick is not the place to discover a typo in a rule.

*The clock* — `cooldown_s` is the original gate, now scoped per rule or per instrument; the aligned
`once_per_window_s` / `max_per_window` pair is the "once per 5-minute bar" clock, which a sliding
cooldown cannot express.

*The evidence* — `context_block()` renders what triggered the rule as plain text or CSV under a hard
character cap, and it rides the notification instead of dying in the log: `Alert.context` is on every
logged alert, `webhook_payload()` carries it, and every channel appends it with
`notify._with_context` — `notification_text()` is that same render for a whole alert.

Alongside those: `clean()` is the settings block's only door, the JS half of the builder is executed
by its own selftest under plain node with no DOM, and the JS condition catalogue must stay identical
to `CONDITION_KINDS` — the form may not offer a reading the engine does not have, or drop one it
does. That last check is the one that matters most: it is the same shape as the params gate in
`test_alert_format.py`, because a field a form shows and the engine ignores is a lie.
"""

from __future__ import annotations

import csv
import io
import json
import re
import subprocess
from pathlib import Path

import pytest

from orderflow_system.atlas import alerts as A

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
MODULE = UI / "alert-builder.js"
SELFTEST = UI / "alert-builder.selftest.js"
ALERTS_PY = ROOT / "orderflow_system" / "atlas" / "alerts.py"

NOW = 1_770_000_000_000                      # one fixed stamp, so every window in here is arithmetic

#: A sell sweep, the shape `alerts.evaluate()` really receives for that kind.
SWEEP = {"kind": "sweep", "symbol": "btcusdt", "price": 63120.5, "side": "sell", "levels": 7,
         "size": 42.5, "ts_ms": NOW, "multiple": 3.4, "ticks": 11.0, "zscore": 2.8}

#: A snapshot in `ContextBuffer.ctx()`'s own shape: prints in, levels in, session in, delta out.
SNAPSHOT = {
    "symbol": "BTCUSDT", "window_ms": 60_000, "now_ms": NOW, "last_price": 63118.0,
    "delta": {"window_ms": 60_000, "end_ms": NOW, "prints": 5, "buy": 3.25, "sell": 57.75,
              "value": -54.5, "unknown": 0, "buy_pct": 5.0, "sell_pct": 95.0},
    "prints": [
        {"ts_ms": NOW - 40_000, "price": 63100.0, "size": 2.0, "side": "buy"},
        {"ts_ms": NOW - 30_000, "price": 63105.0, "size": 6.5, "side": "sell"},
        {"ts_ms": NOW - 20_000, "price": 63110.0, "size": 1.25, "side": "buy"},
        {"ts_ms": NOW - 10_000, "price": 63115.0, "size": 9.0, "side": "sell"},
        {"ts_ms": NOW - 1_000, "price": 63120.5, "size": 42.5, "side": "sell"},
    ],
    "levels": [{"price": 63000.0, "size": 140.0, "side": "bid"},
               {"price": 63250.0, "size": 96.5, "side": "ask"},
               {"price": 63200.0, "size": 12.0, "side": "ask"}],
    "session": {"name": "us", "state": "open", "minutes_in": 125, "vwap": 63090.0,
                "range_low": 62800.0, "range_high": 63250.0},
}

#: A rule the way rules were written before any of this existed: one kind and its params.
LEGACY = {"id": "legacy-sweep", "name": "Big sell sweep", "kind": "sweep",
          "params": {"min_levels": 5}, "cooldown_s": 30, "channels": ["ui"]}


def _settings(**over: object) -> dict[str, object]:
    return A.clean(over)


def _rule(**over: object) -> dict[str, object]:
    rule = {"id": "r1", "name": "sweep with a condition", "kind": "sweep", "channels": ["ui"]}
    rule.update(over)
    return rule


# ── the settings block ────────────────────────────────────────────────────────────────────────────

def test_defaults_are_the_documented_block():
    assert A.DEFAULTS["context_enabled"] is True
    assert A.DEFAULTS["context_format"] == "text"
    assert A.DEFAULTS["context_max_chars"] == 360
    assert A.DEFAULTS["context_prints"] == 3
    assert A.DEFAULTS["context_levels"] == 3
    assert A.DEFAULTS["context_window_ms"] == 60_000
    assert list(A.DEFAULTS["context_channels"]) == ["telegram", "ntfy", "email", "webhook"]
    assert A.DEFAULTS["max_conditions"] == 8
    assert A.MAX_CONDITIONS == 12


def test_clean_returns_only_this_block_and_never_raises():
    for junk in (None, "", 7, [], {"nope": 1}, object()):
        out = A.clean(junk)
        assert set(out) == set(A.DEFAULTS), "clean() returns exactly this feature's block"
    assert A.clean({"max_conditions": 99})["max_conditions"] == A.MAX_CONDITIONS
    assert A.clean({"max_conditions": -4})["max_conditions"] == 0
    assert A.clean({"max_conditions": "abc"})["max_conditions"] == A.DEFAULTS["max_conditions"]
    assert A.clean({"context_max_chars": 10})["context_max_chars"] == 40
    assert A.clean({"context_max_chars": 99_999})["context_max_chars"] == 2_000
    assert A.clean({"context_prints": -3})["context_prints"] == 0
    assert A.clean({"context_prints": 40})["context_prints"] == 10
    assert A.clean({"context_levels": 40})["context_levels"] == 10
    assert A.clean({"context_window_ms": 10})["context_window_ms"] == 1_000
    assert A.clean({"context_window_ms": 10_000_000})["context_window_ms"] == 3_600_000
    assert A.clean({"context_format": "yaml"})["context_format"] == "text"
    # A word this app understands is read, not defaulted away; only a word it does not is ignored.
    assert A.clean({"context_enabled": "off"})["context_enabled"] is False
    assert A.clean({"context_enabled": "no"})["context_enabled"] is False
    assert A.clean({"context_enabled": "yes"})["context_enabled"] is True
    assert A.clean({"context_enabled": "maybe"})["context_enabled"] is True
    assert A.clean({"context_enabled": False})["context_enabled"] is False
    # An unknown channel is dropped, a string is not iterated character by character.
    assert A.clean({"context_channels": "telegram"})["context_channels"] == ["telegram"]
    assert A.clean({"context_channels": ["telegram", "carrier-pigeon"]})["context_channels"] == \
        ["telegram"]
    assert A.clean({"context_channels": []})["context_channels"] == []


def test_clean_hands_out_its_own_lists():
    """A caller mutating what clean() returned must not be able to edit the defaults."""
    out = A.clean({})
    out["context_channels"].append("ui")
    assert list(A.DEFAULTS["context_channels"]) == ["telegram", "ntfy", "email", "webhook"]


# ── conditions: the truth tables ──────────────────────────────────────────────────────────────────

def test_a_rule_with_no_conditions_is_met():
    """The whole compatibility story, in one assertion."""
    assert A.conditions_of(LEGACY) == []
    assert A.evaluate_conditions(A.AlertRule.from_dict(LEGACY), SWEEP, SNAPSHOT) is True
    assert A.evaluate_conditions({}, None, None) is True


def test_all_needs_every_condition_and_any_needs_one():
    met = {"kind": "side", "op": "==", "value": "sell"}
    unmet = {"kind": "delta", "op": ">", "value": 10_000}
    both = {"kind": "delta", "op": "<=", "value": 0}
    assert A.evaluate_conditions(_rule(match="all", conditions=[met, both]), SWEEP, SNAPSHOT) is True
    assert A.evaluate_conditions(_rule(match="all", conditions=[met, unmet]), SWEEP, SNAPSHOT) is False
    assert A.evaluate_conditions(_rule(match="any", conditions=[met, unmet]), SWEEP, SNAPSHOT) is True
    assert A.evaluate_conditions(_rule(match="any", conditions=[unmet]), SWEEP, SNAPSHOT) is False
    assert A.match_of(_rule(match="sometimes")) == "all"
    assert A.match_of(_rule(match="ANY")) == "any"


def test_an_unknown_or_unreadable_condition_is_never_met_and_never_raises():
    event, ctx = SWEEP, SNAPSHOT
    assert A.evaluate_condition({"kind": "nonsense", "op": ">", "value": 1}, event, ctx) is False
    assert A.evaluate_condition({"kind": "delta"}, event, ctx) is False          # no op, no value
    assert A.evaluate_condition("delta > 1", event, ctx) is False                # not a dict
    assert A.evaluate_condition(None, event, ctx) is False
    # A reading the event does not carry cannot be met, however the rule is written.
    assert A.evaluate_condition({"kind": "size", "op": ">", "value": 1}, {}, {}) is False
    assert A.evaluate_condition({"kind": "tape_speed", "op": ">", "value": 1}, event, {}) is False
    # And an unknown reading poisons an AND but not an OR — the honest reading of each mode.
    unknown = {"kind": "nonsense", "op": ">", "value": 1}
    assert A.evaluate_conditions(_rule(match="all", conditions=[unknown]), event, ctx) is False
    assert A.evaluate_conditions(_rule(match="any", conditions=[unknown]), event, ctx) is False


def test_every_condition_kind_refuses_politely_on_an_empty_market():
    """No resolver may raise, whatever it is handed — the engine runs inside the tick path."""
    junk = [None, {}, "", 0, [], {"price": "abc"}, {"prints": "not a list"}, {"delta": object()}]
    for kind in A.CONDITION_KINDS:
        for event in junk:
            for ctx in junk:
                assert A.evaluate_condition({"kind": kind, "op": ">", "value": 1}, event, ctx) is False
                assert A.evaluate_condition({"kind": kind, "op": "in", "value": [1]}, event, ctx) is False


def test_comparisons_are_numeric_for_numbers_and_worded_for_words():
    delta = {"value": -412.5, "buy": 100.0, "sell": 512.5}
    ctx = dict(SNAPSHOT, delta=delta)
    assert A.evaluate_condition({"kind": "delta", "op": "<=", "value": -300}, SWEEP, ctx) is True
    assert A.evaluate_condition({"kind": "delta", "op": ">=", "value": -300}, SWEEP, ctx) is False
    assert A.evaluate_condition({"kind": "delta", "op": "==", "value": -412.5}, SWEEP, ctx) is True
    assert A.evaluate_condition({"kind": "delta", "op": "!=", "value": -412.5}, SWEEP, ctx) is False
    assert A.evaluate_condition({"kind": "delta", "op": "in", "value": [-500, -412.5]}, SWEEP, ctx) is True
    assert A.evaluate_condition({"kind": "delta", "op": "not_in", "value": [-500]}, SWEEP, ctx) is True
    # A string that happens to be a number still compares as a number: rule bodies come from JSON.
    assert A.evaluate_condition({"kind": "delta", "op": "<=", "value": "-300"}, SWEEP, ctx) is True
    # An op that does not belong to the class is False, not an exception.
    assert A.evaluate_condition({"kind": "delta", "op": "~", "value": 1}, SWEEP, ctx) is False
    assert A.evaluate_condition({"kind": "side", "op": ">", "value": "buy"}, SWEEP, SNAPSHOT) is False
    assert A.evaluate_condition({"kind": "side", "op": "==", "value": "SELL"}, SWEEP, SNAPSHOT) is True
    assert A.evaluate_condition({"kind": "side", "op": "!=", "value": "buy"}, SWEEP, SNAPSHOT) is True
    assert A.evaluate_condition({"kind": "side", "op": "in", "value": ["buy", "sell"]}, SWEEP, SNAPSHOT) is True
    # The book's word for a resting side is not the tape's word for an aggressor.
    assert A.evaluate_condition({"kind": "side", "op": "==", "value": "ask"},
                                {"side": "sell"}, {}) is True


def test_the_field_readings_need_a_field_and_read_the_one_they_are_given():
    event = {"multiple": 3.4, "venue": "binance", "ts_ms": NOW}
    assert A.evaluate_condition({"kind": "field", "op": ">", "value": 3}, event, {}) is False
    assert A.evaluate_condition({"kind": "field", "op": ">", "value": 3}, event,
                                {"params": {}}) is False
    assert A.evaluate_condition({"kind": "field", "op": ">", "value": 3, "params": {"field": "multiple"}},
                                event, {}) is True
    assert A.evaluate_condition({"kind": "ctx_field", "op": ">", "value": 100_000,
                                 "params": {"field": "now_ms"}}, event, {"now_ms": NOW}) is True
    assert A.evaluate_condition({"kind": "text_field", "op": "==", "value": "binance",
                                 "params": {"field": "venue"}}, event, {}) is True
    # A named reading the event simply does not have is not met, and does not fall over.
    assert A.evaluate_condition({"kind": "field", "op": ">", "value": 1,
                                 "params": {"field": "missing"}}, event, {}) is False


def test_conditions_of_keeps_every_authored_entry_and_respects_the_cap():
    """AB-02 (§148) — the quarantine half: nothing authored is dropped.

    The old reading kept only dicts and read every other value as "no conditions", so a typo made
    a rule LOUDER. A non-dict entry now survives as a condition that can never be met (carrying
    the authored entry itself, so a save round-trips the author's text), and a lone condition
    object is read as the one condition it is."""
    conds = [{"kind": "side", "op": "==", "value": "sell"}] * (A.MAX_CONDITIONS + 5)
    assert len(A.conditions_of({"conditions": conds})) == A.MAX_CONDITIONS
    valid = {"kind": "side", "op": "==", "value": "buy"}
    kept = A.conditions_of({"conditions": ["nope", None, 7, valid]})
    assert len(kept) == 4, "every authored entry is kept — nothing is silently dropped"
    assert kept[-1] == valid
    assert [row["unreadable"] for row in kept[:3]] == ["a string", "null", "a number"]
    assert [row["entry"] for row in kept[:3]] == ["nope", None, 7], "the authored entry is preserved"
    assert A.evaluate_conditions({"conditions": ["nope"]}, SWEEP, SNAPSHOT) is False
    assert A.conditions_of({"conditions": valid}) == [valid]
    assert A.conditions_of({"conditions": "sell"})[0]["unreadable"] == "a string"
    assert A.conditions_of(None) == []
    assert A.conditions_of(A.AlertRule.from_dict(_rule(conditions=conds))) == conds[:A.MAX_CONDITIONS]


def test_a_malformed_conditions_value_quiets_the_rule_instead_of_loosening_it():
    """AB-02 (§148): the old reading dropped what it could not parse, so a rule authored with
    ``conditions: "junk"`` evaluated as if it had no conditions at all — it fired LOUDER than
    written. A condition may only ever make a rule quieter: the malformed entry is quarantined as
    one that can never be met, the live engine refuses the event, and the rehearsal says why."""
    engine = A.AlertEngine([_rule(params={})], history=50)
    engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)          # one real event in the log

    malformed = {"id": "bad", "name": "bad", "kind": "sweep", "enabled": True,
                 "conditions": "junk", "cooldown_s": 0, "channels": ["ui"]}
    answer = engine.test_fire(malformed)
    assert answer["ok"] is True and answer["fires"] is False
    assert answer["conditions"] and answer["conditions"][0]["met"] is False
    assert "not a condition" in answer["conditions"][0]["why"]
    # The live engine refuses the same event for the same rule: nothing fires, nothing recorded.
    live = A.AlertEngine([dict(malformed)], history=5)
    assert live.evaluate("BTCUSDT", "sweep", SWEEP, NOW) == [] and live.history == []

    # A list mixing junk with real readings: the junk stays as a never-met entry (so `match: all`
    # can never fire) and the real reading gates the rule as written.
    mixed = dict(malformed, conditions=["junk", {"kind": "side", "op": "==", "value": "sell"}])
    assert A.evaluate_conditions(mixed, SWEEP, SNAPSHOT) is False
    assert A.evaluate_conditions(dict(mixed, match="any"), SWEEP, SNAPSHOT) is True

    # A single condition object (not wrapped in a list) is read as the one condition it is.
    single = dict(malformed, conditions={"kind": "side", "op": "==", "value": "sell"})
    assert [row["met"] for row in A.condition_results(single, SWEEP, SNAPSHOT)] == [True]
    assert engine.test_fire(dict(single, id="one"))["fires"] is True

    # The author's own text survives a save round trip — quarantined, not erased.
    assert A.AlertRule.from_dict(malformed).to_dict()["conditions"][0]["entry"] == "junk"


def test_the_settings_cap_can_turn_conditions_off_entirely():
    """`max_conditions: 0` is the switch to reach for when a rule set is behaving oddly."""
    rule = _rule(conditions=[{"kind": "side", "op": "==", "value": "buy"}])
    assert A.evaluate_conditions(rule, SWEEP, SNAPSHOT, _settings()) is False
    assert A.evaluate_conditions(rule, SWEEP, SNAPSHOT, _settings(max_conditions=0)) is True
    # The cap truncates rather than reorders: the first N readings are the ones evaluated.
    three = [{"kind": "side", "op": "==", "value": "sell"},
             {"kind": "levels", "op": ">=", "value": 5},
             {"kind": "size", "op": ">=", "value": 1_000}]
    assert A.evaluate_conditions(_rule(conditions=three), SWEEP, SNAPSHOT, _settings(max_conditions=2)) is True
    assert A.evaluate_conditions(_rule(conditions=three), SWEEP, SNAPSHOT, _settings(max_conditions=3)) is False
    # A settings block that is not a dict is ignored rather than fatal — every condition counts.
    assert A.evaluate_conditions(_rule(conditions=three), SWEEP, SNAPSHOT, "nope") is False
    assert A.evaluate_conditions(_rule(conditions=three[:2]), SWEEP, SNAPSHOT, "nope") is True


def test_condition_results_are_words_a_reader_can_check():
    rule = _rule(conditions=[{"kind": "side", "op": "==", "value": "sell"},
                             {"kind": "delta", "op": ">", "value": 10}])
    rows = A.condition_results(rule, SWEEP, SNAPSHOT, _settings())
    assert [row["met"] for row in rows] == [True, False]
    assert rows[0]["label"] == "Side" and rows[0]["read"] == "sell"
    assert rows[1]["why"] == "read but did not match"
    unknown = A.condition_results(_rule(conditions=[{"kind": "ghost", "op": ">", "value": 1}]),
                                  SWEEP, SNAPSHOT)
    assert unknown[0]["met"] is False and "no condition called 'ghost'" in unknown[0]["why"]
    missing = A.condition_results(_rule(conditions=[{"kind": "size", "op": ">", "value": 1}]), {}, {})
    assert missing[0]["read"] is None and "carry no size reading" in missing[0]["why"]


def test_the_condition_catalogue_describes_itself_for_a_form():
    rows = A.condition_kinds()
    assert [row["kind"] for row in rows] == list(A.CONDITION_KINDS), \
        "the catalogue keeps the engine's own order, so the form's list does not shuffle"
    for row in rows:
        assert set(row) == {"kind", "label", "unit", "value", "source", "hint", "ops"}
        assert row["value"] in ("number", "text")
        assert row["source"] in ("event", "ctx", "either")
        assert row["label"] and row["hint"], "a form row with no words is not usable"
        assert row["ops"] == list(A.NUM_OPS if row["value"] == "number" else A.TEXT_OPS)


# ── the clock: cooldown, scope, once-per-window ───────────────────────────────────────────────────

def test_cooldown_holds_a_rule_back_and_then_releases_it():
    engine = A.AlertEngine([dict(LEGACY)], history=50)
    assert len(engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)) == 1
    assert engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + 5_000) == []
    assert engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + 29_999) == []
    assert len(engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + 30_000)) == 1


def test_a_zero_cooldown_means_every_qualifying_event():
    rule = dict(LEGACY, cooldown_s=0)
    engine = A.AlertEngine([rule], history=50)
    for step in range(5):
        assert len(engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + step * 1_000)) == 1


def test_the_cooldown_can_be_counted_per_instrument():
    """The case this exists for: a busy symbol must not mute a quiet one."""
    per_rule = A.AlertEngine([dict(LEGACY)], history=50)
    assert len(per_rule.evaluate("BTCUSDT", "sweep", SWEEP, NOW)) == 1
    assert per_rule.evaluate("ETHUSDT", "sweep", SWEEP, NOW + 1_000) == []

    per_symbol = A.AlertEngine([dict(LEGACY, cooldown_scope="symbol")], history=50)
    assert len(per_symbol.evaluate("BTCUSDT", "sweep", SWEEP, NOW)) == 1
    assert len(per_symbol.evaluate("ETHUSDT", "sweep", SWEEP, NOW + 1_000)) == 1
    assert per_symbol.evaluate("ETHUSDT", "sweep", SWEEP, NOW + 2_000) == []


def test_an_unknown_cooldown_scope_reads_as_the_rule_wide_one():
    assert A.AlertRule.from_dict(dict(LEGACY, cooldown_scope="galaxy")).cooldown_scope == "rule"
    assert A.AlertRule.from_dict(dict(LEGACY, cooldown_scope="SYMBOL")).cooldown_scope == "symbol"
    assert A.COOLDOWN_SCOPES == ("rule", "symbol")


def test_once_per_window_is_aligned_not_sliding():
    """One fire per five-minute bar: the next bar fires, the seconds after it does not."""
    window = 300
    rule = dict(LEGACY, cooldown_s=0, once_per_window_s=window, max_per_window=1)
    engine = A.AlertEngine([rule], history=50)
    start = NOW - (NOW % (window * 1000))
    assert len(engine.evaluate("BTCUSDT", "sweep", SWEEP, start + 1_000)) == 1
    assert engine.evaluate("BTCUSDT", "sweep", SWEEP, start + 299_000) == []
    assert len(engine.evaluate("BTCUSDT", "sweep", SWEEP, start + 300_000)) == 1
    assert engine.evaluate("BTCUSDT", "sweep", SWEEP, start + 301_000) == []


def test_max_per_window_allows_that_many_and_no_more():
    rule = dict(LEGACY, cooldown_s=0, once_per_window_s=60, max_per_window=2)
    engine = A.AlertEngine([rule], history=50)
    fired = [len(engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + step * 1_000)) for step in range(3)]
    assert fired == [1, 1, 0]
    assert len(engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + 61_000)) == 1


def test_a_rule_saved_with_a_nonsense_window_is_read_as_the_nearest_sane_thing():
    rule = A.AlertRule.from_dict(dict(LEGACY, once_per_window_s=-5, max_per_window=0))
    assert rule.once_per_window_s == 0.0
    assert rule.max_per_window == 1
    assert A.AlertRule.from_dict(dict(LEGACY, once_per_window_s="300")).once_per_window_s == 300.0


def test_the_fire_state_grows_with_instruments_not_events():
    """A per-instrument clock is one key per instrument however busy the symbol gets."""
    engine = A.AlertEngine([dict(LEGACY, cooldown_s=0, cooldown_scope="symbol")], history=20)
    for step in range(200):
        engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + step * 1_000)
    assert len(engine._last_fire) == 1, "200 events on one instrument are one clock"
    for step in range(40):
        engine.evaluate(f"SYM{step}", "sweep", SWEEP, NOW + step * 1_000)
    assert len(engine._last_fire) == 41, "one key per instrument, never one per event"
    assert len(engine.history) <= 20, "the log is capped as it always was"


def test_removing_a_rule_takes_its_clock_with_it():
    engine = A.AlertEngine([dict(LEGACY), _rule(conditions=[{"kind": "side", "op": "==", "value": "sell"}])],
                           history=50)
    engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    assert engine._last_fire
    remaining = engine.remove("legacy-sweep")
    assert [rule["id"] for rule in remaining] == ["r1"]
    assert "legacy-sweep" not in engine._last_fire, "a deleted rule leaves no clock behind"
    assert engine.remove("r1") == []
    assert engine._last_fire == {}


# ── the evidence block ────────────────────────────────────────────────────────────────────────────

def test_the_block_says_what_fired_and_what_the_market_was_doing():
    block = A.context_block(SWEEP, SNAPSHOT, A.clean({"context_max_chars": 2_000}), "sweep")
    assert re.search(r"\d\d:\d\d:\d\d · BTCUSDT · 63,120.50", block), block
    assert "sweep — SELL" in block, "the trigger line is the event's own numbers"
    assert "delta 40s of 60s: -54.50 (buy 5% / sell 95%)" in block
    assert "prints:" in block, "the biggest prints in the window"
    assert "walls:" in block, "the nearest resting levels"
    assert "session: us" in block and "vwap 63,090.00" in block
    assert "range 62,800.00–63,250.00" in block
    assert "tape 5 prints in 40s of 60s" in block, "below one print a second, the count is the honest form"
    assert all(len(line) >= 1 for line in block.splitlines())


def test_the_same_block_at_the_shipped_cap_drops_lines_rather_than_printing_half_a_row():
    default_cap = A.context_block(SWEEP, SNAPSHOT, A.clean({}), "sweep")
    assert len(default_cap) <= A.DEFAULTS["context_max_chars"]
    assert "+" in default_cap and "more" in default_cap, "a capped block says what it left out"
    for line in default_cap.splitlines():
        assert not line.endswith("…"), "whole lines, never a cut-off number"


def test_the_block_never_exceeds_its_cap_in_either_format():
    for fmt in A.CONTEXT_FORMATS:
        for cap in (40, 90, 200, 360, 1_000, 2_000):
            cfg = A.clean({"context_format": fmt, "context_max_chars": cap})
            block = A.context_block(SWEEP, SNAPSHOT, cfg, "sweep")
            assert len(block) <= cap, (fmt, cap, len(block))
    # A cap too small for one line still says something rather than nothing.
    tiny = A.context_block(SWEEP, SNAPSHOT, A.clean({"context_max_chars": 40}), "sweep")
    assert tiny and len(tiny) <= 40
    assert tiny.endswith("…") or "+" in tiny, "cut short, but honest about it"


def test_a_block_keeps_its_first_line_when_the_note_cannot_fit_beside_it():
    """AB-03 (§148): at a legal cap (40) the cap loop could make room for the ``+N more`` note by
    dropping EVERY line — the block came back "" and the panel's own fallback then claimed "the
    snapshot was empty", for an event the snapshot covered. With rows to show, an empty block is
    never an answer: the first line rides, marked."""
    # unit: a 33-char first line + more rows at cap 40 — the note cannot fit beside it.
    out = A._cap_lines(["x" * 33, "second", "third"], 40)
    assert out and len(out) <= 40, out
    assert out.endswith("…") or "+" in out, "marked as incomplete, never silently empty"
    # end-to-end: the same shape through the real block, the first line coming from the event.
    block = A.context_block(dict(SWEEP, price=1_234_567.89), SNAPSHOT,
                            A.clean({"context_max_chars": 40}), "sweep")
    assert block, "the block was dropped exactly because it had something to say"
    assert len(block) <= 40 and (block.endswith("…") or "+" in block)
    assert re.match(r"\d\d:\d\d:\d\d · BTCUSDT · 1,234,567\.89…$", block), block
    # rows that do not exist still answer "" — the true "the snapshot was empty" case stays honest.
    assert A._cap_lines([], 40) == "" and A._cap_lines(["   ", ""], 40) == ""


def test_a_builder_failure_says_so_rather_than_claiming_an_empty_snapshot():
    """§148 follow-up (the docs batch): the crash fallback returned "" — which every reader renders
    as "the snapshot was empty for this event", a claim about the market where the truth is a fault
    in this code. A failure now carries its own sentence, and "" stays reserved for the genuine
    empty block (``_cap_lines([])``)."""
    real = A._block_sections

    def boom(*_args, **_kwargs):
        raise RuntimeError("row builder down")

    A._block_sections = boom
    try:
        for fmt in A.CONTEXT_FORMATS:
            cfg = A.clean({"context_format": fmt,
                           "context_max_chars": A.DEFAULTS["context_max_chars"]})
            block = A.context_block(SWEEP, SNAPSHOT, cfg, "sweep")
            assert block == A.BLOCK_FAILED, (fmt, block)
            assert len(block) <= A.DEFAULTS["context_max_chars"]
        # The smallest legal cap (40) still respects the cap — the sentence fits it whole.
        tiny = A.context_block(SWEEP, SNAPSHOT, A.clean({"context_max_chars": 40}), "sweep")
        assert tiny == A.BLOCK_FAILED and len(tiny) <= 40
    finally:
        A._block_sections = real
    # A healthy builder is untouched, and "" is still the genuine-empty answer.
    assert A.context_block(SWEEP, SNAPSHOT, A.clean({}), "sweep") != A.BLOCK_FAILED
    assert A._cap_lines([], 40) == ""


def test_the_block_is_csv_when_asked_for_csv():
    cfg = A.clean({"context_format": "csv", "context_max_chars": 2_000})
    block = A.context_block(SWEEP, SNAPSHOT, cfg, "sweep")
    assert block.splitlines()[0] == "section,key,value"
    assert 'head,symbol,BTCUSDT' in block
    assert 'head,price,"63,120.50"' in block, "a value with a comma of its own is quoted"
    assert "trigger,kind,sweep" in block
    assert "trigger,line," in block, "the composed trigger line rides in the CSV too"
    assert "wall,1," in block and "print,1," in block
    assert "delta,value,-54.50" in block and "session,state,us" in block
    assert len(block.splitlines()) > 10
    # Four columns never appear: the long form is still three, whatever the value holds.
    for line in block.splitlines():
        assert len(re.findall(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", line)) == 2, line


def test_the_block_reads_the_counts_the_rule_asked_for():
    cfg = A.clean({"context_prints": 1, "context_levels": 0, "context_max_chars": 2_000})
    block = A.context_block(SWEEP, SNAPSHOT, cfg, "sweep")
    assert "prints:" in block and "walls:" not in block
    assert block.count("63,120.50 × 42.50") == 1, block


def test_a_block_with_nothing_to_say_is_still_a_string():
    """The honest answer for a rule with no snapshot provider and a bare event — never an error."""
    for event in (None, {}, "", 7, [1, 2]):
        for ctx in (None, {}, "", [], {"prints": "junk"}):
            block = A.context_block(event, ctx, A.clean({}), "sweep")
            assert isinstance(block, str)
            assert len(block) <= A.DEFAULTS["context_max_chars"]
    assert A.context_block({"kind": "sweep", "symbol": "BTCUSDT", "price": 1.0, "ts_ms": NOW},
                           None, A.clean({}), "sweep"), "an event alone still names itself"
    assert A.context_block(SWEEP, SNAPSHOT, "junk", "")          # a bad cfg falls back to DEFAULTS


def test_the_block_never_invents_a_reading_the_snapshot_does_not_have():
    bare = A.context_block(SWEEP, {"symbol": "BTCUSDT"}, A.clean({}), "sweep")
    assert "delta" not in bare and "walls" not in bare and "prints" not in bare
    assert "session" not in bare
    assert "sweep" in bare, "the event is always there — that part is not a guess"


def test_nearest_levels_and_biggest_prints_are_ordered_by_distance_and_size():
    levels = A.nearest_levels(SNAPSHOT["levels"], 63_120.5, 3)
    assert [row["price"] for row in levels] == [63_200.0, 63_000.0, 63_250.0], \
        "nearest first: 79.5t, then 120.5t, then the 129.5t wall"
    assert [row["distance_ticks"] for row in levels] == [79.5, 120.5, 129.5]
    assert [row["side"] for row in levels] == ["ask", "bid", "ask"]
    assert len(A.nearest_levels(SNAPSHOT["levels"], 63_120.5, 2)) == 2
    assert A.nearest_levels([], 1.0, 3) == []
    assert A.nearest_levels("junk", 1.0, 3) == []
    assert A.nearest_levels(SNAPSHOT["levels"], None, 3), "with no reference price it still lists them"
    picks = A.biggest_prints(SNAPSHOT["prints"], 2, 60_000, NOW)
    assert sorted(row["size"] for row in picks) == [9.0, 42.5], "the two biggest in the window"
    assert [row["ts_ms"] for row in picks] == sorted(row["ts_ms"] for row in picks), \
        "returned in tape order, not size order — the tape reads left to right"
    assert A.biggest_prints(SNAPSHOT["prints"], 0, 60_000, NOW) == []
    assert A.biggest_prints(SNAPSHOT["prints"], 2, 1_000, NOW) == [], \
        "the window is respected, not just the count"


def test_the_window_really_ends_at_its_end_stamp():
    """AB-04 (§148): the window is documented as ending at ``end_ms``, but only its lower bound was
    held — the filter kept every print after the end too, so a snapshot held NOW read against an
    older event dragged the whole current tape into the old window."""
    old = NOW - 120_000
    rows = [{"ts_ms": NOW - 150_000, "price": 1.0, "size": 1.0, "side": "buy"},
            {"ts_ms": NOW - 130_000, "price": 1.0, "size": 2.0, "side": "sell"},
            {"ts_ms": old + 5_000, "price": 1.0, "size": 4.0, "side": "buy"},
            {"ts_ms": NOW - 1_000, "price": 1.0, "size": 8.0, "side": "sell"}]
    window, end = A._windowed(rows, 60_000, old)
    assert end == old
    assert [row["size"] for row in window] == [1.0, 2.0], "prints after the end are not in it"
    delta = A.window_delta(rows, 60_000, old)
    assert (delta["prints"], delta["value"]) == (2, -1.0)
    assert [row["size"] for row in A.biggest_prints(rows, 3, 60_000, old)] == [1.0, 2.0]


def test_a_print_row_is_cleaned_before_it_is_read():
    """Feeds hand over what the venue gave them: seconds, strings, unknown sides, gaps."""
    rows = A._print_rows([{"ts": (NOW // 1000) - 5, "price": "63100.0", "size": "3", "side": "unknown"},
                          {"ts_ms": NOW, "price": 63101.0},
                          {"ts_ms": None, "price": 63102.0},
                          "junk", None])
    assert len(rows) == 2
    assert rows[0]["ts_ms"] == (NOW // 1000 - 5) * 1000, "a seconds stamp is read as seconds"
    assert rows[0]["side"] == "" and rows[1]["size"] == 0.0


# ── the delivery path ─────────────────────────────────────────────────────────────────────────────

def test_a_legacy_rule_fires_exactly_as_before_and_carries_no_block():
    engine = A.AlertEngine([dict(LEGACY)], history=50)
    alerts = engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.context == ""
    assert alert.rule_id == "legacy-sweep" and alert.kind == "sweep"
    assert alert.message and alert.severity == "warning" and alert.channels == ["ui"]
    assert alert.data["price"] == SWEEP["price"]
    assert alert.to_dict()["context"] == ""


def test_a_rule_that_asks_for_a_block_gets_one_on_its_alert():
    engine = A.AlertEngine([_rule(channels=["telegram"], context={})], history=50,
                           settings=_settings())
    engine.context_provider = lambda symbol: SNAPSHOT
    alert = engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0]
    assert "BTCUSDT" in alert.context and "sweep — SELL" in alert.context
    assert engine.context_blocks == 1
    assert alert.to_dict()["context"] == alert.context


def test_the_module_switch_and_the_channel_list_can_both_hold_a_block_back():
    rule = _rule(channels=["telegram"], context={})
    off = A.AlertEngine([rule], history=50, settings=_settings(context_enabled=False))
    off.context_provider = lambda symbol: SNAPSHOT
    assert off.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0].context == ""

    # The app already has the event on screen, so the UI log is not where a snapshot is useful.
    ui_only = A.AlertEngine([_rule(channels=["ui"], context={})], history=50)
    ui_only.context_provider = lambda symbol: SNAPSHOT
    assert ui_only.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0].context == ""

    # A rule in the context's own channel list gets it; one outside both does not.
    narrowed = A.AlertEngine([rule], history=50, settings=_settings(context_channels=["ntfy"]))
    narrowed.context_provider = lambda symbol: SNAPSHOT
    assert narrowed.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0].context == ""
    assert A.context_config(rule, _settings())["enabled"] is True
    assert A.context_config(rule, _settings(context_enabled=False))["enabled"] is False
    assert A.context_config(dict(LEGACY), _settings())["enabled"] is False, "no key, no block"
    assert A.context_config(_rule(context=False), _settings())["enabled"] is False


def test_the_rule_can_override_the_block_without_touching_the_module_settings():
    cfg = A.context_config(_rule(context={"format": "csv", "max_chars": 500, "prints": 1}),
                           _settings())
    assert cfg["enabled"] is True and cfg["context_format"] == "csv"
    assert cfg["context_max_chars"] == 500 and cfg["context_prints"] == 1
    assert A.context_config(_rule(context=True), _settings())["enabled"] is True
    assert A.context_config(_rule(context={"max_chars": 5}), _settings())["context_max_chars"] == 40
    assert A.context_config(_rule(context={"enabled": False}), _settings())["enabled"] is False


def test_every_channel_can_carry_the_block():
    """The four paths a notification leaves by, all formatted from one function."""
    engine = A.AlertEngine([_rule(channels=["telegram", "ntfy", "email", "webhook"], context={})],
                           history=50)
    engine.context_provider = lambda symbol: SNAPSHOT
    alert = engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0]
    payload = engine.webhook_payload(alert)
    assert payload["source"] == "orderflow-analysis-pro" and payload["type"] == "orderflow_alert"
    assert payload["context"] == alert.context and payload["kind"] == "sweep"
    assert payload["message"] == alert.message
    text = A.notification_text(alert)
    assert text.startswith(alert.message) and text.endswith(alert.context)
    assert A.notification_text(payload) == text, "the webhook body says the same thing"
    assert A.notification_text({"message": "only a sentence"}) == "only a sentence"
    assert A.notification_text(None) == ""
    assert json.dumps(payload) is not None, "the payload must stay JSON-serialisable"


def test_a_provider_that_falls_over_does_not_take_the_alert_with_it():
    """Losing the snapshot costs the block its readings, never the alert."""
    engine = A.AlertEngine([_rule(channels=["telegram"], context={})], history=50)

    def broken(symbol: str) -> dict[str, object]:
        raise RuntimeError("the feed died")

    engine.context_provider = broken
    alerts = engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    assert len(alerts) == 1
    assert alerts[0].context, "the event's own evidence is still there"
    assert "sweep — SELL" in alerts[0].context
    assert "walls:" not in alerts[0].context and "session:" not in alerts[0].context, \
        "and nothing the dead provider would have carried is invented"


def test_the_snapshot_provider_is_only_asked_when_something_wants_one():
    """Twenty-four shipped rules cost nothing for a feature none of them use."""
    asked: list[str] = []

    def provider(symbol: str) -> dict[str, object]:
        asked.append(symbol)
        return SNAPSHOT

    plain = A.AlertEngine([dict(LEGACY, channels=["telegram"])], history=50)
    plain.context_provider = provider
    plain.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    assert asked == [], "a rule with neither conditions nor a context request is not worth a snapshot"

    wants = A.AlertEngine([_rule(conditions=[{"kind": "side", "op": "==", "value": "sell"}])], history=50)
    wants.context_provider = provider
    wants.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    assert asked == ["BTCUSDT"]

    # And the ctx handed in explicitly always wins over the provider.
    asked.clear()
    wants.evaluate("BTCUSDT", "sweep", SWEEP, NOW + 60_000, {"symbol": "BTCUSDT"})
    assert asked == []


def test_conditions_hold_a_rule_back_but_never_raise_a_count():
    rule = _rule(conditions=[{"kind": "delta", "op": ">", "value": 0}])
    engine = A.AlertEngine([rule], history=50)
    engine.context_provider = lambda symbol: SNAPSHOT
    assert engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW) == [], "delta is negative: buy sweep, not this"
    assert engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW + 1_000) == []
    assert engine.context_blocks == 0
    # The same rule with the readings that do match fires.
    rule2 = _rule(conditions=[{"kind": "delta", "op": "<", "value": 0},
                              {"kind": "side", "op": "==", "value": "sell"}])
    other = A.AlertEngine([rule2], history=50)
    other.context_provider = lambda symbol: SNAPSHOT
    assert len(other.evaluate("BTCUSDT", "sweep", SWEEP, NOW)) == 1


# ── the builder's rehearsal ───────────────────────────────────────────────────────────────────────

def test_test_fire_refuses_when_there_is_nothing_real_to_rehearse_against():
    engine = A.AlertEngine([dict(LEGACY)], history=50)
    answer = engine.test_fire({"id": "x", "kind": "sweep", "name": "unseen"})
    assert answer["ok"] is False
    assert "no sweep event has been seen yet" in answer["error"]
    assert "never a guess" not in answer["error"], "the refusal is plain, not a lecture"
    assert engine.test_fire(None)["ok"] is False
    # Malformed authored content is ANSWERED, never raised, and never read as "no conditions"
    # (the quarantine itself is pinned in test_a_malformed_conditions_value_quiets_...):
    unreadable = engine.test_fire({"kind": "sweep", "conditions": "junk"})
    assert unreadable["ok"] is False and "no sweep event has been seen yet" in unreadable["error"]


def test_test_fire_reports_every_gate_condition_and_the_block():
    engine = A.AlertEngine([dict(LEGACY)], history=50)      # one real sweep in the log
    engine.context_provider = lambda symbol: SNAPSHOT
    engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    answer = engine.test_fire(_rule(conditions=[{"kind": "price", "op": ">", "value": 1}],
                                    channels=["telegram"], context={}))
    assert answer["ok"] is True and answer["fires"] is True
    assert [gate["gate"] for gate in answer["gates"]] == ["kind", "thresholds", "conditions", "cooldown"]
    assert all(gate["ok"] for gate in answer["gates"])
    assert answer["conditions"][0]["met"] is True
    assert "BTCUSDT" in answer["context"] and "sweep — SELL" in answer["context"]
    assert answer["origin"].startswith("the newest sweep event")
    assert answer["event"]["side"] == "sell" and answer["event"]["levels"] == SWEEP["levels"], \
        "the rehearsed event is the one the engine evaluated, not the copy the alert log holds"
    assert answer["symbol"] == "BTCUSDT"
    assert json.dumps(answer) is not None

    # A failing condition is named, and the rule is not reported as firing.
    failed = engine.test_fire(_rule(conditions=[{"kind": "side", "op": "==", "value": "buy"}]))
    assert failed["fires"] is False
    assert any(gate["gate"] == "conditions" and gate["ok"] is False for gate in failed["gates"])
    assert failed["conditions"][0]["met"] is False
    # A rehearsal never counts as a fire.
    assert engine.rules and engine.history and len(engine.history) == 1


def test_test_fire_can_be_handed_an_event_directly():
    engine = A.AlertEngine([dict(LEGACY)], history=50)
    answer = engine.test_fire(_rule(conditions=[{"kind": "side", "op": "==", "value": "buy"}]),
                              event=dict(SWEEP, side="buy"))
    assert answer["ok"] is True and answer["fires"] is True
    assert answer["origin"] == "the event handed to the test"


def test_the_rehearsal_applies_the_scope_gates_the_engine_refuses_on():
    """AB-01 (§148): the rehearsal used to promise a fire for rules the live engine refuses.

    A rule scoped to a level (or to a minimum hold) now carries those gates in its rehearsal, from
    the same implementation ``evaluate`` refuses on — asserted here from both sides at once."""
    engine = A.AlertEngine([_rule(params={})], history=50)
    engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)                  # one real sweep in the log
    assert len(engine.history) == 1, "the fixture needs a real event to rehearse against"

    scoped = _rule(id="scoped", params={"at_price": 80_500.0, "at_tol": 0.5}, cooldown_s=0)
    answer = engine.test_fire(scoped)
    assert answer["ok"] is True and answer["fires"] is False
    assert [gate["gate"] for gate in answer["gates"]] == \
        ["kind", "at_price", "thresholds", "conditions", "cooldown"]
    price_gate = next(gate for gate in answer["gates"] if gate["gate"] == "at_price")
    assert price_gate["ok"] is False and "away from the rule's own level" in price_gate["detail"]
    assert "63,120.50" in price_gate["detail"] and "80,500.00" in price_gate["detail"]
    # The engine's own verdict on the same event and scope: refused, and nothing recorded.
    live = A.AlertEngine([dict(scoped)], history=5)
    assert live.evaluate("BTCUSDT", "sweep", SWEEP, NOW) == [] and live.history == []

    # The gate is a check, not a wall: an event at the level clears it and the rule would fire.
    assert engine.test_fire(scoped, event=dict(SWEEP, price=80_500.4))["fires"] is True

    # The hold scope: an event that does not say how long the level held is no evidence for it.
    holds = _rule(id="holds", params={"min_age_s": 120}, cooldown_s=0)
    held = engine.test_fire(holds)
    assert held["fires"] is False
    hold_gate = next(gate for gate in held["gates"] if gate["gate"] == "min_age_s")
    assert hold_gate["ok"] is False and "does not say how long" in hold_gate["detail"]
    assert engine.test_fire(holds, event=dict(SWEEP, held_ms=180_000))["fires"] is True


def test_a_rehearsal_of_an_old_event_does_not_smuggle_the_current_tape_in():
    """AB-04 (§148): a snapshot held NOW, read against an older event, came back as the CURRENT
    tape — the block for a two-minute-old event was identical to the block for a now event, the
    provider's delta and the biggest prints included. The window now ends where it says, and a
    delta that ends after the block's own window is not used; the event's own lines stay."""
    snap = {"symbol": "BTCUSDT", "window_ms": 60_000, "now_ms": NOW, "last_price": 63_118.0,
            "delta": {"window_ms": 60_000, "end_ms": NOW, "prints": 1, "buy": 0.0, "sell": 777.25,
                      "value": -777.25, "unknown": 0, "buy_pct": 0.0, "sell_pct": 100.0},
            "prints": [{"ts_ms": NOW - 1_000, "price": 63_120.5, "size": 777.25, "side": "sell"}],
            "levels": SNAPSHOT["levels"], "session": SNAPSHOT["session"]}
    rule = _rule(channels=["telegram"], context={})
    engine = A.AlertEngine([dict(rule)], history=50, settings=_settings())
    engine.context_provider = lambda symbol: snap

    old_block = engine.test_fire(dict(rule), event=dict(SWEEP, ts_ms=NOW - 120_000))["context"]
    assert old_block.splitlines()[0].endswith("· BTCUSDT · 63,120.50"), "the event's own head stays"
    assert "sweep — SELL" in old_block, "the event's own trigger stays"
    assert "delta 60s" not in old_block and "777.25" not in old_block, \
        "neither the provider's current delta nor the current tape rides a two-minute-old event"
    assert "prints:" not in old_block

    control = engine.test_fire(dict(rule), event=dict(SWEEP))["context"]
    assert "delta 1s of 60s: -777.25 (buy 0% / sell 100%)" in control
    assert "prints: 63,120.50 × 777.25 sell" in control, \
        "the same snapshot still feeds a window that genuinely covers it — bounded, not blanked"


def test_an_unreadable_param_skips_the_rule_it_never_raises():
    """AB-05 (§148): a rule authored with a non-numeric threshold (`"min_multiple": "big"`) threw
    straight out of `evaluate()` — through `hub._dispatch` into the per-tick detection loop, where
    one bad rule could stop every other rule and every other symbol. It is now counted and skipped:
    quieter, never louder, and never a traceback on a market event."""
    typo = _rule(id="typo", kind="big_trade", params={"min_multiple": "big"}, cooldown_s=0)
    solid = _rule(id="solid", kind="big_trade", params={"min_multiple": 1.5}, cooldown_s=0)
    engine = A.AlertEngine([dict(typo), dict(solid)], history=50, settings=_settings())
    payload = {"symbol": "BTCUSDT", "ts_ms": NOW, "price": 63_000.0, "size": 42.5,
               "side": "sell", "multiple": 3.4}

    fired = engine.evaluate("BTCUSDT", "big_trade", dict(payload))
    assert [a.rule_id for a in fired] == ["solid"], "the rule beside the typo still fires"
    assert engine._unreadable == {"typo": 1}, "the skip is counted, not silent"
    assert engine.stats()["unreadable"] == {"typo": 1}, \
        "and the count reaches the surface — the status payload carries it"

    answer = engine.test_fire(dict(typo), event=dict(payload))
    assert answer["ok"] is False and "params could not be read" in answer["error"], \
        "the rehearsal refuses with a sentence — it must never dress the skip as 'the market said no'"

    engine.remove("typo")
    assert engine.stats()["unreadable"] == {}, "the count does not outlive the rule it counted"
    assert engine.test_fire(dict(solid), event=dict(payload))["fires"] is True, \
        "and it only refuses the rule that cannot be read"


def test_an_unreadable_band_is_skipped_by_the_touch_path_too():
    """The same class through `evaluate_touch`, which rides the same tick loop (a level that is not
    a number must not stop every price-touch rule either)."""
    engine = A.AlertEngine([_rule(id="tb", kind="level_touch", params={"at_price": "sixty-three thousand"})],
                           history=50, settings=_settings())
    assert engine.evaluate_touch("BTCUSDT", 63_000.0, NOW) == []
    assert engine._unreadable == {"tb": 1}


# ── the snapshot the hub feeds ────────────────────────────────────────────────────────────────────

def test_the_context_buffer_keeps_a_window_and_answers_per_symbol():
    buf = A.ContextBuffer(window_ms=10_000, max_prints=12)
    assert buf.ctx("BTCUSDT") == {}, "a symbol nobody has fed is empty, not an error"
    for step in range(30):
        buf.add_print("btcusdt", NOW + step * 500, 63_000.0 + step, 1.0 + step, "buy")
    buf.set_levels("BTCUSDT", SNAPSHOT["levels"])
    buf.set_session("BTCUSDT", {"name": "us", "state": "open"})
    snapshot = buf.ctx("BTCUSDT")
    assert snapshot["symbol"] == "BTCUSDT" and snapshot["window_ms"] == 10_000
    assert len(snapshot["prints"]) == 12, "the ring is capped, and the newest 12 are what is kept"
    assert snapshot["prints"][-1]["price"] == 63_029.0
    assert all(row["ts_ms"] > snapshot["now_ms"] - 10_000 for row in snapshot["prints"])
    assert snapshot["last_price"] == snapshot["prints"][-1]["price"]
    assert snapshot["delta"]["value"] == snapshot["delta"]["buy"] > 0
    assert snapshot["levels"] == SNAPSHOT["levels"] and snapshot["session"]["name"] == "us"
    assert buf.ctx("ethusdt") == {}, "a symbol with no feed has no snapshot"
    for junk in ("junk", None, "", 0):
        buf.add_print("BTCUSDT", junk, junk, junk)          # nothing here may raise
    assert buf.ctx("") == {} and buf.ctx(None) == {}


def test_the_buffer_reads_as_a_provider_and_survives_being_empty():
    buf = A.ContextBuffer(window_ms=60_000)
    assert A.context_block(SWEEP, buf.ctx("BTCUSDT"), A.clean({"context_format": "csv"}), "sweep")
    buf.add_print("BTCUSDT", NOW, 63_120.5, 42.5, "sell")
    engine = A.AlertEngine([_rule(channels=["telegram"], context={})], history=50)
    engine.context_provider = buf.ctx
    alert = engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0]
    assert "63,120.50" in alert.context and "BTCUSDT" in alert.context


class _Feats:
    last_price = 63_100.0
    tick_size = 0.5

    class tape:
        @staticmethod
        def recent(limit: int = 0) -> list[dict[str, object]]:
            return [{"ts": NOW - 2_000, "price": 63_095.0, "size": 4.0, "side": "buy"},
                    {"ts": NOW - 1_000, "price": 63_100.0, "size": 12.0, "side": "sell"}]

    class heatmap:
        @staticmethod
        def wall_prices(top: int = 0) -> list[dict[str, object]]:
            return [{"price": 63_000.0, "size": 140.0}, {"price": 63_250.0, "size": 96.5}]


class _Hub:
    symbols = {"BTCUSDT": _Feats()}

    @staticmethod
    def session_state(symbol: str) -> dict[str, str]:
        return {"name": "us", "state": "open"}


def test_a_snapshot_can_be_read_straight_off_the_hub():
    snapshot = A.context_from_hub(_Hub(), "btcusdt", window_ms=60_000, walls=2)
    assert snapshot["symbol"] == "BTCUSDT" and snapshot["last_price"] == 63_100.0
    assert [row["price"] for row in snapshot["prints"]] == [63_095.0, 63_100.0]
    assert [row["side"] for row in snapshot["levels"]] == ["bid", "ask"], \
        "which side a wall is on follows from where it sits against the last trade"
    assert snapshot["levels"][0]["distance_ticks"] == 200.0
    assert snapshot["session"]["state"] == "open"
    block = A.context_block(SWEEP, snapshot, A.clean({}), "sweep")
    assert "walls:" in block and "bid 63,000.00" in block
    # A hub with none of it — and one that raises — both answer {} rather than raising upward.
    assert A.context_from_hub(object(), "BTCUSDT")["symbol"] == "BTCUSDT"

    class Hostile:
        @property
        def symbols(self) -> dict[str, object]:
            raise RuntimeError("no hub today")

    assert A.context_from_hub(Hostile(), "BTCUSDT") == {"symbol": "BTCUSDT", "window_ms": 60_000}
    assert A.context_from_hub(None, "")["symbol"] == ""


# ── the rest of the engine, unchanged ─────────────────────────────────────────────────────────────

def test_the_shipped_rules_and_the_kind_list_are_untouched():
    assert len(A.DEFAULT_RULES) == 19
    for raw in A.DEFAULT_RULES:
        rule = A.AlertRule.from_dict(raw)
        assert rule.conditions == [] and rule.context is None
        assert rule.cooldown_scope == "rule" and rule.once_per_window_s == 0.0
        assert rule.max_per_window == 1
        assert rule.to_dict()["params"] == dict(raw.get("params") or {})
    assert len(A.KINDS) == 22


def test_a_rules_dict_still_carries_every_legacy_key():
    out = A.AlertRule.from_dict(LEGACY).to_dict()
    for key in ("id", "name", "kind", "params", "enabled", "cooldown_s", "channels", "fired",
                "last_fired_ms"):
        assert key in out, key
    assert out["id"] == "legacy-sweep" and out["params"] == {"min_levels": 5}
    assert out["context"] is None and out["conditions"] == [] and out["match"] == "all"


def test_the_engine_still_builds_the_way_it_always_did():
    engine = A.AlertEngine([dict(LEGACY)], history=500, webhook_url="http://127.0.0.1:9/hook")
    assert engine.webhook_url.endswith("/hook") and engine.history == []
    assert engine.stats()["rules"] == 1 and engine.stats()["enabled"] == 1
    engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)
    assert engine.recent(limit=5)[0]["kind"] == "sweep"
    assert engine.to_csv(limit=5).splitlines()[0].count(",") >= 3
    assert engine.upsert({"id": "new", "kind": "sweep"})[-1]["id"] == "new"
    assert A.AlertEngine().rules, "no rules handed in means the shipped defaults"


def test_an_upsert_merges_a_builder_rule_onto_the_one_it_replaces():
    engine = A.AlertEngine([dict(LEGACY)], history=50)
    saved = engine.upsert({"id": "legacy-sweep", "conditions": [{"kind": "side", "op": "==", "value": "sell"}],
                           "match": "any", "context": {}})
    assert len(saved) == 1, "the id matched, so the rule was replaced rather than duplicated"
    assert saved[0]["conditions"] == [{"kind": "side", "op": "==", "value": "sell"}]
    assert saved[0]["match"] == "any" and saved[0]["context"] == {}
    assert saved[0]["name"] == "Big sell sweep", "the fields it did not send are kept"
    assert saved[0]["params"] == {"min_levels": 5}


# ── the JS half ───────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def source() -> str:
    return MODULE.read_text(encoding="utf-8")


def _js_conditions(source: str) -> dict[str, dict[str, str]]:
    """The condition catalogue as the JS holds it, parsed out of the module's own table."""
    body = source.split("const CONDITION_KINDS = {", 1)[1].split("\n    };", 1)[0]
    out: dict[str, dict[str, str]] = {}
    for line in body.splitlines():
        found = re.match(r"\s{8}([a-z_]+): \{ label: '([^']*)', unit: '([^']*)', "
                         r"value: '(number|text)', source: '(event|ctx|either)', "
                         r"hint: (?:\"([^\"]*)\"|'([^']*)') \},$", line)
        if found:
            out[found.group(1)] = {"label": found.group(2), "unit": found.group(3),
                                   "value": found.group(4), "source": found.group(5),
                                   "hint": found.group(6) or found.group(7)}
    return out


def _js_list(source: str, name: str) -> list[str]:
    found = re.search(rf"const {name} = \[([^\]]*)\]", source)
    assert found, f"{name} moved — this gate reads it by name"
    return re.findall(r"'([^']*)'", found.group(1))


def test_the_module_and_its_selftest_are_present():
    assert MODULE.exists(), "the builder panel is the point of this workstream"
    assert SELFTEST.exists(), "the module carries its own gate"


def test_it_parses_and_its_selftest_passes():
    check = subprocess.run(["node", "--check", str(MODULE)], capture_output=True, text=True,
                           encoding="utf-8")
    assert check.returncode == 0, check.stderr
    run = subprocess.run(["node", str(SELFTEST)], capture_output=True, text=True, encoding="utf-8",
                         cwd=str(UI))
    assert run.returncode == 0, run.stdout + run.stderr
    assert re.search(r"alert-builder selftest: \d+ ok, 0 failed", run.stdout), run.stdout


def test_the_files_are_crlf_like_every_other_panel():
    for path in (MODULE, SELFTEST):
        raw = path.read_bytes()
        assert raw.count(b"\r\n") > 100, f"{path.name} should be CRLF like its siblings"
        assert raw.count(b"\n") == raw.count(b"\r\n"), f"{path.name} has a bare LF"


def test_the_js_condition_catalogue_is_the_engines_own():
    """The form may not offer a reading the engine does not have, or hide one it does."""
    js = _js_conditions(MODULE.read_text(encoding="utf-8"))
    assert sorted(js) == sorted(A.CONDITION_KINDS), (
        "the JS catalogue and atlas/alerts.py's CONDITION_KINDS have drifted")
    for kind, spec in js.items():
        ours = A.CONDITION_KINDS[kind]
        assert (spec["label"], spec["unit"], spec["value"], spec["source"]) == (
            ours["label"], ours["unit"], ours["value"], ours["source"]), kind


def test_the_js_mirrors_the_engines_ops_modes_and_bounds(source):
    assert _js_list(source, "OPS_NUM") == list(A.NUM_OPS)
    assert _js_list(source, "OPS_TEXT") == list(A.TEXT_OPS)
    assert _js_list(source, "MATCH_MODES") == list(A.MATCH_MODES)
    assert _js_list(source, "CONTEXT_FORMATS") == list(A.CONTEXT_FORMATS)
    assert _js_list(source, "COOLDOWN_SCOPES") == list(A.COOLDOWN_SCOPES)
    channels = re.findall(r"'([a-z]+)'", re.search(r"const CONTEXT_CHANNELS = \[([^\]]*)\]",
                                                   source).group(1))
    assert channels == list(A.CONTEXT_CHANNELS)
    limits = {name: (str(lo), str(hi).replace("_", ""))
              for name, lo, hi in re.findall(r"(\w+): \[(\d+), ([\d_]+)\]", source)}
    assert limits["chars"] == ("40", "2000"), "the block's cap and the form's clamp are one number"
    assert limits["prints"] == ("0", "10") and limits["levels"] == ("0", "10")
    assert A.clean({"context_max_chars": int(limits["chars"][1]) + 1})["context_max_chars"] == 2000
    assert A.clean({"context_prints": int(limits["prints"][1]) + 1})["context_prints"] == 10
    assert A.clean({"context_levels": int(limits["levels"][1]) + 1})["context_levels"] == 10
    assert A.clean({"max_conditions": A.MAX_CONDITIONS + 1})["max_conditions"] == A.MAX_CONDITIONS


_DOM_HARNESS = r"""
/* The DOM half against a stub document: does the panel read back only fields its own markup
   declared, and do the buttons actually change the rule? `node` runs this with a fake document, so
   it is the closest thing to a browser a test machine without one can offer. */
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const registry = new Map(), asked = [];
function mk(id) {
    return { id: id, value: '', checked: false, textContent: '', innerHTML: '', style: {},
             classList: { contains: () => false },
             addEventListener() {}, removeEventListener() {},
             getAttribute: () => null, setAttribute() {}, closest: () => null };
}
const document = {
    readyState: 'complete', head: { appendChild() {} }, body: {},
    createElement: () => ({ id: '', textContent: '' }),
    getElementById(id) { asked.push(id); return registry.get(id) || null; },
    querySelector: () => null, addEventListener() {},
};
const win = { document: document, console: console };
/* The kind catalogue the page loads before this module: one set param and one number, enough for
   the AB-15 checks below to exercise a member list. */
const AB15_FIELDS = [
    { key: 'sides', label: 'Sides', kind: 'set', options: ['buy', 'sell'] },
    { key: 'min_levels', label: 'Levels', unit: '\u00d7', min: 1, step: 1 },
];
win.OFAPALERTS = {
    kinds: () => [{ kind: 'sweep', label: 'Sweep', base: 'a sweep', params: AB15_FIELDS }],
    paramSpec: (kind) => (kind === 'sweep' ? AB15_FIELDS : []),
};
let bad = 0;
function ok(cond, what) { if (!cond) { bad += 1; console.log('  FAIL ' + what); } }
new Function('window', 'document', src)(win, document);
const B = win.OFAPALERTBUILDER;
ok(!!B, 'the module registers itself on window');
ok(typeof B.formHtml === 'function' && typeof B.readForm === 'function', 'its surface is exported');

registry.set('alertBuilderBody', mk('alertBuilderBody'));
registry.set('alertBuilderPill', mk('alertBuilderPill'));
registry.set('symbolSelect', mk('symbolSelect'));
B.watch();
const host = registry.get('alertBuilderBody');
const declared = [...host.innerHTML.matchAll(/id="([A-Za-z0-9_]+)"/g)].map((m) => m[1]);
declared.forEach((id) => registry.set(id, mk(id)));
ok(declared.length > 20, 'the form declares its fields');
ok(declared.every((id) => id.indexOf('alertBuilder') === 0), 'every id it renders is prefixed');
ok(registry.get('alertBuilderPill').textContent.indexOf('0 rules') === 0, 'the pill starts empty');

asked.length = 0;
B.readForm();
const missing = asked.filter((id) => !registry.has(id));
ok(missing.length === 0, 'every id it reads was declared by its own markup: ' + missing.join(','));

/* A rule built through the fields, the way a user would. */
registry.get('alertBuilderName').value = 'sweep + delta';
registry.get('alertBuilderKind').value = 'sweep';
registry.get('alertBuilderMatch').value = 'any';
registry.get('alertBuilderCooldown').value = '45';
registry.get('alertBuilderContextOn').checked = true;
registry.get('alertBuilderCtxChan_telegram').checked = true;
B.onClick({ target: { closest: () => ({ getAttribute: (k) => (k === 'data-ab-act' ? 'add' : '') }) } });
['kind', 'op', 'value'].forEach((key) => registry.set('alertBuilderRow_0_' + key, mk('alertBuilderRow_0_' + key)));
registry.get('alertBuilderRow_0_kind').value = 'delta';
registry.get('alertBuilderRow_0_op').value = '<=';
registry.get('alertBuilderRow_0_value').value = '-300';
const rule = B.ruleFromDraft(B.readForm());
ok(rule.name === 'sweep + delta', 'the name travels');
ok(rule.match === 'any' && rule.cooldown_s === 45, 'the mode and cooldown travel');
ok(rule.conditions.length === 1 && rule.conditions[0].value === -300, 'the condition travels');
ok(rule.context && rule.context.channels.indexOf('telegram') >= 0, 'the snapshot travels');
ok(rule.id.indexOf('ab-') === 0, 'a rule built here carries its own id');

/* The kind switch repaints without eating what was typed. */
B.onChange({ target: { getAttribute: (k) => (k === 'data-ab-act' ? 'kind' : null), id: 'alertBuilderKind', value: 'level_touch' } });
ok(host.innerHTML.indexOf('id="alertBuilderKind"') > 0, 'the repaint happened');
ok(B.state().name === 'sweep + delta' && B.state().conditions.length === 1, 'and nothing typed was lost');

/* Test fire's answer, painted into fields the markup declared. */
registry.set('alertBuilderVerdict', mk('alertBuilderVerdict'));
registry.set('alertBuilderPreview', mk('alertBuilderPreview'));
registry.set('alertBuilderReadings', mk('alertBuilderReadings'));
B.state().context = { enabled: true, channels: ['telegram'] };
B.paintAnswer({ ok: true, fires: true, origin: 'the newest sweep event (12s ago)', gates: [],
                conditions: [{ kind: 'delta', op: '<=', value: -300, met: true, read: -412.8, label: 'Cumulative delta' }],
                context: '12:00:01 · BTCUSDT · 63,120.50\nsweep — SELL · levels 7' });
ok(registry.get('alertBuilderVerdict').textContent.indexOf('would fire') === 0, 'the verdict reads');
ok(registry.get('alertBuilderPreview').textContent.indexOf('sweep — SELL') > 0, 'the block is shown');
ok(registry.get('alertBuilderReadings').innerHTML.indexOf('met') === 0, 'the readings are listed');

/* The two buttons that talk to the engine. */
ok(B.saveBody(rule).body === rule, 'the save sends the rule as an object (api() stringifies it)');
ok(Object.keys(B.testBody(rule, 'btcusdt').body).sort().join() === 'rule,symbol', 'the test sends rule + symbol');

/* ── AB-15: a set param is a member list the kind reads, never a text box that takes anything ── */
const AB15_SET = { key: 'sides', label: 'Sides', kind: 'set', options: ['buy', 'sell'] };
ok(B.coerceParam(AB15_SET, 'buy,sell').join() === 'buy,sell', 'known members travel as typed');
ok(B.coerceParam(AB15_SET, 'byu') === undefined, 'a typo never becomes the rule\'s member list');
ok(B.coerceParam(AB15_SET, 'buy, sl').join() === 'buy', 'and never rides beside a real one');
ok(B.coerceParam(AB15_SET, 'BUY').join() === 'buy', 'the catalogue spelling is what is stored');
const typoDraft = B.newDraft('sweep');
typoDraft.params = { sides: 'byu' };
const typoRule = B.ruleFromDraft(typoDraft);
ok(typoRule.params.sides === undefined, 'so the drafted rule cannot carry an unmatchable side');
const said = B.issuesFor(typoRule, typoDraft).join(' | ');
ok(said.indexOf("Sides: 'byu' is not a member") === 0, 'the panel names the typo instead: ' + said);
ok(B.issuesFor(typoRule).join(' | ').indexOf('byu') < 0, 'the rule alone holds nothing to name');

console.log(bad ? 'DOM HARNESS: ' + bad + ' failed' : 'DOM HARNESS: ok');
process.exit(bad ? 1 : 0);
"""


def test_the_dom_half_renders_and_reads_back_its_own_fields(tmp_path: Path):
    """A stub document, so the panel's own field ids and buttons are exercised, not just its maths."""
    harness = tmp_path / "dom_harness.js"
    harness.write_text(_DOM_HARNESS, encoding="utf-8")
    run = subprocess.run(["node", str(harness), str(MODULE)], capture_output=True, text=True,
                         encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "DOM HARNESS: ok" in run.stdout, run.stdout


_NO_DOM_JS = """
/* The module booted with no document at all: it must not throw, and must not invent an id. */
const fs = require('fs');
const w = {};
new Function('window', fs.readFileSync(process.argv[2], 'utf8'))(w);
const B = w.OFAPALERTBUILDER;
B.paint(); B.watch(); B.readForm();
console.log('no-dom ok', B.rules().length, B.state().kind);
"""


def test_a_call_with_no_dom_at_all_is_a_no_op(tmp_path: Path):
    """The same module, booted with nothing: no throw, no id invented."""
    script = tmp_path / "no_dom.js"
    script.write_text(_NO_DOM_JS, encoding="utf-8")
    run = subprocess.run(["node", str(script), str(MODULE)], capture_output=True, text=True,
                         encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "no-dom ok 0 sweep" in run.stdout, run.stdout


def test_the_panel_is_null_safe_and_keeps_no_timers(source):
    """Its selftest boots it with a stub window and no DOM, so DOM access has to be guarded."""
    assert "typeof document !== 'undefined'" in source
    assert source.count("typeof document === 'undefined' || !document") >= 2, \
        "the style injector and the boot both check for a page before touching one"
    assert "setInterval" not in source and "setTimeout" not in source, \
        "the card reads the rules on activation and on demand — nothing ticks"
    assert "localStorage" not in source, "the config store is the record, not the browser"


def test_it_asks_for_the_container_the_parent_supplies():
    html = (UI / "index.html").read_text(encoding="utf-8", errors="replace")
    if "/desktop/alert-builder.js" not in html:
        pytest.skip("awaiting the parent's wiring: the Alerts view's card + script tag")
    assert 'id="alertBuilderBody"' in html, "the module renders into this one container"
    # The intent: if a shared alerts.js module exists, the builder must load before it. Written as
    # an index() comparison the `or` could never rescue the missing-module case — index() raises
    # before it is evaluated — so the absence is checked first.
    if "/desktop/alerts.js" in html:
        assert html.index("/desktop/alert-builder.js") < html.index("/desktop/alerts.js"), \
            "the builder must load before the module that reads it"


def test_it_is_registered_with_the_audit():
    audit = (ROOT / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    if '"alert-builder.js"' not in audit:
        pytest.skip("awaiting the parent's wiring: the audit's JS_FILES entry")
    assert '"alert-builder.js"' in audit


# ── AB-06: legacy shapes read quiet, never fatal ─────────────────────────────────────────────────


def test_a_legacy_string_channel_reads_as_channels_not_letters():
    """AB-06 (§148): a rule saved with `"channels": "telegram"` — one channel, written as a bare
    string — came back as ['t','e','l','e','g','r','a','m']: per-letter noise that matched no
    delivery, so the rule went mute and nothing said so."""
    one = A.AlertRule.from_dict(_rule(id="legacy", channels="telegram"))
    assert one.channels == ["telegram"], "one channel, read as one channel"
    both = A.AlertRule.from_dict(_rule(id="both", channels="ui, telegram"))
    assert both.channels == ["ui", "telegram"], "a comma string is several channels"
    junk = A.AlertRule.from_dict(_rule(id="junk", channels=42))
    assert junk.channels == ["ui"], "an unreadable shape reads as the default surface, not letters"


def test_a_legacy_flag_or_clock_reads_quiet_never_fatal():
    """AB-06 (§148): `bool("false")` is True — a rule a person had switched off in an older save
    came back on; and a legacy `"cooldown_s": "30s"` raised straight out of the rules load."""
    payload = {"symbol": "BTCUSDT", "ts_ms": NOW, "price": 63_000.0, "size": 42.5, "side": "sell",
               "multiple": 3.4}
    off = _rule(id="off", kind="big_trade", params={"min_multiple": 0}, enabled="false", cooldown_s=0)
    on = _rule(id="on", kind="big_trade", params={"min_multiple": 1.5}, enabled="yes", cooldown_s="30s")
    engine = A.AlertEngine([dict(off), dict(on)], history=50, settings=_settings())
    assert engine.rules[0].enabled is False, "'false' reads off"
    assert engine.rules[1].cooldown_s == 30.0, "a legacy clock reads as the default, never raises"
    fired = engine.evaluate("BTCUSDT", "big_trade", dict(payload))
    assert [a.rule_id for a in fired] == ["on"], "the rule saved off stays off; the one saved on fires"


def test_a_legacy_params_shape_or_junk_entry_cannot_take_the_rules_load_down():
    """AB-06 (§148): `dict("min_multiple=5")` and a bare string entry each raised out of the rules
    load — at boot that load is hub.configure inside _wire_atlas, the engine start itself. Now the
    string params are kept verbatim (the rule reads skipped-and-counted via the unreadable guard),
    a junk entry becomes a disabled placeholder, and the load survives."""
    legacy = _rule(id="legacy-params", kind="big_trade", params="min_multiple=5")
    good = _rule(id="good", kind="big_trade", params={"min_multiple": 1.5}, cooldown_s=0)
    engine = A.AlertEngine([dict(legacy), "junk-entry", dict(good)], history=50, settings=_settings())
    assert len(engine.rules) == 3, "every entry answered, none raised"
    assert engine.rules[1].enabled is False and engine.rules[1].name == "junk-entry", \
        "a junk entry is a disabled placeholder a person can see and delete, not a crash"
    payload = {"symbol": "BTCUSDT", "ts_ms": NOW, "price": 63_000.0, "size": 42.5, "side": "sell",
               "multiple": 3.4}
    fired = engine.evaluate("BTCUSDT", "big_trade", dict(payload))
    assert [a.rule_id for a in fired] == ["good"], "the readable rules are untouched by the junk"
    assert engine._unreadable == {"legacy-params": 1}, "the string params read as skipped-and-counted"
    assert engine.rules[0].to_dict()["params"] == "min_multiple=5", \
        "the authored text survives the save round-trip"


# ── AB-07: a side list reads bid/ask and buy/sell as the same two sides ──────────────────────────


def test_a_side_list_reads_bid_ask_and_buy_sell_as_the_same_two_sides():
    """AB-07 (§148): the catalogue promises "bid/ask are read as the same thing" — `== ask` honoured
    it while `in ["ask"]` compared raw strings and never met on a detector that says "sell"; worse,
    `not_in ["bid"]` fired on exactly the buys it meant to exclude. The list ops now read the same
    way the equality ops do, so both spellings agree whatever the detector says."""
    def meets(op, value, side):
        event = {"kind": "sweep", "side": side, "price": 63120.5, "ts_ms": NOW}
        rule = {"id": "c1", "conditions": [{"id": "c1", "kind": "side", "op": op, "value": value}]}
        return A.evaluate_conditions(rule, event, {}, _settings())

    assert meets("in", ["ask"], "sell") is True, "an author's 'ask' meets a detector's 'sell'"
    assert meets("in", ["bid"], "sell") is False, "'bid' does not meet a sell"
    assert meets("in", ["ask", "bid"], "buy") is True, "the list meets a buy"
    assert meets("in", ["ask", "bid"], "sell") is True, "and a sell"
    assert meets("not_in", ["bid"], "buy") is False, "the excluded side is excluded"
    assert meets("not_in", ["bid"], "sell") is True, "and only that side"
    for side in ("buy", "sell", "ask", "bid"):
        assert meets("==", "ask", side) == meets("in", ["ask"], side), \
            f"== and in must agree on {side!r} — one promise, one reading"


def test_a_side_condition_reaches_a_firing_rule_in_either_spelling():
    """AB-07, end to end: a rule whose condition lists the book's spelling fires on the detector's
    event, and a rule that excludes a side stays quiet on it."""
    sells = _rule(id="both-spellings", kind="sweep", params={"min_levels": 1},
                  conditions=[{"id": "c1", "kind": "side", "op": "in", "value": ["ask", "bid"]}],
                  cooldown_s=0)
    no_buys = _rule(id="no-buys", kind="sweep", params={"min_levels": 1},
                    conditions=[{"id": "c1", "kind": "side", "op": "in", "value": ["bid"]}],
                    cooldown_s=0)
    engine = A.AlertEngine([dict(sells), dict(no_buys)], history=50, settings=_settings())
    fired = engine.evaluate("btcusdt", "sweep", dict(SWEEP))       # SWEEP is a sell sweep
    assert [a.rule_id for a in fired] == ["both-spellings"], \
        "the book's spelling meets the detector's event; the buy-only rule stays quiet on a sell"


# ── AB-08: a delta over an empty window is not a measured zero ───────────────────────────────────


def test_a_delta_over_an_empty_window_is_not_a_measured_zero():
    """AB-08 (§148): over a quiet tape the window's delta is the ABSENCE of a reading — the block
    printed a bare "delta 60s: +0.00" (a measured balance it never measured) and a `<= 0` condition
    met on it. Now the block names the emptiness and the condition never meets; a genuinely balanced
    window still reads +0.00, and a shape that does not say how many prints it summed is taken at
    its word."""
    empty = A.window_delta([], 60_000, NOW)
    quiet_ctx = {"prints": [], "delta": empty, "now_ms": NOW, "symbol": "BTCUSDT"}
    cfg = A.clean({})
    quiet_block = A.context_block(dict(SWEEP), quiet_ctx, cfg, "sweep")
    assert "delta 60s: no prints" in quiet_block, quiet_block
    assert "+0.00" not in quiet_block, f"an empty window is not a measured zero:\n{quiet_block}"

    pairs = [{"ts_ms": NOW - 1_000, "price": 63_000.0, "size": 2.0, "side": "buy"},
             {"ts_ms": NOW - 900, "price": 63_000.0, "size": 2.0, "side": "sell"}]
    balanced_ctx = {"prints": list(pairs), "delta": A.window_delta(pairs, 60_000, NOW), "now_ms": NOW,
                    "symbol": "BTCUSDT"}
    balanced_block = A.context_block(dict(SWEEP), balanced_ctx, cfg, "sweep")
    assert "delta 1s of 60s: +0.00 (buy 50% / sell 50%)" in balanced_block, \
        "a genuinely balanced window still reads as the zero it measured"

    csv_block = A.context_block(dict(SWEEP), quiet_ctx, A.clean({"context_format": "csv"}), "sweep")
    assert "delta,line,delta 60s: no prints" in csv_block, csv_block
    assert "delta,value" not in csv_block, "no numeric value row for a window that summed nothing"

    le0 = {"conditions": [{"kind": "delta", "op": "<=", "value": 0}]}
    assert A.evaluate_conditions(le0, dict(SWEEP), quiet_ctx, cfg) is False, \
        "a condition over an empty window never meets"
    assert A.evaluate_conditions(le0, dict(SWEEP), balanced_ctx, cfg) is True, \
        "a measured zero does meet it"
    bare = dict(quiet_ctx, delta={"value": -412.5, "buy": 100.0, "sell": 512.5})
    assert A.evaluate_condition({"kind": "delta", "op": "<=", "value": -300}, dict(SWEEP), bare) is True, \
        "a shape that does not say how many prints it summed is taken at its word"


# ── AB-09: one appender — the model render and the channels' append agree ────────────────────────


def test_the_model_render_and_the_channels_append_the_block_the_same_way():
    """AB-09 (§148): `notification_text()` was dead (no production caller) while its docstring claimed
    "notify.py's formatters use this" — the real path is `notify._with_context` — and the two had
    drifted: a sentence-less alert rendered with a leading blank line, and the block was not
    stripped. It now delegates to the one appender, so both readings are the same text by
    construction."""
    from orderflow_system.atlas.notify import _with_context
    engine = A.AlertEngine([_rule(id="with-block", channels=["telegram"], context={})], history=50)
    engine.context_provider = lambda symbol: SNAPSHOT
    alert = engine.evaluate("BTCUSDT", "sweep", SWEEP, NOW)[0]
    payload = engine.webhook_payload(alert)
    text = A.notification_text(alert)
    assert text.startswith(alert.message) and text.endswith(alert.context)
    assert text == _with_context(payload, payload["message"]), "one appender, one reading"

    assert A.notification_text({"context": "delta 60s: -54.50"}) == "delta 60s: -54.50", \
        "an alert with no sentence is its block alone — no leading blank line"
    untrimmed = {"message": "  SWEEP  ", "context": "  delta 60s  "}
    assert A.notification_text(untrimmed) == "  SWEEP\ndelta 60s", "appended, never substituted"
    assert A.notification_text(untrimmed) == _with_context(untrimmed, untrimmed["message"])
    assert A.notification_text({"message": "only a sentence"}) == "only a sentence"
    assert A.notification_text(None) == ""

    class _Alert:
        pass
    obj = _Alert()
    obj.message = "plain object"
    obj.context = "block"
    assert A.notification_text(obj) == "plain object\nblock", "the object path still works"


# ── AB-10: the conditions gate speaks the rule's own match ──────────────────────────────────────


def test_the_rehearsal_says_which_condition_bar_applied():
    """AB-10 (§148): the gate's sentence ignored `match` — an `any` rule that passed on ONE
    condition claimed "every condition is met" (false), and one that failed — because NONE met —
    said "at least one condition is not met", which reads as if the bar were every. Each mode now
    says its own truth; the `all` sentences are unchanged."""
    def gate(match, conditions):
        rule = {"id": "r", "kind": "sweep", "match": match, "params": {"min_levels": 1},
                "cooldown_s": 0, "channels": ["ui"], "conditions": conditions}
        engine = A.AlertEngine([dict(rule)], history=10, settings=A.clean({}))
        engine.context_provider = lambda symbol: SNAPSHOT
        ans = engine.test_fire(dict(rule), event=dict(SWEEP))
        return next(g for g in ans["gates"] if g["gate"] == "conditions")

    buy = {"kind": "side", "op": "==", "value": "buy"}        # unmet on the sell sweep
    delta_ok = {"kind": "delta", "op": ">", "value": -100}    # met (SNAPSHOT's delta is -54.5)
    delta_no = {"kind": "delta", "op": ">", "value": 1000}    # unmet

    passed = gate("any", [buy, delta_ok])
    assert passed["ok"] is True and passed["detail"] == "at least one condition is met", \
        "an any-rule that met one condition may not claim every condition is met"
    failed = gate("any", [buy, delta_no])
    assert failed["ok"] is False and failed["detail"] == "no condition is met", \
        "an any-rule fails because none met, not because one did not"
    assert gate("all", [delta_ok, delta_ok])["detail"] == "every condition is met"
    assert gate("all", [delta_ok, delta_no])["detail"] == "at least one condition is not met"


# ── AB-11: the rehearsal shows only a block that would really ride ──────────────────────────────


def test_the_rehearsal_only_shows_a_block_that_would_really_ride():
    """AB-11 (§148): the rehearsal rendered the evidence block unconditionally, so a rule whose
    evidence was switched off — or whose channels wake nobody (blocks ride telegram, ntfy, email and
    webhook, never the panel) — was shown a block no notification would ever carry. The answer now
    applies the same gate the delivery path applies, reports which gate held it back, and for a block
    that would ride, shows exactly what the live alert would carry."""
    def rehearse(rule):
        engine = A.AlertEngine([dict(rule)], history=10, settings=A.clean({}))
        engine.context_provider = lambda symbol: SNAPSHOT
        ans = engine.test_fire(dict(rule), event=dict(SWEEP))
        assert ans.get("ok"), ans
        live = engine._evidence(A.AlertRule.from_dict(rule), SWEEP, SNAPSHOT, "sweep", "BTCUSDT")
        return ans, live

    base = {"id": "r", "kind": "sweep", "params": {"min_levels": 1}, "cooldown_s": 0,
            "channels": ["ui", "telegram"]}

    ridden, live = rehearse({**base, "context": {"enabled": True}})
    assert ridden["context_gate"] == "" and ridden["context"], "a waking rule still shows its block"
    assert ridden["context"] == live, \
        "the rehearsal's block and the live alert's block are the same render, from one gate"

    silenced, _ = rehearse({**base, "channels": ["ui"], "context": {"enabled": True}})
    assert silenced["context"] == "" and silenced["context_gate"] == "no-channel", \
        "the panel is not a waking channel — no block rides, and the answer says why"

    off, _ = rehearse({**base, "context": {"enabled": False}})
    assert off["context"] == "" and off["context_gate"] == "off", \
        "an evidence-off rule is never shown a block no notification would carry"


# ── AB-13: the capped CSV stays a spreadsheet ───────────────────────────────────────────────────


def test_the_capped_csv_stays_a_spreadsheet():
    """AB-13 (§148): the CSV block's cap appended the text form's bare "+N more" line — a one-field
    row among three-field rows — so a spreadsheet read the capped block as malformed. The CSV cap now
    drops whole rows and writes the marker as a row of the same shape; no row is ever cut."""
    def rows_of(block):
        return list(csv.reader(io.StringIO(block)))

    whole = rows_of(A.context_block(dict(SWEEP), dict(SNAPSHOT),
                                    A.clean({"context_format": "csv", "context_max_chars": 2_000}),
                                    "sweep"))
    assert all(len(row) == 3 for row in whole) and len(whole) > 3, "the uncapped form's shape"

    for cap in (140, 40):
        block = A.context_block(dict(SWEEP), dict(SNAPSHOT),
                                A.clean({"context_format": "csv", "context_max_chars": cap}), "sweep")
        rows = rows_of(block)
        assert rows and all(len(row) == 3 for row in rows), \
            f"every row is three fields at cap {cap}: {block!r}"
        assert len(block) <= cap, f"the cap holds at {cap}: {len(block)} chars"
        marker = next((row for row in rows if row[0] == "note" and row[1] == "cap"), None)
        assert marker and marker[2].startswith("+") and "more" in marker[2], \
            f"the marker rides as a row of the same shape at cap {cap}: {rows!r}"
        dropped = int(marker[2].split()[0][1:])
        shown = len([row for row in rows if row[0] != "note"])
        assert shown + dropped == len(whole), \
            f"the count is exact at cap {cap}: {shown} shown + {dropped} dropped == {len(whole)}"


# ── AB-14: the rehearsal reads the event the engine actually saw ────────────────────────────────


def test_the_rehearsal_reads_the_event_the_engine_actually_saw():
    """AB-14 (§148): the rehearsal fell back to the alert log, whose entries carry the record's
    scalarised copy — nested values stringified — so a dry run read a string where the live path read
    a structure; and with every rule cooling, the newest event fired nothing and the log's newest
    entry was an OLDER event. The engine now keeps the newest raw payload per kind and the rehearsal
    reads that: the same shape the live path read, the newest event even when nothing fired, and a
    copy the caller cannot corrupt."""
    rule = {"id": "r", "kind": "sweep", "params": {"min_levels": 1}, "cooldown_s": 300,
            "channels": ["ui"], "conditions": []}
    engine = A.AlertEngine([dict(rule)], history=20, settings=A.clean({}))
    first = {"kind": "sweep", "symbol": "btcusdt", "price": 63120.5, "side": "sell", "levels": 7,
             "size": 42.5, "ts_ms": NOW, "nested": {"levels": [63100.0, 63115.0]}}
    newest = {**first, "price": 63130.0, "side": "buy", "levels": 9, "ts_ms": NOW + 30_000,
              "nested": {"levels": [63125.0, 63130.0, 63135.0]}}
    assert len(engine.evaluate("btcusdt", "sweep", dict(first), ts_ms=NOW)) == 1
    assert engine.evaluate("btcusdt", "sweep", dict(newest), ts_ms=NOW + 30_000) == [], \
        "the second event is inside the cooldown: it fires nothing, and the log keeps only the first"

    payload, origin, stamp = engine._rehearsal_event(engine.rules[0])
    assert stamp == NOW + 30_000 and "event" in origin, \
        f"the rehearsal reads the newest event, not the newest alert: {origin!r}"
    assert payload["nested"] == {"levels": [63125.0, 63130.0, 63135.0]}, \
        "the nested value is the structure the live path read, never the record's stringified copy"

    payload["nested"]["levels"].append("tampered")
    again, _origin, _stamp = engine._rehearsal_event(engine.rules[0])
    assert again["nested"]["levels"] == [63125.0, 63130.0, 63135.0], \
        "what the rehearsal hands out is a copy — the ring cannot be corrupted from outside"

    # The log fallback still answers for a kind nothing has been evaluated for since boot.
    cold = A.AlertEngine([dict(rule)], history=20, settings=A.clean({}))
    cold.history.append(A.Alert(rule_id="r", name="x", kind="sweep", symbol="btcusdt", ts_ms=NOW,
                                message="m", data={"kind": "sweep", "levels": 5}))
    payload, origin, stamp = cold._rehearsal_event(cold.rules[0])
    assert stamp == NOW and "alert" in origin, f"the fallback names the log's copy: {origin!r}"


def test_the_window_labels_say_the_span_the_tape_actually_covers():
    """§148 (own finding, from AB-04's receipt): the provider's tape is a fixed ring (240 prints),
    so a "60 s" window is regularly a fraction of a minute. The delta and tape labels now name the
    span that was measured, not the window that was asked for.
    """
    cfg = A.clean({"context_window_ms": 60_000})
    block = A.context_block(SWEEP, SNAPSHOT, cfg, "sweep")
    assert "delta 40s of 60s: -54.50 (buy 5% / sell 95%)" in block
    assert "tape 5 prints in 40s of 60s" in block
    assert A._tape_speed_of(SNAPSHOT["prints"], 60_000, NOW) == 0.12
    # a full ring: the prints cover the whole window, so no "of" in the labels
    full_prints = [{"ts_ms": NOW - i * 1000, "price": 63000.0, "size": 1.0, "side": "buy"}
                   for i in range(61)]
    full_delta = {"window_ms": 60_000, "end_ms": NOW, "prints": 61, "buy": 61.0,
                  "sell": 0.0, "value": 61.0, "unknown": 0, "buy_pct": 100.0, "sell_pct": 0.0}
    full_ctx = {"prints": full_prints, "delta": full_delta, "now_ms": NOW, "symbol": "BTCUSDT"}
    full_block = A.context_block(SWEEP, full_ctx, cfg, "sweep")
    assert "delta 60s:" in full_block
    assert "of" not in full_block.split("tape")[0]
    assert "tape 61 prints in 60s" in full_block or "tape 1.0/s" in full_block
    assert A._tape_speed_of(full_prints, 60_000) == 1.02
