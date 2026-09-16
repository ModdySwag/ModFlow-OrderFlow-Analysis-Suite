"""The Fundamentals panel (desktop/ui/fundamentals.js + desktop/edgar.py) — filings, or crypto.

The claim this gate is about: for the instrument the app is showing, the panel shows the numbers the
sources actually publish — SEC EDGAR's annual filing facts for a US ticker, CoinGecko's rank / market
cap / supply / 24 h for a crypto major — or it says which of the reasons it is, in the server's own
words, and a keyless endpoint that 403s, times out or has never heard of the symbol produces a
sentence rather than an exception.

What is pinned here, against small captures taken from the real endpoints (testdata/fundamentals/):

* the symbol → source decision (venue symbol → CoinGecko id; ticker → CIK; neither → 'none');
* the companyfacts reduction — annual report forms only, real year lengths, the newest period first,
  a restated comparative replacing the earlier value, a restated/renamed tag resolved through its
  fallback, and a concept the filer does not tag contributing no row at all (never a zero);
* the same reduction in JavaScript, run in Node against the same fixture and compared row for row,
  so the two implementations of one rule cannot drift;
* the declared User-Agent (regex + the value that actually leaves the machine) and the fact that a
  403 from sec.gov is reported, not raised;
* the route: declared on the module's own router, discoverable by scripts/audit_ui_refs.py, and
  answering the documented JSON shape end to end;
* the invariants: no browser storage, no engine control verb, no data stream, and a companyfacts
  document that never reaches the browser.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_fundamentals.py -q
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = Path(__file__).parent
UI = PKG / "desktop" / "ui"
PANEL = UI / "fundamentals.js"
SELFTEST = UI / "fundamentals.selftest.js"
MODULE = PKG / "desktop" / "edgar.py"
AUDIT = ROOT / "scripts" / "audit_ui_refs.py"
FIXTURES = PKG / "testdata" / "fundamentals"
TICKERS_FIX = FIXTURES / "company_tickers.sample.json"
FACTS_FIX = FIXTURES / "companyfacts.AAPL.sample.json"
CRYPTO_FIX = FIXTURES / "coingecko.markets.sample.json"

#: The sentence the panel and the server owe an instrument neither source covers (indices, FX,
#: metals, non-US issuers). One wording, checked on both sides.
NO_SOURCE = ("no fundamentals source for {symbol} — EDGAR covers US filings, "
             "CoinGecko covers crypto")

#: The names the module publishes on window.OFAPFUNDAMENTALS — its documented surface.
SURFACE = (
    "VERSION", "VIEW", "URL_BASE", "REFRESH_MS", "TICK_MS", "DASH", "ANNUAL_FORMS", "HEADLINES",
    "CRYPTO_IDS", "NO_SOURCE",
    "esc", "normalize", "cryptoAsset", "sourceOf", "sourceLabel", "noSourceNote",
    "num", "daysBetween", "unitsOf", "candidatesFor", "reduceFacts", "normalizeRows", "rowsOf",
    "conceptsOf", "pickedRows", "pickConcept", "full", "compact", "valueText", "usd", "pct",
    "periodLabel", "rowTitle", "rowHtml", "tableHtml", "cryptoHtml", "sourceLine", "subText",
    "plan", "paint", "refresh", "onPayload", "startPoll", "stopPoll", "sync", "tick", "wire",
    "watch", "urlFor", "activeSymbol", "state", "poll", "pick",
)

#: The <section> markup that has to go into index.html. It is NOT applied here: another workstream
#: owns index.html while this panel is being built, so the module is delivered with its wiring and
#: this constant is the copy the ids in the module are checked against.
SECTION_MARKUP = '''            <section class="view" data-view="fundamentals">
                <div class="view-head"><div class="view-title">Fundamentals</div>
                    <div class="view-sub" id="fundamentalsSub">filed numbers for the active instrument — SEC EDGAR for US filers, CoinGecko for crypto</div></div>
                <div class="card"><div class="card-head">
                    <span class="card-title" id="fundamentalsSymbol">—</span><div class="spacer"></div>
                    <span class="dim" id="fundamentalsCount">0</span>
                    <select id="fundamentalsConcept" title="Which headline concept to read the annual filing facts for"></select>
                    <button class="btn small" id="fundamentalsRefresh">Refresh</button></div>
                    <div class="card-body" style="padding:0"><div class="log-list" id="fundamentalsBody"><div class="dim">Loading…</div></div></div>
                </div>
            </section>'''


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _fixture(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_module():
    """The audit script itself, so the route table is discovered by one piece of code, not two."""
    spec = importlib.util.spec_from_file_location("audit_ui_refs_for_fundamentals", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Stub:
    """A network stand-in: the captured fixtures, and a record of every call that was made."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.error = error

    def __call__(self, url: str, user_agent: str, timeout_s: float):
        self.calls.append({"url": url, "user_agent": user_agent, "timeout_s": timeout_s})
        if self.error is not None:
            raise self.error
        if "company_tickers" in url:
            return _fixture(TICKERS_FIX)
        if "companyfacts" in url:
            return _fixture(FACTS_FIX)
        if "coins/markets" in url:
            return _fixture(CRYPTO_FIX)
        raise AssertionError("unexpected URL: " + url)

    @property
    def urls(self) -> list[str]:
        return [str(call["url"]) for call in self.calls]


