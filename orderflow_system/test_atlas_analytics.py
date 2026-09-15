"""
Unit tests for the reference layout-inspired analytics (atlas package).

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_atlas_analytics.py -v

Every test drives the analyzers with synthetic, deterministic streams so the
detection thresholds are actually exercised (not "does it import").
"""

from __future__ import annotations

import time

import pytest

from orderflow_system.atlas.cvd import CvdTracker
from orderflow_system.atlas.depthmap import DepthHeatmap
from orderflow_system.atlas.frames import FrameSet, RangeBars, RenkoBricks, ReversalBars, TickBars, VolumeBars
from orderflow_system.atlas.profiles import MarketProfile, developing_value_area, virgin_pocs
from orderflow_system.atlas.tapeflow import TapeFlow
from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot, Side, Tick

T0 = 1_700_000_000_000          # fixed epoch ms → deterministic bucketing


def tick(ts: int, price: float, size: float, side: str = "buy") -> Tick:
    return Tick(timestamp_ms=ts, price=price, size=size, side=Side.BUY if side == "buy" else Side.SELL)


def book(ts: int, bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> OrderbookSnapshot:
    return OrderbookSnapshot(
        timestamp_ms=ts,
        bids=[OrderbookLevel(price=p, quantity=q) for p, q in bids],
        asks=[OrderbookLevel(price=p, quantity=q) for p, q in asks],
    )


# ── heatmap ─────────────────────────────────────────────────────────────────

def test_heatmap_builds_matrix_and_finds_walls():
    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000, wall_quantile=0.85)
    hm.on_orderbook(book(T0, [(100, 5), (99, 3), (98, 1)], [(101, 4), (102, 2)]))
    snap = hm.snapshot()

    assert snap["tick"] == 1.0
    assert len(snap["buckets"]) == 1
    assert 100.0 in snap["prices"] and 101.0 in snap["prices"]
    row_100 = snap["values"][snap["prices"].index(100.0)][0]
    assert row_100 == 5.0

    walls = hm.wall_prices()
    assert walls, "a level at the top quantile must register as a wall"
    assert walls[0]["price"] in (100.0, 101.0)


def test_heatmap_pull_detected_only_near_price():
    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000, wall_quantile=0.5,
                      pull_pct=0.5, pull_near_ticks=5.0)
    # price is at 100 → the level at 130 is far away, the one at 101 is close
    hm.on_tick(tick(T0, 100.0, 1.0))
    hm.on_orderbook(book(T0, [(130.0, 100.0), (101.0, 100.0)], [(102.0, 50.0)]))
    hm.on_orderbook(book(T0 + 1000, [(130.0, 10.0), (101.0, 10.0)], [(102.0, 50.0)]))

    pulls = [e for e in hm.events("pull")]
    assert len(pulls) == 1, f"exactly the near-price pull should fire, got {pulls}"
    assert pulls[0]["price"] == 101.0


def test_heatmap_stack_event():
    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000, wall_quantile=0.5, stack_pct=1.5)
    hm.on_orderbook(book(T0, [(100.0, 10.0)], [(101.0, 10.0)]))
    hm.on_orderbook(book(T0 + 1000, [(100.0, 40.0)], [(101.0, 10.0)]))
    stacks = hm.events("stack")
    assert stacks and stacks[0]["price"] == 100.0
    assert "stacked" in stacks[0]["detail"]


def test_heatmap_traded_volume_lands_in_the_right_bucket():
    hm = DepthHeatmap("T", tick_size=0.5, bucket_ms=1000)
    hm.on_tick(tick(T0 + 200, 100.5, 3.0))
    hm.on_tick(tick(T0 + 400, 100.5, 2.0))
    snap = hm.snapshot()
    idx = snap["prices"].index(100.5)
    assert snap["traded"][idx][0] == 5.0
    assert snap["best"][0]["trades"] == 2


# ── tape: big trades, sweeps, icebergs, stop runs ───────────────────────────

def test_big_trade_threshold_is_adaptive():
    tf = TapeFlow("T", tick_size=0.1, big_quantile=0.95, big_min_size=0.0)
    for i in range(200):                              # mostly small prints
        tf.on_tick(tick(T0 + i, 100.0, 1.0))
    thr = tf.big_threshold()
    assert thr >= 1.0

    out = tf.on_tick(tick(T0 + 500, 100.0, thr * 4))   # a clearly big print
    assert "big_trade" in out
    assert out["big_trade"].multiple >= 3.0
    assert "block_trade" in out                        # ≥ 3× threshold = block
    assert tf.stats()["blocks"] == 1


