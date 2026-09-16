#!/usr/bin/env python3
"""Golden snapshot of the analytics engines — the safety net for the numpy removal.

Why it exists: `analytics/volume_profile.py` and `analytics/delta.py` are being
rewritten from numpy to the standard library so the frozen build can drop numpy
(27 MB of the package). The rewrite is only safe if "the numbers did not move" is a
*verified* statement, not a promise — so every engine entry point is run on fixed,
deterministic fixtures and the results are serialised to one canonical JSON file.

    .venv/Scripts/python.exe scripts/regen_analytics_golden.py            # check (exit 1 on drift)
    .venv/Scripts/python.exe scripts/regen_analytics_golden.py --write    # accept a deliberate change

A deliberate change is a reviewed diff of exactly the case that changed. Floats are
compared with a 1e-9 tolerance (numpy's LAPACK polyfit and the stdlib least-squares
can disagree in the last bits); everything else must be identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orderflow_system.analytics.delta import DeltaEngine          # noqa: E402
from orderflow_system.analytics.volume_profile import VolumeProfileEngine  # noqa: E402
from orderflow_system.config.settings import VolumeProfileConfig  # noqa: E402
from orderflow_system.data.models import Candle, FootprintLevel, Side, Tick  # noqa: E402

GOLDEN = ROOT / "orderflow_system" / "testdata" / "analytics_golden.json"
TOL = 1e-9


# ── fixtures (deterministic; no RNG anywhere) ────────────────────────────────


def fixture_ticks() -> list[Tick]:
    """A session's worth of ticks: one heavy cluster, two shoulders, light extremes."""
    out: list[Tick] = []
    ts = 1_700_000_000_000

    def add(price: float, size: float, side: Side, count: int = 1) -> None:
        nonlocal ts
        for _ in range(count):
            out.append(Tick(ts, float(price), float(size), side))
            ts += 250

    add(18500.0, 10.0, Side.BUY, 100)
    add(18490.0, 5.0, Side.SELL, 50)
    add(18510.0, 5.0, Side.BUY, 50)
    add(18470.0, 1.0, Side.SELL, 5)
    add(18530.0, 1.0, Side.BUY, 5)
    return out


def fixture_candles(count: int, with_footprint: bool = True) -> list[Candle]:
    """Deterministic candles: both the footprint path and the even-distribution fallback."""
    out: list[Candle] = []
    for i in range(count):
        price = 100.0 + (i % 7) * 0.5
        vol = 100.0 + float((i * 13) % 40)
        buy = round(vol * (0.45 + (i % 5) * 0.05), 6)
        sell = round(vol - buy, 6)
        footprint: dict[float, FootprintLevel] = {}
        if with_footprint:
            for k in range(3):
                level = round(price + k * 0.5, 6)
                bid = round(buy / 3 * (1 + 0.1 * k), 6)
                ask = round(sell / 3 * (1 + 0.1 * k), 6)
                footprint[level] = FootprintLevel(level, bid_volume=bid, ask_volume=ask)
        out.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 60_000,
            open=price, high=price + 0.4, low=price - 0.4, close=price + 0.1,
            volume=vol, buy_volume=buy, sell_volume=sell,
            tick_count=10, footprint=footprint,
        ))
    return out


# Explicit volume-at-price shapes — the branches of _compute_profile, one each.
PROFILE_SHAPES: dict[str, dict[float, float]] = {
    # bell around the middle → d_shape
    "d_flat": {round(100.0 + i * 0.5, 6): float(100 - abs(i - 5) * 6) for i in range(11)},
    # rising ramp → POC at the top → p_shape
    "p_ramp": {round(100.0 + i * 0.5, 6): float(10 + 8 * i) for i in range(12)},
    # falling ramp → POC at the bottom → b_shape
    "b_ramp": {round(100.0 + i * 0.5, 6): float(200 - 8 * i) for i in range(12)},
    # one-sided: heavy cluster at the top, a thin tail below. The algorithm only ever walks
    # up here; VAL must stay BELOW the POC (v0.1b audit Tier 1.1 pin — the claimed inversion
    # does not reproduce: the invariant val <= poc <= vah holds and this case proves it).
    "poc_top_cluster": {round(100.0 + i * 0.5, 6): v for i, v in enumerate(
        [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 4.0, 6.0, 9.0, 12.0])},
    # POC at the bottom extreme with a fat shoulder above — val == poc is the CORRECT result
    # here (the value area has no lower neighbour it could include), pinned so a future
    # "fix" cannot silently widen the band.
    "poc_at_low": {round(100.0 + i * 0.5, 6): v for i, v in enumerate(
        [12.0, 9.0, 6.0, 4.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])},
    # two clusters with a deep valley → double_dist
    "double": {round(100.0 + i * 0.5, 6): v for i, v in enumerate(
        [80.0, 90.0, 95.0, 20.0, 15.0, 10.0, 18.0, 12.0, 88.0, 92.0, 96.0, 85.0])},
    # one level far below mean - 1.5σ and a local minimum → LVN
    "lvn": {round(100.0 + i * 0.5, 6): v for i, v in enumerate([100.0, 100.0, 5.0, 100.0, 100.0])},
    # below the 5-level LVN guard
    "small": {100.0: 10.0, 100.5: 20.0, 101.0: 30.0},
    # single level (argmax of length 1, shape fallback)
    "one": {100.0: 42.0},
    # total volume 0 → the empty result
    "zero": {100.0: 0.0, 100.5: 0.0},
}


