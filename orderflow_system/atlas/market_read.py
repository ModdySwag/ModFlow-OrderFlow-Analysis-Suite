
"""
Deterministic market read engine — regime classification, composite scoring,
key levels, confluence.

Pure computation: given a structured snapshot of market state (tape, footprint,
heatmap, radar, volume profile, VWAP), it returns a deterministic "read" with
regime, score, levels, and confluence points.

This is the FALLBACK engine for the AI copilot (§7.7): when no LLM key is
configured, the copilot panel renders this read. When an LLM key IS configured,
this read is serialized as context for the LLM.

No network, no config, no UI — a pure function of a state snapshot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


# ── input snapshot shape ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TapeSnapshot:
    """Recent tape state."""
    direction: str = "neutral"        # "up" | "down" | "neutral"
    delta: float = 0.0                # cumulative delta over the window
    volume: float = 0.0               # total volume over the window
    big_prints: int = 0               # prints above big_quantile
    sweeps: int = 0                   # sweep events detected
    timestamp_ms: int = 0


@dataclass(frozen=True)
class FootprintSnapshot:
    """Footprint matrix summary."""
    imbalances_buy: int = 0           # 2:1+ buy imbalances
    imbalances_sell: int = 0          # 2:1+ sell imbalances
    absorption_buy: int = 0           # absorption at levels (buy side holding)
    absorption_sell: int = 0          # absorption at levels (sell side holding)
    delta_slope: float = 0.0          # delta trend: positive = buying pressure
    delta_slope_ticks: int = 0        # ticks over which delta_slope was measured
    poc_price: Optional[float] = None # point of control


@dataclass(frozen=True)
class HeatmapSnapshot:
    """Heatmap / liquidity map state."""
    walls_above: int = 0              # resting walls above price
    walls_below: int = 0              # resting walls below price
    wall_refills: int = 0             # walls that refilled after being hit
    wall_pulls: int = 0               # walls that pulled before being hit
    absorption_zones: int = 0         # zones where absorption was detected
    pinned_levels: int = 0            # user-pinned levels


@dataclass(frozen=True)
class RadarSnapshot:
    """Radar / level lifecycle state."""
    armed_levels: int = 0             # levels armed and waiting
    approaching_levels: int = 0       # levels price is approaching
    held_levels: int = 0              # levels price has held (defended/confirmed)
    spent_levels: int = 0             # levels that were broken
    #: The tracker's own levels (``{price, state, strength, live, …}``) when the caller has them.
    #: With these in hand the read quotes the real prices the radar is tracking; without them it
    #: keeps the count-anchored placeholders it shipped with, so a caller that only has counts
    #: still gets a read. The scoring reads the counts either way.
    levels: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class VolumeProfileSnapshot:
    """Volume profile state."""
    poc: Optional[float] = None       # point of control
    vah: Optional[float] = None       # value area high
    val: Optional[float] = None       # value area low
    poc_volume_pct: float = 0.0       # POC as % of total volume


@dataclass(frozen=True)
class VWAPSnapshot:
    """VWAP state."""
    price: Optional[float] = None     # current VWAP
    deviation: Optional[float] = None # price - VWAP (in ticks or $)
    deviation_ticks: Optional[float] = None


@dataclass
class MarketState:
    """Everything the market read engine needs — a point-in-time snapshot."""
    symbol: str = ""
    spot: float = 0.0
    tape: TapeSnapshot = field(default_factory=TapeSnapshot)
    footprint: FootprintSnapshot = field(default_factory=FootprintSnapshot)
    heatmap: HeatmapSnapshot = field(default_factory=HeatmapSnapshot)
    radar: RadarSnapshot = field(default_factory=RadarSnapshot)
    profile: VolumeProfileSnapshot = field(default_factory=VolumeProfileSnapshot)
    vwap: VWAPSnapshot = field(default_factory=VWAPSnapshot)
    timestamp_ms: int = 0


# ── output shape ────────────────────────────────────────────────────────────────

@dataclass
class Regime:
    name: str                         # "trending_up" | "trending_down" | "ranging" | "choppy"
    buyer_led: bool                   # buyers initiating more than sellers
    seller_led: bool                  # sellers initiating more than buyers
    absorbing: bool                   # absorption dominates (price stuck at level)
    absorbing_side: Optional[str]     # "buy" | "sell" | None
    description: str                  # plain-language regime description


@dataclass
class KeyLevel:
    price: float
    kind: str                         # "poc" | "vah" | "val" | "radar_armed" | "radar_held" |
                                      # "round_number" | "overnight_high" | "overnight_low" |
                                      # "wall_above" | "wall_below"
    source: str                       # which signal nominated this level
    strength: float                   # 0..1, how strong the confluence is
    notes: str = ""


@dataclass
class ConfluencePoint:
    price: float
    signals: list[str]               # which signals agree at this price
    strength: float                   # how many signals / how strong


@dataclass
class MarketRead:
    regime: Regime
    composite_score: float            # 0..100, overall conviction
    score_breakdown: dict[str, float] # per-signal scores
    key_levels: list[KeyLevel]        # all notable levels, sorted by strength
    confluence_points: list[ConfluencePoint]  # where multiple signals agree
    summary: str                      # plain-language 2-3 sentence read
    timestamp_ms: int
    n_levels: int
    n_confluence: int


# ── pure helpers ────────────────────────────────────────────────────────────────

def _finite(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _round_price(price: float, tick_size: float = 0.25) -> float:
    """Round to the nearest tick for display."""
    if tick_size <= 0:
        return round(price, 2)
    return round(round(price / tick_size) * tick_size, 6)


def _round_number(price: float) -> bool:
    """Is this price near a round number (within 0.5 tick of a whole/half)?"""
    return abs(price - round(price)) < 0.01 or abs(price - round(price * 2) / 2) < 0.01


# ── regime classification ───────────────────────────────────────────────────────

def classify_regime(state: MarketState) -> Regime:
    """Classify the current regime from tape + footprint signals."""
    tape = state.tape
    fp = state.footprint

    # Absorption: lots of imbalances but price not moving.
    imbalance_total = fp.imbalances_buy + fp.imbalances_sell
    absorbing = (imbalance_total > 3 and tape.direction == "neutral") or (
        imbalance_total > 5 and abs(fp.delta_slope) < 0.1
    )

    # Trending: clear direction + delta slope + volume.
    trending_up = (tape.direction == "up" and fp.delta_slope > 0.15 and tape.volume > 0)
    trending_down = (tape.direction == "down" and fp.delta_slope < -0.15 and tape.volume > 0)

    # Choppy: lots of big prints and sweeps but no clear direction.
    choppy = tape.big_prints > 5 and tape.sweeps > 2 and not trending_up and not trending_down

    if trending_up:
        return Regime(
            name="trending_up",
            buyer_led=True, seller_led=False, absorbing=False, absorbing_side=None,
            description="Buyers are in control — delta positive, footprint slope up, volume supporting.",
        )
    if trending_down:
        return Regime(
            name="trending_down",
            buyer_led=False, seller_led=True, absorbing=False, absorbing_side=None,
            description="Sellers are in control — delta negative, footprint slope down, volume supporting.",
        )
    if absorbing and imbalance_total > 0:
        side = "buy" if fp.absorption_buy > fp.absorption_sell else "sell"
        return Regime(
            name="absorbing",
            buyer_led=False, seller_led=False, absorbing=True, absorbing_side=side,
            description=f"Absorption at work — {imbalance_total} imbalances with price stuck, "
                        f"large orders eating through the {side} side.",
        )
    if choppy:
        return Regime(
            name="choppy",
            buyer_led=False, seller_led=False, absorbing=False, absorbing_side=None,
            description="Choppy — big prints and sweeps with no clear direction. Expect whipsaws.",
        )
    return Regime(
        name="ranging",
        buyer_led=False, seller_led=False, absorbing=False, absorbing_side=None,
        description="Ranging — no clear trend, price oscillating between levels.",
    )


# ── composite scoring ───────────────────────────────────────────────────────────

def compute_score(state: MarketState, regime: Regime) -> tuple[float, dict[str, float]]:
    """0..100 composite conviction score + per-signal breakdown.

    Signals (each 0..100, then weighted):
      - trend: direction clarity + delta slope + volume
      - imbalance: count and ratio of buy/sell imbalances
      - absorption: absorption events and their sides
      - liquidity: walls, refills, pulls
      - levels: radar levels approaching/held
      - profile: POC sharpness, value area position
      - vwap: deviation from VWAP
    """
    tape = state.tape
    fp = state.footprint
    hm = state.heatmap
    radar = state.radar
    profile = state.profile
    vwap = state.vwap

    # Trend score: direction + delta slope + volume confirmation.
    trend = 50.0
    if tape.direction == "up":
        trend += min(25.0, abs(fp.delta_slope) * 100)
    elif tape.direction == "down":
        trend += min(25.0, abs(fp.delta_slope) * 100)
    if tape.volume > 0:
        trend += min(15.0, tape.volume / max(1.0, tape.volume) * 15)
    trend = min(100.0, trend)

    # Imbalance score.
    imb = min(100.0, (fp.imbalances_buy + fp.imbalances_sell) * 12.0)
    if fp.imbalances_buy > fp.imbalances_sell * 1.5:
        imb += 10.0  # buyer imbalance dominance
    elif fp.imbalances_sell > fp.imbalances_buy * 1.5:
        imb += 10.0  # seller imbalance dominance
    imb = min(100.0, imb)

    # Absorption score.
    abs_score = min(100.0, (fp.absorption_buy + fp.absorption_sell) * 20.0)

    # Liquidity score: walls + refills - pulls.
    liq = min(100.0, (hm.walls_above + hm.walls_below) * 10.0
              + hm.wall_refills * 15.0
              - hm.wall_pulls * 8.0)
    liq = max(0.0, min(100.0, liq))

    # Levels score: radar levels approaching/held.
    levels = min(100.0, (radar.approaching_levels + radar.held_levels) * 20.0)

    # Profile score: POC sharpness.
    prof = min(100.0, profile.poc_volume_pct * 100) if profile.poc_volume_pct > 0 else 50.0

    # VWAP score: deviation from VWAP (closer = higher score when trending, further = signal when ranging).
    vwap_score = 50.0
    if vwap.deviation is not None and vwap.deviation_ticks is not None:
        if regime.name in ("trending_up", "trending_down"):
            vwap_score = min(100.0, 50.0 + abs(vwap.deviation_ticks) * 2)
        else:
            vwap_score = max(0.0, 50.0 - abs(vwap.deviation_ticks) * 5)
    vwap_score = max(0.0, min(100.0, vwap_score))

    # Weighted composite.
    weights = {
        "trend": 0.25,
        "imbalance": 0.20,
        "absorption": 0.15,
        "liquidity": 0.15,
        "levels": 0.15,
        "profile": 0.05,
        "vwap": 0.05,
    }
    composite = sum(weights[k] * v for k, v in [
        ("trend", trend), ("imbalance", imb), ("absorption", abs_score),
        ("liquidity", liq), ("levels", levels), ("profile", prof), ("vwap", vwap_score),
    ])

    breakdown = {
        "trend": round(trend, 1),
        "imbalance": round(imb, 1),
        "absorption": round(abs_score, 1),
        "liquidity": round(liq, 1),
        "levels": round(levels, 1),
        "profile": round(prof, 1),
        "vwap": round(vwap_score, 1),
    }

    return round(min(100.0, max(0.0, composite)), 1), breakdown


# ── key levels ──────────────────────────────────────────────────────────────────

def extract_levels(state: MarketState) -> list[KeyLevel]:
    """All notable price levels from every signal, ranked by strength."""
    levels: list[KeyLevel] = []
    seen: set[float] = set()
    spot = state.spot

    def add(price: float, kind: str, source: str, strength: float, notes: str = "") -> None:
        if price <= 0:
            return
        r = _round_price(price)
        if r in seen:
            return
        seen.add(r)
        levels.append(KeyLevel(price=r, kind=kind, source=source,
                               strength=min(1.0, max(0.0, strength)), notes=notes))

    # Volume profile levels.
    if state.profile.poc is not None:
        add(state.profile.poc, "poc", "volume_profile",
            strength=0.9, notes="Point of Control")
    if state.profile.vah is not None:
        add(state.profile.vah, "vah", "volume_profile",
            strength=0.6, notes="Value Area High")
    if state.profile.val is not None:
        add(state.profile.val, "val", "volume_profile",
            strength=0.6, notes="Value Area Low")

    # Radar levels. The tracker's own rows carry the real price of every level it is watching, so
    # they are preferred over the count-anchored placeholders below (which stay for callers that
    # only hold counts — the scoring path reads the counts either way).
    radar_rows = [row for row in state.radar.levels if isinstance(row, dict)]
    if radar_rows:
        for row in radar_rows:
            price = _finite(row.get("price"))
            if price is None or price <= 0:
                continue
            state_name = str(row.get("state") or "")
            if state_name in ("defended", "confirmed"):
                add(price, "radar_held", "radar", 0.9, f"Level {state_name}")
            elif state_name == "armed":
                add(price, "radar_armed", "radar", 0.7, "Armed level (pending)")
            elif state_name == "approaching":
                add(price, "radar_approaching", "radar", 0.8, "Level price is approaching")
    else:
        for _ in range(state.radar.armed_levels):
            add(spot * (1.0 + 0.001 * (len(levels) + 1)), "radar_armed", "radar",
                strength=0.7, notes="Armed level (pending)")
        for _ in range(state.radar.approaching_levels):
            add(spot * (1.0 + 0.0005 * (len(levels) + 1)), "radar_approaching", "radar",
                strength=0.8, notes="Level price is approaching")
        for _ in range(state.radar.held_levels):
            add(spot * (1.0 + 0.0002 * (len(levels) + 1)), "radar_held", "radar",
                strength=0.9, notes="Price has held this level")

    # Heatmap walls.
    if state.heatmap.walls_above > 0:
        add(spot * 1.005, "wall_above", "heatmap",
            strength=0.7, notes=f"{state.heatmap.walls_above} resting walls above")
    if state.heatmap.walls_below > 0:
        add(spot * 0.995, "wall_below", "heatmap",
            strength=0.7, notes=f"{state.heatmap.walls_below} resting walls below")

    # VWAP.
    if state.vwap.price is not None:
        add(state.vwap.price, "vwap", "vwap",
            strength=0.5, notes=f"VWAP (deviation: {state.vwap.deviation:.2f})"
            if state.vwap.deviation is not None else "VWAP")

    # Round numbers near spot.
    for mult in [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0]:
        rn = round(spot / mult) * mult
        if rn > 0 and abs(rn - spot) < spot * 0.05:  # within 5% of spot
            add(rn, "round_number", "round_number", strength=0.3,
                notes=f"Round number ({mult}×)")

    # Sort by strength descending.
    levels.sort(key=lambda l: (-l.strength, l.price))
    return levels


# ── confluence ──────────────────────────────────────────────────────────────────

def find_confluence(levels: list[KeyLevel], spot: float, tolerance_pct: float = 0.002) -> list[ConfluencePoint]:
    """Where multiple levels cluster within tolerance → confluence point."""
    if not levels:
        return []

    groups: list[list[KeyLevel]] = []
    used: set[int] = set()

    for i, a in enumerate(levels):
        if i in used:
            continue
        group = [a]
        used.add(i)
        for j, b in enumerate(levels):
            if j in used:
                continue
            if abs(a.price - b.price) / max(a.price, b.price, 1.0) <= tolerance_pct:
                group.append(b)
                used.add(j)
        if len(group) >= 2:
            signals = sorted({s.kind for s in group})
            strength = min(1.0, len(group) / 5.0)  # up to 5 signals → strength 1.0
            groups.append(ConfluencePoint(
                price=group[0].price,
                signals=signals,
                strength=strength,
            ))

    return sorted(groups, key=lambda c: (-c.strength, c.price))


# ── summary text ────────────────────────────────────────────────────────────────

def build_summary(read: MarketRead) -> str:
    """2-3 sentence plain-language read."""
    r = read.regime
    parts = []

    parts.append(f"{r.description.capitalize()}")

    if r.buyer_led:
        parts.append("Buyers are leading the action.")
    elif r.seller_led:
        parts.append("Sellers are leading the action.")
    if r.absorbing:
        side = r.absorbing_side or "unknown"
        parts.append(f"Absorption is dominating on the {side} side — large orders are holding the level.")

    if read.composite_score >= 70:
        parts.append(f"Conviction is high (score {read.composite_score}).")
    elif read.composite_score >= 50:
        parts.append(f"Conviction is moderate (score {read.composite_score}).")
    else:
        parts.append(f"Conviction is low (score {read.composite_score}) — signals are conflicting.")

    if read.n_confluence > 0:
        parts.append(f"{read.n_confluence} confluence point(s) where multiple signals agree.")

    if read.key_levels:
        top = read.key_levels[:3]
        level_desc = ", ".join(f"{l.kind} at {_round_price(l.price)}" for l in top)
        parts.append(f"Key levels: {level_desc}.")

    return " ".join(parts)


# ── main engine ─────────────────────────────────────────────────────────────────

def read_market(state: MarketState) -> MarketRead:
    """The deterministic market read — pure function of a state snapshot."""
    regime = classify_regime(state)
    composite, breakdown = compute_score(state, regime)
    levels = extract_levels(state)
    confluence = find_confluence(levels, state.spot)

    return MarketRead(
        regime=regime,
        composite_score=composite,
        score_breakdown=breakdown,
        key_levels=levels,
        confluence_points=confluence,
        summary=build_summary(MarketRead(
            regime=regime, composite_score=composite, score_breakdown=breakdown,
            key_levels=levels, confluence_points=confluence,
            summary="", timestamp_ms=state.timestamp_ms,
            n_levels=len(levels), n_confluence=len(confluence),
        )),
        timestamp_ms=state.timestamp_ms,
        n_levels=len(levels),
        n_confluence=len(confluence),
    )
