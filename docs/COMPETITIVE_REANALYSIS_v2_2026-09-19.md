# ModFlow OrderFlow Analysis Suite — Competitive Reanalysis v2

> **Executed same day (§124, §125):** §7 items 1–6, 10 and 12 are built, tested and live-verified; item 11's resets/ladder grammar verified as already shipped; items 7 (tips), 9 (provenance counter) and 11b (range-to-table) are built and live-verified (§125), together with the rebuild and its packaging receipts; 13's commit/publish stays on his word. Receipts: SESSION_HANDOFF §124, §125.

**Prepared for:** Moddy (OrderFlow-Analysis-Pro)
**Date:** 19 September 2026 — second pass, run against the build as it stands
**Supersedes:** `docs/COMPETITIVE_REANALYSIS_2026-09-19.md` (first pass, 07:38). The first pass's ModFlow section was written from the static inventory (`docs/ux-study/modflow_inventory.md`), not the tree, so several of its headline gaps were already shipped when it was read; its corrections ledger lives in `docs/COMPETITIVE_AUDIT_DIFF.md`. This pass re-derives every ModFlow claim from the live tree.
**Scope:** Quantower · Bookmap · NinjaTrader 8 · MetaTrader 5 · Sierra Chart · ATAS — how the programs function (layout · interaction · GUI · technical advantages · product features), compared against ModFlow in all metrics, plus the market-norms model and the improvement set that follows.
**Baseline (the tree the owner runs):** `git rev-parse HEAD` = `797eea0` **plus** the uncommitted worktree (§119–§125: the list.txt pass, the liquidity-map audits §120–§122, the wizard/help audit §123, the staged fixes §124, the last staged three + the rebuild §125). The packaged artifacts in `dist/` were rebuilt at §125 (2026-09-19 16:03) over the §119–§125 tree — `dist/BUILD_INFO.json` records the commit and the dirty state, and the handoff carries the receipts.
**Method:** every ModFlow claim carries a receipt (file, test name, or counted grep) taken from the tree this date. Competitor claims trace to the six sourced briefs in `docs/ux-study/` (compiled 2026-09-18 from vendor docs, help centres and community posts, each claim carrying its source URL); this date they were re-mined into six digests, checked in at `docs/ux-study/digests-2026-09-19/`. Nothing was read from memory, and no code was changed in this pass — it is an audit and a plan, like the passes before it.

---

## 0. Why a second pass — and what changed since the first

