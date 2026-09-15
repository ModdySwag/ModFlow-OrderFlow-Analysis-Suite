"""
DTC protocol client — talks to a **the DTC platform DTC server** (or any DTC server).

the DTC platform can act as a DTC server, and DTC is an open, public-domain protocol (the DTC platform
states the specification "has no license and is in the public domain" and the documentation
"has no copyrights"). That makes it the legitimate way for this build to read data from a
the DTC platform the user already runs, instead of scraping or faking anything.

Implemented from the published message definitions shipped with the local install
(`C:\\the DTC platformChart\\DTC\\DTCProtocol.proto` / `.h`), which is why the message numbers and
field names below are exact:

    ENCODING_REQUEST=6  ENCODING_RESPONSE=7          (binary, 4-byte header: uint16 size, uint16 type)
    LOGON_REQUEST=1     LOGON_RESPONSE=2   HEARTBEAT=3   LOGOFF=5
    MARKET_DATA_REQUEST=101   MARKET_DATA_REJECT=103
    MARKET_DATA_SNAPSHOT=104  MARKET_DATA_UPDATE_TRADE=107  MARKET_DATA_UPDATE_BID_ASK=108
    SECURITY_DEFINITION_FOR_SYMBOL_REQUEST=506  SECURITY_DEFINITION_RESPONSE=507

Wire format (per the DTC docs): the client opens with an ENCODING_REQUEST in **fixed-length
binary** to negotiate the encoding; after that, JSON-encoded messages are JSON objects
separated by a NUL (0x00) terminator, field names exactly as in the spec, and each object
carries its message type in the ``Type`` field.

Scope: connect, negotiate, log on, subscribe to one symbol, collect evidence, log off. It is
a *probe/reader*, not a trading client — no order messages are implemented on purpose.
"""

from __future__ import annotations

import json
import socket
import ssl
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# ── protocol constants (from the shipped DTC spec) ───────────────────────────────
DTC_VERSION = 8
PROTOCOL_TYPE = b"DTC"
ENCODING_BINARY = 0
ENCODING_VLS = 1
ENCODING_JSON = 2
ENCODING_JSON_COMPACT = 3
ENCODING_NAMES = {ENCODING_BINARY: "Binary", ENCODING_VLS: "Binary (variable-length strings)",
                  ENCODING_JSON: "JSON", ENCODING_JSON_COMPACT: "JSON Compact"}

T_ENCODING_REQUEST = 6
T_ENCODING_RESPONSE = 7
T_LOGON_REQUEST = 1
T_LOGON_RESPONSE = 2
T_HEARTBEAT = 3
T_LOGOFF = 5
T_MARKET_DATA_REQUEST = 101
T_MARKET_DATA_REJECT = 103
T_MARKET_DATA_SNAPSHOT = 104
T_MARKET_DATA_UPDATE_TRADE = 107
T_MARKET_DATA_UPDATE_BID_ASK = 108
T_SECURITY_DEFINITION_FOR_SYMBOL_REQUEST = 506
T_SECURITY_DEFINITION_RESPONSE = 507

MSG_NAMES = {
    T_ENCODING_REQUEST: "ENCODING_REQUEST", T_ENCODING_RESPONSE: "ENCODING_RESPONSE",
    T_LOGON_REQUEST: "LOGON_REQUEST", T_LOGON_RESPONSE: "LOGON_RESPONSE",
    T_HEARTBEAT: "HEARTBEAT", T_LOGOFF: "LOGOFF",
    T_MARKET_DATA_REQUEST: "MARKET_DATA_REQUEST", T_MARKET_DATA_REJECT: "MARKET_DATA_REJECT",
    T_MARKET_DATA_SNAPSHOT: "MARKET_DATA_SNAPSHOT",
    T_MARKET_DATA_UPDATE_TRADE: "MARKET_DATA_UPDATE_TRADE",
    T_MARKET_DATA_UPDATE_BID_ASK: "MARKET_DATA_UPDATE_BID_ASK",
    T_SECURITY_DEFINITION_FOR_SYMBOL_REQUEST: "SECURITY_DEFINITION_FOR_SYMBOL_REQUEST",
    T_SECURITY_DEFINITION_RESPONSE: "SECURITY_DEFINITION_RESPONSE",
}

