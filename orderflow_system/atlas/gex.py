"""
Gamma Exposure (GEX) engine — per-strike dealer gamma, zero-gamma line, call/put walls.

Pure computation: given an options chain (list of strikes with gamma, OI, side, spot,
multiplier), it returns the GEX map, zero-gamma level, walls, and summary figures.

Calibrate against Senzoukria's published NQ example (senzoukria.com home page, 2026-09-19):
  Zero Gamma    $641.00
  Call Wall     $655.00  (+10.31, +1.60%)
  Put Wall      $630.00  (-14.69, -2.28%)
  Total DEX     +2.2M shares
  Total VEX     +$629.5M per vol-pt
  Theta Decay   -$127.4M/$/day
  Vanna exposure +$833.9M $delta per vol-pt
  Charm exposure +$48.5M $delta per day
  Put/Call OI   1.29  (426K / 329K)
  25Δ Skew       -3.37%  (put - call IV)
  ATM IV        13.87%  front month

No network, no config, no UI — a pure function of a chain. The Deribit adapter already
gives us per-strike gamma/OI/side from /api/control/deribit/chain + ticker; the
 Tradier/Market Data adapters (when wired) give us OPRA chains the same shape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


# ── input shape ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Strike:
    """One strike's slice of the chain — the minimum a GEX engine needs."""
    price: float
    gamma: float           # per-share gamma (e.g. Deribit greeks.gamma, or OPRA gamma)
    oi: float              # open interest (contracts or shares)
    side: str              # "call" | "put"
    iv: Optional[float] = None   # implied vol for this strike (for skew/ATM calcs)
    vega: Optional[float] = None # per-share vega (for VEX)
    theta: Optional[float] = None # per-share theta (for theta decay)
    vanna: Optional[float] = None # per-share vanna (for vanna exposure)
    charm: Optional[float] = None # per-share charm (for charm exposure)


@dataclass
class GEXResult:
    """Everything the GEX view renders from one chain."""
    spot: float
    multiplier: float
    per_strike: list[dict[str, Any]]     # ordered by price: {strike, gamma, oi, side, dex, ...}
                                         # gamma/dex/gamma_exp carry the contract's own units
                                         # (coins on Deribit, shares on an OPRA chain)
    zero_gamma_level: Optional[float]    # price where cumulative gamma crosses zero
    call_walls: list[dict[str, Any]]     # strikes above spot with notable positive gamma
    put_walls: list[dict[str, Any]]      # strikes below spot with notable positive gamma
    total_dex: float                     # Σ |delta| * oi * multiplier  (contracts: coins, or shares)
    total_vex: float                     # Σ |gamma| * oi * vega  (volatility exposure, per vol-pt)
    total_theta: float                   # Σ theta * oi  (time decay, per day)
    total_vanna: float                   # sum of vanna * oi (vanna exposure)
    total_charm: float                   # sum of charm * oi (charm exposure)
    put_call_oi: float                   # put OI / call OI ratio
    call_oi: float
    put_oi: float
    atm_iv: Optional[float]              # IV at the strike nearest spot
    skew_25d: Optional[float]            # 25-delta put IV - call IV  (None if not enough data)
    n_strikes: int
    note: str = ""


# ── pure helpers ────────────────────────────────────────────────────────────────

