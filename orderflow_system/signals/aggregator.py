"""
Signal Aggregator & State Machine
Combines all pattern signals with volume profile context into actionable trade alerts.

Implements Fabio's execution model as a state machine:
  WATCHING → ABSORPTION_DETECTED → POSITION_OPEN → BREAK_EVEN → TRAILING → CLOSED

Signal weighting:
  - Absorption: 30% (primary entry)
  - Delta/Divergence: 25% (confirmation)
  - Volume Profile context: 25% (level qualification)
  - Initiative/Sweep: 20% (BE trigger / trail)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from orderflow_system.data.models import (
    Signal, SignalType, Side, TradeState, TradePhase, Candle,
)
from orderflow_system.signals.profile_framing import DailyBias, QualifiedLevel
from orderflow_system.config.settings import BiasDirection
from orderflow_system.patterns import remember_signal

logger = logging.getLogger(__name__)

#: MEM-A1-04: watched levels are working state, not an archive. The radar keeps its own
#: lifecycle (max_age_ms + spent_keep_ms) and the entry check only reads the nearest level, so
#: 200 per instrument is far more than a session of actionable ones and makes the per-signal
#: scan bounded. The pattern is the file next door: `patterns.remember_signal`.
MAX_WATCHED_LEVELS = 200


@dataclass
class AggregatedSignal:
    """Weighted combination of multiple signals at a qualified level."""
    timestamp_ms: int
    direction: Side
    composite_score: float = 0.0       # 0-100
    qualified_level: Optional[QualifiedLevel] = None
    signals: list[Signal] = field(default_factory=list)
    action: str = ""                    # 'enter', 'break_even', 'trail', 'exit', 'alert_only'
    suggested_sl: float = 0.0
    suggested_tp: float = 0.0
    notes: str = ""


class SignalAggregator:
    """
    Combines pattern signals with profile context and manages the trade state machine.

    Flow:
    1. Profile framing qualifies levels and sets daily bias
    2. When price reaches a qualified level, enter WATCHING state
    3. Absorption at the level → ENTRY signal (composite score must pass threshold)
    4. Initiative auction after entry → BREAK EVEN trigger
    5. Subsequent initiative prints → TRAIL stop
    6. Exhaustion or divergence → EXIT / reduce
    """

    def __init__(
        self,
        min_composite_score: float = 60.0,
        signal_cooldown_seconds: float = 60.0,
        price_proximity_pct: float = 0.002,  # 0.2% proximity to qualified level
    ):
        self.min_composite_score = min_composite_score
        self.signal_cooldown_seconds = signal_cooldown_seconds
        self.price_proximity_pct = price_proximity_pct
        self._active_trades: dict[str, TradeState] = {}  # instrument → trade
        self._watched_levels: dict[str, list[QualifiedLevel]] = {}  # instrument → watched levels
        self._last_signal_time: dict[str, int] = {}      # instrument → timestamp_ms
        self._signal_history: list[AggregatedSignal] = []

    def process_signal(
        self,
        instrument: str,
        signal: Signal,
        bias: Optional[DailyBias],
        current_price: float,
        recent_candles: list[Candle],
    ) -> Optional[AggregatedSignal]:
        """
        Process a new pattern signal against the current bias and trade state.
        Returns an aggregated signal if action is needed.
        """
        now_ms = int(time.time() * 1000)

        # Cooldown check
        last_ts = self._last_signal_time.get(instrument, 0)
        if now_ms - last_ts < self.signal_cooldown_seconds * 1000:
            return None

        active_trade = self._active_trades.get(instrument)

        # ── State machine routing ──

        if active_trade is None or active_trade.phase == TradePhase.CLOSED:
            # No active trade — check for new entry
            return self._check_new_entry(
                instrument, signal, bias, current_price, now_ms
            )

        elif active_trade.phase == TradePhase.WATCHING:
            # Watching a qualified level — look for absorption or sweep
            if signal.signal_type == SignalType.ABSORPTION:
                return self._handle_absorption_at_level(
                    instrument, signal, bias, active_trade, current_price, now_ms
                )
            elif signal.signal_type == SignalType.SWEEP:
                # Sweep at watched level — generate alert but don't enter
                return self._handle_sweep_at_level(
                    instrument, signal, bias, active_trade, current_price, now_ms
                )

        elif active_trade.phase == TradePhase.POSITION_OPEN:
            # Position open, waiting for BE trigger
            if signal.signal_type == SignalType.INITIATIVE:
                return self._handle_initiative_for_be(
                    instrument, signal, active_trade, now_ms
                )
            elif signal.signal_type in (SignalType.EXHAUSTION, SignalType.DIVERGENCE):
                return self._handle_exit_warning(
                    instrument, signal, active_trade, now_ms
                )

        elif active_trade.phase in (TradePhase.BREAK_EVEN, TradePhase.TRAILING):
            # Trailing — update trail or detect exit
            if signal.signal_type == SignalType.INITIATIVE:
                return self._handle_initiative_for_trail(
                    instrument, signal, active_trade, recent_candles, now_ms
                )
            elif signal.signal_type in (SignalType.EXHAUSTION, SignalType.DIVERGENCE):
                return self._handle_exit_warning(
                    instrument, signal, active_trade, now_ms
                )

        return None

    def set_watching(
        self, instrument: str, level: QualifiedLevel, direction: Side
    ):
        """Begin watching a qualified level for entry signals."""
        # Track multiple watched levels per instrument (don't overwrite)
        if instrument not in self._watched_levels:
            self._watched_levels[instrument] = []

        # Avoid duplicate levels (same price within 0.01%)
        for existing in self._watched_levels[instrument]:
            if abs(existing.price - level.price) / max(level.price, 1) < 0.0001:
                return  # Already watching this level

        watched = self._watched_levels[instrument]
        watched.append(level)
        # MEM-A1-04: watched levels are working state, not history — the radar expires its own
        # levels and the state machine only ever reads the nearest one, so the list is capped
        # (oldest dropped). Unbounded, it grew for the whole session (audit A1-04) and made the
        # per-absorption scan linear.
        if len(watched) > MAX_WATCHED_LEVELS:
            del watched[:-MAX_WATCHED_LEVELS]

        # Only create WATCHING trade if no active trade yet
        active = self._active_trades.get(instrument)
        if active is None or active.phase == TradePhase.CLOSED:
            trade = TradeState(
                instrument=instrument,
                direction=direction,
                phase=TradePhase.WATCHING,
                qualified_level=level.price,
            )
            self._active_trades[instrument] = trade
            logger.info(
                f"[{instrument}] WATCHING {level.level_type.value} "
                f"@ {level.price:.2f} for {'LONG' if direction == Side.BUY else 'SHORT'}"
            )

    def _check_new_entry(
        self,
        instrument: str,
        signal: Signal,
        bias: Optional[DailyBias],
        current_price: float,
        now_ms: int,
    ) -> Optional[AggregatedSignal]:
        """Check if a new signal qualifies for entry at a profile level."""
        if signal.signal_type != SignalType.ABSORPTION:
            return None  # Only absorption triggers new entries

        if bias is None or not bias.qualified_levels:
            return None

        # Find nearest qualified level to current price
        nearest = None
        min_dist = float("inf")

        for level in bias.qualified_levels:
            dist = abs(current_price - level.price) / max(current_price, 1.0)
            if dist < min_dist and dist < self.price_proximity_pct:
                min_dist = dist
                nearest = level

        if nearest is None:
            return None  # Not near any qualified level

        # Check direction alignment
        if nearest.direction != signal.direction:
            return None

        # Compute composite score
        score = self._compute_composite_score(signal, nearest, bias)

        if score < self.min_composite_score:
            return None

        # Create trade state
        trade = TradeState(
            instrument=instrument,
            direction=signal.direction,
            qualified_level=nearest.price,
        )
        trade.advance_to_absorption(signal)

        # Compute SL/TP and advance to position
        sl, tp = self._compute_sl_tp(signal.direction, nearest, bias, current_price)
        trade.advance_to_position(current_price, sl, tp)
        self._active_trades[instrument] = trade

        agg = AggregatedSignal(
            timestamp_ms=now_ms,
            direction=signal.direction,
            composite_score=score,
            qualified_level=nearest,
            signals=[signal],
            action="enter",
            suggested_sl=sl,
            suggested_tp=tp,
            notes=(
                f"ENTRY SIGNAL: Absorption at {nearest.level_type.value} "
                f"({nearest.price:.2f}). Score: {score:.0f}. "
                f"SL: {sl:.2f}, TP: {tp:.2f}"
            ),
        )
        self._last_signal_time[instrument] = now_ms
        remember_signal(self._signal_history, agg)
        return agg

    def _handle_absorption_at_level(
        self,
        instrument: str,
        signal: Signal,
        bias: Optional[DailyBias],
        trade: TradeState,
        current_price: float,
        now_ms: int,
    ) -> Optional[AggregatedSignal]:
        """Handle absorption signal while watching a level."""
        # Find nearest watched level matching signal direction
        watched = self._watched_levels.get(instrument, [])
        nearest_level = None
        min_dist = float("inf")
        for wl in watched:
            if wl.direction != signal.direction:
                continue
            dist = abs(current_price - wl.price) / max(current_price, 1.0)
            if dist < min_dist and dist < self.price_proximity_pct:
                min_dist = dist
                nearest_level = wl

        if nearest_level is None:
            # Fall back to original logic
            if signal.direction != trade.direction:
                return None
            nearest_level = self._find_qualified_level(bias, trade.qualified_level)

        trade.advance_to_absorption(signal)

        score = self._compute_composite_score(signal, nearest_level, bias)

        if score < self.min_composite_score:
            return None

        sl, tp = self._compute_sl_tp(
            signal.direction, nearest_level, bias, current_price
        )

        # Advance to position with SL/TP
        trade.advance_to_position(current_price, sl, tp)

        agg = AggregatedSignal(
            timestamp_ms=now_ms,
            direction=signal.direction,
            composite_score=score,
            qualified_level=nearest_level,
            signals=[signal],
            action="enter",
            suggested_sl=sl,
            suggested_tp=tp,
            notes=(
                f"ENTRY: Absorption confirmed at watched level "
                f"{nearest_level.price:.2f}. Attempts: {len(trade.absorption_signals)}"
            ),
        )
        self._last_signal_time[instrument] = now_ms
        remember_signal(self._signal_history, agg)
        return agg

    def _handle_initiative_for_be(
        self,
        instrument: str,
        signal: Signal,
        trade: TradeState,
        now_ms: int,
    ) -> Optional[AggregatedSignal]:
        """Initiative after entry → move to break even."""
        if signal.direction != trade.direction:
            return None

        trade.advance_to_break_even(signal)

        agg = AggregatedSignal(
            timestamp_ms=now_ms,
            direction=trade.direction,
            composite_score=signal.strength,
            signals=[signal],
            action="break_even",
            notes=(
                f"BREAK EVEN: Initiative auction confirmed. "
                f"Move SL to entry {trade.break_even_price:.2f}"
            ),
        )
        self._last_signal_time[instrument] = now_ms
        remember_signal(self._signal_history, agg)
        return agg

    def _handle_initiative_for_trail(
        self,
        instrument: str,
        signal: Signal,
        trade: TradeState,
        recent_candles: list[Candle],
        now_ms: int,
    ) -> Optional[AggregatedSignal]:
        """Subsequent initiative prints → trail stop."""
        if signal.direction != trade.direction:
            return None

        # Trail to the low of the initiative candle (for longs) or high (for shorts)
        if recent_candles:
            last_candle = recent_candles[-1]
            if trade.direction == Side.BUY:
                new_trail = last_candle.low
            else:
                new_trail = last_candle.high
        else:
            new_trail = signal.price_level

        trade.update_trail(new_trail, signal)

        agg = AggregatedSignal(
            timestamp_ms=now_ms,
            direction=trade.direction,
            composite_score=signal.strength,
            signals=[signal],
            action="trail",
            notes=(
                f"TRAIL: New initiative print. "
                f"Move SL to {trade.trail_stop:.2f}"
            ),
        )
        self._last_signal_time[instrument] = now_ms
        remember_signal(self._signal_history, agg)
        return agg

    def _handle_exit_warning(
        self,
        instrument: str,
        signal: Signal,
        trade: TradeState,
        now_ms: int,
    ) -> Optional[AggregatedSignal]:
        """Exhaustion or divergence → warning to exit/tighten."""
        # Only warn if signal is AGAINST current trade direction
        if signal.direction == trade.direction:
            return None  # Same direction exhaustion/divergence = less relevant

        action = "exit_warning"
        if signal.strength >= 70:
            action = "exit"
            # Auto-close trade on strong exit signal
            trade.close_trade(signal.price_level, f"{signal.signal_type.value} exit (strength {signal.strength:.0f})")

        agg = AggregatedSignal(
            timestamp_ms=now_ms,
            direction=signal.direction,
            composite_score=signal.strength,
            signals=[signal],
            action=action,
            notes=(
                f"{'EXIT' if action == 'exit' else 'WARNING'}: "
                f"{signal.signal_type.value} detected against position. "
                f"Strength: {signal.strength:.0f}"
            ),
        )
        self._last_signal_time[instrument] = now_ms
        remember_signal(self._signal_history, agg)
        return agg

    def _handle_sweep_at_level(
        self,
        instrument: str,
        signal: Signal,
        bias: Optional[DailyBias],
        trade: TradeState,
        current_price: float,
        now_ms: int,
    ) -> Optional[AggregatedSignal]:
        """Handle sweep signal while watching a level — alert only, adds context."""
        agg = AggregatedSignal(
            timestamp_ms=now_ms,
            direction=signal.direction,
            composite_score=signal.strength,
            signals=[signal],
            action="alert_only",
            notes=(
                f"SWEEP detected near watched level @ {trade.qualified_level:.2f}. "
                f"Strength: {signal.strength:.0f} — watch for absorption follow-up"
            ),
        )
        self._last_signal_time[instrument] = now_ms
        remember_signal(self._signal_history, agg)
        return agg

    def _compute_composite_score(
        self,
        signal: Signal,
        level: Optional[QualifiedLevel],
        bias: Optional[DailyBias],
    ) -> float:
        """
        Weighted composite score:
          Absorption: 30%
          Delta/Divergence: 25%
          VP context (level strength): 25%
          Initiative/Sweep: 20%
        """
        score = 0.0

        # Signal strength component (30-40% depending on type)
        if signal.signal_type == SignalType.ABSORPTION:
            score += signal.strength * 0.30
        elif signal.signal_type in (SignalType.DIVERGENCE,):
            score += signal.strength * 0.25
        elif signal.signal_type == SignalType.INITIATIVE:
            score += signal.strength * 0.20
        elif signal.signal_type == SignalType.SWEEP:
            score += signal.strength * 0.20
        else:
            score += signal.strength * 0.15

        # Volume profile context (25%)
        if level:
            score += level.strength * 0.25

        # Bias alignment (remaining %)
        if bias:
            bias_aligned = (
                (bias.direction == BiasDirection.LONG and signal.direction == Side.BUY)
                or (bias.direction == BiasDirection.SHORT and signal.direction == Side.SELL)
            )
            if bias_aligned:
                score += bias.confidence * 0.20
            elif bias.direction == BiasDirection.WARNING:
                score -= 10  # Penalty for trading against warning

        return min(100.0, max(0.0, score))

    def _compute_sl_tp(
        self,
        direction: Side,
        level: Optional[QualifiedLevel],
        bias: Optional[DailyBias],
        current_price: float,
    ) -> tuple[float, float]:
        """Compute suggested stop loss and take profit."""
        if bias is None:
            # Default: 0.3% SL, 0.6% TP
            if direction == Side.BUY:
                return current_price * 0.997, current_price * 1.006
            else:
                return current_price * 1.003, current_price * 0.994

        if direction == Side.BUY:
            # SL below VAL or absorption zone
            sl = bias.val - (bias.vah - bias.val) * 0.1
            # TP at POC first, then VAH
            tp = bias.vah
        else:
            # SL above VAH
            sl = bias.vah + (bias.vah - bias.val) * 0.1
            # TP at POC first, then VAL
            tp = bias.val

        return sl, tp

    def _find_qualified_level(
        self, bias: Optional[DailyBias], price: float
    ) -> Optional[QualifiedLevel]:
        """Find the qualified level closest to a price."""
        if bias is None or not bias.qualified_levels:
            return None
        return min(
            bias.qualified_levels,
            key=lambda lv: abs(lv.price - price),
        )

    def get_active_trade(self, instrument: str) -> Optional[TradeState]:
        return self._active_trades.get(instrument)

    def close_trade(self, instrument: str, exit_price: float, reason: str = ""):
        trade = self._active_trades.get(instrument)
        if trade:
            trade.close_trade(exit_price, reason)

    @property
    def signal_history(self) -> list[AggregatedSignal]:
        return self._signal_history
