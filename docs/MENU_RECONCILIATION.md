# Menu reconciliation — the rail and the top menu bar vs. what the program can actually do

**Method (so this document can be re-run, not trusted):** every claim below comes from reading the
shipped code, not memory. The rail inventory is parsed from `ui/index.html` (plus `scanner.js`,
which injects its own view); the menu inventory from `ui/menubar.js` (`menus()`, `planned(...)`,
`disabled` rows); the exposure diff reads every route in `orderflow_system/desktop/api.py`,
`atlas/api.py` and `edgar.py`, normalises template literals in every `ui/*.js`, and lists routes
with **no UI caller**. Re-run by re-extracting the same way.
**Date of extraction: 2026-09-18 (session §93). State: nothing committed; HEAD `110c568`.**

---

## 1. The left rail — every view, and what it can already do

| # | View | Updater | Pause button | Keys/hints | Notes |
|---|------|---------|--------------|-----------|-------|
| 1 | Overview | status tick + WS | ✔ (§89) | 1 | Systems card, KPIs tick (§90) |
| 2 | Chart | WS + atlas | ✔ | 2 | per-view Chart menu = its variables |
| 3 | Heatmap | WS/depth-driven | ✖ | 3 | canvas repaint path does not consult the arbiter yet (§89 note) |
| 4 | Studies | studies API | — | 4 | settings-like |
| 5 | Order Flow | poll | ✔ | 5 | footprint |
| 6 | Engine (ofx) | poll + rAF | ✔ | 6 | crosshair HUD; held('ofx') honoured |
| 7 | Depth | WS + poll | ✔ | 7 | ladder + KPIs (§90 ticks) |
| 8 | Time & Sales | WS | ✔ | 8 | tape + freshness chip |
| 9 | Market Watch | 1.5 s timer | ✔ (shared) | 9 | MT5 mirror, in-place ticks (§88) |
| 10 | Scanner | 4 s poll | ✔ | ⌘ | injects itself; row ticks (§90); registered with global pause |
| 11 | Trackers | 4 s poll (v2) | ✔ | — | **see F1 — advertises readings it does not fetch** |
| 12 | CVD | ws/derived | ✖ | — | §89 note |
| 13 | Profile | poll | ✖ | — | §89 note |
| 14 | Frames | poll | ✖ | — | §89 note |
| 15 | Signals | WS + poll | ✔ | — | card arrival flash (§90) |
| 16 | Strategy | poll | — | — | follows global pause |
| 17 | Performance | poll | — | — | follows global pause |
| 18 | Replay | own transport | n/a | space , . (Replay scope) | transport is the pause |
| 19 | Alerts | poll + WS | — | — | alert-rules API; **see F2 (CSV export unused)** |
| 20 | Instruments | poll/config | — | — | toggle self-saves/applies (§85) |
| 21 | Alpaca | on demand | — | — | link flow |
| 22 | Platforms | on demand | — | — | bridge cards incl. NT (§84) |
| 23 | Settings | on demand | — | — | channels, appearance, storage-ish |
| 24 | Logs | 3 s poll (registered) | — | — | **see F3 (storage prune unused)** |
| 25 | Watchlist | poll | — | — | symbol activation list |
| 26 | News | poll | — | — | headlines |
| 27 | Fundamentals | snapshot | — | — | EDGAR/CoinGecko |
| 28 | Options | snapshot | — | — | Deribit chain |
| + | Setup wizard (rail top) | flow | n/a | — | writes config, never source |

Also in the rail's own footer/top: **Terminal mode** (Ctrl+Alt+T), Classic-terminal link,
**‹ hide rail** (brand row) and the edge **❯** return arrow (visible only while hidden) — §92b/§93.

## 2. The top menu bar — what is real vs advertised

Menus: File · View · Layout · Drawings · Chart · Data · Profiles · Run · Keys · Tools · Help.

**Real and wired** (selected): workspaces (new/save/open — real store), folder openers, engine
start/stop/restart (now genuinely keyed, §92), view switching with 1–9, legend/rail/status/menubar
toggles + zen, drawing tools, chart variable editors, source switcher, extra streams, instrument
list/look-up, Run modes (desktop/headless/CLI, §87), Keys menu (§92), command palette, hotkey
sheet, telemetry, diagnostics copy, help centre, About (from live `/api/control/help`).

**26 `planned(...)` stubs — classified:**
- **Stale wording, function now exists → promote to real deep-links (quick wins):**
  *Replay…* (Replay view exists), *Notifications…* (Settings holds the channels), *Performance…*,
  *Studies library* (Studies view), *Timeframe/aggregation* (chart owns it), *History & retention*
  (Logs/Settings storage block exists — `GET /api/control/storage` is live and rendered).
- **Real, unimplemented (keep as honest stubs):** profile store family (New/Save/Save as/Load/
  Rename/Import-Export/Backup/Templates/Autosave — the *workspaces* store covers part of this
  concept; **F4: two overlapping concepts, only one built**), *Record session…*, *Recent*, *Reset
  rail order*, *Reset all view settings*, *Edit list*.
