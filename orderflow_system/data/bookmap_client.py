"""Bookmap add-on bridge — the suite's side of the one honest way data leaves Bookmap.

Bookmap has no public market-data-out API: it speaks to *its* data adapters and to add-ons that run
INSIDE it. So the bridge is deliberately arranged the other way round from the DTC one — here the
**add-on is the server**: a small add-on (Java, built against the `bm-l1api`/`bm-simplified-api-wrapper`
jars that ship inside Bookmap itself) subscribes to Bookmap's own simplified-API callbacks and writes
them out on a loopback TCP port; this module connects to that port and reads them.

That is not a limitation this module hides — it is stated in the UI and in `bookmap_addon/README.md`:
the suite side here is complete and tested against a mock add-on; the jar on the Bookmap side must be
built (a JDK) and added once, by hand, in *Settings → Configure API plugins → Add*.

Wire format (the add-on template in `bookmap_addon/` writes exactly this):

    <json>\\x00<json>\\x00…        NUL-terminated JSON, one message per frame, UTF-8

    {"Type": "hello",    "Addon": "ofap-bookmap-bridge", "Version": "0.1",
     "Bookmap": "7.8.0 build:13", "Symbol": "BTCUSDT", "Licence": "Digital"}
    {"Type": "snapshot", "Symbol": "BTCUSDT", "Bid": 61234.5, "Ask": 61235.0,
     "Last": 61234.5, "Volume": 1234, "Ts": 1789425000123}
    {"Type": "trade",    "Symbol": "BTCUSDT", "Price": 61234.5, "Size": 0.25,
     "Aggressor": "buy"|"sell", "Ts": 1789425000123}
    {"Type": "depth",    "Symbol": "BTCUSDT", "Side": "bid"|"ask", "Price": 61234.5,
     "Size": 3.5, "Ts": 1789425000123}
    {"Type": "heartbeat","Ts": 1789425000123}

`Type` values are matched case-insensitively; unknown types are counted as rejects rather than raising
— an add-on that grows a new message must not take the suite down.
"""

from __future__ import annotations

import json
import socket
import time
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8791                       # the template's default; the suite only ever connects
PROTOCOL = "bookmap-addon-jsonl"
ADDON_NAME = "ofap-bookmap-bridge"
#: The frame terminator. JSON messages are text; a NUL between them survives any chunking.
FRAME = b"\x00"
MAX_FRAME = 1 << 20                       # 1 MiB per message: a sane ceiling, never a buffer blow-up
#: Frame type → the counter it lands in. Two spellings reach the same bucket on purpose: an add-on
#: may send `snapshot` or `quote` for the same idea, and the suite counts them as one thing.
COUNTERS = {"hello": "hello", "snapshot": "snapshots", "quote": "snapshots",
            "trade": "trades", "trades": "trades", "depth": "depth",
            "heartbeat": "heartbeats", "bye": "bye"}


