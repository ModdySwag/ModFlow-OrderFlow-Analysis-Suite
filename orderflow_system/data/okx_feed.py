"""OKX USDT swaps — the public feed: `trades` + `books`, snapshot-first, `seqId`-chained.

The fourth L2 venue for this suite (Bybit is the default; Binance carries the diff-chain;
Alpaca quotes only). What makes this adapter different from the Binance one is that OKX needs no
stitching machine at all: the `books` channel **pushes the full 400-level snapshot first** (verified
live: exactly 400 levels per side, ~21 KB, `prevSeqId` = -1) and then 100 ms incremental updates,
so there is no REST snapshot to race against and no buffer to replay. The whole book machine is
therefore:

    subscribe ──▶ snapshot (400×400, prevSeqId = -1) ──▶ updates (sz "0" removes a level)
                        ▲                                    │
                        └── unsubscribe + subscribe ◀── gap / checksum mismatch / stale

Recovery is the cheap path, and it was chosen after watching the venue: re-sending the *same*
subscribe only re-acks (no snapshot), while unsubscribe→subscribe on the live socket pushes a fresh
400-level snapshot immediately. So a broken book costs one round of two small frames — no reconnect,
and the other symbols sharing the socket never notice.

Two venue facts that differ from the documentation, both verified live (the Binance adapter's author
found the same class of thing with `@aggTrade`, which is why this file was checked against the wire
before it was written):

* **The crc32 checksum is dead.** OKX's docs still describe it and this module still implements it
  exactly (`okx_book_checksum`: the top 25 bids then the top 25 asks, each px/sz token cut to 25
  characters, joined with ":", `zlib.crc32`), but the venue now fixes the field to `0` — the docs
  themselves mark it "Deprecated … must no longer be used for integrity verification. Please use
  seqId/prevSeqId". Every live frame carried `"checksum": 0`. So a `0` is read as "no value" and
  never stales a book; a *nonzero* value is compared, and a disagreement is treated as a broken book
  (stale + counted + a fresh snapshot), because that would mean the venue believes something about
  our book that we do not.
* **`{"op": "ping"}` is rejected.** The current endpoint answers it with
  `{"event":"error","code":"60012","msg":"Illegal request: …"}` — and so does `/ws/v5/business`.
  What works is a bare text frame `ping`, answered by a bare text frame `pong` (not JSON). That is
  exactly what `data/feed_session.py` sends by default, so the OKX policy
  (`VENUE_POLICIES["okx"]`, `ping_after_idle`) is driven untouched: the frame handler just has to
  tolerate the `pong` frame instead of logging it as a parse error.

Continuity is the venue's own `seqId`/`prevSeqId` chain (verified live: the snapshot opens it with
`prevSeqId=-1`, every update's `prevSeqId` matched the previous frame's `seqId`), with the two
documented exceptions handled: the empty `{"asks": [], "bids": []}` keepalive (`seqId == prevSeqId`)
is not a gap, and a maintenance **sequence reset** (`seqId < prevSeqId`) is adopted as the new head
rather than treated as a hole. The keepalive itself could not be provoked live — 100 s on the
quietest listed USDT swap still pushed ~10 updates/s — so that one shape is implemented from the
documentation rather than from a captured frame.

Everything public: `wss://ws.okx.com:8443/ws/v5/public` + `https://www.okx.com`. No key, no account.
Timestamps are venue ms. Sizes stay in the venue's own unit — OKX perpetual `sz` is in **contracts**
(`BTC-USDT-SWAP` `ctVal` = 0.01 BTC, from the same REST listing `validate_symbols` reads); the
public feed carries no conversion factor, so the adapter reports contracts rather than inventing a
base-currency number the venue never sent.

Symbols are mapped to venue instIds by one documented rule — `BTCUSDT` → `BTC-USDT-SWAP` — and
`validate_symbols` checks them against the venue's own listing (GET /api/v5/public/instruments).

The session loop (reader never cancelled, per-venue heartbeat policy, jittered ladder) is
`data/feed_session.py`; the ladder resets only on a parsed frame, which here means a real market
frame rather than a `pong`.
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import websockets

from orderflow_system.data.feed_session import FeedSession, VENUE_POLICIES
from orderflow_system.data.models import Tick, Side, OrderbookSnapshot, OrderbookLevel

logger = logging.getLogger(__name__)

OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"        # dynamic subscribe, no stream-name URL
OKX_REST = "https://www.okx.com"
TRADES_CHANNEL = "trades"
BOOKS_CHANNEL = "books"                                   # snapshot + updates, checksum/seqId fields

#: The venue's own push depth: a fresh `books` snapshot carries 400 levels per side (verified live),
#: so the book is capped there — anything deeper is a level the venue itself does not publish.
BOOK_DEPTH = 400

#: The checksum covers the top 25 levels per side, bids first (OKX's spec, kept for the day the
#: field comes back — see the module docstring on why a live `0` is not a mismatch).
CHECKSUM_LEVELS = 25
CHECKSUM_TOKEN_CHARS = 25

#: A stale book asks for a fresh snapshot at most this often (two small frames, so this is about
#: bounding a resync loop, not about network cost).
RESYNC_COOLDOWN_S = 1.0

#: The venue 403s a bare urllib request; every REST call in this module sends this header.
USER_AGENT = "OrderFlow-Analysis-Pro"


def _finite(value: Any) -> Optional[float]:
    """A venue number that is safe to carry, or None (see the Bybit feed — same gate)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _level(pair: Any) -> Optional[OrderbookLevel]:
    """One venue `[px, sz, deprecated, count]` row → OrderbookLevel, or None when unusable."""
    try:
        price, qty = _finite(pair[0]), _finite(pair[1])
    except (TypeError, IndexError, KeyError):
        return None
    if price is None or qty is None or price <= 0 or qty < 0:
        return None
    return OrderbookLevel(price=price, quantity=qty)


