"""JS↔Python parity for the diagonal imbalance rule (audit C-01).

The engine (``desktop/ui/ofx.js``) and the analytics pack (``analytics/footprint.py``) are two
runtimes of one rule: the chart tints a level with one side label and the alert layer emits the
other. This test runs both implementations on one shared ladder and asserts they agree, so the
drift that made them contradict each other cannot come back. ``footprint.py``'s documented
convention is the reference (Ask[Y] vs Bid[Y−1] is a buy; Bid[Y] vs Ask[Y+1] is a sell).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.analytics.footprint import FootprintBar
from orderflow_system.data.models import FootprintLevel

UI = Path(__file__).parent / "desktop" / "ui"
ENGINE = UI / "ofx.js"

#: price -> (bid volume, ask volume). One ladder for both runtimes: a selling row, a quiet row,
#: a buying row whose comparison volume is zero (the "no bid underneath" case) and a ladder-edge
#: row with no neighbour on the compared side.
LADDER = [
    (100.0, 100.0, 2.0),
    (100.5, 0.0, 20.0),
    (101.0, 2.0, 40.0),
    (101.5, 1.0, 1.0),
]
TICK = 0.5
R = 4.0


def _python_sides() -> dict[float, str]:
    bar = FootprintBar(timestamp_ms=0)
    for price, bid, ask in LADDER:
        bar.levels[price] = FootprintLevel(price=price, bid_volume=bid, ask_volume=ask)
    return {price: side for price, side in bar.imbalance_levels(R, "diagonal", tick_size=TICK)}


def _js_sides() -> list[dict]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    payload = [{"price": p, "bid": b, "ask": a} for p, b, a in LADDER]
    script = (
        f"const OFX = require({json.dumps(str(ENGINE))});"
        f"console.log(JSON.stringify(OFX.math.diagonalImbalance({json.dumps(payload)}, {R}).rows));"
    )
    proc = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8",
                          timeout=60, cwd=str(UI.parent.parent))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_js_engine_matches_footprint_py_on_a_shared_ladder():
    expected = _python_sides()
    rows = _js_sides()
    assert rows, "the engine returned no rows"

    for row in rows:
        price = float(row["price"])
        want = expected.get(price, "")
        got = row["side"]
        if want == "both" or got == "both":
            # footprint.py reports one side per price (buy wins); the engine may report both.
            # 'both' only satisfies a row the Python side also flagged.
            assert want != "", f"{price}: engine flagged 'both' but footprint.py flagged nothing"
            continue
        assert got == want, f"{price}: engine={got!r} footprint.py={want!r}"

    # and the fixture must exercise both directions, or the parity claim is vacuous
    assert "buy" in {r["side"] for r in rows}, "fixture never exercises a buy"
    assert "sell" in {r["side"] for r in rows}, "fixture never exercises a sell"
