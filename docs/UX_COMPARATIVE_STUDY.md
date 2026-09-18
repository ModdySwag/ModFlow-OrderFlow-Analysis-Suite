# UX comparative study — the paid order-flow platforms vs ModFlow
## layout · navigation · interaction · visual design · onboarding · trust

**Status: study + plan for approval, written 2026-09-18 after his brief. Nothing in the app was changed by
this pass.** The deliverable is the ranked improvement programme in §5 (waves A–C); implementation starts
when he says so.

**Scope.** Quantower, Bookmap, NinjaTrader 8, MetaTrader 5, Sierra Chart, ATAS — studied for the way they
function as *software a person uses*: windowing, information architecture, input, visual language,
onboarding, and the trust/performance wounds their users report. Compared against ModFlow as it stands in
§95 (evidence-backed inventory, all counts measured from the tree).

**Sources.** Seven parallel cited briefs, copied into the repo and read by the author of this doc:

| Brief | What it is | Evidence base (as verified in the brief) |
|---|---|---|
| `docs/ux-study/quantower.md` | Quantower UX/GUI study | 76 unique URLs; 42/42 help+vendor links re-checked live; 432 Reddit comments across 11 threads with permalinks; extension of `docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md` |
| `docs/ux-study/bookmap.md` | Bookmap UX/GUI study | 52 unique sources, 159 citation occurrences; 34 KB slugs machine-validated against the sitemap; 12 explicit "not read" markers |
| `docs/ux-study/ninjatrader.md` | NinjaTrader 8 UX/GUI study | full 370-topic help TOC + ~73 help pages cached; 11 forum threads via Discourse API; every quotation re-verified against cached text; 1,220 Trustpilot reviews scanned |
| `docs/ux-study/metatrader5.md` | MetaTrader 5 UX/GUI study | 21 MetaQuotes pages read first-hand (help, release notes, market), plus review sites and MQL5 forum threads; 148 inline links / 39 distinct URLs |
| `docs/ux-study/sierrachart.md` | Sierra Chart UX/GUI study | 46 captured page texts; 44 sources; ~35 claims read directly from docs/Support Board; Reddit quotes labelled `[snippet]` where the site was blocked |
| `docs/ux-study/atas.md` | ATAS UX/GUI study | 166 citations / 67 unique URLs; KB pages fetched in a real browser; 19 Reddit permalinks verified in archived data; extends `docs/ATAS_SDK_NOTES.md` |
| `docs/ux-study/modflow_inventory.md` | ModFlow's own surface (the baseline) | Every structural claim carries file:line; real counts via grep/find/wc/node |

**Licence discipline.** All six are proprietary products. Nothing here is code: every adopted item is a
*mechanism* described in prose, re-implemented in ModFlow's own stack. The peer briefs' §8 tables are
already written in that form and were filtered against ModFlow's existing features before ranking.

**Verification caveats (honest list).** Reddit was blocked for some researchers — quotes from it are
labelled as snippets; Bookmap's price table was reconstructed from a served page and is marked as such;
MetaTrader's own licence prices are not published anywhere readable; one ModFlow finding below (the
wizard-button digit shift) is code-observed, not runtime-verified. Independent spot-checks by me: help
corpus **73 topics / 7 groups / 31 views mapped** ✓, rail **29** entries ✓, `OFAPKEYS.bind` call sites
**26** (the inventory's "32 bind() call sites" is a wider count; the hotkey sheet's 41 rows stand as the
figure used below).

---

## 1. The field at a glance

ModFlow's own numbers, measured (`modflow_inventory.md`): **29 rail views + 3 injected** · **31 view
sections** · **58 cards, 39 KPI tiles** · **12 top-level menus** · keyboard registry with the sheet's
**41 rows across 9 scopes** · **73 help topics / 7 groups, coverage test-enforced** · theme system: one
84-token block, **256 CSS custom-property declarations**, **3 themes × 8 accents × 3 densities**, **4
colour-blind palettes with measured ΔE** · layouts ≤24, widget grid 12×8 (≤12 tabs, ≤24 widgets), aux
windows ≤8 · wizard 9/19 steps · 109 contextual tooltips.

