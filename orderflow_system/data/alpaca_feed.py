"""Alpaca market data — one REST client, one stream per asset class, one subscription set.

Why this file exists next to ``desktop/alpaca.py``: that module *links* the account
(keys, capability probe, portfolio read). This one *feeds the analyzers*: it turns
Alpaca's REST history and websocket streams into the same ``on_tick`` call the Bybit
and MT5 feeds use, so every existing panel (tape, footprint, delta, CVD, VWAP,
profile, scanner) works unchanged.

Design rules, all of them deliberate:

* **No new dependency.** REST is ``urllib``; the websocket is the ``websockets``
  package the repo already ships for Bybit.
* **Budget first.** Alpaca's Basic plan allows 200 REST calls/minute. The client
  keeps its own 150/min window and backs off on 429, because the app also polls
  panels — a self-inflicted 429 would look like an outage.
* **One socket per asset class.** Stocks (``/v2/{iex|sip|delayed_sip}``) and crypto
  (``/v1beta3/crypto/us``) are separate hosts; each connects once, authenticates
  within 10 s, and re-authenticates immediately after any reconnect.
* **No order book, ever.** Depth views cannot run on this data; the capability
  payload says so rather than showing an empty canvas.
* **Testable offline.** The REST transport and the socket factory are injected, so
  the tests drive every path (budget, closed market, error frames, reconnect)
  without touching the network.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from orderflow_system.data.alpaca_normalize import (
    normalize_crypto_trade,
    normalize_quote,
    normalize_snapshot_quote,
    normalize_snapshot_trade,
    normalize_stock_trade,
)

logger = logging.getLogger(__name__)

DATA_BASE = "https://data.alpaca.markets"
TRADING_BASE = "https://api.alpaca.markets"
PAPER_BASE = "https://paper-api.alpaca.markets"

#: Stream hosts per feed. ``test`` is Alpaca's public sandbox stream (FAKEPACA).
STREAM_HOSTS = {
    "iex": "wss://stream.data.alpaca.markets/v2/iex",
    "sip": "wss://stream.data.alpaca.markets/v2/sip",
    "delayed_sip": "wss://stream.data.alpaca.markets/v2/delayed_sip",
    "test": "wss://stream.data.alpaca.markets/v2/test",
}
CRYPTO_STREAM_HOSTS = {
    "us": "wss://stream.data.alpaca.markets/v1beta3/crypto/us",
    "us-1": "wss://stream.data.alpaca.markets/v1beta3/crypto/us-1",
    "eu-1": "wss://stream.data.alpaca.markets/v1beta3/crypto/eu-1",
}
TEST_STREAM_SYMBOL = "FAKEPACA"

#: Client-side budget, below the Basic plan's 200/min (see the module docstring).
REST_PER_MIN = 150
AUTH_DEADLINE_S = 10.0

Transport = Callable[[str, str, dict[str, str], Optional[dict[str, str]], float],
                     "tuple[int, dict[str, str], str]"]
ConnectFactory = Callable[[str], Any]          # url -> an awaitable/async-context socket


# ──────────────────────────────────────────────────────────────
# Errors — Alpaca's codes, mapped to something a user can act on
# ──────────────────────────────────────────────────────────────

#: Documented stream error codes. Every entry names the cause *and* the next step.
STREAM_ERRORS: dict[int, str] = {
    400: "Alpaca rejected the message as malformed — usually an unknown symbol or channel name.",
    401: "Not authenticated: the key id / secret pair was rejected (paper keys only work on paper).",
    402: "Authentication failed for this key — re-check the secret in the Alpaca view.",
    403: "This account is not entitled to that feed — SIP and OPRA data need a paid plan.",
    404: "Alpaca does not publish that symbol on this feed (check the ticker, e.g. BTC/USD).",
    405: "Too many symbols subscribed — the plan's stream limit was reached.",
    406: "Subscription refused: this plan does not include that channel.",
    407: "The client fell behind and Alpaca dropped the connection — it will reconnect automatically.",
    409: "Connection limit reached: Alpaca allows one stream connection per key at a time.",
    413: "A message exceeded Alpaca's size limit.",
    500: "Alpaca reported an internal error — it will reconnect automatically.",
}


class AlpacaError(RuntimeError):
    """A stream/REST failure with Alpaca's code and a user-facing message."""

    def __init__(self, code: int, message: str, *, fatal: bool = False, detail: str = "") -> None:
        self.code = int(code or 0)
        self.fatal = fatal
        self.detail = detail or message
        super().__init__(f"[{self.code}] {message}")


