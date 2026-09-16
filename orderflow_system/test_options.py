"""The Options panel (desktop/ui/options.js) and the Deribit feed behind it (desktop/deribit.py).

OPTIONS ARE CRYPTO-ONLY HERE, AND THIS FILE GATES THAT HONESTLY. Deribit publishes keyless, free
crypto option chains (BTC and ETH — SOL is a recognised currency with NO chain, which a live capture
in `fixtures/deribit/instruments_sol.json` records), and this suite mounts exactly two read-only
routes for it. Everything a panel could get wrong is pinned here:

  * the panel's decisions are pinned in Node (`options.selftest.js`, run from this file) against the
    REAL chain reply captured from a live sandbox — field names and value shapes verbatim;
  * the Python half is exercised against captured payloads with `get_json` stubbed out, including the
    failure path (the venue's own HTTP 400 body for an unknown instrument) and the SOL case;
  * the wiring is checked where it can break silently: the routes exist at the paths the JS calls,
    `api.py` mounts the router, the module is registered with the UI audit, and the panel never
    reaches for storage, ingest or an engine verb.

Nothing below touches the network.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from orderflow_system.desktop import deribit

ROOT = Path(__file__).resolve().parents[1]
UI = Path(__file__).parent / "desktop" / "ui"
DERIBIT = Path(__file__).parent / "desktop" / "deribit.py"
OPTIONS = UI / "options.js"
SELFTEST = UI / "options.selftest.js"
INDEX = UI / "index.html"
API = Path(__file__).parent / "desktop" / "api.py"
AUDIT = ROOT / "scripts" / "audit_ui_refs.py"
FIXTURES = Path(__file__).parent / "fixtures" / "deribit"

#: The sentence the panel must answer with for a market Deribit does not quote options on. The
#: server's refusal carries the same lead, so the two tables cannot drift in silence.
NO_COVERAGE_LEAD = "crypto only via Deribit — no options feed for "

#: The moment the payloads were captured (2026-09-15, epoch ms). Freezing `now_ms` on it keeps the
#: "nearest expiry" and "days to expiry" decisions the same for ever, instead of aging with the wall
#: clock and failing on the fixture's own expiry date.
FIXTURE_NOW = 1789478400000

#: The names options.js publishes on window.OFAPOPTIONS — its documented surface.
SURFACE = (
    "VERSION", "CHAIN_URL", "TICKER_URL", "INTERVAL_MS", "CACHE_MS", "WIDTH", "DASH",
    "esc", "num", "currencyFor", "coverageSentence", "expiriesFrom", "sideOf", "ladderFrom",
    "atmIndex", "fmtStrike", "fmtPrice", "fmtPct", "fmtGreek", "fmtDelta", "fmtSize", "clockOf",
    "cacheKey", "cacheGet", "cachePut", "cacheSize", "cacheClear", "plan", "subText", "headHtml",
    "rowHtml", "sideCells", "bodyHtml", "detailHtml", "render", "syncSelect", "state", "activeSymbol",
    "paramsNow", "urlNow", "onChain", "loadChain", "loadTicker", "getJson", "startPoll", "stopPoll",
    "sync", "rekey", "setExpiry", "rowClick", "bindControls", "injectStyles", "boot", "watch",
)

#: The names desktop/deribit.py publishes — its documented surface.
FEED_SURFACE = ("BASE", "OPTION_CURRENCIES", "CHAIN_TTL_MS", "TICKER_TTL_MS", "DEFAULT_WIDTH",
                "MAX_WIDTH", "currency_for", "get_json", "parse_instruments", "parse_ticker",
                "group_expiries", "expiry_label", "build_ladder", "instruments", "one_ticker",
                "tickers", "chain", "ticker", "stats", "reset", "TtlCache")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _audit_module():
    """The audit script itself, so the route table is discovered by one piece of code, not two."""
    spec = importlib.util.spec_from_file_location("audit_ui_refs_for_options", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _routes() -> set[str]:
    audit = _audit_module()
    routes: set[str] = set()
    routes |= audit.routes_from(ROOT / "orderflow_system" / "atlas" / "api.py", "/api/atlas")
    routes |= audit.routes_from(ROOT / "orderflow_system" / "desktop" / "api.py", "/api/control")
    routes |= audit.routes_from(ROOT / "orderflow_system" / "dashboard" / "app.py", "")
    return {re.sub(r"\{[^}]+\}", "{param}", route).rstrip("/") for route in routes}


class Venue:
    """The captured payloads, served by URL. The suite never touches the network.

    The tickers that exist as fixtures are the ones the panel's window actually shows, so the ladder
    below is built from real venue answers; every other instrument gets the venue's real refusal for
    an unknown name (HTTP 400), which is how the unquoted-cell path is exercised with real words.
    """

    BY_INSTRUMENT = {
        "BTC-16SEP26-77000-C": "ticker_77000c.json",
        "BTC-16SEP26-77000-P": "ticker_77000p.json",
        "BTC-16SEP26-68000-C": "ticker_68000c_itm.json",
        "BTC-16SEP26-77500-C": "ticker_77500c_probe.json",
        "BTC-25SEP26-80000-C": "ticker_25sep_80000c.json",
    }

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float | None = None):
        self.calls.append(url)
        if "get_instruments" in url:
            if "currency=SOL" in url:
                return _fixture("instruments_sol.json"), ""
            if "currency=BTC" in url:
                return _fixture("instruments_btc.json"), ""
            return None, "HTTP 400: Invalid params"
        name = url.split("instrument_name=")[-1].split("&")[0]
        fixture = self.BY_INSTRUMENT.get(name)
        if fixture:
            return _fixture(fixture), ""
        return None, "HTTP 400: instrument not found (instrument_name)"


@pytest.fixture(autouse=True)
def _cold_caches():
    """Every test starts with empty caches and counters, and leaves them that way."""
    deribit.reset()
    yield
    deribit.reset()


# ──────────────────────────────────────────────────────────────
# The files, and the Node half
# ──────────────────────────────────────────────────────────────

def test_the_options_files_exist():
    assert OPTIONS.is_file(), "desktop/ui/options.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/options.selftest.js is missing"
    assert DERIBIT.is_file(), "desktop/deribit.py is missing"
    assert FIXTURES.is_dir(), "the captured Deribit payloads are missing"
    for name in ("instruments_btc.json", "instruments_sol.json", "ticker_error.json",
                 "chain_btc.json", "ticker_77000c_reply.json"):
        assert (FIXTURES / name).is_file(), f"fixtures/deribit/{name} is missing"


def test_the_panel_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(OPTIONS)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_panel_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=180,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"options selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 10, f"the self-test shrank to {ok} checks — expected the parsing and state coverage"
    assert proc.returncode == 0


def test_the_panel_exposes_the_documented_surface():
    src = _read(OPTIONS)
    assert "window.OFAPOPTIONS" in src
    for name in SURFACE:
        assert name in src, f"options.js must expose {name}"
    assert "'/api/control/deribit/chain'" in src, "the chain route is stated once, in the source"
    assert "'/api/control/deribit/ticker'" in src
    assert NO_COVERAGE_LEAD in src, "the no-coverage sentence the panel must never lose"


def test_the_feed_exposes_the_documented_surface():
    src = _read(DERIBIT)
    ast.parse(src)                                          # it must be importable as written
    for name in FEED_SURFACE:
        assert name in src, f"deribit.py must expose {name}"
    assert "fastapi" not in src, \
        "the feed is a pure data module — the two routes that serve it live in desktop/api.py"


def test_the_two_routes_are_defined_where_the_audit_reads_them():
    """The audit discovers routes by their literal decorator in api.py, so that is where they go."""
    src = _read(API)
    assert '@router.get("/deribit/chain")' in src
    assert '@router.get("/deribit/ticker")' in src
    assert "deribit_mod.chain" in src and "deribit_mod.ticker" in src, \
        "both routes call the module that owns the fetching and the caching"


# ──────────────────────────────────────────────────────────────
# Wiring: the section, the script tag, the audit, the routes
# ──────────────────────────────────────────────────────────────

def test_the_panel_is_wired_into_the_shell_after_news():
    html = _read(INDEX)
    nav_news = html.index('<button class="nav-item" data-view="news"')
    nav_options = html.index('<button class="nav-item" data-view="options"')
    section_news = html.index('<section class="view" data-view="news">')
    section_options = html.index('<section class="view" data-view="options">')
    assert nav_news < nav_options, "the nav item lands after News"
    assert section_news < section_options, "and so does the section"
    assert 'src="/desktop/options.js"' in html and 'id="optionsExpiry"' in html and 'id="optionsBody"' in html
    assert html.index('src="/desktop/news.js"') < html.index('src="/desktop/options.js"'), \
        "the new script tag goes after news.js"
    assert html.index('src="/desktop/bus.js"') < html.index('src="/desktop/options.js"'), \
        "the bus defines window.OFAPBUS before the panel looks for it"
    assert html.index('src="/desktop/ui.js"') < html.index('src="/desktop/options.js"'), \
        "the panel reads S and api(), so it loads after the controller"
    assert "options.js" in _read(AUDIT), "register it in JS_FILES"


def test_the_panel_only_uses_ids_the_markup_carries():
    html = _read(INDEX)
    ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
    used = set(re.findall(r"el\('([A-Za-z0-9_-]+)'\)", _read(OPTIONS)))
    assert used, "the module must name the elements it drives"
    for element_id in sorted(used):
        assert element_id in ids, f"{element_id} is not in index.html"
    assert {"optionsSub", "optionsCount", "optionsExpiry", "optionsRefresh", "optionsBody"} <= used, \
        "the card's own controls are what the panel drives"
    assert "symbolSelect" in used, "the active symbol is read from the app's own select"


def test_the_routes_the_panel_calls_exist_and_are_mounted():
    """The paths are literals in one place in the JS; both must resolve against the real route
    table, and both must be mounted by the desktop API router the launcher hands to the app."""
    src = _read(OPTIONS)
    urls = sorted(set(re.findall(r"'(/api/[^']+)'", src)))
    assert urls, "the module must state the routes it reads"
    known = _routes()
    assert known, "the route table came back empty — the audit could not see the modules"
    for url in urls:
        assert url in known, f"{url} is not a route this app serves"
    assert sorted(u for u in urls if "deribit" in u) == \
        ["/api/control/deribit/chain", "/api/control/deribit/ticker"]

    from fastapi import FastAPI
    from orderflow_system.desktop.api import router as control_router

    mounted = {route.path for route in control_router.routes if hasattr(route, "path")}
    assert "/api/control/deribit/chain" in mounted
    assert "/api/control/deribit/ticker" in mounted
    app = FastAPI()
    app.include_router(control_router)
    params = {p.get("name") for p in app.openapi()["paths"]["/api/control/deribit/chain"]["get"]["parameters"]}
    assert params == {"symbol", "expiry", "width"}, "the chain route takes the parameters the panel sends"


def test_the_panel_never_touches_ingest_or_storage_and_never_calls_the_venue_directly():
    """CORS means the browser cannot reach Deribit at all: the panel's only source is this app."""
    src = _read(OPTIONS)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource",
                      "/api/control/engine", "engine/start", "engine/stop", "deribit.com"):
        assert forbidden not in src, f"options.js must not touch {forbidden}"
    assert src.count("setInterval(") == 1, "one timer for the panel, guarded by the visible section"
    assert "OFAPBUS" in src, "and it takes its delivery from the suite's own layer"
    assert "MutationObserver" in src and "attributeFilter: ['class']" in src
    assert "classList.contains('active')" in src, "it only works while the section is on screen"
    assert "typeof S !== 'undefined'" in src, "the active symbol is read defensively"


