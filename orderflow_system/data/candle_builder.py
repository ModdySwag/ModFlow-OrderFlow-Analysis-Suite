"""
Candle Builder — aggregates ticks into OHLCV candles with footprint data.
Builds candles in real-time from the tick stream.
"""

from __future__ import annotations

from typing import Callable, Optional

from orderflow_system.data.models import Tick, Candle, FootprintLevel


#: MEM-A2-03: with 5,000 candles each carrying a full footprint dict the builder measured
#: ~45-255 MiB per instrument. The 5,000-candle window itself stays (the chart, the range-VP
#: and the delta endpoints aggregate over it), but only the newest bars keep their footprint —
#: footprint-level detail is only ever read for recent bars.
FOOTPRINT_KEEP = 200


class CandleBuilder:
    """
    Builds time-based candles from a tick stream.
    Each candle includes full footprint data (bid/ask volume at each price level).
    """

    def __init__(
        self,
        interval_seconds: int = 60,
        tick_size: float = 0.1,
        on_candle_close: Optional[Callable] = None,
    ):
        self.interval_ms = interval_seconds * 1000
        self.tick_size = tick_size
        self.on_candle_close = on_candle_close
        self._current_candle: Optional[Candle] = None
        self._candle_history: list[Candle] = []
        self._max_history = 5000
        #: Prints older than the live interval (venue reorder, replay overlap) are counted here
        #: and dropped — never folded into the open bar (see process_tick; audit D-02).
        self.late_prints = 0

    def _round_price(self, price: float) -> float:
        """Round price to tick size for footprint grouping."""
        return round(round(price / self.tick_size) * self.tick_size, 10)

    def _candle_start_ms(self, timestamp_ms: int) -> int:
        """Align timestamp to candle interval boundary."""
        return (timestamp_ms // self.interval_ms) * self.interval_ms

    async def process_tick(self, tick: Tick) -> Optional[Candle]:
        """
        Feed a tick into the builder. Returns a closed candle if interval completed.
        """
        candle_start = self._candle_start_ms(tick.timestamp_ms)
        closed_candle = None

        # Check if we need to close current candle and start new one
        if self._current_candle is not None:
            if candle_start > self._current_candle.timestamp_ms:
                closed_candle = self._current_candle
                # Clear BEFORE the callback: while it runs the interval is no longer live, so a
                # second caller (a racing coroutine) can never close the same candle twice.
                self._current_candle = None
                # Deduplicate: replace last entry if same timestamp
                if (self._candle_history
                        and self._candle_history[-1].timestamp_ms
                        == closed_candle.timestamp_ms):
                    self._candle_history[-1] = closed_candle
                else:
                    self._candle_history.append(closed_candle)
                if len(self._candle_history) > self._max_history:
                    self._candle_history = self._candle_history[-self._max_history:]
                # MEM-A2-03: the candle that just left the footprint window gives its dict up.
                if len(self._candle_history) > FOOTPRINT_KEEP:
                    stale = self._candle_history[-FOOTPRINT_KEEP - 1]
                    if stale.footprint:
                        stale.footprint = {}

                if self.on_candle_close:
                    await self.on_candle_close(closed_candle)
            elif candle_start < self._current_candle.timestamp_ms:
                # A print older than the live interval — a venue reorder, a replay overlapping
                # live data. Folding it in rewrote the live bar's OHLCV, footprint and delta with
                # another interval's data; count it and drop it instead.
                self.late_prints += 1
                return None

        # Start new candle if needed
        if self._current_candle is None:
            self._current_candle = Candle(
                timestamp_ms=candle_start,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
            )

        # Update OHLCV
        c = self._current_candle
        c.high = max(c.high, tick.price)
        c.low = min(c.low, tick.price)
        c.close = tick.price
        c.volume += tick.size
        c.tick_count += 1

        if tick.is_buy:
            c.buy_volume += tick.size
        else:
            c.sell_volume += tick.size

        # Update footprint at this price level
        fp_price = self._round_price(tick.price)
        if fp_price not in c.footprint:
            c.footprint[fp_price] = FootprintLevel(price=fp_price)

        if tick.is_buy:
            c.footprint[fp_price].ask_volume += tick.size
        else:
            c.footprint[fp_price].bid_volume += tick.size

        return closed_candle

    @property
    def current_candle(self) -> Optional[Candle]:
        return self._current_candle

    @property
    def history(self) -> list[Candle]:
        return self._candle_history

    def stats(self) -> dict:
        """Builder counters for the engine status payload (late prints are dropped — D-02)."""
        return {
            "interval_ms": self.interval_ms,
            "tick_size": self.tick_size,
            "candles": len(self._candle_history),
            "current_start_ms": self._current_candle.timestamp_ms if self._current_candle else 0,
            "late_prints": self.late_prints,
        }

    def get_recent_candles(self, n: int) -> list[Candle]:
        """Return last N closed candles."""
        return self._candle_history[-n:]

    def load_historical_candles(self, candles: list[Candle]) -> int:
        """
        Bulk-load historical candles (e.g. from MT5 bars).
        Prepends them before any real-time candles, deduplicating by timestamp.
        Returns the number of candles actually added.
        """
        if not candles:
            return 0

        # Existing timestamps for dedup
        existing_ts = {c.timestamp_ms for c in self._candle_history}
        new_candles = [c for c in candles if c.timestamp_ms not in existing_ts]

        if not new_candles:
            return 0

        # Merge: historical first, then real-time, sorted by time
        merged = sorted(new_candles + self._candle_history, key=lambda c: c.timestamp_ms)
        self._candle_history = merged[-self._max_history:]
        # MEM-A2-03: the same footprint release after a bulk merge (a seeded history).
        for candle in self._candle_history[:-FOOTPRINT_KEEP]:
            if candle.footprint:
                candle.footprint = {}
        return len(new_candles)
