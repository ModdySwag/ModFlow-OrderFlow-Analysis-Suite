"""
Node persistence — multiple High Volume Nodes ("double / triple nodes") across consecutive bars.

The reading (the reference order-flow teaching): a bar's heaviest-volume price is its High Volume
Node; when the *same price* keeps being the heaviest-volume price across consecutive bars, those
are stacked nodes — a double node at two bars, a triple at three — and the reference software
highlights them because stacked nodes work as stronger support/resistance than a single bar's
HVN. Persistence is the whole point: one bar's POC is noise, three bars of POC agreement is a
level somebody defended.

    node_runs()     a bar series -> every run of >= min_count consecutive bars at one price
    NodeTracker     the live form: on_bar() grows runs, returns an event when a run crosses a
                    threshold (2 = double, 3 = triple); a bar whose POC leaves the price closes
                    the run into `completed`

Prices are compared within `tol_ticks` ticks of the run's anchor price (default half a tick),
so float drift and a one-tick wobble do not split a run. Stdlib only; no alerts, sockets or UI
knowledge here — events are plain dicts with ``kind`` = "node_zone".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

KIND_NODE = "node_zone"


def _row_volume(levels: Any, price: float, tol: float) -> float:
    """Total volume of the row nearest `price` within `tol` — the POC row's traded size."""
    best = None
    best_d = tol
    for p, (b, a) in levels.items():
        d = abs(float(p) - price)
        if d <= best_d:
            best = float(b or 0.0) + float(a or 0.0)
            best_d = d
    return best or 0.0


def _bar_poc(bar: Any) -> tuple[int, Optional[float], float]:
    """(ts_ms, poc price or None, poc row volume) from either payload bars or (ts, poc[, vol])."""
    if isinstance(bar, tuple):
        ts = int(bar[0])
        poc = float(bar[1]) if len(bar) > 1 and bar[1] is not None else None
        vol = float(bar[2]) if len(bar) > 2 and bar[2] is not None else 0.0
        return ts, poc, vol
    ts_raw = bar.get("time_ms", bar.get("time", 0))
    ts_ms = int(round(float(ts_raw) * 1000)) if float(ts_raw or 0) < 1e11 else int(ts_raw or 0)
    poc = bar.get("poc")
    poc = float(poc) if isinstance(poc, (int, float)) else None
    vol = 0.0
    levels = bar.get("levels") or []
    if poc is not None and levels:
        rows = {}
        for level in levels:
            try:
                rows[float(level.get("price"))] = (float(level.get("bid") or 0.0),
                                                   float(level.get("ask") or 0.0))
            except (TypeError, ValueError):
                continue
        prices = sorted(rows)
        tol = (min((abs(b - a) for a, b in zip(prices, prices[1:]) if b != a), default=0.0) or 0.0) / 2.0 + 1e-12
        vol = _row_volume(rows, poc, tol)
    return ts_ms, poc, vol


@dataclass
class NodeRun:
    """A run of consecutive bars sharing one HVN price."""

    price: float
    count: int = 0
    start_ts_ms: int = 0
    last_ts_ms: int = 0
    volume: float = 0.0            # summed POC-row volume across the run
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"price": self.price, "count": self.count, "start_ts_ms": self.start_ts_ms,
                "last_ts_ms": self.last_ts_ms, "volume": round(self.volume, 8),
                "completed": self.completed}


