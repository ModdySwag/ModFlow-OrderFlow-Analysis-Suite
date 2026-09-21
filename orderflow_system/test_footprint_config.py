"""The footprint configuration block and the per-cell reading it drives (W2 / P0-3).

The claim this file is about: the panel's settings block is honest under garbage, and every mark the
panel draws is arithmetic a test can pin — so a cell marked imbalanced, a stack, an absorption row,
the POC of a bar and its value area all follow from the numbers in the bar, not from a drawing
convention nobody can check.

What is pinned here, all of it offline (no feed, no hub, no config file):

* `clean()` — unknown keys dropped, wrong types coerced, numbers clamped to the published bounds,
  whole-row counts made whole, and never a raise (a hand-edited config or a stale drawer cannot put
  the panel into a state it cannot draw);
* the session window: inside / outside / wrapping / a window the whole day long, and a bar whose
  clock is unknown (kept, never thrown away);
* the reading against `analytics/footprint.py` — the same fixture must produce the same imbalances,
  the same POC and the same absorption rows the panel's own "calc:" line is built from;
* a stacked run, a diagonal run (the case where same-price says nothing and the diagonal does),
  absorption with and without the bar's body clause, POC/value area, the row filter and the
  `count` metric with no counts to read;
* the two routes: the block that comes back, the capabilities the drawer renders from, a refused
  patch, and a GET that writes nothing;
* the panel module's own selftest (`orderflow.selftest.js`, run under node) and the parity between
  the Python and JavaScript copies of this arithmetic on the same fixtures — two implementations
  that disagree would draw marks that contradict the printed numbers.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_footprint_config.py -q
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.atlas import footprint_config as fp

UI = Path(__file__).parent / "desktop" / "ui"
MODULE = UI / "orderflow.js"
SELFTEST = UI / "orderflow.selftest.js"


# ── fixtures: small enough to check by hand, shared with the JavaScript parity run ───────────────

#: Six rows, one row step apart. Three ask-heavy rows in a row (a stack at ratio ≥ 3), then two
#: bid-heavy rows (a run of two, which is one short of the shipped stack count).
SAME_PRICE_LEVELS = [
    {"price": 100.0, "bid": 20, "ask": 20},
    {"price": 100.5, "bid": 5, "ask": 15},
    {"price": 101.0, "bid": 4, "ask": 16},
    {"price": 101.5, "bid": 3, "ask": 15},
    {"price": 102.0, "bid": 30, "ask": 5},
    {"price": 102.5, "bid": 18, "ask": 6},
]

#: The diagonal case: 100.5's own bid makes the same-price ratio 1.5 (no mark), while the bid one
#: row below is 5 — 30/5 = 6, so only the diagonal convention flags it.
DIAGONAL_LEVELS = [
    {"price": 100.0, "bid": 5, "ask": 10},
    {"price": 100.5, "bid": 20, "ask": 30},
    {"price": 101.0, "bid": 10, "ask": 9},
]

#: Every price sits exactly half a step up (…200.5, …201.5, …202.5 at a 0.5 tick): the rows where
#: Python's half-to-even keying and the panel's Math.round keying disagreed (T6-F06).
HALF_STEP_LEVELS = [
    {"price": 100.25, "bid": 20, "ask": 5},
    {"price": 100.75, "bid": 5, "ask": 30},
    {"price": 101.25, "bid": 30, "ask": 5},
]

#: Five rows, the middle one ten times a normal row: the average row is 56, so the middle row reads
#: 3.57x — absorption, while the bar's body stays inside its range.
ABSORPTION_LEVELS = [
    {"price": 100.0, "bid": 10, "ask": 10},
    {"price": 100.5, "bid": 10, "ask": 10},
    {"price": 101.0, "bid": 100, "ask": 100},
    {"price": 101.5, "bid": 10, "ask": 10},
    {"price": 102.0, "bid": 10, "ask": 10},
]
ABSORPTION_BAR = {"open": 101.0, "high": 101.4, "low": 100.9, "close": 101.05}
RANGE_BAR = {"open": 100.0, "high": 102.0, "low": 99.9, "close": 101.9}

#: Four rows a quarter apart — two clustered rows at two ticks per row. The upper cluster is
#: ask-heavy (60 over 10 = 6x) and carries 8 prints, so both the count metric and an imbalance have
#: something to read there.
CLUSTER_LEVELS = [
    {"price": 100.0, "bid": 10, "ask": 10, "count": 4},
    {"price": 100.25, "bid": 12, "ask": 8, "count": 6},
    {"price": 100.5, "bid": 5, "ask": 30, "count": 3},
    {"price": 100.75, "bid": 5, "ask": 30, "count": 5},
]


def sides(block: dict) -> dict[float, str]:
    return {row["price"]: row["imbalance"] for row in block["rows"] if row["imbalance"]}


# ── clean(): the contract the config store registers ────────────────────────────────────────────


def test_defaults_are_the_block_the_parent_registers():
    assert set(fp.DEFAULTS) == set(fp.BOUNDS) | set(fp.CHOICES) | {
        key for key, value in fp.DEFAULTS.items() if isinstance(value, bool)}
    block = fp.clean(None)
    assert block == fp.DEFAULTS and block is not fp.DEFAULTS


def test_clean_drops_unknown_keys_and_never_raises():
    block = fp.clean({"unknown": 1, "imbalance_threshold": 4.0})
    assert "unknown" not in block
    assert block["imbalance_threshold"] == 4.0
    for garbage in (None, 5, "junk", ["x"], {"cell_metric": object()}, {"ticks_per_row": math.nan}):
        assert fp.clean(garbage) == fp.DEFAULTS


def test_clean_coerces_enums_including_hand_typed_spellings():
    assert fp.clean({"cell_metric": "BID"})["cell_metric"] == "bid"
    assert fp.clean({"cell_metric": "same price"})["cell_metric"] == "bid_ask"
    assert fp.clean({"session_filter": "same-price"})["session_filter"] == "all"
    assert fp.clean({"imbalance_mode": "same-price"})["imbalance_mode"] == "same_price"
    assert fp.clean({"imbalance_mode": "Both"})["imbalance_mode"] == "both"
    assert fp.clean({"color_by": "imbalance"})["color_by"] == "imbalance"
    assert fp.clean({"cell_metric": "prints"})["cell_metric"] == "count"


def test_clean_clamps_numbers_and_coerces_switches():
    assert fp.clean({"imbalance_threshold": 99})["imbalance_threshold"] == 50.0
    assert fp.clean({"imbalance_threshold": -3})["imbalance_threshold"] == 1.0
    assert fp.clean({"imbalance_threshold": "2.5"})["imbalance_threshold"] == 2.5
    assert fp.clean({"imbalance_threshold": "junk"})["imbalance_threshold"] == 3.0
    assert fp.clean({"stack_min_levels": 3.7})["stack_min_levels"] == 4
    assert fp.clean({"stack_min_levels": 500})["stack_min_levels"] == 20
    assert fp.clean({"poc_per_bar": 0})["poc_per_bar"] is False
    assert fp.clean({"poc_per_bar": "on"})["poc_per_bar"] is True
    assert fp.clean({"poc_per_bar": "junk"})["poc_per_bar"] is True
    assert fp.clean({"value_area_pct": 0.02})["value_area_pct"] == 0.5


def test_clean_keeps_a_none_value_at_its_default():
    block = fp.clean({"imbalance_threshold": None, "cell_metric": None})
    assert block["imbalance_threshold"] == fp.DEFAULTS["imbalance_threshold"]
    assert block["cell_metric"] == fp.DEFAULTS["cell_metric"]


def test_capabilities_describe_every_key_with_a_label_and_a_sentence():
    rows = fp.capabilities()
    assert {row["key"] for row in rows} == set(fp.DEFAULTS)
    for row in rows:
        assert row["path"] == "atlas.footprint." + row["key"]
        assert row["label"] and row["meaning"] and len(row["meaning"]) > 20
        assert row["kind"] in ("number", "bool", "enum")
        assert row["applies"] in ("live", "restart")
        if row["kind"] == "number":
            assert row["min"] < row["max"]
        if row["kind"] == "enum":
            assert len(row["choices"]) >= 2
    restart = {row["key"] for row in rows if row["applies"] == "restart"}
    assert restart == {"min_print_size"}, "only the print-size filter needs the engine to re-read"


# ── the session window ──────────────────────────────────────────────────────────────────────────


def test_session_verdict_reads_the_window_in_utc():
    cfg = {"session_filter": "rth"}
    assert fp.session_verdict("2026-09-18T14:00:00Z", cfg) == "in"      # 14:00 UTC, inside
    assert fp.session_verdict("2026-09-18T02:00:00Z", cfg) == "out"
    assert fp.session_verdict(1758205200, cfg) == fp.session_verdict(1758205200000, cfg)
    outside = {"session_filter": "outside_rth"}
    assert fp.session_verdict("2026-09-18T14:00:00Z", outside) == "out"
    assert fp.session_verdict("2026-09-18T02:00:00Z", outside) == "in"
    assert fp.session_verdict(None, cfg) == "all"                       # an unknown clock is kept
    assert fp.session_verdict("junk", cfg) == "all"
    assert fp.session_verdict(1758205200, None) == "all"                # filter off by default


def test_session_verdict_handles_a_wrapping_window_and_a_whole_day_one():
    wrap = {"session_filter": "rth", "session_start_min": 1200, "session_end_min": 120}
    assert fp.session_verdict("2026-09-18T22:00:00Z", wrap) == "in"
    assert fp.session_verdict("2026-09-18T01:00:00Z", wrap) == "in"
    assert fp.session_verdict("2026-09-18T06:00:00Z", wrap) == "out"
    whole = {"session_filter": "rth", "session_start_min": 0, "session_end_min": 0}
    assert fp.session_verdict("2026-09-18T06:00:00Z", whole) == "in"


# ── the reading ─────────────────────────────────────────────────────────────────────────────────


def test_same_price_reading_marks_the_heavy_side_and_stacks_three_in_a_row():
    block = fp.annotate_bar(SAME_PRICE_LEVELS)
    assert block["ok"] is True
    assert sides(block) == {100.5: "buy", 101.0: "buy", 101.5: "buy", 102.0: "sell", 102.5: "sell"}
    assert block["counts"]["imbalance_buy"] == 3 and block["counts"]["imbalance_sell"] == 2
    stacks = block["stacks"]
    assert len(stacks) == 1, "the two sell rows are one short of a stack"
    stack = stacks[0]
    assert (stack["side"], stack["levels"], stack["mode"]) == ("buy", 3, "same_price")
    assert stack["from_price"] == 101.5 and stack["to_price"] == 100.5
    assert stack["max_ratio"] == 5.0
    assert [row["price"] for row in block["rows"] if row["stack"]] == [100.5, 101.0, 101.5]


def test_a_stack_breaks_where_a_row_is_missing():
    levels = [row for row in SAME_PRICE_LEVELS if row["price"] != 101.0]
    block = fp.annotate_bar(levels)
    assert block["stacks"] == [], "a missing row between two marked ones is not one stack"
    assert block["counts"]["imbalance_buy"] == 2


def test_diagonal_reading_flags_what_same_price_cannot_see():
    same = fp.annotate_bar(DIAGONAL_LEVELS, {"imbalance_mode": "same_price"})
    assert sides(same) == {}
    diagonal = fp.annotate_bar(DIAGONAL_LEVELS, {"imbalance_mode": "diagonal"})
    assert sides(diagonal) == {100.5: "buy"}
    assert diagonal["rows"][1]["ratios"]["diagonal"] == 6.0
    assert diagonal["rows"][1]["readings"] == {"same_price": None, "diagonal": "buy"}
    both = fp.annotate_bar(DIAGONAL_LEVELS, {"imbalance_mode": "both"})
    assert sides(both) == {100.5: "buy"}
    assert both["counts"]["diagonal"] == 1


def test_diagonal_stacks_are_counted_separately_when_both_readings_are_on():
    levels = [
        {"price": 100.0, "bid": 5, "ask": 5},
        {"price": 100.5, "bid": 1, "ask": 40},
        {"price": 101.0, "bid": 1, "ask": 40},
        {"price": 101.5, "bid": 1, "ask": 40},
    ]
    block = fp.annotate_bar(levels, {"imbalance_mode": "both", "imbalance_threshold": 3.0})
    # Same-price: 40 over 1 on the last three rows. Diagonal asks against the bid one row below:
    # 40/5 = 8 on 100.5, then 40/1 = 40 on the rest — three rows either way.
    assert sides(block) == {100.5: "buy", 101.0: "buy", 101.5: "buy"}
    modes = sorted(stack["mode"] for stack in block["stacks"])
    assert modes == ["diagonal", "same_price"], "a user marking both conventions wants both stacks"
    for stack in block["stacks"]:
        assert (stack["side"], stack["levels"]) == ("buy", 3)
    assert block["counts"]["diagonal"] == 3


def test_absorption_needs_the_size_and_a_quiet_body():
    quiet = fp.annotate_bar(ABSORPTION_LEVELS, bar=ABSORPTION_BAR)
    assert [row["price"] for row in quiet["absorption"]] == [101.0]
    assert quiet["absorption"][0]["ratio"] == 3.5714
    assert quiet["body_known"] is True
    assert [row["price"] for row in quiet["rows"] if row["absorption"]] == [101.0]
    moved = fp.annotate_bar(ABSORPTION_LEVELS, bar=RANGE_BAR)
    assert moved["absorption"] == [], "a bar that ran did not absorb"
    unknown = fp.annotate_bar(ABSORPTION_LEVELS)         # no OHLC: the size clause alone decides
    assert unknown["body_known"] is False and len(unknown["absorption"]) == 1
    strict = fp.annotate_bar(ABSORPTION_LEVELS, {"absorption_threshold": 4.0}, bar=ABSORPTION_BAR)
    assert strict["absorption"] == []


def test_poc_and_value_area_are_read_on_traded_volume():
    block = fp.annotate_bar(ABSORPTION_LEVELS)
    assert block["poc"]["price"] == 101.0 and block["poc"]["share_pct"] == 71.4286
    assert block["value_area"] == {"val": 101.0, "vah": 101.0, "pct": 0.7, "rows": 1,
                                   "share_pct": 71.4286}
    assert [row["price"] for row in block["rows"] if row["poc"]] == [101.0]
    assert [row["price"] for row in block["rows"] if row["value_area"]] == [101.0]
    wider = fp.annotate_bar(ABSORPTION_LEVELS, {"value_area_pct": 0.95})
    # 266 of 280: the expansion takes the bigger neighbour each step and prefers the upper row on a
    # tie, so a 0.95 share swallows the whole bar.
    assert (wider["value_area"]["val"], wider["value_area"]["vah"]) == (100.0, 102.0)
    assert wider["value_area"]["rows"] == 5 and wider["value_area"]["share_pct"] == 100.0
    off = fp.annotate_bar(ABSORPTION_LEVELS, {"poc_per_bar": False, "value_area_per_bar": False})
    assert off["poc"] is None and off["value_area"] is None
    assert not any(row["poc"] or row["value_area"] for row in off["rows"])


def test_equal_rows_extremes_and_the_row_filter():
    block = fp.annotate_bar(ABSORPTION_LEVELS)
    assert block["counts"]["equal"] == 5, "every row in this fixture has bid == ask"
    assert block["extremes"] == {"max_bid": 101.0, "max_ask": 101.0}
    assert sorted(row["price"] for row in block["rows"] if row.get("extreme")) == [101.0]
    filtered = fp.annotate_bar(ABSORPTION_LEVELS, {"min_level_volume": 50})
    assert [row["price"] for row in filtered["rows"]] == [101.0]
    assert filtered["filtered"] == {"levels": 4, "volume": 80.0}
    assert filtered["poc"]["price"] == 101.0
    empty = fp.annotate_bar(ABSORPTION_LEVELS, {"min_level_volume": 500})
    assert empty["ok"] is False and empty["refusal"] == fp.REFUSAL_ALL_FILTERED
    no_extremes = fp.annotate_bar(ABSORPTION_LEVELS, {"show_extremes": False})
    assert no_extremes["extremes"] == {"max_bid": None, "max_ask": None}


def test_the_count_metric_refuses_when_the_bars_carry_no_counts():
    block = fp.annotate_bar(ABSORPTION_LEVELS, {"cell_metric": "count"})
    assert block["refusal"] == fp.REFUSAL_COUNT
    assert block["ok"] is False, "an unreadable metric refuses the whole bar, not just the sentence"
    assert all(row["metric"] is None for row in block["rows"])
    counted = fp.annotate_bar(CLUSTER_LEVELS, {"cell_metric": "count", "ticks_per_row": 2})
    assert [row["metric"] for row in counted["rows"]] == [10.0, 8.0]
    assert counted["refusal"] is None
    assert counted["ok"] is True
    # And the payload reading agrees: no bar kept, so the panel has nothing to mark.
    payload = fp.annotate_bars([{"levels": ABSORPTION_LEVELS}], {"cell_metric": "count"})
    assert payload["kept"] == 0 and payload["ok"] is False


def test_cell_metrics_read_the_row_they_name():
    levels = [{"price": 100.0, "bid": 30, "ask": 10, "count": 7}]
    assert fp.annotate_bar(levels, {"cell_metric": "bid"})["rows"][0]["metric"] == 30.0
    assert fp.annotate_bar(levels, {"cell_metric": "ask"})["rows"][0]["metric"] == 10.0
    assert fp.annotate_bar(levels, {"cell_metric": "delta"})["rows"][0]["metric"] == -20.0
    assert fp.annotate_bar(levels, {"cell_metric": "bid_ask"})["rows"][0]["metric"] == 40.0
    assert fp.annotate_bar(levels, {"cell_metric": "volume"})["rows"][0]["metric"] == 40.0
    assert fp.annotate_bar(levels, {"cell_metric": "count"})["rows"][0]["metric"] == 7.0


def test_ticks_per_row_clusters_rows_and_keeps_their_span():
    block = fp.annotate_bar(CLUSTER_LEVELS, {"ticks_per_row": 2}, tick_size=0.25)
    assert len(block["rows"]) == 2
    first, second = block["rows"]
    assert first["span"] == [100.0, 100.25] and first["levels"] == 2
    assert first["bid"] == 22.0 and first["ask"] == 18.0 and first["volume"] == 40.0
    assert first["imbalance"] is None, "22 against 18 is no imbalance at any of the ratios here"
    assert second["span"] == [100.5, 100.75] and second["levels"] == 2
    assert second["bid"] == 10.0 and second["ask"] == 60.0 and second["volume"] == 70.0
    assert second["imbalance"] == "buy" and second["imbalance_ratio"] == 6.0
    unclustered = fp.annotate_bar(CLUSTER_LEVELS, {}, tick_size=0.25)
    assert len(unclustered["rows"]) == 4


def test_the_session_filter_keeps_the_marks_off_bars_it_excludes():
    cfg = {"session_filter": "rth"}
    quiet = fp.annotate_bar(SAME_PRICE_LEVELS, cfg, bar={"time": "2026-09-18T02:00:00Z"})
    assert quiet["ok"] is False and quiet["refusal"] == fp.REFUSAL_SESSION
    assert quiet["session"] == "out" and quiet["rows"] == []
    marked = fp.annotate_bar(SAME_PRICE_LEVELS, cfg, bar={"time": "2026-09-18T14:00:00Z"})
    assert marked["ok"] is True and marked["session"] == "in"


def test_malformed_payloads_refuse_in_one_sentence_instead_of_raising():
    for garbage in (None, "junk", 5, [None, "x", {"nope": 1}], [{"price": "abc"}], {}):
        block = fp.annotate_bar(garbage)
        assert block["ok"] is False and block["refusal"] == fp.REFUSAL_NO_ROWS
        assert block["rows"] == [] and block["poc"] is None
    mapping = fp.annotate_bar({100.0: (5, 15), 100.5: (5, 15)})
    assert mapping["ok"] is True and mapping["counts"]["imbalance_buy"] == 2
    assert fp.annotate_bars(None)["refusal"] == fp.REFUSAL_NO_BARS
    assert fp.annotate_bars([None, 5])["ok"] is False
    assert fp.annotate_bars([{"levels": SAME_PRICE_LEVELS}])["kept"] == 1


def test_the_reading_agrees_with_the_analytics_pack_the_panel_prints():
    """A mark that disagreed with the "calc:" line would be a lie — so hold them equal."""
    from orderflow_system.analytics.footprint import analyse_levels

    rows = {float(row["price"]): (float(row["bid"]), float(row["ask"])) for row in SAME_PRICE_LEVELS}
    for mode in ("same_price", "diagonal"):
        pack = analyse_levels(rows, tick_size=0.0, threshold=3.0, mode=mode)
        mine = fp.annotate_bar(SAME_PRICE_LEVELS, {"imbalance_mode": mode, "imbalance_threshold": 3.0})
        theirs = {(float(item["price"]), item["side"]) for item in pack["imbalances"]}
        ours = {(row["price"], row["imbalance"]) for row in mine["rows"] if row["imbalance"]}
        assert ours == theirs, f"{mode}: marks and the printed pack disagree"
        assert mine["counts"]["imbalance_buy"] == pack["imbalance_counts"]["buy"]
        assert mine["counts"]["imbalance_sell"] == pack["imbalance_counts"]["sell"]
        assert mine["poc"]["price"] == pack["poc"]["price"]
        assert mine["poc"]["share_pct"] == pack["poc"]["share_pct"]


def test_absorption_agrees_with_the_charts_own_rule():
    """The chart's purple cells and these marks must be the same rows (shipped defaults)."""
    block = fp.annotate_bar(ABSORPTION_LEVELS, bar=ABSORPTION_BAR)
    rows = block["rows"]
    average = sum(row["volume"] for row in rows) / len(rows)
    bar = ABSORPTION_BAR
    chart = [
        row["price"] for row in rows
        if row["volume"] >= average * 2.0
        and abs(bar["close"] - bar["open"]) < (bar["high"] - bar["low"]) * 0.3
    ]
    assert [row["price"] for row in block["absorption"]] == chart


