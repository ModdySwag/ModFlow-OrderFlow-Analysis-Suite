"""
Extra Bybit streams the base feed does not subscribe to, plus REST loaders.

The repo's ``BybitFeed`` subscribes ``publicTrade`` + ``orderbook.50``. the reference layout-class
analysis needs more:

* ``orderbook.200``    — a deep book for the liquidity heatmap
* ``allLiquidation``   — the liquidation stream (stop-run confirmation)
* block-trade flags    — ``publicTrade`` carries ``BT`` (block trade) which the
                         base feed discards; block prints are a first-class the reference layout
                         concept ("Big Trades")

All public endpoints: no API key, no account. Verified against
``wss://stream.bybit.com/v5/public/linear`` during development.
"""

from __future__ import annotations

import inspect
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

import websockets

from orderflow_system.data.feed_session import VENUE_POLICIES, FeedSession

logger = logging.getLogger(__name__)

WS_URL = "wss://stream.bybit.com/v5/public/linear"
REST_BASE = "https://api.bybit.com"


async def _maybe_await(value: Any) -> Any:
    """Call handler results tolerate sync OR async callbacks.

    Awaiting a plain ``None`` (a sync callback's return value) raises
    ``TypeError: object NoneType can't be used in 'await' expression`` and used
    to kill the whole listener on the first liquidation — hence this guard.
    """
    if inspect.isawaitable(value):
        return await value
    return value


