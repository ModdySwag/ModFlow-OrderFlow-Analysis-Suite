"""
Depth history — the depth-over-time store (the reference platform's "Market Depth Historical Graph").

The heatmap draws the book as it is, and keeps only a rolling drawn window. Look away for twenty
minutes and the record of how liquidity built and pulled is gone — which is the whole product on
the reference platform, where the depth graph is a study you scroll back through rather than a
live canvas. The app already receives every depth column; nothing kept them.

This module keeps them. One column per ``interval_ms`` of book time, per symbol:
``price -> (bid, ask)``. A column is the *last* book seen inside its grid cell — a snapshot, never
a sum of the updates that landed in it, which would invent size that was never on the book.

Bounded three ways, so the store cannot grow with uptime: a retention window in minutes, a column
ceiling per symbol, and a symbol ceiling with least-recently-fed eviction. The ceilings are real
memory ceilings: one retained level is a float key plus a two-float tuple, so a column of
``max_levels`` levels costs a few kB and the defaults hold a 30-minute, 40-level, 8-symbol record
(≈8 MB per symbol of book, measured by ``stats()["retained_levels"]`` rather than guessed).

What it answers
---------------
* ``series()``   — per bucket: total resting bid/ask, the biggest single level, the size-weighted
  mid, and the resting-size profile in price bands (the graph the panel draws).
* ``events()``   — pull/add detection between consecutive columns: which levels were withdrawn or
  stacked, by relative *and* absolute size delta.
* ``gaps()``     — where the record has holes (a stopped engine, a dropped feed).
* ``staleness()``— how old the newest column is, in the app's fresh/aging/stale words.
* ``prune()``    — drop what the retention window no longer covers.

Pure: every query above is a function over plain lists of columns. No file, network or hub access
lives here — the hub feeds it (``record``) and the router at the bottom serves it.
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from fastapi import APIRouter, Body, Query

from orderflow_system.atlas.clock import as_epoch_ms

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atlas", tags=["atlas"])


#: The feature's settings block — registered by the parent as ``atlas.depth_history``.
DEFAULTS: dict[str, Any] = {
    "enabled": True,
    #: how far back the record is kept (minutes). 24 h is the ceiling, not a promise about memory.
    "retention_minutes": 30,
    #: columns kept per symbol; at the 1 s grid this is the same 30 minutes, as a hard count.
    "max_columns_per_symbol": 1800,
    #: symbols kept at once — the least recently fed one is evicted past this.
    "max_symbols": 8,
    #: the column grid, in ms: one depth column per this much book time.
    "interval_ms": 1000,
    #: the aggregation width the panel starts with (a bucket holds many columns).
    "bucket_ms": 5000,
    #: levels kept per column, nearest the mid first — a 200-level book is not worth 200 rows
    #: of scrollback nobody reads.
    "max_levels": 40,
    #: a level losing this share of its size (and at least ``min_size``) was pulled.
    "pull_pct": 0.5,
    #: a level gaining this share (and at least ``min_size``) was stacked.
    "add_pct": 0.5,
    #: the absolute floor under both: a 2 → 1 wiggle on a thin book is not an event.
    "min_size": 1.0,
    #: silence longer than this many intervals is a hole in the record, not a quiet book.
    "gap_multiple": 3,
    #: price bands in the resting-size profile.
    "bands": 8,
}

#: How many raw levels a single incoming book may cost us before the rest are ignored.
_MAX_LEVELS_READ = 400

#: Per-bucket ceiling: a request wider than this is answered on a wider bucket, and the width used
#: is reported, so a 24 h window cannot build a 86 400-cell payload.
_MAX_BUCKETS = 1500

#: How far ahead of the wall clock a fed stamp may sit before it is treated as unreadable (T6-F04).
#: A venue a few seconds ahead of us is ordinary clock skew and is kept as it stands; a stamp beyond
#: this is a broken clock, and a column stamped there would be invisible to every reader.
_FUTURE_TOLERANCE_MS = 60_000

#: Events per series answer — the biggest, then re-sorted by time.
_MAX_EVENTS = 400


def empty_note(symbol: str) -> str:
    """The refusal sentence, in the app's own voice."""
    return (f"no depth recorded yet for {symbol} — leave the heatmap open for a minute "
            "and it will start filling")


# ── coercion helpers (never raise) ──────────────────────────────────────────

def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "on"):
            return True
        if text in ("0", "false", "no", "off", ""):
            return False
    return default


