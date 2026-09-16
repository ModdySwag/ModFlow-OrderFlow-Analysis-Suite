"""Display geometry (§72) — the window's memory, the canvas law, the per-screen layout.

Pinned here, because this is what "supports every monitor/display scenario" means in code:

  * the remembered window geometry survives a store round-trip and cannot be stored as nonsense
  * pick_window_geometry() chooses a screen that still exists and clamps to it — an unplugged
    monitor must never place the window off-desktop, and a small display gets a small-but-usable
    window (the old fixed 1500×940 with a 1080×680 minimum could not fit a 1024×640 work area
    or a 1366×768 display at 150% at all)
  * the canvas law: a canvas has a CSS box and its backing store is box × devicePixelRatio, with
    dpr = 1 as the identity (the sizes the app has always painted at — the regression pin), and
    a canvas must never size itself from its own backing store
  * per-screen layouts: one key per screen (two identical monitors are two screens), and the
    most recently saved layout for a screen is the one boot adopts

The behavioural half of the JS rules lives in the modules' own selftests (ofx.selftest.js,
shell.selftest.js); these are the source-level contracts that hold the two halves together.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store, launcher

UI = Path(__file__).resolve().parent / "desktop" / "ui"

PRIMARY = {"x": 0, "y": 0, "width": 2560, "height": 1440}
SECOND = {"x": 2560, "y": 0, "width": 2560, "height": 1440}
SMALL = {"x": 0, "y": 0, "width": 1024, "height": 640}
#: 1366×768 at 150%: what the desktop actually reports as the work area.
NARROW = {"x": 0, "y": 0, "width": 911, "height": 512}


def source(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


class _Screen:
    """The two attributes pywebview's Screen exposes that decide anything here."""

    def __init__(self, rect: dict):
        self.__dict__.update(rect)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


# ── the remembered window geometry ───────────────────────────────────────────────────────────────

def test_defaults_carry_the_window_block(store):
    cfg = store.default_config()
    assert cfg["ui"]["window"] == {"width": 1500, "height": 940, "x": None, "y": None, "maximised": False}


def test_window_geometry_round_trips(store):
    clean = store.save_config({"ui": {"window": {"width": 1200, "height": 800, "x": 2560, "y": 120,
                                               "maximised": True}}})
    assert clean["ui"]["window"] == {"width": 1200, "height": 800, "x": 2560, "y": 120, "maximised": True}
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["ui"]["window"] == clean["ui"]["window"]


@pytest.mark.parametrize("bad", ["wide", None, [], {"nested": 1}, 1e30])
def test_a_bad_window_value_is_clamped_not_trusted(store, bad):
    clean = store.save_config({"ui": {"window": {"width": bad, "height": -4, "x": bad, "y": "top"}}})
    win = clean["ui"]["window"]
    assert 640 <= win["width"] <= 10_000
    assert 420 <= win["height"] <= 6_000
    assert win["x"] is None and win["y"] is None
    assert win["maximised"] is False


def test_a_position_off_every_desktop_is_dropped(store):
    clean = store.save_config({"ui": {"window": {"x": 999_999, "y": -999_999}}})
    assert clean["ui"]["window"]["x"] is None
    assert clean["ui"]["window"]["y"] is None


def test_a_monitor_left_of_the_primary_keeps_its_negative_origin(store):
    clean = store.save_config({"ui": {"window": {"x": -1920, "y": -200}}})
    assert clean["ui"]["window"]["x"] == -1920
    assert clean["ui"]["window"]["y"] == -200


# ── picking the geometry to open with ────────────────────────────────────────────────────────────

def test_first_run_centres_on_the_primary_screen():
    geo = launcher.pick_window_geometry({"width": 1500, "height": 940, "x": None, "y": None},
                                        [_Screen(PRIMARY)])
    assert (geo["width"], geo["height"]) == (1500, 940)
    assert geo["x"] == (PRIMARY["width"] - 1500) // 2
    assert geo["y"] == (PRIMARY["height"] - launcher.WINDOW_CHROME_H - 940) // 2


def test_a_stored_position_on_a_still_present_monitor_is_kept_exactly():
    geo = launcher.pick_window_geometry({"width": 1200, "height": 800, "x": 2600, "y": 40},
                                        [_Screen(PRIMARY), _Screen(SECOND)])
    assert (geo["x"], geo["y"], geo["width"], geo["height"]) == (2600, 40, 1200, 800)


def test_an_unplugged_monitor_falls_back_to_the_primary():
    # the stored origin was on the second screen; only the primary exists now
    geo = launcher.pick_window_geometry({"width": 1200, "height": 800, "x": 2600, "y": 40},
                                        [_Screen(PRIMARY)])
    assert 0 <= geo["x"] <= PRIMARY["width"] - geo["width"]
    assert 0 <= geo["y"] <= PRIMARY["height"] - launcher.WINDOW_CHROME_H - geo["height"]


def test_a_position_hanging_off_the_right_edge_is_pulled_back():
    geo = launcher.pick_window_geometry({"width": 1500, "height": 940, "x": 2500, "y": 600},
                                        [_Screen(PRIMARY)])
    assert geo["x"] + geo["width"] <= PRIMARY["width"]
    assert geo["y"] + geo["height"] <= PRIMARY["height"] - launcher.WINDOW_CHROME_H


