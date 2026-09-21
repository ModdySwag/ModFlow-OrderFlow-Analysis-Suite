"""Release-assurance fix receipts (§127): the three RA findings and the two queued cosmetics.

One test per executed fix, each pinning the shipped shape:

* **RA-01** — the Engine readout escapes the symbol, and the store clamps it (A-Z, 0-9, . _ -,
  max 24) so no renderer has to defend itself; a symbol that cleans to nothing is dropped.
* **RA-02** — the export filename tag is a sanitised filename component, and the route answers
  a sentence (400) when the store cannot be read, never a traceback.
* **RA-03** — the Bybit validation URL carries a fully-quoted symbol; a symbol cannot add,
  drop or restructure query parameters.
* **F-05** — client-abort tracebacks (ConnectionResetError) are dropped by every log sink.
* **F-08** — the sha1 non-security use is annotated; the two dynamic-SQL loops use static
  statement strings (identifiers never interpolated).

The pins read the shipped sources or drive the real functions — a refactor that silently
reopens a finding fails here first.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

_UI_OFXV = Path(__file__).parent / "desktop" / "ui" / "ofx-view.js"


# ── RA-01 ───────────────────────────────────────────────────────────────────────────────────

def test_the_engine_view_escapes_its_symbol_sinks():
    """The Engine readout was the audit's proven sink — and the live re-probe of THIS pass caught
    a second one: the legend panel renders `OFX.legend()`'s `live` string, which carries the
    symbol (ofx.js). Both now escape at the sink; every legend field does, uniformly."""
    src = _UI_OFXV.read_text(encoding="utf-8")
    hazards = [ln.strip() for ln in src.splitlines() if "innerHTML" in ln and "${sym}" in ln]
    assert hazards == [], f"unescaped symbol reachable from innerHTML: {hazards[:3]}"
    assert src.count("${esc(sym)}") == 2, "both readout branches must carry the escape"
    for banned in ("${e.live}", "${e.name}", "${e.meaning}", "${d.field}", "${d.meaning}",
                   "${d.from}", "${i.keys}", "${i.action}", "<li>${l}</li>",
                   "${spec.glyph}", "${spec.sample || 'abc'}"):
        assert banned not in src, f"legend field unescaped: {banned}"
    for wanted in ("${esc(e.live)}", "${esc(e.name)}", "${esc(d.from)}", "${esc(i.keys)}",
                   "<li>${esc(l)}</li>", "${esc(spec.glyph)}"):
        assert wanted in src, f"missing escape: {wanted}"


def test_symbols_are_clamped_in_the_store():
    """The store is the choke point for the streaming symbol: whatever a hand-edited file holds,
    the value of `instruments[].symbol` can only carry the charset the readout, the feed lanes
    and the export tag all tolerate."""
    from orderflow_system.desktop.config_store import _sanitise

    clean = _sanitise({
        "instruments": [
            {"symbol": 'BTCUSDT"</div><img src="x">', "enabled": True},
            {"symbol": "<<>>", "enabled": True},                       # cleans to nothing → dropped
            {"symbol": "ethusdt", "enabled": True},
            {"symbol": "NQ 12-26", "ninjatrader_symbol": "NQ 12-26", "enabled": True},
        ],
    })
    assert [i["symbol"] for i in clean["instruments"]] == [
        "BTCUSDTDIVIMGSRCX", "ETHUSDT", "NQ12-26"]
    nt = [i for i in clean["instruments"] if i["symbol"] == "NQ12-26"][0]
    assert nt["ninjatrader_symbol"] == "NQ 12-26", "the terminal's own name is case and shape free"
    # The palette lanes (watchlist / search recents+pins) deliberately keep their own contract —
    # `BTC/USD` is a pair a user can search and watch (pinned by test_config_store); the readout
    # sink only ever renders `instruments[].symbol`, which is what this clamp covers.


def test_a_legitimate_config_round_trips():
    """The clamp is a no-op for everything the app itself writes."""
    from orderflow_system.desktop.config_store import _sanitise

    inst = {"symbol": "BTCUSDT", "enabled": True}
    clean = _sanitise({"instruments": [dict(inst)], "watchlist": ["BTCUSDT", "ETHUSDT"]})
    assert clean["instruments"][0]["symbol"] == "BTCUSDT"
    assert clean["watchlist"] == ["BTCUSDT", "ETHUSDT"]


# ── RA-02 ───────────────────────────────────────────────────────────────────────────────────

def test_export_filename_tag_is_sanitised(tmp_path):
    """A symbol with a path separator used to build a bogus subpath (ticks-BTC/USDT-….csv).
    The tag is now clamped like the paper export's — the file lands in dest_dir, full stop."""
    from orderflow_system.desktop import dataport

    db = tmp_path / "d.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE ticks (instrument TEXT, timestamp_ms INTEGER, price REAL, "
                 "size REAL, side TEXT, trade_id TEXT)")
    conn.execute("INSERT INTO ticks VALUES ('BTC/USDT', 1700000000000, 1.0, 2.0, 'buy', 't1')")
    conn.commit()
    conn.close()

    dest = tmp_path / "exports"
    out = dataport.export_rows(db, "ticks", dest, symbol="../../evil", now=1_700_000_000)
    p = Path(out["path"])
    assert p.parent == dest, p
    assert re.fullmatch(r"ticks-[A-Za-z0-9._-]+-\d{8}-\d{6}\.csv(\.gz)?", p.name), p.name

    found = dataport.export_rows(db, "ticks", dest, symbol="btc/usdt", now=1_700_000_001)
    assert Path(found["path"]).name.startswith("ticks-BTCUSDT-"), found
    assert found["rows"] == 1


