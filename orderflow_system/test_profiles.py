"""Profiles — switchable playbooks: the store clamps, the lifecycle works, the two promises hold.

The two promises this file exists to pin:

1. **A profile never carries a credential, machine path or network setting.** Capture reads only
   `config_store.PROFILE_BLOCKS`, the sanitiser drops anything else, and an exported bundle is
   therefore shareable by construction — asserted against the SEC-09 secret paths by value, not
   by spelling.
2. **Applying a profile never touches anything it does not carry.** A switch replaces exactly
   the blocks the profile holds; tokens, ports, storage paths and machine settings survive it.

Plus the lifecycle receipts: saved/dirty/preview/apply/update (with the version ring) / rename /
duplicate / delete / restore / default + boot auto-apply / rules clamping / export + import, and
the journal's profile tag (the "trades under this playbook" metric) with its legacy migration.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store, profiles

FAKE_TOKEN = "123456:FAKE-TOKEN-ABCDEF"
FAKE_ALPACA = "PKFAKEPROFILEKEY"


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    """An isolated config dir with a factory config and one fake credential to defend."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    config_store.save_config(config_store.merge_config({
        "telegram": {"bot_token": FAKE_TOKEN},
        "alpaca": {"key_id": FAKE_ALPACA, "secret": "fake-secret"},
    }))
    return tmp_path


def _only_profile(state: dict) -> dict:
    assert state.get("ok"), state
    assert len(state["items"]) == 1, state["items"]
    return state["items"][0]


# ── the two promises ──────────────────────────────────────────────────────────────────────────

def test_capture_can_never_carry_a_credential(scratch):
    snapshot = config_store.profile_capture(config_store.load_config())
    assert set(snapshot) <= set(config_store.PROFILE_BLOCKS)
    for forbidden in ("telegram", "notify", "platforms", "alpaca", "mt5", "dashboard", "storage",
                      "updates", "logging", "data", "version"):
        assert forbidden not in snapshot, f"{forbidden} must never be capturable"
    text = json.dumps(snapshot)
    assert FAKE_TOKEN not in text and FAKE_ALPACA not in text


def test_apply_replaces_only_the_carried_blocks(scratch):
    out = profiles.save("Playbook A", blocks=["atlas", "ui"])
    ident = out["saved"]
    entry = _only_profile(out)
    assert set(entry["blocks"]) == {"atlas", "ui"}

    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 1234}}, "ui": {"scale": 0.8},
                               "telegram": {"chat_id": "777"}, "dashboard": {"port": 8123}})
    result = profiles.apply(ident)
    assert result["ok"] and result["applied"]
    assert set(result["changed"]) <= {"atlas", "ui"}

    live = config_store.load_config()
    # the carried blocks are back to the profile; the rest is untouched
    snapshot = config_store.load_config()["profiles"]["items"][ident]["snapshot"]
    assert live["atlas"] == snapshot["atlas"]
    assert live["ui"] == snapshot["ui"]
    assert live["telegram"]["bot_token"] == FAKE_TOKEN, "a switch must not touch credentials"
    assert live["telegram"]["chat_id"] == "777", "a switch must not touch blocks it does not carry"
    assert live["dashboard"]["port"] == 8123


def test_dirty_preview_and_apply_round_trip(scratch):
    out = profiles.save("Playbook A", blocks=["atlas"])
    ident = out["saved"]
    assert _only_profile(out)["dirty"] is False

    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 4242}}})
    state = profiles.state()
    row = state["items"][0]
    assert row["dirty"] is True and row["dirty_blocks"] == ["atlas"]

    preview = profiles.preview(ident)
    assert preview["ok"] and preview["changed"] == ["atlas"] and preview["already_current"] is False
    assert preview["restart"] == ["atlas"], "atlas parameters are read by the engine at start"

    applied = profiles.apply(ident)
    assert applied["ok"] and applied["applied"] and applied["already_current"] is False
    row = profiles.state()["items"][0]
    assert row["dirty"] is False and row["stats"]["applied"] == 1
    assert profiles.state()["active"] == ident


