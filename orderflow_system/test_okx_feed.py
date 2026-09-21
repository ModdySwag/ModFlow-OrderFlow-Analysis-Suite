"""OKX feed — the `seqId` chain, the deprecated checksum, the taker side, and the gates.

The live venue settled two of these rules before the adapter was written, so the tests encode what
the wire actually does: the crc32 checksum is validated exactly as documented but a `0` (what every
live frame carries) is not a verdict, and continuity is the `seqId`/`prevSeqId` chain — with the two
documented exceptions (empty keepalive, maintenance reset). Then the feed end to end with a fake
socket, against real frame shapes captured from `wss://ws.okx.com:8443/ws/v5/public`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import zlib

from orderflow_system.data.feed_session import VENUE_POLICIES
from orderflow_system.data.models import Side
from orderflow_system.data.okx_feed import (
    BOOK_DEPTH,
    CHECKSUM_LEVELS,
    OkxBook,
    OkxFeed,
    okx_book_checksum,
    verify_okx_checksum,
)

INST = "BTC-USDT-SWAP"
TS = 1_789_565_815_382                        # a real `ts` from the live trades channel


def _trades(px="75662.6", sz="0.49", ts=TS, side="buy", inst=INST, tid="2922676531"):
    """A trades frame exactly as the live venue sends it (side is the taker's, as a string)."""
    return {"arg": {"channel": "trades", "instId": inst},
            "data": [{"instId": inst, "tradeId": tid, "px": px, "sz": sz, "side": side,
                      "ts": str(ts), "count": "1", "source": "0", "seqId": 339940381992}]}


def _rows(pairs):
    """The venue's 4-column level rows: [px, sz, deprecated, order count]."""
    return [[px, sz, "0", "1"] for px, sz in pairs]


def _snapshot(bids, asks, seq_id=100, prev_seq_id=-1, ts=TS, inst=INST, checksum=0):
    return {"arg": {"channel": "books", "instId": inst}, "action": "snapshot",
            "data": [{"asks": _rows(asks), "bids": _rows(bids), "ts": str(ts), "checksum": checksum,
                      "seqId": seq_id, "prevSeqId": prev_seq_id}]}


def _update(bids, asks, seq_id, prev_seq_id, checksum=0, ts=TS, inst=INST):
    return {"arg": {"channel": "books", "instId": inst}, "action": "update",
            "data": [{"asks": _rows(asks), "bids": _rows(bids), "ts": str(ts), "checksum": checksum,
                      "seqId": seq_id, "prevSeqId": prev_seq_id}]}


def _deep_book(levels=30, base=100.0):
    """`levels` prices a side, best-first, as the venue would print them."""
    return ([(f"{base - i * 0.1:.1f}", f"{i + 1}.5") for i in range(levels)],
            [(f"{base + 0.1 + i * 0.1:.1f}", f"{i + 2}.25") for i in range(levels)])


def _expected_checksum(bids, asks, cap=CHECKSUM_LEVELS):
    """The documented string, built by hand: bids first, then asks, one colon between every token."""
    tokens = []
    for px, sz in list(bids)[:cap] + list(asks)[:cap]:
        tokens += [px[:25], sz[:25]]
    return zlib.crc32(":".join(tokens).encode("ascii")) & 0xFFFFFFFF


# ── the book: snapshot + `seqId` chain ────────────────────────────────────────────────────────
def test_a_snapshot_replaces_the_book_and_an_update_applies_level_changes():
    book = OkxBook("BTCUSDT", inst_id=INST)
    assert book.stale is True and book.has_snapshot is False

    book.snapshot(_rows([("75662.7", "765.24"), ("75662.6", "0.5")]),
                  _rows([("75663.0", "379.45")]), seq_id=100, prev_seq_id=-1, ts_ms=TS)
    assert book.stale is False and book.has_snapshot is True and book.seq_id == 100
    assert book.last_ts_ms == TS, "the venue's own ts must be carried, not the local clock"
    snap = book.to_snapshot()
    assert snap.best_bid == 75662.7 and snap.best_ask == 75663.0

    assert book.on_update([("75662.8", "4")], [("75662.9", "1")], seq_id=105, prev_seq_id=100) is True
    assert book.to_snapshot().best_bid == 75662.8
    assert book.to_snapshot().best_ask == 75662.9
    # sz "0" removes the level — how this venue deletes instead of publishing an empty row.
    assert book.on_update([("75662.6", "0")], [], seq_id=110, prev_seq_id=105) is True
    assert [lv.price for lv in book.to_snapshot().bids] == [75662.8, 75662.7]
    assert book.seq_id == 110 and book.applied == 2


def test_the_chain_must_continue_or_the_book_goes_stale():
    book = OkxBook("BTCUSDT", inst_id=INST)
    book.snapshot(_rows([("100.0", "1")]), _rows([("100.1", "1")]), seq_id=100, prev_seq_id=-1)

    assert book.on_update([("99.9", "1")], [], seq_id=105, prev_seq_id=100) is True
    assert book.applied == 1 and book.seq_id == 105

    # prevSeqId 999 is neither the last seqId (105) nor the venue's reset shape: a hole
    assert book.on_update([("99.8", "1")], [], seq_id=200, prev_seq_id=999) is False
    assert book.stale is True and book.gaps == 1 and book.seq_id is None
    assert book.to_snapshot().stale is True

    # once stale, updates are dropped until a snapshot lands
    assert book.on_update([("99.7", "1")], [], seq_id=201, prev_seq_id=200) is True
    assert book.dropped == 1 and book.applied == 1


def test_the_empty_keepalive_is_not_a_gap():
    """The venue keeps a quiet socket alive with an empty delta whose seqId repeats itself."""
    book = OkxBook("BTCUSDT", inst_id=INST)
    book.snapshot(_rows([("100.0", "1")]), _rows([("100.1", "1")]), seq_id=100, prev_seq_id=-1)

    assert book.on_update([], [], seq_id=105, prev_seq_id=105) is True
    assert book.heartbeats == 1 and book.stale is False and book.gaps == 0
    assert book.seq_id == 100, "a keepalive carries no state and must not move the chain head"


def test_a_maintenance_sequence_reset_is_adopted_as_the_new_head():
    """The venue's worked example: 10 → 15 (normal) → 3 (reset) → 5 (normal), prevSeqId always the
    last seqId. A reset is `seqId < prevSeqId`, and it re-heads the chain instead of staling it."""
    book = OkxBook("BTCUSDT", inst_id=INST)
    book.snapshot(_rows([("100.0", "1")]), _rows([("100.1", "1")]), seq_id=10, prev_seq_id=-1)

    assert book.on_update([("99.9", "1")], [], seq_id=15, prev_seq_id=10) is True
    assert book.seq_id == 15 and book.seq_resets == 0

    assert book.on_update([("99.8", "1")], [], seq_id=3, prev_seq_id=15) is True
    assert book.seq_resets == 1 and book.stale is False and book.gaps == 0
    assert book.seq_id == 3, "the reset message is the new head, not a hole"
    assert book.on_update([("99.7", "1")], [], seq_id=5, prev_seq_id=3) is True
    assert book.applied == 3


def test_updates_before_the_first_snapshot_are_dropped():
    book = OkxBook("BTCUSDT", inst_id=INST)
    assert book.on_update([("100.0", "1")], [], seq_id=5, prev_seq_id=4) is True
    assert book.dropped == 1 and book.applied == 0 and book.has_snapshot is False


def test_the_book_is_trimmed_at_the_venue_push_depth():
    book = OkxBook("BTCUSDT", inst_id=INST)
    bids = [(f"{100.0 - i * 0.01:.2f}", "1") for i in range(BOOK_DEPTH + 50)]
    book.snapshot(_rows(bids), _rows([("100.5", "1")]), seq_id=1, prev_seq_id=-1)
    assert len(book.bids) == BOOK_DEPTH
    assert book.snapshot_evictions >= 50
    assert len(book.bid_tokens) == BOOK_DEPTH, "tokens must be trimmed with the levels they describe"


# ── the checksum (documented algorithm; a live `0` is not a verdict) ──────────────────────────
def test_the_checksum_accepts_a_self_consistent_book_and_rejects_a_mutation():
    bids, asks = _deep_book()
    expected = _expected_checksum(bids, asks)
    assert okx_book_checksum(bids, asks) == expected
    assert verify_okx_checksum(bids, asks, expected) is True

    mutated = list(bids)
    mutated[3] = (mutated[3][0], "999.5")
    assert verify_okx_checksum(mutated, asks, expected) is False, \
        "one changed size at the top of book must change the checksum"
    assert verify_okx_checksum(bids, list(asks[:2]) + [("1.0", "1.0")], expected) is False


def test_the_checksum_covers_only_the_top_25_levels_per_side():
    bids, asks = _deep_book(levels=30)
    expected = _expected_checksum(bids, asks)
    assert okx_book_checksum(bids, asks) == expected

    deep = list(bids)
    deep[CHECKSUM_LEVELS + 2] = (deep[CHECKSUM_LEVELS + 2][0], "123.5")
    assert verify_okx_checksum(deep, asks, expected) is True, \
        "levels below the top 25 are outside the checksum's reach by definition"
    assert verify_okx_checksum(bids, asks, None) is None
    assert verify_okx_checksum(bids, asks, 0) is None, \
        "0 is the venue's deprecated 'fixed to 0' state (every live frame carries it), not a match"


def test_a_bad_checksum_marks_the_book_stale_and_counts_it():
    book = OkxBook("BTCUSDT", inst_id=INST)
    book.snapshot(_rows([("100.0", "1")]), _rows([("100.1", "1")]), seq_id=100, prev_seq_id=-1)

    assert book.on_update([("99.9", "1")], [], seq_id=105, prev_seq_id=100,
                          checksum=1234567) is False
    assert book.stale is True
    assert book.checksum_mismatches == 1 and book.checksum_checks == 1
    assert book.gaps == 1 and book.seq_id is None
    assert book.to_snapshot().stale is True


def test_a_correct_nonzero_checksum_is_accepted_and_counted():
    book = OkxBook("BTCUSDT", inst_id=INST)
    book.snapshot(_rows([("100.0", "1")]), _rows([("100.1", "1")]), seq_id=100, prev_seq_id=-1)

    bids, asks = [("99.9", "1"), ("100.0", "1")], [("100.1", "1")]
    good = okx_book_checksum(sorted(bids, key=lambda r: -float(r[0])),
                             sorted(asks, key=lambda r: float(r[0])))
    assert book.on_update(bids, asks, seq_id=105, prev_seq_id=100, checksum=good) is True
    assert book.stale is False and book.checksum_checks == 1 and book.checksum_mismatches == 0


def test_the_venues_zero_checksum_is_unavailable_rather_than_a_mismatch():
    book = OkxBook("BTCUSDT", inst_id=INST)
    book.snapshot(_rows([("100.0", "1")]), _rows([("100.1", "1")]), seq_id=100, prev_seq_id=-1)
    assert book.on_update([("99.9", "1")], [], seq_id=105, prev_seq_id=100, checksum=0) is True
    assert book.checksum_unavailable == 1 and book.checksum_mismatches == 0 and book.stale is False


# ── the feed ──────────────────────────────────────────────────────────────────────────────────
class FakeWS:
    """A socket that hands out frames on demand — no network anywhere in this file."""

    def __init__(self):
        self.sent = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self.delivered = 0

    def push(self, *frames):
        for frame in frames:
            self._queue.put_nowait(frame)

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            # Park while the queue is empty: a test may push a frame later (a resync's snapshot),
            # and the reader must pick it up the moment it lands rather than after a fixed sleep.
            frame = await asyncio.wait_for(self._queue.get(), timeout=5)
        except asyncio.TimeoutError:
            raise StopAsyncIteration from None
        self.delivered += 1
        return frame


async def _until(pred, tries: int = 400):
    """Spin the loop until `pred()` holds: the tests poll for the state they assert."""
    for _ in range(tries):
        await asyncio.sleep(0.005)
        if pred():
            break


async def _run_feed(frames, *, symbols=("BTCUSDT",), resync_cooldown_s=0.0):
    ticks: list = []
    books: list = []
    ws = FakeWS()
    ws.push(*frames)

    async def connect():
        feed._conn = ws              # production's _connect parks the live connection here too
        return ws

    async def on_tick(symbol, tick):
        ticks.append((symbol, tick))

    async def on_book(symbol, book):
        books.append((symbol, book))

    feed = OkxFeed(symbols=list(symbols), on_tick=on_tick, on_orderbook=on_book,
                   resync_cooldown_s=resync_cooldown_s)
    session = await feed_start(feed, connect)
    return feed, ws, ticks, books, session


async def feed_start(feed, connect):
    """Drive the session for a moment without waiting on real sockets.

    The session owns the connection and the subscription — one owner, as production's
    OkxFeed.start() has it; the harness must not call on_connected beside it (the second, manual
    subscribe cycle raced the session's own — the Hyperliquid harness shipped the same shape and a
    whole-list assertion read whichever cycle won). The wait is the subscription itself, not a
    wall-clock guess.
    """
    import orderflow_system.data.feed_session as fs

    connected = asyncio.Event()

    async def on_connected(conn):
        await feed._on_connected(conn)
        connected.set()

    session = fs.FeedSession("okx", connect, feed._on_frame,
                             on_connected=on_connected,
                             on_disconnected=feed._on_disconnected,
                             policy=VENUE_POLICIES["okx"], heartbeat_tick_s=0.05)
    feed._session = session
    task = asyncio.create_task(session.run())
    for _ in range(200):
        await asyncio.sleep(0.01)
        if not task.done() and connected.is_set():
            break
    return session


def test_the_feed_subscribes_trades_and_books_for_every_symbol():
    async def main():
        feed, ws, _ticks, _books, session = await _run_feed([])
        await session.stop()
        return feed, ws

    feed, ws = asyncio.run(main())
    sub = json.loads(ws.sent[0])
    assert sub["op"] == "subscribe", "the live venue takes one dynamic subscribe, not a URL stream"
    assert {"channel": "trades", "instId": INST} in sub["args"]
    assert {"channel": "books", "instId": INST} in sub["args"]
    assert {a["channel"] for a in sub["args"]} == {"trades", "books"}
    assert feed.symbols == ["BTCUSDT"] and feed.inst_of == {"BTCUSDT": INST}


def test_the_feed_installs_the_pushed_snapshot_and_publishes_it():
    async def main():
        frames = [json.dumps(_snapshot([("75662.7", "765.24")], [("75662.8", "379.45")]))]
        feed, _ws, _ticks, books, session = await _run_feed(frames)
        await _until(lambda: bool(books))
        health = feed.books["BTCUSDT"].health()
        await session.stop()
        return feed, books, health

    feed, books, health = asyncio.run(main())
    assert books, "the pushed snapshot must be published (the heatmap needs a seed)"
    symbol, snapshot = books[-1]
    assert symbol == "BTCUSDT" and snapshot.stale is False
    assert snapshot.best_bid == 75662.7 and snapshot.best_ask == 75662.8
    assert health["has_snapshot"] is True and health["resyncs"] == 1, "subscribing is the snapshot"
    assert feed.get_orderbook("BTCUSDT").best_bid == 75662.7
    assert feed.book_health()["seq"] == {"BTCUSDT": 100}


def test_a_gap_on_the_wire_resubscribes_and_recovers():
    async def main():
        frames = [
            json.dumps(_snapshot([("75662.7", "765.24")], [("75662.8", "379.45")], seq_id=100)),
            json.dumps(_update([("75662.6", "1")], [], seq_id=200, prev_seq_id=999)),   # a hole
        ]
        feed, ws, _ticks, _books, session = await _run_feed(frames)
        await _until(lambda: feed.books["BTCUSDT"].stale and len(ws.sent) > 1)
        ops = [json.loads(p).get("op") for p in ws.sent[1:]]
        assert "unsubscribe" in ops and "subscribe" in ops, \
            "a broken book recovers by re-subscribing on the live socket (verified against the venue)"
        ws.push(json.dumps(_snapshot([("75662.5", "2")], [("75662.6", "3")], seq_id=300)))
        await _until(lambda: not feed.books["BTCUSDT"].stale
                     and feed.books["BTCUSDT"].seq_id == 300)
        health = feed.books["BTCUSDT"].health()
        board = feed.book_health()
        await session.stop()
        return feed, health, board

    feed, health, board = asyncio.run(main())
    assert health["gaps"] >= 1
    assert health["stale"] is False, "the resynced book must be live again"
    assert health["seq_id"] == 300
    assert board["stale"] == [] and board["resyncs"] >= 2, \
        "the venue's pushed snapshot counts as the resync that fixed it"


def test_a_closed_socket_marks_every_book_stale():
    """A socket that goes away invalidates the books: the levels are the last known-good state,
    not what the venue shows now, and the flag must travel with the snapshot."""

    async def main():
        frames = [json.dumps(_snapshot([("100.0", "1")], [("100.1", "1")]))]
        feed, _ws, _ticks, _books, session = await _run_feed(frames)
        await _until(lambda: feed.books["BTCUSDT"].has_snapshot)
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
            json.dumps(_trades(px="75662.6", sz="0.49", side="buy")),      # taker bought
            json.dumps(_trades(px="75662.5", sz="1.33", side="sell", tid="2922676769")),
        ]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await _until(lambda: len(ticks) >= 2)
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert len(ticks) == 2
    (sym1, t1), (sym2, t2) = ticks
    assert sym1 == sym2 == "BTCUSDT"
    assert t1.side is Side.BUY and t2.side is Side.SELL, \
        "this venue reports the taker side directly — there is no maker flag to invert"
    assert t1.price == 75662.6 and t1.size == 0.49 and t1.trade_id == "2922676531"
    assert t1.timestamp_ms == TS
    assert t2.price == 75662.5 and t2.trade_id == "2922676769"
    assert feed.ticks == 2
    assert feed.stats()["ticks"] == 2


