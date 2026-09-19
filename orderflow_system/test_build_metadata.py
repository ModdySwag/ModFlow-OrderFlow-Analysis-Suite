"""Release-metadata guards (audit F-01 / F-02 / F-04).

F-02: the shipped exe had no Windows version metadata while the installer said 0.1.0 — the build
script now generates the resource from pyproject, so the two cannot drift.
F-01: the artifact gets a BUILD_INFO.json (commit, worktree state, exe hash) so a published
binary is traceable to the tree it came from.
F-04: a corrupt config.json is moved aside and reported, never silently replaced by defaults.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from orderflow_system.desktop import config_store

ROOT = Path(__file__).resolve().parents[1]


def _build_module():
    spec = importlib.util.spec_from_file_location("ofap_build_exe", ROOT / "scripts" / "build_exe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_build_script_generates_the_exe_version_resource():
    mod = _build_module()

    version_file = mod.write_version_file()
    text = version_file.read_text(encoding="utf-8")

    assert "VSVersionInfo" in text
    assert mod._project_version() in text, "the exe's version comes from pyproject.toml"
    assert "ModFlow OrderFlow Analysis Suite" in text


def test_the_build_script_stamps_provenance_next_to_the_artifact(tmp_path):
    mod = _build_module()
    target = tmp_path / "ModFlowOrderFlowAnalysisSuite.exe"
    target.write_bytes(b"stub-binary")

    stamp_path = mod.write_build_stamp(target)
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))

    assert stamp["version"] == mod._project_version()
    assert stamp["worktree_state"] in ("clean", "dirty")
    assert len(stamp["exe_sha256"]) == 64
    assert stamp_path.parent == tmp_path, "the stamp rides with the artifact it describes"


def test_a_corrupt_config_is_moved_aside_and_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    path = tmp_path / "config.json"
    path.write_text("{not json at all", encoding="utf-8")
    config_store._config_error.clear()

    cfg = config_store.load_config()

    assert isinstance(cfg, dict) and cfg, "defaults must come back so the app can start"
    assert not path.exists(), "the unreadable file must stop being 'the config'"
    backups = list(tmp_path.glob("config.json.corrupt-*"))
    assert len(backups) == 1, "the corrupt bytes are kept, not discarded"
    error = config_store.config_error()
    assert error["reason"] and error["backup"].endswith(backups[0].name)
    config_store._config_error.clear()

def test_the_packaged_app_serves_no_openapi_endpoints(monkeypatch):
    """F-11: a packaged build must not publish /docs, /redoc or /openapi.json (they describe the
    whole control surface). A source checkout keeps them; OFAP_OPENAPI=1 re-enables them."""
    from orderflow_system.dashboard import app as dash

    monkeypatch.delenv("OFAP_OPENAPI", raising=False)
    monkeypatch.setenv("OFAP_FORCE_FROZEN", "1")
    assert dash.endpoint_policy() == (None, None, None)

    monkeypatch.setenv("OFAP_OPENAPI", "1")
    assert dash.endpoint_policy() == ("/docs", "/redoc", "/openapi.json")

    monkeypatch.delenv("OFAP_FORCE_FROZEN")
    monkeypatch.delenv("OFAP_OPENAPI")
    assert dash.endpoint_policy() == ("/docs", "/redoc", "/openapi.json")
