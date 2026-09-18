# §82 — Instrument switching, full pass (Tier A + B)

**Directive (owner, 2026-09-17):** a suite user could not change the Engine panel to `NQ1!`
and got a blank stage with no explanation. Root cause measured (§82 recon, below): the
Engine view's symbol box is a *display filter*, not a subscription — and no wired venue has
an `NQ1!` instrument at all. Build the full fix: the panel becomes an honest instrument
control, and the backend learns to add/enable/stream any instrument the active venue can
actually carry.

## Recon (measured 2026-09-17, scratch APPDATA, headless 8099)

- `POST /api/control/ofx {"symbol":"NQ1!"}` → `ok:true`, stored verbatim (no validation).
- Engine stopped: `/api/footprint/NQ1!` → `[]` (demo guard), `/api/footprint/NAS100USDT` → demo bars (~21,450).
- Engine running (BTCUSDT): `/api/footprint/NQ1!` → **404 `Unknown symbol: NQ1!`** — swallowed by
  `ofx-view.js`'s `.catch(() => [])`, leaving a blank stage + a misleading "no depth history" note.
- Subscriptions are fixed at engine start (`cfg["instruments"]`, enabled + source-capable);
  `select_instruments` refuses anything outside the shipped matrix unless a Bybit stamp exists.
- `mt5_feed.list_available_symbols()` exists with **zero callers** — the seam for broker discovery.
- The app's Nasdaq instrument is `NAS100USDT` (settings.py:561, "proxy for NASDAQ futures"; MT5 default `USTECm`).

## Fixed decisions

- Nothing committed; work stays on disk (repo rule).
- The Engine panel's `#ofxSymbol` stays free-text (a typed symbol must always be *answered*, never silently accepted).
- Alias resolution is a small honest table; it may only point at instruments the app ships.
- Adding an instrument requires **venue evidence** (a Bybit catalog hit, an MT5 `symbol_info` hit,
  or an Alpaca asset) — the existing "unknown instrument" refusal stays for rows with no stamp.
- The installer rebuild is NOT part of this phase (IS IDE is mid-polish; owner says when).

## Tasks

- T1 `desktop/instrument_lookup.py` (pure): normalise/alias/resolve → state + reason + suggestions + closed action set. Tests `test_instrument_lookup.py`.
- T2 `engine.select_instruments`: venue-stamp relaxation (mt5 / alpaca stamps build a profile from the venue tick) without touching the pinned bybit behaviour.
- T3 `engine.mt5_symbols`: broker symbol discovery (threaded, cached, honest when MT5 is absent).
- T4 `api.py`: `GET /instruments/resolve`, `GET /mt5/symbols`, source-aware `POST /instruments/add` (mt5/alpaca/bybit stamps, `enable`), `POST /ofx` returns a `stream` block.
- T5 `ui/instrument.js` (pure) + `instrument.selftest.js` + `test_instrument_ui.py` gate.
- T6 `index.html` / `atlas.css` / `ofx-view.js`: state chip + look-up panel + actions (use / enable / add+restart / open Instruments); the 404 is surfaced, never swallowed.
- T7 `scripts/audit_ui_refs.py` JS_FILES + `help-data.js` Engine topic.
- T8 Verification: pytest, audit, ruff, goldens, node selftests, live smoke (curl + browser).

## Verification map

| Acceptance criterion | Proving task / command |
|---|---|
| Typed symbol is answered with a state + reason, not silence | T1 tests + T4 resolve endpoint live curl |
| The panel can enable + stream an addable venue instrument | T3/T4 + T6, live: add `NAS100USDT` mapping → restart → footprint bars |
| Unknown symbols still refused without venue evidence | T2 keeps `test_instrument_matrix` pins green |
| No silent 404 in the Engine view | T6 + live browser check (note text shows the reason) |
| Full gates | T8: pytest / AUDIT CLEAN / ruff / goldens / 24 selftests / payload parity |

## Execution log