def _token(pair: Any) -> tuple[str, str]:
    """The venue's own text for one row: `(px, sz)`, left exactly as it arrived.

    The checksum is defined over the venue's *strings*, not over floats — rebuilding `"75662.60"`
    from `75662.6` would change the checksum input — so the raw tokens are what gets stored.
    """
    return (str(pair[0]), str(pair[1]))


def okx_book_checksum(bids: Iterable[Any], asks: Iterable[Any]) -> int:
    """OKX's documented crc32 over the top of a book: bids first, then asks.

    ``bids``/``asks`` are best-first rows (``[px, sz, ...]`` or ``(px, sz)``); up to
    :data:`CHECKSUM_LEVELS` of each side are used, every token is cut to
    :data:`CHECKSUM_TOKEN_CHARS` characters, the tokens are joined with ":" and ``zlib.crc32`` runs
    over the ASCII of that string. Returns the checksum as an unsigned 32-bit integer (the venue
    prints it signed, hence the comparison mask in :func:`verify_okx_checksum`).
    """
    tokens: list[str] = []
    for row in list(bids)[:CHECKSUM_LEVELS]:
        px, sz = _token(row)
        tokens += [px[:CHECKSUM_TOKEN_CHARS], sz[:CHECKSUM_TOKEN_CHARS]]
    for row in list(asks)[:CHECKSUM_LEVELS]:
        px, sz = _token(row)
        tokens += [px[:CHECKSUM_TOKEN_CHARS], sz[:CHECKSUM_TOKEN_CHARS]]
    return zlib.crc32(":".join(tokens).encode("ascii")) & 0xFFFFFFFF


def verify_okx_checksum(bids: Iterable[Any], asks: Iterable[Any], checksum: Any) -> Optional[bool]:
    """Compare a local book against the venue's checksum. None = the venue sent no verdict.

    A live `0` is the documented "field deprecated, fixed to 0" state (every frame carries it), so
    it is *not* evidence of a bad book and must not stale one; only a real disagreement is.
    """
    if checksum is None:
        return None
    try:
        wanted = int(checksum)
    except (TypeError, ValueError):
        return None
    if wanted == 0:
        return None                                        # the venue has no value for us here
    # The venue prints checksums signed; crc32 is unsigned, so compare the 32-bit patterns.
    return (okx_book_checksum(bids, asks) & 0xFFFFFFFF) == (wanted & 0xFFFFFFFF)


