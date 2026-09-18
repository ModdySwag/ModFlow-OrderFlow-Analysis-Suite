"""Pins for the MT5 feed's DOM parsing and its server-clock handling.

Written after the real-terminal verification (2026-09-17) caught the feed reading
``volume_real`` off BookInfo objects that have never had it: a live MetaQuotes-Demo
terminal, package 5.0.6180, exposed ``BookInfo(type, price, volume, volume_dbl)`` and
every DOM poll raised — killing the book silently behind one ERROR per cycle. The
helper must read whatever the installed package actually exposes, and fall back
cleanly for the older documented shapes.

The clock pins (2026-09-18) answer the same terminal's other habit: MT5 stamps ticks
with the terminal's SERVER clock (that demo runs UTC+3), so a raw ``time_msc`` stored
as an epoch put every MT5 row three hours into the future — candle buckets, session
windows and the freshness ages all read a skew that never existed. The feed learns the
offset from the freshest tick it can see and stores UTC. These tests use a stub module
(a list of dict rows), so no terminal is needed.
"""

from __future__ import annotations

import asyncio
import time
import types
from collections import namedtuple
from datetime import datetime, timezone

import pytest

from orderflow_system.data.mt5_feed import MT5Feed, _book_quantity


def test_book_quantity_reads_volume_dbl() -> None:
    e = types.SimpleNamespace(type=1, price=1.15, volume=2_000_000, volume_dbl=2_000_000.0)
    assert _book_quantity(e) == 2_000_000.0


def test_book_quantity_reads_legacy_volume_real() -> None:
    old_book_info = namedtuple("MqlBookInfo", "type price volume volume_real")
    e = old_book_info(2, 1.15, 0, 1500.0)
    assert _book_quantity(e) == 1500.0


def test_book_quantity_falls_back_to_integer_volume() -> None:
    e = types.SimpleNamespace(type=2, price=1.15, volume=75)
    assert _book_quantity(e) == 75.0


def test_book_quantity_zero_when_nothing_usable() -> None:
    e = types.SimpleNamespace(type=1, price=1.15, volume=0)
    assert _book_quantity(e) == 0.0


def test_book_quantity_reads_the_installed_packages_book_info() -> None:
    """The shape pin: whatever MetaTrader5 the environment ships must parse to its volume."""
    mt5 = pytest.importorskip("MetaTrader5")
    try:
        # BookInfo is a structseq: construct from the value sequence, in field order
        # (type, price, volume, volume_dbl) — measured on package 5.0.6180.
        entry = mt5.BookInfo((1, 1.23456, 42, 42.5))
    except TypeError:  # pragma: no cover - other package builds
        pytest.skip("this BookInfo build is not constructible directly")
    assert _book_quantity(entry) in (42.0, 42.5)  # int lots or the float twin
# ── The server clock (learned offset → UTC stamps) ────────────────────────────────────────────


class _FakeMT5:
    """The stub module surface the feed touches: copy_ticks_*/copy_rates_range + ONE tick."""

    COPY_TICKS_ALL = 0
    TIMEFRAME_M1 = 1

    def __init__(self, rows=(), bars=(), tick=None):
        self._rows = list(rows)
        self._bars = list(bars)
        self._tick = tick

    def copy_ticks_from(self, symbol, from_dt, count, kind):
        return self._rows

    def copy_ticks_range(self, symbol, from_dt, to_dt, kind):
        return self._rows

    def copy_rates_range(self, symbol, timeframe, from_dt, to_dt):
        return self._bars

    def symbol_info_tick(self, symbol):
        return self._tick


def _make_feed(fake, on_tick=None):
    feed = MT5Feed(symbols={"NAS100USDT": "USTEC"}, on_tick=on_tick,
                   enable_book=False, poll_interval_ms=1)
    feed._mt5 = fake
    feed._initialized = True
    return feed


def _row(time_msc, *, last=23_450.5):
    return {"time_msc": time_msc, "flags": 0x20, "last": last, "bid": last - 0.5,
            "ask": last + 0.5, "volume_real": 2.0, "volume": 2}


