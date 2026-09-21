"""§146 — the optional REST feeds' keys (Settings ▸ Feed keys) and the two lanes that read them.

The claim this file is about: a key the user types in the card is (a) stored in the config, (b) live
for the chain panels, the calendar lane and the news lane without an engine restart, and (c) never
readable back out of the API — while (d) the card and the routes offer exactly the same set of
leaves, so nothing a field writes can be silently dropped and nothing a route accepts is invisible.

What is pinned here, all of it offline (a stubbed feed, a stubbed transport, no socket):

* the read masks each credential and the payload carries no trace of the stored value;
* the write whitelist: an unknown leaf in the body never reaches the store, a blank credential keeps
  the stored value (SEC-09), a typed one replaces it, and the answer is masked too;
* the two lanes accept only the values the panels understand, and each is saved on the spot;
* an empty body is refused rather than treated as "write nothing";
* the calendar lane refuses without a key with one honest sentence, and with one it maps Finnhub
  events through the app's own row shape and filters them exactly like the built-in lane;
* the news lane REPLACES the headline section (the built-in feeds are not asked at all) and names
  itself in stats.lane, with the server's reason when it has no headlines;
* the card's markup ids exist, the module is loaded by the shell, and the JS SPECS table and the
  route's `_FEED_KEY_BLOCKS` agree leaf for leaf;
* the store keeps what the card writes, at the bounds the card prints.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_feedkeys.py -q
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).parent / "desktop" / "ui"

CREDENTIALS = {
    "tradier": {"key_id": "KEYID-REAL-1234", "secret": "SECRET-REAL-5678"},
    "marketdata": {"api_key": "MD-REAL-TOKEN"},
    "finnhub": {"api_key": "FH-REAL-TOKEN"},
}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


@pytest.fixture()
def client(store, monkeypatch):
    """The two routers on a bare app, with the global settings push replaced by a recorder.

    `engine.apply_settings` is called by the write route so a fresh key is live for the panels; the
    real one rewrites global settings, which a test has no business doing — so it is recorded, and
    the tests assert it was asked.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from orderflow_system.atlas import api as atlas_api
    from orderflow_system.desktop import api as desktop_api

    applied: list[dict] = []
    monkeypatch.setattr(desktop_api.engine_mod, "apply_settings",
                        lambda cfg: applied.append(cfg), raising=False)
    app = FastAPI()
    app.include_router(desktop_api.router)
    app.include_router(atlas_api.router)
    return TestClient(app), applied


# ── the read: masked, and never the value ────────────────────────────────────────────────────

def test_the_read_masks_every_credential_and_keeps_the_rest(store):
    from orderflow_system.desktop import api as desktop_api

    cfg = store.save_config({
        "tradier": {"key_id": CREDENTIALS["tradier"]["key_id"],
                    "secret": CREDENTIALS["tradier"]["secret"], "chain_width": 11},
        "marketdata": {"api_key": CREDENTIALS["marketdata"]["api_key"]},
        "finnhub": {"api_key": CREDENTIALS["finnhub"]["api_key"], "calendar_days": 5},
    })

    state = desktop_api._feed_keys_state(cfg)
    blob = json.dumps(state)
    for block in CREDENTIALS.values():
        for value in block.values():
            assert value not in blob, "a stored credential must not travel back to the page"

    rows = {row["id"]: row for row in state["feeds"]}
    assert rows["tradier"]["key_hint"].startswith("KEYI") and "REAL-1234" not in rows["tradier"]["key_hint"]
    assert rows["tradier"]["has_secret"] is True
    assert rows["tradier"]["values"]["chain_width"] == 11
    assert rows["marketdata"]["key_hint"].startswith("MD-R")
    assert rows["finnhub"]["values"]["calendar_days"] == 5
    assert all(row["ready"] for row in state["feeds"])
    assert state["lanes"] == {"calendar": "builtin", "news": "feeds"}


def test_an_unset_feed_reads_as_not_set(store):
    from orderflow_system.desktop import api as desktop_api

    state = desktop_api._feed_keys_state(store.load_config())
    rows = {row["id"]: row for row in state["feeds"]}
    assert rows["tradier"]["ready"] is False and rows["tradier"]["key_hint"] == ""
    assert rows["tradier"]["has_secret"] is False
    assert [len(row["leaves"]) for row in state["feeds"]] == [4, 1, 4]


def test_the_route_answers_the_same_masked_shape(client, store):
    tc, _applied = client
    store.save_config({"finnhub": {"api_key": CREDENTIALS["finnhub"]["api_key"]}})
    body = tc.get("/api/control/feedkeys").json()
    assert body["ok"] is True
    assert CREDENTIALS["finnhub"]["api_key"] not in json.dumps(body)
    assert [row["id"] for row in body["feeds"]] == ["tradier", "marketdata", "finnhub"]


