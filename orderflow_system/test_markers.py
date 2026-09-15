"""Pinned levels (markers) — the heatmap's markers memory (P1-3).

Pinned here: the defaults ship the markers block, a marker round-trips through the sanitiser in data
space, junk prices are dropped rather than stored, the note is bounded, the per-symbol cap holds, and
the endpoints answer with the state the store *accepted*.
"""

from __future__ import annotations

import asyncio

import pytest

from orderflow_system.desktop import api, config_store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def _mark(price=76500.0, bucket=1789488000, size=1.5, note=""):
    return {"price": price, "bucket": bucket, "size": size, "note": note}


# ── the store ──────────────────────────────────────────────────────────────────────────────────

def test_defaults_carry_the_markers_block(store):
    cfg = store.load_config()
    assert isinstance(cfg.get("markers"), dict), "the defaults ship the markers block"


def test_a_marker_round_trips_in_data_space(store):
    stored = store.save_config({"markers": {"btcusdt": {"markers": [_mark(note="the wall")]}}})
    rows = stored["markers"]["BTCUSDT"]["markers"]
    assert len(rows) == 1
    assert rows[0]["price"] == 76500.0 and rows[0]["note"] == "the wall"
    assert rows[0]["bucket"] == 1789488000
    assert "x" not in rows[0] and "y" not in rows[0], "pixels are never stored"


def test_a_junk_price_is_dropped_not_stored(store):
    stored = store.save_config({"markers": {"BTCUSDT": {"markers": [
        _mark(price="not a number"), _mark(price=-5), _mark(price=0), _mark(price=76000.0, note="kept"),
    ]}}})
    rows = stored["markers"]["BTCUSDT"]["markers"]
    assert len(rows) == 1 and rows[0]["note"] == "kept"


def test_the_note_is_bounded(store):
    stored = store.save_config({"markers": {"BTCUSDT": {"markers": [_mark(note="z" * 400)]}}})
    assert len(stored["markers"]["BTCUSDT"]["markers"][0]["note"]) == 120


def test_the_per_symbol_cap_holds(store):
    stored = store.save_config({"markers": {"BTCUSDT": {"markers": [_mark(price=70000.0 + i) for i in range(620)]}}})
    assert len(stored["markers"]["BTCUSDT"]["markers"]) == 500


def test_an_empty_list_leaves_no_slot(store):
    stored = store.save_config({"markers": {"BTCUSDT": {"markers": []}}})
    assert "BTCUSDT" not in stored["markers"], "an empty list is not a stored symbol"


# ── the endpoints ──────────────────────────────────────────────────────────────────────────────

def test_the_routes_answer_with_what_the_store_accepted(store):
    out = asyncio.run(api.markers_post({"symbol": "btcusdt", "markers": [_mark(note="zone")]}))
    assert out["ok"] and out["key"] == "BTCUSDT"
    assert len(out["block"]["markers"]) == 1 and out["block"]["markers"][0]["note"] == "zone"
    back = asyncio.run(api.markers_get(symbol="BTCUSDT"))
    assert back["block"]["markers"][0]["price"] == 76500.0
    other = asyncio.run(api.markers_get(symbol="ETHUSDT"))
    assert other["block"]["markers"] == [], "another symbol does not inherit them"


def test_a_junk_post_stores_nothing_and_says_so(store):
    out = asyncio.run(api.markers_post({"symbol": "BTCUSDT", "markers": [{"price": "nope"}]}))
    assert out["block"]["markers"] == [], "the route reports the sanitised result, not the request"
