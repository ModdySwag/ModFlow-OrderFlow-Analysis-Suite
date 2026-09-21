"""§122's gate: the colour ceiling cannot re-grade the map under the user's eyes.

Measured before the leash: the ceiling (top share of the visible window) climbed x1.84 in four
minutes while the window filled, so identical cells slid from bright to dull. The percentile stays
the statistic; the applied value walks toward it, speed-capped.
"""

from __future__ import annotations

from pathlib import Path

import orderflow_system.atlas.depthmap as dm
from orderflow_system.atlas.depthmap import DepthHeatmap

BASE = 1_700_000_000_000


class _Lvl:
    def __init__(self, price, quantity):
        self.price = price
        self.quantity = quantity


class _Book:
    def __init__(self, ts_ms, bids, asks):
        self.timestamp_ms = ts_ms
        self.best_bid = bids[0].price if bids else 0.0
        self.best_ask = asks[0].price if asks else 0.0
        self.bids = bids
        self.asks = asks
        self.stale = False


def _store(size: float = 5.0) -> DepthHeatmap:
    store = DepthHeatmap(symbol="BTCUSDT", tick_size=0.01, bucket_ms=1000)
    store.on_orderbook(_Book(BASE, [_Lvl(100.0, size)], [_Lvl(100.5, size)]))
    return store


# ── the leash itself, with an explicit clock ─────────────────────────────────────────────────

def test_first_build_adopts_the_target():
    store = _store()
    assert store._stabilise_scale(5.0, BASE) == 5.0
    assert store._scale_hold == 5.0


def test_a_doubling_target_moves_at_the_cap_not_the_gap():
    store = _store()
    store._stabilise_scale(5.0, BASE)
    out = store._stabilise_scale(10.0, BASE + 1000)          # one second later
    cap = 5.0 * store.SCALE_PER_S
    assert abs(out - (5.0 + cap)) < 1e-9, "one second must buy exactly the per-second cap"
    assert out < 10.0 * 0.6


def test_the_cap_bounds_four_minutes_of_drift():
    """The pre-fix statistic moved x1.84 in four minutes; the leash must hold it near x1.22."""
    store = _store()
    store._stabilise_scale(3.27, BASE)
    out = 3.27
    for i in range(1, 241):                                  # 240 one-second builds
        out = store._stabilise_scale(6.02, BASE + i * 1000)  # target pinned way above
    assert out <= 3.27 * 1.23, out
    assert out > 3.27 * 1.15, out                            # …and it still converges


def test_downward_drift_is_capped_the_same_way():
    store = _store()
    store._stabilise_scale(6.0, BASE)
    out = store._stabilise_scale(1.0, BASE + 1000)
    assert abs(out - (6.0 - 6.0 * store.SCALE_PER_S)) < 1e-9


def test_an_empty_window_never_moves_the_hold():
    store = _store()
    store._stabilise_scale(5.0, BASE)
    assert store._stabilise_scale(0.0, BASE + 60_000) == 0.0
    assert store._scale_hold == 5.0, "an empty slice must not reset the regime"


def test_a_cleared_store_forgets_the_regime():
    store = _store()
    store._stabilise_scale(5.0, BASE)
    store.clear()
    assert store._scale_hold == 0.0 and store._scale_hold_ts == 0
    assert store._stabilise_scale(9.0, BASE + 10) == 9.0, "a fresh buffer adopts its own target"


def test_snapshot_applies_the_leash_and_reports_the_target(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(dm.time, "time", lambda: clock["t"])
    store = _store(size=5.0)
    snap1 = store.snapshot(columns=10, max_rows=40)
    assert snap1["scale_max"] == snap1["scale_target"]        # first build adopts
    # a heavier book lands: the statistic jumps, the applied ceiling may not
    store.on_orderbook(_Book(BASE + 1000, [_Lvl(100.0, 60.0)], [_Lvl(100.5, 60.0)]))
    clock["t"] = 1001.0
    snap2 = store.snapshot(columns=10, max_rows=40)
    assert snap2["scale_target"] > snap1["scale_max"] * 1.5, "the raw statistic moved"
    assert snap2["scale_max"] <= snap1["scale_max"] * (1 + 0.001), "the applied ceiling held"


def test_the_pinned_ceiling_still_wins(monkeypatch):
    monkeypatch.setattr(dm.time, "time", lambda: 1000.0)
    store = _store()
    store.upper_cutoff_abs = 42.0
    snap = store.snapshot(columns=10, max_rows=40)
    assert snap["scale_max"] == 42.0, "an explicit pin is not leashed to anything"


# ── the wiring the UI rides ──────────────────────────────────────────────────────────────────

def test_a_width_change_restarts_the_buffer_and_the_dials_apply_live():
    root = Path(__file__).parent
    hub = (root / "atlas" / "hub.py").read_text(encoding="utf-8", errors="replace")
    api = (root / "desktop" / "api.py").read_text(encoding="utf-8", errors="replace")
    assert "if new_bucket != self.heatmap.bucket_ms:" in hub
    assert "self.heatmap.clear()" in hub
    assert 'if path.startswith("atlas."):' in api
    assert "hub.configure(saved.get(\"atlas\") or {})" in api