@dataclass
class OkxBook:
    """One symbol's local book: a pushed snapshot plus a `seqId`-verified update chain.

    Pure and synchronous on purpose — the websocket handler only ever calls `snapshot()` and
    `on_update()`, so the chain rules are testable without a socket.
    """

    symbol: str
    inst_id: str = ""
    #: price → quantity, and price → the venue's exact `(px, sz)` tokens for that level.
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    bid_tokens: dict[float, tuple[str, str]] = field(default_factory=dict)
    ask_tokens: dict[float, tuple[str, str]] = field(default_factory=dict)
    seq_id: Optional[int] = None
    prev_seq_id: Optional[int] = None
    has_snapshot: bool = False
    stale: bool = True
    last_ts_ms: int = 0
    # counters a status line can quote
    applied: int = 0
    dropped: int = 0
    gaps: int = 0
    resyncs: int = 0
    junk_values: int = 0
    snapshot_evictions: int = 0
    checksum_checks: int = 0
    checksum_mismatches: int = 0
    checksum_unavailable: int = 0
    seq_resets: int = 0
    heartbeats: int = 0

    # ── ingest ────────────────────────────────────────────────
    def snapshot(self, bids: list, asks: list, seq_id: Any = None, prev_seq_id: Any = None,
                 ts_ms: Any = 0) -> None:
        """Install the venue's pushed snapshot: a full replace that opens a new `seqId` chain."""
        self.bids.clear()
        self.asks.clear()
        self.bid_tokens.clear()
        self.ask_tokens.clear()
        self._apply_levels(bids, side="bid")
        self._apply_levels(asks, side="ask")
        self.seq_id = _int_or_none(seq_id)
        self.prev_seq_id = _int_or_none(prev_seq_id)
        self.has_snapshot = True
        self.stale = False
        self.last_ts_ms = int(_int_or_none(ts_ms) or 0)
        self._trim()

    def on_update(self, bids: list, asks: list, seq_id: Any = None, prev_seq_id: Any = None,
                  checksum: Any = None, ts_ms: Any = 0) -> bool:
        """Apply one incremental update. False means the caller must ask for a fresh snapshot."""
        new_seq, new_prev = _int_or_none(seq_id), _int_or_none(prev_seq_id)
        bid_rows = list(bids or [])
        ask_rows = list(asks or [])

        if not self.has_snapshot:
            # No snapshot yet (still in flight after a subscribe): nothing to apply an update to.
            self.dropped += 1
            return True
        if not bid_rows and not ask_rows and new_seq is not None and new_seq == new_prev:
            # The venue's keepalive: an empty delta whose seqId repeats ("the connection is still
            # active"). It carries no levels, so it must not be mistaken for a gap.
            self.heartbeats += 1
            return True
        if self.stale:
            self.dropped += 1
            return True                                    # waiting for the fresh snapshot
        if not self._applies_to_chain(new_seq, new_prev):
            self._mark_stale("sequence gap (prevSeqId does not match the last seqId)")
            return False

        self._apply_levels(bid_rows, side="bid")
        self._apply_levels(ask_rows, side="ask")
        self._trim()

        verdict = verify_okx_checksum(self.bid_rows(), self.ask_rows(), checksum)
        if verdict is None:
            self.checksum_unavailable += 1
        else:
            self.checksum_checks += 1
            if not verdict:
                # The venue says our top of book is not its top of book: the levels cannot be
                # trusted, so the book goes stale and a fresh snapshot is requested.
                self.checksum_mismatches += 1
                self._mark_stale("checksum mismatch")
                return False

        self.seq_id, self.prev_seq_id = new_seq, new_prev
        self.last_ts_ms = int(_int_or_none(ts_ms) or self.last_ts_ms or 0)
        self.applied += 1
        return True

    def _applies_to_chain(self, new_seq: Optional[int], new_prev: Optional[int]) -> bool:
        """True when this update continues the chain (the venue's reset signal included).

        The venue's own worked example is the contract: normal `prevSeqId=10 → seqId=15`, then a
        reset `prevSeqId=15 → seqId=3`, then normal again `prevSeqId=3 → seqId=5`. So `prevSeqId`
        matches the last `seqId` in *every* case — including the reset — and the reset is signalled
        by `seqId < prevSeqId` alone. A `prevSeqId` that matches nothing we ever saw is a hole.
        """
        if new_prev is None or self.seq_id is None:
            return True                                    # nothing to compare: accept and re-head
        if new_prev != self.seq_id:
            return False                                   # the chain skips one of our messages
        if new_seq is not None and new_seq < new_prev:
            self.seq_resets += 1                           # documented maintenance reset: new head
        return True

    def _apply_levels(self, rows: Any, side: str) -> None:
        book = self.bids if side == "bid" else self.asks
        tokens = self.bid_tokens if side == "bid" else self.ask_tokens
        for row in rows or []:
            lv = _level(row)
            if lv is None:
                self.junk_values += 1
                continue
            if lv.quantity == 0:
                book.pop(lv.price, None)                   # sz "0" = remove the level
                tokens.pop(lv.price, None)
            else:
                book[lv.price] = lv.quantity
                try:
                    tokens[lv.price] = _token(row)
                except (TypeError, IndexError, KeyError):
                    tokens.pop(lv.price, None)

    def _trim(self) -> None:
        """Keep the book at the venue's own push depth so memory cannot creep."""
        for book, tokens, reverse in ((self.bids, self.bid_tokens, True),
                                      (self.asks, self.ask_tokens, False)):
            if len(book) > BOOK_DEPTH:
                order = sorted(book.items(), key=lambda kv: -kv[0]) if reverse \
                    else sorted(book.items(), key=lambda kv: kv[0])
                keep = order[:BOOK_DEPTH]
                dropped = len(book) - len(keep)
                book.clear()
                book.update(dict(keep))
                for price in [p for p in tokens if p not in book]:
                    tokens.pop(price, None)
                self.snapshot_evictions += dropped

    def _mark_stale(self, reason: str) -> None:
        if not self.stale:
            self.gaps += 1
        self.stale = True
        self.seq_id = None                                 # the chain head is meaningless now
        self.prev_seq_id = None
        logger.warning("okx orderbook %s (%s): %s — marked stale, a fresh snapshot is being asked for",
                       self.symbol, self.inst_id, reason)

    def prepare_resync(self) -> None:
        """Drop the local book and wait for a fresh snapshot (the frame on the way is the fix)."""
        self.bids.clear()
        self.asks.clear()
        self.bid_tokens.clear()
        self.ask_tokens.clear()
        self.has_snapshot = False
        self._mark_stale("resync requested")

    # ── output ────────────────────────────────────────────────
    def bid_rows(self) -> list[tuple[str, str]]:
        """Bid tokens, best (highest price) first — the order the checksum is defined over."""
        return [self.bid_tokens[p] for p in sorted(self.bids, reverse=True) if p in self.bid_tokens]

    def ask_rows(self) -> list[tuple[str, str]]:
        """Ask tokens, best (lowest price) first."""
        return [self.ask_tokens[p] for p in sorted(self.asks) if p in self.ask_tokens]

    def to_snapshot(self, levels: int = 0) -> OrderbookSnapshot:
        take = BOOK_DEPTH if levels <= 0 else min(int(levels), BOOK_DEPTH)
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
            "inst_id": self.inst_id,
            "seq_id": self.seq_id,
            "prev_seq_id": self.prev_seq_id,
            "levels": {"bids": len(self.bids), "asks": len(self.asks)},
            "applied": self.applied,
            "dropped": self.dropped,
            "gaps": self.gaps,
            "resyncs": self.resyncs,
            "junk_values": self.junk_values,
            "checksum_checks": self.checksum_checks,
            "checksum_mismatches": self.checksum_mismatches,
            "checksum_unavailable": self.checksum_unavailable,
            "seq_resets": self.seq_resets,
            "heartbeats": self.heartbeats,
        }


