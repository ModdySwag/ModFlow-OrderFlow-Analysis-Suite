"""Gate for `desktop/param_registry.py` — the table every settings dialog, menu and palette reads.

The valuable assertion here is coverage: every display-relevant leaf in `default_config()` must be
registered, so a variable added to the config store cannot stay invisible to the UI (that is how the
app ended up with ~80 knobs and a handful of controls).
"""

from __future__ import annotations

import json

import pytest

from orderflow_system.desktop import param_registry as reg
from orderflow_system.desktop.config_store import default_config

CONFIG = default_config()


def _leaves(node, prefix=""):
    """Every leaf under a config node, as (dotted path, value, kind) with lists as one leaf."""
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            yield from _leaves(value, path)
    elif isinstance(node, list):
        yield prefix, node, "list"
    else:
        kind = "bool" if isinstance(node, bool) else ("number" if isinstance(node, (int, float)) else "text")
        yield prefix, node, kind


def display_leaves():
    """Display-relevant leaves: under a display root, numeric or boolean, not on the exclusion list."""
    for root in reg.DISPLAY_ROOTS:
        node = CONFIG
        ok = True
        for part in root.split("."):
            if not isinstance(node, dict) or part not in node:
                ok = False
                break
            node = node[part]
        if not ok:
            continue
        for path, _value, kind in _leaves(node, root):
            if kind in ("number", "bool") and path not in reg.NOT_DISPLAY:
                yield path, kind


def test_paths_are_unique():
    paths = [p.path for p in reg.PARAMS]
    assert len(paths) == len(set(paths)), "duplicate path in the registry"


def test_every_path_resolves():
    missing = [p.path for p in reg.PARAMS if reg.current(CONFIG, p) is None]
    assert missing == [], f"registry points at config paths that do not exist: {missing}"


def test_kinds_match_the_config():
    wrong = []
    for param in reg.PARAMS:
        value = reg.current(CONFIG, param)
        if param.kind == "bool" and not isinstance(value, bool):
            wrong.append((param.path, param.kind, type(value).__name__))
        if param.kind == "number" and not isinstance(value, (int, float)):
            wrong.append((param.path, param.kind, type(value).__name__))
        if param.kind == "enum" and not param.choices:
            wrong.append((param.path, "enum without choices", ""))
        if param.kind == "enum" and isinstance(value, str) and value not in param.choices:
            wrong.append((param.path, "enum value outside its choices", value))
    assert wrong == [], f"registry/config kind mismatches: {wrong}"


def test_numbers_carry_bounds():
    unbounded = [p.path for p in reg.PARAMS if p.kind == "number" and (p.minimum is None or p.maximum is None)]
    assert unbounded == [], f"numeric variables without bounds cannot be rendered as controls: {unbounded}"
    inverted = [p.path for p in reg.PARAMS if p.kind == "number" and p.minimum >= p.maximum]
    assert inverted == [], f"inverted bounds: {inverted}"


def test_display_coverage():
    """Nothing display-relevant may be missing from the registry."""
    registered = {p.path for p in reg.PARAMS}
    unregistered = [(path, kind) for path, kind in display_leaves() if path not in registered]
    assert unregistered == [], (
        "config variables missing from the registry — add them to PARAMS (or to NOT_DISPLAY with a "
        f"reason): {unregistered}")


def test_descriptions_are_present():
    bare = [p.path for p in reg.PARAMS if len(p.meaning) < 20 or not p.label or not p.group or not p.view]
    assert bare == [], f"every entry needs a label, group, view and a real meaning: {bare}"


def test_groups_and_views_helpers():
    grouped = reg.groups()
    assert sum(len(v) for v in grouped.values()) == len(reg.PARAMS)
    assert "ofx" in {p.view for p in reg.PARAMS}
    assert reg.for_view("ofx"), "the Engine view owns variables"
    assert reg.for_view("no-such-view") == []


def test_dump_shape_and_live_values():
    out = reg.dump(CONFIG)
    assert out["ok"] is True and out["count"] == len(reg.PARAMS)
    assert "Footprint" in out["groups"]
    engine_r = next(p for p in out["groups"]["Footprint"] if p["path"] == "ofx.R")
    assert engine_r["value"] == CONFIG["ofx"]["R"] and engine_r["min"] == 1.5 and engine_r["max"] == 20.0
    assert json.loads(json.dumps(out))["count"] == out["count"]        # JSON-safe for the API


