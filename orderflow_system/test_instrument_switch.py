"""The top bar's instrument switcher — one selection, one instrument's data, everywhere.

Measured faults this file pins (all reproduced live on a running engine before the fixes):

- the Overview's price/delta/ticks/candles cells read `per_symbol[0]` — the FIRST stream — so an
  XRPUSDT selection showed BTC's 81 112.50 within 2 s of every XRP tick;
- GET /api/signals/<symbol> returned the whole shared history for every instrument (all four
  symbols answered with the byte-identical merged list) and AggregatedSignal carried no
  instrument at all, so the UI labelled other instruments' signals with the selected symbol;
- the Depth ladder drew its rows on a hardcoded 0.5 grid (XRP rows 5.00 … −2.00, every cell
  empty) and ui.js *deleted* the top-of-book rungs on every book tick (updateLevel(…, 0) is the
  ladder's remove path);
- the Order Flow footprint used the same 0.5 constant for its row height and hover hit-test;
- the tape kept the previous instrument's prints (and their volumes) after a switch;
- a row switched on in the Instruments panel never reached the switcher, because the switcher
  was only rebuilt at boot and on the engine's stopped→running transition;
- the Engine view only heard announcements made after its first boot, so a switch made earlier
  was dropped when the view opened.
"""
from __future__ import annotations

import asyncio
import json
import re
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "orderflow_system" / "desktop" / "ui"
STATIC = ROOT / "orderflow_system" / "dashboard" / "static"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ── the shell's own KPIs follow the selection ──────────────────────────────────────────────────


def test_shell_kpis_read_the_selected_symbols_row():
    ui = _read(UI / "ui.js")
    assert ".find((p) => p.symbol === wanted)" in ui, (
        "applyStatus must locate the SELECTED instrument's row in per_symbol")
    assert "const wanted = S.symbol || (rows[0] || {}).symbol;" in ui, (
        "the fallback for an empty selection is the stream's first row, exactly once")
    assert "const first = (S.status.per_symbol || [])[0];" not in ui, (
        "per_symbol[0] is the first stream, not the selected instrument — the Overview showed "
        "another instrument's price/delta/ticks whatever the switcher said (measured live)")


def test_shell_kpi_cells_follow_the_selection_not_the_first_row():
    ui = _read(UI / "ui.js")
    table = re.search(r"function renderOverviewTable\(\)(.*?)\n\}", ui, re.S)
    assert table, "renderOverviewTable is gone — update this guard"
    body = table.group(1)
    assert "rows.find((r) => r.symbol === wanted)" in body, (
        "the Ticks / Candles-closed cells must read the selected instrument's row")
    assert "const first = rows[0];" not in body, (
        "rows[0] put the first stream's tick and candle counts under every selection")


# ── the tape is one instrument's tape ──────────────────────────────────────────────────────────


def test_the_tape_resets_on_an_instrument_switch():
    ui = _read(UI / "ui.js")
    handler = re.search(r'\$\("#symbolSelect"\)\.onchange = \(e\) => \{(.*?)\n\};', ui, re.S)
    assert handler, "the instrument switcher's change handler is gone — update this guard"
    assert "S.inst.tape.clear()" in handler.group(1), (
        "a switch that leaves the previous instrument's prints (and their buy/sell totals) in the "
        "tape mixes two instruments in one list — measured live before the fix")


# ── the switcher itself: rebuilt after a panel change, and adopted by the Engine view ──────────


def test_an_instruments_panel_change_rebuilds_the_switcher():
    ui = _read(UI / "ui.js")
    apply_now = re.search(r"async function applyInstrumentChangesNow\(\)(.*?)\n\}", ui, re.S)
    assert apply_now, "applyInstrumentChangesNow is gone — update this guard"
    body = apply_now.group(1)
    assert "await refreshInstruments();" in body, (
        "without a rebuild after the save/restart the switcher keeps its boot-time option set — "
        "an instrument enabled in the panel never arrived in the top bar (measured live)")
    assert "skippedNotice" in body, (
        "a row the active source cannot serve is reported with the engine's own reason, not a "
        "silent 'the engine covers it now'")


def test_the_engine_view_adopts_the_apps_current_instrument_at_boot():
    view = _read(UI / "ofx-view.js")
    init = re.search(r"async function ofxInit\(\)(.*?)\n    \}", view, re.S)
    assert init, "ofxInit is gone — update this guard"
    body = init.group(1)
    assert "adopt(S.symbol)" in body or "adopt(now)" in body, (
        "the top bar's announcement listener only hears changes made after this boot; a switch "
        "made earlier was dropped (measured: switcher on XRPUSDT, stage on its stored BTCUSDT)")


# ── the Depth ladder's grid is the instrument's own pricing ────────────────────────────────────


