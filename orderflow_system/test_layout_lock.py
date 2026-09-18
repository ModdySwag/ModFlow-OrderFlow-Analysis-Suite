"""Layout lock (T2) — the arrangement holds still until it is unlocked, and the lock persists.

The store half is behavioural (ui.layout_lock survives a round trip and coerces). The shell half
is source-level on purpose: the gates sit inside functions that need a live DOM, and the property
this pin defends is that every way the arrangement can change is gated (move, resize, add, remove,
tab reorder) — a lock that misses one door is a lock that lies.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).parent / "desktop" / "ui"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_the_lock_ships_off_and_survives_a_round_trip(store):
    assert store.default_config()["ui"]["layout_lock"] is False
    clean = store.save_config({"ui": {"layout_lock": True}})
    assert clean["ui"]["layout_lock"] is True
    assert store.load_config()["ui"]["layout_lock"] is True


def test_the_lock_coerces_a_non_boolean(store):
    clean = store.save_config({"ui": {"layout_lock": "yes"}})
    assert clean["ui"]["layout_lock"] is True
    clean = store.save_config({"ui": {"layout_lock": 0}})
    assert clean["ui"]["layout_lock"] is False


def test_the_shell_gates_every_door_into_the_arrangement():
    code = _text(UI / "shell.js")
    assert "function setLocked" in code and "function refuseLocked" in code
    assert code.count("refuseLocked()") >= 5, "a door into the arrangement is not gated"
    assert "layout_lock" in code, "the lock is never persisted or adopted"


def test_the_menu_offers_the_lock_and_the_status_bar_shows_it():
    assert "Lock the layout" in _text(UI / "menubar.js")
    assert 'id="statusLock"' in _text(UI / "index.html")