def test_sweep_requires_levels_within_window():
    tf = TapeFlow("T", tick_size=1.0, sweep_levels=5, sweep_max_ms=100, sweep_min_size=0.0)
    for i in range(5):                                  # 5 distinct prices in 80 ms
        out = tf.on_tick(tick(T0 + i * 20, 100.0 + i, 2.0, "buy"))
    assert "sweep" in out
    assert out["sweep"].levels == 5
    assert out["sweep"].duration_ms <= 100

    tf2 = TapeFlow("T", tick_size=1.0, sweep_levels=5, sweep_max_ms=100)
    last = {}
    for i in range(4):                                  # only 4 prices → no sweep
        last = tf2.on_tick(tick(T0 + i * 20, 100.0 + (i % 2), 2.0, "buy"))
    assert "sweep" not in last
    assert tf2.stats()["sweeps"] == 0


def test_sweep_side_change_resets_the_buffer():
    tf = TapeFlow("T", tick_size=1.0, sweep_levels=3, sweep_max_ms=500)
    tf.on_tick(tick(T0, 100.0, 1.0, "buy"))
    tf.on_tick(tick(T0 + 10, 101.0, 1.0, "sell"))       # flips side → buffer resets
    out = tf.on_tick(tick(T0 + 20, 102.0, 1.0, "sell"))
    assert "sweep" not in out


def test_iceberg_detected_from_repeated_equal_fills():
    tf = TapeFlow("T", tick_size=1.0, iceberg_min_fills=4, iceberg_size_tol=0.1, iceberg_max_ms=10_000)
    fired = None
    for i in range(5):
        out = tf.on_tick(tick(T0 + i * 100, 100.0, 5.0))
        if "iceberg" in out:
            fired = out["iceberg"]
    assert fired is not None, "5 identical refills at one price must be flagged"
    assert fired.price == 100.0
    assert fired.fills >= 4
    assert tf.stats()["icebergs"] >= 1

    # and it must not spam the same level on every print
    for i in range(5, 8):
        tf.on_tick(tick(T0 + i * 100, 100.0, 5.0))
    assert tf.stats()["icebergs"] <= 4, "8 prints must not produce 8 events"


def test_no_iceberg_when_sizes_vary():
    tf = TapeFlow("T", tick_size=1.0, iceberg_min_fills=4, iceberg_size_tol=0.05)
    out = {}
    for i, size in enumerate((1.0, 9.0, 3.0, 20.0, 7.0)):
        out = tf.on_tick(tick(T0 + i * 100, 100.0, size))
    assert "iceberg" not in out


def test_stop_run_needs_range_and_volume_burst():
    tf = TapeFlow("T", tick_size=0.1, stoprun_ticks=20, stoprun_ms=3000, stoprun_vol_z=1.0)
    tf.speed_windows = (1,)
    for i in range(60):                                # quiet background
        tf.on_tick(tick(T0 + i * 50, 100.0, 0.5))
    t1 = T0 + 4000
    found = None
    for i in range(20):                                # burst: 30 ticks in 2 s
        out = tf.on_tick(tick(t1 + i * 100, 99.0 - i * 0.15, 40.0, "sell"))
        if "stop_run" in out:
            found = out["stop_run"]
    assert found is not None, "a 28-tick burst in 2 s must register as a stop run"
    assert found.direction == "down"
    assert found.ticks_moved >= 20


def test_no_stop_run_on_slow_drift():
    tf = TapeFlow("T", tick_size=0.1, stoprun_ticks=20, stoprun_ms=3000)
    out = {}
    for i in range(40):                                # same range but spread over 40 s
        out = tf.on_tick(tick(T0 + i * 1000, 99.0 - i * 0.05, 0.1))
    assert "stop_run" not in out


