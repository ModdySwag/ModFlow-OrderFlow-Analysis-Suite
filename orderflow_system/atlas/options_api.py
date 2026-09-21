"""
Options analytics REST — dealer gamma (GEX), the implied-volatility surface, option flow.

Mounted by the desktop launcher beside the atlas and fundamentals routers:

    /api/options/gex/{symbol}          per-strike dealer gamma, zero-gamma line, call/put walls
    /api/options/volatility/{symbol}   IV smile per expiry, 25-delta skew, term structure
    /api/options/flow/{symbol}         sweep / block / unusual-premium classification of prints

The three sources and EXACTLY what each one carries. The routes refuse rather than fill a gap
with zeros — a GEX of zeros is a lie, not a reading:

    deribit      public and keyless; per-instrument gamma, vega, theta, IV and open interest
    marketdata   US equity OPRA chains with server-side greeks (the ``marketdata`` config block)
    tradier      US equity OPRA chains: IV, open interest, volume, mid — **no gammas**, so the
                 GEX route answers with that sentence while the surface still works

Read-only by construction: GETs to venues the browser cannot reach itself (no CORS header), no
engine verb, no socket, nothing stored. Blocking venue I/O runs off the event loop.

The analytics themselves are pure and live next door — ``atlas/gex.py``, ``atlas/volatility.py``,
``atlas/option_flow.py`` — so every number this module returns is a function of a payload a test
can pin without a network.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/options", tags=["options"])

#: The chain sources these routes know, in the order the panels offer them.
SOURCES: tuple[str, ...] = ("deribit", "tradier", "marketdata")

#: What a user has to fill in before an equity source can answer at all. The sentence names the
#: control, because that is where the key actually lives — Settings ▸ Feed keys writes the config
#: block these routes read (the file stays the fallback for a hand-edit).
_KEY_HELP: dict[str, str] = {
    "tradier": "Settings ▸ Feed keys (key_id + secret from a Tradier account)",
    "marketdata": "Settings ▸ Feed keys (an api_key from marketdata.app)",
}

#: US equity options carry 100 shares per contract; crypto contracts on Deribit are 1 coin.
EQUITY_MULTIPLIER = 100.0
CRYPTO_MULTIPLIER = 1.0

#: Per-strike rows a response will carry. A full equity chain is thousands of rows and the panel
#: draws a window; the count that was cut is stated in the payload rather than silently dropped.
MAX_STRIKE_ROWS = 400

#: Prints the flow tape carries. A 15-minute crypto window is a few hundred prints; the panel draws
#: a readable window of the newest ones and the payload says how many the read actually covered.
TAPE_ROWS = 120


# ── small helpers ────────────────────────────────────────────────────────────────

def _finite(value: Any) -> Optional[float]:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num or num in (float("inf"), float("-inf")):
        return None
    return num


def _unknown_source(source: str) -> dict[str, Any]:
    return {"ok": False, "source": source, "strikes": 0,
            "error": f"unknown chain source {source!r} — one of {', '.join(SOURCES)}"}


def _no_key(source: str) -> dict[str, Any]:
    return {"ok": False, "source": source, "strikes": 0,
            "error": f"no {source} key — add one to {_KEY_HELP.get(source, 'the app config')}"}


def _expiry_ms(text: str) -> Optional[int]:
    """``2026-09-18`` (Tradier / Market Data) or ``18SEP26`` (Deribit) → epoch ms, UTC close.

    Returns None for anything else: a made-up timestamp would sort an expiry into the wrong place
    in the term structure, and the analytics treat None as "no expiry known" on purpose.
    """
    raw = str(text or "").strip()
    for pattern in ("%Y-%m-%d", "%d%b%y", "%d%b%Y"):
        try:
            stamp = _dt.datetime.strptime(raw.upper() if "%b" in pattern else raw, pattern)
        except ValueError:
            continue
        return int(stamp.replace(tzinfo=_dt.timezone.utc).timestamp() * 1000)
    return None


def _mid(leg: Any) -> Optional[float]:
    """A leg's mid price: bid/ask when both sides are quoted, else the venue's own mark/last."""
    bid, ask = _finite(getattr(leg, "bid", None)), _finite(getattr(leg, "ask", None))
    if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid:
        return (bid + ask) / 2.0
    for field in ("mark", "last"):
        value = _finite(getattr(leg, field, None))
        if value is not None and value > 0:
            return value
    return None


def _parity_spot(strikes: list[dict[str, Any]]) -> Optional[float]:
    """A synthetic forward from put-call parity when the venue sends no underlying price.

    Every strike quotes both sides in a liquid chain, and ``C − P = F − K`` holds for a European
    pair, so ``F = K + (C − P)``. The median over the strikes that quote both sides is used (a
    single wide spread cannot move it), and fewer than three usable strikes answers None — an
    estimate from one stale quote is worse than saying "spot unknown".
    """
    pairs: dict[float, dict[str, float]] = {}
    for row in strikes:
        price = _finite(row.get("price"))
        mid = _finite(row.get("mid"))
        if price is None or mid is None:
            continue
        pairs.setdefault(price, {})[str(row.get("side") or "")] = mid
    estimates = sorted(price + (slot["call"] - slot["put"])
                       for price, slot in pairs.items() if "call" in slot and "put" in slot)
    if len(estimates) < 3:
        return None
    return estimates[len(estimates) // 2]


def _strike_rows(payload: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Sort by strike and keep the window the panel draws; the total rides back with it."""
    ordered = sorted(payload, key=lambda row: _finite(row.get("price")) or 0.0)
    if len(ordered) <= MAX_STRIKE_ROWS:
        return ordered, len(ordered)
    return ordered[:MAX_STRIKE_ROWS], len(ordered)


