"""W3: depth history — recording, bucketing, pull/add detection, retention, gaps, the refusal path.

Offline and deterministic: every timestamp is built from the real clock at import, and every query
that takes a clock takes ``now_ms`` explicitly, so nothing here depends on how long the suite takes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from orderflow_system.atlas import depth_history as dh
from orderflow_system.desktop import config_store

#: The grid the fixtures are stamped on — minute-aligned and just in the past, so bucket
#: arithmetic is exact and the retention window has something real to keep.
BASE = ((int(time.time() * 1000) - 120_000) // 60_000) * 60_000


def _store(**settings) -> dh.DepthHistoryStore:
    block = dict(dh.DEFAULTS)
    block.update(settings)
    return dh.DepthHistoryStore(block)


def _book(mid: float = 100.0, levels: int = 4, size: float = 10.0) -> dict[float, tuple[float, float]]:
    """A symmetric book around ``mid``: ``levels`` rows each side, ``size`` on each."""
    out = {}
    for i in range(levels):
        out[round(mid - 0.5 - i, 2)] = (size, 0.0)
        out[round(mid + 0.5 + i, 2)] = (0.0, size)
    return out


def _fill(store: dh.DepthHistoryStore, symbol: str, count: int, *, start: int = BASE,
          step: int = 1000, book=None) -> None:
    for i in range(count):
        store.record(symbol, start + i * step, book or _book())


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(dh.router)
    return app


def _client(store: dh.DepthHistoryStore) -> TestClient:
    """My router alone, on a bare app: the route table and the refusals are what is under test."""
    dh.set_store(store)
    return TestClient(_app())


@pytest.fixture(autouse=True)
def _hand_the_store_back():
    """§148 T6-F11: `_client` installs a store and nothing put the process singleton back, so the
    last test in this file decided what every later reader saw. The fixture hands it back."""
    before = dh._STORE
    yield
    dh.set_store(before)


# ── clean(): the settings block ─────────────────────────────────────────────

def test_clean_returns_only_the_block_and_never_raises():
    assert dh.clean(None) == dh.DEFAULTS
    assert dh.clean("junk") == dh.DEFAULTS
    assert dh.clean([]) == dh.DEFAULTS
    out = dh.clean({"unknown_key": 1, "retention_minutes": 15})
    assert set(out) == set(dh.DEFAULTS), "unknown keys must be dropped"
    assert out["retention_minutes"] == 15
    assert dh.DEFAULTS["retention_minutes"] == 30 and dh.DEFAULTS["interval_ms"] == 1000


def test_clean_coerces_strings_booleans_and_junk():
    assert dh.clean({"retention_minutes": "45"})["retention_minutes"] == 45
    assert dh.clean({"retention_minutes": "junk"})["retention_minutes"] == dh.DEFAULTS["retention_minutes"]
    assert dh.clean({"enabled": "off"})["enabled"] is False
    assert dh.clean({"enabled": "yes"})["enabled"] is True
    assert dh.clean({"enabled": 0})["enabled"] is False
    assert dh.clean({"pull_pct": "0.75"})["pull_pct"] == 0.75
    assert dh.clean({"min_size": None})["min_size"] == dh.DEFAULTS["min_size"]


def test_clean_clamps_every_knob_to_a_usable_range():
    assert dh.clean({"retention_minutes": 0})["retention_minutes"] == 1
    assert dh.clean({"retention_minutes": 99999})["retention_minutes"] == 1440
    assert dh.clean({"max_columns_per_symbol": 1})["max_columns_per_symbol"] == 60
    assert dh.clean({"max_columns_per_symbol": 10**9})["max_columns_per_symbol"] == 20000
    assert dh.clean({"max_symbols": 0})["max_symbols"] == 1
    assert dh.clean({"max_symbols": 999})["max_symbols"] == 64
    assert dh.clean({"interval_ms": 10})["interval_ms"] == 200
    assert dh.clean({"interval_ms": 10**9})["interval_ms"] == 60000
    assert dh.clean({"max_levels": 1})["max_levels"] == 5
    assert dh.clean({"max_levels": 10**9})["max_levels"] == 400
    assert dh.clean({"pull_pct": 2.0})["pull_pct"] == 0.99
    assert dh.clean({"add_pct": -1})["add_pct"] == 0.05
    assert dh.clean({"gap_multiple": 1})["gap_multiple"] == 2
    assert dh.clean({"gap_multiple": 10**6})["gap_multiple"] == 240
    assert dh.clean({"bands": 1})["bands"] == 2
    assert dh.clean({"bands": 99})["bands"] == 32
    # a bucket narrower than the column grid would repeat columns under one time axis
    assert dh.clean({"interval_ms": 5000, "bucket_ms": 1000})["bucket_ms"] == 5000
    assert dh.clean({"bucket_ms": 60000})["bucket_ms"] == 60000


# ── recording ───────────────────────────────────────────────────────────────

def test_record_folds_one_grid_cell_and_counts_what_it_did():
    store = _store()
    store.record("btcusdt", BASE, _book())
    store.record("BTCUSDT", BASE + 400, _book())          # same 1 s cell: folded, not a new column
    store.record("BTCUSDT", BASE + 1200, _book())
    assert store.columns() == 2, "one column per grid cell, not per update"
    assert store.counters["records"] == 3 and store.counters["folded"] == 1
    assert store.has("BTCUSDT") and not store.has("ETHUSDT"), "symbols are normalised, not case-folded apart"
    assert store.bounds("BTCUSDT") == (BASE, BASE + 1000), "columns land on the grid"


def test_a_folded_cell_holds_the_newest_book_not_a_union():
    """T6-F02 (§148): the same-cell fold unioned every book that landed inside the cell — one 1 s
    cell could hold many times ``max_levels`` of prices, including sizes no book was showing any
    more. The cell is the interval's newest snapshot, the module's own doctrine.
    """
    store = _store()
    store.record("BTCUSDT", BASE, _book())
    store.record("BTCUSDT", BASE + 400, {99.5: (1.0, 0.0), 100.5: (0.0, 1.0)})
    cell = store._cols["BTCUSDT"][-1]
    assert set(cell.levels) == {99.5, 100.5}, \
        f"the fold kept prices no book showed any more: {sorted(cell.levels)}"
    assert cell.levels[99.5] == (1.0, 0.0)
    assert cell.updates == 2 and store.counters["folded"] == 1

    # and growth past one book's ceiling is structurally impossible: eight books, one cell, <= 5
    small = _store(max_levels=5)
    for step in range(8):
        small.record("BTCUSDT", BASE + step * 50, _book(levels=4))
    assert len(small._cols["BTCUSDT"][-1].levels) <= 5, \
        "a cell can hold no more levels than the newest book may carry"
    assert small.columns("BTCUSDT") == 1


def test_a_late_frame_never_reorders_the_record():
    """T6-F03 (§148): a book stamped older than the newest column was appended anyway — the record
    ran out of time order and one late frame read as phantom gaps with a collapsed span. A late book
    folds into its own cell when that is the last cell; anything older is skipped and counted.
    """
    store = _store()
    _fill(store, "BTCUSDT", 6)                          # six 1 s columns: BASE .. BASE+5000
    late = store.record("BTCUSDT", BASE + 2000, _book())
    assert late == 6 and store.counters["late_skipped"] == 1, \
        "a book older than the newest column is not the newer truth"
    assert [col.ts_ms for col in store._cols["BTCUSDT"]] == [BASE + i * 1000 for i in range(6)], \
        "the record stays monotonic"
    report = store.gaps("BTCUSDT")
    assert report["count"] == 0 and report["span_ms"] == 5000, \
        f"no phantom gap, no collapsed span: {report}"

    # a late book for the CELL ALREADY RECORDED is that cell's own snapshot and still folds
    store.record("BTCUSDT", BASE + 5400, _book(levels=2))
    assert store.counters["folded"] == 1 and store.counters["late_skipped"] == 1


def test_a_future_stamped_book_never_enters_the_record():
    """T6-F04 (§148): a book stamped far in the future was kept, sat past every prune cutoff,
    stood outside every replay window, and the newest-column staleness read "fresh" over it — a
    column nothing can see. Beyond a minute the stamp falls back to the stream's own clock, the
    same contract junk stamps get, and the refusal is counted. Skew within the tolerance is kept.
    """
    store = _store()
    _fill(store, "BTCUSDT", 3)                        # BASE .. BASE+2000, ~2 min in the past
    now = int(time.time() * 1000)
    columns = store.record("BTCUSDT", now + 86_400_000, _book())      # a day ahead: unreadable
    assert store.counters["future_skipped"] == 1, "the refusal is counted"
    assert columns == 4, "the book lands — at the stream's clock, never under the day-ahead stamp"
    stamps = [col.ts_ms for col in store._cols["BTCUSDT"]]
    assert max(stamps) <= now, f"a future column entered the record: {stamps}"
    age = store.staleness("BTCUSDT", now_ms=now)
    assert age["last_ms"] == max(stamps) and age["age_ms"] == now - max(stamps), \
        "the staleness reader describes the column the record really holds, not one nobody can see"
    report = store.series("BTCUSDT", now_ms=now)
    assert report["ok"] is True and all(b["ts_ms"] <= now for b in report["buckets"]), \
        "every drawn bucket is in the past"

    # skew: two seconds ahead of the wall clock is a real venue's clock, not a broken one
    ahead = now + 2000
    store.record("BTCUSDT", ahead, _book())
    assert store.counters["future_skipped"] == 1, "ordinary skew is not a refusal"
    stamps = [col.ts_ms for col in store._cols["BTCUSDT"]]
    assert max(stamps) >= ahead - 1000, f"the skewed stamp was kept as it stands: {stamps}"


def test_record_refuses_empty_books_and_unknown_input_without_raising():
    store = _store()
    assert store.record("", BASE, _book()) == 0
    assert store.record("BTCUSDT", BASE, None) == 0
    assert store.record("BTCUSDT", BASE, {}) == 0
    assert store.record("BTCUSDT", BASE, {"not a price": "x"}) == 0
    assert store.record("BTCUSDT", BASE, ["junk", object(), (1,)]) == 0
    assert store.record("BTCUSDT", BASE, object()) == 0
    assert store.columns() == 0, "nothing recorded, nothing invented"
    assert store.counters["refused"] == 1 and store.counters["empty_books"] == 5


def test_record_is_disabled_by_config_and_says_so():
    store = _store(enabled=False)
    assert store.record("BTCUSDT", BASE, _book()) == 0
    assert store.columns() == 0 and store.counters["refused"] == 1
    payload = store.series("BTCUSDT")
    assert payload["ok"] is False and payload["detail"] == dh.empty_note("BTCUSDT")


def test_record_survives_the_timestamp_shapes_the_feeds_send():
    store = _store(interval_ms=1000)
    store.record("BTCUSDT", BASE // 1000, _book())        # epoch seconds -> ms
    store.record("BTCUSDT", 1, _book())                   # an update id, not a clock
    store.record("BTCUSDT", "junk", _book())
    first, last = store.bounds("BTCUSDT")
    assert first == BASE, "the seconds stamp landed on the grid it really meant"
    assert last >= first and 1 <= store.columns() <= 3, "a clock we cannot read falls back, never a hole"


def test_prices_are_snapped_to_the_tick_grid_when_the_caller_knows_it():
    """A 0.01-tick venue hands over 99.499999999: one level, not two rows nobody can tell apart."""
    store = _store()
    store.record("BTCUSDT", BASE, {99.499999999: (3.0, 0.0), 99.5: (2.0, 0.0), 100.5: (0.0, 4.0)},
                 tick_size=0.01)
    kept = store._cols["BTCUSDT"][-1].levels
    assert kept == {99.5: (5.0, 0.0), 100.5: (0.0, 4.0)}, kept

    unset = _store()
    unset.record("BTCUSDT", BASE, {99.499999999: (3.0, 0.0), 99.5: (2.0, 0.0)})
    assert len(unset._cols["BTCUSDT"][-1].levels) == 2, "no tick size given: the venue's prices stand"


def test_coerce_levels_reads_every_shape_the_repo_hands_over():
    snapshot = SimpleNamespace(
        bids=[SimpleNamespace(price=99.5, quantity=3.0), SimpleNamespace(price=99.0, quantity=2.0)],
        asks=[SimpleNamespace(price=100.5, quantity=4.0)])
    book, guessed = dh.coerce_levels(snapshot)
    assert book == {99.5: (3.0, 0.0), 99.0: (2.0, 0.0), 100.5: (0.0, 4.0)} and guessed == 0

    book, _g = dh.coerce_levels({99.5: (3.0, 0.0), 100.5: {"bid": 0.0, "ask": 4.0}})
    assert book == {99.5: (3.0, 0.0), 100.5: (0.0, 4.0)}

    rows = [{"price": 99.5, "side": "bid", "size": 3.0}, {"price": 100.5, "side": "ask", "size": 4.0},
            (98.5, 1.0, 1.5)]
    book, _g = dh.coerce_levels(rows)
    assert book[99.5] == (3.0, 0.0) and book[100.5] == (0.0, 4.0) and book[98.5] == (1.0, 1.5)

    # a bare size with no side goes below the mid for a bid and above it for an ask — counted
    book, guessed = dh.coerce_levels({99.5: (5.0, 0.0), 100.5: (0.0, 5.0), 99.0: 2.0, 101.0: 3.0})
    assert guessed == 2 and book[99.0] == (2.0, 0.0) and book[101.0] == (0.0, 3.0)

    assert dh.coerce_levels("nonsense") == ({}, 0)


def test_levels_are_trimmed_to_the_ones_nearest_the_mid():
    store = _store(max_levels=6)
    store.record("BTCUSDT", BASE, _book(levels=10, size=5.0))
    kept = store._cols["BTCUSDT"][-1].levels
    assert len(kept) == 6 and store.counters["levels_trimmed"] == 14
    # the three rows each side of a 100.0 mid, not the 90.5/109.5 ends of a 20-level book
    assert sorted(kept) == [97.5, 98.5, 99.5, 100.5, 101.5, 102.5]


# ── the series ──────────────────────────────────────────────────────────────

def test_buckets_summarise_totals_biggest_and_the_weighted_mid():
    store = _store()
    book = {99.5: (10.0, 0.0), 100.5: (0.0, 10.0), 99.0: (30.0, 0.0), 101.0: (0.0, 2.0)}
    _fill(store, "BTCUSDT", 12, book=book)
    payload = store.series("BTCUSDT", bucket_ms=5000)

    assert payload["ok"] is True and payload["detail"] == ""
    assert payload["bucket_ms"] == 5000 and payload["bucket_ms_requested"] == 5000
    assert [b["ts_ms"] for b in payload["buckets"]] == [BASE, BASE + 5000, BASE + 10000]
    assert [b["columns"] for b in payload["buckets"]] == [5, 5, 2]
    first = payload["buckets"][0]
    assert first["total_bid"] == 40.0 and first["total_ask"] == 12.0 and first["total"] == 52.0
    assert first["biggest"] == {"price": 99.0, "size": 30.0, "side": "bid", "share": round(30.0 / 52.0, 4)}
    assert first["best_bid"] == 99.5 and first["best_ask"] == 100.5 and first["spread"] == 1.0
    # micro-price: each side weighted by the other side's size (10 vs 10 -> the plain mid)
    assert first["weighted_mid"] == 100.0
    assert payload["busiest_bucket"] == {"ts_ms": BASE, "total": 52.0}
    assert payload["levels"] == 12 * 4
    assert payload["have_from_ms"] == BASE and payload["have_to_ms"] == BASE + 11000
    assert payload["buckets"][0]["at_ms"] == BASE + 4000, "the cell is the label, at_ms is the reading"

    bands = payload["profile"]
    assert len(bands) == dh.DEFAULTS["bands"]
    assert round(sum(b["bid"] for b in bands), 6) == round(sum(b["total_bid"] for b in payload["buckets"]), 6)
    assert round(sum(b["ask"] for b in bands), 6) == round(sum(b["total_ask"] for b in payload["buckets"]), 6)
    assert payload["peak_band"] == max(bands, key=lambda b: b["total"])
    assert payload["bands"][0] < payload["bands"][-1]
    assert bands[-1]["ask"] == 2.0 * 3, "one 2.0 level in the top band of each of the three buckets"


def test_series_widens_the_bucket_rather_than_building_a_huge_payload():
    store = _store()
    _fill(store, "BTCUSDT", 60)
    payload = store.series("BTCUSDT", bucket_ms=1000)
    assert len(payload["buckets"]) == 60 and payload["bucket_ms"] == 1000

    cols = list(store._cols["BTCUSDT"])
    wide = dh.series_of(cols, bucket_ms=1000, interval_ms=1000, max_buckets=5)
    assert wide["bucket_ms"] > 1000, "a window that cannot fit the cell ceiling is answered wider"
    assert len(wide["buckets"]) <= 5 and wide["bucket_ms_requested"] == 1000
    assert wide["buckets"][-1]["ts_ms"] <= BASE + 59000


def test_series_honours_the_requested_window():
    store = _store()
    _fill(store, "BTCUSDT", 10)
    payload = store.series("BTCUSDT", from_ms=BASE + 4000, to_ms=BASE + 7000, bucket_ms=1000)
    assert [b["ts_ms"] for b in payload["buckets"]] == [BASE + 4000, BASE + 5000,
                                                       BASE + 6000, BASE + 7000]
    assert payload["from_ms"] == BASE + 4000 and payload["to_ms"] == BASE + 7000
    assert payload["span_ms"] == 3000


# ── pull / add ──────────────────────────────────────────────────────────────

def test_pull_and_add_detection_on_a_small_fixture():
    store = _store()
    store.record("BTCUSDT", BASE, {100.0: (100.0, 20.0), 99.5: (40.0, 0.0), 101.0: (0.0, 3.0)})
    store.record("BTCUSDT", BASE + 1000, {100.0: (30.0, 20.0), 99.5: (70.0, 0.0),
                                          101.0: (0.0, 2.0), 98.5: (5.0, 0.0)})
    events = store.events("BTCUSDT")
    found = {(e["kind"], e["price"], e["side"]): e for e in events}

    # 100.0 lost 70 of 100 on the bid: a pull, with the size and the share both recorded
    pull = found[("pull", 100.0, "bid")]
    assert pull["size"] == 70.0 and pull["from"] == 100.0 and pull["to"] == 30.0 and pull["pct"] == 0.7
    assert pull["ts_ms"] == BASE + 1000
    # 99.5 stacked 30 onto 40: an add
    add = found[("add", 99.5, "bid")]
    assert add["size"] == 30.0 and add["pct"] == 0.75
    # a level that was not on the book at all is an add too (share 1.0, never a division by zero)
    fresh = found[("add", 98.5, "bid")]
    assert fresh["from"] == 0.0 and fresh["pct"] is None
    # 3 -> 2 is under the relative floor (50% of 3 = 1.5), so it is a wiggle, not an event
    assert ("pull", 101.0, "ask") not in found
    assert len(events) == 3 and all(e["size"] > 0 for e in events)
    assert [(e["ts_ms"], e["price"]) for e in events] == sorted((e["ts_ms"], e["price"]) for e in events)


def test_the_event_floor_is_absolute_as_well_as_relative():
    store = _store(min_size=10.0)
    store.record("BTCUSDT", BASE, {100.0: (1000.0, 0.0)})
    store.record("BTCUSDT", BASE + 1000, {100.0: (400.0, 0.0)})     # -600, well past 50%
    assert [e["kind"] for e in store.events("BTCUSDT")] == ["pull"]
    store.record("BTCUSDT", BASE + 2000, {100.0: (395.0, 0.0)})     # -5: under the 10 floor
    assert len(store.events("BTCUSDT")) == 1, "a five-lot flicker is not a pulled level"

    wide = _store(pull_pct=0.2, min_size=0.0)
    wide.record("BTCUSDT", BASE, {100.0: (10.0, 10.0)})
    wide.record("BTCUSDT", BASE + 1000, {100.0: (5.0, 10.0)})
    assert [e["side"] for e in wide.events("BTCUSDT")] == ["bid"]


def test_one_price_can_pull_on_one_side_and_stack_on_the_other():
    store = _store()
    store.record("BTCUSDT", BASE, {100.0: (50.0, 4.0), 99.0: (20.0, 0.0)})
    store.record("BTCUSDT", BASE + 1000, {100.0: (10.0, 12.0), 99.0: (20.0, 0.0)})
    events = store.events("BTCUSDT")
    assert [(e["kind"], e["side"], e["size"]) for e in events] == [("pull", "bid", 40.0),
                                                                   ("add", "ask", 8.0)]


def test_only_the_biggest_events_survive_a_crowded_window_and_stay_in_time_order():
    store = _store()
    keep = {99.0: (1.0, 1.0)}
    booked = dict(keep)
    booked.update({float(100 + i): (100.0, 0.0) for i in range(30)})
    store.record("BTCUSDT", BASE, booked)
    store.record("BTCUSDT", BASE + 1000, keep)
    events = store.events("BTCUSDT", limit=5)
    assert len(events) == 5
    assert all(e["kind"] == "pull" and e["size"] == 100.0 for e in events)
    assert [e["ts_ms"] for e in events] == [BASE + 1000] * 5

    every = store.events("BTCUSDT")
    assert len(every) == 30, "the cap keeps the biggest; the uncapped read is the whole tail"
    assert store.series("BTCUSDT", limit_events=0)["events"] == [], "a caller can ask for no events"


# ── gaps, staleness, retention ──────────────────────────────────────────────

def test_gaps_report_the_holes_and_the_coverage():
    store = _store()
    _fill(store, "BTCUSDT", 3)
    store.record("BTCUSDT", BASE + 8000, _book())        # a 6000 ms hole after BASE + 2000
    report = store.gaps("BTCUSDT")
    assert report["count"] == 1 and report["largest_ms"] == 6000 and report["missing_ms"] == 6000
    hole = report["gaps"][0]
    assert hole["from_ms"] == BASE + 2000 and hole["to_ms"] == BASE + 8000 and hole["missing_ms"] == 5000
    assert report["span_ms"] == 8000 and report["covered_pct"] == 25.0

    quiet = _store()
    _fill(quiet, "BTCUSDT", 3)
    assert quiet.gaps("BTCUSDT") == {"gaps": [], "count": 0, "largest_ms": 0, "missing_ms": 0,
                                     "span_ms": 2000, "covered_pct": 100.0}


def test_staleness_speaks_the_apps_own_words():
    fresh = dh.staleness_of(BASE, BASE + 1000, interval_ms=1000)
    assert fresh["state"] == "fresh" and fresh["age_ms"] == 1000
    aging = dh.staleness_of(BASE, BASE + 5000, interval_ms=1000)
    assert aging["state"] == "aging" and aging["text"].startswith("quiet")
    stale = dh.staleness_of(BASE, BASE + 60_000, interval_ms=1000)
    assert stale["state"] == "stale" and "no depth for" in stale["text"]
    empty = dh.staleness_of(0, BASE, interval_ms=1000)
    assert empty["state"] == "empty" and empty["text"] == "nothing recorded yet"


def test_retention_prunes_by_count_and_symbol_ceiling():
    # 30 minutes of retention: nothing here is old enough for the clock, so the count is the subject
    store = _store(retention_minutes=30, max_columns_per_symbol=60, max_symbols=2)
    _fill(store, "BTCUSDT", 65)                          # 65 s of columns into a 60-column ceiling
    assert store.columns("BTCUSDT") == 60 and store.counters["dropped_columns"] >= 5
    assert store.bounds("BTCUSDT") == (BASE + 5000, BASE + 64000)

    # three symbols into a two-symbol store: the least recently fed one goes
    store.record("ETHUSDT", BASE + 1000, _book())
    store.record("SOLUSDT", BASE + 1000, _book())
    store.record("XRPUSDT", BASE + 1000, _book())
    assert store.has("SOLUSDT") and store.has("XRPUSDT")
    assert not store.has("BTCUSDT") and not store.has("ETHUSDT")
    assert store.counters["dropped_symbols"] >= 2

    stats = store.stats()
    assert stats["symbols"] == 2 and stats["columns"] <= 2 * 60
    assert stats["retained_levels"] <= stats["columns"] * dh.DEFAULTS["max_levels"]
    assert stats["retention_ms"] == 30 * 60_000 and stats["interval_ms"] == 1000


def test_retention_prunes_by_time_and_the_leash_is_the_record_path():
    now = int(time.time() * 1000)
    store = _store(retention_minutes=1)
    # the implicit one-second leash is exercised below; here the explicit prune is the subject
    store._last_prune_ms = now
    store.record("BTCUSDT", now - 10 * 60_000, _book())
    store.record("BTCUSDT", now - 5_000, _book())
    assert store.columns("BTCUSDT") == 2

    report = store.prune(now)
    assert report["dropped_columns"] == 1 and report["cutoff_ms"] == now - 60_000
    assert report["columns"] == 1 and report["symbols"] == 1
    fresh = (now - 5_000) // 1000 * 1000
    assert store.bounds("BTCUSDT") == (fresh, fresh), "the aged column went, the fresh one stayed"

    # a record is what prunes: an aged book never even settles in the store
    leashed = _store(retention_minutes=1)
    leashed.record("BTCUSDT", now - 10 * 60_000, _book())
    assert leashed.columns("BTCUSDT") == 0 and not leashed.has("BTCUSDT")
    assert leashed.counters["dropped_columns"] == 1 and leashed.counters["prunes"] == 1


def test_clear_forgets_one_symbol_or_all_of_them_and_symbols_lists_what_is_held():
    store = _store()
    near = ((int(time.time() * 1000) - 2_000) // 1000) * 1000
    _fill(store, "BTCUSDT", 3)
    _fill(store, "ETHUSDT", 2, start=near)
    rows = store.symbols()
    assert [r["symbol"] for r in rows] == ["ETHUSDT", "BTCUSDT"], "the newest book first"
    assert rows[0]["columns"] == 2 and rows[0]["levels"] == 16 and rows[0]["span_ms"] == 1000
    assert rows[0]["state"] == "fresh" and rows[0]["total_bid"] == 40.0 and rows[0]["total_ask"] == 40.0

    assert store.clear("BTCUSDT")["cleared"] == "BTCUSDT"
    assert not store.has("BTCUSDT") and store.has("ETHUSDT")
    assert store.clear()["cleared"] == "*" and store.columns() == 0 and store.symbols() == []


def test_configure_reprunes_immediately_so_a_shorter_retention_frees_memory():
    now = int(time.time() * 1000)
    store = _store(retention_minutes=30)
    store.record("BTCUSDT", now - 90_000, _book())        # a minute and a half old
    store.record("BTCUSDT", now - 5_000, _book())
    assert store.columns("BTCUSDT") == 2
    applied = store.configure({"retention_minutes": 1, "max_symbols": "junk", "bands": 999})
    assert applied["retention_minutes"] == 1 and applied["max_symbols"] == dh.DEFAULTS["max_symbols"]
    assert applied["bands"] == 32
    assert store.columns("BTCUSDT") == 1, "the older column went with the retention change"


# ── the routes ──────────────────────────────────────────────────────────────

def test_the_router_declares_the_documented_paths():
    paths = {getattr(r, "path", "") for r in dh.router.routes}
    assert "/api/atlas/depth-history" in paths
    assert "/api/atlas/depth-history/{symbol}" in paths
    assert "/api/atlas/depth-history/retention" in paths
    assert "/api/atlas/depth-history/clear" in paths
    assert dh.router.prefix == "/api/atlas"


def test_the_get_route_refuses_an_instrument_with_no_depth():
    store = _store()
    client = _client(store)
    answer = client.get("/api/atlas/depth-history/NOPEUSDT")
    assert answer.status_code == 200
    body = answer.json()
    assert body["ok"] is False
    assert body["detail"] == ("no depth recorded yet for NOPEUSDT — leave the heatmap open for a "
                              "minute and it will start filling")
    assert body["buckets"] == [] and body["events"] == [] and body["profile"] == []


def test_the_get_route_serves_the_series_and_says_why_a_window_is_empty():
    store = _store()
    _fill(store, "BTCUSDT", 30)
    client = _client(store)
    body = client.get(f"/api/atlas/depth-history/btcusdt?from_ms={BASE}&to_ms={BASE + 29000}"
                      "&bucket_ms=1000").json()
    assert body["ok"] is True and body["symbol"] == "BTCUSDT"
    assert len(body["buckets"]) == 30 and body["bucket_ms"] == 1000
    assert body["retained"]["columns"] == 30 and body["settings"]["retention_minutes"] == 30
    assert body["detail"] == ""

    assert client.get("/api/atlas/depth-history/BTCUSDT?minutes=2").json()["ok"] is True
    no_events = client.get("/api/atlas/depth-history/BTCUSDT?events=0").json()
    assert no_events["ok"] is True and no_events["events"] == []

    # a window before the record answers honestly instead of faking a chart
    old = client.get(f"/api/atlas/depth-history/BTCUSDT?from_ms={BASE - 600000}"
                     f"&to_ms={BASE - 300000}").json()
    assert old["ok"] is True and old["buckets"] == [] and "ask for a window" in old["detail"]
    assert old["have_from_ms"] == BASE

    status = client.get("/api/atlas/depth-history").json()
    assert status["ok"] is True and status["symbols"][0]["symbol"] == "BTCUSDT"
    assert status["stats"]["retained_levels"] > 0


def test_the_retention_post_applies_the_patch_and_never_500s(tmp_path, monkeypatch):
    """The route is also the writer now (§148), so it gets its own config dir — never the real one."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    store = _store()
    client = _client(store)
    try:
        body = client.post("/api/atlas/depth-history/retention",
                           json={"retention_minutes": 5, "max_levels": 20}).json()
        assert body["ok"] is True
        assert body["settings"]["retention_minutes"] == 5 and body["settings"]["max_levels"] == 20
        assert store.settings["retention_minutes"] == 5

        junk = client.post("/api/atlas/depth-history/retention", json={"retention_minutes": "junk"}).json()
        assert junk["ok"] is True and junk["settings"]["retention_minutes"] == dh.DEFAULTS["retention_minutes"]
        assert client.post("/api/atlas/depth-history/retention", json={}).json()["ok"] is True
        cleared = client.post("/api/atlas/depth-history/clear", json={}).json()
        assert cleared["ok"] is True and cleared["cleared"] == "*"
    finally:
        dh.set_store(None)