def test_the_feed_is_keyless_read_only_and_never_raises():
    """A public, keyless API: no credentials to leak, and no exception can escape a route."""
    src = _read(DERIBIT)
    assert '"https://www.deribit.com' in src
    for forbidden in ("api_key", "api_secret", "Authorization", "Bearer", "localStorage"):
        assert forbidden not in src, f"deribit.py must not carry {forbidden}"
    code = re.sub(r'""".*?"""', "", src, flags=re.S)          # docstrings are prose, not behaviour
    code = re.sub(r"#[^\n]*", "", code)
    assert "raise" not in code, "every failure is a dict with ok=False, never an exception"


# ──────────────────────────────────────────────────────────────
# The feed, against the captured payloads
# ──────────────────────────────────────────────────────────────

def test_the_symbol_mapper_table():
    assert deribit.currency_for("BTCUSDT") == "BTC"
    assert deribit.currency_for("btcusdt") == "BTC"
    assert deribit.currency_for("ETHUSDT") == "ETH"
    assert deribit.currency_for("ethusd") == "ETH"
    assert deribit.currency_for("SOLUSDT") == "SOL"
    assert deribit.currency_for("BTC") == "BTC"
    assert deribit.currency_for("BTC-USD") == "BTC"
    assert deribit.currency_for("BTCUSDC") == "BTC"
    for symbol in ("ESZ6", "EURUSD", "NAS100USDT", "SPX500", "AAPL", "", "   ", None):
        assert deribit.currency_for(symbol) is None, f"{symbol!r} has no Deribit chain"


