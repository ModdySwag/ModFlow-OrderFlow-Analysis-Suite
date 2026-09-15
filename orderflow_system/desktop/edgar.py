"""Fundamentals for the instrument the app is showing — SEC EDGAR filings, or CoinGecko for crypto.

Two keyless public sources, one decision, one payload:

* **SEC EDGAR** (US filers only) — the filed numbers, straight from the filings' XBRL.
  ``https://www.sec.gov/files/company_tickers.json`` maps a ticker to a CIK (214 KB, changes
  rarely → cached for the session), and ``https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json``
  carries every fact that filer ever tagged (Apple's is ~3.8 MB → fetched and reduced HERE, on the
  server; the browser only ever receives the few headline rows the panel draws).
* **CoinGecko** (crypto, keyless) — rank, market cap, supply and the 24 h move for the majors the
  suite streams. Crypto has no filings, and this module never pretends otherwise.

The rules this module exists to enforce
--------------------------------------

* **A declared User-Agent is mandatory.** Measured from this machine: a sloppy UA
  (``ModFlow OrderFlow Analysis Suite (contact: moddys.net)``) gets HTTP 403 from sec.gov, the
  declared one below gets 200. It lives in exactly one constant, every request carries it, and
  requests are spaced (``MIN_INTERVAL_S``) to stay far below EDGAR's 10/s ceiling.
* **Annual filings only.** A 10-Q's three-month revenue rendered next to a 10-K's full year is a
  lie with a decimal point, so a row is only built from an annual report form (10-K/20-F/40-F and
  their amendments) *and* from a period that really is a year long (330–400 days) when the fact is
  a flow. Instant facts (assets, equity) have no period length to check.
* **The newest period wins, and the tag is named.** A concept is read from its primary XBRL tag and
  its documented fallbacks (Apple tags ``Revenues`` only up to FY2018 and has used
  ``RevenueFromContractWithCustomerExcludingAssessedTax`` since, so a primary-only reader would
  show a 2018 number as today's revenue). Rows are ordered by period end, a restated comparative
  from a later filing replaces the earlier one for the same period, and every row carries the tag it
  came from so nothing on screen is unattributable.
* **A missing concept is a missing row — never a zero, never a dash.** A filer that does not tag
  ``GrossProfit`` (banks do not) simply has one fewer row; a genuine 0 in the data stays a 0.
* **Nothing raises out of this module.** The panel is a panel: a 403, a timeout, a symbol the SEC
  has never heard of and an instrument with no fundamentals source at all each come back as data
  (``ok: False`` + an ``error`` sentence, or ``source: "none"`` + the sentence that says why), and
  the route below always answers JSON.

Coverage, stated honestly: US filers (no non-US issuers, no indices, no FX, no market cap, no
valuation ratios) and the crypto majors in ``CRYPTO_IDS``. Everything else answers
``source: "none"`` with the sentence the panel shows.

The network call is one injectable seam (``FundamentalsService(fetch=...)``) so the tests — and this
module's gate, ``orderflow_system/test_fundamentals.py`` — never touch the internet.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# The constants that matter
# ──────────────────────────────────────────────────────────────

#: THE declared User-Agent — one constant, every EDGAR request. sec.gov answers 403 to anything
#: that does not name an application and a contact (verified from this machine, both ways).
USER_AGENT = "ModFlow-OrderFlow-Suite/1.0 (moddy@moddys.net)"

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

#: How long each answer is kept. The ticker map changes when a company lists; a filer's facts change
#: quarterly (a refresh within the hour is already generous); CoinGecko's prices are the only thing
#: here that moves by the minute.
TTL_TICKERS_S = 21600.0
TTL_FACTS_S = 21600.0
TTL_CRYPTO_S = 60.0

#: Spacing between actual requests: ~4/s, comfortably under EDGAR's 10/s and CoinGecko's free tier.
MIN_INTERVAL_S = 0.25
TIMEOUT_S = 12.0

#: Annual report forms. A quarterly or current report is never a row (see the module docstring).
ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A")

#: A "year long" period, with room for 52/53-week fiscal years.
MIN_ANNUAL_DAYS = 330
MAX_ANNUAL_DAYS = 400

#: How many periods per concept the payload carries (the newest ones).
MAX_PERIODS_PER_CONCEPT = 4

#: The sentence for an instrument neither source covers. One constant, so the panel and the server
#: cannot drift apart on the wording.
NO_SOURCE_NOTE = ("no fundamentals source for {symbol} — EDGAR covers US filings, "
                  "CoinGecko covers crypto")

#: Bybit symbols → CoinGecko coin ids. Every id below was verified live (one /coins/markets call)
#: against the suite's own crypto universe: ``config.settings.CRYPTO_MAJORS`` plus BTCUSDT. The id
#: is spelled out rather than derived from the ticker because a symbol match is not an identity —
#: CoinGecko's ``the-open-network`` now trades as "gram", and ``matic-network`` still exists with a
#: null rank and a 0 market cap while POL is ``polygon-ecosystem-token``.
CRYPTO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "DOT": "polkadot",
    "TRX": "tron",
    "SUI": "sui",
    "APT": "aptos",
    "NEAR": "near",
    "ARB": "arbitrum",
    "OP": "optimism",
    "POL": "polygon-ecosystem-token",
    "TON": "the-open-network",
}

#: Perp/quote suffixes a venue symbol carries. Longest first, so USDT is stripped before USD.
CRYPTO_SUFFIXES = ("USDT", "USDC", "BUSD", "FDUSD", "USD")


@dataclass(frozen=True)
class Concept:
    """One headline line on the panel: the tag to read, what to call it, and how it behaves."""

    key: str                 #: stable key the panel's picker uses
    label: str               #: what the row is called on screen
    unit: str                #: the XBRL unit to read (USD, USD/shares)
    tags: tuple[str, ...]    #: primary XBRL tag first, then the documented fallbacks
    kind: str = "flow"       #: 'flow' (an income-statement period) or 'instant' (a balance)


#: What the panel headlines, in the order it shows them. ``latest`` in the payload marks each
#: concept's newest period; the older ones are context, and every row names the tag it came from.
HEADLINES: tuple[Concept, ...] = (
    Concept("revenue", "Revenue", "USD",
            ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")),
    Concept("net_income", "Net income", "USD", ("NetIncomeLoss", "ProfitLoss")),
    Concept("eps_diluted", "EPS (diluted)", "USD/shares", ("EarningsPerShareDiluted",)),
    Concept("gross_profit", "Gross profit", "USD", ("GrossProfit",)),
    Concept("assets", "Total assets", "USD", ("Assets",), kind="instant"),
    Concept("equity", "Stockholders' equity", "USD",
            ("StockholdersEquity",
             "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
            kind="instant"),
)


class FetchError(RuntimeError):
    """A fetch that failed, with a sentence the panel can print as-is."""


def _host(url: str) -> str:
    return urlsplit(str(url)).hostname or str(url)


def http_json(url: str, user_agent: str = USER_AGENT, timeout_s: float = TIMEOUT_S) -> Any:
    """The only place this module touches the network: the declared UA, a timeout, a clean error.

    Every failure becomes a :class:`FetchError` carrying what actually happened — a 403 that names
    the User-Agent rule, a host that did not answer, a body that was not JSON. Nothing else is
    swallowed here; the service turns whatever comes out into ``ok: False`` + ``error``.
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        hint = ""
        if exc.code in (401, 403, 429):
            if "sec.gov" in _host(url):
                hint = (" — SEC EDGAR refuses a request whose User-Agent does not name an "
                        "application and a contact")
            else:
                hint = " — the endpoint refused the request (missing key or over its rate limit)"
        raise FetchError(f"HTTP {exc.code} {exc.reason} from {_host(url)}{hint}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"{_host(url)} did not answer: {exc.reason}") from exc
    except OSError as exc:
        raise FetchError(f"{_host(url)} failed: {exc}") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise FetchError(f"{_host(url)} answered with something that is not JSON: {exc}") from exc


# ──────────────────────────────────────────────────────────────
# The decision half — pure, no clock, no network (pinned by the gate and the panel's selftest)
# ──────────────────────────────────────────────────────────────

def normalize_symbol(symbol: Any) -> str:
    """The symbol as this module compares it: trimmed, upper-case, no exchange noise."""
    return str(symbol if symbol is not None else "").strip().upper()


def crypto_asset(symbol: Any) -> str:
    """The CoinGecko id for a venue symbol, or '' when it is not one of the mapped coins.

    ``BTCUSDT`` → ``bitcoin``, ``ethusdt`` → ``ethereum``, ``BTC`` → ``bitcoin``; ``NAS100USDT``
    and ``XAUUSDT`` strip to bases nothing maps, which is exactly the point: an index or a metal
    must fall through to the honest "no source" answer, not to a wrong coin.
    """
    text = normalize_symbol(symbol)
    if not text:
        return ""
    if text in CRYPTO_IDS:
        return CRYPTO_IDS[text]
    for suffix in sorted(CRYPTO_SUFFIXES, key=len, reverse=True):
        if len(text) > len(suffix) and text.endswith(suffix):
            base = text[: -len(suffix)]
            if base in CRYPTO_IDS:
                return CRYPTO_IDS[base]
    return ""


def _is_date(text: Any) -> bool:
    parts = str(text or "").split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return False
    try:
        date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return False
    return True


def _days_between(start: Any, end: Any) -> Optional[int]:
    if not (_is_date(start) and _is_date(end)):
        return None
    y1, m1, d1 = (int(x) for x in str(start).split("-"))
    y2, m2, d2 = (int(x) for x in str(end).split("-"))
    return (date(y2, m2, d2) - date(y1, m1, d1)).days


def units_of(doc: Any, tag: str, unit: str) -> list[dict[str, Any]]:
    """``facts['us-gaap'][tag]['units'][unit]`` — a list, or an empty list, never a throw."""
    gaap = ((doc or {}).get("facts") or {}).get("us-gaap")
    if not isinstance(gaap, dict):
        return []
    node = gaap.get(tag)
    if not isinstance(node, dict):
        return []
    rows = (node.get("units") or {}).get(unit)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _candidates(doc: Any, concept: Concept) -> dict[str, dict[str, Any]]:
    """Every annual, correctly-lengthed fact for one headline, keyed by period end.

    The winner for a period is the most recently *filed* value (a restated comparative in a later
    report replaces the number the earlier report carried); on the same filing date the earlier tag
    in the concept's list wins, so the primary tag is never displaced by its fallback.
    """
    best: dict[str, dict[str, Any]] = {}
    for rank, tag in enumerate(concept.tags):
        for raw in units_of(doc, tag, concept.unit):
            form = str(raw.get("form") or "")
            if form not in ANNUAL_FORMS:
                continue                                    # a 10-Q never becomes a row
            end = str(raw.get("end") or "")
            if not _is_date(end):
                continue
            val = raw.get("val")
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                continue
            start = str(raw.get("start") or "")
            if concept.kind == "flow":
                if not start:
                    continue                                # a flow with no period is not a year
                days = _days_between(start, end)
                if days is None or not (MIN_ANNUAL_DAYS <= days <= MAX_ANNUAL_DAYS):
                    continue                                # a quarter tagged FY is still a quarter
            candidate = {
                "tag": tag, "value": val, "unit": concept.unit, "form": form,
                "filed": str(raw.get("filed") or ""), "period": end, "start": start,
                "fy": raw.get("fy") if isinstance(raw.get("fy"), int) else None,
                "_rank": rank,
            }
            held = best.get(end)
            if held is None or (candidate["filed"], -candidate["_rank"]) > (
                    held["filed"], -held["_rank"]):
                best[end] = candidate
    return best


def reduce_company_facts(doc: Any,
                         headlines: tuple[Concept, ...] = HEADLINES,
                         max_periods: int = MAX_PERIODS_PER_CONCEPT) -> list[dict[str, Any]]:
    """A companyfacts document → the rows the panel shows, newest period first, per concept.

    One pass per headline so the payload keeps the panel's order (revenue, income, EPS, gross
    profit, assets, equity), newest period first inside each, ``latest`` on the first of each
    concept. A concept the filer does not tag (or only tags in quarters) contributes nothing at
    all: no zero, no dash, no row.
    """
    rows: list[dict[str, Any]] = []
    for concept in headlines:
        periods = sorted(_candidates(doc, concept).items(),
                         key=lambda item: (item[1]["period"], item[1]["filed"]), reverse=True)
        for index, (_end, held) in enumerate(periods[:max(0, int(max_periods))]):
            rows.append({
                "concept": concept.key,
                "label": concept.label,
                "tag": held["tag"],
                "value": held["value"],
                "unit": held["unit"],
                "form": held["form"],
                "filed": held["filed"],
                "period": held["period"],
                "start": held["start"],
                "fy": held["fy"],
                "latest": index == 0,
            })
    return rows


def cik_for(table: Any, symbol: Any) -> str:
    """The zero-padded CIK for a ticker, or ''. ``BRK.B`` and ``BRK-B`` are the same issuer."""
    wanted = normalize_symbol(symbol)
    if not wanted or not isinstance(table, dict):
        return ""
    for candidate in (wanted, wanted.replace(".", "-"), wanted.replace("-", ".")):
        row = table.get(candidate)
        if isinstance(row, dict) and row.get("cik"):
            return str(row["cik"])
    return ""


def _num(value: Any) -> Optional[float]:
    """A number, or None — never NaN, never a string dressed as a price."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


# ──────────────────────────────────────────────────────────────
# The service: cache, spacing, and a payload that never throws
# ──────────────────────────────────────────────────────────────

class FundamentalsService:
    """Cached, space-out reader for the two sources. ``fetch`` is the injectable seam."""

    def __init__(self,
                 fetch: Optional[Callable[[str, str, float], Any]] = None,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 ttl_tickers_s: float = TTL_TICKERS_S,
                 ttl_facts_s: float = TTL_FACTS_S,
                 ttl_crypto_s: float = TTL_CRYPTO_S,
                 min_interval_s: float = MIN_INTERVAL_S) -> None:
        self._fetch = fetch or http_json
        self._clock = clock
        self._sleep = sleep
        self.ttl_tickers_s = ttl_tickers_s
        self.ttl_facts_s = ttl_facts_s
        self.ttl_crypto_s = ttl_crypto_s
        self.min_interval_s = min_interval_s
        self._cache: dict[str, tuple[float, Any]] = {}
        self._last_call = 0.0
        self.counters = {"requests": 0, "cache_hits": 0, "ticker_maps": 0, "facts": 0, "crypto": 0}

    # ── cache + transport ─────────────────────────────────────────────────────────────────────

    def _cached(self, key: str, ttl_s: float, producer: Callable[[], Any]) -> Any:
        held = self._cache.get(key)
        now = self._clock()
        if held is not None and (now - held[0]) < ttl_s:
            self.counters["cache_hits"] += 1
            return held[1]
        value = producer()                       # a failure is NOT cached: the next ask retries
        self._cache[key] = (self._clock(), value)
        return value

    def _get_json(self, url: str) -> Any:
        wait = self.min_interval_s - (self._clock() - self._last_call)
        if wait > 0:
            self._sleep(wait)                    # stay far below EDGAR's 10 requests/second
        self._last_call = self._clock()
        self.counters["requests"] += 1
        return self._fetch(url, USER_AGENT, TIMEOUT_S)

    def cache_clear(self) -> None:
        self._cache.clear()
        self._last_call = 0.0

    # ── EDGAR ─────────────────────────────────────────────────────────────────────────────────

    def ticker_map(self) -> dict[str, dict[str, str]]:
        """``{TICKER: {cik, title}}`` from the SEC's own map — cached for the session."""
        raw = self._cached("edgar:tickers", self.ttl_tickers_s, lambda: self._get_json(TICKERS_URL))
        self.counters["ticker_maps"] += 1
        table: dict[str, dict[str, str]] = {}
        if isinstance(raw, dict):
            for row in raw.values():
                if not isinstance(row, dict):
                    continue
                ticker = normalize_symbol(row.get("ticker"))
                cik = row.get("cik_str")
                if not ticker or isinstance(cik, bool) or not isinstance(cik, int):
                    continue
                table.setdefault(ticker, {"cik": str(cik).zfill(10),
                                          "title": str(row.get("title") or "")})
        return table

    def company_facts(self, cik: str) -> Any:
        """The filer's whole companyfacts document — parsed here, never handed to the browser."""
        self.counters["facts"] += 1
        return self._cached(f"edgar:facts:{cik}", self.ttl_facts_s,
                            lambda: self._get_json(FACTS_URL.format(cik=cik)))

    def _edgar_payload(self, symbol: str) -> dict[str, Any]:
        table = self.ticker_map()
        cik = cik_for(table, symbol)
        if not cik:
            return {"ok": True, "symbol": symbol, "source": "none", "rows": [],
                    "note": NO_SOURCE_NOTE.format(symbol=symbol)}
        entry = table.get(symbol) or {}
        doc = self.company_facts(cik)
        rows = reduce_company_facts(doc)
        company = {"cik": cik, "ticker": symbol,
                   "name": str(entry.get("title") or (doc or {}).get("entityName") or "")}
        payload: dict[str, Any] = {"ok": True, "symbol": symbol, "source": "edgar",
                                   "company": company, "rows": rows}
        if not rows:
            payload["note"] = ("the SEC facts for " + symbol + " carry none of the headline "
                               "concepts this panel shows (annual filings only)")
        else:
            payload["note"] = ("annual filings only (" + ", ".join(
                sorted({row["form"] for row in rows}))
                + ") — a quarter's figure never sits next to a year's")
        return payload

    # ── CoinGecko ─────────────────────────────────────────────────────────────────────────────

    def crypto_payload(self, symbol: str, coin_id: str) -> dict[str, Any]:
        """Rank, market cap, supply and the 24 h move for one coin — cached briefly."""
        self.counters["crypto"] += 1
        url = f"{COINGECKO_MARKETS_URL}?vs_currency=usd&ids={coin_id}"
        rows = self._cached(f"cg:{coin_id}", self.ttl_crypto_s, lambda: self._get_json(url))
        row = next((r for r in rows if isinstance(r, dict) and str(r.get("id")) == coin_id), None) \
            if isinstance(rows, list) else None
        if row is None:
            return {"ok": False, "symbol": symbol, "source": "coingecko", "rows": [],
                    "error": f"CoinGecko returned no row for {coin_id}"}
        crypto = {
            "id": coin_id,
            "name": str(row.get("name") or ""),
            "ticker": str(row.get("symbol") or "").upper(),
            "rank": row.get("market_cap_rank") if isinstance(row.get("market_cap_rank"), int) else None,
            "price": _num(row.get("current_price")),
            "market_cap": _num(row.get("market_cap")),
            "volume_24h": _num(row.get("total_volume")),
            "circulating_supply": _num(row.get("circulating_supply")),
            "total_supply": _num(row.get("total_supply")),
            "max_supply": _num(row.get("max_supply")),
            "change_24h": _num(row.get("price_change_percentage_24h")),
            "as_of": str(row.get("last_updated") or ""),
        }
        return {"ok": True, "symbol": symbol, "source": "coingecko", "rows": [], "crypto": crypto,
                "note": ("market data from CoinGecko's keyless public endpoint — crypto has no SEC "
                         "filings, so this is supply and price, not an audited statement")}

    # ── the one entry point the route uses ────────────────────────────────────────────────────

    def payload(self, symbol: Any) -> dict[str, Any]:
        """Everything the panel needs for one symbol. Never raises; failures are ``ok: False``."""
        text = normalize_symbol(symbol)
        if not text:
            return {"ok": False, "symbol": "", "source": "none", "rows": [],
                    "error": "no instrument is active, so there is no symbol to look up"}
        try:
            coin = crypto_asset(text)
            if coin:
                return self.crypto_payload(text, coin)
            return self._edgar_payload(text)
        except Exception as exc:                     # a panel never gets a stack trace
            logger.debug("fundamentals lookup failed for %s", text, exc_info=True)
            message = str(exc) if isinstance(exc, FetchError) else f"{type(exc).__name__}: {exc}"
            return {"ok": False, "symbol": text, "source": "none", "rows": [], "error": message}

    # ── introspection for the tests and the audit ─────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {"counters": dict(self.counters), "cached": sorted(self._cache),
                "user_agent": USER_AGENT}


#: The process-wide reader the route uses (tests swap in their own, or a stubbed fetch).
SERVICE = FundamentalsService()

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}")
async def fundamentals_for_symbol(symbol: str) -> dict[str, Any]:
    """Headline fundamentals for ``symbol``: EDGAR rows, a CoinGecko block, or the reason for none.

    Blocking I/O runs in a worker thread (the same rule the rest of the suite's public-endpoint
    readers follow) so a slow 3.8 MB companyfacts fetch cannot stall the event loop.
    """
    return await asyncio.to_thread(SERVICE.payload, symbol)
