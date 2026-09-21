"""Hyperliquid feed — the snapshot rule, the taker-side letters, the listing gate, the junk gates.

There is no chain to drive here (the venue pushes a whole book per frame), so what these tests pin is
what this venue really leaves to the client: a wholesale replace that cannot be half-applied, an age
window checked against an injected clock, the taker-side convention, the meta listing as the only
gate on what may be subscribed, and the session wiring. No sockets, no REST — the frame shapes are
the live venue's (see the module docstring for what was verified against it).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from orderflow_system.data.feed_session import VENUE_POLICIES
from orderflow_system.data.hyperliquid_feed import (
    MAX_LEVELS,
    HyperliquidBook,
    HyperliquidFeed,
)
from orderflow_system.data.models import Side

ROOT = Path(__file__).resolve().parents[1]
FEED_SRC = ROOT / "orderflow_system" / "data" / "hyperliquid_feed.py"

TS = 1_700_000_000_000


# ── the venue's frames (as they arrived live; see the module docstring) ────────────────────────
def _trade(coin="BTC", side="B", px="100.5", sz="2", ts=TS, tid=7):
    """One print: strings for the numbers, a 15-digit int id, venue ms, a buyer/seller pair."""
    return {"coin": coin, "side": side, "px": px, "sz": sz, "time": ts,
            "hash": "0x" + "0" * 64, "tid": tid,
            "users": ["0x" + "b" * 40, "0x" + "a" * 40]}


def _trades(*items, coin=None):
    """The frame the venue pushes for prints: a BATCH under a channel (1-30 prints live)."""
    payload = [dict(item, coin=coin) if coin else item for item in items]
    return json.dumps({"channel": "trades", "data": payload})


def _levels(pairs):
    return [{"px": p, "sz": s, "n": 1} for p, s in pairs]


def _book(bids, asks, coin="BTC", ts=TS):
    return json.dumps({"channel": "l2Book",
                       "data": {"coin": coin, "time": ts,
                                "levels": [_levels(bids), _levels(asks)]}})


def _meta(universe):
    return {"universe": [{"name": name, **fields} for name, fields in universe]}


#: The listing the fake REST answers with, unless a test asks for its own.
LISTING = _meta([("BTC", {"szDecimals": 5}), ("ETH", {"szDecimals": 4}),
                 ("kPEPE", {"szDecimals": 0}),
                 ("MATIC", {"szDecimals": 1, "isDelisted": True})])


# ── the book: wholesale replace, age window, junk gates ─────────────────────────────────────────
def test_a_snapshot_replaces_the_book_wholesale():
    book = HyperliquidBook("BTCUSDT", coin="BTC")
    assert book.stale is True and book.has_snapshot is False

    assert book.replace([_levels([(99.5, "3"), (99.0, "1")]), _levels([(100.5, "2")])], TS, 1000.0) == 3
    assert book.has_snapshot is True and book.stale is False and book.updates == 1
    assert book.to_snapshot().best_bid == 99.5 and book.to_snapshot().best_ask == 100.5

    # The second snapshot is the whole book, not a delta onto the first: 99.5 is simply gone.
    assert book.replace([_levels([(98.5, "4")]), _levels([(101.0, "1")])], TS + 1, 1004.0) == 2
    assert [lv.price for lv in book.to_snapshot().bids] == [98.5]
    assert [lv.price for lv in book.to_snapshot().asks] == [101.0]
    assert book.updates == 2 and book.last_ts_ms == TS + 1


def test_the_book_goes_stale_only_when_it_became_stale():
    book = HyperliquidBook("BTCUSDT")
    book.replace([_levels([(99.5, "3")]), _levels([(100.5, "2")])], TS, 1000.0)
    assert book.refresh(10.0, 1005.0) is False, "half the window is not stale"
    assert book.refresh(10.0, 1010.5) is True, "past the window is the transition"
    assert book.stale is True and book.stale_marks == 1
    assert book.refresh(10.0, 1400.0) is False, "an already-stale book must not announce again"
    assert book.stale_marks == 1


def test_a_stale_book_is_the_last_known_state_not_an_empty_one():
    book = HyperliquidBook("BTCUSDT")
    book.replace([_levels([(99.5, "3")]), _levels([(100.5, "2")])], TS, 1000.0)
    book.refresh(10.0, 1200.0)
    snap = book.to_snapshot()
    assert snap.stale is True
    assert snap.best_bid == 99.5, "the levels must travel with the flag, not be thrown away"
    assert snap.timestamp_ms == TS, "the snapshot keeps the venue's own stamp, not the local clock"


def test_an_empty_snapshot_never_erases_a_good_book():
    book = HyperliquidBook("BTCUSDT")
    book.replace([_levels([(99.5, "3")]), _levels([(100.5, "2")])], TS, 1000.0)
    assert book.replace([[], []], TS, 1001.0) == 0
    assert book.replace("nonsense", TS, 1001.0) == 0
    assert book.to_snapshot().best_bid == 99.5 and book.updates == 1
    assert book.junk_values == 2


def test_junk_levels_are_refused_and_counted():
    book = HyperliquidBook("BTCUSDT")
    accepted = book.replace([
        _levels([(99.5, "3")]) + [{"px": "NaN", "sz": "1"}, {"px": "99.0", "sz": "-1"},
                                  {"px": "98.0"}],
        _levels([(100.5, "2"), (100.6, "0")]),
    ], TS, 1000.0)
    assert accepted == 2, "only the usable levels may land — one bid, one ask"
    assert book.to_snapshot().best_bid == 99.5 and book.to_snapshot().best_ask == 100.5
    assert book.junk_values == 4, "NaN, negative, missing sz and zero size are all refused"


def test_the_venue_depth_is_the_book_cap():
    book = HyperliquidBook("BTCUSDT")
    bids = [(100.0 - i * 0.1, "1") for i in range(MAX_LEVELS + 5)]
    book.replace([_levels(bids), _levels([(200.0, "1")])], TS, 1000.0)
    assert len(book.bids) == MAX_LEVELS
    assert book.to_snapshot().best_bid == 100.0, "the trim keeps the levels nearest the touch"


# ── the feed ───────────────────────────────────────────────────────────────────────────────────
async def _run_feed(frames, *, meta=None, symbols=("BTCUSDT",), stale_after_s=10.0, clock=None):
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
        feed._conn = ws      # production's _connect parks the live connection here too
        return ws

    async def on_tick(symbol, tick):
        ticks.append((symbol, tick))

    async def on_book(symbol, book):
        books.append((symbol, book))

    kwargs = {"clock": clock} if clock else {}
    feed = HyperliquidFeed(symbols=list(symbols), on_tick=on_tick, on_orderbook=on_book,
                           stale_after_s=stale_after_s, **kwargs)

    def default_meta():                                          # no network in tests
        return LISTING

    feed._fetch_meta = meta or default_meta
    session = await feed_start(feed, connect, frames)
    return feed, ws, ticks, books, session


async def feed_start(feed, connect, frames):
    """Drive the session for a moment without waiting on real sockets.

    The session owns the connection and the subscription — one owner, exactly as production's
    HyperliquidFeed.start() has it (connect → on_connected → read loop). The harness must not
    call on_connected beside it: a second, manual subscribe cycle raced the session's own, and
    whole-list `ws.sent` assertions then read whichever cycle finished first — 4 payloads where
    a stop a millisecond sooner read 2 (the CI test (3.11) red on a docs-only push).
    """
    import orderflow_system.data.feed_session as fs

    connected = asyncio.Event()

    async def on_connected(conn):
        await feed._on_connected(conn)
        connected.set()

    session = fs.FeedSession("hyperliquid", connect, feed._on_frame,
                             on_connected=on_connected,
                             on_disconnected=feed._on_disconnected,
                             policy=VENUE_POLICIES["hyperliquid"],
                             ping_payload=json.dumps({"method": "ping"}),
                             heartbeat_tick_s=0.05)
    feed._session = session
    task = asyncio.create_task(session.run())
    for _ in range(200):
        await asyncio.sleep(0.01)
        if not task.done() and connected.is_set() and not frames:
            break
    return session


def test_the_feed_subscribes_trades_and_the_book_for_every_symbol():
    async def main():
        feed, ws, _ticks, _books, session = await _run_feed([], symbols=("BTCUSDT", "ETHUSDT"))
        await session.stop()
        return feed, ws

    feed, ws = asyncio.run(main())
    sent = [json.loads(payload) for payload in ws.sent]
    assert all(message["method"] == "subscribe" for message in sent)
    assert [message["subscription"] for message in sent] == [
        {"type": "trades", "coin": "BTC"}, {"type": "l2Book", "coin": "BTC"},
        {"type": "trades", "coin": "ETH"}, {"type": "l2Book", "coin": "ETH"},
    ], "one trades and one l2Book subscription per symbol, by the venue's coin name"
    assert feed.symbols == ["BTCUSDT", "ETHUSDT"]


def test_every_frame_lands_and_the_book_frame_is_published():
    async def main():
        frames = [
            _trades(_trade(px="100.5", sz="2", tid=7)),
            _trades(_trade(px="100.4", sz="1", tid=8), _trade(px="100.6", sz="3", side="A", tid=9)),
            _book([(99.5, "3")], [(100.5, "2")]),
            json.dumps({"channel": "subscriptionResponse", "data": {"method": "subscribe"}}),
            json.dumps({"channel": "pong"}),
            _book([(99.6, "4")], [(100.4, "2")]),
        ]
        feed, _ws, ticks, books, session = await _run_feed(frames)
        await session.stop()
        return feed, ticks, books

    feed, ticks, books = asyncio.run(main())
    assert len(ticks) == 3, f"every print in the batch must land: {ticks}"
    assert len(books) == 2, "each l2Book frame publishes a snapshot"
    assert feed.ticks == 3
    assert [symbol for symbol, _ in ticks] == ["BTCUSDT"] * 3
    assert books[-1][1].best_bid == 99.6 and books[-1][1].stale is False
    assert feed.get_orderbook("BTCUSDT").best_ask == 100.4
    assert feed.get_orderbook("BTC").best_ask == 100.4, "the wire speaks coins — accept one"


def test_the_taker_side_convention_b_is_buy_and_a_is_sell():
    async def main():
        frames = [_trades(_trade(side="B", px="100.5", sz="2", tid=42),
                          _trade(side="A", px="100.4", sz="1", tid=43))]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert len(ticks) == 2, "a batch frame carries more than one print"
    (sym1, t1), (sym2, t2) = ticks
    assert sym1 == sym2 == "BTCUSDT"
    assert t1.side is Side.BUY, "B is the buy aggressor — it lifts the offer"
    assert t2.side is Side.SELL, "A is the seller — it hits the bid"
    assert t1.price == 100.5 and t1.size == 2.0 and t1.timestamp_ms == TS
    assert t1.trade_id == "42" and t2.trade_id == "43", "the venue's tid is carried as the id"


def test_an_unknown_taker_side_is_dropped_not_guessed(caplog):
    caplog.set_level(logging.INFO)

    async def main():
        frames = [_trades(_trade(side="X"), _trade(px="NaN"), _trade(), _trade(side="A"))]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert [tick.side for _sym, tick in ticks] == [Side.BUY, Side.SELL]
    assert feed.junk_prints == 2, "an unknown side and a NaN price are both refused"
    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1, f"one warning on the first bad value, then silence: {warnings}"


def test_junk_prints_are_dropped_and_counted():
    async def main():
        frames = [
            _trades(_trade(px="NaN")),
            _trades(_trade(px="-1")),
            _trades(_trade(sz="0")),
            _trades(_trade()),                       # the only good one
        ]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert len(ticks) == 1, f"only the good print may pass: {ticks}"
    assert feed.junk_prints == 3
    assert feed.book_health()["junk_values"] >= 3
    assert feed.stats()["junk_prints"] == 3


def test_a_print_without_venue_time_falls_back_once(caplog):
    caplog.set_level(logging.INFO)

    async def main():
        frames = [_trades(dict(_trade(), time=None), dict(_trade(tid=8), time=None))]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await session.stop()
        return feed, ticks

    _feed, ticks = asyncio.run(main())
    assert len(ticks) == 2, "a missing stamp must not lose the print"
    assert all(tick.timestamp_ms > 1_600_000_000_000 for _sym, tick in ticks), \
        "the local clock stands in for the venue stamp"
    assert len([r for r in caplog.records if "without time" in r.getMessage()]) == 1, \
        "say it once per connection, not once per print"


def test_an_unknown_channel_is_ignored_with_one_warning(caplog):
    caplog.set_level(logging.INFO)

    async def main():
        frames = [json.dumps({"channel": "somethingNew", "data": {}}),
                  json.dumps({"channel": "somethingNew", "data": {}}),
                  _trades(_trade())]
        feed, _ws, ticks, _books, session = await _run_feed(frames)
        await session.stop()
        return feed, ticks

    feed, ticks = asyncio.run(main())
    assert len(ticks) == 1, "an unknown channel must not stop the ones we do speak"
    assert len([r for r in caplog.records if "unexpected channel" in r.getMessage()]) == 1


def test_a_quiet_book_is_flagged_stale_while_trades_keep_flowing(caplog):
    caplog.set_level(logging.INFO)
    now = [1000.0]

    async def main():
        frames = [_book([(99.5, "3")], [(100.5, "2")])]
        feed, _ws, _ticks, books, session = await _run_feed(
            frames, stale_after_s=10.0, clock=lambda: now[0])
        assert feed.book_health()["stale"] == [], "a fresh book is not stale"

        # The l2Book push stopped, the socket did not: age is checked on every frame and every read.
        now[0] += 11.0
        await feed._on_frame(_trades(_trade()))
        health = feed.book_health()
        await session.stop()
        return feed, books, health

    feed, books, health = asyncio.run(main())
    assert health["stale"] == ["BTCUSDT"], "a book older than the window must say so"
    assert health["stale_marks"] == 1
    assert feed.get_orderbook("BTCUSDT").stale is True
    assert books[-1][1].stale is False, "the published snapshot was fresh when it was published"
    assert sum("no l2Book update" in r.getMessage() for r in caplog.records) == 1, \
        "the transition is announced once, on a trades frame that proves the socket is alive"

    async def recover():
        now[0] += 1.0
        await feed._on_frame(_book([(99.7, "5")], [(100.3, "1")]))
        return feed.book_health()

    health = asyncio.run(recover())
    assert health["stale"] == [] and health["stale_marks"] == 1, \
        "a fresh snapshot clears the flag without inventing a second mark"
    assert any("live again" in r.getMessage() for r in caplog.records)


def test_a_closed_socket_marks_every_book_stale():
    """The venue pushes the book, so a socket that goes away is silence: the last book is the last
    known-good state, and the flag must travel with the snapshot."""

    async def main():
        feed, _ws, _ticks, _books, session = await _run_feed([_book([(99.5, "3")], [(100.5, "2")])])
        assert feed.books["BTCUSDT"].stale is False
        await feed._on_disconnected(ConnectionResetError("closed"))
        health = feed.book_health()
        snap = feed.books["BTCUSDT"].to_snapshot()
        await session.stop()
        return health, snap

    health, snap = asyncio.run(main())
    assert health["stale"] == ["BTCUSDT"]
    assert snap.stale is True, "the published snapshot must carry the stale flag"


# ── the listing: what may be subscribed, and what the venue will not trade ─────────────────────
def test_the_symbol_mapping_strips_only_the_quote():
    assert HyperliquidFeed.to_venue_symbol("btcusdt") == "BTC"
    assert HyperliquidFeed.to_venue_symbol("BTCUSD") == "BTC"
    assert HyperliquidFeed.to_venue_symbol("BTCUSDT") == "BTC"
    assert HyperliquidFeed.to_venue_symbol("APTUSDT") == "APT", "only the quote is stripped, not a T"
    assert HyperliquidFeed.to_venue_symbol("BTC") == "BTC"
    assert HyperliquidFeed.to_venue_symbol("") == "" and HyperliquidFeed.to_venue_symbol("  ") == ""
    assert HyperliquidFeed.to_venue_symbol("KPEPEUSDT", universe={"kPEPE": 0}) == "kPEPE", \
        "the venue's own spelling wins when the listing is known"


def test_the_listing_gate_skips_a_delisted_an_unlisted_and_a_duplicate_coin(caplog):
    caplog.set_level(logging.INFO)

    async def main():
        frames = []
        feed, ws, _ticks, _books, session = await _run_feed(
            frames, symbols=("BTCUSDT", "MATICUSDT", "NOPEUSDT", "BTCUSD"))
        await session.stop()
        return feed, ws

    feed, ws = asyncio.run(main())
    coins = [json.loads(payload)["subscription"]["coin"] for payload in ws.sent]
    assert coins == ["BTC", "BTC"], "only the listed BTC is subscribed, once for each of its topics"
    assert feed.books["BTCUSDT"].coin == "BTC"
    assert feed.books["MATICUSDT"].stale is True, \
        "a delisted coin is accepted by the venue and then replays a dead backlog — never subscribed"
    assert feed.books["NOPEUSDT"].stale is True
    assert feed.books["BTCUSD"].stale is True, \
        "a second symbol mapping to BTC must not double every print"
    said = " | ".join(r.getMessage() for r in caplog.records)
    assert "delisted" in said and "not in the venue listing" in said and "both coin BTC" in said, said


def test_the_listing_does_not_stop_the_mapping_when_the_rest_call_fails():
    """FG-08 (§135 fix pass): the second assertion used `caplog.records`, which depends on global
    logging state — one full-suite run in ten failed here while the same test passed six times
    alone. The capture now hangs off the FEED's own logger with its level pinned for the
    duration, so the test measures the feed rather than whatever a previous test did to the root
    logger. The assertion itself is unchanged (never widen one to chase a flake)."""
    feed_logger = logging.getLogger("orderflow_system.data.hyperliquid_feed")
    records: list = []
    handler = logging.Handler()
    handler.emit = records.append
    previous_level = feed_logger.level
    feed_logger.addHandler(handler)
    feed_logger.setLevel(logging.INFO)
    try:
        def offline():
            raise OSError("offline")

        async def main():
            feed, ws, _ticks, _books, session = await _run_feed([], meta=offline)
            await session.stop()
            return feed, ws

        _feed, ws = asyncio.run(main())
    finally:
        feed_logger.removeHandler(handler)
        feed_logger.setLevel(previous_level)
    assert [json.loads(payload)["subscription"]["coin"] for payload in ws.sent] == ["BTC", "BTC"], \
        "a REST hiccup must not silence a feed whose mapping is unambiguous"
    assert any("meta fetch failed" in r.getMessage() for r in records)


def test_a_session_that_lives_longer_still_reads_as_one_subscription_cycle():
    """The harness used to subscribe beside the session, so a stop that arrived a millisecond late
    read 4 payloads where a prompt one read 2 — that race is what went red on a CI test (3.11) run
    (measured: doubling the delay flipped 2 → 4, every time). The session is the single subscribe
    owner now; letting it live beyond its first iteration must not change what the assertion sees.
    """
    async def main():
        feed, ws, _ticks, _books, session = await _run_feed([])
        await asyncio.sleep(0.05)          # several session iterations' worth of slack
        await session.stop()
        return feed, ws

    _feed, ws = asyncio.run(main())
    assert [json.loads(payload)["subscription"]["coin"] for payload in ws.sent] == ["BTC", "BTC"], \
        "one subscribe per topic — a second cycle appeared only when stop() lost the race"


def test_validate_symbols_reads_the_venue_listing(monkeypatch):
    import orderflow_system.data.hyperliquid_feed as mod

    payload = _meta([("BTC", {"szDecimals": 5}), ("kPEPE", {"szDecimals": 0}),
                     ("MATIC", {"szDecimals": 1, "isDelisted": True})])

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
    got = HyperliquidFeed.validate_symbols(["BTCUSDT", "MATICUSDT", "KPEPEUSDT", "NOPEUSDT", "BTC"])
    assert got == {"BTCUSDT": True, "MATICUSDT": False, "KPEPEUSDT": True, "NOPEUSDT": False,
                   "BTC": True}, "only a listed, non-delisted coin is tradable"

    def boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    assert HyperliquidFeed.validate_symbols(["BTCUSDT"]) == {"BTCUSDT": False}
    assert HyperliquidFeed.validate_symbols([]) == {}


# ── the price grid, the policy, and the shape the suite consumes ────────────────────────────────
@pytest.mark.parametrize("sz_decimals,tick", [(5, 0.1), (1, 1e-5), (0, 1e-6)])
def test_tick_size_is_the_venue_rule(sz_decimals, tick):
    """`10 ** -(6 - szDecimals)`: BTC (5) quotes in tenths, a coin with 0 in millionths."""
    assert HyperliquidFeed.tick_size(sz_decimals) == tick


def test_prices_are_snapped_to_the_coin_tick_grid():
    assert HyperliquidFeed.price_decimals(5) == 1
    assert HyperliquidFeed.price_decimals(9) == 0, "the clamp keeps a future listing sane"

    async def main():
        frames = [_trades(_trade(px="75680.123456")), _book([(75680.123456, "1")], [(75681.9, "1")])]
        feed, _ws, ticks, books, session = await _run_feed(frames)
        await session.stop()
        return ticks, books

    ticks, books = asyncio.run(main())
    assert ticks[0][1].price == 75680.1, "a print is rounded onto the venue's own tick grid"
    assert books[-1][1].best_bid == 75680.1 and books[-1][1].best_ask == 75681.9


def test_the_adapter_uses_the_ping_after_idle_policy():
    policy = VENUE_POLICIES["hyperliquid"]
    assert policy.mode == "ping_after_idle", \
        "this venue pings us and expects an answer — the read must never be wrapped in a timeout"
    assert policy.ping_after_idle_s > 0 and policy.silence_budget_s > policy.ping_after_idle_s


def test_start_wires_the_session_to_that_policy(monkeypatch):
    import orderflow_system.data.hyperliquid_feed as mod

    captured = {}

    class RecordingSession:
        def __init__(self, venue, connect, on_frame, **kwargs):
            captured.update(venue=venue, connect=connect, on_frame=on_frame, kwargs=kwargs)

        async def run(self):
            return None

        async def stop(self):
            return None

        def stats(self):
            return {}

    monkeypatch.setattr(mod, "FeedSession", RecordingSession)
    feed = HyperliquidFeed(symbols=["BTCUSDT"])
    asyncio.run(feed.start())
    assert captured["venue"] == "hyperliquid"
    assert captured["kwargs"]["policy"] is VENUE_POLICIES["hyperliquid"]
    assert captured["on_frame"] == feed._on_frame
    assert captured["kwargs"]["on_connected"] == feed._on_connected
    assert captured["kwargs"]["on_disconnected"] == feed._on_disconnected
    assert json.loads(captured["kwargs"]["ping_payload"]) == {"method": "ping"}, \
        "the venue answers its documented JSON ping with a pong; the session sends that, not a string"


def test_nothing_wraps_the_read_loop():
    """The house rule this adapter must keep (data/feed_session.py): the reader is never cancelled,
    and this venue answers the library's ping frames by itself — so no read timeout may appear here.

    The pin is on a *call* (`wait_for(`), not the word: the adapter's own comment names the thing it
    forbids, and only the call can cancel a read mid-frame.
    """
    source = FEED_SRC.read_text(encoding="utf-8")
    assert "wait_for(" not in source, \
        "no asyncio.wait_for(...) around the read — cancelling mid-frame corrupts the assembler"
    assert "recv(" not in source, "reading frames is the session's job, not the adapter's"


def test_book_health_and_stats_carry_the_venue_shape():
    feed = HyperliquidFeed(symbols=["BTCUSDT", "ETHUSDT"])
    health = feed.book_health()
    assert health["venue"] == "hyperliquid"
    assert set(health) >= {"stale", "updates", "last_update_ms", "stale_marks", "junk_values",
                           "coins"}
    assert "seq" not in health, "a snapshot channel has no id chain to report"
    assert health["stale"] == ["BTCUSDT", "ETHUSDT"], "nothing seeded yet"
    assert health["coins"] == {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
    stats = feed.stats()
    assert stats["venue"] == "hyperliquid" and stats["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert set(stats["books"]) == {"BTCUSDT", "ETHUSDT"}
    assert HyperliquidFeed(symbols=["BTCUSDT"]).get_orderbook("BTCUSDT") is None
