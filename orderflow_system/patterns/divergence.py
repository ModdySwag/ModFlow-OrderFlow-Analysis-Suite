"""
Delta Divergence Detector
Detects when price makes new extremes but cumulative delta fails to confirm.

From Fabio:
  Delta divergence is a WARNING signal — it weakens conviction in the current trend.
  "Price makes new high AND cumulative_delta < previous_delta_high → bearish divergence"

Logic:
  Bearish divergence: Price new high + cumulative delta lower high
  Bullish divergence: Price new low + cumulative delta higher low
  → REVERSAL warning or filter to reduce confidence in current direction
"""

from __future__ import annotations

from typing import Optional

from orderflow_system.data.models import Candle, Signal, SignalType, Side
from orderflow_system.analytics.delta import DeltaEngine
from orderflow_system.config.settings import DivergenceConfig


class DivergenceDetector:
    """
    Detects bearish and bullish delta divergences.

    Compares price peaks/troughs with cumulative delta peaks/troughs.
    If they disagree, the move is weakening.
    """

    def __init__(self, config: DivergenceConfig):
        self.config = config
        self._price_history: list[tuple[int, float, float]] = []
        # (timestamp_ms, high, low)
        self._signal_history: list[Signal] = []
        self._max_history = 100

    def check_candle(
        self,
        candle: Candle,
        delta_engine: DeltaEngine,
    ) -> Optional[Signal]:
        """Check for delta divergence after a completed candle."""
        self._price_history.append((candle.timestamp_ms, candle.high, candle.low))
        if len(self._price_history) > self._max_history:
            self._price_history = self._price_history[-self._max_history:]

        lookback = self.config.lookback_bars
        if len(self._price_history) < lookback:
            return None

        # Get delta peaks and troughs
        peaks, troughs = delta_engine.detect_delta_peaks(lookback=lookback)

        # ── Bearish divergence: price higher high, delta lower high ──
        bear_signal = self._check_bearish_divergence(candle, peaks)
        if bear_signal:
            return bear_signal

        # ── Bullish divergence: price lower low, delta higher low ──
        return self._check_bullish_divergence(candle, troughs)

    def _check_bearish_divergence(
        self, candle: Candle, delta_peaks: list[tuple[int, float]]
    ) -> Optional[Signal]:
        """Price new high but delta peak is lower than previous."""
        if len(delta_peaks) < 2:
            return None

        recent_prices = self._price_history[-self.config.lookback_bars:]
        prev_highs = [h for _, h, _ in recent_prices[:-1]]
        if not prev_highs:
            return None

        max_prev_high = max(prev_highs)
        tick = self.config.min_price_new_extreme_ticks * 0.1  # Approx tick

        # Price must make new high
        if candle.high < max_prev_high + tick:
            return None

        # Delta peak must be lower than previous peak
        latest_delta_peak = delta_peaks[-1][1]
        prev_delta_peak = delta_peaks[-2][1]

        if latest_delta_peak >= prev_delta_peak * self.config.delta_failure_pct:
            return None  # Delta confirmed the move — no divergence

        strength = min(100.0, (
            30  # Base divergence
            + (1 - latest_delta_peak / max(prev_delta_peak, 0.01)) * 40
            + (candle.high - max_prev_high) / max(tick, 0.01) * 10
        ))

        signal = Signal(
            timestamp_ms=candle.timestamp_ms,
            signal_type=SignalType.DIVERGENCE,
            direction=Side.SELL,   # Bearish divergence → weakening buyers
            price_level=candle.high,
            strength=strength,
            details={
                "type": "bearish_divergence",
                "price_high": candle.high,
                "prev_price_high": max_prev_high,
                "delta_peak": round(latest_delta_peak, 2),
                "prev_delta_peak": round(prev_delta_peak, 2),
            },
        )
        self._signal_history.append(signal)
        return signal

    def _check_bullish_divergence(
        self, candle: Candle, delta_troughs: list[tuple[int, float]]
    ) -> Optional[Signal]:
        """Price new low but delta trough is higher than previous."""
        if len(delta_troughs) < 2:
            return None

        recent_prices = self._price_history[-self.config.lookback_bars:]
        prev_lows = [l for _, _, l in recent_prices[:-1]]
        if not prev_lows:
            return None

        min_prev_low = min(prev_lows)
        tick = self.config.min_price_new_extreme_ticks * 0.1

        if candle.low > min_prev_low - tick:
            return None

        latest_delta_trough = delta_troughs[-1][1]
        prev_delta_trough = delta_troughs[-2][1]

        # Trough should be HIGHER (less negative) than previous — divergence
        if latest_delta_trough <= prev_delta_trough * self.config.delta_failure_pct:
            return None

        strength = min(100.0, (
            30
            + (1 - abs(latest_delta_trough) / max(abs(prev_delta_trough), 0.01)) * 40
            + (min_prev_low - candle.low) / max(tick, 0.01) * 10
        ))

        signal = Signal(
            timestamp_ms=candle.timestamp_ms,
            signal_type=SignalType.DIVERGENCE,
            direction=Side.BUY,   # Bullish divergence → weakening sellers
            price_level=candle.low,
            strength=strength,
            details={
                "type": "bullish_divergence",
                "price_low": candle.low,
                "prev_price_low": min_prev_low,
                "delta_trough": round(latest_delta_trough, 2),
                "prev_delta_trough": round(prev_delta_trough, 2),
            },
        )
        self._signal_history.append(signal)
        return signal
