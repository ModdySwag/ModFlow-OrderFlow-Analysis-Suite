"""NinjaTrader bridge tests — the suite's reader against a **mock bridge**, written to the wire
format in `data/ninjatrader_bridge/README.md`.

Nothing here needs NinjaTrader, the built DLL or a network: the mock is a loopback TCP server that
speaks the same NUL-framed JSON as the shipped add-on, so this file is half of the contract — a
change to the frame format is a change in both places on purpose.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from typing import Any

# ── frame-level helpers ─────────────────────────────────────────────────────────────────────


def test_parse_frame_reads_our_frames_and_never_raises():
    from orderflow_system.data.ninjatrader_feed import parse_frame

    assert parse_frame('{"Type":"trade","Price":1}')["Type"] == "trade"
    assert parse_frame('{"type":"QUOTE"}')["Type"] == "quote", "type matching is case-insensitive"
    assert parse_frame("{not json") is None
    assert parse_frame("[1,2,3]") is None, "a bare list is not a message"
    assert parse_frame("") is None


def test_num_and_size_gate_non_finite_values():
    from orderflow_system.data.ninjatrader_feed import _num, _size

    assert _num("2.5") == 2.5
    assert _num(float("nan")) == 0.0, "json accepts bare NaN; it must never reach an engine"
    assert _num(float("inf")) == 0.0
    assert _num(None) == 0.0 and _num("junk") == 0.0
    assert _size(-4) == 0.0, "a negative size is not a size"
    assert _size(3) == 3.0


def test_nt_side_prefers_the_aggressor_and_falls_back_to_quote_comparison():
    from orderflow_system.data.models import Side
    from orderflow_system.data.ninjatrader_feed import nt_side

    assert nt_side("buy", 10.0, 9.9, 10.1) == Side.BUY
    assert nt_side("sell", 10.0, 9.9, 10.1) == Side.SELL
    assert nt_side("", 10.1, 9.9, 10.1) == Side.BUY, "print at the ask is a buy"
    assert nt_side("", 9.9, 9.9, 10.1) == Side.SELL, "print at the bid is a sell"
    assert nt_side("", 10.0, 0.0, 0.0) == Side.BUY, "no quotes at all: the MT5 default holds"


# ── the mock bridge (the contract half) ─────────────────────────────────────────────────────


class MockNtBridge(threading.Thread):
    """Speaks the shipped bridge's wire format: hello on accept, bursts on subscribe, replies by
    RequestId. Records every frame the client sent so tests can assert on the conversation."""

    def __init__(self, *, hello: bool = True, frames: int = 3, garbage: bytes = b"",
                 instrument: str = "NQ 12-26", subscribe_instrument: str = "NQ 12-26",
                 nt: str = "8.1.8.2", connection: str = "Simulation", status: str = "Connected",
                 send_depth: bool = True, bad_trade_price: bool = False,
                 other_instrument_every: int = 0, reply_error_for: str = "", port: int = 0) -> None:
        super().__init__(daemon=True)
        self.hello = hello
        self.frames = frames
        self.garbage = garbage
        self.instrument = instrument
        self.subscribe_instrument = subscribe_instrument
        self.nt = nt
        self.connection = connection
        self.status = status
        self.send_depth = send_depth
        self.bad_trade_price = bad_trade_price
        self.other_instrument_every = other_instrument_every
        self.reply_error_for = reply_error_for
        self.received: list[dict[str, Any]] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", port))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self.accepted = 0

    def frame(self, message: dict[str, Any]) -> bytes:
        return json.dumps(message).encode("utf-8") + b"\x00"

    def hello_frame(self) -> bytes:
        return self.frame({
            "Type": "hello", "Addon": "modflow-nt-bridge", "Version": "1.0", "NT": self.nt,
            "Machine": "TESTBOX", "Port": self.port, "Mode": "read-only",
            "Connection": {"Name": self.connection, "Status": self.status},
            "Accounts": [{"Name": "Sim101", "Connection": self.connection, "Status": self.status,
                          "Sim": True}],
        })

    def _burst(self, conn: socket.socket) -> None:
        conn.sendall(self.frame({"Type": "depthsnapshot", "Instrument": self.instrument,
                                 "Bids": ([[100.0, 5], [99.75, 9]] if self.send_depth else []),
                                 "Asks": ([[100.25, 3], [100.5, 7]] if self.send_depth else []),
                                 "Ts": 1789425000123}))
        conn.sendall(self.frame({"Type": "quote", "Instrument": self.instrument, "Last": 100.1,
                                 "Bid": 100.0, "Ask": 100.25, "BidSize": 5, "AskSize": 3,
                                 "Volume": 1000, "Ts": 1789425000124}))
        for i in range(self.frames):
            sym = self.instrument if not (self.other_instrument_every and i % self.other_instrument_every == 0) \
                else "ES 12-26"
            price = float("nan") if self.bad_trade_price else 100.2 + i * 0.25
            conn.sendall(self.frame({"Type": "trade", "Instrument": sym, "Price": price,
                                     "Size": 1 + i, "Aggressor": "buy" if i % 2 == 0 else "sell",
                                     "Ts": 1789425000125 + i}))
            if self.send_depth:
                conn.sendall(self.frame({"Type": "depth", "Instrument": sym, "Side": "bid" if i % 2 else "ask",
                                         "Price": 100.0 + i * 0.25, "Size": 4 + i,
                                         "Operation": "update", "Position": i, "Ts": 1789425000130 + i}))
        conn.sendall(self.frame({"Type": "heartbeat", "Ts": 1789425000999}))

    def _reply(self, conn: socket.socket, message: dict[str, Any]) -> None:
        kind = str(message.get("Type") or "")
        request_id = str(message.get("RequestId") or "")
        if self.reply_error_for and kind == self.reply_error_for:
            conn.sendall(self.frame({"Type": "error", "RequestId": request_id,
                                     "Message": "mock says no"}))
            return
        if kind == "instruments":
            conn.sendall(self.frame({"Type": "instruments", "RequestId": request_id, "Instruments": [
                {"Name": "NQ 12-26", "Root": "NQ", "Kind": "Future", "TickSize": 0.25,
                 "PointValue": 20, "Expiry": "2026-12-18", "Description": "E-mini Nasdaq-100"},
                {"Name": "ES 12-26", "Root": "ES", "Kind": "Future", "TickSize": 0.25,
                 "PointValue": 50, "Expiry": "2026-12-18", "Description": "E-mini S&P 500"},
            ]}))
        elif kind == "resolve":
            wanted = str(message.get("Instrument") or "")
            resolved = self.instrument if wanted.upper().rstrip("!").rstrip("1") == "NQ" else ""
            conn.sendall(self.frame({"Type": "resolve", "RequestId": request_id, "Instrument": wanted,
                                     "Resolved": resolved, "Root": "NQ" if resolved else "",
                                     "Front": bool(resolved)}))
        elif kind == "capabilities":
            conn.sendall(self.frame({"Type": "capabilities", "RequestId": request_id, "NT": self.nt,
                                     "Connections": [{"Name": self.connection, "Status": self.status}],
                                     "Accounts": [{"Name": "Sim101", "Sim": True}],
                                     "Depth": {"Enabled": True, "Events": 12}, "Mode": "read-only"}))
        elif kind == "quote":
            conn.sendall(self.frame({"Type": "quote", "RequestId": request_id, "Instrument": self.instrument,
                                     "Last": 100.1, "Bid": 100.0, "Ask": 100.25, "Ts": 1789425000200}))

    def run(self) -> None:
        deadline = time.time() + 6.0
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        self.accepted += 1
        conn.settimeout(0.2)
        buf = b""
        try:
            if self.hello:
                conn.sendall(self.hello_frame())
            if self.garbage:
                conn.sendall(self.garbage)
            while time.time() < deadline:
                try:
                    chunk = conn.recv(65536)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\x00" in buf:
                    raw, buf = buf.split(b"\x00", 1)
                    try:
                        message = json.loads(raw.decode("utf-8"))
                    except ValueError:
                        continue
                    if not isinstance(message, dict):
                        continue
                    self.received.append(message)
                    kind = str(message.get("Type") or "")
                    if kind == "subscribe":
                        self._burst(conn)
                    elif kind in ("instruments", "resolve", "capabilities", "quote"):
                        self._reply(conn, message)
                    elif kind == "ping":
                        conn.sendall(self.frame({"Type": "pong", "Ts": 1789425000300}))
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass


def _closed_port() -> int:
    """A port nothing listens on: open, take the number, close."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


