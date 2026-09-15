# UI menu bar, sidebar and user-profile system — design and build plan

Status: plan for approval. Nothing here is built yet; nothing in the repo was changed while
writing it. HEAD `b2ff4ee`, working tree already carries the engine/legend work from today.

Sources: the 15 reference screenshots in `Desktop\New Folder` (the reference platform and the DTC platform), the
the reference platform knowledge-base link supplied with `no7.jpg` (Volume Dots / volume bars), the reference platform's
"Open The Main Window" (File / Connections / Settings / Help menus), the DTC platform's *Chartbooks
(Workspaces)*, *Global Settings Menu* and *Transferring settings between installations* pages, and
the reference platform's workspaces/templates/reset documentation. Plus an inventory of this app's own chrome,
config store and control API.

---

## 1. What the screenshots actually show (register)

| # | Program | Surface | What it teaches |
|---|---|---|---|
| no1 | the reference platform | Main window, full | Classic four-item menu bar (File / Connections / Settings / Help) over a dense chart: toolbar of tool icons + colour-scale slider, instrument tabs, left trading panel, right ladder, time axis |
| no2 | the reference platform | **File menu open** | Create/Open/Save/Save As Workspace (Ctrl+O, Ctrl+Shift+S), Record, Import orders file, Export, Alerts, Show log file, **Open user folder**, Refresh the reference platform, Exit — i.e. workspaces are a *File*-level concept, and the "user folder" is a first-class door to config/logs |
| no3 | the reference platform | **Settings menu open** | Colour settings, Configuration, Configure add-ons, Manage plugins, **Keyboard shortcuts**, Time zone, Reset zoom on subscription, Orders dialogs, Reset strategy permissions, **Reset all chart settings**, Replay startup action, Coredump, Performance — Settings mixes *links to windows*, *behaviour toggles* and *reset actions* in one menu |
| no5 | the reference platform | Plugin manager + Connection configuration | Connectors as installable/removable plugins with versions (the reference platform Connect / Add-ons tabs, Install/Remove); connection = platform + name, add/remove platforms, "active connection cannot be edited" |
| no6 | the reference platform | Drawing-tools dropdown | Anatomy of a tool menu: None/Edit/Line/Ray/Vertical/Horizontal/Rectangle/Ellipse/Text/Channel + **Single figure mode** (checkable), Hide all drawings, Change drawing style, Clear drawings |
| no7 | the reference platform | Studies configuration (Volume Dots) | The deep settings pattern: left = study list with checkboxes, right = the selected study's parameters: 2D dots / 3D bubbles, total volume vs delta, size slider (+ show slider on toolbar), transparency, **clustering** (Smart / by time / by volume / by price / by price+aggressor) with a level slider, min displayed volume, min trade size, Apply-to-bars / Inherit-from-bars, RESTORE defaults |
| no8 | the DTC platform | **File menu open** | New/Open Historical + Intraday Chart, Find Symbol, Trading DOM, **New/Open Chartbook (Ctrl-B)**, Chartbook Group, spreadsheets, Save/Save As/Save All, Data/Trade Service Settings, Connect/Disconnect/Reconnect, Sub Instances, Study Summary, Print, and a **recent-files list** (1…14, Open All, Clear Recent File List) |
| no9 | the DTC platform | **Chart menu open** | Per-window settings *and* commands in one place: Chart Settings (F5), Graph Draw Types ▸, Graphics Settings ▸, session toggles, grids ▸, log scale, show bid/ask lines, Replay ▸, Reload/Recalculate, Watch-list scoping, linking ▸, **Show Menu** (a toggle), bar periods ▸, scale ▸, **Reset Bar Size/Spacing/Scale**, **Reset Child Windows**, hide-drawings ▸, Goto Date-Time, scroll ▸, goto beginning/end |
| no10 | the DTC platform | **Trade menu open** | Simulation/live toggles, trade windows, chart trade mode, DOM settings, order/fill visibility, **General Trade Settings**, **Customize Columns**, Global P&L, clear simulation data, AutoTrade, keyboard-shortcut toggles, order allocation |
| no11 | the DTC platform | Quote/spreadsheet window + its context menu | Window-scoped settings menu (File ▸ / Settings ▸ / Alerts ▸ / Symbols ▸) with per-window fields, title, sorting, editing, always-on-top, linking |
| no12 | the DTC platform | **Window menu open** | Cascade / tile H+V / grid, maximise/minimise/restore (Ctrl-Alt-X / Ctrl-Alt-R), always-on-top, detach, hide, **Control Bars ▸**, Windows and Chartbooks (Ctrl-W), **Reset Windows**, **Reset Settings Windows**, Message Log (Ctrl-M), Alert Manager, Chart Values (F3), previous/next chart (F4/F9), chartbook navigation (F7/F8), rename title |
| no13 | the DTC platform | Spreadsheet menu with Alerts submenu | Menu row itself: File, Quote, Trade, Global Settings, Window, CB, CW, Help + a green toggle button on the bar — submenu nesting where Alerts is greyed until the window type supports it |
| no14 | the DTC platform | **CW (charts) menu open** | A live list of open charts with symbol, period, source and **delayed/live status** — "switch chart by listing them", not by hunting tabs |
| no15 | the DTC platform | **Help menu open** | Getting Started, Table of Contents, Support, Data/Trade Services — Help as a small, curated set of doors |

