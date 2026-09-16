"""P1-9's gate: the app's one shortcut map exists, is wired, and carries the eight actions.

The map is `desktop/ui/keys.js` — one registry, one dispatcher, one source for the hotkey sheet.
This file checks the wiring as data (the module is loaded, loaded early enough to be registered
into, audited, and every action the phase names is bound by the module that owns it) and shells out
to `keys.selftest.js` for the behavioural half. The live pass is the handoff's §44.

Deliberately dumb: source text in, assertions out, no browser, no imports from the app.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
ROOT = Path(__file__).resolve().parents[1]
INDEX = UI / "index.html"
KEYS = UI / "keys.js"
SELFTEST = UI / "keys.selftest.js"

#: Every action the phase names must be reachable with no mouse — the binding's id lives in the
#: module that owns the action (keys.js for the app-core ones).
REQUIRED_ACTIONS = {
    "palette": "search.js",
    "freeze": "pause.js",
    "view-switch": "keys.js",
    "zoom-time-in": "ofx-view.js",
    "zoom-time-out": "ofx-view.js",
    "zoom-price-in": "ofx-view.js",
    "zoom-price-out": "ofx-view.js",
    "selection-clear": "ofx-view.js",
    "export": "ofx-view.js",
    "replay-play": "atlas.js",
    "replay-seek-back": "atlas.js",
    "replay-seek-fwd": "atlas.js",
    "alert-from-cursor": "heatmap-pro.js",
}

#: Static modules that register a binding at parse time (search.js is injected later) — each must
#: load AFTER keys.js, or its `OFAPKEYS.bind` call finds nothing and the key silently does not exist.
REGISTERING_MODULES = ["menu.js", "pause.js", "atlas.js", "heatmap-pro.js", "ofx-view.js",
                       "strips.js", "drawings.js", "menubar.js", "shell.js"]

#: The globals these modules used to dispatch themselves; P1-9 moved them into the one map.
MIGRATED = ["menu.js", "pause.js", "ui.js", "search.js"]


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8", errors="replace")


def _order(html: str) -> list[str]:
    srcs = re.findall(r'<script[^>]+src="(/desktop/[^"]+)"', html)
    return [s[len("/desktop/"):] for s in srcs]


def test_the_map_and_its_selftest_exist():
    assert KEYS.is_file() and SELFTEST.is_file()


def test_the_map_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, "--check", str(KEYS)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


def test_the_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"keys selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 30, f"only {found.group(1)} checks ran — the selftest shrank"


def test_the_map_is_loaded_before_every_module_that_registers_into_it():
    order = _order(INDEX.read_text(encoding="utf-8", errors="replace"))
    assert "keys.js" in order, "keys.js is not loaded at all"
    at = order.index("keys.js")
    early = [m for m in REGISTERING_MODULES if m in order and order.index(m) < at]
    assert not early, f"these register before the map exists: {early}"


def test_the_audit_scans_the_map():
    audit = (ROOT / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8", errors="replace")
    assert '"keys.js"' in audit, "keys.js is missing from JS_FILES"


def test_every_required_action_is_bound_by_the_module_that_owns_it():
    missing = []
    for action, owner in REQUIRED_ACTIONS.items():
        text = _text(owner) if (UI / owner).is_file() else ""
        if f"'{action}'" not in text:
            missing.append(f"{action} ({owner})")
    assert not missing, "actions the phase names are not bound anywhere: " + ", ".join(missing)


def test_one_dispatcher_only():
    text = _text("keys.js")
    listeners = text.count("addEventListener('keydown'")
    assert listeners == 1, f"keys.js must attach exactly one keydown listener, found {listeners}"
    assert "isTypingTarget" in text, "the typing guard is missing from the dispatcher"


def test_the_sheet_renders_from_the_map_and_the_old_list_is_gone():
    menu = _text("menu.js")
    assert "OFAPKEYS.list" in menu, "the hotkey sheet no longer renders from the map"
    assert "const HOTKEYS" not in menu, "the hand-written HOTKEYS list came back"


def test_the_migrated_modules_no_longer_dispatch_their_globals():
    offenders = [name for name in MIGRATED if "document.addEventListener('keydown'" in _text(name)]
    assert not offenders, f"these still bind global keys outside the map: {offenders}"
