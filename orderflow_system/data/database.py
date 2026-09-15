"""
SQLite storage for ticks, candles, volume profiles, and signals.
Lightweight, zero-cost, zero-config alternative to TimescaleDB.
"""

from __future__ import annotations

import aiosqlite
import json
import logging
from pathlib import Path
from typing import Optional

from orderflow_system.data.models import Tick, Side, Candle, Signal, SignalType, VolumeProfileResult

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

    # ── Candles ──

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
            "buy_volume, sell_volume, tick_count FROM candles "
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
            )
            for r in rows
        ]

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
