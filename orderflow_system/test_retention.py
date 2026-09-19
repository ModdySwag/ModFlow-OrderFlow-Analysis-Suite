"""P3-2 (R5): prune_ticks, the storage snapshot, the vacuum path and the routes."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from orderflow_system.data.database import Database
from orderflow_system.data.models import Side, Tick

NOW_MS = int(time.time() * 1000)
DAY = 86_400_000


def _tick(ts_ms):
    return Tick(timestamp_ms=ts_ms, price=100.0, size=1.0, side=Side.BUY)


def test_prune_snapshot_and_vacuum():
    asyncio.run(_scenario())


async def _scenario():
    with tempfile.TemporaryDirectory() as td:
        db = Database(str(Path(td) / "t.db"))
        await db.connect()
        old = NOW_MS - 40 * DAY
        new = NOW_MS - 1 * DAY
        for inst in ("BTCUSDT", "ETHUSDT"):
            await db.insert_ticks_batch(inst, [_tick(old), _tick(old + 1000), _tick(new), _tick(new + 1000)])

        snap = await db.storage_snapshot()
        assert snap["tables"]["ticks"] == 8, snap["tables"]
        assert snap["bytes"] > 0 and snap["ticks"]["newest_ms"] > snap["ticks"]["oldest_ms"]

        deleted = await db.prune_ticks(NOW_MS - 30 * DAY, ["BTCUSDT", "ETHUSDT"])
        assert deleted == 4, deleted
        snap2 = await db.storage_snapshot()
        assert snap2["tables"]["ticks"] == 4 and snap2["ticks"]["oldest_ms"] > old

        # nothing left to delete: a second pass is a clean zero, not an error
        assert await db.prune_ticks(NOW_MS - 30 * DAY, ["BTCUSDT", "ETHUSDT"]) == 0

        mode = await db.ensure_incremental_autovacuum()
        assert mode in ("converted", "already"), mode
        cur = await db._db.execute("PRAGMA auto_vacuum")
        row = await cur.fetchone()
        assert int(row[0]) == 2                       # incremental from here on
        await db.vacuum_incremental()                 # bounded, and never raises out
        await db.close()

        # a stopped handle answers honestly instead of guessing
        db2 = Database(str(Path(td) / "t.db"))
        snap3 = await db2.storage_snapshot()
        assert snap3["bytes"] > 0 and snap3["tables"] == {}


def test_storage_routes_exist():
    from orderflow_system.desktop.api import router

    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/api/control/storage" in paths
    assert "/api/control/storage/prune" in paths


def test_data_config_defaults_and_clamps():
    """The `data` block defaults exist, and the pure clamp turns junk into them."""
    from orderflow_system.desktop import config_store
    from orderflow_system.desktop.engine import clamp_data_settings

    block = (config_store.default_config().get("data") or {})
    assert block.get("session_start_hour") == 0
    assert block.get("retention_days") == 7
    assert block.get("prune_interval_hours") == 6

    assert clamp_data_settings({}) == (0, 7, 6)
    # range-clamped, not defaulted: 99 -> 23, -5 -> 0 (keep all: never delete on bad input),
    # "x" -> the default cadence
    assert clamp_data_settings({"data": {"session_start_hour": 99, "retention_days": -5,
                                         "prune_interval_hours": "x"}}) == (23, 0, 6)
    assert clamp_data_settings({"data": {"session_start_hour": 6, "retention_days": 7,
                                         "prune_interval_hours": 12}}) == (6, 7, 12)
    assert clamp_data_settings({"data": {"retention_days": 0}}) == (0, 0, 6)   # 0 is legal: keep all
# ── §93 storage follow-ups: the stopped-engine read and a prune that survives a restart ──────


def _build_db(path, batches):
    """Write tick batches into a real database file, then close every handle."""
    from orderflow_system.data.database import Database

    async def run():
        db = Database(str(path))
        await db.connect()
        for instrument, ticks in batches.items():
            await db.insert_ticks_batch(instrument, ticks)
        await db.close()

    asyncio.run(run())


def test_the_offline_snapshot_reads_the_file_with_no_engine(tmp_path):
    """A stopped app still owns a file with a size, page accounting and a tick span."""
    from orderflow_system.data.database import readonly_snapshot

    path = tmp_path / "t.db"
    _build_db(path, {
        "BTCUSDT": [_tick(NOW_MS - 5_000), _tick(NOW_MS - 4_000)],
        "ETHUSDT": [_tick(NOW_MS - 3_000)],
    })

    snap = readonly_snapshot(str(path))
    assert snap["bytes"] > 0
    assert snap["page_size"] == 4096 and snap["page_count"] > 0
    assert snap["reclaimable_bytes"] == snap["freelist_pages"] * snap["page_size"]
    assert [s["instrument"] for s in snap["spans"]] == ["BTCUSDT", "ETHUSDT"]
    assert snap["ticks"] == {"oldest_ms": NOW_MS - 5_000, "newest_ms": NOW_MS - 3_000}

    missing = readonly_snapshot(str(tmp_path / "nope.db"))
    assert missing["bytes"] == 0 and missing["spans"] == [] and missing["ticks"]["oldest_ms"] == 0

    foreign = tmp_path / "foreign.db"
    foreign.write_bytes(b"not a database at all" * 100)
    shrug = readonly_snapshot(str(foreign))
    assert shrug["bytes"] > 0 and shrug["spans"] == [] and shrug["ticks"]["newest_ms"] == 0


def test_the_storage_route_answers_with_the_engine_stopped(tmp_path, monkeypatch):
    """The panel's data: real sizes, a real span, retention from the file, the last prune kept."""
    from orderflow_system.desktop import api as api_mod
    from orderflow_system.desktop import config_store
    from orderflow_system.desktop import engine as engine_mod

    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    _build_db(config_store.db_path(), {"BTCUSDT": [_tick(NOW_MS - 9_000), _tick(NOW_MS - 8_000)]})
    config_store.save_last_prune({"at_ms": NOW_MS - 60_000, "retention_days": 7,
                                  "prune_interval_hours": 6, "deleted": 12})

    monkeypatch.setattr(engine_mod.engine, "_system", None, raising=False)
    out = asyncio.run(api_mod.get_storage(refresh=1))

    assert out["engine_running"] is False
    assert out["bytes"] > 0 and out["tables"] == {}
    assert out["ticks"]["newest_ms"] == NOW_MS - 8_000
    assert out["retention"]["days"] == 7
    assert out["last_prune"]["deleted"] == 12, "a restart must not erase the prune record"


