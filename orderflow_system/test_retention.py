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
