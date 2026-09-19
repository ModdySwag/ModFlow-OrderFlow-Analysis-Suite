"""§117 — the user's own shortcut chords: the registry half, the sheet half, and the store half.

The competitive audit asked for a Hot Keys surface (per-action bindings, conflict detection, a
printable list). The registry, the sheet and the copy-list already existed; what was missing is
the user's own chord. These pins hold the three halves together — keys.js resolves an override
and names conflicts, menu.js's sheet owns the capture + the save, and config_store guards the
shape and REBUILDS the block, which is what lets a reset actually remove a stored chord.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).resolve().parent / "desktop" / "ui"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_the_registry_exposes_the_rebinding_half():
    code = (UI / "keys.js").read_text(encoding="utf-8")
    for name in ("keysFor", "applyOverrides", "rebind", "clearOverride", "clearAllOverrides",
                 "overridesMap", "conflicts"):
        assert name in code, f"keys.js lacks {name}"
    assert "keysFor(b).indexOf(chord)" in code, "resolve must consult the override"
    assert "custom: custom" in code, "list() must tell the sheet which rows are custom"


def test_the_sheet_owns_capture_and_save():
    code = (UI / "menu.js").read_text(encoding="utf-8")
    for needle in ("hk-edit", "beginCapture", "captureKeys", "OFAPKEYS.rebind",
                   "OFAPKEYS.conflicts", "hkResetAll", "/api/control/config",
                   "ui: { keys:", "OFAPKEYS.overrides()"):
        assert needle in code, f"menu.js lacks {needle}"


def test_boot_applies_the_saved_overrides():
    code = (UI / "ui.js").read_text(encoding="utf-8")
    assert "applyOverrides" in code, "boot must adopt the saved overrides"


def test_the_menu_and_the_help_name_the_way_in():
    menu = (UI / "menubar.js").read_text(encoding="utf-8")
    assert "Change a shortcut" in menu, "the Keys menu must carry the rebind entry point"
    help_text = (UI / "help-data.js").read_text(encoding="utf-8")
    assert "captures your own combination" in help_text, \
        "the keyboard topic must teach the sheet's Change affordance"


def test_the_store_ships_the_default_block(store):
    cfg = store.default_config()
    assert cfg["ui"]["keys"] == {"version": 1, "overrides": {}}


def test_the_store_clamps_the_shape(store):
    cfg = store.default_config()
    cfg["ui"]["keys"] = {"version": 9, "overrides": {
        "engine-start": ["ctrl+alt+1"],
        "BAD ID!": ["ctrl+q"],
        "view-switch": ["nope", "shift+?", "ctrl+shift+k"],
        "many": ["ctrl+1", "ctrl+2", "ctrl+3", "ctrl+4", "ctrl+5"],
        "empty": [],
    }}
    store.save_config(cfg)
    out = store.load_config()["ui"]["keys"]
    assert out["version"] == 1
    assert out["overrides"]["engine-start"] == ["ctrl+alt+1"]
    assert "BAD ID!" not in out["overrides"], "an invalid binding id must be dropped"
    assert out["overrides"]["view-switch"] == ["ctrl+shift+k"], "bad chords drop; shift+punct never forms"
    assert out["overrides"]["many"] == ["ctrl+1", "ctrl+2", "ctrl+3", "ctrl+4"], "the 4-chord cap holds"
    assert "empty" not in out["overrides"], "an emptied override is the removal marker, not a value"


def test_an_emptied_override_is_removed_by_merge_plus_rebuild(store):
    """The sheet resets a key by posting [] for it; a plain deep-merge would keep the stored
    value — the store rebuilds the block on every save, which is what makes removal possible."""
    cfg = store.load_config()
    cfg["ui"]["keys"] = {"version": 1, "overrides": {"freeze": ["p"]}}
    store.save_config(cfg)
    saved = store.merge_config({"ui": {"keys": {"overrides": {"freeze": []}}}})
    assert "freeze" not in saved["ui"]["keys"]["overrides"]
    assert "freeze" not in store.load_config()["ui"]["keys"]["overrides"], "and it stayed gone on disk"
