
"""
Option flow classification — sweeps, blocks, unusual premium from option trade prints.

Pure computation: given a stream of option trade prints (symbol, expiry, strike, side,
size, price, timestamp), classifies each as a sweep, block, unusual premium, or
routine print. Aggregates by symbol/expiry/strike/side/time window.

Calibrate against Senzoukria's three classification buckets (senzoukria.com/flow):
  - Sweeps: large order executed across multiple strikes/exchanges in a short window
  • Blocks: single large print at one strike/expiry (institutional)
  • Unusual premium: premium paid relative to open interest is abnormally high

No network, no config, no UI — a pure function of a trade print stream.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


# ── input shape ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OptionTrade:
    symbol: str                 # e.g. "BTCUSDT", "SPY"
    expiry: str                 # e.g. "16SEP26", "2026-09-18"
    strike: float               # strike price
    side: str                   # "call" | "put" | "unknown"
    size: float                 # number of contracts
    price: float                # premium per contract
    timestamp_ms: int           # epoch ms
    aggressor: Optional[str] = None   # "buy" | "sell" | None
    oi_at_trade: Optional[float] = None  # open interest at this strike (for unusual premium)


# ── classification thresholds (tunable) ─────────────────────────────────────────

# A trade this size or larger (in contracts) is a candidate for block/sweep classification.
BLOCK_SIZE_MIN = 50.0

# A sweep: multiple large prints across different strikes within this many ms.
SWEEP_WINDOW_MS = 300000          # 5 minutes
SWEEP_MIN_STRIKES = 3             # at least this many distinct strikes
SWEEP_MIN_TOTAL_SIZE = 200.0      # total contracts across the window

# Unusual premium: premium / OI ratio above this threshold.
UNUSUAL_PREMIUM_RATIO = 0.10      # 10% of OI paid in one print


# ── classification result ────────────────────────────────────────────────────────

@dataclass
class ClassifiedTrade:
    trade: OptionTrade
    classification: str          # "sweep" | "block" | "unusual_premium" | "routine"
    reason: str                  # plain-language why
    sweep_id: Optional[str] = None   # if part of a sweep, the sweep's id


@dataclass
class Sweep:
    sweep_id: str
    symbol: str
    start_ms: int
    end_ms: int
    strikes: list[float]
    total_size: float
    total_premium: float
    trades: list[ClassifiedTrade]


@dataclass
class FlowSummary:
    symbol: str
    window_start_ms: int
    window_end_ms: int
    total_trades: int
    sweeps: list[Sweep]
    blocks: list[ClassifiedTrade]
    unusual_premium: list[ClassifiedTrade]
    routine: list[ClassifiedTrade]
    n_sweeps: int
    n_blocks: int
    n_unusual: int
    n_routine: int


# ── helpers ──────────────────────────────────────────────────────────────────────

def _finite(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _premium(trade: OptionTrade) -> float:
    """Total premium paid: size × price per contract."""
    s = _finite(trade.size) or 0.0
    p = _finite(trade.price) or 0.0
    return s * p


# ── single-trade classification ──────────────────────────────────────────────────

def classify_trade(trade: OptionTrade, oi_at_strike: Optional[float] = None) -> ClassifiedTrade:
    """Classify one option trade print.

    Priority order:
      1. Unusual premium — premium is a large fraction of OI at this strike.
      2. Block — single large print at one strike/expiry.
      3. Routine — everything else (may later be grouped into a sweep).
    """
    size = _finite(trade.size) or 0.0
    price = _finite(trade.price) or 0.0
    premium = _premium(trade)

    # Unusual premium: |premium| / OI > threshold.
    # Use oi_at_strike if provided, else fall back to the trade's own oi_at_trade.
    oi = oi_at_strike if oi_at_strike is not None else trade.oi_at_trade
    if oi is not None and oi > 0:
        ratio = abs(premium) / oi
        if ratio >= UNUSUAL_PREMIUM_RATIO:
            return ClassifiedTrade(
                trade=trade,
                classification="unusual_premium",
                reason=(f"premium ${premium:,.0f} is {ratio:.1%} of OI ({oi:,.0f} contracts) "
                        f"— abnormally high premium for {trade.symbol} {trade.strike} {trade.expiry}"),
            )

    # Block: large single print.
    if size >= BLOCK_SIZE_MIN:
        return ClassifiedTrade(
            trade=trade,
            classification="block",
            reason=(f"{size:,.0f} contracts of {trade.side} {trade.symbol} "
                    f"${trade.strike} {trade.expiry} at ${price:.2f} — "
                    f"large single-print block"),
        )

    size = _finite(trade.size) or 0.0
    premium = _premium(trade)

    return ClassifiedTrade(
        trade=trade,
        classification="routine",
        reason=f"routine print — {size:,.0f} contracts, ${premium:,.0f} premium",
    )


# ── sweep detection (across multiple trades) ────────────────────────────────────

def detect_sweeps(
    trades: Iterable[Mapping[str, Any] | OptionTrade],
    *,
    window_ms: int = SWEEP_WINDOW_MS,
    min_strikes: int = SWEEP_MIN_STRIKES,
    min_total_size: float = SWEEP_MIN_TOTAL_SIZE,
) -> list[Sweep]:
    """Find sweeps: large option flow across multiple strikes within a time window.

    A sweep is a cluster of block-sized trades across >= min_strikes distinct strikes
    within window_ms milliseconds, totalling >= min_total_size contracts.
    """
    items: list[OptionTrade] = []
    for entry in trades:
        if isinstance(entry, OptionTrade):
            items.append(entry)
        elif isinstance(entry, dict):
            items.append(OptionTrade(
                symbol=str(entry.get("symbol") or ""),
                expiry=str(entry.get("expiry") or ""),
                strike=_finite(entry.get("strike")) or 0.0,
                side=str(entry.get("side") or "").lower() or "unknown",
                size=_finite(entry.get("size")) or 0.0,
                price=_finite(entry.get("price")) or 0.0,
                timestamp_ms=int(entry.get("timestamp_ms") or 0),
                aggressor=str(entry.get("aggressor") or "").lower() or None,
                oi_at_trade=_finite(entry.get("oi_at_trade")),
            ))
        else:
            continue

    if not items:
        return []

    # Sort by timestamp.
    items.sort(key=lambda t: t.timestamp_ms)

    # Only consider block-sized trades for sweep detection.
    blocks = [t for t in items if (t.size or 0) >= BLOCK_SIZE_MIN]
    if len(blocks) < min_strikes:
        return []

    sweeps: list[Sweep] = []
    used: set[int] = set()
    sweep_counter = 0

    for i, seed in enumerate(blocks):
        if i in used:
            continue
        # Collect all block trades within window_ms of the seed.
        window_trades: list[OptionTrade] = []
        for j, t in enumerate(blocks):
            if j in used:
                continue
            if abs(t.timestamp_ms - seed.timestamp_ms) <= window_ms:
                window_trades.append(t)

        if len(window_trades) < min_strikes:
            continue

        distinct_strikes = {t.strike for t in window_trades}
        if len(distinct_strikes) < min_strikes:
            continue

        total_size = sum(t.size for t in window_trades)
        if total_size < min_total_size:
            continue

        # This is a sweep.
        sweep_counter += 1
        sweep_id = f"sweep-{seed.symbol}-{seed.timestamp_ms}-{sweep_counter}"
        total_premium = sum(_premium(t) for t in window_trades)

        classified = []
        for t in window_trades:
            used.add(blocks.index(t))
            classified.append(ClassifiedTrade(
                trade=t,
                classification="sweep",
                reason=(f"part of sweep {sweep_id} — {t.size:,.0f} contracts "
                        f"{t.side} {t.symbol} ${t.strike} {t.expiry}"),
                sweep_id=sweep_id,
            ))

        sweeps.append(Sweep(
            sweep_id=sweep_id,
            symbol=seed.symbol,
            start_ms=min(t.timestamp_ms for t in window_trades),
            end_ms=max(t.timestamp_ms for t in window_trades),
            strikes=sorted(distinct_strikes),
            total_size=total_size,
            total_premium=total_premium,
            trades=classified,
        ))

    return sweeps


# ── full classification pipeline ─────────────────────────────────────────────────

def classify_stream(
    trades: Iterable[Mapping[str, Any] | OptionTrade],
    *,
    oi_lookup: Optional[Mapping[str, float]] = None,
) -> FlowSummary:
    """Classify an entire stream of option trades.

    Parameters
    ----------
    trades : iterable of OptionTrade or dicts with the OptionTrade shape.
    oi_lookup : optional mapping { "symbol|expiry|strike|side" : open_interest } for
                unusual-premium detection.
    """
    items: list[OptionTrade] = []
    for entry in trades:
        if isinstance(entry, OptionTrade):
            items.append(entry)
        elif isinstance(entry, dict):
            items.append(OptionTrade(
                symbol=str(entry.get("symbol") or ""),
                expiry=str(entry.get("expiry") or ""),
                strike=_finite(entry.get("strike")) or 0.0,
                side=str(entry.get("side") or "").lower() or "unknown",
                size=_finite(entry.get("size")) or 0.0,
                price=_finite(entry.get("price")) or 0.0,
                timestamp_ms=int(entry.get("timestamp_ms") or 0),
                aggressor=str(entry.get("aggressor") or "").lower() or None,
                oi_at_trade=_finite(entry.get("oi_at_trade")),
            ))
        else:
            continue

    if not items:
        return FlowSummary(
            symbol="", window_start_ms=0, window_end_ms=0,
            total_trades=0, sweeps=[], blocks=[], unusual_premium=[],
            routine=[], n_sweeps=0, n_blocks=0, n_unusual=0, n_routine=0,
        )

    items.sort(key=lambda t: t.timestamp_ms)
    window_start = items[0].timestamp_ms
    window_end = items[-1].timestamp_ms
    symbol = items[0].symbol

    # Single-trade classification.
    classified: list[ClassifiedTrade] = []
    for t in items:
        oi = t.oi_at_trade
        if oi is None and oi_lookup is not None:
            key = f"{t.symbol}|{t.expiry}|{t.strike}|{t.side}"
            oi = oi_lookup.get(key)
        classified.append(classify_trade(t, oi))

    # Sweep detection on block-sized trades.
    sweeps = detect_sweeps(items)

    # Re-classify sweep members.
    sweep_ids = {s.sweep_id for s in sweeps}
    for c in classified:
        if c.sweep_id in sweep_ids:
            c.classification = "sweep"

    sweeps_out = [s for s in sweeps]
    blocks = [c for c in classified if c.classification == "block" and c.sweep_id is None]
    unusual = [c for c in classified if c.classification == "unusual_premium"]
    routine = [c for c in classified if c.classification == "routine"]

    return FlowSummary(
        symbol=symbol,
        window_start_ms=window_start,
        window_end_ms=window_end,
        total_trades=len(items),
        sweeps=sweeps_out,
        blocks=blocks,
        unusual_premium=unusual,
        routine=routine,
        n_sweeps=len(sweeps_out),
        n_blocks=len(blocks),
        n_unusual=len(unusual),
        n_routine=len(routine),
    )
