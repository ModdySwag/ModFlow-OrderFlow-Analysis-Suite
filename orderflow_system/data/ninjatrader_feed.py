"""NinjaTrader 8 feed — the suite reads a running terminal through the shipped ModFlow bridge.

NinjaTrader publishes no market-data-out API, so the integration is the same shape as the Bookmap
one: a small read-only add-on runs **inside** NinjaTrader (``data/ninjatrader_bridge/``), subscribes
to the platform's own ``MarketData`` / ``MarketDepth`` callbacks and republishes them on loopback;
this module connects to that port and turns the frames into the suite's own ``Tick`` and
``OrderbookSnapshot`` models.

Wire format (the bridge writes exactly this; NUL-terminated JSON, UTF-8, one message per frame)::

    {"Type":"hello",  "Addon":"modflow-nt-bridge", "NT":"8.1.8.2", "Port":8790,
                      "Connection":{"Name":"Simulation","Status":"Connected"},
                      "Accounts":[{"Name":"Sim101","Sim":true}]}
    {"Type":"quote",  "Instrument":"NQ 12-26", "Last":25431.25, "Bid":25431.0, "Ask":25431.25,
                      "BidSize":3, "AskSize":2, "Volume":184233, "Ts":1789425000123}
    {"Type":"trade",  "Instrument":"NQ 12-26", "Price":25431.25, "Size":1, "Aggressor":"buy"}
    {"Type":"depth",  "Instrument":"NQ 12-26", "Side":"bid", "Price":25431.0, "Size":14,
                      "Operation":"update", "Position":0}
    {"Type":"depthsnapshot", "Instrument":"NQ 12-26", "Bids":[[p,s],..], "Asks":[[p,s],..]}
    {"Type":"heartbeat"}
    {"Type":"error",  "RequestId":"r1", "Message":".."}

``Type`` values are matched case-insensitively; unknown types are counted as rejects rather than
raising — a bridge that grows a new message must not take the suite down. Every field that reaches
an engine passes through :func:`_num`/:func:`_size`, so a NaN/Infinity in a frame can never reach
the aggregates (the venue-value rule the security sweep pinned).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import socket
import time
from typing import Any, Callable, Optional

from orderflow_system.data.feed_session import ReconnectBackoff
from orderflow_system.data.models import (
    OrderbookLevel, OrderbookSnapshot, Side, Tick,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790                       # the bridge's convention (Bookmap's add-on uses 8791)
PROTOCOL = "modflow-nt-jsonl"
BRIDGE_NAME = "modflow-nt-bridge"
#: The frame terminator. JSON messages are text; a NUL between them survives any chunking.
FRAME = b"\x00"
MAX_FRAME = 1 << 20                       # 1 MiB per message: a sane ceiling, never a buffer blow-up
#: The bridge heartbeats every 5 s; three missed ones plus slack is a dead socket.
SILENCE_BUDGET_S = 30.0
#: Frame type → the counter it lands in.
COUNTERS = {"hello": "hello", "quote": "quotes", "trade": "trades", "depth": "depth",
            "depthsnapshot": "snapshots", "heartbeat": "heartbeats", "bye": "bye", "pong": "pongs"}


def _clean(value: Any) -> Any:
    """JSON-safe scalars only — a message field is data from another process, never trusted."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:120]


def _num(value: Any) -> float:
    """A finite float or 0.0 — ``json`` accepts bare NaN/Infinity and they poison comparisons."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return out if math.isfinite(out) else 0.0


def _size(value: Any) -> float:
    """A finite, non-negative size."""
    return max(0.0, _num(value))


def parse_frame(text: str) -> Optional[dict[str, Any]]:
    """One frame → a message dict, or None when it is not one. Never raises."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        message = json.loads(text)
    except ValueError:
        return None
    if not isinstance(message, dict):
        return None
    kind = str(message.get("Type") or message.get("type") or "").strip().lower()
    message["Type"] = kind
    return message


