"""Deribit's public options data — the chain, IV and Greeks behind the Options panel.

Deribit publishes crypto option chains on a keyless, free public API (measured from this machine:
410 ms for the whole BTC chain, 355 ms for one ticker), and the browser cannot reach it — the venue
sends no CORS header — so this module is the server-side half. It fetches, parses and caches; the
panel reads two routes, mounted in `desktop/api.py` (which is where every other control route lives):

    GET /api/control/deribit/chain?symbol=BTCUSDT[&expiry=16SEP26][&width=10]
    GET /api/control/deribit/ticker?instrument=BTC-16SEP26-68000-C

WHAT A CHAIN RESPONSE HOLDS: every expiry the venue lists for that currency, and a strike ladder for
one of them — per strike the call and the put with bid, ask, mark IV, open interest, volume and the
Greeks, plus the forward the window was centred on. Greeks live only on `public/ticker` (one
instrument per call), so the ladder's window is bounded on purpose: this module reads the tickers for
the strikes around the forward, not for all 896 instruments, and reports how many it read.

WHAT IT NEVER DOES: no key, no account, no writes, no sockets. Every failure comes back as a dict with
ok=False and a readable `error` — the panel has to be able to print the venue's own words ("HTTP 400:
instrument not found (instrument_name)") instead of a generic one. Nothing in here raises.

LIVE FACTS THE CODE BELOW DEPENDS ON (all verified against the public API on 2026-09-15):
  * `get_instruments?currency=BTC&kind=option&expired=false` → 896 live BTC options over 11 expiries.
    Strikes are NOT uniformly spaced (1000 apart far out, 500 near the money), so the ladder sorts
    what the venue lists and never assumes a step.
  * `ticker` → best_bid_price/best_ask_price, mark_iv, open_interest, stats.volume,
    greeks.{delta,gamma,theta,vega,rho}, and `underlying_price` — the FORWARD of that expiry, which
    sat ~3000 above the index for the June-2027 series. That is why the window is centred on a
    ticker's own forward rather than on the index price.
  * A bad instrument answers HTTP 400 with {"error":{"code":-32602,"data":{"reason":"instrument not
    found","param":"instrument_name"}}} — captured verbatim in `fixtures/deribit/ticker_error.json`
    and quoted back to the panel.
  * SOL exists as a currency and lists NO options (two spot instruments, nothing else), so
    "recognised currency, empty chain" is a real state reported honestly here, not an error state.
  * The JSON-RPC batch endpoint refuses an array ("invalid json", HTTP 400), so a window of tickers
    is fetched one per request through a bounded pool (~1.4 s for 42 of them at 12 workers).
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, Sequence

# ──────────────────────────────────────────────────────────────
# The venue, and what this module is allowed to cost it
# ──────────────────────────────────────────────────────────────

BASE = "https://www.deribit.com/api/v2/public"
USER_AGENT = "OrderFlow-Analysis-Pro"
TIMEOUT_S = 15.0

#: The currencies that carry a Deribit option chain. Anything else — an index, FX, an equity — has
#: none, and saying exactly that is the whole job of `currency_for`.
OPTION_CURRENCIES = ("BTC", "ETH", "SOL")

#: Quote/contract suffixes stripped before the base currency is read ("BTCUSDT" → "BTC").
QUOTE_SUFFIXES = ("PERPUSDT", "PERP", "USDT", "USDC", "USD")

CHAIN_TTL_MS = 5000          # the instrument list is the big, slow-moving half
TICKER_TTL_MS = 3000         # a ticker is the live half, and it is what the panel repaints from
DEFAULT_WIDTH = 10           # strikes each side of the forward → at most 21 ladder rows
MAX_WIDTH = 30
WORKERS = 12                 # ticker fetches in flight; 42 of them measure ~1.4 s at this width
ERROR_SAMPLE = 3             # how many of the venue's own refusals are kept for the panel to print

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def now_ms() -> int:
    return int(time.time() * 1000)


# ──────────────────────────────────────────────────────────────
# Which currency an app symbol belongs to
# ──────────────────────────────────────────────────────────────

def currency_for(symbol: Any) -> Optional[str]:
    """BTCUSDT → BTC, ethusdt → ETH, BTC-USD → BTC, SOLUSDT → SOL; everything else → None.

    A symbol the app streams for a market Deribit does not quote options on (an index, FX, a stock)
    must come back None rather than being coerced into a currency: that answer is what turns the
    panel's missing-coverage sentence on.
    """
    text = re.sub(r"[^A-Z0-9]", "", str(symbol or "").upper())
    if not text:
        return None
    if text in OPTION_CURRENCIES:
        return text
    for suffix in QUOTE_SUFFIXES:
        if text.endswith(suffix):
            base = text[: -len(suffix)]
            if base in OPTION_CURRENCIES:
                return base
    return None


# ──────────────────────────────────────────────────────────────
# Fetching: one GET, decoded, and never an exception
# ──────────────────────────────────────────────────────────────

def _venue_reason(body: str) -> str:
    """Deribit's own reason for a refusal, so a panel can print it instead of a generic sentence."""
    try:
        payload = json.loads(body)
    except ValueError:
        return " ".join(str(body or "").split())[:160]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        data = error.get("data") if isinstance(error.get("data"), dict) else {}
        reason = str(data.get("reason") or error.get("message") or "").strip()
        param = str(data.get("param") or "").strip()
        if reason and param:
            return f"{reason} ({param})"
        if reason:
            return reason
    return " ".join(str(payload).split())[:160]


