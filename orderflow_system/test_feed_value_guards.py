"""Value containment on the live feed path (secure2 sweep).

A venue frame is untrusted input. Python's `json` accepts the bare tokens `NaN` and
`Infinity`, and neither `float(x) <= 0` nor comparisons catch them (every comparison with
NaN is False) — so a malformed or hostile frame could carry a NaN/Infinity/negative price
or size straight into the footprint, delta and CVD aggregates, where it would poison every
number downstream and never raise. The same class of hole sat in the Alpaca normalisers:
`_num()` happily returned NaN and `price <= 0` waved it through.

These tests pin the containment on both feeds: junk values are dropped before analytics,
counted (so a bad socket is visible, not silent), and every legitimate frame is untouched.
"""

from __future__ import annotations

import asyncio
import json


def _bybit_feed():
    from orderflow_system.data.bybit_feed import BybitFeed

    ticks: list = []
    books: list = []

    async def on_tick(symbol, tick):
        ticks.append(tick)

    async def on_orderbook(symbol, book):
        books.append((symbol, book))

    return BybitFeed(symbols=["BTCUSDT"], on_tick=on_tick, on_orderbook=on_orderbook), ticks, books


def test_junk_trades_never_reach_the_analytics_path():
    """NaN / Infinity / non-positive price or size are dropped; the good print is not."""
    feed, ticks, _ = _bybit_feed()
    # Written as the venue would deliver it — including the bare NaN token json.loads accepts.
    raw = ('{"topic":"publicTrade.BTCUSDT","data":['
           '{"S":"Buy","T":1700000000000,"p":NaN,"v":1,"i":"nan-price"},'
           '{"S":"Buy","T":1700000000001,"p":Infinity,"v":1,"i":"inf-price"},'
           '{"S":"Sell","T":1700000000002,"p":-5,"v":1,"i":"neg-price"},'
           '{"S":"Buy","T":1700000000003,"p":100,"v":-1,"i":"neg-size"},'
           '{"S":"Buy","T":1700000000004,"p":100,"v":NaN,"i":"nan-size"},'
           '{"S":"Buy","T":1700000000005,"p":0,"v":1,"i":"zero-price"},'
           '{"S":"Buy","T":1700000000006,"p":100.5,"v":2,"i":"good"}]}')
    asyncio.run(feed._handle_trades(json.loads(raw)))
    assert [t.trade_id for t in ticks] == ["good"], [t.trade_id for t in ticks]
    assert feed.book_health()["junk_values"] == 6, "each dropped value is counted, not silent"


def test_junk_orderbook_levels_never_enter_the_book():
    """A snapshot's bad levels are skipped; a delta's bad cells change nothing."""
    feed, _, books = _bybit_feed()
    snapshot = {"topic": "orderbook.50.BTCUSDT", "type": "snapshot", "data": {
        "u": 100,
        "b": [["NaN", "1"], ["99.0", "2"], ["98.0", "-3"]],
        "a": [["101.0", "Infinity"], ["102.0", "4"]],
    }}
    asyncio.run(feed._handle_orderbook(snapshot))
    book = feed.get_orderbook("BTCUSDT")
    assert [lv.price for lv in book.bids] == [99.0], [lv.price for lv in book.bids]
    assert [lv.price for lv in book.asks] == [102.0], [lv.price for lv in book.asks]

    delta = {"topic": "orderbook.50.BTCUSDT", "type": "delta", "data": {
        "u": 101, "b": [["99.0", "NaN"], ["97.0", "5"]], "a": [["102.0", "-9"]],
    }}
    asyncio.run(feed._handle_orderbook(delta))
    book = feed.get_orderbook("BTCUSDT")
    assert [(lv.price, lv.quantity) for lv in book.bids] == [(99.0, 2.0), (97.0, 5.0)], \
        [(lv.price, lv.quantity) for lv in book.bids]
    assert [(lv.price, lv.quantity) for lv in book.asks] == [(102.0, 4.0)], \
        [(lv.price, lv.quantity) for lv in book.asks]


def test_alpaca_normalizers_refuse_non_finite_numbers():
    from orderflow_system.data.alpaca_normalize import normalize_bar, normalize_stock_trade

    ok = normalize_bar({"t": "2026-09-16T12:00:00Z", "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5,
                        "v": 3, "S": "AAPL"}, symbol="AAPL")
    assert ok and ok["close"] == 1.5, "a legitimate bar is untouched"

    for bad in (float("nan"), float("inf"), float("-inf")):
        frame = {"t": "2026-09-16T12:00:00Z", "o": 1.0, "h": 2.0, "l": 0.5, "c": bad,
                 "v": 3, "S": "AAPL"}
        assert normalize_bar(frame, symbol="AAPL") is None, f"a {bad!r} close must not become a candle"
        trade = {"T": "t", "S": "AAPL", "i": 1, "p": bad, "s": 100, "t": "2026-09-16T12:00:00Z"}
        assert normalize_stock_trade(trade) is None, f"a {bad!r} print must not become a tick"

    # a NaN size on an otherwise valid print becomes a 0-size tick (the shape the feed
    # already uses for "no size"), never NaN
    soft = normalize_stock_trade({"T": "t", "S": "AAPL", "i": 2, "p": 182.4, "s": float("nan"),
                                  "t": "2026-09-16T12:00:00Z"})
    assert soft is not None and soft.size == 0.0, soft
