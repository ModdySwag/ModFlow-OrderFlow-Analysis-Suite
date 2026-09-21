"""R6 storage management pins: the clamps, the growth maths, the backup artefact, the rotation.

The artefact assertions are the point of this file: a backup is only worth anything if the copy
opens, the CSV reads in a spreadsheet and the manifest tells the truth about what is inside.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

import pytest

from orderflow_system.desktop import storage as st


def _db(tmp_path: Path, rows: int = 50) -> Path:
    """A miniature database in the real schema's shape."""
    path = tmp_path / "orderflow_data.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")   # the app's own mode: the copy inherits it
    conn.executescript(
        """
        CREATE TABLE ticks (instrument TEXT, timestamp_ms INTEGER, price REAL, size REAL,
                            side TEXT, trade_id TEXT);
        CREATE TABLE candles (instrument TEXT, timestamp_ms INTEGER, timeframe TEXT, open REAL,
                              high REAL, low REAL, close REAL, volume REAL);
        CREATE TABLE signals (instrument TEXT, timestamp_ms INTEGER, kind TEXT, score REAL);
        CREATE TABLE volume_profiles (instrument TEXT, day TEXT, price REAL, volume REAL);
        """)
    now_ms = int(time.time() * 1000)
    conn.executemany("INSERT INTO ticks VALUES (?,?,?,?,?,?)",
                     [("BTCUSDT", now_ms - i * 1000, 100.0 + i, 1.0, "buy", str(i))
                      for i in range(rows)])
    conn.executemany("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?)",
                     [("BTCUSDT", now_ms - i * 60000, "1m", 1.0, 2.0, 0.5, 1.5, 3.0)
                      for i in range(rows)])
    conn.execute("INSERT INTO signals VALUES ('BTCUSDT', ?, 'delta', 42.0)", (now_ms,))
    conn.commit()
    conn.close()
    return path


# ── settings ─────────────────────────────────────────────────────────────────────────────────

def test_clamp_storage_settings_falls_back_on_junk():
    """A hand-edited config tunes the numbers; it can never break the job."""
    out = st.clamp_storage_settings({"storage": {
        "auto_backup": "yes", "backup_interval_hours": "-4", "backup_keep": 9999,
        "backup_format": "tar.gz", "backup_target": "  E:/backups  ", "max_db_mb": "lots",
    }})
    assert out["auto_backup"] is True
    assert out["backup_interval_hours"] == 1          # clamped up to the floor
    assert out["backup_keep"] == 60                   # clamped down to the ceiling
    assert out["backup_format"] == "sqlite+csv"       # unknown format -> the default
    assert out["backup_target"] == "E:/backups"
    assert out["max_db_mb"] == 0                      # junk -> off
    assert st.clamp_storage_settings({}) == st.DEFAULT_SETTINGS


def test_resolved_target_defaults_beside_the_config(tmp_path):
    assert st.resolved_target({"backup_target": ""}, tmp_path) == tmp_path / "backups"
    assert st.resolved_target({"backup_target": r"\\server\share"}, tmp_path) == Path(r"\\server\share")


# ── growth ───────────────────────────────────────────────────────────────────────────────────

def test_growth_report_maths_and_steady_state():
    now = time.time()
    samples = [[now - 3600, 100_000_000], [now - 1800, 125_000_000], [now, 150_000_000]]
    g = st.growth_report(samples, 150_000_000, now=now, retention_days=7)
    assert g["ok"] and g["samples"] == 3
    assert g["bytes_per_hour"] == pytest.approx(50_000_000, rel=0.01)
    assert g["bytes_per_day"] == pytest.approx(1_200_000_000, rel=0.01)
    assert g["steady_state_bytes"] == pytest.approx(8_400_000_000, rel=0.01)
    assert "steady state" in g["note"]

    thin = st.growth_report([[now, 10]], 10, now=now)
    assert thin["ok"] is False and "not enough history" in thin["note"]


