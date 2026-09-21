# Control-surface audit — the dropdowns, value inputs and menu rows vs. what the program can do

**Method (so this document can be re-run, not trusted):** the dropdown inventory is parsed from
`ui/index.html` (`<select>` blocks, option value → label); the value-input inventory from every
`<input>` carrying an id (type/min/max/step); the bindings by grepping each id through `ui/*.js`;
"correct" is judged against the program's own authorities, never memory — `config_store` defaults +
clamps (the store's `_sanitise`), `param_registry.py` (the display-variable registry served by
`/api/control/params`), the engine modules that read the values, and live probes against a
scratch-`APPDATA` build on port 8099. **No finding below is a claim about the owner's live config:
the one mutation probe ran on the scratch sandbox.**
**Date of extraction: 2026-09-19. State: nothing committed; report-only pass.**

---

## 0. What was inventoried

- **41 `<select>` controls** in `ui/index.html` (plus 1 runtime-built: the terminal's "+ widget"
  adder in `shell.js`).
- **93 id'd inputs**: 38 `type=number`, 13 text, 31 checkbox, 2 range, 2 time, 2 password, 2 file,
  plus the 6 buttons excluded as actions.
- **Dynamic editors** (sampled, not exhausted): the registry-driven Chart menus + Settings browser
  (`/api/control/params`), alert-rule parameter fields (`atlas.js`), heatmap-pro level prompts,
  study parameter editors (`studies.js`/`study-api.js`), atlas-v2 panel groups, the menu bar's
  inline number editor (`mbEditNum`), replay/paper ticket fields.

## 1. The authority chain, and what "tight" means here

```
config_store defaults + _sanitise clamps   ← the store (last word, silent coercion lives here)
param_registry (choices/bounds/units)      ← presentation authority for display variables
/api/control/params (validated writes)     ← the registry-driven edit path
hand-written controls (41 selects / 38 numbers)  ← drift surface — they duplicate bounds/choices
engine readers (footprint, frames, heat…)  ← what actually consumes a value
```

A control is **tight** when its option values and bounds are all accepted end-to-end without silent
coercion, its changes persist (config, saved on change, restored at boot), and its help text names
things that exist. The findings below are where one of those breaks.

## 2. Findings — dropdown and input correctness

