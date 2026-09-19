# ModFlow OrderFlow Analysis Suite — UX/GUI inventory (the comparison baseline)

**Target:** `C:\Users\<you>\OrderFlow-Analysis-Pro` (ModFlow OrderFlow Analysis Suite; Python FastAPI + SQLite backend, pywebview/WebView2 shell, vanilla-JS dashboard under `orderflow_system/desktop/ui/`, no bundler).
**Method:** static read-only inspection (grep / find / wc / small Python counts) of the shipped source. **No file was modified, nothing was built, no app was launched.**
**Every count below is a real grep/wc count unless the line says "not measured".** `file:line` cites are of the form *path:line* within the repo root.
**Date of extraction:** 2026-09-18. Repo HEAD per `docs/RESUME.md`: `110c568`, 108 dirty entries, nothing committed.

Sizes (measured, `wc -l`): `desktop/ui/index.html` **1194**; all top-level `desktop/ui/*.js` **37,631**; all `ui/*.css` + `themes/*.css` **1908**. JS files under `ui/`: **95** total = **83** top-level `.js` (28 of them `*.selftest.js`) + vendor/subdirs; **66** non-vendor, non-selftest JS files.

---

## 1. Views & panels — the rail and what each view declares

### 1.1 Rail entries

| Bucket | Count | Evidence |
|---|---|---|
| Static rail buttons (`<button class="nav-item …">`) | **29** | `desktop/ui/index.html:55-84` (one per line 55…84; `grep -c 'class="nav-item'` = 29) |
| Runtime-added rail buttons | **3** | Setup wizard (inserted *above the first* nav item) `ui/guide.js:2298-2318` (insert at 2314-2315); Scanner (inserted before Trackers) `ui/scanner.js:62-72`; Guide (inserted before Logs) `ui/guide.js:390-397` |
| **Rail buttons at runtime** | **32** | 29 + 3 |
| Rail badges (live counters) | **3** | `#navTrackerCount` `index.html:64`, `#navSignalCount` `index.html:68`, `#navAlertCount` `index.html:74` |

Static rail order (`index.html:55-84`): Overview 55 · Chart 56 · Heatmap 57 · Studies 58 · Order Flow 59 · Engine/ofx 60 · Depth 61 · Time & Sales 62 · Market Watch 63 · Trackers 64 · CVD 65 · Profile 66 · Frames 67 · Signals 68 · Strategy 69 · Performance 70 · Journal 71 · *(rail-spacer 72)* · Replay 73 · Alerts 74 · Instruments 75 · Alpaca 76 · Platforms 77 · Settings 78 · Logs 79 · Watchlist 80 · News 81 · Calendar 82 · Fundamentals 83 · Options 84.
Rail footer: platform label `#railPlatform` 86, **Terminal mode** button `#railTerminal` 87-88, "Classic terminal ↗" external link 89 (`index.html:85-90`).
Rail chrome: brand mark + `#railHide` (‹) `index.html:43-53`; edge reveal arrow `#railReveal` (❯) `index.html:95`.

**Note (observed in code, not verified at runtime):** `keys.js` maps digits `1…9` to `.rail .nav-item[0…8]` (`ui/keys.js:236-242`, annotation at `321-323`). Because the Setup-wizard button is inserted *first* (`guide.js:2314-2315`, mounted by an IIFE that retries up to 40×500 ms — `guide.js:2338-2346`), the digit row shifts by one at runtime (1 → Setup wizard, 2 → Overview, …). The same shift affects the "1…9" accelerators shown in the View menu (`menubar.js:56-67`, `accel: i < 9`).

### 1.2 View sections and their cards

`<section class="view" data-view="…">` **29** (`grep -c` = 29; `index.html:152-1111`), plus **2** injected at runtime (Scanner `scanner.js:75-78`; Guide `guide.js:404`) → **31** view sections at runtime.
Cards declared in `index.html`: **58** (`grep -o 'class="card"'` = 58; card / card-head / card-title / card-body each appear 58×). KPI tiles: **39** (`class="kpi"`). View heads: **29** (`class="view-head"`).

| # | View (`data-view`) | Section lines | Cards (n) — `index.html:line` | KPIs |
|---|---|---|---|---|
| 1 | overview | 152-189 | **3** — Systems 159, Session summary 175, Latest signals 183 | 4 (169-172) |
| 2 | chart | 192-232 | **2** — Price action 222, Data box 227 | 4 (217-220) |
| 3 | studies | 236-266 | **0** (body host `#studiesBody` 265; view-local `<style>` 237-257) | 0 |
| 4 | orderflow | 268-292 | **1** — Footprint 278 | 4 (271-276) |
| 5 | ofx | 295-361 | **0** — canvas stage 343-351, readout 350, ribbon 352, legend panel 353-359, symbol look-up panel `#ofxSymbolPanel` 333-341 | 0 |
| 6 | depth | 363-373 | **1** — Order book 371 | 3 (366-370) |
| 7 | tape | 376-382 | **1** — Tape 380 | 0 |
| 8 | marketwatch | 385-409 | **1** — Board 389 | 0 |
| 9 | signals | 412-417 | **1** — Signal cards 415 | 0 |
| 10 | strategy | 420-429 | **2** — Fabio methodology checklist 424, Microstructure 426 | 0 |
| 11 | performance | 432-437 | **1** — Journal 435 | 0 |
| 12 | heatmap | 440-475 | **3** — Liquidity map 463, Level events 468, Fresh walls 471 | 4 (457-462) |
| 13 | trackers | 478-525 | **8** — Iceberg 489, Sweeps 493, Imbalance ladder 498, Stacked imbalances 502, Big-trade zones 507, Stop runs 512, Big trades 516, Liquidations 521 | 4 (482-487) |
| 14 | cvd | 528-546 | **2** — CVD vs price 539, Divergences 543 | 4 (533-538) |
| 15 | profile | 549-565 | **2** — TPO ladder 559, Session reads 562 | 4 (552-557) |
| 16 | frames | 568-584 | **2** — Closed bars 577, Recent bars 581 | 0 |
| 17 | replay | 587-666 | **3** — Source 592, Transport 607, Simulated account 628 | 8 (622-627, 654-659) |
| 18 | alerts | 669-693 | **3** — Alert log 677, Rules 681, Persisted history 688 | 0 |
| 19 | instruments | 696-711 | **1** — Coverage 703 | 0 |
| 20 | platforms | 715-745 | **0** (body host `#platformsBody` 744; view-local `<style>` 716-736) | 0 |
| 21 | journal | 748-768 | **2** — Trades 756, Daily P&L 766 | 4 (`#jnStats` host 755, filled at runtime) |
| 22 | calendar | 771-794 | **2** — Upcoming 780, Watch filter 783 | 0 |
| 23 | settings | 796-996 | **9** — Appearance 800, Data & engine 821, Telegram alerts 838, Order-flow (reference layout) settings 851, Pattern thresholds 860, Order-flow extras 867, Storage 874, Backup & reports 907, Updates 956 | 0 |
| 24 | alpaca | 999-1051 | **3** — Symbols 1009, Live feed 1017, "What Alpaca adds — and what it cannot" 1036 (+ card host `#alpCardHost` 1008) | 0 |
| 25 | logs | 1054-1063 | **1** — Engine log 1057 | 0 |
| 26 | watchlist | 1065-1074 | **1** — Instruments 1068 | 0 |
| 27 | news | 1076-1085 | **1** — Headlines 1079 | 0 |
| 28 | fundamentals | 1088-1098 | **1** (title `#fundamentalsSymbol` 1092) | 0 |
| 29 | options | 1100-1111 | **1** — Chain 1103 | 0 |

