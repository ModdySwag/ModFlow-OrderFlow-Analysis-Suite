# dxFeed-style terminal shell + Quantower integration — architecture and plan

Status: plan for approval, written after his brief. **Phases 0–3 are built and verified**
(§7, §8, §9, §10 below) — HEAD `b2ff4ee`, nothing committed.

Sources: dxFeed's own dxAnalytics product page (web terminal; widget interface; authorisation over
their auth service; flexible layouts; workspace management; data export; widget integration;
dark/light themes; white-label option), the Quantower help index (account and licensing pages,
workspaces/templates/reset from earlier research), and this suite's own chrome, stores and endpoints.

---

## 1. The enabling insight: widgets are already sections

Every panel in this suite is a `<section class="view" data-view="X">` inside `.content`, and every
module self-registers, watches **its own section** with a `MutationObserver` and boots when that
section carries `.active`. That means a shell can adopt the existing panels without touching a single
view module:

* moving a section into a widget frame with `appendChild` **preserves its DOM and its listeners** —
  no re-init, no rewrite, no second copy of any view;
* the observer contract already handles activation, so a widget's panel boots when its tab shows it
  and pauses when it does not;
* therefore the terminal is a **host**, not a fork. Classic mode and terminal mode are two
  arrangements of the same panels, and switching back is a re-parent, not a rebuild.

That is the novel part worth stating plainly: the risk in "a complete UI switch" is normally the
rewrite. Here the switch is cheap because the panels were already self-contained widgets in all but
name.

## 2. What gets added

| Piece | File | Job |
|---|---|---|
| Shell host | `desktop/ui/shell.js` (new) | `OFAPSHELL.mode()`, `switchTo('classic'|'terminal')`, the widget registry, re-parenting, tab strips, keyboard (Alt+1…9 tabs, F11 focus widget, Esc back) |
| Layout store | `config_store.py` + `/api/control/layouts` | named layouts: `{id, name, mode, screen_key, tabs:[{id, name, widgets:[{view, x, y, w, h, link, settings}]}], theme, saved}`; atomic, sanitised, capped, export/import |
| Terminal styles | `atlas.css` (appended) | CSS-grid dashboard, widget chrome (title bar, tools, resize grip), tab strip, density tokens, **light theme** via `html.theme-light` variables |
| Widget chrome | `shell.js` | per-widget: drag by title bar, resize from the grip, maximise/float, close, "settings" (deep-links the parameter registry dialog), symbol/timeframe link chip |
| Layout menu | `menubar.js` | a **Layout** menu: save / save as / load / duplicate / rename / delete / auto-arrange / reset / per-screen profile / export / import — and the Classic ⇄ Terminal switch with a tick |
| Link groups | `desktop/ui/links.js` (new, ~80 lines) | symbol + timeframe groups (A/B/C/D) any widget can join: change a group's symbol once and every member follows — the widget-terminal convention |
| Widget channel bus | `desktop/ui/bus.js` (new, ~100 lines) | one subscription per (endpoint, params) with refcounts: twelve widgets on the same symbol cost one poll, not twelve. Existing views keep working when they are alone — the bus is the shell's delivery layer, opt-in per widget |

New widgets to add (all *additional*, nothing replaced): Watchlist grid, News, Fundamentals, and an
Options panel (Greeks / implied volatility / chain) — the last three are what dxAnalytics sells on top
of a data feed, so their honest state here is: build the widget, and let the data source be chosen
(free feeds give quotes and news; Greeks/IV need a real options feed such as a dxFeed subscription —
that is a data decision and a billing decision, not a rendering one).

## 3. Top Bar integration

* **Workspace switch** in the menu bar: `Layout ▸ Mode ▸ Classic | Terminal`, plus a segmented
  control in the top bar's right cluster (one click, no menu), and `Ctrl+Alt+T` as the accelerator.
* **Tabs** get their own strip directly under the top bar (Terminal mode only): `+`, rename,
  reorder, close, per-tab layout.
* **Status bar** gains: mode, active tab, the widget count, the shadow (delayed/real-time) feed state
  from the plan toggle, and the bus's own telemetry (widgets, subscriptions, deduped fetches/s).
* The existing menu bar keeps everything it has; only Layout and Window menus are new.

## 4. Non-negotiable rules for the switch

1. **Classic is untouched.** In Classic mode the DOM is exactly today's (the shell detaches), and the
   rail, menu bar, drawings, engine, legend and every parameter dialog behave as they do now.
2. **Round-trip proof, not a promise.** The gate for every phase includes: switch to Terminal, open
   three widgets, switch back to Classic, then assert every view still boots (client-error log empty,
   engine stats advancing, drawings still listed). A shell that strands a panel is a failure.
