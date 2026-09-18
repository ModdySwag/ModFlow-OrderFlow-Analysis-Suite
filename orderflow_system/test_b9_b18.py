"""Wave B T12a — B18 (palette deep-launch) · B9 (per-instrument settings scoping).

The pure halves are executed by scopes.selftest.js; this file pins the contracts: the scoped-path
list held equal between the server sanitiser and the page module, the store's clamps, and the
wiring landmarks the palette and the two heat surfaces read them through.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from orderflow_system.desktop import config_store

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def _walk(cfg: dict, path: str):
    cur = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return "<missing>"
        cur = cur[part]
    return cur


def test_b9_the_scoped_list_is_one_list() -> None:
    src = _text("scopes.js")
    block = re.search(r"const SCOPED = \[(.*?)\];", src, re.S)
    assert block, "SCOPED in scopes.js"
    listed = re.findall(r"'([^']+)'", block.group(1))
    assert listed == list(config_store.SCOPED_DISPLAY_PATHS), \
        "the sanitiser's allow-list and the page module's list are the same list, in order"


def test_b9_every_scoped_path_exists_in_the_defaults() -> None:
    cfg = config_store.default_config()
    for path in config_store.SCOPED_DISPLAY_PATHS:
        assert _walk(cfg, path) != "<missing>", path
    assert cfg["ui"]["instrument_scopes"] == {}


def test_b9_the_sanitiser_keeps_a_scope_to_its_shape() -> None:
    cfg = config_store.default_config()
    cfg["ui"]["instrument_scopes"] = {
        "btcusdt": {"ofx.ramp": "thermal", "evil.path": 1, "atlas.ofx.degrade": False,
                    "atlas.heatmap.floor": 2.5},
        "BAD SYMBOL": {"ofx.ramp": "classic"},
        "NQ": "not-a-block",
    }
    out = config_store._sanitise(cfg)["ui"]["instrument_scopes"]
    assert set(out.keys()) == {"BTCUSDT"}, "symbols are upper-cased; junk symbols and blocks dropped"
    assert out["BTCUSDT"] == {"ofx.ramp": "thermal", "atlas.ofx.degrade": False,
                              "atlas.heatmap.floor": 2.5}
    # the cap: 45 instruments in, 40 out
    cfg2 = config_store.default_config()
    cfg2["ui"]["instrument_scopes"] = {f"SYM{i}": {"ofx.ramp": "classic"} for i in range(45)}
    assert len(config_store._sanitise(cfg2)["ui"]["instrument_scopes"]) == 40


def test_b18_the_palette_deep_launches() -> None:
    src = _text("search.js")
    assert "const LAUNCH_TARGETS" in src and "const LAUNCH_TAG_RE" in src
    for view in ("'ofx'", "'heatmap'", "'chart'", "'replay'", "'depth'"):
        assert view in src, view
    assert "cat: 'Deep launch'" in src
    assert "if (item.launch) {" in src, "searchRun handles the launch rows"
    assert "engineSel" in src, "the Engine deep-launch pre-loads its own symbol control"
    assert "OFAPSCOPES.forgetCurrent" in src, "the forget command rides the palette"
    assert "@BTCUSDT" in src, "the empty-panel hint teaches the selector"


def test_b9_the_surfaces_follow_the_scopes_event() -> None:
    assert "ofap:scopes" in _text("scopes.js")
    assert "ofap:scopes" in _text("ofx-view.js")
    assert "ofap:scopes" in _text("atlas.js")
    html = _text("index.html")
    assert html.index("/desktop/scopes.js") > html.index("/desktop/links.js"), \
        "scopes.js loads after links.js (the shell it reads is up)"


def test_b9_the_pure_half_passes_its_selftest() -> None:
    node = shutil.which("node") or "node"
    run = subprocess.run([node, str(UI / "scopes.selftest.js")], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "0 failed" in run.stdout