# ── the write: whitelisted, kept, and masked on the way out ──────────────────────────────────

def test_an_omitted_credential_keeps_it_and_an_explicit_empty_string_clears_it(client, store):
    tc, applied = client
    before = store.save_config({
        "tradier": {"key_id": "OLD-ID", "secret": "OLD-SECRET"},
        "marketdata": {"api_key": "MD-OLD"},
    })

    # The card omits a credential the user did not touch — that omission is what keeps it.
    res = tc.post("/api/control/feedkeys", json={"tradier": {
        "secret": "NEW-SECRET",             # typed: replace
        "chain_width": 12,
        "view_symbols": ["HACK"],           # not a leaf this route accepts
        "enabled": True,                    # deliberately not offered either
    }})
    assert res.status_code == 200 and res.json()["ok"] is True

    kept = store.load_config()
    assert kept["tradier"]["key_id"] == "OLD-ID", "an omitted credential is left alone"
    assert kept["tradier"]["secret"] == "NEW-SECRET"
    assert kept["tradier"]["chain_width"] == 12
    assert kept["tradier"]["view_symbols"] == before["tradier"]["view_symbols"]
    assert kept["tradier"]["enabled"] == before["tradier"]["enabled"]
    assert applied, "the settings push must run so a fresh key is live without a restart"

    wire = json.dumps(res.json())
    assert "NEW-SECRET" not in wire and "OLD-ID" not in wire, "the answer is masked like the read"

    # …and an explicit empty string is the one path that empties a credential (the card's ×).
    cleared = tc.post("/api/control/feedkeys", json={"tradier": {"key_id": ""}}).json()
    assert cleared["ok"] is True
    assert store.load_config()["tradier"]["key_id"] == ""
    assert store.load_config()["tradier"]["secret"] == "NEW-SECRET", "and only the named leaf"


def test_an_empty_body_is_refused_rather_than_written(client, store):
    tc, applied = client
    store.save_config({"finnhub": {"api_key": "KEEP-ME"}})
    body = tc.post("/api/control/feedkeys", json={}).json()
    assert body["ok"] is False and "no feed block" in body["error"]
    assert store.load_config()["finnhub"]["api_key"] == "KEEP-ME"
    assert not applied


def test_the_lanes_accept_only_what_the_panels_understand(client, store):
    tc, _applied = client
    refused = tc.post("/api/control/feedkeys", json={"lanes": {"calendar": "bogus", "news": "wat"}}).json()
    assert refused["lanes"] == {"calendar": "builtin", "news": "feeds"}

    chosen = tc.post("/api/control/feedkeys", json={"lanes": {"calendar": "finnhub", "news": "finnhub"}}).json()
    assert chosen["lanes"] == {"calendar": "finnhub", "news": "finnhub"}
    saved = store.load_config()
    assert saved["calendar"]["source"] == "finnhub" and saved["context"]["news_source"] == "finnhub"


# ── the calendar lane ────────────────────────────────────────────────────────────────────────

def test_the_calendar_lane_refuses_without_a_key_in_one_sentence(client, store):
    tc, _applied = client
    store.merge_config({"calendar": {"source": "finnhub"}})
    body = tc.get("/api/control/calendar?hours=48&impact=high").json()
    assert body["ok"] is False and body["lane"] == "finnhub"
    assert body["events"] == [] and body["upcoming"] == 0
    assert "no Finnhub key" in body["error"] and "Feed keys" in body["error"]


def test_the_calendar_lane_maps_finnhub_rows_through_the_apps_own_filter(client, store, monkeypatch):
    from orderflow_system.data.finnhub_feed import Calendar, CalendarEvent
    from orderflow_system.desktop import api as desktop_api

    tc, _applied = client
    store.merge_config({"calendar": {"source": "finnhub"}, "finnhub": {"api_key": "K"}})
    now = int(time.time() * 1000)
    fake = Calendar(events=[
        CalendarEvent(category="forex", title="US CPI Release", timestamp_ms=now + 3_600_000,
                      priority=1, country="US", consensus="3.6%", previous="3.4%"),
        CalendarEvent(category="forex", title="Quiet release", timestamp_ms=now + 3_600_000,
                      priority=3, country="US"),
        CalendarEvent(category="forex", title="Next week", timestamp_ms=now + 90 * 3_600_000,
                      priority=1, country="US"),
        CalendarEvent(category="forex", title="No clock", timestamp_ms=None, priority=1, country="US"),
    ], fetched_ms=now)
    monkeypatch.setattr(desktop_api, "_finnhub_calendar", lambda category, days: fake)

    body = tc.get("/api/control/calendar?hours=48&impact=high").json()
    assert body["ok"] is True and body["lane"] == "finnhub"
    assert [row["title"] for row in body["events"]] == ["US CPI Release"]
    assert body["upcoming"] == 1 and body["total"] == 3, "the row with no clock is not a row"
    assert body["currencies"] == [{"code": "US", "count": 1}]
    assert body["events"][0]["impact"] == "high" and body["events"][0]["forecast"] == "3.6%"
    assert "Finnhub" in body["source"] and "country" in body["source"]


