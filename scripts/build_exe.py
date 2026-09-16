#!/usr/bin/env python3
"""Build ModFlow OrderFlow Analysis Suite as a standalone Windows executable.

No Hermes, no external service, no build-time dependency on anything outside this repo: the
entry point is the app's own `orderflow_system.main:main`, and the only extra payload is the
web UI that ships inside the package.

    .venv/Scripts/python.exe scripts/build_exe.py            # onedir (default: fast start)
    .venv/Scripts/python.exe scripts/build_exe.py --onefile  # single file, slower start

Output: dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe  (or dist/OrderFlowAnalysisPro.exe)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "ModFlowOrderFlowAnalysisSuite"
ENTRY = ROOT / "scripts" / "_exe_entry.py"
ICON = ROOT / "orderflow_system" / "desktop" / "ui" / "app.ico"

# Directories the frozen build must ship as data — module-level so `test_wiring` can pin them
# against what the shell actually loads. `dashboard/static` is required, not optional: six of its
# modules (footprint, orderbook, tape, signals, performance, microstructure) are loaded by the
# DESKTOP shell's own index.html (`/static/*.js`), and the UI instantiates their classes — a
# build without them answers 404 for all six and those widgets silently never initialise
# (measured on the first v0.1.0-beta exe, 2026-09-17; the repo tree was fine, which is why no
# test caught it — see test_wiring.test_the_frozen_build_ships_every_asset_root_the_shell_loads).
UI_REL = "orderflow_system/desktop/ui"
STATIC_REL = "orderflow_system/dashboard/static"
REQUIRED_DATA_RELS = (UI_REL, STATIC_REL)
# The Bookmap add-on jar ships the same way, beside its source: a fresh install can add it in
# Bookmap with no JDK and no build step, and the suite's card can point straight at the file.
ADDON_REL = "orderflow_system/data/bookmap_addon"

ENTRY_SOURCE = '''"""Frozen entry point — the app's own main, nothing else."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()          # PyInstaller: no re-exec of the parent process
    from orderflow_system.desktop.__main__ import main

    sys.exit(main())
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the standalone OFAP executable.")
    parser.add_argument("--onefile", action="store_true", help="single-file build (slower first start)")
    parser.add_argument("--clean", action="store_true", default=True, help="drop build/ before building")
    args = parser.parse_args()

    ENTRY.write_text(ENTRY_SOURCE, encoding="utf-8")

    # The web UI ships as data, keeping the package layout so `Path(__file__).parent / "ui"`
    # resolves identically in the frozen app (PyInstaller 6 puts data under `_internal/`).
    # `dashboard/static` ships too — the desktop shell loads six of its modules itself (see the
    # REQUIRED_DATA_RELS comment): without them the frozen app 404s those scripts and the
    # Footprint/Depth/Tape/Signals/Performance/Microstructure widgets never initialise. The
    # legacy page's own files ride along; they are small, and the legacy page stays on disk by design.
    script_icon = ROOT / "scripts" / "app.ico"
    icon = ICON if ICON.is_file() else (script_icon if script_icon.is_file() else None)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", APP_NAME,
        "--windowed",                          # no console window; the app logs to its own log file
        "--collect-submodules", "orderflow_system",
        "--collect-all", "uvicorn",
        "--collect-all", "webview",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--hidden-import", "clr_loader",
        "--hidden-import", "pythonnet",
        # numpy IS bundled: the MetaTrader5 bridge's native core imports it, and the portable
        # build ships the MT5 feed (the owner's call — ≈ +27 MB). The analytics engines themselves
        # stay stdlib-only (pinned by test_no_numpy.py + scripts/regen_analytics_golden.py), so
        # numpy rides along for MT5 alone. The rest of this list is hook collateral — nothing the
        # app can import needs any of it (pytz/tzdata/watchfiles ride in on other packages' hooks).
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "plotly",
        "--exclude-module", "kaleido",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pytz",
        "--exclude-module", "tzdata",
        "--exclude-module", "watchfiles",
        # MetaTrader5 is deliberately NOT excluded: with numpy bundled above, the bridge loads in
        # the frozen app and the MT5 feed works from the portable build (verified against a real
        # terminal, 2026-09-17).
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ]
    for rel in REQUIRED_DATA_RELS:
        src = ROOT / rel
        if not src.is_dir():
            print(f"build refused: {rel} is missing — the shell loads files from it, so a build "
                  f"without it ships dead widgets")
            return 1
        # source must be absolute: --specpath makes relative sources resolve inside build/
        cmd += ["--add-data", f"{src.as_posix()};{rel}"]
    if (ROOT / ADDON_REL).is_dir():
        cmd += ["--add-data", f"{(ROOT / ADDON_REL).as_posix()};{ADDON_REL}"]
    else:
        print(f"warning: {ADDON_REL} is missing — the frozen build will ship without the Bookmap "
              f"bridge add-on")
    if args.onefile:
        cmd.append("--onefile")
    if icon is not None:
        cmd += ["--icon", str(icon)]
    cmd.append(str(ENTRY))

    if args.clean and (ROOT / "build").is_dir():
        shutil.rmtree(ROOT / "build", ignore_errors=True)

    print("building:", " ".join(cmd[:6]), "...")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        print(f"build failed: exit {proc.returncode}")
        return proc.returncode

    target = (ROOT / "dist" / f"{APP_NAME}.exe") if args.onefile else (ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe")
    if not target.is_file():
        print(f"build reported success but {target} is missing")
        return 1
    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"built {target} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
