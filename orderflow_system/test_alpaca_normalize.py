"""Alpaca normalisation fixtures (plan T21) — recorded message shapes, no network.

One fixture per message family, in the exact field names Alpaca publishes, so a
field rename on their side fails here rather than silently producing an empty tape.
"""

from __future__ import annotations

import pytest

from orderflow_system.data.alpaca_normalize import (
    classify_side,
    normalize_bar,
    normalize_crypto_trade,
    normalize_options_trade,
    normalize_quote,
    normalize_snapshot_quote,
    normalize_snapshot_trade,
    normalize_stock_trade,
    parse_ts_ms,
)
from orderflow_system.data.models import Side

# ── recorded shapes (trimmed to the fields we read) ─────────────────────

STOCK_TRADE = {"T": "t", "S": "AAPL", "i": 52983525029461, "x": "D", "p": 182.42, "s": 100,
               "c": ["@", "T"], "z": "C", "t": "2026-09-15T13:30:00.123456789Z"}
STOCK_QUOTE = {"T": "q", "S": "AAPL", "bx": "V", "bp": 182.40, "bs": 3, "ax": "Q", "ap": 182.44,
               "as": 5, "c": ["R"], "z": "C", "t": "2026-09-15T13:30:00.500Z"}
CRYPTO_TRADE = {"T": "t", "S": "BTC/USD", "p": 60123.45, "s": 0.0031, "t": "2026-09-15T13:30:01.000Z",
                "i": 12345678, "tks": "B"}
CRYPTO_QUOTE = {"T": "q", "S": "BTC/USD", "bp": 60120.0, "bs": 0.5, "ap": 60126.0, "as": 0.4,
                "t": "2026-09-15T13:30:01.100Z"}
OPTIONS_TRADE = {"T": "t", "S": "SPY260116C00450000", "x": "P", "p": 12.35, "s": 5, "c": ["I"],
                 "t": "2026-09-15T14:00:02.000000Z"}
BAR = {"T": "b", "S": "AAPL", "o": 182.10, "h": 182.55, "l": 182.02, "c": 182.42, "v": 151234,
       "n": 902, "vw": 182.33, "t": "2026-09-15T13:30:00Z"}
SNAPSHOT = {"latestTrade": STOCK_TRADE, "latestQuote": STOCK_QUOTE,
            "minuteBar": BAR, "dailyBar": BAR, "prevDailyBar": BAR}


# ── timestamps ──────────────────────────────────────────────────────────

def test_parse_timestamp_variants():
    assert parse_ts_ms("2026-09-15T13:30:00Z") == 1789479000000
    assert parse_ts_ms("2026-09-15T13:30:00.123456789Z") == 1789479000123     # ns truncated to ms
    assert parse_ts_ms("2026-09-15 13:30:00+00:00") == 1789479000000
    assert parse_ts_ms(1789479000) == 1789479000000                          # epoch seconds
    assert parse_ts_ms(1789479000123) == 1789479000123                       # epoch ms
    assert parse_ts_ms("") == 0 and parse_ts_ms(None) == 0
    assert parse_ts_ms("not a date") == 0


# ── side classification ─────────────────────────────────────────────────

def test_side_prefers_the_venue_tick_side():
    assert classify_side(100.0, mid=100.5, tick_side="B") == Side.BUY
    assert classify_side(101.0, mid=100.5, tick_side="S") == Side.SELL     # venue wins over the mid


def test_side_falls_back_to_the_tick_rule():
    assert classify_side(100.6, mid=100.5) == Side.BUY
    assert classify_side(100.5, mid=100.5) == Side.BUY                     # at the mid = buy
    assert classify_side(100.4, mid=100.5) == Side.SELL
    assert classify_side(100.0, mid=None) == Side.BUY                      # documented default


# ── trades ──────────────────────────────────────────────────────────────

def test_stock_trade_normalises_to_tick():
    tick = normalize_stock_trade(STOCK_TRADE, mid=182.41)
    assert tick is not None
    assert (tick.price, tick.size) == (182.42, 100.0)
    assert tick.timestamp_ms == 1789479000123
    assert tick.side == Side.BUY                       # above the mid
    assert tick.trade_id == "52983525029461"


