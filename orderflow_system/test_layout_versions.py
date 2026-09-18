"""Layout versions (T2) — a save-overwrite and a delete are recoverable, and the ring is capped.

The store keeps, per layout, what it was before the last writes (newest first, ten deep). A
version of a deleted layout survives on purpose: restoring it is what makes a delete recoverable.
The route is driven as a function against a temp store, the same way test_aux_windows drives the
window endpoints.
"""

from __future__ import annotations

import asyncio

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
    _post({"save": _entry("v0")})
    for i in range(1, 14):
        _post({"save": _entry("v%d" % i)})
    ring = _post({})["versions"]["lytest01"]
    assert len(ring) == config_store.LAYOUT_VERSIONS_MAX
    assert ring[0]["name"] == "v12" and ring[-1]["name"] == "v3"


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
