"""
Unfinished business (failed auctions) — footprint extremes the market never properly auctioned.

The reading (the reference order-flow teaching, re-implemented in this app's own words): a
properly auctioned **high** trades zero volume on the BID side of its top row, and a properly
auctioned **low** trades zero volume on the ASK side of its bottom row. When the market turns
away from a new extreme *without* that condition, the extreme is unfinished business — an
imperfection the market tends to revisit, where price then "fixes" it. The reference software
draws a line at such a price until that revisit; this module is the same mechanic as a pure core:

    classify_extremes()    one bar  -> did its high / low end unfinished?
    unfinished_from_bars() a series -> every magnet, with its resolution when one happened
    UnfinishedTracker      the live form: on_bar() detects and resolves against this bar,
                           on_tick() resolves the moment price returns to the level

Prices are compared with a tolerance of half a tick (or half the smallest observed price gap
when the tick is unknown), so a forex 1e-5 row behaves exactly like a futures row. Stdlib only
(test_no_numpy.py), and nothing here knows about alerts, sockets or the UI — the tracker returns
plain event dicts whose ``kind`` the hub can dispatch unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

#: price -> (bid volume, ask volume) — the shape the footprint pipeline produces
Row = tuple[float, float]
Levels = Mapping[float, Row]

#: the tracker's event kinds (alerts match on these)
KIND_DETECTED = "unfinished_business"
KIND_FIXED = "unfinished_fixed"


def _tol_for(tick_size: float, prices: Sequence[float]) -> float:
    """Half a tick when the tick is known; half the smallest observed gap otherwise."""
    if tick_size and tick_size > 0:
        return tick_size / 2.0 + 1e-12
    gaps = [abs(b - a) for a, b in zip(prices, prices[1:]) if b != a]
    if gaps:
        return min(gaps) / 2.0 + 1e-12
    return 1e-9


def _clean_rows(levels: Levels) -> dict[float, Row]:
    return {float(p): (float(b or 0.0), float(a or 0.0)) for p, (b, a) in levels.items()}


def classify_extremes(levels: Levels, tick_size: float = 0.0) -> dict[str, Any]:
    """Do this bar's extremes end properly, or leave business unfinished?

    Returns ``{"high": {...} | None, "low": {...} | None, "tick_tol": float}``; each side is
    ``{price, bid, ask, unfinished}``. A high is unfinished when its top row carries *any* bid
    volume (the auction turned without the zero-on-bid completion); a low is unfinished when its
    bottom row carries any ask volume. Tolerance: a row within half a tick of the extreme counts
    as the extreme (the builder already rounds to tick, so this only absorbs float drift).
    """
    clean = _clean_rows(levels)
    out: dict[str, Any] = {"high": None, "low": None}
    if not clean:
        return out
    prices = sorted(clean)
    out["tick_tol"] = _tol_for(tick_size, prices)

    hi_price = prices[-1]
    lo_price = prices[0]
    hi_bid, hi_ask = clean[hi_price]
    lo_bid, lo_ask = clean[lo_price]
    out["high"] = {"price": hi_price, "bid": hi_bid, "ask": hi_ask,
                   "unfinished": hi_bid > 0.0}
    out["low"] = {"price": lo_price, "bid": lo_bid, "ask": lo_ask,
                  "unfinished": lo_ask > 0.0}
    return out


@dataclass
class UnfinishedLevel:
    """One magnet: an unfinished extreme, open until price returns to the level."""

    price: float
    side: str                       # "above" = unfinished high, "below" = unfinished low
    bar_ts_ms: int
    started_ts_ms: int
    high: float = 0.0               # the creating bar's range (context)
    low: float = 0.0
    bid: float = 0.0                # the extreme row's volumes, as found
    ask: float = 0.0
    arms: int = 1                   # how many times the same price was left unfinished
    resolved_ts_ms: Optional[int] = None
    resolution_price: float = 0.0

    @property
    def active(self) -> bool:
        return self.resolved_ts_ms is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "price": self.price,
            "side": self.side,
            "bar_ts_ms": self.bar_ts_ms,
            "started_ts_ms": self.started_ts_ms,
            "high": self.high,
            "low": self.low,
            "bid": self.bid,
            "ask": self.ask,
            "arms": self.arms,
            "active": self.active,
            "resolved_ts_ms": self.resolved_ts_ms,
            "resolution_price": self.resolution_price,
        }


def _life_key(side: str, price: float, tick_size: float) -> tuple[str, float]:
    rounded = round(price / tick_size) if tick_size > 0 else round(price, 8)
    return side, rounded


def _bar_levels(bar: Any) -> tuple[int, Levels]:
    """Adapt either the served payload shape or a (ts_ms, mapping) pair to a mapping."""
    if isinstance(bar, tuple) and len(bar) == 2:
        ts, levels = bar
        return int(ts), _clean_rows(levels)
    ts_raw = bar.get("time_ms", bar.get("time", 0))
    ts_ms = int(round(float(ts_raw) * 1000)) if float(ts_raw or 0) < 1e11 else int(ts_raw or 0)
    rows: dict[float, Row] = {}
    for level in bar.get("levels") or []:
        try:
            rows[float(level.get("price"))] = (float(level.get("bid") or 0.0),
                                               float(level.get("ask") or 0.0))
        except (TypeError, ValueError):
            continue
    return ts_ms, rows


def _reaches(lv: UnfinishedLevel, high: float, low: float, tol: float) -> bool:
    """Did this bar's range reach (or trade through) the magnet's level?"""
    if lv.side == "above":
        return high >= lv.price - tol
    return low <= lv.price + tol


def unfinished_from_bars(bars: Iterable[Any], tick_size: float = 0.0) -> list[UnfinishedLevel]:
    """One-shot pass over a bar series: every magnet, resolved when a later bar reaches it.

    ``bars`` accepts the served footprint shape (``{time, high, low, levels: [...]}``) or
    ``(ts_ms, levels_mapping)`` pairs — one implementation for served, stored and test data.
    Resolution is by *reach*: a later bar that comes back to the level (or trades through it,
    within the tick tolerance) closes the magnet on that bar — never the magnet's own bar.
    """
    parsed = [(ts, rows) for ts, rows in (_bar_levels(b) for b in bars) if rows]
    open_levels: list[UnfinishedLevel] = []
    life: dict[tuple[str, float], int] = {}

    for ts, rows in parsed:
        prices = sorted(rows)
        tol = _tol_for(tick_size, prices)
        high, low = prices[-1], prices[0]

        for lv in open_levels:
            if lv.active and _reaches(lv, high, low, tol):
                lv.resolved_ts_ms = ts
                lv.resolution_price = high if lv.side == "above" else low

        ext = classify_extremes(rows, tick_size=tick_size)
        for side, key in (("above", "high"), ("below", "low")):
            info = ext.get(key)
            if not info or not info["unfinished"]:
                continue
            lk = _life_key(side, info["price"], tick_size)
            arms = life.get(lk, 0) + 1
            life[lk] = arms
            open_levels.append(UnfinishedLevel(
                price=info["price"], side=side, bar_ts_ms=ts, started_ts_ms=ts,
                high=high, low=low, bid=info["bid"], ask=info["ask"], arms=arms,
            ))

    return open_levels


class UnfinishedTracker:
    """The live form: bars close into it, ticks resolve it, a snapshot serves the REST layer.

    ``arms`` counts how many times the *same price* has been left unfinished over the tracker's
    life — a level that keeps failing to auction is the stronger read, and it is the honest way
    to count it, because a revisit fixes the previous magnet before the next one forms. A new
    magnet within ``merge_ticks`` ticks of an open one on the same side still merges rather than
    drawing two lines a tick apart.
    """

    def __init__(self, tick_size: float = 0.0, max_open: int = 200,
                 merge_ticks: float = 0.5, keep_resolved: int = 100,
                 enabled: bool = True) -> None:
        self.enabled = bool(enabled)
        self.tick_size = float(tick_size or 0.0)
        self.max_open = max(1, int(max_open))
        self.merge_ticks = float(merge_ticks)
        self.keep_resolved = max(0, int(keep_resolved))
        self._open: list[UnfinishedLevel] = []
        self._resolved: list[UnfinishedLevel] = []
        self._life: dict[tuple[str, float], int] = {}
        self.stats: dict[str, int] = {"bars": 0, "detected": 0, "rearmed": 0, "fixed": 0}

    # ── ingest ────────────────────────────────────────────────
    def on_bar(self, ts_ms: int, levels: Levels, tick_size: Optional[float] = None) -> list[dict[str, Any]]:
        """A closed bar: resolve open magnets its range reaches, then detect new ones."""
        if tick_size:
            self.tick_size = float(tick_size)
        rows = _clean_rows(levels)
        if not rows:
            return []
        self.stats["bars"] += 1
        prices = sorted(rows)
        tol = _tol_for(self.tick_size, prices)
        high, low = prices[-1], prices[0]
        events: list[dict[str, Any]] = []

        for lv in self._open:
            if _reaches(lv, high, low, tol):
                lv.resolved_ts_ms = int(ts_ms)
                lv.resolution_price = high if lv.side == "above" else low
                events.append(self._fixed_event(lv))
        fixed = [lv for lv in self._open if not lv.active]
        if fixed:
            self._open = [lv for lv in self._open if lv.active]
            self._remember(fixed)

        ext = classify_extremes(rows, tick_size=self.tick_size)
        for side, key in (("above", "high"), ("below", "low")):
            info = ext.get(key)
            if not info or not info["unfinished"]:
                continue
            merge_tol = (self.merge_ticks * self.tick_size) if self.tick_size > 0 else tol
            existing = next(
                (lv for lv in self._open
                 if lv.side == side and abs(lv.price - info["price"]) <= merge_tol),
                None,
            )
            if existing is not None:
                existing.arms += 1
                self.stats["rearmed"] += 1
                continue
            lk = _life_key(side, info["price"], self.tick_size)
            arms = self._life.get(lk, 0) + 1
            self._life[lk] = arms
            lv = UnfinishedLevel(
                price=info["price"], side=side, bar_ts_ms=int(ts_ms), started_ts_ms=int(ts_ms),
                high=high, low=low, bid=info["bid"], ask=info["ask"], arms=arms,
            )
            self._open.append(lv)
            self.stats["detected"] += 1
            events.append(self._detected_event(lv))
        if len(self._open) > self.max_open:
            self._open = self._open[-self.max_open:]
        return events

    def on_tick(self, price: float, ts_ms: int) -> list[dict[str, Any]]:
        """A trade print: resolves magnets the moment price returns to the level."""
        events: list[dict[str, Any]] = []
        tol = (self.tick_size / 2.0) if self.tick_size > 0 else 1e-9
        for lv in self._open:
            reaches = price >= lv.price - tol if lv.side == "above" else price <= lv.price + tol
            if reaches:
                lv.resolved_ts_ms = int(ts_ms)
                lv.resolution_price = float(price)
                events.append(self._fixed_event(lv))
        if events:
            fixed = [lv for lv in self._open if not lv.active]
            self._open = [lv for lv in self._open if lv.active]
            self._remember(fixed)
        return events

    # ── output ────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        return {
            "open": [lv.to_dict() for lv in self._open],
            "resolved": [lv.to_dict() for lv in self._resolved[-self.keep_resolved:]] if self.keep_resolved else [],
            "stats": dict(self.stats),
        }

    def clear(self) -> None:
        self._open.clear()
        self._resolved.clear()
        self._life.clear()
        self.stats = {k: 0 for k in self.stats}

    # ── internals ─────────────────────────────────────────────
    def _remember(self, levels: list[UnfinishedLevel]) -> None:
        self._resolved.extend(levels)
        if self.keep_resolved and len(self._resolved) > self.keep_resolved:
            self._resolved = self._resolved[-self.keep_resolved:]

    def _detected_event(self, lv: UnfinishedLevel) -> dict[str, Any]:
        return {"kind": KIND_DETECTED, "price": lv.price, "side": lv.side,
                "ts_ms": lv.started_ts_ms, "bar_ts_ms": lv.bar_ts_ms,
                "bid": lv.bid, "ask": lv.ask, "arms": lv.arms,
                "detail": f"unfinished {'high' if lv.side == 'above' else 'low'} at {lv.price} "
                          f"(no zero-on-{'bid' if lv.side == 'above' else 'ask'} completion)"}

    def _fixed_event(self, lv: UnfinishedLevel) -> dict[str, Any]:
        self.stats["fixed"] += 1
        return {"kind": KIND_FIXED, "price": lv.price, "side": lv.side,
                "ts_ms": lv.resolved_ts_ms, "bar_ts_ms": lv.bar_ts_ms,
                "detail": f"price returned to the unfinished level at {lv.price}"}
