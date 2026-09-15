"""
Market Replay (the reference layout "Market Replay" equivalent).

Replays a recorded session through the analytics with speed control, pause/resume,
seek and progress — exactly the reference layout loop of "study a past session as if it were
live", minus broker order placement.

Source priority for one symbol/time-range:
  1. our own SQLite ``ticks`` table (full microstructure, written by the engine)
  2. the ``candles`` table (synthesises one print per candle — labelled as such)
  3. the exchange REST taper (``atlas.feed_extras.fetch_recent_trades``) as a seed
     when the local DB has nothing for that symbol yet

Replay never touches the live feed: the GUI runs it in its own task.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import aiosqlite

from orderflow_system.data.models import Side, Tick

logger = logging.getLogger(__name__)


@dataclass
class ReplayStatus:
    state: str = "idle"             # idle | loaded | playing | paused | finished | error
    symbol: str = ""
    mode: str = ""                  # ticks | candles | exchange
    total: int = 0
    index: int = 0
    speed: float = 10.0
    start_ms: int = 0
    end_ms: int = 0
    current_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        pct = (self.index / self.total * 100) if self.total else 0.0
        return {**self.__dict__, "progress_pct": round(pct, 2),
                "remaining": max(0, self.total - self.index)}


class MarketReplay:
    """Drives recorded data into any tick consumer at a chosen speed."""

    def __init__(
        self,
        db_path: str,
        speed: float = 10.0,
        max_gap_ms: int = 750,
        max_ticks: int = 300_000,
        batch_sleep: float = 0.0,
    ) -> None:
        self.db_path = str(db_path)
        self.status_obj = ReplayStatus(speed=max(0.1, float(speed)))
        self.max_gap_ms = int(max_gap_ms)
        self.max_ticks = int(max_ticks)
        self.batch_sleep = float(batch_sleep)
        self._rows: list[tuple[int, float, float, str]] = []
        self._pause = asyncio.Event()
        self._pause.set()
        self._stop = False
        self._task: Optional[asyncio.Task] = None
        self._seek_to: Optional[int] = None

    # ── loading ───────────────────────────────────────────────
    async def load(self, symbol: str, start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> dict[str, Any]:
        st = self.status_obj
        st.symbol = symbol
        st.error = ""
        start = int(start_ms or 0)
        end = int(end_ms or (time.time() * 1000))
        st.start_ms, st.end_ms = start, end

        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                if not start:
                    cur = await db.execute("SELECT MIN(timestamp_ms) FROM ticks WHERE instrument=?", (symbol,))
                    row = await cur.fetchone()
                    start = int(row[0] or 0) if row else 0
                    st.start_ms = start
                cur = await db.execute(
                    "SELECT timestamp_ms, price, size, side FROM ticks WHERE instrument=? AND timestamp_ms>=? AND timestamp_ms<=? ORDER BY timestamp_ms LIMIT ?",
                    (symbol, start, end, self.max_ticks),
                )
                rows = await cur.fetchall()
                if rows:
                    self._rows = [(int(r["timestamp_ms"]), float(r["price"]), float(r["size"]), str(r["side"])) for r in rows]
                    st.mode = "ticks"
                else:
                    cur = await db.execute(
                        "SELECT timestamp_ms, close, volume, delta FROM candles WHERE instrument=? AND timestamp_ms>=? AND timestamp_ms<=? ORDER BY timestamp_ms LIMIT ?",
                        (symbol, start, end, self.max_ticks),
                    )
                    crows = await cur.fetchall()
                    self._rows = [(int(r["timestamp_ms"]), float(r["close"]), float(r["volume"] or 0),
                                   "buy" if (r["delta"] or 0) >= 0 else "sell") for r in crows]
                    st.mode = "candles" if crows else ""
        except Exception as exc:
            st.state, st.error = "error", f"{type(exc).__name__}: {exc}"
            logger.warning("Replay load failed: %s", exc)
            return st.to_dict()

        st.total = len(self._rows)
        st.index = 0
        st.state = "loaded" if self._rows else "idle"
        if self._rows:
            st.start_ms, st.end_ms = self._rows[0][0], self._rows[-1][0]
            st.current_ms = st.start_ms
        return st.to_dict()

    async def load_from_exchange(self, symbol: str, limit: int = 1000) -> dict[str, Any]:
        """Seed a replay from the exchange tape when the local DB is empty."""
        from orderflow_system.atlas import feed_extras
        st = self.status_obj
        st.symbol = symbol
        try:
            trades = await asyncio.to_thread(feed_extras.fetch_recent_trades, symbol, limit)
        except Exception as exc:
            st.state, st.error = "error", f"{type(exc).__name__}: {exc}"
            return st.to_dict()
        trades.sort(key=lambda t: t["ts_ms"])
        self._rows = [(t["ts_ms"], t["price"], t["size"], t["side"] or "buy") for t in trades]
        st.total = len(self._rows)
        st.index = 0
        st.mode = "exchange"
        st.state = "loaded" if self._rows else "idle"
        if self._rows:
            st.start_ms, st.end_ms = self._rows[0][0], self._rows[-1][0]
            st.current_ms = st.start_ms
        return st.to_dict()

    # ── transport ─────────────────────────────────────────────
    async def play(self, on_tick: Callable[[Tick], Awaitable[None]], speed: Optional[float] = None) -> dict[str, Any]:
        st = self.status_obj
        if not self._rows:
            return {"ok": False, "error": "nothing loaded — call load() first"}
        if self._task and not self._task.done():
            return {"ok": False, "error": "replay already running"}
        if st.index >= st.total:
            # Replaying a finished session starts over from the seek point.
            start = self._seek_to if self._seek_to is not None else 0
            st.index = max(0, min(start, st.total - 1))
            self._seek_to = None
        if speed:
            st.speed = max(0.1, float(speed))
        self._stop = False
        self._pause.set()
        st.state = "playing"

        async def runner() -> None:
            try:
                started = time.monotonic()
                base_ts = self._rows[st.index][0]
                while st.index < st.total and not self._stop:
                    if self._seek_to is not None:
                        st.index = max(0, min(self._seek_to, st.total - 1))
                        base_ts = self._rows[st.index][0]
                        started = time.monotonic()
                        self._seek_to = None
                    await self._pause.wait()

                    ts, price, size, side = self._rows[st.index]
                    # Virtual clock: sleep only while AHEAD of schedule. Sleeping
                    # per tick would cap throughput at the OS timer resolution
                    # (~15 ms on Windows ≈ 64 ticks/s) no matter the speed factor.
                    target = (ts - base_ts) / 1000.0 / st.speed
                    ahead = target - (time.monotonic() - started)
                    if ahead > 0:
                        await asyncio.sleep(min(ahead, 0.25))
                        continue                      # re-check pause/seek/stop

                    tick = Tick(timestamp_ms=ts, price=price, size=size,
                                side=Side.BUY if side == "buy" else Side.SELL)
                    st.current_ms = ts
                    st.index += 1
                    try:
                        await on_tick(tick)
                    except Exception:
                        logger.exception("replay consumer failed")

                    if self.batch_sleep:
                        await asyncio.sleep(self.batch_sleep)
                st.state = "finished" if not self._stop else "idle"
            except asyncio.CancelledError:
                st.state = "idle"
                raise

        self._task = asyncio.create_task(runner())
        return {"ok": True, "status": st.to_dict()}

    def pause(self) -> dict[str, Any]:
        self._pause.clear()
        if self.status_obj.state == "playing":
            self.status_obj.state = "paused"
        return self.status_obj.to_dict()

    def resume(self) -> dict[str, Any]:
        self._pause.set()
        if self.status_obj.state == "paused":
            self.status_obj.state = "playing"
        return self.status_obj.to_dict()

    async def stop(self) -> dict[str, Any]:
        self._stop = True
        self._pause.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None
        self.status_obj.state = "idle"
        return self.status_obj.to_dict()

    def seek(self, index: int) -> dict[str, Any]:
        st = self.status_obj
        index = int(max(0, min(index, max(0, st.total - 1))))
        if st.state == "finished":
            st.state = "loaded"          # scrubbing a finished session arms it again
        if st.state != "playing" and self._rows:
            # Not playing → apply immediately so the UI slider and clock track
            # the scrub instead of waiting for a resume that may never come.
            st.index = index
            st.current_ms = self._rows[index][0]
            self._seek_to = None
        else:
            self._seek_to = index
        return st.to_dict()

    def seek_fraction(self, fraction: float) -> dict[str, Any]:
        return self.seek(int(max(0.0, min(1.0, fraction)) * self.status_obj.total))

    def set_speed(self, speed: float) -> dict[str, Any]:
        self.status_obj.speed = max(0.1, float(speed))
        return self.status_obj.to_dict()

    def status(self) -> dict[str, Any]:
        return self.status_obj.to_dict()

    def reset(self) -> None:
        self._rows = []
        self.status_obj = ReplayStatus(speed=self.status_obj.speed)
