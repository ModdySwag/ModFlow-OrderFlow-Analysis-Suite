"""
Footprint Engine
Aggregates tick data into price-level bid/ask volume buckets.
Detects imbalances, strong levels, and unfinished auction levels.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from orderflow_system.data.models import Tick, Candle, FootprintLevel, Side


@dataclass
class FootprintBar:
    """Complete footprint for a single time bar."""
    timestamp_ms: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    levels: dict[float, FootprintLevel] = field(default_factory=dict)

    @property
    def total_buy_volume(self) -> float:
        return sum(lv.ask_volume for lv in self.levels.values())

    @property
    def total_sell_volume(self) -> float:
        return sum(lv.bid_volume for lv in self.levels.values())

    @property
    def delta(self) -> float:
        return self.total_buy_volume - self.total_sell_volume

    @property
    def total_volume(self) -> float:
        return self.total_buy_volume + self.total_sell_volume

    def imbalance_levels(self, threshold: float = 3.0) -> list[tuple[float, str]]:
        """
        Find price levels with strong imbalance (buy/sell ratio > threshold).
        These are one-side-print levels — key for initiative auction detection.
        Returns list of (price, 'buy'|'sell') for imbalanced levels.
        """
        results = []
        for price, lv in sorted(self.levels.items()):
            if lv.bid_volume > 0 and lv.ask_volume / lv.bid_volume >= threshold:
                results.append((price, "buy"))
            elif lv.ask_volume > 0 and lv.bid_volume / lv.ask_volume >= threshold:
                results.append((price, "sell"))
            elif lv.bid_volume == 0 and lv.ask_volume > 0:
                results.append((price, "buy"))
            elif lv.ask_volume == 0 and lv.bid_volume > 0:
                results.append((price, "sell"))
        return results

    def max_volume_level(self) -> Optional[tuple[float, FootprintLevel]]:
        """Price level with highest total volume = POC of this bar."""
        if not self.levels:
            return None
        return max(self.levels.items(), key=lambda x: x[1].total_volume)

    def absorption_at_level(self, price: float, tolerance: float = 0.0) -> Optional[FootprintLevel]:
        """Get footprint data at a specific price level."""
        if price in self.levels:
            return self.levels[price]
        # Check with tolerance
        for p, lv in self.levels.items():
            if abs(p - price) <= tolerance:
                return lv
        return None


class FootprintEngine:
    """
    Builds and analyzes footprint data from ticks or candles.
    The footprint shows executed buy and sell orders at each price level,
    revealing aggression, absorption, and imbalance.
    """

    def __init__(self, tick_size: float = 0.1):
        self.tick_size = tick_size
        self._bar_history: list[FootprintBar] = []
        self._max_history = 200

    def build_from_candle(self, candle: Candle) -> FootprintBar:
        """Build footprint bar from a candle that already has footprint data."""
        bar = FootprintBar(
            timestamp_ms=candle.timestamp_ms,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            levels=dict(candle.footprint),
        )
        self._bar_history.append(bar)
        if len(self._bar_history) > self._max_history:
            self._bar_history = self._bar_history[-self._max_history:]
        return bar

    def build_from_ticks(self, ticks: list[Tick], timestamp_ms: int = 0) -> FootprintBar:
        """Build footprint bar from raw ticks."""
        if not ticks:
            return FootprintBar(timestamp_ms=timestamp_ms)

        levels: dict[float, FootprintLevel] = {}
        prices = []

        for t in ticks:
            rounded = round(round(t.price / self.tick_size) * self.tick_size, 10)
            prices.append(t.price)

            if rounded not in levels:
                levels[rounded] = FootprintLevel(price=rounded)

            if t.is_buy:
                levels[rounded].ask_volume += t.size
            else:
                levels[rounded].bid_volume += t.size

        bar = FootprintBar(
            timestamp_ms=timestamp_ms or ticks[0].timestamp_ms,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            levels=levels,
        )

        self._bar_history.append(bar)
        if len(self._bar_history) > self._max_history:
            self._bar_history = self._bar_history[-self._max_history:]

        return bar

    @property
    def history(self) -> list[FootprintBar]:
        return self._bar_history

    def get_recent_bars(self, n: int) -> list[FootprintBar]:
        return self._bar_history[-n:]

    def get_aggressive_volume_at_level(
        self, price: float, lookback_bars: int = 5
    ) -> tuple[float, float]:
        """
        Get total aggressive buy and sell volume at a price level
        across the last N bars. Used for absorption detection.
        Returns (buy_volume, sell_volume) at that level.
        """
        total_buy = 0.0
        total_sell = 0.0
        tolerance = self.tick_size * 0.5

        for bar in self._bar_history[-lookback_bars:]:
            lv = bar.absorption_at_level(price, tolerance)
            if lv:
                total_buy += lv.ask_volume
                total_sell += lv.bid_volume

        return total_buy, total_sell

    def count_consecutive_imbalances(
        self, direction: str, lookback: int = 5, threshold: float = 3.0
    ) -> int:
        """
        Count consecutive bars with one-sided imbalance in a direction.
        Used for initiative auction detection — "constant aggression" signal.
        """
        count = 0
        for bar in reversed(self._bar_history[-lookback:]):
            imbalances = bar.imbalance_levels(threshold)
            has_directional = any(d == direction for _, d in imbalances)
            if has_directional:
                count += 1
            else:
                break
        return count