3. **One store, no duplicates.** Layouts go in `config.json` beside workspaces and drawings, with the
   same atomic write + sanitiser pattern; browser storage stays a cache only.
4. **No feed changes without a toggle.** The bus is opt-in per widget; a widget that has no bus
   subscription keeps its own polling, so a half-built terminal can never silence a view.
5. **dxFeed is a data vendor, not a dependency.** Nothing in the build will require their account;
   their terminal is the *reference* for the layout language (widgets, layouts, workspaces, themes),
   and if he later buys a feed it plugs in behind the same widget interface.

## 5. Quantower integration parity (same treatment as the Sierra surface)

`platforms.py` grows a second platform row and `platforms.js` renders it with the same structure that
already works for Sierra: free-first workflow steps, account/login links, published plans with their
read-date and source link, the separate-data-fee caveat, install detection (path + version file only),
a connection card under its own route namespace (`/api/control/platforms/quantower/*`), and the same
plan/integrated toggle whose stored facts change the suite's wording and status line.

Workflow shape (mirrors the approved Sierra one): create the free account → download and install →
stay on the free licence (limited but real) or activate a paid licence → sign in inside the platform →
add a data connection → point this suite's bridge at it → load it and pick the plan.

**One dependency before that ships:** the exact Quantower licence tiers and prices must be read from
their own licensing pages in a fresh pass (the page I reached during this investigation 404'd and the
index only pointed at the right names) — I will not print prices I have not read, which is the rule
already enforced for the Sierra numbers by `test_sierra_integration.py`.

## 6. Build order and gates

| Phase | Work | Gate |
|---|---|---|
| 0 | layout store + sanitiser + endpoints; shell host that can re-parent one panel | round-trip: classic → terminal → classic, all views still boot, log empty | **built — §7** |
| 1 | widget frames, drag/resize/maximise, tab strip, keyboard | twelve widgets on one tab stay inside the frame bounds; frames persist across a reload | **built — §8** |
| 2 | Layout menu + Workspace switch in the top bar + status-bar fields | every menu item reachable by keyboard; switches and layouts round-trip through the config | **built — §9** |
| 3 | link groups (symbol/timeframe) | changing a group moves every member widget; non-members unaffected | **built — §10** |
| 4 | channel bus with refcounts + telemetry | twelve same-symbol widgets produce one fetch per interval (measured), three different symbols produce three |
| 5 | Watchlist / News / Fundamentals / Options widgets | each renders real data from the chosen source; options panel says plainly when no Greeks feed is configured |
| 6 | Quantower surface (after the licensing read) | the `test_sierra_integration.py` pattern, mirrored: free first, published prices with read-date, allow-listed links, plan toggle adapts the wording |

Standing constraints unchanged: no commits; no new runtime dependency; the frozen build must still
work; the suite must stay fully usable in Classic mode with zero terminal code loaded.

---

## 7. Phase 0 build log (2026-09-15) — what landed and what it measured

Files: `desktop/ui/shell.js` + `shell.selftest.js` (new), `desktop/config_store.py` (`layouts` block
+ sanitiser), `desktop/api.py` (`GET/POST /api/control/layouts`), `desktop/ui/index.html` (script tag,
rail-footer **◫ Terminal mode** button), `desktop/ui/atlas.css` (terminal styles), and
`orderflow_system/test_{shell,layouts}.py`. Registered in `scripts/audit_ui_refs.py`'s `JS_FILES`.

The store keeps `{mode, active, items{id:{name, mode, screen_key, theme, saved, tabs[{id, name,
widgets[{view, x, y, w, h, link, settings}]}]}}}`; the grid is 12×8 with 24 layouts / 12 tabs /
24 widgets per tab. Geometry is clamped size-first then position (a widget cannot be stored hanging
off the grid), ids must be slugs, and unknown views or repeated panels are dropped — one section per
view means one frame per view. Endpoints answer with the state the store *accepted*, and a refused
save comes back `ok:false` with the reason instead of disappearing.

The round trip was measured live in a sandboxed instance (port 8099, APPDATA redirected, Bybit feed
running), Classic → 10 widgets across two tabs → Classic: 24 sections in the exact recorded order
afterwards, `.view.active` count == the number of visible widgets on each tab (7 on Main, 3 on
Macro — hidden tabs really do pause their panels), a rail click inside Terminal mode places and
focuses that panel, `OFAPINTENT.status().feed.ticks` runs 0 → 4 426 → 4 480 straight through the
switch (ingest is never touched), the mode survives a reload and the app boots back into Terminal
with the same 10 widgets, and the sandbox log holds **0** `client error:` lines.

