"""Free market-context integrations — no keys, no accounts, nothing to sign up for.

Three public sources, all optional and all failing soft:

* **Bybit v5 public market endpoints** — funding rate, next funding time, open
  interest, 24h turnover and the long/short account ratio for the selected
  perpetual. Public perps price carry and positioning; no key needed.
* **alternative.me Fear & Greed index** — one number that says whether the
  market is euphoric or capitulating, free and keyless.
* **RSS news** — CoinDesk / Cointelegraph / Decrypt, or any feed URL the user
  pastes. Headlines only, links out to the article.

Design rules, learned the hard way with public endpoints:

* A fetcher NEVER raises into the trading path: failures come back as
  ``{"ok": False, "error": ...}`` and the UI shows "unavailable".
* Every source has its own TTL cache — funding changes every few seconds, news
  every few minutes, Fear & Greed once a day. Hammering them is what gets a
  public IP throttled.
* All network calls run in a worker thread (``asyncio.to_thread``) with explicit
  timeouts so a slow feed cannot stall the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Iterable, Optional
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

#: Default feeds — all public RSS, no key. A user-supplied URL replaces them.
DEFAULT_NEWS_FEEDS: tuple[str, ...] = (
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
)

_BYBIT_TICKERS = "https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
_BYBIT_RATIO = (
    "https://api.bybit.com/v5/market/account-ratio"
    "?category=linear&symbol={symbol}&period=5min&limit=1"
)
_FEAR_GREED = "https://api.alternative.me/fng/?limit=1"

_USER_AGENT = "OrderFlow-Analysis-Pro/1.0 (market context; public endpoints)"


def _fetch_text(url: str, timeout_s: float = 8.0) -> str:
    """Blocking GET with a browser-ish UA (a couple of these feeds 403 a bare one)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_json(url: str, timeout_s: float = 8.0) -> Any:
    return json.loads(_fetch_text(url, timeout_s=timeout_s))


