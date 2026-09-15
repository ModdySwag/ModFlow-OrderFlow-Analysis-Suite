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
    ui_rel = "orderflow_system/desktop/ui"
    # The Bookmap add-on jar ships the same way, beside its source: a fresh install can add it in
    # Bookmap with no JDK and no build step, and the suite's card can point straight at the file.
    addon_rel = "orderflow_system/data/bookmap_addon"
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
        # source must be absolute: --specpath makes relative sources resolve inside build/
        "--add-data", f"{(ROOT / ui_rel).as_posix()};{ui_rel}",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ]
    if (ROOT / addon_rel).is_dir():
        cmd += ["--add-data", f"{(ROOT / addon_rel).as_posix()};{addon_rel}"]
    else:
        print(f"warning: {addon_rel} is missing — the frozen build will ship without the Bookmap "
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
