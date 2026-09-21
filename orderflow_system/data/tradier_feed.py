"""
Tradier market data — real-time OPRA options chains for US equities.

Pure REST, no new dependency (``urllib``). Tradier's free brokerage account gives
access to the options chain API; the app stores the account's API key + secret in
the profile config and passes them here.

Design rules (all deliberate):

* **No new dependency.** REST is ``urllib``; auth is Basic (key:secret base64).
* **Budget first.** Tradier's free tier allows 240 calls/day (sandbox: unlimited for
  testing). The client keeps a conservative window and backs off on 429/403.
* **Chain-first.** This feed's job is the options chain: strikes, bids, asks, last,
  OI, volume, IV. That's what the gex + options panels consume.
* **Symbols mapped from the streaming source.** When Tradier is the options source,
  the app passes equity symbols (SPY, AAPL, …) and this feed resolves the chain.
* **Testable offline.** The transport is injected, so tests cover auth fail, 429,
  malformed responses, and empty chains without touching the network.

Reference: Tradier Developer API v1 — /v1/markets/options/chains
"""

from __future__ import annotations

import base64
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

BASE = "https://api.tradier.com"
SANDBOX_BASE = "https://sandbox.tradier.com"

#: Conservative daily budget below Tradier's free-tier 240/day.
REST_PER_DAY = 200

#: How long the client waits before retrying a 429/403.
BACKOFF_S = 5.0

#: Default options chain width: 6 strikes around the theoretical forward per expiry.
DEFAULT_CHAIN_WIDTH = 6


# ── errors ────────────────────────────────────────────────────────────────────────

class TradierError(RuntimeError):
    """A Tradier API failure with a user-facing message."""

    def __init__(self, status: int, message: str, *, fatal: bool = False) -> None:
        self.status = int(status or 0)
        self.fatal = fatal
        self.detail = message
        super().__init__(f"[{self.status}] {message}")


def _map_status(status: int, body: str = "") -> TradierError:
    """HTTP status → typed error. 401/403 are fatal (wrong keys/plan)."""
    msg: str
    if status == 401:
        msg = "Tradier rejected the API credentials — check the key and secret."
        fatal = True
    elif status == 403:
        msg = "This Tradier account is not entitled to options chain data — upgrade the plan."
        fatal = True
    elif status == 429:
        msg = "Tradier rate limit hit — backing off."
        fatal = False
    elif status == 0:
        msg = f"Tradier connection failed: {body}"
        fatal = True
    else:
        msg = f"Tradier returned status {status}."
        fatal = status >= 500
    return TradierError(status, msg, fatal=fatal)


# ── rate budget ───────────────────────────────────────────────────────────────────

@dataclass
class RateBudget:
    """Sliding-window call budget (same shape as alpaca_feed.RateBudget)."""

    per_day: int = REST_PER_DAY
    window_s: float = 86400.0          # 1 day
    _hits: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    blocked: int = 0
    _clock: Callable[[], float] = time.time

    def take(self) -> float:
        """Seconds to wait before the next call (0 = go). Counts the attempt."""
        now = self._clock()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window_s]
            if len(self._hits) >= self.per_day:
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
    """One option contract in a chain."""
    strike: float
    expiry: str                              # ISO date "YYYY-MM-DD"
    side: str                                # "call" | "put"
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    mark: Optional[float] = None
    iv: Optional[float] = None               # implied volatility (decimal)
    oi: Optional[float] = None               # open interest
    volume: Optional[float] = None
    symbol: Optional[str] = None             # Tradier option symbol
    root_symbol: Optional[str] = None        # underlying e.g. "SPY"


@dataclass
class OptionChain:
    """One expiry's worth of strikes."""
    symbol: str                              # underlying e.g. "SPY"
    expiry: str                              # "YYYY-MM-DD"
    forward: Optional[float] = None          # theoretical forward
    legs: list[OptionLeg] = field(default_factory=list)


@dataclass
class TradierOptions:
    """What the feed delivers for one underlying symbol."""
    symbol: str
    chains: list[OptionChain]               # one per expiry
    fetched_ms: int = 0
    error: Optional[str] = None


# ── client ────────────────────────────────────────────────────────────────────────

