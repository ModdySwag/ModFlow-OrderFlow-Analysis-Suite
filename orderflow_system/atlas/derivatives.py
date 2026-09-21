"""Crypto derivatives context — funding, open interest and basis, four venues side by side.

Why this module exists: on a perpetual, the price on the chart is only half the trade. Funding is
what it costs to keep the position overnight, open interest is how much money is committed to it,
and the basis (the perp's mark against its index) says which side is paying for the privilege. The
tape this app already reads does not carry any of it, so a footprint cannot tell a squeeze building
in the book from one being *financed* out of the funding rate. CoinGlass sells this layer on its own;
here it sits next to the depth it is meant to explain.

The four venues, all public and keyless, and the exact route each read uses (each verified live
against the venue before this file was written — the captured shapes are the fixtures in
``orderflow_system/test_derivatives.py``)::

    bybit        GET {BYBIT_REST}/v5/market/tickers?category=linear&symbol=BTCUSDT
                 fundingRate, fundingIntervalHour, nextFundingTime, openInterest,
                 openInterestValue, indexPrice, markPrice — all of it in one row
    binance      GET {BINANCE_REST}/fapi/v1/premiumIndex?symbol=BTCUSDT
                 lastFundingRate, markPrice, indexPrice, nextFundingTime (no interval in the payload)
                 GET {BINANCE_REST}/fapi/v1/openInterest?symbol=BTCUSDT
                 openInterest in coin terms; the venue publishes no USD figure, so the row's USD
                 value is this app's arithmetic on the venue's own open interest and mark
    okx          GET {OKX_REST}/api/v5/public/funding-rate?instId=BTC-USDT-SWAP
                 GET {OKX_REST}/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP
                 GET {OKX_REST}/api/v5/public/mark-price?instType=SWAP&instId=BTC-USDT-SWAP
                 GET {OKX_REST}/api/v5/market/index-tickers?instId=BTC-USDT
    hyperliquid  POST {HYPERLIQUID_REST}/info  {"type":"metaAndAssetCtxs"} — one document for every
                 listed coin: funding (per hour), openInterest (in coin), markPx, oraclePx, premium.
                 The venue serves this route by POST only, so the URL this module's one fetch seam
                 receives carries the request as ``?type=…`` and ``default_fetch`` turns it into the
                 JSON body the venue wants. The seam stays one argument wide, so a test stub is one
                 lambda.

Every reading, with the rule that keeps it honest:

* **funding** is a fraction of the position per settlement, reported three ways: the venue's own rate,
  the same rate as a percentage, and annualised — ``rate x (24 / interval) x 365 x 100``. The interval
  is the venue's own when its payload names one (bybit's ``fundingIntervalHour``, okx's settlement
  spacing) and otherwise the venue's documented default (8 h; hyperliquid settles hourly). Funding is
  the ONLY number here that annualises cleanly, because it really does repeat.
* **open interest** is reported in the unit the venue publishes (the coin, and okx's ``oiCcy`` — never
  its contract count) plus USD when the venue gives one or it can be computed from the venue's own
  numbers. Its change is measured against this app's own stored samples: no venue here publishes a
  change, and a "24 h" figure derived from one snapshot would be an invention. The read carries the
  window it actually managed ("on the day" only when a day really was watched).
* **basis** is the perp's mark against its index in basis points, plus the same figure annualised
  (x 365) as the desk shorthand for "if this premium held for a year" — a perp premium is not a
  yield, and the payload says so where it prints it.

Refusals: a venue that does not answer, does not list the instrument, or is not one of the four
becomes a row with ``ok: false`` and one plain sentence naming the venue and the reason. When no
venue answers at all the route answers ``{"ok": false, "detail": <those sentences joined>}``. Nothing
here ever raises into a panel, and nothing ever prints a stack trace.

Read-only apart from one POST that stores the venue LIST (the user's own choice); no key is read, no
file is written by the analysis, and the blocking venue I/O runs off the event loop. Network access
is exactly one injected seam — ``DerivativesService(fetch=...)``, whose real implementation is
``default_fetch`` — so the whole module is exercised offline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from typing import Any, Callable, Iterable, Optional, Sequence

from fastapi import APIRouter, Body, Query

logger = logging.getLogger(__name__)

# ── the venues as this module knows them ────────────────────────────────────────────────────────────

#: The venues this panel covers, in the order it offers them. Anything else is refused by name.
VENUES: tuple[str, ...] = ("bybit", "binance", "okx", "hyperliquid")

VENUE_LABELS: dict[str, str] = {
    "bybit": "Bybit",
    "binance": "Binance",
    "okx": "OKX",
    "hyperliquid": "Hyperliquid",
}

BYBIT_REST = "https://api.bybit.com"
BINANCE_REST = "https://fapi.binance.com"
OKX_REST = "https://www.okx.com"
HYPERLIQUID_REST = "https://api.hyperliquid.xyz"

USER_AGENT = "OrderFlow-Analysis-Pro/1.0 (derivatives context; public endpoints)"
TIMEOUT_S = 10.0

#: Settlement spacing, in hours, when the venue's payload does not name one. Bybit, Binance and OKX
#: quote a rate per 8 h for the perpetuals this suite streams; Hyperliquid settles hourly.
FUNDING_INTERVAL_H: dict[str, float] = {"bybit": 8.0, "binance": 8.0, "okx": 8.0, "hyperliquid": 1.0}

#: The annualising constant: hours in a year / hours per settlement, x100 for a percentage.
ANNUAL_HOURS = 24.0 * 365.0

#: Quote suffixes the suite's symbols carry — stripped to reach the coin a contract is written on.
QUOTE_SUFFIXES: tuple[str, ...] = ("USDT", "USDC", "USD", "PERP")

#: The one network seam: a URL in, a parsed JSON document out, raising on any failure.
Fetch = Callable[[str], Any]

#: The key the cross-venue USD total is stored under, beside the per-venue samples.
TOTAL_KEY = "*"


# ── settings ───────────────────────────────────────────────────────────────────────────────────────

DEFAULTS: dict[str, Any] = {
    "venues": list(VENUES),           # which venues the read asks, in the order it asks them
    "refresh_s": 60,                  # an OI snapshot is a slow number; the venues are public
    "oi_window_s": 86400,             # the window the OI change is measured over (a day)
    "crowded_apr_pct": 30.0,          # |annualised funding| past this is a crowded side
    "flat_apr_pct": 5.0,              # |annualised funding| under this is neither side paying much
    "history_max": 2880,              # OI samples kept per venue+instrument (2 days at 60 s)
}


def _num(value: Any) -> Optional[float]:
    """A JSON number that is safe to carry, or None — the gate every venue value passes."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _int(value: Any) -> Optional[int]:
    number = _num(value)
    return int(number) if number is not None else None


def _clamp_float(value: Any, default: float, low: float, high: float) -> float:
    number = _num(value)
    if number is None:
        return default
    return round(max(low, min(high, number)), 4)


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    number = _int(value)
    if number is None:
        return default
    return max(low, min(high, number))


