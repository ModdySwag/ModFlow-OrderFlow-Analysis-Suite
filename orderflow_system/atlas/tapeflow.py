"""
Print-side order-flow analytics (the reference layout: Time & Sales / Smart Tape / Speed of Tape /
Big Trades / Sweeps Tracker / Stop Runs Tracker / Iceberg Tracker).

Everything is derived from executed prints (`publicTrade`) plus, for stop-run
confirmation, the exchange liquidation stream (`allLiquidation`).

Terminology used here (all computed, never guessed):
  big trade    size ≥ adaptive percentile of the trailing print distribution
  block        size ≥ block_multiple × big-trade threshold
  sweep        one aggressor consuming ≥ min_levels price levels within max_ms
  iceberg      repeated same-size refills at one price (MBO *inference* — the
               venue never exposes order ids publicly)
  stop run     fast directional move through liquidity with a volume burst,
               optionally confirmed by a liquidation cluster
  speed        trades/second and size/second with z-score spike detection
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from orderflow_system.data.models import Tick
from orderflow_system.data.enums import as_value


@dataclass
class BigTrade:
    ts_ms: int
    price: float
    size: float
    side: str
    multiple: float = 1.0          # × adaptive threshold
    reassembled: bool = False      # built from fragmented prints
    fragments: int = 1             # how many prints the aggregate covers

    @property
    def is_block(self) -> bool:
        return self.multiple >= 3.0


@dataclass
class SweepEvent:
    ts_ms: int
    side: str
    levels: int
    size: float
    from_price: float
    to_price: float
    duration_ms: int
    aggressors: int = 0             # separate prints reassembled (the reference layout "Aggressors Count")
    range_ticks: float = 0.0        # price span in instrument ticks (the reference layout "Min Range (ticks)")


@dataclass
class StopRunEvent:
    ts_ms: int
    direction: str                  # up | down
    ticks_moved: float
    volume: float
    duration_ms: int
    from_price: float
    to_price: float
    confirmed_by_liquidations: bool = False
    prints: int = 0                 # stop aggressors folded into the run (the reference layout "Stops Count")


@dataclass
class IcebergEvent:
    ts_ms: int
    price: float
    side: str
    fills: int
    total_size: float
    modal_size: float
    duration_ms: int = 0            # lifetime of the refilling level (the reference layout "Min Duration (sec)")
    confidence: str = "inferred"    # the reference layout grades Absolute (native refresh) vs Medium; from
                                    # L2 + prints we can only ever claim "inferred"


@dataclass
class LiquidationEvent:
    ts_ms: int
    price: float
    size: float
    side: str                       # side of the liquidated position


class TapeFlow:
    """Rolling tape analytics with reference-style detectors."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        hist_size: int = 4000,
        big_quantile: float = 0.99,
        big_min_size: float = 0.0,
        block_multiple: float = 3.0,
        sweep_levels: int = 5,
        sweep_max_ms: int = 120,
        sweep_min_size: float = 0.0,
        sweep_min_aggressors: int = 1,
        sweep_min_range_ticks: float = 0.0,
        iceberg_min_fills: int = 4,
        iceberg_size_tol: float = 0.15,
        iceberg_max_ms: int = 8000,
        iceberg_min_size: float = 0.0,
        iceberg_min_total: float = 0.0,
        iceberg_min_duration_ms: int = 0,
        stoprun_ticks: float = 12.0,
        stoprun_ms: int = 3000,
        stoprun_vol_z: float = 2.0,
        stoprun_min_volume: float = 0.0,
        stoprun_min_prints: int = 1,
        speed_windows: tuple[int, ...] = (1, 5, 15),
        reassembly_ms: int = 80,
        zone_ticks: float = 100.0,
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.hist_size = int(hist_size)
        self.big_quantile = float(big_quantile)
        self.big_min_size = float(big_min_size)
        self.block_multiple = float(block_multiple)
        self.sweep_levels = int(sweep_levels)
        self.sweep_max_ms = int(sweep_max_ms)
        self.sweep_min_size = float(sweep_min_size)
        self.sweep_min_aggressors = int(sweep_min_aggressors)
        self.sweep_min_range_ticks = float(sweep_min_range_ticks)
        self.iceberg_min_fills = int(iceberg_min_fills)
        self.iceberg_size_tol = float(iceberg_size_tol)
        self.iceberg_max_ms = int(iceberg_max_ms)
        self.iceberg_min_size = float(iceberg_min_size)
        self.iceberg_min_total = float(iceberg_min_total)
        self.iceberg_min_duration_ms = int(iceberg_min_duration_ms)
        self.stoprun_ticks = float(stoprun_ticks)
        self.stoprun_ms = int(stoprun_ms)
        self.stoprun_vol_z = float(stoprun_vol_z)
        self.stoprun_min_volume = float(stoprun_min_volume)
        self.stoprun_min_prints = int(stoprun_min_prints)
        self.speed_windows = tuple(speed_windows)

        self._prints: deque[Tick] = deque(maxlen=self.hist_size)
        self._sizes: deque[float] = deque(maxlen=self.hist_size)
        # ≤1 print quantile rebuild interval + per-second aggregates (see big_threshold
        # and _update_stop_run): both keep the per-tick path free of full-ring scans
        self._THRESHOLD_EVERY = 25
        self._appends = 0
        self._threshold: Optional[float] = None
        self._threshold_at: Optional[int] = None
        self._sec_trace: dict[int, list[float]] = {}
        self.big_trades: deque[BigTrade] = deque(maxlen=300)
        self.sweeps: deque[SweepEvent] = deque(maxlen=200)
        self.stop_runs: deque[StopRunEvent] = deque(maxlen=100)
        self.icebergs: deque[IcebergEvent] = deque(maxlen=200)
        self.liquidations: deque[LiquidationEvent] = deque(maxlen=400)

        self._sweep_buf: list[Tick] = []
        self._sweep_side: Optional[str] = None
        self._print_stats: list[tuple[int, float, float]] = []   # (ts_ms, price, size)
        self._iceberg_last: dict[float, tuple[int, int]] = {}    # price -> (ts, fills)
        self._iceberg_last_price: Optional[float] = None
        self._last_liquidation_ts: dict[float, int] = {}
        self._volume_by_second: dict[int, float] = {}
        self._trades_by_second: dict[int, int] = {}

        # fragmented-print reassembly + big-trade zones
        self.reassembly_ms = max(0, int(reassembly_ms))
        self.zone_ticks = max(1.0, float(zone_ticks))
        self._frag_buf: list[tuple[int, float, str, float]] = []   # ts, price, side, size
        self._frag_total: dict[float, float] = {}                   # price -> last aggregate
        self._zones: dict[float, dict[str, float]] = {}             # zone base -> totals

    # ── ingest ────────────────────────────────────────────────
    def on_tick(self, tick: Tick) -> dict[str, Any]:
        """Feed one print. Returns a dict of detections triggered by it."""
        out: dict[str, Any] = {}
        ts = int(tick.timestamp_ms or time.time() * 1000)
        side = as_value(tick.side)

        self._prints.append(tick)
        self._sizes.append(float(tick.size))
        self._appends += 1
        sec = ts // 1000
        self._volume_by_second[sec] = self._volume_by_second.get(sec, 0.0) + float(tick.size)
        self._trades_by_second[sec] = self._trades_by_second.get(sec, 0) + 1
        # per-second trace [first, last, lo, hi, volume, prints] — lets the stop-run
        # detector read ~4 buckets instead of rescanning the whole 4,000-print ring
        # on every tick (the reference layout performance guide: hoist work out of the per-event path)
        trace = self._sec_trace.get(sec)
        pk = float(tick.price)
        if trace is None:
            self._sec_trace[sec] = [pk, pk, pk, pk, float(tick.size), 1.0]
        else:
            trace[1] = pk
            if pk < trace[2]:
                trace[2] = pk
            if pk > trace[3]:
                trace[3] = pk
            trace[4] += float(tick.size)
            trace[5] += 1.0
        if len(self._volume_by_second) > 600:
            # evict oldest keys in insertion order — no sort per tick
            while len(self._volume_by_second) > 600:
                old = next(iter(self._volume_by_second))
                self._volume_by_second.pop(old, None)
                self._trades_by_second.pop(old, None)
                self._sec_trace.pop(old, None)

        # 1. big trade — a single large print, or fragmented prints reassembled
        thr = self.big_threshold()
        if thr > 0 and float(tick.size) >= thr:
            bt = BigTrade(ts_ms=ts, price=float(tick.price), size=float(tick.size), side=side,
                          multiple=round(float(tick.size) / thr, 2))
            self._record_big_trade(bt, out)
        elif thr > 0:
            self._update_reassembly(tick, side, ts, thr, out)

        # 2. sweep (consecutive same-side prints across levels)
        self._update_sweep(tick, side, ts, out)

        # 3. iceberg inference on prints
        self._update_iceberg(tick, side, ts, out)

        # 4. stop run
        sr = self._update_stop_run(ts)
        if sr:
            out["stop_run"] = sr

        # 5. speed spike
        spike = self.speed_spike()
        if spike:
            out["speed_spike"] = spike
        return out

    def on_liquidation(self, price: float, size: float, side: str, ts_ms: Optional[int] = None) -> Optional[StopRunEvent]:
        """Feed an exchange liquidation; returns a stop-run confirmation if clustered."""
        ts = int(ts_ms or time.time() * 1000)
        price = float(price)
        self.liquidations.append(LiquidationEvent(ts_ms=ts, price=price, size=float(size), side=str(side)))
        self._last_liquidation_ts[price] = ts

        window = [l for l in self.liquidations if ts - l.ts_ms <= self.stoprun_ms]
        cluster = [l for l in window if abs(l.price - price) <= self.stoprun_ticks * self.tick_size]
        if len(cluster) >= 3:
            total = sum(l.size for l in cluster)
            for sr in reversed(self.stop_runs):
                if ts - sr.ts_ms <= self.stoprun_ms * 2:
                    sr.confirmed_by_liquidations = True
                    sr.permanent_note = f"{len(cluster)} liquidations ({total:.2f}) at {price}"  # type: ignore[attr-defined]
                    return sr
            direction = "down" if str(side).lower().startswith("sell") else "up"
            sr = StopRunEvent(ts_ms=ts, direction=direction, ticks_moved=0.0, volume=total,
                              duration_ms=self.stoprun_ms, from_price=price, to_price=price,
                              confirmed_by_liquidations=True)
            sr.permanent_note = f"{len(cluster)} liquidations ({total:.2f}) in {self.stoprun_ms}ms"  # type: ignore[attr-defined]
            self.stop_runs.append(sr)
            return sr
        return None

    # ── big-trade reassembly + zones ──────────────────────────
    def _record_big_trade(self, bt: BigTrade, out: dict) -> None:
        self.big_trades.append(bt)
        self._accumulate_zone(bt)
        out["big_trade"] = bt
        if bt.is_block:
            out["block_trade"] = bt

    def _update_reassembly(self, tick: Tick, side: str, ts: int, thr: float, out: dict) -> None:
        """Fragmented prints at one price, same side, inside the window → one trade.

        the reference layout's Big Trades indicator reassembles split executions into the original
        large trade. A run only reports once its aggregate crosses the adaptive
        threshold, and only when it has grown past the last reported total — so a
        steady drumbeat at one price does not spam the table.
        """
        if self.reassembly_ms <= 0:
            return
        price = round(round(float(tick.price) / self.tick_size) * self.tick_size, 10)
        self._frag_buf = [f for f in self._frag_buf if ts - f[0] <= self.reassembly_ms]
        if self._frag_buf and (self._frag_buf[-1][2] != side or self._frag_buf[-1][1] != price):
            self._frag_buf = []                       # a run is same side + same price
        self._frag_buf.append((ts, price, side, float(tick.size)))
        total = sum(f[3] for f in self._frag_buf)
        if len(self._frag_buf) < 2 or total < thr:
            return
        prev = self._frag_total.get(price, 0.0)
        if prev and total < prev * 2.0:
            return                                    # reported already; wait for it to double
        self._frag_total[price] = total
        bt = BigTrade(ts_ms=ts, price=price, size=round(total, 6), side=side,
                      multiple=round(total / thr, 2), reassembled=True, fragments=len(self._frag_buf))
        self._record_big_trade(bt, out)

    def _zone_key(self, price: float) -> float:
        zone = max(self.tick_size * self.zone_ticks, 1e-9)
        return round(math.floor(price / zone) * zone, 10)

    def _accumulate_zone(self, bt: BigTrade) -> None:
        base = self._zone_key(bt.price)
        z = self._zones.get(base)
        if z is None:
            z = self._zones[base] = {"buy": 0.0, "sell": 0.0, "count": 0.0,
                                     "first_ms": float(bt.ts_ms), "last_ms": float(bt.ts_ms)}
        z["buy" if bt.side == "buy" else "sell"] += bt.size
        z["count"] += 1
        z["last_ms"] = float(bt.ts_ms)
        z["first_ms"] = min(z["first_ms"], float(bt.ts_ms))

    def zones(self, top: int = 12) -> list[dict[str, Any]]:
        """Price zones that collected the most big-trade volume this session."""
        zone = max(self.tick_size * self.zone_ticks, 1e-9)
        rows = []
        for base, z in self._zones.items():
            buy, sell = z["buy"], z["sell"]
            rows.append({
                "zone_price": base, "zone_size": round(zone, 10),
                "buy": round(buy, 6), "sell": round(sell, 6), "total": round(buy + sell, 6),
                "delta": round(buy - sell, 6), "count": int(z["count"]),
                "first_ms": int(z["first_ms"]), "last_ms": int(z["last_ms"]),
            })
        rows.sort(key=lambda r: -r["total"])
        return rows[:top]

    # ── metrics ───────────────────────────────────────────────
    def big_threshold(self) -> float:
        """Adaptive big-trade size: high quantile of the trailing distribution.

        Rebuilt at most every ``_THRESHOLD_EVERY`` prints. Sorting the whole
        4,000-print ring on every tick costs ~50 µs of an ~800 µs tick path, and a
        threshold that trails by a few dozen prints is the same threshold in
        practice — the same trade-off the reference layout's performance page recommends.
        """
        if len(self._sizes) < 50:
            return self.big_min_size
        if self._threshold is not None and self._threshold_at is not None \
                and self._appends - self._threshold_at < self._THRESHOLD_EVERY:
            return self._threshold
        ordered = sorted(self._sizes)
        idx = min(len(ordered) - 1, int(self.big_quantile * len(ordered)))
        thr = max(ordered[idx], self.big_min_size)
        self._threshold, self._threshold_at = thr, self._appends
        return thr

    def speed(self) -> dict[str, Any]:
        """Trades/s and size/s over the configured windows, plus spike z-scores.

        Mean/stdev are computed with plain float maths over the last 300 seconds in
        insertion order (the dict's keys are seconds, so insertion order is
        chronological). ``statistics.mean/pstdev`` convert every element to an exact
        ``Fraction`` — measured at ~450 µs per call, on the per-tick path.
        """
        now = int(time.time())
        out: dict[str, Any] = {"windows": {}}
        for w in self.speed_windows:
            vol = sum(self._volume_by_second.get(s, 0.0) for s in range(now - w + 1, now + 1))
            cnt = sum(self._trades_by_second.get(s, 0) for s in range(now - w + 1, now + 1))
            out["windows"][f"{w}s"] = {"trades": cnt, "volume": round(vol, 6),
                                       "trades_per_s": round(cnt / w, 3), "size_per_s": round(vol / w, 6)}
        hist = list(self._volume_by_second.values())[-300:]
        if len(hist) >= 30:
            n = len(hist)
            mu = sum(hist) / n
            variance = sum((x - mu) ** 2 for x in hist) / n          # population stdev, as before
            sd = math.sqrt(variance) if variance > 0 else 1e-9
            cur = self._volume_by_second.get(now, 0.0)
            out["zscore"] = round((cur - mu) / (sd or 1e-9), 2)
            out["mean_size_per_s"] = round(mu, 6)
        return out

    def speed_spike(self, z: float = 3.0) -> Optional[dict[str, Any]]:
        s = self.speed()
        if s.get("zscore", 0.0) >= z and s["windows"].get("5s", {}).get("volume", 0) > 0:
            return {"zscore": s["zscore"], "volume_5s": s["windows"]["5s"]["volume"],
                    "trades_5s": s["windows"]["5s"]["trades"]}
        return None

    def stats(self) -> dict[str, Any]:
        buy = sum(t.size for t in self._prints if _side(t) == "buy")
        sell = sum(t.size for t in self._prints if _side(t) == "sell")
        big_buy = sum(b.size for b in self.big_trades if b.side == "buy")
        big_sell = sum(b.size for b in self.big_trades if b.side == "sell")
        return {
            "prints": len(self._prints),
            "volume": round(buy + sell, 6),
            "buy_volume": round(buy, 6),
            "sell_volume": round(sell, 6),
            "delta": round(buy - sell, 6),
            "big_threshold": round(self.big_threshold(), 6),
            "big_trades": len(self.big_trades),
            "blocks": sum(1 for b in self.big_trades if b.is_block),
            "big_delta": round(big_buy - big_sell, 6),
            "sweeps": len(self.sweeps),
            "stop_runs": len(self.stop_runs),
            "icebergs": len(self.icebergs),
            "liquidations": len(self.liquidations),
            "reassembled": sum(1 for b in self.big_trades if b.reassembled),
            "zones": len(self._zones),
            "speed": self.speed(),
        }

    def recent(self, count: int = 60) -> list[dict]:
        return [{
            "ts": t.timestamp_ms / 1000, "price": float(t.price), "size": float(t.size), "side": _side(t),
        } for t in list(self._prints)[-count:]]

    def events(self) -> dict[str, list[dict]]:
        return {
            "big_trades": [b.__dict__ for b in list(self.big_trades)[-40:]],
            "sweeps": [s.__dict__ for s in list(self.sweeps)[-30:]],
            "stop_runs": [{**s.__dict__, "note": getattr(s, "permanent_note", "")} for s in list(self.stop_runs)[-20:]],
            "icebergs": [i.__dict__ for i in list(self.icebergs)[-30:]],
            "liquidations": [l.__dict__ for l in list(self.liquidations)[-60:]],
            "zones": self.zones(12),
        }

    def clear(self) -> None:
        for q in (self._prints, self._sizes, self.big_trades, self.sweeps, self.stop_runs, self.icebergs, self.liquidations):
            q.clear()
        self._sweep_buf.clear()
        self._print_stats.clear()
        self._iceberg_last.clear()
        self._iceberg_last_price = None
        self._volume_by_second.clear()
        self._trades_by_second.clear()
        self._sec_trace.clear()
        self._threshold = None
        self._threshold_at = None
        self._appends = 0
        self._frag_buf.clear()
        self._frag_total.clear()
        self._zones.clear()

    # ── detectors ─────────────────────────────────────────────
    def _update_sweep(self, tick: Tick, side: str, ts: int, out: dict) -> None:
        self._sweep_buf = [t for t in self._sweep_buf if ts - int(t.timestamp_ms) <= self.sweep_max_ms]
        if self._sweep_side != side:
            self._sweep_buf = []
            self._sweep_side = side
        self._sweep_buf.append(tick)

        prices = {float(t.price) for t in self._sweep_buf}
        size = sum(float(t.size) for t in self._sweep_buf)
        aggressors = len(self._sweep_buf)
        prices_sorted = sorted(prices)
        range_ticks = (prices_sorted[-1] - prices_sorted[0]) / self.tick_size if prices else 0.0
        if (len(prices) >= self.sweep_levels and size >= self.sweep_min_size
                and aggressors >= self.sweep_min_aggressors
                and range_ticks >= self.sweep_min_range_ticks):
            ev = SweepEvent(
                ts_ms=ts, side=side, levels=len(prices), size=round(size, 6),
                from_price=prices_sorted[0], to_price=prices_sorted[-1],
                duration_ms=ts - int(self._sweep_buf[0].timestamp_ms),
                aggressors=aggressors, range_ticks=round(range_ticks, 2),
            )
            self.sweeps.append(ev)
            out["sweep"] = ev
            self._sweep_buf = []

    def _update_iceberg(self, tick: Tick, side: str, ts: int, out: dict) -> None:
        price = round(round(float(tick.price) / self.tick_size) * self.tick_size, 10)
        self._print_stats.append((ts, price, float(tick.size)))
        self._print_stats = [row for row in self._print_stats if ts - row[0] <= self.iceberg_max_ms]

        same = [row for row in self._print_stats if row[1] == price]
        if len(same) < self.iceberg_min_fills:
            return
        sizes = [row[2] for row in same]
        modal = max(set(sizes), key=sizes.count)
        if modal <= 0:
            return
        similar = [s for s in sizes if abs(s - modal) <= self.iceberg_size_tol * modal]
        if len(similar) < self.iceberg_min_fills or len(similar) / len(sizes) < 0.7:
            return
        if modal < self.iceberg_min_size:
            return
        if self.iceberg_min_total and sum(sizes) < self.iceberg_min_total:
            return
        first_ts = min(row[0] for row in same)
        lifetime = ts - first_ts
        if self.iceberg_min_duration_ms and lifetime < self.iceberg_min_duration_ms:
            return

        # emit once per price, then only when the refill count has grown materially
        last_ts, last_fills = self._iceberg_last.get(price, (0, 0))
        if price == getattr(self, "_iceberg_last_price", None) and ts - last_ts <= self.iceberg_max_ms and len(similar) < last_fills + 2:
            return
        self._iceberg_last[price] = (ts, len(similar))
        self._iceberg_last_price = price
        ev = IcebergEvent(ts_ms=ts, price=price, side=side, fills=len(similar),
                          total_size=round(sum(sizes), 6), modal_size=modal,
                          duration_ms=lifetime, confidence="inferred")
        self.icebergs.append(ev)
        out["iceberg"] = ev

    def _update_stop_run(self, ts: int) -> Optional[StopRunEvent]:
        """Detect a stop run from the per-second aggregates.

        The window is ``stoprun_ms`` wide, read from the second buckets the ingest
        path already maintains — the previous version rescanned the whole 4,000
        print ring (~356 µs) on every tick. Aggregates are second-granular, so the
        window can reach back up to one second further than the exact millisecond
        cut-off; volume, prints, range and direction are otherwise identical.
        """
        if len(self._prints) < 10:
            return None
        ts_lo = ts - self.stoprun_ms
        oldest = int(self._prints[0].timestamp_ms)          # never count prints the ring dropped
        if oldest > ts_lo:
            ts_lo = oldest
        hi = float("-inf")
        lo = float("inf")
        volume = 0.0
        prints = 0.0
        first_price: Optional[float] = None
        last_price = 0.0
        for sec in range(ts_lo // 1000, ts // 1000 + 1):
            trace = self._sec_trace.get(sec)
            if trace is None:
                continue
            if first_price is None:
                first_price = trace[0]
            last_price = trace[1]
            if trace[2] < lo:
                lo = trace[2]
            if trace[3] > hi:
                hi = trace[3]
            volume += trace[4]
            prints += trace[5]
        if prints < 10 or first_price is None:
            return None
        move_ticks = (hi - lo) / self.tick_size
        if move_ticks < self.stoprun_ticks:
            return None
        if volume < self.stoprun_min_volume or prints < self.stoprun_min_prints:
            return None
        if self.stoprun_min_prints > 1 and self.stoprun_vol_z <= 0:
            return None                                     # keeps the old fast path for defaults
        speeds = self._volume_by_second
        if len(speeds) >= 30:
            vals = list(speeds.values())[-300:]
            n = len(vals)
            mu = sum(vals) / n
            variance = sum((x - mu) ** 2 for x in vals) / n
            sd = math.sqrt(variance) if variance > 0 else 1e-9
            local = sum(speeds.get((ts // 1000) - i, 0.0) for i in range(0, max(1, self.stoprun_ms // 1000) + 1))
            if (local - mu) / (sd or 1e-9) < self.stoprun_vol_z:
                return None
        direction = "up" if last_price >= first_price else "down"
        ev = StopRunEvent(ts_ms=ts, direction=direction, ticks_moved=round(move_ticks, 2),
                          volume=round(volume, 6), duration_ms=self.stoprun_ms,
                          from_price=first_price, to_price=last_price, prints=int(prints))
        if not self.stop_runs or ts - self.stop_runs[-1].ts_ms > self.stoprun_ms:
            self.stop_runs.append(ev)
            return ev
        return None


def _side(tick: Tick) -> str:
    return as_value(tick.side)