def _sample_of(message: dict[str, Any]) -> dict[str, Any]:
    """A compact 'here is what it is sending' for the connection test — no dumping raw frames."""
    kind = message.get("Type") or "?"
    row = {"kind": kind, "instrument": str(_clean(message.get("Instrument")) or "")[:32],
           "ts": _clean(message.get("Ts"))}
    if kind == "trade":
        row["price"] = _clean(message.get("Price"))
        row["size"] = _clean(message.get("Size"))
        row["aggressor"] = _clean(message.get("Aggressor"))
    elif kind in ("quote", "snapshot"):
        row["bid"] = _clean(message.get("Bid"))
        row["ask"] = _clean(message.get("Ask"))
        row["last"] = _clean(message.get("Last"))
    elif kind in ("depth", "depthsnapshot"):
        row["side"] = _clean(message.get("Side"))
        row["price"] = _clean(message.get("Price"))
        row["size"] = _clean(message.get("Size"))
    return row


def _connect(host: str, port: int, timeout: float) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.2, float(timeout)))
    sock.connect((host, port))
    return sock


def _send_frame(sock: socket.socket, payload: dict[str, Any]) -> None:
    sock.sendall(json.dumps(payload).encode("utf-8") + FRAME)


def _read_frames(sock: socket.socket, seconds: float, timeout: float,
                 on_message: Callable[[dict[str, Any]], None]) -> Optional[str]:
    """Read frames for ``seconds``; returns an error string when the stream died mid-read."""
    deadline = time.time() + max(0.2, float(seconds))
    buf = b""
    sock.settimeout(max(0.2, min(float(timeout), 0.5)))
    while time.time() < deadline:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        except OSError as exc:
            return f"{type(exc).__name__}: {exc}"
        if not chunk:
            return "the bridge closed the connection"
        buf += chunk
        if len(buf) > MAX_FRAME:
            buf = buf[-4096:]                      # a frame this long is not one of ours
        while FRAME in buf:
            raw, buf = buf.split(FRAME, 1)
            message = parse_frame(raw.decode("utf-8", errors="replace"))
            if message is not None:
                on_message(message)
    return None


