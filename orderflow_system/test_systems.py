"""§86 — the Systems board: the aggregation behind ``GET /api/control/systems``, pinned.

The board's job is honesty: a row is a fact the program can check in a moment, states are a closed
set the UI only paints (live | ready | off | error), and the score counts the systems the install
expects — never the capabilities it has simply not set up. These pins hold those properties down,
plus the two failure modes the board exists to surface: a missing bridge and a locked database.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from orderflow_system.desktop import api, config_store, engine as engine_mod

# R6: "storage" joined the board (usage, retention window, backup count) after "alerts".
ROWS = ["engine", "source", "mt5", "ninjatrader", "alpaca", "database", "ws", "alerts", "storage"]
STATES = {"live", "ready", "off", "error"}


def _stub(monkeypatch, tmp_path, *, cfg=None, running=False, error="", ticks=0, nt=None, mt5=None,
          db=None, telegram=None):
    base = {"data_source": "bybit", "instruments": [], "platforms": {}, "alpaca": {},
            "telegram": telegram or {}}
    base.update(cfg or {})
    monkeypatch.setattr(config_store, "load_config", lambda: base)
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(engine_mod.engine, "status", lambda: {
        "running": running, "error": error,
        "symbols": ["BTCUSDT"] if running else [],
        "per_symbol": [{"symbol": "BTCUSDT", "ticks": ticks}] if running else [],
        "uptime_s": 12 if running else 0, "ws_clients": 1 if running else 0})
    monkeypatch.setattr(engine_mod, "mt5_status", lambda: mt5 or {"available": True, "reason": ""})
    monkeypatch.setattr(engine_mod, "ninjatrader_status",
                        lambda payload=None: nt or {"available": False,
                                                    "reason": "no bridge at 127.0.0.1:8790 (TimeoutError)"})
    if db is not None:
        monkeypatch.setattr(engine_mod, "_database_state", lambda: db)
    return base


def test_every_row_is_well_formed_ordered_and_closed_vocabulary(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path)
    rep = engine_mod.systems_report()
    assert rep["ok"] is True
    assert [r["id"] for r in rep["rows"]] == ROWS
    for row in rep["rows"]:
        assert row["state"] in STATES, row
        assert isinstance(row["name"], str) and row["name"]
        assert isinstance(row["detail"], str) and row["detail"], row
        assert isinstance(row["view"], str)
    assert [r["id"] for r in rep["optional"]] == ["bookmap", "sierra"]
    assert all(r["optional"] is True for r in rep["optional"])
    assert rep["percent"] == round(100 * rep["live"] / rep["total"])


def test_a_stopped_engine_leaves_engine_off_and_the_source_ready(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path, running=False)
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["engine"]["state"] == "off"
    assert "Start engine" in rows["engine"]["detail"]
    assert rows["source"]["state"] == "ready"
    assert "start the engine" in rows["source"]["detail"].lower()


def test_a_running_engine_turns_the_engine_source_and_ws_rows_live(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path, running=True, ticks=1234)
    rep = engine_mod.systems_report()
    rows = {r["id"]: r for r in rep["rows"]}
    assert rows["engine"]["state"] == "live" and "1,234 ticks" in rows["engine"]["detail"]
    assert rows["source"]["state"] == "live"
    assert rows["ws"]["state"] == "live" and "1 client" in rows["ws"]["detail"]
    assert rep["live"] >= 3


def test_a_locked_database_is_an_error_row_that_names_the_way_out(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path, running=True,
          db={"state": "error", "detail": "locked (database is locked) — close any second app instance"})
    rep = engine_mod.systems_report()
    row = {r["id"]: r for r in rep["rows"]}["database"]
    assert row["state"] == "error" and "locked" in row["detail"] and "close" in row["detail"]
    assert "database" in rep["uphill"]


def test_a_missing_bridge_reads_as_off_with_its_own_reason_and_available_reads_ready(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path)
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["ninjatrader"]["state"] == "off"
    assert rows["ninjatrader"]["detail"] == "no bridge at 127.0.0.1:8790 (TimeoutError)"
    _stub(monkeypatch, tmp_path, nt={"available": True, "host": "127.0.0.1", "port": 8790, "reason": ""})
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["ninjatrader"]["state"] == "ready" and "bridge answering" in rows["ninjatrader"]["detail"]


def test_mt5_never_claims_the_feed_when_the_exchange_is_the_source(monkeypatch, tmp_path):
    """The board's whole value is that its sentences are true — a running exchange engine must
    not make the MT5 row say "feeding the engine now" (caught on a live screenshot)."""
    _stub(monkeypatch, tmp_path, running=True, ticks=5)
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["mt5"]["state"] == "ready"
    assert "feeding" not in rows["mt5"]["detail"]
    assert "choose MT5" in rows["mt5"]["detail"]
    _stub(monkeypatch, tmp_path, running=True, ticks=5, cfg={"data_source": "mt5"})
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["mt5"]["state"] == "live" and "feeding" in rows["mt5"]["detail"]


def test_alerts_are_off_unconfigured_ready_when_configured_and_live_when_sending(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path, telegram={})
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["alerts"]["state"] == "off" and "not configured" in rows["alerts"]["detail"]
    _stub(monkeypatch, tmp_path, telegram={"bot_token": "t", "chat_id": "c", "enabled": False})
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["alerts"]["state"] == "ready" and "switch on" in rows["alerts"]["detail"]
    _stub(monkeypatch, tmp_path, telegram={"bot_token": "t", "chat_id": "c", "enabled": True})
    rows = {r["id"]: r for r in engine_mod.systems_report()["rows"]}
    assert rows["alerts"]["state"] == "live"


def test_optional_capabilities_never_dilute_the_score(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path, running=True, ticks=5)
    rep = engine_mod.systems_report()
    assert rep["total"] == len(ROWS)                     # optional rows excluded
    assert rep["live"] <= len(ROWS)
    assert rep["percent"] == round(100 * rep["live"] / len(ROWS))


def test_the_route_passes_the_report_through(monkeypatch):
    stub = {"ok": True, "rows": [], "optional": [], "live": 0, "total": 0, "percent": 0}
    monkeypatch.setattr(engine_mod, "systems_report", lambda: stub)
    assert asyncio.run(api.systems()) == stub


def test_the_board_vocabulary_matches_the_js_module():
    js = (Path(__file__).parent / "desktop" / "ui" / "systems.js").read_text(encoding="utf-8")
    for state in STATES:
        assert state in js, state
    assert "OFAPSYSTEMS" in js and "tiles" in js and "score" in js
