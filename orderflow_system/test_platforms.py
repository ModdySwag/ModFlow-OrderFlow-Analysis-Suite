"""External data bridge: the DTC client and its connection block.

The DTC tests run against a **mock DTC server** written to the published message/field
definitions, so the client's handshake, message handling and error reporting are proven
without the DTC platform running. The live path is the same code with a real server on the
other end (the settings view's "Test connection" button).
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Optional

import pytest

from orderflow_system.data.dtc_client import (ENCODING_JSON, T_ENCODING_RESPONSE, T_HEARTBEAT,
                                              T_LOGON_RESPONSE, T_MARKET_DATA_SNAPSHOT,
                                              T_MARKET_DATA_UPDATE_TRADE, decode_binary_header,
                                              dtc_probe, encode_encoding_request)
from orderflow_system.desktop import platforms

# ── catalogue ──────────────────────────────────────────────────────────────────────








def test_dtc_defaults_are_empty_credentials():
    block = platforms.dtc_defaults()
    assert block["username"] == "" and block["password"] == ""
    assert block["enabled"] is False and block["host"] == "127.0.0.1" and 1 <= block["port"] <= 65535



def test_encoding_request_layout_matches_the_spec():
    raw = encode_encoding_request()
    assert len(raw) == 16
    size, mtype = decode_binary_header(raw)
    assert (size, mtype) == (16, 6)                       # ENCODING_REQUEST = 6
    version, encoding, protocol = struct.unpack("<ii4s", raw[4:16])
    assert version == 8 and encoding == ENCODING_JSON
    assert protocol == b"DTC\x00"                          # char[4], NUL-padded


# ── mock DTC server ────────────────────────────────────────────────────────────────
class MockDtcServer(threading.Thread):
    """Minimal DTC server: binary ENCODING_REQUEST → JSON from then on (NUL-terminated)."""

    def __init__(self, *, encoding: int = ENCODING_JSON, logon_status: int = 1,
                 result_text: str = "Success", server_name: str = "MockDTC",
                 trades: int = 3, garbage: bytes = b"") -> None:
        super().__init__(daemon=True)
        self.encoding = encoding
        self.logon_status = logon_status
        self.result_text = result_text
        self.server_name = server_name
        self.trades = trades
        self.garbage = garbage
        self.received: list[dict[str, Any]] = []
        self.binary_request: bytes = b""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]

    def _frame(self, message: dict[str, Any]) -> None:      # noqa: D401 — NUL-terminated JSON
        self._conn.sendall(json.dumps(message).encode("utf-8") + b"\x00")

    def run(self) -> None:
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        self._conn = conn
        conn.settimeout(5.0)
        try:
            self.binary_request = conn.recv(16)
            size, mtype = struct.unpack("<HH", self.binary_request[:4])
            want = struct.unpack("<i", self.binary_request[8:12])[0]
            agreed = self.encoding if self.encoding != ENCODING_JSON else want
            conn.sendall(struct.pack("<HHii4s", 16, T_ENCODING_RESPONSE, 8, agreed, b"DTC"))
            if self.garbage:
                conn.sendall(self.garbage)
            buf = b""
            while True:
                end = buf.find(b"\x00")
                if end < 0:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                    continue
                text, buf = buf[:end], buf[end + 1:]
                if not text.strip():
                    continue
                message = json.loads(text)
                self.received.append(message)
                mtype = int(message.get("Type") or 0)
                if mtype == 1:                            # LOGON_REQUEST
                    self._frame({"Type": T_LOGON_RESPONSE, "ProtocolVersion": 8,
                                 "Result": self.logon_status, "ResultText": self.result_text,
                                 "ServerName": self.server_name,
                                 "MarketDataSupported": 1, "MarketDepthIsSupported": 1,
                                 "SecurityDefinitionsSupported": 1, "HistoricalPriceDataSupported": 0})
                elif mtype == 101:                        # MARKET_DATA_REQUEST
                    self._frame({"Type": T_MARKET_DATA_SNAPSHOT, "SymbolID": 7, "BidPrice": 5000.25,
                                 "AskPrice": 5000.5, "LastTradePrice": 5000.5, "SessionVolume": 1234})
                    for i in range(self.trades):
                        self._frame({"Type": T_MARKET_DATA_UPDATE_TRADE, "SymbolID": 7,
                                     "AtBidOrAsk": 1 if i % 2 else 2,
                                     "Price": 5000.25 + i * 0.25, "Volume": 1 + i,
                                     "DateTime": 1789425000.0 + i})
                    self._frame({"Type": T_HEARTBEAT})
                elif mtype == 5:                          # LOGOFF
                    return
        except (OSError, ValueError):
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass


@pytest.fixture()
def mock_server():
    server = MockDtcServer()
    server.start()
    yield server
    server.join(timeout=1.0)


def test_probe_handshake_against_a_spec_conformant_server(mock_server):
    result = dtc_probe("127.0.0.1", mock_server.port, username="dtcuser", password="dtc-secret-value",
                       symbol="ESZ6", seconds=2.0, timeout=3.0)
    assert result["ok"] is True and result["stage"] == "done"
    assert result["logon"]["server_name"] == "MockDTC"
    assert result["logon"]["market_data"] is True and result["logon"]["depth"] is True
    assert result["encoding"] == ENCODING_JSON
    assert result["messages"]["snapshots"] == 1 and result["messages"]["trades"] == 3
    assert result["sample"]["kind"] in ("trade", "quote", "snapshot")
    # the client really did send the credentials, and the response never echoes them
    logon = next(m for m in mock_server.received if m.get("Type") == 1)
    assert logon["Username"] == "dtcuser" and logon["Password"] == "dtc-secret-value"
    assert logon["ProtocolVersion"] == 8
    assert "dtc-secret-value" not in json.dumps(result)
    subscribe = next(m for m in mock_server.received if m.get("Type") == 101)
    assert subscribe["Symbol"] == "ESZ6" and subscribe["RequestAction"] == 1
    # The client sends its LOGOFF and then closes; the mock server records it on its own thread, so
    # wait for that read loop before asserting. Racing it cost roughly one full-suite run in four,
    # which reads as an intermittent client bug rather than a test-side race.
    deadline = time.time() + 1.5
    while time.time() < deadline and not any(m.get("Type") == 5 for m in mock_server.received):
        time.sleep(0.05)
    assert any(m.get("Type") == 5 for m in mock_server.received)      # logged off politely


def test_refused_logon_reports_the_servers_own_words():
    server = MockDtcServer(logon_status=2, result_text="Invalid username or password")
    server.start()
    try:
        result = dtc_probe("127.0.0.1", server.port, username="u", password="p", timeout=3.0)
        assert result["ok"] is False and result["stage"] == "logon"
        assert "Invalid username or password" in result["error"]
        assert "password" not in result["error"].lower().replace("invalid username or password", "")
    finally:
        server.join(timeout=1.0)


def test_server_that_insists_on_binary_says_so():
    server = MockDtcServer(encoding=0)                    # BINARY_ENCODING
    server.start()
    try:
        result = dtc_probe("127.0.0.1", server.port, timeout=3.0)
        assert result["ok"] is False and result["stage"] == "encoding"
        assert "Binary" in result["error"] and "JSON" in result["detail"]
    finally:
        server.join(timeout=1.0)


def test_garbage_from_the_server_is_reported_not_raised():
    server = MockDtcServer(garbage=b"\x01\x02not json at all\x00")
    server.start()
    try:
        result = dtc_probe("127.0.0.1", server.port, timeout=2.0, seconds=0.5)
        assert result["ok"] is True                          # the handshake still completed
        assert any("unparsable" in r for r in result["rejects"])
    finally:
        server.join(timeout=1.0)


def test_no_server_at_the_address_is_a_connect_error_with_a_hint():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()                                          # nothing is listening now
    result = dtc_probe("127.0.0.1", port, timeout=2.0)
    assert result["ok"] is False and result["stage"] == "connect"
    assert "DTC server" in result["detail"]


def test_missing_host_or_port_is_a_config_error():
    assert dtc_probe("", 0)["stage"] == "config"


# ══════════════════════════════════════════════════════════════════════════════════════════
# Bookmap: the catalogue half and the bridge half
# ══════════════════════════════════════════════════════════════════════════════════════════


def test_the_catalogue_carries_both_platforms_sierra_first():
    """The Platforms view indexes platforms[0] for its Sierra keys — Bookmap must arrive beside it,
    never instead of it."""
    cat = platforms.catalogue()
    rows = cat["platforms"]
    assert [row["id"] for row in rows] == ["sierra", "bookmap"]
    assert rows[0]["plans"] == platforms.PLANS and rows[0]["links"] == platforms.LINKS
    for row in rows:
        assert row["name"] and row["why"] and row["free_tier"] is True
        assert row["plans"] and row["prices_as_of"], f"{row['id']} must publish prices and their date"
        assert row["plans"][0]["id"] in ("free", "digital"), "the free path comes first"
        assert row["plans"][0]["price"] == "0" and row["plans"][0].get("highlight") is True


def test_bookmap_tiers_carry_their_own_limits():
    """The instrument cap and backfill window are the tier's published facts — quoting them beats
    implying 'the full thing'."""
    caps = {plan["id"]: plan for plan in platforms.BOOKMAP_PLANS}
    assert list(caps) == ["digital", "digitalplus", "global", "globalplus"]
    assert [caps[k]["instruments"] for k in caps] == [1, 3, 10, 20]
    assert "1 hour" in caps["digital"]["backfill"] and "7 days" in caps["globalplus"]["backfill"]
    assert caps["digital"]["price"] == "0" and caps["globalplus"]["price"] == "99"
    assert caps["global"]["lifetime"] == "990", "a lifetime licence is a published option"
    free = " ".join(caps["digital"]["includes"]).lower()
    assert "crypto" in free and "one instrument" in free and "account" in free


def test_bookmap_caveats_state_the_limits_where_they_bite():
    text = " ".join(platforms.BOOKMAP_CAVEATS).lower()
    assert "market data is not included" in text
    assert "one instrument at a time" in text
    assert "licence-gated" in text or "locked" in text, "the API-plugins gate must be stated"
    assert "no market-data-out api" in text, "and why an add-on is the only route"
    assert platforms.BOOKMAP_PRICES_AS_OF in " ".join(platforms.BOOKMAP_CAVEATS)


def test_the_link_allow_list_covers_both_vendors_and_one_code_host():
    ok_cases = [
        "https://www.sierrachart.com/index.php?page=doc/Packages.php",
        "https://bookmap.com/packages-comparison/",
        "https://bookmap.com/portal/",
        "https://bookmap.com/knowledgebase/docs/API-Tutorial",
        "https://github.com/BookmapAPI/python-api",
    ]
    for url in ok_cases:
        assert platforms.validate_url(url)[0] is True, url
    refused = [
        "http://bookmap.com/",                              # https only
        "https://evil.example.com/bookmap",
        "https://github.com/someone/else",                  # not the Bookmap org
        "https://raw.githubusercontent.com/BookmapAPI/x",   # not even Bookmap's org by another route
        "https://bookmap.com.evil.example/pricing",         # a lookalike host is not the vendor
        "file:///C:/Windows/System32/drivers/etc/hosts",
    ]
    for url in refused:
        ok, why = platforms.validate_url(url)
        assert ok is False, url
        assert why, "a refusal must say why"


def test_bookmap_workflow_is_free_first_and_ends_at_the_addon_gate():
    free = platforms.bookmap_workflow()
    assert free["plan"] == "digital" and free["plan_kind"] == "free"
    titles = " ".join(step["title"] for step in free["steps"]).lower()
    assert "install" in titles and "account" in titles and "free path" in titles
    assert "add-on" in titles and "locked" in titles, "the licence gate is a step, not a footnote"
    assert any(step["link"] == "setup_api" for step in free["steps"])
    assert all(1 <= step["n"] <= len(free["steps"]) for step in free["steps"])
    assert platforms.bookmap_workflow("nonsense")["plan"] == "digital", "an unknown tier falls back"

    paid = platforms.bookmap_workflow("globalplus")
    assert paid["plan"] == "globalplus" and paid["plan_kind"] == "integrated"
    activate = [step for step in paid["steps"] if "Activate" in step["title"]]
    assert activate and "1990" in activate[0]["text"], "the lifetime price rides on the paid path"
    assert any("separate subscription" in c or "separate" in c for c in paid["suite_changes"]) or \
        any("market data" in c.lower() for c in paid["suite_changes"]) is not None


def test_bookmap_defaults_are_loopback_and_carry_no_credentials():
    block = platforms.bookmap_defaults()
    assert block["host"] == "127.0.0.1" and block["port"] == 8791
    assert block["protocol"] == "bookmap-addon-jsonl"
    assert block["enabled"] is False and block["plan"] == "digital"
    for forbidden in ("password", "username", "token", "api_key", "secret"):
        assert forbidden not in block, "there is nothing to authenticate: the add-on is loopback-only"


# ── a mock of the add-on, written to the format in bookmap_addon/README.md ─────────────────
class MockBookmapAddon(threading.Thread):
    """The add-on side of the wire: hello, then a few frames, then silence."""

    def __init__(self, *, hello: bool = True, frames: int = 3, garbage: bytes = b"",
                 symbol: str = "BTCUSDT", addon: str = "ofap-bookmap-bridge",
                 version: str = "0.1", bookmap: str = "7.8.0 build:13", licence: str = "Digital",
                 other_symbol_every: int = 0, port: int = 0) -> None:
        super().__init__(daemon=True)
        self.hello = hello
        self.frames = frames
        self.garbage = garbage
        self.symbol = symbol
        self.addon = addon
        self.version = version
        self.bookmap = bookmap
        self.licence = licence
        self.other_symbol_every = other_symbol_every
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", port))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self.accepted = 0

    def frame(self, message: dict[str, Any]) -> bytes:
        return json.dumps(message).encode("utf-8") + b"\x00"

    def run(self) -> None:
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        self.accepted += 1
        try:
            if self.hello:
                conn.sendall(self.frame({"Type": "hello", "Addon": self.addon, "Version": self.version,
                                         "Bookmap": self.bookmap, "Symbol": self.symbol,
                                         "Licence": self.licence}))
            if self.garbage:
                conn.sendall(self.garbage)
            for i in range(self.frames):
                sym = self.symbol if not (self.other_symbol_every and i % self.other_symbol_every == 0) \
                    else "DOGEUSDT"
                conn.sendall(self.frame({"Type": "snapshot", "Symbol": sym, "Bid": 61000.5 + i,
                                         "Ask": 61001.0 + i, "Last": 61000.75 + i,
                                         "Volume": 100 + i, "Ts": 1789425000123 + i}))
                conn.sendall(self.frame({"Type": "trade", "Symbol": sym, "Price": 61000.5 + i,
                                         "Size": 1 + i, "Aggressor": "buy" if i % 2 else "sell",
                                         "Ts": 1789425000123 + i}))
                conn.sendall(self.frame({"Type": "depth", "Symbol": sym, "Side": "bid",
                                         "Price": 61000.0 + i, "Size": 5 + i}))
            conn.sendall(self.frame({"Type": "heartbeat", "Ts": 1789425000999}))
            time.sleep(0.4)
        except OSError:
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass


def test_bookmap_probe_reads_the_addon_stream():
    from orderflow_system.data.bookmap_client import bookmap_probe

    server = MockBookmapAddon(frames=3)
    server.start()
    try:
        result = bookmap_probe("127.0.0.1", server.port, seconds=1.5, timeout=2.0)
        assert result["ok"] is True and result["stage"] == "done", result
        assert result["addon"]["Addon"] == "ofap-bookmap-bridge"
        assert result["addon"]["Bookmap"] == "7.8.0 build:13"
        assert result["messages"]["hello"] == 1
        assert result["messages"]["snapshots"] == 3 and result["messages"]["trades"] == 3
        assert result["messages"]["depth"] == 3
        assert result["sample"]["kind"] in ("snapshot", "trade", "depth")
        assert "Digital" in result["note"], "the licence the add-on reported is echoed back"
        assert result["protocol"] == "bookmap-addon-jsonl"
    finally:
        server.join(timeout=1.0)


def test_a_listener_without_our_addon_says_so():
    from orderflow_system.data.bookmap_client import bookmap_probe

    server = MockBookmapAddon(hello=False, frames=1)
    server.start()
    try:
        result = bookmap_probe("127.0.0.1", server.port, seconds=1.0, timeout=2.0)
        assert result["ok"] is False and result["stage"] == "hello"
        assert "ofap-bookmap-bridge" in result["detail"], "name the add-on the port must be serving"
    finally:
        server.join(timeout=1.0)


def test_bookmap_garbage_is_reported_not_raised():
    from orderflow_system.data.bookmap_client import bookmap_probe

    server = MockBookmapAddon(frames=1, garbage=b"\x01\x02not json at all\x00")
    server.start()
    try:
        result = bookmap_probe("127.0.0.1", server.port, seconds=1.2, timeout=2.0)
        assert result["ok"] is True, "the hello still arrived; a bad frame is data, not a crash"
        assert any("unparsable" in r for r in result["rejects"])
    finally:
        server.join(timeout=1.0)


def test_a_symbol_filter_reports_what_it_dropped():
    from orderflow_system.data.bookmap_client import bookmap_probe

    server = MockBookmapAddon(frames=4, other_symbol_every=2, symbol="BTCUSDT")
    server.start()
    try:
        result = bookmap_probe("127.0.0.1", server.port, seconds=1.2, timeout=2.0, symbol="btcusdt")
        assert result["ok"] is True
        assert any("DOGEUSDT" in r for r in result["rejects"]), "a filtered frame is named, not hidden"
    finally:
        server.join(timeout=1.0)


def test_no_addon_listening_is_a_connect_error_with_a_hint():
    from orderflow_system.data.bookmap_client import bookmap_probe

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    result = bookmap_probe("127.0.0.1", port, seconds=0.5, timeout=1.0)
    assert result["ok"] is False and result["stage"] == "connect"
    assert "Configure API plugins" in result["detail"], "the hint must be the real install path"
    assert bookmap_probe("127.0.0.1", 0)["stage"] == "config"


def test_bookmap_detection_reads_the_manifest_and_nothing_personal(tmp_path):
    """A fake install: the version comes from Bookmap.jar's manifest, and no licence/config file is
    opened even though they are sitting right there."""
    NL = chr(10)
    root = tmp_path / "Bookmap"
    (root / "lib").mkdir(parents=True)
    (root / "Bookmap.exe").write_bytes(b"MZ")
    (root / "Keys").mkdir()
    (root / "Keys" / "licence.key").write_text("SECRET-LICENCE-VALUE", encoding="utf-8")
    (root / "Config").mkdir()
    (root / "Config" / "bookmap_config_v21.json").write_text('{"token":"SECRET-CONFIG-TOKEN"}',
                                                            encoding="utf-8")
    for jar in ("bm-l1api.jar", "bm-simplified-api-wrapper.jar"):
        (root / "lib" / jar).write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    with zipfile.ZipFile(root / "Bookmap.jar", "w") as bundle:
        bundle.writestr("META-INF/MANIFEST.MF",
                        "Manifest-Version: 1.0" + NL + "Main-Class: velox.ib.Main" + NL
                        + "BookMap-version: 7.8.0 build:13" + NL)

    original = platforms.BOOKMAP_CANDIDATES
    platforms.BOOKMAP_CANDIDATES = (str(root),)
    try:
        found = platforms.detect_installs()["bookmap"]
    finally:
        platforms.BOOKMAP_CANDIDATES = original
    assert found["found"] is True and found["path"] == str(root)
    assert found["version"] == "7.8.0 build:13", "the build number is the jar's own manifest line"
    assert found["api_jars"] is True, "both API jars are required for the template to build"
    blob = json.dumps(found)
    assert "SECRET-LICENCE-VALUE" not in blob and "SECRET-CONFIG-TOKEN" not in blob
    assert "Keys" not in blob and "licence.key" not in blob, "the licence folder is not even listed"


def test_local_bookmap_is_found_when_it_is_installed():
    """On this machine (when Bookmap is present) the detection must agree with the disk."""
    found = platforms.detect_installs()["bookmap"]
    if not found["found"]:
        pytest.skip("Bookmap is not installed on this machine")
    assert Path(found["path"], "Bookmap.exe").is_file()
    assert found["version"], "an installed Bookmap must report the build from its own manifest"


# ── the jar that ships with the app (fresh installs need no JDK) ───────────────────────────


def test_the_app_ships_a_built_bridge_jar():
    """A fresh install must be able to add the add-on with no compiler: the jar travels with the app."""
    info = platforms.bridge_jar()
    assert info["exists"], f"the shipped jar is missing: {info['path']}"
    assert info["size"] > 2000, "a jar this small is a stub, not the add-on"
    assert info["built_for"], "the jar's build target must be readable from its class files"
    assert info["built_for"] == "25", (
        "Bookmap 7.8 ships Temurin 25, so the shipped jar is built for Java 25 — "
        f"got {info['built_for']}")
    assert Path(info["source"]).is_dir(), "the source must travel beside the jar for rebuilds"


def test_the_jar_target_is_read_from_the_class_file_header(tmp_path):
    """No guessing from file names: the major version in the class header is the fact."""
    broken = tmp_path / "not-a-jar.jar"
    broken.write_bytes(b"nope")
    assert platforms.jar_target_java(broken) == ""
    empty = tmp_path / "empty.jar"
    with zipfile.ZipFile(empty, "w") as bundle:
        bundle.writestr("readme.txt", "no classes here")
    assert platforms.jar_target_java(empty) == ""
    modern = tmp_path / "modern.jar"
    with zipfile.ZipFile(modern, "w") as bundle:
        bundle.writestr("a/b/C.class", b"\xca\xfe\xba\xbe" + b"\x00\x00" + (69).to_bytes(2, "big"))
    assert platforms.jar_target_java(modern) == "25"


def test_the_frozen_build_ships_the_addon_folder():
    """`dist/` must carry the add-on too, or the packaged app loses the integration."""
    text = (Path(__file__).resolve().parents[1] / "scripts" / "build_exe.py").read_text(
        encoding="utf-8", errors="replace")
    assert "orderflow_system/data/bookmap_addon" in text, "build_exe.py must ship the add-on folder"
    assert "--add-data" in text and "addon_rel" in text, "it ships as data, like the web UI does"


def test_the_bridge_compat_is_compared_not_assumed(tmp_path):
    """Two facts, one comparison: what Java the jar needs, what runtime the local Bookmap ships."""
    jar = tmp_path / "Bookmap"
    (jar / "lib").mkdir(parents=True)
    (jar / "Bookmap.exe").write_bytes(b"MZ")
    (jar / "jre").mkdir()
    (jar / "jre" / "release").write_text('JAVA_VERSION="25.0.2"' + chr(10), encoding="utf-8")

    original = platforms.BOOKMAP_CANDIDATES
    platforms.BOOKMAP_CANDIDATES = (str(jar),)
    try:
        matched = platforms.bookmap_bridge_state()
        assert matched["bookmap_runtime"] == "25.0.2"
        assert matched["ok"] is True and "will load as-is" in matched["note"]

        (jar / "jre" / "release").write_text('JAVA_VERSION="17.0.9"' + chr(10), encoding="utf-8")
        mismatched = platforms.bookmap_bridge_state()
        assert mismatched["ok"] is False
        assert "Rebuild" in mismatched["note"] and "17.0.9" in mismatched["note"]
    finally:
        platforms.BOOKMAP_CANDIDATES = original

    # and with no Bookmap at all the comparison is honestly not made, rather than passed
    platforms.BOOKMAP_CANDIDATES = (str(tmp_path / "nowhere"),)
    try:
        unknown = platforms.bookmap_bridge_state()
        assert unknown["ok"] is None and "nothing to compare" in unknown["note"]
    finally:
        platforms.BOOKMAP_CANDIDATES = original


def test_revealing_the_jar_refuses_anything_but_our_own_folder():
    """'Show the jar' opens what the suite shipped — never a path handed to it from elsewhere."""
    for foreign in ("C:\\Windows", str(Path.home()), "C:\\Program Files\\Bookmap"):
        res = platforms.reveal_bridge_jar(foreign)
        assert res["ok"] is False, f"{foreign} must be refused"
        assert "not this app's add-on folder" in res["error"] or "no such folder" in res["error"]


def test_the_free_path_now_ships_the_addon_instead_of_a_compiler():
    """The wizard step must match what the product does: the jar is shipped, not built by the user."""
    steps = platforms.bookmap_workflow()["steps"]
    step = [s for s in steps if "add-on" in s["title"].lower()][0]
    assert "no compiler needed" in step["text"], "a fresh user must not be told to build anything"
    assert "ofap-bridge.jar" in step["text"] and "Configure API plugins" in step["text"]
    assert "JDK" not in step["text"]