def test_the_chain_is_built_from_the_captured_instruments_and_tickers(monkeypatch):
    venue = Venue()
    monkeypatch.setattr(deribit, "get_json", venue)
    monkeypatch.setattr(deribit, "now_ms", lambda: FIXTURE_NOW)

    out = deribit.chain("BTCUSDT")
    assert out["ok"] is True, out
    assert out["source"] == "deribit" and out["currency"] == "BTC"
    assert out["expiry"] == "16SEP26", "the nearest expiry is drawn by default"
    assert out["cached"] is False
    assert [entry["code"] for entry in out["expiries"]] == \
        ["16SEP26", "17SEP26", "25SEP26", "30OCT26", "25JUN27"]
    assert out["expiries"][0]["label"] == "16 Sep 2026"
    assert out["expiries"][0]["strikes"] == 26 and out["expiries"][0]["calls"] == 26
    assert out["strikes_total"] == 26, "the fixture carries the whole 16SEP26 strike set"
    assert len(out["strikes"]) == 21, "and the ladder windows it: +/-10 strikes"
    assert out["forward"] == pytest.approx(76793.63), "the probe ticker's own forward"
    assert out["forward_from_ticker"] is True
    # The venue's spacing is not uniform (500 near the money, 1000 far out) — the window shows both.
    assert [int(entry["strike"]) for entry in out["strikes"]] == [
        70000, 71000, 72000, 73000, 74000, 74500, 75000, 75500, 76000, 76500, 77000,
        77500, 78000, 78500, 79000, 79500, 80000, 80500, 81000, 82000, 83000]

    row = next(entry for entry in out["strikes"] if entry["strike"] == 77000)
    assert row["call"]["instrument"] == "BTC-16SEP26-77000-C"
    assert row["call"]["iv"] == 53.78 and row["call"]["delta"] == 0.48952
    assert row["call"]["oi"] == 287.8 and row["call"]["volume"] == 293.1
    assert row["put"]["instrument"] == "BTC-16SEP26-77000-P" and row["put"]["delta"] == -0.51184


