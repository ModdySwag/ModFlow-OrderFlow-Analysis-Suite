"""Gate for the control-surface fixes (the v2 competitive-reanalysis pass, 2026-09-19).

Pins the truths the control-surface audit caught and this pass fixed:

  * the Frames control offers the sixth family the engine builds (delta);
  * no two Bars options render the same word (the duplicate "candles" pair now reads
    "default" / "classic candles" — the catalogue's own words);
  * the Logs filter can name DEBUG (its help entry existed but no option matched);
  * the hover-help map resolves every option of the selects it decorates, matched
    case-insensitively (a label "1H" against a key '1h' was the F-6 drift);
  * the Settings Data-source dropdown is built from /api/control/sources — the Data menu's
    own endpoint — so the two surfaces cannot disagree;
  * the calendar filters persist through the store, clamped.

Mirror of `search.js`'s lookup rules, in Python, so the two halves are held equal by a test.
"""

from __future__ import annotations

import re
from pathlib import Path

PKG = Path(__file__).resolve().parent
UI = PKG / "desktop" / "ui"


def _html() -> str:
    return (UI / "index.html").read_text(encoding="utf-8")


def _sel_options(html: str, select_id: str) -> list[tuple[str, str]]:
    block = re.search(r'<select[^>]*id="%s".*?</select>' % re.escape(select_id), html, re.S)
    assert block, f"no <select id={select_id}>"
    return re.findall(r'<option(?: value="([^"]*)")?[^>]*>([^<]*)</option>', block.group(0))


def _select_help_keys() -> dict[str, set[str]]:
    """The SELECT_HELP map out of search.js, per select, keys lowercased."""
    js = (UI / "search.js").read_text(encoding="utf-8")
    block = re.search(r"const SELECT_HELP = \{(.*?)\n\};", js, re.S)
    assert block, "search.js no longer defines SELECT_HELP"
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"(\w+): \{(.*?)\}", block.group(1), re.S):
        sid, body = m.group(1), m.group(2)
        keys = set()
        for km in re.finditer(r"'([^']+)'\s*:|([A-Za-z_][\w]*)\s*:", body):
            keys.add((km.group(1) or km.group(2)).lower())
        out[sid] = keys
    return out


def test_frames_control_offers_the_sixth_family():
    values = [v or t.strip().lower() for v, t in _sel_options(_html(), "frameSelect")]
    assert "delta" in values, values
    assert "Volume · Delta" in _html(), "the view sub-line must name the sixth family too"


def test_bars_options_render_distinct_words():
    texts = [t.strip() for _v, t in _sel_options(_html(), "chartMode")]
    assert "classic candles" in texts and "default" in texts, texts
    assert len(texts) == len(set(texts)), f"two options render the same word: {texts}"


def test_log_filter_can_name_debug():
    opts = _sel_options(_html(), "logLevel")
    assert any((t or "").strip() == "DEBUG" for _v, t in opts), opts


def test_hover_help_covers_every_option_it_decorates():
    html = _html()
    keys = _select_help_keys()
    for sid in ("frameSelect", "tfSelect", "rangeSelect", "logLevel"):
        assert sid in keys, f"SELECT_HELP lost its {sid} block"
        for value, text in _sel_options(html, sid):
            probe = (text.strip() or value).strip().lower()
            if not probe:
                continue
            assert probe in keys[sid], f"{sid}: option {text!r} has no help entry"
    # …and the entries the audit asked for specifically:
    assert "delta" in keys["frameSelect"]
    assert {"1w", "1m"} <= keys["rangeSelect"], "the week/month range keys"
    assert "debug" in keys["logLevel"]
    assert "all levels" in keys["logLevel"]


def test_settings_source_dropdown_builds_from_the_sources_route():
    js = (UI / "ui.js").read_text(encoding="utf-8")
    assert "async function fillSourceOptions()" in js
    assert "'/api/control/sources'" in js
    assert "sourceOptionsFilled" in js


