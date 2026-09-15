"""Per-analyser profile: where the ingest microseconds actually go."""

from __future__ import annotations

import cProfile
import pstats
import random
import sys
import time
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow_system.atlas.cvd import CvdTracker                # noqa: E402
from orderflow_system.atlas.depthmap import DepthHeatmap         # noqa: E402
from orderflow_system.atlas.imbalance import ImbalanceLadder     # noqa: E402
from orderflow_system.atlas.profiles import MarketProfile        # noqa: E402
from orderflow_system.atlas.tapeflow import TapeFlow             # noqa: E402
from orderflow_system.data.models import Side, Tick              # noqa: E402

N = 20_000


def ticks(n: int):
    rng = random.Random(7)
    ts, price = int((time.time() - 600) * 1000), 78_000.0
    out = []
    for _ in range(n):
        ts += rng.randint(4, 40)
        price = max(1.0, price + rng.choice((-1, 0, 0, 1)) * 0.1 * rng.randint(1, 3))
        out.append(Tick(timestamp_ms=ts, price=round(price, 2),
                        size=rng.choice((0.001, 0.005, 0.01, 0.02, 0.05, 0.4, 1.5)),
                        side=Side.BUY if rng.random() < 0.52 else Side.SELL))
    return out


DATA = ticks(N)


def bench(label: str, factory) -> None:
    tr = factory()
    t0 = time.perf_counter()
    for t in DATA:
        tr.on_tick(t)
    dt = time.perf_counter() - t0
    print(f"{label:<22} {dt:6.3f} s  {dt / N * 1e6:9.1f} µs/tick  {N / dt:9,.0f} ticks/s")


def main() -> int:
    bench("TapeFlow", lambda: TapeFlow("BTCUSDT", tick_size=0.1))
    bench("DepthHeatmap", lambda: DepthHeatmap("BTCUSDT", tick_size=0.1, bucket_ms=1000))
    bench("CvdTracker", lambda: CvdTracker("BTCUSDT", tick_size=0.1))
    bench("MarketProfile", lambda: MarketProfile("BTCUSDT", tick_size=0.1))
    bench("ImbalanceLadder", lambda: ImbalanceLadder("BTCUSDT", tick_size=0.1, min_volume=0.01))

    print("\n--- cProfile: TapeFlow ---")
    tf = TapeFlow("BTCUSDT", tick_size=0.1)
    pr = cProfile.Profile()
    pr.enable()
    for t in DATA:
        tf.on_tick(t)
    pr.disable()
    buf = StringIO()
    pstats.Stats(pr, stream=buf).sort_stats("cumulative").print_stats(12)
    print("\n".join(buf.getvalue().splitlines()[4:20]))

    print("\n--- cProfile: ImbalanceLadder ---")
    il = ImbalanceLadder("BTCUSDT", tick_size=0.1, min_volume=0.01)
    pr = cProfile.Profile()
    pr.enable()
    for t in DATA:
        il.on_tick(t)
    pr.disable()
    buf = StringIO()
    pstats.Stats(pr, stream=buf).sort_stats("cumulative").print_stats(12)
    print("\n".join(buf.getvalue().splitlines()[4:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
