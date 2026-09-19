#!/usr/bin/env python3
"""Build the release zip and SBOM from the frozen payload (F-04).

The zip and the CycloneDX SBOM used to be assembled by hand at release time, which is how the
release-evidence page drifted from the artifacts actually uploaded. Both are reproducible here:

    python scripts/make_release.py            # zip + SBOM from dist/<APP>/
    python scripts/make_release.py --sbom-only

The SBOM comes from ``uv export --frozen --format cyclonedx1.5 --extra mt5`` — the same command
CI uses — and the zip mirrors ``dist/<APP>/`` file for file.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "ModFlowOrderFlowAnalysisSuite"
DIST = ROOT / "dist"
PAYLOAD = DIST / APP_NAME


def _project_version() -> str:
    try:
        import tomllib

        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version") or "0.0.0")
    except Exception:                                  # pragma: no cover - metadata is best effort
        return "0.0.0"


def build_zip(payload: Path = PAYLOAD) -> Path:
    """Zip the frozen payload, entry names relative to dist/ (the documented shape)."""
    if not payload.is_dir():
        raise SystemExit(f"no payload at {payload} — run scripts/build_exe.py first")
    target = DIST / f"{APP_NAME}-win64.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(payload.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(DIST).as_posix())
    return target


def build_sbom() -> Path:
    """CycloneDX 1.5 from the lockfile + the mt5 extra the portable build ships."""
    target = DIST / f"{APP_NAME}-win64.sbom.cdx.json"
    cmd = ["uv", "export", "--frozen", "--format", "cyclonedx1.5", "--extra", "mt5",
           "--output-file", str(target)]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit(f"uv export failed (exit {proc.returncode})")
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sbom-only", action="store_true")
    args = parser.parse_args()

    print(f"version {_project_version()}")
    if not args.sbom_only:
        zip_path = build_zip()
        print(f"zip:  {zip_path}  ({zip_path.stat().st_size} bytes, sha256 {sha256(zip_path)})")
    sbom_path = build_sbom()
    print(f"sbom: {sbom_path}  (sha256 {sha256(sbom_path)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