**F-1 — `frameSelect` cannot choose the sixth frame family (the engine builds it; the API serves
it).** `atlas/frames.py` `FrameSet.builders` defines **six** families — range, renko, reversal,
tick, volume, **delta** (`frame = "delta"`, line 246) — and the help map in `search.js` even
documents delta bars ("closes when the delta inside the bar passes the trend threshold or reverses
from its extreme"), but `index.html:637-640` offers five options and `atlas/api.py:12`'s docstring
lists five. **Live receipt:** `GET /api/atlas/frames/BTCUSDT/delta?count=5` answered real bars
(delta_min/max, delta_sh/sl populated). Verdict: one `<option value="delta">Delta</option>` + the
two doc lines. *Small — hours.*

**F-2 — the Settings Data-source dropdown is stale against the venue matrix.** The allow-list
(`config_store.py:1428`) accepts **nine** values — mt5, bybit, binance, hyperliquid, okx, both,
alpaca, ninjatrader, all — and the live `/api/control/sources` lists seven venues (bybit, binance,
mt5, alpaca, okx, hyperliquid, ninjatrader) which the **Data menu** renders dynamically and the
**setup wizard** offers as radios. The Settings select (`index.html:1014-1019`) offers five: bybit,
mt5, both, alpaca, all. Verdict: binance / okx / hyperliquid / ninjatrader are unreachable from
Settings. *Small — populate from `/api/control/sources` (the menu's own source), keep both/all.*

**F-3 — the registry offers a value the store silently drops: `imbalance_mode = "both"`.**
`param_registry.py:326` lists choices `("same_price", "diagonal", "both")` and the meaning text says
"or both" — but the store accepts only two (`config_store.py:1540-1541` coerces anything else to
`same_price`) and `analytics/footprint.py` branches on same_price/diagonal only. **Live receipt:**
`POST /api/control/params {path: atlas.footprint.imbalance_mode, value: "both"}` answered
`ok:true` **and `"value":"same_price"`** — the Chart menu's "both" choice stores nothing new; the
config read back `same_price`. Verdict: the registry's choices are the lie; drop `"both"` (or build
it end-to-end — the engine has no branch for it today). *Small — one tuple + one meaning string.*

**F-4 — bounds exist in up to three places; they disagree.** Samples from the registry vs the
hand-written inputs vs the store clamp: `ofx.lambda_ms` — registry 50–5000, input `min=100`,
store clamps 100–5000 (`config_store.py:1264`); `ofx.min_block` — registry 0–1000 step 0.01, input
`min=0 step=5 max=-`, store clamps 0–1,000,000 round 2 (`:1409`);
`atlas.footprint.imbalance_threshold` — registry 0–50, input `min=1 max=50`. Each disagreement is a
value the UI lets you type and the store then quietly changes. Verdict: make the registry the one
source — render registered paths from `/api/control/params`, or pin the markup's attrs against
registry bounds in `test_param_registry.py`. *Medium — the pin is the cheap half.*

**F-5 — the Chart's Bars menu lists "candles" twice, indistinguishably.** `index.html:216-219`:
`<option value="default">candles</option> … <option value="candles">candles</option>` — both render
the word "candles"; on the Engine the pair is meaningful (`default` = footprint default, `candles` =
classic candle — and degrade mode *uses* `candles`), on the Chart both paint plain candles.
Verdict: relabel one ("default (candles)" / "classic candles") or drop the redundant value on the
chart surface. *Small.*

**F-6 — hover help that never shows (option-value drift).** `search.js` `SELECT_HELP` +
`decorateSelects()` match an option by value, then by trimmed text. Against today's markup:
`tfSelect`'s options read `1m/5m/15m/1H/4H/1D` (values are seconds) so the `'1h'/'4h'/'1d'` keys
never match; `rangeSelect`'s options read `1H/4H/1D/1W/1M` so **all five** keys miss; `logLevel`
has no DEBUG option though a DEBUG help entry exists (the Logs filter cannot select DEBUG
specifically, only "all levels"). Verdict: normalise the keys or the option text; decide whether
DEBUG joins the filter. *Small.*

**F-7 — the Calendar's load filters don't persist or restore.** `calendar.js` saves
`{alerts, lead_minutes, currencies}` (`saveAlerts()`), but `calHours` and `calImpact` ride the same
onchange yet are never saved or restored — the view reopens at 48 h / "High only" every launch,
while `calCurrencies` (persisted) keeps its value. §83's rule ("user-visible state belongs in the
config and is saved on change") says these two should join the block. *Small — two fields + restore.*

**F-8 — `hmAgeTint` lives in localStorage only.** `atlas.js:1105-1114` self-documents it ("remembered
here and nowhere else") — deliberate, but it is the one display pref that ignores the config-store
rule its siblings follow (§83's pattern; `ui.logs`/`ui.chart` show the shape). Verdict: leave or
move; if left, keep the comment as the reason. *Tiny.*

**Not-a-bug, verified positively:** `ofImbMode`/`ofImbThresh` clamp + save correctly
(`ui.js:1010-1019`, 1–50 enforced twice); the audio card converts 0–100 ↔ 0–1 with a clamp and
adopts the accepted value back (`audio.js:215-245`); the column rail saves its trio with a clamp
(`colrail.js:136-165`); both heat-dial surfaces write through the shared params gate (§118);
the storage card's SMTP fields **do** have their own save (`btnStSmtpSave` → `notify.email`); the
replay transport and paper-ticket fields read/save as expected.

## 3. Menu rows — the standing reconciliation, re-run

`docs/MENU_RECONCILIATION.md` (2026-09-18) listed 26 `planned(...)` stubs; today's `menubar.js`
carries **15**. Of those:

- **Stale wording, function ships now → promote to real deep-links:** *Replay…* (Replay view
  exists), *Notifications…* (Settings holds the channels), *Performance…*, *Studies library*
  (Studies view), *History & retention* (the Logs/Settings storage block is live — and its own stub
  text is stale: "DB is ~547 MB" vs ~851 MB measured today), *Export data…* (the endpoint exists —
  `/export/save`).
- **Honest, still unbuilt:** the profile-store family (*Import profile…*, plus New/Save family from
  the earlier pass), *Record session…*, *Recent*, *Exit*, *Reset rail order*.
- **Environment-conditional (fine as-is):** *Layouts* (terminal shell), *Drawing layer not loaded*,
  *no saved workspaces yet*, *Edit list*.
- **Still dark from §93's list:** the three server-made CSV exports (tape / heatmap / alerts) —
  Tools has no Export submenu; and `storage/prune` still has no button.

## 4. Where presets + custom entry ("common values, else your own") would help

The asked-for pattern is a small combobox: the common values as options, a **Custom…** row that
reveals the existing number field. The app already contains the pattern's DNA — the replay speed is
a slider + readout (`rpSpeed`/`rpSpeedLabel`), heat schemes write their dials, the Settings browser
stages edits. Ranked candidates (all ranges already clamped, so a preset is pure convenience):

| Control | Path | Suggested presets |
|---|---|---|
| `ofxVaPct` | ofx.va_pct | 68% · 70% · 80% · 90% · custom |
| `ofxLambda` | ofx.lambda_ms | 100 · 250 · 500 · 1000 · 2000 ms · custom |
| `ofxStack` | ofx.stack | 2 · 3 · 5 · 8 · custom |
| `ofxR` | ofx.R | 2 · 4 · 8 · custom |
| `ofxMinBlock` | ofx.min_block | 0 · 10 · 50 · 100 · custom |
| `setCooldown` | risk.signal_cooldown_seconds | 0 · 15 · 30 · 60 · 300 · custom |
| `setScore` | risk.min_composite_score | 20 · 40 · 60 · 80 · custom |
| `calLead` | calendar.lead_minutes | 5 · 15 · 30 · 60 · 240 · custom |
| `calHours` | calendar.hours (once persisted) | 12 · 24 · 48 · 72 · 168 h · custom |
| `stRetention` | data.retention_days | 7 · 14 · 30 · 90 · 365 · 0 (keep all) · custom |
| `stPruneInterval` | data.prune_interval_hours | 1 · 6 · 12 · 24 · custom |
| `stBackupInterval` | storage.backup_interval_hours | 6 · 12 · 24 · 72 · custom |
| `stBackupKeep` | storage.backup_keep | 3 · 5 · 10 · 20 · custom |
| `updInterval` | updates.interval_hours | 1 · 6 · 12 · 24 · custom |
| `stMaxDb` | storage.max_db_mb | 0 (off) · 500 · 1000 · 2000 · custom |
| `stSmtpPort` | notify.email.port | 25 · 465 · 587 · 2525 · custom |
| `hmColThreshold` | atlas.columns.threshold | 0 · 500 · 1000 · 5000 · custom |
| `rpFrom` / `rpTo` | replay window | 15 m · 1 h · 4 h · 24 h · 72 h · custom |
| `stSessionHour` | data.session_start_hour | a 24-entry hour picker (or time input) |

Text→picker upgrades: `rpSymbol` (a select of enabled instruments), `calCurrencies` (a checklist),
`updDir` / `stBackupTarget` (folder pickers), leaving genuinely free text (names, notes, paths by
hand) alone. Standardise the labels' units while there (the registry carries `unit` for numbers —
use it).

## 5. Recommended order

1. F-3 (registry 'both') and F-1 (frameSelect delta) — two one-liners, real capability unlocked.
2. F-2 (Settings source dropdown from `/sources`).
3. F-6 (hover-help keys + DEBUG decision).
4. F-7 (calendar persistence).
5. F-4's pin (`test_param_registry` vs markup bounds) — stops the drift class for good.
6. Stale stubs → deep links (§3's first bullet), ideally in the same pass as the CSV-export submenu.
7. The preset+custom helper (`presetField`) applied down §4's table.

## 6. Re-run recipe

- Selects with options: Python `re.findall(r'<select\b[^>]*id="([^"]+)"[^>]*>(.*?)</select>')` over
  `ui/index.html`, then `<option>` value/text pairs (over `re.S|re.I`).
- Number bounds: `re.findall(r'<input\b[^>]*type="number"[^>]*>')` → id/min/max/step/value.
- Bindings: for each id, grep the id through `ui/*.js` (exact string; beware prefix patterns like
  `'pfDay' + i` and ids reused in selftests — trim hits from `*.selftest.js` when judging "who
  reads it").
- Authorities: `config_store.py` (`_sanitise` blocks + `_clamp` calls), `param_registry.py`
  (`choices`/`minimum`/`maximum`), engine readers (`analytics/footprint.py`, `atlas/frames.py`).
- Live probes (scratch `APPDATA` build): `GET /api/control/params`, `POST /api/control/params
  {path,value}`, `GET /api/control/sources`, `GET /api/atlas/frames/{symbol}/{frame}`,
  `GET /api/control/config`.
- Not exhaustively covered here, left for a follow-up: the study/alert-rule dynamic editors'
  field-level bounds, and the atlas-v2 group editors' per-key steps.

---

## Status after §124 (2026-09-19, executed same day)

- **F1 (Trackers' dark routes) — CLOSED by wiring.** All five routes render (cross-venue book, correlation, clusters, feed history, intent) on the Trackers view's own beat. `test_trackers_wiring.py` guards both ends.
- **F2 (three CSV exports, no submenu) — CLOSED.** Tools ▸ Export fetches tape/heatmap/alerts and writes through `/api/control/export/save`.
- **F3 (no prune button) — was STALE; already shipped.** `storage.js` wires `/storage/prune`, vacuum and sweep with result lines. This audit line predated the wave that added them.
- **F-1…F-7 — CLOSED.** delta option + copy + docstring; Bars labels distinct; registry 'both' dropped; bounds unified (registry = markup = store) and pinned; DEBUG in the Logs filter; hover-help case-insensitive + full coverage; calendar hours/impact persisted.
- **§3 list — closed:** the five dark routes (F1); the CSV trio (F2). `/api/control/sources` gained a second consumer (Settings builds from it).
- **§4 (preset comboboxes) — SHIPPED** as `presets.js` over 19 controls (`data-presets`, Custom… hands the field back). Remaining stretch: text→picker upgrades (rpSymbol select, calCurrencies checklist, folder pickers) — open.
- **Stubs — decided.** Reset rail order removed; Recent real; Edit list real (`/params` lists); Exit disabled-with-reason; Record session stays honest.
- Rerun this audit any time: `python scripts/audit_ui_refs.py` is the mechanical half; this document is the judgement half.
