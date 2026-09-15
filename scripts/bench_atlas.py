"""Throughput benchmark for the atlas analysers — the numbers behind the tuning.

Motivated by the reference layout's own performance guidance (docs.atas.net → Performance
recommendations): keep the per-event path allocation-free, do not rebuild what has
not changed, and never recompute inside the render step.

Measures, on synthetic but realistic BTC-shaped data:
  * ticks/second through the whole analyser stack (tape flow, depth map, CVD,
    profiles, imbalance ladder)
  * heatmap snapshot build time, cold vs cached (the version-stamped payload)
  * alerts evaluated per second

Run:  .venv/Scripts/python.exe scripts/bench_atlas.py [ticks]
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow_system.atlas.cvd import CvdTracker                # noqa: E402
from orderflow_system.atlas.depthmap import DepthHeatmap         # noqa: E402
from orderflow_system.atlas.imbalance import ImbalanceLadder     # noqa: E402
from orderflow_system.atlas.profiles import MarketProfile        # noqa: E402
from orderflow_system.atlas.tapeflow import TapeFlow             # noqa: E402
from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot, Side, Tick  # noqa: E402

PRICE = 78_000.0
TICK = 0.1


def make_ticks(n: int, start_ms: int) -> list[Tick]:
    rng = random.Random(7)
    out = []
    ts, price = start_ms, PRICE
    for i in range(n):
        ts += rng.randint(4, 40)
        price = max(1.0, price + rng.choice((-1, 0, 0, 1)) * TICK * rng.randint(1, 3))
        size = rng.choice((0.001, 0.005, 0.01, 0.02, 0.05, 0.4, 1.5))
        out.append(Tick(timestamp_ms=ts, price=round(price, 2), size=size,
                        side=Side.BUY if rng.random() < 0.52 else Side.SELL))
    return out


def make_book(start_ms: int, levels: int = 50) -> OrderbookSnapshot:
    rng = random.Random(11)
    bids = [OrderbookLevel(price=round(PRICE - i * TICK, 2), quantity=round(rng.uniform(0.5, 30.0), 3))
            for i in range(levels)]
    asks = [OrderbookLevel(price=round(PRICE + i * TICK, 2), quantity=round(rng.uniform(0.5, 30.0), 3))
            for i in range(levels)]
    return OrderbookSnapshot(timestamp_ms=start_ms, bids=bids, asks=asks)


def timed(fn, repeat: int = 5) -> tuple[float, float]:
    runs = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        runs.append(time.perf_counter() - t0)
    return statistics.median(runs), min(runs)


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60_000
    start_ms = int((time.time() - 900) * 1000)
    ticks = make_ticks(n, start_ms)
    book = make_book(start_ms)
    print(f"benchmark: {n:,} synthetic BTC ticks (0.001–1.5 size, 0.1 grid)\n")

    tape = TapeFlow("BTCUSDT", tick_size=TICK)
    depth = DepthHeatmap("BTCUSDT", tick_size=TICK, bucket_ms=1000)
    cvd = CvdTracker("BTCUSDT")
    profile = MarketProfile("BTCUSDT", tick_size=TICK)
    ladder = ImbalanceLadder("BTCUSDT", tick_size=TICK, rate_pct=150.0, window_ms=300_000,
                             min_volume=0.01, alert_min_levels=3)

    def feed_all() -> None:
        for t in ticks:
            tape.on_tick(t)
            depth.on_tick(t)
            cvd.on_tick(t)
            profile.on_tick(t)
            ladder.on_tick(t)

    t0 = time.perf_counter()
    feed_all()
    elapsed = time.perf_counter() - t0
    print(f"ingest (5 analysers, per tick) : {elapsed:6.3f} s → {n / elapsed:,.0f} ticks/s "
          f"({elapsed / n * 1e6:.1f} µs/tick)")

    # book updates interleaved, as the live engine sees them
    depth2 = DepthHeatmap("BTCUSDT", tick_size=TICK, bucket_ms=1000)

    def feed_book() -> None:
        for i, t in enumerate(ticks[: n // 4]):
            depth2.on_orderbook(book, ts_ms=start_ms + i * 4)
            depth2.on_tick(t)

    med, best = timed(feed_book, repeat=3)
    print(f"book updates (1 per 4 ticks)   : {med:6.3f} s → {n / 4 / med:,.0f} book+ticks/s")

    # cold = a build after the data changed; warm = a poll with an unchanged version.
    # (timing the same call repeatedly would just measure the cache, so invalidate
    # between cold runs the same way the ingest path does.)
    cold_runs = []
    for _ in range(3):
        depth._snapshot_cache = None
        depth._version += 1
        t0 = time.perf_counter()
        depth.snapshot(columns=300, max_rows=220)
        cold_runs.append(time.perf_counter() - t0)
    cold = statistics.median(cold_runs)
    warm = statistics.median([
        (lambda t0: (depth.snapshot(columns=300, max_rows=220), time.perf_counter() - t0)[1])(time.perf_counter())
        for _ in range(200)
    ])
    print(f"heatmap snapshot cold          : {cold * 1e3:6.2f} ms (builds: {depth.snapshot_builds})")
    print(f"heatmap snapshot cached        : {warm * 1e6:6.1f} µs  → {cold / warm:,.0f}× faster on an unchanged version")

    from orderflow_system.atlas.alerts import AlertEngine

    engine = AlertEngine()
    ev = {"ts_ms": start_ms, "price": PRICE, "size": 1.0, "side": "buy", "levels": 5,
          "from_price": PRICE, "to_price": PRICE + 1, "duration_ms": 20}

    def evaluate() -> None:
        for i in range(n // 10):
            engine.evaluate("BTCUSDT", "sweep", dict(ev, ts_ms=start_ms + i))

    med, _ = timed(evaluate, repeat=3)
    print(f"alert rules evaluated          : {n / 10 / med:,.0f} events/s")

    stats = stats_line(tape, depth, cvd, profile, ladder)
    print("\nanalyser output after the run :", stats)
    return 0


def stats_line(*trackers) -> str:
    bits = []
    for tr in trackers:
        s = tr.stats() if hasattr(tr, "stats") else {}
        name = type(tr).__name__.replace("Tracker", "").replace("Heatmap", "").replace("Ladder", "")
        key = next((k for k in ("big_trades", "trades", "columns", "buckets", "clusters", "levels")
                    if k in s), None)
        bits.append(f"{name}:{s.get(key) if key else '-'}")
    return " ".join(bits)


if __name__ == "__main__":
    raise SystemExit(main())
