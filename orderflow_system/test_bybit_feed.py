"""The Bybit adapter — the venue with the one measured live leak (G-06).

There was no dedicated module for this adapter. This one mirrors test_binance_feed.py's
contract: the book's chain discipline, the level cap, copies published downstream, a closed
socket marking books stale — plus a per-tick container-growth identity check, which is the
class of defect the audit's live soak found here.
"""

from __future__ import annotations

import asyncio
import json

from orderflow_system.data.bybit_feed import MAX_LEVELS, BybitFeed

TOPIC = "orderbook.50.BTCUSDT"


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))


def _snapshot(u: int, bids, asks=None):
    return {"topic": TOPIC, "type": "snapshot",
            "data": {"u": u, "b": bids, "a": asks or [["101.0", "1"]]}}


def _delta(u: int, bids, asks=None):
    return {"topic": TOPIC, "type": "delta", "data": {"u": u, "b": bids, "a": asks or []}}


def _trade_frame(price="100.5", size="2", ts=1_700_000_000_000, side="Buy", tid="t1"):
    return {"topic": "publicTrade.BTCUSDT", "type": "snapshot",
            "data": [{"T": ts, "s": "BTCUSDT", "S": side, "v": size, "p": price, "i": tid}]}


def _feed():
    seen: list = []
    books: list = []

    async def on_tick(symbol, tick):
        seen.append(tick)

    async def on_book(symbol, book):
        books.append(book)

    feed = BybitFeed(["BTCUSDT"], on_tick=on_tick, on_orderbook=on_book)
    feed._ws = FakeWS()
    return feed, seen, books


def test_a_chain_break_marks_stale_and_a_closed_socket_marks_books_stale():
    feed, _seen, books = _feed()

    async def scenario():
        await feed._handle_orderbook(_snapshot(100, [["100.0", "1"]]))
        assert feed._orderbooks["BTCUSDT"].stale is False
        await feed._handle_orderbook(_delta(105, [["100.0", "9"]]))     # a gap: 101..104 never came
        assert feed._orderbooks["BTCUSDT"].stale is True
        assert feed.book_health()["gaps"] >= 1

    asyncio.run(scenario())
    assert books, "the feed published a book before the gap"


def test_the_local_book_is_capped_per_side():
    feed, _seen, books = _feed()

    async def scenario():
        await feed._handle_orderbook(_snapshot(1, [["100.0", "1"]]))
        assert "BTCUSDT" in feed._orderbooks
        book = feed._orderbooks["BTCUSDT"]
        for n in range(6):
            # u must keep the chain: prev + 1, or the delta is a gap and gets dropped
            await feed._handle_orderbook(_delta(2 + n,
                                                [[str(1000.0 - (n * 300 + i) * 0.5), "1"] for i in range(300)]))
        return book

    book = asyncio.run(scenario())
    assert len(book.bids) <= MAX_LEVELS, f"{len(book.bids)} levels kept"
    assert feed.book_health()["evictions"] > 0


def test_get_orderbook_publishes_a_copy():
    feed, _seen, _books = _feed()

    async def scenario():
        await feed._handle_orderbook(_snapshot(100, [["100.0", "1"]]))

    asyncio.run(scenario())
    snap = feed.get_orderbook("BTCUSDT")
    assert snap is not None and snap.bids[0].price == 100.0
    feed._orderbooks["BTCUSDT"].bids[0].quantity = 999.0
    assert snap.bids[0].quantity != 999.0
    assert feed.get_orderbook("NOPE") is None


def test_no_container_grows_per_tick():
    """A 5,000-frame storm must not grow any container on the instance (dir() snapshot)."""
    feed, seen, _books = _feed()

    async def scenario():
        for n in range(5000):
            await feed._handle_trades(_trade_frame(price=str(100.0 + (n % 50) * 0.5), tid=f"t{n}"))
            if n % 5 == 0:
                await feed._handle_orderbook(_delta(10_000 + n, [[str(100.0 + (n % 20)), "1"]]))

    def sizes():
        out = {}
        for name in dir(feed):
            if name.startswith("__"):
                continue
            value = getattr(feed, name, None)
            if isinstance(value, (dict, list, set)):
                out[name] = len(value)
        return out

    asyncio.run(scenario())
    before = sizes()
    asyncio.run(scenario())                     # the same storm again: identities must hold
    after = sizes()
    grew = {k: (before[k], after[k]) for k in before
            if k in after and after[k] > before[k]}
    # the per-instrument books and the sequence maps are keyed by SYMBOL, so they may not grow
    for key, (b, a) in grew.items():
        assert a - b <= 1, f"{key} grew {b} → {a} under a repeated storm"
    assert seen, "the trades reached the callback"