**Distilled from all fifteen** — what an experienced user of these programs expects:

1. A **persistent menu bar** at the very top with 4-9 named menus, every item labelled with its
   accelerator, every toggle showing a checkmark, every grouping expressed as a submenu.
2. **Workspaces/profiles are a File-menu concept**, saved as named files, reopened automatically,
   with a recent list and Save / Save As / Duplicate semantics.
3. **Settings menus mix four kinds of thing**: windows (colour, configuration), behaviour toggles
   (reset zoom on open, mute alerts), **reset actions** (reset chart settings / windows / scale),
   and diagnostics (log file, message log, about/version).
4. **Per-window (per-view) settings live in the menu for that window** — the conventional Chart menu is the
   masterclass: settings, toggles, quick resets and navigation for the chart you are looking at.
5. **Studies/indicators each carry their own deep parameter panel** with a restore button, and
   *clustering/aggregation* is a first-class parameter family (no7) — exactly the kind of control
   this app's footprint/heat layers need.
6. **Connections and plugins are managed, versioned and removable** (no5) — not hardcoded.
7. **Layout control is explicit**: tile/cascade/reset windows, control bars, always-on-top,
   detach (no12) — plus a "reach the folder, reach the log" escape hatch (`Open user folder`,
   `Show log file`).
8. **A hotkey map that is itself editable** (the reference platform: double-click the line to rebind).
9. **A Help menu that is short** — Getting Started, Table of Contents, Support, Data services.
10. Colours, timezone, and *display density* are global settings; **chart variables are per view**.

---

## 2. Where this app stands today (inventory, verified in the working tree)