def test_liquidation_cluster_confirms_stop_run():
    tf = TapeFlow("T", tick_size=1.0, stoprun_ticks=8, stoprun_ms=3000)
    t1 = T0 + 10_000
    found = None
    for i in range(15):
        out = tf.on_tick(tick(t1 + i * 50, 100.0 - i, 5.0, "sell"))
        if "stop_run" in out:
            found = out["stop_run"]
    assert found is not None, "a 14-tick burst must register as a stop run"

    sr = tf.on_liquidation(price=95.0, size=3.0, side="Sell", ts_ms=t1 + 200)
    sr = tf.on_liquidation(price=95.5, size=2.0, side="Sell", ts_ms=t1 + 400) or sr
    sr = tf.on_liquidation(price=95.2, size=4.0, side="Sell", ts_ms=t1 + 600) or sr
    assert sr is not None and sr.confirmed_by_liquidations is True
    assert tf.stats()["liquidations"] == 3


# ── CVD ─────────────────────────────────────────────────────────────────────

def test_cvd_windows_and_cumulative():
    cvd = CvdTracker("T", tick_size=1.0, bucket_ms=1000, windows_s=(1, 5))
    cvd.on_tick(tick(T0, 100.0, 10.0, "buy"))
    cvd.on_tick(tick(T0 + 100, 100.0, 4.0, "sell"))
    cvd.on_tick(tick(T0 + 2000, 100.0, 1.0, "buy"))
    snap = cvd.snapshot()
    assert snap["cvd"] == pytest.approx(7.0)
    assert snap["windows"]["1s"] == pytest.approx(1.0)      # only the latest bucket
    assert snap["windows"]["5s"] == pytest.approx(7.0)


def test_cvd_bearish_divergence():
    cvd = CvdTracker("T", tick_size=0.1, bucket_ms=1000, divergence_lookback=3,
                     divergence_min_ticks=5.0)
    ts = T0
    for i in range(3):                                   # warm-up so both windows are full
        cvd.on_tick(tick(ts, 99.0, 1.0, "buy"))
        ts += 1000
    for i in range(3):                                   # previous window: price near 100, buying
        cvd.on_tick(tick(ts, 100.0 + i * 0.01, 10.0, "buy"))
        ts += 1000
    for i in range(3):                                   # current window: price higher, delta negative
        cvd.on_tick(tick(ts, 101.0 + i * 0.01, 2.0, "buy"))
        cvd.on_tick(tick(ts + 10, 101.0, 30.0, "sell"))
        ts += 1000
    div = cvd.detect_divergence()
    assert div is not None, "price up + CVD down must register as a bearish divergence"
    assert div.kind == "bearish"
    assert "higher high" in div.note


def test_cvd_reanchor_resets():
    cvd = CvdTracker("T", tick_size=1.0)
    cvd.on_tick(tick(T0, 100.0, 5.0, "buy"))
    cvd.reanchor()
    assert cvd.snapshot()["cvd"] == 0.0


# ── Market Profile / TPO ────────────────────────────────────────────────────

def test_market_profile_tpo_letters_and_poc():
    mp = MarketProfile("T", tick_size=1.0, bracket_seconds=1800, value_area_pct=0.7)
    # bracket A (first half hour): 100-102, heavy at 101
    for i in range(10):
        mp.on_tick(tick(T0 + i * 100, 101.0, 5.0))
    for i in range(3):
        mp.on_tick(tick(T0 + i * 100, 100.0, 1.0))
        mp.on_tick(tick(T0 + i * 100, 102.0, 1.0))
    # bracket B (initial balance = A+B): 101-103
    for i in range(10):
        mp.on_tick(tick(T0 + 1_800_000 + i * 100, 103.0, 2.0))
        mp.on_tick(tick(T0 + 1_800_000 + i * 100, 101.0, 2.0))
    # bracket C: range extension above the IB high
    for i in range(5):
        mp.on_tick(tick(T0 + 3_600_000 + i * 100, 104.0, 2.0))

    snap = mp.snapshot()
    assert len(snap["brackets"]) == 3
    assert snap["poc"] == 101.0
    vah, val = snap["vah"], snap["val"]
    assert val <= 101.0 <= vah
    letters = {row["price"]: row["letters"] for row in snap["levels"]}
    assert letters[101.0] == "AB"                     # traded in both opening brackets
    assert letters[102.0] == "A" and "C" in letters[104.0]
    assert snap["ib"]["ib_high"] == 103.0             # IB = first two brackets
    assert snap["range_extension"]["extended"] is True
    assert snap["range_extension"]["extension_up_ticks"] == pytest.approx(1.0)
    assert 100.0 in snap["single_prints"]             # only touched in A