def test_the_marks_agree_with_the_panels_own_numbers_on_real_payloads():
    """The fixtures above are hand-checked; this runs the same reading over the app's own payloads.

    Every bar the generator models is annotated and the totals are held against the Numbers-Bars
    pack the panel prints under the chart ("calc: ...") — the same comparison a trader would make by
    eye, on 200 bars per instrument instead of one. The generator is deterministic per
    (symbol, tf, range), so this is a stable check, not a sample.
    """
    from orderflow_system.dashboard import demo_data
    from orderflow_system.dashboard.app import _annotate_footprint_bars

    checked = 0
    for symbol in ("BTCUSDT", "ES", "NQ", "SPY"):
        bars = demo_data.demo_footprint(symbol, tf=60, range_s=86400)
        if not bars:
            continue                                   # a generator that does not model it: no claim
        checked += 1
        bars = _annotate_footprint_bars(bars, mode="same_price", threshold=3.0)
        marked = fp.annotate_bars(bars)
        assert marked["kept"] == len(bars), f"{symbol}: {marked['skipped']} bars were not read"
        mine = [block["counts"] for block in marked["bars"]]
        theirs = [((bar.get("calc") or {}).get("imbalance_counts") or {}) for bar in bars]
        assert sum(count["imbalance_buy"] for count in mine) == sum(item.get("buy", 0) for item in theirs)
        assert sum(count["imbalance_sell"] for count in mine) == sum(item.get("sell", 0) for item in theirs)
        for block, bar in zip(marked["bars"], bars):
            pack = (bar.get("calc") or {}).get("poc") or {}
            assert block["poc"]["price"] == pack.get("price"), f"{symbol}: POC disagrees"
    assert checked >= 2, "the generator modelled nothing — the check did not run"


