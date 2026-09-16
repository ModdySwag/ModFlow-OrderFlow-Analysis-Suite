"""Binance USDⓈ-M futures feed — the depth chain, the trade side convention, and the gates.

The chain rules are the whole point of this adapter (Binance publishes depth *diffs* only), so the
tests drive `BinanceDepthBook` directly with the venue's real message shapes, then the feed end to
end with a fake socket and a fake REST snapshot.
"""

from __future__ import annotations

import asyncio
import json

from orderflow_system.data.binance_feed import (
    MAX_LEVELS,
    MAX_PENDING_DIFFS,
    BinanceDepthBook,
    BinanceFeed,
)
from orderflow_system.data.models import Side
from orderflow_system.data.feed_session import VENUE_POLICIES


def _trade(price="100.5", qty="2", ts=1_700_000_000_000, maker=False, symbol="BTCUSDT", tid=7):
    return {"e": "aggTrade", "s": symbol, "a": tid, "p": price, "q": qty, "T": ts, "m": maker}


def _depth(first, final, prev, bids=None, asks=None, symbol="BTCUSDT", ts=1_700_000_000_000):
    return {"e": "depthUpdate", "s": symbol, "U": first, "u": final, "pu": prev,
            "b": bids if bids is not None else [], "a": asks if asks is not None else [], "T": ts}


def _trade_stream(price="100.5", qty="2", ts=1_700_000_000_000, maker=False, symbol="BTCUSDT", tid=42):
    """The futures venue's per-fill shape (`@trade`): id field `t`, event `trade`."""
    return {"e": "trade", "E": ts, "T": ts, "s": symbol, "t": tid,
            "p": price, "q": qty, "X": "MARKET", "m": maker}


# ── the depth chain ───────────────────────────────────────────────────────────────────────────
def test_snapshot_then_diffs_apply_in_chain_order():
    book = BinanceDepthBook("BTCUSDT")
    assert book.stale is True and book.has_snapshot is False

    book.snapshot(100, [[99.5, 3], [99.0, 1]], [[100.5, 2]])
    assert book.stale is False and book.last_update_id == 100
    assert book.to_snapshot().best_bid == 99.5

    assert book.on_diff(101, 105, 100, bids=[[99.7, 4]], asks=[[100.6, 1]]) is True
    assert book.to_snapshot().best_bid == 99.7
    assert book.on_diff(106, 110, 105, bids=[[99.5, 0]], asks=[]) is True      # qty 0 removes
    assert [lv.price for lv in book.to_snapshot().bids] == [99.7, 99.0]
    assert book.last_update_id == 110 and book.applied == 2


def test_the_first_event_after_a_snapshot_must_straddle_it():
    book = BinanceDepthBook("BTCUSDT")
    book.snapshot(100, [[99.5, 3]], [[100.5, 2]])
    # U=105 does not cover last_update_id + 1 (101): the snapshot is not the chain's head
    assert book.on_diff(105, 108, 103, bids=[[99.9, 1]]) is False
    assert book.stale is True and book.gaps == 1
    assert book.pending == book.pending and len(book.pending) == 0


def test_a_stale_event_is_dropped_not_applied():
    book = BinanceDepthBook("BTCUSDT")
    book.snapshot(100, [[99.5, 3]], [[100.5, 2]])
    assert book.on_diff(95, 98, 94, bids=[[99.9, 1]]) is True      # duplicate/late: ignored
    assert book.dropped == 1 and book.applied == 0
    assert book.to_snapshot().best_bid == 99.5


def test_a_chain_break_marks_stale_and_calls_for_a_resync():
    book = BinanceDepthBook("BTCUSDT")
    book.snapshot(100, [[99.5, 3]], [[100.5, 2]])
    assert book.on_diff(101, 105, 100, bids=[[99.7, 1]]) is True
    # pu must equal the previous u (105): 130 is a hole
    assert book.on_diff(120, 130, 119, bids=[[99.8, 1]]) is False
    assert book.stale is True
    assert book.gaps == 1
    # once stale, further diffs are dropped until a snapshot lands
    assert book.on_diff(131, 132, 130, bids=[[99.9, 1]]) is True
    assert book.to_snapshot().stale is True


def test_diffs_before_a_snapshot_buffer_then_replay():
    book = BinanceDepthBook("BTCUSDT")
    # diffs arrive while the REST snapshot is still in flight
    for first, final in ((101, 105), (106, 110)):
        assert book.on_diff(first, final, first - 1, bids=[[99.5 + final / 1000, 1]]) is True
    assert len(book.pending) == 2 and book.applied == 0

    replayed = book.snapshot(100, [[99.5, 3]], [[100.5, 2]])
    assert replayed == 2
    assert book.applied == 2 and book.last_update_id == 110
    assert len(book.pending) == 0
    assert book.stale is False