Two of my own defects the probe caught and this log records: the first restore pass re-inserted each
section "before its recorded next sibling" and came back **shuffled** (a sibling still inside a frame
reads as absent, so the node was appended instead — fixed with a DocumentFragment re-append in
recorded order), and the Engine view's fixed 238 px readout starved its canvas to **79 px** inside a
327 px frame (fixed with container queries on the frame: `container-type: inline-size` → 295 px
stage). Grid rows are `minmax(56px, 1fr)` so a full board fits the window instead of always scrolling.

A third one, in the Engine view's own geometry: the engine's pointer maths reads
`getBoundingClientRect`, so its internal space and the stage box must be the same — `stageSize()`
returned `max(240, clientHeight - 8)`, which in a 148 px-tall widget put the hovered price (and the
trace line naming it) elsewhere on the drawn matrix. It now returns the exact box, `null` when the
stage is hidden, the view re-measures whenever it comes back on screen, and the shell announces
re-parents and arrangement changes as `ofap:relayout` — a re-parent is invisible to the window resize
listeners the views already have, so the canvas otherwise kept its Classic size (293×240 in a
213×148 stage). Verified live: stage == internal == canvas at 750×260 in Classic, 293×148 in a
widget and back; hover offset 0.00 px (34 px before the fix).

Deviations to know about before phase 1: the active tab is session state (it resets to the first tab
on reload — the store has no field for it yet), and a layout widget whose panel is missing from the
build is dropped with a line in the bar without persisting the drop until the user rearranges
something.

---

## 8. Phase 1 build log (2026-09-15) — widget chrome, tabs, keyboard

`desktop/ui/shell.js` (765 → 1185 lines) and `shell.selftest.js` (18 → 22 checks), plus
`OFAPMenuBar.setView/openFor` in `menubar.js` and the frame/chip styles in `atlas.css`.

**Chrome.** Drag by the title bar and resize from the corner grip, both snapped to grid cells through
two pure functions (`math.moveRect` — a delta in cells then the same clamp a stored rect gets;
`math.resizeRect` — position kept, size limited by the distance to the edge). The clamp is applied on
every pointermove, so no gesture can leave the grid; the widget you placed comes to the front. The
bar carries ⚙ (this panel's registry variables), ⛶ (fill the grid, `F11`) and × (off the tab).
Maximising stores the pre-maximise rect in the widget's own scalars (`settings.px/py/pw/ph/max`), so
Esc still restores after a reload. `Esc` is also the focus ring's escape.

**Tab strip.** `+` adds a tab, double-click renames it in place (the input swallows its own keys, so
a tab named "1" is not the tab hotkey), chips drag to reorder, and the active chip's × closes it —
saying out loud how many panels went with it. One tab minimum, twelve maximum.

**Keyboard.** `Alt+1…9` switch tab, `F11` fills the grid with the focused widget, `Esc` restores,
`Ctrl+Alt+T` still swaps modes. Typing is never a hotkey.

**Measured.** A 2-cell/1-cell drag landed exactly at (6,1); a drag 3× the board past the corner
stopped at (8,6); a resize at the edge changed nothing (before the fix it jumped the widget to x=0 at
full width); the gear opened the Chart menu carrying the focused panel's own variables (`ofx.R`,
"Stacked run (levels)", 65 items). The gate: twelve widgets on one tab, **none outside the board**
(998×504 px, frames 120–248 px), `bounds().outside` 0, twelve `.view.active`, all 24 sections still in
the document; a drag and a resize survived an **immediate** reload; Classic → Terminal → Classic
restored the 24 sections in the exact recorded order with ingest ticking throughout and 0 client
errors.

**One real persistence hole, found and closed:** writes are deferred behind the arbiter's gesture
lease (by design), so a drag followed by a reload within ~1.6 s reverted. `pagehide` and a hidden
`visibilitychange` now run the pending save immediately with `keepalive`, and a dirty stamp means a
save in flight never swallows a later edit.

