# AI agent brief — ModFlow OrderFlow Analysis Suite, next build

You are picking up a **working, tested, standalone Windows order-flow suite**. This document is
written to be executed, not admired: it states what exists, what must not break, the design language
to build to, and the workstreams with acceptance tests. Read §1 and §2 before touching anything.

Two inputs informed the design section. One: the brief the owner gave me, which asked what makes an
interactive order-flow chart good — highlightable elements, scrolling information elements, chart
colour and bar/candle treatment, linked panels (his words: "elements of a good interactive chart
design relevant specifically to order flow analysis software"). Two: a visual reference he supplied —
a *Material Design for Windows 8/8.1* skin (flat tiles, accent colour, Metro typography, bold colour
blocks, sharp geometry). Note honestly: the Google search page he linked is a JavaScript-rendered
result page and could not be read reliably by a text fetch, so the interaction canon below is drawn
from the order-flow tools this build already studied (the reference layout, the reference platform, the DTC platform, the reference platform, and
the suite's indicator contract's study contract) plus what is already implemented. Where a claim is practice rather than
specification, it is phrased as practice.

---

## 0. How to use this document

- Work top to bottom through §4. Each workstream is self-contained, but the **order matters** for
  A → B → C because later workstreams consume the interaction primitives built earlier.
- Every workstream ends with a **Gate** — a command whose output is the evidence. Do not move on
  with a red gate. Do not report success without pasting the gate output.
- Nothing is committed to git. The owner's standing rule. Leave the tree dirty and say so.
- If a genuinely blocking decision appears, stop and state it in one paragraph. Do not guess at
  credentials, do not invent data, do not "fix" a test to make it pass.

---

## 1. What exists (do not rebuild any of this)

**Runtime.** Python 3.12 `.venv`, FastAPI backend, vanilla-JS front end (no build step), pywebview
desktop shell launched by `orderflow_system.desktop` (also `pythonw -m orderflow_system.desktop` from
the owner's shortcut), bound to `127.0.0.1:8080`. A frozen build exists at
`dist/OrderFlowAnalysisPro/OrderFlowAnalysisPro.exe` (PyInstaller `onedir`, ~80 MB) produced by
`scripts/build_exe.py`; `scripts/_exe_entry.py` is its entry point.

**Backend map.**

| Area | File | Notes |
|---|---|---|
| REST for the desktop shell | `orderflow_system/desktop/api.py` | bootstrap, engine start/stop/restart, config, logs, workspaces, sources, `client-error`, `export/save` |
| Feature hub | `orderflow_system/atlas/hub.py` | per-symbol feature objects, `_dispatch()` routes detections to the alert engine |
| Depth heatmap | `orderflow_system/atlas/depthmap.py` | `DepthHeatmap`: columns × levels, walls, pull/stack, **wall streaks + `wall_age` detection**, `wall_durations()` |
| Alerts | `orderflow_system/atlas/alerts.py` | dataclass rules, `evaluate()`, **level scope `at_price`/`at_tol`**, CSV + webhook payloads |
| Replay | `orderflow_system/atlas/replay.py` | `MarketReplay.load(symbol, start_ms, end_ms)`, play/pause/seek/speed |
| Others | `atlas/{cvd,profiles,frames,imbalance,dots,crossvenue,correlation,intent,scanner,history,context,notify}.py` | all behind `/api/atlas/*` |
| Config | `desktop/config_store.py` + `config/settings.py` | whitelisted writes, `%APPDATA%\OrderFlowAnalysisPro\config.json`, clamps on load |

**Front-end map.** `desktop/ui/index.html` (shell: rail, topbar, 24 views, status bar), `atlas.css`
(single stylesheet), `ui.js` (boot, view switching, panels), `atlas.js` (heatmap/CVD/profile/frames
draw + controls), `atlas-v2.js` (v2 panels, alert routing table, lazy module loader), `guide.js`
(setup wizard + help + panel map), `menu.js` (purpose-grouped menu, workspaces, hotkeys), `scale.js`
(**the** window-change authority), `heatmap-pro.js` (heatmap interaction layer), `ofx.js` +
`ofx-view.js` (order-flow rendering engine), `study-api.js` + `studies.js` + `indicators/*` (study
runtime), `pause.js`, `platforms.js`, `market-pressure.js`.

**Interaction primitives already built — reuse, do not reinvent.**

- `scale.js` exposes `window.OFAPScale`: `register(name, fn)` to join the re-fit pass, debounced
  `ofap:relayout` event, zero-size guard for minimised windows, `ui-compact` class under 760 px
  height. Every canvas must (a) size its backing store to `clientWidth × clientHeight × dpr` and
  (b) be reachable from the active view so the generic fit finds it.
- `heatmap-pro.js` establishes the interaction pattern to copy everywhere: **zoom drives the panel's
  own control** (not a private re-fetch), **selection is a first-class object** (box → stats →
  isolate → export), **a floating readout shows what the panel does not**, and **actions report on
  their own line** (`[data-hm-pro-msg]`) so a repainting readout cannot erase them.
- `guide.js` wizard: two depths (Express = 12 steps, Professional = 22, `wizList()` is the single
  source of truth for navigation; `collect()` sites are bounds-safe; deep links go through `wizGo`).
- Alert rules carry `params.at_price` + `params.at_tol` (a rule bound to a level) and
  `params.min_age_s` (a rule bound to how long a level holds).

**Test and audit surface (your gates).**

```
.venv/Scripts/python.exe -m pytest orderflow_system -q      # 313 passed, 2 skipped baseline
.venv/Scripts/python.exe scripts/audit_ui_refs.py           # ids, API routes, JS wiring
node orderflow_system/desktop/ui/ofx.selftest.js             # engine maths (94 ok today)
node --check orderflow_system/desktop/ui/<file>.js          # every JS file you touch
.venv/Scripts/python.exe scripts/regen_config_golden.py     # only when config defaults change
```

Known flake: `test_platforms.py::test_probe_handshake_against_a_spec_conformant_server` is a
socket-timing test; it failed once in three full-suite runs on 2026-09-15 and passed alone and in
its own file — re-run it alone before believing it.

**Runtime diagnostics already wired.** The client reports uncaught errors and unhandled rejections
with file:line and stack to `POST /api/control/client-error`, which writes them to
`%APPDATA%\OrderFlowAnalysisPro\orderflow.log`. **Read that log before theorising about a UI bug.**

---

## 2. Non-negotiables

1. **Error-free means proven, not probable.** For every change: `node --check` the JS, run the full
   pytest suite, run the audit, and exercise the feature in a real browser session against a running
   instance. Paste the evidence. If you cannot exercise it, say which part is unproven.
2. **Never edit silently.** Long edits go through a script that asserts each anchor matches exactly
   once and aborts without writing otherwise. This project has been bitten by partial edits more
   than once (an apostrophe, a mid-class insertion, a brace moved by a "harmless" replace).
3. **Do not break these contracts.** The metrics/units in `docs/` and the golden config; the
   `/api/atlas/*` payload field names (`values`, `prices`, `buckets`, `traded`, `events`, `walls`,
   `bucket_ms`); the study module contract (a module returning a plain number is valid); the wizard's
   `wizList()` navigation; `OFAPScale` registration for anything drawn on a canvas.
4. **Secrets.** Never open, print, store or transmit `.env`, `auth.json`, `keys.db`, `Username.txt`
   or `Accounts*.config`. Vendor passwords are never collected; key entry happens only inside the
   app's own Connections panel. No secrets in comments, tests, logs or exports.
5. **Free data only.** Public exchange feeds and free tiers. No paid market-data assumptions.
6. **Original work.** Extrapolate form and function from other platforms; never copy code, assets,
   provider lists or copy text from them.
7. **Hermes is out of this build.** `grep -ri hermes` over source and the frozen binary must stay at
   zero matches.
8. **Keep it a working app at every checkpoint** — the owner runs it from his desktop shortcut while
   you work.

---

## 3. Design language to build to

### 3.1 Windows-native, Material/Metro-flavoured (the owner's visual reference)

The reference is Material Design for Windows 8/8.1: flat, tile-based, accent-driven, typographically
bold, geometrically sharp. I have looked at the image he supplied, and the specific traits to copy
are these — they are more particular than the general idiom:

- **Square geometry.** Corners are effectively 0; panels are flat rectangles separated by whitespace,
  not cards with rounded corners and borders.
- **Solid accent blocks with white glyphs.** The four tiles in the reference (red, teal, cobalt,
  amber) are a flat fill and a centred white icon. That is exactly a KPI/stat tile here — a large
  number, one accent block, nothing else.
- **One accent per window, in the chrome itself.** Each window's title bar is fully accent-coloured
  with white glyphs. Translate as: each panel's header bar carries that panel's accent, which doubles
  as its identity inside a workspace.
- **Colour as a marker in-panel, not as a background.** The nav uses small coloured dots; the combo
  uses a 2 px accent underline. State should read as dots, rails and underlines — full-bleed colour
  is reserved for headers and tiles, or a dense trading screen turns into a fairground.
- **Almost no elevation.** One soft shadow level for genuinely floating surfaces (the menu, the
  wizard). Everything else sits flat.
- **A light and a dark shell off the same tokens.** The reference proves both: the light shell is airy
  white on a pale background, the dark shell is slate with a teal accent and a flat blue scrollbar.
- **Quiet, light typography** with large light titles and generous spacing; in this app that means
  light-weight titles, tabular numerals in data, and panel gutters on a 4/8/12 px step.

Translated to this app as a **theme layer**, not a rewrite:

- **Tokens first.** Define one token block in `atlas.css` (`--of-bg`, `--of-surface`, `--of-accent`,
  `--of-accent-soft`, `--of-ink`, `--of-ink-dim`, `--of-ok`, `--of-warn`, `--of-err`, `--of-grid`,
  `--of-radius: 2px`, `--of-shadow`, `--of-font: "Segoe UI Variable", "Segoe UI", system-ui`).
  Every colour in the shell must come from a token. Screenshot-proof: grep must find no raw hex
  outside the token block.
- **Tiles.** KPI/stat blocks become Metro tiles: flat fill, 2 px radius, no gradient, a single accent
  block behind the number, and a 6 px accent rail on the leading edge of a selected tile.
- **Accent system.** One accent colour drives selection, focus rings, active rail item and the
  primary button. Provide 8 accents (the Windows 8 palette: cobalt, teal, green, lime, amber, orange,
  magenta, violet) plus light/dark shells and a high-contrast mode.
- **Typography.** Segoe UI Variable; numbers in tabular figures (`font-variant-numeric: tabular-nums`)
  so digits never shift while the tape runs — this is a correctness requirement for a running price.
- **Density.** Three densities (comfortable / compact / dense) bound to a token `--of-row-h`, so the
  same panel works on a laptop and a trading desk; `scale.js` already flips `ui-compact` on height.
- **Windows shell integration.** Taskbar progress while the engine starts, jump-list entries for
  workspaces, a proper icon (`scripts/make_icon.py` exists and is unused), remembered window
  geometry and monitor, per-monitor DPI awareness, and an installer (NSIS or Inno) that writes to
  Program Files, registers an uninstaller, and never requires admin for the portable build.

### 3.2 The order-flow interaction canon (what an interactive order-flow chart must do)

This is the substance of the owner's question. Each item is a requirement, with the primitive that
already exists to build on:

1. **Everything is linked to one price and one time cursor.** Hovering a level in the heatmap must
   highlight that price across profile, CVD, tape, depth, imbalance and the footprint engine, and pin
   a shared time cursor across every time-series panel. *(Build on: the same coordinate maths in
   `ofx.js`; the heatmap overlay's `cellAt()`.)*
2. **Everything selectable is measurable.** A drag over bars, a level, a time range or a set of
   markers yields a statistics strip (volume, delta, resting depth change, VWAP of the selection,
   count and largest trade) plus export. *(Build on: `heatmap-pro.js` selection → stats → isolate →
   export.)*
3. **Highlighting must survive repaints.** Highlights, selections and markers are state, not pixels:
   they live in a per-panel state object and are re-applied on every draw, including after a resize
   or a symbol switch.
4. **Scrolling information elements.** A market has three streams that scroll on their own clock:
   the tape (prints), the event stream (walls pulled/stacked, sweeps, stop runs, absorption) and the
   alert stream. Each gets a compact scrolling strip that never steals layout: max-height, fade at
   the edges, pause-on-hover, click-to-locate (which seeks the linked panels to that print/event),
   and a keyboard way to step through them.
5. **Bars and candles must be able to express order flow, not just price.** Required modes:
   delta-coloured candles (body tint by bar delta, outline by price direction), split candle (up/down
   volume drawn inside the range), heat-gradient mode (body coloured on a diverging palette by
   delta/volume), wick-only + footprint mode, and a **colour-blind-safe palette set** (deuteranopia,
   protanopia, tritanopia) selectable independently of the theme. Colour ramps for the heatmap must
   be perceptually uniform and never rely on red/green alone to carry a sign (pair colour with a
   texture, a bar or a sign glyph).
6. **The heatmap must answer duration questions, not only size.** Size, delta-per-bucket, and how
   long a level has held are three different questions; the third now exists as `wall_age` and must
   be visible (a held-time column, a wall-age tint, a "held ≥ N min" alert).
7. **Keyboard-first.** Every action reachable without a mouse, with a single shortcut map and scopes:
   palette, freeze, view switching, zoom, selection clear, replay seek, export, alert-from-cursor.
   Bindings must be discoverable in-app and never fire inside a text field.
8. **Declare the data's freshness, always.** Every panel shows the age of what it is displaying
   (depth 5 s / quote 60 s windows; `age_known: false` when the clock is unknown) and the panel must
   visibly stale out rather than silently freeze.
9. **Replay is the same UI.** Replay must drive the identical panels through the identical code path
   (no separate "replay view" rendering), so anything learned live is learnable in replay and vice
   versa.
10. **Nothing may degrade silently.** A panel without data says why (feed not wired, engine stopped,
    window has no recorded history) in the panel, in the words of the actual condition.

---

## 4. Workstreams

### A — Theme and token layer (Windows/Material direction)

**Deliverables**
1. Token block + `themes/` CSS files (dark shell, light shell, high contrast, 8 accents) selected by a
   `theme` config key and a switcher in Settings; theme applied before first paint (no flash).
2. Segoe UI Variable typography with tabular numerals everywhere a number can change while running.
3. Metro tile treatment for all KPI/stat blocks; accent rail for selection state.
4. Density selector bound to `--of-row-h`; the three densities must survive every view.
5. Icon and window chrome: `scripts/make_icon.py` wired into `build_exe.py`, remembered window
   geometry/monitor in config, taskbar progress during engine start.

**Gate**
```
# no raw colours outside the token block
grep -nE '#[0-9a-fA-F]{3,8}\b' orderflow_system/desktop/ui/atlas.css | grep -v '^.*--of-'   # expect 0
node --check orderflow_system/desktop/ui/*.js ; pytest orderflow_system -q                   # 297/2
# live: theme switch x4, density x3, light/dark, no layout breakage at 1024x640 and 2560x1440
```

### B — Linked cursor and shared highlight (the interaction spine)

**Deliverables**
1. One module (`cursor-link.js`) owning `{price, timeMs, source, selection}`; every panel publishes
   hover/selection and subscribes to the same store; no panel listens to another panel directly.
2. Price highlight propagates to profile, CVD, tape, depth, imbalance and the footprint engine; it
   survives repaint, symbol switch and window resize.
3. Crosshair with a price/time badge in every time-series panel, matching the engine's HUD style.

**Gate:** live — hover a level in the heatmap and observe the highlight in four other panels at once;
resize; confirm the highlight is still there and still at the same price.

### C — Scrolling information strips (tape, events, alerts)

**Deliverables:** three strips with the §3.2-4 behaviour (pause-on-hover, edge fade, click-to-locate,
keyboard stepping), each able to scroll back through its own history, each bounded in height, all
three reflowing correctly at every window size.

**Gate:** live — generate prints/events, pause on hover, click a print and confirm the linked panels
seek to it; confirm no layout shift when a new print arrives.

### D — Bar/candle expression modes and accessible palettes

**Deliverables:** the five modes in §3.2-5, per-chart persistence, palette set independent of theme,
colour-blind-safe ramps, and a legend that names the encoding actually in use ("body = bar delta,
outline = direction").

**Gate:** live — switch each mode on a running instrument (engine view and chart view), plus a
colour-blind palette, and confirm the legend text matches the drawing.

### E — Heatmap: duration columns, wall-age surfacing, selection everywhere

**Deliverables:** a held-time column in the readout and the walls table; wall-age tint option;
`wall_durations()` surfaced in the UI; the existing selection/isolate/export extended to walls and
markers (not only cells); the 74 px / 22 px plot insets promoted to one shared constant used by both
the map and the overlay.

**Gate:** live — a level that holds ≥ 2 min shows its age; an alert created from that level fires at
that level only (create it, wait for `wall_age` in `/api/atlas/alerts`, then delete the rule).

### F — Alerts: manage, scope, and read like sentences

**Deliverables:** rule editor (kind, threshold, level scope, hold time, channels, cooldown) in the
alerts UI; every rule rendered with its scope in words; a "created from heatmap" filter; the alert
log showing symbol, level, size and why it fired.

**Gate:** live — edit a rule's threshold and scope, fire it, read it in the log, delete it; the log
line must name the level for a level-scoped rule.

### G — Replay parity

**Deliverables:** one rendering path for live and replay; replay honours the current theme, cursor
link, strips, modes and highlights; a "send region to replay" action from any selection; documented
history requirements (a window with no recorded ticks says so).

**Gate:** live — replay a window with the same panels and interactions as live; assert the panels
render from replay data through the same functions (no second renderer in the codebase).

### H — Windows packaging, installer, and first-run

**Deliverables:** `onedir` build with icon, version resource and no console window; NSIS/Inno
installer writing to Program Files with a per-user portable variant; uninstaller; jump-list and
file-association-free install (this app opens no documents); first-run experience = the existing
wizard (Express/Professional) with the theme applied.

**Gate:**
```
.venv/Scripts/python.exe scripts/build_exe.py
# launch the frozen exe on a clean port; bootstrap 200; engine streaming; theme applied;
# grep -ri hermes <frozen dir> == 0 matches
```

---

### I — Expression details carried over from the owner's design research

The pasted design research (a search-page transcription in `convo.txt`) overlaps heavily with what
this build already does — split-cell footprint with weight-mapped text, diagonal cyan/magenta
imbalance, POC glow, thermal depth heatmap with λ decay, synchronised crosshair HUD, sweep bubbles
sized `r = c·∛(volume)`, independent X/Y scaling, historical-mode auto-anchor with a snap badge, the
volume/delta/CVD ribbon, the 45 px text threshold handing off to profiles, and the noise filter. What
it names that this build does **not** yet do:

1. **Stacked-imbalance zones.** Three or more adjacent levels sharing an imbalance side must project
   a semi-translucent band across the canvas matrix, not just per-cell accents. (Cell-level accent
   exists; the zone does not.) Acceptance: on live data, a stacked run draws one band spanning its
   levels; the band survives zoom, resize and symbol change; a legend entry names it.
2. **The crosshair trace to the ladder.** The reference line from the cursor's price must extend into
   the live order-book ladder (depth panel), so the eye can follow price from a historical cell to
   current resting size without re-finding it. Acceptance: hover a footprint cell → the depth ladder
   highlights the same price and draws the connecting line; leaving the canvas clears both.
3. **A visible noise filter.** The minimum-size filter is currently a parameter; it must be a control
   (slider in the chart toolbar, value shown in contracts) that re-filters live without a reload.
   Acceptance: dragging it immediately changes which trades/events are drawn, and the readout says
   how many were hidden.
4. **A second, monotonic heat ramp.** Offer the "slate → orange → white-hot gold" ramp alongside the
   current blue→cyan→green→yellow→red one, selectable per panel and persisted. Pair it with the
   research's design rule, made explicit in this codebase: *desaturate the baseline* (candles, bars,
   grid) so saturated colour is reserved for signals — an accent is only an accent if it is scarce.
   Acceptance: both ramps selectable and persisted; a screenshot shows the desaturated baseline with
   only signals saturated; no sign of a value is carried by hue alone (pair with weight, glyph or bar).
5. **Trackpad pinch on the price axis.** Shift+wheel already aggregates ticks; the two-finger pinch
   gesture must do the same, so a laptop has parity with a mouse. Acceptance: pinch aggregates and
   de-aggregates smoothly; text stays suppressed below the 45 px threshold.



---

## 5. Sequence and checkpoints

1. **A** (theme/tokens) — checkpoint: a screenshot at 1024×640 and 2560×1440, light and dark.
2. **B** (cursor link) then **C** (strips) — checkpoint: one recording of a linked hover driving four
   panels and a click-to-locate from the tape.
3. **D** (modes/palettes) — checkpoint: each mode on live data, plus one colour-blind palette.
4. **E** (heatmap duration) and **F** (alert editing) — checkpoint: a level-scoped alert fired by
   `wall_age`, read in the log, then deleted.
5. **G** (replay parity) — checkpoint: replay rendering through the same functions (show the call
   path, not just the screen).
6. **H** (packaging) — checkpoint: frozen build + installer, launched from a clean path.

At each checkpoint: full pytest, audit, `node --check` on changed JS, and the browser evidence. If a
gate is red, stop at that workstream — do not stack work on a broken foundation.

---

## 6. Known gaps to fix on the way (inherited, honest)

- 4K at Windows 150 % scaling is untested; fractional DPI costs a full re-raster on resize.
- The heatmap overlay duplicates the map's plot insets (74/22) — promote to one constant (workstream
  E) and make both read it.
- The engine is Canvas2D by design (4.5 ms full repaint, 3 layers, 200 bars × ~128 levels). Revisit
  only for > 2 k simultaneous cells or forced 4K/144 Hz; if you do, keep the coordinate matrix.
- Depth history is bounded; a replay window older than the buffer honestly reports "nothing recorded".
- Sweeps need bars and prints from the same feed; when they cannot be drawn the panel says why.
- `heatmap-pro.js` markers are session-only; persisting them per symbol is unclaimed work.

---

## 7. What not to do

- Do not add a framework, a bundler or a build step to the front end. The app ships as files.
- Do not rename payload fields or config keys; add, don't rename, and keep the golden config green.
- Do not introduce a second rendering path for replay.
- Do not let a panel draw without registering with `OFAPScale`.
- Do not hide a failure behind a spinner, a zero or a plausible-looking default. Say what is wrong.
- Do not commit.

---

## 8. Handoff checklist for the agent

```
[ ] read §1 and §2; confirm the baseline suite is 297 passed / 2 skipped before touching anything
[ ] work workstream by workstream; paste gate output at each checkpoint
[ ] leave the tree dirty; report exactly which files changed
[ ] report unproven items explicitly, in the same message as the proven ones
[ ] leave the app runnable from the owner's desktop shortcut at every stop point
```