class TradierFeed:
    """REST client for Tradier's options chain API.

    Stores nothing sensitive permanently; the profile config holds the key/secret
    and passes them in. The feed is stateless between calls (no persistent socket).
    """

    def __init__(self, *, key_id: str = "", secret: str = "",
                 base: str = BASE, transport: Optional[Transport] = None,
                 budget: Optional[RateBudget] = None, timeout: float = 12.0,
                 chain_width: int = DEFAULT_CHAIN_WIDTH,
                 sandbox: bool = False,
                 clock: Callable[[], float] = time.time) -> None:
        self.key_id = (key_id or "").strip()
        self.secret = (secret or "").strip()
        self.base = SANDBOX_BASE if sandbox else (base or BASE)
        self.transport = transport or _default_transport
        self.budget = budget or RateBudget()
        self.timeout = timeout
        self.chain_width = chain_width
        self.last_error: Optional[str] = None
        self._last_chain: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ── auth ──────────────────────────────────────────────────────────────────────

    def _auth_header(self) -> dict[str, str]:
        if not self.key_id or not self.secret:
            return {}
        token = base64.b64encode(f"{self.key_id}:{self.secret}".encode()).decode()
        return {"Authorization": f"Basic {token}",
                "Accept": "application/json"}

    # ── chains ───────────────────────────────────────────────────────────────────

    def chains(self, symbol: str, *, expires: Optional[list[str]] = None) -> TradierOptions:
        """Fetch the options chain for one equity symbol.

        Parameters
        ----------
        symbol : underlying ticker, e.g. "SPY", "AAPL".
        expires : optional list of expiry dates to request (ISO "YYYY-MM-DD").
                 If None, the API returns all available expiries.
        """
        symbol = (symbol or "").strip().upper()
        if not symbol:
            return TradierOptions(symbol="", chains=[], error="empty symbol")

        wait = self.budget.take()
        if wait > 0:
            time.sleep(wait)

        headers = self._auth_header()
        params: dict[str, str] = {"symbol": symbol, "expiration": "", "strike": ""}
        if expires:
            params["expiration"] = ",".join(expires)

        status, _, body = self.transport("GET", f"{self.base}/v1/markets/options/chains",
                                          headers, params, self.timeout)

        if status != 200:
            err = _map_status(status, body)
            self.last_error = err.detail
            logger.warning("Tradier chains failed for %s: %s", symbol, err.detail)
            return TradierOptions(symbol=symbol, chains=[], error=err.detail)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.last_error = f"malformed Tradier response for {symbol}"
            logger.warning(self.last_error)
            return TradierOptions(symbol=symbol, chains=[], error=self.last_error)

        chains = self._parse_chains(symbol, data)
        with self._lock:
            self._last_chain = {"symbol": symbol, "chains": chains,
                                "fetched_ms": int(time.time() * 1000)}
        return TradierOptions(symbol=symbol, chains=chains)

    # ── parse ─────────────────────────────────────────────────────────────────────

    def _parse_chains(self, symbol: str, data: Any) -> list[OptionChain]:
        """Turn Tradier's chain response into OptionChain list."""
        chains: list[OptionChain] = []
        if not isinstance(data, dict):
            return chains
        root = data.get("options") or {}
        if not isinstance(root, dict):
            return chains

        for expiry_node in (root.get("expirations") or []):
            if not isinstance(expiry_node, dict):
                continue
            expiry = str(expiry_node.get("expiration_date") or "")
            if not expiry:
                continue

            strike_nodes = (expiry_node.get("strikes") or [])
            if not isinstance(strike_nodes, list):
                continue

            legs: list[OptionLeg] = []
            forward: Optional[float] = None

            for sk in strike_nodes:
                if not isinstance(sk, dict):
                    continue
                # Tradier puts call/put under "call" / "put" keys.
                call_node = sk.get("call")
                put_node = sk.get("put")

                strike_val = sk.get("strike")
                try:
                    strike = float(strike_val)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(strike):
                    continue

                # Forward from the first valid call.
                if forward is None and isinstance(call_node, dict):
                    fwd = call_node.get("theoretical_price")
                    try:
                        forward = float(fwd)
                    except (TypeError, ValueError):
                        pass

                if isinstance(call_node, dict):
                    legs.append(OptionLeg(
                        strike=strike,
                        expiry=expiry,
                        side="call",
                        bid=self._num(call_node.get("bid")),
                        ask=self._num(call_node.get("ask")),
                        last=self._num(call_node.get("last")),
                        mark=self._num(call_node.get("mark")),
                        iv=self._num(call_node.get("implied_volatility")),
                        oi=self._num(call_node.get("open_interest")),
                        volume=self._num(call_node.get("volume")),
                        symbol=str(call_node.get("option_symbol") or ""),
                        root_symbol=symbol,
                    ))
                if isinstance(put_node, dict):
                    legs.append(OptionLeg(
                        strike=strike,
                        expiry=expiry,
                        side="put",
                        bid=self._num(put_node.get("bid")),
                        ask=self._num(put_node.get("ask")),
                        last=self._num(put_node.get("last")),
                        mark=self._num(put_node.get("mark")),
                        iv=self._num(put_node.get("implied_volatility")),
                        oi=self._num(put_node.get("open_interest")),
                        volume=self._num(put_node.get("volume")),
                        symbol=str(put_node.get("option_symbol") or ""),
                        root_symbol=symbol,
                    ))

            if legs:
                chains.append(OptionChain(symbol=symbol, expiry=expiry,
                                           forward=forward, legs=legs))

        return chains

    @staticmethod
    def _num(v: Any) -> Optional[float]:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    # ── status ────────────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return {
            "source": "tradier",
            "key_configured": bool(self.key_id and self.secret),
            "used": self.budget.used,
            "limit": self.budget.per_day,
            "last_error": self.last_error,
            "last_chain": dict(self._last_chain),
        }
