"""Alert rules read like sentences (P1-7).

`alert-format.js` is the one place that turns a rule into words, and the Rules card renders it while
the inline editor builds its fields from the same spec — so the form and the words cannot disagree.
Pinned here: the module and its selftest exist and are green, it is pure (no DOM, no API, no storage,
so the selftest means something), index.html loads it BEFORE atlas.js (which reads it), and — the
check that matters most — the params it offers per kind are exactly the params
`AlertEngine._passes()` reads for that kind. A field the engine ignores is a lie in a form; a knob
the engine honours but the form never shows is a feature nobody can reach.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from orderflow_system.atlas.alerts import DEFAULT_RULES, KINDS

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "orderflow_system" / "desktop" / "ui"
MODULE = UI / "alert-format.js"
SELFTEST = UI / "alert-format.selftest.js"
ALERTS_PY = ROOT / "orderflow_system" / "atlas" / "alerts.py"

#: The engine's own tuple plus `wall_age`, the kind the depth map emits (`depthmap._record`).
ENGINE_KINDS = sorted(set(KINDS) | {"wall_age"})


@pytest.fixture(scope="module")
def source() -> str:
    return MODULE.read_text(encoding="utf-8")


def _js_kinds_and_params(source: str) -> dict[str, set[str]]:
    """The kind catalogue as the JS holds it: kind -> the param keys its spec names."""
    body = source.split("const KINDS = {", 1)[1].split("/* The kind every rule", 1)[0]
    out: dict[str, set[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        head = re.match(r"^        ([a-z_]+): \{\s*$", line)
        if head:
            current = head.group(1)
            out[current] = set()
            continue
        if current:
            found = re.search(r"\bkey: '([a-z_]+)'", line)
            if found:
                out[current].add(found.group(1))
    return out


def _passes_params_by_kind() -> dict[str, set[str]]:
    """kind -> the params `_passes()` reads in that kind's own branch."""
    src = ALERTS_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    segment = next(ast.get_source_segment(src, node) for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == "_passes")
    assert segment, "_passes() moved or was renamed — this gate reads it by name"

    out: dict[str, set[str]] = {}
    kinds: list[str] = []
    lines: list[str] = []

    def flush() -> None:
        block = "\n".join(lines)
        for kind in kinds:
            out[kind] = set(re.findall(r'params\.get\("(\w+)"', block))

    for line in segment.splitlines():
        head = re.match(r'\s*if kind (?:== "(\w+)"|in \(([^)]*)\))\s*:', line)
        if head:
            flush()
            kinds = [head.group(1)] if head.group(1) else re.findall(r'"(\w+)"', head.group(2))
            lines = []
            continue
        lines.append(line)
    flush()
    return out


def test_the_module_and_its_selftest_are_present():
    assert MODULE.exists(), "alert-format.js is the one place a rule becomes words"
    assert SELFTEST.exists(), "the module carries its own gate"


def test_it_parses():
    out = subprocess.run(["node", "--check", str(MODULE)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_its_selftest_passes():
    out = subprocess.run(["node", str(SELFTEST)], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert re.search(r"alert-format selftest: \d+ ok, 0 failed", out.stdout), out.stdout


def test_it_is_registered_with_the_audit():
    audit = (ROOT / "scripts" / "audit_ui_refs.py").read_text(encoding="utf-8")
    assert '"alert-format.js"' in audit, "the audit cross-checks api() calls and element ids per module"


def test_it_stays_pure(source):
    """A module the selftest can run without a browser has to keep the browser out of it."""
    assert "document." not in source, "the selftest boots this with a stub window, not a DOM"
    assert "fetch(" not in source and "OFAPBUS" not in source, "words do not need the wire"
    assert "localStorage" not in source and "sessionStorage" not in source, "the config is the record"


def test_it_loads_before_the_module_that_reads_it():
    html = (UI / "index.html").read_text(encoding="utf-8", errors="replace")
    assert "/desktop/alert-format.js" in html, "the Alerts card renders OFAPALERTS.sentence()"
    assert html.index("/desktop/alert-format.js") < html.index("/desktop/atlas.js"), \
        "atlas.js reads OFAPALERTS at boot — the script tag must come first"


def test_every_kind_the_engine_evaluates_is_in_the_catalogue(source):
    catalogue = _js_kinds_and_params(source)
    missing = [k for k in ENGINE_KINDS if k not in catalogue]
    assert not missing, f"the editor cannot render these kinds: {missing}"


def test_every_shipped_default_rule_can_be_rendered(source):
    catalogue = _js_kinds_and_params(source)
    for rule in DEFAULT_RULES:
        assert rule["kind"] in catalogue, f"default rule {rule['id']} has no catalogue entry"


def test_the_js_offers_exactly_the_params_the_engine_reads(source):
    """The editor's fields and the evaluator's thresholds are one contract, checked both ways."""
    js = _js_kinds_and_params(source)
    engine = _passes_params_by_kind()

    for kind in ENGINE_KINDS:
        expected = engine.get(kind, set())
        offered = js.get(kind, set())
        assert offered == expected, (
            f"{kind}: the form offers {sorted(offered)} but _passes() reads {sorted(expected)}")


def test_the_scope_fields_are_the_ones_evaluate_checks_generically(source):
    scope_block = source.split("const SCOPE_FIELDS = [", 1)[1].split("];", 1)[0]
    js_scope = set(re.findall(r"key: '(\w+)'", scope_block))
    src = ALERTS_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    segment = next(ast.get_source_segment(src, node) for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == "evaluate")
    engine_scope = set(re.findall(r'params\.get\("(\w+)"', segment))
    assert js_scope == engine_scope, (
        f"the rule's scope in the form is {sorted(js_scope)}, the evaluator checks {sorted(engine_scope)}")


def test_the_heatmap_prefix_matches_the_module_that_writes_it():
    spec = (UI / "heatmap-pro.js").read_text(encoding="utf-8")
    assert "'hm-' +" in spec, "heatmap-pro.js names its rules with the prefix the filter counts"
    module = MODULE.read_text(encoding="utf-8")
    assert "HEATMAP_PREFIX = 'hm-'" in module, "the prefix lives in one place"


def test_the_editor_reads_its_channel_checkboxes_by_key():
    """A checkbox carries no value unless one is written into the markup, so `b.value` returns the
    literal "on" for every ticked channel — measured live, the edited rule's sentence read
    'UI log + on + on' and a save would have stored a channel called "on"."""
    src = (UI / "atlas.js").read_text(encoding="utf-8")
    anchor = next((line for line in src.splitlines()
                   if "input[data-channel]" in line and "querySelectorAll" in line), None)
    assert anchor, "the editor's channel checkboxes moved — this guard reads them where they are"
    block = src[src.index(anchor):src.index(anchor) + 400]
    assert "getAttribute('data-channel')" in block, "channels are read by their own key"
    assert "=> b.value" not in block, "a checkbox has no value of its own"