def test_market_profile_reset():
    mp = MarketProfile("T", tick_size=1.0)
    mp.on_tick(tick(T0, 100.0, 1.0))
    mp.clear()
    assert mp.snapshot()["levels"] == []


def test_developing_value_area_and_virgin_pocs():
    class P:
        def __init__(self, s, poc, vah, val):
            self.session_date, self.poc, self.vah, self.val = s, poc, vah, val

    profiles = [P("d1", 100.0, 105.0, 95.0), P("d2", 110.0, 112.0, 108.0)]
    dva = developing_value_area(profiles)
    assert dva["trend"] == "higher"
    assert dva["sessions"][0]["poc"] == 100.0

    virgins = virgin_pocs(profiles, current_price=111.0)
    prices = [v["poc"] for v in virgins]
    assert 100.0 in prices and 110.0 not in prices     # d2's POC sits inside d2's range


# ── frames ──────────────────────────────────────────────────────────────────

def test_range_bars_close_on_height():
    rb = RangeBars("T", tick_size=1.0, range_ticks=5)
    closed = []
    for price in (100, 101, 103, 105, 106, 104):       # height reaches 5 at the 4th print
        bar = rb.on_tick(tick(T0, float(price), 1.0))
        if bar:
            closed.append(bar)
    assert len(closed) == 1
    assert closed[0].high - closed[0].low >= 5
    assert closed[0].high == 105.0


def test_renko_bricks_and_reversal():
    rk = RenkoBricks("T", tick_size=1.0, brick_ticks=5, reversal_bricks=2)
    bricks = []
    for price in (100, 104, 105, 110, 115, 114, 109, 105, 104):   # up 3 bricks, then reverse needs 2
        b = rk.on_tick(tick(T0, float(price), 1.0))
        if b:
            bricks.append(b)
    ups = [b for b in bricks if b.close > b.open]
    downs = [b for b in bricks if b.close < b.open]
    assert len(ups) >= 3
    assert downs, "a 2-brick reversal must produce a down brick"
    assert all(abs(b.close - b.open) == 5 for b in bricks)


def test_reversal_bars():
    rev = ReversalBars("T", tick_size=1.0, reversal_ticks=10)
    closed = []
    for price in (100, 105, 110, 108, 101):            # +10 from low 100 → close
        b = rev.on_tick(tick(T0, float(price), 1.0))
        if b:
            closed.append(b)
    assert closed and closed[0].high == 110.0


def test_tick_and_volume_bars():
    tb = TickBars("T", tick_size=1.0, ticks_per_bar=3)
    bars = [b for b in (tb.on_tick(tick(T0 + i, 100.0, 1.0)) for i in range(6)) if b]
    assert len(bars) == 2 and all(b.ticks == 3 for b in bars)

    vb = VolumeBars("T", tick_size=1.0, volume_per_bar=10.0)
    bars = [b for b in (vb.on_tick(tick(T0 + i, 100.0, 4.0)) for i in range(6)) if b]
    assert len(bars) == 2
    assert all(b.volume >= 10.0 for b in bars)


def test_frameset_dispatch_and_snapshot():
    fs = FrameSet("T", 1.0, {"ticks_per_bar": 2, "volume_per_bar": 3, "range_ticks": 100, "brick_ticks": 100, "reversal_ticks": 100})
    closed = {}
    for i in range(4):
        closed.update(fs.on_tick(tick(T0 + i, 100.0 + i, 1.0)))
    assert "tick" in closed and "volume" in closed
    snap = fs.snapshot()
    assert set(snap) == {"range", "renko", "reversal", "tick", "volume", "delta"}
    assert fs.recent("tick")[-1]["ticks"] == 2


def test_heatmap_folds_out_of_order_updates_into_one_column():
    """Two feeds with independent clocks must not create duplicate columns."""
    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000)
    # strictly increasing timeline
    for i in range(5):
        hm.on_orderbook(book(T0 + i * 1000, [(100.0, float(i + 1))], [(101.0, 1.0)]))
    # a late update from the other feed (older timestamp) must not add a column
    hm.on_orderbook(book(T0 + 1000, [(100.0, 99.0)], [(101.0, 1.0)]))
    hm.on_orderbook(book(T0, [(100.0, 5.0)], [(101.0, 1.0)]))

    snap = hm.snapshot()
    assert len(snap["buckets"]) == 5, f"expected 5 buckets, got {len(snap['buckets'])}"
    assert snap["buckets"] == sorted(set(snap["buckets"]))
    assert snap["buckets"][-1] - snap["buckets"][0] == 4000


