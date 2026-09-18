"""Hyperliquid perpetuals — the public feed: trades (taker side) + whole-book l2Book snapshots.

Hyperliquid is the only venue in this package whose L2 channel is a *snapshot* channel: it pushes a
whole 20-level book per frame and no diff, so there is no id chain to stitch and none of the
buffer → validate → replay → resync machine the Binance adapter is built around. What is left of
"is this book trustworthy" is one question — how old is the last snapshot — so the local book is
replaced wholesale on every frame and a documented stale window (default 10 s) flags one that
stopped arriving. Against the live venue, l2Book arrived every 2.6-5.6 s, so that window is about
two missed pushes rather than a stopwatch.

Trades arrive as a *batch*, `{"channel":"trades","data":[{...}, ...]}`: 1-30 prints per frame in a
live check, the first frame after a subscribe being a catch-up of recent prints. `side` is the TAKER
side — "B" is the buy aggressor (it lifts the offer), "A" the seller (it hits the bid) — verified
live by comparing each print against the mid of the nearest book frame: "B" prints sat at or above
that mid, "A" at or below, the drift being the book's own multi-second cadence.

The suite names instruments BTCUSDT; the venue names coins BTC. No name in the venue's whole listing
contains "USD" (verified over all 234 entries), so stripping the suite's quote cannot collide with a
real coin — but the venue's spelling is its own (`kPEPE`), so a known listing wins over the mapping.
The listing is also a *gate*, not a convenience: an unknown coin does not get an error frame, it
drops the socket (verified — subscribing NOPECOIN closed the connection 0.2 s later with no close
frame), and a delisted coin is accepted and then replayed out of a dead backlog (verified — MATIC
acked the subscription and streamed prints from 2024). Subscription is filtered by the venue's meta
listing for exactly those two reasons, and `validate_symbols` answers the capability block from that
same call.

Prices obey the venue's own rule — at most 5 significant figures and at most `6 - szDecimals`
decimals — so a coin's tick is `10 ** -(6 - szDecimals)` and incoming prices are snapped to that
grid (BTC: 0.1, and every BTC price the venue pushed carried exactly one decimal).

Everything public: `wss://api.hyperliquid.xyz/ws` + `https://api.hyperliquid.xyz/info`. No key, no
account. Timestamps are venue ms. Values pass the same `math.isfinite` gate the Bybit feed uses (a
JSON `NaN` would otherwise sail into the aggregates and never raise).

The session loop (reader never cancelled, per-venue heartbeat policy, jittered ladder) is
`data/feed_session.py`: this venue is ping-after-idle and answers a JSON ping with a pong, while its
own ping frames are answered by the library — nothing wraps the read, on purpose.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import websockets

from orderflow_system.data.feed_session import FeedSession, VENUE_POLICIES
from orderflow_system.data.models import Tick, Side, OrderbookSnapshot, OrderbookLevel

logger = logging.getLogger(__name__)

HYPERLIQUID_WS_URL = "wss://api.hyperliquid.xyz/ws"       # dynamic subscribe, no coin in the URL
HYPERLIQUID_REST = "https://api.hyperliquid.xyz/info"     # one endpoint, POST {"type": ...}

#: Quote suffixes the suite's instruments carry and the venue's coins never do (no listed name
#: contains "USD"), so stripping one is unambiguous. Longest first — USDT before USD.
QUOTE_SUFFIXES = ("USDT", "USDC", "USD")

#: The venue's l2Book depth: 20 levels per side, replaced whole on each push. A cap, not a policy —
#: nothing deeper is ever sent, so anything past it is a malformed frame, not a deeper book.
MAX_LEVELS = 20

#: The venue's price rule: at most 5 significant figures and at most MAX_DECIMALS - szDecimals
#: decimals. The listed coins carry szDecimals 0..5 (verified over the live meta), so a coin's
#: smallest price step is between 0.1 and 1e-6.
MAX_DECIMALS = 6

#: How long the local book may go without an l2Book push before it is marked stale. The venue's own
#: cadence was 2.6-5.6 s in a live check, so 10 s is about two missed pushes, not a stopwatch.
STALE_AFTER_S = 10.0

#: The venue's taker-side letters — verified live against the book mid (see the module docstring).
TAKER_SIDES = {"B": Side.BUY, "A": Side.SELL}


def _finite(value: Any) -> Optional[float]:
    """A venue number that is safe to carry, or None (see the Bybit feed — same gate)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ts_ms(value: Any) -> Optional[int]:
    """A venue millisecond stamp as int, or None when it is not a usable number."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _level(entry: Any) -> Optional[OrderbookLevel]:
    """One venue level `{"px": "...", "sz": "...", "n": 3}` → OrderbookLevel, or None.

    Unlike Bybit's and Binance's `[price, qty]` tuples the level is an object here; the venue's `n`
    (how many orders sit at the level) is deliberately not carried — nothing in this suite reads it.
    """
    try:
        price, qty = _finite(entry.get("px")), _finite(entry.get("sz"))
    except (AttributeError, TypeError):
        return None
    if price is None or qty is None or price <= 0 or qty <= 0:
        return None
    return OrderbookLevel(price=price, quantity=qty)


def _trade_items(payload: Any) -> list[dict]:
    """The trades payload as a list of prints. It is a batch here; a lone dict is tolerated."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return [payload] if isinstance(payload, dict) else []


