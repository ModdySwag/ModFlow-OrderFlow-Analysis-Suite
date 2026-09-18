"""Terminal layouts — the arrangement store behind the shell (plan: docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md).

Pinned here: the defaults ship the layouts block, a layout round-trips through the sanitiser with its
geometry inside the grid, panels and ids this build cannot honour are dropped rather than stored, the
caps hold, and the endpoints answer with the state the store *accepted* — including a refusal.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from orderflow_system.desktop import api, config_store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def _layout(**over):
    layout = {
        "id": "lymain", "name": "My terminal", "mode": "terminal", "screen_key": "1920x1080", "theme": "dark",
        "tabs": [{"id": "main", "name": "Main", "widgets": [
            {"view": "ofx", "x": 0, "y": 0, "w": 8, "h": 5, "link": "A"},
            {"view": "tape", "x": 8, "y": 0, "w": 4, "h": 5},
            {"view": "depth", "x": 0, "y": 5, "w": 6, "h": 3},
        ]}],
    }
    layout.update(over)
    return layout


# ── the store ──────────────────────────────────────────────────────────────────────────────────

def test_defaults_carry_the_layouts_block(store):
    cfg = store.default_config()
    assert cfg["layouts"] == {"mode": "classic", "active": "", "items": {}, "versions": {}}


def test_a_layout_round_trips_with_its_geometry(store):
    clean = store.save_config({"layouts": {"mode": "terminal", "active": "lymain",
                                           "items": {"lymain": _layout()}}})
    block = clean["layouts"]
    assert block["mode"] == "terminal" and block["active"] == "lymain"
    stored = block["items"]["lymain"]
    assert stored["name"] == "My terminal"
    assert stored["screen_key"] == "1920x1080"
    assert [(w["view"], w["x"], w["y"], w["w"], w["h"]) for w in stored["tabs"][0]["widgets"]] == [
        ("ofx", 0, 0, 8, 5), ("tape", 8, 0, 4, 5), ("depth", 0, 5, 6, 3)]
    assert stored["tabs"][0]["widgets"][0]["link"] == "A"

    # …and it comes back through a fresh load, which is what the shell reads
    assert store.load_config()["layouts"]["items"]["lymain"]["tabs"][0]["widgets"][0]["view"] == "ofx"


def test_geometry_is_clamped_inside_the_grid(store):
    clean = store.save_config({"layouts": {"items": {"ly1": {"name": "X", "tabs": [{"widgets": [
        {"view": "ofx", "x": 999, "y": 999, "w": 999, "h": 999},
        {"view": "tape", "x": 9, "y": 7, "w": 6, "h": 4},
        {"view": "depth", "x": "left", "w": "wide", "h": 0},
    ]}]}}}})
    widgets = clean["layouts"]["items"]["ly1"]["tabs"][0]["widgets"]
    assert widgets[0]["w"] == config_store.LAYOUT_GRID_COLS
    assert widgets[0]["h"] == config_store.LAYOUT_GRID_ROWS
    assert widgets[0]["x"] == 0 and widgets[0]["y"] == 0
    # x is clamped against the width the same call produced, so nothing hangs off the right edge
    assert (widgets[1]["x"], widgets[1]["w"]) == (6, 6)
    assert (widgets[1]["y"], widgets[1]["h"]) == (4, 4)
    # a zero size is a real number, so it clamps to the minimum cell (1) rather than to the default
    assert (widgets[2]["w"], widgets[2]["h"], widgets[2]["x"]) == (6, 1, 0)


def test_unidentifiable_ids_and_panels_are_dropped_not_stored(store):
    clean = store.save_config({"layouts": {"items": {
        "Not A Slug": {"name": "bad id"},
        "ly-ok": {"name": "kept", "tabs": [{"widgets": [
            {"view": "ofx"},
            {"view": "OFX!"},                     # not a slug
            {"view": ""},
            "not-a-mapping",
        ]}]},
    }}})
    items = clean["layouts"]["items"]
    assert list(items) == ["ly-ok"]
    assert [w["view"] for w in items["ly-ok"]["tabs"][0]["widgets"]] == ["ofx"]


def test_caps_hold(store):
    many = {f"ly{i}": {"name": f"L{i}"} for i in range(40)}
    clean = store.save_config({"layouts": {"items": many}})
    assert len(clean["layouts"]["items"]) == config_store.LAYOUT_MAX_ITEMS

    clean = store.save_config({"layouts": {"items": {"ly1": {
        "tabs": [{"id": f"t{i}", "widgets": [{"view": f"v{i}"} for i in range(40)]} for i in range(20)]}}}})
    tabs = clean["layouts"]["items"]["ly1"]["tabs"]
    assert len(tabs) == config_store.LAYOUT_MAX_TABS
    assert len(tabs[0]["widgets"]) == config_store.LAYOUT_MAX_WIDGETS


def test_tab_ids_are_slugs_and_unique(store):
    clean = store.save_config({"layouts": {"items": {"ly1": {"tabs": [
        {"id": "main"}, {"id": "main"}, {"id": "TAB ONE"}]}}}})
    ids = [t["id"] for t in clean["layouts"]["items"]["ly1"]["tabs"]]
    assert len(set(ids)) == len(ids), ids
    assert all(config_store.LAYOUT_ID_RE.match(i) for i in ids), ids


def test_mode_and_active_are_whitelisted(store):
    clean = store.save_config({"layouts": {"mode": "sideways", "active": "ly-nope", "items": {"ly1": {}}}})
    assert clean["layouts"]["mode"] == "classic"
    assert clean["layouts"]["active"] == "", "an active id that does not exist is not stored"
    clean = store.save_config({"layouts": {"mode": "TERMINAL", "active": "ly1", "items": {"ly1": {}}}})
    assert clean["layouts"]["mode"] == "terminal" and clean["layouts"]["active"] == "ly1"


def test_widget_settings_are_scalars_only(store):
    clean = store.save_config({"layouts": {"items": {"ly1": {"tabs": [{"widgets": [
        {"view": "ofx", "settings": {"symbol": "btcusdt", "R": 5, "on": True, "nested": {"a": 1},
                                     "list": [1, 2], "long": "x" * 400}},
    ]}]}}}})
    settings = clean["layouts"]["items"]["ly1"]["tabs"][0]["widgets"][0]["settings"]
    assert settings == {"symbol": "btcusdt", "R": 5, "on": True, "long": "x" * 120}


def test_garbage_types_do_not_break_saving(store):
    clean = store.save_config({"layouts": 5})
    assert isinstance(clean["layouts"], dict) and clean["layouts"]["mode"] == "classic"
    clean = store.save_config({"layouts": {"items": "nonsense", "mode": [], "active": 7}})
    assert clean["layouts"]["items"] == {} and clean["layouts"]["mode"] == "classic"
    clean = store.save_config({"layouts": {"items": [{"id": "ly1", "tabs": "nonsense"}]}})
    assert list(clean["layouts"]["items"]) == ["ly1"], "a bundle round-tripped as a list is accepted"


# ── the endpoints ──────────────────────────────────────────────────────────────────────────────

def test_get_returns_the_stored_state(store):
    store.save_config({"layouts": {"items": {"lymain": _layout()}}})
    out = asyncio.run(api.layouts_get())
    assert out["ok"] is True and out["count"] == 1
    assert out["items"]["lymain"]["name"] == "My terminal"
    assert out["mode"] == "classic" and out["active"] == ""


def test_one_post_can_switch_mode_save_and_activate(store):
    out = asyncio.run(api.layouts_post({"mode": "terminal", "save": _layout(), "activate": "lymain"}))
    assert out["ok"] is True and out["actions"] == ["mode", "save", "activate"]
    assert out["mode"] == "terminal" and out["active"] == "lymain" and out["count"] == 1

    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["layouts"]["mode"] == "terminal"
    assert on_disk["layouts"]["items"]["lymain"]["tabs"][0]["widgets"][0]["view"] == "ofx"


def test_a_refused_layout_is_reported_not_silently_dropped(store):
    out = asyncio.run(api.layouts_post({"save": {"id": "NOT A SLUG", "name": "bad"}}))
    assert out["ok"] is False
    assert "slug" in out["error"]
    assert out["count"] == 0


def test_a_save_without_an_id_gets_one(store):
    out = asyncio.run(api.layouts_post({"save": {"name": "Fresh", "tabs": [{"widgets": [{"view": "ofx"}]}]}}))
    assert out["ok"] is True and out["count"] == 1
    new_id = next(iter(out["items"]))
    assert config_store.LAYOUT_ID_RE.match(new_id)
    assert out["items"][new_id]["name"] == "Fresh"


def test_export_returns_a_bundle_and_writes_nothing(store):
    store.save_config({"layouts": {"items": {"lymain": _layout()}}})
    out = asyncio.run(api.layouts_post({"export": "lymain"}))
    assert out["ok"] is True and out["filename"] == "layout-My_terminal.json"
    bundle = json.loads(out["text"])
    assert bundle["layout"]["id"] == "lymain"
    assert asyncio.run(api.layouts_get())["count"] == 1, "an export is not a write"

    missing = asyncio.run(api.layouts_post({"export": "ly-nope"}))
    assert missing["ok"] is False and "no layout" in missing["error"]


def test_import_always_lands_under_a_new_id_and_a_free_name(store):
    bundle = {"layout": _layout()}
    first = asyncio.run(api.layouts_post({"import": bundle}))
    second = asyncio.run(api.layouts_post({"import": bundle}))
    assert first["ok"] and second["ok"]
    names = sorted(v["name"] for v in second["items"].values())
    assert names == ["My terminal", "My terminal 2"]
    assert len(set(second["items"])) == 2, "an import never overwrites an existing layout"


def test_duplicate_rename_and_delete(store):
    store.save_config({"layouts": {"items": {"lymain": _layout()}, "active": "lymain"}})
    dup = asyncio.run(api.layouts_post({"duplicate": "lymain"}))
    assert dup["count"] == 2
    copy_id = [k for k in dup["items"] if k != "lymain"][0]
    assert dup["items"][copy_id]["name"] == "My terminal copy"
    assert dup["items"][copy_id]["tabs"] == dup["items"]["lymain"]["tabs"], "a copy is a copy"

    renamed = asyncio.run(api.layouts_post({"rename": copy_id, "to": "Evening"}))
    assert renamed["items"][copy_id]["name"] == "Evening"

    gone = asyncio.run(api.layouts_post({"delete": copy_id}))
    assert list(gone["items"]) == ["lymain"]

    cleared = asyncio.run(api.layouts_post({"delete": "lymain"}))
    assert cleared["count"] == 0 and cleared["active"] == "", "deleting the active layout clears it"


def test_activating_something_that_does_not_exist_is_refused(store):
    out = asyncio.run(api.layouts_post({"activate": "ly-nope"}))
    assert out["ok"] is True
    assert out["active"] == ""
    assert "no layout" in out["error"]
