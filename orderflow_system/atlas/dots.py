"""
Volume-dot cluster map — the function of the reference platform's core "volume dots & bars clustering"
visualisation, rebuilt here from this build's own tape.

The three visualisations of the same instrument answer different questions: the footprint
buckets a bar into price rows (how much traded where), the depth heatmap draws resting size
(what was offered), and this draws executed prints over price × time (when business was done
and how it was split). the reference platform ships the dots on its free tier, so "reproducing the free
tier" starts here.

Clustering is what keeps a busy tape readable: forty taps at one price within a quarter of a
second are one bubble with a count of forty, not forty dots. Prints merge only when they
share an aggressor side, sit in the same price bucket, and fall inside ``cluster_ms`` —
mixing sides would hide exactly the flip a trader is looking for.

Prints smaller than ``min_size`` are dropped **before** clustering (a filter, not a display
setting), so a dust-heavy tape cannot inflate a bubble's count.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from orderflow_system.data.models import Tick

DEFAULT_WINDOW_MS = 300_000      # five minutes of tape
DEFAULT_CLUSTER_MS = 250         # prints closer together than this merge
DEFAULT_MAX_DOTS = 1_200         # hard ceiling on stored bubbles
DEFAULT_MAX_PAYLOAD = 600        # hard ceiling on what one request returns


@dataclass
class Dot:
    """One bubble: prints merged by side, price bucket and proximity in time."""
    ts_ms: int
    price: float
    size: float
    side: str
    count: int = 1
    last_ts_ms: int = 0

    @property
    def avg_size(self) -> float:
        return self.size / self.count if self.count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts_ms, "price": round(self.price, 10), "size": round(self.size, 10),
                "side": self.side, "count": self.count, "avg": round(self.avg_size, 10)}


class DotMap:
    """Rolling window of clustered prints for one instrument."""

    def __init__(self, symbol: str, tick_size: float = 1.0, window_ms: int = DEFAULT_WINDOW_MS,
                 cluster_ms: int = DEFAULT_CLUSTER_MS, min_size: float = 0.0,
                 max_dots: int = DEFAULT_MAX_DOTS) -> None:
        self.symbol = symbol
        self.tick_size = float(tick_size or 1.0)
        self.window_ms = max(1_000, int(window_ms))
        self.cluster_ms = max(0, int(cluster_ms))
        self.min_size = max(0.0, float(min_size))
        self.max_dots = max(50, int(max_dots))
        self._dots: list[Dot] = []
        self.kept = 0
        self.dropped = 0          # below the size filter
        self.merged = 0
        self.evicted = 0          # pushed out by the window or the cap

    # ── data in ──────────────────────────────────────────────────────
    def _bucket(self, price: float) -> float:
        tick = self.tick_size
        return round(price / tick) * tick if tick > 0 else price

    def on_tick(self, tick: Tick) -> Optional[Dot]:
        """Feed one print. Returns the bubble it landed in (existing or new)."""
        try:
            price = float(tick.price)
            size = float(tick.size)
        except (TypeError, ValueError, AttributeError):
            return None
        ts = int(tick.timestamp_ms or time.time() * 1000)
        if price <= 0 or size <= 0:
            return None
        if size < self.min_size:
            self.dropped += 1
            return None

        side = "buy" if getattr(tick, "is_buy", False) else "sell"
        bucket = self._bucket(price)
        last = self._dots[-1] if self._dots else None
        if (last is not None and last.side == side and last.price == bucket
                and ts - last.last_ts_ms <= self.cluster_ms):
            last.size += size
            last.count += 1
            last.last_ts_ms = ts
            last.ts_ms = min(last.ts_ms, ts)
            self.merged += 1
            self.kept += 1
            return last

        dot = Dot(ts_ms=ts, price=bucket, size=size, side=side, count=1, last_ts_ms=ts)
        self._dots.append(dot)
        self.kept += 1
        self._prune(ts)
        return dot

    def _prune(self, now_ms: int) -> None:
        cutoff = now_ms - self.window_ms
        if self._dots and self._dots[0].last_ts_ms < cutoff:
            keep = [d for d in self._dots if d.last_ts_ms >= cutoff]
            self.evicted += len(self._dots) - len(keep)
            self._dots = keep
        if len(self._dots) > self.max_dots:
            over = len(self._dots) - self.max_dots
            self.evicted += over
            del self._dots[:over]

    # ── data out ─────────────────────────────────────────────────────
    def stats(self) -> dict[str, Any]:
        buys = sum(1 for d in self._dots if d.side == "buy")
        return {
            "symbol": self.symbol,
            "bubbles": len(self._dots),
            "buy_bubbles": buys,
            "sell_bubbles": len(self._dots) - buys,
            "kept_prints": self.kept,
            "merged_prints": self.merged,
            "dropped_small": self.dropped,
            "evicted": self.evicted,
            "window_ms": self.window_ms,
            "cluster_ms": self.cluster_ms,
            "min_size": self.min_size,
            "tick_size": self.tick_size,
        }

    def snapshot(self, max_dots: int = DEFAULT_MAX_PAYLOAD, min_size: Optional[float] = None,
                 side: str = "") -> dict[str, Any]:
        """Bubbles (oldest first) plus a size legend for the caller's colour scale."""
        floor = self.min_size if min_size is None else max(0.0, float(min_size))
        want = (side or "").strip().lower()
        dots = [d for d in self._dots if d.size >= floor and (not want or d.side == want)]
        if len(dots) > max_dots:
            dots = sorted(dots, key=lambda d: -d.size)[:max_dots]
            dots.sort(key=lambda d: d.ts_ms)
        sizes = [d.size for d in dots]
        return {
            "symbol": self.symbol,
            "dots": [d.to_dict() for d in dots],
            "shown": len(dots),
            "stats": self.stats(),
            "legend": {"min": min(sizes) if sizes else 0.0, "max": max(sizes) if sizes else 0.0},
        }

    def clear(self) -> None:
        self._dots = []
        self.kept = self.merged = self.dropped = self.evicted = 0
