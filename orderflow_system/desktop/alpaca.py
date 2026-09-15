"""Alpaca Markets integration — account linking, capability discovery, portfolio read.

Alpaca is a *brokerage as an API*: commission-free US stocks/ETFs, options and crypto,
self-clearing, with a free paper-trading environment that anyone can open with just an
email address. What it adds to this program is a different axis from Bybit and MT5:
real US equities and options instruments, a real broker account (positions, orders,
P&L, portfolio history), Benzinga news, and the market calendar.

What it does **not** add is depth. Alpaca publishes trades, quotes and bars — no order
book. The heatmap, the DOM ladder and the participants'-intent reader therefore cannot
run on Alpaca data, and this module says so in its capability report instead of
pretending otherwise.

Free ("Basic") plan, from Alpaca's own docs: real-time IEX only, SIP restricted to data
older than 15 minutes, 200 REST calls/min, 30 websocket symbols, options indicative feed,
news included with plan rate limits, history since 2016.

Nothing here is a dependency: the client is plain ``urllib``.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE = "https://api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"

# Alpaca's Basic plan allows 200 REST calls/minute. Stay well under it: the app polls
# panels, and a 429 from our own polling would look like an outage to the user.
MAX_CALLS_PER_MIN = 150

Transport = Callable[[str, str, dict[str, str], Optional[dict[str, str]], float], tuple[int, dict, str]]


def mask_key(key_id: str) -> str:
    """Never show a stored key back in full."""
    k = (key_id or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return k[:2] + "…"
    return f"{k[:4]}…{k[-2:]} ({len(k)} chars)"


class _RateLimiter:
    def __init__(self, per_minute: int = MAX_CALLS_PER_MIN) -> None:
        self.window = 60.0
        self.limit = per_minute
        self._hits: list[float] = []
        self._lock = threading.Lock()

    def take(self) -> float:
        """Return seconds to wait before the next call (0 when allowed)."""
        now = time.time()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window]
            if len(self._hits) >= self.limit:
                return max(0.0, self.window - (now - self._hits[0]))
            self._hits.append(now)
            return 0.0


_LIMITER = _RateLimiter()


def _default_transport(method: str, url: str, headers: dict[str, str],
                       params: Optional[dict[str, str]], timeout: float) -> tuple[int, dict, str]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode("utf-8", "replace")
    except Exception as exc:                      # DNS, TLS, timeout
        return 0, {}, f"{type(exc).__name__}: {exc}"


class AlpacaClient:
    """Thin, dependency-free client for the endpoints this app actually uses."""

    def __init__(self, key_id: str = "", secret: str = "", paper: bool = True,
                 transport: Optional[Transport] = None, timeout: float = 12.0) -> None:
        self.key_id = (key_id or "").strip()
        self.secret = (secret or "").strip()
        self.paper = bool(paper)
        self.transport = transport or _default_transport
        self.timeout = timeout
        self.base = PAPER_BASE if self.paper else LIVE_BASE

    # ── plumbing ─────────────────────────────────────────────────
    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret,
            "accept": "application/json",
        }

    def call(self, url: str, params: Optional[dict[str, str]] = None, auth: bool = True,
             method: str = "GET") -> tuple[int, dict, Any]:
        wait = _LIMITER.take()
        if wait > 0:
            time.sleep(min(wait, 5.0))
        status, headers, body = self.transport(method, url, self._headers() if auth else
                                               {"accept": "application/json"}, params, self.timeout)
        try:
            parsed: Any = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return status, headers, parsed

    # ── trading API (needs keys) ─────────────────────────────────
    def account(self) -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/account")
        return s, b

    def clock(self) -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/clock")
        return s, b

    def positions(self) -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/positions")
        return s, b

    def orders(self, status: str = "all", limit: int = 25) -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/orders", {"status": status, "limit": str(limit), "direction": "desc"})
        return s, b

    def portfolio_history(self, period: str = "1M", timeframe: str = "1D") -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/account/portfolio/history",
                             {"period": period, "timeframe": timeframe})
        return s, b

    def activities(self, activity_type: str = "FILL", limit: int = 50) -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/account/activities/{activity_type}",
                             {"page_size": str(limit)})
        return s, b

    def assets(self, asset_class: str = "us_equity", status: str = "active") -> tuple[int, Any]:
        s, _h, b = self.call(f"{self.base}/v2/assets", {"asset_class": asset_class, "status": status})
        return s, b

    # ── market data (keys needed except crypto history) ──────────
    def latest_trade(self, symbol: str = "AAPL", feed: str = "iex") -> tuple[int, Any]:
        s, _h, b = self.call(f"{DATA_BASE}/v2/stocks/{urllib.parse.quote(symbol)}/trades/latest",
                             {"feed": feed})
        return s, b

    def bars_aged(self, symbol: str = "AAPL", age_min: int = 20, feed: str = "sip",
                  span_min: int = 2) -> tuple[int, Any]:
        """Bars that end ``age_min`` minutes ago — the free plan's SIP window.

        The Basic plan may read full-market SIP data as long as it is older than 15
        minutes. Probing exactly that window distinguishes "no SIP at all" from
        "SIP with a 15-minute delay", which is the honest description of the free tier.
        """
        end = time.time() - age_min * 60
        start = end - span_min * 60
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        s, _h, b = self.call(f"{DATA_BASE}/v2/stocks/{urllib.parse.quote(symbol)}/bars",
                             {"timeframe": "1Min", "feed": feed,
                              "start": time.strftime(fmt, time.gmtime(start)),
                              "end": time.strftime(fmt, time.gmtime(end)), "limit": "5"})
        return s, b

    def news(self, limit: int = 2, symbols: str = "") -> tuple[int, Any]:
        params = {"limit": str(limit)}
        if symbols:
            params["symbols"] = symbols
        s, _h, b = self.call(f"{DATA_BASE}/v1beta1/news", params)
        return s, b

    def option_trades(self, limit: int = 1) -> tuple[int, Any]:
        s, _h, b = self.call(f"{DATA_BASE}/v1beta1/options/trades", {"limit": str(limit)})
        return s, b

    def crypto_bars(self, symbol: str = "BTC/USD", limit: int = 2) -> tuple[int, Any]:
        """Historical crypto data is the one market-data family that needs no key."""
        s, _h, b = self.call(f"{DATA_BASE}/v1beta3/crypto/us/bars",
                             {"symbols": symbol, "timeframe": "1Min", "limit": str(limit)}, auth=False)
        return s, b


# ──────────────────────────────────────────────────────────────
# The staged probe the UI shows
# ──────────────────────────────────────────────────────────────

def _note(ok: bool, yes: str, no: str) -> str:
    return yes if ok else no


def probe(payload: dict[str, Any], transport: Optional[Transport] = None) -> dict[str, Any]:
    """Validate Alpaca credentials and report what the account can actually reach.

    Stages, in order, so a failure names the missing piece:
      ``keys``  → nothing typed yet
      ``auth``  → Alpaca rejected the pair (the classic cause is a paper key against the
                  live host, or the reverse)
      ``api``   → reachable but something else went wrong (network, 500, 429)
      ``ready`` → account read; capability report attached
    """
    key_id = str(payload.get("key_id") or "").strip()
    secret = str(payload.get("secret") or "").strip()
    paper = bool(payload.get("paper", True))
    out: dict[str, Any] = {
        "ok": False, "stage": "keys", "message": "", "paper": paper,
        "account": None, "capabilities": {}, "limits": {"rest_per_min": 200, "websocket_symbols": 30},
        "key_masked": "", "checked_ms": int(time.time() * 1000), "entitlement_notes": [],
    }
    if not key_id or not secret:
        out["message"] = ("Paste the API key id and secret from your Alpaca dashboard. "
                          "A paper-trading account takes only an email address and needs no funding.")
        out["help"] = "https://app.alpaca.markets/paper/dashboard/overview"
        return out

    out["key_masked"] = mask_key(key_id)
    client = AlpacaClient(key_id, secret, paper, transport=transport)

    status, body = client.account()
    if status == 401 or (isinstance(body, dict) and str(body.get("message", "")).lower().startswith("unauthorized")):
        other = "live" if paper else "paper"
        out["stage"] = "auth"
        out["message"] = (f"Alpaca rejected these keys for the {'paper' if paper else 'live'} account. "
                          f"Keys are per environment — this looks like a {'live' if paper else 'paper'}-account "
                          f"pair. Switch the toggle to {other}, or generate keys in the right dashboard.")
        return out
    if status != 200 or not isinstance(body, dict):
        out["stage"] = "api"
        out["message"] = f"Alpaca answered HTTP {status}: {str(body)[:200]}"
        return out

    acct = body
    out["stage"] = "ready"
    out["ok"] = True
    out["account"] = {
        "status": acct.get("status"),
        "currency": acct.get("currency"),
        "account_number_masked": mask_key(str(acct.get("account_number") or "")),
        "cash": _f(acct.get("cash")),
        "equity": _f(acct.get("equity")),
        "buying_power": _f(acct.get("buying_power")),
        "portfolio_value": _f(acct.get("portfolio_value")),
        "pattern_day_trader": bool(acct.get("pattern_day_trader")),
        "daytrade_count": acct.get("daytrade_count"),
        "trading_blocked": bool(acct.get("trading_blocked")),
        "shorting_enabled": bool(acct.get("shorting_enabled")),
        "options_approved_level": acct.get("options_approved_level"),
        "created_at": acct.get("created_at"),
        "environment": "paper" if paper else "live",
    }

    caps: dict[str, Any] = {}
    notes: list[str] = []

    st, clk = client.clock()
    caps["market_clock"] = st == 200 and isinstance(clk, dict)
    if caps["market_clock"]:
        out["clock"] = {"is_open": clk.get("is_open"), "timestamp": clk.get("timestamp"),
                        "next_open": clk.get("next_open"), "next_close": clk.get("next_close")}
        notes.append("Market calendar reachable — the app can know when US equities are open.")

    st, a = client.assets()
    if st == 200 and isinstance(a, list):
        tradable = [x for x in a if x.get("tradable")]
        frac = [x for x in a if x.get("fractionable")]
        caps["equities_assets"] = len(a)
        caps["equities_fractionable"] = len(frac)
        out["asset_sample"] = {"total": len(a), "tradable": len(tradable), "fractionable": len(frac),
                              "first": [x.get("symbol") for x in a[:8]]}
        notes.append(f"{len(tradable)} tradable US equities/ETFs ({len(frac)} fractionable).")
    else:
        caps["equities_assets"] = 0

    st, t = client.latest_trade("AAPL", feed="iex")
    caps["equities_realtime_iex"] = st == 200 and isinstance(t, dict) and bool(t.get("trade"))
    notes.append(_note(caps["equities_realtime_iex"],
                       "Real-time IEX trades available (this is the free plan's real-time feed).",
                       "Real-time IEX trades not available on this account."))

    st, _b = client.bars_aged("AAPL", age_min=20, feed="sip")
    caps["equities_sip_delayed"] = st == 200
    notes.append(_note(caps["equities_sip_delayed"],
                       "Full-market SIP history reachable for data older than 15 minutes (free-plan window).",
                       "SIP history not reachable — expect IEX only."))

    st, n = client.news(limit=2)
    caps["news"] = st == 200 and isinstance(n, dict)
    if caps["news"]:
        items = n.get("news") or []
        out["news_sample"] = [{"headline": (i.get("headline") or "")[:120],
                               "symbols": i.get("symbols"), "source": i.get("source")} for i in items[:2]]
    notes.append(_note(caps["news"], "Benzinga news feed available.", "News feed not available on this plan."))

    st, _o = client.option_trades(limit=1)
    caps["options_data"] = st == 200
    notes.append(_note(caps["options_data"],
                       "Options data reachable (indicative feed on the free plan).",
                       "Options data not reachable on this plan."))

    st, tb = client.positions()
    caps["positions"] = st == 200 and isinstance(tb, list)
    if caps["positions"]:
        out["position_count"] = len(tb)
    st, ob = client.orders(limit=5)
    caps["orders"] = st == 200 and isinstance(ob, list)
    if caps["orders"]:
        out["open_order_count"] = len([x for x in ob if x.get("status") in ("new", "accepted", "partially_filled", "pending_new")])
    st, ph = client.portfolio_history(period="1M", timeframe="1D")
    caps["portfolio_history"] = st == 200 and isinstance(ph, dict)
    if caps["portfolio_history"]:
        eq = ph.get("equity")
        if isinstance(eq, list):
            out["portfolio"] = {"points": len(eq),
                                "last_equity": eq[-1] if eq else None,
                                "period": ph.get("timeframe")}
        else:
            caps["portfolio_history"] = False      # a dict without an equity series is not usable

    st, cb = client.crypto_bars("BTC/USD", 2)
    caps["crypto_history_keyless"] = st == 200

    out["capabilities"] = caps
    out["entitlement_notes"] = notes
    out["depth_available"] = False
    notes.append("No order book: Alpaca publishes trades, quotes and bars only — the heatmap, "
                 "DOM ladder and participants'-intent reader cannot run on Alpaca data.")
    out["message"] = (f"Connected to the {out['account']['environment']} account "
                      f"({out['account']['status']}). Capabilities checked.")
    return out


def _f(value: Any) -> Optional[float]:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None