def test_growth_report_says_when_retention_is_off():
    now = time.time()
    g = st.growth_report([[now - 3600, 0], [now, 50_000_000]], 50_000_000, now=now)
    assert g["ok"] and "retention is off" in g["note"]


def test_record_sample_respects_the_gap_and_the_cap(tmp_path):
    path = tmp_path / "storage-usage.json"
    now = time.time()
    st.record_sample(path, 100, now=now)
    st.record_sample(path, 200, now=now + 60)          # inside the 10-minute gap: ignored
    assert json.loads(path.read_text(encoding="utf-8"))["samples"] == [[round(now, 1), 100]]
    for i in range(12):
        st.record_sample(path, 1000 + i, now=now + 3600 + i * 700, min_gap_s=0, keep=5)
    kept = json.loads(path.read_text(encoding="utf-8"))["samples"]
    assert len(kept) == 5 and kept[-1][1] == 1011      # newest wins, the cap holds


def test_threshold_message_only_when_over_budget():
    usage = {"db_bytes": 900_000_000, "wal_bytes": 10_000_000}
    assert st.threshold_message(usage, {"max_db_mb": 0}) is None        # budget off
    assert st.threshold_message(usage, {"max_db_mb": 1200}) is None     # under
    message = st.threshold_message(usage, {"max_db_mb": 800})
    assert message and "910 MB" in message["message"] and message["severity"] == "warning"


def test_usage_snapshot_counts_the_wal_and_the_folders(tmp_path):
    db = _db(tmp_path)
    config_dir = tmp_path / "cfg"
    (config_dir / "exports").mkdir(parents=True)
    (config_dir / "exports" / "tape.csv").write_text("a,b\r\n1,2\r\n", encoding="utf-8")
    (config_dir / "orderflow.log").write_text("x" * 500, encoding="utf-8")
    (config_dir / "orderflow.log.1").write_text("y" * 300, encoding="utf-8")   # the rotation ring
    (config_dir / "webview2").mkdir(parents=True)
    (config_dir / "webview2" / "Cache").write_bytes(b"c" * 700)                # the shell's cache
    (config_dir / "archive").mkdir(parents=True)
    (config_dir / "archive" / "quarantine.db").write_bytes(b"q" * 200)
    Path(str(db) + "-wal").write_bytes(b"w" * 400)
    snap = st.usage_snapshot(db, config_dir=config_dir)
    assert snap["db_bytes"] > 0 and snap["wal_bytes"] == 400
    assert snap["exports_bytes"] > 0
    assert snap["log_bytes"] == 800, "the whole log ring counts, not one file of it"
    assert snap["webview2_bytes"] == 700 and snap["archive_bytes"] == 200, (
        "the WebView2 cache and the archive folder are the app's footprint and belong in the total")
    assert snap["total_bytes"] == (snap["db_bytes"] + snap["wal_bytes"] + snap["log_bytes"]
                                   + snap["exports_bytes"] + snap["webview2_bytes"]
                                   + snap["archive_bytes"] + snap["backups_bytes"])


# ── the backup artefact ──────────────────────────────────────────────────────────────────────

