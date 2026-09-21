"""§118 — the paper session's ledger and the bracket-edit route, over the real atlas routes.

The account itself is pinned in test_paper.py; this file holds the wiring AROUND it: the events
the routes record (start · submit · reject · cancel · fill · exits · end), the state payload the
panel reads, the CSV export landing where the app's other exports land — and a source pin for the
replay feed's own two ledger lines, which run inside replay_play's closure and cannot be called
directly without a transport.
"""

from __future__ import annotations

import asyncio
import csv
import sqlite3
from pathlib import Path

from orderflow_system.atlas import api as atlas_api
from orderflow_system.desktop import config_store


def _run(coro):
    return asyncio.run(coro)


def _reset(monkeypatch, tmp_path):
    """A clean ledger over a scratch config dir — never the user's real one."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    atlas_api._paper["account"] = None
    atlas_api._paper["fills"] = []
    atlas_api._paper["events"] = []
    atlas_api._paper["event_count"] = 0
    atlas_api._paper["last_ts_ms"] = 0
    atlas_api._paper["last_price"] = 0.0


def _open_position(price: float) -> None:
    """Put the session long 1 at ``price`` through the account's own fill path."""
    account = atlas_api._paper["account"]
    atlas_api._paper["last_price"] = price
    account.submit("buy", 1, ts_ms=10)
    for fill in account.on_trade(price, 1, "sell", 20):
        atlas_api._paper["fills"].append(fill)
        atlas_api._paper_event("fill", order_id=fill.get("order_id") or "",
                               side=fill.get("side") or "", size=fill.get("size"),
                               price=fill.get("price"), order_kind=fill.get("kind") or "",
                               note=fill.get("reason") or "", at_ms=20)