def test_heatmap_price_aggregation_fits_requested_rows():
    """A 0.01 tick with a 200-level book must still fit the requested row count."""
    hm = DepthHeatmap("T", tick_size=0.01)
    bids = [(100.0 - i * 0.1, float(i + 1)) for i in range(200)]     # 200 levels, $20 wide
    asks = [(100.0 + i * 0.1, float(i + 1)) for i in range(200)]
    hm.on_orderbook(book(T0, bids, asks))
    hm.on_tick(tick(T0, 100.0, 3.0))

    snap = hm.snapshot(columns=50, max_rows=100)
    assert len(snap["prices"]) <= 100
    assert snap["step"] > 0.01, "display step must grow to fit the book"
    span = snap["prices"][-1] - snap["prices"][0]
    assert span >= 30, f"aggregated view must cover the book, got {span}"
    # the traded print still lands somewhere on the grid
    assert sum(v for row in snap["traded"] for v in row) == 3.0
    assert sum(v for row in snap["values"] for v in row) > 0


# ── the reference layout-documented filter semantics (from the ULTRA/MBO spec) ──────────────

def test_sweep_respects_aggressor_and_range_filters():
    """the reference layout Sweeps Tracker gates on Min Volume / Min Range (ticks) / Min Aggressors."""
    tf = TapeFlow("T", tick_size=0.1, sweep_levels=2, sweep_max_ms=1000,
                  sweep_min_aggressors=4, sweep_min_range_ticks=5.0)
    # 3 aggressors, 2 levels, 0.1 span (1 tick) → fails both gates
    for i in range(3):
        tf.on_tick(tick(T0 + i * 10, 100.0 + i * 0.1, 2.0))
    assert not tf.sweeps, "3 aggressors / 1 tick must not qualify"
    # 5 aggressors across 6 levels → passes the aggressor gate and the range gate
    tf2 = TapeFlow("T", tick_size=0.1, sweep_levels=2, sweep_max_ms=1000,
                   sweep_min_aggressors=4, sweep_min_range_ticks=5.0)
    for i in range(6):
        tf2.on_tick(tick(T0 + i * 10, 100.0 + i * 0.1, 2.0))
    assert tf2.sweeps, "6 aggressors over 6 ticks must qualify"
    ev = tf2.sweeps[-1]
    assert ev.aggressors >= 4 and ev.range_ticks >= 5.0


def test_iceberg_respects_total_volume_and_duration_filters():
    """the reference layout Icebergs Tracker filters: Min Hidden Volume, Min Total Volume, Min Duration."""
    tf = TapeFlow("T", tick_size=1.0, iceberg_min_fills=3, iceberg_max_ms=60_000,
                  iceberg_min_total=100.0, iceberg_min_duration_ms=2000)
    for i in range(4):                                  # 4 × 5 = 20 total → below Min Total
        tf.on_tick(tick(T0 + i * 100, 100.0, 5.0))
    assert not tf.icebergs, "total 20 < Min Total Volume 100"
    tf2 = TapeFlow("T", tick_size=1.0, iceberg_min_fills=3, iceberg_max_ms=60_000,
                   iceberg_min_total=10.0, iceberg_min_duration_ms=2000)
    for i in range(3):                                  # lifetime 200ms < Min Duration 2000ms
        tf2.on_tick(tick(T0 + i * 100, 100.0, 5.0))
    assert not tf2.icebergs, "lifetime 200ms < Min Duration 2000ms"
    for i in range(3, 30):                              # keep refilling for ~3s
        tf2.on_tick(tick(T0 + i * 100, 100.0, 5.0))
    assert tf2.icebergs, "long refill with enough volume must qualify"
    assert tf2.icebergs[-1].duration_ms >= 2000
    assert tf2.icebergs[-1].confidence == "inferred"


