"""Bar/candle expression modes and accessible palettes (P1-8).

`desktop/ui/expression.js` decides how a bar is expressed and with which colours; the engine view
(`ofx.js`) and the chart view (`ui.js`) only execute that decision, and both quote its sentence, so a
picture and its legend cannot disagree. Pinned here:

* the module and its selftest exist, parse, and the selftest is green — including the MEASURED
  palette claims (each colour-blind pair's separation under all three dichromacies, the shipped pair
  as the control that collapses, and the legibility of every colour on the stage);
* one list per catalogue: the JS modes/palettes/ramps and `config_store`'s clamp tuples are equal,
  and the three controls in `index.html` offer exactly them (a ramp the engine knows and the control
  does not was §41's defect 1 — a feature nobody could reach);
* the depth ramps are monotone in luminance, measured at 21 samples — the property that lets a
  magnitude be read by a reader who has no colour vision;
* the engine's own default chrome and the catalogue's `default` mode agree, and both surfaces read
  the catalogue rather than re-deriving a colour;
* the store clamps junk and accepts legal values, and the route the UI calls is discoverable by the
  audit that checks every other module.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
MODULE = UI / "expression.js"
SELFTEST = UI / "expression.selftest.js"
ENGINE = UI / "ofx.js"
VIEW = UI / "ofx-view.js"
CHART = UI / "ui.js"
HTML = UI / "index.html"
AUDIT = ROOT / "scripts" / "audit_ui_refs.py"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


@pytest.fixture(scope="module")
def source() -> str:
    return MODULE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html() -> str:
    return HTML.read_text(encoding="utf-8", errors="replace")


def _run(script: str) -> str:
    out = subprocess.run([_node(), "-e", script], capture_output=True, text=True, cwd=str(UI))
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


# ── files, syntax, the module's own gate ──────────────────────────────────────────────────────

def test_files_exist():
    assert MODULE.is_file(), "desktop/ui/expression.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/expression.selftest.js is missing"


@pytest.mark.parametrize("path", [MODULE, SELFTEST, ENGINE, VIEW, CHART])
def test_parses_as_javascript(path):
    out = subprocess.run([_node(), "--check", str(path)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_its_selftest_passes_with_the_measured_claims():
    out = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    match = re.search(r"expression selftest: (\d+) ok, 0 failed", out.stdout)
    assert match, out.stdout
    assert int(match.group(1)) >= 40, f"the selftest shrank to {match.group(1)} checks"


def test_it_stays_pure(source):
    """A module the selftest boots with a stub window has to keep the browser out of it."""
    assert "document." not in source, "no DOM in the decision"
    assert "fetch(" not in source and "OFAPBUS" not in source, "the decision does not need the wire"
    assert "localStorage" not in source and "sessionStorage" not in source, "the config is the record"
    assert "setInterval" not in source and "setTimeout" not in source, "no timers in a pure module"


def test_it_is_registered_with_the_audit():
    audit = AUDIT.read_text(encoding="utf-8")
    assert '"expression.js"' in audit, "register it in JS_FILES — the audit cross-checks api() calls and ids"


def test_it_loads_before_the_engine_that_reads_it(html):
    assert "/desktop/expression.js" in html
    assert html.index("/desktop/expression.js") < html.index("/desktop/ofx.js"), \
        "ofx.js resolves the catalogue at paint time — the script tag must come first"


# ── one list per catalogue, held equal by this test ───────────────────────────────────────────

def test_the_mode_and_palette_catalogues_agree_everywhere():
    js = json.loads(_run(
        "const E=require('./expression.js');"
        "console.log(JSON.stringify({modes:E.MODE_KEYS,palettes:E.PALETTE_KEYS}));"
    ))
    assert js["modes"] == list(config_store.EXPRESSION_MODES), js["modes"]
    assert js["palettes"] == list(config_store.EXPRESSION_PALETTES), js["palettes"]


def test_the_ramp_catalogue_agrees_everywhere():
    js = json.loads(_run("console.log(JSON.stringify(require('./ofx.js').RAMPS));"))
    assert js == list(config_store.RAMP_KEYS), js


def test_the_engine_view_control_offers_exactly_those_lists(html):
    block = re.search(r'<select id="ofxMode".*?</select>', html, re.S)
    assert block, "the engine view has no bar-mode control"
    values = re.findall(r'<option value="([^"]+)"', block.group(0))
    assert values == list(config_store.EXPRESSION_MODES), values

    pal = re.search(r'<select id="ofxPalette".*?</select>', html, re.S)
    assert pal, "the engine view has no palette control"
    assert re.findall(r'<option value="([^"]+)"', pal.group(0)) == list(config_store.EXPRESSION_PALETTES)

    ramp = re.search(r'<select id="ofxRamp".*?</select>', html, re.S)
    assert ramp, "the engine view has no ramp control"
    assert re.findall(r'<option value="([^"]+)"', ramp.group(0)) == list(config_store.RAMP_KEYS)


def test_the_chart_view_control_offers_its_own_support(html):
    block = re.search(r'<select id="chartMode".*?</select>', html, re.S)
    assert block, "the chart view has no bar-mode control"
    values = re.findall(r'<option value="([^"]+)"', block.group(0))
    assert values == list(config_store.EXPRESSION_MODES), values
    pal = re.search(r'<select id="chartPalette".*?</select>', html, re.S)
    assert pal and re.findall(r'<option value="([^"]+)"', pal.group(0)) == list(config_store.EXPRESSION_PALETTES)


def test_the_chart_view_declares_the_mode_it_cannot_draw():
    """Split candles need pixels inside the range; the chart view says so instead of drawing
    something else with the same name. The control offers the mode so the reason can be read."""
    supported = json.loads(_run("console.log(JSON.stringify(require('./expression.js').CHART_SUPPORT));"))
    assert supported["split"] is False
    assert [k for k in config_store.EXPRESSION_MODES if not supported.get(k)] == ["split"]
    chart = CHART.read_text(encoding="utf-8")
    assert "chartGap" in chart, "the chart view must hand the gap to the legend"


# ── the measured properties, re-measured here ─────────────────────────────────────────────────

def test_every_ramp_is_monotone_in_luminance():
    """Magnitude must survive a reader who cannot use hue: measured, not asserted."""
    script = (
        "const O=require('./ofx.js');"
        "const lum=(c)=>{const t=Array.isArray(c)?c:String(c).replace(/^rgb\\(|\\)$/g,'').split(',').map(Number);"
        "const l=(v)=>{const s=v/255;return s<=0.04045?s/12.92:Math.pow((s+0.055)/1.055,2.4)};"
        "return 0.2126*l(t[0])+0.7152*l(t[1])+0.0722*l(t[2])};"
        "const out={};for(const r of O.RAMPS){const ys=[];for(let i=0;i<=20;i++)ys.push(lum(O.math.heatColor01(i/20,r)));"
        "let dips=0;for(let i=1;i<ys.length;i++)if(ys[i]<ys[i-1]-1e-9)dips++;out[r]={dips,lo:ys[0],hi:ys[ys.length-1]};}"
        "console.log(JSON.stringify(out));"
    )
    measured = json.loads(_run(script))
    for ramp, m in measured.items():
        assert m["dips"] == 0, f"{ramp} dips {m['dips']} times — its magnitude would ride on hue"
        assert m["hi"] - m["lo"] > 0.3, f"{ramp} barely changes luminance ({m})"


def test_the_shipped_pair_is_the_measured_control(source):
    """The palettes exist because of one measurement; if it ever stops holding, the docs are wrong."""
    script = (
        "const E=require('./expression.js');"
        "console.log(JSON.stringify({deut:E.separation('53,208,127','255,93,108','deuteranopia'),"
        "floor:E.MIN_PAIR_DE}));"
    )
    m = json.loads(_run(script))
    assert m["deut"]["ok"] is False, f"the shipped pair no longer collapses (measured {m['deut']})"
    assert m["floor"] == 40, m["floor"]
    assert "collapse" in source


# ── the engine executes the catalogue instead of re-deriving it ───────────────────────────────

def test_the_engine_applies_the_palette_to_the_one_colour_table():
    src = ENGINE.read_text(encoding="utf-8")
    assert "themeOverrides" in src, "the palette must be applied from the catalogue"
    assert "BASE_THEME" in src and "Object.assign(math.theme" in src, \
        "the palette is written INTO math.theme (the table the renderers and the legend share)"
    probe = _run(
        "const O=require('./ofx.js');globalThis.OFAPEXPR=require('./expression.js');"
        "const before=Object.assign({},O.math.theme);"
        "O.setExpression({mode:'delta',palette:'deutan'});const mid=O.math.theme.bid;"
        "O.setExpression({mode:'default',palette:'theme'});"
        "const same=Object.keys(before).every((k)=>before[k]===O.math.theme[k]);"
        "console.log(JSON.stringify({mid,same,keys:Object.keys(before).length}));"
    )
    m = json.loads(probe)
    assert m["mid"] != "53,208,127", "the deutan palette did not move the bid colour"
    assert m["same"] and m["keys"] >= 15, f"switching back was not lossless: {m}"


def test_the_engines_default_chrome_is_the_catalogues_default_mode():
    """'Default changes nothing' is checked against the engine's own pre-P1-8 chrome."""
    src = ENGINE.read_text(encoding="utf-8")
    anchor = re.search(r"CHROME_DEFAULT = Object\.freeze\(\{([^}]*)\}\)", src)
    assert anchor, "the engine no longer declares its default chrome in one place"
    engine_chrome = {k.strip(): v.strip() == "true"
                     for k, v in (part.split(":") for part in anchor.group(1).split(","))}
    js = json.loads(_run("console.log(JSON.stringify(require('./expression.js').MODES.default.chrome));"))
    assert engine_chrome == js, f"engine {engine_chrome} vs catalogue {js}"