def _exposure_unit(chain: dict[str, Any]) -> str:
    """What one unit of ``dex`` / ``gamma_exp`` / ``total_dex`` is, named from the chain itself.

    A Deribit contract is written on one coin, so the exposure is in that coin (BTC on a BTC
    chain). An OPRA contract is a 100-share lot, so the same figures come out in shares. An
    unknown venue answers "" and the panel then shows the numbers without a unit rather than
    inventing one.
    """
    coin = str(chain.get("currency") or "").strip()
    if coin:
        return coin
    return "shares" if float(chain.get("multiplier") or 0.0) >= EQUITY_MULTIPLIER else ""


def _chain_stats(chain: dict[str, Any]) -> dict[str, Any]:
    """The desk numbers a chain answers about itself: put/call open interest, the IV range and the
    days left on the expiry. Computed from the same rows the engines read, so a summary line and
    the table under it can never disagree."""
    call_oi = 0.0
    put_oi = 0.0
    ivs: list[float] = []
    for row in chain.get("strikes") or []:
        oi = _finite(row.get("open_interest"))
        if str(row.get("side") or "") == "call":
            call_oi += oi or 0.0
        else:
            put_oi += oi or 0.0
        iv = _finite(row.get("iv"))
        if iv is not None:
            ivs.append(iv)
    exp_ms = _finite(chain.get("expiry_ms"))
    dte: Optional[float] = None
    if exp_ms:
        dte = max(0.0, (float(exp_ms) - time.time() * 1000.0) / 86_400_000.0)
    return {
        "call_oi": call_oi, "put_oi": put_oi, "total_oi": call_oi + put_oi,
        "put_call_oi": (put_oi / call_oi) if call_oi > 0 else 0.0,
        "iv_min": min(ivs) if ivs else None, "iv_max": max(ivs) if ivs else None,
        "dte": dte,
    }


# ── chain loading: one shape for three venues ────────────────────────────────────

def _deribit_chain(symbol: str, expiry: str, width: int) -> dict[str, Any]:
    from orderflow_system.atlas.gex import from_deribit_ladder
    from orderflow_system.desktop import deribit as deribit_mod

    raw = deribit_mod.chain(symbol, expiry, width or deribit_mod.DEFAULT_WIDTH)
    if not raw.get("ok"):
        return {"ok": False, "error": str(raw.get("error") or "the Deribit chain could not be read")}
    strikes = from_deribit_ladder(raw, multiplier=CRYPTO_MULTIPLIER)
    if not strikes:
        return {"ok": False, "error": f"Deribit returned no quoted strikes for {symbol}"}
    # One expiry per Deribit chain call, so every row carries that expiry's stamp: the surface
    # groups by it, and without the stamp a single-expiry chain would report no expiries at all.
    exp_ms = _finite(raw.get("expiry_ms"))
    label = str(raw.get("expiry") or "")
    for row in strikes:
        row["expiry_ms"] = int(exp_ms) if exp_ms else None
        row["expiry"] = label
    forward = _finite(raw.get("forward")) or 0.0
    return {"ok": True, "strikes": strikes, "spot": forward, "spot_from": "forward" if forward else "",
            "expiry": str(raw.get("expiry") or ""), "expiry_ms": _finite(raw.get("expiry_ms")),
            "carries_greeks": True, "multiplier": CRYPTO_MULTIPLIER,
            "currency": str(raw.get("currency") or ""), "note": str(raw.get("note") or ""),
            "quoted_sides": int(raw.get("quoted_sides") or 0)}


