"""Storage management (R6): usage a user can see, retention a user can set, backups it can trust.

The program already keeps its database under the user's config directory, rotates its log ring and
prunes on a window (``data.retention_days``, R4/R5). What this module adds is the layer the user
steers from Settings ▸ Storage:

* **A usage snapshot** — database + WAL, the log ring, exports, every backup set — plus a growth
  rate sampled over time and a forecast, so "will this fill my disk" has an answer, not a shrug.
* **A backup that is a real artefact in the formats everyone else uses.** A hot copy of the
  database through SQLite's own online-backup API (consistent while the engine is writing), the
  analyst-facing tables as CSV (RFC 4180, CRLF, UTF-8, ISO 8601 UTC stamps), gzipped once they are
  worth compressing, a JSON manifest carrying row counts and the SHA-256 of the database file, all
  inside one ISO-8601-stamped folder, rotated to the newest N.
* **Targets that are simply paths** — a local folder, a UNC share (``\\\\server\\share``), a
  removable drive (``E:\\``), or a synced folder (OneDrive/Dropbox/Drive). The target is validated
  by writing to it, so an unreachable share fails with the operating system's own reason.
* **A report** that can leave the machine by email through the same SMTP path the alerts use
  (``atlas.notify.EmailNotifier`` — one implementation, not two).

Everything decision-shaped is a pure function (the clamps, the growth maths, the rotation plan, the
threshold test) so the tests pin behaviour without a server, a socket or a user profile. The module
also runs headless:

    python -m orderflow_system.desktop.storage backup --target "E:/backups" --format sqlite+csv
    python -m orderflow_system.desktop.storage report --print
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

#: Every backup set this module makes starts with this name, and rotation only ever deletes
#: folders that carry it *and* our manifest — a user's own folder in the same place is not ours.
BACKUP_PREFIX = "modflow-backup-"
MANIFEST_NAME = "manifest.json"
BACKUP_FORMAT_VERSION = "modflow-backup/1"

#: The portable, analyst-facing tables. `ticks` is deliberately absent: it is the big table and the
#: database copy carries it whole, while a per-instrument/day tick matrix travels as `ticks-summary`.
CSV_TABLES = ("candles", "signals", "volume_profiles", "trade_journal")
WAL_SUFFIXES = ("-wal", "-shm")

#: Usage samples: one every ≥10 minutes, at most 288 kept (two days at that spacing) — enough for
#: a 24 h rate without the file itself becoming a storage problem.
SAMPLE_MIN_GAP_S = 600
SAMPLE_KEEP = 288

DEFAULT_SETTINGS: dict[str, Any] = {
    "auto_backup": False,
    "backup_interval_hours": 24,
    "backup_target": "",              # empty = <config>/backups
    "backup_format": "sqlite+csv",    # sqlite | csv | sqlite+csv
    "backup_keep": 5,
    "max_db_mb": 0,                   # 0 = no budget; else warn/email when the DB passes it
    "email_report": False,            # email a report after every automatic backup
    "email_threshold": True,          # email when the size budget is passed
}


class StorageError(RuntimeError):
    """A backup/cleanup could not run, with a reason worth showing the user."""


# ══════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════

def clamp_storage_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """The ``storage`` block, clamped — junk falls back to the documented defaults. Pure.

    Same contract as ``engine.clamp_data_settings``: a hand-edited config.json can tune every
    number here and can never break the job (an insane interval becomes a sane one, an unknown
    format becomes the default).
    """
    raw = dict((cfg or {}).get("storage") or {})
    out = dict(DEFAULT_SETTINGS)

    def _int(key: str, lo: int, hi: int) -> int:
        try:
            return max(lo, min(hi, int(raw.get(key, DEFAULT_SETTINGS[key]))))
        except (TypeError, ValueError):
            return int(DEFAULT_SETTINGS[key])

    fmt = str(raw.get("backup_format") or DEFAULT_SETTINGS["backup_format"]).strip().lower()
    if fmt not in ("sqlite", "csv", "sqlite+csv"):
        fmt = str(DEFAULT_SETTINGS["backup_format"])
    out["backup_format"] = fmt
    out["backup_target"] = str(raw.get("backup_target") or "").strip()
    out["backup_interval_hours"] = _int("backup_interval_hours", 1, 720)
    out["backup_keep"] = _int("backup_keep", 1, 60)
    out["max_db_mb"] = _int("max_db_mb", 0, 1_000_000)
    out["auto_backup"] = bool(raw.get("auto_backup", DEFAULT_SETTINGS["auto_backup"]))
    out["email_report"] = bool(raw.get("email_report", DEFAULT_SETTINGS["email_report"]))
    out["email_threshold"] = bool(raw.get("email_threshold", DEFAULT_SETTINGS["email_threshold"]))
    return out


def default_backup_dir(config_dir: Path | str) -> Path:
    """Where backups go unless the user names a target: beside the config, in ``backups/``."""
    return Path(config_dir) / "backups"


def resolved_target(settings: dict[str, Any], config_dir: Path | str) -> Path:
    """The configured target as a path (the default when unset). Empty string means unset."""
    raw = str(settings.get("backup_target") or "").strip()
    return Path(raw) if raw else default_backup_dir(config_dir)


# ══════════════════════════════════════════════════════════════
# Usage snapshot + growth
# ══════════════════════════════════════════════════════════════

def _file_bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _tree_bytes(path: Path) -> int:
    """Total bytes of a folder, 0 when it is absent. Depth is bounded: our own layout is flat."""
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += _file_bytes(p)
    return total


def usage_snapshot(db_path: Path | str, *, config_dir: Path | str,
                   target: Path | str | None = None, now: float | None = None) -> dict[str, Any]:
    """What this program occupies on disk, by area. Pure I/O, no engine required.

    The database is measured as the file plus its WAL (a writer-heavy hour lives in the WAL until
    the next checkpoint, and counting only the .db is how a storage panel lies small).
    """
    db = Path(db_path)
    cfg_dir = Path(config_dir)
    backups_dir = Path(target) if target else default_backup_dir(cfg_dir)
    log_bytes = sum(_file_bytes(cfg_dir / name) for name in ("orderflow.log", "desktop.log"))
    parts = {
        "db_bytes": _file_bytes(db),
        "wal_bytes": sum(_file_bytes(Path(str(db) + sfx)) for sfx in WAL_SUFFIXES),
        "log_bytes": log_bytes,
        "exports_bytes": _tree_bytes(cfg_dir / "exports"),
        "backups_bytes": _tree_bytes(backups_dir),
    }
    parts["total_bytes"] = sum(parts.values())
    return {
        "at_ms": int((now if now is not None else time.time()) * 1000),
        "db_path": str(db),
        "backups_dir": str(backups_dir),
        **parts,
    }


def usage_store_path(config_dir: Path | str) -> Path:
    """The small JSON that remembers usage samples and the once-a-day warning flags."""
    return Path(config_dir) / "storage-usage.json"


def load_usage_store(path: Path | str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("samples", [])
            return data
    except (OSError, ValueError):
        pass
    return {"samples": []}


def record_sample(path: Path | str, db_bytes: int, *, now: float | None = None,
                  min_gap_s: int = SAMPLE_MIN_GAP_S, keep: int = SAMPLE_KEEP) -> dict[str, Any]:
    """Append one (epoch, bytes) sample unless the newest is younger than ``min_gap_s``.

    Returns the store as saved. A failure to write is logged, never raised: a usage sample is not
    worth interrupting the caller's loop for.
    """
    now = float(now if now is not None else time.time())
    store = load_usage_store(path)
    samples = [s for s in store.get("samples", []) if isinstance(s, (list, tuple)) and len(s) == 2]
    if samples and (now - float(samples[-1][0])) < min_gap_s:
        return store
    samples.append([round(now, 1), int(db_bytes)])
    samples = samples[-keep:]
    store["samples"] = samples
    try:
        Path(path).write_text(json.dumps(store, separators=(",", ":")), encoding="utf-8")
    except OSError as exc:
        logger.debug("could not persist the usage sample: %s", exc)
    return store


def growth_report(samples: Iterable[Iterable[float]], db_bytes: int, *,
                  now: float | None = None, retention_days: int = 0) -> dict[str, Any]:
    """Rate and forecast from the sample series. Pure.

    The honest forecast is not a straight line: a retention window deletes a row for every row
    written once it is full, so the size settles near ``daily rate × window``. Both numbers are
    reported — the current rate, and where the window says it ends.
    """
    now = float(now if now is not None else time.time())
    pts: list[tuple[float, float]] = []
    for entry in (samples or []):
        try:                                     # a 0-byte sample is an observation, not junk
            pts.append((float(entry[0]), float(entry[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if len(pts) < 2:
        return {"ok": False, "samples": len(pts),
                "note": "not enough history yet — samples are recorded while the engine runs"}
    pts = [p for p in pts if now - p[0] <= 7 * 86400]
    window = [p for p in pts if now - p[0] <= 86400]
    if len(window) < 2:
        window = pts[-2:]
    span_h = max((window[-1][0] - window[0][0]) / 3600.0, 1e-6)
    per_hour = (window[-1][1] - window[0][1]) / span_h
    per_day = per_hour * 24
    out: dict[str, Any] = {
        "ok": True, "samples": len(pts), "span_hours": round(span_h, 2),
        "bytes_per_hour": int(per_hour), "bytes_per_day": int(per_day),
        "bytes_per_week": int(per_day * 7), "current_bytes": int(db_bytes),
    }
    if retention_days > 0 and per_day > 0:
        out["steady_state_bytes"] = int(per_day * retention_days)
        out["note"] = (f"steady state ≈ {per_day * retention_days / 1e9:.2f} GB at a "
                       f"{retention_days} d window (a row is deleted for every row written)")
    elif per_day <= 0:
        out["note"] = "no net growth over the sampled window"
    else:
        out["note"] = "retention is off (0 d) — the file grows until you set a window"
    return out


def threshold_message(usage: dict[str, Any], settings: dict[str, Any]) -> Optional[dict[str, Any]]:
    """An alert-shaped message when the database passes the user's size budget, else None. Pure."""
    limit_mb = int(settings.get("max_db_mb") or 0)
    if limit_mb <= 0:
        return None
    db_bytes = int(usage.get("db_bytes") or 0) + int(usage.get("wal_bytes") or 0)
    if db_bytes <= limit_mb * 1_000_000:
        return None
    return {
        "kind": "storage_threshold", "severity": "warning", "symbol": "",
        "message": (f"the database is {db_bytes / 1e6:.0f} MB — over the {limit_mb} MB budget "
                    f"you set in Settings ▸ Storage"),
    }