def accepted_venues(raw: Any) -> tuple[list[str], list[str]]:
    """Split a requested venue list into (names this panel covers, names it does not).

    Accepts a list of names or one comma/space separated string (the panel's own input). Names are
    lower-cased, de-duplicated and kept in the order given; an unknown name is dropped and reported,
    never silently renamed onto a venue that does exist.
    """
    if isinstance(raw, str):
        entries: Iterable[Any] = raw.replace(",", " ").split()
    elif isinstance(raw, (list, tuple, set)):
        entries = raw
    else:
        entries = []
    kept: list[str] = []
    dropped: list[str] = []
    for entry in entries:
        name = str(entry or "").strip().lower()
        if not name:
            continue
        if name in VENUES:
            if name not in kept:
                kept.append(name)
        elif name not in dropped:
            dropped.append(name[:24])
    return kept, dropped


def clean(patch: Any) -> dict[str, Any]:
    """Coerce/clamp an incoming derivatives settings block onto ``DEFAULTS``. Never raises.

    An unrecognised venue name is dropped here and *reported by the POST route* rather than clamped
    onto a venue the user did not ask for; a block with no usable venue at all keeps the default
    four, because a panel with nothing enabled is a blank panel, not a preference.
    """
    raw = patch if isinstance(patch, dict) else {}
    venues, _dropped = accepted_venues(raw.get("venues"))
    crowded = _clamp_float(raw.get("crowded_apr_pct"), DEFAULTS["crowded_apr_pct"], 1.0, 1000.0)
    flat = _clamp_float(raw.get("flat_apr_pct"), DEFAULTS["flat_apr_pct"], 0.0, 100.0)
    return {
        "venues": venues or list(VENUES),
        "refresh_s": _clamp_int(raw.get("refresh_s"), DEFAULTS["refresh_s"], 10, 3600),
        "oi_window_s": _clamp_int(raw.get("oi_window_s"), DEFAULTS["oi_window_s"], 300, 604800),
        "crowded_apr_pct": crowded,
        "flat_apr_pct": min(flat, crowded),          # "flat" can never be looser than "crowded"
        "history_max": _clamp_int(raw.get("history_max"), DEFAULTS["history_max"], 60, 20000),
    }


# ── symbols ────────────────────────────────────────────────────────────────────────────────────────

def normalise_symbol(text: Any) -> str:
    return str(text or "").strip().upper()[:24]


def base_coin(instrument: Any) -> str:
    """``BTCUSDT`` / ``BTC-USDT-SWAP`` / ``BTC`` → ``BTC`` — the coin a contract is written on.

    The same rule ``data/okx_feed.py`` and ``data/hyperliquid_feed.py`` apply to route their frames,
    kept here so this module imports nothing from the feed stack.
    """
    text = normalise_symbol(instrument)
    if not text:
        return ""
    if text.endswith("-SWAP"):
        text = text[: -len("-SWAP")]
    if "-" in text:
        return text.split("-", 1)[0]
    for suffix in QUOTE_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def venue_instrument(venue: str, symbol: Any) -> str:
    """The suite symbol as the venue's own instrument id (``BTCUSDT`` → ``BTC-USDT-SWAP`` on OKX)."""
    text = normalise_symbol(symbol)
    if not text:
        return ""
    if venue == "okx":
        # An id already in venue form passes through: a made-up one could silently read the wrong
        # instrument, while the venue's own refusal is loud and lands in the row's sentence.
        if "-" in text or not text.endswith("USDT"):
            return text
        return f"{text[:-4]}-USDT-SWAP"
    if venue == "hyperliquid":
        return base_coin(text)
    return text


def venue_calls(venue: str, symbol: Any) -> tuple[tuple[str, str, bool], ...]:
    """The (call name, URL, required) triples one venue's read is made of, in order.

    ``required`` is about the ROW, not the venue: a read whose funding/price call fails has nothing to
    say about carry, while a read that only loses its open-interest call still answers funding and
    basis — and says which part is missing rather than zeroing it.
    """
    sym = venue_instrument(venue, symbol)
    quoted = urllib.parse.quote(sym, safe="")
    if venue == "bybit":
        return (("tickers", f"{BYBIT_REST}/v5/market/tickers?category=linear&symbol={quoted}", True),)
    if venue == "binance":
        return (("premium_index", f"{BINANCE_REST}/fapi/v1/premiumIndex?symbol={quoted}", True),
                ("open_interest", f"{BINANCE_REST}/fapi/v1/openInterest?symbol={quoted}", False))
    if venue == "okx":
        index = sym[: -len("-SWAP")] if sym.endswith("-SWAP") else sym
        return (("funding_rate", f"{OKX_REST}/api/v5/public/funding-rate?instId={quoted}", True),
                ("mark_price", f"{OKX_REST}/api/v5/public/mark-price?instType=SWAP&instId={quoted}", False),
                ("index_tickers", f"{OKX_REST}/api/v5/market/index-tickers"
                                  f"?instId={urllib.parse.quote(index, safe='')}", False),
                ("open_interest", f"{OKX_REST}/api/v5/public/open-interest"
                                  f"?instType=SWAP&instId={quoted}", False))
    if venue == "hyperliquid":
        return (("meta_contexts", f"{HYPERLIQUID_REST}/info?type=metaAndAssetCtxs", True),)
    return ()


# ── arithmetic (pure; the numbers every row and sentence comes from) ────────────────────────────────

def annualise_pct(rate: Any, interval_h: Any) -> Optional[float]:
    """A per-settlement funding rate as a yearly percentage.

    ``rate x (24 / interval) x 365 x 100``: 0.0001 per 8 h is 10.95%/yr, and the same rate per hour
    would be 87.6%/yr — which is why the interval travels with the rate everywhere in this module.
    """
    r, hours = _num(rate), _num(interval_h)
    if r is None or hours is None or hours <= 0:
        return None
    return r * (ANNUAL_HOURS / hours) * 100.0


def basis_bps(mark: Any, index: Any) -> Optional[float]:
    """The perp's mark against its index, in basis points (10 000 x the fraction)."""
    m, i = _num(mark), _num(index)
    if m is None or i is None or i <= 0 or m <= 0:
        return None
    return (m - i) / i * 10_000.0


def basis_apr_pct(bps: Any) -> Optional[float]:
    """Basis annualised as if the premium held for a year — a shorthand, never a yield.

    A perpetual has no expiry to price against, so there is no honest "carry" reading behind this
    number; it is printed with that sentence next to it wherever it appears.
    """
    value = _num(bps)
    if value is None:
        return None
    return value / 10_000.0 * 365.0 * 100.0