def _stored_feed_block(name: str) -> dict[str, Any]:
    """The stored config block for a REST feed, or ``{}``.

    This is the fall-back half of every credential read below: `settings` carries what the ENGINE
    applied (at its start), so a key saved in Settings ▸ Feed keys must still be honoured by these
    routes before any engine start — and after a restart with the engine never started. Reading the
    store directly is the same source of truth the settings card writes; the settings copy keeps
    winning when it has a value, so nothing about a running engine's behaviour changes.
    """
    try:
        from orderflow_system.desktop import config_store

        block = config_store.load_config().get(name) or {}
        return block if isinstance(block, dict) else {}
    except Exception:                                  # pragma: no cover - never blank a panel
        return {}


def _equity_chain(symbol: str, source: str) -> dict[str, Any]:
    """Tradier / Market Data chains — keyed, blocking, and called from a worker thread."""
    from orderflow_system.config import settings

    if source == "marketdata":
        block = _stored_feed_block("marketdata")
        api_key = (str(getattr(settings.MARKETDATA, "api_key", "") or "").strip()
                   or str(block.get("api_key") or "").strip())
        if not api_key:
            return _no_key(source)
        from orderflow_system.data.marketdata_feed import MarketDataFeed
        feed = MarketDataFeed(api_key=api_key)
    else:
        block = _stored_feed_block("tradier")
        key_id = (str(getattr(settings.TRADIER, "key_id", "") or "").strip()
                  or str(block.get("key_id") or "").strip())
        secret = (str(getattr(settings.TRADIER, "secret", "") or "").strip()
                  or str(block.get("secret") or "").strip())
        if not (key_id and secret):
            return _no_key(source)
        try:
            width = int(block.get("chain_width", getattr(settings.TRADIER, "chain_width", 6)) or 6)
        except (TypeError, ValueError):
            width = 6
        from orderflow_system.data.tradier_feed import TradierFeed
        feed = TradierFeed(key_id=key_id, secret=secret,
                           chain_width=min(max(width, 1), 20),
                           sandbox=bool(block.get("sandbox", getattr(settings.TRADIER, "sandbox", False))))

    data = feed.chains(symbol)
    if data.error:
        return {"ok": False, "source": source, "error": str(data.error)}
    if not data.chains:
        return {"ok": False, "source": source, "error": f"{source} returned no chains for {symbol}"}

    strikes: list[dict[str, Any]] = []
    forward: Optional[float] = None
    greeks = False
    expiries = 0
    for chain in data.chains:
        expiries += 1
        forward = forward if forward is not None else _finite(getattr(chain, "forward", None))
        stamp = _expiry_ms(getattr(chain, "expiry", ""))
        for leg in chain.legs:
            gamma = _finite(getattr(leg, "gamma", None))
            greeks = greeks or gamma is not None
            strikes.append({
                "price": _finite(getattr(leg, "strike", None)) or 0.0,
                "gamma": gamma or 0.0,
                "oi": _finite(getattr(leg, "oi", None)) or 0.0,
                "open_interest": _finite(getattr(leg, "oi", None)) or 0.0,
                "side": str(getattr(leg, "side", "") or "call").lower(),
                "iv": _finite(getattr(leg, "iv", None)),
                "delta": _finite(getattr(leg, "delta", None)),
                "vega": _finite(getattr(leg, "vega", None)),
                "theta": _finite(getattr(leg, "theta", None)),
                "volume": _finite(getattr(leg, "volume", None)),
                "mid": _mid(leg),
                "expiry_ms": stamp,
                "expiry": str(getattr(chain, "expiry", "") or ""),
            })
    if not strikes:
        return {"ok": False, "source": source, "error": f"{source} returned {expiries} chain(s) with no legs"}
    return {"ok": True, "strikes": strikes, "spot": forward or 0.0,
            "spot_from": "the venue's forward" if forward else "",
            "expiry": str(getattr(data.chains[0], "expiry", "") or ""), "expiry_ms": None,
            "carries_greeks": bool(greeks), "multiplier": EQUITY_MULTIPLIER, "currency": "",
            "note": f"{expiries} expiries read from {source}", "quoted_sides": len(strikes)}


