"""Binance USDⓈ-M futures — the public feed: aggTrade + diff-depth, snapshot-synced.

The third L2 venue for this suite (Bybit is the default; Alpaca carries quotes only). What makes
this adapter different from a naive listener is the *depth chain*: Binance publishes only depth
**diffs** on the websocket, so a local book is only valid while it is stitched to a REST snapshot
and every diff in between. The machine below (buffer → validate → replay → resync) is the one the
flowsurface reading pass singled out as that crate's most transferable algorithm; this is an
independent implementation of the same contract, in this suite's own terms:

    WaitingSnapshot            Live
    ├─ fetch /fapi/v1/depth    ├─ drop  u < last_update_id          (stale/duplicate)
    ├─ buffer diffs (≤ 512)    ├─ first event:  U ≤ last+1 ≤ u      (stitch)
    └─ replay in order         ├─ then:         pu == previous u    (chain)
                               └─ any break → mark stale, drain, re-fetch a snapshot

Everything public: `wss://fstream.binance.com/ws` + `https://fapi.binance.com`. No key, no account.
Timestamps are venue ms. Values pass the same `math.isfinite` gate the Bybit feed uses (a JSON
`NaN` would otherwise sail into the aggregates and never raise).

The session loop (reader never cancelled, per-venue heartbeat policy, jittered ladder) is
`data/feed_session.py` — Binance is server-driven there: it pings us and the library answers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import websockets

from orderflow_system.data.feed_session import FeedSession
from orderflow_system.data.models import Tick, Side, OrderbookSnapshot, OrderbookLevel

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://fstream.binance.com/ws"          # dynamic SUBSCRIBE, no stream-name URL
BINANCE_REST = "https://fapi.binance.com"
DEPTH_LIMIT = 1000                                        # venue max for one REST snapshot
DEPTH_MS = 100                                            # the diff cadence subscribed below

#: How many diff events may buffer while the REST snapshot is in flight. A cap, not a queue: past
#: it the machine resyncs instead of pretending the book is whole.
MAX_PENDING_DIFFS = 512

#: Book levels kept per side (the venue's own diff stream can run deeper than any panel needs).
MAX_LEVELS = 1000

#: A stale book refetches its REST snapshot at most this often — bounded self-healing, never a
#: fetch storm (the schedule call sits on the frame path).
SNAPSHOT_COOLDOWN_S = 1.0


def _finite(value: Any) -> Optional[float]:
    """A venue number that is safe to carry, or None (see the Bybit feed — same gate)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _level(pair: Any) -> Optional[OrderbookLevel]:
    try:
        price, qty = _finite(pair[0]), _finite(pair[1])
    except (TypeError, IndexError, KeyError):
        return None
    if price is None or qty is None or price <= 0 or qty < 0:
        return None
    return OrderbookLevel(price=price, quantity=qty)