def _median(values: Sequence[float]) -> Optional[float]:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def oi_change(series: Iterable[tuple[Any, Any]], window_s: Any, now_ms: int,
              min_span_s: Any = None) -> dict[str, Any]:
    """Open interest's move over ``window_s``, from this app's own samples.

    ``series`` is an iterable of ``(ts_ms, value)`` pairs in any order. The newest sample at or before
    ``now_ms`` is the current reading; the baseline is the newest sample at or before
    ``now_ms - window_s`` when the series reaches that far back, and the oldest sample otherwise — in
    which case ``window_limited`` is True and the caller says which window it *really* measured.

    Fewer than two usable samples, or a span under ``min_span_s`` (default: 60 s, or a twentieth of
    the window), answers ``pct: None`` with a reason instead of a number: an open-interest change
    computed across two samples a second apart is noise dressed as a statistic.
    """
    window = max(0.0, _num(window_s) or 0.0)
    floor_s = _num(min_span_s)
    if floor_s is None:
        floor_s = max(60.0, window / 20.0)
    samples = sorted((int(ts), float(value))
                     for ts, value in (series or ())
                     if _num(ts) is not None and _num(value) is not None
                     and float(value) > 0 and int(ts) <= now_ms)
    out: dict[str, Any] = {"pct": None, "baseline_ms": None, "span_s": None, "samples": len(samples),
                           "window_limited": False, "reason": ""}
    if len(samples) < 2:
        out["reason"] = "only one open-interest sample so far" if samples else "no open-interest samples yet"
        return out
    latest_ts, latest = samples[-1]
    target = now_ms - window * 1000.0
    older = [row for row in samples if row[0] <= target]
    baseline = older[-1] if older else samples[0]
    out["window_limited"] = not older
    span_ms = float(latest_ts - baseline[0])
    if baseline[1] <= 0 or span_ms < floor_s * 1000.0:
        out["reason"] = f"only {round(span_ms / 1000.0)} s of samples so far"
        return out
    out["pct"] = round((latest - baseline[1]) / baseline[1] * 100.0, 4)
    out["baseline_ms"] = baseline[0]
    out["span_s"] = round(span_ms / 1000.0, 1)
    return out


# ── the venue parsers (pure: a payload dict in, fields out) ─────────────────────────────────────────

#: The fields a parsed venue payload may carry. Everything else a parser learns ends up in notes.
FIELD_KEYS: tuple[str, ...] = ("funding_rate", "funding_interval_h", "next_funding_ms", "mark", "index",
                               "open_interest", "open_interest_unit", "open_interest_usd", "ts_ms")


def _fields(**values: Any) -> dict[str, Any]:
    out: dict[str, Any] = {key: None for key in FIELD_KEYS}
    out.update({key: value for key, value in values.items() if key in out})
    return out


def _problem(sentence: str, notes: Optional[list[str]] = None) -> dict[str, Any]:
    return {"fields": _fields(), "problem": sentence, "notes": list(notes or [])}


def _ok(fields: dict[str, Any], notes: Optional[list[str]] = None) -> dict[str, Any]:
    return {"fields": fields, "problem": "", "notes": list(notes or [])}


def _env_data(payload: Any) -> list[dict[str, Any]]:
    """The ``data`` array of an OKX envelope, or [] — every OKX answer is that shape."""
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _okx_refusal(payload: Any, label: str) -> str:
    """OKX says "no" inside a 200 response: ``code`` is the venue's own error number."""
    code = str((payload or {}).get("code") or "0") if isinstance(payload, dict) else "0"
    message = str((payload or {}).get("msg") or "no message") if isinstance(payload, dict) else "no message"
    return f"{label} answered code {code}: {message}"


def parse_bybit(payloads: dict[str, Any], instrument: str = "",
                *, now_ms: Optional[int] = None) -> dict[str, Any]:
    """Bybit v5 ``/v5/market/tickers?category=linear`` — carry, OI and both prices in one row."""
    payload = payloads.get("tickers")
    if not isinstance(payload, dict):
        return _problem("the venue's ticker payload did not arrive")
    code = str(payload.get("retCode") or "0")
    if code not in ("0", ""):
        return _problem(f"Bybit answered retCode {code}: {payload.get('retMsg') or 'no message'}")
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    rows = [row for row in (result.get("list") or []) if isinstance(row, dict)]
    if not rows:
        return _problem(f"Bybit's ticker list did not carry {instrument or 'this instrument'}")
    row = rows[0]
    named_interval = _num(row.get("fundingIntervalHour"))
    interval = named_interval if named_interval and 0 < named_interval <= 24 else None
    notes: list[str] = []
    oi = _num(row.get("openInterest"))
    return _ok(_fields(
        funding_rate=_num(row.get("fundingRate")),
        funding_interval_h=interval,
        next_funding_ms=_int(row.get("nextFundingTime")),
        mark=_num(row.get("markPrice")),
        index=_num(row.get("indexPrice")),
        open_interest=oi,
        open_interest_unit=base_coin(instrument) if oi is not None else "",
        #: Bybit's own USD figure — not this app's arithmetic on somebody else's numbers.
        open_interest_usd=_num(row.get("openInterestValue")),
        ts_ms=_int(payload.get("time")),
    ), notes)


def parse_binance(payloads: dict[str, Any], instrument: str = "",
                  *, now_ms: Optional[int] = None) -> dict[str, Any]:
    """Binance USDT-M: ``premiumIndex`` for carry and prices, ``openInterest`` for the size."""
    premium = payloads.get("premium_index")
    if not isinstance(premium, dict):
        return _problem("the venue's premium-index payload did not arrive")
    if "symbol" not in premium:
        return _problem(str(premium.get("msg") or "Binance did not answer with a premium index"))
    mark, index = _num(premium.get("markPrice")), _num(premium.get("indexPrice"))
    notes: list[str] = []
    interest = payloads.get("open_interest")
    oi = _num(interest.get("openInterest")) if isinstance(interest, dict) else None
    oi_usd: Optional[float] = None
    if oi is not None and mark:
        # The venue publishes open interest in coin terms only: this is this app's arithmetic, the
        # row says so — and Hyperliquid's own computed figure says so too (§148 T5-F-09).
        oi_usd = round(oi * mark, 4)
        notes.append("open interest in USD is computed from this venue's own open interest and mark")
    if interest is not None and not isinstance(interest, dict):
        notes.append("the venue's open-interest payload did not arrive — the row carries no size")
    if _num(premium.get("lastFundingRate")) is not None:
        notes.append("Binance publishes no funding interval; the row assumes its 8 h default")
    return _ok(_fields(
        funding_rate=_num(premium.get("lastFundingRate")),
        next_funding_ms=_int(premium.get("nextFundingTime")),
        mark=mark,
        index=index,
        open_interest=oi,
        open_interest_unit=base_coin(instrument) if oi is not None else "",
        open_interest_usd=oi_usd,
        ts_ms=_int(premium.get("time")) or _int(interest.get("time") if isinstance(interest, dict) else None),
    ), notes)


