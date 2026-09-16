"""The feed-session shape every websocket adapter in this package follows — and why it is that shape.

A session that reads, heartbeats and reconnects has exactly one rule that must not be broken:

    **the reader is never cancelled mid-frame.**

When a read is cancelled halfway through a frame, the frame assembler loses its place: the next
bytes are misread as a header and the connection dies with a protocol error (`Reserved bits are not
zero` is the classic shape) that looks exactly like a venue problem. The naive spelling of that
trap is `await asyncio.wait_for(ws.recv(), timeout)` — or a shared timeout that wraps the read
loop — and it is the reason flowsurface's newest commit reworked its session loop. This module is
the same design in Python:

* one reader loop over complete frames; nothing cancels it;
* the heartbeat is its **own task**, and the venue's liveness contract is **data** (`HeartbeatPolicy`),
  not a hardcoded number (Bybit pings on a cadence, OKX pings only when the connection has gone
  quiet, Binance is server-driven with a much larger silence budget);
* a **silence budget** per venue: nothing parsed for that long and the socket is treated as dead —
  which is how a half-open TCP connection is detected without a ping storm;
* the reconnect ladder resets **only when a frame actually parsed**, and carries jitter so several
  adapters that lost their sockets at the same moment (a local blip, a venue outage) do not come
  back in lockstep.

Adapter authors: subclass nothing — pass `connect`, `on_frame` and a policy from `VENUE_POLICIES`.
`data/bybit_feed.py` predates this module and keeps its own loop on purpose (it is verified and
shipped); the comment there records why its `async for` + library ping is safe.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

#: ±fraction applied to every reconnect delay.
JITTER = 0.25


@dataclass(frozen=True)
class HeartbeatPolicy:
    """One venue's liveness contract.

    ``mode`` decides what the heartbeat task sends:

    * ``client_ping``      — send a ping every ``ping_every_s`` seconds;
    * ``ping_after_idle``  — send a ping when the connection has been quiet for ``ping_after_idle_s``
                             (OKX and Hyperliquid behave this way; a fixed cadence would ping a busy
                             socket for no reason);
    * ``server_driven``    — the venue sends its own pings and we only answer (the library does);
                             the heartbeat task watches the silence budget and nothing else.
    """

    mode: str
    ping_every_s: float = 0.0
    ping_after_idle_s: float = 0.0
    silence_budget_s: float = 60.0
    note: str = ""

    def __post_init__(self) -> None:
        if self.mode not in ("client_ping", "ping_after_idle", "server_driven"):
            raise ValueError(f"unknown heartbeat mode {self.mode!r}")
        if self.mode == "client_ping" and self.ping_every_s <= 0:
            raise ValueError("client_ping needs ping_every_s > 0")
        if self.mode == "ping_after_idle" and self.ping_after_idle_s <= 0:
            raise ValueError("ping_after_idle needs ping_after_idle_s > 0")
        if self.silence_budget_s <= 0:
            raise ValueError("silence_budget_s must be > 0")


#: The venues this package can speak to, with the contracts their own docs state. The numbers are
#: the reason this table is data: one shared timeout cannot be right for all of them (a 60 s budget
#: would kill a healthy Binance perps socket, which can legitimately stay quiet for minutes).
VENUE_POLICIES: dict[str, HeartbeatPolicy] = {
    "bybit": HeartbeatPolicy(
        "client_ping", ping_every_s=20.0, silence_budget_s=60.0,
        note="Bybit: ping every ~20 s; a socket quiet for 60 s is dead."),
    "binance": HeartbeatPolicy(
        "server_driven", silence_budget_s=240.0,
        note="Binance: the venue sends its own pings (the client only answers); the futures market "
             "stream may legitimately be quiet for minutes — 240 s budget, spot is 45 s."),
    "okx": HeartbeatPolicy(
        "ping_after_idle", ping_after_idle_s=20.0, silence_budget_s=75.0,
        note="OKX: ping only after ~20 s of quiet; the venue keeps a quiet instrument alive at a"
             " ~60 s cadence, so 40 s tripped the budget first — 75 s is the dead-socket line."),
    "hyperliquid": HeartbeatPolicy(
        "ping_after_idle", ping_after_idle_s=30.0, silence_budget_s=60.0,
        note="Hyperliquid: ping after ~30 s of quiet."),
    "mexc": HeartbeatPolicy(
        "client_ping", ping_every_s=15.0, silence_budget_s=45.0,
        note="MEXC: ping every ~15 s."),
}


class ReconnectBackoff:
    """Escalating delay that only resets on **parsed data**.

    A socket that opens and immediately dies must keep escalating: resetting the ladder on
    ``connect()`` (the common mistake) turns a venue-side outage into a 1-second hammer.
    """

    def __init__(self, base: float = 1.0, factor: float = 2.0, cap: float = 30.0,
                 jitter: float = JITTER, rng: Optional[random.Random] = None) -> None:
        self.base = float(base)
        self.factor = float(factor)
        self.cap = float(cap)
        self.jitter = max(0.0, float(jitter))
        self._rng = rng or random.Random()
        self._current = self.base
        self.attempts = 0
        self.reset_count = 0

    @property
    def current(self) -> float:
        """The next un-jittered delay the ladder will ask for."""
        return self._current

    def record_parsed(self) -> None:
        """A frame was decoded — the connection is genuinely working; start over."""
        if self._current != self.base:
            self.reset_count += 1
        self._current = self.base
        self.attempts = 0

    def next_delay(self) -> float:
        """The delay to sleep before the next attempt, then escalate."""
        delay = self._current * (1.0 + self._rng.uniform(-self.jitter, self.jitter))
        self._current = min(self._current * self.factor, self.cap)
        self.attempts += 1
        return max(0.0, delay)


class FeedSession:
    """Read / heartbeat / reconnect for one websocket connection.

    ``connect``  — async callable returning a connection: async-iterable of raw frames, with
                   ``send(payload)`` and ``close()`` (websockets' ``ClientConnection`` fits).
    ``on_frame`` — async handler for one raw frame; raising counts as a session error.
    """

    def __init__(
        self,
        venue: str,
        connect: Callable[[], Awaitable[Any]],
        on_frame: Callable[[Any], Awaitable[None]],
        *,
        on_connected: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_disconnected: Optional[Callable[[Optional[BaseException]], Awaitable[None]]] = None,
        policy: Optional[HeartbeatPolicy] = None,
        backoff: Optional[ReconnectBackoff] = None,
        ping_payload: Any = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        heartbeat_tick_s: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.venue = venue
        self.policy = policy or VENUE_POLICIES.get(venue) or HeartbeatPolicy("client_ping", 20.0, silence_budget_s=60.0)
        self._connect = connect
        self._on_frame = on_frame
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._backoff = backoff or ReconnectBackoff()
        self._ping_payload = ping_payload
        self._sleep = sleep
        self._clock = clock
        self._heartbeat_tick = max(0.001, float(heartbeat_tick_s))
        self._running = False
        self._conn: Any = None
        self._heartbeats = 0
        self._frames = 0
        self._reconnects = 0
        self._last_frame_ms = 0
        self.last_error: str = ""

    # ── lifecycle ────────────────────────────────────────────
    async def run(self) -> None:
        """Run until :meth:`stop` (never raises: a dead socket is a reconnect, not an error)."""
        self._running = True
        while self._running:
            heartbeat: Optional[asyncio.Task] = None
            error: Optional[BaseException] = None
            try:
                self._conn = await self._connect()
                self._last_frame_ms = self._now_ms()
                if self._on_connected is not None:
                    await self._on_connected(self._conn)
                heartbeat = asyncio.create_task(self._heartbeat_loop())
                async for raw in self._conn:            # ← never cancelled from outside
                    await self._on_frame(raw)
                    self._frames += 1
                    self._last_frame_ms = self._now_ms()
                    self._backoff.record_parsed()       # the ladder resets on DATA, not on connect
            except asyncio.CancelledError:
                raise
            except BaseException as exc:                # noqa: BLE001 — a feed must survive anything
                error = exc
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("%s feed session ended: %s", self.venue, self.last_error)
            finally:
                if heartbeat is not None:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)
                await self._close_conn()
                if self._on_disconnected is not None:
                    try:
                        await self._on_disconnected(error)
                    except Exception:                   # pragma: no cover - hook errors are logged
                        logger.warning("%s disconnect hook failed", self.venue, exc_info=True)
            if not self._running:
                break
            delay = self._backoff.next_delay()
            self._reconnects += 1
            logger.info("%s feed reconnecting in %.1fs (attempt %d)", self.venue, delay,
                        self._backoff.attempts)
            await self._sleep(delay)

    async def stop(self) -> None:
        """Ask the session to close: the reader exits with the socket, no task is left behind."""
        self._running = False
        await self._close_conn()

    # ── internals ────────────────────────────────────────────
    def _now_ms(self) -> int:
        #: Injected clock (`time.monotonic` in production): the heartbeat contract is a *virtual*
        #: time contract, so tests drive it without waiting on real seconds.
        return int(self._clock() * 1000)

    async def _close_conn(self) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            await conn.close()
        except Exception:                                # pragma: no cover - socket errors
            logger.debug("%s close failed", self.venue, exc_info=True)

    async def _heartbeat_loop(self) -> None:
        """Its own task: it may only *send*, and it may only *watch* the silence budget."""
        policy = self.policy
        last_ping = self._clock()
        try:
            while True:
                await self._sleep(self._heartbeat_tick)
                idle = (self._now_ms() - self._last_frame_ms) / 1000.0
                if idle >= policy.silence_budget_s:
                    logger.warning("%s feed silent for %.1fs (budget %.1fs) — forcing a reconnect",
                                   self.venue, idle, policy.silence_budget_s)
                    await self._close_conn()
                    return
                if policy.mode == "server_driven":
                    continue
                since_ping = self._clock() - last_ping
                due = (policy.mode == "client_ping" and since_ping >= policy.ping_every_s)
                if not due and policy.mode == "ping_after_idle":
                    due = idle >= policy.ping_after_idle_s and since_ping >= policy.ping_after_idle_s
                if not due:
                    continue
                conn = self._conn
                if conn is None:
                    return
                try:
                    await conn.send(self._ping_payload if self._ping_payload is not None else "ping")
                    self._heartbeats += 1
                    last_ping = self._clock()
                except Exception as exc:                 # noqa: BLE001 — a failed ping is a dead socket
                    logger.warning("%s heartbeat failed: %s", self.venue, exc)
                    await self._close_conn()
                    return
        except asyncio.CancelledError:
            raise

    def stats(self) -> dict[str, Any]:
        """What a status line needs — counters, not opinions."""
        return {
            "venue": self.venue,
            "mode": self.policy.mode,
            "frames": self._frames,
            "heartbeats": self._heartbeats,
            "reconnects": self._reconnects,
            "backoff_s": round(self._backoff.current, 2),
            "silence_budget_s": self.policy.silence_budget_s,
            "running": self._running,
            "last_error": self.last_error,
        }
