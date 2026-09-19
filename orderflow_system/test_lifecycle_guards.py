"""Lifecycle guards from the v0.1b audit (A-01 / A-02 / A-03 / A-05 / A-06 / A-07).

Each test pins a mechanism the audit proved broken: a stopping system must not lose its buffered
ticks, an MT5 probe must never shut down a session the live feed owns, a closed database handle
must read as stopped, and the launcher's exit path must tolerate a dead control port.
"""
from __future__ import annotations

import asyncio

from orderflow_system.data.database import Database


class _RecordingDB:
    """A stand-in database that records what a drain hands it."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, list]] = []

    async def insert_ticks_batch(self, symbol, batch):
        self.rows.append((symbol, list(batch)))


def test_stop_drains_the_buffered_ticks():
    from orderflow_system.main import OrderflowSystem

    system = object.__new__(OrderflowSystem)     # buffers only: no feeds, no running loop
    system._tick_buffers = {"NAS100USDT": [1, 2, 3], "EMPTY": []}
    system._db_write_failures = 0
    system.db = _RecordingDB()

    asyncio.run(system._drain_tick_buffers())

    assert system.db.rows == [("NAS100USDT", [1, 2, 3])], "the final batch must reach the database"
    assert system._tick_buffers["NAS100USDT"] == []


def test_an_mt5_probe_does_not_shut_down_a_session_the_feed_owns(monkeypatch):
    from orderflow_system.desktop import engine as eng

    class _FakeMT5:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def shutdown(self):
            self.calls.append("shutdown")

    class _LiveFeed:
        _initialized = True

    class _LiveSystem:
        mt5_feed = _LiveFeed()

    class _LiveEngine:
        system = _LiveSystem()          # `engine.system` is read as an attribute, as in api.py

    fake = _FakeMT5()
    monkeypatch.setattr(eng, "engine", _LiveEngine())
    eng._mt5_shutdown_unless_owned(fake)
    assert fake.calls == [], "the probe must leave the live feed's session alone"

    class _IdleEngine:
        system = None

    monkeypatch.setattr(eng, "engine", _IdleEngine())
    eng._mt5_shutdown_unless_owned(fake)
    assert fake.calls == ["shutdown"], "with no live feed the probe still leaves nothing behind"


def test_a_closed_database_handle_reads_as_stopped():
    db = Database(":memory:")

    async def run():
        await db.connect()
        await db.close()
        assert db._db is None, "a closed handle must not satisfy the `if self._db:` guards"
        await db.close()                     # idempotent: a second close is not an error

    asyncio.run(run())


def test_the_exit_shutdown_never_raises_on_a_dead_port():
    from orderflow_system.desktop.launcher import _shutdown_engine

    _shutdown_engine(9, timeout=0.5)         # nothing listens on 9 — best effort, never raises
