"""
Market Profile / TPO (the reference layout "Market Profile") and volume-profile extensions.

Market Profile builds a TPO (time price opportunity) histogram: each 30-minute
bracket gets a letter, every price traded during that bracket gets that letter.
From it traders read the POC, value area, initial balance (IB), range extension,
single prints and day extremes — all computed here.

The volume-profile extensions (developing value area, virgin/naked POC, session
vs range profiles, profile shape) complement the repo's ``VolumeProfileEngine``;
this module does not duplicate it, it adds the reads that engine lacks.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Optional

from orderflow_system.data.models import Tick


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class Bracket:
    index: int
    letter: str
    ts_ms: int
    prices: set[float] = field(default_factory=set)
    volume: float = 0.0
    high: float = 0.0
    low: float = 0.0

    @property
    def range_ticks(self) -> float:
        return self.high - self.low


class MarketProfile:
    """TPO profile for one instrument and one session."""

    def __init__(
        self,
        symbol: str,
        tick_size: float = 1.0,
        bracket_seconds: int = 1800,
        value_area_pct: float = 0.70,
        max_brackets: int = 26,
        session_start_ms: Optional[int] = None,
    ) -> None:
        self.symbol = symbol
        self.tick_size = max(float(tick_size), 1e-9)
        self.bracket_ms = int(bracket_seconds * 1000)
        self.value_area_pct = float(value_area_pct)
        self.max_brackets = int(max_brackets)
        self.session_start_ms = session_start_ms
        self.brackets: list[Bracket] = []
        self._tpo: dict[float, list[int]] = {}          # price -> bracket indexes
        self._volume: dict[float, float] = {}
        self._counts: dict[float, int] = {}
        self.session_high = 0.0
        self.session_low = 0.0
        self.session_open = 0.0
        self.session_ticks = 0

    # ── ingest ────────────────────────────────────────────────
    def on_tick(self, tick: Tick) -> None:
        ts = int(tick.timestamp_ms or time.time() * 1000)
        if self.session_start_ms is None:
            self.session_start_ms = ts
            self.session_open = float(tick.price)
        if not self.session_open:
            self.session_open = float(tick.price)

        price = self._bucket(tick.price)
        self._counts[price] = self._counts.get(price, 0) + 1
        bracket = self._bracket(ts)
        bracket.prices.add(price)
        bracket.volume += float(tick.size)
        bracket.high = max(bracket.high or float(tick.price), float(tick.price))
        bracket.low = min(bracket.low or float(tick.price), float(tick.price))

        self._tpo.setdefault(price, [])
        if bracket.index not in self._tpo[price]:
            self._tpo[price].append(bracket.index)
        self._volume[price] = self._volume.get(price, 0.0) + float(tick.size)
        self.session_high = max(self.session_high or float(tick.price), float(tick.price))
        self.session_low = min(self.session_low or float(tick.price), float(tick.price))
        self.session_ticks += 1

    def _bucket(self, price: float) -> float:
        return round(round(float(price) / self.tick_size) * self.tick_size, 10)

    def _bracket(self, ts_ms: int) -> Bracket:
        assert self.session_start_ms is not None
        idx = int((ts_ms - self.session_start_ms) // self.bracket_ms)
        if idx >= self.max_brackets:
            idx = self.max_brackets - 1
        while len(self.brackets) <= idx:
            i = len(self.brackets)
            self.brackets.append(Bracket(index=i, letter=LETTERS[i % 26], ts_ms=self.session_start_ms + i * self.bracket_ms))
        return self.brackets[idx]

    # ── derived reads ─────────────────────────────────────────
    def levels(self) -> list[dict[str, Any]]:
        rows = []
        for price in sorted(self._tpo, reverse=True):
            idxs = self._tpo[price]
            rows.append({
                "price": price,
                "letters": "".join(LETTERS[i % 26] for i in sorted(set(idxs))),
                "tpo": len(set(idxs)),
                "volume": round(self._volume.get(price, 0.0), 6),
            })
        return rows

    def tick_profile(self, max_levels: int = 160) -> list[dict[str, Any]]:
        """Profile by number of trades rather than volume — pure activity (the reference platform's
        Tick Profile): a level can be quiet in size and busy in prints, and vice versa."""
        rows = [{"price": price, "trades": count}
                for price, count in sorted(self._counts.items(), reverse=True)]
        if len(rows) > max_levels:
            rows.sort(key=lambda r: -r["trades"])
            rows = sorted(rows[:max_levels], key=lambda r: -r["price"])
        return rows

    def poc(self) -> float:
        """Point of control — the price with the most TPOs (ties → highest volume)."""
        if not self._tpo:
            return 0.0
        best = max(self._tpo.items(), key=lambda kv: (len(set(kv[1])), self._volume.get(kv[0], 0.0)))
        return best[0]

    def value_area(self, pct: Optional[float] = None) -> tuple[float, float, float]:
        """Value area (default 70% of TPOs) expanded from the POC. Returns (poc, vah, val)."""
        pct = pct or self.value_area_pct
        poc = self.poc()
        if not poc:
            return 0.0, 0.0, 0.0
        ordered = sorted(self._tpo)
        if len(ordered) < 2:
            return poc, poc, poc
        counts = {p: len(set(self._tpo[p])) for p in ordered}
        total = sum(counts.values())
        target = total * pct
        i = ordered.index(poc)
        lo = hi = i
        acc = counts[poc]
        while acc < target and (lo > 0 or hi < len(ordered) - 1):
            up = counts[ordered[hi + 1]] if hi < len(ordered) - 1 else -1
            down = counts[ordered[lo - 1]] if lo > 0 else -1
            if up >= down:
                hi += 1
                acc += max(up, 0)
            else:
                lo -= 1
                acc += max(down, 0)
        return poc, ordered[hi], ordered[lo]

    def initial_balance(self) -> dict[str, float]:
        """IB = range of the first two brackets (the opening auction)."""
        first = [b for b in self.brackets if b.index < 2 and b.high > 0]
        if not first:
            return {}
        return {"ib_high": max(b.high for b in first), "ib_low": min(b.low for b in first)}

    def range_extension(self) -> dict[str, Any]:
        ib = self.initial_balance()
        if not ib:
            return {}
        ext_up = self.session_high - ib["ib_high"]
        ext_dn = ib["ib_low"] - self.session_low
        return {
            "extension_up_ticks": round(max(0.0, ext_up) / self.tick_size, 2),
            "extension_down_ticks": round(max(0.0, ext_dn) / self.tick_size, 2),
            "extended": bool(ext_up > 0 or ext_dn > 0),
        }

    def single_prints(self) -> list[float]:
        """Prices touched by exactly one bracket (unfinished business / magnets)."""
        return [p for p, idxs in self._tpo.items() if len(set(idxs)) == 1]

    def snapshot(self, max_levels: int = 160) -> dict[str, Any]:
        poc, vah, val = self.value_area()
        levels = self.levels()
        if len(levels) > max_levels:
            centre = poc or levels[len(levels) // 2]["price"]
            levels.sort(key=lambda r: abs(r["price"] - centre))
            levels = sorted(levels[:max_levels], key=lambda r: -r["price"])
        return {
            "symbol": self.symbol,
            "tick": self.tick_size,
            "session_start_ms": self.session_start_ms,
            "brackets": [{"letter": b.letter, "ts_ms": b.ts_ms, "high": b.high, "low": b.low, "volume": round(b.volume, 6)} for b in self.brackets],
            "levels": levels,
            "poc": poc,
            "vah": vah,
            "val": val,
            "ib": self.initial_balance(),
            "range_extension": self.range_extension(),
            "single_prints": self.single_prints()[:40],
            "tick_profile": self.tick_profile(max_levels),
            "session": {"open": self.session_open, "high": self.session_high, "low": self.session_low, "ticks": self.session_ticks},
        }

    def clear(self) -> None:
        self.brackets.clear()
        self._tpo.clear()
        self._volume.clear()
        self._counts.clear()
        self.session_high = self.session_low = self.session_open = 0.0
        self.session_ticks = 0
        self.session_start_ms = None


# ── volume-profile extensions ───────────────────────────────────────────────

def developing_value_area(profiles: Iterable[Any]) -> dict[str, Any]:
    """Developing VA drift across sessions (the reference layout 'Developing Value Area').

    ``profiles`` is any iterable of profile results carrying ``poc``/``vah``/``val``
    and a session marker — e.g. the repo's ``VolumeProfileResult``.
    """
    rows = []
    for p in profiles:
        rows.append({
            "session": getattr(p, "session_date", ""),
            "poc": getattr(p, "poc", 0.0),
            "vah": getattr(p, "vah", 0.0),
            "val": getattr(p, "val", 0.0),
        })
    if len(rows) < 2:
        return {"sessions": rows, "trend": "flat", "drift_ticks": 0.0}
    poc_now, poc_prev = rows[-1]["poc"], rows[0]["poc"]
    drift = poc_now - poc_prev
    trend = "higher" if drift > 0 else "lower" if drift < 0 else "flat"
    return {"sessions": rows, "trend": trend, "drift": drift,
            "va_overlap": rows[-1]["vah"] - rows[-2]["val"] if len(rows) > 1 else 0.0}


def virgin_pocs(profiles: Iterable[Any], current_price: float = 0.0) -> list[dict[str, Any]]:
    """Untested POCs from *closed* sessions — the classic magnets.

    A POC is 'virgin' when no later session traded through it. The newest session
    is excluded: its POC cannot have been tested yet by definition.
    """
    ordered = list(profiles)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(ordered[:-1]):
        poc = getattr(p, "poc", 0.0)
        if not poc:
            continue
        later = ordered[i + 1:]
        tested = False
        for q in later:
            hi = max(getattr(q, "vah", 0.0), getattr(q, "poc", 0.0))
            lo = min(getattr(q, "val", 0.0), getattr(q, "poc", 0.0))
            if lo <= poc <= hi:
                tested = True
                break
        if not tested:
            out.append({"session": getattr(p, "session_date", ""), "poc": poc,
                        "distance": round(poc - current_price, 6) if current_price else 0.0})
    return out


# ── HTF POC ladder: aggregate stored sessions into period POCs ────────────────

def _period_key(day: "date", period: str) -> str:
    """ISO week ('2026-W38') or calendar month ('2026-09')."""
    if period == "month":
        return f"{day.year:04d}-{day.month:02d}"
    year, week, _ = day.isocalendar()
    return f"{year:04d}-W{week:02d}"


def _aggregate_value_area(prices: list[float], volumes: list[float], poc_idx: int,
                          value_area_pct: float) -> tuple[float, float]:
    """The engine's own expansion rule (grow from the POC toward the heavier side)."""
    total = math.fsum(volumes)
    if total <= 0:
        return prices[poc_idx], prices[poc_idx]
    target = total * value_area_pct
    accumulated = volumes[poc_idx]
    lo = hi = poc_idx
    while accumulated < target:
        up = volumes[hi + 1] if hi + 1 < len(prices) else -1.0
        down = volumes[lo - 1] if lo - 1 >= 0 else -1.0
        if up < 0 and down < 0:
            break
        if up >= down:
            hi += 1
            accumulated += up
        else:
            lo -= 1
            accumulated += down
    return prices[hi], prices[lo]


