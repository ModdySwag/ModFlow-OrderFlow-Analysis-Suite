"""Wave B T14b — B7: the notifications inbox.

The inbox reads the engine's own firings; this pins the reading-state clamps, the one-category-per-
kind rule (checked against the same kind list the palette's alert help carries), the routes, the
view's wiring, and the help topic every data-view requires.
"""

from __future__ import annotations

import re
from pathlib import Path

from orderflow_system.desktop import config_store

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def test_the_reading_state_persists_and_clamps() -> None:
    cfg = config_store.default_config()
    assert cfg["ui"]["notifications"] == {"read_ms": 0, "dnd": False, "priority": False}
    cfg["ui"]["notifications"] = {"read_ms": -5, "dnd": "yes", "priority": 1, "extra": 2}
    out = config_store._sanitise(cfg)["ui"]["notifications"]
    assert out == {"read_ms": 0, "dnd": True, "priority": True}, "an int watermark and two switches, nothing more"
    cfg["ui"]["notifications"] = {"read_ms": 1758100000000}
    assert config_store._sanitise(cfg)["ui"]["notifications"]["read_ms"] == 1758100000000


def test_every_alert_kind_is_categorised_exactly_once() -> None:
    search = _text("search.js")
    block = re.search(r"const ALERT_KIND_HELP = \[(.*?)\];", search, re.S)
    assert block, "the palette's alert help"
    kinds = re.findall(r"\['([a-z_]+)',", block.group(1))
    assert len(kinds) >= 17, "the kind list the help carries"
    inbox = _text("inbox.js")
    cats = re.search(r"const CATEGORIES = \{(.*?)\};", inbox, re.S)
    assert cats, "the categories map"
    listed = re.findall(r"'([a-z_]+)'", cats.group(1))
    assert sorted(listed) == sorted(kinds), "every kind lands in exactly one category"
    surf = re.search(r"const SURFACE_FOR_KIND = \{(.*?)\};", inbox, re.S)
    assert surf, "the surface map"
    sk = re.findall(r"([a-z_]+):", surf.group(1))
    assert sorted(sk) == sorted(kinds), "every kind knows where its evidence lives"


def test_the_routes_and_the_view() -> None:
    api = (PKG / "atlas" / "api.py").read_text(encoding="utf-8")
    for marker in ('@router.get("/notifications")', '@router.post("/notifications")',
                   '"read_all"', 'merge_config({"ui": {"notifications"', "h.alerts.recent"):
        assert marker in api, marker
    html = _text("index.html")
    for marker in ('data-view="inbox"', 'id="navInboxCount"', 'id="inboxDnd"', 'id="inboxReadAll"'):
        assert marker in html, marker
    assert html.index("/desktop/inbox.js") > html.index("/desktop/calendar.js")
    assert "id: 'view.inbox'" in _text("help-data.js"), "test_help requires a topic per view"
    assert ".inb-tile" in _text("modules.css")


def test_the_inbox_reads_the_engines_own_firings() -> None:
    src = _text("inbox.js")
    assert "'/api/atlas/notifications'" in src
    assert "chainOnEvent" in src and "atlasOnEvent" in src, "the badge rides the socket's dispatcher"
    assert "searchActivateSymbol(sym, { view: view })" in src, "act-on-click opens the evidence"
    assert "state.prefs.dnd ? '•' : String(state.unread)" in src, "DND silences the badge, not the record"
