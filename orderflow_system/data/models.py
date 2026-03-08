"""
Core data models used across the entire system.
Tick, OrderbookSnapshot, Candle, Signal, TradeState — the common language.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class Side(Enum):
    BUY = "buy"
    SELL = "sell"


class SignalType(Enum):
    ABSORPTION = "absorption"
    INITIATIVE = "initiative_auction"
    SWEEP = "book_sweep"
    EXHAUSTION = "exhaustion"
    DIVERGENCE = "delta_divergence"


class TradePhase(Enum):
    """State machine phases for the execution model."""
    WATCHING = "watching"                    # Monitoring a qualified level
    ABSORPTION_DETECTED = "absorption"       # Entry signal seen
    POSITION_OPEN = "position_open"          # Trade entered
    BREAK_EVEN = "break_even"                # SL moved to BE after initiative
    TRAILING = "trailing"                    # Trailing on initiative prints
    CLOSED = "closed"                        # Trade finished


# ──────────────────────────────────────────────
# Raw Market Data
# ──────────────────────────────────────────────

@dataclass(slots=True)
class Tick:
    """Single executed trade from the exchange."""
    timestamp_ms: int          # Unix ms
    price: float
    size: float                # Contracts / quantity
    side: Side                 # Aggressor side (taker)
    trade_id: str = ""

    @property
    def timestamp(self) -> float:
        return self.timestamp_ms / 1000.0

    @property
    def is_buy(self) -> bool:
        return self.side == Side.BUY


@dataclass(slots=True)
class OrderbookLevel:
    """Single price level in the orderbook."""
    price: float
    quantity: float


@dataclass
class OrderbookSnapshot:
    """L2 orderbook state at a point in time."""
    timestamp_ms: int
    bids: list[OrderbookLevel] = field(default_factory=list)  # Sorted desc by price
    asks: list[OrderbookLevel] = field(default_factory=list)  # Sorted asc by price

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2.0
        return None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    def bid_depth(self, levels: int = 5) -> float:
        """Total bid quantity in top N levels."""
        return sum(b.quantity for b in self.bids[:levels])

    def ask_depth(self, levels: int = 5) -> float:
        """Total ask quantity in top N levels."""
        return sum(a.quantity for a in self.asks[:levels])

    def imbalance_ratio(self, levels: int = 5) -> float:
        """Book imbalance: +1 = all bids, -1 = all asks."""
        bd = self.bid_depth(levels)
        ad = self.ask_depth(levels)
        total = bd + ad
        if total == 0:
            return 0.0
        return (bd - ad) / total


# ──────────────────────────────────────────────
# Aggregated Structures
# ──────────────────────────────────────────────

@dataclass
class FootprintLevel:
    """Bid/Ask volume at a single price level within a candle."""
    price: float
    bid_volume: float = 0.0    # Aggressive sell volume hitting this bid
    ask_volume: float = 0.0    # Aggressive buy volume hitting this ask

    @property
    def delta(self) -> float:
        """Horizontal delta at this level."""
        return self.ask_volume - self.bid_volume

    @property
    def total_volume(self) -> float:
        return self.bid_volume + self.ask_volume

    @property
    def imbalance_ratio(self) -> float:
        """Buy/sell ratio. >3 = strong buy imbalance."""
        if self.bid_volume == 0:
            return float("inf") if self.ask_volume > 0 else 0.0
        return self.ask_volume / self.bid_volume


@dataclass
class Candle:
    """OHLCV candle enriched with orderflow data."""
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    buy_volume: float = 0.0       # Aggressive buy volume
    sell_volume: float = 0.0      # Aggressive sell volume
    tick_count: int = 0
    footprint: dict[float, FootprintLevel] = field(default_factory=dict)

    @property
    def delta(self) -> float:
        """Vertical delta for this candle."""
        return self.buy_volume - self.sell_volume

    @property
    def is_green(self) -> bool:
        return self.close >= self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low


# ──────────────────────────────────────────────
# Volume Profile
# ──────────────────────────────────────────────

@dataclass
class VolumeProfileResult:
    """Output of the volume profile engine for a session."""
    session_date: str = ""                           # YYYY-MM-DD
    poc: float = 0.0                               # Point of Control
    vah: float = 0.0                               # Value Area High
    val: float = 0.0                               # Value Area Low
    volume_at_price: dict[float, float] = field(default_factory=dict)
    total_volume: float = 0.0
    lvn_levels: list[float] = field(default_factory=list)
    shape: str = "unknown"                         # p_shape, b_shape, d_shape, double_dist
    poc_position_pct: float = 0.5                  # POC position within range (0=bottom, 1=top)

    @property
    def value_area_range(self) -> float:
        return self.vah - self.val


# ──────────────────────────────────────────────
# Signals
# ──────────────────────────────────────────────

@dataclass
class Signal:
    """Output from a pattern detector."""
    timestamp_ms: int
    signal_type: SignalType
    direction: Side                # Suggested direction
    price_level: float             # Key price
    strength: float = 0.0         # 0-100 confidence score
    details: dict = field(default_factory=dict)

    @property
    def is_bullish(self) -> bool:
        return self.direction == Side.BUY

    def __repr__(self) -> str:
        dir_str = "LONG" if self.is_bullish else "SHORT"
        return (
            f"Signal({self.signal_type.value} {dir_str} "
            f"@ {self.price_level:.2f}, strength={self.strength:.0f})"
        )


# ──────────────────────────────────────────────
# Trade State (State Machine)
# ──────────────────────────────────────────────

@dataclass
class TradeState:
    """
    Tracks the state machine for a single trade idea.
    Qualified Level → Absorption → Position → Break-Even → Trail → Closed
    """
    instrument: str
    direction: Side
    phase: TradePhase = TradePhase.WATCHING
    qualified_level: float = 0.0           # Level from profile framing
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    break_even_price: float = 0.0
    trail_stop: float = 0.0
    absorption_signals: list[Signal] = field(default_factory=list)
    initiative_signals: list[Signal] = field(default_factory=list)
    entry_time_ms: int = 0
    rr_ratio: float = 0.0
    pnl_ticks: float = 0.0
    notes: str = ""

    def advance_to_absorption(self, signal: Signal):
        """Absorption detected at qualified level — entry signal."""
        self.phase = TradePhase.ABSORPTION_DETECTED
        self.absorption_signals.append(signal)

    def advance_to_position(self, entry_price: float, stop_loss: float, take_profit: float):
        """Trade entered."""
        self.phase = TradePhase.POSITION_OPEN
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.break_even_price = entry_price
        self.entry_time_ms = int(time.time() * 1000)
        risk = abs(entry_price - stop_loss)
        if risk > 0:
            self.rr_ratio = abs(take_profit - entry_price) / risk

    def advance_to_break_even(self, signal: Signal):
        """Initiative auction confirmed — move SL to break even."""
        self.phase = TradePhase.BREAK_EVEN
        self.stop_loss = self.break_even_price
        self.trail_stop = self.break_even_price
        self.initiative_signals.append(signal)

    def update_trail(self, new_trail_level: float, signal: Signal):
        """New initiative print — trail stop to the candle's extreme."""
        self.phase = TradePhase.TRAILING
        if self.direction == Side.BUY:
            self.trail_stop = max(self.trail_stop, new_trail_level)
        else:
            self.trail_stop = min(self.trail_stop, new_trail_level)
        self.stop_loss = self.trail_stop
        self.initiative_signals.append(signal)

    def close_trade(self, exit_price: float, reason: str = ""):
        """Trade finished."""
        self.phase = TradePhase.CLOSED
        if self.direction == Side.BUY:
            self.pnl_ticks = exit_price - self.entry_price
        else:
            self.pnl_ticks = self.entry_price - exit_price
        self.notes = reason