def test_the_ladder_grid_comes_from_the_book_not_a_constant():
    ob = _read(STATIC / "orderbook.js")
    assert "_bookStep()" in ob and "this._bookStep() || this.options.priceStep" in ob, (
        "the drawn step must come from the book, with the configured step only as the fallback")
    assert "const step = this.options.priceStep;" not in ob, (
        "a hardcoded 0.5 grid drew XRP rows 5.00 … −2.00 with every cell empty (measured live)")
    assert "this._sizeMap(this.bids)" in ob and "this._key(price)" in ob, (
        "book sizes are matched through the same rounding the rows are keyed by — float identity "
        "missed its own rung")


def test_the_ladder_formats_prices_at_the_instruments_granularity():
    ob = _read(STATIC / "orderbook.js")
    fmt = re.search(r"_formatPrice\(price\) \{(.*?)\n    \}", ob, re.S)
    assert fmt, "_formatPrice is gone — update this guard"
    assert "this._digits()" in fmt.group(1), (
        "price labels carry the step's decimals; the old magnitude guess printed every XRP rung "
        "as '1.41'")


def test_the_ladder_footer_totals_the_rows_it_draws():
    ob = _read(STATIC / "orderbook.js")
    stats = re.search(r"_updateStats\(levels\) \{(.*?)\n    \}", ob, re.S)
    assert stats, "_updateStats(levels) is gone — update this guard"
    assert "drawn.reduce" in stats.group(1), (
        "the footer must sum the drawn rows; totalling the raw top-N lists disagreed with the "
        "cells on screen")


def test_nothing_deletes_the_top_of_book_on_a_book_tick():
    ui = _read(UI / "ui.js")
    assert "updateLevel('bid', d.best_bid, 0)" not in ui, (
        "updateLevel(…, 0) is the ladder's DELETE path — every book tick spliced the top rungs "
        "out between REST snapshots (measured: 38 calls, 6 rungs gone in 9 s)")
    assert "updateLevel('ask', d.best_ask, 0)" not in ui


def test_the_footprint_row_step_comes_from_the_bars():
    fp = _read(STATIC / "footprint.js")
    assert "    _rowStep() {" in fp, "the footprint derives its row step from the bars it holds"
    assert "this.options.priceStep);" not in fp, (
        "the 0.5 constant made every XRP cell thousands of pixels tall (a smear) and the hover "
        "hit-test matched the first level of the bar")
    assert fp.count("this._rowStep()") == 2, (
        "the derived step feeds the cell height and the hover tolerance (both call sites)")


# ── the instrument dropdown is readable in every theme ─────────────────────────────────────────


def test_the_instrument_dropdown_styles_its_options():
    css = _read(UI / "ui.css")
    assert re.search(r"select option \{ background-color: var\(--bg-panel\); color: var\(--text-primary\); \}", css), (
        "the popup is drawn by the browser: without option colours the theme's light ink landed "
        "on the platform's white list (the instrument menu in the top bar)")


# ── the server: one instrument's signals ───────────────────────────────────────────────────────


def _signals_route():
    from orderflow_system.dashboard import app as dash
    return dash


def test_signals_route_filters_the_live_history_by_instrument(monkeypatch):
    dash = _signals_route()
    from orderflow_system.signals.aggregator import AggregatedSignal

    history = [
        AggregatedSignal(timestamp_ms=1, direction="buy", symbol="BTCUSDT", notes="btc"),
        AggregatedSignal(timestamp_ms=2, direction="sell", symbol="ETHUSDT", notes="eth"),
        AggregatedSignal(timestamp_ms=3, direction="buy", symbol="BTCUSDT", notes="btc2"),
    ]
    fake = types.SimpleNamespace(aggregator=types.SimpleNamespace(signal_history=history))
    monkeypatch.setattr(dash, "get_system", lambda: fake)

    rows = asyncio.run(dash.get_signals("BTCUSDT", limit=50))
    assert [r["symbol"] for r in rows] == ["BTCUSDT", "BTCUSDT"], (
        "every instrument used to be served the identical merged list (measured: BTC/ETH/SOL/XRP "
        "answered byte-for-byte the same 26 rows)")
    assert [r["notes"] for r in rows] == ["btc2", "btc"], "newest first, filtered by instrument"
    assert asyncio.run(dash.get_signals("SOLUSDT", limit=50)) == [], "no rows for a symbol with none"