1. **The first report misread the build.** It scored "single frame, no way to save a screen setup" against a tree that already had terminal layouts, link groups A–D and the shortcut registry; and it called cross-view symbol sync missing when the terminal board had carried it for days. Cause named in the diff: the static inventory was read instead of the tree. **Law for future passes: read the tree.**
2. **Since the diff (08:47), commit `42ec6a2` landed** the profiles store (§116), the competitive-audit response (§117: per-view pause completed for the live-data four, user-rebindable shortcuts with conflict refusal, study collections, the identity copy) and the paper desk (§118: Trade DOM ladder, chart strip, bracket editing after entry, the session ledger + CSV).
3. **Then the uncommitted §119–§123 work:** his list.txt pass (§119 — one menu hide, the heatmap panel's way back, the "← Back to X" context chip), the liquidity-map audits (§120 click/box/wheel end-to-end; §121 — the real zoom fix: the intent gate was deferring repaints behind a 900 ms wheel lease; the server time anchor `until=`; the full Bookmap-grade grammar; §122 — the colour ceiling measured (×1.84 drift) and leashed to 5%/min, the Detail control 100 ms–5 s applied live), and the wizard/help audit (§123 — overlay keyboard grammar, truthful close, dead clicks closed, Centre doors, seven menu rows promoted; `test_guide.py` gates the layer).
4. **So this pass:** re-derive ModFlow from the tree (Section 3), re-score every dimension (Section 4), re-test the market-norms model (Section 5), and rebuild the improvement list from what remains — internal audit receipts plus what the field still offers that ModFlow doesn't (Sections 6–8).

---

## 1. Executive summary

**Where the build stands: the analytics-layer mandate is essentially complete.** Every "gap" the first pass named as Phase A/B/D is shipped or exceeded: saved layouts with lock, versions and a master window list; profiles over 13 config blocks; link groups that carry symbol and timeframe; a rebindable conflict-refusing shortcut registry with an armed gate; study collections; per-view pause on all live-data surfaces; a heatmap whose craft (cursor-anchored zoom, leashed ceiling, percentile/exact cut-offs, dim + large-size highlight, global apply, a time anchor and a 100 ms–5 s live-applied Detail control) is now the closest thing outside Bookmap's own canvas; a paper desk with a ladder, brackets, a locked-armed safety grammar and an order-recording ledger; an 83-topic Help Centre with per-panel doors, a wizard (12 express + 10 professional) and a Guide; and the identity copy that finally says out loud what the product is — *the analytics layer beside your terminal*, with the market's own data-billing language.

**What genuinely remains, in order of importance:**

1. **Small internal truths the audits caught (fix these first — they are cheap and they are ours):** Trackers advertises reads it doesn't fetch while five live routes sit dark (F1); the three server-made CSV exports have no Tools ▸ Export submenu (F2); `storage/prune` has no button (F3); the control-surface audit's F-1–F-7 (frameSelect can't pick the delta family; the Settings source dropdown is stale vs the venue matrix; the registry offers an `imbalance_mode` the store silently drops; bounds drift in up to three places; "candles" listed twice; hover-help option keys that never match; calendar filters that don't persist); eight honest-but-open menu stubs.
2. **Release hygiene:** dist/zip/SBOM/installer rebuilt over the §119–§125 tree (§125: Setup `5B8BF8B4…`, zip `917a48b2…`, SBOM `eb51942b…`, dist exe `b2eb32d8…`; frozen smoke 18/18, Setup journey 17/17); commit/publish on the owner's word (drafts first, standing gate).
3. **Field-derived refinements the study still supports (small, high-polish):** a Show-Original-Values diff in the staged settings surface; MT5-style novelty-gated tips as a third onboarding layer; per-symbol data-provenance depth for the MT5/bridged feeds (turn MT5's own wound into a feature); on the paper ladder — a held-modifier override with a cursor tooltip (ATAS grammar) and interval auto-centre; Bookmap-style per-column reset modes and a range-to-table events list; size-formula quick buttons and the preset+custom combobox pattern across the 19 controls already listed.
4. **The two deliberate open gates:** real broker execution (no real order path exists anywhere — keep it that way until it can ship as one complete, gated mode with the credential story answered), and cross-platform (Windows-only today; Bookmap and MT5 own that flank).

**Recommendation: ship the analytics layer — it already beats the field on the axes it chose — with item 1 closed as the next wave and item 2 run when the owner says go.** The paper desk is the correct boundary for now: it gives the market's practice loop without inviting execution expectations ModFlow doesn't yet back.

---

## 2. The field, platform by platform

*Evidence base: the six digests in `docs/ux-study/digests-2026-09-19/` (each claim there traces to a source URL in the original briefs). Amounts as published; no currency symbol is served by some vendors.*

### 2.1 Quantower

**What it is.** Windows-only (.NET) broker-agnostic terminal, order-flow heavy, 60+ connections claimed; install is a folder extract (no AppData/registry writes) — portable by construction. Pricing (18 Sep 2026): Free (1 connection, 2 indicators/chart, no registration) · All-in-One monthly 70 (189/336/588 for 3/6/12 mo) · Lifetime 1690; market data billed separately.

**How it functions.** Its differentiator, users say, is layout: **every panel is a real OS window** ("window management is simply superb"), and persistence is a four-layer nesting — Workspace (XML, autosave, **Lock** disabling add/remove/move/resize) ⊃ Bind ("super-panel" rectangle-selection that resizes as one unit) ⊃ Group (tabs) ⊃ Panel (Template + Set as Default). Right-click is universal (panel corner menus end with a **Help deep-link** to that panel's docs). Hotkeys are parameterised ("open template", "pre-configured order"), scoped focused-vs-global, and trading keys require an **"Enable Keyboard Trading"** arm. Trust is shown visually: latency threshold with a market-data-delay message, status dots, trading locks. Themes are colour-variable driven (switching one resets in-panel colours — only Set-as-Default or a Template survives).

**Standout assets.** The OS-window panel model with snapping; Templates + Set as Default ("all the order flow tools are already configured… complex things you can do in 30 seconds"), templates as **sharable files**; DOM Trader composable columns (liquidity changes = pulling/stacking, change counts, imbalance); Market Replay + Trading Simulator (paid tier).

**Where it hurts (documented).** Runtime trust, not features: 20-second delays scaling with window count; memory ~2 GB → "over 7 GB after several days"; a failed exit that "blew a prop account"; state that doesn't stick; a layout-breaking release (1.146.13) with no compatibility path; settings sprawl ("100 different graphical features that you can set the color on"); **no command or settings search anywhere** ("you'll often have to Google how to configure something").

**Take / avoid.** Take: per-panel Help deep-links (have it), layout Lock (have it), armed hotkeys (have it), latency/status badges (have the delayed-data badge), link colour on the frame (have groups + letters), Set-as-default + factory reset (have it via per-view defaults), instrument lookup as a designed screen (have `Ctrl+F` finder + engine lookup), notifications inbox with persistent history (have the Inbox). Avoid: the bind/group gesture hierarchy itself (high blast radius in a single-window app — 1.146.13 is the cost of layout change without a compatibility story; ModFlow's per-screen layouts + versions + lock is the lighter, safer cut), and entitlement-gated basics.

### 2.2 Bookmap

**What it is.** The heatmap-first visualisation platform (Java/OpenGL), Win/mac/Linux; tiers Digital (free) → Digital+ $19 → Global $49 → Global+ $99 monthly (lifetime 990/1990), symbols capped 1/3/10/20; **data billed separately** (BookmapData $34–79; dxFeed/Rithmic per-exchange); heavy end wants 32 GB/i9.

**How it functions.** One main window; instruments as tabs; the heatmap is the spine, everything else is rails (right-side per-price Columns: order book, session/chart-range profile, counters, quote delta, T&S, DOM, notes). The **canvas grammar is the craft**: wheel zoom **anchored to the cursor**, axis-drag zoom, Ctrl+Z back-out, **hold-D drag mode** with 1 px / Shift 10 px arrow nudge, anti-flicker hysteresis (`Reappear = Hide × (1+Factor)`), vertical smoothing Auto/Manual/None, hover-to-number everywhere **mirrored in a persistent Information Bar**. Ramp: percentile **or** exact cut-offs, auto-contrast (re-adjustable), dimming, large-size highlight, **apply colour scheme globally**. `.bmw` workspaces store layout + settings + instruments, double-click launch, share-by-link; detached windows return home on close. **Estimated depth is labelled as estimation** — the highest-integrity pattern in the study.

**Standout assets.** 40 FPS depth at nanosecond updates ("industry leader for the best heatmap"); replay + simulator (records orders, 3 run modes); master-slave cross-chart sync; ~3 dozen add-ons; the columns rail with per-column reset modes (Manual/Scheduled/Conditional/double-click); a range-to-table events list.

**Where it hurts.** Steep curve and overload ("like handing someone a cockpit"; community advice: "Disable everything except the heatmap and volume dots"); resource heaviness; cost stacking ("best features… only at the highest tier"); entitlement-gated history (1 h vs 24 h scroll-back by tier); look-and-feel minority reports; detached-window fragility history.

**Take / avoid.** Take: the full canvas vocabulary (ModFlow's §120–§122 pass already carries wheel/cursor anchoring, pan, arrows, Home, box clear + export, dim/highlight, percentile/exact, global apply, smoothing, a live chip — verified in the tree); the synthetic/estimated labelling discipline (ModFlow labels inferred icebergs/sweeps/stop-runs "(inferred)" — keep it, extend where new analytics arrive); per-column reset modes and the range-to-table events list (small, open); one-click minimal/focus per surface (ModFlow has zen + minimal). Avoid: density-by-default, entitlement-gated time travel, scattered settings.

### 2.3 NinjaTrader 8

**What it is.** Windows (.NET/WPF) + Web/Mobile execution platform: Free (0.39/1.29 per side), Monthly $99, Lifetime $1,499; Order Flow+, Market Replay and Pulse need a **funded live account**. Login required.

**How it functions.** Control Center is the always-on shell; **every surface is an independent OS window**; New is a flat catalogue of ~20 window constructors. Workspaces = saved arrangements, **one visible at a time**, with 10 prior versions retained (Tools → Database Management → Restore) and import/export. Context-valid right-click: "available order types… limited to those which will be accepted by a brokerage, based on the side of the market on which you right click". **Freeze-on-hover** on the dynamic ladder (suspends updates, pins the top row). Ladder grammar is deliberately graded (left=limit, Ctrl+left=MIT, middle=stop-limit; modify is two-step "to eliminate… dropping an order on the wrong price"). The **Hot Keys window** (categories by active window + Global, conflict detection, printable) is the reference standard. **Dynamic title tokens** (`@INSTRUMENT`, `@PERIOD`, …) let surfaces self-label from live state. Safe Mode = hold Ctrl at launch.

**Standout assets.** ATM strategies as reusable bracket rule sets (one dropdown, iconography marking an active instance); Global Simulation Mode gate with sim surfaces painted; workspace version history; colour-coded linking + Link All; curated starter workspaces (8.1.7).

**Where it hurts.** Modal-heavy flows ("everything requires a modal dialog… slows you down"); the facelift critique ("all they need to do is give it a facelift… how about an in-built trade analysis tool"); performance creep (workspace load >3 min in 8.1.7 vs <1 min in 8.0.x); freezes/crashes reports; regressions shipped beside features.

**Take / avoid.** Take: title tokens (ModFlow's watermarks + widget `titleToken` cover it), context-valid menus (T6/A8 shipped), freeze-on-hover (shipped, §97/A7), layered destructive-action depth (ModFlow's armed gate + lock + explicit confirmations is the safer cousin), collapsed panels that keep function, semantic colour **plus** label (the CVD rule — already law here), link colours + Link All (have groups), workspace version history (have layouts versions). Avoid: account/server coupling, add-on liability, the one-visible-workspace restriction.

### 2.4 MetaTrader 5

**What it is.** The distribution play: the desktop is free at point of use because the broker side pays (licences tier by account capacity; Market, Signals and an in-terminal VPS are the in-platform upsells). Windows-first but on mac/Linux/web/mobile. The vendor itself admits the UX debt: Build 5800 (Apr 2026) "started a comprehensive redesign of the trading dialog to make it more intuitive and functional".

**How it functions.** Dense compound shell — main menu (almost all commands), three duplicated toolbars, Market Watch left, Navigator tree, chart area with a **chart switch bar** (up to 100 charts), one Toolbox window at the bottom (positions/news/history/alerts/logs/journals), status bar carrying **the active template and profile names — always visible**. Persistence splits **profiles (the open-chart set) from templates (chart appearance)**, cycled by Ctrl+F5/Shift+F5. Interaction: **position-aware menus** (above the price you can place Sell Limit/Buy Stop; below, Buy Limit/Sell Stop — stop distance pre-validated before the command appears); **drag-to-set SL/TP with a live tooltip of the P/L in deposit currency and pips**; zero-confirmation closes/deletes (undo exists for chart objects only); **user hotkeys silently outrank platform defaults**. The best onboarding idea in the whole study: **>100 interactive tips that fire only for actions the user has never performed — each tip a launcher into the real UI.**

**Where it hurts.** Its two chronic visual failures map straight to code: **no in-app font scaling** (the most-cited visual failure; a decade of HiDPI patch notes; custom in-chart panels documented as not scaling) and dense small fixed text. Beginners stall ("half an hour just trying to figure out how to see the chart"); provenance is never shown ("missing candles…", "not confident the data is up to date"); the broker feed is usually to blame but MT5 wears it.

**Take / avoid.** Take: global UI scale (**already shipped here — `UI scale` input `setScale`, 0.75–1.5, `--ui-scale` + canvas DPI via `scale.js`; verify it stays enforced on monitor moves**), position-aware menus as a pattern for the paper ladder, consequence-preview tooltips when paper drag arrives, profiles + templates as separate concepts (Profiles vs per-view defaults — have it), the always-visible active-profile name (consider surfacing in the status bar), per-symbol data-provenance depth (see §6 — MT5's wound, and ModFlow ingests MT5 read-only, so a provenance chip converts a competitor's weakness into a feature here), and novelty-gated tips as a light third onboarding layer over the Centre + wizard + Guide. Avoid: zero-confirm destructive actions (ModFlow's armed/locked grammar is deliberately the opposite), broker-anchored shells, and duplicated main menus.

### 2.5 Sierra Chart

**What it is.** The anti-Bloomberg power tool: dense, fast, deliberately unattractive; monthly packages only (26–56 USD, no perpetual ever; external feeds gated behind Integrated tiers); in business since 1996.

**How it functions.** The abstraction is the **Chartbook, not the window** — a chartbook "is not a window… a collection of multiple windows", **only one visible per instance** (multi-monitor = extra instances; chartbooks cannot be detached). The Window menu is the manager (Cascade/Tile/Always on Top/Detach…), and the failure modes are documented in the brief: an unreachable title-bar-less window on monitor 2; "I tried to reattach it for 10mins now. It's simply impossible"; recovery via the CW menu → Cascade → Maximize. **Menus are the API**: every menu line prints its shortcut; menus are user-editable; a chart's right-click menu holds only what the user added. The **settings-panel grammar is the most copyable asset in the study**: modeless panels that never block the chart; per-field **A (accept) / C (revert field)**; panel-level **OK / Cancel / Revert All / Apply All**; **View ▸ Show Original Values** (a diff of pre-change values); and **tokenised in-panel search** ("Mas Mod" → "Master Mode"). Analysis units are **instances, not types** (the same study twice, tuned independently); **Study Collections** let configs travel; chartbooks are portable files users mail each other.

**Where it hurts.** Dated UI ("Old Design"); settings overwhelm and no global study search; **window traps** (the archetypal support threads); scope confusion — the "small axis text" thread whose fix was "didn't realise there are 2 types of graphic settings"; hundreds-entry per-object colour tables; support tone.

**Take / avoid.** Take: modeless settings with per-field accept/revert (**ModFlow has staging with Apply/Revert — the open nicety is the Show-Original-Values diff view**), explicit labelled scopes with copy-to/from-global (ModFlow's scoped params + "apply globally" dials are the analogue — consider one explicit scope label in the scope editor), error states naming a help topic (ModFlow's blank states already carry `data-helptopic` doors — extend to runtime error toasts), the window-recovery kit (**already built: master window list, reset position, layout versions, safe start — this is precisely the capability Sierra's threads say users lose weeks to**), and numbered citable docs habit. Avoid: menu-as-API without the docs infrastructure, title-less windows, per-object colour tables, multi-instance architecture.

### 2.6 ATAS

**What it is.** The all-in-one paid order-flow platform: footprint/Smart DOM/Smart Tape/volume profile/heatmap (Vulkan)/replay/options board on **your own feed** ("you must connect to a data provider"); START €0 (replay gated off) / PLUS €24.95 / PRO €69.95 / ULTRA €89.95 per month; 14-day trial card-gated; ATAS X beta adds macOS.

**How it functions.** **Real docking** — modules drag-merge into one window with quadrant drops and centre-drop collapsing to a tab; two-tier persistence (workspaces = layers of windows with an **Edit** mode that repairs an overloaded workspace without opening it; layouts = instrument groupings with a **Universal** layer) plus module templates (Set as Default, Export) and a Recommended Templates Gallery. Symbol sync by **colour group** — one selector, same-colour windows switch together. The **order-entry safety grammar is its best export**: One-Click Mode as a master switch mirrored as a visible **Lock**; type from column+level ("below market in Bids ⇒ Buy Limit; above ⇒ Buy Stop"; best ask ⇒ Buy Market); **held-modifier override** (hold the Stop-Orders-Mode key, default `V`, while clicking the ladder) with a **cursor tooltip stating the operation before it fires**; a fixed **Flatten/Reverse danger strip**; conflict-warned hotkeys in five sections. Visual system: **data-semantic colour schemes** (Delta, Volume/Trades/Proportion, Heatmap by Volume/Trades/Delta) tuned by **Upper Cut-off % + Contrast**; density knobs on every surface (row heights, fonts, digits, "12k" abbreviations, max candles/levels trade history vs memory); **zoom-level degradation** (footprint auto-switches to candles when zoomed out — disableable). Honest documentation: the Queue emulator disclaimer; "alerts will not trigger if ATAS is closed". **The colour-blind gap is real and uncontested**: KB search for "colorblind" returns nothing.

**Where it hurts.** Not the UI — feeds, price and support: "Feeds are an issue…"; ATAS X stability ("heatmap so buggy"); "Windows 95 nightmare" clutter; bloat ("90% are useless"); **silent-truth traps** (POC differing between chart and DOM because of different price scales; the daily profile shifting intraday); templates as a switching cost.

**Take / avoid.** Take: the locked danger strip (ModFlow's paper ticket already mirrors it — Lock trading, flatten/cancel always live), the **held-modifier + cursor-tooltip grammar for the paper ladder** (open — see §6), **auto-centre with interval/speed and double-click centring** on the ladder, density knobs everywhere (ModFlow's density select + per-surface settings — extend if a legibility complaint ever lands), **zoom-level degradation** (**already present on the Engine — the degrade mode uses candles**; extend the habit if dense text surfaces need it), semantic colour + label redundancy (already law here — the CVD rule), replay tiers honesty (ModFlow labels its replay's simulated account plainly), one triggered-alert log (have the Inbox). Also hold the line on the flank ATAS leaves open: **ModFlow ships colour-blind-aware palettes; none of the six competitors documents one.** Avoid: per-surface-only theming without global scale (the MT5 wound), silent POC shifts (ModFlow's explain cards + definitional labels are the countermeasure — keep them honest as new reads land).

---

## 3. ModFlow as it stands (live tree, 2026-09-19)

**Platform & architecture.** A single-window desktop app — pywebview/WebView2 shell over a FastAPI + SQLite backend, vanilla-JS UI with no bundler (70 UI modules + 38 node selftests; 25 desktop Python modules). Windows-only. Open-source, local-first, keyless by default. A terminal mode turns the same panels into native widget windows; `--safe` starts without restoring them; headless mode and CLI exist for scripted runs.

**Navigation & layout — the part the first report called "single frame, nothing to save". What actually ships:**
- Classic mode: a 31-entry rail (three more injected at runtime — Scanner, Help Centre, Guide), an 11-menu top bar (File · View · Layout · Drawings · Chart · Data · Profiles · Run · Keys · Tools · Help), a command palette, a status bar.
- Terminal mode (Ctrl+Alt+T): panels become widgets with tabs; **named layouts** in the config store (`layouts`: mode/active/items/versions — `test_layouts.py`), **per-screen layouts** keyed by `screen_key` (`test_display_geometry.py`), a **layout lock** (`ui.layout_lock`; move/resize/add/remove/reorder all gated, status-chip shown — `test_layout_lock.py`), and **per-layout version rings** (10 retained; restore in one click; a deleted layout's version survives on purpose — `test_layout_versions.py`).
- Window trust: a master **Windows & layouts…** dialog (screens; every window open/closed; Focus / Pin / Reset position / Close / Remove; close-all) over `POST /api/control/windows`, whose `reset` action drops geometry and re-places on the primary screen — the in-app rescue for the field-wide "the window became unreachable" failure class (`test_windowing_ui.py`, `test_aux_windows.py`).
- Persistence stack: terminal layouts + **profiles** (named playbooks over 13 config blocks — `PROFILE_BLOCKS`: data_source, instruments, atlas, ofx, studies, expression, ui, layouts, workspaces, watchlist, risk, audio, calendar; credentials and machine paths excluded by construction) + per-view **workspaces** + the **template gallery** + per-view "remember my settings" defaults.
- Settings discovery: 12 Settings cards including **"Find a setting"** (search + staged edits with Apply/Revert) — the Sierra-style modeless-searchable lesson, applied.

**Interaction.**
- The **shortcut registry** (`keys.js`): one map, scopes + priorities + per-binding gates + typing guard; at source level **39 dispatchable bindings + 6 documented rows across 15 modules**; the `?` sheet renders from the map and offers **Change / Reset / Reset all** with conflict refusal naming every owner; overrides persist (`ui.keys` block; the sanitiser rebuilds, so a reset really removes).
- **Armed order keys**: danger-marked bindings cannot dispatch until armed (visible session switch, status badge, Keys-menu toggle); a disarmed press explains itself.
- Per-panel help: a `?` injected into every panel head; **F1 answers for the panel in focus**; blank/error states link into the Centre (`data-helptopic`).
- Mouse grammar on the liquidity map (§120–§122): cursor-anchored wheel zoom, shift+wheel / gutter wheel for rows, middle/shift-drag pan, arrow-pan (shift ×10), Home = live, click-off clears a box, box export, live chip. Deliberate gestures **force** past the intent gate — the 900 ms wheel lease that silently ate zoom commands was found and fixed in §121.
- Anti-seizure craft: freeze-on-hover, watermark titles (instrument · view · mode), the delayed-data badge that judges only on-screen panels.

**The heatmap / depth suite (the direct Bookmap competitor).**
- Named schemes (Balanced / Wall hunt / Thin-book / Quiet book / custom), ceiling as percentile **or** exact, floor, contrast gamma, vertical smoothing, **dimming** and **large-size highlight** on both heat surfaces, **apply globally** across surfaces (all registered params; `test_b2_ramps.py`).
- A **leashed colour ceiling**: the percentile stays the target, the applied ceiling walks 25% of the gap per build capped at 5%/min (measured ×1.84/4 min drift → ×1.18 smooth); an explicit pin applies instantly (`test_heatmap_scale.py`).
- **Time anchor + deep zoom**: `until=` slicing server-side, buckets 100 ms–5 s applied **live** to the running hub (the Detail control), windows 6 s … 75 min (extendable via `max_columns`), rows 60–400; `heatview.js` viewport maths pinned by 31 selftest checks + `test_heatview.py` / `test_heatmap_anchor.py`.

**Order-flow analytics breadth.** Footprint (imbalance modes, stacked), CVD + divergences, TPO/Profile incl. the **area profile** (box any region → POC/VAH/VAL + "Watch this level" → radar), Frames (six families incl. delta bars), Depth ladder, Tape (freshness chips), 8 tracker cards, the **level radar** (armed → approaching → defended → confirmed → spent/failed, across the watchlist), unfinished business + node persistence, VWAP bands, signals, strategy, performance, journal (statistics + broker-style statement), replay, alerts (rules + Inbox + Telegram/ntfy/email + sounds).

**The paper desk (terminal mode's safe half, §118).** A Trade DOM ladder (print-centred, click grammar, cancel chips), the chart strip (quick-fire from Chart), bracket **editing after entry** (`paper.set_exits()`), the session **ledger** (start/submit/reject/fill/cancel/exits/end with tape + wall clocks) with CSV export, **Lock trading** (`ui.paper_lock`), and one `submit()` door gating on armed + unlocked; flatten/cancel stay live while locked. **Broker execution is deliberately absent** — no real order path exists anywhere, and the audit's warning against a half-built execution stack stands.

**Help / wizard / onboarding.** Help Centre (83 topics; search + autofill; Simple/Advanced gate; dock + FAB), the Guide view, the setup wizard (12 express = 9 static + 3 runtime splices; +10 professional), inline walkthrough cards each carrying "Open in the Help Centre →", overlay keyboard grammar (Esc through the overlay's own close; Enter advances; Tab trapped; focus rides in), truthful ✕ copy, visited-dot navigation, seven menu rows promoted from "planned" to real doors (§123). The layer is gated by `test_guide.py` — door targets must be real views; inline ids must have Centre continuations.

**Data & feeds.** Exchange feeds (Bybit, Binance, OKX, Hyperliquid), MetaTrader 5, Alpaca (keyless equities lane), NinjaTrader (`ModFlowBridge.dll`), Bookmap (`OfapBridge.java`), Quantower DTC — adapters for every competitor in this report as data sources. News/calendar (Forex Factory), SEC EDGAR fundamentals, CoinGecko, Deribit options. The identity copy speaks the market's own language: "what a broker or exchange charges for its own data is between you and them" (`start.identity`, §117).

**Quality gates at §123.** pytest **1,631 passed / 3 skipped / 0 failed** (1,634 collected); **38/38 node selftests**; `audit_ui_refs.py` CLEAN; ruff clean at the CI pin. The visible surface counts: 31+3 views; 41 `<select>` + 93 id'd inputs (inventoried by the control-surface audit); 83 help topics; 45 registry rows.

---

## 4. Head-to-head matrix (live-tree columns)

| Capability | ModFlow (today) | Quantower | Bookmap | NinjaTrader 8 | MT5 | Sierra Chart | ATAS |
|---|---|---|---|---|---|---|---|
| **Platform** | Win (pywebview; widgets as native windows; headless/CLI) | Win (.NET) | Win/mac/Linux (Java) | Win + Web/Mobile | Win/mac/Linux/web/mobile | Win (native) | Win (+macOS beta) |
| **Cost to trader** | Free · open-source · keyless · no account | Free tier → 70/mo · lifetime 1690 | Digital free → $99/mo · lifetime 1990 · symbols capped | Free → $99/mo · $1,499 lifetime (+funding for Order Flow+) | Free (broker-distributed) | 26–56/mo, no perpetual | START €0 → €89.95/mo |
| **Order-flow spine** | heatmap + footprint + CVD + TPO + area profile + depth + tape + trackers + **level radar** | DOM Surface + footprint + profile + DOM Trader | heatmap-first + columns rail | footprint + cum delta + profile + DOM | 3rd-party only | DOM + footprint + profile (dense) | footprint + Smart DOM/Tape + profile + heatmap |
| **Order execution** | **paper only** — Trade DOM + chart strip, armed + lock, exits editing, ledger; no broker path (deliberate) | full | full (chart clicks, brackets) | full (Chart Trader/SuperDOM/ATM) | full | full (right-click, Trade DOM, OCO) | full (one-click + Lock, held-modifier) |
| **Workspace persistence** | layouts (+lock, versions, per-screen) + profiles (13 blocks) + workspaces + templates | Workspace⊃Bind⊃Group⊃Panel XML + Lock | .bmw (layout+settings+instruments; link-share) | workspaces, 10 versions, one visible | profiles + templates (cycle keys) | chartbooks (one visible; portable files) | workspaces + layouts (Universal) + templates |
| **Panel/window model** | rail + content; **terminal widgets with tabs as OS windows**; master window list; reset rescue; safe start | OS windows w/ snapping, minimise-all | one window, tabs, detach (return home on close) | OS windows, no dock, one workspace at a time | docked/undocked up to 100 charts | MDI windows; chartbook=collection; window traps | real docking; quadrant/centre-drop; clone/pin/freeze |
| **Cross-view sync** | link groups **A–D** (symbol + timeframe), colour + letter | link colour on titles | master-slave charts, multi-instrument crosshair | link buttons + Link All + interval | chart switch bar (no link system doc'd) | not documented | colour-group linking |
| **Hotkeys** | one registry; rebindable; conflict refusal; armed gate; printable sheet | parameterised, scoped, armed (trading) | one editable table | Hot Keys window (conflicts, window-aware) | assignable; user keys outrank | global rebindable + trading gate | five sections; conflict warn; per-section reset |
| **Brackets/OCO** | paper exits editing (`set_exits`); no real OCO | per-connection OCO | brackets OCO after trigger, trailing | ATM rule sets; server+local | pending mgmt; no native OCO | OCO pairs per leg | order types + Flatten/Reverse |
| **Replay w/ order recording** | replay + paper ledger records orders (tape + wall clocks) + CSV | paid simulator | records orders; 3 modes | Market Replay (funded) | Strategy Tester | not in read scope | tiered replay (paid), resettable account + journal |
| **Extensibility** | Python adapters + JS modules + studies; open-source | C# Algo (paid) | ~36 add-ons + API | NinjaScript ecosystem | MQL5 marketplace | C++ DLL studies | connectors + KB |
| **Visual/perceptual depth** | schemes + percentile/exact + floor + gamma + smoothing + dim + large-highlight + global apply + **leashed ceiling** + time anchor + Detail 100 ms–5 s | 8 themes (reset in-panel colours) | ramp percentile/exact + auto-contrast + dimming + large-highlight + global apply | skins per-window (XAML) | no global font scaling (chronic) | per-object colour tables; per-scope fonts | data-semantic schemes + cut-off + contrast on every surface |
| **Multi-monitor & window trust** | any monitor; per-screen layouts; clamp/reset rescue | OS windows everywhere | mostly bug history + full HiDPI | OS windows + fixed maximise bug | detach + keep-on-screen patch | window traps; multi-instance workaround | not documented |
| **Onboarding & help** | 83-topic Centre + search/autofill + F1-per-panel + wizard 12+10 + Guide + identity copy | sidebar launcher + per-panel Help deep-links; no settings search | getting-started + launchpad; steep curve | F1 + video library; facelift critique | >100 novelty tips + global search; UI dated | numbered docs; settings overwhelm | Learn Center + template gallery |
| **Alerts channels** | ui + Inbox + Telegram + ntfy + email + sounds | in-app + telegram | in-app + alerts | in-app + email | in-app alarms + push | in-app + email | audio + Telegram; own-the-object alerts |
| **Settings discovery** | **Find-a-setting search + staging (Apply/Revert)** | none ("Google how") | scattered | modal-heavy | none | modeless + A/C + Apply All/Revert All + tokenised search | per-surface panels |
| **Data feeds & sources** | 9-value matrix incl. adapters for **every competitor here** + Alpaca + news/calendar/EDGAR/CoinGecko/Deribit | 60+ brokers; data billed separately | data billed separately (BookmapData/dxFeed/Rithmic) | top-of-book free; Order Flow+ gated | broker feed (gaps blamed on it) | feed depth first-class; external feeds gated | your own feed required |
| **Provenance labelling** | inferred tags (icebergs/sweeps/stop-runs) + freshness chips + live/warming/demo pill + watermarks | status dots + latency threshold | **estimated depth labelled** | sim surfaces painted | never shown | n/a | honest limits documented |

## 5. Market norms, re-tested against today's build

The field's expectations (mined from the six digests) vs ModFlow now. Legend: **Met** · **Mostly** (one refinement named) · **Partial** (real piece still open) · **N/A-by-design** (a deliberate divergence, stated as such).

| Area | Norm (who sets it) | Status | Note / receipt |
|---|---|---|---|
| Identity | Explicit "analytics layer beside your terminal", or BE a terminal (Bookmap/ATAS own the hybrid) | **Met** | `start.identity` topic + Guide section + README (§117) |
| Identity | "Market data is billed separately" spoken in the market's own words | **Met** | identity copy; venues' own terms referenced |
| Identity | Free tier / trial expected | **Met** | free, keyless, no account; replay + paper free (none of the six gives replay free *and* order recording) |
| Identity | Cross-platform increasingly expected | **Gap (accepted)** | Windows-only vs Bookmap/MT5; stated openly, not hidden |
| Layout | Saved layouts survive restart; set up once, reuse | **Met** | layouts store + boot adoption; `test_layouts.py` |
| Layout | Named, versioned, restorable, exportable arrangements | **Met** | version rings (10), restore-in-one-click, import/export; `test_layout_versions.py` |
| Layout | Layout lock (accidental rearrange protection) | **Met** | `ui.layout_lock` + status chip; `test_layout_lock.py` |
| Layout | Multi-window/multi-monitor without traps; recovery path for any window | **Met** | widget windows on any monitor; master list + reset; `--safe`; per-screen layouts — the exact class Sierra's threads lose days to |
| Layout | Templates/profiles travel between symbols/views and as files | **Met** | profiles (13 blocks, export-safe) + template gallery + per-view defaults |
| Interaction | Comprehensive, rebindable, conflict-aware hotkeys | **Met** | registry + Change/Reset/Reset-all + conflict refusal (§117); NT's "Hot Keys window" standard met |
| Interaction | Armed state for live-action keys | **Met** | armed gate + badge + spoken refusal (T3) |
| Interaction | Right-click menus that only offer valid actions | **Met** | T6/A8 context-validity |
| Interaction | Freeze a live canvas in place | **Met** | freeze-on-hover (§97/A7) |
| Interaction | Cursor-anchored zoom, hold-key/drag panning, arrow nudge | **Met** | §121 heat grammar (wheel-anchored, middle/shift-drag, arrows, Home) |
| Interaction | Position-aware menus for order-adjacent surfaces | **Partial** | paper ticket/ladder grammars exist; MT5's above/below-price pattern not yet applied to the ladder (§6) |
| Interaction | Drag with consequence preview (live P/L while dragging) | **N/A yet** | no drag-to-trade in the paper desk; applies when it lands |
| Interaction | Undo for destructive actions | **N/A-by-design** | no irreversible action exists; error-side undo moot |
| Interaction | Cross-view symbol sync | **Met** | link groups A–D (symbol + timeframe) with colour + letter; classic mode single-frame by design |
| Analytics | Footprint + CVD + profile + DOM/depth + heatmap minimum | **Met** | plus area profile, radar, unfinished business/node persistence |
| Analytics | Replay/practice loop | **Met** | replay + paper ledger records orders; CSV |
| Analytics | Alerts (visual + audio + push) | **Met** | ui + Inbox + Telegram + ntfy + email + sounds |
| Analytics | Save my analysis setup; reuse across symbols | **Met** | studies collections (§117) + profiles + per-view defaults |
| Visual | Dark default + theming | **Met** | dark/light/contrast palettes + density + accents |
| Visual | Perceptual heatmap controls (Bookmap-grade) | **Met** | percentile/exact + floor + gamma + smoothing + dim + large-highlight + global apply + **leashed ceiling** + time anchor + Detail (§102/§118/§121/§122) |
| Visual | Global UI scale + DPI correctness (MT5's wound) | **Met** | `setScale` 0.75–1.5, `--ui-scale`, `scale.js` canvas DPI |
| Visual | Anti-flicker hysteresis on colliding overlays | **Mostly** | Engine fit hysteresis (§98/A11); dials on further surfaces open (§6) |
| Visual | "What am I looking at" context at a glance + title tokens | **Met** | watermarks (instrument · view · mode), widget `titleToken`, topbar pills, link chips |
| Visual | Hover-to-number, mirrored in a persistent info line | **Mostly** | hint cards + info lines + tooltips; the Bookmap "Information Bar" mirror is the remaining nicety |
| Visual | Colour never alone (semantic + label redundancy) | **Met** | the CVD rule; every badge carries a letter |
| Visual | Colour-blind affordances | **Met — and unique** | none of the six documents one (ATAS KB: "nothing found") |
| Visual | Estimated/synthetic data labelled | **Met** | inferred tags on icebergs/sweeps/stop-runs; freshness chips; live/warming/demo pill |
| Visual | Density knobs per data surface | **Mostly** | density select + per-surface settings; extend on complaint |
| Settings | Modeless, searchable settings; staged edits | **Met** | "Find a setting" + staging with Apply/Revert (§96/T7) |
| Settings | Show-original-values diff; tokenised search | **Partial** | tokenised search in the Centre (have); diff view open (§6) |
| Onboarding | Per-panel help deep-links | **Met** | `?` per panel + F1-in-focus (§96/T1) |
| Onboarding | Searchable help with autofill | **Met** | 83 topics + autofill + Simple/Advanced |
| Onboarding | Tips that fire only for never-performed actions | **Partial** | wizard + Guide + inline cards exist; the MT5 novelty-tip layer is the open idea (§6) |
| Data | Feed breadth + honest capability display | **Met** | 9-value source matrix; adapters for every competitor; venue hints |
| Data | Per-symbol provenance (source, last tick, gaps, backfill) | **Partial** | chips/pills exist; gap/backfill counters open (needs an ingest counter — the known Wave-B piece) |
| Data | Entitlement gating of the product's own features | **N/A-by-design** | nothing in ModFlow is tier-gated; keep it that way |

---

## 6. Findings — the honest remainder

### 6.1 Internal (ours; from the standing audits — receipts in `docs/MENU_RECONCILIATION.md` and `docs/CONTROL_SURFACE_AUDIT.md`)

1. **F1 — Trackers advertises reads it doesn't fetch.** The view's menu copy promises "correlation, dots, cross-venue reads"; the fetches are alert-rules/history/imbalance/tape only. Five live routes have no UI caller: `/api/atlas/dots`, `/correlation`, `/crossvenue`, `/intent`, `/trades/recent`. Wire or correct — never neither.
2. **F2 — Three server-made CSV exports sit dark** (tape, heatmap, alerts; routes verified HTTP 200). Tools has no Export submenu.
3. **F3 — `POST /api/control/storage/prune` has no button** while the storage block renders usage (DB ~776 MB at the audit; ~851 MB measured since).
4. **Control surface (F-1…F-7 open):** `frameSelect` can't choose the sixth frame family (delta — the engine builds it, the API serves it; one `<option>` + two doc lines); the Settings Data-source dropdown offers 5 of the 9 accepted values (populate from `/api/control/sources`); the registry offers `imbalance_mode: "both"` that the store silently coerces (drop it or build it end-to-end); bounds drift in up to three places (registry vs inputs vs store clamp — pin the markup against the registry in `test_param_registry`); "candles" listed twice in the Chart's Bars menu; hover-help option keys that never match today's markup (tfSelect/rangeSelect; DEBUG decision); the Calendar's hours/impact filters don't persist. Plus the preset+custom combobox pattern across the 19 controls already listed in that audit's §4. (F-8, hmAgeTint localStorage-only, is deliberate — keep the comment.)
5. **Eight `planned(...)` stubs remain** — actionable: *Reset rail order*, *Edit list*, *Record session…*, *Recent*; decision needed: *Exit* (the close button is the way — either close the stub with that sentence or add a quit route); honest-as-is: *Layouts*, *Drawing layer not loaded*, *no saved workspaces yet* (environment-conditional).
6. **Standing follow-ups (handoff):** radar walls / big-trade zones · spent-state persistence · config slots.
7. **Release hygiene:** `dist/` rebuilt at §125 over the §119–§125 tree (Setup 37,659,252 bytes sha256 `5B8BF8B4…`; frozen smoke 18/18 at 78 shell refs; Setup journey 17/17 ALL PASS). Commit/publish on the owner's word, drafts first.

### 6.2 Field-derived (new this pass — what the six still offer that ModFlow doesn't)

1. **A Show-Original-Values diff** in the staged settings surface (Sierra's most-cited nicety; ModFlow stages edits with Apply/Revert but shows no pre-change diff).
2. **Novelty-gated tips** — MT5's "tips fire only for actions you've never performed, and each tip is a launcher". ModFlow's Centre + wizard + Guide cover the ground; a tip layer would catch the user who skips all three.
3. **Paper-ladder grammar refinements** (ATAS/NT/MT5): a held-modifier override with a cursor tooltip that states the operation before it fires; interval auto-centre + double-click centring; above/below-price position-aware context. The paper desk is ModFlow's practice loop — make its grammar best-in-class while it is cheap.
4. **MT5-ingest provenance depth** — MT5 users' own wound is "missing candles / not confident the data is up to date", and ModFlow ingests MT5 read-only. A per-symbol provenance sentence (source, last-tick age, backfill, gap count) turns a competitor's weakness into a ModFlow feature. Needs the ingest counter (already flagged as a Wave-B piece, not faked).
5. **Bookmap's remaining small craft:** per-column reset modes (Manual/Scheduled/Conditional/double-click) for the columns rail; a range-to-table events list (box a region → table + filters + CSV — ModFlow already boxes and exports; the table is the missing middle).
6. **Quantower's size-formula quick buttons** (`;`-lists, arithmetic) — pairs naturally with the preset+custom combobox pattern already queued in the control-surface audit.
7. **Anti-flicker dials beyond the Engine** (Bookmap hysteresis controls) — nice-to-have if a collision surface ever annoys.
8. **Error states naming a help topic** (Sierra wires every error to a numbered topic; ModFlow's blank states do this — extend the habit to runtime error toasts).
9. **The active profile's name, always visible** (MT5's status bar carries template + profile). ModFlow's Profiles rail row carries a dirty badge; the name in the status bar is the small missing half.

### 6.3 Where ModFlow is already ahead of the finding — do not "fix" these

- Settings search exists (Quantower and MT5 have none; users say "you'll have to Google how to configure something"). 
- Window recovery kit (Sierra's own board: "I tried to reattach it for 10mins… impossible" — ModFlow resets position in one click).
- Structured onboarding (wizard + Guide + Centre + identity) vs Bookmap's steep curve and MT5's "half an hour just to see the chart".
- Colour-blind palettes — none of the six documents one.
- No entitlement gating anywhere.
- Collapsed/minimal modes and zen exist (Bookmap's community advice — "disable everything except the heatmap" — is a shipped toggle here).
- Zoom-level degradation on the Engine (ATAS's footprint→candles trick) already exists.

---

## 7. Improvement suggestions, ranked

**Priority 1 — close our own truths (small, cheap, ours; do next).**
1. Trackers: wire dots/correlation/cross-venue/intent/recent-trades, or correct the copy (F1). The wiring is the bigger unlock; the tables already have a home.
2. Control-surface one-liners: delta option in `frameSelect`; Settings source dropdown from `/api/control/sources`; drop registry 'both'; relabel the duplicate "candles"; fix the hover-help keys (+DEBUG decision); persist the calendar filters.
3. The bounds pin (`test_param_registry` vs markup attrs) — stops the three-places-drift class for good.
4. Tools ▸ Export submenu (tape/heatmap/alerts CSV) + a "Prune now…" button on the storage block with confirm.
5. Promote or decide the four actionable stubs (Reset rail order, Edit list, Record session…, Recent) and close the Exit question deliberately.

**Priority 2 — take the field's cheap differentiators (still small; the polish pass).**
6. Show-Original-Values diff in the staging surface (§6.2-1).
7. Novelty-gated tips layer over the existing help stack (§6.2-2).
8. Paper-ladder grammar: held-modifier override + cursor tooltip; auto-centre interval + double-click; position-aware ladder context (§6.2-3).
9. MT5-ingest provenance depth — build the ingest gap counter, surface the provenance sentence (§6.2-4).
10. Preset+custom comboboxes on the 19 listed controls + Quantower-style size-formula quick buttons (§6.2-6).
11. Bookmap remainder: per-column reset modes; range-to-table events list (§6.2-5).
12. Error-toast → help-topic wiring; active profile name in the status bar (§6.2-8/9).

**Priority 3 — release hygiene and the two gates.**
13. Rebuild dist/zip/SBOM/installer over the §119–§123 tree; commit/publish on the owner's word (drafts first — standing gate).
14. **Keep broker execution out** until it can ship as one complete, gated mode (credentials answered, brackets + OCO + position/P&L whole). The paper desk is the correct boundary today; a half-built execution stack is the one thing the study warns against across every platform.
15. **The cross-platform question stays open** — Windows-only is acceptable for the analytics-layer identity; revisit only with a concrete demand signal.

**What NOT to build (updated):** OS-window bind/super-panel gesture hierarchies (Quantower's blast radius); entitlement gating on anything (history, replay, symbols); dock-manager clones; per-object colour tables (Sierra's hundreds-entry model); menu-as-API without docs infrastructure; any update mechanism that blocks or restarts; account/server coupling; add-on ecosystems before a plugin SDK exists; and do not copy a competitor's density-by-default — ModFlow's focus-first reading order is the differentiator.

---

## 8. Recommended roadmap

**Phase E — truth close-out (next wave; hours-to-days total):** items 1–5 above, then the rebuild (13). The audit docs already contain the re-run recipes; each fix has a named receipt target.
**Phase F — field-derived polish (a wave of its own):** items 6–12; each is independently shippable and test-pinnable, and none touches the engine.
**Phase G — the gates (owner's timing):** broker execution as its own gated mode; cross-platform reconsidered only on demand.
**Standing:** the follow-ups already recorded in the handoff (radar walls / big-trade zones, spent-state persistence, config slots).

---

## 9. What ModFlow already beats every competitor on

- **Free, keyless, local-first, no account, open-source** — every competitor here is either paid (Bookmap/ATAS/Sierra/Quantower's good tiers), broker-owned (MT5), or account-bound/funding-gated (NinjaTrader's Order Flow+).
- **Feed adapters for every competitor in this report as data sources** — no competitor ingests the others. Unique, and now surfaced in the identity copy.
- **Unified breadth in one tool:** heatmap + footprint + CVD + TPO + area profile + depth + tape + 8 trackers + the **level radar** (a lifecycle read no competitor ships as a product) + signals + strategy + journal + calendar + news + fundamentals + options + replay + alerts — the breadth competitors split across price tiers and add-ons.
- **Colour-blind-aware palettes** — none of the six documents one; ATAS's KB returns nothing for "colorblind".
- **Test-enforced help coverage and gates** (`test_guide.py` and the standing battery) — an internal asset, but it is why the 83-topic Centre, the wizard and the doors cannot silently rot the way competitor docs "trail the product by months" (Quantower's help still headlines a June build).
- **A never-blocking updater, checksummed backups, write-only credentials, CSP** — the trust posture every competitor's forum history says they lack.
- **Nothing one-click irreversible; armed + locked safety as the default posture** — the opposite of MT5's zero-confirm deletes and Quantower's blown-account reports; the paper desk demonstrates the full grammar safely.
- **Settings search + staging, a command palette, F1-per-panel** — Quantower and MT5 have no settings search at all; the Centre answers for the panel in focus.
- **Per-surface pause everywhere** — no competitor in the study documents "pause this panel" as a first-class idea.

---

## 10. Coverage, method and re-run recipe

**Inspected this pass (all read at the tree, this date):** `index.html` (rail 31 + runtime injections; 41 selects / 93 id'd inputs; settings cards), `keys.js` (registry: 39 `OFAPKEYS.bind` + 6 `OFAPKEYS.document` across 15 modules), `links.js`, `shell.js`/`windowing.js`/`windows-ui.js`, `heatview.js`/`heatmap-pro.js`, `ladder.js`/`paper.js`, `guide.js`/`help.js`/`help-data.js` (83 topics), `config_store.py` (`PROFILE_BLOCKS` = 13; `ui.keys`; layouts block), `param_registry.py`, desktop/atlas/api route inventories, the six digests (spot-checked against the briefs: Bookmap hysteresis formula, Bookmap prices, ATAS prices, MT5 tips, NT version retention, Sierra tokens, Quantower armed-trading toggle — all verified), plus the standing audits (`COMPETITIVE_AUDIT_DIFF.md`, `CONTROL_SURFACE_AUDIT.md`, `MENU_RECONCILIATION.md`) and the §96–§123 handoff records. Test count re-run: 1,634 collected.
**Not covered (stated, not hidden):** no live-app drive this pass (the last live receipts are §121–§123's); typography/accessibility beyond the palettes; competitor prices as published on the briefs' dates; the digests' own "not read" items stay unasserted.
**Re-run:** the digests are re-mineable from the briefs in an hour; the ModFlow side is re-derivable with the scripted counts above; the audit docs carry their own re-run recipes. Law from the first pass stands: **read the tree, cite the receipt.**

*End of report. Six supporting digests: `docs/ux-study/digests-2026-09-19/`. No code was changed in this pass — nothing committed.*


