"""Live-bridge tests — audit P1 / plan Phase 1 (T5, T6, T8-T13).

Runs fully offline: synthetic ticks in, engine state and REST payloads out.
A stub DB + stub WS manager are injected, so no SQLite file, no network, no Telegram.
"""

from __future__ import annotations

import asyncio

import pytest

from orderflow_system.config import settings as runtime_settings
from orderflow_system.config.settings import get_btcusd_config
from orderflow_system.data.models import Side, Tick


# ──────────────────────────────────────────────
# fakes
# ──────────────────────────────────────────────

class FakeDB:
    def __init__(self):
        self.candles = []
        self.signals = []
        self.tick_batches = []

    async def connect(self):
        pass

    async def insert_candle(self, symbol, timeframe, candle):
        self.candles.append((symbol, timeframe, candle))

    async def insert_ticks_batch(self, symbol, ticks):
        self.tick_batches.append((symbol, list(ticks)))

    async def insert_signal(self, symbol, signal):
        self.signals.append((symbol, signal))

    async def get_candles(self, *a, **k):
        return []

    async def insert_volume_profile(self, *a, **k):
        pass


class FakeWS:
    def __init__(self):
        self.candles = []
        self.deltas = []
        self.ticks = []

    async def broadcast_tick(self, symbol, price, size, side):
        self.ticks.append((symbol, price, size, side))

    async def broadcast_candle(self, symbol, data):
        self.candles.append((symbol, data))

    async def broadcast_delta(self, symbol, data):
        self.deltas.append((symbol, data))

    async def broadcast(self, *a, **k):
        pass

    async def broadcast_orderbook(self, *a, **k):
        pass

    async def broadcast_signal(self, *a, **k):
        pass

    async def broadcast_trade_state(self, *a, **k):
        pass

    async def broadcast_stats(self, *a, **k):
        pass

    async def broadcast_volume_profile(self, *a, **k):
        pass

    async def broadcast_bias(self, *a, **k):
        pass

    @property
    def client_count(self):
        return 0


class _NoTelegram:
    async def initialize(self):
        pass

    async def send_signal_alert(self, *a, **k):
        pass


@pytest.fixture()
def system(tmp_path):
    """An OrderflowSystem with one crypto instrument and stubbed IO."""
    runtime_settings.DB_PATH = str(tmp_path / "orderflow-test.db")
    from orderflow_system.main import OrderflowSystem

    obj = OrderflowSystem(instruments=[get_btcusd_config()])
    obj.db = FakeDB()
    obj.ws_manager = FakeWS()
    obj.telegram = _NoTelegram()
    return obj


