"""
Profile Framing — Daily Bias Engine
Implements Fabio's profile framing methodology for determining directional bias.

Core logic:
  1. Build daily cash-session volume profiles
  2. Classify profile shape → P-shape (long), b-shape (short), D (neutral), double (transition)
  3. Track value acceptance/rejection across days
  4. Merge overlapping profiles (2-3 days) for refined VAL/VAH
  5. Detect market shifts: failed auctions, hooks, distribution warnings
  6. Output: daily bias direction + qualified levels for orderflow execution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from orderflow_system.data.models import VolumeProfileResult, Side
from orderflow_system.config.settings import BiasDirection

logger = logging.getLogger(__name__)


class LevelType(Enum):
    VAH = "vah"
    VAL = "val"
    POC = "poc"
    LVN = "lvn"
    MERGED_VAH = "merged_vah"
    MERGED_VAL = "merged_val"


@dataclass
class QualifiedLevel:
    """A price level qualified by profile framing for orderflow execution."""
    price: float
    level_type: LevelType
    direction: Side               # Expected trade direction at this level
    strength: float = 0.0         # How many confirmations (rejection days, merges)
    source_dates: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class DailyBias:
    """Output of the profile framing analysis for the current session."""
    date: str
    direction: BiasDirection = BiasDirection.NEUTRAL
    confidence: float = 0.0        # 0-100
    profile_shape: str = "unknown"
    qualified_levels: list[QualifiedLevel] = field(default_factory=list)
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    lvn_levels: list[float] = field(default_factory=list)
    merged_vah: Optional[float] = None
    merged_val: Optional[float] = None
    notes: str = ""


class ProfileFramingEngine:
    """
    Analyzes multi-day volume profiles to determine directional bias
    and qualify key levels for orderflow execution.

    Fabio's methodology:
      - P-shape profile (POC > 65% position) → buyers in control → bias LONG
      - b-shape profile (POC < 35%) → sellers in control → bias SHORT
      - D-shape → balanced/neutral → fade extremes
      - Profile merging: when days overlap at same level, merge for precision
      - Rejection tracking: 2-3 days rejecting same level → strong wall
      - Market shift detection: accepted value moving direction
      - Failed auction / hook: price tries to break VA boundary, gets rejected
    """

    def __init__(self):
        self._profile_history: list[VolumeProfileResult] = []
        self._bias_history: list[DailyBias] = []
        self._max_history = 30
        self._rejection_tracker: dict[str, list[str]] = {}
        # key = 'vah_zone' or 'val_zone', value = list of dates that rejected

    def add_profile(self, profile: VolumeProfileResult):
        """Add a daily profile to history."""
        self._profile_history.append(profile)
        if len(self._profile_history) > self._max_history:
            self._profile_history = self._profile_history[-self._max_history:]

    def analyze(self, current_price: float = 0.0) -> DailyBias:
        """
        Analyze the most recent profiles to produce a directional bias
        and qualified levels for today's trading.
        """
        if not self._profile_history:
            return DailyBias(date="unknown")

        latest = self._profile_history[-1]
        bias = DailyBias(
            date=latest.session_date,
            poc=latest.poc,
            vah=latest.vah,
            val=latest.val,
            lvn_levels=latest.lvn_levels,
            profile_shape=latest.shape,
        )

        # ── Step 1: Determine direction from profile shape ──
        self._classify_direction(bias, latest)

        # ── Step 2: Check multi-day context ──
        if len(self._profile_history) >= 2:
            self._check_multi_day_context(bias, current_price)

        # ── Step 3: Build qualified levels ──
        self._build_qualified_levels(bias, current_price)

        # ── Step 4: Try multi-day merge for refined levels ──
        if len(self._profile_history) >= 2:
            self._try_merge_profiles(bias)

        self._bias_history.append(bias)
        if len(self._bias_history) > self._max_history:
            self._bias_history = self._bias_history[-self._max_history:]

        return bias

    def _classify_direction(self, bias: DailyBias, profile: VolumeProfileResult):
        """
        Classify bias from profile shape.
        P-shape = buyers in control = LONG bias
        b-shape = sellers in control = SHORT bias
        """
        shape = profile.shape
        poc_pct = profile.poc_position_pct

        if shape == "p_shape":
            bias.direction = BiasDirection.LONG
            bias.confidence = 40 + poc_pct * 30  # Higher POC = stronger
            bias.notes = f"P-shape profile, POC at {poc_pct:.0%} — buyers in control"
        elif shape == "b_shape":
            bias.direction = BiasDirection.SHORT
            bias.confidence = 40 + (1 - poc_pct) * 30
            bias.notes = f"b-shape profile, POC at {poc_pct:.0%} — sellers in control"
        elif shape == "double_dist":
            bias.direction = BiasDirection.NEUTRAL
            bias.confidence = 30
            bias.notes = "Double distribution — transition day, watch for direction"
        else:
            bias.direction = BiasDirection.NEUTRAL
            bias.confidence = 20
            bias.notes = f"D-shape balanced profile, POC at {poc_pct:.0%}"

    def _check_multi_day_context(self, bias: DailyBias, current_price: float):
        """
        Check value acceptance/rejection across recent days.
        - Value moving UP across days → strengthen LONG bias
        - Value moving DOWN → strengthen SHORT bias
        - Repeated rejection at same VAH → warning of distribution
        - Failed auction (hook at VA boundary) → continuation setup
        """
        recent = self._profile_history[-3:]  # Last 3 days
        if len(recent) < 2:
            return

        prev = recent[-2]
        latest = recent[-1]

        # Value acceptance direction
        poc_shift = latest.poc - prev.poc
        vah_shift = latest.vah - prev.vah
        val_shift = latest.val - prev.val

        if poc_shift > 0 and vah_shift > 0:
            # Value accepted higher
            if bias.direction == BiasDirection.LONG:
                bias.confidence = min(100, bias.confidence + 15)
                bias.notes += " | Value accepted higher — momentum confirmed"
            elif bias.direction == BiasDirection.NEUTRAL:
                bias.direction = BiasDirection.LONG
                bias.confidence = min(100, bias.confidence + 10)
        elif poc_shift < 0 and val_shift < 0:
            # Value accepted lower
            if bias.direction == BiasDirection.SHORT:
                bias.confidence = min(100, bias.confidence + 15)
                bias.notes += " | Value accepted lower — downtrend confirmed"
            elif bias.direction == BiasDirection.NEUTRAL:
                bias.direction = BiasDirection.SHORT
                bias.confidence = min(100, bias.confidence + 10)

        # Check for VAH rejection across days (distribution warning)
        if len(recent) >= 2:
            vah_tolerance = (latest.vah - latest.val) * 0.1
            vahs_similar = all(
                abs(p.vah - latest.vah) < vah_tolerance for p in recent[-2:]
            )
            if vahs_similar and latest.shape != "p_shape":
                bias.direction = BiasDirection.WARNING
                bias.confidence = min(100, bias.confidence + 10)
                bias.notes += " | WARNING: VAH rejected for multiple days — possible distribution"

        # Failed auction detection (hook)
        # Use VA boundaries as proxies since VolumeProfileResult doesn't have high/low
        if current_price > 0:
            # Price is above VAL after a session that traded below it → bullish hook
            if current_price > latest.val and prev.val < latest.val:
                bias.notes += " | Failed auction below VAL — hook setup (bullish)"
                bias.confidence = min(100, bias.confidence + 10)
            # Price is below VAH after a session that traded above it → bearish hook
            elif current_price < latest.vah and prev.vah > latest.vah:
                bias.notes += " | Failed auction above VAH — hook setup (bearish)"
                bias.confidence = min(100, bias.confidence + 10)

    def _build_qualified_levels(self, bias: DailyBias, current_price: float):
        """Build the list of qualified levels for orderflow execution."""
        latest = self._profile_history[-1]
        levels = []

        # VAL — primary support / long entry zone in uptrend
        val_dir = Side.BUY if bias.direction in (BiasDirection.LONG, BiasDirection.NEUTRAL) else Side.SELL
        levels.append(QualifiedLevel(
            price=latest.val,
            level_type=LevelType.VAL,
            direction=val_dir,
            strength=50,
            source_dates=[latest.session_date],
            notes="Value Area Low — fade for longs in uptrend, break confirms short",
        ))

        # VAH — primary resistance / short entry zone in downtrend
        vah_dir = Side.SELL if bias.direction in (BiasDirection.SHORT, BiasDirection.NEUTRAL) else Side.BUY
        levels.append(QualifiedLevel(
            price=latest.vah,
            level_type=LevelType.VAH,
            direction=vah_dir,
            strength=50,
            source_dates=[latest.session_date],
            notes="Value Area High — fade for shorts in downtrend, break confirms long",
        ))

        # POC — fair value / mean reversion target
        levels.append(QualifiedLevel(
            price=latest.poc,
            level_type=LevelType.POC,
            direction=val_dir,  # Same as general direction
            strength=30,
            source_dates=[latest.session_date],
            notes="Point of Control — fair value, mean reversion target",
        ))

        # LVN levels — rebalancing magnets / rejection points
        for lvn in latest.lvn_levels:
            # Direction at LVN: price above → expect rejection → SELL; price below → bounce → BUY
            if current_price > 0:
                lvn_dir = Side.SELL if current_price > lvn else Side.BUY
            else:
                lvn_dir = val_dir
            levels.append(QualifiedLevel(
                price=lvn,
                level_type=LevelType.LVN,
                direction=lvn_dir,
                strength=40,
                source_dates=[latest.session_date],
                notes="Low Volume Node — rebalancing pivot, expect rejection",
            ))

        # Strengthen levels that appear across multiple days
        if len(self._profile_history) >= 2:
            prev = self._profile_history[-2]
            tolerance = (latest.vah - latest.val) * 0.05
            for level in levels:
                # Check if level aligns with previous day's levels
                for prev_level in [prev.val, prev.vah, prev.poc]:
                    if abs(level.price - prev_level) < tolerance:
                        level.strength = min(100, level.strength + 20)
                        level.source_dates.append(prev.session_date)
                        level.notes += " | Confluent with previous day"

        bias.qualified_levels = levels

    def _try_merge_profiles(self, bias: DailyBias):
        """
        Merge recent profiles if they overlap at similar levels.
        Fabio merges 2-3 day profiles when value areas overlap to get
        more precise VAL/VAH.
        """
        from orderflow_system.analytics.volume_profile import (
            VolumeProfileEngine,
            VolumeProfileConfig,
        )

        recent = self._profile_history[-3:]
        if len(recent) < 2:
            return

        # Check if profiles overlap (value areas intersect)
        latest = recent[-1]
        to_merge = [latest]

        for prev in recent[:-1]:
            overlap = min(latest.vah, prev.vah) - max(latest.val, prev.val)
            range_avg = ((latest.vah - latest.val) + (prev.vah - prev.val)) / 2
            if range_avg > 0 and overlap / range_avg > 0.3:
                to_merge.append(prev)

        if len(to_merge) < 2:
            return

        # Merge the overlapping profiles
        engine = VolumeProfileEngine(VolumeProfileConfig())
        merged = engine.merge_profiles(to_merge)

        bias.merged_vah = merged.vah
        bias.merged_val = merged.val
        bias.notes += f" | Merged {len(to_merge)}-day profile: VAH={merged.vah:.2f}, VAL={merged.val:.2f}"

        # Add merged levels as qualified
        bias.qualified_levels.append(QualifiedLevel(
            price=merged.val,
            level_type=LevelType.MERGED_VAL,
            direction=Side.BUY,
            strength=70,
            source_dates=[p.session_date for p in to_merge],
            notes=f"Merged {len(to_merge)}-day VAL — high precision support",
        ))
        bias.qualified_levels.append(QualifiedLevel(
            price=merged.vah,
            level_type=LevelType.MERGED_VAH,
            direction=Side.SELL,
            strength=70,
            source_dates=[p.session_date for p in to_merge],
            notes=f"Merged {len(to_merge)}-day VAH — high precision resistance",
        ))

    @property
    def current_bias(self) -> Optional[DailyBias]:
        return self._bias_history[-1] if self._bias_history else None

    @property
    def profile_history(self) -> list[VolumeProfileResult]:
        return self._profile_history