def _int_or_none(value: Any) -> Optional[int]:
    """A venue id (`seqId`, `ts` — both strings on this venue) or None when it is not one."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class OkxFeed:
    """Live OKX USDT swaps: `trades` (taker side, no inversion) + `books` (snapshot + updates).

    Interface-compatible with `BybitFeed` and `BinanceFeed` (same callbacks, `get_orderbook`,
    `book_health`) so the engine and the atlas hub cannot tell them apart.
    """

    def __init__(
        self,
        symbols: list[str],
        on_tick: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
        *,
        ws_url: str = OKX_WS_URL,
        rest_url: str = OKX_REST,
        resync_cooldown_s: float = RESYNC_COOLDOWN_S,
    ):
        self.symbols = [str(s).upper() for s in symbols]
        self.on_tick = on_tick
        self.on_orderbook = on_orderbook
        self.ws_url = ws_url
        self.rest_url = str(rest_url).rstrip("/")
        self.resync_cooldown_s = float(resync_cooldown_s)

        #: suite symbol ↔ venue instId, resolved once so every frame routes by string lookup.
        self.inst_of = {s: self.to_venue_symbol(s) for s in self.symbols}
        self.symbol_of_inst = {inst: s for s, inst in self.inst_of.items()}
        self.books: dict[str, OkxBook] = {
            s: OkxBook(s, inst_id=self.inst_of[s]) for s in self.symbols
        }
        self._session: Optional[FeedSession] = None
        self._conn: Any = None
        self._resync_last: dict[str, float] = {}
        self._ts_fallback_warned = False
        self._junk_warned = False
        self._error_codes: set[str] = set()
        self.junk_prints = 0
        self.ticks = 0
        self.pongs = 0
        self.venue_errors = 0
        self._stale_announced: set[str] = set()

    # ── lifecycle ────────────────────────────────────────────
    async def start(self) -> None:
        self._session = FeedSession(
            "okx",
            connect=self._connect,
            on_frame=self._on_frame,
            policy=VENUE_POLICIES["okx"],                  # ping_after_idle: the venue needs it
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
        )
        await self._session.run()

    async def stop(self) -> None:
        if self._session is not None:
            await self._session.stop()

    async def _connect(self):
        # ping_interval=None: this venue's liveness contract is the application-level idle ping the
        # session policy sends (a bare "ping" → a bare "pong", verified live), not a protocol ping.
        conn = await websockets.connect(self.ws_url, ping_interval=None)
        self._conn = conn
        return conn

    async def _on_connected(self, conn) -> None:
        self._ts_fallback_warned = False
        self._resync_last.clear()
        args: list[dict] = []
        for sym in self.symbols:
            inst = self.inst_of[sym]
            args.append({"channel": TRADES_CHANNEL, "instId": inst})
            args.append({"channel": BOOKS_CHANNEL, "instId": inst})
        await conn.send(json.dumps({"op": "subscribe", "args": args}))
        logger.info("OKX feed subscribed: %d channels over %d symbols", len(args), len(self.symbols))
        # Every symbol needs a fresh snapshot on a new socket: `seqId` chains do not survive one.
        # No REST fetch is involved — subscribing *is* how a snapshot is requested here.
        for sym in self.symbols:
            book = self.books[sym]
            book.has_snapshot = False
            book.seq_id = None
            book.prev_seq_id = None
            book.bids.clear()
            book.asks.clear()
            book.bid_tokens.clear()
            book.ask_tokens.clear()
            book.stale = True

    async def _on_disconnected(self, exc: Optional[BaseException]) -> None:
        self._conn = None
        for book in self.books.values():
            book.stale = True
        if exc is not None:
            logger.warning("OKX socket closed: %s", exc)

    # ── frames ───────────────────────────────────────────────
    async def _on_frame(self, raw: Any) -> bool:
        """Parse one frame. False = no market data (acks, pongs, errors): the session's reconnect
        ladder only resets on data, so a venue that acks and then stalls keeps escalating."""
        if isinstance(raw, (bytes, bytearray)):
            # Every channel this adapter subscribes to is JSON on a text frame; the venue's binary
            # (SBE) variants are separate channels, so a binary frame is not something we asked for.
            logger.warning("OKX: unexpected binary frame (%d bytes)", len(raw))
            return False
        if raw == "pong":
            # The heartbeat's answer: the venue replies to a bare text "ping" with a bare "pong",
            # which is not JSON and must not be logged as a parse error.
            self.pongs += 1
            return False
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("OKX: invalid JSON (%s)", str(raw)[:120])
            return False
        if not isinstance(msg, dict):
            return False
        if "event" in msg:
            self._on_event(msg)
            return False
        channel = str((msg.get("arg") or {}).get("channel") or "")
        if channel == TRADES_CHANNEL:
            await self._handle_trade(msg)
            return True
        if channel == BOOKS_CHANNEL:
            await self._handle_books(msg)
            return True
        # anything else is a channel we did not subscribe to
        return False

    def _on_event(self, msg: dict) -> None:
        event = str(msg.get("event") or "")
        if event == "pong":
            self.pongs += 1
        elif event == "error":
            self.venue_errors += 1
            code = str(msg.get("code") or "")
            if code not in self._error_codes:
                # One warning per code, then silence: a rejected subscription that repeats every
                # reconnect would otherwise fill the log with the same line forever.
                self._error_codes.add(code)
                logger.warning("OKX rejected a request (code %s): %s", code, str(msg.get("msg"))[:200])
        else:
            logger.debug("OKX %s event: %s", event, str(msg)[:160])

    async def _handle_trade(self, msg: dict) -> None:
        inst = str((msg.get("arg") or {}).get("instId") or "")
        for row in msg.get("data") or []:
            symbol = self.symbol_of_inst.get(str(row.get("instId") or inst))
            if symbol is None:
                continue
            price, size = _finite(row.get("px")), _finite(row.get("sz"))
            # The venue reports the TAKER side as the string "buy"/"sell" — no maker flag to invert
            # (verified live against the book: 327/343 "buy" prints landed at or above the ask).
            side = {"buy": Side.BUY, "sell": Side.SELL}.get(str(row.get("side") or "").lower())
            if price is None or price <= 0 or size is None or size <= 0 or side is None:
                self.junk_prints += 1
                if not self._junk_warned:
                    self._junk_warned = True
                    logger.warning("OKX trade with an unusable value/price/side dropped: %s",
                                   str(row)[:160])
                continue
            ts = _int_or_none(row.get("ts"))
            if ts is None:
                if not self._ts_fallback_warned:
                    self._ts_fallback_warned = True
                    logger.warning("OKX trade without ts (venue time) — falling back to the local "
                                   "clock; timestamps are loose until the next reconnect")
                ts = int(time.time() * 1000)
            tick = Tick(timestamp_ms=int(ts), price=price, size=size, side=side,
                        trade_id=str(row.get("tradeId") or ""))
            self.ticks += 1
            if self.on_tick:
                await self.on_tick(symbol, tick)

    async def _handle_books(self, msg: dict) -> None:
        inst = str((msg.get("arg") or {}).get("instId") or "")
        symbol = self.symbol_of_inst.get(inst)
        book = self.books.get(symbol) if symbol else None
        if book is None:
            return
        rows = msg.get("data") or []
        row = rows[0] if rows and isinstance(rows[0], dict) else {}   # one row per frame (live: n=1)
        action = str(msg.get("action") or "")
        if action == "snapshot":
            book.snapshot(row.get("bids") or [], row.get("asks") or [],
                          seq_id=row.get("seqId"), prev_seq_id=row.get("prevSeqId"),
                          ts_ms=row.get("ts"))
            book.resyncs += 1
            self._stale_announced.discard(symbol)
            logger.info("OKX orderbook %s (%s): snapshot installed (seqId=%s, %d levels)",
                        symbol, book.inst_id, book.seq_id, len(book.bids) + len(book.asks))
        elif action == "update":
            ok = book.on_update(row.get("bids") or [], row.get("asks") or [],
                                seq_id=row.get("seqId"), prev_seq_id=row.get("prevSeqId"),
                                checksum=row.get("checksum"), ts_ms=row.get("ts"))
            if book.stale and symbol not in self._stale_announced:
                self._stale_announced.add(symbol)
                logger.warning("OKX orderbook %s is stale — a fresh snapshot is being asked for", symbol)
            if not ok:
                await self._resync(symbol)                 # a gap or a mismatch: recover now
            elif book.stale:
                # Stale without this frame being the culprit (a failed checksum earlier, say): keep
                # a snapshot request in flight, rate-limited, until the book is whole again.
                await self._resync(symbol)
            elif symbol in self._stale_announced:
                self._stale_announced.discard(symbol)
                logger.info("OKX orderbook %s recovered after a resync", symbol)
        else:
            logger.debug("OKX books frame with action %r ignored", action)
            return
        if self.on_orderbook and book.has_snapshot:
            await self.on_orderbook(symbol, book.to_snapshot())

    # ── resync ───────────────────────────────────────────────
    async def _resync(self, symbol: str) -> None:
        """Ask for a fresh snapshot the way this venue actually answers one.

        Verified live: a repeated subscribe is only re-acked (no snapshot), while
        unsubscribe→subscribe on the live socket pushes a full 400-level snapshot with
        `prevSeqId=-1`. Two frames on the existing connection is the cheapest thing that genuinely
        recovers, and it leaves the other symbols on the socket untouched.
        """
        now = time.monotonic()
        if now - self._resync_last.get(symbol, 0.0) < self.resync_cooldown_s:
            return
        conn = self._conn
        if conn is None:
            return
        self._resync_last[symbol] = now
        book = self.books.get(symbol)
        if book is not None:
            book.prepare_resync()
        args = [{"channel": BOOKS_CHANNEL, "instId": self.inst_of[symbol]}]
        try:
            await conn.send(json.dumps({"op": "unsubscribe", "args": args}))
            await conn.send(json.dumps({"op": "subscribe", "args": args}))
        except Exception as exc:                            # noqa: BLE001 — a dead socket resyncs
            logger.warning("OKX resubscribe failed for %s: %s", symbol, exc)

    # ── read paths (parity with BybitFeed / BinanceFeed) ─────
    def get_orderbook(self, symbol: str) -> Optional[OrderbookSnapshot]:
        book = self.books.get(str(symbol).upper())
        if book is None or not book.has_snapshot:
            return None
        return book.to_snapshot()

    def book_health(self) -> dict:
        return {
            "venue": "okx",
            "stale": sorted(s for s, b in self.books.items() if b.stale),
            "gaps": sum(b.gaps for b in self.books.values()),
            "dropped_deltas": sum(b.dropped for b in self.books.values()),
            "junk_values": sum(b.junk_values for b in self.books.values()) + self.junk_prints,
            "seq": {s: b.seq_id for s, b in self.books.items()},
            "checksum_mismatches": sum(b.checksum_mismatches for b in self.books.values()),
            "resyncs": sum(b.resyncs for b in self.books.values()),
        }

    def stats(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "venue": "okx",
            "symbols": list(self.books),
            "ticks": self.ticks,
            "junk_prints": self.junk_prints,
            "pongs": self.pongs,
            "venue_errors": self.venue_errors,
            "books": {s: b.health() for s, b in self.books.items()},
        }
        if self._session is not None:
            out["session"] = self._session.stats()
        return out

    # ── symbol mapping (the suite's naming ↔ OKX instIds) ────
    @staticmethod
    def to_venue_symbol(symbol: str) -> str:
        """`BTCUSDT` → `BTC-USDT-SWAP`: this suite's USDT perps → the venue's swap instIds.

        The mapping is total for this suite's instruments (USDT-margined perpetuals, which the venue
        lists as `{base}-USDT-SWAP`). Anything else — an instId already in venue form, a coin-margined
        or dated contract — is passed through unchanged on purpose: an instId the venue refuses is a
        loud error, while a made-up one could silently stream the wrong instrument.
        """
        sym = str(symbol).upper()
        if "-" in sym or not sym.endswith("USDT"):
            return sym
        return f"{sym[:-4]}-USDT-SWAP"

    @staticmethod
    def from_venue_symbol(inst_id: str) -> str:
        """`BTC-USDT-SWAP` → `BTCUSDT` — the inverse, used to route frames and REST rows."""
        inst = str(inst_id).upper()
        if inst.endswith("-SWAP"):
            inst = inst[:-len("-SWAP")]
        return inst.replace("-", "")

    # ── capability probe (public REST; used by /api/control/capabilities) ────
    @staticmethod
    def validate_symbols(symbols: list[str], rest_url: str = OKX_REST) -> dict[str, bool]:
        """Ask the venue which of these symbols exist (USDT-margined perpetual swaps).

        A symbol is `True` only when the venue itself lists it as a live linear/USDT swap — stronger
        evidence than any hardcoded list, and the same shape `bybit_validate` and
        `BinanceFeed.validate_symbols` return so the capability block stays symmetric. Note the
        venue's own currency for "trading" is `state == "live"`, and the listing also carries the
        coin-margined swaps (`BTC-USD-SWAP`), which are not this suite's instruments.
        """
        wanted = {str(s).upper(): False for s in symbols}
        if not wanted:
            return {}
        query = urllib.parse.urlencode({"instType": "SWAP"})
        try:
            req = urllib.request.Request(f"{str(rest_url).rstrip('/')}/api/v5/public/instruments?{query}",
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                             # noqa: BLE001 — reported as "unknown"
            logger.warning("OKX symbol validation failed: %s", exc)
            return wanted
        rows = body.get("data") if isinstance(body, dict) else None
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            symbol = OkxFeed.from_venue_symbol(row.get("instId") or "")
            if symbol in wanted and str(row.get("state")) == "live" \
                    and str(row.get("ctType")) == "linear" and str(row.get("settleCcy")) == "USDT":
                wanted[symbol] = True
        return wanted
