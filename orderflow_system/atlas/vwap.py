"""VWAP suite — session VWAP, anchored VWAP and standard-deviation bands.

Modelled on the reference platform's *Order Flow VWAP* (+ the deviation bands traders use it
with), with one deliberate difference: crypto trades around the clock, so a "session"
is a convention rather than a bell. This module therefore offers both

* a **rolling session** VWAP (default 24 h), recomputed over a real sliding window, and
* an **anchored** VWAP that accumulates from a moment you pick (a swing, a news print,
  the session open) — the way a desk anchors a VWAP after an event.

Bands are the standard VWAP ± k·σ where σ is the volume-weighted standard deviation of
price about the VWAP:  σ² = Σ(p²·v)/Σv − VWAP².

Everything here is computed from public trades; no account, no key.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Optional

from orderflow_system.data.models import Tick
from orderflow_system.data.enums import as_value

BUCKET_MS = 60_000                     # one accumulation bucket per minute


def _side(tick: Tick) -> str:
    return as_value(tick.side)


class VWAPStudy:
    """Rolling-window VWAP with σ bands, plus an optional anchored VWAP."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        window_s: float = 86_400.0,          # rolling "session" (24 h of crypto)
        bands: tuple[float, ...] = (1.0, 2.0, 3.0),
        anchor_ms: int = 0,
        cross_min_ticks: float = 1.0,
        cross_cooldown_ms: int = 30_000,
        history_s: int = 200_000,
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.window_ms = int(max(60.0, float(window_s)) * 1000)
        self.bands = tuple(sorted(float(b) for b in bands if float(b) > 0)) or (1.0,)
        self.cross_min_ticks = max(0.0, float(cross_min_ticks))
        self.cross_cooldown_ms = int(max(0, cross_cooldown_ms))
        self._history_s = int(history_s)

        self.anchor_ms = int(anchor_ms or 0)
        # bucket -> [pv, v, p2v, open, close, high, low]  (all floats)
        self._buckets: dict[int, list[float]] = {}
        self._order: deque[int] = deque()          # bucket keys, oldest first
        self.last_price = 0.0
        self.version = 0
        self.crosses = 0
        self._last_cross_ms = 0
        self._last_side = 0                        # +1 above VWAP, -1 below, 0 on the line
        self._side_known = False                   # the first reading is not a crossing
        # anchored accumulation is exact (per print), not bucket-grained: an anchor can
        # land mid-minute, and pretending otherwise would pull the line up to 59 s early
        self._anchor_acc = [0.0, 0.0, 0.0, 0]      # [pv, v, p2v, prints]
        self._anchor_first_ms = 0

    # ── ingest ────────────────────────────────────────────────────
    def on_tick(self, tick: Tick) -> dict[str, Any]:
        """Accumulate one print; only prints after the anchor belong to the anchored study."""
        try:
            price = float(tick.price)
            size = abs(float(tick.size))
        except (TypeError, ValueError):
            return {}
        if price <= 0:
            return {}
        ts = int(tick.timestamp_ms or time.time() * 1000)
        self.version += 1
        self.last_price = price
        key = (ts // BUCKET_MS) * BUCKET_MS
        row = self._buckets.get(key)
        if row is None:
            row = [0.0, 0.0, 0.0, price, price, price, price]
            self._buckets[key] = row
            self._order.append(key)
        row[0] += price * size
        row[1] += size
        row[2] += price * price * size
        row[4] = price
        if price > row[5]:
            row[5] = price
        if price < row[6] or row[6] <= 0:
            row[6] = price
        if self.anchor_ms and ts >= self.anchor_ms:
            acc = self._anchor_acc
            acc[0] += price * size
            acc[1] += size
            acc[2] += price * price * size
            acc[3] += 1
            if not self._anchor_first_ms:
                self._anchor_first_ms = ts
        self._prune(ts)
        return self._cross_check(ts)

    def _prune(self, now_ms: int) -> None:
        cutoff = now_ms - max(self._history_s * 1000, self.window_ms * 2)
        while self._order and self._order[0] < cutoff:
            self._buckets.pop(self._order.popleft(), None)

    # ── maths ─────────────────────────────────────────────────────
    def _aggregate(self, rows: list[list[float]]) -> tuple[float, float, float]:
        """Return (vwap, sigma, volume) for a list of buckets."""
        pv = sum(r[0] for r in rows)
        v = sum(r[1] for r in rows)
        p2v = sum(r[2] for r in rows)
        if v <= 0:
            return 0.0, 0.0, 0.0
        vwap = pv / v
        var = max(0.0, p2v / v - vwap * vwap)
        return vwap, math.sqrt(var), v

    def _window_rows(self, now_ms: int) -> list[list[float]]:
        """The rolling-session window ending now.

        Buckets are minute-sized, so a bucket that merely *straddles* the window edge
        still holds prints from inside the window — dropping it would silently discard
        up to a minute of the most recent trading. Granularity is therefore one minute:
        the window can reach at most 59 s further back than asked.
        """
        start = now_ms - self.window_ms
        return [self._buckets[k] for k in self._order if k + BUCKET_MS > start]

    def _anchored_aggregate(self) -> tuple[float, float, float, int]:
        """Exact anchored VWAP: (vwap, sigma, volume, prints)."""
        pv, v, p2v, prints = self._anchor_acc
        if v <= 0:
            return 0.0, 0.0, 0.0, prints
        vwap = pv / v
        var = max(0.0, p2v / v - vwap * vwap)
        return vwap, math.sqrt(var), v, prints

    # ── crosses ───────────────────────────────────────────────────
    def _cross_check(self, now_ms: int) -> dict[str, Any]:
        vwap, _sigma, v = self._aggregate(self._window_rows(now_ms))
        if v <= 0 or vwap <= 0 or self.last_price <= 0:
            return {}
        if self.last_price == vwap:
            self._last_side = 0                     # sitting exactly on the line is its own state
            self._side_known = True
            return {}
        side = 1 if self.last_price > vwap else -1
        prev = self._last_side
        first_read = not self._side_known
        self._last_side = side
        self._side_known = True
        if first_read:
            return {}                               # the first reading is a position, not a crossing
        if side == prev:
            return {}
        if abs(self.last_price - vwap) / self.tick_size < self.cross_min_ticks:
            return {}
        if now_ms - self._last_cross_ms < self.cross_cooldown_ms:
            return {}
        self._last_cross_ms = now_ms
        self.crosses += 1
        return {"vwap_cross": {
            "ts_ms": now_ms, "price": self.last_price, "vwap": round(vwap, 8),
            "side": "above" if side > 0 else "below",
            "ticks": round((self.last_price - vwap) / self.tick_size, 2),
            "direction": "up" if side > 0 else "down",
        }}

    # ── anchor ────────────────────────────────────────────────────
    def set_anchor(self, ts_ms: Optional[int] = None) -> dict[str, Any]:
        """Anchor the second VWAP here (defaults to now).

        An anchor accumulates from the moment it is set: nothing in the past can be
        reconstructed honestly from a live feed, and saying so beats inventing it.
        """
        self.anchor_ms = int(ts_ms or time.time() * 1000)
        self._anchor_acc = [0.0, 0.0, 0.0, 0]
        self._anchor_first_ms = 0
        self.version += 1
        return {"anchor_ms": self.anchor_ms}

    def clear_anchor(self) -> None:
        self.anchor_ms = 0
        self._anchor_acc = [0.0, 0.0, 0.0, 0]
        self._anchor_first_ms = 0
        self.version += 1

    # ── output ────────────────────────────────────────────────────
    def snapshot(self, points: int = 240) -> dict[str, Any]:
        """Current VWAP/bands, the anchored line, and a chartable series."""
        now_ms = int(time.time() * 1000)
        rows = self._window_rows(now_ms)
        vwap, sigma, volume = self._aggregate(rows)
        ticks = self.tick_size or 1e-9
        out: dict[str, Any] = {
            "symbol": self.symbol,
            "vwap": round(vwap, 8),
            "sigma": round(sigma, 8),
            "volume": round(volume, 6),
            "window_s": int(self.window_ms / 1000),
            "bands": [],
            "last_price": self.last_price,
            "ticks_from_vwap": round((self.last_price - vwap) / ticks, 2) if vwap else None,
            "anchor_ms": self.anchor_ms,
            "anchored": None,
            "series": [],
            "version": self.version,
            "crosses": self.crosses,
        }
        if vwap:
            for k in self.bands:
                out["bands"].append({
                    "k": k,
                    "upper": round(vwap + k * sigma, 8),
                    "lower": round(vwap - k * sigma, 8),
                    "ticks_to_upper": round((vwap + k * sigma - self.last_price) / ticks, 2),
                    "ticks_to_lower": round((self.last_price - (vwap - k * sigma)) / ticks, 2),
                })
            # position of price inside the band envelope, -1 = at the lower 1σ band
            if sigma > 0:
                out["band_position"] = round((self.last_price - vwap) / sigma, 3)

        if self.anchor_ms:
            a_vwap, a_sigma, a_vol, a_prints = self._anchored_aggregate()
            out["anchored"] = {
                "anchor_ms": self.anchor_ms,
                "vwap": round(a_vwap, 8),
                "sigma": round(a_sigma, 8),
                "volume": round(a_vol, 6),
                "prints": a_prints,
                "exact_from_ms": self._anchor_first_ms,
                "minutes": round(max(0.0, (now_ms - self.anchor_ms) / 60_000.0), 1),
                "ticks_from_price": (round((self.last_price - a_vwap) / ticks, 2)
                                     if a_vwap else None),
                "bands": [{"k": k, "upper": round(a_vwap + k * a_sigma, 8),
                           "lower": round(a_vwap - k * a_sigma, 8)} for k in self.bands] if a_vwap else [],
            }

        # chartable series: the windowed VWAP and its bands at each bucket
        step = max(1, len(rows) // max(1, points))
        acc: list[list[float]] = []
        series: list[dict[str, Any]] = []
        for idx, key in enumerate(self._order):
            row = self._buckets.get(key)
            if row is None or key < now_ms - self.window_ms:
                continue
            acc.append(row)
            if idx % step:
                continue
            v, s, vol = self._aggregate(acc)
            if v:
                series.append({
                    "ts": key / 1000.0,
                    "vwap": round(v, 8),
                    "upper1": round(v + self.bands[0] * s, 8),
                    "lower1": round(v - self.bands[0] * s, 8),
                })
        out["series"] = series[-max(1, points):]
        return out

    def stats(self) -> dict[str, Any]:
        return {
            "buckets": len(self._buckets),
            "window_s": int(self.window_ms / 1000),
            "ticks_accumulated": self.version,
            "crosses": self.crosses,
            "anchored": bool(self.anchor_ms),
        }

    def clear(self) -> None:
        self._buckets.clear()
        self._order.clear()
        self._last_side = 0
        self.last_price = 0.0
