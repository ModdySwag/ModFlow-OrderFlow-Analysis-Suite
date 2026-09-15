"""
Cross-instrument correlation tracker — the function of the reference platform's "Correlation Tracker"
add-on (Global tier there), rebuilt here against this build's own stream.

A single-instrument order-flow view cannot answer the portfolio question: are these two
instruments still moving together, or has that relationship broken? This keeps a rolling
matrix of return correlations across every instrument the engine streams.

Method, and why: each instrument's last print is sampled into fixed time buckets (60 s by
default). Log returns are computed between consecutive buckets, and a pair's Pearson
correlation is computed over the buckets **both** instruments actually traded in. Buckets
are never forward-filled — a filled return is not a return, and it is the fastest way to
invent a correlation that does not exist. The shared sample count travels with every
number, so a 0.91 on six buckets can never be mistaken for a signal.

Nothing here knows about the book or the tape: it is arithmetic over prices this build has
already streamed or stored, so it also works in replay and from backfilled candles.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Iterable, Optional

DEFAULT_BUCKET_MS = 60_000     # one sample per minute per instrument
DEFAULT_WINDOW = 120           # buckets kept per instrument (~2 h)
MIN_SAMPLES = 10               # below this many shared buckets, report "insufficient"


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    """Pearson r, or None when a series has no real dispersion (see the guard below)."""
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx <= 0 or dy <= 0:
        return None
    std_x = dx / math.sqrt(n)
    std_y = dy / math.sqrt(n)
    # A constant-rate move (every bucket up 1%) has *identical* returns, so its dispersion is
    # float rounding noise. Pearson over that residue is noise dressed up as a correlation —
    # it was measured at 0.73 on a pair that is perfectly in phase — so require the returns to
    # actually vary before any number is reported.
    if std_x <= 1e-9 * max(abs(mx), 1e-9) or std_y <= 1e-9 * max(abs(my), 1e-9):
        return None
    return num / (dx * dy)


class CorrelationTracker:
    """Rolling pairwise correlation of log returns, with honest sample counts."""

    def __init__(self, bucket_ms: int = DEFAULT_BUCKET_MS, window: int = DEFAULT_WINDOW,
                 min_samples: int = MIN_SAMPLES) -> None:
        self.bucket_ms = max(1_000, int(bucket_ms))
        self.window = max(4, int(window))
        self.min_samples = max(3, int(min_samples))
        self._series: dict[str, deque[tuple[int, float]]] = {}

    # ── data in ──────────────────────────────────────────────────────
    def on_tick(self, symbol: str, price: float, ts_ms: Optional[int] = None) -> None:
        """Record a print into its time bucket (last print = the bucket's close)."""
        try:
            price = float(price)
        except (TypeError, ValueError):
            return
        if not symbol or price <= 0:
            return
        ts = int(ts_ms if ts_ms is not None else time.time() * 1000)
        bucket = ts - (ts % self.bucket_ms)
        series = self._series.setdefault(symbol, deque(maxlen=self.window + 1))
        if series and series[-1][0] == bucket:
            series[-1] = (bucket, price)
        else:
            while series and bucket - series[-1][0] > self.bucket_ms * self.window:
                series.popleft()                     # drop samples that fell out of the window
            series.append((bucket, price))

    def backfill(self, symbol: str, closes: Iterable[tuple[int, float]]) -> int:
        """Seed a series from stored candles (ts_ms, close, oldest first). Returns count."""
        series = self._series.setdefault(symbol, deque(maxlen=self.window + 1))
        series.clear()
        n = 0
        for item in closes:
            try:
                ts_ms, close = int(item[0]), float(item[1])
            except (TypeError, ValueError, IndexError):
                continue
            self.on_tick(symbol, close, ts_ms)
            n += 1
        return n

    def clear(self, symbol: Optional[str] = None) -> None:
        if symbol is None:
            self._series.clear()
        else:
            self._series.pop(symbol, None)

    # ── maths ────────────────────────────────────────────────────────
    def _returns(self, symbol: str) -> dict[int, float]:
        """bucket → log return between consecutive buckets this instrument has."""
        out: dict[int, float] = {}
        prev: Optional[tuple[int, float]] = None
        for bucket, price in self._series.get(symbol) or ():
            if prev is not None and prev[1] > 0 and price > 0:
                out[bucket] = math.log(price / prev[1])
            prev = (bucket, price)
        return out

    def symbols(self, min_buckets: int = 2) -> list[str]:
        return sorted(s for s, ser in self._series.items() if len(ser) >= min_buckets)

    def coverage(self, symbol: str) -> int:
        """How many buckets this instrument has (0 when it is not tracked at all)."""
        return len(self._series.get(symbol) or ())

    def stats(self) -> dict[str, Any]:
        return {
            "symbols": len(self._series),
            "buckets": {s: len(ser) for s, ser in sorted(self._series.items())},
            "bucket_ms": self.bucket_ms,
            "window": self.window,
            "min_samples": self.min_samples,
        }

    def pair(self, a: str, b: str) -> dict[str, Any]:
        """Correlation of one pair (their shared buckets only)."""
        ra, rb = self._returns(a), self._returns(b)
        shared = sorted(set(ra) & set(rb))
        n = len(shared)
        if a == b:
            return {"a": a, "b": b, "ok": n >= self.min_samples, "n": n, "r": 1.0 if n >= self.min_samples else None,
                    "reason": "" if n >= self.min_samples else f"needs {self.min_samples} shared buckets, has {n}"}
        if n < self.min_samples:
            return {"a": a, "b": b, "ok": False, "n": n, "r": None,
                    "reason": f"needs {self.min_samples} shared buckets, has {n}"}
        r = _pearson([ra[t] for t in shared], [rb[t] for t in shared])
        if r is None:
            return {"a": a, "b": b, "ok": False, "n": n, "r": None,
                    "reason": "returns have no dispersion over the shared window "
                              "(a constant-rate move is not a correlation)"}
        return {"a": a, "b": b, "ok": True, "n": n, "r": round(r, 4)}

    def matrix(self, symbols: Optional[Iterable[str]] = None, max_symbols: int = 24) -> dict[str, Any]:
        """Symmetric matrix of pairwise correlations plus the per-pair sample counts."""
        syms = list(symbols) if symbols is not None else self.symbols()
        syms = [s for s in syms][:max_symbols]
        cells: list[list[Optional[float]]] = []
        counts: list[list[int]] = []
        for a in syms:
            row: list[Optional[float]] = []
            crow: list[int] = []
            for b in syms:
                p = self.pair(a, b)
                row.append(p["r"])
                crow.append(int(p["n"]))
            cells.append(row)
            counts.append(crow)
        return {
            "symbols": syms,
            "matrix": cells,
            "samples": counts,
            "bucket_ms": self.bucket_ms,
            "window": self.window,
            "min_samples": self.min_samples,
            "ready": len(syms) >= 2 and any(p["ok"] for p in self.pairs(syms, limit=1)),
        }

    def pairs(self, symbols: Optional[Iterable[str]] = None, limit: int = 12,
              min_samples: Optional[int] = None, min_abs_r: float = 0.0) -> list[dict[str, Any]]:
        """Every usable pair, strongest absolute correlation first."""
        syms = list(symbols) if symbols is not None else self.symbols()
        need = self.min_samples if min_samples is None else int(min_samples)
        out: list[dict[str, Any]] = []
        for i, a in enumerate(syms):
            for b in syms[i + 1:]:
                p = self.pair(a, b)
                if not p["ok"] or p["r"] is None or p["n"] < need:
                    continue
                if abs(float(p["r"])) < float(min_abs_r):
                    continue
                out.append(p)
        out.sort(key=lambda p: (-abs(float(p["r"])), p["a"], p["b"]))
        return out[:max(0, int(limit))]

    def snapshot(self, symbols: Optional[Iterable[str]] = None, top: int = 12) -> dict[str, Any]:
        """Everything the UI needs in one payload: matrix, strongest pairs, coverage."""
        syms = [s for s in (symbols if symbols is not None else self.symbols())]
        grid = self.matrix(syms)
        return {
            "symbols": syms,
            "matrix": grid["matrix"],
            "samples": grid["samples"],
            "top": self.pairs(syms, limit=top),
            "stats": self.stats(),
            "note": ("Correlations use log returns over aligned "
                     f"{self.bucket_ms // 1000}s buckets; at least {self.min_samples} shared buckets "
                     "are required before a number is reported."),
        }