def _service(stub: _Stub, clock=None, **kw):
    from orderflow_system.desktop import edgar
    return edgar.FundamentalsService(fetch=stub, clock=clock or (lambda: 1000.0),
                                     sleep=lambda _s: None, **kw)


# ──────────────────────────────────────────────────────────────
# Files, syntax, selftest
# ──────────────────────────────────────────────────────────────

def test_the_fundamentals_files_exist():
    for path in (MODULE, PANEL, SELFTEST, TICKERS_FIX, FACTS_FIX, CRYPTO_FIX):
        assert path.is_file(), f"{path.name} is missing"


def test_the_captured_fixtures_are_small():
    """The panel's fixtures are trimmed captures, not multi-megabyte dumps: Apple's raw companyfacts
    is ~3.8 MB and must never be committed as a test fixture."""
    for path in (TICKERS_FIX, FACTS_FIX, CRYPTO_FIX):
        size = path.stat().st_size
        assert size < 64_000, f"{path.name} is {size} bytes — trim the capture"
        assert size > 200, f"{path.name} looks empty"


def test_the_captured_fixtures_are_the_real_thing():
    """Field names and shapes verbatim from the endpoints, so the parsers are pinned to reality."""
    facts = _fixture(FACTS_FIX)
    assert facts["entityName"] == "Apple Inc." and facts["cik"] == 320193
    gaap = facts["facts"]["us-gaap"]
    revenue = gaap["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    head = [row for row in revenue if row["end"] == "2025-09-27" and row["form"] == "10-K"][0]
    assert head["val"] == 416161000000 and head["filed"] == "2025-10-31" and head["fy"] == 2025
    assert gaap["EarningsPerShareDiluted"]["units"]["USD/shares"][0]["val"] == 7.46
    tickers = _fixture(TICKERS_FIX)
    by_ticker = {row["ticker"]: row for row in tickers.values()}
    assert by_ticker["AAPL"]["cik_str"] == 320193 and by_ticker["AAPL"]["title"] == "Apple Inc."
    markets = _fixture(CRYPTO_FIX)
    assert [row["id"] for row in markets] == ["bitcoin", "ethereum", "solana"]
    assert markets[0]["market_cap_rank"] == 1 and markets[0]["symbol"] == "btc"


def test_the_panel_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(PANEL)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_panel_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=180,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"fundamentals selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 10, f"the self-test shrank to {ok} checks — expected the source, row and state coverage"
    assert proc.returncode == 0


def test_the_panel_exposes_the_documented_surface():
    src = _read(PANEL)
    assert "window.OFAPFUNDAMENTALS" in src
    for name in SURFACE:
        assert name in src, f"fundamentals.js must expose {name}"


# ──────────────────────────────────────────────────────────────
# The Python layer, against the captured fixtures, with the network stubbed
# ──────────────────────────────────────────────────────────────

def test_the_symbol_to_source_decision():
    from orderflow_system.desktop import edgar
    assert edgar.crypto_asset("BTCUSDT") == "bitcoin"
    assert edgar.crypto_asset(" btcusdt ") == "bitcoin"
    assert edgar.crypto_asset("BTC") == "bitcoin"
    assert edgar.crypto_asset("ethusdc") == "ethereum"
    assert edgar.crypto_asset("SOL") == "solana"
    assert edgar.crypto_asset("TONUSDT") == "the-open-network"
    assert edgar.crypto_asset("POLUSDT") == "polygon-ecosystem-token"
    for not_a_coin in ("NAS100USDT", "XAUUSDT", "EURUSD", "USDT", "", None, "AAPL"):
        assert edgar.crypto_asset(not_a_coin) == "", not_a_coin
    assert edgar.normalize_symbol(" aapl ") == "AAPL"


def test_every_crypto_major_the_suite_can_stream_has_a_coin_id():
    """The panel must not be empty for the suite's own crypto universe: each CRYPTO_MAJORS symbol
    has to map. The ids themselves were verified live (see the module's CRYPTO_IDS note)."""
    from orderflow_system.config.settings import CRYPTO_MAJORS
    from orderflow_system.desktop import edgar
    missing = [symbol for symbol in ("BTCUSDT", *CRYPTO_MAJORS)
               if not edgar.crypto_asset(symbol)]
    assert not missing, f"no CoinGecko id for {missing} — the panel would be empty for them"


def test_the_ticker_map_becomes_a_padded_cik():
    from orderflow_system.desktop import edgar
    stub = _Stub()
    service = _service(stub)
    table = service.ticker_map()
    assert edgar.cik_for(table, "AAPL") == "0000320193"
    assert edgar.cik_for(table, "aapl") == "0000320193"
    assert table["AAPL"]["title"] == "Apple Inc."
    assert edgar.cik_for(table, "NOSUCH") == ""
    # a class share is spelled both ways in the wild; the same issuer is the same filing
    assert edgar.cik_for({"BRK-B": {"cik": "0001067983", "title": "BERKSHIRE"}}, "BRK.B") == "0001067983"
    assert stub.urls == [edgar.TICKERS_URL], "the map is read once — the rest is the cache"


def test_the_reduction_reads_the_fixture_the_way_the_filings_are_written():
    from orderflow_system.desktop import edgar
    rows = edgar.reduce_company_facts(_fixture(FACTS_FIX))
    assert len(rows) == 19
    assert [row["concept"] for row in rows] == (
        ["revenue"] * 4 + ["net_income"] * 3 + ["eps_diluted"] * 3 + ["gross_profit"] * 3
        + ["assets"] * 3 + ["equity"] * 3)
    head = rows[0]
    assert head["label"] == "Revenue"
    assert head["tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax", \
        "the primary Revenues tag stops at FY2018 — the fallback carries today's number"
    assert head["value"] == 416161000000
    assert (head["form"], head["filed"], head["period"], head["fy"]) == \
        ("10-K", "2025-10-31", "2025-09-27", 2025)
    assert head["latest"] is True and head["unit"] == "USD"
    assert rows[1]["latest"] is False, "only the newest period of a concept is the latest one"
    assert [row["value"] for row in rows if row["concept"] == "eps_diluted"] == [7.46, 6.08, 6.13]
    assert all(row["unit"] == "USD/shares" for row in rows if row["concept"] == "eps_diluted")
    assert all(row["form"] in edgar.ANNUAL_FORMS for row in rows), "annual report forms only"


def test_a_quarter_and_a_restatement_never_become_a_row():
    from orderflow_system.desktop import edgar
    rows = edgar.reduce_company_facts(_fixture(FACTS_FIX))
    values = {row["value"] for row in rows}
    # 10-Q facts in the capture: a nine-month and a three-month figure, plus a balance-sheet instant
    for quarter in (364357000000, 109417000000, 101464000000, 29789000000,
                    178782000000, 54770000000, 383266000000):
        assert quarter not in values, f"a 10-Q value leaked into the rows: {quarter}"
    # the old Revenues tag carries 90-day periods filed with fp "FY": a quarter by any label
    assert 62900000000 not in values and 53265000000 not in values
    # 2024-09-28 revenue appears in the FY2024 and the FY2025 10-K; one row, the later filing
    restated = [row for row in rows if row["concept"] == "revenue" and row["period"] == "2024-09-28"]
    assert len(restated) == 1 and restated[0]["filed"] == "2025-10-31"


def test_a_missing_concept_is_a_missing_row_and_a_real_zero_is_a_row():
    from orderflow_system.desktop import edgar
    doc = _fixture(FACTS_FIX)
    del doc["facts"]["us-gaap"]["GrossProfit"]                     # banks do not tag it
    rows = edgar.reduce_company_facts(doc)
    assert len(rows) == 16
    assert not [row for row in rows if row["concept"] == "gross_profit"]
    zeroed = _fixture(FACTS_FIX)
    zeroed["facts"]["us-gaap"]["GrossProfit"]["units"]["USD"].append(
        {"end": "2022-09-24", "start": "2021-09-26", "val": 0, "fy": 2022, "fp": "FY",
         "form": "10-K", "filed": "2022-10-28"})
    gross = [row for row in edgar.reduce_company_facts(zeroed) if row["concept"] == "gross_profit"]
    assert len(gross) == 4 and gross[-1]["value"] == 0, "a filed zero is data, not a gap"
    # a document that is not a document must not throw
    for nonsense in (None, {}, {"facts": {}}, {"facts": {"us-gaap": {"Assets": {}}}},
                     {"facts": {"us-gaap": {"Assets": {"units": {"USD": "nope"}}}}}):
        assert edgar.reduce_company_facts(nonsense) == []


def test_the_edgar_payload_is_reduced_before_it_reaches_the_browser():
    from orderflow_system.desktop import edgar
    stub = _Stub()
    payload = _service(stub).payload("aapl")
    assert payload["ok"] is True and payload["source"] == "edgar"
    assert payload["symbol"] == "AAPL"
    assert payload["company"] == {"cik": "0000320193", "ticker": "AAPL", "name": "Apple Inc."}
    assert len(payload["rows"]) == 19
    assert payload["rows"][0]["value"] == 416161000000
    text = json.dumps(payload)
    assert "us-gaap" not in text and '"facts"' not in text, \
        "the companyfacts document itself must never be handed to the browser"
    assert len(text) < 12000, f"the payload is {len(text)} bytes — send the rows, not the file"
    assert stub.urls == [edgar.TICKERS_URL,
                         "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"], \
        "the CIK in the URL is the zero-padded one EDGAR requires"


def test_the_crypto_payload_is_the_coingecko_block():
    stub = _Stub()
    payload = _service(stub).payload("btcusdt")
    assert payload["ok"] is True and payload["source"] == "coingecko"
    assert payload["rows"] == [], "crypto has no filings — the panel must not invent rows"
    crypto = payload["crypto"]
    assert crypto["id"] == "bitcoin" and crypto["name"] == "Bitcoin" and crypto["ticker"] == "BTC"
    assert crypto["rank"] == 1
    assert crypto["market_cap"] == 1544774036544
    assert crypto["price"] == 76915
    assert crypto["circulating_supply"] == 20084731.0 and crypto["max_supply"] == 21000000.0
    assert crypto["change_24h"] == pytest.approx(-1.08356)
    assert crypto["as_of"].startswith("2026-09-15")
    assert "ids=bitcoin" in stub.urls[0], "the coin id, not the venue symbol, is what is asked for"
    # ethereum and solana come back through the same path
    assert _service(_Stub()).payload("SOLUSDT")["crypto"]["rank"] == 7


def test_an_instrument_neither_source_covers_gets_the_sentence():
    stub = _Stub()
    service = _service(stub)
    for symbol in ("SPX", "EURUSD", "XAUUSDT", "NAS100USDT", "NOSUCHTICKER"):
        payload = service.payload(symbol)
        assert payload["ok"] is True, symbol
        assert payload["source"] == "none", symbol
        assert payload["rows"] == []
        assert payload["note"] == NO_SOURCE.format(symbol=symbol.upper()), payload["note"]
    assert "companyfacts" not in " ".join(stub.urls), \
        "the map answers that one — no filer is fetched for a symbol the SEC does not list"


def test_no_symbol_is_an_error_the_panel_can_print():
    payload = _service(_Stub()).payload("")
    assert payload["ok"] is False and payload["source"] == "none"
    assert payload["error"] and "instrument" in payload["error"]
    assert _service(_Stub()).payload(None)["ok"] is False


# ──────────────────────────────────────────────────────────────
# Failure paths: reported, never raised
# ──────────────────────────────────────────────────────────────

def test_a_403_is_reported_with_the_reason_and_without_raising():
    from orderflow_system.desktop import edgar
    stub = _Stub(error=edgar.FetchError(
        "HTTP 403 Forbidden from www.sec.gov — SEC EDGAR refuses a request whose User-Agent does "
        "not name an application and a contact"))
    payload = _service(stub).payload("AAPL")
    assert payload["ok"] is False
    assert payload["error"].startswith("HTTP 403") and "User-Agent" in payload["error"]
    assert payload["rows"] == []


def test_a_dead_network_is_a_sentence_too():
    from orderflow_system.desktop import edgar
    payload = _service(_Stub(error=edgar.FetchError("data.sec.gov did not answer: timed out"))).payload("AAPL")
    assert payload["ok"] is False and "timed out" in payload["error"]
    payload = _service(_Stub(error=RuntimeError("something unforeseen"))).payload("BTCUSDT")
    assert payload["ok"] is False and "RuntimeError" in payload["error"]
    # CoinGecko answering with an empty list is its own readable failure, not an empty block
    class _EmptyCrypto(_Stub):
        def __call__(self, url, user_agent, timeout_s):
            self.calls.append({"url": url, "user_agent": user_agent, "timeout_s": timeout_s})
            return []
    payload = _service(_EmptyCrypto()).payload("BTCUSDT")
    assert payload["ok"] is False and "no row" in payload["error"]


def test_http_json_turns_a_real_http_error_into_a_clean_message(monkeypatch):
    """The transport itself: an HTTPError from urllib becomes a FetchError naming the host, and a
    403 on sec.gov names the User-Agent rule (that is the fix the operator needs)."""
    from orderflow_system.desktop import edgar

    def refuse(url, timeout=None, headers=None, **kw):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(edgar.urllib.request, "urlopen", refuse)
    with pytest.raises(edgar.FetchError) as caught:
        edgar.http_json("https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json")
    assert "403" in str(caught.value) and "User-Agent" in str(caught.value)
    assert "data.sec.gov" in str(caught.value)
    # a 404 is not the UA's fault and must not claim to be
    def missing(url, timeout=None, **kw):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr(edgar.urllib.request, "urlopen", missing)
    with pytest.raises(edgar.FetchError) as caught404:
        edgar.http_json("https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json")
    assert "404" in str(caught404.value) and "User-Agent" not in str(caught404.value)

    def dead(url, timeout=None, **kw):
        raise urllib.error.URLError("getaddrinfo failed")
    monkeypatch.setattr(edgar.urllib.request, "urlopen", dead)
    with pytest.raises(edgar.FetchError) as caught_dead:
        edgar.http_json("https://www.sec.gov/files/company_tickers.json")
    assert "did not answer" in str(caught_dead.value)


def test_the_whole_chain_from_urlopen_to_payload_reports_instead_of_raising(monkeypatch):
    """The service with the real transport (no stub fetch) and a refusing socket: the panel gets
    ok: False and the sentence, which is what an offline machine looks like."""
    from orderflow_system.desktop import edgar

    def refuse(url, timeout=None, **kw):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(edgar.urllib.request, "urlopen", refuse)
    payload = edgar.FundamentalsService(clock=lambda: 1000.0,
                                        sleep=lambda _s: None).payload("AAPL")
    assert payload["ok"] is False and "403" in payload["error"]
    assert payload["source"] == "none" and payload["rows"] == []


# ──────────────────────────────────────────────────────────────
# The declared User-Agent, the cache and the request spacing
# ──────────────────────────────────────────────────────────────

def test_the_declared_user_agent_names_the_app_and_a_contact():
    """sec.gov answers 403 to anything that does not name an application and a contact — verified
    from this machine with both a good and a sloppy UA, so the constant is not decoration."""
    from orderflow_system.desktop import edgar
    agent = edgar.USER_AGENT
    assert re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]+/[0-9]+\.[0-9]+ \([^)]*@[^)]*\)$", agent), agent
    assert _read(MODULE).count("USER_AGENT = ") == 1, "one constant, one place to change it"
    assert "@" in agent and len(agent) < 120


