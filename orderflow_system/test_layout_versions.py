"""Layout versions (T2) — a save-overwrite and a delete are recoverable, and the ring is capped.

The store keeps, per layout, what it was before the last writes (newest first, ten deep). A
version of a deleted layout survives on purpose: restoring it is what makes a delete recoverable.
The route is driven as a function against a temp store, the same way test_aux_windows drives the
window endpoints.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orderflow_system.desktop import api, config_store


def _entry(name):
    return {"id": "lytest01", "name": name, "mode": "terminal",
            "tabs": [{"id": "main", "name": "Main", "widgets": [
                {"view": "chart", "x": 0, "y": 0, "w": 6, "h": 4}]}]}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def _post(payload):
    return asyncio.run(api.layouts_post(payload))


def test_the_defaults_carry_the_versions_ring(store):
    assert "versions" in store.default_config()["layouts"]


def test_auto_cull_is_on_by_default_and_reads_from_the_ui_block(store):
    assert store.default_config()["ui"]["layout_versions_autocull"] is True
    assert store.layout_versions_autocull({}) is True
    assert store.layout_versions_autocull({"ui": {}}) is True
    assert store.layout_versions_autocull({"ui": {"layout_versions_autocull": False}}) is False


def test_the_first_save_has_no_previous_version(store):
    r = _post({"save": _entry("First")})
    assert r["ok"] and r["count"] == 1
    assert not (r["versions"] or {}).get("lytest01")


def test_a_save_overwrite_keeps_the_previous_version(store):
    _post({"save": _entry("First")})
    r = _post({"save": _entry("Second")})
    ring = r["versions"]["lytest01"]
    assert len(ring) == 1 and ring[0]["name"] == "First"
    assert r["items"]["lytest01"]["name"] == "Second"


def test_a_delete_is_recoverable_through_the_ring(store):
    _post({"save": _entry("First")})
    _post({"save": _entry("Second")})
    d = _post({"delete": "lytest01"})
    assert d["ok"] and "lytest01" not in d["items"]
    assert d["versions"]["lytest01"][0]["name"] == "Second"
    ring = d["versions"]["lytest01"]
    r = _post({"restore_version": {"id": "lytest01", "at": ring[0]["at"]}})
    assert r["ok"] and "restore_version" in r["actions"]
    assert r["items"]["lytest01"]["name"] == "Second"


def test_a_restore_of_nothing_is_refused_with_its_reason(store):
    _post({"save": _entry("First")})
    r = _post({"restore_version": {"id": "lytest01", "at": 123456789}})
    assert "restore_version" not in r["actions"]
    assert "no version" in (r["error"] or "")


def test_the_ring_is_capped_and_newest_first(store):
    """Default (auto-cull ON): the five most recent are kept, newest first (§129)."""
    _post({"save": _entry("v0")})
    for i in range(1, 14):
        _post({"save": _entry("v%d" % i)})
    ring = _post({})["versions"]["lytest01"]
    assert len(ring) == config_store.LAYOUT_VERSIONS_KEEP
    assert ring[0]["name"] == "v12" and ring[-1]["name"] == "v8"


def test_with_auto_cull_off_the_ring_keeps_the_hard_ceiling(store):
    _post({"autocull": False})
    _post({"save": _entry("v0")})
    for i in range(1, 14):
        _post({"save": _entry("v%d" % i)})
    ring = _post({})["versions"]["lytest01"]
    assert len(ring) == config_store.LAYOUT_VERSIONS_MAX
    assert ring[0]["name"] == "v12" and ring[-1]["name"] == "v3"


def test_turning_auto_cull_back_on_culls_what_is_already_stored(store):
    """The depth the user picks applies to what is stored, not only to the next save."""
    _post({"autocull": False})
    _post({"save": _entry("v0")})                 # the first save has nothing to keep
    for i in range(1, 11):                        # ten more saves → ten versions
        _post({"save": _entry("v%d" % i)})
    before = _post({})["versions"]["lytest01"]
    assert len(before) == config_store.LAYOUT_VERSIONS_MAX
    out = _post({"autocull": True})
    assert out["actions"] == ["autocull"] and out["culled"] == config_store.LAYOUT_VERSIONS_MAX - config_store.LAYOUT_VERSIONS_KEEP
    ring = out["versions"]["lytest01"]
    assert len(ring) == config_store.LAYOUT_VERSIONS_KEEP and ring[0]["name"] == "v9"
    assert ring[-1]["name"] == "v5", "the five NEWEST of the ten are the ones kept"
    assert _post({"autocull": False})["culled"] == 0        # nothing to cull when it is switched off


def test_the_state_reports_the_switch_and_what_each_version_holds(store):
    _post({"save": _entry("First")})
    _post({"save": _entry("Second")})
    state = _post({})
    assert state["autocull"] is True
    assert state["keep"] == config_store.LAYOUT_VERSIONS_KEEP
    assert state["max"] == config_store.LAYOUT_VERSIONS_MAX
    row = state["versions"]["lytest01"][0]
    assert row["name"] == "First" and row["widgets"] == 1 and row["tabs"] == 1


def test_a_restore_is_recorded_so_it_can_be_stepped_forward_again(store):
    """The state a restore replaces must be recoverable — otherwise the arrangement you were just
    looking at is the one state with no way back."""
    _post({"save": _entry("First")})
    _post({"save": _entry("Second")})
    ring = _post({})["versions"]["lytest01"]
    out = _post({"restore_version": {"id": "lytest01", "at": ring[0]["at"]}})
    assert out["items"]["lytest01"]["name"] == "First"
    ring = out["versions"]["lytest01"]
    assert ring[0]["name"] == "Second", "the replaced state was not kept"
    back = _post({"restore_version": {"id": "lytest01", "at": ring[0]["at"]}})
    assert back["items"]["lytest01"]["name"] == "Second"


def test_versions_survive_a_round_trip_and_junk_is_clamped(store):
    clean = store.save_config({"layouts": {"versions": {"lytest01": [
        {"at": "junk", "name": "x" * 99, "entry": _entry("Kept")},
        "not a row",
        {"at": 5, "entry": None},
    ]}}})
    ring = clean["layouts"]["versions"]["lytest01"]
    assert len(ring) == 1
    assert ring[0]["at"] == 0 and len(ring[0]["name"]) == 40
    assert ring[0]["entry"]["name"] == "Kept"


def test_every_write_answer_reports_the_flag_it_just_stored(store):
    """Found by the §129b rebuild probe against the FROZEN exe: the route's returns used the
    parameter DEFAULT for `autocull`, so turning the switch OFF answered `autocull: True` while the
    store held False — a state the app never accepted, reported as if it had (`/api/control/layouts`
    POST, {autocull: false} → response autocull True, config on disk False). The helper has no
    default now and every answer — write, refusal, export — carries the stored flag."""
    off = _post({"autocull": False})
    assert off["actions"] == ["autocull"] and off["autocull"] is False
    assert store.load_config()["ui"]["layout_versions_autocull"] is False
    assert _post({"autocull": True})["autocull"] is True

    _post({"autocull": False})
    _post({"save": _entry("Present")})
    soft = _post({"restore_version": {"id": "lymissing", "at": 0}})
    assert "no version" in (soft["error"] or "") and soft["autocull"] is False, "a refusal must not lie either"
    hard = _post({"save": {"id": "BAD ID", "name": "x"}})
    assert hard["ok"] is False and hard["autocull"] is False
    bundle = _post({"export": "lytest01"})
    assert bundle["ok"] is True and bundle["autocull"] is False

    src = (Path(api.__file__).parent / "api.py").read_text(encoding="utf-8")
    assert "def _layouts_state(block: dict[str, Any], autocull: bool) -> dict[str, Any]:" in src, \
        "the flag gained a default again — a write could answer with a state the store refused"
    assert "**_layouts_state(block)}" not in src and "**_layouts_state(block_out)}" not in src, \
        "a call site dropped the flag"
