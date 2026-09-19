"""Pins for the security-audit fixes: the boundary (SEC-24/SEC-29), the log leak (SEC-01),
the two numeric gates (SEC-05/SEC-06), the update channel and its download (SEC-10/11/25),
the news fetch (SEC-28), the derived-profile label (SEC-14) and the CSV reader (SEC-33).

Every one of these is a REGRESSION pin: each test fails on the pre-fix behaviour.
"""
from __future__ import annotations

import asyncio
import logging
import os

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from orderflow_system.dashboard.app import (
    LocalRequestGuard,
    is_trusted_ws_handshake,
    names_this_server,
    origin_port,
)


def _guarded_client() -> TestClient:
    async def probe(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/probe", probe, methods=["POST"])])
    app.add_middleware(LocalRequestGuard)
    return TestClient(app)


# ── SEC-24 · the port is part of the origin ──────────────────────────────────────────────────
def test_origin_port_parsing() -> None:
    assert origin_port("http://127.0.0.1:8123") == "8123"
    assert origin_port("127.0.0.1:8099") == "8099"
    assert origin_port("http://localhost") == ""
    assert origin_port("[::1]:8099") == "8099"
    assert origin_port("http://127.0.0.1:8123@evil.com") == ""


def test_a_loopback_origin_on_another_port_is_a_different_origin() -> None:
    """A page served by any other local process lives on another port — and browsers call
    cross-port loopback `same-site`, so the old host-only check let it through."""
    assert names_this_server("http://127.0.0.1:8123", "8123") is True
    assert names_this_server("http://127.0.0.1:8140", "8123") is False
    assert names_this_server("http://localhost:8140", "8123") is False
    assert names_this_server("http://evil.example", "8123") is False


def test_the_middleware_refuses_a_cross_port_loopback_post() -> None:
    client = _guarded_client()
    host = {"Host": "127.0.0.1:8123"}          # this server states its port, as the real app does
    # same port → allowed
    ok = client.post("/probe", headers={**host, "Origin": "http://127.0.0.1:8123"})
    assert ok.status_code == 200, ok.text
    # the audit's reproduction: any OTHER loopback port is a foreign origin
    for origin in ("http://127.0.0.1:8140", "http://localhost:9000", "https://evil.example"):
        res = client.post("/probe", headers={**host, "Origin": origin})
        assert res.status_code == 403, (origin, res.status_code)
    # native clients (no Origin) keep working
    assert client.post("/probe", headers=host).status_code == 200


def test_the_websocket_handshake_applies_the_same_rule() -> None:
    assert is_trusted_ws_handshake({"origin": "http://127.0.0.1:8123", "host": "127.0.0.1:8123"})
    assert not is_trusted_ws_handshake({"origin": "http://127.0.0.1:8140", "host": "127.0.0.1:8123"})
    assert not is_trusted_ws_handshake({"origin": "https://evil.example", "host": "127.0.0.1:8123"})
    assert not is_trusted_ws_handshake({"origin": "http://127.0.0.1:8123",
                                        "host": "127.0.0.1:8123", "sec-fetch-site": "cross-site"})
    assert is_trusted_ws_handshake({"host": "127.0.0.1:8123"})   # native client, no Origin


# ── SEC-29 · frame refusal ───────────────────────────────────────────────────────────────────
def test_every_response_refuses_to_be_framed() -> None:
    res = _guarded_client().post("/probe")
    assert res.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in res.headers.get("content-security-policy", "")
    assert res.headers.get("x-content-type-options") == "nosniff"


# ── SEC-01 · no token-shaped text reaches a sink ─────────────────────────────────────────────
TOKEN = "8123456789:" + "AAF" + "x" * 30


def test_redact_rewrites_every_token_shape() -> None:
    from orderflow_system.desktop.logs import redact

    url = redact(f"POST https://api.telegram.org/bot{TOKEN}/getMe")
    assert TOKEN not in url and "bot<redacted>" in url
    bare = redact(f"The token `{TOKEN}` was rejected by the server.")
    assert TOKEN not in bare and "<redacted>" in bare
    qs = redact("https://x.example/hook?token=abcdefghijklmnop")
    assert "abcdefghijklmnop" not in qs and "<redacted>" in qs
    assert redact("nothing to hide") == "nothing to hide"


def test_the_filter_cleans_a_third_party_record_before_formatting() -> None:
    from orderflow_system.desktop.logs import RedactingFilter

    record = logging.LogRecord("httpx", logging.WARNING, __file__, 1,
                               "HTTP Request: POST https://api.telegram.org/bot%s/getMe",
                               (TOKEN,), None)
    RedactingFilter().filter(record)
    assert TOKEN not in record.getMessage()


def test_every_installed_handler_carries_the_filter(monkeypatch, tmp_path) -> None:
    from orderflow_system.desktop import logs as logs_mod
    from orderflow_system.desktop.logs import RedactingFilter

    import logging.handlers

    monkeypatch.setattr(logs_mod, "log_path", lambda: tmp_path / "orderflow.log")
    logs_mod.install()
    # pytest attaches its own capture handlers to the root logger, so look only at ours
    ours = [h for h in logging.getLogger().handlers
            if isinstance(h, (logs_mod.BufferHandler, logging.handlers.RotatingFileHandler))]
    assert ours, "install() added no handlers of its own"
    assert all(any(isinstance(f, RedactingFilter) for f in h.filters) for h in ours)


# ── SEC-05 · tick_size ───────────────────────────────────────────────────────────────────────
def test_a_zero_or_nan_tick_size_is_clamped() -> None:
    from orderflow_system.desktop.config_store import _sanitise

    for bad in (0, float("nan"), float("inf"), -3, "abc", None):
        cfg = _sanitise({"instruments": [{"symbol": "NAS100USDT", "tick_size": bad}]})
        got = cfg["instruments"][0]["tick_size"]
        assert isinstance(got, float) and 1e-9 <= got <= 1e6, (bad, got)


# ── SEC-25 · the update channel must exist ───────────────────────────────────────────────────
def test_the_updater_watches_the_repository_that_carries_the_releases() -> None:
    from orderflow_system.desktop import updater

    assert updater.REPO == "ModdySwag/ModFlow-beta-builds", (
        "SEC-25: releases live in the -beta-builds repository; the source repo has none, so an "
        "installed build would read 'up to date' forever")
    assert updater.REPO in updater.RELEASES_URL and updater.REPO in updater.RELEASE_PAGE


@pytest.mark.skipif(os.environ.get("OFAP_NETWORK_TESTS") != "1",
                    reason="network test — run with OFAP_NETWORK_TESTS=1")
def test_the_configured_repository_actually_answers() -> None:
    import json
    import urllib.request

    from orderflow_system.desktop import updater

    with urllib.request.urlopen(updater.RELEASES_URL, timeout=20) as response:
        releases = json.load(response)
    assert isinstance(releases, list) and releases, "the update channel answers with no releases"


# ── SEC-10 / SEC-11 · downloads ─────────────────────────────────────────────────────────────
def test_a_non_http_update_url_is_refused(tmp_path) -> None:
    from orderflow_system.desktop import updater

    res = updater.download_asset("file:///C:/Windows/win.ini", tmp_path)
    assert res["ok"] is False and "http" in res["error"]


def test_an_over_cap_download_is_refused(tmp_path) -> None:
    from orderflow_system.desktop import updater

    class _Resp:
        headers = {"Content-Length": str(updater.MAX_DOWNLOAD_BYTES + 1)}

        def read(self, n):                              # pragma: no cover - never reached
            return b""

    res = updater.download_asset("https://example.invalid/big.exe", tmp_path,
                                 opener=lambda url, timeout: _Resp())
    assert res["ok"] is False and "cap" in res["error"]


# ── SEC-28 · the news fetch is not a relay ──────────────────────────────────────────────────
def test_a_foreign_news_url_cannot_drive_the_fetch(monkeypatch) -> None:
    from orderflow_system.atlas import api as atlas_api

    monkeypatch.setattr(atlas_api, "_context_settings",
                        lambda: {"enabled": True, "news_url": "https://mine.example/feed.json"})
    out = asyncio.run(atlas_api.market_context("BTCUSDT", news_url="https://evil.example/steal",
                                               news_limit=0))
    assert out["ok"] is False and "Settings" in out["error"]


# ── SEC-33 · an unreadable CSV is the caller's error, not ours ──────────────────────────────
def test_an_unreadable_csv_is_a_400(monkeypatch) -> None:
    import _csv

    from fastapi import HTTPException

    from orderflow_system.desktop import api as desktop_api
    from orderflow_system.desktop import dataport

    def _boom(text, **kwargs):
        raise _csv.Error("field larger than field limit (131072)")

    monkeypatch.setattr(dataport, "parse_ticks", _boom)
    with pytest.raises(HTTPException) as err:
        asyncio.run(desktop_api.data_import({"text": "price,size\n" + "x" * 40}))
    assert err.value.status_code == 400


# ── SEC-07 · a book the feed flagged stale is not folded ────────────────────────────────────
def test_a_stale_book_is_not_folded_into_the_heatmap() -> None:
    from types import SimpleNamespace

    from orderflow_system.atlas import depthmap as depthmap_mod

    cls = next(v for v in vars(depthmap_mod).values()
               if isinstance(v, type) and hasattr(v, "on_orderbook"))
    heat = cls("BTCUSDT")
    stale = SimpleNamespace(stale=True, timestamp_ms=1, best_bid=1.0, best_ask=2.0, bids=[], asks=[])
    assert heat.on_orderbook(stale) == []
    assert heat.stats()["stale_skipped"] == 1
    fresh = SimpleNamespace(stale=False, timestamp_ms=1, best_bid=1.0, best_ask=2.0, bids=[], asks=[])
    heat.on_orderbook(fresh)
    assert heat.stats()["stale_skipped"] == 1


# ── SEC-15 · the tape stores a print once ───────────────────────────────────────────────────
def test_the_tape_cannot_store_the_same_print_twice(tmp_path) -> None:
    from orderflow_system.data.database import Database
    from orderflow_system.data.models import Side, Tick

    async def run() -> tuple[int, int]:
        db = Database(str(tmp_path / "t.db"))
        await db.connect()
        try:
            tagged = Tick(1_700_000_000_000, 100.0, 2.0, Side.BUY, trade_id="abc")
            await db.insert_ticks_batch("BTCUSDT", [tagged, tagged])
            first = len(await db.get_ticks("BTCUSDT", 0, 2_000_000_000_000))
            bare = Tick(1_700_000_000_001, 100.0, 2.0, Side.BUY)
            await db.insert_ticks_batch("BTCUSDT", [bare, bare])
            second = len(await db.get_ticks("BTCUSDT", 0, 2_000_000_000_000))
            return first, second
        finally:
            await db.close()

    first, second = asyncio.run(run())
    assert first == 1, "a print with a trade_id must be stored once"
    assert second == 3, "a print WITHOUT a trade_id may legitimately repeat — 1 + 2"


# ── SEC-14 · a profile built from footprint-less candles says so ─────────────────────────────
def test_a_derived_profile_is_counted_persisted_and_spoken(tmp_path) -> None:
    """The even-smear fallback is fabricated distribution: the builder must count it, the DB
    must keep the count across a rebuild, the wire must carry it and the UI must say it."""
    from pathlib import Path

    from orderflow_system.analytics.volume_profile import VolumeProfileEngine
    from orderflow_system.config.settings import VolumeProfileConfig
    from orderflow_system.data.database import Database
    from orderflow_system.data.models import Candle, FootprintLevel

    engine = VolumeProfileEngine(VolumeProfileConfig(tick_size=0.5))
    measured = Candle(timestamp_ms=1, open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0,
                      footprint={100.0: FootprintLevel(price=100.0, bid_volume=4.0, ask_volume=6.0)})
    smeared = Candle(timestamp_ms=2, open=100.0, high=101.0, low=99.0, close=100.5, volume=8.0)

    only_measured = engine.compute_from_candles([measured], session_date="2026-01-01")
    assert only_measured.derived_candles == 0 and only_measured.derived is False
    only_smeared = engine.compute_from_candles([smeared], session_date="2026-01-01")
    assert only_smeared.derived_candles == 1 and only_smeared.derived is True
    mixed = engine.compute_from_candles([measured, smeared], session_date="2026-01-01")
    assert mixed.derived_candles == 1, "one of the two candles had no footprint"
    merged = engine.merge_profiles([only_smeared, mixed])
    assert merged.derived_candles == 2, "a composite carries the sum of its inputs' counts"

    async def run() -> int:
        db = Database(str(tmp_path / "vp.db"))
        await db.connect()
        try:
            await db.insert_volume_profile("BTCUSDT", only_smeared)
            rows = await db.get_volume_profiles("BTCUSDT", days=5)
            return rows[-1].derived_candles
        finally:
            await db.close()

    assert asyncio.run(run()) == 1, "the count must survive the DB round trip"

    root = Path(__file__).parent
    assert "derived_candles" in (root / "atlas" / "api.py").read_text(encoding="utf-8"), (
        "the profile route stopped carrying the derived count — the screen goes back to hiding it")
    assert "derived_candles" in (root / "main.py").read_text(encoding="utf-8")
    ui = (root / "desktop" / "ui" / "atlas.js").read_text(encoding="utf-8")
    assert "Profile basis" in ui and "footprint-less" in ui, "the derived label left the Profile view"


# ── SEC-09 · credentials are write-only over the control API ─────────────────────────────────
def test_credentials_are_masked_on_read_and_kept_through_a_masked_write(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from orderflow_system.desktop import config_store

    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    stored = config_store.save_config({
        "telegram": {"bot_token": "123456:REAL-TOKEN", "chat_id": "42"},
        "notify": {"email": {"password": "hunter2"}},
        "platforms": {"sierra": {"password": "dtc-pass"}},
        "alpaca": {"key_id": "PKREALKEY", "secret": "verysecret"},
        "mt5": {"password": "broker-pass"},
    })

    masked = config_store.mask_secrets(stored)
    assert masked["telegram"]["bot_token"] == config_store.SECRET_MASK
    assert masked["notify"]["email"]["password"] == config_store.SECRET_MASK
    assert masked["platforms"]["sierra"]["password"] == config_store.SECRET_MASK
    assert masked["alpaca"]["key_id"] == config_store.SECRET_MASK
    assert masked["alpaca"]["secret"] == config_store.SECRET_MASK
    assert masked["mt5"]["password"] == config_store.SECRET_MASK
    assert masked["telegram"]["chat_id"] == "42", "a chat id is an identifier, not a credential"
    assert stored["telegram"]["bot_token"] == "123456:REAL-TOKEN", "the input must not be mutated"

    # the exact UI flow: POST the whole (masked) config back — every secret survives
    config_store.merge_config(masked)
    kept = config_store.load_config()
    assert kept["telegram"]["bot_token"] == "123456:REAL-TOKEN"
    assert kept["alpaca"]["secret"] == "verysecret"
    assert kept["mt5"]["password"] == "broker-pass"

    # a genuine value replaces; an explicit empty string clears
    config_store.merge_config({"telegram": {"bot_token": "new-token"}})
    assert config_store.load_config()["telegram"]["bot_token"] == "new-token"
    config_store.merge_config({"telegram": {"bot_token": ""}})
    assert config_store.load_config()["telegram"]["bot_token"] == ""

    # the test routes substitute the STORED secret for a mask (never post bullets to a provider)
    assert config_store.secret_or_stored(stored, "telegram.bot_token", config_store.SECRET_MASK) \
        == "123456:REAL-TOKEN"
    assert config_store.secret_or_stored(stored, "telegram.bot_token", "typed") == "typed"

    # and the read routes are wired to the mask
    api = (Path(__file__).parent / "desktop" / "api.py").read_text(encoding="utf-8")
    assert "mask_secrets" in api, "GET /config and /bootstrap must mask"


# ── SEC-08 · the shell's script-src carries a hash, not 'unsafe-inline' ──────────────────────
def test_the_shell_csp_hashes_its_inline_script_instead_of_allowing_all_inline() -> None:
    import base64
    import hashlib
    import re
    from pathlib import Path

    html = (Path(__file__).parent / "desktop" / "ui" / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    assert csp, "the shell lost its CSP"
    policy = csp.group(1)
    script_src = next(part.strip() for part in policy.split(";") if part.strip().startswith("script-src"))
    assert "'self'" in script_src
    assert "'unsafe-inline'" not in script_src, (
        "an injected inline script must not run — the hash list is what allows the one block")
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(blocks) == 1, "the hash list must match the inline blocks exactly"
    norm = blocks[0].replace(chr(13) + chr(10), chr(10))   # CRLF -> LF, the parser's normalisation
    digest = base64.b64encode(hashlib.sha256(norm.encode("utf-8")).digest()).decode()
    assert f"'sha256-{digest}'" in script_src, "the hash no longer matches the inline block"
    assert "'unsafe-eval'" in script_src, (
        "the Studies runtime compiles pasted modules with new Function; drop this flag only when "
        "that feature is redesigned")


# ── SEC-02 · an artifact that carries code asks first ──────────────────────────────────────
def test_an_artifact_that_carries_code_is_stripped_without_consent(monkeypatch) -> None:
    from orderflow_system.desktop import api as desktop_api
    from orderflow_system.desktop import config_store

    code = "console.log('probe')"
    saved: dict = {}

    def fresh():
        return {"format": desktop_api._ARTIFACT_FORMAT, "schema": 1, "kind": "studies",
                "blocks": {"studies": {"custom": [{"name": "probe", "source": code}]}}}

    monkeypatch.setattr(config_store, "load_config", lambda: {})
    monkeypatch.setattr(config_store, "save_config", lambda cfg: saved.update(cfg))

    out = asyncio.run(desktop_api.post_config_import({"artifact": fresh()}))
    assert out["ok"] and out["code_modules"] == ["probe"] and out["code_stripped"] == 1
    stored = (saved.get("studies") or {}).get("custom") or [{}]
    assert not str(stored[0].get("source") or ""), "the source must not survive an unconsented import"

    saved.clear()
    out2 = asyncio.run(desktop_api.post_config_import({"artifact": fresh(), "allow_code": True}))
    assert out2["code_stripped"] == 0
    assert ((saved.get("studies") or {}).get("custom") or [{}])[0].get("source") == code


# ── SEC-04 · a replayed print never fires an alert ─────────────────────────────────────────
def test_a_replayed_print_does_not_fire_an_alert() -> None:
    from orderflow_system.atlas.hub import FeatureHub
    from orderflow_system.data.models import Side, Tick

    assert Tick(1, 1.0, 1.0, Side.BUY).replay is False

    class _Alert:
        ts_ms = 0
        message = "probe"

        def to_dict(self):
            return {"message": self.message}

    hub = FeatureHub()
    sent = []
    keep_emit, keep_record = hub._emit, hub._record
    hub._emit = lambda *a, **k: sent.append(a)
    hub._record = lambda *a, **k: None
    try:
        hub.replaying = True
        hub._emit_fired("BTCUSDT", [_Alert()], 100.0, 1.0)
        assert sent == [], "a replayed print fired an alert"
        assert hub.counters.get("alerts_suppressed_replay", 0) >= 1
    finally:
        hub.replaying = False
        hub._emit, hub._record = keep_emit, keep_record


def test_the_log_ring_bound_is_asserted():
    """G-10: the ring holds exactly MAX_LINES after MAX_LINES*3 records, and tail() is honest."""
    import logging as _logging

    from orderflow_system.desktop import logs as logs_mod

    logger = _logging.getLogger("orderflow_system.test.ring_bound")
    for n in range(logs_mod.MAX_LINES * 3):
        logger.info("ring bound test %d", n)
    assert len(logs_mod._buffer) == logs_mod.MAX_LINES
    assert len(logs_mod.tail(lines=10_000)) == logs_mod.MAX_LINES