def test_every_cell_the_venue_did_not_quote_is_counted_not_invented(monkeypatch):
    """The window is 21 rows (42 sides) and the fixtures hold three of those tickers: the rest must
    come back empty and counted, never as a zero."""
    venue = Venue()
    monkeypatch.setattr(deribit, "get_json", venue)
    monkeypatch.setattr(deribit, "now_ms", lambda: FIXTURE_NOW)

    out = deribit.chain("BTCUSDT")
    assert out["quoted_sides"] == 3
    assert out["ticker_errors"] == 39
    assert out["tickers"] == 41, "the probe was already cached, so 41 of the 42 were read"
    quoted = [entry for entry in out["strikes"] if entry["call"] or entry["put"]]
    assert [int(entry["strike"]) for entry in quoted] == [77000, 77500]
    empty = next(entry for entry in out["strikes"] if entry["strike"] == 70000)
    assert empty["call"] is None and empty["put"] is None
    assert "39 failed" in out["note"]
    sample = out["ticker_error_sample"]
    assert sample and "instrument not found" in sample[0], sample
    assert any("instrument not found" in note for note in deribit.stats()["requests"]["recent_errors"]), \
        "the venue's own refusal is kept, so a dead row has a reason"


def test_the_chain_honours_the_expiry_it_was_asked_for(monkeypatch):
    monkeypatch.setattr(deribit, "get_json", Venue())
    monkeypatch.setattr(deribit, "now_ms", lambda: FIXTURE_NOW)
    # The trimmed fixture keeps one strike of the 25SEP26 series (80000, both sides) and all 27 of
    # 17SEP26 — enough to pin both the honoured pick and the probe-failure fallback.
    out = deribit.chain("BTCUSDT", "25SEP26")
    assert out["ok"] is True
    assert out["expiry"] == "25SEP26" and out["expiry_instrument"] == "BTC-25SEP26"
    assert out["strikes_total"] == 1 and len(out["strikes"]) == 1
    row = out["strikes"][0]
    assert row["strike"] == 80000.0
    assert row["call"]["instrument"] == "BTC-25SEP26-80000-C" and row["call"]["oi"] == 7121.0
    assert out["forward"] == pytest.approx(77004.3), "the probe ticker's own forward"
    assert out["forward_from_ticker"] is True
    assert out["quoted_sides"] == 1, "only its call has a fixture ticker"
    assert out["ticker_errors"] == 1, "its put was refused by the venue, and stays empty"
    out2 = deribit.chain("BTCUSDT", "BTC-25SEP26")
    assert out2["expiry"] == "25SEP26", "the series name is accepted too"
    assert deribit.chain("BTCUSDT", "99XXX99")["expiry"] == "16SEP26", "an unknown pick falls back"

    # 17SEP26 has no fixture ticker at all, so the forward probe fails — the ladder must still be
    # drawn (windowed on the middle strike), say so, and count every unquoted cell.
    fallback = deribit.chain("BTCUSDT", "17SEP26")
    assert fallback["ok"] is True and fallback["expiry"] == "17SEP26"
    assert fallback["forward_from_ticker"] is False
    assert len(fallback["strikes"]) == 21 and fallback["quoted_sides"] == 0
    assert fallback["ticker_errors"] == 42
    assert "probe" in fallback["note"] and "fell back" in fallback["note"]