# ══════════════════════════════════════════════════════════════
# The backup itself
# ══════════════════════════════════════════════════════════════

def _stamp(now: float | None = None) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(now if now is not None else time.time()))


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path, chunk: int = 262144) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _ensure_writable(target: Path) -> None:
    """Prove the target can be written before a 800 MB copy is attempted.

    This is the step that turns "\\\\server\\share that nobody is at the other end of" into a
    sentence the user can act on, instead of a partial folder and a stack trace.
    """
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".modflow-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise StorageError(f"cannot write to {target} — {exc.strerror or exc}") from exc


def _hot_copy(src_path: Path, dst_path: Path) -> None:
    """A consistent copy through SQLite's own online-backup API (WAL writers welcome).

    The copy inherits the source's WAL journal mode, which would leave ``-wal``/``-shm`` sidecars
    beside it and make the set a three-file thing that has to travel together. A backup is one
    file: the copy is checkpointed and switched back to the default rollback journal, and any
    sidecar left behind is removed — so what sits in the folder opens on its own.
    """
    src = sqlite3.connect(f"file:{src_path.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(dst_path))
        try:
            src.backup(dst)
            try:
                dst.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                dst.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.Error as exc:             # pragma: no cover - defensive
                logger.debug("could not normalise the backup's journal mode: %s", exc)
        finally:
            dst.close()
    finally:
        src.close()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(dst_path) + suffix)
        if sidecar.exists():
            try:
                sidecar.unlink()
            except OSError:                          # pragma: no cover - defensive
                pass