def node_runs(bars: Iterable[Any], tick_size: float = 0.0, tol_ticks: float = 0.5,
              min_count: int = 2) -> list[NodeRun]:
    """Every run of >= ``min_count`` consecutive bars whose POC sits at one price.

    ``bars`` accepts the served payload shape (``{time, poc, levels}``) or ``(ts_ms, poc[, vol])``
    tuples. A bar with no POC ends any open run. The anchor price is the first bar's POC; later
    bars join while their POC is within ``tol_ticks`` ticks of the anchor.
    """
    tol = (tick_size * tol_ticks) if tick_size and tick_size > 0 else None
    parsed = [_bar_poc(b) for b in bars]

    runs: list[NodeRun] = []
    current: Optional[NodeRun] = None
    for ts, poc, vol in parsed:
        if poc is None:
            if current is not None:
                current.completed = True
                runs.append(current)
                current = None
            continue
        if current is None:
            current = NodeRun(price=poc, count=1, start_ts_ms=ts, last_ts_ms=ts, volume=vol)
            continue
        within = abs(poc - current.price) <= (tol if tol is not None else 1e-9)
        if within:
            current.count += 1
            current.last_ts_ms = ts
            current.volume += vol
        else:
            current.completed = True
            runs.append(current)
            current = NodeRun(price=poc, count=1, start_ts_ms=ts, last_ts_ms=ts, volume=vol)
    if current is not None:
        runs.append(current)
    return [r for r in runs if r.count >= max(2, int(min_count))]


class NodeTracker:
    """The live form: bars close into it; threshold crossings become events.

    Events fire when a run *reaches* 2 (double) and 3 (triple) bars — a growing run does not
    re-fire every bar (alert cooldowns and the UI refresh handle the rest; the snapshot always
    carries the live ``count``). ``crossings_only`` keeps that policy explicit.
    """

    def __init__(self, tick_size: float = 0.0, tol_ticks: float = 0.5,
                 thresholds: Sequence[int] = (2, 3), keep_completed: int = 50,
                 enabled: bool = True) -> None:
        self.enabled = bool(enabled)
        self.tick_size = float(tick_size or 0.0)
        self.tol_ticks = float(tol_ticks)
        self.thresholds = tuple(sorted({int(t) for t in thresholds if int(t) >= 2})) or (2, 3)
        self.keep_completed = max(0, int(keep_completed))
        self.current: Optional[NodeRun] = None
        self.completed: list[NodeRun] = []
        self.stats: dict[str, int] = {"bars": 0, "runs": 0, "crossings": 0}

    def on_bar(self, ts_ms: int, poc: Optional[float], volume: float = 0.0) -> list[dict[str, Any]]:
        ts = int(ts_ms)
        events: list[dict[str, Any]] = []
        tol = (self.tick_size * self.tol_ticks) if self.tick_size > 0 else 1e-9

        if poc is None:
            if self.current is not None:
                self.current.completed = True
                self._remember(self.current)
                self.current = None
            return events

        self.stats["bars"] += 1
        poc = float(poc)
        if self.current is None:
            self.current = NodeRun(price=poc, count=1, start_ts_ms=ts, last_ts_ms=ts, volume=float(volume or 0.0))
            return events
        if abs(poc - self.current.price) <= tol:
            self.current.count += 1
            self.current.last_ts_ms = ts
            self.current.volume += float(volume or 0.0)
            if self.current.count in self.thresholds:
                self.stats["crossings"] += 1
                events.append(self._event(self.current))
        else:
            self.current.completed = True
            self._remember(self.current)
            self.current = NodeRun(price=poc, count=1, start_ts_ms=ts, last_ts_ms=ts, volume=float(volume or 0.0))
        return events

    def snapshot(self) -> dict[str, Any]:
        return {
            "current": self.current.to_dict() if self.current else None,
            "completed": [r.to_dict() for r in self.completed[-self.keep_completed:]] if self.keep_completed else [],
            "stats": dict(self.stats),
        }

    def clear(self) -> None:
        self.current = None
        self.completed.clear()
        self.stats = {k: 0 for k in self.stats}

    def _remember(self, run: NodeRun) -> None:
        self.completed.append(run)
        self.stats["runs"] += 1
        if self.keep_completed and len(self.completed) > self.keep_completed:
            self.completed = self.completed[-self.keep_completed:]

    def _event(self, run: NodeRun) -> dict[str, Any]:
        label = {2: "double", 3: "triple"}.get(run.count, f"{run.count}-bar")
        return {"kind": KIND_NODE, "price": run.price, "count": run.count,
                "ts_ms": run.last_ts_ms, "start_ts_ms": run.start_ts_ms,
                "volume": round(run.volume, 8),
                "detail": f"{label} node at {run.price} ({run.count} consecutive bars)"}