# ── the routes ──────────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(monkeypatch):
    """This router on a bare app, with the config store booby-trapped: nothing here may read or
    write the user's config (the parent owns persistence)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from orderflow_system.desktop import config_store

    def explode(*_args, **_kwargs):
        raise AssertionError("footprint_config touched the config store")

    monkeypatch.setattr(config_store, "save_config", explode, raising=False)
    monkeypatch.setattr(config_store, "merge_config", explode, raising=False)
    monkeypatch.setattr(config_store, "load_config", explode, raising=False)
    app = FastAPI()
    app.include_router(fp.router)
    return TestClient(app)


def test_get_returns_the_block_the_defaults_and_every_control(client):
    answer = client.get("/api/atlas/footprint/config").json()
    assert answer["ok"] is True and answer["source"] == "defaults"
    assert answer["block"] == fp.DEFAULTS and answer["detail"] is None
    assert {row["key"] for row in answer["capabilities"]} == set(fp.DEFAULTS)
    assert answer["capabilities"][0]["path"].startswith("atlas.footprint.")


def test_get_validates_a_supplied_block_and_never_writes_config(client):
    body = json.dumps({"imbalance_threshold": 99, "cell_metric": "delta", "nope": 1})
    answer = client.get("/api/atlas/footprint/config", params={"settings": body}).json()
    assert answer["ok"] is True and answer["source"] == "supplied"
    assert answer["block"]["imbalance_threshold"] == 50.0
    assert answer["block"]["cell_metric"] == "delta" and "nope" not in answer["block"]
    junk = client.get("/api/atlas/footprint/config", params={"settings": "{not json"}).json()
    assert junk["ok"] is True and junk["source"] == "defaults"
    assert junk["detail"] == fp.REFUSAL_SETTINGS_TEXT
    assert junk["block"] == fp.DEFAULTS


def test_post_accepts_a_patch_and_refuses_a_body_it_cannot_read(client):
    answer = client.post("/api/atlas/footprint/config",
                         json={"stack_min_levels": 4, "imbalance_mode": "both"}).json()
    assert answer["ok"] is True
    assert answer["block"]["stack_min_levels"] == 4
    assert answer["block"]["imbalance_mode"] == "both"
    assert sorted(answer["changed"]) == ["imbalance_mode", "stack_min_levels"]
    assert answer["block"] == fp.clean({"stack_min_levels": 4, "imbalance_mode": "both"})

    refused = client.post("/api/atlas/footprint/config", json=["not", "an", "object"]).json()
    assert refused["ok"] is False and refused["detail"] == fp.REFUSAL_PATCH
    assert refused["block"] == fp.DEFAULTS

    junk = client.post("/api/atlas/footprint/config",
                       json={"ticks_per_row": "junk", "poc_per_bar": None}).json()
    assert junk["ok"] is True and junk["block"]["ticks_per_row"] == 1
    assert junk["block"]["poc_per_bar"] is fp.DEFAULTS["poc_per_bar"]
    assert client.post("/api/atlas/footprint/config").json()["block"] == fp.DEFAULTS


# ── the panel module: its selftest, and the two implementations held equal ───────────────────────


def _node(script: str, *args: str) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    if not node:                                     # pragma: no cover - node ships with the build
        pytest.skip("node is not on PATH")
    return subprocess.run([node, "-e", script, *args], capture_output=True, text=True, encoding="utf-8", timeout=120)


def _js_annotate(fixture: dict) -> dict:
    script = (
        "const fs=require('fs');"
        f"const src=fs.readFileSync({json.dumps(str(MODULE))},'utf8');"
        "const win={};"
        "new Function('window','document',src)(win, undefined);"
        "const fixture=JSON.parse(process.argv[1]);"
        "const api=win.OFAPFOOTPRINT;"
        "let out;"
        "if(fixture.bars){out=api.annotateBars(fixture.bars, fixture.settings, fixture.tickSize||0);}"
        "else{out=api.annotateBar(fixture.levels, fixture.settings, fixture.bar||null, fixture.tickSize||0);}"
        "console.log(JSON.stringify(out));"
    )
    proc = _node(script, json.dumps(fixture))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _compare(ours, theirs, path: str, problems: list[str]) -> None:
    """Structure first, then numbers with a tolerance: two languages will not agree to the last bit."""
    if isinstance(ours, dict) and isinstance(theirs, dict):
        if set(ours) != set(theirs):
            missing = sorted(set(ours) ^ set(theirs))
            problems.append(f"{path}: keys differ {missing}")
            return
        for key in ours:
            _compare(ours[key], theirs[key], f"{path}.{key}", problems)
        return
    if isinstance(ours, list) and isinstance(theirs, list):
        if len(ours) != len(theirs):
            problems.append(f"{path}: {len(ours)} rows here, {len(theirs)} there")
            return
        for index, (left, right) in enumerate(zip(ours, theirs)):
            _compare(left, right, f"{path}[{index}]", problems)
        return
    if isinstance(ours, bool) or isinstance(theirs, bool):
        if ours != theirs:
            problems.append(f"{path}: {ours!r} != {theirs!r}")
        return
    if isinstance(ours, (int, float)) and isinstance(theirs, (int, float)):
        if abs(ours - theirs) > 1e-9 * max(1.0, abs(ours)):
            problems.append(f"{path}: {ours} != {theirs}")
        return
    if ours != theirs:
        problems.append(f"{path}: {ours!r} != {theirs!r}")


PARITY_CASES = [
    ("same-price and stacks", {"levels": SAME_PRICE_LEVELS}),
    ("a hand-tuned block", {"levels": SAME_PRICE_LEVELS,
                            "settings": {"imbalance_mode": "both", "imbalance_threshold": 2.5,
                                         "stack_min_levels": 2, "cell_metric": "delta",
                                         "value_area_pct": 0.9, "ticks_per_row": 2}}),
    ("diagonal", {"levels": DIAGONAL_LEVELS, "settings": {"imbalance_mode": "both"}}),
    ("a half-step ladder", {"levels": HALF_STEP_LEVELS, "settings": {"imbalance_mode": "both"}}),
    ("absorption and a body", {"levels": ABSORPTION_LEVELS, "bar": ABSORPTION_BAR}),
    ("absorption without a body", {"levels": ABSORPTION_LEVELS}),
    ("clustered rows and counts", {"levels": CLUSTER_LEVELS, "tickSize": 0.25,
                                   "settings": {"ticks_per_row": 2, "cell_metric": "count"}}),
    ("a filtered bar", {"levels": ABSORPTION_LEVELS, "settings": {"min_level_volume": 50}}),
    ("a session-excluded bar", {"levels": SAME_PRICE_LEVELS,
                                "settings": {"session_filter": "rth"},
                                "bar": {"time": "2026-09-18T02:00:00Z"}}),
    ("junk settings", {"levels": SAME_PRICE_LEVELS,
                       "settings": {"imbalance_threshold": "junk", "cell_metric": "PRINTS",
                                    "poc_per_bar": 0, "ticks_per_row": 500}}),
    ("no usable rows", {"levels": [None, {"price": "abc"}]}),
    ("a whole payload", {"bars": [{"levels": SAME_PRICE_LEVELS, "time": "2026-09-18T14:00:00Z",
                                   "open": 100.0, "high": 103.0, "low": 99.5, "close": 102.0},
                                  {"levels": CLUSTER_LEVELS, "time": "2026-09-18T02:00:00Z"}],
                         "settings": {"session_filter": "rth", "ticks_per_row": 1}}),
    ("a zone-less T-stamp is read by both engines", {"levels": SAME_PRICE_LEVELS,
                                                      "settings": {"session_filter": "rth"},
                                                      "bar": {"time": "2026-09-18T14:00:00"}}),
    ("a basic date form is refused by both engines", {"levels": SAME_PRICE_LEVELS,
                                                       "settings": {"session_filter": "rth"},
                                                       "bar": {"time": "20260918"}}),
]


@pytest.mark.parametrize("name,fixture", PARITY_CASES, ids=[case[0] for case in PARITY_CASES])
def test_the_python_and_javascript_readings_agree(name, fixture):
    payload = dict(fixture)
    payload.setdefault("settings", None)
    theirs = _js_annotate(payload)
    if payload.get("bars"):
        ours = fp.annotate_bars(payload["bars"], payload["settings"],
                                tick_size=payload.get("tickSize", 0.0))
    else:
        ours = fp.annotate_bar(payload.get("levels"), payload["settings"], bar=payload.get("bar"),
                               tick_size=payload.get("tickSize", 0.0))
    problems: list[str] = []
    _compare(ours, theirs, name, problems)
    assert not problems, "python and javascript disagree:\n" + "\n".join(problems[:12])


def test_a_half_step_price_keys_onto_the_row_the_panel_keys():
    """T6-F06 (§148): a price exactly half a step up — 100.25 at a 0.5 tick — keys onto step 201, the
    row `Math.round` gives it, not step 200 (Python's half-to-even). Keyed low, the row's diagonal
    comparison loses its neighbour above and falls back to its own ask, inventing a sell mark the
    panel never draws.
    """
    rows = [dict(level) for level in HALF_STEP_LEVELS]
    cfg = fp.clean(None)
    readings = fp._readings(rows, 0.5, cfg)
    assert [fp._ladder_key(row["price"], 0.5) for row in rows] == [201, 202, 203]
    assert readings[0]["diagonal"]["side"] is None, \
        "100.25 compares its bid against 100.75's ask (30): 20/30 is no diagonal sell"
    assert readings[0]["diagonal"]["ratio"] is None or readings[0]["diagonal"]["ratio"] < 3.0


def test_the_panel_module_and_its_selftest_are_where_the_parent_wires_them():
    assert MODULE.is_file() and SELFTEST.is_file()
    text = MODULE.read_text(encoding="utf-8", errors="replace")
    assert "window.OFAPFOOTPRINT" in text
    assert "addEventListener" not in text, "the panel is listener-free by design (no ledger entry)"
    assert "setInterval" not in text, "the panel has no timers to guard"
    assert "/api/atlas/footprint/config" in text, "the drawer must call its own route literally"


def test_the_selftest_runs_green_under_node():
    node = shutil.which("node")
    if not node:                                     # pragma: no cover
        pytest.skip("node is not on PATH")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "failed" in proc.stdout and "0 failed" in proc.stdout, proc.stdout


def test_the_bar_time_reader_holds_the_one_shape_both_engines_read():
    """T6-F7 (§148): the Python half accepts ISO stamps with or without a zone (zone-less = UTC),
    and the panel's Date.parse does the same. The shapes only Python parses — the basic 20260918
    form and the space separator — are refused by both, so neither marks a bar the other cannot see.
    """
    from orderflow_system.atlas.footprint_config import _epoch_ms
    assert _epoch_ms("2026-09-18T14:00:00") == _epoch_ms("2026-09-18T14:00:00Z")
    assert _epoch_ms("2026-09-18 14:00:00") is None
    assert _epoch_ms("20260918") is None
    assert fp.session_verdict("2026-09-18T14:00:00", {"session_filter": "rth"}) == "in"
    assert fp.session_verdict("2026-09-18T02:00:00", {"session_filter": "rth"}) == "out"
