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
    assert engine_r["value"] == CONFIG["ofx"]["R"] and engine_r["min"] == 1.0 and engine_r["max"] == 20.0
    assert json.loads(json.dumps(out))["count"] == out["count"]        # JSON-safe for the API


def test_applies_flags_are_known():
    bad = [p.path for p in reg.PARAMS if p.applies not in ("live", "restart")]
    assert bad == [], f"unknown applies flag: {bad}"
    restart = [p.path for p in reg.PARAMS if p.applies == "restart"]
    assert "atlas.extras_enabled" in restart, "the streams switch needs an engine restart"


if __name__ == "__main__":       # pragma: no cover - convenience only
    raise SystemExit(pytest.main([__file__, "-q"]))
