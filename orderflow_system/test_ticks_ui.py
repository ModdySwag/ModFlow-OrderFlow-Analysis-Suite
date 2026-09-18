"""§90 — the live-tick layer: values that move must show it (arrow, tint, flash).

A file-level contract, deliberately: the selftest pins the behaviour (ticks.selftest.js), and these
pins hold the wiring together — the module ships and is registered, and the numeric readouts that
matter actually call it. A readout that silently drops back to plain textContent would fail here.
"""

from __future__ import annotations

from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"


def test_the_layer_ships_and_is_registered():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'src="/desktop/ticks.js"' in html
    assert (UI / "ticks.selftest.js").exists()
    code = (UI / "ticks.js").read_text(encoding="utf-8")
    assert "OFAPTICK" in code and "arrival" in code


def test_the_main_readouts_tick():
    code = (UI / "ui.js").read_text(encoding="utf-8")
    for anchor, marker in (("function updatePriceKpis", "OFAPTICK"),
                           ("function updateDeltaKpi", "OFAPTICK"),
                           ("function updateDepthKpis", "OFAPTICK"),
                           ("function renderOverviewSignals", "OFAPTICK.arrival"),
                           ("async function renderSystems", "sy-flash")):
        start = code.index(anchor)
        chunk = code[start:start + 1800]
        assert marker in chunk, f"{anchor} lost its {marker} wiring"


def test_the_side_readouts_tick():
    code = (UI / "atlas.js").read_text(encoding="utf-8")
    assert "OFAPTICK.tick(el, text, { arrow: false })" in code     # tracker badge
    assert "cvdValue" in code and "OFAPTICK.tick" in code          # CVD session value
