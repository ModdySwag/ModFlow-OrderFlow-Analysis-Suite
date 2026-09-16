"""Trade detector — executions that actually eat resting liquidity.

the reference platform's *Order Flow Trade Detector* marks trades that execute against real
depth rather than against the touch. On a venue with no order identities (Bybit L2),
the honest version of that idea is: compare every print with the size that was resting
at that price a moment earlier, and flag the prints that consumed a large share of it.

Two things come out of that comparison:

* **execution into depth** — a print that took a meaningful share of the resting size
  at its price (someone ate a wall, rather than picking off the inside), and
* **refill** — the level restores itself within a few seconds without price leaving,
  which is as close to "hidden size" as a public feed can honestly get.

Label: the refill read is an *inference from behaviour*. The venue publishes no order
identities, so the UI says "refill", never "iceberg".
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from orderflow_system.atlas.clock import as_epoch_ms
from orderflow_system.data.models import OrderbookSnapshot, Tick
from orderflow_system.data.enums import as_value

LEVELS_TRACKED = 40            # prices kept per side around the touch
PRINT_HISTORY = 400            # recent print sizes for the adaptive floor


def _side(tick: Tick) -> str:
    return as_value(tick.side)


def _price_size(level: Any) -> tuple[Optional[float], Optional[float]]:
    """Read (price, size) from a book level — dataclass, named tuple or plain pair.

    Note the shape of this: ``getattr(level, "quantity", level[1])`` looks equivalent
    and is not — the default is evaluated *before* the attribute lookup, so the index
    raises on every object-shaped level and the whole book silently reads as empty.
    """
    price = getattr(level, "price", None)
    size = getattr(level, "quantity", None)
    if size is None:
        size = getattr(level, "size", None)
    if price is None or size is None:
        try:
            price, size = level[0], level[1]          # type: ignore[index]
        except Exception:
            return None, None
    try:
        return float(price), float(size)
    except (TypeError, ValueError):
        return None, None


@dataclass
class DepthExecution:
    """A print that consumed a large share of the resting size at its price."""

    ts_ms: int
    price: float
    size: float
    side: str
    resting: float
    share: float               # size / (size + resting) → 1.0 means nothing was there
    refilled: bool = False
    refill_ms: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts_ms": self.ts_ms, "price": self.price, "size": round(self.size, 6),
            "side": self.side, "resting": round(self.resting, 6),
            "share": round(self.share, 3), "refilled": self.refilled,
            "refill_ms": self.refill_ms, "note": self.note,
        }


@dataclass
class _Pending:
    price: float
    pre_size: float
    eaten: float
    started_ms: int
    event: DepthExecution = field(repr=False, default=None)  # type: ignore[assignment]


class TradeDetector:
    """Executions into resting depth, plus refills of the levels they ate."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        min_share: float = 0.25,        # must consume ≥25% of what was resting
        size_mult: float = 4.0,         # and the print must be ≥4× the median print
        resting_mult: float = 8.0,      # and what was resting must be ≥8× the median print
        size_floor: float = 0.0,
        refill_pct: float = 0.7,        # level back to ≥70% of its pre-print size
        refill_ms: int = 4_000,
        max_events: int = 60,
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.min_share = max(0.0, min(1.0, float(min_share)))
        self.size_mult = max(1.0, float(size_mult))
        self.resting_mult = max(1.0, float(resting_mult))
        self.size_floor = max(0.0, float(size_floor))
        self.refill_pct = max(0.1, min(1.0, float(refill_pct)))
        self.refill_ms = int(max(200, refill_ms))

        self._resting: dict[float, float] = {}       # price -> size resting
        self._prints: deque[float] = deque(maxlen=PRINT_HISTORY)
        self._pending: dict[float, _Pending] = {}
        self.executions: deque[DepthExecution] = deque(maxlen=max_events)
        self.refills: deque[DepthExecution] = deque(maxlen=max_events)
        self.executions_seen = 0
        self.refills_seen = 0
        self._median_cache = 0.0
        self._since_median = 0
        self._last_book_ms = 0
        #: the newest clock this detector has seen from EITHER feed — the fallback for a stamp
        #: that is not a clock (the book's update id), so a duration never goes backwards
        self._last_event_ms = 0
        self.version = 0

    # ── booking ───────────────────────────────────────────────────
    def on_orderbook(self, snapshot: OrderbookSnapshot, ts_ms: Optional[int] = None) -> dict[str, Any]:
        """Refresh the resting-size map and look for refills of eaten levels."""
        ts = as_epoch_ms(ts_ms or snapshot.timestamp_ms, fallback_ms=self._last_event_ms or None)
        self.version += 1
        self._last_book_ms = ts
        self._last_event_ms = max(self._last_event_ms, ts)
        fresh: dict[float, float] = {}
        for rows in (snapshot.bids[:LEVELS_TRACKED], snapshot.asks[:LEVELS_TRACKED]):
            for level in rows:
                price, size = _price_size(level)
                if price is None or size is None or size <= 0:
                    continue
                fresh[price] = size

        out: dict[str, Any] = {}
        for price, pend in list(self._pending.items()):
            now = fresh.get(price)
            if now is None:
                if ts - pend.started_ms > self.refill_ms:
                    self._pending.pop(price, None)
                continue
            if now >= pend.pre_size * self.refill_pct:
                ev = pend.event
                if ev is not None:
                    ev.refilled = True
                    ev.refill_ms = ts - pend.started_ms
                    ev.note = ("the level refilled after being eaten — read as refreshed "
                               "liquidity, an inference not an order id")
                    self.refills.append(ev)
                    self.refills_seen += 1
                    out.setdefault("depth_refill", []).append(ev.to_dict())
                self._pending.pop(price, None)
            elif ts - pend.started_ms > self.refill_ms:
                self._pending.pop(price, None)

        self._resting = fresh
        out.setdefault("depth_refill", [])
        return out

    def _median_print(self) -> float:
        if not self._prints:
            return 0.0
        if self._since_median >= 25 or self._median_cache <= 0:
            ordered = sorted(self._prints)
            self._median_cache = ordered[len(ordered) // 2]
            self._since_median = 0
        return self._median_cache

    def big_enough(self) -> float:
        med = self._median_print()
        return max(self.size_floor, med * self.size_mult if med > 0 else 0.0)

    # ── detection ─────────────────────────────────────────────────
    def on_tick(self, tick: Tick) -> dict[str, Any]:
        """Flag prints that ate resting depth at their price."""
        try:
            price = float(tick.price)
            size = abs(float(tick.size))
        except (TypeError, ValueError):
            return {}
        if price <= 0 or size <= 0:
            return {}
        ts = as_epoch_ms(tick.timestamp_ms, fallback_ms=self._last_event_ms or None)
        self.version += 1
        self._last_event_ms = max(self._last_event_ms, ts)
        self._prints.append(size)
        self._since_median += 1

        resting = self._resting.get(price, 0.0)
        if resting <= 0:
            return {}
        median = self._median_print()
        if median > 0 and resting < median * self.resting_mult:
            return {}          # the level itself must be large: eating a small order is ordinary
        share = size / (size + resting)
        if share < self.min_share or size < self.big_enough():
            return {}

        ev = DepthExecution(
            ts_ms=ts, price=price, size=size, side=_side(tick), resting=resting,
            share=round(share, 3),
            note=f"consumed {share * 100:.0f}% of the {resting:g} resting at {price:g}",
        )
        self.executions.append(ev)
        self.executions_seen += 1
        self._pending[price] = _Pending(price=price, pre_size=resting, eaten=size,
                                        started_ms=ts, event=ev)
        return {"depth_execution": [ev.to_dict()]}

    # ── output ────────────────────────────────────────────────────
    def snapshot(self, max_rows: int = 30) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "min_share": self.min_share,
            "size_mult": self.size_mult,
            "resting_mult": self.resting_mult,
            "threshold": round(self.big_enough(), 6),
            "executions": [e.to_dict() for e in list(self.executions)[-max_rows:]][::-1],
            "refills": [e.to_dict() for e in list(self.refills)[-max_rows:]][::-1],
            "version": self.version,
        }

    def stats(self) -> dict[str, Any]:
        return {
            "levels_tracked": len(self._resting),
            "executions": self.executions_seen,
            "refills": self.refills_seen,
            "threshold": round(self.big_enough(), 6),
        }

    def clear(self) -> None:
        self._resting.clear()
        self._prints.clear()
        self._pending.clear()
        self.executions.clear()
        self.refills.clear()
