"""B2 — heat ramp controls: the shared dials module, the seven new display variables, and the
absolute-ceiling override on the depth map.

`ramp.js`'s own behaviour is pinned by `ramp.selftest.js` (node). What this file adds are the
CONTRACTS around it: the 'balanced' scheme must equal the shipped defaults (a values equality, not
a comment), every scheme dial must sit inside its registered bounds (the /params gate refuses the
rest), the config sanitiser must clamp junk back to the shipped look, and the depth map must honour
an absolute ceiling over the percentile one — the rest of the suite pins the percentile path.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from orderflow_system.desktop import config_store, param_registry

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"
RAMP = UI / "ramp.js"
INDEX = UI / "index.html"

B2_PATHS = (
    "ofx.heat_contrast", "ofx.heat_floor", "ofx.heat_floor_pct",
    "atlas.heatmap.upper_cutoff_abs", "atlas.heatmap.contrast",
    "atlas.heatmap.floor", "atlas.heatmap.floor_pct",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("node") or "node"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def _schemes_from_js() -> list:
    code = _text(RAMP)
    found = re.findall(
        r'\{ id: "([a-z]+)", label: "([^"]+)", ceiling_pct: ([\d.]+), floor: ([\d.]+), '
        r'floor_pct: ([\d.]+), contrast: ([\d.]+),', code)
    assert len(found) == 4, "the scheme catalogue changed shape: " + repr(found)
    return [{"id": i, "label": lab, "ceiling_pct": float(c), "floor": float(f),
             "floor_pct": float(fp), "contrast": float(ct)} for i, lab, c, f, fp, ct in found]


def test_the_seven_variables_are_registered_with_bounds():
    for path in B2_PATHS:
        p = param_registry.BY_PATH.get(path)
        assert p is not None, "missing from the registry: " + path
        assert p.kind == "number", path + " must be a number"
        assert p.minimum is not None and p.maximum is not None and p.minimum < p.maximum, path
        assert p.meaning and p.label and p.group and p.view, "no presentation for " + path


def test_the_scheme_dials_sit_inside_the_registered_bounds():
    bounds = {
        "ceiling_pct": param_registry.BY_PATH["atlas.heatmap.upper_cutoff_pct"],
        "floor": param_registry.BY_PATH["atlas.heatmap.floor"],
        "floor_pct": param_registry.BY_PATH["atlas.heatmap.floor_pct"],
        "contrast": param_registry.BY_PATH["atlas.heatmap.contrast"],
    }
    for scheme in _schemes_from_js():
        for dial, param in bounds.items():
            assert param.minimum <= scheme[dial] <= param.maximum, (
                scheme["id"] + " proposes " + dial + "=" + str(scheme[dial])
                + " outside [" + str(param.minimum) + ", " + str(param.maximum) + "]")


def test_balanced_equals_the_shipped_defaults():
    cfg = config_store.default_config()
    ofx, hm = cfg["ofx"], cfg["atlas"]["heatmap"]
    balanced = [s for s in _schemes_from_js() if s["id"] == "balanced"][0]
    assert balanced["ceiling_pct"] == hm["upper_cutoff_pct"]
    assert balanced["floor"] == ofx["heat_floor"] == hm["floor"]
    assert balanced["floor_pct"] == ofx["heat_floor_pct"] == hm["floor_pct"]
    assert balanced["contrast"] == ofx["heat_contrast"] == hm["contrast"]


def test_defaults_ship_the_old_look_and_the_sanitiser_clamps():
    cfg = config_store.default_config()
    ofx, hm = cfg["ofx"], cfg["atlas"]["heatmap"]
    assert (ofx["heat_contrast"], ofx["heat_floor"], ofx["heat_floor_pct"]) == (1.0, 0.0, 0.0)
    assert (hm["contrast"], hm["floor"], hm["floor_pct"], hm["upper_cutoff_abs"]) == (1.0, 0.0, 0.0, 0.0)

    cfg["ofx"]["heat_contrast"] = 99
    cfg["ofx"]["heat_floor"] = -5
    cfg["ofx"]["heat_floor_pct"] = 500
    cfg["atlas"]["heatmap"]["contrast"] = "junk"
    cfg["atlas"]["heatmap"]["floor"] = -1
    cfg["atlas"]["heatmap"]["floor_pct"] = 80
    cfg["atlas"]["heatmap"]["upper_cutoff_abs"] = -3
    out = config_store._sanitise(cfg)
    o, h = out["ofx"], out["atlas"]["heatmap"]
    assert o["heat_contrast"] == 2.5 and o["heat_floor"] == 0.0 and o["heat_floor_pct"] == 50.0
    assert h["contrast"] == 1.0 and h["floor"] == 0.0 and h["floor_pct"] == 50.0
    assert h["upper_cutoff_abs"] == 0.0


def test_the_absolute_ceiling_overrides_the_percentile_one():
    from orderflow_system.atlas.depthmap import DepthHeatmap
    from orderflow_system.data.models import OrderbookLevel, OrderbookSnapshot

    def book(ts_ms: int, levels_bid):
        bids = [OrderbookLevel(price=p, quantity=q) for p, q in levels_bid]
        asks = [OrderbookLevel(price=p + 50.0, quantity=q) for p, q in levels_bid]
        return OrderbookSnapshot(timestamp_ms=ts_ms, bids=bids, asks=asks)

    # A realistic epoch: the map's bucketing misreads epoch-0 stamps (a falsy-zero), so house
    # tests carry a real base the way the sibling cutoff test does.
    T0 = 1_724_000_000_000
    hm = DepthHeatmap("T", tick_size=1.0, bucket_ms=1000, wall_quantile=0.9, upper_cutoff_pct=5.0)
    for i in range(20):
        hm.on_orderbook(book(T0 + 1000 * i, [(100.0, 1.0 + i)]))
    # The snapshot cache key carries the cutoff options (its own comment: flipping the cutoff
    # must take effect immediately), so a same-shape poll already sees each change.
    pct_scale = hm.snapshot(columns=30, max_rows=40)["scale_max"]
    assert 0 < pct_scale < 20.0              # the outlier is ignored on the percentile path

    hm.upper_cutoff_abs = 12.0
    assert hm.snapshot(columns=30, max_rows=40)["scale_max"] == 12.0

    hm.upper_cutoff_abs = 0.0
    assert hm.snapshot(columns=30, max_rows=40)["scale_max"] == pct_scale


def test_the_module_parses_and_its_selftest_passes():
    check = _node("--check", str(RAMP))
    assert check.returncode == 0, check.stderr
    run = _node(str(UI / "ramp.selftest.js"))
    assert run.returncode == 0, (run.stdout or "") + (run.stderr or "")
    assert "0 failed" in run.stdout, run.stdout


def test_the_controls_are_in_the_page_and_ramp_js_loads_before_atlas():
    html = _text(INDEX)
    for cid in ("ofxHeatScheme", "ofxHeatContrast", "ofxHeatFloor", "ofxHeatGlobal",
                "hmHeatScheme", "hmHeatContrast", "hmHeatFloor", "hmHeatGlobal"):
        assert 'id="' + cid + '"' in html, "control missing from index.html: " + cid
    assert '/desktop/ramp.js' in html, "ramp.js is not loaded"
    assert html.index('/desktop/ramp.js') < html.index('/desktop/atlas.js'), (
        "ramp.js must be parsed before atlas.js (the painter reads OFAPRAMP)")
    for sel in ("ofxHeatScheme", "hmHeatScheme"):
        block = re.search(r'id="' + sel + r'"[\s\S]*?</select>', html)
        assert block, sel + " has no options block"
        ids = re.findall(r'<option value="([a-z]+)"', block.group(0))
        assert ids == ["balanced", "walls", "detail", "quiet", "custom"], (sel, ids)


def test_the_audit_knows_the_module():
    audit = (PKG.parent / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"ramp.js"' in audit, "ramp.js missing from audit_ui_refs JS_FILES"