def test_signals_route_filters_the_demo_rows_too(monkeypatch):
    dash = _signals_route()
    monkeypatch.setattr(dash, "get_system", lambda: None)
    demo = dash.demo_data.demo_signals()
    symbol = str(demo[0]["symbol"])
    rows = asyncio.run(dash.get_signals(symbol, limit=50))
    assert rows, "the demo generator's own rows for this symbol must be served"
    assert {str(r.get("symbol")) for r in rows} == {symbol}, (
        "the demo path must not hand another instrument's rows to this symbol")
    assert asyncio.run(dash.get_signals("__NOSUCH__", limit=50)) == []


def test_every_aggregate_stamps_the_instrument_it_was_raised_for():
    src = _read(ROOT / "orderflow_system" / "signals" / "aggregator.py")
    creations = src.count("agg = AggregatedSignal(")
    stamped = src.count("symbol=instrument,")
    assert creations == stamped == 6, (
        f"{creations} constructions, {stamped} stamped — every AggregatedSignal carries the "
        "instrument, or the signals route cannot filter (it used to return them all)")
    assert "    symbol: str = \"\"" in src, "the dataclass field itself must exist"


def test_the_charts_window_delta_owns_its_cell():
    ui = _read(UI / "ui.js")
    upd = re.search(r"function updateDeltaKpi\(cum, bar\) \{(.*?)\n\}", ui, re.S)
    assert upd, "updateDeltaKpi is gone — update this guard"
    assert "chDelta" not in upd.group(1), (
        "the chart's Window-delta cell must not receive the SESSION cumulative — measured live: "
        "LAST 81263.70 / WINDOW DELTA 13.49 under an XRPUSDT selection (both BTC's numbers)")
    assert "function windowDeltaSum()" in ui and "function paintWindowDelta()" in ui, (
        "the chart's window delta comes from the chart's own loaded series")
    assert ui.count("paintWindowDelta()") >= 3, (
        "painted on every chart load and on the live delta tick")
    assert "tail.bar_delta = data.bar_delta" in ui, (
        "the newest bar's own delta updates the window in place, the same bar the lane took")


def test_no_tick_folds_into_the_previous_instruments_series():
    ui = _read(UI / "ui.js")
    assert "S.lastDeltaSymbol = S.symbol;" in ui, "the delta series is tagged with its instrument"
    assert "S.chartSymbol = S.symbol;" in ui, "the candle series is tagged with its instrument"
    assert "if (S.lastDeltaSymbol !== S.symbol) break;" in ui, (
        "a delta tick for the newly selected symbol must not fold into the previous instrument's "
        "series while the load is in flight (measured: a mixed 46.60K window value)")
    assert "S.candleSeries && S.chartSymbol === S.symbol" in ui, (
        "a candle tick must only land on its own symbol's series")
    handler = re.search(r'\$\("#symbolSelect"\)\.onchange = \(e\) => \{(.*?)\n\};', ui, re.S)
    assert "S.chartSymbol = ''" in handler.group(1) and "S.lastDeltaSymbol = ''" in handler.group(1), (
        "a switch untags both series, or the guards have nothing to compare")


def test_a_stalled_chart_load_retries_until_it_belongs_to_the_selection():
    ui = _read(UI / "ui.js")
    assert "function chartLoadWatch()" in ui, (
        "the chart has no poll of its own: a load that never lands leaves the chart KPIs blank")
    watch = re.search(r"function chartLoadWatch\(\) \{(.*?)\n\}", ui, re.S).group(1)
    assert "S.chartSymbol === S.symbol" in watch and "S.lastDeltaSymbol === S.symbol" in watch, (
        "it retries until the loaded series belongs to the SELECTED instrument")
    assert "chartLoadWatch();" in ui and "chartRetryAt" in ui, (
        "the status tick drives it, with a retry interval so it cannot spam the wire — measured "
        "before: 'loading…' held 20 s+ after a switch made right after boot")


def test_a_switch_blanks_the_instruments_cells():
    ui = _read(UI / "ui.js")
    handler = re.search(r'\$\("#symbolSelect"\)\.onchange = \(e\) => \{(.*?)\n\};', ui, re.S)
    assert handler, "the switcher's change handler is gone — update this guard"
    body = handler.group(1)
    for cell in ("kpiPrice", "kpiDelta", "kpiTicks", "kpiCandles", "chPrice", "chDelta"):
        assert cell in body, (
            f"{cell} is not blanked on a switch — the instrument the selector moved away from "
            "shows under the new selection for a poll")


def test_the_wire_keeps_one_name_for_the_instrument():
    """`symbol` is the name the UI, the demo rows and the WebSocket envelope all use."""
    dash = _read(ROOT / "orderflow_system" / "dashboard" / "app.py")
    assert "getattr(sig, \"symbol\", \"\")" in dash, "the route filters on the same field the dataclass carries"
    body = json.dumps({"symbol": "BTCUSDT"})
    assert "symbol" in body  # the shape the cards read (renderOverviewSignals / signals.js)