@dataclass
class BinanceDepthBook:
    """One symbol's local book: a snapshot plus a validated diff chain.

    Pure and synchronous on purpose — the websocket handler only ever calls `snapshot()` and
    `on_diff()`, so the chain rules are testable without a socket.
    """

    symbol: str
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    last_update_id: int = 0
    has_snapshot: bool = False
    stale: bool = True
    pending: deque = field(default_factory=lambda: deque(maxlen=MAX_PENDING_DIFFS))
    last_ts_ms: int = 0
    # counters a status line can quote
    applied: int = 0
    dropped: int = 0
    gaps: int = 0
    resyncs: int = 0
    junk_values: int = 0
    snapshot_evictions: int = 0

    # ── ingest ────────────────────────────────────────────────
    def snapshot(self, last_update_id: int, bids: list, asks: list, ts_ms: int = 0) -> int:
        """Install a REST snapshot and replay what buffered meanwhile. Returns diffs replayed."""
        self.bids = {lv.price: lv.quantity for lv in map(_level, bids) if lv is not None and lv.quantity > 0}
        self.asks = {lv.price: lv.quantity for lv in map(_level, asks) if lv is not None and lv.quantity > 0}
        self.last_update_id = int(last_update_id or 0)
        self.has_snapshot = True
        self.stale = False
        self.last_ts_ms = int(ts_ms or 0)

        replayed = 0
        pending, self.pending = list(self.pending), deque(maxlen=MAX_PENDING_DIFFS)
        for diff in pending:
            if diff["u"] < self.last_update_id:            # ws event older than the snapshot
                self.dropped += 1
                continue
            if self._apply_chain(diff):
                replayed += 1
            else:
                self._mark_stale("a gap while replaying after the snapshot")
                break
        self._trim()
        return replayed

    def on_diff(self, first_id: int, final_id: int, prev_final_id: Optional[int],
                bids: Optional[list] = None, asks: Optional[list] = None, ts_ms: int = 0) -> bool:
        """Apply one diff event. False means the caller must resync (a gap was detected)."""
        diff = {"U": int(first_id), "u": int(final_id), "pu": prev_final_id,
                "b": bids or [], "a": asks or [], "T": ts_ms}

        if not self.has_snapshot:
            self.pending.append(diff)                      # buffer while the snapshot lands
            return True
        if diff["u"] < self.last_update_id:
            # A duplicate or a late event: applying it would write an old state over a newer one.
            self.dropped += 1
            return True
        if self.stale:
            self.dropped += 1
            return True                                    # waiting for a fresh snapshot
        if not self._apply_chain(diff):
            self._mark_stale("sequence gap")
            return False
        return True

    def _apply_chain(self, diff: dict) -> bool:
        """Validate one event against the chain and apply it. False = gap."""
        first_id, final_id, prev_final_id = diff["U"], diff["u"], diff["pu"]
        if self.applied_at_chain_head():
            # The first event after a snapshot must straddle `last_update_id + 1` — the venue's
            # own rule; a gap here means the snapshot is not the one the stream continued from.
            if not (first_id <= self.last_update_id + 1 <= final_id):
                return False
        else:
            expect = getattr(self, "_chain_prev", None)
            if expect is None:
                return False
            if prev_final_id is not None:
                if int(prev_final_id) != expect:
                    return False
            elif first_id != expect + 1:
                return False
        self._apply_levels(diff["b"], side="bid")
        self._apply_levels(diff["a"], side="ask")
        self.last_update_id = int(final_id)
        self._chain_prev = int(final_id)
        self.last_ts_ms = int(diff.get("T") or self.last_ts_ms or 0)
        self.applied += 1
        return True

    def applied_at_chain_head(self) -> bool:
        """True while the book has never applied a diff since its snapshot."""
        return getattr(self, "_chain_prev", None) is None

    def _apply_levels(self, rows: Any, side: str) -> None:
        book = self.bids if side == "bid" else self.asks
        for row in rows or []:
            lv = _level(row)
            if lv is None:
                self.junk_values += 1
                continue
            if lv.quantity == 0:
                book.pop(lv.price, None)                   # qty 0 = remove the level
            else:
                book[lv.price] = lv.quantity
        self._trim()

    def _trim(self) -> None:
        """Keep the book at the venue's own REST depth so memory cannot creep."""
        for book, reverse in ((self.bids, True), (self.asks, False)):
            if len(book) > MAX_LEVELS:
                keep = sorted(book.items(), key=lambda kv: -kv[0])[:MAX_LEVELS] if reverse \
                    else sorted(book.items(), key=lambda kv: kv[0])[:MAX_LEVELS]
                dropped = len(book) - len(keep)
                book.clear()
                book.update(dict(keep))
                self.snapshot_evictions += dropped

    def _mark_stale(self, reason: str) -> None:
        if not self.stale:
            self.gaps += 1
        self.stale = True
        self.pending.clear()
        self._chain_prev = None
        logger.warning("binance orderbook %s: %s — marked stale, waiting for a fresh snapshot",
                       self.symbol, reason)

    # ── output ────────────────────────────────────────────────
    def to_snapshot(self, levels: int = 0) -> OrderbookSnapshot:
        take = MAX_LEVELS if levels <= 0 else min(int(levels), MAX_LEVELS)
        bids = sorted(self.bids.items(), key=lambda kv: -kv[0])[:take]
        asks = sorted(self.asks.items(), key=lambda kv: kv[0])[:take]
        snap = OrderbookSnapshot(
            timestamp_ms=int(self.last_ts_ms or time.time() * 1000),
            bids=[OrderbookLevel(price=p, quantity=q) for p, q in bids],
            asks=[OrderbookLevel(price=p, quantity=q) for p, q in asks],
        )
        snap.stale = bool(self.stale)
        return snap

    def health(self) -> dict[str, Any]:
        return {
            "stale": self.stale,
            "has_snapshot": self.has_snapshot,
            "last_update_id": self.last_update_id,
            "pending": len(self.pending),
            "levels": {"bids": len(self.bids), "asks": len(self.asks)},
            "applied": self.applied,
            "dropped": self.dropped,
            "gaps": self.gaps,
            "junk_values": self.junk_values,
        }