def _csv_cell(column: str, value: Any) -> Any:
    """One CSV cell, in the formats the rest of the world reads."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if column.endswith("_ms") and isinstance(value, (int, float)) and abs(value) > 1e11:
        return _iso(float(value) / 1000.0)          # epoch-ms -> ISO 8601 UTC
    if isinstance(value, float):
        return repr(round(value, 10))
    return value


def _write_csv(conn: sqlite3.Connection, table: str, dst_dir: Path, *,
               gzip_over_mb: float = 1.0) -> Optional[dict[str, Any]]:
    """One portable table: RFC 4180, UTF-8, gzipped once it is worth compressing."""
    try:
        cur = conn.execute(f'SELECT * FROM "{table}"')
    except sqlite3.OperationalError:
        return None                                  # table absent in an older database
    cols = [str(d[0]) for d in cur.description]
    tmp = dst_dir / f"{table}.csv"
    rows = 0
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\r\n")
        writer.writerow(cols)
        for row in cur:
            writer.writerow([_csv_cell(c, v) for c, v in zip(cols, row)])
            rows += 1
    if tmp.stat().st_size > gzip_over_mb * 1_000_000:
        gz = tmp.with_name(tmp.name + ".gz")
        with tmp.open("rb") as src_fh, gzip.open(gz, "wb") as out_fh:
            shutil.copyfileobj(src_fh, out_fh)
        tmp.unlink()
        tmp = gz
    return {"file": tmp.name, "rows": rows, "bytes": _file_bytes(tmp)}


def _write_tick_summary(conn: sqlite3.Connection, dst_dir: Path) -> Optional[dict[str, Any]]:
    """Per-instrument/day tick matrix — the small, portable answer to "what is in ticks"."""
    try:
        cur = conn.execute(
            "SELECT instrument, date(timestamp_ms / 1000, 'unixepoch') AS day, COUNT(*) AS ticks, "
            "MIN(timestamp_ms) AS first_ms, MAX(timestamp_ms) AS last_ms "
            "FROM ticks GROUP BY instrument, day ORDER BY day DESC, instrument")
    except sqlite3.OperationalError:
        return None
    cols = [str(d[0]) for d in cur.description]
    tmp = dst_dir / "ticks-summary.csv"
    rows = 0
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\r\n")
        writer.writerow(cols)
        for row in cur:
            writer.writerow([_csv_cell(c, v) for c, v in zip(cols, row)])
            rows += 1
    return {"file": tmp.name, "rows": rows, "bytes": _file_bytes(tmp)}


def _rotate(target: Path, keep: int) -> list[str]:
    """Delete the oldest sets beyond ``keep`` — only ever folders carrying our manifest."""
    sets = sorted((p for p in target.glob(BACKUP_PREFIX + "*")
                   if p.is_dir() and (p / MANIFEST_NAME).exists()), reverse=True)
    removed: list[str] = []
    for old in sets[keep:]:
        try:
            shutil.rmtree(old)
            removed.append(old.name)
        except OSError as exc:                       # pragma: no cover - defensive
            logger.warning("could not remove old backup %s: %s", old, exc)
    return removed


def run_backup(db_path: Path | str, target_dir: Path | str, *, fmt: str = "sqlite+csv",
               keep: int = 5, now: float | None = None,
               tables: Iterable[str] = CSV_TABLES) -> dict[str, Any]:
    """One backup set. Returns its manifest; raises :class:`StorageError` with the reason.

    Layout (every name sorts):

        <target>/modflow-backup-YYYYmmdd-HHMMSS/
            orderflow_data-YYYYmmdd-HHMMSS.db     the hot copy (sqlite)
            candles.csv[.gz] signals.csv …        the portable tables (csv)
            ticks-summary.csv
            manifest.json                         counts, bytes, sha256, integrity
    """
    fmt = str(fmt or "sqlite+csv").strip().lower()
    if fmt not in ("sqlite", "csv", "sqlite+csv"):
        raise StorageError(f"unknown backup format {fmt!r} — use sqlite, csv or sqlite+csv")
    src = Path(db_path)
    if not src.exists():
        raise StorageError(f"no database at {src} — start the engine once so it is created")
    target = Path(target_dir)
    _ensure_writable(target)

    stamp = _stamp(now)
    folder = target / f"{BACKUP_PREFIX}{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    started = time.time()
    manifest: dict[str, Any] = {
        "format": BACKUP_FORMAT_VERSION,
        "created_at": _iso(now if now is not None else time.time()),
        "app": {"name": "ModFlow OrderFlow Analysis Suite",
                "version": _app_version()},
        "source": {"db_path": str(src), "db_bytes": _file_bytes(src)},
        "database": None, "csv": [], "tables": {},
    }

    if "sqlite" in fmt:
        db_copy = folder / f"orderflow_data-{stamp}.db"
        _hot_copy(src, db_copy)
        check = sqlite3.connect(f"file:{db_copy.as_posix()}?mode=ro", uri=True)
        try:
            integrity = str(check.execute("PRAGMA quick_check").fetchone()[0])
        finally:
            check.close()
        manifest["database"] = {
            "file": db_copy.name, "bytes": _file_bytes(db_copy),
            "sha256": _sha256(db_copy), "integrity": integrity,
        }

    if "csv" in fmt:
        conn = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
        try:
            for table in tables:
                entry = _write_csv(conn, str(table), folder)
                if entry:
                    manifest["csv"].append({"table": str(table), **entry})
            summary = _write_tick_summary(conn, folder)
            if summary:
                manifest["csv"].append({"table": "ticks", "summary": True, **summary})
            for table in ("ticks", "candles", "signals"):
                try:
                    manifest["tables"][table] = int(
                        conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                except sqlite3.OperationalError:
                    continue
        finally:
            conn.close()

    manifest["duration_s"] = round(time.time() - started, 2)
    (folder / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["folder"] = str(folder)
    manifest["bytes"] = _tree_bytes(folder)
    manifest["removed"] = _rotate(target, max(1, int(keep)))
    logger.info("[storage] backup written: %s (%.1f MB, %s)", folder, manifest["bytes"] / 1e6, fmt)
    return manifest


def _app_version() -> str:
    try:
        from orderflow_system import __version__

        return str(__version__)
    except Exception:                                # pragma: no cover - defensive
        return "unknown"


def backup_age_seconds(entry: dict[str, Any], target_dir: Path | str, *,
                       now: float | None = None) -> float:
    """Seconds since a backup set was written — the manifest's stamp, else the folder's mtime.

    The scheduled job decides "is it due?" from this and nothing else, so restarting the app can
    never make it back up again immediately; a set with no readable stamp counts as due rather
    than as never.
    """
    now = float(now if now is not None else time.time())
    stamp = str((entry or {}).get("created_at") or "")
    if stamp:
        try:
            parsed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return max(0.0, now - parsed.timestamp())
        except ValueError:
            pass
    folder = Path(str((entry or {}).get("folder") or "")) if (entry or {}).get("folder") else None
    if folder is None:
        folder = Path(target_dir) / str((entry or {}).get("name") or "")
    try:
        return max(0.0, now - folder.stat().st_mtime)
    except OSError:
        return float("inf")


def list_backups(target_dir: Path | str) -> list[dict[str, Any]]:
    """Every backup set in the target, newest first (read from each manifest)."""
    target = Path(target_dir)
    if not target.exists():
        return []
    out: list[dict[str, Any]] = []
    for folder in sorted((p for p in target.glob(BACKUP_PREFIX + "*") if p.is_dir()), reverse=True):
        entry: dict[str, Any] = {"name": folder.name, "folder": str(folder),
                                 "bytes": _tree_bytes(folder), "created_at": "", "database": None,
                                 "files": len([p for p in folder.iterdir() if p.is_file()])}
        try:
            manifest = json.loads((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
            entry["created_at"] = str(manifest.get("created_at") or "")
            entry["database"] = manifest.get("database")
            entry["tables"] = manifest.get("tables") or {}
        except (OSError, ValueError):
            entry["created_at"] = _iso(folder.stat().st_mtime)
        out.append(entry)
    return out


# ══════════════════════════════════════════════════════════════
# Vacuum — reclaim pages, honestly guarded
# ══════════════════════════════════════════════════════════════

def vacuum_now(db_path: Path | str, *, allow_full: bool = True,
               min_free_factor: float = 2.2) -> dict[str, Any]:
    """Reclaim free pages. A full VACUUM needs room for a second copy and says so.

    With the engine running the writer stays live: the caller passes ``allow_full=False`` and the
    pass is an incremental one (the app already keeps ``auto_vacuum=INCREMENTAL`` set). With the
    engine stopped, a full VACUUM is the real answer — but only when the volume can hold the
    rewrite, otherwise it is refused with the arithmetic instead of a disk-full crash.
    """
    path = Path(db_path)
    if not path.exists():
        return {"ok": False, "mode": "refused", "error": f"no database at {path}"}
    size = _file_bytes(path)
    free = shutil.disk_usage(path.parent).free
    if allow_full and free < int(size * min_free_factor):
        return {"ok": False, "mode": "refused", "free_bytes": free, "bytes": size,
                "error": (f"a full VACUUM needs about {int(size * min_free_factor) / 1e6:.0f} MB "
                          f"free and this volume has {free / 1e6:.0f} MB — prune first or free "
                          f"space, or use the incremental pass")}
    conn = sqlite3.connect(str(path))
    try:
        if allow_full:
            conn.execute("VACUUM")
            mode = "full"
        else:
            conn.execute("PRAGMA incremental_vacuum")
            mode = "incremental"
    finally:
        conn.close()
    after = _file_bytes(path)
    return {"ok": True, "mode": mode, "bytes_before": size, "bytes_after": after,
            "reclaimed_bytes": max(0, size - after)}


# ══════════════════════════════════════════════════════════════
# The report (text + CSV, by email)
# ══════════════════════════════════════════════════════════════

def build_report(usage: dict[str, Any], growth: dict[str, Any], retention: dict[str, Any],
                 backups: list[dict[str, Any]], last_prune: Optional[dict[str, Any]]) -> tuple[str, str, str]:
    """(subject, plain-text body, CSV) — plain text and CSV because every mail client reads those."""
    def mb(n: Any) -> str:
        """Human-readable bytes — the unit every backup/report tool shows."""
        value = float(int(n or 0))
        if value >= 1e9:
            return f"{value / 1e9:.2f} GB"
        if value >= 1e6:
            return f"{value / 1e6:.1f} MB"
        if value >= 1e3:
            return f"{value / 1e3:.0f} KB"
        return f"{int(value)} B"
    created = _iso(time.time())
    lines = [
        "ModFlow OrderFlow Analysis Suite — storage report",
        f"generated: {created}",
        "",
        "Usage",
        f"  database (with WAL)   {mb(usage.get('db_bytes', 0) + usage.get('wal_bytes', 0))}",
        f"  logs                  {mb(usage.get('log_bytes', 0))}",
        f"  exports               {mb(usage.get('exports_bytes', 0))}",
        f"  backups               {mb(usage.get('backups_bytes', 0))} ({len(backups)} set(s))",
        f"  total                 {mb(usage.get('total_bytes', 0))}",
        "",
        "Growth",
    ]
    if growth.get("ok"):
        lines += [
            f"  measured              {mb(growth.get('bytes_per_hour', 0))}/h over "
            f"{growth.get('span_hours', 0)} h ({growth.get('samples', 0)} samples)",
            f"  forecast              +{mb(growth.get('bytes_per_day', 0))}/day, "
            f"+{mb(growth.get('bytes_per_week', 0))}/week",
        ]
        if growth.get("steady_state_bytes"):
            lines.append(f"  steady state          {mb(growth['steady_state_bytes'])} at this window")
    else:
        lines.append(f"  {growth.get('note', 'no history yet')}")
    lines += [
        "",
        "Retention",
        f"  window {retention.get('days', 0)} d · prune every {retention.get('prune_interval_hours', 0)} h "
        f"· session start {int(retention.get('session_start_hour', 0)):02d}:00 UTC",
    ]
    if last_prune:
        lines.append(f"  last prune: {_iso(int(last_prune.get('at_ms', 0)) / 1000)} — "
                     f"{last_prune.get('deleted', 0)} tick row(s), other={last_prune.get('other_deleted')}")
    else:
        lines.append("  last prune: never")
    lines += ["", f"Backups ({len(backups)} set(s) in {usage.get('backups_dir', '')})"]
    for entry in backups[:10]:
        db = entry.get("database") or {}
        bits = [entry.get("created_at") or entry.get("name", ""), entry.get("name", ""),
                mb(entry.get("bytes", 0))]
        if db:
            bits.append(f"db {mb(db.get('bytes', 0))} sha256 {str(db.get('sha256', ''))[:12]}…")
        lines.append("  " + "  ".join(str(b) for b in bits))
    subject = (f"[OrderFlow] storage report — {mb(usage.get('total_bytes', 0))} on disk, "
               f"{mb((usage.get('db_bytes', 0) + usage.get('wal_bytes', 0)))} database")
    rows = [
        ("generated", created),
        ("db_bytes", usage.get("db_bytes", 0)), ("wal_bytes", usage.get("wal_bytes", 0)),
        ("log_bytes", usage.get("log_bytes", 0)), ("exports_bytes", usage.get("exports_bytes", 0)),
        ("backups_bytes", usage.get("backups_bytes", 0)), ("total_bytes", usage.get("total_bytes", 0)),
        ("backups_sets", len(backups)),
    ]
    if growth.get("ok"):
        rows += [("bytes_per_hour", growth.get("bytes_per_hour", 0)),
                 ("bytes_per_day", growth.get("bytes_per_day", 0)),
                 ("steady_state_bytes", growth.get("steady_state_bytes", ""))]
    rows += [("retention_days", retention.get("days", 0)),
             ("last_backup", (backups[0].get("created_at") if backups else ""))]
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(("metric", "value"))
    for metric, value in rows:
        writer.writerow((metric, value))
    return subject, "\n".join(lines), buf.getvalue()


async def email_report(cfg: dict[str, Any], subject: str, body: str, *,
                       attachments: Optional[list[tuple[str, bytes, str]]] = None) -> dict[str, Any]:
    """Send the report through the alerts' own SMTP path (``atlas.notify``) — one implementation."""
    from orderflow_system.atlas.notify import build_notifiers

    hub = build_notifiers(telegram_cfg=cfg.get("telegram"), notify_cfg=cfg.get("notify"),
                          telegram_enabled=False)
    channel = hub.channels.get("email")
    if channel is None:
        return {"ok": False, "error": "email is not configured — fill it in Settings ▸ Backup & reports"}
    ok = bool(await channel.send_report(subject, body, attachments or []))
    return {"ok": ok, "error": "" if ok else (getattr(channel, "last_error", "") or "send failed")}


