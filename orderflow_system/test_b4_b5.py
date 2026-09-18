"""Wave B T15 — B4 (columns rail) · B5 (one-table component, Watchlist trial).

The rails' and the component's pure halves are executed by colrail.selftest.js / table.selftest.js;
this pins the config records and clamps, the wiring landmarks, and the adoption flag's honesty
(the built-in renderer stays the default until the trial is switched on).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from orderflow_system.desktop import config_store

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def _selftest(name: str) -> subprocess.CompletedProcess:
    node = shutil.which("node") or "node"
    return subprocess.run([node, str(UI / name)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def test_b4_the_rails_dials_persist_and_clamp() -> None:
    cfg = config_store.default_config()
    assert cfg["atlas"]["columns"] == {"metric": "traded", "reset": "manual", "threshold": 500, "reset_s": 30}
    cfg["atlas"]["columns"] = {"metric": "zzz", "reset": "sometimes", "threshold": -4, "reset_s": 9000}
    out = config_store._sanitise(cfg)["atlas"]["columns"]
    assert out["metric"] == "traded" and out["reset"] == "manual"
    assert out["threshold"] == 0.0 and out["reset_s"] == 600.0
    cfg["atlas"]["columns"] = {"metric": "resting", "reset": "conditional", "threshold": 250, "reset_s": 45}
    assert config_store._sanitise(cfg)["atlas"]["columns"]["metric"] == "resting"


def test_b4_the_rail_is_wired_to_the_map() -> None:
    src = _text("colrail.js")
    for marker in ("function reduce(", "function resetEntry(", "function resetAll(",
                   "function observe(", "RESETS = ['manual', 'scheduled', 'conditional']"):
        assert marker in src, marker
    assert "OFAPCOLRAIL.observe(d)" in _text("atlas.js"), "every fresh snapshot reaches the rail"
    html = _text("index.html")
    for marker in ('id="hmColRail"', 'id="hmColMetric"', 'id="hmColReset"', 'id="hmColRows"',
                   'id="hmColResetAll"', 'class="card-body hm-split"'):
        assert marker in html, marker
    assert ".hm-rail" in _text("modules.css")
    run = _selftest("colrail.selftest.js")
    assert run.returncode == 0 and "0 failed" in run.stdout, (run.stdout, run.stderr)


def test_b5_the_tables_record_persists_and_clamps() -> None:
    cfg = config_store.default_config()
    assert cfg["ui"]["table_component"] == [] and cfg["ui"]["tables"] == {}
    cfg["ui"]["table_component"] = ["watchlist", 5, {"x": 1}, "another"]
    assert config_store._sanitise(cfg)["ui"]["table_component"] == ["watchlist", "5", "another"], \
        "strings only, small, capped"
    cfg["ui"]["tables"] = {"watchlist": {"order": ["b", "a", "b"], "hidden": ["c"],
                                         "sort": {"key": "volume", "dir": "desc"}, "group": "phase", "junk": 1},
                           "bad": "not-a-dict"}
    out = config_store._sanitise(cfg)["ui"]["tables"]
    assert out["watchlist"]["order"] == ["b", "a", "b"]
    assert out["watchlist"]["sort"] == {"key": "volume", "dir": "desc"}
    assert out["watchlist"]["group"] == "phase" and "junk" not in out["watchlist"]
    assert "bad" not in out


def test_b5_the_component_and_its_trial_host() -> None:
    src = _text("table.js")
    for marker in ("function applyOrder(", "function cycleSort(", "function sortRows(",
                   "function groupRows(", "function moveColumn(", "ui: { tables: patch }"):
        assert marker in src, marker
    wl = _text("watchlist.js")
    assert "function tableModeOn(" in wl and "function renderTableMode(" in wl
    assert "if (host && tableModeOn()) renderTableMode(host, rows);" in wl, \
        "the built-in renderer stays the default until the trial is on"
    assert "Toggle the table-component trial" in _text("search.js"), "the flag has a switch"
    assert ".oft-head" in _text("modules.css") and ".oft-row" in _text("modules.css")
    run = _selftest("table.selftest.js")
    assert run.returncode == 0 and "0 failed" in run.stdout, (run.stdout, run.stderr)
