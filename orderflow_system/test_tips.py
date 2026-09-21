"""Gate for the novelty-gated tips layer (v2 report §7-7, closed 2026-09-19).

The deciding half (which tips show, in what order, capped, and that a broken check silences a tip
rather than nagging) runs in the Node selftest. This file pins the wiring: the module loads and is
audited, the card mounts into the Guide, and every door points at something that exists — a real
view, a real help topic, or the menu.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _run_selftest():
    node = shutil.which("node") or "node"
    res = subprocess.run([node, str(UI / "tips.selftest.js")], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    return res.stdout


def test_selftest_passes_with_real_coverage():
    out = _run_selftest()
    m = re.search(r"tips selftest: (\d+) ok, 0 failed", out)
    assert m and int(m.group(1)) >= 10, out


def test_module_loads_in_the_shell_and_the_audit_sees_it():
    js = (UI / "tips.js").read_text(encoding="utf-8")
    assert "window.OFAPTIPS" in js
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '<script src="/desktop/tips.js"></script>' in html
    audit = (PKG.parent / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"tips.js"' in audit
    ledger = (PKG / "test_listener_balance.py").read_text(encoding="utf-8")
    assert '"tips.js"' in ledger, "the DOMContentLoaded add must be in the ledger"


def test_the_card_mounts_into_the_guide():
    js = (UI / "tips.js").read_text(encoding="utf-8")
    assert "getElementById('guideBody')" in js
    assert "Try next" in js and "tipsCard" in js
    assert "retires" in js


def test_every_door_points_at_something_real():
    js = (UI / "tips.js").read_text(encoding="utf-8")
    html = (UI / "index.html").read_text(encoding="utf-8")
    views = set(re.findall(r'data-view="([^"]+)"', html))
    help_js = (UI / "help-data.js").read_text(encoding="utf-8")
    topic_ids = set(re.findall(r"id: '([^']+)'", help_js))
    doors = re.findall(r"door: \{ label: '[^']*', (view|help|menu): (true|'[^']+')", js)
    assert len(doors) >= 4, doors
    for kind, target in doors:
        if kind == "view":
            v = target.strip("'")
            assert v in views, f"tip door targets unknown view {v}"
        elif kind == "help":
            t = target.strip("'")
            assert t in topic_ids, f"tip door targets unknown help topic {t}"
        else:
            assert target == "true", "menu door must be menu: true"