@dataclass
class HyperliquidBook:
    """One symbol's local book: the venue's last l2Book snapshot, replaced wholesale.

    Pure and synchronous on purpose — the frame handler only ever calls `replace()` and `refresh()`,
    so the age rules are testable without a socket. There is no sequence to keep (the venue sends no
    id with the book) and no diff to apply: `replace()` is the whole state transition, which is
    exactly what a snapshot channel leaves to the client.
    """

    symbol: str
    coin: str = ""
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    has_snapshot: bool = False
    stale: bool = True
    last_ts_ms: int = 0
    last_update_s: float = 0.0                 # local monotonic clock at the last replace()
    # counters a status line can quote
    updates: int = 0
    junk_values: int = 0
    stale_marks: int = 0

    # ── ingest ────────────────────────────────────────────────
    def replace(self, levels: Any, ts_ms: int = 0, now: Optional[float] = None,
                decimals: Optional[int] = None) -> int:
        """Install a whole-book snapshot. Returns how many levels the book holds (0 = refused).

        `decimals` is the coin's price precision (see the feed's `tick_size`) and snaps every level
        onto the venue's tick grid; None leaves the venue's own digits untouched, which is what the
        book does while the listing has not been read yet.
        """
        if not isinstance(levels, list) or len(levels) < 2:
            self.junk_values += 1
            return 0
        bids, asks = self._parse(levels[0], decimals), self._parse(levels[1], decimals)
        if not bids and not asks:
            # The venue always sends both sides of a live book (20/20 in a live check): an empty
            # payload is a malformed frame, not a market without liquidity, and installing it
            # would throw away a good book in favour of nothing.
            self.junk_values += 1
            return 0
        self.bids = {lv.price: lv.quantity for lv in sorted(bids, key=lambda lv: -lv.price)[:MAX_LEVELS]}
        self.asks = {lv.price: lv.quantity for lv in sorted(asks, key=lambda lv: lv.price)[:MAX_LEVELS]}
        self.has_snapshot = True
        self.stale = False
        self.updates += 1
        self.last_ts_ms = int(ts_ms or 0)
        self.last_update_s = time.monotonic() if now is None else float(now)
        return len(self.bids) + len(self.asks)

    def _parse(self, rows: Any, decimals: Optional[int] = None) -> list[OrderbookLevel]:
        """One side of a snapshot, with unusable levels refused and counted (never raised)."""
        if not isinstance(rows, list):
            self.junk_values += 1
            return []
        out = []
        for row in rows:
            level = _level(row)
            if level is None:
                self.junk_values += 1
                continue
            if decimals is not None:
                level = OrderbookLevel(price=round(level.price, decimals), quantity=level.quantity)
            out.append(level)
        return out

    def refresh(self, stale_after_s: float, now: float) -> bool:
        """Recompute the book's age against the window. True only when it *became* stale.

        Returns the transition rather than the state so the caller can announce it once: a book
        that stays stale must not log on every frame.
        """
        if not self.has_snapshot or self.stale:
            return False                          # never seeded, or already known to be stale
        if now - self.last_update_s <= stale_after_s:
            return False
        self.stale = True
        self.stale_marks += 1
        return True

    def mark_stale(self, reason: str = "") -> None:
        """Flag the book without a window (the socket went away: the venue pushes, so silence)."""
        if not self.stale:
            self.stale_marks += 1
        self.stale = True
        if reason:
            logger.warning("hyperliquid orderbook %s: %s — marked stale", self.symbol, reason)

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
            "coin": self.coin,
            "stale": self.stale,
            "has_snapshot": self.has_snapshot,
            "levels": {"bids": len(self.bids), "asks": len(self.asks)},
            "updates": self.updates,
            "stale_marks": self.stale_marks,
            "junk_values": self.junk_values,
            "last_update_ms": self.last_ts_ms,
        }


