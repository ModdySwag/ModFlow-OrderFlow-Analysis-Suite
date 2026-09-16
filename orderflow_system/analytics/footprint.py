"""
Footprint Engine
Aggregates tick data into price-level bid/ask volume buckets.
Detects imbalances, strong levels, and unfinished auction levels.

The analysis pack below (`analyse_levels`) rebuilds the four behaviours traders pay
the DTC platform's advanced service package for in its Numbers Bars study — same-price and
**diagonal** imbalance, the "calculated values" row, equal-side highlighting and the
min/max highlight — plus a print-size filter (their Volume Filtering) at build time.
Function-level rebuild: no the DTC platform code, naming or colours; the maths is standard
footprint arithmetic and is pinned by `test_footprint_analysis.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Optional

#: price → (bid volume, ask volume) — the only shape the analysis pack needs
MappingLike = Mapping[float, tuple[float, float]] | dict[float, tuple[float, float]]

from orderflow_system.data.models import Tick, Candle, FootprintLevel


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

    def imbalance_levels(self, threshold: float = 3.0, mode: str = "same_price",
                         tick_size: float = 0.0) -> list[tuple[float, str]]:
        """
        One-sided print levels — key for initiative auction detection.

        ``mode="same_price"`` compares the two sides of one price row (the reference layout
        convention this module started with). ``mode="diagonal"`` compares a row's ask
        against the **bid one tick below** and its bid against the **ask one tick above**
        (the conventional diagonal convention): a lift through an offer that has no bid of its own
        is invisible to a same-price ratio — the opposite side of that row is simply
        empty — but obvious against the neighbouring row.

        Returns a list of (price, 'buy'|'sell').
        """
        rows = sorted(self.levels.items())
        if mode == "diagonal" and rows:
            tick = float(tick_size or 0.0)
            if tick <= 0:
                gaps = [abs(rows[i + 1][0] - rows[i][0]) for i in range(len(rows) - 1) if rows[i + 1][0] != rows[i][0]]
                tick = min(gaps) if gaps else 0.0
            if tick <= 0:
                return self.imbalance_levels(threshold, "same_price")     # one row: nothing diagonal
            by_price = {round(p / tick): lv for p, lv in rows}
            results: list[tuple[float, str]] = []
            for _index, (price, lv) in enumerate(rows):
                key = round(price / tick)
                below = by_price.get(key - 1)      # one tick down
                above = by_price.get(key + 1)      # one tick up
                bid_cmp = below.bid_volume if below is not None else self.levels[price].bid_volume
                ask_cmp = above.ask_volume if above is not None else lv.ask_volume
                if lv.ask_volume > 0 and (bid_cmp <= 0 or lv.ask_volume / max(bid_cmp, 1e-12) >= threshold):
                    results.append((price, "buy"))
                elif lv.bid_volume > 0 and (ask_cmp <= 0 or lv.bid_volume / max(ask_cmp, 1e-12) >= threshold):
                    results.append((price, "sell"))
            return results

        results = []
        for price, lv in rows:
            if lv.bid_volume > 0 and lv.ask_volume / lv.bid_volume >= threshold:
                results.append((price, "buy"))
            elif lv.ask_volume > 0 and lv.bid_volume / lv.ask_volume >= threshold:
                results.append((price, "sell"))
            elif lv.bid_volume == 0 and lv.ask_volume > 0:
                results.append((price, "buy"))
            elif lv.ask_volume == 0 and lv.bid_volume > 0:
                results.append((price, "sell"))
        return results

    def calculated_values(self, threshold: float = 3.0, mode: str = "same_price",
                          tick_size: float = 0.0) -> dict:
        """The per-bar numbers a footprint row is read for (see `analyse_levels`)."""
        rows = {price: (lv.bid_volume, lv.ask_volume) for price, lv in self.levels.items()}
        return analyse_levels(rows, tick_size=tick_size, threshold=threshold, mode=mode)

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


def analyse_levels(levels: "MappingLike", tick_size: float = 0.0, *, threshold: float = 3.0,
                   mode: str = "same_price", equal_tolerance: float = 0.0) -> dict:
    """The Numbers-Bars analysis pack over one bar's price rows.

    ``levels`` maps price → (bid_volume, ask_volume). Everything here is arithmetic over
    that mapping, so the same code serves the live pipeline, the stored history and the
    demo generator, and a unit test can pin each behaviour.

    Returns:
      ``volume``/``buy``/``sell``/``delta``  — the bar's totals (buy = aggressive buys, i.e.
                                               the ask side of the book, as in the rest of
                                               this codebase),
      ``poc``                                — price, volume and share of the bar at the
                                               highest-volume row,
      ``max_bid``/``max_ask``                — the heaviest sell-side and buy-side rows,
      ``extremes``                           — min/max rows by total volume,
      ``imbalances``                         — {price, side, ratio} rows for the chosen mode,
      ``imbalance_counts``                   — how many rows each side produced,
      ``equal``                              — rows where both sides are (near) equal,
      ``dominant``                           — "buy" | "sell" | "flat" for the whole bar.
    """
    rows = sorted((float(p), float(b or 0.0), float(a or 0.0)) for p, (b, a) in levels.items())
    total_bid = sum(b for _, b, _ in rows)
    total_ask = sum(a for _, _, a in rows)
    total = total_bid + total_ask
    out: dict = {
        "volume": round(total, 10),
        "buy": round(total_ask, 10),
        "sell": round(total_bid, 10),
        "delta": round(total_ask - total_bid, 10),
        "rows": len(rows),
        "poc": None,
        "max_bid": None,
        "max_ask": None,
        "extremes": {"max": None, "min": None},
        "imbalances": [],
        "imbalance_counts": {"buy": 0, "sell": 0},
        "equal": [],
        "dominant": "flat" if total == 0 else ("buy" if total_ask > total_bid else "sell"),
        "mode": mode,
        "threshold": float(threshold),
    }
    if not rows:
        return out

    by_volume = sorted(rows, key=lambda r: (r[1] + r[2], -r[0]))
    top = by_volume[-1]
    out["poc"] = {
        "price": top[0],
        "volume": round(top[1] + top[2], 10),
        "share_pct": round(((top[1] + top[2]) / total) * 100, 4) if total else 0.0,
        "delta": round(top[2] - top[1], 10),
    }
    out["max_bid"] = {"price": max(rows, key=lambda r: r[1])[0],
                      "volume": round(max(r[1] for r in rows), 10)}
    out["max_ask"] = {"price": max(rows, key=lambda r: r[2])[0],
                      "volume": round(max(r[2] for r in rows), 10)}
    lo, hi = by_volume[0], by_volume[-1]
    out["extremes"] = {
        "min": {"price": lo[0], "volume": round(lo[1] + lo[2], 10)},
        "max": {"price": hi[0], "volume": round(hi[1] + hi[2], 10)},
    }

    # imbalance, both conventions
    tick = float(tick_size or 0.0)
    if mode == "diagonal" and tick <= 0 and len(rows) > 1:
        gaps = [rows[i + 1][0] - rows[i][0] for i in range(len(rows) - 1) if rows[i + 1][0] != rows[i][0]]
        tick = min(gaps) if gaps else 0.0
    by_key = {round(p / tick): (b, a) for p, b, a in rows} if (mode == "diagonal" and tick > 0) else {}
    imbalances: list[dict] = []
    for price, bid, ask in rows:
        if mode == "diagonal" and by_key:
            key = round(price / tick)
            below = by_key.get(key - 1)
            above = by_key.get(key + 1)
            bid_cmp = below[0] if below is not None else bid
            ask_cmp = above[1] if above is not None else ask
        else:
            bid_cmp, ask_cmp = bid, ask
        if ask > 0 and (bid_cmp <= 0 or ask / max(bid_cmp, 1e-12) >= threshold):
            imbalances.append({"price": price, "side": "buy",
                               "ratio": round(ask / bid_cmp, 4) if bid_cmp > 0 else None})
        elif bid > 0 and (ask_cmp <= 0 or bid / max(ask_cmp, 1e-12) >= threshold):
            imbalances.append({"price": price, "side": "sell",
                               "ratio": round(bid / ask_cmp, 4) if ask_cmp > 0 else None})
    out["imbalances"] = imbalances
    out["imbalance_counts"] = {
        "buy": sum(1 for i in imbalances if i["side"] == "buy"),
        "sell": sum(1 for i in imbalances if i["side"] == "sell"),
    }

    tol = float(equal_tolerance or 0.0)
    if tol > 1e-9:
        # tolerance is relative to the row's own size, so it behaves the same on a
        # 0.0001-lot crypto row and a 100-lot futures row
        out["equal"] = [
            {"price": price, "bid": round(bid, 10), "ask": round(ask, 10)}
            for price, bid, ask in rows
            if (bid + ask) > 0 and abs(bid - ask) <= tol * (bid + ask)
        ]
    else:
        out["equal"] = [
            {"price": price, "bid": round(bid, 10), "ask": round(ask, 10)}
            for price, bid, ask in rows
            if bid > 0 and bid == ask
        ]
    return out


class FootprintEngine:
    """
    Builds and analyzes footprint data from ticks or candles.
    The footprint shows executed buy and sell orders at each price level,
    revealing aggression, absorption, and imbalance.
    """

    def __init__(self, tick_size: float = 0.1, min_print_size: float = 0.0):
        self.tick_size = tick_size
        #: Prints smaller than this are ignored while building a bar — the equivalent of
        #: the conventional "Volume Filtering" on Numbers Bars. 0 keeps every print. It filters at
        #: *aggregation* time (the honest place): a bar built without it cannot be
        #: un-filtered afterwards, and silently dropping rows at render time would make the
        #: bar's own totals lie.
        self.min_print_size = max(0.0, float(min_print_size or 0.0))
        self.filtered_prints = 0
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
        """Build footprint bar from raw ticks (after the print-size filter)."""
        if not ticks:
            return FootprintBar(timestamp_ms=timestamp_ms)

        levels: dict[float, FootprintLevel] = {}
        prices = []

        for t in ticks:
            if self.min_print_size and float(t.size or 0.0) < self.min_print_size:
                self.filtered_prints += 1
                continue
            rounded = round(round(t.price / self.tick_size) * self.tick_size, 10)
            prices.append(t.price)

            if rounded not in levels:
                levels[rounded] = FootprintLevel(price=rounded)

            if t.is_buy:
                levels[rounded].ask_volume += t.size
            else:
                levels[rounded].bid_volume += t.size

        if not prices:                      # every print was filtered out
            return FootprintBar(timestamp_ms=timestamp_ms or ticks[0].timestamp_ms)

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