| Task | Status | Evidence |
|---|---|---|
| T1 pure look-up module + tests | done | `desktop/instrument_lookup.py`; `test_instrument_lookup.py` 27 pins (states, alias honesty, closed actions, remap cases) |
| T2 venue-stamp relaxation | done | `engine.venue_stamp_for()`; `test_instrument_matrix.py` +3 (mt5/alpaca stamps stream on their own source; no-stamp rows still refused) |
| T3 broker discovery | done | `engine.mt5_symbol_names` / `mt5_symbols` / `mt5_validate_symbols`, TTL cache; live: 12,388 broker symbols from the real terminal |
| T4 API routes | done | `GET /instruments/resolve`, `GET /mt5/symbols`, source-aware `POST /instruments/add`, `stream` block on `POST /ofx`; `test_instrument_api.py` 14 pins |
| T5 panel module + gate | done | `ui/instrument.js` + `instrument.selftest.js` (13 checks); `test_instrument_ui.py` 6 pins incl. JS↔Python vocabulary equality |
| T6 panel wiring | done | chip + `find` + look-up panel in `index.html`/`atlas.css`/`ofx-view.js`; 404 surfaced; view follows the row after an add |
| T7 audit + help | done | `scripts/audit_ui_refs.py` JS_FILES (AUDIT CLEAN, 80 modules); Engine help topic documents the look-up |
| T8 gates | done | pytest **942 passed / 2 skipped**; AUDIT CLEAN; ruff clean; goldens OK; **24/24 selftests**; OpenAPI 140 ops |

**Live receipts (scratch APPDATA, real MT5 terminal, real browser).**
- Recon before: `POST /ofx NQ1!` stored verbatim; `footprint/NQ1!` → `[]` (demo) / `404 Unknown symbol` (engine running); `NAS100USDT` → demo bars.
- After: `resolve("NQ1!")` → `disabled` + "enable it and restart the engine" → add `NAS100USDT` on `USTEC` → engine start → **38,045 ticks / 181 candles**, `resolve("NQ1!")` → **live**.
- Panel-driven: `USTECH100M` (broker-only) → "＋ available" → Add & restart → 32,896 ticks / 121 candles; `US500M` → remap offered ("its broker symbol (US500m) is not one of your broker's names — it lists US500M") → SP500 enabled + remapped; `TDAX` → add → panel reads "TDAX is streaming from mt5."
- Log after all of it: 300 lines, 0 client errors.

**Found live and fixed in-pass:** MT5 `symbol_info` case sensitivity (MetaQuotes `US500M`/`USTEC` vs shipped `US500m`/`USTECm`); the panel not repainting after an action; an empty panel sentence for a healthy exact-match symbol; the view keeping a broker-only name after a successful add.

**Owed:** `dist/`, zip, SBOM and the installer are not rebuilt (payload changed) — the next packaging pass rebuilds and re-runs payload parity + the installer journey. Nothing committed.

## Addendum — the owner's exact user report

The original report was *"i was trying to view the nq chart but it says crpto only"* — the exchange feed (Bybit) carries crypto perpetuals only, and there is no keyless NQ anywhere. The look-up now answers that case with the engine's own sentence **plus the way out** (gate-first: the source refusal outranks "enable it and restart", because enabling on Bybit would only have the engine skip the row with the same words). Measured on the bybit source with the running app: `resolve("NQ1!")` → `unsupported · NAS100USDT (alias)` — reason *"Bybit perps list crypto only — switch to MT5 (Windows) for this instrument"*, hint *"switch the data source to MetaTrader 5 for indices, metals and FX (☰ ▸ sources, or the setup assistant) and map the broker symbol"*; in the panel: chip **⚠ not on this source**, that sentence, one action (**Open Instruments**), and the stage note finally carries the refusal instead of "no depth history yet". Pins: `test_the_reported_case_nq_on_the_exchange_feed_answers_crypto_only_and_the_way_out`, `test_an_enabled_row_on_a_source_that_cannot_carry_it_is_not_called_ready`, and the JS panel-sentence check. pytest **944 / 2** after the addendum.

**Still true, and no code change can alter it:** a keyless crypto venue cannot carry NQ. The MT5 lane (or a paid futures venue — tier C) is required; the pass makes the path explicit and one-click, not the data appear.