# ── probe ───────────────────────────────────────────────────────────────────────────────────


def test_probe_reads_the_bridge_stream():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    server = MockNtBridge(frames=3)
    server.start()
    try:
        result = ninjatrader_probe("127.0.0.1", server.port, seconds=1.5, timeout=2.0, symbol="NQ")
        assert result["ok"] is True and result["stage"] == "done", result
        assert result["bridge"]["Addon"] == "modflow-nt-bridge"
        assert result["bridge"]["NT"] == "8.1.8.2"
        assert result["bridge"]["Connection"] == "Simulation"
        assert result["messages"]["hello"] == 1
        assert result["messages"]["trades"] == 3
        assert result["messages"]["depth"] == 3
        assert "level-2 depth is flowing" in result.get("depth", ""), result
        assert result["protocol"] == "modflow-nt-jsonl"
        assert "Simulation" in result["note"]
        subscribe = next(m for m in server.received if m.get("Type") == "subscribe")
        assert subscribe["Instrument"] == "NQ"
        assert "depth" in subscribe["Channels"]
    finally:
        server.join(timeout=1.0)


def test_a_listener_without_the_bridge_says_so():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    server = MockNtBridge(hello=False)
    server.start()
    try:
        result = ninjatrader_probe("127.0.0.1", server.port, seconds=1.0, timeout=2.0)
        assert result["ok"] is False and result["stage"] == "hello"
        assert "modflow-nt-bridge" in result["detail"]
    finally:
        server.join(timeout=1.0)


