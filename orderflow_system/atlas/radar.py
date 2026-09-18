"""Level Radar (G1, fold-in plan §4) — the level lifecycle, one state machine over every level source.

Every level the app already computes can be registered here — unfinished-auction magnets, node
runs, virgin POCs, the weekly / monthly POC ladder, area-profile POCs, VWAP bands, stacked-
imbalance zones. From the moment it registers, price is stepped against it and the level moves
through states:

    armed → approaching → defended / confirmed → spent / failed

  * ``armed``       — registered; price is away from it.
  * ``approaching`` — price is inside the approach band (``approach_mult × tol``).
  * ``defended``    — a test held: price entered the test band (±``tol``) from one side and left
                      on that same side, without trading through.
  * ``confirmed``   — the same defense, on a level that two independent sources registered
                      (the confluence read). Confirmed is a defended level with corroboration.
  * ``spent``       — price traded through the level without it ever holding.
  * ``failed``      — a level that held at least once, then was traded through — the course's
                      "second test breaks" outcome, kept distinct from spent for exactly that
                      reason.

``spent`` and ``failed`` are terminal: the level stops stepping, stays visible for
``spent_keep_ms`` (so the UI can dim-and-label it) and then drops. Live levels older than
``max_age_ms`` expire silently.

Conventions, all pinned in ``test_radar.py``:

  * One band in price units: ``tol`` = ``tol_ticks × tick_size`` (callers may pass an explicit
    tol — the area-profile rules pass their own). A level with no known tick still gets a hair
    of band (``price × 1e-6``) rather than exact-equality games.
  * ``approaching`` begins at ``|price − level| ≤ approach_mult × tol`` and the state falls
    back to ``armed``, silently, once price is outside that band again (no event: ``armed`` is
    where levels start, not a transition users watch).
  * A test starts the moment price is inside ±tol from outside it; the side it entered from is
    recorded. The test ends when price leaves ±tol:
      - leaving on the entry side        → the level held (touch counted, ``defended``);
      - leaving on the far side         → terminal: ``failed`` if it had ever held, else ``spent``.
  * Crossing without lingering (a jump straight from one side beyond the far edge — one bar in
    candle mode) spends the level the same way, test or no test.
  * Events are emitted for: registration (``armed``), ``approaching``, ``defended``,
    ``confirmed``, ``spent``, ``failed`` — each as a plain dict the hub dispatches like any
    other detection, so alert rules and the history see radar transitions identically.

The tracker is pure: ``(price, ts)`` in, events out; no I/O, no imports beyond the stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

#: The states, in lifecycle order. ``spent`` / ``failed`` are terminal.
STATES = ("armed", "approaching", "defended", "confirmed", "spent", "failed")
TERMINAL = ("spent", "failed")


@dataclass
class RadarLevel:
    """One tracked level. Prices in the instrument's own units; timestamps in ms."""

    id: str
    symbol: str
    price: float
    source: str
    tol: float
    strength: float
    created_ms: int
    sources: list[str] = field(default_factory=list)
    state: str = "armed"
    state_ms: int = 0
    touches: int = 0
    defenses: int = 0
    test_side: str = ""            # '' | 'above' | 'below' — the side the running test entered from
    side: str = ""                 # 'above' | 'below' | 'at' — price side at registration
    last_price: float = 0.0

    @property
    def live(self) -> bool:
        return self.state not in TERMINAL

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "symbol": self.symbol, "price": self.price,
                "source": self.source, "sources": list(self.sources), "tol": self.tol,
                "strength": self.strength, "created_ms": self.created_ms,
                "state": self.state, "state_ms": self.state_ms,
                "touches": self.touches, "defenses": self.defenses,
                "first_test": (self.touches == 1 and self.defenses == 1),
                "side": self.side, "last_price": self.last_price, "live": self.live}