def test_restart_blocks_are_flagged_for_the_engine(scratch):
    out = profiles.save("Feed swap", blocks=["data_source", "instruments"])
    ident = out["saved"]
    config_store.merge_config({"data_source": "mt5"})
    preview = profiles.preview(ident)
    assert set(preview["changed"]) == {"data_source"}
    assert preview["restart"] == ["data_source"]


# ── lifecycle ─────────────────────────────────────────────────────────────────────────────────

def test_update_banks_a_version_and_restore_brings_it_back(scratch):
    out = profiles.save("Playbook A", blocks=["atlas"])
    ident = out["saved"]
    before = json.loads(json.dumps(profiles.state()["items"][0]))
    assert before  # silences the linter about the name

    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 5555}}})
    updated = profiles.update(ident)
    assert updated["ok"]
    ring = config_store.load_config()["profiles"]["versions"][ident]
    assert len(ring) == 1 and ring[0]["entry"]["snapshot"]["atlas"]["heatmap"]["bucket_ms"] != 5555

    at = ring[0]["at"]
    restored = profiles.restore_version(ident, at)
    assert restored["ok"] and restored["restored_at"] == at
    entry = profiles.state()["items"][0]
    assert entry["dirty"] is True, "restoring a profile version does not re-tune the live app"


def test_rename_duplicate_delete(scratch):
    out = profiles.save("Playbook A", blocks=["atlas"])
    ident = out["saved"]

    renamed = profiles.rename(ident, "London FX")
    assert renamed["ok"] and _only_profile(renamed)["name"] == "London FX"

    dup = profiles.duplicate(ident)
    assert dup["ok"] and len(dup["items"]) == 2
    copy = next(row for row in dup["items"] if row["id"] != ident)
    assert copy["name"].startswith("London FX")
    assert copy["stats"]["applied"] == 0 and copy["blocks"] == ["atlas"]

    deleted = profiles.delete(ident)
    assert deleted["ok"] and len(deleted["items"]) == 1
    assert config_store.load_config()["profiles"]["versions"].get(ident), "a delete stays recoverable"


def test_delete_clears_active_and_default_pointers(scratch):
    ident = profiles.save("Playbook A", blocks=["atlas"])["saved"]
    profiles.apply(ident)
    profiles.set_default(ident, auto_apply=True)
    profiles.delete(ident)
    block = config_store.load_config()["profiles"]
    assert block["active"] == "" and block["default"] == ""


def test_default_and_boot_apply(scratch):
    ident = profiles.save("Playbook A", blocks=["atlas"])["saved"]
    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 9999}}})
    profiles.set_default(ident, auto_apply=True)

    assert profiles.boot_apply() == ident
    live = config_store.load_config()
    assert live["atlas"] == live["profiles"]["items"][ident]["snapshot"]["atlas"]
    assert live["profiles"]["items"][ident]["stats"]["applied"] == 1

    # auto-apply off → boot does nothing
    profiles.set_default(ident, auto_apply=False)
    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 1111}}})
    assert profiles.boot_apply() is None
    assert config_store.load_config()["atlas"]["heatmap"]["bucket_ms"] == 1111


def test_active_time_is_banked_across_switches(scratch):
    a = profiles.save("A", blocks=["atlas"])["saved"]
    b = profiles.save("B", blocks=["atlas"])["saved"]
    profiles.apply(a)
    profiles.apply(b)
    block = config_store.load_config()["profiles"]["items"]
    assert block[a]["stats"]["active_since"] == 0, "the previous playbook's clock stops on switch"
    assert block[b]["stats"]["active_since"] > 0
    assert block[a]["stats"]["active_ms"] >= 0


# ── rules, scoping, sharing ───────────────────────────────────────────────────────────────────