def test_run_backup_writes_a_portable_set(tmp_path):
    db = _db(tmp_path)
    target = tmp_path / "backups"
    manifest = st.run_backup(db, target, fmt="sqlite+csv", keep=2)

    folder = Path(manifest["folder"])
    assert folder.name.startswith(st.BACKUP_PREFIX) and folder.parent == target
    assert manifest["format"] == "modflow-backup/1"

    # the copy opens and carries the rows — the only proof a backup works
    copy = folder / manifest["database"]["file"]
    conn = sqlite3.connect(copy)
    try:
        assert conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 50
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()
    assert manifest["database"]["integrity"] == "ok"
    assert len(manifest["database"]["sha256"]) == 64
    # a backup is ONE file: the copy must not carry the source's WAL sidecars with it
    assert not [p for p in folder.iterdir() if p.name.endswith(("-wal", "-shm"))], \
        sorted(p.name for p in folder.iterdir())

    # CSV: RFC 4180 (CRLF), UTF-8, ISO 8601 timestamps, header row. Read with newline="" —
    # read_text() translates CRLF away and would hide exactly what this assertion is about.
    candles_csv = folder / "candles.csv"
    with candles_csv.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    lines = text.splitlines()
    assert lines[0] == "instrument,timestamp_ms,timeframe,open,high,low,close,volume"
    stamp = lines[1].split(",")[1]
    assert stamp.endswith("Z") and "T" in stamp and stamp.startswith("20")
    assert "\r\n" in text
    assert (folder / "ticks-summary.csv").exists()

    # the manifest tells the truth about what is inside
    on_disk = json.loads((folder / st.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert on_disk["tables"]["ticks"] == 50
    assert {entry["table"] for entry in on_disk["csv"]} >= {"candles", "signals", "volume_profiles", "ticks"}


def test_run_backup_rotates_to_the_newest_n(tmp_path):
    db = _db(tmp_path)
    target = tmp_path / "backups"
    first = st.run_backup(db, target, fmt="sqlite", keep=2, now=time.time() - 7200)
    second = st.run_backup(db, target, fmt="sqlite", keep=2, now=time.time() - 3600)
    third = st.run_backup(db, target, fmt="sqlite", keep=2, now=time.time())
    remaining = sorted(p.name for p in target.glob(st.BACKUP_PREFIX + "*"))
    assert len(remaining) == 2
    assert Path(first["folder"]).name not in remaining
    assert Path(second["folder"]).name in remaining and Path(third["folder"]).name in remaining
    assert third["removed"] == [Path(first["folder"]).name]


def test_run_backup_refuses_saying_why(tmp_path):
    db = _db(tmp_path)
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("i am a file", encoding="utf-8")
    with pytest.raises(st.StorageError):
        st.run_backup(db, blocker)                     # target is a file: the OS reason is shown
    with pytest.raises(st.StorageError):
        st.run_backup(db, tmp_path / "b", fmt="tar.gz")  # unknown format refused up front
    with pytest.raises(st.StorageError):
        st.run_backup(tmp_path / "missing.db", tmp_path / "b")


def test_list_backups_and_age(tmp_path):
    db = _db(tmp_path)
    target = tmp_path / "backups"
    when = time.time() - 3600
    st.run_backup(db, target, fmt="csv", now=when)
    sets = st.list_backups(target)
    assert len(sets) == 1
    assert sets[0]["created_at"].endswith("Z")
    age = st.backup_age_seconds(sets[0], target)
    assert age == pytest.approx(3600, abs=5)
    assert st.backup_age_seconds({}, tmp_path / "nothing") == float("inf")   # unknown -> due


def test_vacuum_refuses_without_headroom(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(st.shutil, "disk_usage",
                        lambda _p: type("U", (), {"free": 1, "total": 1, "used": 0})())
    refused = st.vacuum_now(db, allow_full=True)
    assert refused["ok"] is False and "VACUUM needs" in refused["error"]
    # the incremental pass is always safe (no second copy is made)
    assert st.vacuum_now(db, allow_full=False)["ok"] is True


def test_build_report_carries_the_numbers(tmp_path):
    db = _db(tmp_path)
    target = tmp_path / "backups"
    st.run_backup(db, target, fmt="sqlite", keep=3)
    usage = st.usage_snapshot(db, config_dir=tmp_path, target=target)
    growth = st.growth_report([[time.time() - 3600, 0], [time.time(), usage["db_bytes"]]],
                              usage["db_bytes"], retention_days=7)
    subject, body, csv_text = st.build_report(
        usage, growth, {"days": 7, "prune_interval_hours": 6, "session_start_hour": 0},
        st.list_backups(target), {"at_ms": int(time.time() * 1000), "deleted": 12, "other_deleted": {}})
    assert subject.startswith("[OrderFlow] storage report")
    assert "Retention" in body and "steady state" in body and "sha256" in body
    assert csv_text.splitlines()[0] == "metric,value"
    assert any(line.startswith("retention_days,") for line in csv_text.splitlines())


def test_email_report_without_a_mailbox_says_so(monkeypatch):
    result = asyncio.run(st.email_report({}, "subject", "body"))
    assert result["ok"] is False and "not configured" in result["error"]

    # configured: the one SMTP path is used, with the attachment
    from orderflow_system.atlas.notify import EmailNotifier

    captured: dict[str, object] = {}

    def fake_send(self, subject, body, attachments=None):
        captured.update({"subject": subject, "attachments": list(attachments or [])})
        return True

    monkeypatch.setattr(EmailNotifier, "_smtp_send", fake_send)
    cfg = {"notify": {"email": {"enabled": True, "host": "smtp.example.com", "port": 587,
                                "to": "alerts@example.com", "from": "me@example.com"}}}
    result = asyncio.run(st.email_report(cfg, "S", "B", attachments=[("s.csv", b"a,b\r\n", "text/csv")]))
    assert result["ok"] is True
    assert captured["subject"] == "S" and captured["attachments"][0][0] == "s.csv"


# ── clearing the app cache and the quarantine (R6b) ──────────────────────────────────────────

def test_clear_app_cache_frees_what_it_can_and_schedules_the_rest(tmp_path):
    """The open window holds its profile: what can go, goes; the rest is armed for the next boot."""
    cfg = tmp_path / "cfg"
    cache = cfg / "webview2" / "EBWebView" / "Default" / "Cache"
    cache.mkdir(parents=True)
    (cache / "entry.bin").write_bytes(b"c" * 4096)
    locked = cache / "in-use.bin"
    locked.write_bytes(b"l" * 2048)
    keep = cfg / "webview2" / "EBWebView" / "Local State"
    keep.write_text("profile", encoding="utf-8")
    handle = locked.open("r+b")
    try:
        result = st.clear_app_cache(cfg)
        assert result["freed_bytes"] == 4096, "the deletable entry frees, the locked one stays"
        assert locked.exists() and keep.exists(), "a lock and a non-cache file both survive the pass"
        assert result["scheduled"] is True
        assert (cfg / st.CLEAR_CACHE_FLAG).exists(), "with anything left behind, the boot flag is armed"
    finally:
        handle.close()
    boot = st.apply_pending_cache_clear(cfg)
    assert boot["cleared"] is True and boot["freed_bytes"] > 0
    assert not (cfg / "webview2").exists(), "the boot pass takes the whole profile"
    assert not (cfg / st.CLEAR_CACHE_FLAG).exists()


def test_clear_app_cache_with_nothing_to_clear_is_quiet(tmp_path):
    result = st.clear_app_cache(tmp_path / "empty")
    assert result["ok"] is True and result["freed_bytes"] == 0 and result["scheduled"] is False


def test_apply_pending_cache_clear_is_a_noop_without_the_flag(tmp_path):
    cfg = tmp_path / "cfg"
    (cfg / "webview2").mkdir(parents=True)
    (cfg / "webview2" / "keep.bin").write_bytes(b"k" * 64)
    assert st.apply_pending_cache_clear(cfg) == {"cleared": False, "freed_bytes": 0}
    assert (cfg / "webview2" / "keep.bin").exists()


def test_clear_archive_removes_the_contents_and_keeps_the_folder(tmp_path):
    cfg = tmp_path / "cfg"
    entry = cfg / "archive" / "stray-repo-data-2026-01-01"
    entry.mkdir(parents=True)
    (entry / "old.db").write_bytes(b"d" * 999)
    (cfg / "archive" / "loose.txt").write_text("x" * 11, encoding="utf-8")
    result = st.clear_archive(cfg)
    assert result["ok"] is True
    assert sorted(result["removed"]) == ["loose.txt", "stray-repo-data-2026-01-01"]
    assert result["freed_bytes"] == 1010 and result["remaining_bytes"] == 0
    assert (cfg / "archive").is_dir() and not any((cfg / "archive").iterdir())