def test_the_retention_post_persists_and_a_restart_keeps_it(tmp_path, monkeypatch):
    """§148: this route used to change the running store only — the next start reverted it.

    Measured before the fix, live on the scratch profile: POST retention 120 -> restart -> the store
    answered 30 again, because nothing had written ``atlas.depth_history`` and boot reads the file.
    """
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    store = _store()
    client = _client(store)
    try:
        body = client.post("/api/atlas/depth-history/retention",
                           json={"retention_minutes": 120, "max_levels": 40}).json()
        assert body["ok"] is True and body["settings"]["retention_minutes"] == 120
        stored = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        block = stored["atlas"]["depth_history"]
        assert block["retention_minutes"] == 120 and block["max_levels"] == 40
        # what the next boot does with that file: configure a fresh store from the saved block
        fresh = dh.DepthHistoryStore()
        fresh.configure(block)
        assert fresh.settings["retention_minutes"] == 120 and fresh.settings["max_levels"] == 40
    finally:
        dh.set_store(None)


def test_a_saved_depth_history_block_reaches_the_running_store_on_configure():
    """§148, the mirror half: /api/control/params persisted these keys and the store never heard it.

    The params route applies a saved atlas block by calling ``hub.configure`` — that call used to
    touch the alert rules and the per-symbol features only, so a depth-history dial moved in the
    file and the running store kept its old ceilings.
    """
    from orderflow_system.atlas.hub import FeatureHub

    store = _store()
    dh.set_store(store)
    try:
        hub = FeatureHub({})                  # captures the store this test installed
        assert hub.depth_history is store
        before = dict(store.settings)
        hub.configure({"depth_history": {"retention_minutes": 7, "max_levels": 12}})
        assert store.settings["retention_minutes"] == 7 and store.settings["max_levels"] == 12
        # a block that is not a mapping is left alone rather than crashing the apply
        hub.configure({"depth_history": "junk"})
        assert store.settings["retention_minutes"] == 7
        # and a partial block only moves the keys it names
        hub.configure({"depth_history": {"retention_minutes": before["retention_minutes"]}})
        assert store.settings["retention_minutes"] == before["retention_minutes"]
        assert store.settings["max_levels"] == 12
    finally:
        dh.set_store(None)