def test_a_small_display_gets_a_window_it_can_hold():
    geo = launcher.pick_window_geometry({"width": 1500, "height": 940, "x": None, "y": None},
                                        [_Screen(SMALL)])
    assert geo["width"] <= SMALL["width"]
    assert geo["height"] <= SMALL["height"] - launcher.WINDOW_CHROME_H
    assert geo["min_width"] <= geo["width"] and geo["min_height"] <= geo["height"]


def test_a_display_at_150_percent_is_usable():
    # the pre-§72 minimum was 1080×680 — wider and taller than this entire work area
    geo = launcher.pick_window_geometry(None, [_Screen(NARROW)])
    assert geo["width"] <= NARROW["width"]
    assert geo["height"] <= NARROW["height"] - launcher.WINDOW_CHROME_H
    assert geo["min_width"] <= NARROW["width"]
    assert geo["min_height"] <= NARROW["height"] - launcher.WINDOW_CHROME_H


def test_without_screens_the_pre_72_geometry_is_unchanged():
    geo = launcher.pick_window_geometry(None, [])
    assert (geo["width"], geo["height"]) == (1500, 940)
    assert (geo["min_width"], geo["min_height"]) == (1080, 680)
    assert geo["x"] is None and geo["y"] is None


def test_a_junk_screen_object_is_ignored():
    geo = launcher.pick_window_geometry(None, [object(), {"x": 1}, _Screen(PRIMARY)])
    assert geo["width"] == 1500
    assert geo["x"] == (PRIMARY["width"] - 1500) // 2


def test_a_zero_sized_screen_is_not_a_screen():
    assert launcher.screen_rects([_Screen({"x": 0, "y": 0, "width": 0, "height": 0})]) == []


def test_maximised_survives_the_choice():
    geo = launcher.pick_window_geometry({"maximised": True}, [_Screen(PRIMARY)])
    assert geo["maximised"] is True


def test_the_geometry_is_what_create_window_is_given():
    src = (Path(__file__).resolve().parent / "desktop" / "launcher.py").read_text(encoding="utf-8")
    assert "width=geo[\"width\"]" in src and "height=geo[\"height\"]" in src
    assert "x=geo[\"x\"]" in src and "y=geo[\"y\"]" in src
    assert "min_size=(geo[\"min_width\"], geo[\"min_height\"])" in src
    assert "maximized=geo[\"maximised\"]" in src
    assert "remember_window(window, window_cfg)" in src
    assert "min_size=(1080, 680)" not in src            # the fixed minimum is gone


# ── the canvas law (dpr) ─────────────────────────────────────────────────────────────────────────

def test_the_engine_backs_every_layer_at_the_display_scale():
    src = source("ofx.js")
    assert "layerSize(cssW, cssH, dpr) {" in src
    assert "state.view.dpr = dpr;" in src
    assert "function resetLayer(ctx, canvas, dpr) {" in src
    assert "c.width = width;" not in src                # the 1× sizing this replaces
    assert "r.width = width" not in src


def test_the_engine_clears_at_one_to_one_and_paints_in_css_pixels():
    src = source("ofx.js")
    assert "ctx.setTransform(1, 0, 0, 1, 0, 0);" in src
    assert "ctx.setTransform(dpr, 0, 0, dpr, 0, 0);" in src
    assert "const width = canvas.width / dpr;" in src   # the ribbon's logical size


def test_the_ribbon_box_is_the_stage_width():
    src = source("ofx.js")
    assert "r.style.width !== boxW + 'px'" in src


def test_market_pressure_has_a_css_box_and_repaints_on_relayout():
    src = source("market-pressure.js")
    assert "el.style.width = '100%'" in src
    assert "el.style.height = cssH + 'px'" in src       # without it a fit pass multiplies by dpr
    assert "PRESSURE.lastSeries = series;" in src       # the redraw's input
    assert "'ofap:relayout'" in src


def test_the_snapshot_spark_keeps_its_css_box():
    src = source("ofx-view.js")
    assert "paintSpark(el('ofxSpark'), 90, 20);" in src
    assert "paintSpark(el('ofxSpark2'), 88, 18);" in src
    assert "spark.style.width = cssW + 'px';" in src


def test_fit_view_covers_every_visible_canvas():
    src = source("scale.js")
    assert "const view = scope || document;" in src
    assert "querySelector('.view.active')" not in src    # the stale-scope default this replaces


def test_drawings_refit_on_relayout():
    src = source("drawings.js")
    assert "'ofap:relayout'" in src


# ── per-screen layouts ───────────────────────────────────────────────────────────────────────────

def test_the_screen_key_carries_the_screen_origin():
    src = source("shell.js")
    assert "screenKeyOf(scr, dpr) {" in src
    assert "screenKeyOf(window.screen, window.devicePixelRatio)" in src


def test_boot_adopts_this_screens_layout():
    src = source("shell.js")
    assert "pickScreenLayout(S.items, screenKey(), S.layoutId)" in src
    assert "this screen’s layout: “" in src


def test_the_layout_store_keeps_a_screen_key_of_the_same_shape():
    # the shell writes it, the store keeps it — one shape, or auto-apply can never match
    clean = config_store._clean_layout("ly1", {
        "id": "ly1", "name": "Desk", "mode": "terminal",
        "screen_key": "2560x1440@1@2560,0", "theme": "dark", "saved": 1, "tabs": [],
    })
    assert clean is not None
    assert clean["screen_key"] == "2560x1440@1@2560,0"