def test_the_replay_instrument_is_a_picker_built_from_the_catalogue():
    """The replay's Instrument control was free text: a symbol the app does not hold is a guess
    the server can only refuse ("must have local history, or use the exchange tape"). It is now
    the same grouped catalogue the Engine's own picker draws from."""
    html = _html()
    assert re.search(r'<select[^>]*id="rpSymbol"', html), "rpSymbol must be a picker"
    assert not re.search(r'<input[^>]*id="rpSymbol"', html), "the free-text input is gone"
    js = (UI / "atlas.js").read_text(encoding="utf-8")
    assert "function fillReplaySymbols()" in js and "instrument.pickerRows(" in js, (
        "its options come from OFAPINSTRUMENT.pickerRows — streaming now → enabled → configured — off")
    assert "api('/api/control/config')" in js and "api('/api/control/engine/status')" in js, (
        "the two halves of the catalogue: the config's instruments and the engine's own status")


def test_the_platform_bridge_symbol_boxes_offer_the_suggested_symbols():
    """Both bridges carry a Symbol box (DTC: the broker-side name, Bookmap: an optional filter).
    Free text with only a placeholder hint asked the user to recall names the server already
    suggests — each box now carries that list as a datalist, and typing still works because a
    bridge name (ESZ6, MNQ 12-26) need not equal an app instrument."""
    js = (UI / "platforms.js").read_text(encoding="utf-8")
    for control in ("plDtcSymbol", "bmSymbol", "ntSymbol"):
        assert f'list="{control}Options"' in js, f"{control} must reference its datalist"
        assert f'id="{control}Options"' in js, f"{control}'s datalist must exist"
    assert js.count("suggested_symbols") >= 2, (
        "the DTC and Bookmap lists come from the server's own suggested_symbols — the lane the "
        "placeholders hint at")
    assert "ninjatraderNames" in js, (
        "the NinjaTrader probe box's options are the terminal names the config already maps — the "
        "terminal's own list cannot be read offline, and inventing one would be worse than none")
    guide = (UI / "guide.js").read_text(encoding="utf-8")
    assert 'list="ntSymbolOptions"' in guide and "G_NT_NAMES" in guide, (
        "the wizard's NinjaTrader test row offers the same list")
    inst = (UI / "instrument.js").read_text(encoding="utf-8")
    assert "function ninjatraderNames(" in inst, "the pure half lives in instrument.js"


def test_the_alpaca_ticker_box_offers_the_accounts_assets():
    js = (UI / "alpaca-card.js").read_text(encoding="utf-8")
    assert 'list="alpAssetOptions"' in js and 'id="alpAssetOptions"' in js, (
        "the ticker box carries a datalist")
    assert "api('/api/control/alpaca/assets')" in js, (
        "filled from the account's own tradable symbols — the lane the look-up reads "
        "(the route rides the control router, so the /api/control prefix is part of it)")
    assert "600000" in js, "and cached, because the route asks Alpaca"


def test_the_calendar_currency_filter_offers_chips():
    """The Currencies box was free text over codes the feed itself lists: the chips are painted
    from the payload's own domain (never a hardcoded list), and a chip writes the same box the
    store persists, so the two controls cannot disagree."""
    js = (UI / "calendar.js").read_text(encoding="utf-8")
    html = _html()
    assert 'id="calCurrencyChips"' in html, "the chip row's host exists in the view"
    assert "function paintChips(payload)" in js and "payload.currencies" in js, (
        "the chips come from the payload's own domain for this window")
    assert "aria-pressed" in js and "cal-chip" in js, "a chip is a real button with its state announced"
    assert "input.value = active.join(',')" in js and "saveAlerts()" in js, (
        "a chip writes the text box and fires the same load/save path its own change event does")
    assert 'data-code=""' in js, "the row carries an 'all' chip so the filter can widen again"


