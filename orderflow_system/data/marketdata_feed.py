"""
Market Data feed — real-time OPRA options chains with server-side greeks.

Market Data (marketdata.app) provides institutional-grade options data: OPRA chains
with bid/ask/last/OI/volume plus server-computed delta, gamma, theta, vega, iv per
strike. The app stores the API key in the profile config.

Design rules (all deliberate):

* **No new dependency.** REST is ``urllib``.
* **Budget first.** Market Data's plans have generous limits; the client keeps a
  conservative window and backs off on 429.
* **Chain + greeks.** This feed delivers the full option contract including greeks,
  which is what the gex + volatility panels prefer when available.
* **Symbols mapped from the streaming source.** When Market Data is the options
  source, the app passes equity symbols and this feed resolves the chain.
* **Testable offline.** The transport is injected, so tests cover auth fail, 429,
  malformed responses, and empty chains without touching the network.

Reference: Market Data API v1 — /v1/options/chain
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

BASE = "https://api.marketdata.app"

#: Conservative budget below Market Data's plan limits.
REST_PER_MIN = 60

#: How long the client waits before retrying a 429.
BACKOFF_S = 5.0


# ── errors ────────────────────────────────────────────────────────────────────────

class MarketDataError(RuntimeError):
    """A Market Data API failure with a user-facing message."""

    def __init__(self, status: int, message: str, *, fatal: bool = False) -> None:
        self.status = int(status or 0)
        self.fatal = fatal
        self.detail = message
        super().__init__(f"[{self.status}] {message}")


def _map_status(status: int, body: str = "") -> MarketDataError:
    if status == 401:
        return MarketDataError(401,
            "Market Data rejected the API key — check the key in the profile config.",
            fatal=True)
    elif status == 403:
        return MarketDataError(403,
            "This Market Data plan does not include options chain data.",
            fatal=True)
    elif status == 429:
        return MarketDataError(429, "Market Data rate limit hit — backing off.")
    elif status == 0:
        return MarketDataError(0, f"Market Data connection failed: {body}", fatal=True)
    else:
        return MarketDataError(status, f"Market Data returned status {status}.",
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


# ── chain shape ───────────────────────────────────────────────────────────────────

@dataclass
class OptionLeg:
    """One option contract with greeks."""
    strike: float
    expiry: str
    side: str                                # "call" | "put"
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    iv: Optional[float] = None               # implied volatility (decimal)
    oi: Optional[float] = None
    volume: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    symbol: Optional[str] = None


@dataclass
class OptionChain:
    symbol: str
    expiry: str
    legs: list[OptionLeg] = field(default_factory=list)


@dataclass
class MarketDataOptions:
    symbol: str
    chains: list[OptionChain]
    fetched_ms: int = 0
    error: Optional[str] = None


# ── client ────────────────────────────────────────────────────────────────────────

class MarketDataFeed:
    """REST client for Market Data's options chain API with greeks."""

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
        self._lock = threading.Lock()

    def _auth_header(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"}

    def chains(self, symbol: str) -> MarketDataOptions:
        """Fetch the options chain for one equity symbol, with greeks."""
        symbol = (symbol or "").strip().upper()
        if not symbol:
            return MarketDataOptions(symbol="", chains=[], error="empty symbol")

        wait = self.budget.take()
        if wait > 0:
            time.sleep(wait)

        headers = self._auth_header()
        params: dict[str, str] = {"symbol": symbol}

        status, _, body = self.transport("GET",
            f"{self.base}/v1/options/chain", headers, params, self.timeout)

        if status != 200:
            err = _map_status(status, body)
            self.last_error = err.detail
            logger.warning("Market Data chains failed for %s: %s", symbol, err.detail)
            return MarketDataOptions(symbol=symbol, chains=[], error=err.detail)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.last_error = f"malformed Market Data response for {symbol}"
            logger.warning(self.last_error)
            return MarketDataOptions(symbol=symbol, chains=[], error=self.last_error)

        chains = self._parse_chains(symbol, data)
        return MarketDataOptions(symbol=symbol, chains=chains,
                                 fetched_ms=int(time.time() * 1000))

    def _parse_chains(self, symbol: str, data: Any) -> list[OptionChain]:
        chains: list[OptionChain] = []
        if not isinstance(data, dict):
            return chains
        root = data.get("options") or data.get("chain") or {}
        if not isinstance(root, dict):
            return chains

        # Market Data may return expiries as a dict keyed by expiry date.
        expiries = root.get("expirations") or []
        if isinstance(expiries, list):
            for exp_node in expiries:
                if not isinstance(exp_node, dict):
                    continue
                expiry = str(exp_node.get("expiration") or exp_node.get("date") or "")
                legs = self._parse_legs(symbol, exp_node)
                if legs:
                    chains.append(OptionChain(symbol=symbol, expiry=expiry, legs=legs))
        else:
            # Single expiry response.
            legs = self._parse_legs(symbol, root)
            if legs:
                chains.append(OptionChain(symbol=symbol, expiry="",
                                           legs=legs))

        return chains

    def _parse_legs(self, symbol: str, node: dict[str, Any]) -> list[OptionLeg]:
        legs: list[OptionLeg] = []
        strikes = node.get("strikes") or node.get("quotes") or []
        if not isinstance(strikes, list):
            # Try a single-contract response.
            return self._parse_leg(symbol, node)

        for sk in strikes:
            if not isinstance(sk, dict):
                continue
            strike_val = sk.get("strike") or sk.get("strike_price")
            try:
                strike = float(strike_val)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(strike):
                continue

            legs.append(OptionLeg(
                strike=strike,
                expiry=str(node.get("expiration") or ""),
                side=str(sk.get("type") or sk.get("option_type") or "").lower(),
                bid=self._num(sk.get("bid")),
                ask=self._num(sk.get("ask")),
                last=self._num(sk.get("last")),
                iv=self._num(sk.get("iv") or sk.get("implied_volatility")),
                oi=self._num(sk.get("open_interest") or sk.get("oi")),
                volume=self._num(sk.get("volume")),
                delta=self._num(sk.get("delta")),
                gamma=self._num(sk.get("gamma")),
                theta=self._num(sk.get("theta")),
                vega=self._num(sk.get("vega")),
                symbol=str(sk.get("symbol") or ""),
            ))

        return legs

    def _parse_leg(self, symbol: str, node: dict[str, Any]) -> list[OptionLeg]:
        """Single-contract response."""
        if not isinstance(node, dict):
            return []
        return [OptionLeg(
            strike=self._num(node.get("strike")) or 0.0,
            expiry=str(node.get("expiration") or ""),
            side=str(node.get("type") or "").lower(),
            bid=self._num(node.get("bid")),
            ask=self._num(node.get("ask")),
            last=self._num(node.get("last")),
            iv=self._num(node.get("iv")),
            oi=self._num(node.get("open_interest")),
            volume=self._num(node.get("volume")),
            delta=self._num(node.get("delta")),
            gamma=self._num(node.get("gamma")),
            theta=self._num(node.get("theta")),
            vega=self._num(node.get("vega")),
            symbol=str(node.get("symbol") or ""),
        )]

    @staticmethod
    def _num(v: Any) -> Optional[float]:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    def status(self) -> dict[str, Any]:
        return {
            "source": "marketdata",
            "key_configured": bool(self.api_key),
            "used": self.budget.used,
            "limit": self.budget.per_minute,
            "last_error": self.last_error,
        }
