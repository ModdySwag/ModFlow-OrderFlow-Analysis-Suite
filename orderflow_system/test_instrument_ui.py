"""§82 — the instrument look-up's browser module, gated the way the other UI engines are.

`desktop/ui/instrument.js` turns the server's look-up answer into a chip, suggestion rows and
an action list. Python cannot paint it, but it can gate the module's own Node self-test, its
syntax, and — the pin worth having — that the action vocabulary the browser draws is exactly
the closed set `desktop/instrument_lookup.py` may emit. A new action on one side and not the
other would otherwise surface as a silently dead button.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.desktop import instrument_lookup

UI = Path(__file__).parent / "desktop" / "ui"
MODULE = UI / "instrument.js"
SELFTEST = UI / "instrument.selftest.js"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def test_module_and_selftest_exist():
    assert MODULE.is_file(), "desktop/ui/instrument.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/instrument.selftest.js is missing"


def test_module_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(MODULE)], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8",
                          timeout=120, cwd=str(UI.parent.parent))
    out = proc.stdout.strip()
    match = re.search(r"instrument selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 14, f"self-test shrank to {ok} checks — expected the full set"
    assert proc.returncode == 0


def test_the_action_vocabulary_matches_the_python_side():
    """The browser may only draw actions the server may emit — one closed set, two languages."""
    proc = subprocess.run(
        [_node(), "-e", "console.log(JSON.stringify(require('./instrument.js').ACTIONS))"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=str(UI),
    )
    assert proc.returncode == 0, proc.stderr
    js_actions = json.loads(proc.stdout.strip())
    assert js_actions == list(instrument_lookup.ACTIONS), (
        f"JS {js_actions} vs Python {list(instrument_lookup.ACTIONS)}")


def test_the_state_vocabulary_matches_the_python_side():
    proc = subprocess.run(
        [_node(), "-e", "console.log(JSON.stringify(Object.keys(require('./instrument.js').STATES)))"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=str(UI),
    )
    assert proc.returncode == 0, proc.stderr
    js_states = json.loads(proc.stdout.strip())
    assert sorted(js_states) == sorted(instrument_lookup.STATES), (
        f"JS {js_states} vs Python {list(instrument_lookup.STATES)}")


def test_the_picker_is_wired_from_config_to_markup():
    """§85: the symbol section's quick picker — the pure builder in the module, the wiring in the
    view, the markup the select lands in. A rename in any of the three would leave a dead control."""
    root = Path(__file__).parent / "desktop" / "ui"
    instrument = (root / "instrument.js").read_text(encoding="utf-8")
    view = (root / "ofx-view.js").read_text(encoding="utf-8")
    page = (root / "index.html").read_text(encoding="utf-8")
    assert "pickerRows" in instrument and "pickerRows: pickerRows" in instrument
    assert "refreshPicker" in view and "pickSymbol" in view and "ofxSymPick" in view
    assert 'id="ofxSymPick"' in page


def test_the_view_module_is_registered_with_the_audit():
    """A new ui/*.js that the audit does not know is a module nothing checks for dead calls."""
    audit = (Path(__file__).parent.parent / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"instrument.js"' in audit, "scripts/audit_ui_refs.py JS_FILES is missing instrument.js"
