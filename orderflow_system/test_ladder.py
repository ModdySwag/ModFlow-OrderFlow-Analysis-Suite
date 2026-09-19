"""§118's gate: the Trade DOM, the bracket row, the ledger and the chart strip are wired.

The ladder itself is `desktop/ui/ladder.js` — pure row layout and click grammar, painted by
paper.js, which owns the session, the lock and the armed gate. This file pins the wiring as data
(loaded in order, audited, gated, single door for orders) and shells out to `ladder.selftest.js`
for the behavioural half. The live pass is the handoff's §118.

Deliberately dumb: source text in, assertions out, no browser, no imports from the front end.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
ROOT = Path(__file__).resolve().parents[1]
INDEX = UI / "index.html"
LADDER = UI / "ladder.js"
SELFTEST = UI / "ladder.selftest.js"
PAPER = UI / "paper.js"
ATLAS = Path(__file__).resolve().parents[0] / "atlas" / "api.py"

#: the ladder's elements must exist in the page — the audit's id pass cannot see paper.js's
#: dynamic writes, so the ids it binds are pinned here directly.
LADDER_IDS = ["ladderBody", "ldCancelAll"]
BRACKET_IDS = ["ppxSl", "ppxTp", "ppxApply", "ppxBreakeven", "ppxClear", "ppExitsHint"]
LEDGER_IDS = ["ppLedger", "ppLedgerCount", "ppExport"]
STRIP_IDS = ["stripPillText", "stripHint", "stripSize", "stripBuy", "stripSell",
             "stripFlatten", "stripLock", "stripResult"]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_ladder_and_its_selftest_exist():
    assert LADDER.is_file() and SELFTEST.is_file()


def test_the_ladder_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, "--check", str(LADDER)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


def test_the_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"ladder selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 30, f"only {found.group(1)} checks ran — the selftest shrank"


def test_the_ladder_loads_before_its_painter():
    order = re.findall(r'<script[^>]+src="/desktop/([^"]+)"', _text(INDEX))
    assert "ladder.js" in order, "ladder.js is not loaded at all"
    assert "paper.js" in order, "paper.js is not loaded at all"
    assert order.index("ladder.js") < order.index("paper.js"), \
        "paper.js paints the ladder — it must load after the module exists"


def test_the_audit_scans_both_new_surfaces():
    audit = _text(ROOT / "scripts" / "audit_ui_refs.py")
    assert '"ladder.js"' in audit and '"paper.js"' in audit


def test_the_panel_owns_every_element_the_new_surfaces_bind():
    html = _text(INDEX)
    missing = [i for i in LADDER_IDS + BRACKET_IDS + LEDGER_IDS + STRIP_IDS if f'id="{i}"' not in html]
    assert not missing, f"index.html is missing: {missing}"


def test_every_ladder_click_reaches_the_one_armed_submit_door():
    paper = _text(PAPER)
    assert "function submit(body, label, needArmed, outId)" in paper, \
        "the single order door (submit) disappeared"
    assert "place: function (body) { submit(body," in paper and "true, 'ppResult')" in paper, \
        "the ladder no longer walks orders through the armed door"
    assert "arm the order keys in the Keys menu first" in paper \
        and "arm the order keys in the Keys menu first" in _text(LADDER), \
        "the disarmed sentence differs between the ladder's refusal and the door's refusal"
    armed_at = paper.index("if (needArmed &&")
    locked_at = paper.index("if (locked) {")
    assert locked_at < armed_at, "the lock must be checked before the armed gate"


def test_the_ticket_walks_through_the_same_door_unarmed():
    paper = _text(PAPER)
    found = re.search(r"submit\(\{ side: side, size: size, kind: kind, price: num\('ppPrice'\),\s*"
                      r"stop_loss: num\('ppSl'\), take_profit: num\('ppTp'\) \}, side \+ ' order', false, outId\)", paper)
    assert found, "the ticket's own orders no longer pass through submit() unarmed"


def test_the_bracket_ledger_and_strip_call_their_routes():
    paper = _text(PAPER)
    assert "/api/atlas/replay/paper/exits" in paper, "nothing moves a position's exits"
    assert "/api/atlas/replay/paper/export" in paper, "the ledger cannot be exported"
    atlas = _text(ATLAS)
    for route in ('"/replay/paper/exits"', '"/replay/paper/export"'):
        assert route in atlas, f"the atlas router lost {route}"
    assert '"exits": account.exits()' in atlas and '"events": ledger["events"]' in atlas, \
        "the state payload stopped carrying the exits or the ledger"


def test_the_session_tick_comes_from_the_instrument_record():
    paper = _text(PAPER)
    assert "function tickFor(symbol)" in paper, "the tick resolver disappeared"
    assert "tick_size: tickFor(symbol)" in paper, "the session no longer starts on the instrument's tick"
    # the ladder's own default stays the shipped one — the resolver is the only new source
    assert "return 0.01;" in paper


def test_the_chart_strip_rides_the_same_account():
    paper = _text(PAPER)
    assert "data-view=\"' + names[i] + '\"" in paper and "'chart'" in paper, \
        "the poller no longer watches the Chart view for the strip"