def test_every_request_carries_that_user_agent():
    from orderflow_system.desktop import edgar
    stub = _Stub()
    service = _service(stub)
    service.payload("AAPL")
    service.payload("BTCUSDT")
    assert stub.calls, "nothing was requested"
    assert {call["user_agent"] for call in stub.calls} == {edgar.USER_AGENT}
    assert all(call["timeout_s"] and call["timeout_s"] > 0 for call in stub.calls)


def test_answers_are_cached_and_the_spacing_is_polite():
    from orderflow_system.desktop import edgar

    class _Clock:
        def __init__(self) -> None:
            self.now = 5000.0

        def __call__(self) -> float:
            return self.now

    clock = _Clock()
    stub = _Stub()
    # distinct TTLs here so the test can tell the session-long map from the hours-long facts
    service = _service(stub, clock=clock, ttl_facts_s=60.0, ttl_tickers_s=100000.0)
    service.payload("AAPL")
    assert len(stub.calls) == 2, "the ticker map and the filer's facts: two requests, no more"
    service.payload("AAPL")
    service.payload("AAPL")
    assert len(stub.calls) == 2, "a cached answer costs nothing — filings move slowly"
    assert service.counters["cache_hits"] >= 2
    clock.now += 61.0
    service.payload("AAPL")
    assert len(stub.calls) == 3, "past the TTL the facts are re-read"
    assert "company_tickers" not in stub.urls[2], \
        "the ticker map is kept for the session, the facts for the TTL"
    assert edgar.MIN_INTERVAL_S >= 0.1, "EDGAR allows 10 requests/second; stay well under it"
    assert edgar.TTL_FACTS_S >= 3600, "hours, not seconds: a filer's facts change quarterly"
    assert edgar.TTL_TICKERS_S >= 3600
    # the spacing itself: two real requests in the same instant are separated
    waited: list[float] = []
    from orderflow_system.desktop import edgar as _edgar
    spaced = _edgar.FundamentalsService(fetch=lambda url, ua, timeout_s: {"ok": True},
                                        clock=clock, sleep=waited.append)
    spaced._get_json("https://example.invalid/a")
    spaced._get_json("https://example.invalid/b")
    assert waited and 0 < waited[0] <= _edgar.MIN_INTERVAL_S + 0.01, waited


