"""Historical trades from the venue's public archive — the tick store's past, filled honestly.

Every panel in this suite is a live view: open the app at 09:00 and there is no order flow from the
overnight session, and a study that wants last week's volume has nothing to read. Binance publishes
daily aggTrade archives on data.binance.vision, so the fix is a download, a parse and an insert —
with four rules that keep it honest:

  · **A window is replaced, never appended.** The delete and the insert happen for the same window,
    so re-running a day (or resuming an interrupted one) can never double-count volume in profiles,
    delta lanes or any study that reads history.
  · **Nothing live is touched.** Rows go in *behind* the live head; the feed's own writes and the
    newest ticks are never deleted, and one pass covers one day.
  · **The timestamp's unit is detected, not assumed.** Binance has moved datasets from milliseconds
    to microseconds before; a 16-digit value is µs and gets normalised, because a silent ×1000 error
    would scatter a day of prints across a month.
  · **The cache is a cache.** Zips live in a scratch directory, are written through a `.part` file
    (so a half-download can never be mistaken for a cache hit) and are pruned after a few days.

Verified against the live archive on 2026-09-16: the futures/um daily file is a single CSV member
named `<SYMBOL>-aggTrades-<YYYY-MM-DD>.csv` with a header row and the columns
`agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker`
(13-digit millisecond timestamps in that file).
"""

from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import logging
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional

from orderflow_system.data.database import Database
from orderflow_system.data.models import Side, Tick

logger = logging.getLogger(__name__)

#: Where the archive lives. Only these two markets are published with this layout.
ARCHIVE_BASE = "https://data.binance.vision/data"
MARKETS = ("futures/um", "spot")

#: One pass covers one day; a request may ask for a handful of days, never a month. Downloads are
#: hundreds of megabytes each for the liquid instruments — this is a deliberate ceiling, not a bug.
MAX_DAYS_PER_REQUEST = 7

#: Rows per database transaction. Large enough to be fast, small enough that a cancel is felt quickly.
BATCH_ROWS = 5_000

#: Cache retention: the last few days of zips stay on disk so a re-run (or a second instrument's
#: pass) costs no bandwidth; older ones are pruned by mtime.
CACHE_KEEP_DAYS = 4

#: A timestamp this large is microseconds: ms values are 13 digits, µs values are 16.
_MICROSECOND_CUTOFF = 10 ** 14

#: Anyone whose archive row claims a print happened before this is looking at a mangled line, not at
#: history: USDⓈ-M futures opened in September 2019. A junk row must never become a print — that is
#: how a garbled download silently poisons a volume profile.
MIN_PLAUSIBLE_MS = 1_560_000_000_000


def daily_url(symbol: str, day: dt.date, *, market: str = "futures/um") -> str:
    """The archive URL for one symbol-day, e.g. …/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-…zip."""
    if market not in MARKETS:
        raise ValueError(f"unknown archive market: {market!r}")
    sym = str(symbol).upper()
    return f"{ARCHIVE_BASE}/{market}/daily/aggTrades/{sym}/{sym}-aggTrades-{day.isoformat()}.zip"


def day_window_ms(day: dt.date) -> tuple[int, int]:
    """The half-open millisecond window [00:00, 24:00) UTC for a day."""
    start = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def parse_day(day: str | dt.date) -> dt.date:
    """Accept 'YYYY-MM-DD' (what the API sends) or a date."""
    if isinstance(day, dt.date):
        return day
    text = str(day).strip()
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"a day must be YYYY-MM-DD, got {text!r}") from exc


def normalise_timestamp_ms(raw: int) -> int:
    """Detect µs archives and hand back milliseconds.

    A 16-digit value cannot be a millisecond timestamp in this century, and a 13-digit one cannot be
    microseconds; anything else is passed through untouched rather than guessed at.
    """
    value = int(raw)
    if value > _MICROSECOND_CUTOFF:
        return value // 1000
    return value


# ── the download ─────────────────────────────────────────────────────────────

def cache_path(symbol: str, day: dt.date, cache_dir: Path, *, market: str = "futures/um") -> Path:
    return Path(cache_dir) / market.replace("/", "_") / f"{str(symbol).upper()}-{day.isoformat()}.zip"