def test_the_calendar_lane_quotes_the_feed_when_it_fails(client, store, monkeypatch):
    from orderflow_system.data.finnhub_feed import Calendar
    from orderflow_system.desktop import api as desktop_api

    tc, _applied = client
    store.merge_config({"calendar": {"source": "finnhub"}, "finnhub": {"api_key": "K"}})
    monkeypatch.setattr(desktop_api, "_finnhub_calendar",
                        lambda category, days: Calendar(error="429 rate limited"))
    body = tc.get("/api/control/calendar").json()
    assert body["ok"] is False and "429 rate limited" in body["error"]


def test_the_key_resolution_prefers_the_settings_copy_then_the_store(store, monkeypatch):
    from orderflow_system.config import settings
    from orderflow_system.desktop import api as desktop_api

    store.save_config({"finnhub": {"api_key": "FROM-STORE"}})
    monkeypatch.setattr(settings.FINNHUB, "api_key", "", raising=False)
    assert desktop_api._finnhub_key() == "FROM-STORE"
    monkeypatch.setattr(settings.FINNHUB, "api_key", "FROM-SETTINGS", raising=False)
    assert desktop_api._finnhub_key() == "FROM-SETTINGS", "a key the engine already applied wins"


# ── the news lane ────────────────────────────────────────────────────────────────────────────

class _FakeContext:
    """A stand-in for the shared atlas context: records what the route asked it for."""

    def __init__(self) -> None:
        self.asked: dict = {}
        self._stats = {"requests": 1, "failures": 0, "last_error": "", "cached": False,
                       "feeds": ["https://www.coindesk.com/arc/outboundfeeds/rss/"]}

    async def snapshot(self, symbol, include=None, news_limit=8, feed_url=""):
        self.asked = {"symbol": symbol, "include": list(include or []), "news_limit": news_limit,
                      "feed_url": feed_url}
        return {"ok": True, "symbol": str(symbol).upper(), "ts_ms": 0,
                "news": [{"title": "an RSS headline", "link": "https://www.coindesk.com/a",
                          "published": "", "source": "coindesk.com", "published_ms": 1}],
                "stats": {}}

    def stats(self):
        return dict(self._stats)


def _finnhub_lane(client, store, monkeypatch, items, reason=""):
    """Point both modules at a fake Finnhub news read, and ask the context route."""
    from orderflow_system.atlas import api as atlas_api
    from orderflow_system.atlas import context as context_mod

    tc, _applied = client
    store.merge_config({"context": {"news_source": "finnhub"}, "finnhub": {"api_key": "K"}})
    ctx = _FakeContext()
    monkeypatch.setattr(context_mod, "shared_context", lambda: ctx)
    monkeypatch.setattr(atlas_api, "_finnhub_headlines", lambda limit: (list(items), reason))
    return tc, ctx


def test_the_news_lane_replaces_the_headline_section(client, store, monkeypatch):
    item = {"title": "Fed holds rates", "link": "https://finnhub.io/a", "published": "",
            "source": "Benzinga", "published_ms": 1}
    tc, ctx = _finnhub_lane(client, store, monkeypatch, [item])

    body = tc.get("/api/atlas/context/BTCUSDT").json()
    assert ctx.asked["include"] == ["positioning", "fear_greed"], \
        "the built-in feeds are not asked for at all when the keyed lane is chosen"
    assert [row["title"] for row in body["news"]] == ["Fed holds rates"]
    assert body["stats"]["lane"] == "finnhub" and body["stats"]["feeds"] == ["finnhub"]
    assert body["stats"]["last_error"] == ""


def test_the_news_lane_reports_the_servers_reason_when_it_has_no_headlines(client, store, monkeypatch):
    tc, _ctx = _finnhub_lane(client, store, monkeypatch, [],
                             reason="no Finnhub key — add one in Settings ▸ Feed keys")
    body = tc.get("/api/atlas/context/BTCUSDT").json()
    assert body["ok"] is True, "a missing key is not the whole context switching off"
    assert body["news"] == []
    assert body["stats"]["feeds"] == []
    assert body["stats"]["last_error"].startswith("no Finnhub key")


