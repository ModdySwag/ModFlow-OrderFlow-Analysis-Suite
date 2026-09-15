"""Golden snapshot of every instrument config (plan T43) — the safety net for Phase 5.

`config/settings.py` spelled out one near-identical constructor per instrument (about
650 lines of repeated numbers). Phase 5 collapses that into a per-class bank plus
per-instrument overrides, and this test is what makes that safe: every config the app
can build — all factories, the whole crypto family, and the ordered list the desktop
app iterates — is compared key-by-key against `testdata/config_golden.json`.

A refactor must therefore be a **no-op** here. A deliberate change is one command and
one reviewed diff:

    .venv/Scripts/python.exe scripts/regen_config_golden.py --write

and the diff should be exactly the entry you meant to change (that is T45's evidence).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import regen_config_golden as golden  # noqa: E402  (path set above)


def test_golden_file_exists():
    assert golden.GOLDEN.is_file(), (
        f"missing {golden.GOLDEN} — generate it with "
        "`.venv/Scripts/python.exe scripts/regen_config_golden.py --write`")


def test_every_config_matches_the_golden_snapshot():
    """The whole point: a settings refactor that changes any number fails here."""
    stored = json.loads(golden.GOLDEN.read_text(encoding="utf-8"))
    now = golden.snapshot()

    for section in ("factories", "crypto_majors", "all_configs"):
        before, after = stored.get(section), now.get(section)
        if before == after:
            continue
        if isinstance(before, dict) and isinstance(after, dict):
            drifted = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            detail = []
            for key in drifted[:6]:
                b, a = before.get(key), after.get(key)
                if isinstance(b, dict) and isinstance(a, dict):
                    for field in sorted(set(b) | set(a)):
                        if b.get(field) != a.get(field):
                            detail.append(f"  {key}.{field}: golden={b.get(field)!r} now={a.get(field)!r}")
                else:
                    detail.append(f"  {key}: golden={b!r} now={a!r}")
            pytest.fail(f"{section} drifted from the golden snapshot:\n" + "\n".join(detail))
        pytest.fail(f"{section} length changed: golden={len(before or [])} now={len(after or [])}")


def test_snapshot_covers_every_instrument_the_app_builds():
    """A net with holes is worse than no net: assert its coverage explicitly."""
    payload = golden.snapshot()
    symbols = [row["symbol"] for row in payload["all_configs"]]
    assert len(symbols) == len(set(symbols)), "get_all_configs() must not repeat an instrument"
    assert len(symbols) >= 45, f"only {len(symbols)} instruments covered"
    assert "BTCUSDT" in symbols and "NAS100USDT" in symbols and "EURUSD" in symbols
    assert payload["crypto_majors"], "the crypto family must be snapshotted"
    assert len(payload["factories"]) >= 30


def test_wrappers_agree_with_get_all_configs():
    """Every factory that appears in get_all_configs() must produce the same numbers
    as the ordered list — a thin wrapper that drifts from the list is a silent bug."""
    payload = golden.snapshot()
    listed = {row["symbol"]: row for row in payload["all_configs"]}
    for name, cfg in payload["factories"].items():
        symbol = cfg["instrument"]
        if symbol not in listed:
            continue
        row = listed[symbol]
        assert cfg["tick_size"] == row["tick_size"], f"{name}: tick size differs from get_all_configs()"
        assert cfg["volume_profile"]["session"] == row["session"], f"{name}: session differs"
        assert cfg["volume_profile"]["tick_size"] == row["vp_tick"], f"{name}: profile tick differs"