def download_day(symbol: str, day: dt.date, cache_dir: Path, *, market: str = "futures/um",
                 timeout: float = 180.0, opener: Callable[..., Any] = urllib.request.urlopen) -> tuple[Path, bool]:
    """Fetch (or reuse) one day's archive. Returns (path, came_from_cache).

    The bytes land in a `.part` file first and are renamed only when the download is complete, so an
    interrupted run can never leave a truncated zip behind that the next run happily parses.
    """
    dest = cache_path(symbol, day, cache_dir, market=market)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest, True
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = daily_url(symbol, day, market=market)
    part = dest.with_suffix(".part")
    logger.info("backfill: downloading %s", url)
    with opener(url, timeout=timeout) as response, open(part, "wb") as sink:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            sink.write(chunk)
    if part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"the archive for {symbol} {day} came back empty")
    part.replace(dest)
    return dest, False


# ── the parse ────────────────────────────────────────────────────────────────

def read_agg_trades(zip_path: Path, *, since_ms: Optional[int] = None, until_ms: Optional[int] = None,
                    market: str = "futures/um") -> Iterator[Tick]:
    """Stream the archive's trades as Ticks, filtered to [since_ms, until_ms).

    Mirrors the live feed's conventions exactly (the archive's `is_buyer_maker` is the same flag the
    websocket sends: true means the aggressor was the seller), so a backfilled row and a live row are
    indistinguishable downstream — which is the whole point of backfilling.
    """
    with zipfile.ZipFile(str(zip_path)) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RuntimeError(f"{zip_path.name} carries no csv member")
        with archive.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            reader = csv.reader(text)
            for row in reader:
                if not row or len(row) < 7:
                    continue
                try:
                    trade_id = int(row[0])          # a real archive row always numbers its trades
                    price = float(row[1])
                    size = float(row[2])
                    ts = normalise_timestamp_ms(row[5])
                except (TypeError, ValueError):
                    continue                       # the header row, or a malformed line
                if ts < MIN_PLAUSIBLE_MS:
                    continue                       # a mangled line, not a print from 1970
                if not (price > 0.0 and size > 0.0):
                    continue
                if since_ms is not None and ts < since_ms:
                    continue
                if until_ms is not None and ts >= until_ms:
                    continue
                side = Side.SELL if str(row[6]).strip().lower() == "true" else Side.BUY
                yield Tick(timestamp_ms=ts, price=price, size=size, side=side, trade_id=str(trade_id))


