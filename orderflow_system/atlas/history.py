"""Durable detection history (the reference layout's MBO Bundle keeps local event history too).

Every detection the hub dispatches — big trades, sweeps, icebergs, stop runs,
liquidations, stack/pull events, stacked imbalances, CVD divergences and the
alerts raised from them — can be appended to a small SQLite table so a session
can be reviewed after the fact instead of only while the window is open.

Writes are batched off the event loop: the ingest path only appends to a deque,
and a background task (or an on-demand ``flush``) commits the batch.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections import deque
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS atlas_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    price REAL DEFAULT 0,
    size REAL DEFAULT 0,
    detail TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_atlas_events_symbol_kind ON atlas_events(symbol, kind, ts_ms);
"""


class EventHistory:
    """Append-only detection log with batched SQLite writes and simple reads."""

    def __init__(
        self,
        db_path: str,
        enabled: bool = True,
        flush_rows: int = 40,
        flush_interval_s: float = 5.0,
        retention_days: float = 7.0,
    ) -> None:
        self.db_path = str(db_path)
        self.enabled = bool(enabled)
        self.flush_rows = int(flush_rows)
        self.flush_interval_s = float(flush_interval_s)
        self.retention_days = float(retention_days)
        self.written = 0
        self.dropped = 0
        self.pruned = 0
        self._pending: deque[tuple[Any, ...]] = deque(maxlen=10_000)
        self._task: Optional[asyncio.Task] = None
        self._schema_ready = False
        self._pruned_once = False

    # ── ingest ────────────────────────────────────────────────
    def record(self, symbol: str, kind: str, price: float = 0.0, size: float = 0.0,
               detail: str = "", ts_ms: Optional[int] = None) -> None:
        """Queue one event. Never raises — history must not break the feed."""
        if not self.enabled:
            return
        try:
            self._pending.append((
                int(ts_ms or time.time() * 1000), str(symbol), str(kind),
                float(price or 0.0), float(size or 0.0), str(detail or "")[:300],
            ))
        except Exception:                       # pragma: no cover - defensive
            logger.debug("history record failed", exc_info=True)

    @property
    def pending(self) -> int:
        return len(self._pending)

    # ── lifecycle ─────────────────────────────────────────────
    async def start(self) -> None:
        if self.enabled and self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        await self.flush()

    async def _loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.flush_interval_s)
                await self.flush()
        except asyncio.CancelledError:           # pragma: no cover - shutdown path
            raise

    async def flush(self) -> int:
        """Commit queued rows. Safe to call from the event loop at any time."""
        if not self._pending:
            return 0
        rows = list(self._pending)
        self._pending.clear()
        try:
            await asyncio.to_thread(self._write_rows, rows)
            self.written += len(rows)
            return len(rows)
        except Exception as exc:                # pragma: no cover - IO errors
            self.dropped += len(rows)
            logger.warning("atlas history flush failed: %s", exc)
            return 0

    def _write_rows(self, rows: list[tuple[Any, ...]]) -> None:
        con = sqlite3.connect(self.db_path, timeout=10)
        try:
            if not self._schema_ready:
                con.executescript(_SCHEMA)
                con.commit()
                self._schema_ready = True
            con.executemany(
                "INSERT INTO atlas_events (ts_ms, symbol, kind, price, size, detail) VALUES (?,?,?,?,?,?)",
                rows,
            )
            con.commit()
            if not self._pruned_once:
                # keep long-running installs from growing without bound; one
                # prune per process is enough (older rows are review material)
                self._pruned_once = True
                cutoff = int((time.time() - self.retention_days * 86_400) * 1000)
                cur = con.execute("DELETE FROM atlas_events WHERE ts_ms < ?", (cutoff,))
                con.commit()
                self.pruned += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        finally:
            con.close()

    # ── reads (call from a worker thread) ─────────────────────
    def recent(self, symbol: str = "", kind: str = "", limit: int = 200,
               since_ms: int = 0) -> list[dict[str, Any]]:
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.executescript(_SCHEMA)
            sql = "SELECT ts_ms, symbol, kind, price, size, detail FROM atlas_events WHERE 1=1"
            args: list[Any] = []
            if symbol:
                sql += " AND symbol = ?"
                args.append(symbol)
            if kind:
                sql += " AND kind = ?"
                args.append(kind)
            if since_ms:
                sql += " AND ts_ms >= ?"
                args.append(int(since_ms))
            sql += " ORDER BY ts_ms DESC LIMIT ?"
            args.append(int(limit))
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()

    def counts(self, symbol: str = "", since_ms: int = 0) -> dict[str, int]:
        con = sqlite3.connect(self.db_path, timeout=10)
        try:
            con.executescript(_SCHEMA)
            sql = "SELECT kind, COUNT(*) FROM atlas_events WHERE 1=1"
            args: list[Any] = []
            if symbol:
                sql += " AND symbol = ?"
                args.append(symbol)
            if since_ms:
                sql += " AND ts_ms >= ?"
                args.append(int(since_ms))
            sql += " GROUP BY kind"
            return {str(k): int(n) for k, n in con.execute(sql, args).fetchall()}
        finally:
            con.close()

    def total(self) -> int:
        con = sqlite3.connect(self.db_path, timeout=10)
        try:
            con.executescript(_SCHEMA)
            row = con.execute("SELECT COUNT(*) FROM atlas_events").fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()
