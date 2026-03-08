"""
Exhaustion Detector
Detects declining volume/delta while price continues making new extremes.

From Fabio:
  "Decreasing volume — the aggression of market participants from the volume standpoint
   is getting lower and lower. And we have a contrarian imbalance at the top from the sellers.
   Price going up up up not being followed by the volume — this divergence."

  "The market is pushing really strong, printing another green candle, but the volume
   is getting lower and lower. This is a dry up in volume. Usually what you see is
   a sudden reversal in price."

Logic:
  Price making new extremes + DECLINING effort (volume & delta) = EXHAUSTION
  → EXIT signal or REVERSAL setup
"""

from __future__ import annotations

from typing import Optional

from orderflow_system.data.models import Candle, Signal, SignalType, Side
from orderflow_system.analytics.delta import DeltaEngine, DeltaResult
from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.config.settings import ExhaustionConfig


class ExhaustionDetector:
    """
    Detects exhaustion patterns — the current move is running out of steam.

    Checked on each new candle by analyzing recent history:
    1. Price trend: making new highs/lows over N bars
    2. Volume trend: declining volume over same bars
    3. Delta trend: declining delta (less conviction)
    4. Optional: contrarian imbalance at extreme
    """

    def __init__(self, config: ExhaustionConfig):
        self.config = config
        self._signal_history: list[Signal] = []

    def check_candle(
        self,
        candle: Candle,
        delta: DeltaResult,
        delta_engine: DeltaEngine,
        footprint: FootprintBar,
        recent_candles: list[Candle],
    ) -> Optional[Signal]:
        """Check for exhaustion after a completed candle."""
        n = self.config.min_bars_declining
        if len(recent_candles) < n + 1:
            return None

        lookback = recent_candles[-(n + 1):]

        # ── Check for BULLISH exhaustion (price up, volume/delta declining) ──
        bull_exhaustion = self._check_bullish_exhaustion(
            lookback, candle, delta, delta_engine, footprint
        )
        if bull_exhaustion:
            return bull_exhaustion

        # ── Check for BEARISH exhaustion (price down, volume/delta declining) ──
        return self._check_bearish_exhaustion(
            lookback, candle, delta, delta_engine, footprint
        )

    def _check_bullish_exhaustion(
        self,
        candles: list[Candle],
        current: Candle,
        delta: DeltaResult,
        delta_engine: DeltaEngine,
        footprint: FootprintBar,
    ) -> Optional[Signal]:
        """
        Price making new highs but volume and delta are declining.
        → Buyers exhausted → potential reversal downward.
        """
        n = self.config.min_bars_declining

        # Price must be making higher highs
        highs = [c.high for c in candles]
        price_trending_up = all(
            highs[i] >= highs[i - 1] for i in range(1, len(highs))
        )
        if not price_trending_up:
            # Relaxed check: at least recent high is higher than N bars ago
            if highs[-1] <= highs[0]:
                return None

        # Volume must be declining
        volumes = [c.volume for c in candles]
        vol_declining = self._is_declining(volumes, self.config.volume_decline_pct)
        if not vol_declining:
            return None

        # Delta trend should also be declining (less buying conviction)
        vol_trend = delta_engine.get_volume_trend(lookback=n)
        delta_roc = delta_engine.get_delta_roc(lookback=n)

        if vol_trend >= 0 and delta_roc >= 0:
            return None  # Both must show some weakness

        # Optional: contrarian imbalance at extreme (sellers at the top)
        contrarian_bonus = 0
        if self.config.requires_contrarian_imbalance and footprint.levels:
            imbalances = footprint.imbalance_levels(threshold=2.5)
            sell_imbalances_at_high = sum(
                1 for price, d in imbalances
                if d == "sell" and price >= current.high - current.range_size * 0.3
            )
            if sell_imbalances_at_high > 0:
                contrarian_bonus = 20
            elif self.config.requires_contrarian_imbalance:
                return None  # Required but not found

        strength = min(100.0, (
            40                          # Base: volume declining while price up
            + abs(vol_trend) * 5        # Volume slope strength
            + abs(delta_roc) * 5        # Delta weakening strength
            + contrarian_bonus          # Contrarian imbalance bonus
        ))

        signal = Signal(
            timestamp_ms=current.timestamp_ms,
            signal_type=SignalType.EXHAUSTION,
            direction=Side.SELL,   # Exhausted buyers → bearish reversal
            price_level=current.high,
            strength=strength,
            details={
                "type": "bullish_exhaustion",
                "declining_bars": n,
                "volume_slope": round(vol_trend, 2),
                "delta_roc": round(delta_roc, 2),
                "has_contrarian_imbalance": contrarian_bonus > 0,
                "high_at_exhaustion": current.high,
            },
        )
        self._signal_history.append(signal)
        return signal

    def _check_bearish_exhaustion(
        self,
        candles: list[Candle],
        current: Candle,
        delta: DeltaResult,
        delta_engine: DeltaEngine,
        footprint: FootprintBar,
    ) -> Optional[Signal]:
        """
        Price making new lows but volume and delta declining.
        → Sellers exhausted → potential reversal upward.
        """
        n = self.config.min_bars_declining

        lows = [c.low for c in candles]
        price_trending_down = all(
            lows[i] <= lows[i - 1] for i in range(1, len(lows))
        )
        if not price_trending_down:
            if lows[-1] >= lows[0]:
                return None

        volumes = [c.volume for c in candles]
        vol_declining = self._is_declining(volumes, self.config.volume_decline_pct)
        if not vol_declining:
            return None

        vol_trend = delta_engine.get_volume_trend(lookback=n)
        delta_roc = delta_engine.get_delta_roc(lookback=n)

        if vol_trend >= 0 and delta_roc <= 0:
            return None

        contrarian_bonus = 0
        if self.config.requires_contrarian_imbalance and footprint.levels:
            imbalances = footprint.imbalance_levels(threshold=2.5)
            buy_imbalances_at_low = sum(
                1 for price, d in imbalances
                if d == "buy" and price <= current.low + current.range_size * 0.3
            )
            if buy_imbalances_at_low > 0:
                contrarian_bonus = 20
            elif self.config.requires_contrarian_imbalance:
                return None

        strength = min(100.0, (
            40 + abs(vol_trend) * 5 + abs(delta_roc) * 5 + contrarian_bonus
        ))

        signal = Signal(
            timestamp_ms=current.timestamp_ms,
            signal_type=SignalType.EXHAUSTION,
            direction=Side.BUY,   # Exhausted sellers → bullish reversal
            price_level=current.low,
            strength=strength,
            details={
                "type": "bearish_exhaustion",
                "declining_bars": n,
                "volume_slope": round(vol_trend, 2),
                "delta_roc": round(delta_roc, 2),
                "has_contrarian_imbalance": contrarian_bonus > 0,
                "low_at_exhaustion": current.low,
            },
        )
        self._signal_history.append(signal)
        return signal

    @staticmethod
    def _is_declining(values: list[float], min_decline_pct: float) -> bool:
        """Check if a series shows consistent decline."""
        if len(values) < 2:
            return False
        if values[0] == 0:
            return False
        # Overall decline from first to last
        overall_decline = (values[0] - values[-1]) / values[0]
        if overall_decline < min_decline_pct:
            return False
        # Check mostly declining (allow 1 up-tick)
        declining_count = sum(
            1 for i in range(1, len(values)) if values[i] < values[i - 1]
        )
        return declining_count >= len(values) // 2