class BinanceFeed:
    """Live Binance USDⓈ-M futures: aggTrade (taker side) + diff-depth, stitched to REST snapshots.

    Interface-compatible with `BybitFeed` (same callbacks, `get_orderbook`, `book_health`) so the
    engine and the atlas hub cannot tell them apart.
    """

    def __init__(
        self,
        symbols: list[str],
        on_tick: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
        *,
        depth_ms: int = DEPTH_MS,
        snapshot_levels: int = DEPTH_LIMIT,
        rest_base: str = BINANCE_REST,
        ws_url: str = BINANCE_WS_URL,
        snapshot_cooldown_s: float = SNAPSHOT_COOLDOWN_S,
    ):
        self.symbols = [str(s).upper() for s in symbols]
        self.on_tick = on_tick
        self.on_orderbook = on_orderbook
        self.depth_ms = int(depth_ms)
        self.snapshot_levels = int(snapshot_levels)
        self.rest_base = str(rest_base).rstrip("/")
        self.ws_url = ws_url
        self.snapshot_cooldown_s = float(snapshot_cooldown_s)

        self.books: dict[str, BinanceDepthBook] = {s: BinanceDepthBook(s) for s in self.symbols}
        self._session: Optional[FeedSession] = None
        self._conn: Any = None
        self._snapshot_tasks: dict[str, asyncio.Task] = {}
        self._snapshot_last: dict[str, float] = {}
        self._ts_fallback_warned = False
        self.junk_prints = 0
        self.ticks = 0
        self._stale_announced: set[str] = set()

    # ── lifecycle ────────────────────────────────────────────
    async def start(self) -> None:
        self._session = FeedSession(
            "binance",
            connect=self._connect,
            on_frame=self._on_frame,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
        )
        await self._session.run()

    async def stop(self) -> None:
        for task in list(self._snapshot_tasks.values()):
            task.cancel()
        self._snapshot_tasks.clear()
        if self._session is not None:
            await self._session.stop()

    async def _connect(self):
        conn = await websockets.connect(self.ws_url, ping_interval=None)   # server-driven venue
        self._conn = conn
        return conn

    async def _on_connected(self, conn) -> None:
        self._ts_fallback_warned = False
        params: list[str] = []
        for sym in self.symbols:
            low = sym.lower()
            # `@trade` (every fill, with the maker flag) — NOT `@aggTrade`: on the futures venue the
            # aggregate stream does not flow on this socket (verified against fstream.binance.com:
            # 12 s of subscription with zero events while `@trade` delivered ~38/s). Individual fills
            # are also the better input for footprint/delta work, which is what this suite does.
            params.append(f"{low}@trade")
            params.append(f"{low}@depth@{self.depth_ms}ms")
        await conn.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": 1}))
        logger.info("Binance feed subscribed: %d streams over %d symbols", len(params), len(self.symbols))
        # Every symbol needs a fresh snapshot on a new socket: the chain cannot survive a reconnect.
        for sym in self.symbols:
            self.books[sym].has_snapshot = False
            self.books[sym].stale = True
            self.books[sym].pending.clear()
            self._schedule_snapshot(sym, force=True)

    async def _on_disconnected(self, exc: Optional[BaseException]) -> None:
        self._conn = None
        for book in self.books.values():
            book.stale = True
        if exc is not None:
            logger.warning("Binance socket closed: %s", exc)

    # ── frames ───────────────────────────────────────────────
    async def _on_frame(self, raw: Any) -> None:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Binance: invalid JSON (%s)", str(raw)[:120])
            return
        if not isinstance(msg, dict):
            return
        kind = msg.get("e")
        if kind in ("trade", "aggTrade"):
            await self._handle_trade(msg)
        elif kind == "depthUpdate":
            await self._handle_depth(msg)
        # subscribe/unsubscribe acks carry `result`/`id` and nothing to do

    async def _handle_trade(self, msg: dict) -> None:
        symbol = str(msg.get("s") or "").upper()
        if symbol not in self.books:
            return
        price, size = _finite(msg.get("p")), _finite(msg.get("q"))
        if price is None or price <= 0 or size is None or size < 0:
            self.junk_prints += 1
            return
        ts = msg.get("T")
        if ts is None:
            if not self._ts_fallback_warned:
                self._ts_fallback_warned = True
                logger.warning("Binance trade without T (venue time) — falling back to the local "
                               "clock; timestamps are loose until the next reconnect")
            ts = int(time.time() * 1000)
        # `m` = "is the buyer the maker": True means the aggressor was the SELLER.
        side = Side.SELL if bool(msg.get("m")) else Side.BUY
        # The fill id: `a` on the spot aggregate stream, `t` on the futures trade stream.
        tick = Tick(timestamp_ms=int(ts), price=price, size=size, side=side,
                    trade_id=str(msg.get("a") or msg.get("t") or ""))
        self.ticks += 1
        if self.on_tick:
            await self.on_tick(symbol, tick)

    async def _handle_depth(self, msg: dict) -> None:
        symbol = str(msg.get("s") or "").upper()
        book = self.books.get(symbol)
        if book is None:
            return
        try:
            first_id = int(msg.get("U"))
            final_id = int(msg.get("u"))
        except (TypeError, ValueError):
            return
        prev = msg.get("pu")
        prev_final_id = int(prev) if prev is not None else None
        ts = msg.get("T") or msg.get("E") or 0
        ok = book.on_diff(first_id, final_id, prev_final_id,
                          msg.get("b") or [], msg.get("a") or [], int(ts or 0))
        if book.stale and symbol not in self._stale_announced:
            self._stale_announced.add(symbol)
            logger.warning("Binance orderbook %s is stale (gap) — a fresh snapshot is on the way", symbol)
        if not ok:
            self._schedule_snapshot(symbol)
        elif book.stale:
            # A book can be stale without this frame being the culprit (a replay gap): keep a
            # snapshot in flight, rate-limited, until it is whole again.
            self._schedule_snapshot(symbol)
        elif symbol in self._stale_announced:
            self._stale_announced.discard(symbol)
            logger.info("Binance orderbook %s recovered after a resync", symbol)
        if self.on_orderbook and book.has_snapshot:
            await self.on_orderbook(symbol, book.to_snapshot())

    # ── snapshots ────────────────────────────────────────────
    def _schedule_snapshot(self, symbol: str, *, force: bool = False) -> None:
        """Fetch a REST snapshot without blocking the reader (deduped and rate-limited per symbol)."""
        task = self._snapshot_tasks.get(symbol)
        if task is not None and not task.done():
            return
        now = time.monotonic()
        if not force and now - self._snapshot_last.get(symbol, 0.0) < self.snapshot_cooldown_s:
            return
        self._snapshot_last[symbol] = now
        self._snapshot_tasks[symbol] = asyncio.create_task(self._refresh_snapshot(symbol))

    async def _refresh_snapshot(self, symbol: str) -> None:
        try:
            payload = await asyncio.to_thread(self._fetch_snapshot, symbol)
        except Exception as exc:                            # noqa: BLE001 — network is the venue's
            logger.warning("Binance snapshot fetch failed for %s: %s", symbol, exc)
            return
        book = self.books.get(symbol)
        if book is None or not isinstance(payload, dict):
            return
        last_id = payload.get("lastUpdateId")
        try:
            replayed = book.snapshot(int(last_id), payload.get("bids") or [],
                                     payload.get("asks") or [], int(payload.get("E") or 0))
        except (TypeError, ValueError):
            return
        book.resyncs += 1
        logger.info("Binance orderbook %s: snapshot installed (lastUpdateId=%s, %d diffs replayed, "
                    "%d levels)", symbol, last_id, replayed, len(book.bids) + len(book.asks))
        if self.on_orderbook:
            await self.on_orderbook(symbol, book.to_snapshot())
        if book.stale:
            # The replay could not stitch onto this snapshot (a hole while it was in flight):
            # ask again, rate-limited, so a stale book always has a way back. The follow-up is
            # scheduled *after* this task finishes — a synchronous re-schedule would dedupe
            # against itself and the book would stay stale forever.
            asyncio.get_running_loop().call_later(0.0, self._schedule_snapshot, symbol)

    def _fetch_snapshot(self, symbol: str) -> dict:
        query = urllib.parse.urlencode({"symbol": symbol, "limit": self.snapshot_levels})
        req = urllib.request.Request(f"{self.rest_base}/fapi/v1/depth?{query}",
                                     headers={"User-Agent": "OrderFlow-Analysis-Pro"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ── read paths (parity with BybitFeed) ───────────────────
    def get_orderbook(self, symbol: str) -> Optional[OrderbookSnapshot]:
        book = self.books.get(str(symbol).upper())
        if book is None or not book.has_snapshot:
            return None
        return book.to_snapshot()

    def book_health(self) -> dict:
        return {
            "venue": "binance",
            "stale": sorted(s for s, b in self.books.items() if b.stale),
            "gaps": sum(b.gaps for b in self.books.values()),
            "dropped_deltas": sum(b.dropped for b in self.books.values()),
            "junk_values": sum(b.junk_values for b in self.books.values()) + self.junk_prints,
            "seq": {s: b.last_update_id for s, b in self.books.items()},
        }

    def stats(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "venue": "binance",
            "symbols": list(self.books),
            "ticks": self.ticks,
            "junk_prints": self.junk_prints,
            "books": {s: b.health() for s, b in self.books.items()},
        }
        if self._session is not None:
            out["session"] = self._session.stats()
        return out

    # ── capability probe (public REST; used by /api/control/capabilities) ────
    @staticmethod
    def validate_symbols(symbols: list[str], rest_base: str = BINANCE_REST,
                         period: str = "1d", open_interest: bool = True) -> dict[str, bool]:
        """Ask the venue which of these symbols exist (perpetual futures).

        A symbol is `True` only when the venue itself lists it as a TRADING perpetual — that is
        stronger evidence than any hardcoded list, and it is the same shape `bybit_validate`
        returns so the capability block stays symmetric.
        """
        wanted = {str(s).upper(): False for s in symbols}
        if not wanted:
            return {}
        try:
            req = urllib.request.Request(f"{rest_base}/fapi/v1/exchangeInfo",
                                         headers={"User-Agent": "OrderFlow-Analysis-Pro"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                             # noqa: BLE001 — reported as "unknown"
            logger.warning("Binance symbol validation failed: %s", exc)
            return wanted
        for entry in info.get("symbols", []) or []:
            sym = str(entry.get("symbol") or "").upper()
            if sym in wanted and str(entry.get("contractType")) in ("PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER"):
                wanted[sym] = str(entry.get("status")) == "TRADING"
        return wanted