def _vp_result_dict(res: Any) -> dict[str, Any]:
    return {
        "session_date": res.session_date,
        "poc": res.poc,
        "vah": res.vah,
        "val": res.val,
        "total_volume": res.total_volume,
        "lvn_levels": list(res.lvn_levels),
        "shape": res.shape,
        "poc_position_pct": res.poc_position_pct,
        "volume_at_price": [[p, res.volume_at_price[p]] for p in sorted(res.volume_at_price)],
    }


def _delta_result_dict(res: Any) -> dict[str, Any]:
    return {
        "vertical_delta": res.vertical_delta,
        "cumulative_delta": res.cumulative_delta,
        "delta_pct": res.delta_pct,
        "buy_volume": res.buy_volume,
        "sell_volume": res.sell_volume,
        "max_delta_price": res.max_delta_price,
        "min_delta_price": res.min_delta_price,
        "horizontal_delta": [[p, res.horizontal_delta[p]] for p in sorted(res.horizontal_delta)],
    }


# ── the snapshot ─────────────────────────────────────────────────────────────


def snapshot() -> dict[str, Any]:
    ticks = fixture_ticks()
    cases: dict[str, Any] = {}

    vp = VolumeProfileEngine(VolumeProfileConfig())

    for name, vap in PROFILE_SHAPES.items():
        cases[f"vp.shape.{name}"] = _vp_result_dict(vp._compute_profile(dict(vap), f"fx-{name}"))

    cases["vp.ticks.session"] = _vp_result_dict(vp.compute_from_ticks(ticks, "fx-ticks"))
    cases["vp.ticks.empty"] = _vp_result_dict(vp.compute_from_ticks([], "fx-empty"))
    cases["vp.candles.footprint"] = _vp_result_dict(
        vp.compute_from_candles(fixture_candles(12, True), "fx-candles-fp"))
    cases["vp.candles.fallback"] = _vp_result_dict(
        vp.compute_from_candles(fixture_candles(12, False), "fx-candles-nofp"))
    cases["vp.candles.empty"] = _vp_result_dict(vp.compute_from_candles([], "fx-empty"))

    p1 = vp.compute_from_candles(fixture_candles(6, True), "day-1")
    p2 = vp.compute_from_candles(fixture_candles(6, False), "day-2")
    cases["vp.merge.two"] = _vp_result_dict(vp.merge_profiles([p1, p2]))
    cases["vp.merge.one"] = _vp_result_dict(vp.merge_profiles([p1]))
    cases["vp.merge.empty"] = _vp_result_dict(vp.merge_profiles([]))

    # ── delta ───────────────────────────────────────────────────────────────
    dl = DeltaEngine(tick_size=0.1)
    per_candle = []
    for candle in fixture_candles(30, True):
        per_candle.append(_delta_result_dict(dl.compute_from_candle(candle)))
    cases["dl.candles.per_candle"] = per_candle
    cases["dl.candles.cumulative"] = dl.cumulative_delta
    cases["dl.candles.roc5"] = dl.get_delta_roc(5)
    cases["dl.candles.roc6"] = dl.get_delta_roc(6)
    cases["dl.candles.roc99"] = dl.get_delta_roc(99)      # lookback > history → 0.0
    cases["dl.candles.trend5"] = dl.get_volume_trend(5)
    peaks, troughs = dl.detect_delta_peaks(20)
    cases["dl.candles.peaks"] = [[i, v] for i, v in peaks]
    cases["dl.candles.troughs"] = [[i, v] for i, v in troughs]

    dl2 = DeltaEngine(tick_size=0.1)
    cases["dl.ticks.first"] = _delta_result_dict(dl2.compute_from_ticks(ticks))
    cases["dl.ticks.second"] = _delta_result_dict(dl2.compute_from_ticks(ticks))
    cases["dl.ticks.empty"] = _delta_result_dict(dl2.compute_from_ticks([]))
    cases["dl.ticks.roc2"] = dl2.get_delta_roc(2)
    cases["dl.ticks.trend2"] = dl2.get_volume_trend(2)

    dl3 = DeltaEngine(tick_size=0.1)
    for candle in fixture_candles(520, True):
        dl3.compute_from_candle(candle)
    cases["dl.cap.history_len"] = len(dl3.history)
    cases["dl.cap.cumulative"] = dl3.cumulative_delta
    cases["dl.cap.roc5"] = dl3.get_delta_roc(5)
    cases["dl.cap.trend5"] = dl3.get_volume_trend(5)
    long_peaks, long_troughs = dl3.detect_delta_peaks(500)
    cases["dl.cap.peaks_n"] = len(long_peaks)
    cases["dl.cap.troughs_n"] = len(long_troughs)
    cases["dl.cap.peaks_head"] = [[i, v] for i, v in long_peaks[:10]]

    dl4 = DeltaEngine(tick_size=0.1)
    dl4.compute_from_candle(fixture_candles(1, True)[0])
    cases["dl.single.roc5"] = dl4.get_delta_roc(5)
    cases["dl.single.trend5"] = dl4.get_volume_trend(5)

    # ── input digest: a fixture change must show up as drift ────────────────
    fixture_blob = json.dumps({
        "ticks": [[t.timestamp_ms, t.price, t.size, t.side.value] for t in ticks],
        "shapes": {k: [[p, v] for p, v in sorted(d.items())] for k, d in PROFILE_SHAPES.items()},
        "candles": [[c.timestamp_ms, c.open, c.high, c.low, c.close, c.volume,
                     c.buy_volume, c.sell_volume] for c in fixture_candles(30, True)],
    }, sort_keys=True)
    return {
        "fixtures_sha256": hashlib.sha256(fixture_blob.encode("utf-8")).hexdigest(),
        "cases": cases,
    }


