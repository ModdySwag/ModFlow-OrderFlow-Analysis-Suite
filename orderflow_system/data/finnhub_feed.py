"""
Finnhub feed — economic calendar + news headlines for the news panel.

Finnhub's free tier gives economic calendar events and company/news headlines.
This feed supplements the existing RSS-based news panel (CoinDesk/Cointelegraph/
Decrypt) with US economic data releases and broader market headlines.

Design rules (all deliberate):

* **No new dependency.** REST is ``urllib``.
* **Budget first.** Finnhub's free tier allows 60 calls/minute. The client keeps
  a sliding window and backs off on 429.
* **Calendar + headlines, wired as two lanes.** Two endpoints: /calendar and /news, each reached
  through the app's own routes — the Calendar view's `calendar.source = "finnhub"` lane
  (`GET /api/control/calendar?source=finnhub`) and the News panel's `context.news_source =
  "finnhub"` lane (`GET /api/atlas/context/{symbol}`). `to_calendar_rows()` / `to_news_items()`
  at the bottom are the pure adapters into the shapes those two views already read, so neither
  panel needed a second renderer. The key lives in the config's `finnhub` block and is entered
  in Settings ▸ Feed keys (masked on every read, like the other credentials).
* **Testable offline.** The transport is injected, so tests cover auth fail, 429,
  and malformed responses without touching the network.

Reference: Finnhub API v1 — /calendar, /news
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

BASE = "https://finnhub.io/api/v1"

#: Free tier: 60 calls/minute.
REST_PER_MIN = 60

#: Economic calendar categories the feed cares about.
CALENDAR_CATEGORIES = ["forex", "crypto", "indices", "stocks"]


# ── errors ────────────────────────────────────────────────────────────────────────

class FinnhubError(RuntimeError):
    def __init__(self, status: int, message: str, *, fatal: bool = False) -> None:
        self.status = int(status or 0)
        self.fatal = fatal
        self.detail = message
        super().__init__(f"[{self.status}] {message}")


def _map_status(status: int, body: str = "") -> FinnhubError:
    if status == 401:
        return FinnhubError(401,
            "Finnhub rejected the API key — check the key in the profile config.",
            fatal=True)
    elif status == 429:
        return FinnhubError(429, "Finnhub rate limit hit — backing off.")
    elif status == 0:
        return FinnhubError(0, f"Finnhub connection failed: {body}", fatal=True)
    else:
        return FinnhubError(status, f"Finnhub returned status {status}.",
                            fatal=status >= 500)


# ── rate budget ───────────────────────────────────────────────────────────────────

@dataclass
class RateBudget:
    per_minute: int = REST_PER_MIN
    window_s: float = 60.0
    _hits: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    blocked: int = 0
    _clock: Callable[[], float] = time.time

    def take(self) -> float:
        now = self._clock()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window_s]
            if len(self._hits) >= self.per_minute:
                self.blocked += 1
                return max(0.0, self.window_s - (now - self._hits[0]))
            self._hits.append(now)
            return 0.0

    @property
    def used(self) -> int:
        now = self._clock()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window_s]
            return len(self._hits)


# ── transport ─────────────────────────────────────────────────────────────────────

Transport = Callable[
    [str, str, dict[str, str], Optional[dict[str, str]], float],
    "tuple[int, dict[str, str], str]",
]


def _default_transport(method: str, url: str, headers: dict[str, str],
                        params: Optional[dict[str, str]], timeout: float):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode("utf-8", "replace")
    except Exception as exc:
        return 0, {}, f"{type(exc).__name__}: {exc}"


# ── data shape ────────────────────────────────────────────────────────────────────

@dataclass
class CalendarEvent:
    """One economic calendar event."""
    category: str                           # "forex" | "crypto" | "indices" | "stocks"
    title: str
    description: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    timezone: Optional[str] = None
    date: Optional[str] = None              # ISO "YYYY-MM-DD"
    time: Optional[str] = None              # ISO "HH:mm"
    timestamp_ms: Optional[int] = None      # epoch ms
    priority: Optional[int] = None          # 1-3 (high/medium/low)
    actual: Optional[str] = None
    consensus: Optional[str] = None
    previous: Optional[str] = None
    country: Optional[str] = None           # ISO-3166 code ("US") — the calendar view's filter domain


@dataclass
class Calendar:
    events: list[CalendarEvent] = field(default_factory=list)
    fetched_ms: int = 0
    error: Optional[str] = None


@dataclass
class NewsItem:
    """One news headline."""
    category: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    image: Optional[str] = None
    published_ms: Optional[int] = None      # epoch ms
    associated_stock: Optional[str] = None


@dataclass
class NewsBatch:
    items: list[NewsItem] = field(default_factory=list)
    fetched_ms: int = 0
    error: Optional[str] = None


# ── client ────────────────────────────────────────────────────────────────────────

class FinnhubFeed:
    """REST client for Finnhub's calendar and news APIs."""

    def __init__(self, *, api_key: str = "", base: str = BASE,
                 transport: Optional[Transport] = None,
                 budget: Optional[RateBudget] = None, timeout: float = 12.0,
                 clock: Callable[[], float] = time.time) -> None:
        self.api_key = (api_key or "").strip()
        self.base = base or BASE
        self.transport = transport or _default_transport
        self.budget = budget or RateBudget()
        self.timeout = timeout
        self.last_error: Optional[str] = None

    def _auth_params(self) -> dict[str, str]:
        return {"token": self.api_key} if self.api_key else {}

    # ── calendar ─────────────────────────────────────────────────────────────────

    def calendar(self, category: str = "all", *, days: int = 7) -> Calendar:
        """Fetch economic calendar events for the next `days` days.

        Parameters
        ----------
        category : "all" | "forex" | "crypto" | "indices" | "stocks".
        days : number of days forward to fetch.
        """
        params = self._auth_params()
        params["category"] = category
        params["from"] = int(time.time()) - 86400         # yesterday
        params["to"] = int(time.time()) + days * 86400    # ahead

        wait = self.budget.take()
        if wait > 0:
            time.sleep(wait)

        status, _, body = self.transport("GET",
            f"{self.base}/calendar", {}, params, self.timeout)

        if status != 200:
            err = _map_status(status, body)
            self.last_error = err.detail
            logger.warning("Finnhub calendar failed: %s", err.detail)
            return Calendar(events=[], error=err.detail)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.last_error = "malformed Finnhub calendar response"
            logger.warning(self.last_error)
            return Calendar(events=[], error=self.last_error)

        events = self._parse_calendar(data)
        return Calendar(events=events, fetched_ms=int(time.time() * 1000))

    def _parse_calendar(self, data: list[dict[str, Any]] | dict[str, Any]) -> list[CalendarEvent]:
        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("calendar") or data.get("events") or [data]
        else:
            return []

        events: list[CalendarEvent] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("timestamp")
            try:
                ts_ms = int(ts) * 1000 if ts else None
            except (TypeError, ValueError):
                ts_ms = None

            events.append(CalendarEvent(
                category=str(entry.get("category") or "other"),
                title=str(entry.get("title") or entry.get("event") or ""),
                description=str(entry.get("description") or "") or None,
                source=str(entry.get("source") or "") or None,
                url=str(entry.get("url") or "") or None,
                timezone=str(entry.get("timezone") or "") or None,
                date=str(entry.get("date") or ""),
                time=str(entry.get("time") or ""),
                timestamp_ms=ts_ms,
                priority=self._int(entry.get("priority")),
                actual=str(entry.get("actual") or "") or None,
                consensus=str(entry.get("consensus") or "") or None,
                previous=str(entry.get("previous") or "") or None,
                country=str(entry.get("country") or "") or None,
            ))
        return events

    # ── news ─────────────────────────────────────────────────────────────────────

    def news(self, category: str = "general", *, start_ts: Optional[int] = None,
             end_ts: Optional[int] = None) -> NewsBatch:
        """Fetch news headlines for a category.

        Parameters
        ----------
        category : "general" | "federal Reserve" | "economic" | etc.
        start_ts : epoch seconds start (optional).
        end_ts : epoch seconds end (optional).
        """
        params = self._auth_params()
        params["category"] = category
        if start_ts is not None:
            params["from"] = str(start_ts)
        if end_ts is not None:
            params["to"] = str(end_ts)

        wait = self.budget.take()
        if wait > 0:
            time.sleep(wait)

        status, _, body = self.transport("GET",
            f"{self.base}/news", {}, params, self.timeout)

        if status != 200:
            err = _map_status(status, body)
            self.last_error = err.detail
            logger.warning("Finnhub news failed: %s", err.detail)
            return NewsBatch(items=[], error=err.detail)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.last_error = "malformed Finnhub news response"
            logger.warning(self.last_error)
            return NewsBatch(items=[], error=self.last_error)

        items = self._parse_news(data)
        return NewsBatch(items=items, fetched_ms=int(time.time() * 1000))

    def _parse_news(self, data: list[dict[str, Any]] | dict[str, Any]) -> list[NewsItem]:
        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("news") or [data]
        else:
            return []

        result: list[NewsItem] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("datetime")
            try:
                ts_ms = int(ts) * 1000 if ts else None
            except (TypeError, ValueError):
                ts_ms = None

            result.append(NewsItem(
                category=str(entry.get("category") or "") or None,
                headline=str(entry.get("headline") or entry.get("title") or "") or None,
                summary=str(entry.get("summary") or "") or None,
                source=str(entry.get("source") or "") or None,
                url=str(entry.get("url") or "") or None,
                image=str(entry.get("image") or "") or None,
                published_ms=ts_ms,
                associated_stock=str(entry.get("related") or "") or None,
            ))
        return result

    @staticmethod
    def _int(v: Any) -> Optional[int]:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _num(v: Any) -> Optional[float]:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    def status(self) -> dict[str, Any]:
        return {
            "source": "finnhub",
            "key_configured": bool(self.api_key),
            "used": self.budget.used,
            "limit": self.budget.per_minute,
            "last_error": self.last_error,
        }