def _rest(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{REST_BASE}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


class BybitExtras:
    """Liquidations + deep book + block-trade flags for one or MANY symbols, on ONE connection.

    The primary ``BybitFeed`` carries trades + a 50-level book; this adds the ``allLiquidation``
    stream, the deep (200-level) book the liquidity heatmap needs, and the ``BT`` block-trade flag
    the base feed discards. It used to open one socket PER SYMBOL — five enabled instruments meant
    five extra connections, each one re-subscribing the ``publicTrade`` stream the primary feed
    already carries. It now puts every symbol's topics on one socket (the house shape of
    ``data/bybit_feed.py``), and the loop is ``FeedSession``'s: the reader is never cancelled from
    outside, the heartbeat is its own task, the reconnect ladder resets on parsed DATA only (acks
    and pongs answer ``False``, not ``None``) and Bybit's 60 s silence budget closes a socket that
    stalls without dying. Frames are routed by their topic's own symbol segment — one instrument's
    print is never delivered to another's callbacks.
    """

    def __init__(
        self,
        symbols: str | list[str],
        on_liquidation: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
        on_block_trade: Optional[Callable] = None,
        depth: int = 200,
    ) -> None:
        if isinstance(symbols, str):
            symbols = [symbols]
        self.symbols: list[str] = [str(s) for s in symbols]
        #: Single-symbol callers (and their log lines) keep reading ``.symbol``.
        self.symbol: str = self.symbols[0] if len(self.symbols) == 1 else f"{len(self.symbols)} symbols"
        self.on_liquidation = on_liquidation
        self.on_orderbook = on_orderbook
        self.on_block_trade = on_block_trade
        self.depth = depth
        self._session: Optional[FeedSession] = None
        self._ws = None
        self._running = False
        self.stats = {"liquidations": 0, "book_updates": 0, "block_trades": 0, "reconnects": 0, "errors": 0}
        #: Per-symbol channel counters: a shared connection still reports each instrument's own
        #: numbers (the hub's status line reads these through ``stats_for``).
        self.per_symbol: dict[str, dict[str, int]] = {
            s: {"liquidations": 0, "book_updates": 0, "block_trades": 0} for s in self.symbols}
        #: Local receipt time of the newest book frame per symbol — how the hub decides whether the
        #: deep book is still authoritative for that instrument (a dead extras socket must hand the
        #: map back to the primary book instead of freezing it).
        self._book_local_ms: dict[str, int] = {}

    # ── lifecycle ─────────────────────────────────────────────
    async def start(self) -> None:
        self._running = True
        self._session = FeedSession(
            "bybit",
            connect=self._connect,
            on_frame=self._on_frame,
            # WITHOUT this hook the session opens a socket and never subscribes: the venue answers
            # our 20 s pings (so the connection looks alive and no error is raised) and sends no
            # market data at all — measured live as "frames 1→2 in 25 s, zero book updates".
            on_connected=self._on_connected,
            policy=VENUE_POLICIES["bybit"],
            # Bybit answers its own JSON ping with a pong (verified live against the venue). The
            # session owns liveness here, so the library's keepalive stays off: exactly one owner.
            ping_payload=json.dumps({"op": "ping"}),
        )
        await self._session.run()

    async def stop(self) -> None:
        self._running = False
        if self._session is not None:
            await self._session.stop()

    async def _connect(self):
        conn = await websockets.connect(WS_URL, ping_interval=None)
        self._ws = conn
        return conn

    async def _on_connected(self, conn) -> None:
        args: list[str] = []
        for sym in self.symbols:
            args += [f"allLiquidation.{sym}", f"orderbook.{self.depth}.{sym}", f"publicTrade.{sym}"]
        await conn.send(json.dumps({"op": "subscribe", "args": args}))
        logger.info("BybitExtras subscribed %d topic(s) for %s", len(args), ", ".join(self.symbols))

    async def _on_frame(self, raw: Any) -> Any:
        """One raw frame; ``False`` = it carried no market data (ack, pong, junk)."""
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False
        return await self._handle(msg)

    def book_age_ms(self, symbol: str) -> int:
        """How long ago this symbol's newest book frame arrived (a large number = never)."""
        last = self._book_local_ms.get(symbol)
        if not last:
            return 1 << 62
        return max(0, int(time.time() * 1000) - last)

    def stats_for(self, symbol: Optional[str] = None) -> dict[str, Any]:
        """Per-symbol channel counters plus the connection's own health."""
        out: dict[str, Any] = dict(self.per_symbol.get(symbol or "", {}) or {})
        session = self._session.stats() if self._session is not None else {}
        out["connection"] = {"frames": session.get("frames", 0),
                             "reconnects": session.get("reconnects", 0),
                             "last_error": session.get("last_error", ""),
                             "running": self._running}
        return out

    # ── dispatch ──────────────────────────────────────────────
    async def _handle(self, msg: dict[str, Any]) -> Any:
        """Route one frame; ``True`` = parsed market data, ``False`` = nothing for the ladder."""
        if msg.get("success") is False:
            logger.warning("BybitExtras subscribe rejected: %s", msg.get("ret_msg"))
            return False
        topic = str(msg.get("topic") or "")
        if not topic:
            return False                        # a pong / subscribe ack carries no topic
        symbol = topic.rsplit(".", 1)[-1]
        hit = self.per_symbol.get(symbol)
        if hit is None:
            logger.debug("BybitExtras: %r is not this connection's topic (ignored)", topic)
            return False
        data = msg.get("data")
        if not data:
            return False
        ts_ms = int(msg.get("ts") or time.time() * 1000)

        if topic.startswith("allLiquidation."):
            if self.on_liquidation is None:
                return False
            for row in data:
                hit["liquidations"] += 1
                self.stats["liquidations"] += 1
                await _maybe_await(self.on_liquidation(
                    symbol=symbol,
                    price=float(row.get("p", 0)),
                    size=float(row.get("v", 0)),
                    side=str(row.get("S", "")),
                    ts_ms=int(row.get("T", ts_ms)),
                ))
            return True

        if topic.startswith("orderbook."):
            if self.on_orderbook is None:
                return False
            hit["book_updates"] += 1
            self.stats["book_updates"] += 1
            self._book_local_ms[symbol] = int(time.time() * 1000)
            # NB: data["u"] is an update *sequence id*, not a clock. Use the envelope timestamp so
            # downstream bucketing sees real time.
            await _maybe_await(self.on_orderbook(symbol, msg.get("type", ""), data, ts_ms))
            return True

        if topic.startswith("publicTrade."):
            if self.on_block_trade is None:
                return False
            for row in data:
                if row.get("BT"):               # exchange-flagged block trade
                    hit["block_trades"] += 1
                    self.stats["block_trades"] += 1
                    await _maybe_await(self.on_block_trade(
                        symbol=symbol,
                        price=float(row.get("p", 0)),
                        size=float(row.get("v", 0)),
                        side=str(row.get("S", "")),
                        ts_ms=int(row.get("T", ts_ms)),
                    ))
            return True                          # real venue data even without a block flag
        return False


class BybitDepthBook:
    """Incremental L2 book for the ``orderbook.<depth>.<symbol>`` stream.

    Bybit sends a full ``snapshot`` first, then ``delta`` updates where size 0
    deletes a level — the same convention the repo's tracker implements for the
    50-level book. Keeping our own copy lets the heatmap use the deep (200-level)
    stream without touching the repo's classes.
    """

    def __init__(self, symbol: str, max_keep: int = 600) -> None:
        self.symbol = symbol
        self.max_keep = max_keep
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}
        self.ts_ms = 0
        self.updates = 0

    def apply(self, msg_type: str, data: dict[str, Any], ts_ms: int = 0) -> None:
        if msg_type == "snapshot":
            self.bids = {float(p): float(q) for p, q in data.get("b", []) if float(q) > 0}
            self.asks = {float(p): float(q) for p, q in data.get("a", []) if float(q) > 0}
        else:
            for side, key in ((self.bids, "b"), (self.asks, "a")):
                for price, qty in data.get(key, []):
                    p, q = float(price), float(qty)
                    if q == 0:
                        side.pop(p, None)
                    else:
                        side[p] = q
        self.ts_ms = int(data.get("u") or ts_ms or 0)
        self.updates += 1
        if len(self.bids) > self.max_keep:
            self.bids = dict(sorted(self.bids.items(), reverse=True)[: self.max_keep])
        if len(self.asks) > self.max_keep:
            self.asks = dict(sorted(self.asks.items())[: self.max_keep])

    def to_snapshot(self):
        from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot
        bids = sorted((OrderbookLevel(price=p, quantity=q) for p, q in self.bids.items()), key=lambda l: -l.price)
        asks = sorted((OrderbookLevel(price=p, quantity=q) for p, q in self.asks.items()), key=lambda l: l.price)
        return OrderbookSnapshot(timestamp_ms=self.ts_ms, bids=bids, asks=asks)


