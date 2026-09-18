"""Windows & layouts (T2) — the dialog module is wired, loaded, and calls the real route.

The behaviour lives in the route (pinned in test_aux_windows); this file defends the wiring: the
module exists and parses, the shell loads it, the View menu opens it, and it talks to the same
/api/control/windows route — with the reset action offered for every row.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

UI = Path(__file__).parent / "desktop" / "ui"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_module_exists_and_parses():
    node = shutil.which("node")
    assert node, "node is required for the UI gates"
    proc = subprocess.run([node, "--check", str(UI / "windowing.js")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_the_shell_loads_the_module():
    html = _text(UI / "index.html")
    assert '<script src="/desktop/windowing.js"></script>' in html
    assert "/desktop/chrome.js" in html


def test_the_view_menu_opens_the_dialog():
    assert "Windows & layouts" in _text(UI / "menubar.js")
    assert "OFAPWINDOWS" in _text(UI / "menubar.js")


def test_the_module_talks_to_the_window_route_and_offers_the_reset():
    code = _text(UI / "windowing.js")
    assert "/api/control/windows" in code
    assert "action: 'reset'" in code, "the reset action is not offered"
    assert "action: 'close_all'" in code
    assert "native" in code, "the no-host answer is not handled"
