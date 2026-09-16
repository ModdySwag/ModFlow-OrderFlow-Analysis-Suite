"""Analytics engines match the golden snapshot taken before numpy was removed.

`analytics/volume_profile.py` and `analytics/delta.py` used numpy for argmax/mean/std and a
degree-1 polyfit. So the frozen build could drop numpy (27 MB of 68 MB), both were rewritten
to the standard library — and "the numbers did not move" is checked here rather than promised:
38 cases, 2138 numeric leaves, taken from the numpy implementations on deterministic fixtures.

     .venv/Scripts/python.exe scripts/regen_analytics_golden.py --write   # accept a change

A refactor that moves a number fails this test with the exact case and delta. The tolerance is
1e-9; the rewrite as landed showed a worst case of 2.3e-13 (LAPACK vs plain summation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import regen_analytics_golden as golden  # noqa: E402  (path set above)


def test_golden_file_exists():
    assert golden.GOLDEN.is_file(), (
        f"missing {golden.GOLDEN} — generate it with "
        "`.venv/Scripts/python.exe scripts/regen_analytics_golden.py --write`")


def test_every_case_matches_the_golden_snapshot():
    stored = json.loads(golden.GOLDEN.read_text(encoding="utf-8"))
    now = golden.snapshot()
    problems = golden.drift(stored, now)
    if problems:
        shown = "\n".join("  " + line for line in problems[:20])
        pytest.fail(f"{len(problems)} analytics result(s) drifted from the golden snapshot:\n{shown}")
    assert stored["fixtures_sha256"] == now["fixtures_sha256"], (
        "the fixtures changed, so this comparison no longer means what it says — "
        "regenerate the snapshot deliberately with --write")


def test_the_float_tolerance_is_the_real_backstop():
    """Sanity: the comparison is numeric, not string equality, and it rejects real drift."""
    stored = json.loads(golden.GOLDEN.read_text(encoding="utf-8"))
    now = json.loads(json.dumps(stored))
    # identical snapshots must pass
    assert golden.drift(stored, now) == []
    # a 1e-6 change must fail, a 1e-12 change must pass (numpy/stdlib rounding territory)
    now["cases"]["dl.candles.roc5"] = stored["cases"]["dl.candles.roc5"] + 1e-6
    assert golden.drift(stored, now), "a 1e-6 drift was not detected"
    now["cases"]["dl.candles.roc5"] = stored["cases"]["dl.candles.roc5"] + 1e-12
    assert golden.drift(stored, now) == [], "a 1e-12 rounding difference should not fail the pin"