def test_rules_clamp_and_die_with_their_target(scratch):
    a = profiles.save("A", blocks=["atlas"])["saved"]
    b = profiles.save("B", blocks=["atlas"])["saved"]
    out = profiles.set_rules({
        "enabled": True,
        "sources": {"bybit": a, "not-a-feed": b, "mt5": "pfdeadbeef"},
        "windows": [
            {"from": "07:00", "to": "16:00", "days": [0, 1, 2, 3, 4], "profile": a},
            {"from": "25:00", "to": "16:00", "profile": a},          # bad clock → dropped
            {"from": "08:00", "to": "08:00", "profile": a},          # empty window → dropped
            {"from": "16:00", "to": "23:00", "profile": "pf00000000"},  # unknown id → dropped
        ],
    })
    rules = out["rules"]
    assert rules["enabled"] is True
    assert rules["sources"] == {"bybit": a}
    assert len(rules["windows"]) == 1 and rules["windows"][0]["days"] == [0, 1, 2, 3, 4]

    profiles.set_rules({"sources": {"bybit": a}, "windows": rules["windows"]})
    profiles.delete(a)
    after = config_store.load_config()["profiles"]["rules"]
    assert after["sources"] == {} and after["windows"] == [], "rules die with their profile"


def test_scoped_save_carries_only_the_chosen_blocks(scratch):
    entry = _only_profile(profiles.save("Just analysis", blocks=["atlas", "ofx", "not a block"]))
    assert set(entry["blocks"]) == {"atlas", "ofx"}


def test_from_defaults_ignores_the_live_edits(scratch):
    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 777}}})
    entry = _only_profile(profiles.save("Factory", blocks=["atlas"], from_defaults=True))
    factory = config_store.default_config()["atlas"]
    stored = config_store.load_config()["profiles"]["items"][entry["id"]]["snapshot"]["atlas"]
    assert stored == factory
    assert stored["heatmap"]["bucket_ms"] != 777


def test_export_is_shareable_and_import_returns_it(scratch):
    ident = profiles.save("Playbook A", blocks=["atlas", "watchlist"])["saved"]
    filename, text, error = profiles.export_bundle(ident)
    assert not error and filename.endswith(".json")
    assert FAKE_TOKEN not in text and FAKE_ALPACA not in text
    bundle = json.loads(text)
    assert bundle["ofap_profile"] == 1 and set(bundle["profile"]["snapshot"]) <= set(config_store.PROFILE_BLOCKS)

    imported = profiles.import_bundle(bundle)
    assert imported["ok"] and len(imported["items"]) == 2
    names = [row["name"] for row in imported["items"]]
    assert "Playbook A" in names and "Playbook A 2" in names


def test_import_rejects_junk(scratch):
    assert profiles.import_bundle({"hello": "world"})["ok"] is False
    assert profiles.import_bundle({"profile": {"snapshot": "not a dict"}})["ok"] is False


def test_the_sanitiser_caps_and_drops(scratch):
    raw = config_store.load_config()
    block = raw["profiles"]
    block["items"] = {}
    for i in range(60):                                                   # over PROFILE_ITEMS_MAX
        ident = f"pf{i:08x}"
        block["items"][ident] = {"id": ident, "name": "x" * 100,
                                 "snapshot": {"atlas": {"k": "v"}, "telegram": {"bot_token": FAKE_TOKEN}}}
    block["items"]["not-an-id"] = {"id": "not-an-id", "snapshot": {"atlas": {}}}
    block["items"]["pf00000001"]["snapshot"]["ui"] = {"blob": "x" * (config_store.PROFILE_SNAPSHOT_MAX_CHARS + 1)}
    saved = config_store.save_config(raw)
    kept = saved["profiles"]["items"]
    assert len(kept) <= config_store.PROFILE_ITEMS_MAX
    assert "not-an-id" not in kept
    sample = next(iter(kept.values()))
    assert "telegram" not in sample["snapshot"], "the whitelist is enforced even inside a snapshot"
    assert "ui" not in kept["pf00000001"]["snapshot"], "an over-size block is dropped, not stored"


# ── wiring ────────────────────────────────────────────────────────────────────────────────────

