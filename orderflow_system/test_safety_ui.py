"""The safety trio (T3) — armed order keys, the registry legend, and the paper lock.

Behaviour that can be pure is pinned in keys.selftest.js (the armed gate: a danger row cannot
dispatch while disarmed). This file defends the wiring: the module markers exist, the markup
carries the controls, the paper bindings are danger-gated, and ui.paper_lock survives the store.
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


def test_the_armed_gate_exists_in_the_registry():
    code = _text(UI / "keys.js")
    assert "danger: Boolean(spec.danger)" in code
    assert "b.danger && !armed" in code, "the gate is not enforced in resolve()"
    assert "setArmed" in code and "armed: function" in code


def test_the_status_bar_carries_the_armed_badge():
    assert 'id="keysArmed"' in _text(UI / "index.html")


def test_the_paper_order_keys_are_danger_gated_and_view_scoped():
    code = _text(UI / "paper.js")
    for chord in ("alt+b", "alt+s", "alt+x"):
        assert "keys: ['" + chord + "']" in code, "the paper keys lost " + chord
    assert code.count("danger: true") >= 3
    assert "onScreen() && runningNow && !locked" in code, "the gate ignores view, session or lock"


def test_the_ticket_carries_the_danger_row_and_lock():
    html = _text(UI / "index.html")
    assert 'id="ppLock"' in html and "danger-row" in html
    assert "Lock trading" in html


def test_the_menu_arms_the_keys_and_renders_from_the_registry():
    code = _text(UI / "menubar.js")
    assert "Arm the order keys" in code and "Disarm the order keys" in code
    assert "Copy the shortcut list" in code
    assert "keyId: 'engine-start'" in code, "the engine rows still hand-type their accelerators"
    assert "accelOf(item.keyId)" in code, "the legend does not render from the registry"


def test_the_paper_lock_survives_the_store(store):
    assert store.default_config()["ui"]["paper_lock"] is False
    clean = store.save_config({"ui": {"paper_lock": True}})
    assert clean["ui"]["paper_lock"] is True
    assert store.load_config()["ui"]["paper_lock"] is True
