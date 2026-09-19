"""
CVD and CVD Pro equivalents (the reference layout "CVD" / "CVD Pro" indicators).

CVD      = running sum of (buy volume − sell volume) from the session anchor.
CVD Pro  = the same plus the derived reads the reference layout exposes: multi-window deltas,
           slope, absorption (delta rising while price stalls) and price/delta
           divergence (price prints a new extreme, delta does not).

Everything is computed from executed prints; no assumptions about hidden orders.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from orderflow_system.data.models import Tick
from orderflow_system.data.enums import as_value


@dataclass
class CvdBucket:
    ts_ms: int
    price_high: float = 0.0
    price_low: float = 0.0
    price_close: float = 0.0
    buy: float = 0.0
    sell: float = 0.0
    cvd: float = 0.0
    ticks: int = 0


@dataclass
class Divergence:
    kind: str                 # bearish | bullish | absorption
    ts_ms: int
    price_now: float
    price_prev: float
    cvd_now: float
    cvd_prev: float
    strength: float           # 0-100
    note: str = ""


class CvdTracker:
    """Session-anchored CVD with multi-window deltas and divergence detection."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        bucket_ms: int = 5000,
        history: int = 1500,
        divergence_lookback: int = 24,
        divergence_min_ticks: float = 6.0,
        absorption_ticks: float = 3.0,
        absorption_min_delta: float = 0.0,
        windows_s: tuple[int, ...] = (60, 300, 900, 3600),
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.bucket_ms = int(bucket_ms)
        self.history = int(history)
        self.divergence_lookback = int(divergence_lookback)
        self.divergence_min_ticks = float(divergence_min_ticks)
        self.absorption_ticks = float(absorption_ticks)
        self.absorption_min_delta = float(absorption_min_delta)
        self.windows_s = tuple(windows_s)
        # the reference layout "CVD Pro" (formerly Market Power): a cumulative delta that only
        # counts trades inside a size band; max 0.0 means "no upper bound".
        self.pro_min_size: float = 0.0
        self.pro_max_size: float = 0.0
        self.pro_cvd: float = 0.0
        self._pro_by_bucket: dict[int, float] = {}
        # the reference layout "CVD Pro (Multi)": several size buckets, one cumulative line each
        self.pro_bands: list[tuple[float, float]] = []
        self.pro_band_cvd: list[float] = []
        self._pro_band_by_bucket: dict[int, list[float]] = {}

        self.cvd: float = 0.0
        self.session_start_ms: Optional[int] = None
        self.anchor_ms: Optional[int] = None
        self._buckets: deque[CvdBucket] = deque(maxlen=self.history)
        self.divergences: deque[Divergence] = deque(maxlen=60)
        self._last_price: float = 0.0

    # ── ingest ────────────────────────────────────────────────
    def on_tick(self, tick: Tick) -> None:
        ts = int(tick.timestamp_ms or time.time() * 1000)
        if self.session_start_ms is None:
            self.session_start_ms = ts
        side = as_value(tick.side)
        delta = float(tick.size) if side == "buy" else -float(tick.size)
        self.cvd += delta
        self._last_price = float(tick.price)

        size = float(tick.size)
        if self.pro_filter_passes(size):
            self.pro_cvd += delta
        for i, (lo, hi) in enumerate(self.pro_bands):
            if (not lo or size >= lo) and (not hi or size <= hi):
                if i < len(self.pro_band_cvd):
                    self.pro_band_cvd[i] += delta
                row = self._pro_band_by_bucket.setdefault(self._bucket(ts).ts_ms, [])
                while len(row) < len(self.pro_bands):
                    row.append(0.0)
                row[i] += delta

        bucket = self._bucket(ts)
        if side == "buy":
            bucket.buy += float(tick.size)
        else:
            bucket.sell += float(tick.size)
        bucket.ticks += 1
        bucket.cvd = self.cvd
        bucket.price_close = float(tick.price)
        bucket.price_high = max(bucket.price_high or float(tick.price), float(tick.price))
        bucket.price_low = min(bucket.price_low or float(tick.price), float(tick.price))
        if self.pro_filter_passes(float(tick.size)):
            self._pro_by_bucket[bucket.ts_ms] = self._pro_by_bucket.get(bucket.ts_ms, 0.0) + delta
            if len(self._pro_by_bucket) > self.history:
                for old in sorted(self._pro_by_bucket)[: len(self._pro_by_bucket) - self.history]:
                    self._pro_by_bucket.pop(old, None)

    def pro_filter_passes(self, size: float) -> bool:
        """True when a print of this size counts towards CVD Pro."""
        if self.pro_min_size and size < self.pro_min_size:
            return False
        if self.pro_max_size and size > self.pro_max_size:
            return False
        return True

    def set_pro_filter(self, min_size: float = 0.0, max_size: float = 0.0) -> dict[str, Any]:
        self.pro_min_size = max(0.0, float(min_size or 0.0))
        self.pro_max_size = max(0.0, float(max_size or 0.0))
        return {"min_size": self.pro_min_size, "max_size": self.pro_max_size}

    def set_pro_bands(self, bands: Iterable[Sequence[float]]) -> list[list[float]]:
        """Configure up to 5 size buckets (the reference layout 'CVD Pro (Multi)'), e.g. [[0,10],[10,100],[100,0]]."""
        clean: list[tuple[float, float]] = []
        for band in list(bands or [])[:5]:
            lo, hi = (list(band) + [0.0, 0.0])[:2]
            clean.append((max(0.0, float(lo or 0.0)), max(0.0, float(hi or 0.0))))
        self.pro_bands = clean
        self.pro_band_cvd = [0.0] * len(clean)
        self._pro_band_by_bucket.clear()
        return [[lo, hi] for lo, hi in clean]

    def pro_band_series(self, buckets: list[int]) -> list[list[float]]:
        """Cumulative value per band aligned to the bucket list."""
        running = [0.0] * len(self.pro_bands)
        out: list[list[float]] = []
        for b in buckets:
            row = self._pro_band_by_bucket.get(b) or []
            for i in range(len(running)):
                running[i] += row[i] if i < len(row) else 0.0
            out.append([round(v, 6) for v in running])
        return out

    def _bucket(self, ts_ms: int) -> CvdBucket:
        key = (ts_ms // self.bucket_ms) * self.bucket_ms
        if not self._buckets or self._buckets[-1].ts_ms != key:
            self._buckets.append(CvdBucket(ts_ms=key))
        return self._buckets[-1]

    # ── queries ───────────────────────────────────────────────
    def window_delta(self, seconds: int) -> float:
        """Net delta over the trailing N seconds."""
        if not self._buckets:
            return 0.0
        cutoff = self._buckets[-1].ts_ms - seconds * 1000
        return round(sum(b.buy - b.sell for b in self._buckets if b.ts_ms >= cutoff), 6)

    def slope(self, buckets: int = 10) -> float:
        """CVD change per bucket over the last N buckets (direction/momentum)."""
        rows = list(self._buckets)[-buckets:]
        if len(rows) < 2:
            return 0.0
        return round((rows[-1].cvd - rows[0].cvd) / max(1, len(rows) - 1), 6)

    def detect_divergence(self) -> Optional[Divergence]:
        """Price/delta divergence over the last two lookback halves."""
        n = self.divergence_lookback
        rows = list(self._buckets)
        if len(rows) < n * 2 + 1:
            return None
        prev, cur = rows[-2 * n:-n], rows[-n:]
        prev_high = max(b.price_high for b in prev)
        cur_high = max(b.price_high for b in cur)
        prev_lows = [b.price_low for b in prev if b.price_low]
        cur_lows = [b.price_low for b in cur if b.price_low]
        if not prev_lows or not cur_lows:
            # A zero or missing price is a malformed reading, not a divergence — every other
            # implausible input in this module answers None (audit C-06).
            return None
        prev_low = min(prev_lows)
        cur_low = min(cur_lows)

        min_move = self.divergence_min_ticks * self.tick_size
        div: Optional[Divergence] = None

        if cur_high - prev_high >= min_move and cur[-1].cvd < prev[-1].cvd:
            span = max(1e-9, cur_high - prev_high)
            div = Divergence("bearish", cur[-1].ts_ms, cur_high, prev_high, cur[-1].cvd, prev[-1].cvd,
                             strength=min(100.0, 40 + span / self.tick_size),
                             note="price made a higher high while CVD made a lower high — buyers not behind the move")
        elif prev_low - cur_low >= min_move and cur[-1].cvd > prev[-1].cvd:
            span = max(1e-9, prev_low - cur_low)
            div = Divergence("bullish", cur[-1].ts_ms, cur_low, prev_low, cur[-1].cvd, prev[-1].cvd,
                             strength=min(100.0, 40 + span / self.tick_size),
                             note="price made a lower low while CVD made a higher low — sellers not behind the move")
        elif abs(cur_high - prev_high) <= self.absorption_ticks * self.tick_size and abs(cur[-1].cvd - prev[-1].cvd) >= self.absorption_min_delta:
            div = Divergence("absorption", cur[-1].ts_ms, cur_high, prev_high, cur[-1].cvd, prev[-1].cvd,
                             strength=50.0,
                             note="delta moved while price stood still — one side is being absorbed")

        if div is not None and (not self.divergences or div.ts_ms != self.divergences[-1].ts_ms):
            self.divergences.append(div)
            return div
        return None

    def snapshot(self, series_buckets: int = 400) -> dict[str, Any]:
        rows = list(self._buckets)[-series_buckets:]
        cum = 0.0
        pro_series = []
        for b in rows:
            cum += self._pro_by_bucket.get(b.ts_ms, 0.0)
            pro_series.append(round(cum, 6))
        return {
            "symbol": self.symbol,
            "cvd": round(self.cvd, 6),
            "pro_multi": {
                "bands": [[lo, hi] for lo, hi in self.pro_bands],
                "cvd": [round(v, 6) for v in self.pro_band_cvd],
                "series": self.pro_band_series([b.ts_ms for b in rows]),
                "note": "up to 5 size buckets, one cumulative line each (the reference layout 'CVD Pro (Multi)')",
            },
            "pro": {
                "cvd": round(self.pro_cvd, 6),
                "min_size": self.pro_min_size,
                "max_size": self.pro_max_size,
                "note": "CVD Pro counts only prints inside the size band (the reference layout 'CVD Pro' / Market Power)",
                "series": pro_series,
            },
            "session_start_ms": self.session_start_ms,
            "anchor_ms": self.anchor_ms or self.session_start_ms,
            "windows": {f"{w}s": self.window_delta(w) for w in self.windows_s},
            "slope": self.slope(),
            "series": [{"t": b.ts_ms, "price": b.price_close, "cvd": round(b.cvd, 6),
                        "buy": round(b.buy, 6), "sell": round(b.sell, 6)} for b in rows],
            "divergences": [d.__dict__ for d in list(self.divergences)[-20:]],
        }

    def reanchor(self, ts_ms: Optional[int] = None) -> None:
        """Reset CVD from the current point (the reference layout 'anchor' behaviour)."""
        self.anchor_ms = int(ts_ms or (self._buckets[-1].ts_ms if self._buckets else time.time() * 1000))
        self.cvd = 0.0
        self.pro_cvd = 0.0
        self.pro_band_cvd = [0.0] * len(self.pro_bands)
        self._pro_by_bucket.clear()
        self._pro_band_by_bucket.clear()
        self._buckets.clear()

    def clear(self) -> None:
        self.cvd = 0.0
        self.pro_cvd = 0.0
        self.session_start_ms = None
        self.anchor_ms = None
        self._buckets.clear()
        self.divergences.clear()
        self._pro_by_bucket.clear()
