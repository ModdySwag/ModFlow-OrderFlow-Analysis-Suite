# Session handoff — ModFlow OrderFlow Analysis Suite

**Date:** 2026-09-15 · **Tree:** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · **HEAD:** `b2ff4ee`
**Committed:** nothing. The working tree is dirty on purpose; every change from this session is on disk.

**Run it:** `orderflow_system.desktop` (the owner's shortcut: `.venv\Scripts\pythonw.exe -m
orderflow_system.desktop`, binds 127.0.0.1:8080). Frozen build: `dist/OrderFlowAnalysisPro/OrderFlowAnalysisPro.exe`
(`scripts/build_exe.py`). Scratch scripts belong in `$LOCALAPPDATA/Temp`, not the repo.

---

## 1. What this session delivered

### Setup wizard — a guidance system, then a professional path
- Every decision step now carries **what it unlocks · where to go deeper · a real deep link** into
  the panel that answers the next question (`guide.js`; `wizFooter`, `wizGo`).
- **Guards**: a choice that would leave the app empty raises an inline banner with the one-click fix
  (the Instruments step's "no instruments enabled" is the model).
- **Depth step**: Express (12 steps) ↔ Professional (22). `wizList()` is the single source of truth for
  navigation; every `collect()` site is list-correct and bounds-safe; the express path ends with a
  door into the professional leg; resume works.
- Professional leg (10 steps): feed budget · instruments · engine internals (live fields) · analytics
  thresholds · studies runtime · layout & workspaces · hotkeys · bridges (never asks for a secret) ·
  performance & hygiene · **prove it works** (8-point checklist).

### Heatmap and engine
- `heatmap-pro.js`: wheel/shift-wheel zoom driving the map's own window control, drag-select with
  isolate + stats, cursor readout (resting, Δ vs previous bucket, row total, bucket total, executed,
  events), markers with notes, region/marker CSV export, and an instant repaint on `ofap:relayout`
  (the one-second blank after a resize is gone).
- Exports land as real files via `POST /api/control/export/save` → `%APPDATA%\OrderFlowAnalysisPro\exports\`
  (the desktop shell has no download shelf; export has to mean a file).
- Engine: **thermal ramp** (slate → orange → white-hot gold) selectable and remembered; **stacked-zone
  bands** drawn with a leading rail and a label; **cursor link** (`cursor-link.js`) with a DOM trace
  line at the cursor's price and a ladder highlight; **pinch** parity (ctrl+wheel = price-axis zoom,
  page zoom cancelled).

### Alerts
- Rules can be **bound to a price**: `params.at_price` / `at_tol` added to the alert evaluator
  (any rule kind), plus `min_age_s`.
- **Wall-age detection**: `DepthHeatmap` tracks a streak (`_wall_first`) and emits `wall_age` with
  "held N min"; `wall_durations()` lists walls by how long they have held.
- Rule management: the alerts list shows each rule's scope in words and can delete one.

### Interaction vs live feed — the system-wide answer
- `intent.js` (`OFAPINTENT`): a **lease** on a surface from real input (pointer/wheel/key/focus),
  time-boxed and auto-renewed; updates that would move the view, scroll a strip or replace a
  selection are **DEFERRED and applied on release — never dropped**; writes are coalesced per key;
  the freeze is two-level (view held ≠ feed stopped) and the arbiter never touches ingest.
- `strips.js`: scrolling strips **hold the reader's place**. The guard discovers any element in the
  visible view that actually scrolls (not hand-picked selectors), counts arrivals for appending
  lists and **counts top-row changes for capping lists** (the tape), shows `↓ N prints · jump to
  newest`, and returns on click. It can never move a scroll it cannot anchor.
- Surfaces are tagged in markup (`data-surface="…"` on 12+ view sections) so panels don't need to
  know the arbiter exists. Every poller in the program now consults it (ofx, heatmap, slow panels,
  v2, alpaca, scanner, market-pressure, context).
- One **status cluster** top-right: the pause chip and the hold chip sit together and report
  "… · feed live · N strips holding your place".

### Scaling and packaging
- `scale.js` (`OFAPScale`): the one authority on window change — resize/maximise/restore/orientation/
  fullscreen/dpr + ResizeObserver, debounced, zero-size guard for minimised windows, `ui-compact`
  under 760 px height, `ofap:relayout` for consumers.
- Fixed two measured faults: the topbar could not wrap (315 px overflow at 1024 wide) and the status
  bar sat *below* a 100vh shell (invisible at every size). Now: 0 px overflow, status bar visible, at
  2560×1440 / 1920×1080 / 1366×768 / 1280×800 / 1024×640.

### The tape was empty by its own filter (found and fixed)
`dashboard/static/tape.js` (loaded by the shell as `/static/tape.js`): the Min Size input had
`min="1" value="1"` and the handler did `parseInt(value) || 1` — **0 is falsy, so the floor could never
go below 1**, and 40 sampled live BTCUSDT prints were 0.001–0.15: the tape showed nothing while its
footer tallied them. Now `min="0" value="0"`, 0 means every print, and the default shows the real
tape. Verified: rows 2 → 51, body 19 px → 1 239 px in a 513 px box, guarded, chip counted, click
returned to newest.

### The agent brief
`docs/AI_AGENT_BUILD_PROMPT.md` (~370 lines) — written for another agent to continue this build:
inventory of what exists, the eight non-negotiables (error-free means *proven*; fail-loud edits;
the contracts that must not break; secrets; free data only; original work; Hermes stays out; the app
must always run), the Windows/Material design language read from the owner's reference image, the
order-flow interaction canon, workstreams A–I with gates, and the inherited gaps. Workstream I is
already built (see §1) — the brief predates the last two sessions' work in places; reconcile before
following it literally.

---

## 2. Verified vs unverified — do not blur this line

**Verified live**
- Wizard: depth switch 12 ↔ 22, the door into the professional leg, deep links, resume.
- Heatmap pro: zoom (240 → 120 buckets), selection (81 × 102 cells, resting 8 544.51, heaviest
  77 630 @ 16.85), cursor readout with real numbers, region + marker CSV on disk, "saved to …" line.
- Alerts: a level-scoped rule created, persisted (`at_price`/`at_tol` read back) and deleted.
- Arbiter: lease from a real gesture, deferral (queued, not dropped), write coalescing, two-level
  freeze with `feed.live` true, release flushing everything, chip text.
- Strips: the Logs strip held scrollTop 30 across activity, chip "↓ 1 log line · jump to newest",
  click returned to newest and cleared. Tape: 51 rows, guarded, counted chip, click returned.
- Scaling: five window sizes, no overflow, status bar visible, canvases not stale; engine view kept
  its backing store matched to the CSS box at 1600×900 and 1100×660; pinch changed `scaleY` with the
  page zoom cancelled.
- Gates: **311 passed · 2 skipped**, `intent.selftest.js` 7 ok / 0 failed, `ofx.selftest.js` 80 ok /
  0 failed, `audit_ui_refs.py` CLEAN, `node --check` on every touched JS, no `client error:` lines in
  the log for any of these runs.

**Unverified — say so before claiming otherwise**
- **Stacked-zone bands on live data.** The maths is proven (a forced same-side run yields one zone
  with the right shape) but no band has been *seen*: the live samples had no stacked runs, and the
  engine's view was zoomed to the live price while the bars' levels sat ~80 points away, so nothing
  of the footprint was on screen at all. Test it with the footprint visible.
- **The thermal ramp's pixel effect.** The switch and persistence are verified; the visual change was
  not observed because the heat layer had no depth history and the footprint was off-view.
- **The trace line's successor-path** (ladder highlight) — the note said "outside the drawn ladder
  levels" every time because the ladder was not in the same view. Verify with Depth and the engine
  side by side.
- **Tape scroll position across a rebuild.** The tape rebuilds its row table, so the offset can reset
  to the top on a rebuild; it never yanks the reader to the newest line and the chip appears. The
  Logs strip (append-style) held exactly. Restoring by row index is the fix if wanted.
- **4K at Windows 150 % scaling** — untested; fractional DPI costs a full re-raster.
- The **hidden-sweep count readout** next to the min-block filter (deferred; the engine already
  tallies it, the telemetry block's shape needs a real look).
- The **DTC socket flake** (`test_platforms.py::test_probe_handshake_against_a_spec_conformant_server`)
  — failed twice, passed in isolation both times. Worth a look before it hides a real failure.

---

## 3. Pitfalls that cost time today (read before debugging)

1. **A live page keeps the JavaScript it loaded.** Patching a file does nothing for an open window;
   probes then measure the OLD code and produce confident nonsense. Two fix attempts and three
   verification passes were wasted this way. Restart the app (or open a fresh page with cache
   disabled) after every edit, and say which build a result came from.
2. **Read `%APPDATA%\OrderFlowAnalysisPro\orderflow.log` first.** Client exceptions are POSTed to
   `/api/control/client-error` with `file:line:col` and a stack. That log named two of this session's
   real bugs within minutes; guessing from a screenshot cost far more.
3. **Fail-loud anchor edits.** Every scripted edit asserts its anchor matches exactly once and aborts
   without writing otherwise. Two edits landed in the wrong scope today (helpers inserted mid-class
   split a dataclass; a heading was swallowed by a patch) and the asserts are what caught them.
4. **`parseInt(x) || N` is a falsy trap** whenever 0 is meaningful. The tape's floor of 1 came from it.
5. **Long heredocs mangle.** Write scratch scripts with `write_file` to `$LOCALAPPDATA/Temp` and run
   them, rather than piping multi-line Python through bash.
6. **Browser harness quirks:** each `js()` call is capped at ~5 s (put waits in Python, not JS);
   a locked `bu-*.port` file needs a new session name; a backgrounded tab throttles rAF but DOM
   updates continue.
7. **Never commit.** The owner's standing rule; report "nothing committed" with the HEAD hash.

---

## 4. Where to go next, in priority order

1. **See the three unverified visuals** (§2) with a long-running instance: footprint in view, depth
   history present. If any is wrong, the evidence is a screenshot or a pixel count, not an opinion.
2. **Tape offset across rebuilds** — restore by row index rather than pixel offset (small, contained).
3. **Workstream A–H of `docs/AI_AGENT_BUILD_PROMPT.md`** — theme/token layer first (its gate is a
   grep for raw hex outside the token block), then the cursor-link spine (partly built: `cursor-link.js`
   exists and the engine publishes), then the strips/tape/alert-log refinements, then bar/candle
   expression modes, then replay parity, then the Windows installer.
4. **Harden the DTC test** so the flake stops muddying every gate run.

---

## 5. Gate commands

```
.venv/Scripts/python.exe -m pytest orderflow_system -q           # 311 passed, 2 skipped baseline
.venv/Scripts/python.exe scripts/audit_ui_refs.py                # CLEAN
node --check orderflow_system/desktop/ui/<file>.js               # every JS touched
node orderflow_system/desktop/ui/ofx.selftest.js                 # engine: 80 ok / 0 failed
node orderflow_system/desktop/ui/intent.selftest.js              # arbiter: 7 ok / 0 failed
.venv/Scripts/python.exe scripts/regen_config_golden.py          # only when config defaults change
```

## 6. New files from this session

| File | What it is |
|---|---|
| `desktop/ui/intent.js` + `intent.selftest.js` | the interaction/feed arbiter and its behaviour tests |
| `desktop/ui/strips.js` | scrolling-strip anchoring (holds the reader's place, counts arrivals) |
| `desktop/ui/cursor-link.js` | one price/one time, shared by every panel |
| `desktop/ui/heatmap-pro.js` | heatmap interaction layer (zoom, select, markers, exports) |
| `desktop/ui/scale.js` | the window-change authority (`OFAPScale`) |
| `desktop/ui/ofx.js`, `ofx-view.js`, `atlas.js`, `atlas-v2.js`, `ui.js`, `pause.js`, `guide.js` | extended (ramp, zones, pinch, trace, gates, freeze, wizard) |
| `dashboard/static/tape.js` | tape floor fixed (0 is a real floor now) |
| `orderflow_system/atlas/alerts.py`, `depthmap.py` | level-scoped rules, wall-age detection |
| `desktop/api.py` | `POST /api/control/export/save`, `POST /api/control/client-error` |
| `orderflow_system/test_{intent,strips,workstream_i,wall_age,tape_floor}.py` | the tests that hold all of the above |
| `docs/AI_AGENT_BUILD_PROMPT.md` | the agent brief for the next build phase |

---

## 7. 2026-09-15 — system sweep pass (report: `docs/SYSTEM_SWEEP_2026-09-15.md`)

A full four-step sweep (audit → edge cases → optimisation → roadmap) run against the live Bybit
feed in a sandboxed instance (`APPDATA` redirected, port 8099). Everything below is on disk and
verified; nothing is committed.

| Area | Change | Measured |
|---|---|---|
| `desktop/ui/ofx-view.js` | the Engine view now attaches `ofxHeat`, `ofxLive`, `ofxRibbon` — three of five layers had no canvas, so the depth heatmap, sweeps, crosshair line and CVD ribbon had never painted | canvas ink 0 → 17.9 k/27.4 k (heat), 6.7 k/9.9 k (ribbon) |
| `desktop/ui/ofx.js` | `math.barIndex` (binary search per print), `math.heatColumns` + `math.heatPalette` (column index + colour table), dirty flags always cleared, ribbon path reset | sweep repaint 29.93 → 1.34 ms; heat 0.278 → 0.074 µs/cell |
| `desktop/ui/ofx.selftest.js` | +14 checks for the new maths | 80 → 94 ok |
| `dashboard/static/tape.js` | row-in/row-out live path, per-second clock cache, batched `addTrades`, sub-unit sizes, dead flag removed | 3.628 → 0.284 ms per print; 237 → 7.1 ms per 120-row load |
| `dashboard/static/orderbook.js` | `size\|quantity` normaliser (the REST payload sends `quantity`), finite guards, one scroll per price change | NaN footer / no sizes → real sizes and totals |

Backend findings with line numbers (deliberately not applied — they need their own gates):
broadcast holds `_lock` across every `send_text` with no per-client queue; the tick batch buffer is
cleared after the await; Bybit's `u`/`seq` is used as a timestamp and never checked for gaps; no
retention anywhere (5.8 M tick rows / 547 MB today). Roadmap R2–R5 in the sweep report.

Fixed after three delegated read-throughs (each claim re-verified before acting — full detail in
`docs/SYSTEM_SWEEP_2026-09-15.md` §7):

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/index.html` | `intent.js` is loaded once: the eager tag now sits above `atlas-v2.js` and carries `data-atlas-intent="1"`, so the module's loader no longer injects a second copy (two arbiter instances, two flush timers, doubled listeners) | live: 1 script tag, `frozen:false` |
| `desktop/ui/pause.js` + `ofx-view.js` | the restart contract is real: `pause.js` keeps a `starters` set, empties dead ids on pause, iterates snapshots and exports `unregister`; the Engine view rebuilds its poll on resume (one pause/resume cycle used to stop its updates for the session) | live: 30 fetches/10 s → 0 paused → 25/9 s after resume |
| `desktop/ui/ui.js` | one restartable status poll that honours `OFAP_PAUSED`/`anyHeld()`, plus a logs poll that does the same; the duplicate 3 s status fetch is gone and the tick-rate chip is fed from `per_symbol` (the old code read a `ticks` field the payload does not carry, so the rate was always 0) | live: 0 fetches in 9 s paused; chip reads `{ticks: 2821, rate: 8}` |
| `data/bybit_feed.py` | the undrained `_tick_buffer` (one entry per trade, `flush_tick_buffer` had no caller anywhere) is gone — ~136 bytes/tick at ~52 ticks/s ≈ 250 MB per 10-hour day | grep repo-wide: no consumer; suite green |
| `data/database.py` | volume profiles no longer accrete per rebuild and reads return one row per session (his DB held 81 rows for 2026-09-14, so "last 5 sessions" was one day repeated); rebuilds delete-then-insert, reads take `MAX(id)` per session | new `test_volume_profiles.py`, suite 311 → 313 passed |

### 8. 2026-09-15 — Engine view: bounded navigation + interaction redesign

His report, verbatim: "design a system that prevents the user from scrolling outside draw distances ...
redesign a much better interaction implementation ... consider all metric ingest and output variables".

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/ofx.js` | the viewport is bounded in both axes and re-fits itself: `math.viewLimits()` derives hard limits from the data, `clampView()` clamps **zoom then offsets** (two phases, because the price window depends on `scaleY`) and is called from drag, wheel, pinch, resize, LOD, `snapToLive`, `fitSession` and `setData`; a data-identity change re-fits only when the new price band no longer overlaps the user's window, and a zero-bars-on-screen guard re-fits and counts the recovery | forced clamps by +/-1e6 on offsets and 1e5/1e-6 on zoom read `within: true` with 3-6 bars still on screen; the original blank stage (200 bars at ~99k replaced by 1 bar at ~77k) now lands the bar at x 56 y 108 |
| `desktop/ui/ofx.js` | no axis existed: the base pass now draws gridlines, a right price rail, a bottom clock ruler at adaptive stride, dimmed "no data" bands labelled `no bars after HH:MM:SS`, and the live pass a last-price tag; timestamps are the local clock everywhere (the tip printed ISO/UTC beside a local ruler) | ink probe on `#ofxBase`: rail 1 116 px, ruler 5 976 px; reads `76940 … 76860` and `18:39 … 18:47` |
| `desktop/ui/ofx.js` | `math.adaptHeat` sums the depth matrix onto the bar axis (resting depth + executed volume per `(bar, price)`, one best-bid/ask point per bar, events deduped per `(bar, price, kind)`) — the payload's ~1 s columns were each drawn one bar wide and smeared | heat cells 48 400 -> 593, p95 4.6 -> 0.3 ms, cells per bar `[5:12, 6:69, 7:207, 8:209, 9:96]`; selftest 106 -> 109 checks |
| `desktop/ui/ofx.js` + `ofx-view.js` | the ingest the view ignored is drawn: `calc{}` (volume/buy/sell/delta/POC share/max bid+ask/imbalances), `traded[][]` as flow bubbles, `best[]` as a spread line, `events[]` as stack/pull marks | live: `traded 208 cells`, `best 57`, readout shows POC 20.9 %, max bid/ask with sizes |
| `desktop/ui/index.html` + `atlas.css` + `ofx-view.js` | `#ofxReadout` panel beside the stage (flex row, 20 rows) with the full metric set, `#ofxFit` button, double-click = fit session, an interaction legend, value clipping | overlap check: stage x 240 w 784, panel x 1032 w 206, `overlaps: false`; `#ofxTip` three lines in local time |

Open item deliberately not changed: **the footprint endpoint publishes closed bars only**, so the newest
drawn bar trails the live tape by 45-196 s (newest print 1789464016 vs bar end 1789463940) and
`prints`/`sweep` read 0 for the forming bar. The view says so in its status line; drawing a live forming
bar changes what the view shows and is his call. Backend hardening items from §7 remain unapplied, and
the DTC flake stands.

### 9. 2026-09-15 — Engine legend system + cleaner bars

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/ofx.js` | footprint cells drew `Math.round(bid/ask)` — on crypto sizes (0.001-3) the matrix said "0" almost everywhere (16 of 86 levels on the sampled bar). Now `math.fmtSize` (0.002 / 0.045 / 2.6 / 1.2k) and an empty half is a faint dot | live cell samples; selftest cases for sub-unit, contract and kilo bands |
| `desktop/ui/ofx.js` | bars are framed and annotated: alternating column band + 1px separator, per-column `Δ / V` badge above each bar's high | `columnBadges: 4` at the default `scaleX` 52 |
| `desktop/ui/ofx.js` | colours consolidated into `math.theme` (17 keys), read by the renderers (21 literals replaced) and by `OFX.legend()` — one table, two readers | selftest asserts every legend swatch resolves to a theme colour (first run failed on two that quoted axes literals) |
| `desktop/ui/ofx.js` | `OFX.legend()` — the panel's only source: layout (8 lines), 19 colour keys with meaning + live value, 10 data fields with source + refresh, 9 interactions, live params + stats | selftest + live reads |
| `desktop/ui/ofx-view.js` + `index.html` + `atlas.css` | `#ofxLegendPanel`: three columns, collapsible (remembered), refreshes every fifth 1-second tick, skips while text is selected | 29 rows / 19 swatches / 9 keys / 3 columns measured; collapse toggles; `C = 2.50` followed a param change |

Two bugs of my own, found by probing and fixed: the badge threshold (56px) exceeded the default column
width (52px) so it never drew; and the legend refresh timer was guarded on `view.init`, a flag that does
not exist in this module, so the panel held its birth values (an R change was invisible in it while
`OFX.state.params.R` had moved). It now rides the existing stats timer with no invented guard.

Not rendering-related but worth knowing: **his app instance was closed at ~19:06** — the log ends on
routine signal lines with no traceback, and no OrderFlow process is running. The sandbox on 8099 is
stopped too.

### 10. 2026-09-15 — menu bar / sidebar / profile system plan

`docs/UI_MENU_AND_PROFILES_PLAN.md` — a plan for approval, built from the reference platform and the DTC platform
reference screenshots in `Desktop\New Folder` (register of all 15 in section 1) plus the reference platform
volume-dots knowledge-base page, the reference platform's Open-The-Main-Window, the conventional Chartbooks/Global-Settings/
Transfer pages and the reference platform's workspaces/templates docs, against an inventory of this app's own chrome,
config store and control API.

Headlines: no menu bar exists today (one ☰ overlay); workspaces persist but capture only three fields;
`/api/control/profiles/*` is already the volume-profile feature so the new one is specified as
`/api/control/user-profiles`; credentials stay out of profiles by rule and by test. The plan proposes a
registry-driven menu bar (File/View/Chart/Data/Profiles/Tools/Help), the rail plus per-view Options dock
and workspace tabs, one `param-registry.js` behind every settings dialog, and a schema-versioned profile
store with save/load/rename/duplicate/import/export/backup/restore, five shipped templates, autosave and
quick-switch hotkeys. Five build phases, each with a gate, and six decisions waiting on him (menu style,
profile scope, auto-load, tabs timing, naming, secrets policy).

### 11. 2026-09-15 — Menu bar phases 0 and 1 (plan: docs/UI_MENU_AND_PROFILES_PLAN.md)

Decisions he made: classic menu bar + toolbar; profiles carry alerts + watchlist (opt-out at save);
ask "restore last session?" with a "don't ask again"; tabs in phase 5.

| Area | Change | Verified by |
|---|---|---|
| `desktop/param_registry.py` (new) | the display-variable registry: 81 variables, 17 groups, 14 views, each with kind/bounds/unit/meaning/`applies`; values read from `config_store` at call time, never duplicated | `test_param_registry.py`: 9 tests including **coverage** — every display-relevant leaf in `default_config()` must be registered (suite 313 -> 322) |
| `desktop/api.py` | `GET /params` (registry + live values + defaults), `POST /params` (registered paths only, coerced, clamped by the store, returns the adopted value), `POST /folder/open` (whitelisted config/logs/exports) | live: set R 5.5 -> `stored R = 5.5`; restore -> `stored R = 4` |
| `desktop/ui/menubar.js` (new) | File/View/Chart/Data/Profiles/Tools/Help with accelerators, ticks, disabled-with-reason, inline submenus, Alt/arrow/Enter/Esc navigation, zen mode; **Chart = the active view's own variables** from the registry, with an inline editor (number+slider / bool / enum) and per-variable Restore default | live probes: 7 menus, File 15 items (6 disabled with reasons), View 32 items with ticks, Data sources with "Bybit . active", Chart values inline, editor round trip, keyboard walk, view-switch re-pointing |
| `desktop/ui/index.html` + `modules.css` + `scripts/audit_ui_refs.py` | the `#menuBar` row, its styles (dropdown as a layer of the bar so nothing clips it), the script tag, and `menubar.js` registered in the audit | AUDIT CLEAN; the audit **caught** the one template-literal route the module used |

Three self-inflicted defects the probes caught, all fixed: the dump had no `default` (Restore default
(undefined) and a refused write); `closeAll()` ran before `run()` so `Change…` never opened its editor;
and the engine route was a template literal the audit could not match. Next phase: per-view settings
dialogs from the registry, starting with Engine.

### 12. 2026-09-15 — top-menu dismissal, the ADX/RSI/MACD/OBV/Williams%R add-on pack, drawing layer

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/menubar.js` | the dropdown now closes on any outside touch: `closeAll()` clears the **slot's** class (it only cleared the dropdown's, so menus never shut) and dismissal is a **capture-phase mousedown** plus focusin/blur/scroll/Tab | click the matrix `true -> false`; click the rail -> closed; Escape -> closed; Alt focus, Arrow keys, Escape behave; the matrix still pans (overlay `pointer-events:none` when idle) |
| `desktop/ui/indicators/{adx,rsi,macd,obv,williams-r}.js` (new) | the requested indicators as add-on modules on the existing contract, each carrying `pack`/`version` (OrderFlow indicator pack v0.4.1) | `indicators.selftest.js` 25 checks 0 failed (RSI 100/0 extremes, OBV arithmetic, %R edges, MACD histogram identity, ADX 0-100 + DI dominance); `test_indicators.py` (suite 322 -> 325); live: 5 of 11 modules listed as the pack |
| `desktop/ui/study-api.js` + `studies.js` | `registry.list()` reports pack/version and the library row shows them | live registry dump |
| `desktop/ui/drawings.js` (new) | view-agnostic drawing layer: 11 figures (line, ray, hline, vline, rectangle with extend, ellipse, channel, Fibonacci, text, measure), Shift-45 constraint, endpoint handles, right-click context menu, single-figure mode, hide/clear, axis highlighting, data-space storage | live: gesture-drawn line in data space, persisted via the API, single-figure returned to Select, context menu with six actions, drawings survived a view switch |
| `desktop/api.py` + `config_store.py` | `GET/POST /api/control/drawings` per view+symbol with a strict sanitiser (kinds whitelisted, finite points, hex/rgba colours only, width 1-8, 500 rows/slot, 64 slots) | sanitiser probe: width 99 -> 8, dash 'wobbly' -> solid, a script-url colour -> default, bad rows dropped |
| `desktop/ui/menubar.js` + `modules.css` + `ofx-view.js` | a **Drawings** menu (figures with ticks, modes, colours, the view's drawing list) and the Engine-view mount | live: menu lists 11 figures + modes + `Clear all drawings (2)`; layer mounted with 11 tool buttons |

Known staging: the layer is mounted on the Engine view; the candle chart (lightweight-charts) and the
Heatmap follow through the same adapter contract. `mountDrawings()` was defined but never called at
first — the live probe caught it (layer absent), fixed and re-verified. Next phase remains the
per-view settings dialogs from the parameter registry.

### 13. 2026-09-15 — ModFlow OrderFlow Analysis Suite rename + third-party strip

Display name `OrderFlow Analysis Pro` → **ModFlow OrderFlow Analysis Suite** in 30 files (36
occurrences) and in the chrome: page/window title, rail brand (mark `MF`, name `ModFlow`, sub
`OrderFlow Analysis Suite`), top bar, launcher title, frozen-build `APP_NAME`.

Deliberately unchanged so his install keeps working: the `orderflow_system` package, the config dir
`%APPDATA%\OrderFlowAnalysisPro`, the log/DB names, the repo path, and the config key
`platforms.sierra` (his saved DTC block lives there). The DTC route path *was* neutralised —
`/platforms/bridge/dtc` (+ `/test`); the old `/platforms/sierra/dtc` and `/platforms/open` are gone.

Third-party material removed: the plan/link/install-detection content of `platforms.py` (the module
is now just `dtc_defaults()` + `suggested_symbols()`), the promo halves of `platforms.js` and
`/api/control/platforms`, six reference documents (`PLATFORM_BRIDGES`, `PLATFORM_INTEGRATION_PLAN`,
`NINJATRADER_NOTES`, `TRADOVATE_STUDY_BRIDGE`, `ATAS_COMPARISON`, `ATAS_FEATURE_INTEGRATION`), the
29 MB `.scratch/` research folder, and **612 prose pointers across 77 files** reworded to neutral
wording. The vendored chart library was left alone: third-party code under its own licence.

Repairs after the sweep (it broke two things, both found by the gates): an apostrophe inserted into a
single-quoted JS string in `test_studies.py` (`'ATR (the suite's …-shaped)'` → `'ATR (contract-shaped)'`),
and "the the …" double articles in 15 files from mid-sentence token replacement. A follow-up scan
reports no vendor product words left in our files.

