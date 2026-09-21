"""Windows & layouts (T2, extended §128) — the dialog module is wired, loaded, and calls the route.

The behaviour lives in the route (pinned in test_aux_windows); this file defends the wiring: the
module exists and parses, the shell loads it, the View menu opens it, and it talks to the same
/api/control/windows route — with the reset action offered for every row, the monitor send and the
snap shapes on it, and the shape list equal to the API's own (`windows.PRESETS`).

§128 also pins the namespace split: windowing.js used to assign `window.OFAPWINDOWS`, which
windows-ui.js (loaded later) overwrote — so the View menu's entry called an undefined `open` and
the dialog was unreachable. One global per module now, and a pin so they cannot collide again.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from orderflow_system.desktop import windows as windows_mod

UI = Path(__file__).parent / "desktop" / "ui"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_module_exists_and_parses():
    node = shutil.which("node")
    assert node, "node is required for the UI gates"
    proc = subprocess.run([node, "--check", str(UI / "windowing.js")],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


def test_the_shell_loads_the_module():
    html = _text(UI / "index.html")
    assert '<script src="/desktop/windowing.js"></script>' in html
    assert "/desktop/chrome.js" in html


def test_the_view_menu_opens_the_dialog():
    assert "Windows & layouts" in _text(UI / "menubar.js")
    assert "OFAPWINMGR" in _text(UI / "menubar.js")


def test_the_two_window_namespaces_do_not_collide():
    """The measured defect: two modules assigned one global, the later load won, and the View
    menu's dialog entry became a no-op. One global each — windows-ui.js owns OFAPWINDOWS."""
    dialog = _text(UI / "windowing.js")
    menu = _text(UI / "windows-ui.js")
    assert "window.OFAPWINDOWS =" not in dialog, "windowing.js must not take windows-ui.js's global"
    assert "window.OFAPWINMGR =" not in menu, "windows-ui.js must not take the dialog's global"
    assert "window.OFAPWINMGR = {" in dialog
    assert "window.OFAPWINDOWS = {" in menu


def test_the_dialog_buttons_are_not_gated_on_a_view():
    """A measured regression in this file's first cut: the overlay handler gated EVERY row on
    `payload.view`, so Bring them home / Focus / Pin / Reset / Close all did nothing at all."""
    code = _text(UI / "windowing.js")
    assert "!payload.view" not in code, "the overlay handler must not require a view for every action"
    assert "payload.action === 'open_any'" in code, "the picker row must be the one that reads pickers"


def test_the_module_talks_to_the_window_route_and_offers_the_reset():
    code = _text(UI / "windowing.js")
    assert "/api/control/windows" in code
    assert "action: 'reset'" in code, "the reset action is not offered"
    assert "action: 'close_all'" in code
    assert "native" in code, "the no-host answer is not handled"


def test_the_dialog_offers_send_snap_and_the_unplug_rescue():
    code = _text(UI / "windowing.js")
    assert "action: 'move'" in code, "the send-to-monitor action is not offered"
    assert "action: 'arrange'" in code, "the bring-home rescue is not offered"
    assert "open_any" in code, "the open-any-panel row is missing"
    assert "stranded" in code, "the dialog never checks for windows on a missing monitor"


def test_every_shape_the_dialog_offers_is_a_shape_the_api_can_resolve():
    """Parity, not prose: the dialog's SHAPES and the menu's PRESETS must both be inside the
    server's list, or a click would ask for a rectangle nothing can compute."""
    listed = _text(UI / "windowing.js").split("const SHAPES = [", 1)[1].split("];", 1)[0]
    assert sorted(re.findall(r"\['([a-z]+)'", listed)) == sorted(windows_mod.PRESETS), \
        "the dialog's shapes drifted from PRESETS"
    presets = _text(UI / "windows-ui.js").split("const PRESETS = [", 1)[1].split("];", 1)[0]
    assert sorted(re.findall(r"'([a-z]+)'", presets)) == sorted(windows_mod.PRESETS), \
        "the menu's shapes drifted from PRESETS"


def test_the_widget_frame_carries_the_window_button_and_the_hotkeys_exist():
    shell = _text(UI / "shell.js")
    assert "widgetButton('⧉'" in shell, "the widget frame has no window button"
    assert "OFAPWINDOWS.openFor" in shell, "the button does not open the window menu"
    keys = _text(UI / "keys.js")
    assert "ctrl+alt+w" in keys and "win-menu" in keys, "no hotkey opens the window menu"
    assert "ctrl+alt+shift+arrowright" in keys, "no hotkey sends a panel to the next monitor"
    assert "ctrl+alt+shift+arrowleft" in keys, "no hotkey sends a panel to the previous monitor"


def test_the_send_hotkey_knows_a_single_monitor_has_nowhere_to_send_to():
    """Measured live: the first cut issued a step=1 move anyway, and with ONE screen that resolved
    to the same screen and re-centred a hand-placed window."""
    code = _text(UI / "windows-ui.js")
    assert "screens.length < 2" in code, "the send hotkey has no single-monitor guard"