| Surface | What exists | Gap against the reference |
|---|---|---|
| Left rail | 22 views: overview, chart, heatmap, studies, orderflow, ofx, depth, tape, trackers, cvd, profile, frames, signals, strategy, performance, replay, alerts, instruments, alpaca, platforms, settings, logs | No grouping headers, no collapse, no reorder, no per-view options next to the view |
| Top bar | ☰ menu button, symbol picker, engine pill, **workspace pill**, source pill, live pill, start/stop/restart buttons, pause chip, filter + panel host for the ☰ overlay | **No menu bar.** One ☰ overlay carries everything, so nothing is discoverable by name; the pills are status, not navigable settings |
| ☰ overlay (`menu.js`) | panels grouped by purpose (Order flow / Analytics / Trading / Information), free-data connections with status dots, hotkey list, **workspaces** (save/delete, list) | It is a launcher, not a menu: no accelerators, no toggles, no submenus, no File/View/Profiles/Tools/Help taxonomy |
| Workspaces | `GET/POST /api/control/workspaces`, stored in `config.json → workspaces`, browser cache in `localStorage['ofap.workspaces']`; snapshot = `{view, ofx params + symbol, saved}` | Captures **three fields**. A "profile" needs every display variable, layout, chart config, theme, watchlist, alert rules and hotkeys |
| Config store | `desktop/config_store.py`: schema defaults + sanitisers (`clean_*`, `_block`), **atomic writes** (`*.json.tmp` → `replace`), `POST /config/reset`, `GET/POST /config` | The right home for a profiles block; already has the atomic-write and reset patterns to reuse |
| Config keys | `version, data_source, instruments[49], telegram{token,chat}, notify, context, dashboard{host,port}, platforms, studies, workspaces, ofx, risk, atlas{17 sub-blocks}, alpaca{key,secret}, mt5{login,password,…}, search{recents,pins,…}, watchlist, logging, ui{banner,wizard step}, onboarding_done` | **Credentials live here** (telegram, alpaca, mt5) — profiles must never carry them |
| Control API (`desktop/api.py`) | `bootstrap, config, config/reset, capabilities, datasources, instruments/*, studies/*, sources, source, ofx (GET/POST), atlas/footprint, platforms/*, sierra/dtc*, engine/{status,start,stop,restart}, live-status, alpaca/*, mt5/test, telegram/test, profiles/{rebuild,status} (volume profiles — name collision!), logs, logs/clear, export/save, client-error, workspaces, search/*` | No profile endpoints; note `/profiles/*` is already taken by volume profiles |
| Settings view | rendered by `ui.js renderSettings()` (source, cooldown, score, log level, telegram, MT5 status, atlas toggles + per-instrument pattern thresholds) | Flat page, not organised by the menu taxonomy; no per-view settings dialogs |
| Engine params | `ofx` block: R, stack, lambda_ms, text_px, sweep_c, min_block, va_pct, symbol (+ ramp in localStorage) | A good start, but the *registry* (name, type, range, default, meaning) exists only implicitly |
| Persistence | `localStorage`: `atlas.sound`, `ofx.ramp`, `ofap.workspaces`, plus the new legend open flag | State is split between config.json and localStorage with no single owner |

**Names**: the existing `/api/control/profiles/*` endpoints are **order-flow volume profiles**. The
new user-facing feature must therefore be named distinctly — recommendation: UI calls it
**Profiles** (as he asked), API namespace `/api/control/user-profiles`, internal block
`user_profiles`. Renaming the volume-profile endpoints is not worth the churn.

---

## 3. The top menu bar (specification)

A real menu bar between the title strip and the toolbar, always visible, driven from one registry,
with every item carrying its accelerator. Proposed tree (items marked ★ are new):

**File** — New Workspace ★ · Open Workspace (Ctrl+O) · Save Workspace (Ctrl+S) · Save As (Ctrl+Shift+S) ·
Import… ★ · Export… ★ · **Recent** ▸ (last 10) · Record sessions ▸ (extend to live capture) ★ ·
Import orders/CSV ▸ ★ · Export data ▸ (uses existing `POST /export/save`) · **Open user folder** ★ ·
Show log file ★ · Restart engine · Exit

**View** — the 22 rail views, grouped as the ☰ menu already groups them (Order flow ▸ / Analytics ▸ /
Trading ▸ / Information ▸), each with its rail hotkey; then: Rail ▸ (show/hide, compact, reorder) ★ ·
Status bar ▸ ★ · Legend panel (toggle, persisted) ★ · Readout panel ▸ ★ · Full screen /
Zen mode (hide chrome) ★ · Reset layouts ▸ (ports the reference platform's "Reset all chart settings" + the conventional
Reset Windows) ★