Verified: **316 passed / 2 skipped** (the nine removed catalogue tests account for the drop from
325), `AUDIT CLEAN`, all modules parse, both selftests green; live: sandbox boots, the page serves the
new title/brand, the bridge payload is DTC-only, `/platforms/open` → 404, the neutral DTC route → 200.
Nothing committed — HEAD `b2ff4ee`.
### 14. 2026-09-15 late — Sierra Chart integration (free-first, with a plan toggle)

`platforms.py` + `platforms.js` + `/api/control/plans|open` rebuilt as the suite's own integration
surface: a 6-step free-path workflow (7 with the activation step for paid), 12 allow-listed links
(download, trial, delayed feed, create account, control panel, activate package, pricing, payment,
DTC protocol, setup, support, futures data), plans listed free-first with the published monthly
prices (`0 / 26 / 36 / 36 / 46 / 56` USD) quoted as read 8 September 2026 with the source link and the
exchange-fee caveat, local-install detection, and a "load into my workflow" toggle whose stored facts
(`platforms.sierra.plan`, `.integrated`) change the workflow, the data-quality wording and the status
line. Verified live: p10 switch → 7 steps + real-time wording, then back to free; the link opener
refuses non-allow-listed hosts; install detected at `C:\SierraChart` build 2950. Tests:
`test_sierra_integration.py` (8), suite 324/2, AUDIT CLEAN.
### 15. 2026-09-15 late — dxFeed-style terminal shell + Quantower: plan

`docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md`. Key finding: the panels are already widget-shaped
(`<section class="view">` + own MutationObserver), so the terminal mode **re-parents** them into widget
frames instead of forking them — the switch costs a detach, and Classic stays byte-for-byte today's
DOM. Adds: `shell.js` host, layout store (named layouts/tabs/per-screen, config-backed), widget
chrome, tab strip, symbol/timeframe link groups, and a refcounted channel bus so N widgets on one
symbol share one subscription. New additive widgets: Watchlist, News, Fundamentals, Options/Greeks
(the last states plainly when no Greeks feed is configured). Top bar gains Layout ▸ and the
Classic|Terminal switch (Ctrl+Alt+T) plus a status-bar mode/tab/widget/feed readout. Quantower gets
the same treatment as Sierra in phase 6, held until its licence prices can be read from source rather
than guessed.

### 16. 2026-09-15 late — Terminal shell **phase 0** (plan: `docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md`)

The host that re-parents panels, the layout store behind it, and the round-trip gate. Nothing
committed — HEAD `b2ff4ee`.

| Area | Change | Verified by |
|---|---|---|
| `desktop/config_store.py` | new `layouts` block: `{mode, active, items{id:{name, mode, screen_key, theme, saved, tabs:[{id,name,widgets:[{view,x,y,w,h,link,settings}]}]}}}`. One grid constant set (`LAYOUT_GRID_COLS/ROWS` 12×8, 24 layouts, 12 tabs, 24 widgets/tab). Geometry clamped in two phases (size, then position) so a widget can never be stored hanging off the grid; ids/tab ids must be slugs; unknown views, duplicate tab ids and non-scalar settings are dropped; `active` must name a stored layout | `test_layouts.py` (17 tests) |
| `desktop/api.py` | `GET/POST /api/control/layouts` — one write per call (`mode · save · import · duplicate · rename · delete · activate`, `export` returns a bundle and writes nothing). Every response carries the state the store *accepted*, and a refused save is reported instead of vanishing | live: `{"mode":"terminal","save":…,"activate":…}` → `actions: ["mode","save","activate"]`; bad-id save → `ok:false` + reason |
| `desktop/ui/shell.js` (new, 765 lines) | the host: `OFAPSHELL` with `switchTo/focusView/openWidget/closeWidget/activateTab/arrange/saveNow/stats/math`. Panels are **re-parented** into `.widget-frame`s inside a 12×8 CSS grid; every section stays in the document (hidden tabs use `.wf-off`, never detach); a section carries `.active` exactly while a frame showing it is visible, which is the meaning that class already had. `showView` is wrapped (Classic = straight delegation; Terminal = open/focus that panel's widget) and a capture-phase rail listener covers the case where a module re-wraps it later. Widgets auto-save through `OFAPINTENT.queueWrite` (never mid-gesture) | see the round trip below |
| `desktop/ui/shell.selftest.js` (new) | the layout maths in Node: rect clamping (incl. the falsy-zero family — `null`/`''` are *missing*, not 0), overlap, first-fit slotting, dense tiling (no overlap, inside the grid, exact cover for square counts), the normaliser (drops unknown/duplicate panels, clamps, unique tab ids, ≥1 tab), idempotence of `normaliseLayout(defaultLayout(…))` | `18 ok, 0 failed` |
| `desktop/ui/index.html`, `atlas.css`, `scripts/audit_ui_refs.py` | script tag (+ `shell.js` registered in `JS_FILES`), the rail-footer **◫ Terminal mode** button, and the terminal CSS block (grid, frame chrome, bar, tab chips) + container queries | AUDIT CLEAN |
| `orderflow_system/test_shell.py` (new) | gates the above: parses, selftest passes, documented surface exists, loaded in `index.html` and registered with the audit, grid/cap numbers agree with `config_store`, the module contains no engine/socket/feed call, Classic is delegation-only, it announces `ofap:relayout` (and the Engine view acts on it), and no `localStorage`/`sessionStorage`/`indexedDB` anywhere | suite **351 passed / 2 skipped** |

**The round trip (the phase-0 gate), measured live in a sandboxed instance on 8099 with the Bybit
feed running** — Classic → open widgets → Terminal (two tabs) → Classic:

* Classic: 24 sections in `main.views`, no host, no body class, one `.active`.
* Terminal: 10 frames, 7 visible on Main and 3 on Macro; `.view.active` count == the number of
  visible widgets (7 then 3 after clicking the Macro chip) — hidden tabs really do pause their panels.
* A rail click in Terminal mode placed *and* focused the clicked panel (11 placed afterwards).
* `order_exact: true` — all 24 sections came back in the exact recorded order; host gone, body class
  gone, frame count 0, one active view.
* Ingest was never touched: `OFAPINTENT.status().feed.ticks` 0 → 4 426 across the terminal leg and
  4 480 after the return, with `feed.live` true throughout.
* Mode persists: after switching to Terminal and reloading, the app boots **in** Terminal with the
  same 10 widgets (7 visible), and switching back restores 24 sections.
* `client error:` lines in the sandbox log over the whole session: **0**.

**Two defects found by the probe and fixed (they were mine, both in `shell.js`):** the first restore
re-inserted each section "before its recorded next sibling" — a sibling still inside a frame reads as
absent, so the node was appended instead and the 24 sections came back **shuffled** (the fix is a
DocumentFragment re-append in recorded order, which cannot depend on where the nodes happen to be);
and the Engine view's fixed 238 px readout starved its canvas to **79 px** inside a 327 px frame
(container queries on the frame — `container-type: inline-size` — now size the panel by the frame:
295 px stage, 293 px canvas). Grid rows also changed from `minmax(120px,1fr)` to `minmax(56px,1fr)`
so a full board fits the window instead of always scrolling.

**A third defect the same probe found, in the Engine view's own geometry** (`ofx-view.js`): the
engine's pointer maths reads `getBoundingClientRect`, so its internal space and the stage box have to
be one thing — `stageSize()` returned `max(240, clientHeight - 8)`, and in a 148 px-tall widget that
made the hovered price (and the trace line naming it) land elsewhere on the drawn matrix. It now
returns the exact box, `null` when the stage is hidden (0×0 is not a size to draw at, and the caller
keeps the last real one), the view re-measures whenever it comes back on screen, and the shell
announces every re-parent/arrangement change as `ofap:relayout` — a re-parent is invisible to the
window resize listeners the views already have, so without that the canvas kept its Classic size
(measured: 293×240 inside a 213×148 stage). Verified live: stage == internal == canvas at
750×260 (Classic), 293×148 (widget) and back; hover offset **0.00 px** (34 px before the fix); a
hidden Engine view keeps 750×260 instead of collapsing to 1×1.

**The DTC flake from §2 is fixed.** `test_probe_handshake_against_a_spec_conformant_server` asserted
the mock server had *recorded* the client's LOGOFF while the server thread was still reading it —
about one full-suite run in four failed on that last line. The test now waits (up to 1.5 s) for the
logoff to arrive before asserting. Four consecutive full-suite runs: `351 passed / 2 skipped` each.

**Deliberately still open:** drag/resize/maximise/float and the tab strip's add/rename/reorder/close
(phase 1); the Layout menu, per-screen profiles and status-bar fields (phase 2); link groups (3);
the channel bus (4); Watchlist/News/Fundamentals/Options (5); Quantower, held on its licence read
(6). The active tab is session state (it resets to the first tab on reload) — the store has no field
for it yet. A layout whose panel does not exist in the build is dropped with a line in the bar, and
the drop is not persisted until the user changes the arrangement.

### 17. 2026-09-15 late — Terminal shell **phase 1**: widget chrome, tab strip, keyboard

`shell.js` 765 → 1185 lines, `shell.selftest.js` 18 → 22 checks. Nothing committed — HEAD `b2ff4ee`.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/shell.js` | **drag by title bar** and **resize from the corner grip**, snapped to grid cells through two new pure functions (`math.moveRect`, `math.resizeRect` — size limited by the distance to the edge, position kept), with the clamp applied on every pointermove, so no gesture can leave the grid; the widget you just placed is brought to the front | live: a 2-cell/1-cell drag landed exactly at (6,1); a drag 3× the board past the corner stopped at (8,6) = the edge; `bounds().outside` 0 throughout |
| `desktop/ui/shell.js` | **⛶ maximise** fills the grid and **Esc/the button restores** — the pre-maximise rect rides in the widget's own `settings` (`px/py/pw/ph/max`), so it survives a reload; **⚙** opens the parameter registry for THAT panel | live: 12×8 + `.wf-max` + `settings {px:8,py:6,pw:2,ph:1,max:true}`; Esc → 2×1 at (8,6); the gear opened the Chart menu with the ofx panel's variables (`ofx.R`, "Stacked run (levels)", 65 items) |
| `desktop/ui/menubar.js` | `OFAPMenuBar.setView/openFor` — the shell moves the registry's notion of "active view" to the widget the user is working in (several panels are on screen at once in Terminal mode) | live: the gear's menu carried the focused panel's variables, not the previous view's |
| `desktop/ui/shell.js` | **tab strip editing**: `+` adds a tab, double-click renames in place (the input stops its own keys so a tab named "1" is not the tab hotkey), drag reorders, `×` on the active chip closes it (and says how many panels went with it) | live: add → `t3 "Tab 3"` → renamed to "Scalper"; drag `main` onto `macro` → `[macro, main, t3]`; `×` closed Main with "8 panel(s) went with it"; 1 tab minimum, 12 maximum |
| `desktop/ui/shell.js` | **keyboard**: `Alt+1…9` switch tab, `F11` fills the grid with the focused widget (first widget if none), `Esc` restores it then drops the focus ring; typing is never a hotkey | live: Alt+1/Alt+2 switched tabs; F11/Esc round-tripped the maximise |
| `desktop/ui/shell.js` | `bounds()` telemetry (per-widget rect + `inside`, `outside` count) for the gate | the gate below |
| `desktop/ui/atlas.css` | frame chrome styles (`.wf-btn`, `.wf-grip`, `.wf-move`, `.wf-max`), tab chips (`.tt-name/.tt-x/.tt-add/.tt-input`), `body.wf-gesture` (no text selection; the panel under the pointer stops receiving it) | visual probe + no client errors |

**The phase-1 gate**: *twelve widgets on one tab stay inside the frame bounds; frames persist across a
reload.* A layout with twelve panels on one tab (tiled 4×3) loaded from the store: 12 frames, **none
outside the board** (board 998×504 px, frames 120–248 px; the check compares against the board's
*content* box, because the board scrolls), `bounds().outside === 0`, 12 `.view.active`, and all 24
sections still in the document. A drag and a resize then survived an **immediate** reload, and
switching Classic → Terminal → Classic restored the 24 sections in the exact recorded order with
`OFAPINTENT` ticks rising throughout and **0** `client error:` lines.

**Three defects the probe caught and this session fixed** (two mine, one a real persistence hole):
1. `math.resizeRect` first used the store's storage clamp, so a long rightward resize **jumped the
   widget to the left edge at full width** instead of stopping at the edge — caught by a self-test
   expectation, not by eye.
2. **A dragged arrangement could be lost.** Writes are deferred behind the arbiter's gesture lease
   (by design), so a drag followed by a reload within ~1.6 s reverted (measured). `pagehide` /
   `visibilitychange` now run the pending save immediately with `keepalive`, and a dirty stamp means
   a save in flight never swallows later edits.
3. Probe-side, worth remembering: "widgets inside the board" must be measured against the board's
   scrollable *content* box — comparing against the visible box flagged the bottom row as outside.

**Deliberately still open in this area:** *float* (free-pixel windows that hover over the board) is
not built — **⛶ fills the grid**, which is the same thing within the 12×8 model this suite uses; the
symbol/timeframe link chip belongs with phase 3's `links.js`; the ⚙ button opens the registry's own
Chart-menu editor rather than a new per-panel dialog (phase 2 builds those); the active tab is still
session state, and maximising a widget stores the full-grid rect plus the pre-maximise rect.

### 18. 2026-09-15 late — Terminal shell **phase 2**: Layout menu, workspace switch, status fields

Nothing committed — HEAD `b2ff4ee`. Suite **352 passed / 2 skipped** (one new test), AUDIT CLEAN,
`shell.selftest.js` 22 ok.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/menubar.js` | a **Layout** menu built from the store on every paint: Workspace (Classic ⇄ Terminal with a tick), This layout (Name · Save now · Save as… · Duplicate · Delete…), Auto-arrange this tab (disabled with its reason in Classic mode), Reset to the starter board, Save for this screen (`1920x1080@1.25`), Export current…, Import (paste a bundle)…, then every saved layout with `· active` / `· this screen` / `saved on <key>` and its widget/tab counts, and `N of 24 layouts` | the menu listed all three headers + 15 items; the Saved-layouts rows carried the counts |
| `desktop/ui/menubar.js` | text answers happen **in place** (`mbPromptInput`, Enter applies · Esc cancels · Ctrl+Enter for the multiline paste box) instead of `window.prompt`, which the frozen shell's WebView is not guaranteed to render | typed "Evening board" into the prompt with real keystrokes and Enter → saved, active, `screen_key 800x600@1`, status line "saved as “Evening board”" |
| `desktop/ui/shell.js` | layout CRUD the menu calls: `saveAs / renameLayout / duplicateLayout / deleteLayout / activateLayout / saveForScreen / resetBoard / exportLayout / importLayout / layouts / refreshLayouts / screenKey`; every action adopts **what the store accepted**, and Delete asks for the layout's own name first | rename → "Evening desk"; duplicate → "Evening desk copy"; delete with a wrong name **refused** ("the name did not match"), with the right name → stepped onto the next layout; reset → the 4-widget starter board; arrange → a 2×2 tiling with `outside: 0` |
| `desktop/ui/shell.js` | export writes a **real file** (store bundle → `POST /api/control/export/save`), import takes a pasted bundle under a fresh id with a de-duplicated name, and an unparseable bundle is refused by name | `layout-Start.json`, 1 066 bytes on disk (keys `["layout"]`, one tab, 4 widgets); the same bundle imported as "Start 2"; `'not json at all'` → "that is not a layout bundle (invalid JSON)" |
| `desktop/ui/index.html` + `atlas.css` | the **workspace switch** in the top bar's right cluster (`#modeSwitch`, segmented, `aria-pressed`, one click, no menu) and four status-bar fields: **mode · tab · widgets · feed** | live: clicking Terminal switched the mode, the segmented control followed, and the status line read `Terminal / Twelve / 12 / Bybit · free feed` |
| `desktop/ui/shell.js` | the **feed** field follows the stored plan (Sierra `plan` + `integrated` from `/api/control/platforms`) and falls back to the built-in source from `/api/control/sources` — the wording the platform module itself promises ("free feed" / "delayed data" / "real-time data") | `Bybit · free feed` with no Sierra integration on; the wording is the platform module's own |
| `desktop/ui/menubar.js` | **defect found and fixed:** ArrowDown inside an open menu did nothing — the only ArrowDown branch opened a menu from a *title*, so with an item focused the keyboard could reach the **first item of every menu and no further**. Added the in-menu walk (with the ArrowUp branch that already existed) | walked all 13 Layout items with real CDP keystrokes (Alt → → → ↓ then 12 × ↓), each step reading `document.activeElement` |

**The phase-2 gate** — *every menu item reachable by keyboard; switches and layouts round-trip through
the config*: the Layout menu is reachable at Alt → → → ↓ and every item walks with ↓ (and ↑), the
in-place prompt takes typing and applies on Enter; the top-bar switch and the Layout menu both write
the mode, and the arrangement writes go to the config store — after a reload the app came back in
**Classic** (24 sections, no host) and then, with "Twelve" active, in **Terminal with all 12 widgets**
and the status bar reading `Terminal / Twelve / 12`. Classic → Terminal → Classic still restores the
24 sections in the exact recorded order, and the sandbox log has **0** `client error:` lines.

**Harness note for the next session:** a CDP `Input.dispatchKeyEvent` Enter does **not** synthesise the
default activation of a focused `<button>` (a real Enter does); the item path was verified by the same
`click` a real Enter produces, and the keystroke path was verified on the walk and in the prompt input.


### 19. 2026-09-15 late — Terminal shell **phase 3**: link groups (symbol / timeframe A–D)

Nothing committed — HEAD `b2ff4ee`. Suite **361 passed / 2 skipped** (9 new tests), AUDIT CLEAN,
`shell.selftest.js` 22 ok, `links.selftest.js` 10 ok.

The shape of the phase, in one line: **membership is stored, meaning is derived.** A widget's link
lives in the layout (`config_store` sanitises `"<symbol group>/<timeframe group>"`, A–D, either side
optional) so it survives a reload and travels in an exported bundle; what a group's symbol and
timeframe *are* is seeded from the panels already on screen, because the panels' own controls are the
only place those values really live.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/links.js` (new) | `window.OFAPLINKS`: groups A–D, `plan/controlsOf` (pure: who moves, onto which controls), `setGroup/apply/seed/sweep`, `groups/members/state/tfLabel`. Reach for a panel through its **own** control where it has one (`ofx → #ofxSymbol`), the app-wide instrument (`#symbolSelect`) otherwise, and `#tfSelect` for timeframes — the chart is the only panel with one | `links.selftest.js` 10 checks: members of A move, a B member does not, a panel that joined nothing does not; three app-wide members are **one** control; a timeframe plan only reaches the chart |
| `desktop/ui/links.js` | two-way: a user change of the app instrument moves every group linked to it; a panel's own select moves only its own group. Every write the module makes is wrapped in `state.applying` so its own change cannot bounce back as user input | live: dispatching a `change` on `#symbolSelect` (BTCUSDT) moved group A and left group B on SOLUSDT |
| `desktop/ui/shell.js` | the **link chip** in every widget's title bar (`⇄ A·B`, `⇄ –·–` when independent) with a popover of `– A B C D` per kind, the current choice marked, and a note naming the group's values **and where they land** ("(the app-wide instrument)" vs "(this panel)") | chip + note read back for all five panels; picking timeframe group B from the popover wrote `B/B` through store, chip and note in one click |
| `desktop/ui/shell.js` | `linkSpec / setLink / linkMembers / paintLinkChip`, `math.parseLink / math.formatLink` (the one reader/writer of the link shape), and `ofap:links` announced on a membership change so the module re-reads | membership set on a live layout and read back from `config.json`: `Start → [ofx A/, tape A/, depth B/]`, `Twelve → [ofx B/B, tape A/, depth A/, chart A/A]` |
| `desktop/config_store.py` | `LAYOUT_LINK_RE` — the link is now **validated**, not just truncated: `"A/B"`, `"A/"`, `"/B"` kept as written; `"E/Z"`, `"1/B"`, `"A/B/C"`, `"/"` stored as no link (a link that is not a link is nothing, not text) | `test_links.py::test_the_membership_shape_matches_the_store` (JS writer and Python sanitiser accept exactly the same strings) |
| `orderflow_system/test_links.py` (new) | 9 tests: the module loads and parses, its self-test passes (≥10 checks), it exposes the documented surface, it is loaded **after** the shell, the shape agrees with the store, and — the invariant this layer exists for — **it never reaches for the engine** (no `/api/`, no `fetch(`, no WebSocket) | full suite 361 passed / 2 skipped |
| `scripts/audit_ui_refs.py` | `links.js` added to `JS_FILES` | AUDIT CLEAN |

**The phase-3 gate** — *changing a group moves every member widget; non-members unaffected*:
`setGroup('sym','A','ETHUSDT')` moved the app instrument (`#symbolSelect` **and** `S.symbol` — the
app's own handler ran, so every engine-following panel really did re-read) while the group-B panel kept
BTCUSDT and the panel that joined nothing stayed independent; `setGroup('sym','B','SOLUSDT')` moved only
the Engine's own select, no cross-talk; `setGroup('tf','A','300')` moved `#tfSelect` and `S.tf`. With
the engine **running**, a group symbol change left ingest alone: ticks **146 → 266**, engine still
`Running`, and the sandbox log holds **0** `client error:` lines and **0** engine stop/restart calls
across the whole phase.

**Two defects the gate caught, both fixed:** (1) a value a select cannot hold (an instrument this
installation does not list) *cleared* it — `control.value` was assigned before it was checked, so the
instrument went blank; the control is now put back to what it held, nothing is dispatched, and the
refusal is reported (`"sym A → NOTLISTED: 1 control(s) refused it"`), with a good value applying
normally right after. (2) the chip's timeframe note read `timeframe B ·` with nothing after the dot
when the group had no value yet — now `—`.

**Also fixed while testing (phase-2 surface):** `activateLayout` took an **id** only and failed
*silently* when handed a name, while the menu shows names; it now resolves an id or a unique name
(`resolveLayoutKey`) and refuses to guess when two layouts share one.

### 20. 2026-09-15 late — Bookmap folded in beside Sierra (side task; phase 4 not started)

Nothing committed — HEAD `b2ff4ee`. Suite **374 passed / 2 skipped** (13 new platform tests), AUDIT
CLEAN, sandbox log 0 `client error:` lines.

**The read, from the installed Bookmap 7.8.0 build:13** (not from marketing pages alone): build number
from `Bookmap.jar`'s manifest; API jars in `C:\Program Files\Bookmap\lib` (`bm-l1api`,
`bm-simplified-api-wrapper` + javadocs, `bmmp-history-data-library-jvm`, `api-jvm-0.1.22-alpha`); API
folders `%LOCALAPPDATA%\Bookmap\API\Layer0ApiModules` (adapters, `…---name---version.jar` + `.metadata`)
and `Layer1ApiModules` (add-ons). It listens on **no local port** and publishes **no data-out API** —
its API is in-process, so an add-on is the only way out.

| Area | Change | Verified by |
|---|---|---|
| `data/bookmap_client.py` (new) | the suite's end of the add-on wire: NUL-framed JSON, `bookmap_probe()` shaped like `dtc_probe` (ok/stage/messages/sample/rejects/detail), symbol filter, unknown types tolerated, never raises, 1 MiB frame ceiling | 9 tests vs a mock add-on (hello/no-hello/garbage/filtered/dead-port/bad-port) **and** a live run through the UI button: *"add-on ofap-bookmap-bridge 0.1 on Bookmap 7.8.0 build:13 · licence Digital — hello 1, snapshots 9, trades 9, depth 9"* |
| `data/bookmap_addon/` (new) | the Bookmap side as a template: `OfapBridge.java` (read-only, loopback-only, `Layer1SimpleAttachable` + `CustomModuleAdapter` + trade/depth listeners, names and signatures taken from the **installed** javadocs), `build.gradle` compiling against `fileTree(C:/Program Files/Bookmap/lib)`, README (build, install via *Settings → Configure API plugins → Add*, licence gates, frame format) | **not compiled here — no JDK on this machine** (Bookmap ships a JRE); the README and the UI say so rather than implying it runs |
| `desktop/platforms.py` | Bookmap as a second catalogue row: 13 allow-listed links (portal, packages-comparison, knowledgebase, bmdata, dxfeed, addons-info, the API tutorial, the Python-API GitHub repo), 4 tiers with published prices **read 15 September 2026**, the free-first workflow (incl. the add-on step and the licence-gate step), caveats naming the separate data bill and the one-instrument free tier, and `bookmap_defaults()` (loopback 8791, no credentials at all) | live: tiers `$0/1 ins`, `$19/3`, `$49/10`, `$99/20`; detection `7.8.0 build:13` + api jars + 3 L0 adapters |
| `desktop/platforms.py` | `detect_installs()` now returns both platforms; the Bookmap version comes from `Bookmap.jar`'s manifest and the API module folders are listed by filename only — **licence/account/config files are never opened** | a test plants `Keys/licence.key` and a token-bearing config in a fake install and asserts neither value nor the folder name appears in the result |
| `desktop/api.py` | `/platforms` keeps every Sierra key and adds `bookmap`, `bookmap_plans/_links/_caveats/_prices_as_of/_limits/_workflow/_note`; `/platforms/plan` takes `platform:"bookmap"`; new `/platforms/bridge/bookmap` + `…/test` | live: tier `globalplus` stored, workflow grew the activation step; Save stored `{enabled, port 8791, plan, addon_built}` |
| `desktop/ui/platforms.js` | five Bookmap cards under the five Sierra ones (integration header + tier select, setup steps, tier cards with instrument caps and backfill, "Bookmap on this machine", the loopback bridge card with Save/Test), a Bookmap result line, and updated help topics | live: 10 cards rendered; the bridge Test line; `path not on the allow-list: /someone/else` for a non-Bookmap GitHub path |
| `test_platforms.py` | 13 tests: catalogue order and free-first invariants for both platforms, tier caps/limits, caveats naming the gates, the two-vendor allow-list (incl. the `github.com` path trap and a lookalike host), the Bookmap workflow, credential-free defaults, the mock add-on suite, and detection vs the real disk | 374 passed / 2 skipped |

**Defect the tests caught:** the reader's counter map was singular/plural-wrong (`trade` never reached
`trades`; `snapshot` fell to `other`), so a live add-on would have read "0 trades" while streaming.
Fixed with an explicit frame-type → counter map (`quote` and `snapshot` share one bucket).