class HyperliquidFeed:
    """Live Hyperliquid perpetuals: trades (taker side) + whole-book l2Book snapshots.

    Interface-compatible with `BybitFeed` and `BinanceFeed` (same callbacks, `get_orderbook`,
    `book_health`, `stats`) so the engine and the atlas hub cannot tell them apart.
    """

    def __init__(
        self,
        symbols: list[str],
        on_tick: Optional[Callable] = None,
        on_orderbook: Optional[Callable] = None,
        *,
        stale_after_s: float = STALE_AFTER_S,
        rest_url: str = HYPERLIQUID_REST,
        ws_url: str = HYPERLIQUID_WS_URL,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.symbols = [str(s).upper() for s in symbols]
        self.on_tick = on_tick
        self.on_orderbook = on_orderbook
        self.stale_after_s = float(stale_after_s)
        self.rest_url = str(rest_url)
        self.ws_url = ws_url
        #: Injected monotonic clock: book age is a *virtual* time contract, so tests drive the stale
        #: window without waiting on real seconds (the session's heartbeat does the same).
        self._clock = clock

        # Books are keyed by the suite's instrument; the wire speaks coins (see the module docstring).
        self.books: dict[str, HyperliquidBook] = {
            s: HyperliquidBook(s, coin=self.to_venue_symbol(s)) for s in self.symbols}
        self._session: Optional[FeedSession] = None
        self._conn: Any = None
        self._universe: dict[str, int] = {}       # listed coin -> szDecimals
        self._delisted: set[str] = set()
        self._coin_symbols: dict[str, str] = {}   # coin -> the suite symbol that subscribed it
        self.ticks = 0
        self.junk_prints = 0
        self._ts_fallback_warned = False
        self._junk_warned = False
        self._unknown_channel_warned = False
        self._stale_announced: set[str] = set()

    # ── lifecycle ────────────────────────────────────────────
    async def start(self) -> None:
        # No asyncio.wait_for wraps the read: the venue pings us and the library answers by itself.
        self._session = FeedSession(
            "hyperliquid",
            connect=self._connect,
            on_frame=self._on_frame,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            policy=VENUE_POLICIES["hyperliquid"],
            ping_payload=json.dumps({"method": "ping"}),
        )
        await self._session.run()

    async def stop(self) -> None:
        # Nothing else is in flight: the venue pushes the book, so unlike the Binance adapter there
        # are no snapshot tasks to cancel here.
        if self._session is not None:
            await self._session.stop()

    async def _connect(self):
        # ping_interval=None: this venue answers the library's protocol pings too (verified), but the
        # liveness contract for this feed is the session's ping-after-idle JSON ping — liveness has
        # exactly one owner, and a second one would kill a socket the session considers healthy.
        conn = await websockets.connect(self.ws_url, ping_interval=None)
        self._conn = conn
        return conn

    async def _on_connected(self, conn) -> None:
        self._ts_fallback_warned = False           # a fresh connection may say it again
        self._junk_warned = False
        self._unknown_channel_warned = False
        # The listing first: it decides which symbols may be named at all. A REST hiccup is not
        # fatal — the mapping alone still subscribes, and the next reconnect re-reads the listing.
        await self._load_universe()
        pairs = self._wire_coins()
        for _symbol, coin in pairs:
            for subscription in ({"type": "trades", "coin": coin}, {"type": "l2Book", "coin": coin}):
                await conn.send(json.dumps({"method": "subscribe", "subscription": subscription}))
        logger.info("Hyperliquid feed subscribed: %d streams over %d of %d symbols",
                    2 * len(pairs), len(pairs), len(self.symbols))

    async def _on_disconnected(self, exc: Optional[BaseException]) -> None:
        self._conn = None
        for book in self.books.values():
            book.mark_stale()
        if exc is not None:
            logger.warning("Hyperliquid socket closed: %s", exc)

    # ── the venue's listing ──────────────────────────────────
    async def _load_universe(self) -> None:
        """Read the venue's meta listing: which coins exist, their size decimals, which are dead."""
        try:
            meta = await asyncio.to_thread(self._fetch_meta)
        except Exception as exc:                  # noqa: BLE001 — network is the venue's
            logger.warning("Hyperliquid meta fetch failed (%s) — subscribing by the symbol mapping "
                           "alone, so a delisted coin cannot be filtered out this time", exc)
            return
        universe: dict[str, int] = {}
        delisted: set[str] = set()
        for entry in (meta.get("universe") if isinstance(meta, dict) else None) or []:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            name = str(entry["name"])
            if entry.get("isDelisted"):
                delisted.add(name)
                continue
            try:
                universe[name] = int(entry.get("szDecimals") or 0)
            except (TypeError, ValueError):
                continue
        self._universe, self._delisted = universe, delisted
        logger.info("Hyperliquid meta: %d listed coins, %d delisted", len(universe), len(delisted))

    def _fetch_meta(self) -> dict:
        payload = json.dumps({"type": "meta"}).encode("utf-8")
        req = urllib.request.Request(
            self.rest_url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "OrderFlow-Analysis-Pro"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _wire_coins(self) -> list[tuple[str, str]]:
        """The (suite symbol, coin) pairs this socket may subscribe — the listing is the gate."""
        pairs: list[tuple[str, str]] = []
        claimed: dict[str, str] = {}
        self._coin_symbols = {}
        for symbol in self.symbols:
            coin = self.to_venue_symbol(symbol, universe=self._universe or None)
            if not coin:
                logger.warning("Hyperliquid: %s has no coin on this venue — not subscribing it",
                               symbol)
                continue
            if coin in self._delisted:
                # Verified: the venue ACCEPTS a delisted coin and then replays its dead backlog
                # (MATIC acked the subscription and streamed 2024 prints), so the listing is the
                # only thing standing between the engine and a dead instrument.
                logger.warning("Hyperliquid: %s is delisted on this venue — not subscribing it", coin)
                continue
            if self._universe and coin not in self._universe:
                logger.warning("Hyperliquid: %s is not in the venue listing — not subscribing it",
                               coin)
                continue
            if coin in claimed:
                # One coin, one subscription: two instruments that map to the same coin (BTCUSDT
                # and BTCUSD) would push every print twice into the footprint.
                logger.warning("Hyperliquid: %s and %s are both coin %s — subscribing only %s",
                               claimed[coin], symbol, coin, claimed[coin])
                continue
            claimed[coin] = symbol
            self._coin_symbols[coin] = symbol
            self.books[symbol].coin = coin
            pairs.append((symbol, coin))
        return pairs

    # ── frames ───────────────────────────────────────────────
    async def _on_frame(self, raw: Any) -> None:
        # Age the books before dispatching: a book that stopped pushing must be flagged the moment
        # ANY frame arrives, which is what makes a silent l2Book visible while trades keep flowing.
        self._refresh_stale()
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Hyperliquid: invalid JSON (%s)", str(raw)[:120])
            return False
        if not isinstance(msg, dict):
            return False
        channel = msg.get("channel")
        if channel == "trades":
            await self._handle_trades(msg.get("data"))
        elif channel == "l2Book":
            data = msg.get("data")
            await self._handle_book(data if isinstance(data, dict) else {})
        elif channel in ("subscriptionResponse", "pong"):
            return False                           # acks, and the answer to the session's JSON ping
        elif not self._unknown_channel_warned:
            # One warning per connection, then silence: an unhandled channel is worth knowing about
            # once, but a venue that starts pushing something new must not become a log flood.
            self._unknown_channel_warned = True
            logger.warning("Hyperliquid: unexpected channel %r — ignoring it from now on", channel)
            return False

    async def _handle_trades(self, payload: Any) -> None:
        for item in _trade_items(payload):
            coin = str(item.get("coin") or "")
            symbol = self._coin_symbols.get(coin)
            if symbol is None:
                continue                           # a coin this feed never subscribed
            price, size = _finite(item.get("px")), _finite(item.get("sz"))
            # `side` is a gate of its own: the field is the AGGRESSOR, and guessing one would flip
            # delta, footprint polarity and CVD — a wrong side is worse than a dropped print.
            side = TAKER_SIDES.get(str(item.get("side") or ""))
            if price is None or price <= 0 or size is None or size <= 0 or side is None:
                self.junk_prints += 1
                self._warn_junk(coin, item)
                continue
            ts = _ts_ms(item.get("time"))
            if ts is None:
                if not self._ts_fallback_warned:
                    self._ts_fallback_warned = True
                    logger.warning("Hyperliquid trade without time (venue time) — falling back to "
                                   "the local clock; timestamps are loose until the next reconnect")
                ts = int(time.time() * 1000)
            tick = Tick(timestamp_ms=ts, price=self._round_price(coin, price), size=size, side=side,
                        trade_id=str(item.get("tid") or ""))
            self.ticks += 1
            if self.on_tick:
                await self.on_tick(symbol, tick)

    async def _handle_book(self, data: dict) -> None:
        coin = str(data.get("coin") or "")
        symbol = self._coin_symbols.get(coin)
        book = self.books.get(symbol) if symbol else None
        if book is None:
            return
        accepted = book.replace(data.get("levels"), _ts_ms(data.get("time")) or 0, self._clock(),
                               self._price_decimals(coin))
        if accepted and symbol in self._stale_announced:
            self._stale_announced.discard(symbol)
            logger.info("Hyperliquid orderbook %s: live again on a fresh snapshot", symbol)
        if self.on_orderbook and book.has_snapshot:
            await self.on_orderbook(symbol, book.to_snapshot())

    def _warn_junk(self, coin: str, item: dict) -> None:
        """Say it once per connection, then count in silence (a bad socket must not flood the log)."""
        if self._junk_warned:
            return
        self._junk_warned = True
        logger.warning("Hyperliquid: refusing a malformed print on %s (%s) — dropped and counted "
                       "from now on", coin, str(item)[:160])

    def _refresh_stale(self) -> None:
        """Age every book against the window — on each frame and on every read path.

        A snapshot channel's book has no sequence to check, so age is the only integrity signal it
        has; flagging it here (not only when a book frame arrives) is what makes a stopped book
        visible while the socket itself is still alive.
        """
        now = self._clock()
        for symbol, book in self.books.items():
            if book.refresh(self.stale_after_s, now):
                logger.warning("Hyperliquid orderbook %s: no l2Book update for over %.1fs — marked "
                               "stale", symbol, self.stale_after_s)
                self._stale_announced.add(symbol)

    # ── price grid (the venue's own rule) ────────────────────
    @staticmethod
    def price_decimals(sz_decimals: Any) -> int:
        """How many decimals a price on this coin may carry: MAX_DECIMALS - szDecimals, clamped.

        The listed coins carry szDecimals 0..5 (verified over the live meta), so the clamp never
        bites today — it exists so a future listing cannot turn the venue's rule into a negative
        decimal count.
        """
        try:
            decimals = int(sz_decimals)
        except (TypeError, ValueError):
            return 0
        return max(0, min(MAX_DECIMALS - decimals, MAX_DECIMALS))

    @staticmethod
    def tick_size(sz_decimals: Any) -> float:
        """The smallest price step this coin can be quoted in: `10 ** -(6 - szDecimals)`.

        BTC lists szDecimals 5, so its tick is 0.1 — and every BTC price the venue pushed in a live
        check carried exactly one decimal (MATIC, szDecimals 1, carried five).
        """
        return 10.0 ** -HyperliquidFeed.price_decimals(sz_decimals)

    def _price_decimals(self, coin: str) -> Optional[int]:
        """The coin's price precision from the listing, or None while the listing is unknown."""
        sz_decimals = self._universe.get(coin)
        return None if sz_decimals is None else self.price_decimals(sz_decimals)

    def _round_price(self, coin: str, price: float) -> float:
        """Snap an incoming price onto the coin's tick grid (see `tick_size`).

        The venue rounds what it sends, so this is lossless for a well-formed print and normalizes a
        malformed one instead of letting a phantom level into the footprint aggregates.
        """
        decimals = self._price_decimals(coin)
        return price if decimals is None else round(price, decimals)

    # ── symbol mapping (the suite's instruments are not the venue's coin names) ───
    @staticmethod
    def to_venue_symbol(symbol: str, universe: Optional[Any] = None) -> str:
        """`BTCUSDT` → `BTC`: the venue's coin for a suite instrument, or "" when it has none.

        The venue's coins carry no quote suffix, so stripping the suite's quote cannot collide with
        a real coin. `universe` (any container of the venue's names) is consulted when it is known,
        because the venue's spelling is its own: `KPEPEUSDT` must become `kPEPE`, not `KPEPE`.
        """
        text = str(symbol or "").strip().upper()
        if not text:
            return ""
        for suffix in QUOTE_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                break
        if not text:
            return ""
        if universe:
            if text in universe:
                return text
            for name in universe:
                if str(name).upper() == text:
                    return str(name)
        return text

    # ── read paths (parity with BybitFeed) ───────────────────
    def get_orderbook(self, symbol: str) -> Optional[OrderbookSnapshot]:
        """The last snapshot for an instrument — by suite symbol (`BTCUSDT`) or by coin (`BTC`)."""
        self._refresh_stale()
        text = str(symbol)
        book = self.books.get(text.upper())
        if book is None:
            book = self.books.get(self._coin_symbols.get(text) or "")   # the wire speaks coins
        if book is None or not book.has_snapshot:
            return None
        return book.to_snapshot()

    def book_health(self) -> dict:
        """Book age per symbol — a snapshot venue has no sequence to report, so age is the truth.

        There is deliberately no `seq` key: the venue publishes no id with the book, so the Binance
        adapter's chain head has no counterpart here. `updates` and `last_update_ms` are what can be
        stated honestly, and `stale` is recomputed against the window before it is reported.
        """
        self._refresh_stale()
        return {
            "venue": "hyperliquid",
            "stale": sorted(s for s, b in self.books.items() if b.stale),
            "updates": {s: b.updates for s, b in self.books.items()},
            "last_update_ms": {s: b.last_ts_ms for s, b in self.books.items()},
            "stale_marks": sum(b.stale_marks for b in self.books.values()),
            "junk_values": sum(b.junk_values for b in self.books.values()) + self.junk_prints,
            "coins": {s: b.coin for s, b in self.books.items()},
        }

    def stats(self) -> dict[str, Any]:
        self._refresh_stale()                      # stats() is a read path: report the age, not a lag
        out: dict[str, Any] = {
            "venue": "hyperliquid",
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
    def validate_symbols(symbols: list[str], rest_url: str = HYPERLIQUID_REST) -> dict[str, bool]:
        """Ask the venue's meta listing which of these symbols actually trade here.

        A symbol is `True` only when the venue lists its coin and does not mark it delisted. The
        listing is the only honest gate on this venue: the websocket accepts a delisted coin and
        then replays its dead backlog, and it answers an unknown one by dropping the socket — so
        neither a subscription ack nor a live print proves a symbol is tradable. Same shape
        `binance_validate` returns, so the capability block stays symmetric.
        """
        wanted = {str(s).upper(): False for s in symbols}
        if not wanted:
            return {}
        try:
            payload = json.dumps({"type": "meta"}).encode("utf-8")
            req = urllib.request.Request(
                rest_url, data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "OrderFlow-Analysis-Pro"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                meta = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                   # noqa: BLE001 — reported as "unknown"
            logger.warning("Hyperliquid symbol validation failed: %s", exc)
            return wanted
        listed = {str(entry["name"]): entry for entry in (meta.get("universe") or []) or []
                  if isinstance(entry, dict) and entry.get("name")}
        for symbol in wanted:
            coin = HyperliquidFeed.to_venue_symbol(symbol, universe=listed)
            entry = listed.get(coin)
            wanted[symbol] = bool(entry) and not entry.get("isDelisted")
        return wanted