def load_chain(symbol: str, source: str, *, expiry: str = "", width: int = 0,
               spot: float = 0.0) -> dict[str, Any]:
    """One instrument's option chain, in the shape the analytics modules take.

    Returns ``{"ok": True, strikes, spot, spot_from, carries_greeks, multiplier, note, …}`` or
    ``{"ok": False, "error": <the venue's own words, or the missing input named>}``. Blocking.
    """
    text = str(symbol or "").strip().upper()
    if not text:
        return {"ok": False, "error": "no symbol given"}
    src = str(source or "deribit").strip().lower()
    if src not in SOURCES:
        return _unknown_source(src)

    out = _deribit_chain(text, expiry, width) if src == "deribit" else _equity_chain(text, src)
    if not out.get("ok"):
        return out

    hint = _finite(spot) or 0.0
    if hint > 0:
        out["spot"], out["spot_from"] = hint, "the request"
    elif not out.get("spot"):
        parity = _parity_spot(out["strikes"])
        if parity:
            out["spot"], out["spot_from"] = parity, "put-call parity (the venue sent no forward)"
    out["source"] = src
    out["symbol"] = text
    return out


def _require_spot(chain: dict[str, Any]) -> Optional[str]:
    """GEX and a surface both need the underlying price; name what is missing, never guess."""
    if _finite(chain.get("spot")):
        return None
    return ("the underlying price is unknown — pass ?spot= (the app's own last price for the "
            "instrument) or pick a source that reports the forward")


# ── GEX ──────────────────────────────────────────────────────────────────────────

@router.get("/gex/{symbol}")
async def options_gex(symbol: str, source: str = "deribit", expiry: str = "",
                      width: int = Query(default=0, ge=0, le=30),
                      spot: float = Query(default=0.0, ge=0.0),
                      wall_quantile: float = Query(default=0.95, ge=0.5, le=0.999)) -> dict[str, Any]:
    """Dealer gamma per strike, the zero-gamma line and the call/put walls for one instrument.

    The chain must carry gammas. Deribit sends them per instrument; Market Data sends them with
    its OPRA chains; Tradier's chain carries IV and open interest but no greeks, and this route
    says exactly that instead of returning a map of zeros.

    Units, stated once so no client has to guess: ``iv`` and ``atm_iv``/``skew_25d`` are FRACTIONS
    (0.205 = 20.5%, see ``iv_unit``), and ``unit`` names what one unit of ``dex``/``gamma_exp``/
    ``total_dex`` is — the coin a crypto contract is written on, or shares for an OPRA 100-share
    lot. Both figures are per 1-point move of the underlying.
    """
    from orderflow_system.atlas.gex import compute_gex

    chain = await asyncio.to_thread(load_chain, symbol, source, expiry=expiry, width=width, spot=spot)
    if not chain.get("ok"):
        return {**chain, "symbol": str(symbol or "").upper()}
    if str(chain.get("source")) != "deribit" and not chain.get("carries_greeks"):
        return {"ok": False, "symbol": chain["symbol"], "source": chain["source"], "strikes": 0,
                "error": (f"{chain['source']}'s chain carries implied volatility, open interest and "
                          "volume but no gammas — GEX needs a chain with greeks (Deribit, or "
                          "Market Data). The Volatility view reads this chain happily.")}
    missing = _require_spot(chain)
    if missing:
        return {"ok": False, "symbol": chain["symbol"], "source": chain["source"], "strikes": 0,
                "error": missing}

    result = compute_gex(chain["strikes"], spot=float(chain["spot"]),
                         multiplier=float(chain["multiplier"]), wall_quantile=float(wall_quantile))
    rows, total = _strike_rows(result.per_strike)
    # The engine's GEX map has no use for traded volume, the table shows it beside the open
    # interest — so the chain's own number rides along, matched on the strike and side the two
    # rows describe.
    volumes = {(round(float(s.get("price") or 0.0), 6), str(s.get("side") or "")): s.get("volume")
               for s in chain["strikes"]}
    for row in rows:
        row["volume"] = volumes.get((round(float(row.get("strike") or 0.0), 6), str(row.get("side") or "")))
    return {
        "ok": True, "symbol": chain["symbol"], "source": chain["source"],
        "expiry": chain.get("expiry") or "", "spot": result.spot, "spot_from": chain.get("spot_from") or "",
        "multiplier": result.multiplier, "n_strikes": result.n_strikes,
        "rows_shown": len(rows), "rows_total": total,
        "zero_gamma": result.zero_gamma_level,
        "call_walls": result.call_walls[:5], "put_walls": result.put_walls[:5],
        "total_dex": result.total_dex, "total_vex": result.total_vex,
        "total_theta": result.total_theta, "total_vanna": result.total_vanna,
        "total_charm": result.total_charm, "put_call_oi": result.put_call_oi,
        # Which of the greek families the venue actually published. A 0.0 total for something the
        # venue never sent would read as a measured flat exposure; the panel says "not published"
        # instead, and this flag is how it knows.
        "carried": {"vanna": any(r.get("vanna") is not None for r in rows),
                    "charm": any(r.get("charm") is not None for r in rows)},
        "call_oi": result.call_oi, "put_oi": result.put_oi,
        "atm_iv": result.atm_iv, "skew_25d": result.skew_25d,
        # What the numbers above are made of: iv as a fraction, exposures in `unit` per 1-point
        # move. The panel prints both from these two fields instead of guessing from magnitudes.
        "iv_unit": "fraction", "unit": _exposure_unit(chain),
        "per_strike": rows,
        "note": (chain.get("note") or "") +
                (" · gamma exposure is per 1-point move; the walls are the top "
                 f"{1 - float(wall_quantile):.0%} of each side's |gamma| beyond spot") ,
    }