**Not built in this phase:** *float* (free-pixel windows hovering over the board) — ⛶ fills the grid,
which is the same thing inside a 12×8 model; the symbol/timeframe link chip (phase 3, with
`links.js`); per-panel settings dialogs (phase 2 — the gear reuses the registry's Chart-menu editor).

---

## 9. Phase 2 build log (2026-09-15) — the Layout menu, the switch, the status line

`desktop/ui/menubar.js` (a Layout menu + in-place prompts), `desktop/ui/shell.js` (the CRUD the menu
calls, the status writer, the feed line), `index.html` (the segmented switch, four status fields),
`atlas.css` / `modules.css` (their styles), `test_shell.py` (+1 test → suite 352 passed / 2 skipped).

**The Layout menu** is built from the store on every paint, so it can never show a layout that is not
there: Workspace (Classic ⇄ Terminal, ticked), This layout (Name · Save now · Save as… · Duplicate ·
Delete…), Auto-arrange this tab (disabled *with its reason* in Classic mode), Reset to the starter
board, Save for this screen (`<w>x<h>@<dpr>`), Export current…, Import (paste a bundle)…, then every
saved layout with `· active` / `· this screen` / `saved on <key>` and its widget and tab counts.

**Text answers happen in place.** `window.prompt` is not guaranteed to render inside the frozen
shell's WebView, so the menu swaps its own body for a prompt block (Enter applies, Esc cancels,
Ctrl+Enter for the multiline paste box) — and the input swallows its own keys, so a layout named "1"
is not read as a hotkey.

**The shell grew the store actions the menu names**: `saveAs · renameLayout · duplicateLayout ·
deleteLayout · activateLayout · saveForScreen · resetBoard · exportLayout · importLayout · layouts ·
refreshLayouts · screenKey`. Each one adopts what the store *accepted*, Delete asks for the layout's
own name first, export writes a real file into the exports folder, and import lands the bundle under a
fresh id with a de-duplicated name.

**The top bar** gains a two-segment switch (`#modeSwitch`, one click, `aria-pressed`, in the right
cluster beside Start/Stop), and the **status bar** gains mode · tab · widgets · feed — the feed line
taking its wording from the stored plan (Sierra `plan`/`integrated`) or the built-in source, so it
cannot describe a feed the app is not promising.

**Measured.** The Layout menu walked end to end with real CDP keystrokes (Alt → → → ↓, then ↓ through
all 13 items, reading `document.activeElement` at each step); "Save as…" typed "Evening board" into
the in-place prompt and applied on Enter (saved, active, `screen_key 800x600@1`); rename → "Evening
desk"; duplicate → "Evening desk copy"; delete with a wrong name **refused**, with the right name
stepped onto the next layout; reset → the 4-widget starter board; arrange → a 2×2 tiling with
`outside: 0`; export → `layout-Start.json` (1 066 bytes) on disk; that bundle re-imported as
"Start 2"; an unparseable bundle refused by name. After a reload the app came back in **Classic**,
and then — with "Twelve" active — in **Terminal with all 12 widgets**, status reading
`Terminal / Twelve / 12 / Bybit · free feed`. Classic → Terminal → Classic still restores the 24
sections in the exact recorded order, and the sandbox log holds **0** `client error:` lines.

**Defect found and fixed in `menubar.js`:** ArrowDown inside an open menu did nothing. The only
ArrowDown branch opened a menu from a *title*, so with an item focused the keyboard could reach the
first item of every menu and no further — the phase-2 gate ("every menu item reachable by keyboard")
was failing against the existing menu, not against the new one. The in-menu walk now exists alongside
the ArrowUp branch that was already there.

---

## 10. Phase 3 build log (2026-09-15) — link groups

`desktop/ui/links.js` (new, `window.OFAPLINKS`), `links.selftest.js` (10 checks), the link chip in
`shell.js`, `config_store.py` (the link shape, enforced), `atlas.css`, `test_links.py` (9 tests) —
suite **361 passed / 2 skipped**, AUDIT CLEAN, shell selftest 22 ok.

**Two halves, deliberately split.** MEMBERSHIP is stored state: each widget's `link` field in the
layout (`"<symbol group>/<timeframe group>"`, A–D, either side optional), sanitised by the config store
and written through the shell (`setLink`, `linkMembers`, `linkSpec`) — so it survives a reload because
it is part of the arrangement, and a layout exported on one machine carries its links to another. What
a group *means* — its symbol, its timeframe — is runtime state seeded from the panels already on
screen: a group whose members all show BTCUSDT **is** a BTCUSDT group whether or not anyone wrote it
down, and the panels' own controls are the only place those values really live.

**The panels are the authority for what they can accept**, and the module says so out loud: the Engine
view takes its own symbol (`#ofxSymbol`), every other panel follows the app's instrument select
(`#symbolSelect`) — one engine symbol, so five such panels are **one** change, not five — and the chart
is the only panel with a timeframe control (`#tfSelect`). Values reach those controls through the app's
own change paths (set `.value`, dispatch `change`), and the chip says which kind of thing a group
controls: *"symbol A · ETHUSDT (the app-wide instrument)"* versus *"symbol B · SOLUSDT (this panel)"*.