def test_a_live_batch_is_stored_in_utc_not_server_time() -> None:
    """A broker at UTC+3 stamps +3 h; the stored tick must be the real (UTC) instant."""
    now_ms = int(time.time() * 1000)
    three_h = 3 * 3600_000
    feed = _make_feed(_FakeMT5(rows=[_row(now_ms + three_h - 400, last=1.0)]))
    got = []

    async def on_tick(symbol, tick):
        got.append((symbol, tick))

    feed.on_tick = on_tick
    asyncio.run(feed._poll_ticks("NAS100USDT", "USTEC"))

    assert feed._clock_offset_ms == three_h, "the +3 h server clock must be learned"
    assert len(got) == 1
    assert abs(got[0][1].timestamp_ms - now_ms) < 60_000, "stored stamp must be ~now, not +3 h"


def test_the_poll_window_stays_in_server_time() -> None:
    """The resume marker keeps the RAW server stamp — copy_ticks_from() speaks server time."""
    now_ms = int(time.time() * 1000)
    stamp = now_ms + 3 * 3600_000
    feed = _make_feed(_FakeMT5(rows=[_row(stamp)]))
    asyncio.run(feed._poll_ticks("NAS100USDT", "USTEC"))
    assert feed._last_tick_time["NAS100USDT"] == stamp


def test_an_implausible_offset_is_refused() -> None:
    """Nothing beyond 14 h is a broker offset — refuse it rather than skew every row."""
    feed = _make_feed(_FakeMT5())
    feed._note_clock(int(time.time() * 1000) + 20 * 3600_000)
    assert feed._clock_offset_ms is None


def test_a_stale_print_never_lowers_the_learned_offset() -> None:
    """A quiet symbol's old print understates the offset; the learned value must not follow it."""
    feed = _make_feed(_FakeMT5())
    now_ms = int(time.time() * 1000)
    feed._note_clock(now_ms + 3 * 3600_000)
    feed._note_clock(now_ms + 1 * 3600_000)          # an hour-old print
    assert feed._clock_offset_ms == 3 * 3600_000


def test_the_connect_probe_learns_the_offset_from_symbol_info_tick() -> None:
    """_initialize_mt5's probe: the stub's one fresh tick sets the offset before any batch."""
    now_ms = int(time.time() * 1000)
    tick = types.SimpleNamespace(time_msc=now_ms + 2 * 3600_000)
    feed = MT5Feed(symbols={"NAS100USDT": "USTEC"}, enable_book=False)
    feed._mt5 = _FakeMT5(tick=tick)
    feed._note_clock(feed._newest_visible_tick_ms())
    assert feed._clock_offset_ms == 2 * 3600_000


def test_historical_downloads_convert_with_the_learned_offset() -> None:
    """Backfilled ticks AND bars land in UTC too — the same skew would poison a profile."""
    now_ms = int(time.time() * 1000)
    three_h = 3 * 3600_000
    bar_time_s = (now_ms + three_h) // 1000 - 60
    fake = _FakeMT5(
        rows=[_row(now_ms + three_h - 1000, last=1.0)],
        bars=[{"time": bar_time_s, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15,
               "real_volume": 0, "tick_volume": 5}],
    )
    feed = _make_feed(fake)
    feed._clock_offset_ms = three_h

    ticks = asyncio.run(feed.download_historical_ticks(
        "USTEC", datetime.now(timezone.utc), datetime.now(timezone.utc)))
    assert [t.timestamp_ms for t in ticks] == [now_ms - 1000]

    candles = asyncio.run(feed.download_historical_candles(
        "USTEC", fake.TIMEFRAME_M1, datetime.now(timezone.utc), datetime.now(timezone.utc)))
    assert candles[0].timestamp_ms == bar_time_s * 1000 - three_h


def test_to_utc_ms_is_identity_until_an_offset_is_learned() -> None:
    feed = _make_feed(_FakeMT5())
    assert feed.to_utc_ms(123) == 123
    feed._clock_offset_ms = 3 * 3600_000
    assert feed.to_utc_ms(3 * 3600_000 + 123) == 123
def test_a_print_with_no_volume_is_carried_as_one_lot_and_counted() -> None:
    """A zero-size fill is unusable for order flow, so it becomes 1 lot — but the substitution is
    counted (an invented 1 must not be indistinguishable from a real one)."""
    now_ms = int(time.time() * 1000)
    row = _row(now_ms - 500, last=1.0)
    row["volume_real"] = 0.0
    row["volume"] = 0
    got = []

    async def on_tick(symbol, tick):
        got.append(tick)

    feed = _make_feed(_FakeMT5(rows=[row]))
    feed.on_tick = on_tick
    asyncio.run(feed._poll_ticks("NAS100USDT", "USTEC"))

    assert [t.size for t in got] == [1.0]
    assert feed._volume_defaulted == 1
