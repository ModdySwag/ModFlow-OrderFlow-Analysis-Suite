"""§89 — per-surface pause: every wired Pause button must correspond to a real hold.

The honesty rule of the audit: a button that pretends to freeze a panel whose paint path never
consults the arbiter would be worse than no button. These pins read the shipped files and hold the
two halves together — the markup that offers the control and the code that honours it — plus the
market-watch refactor (one pause system, not two) and the intent module's user-hold API.
"""

from __future__ import annotations

from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"
INDEX = UI / "index.html"

#: surf id -> the file whose code must consult the arbiter for that surface
WIRED = {
    "overview": "ui.js", "chart": "ui.js", "orderflow": "ui.js", "depth": "ui.js",
    "tape": "ui.js", "signals": "ui.js", "marketwatch": "ui.js",
    "ofx": "ofx-view.js", "trackers": "atlas-v2.js",
}


def test_every_pause_button_has_a_real_hold():
    html = INDEX.read_text(encoding="utf-8")
    for surface, owner in WIRED.items():
        assert f'data-surf="{surface}"' in html, f"no Pause button for {surface}"
        code = (UI / owner).read_text(encoding="utf-8")
        assert f"held('{surface}')" in code, f"{owner} never consults the arbiter for {surface}"


def test_each_wired_surface_is_declared_on_its_section():
    html = INDEX.read_text(encoding="utf-8")
    for surface in WIRED:
        assert f'data-surface="{surface}"' in html, f"section for {surface} carries no data-surface"


def test_the_market_watch_uses_the_shared_pause_not_a_second_one():
    code = (UI / "ui.js").read_text(encoding="utf-8")
    assert "mwPaused" not in code, "the board must not keep a parallel pause flag beside the arbiter"
    assert "OFAPINTENT.held('marketwatch')" in code


def test_the_scanner_is_wired_too_even_though_it_injects_its_own_view():
    code = (UI / "scanner.js").read_text(encoding="utf-8")
    for needle in ('data-surf="scanner"', "held('scanner')", "OFAPPause.register"):
        assert needle in code, f"scanner.js lacks {needle}"


def test_intent_exposes_the_user_hold_api():
    code = (UI / "intent.js").read_text(encoding="utf-8")
    for name in ("setUser", "toggleUser", "userHeld", "onUserHold"):
        assert name in code, f"intent.js lacks {name}"


def test_user_holds_persist_but_never_silently():
    code = (UI / "intent.js").read_text(encoding="utf-8")
    assert "ofap.userholds" in code, "holds must be remembered across a reload"
    assert "paintButtons" in code, "buttons must be repainted from the effective state"
