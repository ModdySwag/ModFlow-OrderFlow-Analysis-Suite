"""The Market Pressure card (desktop/ui/market-pressure.js) — buy vs sell per bucket, on the CVD view.

The card reads the SAME series atlas.js's own CVD chart reads (/api/atlas/cvd/{symbol}), which is the
whole point of the change this file gates: one dataset is ONE bus channel, not one per panel. The
decisions that matter are arithmetic — how many channels, at what cadence, and whether the subscription
is released when the card leaves the screen — so they are pinned in Node
(`market-pressure.selftest.js`) against a stub window, a stub document and the real bus.js.

This file gates the invariants around it: the module parses, it is loaded by the shell's own loader
list, it is registered with the UI audit, the route it names really exists, and it never touches
ingest, an engine control verb or browser storage.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
PRESSURE = UI / "market-pressure.js"
SELFTEST = UI / "market-pressure.selftest.js"
INDEX = UI / "index.html"
LOADER = UI / "atlas-v2.js"          # the module that pulls this one in
ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_ui_refs.py"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _audit_module():
    spec = importlib.util.spec_from_file_location("audit_ui_refs_for_pressure", AUDIT)
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


def test_the_panel_and_its_selftest_exist():
    assert PRESSURE.is_file(), "desktop/ui/market-pressure.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/market-pressure.selftest.js is missing"


def test_the_panel_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(PRESSURE)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=180, cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"market-pressure selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 10, f"the self-test shrank to {ok} checks — expected the channel arithmetic"
    assert proc.returncode == 0


def test_the_card_reads_exactly_the_shared_cvd_series():
    """The one route, stated once — and it is the same url atlas.js polls for the CVD view."""
    src = _read(PRESSURE)
    urls = sorted(set(re.findall(r"'(/api/[^']*)'", src)))
    assert urls == ["/api/atlas/cvd/"], f"the card must read one series: {urls}"
    known = _routes()
    assert known, "the route table came back empty — the audit could not see the modules"
    assert "/api/atlas/cvd/{param}" in known, "the series route does not exist in the app's own table"
    atlas = _read(UI / "atlas.js")
    assert "'/api/atlas/cvd/' + encodeURIComponent(S.symbol)" in atlas, \
        "atlas.js's CVD chart must still read the same url — that is what makes it one channel"


def test_it_joins_the_delivery_layer_instead_of_owning_a_poll():
    src = _read(PRESSURE)
    assert "window.OFAPBUS" in src and "bus.subscribe" in src, "it must join the shared channel"
    assert src.count("setInterval(") == 1, "one timer at most — the no-bus fallback"
    assert src.count("clearInterval(") == 1, "and the same code clears it"
    assert "const bus = window.OFAPBUS;" in src, "the bus is read lazily, never at load time"
    assert "OFAPINTENT" in src, "the no-bus tick still asks the interaction arbiter"
    assert 'MP_SHARE_MS = 5000' in src, "the shared cadence is the CVD chart's own 5 s"
    assert 'MP_OWN_MS = 4000' in src, "and the card's own cadence is unchanged for a bus-less page"
    assert "'s via the shared bus'" in src, "the card states which cadence is running"


def test_it_is_loaded_by_the_shell_and_registered_with_the_audit():
    html = _read(INDEX)
    loader = _read(LOADER)
    assert "market-pressure.js" in loader, "atlas-v2.js's loader list must still pull the card in"
    assert 'src="/desktop/atlas-v2.js"' in html, "and atlas-v2.js must be loaded"
    assert 'src="/desktop/bus.js"' in html, "the delivery layer it joins must be loaded too"
    assert "market-pressure.js" in _read(AUDIT), "register it in JS_FILES"
    assert 'data-view="cvd"' in html, "the card lives in the CVD view's section"


def test_it_never_touches_ingest_or_browser_storage():
    src = _read(PRESSURE)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource",
                      "engine/start", "engine/stop", "engine/restart", "ingest"):
        assert forbidden not in src, f"market-pressure.js must not touch {forbidden}"
    assert "OFAPBUS" in src, "it takes its delivery from the suite's own layer"


def test_the_card_scopes_its_section_lookup_and_drives_ids_that_resolve():
    """The bare [data-view=x] selector binds the NAV BUTTON, which comes first in the document — a
    panel watching the button believes it is off-screen. And every id the card drives is either the
    shell's own select or one this module's own markup creates."""
    src = _read(PRESSURE)
    assert "querySelector('[data-view=" not in src and 'querySelector("[data-view=' not in src, \
        "the section lookup must be scoped to .view"
    assert 'const MP_VIEW = \'.view[data-view="cvd"]\';' in src, "one scoped selector, used everywhere"
    html = _read(INDEX)
    ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
    driven = set(re.findall(r"getElementById\('([A-Za-z0-9_-]+)'\)", src))
    assert driven, "the module must name the elements it drives"
    assert "symbolSelect" in driven and "symbolSelect" in ids, "it follows the app's instrument select"
    assert "symbolSelect" in src and src.index("symbolSelect") > 0
    own = {"mpCard", "mpKpis", "mpCanvas", "mpStamp", "mpNote", "mpRefresh"}
    assert own <= driven, f"the card's own controls must all be driven: {sorted(own - driven)}"
    for element_id in sorted(own):
        assert (f'id="{element_id}"' in src or f".id = '{element_id}'" in src), \
            f"{element_id} must be created by this module's markup"