async def _stream_batches(zip_path: Path, start_ms: int, end_ms: int, batch: int, *,
                          market: str = "futures/um"):
    """Parse the archive in a worker thread and hand batches back to the event loop, one at a time.

    A day of a liquid instrument is millions of rows: parsing it on the event loop would freeze every
    panel for seconds, and parsing it into a list would put a gigabyte in memory. So one worker
    thread produces into a small bounded queue and this coroutine drains it — backpressure included,
    which is what stops a fast parse from outrunning a slow disk.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=4)

    def produce() -> None:
        try:
            chunk: list[Tick] = []
            for tick in read_agg_trades(zip_path, since_ms=start_ms, until_ms=end_ms, market=market):
                chunk.append(tick)
                if len(chunk) >= batch:
                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
                    chunk = []
            if chunk:
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    producer = asyncio.create_task(asyncio.to_thread(produce))
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        # A consumer that stops early must not leave the producer wedged with a full queue.
        while not queue.empty():
            queue.get_nowait()
        try:
            await producer
        except Exception:
            pass


# ── the cache ────────────────────────────────────────────────────────────────

def prune_cache(cache_dir: Path, *, keep_days: int = CACHE_KEEP_DAYS, now: Optional[float] = None) -> int:
    """Delete cached archives older than `keep_days` (by mtime). Returns how many files went.

    `*.part` half-downloads go with them: the `.part` → final rename only happens on success, so
    a fetch that died mid-way leaves a file nothing else ever cleans.
    """
    root = Path(cache_dir)
    if not root.is_dir():
        return 0
    horizon = (now if now is not None else time.time()) - keep_days * 86_400
    removed = 0
    for pattern in ("*.zip", "*.part"):
        for path in sorted(root.rglob(pattern)):
            try:
                if path.stat().st_mtime < horizon:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
    return removed


# ── the pass ─────────────────────────────────────────────────────────────────

async def backfill_day(db: Database, symbol: str, day: dt.date, *, market: str = "futures/um",
                       cache_dir: Optional[Path] = None, since_ms: Optional[int] = None,
                       until_ms: Optional[int] = None, batch: int = BATCH_ROWS,
                       opener: Callable[..., Any] = urllib.request.urlopen,
                       progress: Optional[Callable[..., None]] = None) -> dict[str, Any]:
    """Replace one day of stored history for one instrument from the public archive.

    `since_ms`/`until_ms` narrow the window *inside* the day (both default to the whole day). The
    delete and the inserts use the same half-open window, so the pass is idempotent.
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(".")
    day_start, day_end = day_window_ms(day)
    start = max(day_start, int(since_ms)) if since_ms is not None else day_start
    end = min(day_end, int(until_ms)) if until_ms is not None else day_end
    if end <= start:
        raise ValueError(f"empty window for {symbol} {day}: [{start}, {end})")

    def note(stage: str, **fields: Any) -> None:
        if progress is not None:
            try:
                progress(stage, symbol=symbol, day=day.isoformat(), **fields)
            except Exception as exc:               # progress is a courtesy, never a failure mode
                logger.debug("backfill progress callback failed: %s", exc)

    note("download")
    path, cached = await asyncio.to_thread(download_day, symbol, day, cache_dir,
                                          market=market, opener=opener)
    note("parse", cached=cached, bytes=path.stat().st_size)

    written = 0
    total_volume = 0.0
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None

    # The window is cleared first and the inserts follow in batches; a crash mid-pass leaves the day
    # partial and the next run replaces it wholesale, so no state can be half-applied forever.
    deleted = await db.delete_ticks_window(symbol, start, end)
    async for chunk in _stream_batches(path, start, end, batch, market=market):
        await db.insert_ticks_batch(symbol, chunk)
        written += len(chunk)
        total_volume += sum(t.size for t in chunk)
        first_ts = chunk[0].timestamp_ms if first_ts is None else first_ts
        last_ts = chunk[-1].timestamp_ms
        note("write", ticks=written)

    note("done", ticks=written, deleted=deleted)
    return {
        "symbol": str(symbol).upper(),
        "day": day.isoformat(),
        "ticks": written,
        "deleted": deleted,
        "volume": round(total_volume, 6),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "cached": cached,
        "bytes": path.stat().st_size,
    }


async def backfill_range(db: Database, symbol: str, days: Iterable[dt.date], *,
                         market: str = "futures/um", cache_dir: Optional[Path] = None,
                         prune: bool = True,
                         opener: Callable[..., Any] = urllib.request.urlopen,
                         progress: Optional[Callable[..., None]] = None) -> dict[str, Any]:
    """Backfill a handful of days for one instrument, newest last.

    Refuses more than `MAX_DAYS_PER_REQUEST` days and refuses days that have not happened yet: the
    archive does not publish the future, and a request that asks for it is a caller bug worth
    reporting rather than a silent no-op.
    """
    ordered = sorted({parse_day(d) for d in days})
    if not ordered:
        raise ValueError("no days requested")
    if len(ordered) > MAX_DAYS_PER_REQUEST:
        raise ValueError(f"at most {MAX_DAYS_PER_REQUEST} days per request, got {len(ordered)}")
    today = dt.datetime.now(dt.timezone.utc).date()
    future = [d for d in ordered if d >= today]
    if future:
        raise ValueError(f"the archive does not publish {', '.join(d.isoformat() for d in future)}")

    cache_dir = Path(cache_dir) if cache_dir else Path(".")
    results = []
    for day in ordered:
        results.append(await backfill_day(db, symbol, day, market=market, cache_dir=cache_dir,
                                          opener=opener, progress=progress))
    failed = [r for r in results if r.get("ticks") == 0]
    if prune:
        await asyncio.to_thread(prune_cache, cache_dir)
    return {
        "symbol": str(symbol).upper(),
        "days": [r["day"] for r in results],
        "ticks": sum(r["ticks"] for r in results),
        "deleted": sum(r["deleted"] for r in results),
        "days_without_prints": [r["day"] for r in failed],
        "detail": results,
    }
