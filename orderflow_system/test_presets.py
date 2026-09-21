"""Gate for the preset combobox (control-surface audit §4 — the "common values, else your own"
pattern), plus the D-group's small truths: the settings "was" diff, the toast Help door, and the
profile status chip.

The pure half of presets.js runs in its Node selftest; this file pins the wiring: the module
exists and parses, it is loaded by the shell and registered with the audit, all 19 controls carry
their expected spec, and the small additions land where the surface reads them.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"

#: id -> the spec the markup must carry (values are the input's own domain).
PRESETS = {
    "ofxVaPct": "0.6,0.68,0.7,0.8,0.9",
    "ofxLambda": "100,250,500,1000,2000",
    "ofxStack": "2,3,5,8",
    "ofxR": "2,4,8",
    "ofxMinBlock": "0,10,50,100",
    "setCooldown": "0,15,30,60,300",
    "setScore": "20,40,60,80",
    "calLead": "5,15,30,60,240",
    "calHours": "12,24,48,72,168",
    "stRetention": "0,7,14,30,90,365",
    "stPruneInterval": "1,6,12,24",
    "stBackupInterval": "6,12,24,72",
    "stBackupKeep": "3,5,10,20",
    "updInterval": "1,6,12,24",
    "stMaxDb": "0,500,1000,2000",
    "stSmtpPort": "25,465,587,2525",
    "hmColThreshold": "0,500,1000,5000",
    "rpFrom": "15,60,240,1440",
    "rpTo": "0,15,60,240",
}


def test_module_and_wiring():
    js = (UI / "presets.js").read_text(encoding="utf-8")
    assert "window.OFAPPRESETS" in js
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '<script src="/desktop/presets.js"></script>' in html
    audit = (PKG.parent / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"presets.js"' in audit, "the audit's JS_FILES must carry it"


def test_every_control_carries_its_spec():
    html = (UI / "index.html").read_text(encoding="utf-8")
    for input_id, spec in PRESETS.items():
        needle = f'id="{input_id}" data-presets="{spec}"'
        assert needle in html, f"{input_id} lost its preset spec"


def test_the_selftest_passes():
    node = shutil.which("node") or "node"
    res = subprocess.run([node, str(UI / "presets.selftest.js")], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    m = re.search(r"presets selftest: (\d+) ok, 0 failed", res.stdout)
    assert m and int(m.group(1)) >= 12, res.stdout


def test_settings_staged_rows_show_the_was_value():
    js = (UI / "settings-pro.js").read_text(encoding="utf-8")
    assert "was " in js and "state.applied[p.path]" in js and "set-was" in js


def test_toast_carries_a_help_door():
    js = (UI / "ui.js").read_text(encoding="utf-8")
    assert "function toast(el, text, kind = 'info', topic = '')" in js
    assert "toast-topic" in js
    assert "fix.engine_error" in js and "fix.skipped_symbols" in js and "fix.no_instruments" in js


def test_profile_chip_is_wired():
    js = (UI / "profiles.js").read_text(encoding="utf-8")
    assert "paintProfileChip" in js
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'id="statusProfileChip"' in html


def test_the_chip_can_be_repaired_after_a_programmatic_write():
    """A preset pick drives its input's own change path — but a PROGRAMMATIC write (a params
    re-read, a settings render) fires no event, so the chip would keep naming the value the field
    no longer holds. presets.js must expose the repair, and the mass re-seeds must call it."""
    js = (UI / "presets.js").read_text(encoding="utf-8")
    assert "input.__ofapSync = syncFromInput;" in js, "decorate no longer leaves a repair handle"
    assert "function refresh(root)" in js, "presets.js lost its refresh()"
    assert "refresh: refresh" in js, "the repair is not exported"
    for fname, minimum in (("ofx-view.js", 2), ("ui.js", 1), ("calendar.js", 1), ("heatmap-pro.js", 1)):
        src = (UI / fname).read_text(encoding="utf-8")
        calls = src.count("OFAPPRESETS.refresh")
        assert calls >= minimum, f"{fname} stopped re-pairing preset chips after a programmatic write ({calls})"
