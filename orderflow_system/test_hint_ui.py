"""§83 — the explain popover's browser module, gated the way the other UI engines are.

`desktop/ui/hint.js` turns a spec (from markup attributes or from a server answer) into the
card a user reads when something refuses them. Python cannot paint it, but it can gate the
module's Node self-test, its syntax, and two pins worth having: the action vocabulary is the
closed set the dispatcher understands, and the markup that declares hints actually ships in
`index.html` (a hint nobody attaches is a hint nobody reads).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
MODULE = UI / "hint.js"
SELFTEST = UI / "hint.selftest.js"
HTML = UI / "index.html"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def test_module_and_selftest_exist():
    assert MODULE.is_file(), "desktop/ui/hint.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/hint.selftest.js is missing"


def test_module_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(MODULE)], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8",
                          timeout=120, cwd=str(UI.parent.parent))
    out = proc.stdout.strip()
    match = re.search(r"hint selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 7, f"self-test shrank to {ok} checks — expected the full set"
    assert proc.returncode == 0


def test_the_action_vocabulary_is_closed():
    proc = subprocess.run(
        [_node(), "-e", "console.log(JSON.stringify(require('./hint.js').ACTIONS))"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=str(UI),
    )
    assert proc.returncode == 0, proc.stderr
    actions = json.loads(proc.stdout.strip())
    assert sorted(actions) == sorted(["lookup", "engine", "instruments", "wizard", "menu"])


def test_the_shell_ships_the_module_and_declares_its_hints():
    html = HTML.read_text(encoding="utf-8")
    assert "/desktop/hint.js" in html, "the shell never loads hint.js"
    for ident in ("ofxSymbolState", "ofxSymbolFind", "sourcePill", "livePill", "enginePill"):
        assert re.search(rf'id="{ident}"[^>]*data-hint-title|data-hint-title[^>]*id="{ident}"', html, re.S), \
            f"{ident} carries no hint"
    assert 'id="instLookup"' in html, "the Instruments view's look-up button is missing"


def test_the_view_module_is_registered_with_the_audit():
    audit = (Path(__file__).parent.parent / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"hint.js"' in audit, "scripts/audit_ui_refs.py JS_FILES is missing hint.js"


def test_the_skip_banner_offers_the_look_up():
    """The engine's own skip report is the moment a user needs the look-up: the banner must
    carry the button, not just the reason (it is the "crypto only" report, in context)."""
    ui = (UI / "ui.js").read_text(encoding="utf-8")
    assert "OFAPHINT.skippedNotice" in ui and "OFAPHINT.paintNotice" in ui, \
        "the skip banner does not offer the look-up"
    assert "ofxSymPanel" not in ui  # the panel id lived only in the Engine view's own module


def test_the_engine_start_path_announces_what_it_skipped():
    ui = (UI / "ui.js").read_text(encoding="utf-8")
    start = ui.find("/api/control/engine/start")
    assert start >= 0
    window = ui[start:start + 900]
    assert "skippedNotice" in window, "an engine start paints nothing about skipped instruments"