**Left open, deliberately:** the add-on cannot be built or installed from here (no JDK, and Bookmap
running on this machine is the user's live instance — nothing was installed into it). The suite side is
complete and tested; the Bookmap side is a build-and-add-once step for the user, with the licence gate
named on the card.

**Next: phase 4** (the channel bus with refcounts + telemetry) — not started in this run.

### 21. 2026-09-15 late — the bridge jar, actually built (JDK installed, compiler-verified)

The add-on is no longer a template-only claim: a JDK was installed and the jar built and statically
verified. Nothing committed — HEAD `b2ff4ee`.

**The build.** No JDK existed on this machine and Bookmap ships a JRE (its `jre/bin` has `java.exe` and
`keytool.exe` only), so a portable **Temurin 25.0.4.1** was unpacked to `C:\Users\Moddy\tools\jdk-25`
(no installer, no admin, nothing on PATH). Bookmap's bundled runtime is **Temurin 25.0.2**, so the target
is Java 25 — `build.gradle` was corrected from the earlier Java-8 assumption (class files are major
version **69** on purpose; they only ever load inside Bookmap 7.8+).

**What the compiler corrected in the template** (this is why the build is the test):

| Was | Is | Why |
|---|---|---|
| `extends CustomModuleAdapter` | `implements CustomModuleAdapter` | `javap` on the installed jar: `CustomModuleAdapter` is an **interface** (`extends CustomModule`) whose `initialize(...)` and `stop()` are **default** methods. It was never a base class. |
| a leftover identity `frame(String)` helper | removed | dead weight; the JSON strings go straight to the socket |

Everything else compiled against the installed jars unchanged: `initialize(String, InstrumentInfo, Api,
InitialState)`, `stop()`, `onTrade(double, int, TradeInfo)`, `onDepth(boolean, int, int)` — all four
override the real interfaces.

**Verified artifact** `orderflow_system/data/bookmap_addon/ofap-bridge.jar` (7 027 bytes):
`javap -v` shows major version 69, `RuntimeVisibleAnnotations` carrying
`Layer1SimpleAttachable`, `Layer1StrategyName(value="OFAP bridge")`, `Layer1ApiVersion`; the class header
reads `implements velox.api.layer1.simplified.CustomModuleAdapter, TradeDataListener, DepthDataListener`
with the exact signatures, and its constant pool references Bookmap's own
`velox/api/layer1/data/{InstrumentInfo,TradeInfo}` — it cannot load anywhere but inside Bookmap.

**The licence question, answered from his own log rather than guessed:** Bookmap's current
`Logs/log_20260915_122952_560-common-01.txt` shows it loading and unloading
`velox.api.layer1.layers.Layer1ApiLargeTradesAlerter` — a Layer-1 strategy that the pricing table sells
with the paid tiers — so the API-plugins path is open on this licence. The log also shows his live
sources (`ESZ6.CME@BMD`, `BTC-USDT:MB:SP@BMD`, `AAPL@DXFEED`), so the bridge will carry real data for
whichever chart it is attached to.

**Left for the user (GUI only, nothing automatable):** Settings → Configure API plugins → Add → the jar →
enable → attach "OFAP bridge" to a chart → then Platforms → Bookmap → Test connection (127.0.0.1:8791).

### 22. 2026-09-15 late — Terminal shell **phase 4**: the channel bus, and the jar ships with the app

Nothing committed — HEAD `b2ff4ee`. Suite **388 passed / 2 skipped** (14 new tests), AUDIT CLEAN,
`shell.selftest.js` 22 ok, `links.selftest.js` 10 ok, `bus.selftest.js` 10 ok.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/bus.js` (new) | `window.OFAPBUS`: channel = (method, url, params) with cache-busters dropped; **one timer and one in-flight request per channel**, refcounted; late subscribers start from the live payload; a tick during a slow response is skipped, not queued; `subscribe/poll/request/stop/stopAll/install/uninstall/telemetry/summary/reset/canon` | `bus.selftest.js` 10 checks: the key rules, 12 subscribers → 1 channel, a late subscriber, skips on a slow server, one-shot sharing, the wrapper's coalescing, failure + recovery, the interval floor |
| `desktop/ui/bus.js` | `install(['/api/…'])` wraps the global fetch for chosen prefixes only: concurrent identical GETs become one request, everything unmatched passes through untouched, `Response` handed back is real | live: 12 concurrent identical GETs → **1 request, 11 coalesced, 92 % saved** |
| `desktop/ui/index.html`, `shell.js` | a **bus** field in the status bar, written by `paintStatus` only when `OFAPBUS` is present (no bus, no crash) | status line reads `bus: 12 sub · 1 ch · 6 fetches` while polling, `bus: idle` after |
| `desktop/ui/bus.js` + `test_bus.py` | the invariants: exactly one `setInterval`/`clearInterval` in the module and it lives on the channel record; no storage; no engine/socket calls; loaded after shell+links; registered with the audit | `test_bus.py` 7 tests |
| `scripts/build_exe.py` + `platforms.py` + `api.py` + `ui/platforms.js` | the Bookmap add-on **ships with the app** (PyInstaller data, beside the UI), the suite reads the shipped jar's class-file version and the local Bookmap's `jre/release` and **compares** them, the card shows the jar line + path + "Show the jar", the wizard step says "no compiler needed" | live: *shipped with this app · built for Java 25 · your Bookmap runs 25.0.2* + "it will load as-is"; a fake install at Java 17 warns to rebuild; 7 new tests |

**The phase-4 gate** — *twelve same-symbol widgets produce one fetch per interval, three different
symbols produce three*: twelve subscribers on `/api/atlas/klines/BTCUSDT` at 1 s gave **one channel, one
immediate fetch, 6 fetches in 5.6 s and 72 deliveries**; removing them left `channels: 0` and the server
quiet. Three symbols × four widgets gave **three channels, three immediate fetches, 15 fetches in 4.3 s —
5 per symbol**, and the sandbox's own access log agrees (5 / 5 / 5). 0 `client error:` lines throughout.

**Stated plainly: the panels are not routed through the bus yet.** The gate was the bus's arithmetic,
and that is what exists — a delivery layer, its telemetry and an opt-in wrapper. Converting each view's
poll loop into a `subscribe` is the next per-panel step, not something this phase silently claimed.

**Defects caught by the self-test:** the `Math.max(100, intervalMs)` floor made 30 ms test intervals
untestable — the floor is now pinned as a rule and the checks run at/above it; and the flaky-transport
check was asserting against a `window.fetch` the module never reads (it uses the injected transport) —
rewritten to fail and heal the real seam.

### 23. 2026-09-15 late — phase 4b verified live, and phase 5's first two widgets (Watchlist, News)

Nothing committed — HEAD `b2ff4ee`. Suite **407 passed / 2 skipped** (19 new tests: 8 watchlist, 11
news), AUDIT CLEAN, `watchlist.selftest.js` 15 ok, `news.selftest.js` 17 ok, `bus.selftest.js` 11 ok.

**Phase 4b, re-verified in a live app** (sandbox 8098, my own run, not a self-report): the app boots
(26 views, 27 nav items, no error banner) and the delivery layer is installed for
`[/api/control/engine/status, /api/instruments, /api/status, /api/atlas/]`; the status bar reads
`bus: idle · watching …`, and with the Watchlist open the telemetry reads
**`bus: 1 sub · 1 ch · 17 fetches (4 saved)`** — the "4 saved" are real duplicate GETs the wrapper
coalesced in the running app, which is the app-wide adoption doing its job.

**The two panels** (built as parallel workstreams, each on its own three files; I verified the files,
ran every gate myself and checked both panels live):

| Panel | Files | Live evidence (mine) |
|---|---|---|
| Watchlist | `ui/watchlist.js` (477), `ui/watchlist.selftest.js` (415), `test_watchlist.py` (144) | 45 rows, count `45`, sub line *"polling 2s via the shared bus · engine stopped — no live rows · the server is answering with its demo list, not your feed"*, and **1 bus channel** — the panel shares one poll instead of adding its own timer |
| News | `ui/news.js` (348), `ui/news.selftest.js` (240), `test_news.py` (136) | 8 headlines rendered from the app's own context endpoint, source labelled *"built-in: decrypt.co, coindesk.com"*, first title real (*Why an AI Slowdown Could Collapse Under Commercial and US-China Pressure*) |

**What the workstreams found in the app** (recorded here because they matter more than the panels):

1. **`GET /api/status` does not exist** — it answers 404. The real route is
   `GET /api/control/engine/status` (which is also the route my phase-4b adoption had already been
   polling). My original brief named the wrong endpoint; the panel uses the right one.
2. **`GET /api/instruments` is not "your enabled instruments"** — with the engine stopped it returns the
   dashboard's own demo list (45 rows), and while running it returns the streaming set. The panel tags
   every row with the source the server reported and says so in its sub line, rather than dressing the
   demo up as a feed. (`GET /api/control/bootstrap` carries the literal enabled list — the obvious
   follow-up if "enabled instruments" is meant literally.)
3. **The engine status payload has no per-symbol volume** (symbol, price, ticks, candles, cum_delta,
   trade_phase, trade_direction) — so an engine-fed row shows `—` for volume.
4. **An unset `news_url` does not mean "no news"**: `atlas/context.py` falls back to its built-in public
   feeds (CoinDesk, Cointelegraph, Decrypt) and returns real headlines. The panel therefore labels them
   *built-in* and names the config key (`context.news_url`, set through the setup wizard's "Custom news
   feed"), reserving the literal "not configured" state for a genuinely sourceless server. Also:
   `stats.feeds` always lists the built-ins even while a custom feed is serving, so it must not be used
   to name the configured feed — the panel derives that from `context.news_url` plus each item's own
   `source` host.
5. **A real app defect, reported by the news workstream and structurally confirmed by me:** the setup
   wizard's **Skip** button posts the page's in-memory `S.config` back
   (`finishWizard({skip:true})` → `POST /api/control/engine/restart|start` with `S.config`), so a config
   changed elsewhere since page load is silently reverted — in the live run it flipped
   `context.news` back to `false`. Not fixed here; it is one 'Load before you save' change in `guide.js`
   and belongs in its own small pass.

**The 3 `client error:` lines in the sandbox log are mine, not the panels'**: timestamps 22:35:58–59,
i.e. the window when `watchlist.js`/`news.js` were wired into `index.html` before their files existed
(§13) — `failed to load` ×2 plus the downstream `Cannot set properties of null`. After the files
landed the same log has none, and both panels render.

**Still open:** Fundamentals and Options (phase 5's other two). Both need a data decision before a panel
is worth building — a fundamentals source, and a real options feed for Greeks/IV (dxFeed class). That
question is with the user; nothing was built speculatively.


### 24. 2026-09-15 late — Phase 5 complete: Options (Deribit) and Fundamentals (EDGAR + CoinGecko)

Nothing committed — HEAD `b2ff4ee`. Final gates, **all run by me on the wired tree**: full suite
**467 passed / 2 skipped**, `AUDIT CLEAN`, `options.selftest.js` 21 ok, `fundamentals.selftest.js` 18 ok,
`test_options.py` 27 passed, `test_fundamentals.py` 33 passed.

**Wiring applied in one pass** (the six hunks the Fundamentals workstream reported, plus the correction it
could not have known about): `index.html` nav item + section + script tag (both panels), `JS_FILES` for
both modules, and — the part that would otherwise have turned the audit red — the audit's hardcoded route
table now also scans `desktop/edgar.py`. The fundamentals router is mounted at **app level** in
`launcher.py` (a nested `include_router` inside the control router both breaks `test_live_bridge.py`'s
`{route.path for route in router.routes}` comprehension and inverts the URL, per the Options workstream's
own defect note; the Options panel's routes are plain `@router.get`s in `api.py` instead, which is why its
paths read `/api/control/deribit/…`).

**My own live render** (sandbox 8094, real network, then stopped): app boots 28 views / 29 nav, no error
banner. Options: 11 expiries, 21 strike rows, sub line *"polling 20s via the shared bus · BTCUSDT → BTC
16SEP26 · ±10 strikes around 76269 · 21 strike row(s), 42 quoted side(s)…"*. Fundamentals on BTCUSDT: the
CoinGecko branch — 5 rows, *"BTCUSDT · CoinGecko · Bitcoin · rank #1"*, first row `Rank #1`. The EDGAR
branch was verified live at the module level (Apple's real FY2025 10-K: revenue 416 161 000 000 USD, EPS
7.46, filed 2025-10-31) but not yet rendered in the DOM, because the sandbox's active symbol is crypto.

**Defects the workstreams found and fixed** (all pinned by their gates): the Options panel stuck on
"Loading…" when the active symbol has no chain (fixed in `rekey()`); Deribit lists **no SOL options** (the
brief's assumption was wrong — SOL is a recognised currency with an empty chain, a third honest state);
Deribit has no batch ticker endpoint, so the ladder is windowed ±10 strikes and pooled (≈2 req/s while
open, stated in the module header); `router.include_router` in FastAPI 0.141 breaks a pre-existing status
test; strike spacing is not uniform and the ladder never assumes a step; CoinGecko's ticker ≠ id
(POLUSDT → `polygon-ecosystem-token`, not the migrated `matic-network` husk that answers zero); EDGAR's
`fp: FY` is not a period length (90-day facts filed as FY must be dropped); a refusal is never cached as
an answer.

**Not verified, plainly:** neither panel has been run inside the frozen `.exe`/pywebview window; terminal
mode re-parenting of the two new sections is untested; the Options detail line did not surface in my own
probe click (the workstream's live run did show it with real Greeks — mark 0.0959 · IV 93.28 % · Δ +0.991 ·
Γ 0.000 · Θ −37.619 · V 0.807), which I put down to my selector rather than a gap, but I did not re-test it.


### 25. 2026-09-15 late — the seven-item sweep (what closed, what did not)

Gates at the end of this pass, all run by me: suite **473 passed / 2 skipped**, AUDIT CLEAN,
`watchlist.selftest.js` 15 ok, `shell.selftest.js` 22 ok, `options.selftest.js` 21 ok,
`fundamentals.selftest.js` 18 ok. HEAD `b2ff4ee`, nothing committed.

**Closed:**
1. **Wiring guards** (`test_wiring.py`, now 6 tests): every `/desktop` script tag must resolve to a file
   (vendor subfolders included), every `data-view` needs a nav item and a module that claims it, the four
   new panels must stay wired, `bus.js` must load before them, every panel must be in the audit's
   `JS_FILES`, and **every panel must scope its section lookup to `.view[data-view=…]`**. The last guard
   caught a real bug on its first run: `watchlist.js` matched the **nav button** (line 47) instead of its
   section (line 711), so in terminal mode — where no nav button is ever `.active` — the panel thought it
   was off-screen and paused. `platforms.js` had the same latent lookup; both are fixed.
3. **The wizard's stale-config write** (`guide.js`): it now snapshots the config at open and, before
   writing, re-reads the live config and merges three ways (keys the wizard edited win; every other key
   takes the live value). Proven live both ways: a `context.news=false` set by curl survived a real Skip
   click, while a key walked through the wizard (`context.news=true`) won over the live value.
2. The **Options detail line** is confirmed populated (a data cell click → mark 0.0976 · IV 90.30 % ·
   Δ +0.994 · Θ −25.656 · V 0.568 · OI 0, agreeing with the ticker route). The earlier "empty" reading was
   the probe's own fault: `#optionsBody tr` returns the `<thead>` row.
5. **Terminal-mode re-parenting**: five new panels in widgets, a second tab, away-and-back — every panel
   re-booted with no stuck "Loading…", bus channels 2 → 0 (hidden panels release) → 2, and the classic
   round-trip restored all 28 sections in the exact original order.
6. **The frozen app is rebuilt**: `dist/ModFlowOrderFlowAnalysisSuite/` (note the app name, not the old
   `OrderFlowAnalysisPro` folder, which is stale) now carries all four panels plus
   `data/bookmap_addon/ofap-bridge.jar`, the exe serves modules byte-identical to source, and a real
   window opened.
4. **The real pywebview window** shows both new panels with live data (Options: 21 strikes, real IV/Δ;
   Fundamentals: CoinGecko rank/mcap/supply) — but it cannot be driven programmatically: WebView2 exposes
   no CDP port here, and desktop clicks were denied by the approval gate, so no click-through in that
   window is verified.

**Open, with the fix known and the evidence recorded:**
* **Terminal mode leaves legacy panels empty** (measured on tape; the same mechanism applies to orderflow,
  depth, signals, performance, strategy, chart): those instances are built lazily by `ensurePanel()` in
  `ui.js`, which only the classic `showView` path calls — the terminal wrapper bypasses it. Calling
  `ensurePanel('tape')` by hand made the tape widget paint live prints immediately. The fix is one guarded
  call (`window.ensurePanel?.(view)`) at the point the shell mounts a section into a frame; it is NOT
  applied yet, because a blind insert into `shell.js` could not be verified in the time left.
* **`POST /api/control/config` writes over DEFAULTS, not as a patch** (`save_config` deep-merges
  `default_config()` with the body), so a partial post silently resets every key it omits. This also
  bounds the wizard fix above: its three-way merge is per **top-level** key, so a live edit to a different
  leaf inside a block the wizard touched is still reverted (`context.fear_greed` did). Worth a doc line in
  the API surface and, later, either a real PATCH or per-key merge.
* **Cosmetic, recorded not fixed:** the Fundamentals circulating-supply cell prints a literal
  `<span class="dim">of 21.00M max</span>` (a fragment built as text then escaped — `fundamentals.js`
  ~381-393), and the Options gamma shows `0.000` for a venue gamma of `1e-05` (3-decimal formatter).
* Step 7's optional items stand: the Watchlist's demo-list source when the engine is idle (use
  `/api/control/bootstrap` for the literal enabled list), per-panel bus adoption, and a commit boundary —
  67 dirty paths, HEAD still `b2ff4ee`.


### 26. 2026-09-15 — the last two fixes, applied and proven

**A. Legacy panels as terminal widgets** (`shell.js`, `buildFrame`): those instances are created lazily by
`ui.js ensurePanel()`, which only the classic `showView` path calls — the terminal wrapper never ran it, so
a tape/orderflow/depth/signals/performance/strategy/chart widget sat empty (measured: 0 children, `S.inst`
`[]`). A guarded `window.ensurePanel(view)` now runs once the section is in its frame (idempotent, so it is
a no-op for panels that build themselves from their observer). **Proven live**: after `openWidget('tape')`
the frame's container went 0 → 1 child carrying the tape's own *Min Size* scaffold, and a second legacy
panel (`depth`) built its instance the same way. Not re-measured per panel: orderflow, signals, performance,
strategy, chart — same mechanism, same call site.

**B. `POST /api/control/config` patches** (`config_store.merge_config` + `api.put_config`): the write merged
the body over the DEFAULTS, so a partial POST reset every key it omitted. **Proven live** on a sandbox:
after posting `{"search": {"default_view": "chart"}, "context": {"news": false, "fear_greed": false}}`, a
second post of `{"ui": {"banner_dismissed_alpaca": true}}` read back `view=chart, news=false,
fear_greed=false, banner=true` — before the fix the first three would have gone back to factory values.
`save_config` keeps its whole-block semantics **on purpose**: the layout delete path removes an entry by
writing the remaining block, and a disk-based merge would resurrect the deleted key (that is exactly how
`test_layouts.py::test_duplicate_rename_and_delete` failed on the first attempt at this). Reset is
unchanged. Pinned by two tests in `test_config_store.py`.

Gates after both: **475 passed / 2 skipped**, AUDIT CLEAN, `shell.selftest.js` 22 ok. HEAD `b2ff4ee`,
nothing committed.


### 27. 2026-09-15 — the three remaining fixes: two proven, one NOT fixed

Gates after this pass: **475 passed / 2 skipped**, AUDIT CLEAN, `watchlist.selftest.js` 15 ok,
`options.selftest.js` 21 ok, `fundamentals.selftest.js` 18 ok. HEAD `b2ff4ee`, nothing committed.

**Fixed and proven.**
* **Fundamentals supply cell** (`fundamentals.js`): the one value this panel builds as markup carries an
  explicit `r[3] === true` flag; everything else stays escaped. Live: the cell now holds
  `20.08M BTC <span class="dim">of 21.00M max</span>` — a real child element (`elementChildren: 1`), no
  literal tag in the text.
* **Options greeks** (`options.js fmtGreek`, shared by gamma/theta/vega/rho): a non-zero value below a
  milli-unit renders `n.toExponential(2)` instead of rounding to `0.000`, because "no gamma" and "1e-05
  gamma" are different statements. Pinned in `options.selftest.js` (`fmtGreek(0.00021) === '2.10e-4'`,
  `fmtGreek(1e-5) === '1.00e-5'`, exact zero still `'0.000'`). NOTE: the live click-through was **not**
  captured — the probe waited 6 s inside one `js()` call and the harness times out at ~5 s. The rule is
  test-pinned, not eyeballed.

**NOT fixed — stated plainly.** The watchlist's "configured instruments" rows do not appear.
* What is right: `config.instruments` really is the instrument **list** (50 objects after the test
  instrument was added), not a settings block with a `symbols` key — the reader now handles both shapes and
  was verified against the live bootstrap response.
* Correction, same session: the cause was the 2 s poll beat — `setInterval(() => { void loadStatus(); })`
  reloads only the engine status and never called `refresh()`, the helper's sole caller. The beat now runs
  `loadStatus → refreshPlaceholders → render`. Live re-check pending (the ZZZTEST recipe above); this
  paragraph replaces the "NOT fixed" verdict below, which was written before the loop was read.
* What failed: `configuredSymbols()` was never reached in practice. The live sandbox kept showing 45 demo
  rows with **zero** configured rows even after a configured instrument the demo list does not carry
  (`ZZZTEST`) was posted into the config — so the panel's poll path does not go through `refresh()`, which
  is the only caller of the new `refreshPlaceholders()`. The helper is therefore inert. Next step (one
  look, not a guess): find the actual poll loop in `watchlist.js`, call `refreshPlaceholders()` from it, and
  re-run the ZZZTEST check. Until then this is an open item, not a delivered one.


### 28. 2026-09-16 — the bus refactor, and the two delivery-layer defects it exposed

The refactor (child pass): 5 independent pollers across 4 modules collapsed onto **3 shared channels** —
CVD series 5000 ms (market-pressure + atlas.js), tape series 5000 ms (atlas-v2 + atlas.js trackers), engine
status 2000 ms (the shell + watchlist, which were the same URL asked twice at 60 req/min). Measured on the
wire, 45 s windows: CVD 27.8/min → 12.0/min, tape 26.7/min → 12.0/min, status 60.0/min → 30.0/min with one
channel and two subscribers. Everything else was deliberately left: unique-dataset pollers, DOM/UI timers,
or pairs whose URL params differ so they are different channel keys. New gates: `market-pressure.selftest.js`
(12 checks), `test_market_pressure.py` (8 tests).

**Defect it found, mine, fixed here — the worst kind: a silent freeze.**
`bus.js install()` never released a settled request (`inFlight.delete(key)` existed on the error and
non-JSON paths but not the success one), and `canon` drops cache-busters, so the first answer for a wrapped
URL stood in for that URL for the life of the page. With the shipped configuration
(`install(['/api/atlas/', …])` — four prefixes) a CVD panel counted 7 fetches while the server logged **0**,
and its stamp froze. Fixed: the key is released as the body lands; callers that joined while it was in
flight already hold the promise, so nobody is cut off. **Live now: `inFlightRequests` 0, fetches 19 → 37
across 13 s, channels answering.** Pinned by a new `bus.selftest.js` check (12 ok) — the old check pinned
only the concurrent case, so it would have kept passing through the freeze.

**Second defect, same pass — a closed widget kept polling.**
`shell.js releaseFrame()` returned the section to Classic but left `.active` on it: measured
`.active true, offsetParent null, 0x0, in no frame`, so every panel of that view — and now its bus
channel — kept polling for a view nobody was looking at. Fixed: the class is cleared on the return trip.
Live: heatmap widget before `{active: true, inFrame: true}` → after `{active: false, inFrame: false}`, and
the channel count falls with it.

**Third, cosmetic, left:** the status bar's bus chip repaints on shell events only, so it can lag a channel
that opens on a view switch.

Gates after all of it: **483 passed / 2 skipped**, AUDIT CLEAN, bus selftest 12 ok, shell 22 ok,
market-pressure 12 ok, watchlist 15 ok, options 21 ok, fundamentals 18 ok. HEAD `b2ff4ee`, nothing committed.

Still open from §27: the watchlist's configured-instrument rows were wired to the 2 s poll beat after that
note was written and have not been re-checked live (the ZZZTEST recipe is in §27).


### 29. 2026-09-16 — the bus chip lag (the "cosmetic" from §28)

Fixed, and it took three findings rather than one:
1. `bus.js` never announced channel transitions — it dispatched `ofap:bus` once at boot and nothing else, so
   no observer could know a channel had opened or closed. It now announces `open`/`close` with the channel
   key and the live counts (guarded: the module still loads where there is no document).
2. The first wiring of the shell's listener landed inside `applyTab()`, which does not run at boot — the
   listener was never registered until a tab switch. `watchBus()` is now idempotent (`S.busWatcher`) and is
   called from `paintStatus()`, which runs on the first paint.
3. The repaint was queued behind `requestAnimationFrame`, and in a headless page that callback never fired —
   the queue flag stayed set and the chip went permanently stale. The listener now paints directly; a
   channel transition happens a handful of times per view switch, so coalescing bought nothing and cost
   correctness.

Verified live on a sandbox with the page freshly loaded: chip `bus: 1 sub · 1 ch · 2 fetches (1 saved)` →
open the CVD view → `1 sub · 2 ch · 2 fetches` (telemetry: 2 channels) → back to Overview →
`1 ch · 8 fetches` (telemetry: 1 channel) → a terminal round-trip → `1 ch · 12 fetches`. The chip follows
the bus, not just shell events.

**Found while proving it, not fixed:** the chip's `sub` number and `telemetry().subscribers` disagree at the
same instant — measured chip `1 sub · 2 ch` while telemetry reported 3 subscribers. Two channels each with
listeners cannot hold one subscriber, so the bus's internal counter counts something else (channels with a
listener) than what `telemetry()` reports (subscriber references). One of the two is mis-named; worth a
one-line reconciliation so the number means one thing.

