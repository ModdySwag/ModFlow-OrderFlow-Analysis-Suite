"""Strips — the reader's hands on a scrolling list (P1-4).

Pinned here: the module and its selftest are present and green, `strips.js` is registered with the
audit (it is the shell-level module the reader's keys go through), it stays renderer-agnostic (no
engine call, no socket, no storage) and it does not steal Escape — the shell owns that key.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
STRIPS = UI / "strips.js"


@pytest.fixture(scope="module")
def source() -> str:
    return STRIPS.read_text(encoding="utf-8")


def test_the_module_and_its_selftest_are_present():
    assert STRIPS.exists(), "strips.js is the module the reader's keys go through"
    assert (UI / "strips.selftest.js").exists(), "every shell-level module carries its own gate"


def test_it_parses():
    out = subprocess.run([*_node(), "--check", str(STRIPS)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr


def test_its_selftest_passes():
    out = subprocess.run([*_node(), str(UI / "strips.selftest.js")], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stdout + out.stderr
    assert re.search(r"strips selftest: \d+ ok, 0 failed", out.stdout), out.stdout


def test_it_is_registered_with_the_audit():
    audit = (ROOT / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"strips.js"' in audit, "the audit cross-checks element ids and api() calls per module"


def test_it_stays_renderer_and_engine_agnostic(source):
    assert "OFAPBUS" not in source, "a strip watches the DOM; it must not talk to the bus"
    assert "WebSocket" not in source, "ingest is not a strip's business"
    assert "localStorage" not in source and "sessionStorage" not in source, "the config is the record"


def test_it_does_not_steal_escape(source):
    """`shell.js` owns Escape (menus, restoring from maximise); a strip taking it would close the
    wrong thing. The release paths are the chip's click and Home."""
    assert "Escape" not in source.replace("'Escape'", ""), "no Escape binding in strips.js"


def test_the_keys_it_does_own_are_guarded_against_typing(source):
    assert "isContentEditable" in source and "TEXTAREA" in source, "never step while a field has focus"


def _node() -> list[str]:
    return ["node"] if sys.platform != "win32" else ["node"]
