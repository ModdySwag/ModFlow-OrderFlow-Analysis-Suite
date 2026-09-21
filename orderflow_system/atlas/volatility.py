
"""
Implied volatility surface — smile, skew, term structure from an options chain.

Pure computation: given a chain of strikes with IV per strike, returns the IV smile
curve, 25Δ skew, ATM IV, and per-expiry term structure.

Calibrate against Senzoukria's published NQ example (senzoukria.com, 2026-09-19):
  ATM IV        13.87%   front month
  25Δ Skew       -3.37%   put IV − call IV
  IV surface: 3D surface, flat heatmap, one-expiry curve, aggregated profile

No network, no config, no UI — a pure function of a chain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


@dataclass(frozen=True)
class IVStrike:
    price: float
    iv: float
    side: str              # "call" | "put"
    delta: Optional[float] = None   # approximate delta (for 25Δ selection)
    open_interest: float = 0.0
    expiry_ms: Optional[int] = None


@dataclass
class VolatilityResult:
    spot: float
    atm_iv: Optional[float]           # IV at the strike nearest spot
    skew_25d: Optional[float]          # 25Δ put IV − 25Δ call IV (negative = put skew)
    smile: list[dict[str, Any]]        # iv vs strike, ordered by price
    per_expiry: dict[str, dict[str, Any]]  # expiry_ms → {atm_iv, skew_25d, curve: [...]}
    term_structure: list[dict[str, Any]]   # sorted by expiry: {expiry_ms, atm_iv, skew_25d}
    n_strikes: int
    n_expiries: int
    #: The two 25Δ wings the skew is the difference of (None when the chain has no usable pair).
    put_25d_iv: Optional[float] = None
    call_25d_iv: Optional[float] = None
    note: str = ""


def _finite(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _delta_prox(price: float, spot: float) -> float:
    """Crude delta proxy for 25Δ selection — same linear approx as gex._side_delta."""
    if price <= 0:
        return 0.0
    d = (spot - price) / price
    # Calls: +0.5 baseline; puts: −0.5 baseline.
    return d


#: §148 / T7-F10 — said on the row when a "25-delta" wing was in fact picked by the moneyness
#: proxy above, because the chain arrived without deltas. "25-delta" must not claim a selection the
#: data did not support.
PROXY_NOTE = ("the chain arrived without deltas, so the 25-delta wings were picked by a "
              "moneyness proxy")


def _wing_rows(items: Iterable[IVStrike], side: str, spot: float
               ) -> list[tuple[float, Optional[float], bool]]:
    """One side of a chain as (delta-or-proxy, iv, was-the-delta-a-proxy?) for 25Δ selection."""
    rows: list[tuple[float, Optional[float], bool]] = []
    for s in items:
        if s.iv is None or s.side != side:
            continue
        if s.delta is not None:
            rows.append((s.delta, s.iv, False))
        else:
            rows.append((_delta_prox(s.price, spot), s.iv, True))
    return rows


def compute_volatility(
    strikes: Iterable[Mapping[str, Any] | IVStrike],
    *,
    spot: float,
    multiplier: float = 1.0,
) -> VolatilityResult:
    """Compile an IV surface from one option chain.

    Parameters
    ----------
    strikes : each entry is an IVStrike or a dict with {price, iv, side, [delta],
              [open_interest], [expiry_ms]}.
    spot : the underlying price.
    multiplier : not used in IV calcs (IV is unitless) but accepted for shape consistency
                 with gex.compute_gex.
    """
    items: list[IVStrike] = []
    for entry in strikes:
        if isinstance(entry, IVStrike):
            p = _finite(entry.price)
            iv = _finite(entry.iv)
            items.append(IVStrike(
                price=p if p is not None else 0.0,
                iv=iv if iv is not None else 0.0,
                side=entry.side,
                delta=entry.delta,
                open_interest=entry.open_interest,
                expiry_ms=entry.expiry_ms,
            ))
        elif isinstance(entry, dict):
            iv_val = _finite(entry.get("iv"))
            items.append(IVStrike(
                price=_finite(entry.get("price")) or 0.0,
                iv=iv_val if iv_val is not None else 0.0,
                side=str(entry.get("side", "")).lower() or "call",
                delta=_finite(entry.get("delta")),
                open_interest=_finite(entry.get("open_interest")) or 0.0,
                expiry_ms=entry.get("expiry_ms"),
            ))
        else:
            continue

    if not items:
        return VolatilityResult(spot=spot, atm_iv=None, skew_25d=None, smile=[],
                                per_expiry={}, term_structure=[], n_strikes=0, n_expiries=0,
                                note="empty chain")

    # Sort by price ascending.
    items.sort(key=lambda s: s.price)

    # ATM IV: IV at the strike nearest spot.
    atm_strike = min(items, key=lambda s: abs(s.price - spot))
    atm_iv = atm_strike.iv if atm_strike.iv is not None else None

    # Build the smile curve: one point per strike, IV vs price.
    smile: list[dict[str, Any]] = []
    for s in items:
        smile.append({
            "strike": round(s.price, 6),
            "iv": round(s.iv, 6) if s.iv is not None else None,
            "side": s.side,
            "delta": round(s.delta, 6) if s.delta is not None else None,
            "oi": round(s.open_interest, 4),
            # The expiry rides on the row so a multi-expiry chain's table can label each point
            # instead of leaving the column blank between two expiries.
            "expiry_ms": s.expiry_ms,
        })

    # Group by expiry for term structure.
    by_expiry: dict[int, list[IVStrike]] = {}
    for s in items:
        exp = s.expiry_ms
        if exp is None:
            continue
        by_expiry.setdefault(exp, []).append(s)

    per_expiry: dict[str, dict[str, Any]] = {}
    term_structure: list[dict[str, Any]] = []
    proxied_wings = False
    for exp_ms, exp_items in sorted(by_expiry.items()):
        exp_spot = spot  # same spot for all expiries (simplification)
        exp_atm = min(exp_items, key=lambda s: abs(s.price - exp_spot))
        exp_atm_iv = exp_atm.iv if exp_atm.iv is not None else None

        # 25Δ skew per expiry.
        call_ivs = _wing_rows(exp_items, "call", exp_spot)
        put_ivs = _wing_rows(exp_items, "put", exp_spot)

        skew_25d: Optional[float] = None
        if call_ivs and put_ivs:
            put_25 = min(put_ivs, key=lambda x: abs(x[0] + 0.25))
            call_25 = min(call_ivs, key=lambda x: abs(x[0] - 0.25))
            if put_25[1] is not None and call_25[1] is not None:
                skew_25d = round(put_25[1] - call_25[1], 6)
                if put_25[2] or call_25[2]:
                    proxied_wings = True

        curve = [{"strike": round(s.price, 6), "iv": round(s.iv, 6) if s.iv is not None else None,
                  "side": s.side} for s in sorted(exp_items, key=lambda s: s.price)]

        exp_key = str(exp_ms)
        per_expiry[exp_key] = {
            "expiry_ms": exp_ms,
            "atm_iv": round(exp_atm_iv, 6) if exp_atm_iv is not None else None,
            "skew_25d": skew_25d,
            "curve": curve,
        }
        term_structure.append({
            "expiry_ms": exp_ms,
            "atm_iv": round(exp_atm_iv, 6) if exp_atm_iv is not None else None,
            "skew_25d": skew_25d,
        })

    # Overall 25Δ skew (front expiry or closest to spot).
    call_ivs_all = _wing_rows(items, "call", spot)
    put_ivs_all = _wing_rows(items, "put", spot)

    overall_skew: Optional[float] = None
    put_25d_iv: Optional[float] = None
    call_25d_iv: Optional[float] = None
    if call_ivs_all and put_ivs_all:
        put_25 = min(put_ivs_all, key=lambda x: abs(x[0] + 0.25))
        call_25 = min(call_ivs_all, key=lambda x: abs(x[0] - 0.25))
        if put_25[1] is not None and call_25[1] is not None:
            overall_skew = round(put_25[1] - call_25[1], 6)
            # The two wings the skew is the difference OF. A panel that shows only the spread
            # cannot say which wing moved, and both numbers are already in hand here.
            put_25d_iv = round(put_25[1], 6)
            call_25d_iv = round(call_25[1], 6)
            if put_25[2] or call_25[2]:
                proxied_wings = True

    return VolatilityResult(
        spot=spot,
        atm_iv=round(atm_iv, 6) if atm_iv is not None else None,
        skew_25d=overall_skew,
        smile=smile,
        per_expiry=per_expiry,
        term_structure=term_structure,
        n_strikes=len(items),
        n_expiries=len(by_expiry),
        put_25d_iv=put_25d_iv,
        call_25d_iv=call_25d_iv,
        note=PROXY_NOTE if proxied_wings else "",
    )