def _make_ticks(start_ms: int = 1_700_000_000_000, seconds: int = 130, step_ms: int = 1_000):
    """Ticks spanning two+ minutes so at least two candles close."""
    ticks = []
    for i in range(0, seconds * 1000, step_ms):
        ticks.append(Tick(
            timestamp_ms=start_ms + i,
            price=20_000.0 + (i // 1000) * 0.5,
            size=1.0,
            side=Side.BUY if (i // 1000) % 3 else Side.SELL,
        ))
    return ticks


# ──────────────────────────────────────────────
# T5 — bounded tick ring buffer
# ──────────────────────────────────────────────

def test_recent_ticks_ring_buffer_is_bounded_and_ordered(system):
    symbol = next(iter(system.pipelines))
    ticks = _make_ticks(seconds=600)  # 600 ticks > the 500 cap

    async def feed():
        for t in ticks:
            await system._on_tick(symbol, t)

    asyncio.run(feed())

    buf = system.recent_ticks(symbol, count=10_000)
    assert len(buf) == system._recent_ticks_max == 500
    # newest last, oldest dropped
    assert buf[-1].timestamp_ms == ticks[-1].timestamp_ms
    assert buf[0].timestamp_ms == ticks[-500].timestamp_ms
    assert system.recent_ticks("NOPE") == []
    assert system.recent_ticks(symbol, count=0) == []


# ──────────────────────────────────────────────
# T6 — candle-close wiring: analytics once, persist + broadcast once
# ──────────────────────────────────────────────

def test_candle_close_persists_broadcasts_and_runs_analytics_once(system):
    symbol = next(iter(system.pipelines))
    pipeline = system.pipelines[symbol]

    calls = {"analytics": 0, "delta": 0}
    # Patch the callback the candle builder actually holds (patching the pipeline
    # method would miss the bound reference captured at construction time).
    original_close = pipeline.candle_builder.on_candle_close

    async def counting_close(candle):
        calls["analytics"] += 1
        return await original_close(candle)

    pipeline.candle_builder.on_candle_close = counting_close
    original_compute = pipeline.delta_engine.compute_from_candle

    def counting_compute(candle):
        calls["delta"] += 1
        return original_compute(candle)

    pipeline.delta_engine.compute_from_candle = counting_compute

    async def feed():
        for t in _make_ticks():
            await system._on_tick(symbol, t)

    asyncio.run(feed())

    closed = len(system.pipelines[symbol].candle_builder.history)
    assert closed >= 2, "the synthetic ticks should close at least two candles"
    # exactly one analytics pass and one delta computation per closed candle
    assert calls["analytics"] == closed
    assert calls["delta"] == closed
    # persisted + broadcast exactly once each
    assert len(system.db.candles) == closed
    assert len(system.ws_manager.candles) == closed
    assert len(system.ws_manager.deltas) == closed
    assert system.db.candles[0][:2] == (symbol, "1m")
    payload = system.ws_manager.candles[0][1]
    assert {"time", "open", "high", "low", "close", "volume", "delta"} <= set(payload)
    # the last closed candle is remembered for the live endpoints
    assert system._last_candles[symbol].timestamp_ms >= 1_700_000_000_000


# ──────────────────────────────────────────────
# T8/T9/T10 — live REST payloads
# ──────────────────────────────────────────────

def test_tape_endpoint_serves_engine_rows(system):
    from orderflow_system.dashboard.app import get_tape, set_system

    symbol = next(iter(system.pipelines))

    async def feed():
        for t in _make_ticks(seconds=30):
            await system._on_tick(symbol, t)

    asyncio.run(feed())
    set_system(system)
    try:
        rows = asyncio.run(get_tape(symbol, count=10))
    finally:
        set_system(None)

    assert len(rows) == 10
    assert {"time", "price", "size", "side"} <= set(rows[0])
    last = system.recent_ticks(symbol, count=1)[0]
    assert rows[-1]["price"] == round(last.price, 6)
    assert rows[-1]["side"] == "buy"


def test_footprint_endpoint_serves_engine_bars(system):
    from orderflow_system.dashboard.app import get_footprint, set_system

    symbol = next(iter(system.pipelines))

    async def feed():
        for t in _make_ticks():
            await system._on_tick(symbol, t)

    asyncio.run(feed())
    set_system(system)
    try:
        bars = asyncio.run(get_footprint(symbol, tf=60, range_s=86_400))
    finally:
        set_system(None)

    assert isinstance(bars, list) and bars
    bar = bars[-1]
    assert {"time", "open", "high", "low", "close", "poc", "levels"} <= set(bar)
    assert bar["levels"], "live footprint bars must carry bid/ask levels"
    assert {"price", "bid", "ask"} <= set(bar["levels"][0])
    total = sum(lv["bid"] + lv["ask"] for lv in bar["levels"])
    assert total > 0


def test_microstructure_endpoint_reports_engine_source(system):
    from orderflow_system.dashboard.app import get_microstructure, set_system

    symbol = next(iter(system.pipelines))

    async def feed():
        for t in _make_ticks():
            await system._on_tick(symbol, t)

    asyncio.run(feed())
    set_system(system)
    try:
        snap = asyncio.run(get_microstructure(symbol))
    finally:
        set_system(None)

    assert snap["source"] == "engine"
    assert {"marketState", "session", "absorption", "initiative", "delta", "exhaustion", "patterns"} <= set(snap)


def test_dict_endpoints_fall_back_to_demo_and_say_so():
    from orderflow_system.dashboard.app import (
        get_bias, get_microstructure, get_orderbook, get_stats, set_system,
    )

    set_system(None)
    try:
        bias = asyncio.run(get_bias("BTCUSDT"))
        book = asyncio.run(get_orderbook("BTCUSDT", levels=10))
        micro = asyncio.run(get_microstructure("BTCUSDT"))
        stats = asyncio.run(get_stats())
    finally:
        set_system(None)

    assert bias["source"] == "demo"
    assert book["source"] == "demo"
    assert micro["source"] == "demo"
    assert stats["source"] == "demo"


# ──────────────────────────────────────────────
# T12 — live/demo status map
# ──────────────────────────────────────────────

def test_live_status_map_tracks_endpoints_and_state(system):
    from orderflow_system.desktop.engine import engine as controller

    symbol = next(iter(system.pipelines))

    controller._system = system
    controller._state = "stopped"
    stopped = controller.live_status()
    assert stopped["overall"] == "demo"
    assert set(stopped["endpoints"].values()) == {"demo"}

    controller._state = "running"
    warming = controller.live_status()
    assert warming["overall"] == "warming"
    assert warming["endpoints"]["tape"] == "warming"

    async def feed():
        for t in _make_ticks():
            await system._on_tick(symbol, t)

    asyncio.run(feed())

    live = controller.live_status()
    assert live["overall"] == "live"
    assert live["endpoints"]["tape"] == "live"
    assert live["endpoints"]["footprint"] == "live"
    assert live["endpoints"]["candles"] == "live"

    controller._system = None
    controller._state = "stopped"
    assert controller.live_status()["overall"] == "demo"


def test_live_status_is_exposed_on_the_control_router():
    from orderflow_system.desktop.api import router

    paths = {route.path for route in router.routes}
    assert "/api/control/live-status" in paths