**The decision is data.** `OFAPLINKS.plan(kind, group, value, members)` returns the rows that would
move — a member of that group on that kind; members of another group and panels that never joined get
nothing — and `controlsOf(rows)` collapses them onto the controls they actually share. That pair is
pure, so the Node self-test pins the gate's rule ("moves every member; non-members unaffected") without
a browser, and the DOM half just executes the plan.

**Two-way, with a guard.** Changing the app's instrument moves every group linked to it; changing a
panel's own select moves only that panel's group. Everything the module itself writes is wrapped in
`state.applying`, so its own change cannot bounce back as user input.

**The chip** (`⇄ A·B`, `⇄ –·–` when independent) sits in every widget's title bar and opens a small
popover: two rows of `– A B C D`, the current choice marked, plus a note naming the group's values and
where they land.

**Measured.** Membership set on a live layout and read back from the store: `Start → [ofx A/, tape A/,
depth B/]`, `Twelve → [ofx B/B, tape A/, depth A/, chart A/A]`. `setGroup('sym','A','ETHUSDT')` moved
the app instrument (`#symbolSelect` and `S.symbol` both ETHUSDT, the app's own handler having run) while
the group-B panel kept BTCUSDT and **the panel that joined nothing stayed independent**;
`setGroup('sym','B','SOLUSDT')` moved only the Engine's own select with no cross-talk;
`setGroup('tf','A','300')` moved `#tfSelect` and `S.tf`. A user-style change of the app instrument
propagated *into* group A (BTCUSDT) and left group B alone. The chip's popover marked
`sym:B · tf:–` for that panel, and picking timeframe group B from it wrote `B/B` through the store,
the chip and the note in one click. All four links survived a reload with their chips
(`ofx ⇄ B·B`, `tape ⇄ A·–`, `depth ⇄ A·–`, `chart ⇄ A·A`). With the engine running, a group symbol
change left ingest untouched: ticks **146 → 266**, engine still `Running`, and the sandbox log holds
**0** `client error:` lines and **0** engine stop/restart calls for the whole phase.

**Two defects found by the gate and fixed:**
1. a value a control cannot hold (an instrument this installation does not list) *cleared* the select —
   `control.value` was assigned before it was checked, so the chart's instrument went blank. The
   control is now put back to what it held, nothing is dispatched, and the refusal is reported
   (`"sym A → NOTLISTED: 1 control(s) refused it"`); a good value applied straight afterwards still works.
2. the chip's timeframe note read `timeframe B ·` with nothing after the dot when the group had no value
   yet; it now shows `—` rather than a dangling separator.

**Also fixed while testing (phase 2 surface):** `activateLayout` accepted an **id** only and failed
silently when handed a name — and the menu shows names. It now resolves an id *or* a unique name
(`resolveLayoutKey`), and a name two layouts share is refused as a guess rather than picked.

---

## 11. Bookmap fold-in (2026-09-15 — the side task, built and verified)

Bookmap was the platform the plan deliberately held at arm's length (phase 6 in §5's table: "after the
licensing read"). This is that read, done against the **installed** Bookmap 7.8.0 build:13 on this
machine plus the vendor's own pages — and then folded into the platform realm beside Sierra Chart.

**What Bookmap actually is, as measured here.** Installed at `C:\Program Files\Bookmap` (bundled jre,
`lib`, `Keys`, `TurboActivate`); build number read from `Bookmap.jar`'s manifest (`BookMap-version:
7.8.0 build:13`) rather than guessed. The add-on API is *in the install*: `bm-l1api.jar`,
`bm-simplified-api-wrapper.jar` (+ javadocs), `bmmp-history-data-library-jvm.jar`,
`api-jvm-0.1.22-alpha.jar`. Its API folders are
`%LOCALAPPDATA%\Bookmap\API\Layer0ApiModules` (data adapters — 3 present, named
`bmMin---bmMax---apiVersion---name---version.jar` with a JSON `.metadata` beside each) and
`…\Layer1ApiModules` (add-ons — empty until one is added by hand).

**The finding that shapes the integration: Bookmap has no market-data-out API and no local server.**
The running instance listens on nothing (only outbound feed connections), and its API is in-process:
the L1 API runs *inside* Bookmap, the L0 API is for pushing data *in*. So the only honest direction is
an add-on:

```
Bookmap + your licence  →  this add-on (Layer 1, read-only)  →  127.0.0.1:8791  →  this suite
```

**What was built on each side of that wire**

| Side | Files | State |
|---|---|---|
| Suite (complete, tested) | `data/bookmap_client.py` — NUL-framed JSON reader + `bookmap_probe()` with the same result shape as the DTC probe (ok/stage/messages/sample/rejects/detail), symbol filtering, unknown-type tolerance, never raises | 9 tests against a mock add-on server; live-verified end-to-end through the UI button |
| Add-on (template) | `data/bookmap_addon/` — `OfapBridge.java` written against the class names and callback signatures taken from the **installed** jars and javadocs (`Layer1SimpleAttachable`, `Layer1StrategyName`, `Layer1ApiVersion`, `CustomModuleAdapter`, `TradeDataListener.onTrade(double,int,TradeInfo)`, `DepthDataListener.onDepth(boolean,int,int)`, `InstrumentInfo.pips`, `TradeInfo.isBidAggressor`), `build.gradle` compiling against `fileTree("C:/Program Files/Bookmap/lib")`, README with the install path and the licence caveats | cannot be compiled here — **no JDK on this machine** (Bookmap ships a JRE). Stated as such in the README, the UI card and the wizard step |

**The integration surface** (`platforms.py`, `api.py`, `ui/platforms.js`): Bookmap is a second row in
`catalogue()` with its own links/plans/caveats/limits; `/api/control/platforms` keeps every Sierra key
where it was and adds `bookmap*` keys; `/platforms/plan` takes `platform: "bookmap"`;
`/platforms/bridge/bookmap` + `…/test` mirror the DTC pair. The Platforms view renders five Bookmap
cards beneath the five Sierra ones. The allow-list now covers both vendors and **one** exception —
`github.com/BookmapAPI/*` — with a path check, so `github.com/someone/else` is refused by name.

**Free access, as published (read 15 September 2026).** Digital is free with an account: crypto depth,
**one instrument at a time**, 1 hour of backfill. Digital+ $19/mo (3 instruments, 3 h backfill),
Global $49/mo ($39 yearly, $990 lifetime; 10 instruments), Global Plus $99/mo ($79 yearly, $1990
lifetime; 20 instruments, the advanced add-ons, trade from chart). **Market data is not included on
any tier** — BookmapData $34–79/mo per exchange/bundle, dxFeed futures $37/mo per exchange, US equities
$34–119/mo, Rithmic $40–101/mo; crypto connections are free.

**Limitations stated where they bite** (on the tier cards, in the wizard, in the caveats list, not
buried): the free tier sees crypto and one instrument only; the API-plugins dialog can be
**licence-gated** (the marketplace's advanced add-ons ship with Global Plus) — if *Add* is locked, no
add-on integration is possible on that licence and the suite says so rather than half-working; the
bridge republishes what the chart streams, so it inherits the licence's backfill rather than more.

**Measured live (sandbox 8099, real install on this machine).** Detection: Sierra `C:\SierraChart`
build 2950 + DTC folder ✓, Bookmap `C:\Program Files\Bookmap` **7.8.0 build:13**, API jars present,
3 L0 adapters, 0 L1 modules; the licence folder is not even listed and a test plants `Keys/licence.key`
and a token-bearing config to prove neither appears in the result. Tier toggle → `globalplus` stored,
the workflow gained its "Activate the tier you chose" step (with the $1990 lifetime on it), two `in use`
badges. Bridge: against a live mock on 8791 the UI line read *"add-on ofap-bookmap-bridge 0.1 on Bookmap
7.8.0 build:13 · licence Digital — hello 1, snapshots 9, trades 9, depth 9, heartbeats 9"*; against a
dead port it said `could not connect to 127.0.0.1:8799` **with the Configure-API-plugins hint**; a
refused link came back as `path not on the allow-list: /someone/else`. Sierra's own DTC card still
reports its own state (test → "Is the DTC server enabled and listening?"), so nothing of phase 0–2
moved. Sandbox log: **0** `client error:` lines; suite **374 passed / 2 skipped** (13 new tests).

**Defect found by the tests and fixed:** the reader counted frames with a singular/plural mismatch
(`trade` never reached the `trades` counter, `snapshot` fell through to `other`), so a live add-on would
have shown "0 trades" while clearly streaming. The frame-type → counter map is now explicit, and
`quote`/`snapshot` deliberately share one bucket.

---

## 12. Phase 4 build log (2026-09-15) — the channel bus

`desktop/ui/bus.js` (new, `window.OFAPBUS`, ~330 lines), `bus.selftest.js` (10 checks),
`test_bus.py` (7 tests), the status-bar field, the shell hook and the audit registration — suite
**388 passed / 2 skipped**, AUDIT CLEAN.

**One channel per (endpoint, params).** A channel is keyed by what actually determines the response —
method, URL and params, order-insensitive, with cache-busters (`ts`, `_`, `cache`, …) dropped — and it
owns **exactly one timer and one in-flight request**. The first subscriber starts it, the last one stops
it, everybody in between gets the same payload on the same tick, and a late subscriber starts from the
payload already on the wire instead of from blank. A slow server is not queued up: a tick that lands
while a request is in flight is counted as skipped and dropped.

**Two ways in.** `OFAPBUS.subscribe({url, params, intervalMs}, fn)` for code that polls;
`OFAPBUS.install(['/api/atlas/'])` to wrap the global fetch for chosen prefixes, which then coalesces
concurrent identical GETs, counts everything and hands back a real `Response` — everything unmatched
passes through untouched, and with no prefixes installed the wrapper is not installed at all.
`request()` gives the same sharing to one-shot GETs.

**The measurement (real HTTP, real endpoint, real server log).** Twelve subscribers on
`/api/atlas/klines/BTCUSDT` at 1 s: **one channel, one immediate fetch, then one per second — 6 fetches
in 5.6 s and 72 deliveries (12 × 6)**. Unsubscribing all twelve: `channels: 0`, `bus: idle`, and the
server log stops. Three symbols × four widgets: **three channels, three immediate fetches, 15 fetches in
4.3 s — 5 per symbol**, which is one per channel per interval and would have been 17 each if it were per
widget. `install(['/api/atlas/'])` with twelve concurrent identical GETs: **1 request, 11 coalesced, 92 %
saved**. The server's own access log agrees with the telemetry: 5 / 5 / 5 for the three symbols (plus the
first run's 6 and one coalesced call). 0 `client error:` lines.

**What the phase does NOT do, said plainly:** the panels are not yet routed through the bus. The plan's
gate was the bus's own arithmetic ("twelve same-symbol widgets produce one fetch per interval; three
different symbols produce three"), and that is what was built and measured — a delivery layer, its
telemetry and an opt-in wrapper. Adopting it per panel is a per-panel change (each view's poll loop
becomes a `subscribe`), and that is the honest next step rather than something this phase silently did.

**Defect caught by the self-test:** a `Math.max(100, intervalMs)` floor (sane for a UI) against a 30 ms
test interval made the timer arithmetic untestable at that speed; the floor is now pinned as a rule
("a UI is not a benchmark") and the self-test runs at and above it. The flaky-transport check was also
rewritten after it turned out to be asserting against a stubbed `window.fetch` the module never looks at
— the injected transport is the seam, and the test now fails and heals *that*.

## 12a. The bridge jar now ships with the app (follow-up to §11)

A fresh user should not need a JDK to use the Bookmap integration. `scripts/build_exe.py` now adds
`orderflow_system/data/bookmap_addon` to the PyInstaller data list (beside the web UI, guarded — a
missing folder prints a warning rather than failing the build), so the jar and its source travel inside
`dist/OrderFlowAnalysisPro/_internal/`.

The suite then tells the truth about it: `platforms.bridge_jar()` finds the shipped jar and reads its
**class-file major version** (no guessing from the name), `_bookmap_runtime()` reads the local Bookmap's
own `jre/release`, and `bookmap_bridge_state()` **compares the two** — Java 25 jar vs Temurin 25.0.2
runtime is "it will load as-is"; a mismatch says which Bookmap to rebuild against. The card shows the
line, the path and a **"Show the jar"** button (`POST /platforms/bridge/bookmap/jar/open`, which
`reveal_bridge_jar()` refuses to point anywhere but the app's own add-on folder), and the wizard step
now reads *"Add the bridge add-on (once) — no compiler needed"* instead of asking the user to build.

Verified live: the card reads *Add-on jar: shipped with this app · built for Java 25 · your Bookmap runs
25.0.2* with the note *"the jar is built for Java 25 and your Bookmap runs 25.0.2 — it will load as-is."*;
a fake install pointed at Java 17 produces the rebuild warning instead; 7 new tests cover the jar's
presence, the class-version reader, the build list, the comparison (match / mismatch / unknown) and the
refusal.

---

## 13. Phase 4b — the bus adopted app-wide (and one hazard found doing it)

`desktop/ui/ui.js` now opts the app into the delivery layer, without touching a single panel:

* `pollStatus()` asks the bus for `/api/control/engine/status` (`OFAPBUS.request`, in-flight shared)
  and falls back to its own `api()` call when no bus is loaded;
* at boot the app installs the fetch wrapper for the read-only endpoints that panels poll —
  `/api/control/engine/status`, `/api/status`, `/api/atlas/`, `/api/instruments` — so a GET that
  another request is already in flight for is answered from that one request.

The wrapper's semantics were tightened for this: **every caller gets its own Response**, rebuilt from
the one body that was read, with the **real status and statusText kept** (a 503 stays a 503, not a
rebuilt 200), and a body that is not JSON is handed back as the real response, unshared. `bus.selftest.js`
grew that check (11 ok).

**Honest note on where the win is:** this suite shows ONE instance of each view — terminal mode
re-parents the same section rather than cloning it — so a twelve-widget board is twelve *different*
endpoints, not twelve identical requests. The wrapper's dedupe pays off where panels ask for the same
dataset (atlas surfaces on one symbol, the status poll, the instrument list), which is exactly the
prefix list above. The channel API (`subscribe`) is what a panel should use when it wants a shared
poll of its own; adopting that per panel remains open and is a per-panel change.

**Hazard found the hard way:** the two new panel modules (`watchlist.js`, `news.js`) were wired into
`index.html` as script tags *before their files existed* — and this app's module loader treats a script
that fails to load as fatal: it renders its "module error" banner and replaces the shell, so the whole
UI came up empty (`views: 0`) rather than degrading. Nothing was wrong with the bus adoption; the tree
was simply wired ahead of the files. **Rule: land a module file first, wire its script tag second.**

## 14. Phase 5 — the new widgets (in progress, as parallel workstreams)

Four widgets are planned (Watchlist, News, Fundamentals, Options). Two are being built now as
parallel workstreams, each creating only its own three files (module, Node self-test, Python gate) on a
contract already wired into `index.html`:

* **Watchlist** — rows for the install's enabled instruments, quotes from the real `/api/status`
  payload, the app's active symbol first, polling through the bus so the panel shares one channel;
* **News** — headlines for the active symbol from the app's own context endpoint, grounded on the
  response shape the code actually returns, with an honest "no news source configured" state (the
  config key that supplies the feed is named on the panel) rather than placeholder headlines.

**Fundamentals and Options are deliberately not started**, and that is the plan's own position on
them (§2): fundamentals needs a fundamentals source, and Greeks/IV need a real options feed (dxFeed
class) — both are data-and-billing decisions, not rendering ones. Building the panels without the
decision would produce two panels that can only ever say "no feed configured"; the honest move is to
ask which source first.


## 15. Decisions on the last two widgets (approved 2026-09-15)

Both panels are keyless, cost nothing, and were verified from this machine before the decision — the
same discipline as the Bookmap read: test the candidate, then choose.

| Panel | Source (chosen) | Why | Live evidence taken before building |
|---|---|---|---|
| **Options** | **Deribit public API** (crypto only) | The suite's board is crypto-first (BTC/ETH/SOL, bybit feed); Deribit returns the chain *and* the Greeks inline, needs no account, and covers exactly those instruments | 896 live BTC options across multiple expiries, 476 ms; `BTC-16SEP26-68000-C` with `mark_iv` plus `delta, gamma, theta, vega, rho` |
| **Fundamentals (crypto rows)** | **CoinGecko** (keyless) | Rank, market cap, supply and 24 h change are what "fundamentals" means for these instruments | BTC rank 1 · $1 546 B · −1.05 %; ETH rank 2 · $302 B; SOL rank 7 · $59 B, 276 ms |
| **Fundamentals (US filers)** | **SEC EDGAR** (keyless) | Primary source, not a reseller; real filed numbers (revenue, net income, diluted EPS, assets, equity) each tagged with form · filed · period; covers the US names already arriving over the dxFeed/Alpaca path | `company_tickers.json` 214 KB in ~130 ms; a sloppy User-Agent gets **403**, a declared one (`App-Name/x.y (contact)`) gets 200 — so the module declares one |

**Declined, with reasons on file:** an aggregator key (Finnhub / Alpha Vantage / FMP) — the free tiers are
the catch for a polling panel (Alpha Vantage ≈25 calls/day, FMP ≈250/day, Finnhub ≈60/min), which would
mean quota-aware backoff and a "showing cached data" state the keyless sources never need. Coverage was not
worth those failure modes. Equity/index options via a paid feed (dxFeed class) also declined for now: the
Options panel ships with an explicit "crypto only via Deribit — no options feed for <SYMBOL>" state instead
of a stub, so the honest answer is on screen rather than implied.

**Non-US issuers, indices and FX have no fundamentals source** by design, and the panel says so per row.
That is the whole reason the state exists rather than a placeholder number.