def test_the_boot_apply_gives_a_stopped_store_the_saved_block():
    """§148, the boot half: with no engine running the API answered the factory block regardless.

    Live before the fix: the file said 120, the engine was stopped, and
    ``/api/atlas/depth-history`` answered 30 — an engine start was the only thing that read the
    saved block (it builds its own hub from the atlas config).
    """
    from orderflow_system.desktop.launcher import apply_depth_history_block

    store = _store()
    dh.set_store(store)
    try:
        apply_depth_history_block({"atlas": {"depth_history": {"retention_minutes": 120}}})
        assert store.settings["retention_minutes"] == 120
        # a config without the block, or with a block that is not a mapping, leaves the store alone
        apply_depth_history_block({})
        assert store.settings["retention_minutes"] == 120
        apply_depth_history_block({"atlas": "junk"})
        assert store.settings["retention_minutes"] == 120
    finally:
        dh.set_store(None)


def test_a_real_orderbook_snapshot_is_what_the_hub_will_hand_over():
    """The wiring the parent makes passes the repo's own book straight in — pin that shape.

    A snapshot the feed flagged stale is refused (SEC-07's rule, which the depth map follows too):
    the record is only worth keeping if every column in it is a book somebody could vouch for.
    """
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    store = _store()
    snap = OrderbookSnapshot(
        timestamp_ms=BASE,
        bids=[OrderbookLevel(price=99.5, quantity=3.0), OrderbookLevel(price=99.0, quantity=2.0)],
        asks=[OrderbookLevel(price=100.5, quantity=4.0)])
    assert store.record("BTCUSDT", snap.timestamp_ms, snap) == 1
    stale = OrderbookSnapshot(timestamp_ms=BASE + 1000,
                              bids=[OrderbookLevel(price=99.5, quantity=99.0)],
                              asks=[OrderbookLevel(price=100.5, quantity=99.0)], stale=True)
    assert store.record("BTCUSDT", stale.timestamp_ms, stale) == 1
    assert store.counters["stale_skipped"] == 1 and store.columns("BTCUSDT") == 1

    bucket = store.series("BTCUSDT").get("buckets")
    assert bucket, "the recorded book is served"
    row = bucket[-1]
    assert row["total_bid"] == 5.0 and row["total_ask"] == 4.0
    assert row["best_bid"] == 99.5 and row["best_ask"] == 100.5
    assert row["biggest"] == {"price": 100.5, "size": 4.0, "side": "ask", "share": round(4.0 / 9.0, 4)}


