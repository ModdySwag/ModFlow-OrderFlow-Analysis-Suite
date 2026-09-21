"""The companion monitor (P1-8): a read-only, mobile-first page the app already serves.

The claim this file is about: `/desktop/monitor.html` + `monitor.js` are a phone-sized window onto a
running session — alerts, the simulated account, the watchlist quotes and one order-flow read — that
(a) loads nothing from outside this origin, (b) calls only endpoints that exist, (c) issues no write
of any kind, and (d) degrades to a plain sentence in the panel it belongs to when a read fails.

What is pinned here, all of it offline (no server, no socket; the JS runs under plain `node`):

* the two files exist, are CRLF like every sibling under ``desktop/ui/``, and the page loads its
  module from this origin — no URL, font, image or script from anywhere else;
* the page is built for a phone: viewport meta, safe-area insets, a bottom tab bar, touch-sized
  controls, and the app's own dark palette;
* every ``/api/...`` literal in the module is an argument to the module's own GET helper, every one
  of them resolves to a real GET route parsed out of ``atlas/api.py`` and ``desktop/api.py``, and
  the module carries no write verb and no request options at all;
* every element id the module writes to exists in the page, every id is prefixed ``mon`` and is
  unique;
* the timer/listener ledger: exactly one ``setInterval``, handed to the app's pause registry and
  guarded on ``document.hidden`` / ``OFAP_PAUSED``, and exactly three ``addEventListener`` sites
  (the ledger numbers the parent freezes in ``test_listener_balance.py``);
* the module parses (``node --check``) and its own selftest is green;
* the documented formatting cases hold when the real module is executed under node — and every
  panel has a refusal sentence for a failed or missing read, with no leaked JS artefacts in it.

Run:  .venv/Scripts/python.exe -m pytest orderflow_system/test_monitor.py -q
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
PAGE = UI / "monitor.html"
MODULE = UI / "monitor.js"
SELFTEST = UI / "monitor.selftest.js"
ATLAS_API = ROOT / "orderflow_system" / "atlas" / "api.py"
CONTROL_API = ROOT / "orderflow_system" / "desktop" / "api.py"
LAUNCHER = ROOT / "orderflow_system" / "desktop" / "launcher.py"

DASH = "\u2014"
NOW = 1_700_000_000_000

#: The five endpoints the page is allowed to call, as the module writes them.
EXPECTED_CALLS = sorted([
    "/api/atlas/alerts", "/api/atlas/replay/paper/state", "/api/control/search/watchlist",
    "/api/atlas/scanner", "/api/atlas/market-read",
])

#: The ledger numbers the parent freezes in test_listener_balance.py / test_timer_guards.py.
LISTENERS = (3, 0)
TIMERS = 1

#: The documented formatting cases — the same ones monitor.selftest.js asserts, re-run through the
#: real module under node. (fn, args, mode, expectation); mode is value | contains | regex.
CASES: list[tuple[str, list, str, object]] = [
    ("fmtValue", [12.5], "value", "12.5"),
    ("fmtValue", [3], "value", "3"),
    ("fmtValue", ["buy"], "value", "buy"),
    ("fmtValue", [0], "value", "0"),
    ("fmtValue", [None], "value", DASH),
    ("fmtPrice", [81200], "value", "81200.00"),
    ("fmtPrice", [0.1234567], "value", "0.123457"),
    ("fmtPrice", [81200, 0], "value", "81200"),
    ("fmtPrice", [None], "value", DASH),
    ("fmtTicks", [12.34], "value", "+12.3"),
    ("fmtTicks", [-3], "value", "-3.0"),
    ("fmtTicks", [0], "value", "0.0"),
    ("fmtTicks", [10000000], "value", "+10,000,000.0"),
    ("fmtTicks", [-1234567.8], "value", "-1,234,567.8"),
    ("group", [1234567], "value", "1,234,567"),
    ("fmtTicks", [None], "value", DASH),
    ("fmtPct", [1.256], "value", "+1.26%"),
    ("fmtPct", [-0.3], "value", "-0.30%"),
    ("fmtPct", [None], "value", DASH),
    ("toneFor", [5], "value", "up"),
    ("toneFor", [-1], "value", "down"),
    ("toneFor", [0], "value", "flat"),
    ("toneFor", [None], "value", "flat"),
    ("severityTone", ["critical"], "value", "crit"),
    ("severityTone", ["warning"], "value", "warn"),
    ("severityTone", ["info"], "value", "info"),
    ("fmtAge", [NOW - 1500, NOW], "value", "1 s ago"),
    ("fmtAge", [NOW - 5000, NOW], "value", "5 s ago"),
    ("fmtAge", [NOW - 4 * 60000, NOW], "value", "4 min ago"),
    ("fmtAge", [NOW - 2 * 3600000, NOW], "value", "2 h ago"),
    ("fmtAge", [NOW + 60000, NOW], "value", "now"),
    ("fmtAge", [0, NOW], "value", "never"),
    ("fmtClock", [NOW], "regex", r"^\d\d:\d\d$"),
    ("fmtClock", [0], "value", DASH),
    # the alert log reads newest first, and the server's array is left alone
    ("alertsNewestFirst", [[{"ts_ms": 30}, None, {"ts_ms": 60}]], "value",
     [{"ts_ms": 60}, {"ts_ms": 30}]),
    ("alertContext", [{"data": {"price": 81200, "size": 12.5, "side": "buy"}}], "value",
     "price 81200 \u00b7 size 12.5 \u00b7 side buy"),
    ("alertContext", [{"data": {"mystery": 1}}], "value", ""),
    ("alertContext", [None], "value", ""),
    ("alertCountText", [{"ok": True, "alerts": [{"ts_ms": 1}, {"ts_ms": 2}]}], "value", "2"),
    ("alertCountText", [{"ok": False, "error": "x"}], "value", DASH),
    # the watchlist join: the engine's rows are the quotes, and a symbol without one says so
    ("watchRows", [["btcusdt", "ETHUSDT"], {"BTCUSDT": {"last": 81200}}], "value",
     [{"symbol": "BTCUSDT", "quote": {"last": 81200}, "last": 81200, "chg_pct": None, "delta": None},
      {"symbol": "ETHUSDT", "quote": None, "last": None, "chg_pct": None, "delta": None}]),
    ("watchSubText", [{"ok": True, "watchlist": ["BTCUSDT", "ETHUSDT"]}, {}], "value",
     "no instrument here is streaming \u2014 quotes appear while the engine runs"),
    ("watchSubText", [{"ok": True, "watchlist": []}, {}], "value", "no symbols stored"),
    # the simulated account, in the ticks it reports
    ("positionLine", [{"running": True, "symbol": "btcusdt",
                       "position": {"side": "long", "size": 2, "entry_price": 81000,
                                    "entry_ms": NOW - 120000}}, NOW], "value",
     "long 2 @ 81000.00 \u00b7 opened 2 min ago"),
    ("positionLine", [{"running": True, "symbol": "BTCUSDT",
                       "position": {"side": "flat", "size": 0}}, NOW], "value",
     "flat \u2014 no open position on BTCUSDT"),
    ("statsCells", [{"running": True, "stats": {"realised_ticks": 12.34, "unrealised_ticks": -3,
                                                "equity_ticks": 9.34, "closed": 2, "wins": 1,
                                                "losses": 1, "orders_submitted": 4,
                                                "orders_filled": 3}}], "value",
     [{"label": "realised", "value": "+12.3", "tone": "up"},
      {"label": "open", "value": "-3.0", "tone": "down"},
      {"label": "equity", "value": "+9.3", "tone": "up"},
      {"label": "closed", "value": "2  (1 w / 1 l)", "tone": "flat"},
      {"label": "orders", "value": "4 in \u00b7 3 filled", "tone": "flat"}]),
    ("statsCells", [{"running": False}], "value", []),
    ("closedRows", [{"closed": [{"pnl_ticks": 1}, {"pnl_ticks": 2}]}], "value",
     [{"pnl_ticks": 2}, {"pnl_ticks": 1}]),
    # the read follows the account, else the first watchlist symbol
    ("defaultSymbol", [{"running": True, "symbol": "btcusdt"}, ["ETHUSDT"]], "value", "BTCUSDT"),
    ("defaultSymbol", [{"running": False}, ["ethusdt", "BTCUSDT"]], "value", "ETHUSDT"),
    ("defaultSymbol", [None, []], "value", ""),
    ("readInputsText", [{"inputs": {"tape": {"measured": True}, "footprint": {"measured": False}}}],
     "value", "not measured: footprint"),
    ("paperSubText", [{"ok": True, "state": {"running": True, "symbol": "btcusdt", "tick_size": 0.01,
                                             "last_price": 0}}], "value",
     "BTCUSDT \u00b7 tick 0.01 \u00b7 no print yet"),
    ("paperSubText", [{"ok": True, "state": {"running": True, "symbol": "btcusdt", "tick_size": 0.01,
                                             "last_price": 81200}}], "value",
     "BTCUSDT \u00b7 tick 0.01 \u00b7 mark 81200.00"),
    # a failed read says so in plain words, never in a parser's own
    ("failWord", [{"message": "Failed to fetch"}], "value", "the app is not answering on this address"),
    ("failWord", [{"message": "the app answered 503 Service Unavailable"}], "value",
     "the app answered 503 Service Unavailable"),
    ("failWord", [None], "value", "the read failed"),
    ("statusFor", [[], NOW], "regex", r"^read only \u00b7 updated \d\d:\d\d$"),
    ("statusFor", [["alerts", "read"], NOW], "contains",
     "2 of 4 reads failed (alerts, read)"),
]

#: Every panel must answer a failed or missing read with a sentence of its own. (fn, args, phrase).
REFUSALS: list[tuple[str, list, str]] = [
    ("alertListHtml", [None, NOW], "did not answer"),
    ("alertListHtml", [{"ok": False, "error": "no engine is running"}, NOW], "no engine is running"),
    ("alertListHtml", [{"ok": True, "alerts": []}, NOW], "no alerts have fired"),
    ("paperSubText", [None], "did not answer"),
    ("paperSubText", [{"ok": False, "error": "no simulated account"}], "no simulated account"),
    ("positionLine", [{"running": False}, NOW], "no simulated account is running"),
    ("watchListHtml", [None, {}, ""], "did not answer"),
    ("watchListHtml", [{"ok": True, "watchlist": []}, {}, ""], "watchlist is empty"),
    ("watchListHtml", [{"ok": True, "watchlist": ["ETHUSDT"]}, {}, ""], "no live readings"),
    ("readBanner", [None], "did not answer"),
    ("readBanner", [{"ok": False, "error": "no live readings for this instrument"},],
     "no live readings for this instrument"),
    # §148 / T7-F9: a failed read is not a market state. This row used to expect "no key levels" —
    # the panel claiming the market had none when the read had not answered at all.
    ("readLevelsHtml", [None], "the read did not answer"),
    ("readLevelsHtml", [{"ok": True, "levels": []}], "no key levels"),
    # §148 / T7-F8: with no symbol chosen nothing was asked, so nothing failed.
    ("readBanner", [None, ""], "no symbol chosen yet"),
    ("readLevelsHtml", [None, ""], "no symbol chosen yet"),
]

HARNESS = """
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const win = {};
new Function('window', src)(win);
const M = win.OFAPMONITOR;
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = cases.map((item) => {
    const fn = M[item.fn];
    if (typeof fn !== 'function') return { ok: false, error: item.fn + ' is not exported' };
    try { return { ok: true, value: fn.apply(null, item.args) }; }
    catch (e) { return { ok: false, error: String((e && e.message) || e) }; }
});
process.stdout.write(JSON.stringify(out));
"""


def _node() -> str:
    return "node"


def _run_node(paths: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(paths, capture_output=True, text=True, encoding="utf-8")


# ── the route tables (read here, with this file's own regexes) ────────────────────────────────

ROUTE_RE = re.compile(r'@router\.(get|post|put|delete|patch)\("([^"]*)"\)')
#: module -> the router prefix the module declares.
ROUTERS = {ATLAS_API: "/api/atlas", CONTROL_API: "/api/control"}


def _route_table() -> dict[str, set[str]]:
    """Every ``/api/...`` the two routers publish: normalised path -> the methods on it.

    A path can carry more than one verb (the watchlist is read with GET and written with POST), so
    the table keeps the whole set — the page must land on a path that answers GET.
    """
    table: dict[str, set[str]] = {}
    for path, prefix in ROUTERS.items():
        source = path.read_text(encoding="utf-8", errors="replace")
        for method, route in ROUTE_RE.findall(source):
            table.setdefault(_normalise_route(prefix + route), set()).add(method.lower())
    return table


def _normalise_route(route: str) -> str:
    """A path with every ``{hole}`` collapsed to one placeholder, no trailing slash."""
    return re.sub(r"\{[^}]+\}", "{param}", route).rstrip("/")


JS_CALL_RE = re.compile(r"""(?:get|api|fetch)\(\s*['"`]([^'"`]+)['"`]""")
JS_LITERAL_RE = re.compile(r"""['"`](/api/[^'"`]*)['"`]""")


def _js_paths(source: str) -> list[str]:
    """The normalised paths the module calls, the way the end-of-build audit reads them."""
    out: list[str] = []
    for raw in JS_CALL_RE.findall(source):
        if not raw.startswith("/api"):
            continue
        raw = raw.split("?")[0]
        raw = re.sub(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "{param}", raw)
        raw = re.split(r"[`$\s]", raw)[0] or raw
        out.append(raw.rstrip("/") or "/")
    return out


def _resolves(call: str, table: dict[str, set[str]]) -> set[str]:
    """The methods of the route this call hits, or an empty set when nothing matches."""
    if call in table:
        return table[call]
    for depth in (1, 2):
        candidate = call + "/{param}" * depth
        if candidate in table:
            return table[candidate]
    return set()


@pytest.fixture(scope="module")
def module_source() -> str:
    return MODULE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page_source() -> str:
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def node_results(tmp_path_factory) -> list[dict]:
    """The real module, executed under node, over the documented cases and the refusal list."""
    work = tmp_path_factory.mktemp("monitor")
    harness = work / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    cases = ([{"fn": fn, "args": args} for fn, args, _, _ in CASES]
             + [{"fn": fn, "args": args} for fn, args, _ in REFUSALS])
    payload = work / "cases.json"
    payload.write_text(json.dumps(cases), encoding="utf-8")
    out = _run_node([_node(), str(harness), str(MODULE), str(payload)])
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ── the files ────────────────────────────────────────────────────────────────────────────────


def test_the_page_its_module_and_its_selftest_exist():
    assert PAGE.is_file(), "the companion monitor is a page the app already serves"
    assert MODULE.is_file(), "monitor.js holds the page's logic"
    assert SELFTEST.is_file(), "the module carries its own gate"
    assert PAGE.stat().st_size > 2000 and MODULE.stat().st_size > 8000, "both files carry real work"


def test_the_page_sits_where_the_app_already_serves_static_files():
    """No new route: /desktop/monitor.html comes from the mount the launcher already installs."""
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert 'UI_DIR = Path(__file__).parent / "ui"' in launcher, "the static mount's directory moved"
    assert 'dashboard_app.mount("/desktop"' in launcher, "the /desktop mount moved"
    assert UI == ROOT / "orderflow_system" / "desktop" / "ui"


def test_the_page_is_self_contained(page_source, module_source):
    """Nothing on this page loads, connects or points anywhere but this origin."""
    for name, source in (("monitor.html", page_source), ("monitor.js", module_source)):
        assert not re.search(r"https?://", source), f"{name} references an absolute URL"
        assert "//cdn" not in source and "unpkg" not in source and "jsdelivr" not in source, name
        assert "@import" not in source, f"{name} pulls a stylesheet in"
    refs = re.findall(r'(?:src|href)="([^"]+)"', page_source)
    external = [r for r in refs if not r.startswith("/desktop/")]
    assert not external, f"the page loads something outside this app: {external}"
    assert '<script src="/desktop/monitor.js"></script>' in page_source, "the page loads its module"
    assert not re.search(r"<script(?![^>]*\ssrc=)[^>]*>", page_source), \
        "no inline script: the page's CSP is script-src 'self'"
    assert "fonts.googleapis" not in page_source and "font-face" not in page_source, "no web font"


def test_the_page_is_built_for_a_phone(page_source):
    assert 'name="viewport"' in page_source and "viewport-fit=cover" in page_source, \
        "a phone needs the viewport meta and the notch inset"
    assert "env(safe-area-inset-top)" in page_source and "env(safe-area-inset-bottom)" in page_source
    assert "--mon-bg: #0a0e16" in page_source, "dark is the shipped look, from the app's own palette"
    assert 'data-mon-panel="alerts"' in page_source and 'data-mon-tab="alerts"' in page_source, \
        "the page is a tab bar between panels"
    for panel in ("alerts", "paper", "watch", "read"):
        assert f'data-mon-panel="{panel}"' in page_source, f"the {panel} panel is missing"
        assert f'data-mon-tab="{panel}"' in page_source, f"the {panel} tab is missing"
    assert "position: fixed" in page_source and "min-height: 52px" in page_source, \
        "the controls are in thumb reach and big enough to hit"


def test_the_page_carries_no_secrets(page_source, module_source):
    for name, source in (("monitor.html", page_source), ("monitor.js", module_source)):
        found = re.findall(r"(?i)\b(api[_-]?key|secret|password|token|bearer)\b", source)
        assert not found, f"{name} mentions credentials: {sorted(set(found))}"


def test_the_two_files_are_crlf_like_every_sibling():
    for path in (PAGE, MODULE, SELFTEST):
        raw = path.read_bytes()
        assert b"\r\n" in raw, f"{path.name} must be CRLF like the other ui/ modules"
        assert raw.count(b"\n") == raw.count(b"\r\n"), f"{path.name} mixes line endings"


# ── the endpoints ────────────────────────────────────────────────────────────────────────────


def test_the_route_helper_reads_the_real_files():
    """A broken regex must fail loudly here rather than wave every call through."""
    table = _route_table()
    assert len(table) > 100, f"only {len(table)} routes parsed — the helper is wrong"
    assert table["/api/atlas/alerts"] == {"get"}
    assert table["/api/atlas/replay/paper/state"] == {"get"}
    assert table["/api/control/search/watchlist"] == {"get", "post"}, \
        "the watchlist is read here and written elsewhere — this page must land on the GET"
    assert table["/api/atlas/scanner"] == {"get"}
    assert table["/api/atlas/market-read/{param}"] == {"get"}
    assert table["/api/atlas/alerts/clear"] == {"post"}, \
        "the helper sees write routes too — it is the page that may not call them"
    assert "/api/atlas/no-such-route" not in table, "the negative control holds"


def test_every_endpoint_the_page_calls_exists_and_is_a_get(module_source):
    table = _route_table()
    calls = _js_paths(module_source)
    assert calls, "no API call was found in the module — the helper is wrong, not the page"
    assert sorted({c for c in calls}) == EXPECTED_CALLS, \
        "the page calls exactly the documented endpoints"
    for call in calls:
        methods = _resolves(call, table)
        assert methods, f"{call} is not a route on either router"
        assert "get" in methods, f"{call} does not answer GET (it answers {sorted(methods)})"
    assert table["/api/control/search/watchlist"] == {"get", "post"}, \
        "the watchlist path carries a writer in the app; this page must only ever read it"


def test_the_page_only_reads(module_source):
    assert not re.search(r"method\s*:", module_source), "the page sends no request options at all"
    assert not re.search(r"\b(POST|PUT|DELETE|PATCH)\b", module_source), \
        "read-only means read-only"
    literals = {raw for raw in JS_LITERAL_RE.findall(module_source)}
    calls = set(JS_CALL_RE.findall(module_source))
    assert literals == calls, \
        f"an /api path is not an argument to the GET helper: {sorted(literals - calls)}"
    for forbidden in ("alerts/clear", "engine/start", "engine/stop", "replay/paper/order",
                      "replay/paper/cancel", "notifications"):
        assert forbidden not in module_source, f"the monitor must never call {forbidden}"


# ── the page's own wiring ────────────────────────────────────────────────────────────────────


def test_the_elements_the_module_writes_exist_in_the_page(page_source, module_source):
    ids_in_page = re.findall(r'id="([A-Za-z0-9_-]+)"', page_source)
    assert len(ids_in_page) == len(set(ids_in_page)), "duplicate id in the page"
    assert all(i.startswith("mon") for i in ids_in_page), \
        f"ids must carry the view prefix: {[i for i in ids_in_page if not i.startswith('mon')]}"
    used = set(re.findall(r"""(?<![A-Za-z0-9_])(?:el|setText|setHtml|setTone)\(\s*['"]([A-Za-z0-9_-]+)['"]""",
                          module_source))
    used |= set(re.findall(r"""getElementById\(\s*['"]([A-Za-z0-9_-]+)['"]""", module_source))
    assert used, "the id helper is not being read — that would make this test vacuous"
    missing = sorted(i for i in used if i not in ids_in_page)
    assert not missing, f"the module writes to elements the page does not have: {missing}"
    assert all(i.startswith("mon") for i in used)


def test_the_timer_and_listener_ledger(module_source):
    """The numbers the parent freezes in test_timer_guards.py / test_listener_balance.py."""
    timers = re.findall(r"setInterval\s*\(", module_source)
    assert len(timers) == TIMERS, "one poller serves four panels"
    site = module_source.index("setInterval(")
    window = module_source[max(0, site - 400):site + 600]
    assert "OFAPPause" in window, "the cadence is handed to the app's pause registry"
    assert "document.hidden" in module_source and "OFAP_PAUSED" in module_source, \
        "and a hidden page or a paused app does not poll"
    adds = len(re.findall(r"addEventListener\s*\(", module_source))
    removes = len(re.findall(r"removeEventListener\s*\(", module_source))
    assert (adds, removes) == LISTENERS, \
        f"the listener ledger changed: {adds}/{removes} (frozen at {LISTENERS[0]}/{LISTENERS[1]})"
    assert "bootDoc.addEventListener('DOMContentLoaded', wire)" in module_source
    assert "return false" in module_source, "the module stays inert on a page without monitor markup"


# ── the module under node ────────────────────────────────────────────────────────────────────


def test_the_module_parses_and_its_selftest_is_green():
    check = _run_node([_node(), "--check", str(MODULE)])
    assert check.returncode == 0, check.stderr
    out = _run_node([_node(), str(SELFTEST)])
    assert out.returncode == 0, out.stdout + out.stderr
    assert re.search(r"monitor selftest: \d+ ok, 0 failed", out.stdout), out.stdout


def _sentence(value) -> str:
    """The text a case produced — a refusal/banner is a ``{text, kind}`` pair, not a bare string."""
    if isinstance(value, dict):
        return str(value.get("text", ""))
    return value if isinstance(value, str) else ""


def test_the_documented_formatting_cases_hold(node_results):
    for index, (fn, args, mode, expected) in enumerate(CASES):
        result = node_results[index]
        assert result["ok"], f"{fn}({args!r}) threw: {result.get('error')}"
        got = result["value"]
        if mode == "value":
            assert got == expected, f"{fn}({args!r}) → {got!r}, expected {expected!r}"
        elif mode == "contains":
            text = _sentence(got)
            assert isinstance(text, str) and str(expected) in text, f"{fn}({args!r}) → {got!r}"
        else:
            text = _sentence(got)
            assert re.search(str(expected), text), f"{fn}({args!r}) → {got!r}"


def test_every_panel_refuses_in_a_sentence_rather_than_a_blank(node_results):
    """A failed or missing read is a sentence in its own panel — never a blank, never a throw."""
    offset = len(CASES)
    for index, (fn, args, phrase) in enumerate(REFUSALS):
        result = node_results[offset + index]
        assert result["ok"], f"{fn}({args!r}) threw: {result.get('error')}"
        got = _sentence(result["value"])
        assert phrase in got, f"{fn}({args!r}) → {got!r}"
        for artefact in ("undefined", "NaN", "[object", "Error:"):
            assert artefact not in got, f"{fn}: the refusal leaks {artefact!r}: {got!r}"


def test_a_refusal_never_carries_markup_from_the_payload():
    """The alert message, the symbol and the level kind all travel into the page — escaped."""
    source = MODULE.read_text(encoding="utf-8")
    assert "esc(row.message || '')" in source, "the alert message is escaped where it is printed"
    assert "'<div class=\"mon-msg\">' + esc(" in source
    assert "esc(fmtPrice(row.price))" in source, "a level price is escaped too"
