"""
SQLite storage for ticks, candles, volume profiles, and signals.
Lightweight, zero-cost, zero-config alternative to TimescaleDB.
"""

from __future__ import annotations

import aiosqlite
import json
import logging
from typing import Optional

from orderflow_system.data.models import Tick, Side, Candle, FootprintLevel, Signal, VolumeProfileResult

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database for orderflow data storage."""

    def __init__(self, db_path: str = "orderflow_data.db"):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        # timeout + busy_timeout: a second instance (or a CLI run) writing the
        # same file must make us wait for the lock, not fail instantly.
        self._db = await aiosqlite.connect(self.db_path, timeout=15.0)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=15000")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._create_tables()
        logger.info(f"Database connected: {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()
            logger.info("Database closed")

    async def _create_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                side TEXT NOT NULL,
                trade_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_ticks_instrument_ts
                ON ticks(instrument, timestamp_ms);

            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                timeframe TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                volume REAL,
                buy_volume REAL,
                sell_volume REAL,
                delta REAL,
                tick_count INTEGER,
                footprint_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_candles_instrument_ts
                ON candles(instrument, timestamp_ms, timeframe);

            CREATE TABLE IF NOT EXISTS volume_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                session_date TEXT NOT NULL,
                poc REAL, vah REAL, val REAL,
                total_volume REAL,
                shape TEXT,
                poc_position_pct REAL,
                lvn_json TEXT,
                volume_at_price_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_vp_instrument_date
                ON volume_profiles(instrument, session_date);

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                signal_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                price_level REAL,
                strength REAL,
                details_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_signals_instrument_ts
                ON signals(instrument, timestamp_ms);

            CREATE TABLE IF NOT EXISTS trade_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_time_ms INTEGER,
                exit_time_ms INTEGER,
                entry_price REAL,
                exit_price REAL,
                stop_loss REAL,
                take_profit REAL,
                pnl_ticks REAL,
                rr_ratio REAL,
                signals_json TEXT,
                notes TEXT
            );
        """)
        await self._db.commit()

    # ── Ticks ──

    async def insert_tick(self, instrument: str, tick: Tick):
        await self._db.execute(
            "INSERT INTO ticks (instrument, timestamp_ms, price, size, side, trade_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (instrument, tick.timestamp_ms, tick.price, tick.size,
             tick.side.value, tick.trade_id),
        )

    async def insert_ticks_batch(self, instrument: str, ticks: list[Tick]):
        data = [
            (instrument, t.timestamp_ms, t.price, t.size, t.side.value, t.trade_id)
            for t in ticks
        ]
        await self._db.executemany(
            "INSERT INTO ticks (instrument, timestamp_ms, price, size, side, trade_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            data,
        )
        await self._db.commit()

    async def get_ticks(
        self, instrument: str, start_ms: int, end_ms: int
    ) -> list[Tick]:
        cursor = await self._db.execute(
            "SELECT timestamp_ms, price, size, side, trade_id FROM ticks "
            "WHERE instrument = ? AND timestamp_ms >= ? AND timestamp_ms <= ? "
            "ORDER BY timestamp_ms",
            (instrument, start_ms, end_ms),
        )
        rows = await cursor.fetchall()
        return [
            Tick(
                timestamp_ms=r[0], price=r[1], size=r[2],
                side=Side(r[3]), trade_id=r[4] or ""
            )
            for r in rows
        ]

    async def delete_ticks_window(self, instrument: str, start_ms: int, end_ms: int) -> int:
        """Remove a window of stored ticks, returning how many rows went.

        Only the archive backfill calls this: a stored day is *replaced* rather than appended to, so
        re-running an interrupted day (or re-downloading one) can never double-count volume in the
        profiles, delta lanes or any study that reads history.
        """
        cursor = await self._db.execute(
            "DELETE FROM ticks WHERE instrument = ? AND timestamp_ms >= ? AND timestamp_ms < ?",
            (instrument, start_ms, end_ms),
        )
        await self._db.commit()
        return cursor.rowcount or 0

    async def count_ticks(self, instrument: str, start_ms: int, end_ms: int) -> int:
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM ticks WHERE instrument = ? AND timestamp_ms >= ? AND timestamp_ms < ?",
            (instrument, start_ms, end_ms),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def get_recent_ticks(self, instrument: str, start_ms: int, end_ms: int,
                               limit: int = 5_000) -> list[Tick]:
        """The newest `limit` ticks inside a window, returned oldest-first.

        A day of a liquid instrument is millions of rows: reading the window into memory and putting
        every row in an HTTP response would be a denial of service against our own loopback, so the
        read walks backwards from the newest row and stops at the cap.
        """
        cursor = await self._db.execute(
            "SELECT timestamp_ms, price, size, side, trade_id FROM ticks "
            "WHERE instrument = ? AND timestamp_ms >= ? AND timestamp_ms < ? "
            "ORDER BY timestamp_ms DESC LIMIT ?",
            (instrument, start_ms, end_ms, int(limit)),
        )
        rows = await cursor.fetchall()
        return [
            Tick(timestamp_ms=r[0], price=r[1], size=r[2], side=Side(r[3]), trade_id=r[4] or "")
            for r in reversed(rows)
        ]

    # ── Candles ──

    # ── R5: storage retention ─────────────────────────────────────────────

    async def prune_ticks(self, cutoff_ms: int, instruments: list[str], batch: int = 50_000) -> int:
        """Delete ticks older than *cutoff_ms*; returns the rows deleted.

        Per instrument (the composite index leads with `instrument`), in bounded batches —
        SQLite here has no `DELETE … LIMIT`, so each batch deletes by rowid subquery and
        commits, keeping the writer's lock windows short.
        """
        if not self._db or cutoff_ms <= 0:
            return 0
        total = 0
        for inst in instruments or []:
            while True:
                cur = await self._db.execute(
                    "DELETE FROM ticks WHERE rowid IN ("
                    " SELECT rowid FROM ticks WHERE instrument = ? AND timestamp_ms < ? LIMIT ?)",
                    (inst, int(cutoff_ms), int(batch)),
                )
                n = cur.rowcount or 0
                await self._db.commit()
                total += n
                if n < batch:
                    break
        return total

    async def tick_instruments(self) -> list[str]:
        """Every instrument with tick rows — the prune covers the DB's own contents, not
        just the symbols this boot happens to have enabled."""
        if not self._db:
            return []
        try:
            cur = await self._db.execute("SELECT DISTINCT instrument FROM ticks")
            rows = await cur.fetchall()
            return [str(r[0]) for r in rows if r and r[0]]
        except Exception:                                  # noqa: BLE001
            return []

    async def storage_snapshot(self) -> dict:
        """File sizes, per-table row counts and the tick span.

        `COUNT(*)` over millions of rows is not free — callers cache this (the route does,
        30 s; the prune job reports it once per pass).
        """
        import os

        db_file = str(self.db_path)
        out = {"db_path": db_file, "bytes": 0, "wal_bytes": 0, "tables": {},
               "ticks": {"oldest_ms": 0, "newest_ms": 0}}
        for suffix, key in (("", "bytes"), ("-wal", "wal_bytes")):
            try:
                out[key] = os.path.getsize(db_file + suffix)
            except OSError:
                out[key] = 0
        if not self._db:
            return out
        for table in ("ticks", "candles", "volume_profiles", "signals", "trade_journal"):
            try:
                cur = await self._db.execute(f"SELECT COUNT(*) FROM {table}")
                row = await cur.fetchone()
                out["tables"][table] = int(row[0]) if row else 0
            except Exception:                              # noqa: BLE001 — a missing table is 0-ish, not fatal
                out["tables"][table] = -1
        try:
            cur = await self._db.execute("SELECT MIN(timestamp_ms), MAX(timestamp_ms) FROM ticks")
            row = await cur.fetchone()
            out["ticks"] = {"oldest_ms": int(row[0] or 0), "newest_ms": int(row[1] or 0)}
        except Exception:                                  # noqa: BLE001
            pass
        return out

    async def ensure_incremental_autovacuum(self) -> str:
        """Make the DB reclaimable: `PRAGMA incremental_vacuum` is a NO-OP until the file is
        converted once with a full VACUUM (`auto_vacuum=INCREMENTAL`). Returns 'already',
        'converted' or 'failed' — reported, never faked; a locked DB just retries next
        interval."""
        if not self._db:
            return "failed"
        try:
            cur = await self._db.execute("PRAGMA auto_vacuum")
            row = await cur.fetchone()
            if row and int(row[0]) == 2:
                return "already"
            await self._db.commit()
            await self._db.execute("PRAGMA auto_vacuum=INCREMENTAL")
            await self._db.execute("VACUUM")
            await self._db.commit()
            cur = await self._db.execute("PRAGMA auto_vacuum")
            row = await cur.fetchone()
            return "converted" if row and int(row[0]) == 2 else "failed"
        except Exception as exc:                           # noqa: BLE001
            logger.warning("auto-vacuum conversion failed (retries next prune): %s", exc)
            return "failed"

    async def vacuum_incremental(self) -> None:
        """Hand freed pages back to the OS — bounded work after a prune."""
        if not self._db:
            return
        try:
            await self._db.execute("PRAGMA incremental_vacuum")
            await self._db.commit()
            # The vacuum's own traffic parks in the WAL until a checkpoint; without this the
            # file "shrinks" while the footprint on disk does not (measured: 677 MB of WAL
            # after the first real prune on the live DB). TRUNCATE hands the space back now.
            await self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            await self._db.commit()
        except Exception as exc:                           # noqa: BLE001
            logger.warning("incremental vacuum failed: %s", exc)

    async def insert_candle(self, instrument: str, timeframe: str, candle: Candle):
        fp_json = json.dumps({
            str(price): {"bid": lvl.bid_volume, "ask": lvl.ask_volume}
            for price, lvl in candle.footprint.items()
        }) if candle.footprint else "{}"

        await self._db.execute(
            "INSERT INTO candles "
            "(instrument, timestamp_ms, timeframe, open, high, low, close, "
            "volume, buy_volume, sell_volume, delta, tick_count, footprint_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (instrument, candle.timestamp_ms, timeframe,
             candle.open, candle.high, candle.low, candle.close,
             candle.volume, candle.buy_volume, candle.sell_volume,
             candle.delta, candle.tick_count, fp_json),
        )
        await self._db.commit()

    async def get_candles(
        self, instrument: str, timeframe: str, start_ms: int, end_ms: int
    ) -> list[Candle]:
        cursor = await self._db.execute(
            "SELECT timestamp_ms, open, high, low, close, volume, "
            "buy_volume, sell_volume, tick_count, footprint_json FROM candles "
            "WHERE instrument = ? AND timeframe = ? "
            "AND timestamp_ms >= ? AND timestamp_ms <= ? "
            "ORDER BY timestamp_ms",
            (instrument, timeframe, start_ms, end_ms),
        )
        rows = await cursor.fetchall()
        return [
            Candle(
                timestamp_ms=r[0], open=r[1], high=r[2], low=r[3], close=r[4],
                volume=r[5], buy_volume=r[6], sell_volume=r[7], tick_count=r[8],
                footprint=self._decode_footprint(r[9]),
            )
            for r in rows
        ]

    @staticmethod
    def _decode_footprint(raw: Optional[str]) -> dict[float, FootprintLevel]:
        """Deserialize the footprint JSON that insert_candle wrote.

        Without this the DB round trip dropped the per-level bid/ask, so the hourly
        volume-profile rebuild (get_candles → compute_from_candles) silently fell back to
        distributing each candle's volume evenly across its OHLC range — a cruder profile
        than the live path on a system that claims tick-level microstructure. Rows written
        before this change carry '{}' or NULL: that is an empty footprint, not an error.
        """
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        out: dict[float, FootprintLevel] = {}
        for price, lv in (data or {}).items():
            try:
                out[float(price)] = FootprintLevel(
                    price=float(price),
                    bid_volume=float(lv.get("bid", 0.0) or 0.0),
                    ask_volume=float(lv.get("ask", 0.0) or 0.0),
                )
            except (TypeError, ValueError, AttributeError):
                continue
        return out

    # ── Volume Profiles ──

    async def insert_volume_profile(self, instrument: str, vp: VolumeProfileResult):
        # Replace, never append: the hourly/daily rebuild re-inserts the same session_date, and the
        # table had no unique key, so one session accumulated a row per rebuild (his DB held 81 rows
        # for a single date, which is what made "last 5 sessions" five copies of one day).
        await self._db.execute(
            "DELETE FROM volume_profiles WHERE instrument = ? AND session_date = ?",
            (instrument, vp.session_date),
        )
        await self._db.execute(
            "INSERT INTO volume_profiles "
            "(instrument, session_date, poc, vah, val, total_volume, shape, "
            "poc_position_pct, lvn_json, volume_at_price_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (instrument, vp.session_date, vp.poc, vp.vah, vp.val,
             vp.total_volume, vp.shape, vp.poc_position_pct,
             json.dumps(vp.lvn_levels),
             json.dumps({str(k): v for k, v in vp.volume_at_price.items()})),
        )
        await self._db.commit()

    async def get_volume_profiles(
        self, instrument: str, days: int = 5
    ) -> list[VolumeProfileResult]:
        # One row per session_date - the newest - so `days` really means days. Without the
        # correlated max(id) this returned however many rows the rebuilds had accumulated, and the
        # LIMIT then cut across duplicates of a single session.
        cursor = await self._db.execute(
            "SELECT session_date, poc, vah, val, total_volume, shape, "
            "poc_position_pct, lvn_json, volume_at_price_json "
            "FROM volume_profiles v WHERE instrument = ? AND v.id = ("
            "  SELECT MAX(id) FROM volume_profiles x "
            "  WHERE x.instrument = v.instrument AND x.session_date = v.session_date) "
            "ORDER BY session_date DESC LIMIT ?",
            (instrument, days),
        )
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            vap_raw = json.loads(r[8]) if r[8] else {}
            results.append(VolumeProfileResult(
                session_date=r[0], poc=r[1], vah=r[2], val=r[3],
                total_volume=r[4], shape=r[5], poc_position_pct=r[6],
                lvn_levels=json.loads(r[7]) if r[7] else [],
                volume_at_price={float(k): v for k, v in vap_raw.items()},
            ))
        return list(reversed(results))  # Oldest first

    # ── Signals ──

    async def insert_signal(self, instrument: str, signal: Signal):
        await self._db.execute(
            "INSERT INTO signals "
            "(instrument, timestamp_ms, signal_type, direction, price_level, "
            "strength, details_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (instrument, signal.timestamp_ms, signal.signal_type.value,
             signal.direction.value, signal.price_level, signal.strength,
             json.dumps(signal.details)),
        )
        await self._db.commit()

    # ── Trade Journal ──

    async def log_trade(
        self,
        instrument: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        stop_loss: float,
        take_profit: float,
        pnl_ticks: float,
        rr_ratio: float,
        signals: list[Signal],
        notes: str = "",
        entry_time_ms: int = 0,
        exit_time_ms: int = 0,
    ):
        signals_json = json.dumps([
            {"type": s.signal_type.value, "strength": s.strength,
             "price": s.price_level, "ts": s.timestamp_ms}
            for s in signals
        ])
        await self._db.execute(
            "INSERT INTO trade_journal "
            "(instrument, direction, entry_time_ms, exit_time_ms, entry_price, "
            "exit_price, stop_loss, take_profit, pnl_ticks, rr_ratio, "
            "signals_json, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (instrument, direction, entry_time_ms, exit_time_ms,
             entry_price, exit_price, stop_loss, take_profit,
             pnl_ticks, rr_ratio, signals_json, notes),
        )
        await self._db.commit()