# ──────────────────────────────────────────────────────────────
# The route
# ──────────────────────────────────────────────────────────────

def test_the_route_is_declared_on_the_modules_own_router():
    from orderflow_system.desktop import edgar
    assert [route.path for route in edgar.router.routes] == ["/api/fundamentals/{symbol}"]
    src = _read(MODULE)
    assert 'APIRouter(prefix="/api/fundamentals"' in src
    assert '@router.get("/{symbol}")' in src, "the decorator shape the UI audit's regex reads"
    assert "asyncio.to_thread" in src, "blocking fetches run off the event loop"


def test_the_route_answers_the_documented_shape_end_to_end(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from orderflow_system.desktop import edgar

    monkeypatch.setattr(edgar, "SERVICE", _service(_Stub()))
    app = FastAPI()
    app.include_router(edgar.router)
    client = TestClient(app)

    response = client.get("/api/fundamentals/AAPL")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"ok", "symbol", "source", "company", "rows"}
    assert payload["source"] == "edgar"
    row = payload["rows"][0]
    assert set(row) >= {"concept", "label", "value", "unit", "form", "filed", "period"}

    btc = client.get("/api/fundamentals/BTCUSDT").json()
    assert btc["source"] == "coingecko" and btc["crypto"]["rank"] == 1

    spx = client.get("/api/fundamentals/SPX").json()
    assert spx["source"] == "none" and spx["note"] == NO_SOURCE.format(symbol="SPX")