def parse_okx(payloads: dict[str, Any], instrument: str = "",
              *, now_ms: Optional[int] = None) -> dict[str, Any]:
    """OKX USDT swaps: a funding envelope, an OI envelope, the mark, and the index ticker.

    OKX's ``fundingTime`` is the settlement the current rate is charged AT (live payload: ~4 h in the
    future with ``prevFundingTime`` 4 h behind it), and ``nextFundingTime`` is the one after that —
    so the row's "next funding" is ``fundingTime`` while it is still ahead, which is also the gap the
    settlement spacing is read from.
    """
    funding_payload = payloads.get("funding_rate")
    if funding_payload is None:
        return _problem("the venue's funding payload did not arrive")
    if isinstance(funding_payload, dict) and str(funding_payload.get("code") or "0") not in ("0", ""):
        return _problem(_okx_refusal(funding_payload, "OKX"))
    rows = _env_data(funding_payload)
    if not rows:
        return _problem(f"OKX returned no funding row for {instrument or 'this instrument'}")
    row = rows[0]
    notes: list[str] = []
    current_ms, next_ms, prev_ms = (_int(row.get("fundingTime")), _int(row.get("nextFundingTime")),
                                    _int(row.get("prevFundingTime")))
    named = _num(row.get("fundingIntervalHours"))
    interval: Optional[float] = named if named and 0.25 <= named <= 24 else None
    if interval is None:
        for later, earlier in ((next_ms, current_ms), (current_ms, prev_ms)):
            if later and earlier and 0 < (later - earlier) <= 24 * 3_600_000:
                interval = round((later - earlier) / 3_600_000.0, 4)
                notes.append("the settlement spacing was read from the venue's own funding times")
                break
    settles_at = current_ms if (current_ms and (now_ms is None or current_ms > now_ms)) else next_ms
    mark = index = oi = oi_usd = None
    mark_payload = payloads.get("mark_price")
    if isinstance(mark_payload, dict) and str(mark_payload.get("code") or "0") in ("0", ""):
        mark_rows = _env_data(mark_payload)
        mark = _num(mark_rows[0].get("markPx")) if mark_rows else None
    index_payload = payloads.get("index_tickers")
    if isinstance(index_payload, dict) and str(index_payload.get("code") or "0") in ("0", ""):
        index_rows = _env_data(index_payload)
        index = _num(index_rows[0].get("idxPx")) if index_rows else None
    oi_payload = payloads.get("open_interest")
    oi_arrived = False
    if isinstance(oi_payload, dict) and str(oi_payload.get("code") or "0") in ("0", ""):
        oi_rows = _env_data(oi_payload)
        if oi_rows:
            oi_arrived = True
            # oiCcy is the coin figure; the venue's own contract count (oi) is a different unit and is
            # deliberately not mixed into it — a payload without oiCcy carries no coin figure, and the
            # row says so rather than labelling a contract count as coin (T5-F03).
            oi = _num(oi_rows[0].get("oiCcy"))
            oi_usd = _num(oi_rows[0].get("oiUsd"))
            if oi is None and _num(oi_rows[0].get("oi")) is not None:
                notes.append("OKX published only a contract count for open interest — a different "
                             "unit, so the row carries no coin figure")
    if oi is None and not oi_arrived:
        notes.append("the venue's open-interest payload did not arrive — the row carries no size")
    return _ok(_fields(
        funding_rate=_num(row.get("fundingRate")),
        funding_interval_h=interval,
        next_funding_ms=settles_at,
        mark=mark,
        index=index,
        open_interest=oi,
        open_interest_unit=base_coin(instrument) if oi is not None else "",
        open_interest_usd=oi_usd,
        ts_ms=_int(row.get("ts")),
    ), notes)


def parse_hyperliquid(payloads: dict[str, Any], instrument: str = "",
                      *, now_ms: Optional[int] = None) -> dict[str, Any]:
    """Hyperliquid ``metaAndAssetCtxs``: one document, every coin, indexed by the listing order.

    ``funding`` is the **hourly** rate (this venue settles every hour); ``oraclePx`` is the index the
    perp is measured against and the venue's own ``premium`` is the same (mark - oracle) / oracle
    figure this module computes. The document carries no timestamp, so the row's age stays unknown
    rather than being stamped with our own clock.
    """
    payload = payloads.get("meta_contexts")
    if not isinstance(payload, list) or len(payload) < 2:
        return _problem("the venue's meta-and-contexts payload did not arrive")
    meta = payload[0] if isinstance(payload[0], dict) else {}
    contexts = payload[1] if isinstance(payload[1], list) else []
    names = [str(entry.get("name") or "") for entry in (meta.get("universe") or [])
             if isinstance(entry, dict)]
    coin = base_coin(instrument)
    index_of = names.index(coin) if coin in names else -1
    if index_of < 0 or index_of >= len(contexts) or not isinstance(contexts[index_of], dict):
        return _problem(f"Hyperliquid's listing did not carry {coin or 'this instrument'}")
    row = contexts[index_of]
    oi = _num(row.get("openInterest"))
    mark = _num(row.get("markPx"))
    notes = ["Hyperliquid settles funding hourly",
             "this venue's payload carries no timestamp, so the age of this row is unknown"]
    return _ok(_fields(
        funding_rate=_num(row.get("funding")),
        next_funding_ms=None,
        mark=mark,
        index=_num(row.get("oraclePx")),
        open_interest=oi,
        open_interest_unit=base_coin(instrument) if oi is not None else "",
        open_interest_usd=round(oi * mark, 4) if oi is not None and mark else None,
        ts_ms=None,
    ), notes + (["open interest in USD is computed from this venue's own open interest and mark"]
                if oi is not None and mark else []))


PARSERS: dict[str, Callable[..., dict[str, Any]]] = {
    "bybit": parse_bybit,
    "binance": parse_binance,
    "okx": parse_okx,
    "hyperliquid": parse_hyperliquid,
}


# ── refusals, in one voice ─────────────────────────────────────────────────────────────────────────

#: What a caller gets back when nothing nameable was handed in, so no sentence starts mid-air.
UNCLEARED_LABEL = "that venue"


def label_of(venue: Any) -> str:
    text = str(venue or "").strip()
    return VENUE_LABELS.get(text.lower(), text.title() or UNCLEARED_LABEL)


def unsupported_sentence(venue: Any) -> str:
    """``Sonic is not a venue this panel covers — one of Bybit, Binance, OKX, Hyperliquid``."""
    known = ", ".join(VENUE_LABELS[name] for name in VENUES)
    name = label_of(venue)
    if name == UNCLEARED_LABEL:              # nothing was named: say that, not "that venue is not…"
        return f"That name is not a venue this panel covers — one of {known}"
    return f"{name} is not a venue this panel covers — one of {known}"


def reason_of(exc: BaseException) -> str:
    """Why a venue did not answer, in one plain clause — the type name is never shown to the user."""
    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        if code == 429:
            return "the venue is rate-limiting this machine (HTTP 429)"
        if code in (401, 403, 451):
            return f"the venue refused the request from this machine (HTTP {code})"
        if code == 404:
            return "the route this app reads is not there (HTTP 404)"
        return f"the venue answered HTTP {code}"
    if isinstance(exc, json.JSONDecodeError):
        return "the venue sent a reply that is not JSON"
    if isinstance(exc, urllib.error.URLError):
        return f"the venue could not be reached ({getattr(exc, 'reason', '') or 'no reason given'})"
    if isinstance(exc, TimeoutError):
        return "the request timed out"
    if isinstance(exc, ValueError):
        return "the venue sent a reply that is not JSON"
    if isinstance(exc, OSError):
        return f"the connection failed ({exc or 'no reason given'})"
    return "the request failed for a reason the venue did not state"


