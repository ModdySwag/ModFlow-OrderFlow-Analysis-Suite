"""Gate for the Trackers wiring (control-surface audit F1, closed 2026-09-19).

The view's own menu copy promised "correlation, dots, cross-venue reads" while five live
`/api/atlas` routes had no caller. This pins the wiring end-to-end: every route the panel now
fetches exists on the server, every table the readers paint exists in the markup, and the
readers ride the module's existing 4 s beat (no second timer).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"
ATLAS_API = PKG / "atlas" / "api.py"

WIRED = {
    # fetched route literal in atlas-v2.js -> (route decorator in atlas/api.py, painted element)
    "/api/atlas/crossvenue/": ("/crossvenue/{symbol}", "tkCvTable"),
    "/api/atlas/correlation": ("/correlation", "tkCorrTable"),
    "/api/atlas/intent/": ("/intent/{symbol}", "tkIntentGrid"),
    "/api/atlas/dots/": ("/dots/{symbol}", "tkDotsTable"),
    "/api/atlas/trades/recent/": ("/trades/recent/{symbol}", "tkRtTable"),
}


def test_the_five_dark_routes_are_wired_both_sides():
    js = (UI / "atlas-v2.js").read_text(encoding="utf-8")
    html = (UI / "index.html").read_text(encoding="utf-8")
    api = ATLAS_API.read_text(encoding="utf-8")
    for route_literal, (decorator, element) in WIRED.items():
        assert route_literal in js, f"atlas-v2.js no longer fetches {route_literal}"
        assert f'@router.get("{decorator}")' in api, f"atlas/api.py lost the route {decorator}"
        assert f'id="{element}"' in html, f"index.html lost the table #{element}"


def test_the_readers_ride_the_existing_beat():
    js = (UI / "atlas-v2.js").read_text(encoding="utf-8")
    block = re.search(r"function v2Poll\(\).*?\n\}", js, re.S)
    assert block, "v2Poll is gone"
    body = block.group(0)
    for fn in ("loadCrossvenue", "loadCorrelation", "loadIntent", "loadDots", "loadRecentTrades"):
        assert fn + "()" in body, f"{fn} is not on the trackers beat"
    timers = len(re.findall(r"setInterval\(", js))
    assert timers == 1, f"the module grew a second timer ({timers} setInterval calls)"


def test_the_module_still_parses():
    node = shutil.which("node") or "node"
    res = subprocess.run([node, "--check", str(UI / "atlas-v2.js")], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
    assert res.returncode == 0, res.stderr