def test_the_pending_buffer_is_capped():
    book = BinanceDepthBook("BTCUSDT")
    for i in range(MAX_PENDING_DIFFS + 50):
        book.on_diff(1000 + i, 1000 + i, 999 + i, bids=[[99.0, 1]])
    assert len(book.pending) == MAX_PENDING_DIFFS, "the buffer must be a cap, not a queue"


def test_the_book_is_trimmed_at_the_level_cap():
    book = BinanceDepthBook("BTCUSDT")
    bids = [[100.0 - i * 0.01, 1] for i in range(MAX_LEVELS + 200)]
    book.snapshot(1, bids, [[100.5, 1]])
    assert len(book.bids) == MAX_LEVELS
    assert book.snapshot_evictions >= 200


# ── the feed ──────────────────────────────────────────────────────────────────────────────────
async def _run_feed(frames, *, fetch=None, symbols=("BTCUSDT",), snapshot_cooldown_s=0.0):
    ticks = []
    books = []

    class FakeWS:
        def __init__(self):
            self.sent = []

        async def send(self, payload):
            self.sent.append(payload)

        async def close(self):
            pass

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not frames:
                await asyncio.sleep(5)
                raise StopAsyncIteration
            return frames.pop(0)

    ws = FakeWS()

    async def connect():
        return ws

    async def on_tick(symbol, tick):
        ticks.append((symbol, tick))

    async def on_book(symbol, book):
        books.append((symbol, book))

    feed = BinanceFeed(symbols=list(symbols), on_tick=on_tick, on_orderbook=on_book,
                       snapshot_cooldown_s=snapshot_cooldown_s)

    def default_fetch(symbol):                                   # no network in tests
        return {"lastUpdateId": 100, "E": 1_700_000_000_000,
                "bids": [[99.5, 3]], "asks": [[100.5, 2]]}

    feed._fetch_snapshot = fetch or default_fetch
    session = await feed_start(feed, connect)
    return feed, ws, ticks, books, session


async def feed_start(feed, connect):
    """Drive the session for a moment without waiting on real sockets."""
    import orderflow_system.data.feed_session as fs

    session = fs.FeedSession("binance", connect, feed._on_frame,
                             on_connected=feed._on_connected,
                             on_disconnected=feed._on_disconnected,
                             policy=VENUE_POLICIES["binance"], heartbeat_tick_s=0.05)
    feed._session = session
    feed._conn = await connect()
    await feed._on_connected(feed._conn)
    task = asyncio.create_task(session.run())
    for _ in range(200):
        await asyncio.sleep(0.01)
        if not task.done() and feed.books["BTCUSDT"].has_snapshot:
            break
    return session


def test_the_feed_subscribes_trades_and_depth_for_every_symbol():
    async def main():
        feed, ws, _ticks, _books, session = await _run_feed([])
        await session.stop()
        params = json.loads(ws.sent[0])["params"]
        assert "btcusdt@trade" in params and "btcusdt@depth@100ms" in params
        assert not any("aggTrade" in p for p in params), \
            "the futures venue does not serve @aggTrade — subscribing it is dead weight"
        return feed

    feed = asyncio.run(main())
    assert feed.symbols == ["BTCUSDT"]


def test_the_feed_installs_a_snapshot_on_connect_and_does_not_report_an_empty_book():
    async def main():
        feed, _ws, _ticks, books, session = await _run_feed([])
        await asyncio.sleep(0)
        await session.stop()
        return feed, books

    feed, books = asyncio.run(main())
    assert books, "a snapshot on connect must be published (the heatmap needs a seed)"
    symbol, snapshot = books[-1]
    assert symbol == "BTCUSDT"
    assert snapshot.stale is False
    assert snapshot.best_bid == 99.5 and snapshot.best_ask == 100.5


def test_a_gap_on_the_wire_triggers_a_second_snapshot_and_recovers():
    calls = {"n": 0}

    def fetch(symbol):
        calls["n"] += 1
        return {"lastUpdateId": 200 if calls["n"] > 1 else 100, "E": 1_700_000_000_000,
                "bids": [[99.5, 3]], "asks": [[100.5, 2]]}

    async def main():
        frames = [
            json.dumps(_depth(101, 105, 100, bids=[[99.6, 2]])),      # good
            json.dumps(_depth(150, 160, 149, bids=[[99.8, 2]])),      # gap (pu 149 ≠ 105)
        ]
        feed, _ws, _ticks, _books, session = await _run_feed(frames, fetch=fetch)
        for _ in range(300):
            await asyncio.sleep(0.01)
            if calls["n"] >= 2 and not feed.books["BTCUSDT"].stale:
                break
        health = feed.books["BTCUSDT"].health()
        await session.stop()
        return feed, health

    feed, health = asyncio.run(main())
    assert calls["n"] >= 2, "a chain break must fetch a fresh snapshot"
    assert health["gaps"] >= 1
    assert health["stale"] is False, "the resynced book must be live again"
    assert health["last_update_id"] == 200