**Chart** (per active view — the DTC platform pattern) — the *active view's* own settings: for
**Engine**: Footprint ▸ (rows per bar, tick grouping, text threshold, level cap), Heat ▸ (ramp,
saturation, history window, decay), Flow ▸ (sweep size scale, min block, event filter), Value ▸
(VA %, POC/HVN tints), Navigation ▸ (bounded pan, snap-to-live, fit session), Restore view defaults ★ ·
for **Chart**: timeframe, study overlay, markers, session times · for **Depth**: ladder depth,
tick grouping, size format · for **Heatmap**: window, aggregation, dimming, cutoffs (the reference platform's
config panel vocabulary) · for **Time & Sales**: min size, row cap, colouring.

**Data** — Data source ▸ (the six free feeds, with live status — already implemented behind
`/api/control/sources`) · Instruments ▸ (add/enable/remove; `instruments` is 49 entries today) ·
Timeframe/aggregation ▸ · History ▸ (retention, vacuum, storage used — from the DB figures in §8) ·
Replay ▸ (load a stored session, speed) · Feed health ▸ (tick rate, latency, gaps — data exists in
`live-status`) · Notifications ▸ (telegram/ntfy/email tests) ★

**Profiles** (see §6) — current-profile chip · New from current · New from template ▸ ·
Save · Save As… · Load ▸ (list) · Rename · Duplicate · Delete · **Import…** · **Export…** ·
Backup all ★ · Restore from backup ★ · Autosave ▸ (off / 5 / 15 min) · Reset section ▸ ·
Open profiles folder ★ · **Quick switch Ctrl+Alt+1…9** ★

**Tools** — Command palette (Ctrl+K, exists) · Hotkey editor ★ (the reference platform's rebindable list) ·
Studies/indicators library (exists: `/studies/library`) · Alerts manager (exists as a view) ·
Export manager · Performance ▸ ★ (refresh-rate cap, depth resolution, retention, "safe mode"
profile — the reference platform's Performance submenu translated) · Diagnostics ▸ ★ (render telemetry:
frames/p95/LOD/cells — the engine already exposes `OFX.stats()`) · Developer ▸ (client-error test,
reload UI)

**Help** — Getting started (the wizard exists: `guide.js`) · Legend & keys (exists, today's work) ·
Table of contents ▸ (deep-links into every settings dialog) ★ · Data/Trade services ▸ (the
`platforms` view) · Support / diagnostics bundle ★ · About (version, build, config path, DB path) ★

Mechanics that make it feel like a Windows app: Alt or F10 focuses the bar; typing jumps to the
matching item; arrow keys walk items; submenus open on hover with a 150 ms delay; Esc closes
everything; every item that has a shortcut shows it right-aligned; checkable items show ✓; disabled
items are greyed with a tooltip explaining *why* (the conventional greyed Alerts entry is the model);
File/Edit-style items land in a second row (toolbar) only for the five most-used actions.

---

## 4. Sidebar: keep the rail, add the missing two layers

The rail is already the right primary navigation and matches how the reference platform/ATLAS users think (panels,
not documents). What is missing is what the references have around their panels:

1. **Group headers + collapse** in the rail (Order flow / Analytics / Trading / Information), so 22
   items become four readable blocks; collapse state is part of the profile.
2. **Per-view Options dock** ★ — a collapsible right-hand column inside the active view that hosts
   *that view's* variables (Engine: the footprint/heat/flow/value groups from §3; Heatmap: dimming,
   cutoffs, clustering). This is where the reference platform's studies panel lives; today our Engine view has
   these scattered in a toolbar row.
3. **Workspace tabs** ★ — the conventional chartbook tabs / the reference platform's instrument tabs: a tab strip under the
   menu bar where each tab is a saved *layout instance* (view + instrument + profile overlay), so
   "BTC footprint + BTC ladder" and "ETH heatmap" are one click apart. Tabs belong to a profile.
4. **Status bar** stays as is (it already carries the hint text, tick rate, chips) and gains the
   active profile name and a click-through to Profiles ▸.

No second navigation hierarchy: the rail navigates *what kind of panel*, the menu bar commands
*actions and settings*, the dock holds *this panel's variables*. Three levels, no overlap.

---

## 5. Display-variable architecture (the "myriad of variables")

The reference programs get away with hundreds of knobs because the knobs are **registered, typed
and grouped**, not scattered. Proposal:

1. **One registry** `desktop/ui/param-registry.js` ★ — every display variable declared once:
   `{id, label, group, view, type: number|bool|enum|colour, min, max, step, default, unit,
   meaning, applies: 'live'|'restart', since}`. The engine's existing params (R, stack, lambda_ms,
   text_px, sweep_c, min_block, va_pct, ramp) become its first entries; the atlas blocks, ladder and
   tape settings follow.