def test_the_prune_summary_round_trips(tmp_path, monkeypatch):
    from orderflow_system.desktop import config_store

    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    store = config_store
    assert store.load_last_prune() is None, "no prune has run on a fresh profile"
    store.save_last_prune({"at_ms": 123, "deleted": 7, "retention_days": 7})
    assert store.storage_state_path().is_file()
    assert store.load_last_prune()["deleted"] == 7
def test_retention_covers_the_other_tables_too(tmp_path):
    """Only `ticks` was pruned: candles, signals, profiles and the atlas event log grew forever."""
    from orderflow_system.data.database import Database, readonly_snapshot  # noqa: F401

    async def run():
        db = Database(str(tmp_path / "t.db"))
        await db.connect()
        old, new = NOW_MS - 40 * DAY, NOW_MS - 1 * DAY
        for ts in (old, new):
            await db._db.execute(
                "INSERT INTO candles (instrument, timestamp_ms, timeframe, open, high, low, close, "
                "volume, buy_volume, sell_volume, delta, tick_count, footprint_json) "
                "VALUES ('BTCUSDT', ?, '1m', 1, 1, 1, 1, 1, 1, 1, 1, 1, '{}')", (ts,))
            await db._db.execute(
                "INSERT INTO signals (instrument, timestamp_ms, signal_type, direction, strength) "
                "VALUES ('BTCUSDT', ?, 'x', 'long', 1)", (ts,))
        await db._db.execute(
            "INSERT INTO volume_profiles (instrument, session_date, poc, vah, val, total_volume) "
            "VALUES ('BTCUSDT', '2020-01-01', 1, 2, 0, 3)")
        await db._db.commit()

        out = await db.prune_other_tables(NOW_MS - 30 * DAY)
        keep = await (await db._db.execute("SELECT COUNT(*) FROM candles")).fetchone()
        await db.close()
        return out, keep[0]

    out, candles_left = asyncio.run(run())
    assert out["candles"] == 1 and out["signals"] == 1 and out["volume_profiles"] == 1
    assert out["atlas_events"] == -1, "a table this database does not own reports -1, never raises"
    assert candles_left == 1, "the row inside the window must survive"


def test_the_vacuum_conversion_refuses_without_free_space(tmp_path, monkeypatch):
    """The conversion is a FULL vacuum; it must not start when the volume cannot hold a second
    copy of the file (reported as 'no-space', retried by the next pass)."""
    import shutil as _shutil
    import types

    from orderflow_system.data.database import Database

    async def run():
        db = Database(str(tmp_path / "t.db"))
        await db.connect()
        await db.insert_ticks_batch("BTCUSDT", [_tick(NOW_MS)])
        mode = await db.ensure_incremental_autovacuum()
        await db.close()
        return mode

    monkeypatch.setattr(_shutil, "disk_usage", lambda _p: types.SimpleNamespace(free=1))
    assert asyncio.run(run()) == "no-space"


