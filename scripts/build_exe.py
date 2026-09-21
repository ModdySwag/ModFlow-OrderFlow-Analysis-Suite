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
import json
import hashlib
import re
import shutil
import subprocess
import sys
import time
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
#: SEC-34: the NinjaTrader bridge is the same kind of artefact — a folder of files the platform's
#: side loads, not a Python package. `--collect-submodules orderflow_system` finds the READER
#: (data/ninjatrader_feed.py) but never this folder, so the frozen build shipped without the bridge
#: while the UI described it as part of the install.
ADDON_RELS = (ADDON_REL, "orderflow_system/data/ninjatrader_bridge")

ENTRY_SOURCE = '''"""Frozen entry point — the app's own main, nothing else."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()          # PyInstaller: no re-exec of the parent process
    from orderflow_system.desktop.__main__ import main

    sys.exit(main())
'''


#: Windows version resource for the exe (audit F-02): the shipped binary had NO version metadata
#: while the installer and the in-app About said 0.1.0 — every release-facing file disagreed.
_VS_VERSION = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v0}, {v1}, {v2}, 0), prodvers=({v0}, {v1}, {v2}, 0),
                    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'ModdySwag'),
        StringStruct('FileDescription', 'ModFlow OrderFlow Analysis Suite'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', '{name}'),
        StringStruct('OriginalFilename', '{name}.exe'),
        StringStruct('ProductName', 'ModFlow OrderFlow Analysis Suite'),
        StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def _project_version() -> str:
    """The version from pyproject.toml — one source, so the exe cannot drift from the package."""
    try:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


def _version_quad(version: str) -> tuple[int, int, int]:
    parts = []
    for chunk in str(version).split(".")[:3]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def write_version_file() -> Path:
    """Generate build/version_info.txt for PyInstaller's --version-file (audit F-02)."""
    version = _project_version()
    v0, v1, v2 = _version_quad(version)
    out = ROOT / "build" / "version_info.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_VS_VERSION.format(v0=v0, v1=v1, v2=v2, version=version, name=APP_NAME),
                   encoding="utf-8")
    return out


def clean_superseded_artifacts(dist_root: Path) -> list[Path]:
    """Delete last release's setup/zip/SBOM from dist/ before a new build (F-04).

    dist/ kept one of each per version forever (the same class of residue the build/ wipe
    already handled); a release build must leave exactly one of each behind.
    """
    removed: list[Path] = []
    if not dist_root.is_dir():
        return removed
    for pattern in (f"{APP_NAME}-Setup-*.exe", f"{APP_NAME}-Setup-*.exe.sha256",
                    f"{APP_NAME}-win64.zip", f"{APP_NAME}-win64.sbom.cdx.json"):
        for stale in dist_root.glob(pattern):
            try:
                stale.unlink()
                removed.append(stale)
            except OSError:
                pass
    return removed


