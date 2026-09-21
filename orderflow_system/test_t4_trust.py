"""T4 — trust & legibility: the settings, markup and wiring pins for the first slice.

A5: the freshness thresholds are a display preference (atlas.freshness, seconds, 0 = the built-in
window) — the sanitiser must keep them and clamp junk, the JS must consume them, and the strip must
carry the delayed badge. A-corr: the 1–9 view-switch map must count rail VIEW items only, or the
injected Setup button shifts every digit by one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orderflow_system.desktop import config_store

UI = Path(__file__).parent / "desktop" / "ui"
INDEX = UI / "index.html"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    return config_store


# ── A5: the thresholds ───────────────────────────────────────────────

def test_defaults_carry_the_freshness_thresholds(store):
    block = store.default_config()["atlas"]["freshness"]
    assert block == {"depth_s": 0, "quote_s": 0, "trades_s": 0, "candles_s": 0}


def test_the_sanitiser_keeps_freshness_and_clamps_junk(store):
    clean = store.save_config({"atlas": {"freshness": {
        "depth_s": "junk", "quote_s": 9000, "trades_s": 7.5, "nope": 1}}})
    fresh = clean["atlas"]["freshness"]
    assert fresh["depth_s"] == 0.0, "junk must fall back to the built-in window"
    assert fresh["quote_s"] == 3600.0, "an hour is the ceiling"
    assert fresh["trades_s"] == 7.5
    assert "nope" not in fresh, "unknown keys are not kept"


def test_the_settings_form_renders_and_the_page_adopts_the_thresholds():
    atlas = _text(UI / "atlas.js")
    for kind in ("depth_s", "quote_s", "trades_s", "candles_s"):
        assert "'freshness', '" + kind + "'" in atlas, f"the settings registry lost {kind}"
    assert "OFAPFRESH.setWindows" in _text(UI / "ui.js"), "a saved threshold never reaches the chips"
    fresh = _text(UI / "freshness.js")
    assert "function setWindows" in fresh and "var USER" in fresh
    assert "function summary" in fresh and "setWindows: setWindows" in fresh
    assert "function onScreen" in fresh, "the strip would nag about parked panels again"
    assert "if (!onScreen(id)) return;" in fresh


# ── A16: the ambient strip ───────────────────────────────────────────

def test_the_strip_carries_the_ambient_readouts():
    html = _text(INDEX)
    for ident in ("statusDelay", "statusOldest", "statusPause"):
        assert 'id="' + ident + '"' in html, f"the strip lost #{ident}"
    css = _text(UI / "modules.css")
    assert ".status-delay" in css


# ── A-corr: the digit map ────────────────────────────────────────────────

def test_every_rail_list_counts_view_items_only():
    """The Setup button (no data-view, first in the rail) must never be counted: the digit map,
    the Ctrl+PgUp/Dn cycle, the digit annotations, the View menu and the command index all index
    by view order."""
    for name in ("keys.js", "menubar.js", "help.js"):
        code = _text(UI / name)
        assert "querySelectorAll('.rail .nav-item')" not in code, (
            name + " counts the Setup button in a rail list — every digit after it shifts by one")
    assert ".rail .nav-item[data-view]" in _text(UI / "keys.js")


# ── A6: inferred analytics say so ─────────────────────────────────────

def test_inferred_analytics_carry_their_label():
    html = _text(INDEX)
    assert "Sweeps (inferred)" in html
    assert html.count('class="tag warn"') >= 3, "the iceberg/sweeps/stop-run inference tags"
    scanner = _text(UI / "scanner.js")
    for col in ("Sweeps", "Stop runs", "Absorb"):
        row = [ln for ln in scanner.splitlines() if "'" + col + "'" in ln]
        assert row and "Inferred from the tape." in row[0], col + " does not say it is inferred"
    atlas = _text(UI / "atlas.js")
    assert "sweeps are inferred" in atlas and "stop runs are inferred" in atlas


# ── A19: sound controls ────────────────────────────────────────────

def test_the_sound_card_is_wired_to_the_player():
    html = _text(INDEX)
    for ident in ("sndEnabled", "sndVolume", "sndTest", "sndResult"):
        assert 'id="' + ident + '"' in html, "the Settings sound card lost #" + ident
    audio = _text(UI / "audio.js")
    assert "function wireControls" in audio and "wireControls: wireControls" in audio
    assert "test: testSound" in audio, "the test button no longer reaches the player"
    assert "var c = clone(cfg);" in audio, "the sound card paints from a function that does not exist"


def test_the_audio_sanitiser_clamps_the_volume(store):
    clean = store.save_config({"audio": {"volume": 5}})
    assert clean["audio"]["volume"] == 1.0
    clean = store.save_config({"audio": {"volume": "junk"}})
    assert clean["audio"]["volume"] == 0.6, "junk must fall back to the safe default"
    assert clean["audio"]["enabled"] is False, "audio stays off unless it is the boolean True"


# ── A17: the update policy ────────────────────────────────────────

def test_the_update_policy_is_written_down_and_linked():
    doc = Path(__file__).parent.parent / "docs" / "UPDATE_POLICY.md"
    assert doc.exists(), "docs/UPDATE_POLICY.md is gone"
    body = doc.read_text(encoding="utf-8")
    assert "Nothing blocks" in body and "Nothing restarts itself" in body
    html = _text(INDEX)
    assert 'data-helptopic="work.updates"' in html, "the update card does not link the policy"
    hd = _text(UI / "help-data.js")
    assert "id: 'work.updates'" in hd and "Updates never block" in hd
    assert "no sound files to ship" not in hd, "the stale audio claim is back"


# ── A9: dynamic tokens + watermarks ─────────────────────────────────

def test_the_watermark_reads_live_state_and_never_invents_one():
    wm = _text(UI / "watermark.js")
    assert "symbolSelect" in wm, "the watermark no longer reads the live instrument"
    assert "el.hidden = !symbol()" in wm, "a watermark must hide when no symbol is readable"
    html = _text(INDEX)
    assert '/desktop/watermark.js' in html
    assert ".ofap-watermark" in _text(UI / "modules.css")


def test_the_widget_title_carries_the_live_token():
    shell = _text(UI / "shell.js")
    assert "function titleToken" in shell
    assert "title.textContent = titleToken(view)" in shell
    assert "S.frames.forEach" in shell, "the titles are never refreshed after an instrument change"


def test_changing_the_instrument_actually_repaints_the_titles():
    """The refresh above only runs when the shell's status pass runs, and nothing called it on a
    symbol change: measured live (§130) every frame kept the symbol it was BUILT with — after moves
    to ETHUSDT / SOLUSDT / XRPUSDT the montage still read "· BTCUSDT" minutes later, which is the
    owner's photographed "panel says ETHUSDT, title says BTCUSDT" contradiction. The top bar must
    ask for the repaint, through the shell's own exported pass."""
    ui = _text(UI / "ui.js")
    handler = ui.split('$("#symbolSelect").onchange', 1)[1].split("};", 1)[0]
    assert "ofap:symbol" in handler, "the top bar stopped announcing its instrument"
    assert "OFAPSHELL.paintStatus" in handler, "the frame titles are stale again after a symbol change"
    assert "paintStatus: paintStatus" in _text(UI / "shell.js"), "the shell no longer exports the repaint"


