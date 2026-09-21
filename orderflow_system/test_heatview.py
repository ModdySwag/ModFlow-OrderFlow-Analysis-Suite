"""§121's gate: the heatmap viewport — ladders, the anchor contract, gestures, the deliberate path.

The maths live in `desktop/ui/heatview.js` (node selftest runs here); the wiring pins below make
sure the gestures, the loader and the dropdowns all speak the same state — the three-places-drift
class that this audit opened with.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
HV = UI / "heatview.js"
HM = UI / "heatmap-pro.js"
ATLAS = UI / "atlas.js"
IDX = UI / "index.html"
SELFTEST = UI / "heatview.selftest.js"
AUDIT = Path(__file__).parent.parent / "scripts" / "audit_ui_refs.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_selftest_exists_and_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    assert SELFTEST.is_file()
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"heatview selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 28, f"only {found.group(1)} checks ran — the selftest shrank"


def test_the_dropdown_ladders_are_the_view_ladders():
    """One ladder, three places (the module, index.html, the loader's wire values) — compared here."""
    hv = _text(HV)
    idx = _text(IDX)
    cols_js = re.search(r"const COLS = \[([^\]]+)\]", hv)
    rows_js = re.search(r"const ROWS = \[([^\]]+)\]", hv)
    assert cols_js and rows_js, "heatview lost its ladders"
    cols = [int(v) for v in cols_js.group(1).split(",")]
    rows = [int(v) for v in rows_js.group(1).split(",")]

    def options(select_id: str) -> list[int]:
        m = re.search(r'<select id="' + select_id + r'"[^>]*>(.*?)</select>', idx, re.S)
        assert m, f"index.html lost the #{select_id} select"
        return [int(v) for v in re.findall(r'value="(\d+)"', m.group(1))]

    assert options("hmColumns") == cols, "the Window dropdown drifted from heatview's ladder"
    assert options("hmRows") == rows, "the Rows dropdown drifted from heatview's ladder"


def test_heatview_is_wired_where_the_loader_and_gestures_need_it():
    idx = _text(IDX)
    hm = _text(HM)
    assert idx.find("/desktop/heatview.js") < idx.find("/desktop/heatmap-pro.js"), \
        "heatview must load before heatmap-pro's tag"
    assert "heatview.js" in _text(AUDIT), "the audit's JS_FILES lost heatview"
    assert hm.count("OFAPHEATVIEW") >= 8, "heatmap-pro lost its view wiring"


def test_gestures_follow_the_industry_grammar():
    hm = _text(HM)
    # wheel: both axes read, wheel-up = zoom in, gutter/shift = rows
    assert "ev.deltaY !== 0 ? ev.deltaY : ev.deltaX" in hm
    assert "const dir = d < 0 ? -1 : 1;" in hm
    assert "if (ev.shiftKey || overGutter) { zoomRows(dir); return; }" in hm
    # pan: middle or shift+left, tracked on the window, throttled, final load on release
    assert "if (ev.button === 1 || (ev.button === 0 && ev.shiftKey))" in hm
    assert "OFAPHEATVIEW.panBy(probe, ev.clientX - P.pan.x0" in hm
    assert ">= 140" in hm, "the pan throttle is gone"
    # click-off clears a lingering box
    assert "P.born" in hm and "say('selection cleared')" in hm
    # the live chip + keys
    assert 'data-hm-pro="live"' in hm and "back to live" in hm
    assert "keys: ['shift+arrowleft']" in hm and "keys: ['home']" in hm
    assert "←/→ = pan" in hm, "the tip must teach the new grammar"
    # §122: the Detail dial (column width) and the labels that follow it
    assert "id=\"hmBucket\"" in _text(IDX), "index.html lost the Detail control"
    assert "function relabelWindows()" in hm and "function wireBucket()" in hm
    assert "path: 'atlas.heatmap.bucket_ms'" in hm, "the Detail dial must reach the registered param"
    assert "relabelWindows();" in hm


def test_the_loader_takes_the_anchor_and_the_deliberate_path():
    atlas = _text(ATLAS)
    hm = _text(HM)
    assert "async function loadHeatmap(force)" in atlas
    assert "if (!force && window.OFAPINTENT && OFAPINTENT.held('heatmap'))" in atlas, \
        "the force path past the intent gate is gone — the wheel's own lease will defer the zoom again"
    assert "&until=' + Math.round(OFAPHEATVIEW.state.until)" in atlas
    assert "document.getElementById('hmColumns').onchange = () => loadHeatmap(true);" in atlas
    assert "document.getElementById('hmRows').onchange = () => loadHeatmap(true);" in atlas
    assert "(window.OFAPHEATVIEW && OFAPHEATVIEW.state.until != null)) loadHeatmap();" in atlas, \
        "the slow refresh must pause while panned"
    assert "untilQ()" in hm, "the overlay's own fetch must respect the anchor"
