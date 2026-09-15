"""Order-book sequence integrity — the gate for sweep R3.

A dropped or reordered delta used to leave the local book silently wrong: `u` was read as a timestamp
and never checked, so the depth ladder, the heatmap and the wall alerts all traded on levels the venue
had already moved. These tests drive the feed's own handler with the real message shapes.
"""

from __future__ import annotations

import asyncio
import json

from orderflow_system.data.bybit_feed import BybitFeed

TOPIC = "orderbook.50.BTCUSDT"


class FakeWS:
    """Records what the feed would send back to the venue."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))


def _snapshot(u: int, bids, asks):
    return {"topic": TOPIC, "type": "snapshot", "data": {"u": u, "b": bids, "a": asks}}


def _delta(u: int, bids, asks=None):
    return {"topic": TOPIC, "type": "delta", "data": {"u": u, "b": bids, "a": asks or []}}


def _feed(seen=None):
    collected = seen if seen is not None else []

    async def on_book(symbol, book):
        collected.append(book)

    feed = BybitFeed(["BTCUSDT"], on_orderbook=on_book)
    feed._ws = FakeWS()
    return feed, collected


def test_a_sequence_gap_marks_the_book_stale_and_stops_applying_deltas():
    feed, seen = _feed()

    async def scenario():
        await feed._handle_orderbook(_snapshot(100, [["100.0", "1"]], [["101.0", "2"]]))
        await feed._handle_orderbook(_delta(101, [["100.0", "3"]]))
        assert feed._orderbooks["BTCUSDT"].bids[0].quantity == 3.0, "an in-order delta applies"
        assert feed._book_seq["BTCUSDT"] == 101

        # 102 never arrived: the next delta is a gap.
        await feed._handle_orderbook(_delta(103, [["100.0", "9"]]))
        book = feed._orderbooks["BTCUSDT"]
        assert book.stale is True, "a gap marks the book stale"
        assert book.bids[0].quantity == 3.0, "and the gapped delta is not applied"

        # deltas keep arriving while stale: dropped, never applied onto a book we know is wrong
        await feed._handle_orderbook(_delta(104, [["100.0", "50"]]))
        assert book.bids[0].quantity == 3.0

        # the fresh snapshot is what clears it
        await feed._handle_orderbook(_snapshot(105, [["100.0", "7"]], [["101.0", "2"]]))
        fresh = feed._orderbooks["BTCUSDT"]
        assert fresh.stale is False, "the snapshot clears the stale mark"
        assert fresh.bids[0].quantity == 7.0

    asyncio.run(scenario())

    health = feed.book_health()
    assert health["gaps"] == 1
    # the gap itself is a gap; only the deltas that followed it are counted as dropped
    assert health["dropped_deltas"] == 1, health
    assert health["stale"] == [], "the re-seeded book is healthy again"
    assert feed._ws.sent and feed._ws.sent[0]["op"] == "subscribe", \
        "a gap re-subscribes for a fresh snapshot"
    assert any(b.stale for b in seen), "the stale book was announced, not hidden"
    assert seen[-1].stale is False


def test_a_reordered_or_duplicate_delta_never_rewrites_a_newer_state():
    feed, _ = _feed()

    async def scenario():
        await feed._handle_orderbook(_snapshot(10, [["100.0", "1"]], []))
        # same update id: a replay. Applying it would write an old state over the same one.
        await feed._handle_orderbook(_delta(10, [["100.0", "99"]]))
        assert feed._orderbooks["BTCUSDT"].bids[0].quantity == 1.0
        # an older update id: a reorder. Same rule.
        await feed._handle_orderbook(_delta(9, [["100.0", "77"]]))
        assert feed._orderbooks["BTCUSDT"].bids[0].quantity == 1.0
        assert feed._orderbooks["BTCUSDT"].stale is False, "a reorder is dropped, not escalated"

    asyncio.run(scenario())
    assert feed.book_health()["dropped_deltas"] == 2


def test_a_delta_without_a_snapshot_is_ignored():
    feed, _ = _feed()

    async def scenario():
        await feed._handle_orderbook(_delta(500, [["100.0", "5"]]))
        assert "BTCUSDT" not in feed._orderbooks, "no snapshot, no book to update"
        assert feed.book_health()["gaps"] == 0, "and no gap is claimed out of nothing"

    asyncio.run(scenario())


def test_a_gap_on_one_symbol_does_not_touch_another():
    feed, _ = _feed()

    async def scenario():
        await feed._handle_orderbook(_snapshot(1, [["100.0", "1"]], []))
        await feed._handle_orderbook({"topic": "orderbook.50.ETHUSDT", "type": "snapshot",
                                      "data": {"u": 1, "b": [["10.0", "1"]], "a": []}})
        await feed._handle_orderbook(_delta(5, [["100.0", "2"]]))          # BTCUSDT gap
        assert feed._orderbooks["BTCUSDT"].stale is True
        assert feed._orderbooks["ETHUSDT"].stale is False, "the other book is untouched"

    asyncio.run(scenario())
    assert feed.book_health()["stale"] == ["BTCUSDT"]
