"""Alpaca message → internal model normalisation (plan T21).

Alpaca publishes three market-data families, each with its own field names:

    stocks   trades  T,S,i,x,p,s,c,t,z        quotes  T,S,ax,ap,as,bx,bp,bs,t
    crypto   trades  T,S,p,s,t,i,tks          quotes  T,S,bp,bs,ap,as,t
    options  trades  T,S,t,p,s,x,c            quotes  T,S,ax,ap,as,bx,bp,bs,t

Everything here is a pure function: message dict in, ``Tick`` / ``Quote`` out, no
network, no state. That is what makes the recorded fixtures in
``test_alpaca_normalize.py`` enough to pin the mapping.

Two honest notes:

* Alpaca does not publish the aggressor for equity trades. The side is therefore
  classified against the last known mid (the tick rule the analytics already use):
  a print at or above the mid is a buy, below it is a sell. Crypto messages carry
  ``tks`` (tick side, ``B``/``S``) when the venue knows, and that wins.
* Timestamps arrive as RFC3339 (``2026-09-15T13:30:00.123456789Z``). Nanosecond
  precision is truncated to milliseconds, which is all the candles use.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Optional

from orderflow_system.data.models import Quote, Side, Tick

# ──────────────────────────────────────────────
# Timestamps
# ──────────────────────────────────────────────

_NS = re.compile(r"(\.\d{3})\d+")


def parse_ts_ms(value: Any) -> int:
    """RFC3339 (or epoch seconds/ms) → unix milliseconds. 0 when unusable."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        v = float(value)
        return int(v * 1000) if v < 1e11 else int(v)          # seconds vs ms
    text = str(value).strip()
    if not text:
        return 0
    text = _NS.sub(r"\1", text.replace(" ", "T"))             # ns → ms
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# ──────────────────────────────────────────────
# Side classification
# ──────────────────────────────────────────────

_TICK_SIDE = {"b": Side.BUY, "buy": Side.BUY, "a": Side.SELL, "s": Side.SELL, "sell": Side.SELL}


def classify_side(price: float, mid: Optional[float], tick_side: Any = None) -> Side:
    """Aggressor side: the venue's tick side when it exists, else the tick rule.

    Alpaca's equity feed carries no aggressor flag at all, so a print at or above
    the mid counts as a buy. With no reference price the print is called a buy —
    an arbitrary default, documented rather than hidden, because every downstream
    reading (delta, CVD, footprint) is a *difference* and a systematically inverted
    tape would be visible immediately.
    """
    if tick_side is not None:
        mapped = _TICK_SIDE.get(str(tick_side).strip().lower())
        if mapped is not None:
            return mapped
    if mid:
        return Side.BUY if price >= mid else Side.SELL
    return Side.BUY