def test_the_ttl_cache_serves_a_second_read_without_touching_the_venue(monkeypatch):
    venue = Venue()
    monkeypatch.setattr(deribit, "get_json", venue)
    monkeypatch.setattr(deribit, "now_ms", lambda: FIXTURE_NOW)

    first = deribit.chain("BTCUSDT")
    calls = len(venue.calls)
    assert first["cached"] is False and calls >= 40, f"{calls} calls for one chain"
    second = deribit.chain("BTCUSDT")
    assert second["cached"] is True
    # The instrument list and the three quoted tickers come from the cache; only the 39 the venue
    # refused are asked again — a failure is never cached as if it were an answer.
    assert len(venue.calls) - calls == 39, [u for u in venue.calls[calls:]][:2]
    assert second["strikes"] == first["strikes"]
    assert deribit.stats()["ticker_cache"]["hits"] >= 3
    assert deribit.stats()["instruments_cache"]["hits"] == 1

    deribit.reset()
    third = deribit.chain("BTCUSDT")
    assert third["cached"] is False
    assert len(venue.calls) > calls + 39, "after a reset it reads again"


def test_one_ticker_is_parsed_with_its_greeks():
    row, error = deribit.parse_ticker(_fixture("ticker_77000c.json"))
    assert error == ""
    assert row["instrument"] == "BTC-16SEP26-77000-C"
    assert row["bid"] == 0.009 and row["ask"] == 0.01 and row["mid"] == 0.0095
    assert row["iv"] == 53.78 and row["delta"] == 0.48952 and row["theta"] == -380.4349
    assert row["oi"] == 287.8 and row["volume"] == 293.1 and row["underlying"] == 76926.19

    itm, _ = deribit.parse_ticker(_fixture("ticker_68000c_itm.json"))
    assert itm["last"] is None, "a field the venue sent as null stays null (the panel shows a dash)"
    assert itm["mark"] == 0.1161 and itm["gamma"] == 0.0 and itm["underlying"] == 76926.19

    assert deribit.parse_ticker({"result": []}) == (None, "the ticker reply carried no result")
    assert deribit.parse_ticker({"result": {"best_bid_price": 1}})[0] is None
    assert deribit.parse_ticker(None)[0] is None
    assert deribit._number("nan") is None and deribit._number(float("inf")) is None
    assert deribit._number("0.5") == 0.5 and deribit._number(None) is None


