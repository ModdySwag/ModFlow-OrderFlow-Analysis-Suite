"""
Volume Profile Engine
Computes POC, VAH, VAL, LVN, and profile shape classification from tick data.
Implements Fabio's methodology:
  - Cash session profiles (NY session only for US indices)
  - Multi-day profile merging
  - Profile shape: P-shape, b-shape, D-shape, double distribution
  - 68% value area rule
"""

from __future__ import annotations

import numpy as np
from collections import defaultdict
from typing import Optional

from orderflow_system.data.models import Tick, VolumeProfileResult, Candle
from orderflow_system.config.settings import VolumeProfileConfig


class VolumeProfileEngine:
    """
    Builds volume profiles from tick data or candles.

    Core logic from Fabio's teaching:
      - Volume at each price level → histogram
      - POC = price with max volume
      - Value Area = 68% of total volume, expanding from POC
      - LVN = local minima in the histogram, below mean - 1.5*stddev
      - Shape classification based on where POC sits and volume distribution
    """

    def __init__(self, config: VolumeProfileConfig):
        self.config = config

    def compute_from_ticks(
        self, ticks: list[Tick], session_date: str = ""
    ) -> VolumeProfileResult:
        """Build volume profile from raw tick data."""
        if not ticks:
            return VolumeProfileResult(session_date=session_date)

        volume_at_price: dict[float, float] = defaultdict(float)
        tick_size = self.config.tick_size

        for t in ticks:
            rounded = round(round(t.price / tick_size) * tick_size, 10)
            volume_at_price[rounded] += t.size

        return self._compute_profile(dict(volume_at_price), session_date)

    def compute_from_candles(
        self, candles: list[Candle], session_date: str = ""
    ) -> VolumeProfileResult:
        """Build volume profile from candle footprint data."""
        if not candles:
            return VolumeProfileResult(session_date=session_date)

        volume_at_price: dict[float, float] = defaultdict(float)
        tick_size = self.config.tick_size

        for candle in candles:
            if candle.footprint:
                for price, fp in candle.footprint.items():
                    # Re-bucket footprint prices to VP tick_size
                    rounded = round(round(price / tick_size) * tick_size, 10)
                    volume_at_price[rounded] += fp.total_volume
            else:
                # Fallback: distribute candle volume evenly across OHLC range
                low = round(round(candle.low / tick_size) * tick_size, 10)
                high = round(round(candle.high / tick_size) * tick_size, 10)
                n_levels = max(1, int((high - low) / tick_size) + 1)
                vol_per_level = candle.volume / n_levels
                price = low
                while price <= high + tick_size / 2:
                    volume_at_price[round(price, 10)] += vol_per_level
                    price += tick_size

        return self._compute_profile(dict(volume_at_price), session_date)

    def merge_profiles(
        self, profiles: list[VolumeProfileResult]
    ) -> VolumeProfileResult:
        """
        Merge multiple daily profiles into a composite profile.
        Fabio's technique: merge 2-3 overlapping days to refine VAL/VAH.
        """
        if not profiles:
            return VolumeProfileResult()
        if len(profiles) == 1:
            return profiles[0]

        merged_vap: dict[float, float] = defaultdict(float)
        dates = []

        for vp in profiles:
            dates.append(vp.session_date)
            for price, vol in vp.volume_at_price.items():
                merged_vap[price] += vol

        result = self._compute_profile(
            dict(merged_vap),
            session_date=f"{dates[0]}_to_{dates[-1]}",
        )
        return result

    def _compute_profile(
        self, volume_at_price: dict[float, float], session_date: str
    ) -> VolumeProfileResult:
        """Core computation: POC, Value Area, LVN, shape."""
        if not volume_at_price:
            return VolumeProfileResult(session_date=session_date)

        prices = sorted(volume_at_price.keys())
        volumes = np.array([volume_at_price[p] for p in prices])
        total_volume = float(volumes.sum())

        if total_volume == 0:
            return VolumeProfileResult(session_date=session_date)

        # ── POC: price with maximum volume ──
        poc_idx = int(np.argmax(volumes))
        poc = prices[poc_idx]

        # ── Value Area: expand from POC until 68% of volume ──
        vah, val = self._compute_value_area(prices, volumes, poc_idx, total_volume)

        # ── LVN: local minima below mean - 1.5*stddev ──
        lvn_levels = self._detect_lvn(prices, volumes)

        # ── Shape classification ──
        shape, poc_pct = self._classify_shape(prices, volumes, poc_idx)

        return VolumeProfileResult(
            session_date=session_date,
            poc=poc,
            vah=vah,
            val=val,
            volume_at_price=volume_at_price,
            total_volume=total_volume,
            lvn_levels=lvn_levels,
            shape=shape,
            poc_position_pct=poc_pct,
        )

    def _compute_value_area(
        self,
        prices: list[float],
        volumes: np.ndarray,
        poc_idx: int,
        total_volume: float,
    ) -> tuple[float, float]:
        """
        Expand from POC one level at a time (up or down), adding the side
        with higher volume, until 68% of total volume is enclosed.
        """
        target = total_volume * self.config.value_area_pct
        accumulated = float(volumes[poc_idx])
        lo = poc_idx
        hi = poc_idx

        while accumulated < target:
            can_go_up = hi + 1 < len(prices)
            can_go_down = lo - 1 >= 0

            if not can_go_up and not can_go_down:
                break

            vol_up = float(volumes[hi + 1]) if can_go_up else -1.0
            vol_down = float(volumes[lo - 1]) if can_go_down else -1.0

            if vol_up >= vol_down:
                hi += 1
                accumulated += vol_up
            else:
                lo -= 1
                accumulated += vol_down

        val = prices[lo]
        vah = prices[hi]
        return vah, val

    def _detect_lvn(
        self, prices: list[float], volumes: np.ndarray
    ) -> list[float]:
        """
        Detect Low Volume Nodes — price levels with volume significantly
        below the mean. These are inefficient delivery levels where price
        tends to return for rebalancing before resuming trend.
        """
        if len(volumes) < 5:
            return []

        mean_vol = float(np.mean(volumes))
        std_vol = float(np.std(volumes))
        threshold = mean_vol - self.config.lvn_stddev_factor * std_vol
        threshold = max(threshold, mean_vol * 0.2)  # Floor at 20% of mean

        lvn = []
        for i in range(1, len(volumes) - 1):
            # Local minimum AND below threshold
            if (
                volumes[i] < volumes[i - 1]
                and volumes[i] < volumes[i + 1]
                and volumes[i] < threshold
            ):
                lvn.append(prices[i])

        return lvn

    def _classify_shape(
        self,
        prices: list[float],
        volumes: np.ndarray,
        poc_idx: int,
    ) -> tuple[str, float]:
        """
        Classify profile shape per Fabio's methodology:
          - P-shape: POC above 50%, high volume at top → buyers in control
          - b-shape: POC below 50%, high volume at bottom → sellers in control
          - D-shape: POC near center, balanced volume → normal distribution
          - Double distribution: bimodal — two clusters of high volume
        """
        n = len(prices)
        if n == 0:
            return "unknown", 0.5

        poc_pct = poc_idx / max(n - 1, 1)  # 0 = bottom, 1 = top

        # Check for double distribution (bimodal)
        if n >= 10:
            mid = n // 2
            upper_max = int(np.argmax(volumes[mid:])) + mid
            lower_max = int(np.argmax(volumes[:mid]))
            upper_vol = float(volumes[upper_max])
            lower_vol = float(volumes[lower_max])
            mean_vol = float(np.mean(volumes))

            # Both peaks must be significant and there's a valley between them
            if (
                upper_vol > mean_vol * 1.5
                and lower_vol > mean_vol * 1.5
            ):
                # Check for a valley between them
                valley_start = min(lower_max, upper_max)
                valley_end = max(lower_max, upper_max)
                if valley_end - valley_start > 2:
                    valley_min = float(np.min(volumes[valley_start + 1 : valley_end]))
                    if valley_min < min(upper_vol, lower_vol) * 0.5:
                        return "double_dist", poc_pct

        # Single distribution shapes
        if poc_pct > 0.65:
            return "p_shape", poc_pct     # Buyers aggressive, POC at top
        elif poc_pct < 0.35:
            return "b_shape", poc_pct     # Sellers aggressive, POC at bottom
        else:
            return "d_shape", poc_pct     # Balanced / normal