def test_the_route_is_discoverable_by_the_ui_audit():
    """The audit's own scanner, not a copy of its regex. Today the audit's route table covers
    atlas/api.py, desktop/api.py and dashboard/app.py, so the panel's route resolves only once
    desktop/edgar.py is added to that scan — the wiring note beside the nav hunk."""
    audit = _audit_module()
    found = audit.routes_from(MODULE, "/api/fundamentals")
    assert found == {"/api/fundamentals/{symbol}"}
    assert audit.normalise(list(found)[0]) == "/api/fundamentals/{param}"
    scanned_today = set()
    for rel, prefix in ((("atlas", "api.py"), "/api/atlas"), (("desktop", "api.py"), "/api/control"),
                        (("dashboard", "app.py"), "")):
        scanned_today |= audit.routes_from(PKG / rel[0] / rel[1], prefix)
    known_today = {audit.normalise(route) for route in scanned_today}
    assert "/api/fundamentals/{param}" not in known_today, \
        ("edgar.py is not in the audit's route scan yet — the JS_FILES wiring must add "
         "routes_from(.../desktop/edgar.py, '/api/fundamentals') in the same change")
    assert "/api/fundamentals/{param}" in known_today | {audit.normalise(r) for r in found}


def test_the_panel_call_site_is_visible_to_the_audit():
    """news.js keeps the path in a template no wider than the path so the audit can resolve it; this
    panel does the same, so the audit must find exactly one call and it must resolve."""
    audit = _audit_module()
    audit.JS_FILES = ["fundamentals.js"]
    paths = {call for calls in audit.js_api_paths().values() for call in calls}
    assert paths == {"/api/fundamentals/{param}"}, f"the audit sees {paths}"