def test_the_calendar_payload_carries_the_currency_domain(monkeypatch):
    """§130 server half: the domain is computed WITHOUT the currency filter — a row that collapsed
    to the current selection could never widen it again."""
    import asyncio
    import time as _time

    from orderflow_system.desktop import api as api_mod
    from orderflow_system.desktop import calendar as cal_mod

    now = int(_time.time() * 1000)
    events = [
        {"currency": "USD", "impact": "high", "at_ms": now + 3600_000, "title": "NFP"},
        {"currency": "EUR", "impact": "high", "at_ms": now + 7200_000, "title": "CPI"},
        {"currency": "usd", "impact": "high", "at_ms": now + 3 * 3600_000, "title": "FOMC"},
        {"currency": "JPY", "impact": "low", "at_ms": now + 3 * 3600_000, "title": "BoJ"},
    ]
    monkeypatch.setattr(cal_mod, "fetch_events_cached",
                        lambda *a, **k: {"ok": True, "stale": False, "error": "",
                                         "fetched_at_ms": now, "events": events})
    payload = asyncio.run(api_mod.calendar_view(hours=48, currencies="USD", impact="high"))
    assert [e["title"] for e in payload["events"]] == ["NFP", "FOMC"], "the filter still filters"
    assert payload["currencies"] == [{"code": "EUR", "count": 1}, {"code": "USD", "count": 2}], (
        "the domain is the window's own codes (case-normalised, below-impact excluded) and is not "
        "collapsed by the currency filter")


def test_the_calendar_filters_persist_through_the_store(tmp_path, monkeypatch):
    from orderflow_system.desktop import config_store

    monkeypatch.setattr(config_store, "config_dir", lambda: tmp_path)
    assert config_store.default_config()["calendar"]["hours"] == 48
    assert config_store.default_config()["calendar"]["impact"] == "high"

    saved = config_store.save_config({"calendar": {"hours": 9999, "impact": "JUNK"}})
    assert saved["calendar"]["hours"] == 720, "hours clamp"
    assert saved["calendar"]["impact"] == "high", "unknown impact reads the shipped default"

    saved = config_store.save_config({"calendar": {"hours": 0, "impact": "medium"}})
    assert saved["calendar"]["hours"] == 1 and saved["calendar"]["impact"] == "medium"

    cal_js = (UI / "calendar.js").read_text(encoding="utf-8")
    assert "hours: Number((($('calHours')" in cal_js, "saveAlerts must carry the window"
    assert "block.hours != null ? block.hours : 48" in cal_js, "boot must restore the window"
    assert "block.impact || 'high'" in cal_js, "boot must restore the impact filter"


def test_the_engine_publishes_the_stages_the_progress_bar_reads():
    """§132 — the progress bar's truth comes from the engine's own stages, not from a timer.

    Pinned: the ordered plan per direction, the marks on the REAL start/stop paths (not just in the
    status payload), and the fields the route serves. The measured shape behind it — a stop is
    10.3 s, of which `release` (the run's own drain) is 10.0 s while `feeds`/`history` are ~0.3 s —
    is what the bar's own pacing and the log's story are built on.
    """
    from orderflow_system.desktop import engine as engine_mod

    plan = engine_mod.EngineController.STAGE_PLAN
    assert plan["starting"] == ("config", "instruments", "build", "connect")
    assert plan["stopping"] == ("feeds", "history", "release")

    src = Path(engine_mod.__file__).read_text(encoding="utf-8")
    for mark in ('self._mark("config")', 'self._mark("instruments")', 'self._mark("build")',
                 'self._mark("connect")', 'self._mark("ready")', 'self._mark("feeds")',
                 'self._mark("history")', 'self._mark("release")', 'self._mark("closed")'):
        assert mark in src, f"the {mark} boundary is gone — the bar would step through a stage the engine never announced"

    state = engine_mod.EngineController().status()
    for key in ("stage", "stage_at", "stage_ms", "stage_plan", "stage_log"):
        assert key in state, f"/engine/status stopped serving {key!r}"