def test_export_route_answers_400_when_the_store_is_missing(tmp_path, monkeypatch):
    """A fresh profile has no database yet — that is a sentence the panel can show, not the
    500 + traceback the audit receipted."""
    from orderflow_system.desktop import api, config_store
    from orderflow_system.test_request_guard import _client

    monkeypatch.setattr(config_store, "db_path", lambda: tmp_path / "missing.db")
    monkeypatch.setattr(api, "_exports_dir", lambda: tmp_path / "exports")

    resp = _client().post("/api/control/data/export?kind=ticks")
    assert resp.status_code == 400, resp.text
    assert "no tick history" in resp.json()["detail"]


# ── RA-03 ───────────────────────────────────────────────────────────────────────────────────

def test_bybit_url_cannot_be_restructured_by_a_symbol(monkeypatch):
    """SS-12's family: values interpolated into request URLs are quoted, so a symbol cannot
    smuggle `&` / `=` into the query (the parser would otherwise see new parameters)."""
    import json
    import urllib.request

    from orderflow_system.desktop import engine

    seen: list[str] = []

    class _Resp:
        def read(self):
            return json.dumps({"result": {"list": [{"symbol": "A"}]}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(url, timeout=None):
        seen.append(url)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    sym = "A&B=x/y z"
    out = engine.bybit_validate([sym])
    assert seen, "the validator must have called out"
    assert "%26" in seen[0] and "%2F" in seen[0] and "%3D" in seen[0], seen[0]
    assert "&symbol=A&B" not in seen[0], "the raw symbol must not reach the query"
    assert out == {sym: True}


# ── F-05 / F-08 cosmetics ───────────────────────────────────────────────────────────────────

def test_client_aborts_do_not_reach_the_log_sinks():
    """A connection reset mid-response is the client leaving; uvicorn's ASGI-error traceback
    for it is noise the Logs view should not carry. Real errors still land."""
    from orderflow_system.desktop import logs

    dropped = logging.LogRecord(
        "uvicorn.error", logging.ERROR, __file__, 1, "Exception in ASGI application", None,
        (ConnectionResetError, ConnectionResetError(10054, "aborted"), None))
    assert logs.AbortedSocketFilter().filter(dropped) is False

    kept = logging.LogRecord(
        "uvicorn.error", logging.ERROR, __file__, 1, "Exception in ASGI application", None,
        (ValueError, ValueError("a real bug"), None))
    assert logs.AbortedSocketFilter().filter(kept) is True

    logs.install()
    sinks = [h for h in logging.getLogger().handlers]
    assert sinks, "install() must attach at least one sink"
    for h in sinks:
        assert any(isinstance(f, logs.AbortedSocketFilter) for f in h.filters), type(h).__name__


def test_cosmetic_pins():
    """F-08: the sha1 here is an identity digest, not security — annotated so a scanner (and a
    reader) knows. The two dynamic-SQL loops now use static statement strings."""
    from orderflow_system.data import database
    from orderflow_system.desktop import single_instance

    si = Path(single_instance.__file__).read_text(encoding="utf-8")
    assert 'hashlib.sha1(key.encode("utf-8"), usedforsecurity=False)' in si

    db = Path(database.__file__).read_text(encoding="utf-8")
    assert 'f"SELECT COUNT(*) FROM {table}"' not in db
    assert '"SELECT COUNT(*) FROM ticks"' in db
    assert '"DELETE FROM atlas_events WHERE ts_ms < ?"' in db