# ── REST loaders (no key needed) ────────────────────────────────────────────

def fetch_recent_trades(symbol: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Latest public prints — used to preload the tape / seed a replay."""
    payload = _rest("/v5/market/recent-trade", {"category": "linear", "symbol": symbol, "limit": min(limit, 1000)})
    rows = payload.get("result", {}).get("list", []) or []
    return [{
        "ts_ms": int(r.get("time", 0)),
        "price": float(r.get("price", 0)),
        "size": float(r.get("size", 0)),
        "side": str(r.get("side", "")).lower(),
        "block": bool(r.get("isBlockTrade", False)),
        "id": r.get("execId", ""),
    } for r in rows]


def fetch_klines(symbol: str, interval: str = "1", limit: int = 1000) -> list[dict[str, Any]]:
    """Historical candles in Bybit's own frame — a replay seed independent of our DB."""
    payload = _rest("/v5/market/kline", {"category": "linear", "symbol": symbol, "interval": interval, "limit": min(limit, 1000)})
    rows = payload.get("result", {}).get("list", []) or []
    out = []
    for r in rows:                       # Bybit returns newest first, each row is a string array
        out.append({
            "ts_ms": int(r[0]), "open": float(r[1]), "high": float(r[2]),
            "low": float(r[3]), "close": float(r[4]), "volume": float(r[5]),
        })
    return list(reversed(out))


def fetch_instruments(symbols: list[str]) -> dict[str, bool]:
    """Existence check for linear perpetuals (cached by the control layer)."""
    return {s: bool(_rest("/v5/market/instruments-info", {"category": "linear", "symbol": s}).get("result", {}).get("list")) for s in symbols}
