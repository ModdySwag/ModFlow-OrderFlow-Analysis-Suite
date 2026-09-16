"""The runtime tree does not import numpy — the reason the frozen build lost 27 MB.

Two checks, because they fail differently:

1. A source scan of every module the app can import (tests excluded). It catches a new
   `import numpy` the moment it lands, before any build.
2. A subprocess that blocks numpy (`sys.modules["numpy"] = None`) and imports the whole
   legacy pipeline chain — `orderflow_system.main` pulls analytics, patterns and signals,
   which is exactly where numpy used to come from. If any of them still needed it, the
   import raises here instead of in the frozen build on a user's machine.

numpy is still installed in the dev venv; it is simply nothing the app may reach for,
because `scripts/build_exe.py` excludes it from the frozen build.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT_RE = re.compile(r"^\s*(?:import\s+numpy|from\s+numpy)\b", re.MULTILINE)

BLOCKED_IMPORT = (
    "import sys\n"
    "sys.modules['numpy'] = None\n"          # any 'import numpy' now raises ImportError
    "import orderflow_system.main as main\n"
    "from orderflow_system.analytics.delta import DeltaEngine\n"
    "from orderflow_system.analytics.volume_profile import VolumeProfileEngine\n"
    "from orderflow_system.patterns.absorption import AbsorptionDetector\n"
    "from orderflow_system.signals.profile_framing import ProfileFramingEngine\n"
    "from orderflow_system.config.settings import VolumeProfileConfig\n"
    "from orderflow_system.data.models import Side, Tick\n"
    "ticks = [Tick(1_700_000_000_000 + i * 250, 18500.0, 10.0, Side.BUY) for i in range(60)]\n"
    "ticks += [Tick(1_700_000_020_000 + i * 250, 18490.0, 4.0, Side.SELL) for i in range(20)]\n"
    "vp = VolumeProfileEngine(VolumeProfileConfig()).compute_from_ticks(ticks, 'blocked')\n"
    "delta = DeltaEngine(tick_size=0.1)\n"
    "for i in range(6):\n"
    "    delta.compute_from_ticks(ticks[i * 10:(i + 1) * 10])\n"
    "print('imports ok', DeltaEngine.__name__, VolumeProfileEngine.__name__,\n"
    "      AbsorptionDetector.__name__, ProfileFramingEngine.__name__, main.OrderflowSystem.__name__)\n"
    "print('computed', vp.poc, vp.shape, round(delta.get_delta_roc(5), 6),\n"
    "      round(delta.get_volume_trend(5), 6), round(delta.cumulative_delta, 6))\n"
)


def test_no_module_in_the_runtime_tree_imports_numpy():
    offenders = []
    for path in sorted((ROOT / "orderflow_system").rglob("*.py")):
        if path.name.startswith("test_") or "test" in path.parts:
            continue
        if IMPORT_RE.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        "numpy is excluded from the frozen build (scripts/build_exe.py) — these modules would "
        "break inside it:\n  " + "\n  ".join(offenders))


def test_the_pipeline_imports_and_computes_with_numpy_blocked():
    proc = subprocess.run(
        [sys.executable, "-c", BLOCKED_IMPORT],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, (
        "the analytics pipeline still needs numpy:\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
    assert "imports ok" in proc.stdout
    assert "computed 18500.0" in proc.stdout, proc.stdout