def get_json(url: str, timeout: float = TIMEOUT_S) -> tuple[Optional[Any], str]:
    """One public GET, decoded. Returns (payload, "") or (None, a reason the panel can print)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
        _count_request(True)
    except urllib.error.HTTPError as exc:                       # the venue's words, kept verbatim
        _count_request(False)
        try:
            detail = _venue_reason(exc.read().decode("utf-8", "replace"))
        except Exception:                                        # noqa: BLE001 - a body we cannot read
            detail = ""
        return None, f"HTTP {exc.code}" + (f": {detail}" if detail else "")
    except Exception as exc:                                     # noqa: BLE001 - offline, DNS, TLS, …
        _count_request(False)
        return None, f"{type(exc).__name__}: {exc}"
    try:
        return json.loads(body), ""
    except ValueError as exc:
        return None, f"unreadable JSON: {exc}"


_REQUESTS = {"ok": 0, "failed": 0, "lock": threading.Lock()}
_RECENT_ERRORS: list[str] = []


def _count_request(ok: bool) -> None:
    with _REQUESTS["lock"]:
        _REQUESTS["ok" if ok else "failed"] += 1


def _note_error(reason: str) -> None:
    """Keep the last few refusals, so a ladder with dead rows can say why they are dead."""
    with _REQUESTS["lock"]:
        if reason and reason not in _RECENT_ERRORS:
            _RECENT_ERRORS.append(reason)
            del _RECENT_ERRORS[:-ERROR_SAMPLE]


# ──────────────────────────────────────────────────────────────
# The TTL cache: two of them, because the two halves age at different rates
# ──────────────────────────────────────────────────────────────

class TtlCache:
    """A small TTL cache with an injectable clock, so its expiry is testable without sleeping.

    A public API is a shared resource: the panel polls it, and every read inside the TTL that this
    cache answers is a request the venue never sees.
    """

    def __init__(self, ttl_ms: int, clock: Callable[[], float] = time.time) -> None:
        self.ttl_ms = int(ttl_ms)
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[str, tuple[float, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any:
        """The value, or None when it is absent or older than the TTL (an expired entry is dropped)."""
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            at, value = item
            if (self._clock() - at) * 1000.0 >= self.ttl_ms:
                self._items.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return value

    def put(self, key: str, value: Any) -> Any:
        with self._lock:
            self._items[key] = (self._clock(), value)
        return value

    def clear(self) -> int:
        with self._lock:
            dropped = len(self._items)
            self._items.clear()
        return dropped

    def reset_counters(self) -> None:
        """Zero the hit/miss tallies (the module's `reset()` does this with the caches)."""
        with self._lock:
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"entries": len(self._items), "ttl_ms": self.ttl_ms,
                    "hits": self.hits, "misses": self.misses}


