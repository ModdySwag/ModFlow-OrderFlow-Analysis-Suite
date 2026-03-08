"""
Delta Engine
Computes horizontal delta, vertical delta, cumulative delta, and delta rate of change.
Core component for detecting absorption, initiative, exhaustion, and divergence.
"""

from __future__ import annotations

import numpy as np
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from orderflow_system.data.models import Tick, Candle, Side


@dataclass
class DeltaResult:
    """Delta analysis for a single candle or time window."""
    vertical_delta: float = 0.0          # buy_vol - sell_vol for this bar
    cumulative_delta: float = 0.0        # Running total across bars
    horizontal_delta: dict[float, float] = field(default_factory=dict)
    # per-price: buy_vol - sell_vol
    max_delta_price: float = 0.0         # Price with strongest buy delta
    min_delta_price: float = 0.0         # Price with strongest sell delta
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta_pct: float = 0.0              # delta / total_volume


class DeltaEngine:
    """
    Computes delta metrics used throughout the strategy.

    Key concepts from Fabio:
      - Horizontal delta: buy_vol - sell_vol at EACH price level within a candle
      - Vertical delta: total aggressive buys - total aggressive sells per candle
      - Cumulative delta: running sum across candles, used for divergence detection
      - Delta divergence: price makes new high but cum_delta doesn't → weakening
    """

    def __init__(self, tick_size: float = 0.1):
        self.tick_size = tick_size
        self._cumulative_delta = 0.0
        self._delta_history: list[DeltaResult] = []
        self._max_history = 500

    def reset(self):
        self._cumulative_delta = 0.0
        self._delta_history.clear()

    def compute_from_candle(self, candle: Candle) -> DeltaResult:
        """Compute delta from a candle with footprint data."""
        buy_vol = candle.buy_volume
        sell_vol = candle.sell_volume
        vertical_delta = buy_vol - sell_vol

        self._cumulative_delta += vertical_delta

        # Horizontal delta from footprint
        h_delta: dict[float, float] = {}
        max_delta = float("-inf")
        min_delta = float("inf")
        max_delta_price = candle.close
        min_delta_price = candle.close

        if candle.footprint:
            for price, fp in candle.footprint.items():
                d = fp.ask_volume - fp.bid_volume
                h_delta[price] = d
                if d > max_delta:
                    max_delta = d
                    max_delta_price = price
                if d < min_delta:
                    min_delta = d
                    min_delta_price = price

        total = buy_vol + sell_vol
        result = DeltaResult(
            vertical_delta=vertical_delta,
            cumulative_delta=self._cumulative_delta,
            horizontal_delta=h_delta,
            max_delta_price=max_delta_price,
            min_delta_price=min_delta_price,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta_pct=vertical_delta / total if total > 0 else 0.0,
        )

        self._delta_history.append(result)
        if len(self._delta_history) > self._max_history:
            self._delta_history = self._delta_history[-self._max_history:]

        return result

    def compute_from_ticks(
        self, ticks: list[Tick], tick_size: Optional[float] = None
    ) -> DeltaResult:
        """Compute delta from a window of ticks."""
        ts = tick_size or self.tick_size
        h_delta: dict[float, float] = defaultdict(float)
        buy_vol = 0.0
        sell_vol = 0.0

        for t in ticks:
            rounded = round(round(t.price / ts) * ts, 10)
            if t.is_buy:
                buy_vol += t.size
                h_delta[rounded] += t.size
            else:
                sell_vol += t.size
                h_delta[rounded] -= t.size

        vertical_delta = buy_vol - sell_vol
        self._cumulative_delta += vertical_delta

        max_delta_price = max(h_delta, key=lambda k: h_delta[k]) if h_delta else 0.0
        min_delta_price = min(h_delta, key=lambda k: h_delta[k]) if h_delta else 0.0
        total = buy_vol + sell_vol

        result = DeltaResult(
            vertical_delta=vertical_delta,
            cumulative_delta=self._cumulative_delta,
            horizontal_delta=dict(h_delta),
            max_delta_price=max_delta_price,
            min_delta_price=min_delta_price,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta_pct=vertical_delta / total if total > 0 else 0.0,
        )

        self._delta_history.append(result)
        if len(self._delta_history) > self._max_history:
            self._delta_history = self._delta_history[-self._max_history:]

        return result

    @property
    def cumulative_delta(self) -> float:
        return self._cumulative_delta

    @property
    def history(self) -> list[DeltaResult]:
        return self._delta_history

    def get_delta_roc(self, lookback: int = 5) -> float:
        """Rate of change of vertical delta over last N bars."""
        if len(self._delta_history) < lookback:
            return 0.0
        recent = [d.vertical_delta for d in self._delta_history[-lookback:]]
        if len(recent) < 2:
            return 0.0
        # Simple slope via linear regression
        x = np.arange(len(recent), dtype=float)
        y = np.array(recent, dtype=float)
        if np.std(x) == 0:
            return 0.0
        slope = float(np.polyfit(x, y, 1)[0])
        return slope

    def get_volume_trend(self, lookback: int = 5) -> float:
        """Slope of total volume over last N bars. Declining = exhaustion clue."""
        if len(self._delta_history) < lookback:
            return 0.0
        recent = [
            d.buy_volume + d.sell_volume
            for d in self._delta_history[-lookback:]
        ]
        x = np.arange(len(recent), dtype=float)
        y = np.array(recent, dtype=float)
        if np.std(x) == 0:
            return 0.0
        slope = float(np.polyfit(x, y, 1)[0])
        return slope

    def detect_delta_peaks(
        self, lookback: int = 20
    ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
        """
        Find local peaks and troughs in cumulative delta for divergence detection.
        Returns (peaks, troughs) as lists of (index, value).
        """
        if len(self._delta_history) < 3:
            return [], []

        history = self._delta_history[-lookback:]
        cd = [d.cumulative_delta for d in history]
        peaks = []
        troughs = []

        for i in range(1, len(cd) - 1):
            if cd[i] > cd[i - 1] and cd[i] > cd[i + 1]:
                peaks.append((i, cd[i]))
            elif cd[i] < cd[i - 1] and cd[i] < cd[i + 1]:
                troughs.append((i, cd[i]))

        return peaks, troughs
