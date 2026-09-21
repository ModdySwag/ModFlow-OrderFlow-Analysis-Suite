"""Data port (R8): your own history out in the format everyone reads, other people's history in.

The suite already exports CSVs from its panels and backs the database up whole (R6). What was
missing is the other direction: a trader who owns years of ticks — from this app's own backups, an
MT5 export, a Sierra ``.itxt``, a Databento download — could not get them into the views they
analyse with. This module is the parser half of that door, plus the encoder for bulk tick/candle
exports, and it follows the formats the rest of the industry uses:

* timestamps accepted as epoch seconds, epoch milliseconds or ISO 8601 (``Z``, ``+02:00``, a space
  instead of ``T``) — every export anyone hands you uses one of the three;
* a header row with the app's own column names, or the common aliases (``time``, ``price``,
  ``qty``, ``side``, ``volume``…), or no header at all when the column count is unambiguous;
* delimiter sniffed from the file (comma, semicolon, tab), because European exports use semicolons;
* every bad row is counted with a reason, never silently dropped, and nothing here raises on junk.

Encoding is RFC 4180: CRLF rows, a header line, ISO 8601 UTC stamps — the same shape this app's
backups write, so an export can be re-imported (``test_dataport.py`` pins that round trip).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

#: The columns a ticks export carries, in order. The database's own names, so nobody has to learn
#: a second vocabulary to read our files.
TICK_COLUMNS = ("instrument", "timestamp_ms", "price", "size", "side", "trade_id")
CANDLE_COLUMNS = ("instrument", "timestamp_ms", "timeframe", "open", "high", "low", "close", "volume")

_TS_ALIASES = ("timestamp_ms", "timestamp", "time", "ts", "date", "datetime", "time_ms", "t")
_PRICE_ALIASES = ("price", "last", "close", "px")
_SIZE_ALIASES = ("size", "qty", "quantity", "volume", "amount", "vol")
_SIDE_ALIASES = ("side", "direction", "aggressor", "buyer_maker_side")
_ID_ALIASES = ("trade_id", "id", "tid", "tradeid")

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")


def parse_timestamp(value: Any) -> Optional[int]:
    """Any of the three timestamp dialects -> epoch milliseconds, or None. Pure.

    Epoch values are told apart by magnitude (seconds < 1e11, microseconds > 1e15); ISO strings are
    parsed with their offset honoured and reported in UTC.
    """
    if value is None:
        return None
    text = str(value).strip().strip('"')
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        number = None
    if number is not None:
        if number >= 1e15:                      # microseconds
            return int(number / 1000)
        if number >= 1e11:                      # milliseconds
            return int(number)
        if number > 0:                          # seconds
            return int(number * 1000)
        return None
    if not _ISO_RE.match(text):
        return None
    normalised = text.replace(" ", "T")
    if normalised.endswith("Z"):
        normalised = normalised[:-1] + "+00:00"
    if normalised.endswith(("+00", "-00")):     # "+00" is a legal ISO offset some tools emit
        normalised += ":00"
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def sniff(text: str, *, sample_lines: int = 5) -> dict[str, Any]:
    """Delimiter + header + a few sample rows — enough to parse without asking the user. Pure."""
    lines = [line for line in str(text or "").splitlines() if line.strip()][: max(1, sample_lines)]
    if not lines:
        return {"delimiter": ",", "headers": None, "sample": []}
    counts = {d: lines[0].count(d) for d in (",", ";", "\t", "|")}
    delimiter = max(counts, key=lambda d: counts[d]) if max(counts.values()) > 0 else ","
    first = next(csv.reader([lines[0]], delimiter=delimiter))
    header_hit = any(
        str(cell).strip().strip('"').lower() in
        set(_TS_ALIASES) | set(_PRICE_ALIASES) | set(_SIZE_ALIASES) | {"instrument", "symbol"}
        for cell in first
    )
    sample = list(csv.reader(lines[1:], delimiter=delimiter)) if header_hit else list(
        csv.reader(lines, delimiter=delimiter))
    return {"delimiter": delimiter,
            "headers": [str(c).strip().strip('"') for c in first] if header_hit else None,
            "sample": sample[: max(0, sample_lines - 1)]}


def _pick(headers: list[str], aliases: Iterable[str]) -> Optional[int]:
    lowered = [str(h).strip().lower() for h in headers]
    for alias in aliases:
        if alias in lowered:
            return lowered.index(alias)
    return None


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip().strip('"').strip()


def parse_ticks(text: str, *, symbol: str = "", delimiter: Optional[str] = None,
                has_header: Optional[bool] = None) -> dict[str, Any]:
    """A CSV of prints -> rows ready for the ticks table. Counts what it could not read. Pure."""
    info = sniff(text)
    sep = delimiter or info["delimiter"]
    rows = list(csv.reader(io.StringIO(str(text or "")), delimiter=sep))
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    headers = info["headers"] if has_header is None else (headers_from(rows[0]) if has_header else None)
    body = rows[1:] if headers else rows

    index = {"ts": _pick(headers, _TS_ALIASES) if headers else 0,
             "price": _pick(headers, _PRICE_ALIASES) if headers else 1,
             "size": _pick(headers, _SIZE_ALIASES) if headers else 2,
             "side": _pick(headers, _SIDE_ALIASES) if headers else 3,
             "id": _pick(headers, _ID_ALIASES) if headers else 4,
             "symbol": _pick(headers, ("instrument", "symbol", "ticker")) if headers else None}
    out: list[list[Any]] = []
    errors: list[str] = []
    seen: set[tuple] = set()
    deduped = 0
    for number, row in enumerate(body, start=1):
        if not row:
            continue
        record = {
            "instrument": symbol or (_clean(row[index["symbol"]]) if index["symbol"] is not None and index["symbol"] < len(row) else ""),
            "timestamp_ms": parse_timestamp(row[index["ts"]]) if index["ts"] is not None and index["ts"] < len(row) else None,
            "price": _float(row, index["price"]),
            "size": _float(row, index["size"]),
            "side": (_clean(row[index["side"]]).lower() if index["side"] is not None and index["side"] < len(row) else "") or "buy",
            "trade_id": (_clean(row[index["id"]]) if index["id"] is not None and index["id"] < len(row) else ""),
        }
        reason = _tick_problem(record)
        if reason:
            if len(errors) < 25:
                errors.append(f"row {number}: {reason}")
            continue
        # The print's identity is its id when the file carries one: two genuine prints share a
        # millisecond, a price and a size more often than one would think (a sweep is exactly that),
        # and collapsing those would silently drop real volume. Only an id-less file falls back to
        # the four-field key — and those collapses are counted apart from the unreadable rows.
        key = (record["instrument"], record["timestamp_ms"], record["price"], record["size"],
               record["trade_id"])
        if key in seen:
            deduped += 1
            continue
        seen.add(key)
        if record["side"] not in ("buy", "sell"):
            record["side"] = "buy" if record["side"] not in ("s", "ask", "sell", "sell_side") else "sell"
        out.append([record["instrument"], record["timestamp_ms"], record["price"], record["size"],
                    record["side"], record["trade_id"]])
    return {"rows": out, "errors": errors, "skipped": len(body) - len(out), "deduped": deduped,
            "bad_rows": len(body) - len(out) - deduped, "delimiter": sep,
            "headers": headers, "kind": "ticks"}


def parse_candles(text: str, *, symbol: str = "", delimiter: Optional[str] = None,
                  has_header: Optional[bool] = None) -> dict[str, Any]:
    """A CSV of bars -> rows ready for the candles table. Pure, same tolerance as ticks."""
    info = sniff(text)
    sep = delimiter or info["delimiter"]
    rows = [r for r in csv.reader(io.StringIO(str(text or "")), delimiter=sep)
            if any(str(c).strip() for c in r)]
    headers = info["headers"] if has_header is None else (headers_from(rows[0]) if has_header else None)
    body = rows[1:] if headers else rows

    def column(names: tuple[str, ...], default: Optional[int]) -> Optional[int]:
        return _pick(headers, names) if headers else default

    index = {"ts": column(_TS_ALIASES, 0), "tf": column(("timeframe", "tf", "interval"), None),
             "open": column(("open", "o"), 1), "high": column(("high", "h"), 2),
             "low": column(("low", "l"), 3), "close": column(("close", "c", "price", "last"), 4),
             "volume": column(("volume", "vol", "v", "size", "qty"), 5),
             "symbol": column(("instrument", "symbol", "ticker"), None)}
    out: list[list[Any]] = []
    errors: list[str] = []
    for number, row in enumerate(body, start=1):
        record = {
            "instrument": symbol or (_clean(row[index["symbol"]]) if index["symbol"] is not None and index["symbol"] < len(row) else ""),
            "timestamp_ms": parse_timestamp(row[index["ts"]]) if index["ts"] is not None and index["ts"] < len(row) else None,
            "timeframe": (_clean(row[index["tf"]]) if index["tf"] is not None and index["tf"] < len(row) else "") or "1m",
            "open": _float(row, index["open"]), "high": _float(row, index["high"]),
            "low": _float(row, index["low"]), "close": _float(row, index["close"]),
            "volume": _float(row, index["volume"]) or 0.0,
        }
        problem = None
        if not record["instrument"]:
            problem = "no instrument"
        elif record["timestamp_ms"] is None:
            problem = "unreadable timestamp"
        elif None in (record["open"], record["high"], record["low"], record["close"]):
            problem = "unreadable OHLC"
        elif record["high"] < record["low"]:
            problem = "high below low"
        if problem:
            if len(errors) < 25:
                errors.append(f"row {number}: {problem}")
            continue
        out.append([record["instrument"], record["timestamp_ms"], record["timeframe"], record["open"],
                    record["high"], record["low"], record["close"], record["volume"]])
    return {"rows": out, "errors": errors, "skipped": len(body) - len(out), "delimiter": sep,
            "headers": headers, "kind": "candles"}


def headers_from(row: list[str]) -> Optional[list[str]]:
    """Treat a first row as headers only when it names one of the columns we know. Pure."""
    cells = [str(c).strip().strip('"').lower() for c in row]
    known = set(_TS_ALIASES) | set(_PRICE_ALIASES) | set(_SIZE_ALIASES) | set(_SIDE_ALIASES) | {
        "open", "high", "low", "close", "o", "h", "l", "c", "volume", "vol", "v",
        "timeframe", "tf", "interval", "instrument", "symbol", "ticker", "trade_id"}
    return [str(c).strip().strip('"') for c in row] if any(c in known for c in cells) else None


def _float(row: list[str], index: Optional[int]) -> Optional[float]:
    if index is None or index >= len(row):
        return None
    try:
        return float(_clean(row[index]))
    except (TypeError, ValueError):
        return None


def _tick_problem(record: dict[str, Any]) -> str:
    if not record["instrument"]:
        return "no instrument"
    if record["timestamp_ms"] is None:
        return "unreadable timestamp"
    if record["price"] is None or record["price"] <= 0:
        return "unreadable price"
    if record["size"] is None or record["size"] < 0:
        return "unreadable size"
    return ""


def import_rows(db_path: str | Path, kind: str, rows: list[list[Any]], *,
                dedupe_window: int = 500_000) -> dict[str, Any]:
    """Insert parsed rows into the suite's database from its own connection. Safe to re-run.

    Bars are replaced per (instrument, timestamp, timeframe) — a corrected export re-imports as a
    correction, not a duplicate. Prints cannot be keyed that way (the table has no unique index and
    two prints may share a millisecond), so the rows already stored in the imported window are read
    once and matched; the read is skipped — and said so — when the window holds more rows than
    `dedupe_window`, because a giant window is where an import should be fast rather than clever.
    """
    import sqlite3

    conn = sqlite3.connect(str(db_path), timeout=15)
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        inserted = 0
        skipped = 0
        checked = True
        if kind == "candles":
            for row in rows:
                conn.execute("DELETE FROM candles WHERE instrument=? AND timestamp_ms=? AND timeframe=?",
                             (row[0], row[1], row[2]))
                conn.execute("INSERT INTO candles "
                             "(instrument, timestamp_ms, timeframe, open, high, low, close, volume) "
                             "VALUES (?,?,?,?,?,?,?,?)", row)
                inserted += 1
        else:
            instruments = sorted({str(row[0]) for row in rows})
            low = min(int(row[1]) for row in rows)
            high = max(int(row[1]) for row in rows)
            existing: set[tuple] = set()
            if high > low:
                probe = conn.execute(
                    "SELECT COUNT(*) FROM ticks WHERE instrument=? AND timestamp_ms BETWEEN ? AND ?",
                    (instruments[0], low, high)).fetchone()[0]
                if int(probe or 0) <= dedupe_window:
                    placeholders = ",".join("?" for _ in instruments)
                    cursor = conn.execute(
                        f"SELECT instrument, timestamp_ms, price, size, COALESCE(trade_id, '') "
                        f"FROM ticks WHERE instrument IN ({placeholders}) AND timestamp_ms BETWEEN ? AND ?",
                        (*instruments, low, high))
                    existing = {(str(i), int(ms), float(p), float(s), str(tid))
                                for i, ms, p, s, tid in cursor}
                else:
                    checked = False
            for row in rows:
                key = (str(row[0]), int(row[1]), float(row[2]), float(row[3]), str(row[5] or ""))
                if key in existing:
                    skipped += 1
                    continue
                conn.execute("INSERT INTO ticks (instrument, timestamp_ms, price, size, side, trade_id) "
                             "VALUES (?,?,?,?,?,?)", row)
                inserted += 1
        conn.commit()
        return {"inserted": inserted, "skipped_existing": skipped, "checked_existing": checked}
    finally:
        conn.close()


def export_rows(db_path: str | Path, kind: str, dest_dir: str | Path, *, symbol: str = "",
                from_ms: Optional[int] = None, to_ms: Optional[int] = None,
                limit: int = 2_000_000, now: Optional[float] = None) -> dict[str, Any]:
    """Stream one table (or one instrument's slice) to a CSV in ``dest_dir``; gzip when big.

    Returns the file, its byte count and the row count — the numbers a panel shows. The name is
    ``<kind>-<symbol|all>-<YYYYmmdd-HHMMSS>.csv`` so a folder of exports sorts and self-describes.
    """
    import gzip
    import shutil
    import sqlite3
    import time as _time
    from pathlib import Path as _Path

    folder = _Path(dest_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _time.strftime("%Y%m%d-%H%M%S", _time.gmtime(now if now is not None else _time.time()))
    # RA-02: the tag is a filename component — clamp it like the paper export does, or a
    # symbol carrying a path separator builds a bogus subpath (receipt: ticks-BTC/USDT-….csv).
    tag = "".join(ch for ch in str(symbol or "all").upper()
                  if ch.isalnum() or ch in "._-")[:24] or "all"
    csv_path = folder / f"{kind}-{tag}-{stamp}.csv"

    where: list[str] = []
    args: list[Any] = []
    if symbol:
        where.append("instrument = ?")
        args.append(symbol.upper())
    if from_ms is not None:
        where.append("timestamp_ms >= ?")
        args.append(int(from_ms))
    if to_ms is not None:
        where.append("timestamp_ms <= ?")
        args.append(int(to_ms))
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    conn = sqlite3.connect(f"file:{_Path(db_path).as_posix()}?mode=ro", uri=True)
    written = 0
    try:
        columns = TICK_COLUMNS if kind != "candles" else CANDLE_COLUMNS
        cursor = conn.execute(
            f'SELECT {", ".join(columns)} FROM {kind}{clause} ORDER BY timestamp_ms LIMIT ?',
            (*args, int(limit)))
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\r\n")
            writer.writerow(columns)
            for row in cursor:
                writer.writerow([
                    row[0],
                    datetime.fromtimestamp(int(row[1]) / 1000.0, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                    if row[1] is not None else "",
                    *row[2:],
                ])
                written += 1
    finally:
        conn.close()
    if csv_path.stat().st_size > 2_000_000:            # a bulk table travels gzipped
        gz = csv_path.with_name(csv_path.name + ".gz")
        with csv_path.open("rb") as src, gzip.open(gz, "wb") as out:
            shutil.copyfileobj(src, out)
        csv_path.unlink()
        csv_path = gz
    return {"path": str(csv_path), "rows": written, "bytes": csv_path.stat().st_size}


def csv_line(cells: Iterable[Any]) -> str:
    """One RFC 4180 row (CRLF) — the shape every spreadsheet and this app's own reader expects."""
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerow(list(cells))
    return buffer.getvalue()
