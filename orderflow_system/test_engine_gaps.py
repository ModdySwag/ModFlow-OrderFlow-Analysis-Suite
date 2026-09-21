"""Gate for the ingest-gap provenance (v2 report §7-9, closed 2026-09-19).

The counter is a pure function of the engine's retained tick window — testable without a feed —
and the data pill renders it for the active instrument. These tests pin both halves, including
the honest edge cases: an empty window claims nothing, a thin symbol's own cadence is never
miscalled a gap, and a real silence in a busy stream is.
"""

from pathlib import Path

from orderflow_system.desktop.engine import tick_gaps

S = Path(__file__).resolve().parent
UI = S / "desktop" / "ui"


def _ticks(gaps_ms, step_ms=1000, start=1_700_000_000_000):
    ts = [start]
    for g in gaps_ms:
        ts.append(ts[-1] + g)
    return ts


def test_empty_window_claims_nothing():
    assert tick_gaps([]) == {"window": 0}
    assert tick_gaps([123]) == {"window": 0}


def test_uniform_stream_has_no_gaps():
    out = tick_gaps(_ticks([1000] * 199))
    assert out["window"] == 199 and out["count"] == 0
    assert out["worst_ms"] == 1000


def test_a_real_silence_in_a_busy_stream_is_counted():
    out = tick_gaps(_ticks([1000] * 199 + [30000]))
    assert out["count"] == 1 and out["worst_ms"] == 30000
    # the floor rules a 6 s hole in a 100 ms stream as a gap too: 10 × median = 1 s < floor
    out2 = tick_gaps(_ticks([100] * 199 + [6000]))
    assert out2["count"] == 1 and out2["threshold_ms"] == 5000


def test_a_thin_symbols_own_cadence_is_never_a_gap():
    # one tick every 20 s: a 30 s interval is below 10 × the symbol's own median
    out = tick_gaps(_ticks([20000] * 199 + [30000]))
    assert out["count"] == 0 and out["threshold_ms"] == 200000


def test_unsorted_and_duplicate_timestamps_are_safe():
    out = tick_gaps([5000, 1000, 1000, 3000])
    assert out["window"] == 2 and out["count"] == 0   # sorted, equal stamps contribute nothing
    assert tick_gaps([0, 0, 0]) == {"window": 0}


def test_status_carries_the_gaps_key():
    src = (S / "desktop" / "engine.py").read_text(encoding="utf-8")
    assert '"gaps": tick_gaps(' in src


def test_the_pill_reads_them():
    js = (UI / "ui.js").read_text(encoding="utf-8")
    assert "'/api/control/engine/status'" in js
    assert "gaps ≥" in js and "per_symbol" in js
    assert "last tick " in js
