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

    def screens(self) -> list[dict]:
        return [dict(s) for s in self._screens]

    def open(self, record: dict) -> dict:
        assert record["id"] not in self.opened, "the API asked for a duplicate window"
        self.opened[record["id"]] = dict(record)
        return record

    def close(self, wid: str) -> bool:
        self.closed.append(wid)
        return self.opened.pop(wid, None) is not None

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
