"""The tape's size floor must be able to reach the sizes the venue actually prints.

A floor of 1 with `parseInt(value) || 1` hid nearly every crypto print: 40 live BTCUSDT prints sampled
0.001-0.15, all below it. The tape looked broken and empty, and the strip affordances had nothing to
work on.
"""
from pathlib import Path

TAPE = (Path(__file__).resolve().parent / "dashboard" / "static" / "tape.js").read_text(encoding="utf-8")
HTML = (Path(__file__).resolve().parent / "desktop" / "ui" / "index.html").read_text(encoding="utf-8")


def test_floor_can_be_zero_and_zero_survives():
    assert 'value="0" min="0"' in TAPE, "the input must allow a floor of 0"
    assert "parseInt(e.target.value) || 1" not in TAPE, "0 must not be coerced back to 1"
    assert "this.options.minSizeFilter = 0" in TAPE, "the default must show the real tape"


def test_the_shell_loads_this_file():
    assert '/static/tape.js' in HTML, "the desktop shell and the patched file must be the same file"
