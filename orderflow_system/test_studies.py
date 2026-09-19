"""Studies: config contract, library endpoint, and the runtime's own self-test.

The indicator runtime is JavaScript, so the parts worth pinning from Python are the ones
Python owns — the config contract and the module listing — plus a hard check that the
runtime's Node self-test passes and that a module written against the documented
contract (predef/meta/require('./tools/…')) loads and runs through the shim.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
sys.path.insert(0, str(ROOT))

from orderflow_system.desktop import api as control_api          # noqa: E402
from orderflow_system.desktop import config_store                # noqa: E402


# ── the config contract ────────────────────────────────────────────────────────────
def test_defaults_ship_an_empty_but_shaped_studies_block():
    studies = config_store.default_config()["studies"]
    assert studies == {"active": [], "custom": [], "data_box": True, "collections": {}}


def test_active_studies_are_validated(monkeypatch, tmp_path):
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    cfg = config_store.default_config()
    cfg["studies"]["active"] = [
        {"name": "deltaFlow", "params": {"window": "20", "sigma": 2.5, "signal": True}, "visible": True},
        {"name": "2 bad name", "params": {}},                     # dropped: not an identifier
        "not-a-dict",                                             # dropped
        {"name": "ema", "params": {"period": 21, "junk": {"nested": 1}}, "visible": False},
    ]
    saved = config_store.save_config(cfg)["studies"]
    names = [entry["name"] for entry in saved["active"]]
    assert names == ["deltaFlow", "ema"]
    assert saved["active"][0]["params"]["window"] == "20"          # scalars survive as typed
    assert saved["active"][0]["params"]["signal"] is True
    assert "junk" not in saved["active"][1]["params"]              # nested objects are not stored
    assert saved["active"][1]["visible"] is False


def test_active_list_is_capped():
    cfg = config_store.default_config()
    cfg["studies"]["active"] = [{"name": f"study{i}", "params": {}} for i in range(80)]
    assert len(config_store._sanitise(cfg)["studies"]["active"]) == 40


def test_custom_modules_need_a_name_and_have_a_source_cap():
    cfg = config_store.default_config()
    cfg["studies"]["custom"] = [
        {"name": "", "source": "module.exports = {};"},                     # no name
        {"name": "noSource", "source": ""},                                 # no source
        {"name": "big", "source": "x" * 30_000, "enabled": True},           # capped
        {"name": "ok", "source": "module.exports = {name:'ok'};", "enabled": False},
    ]
    saved = config_store._sanitise(cfg)["studies"]
    assert [c["name"] for c in saved["custom"]] == ["big", "ok"]
    assert len(saved["custom"][0]["source"]) == 20_000
    assert saved["custom"][1]["enabled"] is False


# ── the library listing ────────────────────────────────────────────────────────────
def test_library_lists_only_indicator_modules(monkeypatch, tmp_path):
    (tmp_path / "indicators").mkdir()
    (tmp_path / "indicators" / "mine.js").write_text("/* module */", encoding="utf-8")
    (tmp_path / "indicators" / "notes.txt").write_text("ignore me", encoding="utf-8")
    (tmp_path / "other.js").write_text("/* not a module */", encoding="utf-8")
    monkeypatch.setattr(control_api, "STUDY_MODULE_DIR", tmp_path / "indicators")
    payload = json.loads(json.dumps(_run(control_api.studies_library())))
    assert payload["modules"] == ["/desktop/indicators/mine.js"]
    assert payload["ok"] is True and payload["custom"] == []


def test_library_includes_enabled_custom_modules(monkeypatch, tmp_path):
    monkeypatch.setattr(control_api, "STUDY_MODULE_DIR", tmp_path / "missing")
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    cfg = config_store.default_config()
    cfg["studies"]["custom"] = [{"name": "pasted", "source": "module.exports={name:'pasted'};", "enabled": True},
                                {"name": "off", "source": "module.exports={name:'off'};", "enabled": False}]
    config_store.save_config(cfg)
    payload = _run(control_api.studies_library())
    assert payload["modules"] == []
    assert [c["name"] for c in payload["custom"]] == ["pasted"]


def test_collections_clamp_and_survive_a_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    cfg = config_store.default_config()
    cfg["studies"]["collections"] = {
        "Scalp reads": {"saved": 5, "active": [
            {"name": "deltaFlow", "params": {"window": "20"}, "visible": True},
            {"name": "2 bad name", "params": {}},                      # dropped by the shared clamp
        ]},
        "": {"active": []},                                            # unnamed: dropped
        "nested": {"active": [{"name": "ema", "params": {"period": {"x": 1}}}]},   # nested param dropped
    }
    saved = config_store.save_config(cfg)["studies"]
    assert set(saved["collections"].keys()) == {"Scalp reads", "nested"}
    assert [e["name"] for e in saved["collections"]["Scalp reads"]["active"]] == ["deltaFlow"]
    assert saved["collections"]["nested"]["active"][0]["params"] == {}


def test_collection_actions_round_trip_through_the_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    active = [{"name": "ema", "params": {"period": 9}, "visible": True}]
    _run(control_api.studies_save({"active": active}))
    saved = _run(control_api.studies_save({"collection": {"action": "save", "name": "Trend"}}))
    assert saved["ok"] is True
    assert [e["name"] for e in saved["studies"]["collections"]["Trend"]["active"]] == ["ema"]
    # applying swaps the live list
    _run(control_api.studies_save({"active": [{"name": "atr", "params": {}, "visible": True}]}))
    applied = _run(control_api.studies_save({"collection": {"action": "apply", "name": "Trend"}}))
    assert [e["name"] for e in applied["studies"]["active"]] == ["ema"]
    # deleting forgets it; a second apply is refused with a reason
    deleted = _run(control_api.studies_save({"collection": {"action": "delete", "name": "Trend"}}))
    assert "Trend" not in deleted["studies"]["collections"]
    refused = _run(control_api.studies_save({"collection": {"action": "apply", "name": "Trend"}}))
    assert refused["ok"] is False and "unknown collection action" in refused["error"]


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_saving_a_module_derives_its_name(monkeypatch, tmp_path):
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    source = "module.exports = {\n  name: 'myStudy',\n  calculator: class { map(d) { return d.close(); } }\n};"
    payload = _run(control_api.studies_save({"custom_source": source}))
    assert payload["ok"] is True
    assert [c["name"] for c in payload["studies"]["custom"]] == ["myStudy"]
    # and a module with no name is refused with a reason instead of being stored
    refused = _run(control_api.studies_save({"custom_source": "module.exports = {};"}))
    assert refused["ok"] is False and "name field" in refused["error"]


def test_saving_the_active_list_round_trips(monkeypatch, tmp_path):
    monkeypatch.setattr(config_store, "config_path", lambda: tmp_path / "config.json")
    active = [{"name": "ema", "params": {"period": 9}, "visible": True}]
    payload = _run(control_api.studies_save({"active": active}))
    assert payload["studies"]["active"] == active
    on_disk = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert on_disk["studies"]["active"] == active


# ── the runtime itself ─────────────────────────────────────────────────────────────
def _node(script: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["node", str(script)], cwd=str(UI), capture_output=True, text=True, encoding="utf-8", timeout=120)


def test_runtime_self_test_passes():
    result = _node(UI / "study-api.selftest.js")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 failed" in result.stdout and "ok," in result.stdout


def test_contract_style_module_runs_through_the_shim(tmp_path):
    """A module written the way this suite's indicator contract documents it — CommonJS export, predef params,
    meta enums, require('./tools/…') — must load and run here unchanged in shape."""
    script = tmp_path / "compat.js"
    script.write_text(r'''
const path = require('path');
const StudyAPI = require(path.join(process.env.OFAP_UI, 'study-api.js'));

const source = `
const predef = require('./tools/predef');
const meta = require('./tools/meta');
const MMA = require('./tools/MMA');
const trueRange = require('./tools/trueRange');

class averageTrueRange {
    init() { this.movingAverage = MMA(this.props.period); }
    map(d, i, history) {
        const atr = this.movingAverage(trueRange(d, history.prior()));
        const atrInTicks = atr / this.contractInfo.tickSize;
        let overrideStyle;
        if (atrInTicks > this.props.threshold) {
            overrideStyle = { color: d.open() > d.close() ? 'salmon' : 'lightgreen' };
        }
        return { value: atr, candlestick: overrideStyle, style: { value: overrideStyle } };
    }
}
module.exports = {
    name: 'compatATR',
    description: 'ATR (contract-shaped)',
    calculator: averageTrueRange,
    params: { period: predef.paramSpecs.period(14), threshold: predef.paramSpecs.number(10, 1, 0) },
    inputType: meta.InputType.BARS,
    areaChoice: meta.AreaChoice.NEW,
    tags: ['Compat'],
    plotter: predef.plotters.columns('value'),
    schemeStyles: predef.styles.solidLine('#ffe270')
};`;

const loaded = StudyAPI.loadModuleSource(source, { label: 'compat' });
if (!loaded.ok) { console.log('FAIL load: ' + JSON.stringify(loaded.errors)); process.exit(1); }
if (loaded.name !== 'compatATR') { console.log('FAIL name: ' + loaded.name); process.exit(1); }

const bars = [];
let price = 100;
for (let i = 0; i < 40; i++) {
    const open = price;
    price += (i % 4 === 0 ? -0.6 : 0.3);
    bars.push({ time: 1700000000 + i * 60, open, high: Math.max(open, price) + 0.4,
                low: Math.min(open, price) - 0.4, close: price, volume: 20, buy_volume: 12,
                sell_volume: 8, bar_delta: 4 });
}
const run = StudyAPI.run(StudyAPI.registry.get('compatATR'), bars, { period: 5, threshold: 1 }, { tickSize: 0.25 });
if (!run.ok) { console.log('FAIL run: ' + JSON.stringify(run.errors)); process.exit(1); }
if (!run.plots.value.length) { console.log('FAIL no values'); process.exit(1); }
if (!run.plots.value.some((p) => p.style && p.style.color)) { console.log('FAIL no threshold styling'); process.exit(1); }

// failure paths: no name, a throwing module, an unavailable require
const noName = StudyAPI.loadModuleSource('module.exports = {};', { label: 'x' });
const throws = StudyAPI.loadModuleSource('throw new Error("boom");', { label: 'x' });
const badRequire = StudyAPI.loadModuleSource(
    'const z = require("some-npm-package"); module.exports = { name: "z", calculator: { map() {} } };', { label: 'x' });
if (noName.ok !== false || throws.ok !== false || badRequire.ok !== false) {
    console.log('FAIL failure paths: ' + JSON.stringify([noName, throws, badRequire]));
    process.exit(1);
}
console.log('compat ok: ' + run.plots.value.length + ' values, ' + StudyAPI.registry.list().length + ' registered');
''', encoding="utf-8")
    import os
    env = dict(os.environ, OFAP_UI=str(UI))
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "compat ok:" in result.stdout


def test_shipped_studies_all_register(monkeypatch, tmp_path):
    """Every shipped module must pass the same validation the UI applies at load time."""
    script = tmp_path / "pack.js"
    script.write_text(r'''
const path = require('path');
const fs = require('fs');
const UI = process.env.OFAP_UI;
const StudyAPI = require(path.join(UI, 'study-api.js'));
const dir = path.join(UI, 'indicators');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.js'));
const bad = [];
for (const file of files) {
    const def = require(path.join(dir, file));
    const check = StudyAPI.validate(def);
    if (!check.ok) bad.push(file + ': ' + check.errors.join('; '));
    else StudyAPI.registry.register(def);
}
console.log(JSON.stringify({ files: files.length, registered: StudyAPI.registry.list().length, bad }));
''', encoding="utf-8")
    import os
    env = dict(os.environ, OFAP_UI=str(UI))
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["bad"] == [], payload["bad"]
    assert payload["files"] >= 6 and payload["registered"] == payload["files"]


# ── the Guide section it contributes ───────────────────────────────────────────────
def test_every_guide_section_it_pushes_uses_the_heading_shape():
    """GUIDE_SECTIONS entries are {h, body} — the Guide renders `s.h` as the card title and the
    palette indexes `s.h` as the search title.

    The studies entry shipped as {title, lead, body}, so the Guide card read "undefined" and every
    non-empty palette query threw `Cannot read properties of undefined (reading 'toLowerCase')` in
    searchScore (found live in the P1-9 pass, §44). A push block without `h:` is that bug again.
    """
    import re
    for name in ("studies.js", "guide.js"):
        text = (UI / name).read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"GUIDE_SECTIONS\.push\(\{", text):
            block = text[match.end():match.end() + 400]
            assert re.search(r"\bh:", block), f"{name}: a GUIDE_SECTIONS.push without an `h:` heading"
