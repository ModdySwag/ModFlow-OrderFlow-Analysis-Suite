"""Volume-profile persistence: one row per session, and the newest row is what a read returns.

Two defects this pins down (both found in the 2026-09-15 sweep, both fixed in
`orderflow_system/data/database.py`):

  * `insert_volume_profile` appended on every rebuild — the table has no unique key and the hourly
    rebuild re-inserts the same `session_date` — so a session accumulated a row per rebuild. The
    live install held 81 rows for 2026-09-14.
  * The read had no per-session de-duplication, and `days` was applied as a row LIMIT, so
    `get_volume_profiles(days=5)` returned five copies of one day and every merged level / bias
    built from "the last five sessions" was really built from one session repeated.
"""
import os

import pytest

from orderflow_system.data.database import Database
from orderflow_system.data.models import VolumeProfileResult


def _profile(day: str, poc: float) -> VolumeProfileResult:
    return VolumeProfileResult(
        session_date=day,
        poc=poc,
        vah=poc + 10.0,
        val=poc - 10.0,
        total_volume=100.0,
        lvn_levels=[poc - 5.0],
        shape="d_shape",
        poc_position_pct=0.5,
        volume_at_price={poc: 60.0, poc + 1.0: 40.0},
    )


@pytest.mark.asyncio
async def test_rebuild_replaces_the_session_and_read_returns_distinct_days(tmp_path):
    db_path = str(tmp_path / "profiles.db")
    db = Database(db_path)
    await db.connect()
    try:
        # three rebuilds of one session, then two further sessions
        await db.insert_volume_profile("BTCUSDT", _profile("2026-09-14", 100.0))
        await db.insert_volume_profile("BTCUSDT", _profile("2026-09-14", 101.0))
        await db.insert_volume_profile("BTCUSDT", _profile("2026-09-14", 102.0))
        await db.insert_volume_profile("BTCUSDT", _profile("2026-09-15", 110.0))
        await db.insert_volume_profile("BTCUSDT", _profile("2026-09-16", 120.0))

        cursor = await db._db.execute(
            "SELECT COUNT(*) FROM volume_profiles WHERE instrument = ? AND session_date = ?",
            ("BTCUSDT", "2026-09-14"),
        )
        row = await cursor.fetchone()
        assert row[0] == 1, f"three rebuilds of one session must leave one row, left {row[0]}"

        profiles = await db.get_volume_profiles("BTCUSDT", days=2)
        assert [p.session_date for p in profiles] == ["2026-09-15", "2026-09-16"], (
            "days must count distinct sessions, oldest first — got "
            f"{[p.session_date for p in profiles]}"
        )
        assert profiles[0].poc == 110.0, "the surviving row must be the newest rebuild"
    finally:
        await db.close()
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.asyncio
async def test_an_instrument_with_no_profiles_reads_empty(tmp_path):
    db_path = str(tmp_path / "empty.db")
    db = Database(db_path)
    await db.connect()
    try:
        assert await db.get_volume_profiles("NOSUCH", days=5) == []
    finally:
        await db.close()
        if os.path.exists(db_path):
            os.remove(db_path)
