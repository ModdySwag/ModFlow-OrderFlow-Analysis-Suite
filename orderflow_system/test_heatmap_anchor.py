"""§121's server gate: the heatmap's time anchor (`until_ms`) — the primitive pan/zoom ride.

The store is fed by hand so every timestamp is known, which is the only way to prove a slice ENDS
where it says it does (a live-edge-only snapshot passes every other test in the suite).
"""

from __future__ import annotations

from pathlib import Path

from orderflow_system.atlas.depthmap import DepthHeatmap

BASE = 1_700_000_000_000


class _Lvl:
    def __init__(self, price, quantity):
        self.price = price
        self.quantity = quantity


class _Book:
    """Duck-typed OrderbookSnapshot: on_orderbook reads timestamp_ms / best_* / bids / asks / stale."""

    def __init__(self, ts_ms, bids, asks, stale=False):
        self.timestamp_ms = ts_ms
        self.best_bid = bids[0].price if bids else 0.0
        self.best_ask = asks[0].price if asks else 0.0
        self.bids = bids
        self.asks = asks
        self.stale = stale


def _store(buckets: int = 12, bucket_ms: int = 1000) -> DepthHeatmap:
    """One book per bucket; bucket i sits at BASE + i*bucket_ms with a signature bid size."""
    store = DepthHeatmap(symbol="BTCUSDT", tick_size=0.01, bucket_ms=bucket_ms)
    for i in range(buckets):
        ts = BASE + i * bucket_ms
        size = 5.0 + i           # bucket 5's signature size is 10
        store.on_orderbook(_Book(ts, [_Lvl(100.0, size)], [_Lvl(100.5, 3.0)]))
    return store


def test_live_snapshot_is_unchanged_by_default():
    snap = _store().snapshot(columns=3, max_rows=50)
    assert snap["buckets"] == [BASE + 9000, BASE + 10000, BASE + 11000]
    assert snap["until_ms"] == 0


def test_until_ends_the_slice_at_the_anchor():
    snap = _store().snapshot(columns=3, max_rows=50, until_ms=BASE + 5000)
    assert snap["buckets"] == [BASE + 3000, BASE + 4000, BASE + 5000]
    assert snap["until_ms"] == BASE + 5000


def test_until_slice_keeps_the_full_window_width():
    snap = _store().snapshot(columns=4, max_rows=50, until_ms=BASE + 5000)
    assert snap["buckets"] == [BASE + 2000, BASE + 3000, BASE + 4000, BASE + 5000]


def test_matrix_columns_follow_the_slice():
    """values[r][c] must belong to buckets[c] — the slice and the matrix must agree."""
    snap = _store().snapshot(columns=1, max_rows=50, until_ms=BASE + 5000)
    assert snap["buckets"] == [BASE + 5000]
    row = [i for i, p in enumerate(snap["prices"]) if abs(p - 100.0) < 1e-9]
    assert row, "the 100.0 row must exist"
    assert snap["values"][row[0]][0] == 10.0   # bucket 5's signature bid size


def test_traded_matrix_follows_the_slice():
    # feed in tape order: the store folds a late timestamp into the latest column by design
    # ("data that arrived out of order"), so the tick must arrive between its neighbours.
    store = DepthHeatmap(symbol="BTCUSDT", tick_size=0.01, bucket_ms=1000)
    for i in range(6):
        ts = BASE + i * 1000
        store.on_orderbook(_Book(ts, [_Lvl(100.0, 5.0 + i)], [_Lvl(100.5, 3.0)]))
    store.on_tick(type("T", (), {"timestamp_ms": BASE + 5000, "price": 100.02, "size": 7.0})())
    for i in range(6, 12):
        ts = BASE + i * 1000
        store.on_orderbook(_Book(ts, [_Lvl(100.0, 5.0 + i)], [_Lvl(100.5, 3.0)]))
    snap = store.snapshot(columns=1, max_rows=50, until_ms=BASE + 5000)
    row = [i for i, p in enumerate(snap["prices"]) if abs(p - 100.02) < 1e-9]
    assert row, "the 100.02 row must exist"
    assert snap["traded"][row[0]][0] == 7.0
    # …and the same tick must NOT appear in the window before it
    snap2 = store.snapshot(columns=1, max_rows=50, until_ms=BASE + 4000)
    row2 = [i for i, p in enumerate(snap2["prices"]) if abs(p - 100.02) < 1e-9]
    assert not row2 or snap2["traded"][row2[0]][0] == 0.0


def test_until_past_the_newest_clamps_to_the_live_edge():
    snap = _store().snapshot(columns=3, max_rows=50, until_ms=BASE + 999_999)
    assert snap["buckets"] == [BASE + 9000, BASE + 10000, BASE + 11000]


def test_until_before_the_buffer_degrades_out_loud():
    snap = _store().snapshot(columns=3, max_rows=50, until_ms=BASE - 5000)
    assert snap["buckets"] == []
    assert snap["have_from_ms"] == BASE
    assert snap["have_to_ms"] == BASE + 11000
    assert "no depth history at this time" in snap.get("note", "")


def test_payload_carries_the_bounds_for_client_clamping():
    snap = _store().snapshot(columns=3, max_rows=50)
    assert snap["bucket_ms"] == 1000
    assert snap["have_from_ms"] == BASE
    assert snap["have_to_ms"] == BASE + 11000


def test_cache_distinguishes_anchors():
    store = _store()
    a = store.snapshot(columns=3, max_rows=50, until_ms=BASE + 5000)
    b = store.snapshot(columns=3, max_rows=50, until_ms=BASE + 5000)
    c = store.snapshot(columns=3, max_rows=50, until_ms=BASE + 4000)
    assert a["cached"] is False and b["cached"] is True
    assert c["cached"] is False and c["buckets"][-1] == BASE + 4000


def test_the_api_and_hub_thread_the_anchor_through():
    """The gate the UI actually rides: route -> hub -> store, one name each."""
    root = Path(__file__).parent
    api = (root / "atlas" / "api.py").read_text(encoding="utf-8", errors="replace")
    hub = (root / "atlas" / "hub.py").read_text(encoding="utf-8", errors="replace")
    assert "until: int = Query(default=0, ge=0)" in api
    assert "until_ms=(until or None)" in api
    assert "until_ms: Optional[int] = None" in hub
    assert "until_ms=until_ms" in hub