LOGON_SUCCESS = 1
LOGON_ERROR = 2
REQUEST_ACTION_SUBSCRIBE = 1
REQUEST_ACTION_UNSUBSCRIBE = 2
AT_BID = 1
AT_ASK = 2

CLIENT_NAME = "ModFlow OrderFlow Analysis Suite (DTC reader)"


class DtcError(RuntimeError):
    """A DTC failure, tagged with the stage it happened in and the server's own words."""

    def __init__(self, stage: str, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.stage = stage
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "error": str(self), "detail": self.detail}


@dataclass
class DtcLogon:
    """What the server said when it accepted (or refused) the logon."""
    ok: bool = False
    status: int = 0
    result_text: str = ""
    server_name: str = ""
    protocol_version: int = 0
    market_data: bool = False
    depth: bool = False
    security_definitions: bool = False
    historical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "result_text": self.result_text,
                "server_name": self.server_name, "protocol_version": self.protocol_version,
                "market_data": self.market_data, "depth": self.depth,
                "security_definitions": self.security_definitions,
                "historical": self.historical}


@dataclass
class DtcSession:
    """A live connection's collected evidence (kept separate from the socket)."""
    server: DtcLogon = field(default_factory=DtcLogon)
    encoding: int = ENCODING_JSON
    snapshots: int = 0
    trades: int = 0
    bid_ask: int = 0
    heartbeats: int = 0
    rejects: list[str] = field(default_factory=list)
    symbol_id: int = 0
    symbol: str = ""
    last: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"server": self.server.to_dict(), "encoding": self.encoding,
                "encoding_name": ENCODING_NAMES.get(self.encoding, str(self.encoding)),
                "snapshots": self.snapshots, "trades": self.trades, "bid_ask": self.bid_ask,
                "heartbeats": self.heartbeats, "rejects": self.rejects,
                "symbol": self.symbol, "symbol_id": self.symbol_id, "last": self.last}


def encode_encoding_request(encoding: int = ENCODING_JSON) -> bytes:
    """The fixed-length binary ENCODING_REQUEST: 4-byte header + int32 version + int32
    encoding + 4-byte protocol type = 16 bytes, exactly as ``s_EncodingRequest``."""
    return struct.pack("<HHii4s", 16, T_ENCODING_REQUEST, DTC_VERSION, int(encoding), PROTOCOL_TYPE)


def decode_binary_header(raw: bytes) -> tuple[int, int]:
    """(size, type) from a fixed-length binary DTC message header."""
    if len(raw) < 4:
        raise DtcError("decode", "binary header needs 4 bytes", detail=repr(raw))
    size, mtype = struct.unpack("<HH", raw[:4])
    return int(size), int(mtype)