# ── MEM-A2-09 / MEM-A2-10: the journal joins retention; the WAL result is checked ────────────
def test_retention_covers_the_trade_journal():
    import sqlite3  # noqa: F401  (the scenario uses the raw handle through Database)

    async def scenario():
        with tempfile.TemporaryDirectory() as td:
            db = Database(str(Path(td) / "t.db"))
            await db.connect()
            old = NOW_MS - 40 * DAY
            new = NOW_MS - 1 * DAY
            for entry, exit_ in ((old, old), (new, new), (None, None)):
                await db._db.execute(
                    "INSERT INTO trade_journal (instrument, direction, entry_time_ms, exit_time_ms) "
                    "VALUES (?, ?, ?, ?)", ("BTCUSDT", "buy", entry, exit_))
            await db._db.commit()

            out = await db.prune_other_tables(NOW_MS - 30 * DAY)
            assert out["trade_journal"] == 1, out
            cur = await db._db.execute("SELECT COUNT(*) FROM trade_journal")
            assert int((await cur.fetchone())[0]) == 2, "the recent and the undated rows survive"
            await db.close()

    asyncio.run(scenario())


def test_the_event_history_takes_the_configured_window():
    from orderflow_system.atlas.history import EventHistory
    from orderflow_system.atlas.hub import FeatureHub
    from orderflow_system.atlas.services import attach_services

    assert EventHistory(":memory:").retention_days == 7.0
    assert EventHistory(":memory:", retention_days=1).retention_days == 1.0

    hub = FeatureHub({})
    attach_services(hub, {"history": {"enabled": False, "retention_days": 3}})
    assert hub.history is not None and hub.history.retention_days == 3.0, \
        "the configured window reaches the event log, not its own default"


def test_the_wal_checkpoint_reports_the_pragmas_own_answer():
    import sqlite3

    async def scenario():
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.db"
            db = Database(str(path))
            await db.connect()
            await db.insert_ticks_batch("BTCUSDT", [_tick(NOW_MS) for _ in range(100)])

            reader = sqlite3.connect(str(path))
            reader.execute("BEGIN")
            reader.execute("SELECT COUNT(*) FROM ticks").fetchone()
            busy = await db.checkpoint_passive()
            cur = await db._db.execute("PRAGMA wal_checkpoint(PASSIVE)")
            row = await cur.fetchone()
            assert busy == (not int(row[0])), "the helper reports the pragma's own busy flag"
            reader.rollback()
            reader.close()

            await db.vacuum_incremental()
            wal = path.with_name(path.name + "-wal")
            assert (not wal.exists()) or wal.stat().st_size == 0, \
                "a quiet truncate leaves an empty WAL, not a growing one"
            await db.close()

    asyncio.run(scenario())


def test_the_periodic_runner_prunes_on_its_interval_and_survives_a_failure(monkeypatch):
    """G-05: the runner prunes when due (re-clamping each pass) and a failing prune does not end it."""
    from orderflow_system.main import OrderflowSystem
    from orderflow_system.desktop import config_store as _cs

    class _Sentinel(Exception):
        pass

    passes = {"n": 0}
    prunes = []

    system = object.__new__(OrderflowSystem)
    system._running = True
    system._tick_buffers = {}
    system.pipelines = {}
    system._db_write_failures = 0
    system._recent_ticks = {}
    system._recent_ticks_max = 10

    class _DB:
        async def insert_ticks_batch(self, symbol, batch):
            return None

    class _WS:
        client_count = 0

        async def broadcast_stats(self, payload):
            return None

        async def broadcast(self, channel, payload, symbol=""):
            return None

    async def _prune():
        prunes.append(passes["n"])
        if len(prunes) == 1:
            raise RuntimeError("prune failed once")            # the loop must survive this
        return {"skipped": "test"}

    async def _noop():
        return None

    system.db = _DB()
    system.data_source = type("_DS", (), {"value": "bybit"})()
    system.ws_manager = _WS()
    system._prune_storage = _prune
    system._storage_tick = _noop
    system._calendar_tick = _noop

    monkeypatch.setattr(_cs, "load_config",
                        lambda: {"data": {"prune_interval_hours": 1, "session_start_hour": 0,
                                          "retention_days": 7}})

    real_sleep = asyncio.sleep
    sleeps = {"n": 0}
    # the loop clock must advance past the (minimum 1 h) prune interval, or "due" never happens:
    # each read moves an hour, so every pass is due — exactly what the pin wants to observe.
    clock = {"t": 10_000.0}

    class _Loop:
        def time(self):
            clock["t"] += 3_700.0
            return clock["t"]

    monkeypatch.setattr(asyncio, "get_event_loop", lambda: _Loop())

    async def fake_sleep(seconds):
        sleeps["n"] += 1
        passes["n"] = sleeps["n"]
        if sleeps["n"] >= 3:                                   # two body passes, then stop
            raise _Sentinel()
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    try:
        asyncio.run(system._periodic_tasks())
    except _Sentinel:
        pass
    finally:
        monkeypatch.undo()

    assert len(prunes) >= 2, f"the prune ran on its interval each pass: {prunes}"
    assert prunes[0] == 1 and prunes[1] == 2, "once per pass, not once per tick"