def test_the_routes_and_boot_are_wired():
    repo = Path(__file__).resolve().parent
    api = (repo / "desktop" / "api.py").read_text(encoding="utf-8")
    assert '@router.get("/profiles")' in api and '@router.post("/profiles")' in api
    launcher = (repo / "desktop" / "launcher.py").read_text(encoding="utf-8")
    assert "profiles_mod.boot_apply()" in launcher
    assert "profiles as profiles_mod" in api


def test_journal_rows_carry_the_profile_and_old_files_migrate(tmp_path):
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE trade_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT NOT NULL,"
                 " direction TEXT NOT NULL, entry_time_ms INTEGER, exit_time_ms INTEGER, entry_price REAL,"
                 " exit_price REAL, stop_loss REAL, take_profit REAL, pnl_ticks REAL, rr_ratio REAL,"
                 " signals_json TEXT, notes TEXT)")
    conn.commit()
    conn.close()

    from orderflow_system.data.database import Database

    async def run():
        db = Database(str(db_file))
        await db.connect()                                  # the migration runs on connect
        await db.close()

    asyncio.run(run())
    cols = {row[1] for row in sqlite3.connect(db_file).execute("PRAGMA table_info(trade_journal)")}
    assert "profile_id" in cols, "a legacy file gets the column without losing the journal"


def test_profiles_routes_round_trip_on_the_app(scratch):
    from fastapi.testclient import TestClient

    from orderflow_system.test_wiring import _desktop_app

    client = TestClient(_desktop_app())
    got = client.get("/api/control/profiles")
    assert got.status_code == 200 and got.json()["count"] == 0

    saved = client.post("/api/control/profiles", json={"save": {"name": "Route playbook", "blocks": ["atlas"]}})
    assert saved.status_code == 200 and saved.json()["ok"]
    ident = saved.json()["saved"]

    config_store.merge_config({"atlas": {"heatmap": {"bucket_ms": 3210}}})
    dry = client.post("/api/control/profiles", json={"apply": ident, "dry_run": True}).json()
    assert dry["changed"] == ["atlas"] and dry["dry_run"] is True

    live = client.post("/api/control/profiles", json={"apply": ident}).json()
    assert live["ok"] and live["applied"] and live["changed"] == ["atlas"]

    gone = client.post("/api/control/profiles", json={"delete": ident}).json()
    assert gone["ok"] and gone["count"] == 0


def test_state_exposes_the_version_ring_for_the_ui(scratch):
    """The view offers "restore a previous setup"; that needs the ring in the state payload.

    The store has banked versions since the ring landed (update/rename keep the previous entry),
    but `state()` only reported a boolean `dirty`, so the recovery the delete copy promises had no
    control behind it. This pins the field the control renders.
    """
    out = profiles.save("Playbook A", blocks=["atlas"])
    ident = _only_profile(out)["id"]
    assert _only_profile(profiles.state())["versions"] == [], "nothing banked before a write"

    config_store.save_config(config_store.merge_config({"atlas": {"tape": {"min_size": 5}}}))
    profiles.update(ident)                                    # banks the previous snapshot
    ring = _only_profile(profiles.state())["versions"]
    assert len(ring) == 1, ring
    assert ring[0]["at"] > 0 and ring[0]["blocks"] == ["atlas"] and ring[0]["name"] == "Playbook A"

    profiles.restore_version(ident, ring[0]["at"])            # the control's own call
    row = _only_profile(profiles.state())
    assert row["versions"], "a restore banks the state it replaced, so the ring stays usable"


# ── the restart notice: what a switch cannot land on a running engine ─────────────────────────

def _engine_running(monkeypatch, running: bool) -> None:
    from orderflow_system.desktop import engine as engine_mod
    monkeypatch.setattr(engine_mod.engine, "status",
                        lambda: {"state": "running" if running else "stopped", "running": running})