class DtcClient:
    """A minimal DTC reader: negotiate, log on, subscribe, collect, log off."""

    def __init__(self, host: str, port: int, username: str = "", password: str = "",
                 use_tls: bool = False, timeout: float = 6.0,
                 encoding: int = ENCODING_JSON) -> None:
        self.host = str(host or "").strip()
        self.port = int(port or 0)
        self.username = str(username or "")
        self.password = str(password or "")
        self.use_tls = bool(use_tls)
        self.timeout = max(0.5, float(timeout))
        self.encoding = int(encoding)
        self._sock: Optional[socket.socket] = None
        self._buf = b""
        self.session = DtcSession()

    # ── connection ───────────────────────────────────────────────────
    def connect(self) -> None:
        if not self.host or not self.port:
            raise DtcError("config", "host and port are required")
        try:
            raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except (OSError, socket.timeout) as exc:
            raise DtcError("connect", f"cannot reach {self.host}:{self.port} — {exc}",
                           detail="Is the DTC server enabled and listening?") from exc
        if self.use_tls:
            try:
                ctx = ssl.create_default_context()
                raw = ctx.wrap_socket(raw, server_hostname=self.host)
            except (ssl.SSLError, OSError) as exc:
                raw.close()
                raise DtcError("tls", f"TLS handshake failed — {exc}") from exc
        raw.settimeout(self.timeout)
        self._sock = raw

    def close(self) -> None:
        try:
            if self._sock is not None:
                self._sock.close()
        except OSError:
            pass
        self._sock = None

    # ── wire helpers ─────────────────────────────────────────────────
    def _send(self, payload: bytes) -> None:
        if self._sock is None:
            raise DtcError("send", "not connected")
        try:
            self._sock.sendall(payload)
        except (OSError, socket.timeout) as exc:
            raise DtcError("send", f"send failed — {exc}") from exc

    def send_json(self, message: dict[str, Any]) -> None:
        """JSON messages are NUL-terminated objects, 8-bit, field names as in the spec."""
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        self._send(body + b"\x00")

    def _recv_into_buffer(self, timeout: Optional[float] = None) -> bool:
        """One socket read. False on timeout, which callers treat as 'nothing arrived'."""
        if self._sock is None:
            raise DtcError("recv", "not connected")
        self._sock.settimeout(self.timeout if timeout is None else max(0.05, float(timeout)))
        try:
            chunk = self._sock.recv(65536)
        except socket.timeout:
            return False
        except OSError as exc:
            raise DtcError("recv", f"receive failed — {exc}") from exc
        if not chunk:
            raise DtcError("recv", "server closed the connection")
        self._buf += chunk
        return True

    def read_binary_message(self) -> tuple[int, bytes]:
        """Read one fixed-length binary message; returns (type, body-after-header)."""
        deadline = time.time() + self.timeout
        while True:
            if len(self._buf) >= 4:
                size, mtype = decode_binary_header(self._buf)
                if size < 4:
                    raise DtcError("decode", f"bogus message size {size}")
                if len(self._buf) >= size:
                    body = self._buf[4:size]
                    self._buf = self._buf[size:]
                    return mtype, body
            if time.time() > deadline or not self._recv_into_buffer(deadline - time.time()):
                raise DtcError("recv", "timed out waiting for a binary frame")

    def read_json_message(self, timeout: Optional[float] = None) -> Optional[dict[str, Any]]:
        """Read one NUL-terminated JSON object. None when the wait expired."""
        deadline = time.time() + (self.timeout if timeout is None else float(timeout))
        while True:
            end = self._buf.find(b"\x00")
            if end >= 0:
                chunk, self._buf = self._buf[:end], self._buf[end + 1:]
                text = chunk.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    parsed = json.loads(text)
                except ValueError:
                    self.session.rejects.append(f"unparsable JSON frame: {text[:80]}")
                    continue
                return parsed if isinstance(parsed, dict) else {"Type": 0, "raw": parsed}
            remaining = deadline - time.time()
            if remaining <= 0 or not self._recv_into_buffer(remaining):
                return None

    # ── protocol steps ───────────────────────────────────────────────
    def negotiate_encoding(self, encoding: Optional[int] = None) -> int:
        """Open the connection the documented way: binary ENCODING_REQUEST first."""
        want = self.encoding if encoding is None else int(encoding)
        self._send(encode_encoding_request(want))
        mtype, body = self.read_binary_message()
        if mtype != T_ENCODING_RESPONSE:
            raise DtcError("encoding", f"expected ENCODING_RESPONSE (7), got {mtype}",
                           detail=MSG_NAMES.get(mtype, ""))
        # s_EncodingResponse: header(4) + int32 ProtocolVersion + int32 Encoding + char[4] ProtocolType
        if len(body) < 12:
            raise DtcError("encoding", "short ENCODING_RESPONSE", detail=repr(body))
        version, agreed, ptype = struct.unpack("<ii4s", body[:12])
        self.session.encoding = int(agreed)
        if int(agreed) not in (ENCODING_JSON, ENCODING_JSON_COMPACT):
            raise DtcError(
                "encoding",
                f"server negotiated {ENCODING_NAMES.get(int(agreed), agreed)}; this client speaks JSON",
                detail="Set the DTC server's encoding to JSON in the DTC platform, then test again.",
            )
        self.session.server.protocol_version = int(version)
        self.session.server.server_name = ptype.decode("ascii", errors="replace").strip("\x00 ")
        return int(agreed)

    def logon(self, heartbeat_seconds: int = 10) -> DtcLogon:
        """LOGON_REQUEST → LOGON_RESPONSE. Raises DtcError when the server refuses."""
        self.send_json({
            "Type": T_LOGON_REQUEST,
            "ProtocolVersion": DTC_VERSION,
            "Username": self.username,
            "Password": self.password,
            "HeartbeatIntervalInSeconds": int(heartbeat_seconds),
            "ClientName": CLIENT_NAME,
        })
        message = self._await_type(T_LOGON_RESPONSE)
        info = DtcLogon(
            status=int(message.get("Result") or 0),
            result_text=str(message.get("ResultText") or ""),
            server_name=str(message.get("ServerName") or self.session.server.server_name),
            protocol_version=int(message.get("ProtocolVersion") or DTC_VERSION),
            market_data=bool(message.get("MarketDataSupported", 1)),
            depth=bool(message.get("MarketDepthIsSupported", 0)),
            security_definitions=bool(message.get("SecurityDefinitionsSupported", 0)),
            historical=bool(message.get("HistoricalPriceDataSupported", 0)),
        )
        if info.status != LOGON_SUCCESS:
            raise DtcError(
                "logon",
                f"logon refused: {info.result_text or MSG_NAMES.get(T_LOGON_RESPONSE, 'LOGON_RESPONSE')}",
                detail=f"status {info.status}",
            )
        info.ok = True
        self.session.server = info
        return info

    def _await_type(self, wanted: int, timeout: Optional[float] = None) -> dict[str, Any]:
        """Read JSON frames until ``wanted`` arrives, answering heartbeats as we go."""
        deadline = time.time() + (self.timeout if timeout is None else float(timeout))
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise DtcError("recv", f"timed out waiting for {MSG_NAMES.get(wanted, wanted)}")
            message = self.read_json_message(remaining)
            if message is None:
                continue
            self._note(message)
            if int(message.get("Type") or 0) == wanted:
                return message

    def _note(self, message: dict[str, Any]) -> None:
        """Keep score of what the server sent, and answer heartbeats."""
        mtype = int(message.get("Type") or 0)
        if mtype == T_HEARTBEAT:
            self.session.heartbeats += 1
            self.send_json({"Type": T_HEARTBEAT})
        elif mtype == T_MARKET_DATA_SNAPSHOT:
            self.session.snapshots += 1
            self.session.last = {"kind": "snapshot",
                                 "bid": message.get("BidPrice"), "ask": message.get("AskPrice"),
                                 "last": message.get("LastTradePrice"),
                                 "volume": message.get("SessionVolume"),
                                 "ts": message.get("BidAskDateTime")}
        elif mtype == T_MARKET_DATA_UPDATE_TRADE:
            self.session.trades += 1
            self.session.last = {"kind": "trade", "price": message.get("Price"),
                                 "size": message.get("Volume"), "side": message.get("AtBidOrAsk"),
                                 "ts": message.get("DateTime")}
        elif mtype == T_MARKET_DATA_UPDATE_BID_ASK:
            self.session.bid_ask += 1
            self.session.last = {"kind": "quote", "bid": message.get("BidPrice"),
                                 "ask": message.get("AskPrice"), "ts": message.get("DateTime")}
        elif mtype == T_MARKET_DATA_REJECT:
            self.session.rejects.append(str(message.get("RejectText") or "market data rejected"))
        elif mtype == T_SECURITY_DEFINITION_RESPONSE:
            if not self.session.symbol_id and message.get("SymbolID"):
                self.session.symbol_id = int(message["SymbolID"])

    def subscribe(self, symbol: str, exchange: str = "", symbol_id: int = 0) -> None:
        """MARKET_DATA_REQUEST for one symbol (the server assigns the SymbolID)."""
        self.send_json({
            "Type": T_MARKET_DATA_REQUEST,
            "RequestAction": REQUEST_ACTION_SUBSCRIBE,
            "SymbolID": int(symbol_id or 0),
            "Symbol": str(symbol or ""),
            "Exchange": str(exchange or ""),
        })
        self.session.symbol = str(symbol or "")

    def unsubscribe(self, symbol: str, symbol_id: int = 0) -> None:
        self.send_json({
            "Type": T_MARKET_DATA_REQUEST,
            "RequestAction": REQUEST_ACTION_UNSUBSCRIBE,
            "SymbolID": int(symbol_id or 0),
            "Symbol": str(symbol or ""),
        })

    def collect(self, seconds: float = 3.0) -> DtcSession:
        """Read whatever arrives for ``seconds`` (snapshots, trades, quotes, heartbeats)."""
        deadline = time.time() + max(0.2, float(seconds))
        while time.time() < deadline:
            message = self.read_json_message(min(0.5, max(0.05, deadline - time.time())))
            if message is None:
                continue
            self._note(message)
        return self.session

    def logoff(self) -> None:
        try:
            self.send_json({"Type": T_LOGOFF})
        except DtcError:
            pass