def unreachable_sentence(venue: Any, exc: BaseException) -> str:
    return f"{label_of(venue)} did not answer — {reason_of(exc)}"


def no_venue_sentence(symbol: str, errors: Sequence[dict[str, Any]]) -> str:
    """The route's refusal when nothing answered: every venue's own one-line reason, joined."""
    if not errors:
        return f"nothing could be read for {symbol} — no venue is enabled"
    joined = "; ".join(f"{label_of(e.get('venue'))}: {e.get('reason')}" for e in errors)
    return f"no venue answered for {symbol} — {joined}"


# ── one venue's read ───────────────────────────────────────────────────────────────────────────────

def read_venue(venue: str, symbol: str, fetch: Fetch, *, now_ms: int) -> dict[str, Any]:
    """One venue's whole answer for one instrument: parsed fields, or the reason it refused.

    A required call that raises refuses the row; an optional one that raises only leaves a note, so a
    venue whose OI route is down still answers funding and basis instead of going dark.
    """
    label = label_of(venue)
    out: dict[str, Any] = {"venue": venue, "label": label, "instrument": venue_instrument(venue, symbol),
                           "ok": False, "fields": {}, "problem": "", "reason": "", "notes": []}
    if venue not in VENUES:
        out["problem"] = out["reason"] = unsupported_sentence(venue)
        return out
    payloads: dict[str, Any] = {}
    notes: list[str] = []
    for name, url, required in venue_calls(venue, symbol):
        try:
            payloads[name] = fetch(url)
        except Exception as exc:                       # noqa: BLE001 — the venue's failure is data
            if required:
                logger.debug("derivatives: %s %s failed: %s", venue, name, exc)
                out["reason"] = reason_of(exc)
                out["problem"] = unreachable_sentence(venue, exc)
                return out
            notes.append(f"this venue's {name.replace('_', ' ')} call did not answer "
                         f"({reason_of(exc)}) — the row carries what it did")
    parsed = PARSERS[venue](payloads, out["instrument"], now_ms=now_ms)
    out["fields"] = parsed.get("fields") or {}
    out["notes"] = notes + list(parsed.get("notes") or [])
    if parsed.get("problem"):
        out["problem"] = str(parsed["problem"])
        out["reason"] = str(parsed["problem"])
        return out
    out["ok"] = True
    return out


# ── the store: this app's own open-interest samples ────────────────────────────────────────────────

class OiHistory:
    """Open-interest samples per ``(venue, symbol)``, in memory, bounded per key.

    The window in the settings is only meaningful if the samples to fill it exist, and the venues
    publish snapshots, not changes — so the change is measured against what this app itself watched.
    Bounded (a deque per key, oldest dropped) because a panel left open for a week must not grow.
    """

    def __init__(self, max_samples: int = int(DEFAULTS["history_max"])) -> None:
        self.max_samples = max(2, int(max_samples))
        self._series: dict[tuple[str, str], deque[tuple[int, float]]] = {}
        self.stored = 0

    def add(self, venue: str, symbol: str, ts_ms: int, value: Any) -> bool:
        """Store one sample. A duplicate timestamp replaces the value; a bad value is not stored."""
        number = _num(value)
        if number is None or number <= 0:
            return False
        key = (str(venue), str(symbol))
        series = self._series.get(key)
        if series is None:
            series = self._series[key] = deque(maxlen=self.max_samples)
        stamp = int(ts_ms)
        if series and series[-1][0] == stamp:
            series[-1] = (stamp, number)
        else:
            series.append((stamp, number))
            self.stored += 1
        return True

    def series(self, venue: str, symbol: str) -> list[tuple[int, float]]:
        return list(self._series.get((str(venue), str(symbol)), ()))

    def keys(self) -> list[tuple[str, str]]:
        return sorted(self._series)

    def clear(self) -> None:
        self._series.clear()
        self.stored = 0


# ── the panel's payload, assembled from plain data (pure) ──────────────────────────────────────────

def row_for(observed: dict[str, Any], cfg: dict[str, Any], now_ms: int,
            series: Iterable[tuple[int, float]] = ()) -> dict[str, Any]:
    """One venue's table row: what it says, plus this app's own open-interest change for it."""
    venue = str(observed.get("venue") or "")
    fields = observed.get("fields") or {}
    rate = _num(fields.get("funding_rate"))
    interval = _num(fields.get("funding_interval_h")) or FUNDING_INTERVAL_H.get(venue, 8.0)
    mark, index = _num(fields.get("mark")), _num(fields.get("index"))
    bps = basis_bps(mark, index)
    ts_ms = _int(fields.get("ts_ms"))
    oi = _num(fields.get("open_interest"))
    next_ms = _int(fields.get("next_funding_ms"))
    change = oi_change(series, cfg.get("oi_window_s"), now_ms)
    apr = annualise_pct(rate, interval)
    return {
        "venue": venue,
        "label": str(observed.get("label") or label_of(venue)),
        "instrument": str(observed.get("instrument") or ""),
        "ok": bool(observed.get("ok")),
        "error": str(observed.get("problem") or ""),
        "reason": str(observed.get("reason") or ""),
        "notes": list(observed.get("notes") or []),
        "funding_rate": rate,
        "funding_pct": None if rate is None else round(rate * 100.0, 8),
        "funding_interval_h": interval,
        "funding_apr_pct": None if apr is None else round(apr, 4),
        "next_funding_ms": next_ms,
        "next_funding_in_s": None if next_ms is None else round((next_ms - now_ms) / 1000.0, 1),
        "mark": mark,
        "index": index,
        "basis_bps": None if bps is None else round(bps, 4),
        "basis_apr_pct": None if bps is None else round(basis_apr_pct(bps), 4),
        "open_interest": oi,
        "open_interest_unit": str(fields.get("open_interest_unit") or ""),
        "open_interest_usd": _num(fields.get("open_interest_usd")),
        "oi_change_pct": change["pct"],
        "oi_baseline_ms": change["baseline_ms"],
        "oi_span_s": change["span_s"],
        "oi_samples": change["samples"],
        "oi_window_limited": change["window_limited"],
        "oi_change_reason": change["reason"],
        "ts_ms": ts_ms,
        "age_ms": None if ts_ms is None else max(0, now_ms - ts_ms),
    }


