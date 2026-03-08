"""
Book Sweep Detector
Detects when price moves rapidly through multiple price levels with low volume.

From Fabio:
  "Low effort and high result. A lot of executed orders on the bottom side of the
   candle and then the candle closes with an amazing reward... there is movement
   of the candle but an absence of participants. No sell limit players in all this area."

Logic:
  LOW effort + HIGH displacement = BOOK SWEEP
  - Multiple orderbook levels consumed rapidly
  - Low volume per level (vacuum / no resistance)
  - Price jumps through thin areas
"""

from __future__ import annotations

import time
from typing import Optional

from orderflow_system.data.models import Candle, Signal, SignalType, Side
from orderflow_system.analytics.orderbook import OrderbookTracker, BookState
from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.config.settings import SweepConfig


class SweepDetector:
    """
    Detects book sweeping by monitoring orderbook level consumption.

    Sweep = price moves through multiple thin levels quickly with little
    resistance. The market finds a vacuum and jets through it.
    """

    def __init__(self, config: SweepConfig):
        self.config = config
        self._signal_history: list[Signal] = []
        self._last_signal_ms: int = 0
        self._cooldown_ms: int = 5000  # Min 5s between sweep signals

    def check(
        self,
        orderbook_tracker: OrderbookTracker,
        candle: Candle,
        footprint: FootprintBar,
    ) -> Optional[Signal]:
        """
        Check for book sweep based on recent level consumptions.
        """
        now_ms = int(time.time() * 1000)
        if now_ms - self._last_signal_ms < self._cooldown_ms:
            return None

        # Check asks swept (bullish sweep — price going UP through thin asks)
        bull_signal = self._check_side(
            orderbook_tracker, candle, footprint, side="ask", direction=Side.BUY
        )
        if bull_signal:
            return bull_signal

        # Check bids swept (bearish sweep — price going DOWN through thin bids)
        bear_signal = self._check_side(
            orderbook_tracker, candle, footprint, side="bid", direction=Side.SELL
        )
        return bear_signal

    def _check_side(
        self,
        tracker: OrderbookTracker,
        candle: Candle,
        footprint: FootprintBar,
        side: str,
        direction: Side,
    ) -> Optional[Signal]:
        """Check sweep on one side of the book."""
        levels_swept = tracker.count_swept_levels(
            time_window_ms=int(self.config.max_time_ms), side=side
        )
        total_vol = tracker.total_consumed_volume(
            time_window_ms=int(self.config.max_time_ms), side=side
        )

        if levels_swept < self.config.min_levels_swept:
            return None

        # Compute efficiency: levels per unit of volume
        vol_per_level = total_vol / levels_swept if levels_swept > 0 else float("inf")

        # Low effort = low volume per level
        if vol_per_level > self.config.max_volume_per_level:
            return None

        # Also verify with footprint: check that the candle body is large
        # relative to volume (high displacement, low effort)
        if candle.volume > 0:
            displacement_per_vol = candle.range_size / candle.volume
        else:
            displacement_per_vol = 0

        # Compute strength
        efficiency = levels_swept / max(vol_per_level, 0.01)
        strength = min(100.0, (
            levels_swept * 15
            + efficiency * 20
            + displacement_per_vol * 1000
        ))

        # Check thin book confirmation from current state
        book_state = tracker.latest_state
        thin_confirm = False
        if book_state:
            if direction == Side.BUY and len(book_state.thin_asks) >= 2:
                thin_confirm = True
            elif direction == Side.SELL and len(book_state.thin_bids) >= 2:
                thin_confirm = True

        if thin_confirm:
            strength = min(100.0, strength + 15)

        if strength < 30:
            return None

        self._last_signal_ms = int(time.time() * 1000)

        signal = Signal(
            timestamp_ms=candle.timestamp_ms,
            signal_type=SignalType.SWEEP,
            direction=direction,
            price_level=candle.close,
            strength=strength,
            details={
                "levels_swept": levels_swept,
                "total_volume_consumed": round(total_vol, 1),
                "vol_per_level": round(vol_per_level, 2),
                "efficiency": round(efficiency, 2),
                "thin_book_confirmed": thin_confirm,
                "candle_range": round(candle.range_size, 4),
            },
        )
        self._signal_history.append(signal)
        return signal