def ninjatrader_probe(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, seconds: float = 2.5,
                      timeout: float = 3.0, symbol: str = "", want_depth: bool = True) -> dict[str, Any]:
    """Connect to the bridge's port, subscribe to ``symbol`` (if given), report what arrived.

    Never raises: every failure comes back as ``{"ok": False, "stage": …, "error": …, "detail": …}``
    so the settings view can print it verbatim. Stages, in the order they can fail: ``config``,
    ``connect``, ``hello``, ``done``.
    """
    host = str(host or "").strip() or DEFAULT_HOST
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 0
    if not (1 <= port <= 65535):
        return {"ok": False, "stage": "config", "host": host, "port": port,
                "error": "no port to connect to",
                "detail": f"port {port!r} is not a TCP port; the bridge binds {DEFAULT_PORT} and "
                          f"writes the line 'listening on 127.0.0.1:{DEFAULT_PORT}' to its log."}

    out: dict[str, Any] = {"ok": False, "stage": "connect", "host": host, "port": port,
                           "protocol": PROTOCOL,
                           "messages": {"hello": 0, "quotes": 0, "trades": 0, "depth": 0,
                                        "snapshots": 0, "heartbeats": 0, "bye": 0, "other": 0},
                           "rejects": [], "sample": {}, "bridge": {}, "depth_levels": 0,
                           "started": time.time()}
    try:
        sock = _connect(host, port, timeout)
    except OSError as exc:
        return {**out, "stage": "connect", "error": f"could not connect to {host}:{port}",
                "detail": f"{type(exc).__name__}: {exc}. The bridge is a server inside NinjaTrader: "
                          f"if nothing answers, NinjaTrader is not running — or the DLL is not "
                          f"installed (bin\\Custom\\AddOns, compiled once in the platform\u2019s own NinjaScript Editor)."}

    want = str(symbol or "").strip().upper()
    try:
        if want:
            _send_frame(sock, {"Type": "subscribe", "Instrument": want,
                               "Channels": ["quote", "trade", "depth"] if want_depth else ["quote", "trade"]})

        def _count(message: dict[str, Any]) -> None:
            kind = message.get("Type") or ""
            counter = COUNTERS.get(kind)
            if counter:
                out["messages"][counter] += 1
            else:
                out["messages"]["other"] += 1
            if kind == "hello":
                out["bridge"] = {k: _clean(message.get(k)) for k in
                                 ("Addon", "Version", "NT", "Machine", "Port", "Mode")}
                connection = message.get("Connection") or {}
                if isinstance(connection, dict):
                    out["bridge"]["Connection"] = _clean(connection.get("Name"))
                    out["bridge"]["Status"] = _clean(connection.get("Status"))
                accounts = message.get("Accounts") or []
                if isinstance(accounts, list):
                    out["bridge"]["Accounts"] = [str(_clean((a or {}).get("Name")) or "")
                                                 for a in accounts[:8] if isinstance(a, dict)]
                out["stage"] = "hello"
            elif kind == "error":
                out["rejects"].append(f"bridge error: {_clean(message.get('Message'))}")
            elif not out["sample"] and kind in ("trade", "quote", "depth", "depthsnapshot"):
                out["sample"] = _sample_of(message)
            if kind == "depthsnapshot":
                try:
                    out["depth_levels"] += len(message.get("Bids") or []) + len(message.get("Asks") or [])
                except TypeError:
                    pass
            row_symbol = str(_clean(message.get("Instrument")) or "").upper()
            if want and row_symbol and want not in row_symbol and row_symbol not in want:
                out["rejects"].append(f"{row_symbol!r} is not the requested {want!r}")

        death = _read_frames(sock, seconds, timeout, _count)
        if death is not None and out["stage"] != "hello":
            out["stage"] = "read"
            out["error"] = "the bridge closed the connection"
            out["detail"] = f"{death}; the bridge may have been unloaded in NinjaTrader."
    finally:
        try:
            sock.close()
        except OSError:
            pass

    if out["stage"] == "hello" or out["messages"]["hello"]:
        out["ok"] = True
        out["stage"] = "done"
        bridge = out["bridge"]
        out["note"] = (f"bridge {bridge.get('Addon') or BRIDGE_NAME} "
                       f"{bridge.get('Version') or ''}".strip()
                       + (f" on NinjaTrader {bridge.get('NT')}" if bridge.get("NT") else "")
                       + (f" · connection {bridge.get('Connection') or '?'}"
                          f" ({bridge.get('Status') or '?'})" if bridge.get("Connection") else ""))
        levels = int(out.get("depth_levels") or 0)
        if out["messages"]["depth"]:
            out["depth"] = f"level-2 depth is flowing ({out['messages']['depth']} level updates)"
        elif out["messages"]["snapshots"] and levels:
            out["depth"] = (f"a depth snapshot arrived with {levels} ladder levels — live updates "
                            f"will confirm on a trading feed")
        elif want and want_depth:
            out["depth"] = ("no level-2 depth arrived — this feed/tier may not carry it; quotes "
                            "and trades are unaffected")
    else:
        out["stage"] = "hello"
        out["error"] = "connected, but no bridge hello arrived"
        out["detail"] = ("something is listening on that port, but it is not this bridge: the first "
                         "frame must be a hello from " + BRIDGE_NAME + ".")
    out["seconds"] = round(time.time() - out["started"], 2)
    return out


def ninjatrader_request(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, payload: dict[str, Any] | None = None,
                        *, timeout: float = 8.0,
                        want: tuple[str, ...] = ("instruments", "bars", "quote", "capabilities", "resolve", "error"),
                        request_id: str = "r1") -> Optional[dict[str, Any]]:
    """One request/reply round-trip against the bridge. Returns the reply frame, or None.

    The bridge answers every request with a frame carrying the same ``RequestId`` (errors come
    back as ``{"Type":"error", "RequestId":…, "Message":…}``). Never raises.
    """
    body = dict(payload or {})
    body.setdefault("RequestId", request_id)
    out_box: dict[str, Any] = {}

    def _grab(message: dict[str, Any]) -> None:
        if str(message.get("RequestId") or "") != body["RequestId"]:
            return
        if (message.get("Type") or "") in want and "reply" not in out_box:
            out_box["reply"] = message

    try:
        sock = _connect(host, port, timeout)
    except OSError:
        return None
    try:
        _send_frame(sock, body)
        deadline = time.time() + max(0.5, float(timeout))
        buf = b""
        sock.settimeout(0.4)
        while time.time() < deadline and "reply" not in out_box:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            if len(buf) > 4 * MAX_FRAME:
                break
            while FRAME in buf:
                raw, buf = buf.split(FRAME, 1)
                message = parse_frame(raw.decode("utf-8", errors="replace"))
                if message is not None:
                    _grab(message)
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return out_box.get("reply")


