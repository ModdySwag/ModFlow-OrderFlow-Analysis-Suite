"""Auxiliary windows (§73) — one widget per native window, placed on a monitor.

Pinned here, because this is the feature's whole contract:

  * the store ships `ui.windows` and clamps it (identified ids, view slugs, geometry inside its
    bounds, unique, capped) — a hand-edited file may never invent a window
  * placement is pure: an explicit monitor wins, a stored position wins *while a screen still
    contains it*, an unplugged monitor falls back to the primary, size clamps to the screen's work
    area, and a fresh window cascades so two opens do not stack
  * the endpoints answer with what actually happened: `native: false` where no host exists (a
    browser session offers no controls), a refusal with a reason at the cap, the resolved placement
    for a window that opened, and the stored shape (never the informational keys) in the set

The native half — pywebview really making the window — is exercised live (§73 receipts); here the
host is a fake, so these tests hold on any machine with no display at all.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orderflow_system.desktop import api, config_store, windows as windows_mod

PRIMARY = {"x": 0, "y": 0, "width": 2560, "height": 1440}
SECOND = {"x": 2560, "y": 0, "width": 2560, "height": 1440}
SMALL = {"x": 0, "y": 0, "width": 1024, "height": 640}


class FakeHost(windows_mod.WindowHost):
    """A window host with no windows: records what the API asked for."""

    kind = "fake"

    def __init__(self, screens=None):
        self._screens = [dict(s) for s in (screens if screens is not None else [PRIMARY, SECOND])]
        self.opened: dict[str, dict] = {}
        self.closed: list[str] = []
        self.focused: list[str] = []
        self.pinned: dict[str, bool] = {}
        self.moved: list[tuple] = []
        self.refuse_move = False

    def screens(self) -> list[dict]:
        return [dict(s) for s in self._screens]

    def open(self, record: dict) -> dict:
        assert record["id"] not in self.opened, "the API asked for a duplicate window"
        self.opened[record["id"]] = dict(record)
        return record

    def close(self, wid: str) -> bool:
        self.closed.append(wid)
        return self.opened.pop(wid, None) is not None

    def move(self, wid: str, x: int, y: int, width: int, height: int) -> bool:
        if self.refuse_move or wid not in self.opened:
            return False
        self.moved.append((wid, int(x), int(y), int(width), int(height)))
        self.opened[wid].update({"x": int(x), "y": int(y), "width": int(width), "height": int(height)})
        return True

    def geometry(self, wid: str):
        row = self.opened.get(wid)
        if row is None:
            return None
        return {"x": row["x"], "y": row["y"], "width": row["width"], "height": row["height"]}

    def focus(self, wid: str) -> bool:
        self.focused.append(wid)
        return wid in self.opened

    def set_on_top(self, wid: str, on_top: bool) -> bool:
        if wid not in self.opened:
            return False
        self.pinned[wid] = bool(on_top)
        return True

    def open_ids(self) -> list[str]:
        return list(self.opened)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


@pytest.fixture()
def host(store):
    """A fake native host, installed and removed around each test."""
    fake = FakeHost()
    windows_mod.set_host(fake)
    yield fake
    windows_mod.set_host(None)


# ── the store ───────────────────────────────────────────────────────────────────────────────────

def test_defaults_carry_an_empty_window_set(store):
    assert store.default_config()["ui"]["windows"] == []


def test_a_window_record_round_trips(store):
    clean = store.save_config({"ui": {"windows": [{
        "id": "w1a2b3c", "view": "ofx", "screen_key": "2560x1440@1", "x": 2600, "y": 40,
        "width": 1200, "height": 800, "on_top": True,
    }]}})
    assert clean["ui"]["windows"] == [{
        "id": "w1a2b3c", "view": "ofx", "screen_key": "2560x1440@1", "x": 2600, "y": 40,
        "width": 1200, "height": 800, "on_top": True,
    }]
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["ui"]["windows"][0]["view"] == "ofx"


@pytest.mark.parametrize("bad", [None, "ofx", 42, {"view": "ofx"}, {"id": "w1", "view": "NOT A VIEW"},
                                 {"id": "NOT A SLUG", "view": "ofx"}, {"id": "w1", "view": ""}])
def test_an_unidentifiable_record_is_not_stored(store, bad):
    clean = store.save_config({"ui": {"windows": [bad]}})
    assert clean["ui"]["windows"] == []


def test_the_record_is_clamped_not_trusted(store):
    clean = store.save_config({"ui": {"windows": [{
        "id": "w1", "view": "ofx", "screen_key": "x" * 80, "x": 999_999, "y": -999_999,
        "width": 99_999, "height": 1, "on_top": "yes please",
    }]}})
    row = clean["ui"]["windows"][0]
    assert row["screen_key"] == "x" * 24
    assert row["x"] is None and row["y"] is None            # off every desktop → the host chooses
    assert row["width"] == config_store.AUX_MAX_W
    assert row["height"] == config_store.AUX_MIN_H
    assert row["on_top"] is True


def test_the_set_is_unique_and_capped(store):
    rows = [{"id": "w%d" % i, "view": "ofx", "width": 800, "height": 600} for i in range(20)]
    rows.insert(1, dict(rows[0]))                            # a duplicate id
    clean = store.save_config({"ui": {"windows": rows}})
    assert len(clean["ui"]["windows"]) == config_store.WINDOWS_MAX
    assert [r["id"] for r in clean["ui"]["windows"]] == ["w%d" % i for i in range(config_store.WINDOWS_MAX)]


def test_a_monitor_left_of_the_primary_keeps_its_negative_origin(store):
    clean = store.save_config({"ui": {"windows": [{"id": "w1", "view": "tape", "x": -1900, "y": -300}]}})
    assert clean["ui"]["windows"][0]["x"] == -1900


# ── placement (pure) ────────────────────────────────────────────────────────────────────────────

def test_placement_follows_the_screen_you_pick():
    out = windows_mod.place_aux({"id": "w1", "view": "cvd", "width": 1200, "height": 800},
                                [PRIMARY, SECOND], screen_index=1)
    assert out["screen"] == 1
    assert SECOND["x"] <= out["x"] <= SECOND["x"] + SECOND["width"] - out["width"]
    assert out["screen_label"].startswith("Monitor 2")


def test_placement_keeps_a_stored_position_a_screen_still_contains():
    out = windows_mod.place_aux({"id": "w1", "view": "ofx", "x": 2600, "y": 40,
                                 "width": 1200, "height": 800}, [PRIMARY, SECOND])
    assert (out["x"], out["y"], out["screen"]) == (2600, 40, 1)


def test_placement_falls_back_to_the_primary_when_the_monitor_is_gone():
    out = windows_mod.place_aux({"id": "w1", "view": "ofx", "x": 2600, "y": 40,
                                 "width": 1200, "height": 800}, [PRIMARY])
    assert out["screen"] == 0
    assert 0 <= out["x"] <= PRIMARY["width"] - out["width"]
    assert 0 <= out["y"] <= PRIMARY["height"] - windows_mod.CHROME_H - out["height"]


def test_placement_clamps_to_the_work_area_of_a_small_display():
    out = windows_mod.place_aux({"id": "w1", "view": "ofx", "width": 1500, "height": 940}, [SMALL])
    assert out["width"] <= SMALL["width"]
    assert out["height"] <= SMALL["height"] - windows_mod.CHROME_H
    assert out["x"] >= 0 and out["y"] >= 0


def test_placement_pulls_a_window_hanging_off_the_edge_back_in():
    out = windows_mod.place_aux({"id": "w1", "view": "ofx", "x": 2500, "y": 1400,
                                 "width": 900, "height": 700}, [PRIMARY])
    assert out["x"] + out["width"] <= PRIMARY["width"]
    assert out["y"] + out["height"] <= PRIMARY["height"] - windows_mod.CHROME_H


def test_placement_cascades_successive_windows():
    base = windows_mod.place_aux({"id": "w1", "view": "ofx", "width": 800, "height": 600}, [PRIMARY], count=0)
    one = windows_mod.place_aux({"id": "w2", "view": "ofx", "width": 800, "height": 600}, [PRIMARY], count=1)
    two = windows_mod.place_aux({"id": "w3", "view": "ofx", "width": 800, "height": 600}, [PRIMARY], count=2)
    assert one["x"] == base["x"] + windows_mod.CASCADE_STEP
    assert two["y"] == base["y"] + 2 * windows_mod.CASCADE_STEP
    assert (base["x"], base["y"]) != (one["x"], one["y"])


def test_placement_without_screens_sizes_only():
    out = windows_mod.place_aux({"id": "w1", "view": "ofx", "width": 400, "height": 200}, [])
    assert out["screen"] == -1
    # the requested size survives, floored at the minimum a window may be
    assert (out["width"], out["height"]) == (400, config_store.AUX_MIN_H)
    assert out["x"] is None and out["y"] is None


def test_a_junk_screen_is_not_a_screen():
    assert windows_mod.valid_screens([object(), {"x": 1}, {"width": 0, "height": 0}, PRIMARY]) == [PRIMARY]


def test_screen_labels_name_the_monitor_and_its_scale():
    assert windows_mod.screen_label(PRIMARY, 0) == "Monitor 1 · 2560x1440"
    assert windows_mod.screen_label(SECOND, 1, 1.5) == "Monitor 2 · 2560x1440 · 150%"


# ── the endpoints ───────────────────────────────────────────────────────────────────────────────

def test_no_host_means_no_native_windows(store):
    windows_mod.set_host(None)
    out = asyncio.run(api.windows_get())
    assert out["native"] is False and out["screens"] == [] and out["windows"] == []
    refused = asyncio.run(api.windows_post({"action": "open", "view": "ofx"}))
    assert refused["ok"] is False and refused["native"] is False
    assert "desktop app" in refused["error"]


def test_a_host_reports_its_screens_labelled(host):
    out = asyncio.run(api.windows_get())
    assert out["native"] is True and out["host"] == "fake"
    assert [s["label"] for s in out["screens"]] == ["Monitor 1 · 2560x1440", "Monitor 2 · 2560x1440"]
    assert out["max"] == config_store.WINDOWS_MAX


def test_open_places_persists_and_returns_what_it_made(host, store):
    out = asyncio.run(api.windows_post({"action": "open", "view": "ofx", "screen": 1,
                                        "width": 1200, "height": 800}))
    assert out["ok"] is True
    wid = out["opened"]["id"]
    assert wid.startswith("w")                              # generated ids are window ids
    assert out["opened"]["view"] == "ofx"
    assert "screen" not in out["opened"] and "screen_label" not in out["opened"]   # the stored shape
    assert out["screen_label"].startswith("Monitor 2")
    assert SECOND["x"] <= out["opened"]["x"] <= SECOND["x"] + SECOND["width"] - 1200

    assert list(host.opened) == [wid]                       # the host really got it
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert [r["id"] for r in on_disk["ui"]["windows"]] == [wid]
    assert on_disk["ui"]["windows"][0]["screen_key"] == ""


def test_open_twice_with_the_same_id_focuses_instead_of_duplicating(host):
    first = asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wfixed"}))
    assert first["ok"] is True
    again = asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wfixed"}))
    assert again["ok"] is True
    assert list(host.opened) == ["wfixed"]
    assert host.focused == ["wfixed"]                       # the second ask focused the first


def test_open_without_a_view_is_refused(host):
    out = asyncio.run(api.windows_post({"action": "open"}))
    assert out["ok"] is False and "view" in out["error"]
    assert host.opened == {}


def test_the_cap_refuses_the_next_window(host, store):
    for i in range(config_store.WINDOWS_MAX):
        out = asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "w%d" % i}))
        assert out["ok"] is True
    over = asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wover"}))
    assert over["ok"] is False and "limit" in over["error"]
    assert len(over["windows"]) == config_store.WINDOWS_MAX


def test_ontop_flips_in_the_store_and_in_the_host(host, store):
    asyncio.run(api.windows_post({"action": "open", "view": "cvd", "id": "wpin"}))
    out = asyncio.run(api.windows_post({"action": "ontop", "id": "wpin", "on_top": True}))
    assert out["ok"] is True
    assert host.pinned["wpin"] is True
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["ui"]["windows"][0]["on_top"] is True
    off = asyncio.run(api.windows_post({"action": "ontop", "id": "wpin", "on_top": False}))
    assert off["ok"] is True and host.pinned["wpin"] is False


def test_close_removes_it_from_the_host_and_from_the_set(host, store):
    asyncio.run(api.windows_post({"action": "open", "view": "tape", "id": "wclose"}))
    out = asyncio.run(api.windows_post({"action": "close", "id": "wclose"}))
    assert out["ok"] is True and out["closed"] == "wclose"
    assert host.opened == {} and out["windows"] == []
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    assert on_disk["ui"]["windows"] == []


def test_close_of_an_unknown_window_is_a_refusal(host):
    out = asyncio.run(api.windows_post({"action": "close", "id": "wghost"}))
    assert out["ok"] is False and "no window" in out["error"]


def test_focus_reports_what_the_host_said(host):
    asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wf"}))
    assert asyncio.run(api.windows_post({"action": "focus", "id": "wf"}))["ok"] is True
    missing = asyncio.run(api.windows_post({"action": "focus", "id": "wnope"}))
    assert missing["ok"] is False and "focus" in missing["error"]


def test_close_all_closes_everything(host, store):
    for i in range(3):
        asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wc%d" % i}))
    out = asyncio.run(api.windows_post({"action": "close_all"}))
    assert out["ok"] is True and sorted(out["closed"]) == ["wc0", "wc1", "wc2"]
    assert host.opened == {} and out["windows"] == []


def test_an_unknown_action_is_a_refusal(host):
    out = asyncio.run(api.windows_post({"action": "detonate"}))
    assert out["ok"] is False and "unknown action" in out["error"]


# ── §94: the quit sweep — the ghost-frame fix ──────────────────────────────────────────

class _FakeWindow:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


def test_close_all_takes_every_aux_window_down_and_keeps_the_records(monkeypatch):
    """A widget window alive while the process exits = a ghost frame on the desktop."""
    from orderflow_system.desktop import launcher

    host = launcher.NativeWindowHost(1, "t")
    windows = {"a": _FakeWindow(), "b": _FakeWindow(), "c": _FakeWindow()}
    host._windows.update(windows)

    dropped = []
    monkeypatch.setattr(windows_mod, "drop_record", lambda wid: dropped.append(wid))

    closed = host.close_all()
    assert closed == 3
    assert all(w.destroyed for w in windows.values())
    assert host._windows == {}
    assert dropped == [], "quit-time destroys must NOT drop the store's records"


def test_the_launcher_sweeps_on_quit_both_ways():
    code = (Path(__file__).resolve().parent / "desktop" / "launcher.py").read_text(encoding="utf-8")
    assert "host = restore_windows(port, restore=not args.safe)" in code, "main() must hold the host"
    assert "host.close_all()" in code, "the main window's close must sweep the aux windows"
    assert "def close_all(self)" in code

def test_resetting_a_window_brings_it_home_and_keeps_it_in_the_set(store, host):
    """T2’s rescue: a window stored on a monitor that is gone comes back to the primary.

    The stored geometry is dropped (that is the point — it is stale), the window is re-placed on
    screen 0, and it stays in the restore set with the new placement written back.
    """
    store.save_config({"ui": {"windows": [{"id": "wback01", "view": "ofx",
        "screen_key": "2560x1440@1", "x": 2600, "y": 40, "width": 1200, "height": 800}]}})
    opened = asyncio.run(api.windows_post({"action": "open", "id": "wback01", "view": "ofx"}))
    assert opened["ok"] and "wback01" in opened["open"]
    res = asyncio.run(api.windows_post({"action": "reset", "id": "wback01"}))
    assert res["ok"] and res["action"] == "reset" and res["reset"] == "wback01"
    assert "wback01" in res["open"], "the reset window must come back open"
    assert "wback01" in host.closed, "an open window is closed before it is re-placed"
    placed = host.opened["wback01"]
    assert placed["x"] < SECOND["x"], "the window did not come home to the primary screen"
    assert any(r["id"] == "wback01" for r in res["windows"]), "the record left the set"


def test_resetting_an_unknown_window_is_refused_with_its_reason(store, host):
    res = asyncio.run(api.windows_post({"action": "reset", "id": "wnope"}))
    assert res["ok"] is False and "no window" in res["error"]


# ── §128: sending an open (or stored) window to a monitor, and the snap shapes ──────────────────

BIG = {"x": 0, "y": 0, "width": 2560, "height": 1440}
LEFT_OF_PRIMARY = {"x": -1920, "y": 0, "width": 1920, "height": 1080}
AREA = (BIG["width"], BIG["height"] - windows_mod.CHROME_H)


@pytest.mark.parametrize("preset", windows_mod.PRESETS)
def test_every_preset_fits_inside_the_work_area(preset):
    """A shape the menu offers must never be a rectangle that covers the taskbar or leaves the screen."""
    out = windows_mod.preset_rect(BIG, preset, want_w=1100, want_h=760)
    area = windows_mod.work_area(BIG)
    assert out["x"] >= BIG["x"] and out["y"] >= BIG["y"]
    assert out["x"] + out["width"] <= BIG["x"] + BIG["width"]
    assert out["y"] + out["height"] <= BIG["y"] + area["height"]
    assert out["width"] >= min(config_store.AUX_MIN_W, BIG["width"])
    assert out["height"] >= min(config_store.AUX_MIN_H, area["height"])


def test_the_half_shapes_tile_the_work_area_exactly():
    left = windows_mod.preset_rect(BIG, "left", want_w=1100, want_h=760)
    right = windows_mod.preset_rect(BIG, "right", want_w=1100, want_h=760)
    top = windows_mod.preset_rect(BIG, "top", want_w=1100, want_h=760)
    bottom = windows_mod.preset_rect(BIG, "bottom", want_w=1100, want_h=760)
    assert left["x"] + left["width"] == right["x"]
    assert left["width"] + right["width"] == BIG["width"]
    assert top["y"] + top["height"] == bottom["y"]
    assert top["height"] + bottom["height"] == AREA[1]


def test_fill_is_the_whole_work_area_and_centre_keeps_the_size():
    fill = windows_mod.preset_rect(BIG, "fill", want_w=1100, want_h=760)
    assert (fill["x"], fill["y"], fill["width"], fill["height"]) == (0, 0, BIG["width"], AREA[1])
    centre = windows_mod.preset_rect(BIG, "center", want_w=1100, want_h=760)
    assert (centre["width"], centre["height"]) == (1100, 760)
    assert centre["x"] == (BIG["width"] - 1100) // 2


def test_a_junk_preset_falls_back_to_centre_and_a_small_screen_still_answers():
    assert windows_mod.preset_rect(BIG, "diagonal") == windows_mod.preset_rect(BIG, "center")
    tiny = windows_mod.preset_rect(SMALL, "right", want_w=1500, want_h=940)
    assert tiny["x"] >= 0 and tiny["y"] >= 0
    assert tiny["x"] + tiny["width"] <= SMALL["width"]


def test_a_preset_on_a_monitor_left_of_the_primary_keeps_its_negative_origin():
    out = windows_mod.preset_rect(LEFT_OF_PRIMARY, "left", want_w=1100, want_h=760)
    assert out["x"] == -1920
    assert out["width"] == 1920 // 2


def test_screen_index_of_finds_the_screen_and_refuses_junk():
    screens = [PRIMARY, SECOND]
    assert windows_mod.screen_index_of(screens, 100, 100) == 0
    assert windows_mod.screen_index_of(screens, 2600, 40) == 1
    assert windows_mod.screen_index_of(screens, 9999, 40) is None
    assert windows_mod.screen_index_of(screens, None, 40) is None
    assert windows_mod.screen_index_of(screens, True, 40) is None


def test_move_placement_steps_to_the_next_monitor_cyclically():
    here = {"id": "w1", "view": "ofx", "x": 2600, "y": 40, "width": 1100, "height": 760}
    forward = windows_mod.move_placement(here, [PRIMARY, SECOND], step=1)
    back = windows_mod.move_placement(here, [PRIMARY, SECOND], step=-1)
    assert (forward["screen"], back["screen"]) == (0, 0)         # 1+1 → 0 ; 1-1 → 0
    three = [PRIMARY, SECOND, {"x": 5120, "y": 0, "width": 1920, "height": 1080}]
    assert windows_mod.move_placement(here, three, step=1)["screen"] == 2
    assert windows_mod.move_placement(here, three, step=2)["screen"] == 0


def test_move_placement_keeps_the_size_and_resolves_a_real_position():
    out = windows_mod.move_placement({"id": "w1", "view": "ofx", "x": 40, "y": 40,
                                      "width": 1100, "height": 760}, [PRIMARY, SECOND], screen_index=1)
    assert out["screen"] == 1 and out["screen_label"].startswith("Monitor 2")
    assert (out["width"], out["height"]) == (1100, 760)
    assert SECOND["x"] <= out["x"] <= SECOND["x"] + SECOND["width"] - 1100


def test_stranded_names_only_positions_off_every_screen():
    rows = [{"id": "wa", "x": 9000, "y": 40}, {"id": "wb", "x": 100, "y": 40},
            {"id": "wc", "x": None, "y": None}]
    assert windows_mod.stranded(rows, [PRIMARY, SECOND]) == ["wa"]
    assert windows_mod.stranded(rows, []) == []            # nothing to judge against: no claim
    assert windows_mod.stranded([{"id": "wa", "x": 2600, "y": 40}], [PRIMARY, SECOND]) == []


def test_stranded_sees_a_live_window_the_store_still_thinks_is_placed():
    """Measured live: a window pushed to (9000, 40) kept a record saying (100, 100) — the store
    lagged the window, and only the live rect knew the window needed rescuing."""
    rows = [{"id": "wa", "x": 100, "y": 100}]
    live = {"wa": {"x": 9000, "y": 40, "width": 900, "height": 700, "screen": -1}}
    assert windows_mod.stranded(rows, [PRIMARY, SECOND], live=live) == ["wa"]
    assert windows_mod.stranded(rows, [PRIMARY, SECOND]) == [], "without the live rect there is no claim"
    both = windows_mod.stranded(rows + [{"id": "wb", "x": 9000, "y": 40}], [PRIMARY, SECOND], live=live)
    assert both == ["wb", "wa"], "store-side ids first, then live ones, each named once"


def test_move_sends_an_open_window_to_the_other_monitor(store, host):
    asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wgo", "screen": 0}))
    out = asyncio.run(api.windows_post({"action": "move", "id": "wgo", "screen": 1}))
    assert out["ok"] is True and out["action"] == "move" and out["moved"] == "wgo"
    assert out["screen_label"].startswith("Monitor 2")
    assert host.moved[0][0] == "wgo"
    assert host.opened["wgo"]["x"] >= SECOND["x"], "the real window did not move"
    on_disk = json.loads(store.config_path().read_text(encoding="utf-8"))
    stored = on_disk["ui"]["windows"][0]
    assert stored["x"] >= SECOND["x"] and "screen" not in stored and "screen_label" not in stored


def test_move_by_step_sends_it_to_the_next_monitor(store, host):
    asyncio.run(api.windows_post({"action": "open", "view": "tape", "id": "wstep", "screen": 1}))
    out = asyncio.run(api.windows_post({"action": "move", "id": "wstep", "step": 1}))
    assert out["ok"] is True
    assert host.opened["wstep"]["x"] < SECOND["x"], "step +1 from Monitor 2 must land on Monitor 1"


def test_a_step_with_nowhere_to_go_moves_nothing(store):
    """One monitor, "send it to the next monitor": the honest answer is a no-op. The first cut
    resolved the step cyclically to the SAME screen and re-centred the window — measured live on a
    single-display host, where the key moved a window the user had placed by hand."""
    single = FakeHost(screens=[PRIMARY])
    windows_mod.set_host(single)
    try:
        asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wone", "preset": "left"}))
        before = dict(single.opened["wone"])
        assert before["x"] == 0 and before["width"] == PRIMARY["width"] // 2
        out = asyncio.run(api.windows_post({"action": "move", "id": "wone", "step": 1}))
        assert out["ok"] is True and out["moved"] == "" and "already on that monitor" in out["note"]
        assert single.moved == [], "nothing may move when there is no other monitor"
        assert single.opened["wone"] == before, "the hand-placed window must survive the key"
    finally:
        windows_mod.set_host(None)


def test_an_explicit_centre_still_centres_on_one_screen(store):
    """The no-op rule is about `step`, not about `center`: asking for the centre explicitly is a
    real request and must still be honoured."""
    single = FakeHost(screens=[PRIMARY])
    windows_mod.set_host(single)
    try:
        asyncio.run(api.windows_post({"action": "open", "view": "tape", "id": "wc1", "preset": "left"}))
        out = asyncio.run(api.windows_post({"action": "move", "id": "wc1", "preset": "center"}))
        assert out["ok"] is True and out["moved"] == "wc1"
        assert single.opened["wc1"]["x"] == (PRIMARY["width"] - single.opened["wc1"]["width"]) // 2
    finally:
        windows_mod.set_host(None)


def test_move_with_a_preset_snaps_where_it_already_is(store, host):
    asyncio.run(api.windows_post({"action": "open", "view": "cvd", "id": "wsnap", "screen": 1}))
    out = asyncio.run(api.windows_post({"action": "move", "id": "wsnap", "preset": "left"}))
    assert out["ok"] is True and out["screen_label"].startswith("Monitor 2")
    placed = host.opened["wsnap"]
    assert placed["x"] == SECOND["x"] and placed["width"] == SECOND["width"] // 2
    assert placed["height"] == SECOND["height"] - windows_mod.CHROME_H


def test_move_of_a_stored_window_only_replaces_its_record(store, host):
    """A safe start leaves records in the set with no window open (§73's restore=False): sending
    one to a monitor must re-place the record so it OPENS there — the host stays out of it."""
    store.save_config({"ui": {"windows": [
        {"id": "wshut", "view": "ofx", "x": 100, "y": 100, "width": 1100, "height": 760},
    ]}})
    out = asyncio.run(api.windows_post({"action": "move", "id": "wshut", "screen": 1, "preset": "right"}))
    assert out["ok"] is True
    assert host.moved == [] and host.opened == {}
    stored = out["windows"][0]
    assert stored["x"] == SECOND["x"] + SECOND["width"] // 2
    assert stored["width"] == SECOND["width"] - SECOND["width"] // 2


def test_a_refused_move_leaves_everything_where_it_was(store, host):
    asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wstay", "screen": 0}))
    before = dict(host.opened["wstay"])
    host.refuse_move = True
    out = asyncio.run(api.windows_post({"action": "move", "id": "wstay", "screen": 1}))
    assert out["ok"] is False and "could not move" in out["error"]
    assert host.opened["wstay"]["x"] == before["x"], "a refused move must not have moved anything"
    stored = out["windows"][0]
    assert stored["x"] == before["x"], "the store must keep saying where the window really is"


def test_move_of_an_unknown_window_is_refused(host):
    out = asyncio.run(api.windows_post({"action": "move", "id": "wghost", "screen": 1}))
    assert out["ok"] is False and "no window" in out["error"]


def test_open_with_a_preset_lands_already_snapped(store, host):
    out = asyncio.run(api.windows_post({"action": "open", "view": "depth", "id": "wopen",
                                        "screen": 1, "preset": "right"}))
    assert out["ok"] is True and out["screen_label"].startswith("Monitor 2")
    placed = out["opened"]
    assert placed["x"] == SECOND["x"] + SECOND["width"] // 2
    assert placed["width"] == SECOND["width"] - SECOND["width"] // 2
    assert host.opened["wopen"]["x"] == placed["x"]


def test_the_state_says_where_every_open_window_is(store, host):
    asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "won1", "screen": 0}))
    asyncio.run(api.windows_post({"action": "open", "view": "tape", "id": "won2", "screen": 1}))
    state = asyncio.run(api.windows_get())
    assert state["open_geometry"]["won1"]["screen"] == 0
    assert state["open_geometry"]["won2"]["screen_label"].startswith("Monitor 2")
    assert state["stranded"] == []


def test_arrange_brings_home_only_the_windows_whose_monitor_is_gone(store, host):
    """The unplug rescue: a window whose position is on a monitor that no longer exists comes home;
    a window that still has its screen is left exactly alone. The window here is open where its
    record says (the host is the truth about that) — the state must call that out as stranded."""
    store.save_config({"ui": {"windows": [
        {"id": "wgohome", "view": "ofx", "x": 9000, "y": 40, "width": 1100, "height": 760},
        {"id": "wstay2", "view": "tape", "x": 100, "y": 100, "width": 900, "height": 700},
    ]}})
    host.open({"id": "wgohome", "view": "ofx", "x": 9000, "y": 40, "width": 1100, "height": 760})
    state = asyncio.run(api.windows_get())
    assert state["stranded"] == ["wgohome"]
    assert state["open_geometry"]["wgohome"]["screen"] == -1
    out = asyncio.run(api.windows_post({"action": "arrange"}))
    assert out["ok"] is True and out["moved"] == ["wgohome"]
    assert [m[0] for m in host.moved] == ["wgohome"]
    assert host.opened["wgohome"]["x"] < PRIMARY["width"]
    stored = {r["id"]: r for r in out["windows"]}
    assert stored["wstay2"]["x"] == 100, "a window with a live screen must not be touched"
    assert stored["wgohome"]["x"] is not None and stored["wgohome"]["screen_key"] == ""


def test_arrange_with_nothing_stranded_says_so(store, host):
    asyncio.run(api.windows_post({"action": "open", "view": "ofx", "id": "wfine", "screen": 0}))
    out = asyncio.run(api.windows_post({"action": "arrange"}))
    assert out["ok"] is True and out["moved"] == [] and "nothing was stranded" in out["note"]


def test_arrange_rescues_a_live_window_the_store_still_lists_as_placed(store, host):
    """Measured live: an aux window pushed to (9000, 40) kept a record that said (100, 100) — the
    store lagged the window, and only the live rect knew it needed rescuing."""
    store.save_config({"ui": {"windows": [
        {"id": "wdrift", "view": "ofx", "x": 100, "y": 100, "width": 900, "height": 700},
    ]}})
    host.open({"id": "wdrift", "view": "ofx", "x": 9000, "y": 40, "width": 900, "height": 700})
    state = asyncio.run(api.windows_get())
    assert state["stranded"] == ["wdrift"]
    assert state["open_geometry"]["wdrift"]["screen"] == -1
    out = asyncio.run(api.windows_post({"action": "arrange"}))
    assert out["ok"] is True and out["moved"] == ["wdrift"]
    assert host.moved and host.moved[0][0] == "wdrift"
    assert host.opened["wdrift"]["x"] < PRIMARY["width"]
    assert out["stranded"] == [], "after the rescue there is nothing left to rescue"
