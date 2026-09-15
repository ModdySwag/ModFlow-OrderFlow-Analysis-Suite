"""The delivery layer (desktop/ui/bus.js) — one channel per (endpoint, params), refcounted.

Phase 4's gate is a countable claim: twelve widgets on the same symbol must cost ONE fetch per
interval, and three different symbols must cost three. That is arithmetic about keys, refcounts and
timers, so it is pinned in Node (`bus.selftest.js`) with a stub transport and a stopwatch, and this
file gates the invariants around it: the module is loaded after the layers it serves, it is registered
with the UI audit, it holds exactly one timer per channel, it stores nothing, and it never reaches for
the engine. A delivery layer that restarted ingest, or kept a second copy of state, would be worse than
no delivery layer at all.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).parent / "desktop" / "ui"
BUS = UI / "bus.js"
SHELL = UI / "shell.js"
SELFTEST = UI / "bus.selftest.js"
ROOT = Path(__file__).resolve().parents[1]


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_bus_files_exist():
    assert BUS.is_file(), "desktop/ui/bus.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/bus.selftest.js is missing"


def test_the_bus_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(BUS)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_bus_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, timeout=180,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"bus selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 10, f"the self-test shrank to {ok} checks — expected the channel arithmetic"
    assert proc.returncode == 0


def test_the_bus_exposes_the_documented_surface():
    src = _read(BUS)
    assert "window.OFAPBUS" in src or "OFAPBUS" in src
    for name in ("subscribe", "poll", "request", "stop", "stopAll", "install", "uninstall",
                 "telemetry", "summary", "reset", "canon", "VERSION"):
        assert name in src, f"bus.js must expose {name}"


def test_there_is_exactly_one_timer_per_channel():
    """The whole point: subscribers do not each get a timer. Exactly one setInterval exists in the
    module, it lives on the channel record, and it is cleared when the last subscriber leaves."""
    src = _read(BUS)
    assert src.count("setInterval(") == 1, "one timer, created on the channel — not one per subscriber"
    assert src.count("clearInterval(") == 1, "and exactly one place that stops it"
    subscribe = src[src.index("function subscribe"):src.index("function poll")]
    assert "channel.timer = setInterval(" in subscribe, "the channel owns its timer"
    assert "if (channel.refs <= 0) stop(channel.key);" in subscribe, "the last subscriber stops it"


def test_the_bus_stores_nothing_and_never_reaches_the_engine():
    src = _read(BUS)
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "/api/control/engine",
                      "WebSocket", "EventSource", "engine/start", "engine/stop"):
        assert forbidden not in src, f"bus.js must not touch {forbidden}"
    assert "Math.max(100," in src, "a poll interval is floored: a UI is not a benchmark"


def test_the_bus_is_loaded_after_the_layers_it_serves_and_registered():
    html = _read(UI / "index.html")
    assert 'src="/desktop/bus.js"' in html, "index.html must load the delivery layer"
    assert html.index('src="/desktop/shell.js"') < html.index('src="/desktop/bus.js"')
    assert html.index('src="/desktop/links.js"') < html.index('src="/desktop/bus.js"')
    assert "bus.js" in _read(ROOT / "scripts" / "audit_ui_refs.py"), "register it in JS_FILES"


def test_the_status_bar_carries_the_bus_telemetry():
    """The plan's status-bar item: what the delivery layer is doing, visible where the rest of the
    state is — and the suite still runs when the module is absent."""
    html = _read(UI / "index.html")
    shell = _read(SHELL)
    assert 'id="statusBus"' in html, "the status bar must have a bus field"
    assert "statusBus" in shell and "OFAPBUS" in shell, "and the shell must write it"
    assert "typeof bus.summary === 'function'" in shell, "guarded: no bus, no crash"