Gates: 483 passed / 2 skipped, AUDIT CLEAN, shell selftest 22 ok, bus 12 ok.


### 30. 2026-09-16 — the working tree is committed (local only, nothing pushed)

`master` moved off `b2ff4ee` for the first time, in seven commits grouped by area — not by phase, because
`api.py`, `ui.js` and `index.html` were each touched by several phases and a phase split would have needed
`git add -p` to leave a file half-staged. Nothing here is pushed: `origin` is
`github.com/mahmoud20138/OrderFlow-Analysis-Pro` (the original project), and the branch is 7 ahead of it.

  `4b142f1` docs: session handoff, terminal/Quantower plan and audit report                  (58 files)
  `639dd00` feat(desktop): terminal mode, panels, platform realm                             (76)
  `d848421` feat(data): Alpaca and DTC feeds, enums, Bookmap reader and add-on                 (9)
  `4776ac0` feat(atlas): analytics package and its gates                                      (23)
  `bd3cbd5` test: the suite, fixtures and testdata                                            (54)
  `a5d9909` chore(tooling): UI audit, exe packaging, workflows, assets                        (10)
  `e967d02` chore: earlier-session work in settings, dashboard, analytics and data            (15)

The last commit is the pre-existing uncommitted work from earlier sessions (~1,900 changed lines in
`config/settings.py`, `main.py`, `dashboard/`, `analytics/`, `data/`, README, CONTRIBUTING), kept in its
own commit so it stays separable from this work. Identity is repo-local: `ModdySwag
<ModdySwag@users.noreply.github.com>` — no real address, and nothing global was changed.

