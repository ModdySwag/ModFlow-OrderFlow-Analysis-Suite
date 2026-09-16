"""
Non-time chart frames (the reference layout "Frames": Range, Renko, Reversal, Tick, Volume bars).

The repo's CandleBuilder only produces time bars (60 s). These builders turn the
same tick stream into the four other frame families the reference layout offers, each with its
own close rule:

  Range bar    closes when high−low ≥ N ticks (constant-height bars)
  Renko brick  new brick every N ticks of movement; a reversal needs M bricks
  Reversal bar closes when price retraces R ticks from the running extreme
  Tick bar     closes every N prints
  Volume bar   closes when accumulated size reaches V (all prints are in base units)

Each builder returns a closed bar (OHLCV + delta + tick count + duration) the
moment it closes, so a chart can render it incrementally.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from orderflow_system.data.models import Tick
from orderflow_system.data.enums import as_value


@dataclass
class Bar:
    start_ms: int
    end_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    ticks: int = 0
    frame: str = ""
    # bar statistics (the reference platform's Volumetric bar stats). Zero unless the frame tracks delta.
    delta_min: float = 0.0
    delta_max: float = 0.0
    delta_sh: float = 0.0        # delta since price last touched the bar's high
    delta_sl: float = 0.0        # delta since price last touched the bar's low

    @property
    def delta(self) -> float:
        return self.buy_volume - self.sell_volume

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.end_ms / 1000,
            "open": round(self.open, 8), "high": round(self.high, 8),
            "low": round(self.low, 8), "close": round(self.close, 8),
            "volume": round(self.volume, 8), "delta": round(self.delta, 8),
            "ticks": self.ticks, "frame": self.frame,
            "delta_min": round(self.delta_min, 8), "delta_max": round(self.delta_max, 8),
            "delta_sh": round(self.delta_sh, 8), "delta_sl": round(self.delta_sl, 8),
            "duration_ms": self.end_ms - self.start_ms,
        }


class _Builder:
    frame = "base"

    def __init__(self, symbol: str, tick_size: float, history: int = 500) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.bars: deque[Bar] = deque(maxlen=history)
        self.current: Optional[Bar] = None
        self.last_close: float = 0.0

    # helpers -------------------------------------------------
    def _open(self, tick: Tick) -> Bar:
        ts = int(tick.timestamp_ms or time.time() * 1000)
        bar = Bar(start_ms=ts, end_ms=ts, open=float(tick.price), high=float(tick.price),
                  low=float(tick.price), close=float(tick.price), frame=self.frame)
        self.current = bar
        return bar

    def _add(self, tick: Tick) -> None:
        bar = self.current or self._open(tick)
        price = float(tick.price)
        bar.high = max(bar.high, price)
        bar.low = min(bar.low, price)
        bar.close = price
        bar.volume += float(tick.size)
        if _side(tick) == "buy":
            bar.buy_volume += float(tick.size)
        else:
            bar.sell_volume += float(tick.size)
        bar.ticks += 1
        bar.end_ms = int(tick.timestamp_ms or bar.end_ms)

    def _close(self) -> Bar:
        assert self.current is not None
        bar, self.current = self.current, None
        self.bars.append(bar)
        self.last_close = bar.close
        return bar

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        raise NotImplementedError

    def recent(self, count: int = 200) -> list[dict]:
        return [b.to_dict() for b in list(self.bars)[-count:]]


class RangeBars(_Builder):
    """Constant-height bars: close when high−low reaches N ticks."""

    frame = "range"

    def __init__(self, symbol: str, tick_size: float, range_ticks: float = 20.0, history: int = 500) -> None:
        super().__init__(symbol, tick_size, history)
        self.range = float(range_ticks) * self.tick_size

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        self._add(tick)
        assert self.current is not None
        if self.current.high - self.current.low >= self.range:
            return self._close()
        return None


class RenkoBricks(_Builder):
    """Renko: a brick per N ticks of movement, reversals need M bricks."""

    frame = "renko"

    def __init__(self, symbol: str, tick_size: float, brick_ticks: float = 20.0,
                 reversal_bricks: int = 2, history: int = 500) -> None:
        super().__init__(symbol, tick_size, history)
        self.brick = float(brick_ticks) * self.tick_size
        self.reversal = max(1, int(reversal_bricks))
        self._direction = 0          # +1 up, -1 down, 0 unknown
        self._extreme = 0.0

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        price = float(tick.price)
        if not self.last_close:
            self.last_close = price
            self._extreme = price
            return None
        if self._direction == 0:
            if price - self.last_close >= self.brick:
                self._direction = 1
            elif self.last_close - price >= self.brick:
                self._direction = -1
            else:
                return None

        move = price - self.last_close
        brick = self.brick
        if self._direction > 0:
            if move >= brick:
                return self._emit(self.last_close, self.last_close + brick, tick, up=True)
            if self.last_close - price >= brick * self.reversal:
                self._direction = -1
                return self._emit(self.last_close, self.last_close - brick, tick, up=False)
        else:
            if -move >= brick:
                return self._emit(self.last_close, self.last_close - brick, tick, up=False)
            if price - self.last_close >= brick * self.reversal:
                self._direction = 1
                return self._emit(self.last_close, self.last_close + brick, tick, up=True)
        return None

    def _emit(self, open_: float, close_: float, tick: Tick, up: bool) -> Bar:
        ts = int(tick.timestamp_ms or time.time() * 1000)
        hi, lo = max(open_, close_), min(open_, close_)
        bar = Bar(start_ms=ts, end_ms=ts, open=open_, high=hi, low=lo, close=close_,
                  volume=float(tick.size),
                  buy_volume=float(tick.size) if _side(tick) == "buy" else 0.0,
                  sell_volume=float(tick.size) if _side(tick) == "sell" else 0.0,
                  ticks=1, frame=self.frame)
        self.bars.append(bar)
        self.last_close = close_
        self._extreme = close_
        return bar


class ReversalBars(_Builder):
    """Trend bars that close on an R-tick retrace from the running extreme."""

    frame = "reversal"

    def __init__(self, symbol: str, tick_size: float, reversal_ticks: float = 30.0, history: int = 500) -> None:
        super().__init__(symbol, tick_size, history)
        self.reversal = float(reversal_ticks) * self.tick_size

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        self._add(tick)
        assert self.current is not None
        bar = self.current
        if bar.high - tick.price >= self.reversal or tick.price - bar.low >= self.reversal:
            return self._close()
        return None


class TickBars(_Builder):
    """One bar per N prints."""

    frame = "tick"

    def __init__(self, symbol: str, tick_size: float, ticks_per_bar: int = 250, history: int = 500) -> None:
        super().__init__(symbol, tick_size, history)
        self.n = max(1, int(ticks_per_bar))

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        self._add(tick)
        assert self.current is not None
        if self.current.ticks >= self.n:
            return self._close()
        return None


class VolumeBars(_Builder):
    """One bar per V traded base units."""

    frame = "volume"

    def __init__(self, symbol: str, tick_size: float, volume_per_bar: float = 50.0, history: int = 500) -> None:
        super().__init__(symbol, tick_size, history)
        self.v = float(volume_per_bar)

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        self._add(tick)
        assert self.current is not None
        if self.current.volume >= self.v:
            return self._close()
        return None


class DeltaBars(_Builder):
    """Delta bars — the reference platform *Price On Volume* idea, on cumulative delta.

    A new bar starts when the delta accumulated inside the current bar pushes past
    `trend_delta` in its own direction, or when it reverses by `reversal_delta` from
    that extreme. That makes the frame a picture of *effort*, not of time or ticks:
    quiet drift builds long bars, aggressive directional bursts build short ones.
    """

    frame = "delta"

    def __init__(self, symbol: str, tick_size: float, trend_delta: float = 25.0,
                 reversal_delta: float = 15.0, history: int = 500) -> None:
        super().__init__(symbol, tick_size, history)
        self.trend_delta = max(1e-9, float(trend_delta))
        self.reversal_delta = max(1e-9, float(reversal_delta))
        self.bar_delta = 0.0
        self.bar_high_delta = 0.0
        self.bar_low_delta = 0.0
        self._delta_started = False      # min/max must start at the first print, not at 0
        self._high_price = 0.0
        self._low_price = 0.0
        self._delta_at_high = 0.0
        self._delta_at_low = 0.0

    def _add(self, tick: Tick) -> None:
        price_before = self.current.high if self.current else 0.0
        low_before = self.current.low if self.current else 0.0
        super()._add(tick)
        price = float(tick.price)
        size = float(tick.size)
        self.bar_delta += size if _side(tick) == "buy" else -size
        if not self._delta_started:
            # A one-sided bar (only buys, or only sells) has a min/max equal to its own
            # running delta — starting them at zero would report the case the reference platform
            # explicitly calls out ("min delta could be positive, i.e. a strong up bar")
            # as 0 and hide it.
            self.bar_high_delta = self.bar_low_delta = self.bar_delta
            self._delta_started = True
        else:
            self.bar_high_delta = max(self.bar_high_delta, self.bar_delta)
            self.bar_low_delta = min(self.bar_low_delta, self.bar_delta)
        if price > price_before:
            self._delta_at_high = self.bar_delta      # delta so far when the high was made
            self._high_price = price
        if price < low_before or not low_before:
            self._delta_at_low = self.bar_delta
            self._low_price = price

    def on_tick(self, tick: Tick) -> Optional[Bar]:
        if self.current is None:
            self.bar_delta = self.bar_high_delta = self.bar_low_delta = 0.0
            self._delta_started = False
        self._add(tick)
        assert self.current is not None
        closed = False
        if abs(self.bar_delta) >= self.trend_delta:
            closed = True                      # trend leg completed
        elif self.bar_high_delta - self.bar_delta >= self.reversal_delta and self.bar_high_delta > 0:
            closed = True                      # buyers took it up, sellers pulled it back
        elif self.bar_delta - self.bar_low_delta >= self.reversal_delta and self.bar_low_delta < 0:
            closed = True                      # mirror case below
        if not closed:
            return None
        bar = self.current
        bar.delta_min = self.bar_low_delta
        bar.delta_max = self.bar_high_delta
        bar.delta_sh = self.bar_delta - self._delta_at_high
        bar.delta_sl = self.bar_delta - self._delta_at_low
        bar = self._close()
        self.bar_delta = self.bar_high_delta = self.bar_low_delta = 0.0
        self._delta_started = False
        self._delta_at_high = self._delta_at_low = 0.0
        return bar


class FrameSet:
    """All six frame families fed by one tick stream."""

    def __init__(self, symbol: str, tick_size: float, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or {}
        self.symbol = symbol
        self.builders: dict[str, _Builder] = {
            "range": RangeBars(symbol, tick_size, cfg.get("range_ticks", 20.0)),
            "renko": RenkoBricks(symbol, tick_size, cfg.get("brick_ticks", 20.0), cfg.get("reversal_bricks", 2)),
            "reversal": ReversalBars(symbol, tick_size, cfg.get("reversal_ticks", 30.0)),
            "tick": TickBars(symbol, tick_size, cfg.get("ticks_per_bar", 250)),
            "volume": VolumeBars(symbol, tick_size, cfg.get("volume_per_bar", 50.0)),
            "delta": DeltaBars(symbol, tick_size, cfg.get("delta_trend", 25.0), cfg.get("delta_reversal", 15.0)),
        }

    def on_tick(self, tick: Tick) -> dict[str, Bar]:
        closed: dict[str, Bar] = {}
        for name, builder in self.builders.items():
            bar = builder.on_tick(tick)
            if bar is not None:
                closed[name] = bar
        return closed

    def recent(self, frame: str, count: int = 200) -> list[dict]:
        builder = self.builders.get(frame)
        return builder.recent(count) if builder else []

    def snapshot(self) -> dict[str, Any]:
        return {name: {"bars": len(b.bars), "last": b.bars[-1].to_dict() if b.bars else None}
                for name, b in self.builders.items()}

    def clear(self) -> None:
        for b in self.builders.values():
            b.bars.clear()
            b.current = None
            b.last_close = 0.0


def _side(tick: Tick) -> str:
    return as_value(tick.side)
