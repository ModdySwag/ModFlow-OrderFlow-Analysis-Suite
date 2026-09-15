"""Gate for the indicator add-on pack: its own Node self-test plus the files being servable.

The pack lives in `desktop/ui/indicators/*.js` — plain files the browser loads through
`GET /api/control/studies/library`. Python cannot execute them, so it does what the engine gate
does: run the module's own self-test in Node and assert the outcome.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
IND = UI / "indicators"
SELFTEST = UI / "indicators.selftest.js"
PACK_FILES = ["rsi.js", "macd.js", "obv.js", "williams-r.js", "adx.js"]


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def test_addon_files_are_present():
    missing = [name for name in PACK_FILES if not (IND / name).is_file()]
    assert missing == [], f"indicator add-on modules missing from desktop/ui/indicators: {missing}"


def test_each_addon_declares_its_identity():
    """A module the Studies view can list as an installed add-on: name, version, pack, contract."""
    for name in PACK_FILES:
        text = (IND / name).read_text(encoding="utf-8")
        for marker in ("pack:", "version:", "studyDef", "calculator:", "plots:", "plotter:"):
            assert marker in text, f"{name} is missing {marker}"
        assert "0.4.1" in text, f"{name} does not carry the pack version"


def test_indicator_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], cwd=str(UI), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 failed" in proc.stdout, proc.stdout
    assert " ok" in proc.stdout, proc.stdout
