"""
Orderbook Tracker
Maintains real-time L2 orderbook state and detects structural features:
  - Thin levels (low liquidity → sweep risk)
  - Book imbalance (bid vs ask depth)
  - Path of least resistance
  - Levels being consumed (for sweep detection)
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from orderflow_system.data.models import OrderbookSnapshot, OrderbookLevel


@dataclass
class LevelConsumption:
    """Tracks consumption of orderbook levels for sweep detection."""
    timestamp_ms: int
    price: float
    side: str          # 'bid' or 'ask'
    prev_quantity: float
    consumed_quantity: float


@dataclass
class BookState:
    """Analyzed state of the orderbook at a point in time."""
    timestamp_ms: int = 0
    imbalance_ratio: float = 0.0      # +1 = all bids, -1 = all asks
    bid_depth_5: float = 0.0          # Total qty in top 5 bid levels
    ask_depth_5: float = 0.0          # Total qty in top 5 ask levels
    bid_depth_10: float = 0.0
    ask_depth_10: float = 0.0
    thin_bids: list[float] = field(default_factory=list)   # Thin bid prices
    thin_asks: list[float] = field(default_factory=list)   # Thin ask prices
    path_of_least_resistance: str = "neutral"  # 'up', 'down', 'neutral'
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0


class OrderbookTracker:
    """
    Tracks orderbook state changes for sweep and liquidity analysis.

    From Fabio's teaching:
      - "Path of least resistance": the side with less passive liquidity is
        easier for aggressive orders to pierce through
      - Thin levels → potential for book sweeps
      - Tracking level consumption reveals how aggressive orders eat the book
    """

    def __init__(self, thin_threshold: float = 10.0, max_consumption_history: int = 200):
        self.thin_threshold = thin_threshold
        self._prev_snapshot: Optional[OrderbookSnapshot] = None
        self._consumption_history: deque[LevelConsumption] = deque(
            maxlen=max_consumption_history
        )
        self._book_state_history: list[BookState] = []
        self._max_history = 200

    @property
    def latest_snapshot(self) -> Optional[OrderbookSnapshot]:
        """Return the most recent orderbook snapshot."""
        return self._prev_snapshot

    def update(self, snapshot: OrderbookSnapshot) -> BookState:
        """Process a new orderbook snapshot and return analyzed state."""
        # Detect consumed levels if we have a previous snapshot
        if self._prev_snapshot is not None:
            self._detect_consumptions(self._prev_snapshot, snapshot)

        state = self._analyze(snapshot)

        self._prev_snapshot = snapshot
        self._book_state_history.append(state)
        if len(self._book_state_history) > self._max_history:
            self._book_state_history = self._book_state_history[-self._max_history:]

        return state

    def _analyze(self, snap: OrderbookSnapshot) -> BookState:
        """Analyze current orderbook structure."""
        bid_5 = snap.bid_depth(5)
        ask_5 = snap.ask_depth(5)
        bid_10 = snap.bid_depth(10)
        ask_10 = snap.ask_depth(10)

        # Thin level detection
        thin_bids = [
            b.price for b in snap.bids[:20]
            if b.quantity < self.thin_threshold
        ]
        thin_asks = [
            a.price for a in snap.asks[:20]
            if a.quantity < self.thin_threshold
        ]

        # Path of least resistance
        total = bid_10 + ask_10
        if total > 0:
            ratio = (bid_10 - ask_10) / total
        else:
            ratio = 0.0

        if ratio > 0.15:
            polr = "up"      # More bids than asks → harder to go down → easier up
        elif ratio < -0.15:
            polr = "down"    # More asks → easier down
        else:
            polr = "neutral"

        return BookState(
            timestamp_ms=snap.timestamp_ms,
            imbalance_ratio=snap.imbalance_ratio(5),
            bid_depth_5=bid_5,
            ask_depth_5=ask_5,
            bid_depth_10=bid_10,
            ask_depth_10=ask_10,
            thin_bids=thin_bids,
            thin_asks=thin_asks,
            path_of_least_resistance=polr,
            best_bid=snap.best_bid or 0.0,
            best_ask=snap.best_ask or 0.0,
            spread=snap.spread or 0.0,
        )

    def _detect_consumptions(
        self, prev: OrderbookSnapshot, curr: OrderbookSnapshot
    ):
        """
        Detect which book levels were consumed between snapshots.
        If a bid/ask level existed before and now has less or zero quantity,
        it was consumed by aggressive orders.
        """
        ts = curr.timestamp_ms

        # Check consumed asks (eaten by aggressive buyers going UP)
        prev_asks = {a.price: a.quantity for a in prev.asks[:30]}
        curr_asks = {a.price: a.quantity for a in curr.asks[:30]}

        for price, prev_qty in prev_asks.items():
            curr_qty = curr_asks.get(price, 0.0)
            consumed = prev_qty - curr_qty
            if consumed > prev_qty * 0.5 and consumed > 1.0:
                self._consumption_history.append(LevelConsumption(
                    timestamp_ms=ts,
                    price=price,
                    side="ask",
                    prev_quantity=prev_qty,
                    consumed_quantity=consumed,
                ))

        # Check consumed bids (eaten by aggressive sellers going DOWN)
        prev_bids = {b.price: b.quantity for b in prev.bids[:30]}
        curr_bids = {b.price: b.quantity for b in curr.bids[:30]}

        for price, prev_qty in prev_bids.items():
            curr_qty = curr_bids.get(price, 0.0)
            consumed = prev_qty - curr_qty
            if consumed > prev_qty * 0.5 and consumed > 1.0:
                self._consumption_history.append(LevelConsumption(
                    timestamp_ms=ts,
                    price=price,
                    side="bid",
                    prev_quantity=prev_qty,
                    consumed_quantity=consumed,
                ))

    def get_recent_consumptions(
        self, time_window_ms: int = 5000, side: Optional[str] = None
    ) -> list[LevelConsumption]:
        """
        Get recent level consumptions within a time window.
        Used by sweep detector to count how many levels were eaten recently.
        """
        now = int(time.time() * 1000)
        cutoff = now - time_window_ms
        result = [
            c for c in self._consumption_history
            if c.timestamp_ms >= cutoff
        ]
        if side:
            result = [c for c in result if c.side == side]
        return result

    def count_swept_levels(
        self, time_window_ms: int = 3000, side: Optional[str] = None
    ) -> int:
        """Count distinct price levels consumed within time window."""
        consumptions = self.get_recent_consumptions(time_window_ms, side)
        return len(set(c.price for c in consumptions))

    def total_consumed_volume(
        self, time_window_ms: int = 3000, side: Optional[str] = None
    ) -> float:
        """Total volume consumed from the book within time window."""
        consumptions = self.get_recent_consumptions(time_window_ms, side)
        return sum(c.consumed_quantity for c in consumptions)

    @property
    def latest_state(self) -> Optional[BookState]:
        return self._book_state_history[-1] if self._book_state_history else None
