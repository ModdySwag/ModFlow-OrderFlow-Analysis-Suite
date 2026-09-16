"""The Watchlist panel (desktop/ui/watchlist.js) — one quote line per instrument.

The panel is a board: the instruments come from /api/instruments, the numbers from the suite's
read-only engine status route, and a field neither of them carries renders as an em dash rather than
as a zero. The decisions that matter — who is on the board, what a row shows, whether anything is
still polling — are pure and pinned in Node (`watchlist.selftest.js`) against a stub window, a stub
document and the real bus.js. This file gates the invariants around it: the module is loaded after
the delivery layer it subscribes to, it is registered with the UI audit, the routes it names really
exist, and it never reaches for ingest, an engine control verb or browser storage. A quote board that
could restart ingest, or that kept a copy of state in the webview, would be worse than no board.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
WATCHLIST = UI / "watchlist.js"
SELFTEST = UI / "watchlist.selftest.js"
INDEX = UI / "index.html"
ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_ui_refs.py"

#: The names the module publishes on window.OFAPWATCHLIST — its documented surface.
SURFACE = (
    "VERSION", "STATUS_URL", "INSTRUMENTS_URL", "INTERVAL_MS", "DASH",
    "esc", "buildRows", "buildRow", "orderSymbols", "rowHtml", "loadingHtml", "emptyHtml",
    "errorHtml", "noteRow", "bodyHtml", "subText", "render", "rows", "state",
    "getJson", "getStatus", "onStatus", "loadStatus", "loadInstruments", "refresh",
    "startPoll", "stopPoll", "sync", "activate", "rowClick", "boot", "watch",
)


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _audit_module():
    """The audit script itself, so the route table is discovered by one piece of code, not two."""
    spec = importlib.util.spec_from_file_location("audit_ui_refs_for_watchlist", AUDIT)
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


def test_the_watchlist_files_exist():
    assert WATCHLIST.is_file(), "desktop/ui/watchlist.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/watchlist.selftest.js is missing"


def test_the_watchlist_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(WATCHLIST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_watchlist_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=180,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"watchlist selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 6, f"the self-test shrank to {ok} checks — expected the row and poll decisions"
    assert proc.returncode == 0


def test_the_watchlist_exposes_the_documented_surface():
    src = _read(WATCHLIST)
    assert "window.OFAPWATCHLIST" in src
    for name in SURFACE:
        assert name in src, f"watchlist.js must expose {name}"
    assert "'/api/control/engine/status'" in src, "the status route it reads is stated once, in the source"
    assert "'/api/instruments'" in src


def test_the_watchlist_is_loaded_after_the_bus_and_registered():
    html = _read(INDEX)
    assert 'src="/desktop/watchlist.js"' in html, "index.html must load the panel"
    assert 'src="/desktop/bus.js"' in html, "and the delivery layer it subscribes to"
    assert html.index('src="/desktop/bus.js"') < html.index('src="/desktop/watchlist.js"'), \
        "the bus defines window.OFAPBUS before the panel looks for it"
    assert "watchlist.js" in _read(AUDIT), "register it in JS_FILES"
    assert 'data-view="watchlist"' in html, "the panel needs its section"


def test_the_watchlist_reads_only_routes_this_app_serves():
    """The module names its routes as literals in one place; both must resolve against the real
    route table, exactly the check the UI audit would make of a literal call site."""
    src = _read(WATCHLIST)
    urls = sorted(set(re.findall(r"'(/api/[^']+)'", src)))
    assert urls, "the module must state the routes it reads"
    known = _routes()
    assert known, "the route table came back empty — the audit could not see the modules"
    for url in urls:
        assert url in known, f"{url} is not a route this app serves"


def test_the_watchlist_never_touches_ingest_or_browser_storage():
    """A panel that polls a status route has no business holding state or steering the engine."""
    src = _read(WATCHLIST)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource",
                      "engine/start", "engine/stop", "engine/restart", "ingest",
                      "/api/control/engine/status/start"):
        assert forbidden not in src, f"watchlist.js must not touch {forbidden}"
    assert "/api/control/engine/status" in src, "it reads engine status, read-only"
    assert "OFAPBUS" in src, "and takes its delivery from the suite's own layer"
    assert "setInterval(" in src and "clearInterval(" in src, \
        "with no bus it owns one timer — and clears it"


def test_the_panel_only_uses_the_ids_the_markup_carries():
    """Every element the module reaches for is in the section, and the shell keeps the topbar select."""
    html = _read(INDEX)
    ids = set(re.findall(r"id=\"([A-Za-z0-9_-]+)\"", html))
    used = set(re.findall(r"el\('([A-Za-z0-9_-]+)'\)", _read(WATCHLIST)))
    assert used, "the module must name the elements it drives"
    for element_id in sorted(used):
        assert element_id in ids, f"{element_id} is not in index.html"
    assert {"watchlistBody", "watchlistCount", "watchlistAuto", "watchlistRefresh",
            "watchlistSub"} <= used, "the card's own controls are what the panel drives"
    assert "symbolSelect" in used, "a row click drives the app's own instrument select"