Verified after the last commit, against the committed tree: **483 passed / 2 skipped**, AUDIT CLEAN,
`git status` empty, and no `*.db`, `*.log`, `.env`, `dist/`, `build/`, `.venv/` or `__pycache__` in the
tracked files (largest tracked files are two docs screenshots and the vendored lightweight-charts bundle).

Open, unchanged by this: the chip's `sub` count vs `telemetry().subscribers` disagreement (§29), the
watchlist's configured-instrument rows (§27) and the two cosmetics in §25.


### 31. 2026-09-16 — report1.txt reconciled, and the upgrade plan written

The owner asked for a plan of action built from `report1.txt` (the audit comparing `ai prompt.txt` to the
build). It was re-verified against the tree before planning, because it was written before the engine view's
wiring landed and two of its three headline gaps no longer exist:

| report1 said | the tree says |
|---|---|
| no DOM tooltip panel consuming `state.hover` | `ofx-view.js:492` → `paintTip` (:401, `#ofxTip`) + `paintReadout` (:320, `#ofxReadout`, the full metric set) |
| no "snap to live" sparkline widget | `#ofxSnapFloat` + `#ofxSpark2` (`index.html:248`), `paintSpark` (`ofx-view.js:277`), shown in historical mode only, click = `snapToLive()` |
| no lambda control; no perf HUD | `#ofxLambda` (`index.html:230`); the stats line (`ofx-view.js:256`) carries frames · EMA · p95 · max · LOD · col width · levels |
| `footprint.js` looks dead — remove | it is `orderflow_system/dashboard/static/footprint.js`, still loaded by `index.html:764` and built by `ui.js ensurePanel('orderflow')` — the keep/retire call is sweep R7, not a delete |

