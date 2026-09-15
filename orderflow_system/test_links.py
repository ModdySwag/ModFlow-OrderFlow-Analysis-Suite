"""Link groups (desktop/ui/links.js) — the local half of the symbol/timeframe link.

A link group is two things at once, and this gates both: MEMBERSHIP lives in the layout (each widget's
`link` field, which the config store sanitises and `test_layouts` covers), while what a group MEANS is
runtime state the module derives from the panels that are already on screen. The module decides who
moves without touching the DOM (its `plan`), so its Node self-test can pin the rule the phase-3 gate is
about — a group change moves its members, and nothing else — and Python can check the invariants that
keep it safe: it is loaded, ordered after the shell, registered with the audit, and it never reaches
for the engine. A "link" that restarted ingest would take the whole dashboard down with a click.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).parent / "desktop" / "ui"
LINKS = UI / "links.js"
SHELL = UI / "shell.js"
SELFTEST = UI / "links.selftest.js"
ROOT = Path(__file__).resolve().parents[1]


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_links_files_exist():
    assert LINKS.is_file(), "desktop/ui/links.js is missing"
    assert SELFTEST.is_file(), "desktop/ui/links.selftest.js is missing"


def test_the_links_module_parses_as_javascript():
    proc = subprocess.run([_node(), "--check", str(LINKS)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_the_links_selftest_passes():
    proc = subprocess.run([_node(), str(SELFTEST)], capture_output=True, text=True, timeout=120,
                          cwd=str(ROOT))
    out = proc.stdout.strip()
    match = re.search(r"links selftest: (\d+) ok, (\d+) failed", out)
    assert match, f"unexpected selftest output: {out!r}\n{proc.stderr}"
    ok, failed = int(match.group(1)), int(match.group(2))
    assert failed == 0, out
    assert ok >= 10, f"the self-test shrank to {ok} checks — expected the membership and shape rules"
    assert proc.returncode == 0


def test_the_links_module_exposes_the_documented_surface():
    src = _read(LINKS)
    assert "window.OFAPLINKS" in src
    for name in ("plan", "controlsOf", "groups", "members", "setGroup", "apply", "seed", "sweep",
                 "tfLabel", "state", "GROUPS", "SYMBOL_CONTROL", "GLOBAL_SYMBOL", "TIMEFRAME_CONTROL"):
        assert name in src, f"links.js must expose {name}"
    assert "['A', 'B', 'C', 'D']" in src, "the groups are A-D"


def test_the_shell_carries_the_membership_and_the_module_reads_it():
    """One half in the layout, one half in the module — and each side says which is which."""
    shell = _read(SHELL)
    links = _read(LINKS)
    for name in ("linkSpec", "setLink", "linkMembers", "paintLinkChip", "parseLink", "formatLink"):
        assert name in shell, f"the shell must carry {name}"
    for call in ("linkMembers", "linkSpec", "paintLinkChip"):
        assert "OFAPLINKS" in links, "the module must reach the shell through its public surface"
        assert call in links, f"links.js reads {call}"
    assert "ofap:links" in shell and "ofap:links" in links, \
        "the shell announces a membership change and the module re-reads on it"


def test_the_membership_shape_matches_the_store():
    """The JS writer and the Python sanitizer must accept exactly the same strings."""
    pattern = config_store.LAYOUT_LINK_RE
    for good in ("A/B", "A/", "/B", "D/D", "A", ""):
        assert pattern.match(good), f"the store must keep {good!r}"
    for bad in ("E/A", "1/B", "A/BB", "x/y", "A/B/C", "AB", "A-B", "A//B"):
        assert not pattern.match(bad), f"the store must drop {bad!r}"
    #: "/" is the one string the pattern allows and the sanitiser still drops: it links neither half.
    keep = _stored_links(["A/B", "A/", "/B", "/", "E/Z", "", " a/b "])
    assert keep[:3] == ["A/B", "A/", "/B"] or keep[:3] == ["A/B", "A/", "", "/B"], \
        f"links survive as written: {keep}"
    assert "" in keep, "a link that is not a link is stored as no link"
    assert "E/Z" not in keep and "A/B" in keep, "junk is dropped, not kept as text"
    assert any(text == "A/B" for text in keep[4:]), "the store upper-cases and trims what the shell wrote"


def _stored_links(links: list[str]) -> list[str]:
    """What the config store keeps of each link string, round-tripped through the block."""
    cfg = {"layouts": {"mode": "terminal", "active": "one", "items": {"one": {
        "name": "One", "tabs": [{"id": "t1", "widgets": [
            {"view": "ofx", "x": 0, "y": 0, "w": 2, "h": 2, "link": text} for text in links]}]}}}}
    config_store._sanitise_layouts(cfg)
    kept = cfg["layouts"]["items"]["one"]["tabs"][0]["widgets"]
    return [w["link"] for w in kept]


def test_the_links_module_is_loaded_after_the_shell():
    html = _read(UI / "index.html")
    assert 'src="/desktop/links.js"' in html, "index.html must load the links module"
    assert html.index('src="/desktop/shell.js"') < html.index('src="/desktop/links.js"'), \
        "the shell defines the layout the module reads from"
    assert "links.js" in _read(ROOT / "scripts" / "audit_ui_refs.py"), "register it in JS_FILES"


def test_linking_never_touches_ingest():
    """A symbol link sets a control and lets the app's own handler do the work — nothing else."""
    src = _read(LINKS)
    for forbidden in ("/api/", "fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
                      "engine/start", "engine/stop", "engine/restart"):
        assert forbidden not in src, f"links.js must not reach the engine ({forbidden})"
    assert "dispatchEvent(new Event('change'" in src, "it drives the panels' own change path"


def test_the_group_values_come_from_the_panels():
    """A group with no stored value adopts the panels' own — the panels are the authority."""
    src = _read(LINKS)
    assert "function seedGroups" in src
    assert "panelValue(kind, holder.view)" in src, "seeding reads a member's control"
    assert "state.groups[group][key] = value" in src, "and only when the group has no value yet"