class RadarTracker:
    """One instrument's radar book. Pure: (price, ts) in, transitions out."""

    def __init__(
        self,
        symbol: str = "",
        tick_size: float = 0.0,
        enabled: bool = True,
        tol_ticks: float = 2.0,
        approach_mult: float = 2.5,
        max_age_ms: int = 4 * 3_600_000,
        spent_keep_ms: int = 30 * 60_000,
        max_levels: int = 400,
    ) -> None:
        self.symbol = str(symbol or "")
        self.tick_size = max(0.0, float(tick_size or 0.0))
        self.enabled = bool(enabled)
        self.tol_ticks = max(0.0, float(tol_ticks))
        self.approach_mult = max(1.0, float(approach_mult))
        self.max_age_ms = max(60_000, int(max_age_ms))
        self.spent_keep_ms = max(0, int(spent_keep_ms))
        self.max_levels = max(10, int(max_levels))
        self.levels: list[RadarLevel] = []
        self._seq = 0

    # ── registration ─────────────────────────────────────────────

    def register(
        self,
        price: Any,
        source: str,
        ts_ms: int,
        strength: float = 50.0,
        tol: Optional[float] = None,
        ref_price: Optional[float] = None,
    ) -> tuple[Optional[RadarLevel], bool]:
        """Register a level, or merge it into a nearby live one. Returns ``(level, is_new)``.

        Merge rule: a new registration within half the tighter of the two tolerances of an
        existing live level joins it — its source is appended once (the confluence count) and
        its strength raises the level's. Merged registrations are not new, so they emit nothing.
        """
        if not self.enabled:
            return None, False
        try:
            px = float(price)
        except (TypeError, ValueError):
            return None, False
        if not (px > 0):
            return None, False
        tick = max(0.0, float(self.tick_size or 0.0))
        if tol is None:
            tol_f = tick * self.tol_ticks
        else:
            try:
                tol_f = float(tol)
            except (TypeError, ValueError):
                tol_f = tick * self.tol_ticks
        if tol_f <= 0:
            tol_f = max(abs(px), 1.0) * 1e-6      # a hair of band, never exact-equality games
        src = str(source or "level")

        for lv in self.levels:
            if not lv.live:
                continue
            if abs(lv.price - px) <= 0.5 * min(lv.tol, tol_f) + 1e-12:
                if src not in lv.sources:
                    lv.sources.append(src)
                lv.strength = max(lv.strength, float(strength))
                return lv, False

        self._seq += 1
        ref = float(ref_price) if ref_price else 0.0
        side = "above" if ref > px else ("below" if 0 < ref < px else "at")
        lvl = RadarLevel(id=f"{self.symbol}:{src}:{self._seq}", symbol=self.symbol, price=px,
                         source=src, sources=[src], tol=tol_f, strength=float(strength),
                         created_ms=int(ts_ms), state_ms=int(ts_ms), side=side)
        self.levels.append(lvl)
        if len(self.levels) > self.max_levels:
            drop = next((l for l in self.levels if not l.live), None) or self.levels[0]
            self.levels.remove(drop)
        return lvl, True

    # ── stepping ─────────────────────────────────────────────────

    def step(self, price: Any, ts_ms: int) -> list[dict[str, Any]]:
        """Step every live level against one price. Returns the transitions as event dicts."""
        try:
            px = float(price)
        except (TypeError, ValueError):
            return []
        ts = int(ts_ms)
        events: list[dict[str, Any]] = []
        for lv in self.levels:
            if not lv.live:
                continue
            lv.last_price = px
            d = px - lv.price
            ad = abs(d)
            band = lv.tol * self.approach_mult
            inside = ad <= lv.tol
            here_side = "inside" if inside else ("above" if d > 0 else "below")

            if lv.test_side:
                # a test is running — it ends the moment price leaves ±tol
                if here_side == "inside":
                    continue
                lv.touches += 1
                if here_side == lv.test_side:
                    lv.defenses += 1
                    new_state = "confirmed" if len(lv.sources) >= 2 else "defended"
                else:
                    new_state = "failed" if lv.defenses >= 1 else "spent"
                lv.test_side = ""
                events.append(self._transition(lv, new_state, ts, px))
                continue

            if inside:
                # start a test from the side price came from (an exact touch counts as 'above')
                lv.test_side = "above" if d >= 0 else "below"
                if lv.state == "armed":
                    events.append(self._transition(lv, "approaching", ts, px))
                continue

            # no test running: big-jump crossing spends / fails the level
            crossed = (lv.side == "above" and here_side == "below") or \
                      (lv.side == "below" and here_side == "above")
            if crossed:
                new_state = "failed" if lv.defenses >= 1 else "spent"
                events.append(self._transition(lv, new_state, ts, px))
                continue

            if lv.state == "armed" and ad <= band:
                events.append(self._transition(lv, "approaching", ts, px))
            elif lv.state == "approaching" and ad > band:
                lv.state = "armed"                     # falls back silently (documented)
                lv.state_ms = ts

        self._prune(ts)
        return events

    def _transition(self, lv: RadarLevel, new_state: str, ts: int, px: float) -> dict[str, Any]:
        lv.state = new_state
        lv.state_ms = ts
        return {
            "kind": "radar_level", "state": new_state, "price": lv.price, "source": lv.source,
            "sources": list(lv.sources), "tol": lv.tol, "side": lv.side,
            "strength": lv.strength, "id": lv.id, "symbol": lv.symbol,
            "touches": lv.touches, "defenses": lv.defenses,
            "first_test": (lv.touches == 1 and lv.defenses == 1),
            "last": px, "age_ms": ts - lv.created_ms, "ts_ms": ts,
        }

    def _prune(self, ts: int) -> None:
        keep: list[RadarLevel] = []
        for lv in self.levels:
            if lv.state in TERMINAL:
                if self.spent_keep_ms and ts - lv.state_ms > self.spent_keep_ms:
                    continue
            elif ts - lv.created_ms > self.max_age_ms:
                continue
            keep.append(lv)
        self.levels = keep

    # ── reads ────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Counts per state + the stated arming-pressure score for ranking tables."""
        counts = {s: 0 for s in STATES}
        for lv in self.levels:
            counts[lv.state] += 1
        live = counts["armed"] + counts["approaching"] + counts["defended"] + counts["confirmed"]
        # Stated heuristic, in the scanner's own spirit: approaching ×1 + defended ×2 +
        # confirmed ×3, capped at 6 — kept small so a busy instrument cannot dominate silently.
        pressure = (counts["approaching"] + 2 * counts["defended"] + 3 * counts["confirmed"])
        note = (f"{counts['armed']} armed · {counts['approaching']} approaching · "
                f"{counts['defended'] + counts['confirmed']} held")
        return {**counts, "live": live, "score": round(100.0 * min(1.0, pressure / 6.0), 1),
                "note": note}

    def snapshot(self) -> dict[str, Any]:
        """The tracker's state: counts + levels (live first, strongest first, price as tiebreak)."""
        return {"symbol": self.symbol, "counts": self.summary(),
                "levels": [lv.to_dict() for lv in
                           sorted(self.levels, key=lambda l: (not l.live, -l.strength, l.price))]}

    def clear(self) -> None:
        self.levels = []
        self._seq = 0
