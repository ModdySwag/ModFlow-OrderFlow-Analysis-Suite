#!/usr/bin/env python3
"""Golden snapshot of every instrument config — the safety net for settings refactors.

Why it exists: `config/settings.py` used to spell out ~650 lines of near-identical
constructors, one per instrument. Collapsing that into a class bank + per-instrument
overrides is only safe if "nothing changed" is a *verified* statement, not a promise —
so every config the app can produce is serialised to one canonical JSON file and
compared on every test run.

    .venv/Scripts/python.exe scripts/regen_config_golden.py            # check (exit 1 on drift)
    .venv/Scripts/python.exe scripts/regen_config_golden.py --write    # accept a deliberate change

A deliberate change is a one-line diff in the golden file review: exactly the entry
that changed, key by key.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "orderflow_system" / "testdata" / "config_golden.json"


def canonical(obj: Any) -> Any:
    """Dataclass/enum tree → JSON-safe structure, keys sorted, floats untouched."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: canonical(getattr(obj, f.name)) for f in sorted(dataclasses.fields(obj), key=lambda f: f.name)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [canonical(v) for v in obj]
    return obj


def snapshot() -> dict[str, Any]:
    """Everything the app can build, keyed by symbol (and by factory for the wrappers)."""
    from orderflow_system.config import settings as S

    out: dict[str, Any] = {"factories": {}, "all_configs": [], "crypto_majors": {}}

    # 1. every no-argument factory the module exposes
    for name in sorted(dir(S)):
        if not (name.startswith("get_") and name.endswith("_config")):
            continue
        fn = getattr(S, name)
        if not callable(fn):
            continue
        try:
            cfg = fn()
        except TypeError:
            continue                       # needs a symbol argument (get_crypto_config)
        out["factories"][name] = canonical(cfg)

    # 2. the crypto family, one entry per major (the tick sizes matter here)
    for symbol in sorted(S.CRYPTO_MAJORS):
        out["crypto_majors"][symbol] = canonical(S.get_crypto_config(symbol))

    # 3. what the desktop app actually iterates, in order
    out["all_configs"] = [
        {"symbol": cfg.instrument.value, "tick_size": cfg.tick_size,
         "session": cfg.volume_profile.session.value, "vp_tick": cfg.volume_profile.tick_size}
        for cfg in S.get_all_configs()
    ]
    return out


def main() -> int:
    payload = snapshot()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if "--write" in sys.argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
        print(f"wrote {GOLDEN} ({len(text)} bytes, "
              f"{len(payload['factories'])} factories, {len(payload['crypto_majors'])} crypto majors, "
              f"{len(payload['all_configs'])} instruments)")
        return 0

    if not GOLDEN.is_file():
        print(f"MISSING golden file: {GOLDEN}\nRun with --write to create it.")
        return 1
    current = GOLDEN.read_text(encoding="utf-8")
    if current == text:
        print(f"golden matches: {len(payload['factories'])} factories, "
              f"{len(payload['crypto_majors'])} crypto majors, {len(payload['all_configs'])} instruments")
        return 0

    # name exactly what drifted — a config refactor must be a no-op, so this is a bug
    before = json.loads(current)
    for section in sorted(set(before) | set(payload)):
        if before.get(section) == payload.get(section):
            continue
        a, b = before.get(section), payload.get(section)
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if a.get(key) != b.get(key):
                    print(f"DRIFT {section}.{key}:\n  golden: {json.dumps(a.get(key))}\n  now:    {json.dumps(b.get(key))}")
        else:
            print(f"DRIFT {section}:\n  golden: {json.dumps(a)}\n  now:    {json.dumps(b)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
