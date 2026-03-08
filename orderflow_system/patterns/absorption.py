"""
Absorption Detector
Detects when aggressive orders are absorbed by passive liquidity — no price movement.

From Fabio:
  "High effort from the buyers that received zero reward. This is the textbook
   example for absorption — positive delta but negative closure."

  "72 + 61 + 60 + 62 = ~300 contracts on this horizontal level... all this effort
   is being absorbed. This is a perfect example of absorption."

Logic:
  Effort (aggressive volume at a level)  vs  Result (price displacement)
  HIGH effort + LOW result = ABSORPTION → Entry signal

  Also detects repeated absorption: multiple attempts at the same level
  (e.g., 105 contracts, then 101 contracts, all absorbed at same price).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from orderflow_system.data.models import (
    Tick, Candle, Signal, SignalType, Side, FootprintLevel,
)
from orderflow_system.analytics.footprint import FootprintBar, FootprintEngine
from orderflow_system.analytics.delta import DeltaResult
from orderflow_system.config.settings import AbsorptionConfig


@dataclass
class AbsorptionEvent:
    """Tracks absorption building at a price level."""
    price: float
    aggressive_volume: float = 0.0
    price_displacement: float = 0.0
    attempts: int = 0
    absorbing_side: str = ""     # 'buyers_absorbing' or 'sellers_absorbing'
    first_seen_ms: int = 0
    last_seen_ms: int = 0


class AbsorptionDetector:
    """
    Detects absorption patterns in real-time.

    Two detection methods:
    1. Per-candle: High aggressive volume at a level but candle closes in opposite direction
       (positive delta + negative close = buyers absorbed = bearish absorption)
    2. Rolling-window: Aggressive volume accumulates at a price level with no displacement

    Multiple attempts at the same level increase confidence.
    """

    def __init__(self, config: AbsorptionConfig, tick_size: float = 0.1):
        self.config = config
        self.tick_size = tick_size
        self._active_absorptions: dict[float, AbsorptionEvent] = {}
        self._signal_history: list[Signal] = []
        self._cleanup_interval_ms = 60_000  # Clean stale events every minute

    def check_candle(
        self,
        candle: Candle,
        footprint: FootprintBar,
        delta: DeltaResult,
        current_price: float,
    ) -> Optional[Signal]:
        """
        Check a completed candle for absorption.

        Absorption candle signatures:
        - HIGH delta in one direction but candle closes in OPPOSITE direction
          → Positive delta (buy pressure) + red candle = sellers absorbing the buys
          → Negative delta (sell pressure) + green candle = buyers absorbing the sells
        - High volume at a specific level with no price movement through it
        """
        if candle.volume == 0:
            return None

        # ── Method 1: Delta vs Close Mismatch ──
        signal = self._check_delta_close_mismatch(candle, delta, footprint)
        if signal:
            return signal

        # ── Method 2: Level-based absorption ──
        return self._check_level_absorption(candle, footprint, current_price)

    def _check_delta_close_mismatch(
        self,
        candle: Candle,
        delta: DeltaResult,
        footprint: FootprintBar,
    ) -> Optional[Signal]:
        """
        Fabio's textbook absorption:
        "Positive delta but negative closure" = aggressive buyers absorbed by passive sellers.
        The opposite direction wins.
        """
        abs_delta = abs(delta.vertical_delta)
        if abs_delta < self.config.min_aggressive_volume:
            return None

        # Positive delta (buy pressure) but bearish candle close
        if delta.vertical_delta > 0 and not candle.is_green:
            # Buyers were absorbed → bearish signal
            strength = min(100.0, (abs_delta / self.config.min_aggressive_volume) * 40)
            return self._create_signal(
                candle=candle,
                direction=Side.SELL,
                price_level=candle.high,  # Absorption happened at the high
                strength=strength,
                details={
                    "type": "delta_close_mismatch",
                    "delta": delta.vertical_delta,
                    "candle_close": "bearish",
                    "aggressive_buy_vol": delta.buy_volume,
                    "aggressive_sell_vol": delta.sell_volume,
                },
            )

        # Negative delta (sell pressure) but bullish candle close
        if delta.vertical_delta < 0 and candle.is_green:
            # Sellers were absorbed → bullish signal
            strength = min(100.0, (abs_delta / self.config.min_aggressive_volume) * 40)
            return self._create_signal(
                candle=candle,
                direction=Side.BUY,
                price_level=candle.low,  # Absorption happened at the low
                strength=strength,
                details={
                    "type": "delta_close_mismatch",
                    "delta": delta.vertical_delta,
                    "candle_close": "bullish",
                    "aggressive_buy_vol": delta.buy_volume,
                    "aggressive_sell_vol": delta.sell_volume,
                },
            )

        return None

    def _check_level_absorption(
        self,
        candle: Candle,
        footprint: FootprintBar,
        current_price: float,
    ) -> Optional[Signal]:
        """
        Check for absorption at specific price levels within the footprint.
        High volume at a level + price didn't break through = absorption.
        """
        if not footprint.levels:
            return None

        now_ms = int(time.time() * 1000)
        tick_size = self.tick_size

        for price, lv in footprint.levels.items():
            total = lv.total_volume
            if total < self.config.big_trade_filter:
                continue

            # Check: high volume at this level but price displaced little
            price_disp = abs(current_price - price) / max(tick_size, 0.01)
            effort_high = total >= self.config.min_aggressive_volume
            result_low = price_disp <= self.config.max_price_displacement_ticks

            if effort_high and result_low:
                # Track repeated absorption
                rounded = round(price, 4)
                if rounded not in self._active_absorptions:
                    self._active_absorptions[rounded] = AbsorptionEvent(
                        price=rounded,
                        first_seen_ms=now_ms,
                    )

                event = self._active_absorptions[rounded]
                event.aggressive_volume += total
                event.price_displacement = price_disp
                event.attempts += 1
                event.last_seen_ms = now_ms

                # Determine who is absorbing
                if lv.ask_volume > lv.bid_volume:
                    event.absorbing_side = "sellers_absorbing"
                    direction = Side.SELL
                else:
                    event.absorbing_side = "buyers_absorbing"
                    direction = Side.BUY

                # Signal threshold: enough volume or repeated attempts
                if (
                    event.aggressive_volume >= self.config.min_aggressive_volume
                    and event.attempts >= self.config.min_attempts
                ):
                    strength = min(
                        100.0,
                        (event.aggressive_volume / self.config.min_aggressive_volume) * 30
                        + event.attempts * 15,
                    )
                    signal = self._create_signal(
                        candle=candle,
                        direction=direction,
                        price_level=price,
                        strength=strength,
                        details={
                            "type": "level_absorption",
                            "total_aggressive_volume": event.aggressive_volume,
                            "attempts": event.attempts,
                            "absorbing_side": event.absorbing_side,
                            "duration_ms": now_ms - event.first_seen_ms,
                        },
                    )
                    # Reset after signal
                    del self._active_absorptions[rounded]
                    return signal

        # Cleanup stale events
        self._cleanup_stale(now_ms)
        return None

    def _cleanup_stale(self, now_ms: int):
        """Remove absorption events that are too old."""
        stale_threshold = now_ms - (self.config.rolling_window_seconds * 3 * 1000)
        stale_keys = [
            k for k, v in self._active_absorptions.items()
            if v.last_seen_ms < stale_threshold
        ]
        for k in stale_keys:
            del self._active_absorptions[k]

    def _create_signal(
        self,
        candle: Candle,
        direction: Side,
        price_level: float,
        strength: float,
        details: dict,
    ) -> Signal:
        signal = Signal(
            timestamp_ms=candle.timestamp_ms,
            signal_type=SignalType.ABSORPTION,
            direction=direction,
            price_level=price_level,
            strength=strength,
            details=details,
        )
        self._signal_history.append(signal)
        return signal

    @property
    def active_absorptions(self) -> dict[float, AbsorptionEvent]:
        return self._active_absorptions
