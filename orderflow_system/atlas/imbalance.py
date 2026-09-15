"""Stacked imbalance / imbalance-ratio ladder (the reference layout "Bid x Ask" imbalance rule).

the reference layout's footprint imbalance convention, from their own parameter tables:

    compare the bid volume at a price level with the ask volume one level ABOVE
    it as a percentage difference — default Imbalance Rate 150 %
    (their worked example: an ask of 30 at 350 % requires a bid > 105)

The mirror reading (ask volume at a level vs the bid volume one level BELOW)
marks the other side. Consecutive imbalanced levels in the same direction are
what the reference layout calls *stacked* imbalance — the reading that marks defended prices.

Both the level list and the stacked clusters are derived from executed prints
only (aggressor side), so no hidden-order assumptions are involved.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from orderflow_system.data.models import Tick
from orderflow_system.data.enums import as_value


@dataclass
class ImbalanceLevel:
    price: float
    side: str                 # bid = sellers absorbed here, ask = buyers absorbed
    volume: float             # this side's traded volume at the level
    other_volume: float       # the volume it is compared against (diagonal level)
    ratio_pct: float


@dataclass
class StackedCluster:
    side: str
    from_price: float
    to_price: float
    levels: int
    volume: float
    max_ratio_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side, "from_price": self.from_price, "to_price": self.to_price,
            "levels": self.levels, "volume": round(self.volume, 6),
            "max_ratio_pct": round(self.max_ratio_pct, 1),
        }


class ImbalanceLadder:
    """Rolling per-price bid/ask volumes + the reference layout imbalance rule."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        rate_pct: float = 150.0,
        window_ms: int = 300_000,
        min_volume: float = 0.0,
        max_prints: int = 40_000,
        alert_min_levels: int = 3,
        poll_interval_ms: int = 1_000,
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.rate_pct = float(rate_pct)
        self.window_ms = int(window_ms)
        self.min_volume = float(min_volume)
        self.alert_min_levels = int(alert_min_levels)
        self.poll_interval_ms = int(poll_interval_ms)

        # (ts_ms, level_price, side, size)
        self._prints: deque[tuple[int, float, str, float]] = deque(maxlen=int(max_prints))
        self._last_poll_ms = 0
        self.last_cluster: Optional[StackedCluster] = None

    # ── ingest ────────────────────────────────────────────────
    def on_tick(self, tick: Tick) -> dict[str, Any]:
        """Record one print; occasionally returns a fresh stacked cluster."""
        ts = int(tick.timestamp_ms or time.time() * 1000)
        side = as_value(tick.side)
        side = "buy" if side == "buy" else "sell"
        level = round(round(float(tick.price) / self.tick_size) * self.tick_size, 10)
        self._prints.append((ts, level, side, float(tick.size)))

        cutoff = ts - self.window_ms * 2
        while self._prints and self._prints[0][0] < cutoff:
            self._prints.popleft()

        if ts - self._last_poll_ms < self.poll_interval_ms:
            return {}
        self._last_poll_ms = ts
        clusters = self.clusters()
        if not clusters:
            return {}
        best = max(clusters, key=lambda c: (c.levels, c.volume))
        if best.levels < self.alert_min_levels:
            return {}
        if self.last_cluster and self._same_cluster(best, self.last_cluster, ts):
            return {}
        self.last_cluster = best
        return {"stacked_imbalance": best}

    def _same_cluster(self, a: StackedCluster, b: StackedCluster, ts: int) -> bool:
        """True when the new cluster is just the previous one seen again.

        A materially taller cluster, or one anchored at a different price, is a
        fresh reading and may alert; an unchanged repeat is suppressed.
        """
        if a.side != b.side:
            return False
        grew = a.levels >= b.levels + 2
        moved = abs(a.from_price - b.from_price) > self.tick_size * 2
        return not grew and not moved

    # ── reads ─────────────────────────────────────────────────
    def snapshot(self, max_levels: int = 120) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        bid_vol, ask_vol = self._volumes(now_ms)
        levels = self._levels(bid_vol, ask_vol)
        clusters = self._cluster(levels)
        shown = levels
        # keep the levels nearest the busiest prices when the list is long
        if len(shown) > max_levels:
            busiest = sorted(shown, key=lambda l: -l.volume)[:max_levels]
            shown = sorted(busiest, key=lambda l: -l.price)
        return {
            "symbol": self.symbol,
            "rate_pct": self.rate_pct,
            "window_ms": self.window_ms,
            "tick": self.tick_size,
            "prints": len(self._prints),
            "levels": [{
                "price": l.price, "side": l.side, "volume": round(l.volume, 6),
                "other_volume": round(l.other_volume, 6), "ratio_pct": round(l.ratio_pct, 1),
            } for l in shown],
            "stacked": [c.to_dict() for c in clusters],
            "counts": {
                "bid": sum(1 for l in levels if l.side == "bid"),
                "ask": sum(1 for l in levels if l.side == "ask"),
                "stacked": len(clusters),
            },
        }

    def clusters(self) -> list[StackedCluster]:
        bid_vol, ask_vol = self._volumes(int(time.time() * 1000))
        return self._cluster(self._levels(bid_vol, ask_vol))

    def clear(self) -> None:
        self._prints.clear()
        self._last_poll_ms = 0
        self.last_cluster = None

    # ── internals ─────────────────────────────────────────────
    def _volumes(self, now_ms: int) -> tuple[dict[float, float], dict[float, float]]:
        cutoff = now_ms - self.window_ms
        bid: dict[float, float] = {}
        ask: dict[float, float] = {}
        for ts, level, side, size in self._prints:
            if ts < cutoff:
                continue
            target = bid if side == "sell" else ask
            target[level] = target.get(level, 0.0) + size
        return bid, ask

    def _levels(self, bid: dict[float, float], ask: dict[float, float]) -> list[ImbalanceLevel]:
        """Apply the reference layout rule in both directions across neighbouring levels.

        "One level above" means the next *populated* price, not ``price + tick``:
        the printed grid does not always match the configured tick (BTCUSDT
        prints on a 0.1 grid while the repo's tick_size is 0.01), and level-vs-
        level is what the rule is about anyway.
        """
        out: list[ImbalanceLevel] = []
        prices = sorted(set(bid) | set(ask))
        min_v = self.min_volume

        def qualifies(volume: float, other: float) -> bool:
            """Both sides must exist, and both must clear the volume floor.

            Without the floor a level that saw a single 0.003 print next to a
            0.5 print reports a 17 000 % "imbalance" — technically the rule,
            practically noise.
            """
            if volume <= 0 or other <= 0:
                return False
            if min_v > 0 and (volume < min_v or other < min_v):
                return False
            return True

        for i, price in enumerate(prices):
            bid_here = bid.get(price, 0.0)
            ask_above = ask.get(prices[i + 1], 0.0) if i + 1 < len(prices) else 0.0
            if qualifies(bid_here, ask_above):
                ratio = bid_here / ask_above * 100.0
                if ratio >= self.rate_pct:
                    out.append(ImbalanceLevel(price=price, side="bid", volume=bid_here,
                                              other_volume=ask_above, ratio_pct=ratio))
                    continue
            ask_here = ask.get(price, 0.0)
            bid_below = bid.get(prices[i - 1], 0.0) if i > 0 else 0.0
            if qualifies(ask_here, bid_below):
                ratio = ask_here / bid_below * 100.0
                if ratio >= self.rate_pct:
                    out.append(ImbalanceLevel(price=price, side="ask", volume=ask_here,
                                              other_volume=bid_below, ratio_pct=ratio))
        return out

    def _cluster(self, levels: list[ImbalanceLevel]) -> list[StackedCluster]:
        """Group neighbouring same-side imbalances into stacked clusters.

        Neighbouring = consecutive ranks in the imbalance list itself, which is
        already sorted by price, so a gap in the book does not break a stack.
        """
        ordered = sorted(levels, key=lambda l: l.price)
        clusters: list[StackedCluster] = []
        run: list[ImbalanceLevel] = []
        for lvl in ordered:
            if run and lvl.side == run[-1].side:
                run.append(lvl)
                continue
            if len(run) >= 2:
                clusters.append(self._as_cluster(run))
            run = [lvl]
        if len(run) >= 2:
            clusters.append(self._as_cluster(run))
        return sorted(clusters, key=lambda c: (-c.levels, -c.volume))

    @staticmethod
    def _as_cluster(run: list[ImbalanceLevel]) -> StackedCluster:
        return StackedCluster(
            side=run[0].side,
            from_price=min(l.price for l in run),
            to_price=max(l.price for l in run),
            levels=len(run),
            volume=sum(l.volume for l in run),
            max_ratio_pct=max(l.ratio_pct for l in run),
        )
