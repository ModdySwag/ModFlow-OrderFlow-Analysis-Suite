"""Wave B T11 — B14 (UI scale + font zoom) · B15 (contrast tiers) · B17 (link-group colours).

The pure halves are executed by links.selftest.js and theme.js's own clamps; this file pins the
contracts around them: the config record and its clamps, the Appearance card, the CSS tier blocks,
the pre-paint mirror, and the wiring landmarks each surface reads them through.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from orderflow_system.desktop import config_store

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"

TIERS = ("calm", "standard", "aggressive")
GROUP_DEFAULTS = {"A": "#6ec1ff", "B": "#ffb454", "C": "#7fe0a8", "D": "#d49bff"}


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def _selftest(name: str) -> subprocess.CompletedProcess:
    node = shutil.which("node") or "node"
    return subprocess.run([node, str(UI / name)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def test_b14_and_b15_defaults_are_the_shipped_look() -> None:
    ui = config_store.default_config()["ui"]
    assert ui["contrast"] == "standard"
    assert float(ui["scale"]) == 1.0
    assert ui["link_colors"] == GROUP_DEFAULTS


def test_b14_and_b15_sanitiser_clamps() -> None:
    cfg = config_store.default_config()
    cfg["ui"]["contrast"] = "loud"
    cfg["ui"]["scale"] = 99
    cfg["ui"]["link_colors"] = {"A": "red", "B": "#00ff00", "X": "#123456"}
    out = config_store._sanitise(cfg)
    assert out["ui"]["contrast"] == "standard", "an unknown tier reads standard"
    assert out["ui"]["scale"] == 1.5, "the scale clamps to its ceiling"
    assert out["ui"]["link_colors"] == {"A": GROUP_DEFAULTS["A"], "B": "#00ff00",
                                        "C": GROUP_DEFAULTS["C"], "D": GROUP_DEFAULTS["D"]}, \
        "junk colours restore the default; the extra key is dropped"
    cfg["ui"]["scale"] = 0.5
    assert config_store._sanitise(cfg)["ui"]["scale"] == 0.75
    cfg["ui"]["scale"] = "junk"
    assert config_store._sanitise(cfg)["ui"]["scale"] == 1.0
    cfg["ui"]["contrast"] = "aggressive"
    cfg["ui"]["scale"] = 1.35
    out2 = config_store._sanitise(cfg)
    assert out2["ui"]["contrast"] == "aggressive" and out2["ui"]["scale"] == 1.35


def test_b15_tiers_are_css_on_the_root_attribute() -> None:
    css = _text("atlas.css")
    for tier in ("calm", "aggressive"):
        block = re.search(r'html\[data-contrast="' + tier + r'"\]\s*\{([^}]*)\}', css)
        assert block, tier
        assert block.group(1).count("--of-") >= 3, "each tier overrides real tokens: " + tier


def test_b14_and_b15_the_appearance_card_offers_both() -> None:
    html = _text("index.html")
    card = re.search(r'setDensity.*?</div>\s*</div>', html, re.S)
    assert card, "the Appearance card"
    assert 'id="setContrast"' in card.group(0)
    assert [v for v in TIERS if f'<option value="{v}"' in card.group(0)] == list(TIERS)[0:1] + ["standard", "aggressive"]
    assert 'id="setScale"' in card.group(0) and "min=\"0.75\"" in card.group(0) and "max=\"1.5\"" in card.group(0)
    # the pre-paint mirror carries both, so the first paint is already right
    assert "dataset.contrast" in html and "setProperty('--ui-scale'" in html


def test_b14_the_theme_module_applies_and_binds() -> None:
    src = _text("theme.js")
    for marker in ("const CONTRASTS = ['calm', 'standard', 'aggressive']",
                   "root.dataset.contrast = state.contrast",
                   "root.style.setProperty('--ui-scale'",
                   "root.style.zoom",
                   "SCALE_MIN = 0.75, SCALE_MAX = 1.5, SCALE_STEP = 0.05",
                   "function clampScale",
                   "id: 'ui-scale-in'", "id: 'ui-scale-out'", "id: 'ui-scale-reset'",
                   "'ctrl+='", "'ctrl+0'", "OFAPScale.fit('ui-scale')"):
        assert marker in src, marker


def test_b17_the_chip_carries_colour_but_never_alone() -> None:
    shell = _text("shell.js")
    assert "L.colorOf(g)" in shell and "b.textContent = g || '–'" in shell, \
        "the chip colours the letter, the letter stays"
    assert "[data-color-group]" in shell and "function linkColorRow" in shell
    links = _text("links.js")
    for marker in ("FALLBACK_COLORS", "COLOR_CYCLE", "function colorOf", "function nextColor",
                   "function setColor", "function cycleColor", "ofap:link-colors"):
        assert marker in links, marker


def test_b17_the_pure_half_passes_its_selftest() -> None:
    run = _selftest("links.selftest.js")
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "0 failed" in run.stdout
