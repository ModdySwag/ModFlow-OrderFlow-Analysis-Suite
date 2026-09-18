"""T6 — context-validity menus (A8) and per-view defaults (A15).

A8: the Keys menu disables rows whose own gate is false (`OFAPKEYS.canDispatch`) and shows the
binding’s own `why`; the paper ticket disables a panic button that has nothing to act on.
A15: remember / restore / factory-reset for the active view’s settings, with the path map mirrored
between the store and the menu (pinned equal) and a read-only defaults route.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orderflow_system.desktop import api, config_store

UI = Path(__file__).parent / "desktop" / "ui"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


# ── A8: the menus know their context ────────────────────────────────────

def test_the_keys_menu_consults_the_registry_gate():
    keys = _text(UI / "keys.js")
    assert "function canDispatch(id)" in keys and "canDispatch: canDispatch," in keys
    assert "why: String(spec.why || '')," in keys and "why: String(b.why || '')," in keys
    menu = _text(UI / "menubar.js")
    assert "OFAPKEYS.canDispatch(row.id)" in menu, "the Keys menu ignores the gate again"
    assert "row.why ||" in menu


def test_the_gated_bindings_carry_their_why():
    for name, needle in (("ofx-view.js", "'acts on the Engine panel'"),
                         ("heatmap-pro.js", "'acts on the Heatmap panel'"),
                         ("atlas.js", "'acts on the Replay panel'"),
                         ("paper.js", "'needs a running paper session")):
        assert needle in _text(UI / name), name + " lost its why text"
    assert "'box a region first'" in _text(UI / "heatmap-pro.js")


def test_the_paper_ticket_buttons_are_context_valid():
    paper = _text(UI / "paper.js")
    assert "bFlat.disabled = flat && !working;" in paper
    assert "bCancel.disabled = !working;" in paper
    assert "nothing to flatten" in paper and "no working orders to cancel" in paper


# ── A15: per-view defaults ─────────────────────────────────────────

def test_the_view_defaults_map_resolves_and_matches_the_menu():
    defaults = config_store.default_config()
    for view, paths in config_store.VIEW_DEFAULT_MAP.items():
        assert paths, view + " maps to nothing"
        for path in paths:
            node = defaults
            for part in path.split("."):
                assert isinstance(node, dict) and part in node, path + " does not resolve in the defaults"
                node = node[part]
    # the JS mirror must name the same views and the same paths
    menu = _text(UI / "menubar.js")
    import re
    block = re.search(r"const VIEW_DEFAULTS_MAP = \{(.*?)\};", menu, re.S)
    assert block, "the menu mirror is gone"
    js_view = re.findall(r"(\w+): \[([^\]]+)\]", block.group(1))
    assert {v: [p.strip().strip("'") for p in ps.split(",")] for v, ps in js_view} == \
        {v: list(ps) for v, ps in config_store.VIEW_DEFAULT_MAP.items()}


def test_view_defaults_survive_the_store_but_junk_does_not(store):
    assert store.default_config()["ui"]["view_defaults"] == {}
    clean = store.save_config({"ui": {"view_defaults": {
        "chart": {"ui.chart": {"range": 300}},
        "nope": {"ui.chart": {}},
        "tape": {"atlas.strange": {}},
        "heatmap": {"atlas.heatmap": "not-a-dict"},
    }}})
    assert clean["ui"]["view_defaults"] == {"chart": {"ui.chart": {"range": 300}}}


def test_the_defaults_route_answers_without_writing():
    res = asyncio.run(api.config_defaults())
    assert res["ok"] is True and res["config"]["ui"]["view_defaults"] == {}
    assert res["config"]["atlas"]["heatmap"]["bucket_ms"] == config_store.default_config()["atlas"]["heatmap"]["bucket_ms"]


def test_the_menu_ships_the_trio_and_retired_the_planned_row():
    menu = _text(UI / "menubar.js")
    for needle in ("Remember this view’s settings", "Restore the remembered settings",
                   "Reset this view to factory", "function viewDefaultsItems",
                   "VIEW_DEFAULTS_MAP[view]", "const view = (activeEl"):
        assert needle in menu, "the View menu lost: " + needle
    assert "planned('Reset all view settings'" not in menu, "the placeholder is back"


def test_the_timeframe_row_lands_on_the_chart_control():
    menu = _text(UI / "menubar.js")
    assert "planned('Timeframe / aggregation'" not in menu, "the dead TF stub is back"
    assert "openChartTimeframe" in menu and "getElementById('tfSelect')" in menu, \
        "the Data menu must take the user to the chart's timeframe control"


def test_the_index_platforms_explainer_lives_in_the_data_menu():
    menu = _text(UI / "menubar.js")
    assert "Index funds & indices — which platform?" in menu, "the explainer row is gone"
    assert "function explainerBlock" in menu and "explainerBlock()" in menu, "the block is gone"
    for needle in ("mbExplainAlpaca", "mbExplainPlatforms", "mbExplainInstruments", "mbExplainBack"):
        assert needle in menu, "the explainer lost a door: " + needle
    assert "showView(view)" in menu, "the explainer's doors must land on real panels"