def test_no_bridge_listening_is_a_connect_error_with_the_install_hint():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    result = ninjatrader_probe("127.0.0.1", _closed_port(), seconds=0.5, timeout=1.0)
    assert result["ok"] is False and result["stage"] == "connect"
    assert "NinjaTrader" in result["detail"]
    assert "NinjaScript Editor" in result["detail"], \
        "the three install facts (running, folder, the editor) belong in the refusal"


def test_a_bad_port_is_a_config_error_not_a_crash():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    result = ninjatrader_probe("127.0.0.1", 99999)
    assert result["ok"] is False and result["stage"] == "config"


def test_bridge_garbage_is_reported_not_raised():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    server = MockNtBridge(garbage=b"\x01\x02not json at all\x00")
    server.start()
    try:
        result = ninjatrader_probe("127.0.0.1", server.port, seconds=1.0, timeout=2.0)
        assert result["ok"] is True, "the hello still arrived; a bad frame is data, not a crash"
    finally:
        server.join(timeout=1.0)


def test_no_depth_on_this_feed_is_said_plainly():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_probe

    server = MockNtBridge(send_depth=False)
    server.start()
    try:
        result = ninjatrader_probe("127.0.0.1", server.port, seconds=1.2, timeout=2.0, symbol="NQ")
        assert result["ok"] is True
        assert "no level-2 depth arrived" in result.get("depth", ""), result
    finally:
        server.join(timeout=1.0)


# ── request/reply ───────────────────────────────────────────────────────────────────────────


def test_request_round_trips_instruments():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_instruments

    server = MockNtBridge()
    server.start()
    try:
        rows = ninjatrader_instruments("127.0.0.1", server.port, filter_text="NQ")
        assert [r["Name"] for r in rows] == ["NQ 12-26", "ES 12-26"]
        assert rows[0]["TickSize"] == 0.25
        sent = next(m for m in server.received if m.get("Type") == "instruments")
        assert sent["Filter"] == "NQ"
    finally:
        server.join(timeout=2.0)


def test_request_round_trips_resolve_and_error_replies():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_request, ninjatrader_resolve

    server = MockNtBridge()
    server.start()
    try:
        reply = ninjatrader_resolve("127.0.0.1", server.port, "NQ1")
        assert reply.get("Resolved") == "NQ 12-26", "NQ1 resolves to the front-month contract"
        assert reply.get("Front") is True
    finally:
        server.join(timeout=2.0)

    erroring = MockNtBridge(reply_error_for="capabilities")
    erroring.start()
    try:
        reply = ninjatrader_request("127.0.0.1", erroring.port, {"Type": "capabilities"},
                                    want=("capabilities", "error"), request_id="c1")
        assert reply and reply["Type"] == "error" and reply["RequestId"] == "c1"
    finally:
        erroring.join(timeout=2.0)


def test_request_without_a_bridge_returns_none():
    from orderflow_system.data.ninjatrader_feed import ninjatrader_request

    assert ninjatrader_request("127.0.0.1", _closed_port(), {"Type": "capabilities"}, timeout=0.5) is None


# ── the feed ────────────────────────────────────────────────────────────────────────────────


