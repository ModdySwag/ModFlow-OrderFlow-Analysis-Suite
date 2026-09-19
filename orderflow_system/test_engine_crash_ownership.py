"""MEM-A1-01 — a failed group member must not leave a live system behind.

The audit reproduced the mechanism: ``asyncio.gather`` propagates the first exception but
leaves the surviving members running, and once the gather future has raised, cancelling it
cannot reach them. One transient error (a locked DB at the first volume-profile rebuild, a
feed raising during start) could therefore orphan a fully live engine — feeds streaming,
database writing — while the UI showed "error" and the operator's next Start built a second
engine over it. These pins cover the three legs of the fix:

* the engine's concurrent group is owned: first failure cancels and awaits its siblings;
* a crashed run disposes the system (feeds down, DB closed, references dropped);
* a Start over an undisposed system disposes it first — it never runs two engines.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from orderflow_system.desktop import engine as eng


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []


class _RecHub:
    def __init__(self, rec: _Recorder) -> None:
        self._rec = rec
        self.history = self._History(rec)
        self.notifier = self._Notifier(rec)

    class _History:
        def __init__(self, rec: _Recorder) -> None:
            self._rec = rec

        async def stop(self) -> None:
            self._rec.calls.append("history.stop")

    class _Notifier:
        def __init__(self, rec: _Recorder) -> None:
            self._rec = rec

        async def stop(self) -> None:
            self._rec.calls.append("notifier.stop")

    async def stop_feeds(self) -> None:
        self._rec.calls.append("stop_feeds")


class _StubSystem:
    def __init__(self, rec: _Recorder, *, raise_on_start: bool = False) -> None:
        self._rec = rec
        self._raise = raise_on_start
        self._running = True
        self._atlas_hub = _RecHub(rec)

    async def stop(self) -> None:
        self._rec.calls.append("system.stop")
        self._running = False

    async def start(self) -> None:
        if self._raise:
            raise RuntimeError("periodic VP rebuild hit a locked database")
        await asyncio.Event().wait()


def test_a_failed_group_member_cancels_and_awaits_its_siblings():
    from orderflow_system.main import _run_owned

    finished: list[str] = []

    async def feed_forever():
        try:
            await asyncio.Event().wait()
        finally:
            finished.append("feed cancelled")

    async def periodic_raises():
        await asyncio.sleep(0.01)
        raise RuntimeError("transient database error")

    async def run():
        try:
            await _run_owned([feed_forever(), periodic_raises()])
        except RuntimeError as exc:
            assert "transient database error" in str(exc)
        else:                                        # pragma: no cover - the pin would be lying
            raise AssertionError("the group's failure must propagate")

    asyncio.run(run())
    assert finished == ["feed cancelled"], "the sibling must be cancelled and awaited, not orphaned"


def test_a_cancelled_group_cancels_its_siblings():
    from orderflow_system.main import _run_owned

    done: list[str] = []

    async def child():
        try:
            await asyncio.Event().wait()
        finally:
            done.append("child done")

    async def owner():
        await _run_owned([child(), child()])

    task = None

    async def run():
        nonlocal task
        task = asyncio.ensure_future(owner())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert task.cancelled() or task.done()
    assert sorted(done) == ["child done", "child done"], "cancelling the owner must reach the group"


def test_main_start_uses_the_owned_group_not_a_bare_gather():
    """Source-level pin: the engine's group runs through _run_owned (repo text-pin precedent)."""
    source = Path("orderflow_system/main.py").read_text(encoding="utf-8")
    start = source[source.index("        await _run_owned(["):source.index("        await _run_owned([") + 120]
    assert "_run_owned([*feed_tasks, self._periodic_tasks()])" in start
    assert "await asyncio.gather(\n            *feed_tasks" not in source


def test_a_crashed_run_disposes_the_system():
    from orderflow_system.dashboard import app as dashboard_app

    rec = _Recorder()
    system = _StubSystem(rec, raise_on_start=True)
    controller = eng.EngineController()
    controller._system = system
    controller._state = "running"
    dashboard_app.set_system(system)

    asyncio.run(controller._run(system))

    assert controller._state == "error"
    assert controller._system is None, "the orphaned system reference must be dropped"
    assert dashboard_app.get_system() is None
    assert rec.calls[:2] == ["stop_feeds", "history.stop"], rec.calls
    assert "notifier.stop" in rec.calls and "system.stop" in rec.calls, rec.calls
    assert system._running is False


