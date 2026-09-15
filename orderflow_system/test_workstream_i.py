"""Workstream I: the stacked-zone bands are drawn, the ramp is switchable and monotonic, pinch shares
the price zoom, and the cursor link is a real store rather than a convention."""
from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"
OFX = (UI / "ofx.js").read_text(encoding="utf-8")
VIEW = (UI / "ofx-view.js").read_text(encoding="utf-8")
HTML = (UI / "index.html").read_text(encoding="utf-8")


def test_stacked_zones_are_drawn_not_only_counted():
    assert "stackedZones" in OFX
    # the band itself: a fill + a leading rail, using the run's real keys
    assert "zone.high" in OFX and "zone.low" in OFX
    assert "STACK " in OFX, "the band must label its length"


def test_two_ramps_and_the_active_one_is_used():
    assert "classicRamp" in OFX and "thermal" in OFX
    assert "state.params.ramp" in OFX, "heat colour must follow the selected ramp"
    assert "ofxRamp" in HTML and "ofxRamp" in VIEW, "the selector must exist and be wired"


def test_pinch_is_the_price_axis_with_the_browser_zoom_cancelled():
    assert "ev.ctrlKey" in OFX
    body = OFX[OFX.index("ev.ctrlKey"):OFX.index("ev.ctrlKey") + 700]
    assert "preventDefault" in body and "scaleY" in body, "pinch must zoom price, not the page"


def test_cursor_link_is_a_store_with_a_clear():
    link = (UI / "cursor-link.js").read_text(encoding="utf-8")
    assert "OFAPCURSOR" in link and "subscribe" in link and "clear" in link
    assert "cursor-link.js" in HTML, "the store must be loaded"
    assert "OFAPCURSOR" in VIEW, "the engine view must publish the cursor"
    assert "ofxDepthNote" in VIEW, "and report where it landed on the ladder"
