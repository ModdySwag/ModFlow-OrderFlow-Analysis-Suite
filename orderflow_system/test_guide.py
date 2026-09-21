"""§123's gate: the onboarding & help layer — wizard keyboard, doors that land, no dead clicks.

guide.js carries the wizard, the Guide view and the inline walkthroughs; this file pins the
contracts that used to drift silently (it had no gate at all before): every door target is a real
view, every inline walkthrough has a Help-Centre continuation, and the keyboard grammar exists.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
GUIDE = UI / "guide.js"
MENUBAR = UI / "menubar.js"
HELPDATA = UI / "help-data.js"
IDX = UI / "index.html"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def test_the_modules_parse():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    for f in (GUIDE, MENUBAR):
        proc = subprocess.run([node, "--check", str(f)], capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        assert proc.returncode == 0, (f.name, proc.stderr)


def test_the_overlay_keyboard_grammar_exists():
    g = _text(GUIDE)
    assert "function overlayKeys(ev)" in g
    assert "document.addEventListener('keydown', overlayKeys)" in g, \
        "the overlay keys are never registered"
    assert "querySelector('#wizClose, #helpClose, #mt5NoticeClose')" in g, \
        "Esc must dismiss through the overlay's OWN close control"
    assert "overlays[overlays.length - 1]" in g, "only the top-most overlay may answer"
    assert "ev.key === 'Enter'" in g and "ev.key === 'Tab'" in g


def test_the_wizard_speaks_about_what_closing_does():
    g = _text(GUIDE)
    assert "Close \u2014 your place is kept; the assistant resumes at this step" in g
    assert "Setup assistant closed \u2014 it resumes at this step next time." in g
    assert "Close without changing anything" not in g, "the old false tooltip is back"


def test_focus_and_visited_dots():
    g = _text(GUIDE)
    assert 'aria-label="Setup assistant" tabindex="-1"' in g, "the card must be focusable"
    assert "card.focus({ preventScroll: true });" in g, "focus never rides into the dialog"
    assert 'data-wiz-dot="${n}"' in g, "visited dots must be addressable"
    assert "ev.target.closest('[data-wiz-dot]')" in g, "dots are not wired"


def test_no_dead_clicks_and_every_door_lands():
    g = _text(GUIDE)
    # a data-help button with no inline topic continues in the Help Centre (and LANDS there:
    # open() navigates + searches; openTopic's unknown-id path searched invisibly)
    assert "OFAPHELP.open(b.dataset.help)" in g, "the dead data-help buttons are back"
    # every door target is a real view (index.html + runtime-created ones) or a special case
    doors = set(re.findall(r'data-wiz-go="([a-z0-9_-]+)"', g))
    doors |= set(re.findall(r"view:\s*'([a-z0-9_-]+)'", g))
    runtime = set()
    for f in UI.glob("*.js"):
        s = _text(f)
        runtime |= set(re.findall(r'data-view="([a-z0-9_-]+)"', s))
        runtime |= set(re.findall(r'dataset\.view\s*=\s*"([a-z0-9_-]+)"', s))
    views = set(re.findall(r'data-view="([a-z0-9_-]+)"', _text(IDX))) | runtime
    specials = {"hotkeys", "menu"}
    missing = doors - views - specials
    assert not missing, "these wizard doors land nowhere: " + ", ".join(sorted(missing))


def test_every_inline_walkthrough_has_a_centre_continuation():
    g = _text(GUIDE)
    inline_ids = set(re.findall(r"^    ([a-z0-9_.]+): \{$", g.split("const HELP_TOPICS = {")[1], re.M))
    # view modules extend the map at runtime (studies.js, platforms.js, ofx-view.js) — a static
    # read of guide.js alone sees only the first ten keys and lies about coverage
    for f in UI.glob("*.js"):
        inline_ids |= set(re.findall(r"HELP_TOPICS\.([a-z0-9_.]+)\s*=", _text(f)))
    centre = set(re.findall(r"([a-z0-9_.]+): '", g.split("const CENTRE_QUERY = {")[1].split("};")[0]))
    assert inline_ids, "the inline topic map became unparsable"
    assert inline_ids <= centre, "no Help-Centre continuation for: " + ", ".join(sorted(inline_ids - centre))
    assert 'id="helpToCentre"' in g and "OFAPHELP.open(CENTRE_QUERY[id] || id)" in g
    assert 'id="guideCentreBtn"' in g and "OFAPHELP.open('')" in g


def test_the_wizard_step_contract():
    g = _text(GUIDE)
    body = g.split("const WIZ_STEPS = [")[1].split("\n];")[0]
    steps = len(re.findall(r"^    \{\n        title: '", body, re.M)) or body.count("title: '")
    # 9 static + the three runtime splices (MT5, broker, the before-the-end step) = the 12 the user sees
    assert steps >= 9, f"only {steps} static express steps found"
    assert g.count("WIZ_STEPS.splice(") >= 3, "the runtime step additions are gone"
    assert "Step ${i + 1} of ${wizList().length}" in g
    assert "wizList().length - 1 ? 'Save & finish' : 'Next'" in g
    assert "(GUIDE.mode === 'pro') ? WIZ_STEPS.concat(WIZ_PRO) : WIZ_STEPS" in g


def test_the_menu_rows_that_named_real_panels_are_doors_now():
    m = _text(MENUBAR)
    for dead in ("planned('History & retention'", "planned('Replay\u2026'", "planned('Notifications\u2026'",
                 "planned('Performance\u2026'", "planned('Studies library'", "planned('Import profile\u2026'",
                 "planned('Export data\u2026'"):
        assert dead not in m, f"the dead row is back: {dead}"
    assert "OFAPNAV.jump('replay')" in m
    assert "showView('studies')" in m
    assert "showView('profiles')" in m
    assert "folder: 'exports'" in m
    assert m.count("showView('settings')") >= 3