def test_feed_connect_reads_the_hello():
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    server = MockNtBridge()
    server.start()
    try:
        feed = NinjaTraderFeed(symbols={"NQ": "NQ"}, host="127.0.0.1", port=server.port)
        assert feed.connect() is True
        assert feed.bridge_info["NT"] == "8.1.8.2"
        assert feed.bridge_info["Connection"] == "Simulation"
    finally:
        server.join(timeout=1.0)


def test_feed_connect_without_a_bridge_is_false_and_says_why():
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    feed = NinjaTraderFeed(symbols={"NQ": "NQ"}, host="127.0.0.1", port=_closed_port())
    assert feed.connect() is False
    assert "could not connect" in feed.last_error


def test_feed_streams_ticks_and_the_ladder():
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    server = MockNtBridge(frames=3)
    server.start()
    ticks: list[tuple[str, Any]] = []
    books: list[tuple[str, Any]] = []

    async def on_tick(symbol: str, tick: Any) -> None:
        ticks.append((symbol, tick))

    async def on_book(symbol: str, snapshot: Any) -> None:
        books.append((symbol, snapshot))

    async def main() -> None:
        feed = NinjaTraderFeed(symbols={"NQ": "NQ"}, on_tick=on_tick, on_orderbook=on_book,
                               host="127.0.0.1", port=server.port)
        task = asyncio.create_task(feed.start())
        await asyncio.sleep(1.4)
        await feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return feed

    feed = asyncio.run(main())

    assert ticks, "the mock sent trades; the feed must have emitted ticks"
    symbol, tick = ticks[0]
    assert symbol == "NQ", "frames say 'NQ 12-26'; the app's configured symbol is NQ"
    assert tick.price == 100.2 and tick.size == 1.0
    assert tick.trade_id.startswith("nt_")
    from orderflow_system.data.models import Side
    assert tick.side == Side.BUY and ticks[1][1].side == Side.SELL, "aggressor labels carry through"

    assert books, "the depth snapshot must produce a ladder"
    _symbol, snapshot = books[0]
    bid_prices = [level.price for level in snapshot.bids]
    ask_prices = [level.price for level in snapshot.asks]
    assert bid_prices == sorted(bid_prices, reverse=True)
    assert ask_prices == sorted(ask_prices)
    assert snapshot.bids[0].price == 100.0 and snapshot.asks[0].price == 100.25

    subscribe = next(m for m in server.received if m.get("Type") == "subscribe")
    assert subscribe["Instrument"] == "NQ"
    assert feed.stats["trades"] >= 3 and feed.stats["snapshots"] >= 1
    server.join(timeout=1.0)


def test_feed_unsubscribes_every_symbol_before_closing():
    """MEM-E-01: stop() asks the bridge to drop each subscription before the socket closes."""
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    server = MockNtBridge(frames=3)
    server.start()

    async def main() -> None:
        feed = NinjaTraderFeed(symbols={"NQ": "NQ", "ES": "ES"}, host="127.0.0.1", port=server.port)
        task = asyncio.create_task(feed.start())
        await asyncio.sleep(0.8)
        await feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(main())
    server.join(timeout=1.0)

    subscribed = [m["Instrument"] for m in server.received if m.get("Type") == "subscribe"]
    unsubscribed = [m["Instrument"] for m in server.received if m.get("Type") == "unsubscribe"]
    assert subscribed, "the feed subscribes on start"
    assert sorted(unsubscribed) == sorted(subscribed), (subscribed, unsubscribed)


def test_the_bridge_source_keeps_the_heartbeat_and_teardown_guards():
    """MEM-E-01/E-02/E-03 (source pin): one heartbeat, interrupted on Shutdown; a disconnect
    tears its own session down; and no load-kick thread survives in the static constructor."""
    from pathlib import Path

    src = (Path(__file__).parent / "data" / "ninjatrader_bridge" / "src" / "ModFlowBridge.cs") \
        .read_text(encoding="utf-8", errors="replace")
    assert "if (existing != null && existing.IsAlive) return;" in src, "one heartbeat thread per bridge"
    assert "hb.Interrupt()" in src, "Shutdown must break the heartbeat's sleep"
    assert "while (client != null)" in src, "the heartbeat loop must end with the session"
    assert "if (ReferenceEquals(client, conn))" in src, "a disconnect tears down its own session"
    assert "queue.CompleteAdding()" in src and "SubscribeCleanup();" in src
    assert "ModFlowBridge.LoadKick" not in src, "MEM-E-03: the static-ctor kick thread is gone"
    assert "restart NinjaTrader to clear it" in src, "the bind failure names the stale-copy case"