def map_stream_error(code: int, detail: str = "") -> AlpacaError:
    """Alpaca error frame → typed exception. Unknown codes stay honest about it."""
    message = STREAM_ERRORS.get(int(code or 0))
    if message is None:
        message = f"Alpaca reported an unexpected error code {code}."
    # 401/402/403 mean the credentials/plan are wrong: reconnecting cannot fix them.
    fatal = int(code or 0) in (401, 402, 403)
    return AlpacaError(code, message, fatal=fatal, detail=detail)


# ──────────────────────────────────────────────────────────────
# Shared plumbing
# ──────────────────────────────────────────────────────────────

class RateBudget:
    """Sliding-window call budget (same shape as the one in ``desktop/alpaca.py``)."""

    def __init__(self, per_minute: int = REST_PER_MIN, clock: Callable[[], float] = time.time) -> None:
        self.limit = int(per_minute)
        self.window = 60.0
        self._clock = clock
        self._hits: list[float] = []
        self._lock = threading.Lock()
        self.blocked = 0

    def take(self) -> float:
        """Seconds to wait before the next call (0 = go). Counts the attempt."""
        now = self._clock()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window]
            if len(self._hits) >= self.limit:
                self.blocked += 1
                return max(0.0, self.window - (now - self._hits[0]))
            self._hits.append(now)
            return 0.0

    @property
    def used(self) -> int:
        now = self._clock()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window]
            return len(self._hits)

    def snapshot(self) -> dict[str, Any]:
        return {"used": self.used, "limit": self.limit, "window_s": self.window, "blocked": self.blocked}


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
    except Exception as exc:                                   # DNS, TLS, timeout
        return 0, {}, f"{type(exc).__name__}: {exc}"