def ninjatrader_instruments(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *,
                            filter_text: str = "", kind: str = "") -> list[dict[str, Any]]:
    """The terminal's own instrument list (one round trip). Empty list when the bridge is down."""
    reply = ninjatrader_request(host, port,
                                {"Type": "instruments", "Filter": filter_text, "Kind": kind},
                                want=("instruments",), request_id="instruments")
    rows = (reply or {}).get("Instruments")
    return [row for row in (rows if isinstance(rows, list) else []) if isinstance(row, dict)]


def ninjatrader_resolve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, name: str = "") -> dict[str, Any]:
    """Ask the terminal what a typed name is (``NQ1`` → ``NQ 12-26``). Empty dict when down."""
    reply = ninjatrader_request(host, port, {"Type": "resolve", "Instrument": name},
                                want=("resolve",), request_id="resolve")
    return reply if isinstance(reply, dict) else {}


def nt_side(aggressor: Any, price: float, bid: float, ask: float) -> Side:
    """Aggressor → Side, with the price-vs-quote heuristic when the bridge could not tell.

    The bridge already compares the print against its own bid/ask (the platform does not label
    trades); the fallback here repeats the same rule for frames that arrived without a label.
    """
    tag = str(aggressor or "").strip().lower()
    if tag == "buy":
        return Side.BUY
    if tag == "sell":
        return Side.SELL
    if ask > 0 and price >= ask:
        return Side.BUY
    if bid > 0 and price <= bid:
        return Side.SELL
    return Side.BUY