def test_both_surfaces_read_the_catalogue():
    engine = ENGINE.read_text(encoding="utf-8")
    assert "expresson" not in engine  # typo guard
    assert "barPaintFor" in engine and "root.OFAPEXPR" in engine, "the engine must ask the catalogue"
    chart = CHART.read_text(encoding="utf-8")
    assert "chartBars(" in chart and "OFAPEXPR" in chart, "the chart view must project through the catalogue"


def test_the_studies_pass_cannot_strip_a_colour_blind_palette_back_to_the_theme():
    """`studiesApply()` repaints the candle series from the raw bars (it runs with zero studies too),
    so the chart view re-asserts the expression afterwards. That re-assert read only the MODE, and
    `default` was exempt — so `default` + a colour-blind palette settled on the theme's green/red
    candles under a legend claiming sky blue / orange (measured live). The condition must read the
    palette as well; the theme pair is the one case where the studies pass changes no pixel."""
    chart = CHART.read_text(encoding="utf-8")
    line = [l for l in chart.splitlines() if "repaintChart()" in l and "S.expr" in l]
    assert line, "the chart view must re-assert the expression after the studies pass"
    assert any("palette !== 'theme'" in l for l in line), \
        "the re-assert must fire for a colour-blind palette even in `default` mode"


def test_the_ramp_is_no_longer_a_browser_storage_preference():
    view = VIEW.read_text(encoding="utf-8")
    assert "ofx.ramp" not in view, "the ramp is a config value now; browser storage is not the record"
    assert "/api/control/expression" in view, "the engine view reads and writes the expression block"