def _finite(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _side_gamma(side: str, gamma: float) -> float:
    """Dealer gamma sign: calls → dealers short gamma (negative), puts → dealers long gamma (positive)."""
    # When a customer buys a call, the dealer is short the option → short gamma.
    # When a customer buys a put, the dealer is long the option → long gamma.
    # Dealer gamma = -customer_gamma for calls, +customer_gamma for puts (approximately).
    g = _finite(gamma) or 0.0
    if side == "put":
        return +g
    return -g


def _side_delta(side: str, strike: float, spot: float) -> float:
    """Rough delta sign for DEX: calls positive, puts negative. Uses a linear approx near spot."""
    d = _finite(strike) or spot
    if side == "call":
        return max(0.0, min(1.0, (spot - d) / max(1.0, d) + 0.5))
    return min(0.0, max(-1.0, (spot - d) / max(1.0, d) - 0.5))


# ── main engine ──────────────────────────────────────────────────────────────────

def compute_gex(
    strikes: Iterable[Mapping[str, Any] | Strike],
    *,
    spot: float,
    multiplier: float = 1.0,
    wall_quantile: float = 0.95,
    zero_tol: float = 1e-6,
) -> GEXResult:
    """Compile a GEX map from one option chain.

    Parameters
    ----------
    strikes : each entry is a Strike dataclass or a dict with {price, gamma, oi, side,
              [iv], [vega], [theta], [vanna], [charm]}.
    spot : the underlying price (forward for futures options).
    multiplier : contracts' $ multiplier (1 for crypto options, e.g. 50 for stock options).
    wall_quantile : a strike is a "wall" when its absolute gamma exposure is in the top
                    ``wall_quantile`` of all strikes on its side.
    zero_tol : cumulative-gamma proximity to zero that counts as the zero-gamma line.
    """
    items: list[Strike] = []
    for entry in strikes:
        if isinstance(entry, Strike):
            # Clamp non-finite prices so they don't poison the sort or the zero-line walk.
            p = _finite(entry.price)
            items.append(Strike(
                price=p if p is not None else 0.0,
                gamma=entry.gamma,
                oi=entry.oi,
                side=entry.side,
                iv=entry.iv,
                vega=entry.vega,
                theta=entry.theta,
                vanna=entry.vanna,
                charm=entry.charm,
            ))
        elif isinstance(entry, dict):
            items.append(Strike(
                price=_finite(entry.get("price")) or 0.0,
                gamma=entry.get("gamma", 0.0),
                oi=entry.get("oi", 0.0),
                side=str(entry.get("side", "")).lower() or "call",
                iv=entry.get("iv"),
                vega=entry.get("vega"),
                theta=entry.get("theta"),
                vanna=entry.get("vanna"),
                charm=entry.get("charm"),
            ))
        else:
            continue

    if not items:
        return GEXResult(
            spot=spot, multiplier=multiplier, per_strike=[], zero_gamma_level=None,
            call_walls=[], put_walls=[], total_dex=0.0, total_vex=0.0,
            total_theta=0.0, total_vanna=0.0, total_charm=0.0,
            put_call_oi=0.0, call_oi=0.0, put_oi=0.0, atm_iv=None, skew_25d=None,
            n_strikes=0, note="empty chain",
        )

    # Sort by price ascending.
    items.sort(key=lambda s: s.price)

    # Per-strike dex (delta exposure) and gamma exposure.
    per_strike: list[dict[str, Any]] = []
    cum_gamma: list[tuple[float, float]] = []   # (price, cumulative_gamma_exposure)
    call_oi = 0.0
    put_oi = 0.0
    total_dex = 0.0
    total_vex = 0.0
    total_theta = 0.0
    total_vanna = 0.0
    total_charm = 0.0
    call_ivs: list[tuple[float, float]] = []   # (delta proxy, iv) for calls
    put_ivs: list[tuple[float, float]] = []    # (delta proxy, iv) for puts

    cum = 0.0
    for s in items:
        g_raw = _finite(s.gamma) or 0.0
        oi = _finite(s.oi) or 0.0
        dealer_gamma = _side_gamma(s.side, g_raw)
        gamma_exp = dealer_gamma * oi * multiplier          # $ exposure to a 1-point move
        dex = _side_delta(s.side, s.price, spot) * oi * multiplier  # delta exposure (sign + size)
        cum += dealer_gamma * oi                            # cumulative gamma (unitless, for zero line)
        cum_gamma.append((s.price, cum))

        per_strike.append({
            "strike": round(s.price, 6),
            "gamma": round(g_raw, 8),
            "oi": round(oi, 4),
            "side": s.side,
            "dealer_gamma": round(dealer_gamma, 8),
            # 8 dp, not 4: a crypto chain's exposures run 1e-4..1e2 (one BTC contract's gamma is
            # ~0.0004), so 4 dp quantised most strikes to exactly 0.0000 -- which flattened the
            # panel's ΓEX column, made its "widest exposure first" sort a tie, and coarsened the
            # wall threshold that reads these same values.
            "gamma_exp": round(gamma_exp, 8),
            "dex": round(dex, 8),
            "iv": round(_finite(s.iv) or 0.0, 6) if s.iv is not None else None,
            "vega": round(_finite(s.vega) or 0.0, 8) if s.vega is not None else None,
            "theta": round(_finite(s.theta) or 0.0, 8) if s.theta is not None else None,
            "vanna": round(_finite(s.vanna) or 0.0, 8) if s.vanna is not None else None,
            "charm": round(_finite(s.charm) or 0.0, 8) if s.charm is not None else None,
        })

        if s.side == "call":
            call_oi += oi
            if s.iv is not None:
                call_ivs.append((_side_delta(s.side, s.price, spot), _finite(s.iv)))
        else:
            put_oi += oi
            if s.iv is not None:
                put_ivs.append((_side_delta(s.side, s.price, spot), _finite(s.iv)))

        total_dex += abs(dex)
        vega_v = _finite(s.vega) or 0.0
        # VEX = |gamma| * oi * vega -- "per vol-pt" is the venue's vega unit. (This used to claim
        # "gamma * oi * iv" while multiplying by vega; a strike the venue sends no vega for
        # contributes 0, so a chain with no greeks reads a flat VEX rather than a wrong one.)
        total_vex += abs(g_raw) * oi * (vega_v if vega_v else 0.0)
        theta_v = _finite(s.theta) or 0.0
        total_theta += theta_v * oi
        vanna_v = _finite(s.vanna) or 0.0
        total_vanna += vanna_v * oi
        charm_v = _finite(s.charm) or 0.0
        total_charm += charm_v * oi

    # Zero-gamma level: the price where cumulative gamma crosses zero.
    zero_gamma_level: Optional[float] = None
    if cum_gamma:
        # Walk the cumulative gamma; the zero line is where it crosses.
        prev_price, prev_cum = cum_gamma[0]
        for price, c in cum_gamma[1:]:
            if (prev_cum <= zero_tol and c >= -zero_tol) or (prev_cum >= -zero_tol and c <= zero_tol):
                # Linear interpolation between the two points.
                if c != prev_cum:
                    frac = (0.0 - prev_cum) / (c - prev_cum)
                    zero_gamma_level = round(prev_price + frac * (price - prev_price), 6)
                else:
                    zero_gamma_level = round(prev_price, 6)
                break
            prev_price, prev_cum = price, c
        if zero_gamma_level is None:
            # Entirely one-signed — the zero line is at the edge.
            if cum > 0:
                zero_gamma_level = round(cum_gamma[0][0], 6)
            elif cum < 0:
                zero_gamma_level = round(cum_gamma[-1][0], 6)

    # Walls: top wall_quantile of absolute gamma exposure on each side.
    call_gammas = sorted([abs(ps["gamma_exp"]) for ps in per_strike if ps["side"] == "call"], reverse=True)
    put_gammas = sorted([abs(ps["gamma_exp"]) for ps in per_strike if ps["side"] == "put"], reverse=True)

    call_threshold = call_gammas[int(len(call_gammas) * wall_quantile)] if call_gammas else 0.0
    put_threshold = put_gammas[int(len(put_gammas) * wall_quantile)] if put_gammas else 0.0

    call_walls = [ps for ps in per_strike
                  if ps["side"] == "call" and abs(ps["gamma_exp"]) >= call_threshold and ps["strike"] > spot]
    put_walls = [ps for ps in per_strike
                 if ps["side"] == "put" and abs(ps["gamma_exp"]) >= put_threshold and ps["strike"] < spot]

    # Sort walls by distance from spot (closest first).
    call_walls.sort(key=lambda ps: abs(ps["strike"] - spot))
    put_walls.sort(key=lambda ps: abs(ps["strike"] - spot))

    # Put/call OI ratio.
    put_call_oi = put_oi / call_oi if call_oi > 0 else 0.0

    # ATM IV: IV at the strike nearest spot.
    atm_iv: Optional[float] = None
    if items:
        nearest = min(items, key=lambda s: abs(s.price - spot))
        atm_iv = round(_finite(nearest.iv) or 0.0, 6) if nearest.iv is not None else None

    # 25-delta skew: 25Δ put IV - 25Δ call IV.
    skew_25d: Optional[float] = None
    if call_ivs and put_ivs:
        # Approximate 25-delta strikes: the strike whose delta proxy is closest to -0.25 (put) / +0.25 (call).
        put_25 = min(put_ivs, key=lambda iv: abs(iv[0] + 0.25))
        call_25 = min(call_ivs, key=lambda iv: abs(iv[0] - 0.25))
        if put_25[1] is not None and call_25[1] is not None:
            skew_25d = round(put_25[1] - call_25[1], 6)

    return GEXResult(
        spot=spot,
        multiplier=multiplier,
        per_strike=per_strike,
        zero_gamma_level=zero_gamma_level,
        call_walls=call_walls,
        put_walls=put_walls,
        total_dex=round(total_dex, 4),
        total_vex=round(total_vex, 4),
        total_theta=round(total_theta, 4),
        total_vanna=round(total_vanna, 4),
        total_charm=round(total_charm, 4),
        put_call_oi=round(put_call_oi, 6),
        call_oi=round(call_oi, 4),
        put_oi=round(put_oi, 4),
        atm_iv=atm_iv,
        skew_25d=skew_25d,
        n_strikes=len(items),
        note="",
    )


# ── convenience: build a chain from the Deribit ladder shape ────────────────────

def from_deribit_ladder(
    ladder: Mapping[str, Any],
    *,
    spot: Optional[float] = None,
    multiplier: float = 1.0,
) -> list[dict[str, Any]]:
    """Convert the Deribit chain response's strikes into the dict shape compute_gex accepts.

    The Deribit ladder shape (from /api/control/deribit/chain) is:
        { expiries: [{code, label, ms, days, strikes}], strikes: [{strike, call, put}] }
    where each call/put is { instrument, bid, ask, mid, iv, delta, gamma, theta, vega, rho,
                             oi, volume, underlying, ts, state }.

    Returns a list of {price, gamma, oi, side, iv, vega, theta, vanna, charm} dicts
    for all strikes in the ladder (both calls and puts).

    ``iv`` is a FRACTION here (0.1387 = 13.87%) because that is the unit every engine in this
    package takes and its tests pin; Deribit reports ``mark_iv`` as a PERCENTAGE, so the venue's
    unit is converted in this adapter, once, at the only place it is known. A percentage reaching
    ``compute_gex`` would be 100x too large inside every vol-scaled figure (and would read as
    "2450%" in the panel's IV column).
    """
    out: list[dict[str, Any]] = []
    strikes = ladder.get("strikes") if isinstance(ladder, dict) else None
    if not isinstance(strikes, list):
        return out
    for row in strikes:
        if not isinstance(row, dict):
            continue
        strike_price = _finite(row.get("strike")) or 0.0
        for side_key, side_name in (("call", "call"), ("put", "put")):
            side_data = row.get(side_key)
            if not isinstance(side_data, dict):
                continue
            gamma = _finite(side_data.get("gamma")) or 0.0
            if gamma == 0.0 and side_data.get("state") == "inactive":
                continue
            iv_pct = _finite(side_data.get("iv"))          # the venue's percentage, e.g. 13.87
            out.append({
                "price": strike_price,
                "gamma": gamma,
                "oi": _finite(side_data.get("oi")) or 0.0,
                # The surface reads the same number under its own field name (IVStrike.open_interest).
                "open_interest": _finite(side_data.get("oi")) or 0.0,
                "side": side_name,
                "iv": (iv_pct / 100.0) if iv_pct is not None else None,
                # Deribit's ticker does publish a per-instrument delta, and a real delta is what
                # the surface's 25Δ selection wants (its own proxy is a last resort).
                "delta": _finite(side_data.get("delta")),
                "vega": _finite(side_data.get("vega")),
                "theta": _finite(side_data.get("theta")),
                # The venue's own traded volume for this contract — the GEX table shows it beside
                # the open interest, which is what tells a fresh strike from an old one.
                "volume": _finite(side_data.get("volume")),
                # Deribit publishes no vanna and no charm, so the honest value is "unknown" —
                # a 0.0 here would read as a measured zero exposure in the totals.
                "vanna": None,
                "charm": None,
            })
    return out