_INSTRUMENTS_CACHE = TtlCache(CHAIN_TTL_MS)
_TICKER_CACHE = TtlCache(TICKER_TTL_MS)


def stats() -> dict[str, Any]:
    """What the calls cost the venue — the panel's sub line and the tests both read this."""
    with _REQUESTS["lock"]:
        requests = {"ok": _REQUESTS["ok"], "failed": _REQUESTS["failed"],
                    "recent_errors": list(_RECENT_ERRORS)}
    return {"requests": requests, "instruments_cache": _INSTRUMENTS_CACHE.stats(),
            "ticker_cache": _TICKER_CACHE.stats(), "workers": WORKERS,
            "ttl_ms": {"chain": CHAIN_TTL_MS, "ticker": TICKER_TTL_MS}}


def reset() -> None:
    """Drop both caches and every counter — a test hook, and nothing else calls it."""
    for cache in (_INSTRUMENTS_CACHE, _TICKER_CACHE):
        cache.clear()
        cache.reset_counters()
    with _REQUESTS["lock"]:
        _REQUESTS["ok"] = 0
        _REQUESTS["failed"] = 0
        del _RECENT_ERRORS[:]


# ──────────────────────────────────────────────────────────────
# Parsing the two payloads (pure: no network, no cache, testable from a fixture)
# ──────────────────────────────────────────────────────────────

def _number(value: Any) -> Optional[float]:
    """A finite float, or None. Never NaN, never a string that only looks numeric."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def expiry_label(code: str) -> str:
    """The venue's own expiry code → a readable date. '16SEP26' → '16 Sep 2026'."""
    match = re.fullmatch(r"(\d{1,2})([A-Z]{3})(\d{2})", str(code or "").strip().upper())
    if not match:
        return str(code or "")
    day, month, year = match.group(1), match.group(2), match.group(3)
    if month not in MONTHS:
        return str(code)
    return f"{int(day)} {MONTH_NAMES[MONTHS.index(month)]} 20{year}"


def parse_instruments(payload: Any) -> tuple[list[dict[str, Any]], int]:
    """`get_instruments` → the rows a chain is built from, plus how many were unusable.

    Live row shape: instrument_name "BTC-16SEP26-68000-C", expiration_timestamp (epoch ms), strike
    (float), option_type "call"|"put", state "open", is_active true. A row that is not one of those
    is skipped and counted, never raised on: the venue's list is not ours to trust blindly.
    """
    result = payload.get("result") if isinstance(payload, dict) else None
    rows: list[dict[str, Any]] = []
    skipped = 0
    for item in (result if isinstance(result, list) else []):
        name = str(item.get("instrument_name") or "").strip() if isinstance(item, dict) else ""
        parts = name.split("-")
        strike = _number(item.get("strike")) if isinstance(item, dict) else None
        option_type = str(item.get("option_type") or "").lower() if isinstance(item, dict) else ""
        expires = _number(item.get("expiration_timestamp")) if isinstance(item, dict) else None
        if (len(parts) != 4 or option_type not in ("call", "put")
                or strike is None or not expires or strike <= 0):
            skipped += 1
            continue
        rows.append({
            "instrument": name,
            "currency": parts[0],
            "expiry_code": parts[1],
            "expiry_instrument": f"{parts[0]}-{parts[1]}",
            "expiry_ms": int(expires),
            "strike": strike,
            "option_type": option_type,
            "state": str(item.get("state") or ""),
            "active": bool(item.get("is_active")),
        })
    return rows, skipped