def test_a_closed_socket_marks_every_book_stale():
    """A socket that goes away invalidates the books: the levels are the last known-good state,
    not what the venue shows now, and the flag must travel with the snapshot."""

    async def main():
        feed, _ws, _ticks, _books, session = await _run_feed([])
        assert feed.books["BTCUSDT"].stale is False
        await feed._on_disconnected(ConnectionResetError("closed"))
        health = feed.books["BTCUSDT"].health()
        snap = feed.books["BTCUSDT"].to_snapshot()
        await session.stop()
        return health, snap

    health, snap = asyncio.run(main())
    assert health["stale"] is True
    assert snap.stale is True, "the published snapshot must carry the stale flag"


def test_the_feed_parses_trades_with_the_taker_side_convention():
    async def main():
        frames = [
            json.dumps(_trade(price="100.5", qty="2", maker=False)),   # buyer aggressor
            json.dumps(_trade(price="100.4", qty="1", maker=True, tid=8)),   # seller aggressor
            json.dumps(_trade_stream(price="100.3", qty="3", maker=False, tid=99)),  # futures @trade
        ]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        for _ in range(100):
            await asyncio.sleep(0)
            if len(ticks) >= 3:
                break
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert len(ticks) == 3
    (sym1, t1), (sym2, t2), (sym3, t3) = ticks
    assert sym1 == sym2 == sym3 == "BTCUSDT"
    assert t1.side is Side.BUY and t2.side is Side.SELL and t3.side is Side.BUY
    assert t1.price == 100.5 and t1.size == 2.0 and t1.trade_id == "7"
    assert t2.price == 100.4 and t2.trade_id == "8"
    assert t3.price == 100.3 and t3.trade_id == "99", "the futures `t` id must be carried"


def test_junk_prints_are_dropped_and_counted():
    async def main():
        frames = [
            json.dumps(_trade(price="NaN")),
            json.dumps(_trade(price="-1")),
            json.dumps(_trade(qty="-2")),
            json.dumps(_trade()),                    # the only good one
        ]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        for _ in range(100):
            await asyncio.sleep(0)
            if len(ticks) >= 1:
                break
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert len(ticks) == 1, f"only the good print may pass: {ticks}"
    assert feed.junk_prints == 3
    assert feed.book_health()["junk_values"] >= 3


def test_book_health_and_stats_carry_the_venue_shape():
    feed = BinanceFeed(symbols=["BTCUSDT", "ETHUSDT"])
    health = feed.book_health()
    assert health["venue"] == "binance"
    assert set(health) >= {"stale", "gaps", "dropped_deltas", "junk_values", "seq"}
    assert sorted(health["stale"]) == ["BTCUSDT", "ETHUSDT"]      # nothing seeded yet
    stats = feed.stats()
    assert stats["venue"] == "binance" and stats["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert "books" in stats
    assert BinanceFeed(symbols=["BTCUSDT"]).get_orderbook("BTCUSDT") is None


def test_the_adapter_uses_the_server_driven_policy():
    policy = VENUE_POLICIES["binance"]
    assert policy.mode == "server_driven"
    assert policy.silence_budget_s >= 240.0, \
        "a 60 s budget would kill a healthy Binance perps socket (it can be legitimately quiet)"


def test_validate_symbols_reads_the_venue_listing(monkeypatch):
    import orderflow_system.data.binance_feed as mod

    payload = {"symbols": [
        {"symbol": "BTCUSDT", "contractType": "PERPETUAL", "status": "TRADING"},
        {"symbol": "DELISTEDUSDT", "contractType": "PERPETUAL", "status": "SETTLING"},
        {"symbol": "ETHUSDT", "contractType": "CURRENT_QUARTER", "status": "TRADING"},
    ]}

    class Resp:
        def __init__(self, body):
            self._body = json.dumps(body).encode()

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda req, timeout=0: Resp(payload))
    got = BinanceFeed.validate_symbols(["BTCUSDT", "DELISTEDUSDT", "NOPEUSDT", "ETHUSDT"])
    assert got == {"BTCUSDT": True, "DELISTEDUSDT": False, "NOPEUSDT": False, "ETHUSDT": True}

    def boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    assert BinanceFeed.validate_symbols(["BTCUSDT"]) == {"BTCUSDT": False}
    assert BinanceFeed.validate_symbols([]) == {}