def test_a_widgets_hover_text_lives_on_its_grip_not_over_its_content():
    """The owner's screenshot (§131): "Guide & setup · 3×2 cells" popped over the panel's own text —
    the FRAME element carried a native title, so the tooltip covered the whole widget and fired
    wherever the pointer sat, including over the chart or the prose being read (measured: every
    widget frame in both modes carried `view · 6×4 cells`). A widget's hover text belongs to a
    CONTROL (the resize grip); the frame bar already names the widget and hints the move."""
    shell = _text(UI / "shell.js")
    assert "frame.title" not in shell, "a whole-panel tooltip is back — it covers the widget's content"
    assert "function gripTip(" in shell and "grip.title = gripTip(" in shell, "the grip lost its own hover text"
    assert "now ' + w + '×' + h + ' cells" in shell, "the grip stopped saying how big the widget is"
    assert "Drag to move this widget" in shell, "the frame bar's own move hint is gone"


def test_the_chart_retry_is_bounded():
    """FG-06 (final release audit): the chart's retry-until-it-lands watch ran forever at a 5 s
    cadence while the Chart view stayed open — a permanently failing load cost one request every
    5 s, with no attempt cap and nothing said. Bounded now: CHART_RETRY_MAX tries, then the watch
    stops and the chart head says so; a landed load or a new selection resets the budget."""
    ui = _text(UI / "ui.js")
    assert "CHART_RETRY_MAX" in ui, "the chart retry lost its cap"
    watch = ui.split("function chartLoadWatch()", 1)[1].split(chr(10) + "}", 1)[0]
    assert "chartRetryTries >= CHART_RETRY_MAX" in watch, "chartLoadWatch retries without a bound again"
    assert "did not load" in watch, "the bounded retry stopped saying what happened"
    handler = ui.split('$("#symbolSelect").onchange', 1)[1].split("};", 1)[0]
    assert "chartRetryTries = 0" in handler, "a new selection must reset the retry budget"


def test_the_live_chip_reuses_the_status_payload():
    """FG-07 (final release audit): refreshLiveChip() spent a second GET /engine/status on every
    status application (2 s; 480 ms during transitions) although applyStatus already held the very
    payload it wanted. The payload is handed over now; only a bare call fetches."""
    ui = _text(UI / "ui.js")
    assert "async function refreshLiveChip(status)" in ui, "the live chip fetches instead of reusing the payload"
    assert "const st = status || await api(" in ui, "the payload hand-over is gone"
    assert "refreshLiveChip(payload);" in ui, "the status path stopped handing its payload over"


def test_the_top_bar_and_help_say_that_a_pick_can_start_the_engine():
    """FG-05 (final release audit): with the Engine view initialised, picking an instrument starts
    the engine (ofx-view's pickSymbol → resolve 'ready' → runInstrumentAction('start_engine')) —
    designed (§82) and reproduced live, but nothing in the top bar said so. Documentation-only
    fix: the selector's own tooltip and the Instruments help topic both state it."""
    page = _text(UI / "index.html")
    assert 'id="symbolSelect" title=' in page, "the selector stopped saying a pick can start the engine"
    assert "starts the engine when it is stopped" in page
    help_data = _text(UI / "help-data.js")
    assert "starts the engine when it is stopped" in help_data, "the help topic lost the note"