# ══════════════════════════════════════════════════════════════
# Headless entry point — a Task Scheduler job needs no window
# ══════════════════════════════════════════════════════════════

def _cli() -> int:                                   # pragma: no cover - exercised by hand
    import argparse

    from orderflow_system.desktop import config_store

    parser = argparse.ArgumentParser(prog="orderflow_system.desktop.storage",
                                     description="Back up or report on this installation's storage.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    backup = sub.add_parser("backup", help="write one backup set")
    backup.add_argument("--target", default="", help="folder, UNC share or drive (default: <config>/backups)")
    backup.add_argument("--format", default="", help="sqlite | csv | sqlite+csv")
    backup.add_argument("--keep", type=int, default=0, help="sets to keep in the target")
    report = sub.add_parser("report", help="print the storage report")
    report.add_argument("--print", action="store_true", dest="do_print")
    report.add_argument("--email", action="store_true", help="also send it to the configured address")
    args = parser.parse_args()

    cfg = config_store.load_config()
    settings = clamp_storage_settings(cfg)
    config_dir = config_store.config_dir()
    target = Path(args.target) if str(getattr(args, "target", "") or "") else resolved_target(settings, config_dir)

    if args.cmd == "backup":
        manifest = run_backup(config_store.db_path(), target,
                              fmt=str(getattr(args, "format", "") or settings["backup_format"]),
                              keep=int(getattr(args, "keep", 0) or settings["backup_keep"]))
        print(json.dumps({k: manifest[k] for k in ("folder", "bytes", "database", "removed")},
                         indent=2, default=str))
        return 0

    usage = usage_snapshot(config_store.db_path(), config_dir=config_dir, target=target)
    store = load_usage_store(usage_store_path(config_dir))
    days = int(cfg.get("data", {}).get("retention_days", 0) or 0)
    growth = growth_report(store.get("samples", []), usage["db_bytes"], retention_days=days)
    subject, body, csv_text = build_report(
        usage, growth,
        {"days": days, "prune_interval_hours": cfg.get("data", {}).get("prune_interval_hours", 0),
         "session_start_hour": cfg.get("data", {}).get("session_start_hour", 0)},
        list_backups(target), config_store.load_last_prune())
    if args.do_print:
        print(body)
    if args.email:
        import asyncio

        result = asyncio.run(email_report(cfg, subject, body, attachments=[
            ("storage-summary.csv", csv_text.encode("utf-8"), "text/csv")]))
        print(json.dumps(result))
    return 0


if __name__ == "__main__":                           # pragma: no cover
    raise SystemExit(_cli())