# ── compare / check ──────────────────────────────────────────────────────────


def _walk_drift(a: Any, b: Any, path: str, out: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append(f"{path}.{key}: present on one side only")
            else:
                _walk_drift(a[key], b[key], f"{path}.{key}", out)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} -> {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _walk_drift(x, y, f"{path}[{i}]", out)
        return
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        if a != b:
            out.append(f"{path}: {a!r} -> {b!r}")
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=TOL):
            out.append(f"{path}: {a!r} -> {b!r} (delta {float(b) - float(a):+.3e})")
        return
    if a != b:
        out.append(f"{path}: {a!r} -> {b!r}")


def drift(stored: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """Every difference between the stored snapshot and the live one."""
    out: list[str] = []
    _walk_drift(stored, now, "golden", out)
    return out


def floats(stored: dict[str, Any], now: dict[str, Any]) -> tuple[int, float]:
    """(count of float leaves compared, max absolute difference seen)."""
    pairs: list[tuple[float, float]] = []

    def collect(a: Any, b: Any) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for key in set(a) & set(b):
                collect(a[key], b[key])
        elif isinstance(a, list) and isinstance(b, list):
            for x, y in zip(a, b):
                collect(x, y)
        elif (isinstance(a, (int, float)) and not isinstance(a, bool)
              and isinstance(b, (int, float)) and not isinstance(b, bool)):
            pairs.append((float(a), float(b)))

    collect(stored, now)
    worst = max((abs(x - y) for x, y in pairs), default=0.0)
    return len(pairs), worst


def main() -> int:
    parser = argparse.ArgumentParser(description="Analytics golden snapshot (numpy-removal safety net).")
    parser.add_argument("--write", action="store_true", help="write/accept the current output as the snapshot")
    args = parser.parse_args()

    now = snapshot()

    if args.write:
        text = json.dumps(now, indent=2, sort_keys=True) + "\n"
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
        n_cases = len(now["cases"])
        print(f"wrote {GOLDEN} ({len(text)} bytes, {n_cases} cases, "
              f"fixtures {now['fixtures_sha256'][:16]})")
        return 0

    if not GOLDEN.is_file():
        print(f"MISSING golden file: {GOLDEN}\nRun with --write to create it.")
        return 1

    stored = json.loads(GOLDEN.read_text(encoding="utf-8"))
    problems = drift(stored, now)
    n, worst = floats(stored, now)
    if problems:
        print(f"DRIFT — {len(problems)} difference(s):")
        for line in problems[:40]:
            print("  " + line)
        if len(problems) > 40:
            print(f"  … {len(problems) - 40} more")
        return 1
    print(f"analytics golden: OK — {len(now['cases'])} cases, {n} numeric leaves, "
          f"max diff {worst:.3e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