**Cards added at runtime, not in `index.html`:** the Overview gains a "Market context" card (`ui/context.js:15-18` — "owns one card appended to the Overview view"; mount at `context.js:56-`), the Alpaca view renders its own card into `#alpCardHost` (`index.html:1008`, `ui/alpaca-card.js`), and the Overview also hosts `#ovBanner`/`#ovAlpacaBanner`/`#ovAlpacaHost` (`index.html:157-158, 188`). Total runtime card count was **not measured** in a live window.

**Views with no pause control:** heatmap, cvd, profile, frames, strategy, performance, replay, alerts, instruments, platforms, journal, calendar, settings, logs, watchlist, news, fundamentals, options, studies, alpaca (see §4.2 and gap F6).

### 1.3 Where panels are populated

Most views are fill-in-the-blank shells: the markup declares structure and ids, JS module(s) of the same name fill them (`ui/ui.js` 1696 lines drives overview/chart/orderflow/depth/tape/signals/depth/marketwatch; `ui/atlas.js` + `ui/atlas-v2.js` drive heatmap/trackers/settings threshold grids; `ui/ofx.js` + `ui/ofx-view.js` the Engine view; `ui/journal.js`, `ui/calendar.js`, `ui/watchlist.js`, `ui/news.js`, `ui/fundamentals.js`, `ui/options.js`, `ui/windows-ui.js` the R-build views). Load order is the script list at `index.html:1117-1182` (**50** `<script>` tags).

---

## 2. Layout & windowing model

### 2.1 The frame

```
body > div.app                       index.html:39
├── aside.rail                       index.html:42-91
│   ├── .brand (+ #railHide ‹)       43-53
│   ├── 32 nav-items (29 static)     55-84
│   └── .rail-footer (#railPlatform, #railTerminal, Classic-terminal link)  85-90
├── button#railReveal ❯              95
└── div.content                      98
    ├── nav#menuBar.menubar          99          (filled by menubar.js)
    ├── header.topbar                100-147
    │   ├── #menuBtn ☰ (/)           101
    │   ├── span#topWins ⧉           104         (windows-ui.js, classic mode only)
    │   ├── span.brand-mini          105
    │   ├── #railToggle ⇤            106
    │   ├── .symbol-picker (#symbolSelect)  107-110
    │   ├── pills: #enginePill 111, #wsPill 115, #sourcePill 116, #livePill 120
    │   ├── .seg#modeSwitch (Classic | Terminal)  125-130
    │   ├── #btnStart 131, #btnStop 132, #btnRestart 133
    │   ├── #menuPanel (filter + #menuBody)  134-137
    │   ├── #hotkeySheet overlay       138-140
    │   ├── #ofapPause chip            141-142
    │   └── #menubarToggle ⌃ menu bar  145-146
    ├── main.views (31 sections)      149-1113
    └── div.statusbar                 1183-1192  (7 fields + hint)
```

Status bar fields (`index.html:1184-1191`): `source`, `workspace`, `mode`, `tab`, `widgets`, `feed`, `bus`, plus `#statusHint` (default text set at `ui/menu.js:164`: "Ctrl+K palette · P pause · ? hotkeys · ☰ menu").

Chrome can be hidden piecewise: rail / menu bar / status bar + zen (`ui/chrome.js:12-13`, persisted per browser under `ofap.chrome`, `chrome.js:13-45`), with in-bar hide buttons (`#mbHide`, `#railHide`, `#railToggle`, `#menubarToggle`, `#railReveal` — `chrome.js:64-72`).

### 2.2 Terminal mode — panels as widgets

- Model (file header): a view is a `<section class="view" data-view="X">` that boots itself; terminal mode **re-parents** the section into a widget frame, preserving DOM + listeners; Classic is untouched (`ui/shell.js:1-22`).
- Constants: grid **12 × 8** (`shell.js:27`, mirrored server-side at `config_store.py:56-57`), starter board `['overview','ofx','tape','depth']` (`shell.js:28`), sizes `m=[6,4] l=[8,5]` (`shell.js:29`), **max 12 tabs** (`shell.js:30`), **max 24 widgets/tab** (`shell.js:31`).
- Widget chrome: drag bar (`shell.js:461-462, 486`), link chip `buildLinkChip` (`shell.js:802-887`), gear → per-panel variable editor (`shell.js:463-464, 933`), maximise (⛶, `shell.js:465-467, 906`), close (×, `shell.js:468-470, 1166`), resize grip (`shell.js:481-483`), click-to-focus (`shell.js:489-490`).
- Gestures: `beginGesture`/`onGestureMove`/`endGesture` use PointerEvents, cell-quantised, clamp to the grid, auto-save on gesture end (`shell.js:683-740`); tabs support drag-reorder (`shell.js:596`), add/close/rename (`shell.js:614, 630, 650`).
- Mode switch: the topbar segmented control `#modeSwitch` (`index.html:125-130`), the rail button `#railTerminal` (`index.html:87-88`), and **Ctrl+Alt+T** (`shell.js:1736`).
- Status feedback: the bar shows messages via `paintBar()` (`shell.js:968`) and the status bar mirrors mode/tab/widgets (`shell.js:1524-1549`).