# ── adapters into the app's shapes ───────────────────────────────────────────────
#
# Pure, so the two lanes' mapping is pinned without a socket and a shape change cannot slip
# through as a rendering bug. The targets are the shapes the views already read:
#   desktop/calendar.py :: normalise_event  -> {at_ms, currency, impact, title, country, …}
#   atlas/context.py :: parse_rss           -> {title, link, published, source, published_ms}

#: Finnhub labels its economic events by priority; the calendar view speaks impact. 1 = high
#: (Finnhub's own labelling). An unknown priority maps to "unknown" rather than to a guess, and
#: the view's own impact filter treats "unknown" as below the floor — never as a silent "high".
IMPACT_BY_PRIORITY = {1: "high", 2: "medium", 3: "low"}


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_calendar_rows(events: Any) -> list[dict[str, Any]]:
    """Finnhub calendar events in the calendar view's normalised row shape.

    A row with no clock is dropped: the view places every release on a timeline and a title with
    no time would sit at an invented position (the same rule ``desktop/calendar.py`` applies to a
    row whose date will not parse). A title-less row is dropped for the same reason — an empty
    cell in the table is noise, not information.
    """
    rows: list[dict[str, Any]] = []
    for event in events or ():
        at_ms = _int_or_none(getattr(event, "timestamp_ms", None))
        title = str(getattr(event, "title", "") or "").strip()
        if at_ms is None or not title:
            continue
        country = str(getattr(event, "country", "") or "").strip()
        rows.append({
            "at_ms": at_ms,
            "currency": country.upper(),
            "impact": IMPACT_BY_PRIORITY.get(_int_or_none(getattr(event, "priority", None)), "unknown"),
            "title": title,
            "country": country,
            "forecast": str(getattr(event, "consensus", "") or ""),
            "previous": str(getattr(event, "previous", "") or ""),
            "actual": str(getattr(event, "actual", "") or ""),
        })
    rows.sort(key=lambda row: row["at_ms"])
    return rows


def to_news_items(batch: Any, *, fallback_source: str = "finnhub") -> list[dict[str, Any]]:
    """Finnhub headlines in the News panel's item shape.

    ``link`` is blank unless it is really http(s): the panel renders a link only then, and a
    non-web URL in an anchor is a dead end (the same rule ``atlas/context.py``'s parser applies).
    ``published`` is left empty on purpose — the panel orders by ``published_ms``, and inventing
    an RSS-style string from it would be a second, unchecked representation of the same instant.
    """
    items: list[dict[str, Any]] = []
    for item in getattr(batch, "items", None) or ():
        title = str(getattr(item, "headline", "") or "").strip()
        if not title:
            continue
        link = str(getattr(item, "url", "") or "").strip()
        items.append({
            "title": title[:200],
            "link": link if link.lower().startswith(("http://", "https://")) else "",
            "published": "",
            "source": str(getattr(item, "source", "") or "").strip() or fallback_source,
            "published_ms": _int_or_none(getattr(item, "published_ms", None)),
        })
    return items
