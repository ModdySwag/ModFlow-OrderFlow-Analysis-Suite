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


---

## §38 — P1-6: the heatmap answers duration (2026-09-16)

**What this closes.** The depth map knew how long each level had HELD (`wall_durations()`, and a
`wall_age` alert kind on the same streak) and the payload carried none of it, so a level defended for
ten minutes looked exactly like one that appeared a second ago — the map could only answer *how much*.

**One join, three readers.** `atlas/api.py` gains `attach_wall_ages(snapshot, heatmap)`: the walls the
map draws, each with `held_ms`, plus `wall_age_ms` (the engine's own threshold — the UI says "held"
with the engine's definition rather than inventing one). The walls table, the cursor readout and the
age tint all read that one shape.

**Where it shows.**

* **Fresh-walls table** — a fourth column, "Held" (`1.3 min`, `47 s`, `—` when the streak restarted).
* **The cursor readout** — `held 1.2 min` under the rest of the level's numbers, with `(wall)` once it
  has passed the engine's threshold. Nearest drawn price within one step, bounded like every other
  nearest in this app.
* **The age tint** — an optional `wall age` switch in the heat view's overlay row (remembered in the
  view's own storage, off by default): a warm wash on the rows whose level has held past the
  threshold, `0.10` at 2 min rising to `0.22` at 10 min, warm rather than one of the ramp's own
  colours so it cannot be read as density.
* **One shared inset constant** — the 74/22 px plot insets were written twice (the map's `axisR/axisB`
  and the overlay's `geom()`); they are now `HEAT_INSET` in `atlas.js`, exposed as
  `window.OFAPHEAT_INSET`, and `heatmap-pro` reads the map's numbers with the old ones only as a
  fallback. A second copy is how a map and its overlay drift apart.

**Two `window.prompt` sites removed on the way (the P1-3 lesson, same file).** The alert tolerance and
the hold-alert's minutes were asked for with `window.prompt`, which the packaged WebView is not
guaranteed to render — a button that silently does nothing. Both are fields beside the alert buttons
now (empty = the default: two drawn price steps, two minutes), and the tooltips name the defaults.
One defect in my own first cut, found by running it: an empty field read as `Number('') === 0`, which
created a rule with `at_tol: 0` (fires only at the exact cent) — an empty field now means "use the
default". Three more `window.prompt` sites remain outside this phase (the drawing text tool at
`drawings.js:365,417` and the workspace-name prompt at `menubar.js:557`); they need their own in-place
affordances and are **open**.

**The gate, measured.**

* The payload's walls carry `held_ms` and `wall_age_ms: 120000` (curl), and the table rendered real
  holds on live data: `1.3 min`, `1.7 min`, `47 s` across three walls in one window.
* The cursor readout on a held wall read `held 1.2 min`.
* The tint's arithmetic is exact (`0` below the floor, `0.10` at 120 s, `0.145` at 300 s, `0.22` at
  600 s and above), and on the real canvas a wall given a 5-minute hold painted `rgb(255,193,117)` on
  its own row while six rows away stayed `rgb(0,0,0)`.
* The alert: created from the selected level through the new fields —
  `hm-BTCUSDT-77148_72-101555`, kind `wall_age`, `{min_size: 0.504, at_price: 77148.72, at_tol: 3.96,
  min_age_s: 120}`, channel `ui` — "fires only at that level", and the scope is enforced by the
  evaluator generically (`atlas/alerts.py:179-182`) and pinned in `test_wall_age.py`
  (`test_rule_bound_to_a_price_fires_only_there`: 100.0 fires, 103.0 does not, 100.4 does, no price
  means no evidence). It was then deleted through the route (200) and the list read back: 16 rules, no
  `hm-` left.
* **A live 2-minute hold did happen, and the engine said so.** A 20 s poller caught the engine's own
  event: `{kind: wall_age, price: 76800.0, size: 3.538, detail: "held 2.4 min", direction: ask}`. Two
  honest notes about it: the payload's `events` list carries the last 120 events (a couple of minutes
  of pull/stack churn), so a wall_age event rolls out of it quickly — a later query shows none, which
  is why the poller existed; and the Held *column* covers the 12 heaviest walls (`wall_prices(top=12)`),
  so a held level outside that set shows its age in the engine's event list rather than the table
  (76800.0 was not in the top 12 at the time). The level-bound rule did not fire for that unrelated
  event (0 alerts matching the rule), which is the "at that level only" half; its own firing at its own
  level was not observed while it existed, so that last step rests on the evaluator's pinned scope
  rather than a live alert.

Gates: pytest **509 passed / 2 skipped** (the new `test_wall_ages_ride_the_payload_the_map_draws`),
AUDIT CLEAN, `node --check` on every touched module.

Next: **P1-7, alerts — manage, scope and read like sentences** (rule editor, every rule rendered with
its scope in words, a "created from heatmap" filter, and a log that names symbol, level, size and why).


## §39 — P1-7 recon: where the alerts stand, and what to build

Scoped from the tree on 2026-09-16, read-only: no code changed for this entry. It exists so the next
session starts from the measurements instead of re-deriving them.

**What exists now.** The Alerts view is `index.html:522-542` (view `alerts`), rendered by `atlas.js`
(~534-590) with `atlas-v2.js` doing the persisted-history card (`loadHistory`, ~170). Four routes, all
real: `GET /api/atlas/alerts?limit&symbol` → `{alerts, stats}`; `POST /api/atlas/alerts/clear`;
`GET /api/atlas/alert-rules` → `{rules}`; `POST /api/atlas/alert-rules` (upsert by `id`) and
`DELETE /api/atlas/alert-rules/{id}` (`atlas/api.py:445-470`). The engine side is
`atlas/alerts.py`: `AlertRule {id, name, kind, params, enabled, cooldown_s, channels, fired,
last_fired_ms}` and `Alert {rule_id, name, kind, symbol, ts_ms, message, severity, data, channels}`,
with `evaluate()` checking every enabled rule of that kind, the generic level scope at
`alerts.py:179-182` (`at_price`/`at_tol`), per-rule cooldown, and `_message()` (line ~320) writing one
English sentence per kind with `{symbol}: {rule.name}` as the fallback.