# ──────────────────────────────────────────────────────────────
# One rule, two implementations: the JS reduction must agree with the Python one
# ──────────────────────────────────────────────────────────────

def test_the_javascript_reduction_matches_the_python_reduction_row_for_row():
    from orderflow_system.desktop import edgar
    script = ("const fs=require('fs');"
              f"const src=fs.readFileSync({json.dumps(str(PANEL))},'utf8');"
              "const win={};new Function('window','document','fetch',src)(win,undefined,undefined);"
              f"const doc=JSON.parse(fs.readFileSync({json.dumps(str(FACTS_FIX))},'utf8'));"
              "process.stdout.write(JSON.stringify(win.OFAPFUNDAMENTALS.reduceFacts(doc)));")
    proc = subprocess.run([_node(), "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=120,
                          cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    from_js = json.loads(proc.stdout)
    from_py = edgar.reduce_company_facts(_fixture(FACTS_FIX))
    assert len(from_js) == len(from_py) == 19
    for index, (js_row, py_row) in enumerate(zip(from_js, from_py)):
        assert js_row == py_row, f"row {index} drifted: {js_row} != {py_row}"


def _js_constants() -> dict:
    """The panel's constants, read out of Node — the other half of the one-rule check."""
    script = ("const fs=require('fs');"
              f"const src=fs.readFileSync({json.dumps(str(PANEL))},'utf8');"
              "const win={};new Function('window','document','fetch',src)(win,undefined,undefined);"
              "const F=win.OFAPFUNDAMENTALS;"
              "process.stdout.write(JSON.stringify({no_source: F.NO_SOURCE, forms: F.ANNUAL_FORMS,"
              "ids: F.CRYPTO_IDS, refresh_ms: F.REFRESH_MS, tick_ms: F.TICK_MS, dash: F.DASH,"
              "headlines: F.HEADLINES.map((h)=>({key:h.key,label:h.label,unit:h.unit,kind:h.kind,"
              "tags:h.tags}))}));")
    proc = subprocess.run([_node(), "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=120,
                          cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_the_two_halves_carry_one_rule_and_one_wording():
    """The panel and the server must not drift: the same concept table, the same annual-form list,
    the same coin ids, and the same sentence for an instrument with no source at all."""
    from orderflow_system.desktop import edgar
    js = _js_constants()
    assert js["no_source"] == edgar.NO_SOURCE_NOTE, "one wording for the no-source sentence"
    assert js["forms"] == list(edgar.ANNUAL_FORMS)
    assert js["ids"] == edgar.CRYPTO_IDS, "the coin table is not a guess on either side"
    assert [h["key"] for h in js["headlines"]] == [h.key for h in edgar.HEADLINES]
    assert [h["label"] for h in js["headlines"]] == [h.label for h in edgar.HEADLINES]
    assert [h["unit"] for h in js["headlines"]] == [h.unit for h in edgar.HEADLINES]
    assert [h["kind"] for h in js["headlines"]] == [h.kind for h in edgar.HEADLINES]
    assert [tuple(h["tags"]) for h in js["headlines"]] == [h.tags for h in edgar.HEADLINES]
    assert js["refresh_ms"] >= 15000, "the panel may never poll faster than the filing clock"
    assert js["tick_ms"] >= 15000
    assert js["dash"] == "\u2014", "an absent number is an em dash on both sides"


# ──────────────────────────────────────────────────────────────
# Invariants: read-only, no storage, no engine, and the panel only drives its own markup
# ──────────────────────────────────────────────────────────────

def test_the_panel_stores_nothing_and_never_reaches_for_ingest():
    src = _read(PANEL)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource",
                      "/api/control", "engine/start", "engine/stop", "engine/restart", "ingest"):
        assert forbidden not in src, f"fundamentals.js must not touch {forbidden}"
    assert src.count("setInterval(") == 1, "one timer for the panel, guarded by the visible section"
    assert "clearInterval" not in src, "and no second timer to clear"
    assert "MutationObserver" in src and "attributeFilter: ['class']" in src
    assert "classList.contains('active')" in src, "it only works while the section is on screen"
    assert "OFAPBUS" in src, "the poll goes through the suite's own delivery layer when it is loaded"
    assert 'target="_blank"' not in src, "a fundamentals row links nowhere — there is nothing to open"


def test_the_edgar_module_never_serves_an_engine_control_verb():
    src = _read(MODULE)
    assert "/api/control" not in src, "the fundamentals router is not an engine control surface"
    for verb in ("engine/start", "engine/stop", "engine/restart", "engine\"", "ingest"):
        assert verb not in src, f"edgar.py must not mention {verb}"
    assert "POST" not in src and '"post"' not in src, "read-only: GET only"


def test_the_panel_only_drives_ids_the_wiring_hunk_carries():
    """The module is delivered before its section exists in index.html (another workstream owns that
    file), so the ids it reaches for are checked against the markup it ships with."""
    src = _read(PANEL)
    used = set(re.findall(r"el\('([A-Za-z0-9_-]+)'\)", src))
    assert used, "the module must name the elements it drives"
    declared = set(re.findall(r'id="([A-Za-z0-9_-]+)"', SECTION_MARKUP))
    assert {"fundamentalsSub", "fundamentalsCount", "fundamentalsSymbol", "fundamentalsConcept",
            "fundamentalsRefresh", "fundamentalsBody"} <= declared, "the contract's six ids"
    created_by_the_module = {"fundamentalsStyles"}   # its own <style> element, like news.js
    assert used - declared - created_by_the_module == {"symbolSelect"}, \
        f"{sorted(used - declared - created_by_the_module)} is not in the section — symbolSelect is the shell's"
    assert 'data-view="fundamentals"' in SECTION_MARKUP


def test_the_wiring_is_all_or_nothing_in_index_html():
    """Not applied yet by design. Whenever it IS applied, the script tag, the section and the nav
    item have to arrive together — a panel with no section never boots, a section with no script is
    an empty card forever."""
    html = _read(UI / "index.html")
    script = '<script src="/desktop/fundamentals.js"></script>'
    if script in html:
        assert 'data-view="fundamentals"' in html, "the script tag without its section"
        assert 'class="nav-item" data-view="fundamentals"' in html, "and without its nav item"
        assert html.index('src="/desktop/bus.js"') < html.index(script), "load after the delivery layer"
        assert html.index('src="/desktop/ui.js"') < html.index(script), "and after the controller"
    else:
        assert 'data-view="fundamentals"' not in html, "the section arrived without its script tag"
