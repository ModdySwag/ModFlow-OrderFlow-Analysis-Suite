"""Signal-machine state that must stay bounded, and the loop-latency budget for /systems.

MEM-A1-04: `SignalAggregator._watched_levels` grew for the whole session with no removal path —
the radar registers a level per closed bar/node/VWAP band and the aggregator kept every one
(~100 B each, and a linear scan per absorption). The list is now capped per instrument, oldest
first, the same shape `patterns.remember_signal` uses for its sibling histories.

MEM-A1-10: the Systems board's own poll must never stall the loop it reports on — the blocking
sqlite probes and directory walks run off the loop (`asyncio.to_thread` at the route).
"""

from __future__ import annotations

import asyncio
import threading
import time

from orderflow_system.data.models import Side
from orderflow_system.signals.aggregator import MAX_WATCHED_LEVELS, SignalAggregator
from orderflow_system.signals.profile_framing import LevelType, QualifiedLevel


def _level(price: float) -> QualifiedLevel:
    return QualifiedLevel(price=price, level_type=LevelType.NODE, direction=Side.BUY,
                          strength=80.0, notes="radar:node")


def test_watched_levels_stay_bounded_per_instrument():
    agg = SignalAggregator()
    for i in range(1000):
        agg.set_watching("BTCUSDT", _level(100.0 + i * 0.5), Side.BUY)
    kept = agg._watched_levels["BTCUSDT"]
    assert len(kept) == MAX_WATCHED_LEVELS, f"{len(kept)} levels kept — the cap is the contract"
    assert kept[-1].price > kept[0].price, "oldest dropped first: the newest levels survive"

    # a second instrument has its own budget, and near-duplicates are still merged, not capped
    agg.set_watching("ETHUSDT", _level(2000.0), Side.BUY)
    agg.set_watching("ETHUSDT", _level(2000.0001), Side.BUY)
    assert len(agg._watched_levels["ETHUSDT"]) == 1
    assert len(agg._watched_levels["BTCUSDT"]) == MAX_WATCHED_LEVELS


def test_a_signal_persistence_error_never_escapes_the_candle_close_path():
    """MEM-A1-09: the tick path was hardened; the signal path must be too.

    `_handle_signal` runs inside the candle-close callback and the orderbook frame handler —
    a transient "database is locked" there used to propagate into the feed loop.
    """
    import sqlite3

    from orderflow_system.data.models import Signal, SignalType
    from orderflow_system.main import OrderflowSystem

    class _LockedDB:
        async def insert_signal(self, symbol, signal):
            raise sqlite3.OperationalError("database is locked")

    class _Pipeline:
        current_price = 100.0
        profile_framing = type("PF", (), {"current_bias": None})()
        candle_builder = type("CB", (), {"get_recent_candles": staticmethod(lambda n: [])})()

    class _Aggregator:
        def process_signal(self, **kwargs):
            return None

    system = object.__new__(OrderflowSystem)
    system._db_write_failures = 0
    system._recent_signals = {}
    system._recent_signals_max = 50
    system.db = _LockedDB()
    system.aggregator = _Aggregator()
    system.pipelines = {"BTCUSDT": _Pipeline()}

    signal = Signal(timestamp_ms=1_700_000_000_000, signal_type=SignalType.ABSORPTION,
                    direction=Side.BUY, price_level=100.0, strength=80.0)
    asyncio.run(system._on_candle_signals("BTCUSDT", [signal]))

    assert system._db_write_failures == 1, "the failure is counted, with the tick path's pattern"
    assert list(system._recent_signals["BTCUSDT"]) == [signal], "the call path completed"


def test_the_systems_route_never_blocks_the_loop(monkeypatch):
    """The board's poll runs the blocking report off the loop; a ticker keeps ticking."""
    from orderflow_system.desktop import api, engine as engine_mod

    seen: dict = {}
    ticks = {"n": 0}

    def blocking_report():
        seen["worker"] = threading.get_ident()
        time.sleep(0.25)                    # the sqlite probe + dir walks, made unmissable
        return {"ok": True, "rows": []}

    monkeypatch.setattr(engine_mod, "systems_report", blocking_report)

    async def scenario():
        seen["main"] = threading.get_ident()

        async def ticker():
            while True:
                ticks["n"] += 1
                await asyncio.sleep(0.01)

        task = asyncio.create_task(ticker())
        try:
            out = await api.systems()
        finally:
            task.cancel()
        return out

    out = asyncio.run(scenario())
    assert out == {"ok": True, "rows": []}
    assert seen["worker"] != seen["main"], "the blocking report must not run on the loop thread"
    assert ticks["n"] >= 15, f"the loop was stalled while the report worked ({ticks['n']} ticks)"


# ── MEM-A2-11: the stopped-engine storage probe runs off the loop too ────────────────────────
def test_the_storage_route_never_blocks_the_loop_when_the_engine_is_stopped(monkeypatch):
    from orderflow_system.data import database as db_mod
    from orderflow_system.desktop import api, engine as engine_mod

    seen: dict = {}
    ticks = {"n": 0}

    monkeypatch.setattr(engine_mod.engine, "_system", None)     # stopped: the file answers
    monkeypatch.setattr(api.config_store, "load_config",
                        lambda: {"data": {}, "storage": {}, "notify": {}})

    def slow_snapshot(path):
        seen["worker"] = threading.get_ident()
        time.sleep(0.25)
        return {"bytes": 1, "wal_bytes": 0, "tables": {}, "ticks": {}}

    monkeypatch.setattr(db_mod, "readonly_snapshot", slow_snapshot)

    endpoint = next(route.endpoint for route in api.router.routes
                    if getattr(route, "path", "") == "/api/control/storage")

    async def scenario():
        seen["main"] = threading.get_ident()

        async def ticker():
            while True:
                ticks["n"] += 1
                await asyncio.sleep(0.01)

        task = asyncio.create_task(ticker())
        try:
            return await endpoint()
        finally:
            task.cancel()

    out = asyncio.run(scenario())
    assert isinstance(out, dict)
    assert seen.get("worker") not in (None, seen["main"]), "the snapshot ran on the loop thread"
    assert ticks["n"] >= 15, f"the loop was stalled by the covering-index scan ({ticks['n']} ticks)"