def prune_developer_files(dist_dir: Path) -> int:
    """Drop developer-only files from the shipped payload (audit MEM-F-06).

    The UI's 35 `*.selftest.js` harnesses (385 KB) are how the engine's maths is verified — they
    are not runtime assets, and shipping them hands every user a copy of the test suite. The build
    keeps them in the repository and in the wheel; only the frozen payload loses them.
    """
    removed = 0
    for path in list(dist_dir.rglob("*.selftest.js")):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    # F-06: `--collect-all numpy` ships numpy's own test suite and sources. Targeted and
    # conservative: only paths under a numpy tree, only test/source artefacts.
    for pattern in ("_internal/numpy/**/tests/**", "_internal/numpy/**/test_*.py",
                    "_internal/numpy/**/*.pyi", "_internal/numpy/**/*.f90",
                    "_internal/numpy/**/*.pyx",
                    # F-06, continued: `--collect-all numpy` also drags in the compiled test
                    # extensions (numpy/_core/*_tests*.pyd and their import .lib) — a few MB of
                    # modules nothing imports outside numpy's own test runner.
                    "_internal/numpy/**/*_tests*.pyd", "_internal/numpy/**/*_tests*.lib"):
        for path in list(dist_dir.glob(pattern)):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def collect_licences(dist_dir: Path, site_packages: Path | None = None) -> tuple[int, int]:
    """Copy the bundled distributions' licence texts into the payload (audit SEC-32).

    The audit's count: the frozen payload carried 9 licence dirs for 21 bundled module dirs —
    the notices table names every licence, but the TEXTS only travelled for the few packages
    PyInstaller happened to copy metadata for. This walks the built ``_internal``, maps each
    bundled top-level package back to its installed distribution, and copies every licence file
    that distribution records (its ``dist-info/licenses`` tree, plus any LICENSE/COPYING/NOTICE
    file it lists). The repo's own LICENSE and THIRD_PARTY_NOTICES.md are copied beside the exe
    so an install carries its own disclosures. Returns ``(distributions, files)`` copied.
    """
    import sysconfig
    from importlib.metadata import distributions

    internal = dist_dir / "_internal"
    if not internal.is_dir():
        return (0, 0)
    site = Path(site_packages) if site_packages is not None else Path(sysconfig.get_paths()["purelib"])

    tops = {
        p.name for p in internal.iterdir()
        if p.is_dir() and not p.name.endswith(".dist-info") and p.name != "orderflow_system"
    }
    tops.discard("numpy.libs")                    # shared libraries, licensed with numpy itself
    wanted: set[str] = set()
    if site == Path(sysconfig.get_paths()["purelib"]):
        from importlib.metadata import packages_distributions
        mapping = packages_distributions()        # the right answer for odd names (PyYAML → yaml)
        wanted |= {d for t in tops for d in mapping.get(t, [])}
    installed = {str(dist.metadata.get("Name") or ""): dist for dist in distributions(path=[str(site)])}
    by_norm = {name.lower().replace("-", "_"): name for name in installed if name}
    for t in tops:                                # normalized-name fallback (also the test path)
        norm = t.lower().replace("-", "_")
        if norm in by_norm:
            wanted.add(by_norm[norm])

    licence_re = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE)([.\-_].*)?$", re.IGNORECASE)
    out_root = internal / "THIRD_PARTY_LICENCES"
    dists_copied = files_copied = 0
    for name, dist in sorted(installed.items()):
        if name not in wanted:
            continue
        written = 0
        for entry in dist.files or []:
            parts = list(entry.parts)
            if not parts or ".." in parts:
                continue
            text = entry.as_posix()
            if "/licenses/" not in text and not licence_re.match(parts[-1]):
                continue
            src = Path(dist.locate_file(entry))
            if not src.is_file():
                continue
            dest = out_root / name / Path(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            written += 1
        if written:
            dists_copied += 1
            files_copied += written
    for source in (ROOT / "LICENSE", ROOT / "THIRD_PARTY_NOTICES.md"):
        if source.is_file():
            shutil.copyfile(source, dist_dir / source.name)
    if files_copied:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "README.txt").write_text(
            "Licence texts for the third-party Python distributions bundled in this build.\n"
            "One folder per distribution; the modules themselves live in the parent _internal directory.\n"
            "The suite's own notices are in THIRD_PARTY_NOTICES.md beside the executable.\n",
            encoding="utf-8")
    return (dists_copied, files_copied)