class AlpacaData:
    """REST side: clock, assets, bars, trades, snapshots — budgeted and cacheable."""

    def __init__(self, key_id: str = "", secret: str = "", feed: str = "iex",
                 transport: Optional[Transport] = None, budget: Optional[RateBudget] = None,
                 timeout: float = 12.0, cache_dir: Optional[str] = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.key_id = (key_id or "").strip()
        self.secret = (secret or "").strip()
        self.feed = (feed or "iex").strip().lower()
        self.transport = transport or _default_transport
        self.budget = budget or RateBudget(clock=clock)
        self.timeout = timeout
        self.cache_dir = cache_dir
        self._clock = clock
        self.last_error: Optional[str] = None

    # ── plumbing ─────────────────────────────────────────────
    def _headers(self, auth: bool) -> dict[str, str]:
        if auth and self.key_id:
            return {"APCA-API-KEY-ID": self.key_id, "APCA-API-SECRET-KEY": self.secret,
                    "accept": "application/json"}
        return {"accept": "application/json"}

    def call(self, url: str, params: Optional[dict[str, str]] = None, auth: bool = True,
             retries: int = 1) -> tuple[int, Any]:
        """One GET, inside the budget, with 429 backoff (honouring Retry-After)."""
        attempt = 0
        while True:
            wait = self.budget.take()
            if wait > 0:
                time.sleep(min(wait, 5.0))
            status, headers, body = self.transport("GET", url, self._headers(auth), params, self.timeout)
            if status == 429 and attempt < retries:
                attempt += 1
                retry_after = 1.0
                try:
                    retry_after = min(float((headers or {}).get("Retry-After", 1.0)), 10.0)
                except (TypeError, ValueError):
                    pass
                time.sleep(max(retry_after, 0.5))
                continue
            if status == 0:
                self.last_error = str(body)[:200]
            try:
                parsed: Any = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = body
            return status, parsed

    # ── trading API (needs keys) ─────────────────────────────
    def clock(self, paper: bool = True) -> Optional[dict[str, Any]]:
        """Market clock — soft-fails to None (a clock hiccup must not stop the feed)."""
        base = PAPER_BASE if paper else TRADING_BASE
        status, body = self.call(f"{base}/v2/clock")
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"clock HTTP {status}"
            return None
        return body

    def is_open(self, paper: bool = True) -> Optional[bool]:
        clk = self.clock(paper=paper)
        if clk is None:
            return None
        return bool(clk.get("is_open"))

    def assets(self, force: bool = False, cache_hours: float = 24.0) -> list[dict[str, Any]]:
        """Tradable assets, cached on disk for a day (Alpaca changes this rarely)."""
        cached = None if force else self._read_cache("assets.json", cache_hours)
        if isinstance(cached, list):
            return cached
        status, body = self.call(f"{TRADING_BASE}/v2/assets", {"asset_class": "us_equity", "status": "active"})
        if status != 200 or not isinstance(body, list):
            self.last_error = f"assets HTTP {status}"
            return cached if isinstance(cached, list) else []
        self._write_cache("assets.json", body)
        return body

    # ── market data ──────────────────────────────────────────
    def bars(self, symbol: str, timeframe: str = "1Min", limit: int = 500,
             start: Optional[str] = None, end: Optional[str] = None) -> list[dict[str, Any]]:
        params = {"timeframe": timeframe, "limit": str(min(limit, 10_000)), "feed": self.feed}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        status, body = self.call(f"{DATA_BASE}/v2/stocks/{urllib.parse.quote(symbol)}/bars", params)
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"bars HTTP {status}"
            return []
        return [b for b in (body.get("bars") or []) if isinstance(b, dict)]

    def trades(self, symbol: str, limit: int = 1000) -> list[dict[str, Any]]:
        status, body = self.call(f"{DATA_BASE}/v2/stocks/{urllib.parse.quote(symbol)}/trades",
                                 {"limit": str(min(limit, 10_000)), "feed": self.feed})
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"trades HTTP {status}"
            return []
        return [t for t in (body.get("trades") or []) if isinstance(t, dict)]

    def snapshot(self, symbol: str) -> Optional[dict[str, Any]]:
        status, body = self.call(f"{DATA_BASE}/v2/stocks/{urllib.parse.quote(symbol)}/snapshot",
                                 {"feed": self.feed})
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"snapshot HTTP {status}"
            return None
        return body

    def snapshots(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Batched snapshots — one call for every symbol (Alpaca accepts up to 1000)."""
        wanted = [s for s in symbols if s][:1000]
        if not wanted:
            return {}
        status, body = self.call(f"{DATA_BASE}/v2/stocks/snapshots",
                                 {"symbols": ",".join(wanted), "feed": self.feed})
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"snapshots HTTP {status}"
            return {}
        return {k: v for k, v in body.items() if isinstance(v, dict)}

    def crypto_snapshot(self, symbol: str = "BTC/USD", loc: str = "us") -> Optional[dict[str, Any]]:
        """Latest crypto quote + trade for one pair — public, no key required.

        The one Alpaca endpoint that answers without an account, which is what lets the
        cross-venue top of book work out of the box for crypto (Bybit depth + this quote).
        """
        status, body = self.call(f"{DATA_BASE}/v1beta3/crypto/{loc}/snapshots",
                                 {"symbols": symbol}, auth=bool(self.key_id))
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"crypto snapshot HTTP {status}"
            return None
        snaps = body.get("snapshots") or {}
        if not isinstance(snaps, dict):
            return None
        payload = snaps.get(symbol)
        return payload if isinstance(payload, dict) else None

    def crypto_bars(self, symbol: str = "BTC/USD", timeframe: str = "1Min",
                    limit: int = 500, loc: str = "us", start: Optional[str] = None,
                    end: Optional[str] = None) -> list[dict[str, Any]]:
        """Crypto history needs no key at all — the one family that works unlinked."""
        params = {"symbols": symbol, "timeframe": timeframe, "limit": str(min(limit, 10_000))}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        status, body = self.call(f"{DATA_BASE}/v1beta3/crypto/{loc}/bars", params, auth=bool(self.key_id))
        if status != 200 or not isinstance(body, dict):
            self.last_error = f"crypto bars HTTP {status}"
            return []
        rows = body.get("bars") or {}
        if isinstance(rows, dict):
            rows = rows.get(symbol) or next(iter(rows.values()), [])
        return [b for b in (rows or []) if isinstance(b, dict)]

    # ── tiny disk cache ──────────────────────────────────────
    def _cache_path(self, name: str):
        if not self.cache_dir:
            return None
        from pathlib import Path
        return Path(self.cache_dir) / name

    def _read_cache(self, name: str, max_age_hours: float) -> Any:
        path = self._cache_path(name)
        if not path or not path.is_file():
            return None
        try:
            if (time.time() - path.stat().st_mtime) > max_age_hours * 3600:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write_cache(self, name: str, payload: Any) -> None:
        path = self._cache_path(name)
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            logger.debug("alpaca cache write failed for %s", name, exc_info=True)


# ──────────────────────────────────────────────────────────────
# Subscription manager (caps, idempotency, visible trimming)
# ──────────────────────────────────────────────────────────────

@dataclass
class SubscriptionSet:
    """What is currently asked of one stream, with the plan's caps in mind."""

    stock_cap: int = 30
    option_cap: int = 200
    trades: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)
    bars: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    on_warn: Optional[Callable[[str], None]] = None

    # ── helpers ──
    def _channel(self, channel: str) -> Optional[list[str]]:
        """The list for a channel, or None when the channel name is unknown (a typo
        must fail loudly — silently adding to a throwaway list loses subscriptions)."""
        return {"trades": self.trades, "quotes": self.quotes, "bars": self.bars}.get(channel)

    def _cap(self, channel: str, symbol: str = "") -> int:
        if channel == "quotes" and "/" in symbol:          # option quotes have their own cap
            return self.option_cap
        return self.stock_cap

    def _warn(self, text: str) -> None:
        self.warnings.append(text)
        if len(self.warnings) > 20:
            self.warnings.pop(0)
        logger.warning("alpaca subscriptions: %s", text)
        if self.on_warn:
            try:
                self.on_warn(text)
            except Exception:                              # a bad callback must not break the feed
                logger.debug("subscription warning callback failed", exc_info=True)

    # ── API ──
    def add(self, channel: str, symbols: Iterable[str]) -> list[str]:
        """Add symbols to a channel. Returns what was actually added (idempotent)."""
        target = self._channel(channel)
        if target is None:
            raise ValueError(f"unknown channel {channel!r}")
        added: list[str] = []
        for raw in symbols:
            symbol = str(raw or "").strip()
            if not symbol or symbol in target:
                continue
            cap = self._cap(channel, symbol)
            if len(target) >= cap:
                evicted = target.pop(0)
                self._warn(f"{channel}: {symbol} pushed out {evicted} (the plan allows {cap} symbols)")
            target.append(symbol)
            added.append(symbol)
        return added

    def remove(self, channel: str, symbols: Iterable[str]) -> list[str]:
        target = self._channel(channel)
        if target is None:
            raise ValueError(f"unknown channel {channel!r}")
        removed = []
        for raw in symbols:
            symbol = str(raw or "").strip()
            if symbol in target:
                target.remove(symbol)
                removed.append(symbol)
        return removed

    def frame(self, channel: str) -> dict[str, list[str]]:
        return {channel: list(self._channel(channel))} if self._channel(channel) else {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "trades": list(self.trades), "quotes": list(self.quotes), "bars": list(self.bars),
            "stock_cap": self.stock_cap, "option_cap": self.option_cap,
            "count": len(set(self.trades) | set(self.quotes) | set(self.bars)),
            "warnings": list(self.warnings[-5:]),
        }


# ──────────────────────────────────────────────────────────────
# Stream client
# ──────────────────────────────────────────────────────────────

class AlpacaStream:
    """One websocket, authenticated once, with re-auth on every reconnect.

    ``connect_factory`` is injected: production passes ``websockets.connect``,
    tests pass a fake socket that feeds scripted frames.
    """

    def __init__(self, key_id: str = "", secret: str = "", url: Optional[str] = None,
                 feed: str = "iex", *, connect_factory: Optional[ConnectFactory] = None,
                 subscriptions: Optional[SubscriptionSet] = None,
                 on_tick: Optional[Callable[[str, Any], None]] = None,
                 on_quote: Optional[Callable[[str, Any], None]] = None,
                 on_status: Optional[Callable[[str], None]] = None,
                 auth_deadline_s: float = AUTH_DEADLINE_S,
                 label: str = "stocks", require_auth: bool = True) -> None:
        self.key_id = (key_id or "").strip()
        self.secret = (secret or "").strip()
        self.url = url or STREAM_HOSTS.get((feed or "iex").lower(), STREAM_HOSTS["iex"])
        self.feed = feed
        self.label = label
        self.connect_factory = connect_factory
        self.subscriptions = subscriptions or SubscriptionSet()
        self.on_tick = on_tick
        self.on_quote = on_quote
        self.on_status = on_status
        self.auth_deadline_s = auth_deadline_s
        self.require_auth = require_auth and bool(self.key_id)
        self.state = "idle"                 # idle | connecting | authenticating | live | reconnecting | error
        self.last_error: Optional[str] = None
        self.last_message_ms = 0
        self.reconnects = 0
        self.messages = 0
        self.authenticated = False
        self._stop = False
        self._task: Optional[asyncio.Task] = None
        self._socket = None

    # ── status ──
    def status(self) -> dict[str, Any]:
        return {
            "label": self.label, "state": self.state, "url": self.url, "feed": self.feed,
            "authenticated": self.authenticated, "reconnects": self.reconnects,
            "messages": self.messages, "last_message_age_s": (
                round(time.time() - self.last_message_ms / 1000.0, 1) if self.last_message_ms else None),
            "last_error": self.last_error,
            "subscriptions": self.subscriptions.as_dict(),
        }

    def _set_state(self, state: str) -> None:
        self.state = state
        if self.on_status:
            try:
                self.on_status(state)
            except Exception:
                logger.debug("stream status callback failed", exc_info=True)

    # ── frames ──
    def auth_frame(self) -> dict[str, str]:
        return {"action": "auth", "key": self.key_id, "secret": self.secret}

    def subscribe_frame(self) -> dict[str, Any]:
        frame: dict[str, Any] = {"action": "subscribe"}
        for channel in ("trades", "quotes", "bars"):
            if self.subscriptions._channel(channel):
                frame[channel] = list(self.subscriptions._channel(channel))
        return frame

    def unsubscribe_frame(self, channel: str, symbols: Iterable[str]) -> Optional[dict[str, Any]]:
        wanted = [s for s in symbols if s]
        if not wanted or channel not in ("trades", "quotes", "bars"):
            return None
        return {"action": "unsubscribe", channel: wanted}

    async def subscribe(self, channel: str, symbols: Iterable[str]) -> list[str]:
        added = self.subscriptions.add(channel, symbols)
        if added and self._socket is not None and self.authenticated:
            await self._send({"action": "subscribe", channel: added})
        return added

    async def unsubscribe(self, channel: str, symbols: Iterable[str]) -> list[str]:
        removed = self.subscriptions.remove(channel, symbols)
        frame = self.unsubscribe_frame(channel, removed)
        if frame and self._socket is not None and self.authenticated:
            await self._send(frame)
        return removed

    async def _send(self, frame: dict[str, Any]) -> None:
        payload = json.dumps(frame)
        sock = self._socket
        if sock is None:
            return
        send = getattr(sock, "send", None)
        if send is None:
            return
        result = send(payload)
        if asyncio.iscoroutine(result):
            await result

    # ── the loop ──
    async def _connect(self):
        factory = self.connect_factory
        if factory is None:
            import websockets
            factory = websockets.connect
        result = factory(self.url)
        if asyncio.iscoroutine(result):
            result = await result
        return await result if hasattr(result, "__aenter__") is False and asyncio.iscoroutine(result) else result

    async def run(self) -> None:
        """Connect → auth (within the deadline) → subscribe → read, reconnecting."""
        backoff = 1.0
        while not self._stop:
            try:
                self._set_state("connecting")
                self.authenticated = False
                sock = await self._enter()
                self._socket = sock
                if self.require_auth:
                    self._set_state("authenticating")
                    await self._send(self.auth_frame())
                else:
                    self.authenticated = True
                if self.subscriptions.trades or self.subscriptions.quotes or self.subscriptions.bars:
                    await self._send(self.subscribe_frame())
                backoff = 1.0
                async for raw in self._messages(sock):
                    self._handle_message(raw)
                if self._stop:
                    break
                raise AlpacaError(0, "the stream closed")
            except Exception as exc:                        # noqa: BLE001 — reconnect on anything
                err = exc if isinstance(exc, AlpacaError) else AlpacaError(0, f"{type(exc).__name__}: {exc}")
                self.last_error = str(err)
                if err.fatal:
                    self._set_state("error")
                    logger.error("alpaca %s stream: %s", self.label, err)
                    return
                self._set_state("reconnecting")
                self.reconnects += 1
                logger.warning("alpaca %s stream dropped (%s) — reconnecting in %.1fs",
                               self.label, err, backoff)
                await self._close_socket()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
        await self._close_socket()
        self._set_state("idle")

    async def _enter(self):
        """Open the socket, tolerating factories that return a context manager."""
        factory = self.connect_factory
        if factory is None:
            import websockets
            factory = websockets.connect
        try:
            sock = factory(self.url)
            if hasattr(sock, "__await__"):
                sock = await sock
            return sock
        except Exception:
            raise

    async def _messages(self, sock):
        if hasattr(sock, "__aiter__"):
            async for message in sock:
                yield message
            return
        recv = getattr(sock, "recv", None)
        while not self._stop and recv is not None:
            message = recv()
            if asyncio.iscoroutine(message):
                message = await message
            if message is None:
                break
            yield message

    async def _close_socket(self) -> None:
        sock, self._socket = self._socket, None
        if sock is None:
            return
        for name in ("close", "__aexit__"):
            closer = getattr(sock, name, None)
            if closer is None:
                continue
            try:
                result = closer() if name == "close" else closer(None, None, None)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.debug("alpaca socket close failed", exc_info=True)
            return

    def _handle_message(self, raw: Any) -> None:
        self.last_message_ms = int(time.time() * 1000)
        self.messages += 1
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", "replace")
        try:
            frames = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            logger.debug("alpaca stream sent a non-JSON frame: %.120s", raw)
            return
        if isinstance(frames, dict):
            frames = [frames]
        if not isinstance(frames, list):
            return
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            kind = frame.get("T")
            if kind == "success":
                msg = str(frame.get("msg") or "")
                if "authenticated" in msg or "connected" in msg:
                    self.authenticated = "authenticated" in msg or not self.require_auth
                    if self.authenticated:
                        self._set_state("live")
                continue
            if kind == "subscription":
                continue
            if kind == "error":
                err = map_stream_error(frame.get("code"), str(frame.get("msg") or ""))
                self.last_error = str(err)
                if err.fatal:
                    raise err
                logger.warning("alpaca %s stream error frame: %s", self.label, err)
                continue
            if kind == "t":
                symbol = str(frame.get("S") or "")
                tick = (normalize_crypto_trade(frame, mid=self._last_mid(symbol), symbol=symbol)
                        if "/" in symbol else normalize_stock_trade(frame, mid=self._last_mid(symbol), symbol=symbol))
                if tick is not None and self.on_tick:
                    self.on_tick(symbol, tick)
                continue
            if kind == "q":
                quote = normalize_quote(frame)
                if quote is not None:
                    self._mid_cache[quote.symbol or str(frame.get("S") or "")] = quote.mid
                    if self.on_quote:
                        self.on_quote(quote.symbol or str(frame.get("S") or ""), quote)

    # a tiny mid cache so trade classification has a reference price
    _mid_cache: dict[str, float] = {}

    def _last_mid(self, symbol: str) -> Optional[float]:
        return self._mid_cache.get(symbol)

    async def start(self) -> None:
        self._stop = False
        self._task = asyncio.ensure_future(self.run())

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):     # noqa: BLE001
                pass
            self._task = None
        await self._close_socket()
        self._set_state("idle")