def test_the_feeds_lane_is_untouched_by_default(client, store, monkeypatch):
    from orderflow_system.atlas import context as context_mod

    tc, _applied = client
    ctx = _FakeContext()
    monkeypatch.setattr(context_mod, "shared_context", lambda: ctx)
    body = tc.get("/api/atlas/context/BTCUSDT").json()
    assert ctx.asked["include"] == ["positioning", "fear_greed", "news"]
    assert body["stats"]["lane"] == "feeds"
    assert [row["title"] for row in body["news"]] == ["an RSS headline"]


# ── the card and its module ──────────────────────────────────────────────────────────────────

def test_the_card_markup_and_script_tag_are_wired():
    html = (UI / "index.html").read_text(encoding="utf-8", errors="replace")
    for element in ('id="fkRows"', 'id="fkPillText"', 'id="fkCalLane"', 'id="fkNewsLane"'):
        assert element in html, element
    assert '<script src="/desktop/feedkeys.js"></script>' in html
    assert "Feed keys" in html and "Save lanes" not in html, \
        "the lanes save on change — a redundant button is a control that does nothing"


def test_the_module_calls_only_the_routes_it_should():
    js = (UI / "feedkeys.js").read_text(encoding="utf-8", errors="replace")
    for path in ("'/api/control/feedkeys'", "/api/control/calendar", "/api/options/volatility/"):
        assert path in js, path
    assert "setInterval" not in js and "setTimeout" not in js, "this card runs no timers"


def _specs_leaves(js: str) -> dict[str, set[str]]:
    """The leaves the card's input table defines, per feed (read out of the JS source)."""
    body = js.split("const SPECS = {", 1)[1].split("\n    };", 1)[0]
    out: dict[str, set[str]] = {}
    feed = ""
    for line in body.splitlines():
        group = re.match(r"\s{8}([a-z_]+): \{", line)
        if group:
            feed = group.group(1)
            out[feed] = set()
            continue
        leaf = re.match(r"\s{12}([a-z_]+): \{", line)
        if leaf and feed:
            out[feed].add(leaf.group(1))
    return out


def test_the_card_offers_exactly_the_leaves_the_route_accepts():
    from orderflow_system.desktop import api as desktop_api

    js = (UI / "feedkeys.js").read_text(encoding="utf-8", errors="replace")
    route = {name: set(leaves) for name, _label, _buys, leaves in desktop_api._FEED_KEY_BLOCKS}
    assert _specs_leaves(js) == route, \
        "a leaf the route accepts with no input row — or an input row the route drops — is a lie"


def test_every_credential_leaf_the_card_writes_is_on_the_secret_list():
    from orderflow_system.desktop import api as desktop_api

    for name, _label, _buys, leaves in desktop_api._FEED_KEY_BLOCKS:
        for leaf in leaves:
            if leaf in ("key_id", "secret", "api_key"):
                assert f"{name}.{leaf}" in config_store.SECRET_PATHS, (name, leaf)


# ── the store keeps what the card writes ─────────────────────────────────────────────────────

def test_the_store_keeps_what_the_card_writes_at_the_bounds_it_prints(store):
    clean = store.save_config({
        "tradier": {"key_id": "K", "secret": "S", "chain_width": 12, "sandbox": True},
        "marketdata": {"api_key": "M"},
        "finnhub": {"api_key": "F", "calendar_category": "crypto", "calendar_days": 5,
                    "news_category": "economic"},
        "calendar": {"source": "finnhub"},
        "context": {"news_source": "finnhub"},
    })
    assert clean["tradier"]["chain_width"] == 12 and clean["tradier"]["sandbox"] is True
    assert clean["finnhub"]["calendar_category"] == "crypto"
    assert clean["finnhub"]["news_category"] == "economic" and clean["finnhub"]["calendar_days"] == 5
    assert clean["calendar"]["source"] == "finnhub" and clean["context"]["news_source"] == "finnhub"

    # the clamps and choices the card prints are the store's own
    assert store.save_config({"tradier": {"chain_width": 99}})["tradier"]["chain_width"] == 20
    assert store.save_config({"tradier": {"chain_width": 0}})["tradier"]["chain_width"] == 1
    assert store.save_config({"finnhub": {"calendar_days": 0}})["finnhub"]["calendar_days"] == 1
    assert store.save_config({"finnhub": {"calendar_days": 99}})["finnhub"]["calendar_days"] == 30
    assert store.save_config({"finnhub": {"calendar_category": "bogus"}})["finnhub"]["calendar_category"] == "all"
    assert store.save_config({"finnhub": {"news_category": "bogus"}})["finnhub"]["news_category"] == "general"
    assert store.save_config({"calendar": {"source": "bogus"}})["calendar"]["source"] == "builtin"
    assert store.save_config({"context": {"news_source": "bogus"}})["context"]["news_source"] == "feeds"