- **Environment-dependent (already honest):** *Layouts — terminal shell not loaded*; *Drawing
  layer not loaded*; *no saved workspaces yet*.
- **Exit:** no shutdown route exists in the API (`F5`); the honest alternatives are the window
  close button or a new `#mbHide`-style quit — needs a design decision, not a stub.

**3 disabled entries** carry reasons (config authority, starter board, profiles folder) — all
honest as-is.

## 3. Server routes with **no UI caller** (the unexposed surface)

| Route | What it is | Verdict |
|-------|-----------|---------|
| `GET /api/atlas/dots/{symbol}` | Trackers "dots" table | **F1 — wire into Trackers** |
| `GET /api/atlas/correlation` | cross-symbol correlation | **F1 — wire into Trackers** |
| `GET /api/atlas/crossvenue/{symbol}` | cross-venue reads | **F1 — wire into Trackers** |
| `GET /api/atlas/intent/{symbol}` | intent profile per symbol | wire (Trackers/Engine tab) |
| `GET /api/atlas/trades/recent/{symbol}` | recent trades feed | wire (Tape alt / Trackers) |
| `GET /api/atlas/export/tape/{symbol}.csv` | server-made tape CSV | **F2 — Tools ▸ Export** |
| `GET /api/atlas/export/heatmap/{symbol}.csv` | server-made heatmap CSV | **F2 — Tools ▸ Export** |
| `GET /api/atlas/export/alerts.csv` | server-made alerts CSV | **F2 — Tools ▸ Export** |
| `GET /api/atlas/status`, `/capabilities` | atlas module diagnostics | Systems-board candidate |
| `GET /api/control/datasources` | data-source matrix | wizard/Settings candidate |
| `GET /api/control/trades` | engine trade log | Performance candidate |
| `GET/POST /api/control/backfill` | history backfill | platforms.js references it (verify caller) |
| `POST /api/control/storage/prune` | prune the tick store | **F3 — Logs storage block button** |

*(CSV routes verified live: HTTP 200; empty body when the store holds nothing yet — an empty CSV
is the honest answer, not an error.)*

## 4. Findings, in priority order

- **F1 (highest) — Trackers advertises what it does not fetch.** The view's own menu description
  says "correlation, dots, cross-venue reads"; the fetches are alert-rules/history/imbalance/tape
  only. Five live routes (`dots`, `correlation`, `crossvenue`, `intent`, `trades/recent`) have no
  caller. Either wire the tables or correct the claims — never neither.
- **F2 — Three server-made CSV exports sit dark.** Tools has no export entry; `/export/save`
  (client-built) is wired elsewhere. A Tools ▸ Export submenu pointing at the three CSV routes is
  a ~hour job with live endpoints already proven.
- **F3 — `storage/prune` unexposed** while the Logs/Settings storage block renders usage; the DB
  is ~776 MB (§86b). A "Prune now…" button with a confirm is the obvious unlock.
- **F4 — Profiles vs Workspaces: two overlapping stores, one built.** Reconcile the Profiles menu
  against the working workspace store instead of maintaining a parallel story.
- **F5 — No quit/exit path in the API.** Decide: window close only (keep honest stub) or add a
  quit route + menu item.
- **F6 — §89's honest remainder** (CVD/heatmap/profile/frames pause buttons + L2 ladder cell
  ticks) — their paint paths must consult the arbiter first; buttons before wiring would lie.
- **F7 — Serve-time verification habit**: the byte checks (curl on served markup) caught two
  glyph bugs the screenshots alone would have missed; keep using them.

## 5. Recommended upgrade queue (scoped, in order)

1. **Trackers: wire dots / correlation / cross-venue / intent / trades-recent** (F1) — the biggest
   real unlock; tables already have a home, routes are live.
2. **Tools ▸ Export submenu** (F2): Tape CSV · Heatmap CSV · Alerts CSV (active instrument).
3. **Logs/Settings: Prune-now button** (F3) with confirm + post-prune refresh.
4. **Promote the stale stubs** (bare deep-links) from §2's first bullet.
5. **Profiles ↔ Workspaces reconciliation** (F4) — one concept, one menu path.
6. **§89 remainder** (F6): arbiter-consulting paint paths, then buttons + ticks.
7. Optional: `datasources` in the wizard; `atlas/status` into the Systems board; `control/trades`
   into Performance; decide F5.

## 6. Delivered in this session, against this audit

- §88 Market Watch live board (+pause), §89 per-surface pause (10 surfaces wired; remainder named),
  §90 live-tick layer (arrows/flash program-wide), §91–§92b chrome hide/show (persistent topbar
  toggles, in-bar one-way hides), §92 Keys menu + shortcut prompts + the audit's key gaps
  (Ctrl+Alt+S/X/R, Ctrl+F, Ctrl+PgUp/PgDn) — and **§93: the rail's visible return arrow at the
  left edge while hidden**, with the topbar toggles now flipping their own glyphs
  (⇤/⇥ rail, ⌃/⌄ menu bar).