| | Windowing / layout signature | Discovery & settings | Interaction signature | Visual | Onboarding | The wound users report |
|---|---|---|---|---|---|---|
| **Quantower** | OS-window panels, edge snapping; 3-layer hierarchy (Workspace → Bind super-panel → Group tabs); colour link groups | Per-panel menus; **no settings/command search** ("Google how to configure") | Four overlapping order-entry flows, deliberately; armed trading hotkeys; chart hotkeys | Dark, dense, customisable | Demo + templates; docs-driven | Runtime trust: 20 s lags under volatility, 2 GB→7 GB over days, force-update window stranding the app, HiDPI blur |
| **Bookmap** | Tabs + detached OS windows; **no dock manager documented**; `.bmw` workspace files | **Scattered settings** and the vendor keeps moving them (studies icon, right-click ladder, gear, two Settings levels) | Deep canvas fluency: cursor-anchored zoom, hold-D drag, 1 px/Shift-10 px nudge, hysteresis controls | Heatmap-first, dark by default; density-by-default called "info overload" | Replay + demo; community advice is *"disable everything except the heatmap"* | Steep curve; GPU/heavy hardware; cost stacking; one 1★ review: "interface hurts my eyes" |
| **NinjaTrader 8** | Control Center (4 menus, 11 tabs) + every surface its own OS window; workspaces = one visible at a time; **no docking** | Context-valid right-click menus; F1 context help; properties dialogs per surface | Two mouse grammars (Chart Trader vs SuperDOM); hotkey system with window scoping; ATM brackets | XAML skins, restart to change; vendor still shipping "facelift" items in 2026 | Sim account; huge help guide; add-on ecosystem | UI age ("give it a facelift"); release-cadence regressions; training cost |
| **MetaTrader 5** | Fixed panels (Market Watch / Navigator / Toolbox) + undockable charts; profiles + templates | Menus + hotkeys; vendor itself: *"started a comprehensive redesign of the trading dialog to make it more intuitive"* | **Zero-confirmation one-click actions** (close/delete); position-aware context menus; drag with P/L previews | Dated look; **no font-size control** (top complaint); decade of HiDPI patches | Demo accounts, >100 "tips that fire once" with deep links | Data distrust ("does not match up", "missing candles"); DPR/blur pain on 4K |
| **Sierra Chart** | Chartbooks → child windows; detach/attach; master window via CW menu | **Their strongest asset: modeless settings panels with tokenised search, Show Original Values, Apply All/Revert All, per-field A/C** | Everything is a study; per-command shortcut legend; trading shortcuts behind an explicit enable | Extremely dense; tiny text complaints; engineering stance: "UIs are in decline… we will do it right" | Docs-first; numbered permanent help topics linked from blank states | **"The window became unreachable"** class (detached window lost on monitor 2; reattach "simply impossible"); scope-confusion support threads (a font fix took 10 posts) |
| **ATAS** | Real docking; **two-tier persistence** (workspaces/layers vs layouts); windows merge into tabs; colour-group instrument sync | Deep settings tree; module templates | Smart DOM as a column spreadsheet; **held-`V` stop override with cursor tooltip**; sectioned hotkey registry with conflict handling | **Data-semantic colour presets + cut-off/contrast dials**; **no colour-blind option exists** | Demo; template gallery + Learn Center | Feeds/price/support complaints; X-beta stability — UI rarely the gripe (praise: "modern UI") |
| **ModFlow (baseline)** | Single window + rail + terminal mode with **real OS widget windows**; layouts with per-monitor `screen_key`; aux windows ≤8 | One Settings surface; command palette (Ctrl+K//); Keys menu renders live from the registry; hover/right-click explain cards; **no breadcrumbs** | Registry-driven keys + shortcut prompts; per-surface pause/resume; pointer work per view (drag-select, pan/zoom, widget drag/resize) | Dark; 3 themes × 8 accents × 3 densities; **4 measured colour-blind palettes**; canvas-native views | Wizard 9/19 steps; test-enforced help coverage; demo data paths | Own recorded gaps: F1–F7 (§4) + the cross-study gaps below |

---

## 2. What the field teaches, metric by metric

### 2.1 Layout & windowing
- The universal failure class across the paid field is **"the window became unreachable"** (Sierra `[S19][S20]`, acknowledged in a dedicated FAQ; MetaQuotes had to patch service windows being lost off-screen; Bookmap documents UI disappearing across monitors). Every one of these is a *multi-window* product. ModFlow's terminal mode creates **real OS windows** — this class is directly applicable, and the cheapest insurance is a master window list + clamp-to-visible-monitor + the close-to-re-dock rule.
- The best layout mechanics worth borrowing are small: **layout lock** (Quantower), **workspace version history + safe mode** (NinjaTrader), **`Universal` layer** semantics (ATAS), **"set as default" per panel with a factory escape** (Quantower; its removal of reset-to-default is the mistake to not copy), and **export/import of workspace artifacts** (Sierra's shared chartbooks are how its users support each other).
- What is *not* worth copying is structural: Quantower's Workspace→Bind→Group triple hierarchy and a full dock-manager rebuild are large, gesture-heavy, high-blast-radius changes in a single-window + grid model — the study's own example of a layout change shipped without a compatibility path (the 1.146.13 episode) is the cautionary tale.

### 2.2 Navigation & information architecture
- The industry-wide #1 wound is **settings discovery**, and it compounds with surface count: Bookmap's settings live in six places and keep moving; Quantower users are told to Google; Sierra's scope confusion ("2 types of graphic settings") turns a font change into a 10-post thread; MetaTrader admits a redesign mid-flight.
- The winners' mechanics: **modeless settings with in-panel tokenised search + Show Original Values + Apply-All/Revert-All + per-field accept/cancel** (Sierra — the single most transferable asset in the whole study); **explicit scope switch** ("this surface only" vs global, with copy between scopes); **context-valid menus** that only offer actions legal at that price/side/point (NinjaTrader, MetaTrader); **one field that also launches commands/pages** (MetaTrader's Toolbox search; Bookmap's filtered search is absent — a noted gap).
- ModFlow already has the palette, the Keys menu that cannot drift (rendered from the registry), and explain cards. The missing pieces are the *settings* half of this story (§4) and contextual entry points (help deep-links, typed overlay selector, instrument lookup overlay).

### 2.3 Interaction & input
- **Two mouse grammars, deliberately**: NinjaTrader's Chart Trader right-click filters to broker-legal order types; the SuperDOM uses left/Ctrl-left/middle/Ctrl-middle. The teachable core: *the menu teaches the model by omission*.
- **Held-modifier overrides**: ATAS's hold-`V`-to-place-a-stop with a cursor action tooltip removes a mode toggle and doubles as the confirmation dialog for people who turned confirmations off.
- **Canvas fluency is where the power users live**: Bookmap's cursor-anchored wheel zoom, "hold D" drag mode, 1 px / Shift-10 px arrow nudge, Ctrl+Z zoom-out undo. ModFlow's canvases currently have pan/zoom/drag-select but not the *precise* layer around them.
- **Freeze-on-hover** (NinjaTrader's static ladder: suspend + turn red + pin the quotes in a header row) is the cleanest inspect-without-chasing pattern in the field — directly applicable to Depth/Tape/Heatmap.
- **Hotkey registries**: ATAS sections its bindings (5 sections) and prompts keep-or-replace on conflict; Sierra puts the shortcut on the menu line and gates live-order shortcuts behind a master enable; Quantower arms keyboard trading behind a visible toggle. ModFlow's registry is always-live and its Keys menu doesn't show conflicts.
- **Order entry**: MetaTrader's position-aware context menus and consequence-preview drag tooltips (P/L in currency *and* pips while dragging SL/TP) are cheap, high-value mechanisms; ATAS adds the panic-proof **danger row** (Flatten/Reverse) + **Lock trading**. ModFlow's paper ticket just shipped (§95) — these map straight onto it.

### 2.4 Visual design & accessibility
- **Density is the shared tax and the shared craft**: Sierra solves "too small to read" with contrast tiers and per-region fonts, ATAS with values dividers / min-cell-width gating / row-height knobs, Bookmap with vertical smoothing and a community-endorsed minimal mode.
- **DPI/font pain is the loudest accessibility failure** in the field: MetaTrader has no font-size control (its most-cited visual failure) and a decade of HiDPI patches; Bookmap's closest accessibility feature is Ctrl +/− font zoom.
- **Colour**: ATAS explicitly ships **no colour-blind option**; none was found in Bookmap's or Sierra's docs either. ModFlow's four measured-ΔE CVD palettes are a genuine differentiator — worth *publishing* rather than discovering.
- **Data-semantic colour** (ATAS's named schemes — Delta, Volume Proportion, Heatmap by Volume/Trades/Delta — with Upper Cut-off % and Contrast dials) is orthogonal to theming and composes with it; ModFlow has palettes but not data-semantic presets.

### 2.5 Onboarding & discoverability
- The best onboarding mechanics are small and cheap: MetaTrader's **>100 tips that fire only for actions never performed**, with links that launch the target UI; ATAS's **template gallery + Learn Center** ("load a working layout, then mutate it" — the fastest cure for a 30-surface app); NinjaTrader's **starter + advanced layouts shipped in-app** and F1-for-focused-surface.
- Blank/error states that **carry their own fix** (Sierra's "Symbol is Unknown → Help Topic 1.3") turn a docs corpus into in-product onboarding — ModFlow has the corpus (73 topics, test-enforced) and the blank states; it lacks the wiring.

### 2.6 Trust, data honesty & performance
- The paid field's trust wounds are consistent: latency scaling with window count and unbounded memory growth (Quantower), GPU-heavy rendering and "info overload" (Bookmap), **data distrust** — "does not match up", "missing candles", "not confident the data is up to date" (MetaTrader); a force-update that strands the app (Quantower).
- Bookmap's **explicit synthetic-data labelling** ("out-of-range depth is only an estimation") is the highest-integrity pattern in the study — directly relevant to ModFlow's inferred analytics (absorption/iceberg inference) which currently do not mark themselves as inferred.
- Counterpoint where ModFlow already leads: keyless feeds, local-first storage **with** the usage/backup dashboard none of the six ships, checksummed artefacts, a paper simulator on the real tape, and no account requirement anywhere.

### 2.7 Money layer (read-only observations, for context only)
Read from source where possible, flagged where not: Quantower All-in-One **70** monthly / 189 3-mo / 336 6-mo / 588 annual / 1690 lifetime (currency not in the served HTML — quoted as published); NinjaTrader **Free / $99 per month / $1,499 lifetime** with Order Flow+ unlocked by funding; ATAS **€0 / 24.95 / 69.95 / 89.95** per month; Bookmap tier table **reconstructed** ($19/$49/$99 columns) — treat as unverified; Sierra **$26/36/46/56** per month, no perpetual licence; MetaTrader's own licence prices are **not published** (three tiers defined by account capacity only). None of this transfers — ModFlow's keyless, free model is the point of difference, and the entitlement-gated UX these products carry is on the do-not-take list.

---

## 3. Where ModFlow already leads (keep, and say so)

1. **Colour-blind palettes with measured ΔE** — none of the six documents any.
2. **Help corpus enforced by the test suite** (29 views ↔ topics) — no peer test-enforces its docs.
3. **Keyless-first** — all six require an account/keys for data.
4. **Storage management with manifest + SHA-256 + UNC/drive/synced targets** — all six leave retention manual (already established in the previous sweep).
5. **Per-surface pause/resume** — no peer equivalent found; the closest is NinjaTrader's freeze-on-hover (which we should also adopt).
6. **Nothing one-click irreversible** — the contrast is MetaTrader's documented no-confirmation closes/deletes; ModFlow's destructive acts are local and reversible by design.
7. **Explain cards (hover / right-click)** — the field's nearest equivalents are per-panel help (Quantower) and F1 help (NinjaTrader).
8. **An updater policy that never blocks** — Quantower's force-update window is the anti-pattern; write our policy down so it stays true.
9. **One Settings surface + config-as-the-record** — the field's #1 pain is settings scatter; ours is single but lacks search/scope affordances (item B1).

---

## 4. Where ModFlow lags (the findings)

**Already recorded (F1–F7, `docs/MENU_RECONCILIATION.md`):** F1 Trackers advertises what it does not fetch (five live routes, no caller) · F2 three server CSV exports sit dark · F3 `storage/prune` unexposed · F4 profiles-vs-workspaces overlap · F5 no quit path in the API · F6 canvas pause buttons need the arbiter first (buttons before wiring would lie) · F7 serve-time byte checks as habit.

**New, from this study:**
1. **Settings discovery inside the app**: no settings search, no scope labels, no Show-Original-Values analogue, no Apply-All/Revert-All — the field's hardest-won lesson (Sierra) is precisely this layer, and our single Settings surface makes it cheap to add.
2. **Window trust**: terminal-mode aux windows have no master list, no clamp-to-visible-monitor, no version history, no lock — every peer with OS windows has been burned here.
3. **Armed state for order-adjacent keys**: our keyboard registry is always live; with the paper ticket now shipped, a stray key can place/trade a simulated order. Quantower/Sierra gate exactly this.
4. **Heatmap/DOM legibility knobs**: no cut-off/percentile controls, no anti-flicker hysteresis, no smoothing, no columns rail, no zoom-level degradation rule (footprint→candles), no density knobs (values divider, min cell width, row height).
5. **Latency & provenance**: no latency-threshold badge, no per-symbol source/age/gap chip, and inferred analytics (absorption/iceberg) are not labelled as inferred — Bookmap's synthetic-data labelling is the integrity bar to meet.
6. **Onboarding depth**: no template gallery / starter layouts; no first-run tips that fire per never-performed action; no F1 deep-link from the focused surface; blank/error states don't carry topic links yet.
7. **IA polish**: no dynamic title tokens, no collapsed-panel state, no link-group colour on the titles themselves, no table-component unification (Tape/Journal/Logs/Trackers each re-invent interactions), no instrument lookup overlay, no notifications inbox, no in-app "what changed" note per release, no UI scale / font zoom.
8. **New code-observed finding (not runtime-verified)**: the rail-top Setup-wizard button shifts the 1–9 digit view-switch mapping by one (`keys.js:236-242` vs `guide.js:2314`) — a small correctness item to verify and fix.

---

## 5. The ranked improvement programme

Waves are by effort/risk and by what the study evidence supports most strongly. Each item names its
source mechanism(s). Gates for every item: `pytest` + `audit_ui_refs` + node selftests + ruff green, plus a
live sandbox check of the behaviour, recorded in the handoff.

### Wave A — small, reversible, presentation-state only (start here)

| # | Item | From | Why | Effort | Risk |
|---|---|---|---|---|---|
| A1 | **Contextual help wiring**: per-panel menu "Help for this panel" + F1 on the focused surface + blank/error states carry "reason → Help topic" links | QT, NT, SC | Turns the test-enforced corpus into just-in-time help; zero teaching overhead | S | Low |
| A2 | **Layout lock** — one toggle blocks add/remove/move/resize of widgets until unlocked | QT | Live-trading misclicks on a grid we persist; keep the lock out of the drag math | S | Low |
| A3 | **Armed order-adjacent hotkeys** — visible armed/disarmed state gating only order-placing keys, indicator in the status strip, default OFF | QT, SC | The worst failure this app can have is a stray key that trades; two states, one badge | S | Medium |
| A4 | **Shortcut legend from the registry** — render the binding beside menu items and key controls; print/export the sheet; conflicts flagged | SC, NT, ATAS | Registry is the source of truth; the legend must be rendered from it, never a static table | S | Low |
| A5 | **Latency-threshold badge** — user sets ms; panels show "market data delayed" from one honest per-feed threshold | QT | Makes invisible staleness visible; never fabricate latency when unknown | S | Low |
| A6 | **Provenance + synthetic labelling** — per-symbol source / last-tick age / gap count chips; inferred analytics labelled "inferred" | MT5, BM | Converts the field's #1 trust complaint into a feature; highest-integrity pattern in the study | S | Low |
| A7 | **Freeze-on-hover for Depth/Tape/Heatmap** — suspend the moving target while hovered, visibly frozen, pin the readouts | NT | Inspect without chasing; pairs with pause/resume | S | Low |
| A8 | **Context-validity menus** — right-click offers only actions legal at that point/side/price; disabled ones carry the why through explain cards | NT, MT5 | Removes error classes without a modal; menus teach the model | S–M | Low |
| A9 | **Dynamic title tokens** — panel/tab titles built from state (instrument · view · mode); watermark on canvases | NT | Kills "which panel is this?" in screenshots, replay, terminal mode | S | Low |
| A10 | **Minimal mode + collapsed state per surface** — a one-click "heatmap + traded volume only" preset; hide chrome, keep interaction | BM, NT | Cheapest onboarding lever for a 30-surface app; data-per-pixel on laptops | S | Low |
| A11 | **Anti-flicker controls** — hysteresis + tolerance sliders on recentre/overlay logic (Bookmap's `hide × (1+factor)` shape) | BM | Directly fixes jitter in live DOM+heatmap repaint | S–M | Low |
| A12 | **Canvas precision kit** — cursor-anchored wheel zoom, held-key drag mode, arrow-key 1 px / Shift-10 px nudge on heatmap/depth | BM | The keyboard-precise inspection power users miss; register as commands in the Keys menu | S | Low |
| A13 | **Window trust pack** — master window list (every widget window), restore/clamp-to-visible-monitor command, title-bar guarantees, close-to-re-dock rule | SC, MT5, BM | The universal "unreachable window" failure class, applied to our OS windows | S–M | Low |
| A14 | **Layout safety net** — workspace version history (retain N, restore UI) + safe start (no aux/layouts) | NT | Layout loss is the most expensive local accident; doubles as bug evidence | S–M | Low |
| A15 | **Per-surface "set as default"** with factory reset escape | QT, NT | Removes per-session re-tuning; the escape hatch is the part Quantower got wrong | S | Low |
| A16 | **Ambient status strip** — layout/workspace name, data source, pause state, last-tick age | MT5 | Cheap answer to "what state am I in?" | S | Low |
| A17 | **Update policy written down + "what changed" note** — never-blocking error path; short per-release UI-change note in the updater channel | QT, MT5 | The force-update wound is the proof; the note is how a one-dev app avoids "where did the button go?" | S | Low |
| A18 | **Paper-ticket safety row** — Flatten/Reverse/Close-all fixed strip + "Lock trading"; held-`V`-style modifier override with cursor tooltip; auto-centre rules with double-click-to-centre | ATAS | The panic panel should be positional, not findable; the lock is free safety in a sim people leave open | S | Low |
| A19 | **Sound controls** — volume slider + test sound + safe defaults (already have trade audio) | NT | Alerts become trustworthy instead of muted | S | Low |
| A20 | **Data-density knobs** — values divider, min-cell-width text gating, digits-after-comma, row height on data surfaces | ATAS, QT | Canvas renderers fail on density, not features | S–M | Low |

### Wave B — medium, contained mechanisms

| # | Item | From | Why | Effort | Risk |
|---|---|---|---|---|---|
| B1 | **Settings/Studies: modeless + in-panel tokenised search + Show Original Values + Apply-All/Revert-All + per-field accept/cancel; explicit scope switch (this surface vs global) with copy-to/from-global; saved config slots** | SC, MT5 | The field's strongest settings UX, aimed at its #1 wound; our single Settings surface makes it tractable | M | Low |
| B2 | **Heatmap ramp controls** — numeric + percentile cut-offs, contrast dial, "apply scheme globally" broadcast; data-semantic named schemes | BM, ATAS | Fixes the #1 heatmap readability complaint class without new data | M | Low |
| B3 | **Vertical smoothing Auto/Manual/None** for wide zooms, labelled display-only | BM | Cheap perceptual win; "None" keeps distrust out | S–M | Low |
| B4 | **Columns rail** right of the canvases with per-column reset semantics (manual/scheduled/conditional/on-double-click) | BM | Maps 1:1 onto Depth/Tape/Profile rails; reset semantics are the reusable novelty | M | Medium |
| B5 | **One table component** for Tape/Journal/Logs/Trackers/Watchlist — right-click header column set, sort, group, drag-reorder | QT | One interaction to learn, one place to fix; adopt on new views first, migrate behind a flag | M–L | Medium |
| B6 | **Instrument lookup overlay** — connection → venue → type tree, persistent filters, selection counters | QT | Answers "how do I find X across 9 feeds" without leaving the surface | M | Medium |
| B7 | **Notifications inbox** — in-app categories/priority/no-disturb, act-on-click tiles, feeding the existing alert engine | QT | Our alerts fire outward; the inward story is thin and the "why did it fire" evidence lives here | M | Medium |
| B8 | **Template gallery + starter layouts + Learn Center entry** — load a working layout, then mutate it | ATAS, NT | The fastest cure for surface overwhelm; fits the existing help corpus as its entry point | S–M | Low |
| B9 | **Per-instrument settings scoping** — last-used wins for new instruments, with a per-instrument reset | BM | Removes the re-tune-every-symbol tax across ~9 feeds | S | Low |
| B10 | **Config as portable artifacts** — export/import workspace + studies JSON with schema version, readable refusal on corrupt imports | SC, ATAS | Support-cost reducer; doubles as bug-report aid | M | Low |
| B11 | **Consequence-preview drag tooltips** — P/L in ticks while dragging SL/TP/levels (paper accounting is honest) | MT5 | Turns a drag into a decision; no look-ahead | M | Low |
| B12 | **Undo + multi-select for markings** — bounded to local reversible things (drawings, notes, level edits) | NT, MT5 | Drawings are cheap to make, currently expensive to fix; never near execution | M | Low–Med |
| B13 | **Zoom-level degradation rule** — footprint auto-switches to candles below a zoom, user-disableable, hysteresis-banded | ATAS | Change what is drawn, not how fast it draws | S–M | Low-Med |
| B14 | **UI scale + font zoom + DPI audit** — `--ui-scale` custom property, Ctrl±, per-monitor DPR re-read on resize/move, canvas text scaler | MT5, BM | The field's loudest accessibility failure, fixed app-wide; verify on 150%/200% | M | Low |
| B15 | **Contrast tiers** — 2–3 named readability tiers (Calm/Standard/Aggressive) layered on existing palettes | SC | Handles "too small" with layout+contrast, not just size; screenshot-check per tier | S–M | Low-Med |
| B16 | **Price-scale as an interactive object** — right-click the value scale → move/auto/interactive, plus a reset-scales command | SC | Cheapest fix for "my level is off-screen"; behind right-click only | S | Low |
| B17 | **Link-group colour on the titles + colour-sync semantics** | NT, QT, ATAS | Group membership readable at a glance; pair colour with the existing letter for CVD | S–M | Low |
| B18 | **Palette deep-launch + typed overlay selector** — one field that also opens surfaces/instruments pre-loaded (`@INSTRUMENT`-style tokens) | MT5, NT | Keyboard-first path to any surface with no menu depth | M | Medium |

### Wave C — larger, gated, or requires a decision

| # | Item | From | Note |
|---|---|---|---|
| C1 | **Study/expression instance identity** — instance IDs (not type IDs), Inputs separated from display settings, duplicate-with-independent-inputs | SC | Touches the studies/expression API; do after B1 so the settings UX lands first |
| C2 | **In-app AI coach over local data** (journal/replay insights) | NT | **Only if local and keyless**; high risk otherwise — parked pending owner decision |
| C3 | **Global search index** spanning registry + help + rail + settings, with drift tests | MT5, BM | Medium risk: an index that lies is worse than none; build after B1's search exists |
| C4 | **Ingest telemetry strip** (the fuller version of A5/A6) | BM | Cheap to sketch, easy to over-build; scope to ~6 honest fields |
| C5 | **Alert tiles with act-on-click into the Journal** | QT | Composes B7 with the §95 journal; after B7 |

**Sequencing note.** Wave A items are individually shippable and reversible. The three best-value starters
(T1–T3 below) can ship as one package this week. Nothing in any wave touches live execution — routing
remains a separate owner decision that follows the paper-simulator path.

**T1–T3 proposed first package (my recommendation, awaiting approval):**
1. **A1 contextual help wiring** — per-panel help entry + F1 + blank-state topic links.
2. **A13+A2 window & layout trust** — master window list + clamp/restore + layout lock.
3. **A3 armed hotkeys + A4 legend + A18 paper-ticket safety row** — the order-adjacent safety trio, now
   that the paper simulator exists.

---

## 6. What we deliberately do not take

- **Quantower's Workspace → Bind → Group triple hierarchy** and proportional-resize super-panels: genuinely
  good in a multi-window shell; large, gesture-heavy, high-blast-radius here (their own 1.146.13 episode is
  the evidence of cost).
- **A docking-manager rebuild** and multi-window-OS-first models: ModFlow stays single-window + terminal
  mode; we take window *safety* from the field, not window *plurality*.
- **Force-update windows / entitlement-gated UX / accounts as requirements**: against keyless-first and
  against the app's own updater policy.
- **Always-on 40 FPS GPU rendering budgets** (Bookmap's costs are its own cautionary data).
- **Marketplace / add-on commerce / copy-trading / VPS-style layers**: different businesses.
- **One-click irreversibility** (MetaTrader's documented no-confirmation closes): reversibility replaces
  confirmation in this app; never import the opposite.
- **Any code from proprietary products**: mechanisms only, as stated up top.

## 7. Non-negotiables restated

Classic mode stays untouched · keyless-first (no feed or feature may require an account) · local-first ·
no bundler / keep the vanilla-JS UI · every candidate lands non-destructively (flag or additive module,
never a rewrite) · the frozen `dist/` is rebuilt deliberately, never as a side effect · nothing is
committed or pushed without an explicit instruction.

## 8. Next step

This document is the plan for approval. Pick a wave, or approve T1–T3 as the first package; each item then
gets its own build pass with the standard gates and a handoff entry. The seven briefs under
`docs/ux-study/` are the checkable evidence behind every claim above.
