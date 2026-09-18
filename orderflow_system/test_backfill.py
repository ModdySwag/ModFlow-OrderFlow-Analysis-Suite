"""The archive backfill — the parse, the window-replace rule, the cache and the guardrails.

No network: the archive is a zip built inside these tests, the download is a fake opener, and the
database is a scratch file. What is being pinned is the *contract* — that re-running a day cannot
double-count volume, that a half-download can never be mistaken for a cache hit, and that the
timestamp's unit is detected rather than assumed.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import zipfile
from pathlib import Path

import pytest

from orderflow_system.data import backfill as bf
from orderflow_system.data.database import Database
from orderflow_system.data.models import Side

DAY = dt.date(2026, 9, 13)
DAY_A = dt.date(2026, 9, 12)
DAY_B = dt.date(2026, 9, 13)
START_MS, END_MS = bf.day_window_ms(DAY)


def _csv_bytes(rows: list[list[str]], *, header: bool = True) -> bytes:
    lines = []
    if header:
        lines.append("agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker")
    for row in rows:
        lines.append(",".join(str(c) for c in row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _zip_bytes(csv_payload: bytes, member: str = "SYM-aggTrades-2026-09-13.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, csv_payload)
    return buf.getvalue()


def _row(tid: str, price: str, qty: str, ts_ms: int, buyer_maker: bool) -> list[str]:
    return [tid, price, qty, tid, tid, str(ts_ms), "true" if buyer_maker else "false"]


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self, n: int = -1) -> bytes:
        chunk, self.payload = self.payload[:n], self.payload[n:]
        return chunk

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def fake_opener(payload: bytes, calls: list[str]):
    def opener(url, timeout=None):
        calls.append(url)
        return FakeResponse(payload)
    return opener


def _write_zip(tmp_path: Path, payload: bytes, day: dt.date = DAY, symbol: str = "BTCUSDT") -> Path:
    path = bf.cache_path(symbol, day, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _run(coro):
    return asyncio.run(coro)


# ── urls, windows, timestamps ───────────────────────────────────────────────

def test_the_archive_url_is_the_published_layout():
    assert bf.daily_url("btcusdt", DAY) == (
        "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/"
        "BTCUSDT-aggTrades-2026-09-13.zip")
    assert "/spot/" in bf.daily_url("ETHUSDT", DAY, market="spot")
    with pytest.raises(ValueError):
        bf.daily_url("BTCUSDT", DAY, market="nonsense")


def test_the_day_window_is_utc_midnight_to_midnight():
    start, end = bf.day_window_ms(DAY)
    assert end - start == 86_400_000
    assert dt.datetime.fromtimestamp(start / 1000, dt.timezone.utc).isoformat() == \
        "2026-09-13T00:00:00+00:00"


def test_a_microsecond_archive_is_normalised_not_assumed():
    """Binance has moved datasets from ms to µs before: a silent ×1000 error would scatter a day."""
    assert bf.normalise_timestamp_ms(1_789_257_604_331) == 1_789_257_604_331        # already ms
    assert bf.normalise_timestamp_ms(1_789_257_604_331_000) == 1_789_257_604_331    # µs → ms


def test_a_bad_day_string_is_refused_with_the_shape_it_wants():
    assert bf.parse_day("2026-09-13") == DAY
    assert bf.parse_day(DAY) == DAY
    with pytest.raises(ValueError) as err:
        bf.parse_day("13/09/2026")
    assert "YYYY-MM-DD" in str(err.value)


# ── the parse ───────────────────────────────────────────────────────────────

def test_the_parser_reads_the_venue_conventions(tmp_path):
    payload = _csv_bytes([
        _row("1", "100.5", "2", START_MS + 10, buyer_maker=False),   # buyer aggressor
        _row("2", "100.4", "1.5", START_MS + 20, buyer_maker=True),  # seller aggressor
    ])
    path = _write_zip(tmp_path, _zip_bytes(payload))
    ticks = list(bf.read_agg_trades(path))
    assert [t.trade_id for t in ticks] == ["1", "2"]
    assert [t.side for t in ticks] == [Side.BUY, Side.SELL]
    assert ticks[0].price == 100.5 and ticks[0].size == 2.0


def test_the_headers_and_the_junk_lines_never_become_prints(tmp_path):
    payload = _csv_bytes([
        _row("1", "100.5", "2", START_MS + 10, buyer_maker=False),
        ["not-a-number", "1", "1", "1", "1", "1", "false"],         # a mangled trade id
        ["2", "100", "1", "2", "2", "1", "false"],                  # a timestamp from 1970
        ["3", "0", "1", "3", "3", str(START_MS + 20), "false"],     # a zero price
        ["4", "1", "-1", "4", "4", str(START_MS + 30), "false"],    # a negative size
        ["5", "1", "1", "5", "5", str(START_MS + 40)],              # a short line
    ])
    path = _write_zip(tmp_path, _zip_bytes(payload))
    assert [t.trade_id for t in bf.read_agg_trades(path)] == ["1"]


def test_the_window_filter_is_half_open(tmp_path):
    payload = _csv_bytes([
        _row("10", "1", "1", START_MS - 1, True),      # the last print of the previous day
        _row("11", "1", "1", START_MS, True),          # the first print of this day
        _row("12", "1", "1", START_MS + 5, True),
        _row("13", "1", "1", END_MS, True),            # the first print of the next day
    ])
    path = _write_zip(tmp_path, _zip_bytes(payload))
    ids = [t.trade_id for t in bf.read_agg_trades(path, since_ms=START_MS, until_ms=END_MS)]
    assert ids == ["11", "12"]


def test_an_archive_without_a_csv_is_an_error_not_an_empty_day(tmp_path):
    path = _write_zip(tmp_path, _zip_bytes(b"", member="readme.txt"))
    with pytest.raises(RuntimeError) as err:
        list(bf.read_agg_trades(path))
    assert "csv" in str(err.value)


# ── the download and the cache ──────────────────────────────────────────────

def test_a_download_lands_in_the_cache_and_the_second_call_reuses_it(tmp_path):
    payload = _zip_bytes(_csv_bytes([_row("1", "1", "1", START_MS + 1, True)]))
    calls: list[str] = []
    path, cached = bf.download_day("BTCUSDT", DAY, tmp_path, opener=fake_opener(payload, calls))
    assert path.is_file() and cached is False and len(calls) == 1
    again, cached_again = bf.download_day("BTCUSDT", DAY, tmp_path, opener=fake_opener(payload, calls))
    assert again == path and cached_again is True and len(calls) == 1, "the cache was not reused"
    assert not path.with_suffix(".part").exists(), "a .part file was left behind"


def test_a_half_download_is_never_a_cache_hit(tmp_path):
    """The bytes land in .part and are renamed only on completion — a truncated zip is invisible."""
    path = bf.cache_path("BTCUSDT", DAY, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".part").write_bytes(_zip_bytes(b"half"))
    payload = _zip_bytes(_csv_bytes([_row("1", "1", "1", START_MS + 1, True)]))
    calls: list[str] = []
    landed, cached = bf.download_day("BTCUSDT", DAY, tmp_path, opener=fake_opener(payload, calls))
    assert cached is False and len(calls) == 1 and landed.read_bytes() == payload


def test_an_empty_response_is_a_loud_failure(tmp_path):
    calls: list[str] = []
    with pytest.raises(RuntimeError) as err:
        bf.download_day("BTCUSDT", DAY, tmp_path, opener=fake_opener(b"", calls))
    assert "empty" in str(err.value)
    assert not bf.cache_path("BTCUSDT", DAY, tmp_path).exists()


def test_the_cache_is_pruned_by_age(tmp_path):
    fresh = _write_zip(tmp_path, b"x", day=DAY)
    old = _write_zip(tmp_path, b"x", day=DAY_A)
    stale = bf.cache_path("ETHUSDT", DAY, tmp_path)
    stale.write_bytes(b"x")
    long_ago = bf.time.time() - 10 * 86_400
    import os
    os.utime(old, (long_ago, long_ago))
    os.utime(stale, (long_ago, long_ago))
    part = bf.cache_path("BTCUSDT", DAY, tmp_path).with_suffix(".zip.part")
    part.write_bytes(b"half a download")
    os.utime(part, (long_ago, long_ago))
    removed = bf.prune_cache(tmp_path, keep_days=4)
    assert removed == 3, "half-downloads are swept too — nothing else ever cleans them"
    assert fresh.is_file() and not old.is_file() and not stale.is_file() and not part.is_file()


# ── the streaming and the pass ──────────────────────────────────────────────

def test_batches_stream_in_order_without_holding_the_whole_day(tmp_path):
    rows = [_row(str(i), "1", "1", START_MS + i, True) for i in range(11)]
    path = _write_zip(tmp_path, _zip_bytes(_csv_bytes(rows)))

    async def main():
        sizes = []
        ids = []
        async for chunk in bf._stream_batches(path, START_MS, END_MS, 5):
            sizes.append(len(chunk))
            ids.extend(t.trade_id for t in chunk)
        return sizes, ids

    sizes, ids = _run(main())
    assert sizes == [5, 5, 1], sizes
    assert ids == [str(i) for i in range(11)]


def test_a_backfill_replaces_its_window_and_cannot_double_count(tmp_path):
    """The one rule that keeps history honest: a day is replaced, not appended to."""
    payload = _zip_bytes(_csv_bytes([
        _row("1", "100", "2", START_MS + 10, False),
        _row("2", "101", "3", START_MS + 20, True),
    ]))
    opener = fake_opener(payload, [])
    db_path = tmp_path / "ticks.db"

    async def main():
        db = Database(str(db_path))
        await db.connect()
        # a row inside the day (a previous, partial pass) and one on the day before (untouchable)
        await db.insert_ticks_batch("BTCUSDT", [
            bf.Tick(timestamp_ms=START_MS + 15, price=99.0, size=1.0, side=Side.BUY, trade_id="stale"),
            bf.Tick(timestamp_ms=START_MS - 5000, price=98.0, size=1.0, side=Side.BUY, trade_id="before"),
        ])
        first = await bf.backfill_day(db, "BTCUSDT", DAY, cache_dir=tmp_path, opener=opener)
        second = await bf.backfill_day(db, "BTCUSDT", DAY, cache_dir=tmp_path, opener=opener)
        inside = await db.get_ticks("BTCUSDT", START_MS, END_MS - 1)
        before = await db.count_ticks("BTCUSDT", START_MS - 10_000, START_MS)
        await db.close()
        return first, second, inside, before

    first, second, inside, before = _run(main())
    assert first["ticks"] == 2 and first["deleted"] == 1, first
    assert second["ticks"] == 2, "a re-run wrote a different number of rows"
    assert len(inside) == 2, f"the window was appended to instead of replaced: {len(inside)} rows"
    assert "stale" not in [t.trade_id for t in inside], "the previous partial pass survived"
    assert before == 1, "a row outside the window was deleted"
    assert first["volume"] == 5.0 and first["first_ts"] == START_MS + 10 and first["last_ts"] == START_MS + 20


def test_the_progress_callback_reports_the_stages_without_being_able_to_break_the_pass(tmp_path):
    payload = _zip_bytes(_csv_bytes([_row("1", "1", "1", START_MS + 1, True)]))
    stages: list[str] = []

    def progress(stage, **fields):
        stages.append(stage)
        raise RuntimeError("a rude callback must not stop the backfill")

    async def main():
        db = Database(str(tmp_path / "ticks.db"))
        await db.connect()
        result = await bf.backfill_day(db, "BTCUSDT", DAY, cache_dir=tmp_path,
                                       opener=fake_opener(payload, []), progress=progress)
        await db.close()
        return result

    result = _run(main())
    assert result["ticks"] == 1
    assert stages[:2] == ["download", "parse"] and "done" in stages


# ── the range guardrails ────────────────────────────────────────────────────

def test_a_range_refuses_more_days_than_the_ceiling(tmp_path):
    days = [DAY - dt.timedelta(days=i) for i in range(bf.MAX_DAYS_PER_REQUEST + 1)]

    async def main():
        db = Database(str(tmp_path / "ticks.db"))
        await db.connect()
        try:
            with pytest.raises(ValueError) as err:
                await bf.backfill_range(db, "BTCUSDT", days, cache_dir=tmp_path)
            return str(err.value)
        finally:
            await db.close()

    message = _run(main())
    assert str(bf.MAX_DAYS_PER_REQUEST) in message


def test_a_range_refuses_the_future(tmp_path):
    tomorrow = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)

    async def main():
        db = Database(str(tmp_path / "ticks.db"))
        await db.connect()
        try:
            with pytest.raises(ValueError) as err:
                await bf.backfill_range(db, "BTCUSDT", [tomorrow], cache_dir=tmp_path)
            return str(err.value)
        finally:
            await db.close()

    message = _run(main())
    assert "does not publish" in message


def test_a_range_reports_the_days_that_carried_no_prints(tmp_path):
    quiet = _zip_bytes(_csv_bytes([]))
    busy = _zip_bytes(_csv_bytes([_row("1", "1", "1", START_MS + 1, True)]))
    calls: list[str] = []

    async def main():
        db = Database(str(tmp_path / "ticks.db"))
        await db.connect()
        try:
            # one day is present-but-empty, the other carries a print
            (tmp_path / "futures_um").mkdir(exist_ok=True)
            _write_zip(tmp_path, quiet, day=DAY_A)
            _write_zip(tmp_path, busy, day=DAY_B)
            result = await bf.backfill_range(db, "BTCUSDT", [DAY_A, DAY_B], cache_dir=tmp_path,
                                             opener=fake_opener(busy, calls), prune=False)
        finally:
            await db.close()
        return result

    result = _run(main())
    assert result["days"] == [DAY_A.isoformat(), DAY_B.isoformat()]
    assert result["days_without_prints"] == [DAY_A.isoformat()]
    assert result["ticks"] >= 1