# ── Volatility surface ───────────────────────────────────────────────────────────

@router.get("/volatility/{symbol}")
async def options_volatility(symbol: str, source: str = "deribit", expiry: str = "",
                             width: int = Query(default=0, ge=0, le=30),
                             spot: float = Query(default=0.0, ge=0.0)) -> dict[str, Any]:
    """The IV smile per expiry, the 25-delta skew and the term structure for one instrument.

    IV is the one thing every source here does carry, so this route works on all three — the
    difference is only how many expiries the venue sends and whether a single-smile view or the
    whole surface is meaningful.

    Every IV field on the wire — ``iv`` per strike, ``atm_iv``, ``skew_25d``, ``put_25d_iv``,
    ``call_25d_iv`` and the term structure's copies — is a FRACTION (0.205 = 20.5%, see
    ``iv_unit``), the unit the engines take and their tests pin.
    """
    from orderflow_system.atlas.volatility import compute_volatility

    chain = await asyncio.to_thread(load_chain, symbol, source, expiry=expiry, width=width, spot=spot)
    if not chain.get("ok"):
        return {**chain, "symbol": str(symbol or "").upper()}
    missing = _require_spot(chain)
    if missing:
        return {"ok": False, "symbol": chain["symbol"], "source": chain["source"], "strikes": 0,
                "error": missing}
    if not any(row.get("iv") for row in chain["strikes"]):
        return {"ok": False, "symbol": chain["symbol"], "source": chain["source"], "strikes": 0,
                "error": (f"{chain['source']}'s chain carries no implied volatility for this "
                          "instrument right now — nothing to put on a surface")}

    result = compute_volatility(chain["strikes"], spot=float(chain["spot"]),
                                multiplier=float(chain["multiplier"]))
    smile, total = _strike_rows(result.smile)
    return {
        "ok": True, "symbol": chain["symbol"], "source": chain["source"],
        "expiry": chain.get("expiry") or "", "spot": result.spot, "spot_from": chain.get("spot_from") or "",
        "n_strikes": result.n_strikes, "n_expiries": result.n_expiries,
        "rows_shown": len(smile), "rows_total": total,
        "atm_iv": result.atm_iv, "skew_25d": result.skew_25d,
        "put_25d_iv": result.put_25d_iv, "call_25d_iv": result.call_25d_iv,
        "iv_unit": "fraction",
        # The chain's own desk numbers (P/C OI, IV range, days to expiry) — see _chain_stats.
        **_chain_stats(chain),
        "smile": smile, "expiries": result.term_structure, "term_structure": result.term_structure,
        # The chain's provenance note AND the surface's own (§148 / T7-F10: e.g. the 25Δ wings were
        # picked by a moneyness proxy because the chain carried no deltas) — the route used to drop
        # the surface's note on the floor, so the panel could not say it.
        "note": ((chain.get("note") or "")
                 + (" · " + result.note if result.note else "")),
    }