### 2.3 Layouts & workspaces — what persists

Store: `config_store.py` block `"layouts": {"mode": "classic", "active": "", "items": {}}` (`config_store.py:320`); sanitiser `_sanitise_layouts` (`config_store.py:732-752`) and `_clean_layout` (`662-729`).
Caps and shape (measured constants): `LAYOUT_ID_RE`/`LAYOUT_VIEW_RE` (`45-46`), `LAYOUT_MODES = ("classic","terminal")` (`53`), `LAYOUT_THEMES = ("dark","light")` (`54`), grid 12×8 (`56-57`), **`LAYOUT_MAX_ITEMS = 24`** (`58`), **`LAYOUT_MAX_TABS = 12`** (`59`), **`LAYOUT_MAX_WIDGETS = 24`** (`60`). Per layout it keeps `id, name, mode, screen_key, theme, saved, tabs[ { id, name, widgets[{view,x,y,w,h,link,settings}] } ]` (`config_store.py:721-729`).
Screen identity: `screen_key = "<w>x<h>@<dpr>[@{x},{y}]"` (`shell.js:64-79`), applied on boot by `pickScreenLayout` (`shell.js:84-96`) → the "this screen" label the Layout menu shows (`menubar.js:401-403`).
CRUD from the Layout menu: save now / save as / duplicate / delete (types the name to confirm — `shell.js:1370-1377`) / auto-arrange / reset to starter / save-for-this-screen / export / import (`menubar.js:363-437`; implementations `shell.js:1215,1304,1345,1372,1184,1443,1431,1464,1485`). The menu footer prints `<n> of 24 layouts` (`menubar.js:431`).
A second, older concept — **workspaces** — persists the *view/state* snapshot, not the terminal arrangement: `config_store.py:316` + `/api/control/workspaces` (`api.py:2923, 2930`), menu `File ▸ New/Save/Open workspace` (`menubar.js:543-546`). The overlap between Workspaces and Layouts is recorded as gap **F4** (§8).

### 2.4 Auxiliary windows (one widget per real OS window)

- Server module `desktop/windows.py` (270 lines): placement is a pure function `place_aux` (`windows.py:77-148`) — explicit monitor index wins, else a stored position *while a screen still contains it*, else the primary, with an 8-step cascade (`windows.py:34, 139-141`); default size **1100×760** (`windows.py:38`); chrome allowance 56 px (`windows.py:32`); geometry writes throttled to 2 s (`windows.py:36`); screen labels "Monitor N · 2560×1440 · 150%" (`windows.py:45-55`).
- **Max 8 windows** (`config_store.WINDOWS_MAX = 8`, `config_store.py:49`; clamp loop `649-655`); minimum window 360×300 (`AUX_MIN_W/H`, `config_store.py:605`).
- Real windows are created by `launcher.NativeWindowHost` (`launcher.py:316-453`) with `create_window(url, x, y, width, height, min_size, on_top)` where the URL is `/desktop?aux=<view>&win=<id>` (`launcher.py:365-376`); pin/unpin = `window.on_top` (`launcher.py:448-453`); `close_all` sweeps widgets when the main window closes and *keeps* the stored records so they return next start (`launcher.py:417-434`).
- Restored before `webview.start()` (`launcher.restore_windows`, `launcher.py:456-480`).
- Persisted as `ui.windows` — "the desired set, not a history" (`config_store.py:478-482`, sanitised at `1109-1111`).
- Page side: `ui/windows-ui.js` (317 lines) — pure menu model (`windows-ui.js:31-71`), the menu offers *Open <VIEW> in its own window*, *Send <VIEW> to ▸ Monitor N*, pin/unpin, close, close-all (`windows-ui.js:136-196`); in a browser/headless the endpoint answers `native:false` and **nothing is drawn** (`windows-ui.js:1-12, 34`). Wire: `GET/POST /api/control/windows` (`api.py:3118, 3124`, state builder `3087-3117`).
- The aux window renders a *single-widget shell*: `shell.js` detects `?aux=<view>&win=<id>` and refuses to save layouts / change mode / adopt a screen layout (`shell.js:34-47`); its bar carries pin + close (`windows-ui.js:239-260`).

### 2.5 Multi-monitor support — as documented

`docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md` (239 lines) is the record; its status section is authoritative:

- **Worked, measured (16 viewport/DPI scenarios, W1–W6):** no overflow, chrome always inside the viewport, `ui-compact` below 760 px height, widget move/resize clamping at 1024/1920/5120 px, a 10-widget 5120-px board reopening at 1024×640, live DPR change refit, layout persistence with per-layout `screen_key`, 0 client errors — `DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md:35-42`.
- **Defects found (D1–D6):** Engine view painting at 1× on scaled displays, `mpCanvas` inflating ×dpr per fit pass, ribbon backing ≠ CSS box, only the focused view generically refit, **the window had no memory/placement/per-screen restore**, and **no break-apart windows at all** — `…:48-97`; scenario matrix `106-122`.
- **Resolution §72 (landed):** A1–A4 fixed (dpr-aware layers, `mpCanvas` CSS box, ribbon from its own box, `fitView()` walks every visible canvas); P1 items 5/6 landed — `ui.window` geometry + `launcher.pick_window_geometry` (pure, unit-tested) and `screen_key` gaining the screen origin so two identical monitors are two screens — `…:200-219`.
- **§73 update: P2 landed** — auxiliary windows, send-to-monitor, pinning, persisted and restored; the only part still closed is literal **drag-out** (WebView2 cannot start an OS window drag from inside the page), so the command form shipped — `…:225-230`.
- **Still open:** the physical multi-monitor pass by the owner (this host has one display), and the doc's own P3 note that neither the Guide nor the README mentions monitors — `…:170-172, 221-223`.
- Main-window geometry today: `pick_window_geometry` (`launcher.py:196-247`), min 720×480 (`launcher.py:169`), legacy min 1080×680 (`launcher.py:176`), hard min 320×240 (`174`), chrome allowance 56 px (`167`); geometry tracked on shown/moved/resized and written once on close (`launcher.py:250-295`); stored in `ui.window` (`config_store.py:469-472`, clamped `1107-1109`).