def funding_read(rows: Sequence[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """The cross-venue funding read: the median venue, its spread, and who is crowded."""
    quoted = [{"venue": r["venue"], "label": r["label"], "rate": r["funding_rate"],
               "interval_h": r["funding_interval_h"], "pct": r["funding_pct"],
               "apr_pct": r["funding_apr_pct"]}
              for r in rows if _num(r.get("funding_apr_pct")) is not None]
    out: dict[str, Any] = {"available": bool(quoted), "per_venue": quoted, "median_rate": None,
                           "median_pct": None, "median_interval_h": None, "rate_apr_pct": None,
                           "median_apr_pct": None,
                           "min_apr_pct": None, "max_apr_pct": None, "spread_apr_pct": None,
                           "direction": "", "verdict": "", "crowded": [],
                           "crowded_long": False, "crowded_short": False,
                           "reason": "" if quoted else "no venue answered with a funding rate"}
    if not quoted:
        return out
    aprs = [row["apr_pct"] for row in quoted]
    median = _median(aprs) or 0.0
    # The sentence quotes a real venue's rate — the venue whose annualised figure sits closest to
    # the median — and pairs it with THAT venue's own annualised figure (`rate_apr_pct`), never with
    # the cross-venue median below: with an even venue count the median is the mean of the two middle
    # venues, and the sentence's two numbers would then disagree by construction (live: a quoted
    # +0.010%/8h beside a 9.9% median, where the rate itself annualises to 10.95%).
    picked = min(quoted, key=lambda item: (abs(item["apr_pct"] - median), item["venue"]))
    crowded = [{"venue": row["venue"], "label": row["label"], "apr_pct": row["apr_pct"]}
               for row in quoted if abs(row["apr_pct"]) >= cfg["crowded_apr_pct"]]
    lowest, highest = min(aprs), max(aprs)
    # A median of ~0 with venues on both sides is not a quiet market — it is the venues disagreeing
    # about which side is paying, and that is worth its own sentence whenever the disagreement is
    # large enough to matter (the crowded threshold, i.e. one side being paid well and the other
    # paying well). Below that it is a flat market, and the median is the honest read of it.
    disagree = lowest < 0 < highest and (highest - lowest) >= cfg["crowded_apr_pct"]
    if disagree:
        direction = "mixed"
    elif abs(median) < cfg["flat_apr_pct"]:
        direction = "flat"
    else:
        direction = "longs_pay" if median > 0 else "shorts_pay"
    verdict = {"flat": "flat", "mixed": "venues disagree", "longs_pay": "longs pay",
               "shorts_pay": "shorts pay"}[direction]
    if direction == "longs_pay" and any(c["apr_pct"] > 0 for c in crowded):
        verdict = "crowded long"
    if direction == "shorts_pay" and any(c["apr_pct"] < 0 for c in crowded):
        verdict = "crowded short"
    out.update({"median_rate": picked["rate"], "median_pct": picked["pct"],
                "median_interval_h": picked["interval_h"], "rate_apr_pct": picked["apr_pct"],
                "median_apr_pct": round(median, 4),
                "min_apr_pct": round(min(aprs), 4), "max_apr_pct": round(max(aprs), 4),
                "spread_apr_pct": round(max(aprs) - min(aprs), 4), "direction": direction,
                "verdict": verdict, "crowded": crowded,
                "crowded_long": bool(direction == "longs_pay" and crowded),
                "crowded_short": bool(direction == "shorts_pay" and crowded)})
    return out


def oi_read(rows: Sequence[dict[str, Any]], cfg: dict[str, Any], now_ms: int,
            total_series: Iterable[tuple[int, float]] = ()) -> dict[str, Any]:
    """The cross-venue size read: the USD total now, and its change over the watched window."""
    per_venue = {r["venue"]: r["oi_change_pct"] for r in rows if r["oi_change_pct"] is not None}
    usd_rows = [r for r in rows if _num(r.get("open_interest_usd")) is not None]
    total_usd = round(sum(float(r["open_interest_usd"]) for r in usd_rows), 4) if usd_rows else None
    change = oi_change(total_series, cfg.get("oi_window_s"), now_ms)
    if change["pct"] is None and per_venue:
        change = dict(change, pct=round(_median(list(per_venue.values())) or 0.0, 4),
                      source="the median of the venues that had a baseline")
    else:
        change = dict(change, source="the summed open interest of the venues that publish USD")
    return {
        "available": bool(rows),
        "total_usd": total_usd,
        "venues_usd": len(usd_rows),
        "change_pct": change["pct"],
        "change_source": change["source"] if change["pct"] is not None else "",
        "window_s": int(cfg.get("oi_window_s") or 0),
        "span_s": change["span_s"],
        "samples": change["samples"],
        "window_limited": bool(change["window_limited"]),
        "reason": change["reason"],
        "per_venue": per_venue,
        "unit": next((str(r.get("open_interest_unit") or "") for r in rows
                      if r.get("open_interest_unit")), ""),
    }


def basis_read(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The cross-venue basis read, in bps: the median venue, the tightest and the widest."""
    bps = [r["basis_bps"] for r in rows if _num(r.get("basis_bps")) is not None]
    if not bps:
        return {"available": False, "median_bps": None, "min_bps": None, "max_bps": None,
                "spread_bps": None, "median_apr_pct": None,
                "reason": "no venue answered with both a mark and an index", "note": ""}
    median = _median(bps) or 0.0
    return {"available": True, "median_bps": round(median, 4), "min_bps": round(min(bps), 4),
            "max_bps": round(max(bps), 4), "spread_bps": round(max(bps) - min(bps), 4),
            "median_apr_pct": round(basis_apr_pct(median) or 0.0, 4), "reason": "",
            #: Printed next to the annualised figure everywhere it appears: a perp premium is not a
            #: yield, and the annualising is a desk shorthand, not a forecast.
            "note": "the annualised basis assumes the same premium every day — a perp premium is not a yield"}


# ── the sentence (pure: the numbers in, words out) ─────────────────────────────────────────────────

def interval_text(hours: Any) -> str:
    """``8`` → ``8h``, ``1`` → ``1h``, ``0.5`` → ``30m`` — the unit the rate is charged in."""
    value = _num(hours)
    if not value or value <= 0:
        return ""
    if value < 1:
        return f"{int(round(value * 60))}m"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}h"
    return f"{value:.1f}h"


def _signed(value: Any, digits: int) -> str:
    """A number at a fixed precision with its sign kept — on funding, the sign IS the message.

    Written by hand rather than with the format spec's ``+`` flag so that an exact zero reads
    ``0.000`` and not ``+0.000``: nothing is being paid, and the panel should not imply otherwise.
    The JavaScript half (``signed()`` in derivatives.js) does the same, pinned equal by the parity
    test in ``orderflow_system/test_derivatives.py``.
    """
    number = _num(value)
    if number is None:
        return ""
    body = f"{abs(number):.{digits}f}"
    if number > 0:
        return "+" + body
    return f"-{body}" if number < 0 else body


def funding_text(funding: dict[str, Any]) -> str:
    """``+0.011%/8h (+12.0% annualised)`` — the rate, its settlement, and the year it implies.

    The year comes from the quoted venue's own annualised figure (``rate_apr_pct``), never the
    cross-venue median: the sentence's two numbers must imply each other (T5-F01).
    """
    if not funding.get("available"):
        return "funding is not known"
    rate_pct = _num(funding.get("median_pct"))
    apr = _num(funding.get("rate_apr_pct"))
    piece = f"{_signed(rate_pct, 3)}%/{interval_text(funding.get('median_interval_h'))}"
    return f"{piece} ({_signed(apr, 1)}% annualised)" if apr is not None else piece


def span_text(span_s: Any, window_s: Any = None) -> str:
    """The window an OI change was really measured over, in words — never a claim of "the day".

    An unknown span — the number came from the venue-median fallback rather than this app's own
    samples — returns no span claim at all, so no sentence can read "over the last 0 s" for a
    measurement nobody took (T5-F02).
    """
    span = _num(span_s)
    window = _num(window_s) or 0.0
    if span is None or span < 1.0:
        return ""
    if span >= 20 * 3600 and window >= 22 * 3600:
        return "on the day"
    if span >= 3600:
        return f"over the last {round(span / 3600.0, 1):g} h"
    if span >= 540:
        return f"over the last {int(round(span / 60.0))} m"
    return f"over the last {int(round(span))} s"


def oi_text(oi: dict[str, Any]) -> str:
    """``OI up 3.2% on the day`` / ``the open-interest change not known yet (…)``.

    With no measured span, the number's own source is named instead — a venue-median fallback has no
    span this app took (T5-F02).
    """
    pct = _num(oi.get("change_pct"))
    if pct is None:
        reason = str(oi.get("reason") or "the app has not watched long enough")
        return f"the open-interest change not known yet ({reason})"
    where = span_text(oi.get("span_s"), oi.get("window_s"))
    if not where:
        source = str(oi.get("change_source") or "")
        where = f"({source})" if source else ""
    if abs(pct) < 0.05:
        return f"OI flat {where}".strip()
    return f"OI {'up' if pct > 0 else 'down'} {abs(pct):.1f}% {where}".strip()


def direction_text(funding: dict[str, Any], cfg: dict[str, Any]) -> str:
    """Who is paying whom: the plain-English half of the sentence."""
    direction = str(funding.get("direction") or "")
    if direction == "longs_pay":
        lead = "a crowded long: " if funding.get("crowded_long") else ""
        return f"{lead}longs are paying to hold"
    if direction == "shorts_pay":
        lead = "a crowded short: " if funding.get("crowded_short") else ""
        return f"{lead}shorts are paying to hold"
    if direction == "mixed":
        return "the venues disagree about which side is paying"
    if direction == "flat":
        # A caller handing in a bare cfg still gets words, not a TypeError (§148 T5-F-08); the
        # default is the same one the JS twin names.
        threshold = _num(cfg.get("flat_apr_pct"))
        if threshold is None:
            threshold = DEFAULTS["flat_apr_pct"]
        return f"neither side is paying much (under {threshold:g}% annualised)"
    return "funding is not known"


def summary_line(funding: dict[str, Any], oi: dict[str, Any], cfg: dict[str, Any]) -> str:
    """The panel's one plain sentence: ``funding is … with OI … — …``.

    Example: ``funding is +0.011%/8h (+12.0% annualised) with OI up 3.2% on the day — longs are
    paying to hold``. The OI half says exactly which window was watched, so a panel open for two
    hours claims two hours and never "the day".
    """
    if not funding.get("available"):
        return ""
    return f"funding is {funding_text(funding)} with {oi_text(oi)} — {direction_text(funding, cfg)}"


def assemble(symbol: str, observed: Sequence[dict[str, Any]], cfg: Any, *, now_ms: int,
             venue_series: Optional[dict[str, list[tuple[int, float]]]] = None,
             total_series: Iterable[tuple[int, float]] = ()) -> dict[str, Any]:
    """The whole payload from plain data: py parsers' output + this app's OI samples in, panel out."""
    settings = clean(cfg)
    series = venue_series or {}
    rows = [row_for(item, settings, now_ms, series.get(str(item.get("venue") or ""), ()))
            for item in observed]
    served = [r for r in rows if r["ok"]]
    errors = [{"venue": r["venue"], "label": r["label"], "reason": r["reason"] or r["error"]}
              for r in rows if not r["ok"]]
    funding = funding_read(served, settings)
    oi = oi_read(served, settings, now_ms, total_series)
    basis = basis_read(served)
    payload: dict[str, Any] = {
        "ok": bool(served),
        "symbol": symbol,
        "as_of_ms": now_ms,
        "venues_asked": len(rows),
        "venues_ok": len(served),
        "venues": rows,
        "funding": funding,
        "oi": oi,
        "basis": basis,
        "summary": summary_line(funding, oi, settings) if served else "",
        "errors": errors,
        "settings": settings,
        "note": ("" if served else no_venue_sentence(symbol, errors)),
    }
    if not served:
        # One refusal shape for the panel: the same one sentence under both keys it might read.
        payload["detail"] = payload["note"]
        payload["error"] = payload["note"]
    return payload


# ── the fetch seam ─────────────────────────────────────────────────────────────────────────────────

def default_fetch(url: str, timeout_s: float = TIMEOUT_S) -> Any:
    """The real transport: one URL in, parsed JSON out, raising on any failure.

    Hyperliquid serves its ``/info`` route by POST only, so a URL of the form ``/info?type=…`` is
    turned into the JSON body the venue expects here — which keeps the seam every caller (and every
    test stub) uses one argument wide.
    """
    method_body: Optional[bytes] = None
    target = url
    if url.startswith(f"{HYPERLIQUID_REST}/info") and "?" in url:
        parts = urllib.parse.urlsplit(url)
        method_body = json.dumps(dict(urllib.parse.parse_qsl(parts.query))).encode("utf-8")
        target = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    request = urllib.request.Request(target, data=method_body,
                                     headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    if method_body is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


class DerivativesService:
    """Reads the venues and assembles the payload. ``fetch`` is the whole network surface."""

    def __init__(self, fetch: Optional[Fetch] = None, *, timeout_s: float = TIMEOUT_S,
                 history: Optional[OiHistory] = None,
                 now_ms: Optional[Callable[[], int]] = None) -> None:
        self._fetch: Fetch = fetch if fetch is not None else (lambda url: default_fetch(url, timeout_s))
        self.timeout_s = float(timeout_s)
        self.history = history if history is not None else OiHistory()
        self._now = now_ms or (lambda: int(time.time() * 1000))
        self.reads = 0
        self.failures = 0

    def read(self, symbol: str, cfg: Any = None) -> dict[str, Any]:
        """One read of every enabled venue, plus the open-interest samples this read produced.

        Blocking by design: the route hands it to ``asyncio.to_thread`` so a slow venue cannot stall
        the event loop.
        """
        settings = clean(cfg)
        sym = normalise_symbol(symbol)
        now = self._now()
        self.reads += 1
        observed = [read_venue(venue, sym, self._fetch, now_ms=now) for venue in settings["venues"]]
        self.failures += sum(1 for item in observed if not item["ok"])
        for item in observed:
            self._observe(sym, item, now)
        self._observe_total(sym, observed, now)
        payload = assemble(sym, observed, settings, now_ms=now,
                           venue_series={venue: self.history.series(venue, sym)
                                         for venue in settings["venues"]},
                           total_series=self.history.series(TOTAL_KEY, sym))
        payload["cache_max"] = self.history.max_samples
        return payload

    def _observe(self, symbol: str, item: dict[str, Any], now_ms: int) -> None:
        """Store one venue's own open-interest sample, stamped with the venue's clock when it has one."""
        if not item.get("ok"):
            return
        fields = item.get("fields") or {}
        self.history.add(str(item["venue"]), symbol, _int(fields.get("ts_ms")) or now_ms,
                         fields.get("open_interest"))

    def _observe_total(self, symbol: str, observed: Sequence[dict[str, Any]], now_ms: int) -> None:
        """Store the summed USD total this read saw, stamped with this app's own clock.

        The sum, never one venue's figure: the total key is what the cross-venue change is measured
        against, and storing a single venue under it would report a change that belongs to a
        different number entirely (one row's share of the market, dressed as the whole of it).
        """
        total = sum(usd for usd in (_num((item.get("fields") or {}).get("open_interest_usd"))
                                    for item in observed if item.get("ok")) if usd is not None)
        if total > 0:
            self.history.add(TOTAL_KEY, symbol, now_ms, total)


# ── routes ─────────────────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

_service: Optional[DerivativesService] = None
#: (symbol, venue list) -> (stamp, payload). A public read of a slow number: two panels asking for
#: the same instrument within the refresh window share one round of venue calls.
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
#: How many (symbol, venue list) payloads stay resident. The window is the price of one round of
#: venue calls, but a process left running for a week must not grow with every symbol it ever
#: showed (§148 T5-F-14) — the standard `OiHistory` is held to.
CACHE_MAX = 32


def _cache_store(key: str, stamp: float, payload: dict[str, Any]) -> None:
    """Store one payload under ``key`` and keep the cache bounded, oldest write first."""
    _cache[key] = (stamp, payload)
    while len(_cache) > CACHE_MAX:
        _cache.pop(min(_cache, key=lambda item: _cache[item][0]), None)


def settings() -> dict[str, Any]:
    """The stored derivatives block, cleaned. Reads only — never writes, never raises."""
    try:
        from orderflow_system.desktop import config_store

        return clean((config_store.load_config() or {}).get("derivatives"))
    except Exception:                                  # noqa: BLE001 — a panel must still answer
        return clean(None)


def get_service() -> DerivativesService:
    """The process-wide service, so the open-interest window survives between requests."""
    global _service
    if _service is None:
        _service = DerivativesService(history=OiHistory(int(settings()["history_max"])))
    return _service


def requested_venues(query: Any, cfg: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The venue list for one read, and the names it asked for that this panel does not cover.

    No query means the stored list. A query that names something is honoured for the names this panel
    covers and reported for the ones it does not — an empty ``picked`` alongside a non-empty
    ``dropped`` is a request that named nothing readable, which the route refuses by name rather than
    quietly reading something else.
    """
    if str(query or "").strip():
        return accepted_venues(query)
    return list(cfg["venues"]), []


def unknown_venues_sentence(dropped: Sequence[str]) -> str:
    known = ", ".join(VENUE_LABELS[name] for name in VENUES)
    listed = ", ".join(repr(str(name)) for name in dropped)
    return f"no venue this panel covers was named ({listed}) — one of {known}"


def refusal(symbol: str, sentence: str, **extra: Any) -> dict[str, Any]:
    """The one shape a refused read answers with — both keys, one sentence, no traceback."""
    return {"ok": False, "symbol": normalise_symbol(symbol), "detail": sentence, "error": sentence,
            "venues": [], "venues_asked": 0, "venues_ok": 0, "summary": "", "errors": [],
            "funding": {"available": False, "reason": sentence, "per_venue": []},
            "oi": {"available": False, "reason": sentence, "per_venue": {}},
            "basis": {"available": False, "reason": sentence}, "settings": settings(), **extra}


@router.get("/derivatives/{symbol}")
async def derivatives_read(symbol: str, venues: str = Query("", description="comma-separated venue list"),
                           refresh: bool = Query(False, description="ignore the cache and ask again")
                           ) -> dict[str, Any]:
    """Funding, open interest and basis for one instrument, every enabled venue side by side."""
    cfg = settings()
    sym = normalise_symbol(symbol)
    if not sym:
        return refusal(symbol, "pick an instrument first — the derivatives read needs one")
    wanted, dropped = requested_venues(venues, cfg)
    if not wanted:
        return refusal(sym, unknown_venues_sentence(dropped), dropped_venues=dropped)
    key = f"{sym}|{','.join(wanted)}"
    now = time.time()
    hit = _cache.get(key)
    if hit is not None and not refresh and (now - hit[0]) < cfg["refresh_s"]:
        return hit[1]
    try:
        payload = await asyncio.to_thread(get_service().read, sym, dict(cfg, venues=wanted))
    except Exception as exc:                           # noqa: BLE001 — a route never 500s
        logger.warning("derivatives read failed for %s: %s", sym, exc)
        return refusal(sym, f"the derivatives read failed — {reason_of(exc)}")
    if dropped:
        payload["dropped_venues"] = dropped
    _cache_store(key, time.time(), payload)
    return payload


@router.post("/derivatives/venues")
async def derivatives_set_venues(body: Any = Body(default_factory=dict)) -> dict[str, Any]:
    """Store which venues the panel reads. The only write in this module, and it writes a list."""
    raw = body.get("venues") if isinstance(body, dict) else body
    picked, dropped = accepted_venues(raw)
    if not picked:
        known = ", ".join(VENUE_LABELS[name] for name in VENUES)
        if dropped:
            detail = (f"no venue this panel covers was named "
                      f"({', '.join(repr(name) for name in dropped)}) — one of {known}")
        else:
            detail = f"name at least one venue — one of {known}"
        return {"ok": False, "venues": [], "dropped": dropped, "detail": detail}
    try:
        from orderflow_system.desktop import config_store

        config_store.merge_config({"derivatives": {"venues": picked}})
    except Exception as exc:                           # noqa: BLE001 — the read still works unstored
        logger.warning("derivatives venues could not be stored: %s", exc)
        return {"ok": False, "venues": picked, "dropped": dropped,
                "detail": f"the venue list could not be saved ({reason_of(exc)}) — it applies until "
                          f"the app restarts"}
    _cache.clear()
    saved = ", ".join(VENUE_LABELS[name] for name in picked)
    detail = f"reading {saved} from now on"
    if dropped:
        detail += f" — dropped {', '.join(dropped)} (not a venue this panel covers)"
    return {"ok": True, "venues": picked, "dropped": dropped, "detail": detail}