def test_the_ticker_route_reply_is_the_shape_the_panel_parses(monkeypatch):
    """The panel reads flattened fields (`mark`, `iv`, `delta`, ...). If that shape moves, the panel
    renders dashes with no error anywhere — so the shape itself is the gate."""
    monkeypatch.setattr(deribit, "get_json", Venue())
    reply = deribit.ticker("BTC-16SEP26-77000-C")
    assert reply["ok"] is True and reply["cached"] is False
    expected = {"instrument", "bid", "ask", "mid", "mark", "iv", "bid_iv", "ask_iv", "oi", "volume",
                "volume_usd", "underlying", "index", "delta", "gamma", "theta", "vega", "rho", "ts",
                "state", "expiry_instrument", "source", "at", "requests"}
    assert expected <= set(reply), sorted(set(reply))
    assert set(_fixture("ticker_77000c_reply.json")) <= set(reply), \
        "the JS fixture is this same shape — a captured reply"


def test_a_refused_instrument_returns_the_venues_own_words(monkeypatch):
    """The captured HTTP 400 body, replayed through the real fetch path."""
    captured = _fixture("ticker_error.json")                # {"status": 400, "body": {...}}
    assert captured["status"] == 400
    raw = json.dumps(captured["body"]).encode("utf-8")

    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(raw))

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert deribit._venue_reason(json.dumps(captured["body"])) == "instrument not found (instrument_name)"
    payload, error = deribit.get_json(deribit.BASE + "/ticker?instrument_name=BTC-16SEP26-99999-C")
    assert payload is None and error == "HTTP 400: instrument not found (instrument_name)"

    reply = deribit.ticker("BTC-16SEP26-99999-C")
    assert reply["ok"] is False and reply["cached"] is False
    assert "instrument not found (instrument_name)" in reply["error"]
    assert deribit.stats()["requests"]["failed"] == 2
    assert any("instrument not found" in note for note in deribit.stats()["requests"]["recent_errors"])


def test_a_dead_network_is_an_error_not_an_exception(monkeypatch):
    def offline(url, timeout=None):
        return None, "URLError: <urlopen error [Errno 11001] getaddrinfo failed>"

    monkeypatch.setattr(deribit, "get_json", offline)
    out = deribit.chain("BTCUSDT")
    assert out["ok"] is False and out["coverage"] is True
    assert "Deribit chain unavailable" in out["error"] and "getaddrinfo" in out["error"]
    reply = deribit.ticker("BTC-16SEP26-77000-C")
    assert reply["ok"] is False and "Deribit ticker unavailable" in reply["error"]
    assert deribit.ticker("")["ok"] is False, "an empty instrument is refused without a request"
    assert deribit.stats()["requests"]["ok"] == 0


def test_an_unreadable_payload_is_reported_not_guessed(monkeypatch):
    monkeypatch.setattr(deribit, "get_json", lambda url, timeout=None: ({"result": 42}, ""))
    out = deribit.chain("BTCUSDT")
    assert out["ok"] is False and "carried no list" in out["error"], out["error"]
    assert deribit.ticker("BTC-16SEP26-77000-C")["ok"] is False
    assert len(deribit.parse_instruments({"result": 42})[0]) == 0
    assert deribit.parse_instruments(None) == ([], 0)


def test_malformed_payload_items_are_skipped_and_counted():
    payload = {"result": [
        {"instrument_name": "BTC-16SEP26-77000-C", "strike": 77000.0, "option_type": "call",
         "expiration_timestamp": 1789545600000, "state": "open", "is_active": True},
        None, 42, "BTC", {},
        {"instrument_name": "BTC-16SEP26-99-C", "strike": 99},                 # no type, no expiry
        {"instrument_name": "BTC-16SEP26-77000-C", "strike": "n/a", "option_type": "call",
         "expiration_timestamp": 1789545600000},
        {"instrument_name": "BTC-16SEP26-0-C", "strike": 0, "option_type": "call",
         "expiration_timestamp": 1789545600000},
        {"instrument_name": "junk", "strike": 1.0, "option_type": "put",
         "expiration_timestamp": 1789545600000},
    ]}
    rows, skipped = deribit.parse_instruments(payload)
    assert len(rows) == 1 and skipped == 8, (len(rows), skipped)
    assert rows[0]["expiry_code"] == "16SEP26" and rows[0]["expiry_instrument"] == "BTC-16SEP26"
    assert rows[0]["strike"] == 77000.0 and rows[0]["option_type"] == "call"


