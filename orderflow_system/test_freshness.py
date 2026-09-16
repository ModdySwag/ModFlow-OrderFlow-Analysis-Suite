"""P1-10's gate: the age policy is one module, the payloads carry ages, and the chip store is wired.

The policy lives in `atlas/freshness.py`; the UI mirrors its windows in
`desktop/ui/freshness.js` and this file pins the two tables EQUAL, so neither side can drift
alone. The crossvenue payload keys are a regression (the refactor moved the policy out of it),
and the engine's age block is a real payload check on the stopped engine (every age unknown —
nothing invented). The chip store's own behaviour is keys.selftest-style: shelled out to
`freshness.selftest.js`.

Deliberately dumb: source text and public functions in, assertions out, no browser.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
INDEX = UI / "index.html"
FRESH_JS = UI / "freshness.js"
SELFTEST = UI / "freshness.selftest.js"

from orderflow_system.atlas import freshness  # noqa: E402


def test_the_policy_module_is_the_one_home():
    assert freshness.STALE_DEPTH_MS == 5_000
    assert freshness.STALE_QUOTE_MS == 60_000
    assert freshness.WINDOWS_MS == {"depth": 5_000, "quote": 60_000, "trades": 5_000, "candles": 60_000}
    assert freshness.window_ms("depth") == 5_000
    assert freshness.window_ms("nothing-declared") == freshness.DEFAULT_WINDOW_MS


def test_assess_reports_an_unknown_clock_as_unknown():
    now = 1_000_000
    known = freshness.assess("depth", now - 7_000, now)
    assert known == {"age_ms": 7_000, "age_known": True, "window_ms": 5_000, "stale": True}
    unknown = freshness.assess("depth", 0, now)
    assert unknown["age_known"] is False and unknown["stale"] is False
    edge = freshness.assess("quote", now - 60_000, now)
    assert edge["stale"] is False, "exactly at the window is aging, not stale"
    past = freshness.assess("quote", now - 60_001, now)
    assert past["stale"] is True
    override = freshness.assess("depth", now - 7_000, now, window=60_000)
    assert override["window_ms"] == 60_000 and override["stale"] is False


def test_crossvenue_rows_kept_their_shape():
    from orderflow_system.atlas.crossvenue import VenueTop
    row = VenueTop(venue="v", kind="depth", bid=1.0, ask=2.0, ts_ms=100_000).to_dict(107_000)
    for key in ("age_ms", "age_known", "stale_after_ms", "stale", "ok", "ts_ms"):
        assert key in row, f"crossvenue lost {key}"
    assert row["age_ms"] == 7_000 and row["stale"] is True and row["ok"] is False
    from orderflow_system.atlas.crossvenue import STALE_DEPTH_MS, STALE_QUOTE_MS, stale_window_ms  # noqa: F401
    assert STALE_DEPTH_MS == freshness.STALE_DEPTH_MS and STALE_QUOTE_MS == freshness.STALE_QUOTE_MS
    assert stale_window_ms("quote") == 60_000


def test_the_engine_payloads_carry_ages():
    from orderflow_system.desktop import engine as engine_mod
    live = engine_mod.engine.live_status()
    age = live.get("age")
    assert isinstance(age, dict) and age, "live_status has no age block"
    for key in ("tape", "footprint", "candles", "orderbook"):
        assert key in age, f"live_status age block lost {key}"
        for field in ("age_ms", "age_known", "window_ms", "stale"):
            assert field in age[key], f"age.{key} lost {field}"
    assert age["orderbook"]["age_known"] is False, "the book's clock is the venue's — unknown by policy"
    stopped = engine_mod.engine.status()
    assert isinstance(stopped.get("per_symbol"), list)


def test_the_ui_table_mirrors_the_policy():
    text = FRESH_JS.read_text(encoding="utf-8", errors="replace")
    found = re.search(r"var WINDOWS = \{([^}]+)\}", text)
    assert found, "freshness.js lost its WINDOWS table"
    pairs = dict(re.findall(r"(\w+):\s*(\d+)", found.group(1)))
    as_ints = {k: int(v) for k, v in pairs.items()}
    assert as_ints == freshness.WINDOWS_MS, (
        f"the UI windows drifted from atlas/freshness.py: {as_ints} != {freshness.WINDOWS_MS}")


def test_the_module_and_its_selftest_exist_and_parse():
    assert FRESH_JS.is_file() and SELFTEST.is_file()
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, "--check", str(FRESH_JS)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


def test_the_chip_store_selftest_passes():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run([node, str(SELFTEST)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    found = re.search(r"freshness selftest: (\d+) ok, (\d+) failed", out)
    assert found, f"the selftest printed no verdict:\n{out}"
    assert found.group(2) == "0"
    assert int(found.group(1)) >= 20, f"only {found.group(1)} checks ran — the selftest shrank"


def test_every_stamped_panel_view_exists():
    text = FRESH_JS.read_text(encoding="utf-8", errors="replace")
    found = re.search(r"var PANELS = \[([^\]]+)\]", text)
    assert found, "freshness.js lost its PANELS list"
    panels = re.findall(r"'([a-z0-9_-]+)'", found.group(1))
    assert len(panels) >= 10, f"only {len(panels)} panels listed"
    html = INDEX.read_text(encoding="utf-8", errors="replace")
    missing = [p for p in panels if f'data-view="{p}"' not in html]
    # the scanner view is BUILT by its own module (scanEnsureView) after boot, so it is the one
    # panel whose chip is attached there rather than by freshness.js's boot pass — pinned instead.
    assert missing == ["scanner"], f"stamped panels with no view section: {missing}"
    scanner = (UI / "scanner.js").read_text(encoding="utf-8", errors="replace")
    assert "OFAPFRESH.chip" in scanner, "the scanner builds its own view; it must attach its own chip"


def test_the_map_is_loaded_and_audited():
    html = INDEX.read_text(encoding="utf-8", errors="replace")
    assert '<script src="/desktop/freshness.js"></script>' in html, "freshness.js is not loaded"
    audit = (ROOT / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8", errors="replace")
    assert '"freshness.js"' in audit, "freshness.js is missing from JS_FILES"
