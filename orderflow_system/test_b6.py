"""Wave B T14a — B6: the instrument look-up overlay.

The overlay itself is browser code; this pins its contracts: the persisted filters and their
clamps, the venue-confirmed routes every action goes through, and the three doors that open it.
"""

from __future__ import annotations

from pathlib import Path

from orderflow_system.desktop import config_store

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _text(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


def test_the_filters_persist_and_clamp() -> None:
    cfg = config_store.default_config()
    assert cfg["ui"]["lookup"] == {"source": "all", "type": "all", "text": ""}
    cfg["ui"]["lookup"] = {"source": "zzz", "type": 123, "text": "x" * 400}
    out = config_store._sanitise(cfg)["ui"]["lookup"]
    assert out["source"] == "all", "an unknown connection reads all"
    assert out["type"] == "123" and len(out["text"]) <= 120
    cfg["ui"]["lookup"] = {"source": "mt5", "type": "Forex", "text": "EUR"}
    out2 = config_store._sanitise(cfg)["ui"]["lookup"]
    assert out2 == {"source": "mt5", "type": "Forex", "text": "EUR"}


def test_every_action_goes_through_a_confirmed_route() -> None:
    src = _text("lookup.js")
    for marker in ("/api/control/instruments/catalog", "'/api/control/mt5/symbols?q='",
                   "'/api/control/instruments/add'", "source: source, enable: true",
                   "searchActivateSymbol(sym, {})"):
        assert marker in src, marker
    assert "no Alpaca account is linked" in src, "absent data is said, not faked"
    assert "'ui.lookup'" not in src and "ui: { lookup:" in src, "the persistence rides the config patch"


def test_the_three_doors_open_the_overlay() -> None:
    hint = _text("hint.js")
    assert hint.index("OFAPLOOKUP.open") < hint.index("run('lookup')"), \
        "the Instruments button opens the overlay; the walkthrough stays as the fallback"
    assert "Open the instrument look-up across feeds" in _text("search.js"), "the palette action"
    html = _text("index.html")
    assert html.index("/desktop/lookup.js") > html.index("/desktop/instrument.js")
    css = _text("modules.css")
    assert ".lk-overlay" in css and ".lk-row" in css