def test_a_currency_with_no_chain_is_no_coverage(monkeypatch):
    """SOL is a real currency on Deribit with no option chain — the captured empty page proves it."""
    monkeypatch.setattr(deribit, "get_json", Venue())
    assert deribit.currency_for("SOLUSDT") == "SOL", "it maps — the currency exists"
    out = deribit.chain("SOLUSDT")
    assert out["ok"] is False and out["coverage"] is False and out["currency"] == "SOL"
    assert "lists no SOL options" in out["error"], out["error"]
    reply = deribit.ticker("SOL-16SEP26-100-C")
    assert reply["ok"] is False and "instrument not found" in reply["error"], reply


def test_a_symbol_with_no_deribit_currency_is_no_coverage_without_a_request(monkeypatch):
    venue = Venue()
    monkeypatch.setattr(deribit, "get_json", venue)
    for symbol in ("ESZ6", "EURUSD", "NAS100USDT", "AAPL"):
        out = deribit.chain(symbol)
        assert out["ok"] is False and out["coverage"] is False
        assert NO_COVERAGE_LEAD + symbol in out["error"], out["error"]
    assert venue.calls == [], "a market with no chain is answered without asking the venue"
    assert NO_COVERAGE_LEAD in _read(OPTIONS), "and the panel states the same sentence"


def test_the_ttl_cache_expires_on_its_own_clock():
    ticks = {"now": 1000.0}
    cache = deribit.TtlCache(ttl_ms=5000, clock=lambda: ticks["now"])
    cache.put("k", {"v": 1})
    assert cache.get("k") == {"v": 1}
    ticks["now"] += 4.999
    assert cache.get("k") == {"v": 1}, "still inside the TTL"
    ticks["now"] += 0.001
    assert cache.get("k") is None, "gone at the TTL"
    assert cache.stats()["entries"] == 0, "an expired entry is dropped, not kept"
    assert cache.stats()["ttl_ms"] == 5000
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.clear() == 2
    assert cache.get("a") is None
    assert cache.hits == 2 and cache.misses == 2


def test_expiry_grouping_and_labels():
    rows, _ = deribit.parse_instruments(_fixture("instruments_btc.json"))
    grouped = deribit.group_expiries(rows, now=1789478400000)
    codes = [entry["code"] for entry in grouped]
    assert codes == ["16SEP26", "17SEP26", "25SEP26", "30OCT26", "25JUN27"], codes
    assert [entry["ms"] for entry in grouped] == sorted(entry["ms"] for entry in grouped)
    assert grouped[0]["strikes"] == 26 and grouped[0]["calls"] == 26 and grouped[0]["puts"] == 26
    assert grouped[0]["days"] == 0 and grouped[-1]["days"] > 100
    assert deribit.expiry_label("2OCT26") == "2 Oct 2026"
    assert deribit.expiry_label("25JUN27") == "25 Jun 2027"
    assert deribit.expiry_label("nonsense") == "nonsense"


def test_the_ladder_window_is_centred_on_the_forward_not_on_spot():
    rows, _ = deribit.parse_instruments(_fixture("instruments_btc.json"))
    series = [row for row in rows if row["expiry_code"] == "16SEP26"]
    # No tickers at all: the window still lands on the middle strike, and every side stays None.
    ladder, centre = deribit.build_ladder(series, {}, None, 10)
    assert centre == 77500.0, "the middle strike of the 26 that exist"
    assert len(ladder) == 21
    assert [int(entry["strike"]) for entry in ladder] == [
        71000, 72000, 73000, 74000, 74500, 75000, 75500, 76000, 76500, 77000, 77500,
        78000, 78500, 79000, 79500, 80000, 80500, 81000, 82000, 83000, 84000]
    assert all(entry["call"] is None and entry["put"] is None for entry in ladder)
    near, centre_near = deribit.build_ladder(series, {}, 86000.0, 3)
    assert centre_near == 86000.0, "a forward near the top of the chain is not padded out"
    assert [int(entry["strike"]) for entry in near] == [83000, 84000, 85000, 86000]
    assert deribit.build_ladder([], {}, 100.0, 5) == ([], 100.0)
    assert deribit.stats()["ttl_ms"] == {"chain": deribit.CHAIN_TTL_MS, "ticker": deribit.TICKER_TTL_MS}
