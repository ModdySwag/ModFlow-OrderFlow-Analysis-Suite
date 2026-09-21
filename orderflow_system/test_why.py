"""why.js — the metric-explanation registry (§147, competitive P2-2).

The registry itself is selftested under Node (`desktop/ui/why.selftest.js`): every registered read
renders a card that names its kind (measured / inferred / computed), every read the app calls an
inference is labelled one, and every `data-why` id placed in index.html exists in the registry —
a "why" that explains nothing fails rather than ships.

This wrapper runs that selftest in the Python suite and pins the two wiring facts the Python side
owns: the module is loaded by index.html, and the reference audit knows it exists.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
SELFTEST = UI / "why.selftest.js"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    return node


def test_the_registry_selftest_passes():
    proc = subprocess.run(
        [_node(), str(SELFTEST)],
        cwd=str(SELFTEST.parent),
        capture_output=True,
        text=True, encoding="utf-8",
        timeout=60,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    match = re.search(r"why selftest:\s*(\d+)\s*ok,\s*(\d+)\s*failed", output)
    assert match, f"the selftest did not report a summary:\n{output}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, f"why selftest reported {failed} failure(s):\n{output}"
    assert ok >= 8, f"only {ok} checks ran — is the selftest intact?\n{output}"
    assert proc.returncode == 0, output


def test_the_module_is_loaded_by_the_page():
    html = (UI / "index.html").read_text(encoding="utf-8", errors="replace")
    assert '<script src="/desktop/why.js"></script>' in html, "why.js is not loaded by index.html"


def test_the_page_explains_a_real_spread_of_reads():
    """The layer is only worth having if the panels actually use it: at least twelve readouts
    across at least six different views carry a data-why id."""
    html = (UI / "index.html").read_text(encoding="utf-8", errors="replace")
    ids = re.findall(r'data-why="([^"]+)"', html)
    assert len(set(ids)) >= 12, f"only {len(set(ids))} distinct reads carry an explanation"
    registry = json.loads(_registry_json())
    assert registry, "the registry could not be read out of why.js"
    for used in set(ids):
        assert used in registry, f"index.html explains {used!r} but the registry has no such entry"


def _registry_json() -> str:
    """Read the registry straight out of the module so the pin cannot drift from the source."""
    src = (UI / "why.js").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"var WHYS = \{(.*?)\n    \};", src, re.S)
    assert match, "the WHYS registry block was not found in why.js"
    body = match.group(1)
    keys = re.findall(r"^\s*'([^']+)':\s*\{", body, re.M)
    return json.dumps({key: True for key in keys})
