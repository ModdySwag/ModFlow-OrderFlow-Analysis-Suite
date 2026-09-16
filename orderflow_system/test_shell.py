"""The terminal shell (desktop/ui/shell.js) — loaded, self-tested, and inert in Classic mode.

The shell re-parents panels into widget frames, so Python cannot exercise it: it is DOM code. What
this gates is (a) its own Node self-test, which drives the layout maths the store's clamps mirror,
(b) the grid/cap numbers agreeing with `config_store`, and (c) the invariants that keep Classic safe —
the module is loaded, it is registered with the UI audit, and it contains no engine, socket or feed
call. A shell that could stop ingest would be the one failure this layer exists to avoid.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).parent / "desktop" / "ui"
SHELL = UI / "shell.js"
SELFTEST = UI / "shell.selftest.js"
ROOT = Path(__file__).resolve().parents[1]


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_shell_files_exist():
    assert SHELL.is_file(), "desktop/ui/shell.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/shell.selftest.js is missing"


def test_the_shell_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(SHELL)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_shell_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=120,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"shell selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 20, f"the self-test shrank to {ok} checks — expected the layout and gesture rules"
    assert proc.returncode == 0


def test_the_shell_exposes_the_documented_surface():
    src = _read(SHELL)
    for name in ("OFAPSHELL", "switchTo", "focusView", "openWidget", "closeWidget", "activateTab",
                 "stats", "arrange", "math", "bounds", "maximise", "setFocus", "addTab", "closeTab",
                 "reorderTabs", "renameTab", "openPanelSettings", "saveAs", "renameLayout",
                 "duplicateLayout", "deleteLayout", "activateLayout", "saveForScreen", "resetBoard",
                 "exportLayout", "importLayout", "layouts", "screenKey"):
        assert name in src, f"shell.js must expose {name}"


def test_the_layout_menu_switch_and_status_fields_are_wired():
    """The phase-2 surface: a Layout menu, the top-bar workspace switch, and the status-bar fields."""
    html = _read(UI / "index.html")
    bar = _read(UI / "menubar.js")
    shell = _read(SHELL)
    assert "{ id: 'layout', label: 'Layout'" in bar, "the Layout menu must exist"
    assert "mbPromptInput" in bar, "text answers are asked in place, never with window.prompt"
    assert "layoutItems()" in bar, "and its contents come from the store, not a fixed list"
    assert 'id="modeSwitch"' in html and 'data-mode="terminal"' in html, "the top-bar switch"
    for field in ("statusMode", "statusTab", "statusWidgets", "statusFeed"):
        assert f'id="{field}"' in html, f"{field} must exist in the status bar"
        assert field in shell, f"the shell must write {field}"


def test_the_shell_is_loaded_and_registered():
    assert 'src="/desktop/shell.js"' in _read(UI / "index.html"), "index.html must load the shell"
    assert 'id="railTerminal"' in _read(UI / "index.html"), "there must be a way in from the rail"
    assert "shell.js" in _read(ROOT / "scripts" / "audit_ui_refs.py"), "register it in JS_FILES"


def test_the_grid_and_caps_agree_with_the_store():
    """Two clamps, one set of numbers: drift here is an arrangement the shell draws and the store trims."""
    src = _read(SHELL)
    grid = re.search(r"const GRID = \{ cols: (\d+), rows: (\d+) \}", src)
    assert grid, "shell.js must declare its grid"
    assert (int(grid.group(1)), int(grid.group(2))) == (config_store.LAYOUT_GRID_COLS,
                                                       config_store.LAYOUT_GRID_ROWS)
    assert f"const MAX_TABS = {config_store.LAYOUT_MAX_TABS};" in src
    assert f"const MAX_WIDGETS = {config_store.LAYOUT_MAX_WIDGETS};" in src


def test_the_shell_never_touches_ingest():
    """Arrangement is presentation: no engine call, no socket, no feed."""
    src = _read(SHELL)
    for forbidden in ("/api/control/engine", "WebSocket", "engine/stop", "engine/restart",
                      "engine/start", "/api/atlas/", "trade", "tick_buffer"):
        assert forbidden not in src, f"the shell must not touch ingest ({forbidden})"


def test_classic_mode_is_delegation_only():
    """The wrapper exists to hand a nav click to the terminal; in Classic it must call straight through."""
    src = _read(SHELL)
    assert "S.base.apply(window, arguments)" in src, "Classic must be the app's own showView, untouched"
    entering = src[src.index("function enterTerminal"):src.index("function leaveTerminal")]
    assert "document.body.classList.add('term-mode')" in entering, "the mode class is set on entering"
    leaving = src[src.index("function leaveTerminal"):src.index("function switchTo")]
    assert "classList.remove('term-mode')" in leaving, "and only entering Terminal sets it"
    assert "buildHost()" in entering, "the host is built inside enterTerminal, never at load"


def test_the_shell_tells_the_panels_when_their_box_changed():
    """A re-parent is invisible to the window resize listeners the views already have, and a canvas
    measured in Classic keeps that size inside a widget (293x240 in a 213x148 stage) unless the shell
    announces the change — which is what `ofap:relayout` is for."""
    assert "ofap:relayout" in _read(SHELL), "the shell must announce a re-layout"
    assert "ofap:relayout" in _read(UI / "ofx-view.js"), "and the Engine view must act on it"


def test_only_the_config_store_holds_the_arrangement():
    """One store, no second copy: the shell must not keep a layout in browser storage."""
    src = _read(SHELL)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB"):
        assert forbidden not in src, f"layouts belong in the config file, not {forbidden}"