def test_stop_run_min_volume_and_prints_filters():
    """the reference layout Stops Tracker gates on Min Volume and a Stops Count range."""
    tf = TapeFlow("T", tick_size=0.1, stoprun_ticks=10, stoprun_ms=3000,
                  stoprun_min_volume=10_000.0)
    for i in range(20):
        tf.on_tick(tick(T0 + i * 100, 100.0 - i * 0.1, 1.0))
    assert not tf.stop_runs, "volume far below the Min Volume gate"
    tf2 = TapeFlow("T", tick_size=0.1, stoprun_ticks=10, stoprun_ms=3000,
                   stoprun_min_volume=1.0, stoprun_min_prints=5)
    for i in range(20):
        tf2.on_tick(tick(T0 + i * 100, 100.0 - i * 0.1, 1.0))
    assert tf2.stop_runs and tf2.stop_runs[-1].prints >= 5


def test_cvd_pro_multi_size_buckets():
    """the reference layout 'CVD Pro (Multi)': one cumulative line per size bucket."""
    cvd = CvdTracker("T", tick_size=0.1, bucket_ms=1000)
    cvd.set_pro_bands([[0, 1], [1, 10], [10, 0]])          # small / mid / large
    small = tick(T0, 100.0, 0.5, "buy")
    mid = tick(T0 + 10, 100.0, 5.0, "sell")
    big = tick(T0 + 20, 100.0, 50.0, "buy")
    for t in (small, mid, big):
        cvd.on_tick(t)
    snap = cvd.snapshot()
    multi = snap["pro_multi"]
    assert multi["bands"] == [[0.0, 1.0], [1.0, 10.0], [10.0, 0.0]]
    assert multi["cvd"] == [0.5, -5.0, 50.0], multi["cvd"]
    assert len(multi["series"]) == 1 and multi["series"][0] == [0.5, -5.0, 50.0]


def test_heatmap_upper_cutoff_reports_scale_max():
    """the reference layout 'Upper Cut-off %': the render scale saturates at the top share of values."""
    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000, wall_quantile=0.9,
                      upper_cutoff_pct=5.0)
    for i in range(20):
        levels = [(100.0, 1.0 + i)]                        # sizes 1..20
        hm.on_orderbook(_book(T0 + i * 1000, levels))
    snap = hm.snapshot(columns=30, max_rows=40)
    assert snap["upper_cutoff_pct"] == 5.0
    assert 0 < snap["scale_max"] <= 20.0
    # the cut-off must ignore the single largest outlier for the colour scale
    assert snap["scale_max"] < 20.0


def _book(ts_ms: int, levels_bid, levels_ask=None):
    """Small helper: build an OrderbookSnapshot from (price, size) pairs."""
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    bids = [OrderbookLevel(price=p, quantity=q) for p, q in levels_bid]
    asks = [OrderbookLevel(price=p, quantity=q) for p, q in (levels_ask or [(p + 50, q) for p, q in levels_bid])]
    return OrderbookSnapshot(timestamp_ms=ts_ms, bids=bids, asks=asks)


# ═══════════════════════════════════════════════════════════════
# Performance regressions (the reference layout performance guidance, folded in)
# ═══════════════════════════════════════════════════════════════

def test_heatmap_snapshot_is_version_stamped_and_cached():
    """A poll with an unchanged version must not rebuild the matrix."""
    from orderflow_system.atlas.depthmap import DepthHeatmap
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    h = DepthHeatmap("BTCUSDT", tick_size=0.1, bucket_ms=1000)
    bids = [OrderbookLevel(price=round(78000 - i * 0.1, 2), quantity=1.0 + i) for i in range(20)]
    asks = [OrderbookLevel(price=round(78001 + i * 0.1, 2), quantity=1.0 + i) for i in range(20)]
    book = OrderbookSnapshot(timestamp_ms=T0, bids=bids, asks=asks)

    h.on_orderbook(book)
    first = h.snapshot(columns=50, max_rows=40)
    assert first["cached"] is False and first["version"] >= 1
    builds = h.snapshot_builds

    again = h.snapshot(columns=50, max_rows=40)
    assert again["cached"] is True and h.snapshot_builds == builds, "unchanged version must reuse the payload"
    assert again["buckets"] == first["buckets"]

    h.on_orderbook(book)                                   # new data → new version
    fresh = h.snapshot(columns=50, max_rows=40)
    assert fresh["cached"] is False and fresh["version"] > first["version"]
    assert h.snapshot_builds == builds + 1

    # the API attaches `walls` to whatever it gets back — that must not poison the cache
    fresh["walls"] = [{"price": 1}]
    assert "walls" not in h.snapshot(columns=50, max_rows=40)


