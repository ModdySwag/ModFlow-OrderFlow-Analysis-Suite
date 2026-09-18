"""Wave B T10 — B3 vertical smoothing · B13 zoom-level candle degrade · B16 the price-scale object.

The pure halves live in `ramp.js` / `ofx.js` / `expression.js` and are executed by their node
selftests; this file pins the CONTRACTS around them: the registry entries and their bounds, the
sanitiser clamps, the control catalogues held equal everywhere, and the source landmarks the
renderers read them through.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from orderflow_system.desktop import config_store, param_registry

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"

B3_PATHS = ("ofx.heat_smooth", "atlas.heatmap.smooth")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    exe = shutil.which("node") or "node"
    return subprocess.run([exe, *args], capture_output=True, text=True, cwd=str(cwd) if cwd else None,
                          encoding="utf-8", errors="replace", timeout=120)


# ── the registry + the store ───────────────────────────────────────────────────────────────────

def test_b3_the_smoothing_variables_are_registered_enums():
    for path in B3_PATHS:
        p = param_registry.BY_PATH.get(path)
        assert p is not None, "missing from the registry: " + path
        assert p.kind == "enum", path + " must be an enum"
        assert p.choices == tuple(config_store.SMOOTH_MODES) == ("auto", "manual", "none"), path
        assert p.meaning and p.label and p.group and p.view, "no presentation for " + path


def test_b13_degrade_is_registered_as_a_bool():
    p = param_registry.BY_PATH.get("atlas.ofx.degrade")
    assert p is not None and p.kind == "bool", "atlas.ofx.degrade must be a registered bool"
    assert p.meaning and p.label and p.group and p.view


def test_b3_and_b13_defaults_and_the_sanitiser_clamps():
    cfg = config_store.default_config()
    assert cfg["ofx"]["heat_smooth"] == "auto"
    assert cfg["atlas"]["heatmap"]["smooth"] == "auto"
    assert cfg["atlas"]["ofx"]["degrade"] is True

    cfg["ofx"]["heat_smooth"] = "junk"
    cfg["atlas"]["heatmap"]["smooth"] = 3
    cfg["atlas"]["ofx"]["degrade"] = False
    out = config_store._sanitise(cfg)
    assert out["ofx"]["heat_smooth"] == "auto"
    assert out["atlas"]["heatmap"]["smooth"] == "auto"
    assert out["atlas"]["ofx"]["degrade"] is False

    cfg2 = config_store.default_config()
    cfg2["ofx"]["heat_smooth"] = "none"
    cfg2["atlas"]["heatmap"]["smooth"] = "manual"
    out2 = config_store._sanitise(cfg2)
    assert out2["ofx"]["heat_smooth"] == "none"
    assert out2["atlas"]["heatmap"]["smooth"] == "manual"


# ── the catalogues, held equal everywhere ──────────────────────────────────────────────────────

def test_b13_candles_join_every_mode_catalogue():
    assert "candles" in config_store.EXPRESSION_MODES
    js = json.loads(_node("-e", "console.log(JSON.stringify(require('./expression.js').MODE_KEYS));",
                          cwd=UI).stdout)
    assert js == list(config_store.EXPRESSION_MODES), js
    reg = param_registry.BY_PATH["expression.engine.mode"]
    assert reg.choices == tuple(config_store.EXPRESSION_MODES)
    support = json.loads(_node("-e", "console.log(JSON.stringify(require('./expression.js').CHART_SUPPORT));",
                               cwd=UI).stdout)
    assert support["candles"] is True


def test_the_new_controls_offer_exactly_the_catalogues():
    html = _text(UI / "index.html")
    for sid in ("ofxHeatSmooth", "hmHeatSmooth"):
        block = re.search(r'<select id="' + sid + r'".*?</select>', html, re.S)
        assert block, "control missing from index.html: " + sid
        values = re.findall(r'<option value="([^"]+)"', block.group(0))
        assert values == list(config_store.SMOOTH_MODES), (sid, values)
    assert 'id="ofxDegrade"' in html, "the auto-candles switch is missing"
    for sid in ("ofxMode", "chartMode"):
        block = re.search(r'<select id="' + sid + r'".*?</select>', html, re.S)
        assert block and "candles" in re.findall(r'<option value="([^"]+)"', block.group(0)), sid


# ── the wiring landmarks (the renderers read these names) ──────────────────────────────────────

def test_b3_smoothing_is_wired_into_both_heat_renderers():
    ofx = _text(UI / "ofx.js")
    atlas = _text(UI / "atlas.js")
    assert "smoothVector" in ofx and "smoothHeatOn" in ofx and "RPHEAT.smoothDecision" in ofx
    assert "smoothCols" in atlas and "hmSmoothOn" in atlas
    view = _text(UI / "ofx-view.js")
    assert "ofx.heat_smooth" in view and "heatSmooth" in view
    assert "atlas.heatmap.smooth" in atlas


def test_b13_the_degrade_draws_candles_where_the_profiles_fell_back():
    ofx = _text(UI / "ofx.js")
    assert "degradeDecision" in ofx and "state.stats.degraded" in ofx
    assert "barPaintFor(bar, 'candles')" in ofx, "the fallback must draw the candles expression"
    assert "state.params.degrade" in ofx
    view = _text(UI / "ofx-view.js")
    assert "atlas.ofx.degrade" in view and "ofxDegrade" in view


def test_b16_the_scale_object_and_the_reset_command_are_wired():
    ofx = _text(UI / "ofx.js")
    view = _text(UI / "ofx-view.js")
    assert "openScaleMenu" in ofx and "'contextmenu'" in ofx and "RAIL_W" in ofx
    assert "scales: () =>" in ofx and "drag.axis" in ofx
    assert "reset-scales" in view and "ctrl+shift+r" in view


def test_every_selftest_that_owns_a_pure_half_passes():
    for name in ("ramp", "expression", "ofx"):
        run = _node(str(UI / (name + ".selftest.js")))
        assert run.returncode == 0, (name, run.stdout, run.stderr)
        assert "0 failed" in (run.stdout or ""), (name, run.stdout)