def test_crypto_trade_uses_tick_side_and_never_invents_one():
    tick = normalize_crypto_trade(CRYPTO_TRADE, mid=60123.0)
    assert tick is not None and tick.side == Side.BUY and tick.trade_id == "12345678"
    # without tks the mid decides
    no_tks = dict(CRYPTO_TRADE)
    no_tks.pop("tks")
    assert normalize_crypto_trade(no_tks, mid=60123.0).side == Side.BUY
    assert normalize_crypto_trade(no_tks, mid=60200.0).side == Side.SELL


def test_options_trade_normalises_to_tick():
    tick = normalize_options_trade(OPTIONS_TRADE, mid=12.30)
    assert tick is not None and tick.price == 12.35 and tick.side == Side.BUY


def test_junk_trades_are_dropped_not_guessed():
    assert normalize_stock_trade({}) is None
    assert normalize_stock_trade({"T": "t", "p": 0, "s": 10}) is None
    assert normalize_stock_trade({"T": "t", "p": None}) is None
    assert normalize_stock_trade("not a dict") is None
    # A trade with no usable timestamp is dropped, not stamped 1970: a print inside the live
    # bar carried forward a phantom print (audit D-06). normalize_bar already rejected ts == 0.
    assert normalize_stock_trade({"T": "t", "S": "AAPL", "p": "182.5", "s": "7"}) is None
    stamped = normalize_stock_trade({"T": "t", "S": "AAPL", "p": "182.5", "s": "7",
                                     "t": "2026-09-15T13:30:00Z"})
    assert stamped is not None and stamped.price == 182.5 and stamped.size == 7.0


# ── quotes ──────────────────────────────────────────────────────────────

def test_stock_quote_normalises():
    q = normalize_quote(STOCK_QUOTE)
    assert q is not None
    assert (q.bid_price, q.ask_price) == (182.40, 182.44)
    assert (q.bid_size, q.ask_size) == (3.0, 5.0)
    assert q.symbol == "AAPL" and q.timestamp_ms == 1789479000500
    assert q.mid == pytest.approx(182.42) and q.spread == pytest.approx(0.04)
    assert q.is_valid()


def test_quote_edges():
    assert normalize_quote({}) is None
    one_sided = normalize_quote({"T": "q", "S": "AAPL", "bp": 182.4, "bs": 1, "t": "2026-09-15T13:30:00Z"})
    assert one_sided is not None and one_sided.ask_price == 0.0
    assert not one_sided.is_valid()                       # unusable for classification
    assert one_sided.mid == 182.4                         # but the mid still reads
    crossed = normalize_quote({"bp": 182.5, "ap": 182.4})
    assert crossed.spread == pytest.approx(-0.1) and not crossed.is_valid()


# ── snapshot + bars ─────────────────────────────────────────────────────

def test_snapshot_helper_unwraps_last_trade_and_quote():
    tick = normalize_snapshot_trade(SNAPSHOT, symbol="AAPL")
    quote = normalize_snapshot_quote(SNAPSHOT, symbol="AAPL")
    assert tick is not None and tick.price == 182.42
    assert quote is not None and quote.symbol == "AAPL"
    assert normalize_snapshot_trade({}, symbol="AAPL") is None
    assert normalize_snapshot_quote({"latestQuote": None}, symbol="AAPL") is None


def test_bar_maps_to_the_internal_chart_shape():
    row = normalize_bar(BAR, symbol="AAPL")
    assert row is not None
    assert row["time"] == 1789479000 and row["timestamp_ms"] == 1789479000000
    assert row["open"] == 182.10 and row["close"] == 182.42 and row["volume"] == 151234.0
    assert row["trades"] == 902 and row["vwap"] == pytest.approx(182.33)
    assert row["symbol"] == "AAPL"
    assert normalize_bar({"t": "2026-09-15T13:30:00Z", "c": 0}) is None
    assert normalize_bar(None) is None