def _num(value: Any, default: float = 0.0) -> float:
    """A finite float, or ``default``.

    ``json`` accepts the bare tokens ``NaN``/``Infinity``, and a comparison like ``x <= 0``
    cannot catch them (every comparison with NaN is False) — so the mere conversion is not
    enough; a non-finite venue value must fall back here, before it can reach anything.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


# ──────────────────────────────────────────────
# Trades → Tick
# ──────────────────────────────────────────────

def normalize_stock_trade(msg: dict[str, Any], mid: Optional[float] = None,
                          symbol: str = "") -> Optional[Tick]:
    """{'T':'t','S':'AAPL','i':123,'p':182.4,'s':100,'t':'…Z'} → Tick."""
    if not isinstance(msg, dict) or msg.get("p") in (None, ""):
        return None
    price = _num(msg.get("p"))
    if price <= 0:
        return None
    stamp = parse_ts_ms(msg.get("t"))
    if stamp <= 0:
        # A present-but-unusable `t` used to become timestamp_ms=0 — a 1970 candle and phantom
        # prints inside the live bar. Dropped, exactly like normalize_bar already drops ts == 0
        # (audit D-06); the caller counts the drop.
        return None
    return Tick(
        timestamp_ms=stamp,
        price=price,
        size=_num(msg.get("s")),
        side=classify_side(price, mid),
        trade_id=str(msg.get("i") or ""),
    )


def normalize_crypto_trade(msg: dict[str, Any], mid: Optional[float] = None,
                           symbol: str = "") -> Optional[Tick]:
    """Crypto trades add ``tks`` (tick side) when the venue publishes it."""
    tick = normalize_stock_trade(msg, mid=mid, symbol=symbol)
    if tick is None:
        return None
    tick.side = classify_side(tick.price, mid, msg.get("tks") or msg.get("tick_side"))
    return tick


def normalize_options_trade(msg: dict[str, Any], mid: Optional[float] = None,
                            symbol: str = "") -> Optional[Tick]:
    """Options trades carry the same price/size/timestamp fields as stocks."""
    return normalize_stock_trade(msg, mid=mid, symbol=symbol)


# ──────────────────────────────────────────────
# Quotes → Quote
# ──────────────────────────────────────────────

def normalize_quote(msg: dict[str, Any], symbol: str = "") -> Optional[Quote]:
    """{'ax','ap','as','bx','bp','bs'} → Quote. Either side may be missing."""
    if not isinstance(msg, dict):
        return None
    bid = _num(msg.get("bp") if msg.get("bp") is not None else msg.get("bid_price"))
    ask = _num(msg.get("ap") if msg.get("ap") is not None else msg.get("ask_price"))
    bid_size = _num(msg.get("bs") if msg.get("bs") is not None else msg.get("bid_size"))
    ask_size = _num(msg.get("as") if msg.get("as") is not None else msg.get("ask_size"))
    if not bid and not ask:
        return None
    return Quote(
        timestamp_ms=parse_ts_ms(msg.get("t")),
        bid_price=bid,
        bid_size=bid_size,
        ask_price=ask,
        ask_size=ask_size,
        symbol=str(msg.get("S") or symbol or ""),
    )


# ──────────────────────────────────────────────
# Snapshot / bar helpers
# ──────────────────────────────────────────────

def normalize_snapshot_trade(payload: dict[str, Any], symbol: str = "") -> Optional[Tick]:
    """A REST snapshot carries the last trade under its own key."""
    snap = (payload or {}).get("latestTrade") or (payload or {}).get("latest_trade") or {}
    if not isinstance(snap, dict):
        return None
    snap = dict(snap)
    snap.setdefault("S", symbol)
    return normalize_stock_trade(snap, symbol=symbol)


def normalize_snapshot_quote(payload: dict[str, Any], symbol: str = "") -> Optional[Quote]:
    snap = (payload or {}).get("latestQuote") or (payload or {}).get("latest_quote") or {}
    if not isinstance(snap, dict):
        return None
    snap = dict(snap)
    snap.setdefault("S", symbol)
    return normalize_quote(snap, symbol=symbol)


def normalize_bar(bar: dict[str, Any], symbol: str = "") -> Optional[dict[str, Any]]:
    """Alpaca bar → the shape ``CandleBuilder``/chart code already uses."""
    if not isinstance(bar, dict):
        return None
    ts = parse_ts_ms(bar.get("t"))
    price = _num(bar.get("c"))
    if not ts or price <= 0:
        return None
    return {
        "time": ts // 1000,
        "timestamp_ms": ts,
        "symbol": str(bar.get("S") or symbol or ""),
        "open": _num(bar.get("o")),
        "high": _num(bar.get("h")),
        "low": _num(bar.get("l")),
        "close": price,
        "volume": _num(bar.get("v")),
        "vwap": _num(bar.get("vw")) or None,
        "trades": int(_num(bar.get("n"))) if bar.get("n") is not None else None,
    }


#: Channel → normaliser, so the stream client maps messages by ``T`` in one place.
NORMALIZERS = {
    "t": normalize_stock_trade,      # stock trade
    "q": normalize_quote,            # stock/option quote
    "b": None,                       # minute bar — handled by normalize_bar
}