class NinjaTraderFeed:
    """Streams one NinjaTrader 8 terminal into the suite: trades + quotes + level-2 depth.

    Same callback contract as every other adapter (``on_tick(symbol, Tick)``,
    ``on_orderbook(symbol, OrderbookSnapshot)``), so the pipelines, the atlas hub and the heatmap
    stay source-agnostic. ``symbols`` maps the app's symbol → the name sent to the bridge
    (``NQ`` or ``NQ1`` both resolve to the terminal's front-month contract).
    """

    def __init__(self, symbols: dict[str, str], on_tick: Optional[Callable] = None,
                 on_orderbook: Optional[Callable] = None, host: str = DEFAULT_HOST,
                 port: int = DEFAULT_PORT, depth_levels: int = 10):
        self.symbols = {str(k): str(v or k) for k, v in dict(symbols or {}).items()}
        self.on_tick = on_tick
        self.on_orderbook = on_orderbook
        self.host = str(host or DEFAULT_HOST)
        try:
            self.port = int(port)
        except (TypeError, ValueError):
            self.port = DEFAULT_PORT
        try:
            self.depth_levels = max(1, min(50, int(depth_levels)))
        except (TypeError, ValueError):
            self.depth_levels = 10
        self.bridge_info: dict[str, Any] = {}
        self.last_error: str = ""
        self._running = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._book: dict[str, dict[str, dict[float, float]]] = {}   # symbol → side → {price: size}
        self._book_sent: dict[str, float] = {}                       # symbol → monotonic of last emit
        self._seq = 0
        self.stats = {"trades": 0, "quotes": 0, "depth": 0, "snapshots": 0, "heartbeats": 0,
                      "rejects": 0, "reconnects": 0}

    # ── connection ──────────────────────────────────────────────────
    def connect(self) -> bool:
        """One shot: is the bridge there, and what does it say? Stores ``bridge_info``."""
        try:
            sock = _connect(self.host, self.port, 3.0)
        except OSError as exc:
            self.last_error = f"could not connect to {self.host}:{self.port} ({exc})"
            logger.warning("NinjaTrader bridge not reachable: %s", self.last_error)
            return False
        got: dict[str, Any] = {}

        def _hello(message: dict[str, Any]) -> None:
            if message.get("Type") == "hello":
                got.update(message)

        try:
            _read_frames(sock, 1.5, 2.0, _hello)
        finally:
            try:
                sock.close()
            except OSError:
                pass
        if got:
            self.bridge_info = {k: _clean(got.get(k)) for k in
                                ("Addon", "Version", "NT", "Machine", "Port", "Mode")}
            connection = got.get("Connection") or {}
            if isinstance(connection, dict):
                self.bridge_info["Connection"] = _clean(connection.get("Name"))
                self.bridge_info["Status"] = _clean(connection.get("Status"))
            logger.info("NinjaTrader bridge: %s", self.bridge_info)
            return True
        self.last_error = "connected to the port, but no bridge hello arrived"
        logger.warning("NinjaTrader bridge answered without a hello: %s:%s", self.host, self.port)
        return False

    async def start(self) -> None:
        """Connect, subscribe every symbol, read frames — reconnecting with a jittered ladder."""
        self._running = True
        backoff = ReconnectBackoff()
        while self._running:
            try:
                await self._run_once(backoff)
            except asyncio.CancelledError:
                raise
            except Exception as exc:                      # noqa: BLE001 — a feed survives anything
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("NinjaTrader feed session ended: %s", self.last_error)
            if not self._running:
                break
            delay = backoff.next_delay()
            self.stats["reconnects"] += 1
            logger.info("NinjaTrader feed reconnecting in %.1fs", delay)
            await asyncio.sleep(delay)

    async def _run_once(self, backoff: ReconnectBackoff) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self._inbuf = b""                          # per-connection: frames may straddle reads
        try:
            for nt_name in self.symbols.values():
                self._send({"Type": "subscribe", "Instrument": nt_name,
                            "Channels": ["quote", "trade", "depth"], "DepthLevels": self.depth_levels})
            while self._running:
                raw = await asyncio.wait_for(self._reader.read(65536), timeout=SILENCE_BUDGET_S)
                if not raw:
                    raise ConnectionError("the bridge closed the connection")
                self._inbuf += raw
                if len(self._inbuf) > MAX_FRAME * 4:   # runaway junk without a frame mark
                    self._inbuf = b""
                    self.stats["rejects"] = self.stats.get("rejects", 0) + 1
                    continue
                while FRAME in self._inbuf:
                    frame, _, self._inbuf = self._inbuf.partition(FRAME)
                    if not frame.strip():
                        continue
                    message = parse_frame(frame.decode("utf-8", errors="replace"))
                    if message is not None:
                        await self._handle(message)
                        backoff.record_parsed()
        finally:
            writer, self._writer = self._writer, None
            self._reader = None
            if writer is not None:
                try:
                    writer.close()
                except Exception:                          # pragma: no cover - socket errors
                    pass

    async def stop(self) -> None:
        self._running = False
        writer, self._writer = self._writer, None
        if writer is not None:
            try:
                writer.close()
            except Exception:                              # pragma: no cover
                pass

    def _send(self, payload: dict[str, Any]) -> None:
        payload.setdefault("Ts", int(time.time() * 1000))
        try:
            if self._writer is not None:
                self._writer.write(json.dumps(payload).encode("utf-8") + FRAME)
        except Exception:                                  # pragma: no cover - socket errors
            logger.debug("NinjaTrader send failed", exc_info=True)

    # ── frames ──────────────────────────────────────────────────────
    def _symbol_for(self, nt_name: str) -> Optional[str]:
        name = str(nt_name or "").strip().upper()
        for app_symbol, mapped in self.symbols.items():
            if str(mapped).strip().upper() == name:
                return app_symbol
        for app_symbol in self.symbols:
            if name.startswith(str(app_symbol).upper()):
                return app_symbol          # "NQ" configured, frame says "NQ 12-26"
        return None

    async def _handle(self, message: dict[str, Any]) -> None:
        kind = message.get("Type") or ""
        if kind == "heartbeat":
            self.stats["heartbeats"] += 1
            return
        if kind == "error":
            self.stats["rejects"] += 1
            self.last_error = str(_clean(message.get("Message")) or "bridge error")
            logger.warning("NinjaTrader bridge error: %s", self.last_error)
            return
        if kind == "hello":
            self.bridge_info = {k: _clean(message.get(k)) for k in
                                ("Addon", "Version", "NT", "Machine", "Port", "Mode")}
            return
        if kind == "trade":
            await self._on_trade(message)
            return
        if kind == "quote":
            self.stats["quotes"] += 1
            self._update_top(message)
            return
        if kind == "depth":
            self.stats["depth"] += 1
            await self._on_depth(message)
            return
        if kind == "depthsnapshot":
            self.stats["snapshots"] += 1
            await self._on_depth_snapshot(message)
            return
        self.stats["rejects"] += 1

    async def _on_trade(self, message: dict[str, Any]) -> None:
        app_symbol = self._symbol_for(message.get("Instrument"))
        if app_symbol is None:
            self.stats["rejects"] += 1
            return
        price = _num(message.get("Price"))
        if price <= 0:
            self.stats["rejects"] += 1
            return
        size = _size(message.get("Size")) or 1.0
        bid, ask = self._top_of(app_symbol)
        side = nt_side(message.get("Aggressor"), price, bid, ask)
        ts = int(_num(message.get("Ts"))) or int(time.time() * 1000)
        self._seq += 1
        tick = Tick(timestamp_ms=ts, price=price, size=size, side=side,
                    trade_id=f"nt_{ts}_{self._seq}")
        self.stats["trades"] += 1
        if self.on_tick:
            await self.on_tick(app_symbol, tick)

    def _top_of(self, app_symbol: str) -> tuple[float, float]:
        book = self._book.get(app_symbol) or {}
        bids = book.get("bid") or {}
        asks = book.get("ask") or {}
        bid = max(bids) if bids else 0.0
        ask = min(asks) if asks else 0.0
        return bid, ask

    def _update_top(self, message: dict[str, Any]) -> None:
        """A quote frame keeps the ladder's inside levels in sync for the trade-side heuristic."""
        app_symbol = self._symbol_for(message.get("Instrument"))
        if app_symbol is None:
            return
        book = self._book.setdefault(app_symbol, {"bid": {}, "ask": {}})
        bid, bid_size = _num(message.get("Bid")), _size(message.get("BidSize"))
        ask, ask_size = _num(message.get("Ask")), _size(message.get("AskSize"))
        # One level, REPLACED per quote. The old shape kept every price ever quoted, so
        # `max(bids)` was the highest price of the whole session — once the market moved away,
        # the trade-side heuristic compared prints against a top that no longer existed (and the
        # dict grew for the life of the process).
        if bid > 0:
            book["bid"] = {bid: bid_size}
        if ask > 0:
            book["ask"] = {ask: ask_size}

    async def _on_depth(self, message: dict[str, Any]) -> None:
        app_symbol = self._symbol_for(message.get("Instrument"))
        if app_symbol is None:
            self.stats["rejects"] += 1
            return
        side = "ask" if str(message.get("Side") or "").strip().lower() == "ask" else "bid"
        price = _num(message.get("Price"))
        size = _size(message.get("Size"))
        if price <= 0:
            self.stats["rejects"] += 1
            return
        ladder = self._book.setdefault(app_symbol, {"bid": {}, "ask": {}})[side]
        operation = str(message.get("Operation") or "update").strip().lower()
        if operation == "remove" or size <= 0:
            ladder.pop(price, None)
        else:
            ladder[price] = size
        await self._emit_book(app_symbol)

    async def _on_depth_snapshot(self, message: dict[str, Any]) -> None:
        app_symbol = self._symbol_for(message.get("Instrument"))
        if app_symbol is None:
            self.stats["rejects"] += 1
            return
        book: dict[str, dict[float, float]] = {"bid": {}, "ask": {}}
        for side, key in (("bid", "Bids"), ("ask", "Asks")):
            rows = message.get(key) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    price, size = _num(row[0]), _size(row[1])
                    if price > 0:
                        book[side][price] = size
        self._book[app_symbol] = book
        await self._emit_book(app_symbol, force=True)

    async def _emit_book(self, app_symbol: str, force: bool = False) -> None:
        """Publish the ladder as an OrderbookSnapshot, coalesced to ~10/s like the MT5 poll."""
        now = time.monotonic()
        if not force and now - self._book_sent.get(app_symbol, 0.0) < 0.1:
            return
        book = self._book.get(app_symbol)
        if not book or not self.on_orderbook:
            return
        bids = sorted(book["bid"].items(), key=lambda kv: -kv[0])[: self.depth_levels]
        asks = sorted(book["ask"].items(), key=lambda kv: kv[0])[: self.depth_levels]
        if not bids and not asks:
            return
        self._book_sent[app_symbol] = now
        snapshot = OrderbookSnapshot(
            timestamp_ms=int(time.time() * 1000),
            bids=[OrderbookLevel(price=p, quantity=q) for p, q in bids],
            asks=[OrderbookLevel(price=p, quantity=q) for p, q in asks],
        )
        if self.on_orderbook:
            await self.on_orderbook(app_symbol, snapshot)
