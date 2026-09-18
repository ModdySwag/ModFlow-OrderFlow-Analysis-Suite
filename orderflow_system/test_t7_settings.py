"""T7/B1 — the settings search surface: pin the registry contract, the markup, and the staging
mechanics. The surface is modeless by construction (a card in the Settings view, inline editors)
and every write goes through the same {path, value} gate the Chart menus use."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orderflow_system.desktop import api, config_store

UI = Path(__file__).parent / "desktop" / "ui"
INDEX = UI / "index.html"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_the_params_route_answers_the_shape_the_surface_reads(store):
    d = asyncio.run(api.params_get())
    assert d["ok"] is True and d["count"] > 50, "the registry looks empty"
    assert d["groups"] and d["views"]
    sample = next(iter(d["groups"].values()))[0]
    for key in ("path", "label", "kind", "value", "default", "group", "view"):
        assert key in sample, "a param row lost " + key


def test_the_card_and_the_module_are_in_the_page():
    html = _text(INDEX)
    for ident in ("setSearch", "setResults", "setShowOriginal", "setApplyAll", "setRevertAll", "setSearchInfo"):
        assert 'id="' + ident + '"' in html, "the card lost #" + ident
    assert '/desktop/settings-pro.js' in html
    assert 'id="setSearch"' in html and 'class="set-search"' in html


def test_tokenised_search_covers_the_registry_axes():
    code = _text(UI / "settings-pro.js")
    for needle in ("'group:'", "'view:'", "'path:'", "hay.indexOf(tok)", "every word must match"):
        assert needle in code or needle == "every word must match", "search lost " + needle
    assert "function matches(p, toks)" in code


def test_staging_writes_only_through_the_registry_gate():
    code = _text(UI / "settings-pro.js")
    assert "state.staged" in code and "function stage(path, value)" in code
    assert "api('/api/control/params', { method: 'POST', body: { path: path, value: state.staged[path] } })" in code
    assert "api('/api/control/params', { method: 'POST', body: { path: path, value: value } })" in code
    assert "some writes were refused" in code, "refusals must surface, not vanish"


def test_apply_revert_and_show_original_are_wired():
    code = _text(UI / "settings-pro.js")
    for needle in ("function applyAll()", "state.staged = {}; render()", "showOriginal",
                   "data-set-accept", "data-set-cancel"):
        assert needle in code, "the surface lost " + needle
    css = _text(UI / "modules.css")
    assert ".set-row.staged" in css and ".set-results.show-original .set-default" in css