def _clean(value: Any) -> Any:
    """JSON-safe scalars only — a message field is data from another process, never trusted."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:120]


def parse_frame(text: str) -> dict[str, Any] | None:
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
    row = {"kind": kind, "symbol": str(_clean(message.get("Symbol")) or "")[:24],
           "ts": _clean(message.get("Ts"))}
    if kind == "trade":
        row["price"] = _clean(message.get("Price"))
        row["size"] = _clean(message.get("Size"))
        row["aggressor"] = _clean(message.get("Aggressor"))
    elif kind in ("snapshot", "quote"):
        row["bid"] = _clean(message.get("Bid"))
        row["ask"] = _clean(message.get("Ask"))
        row["last"] = _clean(message.get("Last"))
    elif kind == "depth":
        row["side"] = _clean(message.get("Side"))
        row["price"] = _clean(message.get("Price"))
        row["size"] = _clean(message.get("Size"))
    return row


def bookmap_probe(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *, seconds: float = 2.0,
                  timeout: float = 3.0, symbol: str = "") -> dict[str, Any]:
    """Connect to the add-on's port, read its stream for `seconds`, and report what arrived.

    Never raises: every failure comes back as `{"ok": False, "stage": …, "error": …, "detail": …}` so
    the settings view can print it verbatim. Stages, in the order they can fail: `config`, `connect`,
    `hello`, `done`.
    """
    host = str(host or "").strip() or DEFAULT_HOST
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 0
    if not (1 <= port <= 65535):
        return {"ok": False, "stage": "config", "host": host, "port": port,
                "error": "no port to connect to",
                "detail": f"port {port!r} is not a TCP port; the add-on prints the port it bound in "
                          f"Bookmap's log (default {DEFAULT_PORT})."}

    want = str(symbol or "").strip().upper()
    out: dict[str, Any] = {"ok": False, "stage": "connect", "host": host, "port": port,
                           "protocol": PROTOCOL,
                           "messages": {"hello": 0, "snapshots": 0, "trades": 0, "depth": 0,
                                        "heartbeats": 0, "bye": 0, "other": 0},
                           "rejects": [], "sample": {}, "addon": {}, "started": time.time()}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.2, float(timeout)))
    try:
        sock.connect((host, port))
    except OSError as exc:
        sock.close()
        out.update({"stage": "connect", "error": f"could not connect to {host}:{port}",
                    "detail": f"{type(exc).__name__}: {exc}. The add-on is a server: if nothing "
                              f"answers, it is not loaded — Settings → Configure API plugins → Add, "
                              f"then let it bind (its log line names the port)."})
        return out

    deadline = time.time() + max(0.2, float(seconds))
    buf = b""
    try:
        sock.settimeout(max(0.2, min(float(timeout), 0.5)))
        while time.time() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError as exc:
                out.update({"stage": "read", "error": "the add-on closed the connection",
                            "detail": f"{type(exc).__name__}: {exc}"})
                break
            if not chunk:
                out.update({"stage": "read", "error": "the add-on closed the connection",
                            "detail": "the stream ended; the add-on may have been unloaded in Bookmap."})
                break
            buf += chunk
            if len(buf) > MAX_FRAME:
                # A frame this long is not one of ours; keep the tail and say so.
                out["rejects"].append(f"dropped {len(buf)} bytes without a frame separator")
                buf = buf[-4096:]
            while FRAME in buf:
                raw, buf = buf.split(FRAME, 1)
                text = raw.decode("utf-8", errors="replace")
                message = parse_frame(text)
                if message is None:
                    if text.strip():
                        out["rejects"].append(f"unparsable frame: {text[:60]!r}")
                    continue
                kind = message.get("Type") or ""
                counter = COUNTERS.get(kind)
                if counter:
                    out["messages"][counter] += 1
                else:
                    out["messages"]["other"] += 1
                if kind == "hello":
                    out["addon"] = {k: _clean(message.get(k)) for k in
                                    ("Addon", "Version", "Bookmap", "Symbol", "Licence", "Replay")}
                    out["stage"] = "hello"
                elif not out["sample"] and kind in ("trade", "snapshot", "quote", "depth"):
                    out["sample"] = _sample_of(message)
                row_symbol = str(_clean(message.get("Symbol")) or "").upper()
                if want and row_symbol and row_symbol != want:
                    out["rejects"].append(f"symbol {row_symbol!r} is not the requested {want!r}")
    finally:
        try:
            sock.close()
        except OSError:
            pass

    messages = out["messages"]
    if out["stage"] == "hello" or messages["hello"]:
        out["ok"] = True
        out["stage"] = "done"
        out["note"] = (f"add-on {out['addon'].get('Addon') or ADDON_NAME} "
                       f"{out['addon'].get('Version') or ''}".strip()
                       + f" on Bookmap {out['addon'].get('Bookmap') or '?'}")
        if out["addon"].get("Licence"):
            out["note"] += f" · licence {out['addon']['Licence']}"
    else:
        out["stage"] = "hello"
        out["error"] = "connected, but no add-on hello arrived"
        out["detail"] = ("something is listening on that port, but it is not our bridge: the first "
                         "frame must be a hello from " + ADDON_NAME + ".")
    out["seconds"] = round(time.time() - out["started"], 2)
    return out
