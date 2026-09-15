"""Participants' intent — reading the book before the chart moves.

Modelled on the reference layout's order-book analysis toolset (help.atas.net), which is what the
"what order flow analysis reveals" material demonstrates:

* **Liquidity Pressure / DOM Pressure** — weighted liquidity of each side of the
  book, ``Σ(volume × e^(−level / decay))`` over the top N levels, normalised
  against a sliding-window maximum so the number reads as "how unusual is this
  side of the book right now, 0–100 %". Training period on start (default 5 min),
  alerts only after training — the same contract the reference layout documents.
* **Depth changes** — additions vs removals of resting size per side, near price
  and overall: who is building, who is retreating.
* **Tape quality** — trades at bid / at ask / inside the spread / above the ask /
  below the bid (the last two are slippage prints, i.e. someone paid through).
* **Absorption** — aggression that does not move price. Large one-sided volume with
  no displacement means the other side is being filled passively.
* **Pulled size (spoof evidence)** — a level that was prominent near price and
  vanished without being traded.
* **Trapped side** — a level broken by a few ticks and then reclaimed: the traders
  who chased the break are on the wrong side of it.

Everything is fail-soft and read-only: no orders, no account, public data. The
verdict line is generated from the arithmetic above and says so; it is a reading of
the book, not a recommendation.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from orderflow_system.data.models import OrderbookSnapshot, Tick
from orderflow_system.data.enums import as_value

#: Side helpers


def _side(tick: Tick) -> str:
    return as_value(tick.side)


def _as_epoch_ms(value: Any) -> int:
    """Normalise a venue timestamp: seconds → ms, and reject non-clocks.

    Two traps live here, both seen with real Bybit data:

    * the deeper (``orderbook.200``) feed stamps its snapshots in **seconds** while
      the trade feed uses milliseconds;
    * the same snapshot can carry the book's **update id** (``u``) as its timestamp —
      an integer of ~1e8 that is not a clock at all. Treating it as one made every
      book look decades stale, which silently disabled the tape classification.

    Anything that is not plausible as a 2020-or-later epoch is replaced with now.
    """
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return int(time.time() * 1000)
    if ms <= 0:
        return int(time.time() * 1000)
    if ms < 10_000_000_000:              # seconds (2286-11) → ms
        ms *= 1000
    if ms < 1_577_000_000_000:           # before 2020-01-01 → not a clock (update id)
        return int(time.time() * 1000)
    return ms


@dataclass
class PulledSize:
    """A resting order that left the book without being traded."""

    ts_ms: int
    price: float
    size: float
    side: str                 # 'bid' | 'ask'
    distance_ticks: float
    traded: float = 0.0
    age_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"ts_ms": self.ts_ms, "price": self.price, "size": round(self.size, 6),
                "side": self.side, "distance_ticks": round(self.distance_ticks, 2),
                "traded": round(self.traded, 6), "age_ms": self.age_ms}


@dataclass
class TrapEvent:
    """A break that failed: the side that chased it is trapped."""

    ts_ms: int
    side: str                 # 'longs' | 'shorts' — who is trapped
    level: float
    beyond_ticks: float
    reclaim_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {"ts_ms": self.ts_ms, "side": self.side, "level": self.level,
                "beyond_ticks": round(self.beyond_ticks, 2), "reclaim_ms": self.reclaim_ms}


class ParticipantIntent:
    """Rolling read of what the order book says about each side's intentions."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        levels: int = 10,
        decay: float = 3.0,
        threshold_pct: float = 80.0,
        training_s: float = 300.0,
        absorb_window_s: float = 20.0,
        absorb_ref_ticks: float = 8.0,
        spoof_near_ticks: float = 10.0,
        spoof_size_mult: float = 3.0,
        spoof_max_traded_pct: float = 20.0,
        trap_ticks: float = 3.0,
        trap_window_s: float = 120.0,
        trap_reclaim_s: float = 60.0,
        history_s: int = 900,
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.levels = max(5, min(50, int(levels)))
        self.decay = max(1.0, min(20.0, float(decay)))
        self.threshold_pct = max(1.0, min(100.0, float(threshold_pct)))
        self.training_s = max(0.0, float(training_s))
        self.absorb_window_ms = int(absorb_window_s * 1000)
        self.absorb_ref_ticks = max(1.0, float(absorb_ref_ticks))
        self.spoof_near_ticks = max(1.0, float(spoof_near_ticks))
        self.spoof_size_mult = max(1.0, float(spoof_size_mult))
        self.spoof_max_traded_pct = max(0.0, float(spoof_max_traded_pct))
        self.trap_ticks = max(1.0, float(trap_ticks))
        self.trap_window_ms = int(trap_window_s * 1000)
        self.trap_reclaim_ms = int(trap_reclaim_s * 1000)

        self._started_ms: int = 0
        # per-second buckets: [buy_aggression, sell_aggression, close, trades]
        self._sec: dict[int, list[float]] = {}
        self._history_s = int(history_s)
        # depth-change tallies
        self._depth_adds = {"bid": 0.0, "ask": 0.0}
        self._depth_removes = {"bid": 0.0, "ask": 0.0}
        self._prev_levels: dict[float, dict[str, float]] = {}
        # tape quality
        self._tape = {"at_bid": 0.0, "at_ask": 0.0, "inside": 0.0,
                      "above_ask": 0.0, "below_bid": 0.0, "stale_book": 0.0}
        self._tape_vol = dict.fromkeys(self._tape, 0.0)
        # traded volume per price (for spoof evidence)
        self._traded_at: dict[float, float] = {}
        # level bookkeeping for pulled-size detection: price -> [size, first_seen_ms, peak_size]
        self._watched: dict[float, list[float]] = {}
        # pressure state
        self._max_weighted = {"bid": 0.0, "ask": 0.0}
        self._weighted = {"bid": 0.0, "ask": 0.0}
        self._bid_pct = 0.0
        self._ask_pct = 0.0
        self._observations = 0
        # A "percentage of normal" is meaningless before there is a normal: 30 book
        # updates must have been seen before pressure can alert, on top of the
        # training-period requirement (which mirrors the reference layout's own gate).
        self.min_observations = 30
        self._w_hist: deque[tuple[int, float, float]] = deque(maxlen=20_000)
        # tape classification only trusts a book this fresh, and tolerates one tick
        # either side of the touch (the tape is faster than the book snapshot)
        self.tape_fresh_ms = 1500
        self.tape_tolerance_ticks = 0.5
        self._last_book_ms = 0
        self._best = {"bid": 0.0, "ask": 0.0}
        # detections
        self.pulled: deque[PulledSize] = deque(maxlen=60)
        self.traps: deque[TrapEvent] = deque(maxlen=40)
        self.pressure_events: deque[dict[str, Any]] = deque(maxlen=80)
        self._last_trap: dict[str, int] = {}
        self._last_pull_ms: dict[float, int] = {}
        # window extremes for the trapped-side test
        self._extreme: dict[str, Any] = {"hi": 0.0, "hi_ts": 0, "lo": 0.0, "lo_ts": 0,
                                         "broke_hi": 0.0, "broke_lo": 0.0}
        self._last_price = 0.0
        self.version = 0
        self._snapshot_cache: Optional[tuple[int, dict[str, Any]]] = None

    # ── ingest ────────────────────────────────────────────────
    def on_orderbook(self, snapshot: OrderbookSnapshot, ts_ms: Optional[int] = None) -> dict[str, Any]:
        """Update pressure, depth changes and pulled-size watching. Returns alerts."""
        ts = _as_epoch_ms(ts_ms or snapshot.timestamp_ms)
        if not self._started_ms:
            self._started_ms = ts
        self.version += 1
        self._last_book_ms = ts

        bids = [(float(l.price), float(l.quantity)) for l in (snapshot.bids or [])[:self.levels]]
        asks = [(float(l.price), float(l.quantity)) for l in (snapshot.asks or [])[:self.levels]]
        if not bids or not asks:
            return {}
        best_bid, best_ask = bids[0][0], asks[0][0]
        self._best = {"bid": best_bid, "ask": best_ask}
        mid = (best_bid + best_ask) / 2.0

        # ── DOM pressure: Σ(volume × e^(−level / decay)) ──
        def weighted(rows: list[tuple[float, float]]) -> float:
            total = 0.0
            for idx, (_price, qty) in enumerate(rows, start=1):
                total += qty * math.exp(-idx / self.decay)
            return total

        w_bid = weighted(bids)
        w_ask = weighted(asks)
        self._weighted = {"bid": w_bid, "ask": w_ask}
        self._observations += 1
        # sliding-window maximum normalisation (the reference layout: training period, then a
        # sliding window keeps the scale adapted to current conditions). The window
        # is a real window: an old spike must NOT pin the scale down forever.
        self._w_hist.append((ts, w_bid, w_ask))
        window_ms = int(max(self.training_s, 300.0) * 1000)
        cutoff = ts - window_ms
        while self._w_hist and self._w_hist[0][0] < cutoff:
            self._w_hist.popleft()
        self._max_weighted["bid"] = max(r[1] for r in self._w_hist) if self._w_hist else w_bid
        self._max_weighted["ask"] = max(r[2] for r in self._w_hist) if self._w_hist else w_ask
        self._bid_pct = 100.0 * w_bid / self._max_weighted["bid"] if self._max_weighted["bid"] else 0.0
        self._ask_pct = 100.0 * w_ask / self._max_weighted["ask"] if self._max_weighted["ask"] else 0.0

        out: dict[str, Any] = {}

        # ── depth changes vs the previous snapshot ──
        if self._prev_levels:
            for side, rows in (("bid", bids), ("ask", asks)):
                for price, qty in rows:
                    key = price if side == "bid" else -price
                    prev = self._prev_levels.get(key)
                    prev_qty = prev[0] if prev else 0.0
                    delta = qty - prev_qty
                    if delta > 0:
                        self._depth_adds[side] += delta
                    elif delta < 0:
                        self._depth_removes[side] += -delta
        self._prev_levels = {p: [q, ts] for p, q in bids}
        self._prev_levels.update({-p: [q, ts] for p, q in asks})

        # ── pulled-size watching (spoof evidence) ──
        med = self._median_level_size(bids, asks)
        watch_threshold = max(med * self.spoof_size_mult, self.tick_size)
        now_levels = {p: q for p, q in bids}
        now_levels.update({p: q for p, q in asks})
        for price, qty in now_levels.items():
            nearby = abs(price - mid) / self.tick_size <= self.spoof_near_ticks
            entry = self._watched.get(price)
            if entry is None:
                if nearby and qty >= watch_threshold:
                    self._watched[price] = [qty, ts, qty]
            else:
                entry[2] = max(entry[2], qty)
                entry[0] = qty
        for price in list(self._watched):
            entry = self._watched[price]
            size, first_ms, peak = entry
            current = now_levels.get(price)
            if current is not None and current >= peak - watch_threshold:
                continue                                   # still there in size — keep watching
            removed = peak - (current or 0.0)
            traded = self._traded_at.get(price, [0.0, 0])[0]
            traded_pct = (traded / peak * 100.0) if peak else 100.0
            age_ms = ts - int(first_ms)
            if peak >= watch_threshold and removed >= watch_threshold and traded_pct <= self.spoof_max_traded_pct:
                side = "bid" if price <= mid else "ask"
                if ts - self._last_pull_ms.get(price, 0) > 5000:      # one record per level per 5 s
                    self._last_pull_ms[price] = ts
                    ev = PulledSize(ts_ms=ts, price=price, size=removed, side=side,
                                    distance_ticks=abs(price - mid) / self.tick_size,
                                    traded=traded, age_ms=age_ms)
                    self.pulled.append(ev)
                    out.setdefault("pulled_size", []).append(ev)
                    self.version += 1
            del self._watched[price]

        # ── pressure alerts (disabled during training, as the reference layout does) ──
        if self.training_done() and self._observations >= self.min_observations:
            for side, pct in (("bid", self._bid_pct), ("ask", self._ask_pct)):
                if pct >= self.threshold_pct:
                    last = next((e for e in reversed(self.pressure_events) if e["side"] == side), None)
                    if not last or ts - last["ts_ms"] > 30_000:       # at most one per side per 30 s
                        ev = {"ts_ms": ts, "side": side, "pct": round(pct, 1),
                              "threshold": self.threshold_pct,
                              "price": best_bid if side == "bid" else best_ask}
                        self.pressure_events.append(ev)
                        out.setdefault("intent_pressure", []).append(ev)
                        self.version += 1
        return out

    def on_tick(self, tick: Tick) -> dict[str, Any]:
        """Update tape quality, aggression buckets, absorption and traps."""
        ts = _as_epoch_ms(tick.timestamp_ms)
        if not self._started_ms:
            self._started_ms = ts
        self.version += 1
        price = float(tick.price)
        size = float(tick.size)
        side = _side(tick)
        self._last_price = price

        # ── tape quality (Smart DOM "Trades" column) ──
        # Only classify against a fresh book: a print cannot be judged against a
        # snapshot that is older than the print, or every fast move reads as
        # "slippage". Beyond the touch, allow one tick of tolerance.
        bid, ask = self._best.get("bid", 0.0), self._best.get("ask", 0.0)
        book_age_ms = ts - self._last_book_ms if self._last_book_ms else 99999
        if bid and ask and book_age_ms <= self.tape_fresh_ms:
            tol = self.tick_size * self.tape_tolerance_ticks
            da, db = abs(price - ask), abs(price - bid)
            if price > ask + tol:
                bucket = "above_ask"
            elif price < bid - tol:
                bucket = "below_bid"
            elif min(da, db) <= tol and abs(da - db) > 1e-12:
                bucket = "at_ask" if da < db else "at_bid"
            else:
                bucket = "inside"                      # at the midpoint / inside the spread
            self._tape[bucket] += 1
            self._tape_vol[bucket] += size
        else:
            self._tape["stale_book"] += 1
            self._tape_vol["stale_book"] += size

        # ── traded volume per price (spoof evidence needs this) ──
        row_traded = self._traded_at.get(price)
        if row_traded is None:
            self._traded_at[price] = [size, float(ts)]
        else:
            row_traded[0] += size
            row_traded[1] = float(ts)
        if len(self._traded_at) > 8000:                       # drop prices nobody has printed for 10 min
            cutoff = ts - 600_000
            for stale in [p for p, r in self._traded_at.items() if r[1] < cutoff]:
                self._traded_at.pop(stale, None)

        # ── per-second aggression buckets ──
        sec = ts // 1000
        row = self._sec.get(sec)
        if row is None:
            row = [0.0, 0.0, price, 0.0]
            self._sec[sec] = row
        if side == "buy":
            row[0] += size
        else:
            row[1] += size
        row[2] = price
        row[3] += 1
        if len(self._sec) > self._history_s:
            for old in sorted(self._sec)[: len(self._sec) - self._history_s]:
                self._sec.pop(old, None)

        out: dict[str, Any] = {}

        # ── trapped side: a break beyond the recent extreme that comes back ──
        # Order matters: measure distance to the OLD extreme first, then let the
        # extreme move, then freeze it (a break in progress must not drag the base
        # along with it, or nothing is ever measurable).
        ext = self._extreme
        breaking_hi = bool(ext.get("broke_hi")) and ts - ext["broke_hi"] <= self.trap_reclaim_ms
        breaking_lo = bool(ext.get("broke_lo")) and ts - ext["broke_lo"] <= self.trap_reclaim_ms
        beyond_hi = (price - ext["hi"]) / self.tick_size if ext["hi"] else 0.0
        beyond_lo = (ext["lo"] - price) / self.tick_size if ext["lo"] else 0.0

        if not breaking_hi:
            if ext.get("broke_hi"):                       # the break held → re-base on price
                ext["broke_hi"] = 0
                ext["hi"], ext["hi_ts"] = price, ts
            if not ext["hi"] or price > ext["hi"]:
                ext["hi"], ext["hi_ts"] = price, ts
        if not breaking_lo:
            if ext.get("broke_lo"):
                ext["broke_lo"] = 0
                ext["lo"], ext["lo_ts"] = price, ts
            if not ext["lo"] or price < ext["lo"]:
                ext["lo"], ext["lo_ts"] = price, ts

        window_start = ts - self.trap_window_ms
        if ext["hi_ts"] < window_start and not breaking_hi:      # stale base: rebuild from the window
            recent = [r[2] for s, r in self._sec.items() if s * 1000 >= window_start]
            if recent:
                ext["hi"], ext["hi_ts"] = max(recent), ts
        if ext["lo_ts"] < window_start and not breaking_lo:
            recent = [r[2] for s, r in self._sec.items() if s * 1000 >= window_start]
            if recent:
                ext["lo"], ext["lo_ts"] = min(recent), ts

        if not ext.get("broke_hi") and beyond_hi >= self.trap_ticks:
            ext["broke_hi"] = ts
            ext["hi"] = price - beyond_hi * self.tick_size       # keep the pre-break level as the base
        if not ext.get("broke_lo") and beyond_lo >= self.trap_ticks:
            ext["broke_lo"] = ts
            ext["lo"] = price + beyond_lo * self.tick_size
        if ext.get("broke_hi") and ts - ext["broke_hi"] <= self.trap_reclaim_ms \
                and price < ext["hi"] - self.trap_ticks * self.tick_size:
            if ts - self._last_trap.get("longs", 0) > 60_000:
                self._last_trap["longs"] = ts
                ev = TrapEvent(ts_ms=ts, side="longs", level=ext["hi"],
                               beyond_ticks=beyond_hi, reclaim_ms=ts - ext["broke_hi"])
                self.traps.append(ev)
                out["trapped"] = ev
                ext["broke_hi"] = 0
                self.version += 1
        elif ext.get("broke_lo") and ts - ext["broke_lo"] <= self.trap_reclaim_ms \
                and price > ext["lo"] + self.trap_ticks * self.tick_size:
            if ts - self._last_trap.get("shorts", 0) > 60_000:
                self._last_trap["shorts"] = ts
                ev = TrapEvent(ts_ms=ts, side="shorts", level=ext["lo"],
                               beyond_ticks=beyond_lo, reclaim_ms=ts - ext["broke_lo"])
                self.traps.append(ev)
                out["trapped"] = ev
                ext["broke_lo"] = 0
                self.version += 1
        return out

    # ── derived ───────────────────────────────────────────────
    def training_done(self) -> bool:
        if not self._started_ms:
            return False
        return (time.time() * 1000 - self._started_ms) >= self.training_s * 1000

    def training_remaining_s(self) -> int:
        if not self._started_ms or self.training_s <= 0:
            return 0
        left = self.training_s * 1000 - (time.time() * 1000 - self._started_ms)
        return max(0, int(left / 1000))

    @staticmethod
    def _median_level_size(bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> float:
        vals = sorted(q for _p, q in (list(bids) + list(asks)))
        if not vals:
            return 0.0
        return vals[len(vals) // 2]

    def _window(self, seconds: float) -> list[list[float]]:
        now = int(time.time())
        lo = now - int(seconds)
        return [row for sec, row in sorted(self._sec.items()) if sec >= lo]

    def absorption(self) -> dict[str, Any]:
        """Aggression that did not move price: the other side is absorbing."""
        rows = self._window(self.absorb_window_ms / 1000.0)
        if len(rows) < 3:
            return {"available": False}
        buy = sum(r[0] for r in rows)
        sell = sum(r[1] for r in rows)
        total = buy + sell
        if total <= 0:
            return {"available": False}
        first_price, last_price = rows[0][2], rows[-1][2]
        displacement_ticks = (last_price - first_price) / self.tick_size
        net = buy - sell
        share = abs(net) / total
        # How much of the move went WITH the aggressors, and how much against them.
        # A passive side that both stops the move and pushes price back is the
        # strongest read — the old formula scored that case as zero.
        along = displacement_ticks * (1.0 if net > 0 else -1.0)
        ref = max(1.0, self.absorb_ref_ticks)
        failure = max(0.0, 1.0 - min(1.0, max(0.0, along) / ref))
        adverse = min(1.0, max(0.0, -along) / ref)
        score = round(100.0 * share * (0.6 * failure + 0.4 * adverse), 1)
        # who is absorbing: the side that is NOT the aggressor
        if net > 0 and displacement_ticks <= 0:
            absorbing, aggressor = "sellers", "buyers"
        elif net < 0 and displacement_ticks >= 0:
            absorbing, aggressor = "buyers", "sellers"
        else:
            return {"available": True, "absorbing": "", "aggressor": "",
                    "score": score, "buy_volume": round(buy, 6), "sell_volume": round(sell, 6),
                    "displacement_ticks": round(displacement_ticks, 2),
                    "note": "aggression is moving price — no absorption read"}
        return {"available": True, "absorbing": absorbing, "aggressor": aggressor, "score": score,
                "buy_volume": round(buy, 6), "sell_volume": round(sell, 6),
                "displacement_ticks": round(displacement_ticks, 2),
                "note": f"{aggressor} are aggressive ({round(share * 100)}% of the volume) and price has "
                        f"moved {round(displacement_ticks, 1)} ticks — {absorbing} are absorbing"}

    def tape_quality(self) -> dict[str, Any]:
        classified = sum(v for k, v in self._tape.items() if k != "stale_book") or 1.0
        out = {k: int(v) for k, v in self._tape.items()}
        out["volumes"] = {k: round(v, 4) for k, v in self._tape_vol.items()}
        out["share_pct"] = {k: round(v / classified * 100.0, 1)
                            for k, v in self._tape.items() if k != "stale_book"}
        out["slippage_prints"] = int(self._tape["above_ask"] + self._tape["below_bid"])
        out["fresh_book"] = self._last_book_ms > 0 and (time.time() * 1000 - self._last_book_ms) <= self.tape_fresh_ms
        return out

    def pressure(self) -> dict[str, Any]:
        return {
            "buy_weighted": round(self._weighted.get("bid", 0.0), 6),
            "sell_weighted": round(self._weighted.get("ask", 0.0), 6),
            "buy_weighted_max": round(self._max_weighted["bid"], 6),
            "sell_weighted_max": round(self._max_weighted["ask"], 6),
            "window_s": int(max(self.training_s, 300.0)),
            "buy_pct_of_normal": round(self._bid_pct, 1),
            "sell_pct_of_normal": round(self._ask_pct, 1),
            "side": "buyers" if self._bid_pct > self._ask_pct else "sellers",
            "edge_pct": round(abs(self._bid_pct - self._ask_pct), 1),
            "threshold_pct": self.threshold_pct,
            "levels": self.levels,
            "decay": self.decay,
            "training": not self.training_done(),
            "training_remaining_s": self.training_remaining_s(),
            "formula": "SUM(volume * e^(-level/decay)) over the top levels, normalised "
                       "against the sliding-window maximum of the same side",
        }

    def depth_changes(self) -> dict[str, Any]:
        adds, removes = self._depth_adds, self._depth_removes
        return {
            "bids_added": round(adds["bid"], 6), "bids_removed": round(removes["bid"], 6),
            "asks_added": round(adds["ask"], 6), "asks_removed": round(removes["ask"], 6),
            "bid_net": round(adds["bid"] - removes["bid"], 6),
            "ask_net": round(adds["ask"] - removes["ask"], 6),
            "note": "cumulative depth added/removed since this window started — "
                    "who is building and who is retreating",
        }

    def verdict(self) -> dict[str, Any]:
        """One plain-language line, built from the numbers above (no advice)."""
        p = self.pressure()
        a = self.absorption()
        d = self.depth_changes()
        bits: list[str] = []
        if p["training"]:
            bits.append(f"still training ({p['training_remaining_s']}s)")
        elif p["edge_pct"] >= 10:
            bits.append(f"book pressure favours {p['side']} "
                        f"({p['buy_pct_of_normal']:.0f}% vs {p['sell_pct_of_normal']:.0f}% of normal)")
        else:
            bits.append("book pressure is balanced")
        if a.get("absorbing"):
            bits.append(f"{a['absorbing']} absorbing {a['aggressor']} (score {a['score']})")
        if d["bid_net"] > 0 > d["ask_net"]:
            bits.append("bids building while asks retreat")
        elif d["ask_net"] > 0 > d["bid_net"]:
            bits.append("asks building while bids retreat")
        if self.pulled:
            last = self.pulled[-1]
            bits.append(f"last pull {last.size:.4g} on the {last.side} "
                        f"{last.distance_ticks:.1f} ticks away")
        if self.traps:
            last_trap = self.traps[-1]
            bits.append(f"{last_trap.side} trapped at {last_trap.level} "
                        f"({last_trap.reclaim_ms / 1000:.0f}s ago)")
        side = p["side"] if not p["training"] else ""
        return {"line": "; ".join(bits) if bits else "no read yet — waiting for the book to fill",
                "side": side, "confidence": min(100, int(p["edge_pct"] * 2 + (30 if a.get("absorbing") else 0)))}

    # ── snapshot ──────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        if self._snapshot_cache is not None and self._snapshot_cache[0] == self.version:
            out = dict(self._snapshot_cache[1])
            out["cached"] = True
            return out
        payload = {
            "symbol": self.symbol,
            "version": self.version,
            "tick_size": self.tick_size,
            "pressure": self.pressure(),
            "absorption": self.absorption(),
            "depth_changes": self.depth_changes(),
            "tape_quality": self.tape_quality(),
            "pulled_size": [p.to_dict() for p in list(self.pulled)[-12:]],
            "trapped": [t.to_dict() for t in list(self.traps)[-6:]],
            "pressure_events": list(self.pressure_events)[-10:],
            "best": dict(self._best),
            "verdict": self.verdict(),
            "stats": self.stats(),
        }
        self._snapshot_cache = (self.version, payload)
        out = dict(payload)
        out["cached"] = False
        return out

    def stats(self) -> dict[str, Any]:
        return {
            "levels_tracked": len(self._prev_levels),
            "book_age_ms": max(0, int(time.time() * 1000) - self._last_book_ms) if self._last_book_ms else -1,
            "observations": self._observations,
            "pulled_recorded": len(self.pulled),
            "traps_recorded": len(self.traps),
            "pressure_events": len(self.pressure_events),
            "seconds_tracked": len(self._sec),
            "tape_prints": int(sum(self._tape.values())),
            "training_done": self.training_done(),
        }

    def clear(self) -> None:
        self._sec.clear()
        self._traded_at.clear()
        self._w_hist.clear()
        self._prev_levels.clear()
        self._watched.clear()
        self.pulled.clear()
        self.traps.clear()
        self.pressure_events.clear()
        self._tape = dict.fromkeys(self._tape, 0.0)
        self._tape_vol = dict.fromkeys(self._tape_vol, 0.0)
        self._depth_adds = {"bid": 0.0, "ask": 0.0}
        self._depth_removes = {"bid": 0.0, "ask": 0.0}
        self._max_weighted = {"bid": 0.0, "ask": 0.0}
        self._weighted = {"bid": 0.0, "ask": 0.0}
        self._started_ms = 0
        self.version += 1
        self._snapshot_cache = None