def parse_ticker(payload: Any) -> tuple[Optional[dict[str, Any]], str]:
    """One `ticker` payload → the numbers a ladder cell shows. Absent fields stay None (the panel
    prints an em dash for those; a zero would be a lie about a market that simply did not quote)."""
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return None, "the ticker reply carried no result"
    name = str(result.get("instrument_name") or "").strip()
    if not name:
        return None, "the ticker reply named no instrument"
    venue_stats = result.get("stats") if isinstance(result.get("stats"), dict) else {}
    greeks = result.get("greeks") if isinstance(result.get("greeks"), dict) else {}
    bid, ask = _number(result.get("best_bid_price")), _number(result.get("best_ask_price"))
    return {
        "instrument": name,
        "expiry_instrument": str(result.get("underlying_index") or ""),
        "ts": int(_number(result.get("timestamp")) or 0),
        "state": str(result.get("state") or ""),
        "bid": bid,
        "ask": ask,
        "mid": round((bid + ask) / 2.0, 8) if (bid is not None and ask is not None and ask >= bid) else None,
        "mark": _number(result.get("mark_price")),
        "last": _number(result.get("last_price")),
        "iv": _number(result.get("mark_iv")),
        "bid_iv": _number(result.get("bid_iv")),
        "ask_iv": _number(result.get("ask_iv")),
        "oi": _number(result.get("open_interest")),
        "volume": _number(venue_stats.get("volume")),
        "volume_usd": _number(venue_stats.get("volume_usd")),
        "underlying": _number(result.get("underlying_price")),
        "index": _number(result.get("index_price")),
        "delta": _number(greeks.get("delta")),
        "gamma": _number(greeks.get("gamma")),
        "theta": _number(greeks.get("theta")),
        "vega": _number(greeks.get("vega")),
        "rho": _number(greeks.get("rho")),
    }, ""


def group_expiries(rows: Sequence[dict[str, Any]], now: Optional[int] = None) -> list[dict[str, Any]]:
    """The chain's expiries, soonest first: the venue's code, when it expires, how many strikes."""
    at = int(now if now is not None else now_ms())
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = grouped.get(row["expiry_code"])
        if entry is None:
            entry = grouped[row["expiry_code"]] = {
                "code": row["expiry_code"], "instrument": row["expiry_instrument"],
                "ms": row["expiry_ms"], "strikes": set(), "calls": 0, "puts": 0,
            }
        entry["ms"] = min(entry["ms"], row["expiry_ms"])
        entry["strikes"].add(row["strike"])
        entry["calls" if row["option_type"] == "call" else "puts"] += 1
    out = []
    for entry in grouped.values():
        out.append({
            "code": entry["code"], "instrument": entry["instrument"], "ms": entry["ms"],
            "label": expiry_label(entry["code"]), "strikes": len(entry["strikes"]),
            "calls": entry["calls"], "puts": entry["puts"],
            "days": max(0, (entry["ms"] - at) // 86_400_000),
        })
    out.sort(key=lambda item: (item["ms"], item["code"]))
    return out


def build_ladder(rows: Sequence[dict[str, Any]], tickers: dict[str, dict[str, Any]],
                 forward: Optional[float] = None, width: int = DEFAULT_WIDTH) -> tuple[list[dict[str, Any]], float]:
    """The strike ladder around the forward: one row per strike, call and put side by side.

    Windows on the forward (not on the first or the middle strike) because a far expiry's forward
    sits thousands of points above spot — measured for BTC-25JUN27, where the index was ~76 930 and
    that series' own forward ~79 880. A strike with no ticker keeps a None side, which the panel
    shows as an em dash: an unquoted strike is not a zero.
    """
    by_strike: dict[float, dict[str, Any]] = {}
    for row in rows:
        entry = by_strike.setdefault(row["strike"], {"strike": row["strike"], "call": None, "put": None})
        side = tickers.get(row["instrument"])
        if side is not None:
            entry[row["option_type"]] = side
    ordered = sorted(by_strike.values(), key=lambda item: item["strike"])
    if not ordered:
        return [], float(forward or 0.0)
    centre = forward if (forward is not None and forward > 0) else ordered[len(ordered) // 2]["strike"]
    at = min(range(len(ordered)), key=lambda index: abs(ordered[index]["strike"] - centre))
    span = max(1, int(width))
    return ordered[max(0, at - span):at + span + 1], float(centre)


# ──────────────────────────────────────────────────────────────
# The two reads, cache-first
# ──────────────────────────────────────────────────────────────

def instruments(currency: str) -> tuple[list[dict[str, Any]], str, bool, int]:
    """Every live option Deribit lists for a currency. Returns (rows, error, cached, skipped)."""
    key = f"instruments:{currency}"
    cached = _INSTRUMENTS_CACHE.get(key)
    if cached is not None:
        return cached["rows"], "", True, cached["skipped"]
    url = f"{BASE}/get_instruments?currency={urllib.parse.quote(str(currency or '').upper())}&kind=option&expired=false"
    payload, error = get_json(url)
    if error:
        _note_error(error)
        return [], error, False, 0
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), list):
        _note_error("the instrument reply carried no list")
        return [], "the instrument reply carried no list", False, 0
    rows, skipped = parse_instruments(payload)
    _INSTRUMENTS_CACHE.put(key, {"rows": rows, "skipped": skipped})
    return rows, "", False, skipped