def _int_in(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        out = int(float(value))
    except (TypeError, ValueError):
        out = int(default)
    return max(lo, min(hi, out))


def _float_in(value: Any, default: float, lo: float, hi: float) -> float:
    out = _num(value, float(default))
    return max(lo, min(hi, out))


def clean(patch: Any) -> dict[str, Any]:
    """Coerce an incoming settings patch onto ``DEFAULTS``: unknown keys dropped, nothing raises.

    The parent calls this with whatever the config store holds (or with a user's POST body), so it
    must survive a string, a list, a half-filled dict — and it returns only this feature's block.
    """
    out = dict(DEFAULTS)
    if not isinstance(patch, dict):
        return out
    out["enabled"] = _bool(patch.get("enabled"), out["enabled"])
    out["retention_minutes"] = _int_in(patch.get("retention_minutes"), out["retention_minutes"], 1, 1440)
    out["max_columns_per_symbol"] = _int_in(patch.get("max_columns_per_symbol"),
                                            out["max_columns_per_symbol"], 60, 20000)
    out["max_symbols"] = _int_in(patch.get("max_symbols"), out["max_symbols"], 1, 64)
    out["interval_ms"] = _int_in(patch.get("interval_ms"), out["interval_ms"], 200, 60_000)
    out["max_levels"] = _int_in(patch.get("max_levels"), out["max_levels"], 5, 400)
    out["pull_pct"] = _float_in(patch.get("pull_pct"), out["pull_pct"], 0.05, 0.99)
    out["add_pct"] = _float_in(patch.get("add_pct"), out["add_pct"], 0.05, 10.0)
    out["min_size"] = _float_in(patch.get("min_size"), out["min_size"], 0.0, 1e12)
    out["gap_multiple"] = _int_in(patch.get("gap_multiple"), out["gap_multiple"], 2, 240)
    out["bands"] = _int_in(patch.get("bands"), out["bands"], 2, 32)
    out["bucket_ms"] = _int_in(patch.get("bucket_ms"), out["bucket_ms"], out["interval_ms"], 3_600_000)
    # a bucket narrower than the column grid would repeat columns under one time axis
    out["bucket_ms"] = max(out["bucket_ms"], out["interval_ms"])
    return out


def symbol_key(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


# ── the column ──────────────────────────────────────────────────────────────

@dataclass
class DepthColumn:
    """One grid cell of book time: the last depth snapshot seen inside it."""

    ts_ms: int
    levels: dict[float, tuple[float, float]] = field(default_factory=dict)
    best_bid: float = 0.0
    best_ask: float = 0.0
    updates: int = 1          # books folded into this cell (the cell still holds the last one)


def _price_size(item: Any) -> tuple[float, float]:
    """``(price, size)`` out of whatever one book row is (object, dict or pair)."""
    if isinstance(item, dict):
        price = _num(item.get("price", item.get("p")))
        size = _num(item.get("quantity", item.get("size", item.get("q"))))
        return price, size
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return _num(item[0]), _num(item[1])
    price = _num(getattr(item, "price", 0.0))
    size = _num(getattr(item, "quantity", getattr(item, "size", 0.0)))
    return price, size


def _merge(book: dict[float, list[float]], price: float, bid: float, ask: float) -> None:
    if price <= 0:
        return
    row = book.setdefault(price, [0.0, 0.0])
    row[0] += max(0.0, bid)
    row[1] += max(0.0, ask)


def coerce_levels(levels: Any) -> tuple[dict[float, tuple[float, float]], int]:
    """One book -> ``{price: (bid, ask)}``, plus how many levels needed a side guessed for.

    Accepts the shapes the feeds and siblings actually hand over: ``{price: (bid, ask)}``,
    ``{price: {"bid":…, "ask":…}}``, ``{price: size}``, a list of ``{price, bid, ask}`` /
    ``{price, side, size}`` rows / ``(price, bid, ask)`` triples, or an object carrying ``.bids``
    and ``.asks`` (the repo's own ``OrderbookSnapshot``). A bare size with no side goes below the
    mid for a bid, above it for an ask — counted, never silently dropped. Anything unreadable is
    skipped. Never raises.
    """
    book: dict[float, list[float]] = {}
    unsided: list[tuple[float, float]] = []
    if levels is None:
        return {}, 0

    if hasattr(levels, "bids") or hasattr(levels, "asks"):
        for side, attr in (("bid", "bids"), ("ask", "asks")):
            rows = getattr(levels, attr, None) or []
            try:
                rows = list(rows)[:_MAX_LEVELS_READ]
            except TypeError:
                rows = []
            for item in rows:
                price, size = _price_size(item)
                _merge(book, price, size if side == "bid" else 0.0, size if side == "ask" else 0.0)
    elif isinstance(levels, dict):
        for raw_price, value in list(levels.items())[:_MAX_LEVELS_READ]:
            price = _num(raw_price)
            if isinstance(value, dict):
                if "bid" in value or "ask" in value:
                    _merge(book, price, _num(value.get("bid")), _num(value.get("ask")))
                else:
                    unsided.append((price, _num(value.get("size", value.get("quantity")))))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                _merge(book, price, _num(value[0]), _num(value[1]))
            else:
                unsided.append((price, _num(value)))
    elif isinstance(levels, (list, tuple)):
        for item in list(levels)[:_MAX_LEVELS_READ]:
            if isinstance(item, dict):
                price = _num(item.get("price", item.get("p")))
                side = str(item.get("side") or "").strip().lower()
                size = _num(item.get("size", item.get("quantity", item.get("q"))))
                if side.startswith("b"):
                    _merge(book, price, size, 0.0)
                elif side.startswith("a") or side.startswith("s"):
                    _merge(book, price, 0.0, size)
                else:
                    unsided.append((price, size))
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                _merge(book, _num(item[0]), _num(item[1]), _num(item[2]))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                unsided.append((_num(item[0]), _num(item[1])))
    else:
        return {}, 0

    best_bid = max((p for p, r in book.items() if r[0] > 0), default=0.0)
    best_ask = min((p for p, r in book.items() if r[1] > 0), default=0.0)
    if best_bid and best_ask:
        mid = (best_bid + best_ask) / 2.0
    elif book:
        prices = sorted(book)
        mid = prices[len(prices) // 2]
    else:
        prices = sorted(p for p, _s in unsided if p > 0)
        mid = prices[len(prices) // 2] if prices else 0.0

    guessed = 0
    for price, size in unsided:
        if price <= 0 or size <= 0:
            continue
        guessed += 1
        if price <= mid:
            _merge(book, price, size, 0.0)
        else:
            _merge(book, price, 0.0, size)

    out = {p: (round(b, 6), round(a, 6)) for p, (b, a) in book.items() if (b > 0 or a > 0)}
    return out, guessed


def trim_levels(levels: dict[float, tuple[float, float]], max_levels: int) -> tuple[dict[float, tuple[float, float]], int]:
    """Keep the ``max_levels`` prices nearest the mid; return the kept book and the drop count.

    Nearest the mid is what a depth graph is read for: a 200-level book is a wall of rows, and the
    far tail of it changes without ever mattering to price.
    """
    if max_levels <= 0 or len(levels) <= max_levels:
        return dict(levels), 0
    bids = [p for p, (b, _a) in levels.items() if b > 0]
    asks = [p for p, (_b, a) in levels.items() if a > 0]
    if bids and asks:
        mid = (max(bids) + min(asks)) / 2.0
    else:
        prices = sorted(levels)
        mid = prices[len(prices) // 2]
    kept = sorted(levels, key=lambda p: (abs(p - mid), p))[:max_levels]
    return {p: levels[p] for p in sorted(kept)}, len(levels) - len(kept)


def best_prices(levels: dict[float, tuple[float, float]]) -> tuple[float, float]:
    bid = max((p for p, (b, _a) in levels.items() if b > 0), default=0.0)
    ask = min((p for p, (_b, a) in levels.items() if a > 0), default=0.0)
    return bid, ask


def snap_book(levels: dict[float, tuple[float, float]], tick_size: float) -> dict[float, tuple[float, float]]:
    """Coalesce prices onto the instrument's tick grid — the depth map's own bucketing.

    A feed hands over 99.499999999 for a 0.01-tick instrument; left alone, every such print is its
    own level, inflating the column and splitting one band's size across rows nobody can tell apart.
    ``tick_size`` 0 (the default) means "the prices are what the venue said" and changes nothing.
    """
    tick = _num(tick_size)
    if not (tick > 0):
        return levels
    out: dict[float, tuple[float, float]] = {}
    for price, (bid, ask) in levels.items():
        snapped = round(round(price / tick) * tick, 10)
        prev = out.get(snapped, (0.0, 0.0))
        out[snapped] = (round(prev[0] + bid, 6), round(prev[1] + ask, 6))
    return out


# ── pure queries over a list of columns ─────────────────────────────────────

def weighted_mid(levels: dict[float, tuple[float, float]]) -> Optional[float]:
    """The size-weighted mid (micro-price): each side weighted by the OTHER side's size.

    A thin bid under a heavy ask pulls the number toward the ask, which is the compression a
    desk reads as pressure. One side only -> that side's best price; nothing -> ``None``.
    """
    best_bid, best_ask = best_prices(levels)
    if best_bid <= 0 and best_ask <= 0:
        return None
    if best_bid <= 0 or best_ask <= 0:
        return round(best_bid or best_ask, 10)
    bid_size = levels.get(best_bid, (0.0, 0.0))[0]
    ask_size = levels.get(best_ask, (0.0, 0.0))[1]
    if bid_size + ask_size <= 0:
        return round((best_bid + best_ask) / 2.0, 10)
    return round((best_bid * ask_size + best_ask * bid_size) / (bid_size + ask_size), 10)


def _totals(levels: dict[float, tuple[float, float]]) -> tuple[float, float]:
    bid = sum(b for b, _a in levels.values())
    ask = sum(a for _b, a in levels.values())
    return round(bid, 6), round(ask, 6)


def biggest_level(levels: dict[float, tuple[float, float]]) -> Optional[dict[str, Any]]:
    """The single largest resting level in one column, with its side and share of the book."""
    if not levels:
        return None
    total = sum(b + a for b, a in levels.values())
    price, (bid, ask) = max(levels.items(), key=lambda kv: kv[1][0] + kv[1][1])
    size = bid + ask
    side = "bid" if bid >= ask else "ask"
    return {"price": round(price, 10), "size": round(size, 6), "side": side,
            "share": round(size / total, 4) if total > 0 else 0.0}


def band_profile(levels: dict[float, tuple[float, float]], edges: Sequence[float]) -> list[dict[str, float]]:
    """Bid/ask size per price band for one column, against pre-computed band edges."""
    rows = [{"bid": 0.0, "ask": 0.0} for _ in range(max(0, len(edges) - 1))]
    if not rows:
        return []
    low, high = edges[0], edges[-1]
    width = (high - low) / len(rows)
    for price, (bid, ask) in levels.items():
        idx = int((price - low) / width) if width > 0 else 0
        # the range's own top price sits exactly on the last edge — it belongs to the last band
        idx = min(len(rows) - 1, max(0, idx))
        rows[idx]["bid"] = round(rows[idx]["bid"] + bid, 6)
        rows[idx]["ask"] = round(rows[idx]["ask"] + ask, 6)
    return rows


def band_edges(columns: Sequence[DepthColumn], bands: int) -> list[float]:
    """Equal price bands over the columns' own range — the axis the profile is read on."""
    widths = max(2, int(bands))
    prices: list[float] = []
    for col in columns:
        prices.extend(col.levels)
    if not prices:
        return []
    low, high = min(prices), max(prices)
    if high <= low:
        return [low, high + 1e-9]
    step = (high - low) / widths
    return [round(low + i * step, 10) for i in range(widths + 1)]


def summarise(columns: Sequence[DepthColumn]) -> Optional[dict[str, Any]]:
    """One bucket's reading: its LAST column (a bucket reports where the book got to).

    ``series_of`` relabels ``ts_ms`` with the bucket's grid cell; ``at_ms`` stays the column's own
    stamp, so a caller can tell the cell from the reading inside it.
    """
    if not columns:
        return None
    col = columns[-1]
    bid, ask = _totals(col.levels)
    return {"ts_ms": col.ts_ms, "at_ms": col.ts_ms, "columns": len(columns),
            "updates": sum(int(c.updates) for c in columns),
            "total_bid": bid, "total_ask": ask, "total": round(bid + ask, 6),
            "best_bid": round(col.best_bid, 10), "best_ask": round(col.best_ask, 10),
            "spread": round(col.best_ask - col.best_bid, 10) if col.best_bid and col.best_ask else None,
            "weighted_mid": weighted_mid(col.levels),
            "biggest": biggest_level(col.levels),
            "levels": len(col.levels)}


def _level_events(prev: DepthColumn, cur: DepthColumn, pull_pct: float, add_pct: float,
                  min_size: float) -> list[dict[str, Any]]:
    """What changed at each price between two consecutive columns, per side."""
    out: list[dict[str, Any]] = []
    for price in set(prev.levels) | set(cur.levels):
        before_b, before_a = prev.levels.get(price, (0.0, 0.0))
        after_b, after_a = cur.levels.get(price, (0.0, 0.0))
        for side, before, after in (("bid", before_b, after_b), ("ask", before_a, after_a)):
            delta = after - before
            if delta < 0:
                lost = -delta
                if before > 0 and lost >= min_size and lost >= before * pull_pct:
                    out.append({"kind": "pull", "ts_ms": cur.ts_ms, "price": round(price, 10),
                                "side": side, "size": round(lost, 6), "from": round(before, 6),
                                "to": round(after, 6), "pct": round(lost / before, 4)})
            elif delta > 0:
                grew = delta
                if grew >= min_size and (before <= 0 or grew >= before * add_pct):
                    # §148 T6-F9: a level that was not there before has no share to report — 1.0
                    # read as "stacked 100%", a percentage that was never measured. None is the
                    # absence of a reading, and the tape says "new level".
                    out.append({"kind": "add", "ts_ms": cur.ts_ms, "price": round(price, 10),
                                "side": side, "size": round(grew, 6), "from": round(before, 6),
                                "to": round(after, 6),
                                "pct": round(grew / before, 4) if before > 0 else None})
    return out


def pull_add_of(columns: Sequence[DepthColumn], *, pull_pct: float = DEFAULTS["pull_pct"],
                add_pct: float = DEFAULTS["add_pct"], min_size: float = DEFAULTS["min_size"],
                limit: int = _MAX_EVENTS) -> list[dict[str, Any]]:
    """Pulled and stacked levels between consecutive columns, biggest kept, then sorted by time."""
    events: list[dict[str, Any]] = []
    prev: Optional[DepthColumn] = None
    for col in columns:
        if prev is not None:
            events.extend(_level_events(prev, col, float(pull_pct), float(add_pct), float(min_size)))
        prev = col
    keep = int(limit)
    if keep <= 0:
        return []                      # the caller asked for the series without the event tail
    events.sort(key=lambda e: (-e["size"], e["ts_ms"]))
    events = events[:keep]
    events.sort(key=lambda e: (e["ts_ms"], e["price"]))
    return events


def gaps_of(columns: Sequence[DepthColumn], *, interval_ms: int = DEFAULTS["interval_ms"],
            gap_multiple: int = DEFAULTS["gap_multiple"], limit: int = 200) -> dict[str, Any]:
    """Where the record has holes: silence longer than ``gap_multiple`` intervals."""
    threshold = max(2, int(gap_multiple)) * max(1, int(interval_ms))
    found: list[dict[str, Any]] = []
    for prev, cur in zip(columns, columns[1:]):
        delta = cur.ts_ms - prev.ts_ms
        if delta > threshold:
            found.append({"from_ms": prev.ts_ms, "to_ms": cur.ts_ms, "ms": delta,
                          "missing_ms": delta - int(interval_ms)})
    span = max(0, columns[-1].ts_ms - columns[0].ts_ms) if len(columns) > 1 else 0
    missing = sum(g["ms"] for g in found)
    covered = round(100.0 * (span - missing) / span, 1) if span > 0 else 100.0
    found.sort(key=lambda g: -g["ms"])
    return {"gaps": found[:max(1, int(limit))], "count": len(found),
            "largest_ms": found[0]["ms"] if found else 0, "missing_ms": missing,
            "span_ms": span, "covered_pct": max(0.0, covered)}


def staleness_of(last_ms: int, now_ms: int, interval_ms: int = DEFAULTS["interval_ms"]) -> dict[str, Any]:
    """How old the newest column is, in the app's fresh / aging / stale words."""
    interval = max(1, int(interval_ms))
    fresh_ms = max(3000, interval * 3)
    stale_ms = max(15_000, interval * 15)
    if not last_ms:
        return {"last_ms": 0, "age_ms": 0, "state": "empty", "fresh_ms": fresh_ms,
                "stale_ms": stale_ms, "text": "nothing recorded yet"}
    age = max(0, int(now_ms) - int(last_ms))
    if age <= fresh_ms:
        state, text = "fresh", f"recording · last column {age / 1000.0:.1f} s ago"
    elif age <= stale_ms:
        state, text = "aging", f"quiet · last column {age / 1000.0:.1f} s ago"
    else:
        state, text = "stale", f"stale — no depth for {age / 60000.0:.1f} min"
    return {"last_ms": int(last_ms), "age_ms": age, "state": state, "fresh_ms": fresh_ms,
            "stale_ms": stale_ms, "text": text}


def _fit_bucket(span_ms: int, bucket_ms: int, interval_ms: int, max_buckets: int) -> int:
    """Widen the bucket until the window fits the cell ceiling; return the width actually used."""
    interval = max(1, int(interval_ms))
    bucket = max(interval, int(round(max(interval, int(bucket_ms)) / interval)) * interval)
    ceiling = max(1, int(max_buckets))
    guard = 0
    while span_ms > 0 and (span_ms // bucket) + 1 > ceiling and guard < 64:
        bucket = max(bucket * 2, interval * 2)
        guard += 1
    return bucket


def series_of(columns: Sequence[DepthColumn], *, from_ms: int = 0, to_ms: int = 0, bucket_ms: int = 0,
              interval_ms: int = DEFAULTS["interval_ms"], bands: int = DEFAULTS["bands"],
              pull_pct: float = DEFAULTS["pull_pct"], add_pct: float = DEFAULTS["add_pct"],
              min_size: float = DEFAULTS["min_size"], gap_multiple: int = DEFAULTS["gap_multiple"],
              limit_events: int = _MAX_EVENTS, max_buckets: int = _MAX_BUCKETS,
              now_ms: int = 0) -> dict[str, Any]:
    """The graph's data: per-bucket summaries plus the window's own profile, events and state.

    ``bucket_ms`` is a request, not a promise: a window that would need more than ``max_buckets``
    cells is answered on a wider bucket, and the width used is what the payload reports.
    """
    rows = [c for c in columns if (not from_ms or c.ts_ms >= int(from_ms))
            and (not to_ms or c.ts_ms <= int(to_ms))]
    first_ms = rows[0].ts_ms if rows else 0
    last_ms = rows[-1].ts_ms if rows else 0
    bucket = _fit_bucket(max(0, last_ms - first_ms), int(bucket_ms or interval_ms),
                         int(interval_ms), int(max_buckets))
    edges = band_edges(rows, int(bands))

    buckets: list[dict[str, Any]] = []
    grouped: list[tuple[int, list[DepthColumn]]] = []
    for col in rows:
        key = (col.ts_ms // bucket) * bucket
        if grouped and grouped[-1][0] == key:
            grouped[-1][1].append(col)
        else:
            grouped.append((key, [col]))
    for key, group in grouped:
        row = summarise(group)
        if row is None:
            continue
        # the bucket's own grid cell is its label; `at_ms` is the column the reading came from
        row["ts_ms"] = key
        row["bands"] = band_profile(group[-1].levels, edges)
        buckets.append(row)

    profile = []
    for i in range(max(0, len(edges) - 1)):
        bid = round(sum(b["bands"][i]["bid"] for b in buckets if i < len(b["bands"])), 6)
        ask = round(sum(b["bands"][i]["ask"] for b in buckets if i < len(b["bands"])), 6)
        profile.append({"from": edges[i], "to": edges[i + 1], "bid": bid, "ask": ask,
                        "total": round(bid + ask, 6)})
    peak = max(profile, key=lambda p: p["total"]) if profile else None
    busy = max(buckets, key=lambda b: b["total"]) if buckets else None
    return {
        "bucket_ms": bucket,
        "bucket_ms_requested": int(bucket_ms or interval_ms),
        "interval_ms": int(interval_ms),
        "from_ms": int(from_ms or first_ms), "to_ms": int(to_ms or last_ms),
        "first_ms": first_ms, "last_ms": last_ms,
        "buckets": buckets,
        "bands": [round(e, 10) for e in edges],
        "profile": profile,
        "peak_band": peak,
        "busiest_bucket": ({"ts_ms": busy["ts_ms"], "total": busy["total"]} if busy else None),
        "events": pull_add_of(rows, pull_pct=pull_pct, add_pct=add_pct, min_size=min_size,
                              limit=limit_events),
        "gaps": gaps_of(rows, interval_ms=interval_ms, gap_multiple=gap_multiple),
        "staleness": staleness_of(last_ms, int(now_ms or time.time() * 1000), interval_ms),
        "span_ms": max(0, last_ms - first_ms),
        "levels": sum(len(c.levels) for c in rows),
    }


# ── the store ───────────────────────────────────────────────────────────────

class DepthHistoryStore:
    """Bounded per-symbol depth columns. In-memory only; every query is a pure function above."""

    def __init__(self, settings: Any = None) -> None:
        self.settings: dict[str, Any] = clean(settings or {})
        self._cols: dict[str, deque[DepthColumn]] = {}
        self._last: dict[str, int] = {}
        self._last_prune_ms = 0
        self.counters: dict[str, int] = {
            "records": 0, "folded": 0, "refused": 0, "empty_books": 0, "stale_skipped": 0,
            "late_skipped": 0, "future_skipped": 0,
            "dropped_columns": 0, "dropped_symbols": 0, "levels_trimmed": 0, "prunes": 0,
        }

    # ── settings ──
    def configure(self, patch: Any) -> dict[str, Any]:
        """Adopt a settings patch (cleaned) and re-prune: a shorter retention must bite at once."""
        current = clean({**self.settings, **(patch if isinstance(patch, dict) else {})})
        self.settings = current
        self.prune()
        return dict(current)

    # ── ingest ──
    def record(self, symbol: str, ts_ms: Any, levels: Any, *, tick_size: float = 0.0) -> int:
        """Fold one depth column in; return how many columns this symbol now holds.

        Timestamps go through ``as_epoch_ms`` (the feeds hand over seconds, update ids and ms in
        the same field), an empty or unreadable book records nothing and is counted, prices are
        snapped to ``tick_size`` when the caller knows it, and the store prunes on a one-second
        leash so a long-running engine cannot drift past its ceilings.
        """
        if not self.settings.get("enabled", True):
            self.counters["refused"] += 1
            return 0
        key = symbol_key(symbol)
        if not key:
            self.counters["refused"] += 1
            return 0
        now = int(time.time() * 1000)
        if bool(getattr(levels, "stale", False)):
            # SEC-07's rule, the depth map's own: a book the feed has called untrustworthy (its
            # sequence broke) is not a depth column — folded in, it would record liquidity nobody
            # can vouch for, which is the one thing a history is for.
            self.counters["stale_skipped"] += 1
            return len(self._cols.get(key) or ())
        book, _guessed = coerce_levels(levels)
        if not book:
            self.counters["empty_books"] += 1
            return len(self._cols.get(key) or ())
        book = snap_book(book, tick_size)
        book, trimmed = trim_levels(book, int(self.settings["max_levels"]))
        self.counters["levels_trimmed"] += trimmed

        ts = as_epoch_ms(ts_ms, fallback_ms=self._last.get(key) or now)
        # A stamp from the future is a clock we cannot read, exactly like an update id (T6-F04):
        # kept, the column sits past every prune cutoff and outside every replay window, and the
        # newest-column staleness reads "fresh" over a record nobody can see. Beyond a minute the
        # stamp falls back to the stream's own clock — the same contract as a junk stamp — and is
        # counted so the refusal is visible. (A venue a few seconds ahead of us is real and kept.)
        if ts > now + _FUTURE_TOLERANCE_MS:
            self.counters["future_skipped"] += 1
            ts = self._last.get(key) or now
        interval = max(1, int(self.settings["interval_ms"]))
        cols = self._cols.get(key)
        if cols is None:
            cols = deque()
            self._cols[key] = cols
        # the fed symbol's clock is stamped BEFORE anything is evicted: with the stamp after, a
        # brand-new symbol reads as the least recently fed one and the store evicted what it had
        # just been handed.
        self._last[key] = now
        if len(self._cols) > int(self.settings["max_symbols"]):
            self._prune_symbols(keep=key)

        best_bid, best_ask = best_prices(book)
        # The record is monotonic: a book stamped older than the newest column cannot be the newer
        # truth, and appended it would leave the strip out of time order — one late frame reads as
        # phantom gaps and a collapsed span (T6-F03). A late book for the cell already recorded is
        # that cell's own snapshot and folds; anything older is skipped, counted, and not drawn.
        if cols and ts // interval < cols[-1].ts_ms // interval:
            self.counters["late_skipped"] += 1
            return len(cols)
        if cols and cols[-1].ts_ms // interval == ts // interval:
            # Same grid cell: the cell holds the newest snapshot of that cell, not a union of every
            # book that landed inside it. A union grew one cell to many times max_levels and kept
            # quoting sizes no book was showing any more (T6-F02).
            cell = cols[-1]
            cell.levels = dict(book)
            cell.best_bid, cell.best_ask = best_bid, best_ask
            cell.updates += 1
            self.counters["folded"] += 1
        else:
            cols.append(DepthColumn(ts_ms=(ts // interval) * interval, levels=book,
                                    best_bid=best_bid, best_ask=best_ask))
        while len(cols) > int(self.settings["max_columns_per_symbol"]):
            cols.popleft()
            self.counters["dropped_columns"] += 1
        self.counters["records"] += 1
        if now - self._last_prune_ms >= 1000:
            self.prune(now)
        return len(cols)

    def _prune_symbols(self, keep: str = "") -> None:
        """Evict the least recently fed symbols past the ceiling — the record can only be bounded
        by count if something decides which symbol loses. The symbol feeding us right now is never
        the victim (two symbols fed in the same millisecond would otherwise fight over the seat),
        and ties break by name so the choice is reproducible.
        """
        ceiling = int(self.settings["max_symbols"])
        while len(self._cols) > ceiling:
            victims = [s for s in self._cols if s != keep]
            if not victims:
                return
            victim = min(victims, key=lambda s: (self._last.get(s, 0), s))
            self._cols.pop(victim, None)
            self._last.pop(victim, None)
            self.counters["dropped_symbols"] += 1

    def prune(self, now_ms: Optional[int] = None) -> dict[str, Any]:
        """Drop columns older than the retention window, then symbols past the symbol ceiling."""
        now = int(now_ms or time.time() * 1000)
        self._last_prune_ms = now
        self.counters["prunes"] += 1
        cutoff = now - int(self.settings["retention_minutes"]) * 60_000
        dropped = 0
        empties = 0
        for key in list(self._cols):
            cols = self._cols[key]
            while cols and cols[0].ts_ms < cutoff:
                cols.popleft()
                dropped += 1
            if not cols:
                self._cols.pop(key, None)
                self._last.pop(key, None)
                empties += 1
        self.counters["dropped_columns"] += dropped
        self.counters["dropped_symbols"] += empties
        self._prune_symbols()
        return {"dropped_columns": dropped, "dropped_symbols": empties, "cutoff_ms": cutoff,
                "columns": self.columns(), "symbols": len(self._cols)}

    # ── queries ──
    def columns(self, symbol: str = "") -> int:
        if symbol:
            return len(self._cols.get(symbol_key(symbol)) or ())
        return sum(len(c) for c in self._cols.values())

    def bounds(self, symbol: str) -> tuple[int, int]:
        cols = self._cols.get(symbol_key(symbol))
        if not cols:
            return 0, 0
        return cols[0].ts_ms, cols[-1].ts_ms

    def has(self, symbol: str) -> bool:
        return bool(self._cols.get(symbol_key(symbol)))

    def series(self, symbol: str, from_ms: int = 0, to_ms: int = 0, bucket_ms: int = 0,
               *, limit_events: int = _MAX_EVENTS, bands: int = 0, now_ms: int = 0) -> dict[str, Any]:
        """The store's answer for one symbol — the same shape as ``series_of``, plus the symbol."""
        key = symbol_key(symbol)
        cols = list(self._cols.get(key) or ())
        out = series_of(cols, from_ms=from_ms, to_ms=to_ms, bucket_ms=bucket_ms,
                        interval_ms=int(self.settings["interval_ms"]),
                        bands=int(bands or self.settings["bands"]),
                        pull_pct=float(self.settings["pull_pct"]),
                        add_pct=float(self.settings["add_pct"]),
                        min_size=float(self.settings["min_size"]),
                        gap_multiple=int(self.settings["gap_multiple"]),
                        limit_events=limit_events, now_ms=int(now_ms or time.time() * 1000))
        out["symbol"] = key
        out["ok"] = bool(cols)
        out["detail"] = "" if cols else empty_note(key)
        # the window asked for vs the record that exists — the panel needs both to say why a
        # window came back empty without pretending the instrument has no history.
        have_from, have_to = self.bounds(key)
        out["have_from_ms"] = have_from
        out["have_to_ms"] = have_to
        out["settings"] = {"retention_minutes": self.settings["retention_minutes"],
                           "max_columns_per_symbol": self.settings["max_columns_per_symbol"],
                           "interval_ms": self.settings["interval_ms"],
                           "max_levels": self.settings["max_levels"],
                           "pull_pct": self.settings["pull_pct"],
                           "add_pct": self.settings["add_pct"],
                           "min_size": self.settings["min_size"]}
        out["retained"] = {"columns": len(cols), "levels": out.get("levels", 0),
                           "first_ms": out["first_ms"], "last_ms": out["last_ms"]}
        return out

    def events(self, symbol: str, from_ms: int = 0, to_ms: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        key = symbol_key(symbol)
        rows = [c for c in (self._cols.get(key) or ()) if (not from_ms or c.ts_ms >= int(from_ms))
                and (not to_ms or c.ts_ms <= int(to_ms))]
        return pull_add_of(rows, pull_pct=float(self.settings["pull_pct"]),
                           add_pct=float(self.settings["add_pct"]),
                           min_size=float(self.settings["min_size"]), limit=limit)

    def gaps(self, symbol: str) -> dict[str, Any]:
        return gaps_of(list(self._cols.get(symbol_key(symbol)) or ()),
                       interval_ms=int(self.settings["interval_ms"]),
                       gap_multiple=int(self.settings["gap_multiple"]))

    def staleness(self, symbol: str, now_ms: int = 0) -> dict[str, Any]:
        _first, last = self.bounds(symbol)
        return staleness_of(last, int(now_ms or time.time() * 1000),
                            interval_ms=int(self.settings["interval_ms"]))

    def symbols(self) -> list[dict[str, Any]]:
        """What the record holds right now, newest book first — what the panel's head reads.

        ``columns`` and ``levels`` describe the whole record; ``total_bid``/``total_ask`` are the
        newest column's, i.e. what that book looks like at the live edge.
        """
        now = int(time.time() * 1000)
        rows = []
        for key, cols in self._cols.items():
            if not cols:
                continue
            bid, ask = _totals(cols[-1].levels)
            rows.append({"symbol": key, "columns": len(cols), "levels": sum(len(c.levels) for c in cols),
                         "first_ms": cols[0].ts_ms, "last_ms": cols[-1].ts_ms,
                         "span_ms": max(0, cols[-1].ts_ms - cols[0].ts_ms),
                         "total_bid": bid, "total_ask": ask,
                         "state": staleness_of(cols[-1].ts_ms, now, int(self.settings["interval_ms"]))["state"]})
        rows.sort(key=lambda r: (-r["last_ms"], r["symbol"]))
        return rows

    def clear(self, symbol: str = "") -> dict[str, Any]:
        """Forget one symbol, or everything — the panel's Clear, and the engine's stop path."""
        if symbol:
            key = symbol_key(symbol)
            had = len(self._cols.pop(key, ()) or ())
            self._last.pop(key, None)
            return {"cleared": key, "columns": had}
        had = self.columns()
        self._cols.clear()
        self._last.clear()
        return {"cleared": "*", "columns": had}

    def stats(self) -> dict[str, Any]:
        """Measured, not estimated: the retention the store actually holds."""
        held = self.columns()
        return {
            "symbols": len(self._cols),
            "columns": held,
            "retained_levels": sum(len(c.levels) for cols in self._cols.values() for c in cols),
            "retention_ms": int(self.settings["retention_minutes"]) * 60_000,
            "max_columns_per_symbol": self.settings["max_columns_per_symbol"],
            "interval_ms": self.settings["interval_ms"],
            "counters": dict(self.counters),
        }


#: The process-wide store the hub feeds and the routes read (see ``get_store``).
_STORE = DepthHistoryStore()


def get_store() -> DepthHistoryStore:
    """The store the running engine feeds, falling back to the module singleton.

    Same shape as ``atlas/api.py``'s ``get_hub()``: prefer the live engine's own object, and answer
    the module singleton when nothing is attached (replay-only use, tests, a stopped engine).
    """
    try:
        from orderflow_system.desktop import engine as engine_mod
        system = engine_mod.engine.system
        hub = getattr(system, "_atlas_hub", None) if system is not None else None
        store = getattr(hub, "depth_history", None) if hub is not None else None
        if isinstance(store, DepthHistoryStore):
            return store
    except Exception:
        pass
    return _STORE


def set_store(store: Optional[DepthHistoryStore]) -> None:
    """Swap the module singleton — for tests, and for an engine that owns its own store."""
    global _STORE
    _STORE = store if store is not None else DepthHistoryStore()


def record(symbol: str, ts_ms: Any, levels: Any, *, tick_size: float = 0.0) -> int:
    """The one call the hub makes per depth update (see the wiring note in the report).

    Pass the book straight through: ``levels`` accepts the repo's ``OrderbookSnapshot``, a
    ``{price: (bid, ask)}`` mapping, or a list of rows — see ``coerce_levels``.

    §148 T6-F11: this wrote the module singleton while every route reads ``get_store()``; the two
    agreed only because the hub adopts the same object. A later ``set_store()`` would have split
    the writer from the readers, so the writer asks for the store the same way the routes do.
    """
    return get_store().record(symbol, ts_ms, levels, tick_size=tick_size)


# ── routes ──────────────────────────────────────────────────────────────────

@router.get("/depth-history")
async def depth_history_status() -> dict[str, Any]:
    """What the record holds, per symbol, and the settings in force."""
    store = get_store()
    return {"ok": True, "symbols": store.symbols(), "stats": store.stats(),
            "settings": dict(store.settings)}


@router.get("/depth-history/{symbol}")
async def depth_history_series(symbol: str, minutes: float = Query(default=0, ge=0, le=1440),
                               from_ms: int = Query(default=0, ge=0), to_ms: int = Query(default=0, ge=0),
                               bucket_ms: int = Query(default=0, ge=0),
                               events: int = Query(default=1, ge=0, le=1)) -> dict[str, Any]:
    """The depth-over-time series for one instrument.

    ``minutes`` is the usual ask (the last N minutes); explicit ``from_ms``/``to_ms`` win over it.
    An instrument with nothing recorded answers the refusal sentence — never an empty chart dressed
    up as data.
    """
    store = get_store()
    key = symbol_key(symbol)
    try:
        now = int(time.time() * 1000)
        lo, hi = int(from_ms), int(to_ms)
        if hi <= 0 and float(minutes) > 0:
            hi = now
            lo = max(0, now - int(float(minutes) * 60_000))
        payload = store.series(key, from_ms=lo, to_ms=hi, bucket_ms=int(bucket_ms),
                               limit_events=(_MAX_EVENTS if int(events) else 0), now_ms=now)
    except Exception:
        logger.debug("depth history series failed for %s", key, exc_info=True)
        return {"ok": False, "symbol": key, "buckets": [], "events": [], "gaps": {}, "profile": [],
                "detail": f"could not read the depth record for {key} — try again in a moment"}
    if not payload.get("ok"):
        return {"ok": False, "symbol": key, "buckets": [], "events": [], "gaps": {}, "profile": [],
                "bands": [], "settings": payload.get("settings") or {}, "detail": empty_note(key)}
    if not payload.get("buckets"):
        first = payload.get("have_from_ms") or payload.get("first_ms") or 0
        payload["detail"] = (f"{key} has depth recorded from "
                             f"{time.strftime('%H:%M', time.localtime(first / 1000))} — ask for a window "
                             "overlapping it, or widen the range")
    return payload


@router.post("/depth-history/retention")
async def depth_history_retention(payload: dict = Body(default={})) -> dict[str, Any]:
    """Set how much depth history to keep (minutes, plus the optional ceilings).

    The store prunes immediately, so a shorter retention frees the memory as the user asks, and the
    answer is the settings block that is now in force for progress and errors, not the request.

    §148: the block is also written to the config file — measured before the fix, this route changed
    the running store only, and the next start (which reads ``atlas.depth_history``) reverted it.
    """
    store = get_store()
    try:
        body = payload if isinstance(payload, dict) else {}
        # §148 T6-F10: the block's every key travels — max_symbols, gap_multiple and bands were
        # registered controls that this route silently could not touch, so two surfaces for one
        # block were each incomplete. `clean()` bounds whatever arrives.
        applied = store.configure({
            key: body.get(key, store.settings[key])
            for key in store.settings
        })
    except Exception:
        logger.debug("depth history retention refused", exc_info=True)
        return {"ok": False, "detail": "could not change the depth retention — the settings were left alone"}
    try:
        from orderflow_system.desktop import config_store
        config_store.merge_config({"atlas": {"depth_history": applied}})
    except Exception:
        # A retention that is in force but not yet on disk must not turn the answer into a failure —
        # the store is live either way, and the next successful save catches the file up.
        logger.debug("depth history retention: could not persist the block", exc_info=True)
    return {"ok": True, "settings": applied, "stats": store.stats()}


@router.post("/depth-history/clear")
async def depth_history_clear(payload: dict = Body(default={})) -> dict[str, Any]:
    """Forget the record for one instrument (or all of it) — the panel's Clear button."""
    store = get_store()
    body = payload if isinstance(payload, dict) else {}
    return {"ok": True, **store.clear(str(body.get("symbol") or ""))}