def test_feed_drops_a_non_finite_trade_and_counts_it():
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    server = MockNtBridge(frames=2, bad_trade_price=True)
    server.start()
    ticks: list[Any] = []

    async def on_tick(symbol: str, tick: Any) -> None:
        ticks.append(tick)

    async def main() -> Any:
        feed = NinjaTraderFeed(symbols={"NQ": "NQ"}, on_tick=on_tick, host="127.0.0.1", port=server.port)
        task = asyncio.create_task(feed.start())
        await asyncio.sleep(1.0)
        await feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return feed

    feed = asyncio.run(main())
    assert ticks == [], "a NaN price is not a print"
    assert feed.stats["rejects"] >= 2
    server.join(timeout=1.0)


def test_feed_maps_other_instruments_out():
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    server = MockNtBridge(frames=2, other_instrument_every=1)
    server.start()
    ticks: list[Any] = []

    async def on_tick(symbol: str, tick: Any) -> None:
        ticks.append((symbol, tick))

    async def main() -> Any:
        feed = NinjaTraderFeed(symbols={"NQ": "NQ"}, on_tick=on_tick, host="127.0.0.1", port=server.port)
        task = asyncio.create_task(feed.start())
        await asyncio.sleep(1.0)
        await feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return feed

    feed = asyncio.run(main())
    assert ticks == [], "ES frames are not the configured NQ stream"
    assert feed.stats["rejects"] >= 2
    server.join(timeout=1.0)

def test_frames_split_across_reads_survive_the_reassembler():
    """The bridge can write a frame in pieces (big bar replies over a busy socket); the reader must
    reassemble across reads instead of parsing each chunk as a frame."""
    import threading as _threading
    import time as _time
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    class SplitServer(_threading.Thread):
        def __init__(self) -> None:
            super().__init__(daemon=True)
            self._sock = socket.socket()
            self._sock.bind(("127.0.0.1", 0))
            self._sock.listen(1)
            self.port = self._sock.getsockname()[1]

        def run(self) -> None:
            conn, _ = self._sock.accept()
            try:
                hello = json.dumps({"Type": "hello", "Addon": "modflow-nt-bridge",
                                    "Version": "0.0", "NT": "8.1.8.2"}).encode("utf-8")
                trade = json.dumps({"Type": "trade", "Instrument": "NQ 12-26", "Price": 20005.0,
                                    "Size": 3, "Aggressor": "buy", "Ts": 1758100000000}).encode("utf-8")
                for frame in (hello, trade):                     # every frame split in half
                    k = max(1, len(frame) // 2)
                    conn.sendall(frame[:k])
                    _time.sleep(0.15)
                    conn.sendall(frame[k:] + b"\x00")
                _time.sleep(0.6)
            finally:
                conn.close()

    server = SplitServer()
    server.start()

    ticks: list[tuple] = []

    async def on_tick(symbol, tick):
        ticks.append((symbol, tick.price, tick.size))

    async def on_book(symbol, snapshot):
        pass

    async def main() -> None:
        feed = NinjaTraderFeed(
            symbols={"NQ": "NQ"}, on_tick=on_tick, on_orderbook=on_book,
            host="127.0.0.1", port=server.port)
        task = asyncio.ensure_future(feed.start())
        await asyncio.sleep(1.6)
        await feed.stop()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(main())
    assert ticks == [("NQ", 20005.0, 3.0)], f"split frames mangled: {ticks}"
def test_a_quote_replaces_the_top_of_book_instead_of_piling_up():
    """The old shape kept every price ever quoted, so a falling market's prints were compared
    against a stale top — and the dict grew for the life of the process."""
    from orderflow_system.data.ninjatrader_feed import NinjaTraderFeed

    feed = NinjaTraderFeed({"NQ": "NQ"}, on_tick=lambda *a: None)
    feed._book = {"NQ": {"bid": {}, "ask": {}}}

    feed._update_top({"Instrument": "NQ", "Bid": 21_000.0, "BidSize": 5,
                      "Ask": 21_001.0, "AskSize": 3})
    assert feed._top_of("NQ") == (21_000.0, 21_001.0)

    feed._update_top({"Instrument": "NQ", "Bid": 20_990.0, "BidSize": 4,
                      "Ask": 20_991.0, "AskSize": 2})
    assert feed._top_of("NQ") == (20_990.0, 20_991.0), "the newest quote IS the top of book"
    assert feed._book["NQ"]["bid"] == {20_990.0: 4.0}, "one level, not a price history"
