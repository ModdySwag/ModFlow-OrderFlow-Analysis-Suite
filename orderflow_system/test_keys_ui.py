"""§92 — the shortcut helper menu, the program-wide shortcut prompts, and the audit's new keys.

Three contracts held together by reading the shipped files: the Keys menu is BUILT FROM the live
registry (a hand-written list could drift and lie), every advertised accelerator has a matching
binding (the File menu used to display Ctrl+Alt+R for a key that did not exist), and the physical
hide/show controls exist on both bars together with the annotation pass that tells controls their
own shortcuts.
"""

from __future__ import annotations

from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"


def test_the_keys_menu_is_built_from_the_live_registry():
    code = (UI / "menubar.js").read_text(encoding="utf-8")
    assert "{ id: 'keys', label: 'Keys'" in code
    assert "function keysItems" in code
    assert "OFAPKEYS.list()" in code, "the menu must read the registry, not a copy"
    assert "OFAPKEYS.run(row.id)" in code, "a dispatched row must run its action"


def test_the_markup_never_ships_literal_escape_text():
    """HTML does not interpret JS backslash-u escapes — they render as visible text. Caught live
    in §87 (a sub-line) and again in §92 (two toggle glyphs); this pin is the clamp that ends the
    class of bug, not just the instance."""
    import re as _re
    html = (UI / "index.html").read_text(encoding="utf-8")
    bad = sorted(set(_re.findall(r"\\u[0-9a-fA-F]{4}", html)))
    assert not bad, f"markup carries literal escape text: {bad}"


def test_every_advertised_accelerator_is_bound():
    """T3: the legend renders FROM the registry (keyId), so this pin holds both halves — the rows
    name the binding ids, and those ids resolve to real chords in keys.js. A displayed key that is
    not a real binding is exactly the §92 File-menu lie, one refactor later."""
    menubar = (UI / "menubar.js").read_text(encoding="utf-8")
    keys = (UI / "keys.js").read_text(encoding="utf-8")
    for key_id, chord in (("keyId: 'engine-start'", "keys: ['ctrl+alt+s']"),
                          ("keyId: 'engine-stop'", "keys: ['ctrl+alt+x']"),
                          ("keyId: 'engine-restart'", "keys: ['ctrl+alt+r']")):
        assert key_id in menubar, f"{key_id} is not advertised in the menu"
        assert chord in keys, f"{key_id} is displayed but {chord} is not bound"


def test_the_common_journeys_have_keys():
    keys = (UI / "keys.js").read_text(encoding="utf-8")
    for chord in ("keys: ['ctrl+f']", "keys: ['ctrl+pagedown']", "keys: ['ctrl+pageup']"):
        assert chord in keys, f"missing binding {chord}"
    assert "function cycleView" in keys
    menubar = (UI / "menubar.js").read_text(encoding="utf-8")
    total = (keys.count("id: 'zen'") + menubar.count("id: 'zen'"))
    assert total == 1, "zen must be bound exactly once (ids replace, duplicates silently lose)" 


def test_controls_are_told_their_shortcuts():
    keys = (UI / "keys.js").read_text(encoding="utf-8")
    assert "function annotate" in keys and "aria-keyshortcuts" in keys
    assert "annotate: annotate" in keys, "the pass must be exported for re-runs after renders"
    hint = (UI / "hint.js").read_text(encoding="utf-8")
    assert "aria-keyshortcuts" in hint and "hint-shortcut" in hint, "hover cards must show the key"


def test_every_bar_has_a_control_that_cannot_hide_with_it():
    html = (UI / "index.html").read_text(encoding="utf-8")
    for needle in ('id="railToggle"', 'id="menubarToggle"', 'id="railHide"', 'id="railReveal"'):
        assert needle in html, f"markup lacks {needle}"
    assert 'id="menubarReveal"' not in html, "the menubar's way back is its topbar toggle, not a reveal"
    chrome = (UI / "chrome.js").read_text(encoding="utf-8")
    assert "['#railToggle', 'rail']" in chrome and "['#menubarToggle', 'menubar']" in chrome
    assert "['#railReveal', 'rail']" in chrome, "the edge arrow must be wired"
    assert "aria-pressed" in chrome, "pressed faces must stay honest"
    menubar = (UI / "menubar.js").read_text(encoding="utf-8")
    assert 'id="mbHide"' not in menubar, "§119: the in-bar duplicate hide is gone — the boxed topbar toggle is the one"
    assert "mb-hide" not in menubar and "mb-grow" not in menubar, "no half-removed hide markup"
    css_mb = (UI / "modules.css").read_text(encoding="utf-8")
    assert ".mb-hide" not in css_mb and ".mb-grow" not in css_mb, "the removed control left its styles behind"
    css = (UI / "modules.css").read_text(encoding="utf-8")
    assert ".chrome-toggle" in css, "the persistent toggles carry a style"
    assert ".mb-reveal" not in css, "the menubar reveal stays replaced by its toggle"
    assert ".rail-reveal" in css, "the rail's visible way back is styled"