---

## 3. Navigation & IA

### 3.1 Menu bar (`ui/menubar.js`, 1111 lines; mounted into `nav#menuBar`, `index.html:99`)

**12 top-level menus** (`menubar.js:542-609`): File 542 · View 561 · Layout 562 · Drawings 563 · Chart 564 · Data 565 · Profiles 580 · Run 594 · Keys 595 · Tools 596 · Update 608 (label dynamic, `updateLabel()` `498`) · Help 609. *(The project's own reconciliation doc lists 11 — it omits Update; `docs/MENU_RECONCILIATION.md:52`.)*

- **View** (`menubar.js:56-79`): "All panels…" (`/`) + one row per rail item with 1–9 accelerators + toggles for Legend panel / Menu bar (B) / Rail (R) / Status bar / Full screen (B… zen) + 2 `planned()` stubs.
- **Layout** (`menubar.js:363-437`): mode switch, layout name, Save now (Ctrl+S in File), Save as…, Duplicate, Delete…, Auto-arrange this tab, Reset to the starter board, Save for this screen, Export current…, Import (paste a bundle)…, then the list of up to 24 layouts with "· this screen"/"saved on WxH@dpr" annotations.
- **Run** (`menubar.js:464-490`): Desktop app (this window) / Headless server on port 8099 / CLI pipeline + Optional block (MT5, NinjaTrader, dev tooling) + Market watch shortcut.
- **Update** (`menubar.js:503-536`): running build, status, download/release notes/skip, check now, open folder, release page, settings.
- Honest stubs: **26** `planned(…)` calls in `menubar.js` (grep count), and **17** `disabled: true` rows of which **16** carry a `reason:` string (grep counts).
- Items whose action would need an engine are greyed with the reason in the tooltip rather than hidden — stated in the help corpus (`help-data.js:110-111`).

### 3.2 Keys menu (the shortcut map, exposed twice)

- Menu group `Keys` (`menubar.js:439-461`): "Shortcut sheet" (?), "Keyboard help topic", then **every row of `OFAPKEYS.list()` grouped by scope header** — dispatched rows run directly, documented-only rows are listed disabled with "acts in <scope>".
- The sheet itself: `#hotkeySheet` overlay (`index.html:138-140`) rendered from `OFAPKEYS.list()` (`menu.js:248-256`), toggled by `?` (`menu.js:299-300`) and by Escape (`keys.js:230-234`).
- Doc driving the menu: "the map the user reads and the keys the app honours are the same list" (`keys.js:1-7`).

### 3.3 Command palette / search (`ui/search.js`, 1021 lines)

- Binding: **Ctrl+K** and **/** (`search.js:501`); the ☰ button also opens it (`menubar.js:69`).
- Two layers in one panel: the app index (views, panels, settings, actions, alert rules, walkthroughs) and a live market layer with feed chips and sparklines (`search.js:1-23`); timing constants `search.js:47-55`; operators are parsed in `ui/search-ops.js` (205 lines, own Node selftest).
- Action rows: **16** `cat: 'Actions'` entries in `searchActions()` (grep; the function starts `search.js:~60`), including Start/Stop/Restart engine, Run the setup assistant, Alpaca setup, instrument look-up, VWAP anchor, pause-all-alerts, clear stored credentials, export detections.
- The ☰ menu panel (`index.html:134-137`, filled by `menu.js`) groups panels by *purpose*: **21 entries in 5 groups** — Order flow 8, Analytics 5, Trading 3, Information 5, Connections 0 static (`menu.js:18-46`, counted), with 6 free-data sources listed separately (`menu.js:49-55`), plus a filter input `#menuFilter` (`index.html:135`).

### 3.4 Hover / right-click explain cards (`ui/hint.js`, 319 lines)

- One shared card, closed action set of **5** (`lookup · engine · instruments · wizard · menu`) — `hint.js:21-28`; every action ends in a real call (`hint.js:181-205`).
- Hover/focus shows, **right-click pins** (`hint.js:211-225`), dismissed by Escape, outside click or any scroll (`hint.js:106-114`); a 260 ms "reachable" grace keeps the card alive so its buttons can be clicked (`hint.js:131-147`); the card reprints the control's shortcut from `aria-keyshortcuts` (`hint.js:157-166`).
- Declared in markup via `data-hint-title/body/actions` — **5 occurrences in `index.html`** (`grep -c`), 11 across the UI in total (`index.html`, `ofx-view.js`, plus the readers/annotators `hint.js`, `keys.js`): the engine pill (`index.html:111-114`), source pill (116-119), data pill (120-123), the Engine symbol chip (`index.html:301-304`) and the find button (305-308).
- Right-click on a row of the Instruments or Market Watch table asks the server what that symbol is and shows the verdict in place (`hint.js:295-304` + `explainSymbol` `253-270`).
- The engine's skip banner paints the same notice with a real button (`hint.js:229-249`).

### 3.5 Breadcrumbs

**None.** `grep -rn breadcrumb` over `ui/*.js|*.html|*.css` returns **0 matches**. Orientation is carried instead by the per-view head — **29** `view-title` + **29** `view-sub` (`index.html`, one pair per view; e.g. `index.html:153-156`) — plus the status bar's `workspace` / `mode` / `tab` fields (`index.html:1185-1187`) and the rail's `.active` state.

---

## 4. Interaction model

### 4.1 Keyboard — the registry (`ui/keys.js`, 344 lines)

- One document-level dispatcher (`keys.js:328-329`); rows are registered by the module that owns the action. **Measured:** **32** `bind()` call sites — **23** in owning modules + **9** in `keys.js` — plus **9** documented local rows via `OFAPKEYS.document()` → **41 rows** in the hotkey sheet.
  - Owning modules (grep `OFAPKEYS.bind({`): `ofx-view.js` 6, `heatmap-pro.js` 5, `atlas.js` 3, `chrome.js` 2, `help.js` 2, `pause.js` 1, `search.js` 1, `menu.js` 1, `menubar.js` 1, `shell.js` 1.
  - `keys.js` core 9 (`keys.js:230-271`): escape · digits 1–9 (switch view by rail order) · Alt+A (Alpaca) · Ctrl+Alt+S (start engine) · Ctrl+Alt+X (stop) · Ctrl+Alt+R (restart) · Ctrl+F (find an instrument / look-up) · Ctrl+PgDn / Ctrl+PgUp (next/previous panel).
  - Documented-only rows (grep counts): drawings Esc / Del-Backspace · menu bar ← → ↑ ↓ / Enter / Tab · palette ↑ ↓ / Enter / Esc / Shift+? · shell F11 / Esc / Alt+1…9 · strips ↑ ↓ / PgUp / PgDn / Home / End (`drawings.js:595`, `menubar.js:1071`, `search.js:503`, `shell.js:1739`, `strips.js:412`).
  - Scope-scoped bindings: Engine (**6**, `ofx-view.js:1172-1184`: `=`, `-`, `]`, `[`, `x`, Ctrl+E) at priority 6 and Heatmap (**5**, `heatmap-pro.js:719-729`: `=`, `-`, `x`, Ctrl+E, `a`) at priority 5; Replay (**3**, `atlas.js:559-574`: Space, `,`, `.`).
- Mechanical rules: chord grammar `[ctrl+][alt+][meta+]key` with aliases (`keys.js:20-22`); typing guard swallows keys in INPUT/TEXTAREA/SELECT/contenteditable unless `inField: true` (exactly one does — `keys.js:14-18, 87-92, 193`); Space on a focused button/link/summary is left to the browser (`keys.js:191-192`); scope collisions resolve by `priority` then registration order (`keys.js:24-26, 100-112`); scope ordering for the sheet is fixed at `keys.js:160`.
- Shortcut annotation: `annotate()` writes `aria-keyshortcuts`, appends "· Shortcut X" to `title` and to `data-hint-title` for **10 selectors** (`#ofapPause`, `#menuBtn`, `#btnStart`, `#btnStop`, `#railTerminal`, `#menubarToggle`, `#mbHide`, `#railToggle`, `#railHide`, `#railReveal`) and the **first 9** rail items (`keys.js:300-324`).
- Non-registry keyboard handlers still exist in **12** places (`grep -rn "addEventListener('keydown'"` excluding selftests — e.g. `menubar.js:1029, 1032`, `shell.js:1684`, `strips.js:379`, `drawings.js:577`, `search.js:486`), i.e. the registry is the documented map but not yet the only listener.

### 4.2 Pause / freeze — global and per-surface

- Global chip `#ofapPause` in the topbar (`index.html:141-142`), toggled by click or **P** (`pause.js:75-87`); one registry stops every registered interval (`pause.js:61-73`); remembered per browser under `ofap.paused` (`pause.js:15, 53`); fires `ofap:paused` and freezes `OFX` + the intent layer (`pause.js:31-37`).
- Per-surface "Pause" buttons: **9** `data-surf` buttons in `index.html` (overview 154, chart 194, orderflow 269, ofx 296, depth 364, tape 377, signals 413, trackers 479, marketwatch `#mwPause` 400) **+ 1 injected** by `scanner.js:87` → **10 surfaces with a button**, matching `docs/MENU_RECONCILIATION.md:132` ("10 surfaces wired").
- Deeper gate: views/timers consult the arbiter before fetching — `OFAPINTENT.held('<view>')` appears at **20 call sites** covering **12 distinct views** (alerts, chart, depth, heatmap, marketwatch, ofx, orderflow, overview, scanner, signals, tape, trackers; `ui.js`, `atlas.js`, `atlas-v2.js`, `heatmap-pro.js`, `ofx-view.js`, `scanner.js`), with a queued "snap current on resume" path (`ofx-view.js:1094`, `ui.js:782` "deferKeyed").
- Replay's own transport acts as its pause (`docs/MENU_RECONCILIATION.md:34`).

### 4.3 Pointer interactions, per surface

| Surface | What exists | Evidence |
|---|---|---|
| Whole shell (terminal mode) | Drag widget by its bar, resize by grip, click-to-focus, drag tabs to reorder | `shell.js:683-740`, `596`, `742` |
| Heatmap | hover crosshair/tooltip, wheel zoom, mousedown drag-select a price×time box, dblclick clears the selection, key equivalents (=,-,x,Ctrl+E,a) | `heatmap-pro.js:571, 587, 592, 598, 618, 621, 719-729` |
| Engine (ofx) | wheel zoom/scroll, mousedown drag to pan, dblclick = fit session, stage click, floating "Snap to present", legend toggle, symbol chip / find panel | `ofx.js:2452, 2470, 2482, 2491`; `ofx-view.js:993-1000, 1011-1023` |
| Chart (lightweight-charts 4.1.3) | library defaults: drag to pan, wheel to zoom, axis drag to scale; app subscribes only to the crosshair (Data box) | `ui.js:755-770` (createChart, `autoSize`, crosshair Normal); `studies.js:264` `subscribeCrosshairMove`; vendor `ui/vendor/lightweight-charts.js` (injected `window.LightweightCharts`) |
| Order Flow / Frames / Tape / Depth / Signals | canvas/text panels; the Order Flow card advertises "drag to pan · scroll to zoom" (`index.html:289`); no dedicated pointer module found for depth/tape/frames beyond the shared strips/sheet behaviour | `grep addEventListener` per module: `ui.js` 2, `watchlist.js` 2, `marketwatch.js` 0, `ticks.js` 0, `scanner.js` 0 |
| Strips (tape/alert/log-like scrollers) | hold-your-place when scrolled away + "+N new", arrow/PgUp/Home/End stepping, clicking a row with `data-time`/`data-price` **locates** the print on the shared cursor | `strips.js:1-16, 379, 412` |
| Drawings | drawing tool on the chart host with its own context menu, keydown chain and input handling — **15** pointer/context listeners | `drawings.js:441, 567, 577, 595` (module 694 lines) |
| Instrument tables | right-click a row → server verdict; Symbols/feed controls | `hint.js:295-304`; `index.html:1009-1034` |
| Views with a dedicated context menu in code | **3** modules only: `hint.js` (any `[data-hint-title]` + the two tables), `drawings.js` (its host). Everything else: no right-click affordance | `grep -rn contextmenu ui/*.js` (excluding selftests) = 5 hits in 3 files |

Canvas/DPI behaviour is owned by one module: `ui/scale.js` — the single "the window changed" authority, refitting every visible canvas and emitting `ofap:relayout` (`scale.js:1-12, 210-212` per the audit's fix note).

---

## 5. Visual design language

### 5.1 Token system

- One token block, `desktop/ui/atlas.css:1-108` (725 lines total). The header states the rule: *every colour in the shell reads from here; nothing outside this block declares a colour* (`atlas.css:1-10`).
- Values are declared as **rgb triples + a solid form** so translucent overlays can be derived: `--of-surface-rgb: 19,27,42; --of-surface: rgb(var(--of-surface-rgb))` (`atlas.css:17`), used as `rgba(var(--of-steel-rgb), .35)` elsewhere (comment `atlas.css:5-6`).
- Measured token counts (grep `^\s*--x:`): **atlas.css 84**, `ui.css` 21, `modules.css` 9, `themes/light.css` 70, `themes/contrast.css` 70, `themes/dark.css` 2, `themes/accents.css` 0 (it re-*assigns* triples) → **256** declaration lines across the CSS.
- Token families present: surfaces (14), lines (7), ink/typography colours (18), accent + tints + radius/shadow (`atlas.css:61-72`), semantics ok/err/warn/amber/gold/cyan/trace/link/violet (`74-102`), type + density (`104-107`).
- Type: `--of-font: "Segoe UI Variable", "Segoe UI", system-ui …` and `--of-font-mono: "Cascadia Mono", "SF Mono", Consolas …` (`atlas.css:105-106`); radii 2 px / 10 px (`69-70`).

### 5.2 Themes, accents, densities

- **Three themes** (`dark` default, `light`, `contrast`) — `ui/theme.js:16`; anchors: `themes/dark.css` (2 tokens + comment), `themes/light.css` (70), `themes/contrast.css` (70; "black ground, white ink, hard borders" `contrast.css:1-6`). The dark values live in the base block itself (`atlas.css:12-108`).
- **Eight accents** (the Windows 8 palette): cobalt, teal, green, lime, amber, orange, magenta, violet — `themes/accents.css:8-15`, plus 2 `--of-on-accent` overrides for the light accents (`accents.css:18-19`); because tints are derived (`rgba(var(--of-accent-rgb),.13)`), one triple moves the whole system (`accents.css:1-7`).
- **Three densities**: `comfortable 32px / compact 26px / dense 22px` bound to one token `--of-row-h` (`themes/density.css:8-10`), consumed by nav items, data rows, log lines and watchlist rows (`density.css:12-16`) with per-density padding/font rules (`18-25`). Also a height-driven `ui-compact` mode below 760 px, owned by `scale.js` (`scale.js:23-28`, `density.css:1-6`).
- Theming is **one attribute on `<html>`**: `data-theme`, `data-accent`, `data-density` (`theme.js:47-54`), applied *before first paint* from a localStorage mirror and then corrected from the config (`index.html:28-36`, `theme.js:1-11, 116-132`).
- Settings exposes exactly these three selects (`index.html:804-816`), with the on-screen note "Every colour in the shell reads from the token block in atlas.css: these three switches swap the tokens, never the layout" (`index.html:818`).

### 5.3 Colour-blind palettes and colour rules

- Defined in `ui/expression.js` (447 lines) as `PALETTES` (`expression.js:168-195`): `theme` (green/red, with the note that it separates for a protanope ΔE 35 and *collapses* for a deuteranope ΔE 9.1 — `expression.js:173`), `deutan` = sky blue/orange (179), `protan` = yellow/sky blue (185), `tritan` = teal/red (191). Each carries its **measured** ΔE under protanopia/deuteranopia/tritanopia, and the file lists the pairs that were measured and **rejected** (teal/magenta, green/purple, cyan/magenta, yellow/purple — `expression.js:145-156`).
- Simulation matrices for the three dichromacies: `expression.js:49-56`.
- Exposed in the UI twice: the Chart view "Palette" select (`index.html:211-213`) and the Engine "palette" select with the note that the pairs are "chosen and MEASURED" (`index.html:319-321`); bar-expression modes (`default | delta | split | heat | wick`) sit beside them (`index.html:207-210`, `315-318`).
- Depth-heat ramps must stay **monotone in luminance** (`config_store.py:327-329`; ramp select `index.html:322-323`); the Engine legend names every colour and control (`index.html:353-359`, `ofx-view.js:257-330`).
- Semantic tokens are explicit (`ok/err/warn/amber/gold/cyan`, `atlas.css:74-101`), and the header says the token pass "changed no pixel" for dark (`atlas.css:7-8`).
- **Contrast ratios of the shipped pairs are not measured here** (the app measures CVD ΔE, not WCAG contrast).

---

## 6. Onboarding & discoverability

### 6.1 Setup wizard (`ui/guide.js`, 2564 lines)

- **Express path: 9 steps** — Welcome (`guide.js:513`), Depth (choice of express/professional, 542), Data source (569), Instruments (633), Alpaca optional (723), Feeds/history/extras (810), Alerts & notifications optional (829), Market context optional (980), Ready (1032). Measured by parsing the `WIZ_STEPS` array.
- **Professional path: +10 steps** (`WIZ_PRO`, `guide.js:2352-2522`): Feed budget, Instruments, Engine internals, Order-flow analytics, Studies runtime, Layout & workspaces, Hotkeys & workflow, Bridges & accounts, Performance & hygiene, "Prove it works" → **19 steps** in the deep path. `wizList()` decides which set is live (`guide.js:509-511`); the header prints "Step i of N · professional|express" (`guide.js:1210`).
- Resume: `ui.wizard_resume_step` in the config (`config_store.py:463`, sanitised `1104-1106`, written `guide.js:1111-1117`); the wizard opens itself on a fresh install when bootstrap lacks `onboarding_done` (`guide.js:1449-1454`).
- Entry points: rail-top **Setup wizard** button with a status dot (`guide.js:2298-2318`), `openWizard()` (`guide.js:1123`), the ☰/palette action row (Start/Stop… "Run the setup assistant"), Alpaca's "Open setup assistant" (`index.html:1005`), a hint card action (`hint.js:194-196`), and every wizard step's "Open X" deep links (`guide.js:496-505`).
- Each step is skippable (`guide.js:1176`), says "what this unlocks / where to go deeper" (`guide.js:496-505`), and the final save merges only the keys the wizard touched (`guide.js:1304-1341`).

### 6.2 The help corpus (`ui/help-data.js`, 2433 lines)

- **7 groups** (`help-data.js:33-48`): Getting started, Panels one by one, Working with the app, Connections and setup, Data files and storage, Under the hood, Fixes and support.
- **73 topics** (parsed count of `id: '…', group: '…'` entries): panels **29** (one per view — the coverage contract, `help-data.js:2391-2426`), workflow **13** (`work.terminal`, `work.windows`, `work.layouts`, `work.menubar`, `work.palette`, `work.keys`, `work.drawings`, `work.cursor`, `work.pause`, `work.appearance`, `work.display`, `work.audio`, `work.exports`), fix **8**, connect **7**, under **6**, start **5**, data **5**.
- `VIEWS` map (`help-data.js:2394-2426`) = **31 keys** (29 views + `guide`/`help` aliases) and is enforced by a test: "a view without a help topic fails the suite" (`help-data.js:27-28`, `RESUME.md:15`).
- Topic shape includes `blocks`, `actions` (in-app buttons), `links`, `related`, `shots` — screenshots are referenced **10** times and **9** PNGs exist in `desktop/ui/help/`.
- Help Centre UI (`ui/help.js`, 1244 lines): two interfaces **simple / advanced** (`help.js:10-11`, toggle at `help.js:992-1026`), **3 dock positions** taskbar / floating / off (`help.js:1007-1057`), preferences in the config `help` block (`config_store.py:489-494`), bindings **F1** and **Ctrl+Shift+H** (`help.js:1173-1175`), status-bar dock + floating launcher + About card (`index.html:1176-1182` comment; `help.js:1033-1056`).
- System check: `desktop/help.py` produces findings from **23** `_finding(...)` call sites covering **22** distinct check ids (config.file, engine.*, feed.quiet, source.*, mt5.*, alpaca.*, alerts.no_channel, storage.*, log.errors, security.*) — grep count.

### 6.3 Tooltips & shortcut annotation

- **74** `title=` attributes in `index.html` (native tooltips); `ui/guide.js` re-applies a **109-entry** `TIPS` map to controls the app creates later (`guide.js:22-46`, count parsed), wired so a re-render re-tips the DOM (`guide.js:184`, `1435-1443`).
- Shortcut annotation: `keys.js:300-324` (see §4.1) — tooltip, `aria-keyshortcuts`, and the hover card's "⌨ Shortcut X" line (`hint.js:157-166`).

### 6.4 Demo / no-data paths

- The top bar's data pill states live / warming / demo in the UI itself (`index.html:120-123`).
- Server-declared per-panel state is read by `liveState(key)` returning `'live' | 'warming' | 'demo' | 'stale' | ''` (`ui.js:271-273`); the chart stamps demo bars with `source: 'demo'` rather than a clock (`ui.js:804-810`) so the freshness chip says "demo" instead of "live · 0 s".
- Demo is surfaced rather than hidden: the freshness chip per view-head (a module dedicated to age, `freshness.js`, loaded at `index.html:1127` and documented in the load-order comment `1129-1130`), and the Engine/legacy panels label their fallbacks (`ui.js:805`).

---

## 7. Persistence & settings

### 7.1 One config file is the record

`desktop/config_store.py` (1171 lines) owns `config.json` under the user config dir (`config_path()` `94`, `config_dir()` `81`). `default_config()` (`242-495`) declares these blocks (counted from the literal):

`version` · `data_source` · `instruments[]` (with per-instrument `patterns` thresholds) · `telegram` · `notify` (ntfy + email) · `context` · `dashboard` · `platforms` (DTC bridge) · `studies` (`active`, `custom`, `data_box`) · **`workspaces`** (`316`) · **`layouts`** (`320`) · `drawings` · `markers` · `ofx` · `expression` (per-surface bar mode + palette) · `risk` · `audio` · `atlas` (the largest block: heatmap, tape/detectors, cvd, market_profile, imbalance, vwap, footprint, dots, correlation, detector, scanner, intent, history, telegram routing, alert_rules — `351-396`) · `alpaca` · `storage` · **`ui`** · **`help`**.

Nothing persists from the page alone: the browser holds *mirrors* only — `ofap.appearance` (`theme.js:15`), `ofap.paused` (`pause.js:15`), `ofap.chrome` (`chrome.js:13`), `ofap.ofx.legend.open` (`ofx-view.js:327`) — and the appearance mirror exists purely to kill the first-paint flash (`index.html:29-35`, `theme.js:1-11`).

### 7.2 `ui.*` — what the front end remembers (`config_store.py:456-483`)

`banner_dismissed_alpaca` (461) · `wizard_resume_step` (463) · `theme` (466) · `accent` (467) · `density` (468) · `window {width,height,x,y,maximised}` (472) · `chart {range,markers,vp}` (476) · `logs {auto,level}` (477) · `windows[]` — the open auxiliary windows (478-482). Clamps/validators: `1094-1130` (theme/accent/density whitelists, window clamp `1107-1109`, windows `1110-1111`, chart range 0…2,592,000 s `1115-1124`, log level whitelist `1125-1130`).

### 7.3 Layouts, workspaces, windows

Per §2.3/§2.4: `layouts.items` capped at 24 layouts × 12 tabs × 24 widgets, each widget `{view,x,y,w,h,link,settings{≤24 keys}}` (`config_store.py:662-752`); `ui.windows` capped at **8** records `{id,view,x,y,w,h,on_top}` (`config_store.py:49, 609-660`); `workspaces{}` is a name→data map (`config_store.py:847-869`), 32-char names (`api.py:2937`).
HTTP surface for all of it: `GET/POST /api/control/config` (bootstrap `api.py:41`), `/layouts` (`2964`, `2972` — one write per call: mode · save · import · duplicate · rename · delete · activate · export), `/workspaces` (`2923`, `2930`), `/windows` (`3118`, `3124`).
API size for context: **104** route decorators in `desktop/api.py` (46 `@router.get`, 58 `@router.post`), all under `APIRouter(prefix="/api/control")` (`api.py:34`).

### 7.4 Per-surface holds & write arbitration

`ui/intent.js` (313 lines) arbitrates: views ask `held('<view>')` before fetching (12 views, 20 call sites — §4.2), and user-driven writes are queued through `queueWrite` so a burst of setting flips is one POST (`shell.js:1253`, `theme.js:94`). The freeze itself is the global chip (§4.2) rather than a per-panel toggle for every view.

---

## 8. Known UX gaps already recorded

### 8.1 `docs/MENU_RECONCILIATION.md` — findings F1–F7 (`:100-116`)

| Id | Gap (as recorded) |
|---|---|
| **F1** | **Trackers advertises what it does not fetch** — the view's own menu text says "correlation, dots, cross-venue reads"; the fetches are alert-rules/history/imbalance/tape only. Five live routes have no caller (`dots`, `correlation`, `crossvenue`, `intent`, `trades/recent`). "Either wire the tables or correct the claims — never neither." (`:100-103`) |
| **F2** | **Three server-made CSV exports sit dark** — `export/tape/{symbol}.csv`, `export/heatmap/{symbol}.csv`, `export/alerts.csv` have no UI caller; Tools has no export entry (`:104-106`) |
| **F3** | **`POST /api/control/storage/prune` unexposed** while the Logs/Settings storage block renders usage; the DB was ~776 MB at §86b (`:107-108`) |
| **F4** | **Profiles vs Workspaces: two overlapping stores, one built** — reconcile the Profiles menu against the working workspace store (`:109-110`) |
| **F5** | **No quit/exit path in the API** — decide window-close only or add a quit route + menu item (`:111-112`) |
| **F6** | **§89's honest remainder** — CVD/heatmap/profile/frames pause buttons + L2 ladder cell ticks; the paint paths must consult the arbiter *first*, "buttons before wiring would lie" (`:113-114`) |
| **F7** | **Serve-time verification habit** — byte-checks on served markup caught two glyph bugs the screenshots missed (`:115-116`) |

Supporting sections: the rail table (28 rows incl. "Setup wizard" as a rail entry, per-view updater/pause/keys, `:15-48`); "26 `planned(...)` stubs classified" and "3 disabled entries carry reasons" (`:60-75`); the recommended upgrade queue (`:118-128`).

### 8.2 Unexposed-route table (`MENU_RECONCILIATION.md:77-96`) — 13 routes with no UI caller

`GET /api/atlas/dots/{symbol}` (F1) · `GET /api/atlas/correlation` (F1) · `GET /api/atlas/crossvenue/{symbol}` (F1) · `GET /api/atlas/intent/{symbol}` (wire) · `GET /api/atlas/trades/recent/{symbol}` (wire) · `GET /api/atlas/export/tape/{symbol}.csv` (F2) · `GET /api/atlas/export/heatmap/{symbol}.csv` (F2) · `GET /api/atlas/export/alerts.csv` (F2) · `GET /api/atlas/status`, `/capabilities` (Systems-board candidate) · `GET /api/control/datasources` (wizard/Settings candidate) · `GET /api/control/trades` (Performance candidate) · `GET/POST /api/control/backfill` (verify caller) · `POST /api/control/storage/prune` (F3). *(CSV routes verified HTTP 200 with an empty body when the store holds nothing, `:95-96`.)*

### 8.3 `docs/RESUME.md` §95 owed items (`:9-11`)

- `dist/` · zip · SBOM · installer **NOT rebuilt** — the payload changed heavily; **payload parity + installer journey** are the next packaging pass.
- **Nothing committed** — HEAD `110c568`, 108 dirty entries.
- The **toggle-tooltip cosmetic**.
- The **BTCUSDm-on-MetaQuotes-demo** note (rename the mapping or let crypto ride the exchange).
- **Update/backup defaults conservative by design.**
- Gates at save: pytest 1241 passed / 2 skipped; AUDIT CLEAN (**94 JS modules**); ruff clean; 28 node selftests / 0 failures (`RESUME.md:7`).

### 8.4 Other recorded gaps that touch UX

- Display audit's still-open items (physical multi-monitor pass; the "Multiple monitors" documentation note; already-landed §72/§73 fixes) — `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md:170-172, 221-230`.
- §93's chrome work already shipped: per-bar hide/show with persistent topbar toggles, the labelled menu-bar toggle, the rail's visible return arrow, digit-row accelerators in the View menu — `MENU_RECONCILIATION.md:130-137`, `docs/RESUME.md:5`.
- The Known-broken-from-birth note that a *palette/menu* list once drifted is now structurally closed (the sheet renders from `OFAPKEYS.list()` — `keys.js:1-7`), which is why the Keys menu is the cheapest future place to add bindings.

---

## Appendix — measurement index (how each number in this file was obtained)

| Number | Command / method |
|---|---|
| 29 rail buttons, 29 view sections, 58 cards, 39 KPIs, 74 `title=`, 5 `data-hint-title`, 9 `surf-pause`, 11 `<link>` / 50 `<script` opens (49 `src` + 1 inline boot script) | `grep -c` / regex over `desktop/ui/index.html` |
| Cards per view and their line numbers | Python: split `index.html` on `<section class="view" data-view=…`, regex `<div class="card"[ >]`, then read `card-title` |
| 73 help topics / 7 groups / 29 panel topics / 31 `VIEWS` keys / 10 `shots` | Python regex over `ui/help-data.js` |
| 9 `WIZ_STEPS` + 10 `WIZ_PRO` | Python: locate the array literals in `ui/guide.js`, count `    {  title:` entries |
| 32 `bind()` call sites, 9 documented rows | `grep -rn "OFAPKEYS.bind({"` and `OFAPKEYS.document([` over `ui/*.js` (selftests excluded) |
| 12 views / 20 `held()` sites | `grep -rno "held('[a-z]*')"` |
| 104 routes, 46 GET / 58 POST | `grep -c "@router\."` and `grep -o "@router\.\(get\|post\)"` on `desktop/api.py` |
| 256 CSS custom-property declarations | `grep -ho '^\s*--[a-z0-9-]*:'` over `ui/*.css` + `ui/themes/*.css` |
| 26 `planned()`, 17 `disabled: true`, 16 `reason:` | `grep -c` on `ui/menubar.js` |
| 109 TIPS entries | Python regex on the `TIPS` object literal in `ui/guide.js` |
| Layout/window caps (24/12/24, 12×8, 8) | `grep -n` on `desktop/config_store.py:45-60` |
| Line / file counts | `wc -l`, `find`, `ls` |

**Not measured (stated as such):** live rendered behaviour of any view (no app was launched); actual runtime card/rail counts after all injections; WCAG contrast ratios of any palette; screenshot-level appearance; the physical multi-monitor pass (the repo's own audit flags this as owner-only).