def write_build_stamp(target: Path) -> Path:
    """Record what this artifact was built from — commit, worktree state, exe hash (audit F-01).

    A published binary must be traceable to a commit; the release-evidence page carried stale
    hashes because nothing tied the artifact to the tree it came from.
    """
    sha = ""
    dirty = ""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True,
                             text=True, encoding="utf-8", timeout=20).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True,
                               text=True, encoding="utf-8", timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    exe_sha = ""
    try:
        exe_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError:
        pass
    stamp = {
        "app": APP_NAME,
        "version": _project_version(),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "commit": sha,
        "worktree_state": "dirty" if dirty else "clean",
        "exe_sha256": exe_sha,
        "python": sys.version.split()[0],
    }
    out = target.parent / "BUILD_INFO.json"
    out.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the standalone OFAP executable.")
    parser.add_argument("--onefile", action="store_true", help="single-file build (slower first start)")
    parser.add_argument("--clean", action="store_true", default=True, help="drop build/ before building")
    parser.add_argument("--release", action="store_true",
                        help="release build: refuse to stamp an artifact from a dirty worktree (F-08)")
    args = parser.parse_args()

    if args.release:
        dirty = ""
        try:
            dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                   capture_output=True, text=True, encoding="utf-8", timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            dirty = ""
        if dirty:
            print("--release refuses to build from a dirty worktree — commit or stash first:",
                  file=sys.stderr)
            for line in dirty.splitlines()[:10]:
                print("   " + line, file=sys.stderr)
            return 1

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
        # numpy is bundled ON PURPOSE: the MetaTrader5 bridge's native core imports it at load,
        # and the portable build ships the MT5 feed (the owner's call — ≈ +27 MB). The analytics
        # engines stay stdlib-only (pinned by test_no_numpy.py + scripts/regen_analytics_golden.py)
        # — and since NOTHING in the tree imports numpy any more, the import graph never reaches
        # it: without this collect the bridge silently lost its dependency (measured 2026-09-19:
        # a build whose _internal carried MetaTrader5 without numpy answered "MetaTrader5 package
        # not installed" from the frozen app). The rest of this list is hook collateral — nothing
        # the app can import needs any of it (pytz/tzdata/watchfiles ride in on other packages'
        # hooks).
        "--collect-all", "numpy",
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
    for rel in ADDON_RELS:
        if (ROOT / rel).is_dir():
            cmd += ["--add-data", f"{(ROOT / rel).as_posix()};{rel}"]
        else:
            print(f"warning: {rel} is missing — the frozen build will ship without that bridge "
                  f"add-on")
    # SEC-34: `--collect-submodules orderflow_system` walks the whole package, test modules
    # included — they were verifiably inside the release PYZ (fixtures, fake tokens, nothing a
    # user needs). Excluded by name, from the tree, so a new test file is excluded automatically.
    for test_file in sorted((ROOT / "orderflow_system").glob("test_*.py")):
        cmd += ["--exclude-module", f"orderflow_system.{test_file.stem}"]

    if args.onefile:
        cmd.append("--onefile")
    if icon is not None:
        cmd += ["--icon", str(icon)]
    # --clean must run BEFORE the version resource is written: the rmtree used to run after
    # write_version_file(), deleting the file PyInstaller was then told to load.
    if args.clean and (ROOT / "build").is_dir():
        shutil.rmtree(ROOT / "build", ignore_errors=True)
    # F-04: dist/ kept one setup/zip/SBOM per version forever; the same wipe rule as build/.
    stale_artifacts = clean_superseded_artifacts(ROOT / "dist")
    if stale_artifacts:
        print(f"dist/: removed {len(stale_artifacts)} superseded artifact(s)")
    cmd += ["--version-file", str(write_version_file())]     # audit F-02: version metadata on the exe
    cmd.append(str(ENTRY))

    print("building:", " ".join(cmd[:6]), "...")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        print(f"build failed: exit {proc.returncode}")
        return proc.returncode

    target = (ROOT / "dist" / f"{APP_NAME}.exe") if args.onefile else (ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe")
    if not target.is_file():
        print(f"build reported success but {target} is missing")
        return 1
    pruned = prune_developer_files(target.parent)            # audit E-07: no dev harnesses in the payload
    if pruned:
        print(f"pruned {pruned} developer file(s) from the payload")
    licence_dists, licence_files = collect_licences(target.parent)   # audit SEC-32: the texts ship
    if licence_files:
        print(f"licence texts: {licence_files} file(s) from {licence_dists} distribution(s)"
              " -> _internal/THIRD_PARTY_LICENCES + LICENSE/THIRD_PARTY_NOTICES.md beside the exe")
    size_mb = target.stat().st_size / (1024 * 1024)
    stamp = write_build_stamp(target)                        # audit F-01: traceable artifact
    print(f"built {target} ({size_mb:.1f} MB)")
    print(f"build stamp: {stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
