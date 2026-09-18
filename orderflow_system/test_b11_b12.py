"""Wave B T13 — B11 (consequence-preview drag tooltips) · B12 (undo + multi-select for markings).

The consequence maths is executed by risk.selftest.js; this file pins the wiring landmarks: the
drawings module's undo/multi-select surface, the drag chip, the paper context feed, and the ticket
read-out. Everything here is display/annotation — no path in this package touches execution.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def test_b11_the_consequence_maths_passes_its_selftest() -> None:
    node = shutil.which("node") or "node"
    run = subprocess.run([node, str(UI / "risk.selftest.js")], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "0 failed" in run.stdout
    src = _text("risk.js")
    assert "ticks" in src and "no position — a distance" in src, "the honest flat case"


def test_b11_the_drag_chip_and_the_ticket_read_out_are_wired() -> None:
    draw = _text("drawings.js")
    assert "function ensureTip" in draw and "'risk-chip'" in draw
    assert "OFAPRISK.text(now.p)" in draw, "the drag asks the account's maths, never its own"
    paper = _text("paper.js")
    assert "OFAPRISK.setContext(" in paper, "the account feeds the context on every poll"
    assert "function paintRisk" in paper and "'ppRisk'" in paper
    html = _text("index.html")
    assert 'id="ppRisk"' in html
    assert html.index("/desktop/risk.js") > html.index("/desktop/drawings.js"), "risk.js loads beside drawings"
    css = _text("modules.css")
    assert ".risk-chip" in css and "pointer-events: none" in css, "the chip never eats clicks"


def test_b12_undo_is_bounded_and_every_shape_records_one() -> None:
    src = _text("drawings.js")
    for marker in ("const UNDO_MAX = 50", "function pushUndo", "function undo()",
                   "state.undoStack.length > UNDO_MAX", "state.undoStack.shift()"):
        assert marker in src, marker
    # the recorded operations: add, remove, multi-remove, clear, move, reshape, duplicate
    for label in ("'add ' + draw.kind", "'remove ' + gone.kind", "'remove ' + ats.length",
                  "'clear'", "'move'", "'reshape'", "'duplicate ' + draw.kind"):
        assert label in src, label
    # the surfaces: Ctrl+Z, the toolbar button, the context menu, the shortcut sheet
    assert "(ev.key === 'z' || ev.key === 'Z') && (ev.ctrlKey || ev.metaKey)" in src
    assert "data-mode=\"undo\"" in src and "'Undo last edit'" in src
    assert "'Ctrl+Z', label: 'undo the last marking edit'" in src
    assert "undoDepth: () => state.undoStack.length" in src


def test_b12_multi_select_toggles_and_moves_as_a_group() -> None:
    src = _text("drawings.js")
    for marker in ("function toggleMember", "function isSelected", "function selectionIds",
                   "function deleteSelection", "function selectAll",
                   "select(found.draw.id, { add: ev.shiftKey })",
                   "? state.drawings.filter((d) => selectionIds().indexOf(d.id) >= 0)"):
        assert marker in src, marker
    # the primary + the set clear together on a miss and on Escape
    assert src.count("state.selected = null; state.multiIds = [];") >= 3
