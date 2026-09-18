"""§91 — hide/show for the program's frame (top menu bar, side rail, status bar), pinned.

The contract: one owner module (chrome.js) drives the classes, the View menu and the B/R keys,
hiding is remembered per browser, and — the part that matters most — hiding the MENU BAR can
never trap the user, because a keyboard toggle always exists and is bound in the same module.
"""

from __future__ import annotations

from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"


def test_the_owner_module_ships_and_is_registered():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'src="/desktop/chrome.js"' in html
    code = (UI / "chrome.js").read_text(encoding="utf-8")
    for needle in ("OFAPCHROME", "menubar-hidden", "rail-hidden", "status-hidden", "ofap.chrome"):
        assert needle in code, f"chrome.js lacks {needle}"


def test_hiding_the_menu_bar_can_never_trap_the_user():
    code = (UI / "chrome.js").read_text(encoding="utf-8")
    assert "chrome-menubar" in code and "keys: ['b']" in code, "the B key must always bring the bar back"
    assert "chrome-rail" in code and "keys: ['r']" in code


def test_the_view_menu_offers_all_three_and_delegates():
    code = (UI / "menubar.js").read_text(encoding="utf-8")
    assert "{ label: 'Menu bar'" in code
    assert "{ label: 'Rail'" in code and "{ label: 'Status bar'" in code
    assert "OFAPCHROME.toggle('menubar')" in code and "OFAPCHROME.toggle('rail')" in code


def test_the_css_rules_exist_for_every_toggle():
    css = (UI / "modules.css").read_text(encoding="utf-8")
    assert ".app.menubar-hidden .menubar { display: none; }" in css
    assert ".app.rail-hidden .rail { display: none; }" in css
    assert ".app.status-hidden .statusbar { display: none; }" in css
    assert ".chrome-toggle" in css, "the persistent toggles carry a style"
    assert ".app.rail-hidden .rail-reveal" in css, "the edge return arrow shows when the rail is hidden"
