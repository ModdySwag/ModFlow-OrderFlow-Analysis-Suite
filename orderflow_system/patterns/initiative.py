"""
Initiative Auction Detector
Detects aggressive momentum with follow-through — effort + result aligned.

From Fabio:
  "Strong delta and a candle that closes on the upside — delta is leading the price.
   This is the best example of aggressive momentum — initiative auction."

  "Constant aggression of the buyer, consistent pressure on the upside,
   one-side imbalance prints... you can use as a really strong point to join
   the trend when it's developing and you have a strong delta."

Logic:
  HIGH effort + HIGH result + directional alignment = INITIATIVE AUCTION
  - Strong delta in one direction
  - Candle closes in same direction as delta
  - Volume above average (acceleration)
  - One-sided imbalance prints in the footprint
"""

from __future__ import annotations

from typing import Optional

from orderflow_system.data.models import Candle, Signal, SignalType, Side
from orderflow_system.analytics.delta import DeltaResult, DeltaEngine
from orderflow_system.analytics.footprint import FootprintBar, FootprintEngine
from orderflow_system.config.settings import InitiativeConfig


class InitiativeDetector:
    """
    Detects initiative auction patterns.

    Used for:
    1. Break-even trigger (first initiative after absorption → move SL to BE)
    2. Trailing trigger (each new initiative print → trail SL)
    3. Trend joining signal (strong initiative = join the move)
    """

    def __init__(self, config: InitiativeConfig, tick_size: float = 0.1):
        self.config = config
        self.tick_size = tick_size
        self._avg_volume_window: list[float] = []
        self._max_window = 50
        self._signal_history: list[Signal] = []

    def check_candle(
        self,
        candle: Candle,
        delta: DeltaResult,
        footprint: FootprintBar,
    ) -> Optional[Signal]:
        """Check a completed candle for initiative auction pattern."""
        if candle.volume == 0:
            return None

        # Track rolling average volume
        self._avg_volume_window.append(candle.volume)
        if len(self._avg_volume_window) > self._max_window:
            self._avg_volume_window = self._avg_volume_window[-self._max_window:]

        avg_vol = (
            sum(self._avg_volume_window) / len(self._avg_volume_window)
            if self._avg_volume_window
            else candle.volume
        )

        # ── Check criteria ──

        # 1. Strong delta exceeding threshold
        abs_delta = abs(delta.vertical_delta)
        if abs_delta < self.config.min_delta_threshold:
            return None

        # 2. Volume acceleration (above average)
        vol_accel = candle.volume / avg_vol if avg_vol > 0 else 1.0
        if vol_accel < self.config.volume_acceleration_min:
            return None

        # 3. Price displacement (candle body must be meaningful)
        tick_size = self.tick_size  # Use instrument tick size
        price_displacement = candle.body_size / max(tick_size, 0.01)
        if price_displacement < self.config.min_price_displacement_ticks:
            return None

        # 4. Delta and price must be directionally aligned
        delta_bullish = delta.vertical_delta > 0
        candle_bullish = candle.is_green

        if self.config.delta_price_alignment and delta_bullish != candle_bullish:
            return None

        # ── Direction and signal ──
        direction = Side.BUY if delta_bullish else Side.SELL

        # 5. Check for one-sided imbalance prints (bonus strength)
        imbalance_count = 0
        if footprint.levels:
            imbalances = footprint.imbalance_levels(threshold=3.0)
            dir_str = "buy" if delta_bullish else "sell"
            imbalance_count = sum(1 for _, d in imbalances if d == dir_str)

        # Compute strength score
        strength = min(100.0, (
            (abs_delta / self.config.min_delta_threshold) * 20  # Delta strength
            + vol_accel * 15                                     # Volume acceleration
            + price_displacement * 5                             # Price follow-through
            + imbalance_count * 10                               # Imbalance bonus
        ))

        signal = Signal(
            timestamp_ms=candle.timestamp_ms,
            signal_type=SignalType.INITIATIVE,
            direction=direction,
            price_level=candle.close,
            strength=strength,
            details={
                "delta": delta.vertical_delta,
                "volume": candle.volume,
                "avg_volume": round(avg_vol, 1),
                "vol_acceleration": round(vol_accel, 2),
                "body_ticks": round(price_displacement, 1),
                "imbalance_levels": imbalance_count,
                "candle_close": "green" if candle.is_green else "red",
            },
        )
        self._signal_history.append(signal)
        return signal

    @property
    def signal_history(self) -> list[Signal]:
        return self._signal_history