def test_applies_flags_are_known():
    bad = [p.path for p in reg.PARAMS if p.applies not in ("live", "restart")]
    assert bad == [], f"unknown applies flag: {bad}"
    restart = [p.path for p in reg.PARAMS if p.applies == "restart"]
    assert "atlas.extras_enabled" in restart, "the streams switch needs an engine restart"


# ── the control-surface pass (2026-09-19): the markup, the registry and the store agree ─────────
# The audit found the same bound hand-written in up to three places, disagreeing; the registry is
# the display authority, so the markup is pinned to it (and the store was aligned in the same pass).
# A choice the registry offers must also be a choice the store keeps — the `imbalance_mode: "both"`
# lie is what these two tests exist to keep closed.

import re as _re
from pathlib import Path as _Path

_UI_HTML = _Path(__file__).resolve().parent / "desktop" / "ui" / "index.html"

MARKUP_BOUNDS = {
    "ofx.lambda_ms": "ofxLambda",
    "ofx.min_block": "ofxMinBlock",
    "atlas.footprint.imbalance_threshold": "ofImbThresh",
}


def test_markup_bounds_match_the_registry():
    html = _UI_HTML.read_text(encoding="utf-8")
    for path, input_id in MARKUP_BOUNDS.items():
        param = reg.BY_PATH[path]
        tag = _re.search(r'<input[^>]*id="%s"[^>]*>' % _re.escape(input_id), html)
        assert tag, f"no input #{input_id} in index.html"
        attrs = dict(_re.findall(r'(\w+)="([^"]*)"', tag.group(0)))
        assert float(attrs["min"]) == float(param.minimum), f"{path}: min {attrs.get('min')} vs {param.minimum}"
        assert float(attrs["max"]) == float(param.maximum), f"{path}: max {attrs.get('max')} vs {param.maximum}"
        assert float(attrs["step"]) == float(param.step), f"{path}: step {attrs.get('step')} vs {param.step}"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A store whose config directory is a temp dir (never the user's real one)."""
    from orderflow_system.desktop import config_store

    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


def test_every_registry_enum_choice_survives_the_store(store):
    """Every choice an enum control offers must be what the store keeps after a round-trip."""
    for param in reg.PARAMS:
        if param.kind != "enum" or not param.choices:
            continue
        for choice in param.choices:
            parts = param.path.split(".")
            body: dict = {}
            node = body
            for part in parts[:-1]:
                node[part] = {}
                node = node[part]
            node[parts[-1]] = choice
            saved = store.save_config(body)
            node = saved
            for part in parts:
                assert isinstance(node, dict) and part in node, f"{param.path} vanished in the store"
                node = node[part]
            assert node == choice, f"{param.path}: choice {choice!r} came back as {node!r}"


def test_every_registry_bound_survives_the_store(store):
    """A bound a Chart menu prints must be a bound the store keeps — numbers as well as choices.

    Seven variables disagreed when this was written (R 1.0/1.5, stack 12/8, text px 8/20, sweep 5/4,
    lambda ms 50/100, imbalance threshold 0/1, equal tolerance 10/1): the menu offered a value the
    store silently rewrote. The registry states the store's bounds now, and this keeps them equal.
    """
    for param in reg.PARAMS:
        if param.kind != "number" or param.minimum is None or param.maximum is None:
            continue
        for bound in (param.minimum, param.maximum):
            parts = param.path.split(".")
            body: dict = {}
            node = body
            for part in parts[:-1]:
                node[part] = {}
                node = node[part]
            node[parts[-1]] = bound
            saved = store.save_config(body)
            node = saved
            for part in parts:
                assert isinstance(node, dict) and part in node, f"{param.path} vanished in the store"
                node = node[part]
            assert node == bound, f"{param.path}: bound {bound!r} came back as {node!r}"


if __name__ == "__main__":       # pragma: no cover - convenience only
    raise SystemExit(pytest.main([__file__, "-q"]))