# ──────────────────────────────────────────────────────────────
# The feed the engine starts
# ──────────────────────────────────────────────────────────────

class AlpacaFeed:
    """Alpaca as a data source for the existing analyzers.

    ``symbols`` maps the app's symbol to Alpaca's (``{"AAPL": "AAPL",
    "BTCUSDT": "BTC/USD"}``) — the same pattern ``MT5.symbols`` already uses.
    Only the mapped symbols are ever requested; the stream carries trades and
    quotes, and snapshots/bars top up the tape and the history.
    """

    def __init__(self, symbols: dict[str, str], on_tick: Callable[[str, Any], None], *,
                 key_id: str = "", secret: str = "", paper: bool = True, feed: str = "iex",
                 data: Optional[AlpacaData] = None,
                 connect_factory: Optional[ConnectFactory] = None,
                 snapshot_seconds: float = 5.0, history_minutes: int = 240,
                 stock_cap: int = 30, option_cap: int = 200,
                 on_warn: Optional[Callable[[str], None]] = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.symbols = {str(k): str(v) for k, v in (symbols or {}).items() if v}
        self.on_tick = on_tick
        self.paper = bool(paper)
        self.feed = feed
        self.data = data or AlpacaData(key_id, secret, feed=feed)
        self.connect_factory = connect_factory
        self.snapshot_seconds = max(1.0, float(snapshot_seconds))
        self.history_minutes = int(history_minutes)
        self.subscriptions = SubscriptionSet(stock_cap=stock_cap, option_cap=option_cap, on_warn=on_warn)
        self.streams: list[AlpacaStream] = []
        self.state = "idle"
        self.market_open: Optional[bool] = None
        #: (stamp, price, size, trade id) of the last trade each snapshot delivered — a REST
        #: snapshot repeats its `latestTrade` until a new print exists, and re-delivering it as a
        #: fresh tick counted phantom volume and delta into every aggregate panel.
        self._last_snapshot_print: dict[str, tuple] = {}
        self.last_clock: Optional[dict[str, Any]] = None   # cached for the palette
        self.needs_keys = False
        self.errors: list[str] = []
        self.started_ms = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: list[asyncio.Task] = []

    # ── helpers ──
    @property
    def equity_symbols(self) -> list[str]:
        return [a for a in self.symbols.values() if "/" not in a]

    @property
    def crypto_symbols(self) -> list[str]:
        return [a for a in self.symbols.values() if "/" in a]

    def _app_for(self, alpaca_symbol: str) -> Optional[str]:
        for app, alp in self.symbols.items():
            if alp == alpaca_symbol:
                return app
        return None

    async def start(self) -> None:
        """Start the streams + the polling task. Never blocks the caller."""
        self.state = "starting"
        self.started_ms = int(time.time() * 1000)
        self._loop = asyncio.get_running_loop()
        if not self.symbols:
            self.state = "no-symbols"
            return

        if self.equity_symbols:
            stock_stream = AlpacaStream(
                self.data.key_id, self.data.secret, url=STREAM_HOSTS.get(self.feed, STREAM_HOSTS["iex"]),
                feed=self.feed, connect_factory=self.connect_factory,
                subscriptions=self.subscriptions, on_tick=self._on_stream_tick, label="stocks")
            stock_stream.subscriptions.add("trades", self.equity_symbols)
            stock_stream.subscriptions.add("quotes", self.equity_symbols)
            self.streams.append(stock_stream)

        if self.crypto_symbols:
            crypto_stream = AlpacaStream(
                self.data.key_id, self.data.secret, url=CRYPTO_STREAM_HOSTS["us"], feed="crypto",
                connect_factory=self.connect_factory, on_tick=self._on_stream_tick, label="crypto")
            crypto_stream.subscriptions.add("trades", self.crypto_symbols)
            self.streams.append(crypto_stream)

        for stream in self.streams:
            await stream.start()
        self._tasks.append(asyncio.ensure_future(self._poll_loop()))
        self.state = "running"
        logger.info("Alpaca feed: %d symbol(s) mapped (%d equity, %d crypto), feed=%s",
                    len(self.symbols), len(self.equity_symbols), len(self.crypto_symbols), self.feed)

    async def stop(self) -> None:
        self.state = "stopping"
        for task in self._tasks:
            task.cancel()
        for stream in self.streams:
            await stream.stop()
        self._tasks.clear()
        self.state = "stopped"

    def _deliver(self, app_symbol: str, tick: Any) -> None:
        """Hand a tick to the system.

        ``OrderflowSystem._on_tick`` is a coroutine (both other feeds ``await`` it), so
        calling it from this synchronous callback and dropping the coroutine silently
        loses every tick — the first live smoke test showed "720 bars seeded" and zero
        ticks in the pipelines because of exactly that. Schedule it on the loop instead.
        """
        if not self.on_tick or not app_symbol or tick is None:
            return
        try:
            result = self.on_tick(app_symbol, tick)
        except Exception as exc:                            # noqa: BLE001
            self._error(f"tick delivery failed for {app_symbol}: {exc}")
            return
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = self._loop
            if loop is None or loop.is_closed():
                result.close()
                return
            try:
                asyncio.ensure_future(result, loop=loop)
            except RuntimeError as exc:
                result.close()
                self._error(f"tick scheduling failed for {app_symbol}: {exc}")

    def _on_stream_tick(self, alpaca_symbol: str, tick) -> None:
        app = self._app_for(alpaca_symbol)
        if app:
            self._deliver(app, tick)

    # ── REST top-up ──
    async def seed_history(self) -> int:
        """Bars for the configured history window, ingested as ticks.

        Called once at start and again when the session opens: an Alpaca symbol
        otherwise begins with an empty chart, which reads as "broken" rather than
        "new" (the same defect Phase 1 fixed for the exchange feed).

        The window is passed explicitly: Alpaca's bars endpoints page **forward** from
        ``start``, so a bare ``limit`` returns the *oldest* bars it has (the first live
        smoke seeded yesterday's tape instead of the last four hours).
        """
        from orderflow_system.data.alpaca_normalize import normalize_bar

        end_ts = time.time()
        start_ts = end_ts - max(1, self.history_minutes) * 60
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        start = time.strftime(fmt, time.gmtime(start_ts))
        end = time.strftime(fmt, time.gmtime(end_ts))
        total = 0
        for app_symbol, alpaca_symbol in self.symbols.items():
            try:
                if "/" in alpaca_symbol:
                    bars = await asyncio.to_thread(self.data.crypto_bars, alpaca_symbol, "1Min",
                                                   self.history_minutes, "us", start, end)
                else:
                    bars = await asyncio.to_thread(self.data.bars, alpaca_symbol, "1Min",
                                                   self.history_minutes, start, end)
            except Exception as exc:                        # noqa: BLE001
                self._error(f"history for {alpaca_symbol}: {exc}")
                continue
            for bar in bars:
                row = normalize_bar(bar, symbol=alpaca_symbol)
                if row:
                    total += 1
                    self._emit_bar(row, app_symbol)
        return total

    def _emit_bar(self, row: dict[str, Any], app_symbol: str) -> None:
        """A historical bar becomes three synthetic ticks (H, L, C) — enough for the
        tape-driven panels to have a shape, while the candle builder never sees a
        bar it did not build itself."""
        from orderflow_system.data.models import Side, Tick

        for price, size_hint in ((row["open"], 0.0), (row["high"], row["volume"] / 3 or 0.0),
                                 (row["low"], row["volume"] / 3 or 0.0), (row["close"], row["volume"] / 3 or 0.0)):
            if not price:
                continue
            tick = Tick(timestamp_ms=row["timestamp_ms"], price=price, size=size_hint, side=Side.BUY)
            self._deliver(app_symbol, tick)

    async def poll_once(self) -> dict[str, Any]:
        """One REST pass: market clock + batched snapshots. Returns a small report."""
        if not self.data.key_id:
            # No keys: every REST call would be refused with 401. Do not burn the
            # budget or the log — the capability UI already says the account is unlinked.
            self.needs_keys = True
            self.market_open = None
            return {"market_open": None, "equities": 0, "note": "no keys linked — REST polling disabled"}
        clk = await asyncio.to_thread(self.data.clock, self.paper)
        if clk is not None:
            self.last_clock = clk                 # cached: the palette must not poll
        self.market_open = None if clk is None else bool(clk.get("is_open"))
        report: dict[str, Any] = {"market_open": self.market_open, "equities": 0, "crypto": 0,
                                  "unchanged": 0}
        equities = self.equity_symbols
        if equities and self.market_open is not False:
            snaps = await asyncio.to_thread(self.data.snapshots, equities)
            from orderflow_system.data.models import Side
            for alpaca_symbol, snap in snaps.items():
                app = self._app_for(alpaca_symbol)
                if not app:
                    continue
                tick = normalize_snapshot_trade(snap, symbol=alpaca_symbol)
                quote = normalize_snapshot_quote(snap, symbol=alpaca_symbol)
                if tick is not None:
                    key = (tick.timestamp_ms, tick.price, tick.size, tick.trade_id)
                    if self._last_snapshot_print.get(app) == key:
                        report["unchanged"] += 1        # the same print as the last poll
                        continue
                    self._last_snapshot_print[app] = key
                    if quote is not None and quote.is_valid():
                        tick.side = Side.BUY if tick.price >= quote.mid else Side.SELL
                    self._deliver(app, tick)
                    report["equities"] += 1
        return report

    async def _poll_loop(self) -> None:
        """Snapshots while the market is open (or unknown), never in a hot loop when closed."""
        while True:
            try:
                await self.poll_once()
                if not self.data.key_id:
                    delay = 60.0                          # nothing to poll without keys
                elif (self.data.last_error or "").find("401") >= 0:
                    delay = 60.0                          # bad keys: do not hammer it
                    self.needs_keys = True
                elif self.market_open is False:
                    delay = max(30.0, self.snapshot_seconds * 6)
                else:
                    delay = self.snapshot_seconds
            except asyncio.CancelledError:
                raise
            except Exception as exc:                        # noqa: BLE001
                self._error(f"poll: {exc}")
                delay = 15.0
            await asyncio.sleep(delay)

    def _error(self, text: str) -> None:
        self.errors.append(text)
        if len(self.errors) > 20:
            self.errors.pop(0)
        logger.warning("alpaca feed: %s", text)

    # ── status surface ──
    def status(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "feed": self.feed,
            "paper": self.paper,
            "symbols": dict(self.symbols),
            "market_open": self.market_open,
            "subscriptions": self.subscriptions.as_dict(),
            "streams": [s.status() for s in self.streams],
            "budget": self.data.budget.snapshot(),
            "needs_keys": self.needs_keys,
            "errors": list(self.errors[-5:]),
            "uptime_s": round((time.time() - self.started_ms / 1000.0), 1) if self.started_ms else 0.0,
            "depth": False,
            "depth_reason": "Alpaca publishes trades, quotes and bars — no order book.",
        }
