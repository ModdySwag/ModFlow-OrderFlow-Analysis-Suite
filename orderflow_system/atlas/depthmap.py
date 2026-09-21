"""
Market-depth heatmap (the reference layout "Heatmap" module equivalent).

the reference layout shows the *history* of resting limit liquidity, not a single book snapshot:
price on one axis, time on the other, colour = resting size, bubbles = executed
aggression. This module builds exactly that from a Level-2 stream.

What it keeps
-------------
* one column per time bucket (default 1000 ms) holding ``price -> (bid, ask)``
* a rolling window of columns (default 900 ≈ 15 minutes)
* executed volume per price per bucket (for the bubble overlay)
* per-level event flags: ``stacked`` (liquidity added), ``pulled`` (liquidity
  withdrawn shortly before price arrived — the classic spoof footprint)

What it detects
---------------
* ``wall``      — level holding a top-N share of resting liquidity
* ``pull``      — size at a level dropped ≥ pull_pct within pull_window_ms while
                  price was within pull_near_ticks of it (spoofing candidate), and
                  larger than the size traded at that price since the previous
                  snapshot: the pull reported is the part the tape does not explain
* ``stack``     — size grew ≥ stack_pct within one snapshot (the growth test
                  alone — the traded accounting below belongs to the pull path,
                  not to this flag)
* ``iceberg``   — executed volume at a price ≫ displayed size at that price while
                  the level keeps being replenished (MBO inference, see
                  ``atlas/tapeflow.py`` for the print-side half)

All numbers are raw exchange quantities; price bucketing uses the instrument's
tick size so the heatmap aligns exactly with the footprint chart.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from orderflow_system.atlas.clock import as_epoch_ms
from orderflow_system.data.models import OrderbookSnapshot, Tick


@dataclass
class HeatLevel:
    """One price row inside a column."""

    bid: float = 0.0
    ask: float = 0.0

    @property
    def total(self) -> float:
        return self.bid + self.ask


@dataclass
class HeatColumn:
    """One time bucket of the heatmap."""

    ts_ms: int
    levels: dict[float, HeatLevel] = field(default_factory=dict)
    traded: dict[float, float] = field(default_factory=dict)   # price -> executed size
    trades: int = 0
    best_bid: float = 0.0
    best_ask: float = 0.0


@dataclass
class LevelEvent:
    """Something noteworthy that happened at a price level."""

    kind: str            # wall | pull | stack | iceberg | stop_run | sweep | wall_age
    price: float
    ts_ms: int
    size: float
    detail: str = ""
    direction: str = ""  # bid | ask | buy | sell
    #: how long the level had held when this fired (wall_age only, 0.0 elsewhere) — a rule's
    #: `min_age_s` scope reads it, and the alert message says it in words.
    held_ms: float = 0.0


class DepthHeatmap:
    """Rolling depth-heatmap state with spoof/stack/pull detection."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        bucket_ms: int = 1000,
        max_columns: int = 900,
        max_levels: int = 400,
        wall_quantile: float = 0.97,
        wall_age_ms: int = 120_000,
        upper_cutoff_pct: float = 5.0,
        upper_cutoff_abs: float = 0.0,
        pull_pct: float = 0.6,
        pull_window_ms: int = 3000,
        pull_near_ticks: float = 6.0,
        stack_pct: float = 1.5,
        price_span_ticks: int = 600,
    ) -> None:
        self.symbol = symbol
        #: SEC-07: snapshots the feed had flagged stale and this map therefore refused to fold.
        self._stale_skipped = 0
        self.tick_size = max(float(tick_size), 1e-9)
        self.bucket_ms = int(bucket_ms)
        self.max_columns = int(max_columns)
        self.max_levels = int(max_levels)
        self.wall_quantile = float(wall_quantile)
        self.wall_age_ms = int(wall_age_ms)
        self.upper_cutoff_pct = float(upper_cutoff_pct)
        # B2: an exact saturation size; 0 means "follow the percentile cut-off". Display-only —
        # it changes `scale_max` in the snapshot, never a value or a detection.
        self.upper_cutoff_abs = float(upper_cutoff_abs)
        # the reference platform's "extend last known volume", OFF by default here for a protocol
        # reason: Bybit's orderbook deltas *delete* a level when its size reaches zero, so
        # an absent level means "no orders there", not "not reported". Carrying those
        # forward would paint ghost liquidity into the map. The option stays available for
        # snapshot-only feeds (and for anyone who prefers the smoother read).
        self.carry_forward = False
        self.pull_pct = float(pull_pct)
        self.pull_window_ms = int(pull_window_ms)
        self.pull_near_ticks = float(pull_near_ticks)
        self.stack_pct = float(stack_pct)
        self.price_span_ticks = int(price_span_ticks)

        self._columns: deque[HeatColumn] = deque(maxlen=self.max_columns)
        self._prev: dict[float, HeatLevel] = {}
        self._events: deque[LevelEvent] = deque(maxlen=400)
        self._walls: dict[float, float] = {}          # price -> last seen size
        #: §148 / T7-F2: traded size per price since the last snapshot — the fact that tells a pull
        #: from consumption. The heatmap's pull card promises "size that vanished from a level
        #: without being traded", and before this the detector never checked: a level drained by
        #: prints counted as a pull like any other. `_traded_total` only ever rises (it is the
        #: account of prints at that price); `_traded_seen` is its watermark at the last snapshot.
        self._traded_total: dict[float, float] = {}
        self._traded_seen: dict[float, float] = {}
        self._wall_seen: dict[float, int] = {}        # price -> ts_ms of that sighting
        self._wall_first: dict[float, int] = {}       # price -> ts_ms the current streak began
        self._wall_age_fired: dict[float, int] = {}   # price -> ts_ms wall_age last fired
        self._last_tick_price: float = 0.0
        self._book_updates = 0
        self._first_ts: Optional[int] = None
        # Front/back-buffer idea from the reference layout heatmap author guide: the renderer
        # never rebuilds what it already has. `version` bumps on every ingest, so a
        # poll with an unchanged version can be answered from the last payload and
        # the canvas can skip repainting (the reference layout: "read Version, upload on change").
        self._version = 0
        self._snapshot_cache: Optional[tuple[tuple[int, int, int], dict[str, Any]]] = None
        self.snapshot_builds = 0
        # §122: the colour ceiling's leash — see _stabilise_scale.
        self._scale_hold = 0.0
        self._scale_hold_ts = 0

    # ── ingest ────────────────────────────────────────────────
    def on_orderbook(self, snapshot: OrderbookSnapshot, ts_ms: Optional[int] = None) -> list[LevelEvent]:
        """Fold one book snapshot in, and RETURN the level events it recorded.

        The events used to stop here: the map kept them for its own payload while the alert engine
        never saw one, so a rule of kind `heat_pull` / `heat_stack` / `wall_age` — every rule the
        heatmap's own alert buttons create — could not fire at all. The hub dispatches what this
        returns (hub.on_orderbook), which is what makes those kinds live.
        """
        if bool(getattr(snapshot, "stale", False)):
            # SEC-07: the feeds mark a snapshot stale when sequence continuity broke — and then
            # dispatched it anyway, so the heatmap drew, and wall alerts fired on, a book the feed
            # had just called untrustworthy. `engine.book_state()` was the only reader of the flag.
            # A stale snapshot is now not folded at all; the refusals are counted and surfaced.
            self._stale_skipped += 1
            return []
        ts = as_epoch_ms(ts_ms or snapshot.timestamp_ms)
        recorded: list[LevelEvent] = []
        self._version += 1
        col = self._column(ts)
        col.best_bid = snapshot.best_bid
        col.best_ask = snapshot.best_ask
        self._book_updates += 1

        levels: dict[float, HeatLevel] = {}
        for side, book in (("bid", snapshot.bids), ("ask", snapshot.asks)):
            for lvl in book[: self.max_levels]:
                price = self._bucket(lvl.price)
                entry = levels.setdefault(price, HeatLevel())
                if side == "bid":
                    entry.bid += lvl.quantity
                else:
                    entry.ask += lvl.quantity

        # detect stack / pull against the previous snapshot
        threshold = self._wall_threshold(self._prev or levels)
        for price, cur in levels.items():
            old = self._prev.get(price)
            if cur.total >= threshold:
                # §56 carry-over: a level ENTERING the band is the `wall` event rules of kind
                # `wall` wait for. Entry-triggered (previous size below the same threshold), so a
                # standing wall fires once and the hold that follows stays `wall_age`'s business.
                if old is None or old.total < threshold:
                    share = cur.total / max(1e-9, sum(lv.total for lv in levels.values()))
                    recorded.append(self._record("wall", price, ts, cur.total,
                                                 f"wall — {share * 100:.0f}% of visible resting size",
                                                 "bid" if cur.bid >= cur.ask else "ask"))
                self._walls[price] = cur.total
                self._wall_seen[price] = ts
                # Freshness and duration are different questions. _wall_seen answers "is it
                # still there"; the streak below answers "how long has it held", which is
                # the one a desk trades off a wall.
                began = self._wall_first.setdefault(price, ts)
                held_ms = ts - began
                if held_ms >= self.wall_age_ms and ts - self._wall_age_fired.get(price, 0) >= self.wall_age_ms:
                    self._wall_age_fired[price] = ts
                    recorded.append(self._record("wall_age", price, ts, cur.total,
                                                 f"held {held_ms / 60000.0:.1f} min",
                                                 "bid" if cur.bid >= cur.ask else "ask", held_ms=held_ms))
            else:
                self._wall_first.pop(price, None)     # the streak broke
            if old is None:
                continue
            old_total, new_total = old.total, cur.total
            if old_total > 0 and new_total >= old_total * self.stack_pct and new_total >= threshold:
                recorded.append(self._record("stack", price, ts, new_total, f"+{new_total - old_total:.2f} stacked", "bid" if cur.bid >= cur.ask else "ask"))
            if old_total > 0 and new_total <= old_total * (1 - self.pull_pct) and old_total >= threshold:
                near = self._price_is_near(price)
                if near:
                    # §148 / T7-F2: prints at this price since the previous snapshot are the trade
                    # that ate the level, not liquidity being pulled. What is reported is the part
                    # of the drop the tape does not explain, and only when that part is itself a
                    # pull-sized move — a level drained by its own prints is consumption, and the
                    # card's promise ("without being traded") is kept by saying nothing.
                    dropped = old_total - new_total
                    traded = max(0.0, self._traded_total.get(price, 0.0)
                                 - self._traded_seen.get(price, 0.0))
                    consumed = min(dropped, traded)
                    pulled = dropped - consumed
                    if pulled >= old_total * self.pull_pct:
                        detail = f"-{pulled:.2f} pulled near price"
                        if round(consumed, 2) > 0:     # a sub-cent traded part is not worth naming
                            detail += f" ({consumed:.2f} of the drop traded)"
                        recorded.append(self._record("pull", price, ts, old_total, detail,
                                                     "bid" if old.bid >= old.ask else "ask"))

        # the watermark for the next comparison: what has traded at each level up to this snapshot
        for price in levels:
            self._traded_seen[price] = self._traded_total.get(price, 0.0)

        self._prev = levels
        col.levels.update(levels)
        return recorded

    def on_tick(self, tick: Tick) -> None:
        ts = as_epoch_ms(tick.timestamp_ms)
        self._version += 1
        col = self._column(ts)
        price = self._bucket(tick.price)
        col.traded[price] = col.traded.get(price, 0.0) + tick.size
        col.trades += 1
        self._last_tick_price = tick.price
        # §148 / T7-F2: the same print, in the running account of what traded where — the pull
        # detector subtracts it from a level's drop so prints are never reported as pulls.
        self._traded_total[price] = self._traded_total.get(price, 0.0) + float(tick.size)

    # ── queries ───────────────────────────────────────────────
    def snapshot(self, columns: int = 300, max_rows: int = 260,
                 until_ms: Optional[int] = None) -> dict[str, Any]:
        """Return a render-ready matrix: prices on Y, time buckets on X.

        Rows are aggregated to a display step that fits the requested row count
        (the reference layout "price aggregation"): with a 0.01 instrument tick and a 200-level
        book, one row per tick would cover $2 of a $20 book. The step actually
        used is reported as ``step`` so the UI can label the axis.

        The payload is cached against ``version`` + shape: two polls at 1 Hz over a
        quiet instrument cost nothing after the first, and the UI can use
        ``version`` to skip a repaint entirely (see the reference layout heatmap author guide's
        front/back-buffer model). Callers get a shallow copy so they can keep
        adding their own keys (the API attaches ``walls``).
        """
        # the cache key must include the display options, not just the data version:
        # flipping carry-forward (or the cutoff) has to take effect immediately, and
        # with a data-only key it would wait for the next ingest to be noticed.
        key = (self._version, int(columns), int(max_rows), bool(self.carry_forward),
               float(self.upper_cutoff_pct), float(self.upper_cutoff_abs), int(until_ms or 0))
        cached = self._snapshot_cache
        if cached is not None and cached[0] == key:
            out = dict(cached[1])
            out["cached"] = True
            return out
        self.snapshot_builds += 1
        payload = self._build_snapshot(int(columns), int(max_rows), until_ms)
        self._snapshot_cache = (key, payload)
        out = dict(payload)
        out["cached"] = False
        return out

    def _build_snapshot(self, columns: int, max_rows: int,
                        until_ms: Optional[int] = None) -> dict[str, Any]:
        # §121: the time anchor. Without it a snapshot could only ever end at the live edge —
        # pan and zoom-at-cursor were impossible by construction. The slice keeps `columns`
        # buckets but ENDS at `until_ms`, so the window's width survives the anchor.
        all_cols = list(self._columns)
        if until_ms:
            all_cols = [c for c in all_cols if c.ts_ms <= int(until_ms)]
        cols = all_cols[-columns:]
        have_from = self._columns[0].ts_ms if self._columns else 0
        have_to = self._columns[-1].ts_ms if self._columns else 0
        if not cols:
            out = {"symbol": self.symbol, "tick": self.tick_size, "step": self.tick_size,
                   "buckets": [], "prices": [], "values": [], "traded": [], "events": [],
                   "version": self._version, "stats": self.stats(),
                   "bucket_ms": self.bucket_ms, "have_from_ms": have_from, "have_to_ms": have_to,
                   "until_ms": int(until_ms or 0)}
            if until_ms:
                span_min = max(0.0, (have_to - have_from) / 60000.0)
                out["note"] = ("no depth history at this time — the buffer holds %.0f min" % span_min)
            return out

        price_min, price_max = self._visible_range(cols)
        span = max(price_max - price_min, self.tick_size)
        target_rows = max(20, int(max_rows))
        auto_step = span / target_rows
        # snap the display step up to a whole number of instrument ticks
        step = max(self.tick_size, math.ceil(auto_step / self.tick_size) * self.tick_size)

        price_min = math.floor(price_min / step) * step
        price_max = math.ceil(price_max / step) * step
        rows = int(round((price_max - price_min) / step)) + 1
        if rows > target_rows:
            price_max = price_min + (target_rows - 1) * step
            rows = target_rows

        prices = [round(price_min + i * step, 10) for i in range(rows)]
        values = [[0.0] * len(cols) for _ in range(rows)]
        traded = [[0.0] * len(cols) for _ in range(rows)]

        def row_of(price: float) -> int:
            idx = int(round((price - price_min) / step))
            return idx if 0 <= idx < rows else -1

        for c_i, col in enumerate(cols):
            for price, lvl in col.levels.items():
                r = row_of(price)
                if r >= 0:
                    values[r][c_i] = round(values[r][c_i] + lvl.total, 6)
            for price, size in col.traded.items():
                r = row_of(price)
                if r >= 0:
                    traded[r][c_i] = round(traded[r][c_i] + size, 6)

        # the reference platform's "extend last known volume": on a gappy book (crypto prints on a
        # 0.1 grid, so a level can be absent for a whole minute) a hole means "no depth
        # reported", not "no depth there". Carry the last reported value forward until a
        # new one arrives, and say how many cells that touched.
        carried = 0
        if self.carry_forward:
            for r in range(rows):
                last = 0.0
                for c in range(len(cols)):
                    v = values[r][c]
                    if v > 0:
                        last = v
                    elif last > 0:
                        values[r][c] = last
                        carried += 1

        flat = sorted(v for row in values for v in row if v > 0)
        stat_cut = 0.0
        pinned = float(self.upper_cutoff_abs) > 0
        if flat:
            cut = max(0.0, min(50.0, float(self.upper_cutoff_pct)))
            idx = min(len(flat) - 1, int(round((1.0 - cut / 100.0) * (len(flat) - 1))))
            stat_cut = flat[idx]
            # B2: a pinned absolute ceiling wins over the percentile one; the flat[0] guard still
            # applies, so a pin below the smallest size saturates everything rather than zeroing.
            if pinned:
                stat_cut = float(self.upper_cutoff_abs)
            stat_cut = max(stat_cut, flat[0])
        # §122: the ceiling must not re-grade itself under the user's eyes. Measured before this:
        # "top share of the visible window" climbed x1.84 in four minutes as the window filled, so
        # every cell slid from bright to dull (the owner's report: "initially bright then dulls").
        # The percentile stays the TARGET; the APPLIED ceiling is leashed — except an explicit pin,
        # which is the user's own number and applies at once.
        if pinned and flat:
            scale_max = stat_cut
        else:
            scale_max = self._stabilise_scale(stat_cut, int(time.time() * 1000))

        return {
            "symbol": self.symbol,
            "tick": self.tick_size,
            "step": step,
            "version": self._version,
            "bucket_ms": self.bucket_ms,
            "have_from_ms": have_from,
            "have_to_ms": have_to,
            "until_ms": int(until_ms or 0),
            "upper_cutoff_pct": self.upper_cutoff_pct,
            "carry_forward": bool(self.carry_forward),
            "carried_cells": carried,
            "scale_max": round(scale_max, 6),
            "scale_target": round(stat_cut, 6),   # §122: the raw percentile (diagnostics)
            "buckets": [c.ts_ms for c in cols],
            "prices": prices,
            "values": values,
            "traded": traded,
            "best": [{"bid": c.best_bid, "ask": c.best_ask, "trades": c.trades} for c in cols],
            "events": [e.__dict__ for e in list(self._events)[-120:]],
            "stats": self.stats(),
        }

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for e in self._events:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        return {
            "book_updates": self._book_updates,
            "columns": len(self._columns),
            "span_ms": (self._columns[-1].ts_ms - self._columns[0].ts_ms) if len(self._columns) > 1 else 0,
            "walls": len(self._walls),
            # R-01: the measured retention (sum of levels across columns) — the number the audit's
            # 15-minute fill curve was about, now visible in the diagnostics instead of inferred.
            "retained_levels": sum(len(c.levels) for c in self._columns),
            "events": counts,
            "version": self._version,
            "snapshot_builds": self.snapshot_builds,
            "stale_skipped": self._stale_skipped,     # SEC-07
        }

    def events(self, kind: str = "", limit: int = 100) -> list[dict]:
        items = [e for e in self._events if not kind or e.kind == kind]
        return [e.__dict__ for e in items[-limit:]]

    def wall_durations(self) -> list[dict]:
        """Walls with how long each has held, longest first — what the map cannot show."""
        latest = self._columns[-1].ts_ms if self._columns else 0
        rows = []
        for price, size in self._walls.items():
            began = self._wall_first.get(price)
            if began is None:
                continue
            rows.append({"price": price, "size": size, "held_ms": int(latest - began) if latest else 0})
        return sorted([r for r in rows if r["held_ms"] > 0], key=lambda r: -r["held_ms"])

    def wall_prices(self, top: int = 10, max_age_ms: int = 120_000) -> list[dict]:
        """Largest resting levels still fresh, measured on the book's own clock."""
        latest = self._columns[-1].ts_ms if self._columns else 0
        if latest:
            fresh = {p: s for p, s in self._walls.items() if latest - self._wall_seen.get(p, 0) <= max_age_ms}
        else:
            fresh = dict(self._walls)
        items = sorted(fresh.items(), key=lambda kv: -kv[1])[:top]
        return [{"price": p, "size": s} for p, s in items]

    def clear(self) -> None:
        self._columns.clear()
        self._scale_hold = 0.0        # §122: a fresh buffer is a fresh regime
        self._scale_hold_ts = 0
        self._prev.clear()
        self._events.clear()
        self._walls.clear()
        self._wall_seen.clear()
        self._book_updates = 0
        self._version += 1
        self._snapshot_cache = None

    # ── internals ─────────────────────────────────────────────
    def _bucket(self, price: float) -> float:
        return round(round(price / self.tick_size) * self.tick_size, 10)

    def _column(self, ts_ms: int) -> HeatColumn:
        bucket = (ts_ms // self.bucket_ms) * self.bucket_ms
        if self._columns:
            last = self._columns[-1]
            if bucket <= last.ts_ms:
                # Same bucket, or data that arrived out of order (the two feeds
                # have independent clocks): fold it into the current column.
                # Appending here used to create duplicate columns and destroy
                # the time axis.
                return last
        self._columns.append(HeatColumn(ts_ms=bucket))
        if self._first_ts is None:
            self._first_ts = bucket
        return self._columns[-1]

    #: §122: the ceiling's leash — move a share of the gap, never faster than a share per minute.
    SCALE_GAP = 0.25                       # toward the fresh percentile per build
    SCALE_PER_S = 0.05 / 60.0              # …capped at 5% of itself per minute of wall time

    def _stabilise_scale(self, target: float, now_ms: int) -> float:
        """Leash the colour ceiling so the map cannot re-grade itself in seconds.

        The ceiling is "the top share of the visible window", and while a window fills that
        statistic drifts hard (x1.84 in four measured minutes) — the same cells render bright at
        minute one and dull at minute four. Here the statistic is only the TARGET: the applied
        value walks toward it by SCALE_GAP of the gap, capped at SCALE_PER_S of itself per second
        of wall time (a heap-light, like a level meter). A cleared store forgets the hold.
        """
        if target <= 0:
            return 0.0
        prev = self._scale_hold
        if prev <= 0:
            self._scale_hold = target
            self._scale_hold_ts = now_ms
            return target
        dt = max(0, now_ms - self._scale_hold_ts)
        cap = prev * self.SCALE_PER_S * (dt / 1000.0)
        step = (target - prev) * self.SCALE_GAP
        if step > cap:
            step = cap
        elif step < -cap:
            step = -cap
        out = max(0.0, prev + step)
        self._scale_hold = out
        self._scale_hold_ts = now_ms
        return out

    def _wall_threshold(self, levels: dict[float, HeatLevel]) -> float:
        sizes = sorted((lv.total for lv in levels.values()), reverse=True)
        if not sizes:
            return 0.0
        k = max(0, min(len(sizes) - 1, int(math.floor((1 - self.wall_quantile) * len(sizes))) - 1))
        return sizes[k]

    def _price_is_near(self, price: float) -> bool:
        if not self._last_tick_price:
            return False
        return abs(price - self._last_tick_price) <= self.pull_near_ticks * self.tick_size

    def _record(self, kind: str, price: float, ts: int, size: float, detail: str, direction: str,
                held_ms: float = 0.0) -> LevelEvent:
        self._version += 1
        event = LevelEvent(kind=kind, price=price, ts_ms=ts, size=round(size, 6), detail=detail,
                           direction=direction, held_ms=float(held_ms or 0))
        self._events.append(event)
        return event

    def _visible_range(self, cols: Iterable[HeatColumn]) -> tuple[float, float]:
        prices: list[float] = []
        for c in cols:
            prices.extend(c.levels.keys())
        if self._last_tick_price:
            prices.append(self._bucket(self._last_tick_price))
        if not prices:
            return 0.0, 0.0
        return min(prices), max(prices)