def test_the_ledger_records_the_lifecycle(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    start = _run(atlas_api.paper_start({"symbol": "ESZ6", "tick_size": 0.25}))
    assert start["ok"] and start["state"]["events"][0]["kind"] == "start"

    order = _run(atlas_api.paper_order({"side": "buy", "size": 1, "kind": "market"}))
    rejected = _run(atlas_api.paper_order({"side": "buy", "size": 0}))
    assert order["ok"] is True and rejected["ok"] is False
    kinds = [e["kind"] for e in rejected["state"]["events"]]
    assert kinds == ["start", "submit", "reject"]
    assert rejected["state"]["events"][-1]["note"]           # the refusal sentence travels

    _open_position(5000.0)
    state = _run(atlas_api.paper_get_state())["state"]
    assert state["tick_size"] == 0.25          # the ladder spaces its rows on the session tick
    # the endpoint's market order is still working, so the one print fills BOTH entries
    kinds = [e["kind"] for e in state["events"]]
    assert kinds == ["start", "submit", "reject", "fill", "fill"]
    assert state["event_count"] == 5

    resting = _run(atlas_api.paper_order({"side": "sell", "size": 1, "kind": "limit",
                                          "price": 5050.0}))
    assert resting["ok"] is True
    cancelled = _run(atlas_api.paper_cancel({}))
    # ids: o1 endpoint market, o2 its refusal (a refusal still takes an id), o3 the entry, o4 this
    assert cancelled["ok"] is True and cancelled["cancelled"] == ["o4"]
    assert [e["kind"] for e in cancelled["state"]["events"]][-2:] == ["submit", "cancel"]


def test_the_exits_route_edits_the_open_positions_bracket(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    _run(atlas_api.paper_start({"symbol": "ESZ6", "tick_size": 0.25}))
    refused = _run(atlas_api.paper_exits({"stop_loss": 4999.0}))
    assert refused["ok"] is False and "no open position" in refused["error"]

    _open_position(5000.0)
    moved = _run(atlas_api.paper_exits({"stop_loss": 4998.5, "take_profit": 5003.0}))
    assert moved["ok"] is True and moved["changed"] is True
    assert moved["state"]["exits"] == {"stop_loss": 4998.5, "take_profit": 5003.0}
    evt = moved["state"]["events"][-1]
    assert evt["kind"] == "exits" and "4998.5" in evt["note"]

    junk = _run(atlas_api.paper_exits({"stop_loss": "abc", "take_profit": 5003.0}))
    assert junk["ok"] is False and "stop_loss" in junk["error"]
    assert _run(atlas_api.paper_get_state())["state"]["exits"]["stop_loss"] == 4998.5


def test_the_session_ends_with_its_ledger_intact(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    _run(atlas_api.paper_start({"symbol": "ESZ6", "tick_size": 0.25}))
    _run(atlas_api.paper_order({"side": "sell", "size": 2, "kind": "market"}))
    closed = _run(atlas_api.paper_close())
    assert closed["ok"] is True
    state = _run(atlas_api.paper_get_state())["state"]
    assert state["running"] is False
    assert [e["kind"] for e in state["events"]] == ["start", "submit", "end"]


def test_the_export_writes_the_ledger_where_the_apps_exports_land(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    _run(atlas_api.paper_start({"symbol": "ESZ6", "tick_size": 0.25}))
    _run(atlas_api.paper_order({"side": "buy", "size": 1, "kind": "limit", "price": 4999.0}))
    exported = _run(atlas_api.paper_export())
    assert exported["ok"] is True and exported["rows"] == 2

    path = Path(exported["path"])
    assert path.parent == tmp_path / "exports" and path.is_file()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][:2] == ["n", "event"]
    assert [r[1] for r in rows[1:]] == ["start", "submit"]
    assert rows[2][5] == "buy" and rows[2][8] == "limit"   # side and order kind travel


def test_the_end_of_a_session_creates_the_journal_table_it_writes_to(monkeypatch, tmp_path):
    """A fresh database has no trade_journal — "End & save" must create it, not 500."""
    _reset(monkeypatch, tmp_path)
    db = tmp_path / "orderflow_data.db"
    monkeypatch.setattr(config_store, "db_path", lambda: db)
    _run(atlas_api.paper_start({"symbol": "ESZ6", "tick_size": 0.25}))
    account = atlas_api._paper["account"]
    account.submit("buy", 1, ts_ms=1)
    for fill in account.on_trade(5000.0, 1, "sell", 2):
        atlas_api._paper["fills"].append(fill)
    account.set_exits(stop_loss=4999.0, take_profit=None)
    account.on_trade(4999.0, 1, "sell", 3)              # one closed trade to journal
    assert account.closed_trades(), "the fixture must leave a closed trade"
    done = _run(atlas_api.paper_close())
    assert done["ok"] is True and done["saved"] == 1, done
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT instrument, direction, pnl_ticks, signals_json, notes FROM trade_journal").fetchall()
    finally:
        conn.close()
    assert len(rows) == 1 and rows[0][0] == "ESZ6" and rows[0][1] == "long"
    assert rows[0][3] == '{"source": "paper"}' and rows[0][4] == "simulated session"


def test_a_journal_from_before_the_excursion_columns_still_takes_a_session(monkeypatch, tmp_path):
    """§148: the route that owns the table migrates it — "End & save" must not fail on an old file.

    Measured shape of a legacy file: a trade_journal with no mae_ticks/mfe_ticks (CREATE TABLE IF
    NOT EXISTS never alters an existing table). The writer adds them itself before its INSERT, and
    the rows it writes carry the excursion the position took.
    """
    _reset(monkeypatch, tmp_path)
    db = tmp_path / "orderflow_data.db"
    monkeypatch.setattr(config_store, "db_path", lambda: db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "CREATE TABLE trade_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT NOT "
            "NULL, direction TEXT NOT NULL, entry_time_ms INTEGER, exit_time_ms INTEGER, "
            "entry_price REAL, exit_price REAL, stop_loss REAL, take_profit REAL, pnl_ticks REAL, "
            "rr_ratio REAL, signals_json TEXT, notes TEXT)")
        conn.execute("INSERT INTO trade_journal (instrument, direction) VALUES ('OLD', 'long')")
        conn.commit()
    finally:
        conn.close()

    _run(atlas_api.paper_start({"symbol": "ESZ6", "tick_size": 0.25}))
    account = atlas_api._paper["account"]
    account.submit("buy", 1, ts_ms=1)
    for fill in account.on_trade(5000.0, 1, "sell", 2):
        atlas_api._paper["fills"].append(fill)
    account.submit("sell", 1, ts_ms=3)
    for fill in account.on_trade(4998.0, 1, "buy", 4):       # 8 ticks against the long
        atlas_api._paper["fills"].append(fill)
    done = _run(atlas_api.paper_close())
    assert done["ok"] is True and done["saved"] == 1, done

    conn = sqlite3.connect(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(trade_journal)")}
        rows = conn.execute(
            "SELECT instrument, mae_ticks, mfe_ticks FROM trade_journal ORDER BY id").fetchall()
    finally:
        conn.close()
    assert {"mae_ticks", "mfe_ticks"} <= cols, "the writer must migrate the table it writes to"
    assert rows[0][0] == "OLD" and rows[0][1] is None        # the legacy row reads as no excursion
    assert rows[1][0] == "ESZ6" and rows[1][1] == 8.0 and rows[1][2] == 0.0


def test_the_journal_ddl_describes_the_journal_columns():
    """The DDL and TRADE_COLUMNS are two views of one table; they must agree."""
    import re as _re
    from orderflow_system.desktop import journal as journal_mod

    declared = tuple(_re.findall(r"^\s{4}([a-z_]+) ", journal_mod.TRADE_JOURNAL_DDL, _re.M))
    # profile_id is the data layer migration column: every live table has it, so the DDL does too.
    assert "profile_id" in declared and tuple(c for c in declared if c != "profile_id") == journal_mod.TRADE_COLUMNS
    canonical = (Path(__file__).resolve().parent / "data" / "database.py").read_text(encoding="utf-8")
    for column in journal_mod.TRADE_COLUMNS:
        assert ("    " + column + " ") in canonical, column + " missing from the data schema"


def test_the_replay_feed_feeds_the_ledger():
    """replay_play's closure runs per tick; these two lines are its ledger hand-off."""
    src = Path(atlas_api.__file__).read_text(encoding="utf-8")
    assert '_paper["last_ts_ms"] = int(tick.timestamp_ms)' in src
    assert '_paper_event("fill"' in src