# ── Option flow ──────────────────────────────────────────────────────────────────

def _flow_trades_deribit(symbol: str, count: int) -> dict[str, Any]:
    """Deribit's most recent option prints for a currency, as ``OptionTrade`` dicts.

    One request for the whole currency's prints (`get_last_trades_by_currency`, newest first),
    which is the honest shape for a flow read: a per-instrument walk would cost one request per
    contract and still only see the strikes this build happens to know.
    """
    from orderflow_system.desktop import deribit as deribit_mod

    currency = deribit_mod.currency_for(symbol)
    if currency is None:
        return {"ok": False, "error": (f"crypto option prints only via Deribit — no option trade "
                                       f"feed for {symbol}")}
    url = (f"{deribit_mod.BASE}/get_last_trades_by_currency?currency={currency}"
           f"&kind=option&count={int(count)}&sorting=desc")
    payload, error = deribit_mod.get_json(url)
    if error:
        return {"ok": False, "error": f"Deribit prints unavailable: {error}"}
    rows = ((payload or {}).get("result") or {}).get("trades") or []
    trades: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parts = str(row.get("instrument_name") or "").split("-")
        if len(parts) < 4:                        # BTC-26SEP25-68000-C
            continue
        side = {"C": "call", "P": "put"}.get(parts[3].upper())
        if side is None:
            continue
        amount = _finite(row.get("amount"))
        price = _finite(row.get("price"))
        stamp = _finite(row.get("timestamp"))
        if amount is None or price is None or stamp is None:
            continue
        direction = str(row.get("direction") or "").lower()
        trades.append({
            "symbol": currency, "expiry": parts[1], "strike": _finite(parts[2]) or 0.0,
            "side": side, "size": amount, "price": price, "timestamp_ms": int(stamp),
            "aggressor": direction if direction in ("buy", "sell") else None,
            "oi_at_trade": None, "instrument": str(row.get("instrument_name") or ""),
        })
    trades.sort(key=lambda t: t["timestamp_ms"])
    return {"ok": True, "currency": currency, "trades": trades, "prints": len(rows)}


def _flow_spot(currency: str) -> Optional[float]:
    """The underlying's mark price, so premium can be quoted in money instead of in coin.

    One cached request (3 s TTL) for the currency's perpetual — the contract every crypto desk
    quotes option premium against. Unavailable → None, and the panel prints premium in the
    contract's own currency rather than inventing a dollar figure from a stale number.
    """
    from orderflow_system.desktop import deribit as deribit_mod

    try:
        row = deribit_mod.ticker(f"{str(currency or '').upper()}-PERPETUAL")
    except Exception:  # noqa: BLE001 — a missing spot must never fail the flow read
        return None
    if not isinstance(row, dict) or not row.get("ok"):
        return None
    return _finite(row.get("mark")) or _finite(row.get("price"))