# ── the route, through the audit's own machinery ──────────────────────────────────────────────

def _audit_module():
    spec = importlib.util.spec_from_file_location("audit_ui_refs_for_expression", AUDIT)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    return audit


def test_the_route_the_ui_calls_exists_and_is_discoverable():
    audit = _audit_module()
    routes = audit.routes_from(ROOT / "orderflow_system" / "desktop" / "api.py", "/api/control")
    assert "/api/control/expression" in routes, "the desktop router must declare the pair"
    for module_name in ("ofx-view.js", "ui.js"):
        text = (UI / module_name).read_text(encoding="utf-8", errors="replace")
        assert "api('/api/control/expression'" in text or "apiGet('/api/control/expression'" in text, module_name


def test_both_verbs_are_declared():
    src = (ROOT / "orderflow_system" / "desktop" / "api.py").read_text(encoding="utf-8")
    assert '@router.get("/expression")' in src and '@router.post("/expression")' in src


# ── the store ────────────────────────────────────────────────────────────────────────────────

def test_the_defaults_carry_the_block():
    cfg = config_store.default_config()
    assert cfg["expression"]["engine"] == {"mode": "default", "palette": "theme"}
    assert cfg["expression"]["chart"] == {"mode": "default", "palette": "theme"}
    assert cfg["ofx"]["ramp"] == "classic"


def test_junk_is_clamped_and_legal_values_survive():
    junk = {"expression": {"engine": {"mode": "nope", "palette": 7}, "chart": "garbage"},
            "ofx": {"ramp": "rainbow"}}
    clean = config_store._sanitise(config_store._deep_merge(config_store.default_config(), junk))
    assert clean["expression"]["engine"] == {"mode": "default", "palette": "theme"}
    assert clean["expression"]["chart"] == {"mode": "default", "palette": "theme"}
    assert clean["ofx"]["ramp"] == "classic"

    ok = {"expression": {"chart": {"mode": "split", "palette": "tritan"}}, "ofx": {"ramp": "thermal"}}
    kept = config_store._sanitise(config_store._deep_merge(config_store.default_config(), ok))
    assert kept["expression"]["chart"] == {"mode": "split", "palette": "tritan"}
    assert kept["expression"]["engine"] == {"mode": "default", "palette": "theme"}, \
        "one surface's write must not blank the other's"
    assert kept["ofx"]["ramp"] == "thermal"


def test_the_ramp_travels_with_the_other_engine_parameters():
    src = (ROOT / "orderflow_system" / "desktop" / "api.py").read_text(encoding="utf-8")
    save = re.search(r"for key in \(([^)]*)\):", src)
    assert save and '"ramp"' in save.group(1), "POST /api/control/ofx must accept the ramp"
