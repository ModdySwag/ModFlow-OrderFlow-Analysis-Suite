"""Gate the legacy dashboard widgets' Node selftest (D-07 teardown symmetry, D-08 incremental stats).

`node desktop/static/legacy-widgets.selftest.js` loads both widgets against a DOM stub and prints
"N ok, M failed"; this test fails the suite on any failure and on a missing node (skipped instead,
like the other Node gates here).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SELFTEST = (Path(__file__).parent / "dashboard" / "static" / "legacy-widgets.selftest.js")


def test_the_legacy_widgets_selftest_passes():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    assert SELFTEST.is_file(), SELFTEST
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, timeout=120,
                          cwd=str(Path(__file__).resolve().parents[1]))
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    assert proc.returncode == 0, f"{tail[0]}\n{proc.stdout}\n{proc.stderr}"
    assert " 0 failed" in tail[0], tail[0]
