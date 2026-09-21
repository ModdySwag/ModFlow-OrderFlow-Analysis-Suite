"""The OFX engine's math, through its own self-test.

The engine is JavaScript that paints canvases, so Python cannot exercise the pixels. What it
can do — and what the study runtime already does — is gate the suite on the engine's own
Node-runnable self-test, which pins every rule the engine claims: text weight mapping,
the diagonal imbalance matrix, stacked zones, POC, exponential liquidity decay, the thermal
gradient, sweep radii, LOD thresholds, the viewport state machine and the coordinate matrix.

A failure here means a stale or broken `ofx.js` on disk, not a rendering quirk.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
ENGINE = UI / "ofx.js"
SELFTEST = UI / "ofx.selftest.js"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _run_selftest() -> subprocess.CompletedProcess:
    return subprocess.run(
        [_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=120,
        cwd=str(UI.parent.parent),
    )


def test_engine_files_exist():
    assert ENGINE.is_file(), "desktop/ui/ofx.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/ofx.selftest.js is missing"


def test_engine_parses_as_javascript():
    """`node --check` catches the syntax break that would otherwise surface as a blank canvas."""
    proc = subprocess.run([_node(), "--check", str(ENGINE)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_engine_selftest_passes():
    proc = _run_selftest()
    out = proc.stdout.strip()
    match = re.search(r"ofx selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 35, f"self-test shrank to {ok} checks — expected the full set"
    assert proc.returncode == 0


def test_decay_constant_matches_the_spec():
    """lambda = 500 ms is a stated requirement, not an implementation detail: after one lambda
    the track must sit at 1/e of its alpha."""
    out = subprocess.run(
        [_node(), "-e", "const m=require('./ofx.js').math;"
                       "console.log(m.decayAlpha(1,500,500).toFixed(6), m.decayAlpha(1,0,500).toFixed(6));"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=str(UI),
    )
    at_lambda, at_zero = out.stdout.split()
    assert abs(float(at_lambda) - 0.367879) < 1e-4, out.stdout
    assert float(at_zero) == 1.0


def test_engine_exposes_the_surface_the_view_wires():
    src = ENGINE.read_text(encoding="utf-8")
    for name in ("setData", "attach", "resize", "start", "stop", "stats", "snapToLive",
                 "setParams", "indexLevels", "profileBars", "applyLod", "applyMode"):
        assert re.search(rf"\b{name}\b", src), f"ofx.js no longer exposes {name}()"
    assert "globalThis.OFX" in src, "the engine must publish itself for the browser"


def test_pause_control_is_wired():
    """The freeze control is a UI module plus a chip in the topbar; both must exist, and the
    engine poll must check the flag, or the board keeps refreshing under the user."""
    pause = UI / "pause.js"
    assert pause.is_file(), "desktop/ui/pause.js is missing"
    src = pause.read_text(encoding="utf-8")
    for name in ("OFAPPause", "register", "setPaused", "isPaused"):
        assert name in src, f"pause.js no longer exposes {name}"
    assert "ofapPause" in (UI / "index.html").read_text(encoding="utf-8"), "the chip is not in the topbar"
    assert "OFAP_PAUSED" in (UI / "ofx-view.js").read_text(encoding="utf-8"), "the engine poll ignores the freeze"


def test_the_engine_adopts_the_clamped_params_after_a_save():
    """config_store clamps the engine's dials on write (ofx.R max 20, stack max 8, lambda 100–5000).
    The accepted block must come back to the controls: the save's answer carries it, and a control
    left on a value the store never took is the same 'two surfaces, one story' defect the symbol
    bar learned — the next params re-read would look like the app changing the user's input."""
    view = (UI / "ofx-view.js").read_text(encoding="utf-8")
    assert "async function _saveParamsNow" in view
    assert "adoptSavedOfx(res && res.ofx)" in view, "the save no longer adopts the stored block"
    assert "function adoptSavedOfx(saved)" in view, "the adoption helper is gone"
    assert "function adoptSavedOfx" in view and "OFX.setParams(next)" in view
    for control in ("ofxR", "ofxStack", "ofxLambda", "ofxMinBlock", "ofxVaPct", "ofxRamp"):
        assert re.search(rf"el\('{control}'\)\) el\('{control}'\)\.value = String\(OFX\.state\.params\.", view), \
            f"adoptSavedOfx no longer writes {control} back"


def test_the_params_reread_repairs_the_preset_chips():
    """loadParams and adoptSavedOfx write the number fields programmatically; a bare value write
    fires no event, so the preset combobox beside each field must be re-paired explicitly or it
    keeps naming the bygone value (the control pair in the same 'matching' family)."""
    view = (UI / "ofx-view.js").read_text(encoding="utf-8")
    assert view.count("if (window.OFAPPRESETS && OFAPPRESETS.refresh) OFAPPRESETS.refresh();") >= 2, \
        "the engine's re-seed paths stopped repairing the preset chips"