def test_junk_prints_are_dropped_and_counted_with_one_warning(caplog):
    async def main():
        frames = [
            json.dumps(_trades(px="NaN")),                      # the bare JSON token
            json.dumps(_trades(px="-1")),
            json.dumps(_trades(sz="0")),                        # a zero-size fill is not a fill
            json.dumps(_trades(side="", sz="1")),               # no usable side
            json.dumps(_trades()),                              # the only good one
        ]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await _until(lambda: len(ticks) >= 1)
        await session.stop()
        return feed, ticks

    with caplog.at_level(logging.WARNING, logger="orderflow_system.data.okx_feed"):
        feed, ticks = asyncio.run(main())
    assert len(ticks) == 1, f"only the good print may pass: {ticks}"
    assert feed.junk_prints == 4
    assert feed.book_health()["junk_values"] >= 4
    drops = [r for r in caplog.records if "unusable" in r.getMessage()]
    assert len(drops) == 1, "one warning on the first dropped value, then silence"


def test_a_bare_pong_frame_is_the_heartbeat_answer_not_a_parse_error(caplog):
    """The venue answers a bare text `ping` with a bare text `pong`; the session policy relies on it."""

    async def main():
        feed, _ws, _ticks, _books, session = await _run_feed(["pong"])
        await _until(lambda: bool(feed.pongs))
        await session.stop()
        return feed

    with caplog.at_level(logging.WARNING, logger="orderflow_system.data.okx_feed"):
        feed = asyncio.run(main())
    assert feed.pongs == 1
    assert feed.stats()["pongs"] == 1
    assert not [r for r in caplog.records if "invalid JSON" in r.getMessage()], \
        "the heartbeat's answer must not be logged as a parse error"


