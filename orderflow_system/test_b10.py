"""Wave B T12b — B10: configuration as portable artifacts (workspace + studies).

The routes are exercised directly (they are plain async functions); config writes are isolated to
a tmp path, so nothing here can touch a real installation's config file. The client side is pinned
by its landmarks: the Settings card, the export/import flow, and the refusal surface.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orderflow_system.desktop import api, config_store

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Config reads/writes land in tmp_path, never in a real installation."""
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return tmp_path


def test_the_artifact_kinds_and_their_blocks() -> None:
    cfg = config_store.default_config()
    art = api.artifact_build(cfg, "workspace")
    assert art["format"] == "ofap-config" and art["schema"] == 1 and art["kind"] == "workspace"
    assert set(art["blocks"]) == {"layouts", "workspaces", "ui"}
    assert art["app_version"] == cfg.get("version")
    assert set(api.artifact_build(cfg, "studies")["blocks"]) == {"studies", "expression", "atlas", "ofx"}
    assert api.artifact_build(cfg, "nope") is None


def test_refusals_each_say_why() -> None:
    bad = [
        ("not json at all", "not JSON"),
        ({"format": "something-else", "schema": 1, "kind": "workspace", "blocks": {"ui": {}}},
         "not an OFAP configuration artifact"),
        ({"format": "ofap-config", "schema": 99, "kind": "workspace", "blocks": {"ui": {}}}, "newer build"),
        ({"format": "ofap-config", "schema": "one", "kind": "workspace", "blocks": {"ui": {}}}, "no readable schema"),
        ({"format": "ofap-config", "schema": 1, "kind": "wat", "blocks": {"ui": {}}}, "unknown artifact kind"),
        ({"format": "ofap-config", "schema": 1, "kind": "workspace", "blocks": {"data": 1}}, "none of the blocks"),
        (41, "no artifact found"),
    ]
    for raw, needle in bad:
        artifact, why = api.artifact_validate(raw)
        assert artifact is None and needle in why, (raw, why)


def test_round_trip_through_the_real_routes(sandbox) -> None:
    # a baseline config on disk, then an artifact with a visibly different ui block
    config_store.save_config(config_store.default_config())
    cfg = config_store.load_config()
    cfg["ui"]["theme"] = "contrast"
    cfg["data_source"] = "both"
    art = api.artifact_build(cfg, "workspace")
    art["blocks"]["ui"]["contrast"] = "aggressive"

    # mutate the live config so the import's effect is visible
    live = config_store.load_config()
    live["ui"]["theme"] = "dark"
    live["ui"]["contrast"] = "calm"
    live["data_source"] = "mt5"
    config_store.save_config(live)
    before = config_store.load_config()

    res = asyncio.run(api.post_config_import({"artifact": json.dumps(art)}))
    assert res["ok"] and res["applied"] == ["layouts", "workspaces", "ui"]
    after = config_store.load_config()
    assert after["ui"]["theme"] == "contrast" and after["ui"]["contrast"] == "aggressive"
    assert after["data_source"] == before["data_source"], "blocks the artifact does not carry stay put"

    # and a corrupt import changes nothing
    res2 = asyncio.run(api.post_config_import({"artifact": "{not json"}))
    assert res2["ok"] is False and "not JSON" in res2["error"]
    assert config_store.load_config()["ui"]["theme"] == "contrast", "the refusal touched nothing"


def test_the_get_route_answers(sandbox) -> None:
    config_store.save_config(config_store.default_config())
    res = asyncio.run(api.get_config_artifact("studies"))
    assert res["ok"] and res["artifact"]["kind"] == "studies"
    res2 = asyncio.run(api.get_config_artifact("bogus"))
    assert res2["ok"] is False and "unknown artifact kind" in res2["error"]


def test_the_settings_card_and_wiring() -> None:
    html = _text("index.html")
    for marker in ('id="btnCfgExportWorkspace"', 'id="btnCfgExportStudies"', 'id="btnCfgImport"',
                   'id="cfgImportFile"', 'id="cfgArtifactResult"', "Configuration artifacts"):
        assert marker in html, marker
    js = _text("storage.js")
    for marker in ("function exportArtifact", "'/api/control/config/artifact?kind='",
                   "'/api/control/config/import'", "import refused:"):
        assert marker in js, marker
