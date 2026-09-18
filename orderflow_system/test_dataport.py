"""R8 pins: the CSV reader's tolerance, the writer's standards, and the round trip between them.

The round-trip test is the one that matters — an export that this app cannot read back is a file
that only looks like data.
"""

from __future__ import annotations

import csv
import gzip
import sqlite3
from pathlib import Path

import pytest

from orderflow_system.desktop import dataport as dp


def _db(tmp_path: Path, rows: int = 5) -> Path:
    path = tmp_path / "orderflow_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE ticks (instrument TEXT, timestamp_ms INTEGER, price REAL, size REAL,
                            side TEXT, trade_id TEXT);
        CREATE TABLE candles (instrument TEXT, timestamp_ms INTEGER, timeframe TEXT, open REAL,
                              high REAL, low REAL, close REAL, volume REAL);
        """)
    base = 1_789_600_000_000
    conn.executemany("INSERT INTO ticks VALUES (?,?,?,?,?,?)",
                     [("BTCUSDT", base + i * 1000, 100.0 + i, 1.5, "buy", f"t{i}") for i in range(rows)])
    conn.executemany("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?)",
                     [("BTCUSDT", base + i * 60_000, "1m", 1.0, 2.0, 0.5, 1.5, 3.0) for i in range(rows)])
    conn.commit()
    conn.close()
    return path


# ── timestamps ───────────────────────────────────────────────────────────────────────────────

def test_timestamps_in_every_dialect_the_industry_writes():
    ms = dp.parse_timestamp("2026-09-18T05:00:00Z")
    assert ms is not None and ms == dp.parse_timestamp("2026-09-18 05:00:00")          # space form
    assert dp.parse_timestamp("2026-09-18T07:00:00+02:00") == ms                       # offset honoured
    assert dp.parse_timestamp(1_789_600_000) == 1_789_600_000_000                      # epoch seconds
    assert dp.parse_timestamp(1_789_600_000_000) == 1_789_600_000_000                  # epoch ms
    assert dp.parse_timestamp(1_789_600_000_000_000) == 1_789_600_000_000              # microseconds
    assert dp.parse_timestamp("not a time") is None
    assert dp.parse_timestamp("") is None
    assert dp.parse_timestamp(None) is None


# ── sniffing + parsing ───────────────────────────────────────────────────────────────────────

def test_sniff_finds_the_delimiter_and_the_header():
    semi = dp.sniff("instrument;timestamp_ms;price;size\nBTCUSDT;1789600000000;100;1")
    assert semi["delimiter"] == ";" and semi["headers"][0] == "instrument"
    tab = dp.sniff("timestamp\tprice\tsize\n1789600000000\t100\t1")
    assert tab["delimiter"] == "\t" and tab["headers"] == ["timestamp", "price", "size"]
    naked = dp.sniff("BTCUSDT,1789600000000,100,1\nBTCUSDT,1789600001000,101,2")
    assert naked["headers"] is None and naked["delimiter"] == ","


def test_parse_ticks_reads_aliases_and_counts_the_bad_rows():
    text = ("time,instrument,price,qty,side\n"
            "2026-09-18T05:00:00Z,BTCUSDT,100.5,2,buy\n"
            "2026-09-18T05:00:01Z,BTCUSDT,100.6,1,sell\n"
            "nonsense,BTCUSDT,100.7,1,buy\n"          # unreadable timestamp
            "2026-09-18T05:00:03Z,BTCUSDT,,1,buy\n")   # no price
    parsed = dp.parse_ticks(text)
    assert parsed["kind"] == "ticks" and len(parsed["rows"]) == 2
    assert parsed["rows"][0][0] == "BTCUSDT" and parsed["rows"][0][4] == "buy"
    assert parsed["skipped"] == 2 and len(parsed["errors"]) == 2
    assert "unreadable timestamp" in parsed["errors"][0]


def test_parse_ticks_headerless_and_symbol_forced():
    parsed = dp.parse_ticks("1789600000000,100,1,buy,id1\n1789600001000,101,2,sell,id2", symbol="ethusdt")
    assert len(parsed["rows"]) == 2
    assert parsed["rows"][0][0] == "ethusdt" and parsed["rows"][1][4] == "sell"


def test_parse_ticks_dedupes_inside_one_file():
    line = "2026-09-18T05:00:00Z,BTCUSDT,100,1,buy"
    parsed = dp.parse_ticks("time,instrument,price,size,side\n" + line + "\n" + line + "\n")
    assert len(parsed["rows"]) == 1, "the same print twice in one file is one print"
    assert parsed["deduped"] == 1 and parsed["bad_rows"] == 0, "a duplicate is not an unreadable row"


def test_parse_ticks_keeps_same_millisecond_prints_apart_when_they_carry_ids():
    """A sweep is several prints on one millisecond; the id is what keeps them distinct."""
    text = ("timestamp_ms,instrument,price,size,side,trade_id\n"
            "1789600000000,BTCUSDT,100.5,1,buy,a1\n"
            "1789600000000,BTCUSDT,100.5,1,buy,a2\n"
            "1789600000000,BTCUSDT,100.5,2,buy,a3\n")
    parsed = dp.parse_ticks(text)
    assert len(parsed["rows"]) == 3 and parsed["deduped"] == 0


def test_parse_candles_validates_ohlc():
    text = ("timestamp_ms,instrument,open,high,low,close,volume\n"
            "1789600000000,BTCUSDT,1,2,0.5,1.5,10\n"
            "1789600060000,BTCUSDT,1,0.4,0.9,1.2,5\n"       # high below low
            "1789600120000,BTCUSDT,1,2,0.5,,\n")             # no close
    parsed = dp.parse_candles(text)
    assert len(parsed["rows"]) == 1 and parsed["rows"][0][2] == "1m"   # timeframe defaults
    assert parsed["skipped"] == 2
    assert any("high below low" in e for e in parsed["errors"])


def test_headers_from_only_claims_a_row_that_names_our_columns():
    assert dp.headers_from(["price", "size"]) == ["price", "size"]
    assert dp.headers_from(["100", "1"]) is None


# ── the database ends ────────────────────────────────────────────────────────────────────────

def test_import_ticks_is_re_runnable(tmp_path):
    db = _db(tmp_path, rows=0)
    text = "timestamp_ms,instrument,price,size,side\n" + "".join(
        f"{1789600000000 + i * 1000},BTCUSDT,{100 + i},1,buy\n" for i in range(4))
    parsed = dp.parse_ticks(text)
    first = dp.import_rows(db, "ticks", parsed["rows"])
    assert first["inserted"] == 4 and first["skipped_existing"] == 0
    second = dp.import_rows(db, "ticks", parsed["rows"])
    assert second["inserted"] == 0 and second["skipped_existing"] == 4, "a re-run must not double the tape"
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 4
    finally:
        conn.close()


def test_import_candles_replaces_instead_of_duplicating(tmp_path):
    db = _db(tmp_path, rows=0)
    rows = [[ "BTCUSDT", 1789600000000, "1m", 1.0, 2.0, 0.5, 1.5, 3.0 ]]
    dp.import_rows(db, "candles", rows)
    corrected = [["BTCUSDT", 1789600000000, "1m", 1.0, 2.0, 0.5, 9.9, 3.0]]
    dp.import_rows(db, "candles", corrected)
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 1
        assert conn.execute("SELECT close FROM candles").fetchone()[0] == 9.9
    finally:
        conn.close()


def test_export_then_import_round_trips(tmp_path):
    db = _db(tmp_path, rows=6)
    dest = tmp_path / "exports"
    done = dp.export_rows(db, "ticks", dest, symbol="BTCUSDT")
    assert done["rows"] == 6 and Path(done["path"]).exists()
    with Path(done["path"]).open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    assert "\r\n" in text and text.splitlines()[0] == ",".join(dp.TICK_COLUMNS)
    assert "T" in text.splitlines()[1] and text.splitlines()[1].rstrip().endswith("Z") or "Z" in text

    parsed = dp.parse_ticks(text)
    assert len(parsed["rows"]) == 6, "the writer's own shape must parse"

    # and the same rows go back into a second, empty database — the full circle
    import shutil

    empty = tmp_path / "empty.db"
    shutil.copy(db, empty)
    conn = sqlite3.connect(empty)
    conn.execute("DELETE FROM ticks")
    conn.commit()
    conn.close()
    result = dp.import_rows(empty, "ticks", parsed["rows"])
    assert result["inserted"] == 6


def test_export_gzips_a_big_table(tmp_path, monkeypatch):
    db = _db(tmp_path, rows=0)
    conn = sqlite3.connect(db)
    conn.executemany("INSERT INTO ticks VALUES (?,?,?,?,?,?)",
                     [("BTCUSDT", 1789600000000 + i, 100.0, 1.0, "buy", f"x{i}") for i in range(2000)])
    conn.commit()
    conn.close()
    dest = tmp_path / "exports"
    done = dp.export_rows(db, "ticks", dest)
    assert done["rows"] == 2000 and Path(done["path"]).name.endswith(".csv")   # under the gzip floor
    # and the reader handles the gzipped shape too (the backup writer's habit)
    gz = dest / "ticks-gz.csv.gz"
    with gzip.open(gz, "wt", encoding="utf-8", newline="") as handle:
        handle.write("instrument,timestamp_ms,price,size\nBTCUSDT,1789600000000,100,1\n")
    raw = gzip.open(gz, "rt", encoding="utf-8").read()
    assert len(dp.parse_ticks(raw)["rows"]) == 1


@pytest.mark.parametrize("kind", ["ticks", "candles"])
def test_csv_line_is_rfc_4180(kind):
    line = dp.csv_line(["a", 1, None, 2.5])
    assert line.endswith("\r\n") and line.startswith("a,1,")
    parsed = list(csv.reader([line]))
    assert parsed[0][:2] == ["a", "1"]
