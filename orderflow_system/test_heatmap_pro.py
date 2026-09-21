"""§120's gate: the liquidity map's interactions — click, box, wheel, one-fetch path.

The map's own half is `desktop/ui/heatmap-pro.js` (overlay, gestures, stepping) over
`desktop/ui/atlas.js`'s loader. This file pins the interaction contracts as data and shells out
to `heatmap-pro.selftest.js` for the stepping maths.

Deliberately dumb: source text in, assertions out, no browser, no imports from the front end.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
HM = UI / "heatmap-pro.js"
ATLAS = UI / "atlas.js"
SELFTEST = UI / "heatmap-pro.selftest.js"


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
    found = re.search(r"heatmap-pro selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 14, f"only {found.group(1)} checks ran — the selftest shrank"


def test_a_click_can_never_leave_a_zero_size_box():
    hm = _text(HM)
    assert "P.anchor = {" in hm and "DRAG_PX" in hm, "mousedown must anchor, not select"
    assert "if (!P.dragging || !P.anchor) return;" in hm, "the window drag must guard on the anchor"
    assert "Math.abs(nx - P.anchor.x) >= DRAG_PX" in hm, "the box must be born on real movement"
    assert "P.sel = { x0: Math.max(0, ev.clientX - r.left)" not in hm, \
        "mousedown still builds a selection directly — the click-darkens bug returns"
    assert "P.anchor = null" in hm, "mouseup must clear the anchor"
    assert "window.addEventListener('mousemove', (ev) => {" in hm, \
        "the drag must track on the window (past the canvas edge), not the canvas alone"


def test_one_fetch_per_change_and_stale_loads_cannot_land():
    hm = _text(HM)
    at = _text(ATLAS)
    assert "ofap:heat-offer" in hm and "ofap:heat-offer" in at, \
        "the overlay must adopt the loader's payload"
    assert "setTimeout(() => pull(true), 280)" not in hm, \
        "the old double fetch (change + delayed pull) is back"
    assert "seq !== A.heatSeq" in at, "the loader lost its sequence guard"
    assert "A.heatSeq = (A.heatSeq || 0) + 1" in at


def test_end_stops_answer_out_loud():
    hm = _text(HM)
    assert "tightest window already" in hm and "widest window already" in hm
    assert "most rows already" in hm and "fewest rows already" in hm


def test_the_map_refresh_repaints_from_cache():
    hm = _text(HM)
    assert "if (P.last) { draw(); hud(); } else { pull(true); }" in hm, \
        "a click or relayout must not spend a heatmap fetch"
    assert "OFAPHEATVIEW.zoomTime(V, dir, 0.5" in hm, "the buttons must zoom through the view maths"
    assert "listStep: listStep" in hm, "the exported surface lost listStep"

# ── the range-to-table (v2 §7-11b, 2026-09-19) ─────────────────────────────────────────────────

def test_the_selection_strip_lists_events_in_region():
    """The boxed region's own level events (walls/grows/pulls/spikes), listed on demand — and the
    list is taken away with the selection, so a stale table can never stand over an empty map."""
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parent / "desktop" / "ui" / "heatmap-pro.js").read_text(encoding="utf-8")
    assert 'data-hm-pro="events-region"' in js
    assert "function regionEvents()" in js and "function paintEvents()" in js
    assert "csvForEvents" in js and "data-hm-pro-events" in js
    assert "Events in region" in js and "Export events CSV" in js
    assert "close-events" in js


def test_the_region_hand_off_waits_for_the_replay_list():
    """The replay picker fills its options lazily (view entry, focus). A bare `sel.value = …` into
    a list that does not carry the symbol lands on NOTHING and the transport falls back to the app
    symbol — replaying another instrument than the boxed region. The hand-off must ask the picker's
    own filler (atlas.js's OFAPREPLAY) first, and SAY SO when the instrument is genuinely absent —
    never let the form silently disagree with the map."""
    hm = _text(HM)
    at = _text(ATLAS)
    assert "window.OFAPREPLAY = { fillSymbols: fillReplaySymbols }" in at, \
        "atlas.js no longer publishes the replay picker's filler"
    assert "async function handRegionToReplay(" in hm, "the guarded write half is gone"
    assert "OFAPREPLAY.fillSymbols" in hm, "the hand-off no longer waits for the list"
    assert "the replay list does not carry" in hm, "the honest refusal was removed"
    assert "void handRegionToReplay(" in hm, "sendRegionToReplay no longer routes through the guard"
    # the guarded half must also re-pair the From/To preset chips it writes programmatically
    assert "OFAPPRESETS.refresh" in hm
    # and the exported surface still carries the transport entry
    assert "HEATMAP_PRO = { state: P, refresh: refresh, pull: pull" in hm