def one_ticker(instrument: str) -> tuple[Optional[dict[str, Any]], str, bool]:
    """One instrument's ticker. Returns (row, error, cached)."""
    name = str(instrument or "").strip().upper()
    if not name:
        return None, "no instrument given", False
    cached = _TICKER_CACHE.get(name)
    if cached is not None:
        return cached, "", True
    payload, error = get_json(f"{BASE}/ticker?instrument_name={urllib.parse.quote(name)}")
    if error:
        _note_error(f"{name}: {error}")
        return None, error, False
    row, parse_error = parse_ticker(payload)
    if row is None:
        _note_error(f"{name}: {parse_error}")
        return None, parse_error, False
    _TICKER_CACHE.put(name, row)
    return row, "", False


def tickers(names: Sequence[str]) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Tickers for many instruments: the cache first, then a bounded pool. → (rows, fetched, errors).

    Tickers have no batch endpoint (the venue answers an array with "invalid json"), so this is one
    request per instrument — bounded by WORKERS, skipped entirely for anything the 3 s cache already
    holds, and never allowed to raise: a pool that cannot start leaves the cells empty and counted.
    """
    out: dict[str, dict[str, Any]] = {}
    todo: list[str] = []
    for name in names:
        row = _TICKER_CACHE.get(str(name))
        if row is not None:
            out[str(name)] = row
        else:
            todo.append(str(name))
    errors = 0
    if todo:
        try:
            with ThreadPoolExecutor(max_workers=max(1, min(WORKERS, len(todo)))) as pool:
                for name, (row, _error, _cached) in zip(todo, pool.map(one_ticker, todo)):
                    if row is not None:
                        out[name] = row
                    else:
                        errors += 1
        except Exception as exc:                                 # noqa: BLE001 - a pool cannot take the panel down
            errors += len(todo)
            _note_error(f"ticker pool: {type(exc).__name__}: {exc}")
    return out, len(todo), errors


def _choose_expiry(expiries: Sequence[dict[str, Any]], wanted: str) -> Optional[dict[str, Any]]:
    """The expiry to build a ladder for: the caller's pick, else the nearest one still to come."""
    if not expiries:
        return None
    text = str(wanted or "").strip().upper()
    if text:
        for entry in expiries:
            if text in (entry["code"].upper(), entry["instrument"].upper()):
                return entry
    at = now_ms()
    return next((entry for entry in expiries if entry["ms"] >= at), expiries[0])


# ──────────────────────────────────────────────────────────────
# The chain: expiries + a ladder around the forward
# ──────────────────────────────────────────────────────────────

