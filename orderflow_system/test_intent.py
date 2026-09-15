"""The interaction arbiter exists, is loaded, is tagged, and is actually consulted by the pollers and
the writers - a module nobody asks is decoration."""
from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"


def _read(name):
    return (UI / name).read_text(encoding="utf-8")


def test_arbiter_is_loaded_and_tagged():
    intent = _read("intent.js")
    html = _read("index.html")
    assert "OFAPINTENT" in intent
    assert "intent.js" in html, "the arbiter must be loaded"
    assert 'data-surface="ofx"' in html and 'data-surface="heatmap"' in html
    assert html.count('data-surface="') >= 6, "the whole shell, not one view"


def test_pollers_defer_instead_of_fighting():
    for name, marker in (("ofx-view.js", "OFAPINTENT.held('ofx')"),
                         ("heatmap-pro.js", "deferKeyed('heatmap'"),
                         ("ui.js", "OFAPINTENT.anyHeld()"),
                         ("atlas-v2.js", "OFAPINTENT.held('trackers')")):
        assert marker in _read(name), "%s must consult the arbiter (%s)" % (name, marker)


def test_writers_are_coalesced():
    assert "queueWrite('ofx.params'" in _read("ofx-view.js")
    assert "queueWrite('hm.export." in _read("heatmap-pro.js")


def test_freeze_holds_the_view_and_never_the_feed():
    intent = _read("intent.js")
    assert "freezeView" in intent and "setFeed" in intent
    # nothing in the arbiter may call the engine or the socket
    for forbidden in ("engine/stop", "engine/restart", "engine/start", "/api/control/engine"):
        assert forbidden not in intent, "the arbiter must not touch ingest (%s)" % forbidden
    assert "OFAPINTENT.freezeView" in _read("pause.js"), "the P freeze must drive the arbiter"
