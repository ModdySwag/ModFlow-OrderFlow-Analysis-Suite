"""T5 — canvas craft: A11 auto-fit hysteresis, A12 the nudge kit, A20 the values divider,
A10 minimal mode + card collapse. Text pins on the wiring, behavioural pins on the store, and the
pure fit verdict lives in `ofx.selftest.js` where the rest of its arithmetic is pinned."""

from __future__ import annotations

from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).parent / "desktop" / "ui"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


# ── A11: the auto-fit hysteresis ───────────────────────────────────

def test_the_config_readers_use_the_page_binding_not_window_S():
    # `S` is ui.js's top-level `let` — it is NOT a window property, so a `window.S &&` guard
    # reads undefined and silently pins the fallback (learned live, 2026-09-18).
    for name in ("ofx.js", "atlas.js", "heatmap-pro.js"):
        code = _text(UI / name)
        assert "window.S &&" not in code, name + " guards on window.S — the default will win"


def test_the_fit_verdict_is_pure_gated_and_registered():
    ofx = _text(UI / "ofx.js")
    assert "fitDecision(view, band, factor)" in ofx, "the pure verdict is gone"
    assert "fitDecision" in _text(UI / "ofx.selftest.js"), "the verdict lost its selftest"
    assert "if (!force && tol > 0 && state.view.scaleY > 0" in ofx, "the gate left fitHeight"
    assert "fitTolerance" in ofx and "nudge," in ofx
    registry = _text(Path(__file__).parent / "desktop" / "param_registry.py")
    assert "atlas.ofx.fit_tolerance" in registry


def test_the_renderer_knobs_default_and_clamp(store):
    cfg = store.default_config()
    assert cfg["atlas"]["ofx"]["fit_tolerance"] == 0.25
    assert cfg["atlas"]["heatmap"]["values_min_px"] == 0
    assert cfg["ui"]["heatmap_minimal"] is False
    clean = store.save_config({"atlas": {"ofx": {"fit_tolerance": "junk"},
                                         "heatmap": {"values_min_px": 999}}})
    assert clean["atlas"]["ofx"]["fit_tolerance"] == 0.25
    assert clean["atlas"]["heatmap"]["values_min_px"] == 200
    clean = store.save_config({"ui": {"heatmap_minimal": "yes"}})
    assert clean["ui"]["heatmap_minimal"] is False, "only the boolean True counts"


# ── A12: the nudge kit ───────────────────────────────────────────────

def test_the_nudge_keys_are_registered_for_both_axes():
    view = _text(UI / "ofx-view.js")
    for chord in ("arrowleft", "shift+arrowleft", "arrowright", "shift+arrowright",
                  "arrowup", "shift+arrowup", "arrowdown", "shift+arrowdown"):
        assert "['" + chord + "'" in view, "the Engine lost the " + chord + " nudge"
    assert "engine-nudge-" in view and "OFX.nudge(" in view
    heat = _text(UI / "heatmap-pro.js")
    # §121: the arrows PAN (industry grammar — the wheel and the +/- pair own zoom); the shift
    # pair jumps ten buckets, Home returns to the live edge.
    for ident in ("heatmap-rows-more", "heatmap-rows-fewer",
                  "heatmap-zoom-in", "heatmap-zoom-out",
                  "heatmap-pan-back", "heatmap-pan-back-10",
                  "heatmap-pan-fwd", "heatmap-pan-fwd-10", "heatmap-live"):
        assert ident in heat, "the Heatmap lost " + ident


# ── A20: the values divider ───────────────────────────────────────

def test_the_values_divider_is_wired():
    atlas = _text(UI / "atlas.js")
    assert "values_min_px" in atlas and "fillText(compact(v)" in atlas
    assert "'values_min_px', 'Heatmap cell values from" in atlas, "the settings row is gone"
    registry = _text(Path(__file__).parent / "desktop" / "param_registry.py")
    assert "atlas.heatmap.values_min_px" in registry


# ── A10: minimal mode + the collapsed card ────────────────────────────

def test_minimal_mode_persists_and_the_card_collapses():
    heat = _text(UI / "heatmap-pro.js")
    assert 'data-hm-pro="minimal"' in heat and "function setMinimal" in heat
    assert "ui.heatmap_minimal" in heat, "the minimal choice no longer persists"
    registry = _text(Path(__file__).parent / "desktop" / "param_registry.py")
    assert 'P("ui.heatmap_minimal"' in registry, \
        "without a registry entry /params refuses the write and the choice silently stops persisting"
    css = _text(UI / "modules.css")
    assert ".hm-minimal" in css and ".card-collapsed" in css
    chrome = _text(UI / "chrome.js")
    assert "card-collapsed" in chrome, "the collapse delegator is gone"