def test_a_venue_error_event_is_counted_and_warned_once(caplog):
    async def main():
        error = json.dumps({"event": "error", "code": "60012",
                            "msg": "Illegal request", "connId": "86f30dd5"})
        feed, _ws, _ticks, _books, session = await _run_feed([error, error])
        await _until(lambda: feed.venue_errors >= 2)
        await session.stop()
        return feed

    with caplog.at_level(logging.WARNING, logger="orderflow_system.data.okx_feed"):
        feed = asyncio.run(main())
    assert feed.venue_errors == 2
    assert feed.stats()["venue_errors"] == 2
    assert len([r for r in caplog.records if "60012" in r.getMessage()]) == 1, \
        "one warning per error code, then silence"


def test_book_health_and_stats_carry_the_venue_shape():
    feed = OkxFeed(symbols=["BTCUSDT", "ETHUSDT"])
    health = feed.book_health()
    assert health["venue"] == "okx"
    assert set(health) >= {"stale", "gaps", "dropped_deltas", "junk_values", "seq"}
    assert sorted(health["stale"]) == ["BTCUSDT", "ETHUSDT"]      # nothing seeded yet
    stats = feed.stats()
    assert stats["venue"] == "okx" and stats["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert set(stats) >= {"ticks", "junk_prints", "pongs", "venue_errors", "books"}
    assert set(stats["books"]["BTCUSDT"]) >= {"stale", "has_snapshot", "seq_id", "levels",
                                              "checksum_mismatches", "seq_resets", "heartbeats"}
    assert OkxFeed(symbols=["BTCUSDT"]).get_orderbook("BTCUSDT") is None
    assert feed.inst_of["ETHUSDT"] == "ETH-USDT-SWAP"


def test_the_adapter_uses_the_ping_after_idle_policy(monkeypatch):
    import orderflow_system.data.okx_feed as mod

    policy = VENUE_POLICIES["okx"]
    assert policy.mode == "ping_after_idle", \
        "the venue closes an idle socket (4004, no data in 30s), so the session must ping it"
    assert policy.ping_after_idle_s > 0 and policy.silence_budget_s > 0

    seen: dict = {}

    class Recorder:
        def __init__(self, venue, connect, on_frame, **kwargs):
            seen.update({"venue": venue, "connect": connect, "on_frame": on_frame}, **kwargs)

        async def run(self):
            seen["ran"] = True

        async def stop(self):
            pass

    monkeypatch.setattr(mod, "FeedSession", Recorder)
    feed = OkxFeed(symbols=["BTCUSDT"])
    asyncio.run(feed.start())
    assert seen["venue"] == "okx"
    assert seen["policy"] is VENUE_POLICIES["okx"], "the venue's own liveness contract, not a copy"
    assert seen["connect"] == feed._connect and seen["on_frame"] == feed._on_frame
    assert seen["on_connected"] == feed._on_connected
    assert seen["on_disconnected"] == feed._on_disconnected
    assert seen["ran"] is True


def test_to_venue_symbol_maps_the_suite_naming():
    assert OkxFeed.to_venue_symbol("BTCUSDT") == INST
    assert OkxFeed.to_venue_symbol("ethusdt") == "ETH-USDT-SWAP"
    assert OkxFeed.to_venue_symbol("SOLUSDT") == "SOL-USDT-SWAP"
    assert OkxFeed.to_venue_symbol(INST) == INST, "an instId in venue form is already mapped"
    assert OkxFeed.to_venue_symbol("BTCUSD") == "BTCUSD", \
        "not a suite symbol: passed through rather than invented as a different instrument"
    assert OkxFeed.from_venue_symbol(INST) == "BTCUSDT"
    assert OkxFeed.from_venue_symbol("BTC-USD-SWAP") == "BTCUSD"
    assert OkxFeed(symbols=["btcusdt", "ETHUSDT"]).inst_of == {
        "BTCUSDT": INST, "ETHUSDT": "ETH-USDT-SWAP"}


def test_validate_symbols_reads_the_venue_listing(monkeypatch):
    import orderflow_system.data.okx_feed as mod

    payload = {"code": "0", "data": [
        {"instId": "BTC-USDT-SWAP", "state": "live", "ctType": "linear", "settleCcy": "USDT"},
        {"instId": "ETH-USDT-SWAP", "state": "suspend", "ctType": "linear", "settleCcy": "USDT"},
        {"instId": "SOL-USDT-SWAP", "state": "live", "ctType": "linear", "settleCcy": "USDT"},
        {"instId": "BTC-USD-SWAP", "state": "live", "ctType": "linear", "settleCcy": "BTC"},
    ]}
    urls: list = []

    class Resp:
        def __init__(self, body):
            self._body = json.dumps(body).encode()

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=0):
        urls.append(req.full_url)
        return Resp(payload)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    got = OkxFeed.validate_symbols(["BTCUSDT", "ETHUSDT", "NOPEUSDT", "BTCUSD", "SOLUSDT"])
    assert got == {"BTCUSDT": True, "ETHUSDT": False, "NOPEUSDT": False, "BTCUSD": False,
                   "SOLUSDT": True}, "only live linear USDT swaps count as listed"
    assert urls and "instType=SWAP" in urls[0] and urls[0].startswith("https://www.okx.com/api/v5/")

    def boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    assert OkxFeed.validate_symbols(["BTCUSDT"]) == {"BTCUSDT": False}
    assert OkxFeed.validate_symbols([]) == {}
