"""§119's gate: the context-jump way back (navreturn.js) is wired, styled and gated.

The chip itself is `desktop/ui/navreturn.js` — a single-slot navigation memory wrapped around
`window.showView`, painted into the destination view's head. This file pins the wiring as data
(loaded last, audited, frozen in the listener ledger, jump sites routed through it) and shells out
to `navreturn.selftest.js` for the behavioural half of `_decide`.

Deliberately dumb: source text in, assertions out, no browser, no imports from the front end.
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
NAV = UI / "navreturn.js"
SELFTEST = UI / "navreturn.selftest.js"
CSS = UI / "modules.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_module_and_its_selftest_exist():
    assert NAV.is_file() and SELFTEST.is_file()


def test_the_module_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, "--check", str(NAV)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


def test_the_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"navreturn selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 12, f"only {found.group(1)} checks ran — the selftest shrank"


def test_the_module_loads_after_every_other_wrapper():
    order = re.findall(r'<script[^>]+src="/desktop/([^"]+)"', _text(INDEX))
    assert "navreturn.js" in order, "navreturn.js is not loaded at all"
    for other in ("shell.js", "help.js", "menubar.js"):
        assert order.index(other) < order.index("navreturn.js"), \
            f"navreturn.js wraps showView — it must load after {other}"


def test_the_audit_scans_the_new_surface():
    audit = _text(ROOT / "scripts" / "audit_ui_refs.py")
    assert '"navreturn.js"' in audit


def test_the_chip_is_styled():
    css = _text(CSS)
    assert ".nav-back" in css, "the chip has no style"
    assert ":has(.hm-pro-bar)" in css, \
        "the minimal-mode field rule must exempt the pro bar's own field (its way back)"


def test_help_opens_record_the_origin_and_nothing_else_surprises():
    nav = _text(NAV)
    assert "to === 'help'" in nav, "every route into help must record where it came from"
    assert "__ofapNavWrapped" in nav, "the showView wrap must be single-install guarded"


def test_the_registered_jump_sites_route_through_ofapnav():
    for name, needle in (
        ("hint.js", "OFAPNAV.jump('instruments')"),
        ("ofx-view.js", "OFAPNAV.jump('instruments', 'Engine')"),
        ("heatmap-pro.js", "OFAPNAV.jump('replay', 'Heatmap')"),
        ("menubar.js", "OFAPNAV.jump('platforms')"),
        ("menubar.js", "OFAPNAV.jump('logs')"),
        ("menubar.js", "OFAPNAV.jump('instruments')"),
    ):
        assert needle in _text(UI / name), f"{name} lost its jump route: {needle}"
    menu = _text(UI / "menubar.js")
    assert menu.count("OFAPNAV.jump(") >= 6, "the menu's task rows shrank — re-check list.txt item 4"


def test_the_heatmap_panel_keeps_its_own_way_back():
    hm = _text(UI / "heatmap-pro.js")
    assert "minimal: on — restore" in hm, "the minimal face must state the way back"
    assert "heatmap-minimal" in hm and "keys: ['m']" in hm, "the m toggle is gone"
    assert "function fitAll()" in hm and "if (act === 'fit') { fitAll(); return; }" in hm, \
        "fit must reset the view through its own dials, not no-op"
    assert "fitAll: fitAll" in hm, "the exported surface lost fitAll"


def test_the_menubar_has_exactly_one_hide_control():
    menu = _text(UI / "menubar.js")
    assert 'id="mbHide"' not in menu, "the in-bar hide is back — one control per action"
    html = _text(INDEX)
    assert 'id="menubarToggle"' in html, "the boxed topbar toggle must remain"