2. **Settings dialogs are generated from the registry** — a per-view dialog with groups as tabs
   (the reference platform's studies panel, no7), each control showing its meaning on hover, plus **Restore
   defaults per group** and **Apply/Cancel** with live preview where cheap.
3. **Server-side clamp stays authoritative** (`config_store.py` sanitisers) and the UI adopts the
   value the PUT returns — the existing convention, kept.
4. **A `settings` menu item can deep-link any dialog** (`#settings/ofx.heat.saturation`) so docs,
   the wizard and the menu all point at the same place.
5. **Performance group** (new): refresh-rate cap, depth-history window, heat resolution (ticks per
   row), payload caps, "safe mode" (all optional layers off) — the equivalents of the reference platform's
   Performance submenu and the honest answer to "why is it heavy today".
6. **Colour/theme**: one colour editor (the reference platform's Colour settings) writing the theme keys already
   centralised in `math.theme` today — buyer/seller colours, imbalance, POC, heat ramp stops.

---

## 6. The profile system

**A profile is a named, versioned bundle of display + analysis state. Never credentials.**

### 6.1 Scope table (what a profile owns)

| Included | Excluded (machine/licence/safety) |
|---|---|
| Active view, rail order/visibility/collapse | Telegram/ntfy/email tokens |
| Every registry variable (engine, atlas, heatmap, depth, tape, chart, studies) | Alpaca key/secret, MT5 login/password/server/path |
| Chart/panel configs: symbol set, timeframes, study overlays, markers | `dashboard.host/port`, `logging.level` |
| Layout: dock state, split sizes, legend/readout open flags, tabs | `data_source` (offer as a *prompt* on load, not silent) |
| Watchlist + search recents/pins | Paths, device-specific settings (scale/dpr) |
| Alert rules and their channels (opt-in checkbox at save time) | Onboarding/wizard flags |
| Hotkey map, theme/colour keys | Anything matching `password|token|secret|key` |

Rationale: the conventional own docs make the distinction — `the DTC platform4.config` is safely shareable *because*
account settings are not in it. Our profiles follow the same rule, and a test enforces it.

### 6.2 File format and storage

```
%APPDATA%\OrderFlowAnalysisPro\
    profiles\
       index.json                     # {version, active, order:[names], updated}
       daytrade.ofap.json             # one file per profile
       scalping.ofap.json
       crypto-research.ofap.json
       backups\
         2026-09-15T19-40.ofap-backup.zip     # optional full backup
    exports\                          # existing export target
```

```jsonc
{
  "kind": "ofap-profile", "schema": 1, "name": "daytrade",
  "created": "...", "updated": "...", "app": "0.9.x", "notes": "",
  "extends": "builtin.daytrade",          // template inheritance, applied then overridden
  "scope": { "engine": {...}, "views": {...}, "layout": {...},
             "watchlist": [...], "alerts": {...}, "hotkeys": {...}, "theme": {...} }
}
```

Rules: atomic writes (`*.tmp` → `os.replace`, already the house pattern); `schema` integer with a
`migrate()` chain (the conventional "old chartbooks not compatible" lesson — version it now); unknown keys
preserved on round-trip; size cap (e.g. 512 KB) with the offending key named.

### 6.3 API (new, distinct from volume profiles)

```
GET    /api/control/user-profiles                 → index + names + timestamps + active
GET    /api/control/user-profiles/<name>          → the bundle
POST   /api/control/user-profiles                 → {save|saveAs|rename|duplicate|delete|setActive}
POST   /api/control/user-profiles/import          → {path} (leaf-only, under the config dir) or {name, text}
GET    /api/control/user-profiles/export?name=…   → {path} written into <config>/exports/
POST   /api/control/user-profiles/backup          → {path} zip of the profiles folder
POST   /api/control/user-profiles/restore         → {path} (validated, backup taken first)
POST   /api/control/user-profiles/reset           → {section} → defaults from a builtin template
POST   /api/control/folder/open                   → {folder: 'profiles'|'exports'|'config'|'logs'}
```

Every write returns the new index so the UI never displays a state the store did not accept
(house convention). Import paths are reduced to leaf names and must resolve under the config dir;
the same guard as `export/save` today.

### 6.4 UX

- Menu bar **Profiles** menu as in §3, plus a profile chip top-right showing the active name.
- **Save** is instant (`Ctrl+S`), **Save As** prompts, both show "saved to <path>" on its own line.
- **Load** is a list with timestamps and a note of what will change ("3 views, engine + heat params,
  watchlist 12 symbols, 4 alert rules") — a diff summary *before* applying, because silently
  swapping every display variable is the classic footgun.
- **Autosave** every N minutes (the reference platform's 5-minute pattern) into `profiles/autosave.ofap.json`,
  and "restore last session?" on launch if the app closed dirty.
- **Quick switch** Ctrl+Alt+1…9, bound to the nine most recent profiles.
- **Templates shipped** (builtin, read-only, extendable): *Scalper* (15 s/1 m bars, tight rows,
  flow-heavy, low heat history), *Day trader* (1-5 m, VA + ribbon + sweeps), *Swing/analyst*
  (15 m-1 h, depth history long, profiles + heat), *Research/replay* (replay-first, no live feed
  needed), *Low-resource* (safe mode: no heat history, minimal payloads, capped refresh).
- **Backup**: `Backup all` writes a zip; optional "keep last 10"; `Restore` always backs up the
  current folder first and reports exactly what it replaced.

### 6.5 Failure modes to design for (each gets a test)

1. Secret leakage into a profile file → redaction test over every saved bundle.
2. Partial write on crash → atomic write test.
3. Profile written by a newer schema → refuse with the version named, never half-apply.
4. Import path traversal → leaf-only + resolve-under-config-dir test.
5. Applying a profile that references a missing instrument/source → report per-item, apply the rest.
6. Two windows/instances writing profiles → single-writer via config-store lock (already the file
   writer's job), last-writer-wins surfaced in the UI.

---

## 7. Build order, each phase ending in a gate

| Phase | Work | Gate (evidence, not vibes) |
|---|---|---|
| 0 | `param-registry.js` built from the existing params; no UI change | registry dump equals the live config values for engine + atlas blocks; selftest |
| 1 | Menu bar shell: markup, registry-driven rendering, accelerators, arrow/typing navigation, checkmarks, submenus, disabled-with-reason; wire the 20 highest-value items to existing endpoints | every item reachable by keyboard; a probe that clicks each item and asserts the endpoint it calls (fetch spy); no dead items (audit script extended) |
| 2 | Per-view settings dialogs from the registry (Engine first, then Heatmap/Depth/Tape/Chart); restore-defaults per group | apply → PUT returns the adopted value → engine params change; restore returns the documented defaults; screenshot + telemetry |
| 3 | Profile store: config_store block, api routes, atomic writes, schema + migrate, redaction; Profiles menu (save/as/load/list/rename/duplicate/delete/active chip) | round-trip test (save→load→compare), redaction test, atomicity test, API tests, UI smoke asserting three surfaces changed |
| 4 | Templates, import/export, backup/restore, autosave, quick-switch hotkeys, "open folder" | backup zip exists and restores to a byte-identical index; import of a crafted profile applies and reports; autosave file appears after N minutes |
| 5 | Rail grouping/collapse, Options dock, workspace tabs, status-bar profile chip, hotkey editor, About/Diagnostics, user-folder/log links | rail collapse persists in the profile; dock edits round-trip; every new id passes `audit_ui_refs.py` |

Standing constraints apply throughout: no commits, no new runtime dependency, must still freeze into
the standalone exe, credentials never written by the UI, and each phase keeps the suite green
(current baseline: 313 passed / 2 skipped, ofx selftest 119, `audit_ui_refs.py` clean).

---

## 8. Improvements flagged while reading the references

1. **Command palette unification** — Ctrl+K already opens a palette (`search.js`); the menu bar and
   palette should read the same registry so nothing is only in one of them.
2. **"Show Menu" toggle** (the DTC platform) — the menu bar should be hideable for full-chart use, with the
   state in the profile (we have a full-screen ask in the wizard already).
3. **Open user folder / Show log** (the reference platform) — trivial, high value: the app already writes
   `orderflow.log` and a config dir, and the client-error loop lives there.
4. **Recent list** (the DTC platform, 14 entries) for profiles and workspaces — cheap and expected.
5. **Keyboard-shortcut editor** (the reference platform) — our hotkeys are hardcoded in `menu.js`; a registry-backed
   editor also fixes discoverability.
6. **Performance submenu / safe mode** (the reference platform) — our own heavy levers are heat history, payload
   caps, refresh rate and retention; today they are invisible. Also the honest home for the DB
   figures already measured (5.8 M ticks ≈ 547 MB, ~25 MB/hour at 52 ticks/s).
7. **Clustering as a first-class parameter family** (no7) — our depth matrix is already summed onto
   the bar axis; the missing knobs are *by time / by volume / by price / smart* for the flow layer,
   which is what an order-flow user will look for.
8. **Chart templates separate from profiles** (the reference platform) — a chart template (symbol + timeframe +
   studies + drawings) is reusable across profiles; profiles then reference templates.
9. **Diagnostics/About panel** — version, build, config path, DB path, file sizes, last errors
   (from `client-error`), and a "copy diagnostics" button.
10. **Per-view reset actions** — every view gets "Restore view defaults" in its Chart menu; today
    only the global config has a reset.
11. **Instrument tabs / workspace tabs** (§4) — the biggest single UX gain after the menu bar, and
    the natural container for multi-profile working.
12. **Recording / session capture** — the reference platform records feeds and replays them; we have replay over
    stored ticks already, so "record this session" is a small extension to the DB retention story.

---

## 9. Decisions needed before Phase 1

1. **Menu style**: classic menu bar + toolbar (the reference platform/the DTC platform as in the screenshots) — recommended —
   or a ribbon?
2. **Profile scope**: should alert rules and the watchlist travel inside a profile (recommended,
   with an opt-out checkbox) or stay global?
3. **Auto-load**: launch with the last profile silently, or show "restore last session?" briefly?
4. **Tabs**: build workspace tabs in Phase 5 (recommended) or pull them earlier?
5. **Naming**: UI says "Profiles", API says `user-profiles`, the existing volume-profile endpoints
   stay untouched — confirm.
6. **Secrets**: confirm profiles must refuse to contain any credential (recommended) rather than
   offering an encrypted vault.

---

## 10. Risks

- **Menu sprawl**: 22 views × settings menus can become a forest. Mitigation: registry-driven
  rendering, per-view menus generated from the registry, and the disabled-item-with-reason rule.
- **Profile/registry drift**: a variable that exists in the store but not the registry (or vice
  versa) is a silent no-op. Mitigation: a test that walks the config schema and the registry and
  fails on either-only entries.
- **Applying a profile while the engine runs**: some variables are `applies: 'restart'`. Mitigation:
  the registry flags them and the UI offers "apply and restart the engine".
- **localStorage vs config**: today `ofx.ramp` and others live in the browser. Mitigation: Phase 3
  moves them into the store and reduces localStorage to a cache, as the workspace list already does.
- **Naming collision** with volume profiles (§2) — resolved by the `user-profiles` namespace.