**Kinds the engine emits** (from `_message()`'s branches plus the severity list): `big_trade`,
`block_trade`, `sweep`, `stop_run`, `iceberg`, `speed_spike`, `cvd_divergence`, `heat_pull`,
`heat_stack`, `vwap_cross`, `depth_execution`, `depth_refill`, `stacked_imbalance`, `intent_pressure`,
`pulled_size`, `trapped_traders`, and `wall_age` (from the depth map — the kind the heatmap's level
alerts create; it is not in the severity list, so it reads `info`).

**Params the evaluator actually reads** (`evaluate()`, lines 277-316): `min_multiple`, `sides`;
`min_size`; `min_levels`; `min_ticks`; `min_fills`; `min_zscore`; `kinds` (cvd); `min_strength`;
`min_share`; `min_volume`; `min_pct`; `max_distance_ticks`; `min_beyond_ticks` — plus the generic
`at_price` / `at_tol` scope and `min_age_s` where the emitting detector uses it.

**Three defects in the alerts UI, measured:**
1. `alClear` (`atlas.js:585`) writes the row `cleared locally` and never calls the server. The route
   `POST /api/atlas/alerts/clear` exists and is wired to nothing. A button that says it cleared a log
   it did not clear is worse than no button (canon: the UI may not claim what it did not do).
2. `Params (JSON)` is an editable text input of raw JSON (`atlas.js:556`) — every rule is read and
   written in the engine's vocabulary, and a typo is accepted silently by `JSON.parse` failure paths
   (`continue` — the rule is simply not saved, with no message).
3. There is no editor for the fields that make a rule a rule — level scope (`at_price`/`at_tol`),
   hold time, channels — no "created from heatmap" filter (the heatmap's rules are the `hm-` ids), and
   the log table has no Level or Size column: `data.price`/`data.size` are in the payload of every
   fired alert and the table renders only the pre-written message.

**Build spec (decisions taken, so the next session does not re-open them):**
- A pure module `orderflow_system/desktop/ui/alert-format.js` (global `OFAPALERTS`), the one place that
  turns a rule into words: `kindLabel(kind)`, `paramSpec(kind)` (each field's key, label, unit,
  default, min), `sentence(rule)` (e.g. *"Big trade — a single print ≥ 3× the block threshold · any
  level · UI · 30 s cooldown"*), `scopeWords(rule)` (`any level` vs `at 77070.24 ± 3.96`), and
  `why(row)` (the log row's reason, from `data.detail`/`note` with the kind's own sentence as the
  fallback). The editor's fields and the sentence both read `paramSpec`/`sentence`, so the form and
  the words cannot disagree — the same one-source rule as `HEAT_INSET` and the cursor store.
- The Rules card: Keep the On toggle and the Fired count; replace the JSON input with the sentence plus
  an inline **Edit** row built from `paramSpec` (named inputs with units), the level scope (price +
  tolerance), channels (ui / telegram / webhook checkboxes — the channels are the rule's, and
  `dispatch_webhooks` only forwards rules that opt in), and the cooldown. Save posts the whole rule
  back (the route already upserts), reads the rules back, and reports what the store kept.
- A filter row on the Rules card: `created from heatmap` (id starts with `hm-`) and `enabled only`,
  with an honest count line — *"3 of 16 rules · 3 from the heatmap"*, computed from the list, not
  asserted.
- The log table gains **Level** and **Size** columns read from `data.price` / `data.size` (a `—` when
  the detection has none: `speed_spike` and `cvd_divergence` carry no level), and the message column
  becomes the row's *why*, so every row names symbol, level, size and why regardless of kind.
- `alClear` calls `POST /api/atlas/alerts/clear`, re-reads, and says what came back (the count the
  server reports, not "cleared locally").
- Gates for this phase: a `alert-format.selftest.js` (sentences, scopes, the per-kind spec coverage,
  blank-field defaults) + `orderflow_system/test_alert_format.py` (run the selftest under pytest like
  `test_strips.py` does), plus registering `alert-format.js` in `scripts/audit_ui_refs.py`.

**The plan's gate (P1-7)**: live — edit a rule, fire it, read it in the log naming the level, delete it.

**Live recipe that works here** (paid for in P1-2…P1-6): sandbox
`APPDATA="$LOCALAPPDATA/Temp/ofap_p0_sandbox" .venv/Scripts/python.exe -m orderflow_system.desktop
--headless --port 8093`, `POST /api/control/engine/start`, then CDP to
`http://127.0.0.1:8093/desktop/`. Set `Network.setCacheDisabled` before believing any edit, dismiss
`#wizOverlay` and hide `#mt5Notice` (the notice swallows pointer events), and remember the sandbox's
instrument list holds `ZZZTEST` as its marker. Stop the app and leave the sandbox in place afterwards.

**State at this writing.** Branch `master`, clean, **29 ahead of origin**, nothing pushed. Gates:
pytest **509 passed / 2 skipped**; `audit_ui_refs.py` **AUDIT CLEAN**; the fifteen UI selftests —
shell 22, bus 13, links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12,
indicators 25, intent 7, study-api 45, search-ops all-pass, **ofx 139**, **cursor-link 7**,
**strips 9**.

## §40 — P1-7 built: the alerts card reads, edits and fires like the engine means it

Built 2026-09-16 in the sandbox on live Bybit BTCUSDT. Nothing committed: the change set is on disk
(13 modified files, 4 new — listed at the end of this entry) and HEAD is the §39 docs commit.

**What landed.**

* `desktop/ui/alert-format.js` — global `OFAPALERTS`, pure (a rule in, words out: no DOM, no API, no
  storage): `kindLabel`, `kinds()`, `paramSpec(kind)` (that kind's own fields plus the three scope
  fields `at_price` / `at_tol` / `min_age_s`), `sentence(rule)`, `scopeWords`, `channelWords`,
  `cooldownWords`, `why(row)`, `isHeatmapRule`, and the formatters (`fmtSize` never rounds a crypto
  size to zero). The editor builds its fields from `paramSpec` and the row renders `sentence(rule)`,
  so the form and the words cannot disagree. `alert-format.selftest.js` (20 checks) plus
  `test_alert_format.py` (12) gate it — including the check that matters: per kind, the params the
  JS offers against the params `AlertEngine._passes()` reads, compared from the engine's own source,
  both directions.
* The Rules card (`atlas.js`, rewritten block): every rule is its sentence, with an inline editor
  (name, kind, thresholds, level scope + tolerance, min hold, cooldown, state, channels) that
  replaces the rule's own row and previews what it will save ("saves as: …"). Save / delete / toggle
  post through the route and render what the store KEPT. The filter row counts honestly — "1 of 17
  rules · 1 from the heatmap · 17 enabled", computed from the list — and the poll leaves the rules
  alone while an editor is open or the arbiter holds the surface (the section already carries
  `data-surface="alerts"`).
* The log table: Time · Severity · Kind (in words) · Symbol · **Level** · **Size** · **Why** — the
  why from the detection's own `detail`/`note`, else the engine's message with the symbol prefix
  dropped (the Symbol column already names it). `—` where a kind has no level.
* `alClear` calls `POST /api/atlas/alerts/clear` and says what the server answered ("log cleared —
  the engine now holds 0 rows"). "cleared locally" is gone.
* Engine work the phase's gate could not be met without: **the depth map's own events were never
  dispatched to the alert engine.** `hub._dispatch` has mapped `pull`/`stack` to `heat_pull`/
  `heat_stack` since the atlas package landed, and nothing ever called it with those kinds — so every
  rule the heatmap's alert buttons create, and the two default heat rules, could never fire.
  `DepthHeatmap.on_orderbook` now returns the events it recorded and the hub dispatches them;
  `min_age_s` is enforced generically in `evaluate()` (an event that does not say how long it held is
  no evidence — the same shape as the price scope), and `wall_age` got the `min_size` branch the form
  offers plus a message that names the hold.

**A second defect, found in the log's own Why column.** Refills read "level 76887.9 refilled
-1789344734.5s after being eaten": the book feed stamps snapshots with the venue's **update id**
while the print feed stamps epoch ms, and the detector subtracted one from the other. That normaliser
already existed twice and divergently (`depthmap._as_epoch_ms` did not scale seconds,
`intent._as_epoch_ms` did); it is one module now — `atlas/clock.py` (`as_epoch_ms`, `EPOCH_MS_FLOOR`)
— used by depthmap, intent and tradedepth, and `TradeDetector` keeps a monotonic event clock so a
duration cannot go backwards. Regression:
`test_a_refill_latency_is_a_duration_not_a_sequence_number`.

**Live evidence (sandbox 8093, engine on live BTCUSDT, measured in this pass).**

* The two dead kinds fire: `heat_pull` at 76842.9 (size 10.36) and `heat_stack` at 76847.9 inside the
  first minute of the run — dispatched by the new hub path, not by anything the UI did.
* **The plan's gate, walked end to end.** An `hm-` rule created through `HEATMAP_PRO.alertOnLevel`
  (kind `wall_age`, bound to 76902.80 ± 1.70, `min_age_s` 120) then its tolerance edited to 30 in the
  new editor (the preview and the store both read "at 76830.60 ± 30.00") and **it fired**:
  `hm-BTCUSDT-76830_6-976549` at level 76840.0, size 4.572, "-3.24 pulled near price", read in the
  log's own DOM as `03:43:19 | info | Liquidity pulled near price | BTCUSDT | 76840.00 | 4.57 |
  -3.24 pulled near price`, then deleted (the banner names the id, the list reads 16 rules, 0 `hm-`).
* An empty field is "not mentioned", verified in the direction that matters: clearing `heat-pull`'s
  min_size and saving removed the key — the store kept `params: {}`, not a zero.
* `alClear`: banner "log cleared — the engine now holds 0 rows", the table repainted, the server read
  back at 1 (the next alert arrived within seconds).
* The refill fix, live: `level 76593.4 refilled 0.7s after being eaten (0.041 traded)`. The heat map
  after the clock promotion: 31 columns accumulating, newest 6.9 s old, version 8160 to 9451, 12
  walls carrying `wall_age_ms: 120000`.
* No `client error:` line in the sandbox log; the sandbox was stopped afterwards and its config left
  as found (16 default rules).

**Gates (measured this pass).** pytest **526 passed / 2 skipped** (was 509 / 2 at §39);
`audit_ui_refs.py` **AUDIT CLEAN**; the sixteen UI selftests — alert-format **20**, shell 22, bus 13,
links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12, indicators 25,
intent 7, study-api 45, search-ops all-pass, ofx 139, cursor-link 7, strips 9.

**Decisions taken (do not re-open).** The kind catalogue lives in `alert-format.js` and is held
against `atlas/alerts.py` by a test, so a new kind or a renamed param fails the suite instead of
drifting. The three scope fields are generic — the evaluator checks them before any kind-specific
threshold — and `scopeWords` speaks them, not the field loop. Channels are the rule's own, and the
sentence always says "UI log" because every alert reaches it. `cooldown_s` 0 reads "no cooldown".
The editor saves the whole rule and re-renders from the response, never from the form.

**Recipe notes for the next session.** `Network.setCacheDisabled` is the cache-bust — putting a query
on the hash (`#alerts?cb=…`) is a same-document navigation: nothing reloads and the app's router no
longer matches the view, so the panel silently never polls. Navigate to plain `#<view>` and drive it
with `showView('<view>')`. If the heatmap's overlay/bar is not mounted, call `HEATMAP_PRO.refresh()`
(it mounts on a view activation it noticed). The harness caps one `js()` evaluation at about 5 s —
sleep in Python between probes.

**Open / not verified.** `wall` (large resting level) is in the catalogue with its own note, "no live
detector emits this kind yet"; `wall_age` is the event the map emits. There is no "new rule"
affordance in this card — rules come from the heatmap's alert buttons or the shipped defaults. The
*first* level-bound rule (the 76902.80 `wall_age` with a 2-minute hold) never fired while it existed:
its level did not hold two minutes in that window — the bound-scope firing evidence is the later
`heat_pull` rule. The three `window.prompt` sites from §38 are still open.

**The change set.** Modified: `orderflow_system/atlas/alerts.py`, `atlas/depthmap.py`, `atlas/hub.py`,
`atlas/intent.py`, `atlas/tradedepth.py`, `desktop/ui/atlas.css`, `desktop/ui/atlas.js`,
`desktop/ui/guide.js`, `desktop/ui/index.html`, `desktop/ui/search.js`, `test_atlas_v2.py`,
`test_wall_age.py`, `scripts/audit_ui_refs.py`. New: `atlas/clock.py`, `desktop/ui/alert-format.js`,
`desktop/ui/alert-format.selftest.js`, `test_alert_format.py`.

## §41 — P1-8 recon: how bars are expressed today, and what the modes need

Scoped from the tree on 2026-09-16, read-only — no code changed for this entry. It exists so the build
starts from measurements: what already draws a bar, where a mode can live, what the payload really
carries, and the four defects found on the way.

**Two surfaces draw bars, and they share nothing.**

| Surface | Renderer | Bar expression today |
|---|---|---|
| Engine view (`data-view="ofx"`) | `desktop/ui/ofx.js` — layered canvases, one rAF loop | `drawFootprint()` (`ofx.js:1276-1488`): one column per bar, per-level split cells (bid left half, ask right half), alternating framing band + right-edge separator (`:1362-1365`), stacked-zone bands (`:1342-1357`), POC box (`:1449-1461`), a 1px high→low wick (`:1463-1468`), Δ/V column badge above the high (`:1472-1486`). **There is no open→close body anywhere.** |
| Chart view (`data-view="chart"`) | vendored TradingView Lightweight Charts **v4.1.3** (`desktop/ui/vendor/lightweight-charts.js`), created in `ui.js:526-546` | `addCandlestickSeries({upColor:'#35d07f', downColor:'#ff5d6c', …})`; data set in `loadChart()` (`ui.js:556-611`), which already maps `{time, open, high, low, close}` only. Studies re-paint the same series (`studies.js:221-232`). |

**What the payloads already carry** (this is what makes split/heat modes honest instead of invented):
`/api/candles/{symbol}` returns per bar `{time, open, high, low, close, volume, buy_volume, sell_volume,
delta, tick_count}` — the side volumes (`dashboard/app.py:317`, aggregated path `:337-361`). The
engine view's `mergeBars()` (`ofx-view.js:23-38`) drops `buy_volume`/`sell_volume` on the floor; the
footprint payload's own per-bar `calc` (`{volume, buy, sell, delta, poc, max_bid, max_ask, …}`) is
already merged. `/api/delta/{symbol}` carries `bar_delta` + running `value`. The demo path
(`dashboard/demo_data.py:121-156`) has `volume` + `delta` only — no side volumes, so a split mode
reading demo data must derive `buy=(vol+delta)/2, sell=(vol-delta)/2` and say which source it used.

**Where a mode and a palette can live.**
- `OFX.state.params` (`ofx.js:670`) holds the display parameters; `OFX.setParams()` (`:2119`) marks the
  base and live layers dirty. `math.theme` (`:458-478`) is the one colour table, and both the renderers
  and `OFX.legend()` read it — the legend's own selftest asserts every swatch resolves to a colour
  that table owns (`ofx.selftest.js:148-150`). A palette therefore has to *be* `math.theme`, not a
  parallel table, or the legend invariant breaks.
- `GET/POST /api/control/ofx` (`api.py:555-573`) is the engine's persisted parameter pair; the store's
  clamp list is `config_store.py:540-546` (+ `:684-685` for `min_block`/`va_pct`). `DISPLAY_ROOTS`
  (`param_registry.py:26`) is `("ofx", "atlas", "risk", "studies.data_box", "search.default_view")`, and
  `test_param_registry.py` fails the suite when a display-relevant leaf under those roots is not
  registered — so a new block outside those roots needs its own registration decision, not an
  accidental one.
- `localStorage` is *not* a record: `ofx-view.js:679-688` persists the heat ramp as `ofx.ramp` in
  browser storage, which `config_store`'s own rule (§33 decision 2) says never wins. The ramp is
  also absent from the registry, so no Chart menu can show it and no Restore-default can reach it.

**Four defects found, all measured.**
1. **The heat ramp has no server-side record and no registry entry.** `ofx-view.js:680` reads
   `localStorage['ofx.ramp']`; `math.heatColor01(t, ramp)` (`ofx.js:114`) accepts `classic|thermal`, and
   `ofx-view.js:681` hard-codes the same two strings — a third ramp added to the engine would be
   silently unreachable from the control (the two lists have no test holding them together).
2. **The engine view discards the side volumes the feed already sends** (`ofx-view.js:23-38`), so no
   bar-level up/down readout is possible there today even though the data is in flight.
3. **`state.stats` has no expression counters.** Every other renderer decision is countable
   (`columnBadges`, `heatCells`, `textStarved`, `aggregated`) precisely so a feature can be asserted
   from telemetry instead of from pixels (§38's rule); a new expression pass must add its own count
   or it can only be "verified" by looking.
4. **Nothing in the shell names the encoding.** `#chartSub` is a typed string
   (`index.html:145`: "candles · delta · value-area levels · signal markers") and the
   engine's legend has no expression entry, so a picture drawn with a tinted body has no text anywhere
   saying what the tint means — canon #5's pairing obligation without the words for it.

**Decisions (do not re-open).**
- **One pure module owns the encoding:** `desktop/ui/expression.js`, global `OFAPEXPR`, in the
  `alert-format.js` shape (pure, no DOM/API/storage, `new Function('window', src)` bootable in Node).
  It holds: the five modes (`default`, `delta`, `split`, `heat`, `wick`), the palette catalogue
  (`theme`, `deutan`, `protan`, `tritan`), the per-bar paint decision
  (`barPaint(bar, {mode, palette})` → what to fill, what to stroke, the split fractions, the glyph,
  the chrome gates, and the `encoding` sentence), the chart-series projection
  (`chartBars(bars, {mode, palette})` → per-bar `{color, borderColor, wickColor}`), and the words
  (`modeWords`, `paletteWords`, `legendLines`). The renderers execute; they do not decide.
- **A palette is `math.theme`, applied.** `OFAPEXPR.resolve(palette)` returns `{themeKey: 'r,g,b'}`
  overrides; `OFX.setExpression({mode, palette})` copies the frozen base table back and overlays them,
  so switching palettes is lossless and the legend's swatch invariant survives by construction. Default
  palette = today's colours exactly — the default mode must move no pixel.
- **Five modes, defined once, executed on both surfaces.**
  `default` — today's painting (footprint cells, framing, POC, wick, badges), unchanged.
  `delta` — a body rectangle from open→close tinted by the bar's delta bucket, outlined in the
  direction colour, with the direction glyph; the cells stay readable underneath (body alpha ≤ 0.26).
  `split` — the bar's high→low range carries two sub-bars: left = sell volume, right = buy
  volume (the app's own convention — bid left, ask right, `ofx.js:824-838`), heights = share of the
  bar's side-volume total; side volumes from `calc`/`candles` when present, derived from
  `volume`/`delta` when not, and the mode's words name which source was used.
  `heat` — the open→close body filled on the palette's diverging ramp by `|delta| / volume`.
  `wick` — the wick and the footprint cells only: the bar chrome (framing band, VA/HVN grounds,
  zone bands, POC box) is off, badges stay (they are the text carrier for the sign).
- **Persistence is the config, per chart:** a new `expression` block
  `{engine: {mode, palette}, chart: {mode, palette}}`, clamped by `config_store` against the same
  catalogues `expression.js` declares (one test holds the two lists equal), served by
  `GET/POST /api/control/expression` (partial per chart, returning the block the store accepted), and
  registered in `param_registry` as enums owned by `ofx` / `chart` so both Chart menus show them.
  The heat ramp moves into the same record (`ofx.ramp`, enum, clamp list shared with the JS) — the
  localStorage mirror goes away rather than growing a second one.
- **Colour is never the sole carrier.** delta/heat pair their tint with the direction glyph and the
  existing `Δ`/`V` badge; split pairs its colours with position (left/right) and the ↑/↓
  glyphs; the imbalance cells keep their rail/label. The legend prints the pairing sentence for the
  active mode, from the same object the renderer drew from.
- **Colour-blind palettes are measured, not asserted.** `deutan`/`protan`/`tritan` are seeded from the
  Okabe–Ito set (#0072B2 blue, #56B4E9 sky blue, #009E73 bluish green, #E69F00 orange, #D55E00
  vermillion, #F0E442 yellow, #CC79A7 reddish purple — Okabe & Ito 2008; Wong, *Nature Methods*
  2011), and the selftest simulates each palette's up/down pair through the Viénot–Brettel–Mollon
  (1999) dichromat matrices and requires a minimum separation, with today's green/red pair as the
  control that must *fail* under deutan/protan. A palette claim that is not measured is a claim.
- **A colour-blind palette overrides a hue-only heat ramp and says so.** `classic` walks red→green;
  when a CB palette is active the engine draws the depth heat on the palette's own monotone ramp and the
  legend states the override ("ramp cividis — classic is not colour-blind safe"). Silent substitution
  would be exactly the kind of invisible change the canon forbids.

**Build spec (files, in order).** New: `desktop/ui/expression.js`, `desktop/ui/expression.selftest.js`,
`test_expression.py`. Modified: `config_store.py` (block + sanitiser + `EXPRESSION_*` catalogues),
`param_registry.py` (five enum entries), `api.py` (`/api/control/expression` pair; `ramp` joins the
`/api/control/ofx` key list), `ofx.js` (palette application, mode-driven bar pass, legend section,
`stats().expression` counters), `ofx-view.js` (mode + palette controls, config load/save, mergeBars
carries side volumes), `ui.js` (chart-view projection), `index.html` (controls, legend line, script
tag), `audit_ui_refs.py` (`expression.js` in `JS_FILES`), `test_config_store.py` / `test_param_registry.py`
where the new block touches their contracts.

**Live recipe** (unchanged from §40): sandbox `APPDATA="$LOCALAPPDATA/Temp/ofap_p0_sandbox"
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 8093`,
`POST /api/control/engine/start`, CDP at `http://127.0.0.1:8093/desktop/` with
`Network.setCacheDisabled` set before believing any edit; dismiss `#wizOverlay`, hide `#mt5Notice`;
drive views with `showView('<view>')`, never a query on the hash. The engine view's telemetry is the
proof surface: `OFX.stats().expression` must count the bodies/splits actually painted per mode, and the
legend text is read back from the live DOM (`#ofxLegendBody`).

**Known risk, named now.** The chart view can express default/delta/heat/wick with the vendored
candlestick `color`/`borderColor`/`wickColor` per-bar overrides (v4.1.3 accepts them —
`Js('Candlestick')` maps `color`, `borderColor`, `wickColor`), but *split* needs pixels inside the
range, which the vendor only allows through `addCustomSeries` (`v4.1.3` exposes it). That contract is
probed live before it is built on: if the renderer's time→x path proves unusable, split ships on the
engine view and the chart view says so in its own legend line rather than drawing something that is not
a split candle.

## §42 — P1-8 built and verified: five bar expression modes, measured palettes, the legend that names them

Built and verified 2026-09-16 on live Bybit BTCUSDT in the sandbox. Nothing committed: HEAD is still
`fa202d6` (the §39 docs commit) and the tree carries P1-7 and P1-8 together (P1-8's change set at the
end of this entry; §40 lists P1-7's). The build landed first; a second pass finished the verification
and fixed the three defects verification surfaced — each is pinned by a new test.

**What landed.**

* `desktop/ui/expression.js` — `window.OFAPEXPR`, pure (no DOM, no API, no storage; Node-bootable):
  `MODES` (`default | delta | split | heat | wick`, each with `label`, `says`, `pairing` and chrome
  gates), `PALETTES` (`theme | deutan | protan | tritan`, each with its pair and its MEASURED
  separation numbers), `barPaint(bar, {mode, palette, theme})` (the whole decision for one engine bar:
  fills, strokes, split fractions, glyph, chrome gates, `encoding` + `pairing`), `chartBars(bars, opts)`
  (the Lightweight Charts projection — per-bar `color` / `borderColor` / `wickColor`), `splitVolumes`
  (side volumes from `calc` / `buy_volume` when the feed carries them, else derived from volume and
  delta, and it says which), `legendLines`, and the CVD machinery (`simulate` / `deltaE` / `separation`
  / `legibility`).
* The engine view paints from it: `ofx.js` applies a palette INTO `math.theme` (frozen `BASE_THEME`
  copy → assign → overlay the palette's keys), `setExpression` resolves/clamps and returns what the
  control then displays, the bar pass executes `barPaint` (bodies, split candles, glyphs, the chrome
  gates), `stats().expression` counts `bodies` / `splits` per pass, and the legend carries both a
  layout line (`bar expression (<mode>): <says>`) and a colour-key entry (`<says> · sign: <pairing>`,
  live `mode … · palette <label> · N bodies, M splits drawn in the last pass`).
* The chart view projects through the same catalogue: `#chartMode` / `#chartPalette` selects, the
  `#chartExpr` line renders `legendLines` verbatim (encoding + pairing + palette + the palette's own
  mapping sentence; `split` adds "the chart view cannot draw this mode — candles stay plain here"),
  and the delta lane takes the palette's pair (`rgba(pair, .55)`).
* Persistence is the config, per chart: an `expression` block `{engine, chart} × {mode, palette}`
  clamped by `config_store` against `EXPRESSION_MODES` / `EXPRESSION_PALETTES` (tests hold JS ↔ store ↔
  the `<select>` option lists equal), served by `GET`/`POST /api/control/expression` (partial per
  surface; the response carries the value the store ACCEPTED), registered in `param_registry` (the 4
  leaves + `ofx.ramp` — the ramp is a config value now, **81 → 86** variables, an 18th group), and the
  menubar's Chart-menu writes announce themselves (`ofap:expression`) so both surfaces reload from the
  store rather than being called into.
* The heat ramps are data: `RAMPS = classic | thermal`, **monotone in luminance** measured at 21
  samples per ramp in the gate (`dips == 0`, range > 0.3) — a magnitude never rides on hue.

**The three defects verification found (all fixed and pinned in this pass).**

1. **A bare `r,g,b` colour string makes Lightweight Charts THROW, not fall back.** `chartBars` handed
   the vendor `'230,159,0'` / `'86,180,233'` as per-bar colours; the vendor's parser answers
   `Error: Cannot parse color: 230,159,0` (uncaught, from inside its own paint path — the first paint
   dies; the scratch chart's canvases sampled empty). Route to a wiped app: defect 2. Reproduced
   deterministically on a fresh page: chart `default` + palette `deutan` → the log gains
   `Cannot parse color: 86,180,233` and the window is one red banner within 5 s. Fix: `chartBars`
   wraps the pair in `rgb(...)` at every un-alpha'd site, and `expression.selftest.js` now asserts
   every colour the projection emits is CSS-parseable across all 5×4 mode × palette combinations.
2. **(Pre-existing, app-wide.) `toast()` assigned `innerHTML` to its target, and seven call sites
   aimed it at `document.body`** (the client-error reporter, two in `guide.js`, four in `search.js`) —
   so ANY uncaught error replaced the entire UI with one banner. Fix in `toast()` itself: a
   body-level notice is routed into its own fixed `#noticeStrip` (created once, reused; `ui.css`),
   the call sites unchanged. Live probe: a deliberate throw shows
   "module error: Uncaught Error: …" in the strip (`position:fixed; bottom:10px; z-index:9999`) while
   `#chartMode` still exists and view switching keeps working.
3. **`default` mode + a colour-blind palette settled on theme candles.** `studiesApply()` repaints the
   candle series from the raw bars (it runs with zero studies too), and the chart's re-assert read only
   the MODE — `default` was exempt — so every poll stripped the deutan palette back to theme green/red
   under a legend claiming sky blue / orange (measured: 0 of 28 rows coloured; pane reads `sky 0 /
   orange 0 / green 1858 / red 2570`). Fix: the re-assert fires unless `mode === 'default' && palette
   === 'theme'` — the one combination the studies pass cannot move — pinned in `test_expression.py`.

**Live evidence (sandbox 8093, engine on live BTCUSDT).**

* Engine view, five modes on 13 bars (`stats().expression` counters; ink = opaque px on `#ofxBase`):
  default 0 bodies / 0 splits, ink 141,878 → delta 13/0, 140,525 → split 0/13, 63,344 → heat 13/0,
  140,449 → wick 0/0, 51,140 → back to default 141,862. The legend's sentence per mode is the
  catalogue's own `says`, read back from `#ofxLegendBody`.
* Palettes through the control write the same 8 keys (`bid ask up down imBuy imSell stackUp
  stackDown`): deutan `86,180,233 / 230,159,0`, protan `240,228,66 / 86,180,233`, tritan
  `64,176,166 / 220,50,32`; `theme` restores `53,208,127 / 255,93,108` exactly (sentinel: a hand-set
  `bid = '1,2,3'` comes back green). The control → store round trip measures **~1.2 s** on a busy
  sandbox — probes must sleep ≥3 s or they read the previous adopt (that race produced a false
  "restore is broken" reading once).
* Config round-trip, both directions, both surfaces: `POST` junk → the response carries the CLAMPED
  value (`default/theme`), never the junk; partial writes never blank the other surface; a bad surface
  answers `ok:false`; values written by curl are adopted on the next reload (engine read back at
  `heat/protan`, chart at `wick` for wick-mode wicks with transparent bodies).
* Chart view A/B on the same bars: `default` + theme paints the theme pair (exact `53,208,127` /
  `255,93,108`: 1112 / 3013 px); `default` + deutan paints `86,180,233` / `230,159,0` (1119 / 2636 px);
  the settled state (12 s and 18 s after load, ≥2 polls later, reads identical) is 29 of 30 rows
  coloured with pane `sky 1420 / orange 2280 / green 0` — defect 3's fix holding across polls.
* Client-error log: in the clean window (≥04:31, after the fixes) there is exactly ONE line — the
  deliberate strip probe. The pre-fix repro's 619 lines sit at 04:29–04:30.
* The sandbox was stopped afterwards and its config left at `default/theme` on both surfaces.

**Gates (measured this pass).** pytest **553 passed / 2 skipped** (526/2 at §40; `test_expression.py`
carries 27 of them); `audit_ui_refs.py` **AUDIT CLEAN** (116 routes, 65 modules, created ids 229);
**seventeen** UI selftests green — **expression 50**, ofx 139, alert-format 20, shell 22, bus 13,
links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12, indicators 25,
intent 7, study-api 45, search-ops all-pass, cursor-link 7, strips 9.

**Deviations from §41's spec (decisions taken — do not re-open).**

* The CVD model is **Machado–Oliveira–Fernandes 2009** (severity 1.0, applied in linear RGB; each row
  sums to 1, asserted), not the recon's Viénot–Brettel–Mollon set: the VBM matrices are injective on
  (r,g), so no red/green pair ever collapses under them and a bad palette measures "safe" — the metric
  could not detect the failure it exists for. The shipped green/red pair is the control that must FAIL
  the measurement (ΔE 9.1 deutan / 35.0 protan), and every shipped pair's numbers are re-measured in
  the selftest.
* The recon's "a CB palette overrides a hue-only heat ramp (`cividis`)" was **superseded**: both
  shipped ramps are monotone in luminance (measured, dips == 0), so there is no hue-only ramp left to
  override and no silent substitution to announce; the legend names the active ramp instead.
* `split` stays on the chart control on purpose: `CHART_SUPPORT.split` is `false` and the chart's
  legend prints the reason instead of drawing something else under the same name.

**Open / not verified.** The newest chart bar loses its per-bar expression colours between polls (the
WS `series.update()` path writes plain OHLC; ≤5 s until the next fetch; all modes, pre-existing path,
left alone). Chart markers (the optional overlay) keep their own colours under a CB palette — the
palette maps the candles, wicks and the delta lane, which is what the legend's mapping sentence
enumerates. The menubar's Chart-menu items for the expression are registry-verified (the params route
serves all four leaves with values and defaults) but were not clicked live this pass. The three
`window.prompt` sites from §38 are still open.

**The change set (P1-8's own files; P1-7's are listed in §40).** New: `desktop/ui/expression.js`,
`desktop/ui/expression.selftest.js`, `test_expression.py`. Modified: `desktop/config_store.py`,
`desktop/param_registry.py`, `desktop/api.py`, `desktop/ui/menubar.js`, `desktop/ui/ofx.js`,
`desktop/ui/ofx-view.js`, `desktop/ui/ui.js`, `desktop/ui/ui.css`, plus the two shared with P1-7
(`desktop/ui/index.html`, `scripts/audit_ui_refs.py`).

## §43 — P1-9 recon: where the keyboard stands, and what one map has to carry

Read-only against the tree on 2026-09-16 — no code changed for this entry. It exists so the build
starts from a measured inventory: every keydown listener that exists, the eight actions the plan
names, the five defects found on the way, and the decisions that must not be re-opened.

**The ask (plan item P1-9, keyboard-first completion).** One shortcut map with scopes: palette,
freeze, view switch, zoom, selection clear, replay seek, export, alert-from-cursor; discoverable
in-app; never fires inside a text field. Gate: a live pass where every action is reachable with no
mouse and a text field swallows none of them.

**Inventory — every keydown listener in the UI** (grep `addEventListener('keydown'` over `desktop/ui/*.js`).

| File:lines | Keys | Guard today | Notes |
|---|---|---|---|
| `ui.js:105-113` | Alt+A → `showView('alpaca')` | fields checked + rejects ctrl/meta/shift | global nav |
| `pause.js:74-79` | P → pause/resume | fields + ctrl/meta (alt/shift NOT rejected) | the freeze action, exists |
| `search.js:481-489` | input-local ↑/↓/Enter/Esc/Shift+? | field-scoped by construction | palette field |
| `search.js:491-497` | Ctrl+K and `/` → focus `#programSearch` | fields checked for `/` only | the palette, exists |
| `menu.js:289-300` | Esc; ?/F1 → hotkey sheet; `/` → open menu + focus its filter; 1-9 → rail click | Esc runs even while typing (by design); rest field-guarded | the sheet's owner; `/` collides with search.js |
| `menubar.js:755-757` | Tab → close the open menu | state-gated | menu-bar walk |
| `menubar.js:758-791` | Esc; Alt → focus title; ←/→/↑/↓/Enter walk | focus-gated on `.mb-title`/items | menu-bar walk |
| `menubar.js:792-794` | Alt+Z → zen | none — no field check | defect #2 |
| `shell.js:1574-1611` | Ctrl+Alt+T both modes; Escape/F11/Alt+1-9 in Terminal | typing checked only after Ctrl+Alt+T | terminal keys |
| `strips.js:379-407` | ↑/↓ PgUp/PgDn Home/End | fields + hover / inside-strip scoped, capture phase | the reader's keys (P1-4) |
| `drawings.js:516-530` | Esc chain; Delete/Backspace | fields checked | drawing-tool keys |
| `atlas.js:492-530` | none — replay is buttons + range inputs only | — | replay has no keys |
| `heatmap-pro.js` | none (buttons via `[data-hm-pro]`) | — | alert/export are mouse-only |
| `ofx.js:2021-2057` | none — wheel only (time ×1.12/0.89, price ×1.09/0.92; clamps 2.5-90 / 0.02-40) | — | zoom has no keys |
| `intent.js:202-207` | observes keydown to lease a surface | n/a | the arbiter, not a binding |

**The eight required actions, against that inventory.**

| Action | Today | Verdict |
|---|---|---|
| palette | Ctrl+K and `/` (search.js) | exists; `/` has two owners |
| freeze | P (pause.js) | exists |
| view switch | 1-9 (menu.js) | exists |
| zoom | wheel only; the heatmap's `zoom +/-` buttons | no keys |
| selection clear | `Clear` on the sel strip (`ofx-view.js:603`, handler `:714` → `OFX.clearSelection()`); heatmap `clear-sel` | no keys |
| replay seek | `#rpSeek` + `#rpPlay/Pause/Stop` (atlas.js:492-530) | no keys |
| export | `Export CSV` (`ofx-view.js:603` handler `:714`, `exportSelection()` `:629`) + heatmap `export-region/markers` | no keys |
| alert-from-cursor | `alert on cursor level` button (`heatmap-pro.js:633`, act `:693`, `alertOnLevel` `:431`) | no keys |

**Defects found (measured).**
1. **Two owners of `/`.** `menu.js:294` opens the ☰ panel and focuses `#menuFilter`; `search.js:493`
   focuses `#programSearch`. Both are document listeners, both `preventDefault()` — one press does
   both things.
2. **Alt+Z (zen) has no typing guard.** `menubar.js:792` is a capture-phase listener that checks
   `ev.key === 'z' && ev.altKey` and nothing else — it fires while a field has focus.
3. **P's guard is loose.** `pause.js:74-79` rejects only ctrl/meta, so Alt+P and Shift+P also
   pause today: the chords that exist are wider than the ones the sheet advertises.
4. **The discoverable sheet is hand-maintained and already stale.** `menu.js:56-65` lists 8 rows;
   the tree honours a dozen more bindings the sheet never mentions (Alt+Z, Ctrl+Alt+T, F11,
   Alt+1-9, Alt+A, the strip's six keys, drawings Esc/Delete, the menu-bar walk), and nothing
   keeps the two in sync.
5. **The guide's "Open the hotkey map" button does not open the map.** `guide.js:2345-2348` passes
   `view: 'guide'` — `wizGo` lands on the Guide view, so the button the step advertises as "the
   hotkey map" never shows one.

**Decisions (do not re-open).**
- **One registry, one dispatcher, one sheet source.** New `desktop/ui/keys.js` (global `OFAPKEYS`)
  owns the map: `bind({id, keys[], label, scope, when?, run, inField?, priority?})` for
  centrally-dispatched keys, `document([{keys, label, scope}])` for keys that stay local because
  they are scoped to hover state, a focused field or an open menu (strips, drawings, the menu-bar
  walk, the palette field, Terminal F11/Esc/Alt+digits). ONE document-level keydown listener; the
  sheet renders from `OFAPKEYS.list()`; menu.js's hand-written HOTKEYS array is deleted.
- **Chord form** is `[ctrl+][alt+][meta+]key` with the key lowercased; shift is part of a chord
  only when it changes the character (`?` vs `/`, `+` vs `=`, `_` vs `-`). Bindings list aliases
  (`['=', '+']`).
- **The typing guard is the dispatcher's job**, not each handler's: target `INPUT`/`TEXTAREA`/
  `SELECT`/`isContentEditable` swallows every binding except the ones opting in with
  `inField: true` (exactly one: Escape-closes-the-menu, today's behaviour). `Space` is additionally
  skipped when the focused element is a `BUTTON`/`A`/`SUMMARY` — the browser owns that activation.
- **Scope collisions resolve by priority, deterministically**: engine keys 6 > heatmap 5 > replay 5;
  ties → first registered. Contexts come from `OFAPKEYS.inView(view)`: the section must be
  `.active`, and in Terminal mode with a focused panel, that panel must be the one.
- **The new chords.** Engine: `=`/`+` time zoom in, `-`/`_` out (×1.12/0.89, the wheel's factors),
  `]`/`[` price zoom in/out (×1.09/0.92), `X` clear the selection, Ctrl+E export the selection.
  Heatmap: `=`/`-` drive its own `zoom +/-` buttons, `X` clears its selection, Ctrl+E exports the
  region, `A` runs `alert on cursor level`. Replay: `Space` toggles play/pause, `,`/`.` seek -/+2%.
  `/` now belongs to the palette only (defect #1's resolution); the ☰ menu keeps its button and
  Ctrl+K stays the palette's primary chord.
- **Zoom maths get one home**: `math.zoomScale(value, factor, min, max)` + `math.anchorOffset(...)`
  (pure, selftested); `OFX.zoomTime/zoomPrice` compose them around an anchor (stage centre for
  keys, the cursor for the wheel) and the wheel handler is refactored onto them — no second copy
  of the anchor arithmetic.
- **Ctrl+Alt+T migrates into the map and therefore becomes field-guarded** (today it fires while
  typing — `shell.js:1574-1579` checks typing only after it). Intended change; the shell keeps its
  own listener for Escape/F11/Alt+digits (mode-entangled) and documents those rows via the map.

**Build spec.** New: `desktop/ui/keys.js`, `desktop/ui/keys.selftest.js`, `test_keys.py`.
Edits: `index.html` (one script tag after `theme.js`, ahead of every module that registers at
parse time); `menu.js` (drop the static HOTKEYS + the keydown block; sheet renders from the map);
`search.js` (drop its document keydown; register Ctrl+K + `/`); `pause.js` (export a `toggle()`;
register P); `menubar.js` (export `toggleZen`; drop the Alt+Z listener; register it; document the
walk); `ui.js` (drop the Alt+A listener — keys.js core binds it); `shell.js` (drop Ctrl+Alt+T from
its listener; register it; document Terminal rows); `ofx.js` (zoom maths + exports); `ofx-view.js`
(register engine zoom / X / Ctrl+E; add the engine legend's keyboard rows); `heatmap-pro.js`
(register X / Ctrl+E / A); `atlas.js` (register Space and `,`/`.`; track `A.replay.playing`);
`strips.js` + `drawings.js` (document their local rows); `guide.js` (the hotkey step's button
opens the sheet; copy names the new keys); `test_wiring.py` (its audit-list tuple gains keys.js).
No CSS additions — the sheet reuses the existing `hk-*` classes.

**Live recipe (sandbox).** `APPDATA="$LOCALAPPDATA/Temp/ofap_p19_sandbox" .venv/Scripts/python.exe
-m orderflow_system.desktop --headless --port 8092`, driven over CDP with
`Network.setCacheDisabled`. Per action: keys dispatched as real CDP input events, effects read
from the app's own state — `OFAPPause.state.paused`, `.view.active`, `OFX.state.view.scaleX/Y`,
`OFX.selection()`, `#rpSeek.value` + the replay status route, the exports folder listing, the
alert-rules count. The text-field probe focuses `#programSearch`, presses every new chord, and
asserts `OFAPKEYS.recent` gained nothing and no state moved. Created state (an exported file, a
test alert rule) is counted and deleted afterwards; the sandbox log is grepped for `client error:`.

**Gates at recon time (measured this pass).** pytest **553 passed / 2 skipped**;
`audit_ui_refs.py` **AUDIT CLEAN** (116 routes, 65 modules, 144 used ids, created 229); seventeen
selftests green (ofx 139, expression 50, alert-format 20, shell 22, bus 13, links 10, watchlist 17,
news 17, options 21, fundamentals 18, market-pressure 12, indicators 25, intent 7, study-api 45,
search-ops all-pass, cursor-link 7, strips 9).

## §44 — P1-9 built and verified: the one shortcut map, and the palette crash it uncovered

Built on disk 2026-09-16, uncommitted like everything since P1-7. `desktop/ui/keys.js`
(`window.OFAPKEYS`) is now the app's single registry and dispatcher for keyboard bindings: one
document listener, a chord canonicaliser, the shared typing guard, scope gates with priorities, a
`recent` ring of the last firings, and `list()` — the hotkey sheet renders from it, so a key and its
documentation cannot drift. 29 → 31 rows live (the two Drawings rows join when the engine view first
mounts its drawing layer; every other row is present from boot).

**The eight actions, all reachable with no mouse (measured, sandbox :8092).**
palette — Ctrl+K focused `#programSearch` (`recent: palette`). freeze — `P` → paused true → false.
view switch — `4` → `.view.active` became `heatmap` = rail[3]. zoom — `=` / `-` / `]` / `[` moved
`scaleX 52 → 58.24 → 51.8336` and `scaleY 0.8988 → 0.9796 → 0.9013` (the wheel's exact multipliers,
`recent` naming each binding). selection clear — a real shift+drag box → strip shown → `X` → selection
null, strip hidden, `recent: selection-clear`. export — `Ctrl+E` → `ofx-selection-BTCUSDT-20260916T023100.csv`
(19 lines; volume 12.58 / delta 8.05 matching the strip) in the sandbox exports folder; deleted after,
count read back to 0. replay seek — exchange tape loaded (1000 events), `Space` → playing → paused,
`.` seeked `318 → 338`; a focused `#rpStop` + `Space` left the browser its activation and fired no
binding. alert-from-cursor — hovered level `75968.08`, `A` created
`hm-BTCUSDT-75968_08-073188 {kind heat_pull, at_price, at_tol 1.52, channels ['ui']}`; deleted, rules
16 → 17 → 16. The sheet itself: `?` opened it with **31 rows = `OFAPKEYS.list().length`**, every one
of the eight action labels present, 8 Global rows highlighted; `Esc` closed it.

**"A text field swallows none of them":** focus in `#programSearch`, then twelve chords dispatched as
real key events (`p 4 = - x a , space ] ? Ctrl+K Ctrl+Alt+T`) — `recent` stayed 0, paused/hash/mode/
scaleX all unchanged, the characters landed in the field only.

**Terminal mode:** `Ctrl+Alt+T` there and back; `4` focused the heatmap widget and `=` ran
`heatmap-zoom-in` (its window 169 → 180 buckets); `7` focused the engine and `=` ran `zoom-time-in`
(52 → 58.24); `P` froze and resumed inside the mode. Scope collisions resolve by focus, as designed.

**Defects found and fixed in this pass (all measured).**
1. **The palette threw on every non-empty query.** `studies.js`'s Guide section was pushed as
   `{title, lead, body}` while `GUIDE_SECTIONS` entries are `{h, body}` — the Guide renders `s.h` and
   `searchBuildIndex` indexes it, so `searchScore` hit `undefined.toLowerCase` for every query
   (25 `client error:` lines, all 12:01:59-12:02:00, before the fix; the Guide card would have read
   "undefined" had it rendered). Fixed to the `h`/`body` shape; `test_studies.py` now guards the `h:`
   at both push sites. After the fix: typing into the palette renders results and the log gained
   **zero** further client errors; the Guide renders 13 cards with "Writing your own studies" at 12.
2. **The same push never refreshed `#guideBody`** (the guide view is built once, before the push),
   so the section was invisible even in the data. Mirrored the how-to section's refresh.
3. Recon-time defects fixed in the build: the two owners of `/` (palette now owns it; menu.js's copy
   gone), Alt+Z's missing typing guard, `Ctrl+Alt+T` firing mid-typing (now guarded — intended
   behaviour change), and `P`'s loose guard (Alt+P/Shift+P no longer pause; the chord is exact).

**Deviations from §43's spec (do not re-open).** Engine bindings register at MODULE scope in
ofx-view.js, not inside the lazy `ofxInit()` — the live map read 22 rows without them until the view
was opened once, which is exactly the user the sheet exists for. Engine clear/export RUN click the
selection strip's own buttons (`[data-ofx-sel="clear|export"]`) — driving beats duplicating, same as
the heatmap and replay bindings. `test_workstream_i.py`'s pinch test was updated to pin the new
routing (it asserted `scaleY` inside a 700-char window after `ev.ctrlKey`; the maths now live in
`zoomPrice()`, pinned by ofx selftest 139 → 145).

**Gates (measured this pass).** pytest **563 passed / 2 skipped** (553 + `test_keys.py` 9 +
`test_studies.py` 1); `audit_ui_refs.py` **AUDIT CLEAN** (67 modules now, was 65); **eighteen** UI
selftests green — **keys 42** (new), **ofx 145**, expression 50, alert-format 20, shell 22, bus 13,
links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12, indicators 25,
intent 7, study-api 45, search-ops all-pass, cursor-link 7, strips 9. Sandbox client-error log: 25
lines, all the fixed crash, zero after.

**Open / not verified.** The wheel's zoom was refactored onto the same `math.zoomScale` /
`math.anchorOffset` helpers the keys use — a lift of the original formulas, but the wheel itself was
not re-driven visually this pass (its numbers are the selftest's and the keys' live multipliers).
The sheet lists the Drawings rows only after the engine view first mounts that layer. Two `X clear
the selection` rows are by design (Engine and Heatmap scopes). `1` maps to rail[0], which carries no
`data-view` — pre-existing mapping, unchanged (`2` is Overview … `7` is Engine). The harness's CDP
`Input.dispatchMouseEvent` timed out against the sandbox daemon (both sessions); the selection and
heatmap-hover gestures were therefore synthesized in-page for SETUP only — every key under test was
a real CDP key event, and every reading came from the app's own state. The frozen build still
predates P1-7/8/9. Nothing was committed; HEAD stays `fa202d6`.

**The change set (P1-9's own files; P1-7's are listed in §40, P1-8's in §42).** New:
`desktop/ui/keys.js`, `desktop/ui/keys.selftest.js`, `test_keys.py`. Modified: `desktop/ui/index.html`,
`menu.js`, `search.js`, `pause.js`, `menubar.js`, `ui.js`, `shell.js`, `ofx.js`, `ofx.selftest.js`,
`ofx-view.js`, `heatmap-pro.js`, `atlas.js`, `strips.js`, `drawings.js`, `guide.js`, `studies.js`,
`test_wiring.py`, `test_workstream_i.py`, `test_studies.py`, `scripts/audit_ui_refs.py`.

## §45 — P1-10 recon: what young data exists, where age dies, and what stale-out has to mean

Read-only against the tree on 2026-09-16 — no code changed for this entry. Scoped so the build
starts from what is already true: the age policy exists but never reaches a screen, and "stop the
feed" has two opposite behaviours with no shared wording.

**The ask (plan item P1-10).** Show the age of what is displayed (depth 5 s / quote 60 s windows;
`age_known:false` when the clock is unknown) and make a panel visibly stale-out instead of freezing.
Gate: live — stop the feed, watch panels age and say so; restart, watch recovery.

**What exists.**
- **The policy already has one home: `atlas/crossvenue.py`.** `STALE_DEPTH_MS = 5_000`,
  `STALE_QUOTE_MS = 60_000` (`:35-36`), `stale_window_ms(kind)` (`:39-41`), and
  `VenueTop.to_dict()` (`:59-88`) emitting `age_ms`, `age_known`, `stale_after_ms`, `stale`, `ok` —
  with the rule "an unknown age is reported as unknown, not as stale". **No UI reads crossvenue**
  (grep: zero consumers) — the only age semantics in the build are API-only and invisible.
- **`engine.live_status()` (`engine.py:653-708`)** is the UI's live/demo source: a per-endpoint
  string map (`live` / `warming` / `demo`, plus `stale` for a book that lost sequence continuity,
  `bybit_feed` sets the flag). Consumed by `ui.js` as `#livePill` ("data: live|warming|demo", no age,
  `ui.js:235-246`) and `panelIsLive()` (two gates: footprint `:908`, tape `:960`). **No timestamps
  anywhere in the payload.**
- **The clock exists server-side but is dropped.** `main.py:252-257` keeps
  `_recent_ticks[sym]: deque[Tick]`, `_last_candles[sym]: Candle`, `_recent_signals[sym]`;
  `Tick.timestamp_ms` / `Candle.timestamp_ms` (`data/models.py:46,184`). The status payload
  (`engine.py:710-727`) carries symbol/price/ticks/candles/cum_delta/trade_phase/trade_direction —
  no times. `atlas/clock.py` is the one venue-clock normaliser.
- **Payload sample times the UI already holds**: heatmap `buckets` are epoch ms
  (`DepthMap.snapshot`, live value `1789525971000`), tape prints carry `time`, candles carry
  `timestamp_ms`, news items carry their own times. Most panels could know their age today; none
  display it.
- **Existing stale-flavoured behaviours**: footprint/tape demo banners (`ui.js:908-912`), the
  `panelIsLive` gates, `book_state`'s `stale`, atlas rows with `ts_ms=0` = "age unknown"
  (`atlas/api.py:300`), `fresh_book` at a 1500 ms window (`intent.py:463`). Nothing anywhere says
  "this was live and is now N seconds old".
- **The stop-the-feed trap**: on engine stop every `dashboard/app.py` route returns `demo_data.*`
  (`:1097` footprint, `:1119-1126` tape, `:277` candles, `:811` orderbook, …), while the **atlas hub
  keeps serving its last recorded state** (heatmap/cvd/profile/tape are hub reads, no demo fallback).
  So stopping the feed produces two different pictures — a silent demo swap and a silent freeze —
  with no shared wording for either.
- **Claims surface**: `guide.js:2390` says "the logs panel and the status bar show freshness" —
  today neither shows an age (`#statusFeed` carries the stored plan's feed wording, `shell.js:1448`).
- **Chip pattern to reuse**: `OFAPCURSOR.badge(host)` (`cursor-link.js`) — a `.view-head` span owned
  by one store and repainted centrally. The freshness chip is its sibling: one module, chips on
  view-heads, repainted on a shared 1 s tick so a silent feed AGES without any new payload.

**Defects found.**
1. **Age never reaches the screen.** live_status has no times, the status payload drops
   `_recent_ticks`/`_last_candles` stamps, and no panel renders an age. Freshness is a policy
   without a clock.
2. **The one real age vocabulary has no consumer.** crossvenue's `age_ms`/`age_known`/`stale` rows
   exist for API callers only.
3. **"Stop the feed" has two opposite behaviours and one silent one.** Demo-swap panels announce
   demo; hub-backed panels freeze on their last picture and say nothing; neither names a time.
4. **A claim in the copy that is not true today** (guide.js:2390) — the build either makes it true
   or the sentence changes; leaving it is the kind of drift this suite exists to stop.

**Decisions (do not re-open).**
- **One policy module.** Extract the constants + the assessment into `atlas/freshness.py`:
  `window_ms(kind)` and `assess(kind, last_ms, now_ms=None)` → `{age_ms, age_known, window_ms,
  stale}`; kinds depth 5 s, quote 60 s, trades 5 s (a continuous feed), candles 60 s.
  `crossvenue.py` imports it and its payload keys stay byte-identical.
- **The server exposes ages where a real clock exists.** `engine.status()` per_symbol gains
  `last_tick_ms` + `last_candle_ms` (0 = never); `live_status()` gains an additive `age` block per
  endpoint (tape → last tick, footprint/candles → last candle, orderbook → `age_known:false` — its
  timestamp is the venue's own clock, the existing `atlas/api.py:300` note stands; the rest unknown).
  `endpoints` stays the string map `panelIsLive` gates on.
- **One UI store: `desktop/ui/freshness.js` (`OFAPFRESH`)** in the cursor-link shape —
  `stamp(panel, {lastMs|ageMs, ageKnown, windowMs, source})`, `chip(head)` (`.view-head` span,
  class `ofap-fresh-chip`), a 1 s repaint tick, and a pure `pick(state)` → `fresh`/`aging`/`stale`/
  `unknown`/`demo`/`held`. Thresholds: quiet age under half the window, amber to the window, then
  "stale — no update for Ns" plus a section class `ofap-stale` that DIMS the data area (never hides
  it). Demo renders "demo data" — an age on demo numbers would be a lie. `age_known:false` renders
  "age unknown".
- **A user-invoked hold is not a fault.** With `OFAPPause` paused, chips render `held · Ns` (muted),
  not amber — the pause chip already says updates are held; the age still counts because it is real.
- **Windows come from the payload where they exist** (crossvenue rows, the new engine age block);
  the JS default table covers client-only sources (news/options/fundamentals fetch stamps) and a
  pytest pins it to the Python constants so the two can never drift.
- **Stamp call sites are each panel's own paint** (the panel owns its claim): ofx-view
  (footprint poll), watchlist (status paint), atlas.js loads via its 962-971 beat
  (heatmap/cvd/profile/frames/trackers), heatmap-pro (pull), news, options, fundamentals, scanner,
  chart, tape. The **pill** gains the newest-tick age; `#statusFeed` keeps the plan wording.

**Build spec.** New: `atlas/freshness.py`, `desktop/ui/freshness.js`,
`desktop/ui/freshness.selftest.js`, `orderflow_system/test_freshness.py`. Edits: `atlas/crossvenue.py`
(import the policy), `desktop/engine.py` (status + live_status ages), `desktop/ui/index.html` (one
tag + the pill's title copy), `ui.js` (pill age from the age block), `watchlist.js`, `ofx-view.js`,
`atlas.js`, `heatmap-pro.js`, `news.js`, `options.js`, `fundamentals.js`, `scanner.js`,
`ui.css` (`.ofap-fresh-chip`, `.ofap-stale` — tokens only), `scripts/audit_ui_refs.py`,
`test_wiring.py` (audit tuple), `guide.js` (the freshness claim, now made true).

**Live recipe (sandbox).** Engine start → panels' chips read their ages; **stop the feed** = engine
stop: hub-backed panels (heatmap/CVD/profile) must age past the 5 s window and print "stale — no
update for Ns" while demo-served panels must print "demo data"; curl the status + live-status routes
for the age fields; **restart** → every chip returns to fresh. The 1 s tick is the proof the age is
real rather than stamped per payload: with no payload arriving, the number keeps rising.

**Gates at recon time (measured this pass).** pytest **563 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN** (67 modules); eighteen selftests green (keys 42, ofx 145, expression 50, alert-format
20, shell 22, bus 13, links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure
12, indicators 25, intent 7, study-api 45, search-ops all-pass, cursor-link 7, strips 9).

## §46 — P1-10 build: the age of every panel's data, declared

**What it does now.** Every panel view-head carries a freshness chip: `live · 2 s`, `aging · 4 s`,
`stale — no update for 17 s`, `demo data`, `age unknown`, `held · 9 s` (the last when `P` is holding
updates — a deliberate hold is not a fault and does not read as one). The chip repaints on its own
**1 s tick**, so a panel that stops receiving samples ages and then stales out visibly instead of
freezing. A stale panel's data area dims (`opacity: .6`) — dimmed, never hidden — and the chip says
how long. The status bar's pill reads `data: live · 2 s` (the newest tape sample's age), with every
endpoint's age in its title.

**One policy, one store.**
- `atlas/freshness.py` — the one reading of "how old is this": `window_ms(kind)` (depth 5 s, quote
  60 s, trades 5 s, candles 60 s — the numbers `crossvenue.py` had, moved here and re-exported so its
  payload keys stay byte-identical) and `assess(kind, last_ms, now_ms)` → `{age_ms, age_known,
  window_ms, stale}`. An unknown clock (`ts_ms` 0/None, the venue-time case) stays **unknown** —
  never invented, never stale.
- `desktop/ui/freshness.js` (`window.OFAPFRESH`) — `stamp(id, spec)` / `chip(head, id)` / `pick` /
  `fmtAge` / `list()`; chips auto-attach to all fourteen panel view-heads at boot (the scanner
  attaches its own — its view is built by its module after boot), and `pick()` gives demo and unknown
  their own verdicts ahead of any age.
- The JS windows mirror the Python ones and `test_freshness.py` pins them **the-equal**.

**Server.** `engine.status()` per-symbol gains `last_tick_ms` / `last_candle_ms` (raw clocks, 0 =
never); `engine.live_status()` gains an `age` block keyed like `endpoints` — tape/microstructure from
the tick clock, footprint/candles/scanner/strategy/volume_profile/bias from the candle clock,
orderbook `age_known: false` (venue clock, the api.py note stands). Additive: `endpoints` keeps its
string map and `panelIsLive()` is untouched.

**The defect this pass found (live, then fixed).** `_last_candles` holds the newest **closed** 1m
candle (`main.py` stores it on close), so its `timestamp_ms` is the OPEN time — a healthy 1m feed is
legitimately 60–120 s "old" by open, and the first live read showed `footprint: 67s` against a 60 s
window, i.e. a false stale on a live feed. Fixed by ageing from the CLOSE everywhere a closed bar is
the sample: `live_status` adds `CANDLE_INTERVAL_MS` to the newest open; `ofx-view.js` stamps
`(bar.time + barSec) * 1000` with `barSec` measured from the series; the chart does the same from its
last two bars; frames/alerts/profile/trackers and the slow panels (news 10 min, fundamentals 10 min,
options 2× interval, scanner its own `as_of`) use their own honest clocks — a volume-bar panel that
closes on volume, not the clock, measures its fetch flow and says so in the comment.

**The live gate (sandbox :8093), verbatim reads.**
- Engine started, heatmap + engine views staged: `ofx: live · 9 s`, `tape: live · 0 s`;
  server `age.tape` 2 s, `age.candles` 12 s (healthy, no false stale after the clock fix).
- **Stop the feed** (engine stop clicked): tape `live · 1 s` → `stale — no update for 10 s` →
  `stale — no update for 17 s` (rising with no payload — the 1 s tick is the proof the age is real);
  the tape and heatmap sections gained `.ofap-stale`; ofx went `aging · 39 s → 46 s` (its poll
  continues; the closed bar ages).
- **Restart**: tape back to `live · 0 s`; heatmap (re-shown; hidden panels do not poll — they age
  until the view is shown again, then the load re-stamps) back to `live · 1 s`, chip class
  `is-fresh`, `.ofap-stale` cleared. Server `overall: live`, `tape` 2 s.
- 0 client errors in the sandbox log; sandbox killed; port free.

**Files.** New: `orderflow_system/atlas/freshness.py`, `desktop/ui/freshness.js` (166),
`desktop/ui/freshness.selftest.js` (26 checks), `orderflow_system/test_freshness.py` (10 tests).
Edited: `atlas/crossvenue.py` (imports the policy, keys unchanged), `desktop/engine.py` (age
payloads + `CANDLE_INTERVAL_MS`), `index.html`, `atlas.css` (chip + dim), `ui.js` (`liveState`,
pill age, tape + chart stamps), `watchlist.js`, `ofx-view.js`, `heatmap-pro.js`, `atlas.js`
(heatmap/cvd/profile/frames/trackers/alerts stamps), `news.js`, `options.js`, `fundamentals.js`,
`scanner.js` (self-attached chip), `guide.js` (the freshness claim is now true of the chips),
`scripts/audit_ui_refs.py`, `test_wiring.py`.

**Limits, stated.** (a) The "engine running + feed silently dead" state cannot be induced in-sandbox;
the stop-feed pass demonstrates the same machinery (frozen stamps, ages rising). (b) A panel whose
view is hidden keeps ageing until re-shown — by design, and why the heatmap's recovery needed its
view back. (c) The `demo data` chip path is wired and unit-tested; the stop-feed pass did not catch a
panel mid-demo (ofx read `aging` through the stop), so it awaits a live sighting. (d) `news` /
`fundamentals` windows are 10 min by judgement (their feeds are slow); tune on the first complaint.

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped** (563 + test_freshness
9); `audit_ui_refs.py` **AUDIT CLEAN** (69 modules); **nineteen** selftests green —
`freshness 26` new, keys 42, ofx 145, expression 50, study-api 45, shell 22, alert-format 20, options 21,
fundamentals 18, watchlist 17, news 17, bus 13, market-pressure 12, links 10, strips 9, intent 7,
cursor-link 7, indicators 25, search-ops all-pass.

## §47 — P2-1 recon: where the hover path spends its per-mousemove time

**The ask (plan §2, verbatim).** "Build `printsByBar` in `setData()`; index heat cells by column (or
reuse the visible-column search); maintain CVD incrementally. Gate: a measurement on a 10 k-print tape
— mousemove cost before/after, and `ofx.stats()` p95 unchanged or better under the standard synthetic
load." The plan's §1.3 adds the measured shape of the cost: "the per-mousemove cost is O(prints + heat
cells + bars), not O(prints). With a 10 k-print tape and a 30 k-cell matrix that is ~40 k iterations
per pointer move."

**Where the time goes — `ofx.js` `hover()` (2,180–2,223), three full scans per call.**
1. **CVD from bar 0** (`:2,187-2,188`): `for (let k = 0; k <= i; k += 1) cvd += …bars[k].delta` — O(i)
   per move; a sweep across the canvas pays it hundreds of times.
2. **The whole depth matrix** (`:2,198-2,203`): `for (const cell of state.data.heat)` filtering
   `cell.col !== i` — the full 30 k cells to find one column. Note the RENDERER already solved this:
   `setData()` builds `state.data.heatIndex = math.heatColumns(state.data.heat)` — `{cols, groups:
   Map(col → cells)}` — once per payload (`ofx.js:890`), and `drawHeat` walks `groups`/visible cols.
   Hover simply never used it.
3. **The whole print list** (`:2,205-2,208`): `for (const p of state.data.prints)` with the window test
   `p.time >= bar.time && p.time < bar.time + barSeconds()` — O(prints) per move.
4. A fourth, smaller one the report did not name: `state.data.flowEvents.filter((e) =>
   Number(e.col) === i)` (`:2,210`) — O(events) per move, same column question as (2).

**What the surrounding code already provides.**
- `barSeconds()` (`:1,726-1,731`) is derived from the LAST TWO bar times (stable for a payload) — so a
  print→bar assignment is a stable function of the payload.
- Prints from the live path carry **seconds**: `_live_tape_rows` (`dashboard/app.py:923`) emits
  `t.timestamp_ms / 1000`. But `math.selectionStats` still defends against millisecond stamps
  (`raw > 1e11 ? raw / 1000 : raw`, `ofx.js:641`) while **`hover()` does not** — a ms-stamped source
  fed to the engine view would silently show 0 prints in every bar (the view even has a note for
  "prints outside the drawn bar range", so the failure would look like a feed mismatch, not a bug).
- `stats()` (`:2,286`) exposes `p95Ms`/`framesMs` from render passes; `renderLayers(true)` is exported
  (`:2,282`), which matters because rAF can be dead in a headless page (RESUME trap) — the gate's
  frame numbers must be driven by direct renders, not by waiting on rAF.
- `hover(mx, my)` is exported (`:2,282`) and touches no DOM geometry it does not already hold in
  `state.view` — so a Node/sandbox measurement can call it directly without synthesising mouse events
  (which this host's CDP cannot deliver — see the P1-9 limit).

**One live defect found while reading the payload path.** `ofx-view.js:46` requests
`/api/tape/{s}?limit=200`, but the route (`app.py:1,114-1,116`) declares `count` (default 60, `le=200`)
— the query param is ignored and the view always gets **60** prints. The engine's hover print window
is therefore 60 rows wide no matter what the view asks for. Fix rides along with this item (one word:
`count=200`).

**Decisions (do not re-open).**
- Reuse, don't rebuild: hover's depth read becomes `state.data.heatIndex.groups.get(i)` — the index the
  renderer already pays for; no second structure, no drift.
- One index pass in `setData()`, keyed on the payload flags it already receives:
  `state.idx = { printsByBar, cvd, flowByCol }` — rebuilt when `prints` **or** `bars` change (bar
  boundaries define the buckets), when `bars` change (`cvd` prefix sums), and when `heat` changes
  (`flowByCol`, alongside the existing `heatIndex` build). Rebuild cost is one O(prints+heat+bars)
  pass per 2.5 s poll instead of per mousemove.
- Print stamps are normalised **once**, in the index, with the `selectionStats` rule
  (`raw > 1e11 → /1000`). Live seconds-stamped rows are unaffected; ms-stamped rows stop silently
  reading as zero. This is a fix, stated as one.
- `hover()`'s OUTPUT must not change: same fields, same numbers for the same payload. The selftest's
  parity checks compare the new path against the old loops implemented inline as the oracle.
- `drawRibbon()`'s per-draw CVD rebuild (`ofx.js:1,765-1,768`, an O(bars) run over ALL bars every
  ribbon pass) reuses the same prefix — same numbers, one fewer per-frame scan. The max-volume/max-
  delta spreads in that function stay untouched (rendering change, out of scope).
- The bridge table (`hover: null` state, `onHover` callback, `state.dirty.live`) is untouched.

**Gate recipe (measured before the build, re-measured after).**
Sandbox `:8093` → engine view open → `OFX.setData()` with a synthetic payload: 10 k prints over 300
bars (seconds stamps) + 30 k heat cells + flow events → call `OFX.hover(x, y)` 200 times across the
canvas width (staying inside the bar range) timing each with `performance.now()` → per-call
p50/p95/max, plus one `renderLayers(true)` pass timed after. **Correctness parity first**: the same
probe records `prints`, `sweep`, `depth`, `cvd` at 5 sampled bar indices; before/after must be equal
(or explicitly explained). BEFORE numbers are taken on the unmodified tree; AFTER on the built one.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN (69 modules); nineteen selftests
(ofx 145 — which do NOT yet exercise `hover()` at all; this build adds the first hover coverage).

## §48 — P2-1 build: the hover path is indexed

**What changed.** `hover()` no longer rescans the payload on every pointer move. One index pass in
`setData()` builds three structures, and a fourth is reused:

- `buildPrintIndex()` → `state.idx.printsByBar[i] = {prints, sweep}` (binary search per print —
  order-independent, unlike a merge walk).
- `buildCvdPrefix()` → `state.idx.cvd[i + 1]` = cumulation THROUGH bar i (Float64Array, summed in
  bar order — the same arithmetic order as the loop it replaces, so the bits match).
- `buildFlowIndex()` → `state.idx.flowByCol = Map(col → events)`.
- hover's depth read now uses **`state.data.heatIndex.groups`** — the column index the RENDERER
  already builds (`math.heatColumns`). No second structure exists, so the layer that paints the
  cells and the layer that reports them can never disagree about which column it is.

Rebuild rules live in `setData()`: `bars || prints` → print buckets (bar boundaries define them);
`bars` → CVD prefix; `heat` → flow index. `drawRibbon()` also reads the shared prefix now (its
per-draw O(bars) rebuild is gone; `cvd[i + 1]` where it used to read `cvd[i]`).

**Two fixes rode along, both found in recon (§47).**
1. **Millisecond prints counted as zero.** The index normalises stamps with the `math.selectionStats`
   rule (`raw > 1e11 → /1000`); the live tape is seconds (`_live_tape_rows` divides `timestamp_ms`
   by 1000) so live numbers are unchanged, but a ms-stamped source used to silently read 0 prints
   in every bar while claiming the tape was from a different feed.
2. **The tape fetch asked for rows the route ignores**: `ofx-view.js` sent `?limit=200` while the
   route declares `count` (default 60, `le=200`) — the engine's print window was always 60 rows.
   Now `?count=200`: verified live, 60-request → 60 rows, 200-request → **200 rows**.

**The measured gate (sandbox :8093, synthetic 10 k prints / 300 bars / 30 k heat cells, 200 timed
`OFX.hover()` calls, same probes before and after).**

| | BEFORE | AFTER |
|---|---|---|
| hover p50 | 2.2 ms | 2.1 ms |
| hover p95 | **6.2 ms** | **3.3 ms** |
| hover max | 10.6 ms | 7.2 ms |
| 200 hovers, total | 556.7 ms | 442.8 ms |
| `setData` (once per payload) | 6 ms | 14.3 ms |
| `renderLayers(true)` frames | 4.0–16.8 ms | 4.1–16.8 ms |

**Correctness parity is exact** — the six probe samples (`x` = 40/100/200/320/500/700, `y` = 200)
agree byte-for-byte before/after: index 286/287/289/292/295/299 · prints 33 each · sweep
77.25/79/82.5/87.75/83.25/77.25 · depth 9/28.6667/20/30/14.3333/19.3333 · cvd 0/−3/−6/−3/−5/−3 ·
events 2. The honest reading of the timing: the three scans cost ~0.57 ms per move on this payload
(the rest of the 2.8 ms was level maths and object building), so p50 barely moves while p95 — the
sweep-tail this item exists for — nearly halves; the cost is now flat in tape/matrix size rather
than linear. `setData` pays ~8 ms once per 2.5 s poll for that.

**New selftest coverage (the first `hover()` coverage the file has ever had).** `ofx.selftest.js`
gains a P2-1 block whose oracle is the OLD algorithm written out verbatim: bucket parity for
prints/sweep, CVD prefix parity from bar 0, depth from the column groups, flow-by-column parity,
one end-to-end `hover()` read, the ms-stamp normalisation, and a bars-only rebuild check. **152 ok,
0 failed** (was 145).

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN**; `ofx selftest 152 ok, 0 failed`; 0 client errors in the sandbox log; sandbox killed,
port 8093 free.

**Files.** `ofx.js` (state.idx, three builders, setData calls, hover rewrite, ribbon prefix),
`ofx-view.js` (`?count=200`), `ofx.selftest.js` (P2-1 block, +7 checks).

**Limits, stated.** (a) `buildPrintIndex` assumes bars arrive in time order (the payload contract;
prints themselves may be unsorted — the binary search handles that). (b) The synthetic gate is a
desktop-class probe: the sandbox's own `renderLayers` timings are unchanged, as they should be —
this item moved hover work only. (c) p50's small delta is reported as measured, not rounded up
into a story.

## §49 — P2-2 recon: the heat pass at 30 Hz over an unchanged matrix

**The ask (sweep §4 R6, verbatim).** "Incremental heat decay; `Float32Array` heat wire format; coalesce
`hover()` into the rAF tick. Gate: `ofx.stats()` p95 under the same synthetic load must improve on
today's numbers (heat 3.58 ms / live 1.34 ms)."

**The baseline and its recipe (sweep §3, §8 — the gate must reuse these exactly).** heat **3.58 ms**
at 48 400 cells, every 33 ms — "~11 % of one core while the Engine view is open" (`SYSTEM_SWEEP_2026-09-15.md:207`);
live/sweep layer **1.34 ms**; the heat payload "136 KB of objects; a `Float32Array` + column/price
header would cut parse and GC" (`:209`); hover measured 0.12 ms/call at 1440 bars (`:210`). The
reproduction recipe is quoted in §8 (`time(heat, 10)` / `time(live, 5)` over `mk(1440, 200, 4000)`,
with `window.OFAP_PAUSED = true` so the view's 2.5 s poll cannot overwrite the injection).

**What the engine actually does today (`ofx.js`).**
- `tick()` (the one rAF loop, `:2,077-2,091`): `heatAccum >= 33 && state.data.heat.length` → set
  `dirty.heat` — **unconditionally, every 33 ms, for as long as a heat matrix exists**, whether or
  not anything changed. Renderer-busy or not, the pass runs.
- `renderLayers()` heat branch (`:2,028-2,047`): `clearRect` the whole canvas → `drawHeat(ctx)` →
  increment `heatPasses`. No version check, no change detection.
- `drawHeat()` (`:1,359-1,482`): binary-search the visible columns, then every visible cell goes
  through live-paint or the ghost branch — so the pass cost is proportional to VISIBLE cells
  (~10-15 k on a 48 k matrix), 30×/s.
- The ghost branch (`size == 0 && alpha > 0.004`, `:1,470-1,475`) is **unreachable from live data**:
  `math.adaptHeat` drops `value <= 0` (`:282`), and the server's `carry_forward` FORWARD-FILLS a
  vanished level with its last size (`depthmap.py:281-291`) rather than zeroing it. The fading-ghost
  machinery is exercised by synthetic zeros (the sweep decorated the matrix with them) and by
  `cell.peak`/`decayAlpha`, not by the live payload — worth knowing before optimising it.

**The lever the server already hands the UI.** The snapshot payload carries **`version`**
(`depthmap.py:306`) and its docstring says so: "the UI can use `version` to skip a repaint entirely
(see the reference layout heatmap author guide's front/back-buffer model)". Nobody reads it yet
(`grep version` under `desktop/ui/` — nothing). The cached-snapshot path re-serves an unchanged
`version` for an unchanged matrix, which is exactly the skip key R6 needs.

**Hover today.** The `mousemove` listener inside `attach()` calls `hover(...)` **synchronously per
event** — a fast sweep fires it many times per frame; P2-1 made each call cheap (p95 3.3 ms on the
10 k gate) but the call COUNT is still unbounded per frame.

**Decisions (do not re-open).**
1. **Heat passes become change-gated, not cadence-gated.** `dirty.heat = true` keeps its name but
   its meaning becomes "repair if needed": the pass runs a FULL repaint only when the heat epoch
   moved (new payload version, view transform, params, resize, expression) and a PATCH pass only
   while fading ghosts exist; otherwise the 33 ms tick does not even set the flag. The full pass
   keeps today's code path (and its cost), so the win is frequency, not per-pass magic — and the
   gate's forced-dirty recipe then measures a no-op when nothing changed, which is the item's own
   language ("only cells whose alpha actually moved").
2. **`version` is threaded through**: `ofx-view` passes `heat.version` into `setData`; a repeated
   version does not bump the epoch (the server's cached-snapshot case). A payload WITHOUT a version
   behaves like today (every delivery bumps) — synthetic tests stay honest.
3. **Ghost patches are bounded and per-cell**: the full pass rebuilds a list of visible ghosts
   (cell + its screen rect); the 33 ms tick patch-repaints only those, and only when a quantised
   alpha step actually changed; a ghost that drops below the 0.004 floor gets its rect cleared and
   leaves the list. `heatPatches`/`heatSkips` join `heatPasses`/`decayCells` in `stats()`.
4. **`resize()` must bump the epoch** — it sets `canvas.width`, which CLEARS the canvas; with
   change-gating a resize without a bump would leave a blank heat layer. Same for `setParams`
   (lambda changes the decay curve; ramp changes the palette — neither dirties heat today) and
   `setExpression` (already dirties).
5. **Hover coalescing**: the `mousemove` listener stores `pendingHover` + `dirty.live`; `tick()`
   runs `hover()` once, immediately before `renderLayers`, so the HUD paints the newest position.
   The selection-drag path keeps its direct `renderLayers` (it is a drag, not a hover).
6. **The `Float32Array` wire waits for its number** (canon §8: "heat-wire formats wait for a number
   that demands them"). Recon measures JSON parse + `adaptHeat` for the live 136 KB payload
   in-page; if that lands under ~5 ms per 2.5 s poll it is deferred WITH the measurement in §50,
   not built on principle.

**Build spec.** `ofx.js`: heat epoch state + `heatNeedsPass()` gate in `tick()`; renderLayers heat
branch full-vs-patch-vs-skip; `drawHeat` records the painted epoch and rebuilds the ghost list;
`patchHeat()` patch pass; `resize`/`setParams` bumps; hover coalescing (listener + tick).
`ofx-view.js`: pass `heat.version`. Tests: `ofx.selftest.js` — epoch-gating unit checks (paint once,
no-op seconds, version reuse skips, resize forces), ghost patch parity (a synthetic zero-cell fades
and its rect clears), hover coalescing (pend + one tick = one hover). Gate harness: the sweep's
recipe before/after, plus a steady-state number and a full-pass number so frequency and per-pass
cost are reported separately.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN; nineteen selftests (ofx 152).

## §50 — P2-2 build: the heat pass stopped running on a stopped matrix (R6)

**What changed.** Three things, one of them with a measured deferral.

1. **The heat layer is change-gated, not cadence-gated.** `state.heatEpoch` moves on a new payload
   version, a view transform, a resize, a parameter or an expression change; `renderLayers`' heat
   branch then paints in full only when the painted epoch lags. `tick()`'s 33 ms cadence asks first
   ("did anything move?") and leaves the flag alone when the answer is no; a forced pass with
   nothing changed counts itself a **skip** (`heatSkips`) instead of a repaint. `resize()` bumps the
   epoch because `canvas.width = …` clears the canvas — the one place where "nothing changed" would
   have been a lie. The server's own `version` field is threaded from ofx-view through `setData`:
   a repeated version (the cached-snapshot case the depthmap docstring invites clients to use) does
   not repaint; a payload without a version always rebuilds, so synthetic tests stay honest.
2. **Ghost decay became a patch pass.** A full pass remembers every fading cell WITH its screen
   rect; `patchHeat()` then repaints only ghosts whose quantised alpha actually moved (≥ 0.008),
   each inside its own rect on the existing canvas, clears a ghost's rect when it dies below the
   0.004 floor, and paints nothing at all when nothing moved. Cost is proportional to what is
   fading, not to what is on screen.
3. **`hover()` is coalesced into the frame.** The `mousemove` listener stores `pendingHover`; the
   tick runs `hover()` once with the newest position, immediately before the layers paint. A fast
   sweep no longer pays one hover per raw pointer event.
4. **`adaptHeat`'s merge keys are numeric.** The old pass built a string key per wire cell
   (`'12|114.39'`) and sliced it apart again; now `barIndex * 1e5 + Math.round(price / step)` with
   the record carrying the price, and the per-column linear scans are binary searches. Off-grid
   float noise now merges with its grid neighbour instead of making a twin row.

**The measured gate (sandbox :8093, same synthetic load both runs: 48 400 cells / 1 440 bars /
4 000 prints, 450 cells visible in the fitted view; the sweep's §8 recipe method).**

| Same load | BEFORE | AFTER |
|---|---|---|
| recipe `heat()` — forced dirty, matrix unchanged | 0.36 ms | **0.02 ms** (counted skip) |
| one real heat repaint (epoch bump, no setData) | 0.36 ms | **0.12 ms** |
| `live()` — sweeps + HUD (recipe method, warm) | 1.52 ms | 1.00 ms (median of 3 rounds; 1.63/1.00/0.97) |
| `adaptHeat`, 48.4 k cells, 3-call average | **36.47 ms** | **25.50 ms** |
| `JSON.parse` of the 842 KB wire | 1.53 ms | 2.37 ms (unchanged code, noise) |
| `setData`'s heat component per payload | (in the old 6–14 ms composite) | 2.6 ms |

**The frequency number is the real win:** the heat pass used to run 30×/s for as long as a matrix
existed — 3.58 ms at 48 k cells on the sweep's own measurement, ~11 % of a core, forever. It now
runs once per payload (0.4×/s at the view's 2.5 s poll) plus patch passes while something fades.

**The `Float32Array` wire — measured, and deferred WITH its number (canon §8).** The sweep expected
"parse and GC" to be the cost. Measured: `JSON.parse` is **1.5–2.4 ms** for 842 KB — not the
problem. The problem was `adaptHeat` (36.5 → 25.5 ms after the numeric-key rewrite; the residual is
per-cell object + Map allocation, ~0.5 µs/cell). A typed wire would delete exactly that allocation —
so the item now has its trigger number instead of a hunch, and the transport rewrite is a follow-up
card rather than a rushed change in this pass. Stated plainly: one third of R6's named scope is
deferred, and this paragraph is why.

**New selftest coverage: 152 → 169 checks (all green).** The first heat-gate and coalescing coverage:
a stubbed heat canvas counts full clears vs rect clears; a new version paints once; an unchanged
epoch is a counted skip; a repeated server version does not bump; resize and lambda changes do bump;
a ghost patch-repaints only on quantised movement, keeps its alpha, and clears its rect on death;
`adaptHeat` parity for merge/summation/events/float-noise/boundary buckets; and `mousemove` pends
(newest wins) without running hover per event, with out-of-canvas moves ignored.

**Files.** `ofx.js` (state epochs + ghosts + pendingHover, `markHeatFull`, setData versioning,
markViewDirty/resize/setParams/setExpression bumps, renderLayers heat branch, tick gate + hover
consumption, drawHeat ghost rects, `patchHeat`, stats fields, adaptHeat rewrite), `ofx-view.js`
(version threading), `ofx.selftest.js` (+17 checks).

**Limits, stated.** (a) The patch pass clears each ghost's rect; with the 1 px minimum row height a
rect can nibble a neighbour's edge pixel — accepted, invisible, noted. (b) The ghost path is still
synthetic-only in live data (`carry_forward` forward-fills; `adaptHeat` drops zeros) — R6 made it
cheap and tested, not live; that is the separate carry-forward item. (c) rAF can be dead in a
headless page, so the tick's own consumption of `pendingHover` and the cadence gate are pinned by
the selftest and the code path, not by a real frame loop in the sandbox. (d) The sweep's 3.58 ms
was measured at ~10–15 k visible cells; this pass's matrix shows 450 in the fitted view, so the
BEFORE/AFTER pair above is the comparison, with the sweep's figure quoted as the historical
reference for the same code.

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN**; `ofx selftest 169 ok, 0 failed`; 0 client errors in the sandbox log; sandbox killed,
port 8093 free.

## §51 — P2-3 recon: the yielding question is a measurement, and nothing else

**The ask (plan §2, verbatim).** "**P2-3 · Heat-layer yielding — conditional.** S. Render heat in one
rAF and base+live in the next *only if* a 30 k-cell / 4K measurement crosses the 16 ms frame budget.
Norm: defer complexity behind a measurement (§3.8). Gate: the measurement itself."

**What "the measurement" has to be, stated before taking it.** Post-P2-2 the only heavy frame the
engine can produce is a **payload-arrival frame**: `setData` dirties all four layers, so heat + base +
live + ribbon repaint inside one `renderLayers()` call at 4K (3840×2160) with a 30 k-cell matrix.
Steady-state frames are already gated to near-zero (§50). So the number that decides this item is
that one frame's cost, compared against the 16 ms budget — plus its heat/live decomposition so a
"yes" would know where to yield (heat first, base+live next).

**What exists to yield with (if the number says yes).** The scheduler already has the shape for it:
`renderLayers()` takes an explicit job list; `tick()` calls it once per frame; every layer is
independently dirty-flagged. The minimal yielding change would be: when a frame's job list contains
heat AND (base or live) AND the frame budget is at risk, paint heat this frame and leave base+live
dirty for the next tick — with stats telling the truth about the split (a `yielded` counter, and the
frame's `lastMs` still the real cost of what it painted).

**What the plan itself says about the bar.** Brief §6: "The engine is Canvas2D by design (4.5 ms full
repaint, 3 layers, 200 bars × ~128 levels). Revisit only for > 2 k simultaneous cells or forced
4K/144 Hz". The sweep's optimised per-cell constants: 0.074 µs/cell heat after the palette LUT, 1.34 ms
live repaint. On those numbers a 30 k-cell matrix is ~2.2 ms of heat work plus canvas clear costs —
which is why the item is phrased as *conditional*: the honest expectation is a sub-budget frame, and a
custom yielding layer would be complexity nobody asked for. This pass will not build it on a hunch —
the measurement is the deliverable either way, and if it lands under budget the item closes as a
measured no-op with the numbers recorded.

**Also noted, for the record.** Brief §6 flags "4K at Windows 150% scaling is untested; fractional DPI
costs a full re-raster on resize". The resize path (`ofx-view.js:707/770/777/846` → `OFX.resize(w, h)`)
uses the stage element's CSS pixels — the app does not multiply by `devicePixelRatio`, so a 4K screen
at 150 % presents a ~2560×1440 canvas, and the 3840×2160 case measured below is the DPR-1 worst case,
not what that machine runs. The canvas is whatever `resize()` is handed; the measurement uses both.

**The recipe (sandbox :8093, both runs on the same page).**
1. Build the §50 synthetic load: 1440 bars × 200 levels × 4000 prints; 30 k heat cells (150 columns ×
   200 rows) shaped like the live matrix, sized so a 4K viewport actually shows ~30 k of them.
2. `OFX.resize(3840, 2160)`; verify the canvas dimensions took (`state.view.width/height`).
3. Set the view (scaleX/scaleY/offX/offY) so the matrix fills the viewport; count visible cells
   through the same cull `drawHeat` uses.
4. Time, 3 rounds each, with a fresh heat version per round:
   (a) the full arrival frame — `setData(heat vN)` + `renderLayers(false)` with all layers dirty;
   (b) heat alone — epoch bump + heat-only job;
   (c) live alone — the sweep recipe's `live()`.
5. Verdict rule: (a) ≤ 16 ms → P2-3 closes as a measured no-op. (a) > 16 ms → build the yield split
   (heat this frame, base+live next), re-measure, and require (a-split) frames under budget with the
   same picture.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN; nineteen selftests (ofx 169).

## §52 — P2-3 build: the frame yields, and the number said it had to

**The measurement crossed the bar (§51's rule applied).** 30 000 cells, all visible, canvases
3840×2160 (`dims` verified for all three layers): one payload-arrival frame measured **17.5 ms** —
over the 16 ms budget — decomposed heat **6.8** + base **5.9** + live **1.57** + ribbon **0.77**.
So P2-3 built the yield.

**What changed (`ofx.js`, ~20 lines).** `renderLayers()` now walks its job list with an index and,
once a frame has painted something and spent `YIELD_MS = 6` ms (a third of the 16.7 ms budget),
**breaks before the next layer**: the deferred layers keep their dirty flags, so the next tick — one
rAF later — re-queues and paints them. A single-layer job can never yield (nothing to defer to), and
the two-tick picture is identical, one frame later. `stats()` gains `yields` so the split is visible,
and every frame's `lastMs`/p95 remains the REAL cost of what that frame painted.

**Same-session A/B (the honest pair — earlier cross-session numbers wobbled ±30 % with page state,
so the pre-build file was swapped in briefly and the identical script run on the same page).**

| Arrival frame(s), warmed, same page | PRE-YIELD | POST-YIELD |
|---|---|---|
| frame 1 | **13.9–14.1** (cold 20.1) | 11.5–12.4 (cold 17.1) |
| frame 2 | — (nothing left) | 6.0–8.1 |
| frame 3 | — | 0.3–1.5 |
| max frame | 14.1 (20.1 cold) | **12.4 (17.1 cold)** |

**The honest read.** The stacking is gone — nothing ever adds base+live to the heat frame again, so
the worst warm frame is the heat pass itself (~11.5–12) and the rest drains in two small frames. The
cold first arrival still touches ~17 ms because the heat pass alone at 4K/30k is the remainder, and
**no frame split can divide one layer** — that residue is exactly what brief §6's revisit condition
(>2 k simultaneous cells / forced 4K) hands to P3-1's trigger, not to more splitting. Per-frame p95
under the same load: 12.4 vs 14.1 warm, 17.1 vs 20.1 cold.

**Picture parity.** After the split, a subsampled ink scan of all three 4K canvases: heat 836, base
12 361, live 10 sample hits — every layer painted; nothing ended up blank when its frame was deferred.
(The live layer's ink is genuinely sparse — a handful of sweep bubbles — in both the 4K and the fitted
view; checked both.) Two earlier probes that read zero were my own geometry mistakes (a centre crop
that missed the heat band; a centring computed for the wrong price), not the engine — recorded so the
next reader does not chase them.

**New selftest coverage: 169 → 174 (all green).** The yield's contract is pinned with a stubbed heat
canvas that spends 7 ms in its first clear: the frame defers base+live (yields +1, flags left SET),
the next frame finishes them and clears the flags, a fast frame paints the whole job in one pass, a
single-layer frame never yields even when slow, and `stats()` reports `yields`. The stub uses a
self-returning callable Proxy for the 2D context — fifty no-ops for free.

**Files.** `ofx.js` (YIELD_MS, the renderLayers loop + yield, stats.yields), `ofx.selftest.js` (+5).

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN**; `ofx selftest 174 ok, 0 failed`; 0 client errors in the sandbox log; sandbox killed,
port 8093 free.

## §53 — P3-2 recon: the session boundary and the 807 MB that nobody prunes

**The ask (plan §2 P3-2, verbatim).** "P3-2 · Session model (R4) and storage retention (R5). M"
— rendered in the plan as: "sessions at the UTC boundary; make the boundary a config value and
compute profiles per session. Retention: no pruning exists — 5.8 M rows / 547 MB and ~4.5 M rows/day;
add an age/size retention job with incremental vacuum and surface the DB size in Logs. Gate: unit
tests on the session-window function; run retention, read row counts and file size before/after."

**The number has moved.** The live DB at `%APPDATA%\\OrderFlowAnalysisPro\\orderflow_data.db`
measured **807 755 776 bytes (807.7 MB) today**, up from the sweep's 547 MB five days of uptime ago —
the growth estimate is holding. There is still no retention path anywhere (`database.py`, `main.py`,
`desktop/`).

**What exists — session side.**
- `main.py:_rebuild_volume_profile` (`:677-692`): takes `now_ms - 24 h` of 1 m candles and labels
  the profile `session_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")` — a rolling 24 h
  window wearing a calendar-day name. At the UTC boundary the "day's" value area mixes two sessions;
  anything else would need the label to lie differently.
- `analytics/volume_profile.py` carries `session_date` strings through
  `compute_from_candles/ticks` and `combine_profiles` (which merges labels into
  `"{first}_to_{last}"`); `atlas/profiles.py` exposes them read-only. No other session semantics
  exist anywhere — no session-window function, no boundary config.

**What exists — storage side.**
- Schema: `ticks(id, instrument, timestamp_ms, price, size, side, trade_id)` with the index
  `idx_ticks_instrument_ts(instrument, timestamp_ms)`; `candles` (idx by instrument+ts+tf),
  `volume_profiles`, `signals`, `trade_journal`. Insert path: batched every 100 ticks
  (`main.py:_handle_tick`).
- Pragmas (`database.py:26-34`): `journal_mode=WAL`, `busy_timeout=15000` (plus the P1-era
  `synchronous=NORMAL` note). **No `auto_vacuum`** — so a delete alone will never shrink the file;
  `PRAGMA incremental_vacuum` is a no-op until the DB is converted once with a full `VACUUM`.
- The periodic home exists: `main.py:_periodic_tasks` (`:628+`) — a 10 s loop that already flushes
  tick buffers and rebuilds the VP hourly. A retention pass slots in as one more interval block.
- Surfacing: the Logs view renders from `GET /api/control/logs` (`ui.js:1227` `loadLogs()`,
  clear at `:1238`); the storage numbers have no route and no line anywhere.

**Decisions (do not re-open).**
1. **One session function, one config value.** New `analytics/session.py`:
   `session_window(now_ms, start_hour) -> (start_ms, end_ms, label)` — pure UTC, boundary hour on the
   most recent day at or before `now`, label = the session's start date (`YYYY-MM-DD`, the same
   string shape `session_date` always carried, so stored profiles stay comparable). Config:
   `data.session_start_hour`, default 0 (UTC midnight), clamped 0–23, junk falls back to 0.
   `_rebuild_volume_profile` fetches `[session_start, now)` candles and labels with the window's
   label — the boundary mixing dies there.
2. **Retention is age-based on `ticks` only** (the table that grows: 1 m candles × 3 symbols ≈ 4 k
   rows/day, signals smaller). Config `data.retention_days` (default 30; 0 = keep forever) and
   `data.prune_interval_hours` (default 6; the first pass prunes at system start).
3. **Batched deletes through the existing index** — SQLite here has no `DELETE … LIMIT` (not
   compiled in), so each batch is `DELETE FROM ticks WHERE rowid IN (SELECT rowid FROM ticks WHERE
   instrument = ? AND timestamp_ms < ? LIMIT 50000)` — per instrument, because the index leads with
   `instrument`. One commit per batch; the writer never blocks for long.
4. **Vacuum is explicit.** First prune after the config lands: convert once
   (`PRAGMA auto_vacuum=INCREMENTAL` + full `VACUUM` — bounded, logged, once), then
   `PRAGMA incremental_vacuum` after every prune. If the conversion fails on a locked DB it is
   reported and retried next interval, never faked.
5. **Numbers surfaced where the user looks for them**: `GET /api/control/storage` (30 s cache —
   `COUNT(*)` over 8 M rows is not free) → `{db path, bytes, wal bytes, per-table counts,
   oldest/newest tick, retention settings, last prune summary}`; `POST /api/control/storage/prune`
   runs one pass now (the gate's trigger, and a real button later); one line in the Logs panel.
6. **Gate**: unit tests on `session_window` + a VP comparison across a simulated boundary (R4);
   retention run against a COPY of the live 807.7 MB DB with row counts and file size read back
   before/after (R5), plus a live sandbox pass for the route + the panel line.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN; nineteen selftests (ofx 174).

## §54 — P3-2 build: the session has a boundary, the database has a window

**R4 — session model.** `analytics/session.py` is new: `session_window(now_ms, start_hour)` returns
`(start_ms, end_ms, label)` — the boundary hour on the most recent day at or before now, UTC, with the
session's start date as the label (`YYYY-MM-DD`, the shape `session_date` always carried, so stored
profiles stay comparable). Junk hours fall back to 0 rather than raising (it reads config).
`_rebuild_volume_profile` now fetches `[session_start, now)` candles and labels them with the window —
the rolling 24 h wearing a "today" label is gone. Config: `data.session_start_hour` (default 0),
clamped by the pure `clamp_data_settings()` the tests call directly.

The boundary demonstration is a test, not a claim: with sessions at 100.0 and 110.0 across a simulated
UTC midnight, the mixed profile (old behaviour) POCs at **100.0** while the windowed profile POCs at
**110.0** and contains only the new session's candles.

**R5 — storage retention.** The copy of the live DB spans 2.15 days at **7 810 787 tick rows**; the
job is now real:

- `database.prune_ticks(cutoff, instruments, batch)` — per instrument (the index leads with it), in
  50 k-row rowid-subquery batches (this SQLite has no `DELETE … LIMIT`), one commit each.
- The instrument list comes from the DB itself (`SELECT DISTINCT instrument FROM ticks`), not from the
  boot's enabled symbols — the first draft pruned only BTCUSDT, caught before the gate.
- Vacuum: one-time `auto_vacuum=INCREMENTAL` + full `VACUUM` on the first prune that deletes anything
  (`vacuum: converted`), then `PRAGMA incremental_vacuum` + **`wal_checkpoint(TRUNCATE)`** per pass.
- The job lives in `_periodic_tasks` (first pass at engine start, then `data.prune_interval_hours`,
  default 6 h; `retention_days: 0` disables). It never kills the loop: failures warn and retry.
- Surfacing: `GET /api/control/storage` (30 s cache; counts need the engine, sizes never do — and with
  the engine stopped the RETENTION line reads the config file, not the Python defaults, because a
  display lie is a lie), `POST /api/control/storage/prune` (409 without an engine), and one live line
  in the Logs panel.

**The gate, at real scale (a copy of the live 807.7 MB DB; the original verified untouched at
807 755 776 bytes after the pass).**

| | before | after |
|---|---|---|
| ticks | 7 810 787 | 2 264 231 (−4 446 640) |
| plain `.db` | 808.6 MB | **336.4 MB** |
| `.db` + WAL footprint | 845.5 MB | **336.7 MB** (after the checkpoint fix) |
| pass time | — | **15.6 s** (delete + convert + vacuum) |
| second pass | — | 769 boundary rows, `vacuum: already`, 0.4 s |

Live reads: the Logs line renders `storage: 336.8 MB · 2.3 M ticks · keep 1 d · last prune −33 rows`,
and the −33 is the periodic job's own unattended pass. Two fixes came out of the gate itself: the
WAL balllooned to 677 MB mid-prune until `wal_checkpoint(TRUNCATE)` was added (the file "shrank"
while the footprint did not — the exact kind of half-truth this program keeps deleting), and the
stopped-engine retention display read defaults instead of the config.

**The default that had to change.** Retention shipped at 30 days until the gate arithmetic: 2.15 days
measures 808 MB, so ~376 MB/day — 30 days is an **~11 GB** steady state, wrong for this app. The
default is **7 days (~2.6 GB)** in `settings.py`, the config block, the clamp and the tests.

**Behaviour change for the owner's install, stated plainly.** With no `data` block in
`%APPDATA%\\OrderFlowAnalysisPro\\config.json`, the next launch applies the 7-day default; **nothing
in the current DB is older than that**, so the first live prune deletes nothing today and the DB holds
at 7 days going forward. `"retention_days": 0` in the config keeps everything. The retention job only
ever touches `ticks`; candles, signals and volume profiles are kept (tiny, and history the profiles
need).

**Files.** New: `analytics/session.py`, `test_session.py` (6), `test_retention.py` (3). Edited:
`config/settings.py`, `data/database.py`, `main.py`, `desktop/engine.py` (`clamp_data_settings`),
`desktop/config_store.py` (`data` block), `desktop/api.py` (storage routes), `ui.js` +
`index.html` (the Logs line).

**Gates after the build (measured this pass).** pytest **580 passed / 2 skipped** (572 + 8); `audit_ui_refs.py`
**AUDIT CLEAN**; nineteen selftests green; 0 client errors in the sandbox log; sandbox killed, port free,
the 800 MB sandbox copy deleted.

## §55 — P3-3 (R7) build: the legacy page retires behind a redirect

**The decision (the owner's, from the retirement options laid out in the session).** The legacy
dashboard page — `dashboard/static/index.html` + `app.js` + `style.css`, the one-screen "Orderflow
Trading Terminal" with its 1 s whole-series price chart and scanner — stops being the front door.
**Redirect**, not delete: `GET /` answers **307 → `/desktop`**, the desktop shell. Reversible by
deleting one block; nothing on disk removed.

**Why redirect was the right shape.** Recon found the retirement is nearly free: the desktop server
is built ON the dashboard app (`launcher.py` imports `dashboard.app.app`, includes the control/atlas/
fundamentals routers into it, and mounts the shell at `/desktop`), and **six of the nine static
files are shared modules the desktop UI loads itself** (`footprint.js`, `orderbook.js`, `tape.js`,
`signals.js`, `performance.js`, `microstructure.js` — `desktop/ui/index.html:818-823`). Only the
three shell files are "the page", and both of its panels are superseded (the desktop's chart view
with the expression modes; the rebuilt scanner). The legacy page also still works standalone
(`main.py`'s own dashboard), which is why the redirect lives in the LAUNCHER — the standalone
dashboard is not redirected to a path it does not mount.

**The build.** One block in `launcher.build_app()`, inside the desktop-mount guard (now idempotent —
a second call no longer double-mounts): remove the dashboard app's own `GET /` route, register
`legacy_root_redirect()` returning `RedirectResponse("/desktop", status_code=307)`. 307 preserves the
method and is not sticky-cached, so undoing the retirement is deleting the block.

**The gate (live, sandbox).** `GET /` → **307**, `location: /desktop`; following it lands on the
desktop shell (`ModFlow OrderFlow Analysis Suite`, and *not* "Orderflow Trading Terminal") — pinned
as a test as well (`test_wiring.py::test_legacy_root_redirects_to_the_desktop_shell`, via
`TestClient(build_app(8099))`). The static files remain served (shared modules); the standalone
dashboard keeps its own page.

**Gates after the build (measured this pass).** pytest **581 passed / 2 skipped** (580 + 1);
`audit_ui_refs.py` **AUDIT CLEAN**; nineteen selftests green.

## §56 — the deferred Float32Array wire + the carry-over list: recon and decisions

**A. The heat wire (deferred from §50 with its number).** §50 measured `adaptHeat` at 36.5 → 25.5 ms
per 48.4 k-cell payload after the numeric-key rewrite; parse was only ~2 ms. The residual is the
per-cell work: JSON arrays-of-arrays traversal, `Number()` conversions, the Map merge, and — found in
this recon — **two allocations per cell** (`acc.set(key, {v, price, col})` and then a second row object
in the row-build loop). Decisions:
1. **Halve the allocations in the JSON path first**: the Map value IS the row object (mutated
   `size +=`), pushed directly — one object per cell, same merge semantics.
2. **A binary sibling route** `GET /api/atlas/heatmap/{symbol}/bin` (atlas/api.py, same params):
   `atlas/wire.py:pack_heatmap_bin(snapshot) -> bytes` — magic `OFHB` + u32 header length + header
   JSON (symbol, version, step, tick, cols, rows, carry_forward, carried_cells, scale_max,
   wall_age_ms, walls, events, traded flag, note) + sections: buckets `f64[cols]` (epoch ms —
   Float32 cannot hold them exactly), prices `f32[cols×rows]`, values `f32[cols×rows]`, traded
   `f32[cols×rows]` (skipped when absent), best as 12 B/col (`f32 bid, f32 ask, i32 trades`). JSON
   events/walls ride in the header — they are small and keep one source of truth.
   `Response(media_type="application/octet-stream")` + `Cache-Control: no-store` on the response.
3. **The client** (`ofx.js math`): `decodeHeatBin(buffer)` (DataView header, `slice`-copied typed
   sections so alignment is guaranteed) and `adaptHeatBin(decoded)` producing the SAME
   `{rows, scale, traded, best, events, version}` shape with the same numeric-key merge and the same
   `mapCol` fallback; `ofx-view.load()` fetches the bin route with a **raw fetch and JSON fallback**
   on any failure. `heatmap-pro.js` / `atlas.js` keep the JSON route (their DOM paths were never the
   measured cost).
4. **Gates**: a Python round-trip test (pack → decode → sections equal the dict), a node parity test
   (a fabricated bin buffer through `decodeHeatBin`+`adaptHeatBin` deep-equals `adaptHeat` on the
   equivalent dict, empty case included), and a live sandbox measurement of the real hub payload both
   ways.

**B. Carry-overs, by site.**
1. **Chart's newest bar loses expression colours between polls.** `ui.js:403` — the WS `candle`
   handler calls `S.candleSeries.update({time, open, high, low, close})` plainly. The broadcast
   payload also carries `volume` and `delta` (main.py:565-573), and the expression module
   (`E.chartBars`) is already in scope at other call sites in the same file. Fix: run the single bar
   through `E.chartBars([bar], {mode, palette, theme})[0]` before `update()`, falling back to the
   plain point when the expression module or data is missing. Gate: live — with a delta/expression
   mode set, the newest bar's `color`/`borderColor` as returned by `series.data()` must match the
   mode after a `candle` broadcast.
2. **Three `window.prompt` sites.** `drawings.js:365` (Edit text…, inside the draw context menu),
   `drawings.js:417` (the text tool's canvas click), `menubar.js:562` (workspace save as). The house
   pattern already exists twice: `menubar.js:276 askText()` renders an in-place editor INSIDE the open
   menu (used by the layout menus), and heatmap-pro's note field commits without any dialog. Fix:
   menubar's own site uses `askText` directly; the two drawings sites get a small in-place editor
   drawn into the draw-menu (an input + Apply/Cancel row, Enter/Esc/blur semantics) — no system
   dialogs, nothing that can silently no-op in the frozen WebView.
3. **Bus chip `sub` count.** `bus.js:344-346 summary()` reads `telemetry().subscribers` — the same
   `subscriberCount()` the tests compare against — and the comments at `:134-178` record the
   announce-after-join fix that closed the old drift. Verdict: likely already fixed; **verify live**
   (chip text vs `OFAPBUS.telemetry()`), and close the carry-over row as already-fixed with the
   evidence if it holds.
4. **Alerts card has no "new rule" affordance.** The rules table (`atlas.js` `AL.rules`,
   `renderRuleRows`, the row-replacing editor `openEditor(id)` — P1-7) can edit existing rules and
   save via `POST /api/atlas/alert-rules` (`:780-783`, upsert by id). Fix: a "+ New rule" button in
   the rules head that pushes a DRAFT rule (`ui-<ts>` id, first kind from `F.kinds()`, `enabled:
   false`, `channels: ['ui']`, empty params), opens the existing editor on it, and drops the draft
   from the list if the editor is cancelled (a draft must never silently become a saved rule).
5. **`wall` kind has no live detector.** `atlas/alerts.py` already matches `kind == "wall"`
   (size ≥ min_size) but `depthmap.py` only ever emits `wall_age` (and stack/pull). The ingest block
   (`:164-195`) already computes the quantile threshold and tracks `_walls`/`_wall_first`. Fix: emit
   `wall` **on entry** — a price whose previous size was below the threshold and whose current size
   meets it — with the visible-book share in the detail. Entry-triggered, so a standing wall fires
   once and `wall_age` keeps the hold. Gate: a unit test feeding two synthetic snapshots (below →
   above) asserts exactly one `wall` event with the share, plus the no-requalify case.
6. **Watchlist configured-instrument rows.** Verification-only, per the RECIPE row: add a symbol to
   the sandbox config's instrument list, reload, and the watchlist must show its row beside the demo
   set. No code change unless the row is missing.

**Gates at recon time.** pytest 581/2; audit CLEAN; nineteen selftests (ofx 174).

## §57 — the Float32Array wire (measured, kept as machinery), the carry-over list, and two defects the live gate found

**The wire, built and then measured out of the default path.** `atlas/wire.py:pack_heatmap_bin`
(magic `OFHB` + u32 header length + header JSON + f64 buckets + f32 prices/values/traded + 12 B best
per column) serves `GET /api/atlas/heatmap/{symbol}/bin`; `math.decodeHeatBin` / `adaptHeatBin` read
it; `test_heat_wire.py` round-trips the layout and the ofx selftest pins bin-vs-JSON parity. The live
sandbox then priced it: **json parse+adapt 0.8 ms vs bin decode+adapt 0.7 ms at 29 k cells (610
rows), and 1.7 vs 1.2 ms at 51 k cells** — and **the bin is BIGGER than the JSON on sparse books**
(229 KB of JSON vs 296 KB of bin: fixed 4 B per cell per section beats nothing when most cells are
`0,`). The verdict: the JSON route stays the engine view's path (the view was reverted to it); the
wire stays on the shelf, tested and one fetch away, with its trigger written down — **re-measure when
a snapshot's JSON text passes ~2 MB or an adapt pass passes ~8 ms**. The §50 number that motivated
the wire (adapt 25.5 ms / 48.4 k cells) did not survive §56's own rewrite of the adapter; that is
stated here so nobody quotes it again.

**The defect the wire's parity gate exposed — the depth payload's axes.** The snapshot contract is
`values[PRICE ROW][TIME COLUMN]` with `prices` the flat ladder (`depthmap._build_snapshot`:
`values = [[0.0] * len(cols) for _ in range(rows)]`, `prices = [price_min + i * step …]`), and
`heatmap-pro` has always read it that way (`vals[ri][ci]`). **`adaptHeat` had the axes transposed** —
it iterated the outer array as columns, so a live payload was drawn as "the first ~33 price rows at
the bottom of the ladder": the heat sat in the wrong price band, and §52's "ink probes read 0 twice /
heat centred on the wrong price" were **this defect**, not a crop mistake (that §52 note is hereby
corrected). Fixed in `adaptHeat` (row-major: price row outer, bucket column inner, per-column price
fallback kept) and every fixture in the selftest rewritten to the real contract. Live A/B on the same
payload: **old rows n=253 median 75 808 (ladder bottom 75 780.6) vs new rows n=483 median 75 846 —
the ladder mid — with the live best bid/ask at 75 844.3/75 844.4**; the view's own render path
(`setData` with spanning bars) produced 939 rows centred on the book and the heat layer painted
(`heatPasses` 35→36). The wire packer/decode were built on the same contract; the ofx selftest now
pins the row-major fixtures, both modes, and the bin↔json deep-equality.

**The bus fetch wrapper ate binary bodies (found live).** `bus.js` wraps `window.fetch` for
`/api/atlas/` and reads every response as JSON — for the octet-stream `/bin` payload that consumed the
body and the non-JSON fallback then handed the caller the **consumed** original: every bin fetch died
with `body stream already read` and the engine view silently fell back (a fallback that worked only
because the view still had the JSON path). Fixed: non-JSON content types now pass through **unread**,
each caller gets its own `response.clone()`; the JSON-parse-failure branch returns an empty rebuilt
body instead of a consumed response. `bus selftest 13 ok, 0 failed`.

**The new-rule affordance, and the silent no-op it uncovered.** `+ New rule` (index.html, bound in
atlas.js) pushes a draft (`ui-…`, first kind from `F.kinds()`, disabled, `channels:['ui']`) and opens
the existing row editor; cancelling drops the draft. Live: the draft→editor→save flow first **no-opped
in total silence** — the rules auto-refresh adopts the server list (line 634's direct
`AL.rules = r.rules || []` — `alAdopt`'s guard alone was not the site) and clobbered the draft out of
`AL.rules` seconds after it was created, so `saveRule` found no stored rule and returned. Both adopt
sites now preserve drafts. Live, after the fix: banner `saved · Big trade — at least 1.00K in size ·
any level · UI log only · no cooldown`, the server list at 17 with `P56 live check` (kind `big_trade`,
`min_size: 1000`); cancel took the row count 18→17 with no draft left.

**The rest of the carry-over list, verified live.**
- **Chart's newest bar keeps its expression colours** — the WS `candle` handler now paints the single
  bar through the same `E.chartBars` pass as the full repaint (plain-bar fallback on any throw). The
  audit resolves the call; the broadcast payload carries `volume`/`delta` (main.py:565-573); the
  handler's own live wake-up is **not observed** — the WS lives in `ui.js`'s closure with no reachable
  handle for a second listener, so this one is verified by audit + the expression suite, stated as such.
- **All three `window.prompt` sites are gone.** The workspace name now goes through the menubar's own
  `askText` (in-place, in the open menu; both workspace items set `keepOpen` — without it the menu
  closed before the editor could render). Live: File → Save workspace opened the in-place editor, Apply
  saved `P56 live workspace` to `/api/control/workspaces` (view + ofx params + stamp). The two drawing
  text sites use a new `inlineText` editor: the draw menu gets an input row (Enter/Apply/Esc/×; the
  menu stays open), the canvas text tool gets a floating field at the click point (Apply/Enter commits
  and finishes the figure; Esc/× removes the placeholder). Live: menu path — editor prefilled
  `P56 inline`, Apply → text updated, menu closed; canvas path — float appeared, Enter committed
  `{kind:'text', text:'P56 inline'}`; both editors gone after commit. `window.prompt` now appears only
  in comments (5 references, all copy explaining why it is not used).
- **Bus chip** — live `bus: 1 sub · 1 ch · 1 fetches` against `telemetry()` `{subscribers: 1,
  channels: 1}`: they agree. The §29 mismatch row was stale (the announce-after-join fix closed it);
  row retired with this evidence.
- **`wall` kind has a live detector** — `depthmap` now emits a `wall` event when a price ENTERS the
  quantile band (previous size below the same threshold), carrying its share of the visible book in the
  detail; a standing wall fires once and `wall_age` keeps the hold. Unit-pinned (entry once, no
  re-fire, fresh crossing adds exactly one); live: **76 `wall` events in the rolling 120-event window**
  with 12 held walls in the snapshot.
- **Watchlist configured-instrument rows** — the recipe ran live: `ZZZTEST` (copy of a real instrument
  block, `pipelines: []`) in the sandbox config → reload → the watchlist renders its row
  (`SPAN.wl-sym: 'ZZZTEST'`). No code change needed; row retired.

**Gates at close.** pytest **585 passed / 2 skipped** (581 + `test_heat_wire.py`'s 4); **AUDIT CLEAN**;
the nineteen selftests green (ofx **178** ok — +4 wire checks; bus 13; the rest unchanged); 0 page
errors in the live pass (error + rejection collectors installed). Sandbox killed, port 8093 free, the
temp tree deleted; the real APPDATA was never touched (the sandbox ran its own 45 KB DB — the config
copy carries no absolute paths). Tree: **49 modified + 19 new**, HEAD `fa202d6`, nothing committed.

## §58 — P3-1's trigger, measured on the owner's actual hardware; and the options/fundamentals residue

**The trigger text.** Brief §6: "revisit only for > ~2 k simultaneous cells or forced 4K/144 Hz; if you
do, keep the coordinate matrix". Plan §P3-1: "WebGL for the heat layer only — deferred with a trigger.
… port only `drawHeat()` to a point-sprite mesh". Plan addendum: "Do not port WebGL without the trigger
conditions being met and measured."

**The measurement that decides it.** The owner's panel (this machine, queried via `Win32_VideoController`)
is a **2560×1440 @ 144 Hz** display — the 144 Hz case is his DEFAULT, not a hypothetical, and 144 Hz is
a **6.94 ms** frame budget. Against that: §52 measured the post-yield warm frame at **11.5–12.4 ms at
30 k cells / 4 K**, of which the **heat pass alone is the residue** (`no frame split can divide one
layer`), and cold arrival at 17.1. On this pass's readings the *interactive* case is worse than the
arrival frame implies: a pan/zoom drag sets `state.dirty.heat` every mousemove, so **every drag frame
paints 30 k `fillRect`s** — the heat pass runs per frame, and on a 144 Hz panel that is ~1.7× over
budget for the whole duration of the gesture. Simultaneous cells: a default 300×260 heat request on
the live book is ~29 k cells — an order past the brief's "> 2 k". **Both sides of the revisit
condition are met, on his machine, today.** Decision: build P3-1 — port ONLY `drawHeat()` to a WebGL
mesh, keep the coordinate matrix, keep the Canvas2D painter as the fallback.

**Why the code shape is friendly to this.** P2-3 already split the engine into per-layer canvases
(`ofxHeat` / `ofxBase` / `ofxLive` / `ofxRibbon`), so the heat layer is its own DOM canvas with exactly
one 2D consumer; a canvas may hand out only one context type, so the port means `ofxHeat` gets a
`webgl2`/`webgl` context and the 2D heat path is skipped wholesale when it succeeds. The heat canvas
has no 2D-only work: ghosts (decay) can ride the same shader as a small dynamic buffer. The transform
stays CPU-side for everything else (hover, cookies, axes); the shader receives it as the linear map
`x = ax·col + bx, y = cy·price + dy` — the mesh itself is therefore **scale-independent and rebuilt
only when the payload changes**, which is the entire point: pan/zoom becomes two uniform writes.

**Fallback rules.** No WebGL context (headless probes, old drivers) → the existing 2D painter runs
untouched; the selftests keep exercising the 2D path through their stub contexts; `stats().heatBackend`
says which one painted. The 4 selftest checks for the heat layer (P2-2 epoch/patch/skip/ghosts) must
stay green on the 2D path and the live pass must pin the GL path by pixels (`readPixels` ink) and by
the same epoch/gating counters.

**The options/fundamentals residue.** §25 fixed both entries (the Fundamentals supply cell builds its
`of 21.00M max` fragment as a real child element, flagged, everything else escaped; `options.js
fmtGreek` renders a non-zero sub-milli value as `n.toExponential(2)` so "no gamma" and "1e-05 gamma"
stay different statements) — but recorded the honest gap: **"the live click-through was not captured —
the probe waited 6 s inside one js() call and the harness times out at ~5 s. The rule is
test-pinned, not eyeballed."** This pass captures both live in the sandbox (the fixed tooling polls
outside the `js()` call, so the timeout no longer applies), reading the rendered DOM of the
Fundamentals supply cell and the Options gamma/greeks cells.

**Gates at recon time.** pytest 585/2; AUDIT CLEAN; nineteen selftests green (ofx 178).

## §59 — P3-1: the trigger measured against the owner's hardware (NOT triggered); the options/fundamentals residue closed

**The hardware.** This machine's panel (queried this pass via `Win32_VideoController`): **2560×1440 @
144 Hz** on an RTX 4050 laptop. A 144 Hz frame is **6.94 ms**; his app runs windowed (the app's stage
measured 2022×780 in classic full view at that window size).

**The measurements (all warm; forced heat passes via `state.heatEpoch += 1`; sync-block timing; the
current build — post-P2-3, post-§57).**

| shape | viewport | drawn cells | heat pass med / p95 / max |
|---|---|---|---|
| real payload, max server shape (900 buckets × 400 rows → merged) | 2022×780 (his panel) | 1,694 | **0.6 / 0.7 / 0.7 ms** |
| real payload | emulated 4K-wide (3336×898) | 1,809 | **0.7 / 0.8 / 0.8 ms** |
| synthetic 30 k cells (§52 shape) | 2022×780 | 30,000 | 1.3 / 1.6 / 1.7 ms |
| synthetic 30 k cells | emulated 4K-wide | 30,000 | 2.2 / 2.6 / 2.6 ms |

Full forced frame (heat+base+live in one frame) with this pass's thin fixture: 0.7–0.9 ms (real, his
res), 1.4–1.6 ms (30 k). The base layer's own share with real footprint/print data is not the heat's
and P2-3's yield already splits multi-layer arrival frames.

**Why the real drawn count is ~1.7 k, not 30 k.** The payload contract bounds it: his config (read
this pass) is `atlas.heatmap: { bucket_ms: 1000, max_columns: 900 }` — 15 minutes = ≤ ~15 merged bar
columns × ≤ 400 price rows ≈ **≤ 6,000 drawn cells mechanically**, measured 1,694–1,809 on live data.
The 30 k shape is a synthetic stress the pipeline cannot produce. §52's "17.5 ms arrival / 11.5–12.4
warm" was that synthetic shape pre-yield on a ~2× larger plot; today it costs 2.2–2.6 ms on a 3.0 Mpx
viewport (~4.8–5.6 scaled to that plot — the P2-2/P2-3 work improved the shape ~1.4×).

**Decision.** Per the plan's own rule ("Do not port WebGL without the trigger conditions being met
and measured") **P3-1 stays deferred** — the heat's share of any frame he can produce is ≤ 1.7 ms
against a 6.94 ms budget (4× headroom), and on real payloads 0.6–0.7 ms (10× headroom). **Re-open
conditions, sharpened:** (1) drawn heat cells > ~8 k at his resolution; (2) the app's target becomes
a true-4K canvas (> 3,000 CSS px wide); or (3) the heat's own share of a warm frame exceeds **3.5 ms**
(half the 144 Hz budget) at his resolution. If he wants the port anyway as a preference, it is an
L-sized change (quad mesh, pan/zoom matrix as uniforms, ghost buffer on the same shader) that starts
FROM this measurement — not instead of it.

**Bench traps (recorded so the next measurement is not wrong twice).**
1. **Price-spanning bars or everything culls.** The heat painter skips cells outside the viewport;
   synthetic bars at price 1.0 culled every ~75 k-price cell and the "pass" measured 0.0 ms. Two runs
   this pass were invalid before that was caught (cells read 0 or the pass read 0.0–0.1 ms).
2. **The P2-2 epoch gate makes a naive loop measure the SKIP path.** A forced pass needs
   `OFX.state.heatEpoch += 1`; `dirty.heat = true` alone skips the heat (counted in `heatSkips`).
3. **Measure in one sync block.** The view's 2.5 s poll reloads its own data between awaited turns and
   the merged cell count changes under the bench.
4. **Terminal vs classic size.** The default terminal layout gave the ofx widget a 354×148 stage;
   realistic full-view numbers need classic mode (`OFAPSHELL.switchTo('classic')`).
5. **`Browser.setWindowBounds` clamps to the screen** (~2556 px on this panel); a true 4K-width
   canvas needs `Emulation.setDeviceMetricsOverride`.

**The options/fundamentals residue — closed with live captures.**
- Fundamentals supply cell: `20.09M BTC` + a real child element (`of 21.00M max`;
  `elementChildren: 1`) — no literal tag in the text.
- Options gamma: selecting the ATM strike live put the ticker strip at
  `BTC-16SEP26-76000-C · mark 0.0015 · IV 29.29% · Δ +0.385 · Γ 8.80e-4 · Θ -83.256 · V 5.685 ·
  ρ 0.112 · OI 82 · vol 103.5 · forward 75871.2 · as of 2:07:54 pm` — the sub-milli gamma renders as
  the exponential exactly as `fmtGreek` pins it. §25's one un-eyeballed item now has a live example,
  not just a test.

**Ops note (cost time this pass): the automation browser is not immortal.** The harness drives a
Chromium-family browser over CDP. A process cleanup that catches the browser leaves the daemon unable
to recover (`DevToolsActivePort not found`), and stacked half-started daemons then block new calls
(the client reads an empty response). Recovery that works: launch **Edge** with
`--remote-debugging-port=9222 --user-data-dir=<throwaway dir>` — the harness probes 9222/9223
directly and attaches. No Chrome is installed on this machine; Edge is the Chromium family here.

**Gates at close.** pytest **585 / 2 skipped**; **AUDIT CLEAN**; nineteen selftests green; the tree is
untouched by this pass (**49 modified + 19 new**, HEAD `fa202d6` — measurement and documentation
only); sandbox deleted, the scratch Edge closed.

## §60 — the ModFlow badge as the app's iconography, and the new desktop shortcut

**The ask.** Adapt `Desktop/modflow.png` to "seamlessly replace the icons in the build", and add a new
desktop shortcut to the program carrying the new iconography.

**The source and the adaptation.** `modflow.png` is 1664×928, RGB, no alpha — the circular ModFlow
badge (navy disc, ring ensemble, honeycomb + circuit texture, teal M monogram, arced
"Modflow"/"OrderFlow Analysis Suite") on a cream banner (~`#F4F1E7`). Pipeline (PIL): a not-cream mask
(far-from-background threshold 25) gave the badge bbox `(438,69,1227,849)`; 144 rays refined the
centre + radius (median 394, spread 391–396 — a clean circle); a 792² crop was scaled to 96.5 % of a
1024 master and cut with a 4×-supersampled circular alpha mask (≈2 source px inside the edge so no
cream fringe survives — the edge audit shows the boundary pixels are the badge's own thin white ring,
plus 158 fractional-alpha boundary samples for a smooth rim).

**What was produced.** `assets/orderflow.ico` (replacing a 16–128 px stock bar-chart placeholder —
sizes 16/24/32/48/64/128/256, 256 PNG-compressed), `assets/modflow-icon-1024.png` (design master),
`orderflow_system/desktop/ui/app.ico` (**the path `build_exe.py` looks for** — the build had NO custom
icon at all until now, so the frozen exe carried PyInstaller's default), and `ui/app-icon.png` (512)
+ 32/64 PNGs for the web. Size falloff judged from a rendered sheet: 48 px reads fully, 32 legible,
24 recognisable, 16 reads as the round teal emblem — the standard falloff for a detailed badge, and
one consistent design was kept (no separate simplified ≤24 variant).

**Where they were wired.**
- **The web UI**: `index.html` gains `<link rel="icon" … app-icon.png>` + `… app.ico`. Live: both
  serve 200 from the desktop mount (the 512² PNG downloads whole), and the served page carries the
  link.
- **The window/taskbar icon (dev + frozen)**: `launcher.py` — and here the smoke test earned its
  keep twice. `webview.create_window(icon=…)` is **not a parameter in this pywebview** (TypeError at
  launch); `webview.start(icon=…)` is. And the WindowsForms backend refuses the PNG
  (`ArgumentException: 'picture' must be a picture that can be used as a Icon`) — it needs a real
  `.ico`. Final shape: `webview.start(icon=str(ui/app.ico) if it exists else None)`; the subsequent
  dev launch runs clean (the UI client connects in the log). The path resolves in the frozen build
  too: `build_exe.py` already `--add-data`s the whole `ui/` dir, so `Path(__file__).parent/ui/app.ico`
  is there through `_MEIPASS`.
- **The frozen exe itself**: its icon resources were replaced **without a rebuild** (nothing else in
  the build changes) via the classic Win32 path — `BeginUpdateResourceW` →
  `UpdateResourceW(RT_ICON × 7 + RT_GROUP_ICON, group id 1)` → `EndUpdateResourceW` (ctypes). Backup
  taken first (`%LOCALAPPDATA%\Temp\p60_exe_backup.exe` — deliberately OUTSIDE `dist/` so the ship
  folder stays clean). Verified by extraction: the exe's icon now reads 506 navy + 180 cyan pixels
  against the old bar-chart's palette, and the exe runs (the patch cannot have corrupted it).
- **The desktop**: a new shortcut **`ModFlow OrderFlow Analysis Suite.lnk`** (target
  `.venv\Scripts\pythonw.exe -m orderflow_system.desktop`, workdir the repo, icon
  `assets\orderflow.ico`, description set). The pre-existing `OrderFlow Analysis Pro.lnk` pointed at
  the same icon file and therefore picked the new artwork up automatically.

**A rebuild note.** The frozen exe's embedded icon is now the badge, but its bundled code predates
P1-7→§60; a future `scripts/build_exe.py` run picks up both the new `ui/app.ico` (via the ICON
constant) and the `start(icon=)` wiring, so the rebuilt app carries the iconography end to end.

**Traps for the record.** (1) pywebview's icon kwarg lives on `start()`, not `create_window()`, and
the WinForms backend takes an `.ico` (a PNG raises from .NET, not from pywebview). (2) A resource
patch needs `LoadLibraryEx(LOAD_LIBRARY_AS_DATAFILE)` + `EnumResourceNames` to find the existing
group id; orphan old RT_ICON entries beyond the new count are harmless. (3) Verify an icon in an exe
by extraction, not by the write return codes — and smoke-run the exe afterwards.

**Gates.** pytest 585/2, AUDIT CLEAN, nineteen selftests green (the UI change is one `<link>` pair;
the launcher change is verified by the two smoke runs). Tree: 50 modified + 24 new, HEAD `fa202d6`,
nothing committed.

## §61 — the two-tier icon: a simplified 16/24 px variant (the §60 offer, accepted)

**The ask.** §60's review noted the detailed badge mushes at 16 px and offered a simplified small-size
variant — the owner said build it.

**The pick.** Four centre crops of the badge (0.50R / 0.58R / 0.66R / 0.74R, each circle-cut and
rendered for review) were compared: 0.66R clips "Modflow" back in at the top, 0.74R shows the full
text, 0.50R sits tight on the M. **0.58R** won — the text is fully excluded and the M is complete with
breathing room. That crop was scaled to the same 96.5 % circular canvas as the badge master (so the
silhouette is identical) and kept as `assets/modflow-icon-small-1024.png` (1024 master for future
edits).

**The two-tier file.** PIL cannot emit different artwork per size in one `.ico`, so the set was
assembled at the byte level: two PIL-written ICOs (16+24 from the variant; 32/48/64/128/256 from the
badge) were merged into one directory with offsets adjusted — `assets/orderflow.ico` and
`orderflow_system/desktop/ui/app.ico` now carry the mixed set (16/24 simplified, 32+ the badge), and
the desktop shortcuts follow the assets file automatically.

**Verified.** PIL reads all seven sizes back; the exe's icon resources were re-patched with the merged
file and a **.NET** extraction (a second, independent icon parser) shows the badge at 32 px — the same
double-parse agreement that validates the hand-rolled ICO layout; the review sheet shows the variant
clearly more legible than the shrunken badge at 16 and 24 px; the exe smoke-runs; the fresh exe
backup was moved out of `dist/` again. The Explorer icon-cache caveat from §60 stands (a stale
thumbnail refreshes on its own).

**Gates.** Nothing in the app code changed this pass (icon assets only): pytest 585/2, AUDIT CLEAN
and the selftests carry over untouched. Tree: 50 modified + 25 new (`assets/modflow-icon-small-1024.png`
added), HEAD `fa202d6`, nothing committed.

## §62 — the rail brand: the text tile becomes the badge, and the wording modernises

**The ask (verbatim).** "replace the icon in the modflow order analysis suite build with the capital MF
in the top left with the new one you built and modernize the wording ModFlow ORDERFLOW ANALYSIS SUITE"

**What was there.** The rail's top-left block was a *painted* tile — a 32 px div, blue→violet gradient,
the literal text `MF` — above `ModFlow` and an all-caps `ORDERFLOW ANALYSIS SUITE` whose casing came
from the stylesheet (`.brand-sub { text-transform: uppercase; letter-spacing: .09em }`).

**The pick, from a rendered sheet.** The badge master and its §61 0.58R small variant were rendered at
24/28/32/36/40 px over the rail's own background (the dark gradient `rgb(13,20,32)` → `rgb(10,14,22)`,
and the light rail) and judged: at the rail's 32 px the **badge** reads best — its white ring gives the
mark an edge the variant lacks on the dark rail (navy-on-navy there; the variant stays the ICO 16/24
tier). Sheet and scratch scripts kept in `%LOCALAPPDATA%\Temp\p62_*`.

**What changed.**
- `ui/brand-icon.png` (new): the badge master at 128 px LANCZOS, alpha kept, 37 290 bytes — DPR-proof
  for a 32 px slot; `build_exe.py` ships the whole `ui/` dir, so a rebuild carries it exactly as
  `app.ico` already is.
- `index.html`: `<div class="brand-mark">MF</div>` → `<img class="brand-mark"
  src="/desktop/brand-icon.png" alt="ModFlow" width="32" height="32">`; the sub now reads
  **Orderflow Analysis Suite** — sentence case, the badge's own lettering.
- `ui.css`: `.brand-mark` is an image slot now (fixed 32 px, `flex: 0 0 auto`; no tile, no radius —
  the artwork is the disc); `.brand-name` 13.5 → 14 px; `.brand-sub` 10.5 → 11 px with the caps
  transform and the wide tracking removed.
- `test_wiring.py`: a P62 guard — the mark is the icon asset, `>MF<` is gone, the sub is sentence
  case, the caps transform is out of the rule, and the asset is served (`GET /desktop/brand-icon.png`
  → 200 `image/png`). The guard exposed a real trap: **`build_app()` may run once per process** (the
  FastAPI app it decorates is a module-level singleton; a second `add_middleware` raises "Cannot add
  middleware after an application has started" once any client has exercised it) — the file's two
  served-page tests now share one `_desktop_app()` build, green in any order.

**Verified live.** Headless on 8099: the served page carries the new markup; `GET /desktop/brand-icon.png`
→ 200 `image/png` and the downloaded bytes hash-match the file on disk (sha256 `a9d8789b…`; a first
`curl -w %{size_download}` read 0 bytes — a curl artefact: the saved download is the full 37 290).
Browser render: the badge crisp at 32 px in dark AND light themes, the sub aligned and quiet;
**0 `client error:` lines** in the app log; `config.json` byte-identical to a pre-smoke backup. The
frozen exe still carries the pre-§61 `ui/`, so the rail there changes with the pending `dist/` rebuild,
not before.

**Gates.** pytest **586 passed / 2 skipped** (585 + the P62 guard), `audit_ui_refs.py` **AUDIT CLEAN**,
nineteen selftests green (ofx 178). Tree: 50 modified + 26 new (`ui/brand-icon.png` added), HEAD
`fa202d6`, nothing committed.

---

## §63 — The package diet: stage 0 (dead build products) + stage 2 (numpy out, stdlib in)

Trigger: "maximizing pure efficiency of code and file ultimate file size? NOT BREAKING ANYTHING is paramount."
Two stages ran; a third (UPX) stays a separate owner decision.

**Stage 0 — build scratch, nothing referenced it.** `build/` (48.8 MB, 17 files: PyInstaller work dir,
which `build_exe.py --clean` deletes on every build anyway) and `dist/OrderFlowAnalysisPro/` (80.7 MB,
1690 files: the pre-rename Sep 15 onedir build) were removed. Evidence trail:
`%LOCALAPPDATA%\Temp\ofap_stage0_manifest_20260916.txt` (HEAD, file counts/bytes, sha256 of both exes
and the spec) + the spec kept at `%LOCALAPPDATA%\Temp\ofap_stage0_kept\`. No shortcut or launch path
references either folder — the desktop shortcut runs `.venv\Scripts\pythonw.exe`, and a scan of all 106
Desktop/Start-Menu shortcuts found none pointing into `dist/`. Repo: 487 MB → 360 MB. The kept build's
exe hash (`f0884c19…`) was identical before and after.

**Stage 2 — the analytics engines no longer need numpy (27 MB + hook collateral).** numpy was imported
by exactly two runtime files, for four sums, an `argmax`, a `std()` and a five-term line fit:
`analytics/delta.py` (polyfit slope ×2) and `analytics/volume_profile.py` (argmax/mean/std ×5). Both are
stdlib-only now (`_slope`, `_argmax`, `_mean`, `_pstd` — numpy's tie and ddof semantics preserved).
Safe-by-proof, not by promise: `scripts/regen_analytics_golden.py` captured 38 cases / 2138 numeric
leaves from the numpy implementations *before* the edit (fixtures sha256 `88cc0f8e…`), and the rewrite
reproduces them with a worst-case difference of **2.27e-13** (LAPACK vs plain summation; every POC/VAH/VAL,
LVN list, shape, peak index and cumulative delta identical). The pin is permanent:
`test_analytics_golden.py` (drift → the exact case and delta) and `test_no_numpy.py` (source scan of the
runtime tree + a subprocess that blocks numpy via `sys.modules` and then imports *and computes* the whole
pipeline chain, `main.OrderflowSystem` included). `build_exe.py` now excludes numpy/pandas/scipy/plotly/
kaleido/matplotlib/pytz/tzdata/watchfiles. The frozen package: **68 MB → 51 MB**, numpy/pytz/tzdata/
watchfiles all confirmed absent from `_internal` (the exe itself grew 0.5 → 12.7 MB because the CLI build
embeds the Python archive in the exe while the old hand-tuned spec used `exclude_binaries=True` — the
package total is the metric that moved, −17 MB / −25%).

**Verified live (frozen exe).** `dist/…/ModFlowOrderFlowAnalysisSuite.exe --headless --port 8095` with
`APPDATA` sandboxed (`%LOCALAPPDATA%\Temp\ofap_frozen_sandbox` — the live config/DB/log were never
touched): `/healthz`, `/desktop`, `/api/atlas/status`, `/api/atlas/capabilities`, `/api/control/config`
all **200**; the served `/desktop` and `/desktop/ofx.js` **hash-match the files on disk**
(`a238f36c…`, `791f538d…`); `api/atlas/status` returns a real payload; **0 `client error:` lines, 0
tracebacks, 0 ImportErrors** in the sandbox log. Process stopped afterwards (port closed, verified).

**Gates.** pytest **591 passed / 2 skipped** (586 + the five new pins), `audit_ui_refs.py` **AUDIT
CLEAN**, nineteen UI selftests green (ofx 178). Nothing committed; HEAD `fa202d6`.

**Still open.** Stage 1 rode along inside stage 2 (same exclude list, same rebuild). **UPX: NOT pursued —
measured 2026-09-16.** The earlier "~10-14 MB" was an unverified estimate; the measurement says the lever is
mostly imaginary: a plain zip of the shipped folder is **25.8 MB from 49.2 MB raw (−23.5 MB)** with zero
risk, and UPX-packed DLLs barely compress further inside that zip — so the artifact a user actually
downloads gains ~2 MB for Windows Defender/SmartScreen heuristics on packed binaries and a slower cold
start. Ship the zip if the app is ever published; the folder stays as built.

---

## §64 — Release-readiness pass (0.1.0 beta): leaks, lint, packaging — and one live bug the smoke found

Scope asked for: "final debug and file integrity scan … first release 0.1 beta … nothing must be broken",
with a reviewer LLM auditing the code and the build. Everything below is on disk; nothing committed.

**Integrity scan — clean.** No credentials in source (only README's `your_password` / `your_bot_token`
placeholders); no `sk-` / `ghp_` / `xox` / `AKIA` shapes; no `C:\Users\Moddy` in source **and no "Moddy"
string in the shipped payload** (0 hits across the 494 files of the built package); the root
`orderflow_data.db*` / `*.log` are gitignored and untracked; `.gitignore` gained `.pytest_cache/`,
`.ruff_cache/`, `.mypy_cache/`. One cosmetic residue, for the record: 29 packaged files carry the *build
machine's Python path* (`C:\Users\Moddy\AppData\Roaming\uv\python\…`) inside CPython's own binaries —
`python312.dll`, the `.pyd` files, `base_library.zip` — which is how a locally-built CPython stamps itself,
not project data; a Python installed at a neutral path would remove it if that ever matters.

**Release blockers fixed** (a reviewer's tooling would have hit each one):
1. **3.12-only syntax.** `desktop/api.py:399` used a nested same-quote f-string (PEP 701). The tree did not
   parse on 3.11 while pyproject claimed `>=3.10` and CI pinned 3.11 — first push would have been red.
   Hoisted into a local; an AST sweep with the 3.11 interpreter now reports **0 parse failures**.
2. **The dependency set was wrong in both directions.** pyproject declared pandas/numpy/scipy/plotly/
   kaleido/pytz/pyyaml (none imported anywhere) and declared none of fastapi/starlette/uvicorn/pywebview/
   pythonnet (all imported). `pip install -e .[dev]` on a clean machine could not run the app. Rewritten:
   only what the tree imports; `mt5` extra for the Windows-only MetaTrader5 feed; `dev` gained pyinstaller;
   `requires-python = ">=3.11"`; MIT license + classifiers; backend `setuptools.build_meta` (was the
   private `setuptools.backends._legacy:_Backend`); package-data for `desktop/ui`, `testdata`,
   `data/bookmap_addon`; `[tool.ruff]` block. Verified by building a wheel (220 files, UI + testdata inside).
3. **A real user-facing bug, found by exercising the endpoint.** `POST /api/control/source` called
   `engine.state()` while `EngineController.state` is a **property** → `TypeError: 'str' object is not
   callable`, swallowed by the endpoint's `except`. Picking a data source in the menu saved the config,
   never restarted the engine, and showed "the restart failed (…)". Fixed (one line) and pinned by the new
   `orderflow_system/test_source_switch.py` — 3 tests, **proven to bite**: with the bug reintroduced
   2 failed / 1 passed, with the fix 3 passed (`%LOCALAPPDATA%\Temp\ofap_pin_check.py`).

**Lint baseline (new).** `ruff check orderflow_system scripts` → **All checks passed** (was 143 findings).
70 auto-fixed (unused imports, f-strings without placeholders); hand-fixed via fail-loud scripts
(`%LOCALAPPDATA%\Temp\ofap_lint_fixes{,2,3,4}.py`): 12 unused locals — the *call* kept wherever it has an
effect (`hub.ensure()`, `orderbook_tracker.update()`, `webview.create_window()`) — 8 unused loop control
variables, 2 undefined annotation names in `atlas/cvd.py` (`Iterable`/`Sequence` were never imported), and
1 loop variable shadowing the stdlib `signal` import in `main.py`. `B008` (FastAPI's `Depends()`/`Query()`
in argument defaults) and `B905` (`zip(strict=)` is a behaviour change, not a style one) are documented
ignores. CONTRIBUTING now carries the lint baseline, the no-numpy rule and the node requirement.

**Public-face corrections.** README: badges + body corrected against measurements (3.11+, 49 instruments,
~60k lines, 131 operations / 119 paths as actually served per `/openapi.json`, 594 tests); the tree now
shows `atlas/` and `desktop/`; File Inventory is a measured table (163 files / 60,636 lines excl. tests;
the suite is 51 files / 10,477 lines); Installation rewritten around the real dependency set and the
desktop app (`python -m orderflow_system.desktop`, `--headless --port 8099`), with the MT5 extra, demo
mode and `scripts/build_exe.py`; License section states the fork relationship. LICENSE keeps the upstream
MIT notice **and** adds Moddy's copyright line. Test output de-emoji'd (12 sites in `test_integration.py`);
`test_no_numpy.py` no longer names a person in its docstring.

**Gates at close (3.12 venv).** pytest **594 passed / 2 skipped** · `audit_ui_refs.py` **AUDIT CLEAN** ·
ruff clean · analytics golden OK (2.27e-13) · config golden OK (31/18/49) · 19 UI selftests green (ofx 178).

**IMMEDIATE NEXT ACTIONS**
1. ~~Rebuild the frozen dist~~ — **DONE 16:28**, exe now newer than the `api.py` fix, and smoked on the
   shipped artifact (sandboxed `APPDATA`, port 8095): `/healthz`, `/desktop`, `/api/atlas/status`,
   `/api/control/config` all **200**; `POST /api/control/source` answers
   `{"ok":true,…,"engine":{"restarted":false,"reason":"engine was not running"},"note":"source saved;
   press Start engine to stream it"}` — the old `'str' object is not callable` note is gone; the served
   `/desktop` hash-matches disk (`a238f36c…`); **0** error lines in the sandbox log; numpy and the hook
   collateral still absent; package **49.2 MB raw / 25.8 MB zipped** (re-measured on this artifact).
   Process stopped, port closed.
2. **Settle the Python 3.11 question before the first push.** `test_websocket_backpressure.py::
   test_a_broadcast_never_waits_on_a_slow_client` never returns on 3.11 (3.12 completes in <1 s and cancels
   both writer tasks cleanly; the 3.11 venv stalls inside the scenario and, in another run, inside
   `asyncio.run`'s `_cancel_all_tasks` — a faulthandler dump is in `%LOCALAPPDATA%\Temp\ofap_stack.txt`).
   Either root-cause it (real 3.11-vs-manager behaviour) or set `.github/workflows/ci.yml` to 3.12 only and
   `requires-python = ">=3.12"` — the current matrix is `[3.11, 3.12]`, so an unresolved hang burns a job.
3. Then the release proper (owner's call; nothing committed, HEAD `fa202d6`): commit → create the GitHub
   repo → push → tag `v0.1.0-beta` → attach a **zip** of `dist/ModFlowOrderFlowAnalysisSuite/` (measured
   25.8 MB from 49.2 MB raw; UPX closed, not pursued — §63). InstallShield follows, and needs: WebView2
   runtime prerequisite, per-user `%APPDATA%\OrderFlowAnalysisPro` config (leave it on uninstall),
   `ui/app.ico`, version 0.1.0, publisher string.

**Housekeeping left open.** `AUDIT_REPORT_2026-09-15.md` at the repo root carries a `C:\Users\Moddy\…`
path and a few "Moddy" references — move into `docs/` or leave (decision); the docs/ trail keeps its
"Moddy"-flavoured narration by design; the README's ASCII box says "132 REST/WS routes" while the badge and
the served schema say 131 (make exact if it matters).

**Evidence in `%LOCALAPPDATA%\Temp\`**: `ofap_py311.log` (3.11 venv, pytest stalls at 96%),
`ofap_stack.txt` (faulthandler dump), `ofap_taskprobe.py` (3.12 control vs 3.11 blank),
`ofap_lint_fixes*.py`, `ofap_emoji_clean.py`, `ofap_pin_check.py`, `ofap_engine_repro{,2}.py`,
`ofap_release_sandbox/` (first-run sandbox), `ofap_wheel_test/`, `ofap_stage0_manifest_20260916.txt`,
`ofap_stage0_kept/`, `ofap311/` (the 3.11 venv itself).

---

## §65 — The Python 3.11 hang: root cause (a stdlib cancellation swallow), the fix, and the release-face exactness pass

Scope asked for: settle the §64 open item 2 — `test_websocket_backpressure.py::test_a_broadcast_never_waits_on_a_slow_client`
never returns on 3.11 — then the release-face housekeeping. Everything below is on disk; nothing committed.

**The hang, located.** On 3.11 the scenario body completes; the stall is in `asyncio.run`'s shutdown
(`runners._cancel_all_tasks`: cancel the survivors with the loop stopped, then gather them — faulthandler
shows the loop idle in `windows_events._poll`). The two writer tasks are the survivors: one parked in
`asyncio.wait_for(send_text, 5.0)`, one in `queue.get()`. Cancel-while-running always worked; the hang
needs cancel-while-stopped plus one specific state: the write-timeout's `waiter` future already FINISHED
with the writer's wake-up still queued (`ofap_probe65d.py` ticker: `fut_waiter=[Future done=True
state=FINISHED]`, writer alive forever, parked back in `queue.get()`).

**Why.** 3.11's `asyncio.wait_for` (`Lib/asyncio/tasks.py:477`): `except CancelledError: if fut.done():
return fut.result()` — when the awaited write already finished, the caller task's cancellation is
*answered with the write's result*. `Task.cancel()` had already consumed its one shot (`_must_cancel`
can't cancel an already-done `_fut_waiter`), so the writer looped back to `queue.get()` and never died;
`_cancel_all_tasks`'s gather waited forever. 3.12 rewrote `wait_for` as `async with
timeouts.timeout(timeout): return await fut` (same file, line 519) — no swallow clause — which is why
3.12 completed in <1 s. The manager's own contract (producer never waits on a slow socket, bounded
queues, oldest-first trim) was never at fault.

**The fix.** `websocket_manager._writer` and `_offer` no longer use `wait_for`: a plain deadline,
`async with asyncio.timeout(WRITE_TIMEOUT_S)` (3.11+, the same primitive 3.12's `wait_for` is built on).
Semantics unchanged: write deadline → drop the client; offer deadline → `dropped += 1`. Cancellation now
propagates like any other exception, on both interpreters.

**The pin.** `test_a_cancelled_writer_dies_even_when_its_write_just_finished` builds the exact state
deterministically (a gated write completes while the loop is stopped; one settle cycle; cancel; a
bounded gather) so a regression **fails in ~2 s instead of hanging the suite**. Proven to bite: with the
original `wait_for` code it fails (1 failed in 2.29 s, AssertionError at the bounded shutdown, writer
parked in `queue.get()`); with the fix: 6/6 in the file, the formerly-hanging test 10 consecutive runs
at ~0.61 s. The full suite on 3.11 — the thing §64 could not get — now runs: **595 passed / 2 skipped in
26.5 s** (3.12: 595 / 2 in 26.4 s). **CI's `[3.11, 3.12]` matrix and `requires-python = ">=3.11"` stay;
no pin to 3.12 was needed.**

**The one 3.11-only failure found, and why it was not the code.** `test_wiring.py`'s rail-brand test
asserted the served `content-type` of `brand-icon.png`; on this host `HKCR\.png\Content Type` is *empty*
(Media Center residue — the real value sits in `MediaCenter.36.ContentType.BAK`), and 3.11's `mimetypes`
honours the empty registry value while 3.12 falls back — so 3.11 served `application/octet-stream` where
3.12 served `image/png`. The assertion was a statement about the host, not the app; replaced with byte
identity (`res.content == file.read_bytes()`) — strictly stronger and host-independent. The frozen build
is 3.12, so the shipped app never sees it.

**Release-face exactness (all measured this session).**
- README tests badge 591 → 595; CONTRIBUTING baseline 591 → 595 (both interpreters measure 595 / 2).
- "Supported Instruments (29)" → (49) (ToC + heading) plus one clarifying line: 49 = the 31 base specs
  tabled below + 18 crypto majors (config golden 31/18/49); "…for all 29 instruments" → "…for all 49
  configured instruments"; the demo-generator line → 45 (`demo_data.demo_instruments()` measures 45).
- `config/settings.py` tree notes: 29 → 31 instrument configs, 10 → 14 dataclasses, 946L → 777L
  (the File Inventory's Config row — 2 files / 777 — corroborates).
- The §64 route-count question resolved as **no change needed**: measured 119 paths / 131 operations /
  1 WebSocketRoute (`/ws`) → 132 REST/WS routes, exactly what the badge and the box say; `/api/atlas/*`
  = 45 and `/api/control/*` = 70 confirmed exact.
- **Found and recorded, not edited**: the README's tree/diagram `(NNNL)` annotations are broadly stale —
  a read-only audit of the 43 claims found **26 wrong** (main.py 666→815, app.py 1015→1235,
  websocket_manager.py 186→293, …); the File Inventory table (§64) is the accurate set. A dedicated
  docs pass should re-derive them (script: `%LOCALAPPDATA%\Temp\ofap_readme_count_audit65.py`).
- `AUDIT_REPORT_2026-09-15.md` moved from the repo root to `docs/` (its v1 already lives in
  `docs/archive/`); the live pointer in `docs/ALPACA_UPGRADE_EXECUTION_PLAN.md` (source table S3)
  updated. The docs/ trail keeps its "Moddy"-flavoured narration by design.

**The frozen dist is current again.** Rebuilt 16:54:45 (exe newer than the fix) and smoked on the
artifact (sandboxed `APPDATA`, port 8095): `/healthz`, `/desktop`, `/api/atlas/status`,
`/api/control/config` all **200**; `POST /api/control/source` answers `{"ok":true,…,"engine":
{"restarted":false,"reason":"engine was not running"},"note":"source saved; press Start engine to
stream it"}` — the §64 bug stays fixed; the served `/desktop` and `/desktop/ofx.js` **hash-match disk**
(`a238f36c…`, `791f538d…`, unchanged); **0** `client error:` lines, 0 tracebacks; numpy still absent
(0 of 55 `_internal` entries); **49.2 MB raw (51 MB on disk) / 25.8 MB zipped** (494 entries, re-measured on this
artifact). Process stopped, port closed. (Note for the shell: `taskkill //F` is not a valid form here —
it errors and a redirected stderr hides it; `powershell -NoProfile -Command "Stop-Process -Id <pid>
-Force"` is the reliable stop, and PyInstaller's onedir build runs a parent+child pair — the PID
holding the port is the one that must die.)

**Gates at close.** pytest **595 passed / 2 skipped** on both 3.11 and 3.12 · `audit_ui_refs.py`
**AUDIT CLEAN** · ruff clean · analytics golden OK (2.274e-13) · config golden OK (31/18/49) · 19 UI
selftests green (ofx 178).

**Tree.** Nothing committed; HEAD `fa202d6`; `git status --porcelain` = 129 entries. §65 touched:
`orderflow_system/dashboard/websocket_manager.py` (the fix), `orderflow_system/test_websocket_backpressure.py`
(the pin), `orderflow_system/test_wiring.py` (host-independent assertion), `README.md`, `CONTRIBUTING.md`,
`docs/ALPACA_UPGRADE_EXECUTION_PLAN.md`, plus the `AUDIT_REPORT_2026-09-15.md` move (root → `docs/`) and
this section + `docs/RESUME.md`. `dist/` rebuilt (gitignored).

**IMMEDIATE NEXT ACTIONS**
1. Owner's call (unchanged): commit → create the GitHub repo → push → tag `v0.1.0-beta` → attach a zip
   of `dist/ModFlowOrderFlowAnalysisSuite/` (25.8 MB; UPX closed, not pursued — §63). Nothing committed.
2. Optional docs pass: re-derive the README's tree/diagram `(NNNL)` counts (26 of 43 stale as of §65).
3. InstallShield after that (WebView2 prerequisite, per-user `%APPDATA%\OrderFlowAnalysisPro` config,
   `ui/app.ico`, version 0.1.0, publisher string).

**Evidence in `%LOCALAPPDATA%\Temp\`**: `ofap_probe65.py`, `ofap_probe65b.py`, `ofap_probe65c.py`,
`ofap_probe65d.py` (the decisive ticker), `ofap_py311_hang65.log` (the fresh pytest hang + faulthandler),
`ofap_wm_orig.py` / `ofap_wm_fixed.py` (red/green copies), `ofap_taskprobe.py`, `ofap_stack.txt`,
`ofap_doc_edits65.py`, `ofap_readme_count_audit65.py`, `ofap_stage65_build.log`, `ofap_stage65_sandbox/`,
`ofap_stage65_dist.zip`, `ofap_routecount_sandbox/`, `ofap311/` (the 3.11 venv).


## §66 — v0.1b audit return: ingest.txt verified item-by-item, 7 fixes pinned, 3 rejected with evidence

**Context.** `Desktop/ai prompt.txt` (the footprint/heatmap spec + "scrutinise, stepped report, don't
break anything") applied to `Desktop/ingest.txt` — a fresh 799-line "RELEASE AUDIT REPORT v0.1b"
(Tiers 0–8). The full return document is `docs/AUDIT_RETURN_v0.1b.md`; this entry is the worklog.

**Fixed, each with its own pin (8 new test files + 1 case in test_wiring.py; suite 595 → 621 / 2).**
- **1.5 DB footprint round trip** — `get_candles` never read `footprint_json`, so the hourly VP
  rebuild ran the even-distribution fallback on real data. Now read+decoded (`_decode_footprint`;
  `{}`/NULL → empty, malformed cells skipped). Pin: `test_candle_roundtrip.py`.
- **1.4 absorption keying** — `round(price, 4)` merged adjacent levels on the 9 fine-tick
  instruments (forex 1e-5, DOGE, TRX); a probe showed a single candle firing `min_attempts=2` from
  two distinct prices. Keyed by tick-rounded price now. Pin: `test_absorption_keying.py`.
- **Tier 8 #2 unknown-symbol leak** — the `models_symbol` guard sat only on the warming branches of
  `/api/footprint` and `/api/tape`; the no-engine branches served the invented $1,000 chart. Both
  guarded; live-verified (source 8091 + frozen exe 8099): `UNKNOWNXYZ` → `[]`. Pin: `test_wiring.py`.
- **2.1 candle-wiring assertion** — now checks identity (analytics callback on the pipeline's own
  builder; persistence wire == `system._on_candle_closed`), catching the one-letter mis-wire class;
  the audit's rename pass was not taken (churn; the assertion now guards the failure mode). Pin:
  `test_candle_wiring.py`.
- **2.5 Bybit `T` fallback** — one latched warning per connection, re-armed on reconnect. Pin:
  `test_feed_timestamps.py`.
- **2.2 bank-key rename** — `_CONFIG_BANKS`/`_bank` read as destination field names; Spec→bank map
  in `get_config_for`; config golden proves equivalence (31/18/49).
- **demo coverage** — added NIKKEI225/CAC40/ASX200/HK50/USOIL/UKOIL base prices (demo-only content;
  ticks deliberately coarser than live banks, documented). Pin: `test_demo_coverage.py`.
- **README counts pass** — all 43 `(NNNL)` claims re-derived (18 stale); File Inventory re-measured
  (172 files / 26,131 py / 35,813 UI / 61,944 total; suite 60 / 11,138); badge ~62k; "45 demo
  instruments" → every shipped instrument; 9→10 channels ×2; 7→9 dataclasses; provenance now names
  the upstream fork commit `b2ff4ee` (author verified: Mahmoud Chen).
- **Analytics golden** — +2 edge cases (`poc_top_cluster` keeps VAL<POC; `poc_at_low` pins `val==poc`
  at the extreme as correct); 40 cases, regen check max diff 0.000e+00, no existing number moved.

**Rejected, with probe evidence (no change made).**
- **1.1 value-area "inversion"** — the invariant `val <= poc <= vah` holds by construction; the
  audit's own proposed test already passes on the live algorithm; its "fix" would widen the band
  past the 68% containment. Pinned by `test_value_area_edges.py` + the golden cases instead.
- **1.3 exhaustion "inverted gate"** — the proposed gate demands `delta_roc < 0` (delta falling =
  selling STRENGTHENING for bearish exhaustion) and silences the textbook dry-up bin; a 5-bin probe
  shows the live gates correct. Pinned by `test_exhaustion_gates.py`; the sign-flip is documented.
- **1.2 "dead cooldown knob"** — it is wired for the app (`desktop/engine.py:591–594` overrides both
  aggregator values from the user's `risk` config); what was missing was a pin →
  `test_engine_wiring.py` + a provenance comment in `main.py`.

**Verified-already-done (no action):** Tier 0 (dual LICENSE present; provenance line added),
2.3 (selftests ARE in CI — `.github/workflows/ci.yml` runs pytest + audit + all 19), 4.2 (log/db
untracked + ignored), Tier 3 (stacked-SR zones, cbrt sweep circles, snap-to-live float, font ramp,
45 px LOD, CVD readout all present in `ofx.js`/`ofx-view.js` — that section of the audit is stale),
7.10 (the `data` block is deliberately phase-3; backend + /storage + Logs chip exist).

**Open (owner decisions; Part 4 of the return doc).** The `max(tick_size, 0.01)` displacement clamp
in absorption/initiative (25 fine-tick instruments; fixing it narrows when absorption fires — needs
a decision + bank retune), and extending the unknown-symbol guard to the other demo-fill endpoints.

**Gates.** pytest **621 passed / 2 skipped** · AUDIT CLEAN · ruff clean · analytics golden OK
(40 cases, max diff 0.0) · config golden OK (31/18/49) · 19 UI selftests green · source smoke on a
sandbox (8091) and frozen-exe smoke (8099) as recorded in the return doc.

**Frozen dist.** Rebuilt 18:00 (after the last source edit) and smoked sandboxed on 8099: all
endpoints 200; `/api/footprint/UNKNOWNXYZ` → `[]`; served `/desktop/ofx.js` hash-matches disk
(`791f538d…`); log 16 lines, 0 client errors; numpy absent (0 of 494 `_internal` entries);
**49.3 MB raw / 25.9 MB zipped**; `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` written. Port
closed (PowerShell `Stop-Process` — `taskkill //F` remains unreliable here).

**Tree.** Nothing committed; HEAD `fa202d6`; `git status --porcelain` = 139 entries. §66 touched:
`data/database.py`, `patterns/absorption.py`, `patterns/exhaustion.py` (comments), `data/bybit_feed.py`,
`desktop/engine.py`, `main.py` (comment), `config/settings.py`, `dashboard/demo_data.py`,
`dashboard/app.py`, `README.md`, `scripts/regen_analytics_golden.py`,
`orderflow_system/testdata/analytics_golden.json`, `orderflow_system/test_wiring.py`,
plus eight new test files (`test_candle_roundtrip`, `test_absorption_keying`, `test_feed_timestamps`,
`test_exhaustion_gates`, `test_value_area_edges`, `test_demo_coverage`, `test_candle_wiring`,
`test_engine_wiring`), this section, `docs/AUDIT_RETURN_v0.1b.md` and `docs/RESUME.md`. `dist/`
rebuilt + zipped (gitignored).

**IMMEDIATE NEXT ACTIONS**
1. Owner's decision on the displacement clamp (evidence: `docs/AUDIT_RETURN_v0.1b.md`, Part 4).
2. Release sequence (unchanged): commit → create the GitHub repo → push → tag `v0.1.0-beta` →
   attach `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` (25.9 MB).
3. Optional: extend the unknown-symbol guard to the remaining demo-fill endpoints; InstallShield.

## §67 — the displacement unit restored in absorption/initiative (true tick steps), 6 pins, dist rebuilt again

**Ask.** Owner approved attending to the §66/Part-4 finding: displacement in absorption's
"price displaced little" gate and initiative's body gate was divided by `max(tick_size, 0.01)`,
silently redefining "ticks" on the 25 instruments with tick < 0.01 (on EURUSD "2 ticks" meant
0.02 = 2,000 real ticks; absorption's gate was vacuous at candle scale and initiative could
not fire).

**Decision (with its argument).** Restore TRUE tick steps, because that is the unit every
instrument with tick >= 0.01 has always run in (the old floor was inert there): a level N
ticks from the current price is N footprint levels away; a body of N ticks spans N price
levels. The unit is scale-free, so NO bank retune was needed — 2 and 3 mean the same thing on
EURUSD as on NAS100. The alternative (keep the floor, inflate thresholds per class) hides the
unit and re-breaks on the next odd tick; rejected.

**Proven to bite.** `test_displacement_ticks.py` (6 cases) was written FIRST and run against
the untouched code: the three fine-tick cases failed exactly as predicted (EURUSD absorption
admitted a level 5 ticks away; initiative could not fire), while the coarse-tick cases passed
on both sides (they pin what must NOT move). The zero-tick guard case also exposed a latent
ZeroDivisionError in the §66 event-keying line — closed by the same guarded local
(`tick_size if tick_size and tick_size > 0 else 0.01`).

**Change.** `patterns/absorption.py` (guarded local + `/ tick_size`) and `patterns/initiative.py`
(same). For tick >= 0.01 the divisor is mathematically identical — coarse behaviour
bit-unchanged. Live-path proof: an EURUSD InstrumentPipeline (real config) closed 4 candles
end-to-end through all detectors without an exception.

**Gates.** pytest **627 passed / 2 skipped** (621 + 6) · AUDIT CLEAN · ruff clean · analytics
golden OK (40 cases, 0.0e0) · config golden OK (31/18/49) · 19 UI selftests. `docs/AUDIT_RETURN_v0.1b.md`
gained Part 7 (execution record); its Part 4 marker now reads [RESOLVED]. Nothing committed;
HEAD `fa202d6`.

**Frozen dist.** Rebuilt 18:16 after this change; sandboxed 8099 smoke: endpoints 200 (incl. a
EURUSD fine-tick demo footprint), `/api/footprint/UNKNOWNXYZ` → `[]`, served `/desktop/ofx.js`
hash-matches disk (`791f538d…`), log 11 lines, 0 client errors, numpy absent; **49.3 MB raw /
25.9 MB zipped** (494 entries); `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` refreshed. Port
closed (`Stop-Process`).

**Tree.** Nothing committed; `git status --porcelain` = 140 entries. §67 touched:
`patterns/absorption.py`, `patterns/initiative.py`, `test_displacement_ticks.py` (new),
`docs/AUDIT_RETURN_v0.1b.md`, `docs/SESSION_HANDOFF.md`, `docs/RESUME.md`; `dist/` rebuilt +
re-zipped (gitignored).

**IMMEDIATE NEXT ACTIONS** — now ONLY the release sequence (owner): commit → create the GitHub
repo → push → tag `v0.1.0-beta` → attach `dist/ModFlowOrderFlowAnalysisSuite-win64.zip`.
Optional follow-ups unchanged: unknown-symbol guard on the remaining demo-fill endpoints;
InstallShield.

## §68 — the demo-fill guard generalised to all eight remaining symbol endpoints

**Why.** §66 fixed footprint/tape: an UNKNOWN symbol gets NOTHING with no engine running, not
the old invented $1,000 fiction. The same Tier 8 #2 rule belonged to every other demo filler the
desktop shell polls, because the shell clones the active symbol across every panel.

**Prove-it-bites.** `test_demo_symbol_guards.py` (2 tests) written first, run against the
untouched code: the unknown-symbol test FAILED exactly as expected (first: /api/markers returned
8 invented markers), while the modeled-symbol test PASSED — pinning both halves ("nothing
invented" and "nothing moved").

**The change.** `dashboard/app.py`, nine edits, all confined to `if not system:` (and
microstructure's two fill branches): markers / candles / volume-profile / delta → `[]`;
bias → the engine's neutral no-bias shape tagged demo; strategy-status → the existing
OFFLINE checklist tagged demo; orderbook → the engine's empty-book shape; microstructure →
a new `_empty_microstructure()` (the live payload's shape, zeroed) — with the engine-mode
branches tagged "engine" and demo-mode branches tagged "demo", mirroring each mode's own
empty-state convention. For every modeled symbol (all 49 shipped) the fills are byte-identical.

**Gates.** pytest **629 passed / 2 skipped** (627 + 2) · AUDIT CLEAN · ruff clean · analytics
golden OK (40, 0.0e0) · config golden OK (31/18/49). Live sandbox smoke (source on 8092, then
the frozen exe on 8099): all ten endpoints — including footprint/tape — answer UNKNOWNXYZ with
empty-of-shape; BTCUSDT and EURUSD (fine-tick) fully populated; served UI hash-matches disk.

**Dist.** Rebuilt 18:45 after the change; exe smoked on 8099 (0 error lines, port closed);
`dist/ModFlowOrderFlowAnalysisSuite-win64.zip` refreshed — 494 entries, 25.8 MB zipped /
49.3 MB raw. Nothing committed; HEAD `fa202d6`; tree dirty (141 entries).

**IMMEDIATE NEXT ACTIONS.** InstallShield installer (§69, in progress): generated .ism +
IsCmdBld pipeline; then the release sequence (commit → repo → push → tag `v0.1.0-beta` →
attach zip + setup.exe) on the owner's word.

## §69 — the Windows installer: built, verified, and documented

**What.** `installer/` now carries the whole InstallShield pipeline: `make_installer.ps1`
(regenerates the .ism from the blank Basic MSI template, sets identity + per-user context,
adds the payload via one dynamic folder link + a static exe entry, creates the desktop
shortcut, builds with IsCmdBld, copies the artifact to `dist`, prints the hash),
`SetupPrerequisites\WebView2.prq` (ready-to-enable prerequisite), and `README.md` documenting
the design, the eight measured automation traps, and how to rebuild.

**Artifact.** `dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` — 28,094,985 bytes
(26.79 MB), sha256 `0153B20DBB3048937547DFBBD9D7248F910C4786CAE68CB49DE662FDA2D11599`,
built from the current frozen dist (494 files / 49.28 MB), 0 build errors.

**Verified journey (every step receipts-on-disk).** Silent install (`/s /v"/qn"`) → 494 files
under `%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`, exe under its own name, desktop
shortcut `ModFlow OrderFlow Analysis Suite.lnk` with target = installed exe and the right
description → installed app launched headless on 8098 (healthz 200, BTCUSDT candles 200,
UNKNOWNXYZ `[]` — §68 guard holds in the frozen build) → silent uninstall → install dir,
shortcut and ARP entry all gone. The machine's pre-existing development shortcut was backed up
and restored around the tests.

**Traps found and encoded (the hard-won list, full details in installer/README.md).** Automation
is 32-bit only; CreateProject's binder is broken (copy the blank template instead);
AttachComponent needs the object; AddFile must be called natively; a file's DisplayName IS its
destination filename (setting it to the product name installs the exe extension-less — and
orphans the shortcut); AddShortcut's Target defaults to the FEATURE (an advertised shortcut a
silent install drops) and must be `[#<FileKey>]`; the Shortcut.Name cell needs an 8.3 short
name (`MODFLO~1|ModFlow OrderFlow Analysis Suite`); IsCmdBld wants backslash paths; and
InstallShield runs in **evaluation mode** on this machine (compressed setup.exe only — which is
exactly the artifact wanted).

**Deliberately not taken (documented, not silently skipped).** Start Menu shortcut: the
automation cannot create shortcut-folder roots (probed exhaustively — folder set fixed to
TaskBar/SendTo/Desktop); one-click IDE step documented in installer/README.md. WebView2: chain
package cannot source its bootstrapper payload via automation; the .prq ships ready to enable.
Both noted in the report and README.

**Gates.** No app source changed in this pass — pytest remains **629 passed / 2 skipped**,
AUDIT CLEAN, ruff clean, goldens unchanged. Tree dirty (142 entries) with the new `installer/`
files; nothing committed; HEAD `fa202d6`.

**IMMEDIATE NEXT ACTIONS.** The release sequence itself (owner's word): commit → repo → push →
tag `v0.1.0-beta` → attach `ModFlowOrderFlowAnalysisSuite-win64.zip` + the Setup exe. Optional
polish thereafter: the IDE one-click Start Menu/WebView2 enable; .gitignore for
`installer\build\`.

## §70 — the secure2 pre-release security sweep: loopback boundary, feed-value gates, release hygiene

**What.** `Desktop/secure2.txt` (the expanded pre-release audit & security sweep directive) applied
to the whole tree. The report is `docs/SECURITY_SWEEP_v0.1b.md` — directive format A–L, 14 findings
(0 Critical / 3 High / 5 Medium / 5 Low / 1 Informational), every fix with a pin, every claim with a
receipt. 13 fixed in this pass; 1 open by design (SS-8: lockfile/SBOM/dependency-scan tooling).
Each fix landed alone on a green suite, test-first: the new tests were run against the untouched
tree first and failed exactly as predicted, then went green.

**The headline class this sweep targeted: the loopback API is reachable by any web page.** A page
the user visits can *send* requests and open websockets to 127.0.0.1 even though it cannot read
cross-origin replies (readback requires same-origin — which DNS rebinding hands the attacker).

**P0 fixes (each with its pin file).**
1. **DNS rebinding → API read** (High): no Host validation existed; `/api/control/config` returns
   the Alpaca key/secret, Telegram token, e-mail password. Fixed by `LocalRequestGuard`
   (`dashboard/app.py:81-148`, module-level so every consumer of the app singleton gets it):
   non-loopback `Host` → 403 (`local_hostname()` handles host:port, IPv6, URLs). Live proof on the
   real socket: `Host: evil.example` → 403; loopback → 200. Pin: `test_request_guard.py`.
2. **Cross-site POSTs** (High): body-less mutating routes (config/reset, engine/stop, logs/clear,
   storage/prune, alerts/clear, replay…) are "simple requests" — a visited page could fire them.
   Same guard: mutating methods must carry no browser Origin or a loopback one, and never
   `Sec-Fetch-Site: cross-site`. Live hostile-page proof (a real `file://` page in Chromium):
   its POST → `403` in the access log, nothing executed.
3. **WS handshake** (Medium): a websocket is not CORS-gated, so `ws://127.0.0.1:PORT/ws` accepted
   any origin. `is_trusted_ws_handshake()` refuses non-loopback Origin / cross-site before accept.
   Live proof: hostile page got close 1006 + server `"WebSocket /ws" 403`; the app's own page
   stays `WS live` (no Origin works too — native clients).
4. **Feed-value gates** (High, market-data integrity): Python's `json` accepts bare `NaN`/`Infinity`
   and every NaN comparison is False, so `float(x) <= 0` could not catch it — **executed proof: a
   NaN close became a candle before the fix**. `bybit_feed._finite()/_level()` now gate trades,
   snapshots and deltas (refused values counted in `book_health()["junk_values"]`), and
   `alpaca_normalize._num()` is finite-or-default. Pin: `test_feed_value_guards.py`.
5. **News-feed URL** (Medium): `?news_url=` was fetched with `urlopen()` — any scheme (a probe read
   a local file as a "feed"), unbounded read (memory DoS), redirects unchecked. Now http(s)-only,
   http(s)-only redirects, 4 MiB cap (`atlas/context.py:59-95`). Pin: `test_context_hardening.py`.
6. **Legacy bind** (Medium): `config/settings.py` defaulted the standalone pipeline to `0.0.0.0`
   (the repo's own feasibility notes had flagged it). Now `127.0.0.1`, README example updated.

**Also fixed, pinned.** Venue URL templates quote the symbol/currency (context.py `_venue_symbol`,
deribit.py:405) — path-param query injection; RSS parser refuses internal-DTD documents
(entity class, `context.py:118`); `/api/control/client-error` folds CR/LF in every field (log
forging); `SECURITY.md` added (private disclosure path, linked from README/CONTRIBUTING);
CI: actions pinned to verified commit SHAs (`11bd719…` v4.2.2, `a26af69…` v5.6.0) + `contents: read`
+ `persist-credentials: false`; a meta CSP on the shell (`index.html:12`) that forbids every remote
target while keeping the inline boot script and the Studies engine's `new Function`;
`docs/phase4/logs-batch-counters.png` re-rendered to drop the maintainer's username from the path
(the only PII found; 17 of 50 screenshots read with vision — credential fields everywhere else were
empty or masked).

**Accepted / documented, not changed (with the reasons in the report).** `GET /api/control/config`
serves the stored secrets: the settings UI and wizard round-trip those fields (masking would blank a
saved token on the next unrelated save) — the mitigation is the boundary guard, and SECURITY.md says
so. No auth by design (same-user ⇒ same file access). Studies `new Function` engine = the plugin
surface. Webhook/ntfy/DTC targets are user-configured on purpose. No lockfile yet (SS-8).

**Verification.** pytest **649 passed / 2 skipped** (629 + 20 pins) · AUDIT CLEAN · ruff clean ·
analytics golden OK (40 cases, 0.0e0) · config golden OK (31/18/49) · 19 UI selftests green
(search-ops prints "all checks passed"). `uvx pip-audit` over the build env: **no known
vulnerabilities**; `uvx bandit -ll`: **0 High**, 13 Medium — all reviewed (9× fixed-URL B310,
B608 = the fixed table-name COUNT(*), B104 fixed by the loopback default, B314 mitigated).
Live Chromium run against a sandbox: guard 403s on the wire, **0 CSP violations / 0 page errors
across 12 views**, WS live; hostile `file://` page refused on both doors. Frozen exe rebuilt and
smoked on 8099: all probed endpoints 200, unknown symbol `[]`, served page carries the CSP and
hash-matches the packaged `index.html` (2d51c1b9…), 0 client-error lines, numpy absent.

**Artifacts.** `docs/SECURITY_SWEEP_v0.1b.md` (the report), `SECURITY.md`, four new pin files +
two new tests in `test_wiring.py`; frozen `dist/` rebuilt from the hardened source
(`ModFlowOrderFlowAnalysisSuite.exe`, 12.7 MB), re-zipped (494 entries, 25.9 MB), installer
rebuilt: `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, 28,119,760 bytes (26.82 MB),
sha256 `E71C53C1BE30393ECD9E86187E759C8E9AD8166C0CA53B451618347525F65DD7` (InstallShield, 0 build
errors). Nothing committed; HEAD `fa202d6`.

**IMMEDIATE NEXT ACTIONS.** Owner's release sequence unchanged: commit → repo → push →
tag `v0.1.0-beta` → attach zip + Setup exe. Recommended P1 follow-up: `uv.lock` + a `pip-audit`/SBOM
CI step (SS-8). Optional: re-shoot the pre-P62 branded screenshots (P3).

## §71 — the display / multi-monitor audit (actionables first; nothing changed)

**What.** The owner asked whether every monitor/display scenario is supported — widget stacks dragged
across monitors, custom layouts combined over one or many displays, full break-apart windows — and
for an audit + actionables before any adjustment. Report: `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md`.
Read-only pass: no source touched, gates stay 649/2.

**Method.** Live probe matrix over CDP against a sandboxed server (port 8092): 16 viewport/DPI
scenarios (4K@100/200 … 1024×640, ultrawide, portrait, 5120-wide dual-span, 1920×700), real
reloads, per-canvas backing-vs-box measurements, a live devicePixelRatio swap with no reload
(the "window moved to a 150% monitor" signal), widget drag/resize driven through the shell's own
handlers (synthetic PointerEvents — the harness's raw CDP input never reached the page; stated in
the report), and a grid of claims checked against source.

**Verified working (receipts in the report).** A 10-widget board built at 5120×1440 re-opens at
1024×640 with every widget intact (grid scrolls, page never overflows); drag `+3 cols/+1 row` →
`x=3,y=1`, grip `+2 cols` → `w=8`, edge drags clamp, at 1024/1920/5120 alike; `ui-compact` engages
below 760 px height; `scale.js` detects a live DPR change (reason `resize-observer`, dpr updated)
and the dpr-aware panels (atlas/chart/heatmap/orderflow) are crisp at 150%; layouts auto-save with
`screen_key`; the whole session logged **0 client errors**.

**Defects found (P0, each with a measured receipt).** (A1) `ofx.js`/`ofx-view.js` contain **zero**
`devicePixelRatio` references — the Engine layers are sized in CSS px, so the flagship view is
blurry on any 125/150/200% display (measured 1406×624 backing vs 2109×936 correct at 150%).
(A2) `mpCanvas` (CVD view, Market Pressure) has **no CSS size**, so the generic fit pass is
self-referential: 480×285 → 720×428 in one `OFAPScale.fit()` at 150%, and it grows again each pass.
(A3) `ofxRibbon` backing ≠ its CSS box in both axes (1652×82 vs 1406×84 in a widget) — stretched
lanes wherever panel width ≠ stage width. (A4) `scale.js fitView()` refits only `.view.active` and
`OFAPScale.register` has **zero callers**; `market-pressure.js` and `drawings.js` have no
`ofap:relayout` listener.

**Structural gaps (P1/P2, features not defects).** The window has no memory: fixed 1500×940, min
1080×680 (bigger than a 1024×640 or 1366×768@150% work area), no x/y/screen, no persistence
(config `ui` block verified to hold theme/accent/density only); `screen_key` is saved but **never
applied at boot** (boot trusts the store's `active` only); no second window, no detach, no pinning
anywhere. pywebview 6.2.1 already ships the APIs needed (`webview.screens` measured on this host;
`create_window(x,y,screen,on_top)`; `Window.move/resize/on_top/events`) — and WebView2 **cannot**
start an OS window drag from inside the page, so the workable form of "drag a widget to another
monitor" is a Send-to-monitor/detach command plus aux windows (stated honestly in the report).

**Next.** Owner's call: land P0 (A1–A3 + the refit-scope loop, each with pins and a dpr=1
regression check), then P1 (window geometry + per-screen layout apply), then P2 (widget windows /
send-to-monitor / pinning). A physical multi-monitor pass by the owner is required after P1 — this
host has one display, so placement/unplug/RDP behaviour is simulated, not observed.

---

## §72 — display hardening landed: the dpr canvas law, document-wide refit, window memory, per-screen layouts

The §71 audit's P0 list and P1 items 5/6 are implemented, pinned and live-verified. Everything is
additive: no panel, control, endpoint or stored shape was removed, and the dpr = 1 path is
byte-identical to what shipped before (that is the regression pin, asserted in the modules'
own selftests).

**A1 — the Engine carries the display scale.** `ofx.js` gained the one place the backing-store
maths lives — `math.layerSize(cssW, cssH, dpr)` (dpr = 1 returns the CSS size unchanged) — plus
`layerDpr()`, `sizeLayer()` (own CSS box first, stage box as the fallback) and
`resetLayer(ctx, canvas, dpr)` (clear at 1:1, then paint in CSS pixels). `resize()` stores
`state.view.dpr`; `drawRibbon()` derives its logical size as `canvas.width / dpr`. Every painter's
coordinate maths is untouched — that was the point of clearing at 1:1 and setting the transform,
rather than rewriting twelve painters. `ofx-view.js paintSpark()` keeps the spark's fixed 90×20 /
88×18 CSS box and carries dpr in the backing store (it used to display at its backing size, so a
scaled monitor drew it soft and a fit pass could resize the element).

**A2 — `mpCanvas` has a CSS box and a redraw path.** `market-pressure.js` sets
`style.width = '100%'` / `style.height = '190px'` before measuring, so the fit pass can no longer
read the backing store back as the box (measured growth before: 480×285 → 720×428 in one fit at
150%, then again each pass). It stores `PRESSURE.lastSeries` and repaints from it on
`ofap:relayout`, skipped while a gesture holds the view (`OFAPINTENT.anyHeld()`).

**A3 — the ribbon is stage-width.** The legend's contract is "volume, delta, CVD on the same X as
the bars", and the ribbon paints in the stage's coordinate space (`worldX`/`xToIndex`) — so its CSS
box is now pinned to the stage width in `resize()` (`r.style.width = boxW + 'px'`), and its
backing store is `round(box × dpr)`. Before: a stage-wide backing store displayed across
`width:100%`, i.e. a ~17% horizontal stretch wherever the readout column was visible.

**A4 — the refit covers the board, not the focus.** `scale.js fitView()` now walks every canvas in
the document (default scope `document`); hidden sections and unpainted tabs have a zero box and are
skipped inside `fitCanvas`, so a non-focused terminal widget is refitted after a window or
display-scale change. `drawings.js` and `market-pressure.js` now listen to `ofap:relayout` too
(the audit's verified listener list was `atlas.js`, `heatmap-pro.js`, `ofx-view.js`, `strips.js`).

**B1 — the window remembers its geometry.** `config_store` ships `ui.window`
(`{width, height, x, y, maximised}`, `x`/`y` None until first close) and `clean_window()` clamps it
(640…10000 × 420…6000, position kept only while ±20000 — a monitor left of the primary is
negative). `launcher.pick_window_geometry(stored, screens)` is the pure choice, unit-tested through
every branch: a stored position wins while a screen still contains it, otherwise the primary; the
size and the minimum clamp to that screen's work area; the pre-§72 geometry is unchanged when no
screen can be measured. The design minimum is now 720×480 with a hard floor of 320×240 **under the
work area** — a 1366×768 display at 150% reports ~911×512, and the old fixed 1500×940 with a
1080×680 minimum could not fit it at all (the test that caught this is
`test_a_display_at_150_percent_is_usable`). `remember_window()` subscribes to the window's
moved/resized/maximized/restored events, keeps the last *normal* rect while maximised, and writes
the config **once, on close**.

**B2 — the layout for this screen is applied at boot.** `shell.js math.screenKeyOf()` composes the
screen identity: `WxH@dpr` at the primary origin (so layouts saved before this still match it) and
`WxH@dpr@x,y` anywhere else, where x/y are the screen's own origin from `window.screen.availLeft/
availTop` — two identical monitors are then two different screens. `math.pickScreenLayout(items,
key, active)` returns the id to switch to (most recently `saved` wins; empty when this screen has
no layout of its own or that layout is already active), and `boot()` adopts it in terminal mode
with a visible notice: `this screen's layout: "…"`.

**Receipts.** Suite **679 passed / 2 skipped** (was 649/2; +30 = `test_display_geometry.py`),
AUDIT CLEAN, ruff clean, both goldens byte-identical, 20 selftests green (ofx 180 → 183, shell
22 → 30). Live on a sandbox (scratch `APPDATA`, so the owner's real config was never touched),
1440×900:
- engine layers: box `1086×520` → backing `1358×650` / `1629×780` / `2172×1040` at 125/150/200%
  (= `round(box × dpr)`, exactly); `OFX.state.view.dpr` tracks the display.
- ribbon: box `1084×82` → backing `1084×82` at 100% (no stretch), `1626×123` at 150%, with
  `style.width = 1086px` = the stage width.
- `mpCanvas`: box `1304×190` → backing `1956×285` at 150%, **identical across three consecutive
  fit passes** (proving the self-referential growth is gone).
- four-widget terminal board at 150%: every visible canvas box × dpr, **zero mismatches**
  (`ofxHeat`, `ofxBase`, `ofxLive`, `ofxRibbon`, `ofxSpark`, `ofxSpark2` + one anonymous canvas).
- a synthetic heat frame painted at 200% (`heatPasses` 0 → 1) with no error; the whole session
  logged **0 client errors**.
- per-screen layouts: a layout saved through the shell's own writer carries `screen_key
  '800x600@1.5'`; with `active` pointed at a different layout, a reload adopted "Probe Screen
  Layout" and showed the notice in the bar.

**Files.** Changed: `desktop/ui/ofx.js`, `ofx-view.js`, `scale.js`, `market-pressure.js`,
`drawings.js`, `shell.js`, `desktop/config_store.py`, `desktop/launcher.py`; pins:
`desktop/ui/ofx.selftest.js` (+5, incl. the dpr = 1 identity), `desktop/ui/shell.selftest.js` (+8),
`test_display_geometry.py` (new, 30 tests). **Remains open:** B3 (always-on-top toggle), P2
(detached widget windows / send-to-monitor / pinning — a feature build, pywebview's
`create_window(screen=, on_top=)` and `Window.move/resize` are the APIs), and the owner's physical
multi-monitor pass (this host has one display). The frozen `dist/` artifacts were rebuilt after
these changes so the release candidate matches the source.

---

## §73 — widget windows: one panel per native window, placed on a monitor, restored on launch

The §71/§72 audit's P2 item and its P1 item 7 (always-on-top) are built. A power user can now pull
any panel out of the board into its own real native window, put it on another monitor, pin it above
other windows, and find the whole arrangement back after a restart. Everything is additive: with no
native host (a browser, a headless run, a test) the endpoints say `native: false` and the UI draws no
window controls at all — the browser experience is byte-for-byte what it was.

**The seam, and why it is shaped this way.** The page decides *what* should be in a window; the
launcher owns *how* a window comes into existence. Between them:

- `desktop/windows.py` — `place_aux(record, screens, count, screen_index)` is the pure placement
  choice (an explicit monitor wins; a stored position wins **while a screen still contains it**, so
  an unplugged monitor can never place a window off-desktop; size and position clamp to that
  screen's work area; a fresh window cascades by 28 px so two opens do not stack). The module also
  carries the `WindowHost` contract, the installed host, and the record persistence (`records`,
  `add_record`, `drop_record`, `update_geometry` — throttled to one config write per 2 s).
- `config_store` — `ui.windows` is the **desired set**: opening adds, closing (from either side)
  removes, and a launch restores exactly what was open. `clean_window_record`/`clean_windows` clamp
  it (identified ids, view slugs, 360…6000 × 300…4000, unique, capped at 8).
- `desktop/api.py` — `GET/POST /api/control/windows`: the state (screens labelled "Monitor 1 ·
  2560×1440 · 150%", what is open, the stored set, the cap), and the actions `open / close / focus /
  ontop / close_all`. Every answer carries the *resulting* state; `native: false` is a first-class
  answer, not an error.
- `desktop/launcher.py` — `NativeWindowHost` creates the real pywebview window (`?aux=<view>&win=<id>`,
  `on_top`, `min_size`), keeps the store's geometry current from the window's own moved/resized
  events, and drops the record when the window closes (including the OS's X).
  `restore_windows(port)` reinstalls the host and reopens the stored set **before**
  `webview.start()`, re-placing anything whose monitor is gone.
- `desktop/ui/windows-ui.js` (new) — everything the user touches: the menu is built from a pure
  `OFAPWINDOWS.model(state, focus)` (unit-tested in Node), the terminal bar and the Classic top bar
  each carry the control (exactly one visible, following the mode), and the auxiliary window's own
  bar carries its pin and its close.
- `desktop/ui/shell.js` — `?aux=<view>` is detected as `AUX`: the window renders a synthetic
  one-widget layout, **never** reads or writes a layout, never changes the mode, never adopts a
  screen's layout, clears its hash at boot and refuses to add a second widget.

**Receipts (live, on the owner's desktop, scratch `APPDATA` so his config was never touched).**
Real windows enumerated with `EnumWindows` at each step:
- opened `ofx` → a visible window "… — OFX" at (680, 282) 1200×820 — the placed centre of the
  2560×1440 screen; a second window (`cvd`) cascaded to (758, 340); a third from the board's
  terminal-bar control after focusing it.
- pin → `on_top` in the store, and the aux window's own 📌 button flipped it (CDP-driven UI click).
- close from the API, close from the aux window's own ×, and close from the **OS** (WM_CLOSE, i.e.
  as if the user clicked the title-bar X): each removed the window and its record.
- quit and relaunch → both stored windows came back at their exact stored rects, pinned state
  intact (`open after restore: ['w303bd2c', 'w7185c6f']`).
- the UI itself, driven over CDP into WebView2 (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port`):
  Classic shows `⧉ Windows · 1` in the app's top bar and the terminal bar shows nothing; switching
  to terminal mode moves the control to the board's bar and empties the top bar; the menu listed the
  open windows, "Close every widget window", "Open OVERVIEW in its own window" and "Send OVERVIEW
  to ▸ Monitor 1 · 2560x1440"; clicking a row really opened the window. An auxiliary window renders
  **exactly one widget** with no tabs, its name in the title, its pin and close — and its note says
  `this window is fixed to Time & Sales` if anything tries to add a second panel.
- Two real defects the live pass found and closed: `#overview` (the previous window's hash) made the
  aux window open a **second widget** through the shell's `showView` hook → guarded in `openWidget`
  and the hash is cleared at aux boot; and in Classic mode the control did not exist at all (the
  terminal bar is a terminal-mode object) → the app's top bar now carries a copy, and the target for
  "open/send" in Classic is the view being looked at.

**Gates.** Suite 679 → **712 passed / 2 skipped** (+33 = `test_aux_windows.py`), AUDIT CLEAN (275
html ids + 229 created, 0 missing), ruff clean, both goldens byte-identical, **21** selftests green
(new: `windows-ui.selftest.js`, 10 checks).

**Honest limits.** Literal drag-a-widget-out-of-the-window is impossible on WebView2 — there is no
OS-level drag initiation from inside the page — so the shipped form is the command path
(Windows ▸ Open / Send to monitor ▸), which is also what a keyboard user gets. Moving an *aux* window
between monitors is the OS's own drag, and its geometry is remembered when it lands. As with §71/§72,
the physical multi-monitor pass is the owner's: this host has one display, so "a second monitor" was
exercised as a second *window* on one screen plus the placement maths under test for every screen
shape.

**Files.** New: `desktop/windows.py`, `desktop/ui/windows-ui.js`, `desktop/ui/windows-ui.selftest.js`,
`test_aux_windows.py`. Changed: `desktop/api.py` (endpoints), `desktop/config_store.py`
(`ui.windows` + clamps), `desktop/launcher.py` (`NativeWindowHost`, `restore_windows`, wired into
`main()`), `desktop/ui/shell.js` (AUX mode, aux bar, guards), `desktop/ui/index.html` (script tag +
`#topWins`), `desktop/ui/atlas.css` (§73 styles).

---

## §74 — the pre-tag pass: the corpus is committed, the counts refreshed, SS-8 closed

**What this pass is.** With the owner's go, the fixed tree went into history and the release face
was made exact: commits, docs/counts, CI, lockfile. No source semantics changed.

**The series — 18 commits, `fa202d6..14b4759`** (`git log --oneline fa202d6..14b4759` is the register):

```
1aa2a17 atlas: the alerts card reads, edits and fires like the engine means it (P1-7)
a5b0086 desktop: five bar expression modes, measured palettes, and the legend that names them (P1-8)
457bc28 desktop: the one shortcut map, and the palette crash it uncovered (P1-9)
b6e63ec desktop: the age of every panel's data, declared (P1-10)
3b3ff83 desktop: the hover path is indexed, the heat pass change-gated, the frame yields (P2)
26930fe data: the session has a boundary, the database has a window (P3-2)
01f2204 atlas: the heat wire, the carry-overs, and the inline text editors (§56/§57)
efb86a1 desktop: the ModFlow badge becomes the iconography (§60–§62)
272f85c chore: the package diet — numpy out, stdlib in (§63)
0b3507c fix: the source switch called a property; the Python 3.11 hang — the release passes (§64/§65)
c35dd59 chore: the lint pass — unused imports and dead aliases dropped (§64)
350d360 tests: the v0.1b audit return — seven fixes pinned, three probes rejected (§66–§68)
f822052 installer: the Windows installer built, verified, documented (§69)
ea83c48 security: the secure2 sweep — the loopback boundary, feed gates, release hygiene (§70)
4110ea6 desktop: display hardening — the dpr canvas law, refit, window memory (§71/§72)
c25f36d desktop: widget windows — one panel per native window, placed and restored (§73)
fcd0a21 docs: the trail through §73, and the pre-release count pass (handoff, plan, resume, readme)
14b4759 chore: the dependency lock, the CI audit, and the third-party notices (SS-8)
```

**How it was split.** One commit per wave, each file staged exactly once (verified: 166/166 dirty
entries assigned, no file in two commits). A file touched by several waves carries its **final**
content in the latest wave's commit — `index.html` rides in the §73 commit, `dashboard/app.py` in
the §70 commit. The per-section change sets at the end of §§40–65, §70, §72, §73 remain the
authoritative file→section map; the messages carry the §-refs.

**The release face, made true (the audit's N-2/N-3).**
- `SECURITY.md` — the vendored chart library is **Apache-2.0** (was mislabelled "MIT"); the version
  string is `v0.1.0-beta`. New `THIRD_PARTY_NOTICES.md` at the root: the vendored copy (banner
  retained) + the Python dependency licence story (the frozen build carries
  `_internal/*.dist-info/licenses/`).
- Counts re-derived (2026-09-16): suite **712/2 on both interpreters**; UI selftests **20** (shell
  30, ofx 183, + windows-ui 10 — RESUME's list updated); README badges true (tests 644→712, code
  ~62k→~64k, API 132→**133** routes — measured from the running app's OpenAPI: 45 atlas + 72
  control + 16 legacy); File Inventory re-measured (**175 files / 27,237 py / 36,583 UI / 63,820
  total**; suite 68 files / 12,371 lines); the tree diagram's `(NNNL)` claims re-checked — five
  drifted since §66 and were corrected (app.py 1371, bybit_feed.py 329, absorption.py 266,
  initiative.py 136, settings.py 815); CONTRIBUTING baseline updated.

**SS-8 closed.** `uv.lock` committed (59 packages, `uv` 0.12.8); CI gains a pinned dependency-audit
step: `uv export --frozen` (lockfile integrity) → `pip-audit` over the locked set — clean on
2026-09-16. `.gitignore` covers the tool caches. An SBOM artifact remains optional.

**Receipts.** pytest **712 passed / 2 skipped** on 3.12 (24.5 s) *and* 3.11 (24.5 s) — on the exact
committed content; `audit_ui_refs.py` **AUDIT CLEAN** (71 modules); ruff clean; analytics golden
**0.000e+00** (40 cases); config golden **49 instruments**; **20/20** selftests; API surface **133**
operations. Frozen artefacts re-verified against the committed tree: **90/90 bundled loose files
byte-identical**, no source file newer than the build — **no rebuild needed** (docs/CI-only pass);
the zip/setup exe hashes in the RE-ATTENDANCE block remain the release candidates.

**Next (owner).** Push (the remote decision), the physical multi-monitor pass, release-notes
review, then the tag `v0.1.0-beta` + attach zip + Setup exe.

## §75 — the post-beta left-overs: N-1 in the build, CI lint/SBOM parity, and the screenshot re-shoot (closed)

**Why.** After §74 this pass picked up the plan's optional left-overs, asked for in one breath:
(1) the N-1 single-instance guard, (2) ruff-in-CI step parity (N-4), (3) an SBOM artifact (SS-8
was pip-audit only), and (4) re-shooting the pre-§62-branded screenshots in `docs/screenshots/`
(the Sep 14 batch still shows the retired OF tile / "OrderFlow Analysis Pro" wording; the Sep 16
p-series already carries the ModFlow badge). The owner paused the pass mid-way to bank the state
(`b0681a2` was the save point); the **re-attendance closed it** — screenshots landed, counts
re-measured, `dist/` rebuilt and re-verified, gates green on both interpreters — and the closing
commits are `58101f4` (the shots, the counts, the release evidence) and this record.

**Landed and committed.**

* `12211e2` — **the single-instance guard (N-1).** `desktop/single_instance.py`: a named mutex keyed
  to the config directory (sha1 of the casefolded path), taken on windowed launches only — headless
  runs stay exempt because every smoke recipe opens its own scratch APPDATA and runs alongside the
  owner's app; non-Windows is a no-op; unexpected OS errors fail open. A second windowed launch
  finds the mutex held, brings the existing window forward (EnumWindows by window title, best
  effort) and exits 0; if no window can be found it says so in a message box. 4 pins in
  `test_single_instance.py` (name stability across case/slashes/trailing separator, a second
  acquisition of a held name refused, reacquisition after release, a quiet focus miss). Wiring:
  `launcher.main`, after config load, `if not args.headless`. Suite: **716 passed / 2 skipped**
  (3.12, 24.4 s — 712 + the four new pins; the 3.11 re-run belongs to this pass's end).
* `d4fe370` — **CI parity + SBOM (N-4; SS-8's artifact).** CI now pins `ruff==0.16.7` and runs the
  lint baseline on 3.11 and 3.12 (the step CONTRIBUTING always described but CI skipped), and the
  dependency-audit job gains a lockfile SBOM: `uv export --frozen --format cyclonedx1.5`, uploaded
  with `actions/upload-artifact` pinned to v4.6.2 (`ea165f8d`). CONTRIBUTING's intro sentence now
  reads "the lint baseline and a dependency audit". The release SBOM for this build was generated
  beside the zip: `dist/ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json` (CycloneDX 1.5, 42
  components) — attach it to the GitHub release with the zip and the Setup exe.

**The screenshot re-shoot — landed.**

Eleven shots (the Sep 14/15 batch: 4 atlas-* + 7 desktop-*) were re-captured from one live sandbox
session at their original dimensions and are now in `docs/screenshots/` (1264×569 for the atlas-*
set, desktop-heatmap-live and desktop-chart-value-area; 1500×940 for the desktop-* set — every
frame matching the size of the file it replaced, header-checked), all from one clean run (green
Setup dot, no wizard, no MT5 notice). **All eleven were vision-checked**, one was re-shot:

| file | size | state |
|---|---|---|
| atlas-heatmap.png | 1264×569 | verified — map canvas full |
| atlas-cvd.png | 1264×569 | verified — divergence series + table drawn |
| atlas-profile.png | 1264×569 | verified — TPO ladder + volume bars drawn |
| atlas-trackers.png | 1264×569 | verified — live prints + ladder |
| desktop-heatmap-live.png | 1264×569 | verified — full liquidity map (240 buckets × 200 rows) |
| desktop-chart-value-area.png | 1264×569 | **re-shot this pass** — card note + POC/Δ-V chips, no clip |
| desktop-overview-live.png | 1500×940 | verified — KPIs, session summary, market context |
| desktop-live-session.png | 1500×940 | verified — live session, Stop engine visible |
| desktop-window-overview.png | 1500×940 | verified — live session + headlines |
| desktop-window-heatmap.png | 1500×940 | verified — full liquidity map |
| desktop-chart.png | 1500×940 | verified — candles + VWAP band + the POC line |

**One re-shoot, and the rule it taught.** `desktop-chart-value-area.png` first came back with the
Price-action card's note clipped mid-line at the top edge — the previous session had scrolled the
view's scroller ~297 px to bring the chart canvas up. Fix (now in the skill's screenshot
reference): **align the card head to the scroller top by measuring** (`.views` scroller +=
`card.top − views.top`), never by a fixed amount — and read the 70–100 px band under the toolbar as
chrome, not as a clip: the toolbar's own controls (`Classic|Terminal` segment, `Stop engine`, the
live chip) stick ~16 px into the content area and look like clipped content in a crop.


The sandbox: `APPDATA="$LOCALAPPDATA/Temp/ofap_shots_sandbox" .venv/Scripts/python.exe -m
orderflow_system.desktop --headless --port 8093`, engine started via `POST
/api/control/engine/start`; PID 20564 at save time (`taskkill /PID 20564 /F` to stop — scratch
APPDATA only, nothing of the owner's touched). Sandbox config carries `onboarding_done: true`,
`setup_complete: true`, `mt5.notice: seen`, so a reload carries no wizard, a green rail dot and no
MT5 notice.

The capture recipe (browser tool; the daemon session was named `shots`):

1. `goto_url('http://127.0.0.1:8093/desktop/')`, wait; switch views with **`showView('<slug>')`**
   (slugs = the rail's `button.nav-item[data-view]` values — overview, chart, heatmap, cvd,
   profile, trackers, …; no hash navigation).
2. Size via CDP `Emulation.setDeviceMetricsOverride` — **1264×569** for the atlas-* set, heatmap-live
   and chart-value-area; **1500×940** for the desktop-* set. The override persists across calls in
   a session — reset it before each size group.
3. Heatmap views: scroll the view's scroller so the biggest canvas sits ~30 px below the scroller
   top (the map otherwise sits below the cards fold).
4. Chart shots: `#ovVP` (the POC/VAH/VAL overlay checkbox) on.
5. Overlays: wizard `#wizClose`; MT5 notice `#mt5NoticeNever`. Both fire on a fresh load until
   their config flags are set.
6. Capture with CDP `Page.captureScreenshot` (PNG) → write the bytes to the staging dir.

**How the re-attendance closed (in order).**

1. **Screenshots** — the six "check due" frames vision-checked plus the five eye-verified ones
   reviewed; one re-shoot (`desktop-chart-value-area.png`, above); all eleven copied into
   `docs/screenshots/`, and the caption rows in `docs/DESKTOP_GUI_FEASIBILITY.md` re-written to
   describe these files (kept timeless where the numbers moved) with a line recording the re-shoot.
2. **Counts** — README tests badge 712 → **716**; File Inventory re-measured (**176 files /
   27,407 py / 36,583 UI / 63,990 total** — the Desktop-app row 23 → 24 files, 8,895 → 9,065 lines:
   `single_instance.py`'s 162 plus `launcher.py`'s +8 net); suite **69 files / 12,422 lines**;
   CONTRIBUTING's baseline 716. The `launcher.py` (NNNL) row the plan expected does not exist — the
   Project Structure tree carries no per-file counts for `desktop/`; the File Inventory row is where
   the growth shows. One stale count turned up while re-measuring: the architecture diagram's
   "132 REST/WS routes" (the badge already read 133) — corrected.
3. **Rebuild.** The guard touched a bundled file, so the frozen `dist/` (zip `b571c655…`, Setup
   `d2435b6f…`, exe `cfde70b0…`) was stale as a release candidate since `12211e2`. Rebuilt the
   chain — exe (`build_exe.py`) → zip → Setup (`installer/make_installer.ps1`, 0 errors) — re-ran
   the payload check (90/90), the live probe battery (21/21) and the new double-launch acceptance
   on the frozen exe, and re-ran the installer journey. New hashes in
   `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`; the stale ones are gone from this file.
4. **Gates on the final tree** — full pytest on **both** interpreters (716/2 each), audit_ui_refs
   (AUDIT CLEAN), both goldens, 20 selftests, ruff, `pip-audit`: all green (receipts below).

**Receipts.** Suite **716 passed / 2 skipped on both interpreters** (3.12 in 24.4 s, 3.11 in
24.6 s); `audit_ui_refs.py` AUDIT CLEAN (71 modules); ruff 0.16.7 clean; analytics golden 0.000e+00
(40 cases, 2196 numeric leaves); config golden 31/18/49; **20/20 UI selftests**; `pip-audit` over
the locked set (42 packages) clean. Screenshots 11/11 vision-verified at their original sizes and
landed in `docs/screenshots/` (+ captions). Frozen artefacts rebuilt from the hardened tree: exe
`10e6bdf8755abb0e…` (13,371,238 B), zip `00b96304e54949e0…` (27,229,338 B — 496 files, 7-Zip test
OK, extraction byte-identical to the folder), Setup `c3a14576a5a5a5b5…` (28,173,338 B, 0 errors /
4 warnings, ships the same exe), SBOM CycloneDX 1.5 (42 components); all four hashed into
`docs/RELEASE_EVIDENCE_v0.1.0-beta.md`. Payload check: **90/90 loose files byte-identical** to the
tree, no source file newer than the build. Probe battery against the frozen exe: **21/21** — hostile
`Host` → 403 on `/healthz` and `/api/control/bootstrap` (nothing leaked), cross-origin + cross-site
POST → 403, cross-origin + cross-site WS handshake → 403, native WS → 101 with the app's own
`pong`, same-origin/native POST → 200, cross-origin read → 200, `/desktop` byte-identical to the
packaged `index.html` (sha256 `d61ebc1f8c2c33d3…`) and carrying the CSP, unknown symbol → `[]`
(candles + markers), 0 numpy entries in 586 `_internal` entries, 0 `client error:` lines.
Double-launch acceptance (windowed, scratch APPDATA): first launch opens the window on 8080; the
second **exits 0** and focuses it — still one process, one window, one port; a third is refused the
same way; WM_CLOSE closes in ~2 s, frees the port, and the next launch comes up (the guard releases
on close). Installer journey: silent install 496 files, installed exe hash == dist exe, shortcut
targeting the installed exe, ARP entry `0.1.0` (`{197F9514-…}`); the installed app smoked on 8098
(healthz 200, BTCUSDT candles 200, unknown symbol `[]`, hostile Host refused, 0 client errors);
silent uninstall cleaned dir + shortcut + ARP; `%APPDATA%` untouched and the owner's development
shortcut restored.

**Two build-tool lessons (both measured here).** (1) PowerShell 5.1's `Compress-Archive` **mangles
this tree's archive entry names** (truncated prefixes, the main exe entry lost) — the release zip is
built with Python's `zipfile` (or 7-Zip) instead; verify with `namelist()` + a `7z t` pass. (2) The
installer's Add/Remove Programs entry registers under the **32-bit** registry view
(`HKLM\Software\WOW6432Node\…\Uninstall`), so a native-view query reports "no ARP entry" while the
product is installed — query the WOW6432Node key (or `Win32_Product`) before concluding anything
about the install.

**Nothing pushed.** The owner's queue is unchanged: push (the remote decision — `origin` is still
the original author's repo), his **physical multi-monitor pass** (§76 if it finds anything), the
release-notes/tag review, then the tag `v0.1.0-beta` + attach the zip + Setup exe + SBOM.