def period_pocs(profiles: Iterable[Any], period: str = "week",
                value_area_pct: float = 0.68) -> list[dict[str, Any]]:
    """Aggregate stored session profiles into period POCs (week = ISO week, or month).

    Each session's ``volume_at_price`` map is summed per price, and the POC / value area are
    recomputed on the aggregate with the engine's own expansion rule — a weekly POC here is the
    week's genuine volume mode, not a vote between daily POCs. Sessions whose ``session_date``
    cannot be parsed, or which carry no per-price volumes, are excluded; the result's
    ``sessions`` list names exactly what went into each period. Oldest period first, as
    ``{period, kind, sessions, poc, vah, val, total_volume}``.
    """
    groups: dict[str, dict[str, Any]] = {}
    for p in profiles:
        raw = str(getattr(p, "session_date", "") or "")
        try:
            day = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        vap = getattr(p, "volume_at_price", None) or {}
        if not vap:
            continue
        g = groups.setdefault(_period_key(day, period), {"levels": {}, "sessions": []})
        for price, vol in vap.items():
            key = float(price)
            g["levels"][key] = g["levels"].get(key, 0.0) + float(vol or 0.0)
        g["sessions"].append(day.isoformat())

    out: list[dict[str, Any]] = []
    for key in sorted(groups):
        g = groups[key]
        levels = g["levels"]
        if not levels:
            continue
        prices = sorted(levels)
        volumes = [levels[p] for p in prices]
        total = math.fsum(volumes)
        if total <= 0:
            continue
        poc_idx = max(range(len(prices)), key=lambda i: volumes[i])
        vah, val = _aggregate_value_area(prices, volumes, poc_idx, value_area_pct)
        out.append({
            "period": key,
            "kind": period,
            "sessions": list(g["sessions"]),
            "poc": prices[poc_idx],
            "vah": vah,
            "val": val,
            "total_volume": round(total, 8),
        })
    return out