def chain(symbol: Any = "", expiry: str = "", width: int = DEFAULT_WIDTH) -> dict[str, Any]:
    """The options chain for one app symbol — expiries, and the ladder for one of them."""
    wanted = str(symbol or "").strip()
    base: dict[str, Any] = {"source": "deribit", "symbol": wanted, "at": now_ms()}
    currency = currency_for(wanted)
    if currency is None:
        return {**base, "ok": False, "coverage": False, "currency": "",
                "error": f"crypto only via Deribit — no options feed for {wanted or 'this symbol'}"
                         f" — Deribit lists BTC and ETH option chains today (SOL is spot only)"}
    rows, error, cached, skipped = instruments(currency)
    if error:
        return {**base, "ok": False, "coverage": True, "currency": currency, "cached": cached,
                "error": f"Deribit chain unavailable: {error}"}
    if not rows:
        return {**base, "ok": False, "coverage": False, "currency": currency, "cached": cached,
                "error": f"Deribit lists no {currency} options right now "
                         f"(BTC and ETH carry chains today; SOL has spot only)"}
    expiries = group_expiries(rows)
    chosen = _choose_expiry(expiries, expiry)
    if chosen is None:                                           # unreachable with rows in hand
        return {**base, "ok": False, "coverage": True, "currency": currency, "cached": cached,
                "error": f"no {currency} expiry could be read from Deribit's instrument list"}

    series = [row for row in rows if row["expiry_code"] == chosen["code"]]
    span = max(1, min(int(width or DEFAULT_WIDTH), MAX_WIDTH))
    strikes = sorted({row["strike"] for row in series})

    # Where the money is: one ticker at the middle strike of the series reports that expiry's own
    # forward (`underlying_price`), and the window is centred on it rather than on spot — a far
    # expiry's forward can sit thousands of points away from the index.
    middle = strikes[len(strikes) // 2]
    probe_name = next(row["instrument"] for row in series if row["strike"] == middle)
    probe, probe_error, probe_cached = one_ticker(probe_name)
    forward = probe["underlying"] if (probe and probe.get("underlying")) else None

    # Window the strikes first, then read only the instruments inside it.
    centre = forward if forward else middle
    at = min(range(len(strikes)), key=lambda index: abs(strikes[index] - centre))
    window = set(strikes[max(0, at - span):at + span + 1])
    window_rows = [row for row in series if row["strike"] in window]

    names = [row["instrument"] for row in window_rows]
    fetched_rows, fetched, ticker_errors = tickers(names)
    ladder, centre_strike = build_ladder(window_rows, fetched_rows, forward, span)

    quoted = sum(1 for entry in ladder for side in ("call", "put") if entry[side] is not None)
    note = (f"bid, ask, IV, open interest, volume and the Greeks come from Deribit's per-instrument "
            f"ticker ({fetched} read, {ticker_errors} failed); the ladder is the +/-{span} strikes "
            f"around {centre_strike:g}. Deribit's spacing is not uniform, so strikes are listed as "
            f"the venue publishes them.")
    if probe_error:
        note += f" The forward probe ({probe_name}) failed ({probe_error}), so the window fell back to the middle strike."
    return {
        **base, "ok": True, "coverage": True, "currency": currency, "cached": cached,
        "expiry": chosen["code"], "expiry_instrument": chosen["instrument"], "expiry_ms": chosen["ms"],
        "expiries": expiries, "strikes": ladder, "forward": centre_strike,
        "forward_from_ticker": bool(forward), "width": span, "strikes_total": len(strikes),
        "instruments_total": len(rows), "instruments_skipped": skipped, "quoted_sides": quoted,
        "tickers": fetched, "ticker_errors": ticker_errors, "probe_cached": probe_cached,
        "ticker_error_sample": list(stats()["requests"]["recent_errors"]),
        "requests": stats()["requests"], "note": note,
    }


def ticker(instrument: Any = "") -> dict[str, Any]:
    """One instrument's ticker: the Greeks, IV and open interest the ladder cannot enumerate."""
    name = str(instrument or "").strip().upper()
    base: dict[str, Any] = {"source": "deribit", "instrument": name, "at": now_ms()}
    if not name:
        return {**base, "ok": False, "error": "no instrument given — pass ?instrument=BTC-16SEP26-68000-C"}
    row, error, cached = one_ticker(name)
    if row is None:
        return {**base, "ok": False, "cached": False, "error": f"Deribit ticker unavailable: {error}"}
    return {**base, "ok": True, "cached": cached, "requests": stats()["requests"], **row}