def test_stop_run_aggregates_match_the_underlying_prints():
    """The second-bucket fast path must report the same window as a raw scan."""
    tf = TapeFlow("BTCUSDT", tick_size=0.1, stoprun_ticks=12.0, stoprun_ms=3000,
                  stoprun_min_volume=0.0, stoprun_min_prints=1, stoprun_vol_z=0.0)
    base = T0
    prices = [100.0 + i * 0.1 for i in range(40)]           # a clean 4-tick run upward
    ticks = [tick(base + i * 20, p, 0.5, "buy") for i, p in enumerate(prices)]
    ev = None
    for i, t in enumerate(ticks):                       # the event fires the moment the range is met
        out = tf.on_tick(t)
        if "stop_run" in out:
            ev = out["stop_run"]
            assert ev.prints == i + 1, "the window must hold exactly the prints so far"
            assert ev.volume == pytest.approx(0.5 * (i + 1))
            assert ev.from_price == pytest.approx(prices[0])
            assert ev.to_price == pytest.approx(prices[i])
            assert ev.ticks_moved == pytest.approx(round((prices[i] - prices[0]) / 0.1, 2))
            break
    assert ev is not None, "a clean 12-tick run inside one second must fire"


def test_stop_run_window_drops_prints_older_than_the_window():
    """Prints outside stoprun_ms must not inflate the aggregate."""
    tf = TapeFlow("BTCUSDT", tick_size=0.1, stoprun_ticks=12.0, stoprun_ms=1000,
                  stoprun_min_volume=0.0, stoprun_min_prints=1, stoprun_vol_z=0.0)
    base = T0
    old = [tick(base - 30_000 + i * 100, 90.0, 5.0, "sell") for i in range(20)]   # 30 s ago
    for t in old:
        tf.on_tick(t)
    fresh = [tick(base + i * 10, 100.0 + i * 0.1, 0.25, "buy") for i in range(30)]
    ev = None
    for t in fresh:
        out = tf.on_tick(t)
        if "stop_run" in out:
            ev = out["stop_run"]
            break
    assert ev is not None, "the burst itself must still register"
    # every in-window print is 0.25 and every out-of-window print is 5.0: a leaked
    # old print shows up immediately as volume / prints != 0.25
    assert ev.volume == pytest.approx(0.25 * ev.prints), "old prints leaked into the window"
    assert ev.from_price >= 100.0, "the window must not reach back to the 30 s old prints"
    assert ev.prints <= len(fresh)


def test_wall_ages_ride_the_payload_the_map_draws():
    """A wall the engine has watched hold past its threshold must say so where the map is read (P1-6).

    The map could only ever show size; `wall_durations()` knew the streak all along and nothing carried
    it. `attach_wall_ages` is the one place that joins the two, so the table, the cursor readout and the
    age tint read one shape.
    """
    from orderflow_system.atlas.api import attach_wall_ages

    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000, wall_quantile=0.85, wall_age_ms=120_000)
    bids = [(100.0, 50.0), (99.0, 3.0)]
    asks = [(101.0, 4.0)]
    hm.on_orderbook(book(T0, bids, asks))
    for i in range(1, 130):                                   # 130 one-second columns = 129 s of watch
        hm.on_orderbook(book(T0 + i * 1000, bids, asks))

    durs = hm.wall_durations()
    assert durs, "a level held across the window must report a duration"
    assert durs[0]["price"] == 100.0 and durs[0]["held_ms"] >= 120_000, durs[0]
    assert all(r["held_ms"] > 0 for r in durs), "a zero-held row is not a duration"

    snap = attach_wall_ages({}, hm)
    assert snap["wall_age_ms"] == 120_000, "the engine's own threshold travels with the rows"
    walls = {w["price"]: w for w in snap["walls"]}
    assert walls and 100.0 in walls, walls
    assert walls[100.0]["held_ms"] >= 120_000, "the wall the map draws carries how long it has held"
    assert all("held_ms" in w for w in snap["walls"]), "every row carries the key, even at zero"
    assert all(isinstance(w["held_ms"], int) for w in snap["walls"])