@router.get("/flow/{symbol}")
async def options_flow(symbol: str, source: str = "deribit",
                       count: int = Query(default=100, ge=10, le=500),
                       window_ms: int = Query(default=900_000, ge=60_000, le=86_400_000)) -> dict[str, Any]:
    """Sweep / block / unusual-premium classification of an instrument's option prints.

    Only Deribit publishes a keyless public option-print stream today, and this build reads it.
    The equity venues are named with what would be needed rather than answered with sample data:
    a table of invented sweeps is worse than an empty one.

    The payload carries both readings of the same tape: the print-by-print ``tape`` (newest first,
    each print tagged with the class the engine gave it) and the classified lists the summary cards
    draw. ``spot`` is the underlying the premium is quoted against; when it is missing the premium
    stays in the contract's own currency and says so.
    """
    from orderflow_system.atlas.option_flow import classify_stream

    text = str(symbol or "").strip().upper()
    src = str(source or "deribit").strip().lower()
    if src not in SOURCES:
        return _unknown_source(src)
    if src != "deribit":
        return {"ok": False, "symbol": text, "source": src, "trades": 0,
                "error": (f"no live option-print feed is wired for {src} in this build — Deribit's "
                          "public option tape is the one print source the app reads today")}

    out = await asyncio.to_thread(_flow_trades_deribit, text, count)
    if not out.get("ok"):
        return {"ok": False, "symbol": text, "source": src, "trades": 0, "error": out.get("error")}

    now_ms = int(time.time() * 1000)
    trades = [t for t in out["trades"] if now_ms - t["timestamp_ms"] <= int(window_ms)]
    summary = classify_stream(trades)

    # The tape the panel draws: every print in the window, newest first, tagged with the class the
    # engine gave it. Sweep beats block beats unusual when a print qualifies for more than one — a
    # print swept across strikes is read as a sweep first, and the tag states the strongest read.
    def _key(ts: Any, strike: Any, side: Any, price: Any, size: Any) -> tuple:
        return (int(ts), round(float(strike), 8), str(side), round(float(price), 12), round(float(size), 8))

    def _trade_key(trade: Any) -> tuple:
        return _key(getattr(trade, "timestamp_ms", 0), getattr(trade, "strike", 0.0),
                    getattr(trade, "side", ""), getattr(trade, "price", 0.0), getattr(trade, "size", 0.0))

    tagged: dict[tuple, str] = {}
    for sweep in summary.sweeps:
        for sub in sweep.trades:
            tagged[_trade_key(sub)] = "sweep"
    for change in summary.blocks:
        tagged.setdefault(_trade_key(change.trade), "block")
    for change in summary.unusual_premium:
        tagged.setdefault(_trade_key(change.trade), "unusual")

    spot = _flow_spot(out.get("currency") or "")
    tape = [{"expiry": t["expiry"], "strike": t["strike"], "side": t["side"], "size": t["size"],
             "price": t["price"], "timestamp_ms": t["timestamp_ms"], "aggressor": t.get("aggressor"),
             "instrument": t.get("instrument"),
             "class": tagged.get(_trade_key(t), "routine"),
             "premium": t["size"] * t["price"]}
            for t in sorted(trades, key=lambda t: t["timestamp_ms"], reverse=True)][:TAPE_ROWS]
    return {
        "ok": True, "symbol": text, "source": src, "currency": out["currency"],
        "window_ms": int(window_ms), "window_start_ms": summary.window_start_ms,
        "window_end_ms": summary.window_end_ms, "total_trades": summary.total_trades,
        "prints_read": out["prints"], "n_sweeps": summary.n_sweeps, "n_blocks": summary.n_blocks,
        "n_unusual": summary.n_unusual, "n_routine": summary.n_routine,
        "spot": spot, "spot_from": (f"{str(out.get('currency') or '').upper()}-PERPETUAL" if spot else ""),
        "premium_unit": "USD" if spot else str(out.get("currency") or "").lower(),
        "tape": tape, "tape_shown": len(tape),
        "sweeps": [{"sweep_id": s.sweep_id, "start_ms": s.start_ms, "end_ms": s.end_ms,
                    "strikes": s.strikes, "total_size": s.total_size,
                    "total_premium": s.total_premium, "n_trades": len(s.trades)} for s in summary.sweeps],
        "blocks": [{"symbol": text, "expiry": c.trade.expiry, "strike": c.trade.strike, "side": c.trade.side,
                    "size": c.trade.size, "price": c.trade.price, "reason": c.reason,
                    "aggressor": c.trade.aggressor, "timestamp_ms": c.trade.timestamp_ms}
                   for c in summary.blocks],
        "unusual_premium": [{"symbol": text, "expiry": c.trade.expiry, "strike": c.trade.strike,
                             "side": c.trade.side, "size": c.trade.size, "price": c.trade.price,
                             "reason": c.reason, "aggressor": c.trade.aggressor,
                             "timestamp_ms": c.trade.timestamp_ms}
                            for c in summary.unusual_premium],
        "routine": summary.n_routine,
        "note": ("Deribit's public option tape, newest first; the classification rules live in "
                 "atlas/option_flow.py and are pinned by test_option_flow.py"),
    }