def test_start_disposes_an_undisposed_system_first(monkeypatch):
    rec = _Recorder()
    system = _StubSystem(rec)
    controller = eng.EngineController()
    controller._system = system            # left behind by a crash without teardown
    controller._state = "error"
    # never touch the process-wide settings from a test: the disposal happens before the
    # config is even read, so the instrument selection is stubbed out entirely
    monkeypatch.setattr(eng, "apply_settings", lambda cfg: None)
    monkeypatch.setattr(eng, "select_instruments", lambda cfg: ([], []))

    out = asyncio.run(controller.start({"instruments": [], "data_source": "bybit"}))

    assert out["ok"] is False, out
    assert controller._system is None
    assert "stop_feeds" in rec.calls and "system.stop" in rec.calls, rec.calls
    assert system._running is False


def test_engine_stop_disposes_every_service_and_reference():
    """G-01: stop() runs the single dispose path and clears every reference it owns."""
    from orderflow_system.dashboard import app as dashboard_app

    rec = _Recorder()
    system = _StubSystem(rec)
    controller = eng.EngineController()
    controller._system = system
    controller._state = "running"
    controller._symbols = ["BTCUSDT"]
    dashboard_app.set_system(system)

    out = asyncio.run(controller.stop())

    assert out == {"ok": True, "state": "stopped"}
    assert rec.calls[0] == "stop_feeds" and "history.stop" in rec.calls
    assert "notifier.stop" in rec.calls and "system.stop" in rec.calls, rec.calls
    assert controller._task is None
    assert controller._system is None
    assert controller._symbols == []
    assert dashboard_app.get_system() is None


def test_engine_restart_disposes_once_per_cycle():
    """G-01: two restart() cycles dispose twice (the A-01 orphaned-flusher pin)."""
    rec = _Recorder()
    system = _StubSystem(rec)
    controller = eng.EngineController()

    async def fake_start(cfg=None):
        controller._system = system
        controller._state = "running"
        return {"ok": True, "state": "running"}

    controller.start = fake_start                     # type: ignore[assignment]

    async def run():
        for _ in range(2):
            controller._system = system
            controller._state = "running"
            await controller.restart()

    asyncio.run(run())

    assert rec.calls.count("history.stop") == 2, rec.calls
    assert rec.calls.count("stop_feeds") == 2, rec.calls
    assert rec.calls.count("system.stop") == 2, rec.calls


def test_stop_drains_and_closes_the_database_even_when_a_feed_hangs():
    """MEM-A1-07: a stop cancelled mid-cleanup still flushes the last batch and closes the DB."""
    from orderflow_system.data.database import Database
    from orderflow_system.main import OrderflowSystem

    events: list[str] = []

    class _HangingFeed:
        async def stop(self) -> None:
            await asyncio.sleep(30)

    class _RecordingDB:
        async def insert_ticks_batch(self, symbol, batch):
            events.append(f"drain:{symbol}:{len(list(batch))}")

        async def close(self):
            events.append("db.close")

    def build(system_db):
        system = object.__new__(OrderflowSystem)
        system._running = True
        system.feed = _HangingFeed()
        system.mt5_feed = None
        system.alpaca_feed = None
        system.nt_feed = None
        system._tick_buffers = {"BTCUSDT": [1, 2, 3]}
        system._db_write_failures = 0
        system.db = system_db
        return system

    async def run_cancelled_stop():
        system = build(_RecordingDB())
        try:
            await asyncio.wait_for(system.stop(), timeout=0.2)
        except asyncio.TimeoutError:
            pass                                       # the engine's 15 s watchdog, made short
        assert events == ["drain:BTCUSDT:3", "db.close"], events

    asyncio.run(run_cancelled_stop())

    # and with the real handle: the store really is closed after the cancelled stop
    async def run_with_real_db():
        db = Database(":memory:")
        await db.connect()
        system = build(db)
        system._tick_buffers = {"BTCUSDT": []}
        try:
            await asyncio.wait_for(system.stop(), timeout=0.2)
        except asyncio.TimeoutError:
            pass
        assert db._db is None, "a cancelled stop must still close the database handle"

    asyncio.run(run_with_real_db())