What report1 had right and is still open: `hover()` costs O(prints + heat cells + bars) per mousemove
(`ofx.js:1778` — and `:1774` re-scans the whole depth matrix, `:1763` re-sums CVD from bar 0, neither of
which the audit saw); `cell.peak`'s flat 0.92 ghost (`:1150`); the stacked-zone projection and
imbalance-glow cosmetics; `carry_forward` has no on-screen indicator. One new compliance find:
`desktop/api.py:1525` is the only `hermes` match in source (non-negotiable #7).

Plan: **`docs/UPGRADE_ACTION_PLAN.md`** — P0 trust pass (the three unverified visuals, watchlist rows, bus
counter, sweep R2/R3, the hermes string), P1 the interaction canon and spec alignment (theme/token layer
first — `atlas.css` holds zero `--of-` tokens today), P2 measured performance, P3 backend/packaging/
deferred, each with its gate, the design principles the ordering follows, and the evidence appendix.
Gates at writing: 483 passed / 2 skipped, AUDIT CLEAN; selftests ofx 119, shell 22, bus 12, links 10,
watchlist 15, news 17, options 21, fundamentals 18, market-pressure 12, intent 7, study-api 45,
search-ops pass.


### 32. 2026-09-16 — the P0 trust pass from the upgrade plan (all six, with evidence)

Run on a sandbox (`ofap_p0_sandbox`, a copy of the §27 state so `ZZZTEST` is in its instrument list,
port 8093, engine live on Bybit BTCUSDT). Every line below is a measurement, and the gate block at the
end was run after all of it.

| P0 item | Result | Evidence |
|---|---|---|
| **P0-1** the three unverified visuals (§2) | **Seen** | *Stacked zone*: zoomed past the 54 px label gate, the draw-call capture holds `STACK 3L`, the per-bar band `rgba(86,214,255,0.12)` at 62×26 px and 11 projected row bands `rgba(64,224,255,0.18)`. *Thermal ramp*: palette stops `rgb(26,38,58) → rgb(96,70,58) → rgb(186,110,46) → rgb(232,176,84) → rgb(255,244,214)`; the same hottest cell (col 1, size 189) reads `255,236,187,179` on classic and `251,178,73,179` on thermal. *Trace line*: `#ofxTrace` at the cursor's price, tip and readout populated, note `on the ladder` with the row highlighted — and `outside the drawn ladder levels`, with no row, when 140 points away |
| **P0-1 exposed three defects, all fixed** | **Fixed** | (1) The ladder never emitted `data-price` — the attribute `ofx-view.js:461` queries — so no row could ever match, in any view (`orderbook.js`, pinned in `test_wiring.py`). (2) A class toggled by the consumer was wiped by the ladder's next rebuild; the highlight is now state the ladder re-applies in its own render (`setTrace`, verified still present after a poll). (3) `nearest(prices, null)` accepted any distance, so a cursor 41 points off a 15-level ladder read `on the ladder`; the match is bounded by one grid step now |
| **P0-2** watchlist configured rows (§27) | **Fixed, proven both ways** | Engine **stopped**: 45 demo rows + 7 configured rows, incl. `ZZZTEST — ticks — vol — Δ — — configured`, sub line `the server is answering with its demo list, not your feed · 7 configured instrument(s) with no feed`. Engine **running**: 1 row, source `engine`, 0 configured rows. Root cause, measured: `refreshPlaceholders()` was reached only from `refresh()` and the no-bus timer — never from the bus beat — and the bootstrap read called a bare global `api()` that exists only inside a real page, so the read had never worked under test. Selftest 15 → 17 |
| **P0-3** bus chip vs telemetry (§29) | **Fixed** | `announce()` dispatched `subscribers: state.subscribers` — a field this module has never had, so every `ofap:bus` event carried `undefined`, and the one number nobody could verify was the one that appeared to disagree. One `subscriberCount()` now feeds `telemetry()` and the event, and the open event fires after the join. Live: event `{action:'open', channels:2, subscribers:2}`; chip, `summary()` and `telemetry()` agree on subscribers and channels at the same instant. (The chip's *fetch* count still lags between repaints — it is a snapshot, by design.) Selftest 12 → 13 |
| **P0-4** order-book integrity (sweep R3) | **Implemented** | Bybit's `u` is tracked per symbol: duplicates and reorders are dropped, a gap marks the book stale, drops the deltas that follow and re-subscribes for a snapshot (`OrderbookSnapshot.stale`, `book_health()`, `live_status()["endpoints"]["orderbook"] == "stale"`). 4 new tests (`test_book_integrity.py`). Live: 25 s of engine, `orderbook: live`, 0 gap warnings, 684 ticks — no false staleness |
| **P0-5** broadcast backpressure (sweep R2) | **Implemented** | Per-client bounded queue + writer task; nothing is written under the manager's lock; a full queue trims the oldest for `tick/orderbook/delta/stats` only and never for `signal`; a write that times out drops the client. 5 new tests (`test_websocket_backpressure.py`). Live: WS accepted, client count 1, no timeouts or tracebacks in the log |
| **P0-6** `hermes` in source (non-negotiable #7) | **Fixed** | `desktop/api.py:1525` comment reworded; `grep -ri hermes` over source is 0 matches. (`dist/` matches are CPython's own `unicodedata.pyd` — noted so the gate is not misread.) |

Gates after everything: **493 passed / 2 skipped**, AUDIT CLEAN, `node --check` on every touched JS,
selftests ofx 119 · shell 22 · bus 13 · links 10 · watchlist 17 · news 17 · options 21 · fundamentals 18 ·
market-pressure 12 · intent 7 · study-api 45 · search-ops pass; no `client error:` lines in the sandbox
log. New tests: `test_book_integrity.py` (4), `test_websocket_backpressure.py` (5), one wiring guard.

What the pass did **not** cover, stated plainly: the stacked-zone band was seen at one zoom level (not
across zoom/resize/symbol change); the tape's scroll across a rebuild and 4K at Windows 150 % are still
unverified (§2), and they were not part of P0. The `stale` state has not been exercised against a real
venue gap — the unit tests drive the handler, the live run shows no false positives.

Next per the plan: **P1-1, the theme/token layer** (its grep gate is cheap and every colour decision
below it needs the tokens to exist).


### 33. 2026-09-16 — P1-1: the theme and token layer (the brief's gate at zero)

Workstream A of the agent brief, delivered as one pass.

**What landed**

- **One token block** (`atlas.css`): ~110 tokens declared as rgb triples (`--of-bg-rgb: 10,14,22`) with
  the solid form beside each (`--of-bg: rgb(var(--of-bg-rgb))`), because the shell leans on translucent
  overlays and `rgba(var(--of-steel-rgb),.35)` themes while a hard-coded `rgba(120,150,190,.35)` cannot.
- **Every raw colour in the shell converted onto it** — 117 hex literals and ~170 `rgba()` literals
  across `atlas.css`, `ui.css` and `modules.css`. ui.css's own small token block became an alias block
  (`--bg-panel: var(--of-surface)`, …) so the ~1000 lines of existing rules became theme-aware without
  being rewritten. A script did the conversion and aborts on any unmapped colour, so nothing was
  silently missed.
- **`themes/`**: `dark.css` (the anchor), `light.css`, `contrast.css`, `accents.css` (the eight Windows
  accents — cobalt, teal, green, lime, amber, orange, magenta, violet), `density.css`
  (comfortable 32 / compact 26 / dense 22, all on `--of-row-h`; the row rules read the token, so a
  density is a number, not a rewrite).
- **`theme.js`** + an inline `<head>` script: the appearance is `data-theme` / `data-accent` /
  `data-density` on `<html>`. The config (`ui.theme`, `ui.accent`, `ui.density`, clamped on write) is
  the record; localStorage is only the **pre-paint mirror**, so the first paint is already the right
  theme and the config wins where they disagree (verified below).
- **Settings → Appearance**: three selects, wired through the intent arbiter's write queue, so a user
  flipping through them writes once.
- Guards: `test_wiring.py` gains the appearance guard and *the raw-colour guard* (the brief's grep as a
  test); `test_config_store.py` pins the three defaults and their clamps; `audit_ui_refs.py` audits
  `theme.js` with every other module.

**The brief's gate** — `grep -nE '#[0-9a-fA-F]{3,8}\b' atlas.css | grep -v -- '--of-'` → **0 lines**.
Also 0 for `ui.css`, `modules.css` and all five theme files.

**Measured live** (sandbox 8093; screenshots in `docs/screenshots/p11-theme-{dark,light}-{1024x640,2560x1440}.png`):

| state | body bg | ink | accent | `--of-row-h` | nav row | statusbar | doc overflow |
|---|---|---|---|---|---|---|---|
| dark (default) | rgb(10,14,22) | rgb(233,238,248) | rgb(79,140,255) | 32px | 32px | visible | 0 |
| light | rgb(242,245,250) | rgb(20,26,38) | rgb(79,140,255) | 32px | 32px | visible | 0 |
| light + dense | rgb(242,245,250) | rgb(20,26,38) | rgb(79,140,255) | 22px | 22px | visible | 0 |
| light + compact | rgb(242,245,250) | rgb(20,26,38) | rgb(79,140,255) | 26px | 26px | visible | 0 |
| light + dense + magenta | rgb(242,245,250) | rgb(20,26,38) | rgb(216,0,115) | 22px | 22px | visible | 0 |
| contrast | rgb(0,0,0) | rgb(255,255,255) | rgb(216,0,115) | 32px | 32px | visible | 0 |

The dark default renders exactly as it did before the pass (body bg `rgb(10,14,22)`, ink
`rgb(233,238,248)`) — a token pass that moves no pixel. At **1024×640** and **2560×1440**: document
overflow 0, status bar in view (41px, wrapped, at the small size), rail fills the height, 0
`client error:` lines in the log. Config-wins proof: with the localStorage mirror deleted and the page
reloaded, the config's `light`/`teal` came up (`source: 'config'`).

**Two decisions, on the record**

1. **The chart canvases keep their dark ground in the light shell.** The engine's palette
   (`ofx.js math.theme`) is drawn light-on-dark — grid, labels and ramps would be unreadable on a light
   stage. Re-theming the canvas palette is expression work (P1-8), not a token swap; the light shell
   themes the chrome, the panels and the readouts.
2. **The config stays the record.** `config_store` says browser storage is never the source of truth;
   that holds — the mirror never wins, it only paints first.

Gates after the pass: **496 passed / 2 skipped**, AUDIT CLEAN, `node --check` on every module, and all
twelve selftests unchanged (ofx 119 · shell 22 · bus 13 · links 10 · watchlist 17 · news 17 ·
options 21 · fundamentals 18 · market-pressure 12 · intent 7 · study-api 45 · search-ops).

Not covered, plainly: the engine's canvas palette is still its own dark set (decision 1); the
colour-blind ramps are P1-8; and the light shell has been looked at on the two sizes above only.

Next: **P1-2, the cursor-link spine** — one hover lighting the profile, CVD, depth, tape and imbalance
strip at once, surviving repaint, resize and a symbol switch.


---

## §34 — P1-2: the cursor spine adopted by six panels (2026-09-16)

**What this closes.** P1-2 asked for one hover lighting the profile, CVD, depth, tape and imbalance at
once, surviving repaint, resize and a symbol switch. The store (`cursor-link.js`) existed; what was
missing was *adoption* — only the engine published, and only the ladder listened.

**The module now carries the whole contract.** `move(price, timeMs, source)` / `clear(source)` /
`set` / `select` / `subscribe(fn) → unsubscribe` / `nearest(prices, tol)` / `step(prices)` /
`text()` / `badge(host)`, one `state` of `{price, timeMs, source, selection, at}`. Two of those are
new and both matter:

* **`unsubscribe`** — panels subscribe for their lifetime and a panel torn down in terminal mode has
  to let go; the old `subscribe` returned the callback and there was no way out.
* **`badge(host)`** — one badge element per host, driven by the one store, so six panels cannot
  disagree about what the cursor is on. The badge reads `price · time` with `tabular-nums`, is
  silent (`— · —`) when the cursor is clear, and takes the trace token's colour when it is not.

A field the caller did not mention is *not* a change: `move()` carries no `selection`, and treating
that `undefined` as "cleared" woke every panel on every mouse move (caught by the new selftest).

**Six panels, one price.**

| Panel | Publishes | Follows |
|---|---|---|
| Heatmap (`heatmap-pro.js`) | level + bucket under the pointer; clears on leave | draws the shared level as a line + price tag at both edges; repaints only when the drawn level changed |
| Depth ladder (`orderbook.js`) | the rung under the pointer | `setTrace(nearest)` — now with an early-out on an unchanged level |
| Tape (`tape.js`) | the print under the pointer (price + time) | marks rows at the cursor's price; rows carry `data-price`/`data-time`; re-applied on every insert, skipping the pass when the level has not moved |
| Profile (`atlas.js`) | — | marks TPO rows at the cursor's price; re-applied after each rebuild |
| Engine (`ofx.js` / `ofx-view.js`) | already did | already did; now carries the badge |
| CVD / trackers / heatmap / profile heads | — | badge |

**Script order is a build detail, not behaviour.** `atlas.js` and `heatmap-pro.js` load *before*
`cursor-link.js` in `index.html`, so their subscriptions and badges were silently skipped (found
live: 4 badges instead of 8). Both now wait for the module (`whenCursorReady`), and the live pass
shows 8/8.

**The gate, measured.** Hovering the heatmap canvas with a real pointer event:

* at **76332.12** — the engine's readout `cursor 76332.12 · on the ladder`; the ladder rung at
  `76332` traced; **10** tape rows marked (76332.3, 76332.2, 76332.2 …); four badges reading
  `76332.12 · 02:05:02`.
* at **76398.84** — **9** profile rows marked (76399.3 … 76398.4), `8/8` badges agreeing on one text;
  the engine says `outside the drawn ladder levels`, which is true — the ladder draws ~15 levels
  around the mid, the profile's published bracket is 76388.4–76411.6, and a panel that is not
  showing the level says so instead of inventing a match.
* Persistence: the same marks and the same price survived a **1366×900** resize and a forced
  `loadMarketProfile()` rebuild (both panels re-derive the mark from the store — canon #3).

Screenshot: `docs/screenshots/p12-cursor-spine.png` (the map carrying the shared level + badge).

**Decisions on the record**

1. **The cursor is transient; the pointer leaving the owning panel clears its claim.** Verified: a
   view switch away from the heatmap leaves every badge at `— · —` rather than a stale level. A
   *sticky* level (park it and walk to the ladder) is a selection, and that is P1-3's click model —
   two different intents should not share one state.
2. **A panel marks only what it draws.** Out-of-window hovers produce an explicit "outside the drawn
   ladder levels" note, not a nearest-row fudge.

**Not covered, plainly.** The CVD canvas and the imbalance strip carry the badge but no drawn cursor
line yet (they need the series→time index mapping, which belongs with P1-3's selection maths); the
sandbox has one symbol, so the **symbol-switch** half of the gate is unproven; and the terminal-mode
grid overlapped frames in the sandbox layout, which is why the four-panels-at-once pass was measured
in a 6-widget composition and the visual record is the classic view.

Gates after the pass: **496 passed / 2 skipped**, AUDIT CLEAN (now auditing `cursor-link.js` too),
`node --check` on every module, and all **thirteen** selftests green — the new `cursor-link` one at
**6 ok**, ofx 119 · shell 22 · bus 13 · links 10 · watchlist 17 · news 17 · options 21 ·
fundamentals 18 · market-pressure 12 · intent 7 · study-api 45.

Next: **P1-3, selection is measurement everywhere** — a drag over bars, a level, a time range or
markers yields the statistics strip, with the `selection` slot that P1-2 put in the store.


---

## §35 — P1-3: a selection on the engine is a measurement (2026-09-16)

**What this closes.** P1-3 asked for a drag over bars, a level, a time range or markers to yield the
statistics strip and an export, with markers remembered per symbol. The heatmap already had the
mechanism; the engine had none, and markers were session-only.

**The gesture.** Shift+drag on the engine stage boxes a time × price region. A plain drag still pans,
so nothing existing changed; the box is drawn on the live layer (`drawSelection`, above the crosshair
HUD), so it survives every repaint and camera move, and the outside dims rather than hides.

**The arithmetic is pure and pinned.** `math.selectionStats({bars, levels, prints, i0, i1, p0, p1})`
does the sums — volume, delta, buy/sell, prints (count + size), VWAP by size, largest trade with its
price, and the resting-depth change (last bar minus first bar, in the band). `math.selectionRange`
clips *and* orders the two cursor positions. Both are selftested in Node: the ofx selftest went
**119 → 134** checks. `OFX.selection()`, `OFX.selectionStats()` and `OFX.clearSelection()` are the
module's own surface; `legend()` does not carry them (the first attempt anchored on the wrong
`return { symbol: state.symbol,` and the methods landed on the legend object — caught by probing the
page, not by reading the diff).

**The strip and the file.** `ofx-view.js` paints `#ofxSelFloat` — its own line beside the stage, so a
hover repaint cannot wipe it — with volume, delta, buy/sell, prints, VWAP, largest and the resting
change, plus `Export CSV` and `Clear`. The export POSTs `/api/control/export/save` and the path the
server returns is printed on the strip's own note line. The strip is `pointer-events: none` with
`pointer-events: auto` on its two buttons: a measurement readout must not eat the gesture that makes
the next one (found live — the strip, sitting over the stage's bottom-left, blocked re-selection
through it).

**The gate, measured.** Shift+drag over the traded band on live Bybit data: a 4-bar selection at
76346.11–76461.95 read **volume 86.39, delta +14.58, buy/sell 50.48/35.91, resting +4.83**, and the
file landed on disk under the sandbox's exports folder —
`ofx-selection-BTCUSDT-20260915T165000.csv`, 22 lines: a header block (symbol, window, price band,
each figure, exported stamp) then one row per bar (ts, iso, OHLC, volume, delta) and a prints section.
A second export from the first pass (164900) is there too. Screenshot:
`docs/screenshots/p13-engine-selection.png`.

**The selection rides the shared cursor.** `OFAPCURSOR.select({t0, t1, p0, p1, bars})` — the slot P1-2
put in the store — so any panel can answer the window without knowing the engine exists.
`publish()` now distinguishes *not mentioned* from *explicit null*: `select()` carries no price, and
the old comparison treated that absence as "cleared", which would have wiped the cursor every panel
was reading. Pinned in `cursor-link.selftest.js` (now **7 ok**).

**Two defects found live, both fixed in the pass.**

1. **A one-sided index clamp.** Dragging from mid-stage to the right edge resolved to `i0 = 11,
   i1 = 4` — the start index was clamped only at 0, the end index only at `bars.length - 1`. An
   inverted range reads as "the strip measures nothing". `math.selectionRange` now clips both ends
   and orders the pair; five selftest checks cover past-the-edge, reversed, negative and empty-data
   drags.
2. **The strip blocked its own gestures** (above).

**A token read that should have been a triple.** `--of-trace`/`--of-trace-2` exist only as `-rgb`
triples, so `color: var(--of-trace-2)` on the badge was invalid at computed-value time (it fell back
to inherited ink) and the heatmap's canvas cursor line never left its hard-coded fallback. Both now
build the colour from the triple.

**Markers are remembered per symbol.** New store block `markers` (`{SYM: {markers: [{price, bucket,
size, note}]}}`), sanitised in `config_store` (price finite and positive, bucket/size finite, note ≤
120 chars, 500 per symbol, an empty list leaves no slot, the key upper-cased and clamped) behind
`GET/POST /api/control/markers`; the route answers with the block the store *accepted*. The panel
loads them once per symbol on its own poll and saves on mark/clear, and a stored row (data space,
never pixels) is placed back on the map by a **bounded** nearest — a marker whose price is outside the
drawn rows is not pinned to the edge row pretending to be there.

**`window.prompt` is gone from the mark action.** The packaged WebView is not guaranteed to render
one, and a Mark button that silently does nothing is worse than no button; the note is now a field in
the pro toolbar (cleared after each mark), with a `clear markers` button beside it.

Measured live: `POST /api/control/markers` stored the valid row and dropped a junk price; the panel
restored **2** rows after a reload — the one inside the drawn range placed at y=121, the one 67 points
outside it left unplaced and honest.

**Not covered, plainly.** The plan's "extend it to walls" half is not done: the heatmap's region
stats and CSV still carry cells and markers, not the fresh-walls table (**open**). The tape buffer
holds only the last few seconds while the footprint payload publishes closed bars, so a selection over
closed bars legitimately holds no prints — the strip now names that on its own line ("tape buffer
02:24:54–02:24:55 is outside the selected window (closed bars only)") instead of leaving a dash
that reads as a bug. The CVD canvas and the imbalance strip still carry the badge without a drawn
cursor line, and the symbol-switch half of P1-2's gate remains unproven (one symbol in the sandbox).

Gates after the pass: **504 passed / 2 skipped** (`test_markers.py` adds 8), AUDIT CLEAN, ofx selftest
**134 ok**, cursor-link selftest **7 ok**, every touched JS parses.

Next: **P1-4, strips — keyboard stepping and click-to-locate completion** (brief C).


---

## §36 — P1-4: the reader's hands on a strip (2026-09-16)

**What this closes.** `strips.js` could hold a reader's place but not move it, and a print could not
be acted on. Now the strips have keys and a locate.

**Keys.** ArrowUp/ArrowDown step one row (measured 24 px on the tape), PageUp/PageDown a screenful,
Home/End jump to the newest/oldest end. The handler is a document-level capture listener guarded like
the shell's own hotkeys (never while a field has focus; only when a strip is hovered or the event came
from inside one), and it `preventDefault`s what it uses. **No Escape binding on purpose**: `shell.js`
owns that key (menus, restoring from maximise), and a strip stealing it would close the wrong thing —
the release paths are the chip's own click and Home. Stepping engages the hold deliberately, so the
chip now shows even with nothing new to count ("↑ prints held · jump to newest"): a keystroke that
looked like it did nothing was worse.

**Pause on hover.** The gate's phrase, and it did not exist: a fast tape kept pulling rows out from
under a pointer parked on them — the same jump the module exists to prevent, one gesture earlier. While
the pointer is on a strip the follow branch counts arrivals and leaves the rows alone; when the pointer
leaves, a reader who never scrolled resumes following (their hover was transient) and a reader who had
scrolled keeps their place and their chip.

**Click-to-locate.** A click on any row carrying `data-time`/`data-price` publishes that print to the
shared cursor (source `locate`) and calls `OFX.seekToTime()` — the engine's new viewport seek, which
centres the bar containing that moment, clamps a live print to the newest drawn bar, and returns null
for a moment older than the session rather than inventing a place. The click also releases the hold:
the reader has picked the line they were reading.

**Three defects found live, and this is the interesting part of the phase.**

1. **"On the newest line" was measured in pixels, not rows.** `NEAR_BOTTOM_PX = 28` against a 24 px
   row meant a single ArrowDown step still read as "at the end": `step()` released the hold it had just
   engaged and the next arriving print followed, snapping the reader back by the very keystroke they
   used to escape. Measured: three steps landed at 48 px instead of 72. The epsilon is now at most half
   a row (`nearEnd()`), in both the scroll handler and the step.
2. **A scroll event decided against a re-resolved anchor, not its own scroller.** The tape's tbody is
   emptied for a frame while its rows rebuild; `scrollerOf()` then walked up to the PARENT and the
   parent's offset (0) read as "the reader is on the newest line", silently releasing the hold. The
   anchor is now sticky (`keepScroller()`: keep it while it is still the strip's own node).
   Both were found with a property trap on the strip's state that recorded a stack on every `held`
   transition — the stack pointed at the exact line, twice, after guessing had failed.
3. **The tape had its own auto-scroll and it fought the strip.** `tape.js` pins `scrollTop = 0` on
   every render and every batch ("pinned to the newest print"), which released every hold the strip
   engaged. Two owners of one offset. The tape now asks `OFAPSTRIPS.holds(el)` first and leaves the
   offset alone while a reader is parked; the strip's chip is the way back. (Same family as the
   scroll-anchoring fight recorded in the skill — the offset belongs to whoever the reader is
   interacting with.)

**The gate, measured live.** Hover the tape (spin paused, rows steady while prints arrive), two to
three ArrowDown steps → `top` 72 px, `held: true`, `pending: 1` after five seconds of live arrivals,
chip shown ("↑ 1 print · jump to newest"), `OFAPSTRIPS.holding()` 1, and the status chip reads
`✋ held — feed live · 1 tick/s · 1 strip holding your place`. A real click on a print row →
`locate: {price: 76223.9, time: 1789492506772, bar: 9, reached: 2}`, the cursor took that price and
time (`source: 'locate'`), the engine's viewport moved to bar 9, and the strip cleared: chip hidden,
`holding()` 0, offset back to 0. Screenshot: `docs/screenshots/p14-strip-held.png` (the held tape with
the located print marked and the status chip naming the hold).

**Files.** `strips.js` (keys, hover-pause, locate, the held chip, `holds()`, `math.stepTarget`),
`strips.selftest.js` (new: 9 checks on the step arithmetic and the ends), `test_strips.py` (new gate:
selftest green, registered with the audit, renderer-agnostic, no Escape binding, typing guard present),
`ofx.js` (`seekToTime`), `tape.js` (the ownership guard), `atlas.css` (the held chip).

**Not covered, plainly.** The locate path seeks the engine when its module is loaded, whatever view is
on screen; a strip whose rows carry no `data-time` (alerts, the log) has nothing to locate and says
nothing — the wiring for those is theirs to add. Stepping has been exercised on the tape only, and the
"one row" step assumes rows of a uniform height (a wrapped row steps by the first row's height).

Gates after the pass: **508 passed / 2 skipped** (`test_strips.py` adds 7), AUDIT CLEAN (now auditing
`strips.js`), strips selftest **9 ok**, ofx **134 ok**, cursor-link **7 ok**, all twelve others
unchanged, every touched JS parses.

Next: **P1-5, spec-alignment cosmetics redesigned as token-driven feedback** (ghost brightness by size,
imbalance-cell glow, and the rest of report1's minor list, each re-argued rather than copied).


---

## §37 — P1-5: the cosmetics, as feedback (2026-09-16)

Five items from report1's minor lists, each re-argued before it was built. The gate for the phase is a
live reading per item, so every one below carries what the running engine actually painted.

**1. Ghost brightness by size.** The heat pass stamped every live cell `peak = 0.92`, so a level that
was pulled left the same ghost whether it had held a wall or a rounding error — the picture asserted
all liquidity was equal. `math.peakAlpha(size, scale)` maps a cell's own density bucket (the same
`log1p` mapping `heatPalette` uses for colour) onto the ghost's starting alpha: floor 0.32, top 0.92,
`sqrt` between them. Live cells keep their full-strength stamp — the pass moved no live pixel.
Measured on live Bybit depth: 252 painted cells spread over **0.867–0.920 across 6 distinct peaks**
(under the old code: 1 distinct value), and a controlled pull on the real renderer — the window's
heaviest cell (153.43) peaked at 0.920 and a mid cell (69.2) at 0.871 — left two ghosts at exactly
those alphas. Selftested (5 checks): monotone in size, never below the floor or above the top, a
nonsense scale is 1 rather than NaN.

**2. Imbalance-cell glow, and the POC keeps the strong one.** The imbalance tint was a flat
`rgba(imBuy, .18)` fill on the text half. It now goes through `glowCell()`, which adds a glow in the
*imbalance* colour at a third of the POC's radius (`glowRadius × 0.35`, floor 3 px) — accent stays
scarce (§3.3), and the engine's own legend colour table supplies the colour. Measured live with a trap
on `fillRect`: **27 glowed cells in one window — 21 sell, 6 buy — all at blur 3.0**, against the POC's
`glowRadius` of **7.2** on the same stage. The screenshot shows the matrix still readable, which was
the clause that would have cancelled the item.

**3. The stacked-zone projection reads across the chart.** The projected bands went from
`0.10 + min(0.10, count·0.02)` to `0.12 + min(0.12, count·0.025)`, and each distinct zone now carries a
right-edge label where the band *ends* — "BUY 3L projected" / "SELL 4L projected" — deduped per pass so
the per-bar draw does not stack the same words. Measured live with a trap on `fillText`: the label
painted on every base pass in the window (`SELL 4L projected`, 3 passes), which is what "once per
distinct zone per pass" means.

**4. `carry_forward` is on the panel.** The depth map carries liquidity forward between windows; the
payload has said so all along (`carry_forward`) and nothing displayed it. The view now puts the flag on
the engine's state and its notes line: **"ghost liquidity carried forward — levels that left the drawn
window are still shown"**, measured live after setting `atlas.heatmap.carry_forward: true` in the
sandbox config and reading the panel's own note text — a mark whose explanation is only in the code is
a lie of omission (§3.6).

**5. The hidden-block count sits beside the min-block floor.** The engine already tallied
`blocksFiltered`; the count now prints next to the control that causes it (`#ofxHiddenBlocks`), on the
existing one-second stats tick: **empty at floor 0** (a filter that hides nothing says nothing),
**"nothing hidden"** with the floor at 5 and nothing in view below it, and it turns warning-coloured
with "N hidden" and a tooltip naming the floor when the filter *is* hiding executions. Measured live at
both floors; visible in the screenshot beside the field.

**A config-shape finding, on the record.** The engine's hub reads its depth-map knobs from
`atlas.heatmap` (`engine.py` hands it the atlas subtree), while `config_store`'s defaults also declare a
top-level `heatmap` block for the GUI. Setting `carry_forward` at the top level does nothing —
measured: the payload stayed `false` through an engine restart until the flag went in under
`atlas.heatmap`. Worth knowing before the next depth-map knob is added; the sandbox was cleaned back
to its original state afterwards (stray key removed, flag removed).

Gates: **ofx selftest 139 ok** (five new `peakAlpha` checks), pytest **508 passed / 2 skipped**,
AUDIT CLEAN (the new `ofxHiddenBlocks` id is referenced by the view and exists in `index.html`),
`node --check` on every touched module.

Next: **P1-6, the heatmap answers duration** — `wall_age` / `wall_durations()` as a held-time column,
an optional wall-age tint, and the 74/22 px plot insets promoted to one shared constant.
