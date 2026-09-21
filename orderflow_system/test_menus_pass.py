"""Gate for the menus pass (v2 competitive-reanalysis, 2026-09-19).

Pins what this pass added or decided:

  * Tools ▸ Export exists and names the three server-made CSV routes; the flow writes through
    `/api/control/export/save` (the shell's only real "export" contract — no download shelf);
  * File ▸ Recent is a real submenu fed by the one recents writer (`noteRecent`), whose callers
    are the workspace apply (menu.js), a profile apply (profiles.js) and a layout activate
    (shell.js);
  * the stub decisions: 'Reset rail order' retires (rail order is not user-editable), 'Exit'
    becomes a disabled row carrying its reason, and the list-kind variables get the real editor
    ('Edit list' retires);
  * `/params` accepts the list kind end-to-end (functional, against a temp config dir);
  * the `ui.recent` store clamps junk, keeps the three kinds, and caps at 8.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from orderflow_system.desktop import config_store, param_registry

from pathlib import Path

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _read(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


# ── the doors ──────────────────────────────────────────────────────────────────────────────────

def test_tools_export_door_names_the_three_routes():
    mb = _read("menubar.js")
    assert "label: 'Export', submenu: exportItems()" in mb
    assert "/api/atlas/export/tape/" in mb
    assert "/api/atlas/export/heatmap/" in mb
    assert "/api/atlas/export/alerts.csv" in mb
    assert "exportServerCsv" in mb
    assert "api('/api/control/export/save'" in mb, "the CSV must land as a real file"


def test_recent_rows_and_writers():
    mb = _read("menubar.js")
    assert "{ label: 'Recent', submenu: recentItems() }" in mb
    assert "function recentItems()" in mb
    assert "window.OFAPMENUBAR_RECENT = noteRecent" in mb

    menu = _read("menu.js")
    assert "applyWorkspaceByName" in menu, "the File-menu workspace rows must land somewhere real"
    assert "window.OFAPMENUBAR_RECENT('workspace'" in menu
    assert "applyWorkspaceByName, GROUPS, state" in menu, "the export list must carry it"

    prof = _read("profiles.js")
    assert "window.OFAPMENUBAR_RECENT('profile'" in prof

    shell = _read("shell.js")
    assert "window.OFAPMENUBAR_RECENT('layout'" in shell


def test_stub_decisions():
    mb = _read("menubar.js")
    assert "Reset rail order" not in mb, "the rail-order stub retired"
    assert "planned('Exit'" not in mb, "Exit is a decision, not a promise"
    assert "{ label: 'Exit', disabled: true" in mb
    assert "close the window (✕) — the app has no in-app quit by design" in mb
    assert "planned('Edit list'" not in mb, "the list editor is real now"
    assert "mbEditList" in mb


# ── the store ──────────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_recent_store_clamps(store):
    assert store.default_config()["ui"]["recent"] == []

    junk = [{"kind": "workspace", "name": "A"}, {"kind": "nope", "name": "B"},
            {"kind": "profile", "name": ""}, "not-a-dict",
            {"kind": "layout", "name": "x" * 80, "at": "soon"}]
    clean = store.save_config({"ui": {"recent": junk}})
    assert [r["kind"] for r in clean["ui"]["recent"]] == ["workspace", "layout"]
    assert len(clean["ui"]["recent"][1]["name"]) == 40
    assert clean["ui"]["recent"][1]["at"] == 0

    many = [{"kind": "workspace", "name": f"w{i}"} for i in range(20)]
    clean = store.save_config({"ui": {"recent": many}})
    assert len(clean["ui"]["recent"]) == 8


# ── /params and the list kind ──────────────────────────────────────────────────────────────────

def _params_set(payload):
    from orderflow_system.desktop import api as desktop_api

    return asyncio.run(desktop_api.params_set(payload))


def test_params_accepts_the_list_kind(store):
    bands = param_registry.BY_PATH["atlas.vwap.bands"]
    assert bands.kind == "list", "the fixture path must stay a list variable"

    out = _params_set({"path": "atlas.vwap.bands", "value": ["1", 2.5, "three", 0, -4]})
    assert out["ok"] is True
    assert out["value"] == [1.0, 2.5], out

    out = _params_set({"path": "atlas.vwap.bands", "value": "3, 4.5"})
    assert out["ok"] is True and out["value"] == [3.0, 4.5]

    out = _params_set({"path": "atlas.vwap.bands", "value": "nope"})
    assert out["ok"] is False, "an empty list must be refused, not written"

    # the store is still the last word: an out-of-range value comes back clamped/dropped
    out = _params_set({"path": "atlas.vwap.bands", "value": [1, 2, 1e9]})
    assert out["ok"] is True and out["value"] == [1.0, 2.0], "1e9 is outside the store's bound"

    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["atlas"]["vwap"]["bands"] == [1.0, 2.0]


# ── §129: the layout's previous versions, as a legible submenu ─────────────────────────────────

def test_the_layout_versions_row_is_one_submenu_not_a_wall():
    mb = _read("menubar.js")
    assert "label: 'Previous versions of this layout'" in mb, "the submenu row is missing"
    assert "submenu: versionItems(" in mb, "the versions are not a submenu"
    assert "versions.slice(0, 3)" not in mb, "the old flat three-row wall is back"
    assert "' · newest'" in mb, "rows do not say which version is the latest"
    assert "versionAge(" in mb and "versionStamp(" in mb, "rows carry no age/stamp"
    assert "Auto-cull old versions" in mb, "the auto-cull switch is missing"
    assert "body: { autocull: !autocull }" in mb, "the switch is not wired to the route"


def test_the_version_ring_is_explained_programme_wide():
    """The ask: say WHY the ring exists, why five, and what auto-cull does — in the help centre,
    the setup assistant and the Guide view, not only in the menu."""
    help_data = _read("help-data.js")
    assert "the one-click undo for a layout" in help_data
    assert "Why only the last five" in help_data
    assert "Auto-cull" in help_data and "keeps up to ten" in help_data
    guide = _read("guide.js")
    assert "Previous versions" in guide, "the wizard no longer explains the ring"
    assert "Auto-cull" in guide


def test_scrolling_the_open_dropdown_keeps_it_open():
    """The owner's §129 report: the top menu "randomly hides while changing options" — the dropdown's
    own scrollbar closed it. §134 removed the same closer's other false positive: a scroll EVENT is
    not a user gesture (the strips pin to the newest print, the signal log sticks to its bottom, so
    the app scrolls itself every few seconds and killed the menu after 10-20 s of data). The closer is
    now a real gesture — wheel/touch outside the bar — with the bar itself exempt; the other closers
    (mousedown-outside capture, focusin-outside, blur, Tab, Escape) must survive."""
    mb = _read("menubar.js")
    assert "document.addEventListener('scroll'" not in mb, \
        "the scroll-event closer is back — panels scroll themselves and it kills the menu mid-reach"
    assert "document.addEventListener('wheel', (ev) => {" in mb, "the user-scroll closer is gone"
    assert "document.addEventListener('touchmove', (ev) => {" in mb, "the touch-drag closer is gone"
    assert mb.count("ev.target.closest('#menuBar')) return;") >= 2, \
        "scrolling the dropdown itself must stay exempt"
    assert "document.addEventListener('mousedown', (ev) => {" in mb, "the outside-click guard is gone"
    assert "document.addEventListener('focusin', (ev) => {" in mb, "the focus guard is gone"
    assert "window.addEventListener('blur', () => closeAll());" in mb, "the blur guard is gone"