def dtc_probe(host: str, port: int, username: str = "", password: str = "",
              use_tls: bool = False, symbol: str = "", seconds: float = 3.0,
              timeout: float = 6.0) -> dict[str, Any]:
    """One-shot connection test for the settings UI.

    Returns a JSON-safe report: it contains the server's own name/version/capability flags,
    how many messages arrived, and a sample of the last one. It never contains the password,
    and DTC errors are reported by stage so "no server" is distinguishable from "wrong
    password" without reading a log.
    """
    started = time.time()
    client = DtcClient(host, port, username=username, password=password,
                       use_tls=use_tls, timeout=timeout)
    stage = "connect"
    try:
        client.connect()
        stage = "encoding"
        encoding = client.negotiate_encoding()
        stage = "logon"
        logon = client.logon()
        if symbol:
            stage = "subscribe"
            client.subscribe(symbol)
            client.collect(seconds=seconds)
        else:
            client.collect(seconds=min(2.0, max(0.5, seconds)))
        session = client.session
        result = {
            "ok": True,
            "stage": "done",
            "elapsed_ms": int((time.time() - started) * 1000),
            "host": host, "port": int(port), "tls": bool(use_tls),
            "encoding": encoding, "logon": logon.to_dict(),
            "messages": {"snapshots": session.snapshots, "trades": session.trades,
                         "bid_ask": session.bid_ask, "heartbeats": session.heartbeats},
            "sample": session.last,
            "rejects": session.rejects[:5],
            "note": ("Server answered. Market data arrives only when the symbol is streaming "
                     "in the DTC platform for the same DTC service."),
        }
        client.logoff()
        return result
    except DtcError as exc:
        return {"ok": False, "stage": exc.stage, "elapsed_ms": int((time.time() - started) * 1000),
                "host": host, "port": int(port), "tls": bool(use_tls),
                **exc.as_dict()}
    except Exception as exc:                                  # noqa: BLE001 — report, never raise
        return {"ok": False, "stage": stage, "elapsed_ms": int((time.time() - started) * 1000),
                "host": host, "port": int(port), "tls": bool(use_tls),
                "error": f"{type(exc).__name__}: {exc}", "detail": ""}
    finally:
        client.close()