def test_the_module_singleton_is_what_the_hub_feeds_and_the_routes_read():
    """The wiring the parent makes: one ``record()`` per depth update, one store behind both sides."""
    dh.set_store(None)
    try:
        assert dh.record("BTCUSDT", BASE, _book()) == 1
        assert dh.get_store().has("BTCUSDT") is True
        body = TestClient(_app()).get("/api/atlas/depth-history/BTCUSDT").json()
        assert body["ok"] is True and body["retained"]["columns"] == 1
        assert dh.get_store().stats()["counters"]["records"] == 1
    finally:
        dh.set_store(None)


def test_the_panel_and_the_routes_agree_on_one_path_and_one_set_of_parameters():
    """The JS panel builds its urls from a constant; this router owns the truth.

    Pinned here the way ``test_freshness`` pins the two freshness window tables — so a rename on
    either side cannot quietly leave the other pointing at nothing.
    """
    import inspect
    from pathlib import Path

    js = (Path(__file__).parent / "desktop" / "ui" / "depth-history.js").read_text(encoding="utf-8")
    assert "URL_BASE = '/api/atlas/depth-history'" in js
    assert "'/retention'" in js and "'/clear'" in js
    paths = {getattr(r, "path", "") for r in dh.router.routes}
    assert paths == {"/api/atlas/depth-history", "/api/atlas/depth-history/{symbol}",
                     "/api/atlas/depth-history/retention", "/api/atlas/depth-history/clear"}
    params = set(inspect.signature(dh.depth_history_series).parameters)
    assert {"minutes", "from_ms", "to_ms", "bucket_ms", "events"} <= params, params
    assert "retention_minutes" in js
    for name in ("minutes=", "bucket_ms=", "events="):
        assert name in js, name


