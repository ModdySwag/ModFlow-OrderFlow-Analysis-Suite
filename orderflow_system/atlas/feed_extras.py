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

import asyncio
import inspect
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

import websockets

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
    """Liquidations + deep book + block-trade flags for one symbol."""

    def __init__(
        self,
        symbol: str,
        on_liquidation: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
        on_block_trade: Optional[Callable] = None,
        depth: int = 200,
    ) -> None:
        self.symbol = symbol
        self.on_liquidation = on_liquidation
        self.on_orderbook = on_orderbook
        self.on_block_trade = on_block_trade
        self.depth = depth
        self._ws = None
        self._running = False
        self._reconnect_delay = 1.0
        self.stats = {"liquidations": 0, "book_updates": 0, "block_trades": 0, "reconnects": 0, "errors": 0}

    # ── lifecycle ─────────────────────────────────────────────
    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._listen()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.stats["errors"] += 1
                self.stats["reconnects"] += 1
                logger.warning("BybitExtras(%s) reconnect in %.1fs: %s", self.symbol, self._reconnect_delay, exc)
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    async def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def _listen(self) -> None:
        async with websockets.connect(WS_URL, ping_interval=20) as ws:
            self._ws = ws
            self._reconnect_delay = 1.0
            args = [f"allLiquidation.{self.symbol}", f"orderbook.{self.depth}.{self.symbol}", f"publicTrade.{self.symbol}"]
            await ws.send(json.dumps({"op": "subscribe", "args": args}))
            logger.info("BybitExtras subscribed: %s", args)
            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle(msg)

    async def _handle(self, msg: dict[str, Any]) -> None:
        if msg.get("success") is False:
            logger.warning("BybitExtras subscribe rejected: %s", msg.get("ret_msg"))
            return
        topic = msg.get("topic", "")
        data = msg.get("data")
        ts_ms = int(msg.get("ts") or time.time() * 1000)

        if topic.startswith("allLiquidation.") and self.on_liquidation and data:
            for row in data:
                self.stats["liquidations"] += 1
                await _maybe_await(self.on_liquidation(
                    symbol=self.symbol,
                    price=float(row.get("p", 0)),
                    size=float(row.get("v", 0)),
                    side=str(row.get("S", "")),
                    ts_ms=int(row.get("T", ts_ms)),
                ))

        elif topic.startswith("orderbook.") and self.on_orderbook and data:
            self.stats["book_updates"] += 1
            # NB: data["u"] is an update *sequence id*, not a clock. Use the
            # envelope timestamp so downstream bucketing sees real time.
            await _maybe_await(self.on_orderbook(self.symbol, msg.get("type", ""), data, ts_ms))

        elif topic.startswith("publicTrade.") and self.on_block_trade and data:
            for row in data:
                if row.get("BT"):                      # exchange-flagged block trade
                    self.stats["block_trades"] += 1
                    await _maybe_await(self.on_block_trade(
                        symbol=self.symbol,
                        price=float(row.get("p", 0)),
                        size=float(row.get("v", 0)),
                        side=str(row.get("S", "")),
                        ts_ms=int(row.get("T", ts_ms)),
                    ))


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