def test_pending_restart_records_the_switch_and_clears_on_the_next_engine_start(scratch, monkeypatch):
    """A switch made while the engine runs cannot land its engine-read parts — feed, instruments,
    atlas and ofx are read at start. The store records exactly that, at the moment of the switch,
    and the next engine start clears it. A config diff was the obvious alternative and is wrong:
    the atlas and ofx blocks are re-persisted by their own panels in ordinary use (measured: merely
    loading the desktop rewrites the atlas block), so a diff would report the app's own writes.
    """
    _engine_running(monkeypatch, False)
    out = profiles.save("London FX", blocks=["data_source", "instruments", "ui"])
    ident = _only_profile(out)["id"]
    assert profiles.pending_restart() is None, "a stopped engine waits for nothing"

    _engine_running(monkeypatch, True)
    assert profiles.pending_restart() is None, "saving is not switching"

    config_store.merge_config({"instruments": [{"symbol": "BTCUSDT", "enabled": True}]})
    assert profiles.pending_restart() is None, "a manual edit is not a switch either"

    profiles.apply(ident)                          # the switch, while the engine runs
    pend = profiles.pending_restart()
    assert pend and pend["blocks"] == ["instruments"], pend
    assert pend["carried"] == ["instruments"] and pend["name"] == "London FX", pend
    assert pend["profile"] == ident and pend["at"] > 0
    assert profiles.state()["pending_restart"] == pend, "the panel's own state agrees"

    profiles.save("Theme only", blocks=["ui"])
    ui_only = next(r["id"] for r in profiles.state()["items"] if r["name"] == "Theme only")
    profiles.apply(ui_only)                        # carries nothing the engine reads
    assert profiles.pending_restart() is None, "a switch that lands everything clears the note"

    config_store.merge_config({"data_source": "mt5"})    # the engine reads the feed at start too
    profiles.apply(ident)
    assert profiles.pending_restart() is not None
    profiles.note_engine_start()                   # the restart the note asked for
    assert profiles.pending_restart() is None, "the note never outlives its restart"


def test_the_status_route_carries_the_pending_restart_answer(scratch):
    """The status bar must be able to be discreet about it from any view: the shell already polls
    /engine/status, so the derived answer rides that payload rather than a request of its own.
    """
    from fastapi.testclient import TestClient

    from orderflow_system.test_wiring import _desktop_app

    client = TestClient(_desktop_app())
    stat = client.get("/api/control/engine/status")
    assert stat.status_code == 200
    body = stat.json()
    assert "profile_restart_pending" in body, body.keys()
    assert body["profile_restart_pending"] is None, "a stopped engine has nothing waiting"


def test_the_menu_and_the_palette_drive_the_same_store():
    """The Profiles menu was a phase-3 stub ("profiles arrive in phase 3") long after the view and
    the API carried the whole lifecycle. Pin the wiring the fix depends on: no stub, and every
    OFAPPROFILES entry point the menu or the palette calls exists in the view.
    """
    import re

    ui = Path(__file__).parent / "desktop" / "ui"
    menubar = (ui / "menubar.js").read_text(encoding="utf-8")
    palette = (ui / "search.js").read_text(encoding="utf-8")
    view = (ui / "profiles.js").read_text(encoding="utf-8")

    # the stub's own markers (not the comment that explains what was replaced)
    assert "reason: 'profiles arrive in phase 3'" not in menubar, "the Profiles menu is a stub again"
    assert "planned('Save as…', 'phase 3')" not in menubar, "a phase-3 placeholder crept back"
    assert "planned('Backup all / Restore…'" not in menubar, "a phase-4 placeholder crept back"
    assert "refreshProfiles" in menubar, "the menu no longer reads the store's state"

    block = view[view.index("window.OFAPPROFILES = {"):]
    block = block[:block.index("\n        };")]
    exported = set(re.findall(r"(\w+):", block))
    used = set(re.findall(r"OFAPPROFILES\.(\w+)", menubar)) | set(re.findall(r"OFAPPROFILES\.(\w+)", palette))
    missing = sorted(used - exported)
    assert not missing, f"the menu/palette call entry points the view does not export: {missing}"