def parse_rss(xml_text: str, source: str = "", limit: int = 12) -> list[dict[str, Any]]:
    """Pull (title, link, published) out of an RSS or Atom document.

    ElementTree needs namespace-agnostic matching for Atom, so every tag is
    compared on its local name.
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        logger.debug("news feed %s did not parse: %s", source, exc)
        return []

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    items: list[dict[str, Any]] = []
    for node in root.iter():
        if local(node.tag) not in ("item", "entry"):
            continue
        title, link, published = "", "", ""
        for child in node:
            name = local(child.tag)
            if name == "title" and not title:
                title = (child.text or "").strip()
            elif name == "link" and not link:
                link = (child.attrib.get("href") or child.text or "").strip()
            elif name in ("pubdate", "published", "updated", "date") and not published:
                published = (child.text or "").strip()
        if not title:
            continue
        items.append({
            "title": re.sub(r"\s+", " ", title)[:200],
            "link": link,
            "published": published,
            "source": source,
        })
        if len(items) >= limit:
            break
    return items


def _parse_published(value: str) -> Optional[int]:
    """Best-effort RFC-822 / ISO-8601 → epoch ms (the UI only needs ordering)."""
    if not value:
        return None
    text = value.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            import datetime as _dt
            return int(_dt.datetime.strptime(text, fmt).timestamp() * 1000)
        except Exception:
            continue
    return None


class MarketContext:
    """Cached, failure-tolerant reader for the free context sources."""

    def __init__(
        self,
        ttl_positioning_s: float = 60.0,
        ttl_fear_greed_s: float = 3600.0,
        ttl_news_s: float = 300.0,
        news_feeds: Optional[Iterable[str]] = None,
        timeout_s: float = 8.0,
    ) -> None:
        self.ttl_positioning_s = float(ttl_positioning_s)
        self.ttl_fear_greed_s = float(ttl_fear_greed_s)
        self.ttl_news_s = float(ttl_news_s)
        self.news_feeds = tuple(news_feeds or DEFAULT_NEWS_FEEDS)
        self.timeout_s = float(timeout_s)
        self._cache: dict[str, tuple[float, Any]] = {}
        self.requests = 0
        self.failures = 0
        self.last_error = ""

    # ── cache ─────────────────────────────────────────────────
    def _cached(self, key: str, ttl: float, producer) -> Any:
        now = time.time()
        hit = self._cache.get(key)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
        value = producer()
        self._cache[key] = (now, value)
        return value

    # ── sources ───────────────────────────────────────────────
    def positioning(self, symbol: str) -> dict[str, Any]:
        """Funding, open interest and the long/short ratio for one perpetual."""
        def load() -> dict[str, Any]:
            sym = symbol.upper()
            out: dict[str, Any] = {"ok": False, "symbol": sym}
            self.requests += 1
            try:
                payload = _fetch_json(_BYBIT_TICKERS.format(symbol=sym), timeout_s=self.timeout_s)
                row = ((payload.get("result") or {}).get("list") or [{}])[0]
                if not row:
                    raise ValueError("symbol not listed on the venue")
                funding = float(row.get("fundingRate") or 0.0)
                out.update({
                    "ok": True,
                    "last_price": float(row.get("lastPrice") or 0.0),
                    "change_24h_pct": float(row.get("price24hPcnt") or 0.0) * 100.0,
                    "turnover_24h": float(row.get("turnover24h") or 0.0),
                    "volume_24h": float(row.get("volume24h") or 0.0),
                    "funding_rate": funding,
                    "funding_pct": funding * 100.0,
                    "next_funding_ms": int(row.get("nextFundingTime") or 0),
                    "open_interest": float(row.get("openInterest") or 0.0),
                    "open_interest_value": float(row.get("openInterestValue") or 0.0),
                })
            except Exception as exc:
                self.failures += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                out["error"] = self.last_error
                return out
            try:
                ratio_payload = _fetch_json(_BYBIT_RATIO.format(symbol=sym), timeout_s=self.timeout_s)
                ratio_row = ((ratio_payload.get("result") or {}).get("list") or [{}])[0]
                buy = float(ratio_row.get("buyRatio") or 0.0)
                sell = float(ratio_row.get("sellRatio") or 0.0)
                if buy or sell:
                    out["long_short_ratio"] = round(buy / sell, 3) if sell else None
                    out["buy_ratio"] = round(buy, 4)
                    out["sell_ratio"] = round(sell, 4)
            except Exception as exc:                     # ratio is optional, keep the rest
                logger.debug("long/short ratio unavailable for %s: %s", sym, exc)
            return out

        return self._cached(f"positioning:{symbol.upper()}", self.ttl_positioning_s, load)

    def fear_greed(self) -> dict[str, Any]:
        """Alternative.me Fear & Greed — one number, updated daily."""
        def load() -> dict[str, Any]:
            self.requests += 1
            try:
                payload = _fetch_json(_FEAR_GREED, timeout_s=self.timeout_s)
                row = (payload.get("data") or [{}])[0]
                return {
                    "ok": True,
                    "value": int(row.get("value") or 0),
                    "label": str(row.get("value_classification") or ""),
                    "ts_ms": int(row.get("timestamp") or 0) * 1000,
                }
            except Exception as exc:
                self.failures += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                return {"ok": False, "error": self.last_error}

        return self._cached("fear_greed", self.ttl_fear_greed_s, load)

    def news(self, limit: int = 8, feed_url: str = "") -> list[dict[str, Any]]:
        """Headlines from the configured feeds, newest-ish first, tags stripped."""
        feeds = (feed_url.strip(),) if feed_url.strip() else self.news_feeds

        def load() -> list[dict[str, Any]]:
            self.requests += 1
            items: list[dict[str, Any]] = []
            for feed in feeds:
                try:
                    text = _fetch_text(feed, timeout_s=self.timeout_s)
                except Exception as exc:
                    self.failures += 1
                    self.last_error = f"{feed}: {type(exc).__name__}: {exc}"
                    continue
                source = feed.split("/")[2] if "/" in feed else feed
                for item in parse_rss(text, source=source, limit=limit):
                    item["published_ms"] = _parse_published(item.get("published", ""))
                    items.append(item)
            items.sort(key=lambda i: i.get("published_ms") or 0, reverse=True)
            return items[:limit]

        return self._cached(f"news:{','.join(feeds)}:{limit}", self.ttl_news_s, load)

    # ── aggregate ─────────────────────────────────────────────
    async def snapshot(
        self,
        symbol: str,
        include: Optional[Iterable[str]] = None,
        news_limit: int = 8,
        feed_url: str = "",
    ) -> dict[str, Any]:
        """One JSON payload for the UI card; each section degrades on its own."""
        wanted = set(include or ("positioning", "fear_greed", "news"))
        out: dict[str, Any] = {"ok": True, "symbol": symbol.upper(), "ts_ms": int(time.time() * 1000)}

        if "positioning" in wanted:
            out["positioning"] = await asyncio.to_thread(self.positioning, symbol)
            out["ok"] = out["ok"] and bool(out["positioning"].get("ok"))
        if "fear_greed" in wanted:
            out["fear_greed"] = await asyncio.to_thread(self.fear_greed)
        if "news" in wanted:
            out["news"] = await asyncio.to_thread(self.news, news_limit, feed_url)
        return out

    def stats(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "failures": self.failures,
            "last_error": self.last_error,
            "cached": len(self._cache),
            "feeds": list(self.news_feeds),
        }


#: One process-wide instance: the caches are the point of having it.
_SHARED: Optional[MarketContext] = None


def shared_context() -> MarketContext:
    global _SHARED
    if _SHARED is None:
        _SHARED = MarketContext()
    return _SHARED