# ── the panel's marker mapping (T6-F05): a pytest-visible bite for a JS-only fix ─────────────────

#: The band edges every payload carries: nine prices a quarter apart, so eight rows, and 99.5 sits in
#: row 2 by ``floor`` — the same arithmetic the panel's own selftest uses.
_PANEL_BANDS = [99, 99.25, 99.5, 99.75, 100, 100.25, 100.5, 100.75, 101]


def _panel_payload(buckets: list[int], events: list[dict]) -> dict:
    """The store's own shape: the bucket list names only the cells it RECORDED — it skips the rest.

    ``bands`` is the list of band EDGES (not rows), which is how ``/api/atlas/depth-history`` serves
    it and the only thing ``dhBandRow`` reads.
    """
    rows = [{"bid": 5.0, "ask": 4.0} for _ in range(len(_PANEL_BANDS) - 1)]
    return {"bucket_ms": 5000, "bands": _PANEL_BANDS,
            "buckets": [{"ts_ms": ts, "bands": rows} for ts in buckets], "events": events}


def _panel_marker_cells(payload: dict, cap: int | None = None) -> list[dict]:
    """``dhMarkerCells`` as the browser runs it: the real module file, booted under node."""
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    node = shutil.which("node")
    if not node:                                     # pragma: no cover - node ships with the build
        pytest.skip("node is not on PATH")
    module = Path(__file__).parent / "desktop" / "ui" / "depth-history.js"
    script = (
        "const fs=require('fs');"
        f"const src=fs.readFileSync({json.dumps(str(module))},'utf8');"
        "const win={};"
        "new Function('window','document',src)(win, undefined);"
        "const fixture=JSON.parse(process.argv[1]);"
        "const cap=Number(process.argv[2])||undefined;"
        "console.log(JSON.stringify(win.OFAPDEPTHH.markerCells(fixture, cap)));"
    )
    proc = subprocess.run([node, "-e", script, json.dumps(payload), str(cap if cap is not None else "")],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_a_marker_sits_on_its_own_cells_slot_not_the_grid_offset():
    """T6-F05 (§148): the bucket list skips the cells the store never recorded, so a cell's offset on
    the time grid is NOT an array index — read off the grid, every marker after a gap landed one cell
    per gap away from its own depth, and an event whose own cell is missing landed on a neighbour's.
    """
    payload = _panel_payload(
        buckets=[1700000000000, 1700000005000, 1700000015000, 1700000020000],  # ...10000 not recorded
        events=[
            {"kind": "pull", "ts_ms": 1700000000500, "price": 99.5, "size": 1},   # own cell -> slot 0
            {"kind": "pull", "ts_ms": 1700000010500, "price": 99.5, "size": 2},   # cell never recorded
            {"kind": "add", "ts_ms": 1700000015500, "price": 99.5, "size": 3},    # own cell -> slot 2
        ])
    cells = _panel_marker_cells(payload)
    assert [c["size"] for c in cells] == [1, 3], \
        "the event in the cell the store never recorded is dropped, never shifted onto a neighbour"
    assert [(c["column"], c["kind"]) for c in cells] == [(0, "pull"), (2, "add")], \
        "a marker column is its own cell's SLOT in the array, not its offset on the time grid"
    assert [c["band"] for c in cells] == [2, 2], cells


def test_a_marker_cap_keeps_the_newest_never_the_oldest():
    """The cap bounds the read, so it must drop the OLDEST markers: the newest are the ones a live
    strip is watched for. The walk that kept the first events it met capped the strip at its oldest
    end — the marker for the depth that just changed was the one dropped.
    """
    payload = _panel_payload(
        buckets=[1700000000000 + i * 5000 for i in range(4)],
        events=[
            {"kind": "pull", "ts_ms": 1700000000400, "price": 99.5, "size": 1},
            {"kind": "add", "ts_ms": 1700000005400, "price": 99.5, "size": 2},
            {"kind": "pull", "ts_ms": 1700000015400, "price": 99.5, "size": 3},
        ])
    cells = _panel_marker_cells(payload, 2)
    assert [c["size"] for c in cells] == [2, 3], "the newest survive and the oldest fall off"
    assert [c["column"] for c in cells] == [1, 3], cells


def test_a_brand_new_level_carries_no_measured_share():
    """T6-F9 (§148): a level that was not there before has no before-size, so its event carries
    pct: None — the absence of a reading, not a 100% that was never measured. The tape says
    "new level".
    """
    store = _store()
    store.record("BTCUSDT", BASE, {100.0: (5.0, 10.0)})
    store.record("BTCUSDT", BASE + 1000, {100.0: (5.0, 2.0), 101.0: (8.0, 0.0)})
    events = store.events("BTCUSDT")
    add = [e for e in events if e["kind"] == "add" and e["price"] == 101.0][0]
    assert add["from"] == 0.0 and add["pct"] is None
    pull = [e for e in events if e["kind"] == "pull"][0]
    assert pull["price"] == 100.0 and pull["pct"] == 0.8


def test_the_retention_route_takes_every_key_of_the_settings_block():
    """T6-F10 (§148): max_symbols, gap_multiple and bands were registered controls that the
    retention POST silently could not touch — two surfaces for one block, each incomplete.
    """
    store = _store()
    client = _client(store)
    body = client.post("/api/atlas/depth-history/retention",
                       json={"max_symbols": 4, "gap_multiple": 6, "bands": 16}).json()
    assert body["ok"] is True
    assert store.settings["max_symbols"] == 4
    assert store.settings["gap_multiple"] == 6
    assert store.settings["bands"] == 16
    assert body["settings"]["max_symbols"] == 4
    assert body["settings"]["gap_multiple"] == 6
    assert body["settings"]["bands"] == 16


def test_record_writes_the_store_the_routes_read():
    """T6-F11 (§148): record() wrote the module singleton while every route reads get_store() —
    the two agreed only because the hub adopts the same object. A later set_store() would have
    split the writer from the readers, so the writer asks for the store the same way the routes do.
    """
    dh.set_store(None)
    try:
        store = _store()
        dh.set_store(store)
        assert dh.record("BTCUSDT", BASE, _book()) == 1
        assert dh.get_store().has("BTCUSDT")
        other = dh.DepthHistoryStore({})
        dh.set_store(other)
        assert dh.record("ETHUSDT", BASE, _book()) == 1
        assert other.has("ETHUSDT")
        assert not store.has("ETHUSDT")
    finally:
        dh.set_store(None)


def test_the_depth_history_selftest_runs_green_under_node():
    """The panel's own checks for F8 (the poll guard) and F9 (the new-level tape).
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    selftest = Path(__file__).parent / "desktop" / "ui" / "depth-history.selftest.js"
    proc = subprocess.run([node, str(selftest)], capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "failed" in proc.stdout and "0 failed" in proc.stdout, proc.stdout
