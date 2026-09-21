# ModFlow OrderFlow Analysis Suite — competitive reanalysis v3

**Prepared for:** Moddy (OrderFlow-Analysis-Pro)
**Date:** 21 September 2026, 15:40 ACST — run against the build as it stands, after the §147 upgrade package, the §148 final audit and the §149/§149b follow-ups.
**Supersedes:** `docs/COMPETITIVE_ANALYSIS_2026-09.md` (20 Sep, bench §146) and the two 19 Sep reanalyses. Those passes' findings were compiled into `docs/UPGRADE_PACKAGE_2026-09.md` and applied; this pass re-scores everything against the build that came out the other side.
**Scope:** Quantower · Bookmap · NinjaTrader 8 · MetaTrader 5 · Sierra Chart · ATAS — how the programs function (layout · interaction · GUI · technical advantages · product features), compared against ModFlow in all metrics — plus the adjacent tier, one acquired/defunct case, the market-norms model, and the improvement set that follows.
**Baseline (the tree the owner runs):** `git rev-parse HEAD` = `0eedc0d` ("§148–§149b — final audit closed + storage/systems follow-ups", 2026-09-21 14:56 +0930). Working tree **clean**; 81 commits ahead of `origin/master`, nothing pushed. The commit carries the whole §119–§149b wave: **219 files, +55,210 / −1,026 lines** against `797eea0`.
**Method:** every ModFlow claim carries a receipt taken from this tree today — a file, a counted grep, a test-suite result, or a live read from a sandboxed instance of the app (scratch `APPDATA`, ports 8097/8098, stopped after). Competitor prices and gates were **read from the vendors' own pages on 21 September 2026** and are labelled *vendor-stated*; the deeper "how it functions" material traces to the six sourced digests in `docs/ux-study/digests-2026-09-19/` and the two independent 2026 comparison articles named in §11. Nothing was read from memory; anything unverified is marked.
**Nothing in this pass changed code, and nothing was committed — it is an audit and a plan, as the passes before it.**

---

## 0. Why a third pass — and what changed since the last one

The last full pass (20 Sep, bench §146: 1,900 tests / 170 routes / 78 UI modules / 46 selftests / 86 help topics / 35 views) produced a three-part gap list. §147 applied it — **paid features excluded by instruction** — and §148 audited the result, closing a register of 113 findings (0 open) with a regression pin proven to bite for each. §149/§149b added the storage-card controls and the Systems-board fold. Everything is now committed as `0eedc0d`.

What that means in numbers, measured in this tree today:

| Metric | §146 (the last pass's bench) | Today (`0eedc0d`) | Receipt |
|---|---|---|---|
| Test suite | 1,900 passed | **2,494 passed / 3 skipped / 0 failed** | re-run this pass, 90.01 s |
| API paths | 170 | **192** | live `openapi.json` read this pass |
| UI modules (flat, non-selftest) | 78 | **87** (+12 under `indicators/` and `vendor/`) | counted |
| UI selftests | 46 | **57** (56 UI + 1 dashboard) | all green this pass |
| Help topics | 86 | **94** (8 groups, 42 view mappings) | counted via Node |
| Views | 35 | **43 walker-clean** (§148), 40 `data-view` sections | `audit_views.json` |
| py modules (desktop / atlas) | 25 / 34 | **27 / 40** | counted |

The gap list §147 responded to, item by item, as it stands now:

| Last pass's item | Status today | Where it lives |
|---|---|---|
| P0-1 live routing from the ladder | **Structure in, routing deliberately absent** — account-driver abstraction, risk gates, a paper driver that fills from real prints, a bridge driver that refuses in one sentence | `desktop/orders.py`; live read: `/api/control/trading/status` |
| P0-2 brackets / OCO / ATM | **Applied** — three shipped templates, bracket legs from the entry, OCO sibling cancel, break-even, trail, time stop, partial off at R; drawn on the ladder | `desktop/atm.py`, `desktop/ui/ladder.js` |
| P0-3 footprint configurability | **Applied** — 21 controls in an in-panel drawer, plus an annotation layer | `atlas/footprint_config.py`, `ui/orderflow.js` |
| P1-1 depth history + retention | **Applied** — price×time strip with pull/add marks, gaps, staleness, band profile; retention persisted (§148 fixed the in-memory-only write) | `atlas/depth_history.py` |
| P1-2 order-flow alert builder | **Applied** — AND/OR over 21 readings, cooldown scope, once-per-window, Test fire; §148 hardened the whole alert block (AB-01…AB-16) | `atlas/alerts.py`, `ui/alert-builder.js` |
| P1-3 alert payload enrichment | **Applied as the evidence block** (time, price, trigger, window delta, biggest prints, nearest walls, session) on every channel — text or CSV; the screenshot idea was not built | `atlas/alerts.py` + `atlas/notify.py` |
| P1-4 chart linking matrix + chart tabs | **Open** — no chart grid/tabs in the tree | — |
| P1-5 session templates + roll calendar | **Applied** — template model (timezones, breaks, holidays, early closes), built-in library, session phase/countdown, roll table for **20 roots** (17 futures + 3 perpetuals) | `atlas/sessions.py`, `ui/sessions.js` |
| P1-6 synthetic instruments | **Applied** — ratio/spread/basket/basis with weighted legs, carry-forward figure, z-score that refuses to exist on an unmoved composite; three starter definitions ship | `atlas/synthetic.py` |
| P1-7 trade analytics upgrade | **Applied** — R from the row's own stop/exit, expectancy in R, payoff, win/loss runs, MAE/MFE (**the writer now exists** — §148), per-setup/instrument/session splits, P&L calendar, plain-language sentences | `desktop/journal.py` |
| P1-8 read-only companion | **Applied** — mobile-first monitor page, five GETs only, a sentence for every refused panel; **loopback only** pending the host policy | `ui/monitor.html`, `ui/monitor.js` |
| P1-9 data-quality cockpit | **Applied** — per-instrument A–F scorecards from coverage/gaps/duplicate/out-of-order/staleness, repair hints naming real routes | `atlas/dataquality.py` |
| P1-10 publish measured performance | **Applied** — `docs/PERFORMANCE.md`, measured on this host; the render-side FPS figure is explicitly *not* claimed | `scripts/bench_atlas.py` |
| P2-1 options × flow confluence | **Open** (the confluence work only — the options stack itself is live) | — |
| P2-2 explainability as a feature | **Applied** — 25 reads labelled measured / inferred / computed, wired to 19 readouts, the build fails if a `data-why` has no explanation | `ui/why.js`, `test_why.py` |
| P2-3 crypto derivatives context | **Applied** — funding / OI / basis per venue through each venue's own interval; live read below | `atlas/derivatives.py` |
| P2-4 local scripting + study gallery | **Open** | — |
| P2-5 onboarding as a moat | **Partly** — seven help topics joined; layout packs and the interactive first-run checklist are still open | `ui/help-data.js` |

**So this pass's job is not the same list.** The P0s of September are closed or deliberately refused; what remains is a shorter, sharper set — named in §6 and ranked in §7 — and the market-norms table (§5) can now be scored honestly across the whole board.

---

## 1. Executive summary

**Where the build stands.** The analytics mandate the last two passes laid down is complete, and the practice loop around it is now real: a paper desk with ATM templates, brackets, OCO, break-even, trailing and a time stop; risk gates that actually bind (a §148 fix — the gates could previously never fire because the session router was never bound); a refusal-only live path that says in one sentence why a live order cannot exist in this build; a footprint whose settings surface is now ATAS-shaped (21 controls); a depth-history strip; session templates with a roll calendar; synthetic instruments; a data-quality cockpit; crypto derivatives context (live-verified this pass against four venues); a mobile-first companion page; and an explainability registry that labels every read as measured, inferred or computed. All of it keyless, local, account-free, and none of it gated.

**What genuinely remains, in order of importance:**

1. **The execution axis is now structurally complete but functionally capped — by design.** The market's money axis is routing (Bookmap gates one-click trading at Global+; Jigsaw charges $50/mo purely to trade live; NinjaTrader exists to route futures). ModFlow now has the whole grammar around it — templates, gates, refusals, ladder plan bar — and no counterparty. That is still the correct call until a broker adapter can ship complete and tested; what changed is that "no execution" is now a *boundary of a shipped layer*, not a missing layer.
2. **Charts are the weakest remaining surface.** No chart tabs, no 2×2 grid, no per-pane linking matrix — against Sierra's global cursor + linking and Quantower's panel model. The shell already links symbols across panels; the grid itself is a UI project of its own (the deliberate deferral of §147 P1-4).
3. **Reach: companion page exists, but the host binds loopback.** NinjaTrader and MT5 ship mobile; Bookmap and ATAS don't. ModFlow's monitor page is a genuine differentiator the moment a host policy exists — and a liability to advertise until then, because the help topic says so plainly.
4. **Numbers the market buys on.** Exocharts, ATAS and Bookmap all quote FPS/cluster claims; ModFlow now publishes ingest/snapshot/alert numbers but still has no render-side FPS harness — the honest position, and the next measurable win.
5. **Ecosystem and MBO stay out** — no third-party add-on market, no market-by-order data. Both are data/contract decisions, not code decisions, and both are correctly labelled as inferences until then.
6. **The small honest remainder:** study-pack gallery + user-scripted studies, layout packs + a first-run checklist, footprint-region export (the heatmap exports; the footprint view doesn't), stop-limit/MIT order types in the paper grammar, and the standing handoff follow-ups (radar walls / big-trade zones, spent-state persistence, config slots).

**Recommendation — unchanged in direction, sharper in scope: ship the analytics layer with the practice loop as shipped.** Close the five cheap items in P0/P1 below (chart tabs, host policy + mobile honesty, render FPS harness, footprint export, study/layout packs), keep broker routing and MBO out until each can ship whole with its credential and data-contract story answered, and re-run the norm table after the next wave. The build no longer needs to catch up on features; it needs the last few surfaces an experienced paid user checks first.

---

## 2. The market as it stands today (prices read 2026-09-21)

*Every figure in this section is vendor-stated as published on the date read; the digests behind the functional descriptions are dated 2026-09-18/19. Prices and gating move monthly — re-verify before public copy.*

### 2.1 Bookmap — the liquidity visualiser
**Identity.** Heatmap-first visualisation platform (Java/OpenGL), Windows/macOS/Linux. Free **Digital** (delayed US stocks/futures, real-time crypto, **1 symbol** at a time) → **Digital+ $19/mo** ($16/mo billed yearly, 3 symbols) → **Global $49/mo** ($39 yearly; **lifetime $990**; 10 symbols) → **Global+ $99/mo** ($79 yearly; **lifetime $1,990**; 20 symbols). **Data is billed separately:** BookmapData $34–79/mo (per-exchange $34; CME bundle $79; first-month promos $17/$29), dxFeed futures $37/mo per exchange, US equities $34–119/mo, Rithmic $40–101/mo. Backfill is tier/provider-shaped: 1h / 3h / 24h / 7 days. **2026 facts, read today:** Bookmap is **no longer independent — Nelogica (Brazilian fintech) acquired a majority stake (announced via press release; PitchBook dates it 30-Oct-2024)**. Current line: **7.9 build 6 (17-Sep-2026, beta channel)**; the newest production-labelled line is 7.8. BookmapData requires a **Global or Global+** plan, and the deepest order-flow set — **Footprint, DOM Pro, Execution Pro, Multibrackets, Multibook Customizer, Sweep/Absorption indicators, cross-trading** — is **Global+ only**; several other add-ons (order-book & volume imbalance, large-lot tracker, strength indicator) are marked **"Replay mode only"** below Global+. Independent sentiment: Trustpilot **4.4/5 from 603 reviews** — the heatmap and the education are praised, the recurring complaint is price and add-on stacking ("you have to pay extra for almost everything").
**How it functions (digest + prior passes).** One main window, instruments as tabs; the heatmap is the spine, everything else is rails (per-price columns: order book, profile, counters, quote delta, T&S, DOM, notes). The canvas grammar is the craft: cursor-anchored wheel zoom, axis-drag zoom, hold-D drag mode with pixel/10-px arrow nudge, anti-flicker hysteresis, vertical smoothing, percentile *or* exact cut-offs, dimming, large-size highlight, apply-globally.
**The paid gates tell the story.** Reading the tier table as a shopping list of what buyers demonstrably pay for: CVD, Large Trades Alert, Market Pulse, DOM Pro, Execution Pro, Footprint, Multibrackets, Multibook Customizer, Sweep — several of them marked *"Replay mode only"* on the lower tiers. Education, indicators and third-party add-ons sit in the marketplace, sold separately.
**Take / avoid for ModFlow.** Take: the estimation-labelling discipline (ModFlow's inferred tags are the stronger version), per-column reset modes, range-to-table events list. Avoid: entitlement-gated history and one-click trading, density-by-default, scattered settings.

### 2.2 ATAS — the footprint specialist, now reaching into options
**Identity.** All-in-one order-flow platform on **your own feed** (no seller-side data price list is published). **START €0 / PLUS €24.95 / PRO €69.95 / ULTRA €89.95 per month** (yearly rates €19.95/€39.95/€49.95/month; lifetimes **€999 / €1,799 / €1,999**); the four-tier structure dates from 12-Aug-2025, and 1-year plans carry a subscription "freeze" the short plans don't. **Tier gates, read today:** simultaneous assets 2/6/20/unlimited; indicators per chart 3/6/12/unlimited; **real-time futures and stock data are Pro/Ultra only** (Start and Plus are 15-minute delayed); **replay starts at Plus**; cross-trading Pro/Ultra; **Risk Manager (new, Sep 2026)** from Plus. **Ultra carries the MBO Bundle** (Iceberg/Stop-Runs/Sweeps trackers; needs a Rithmic connection) — **with the vendor warning that the bundle "may become paid for all subscription types later this year"** — plus the **Options Board (beta), Options Strategy Analyzer (beta) and options indicators via Interactive Brokers**, and ATAS + **ATAS X (beta, Windows + macOS)** in one subscription. Current build: **Beta 8.0.15 (4-Sep-2026)**, which redesigned replay into a single compact panel; the newest Stable-labelled entry is 7.0.9 (Nov 2025) — no single version string is published. Big Trades history: 7 days on the paid tiers today, with 30/90-day depth marked "coming soon".
**How it functions (digest).** Real docking — modules drag-merge into one window, quadrant drops, centre-drop collapses to a tab; two-tier persistence (workspaces with an Edit mode, layouts with a Universal layer) plus module templates; symbol sync by colour group; one-click mode as a master switch mirrored as a visible Lock; type-from-column+price order entry with a **held-modifier override and a cursor tooltip stating the operation before it fires**; data-semantic colour schemes; density knobs on every surface; zoom-level degradation (footprint → candles) — already mirrored on ModFlow's Engine.
**What it teaches.** The money is in **depth of configuration** — bar construction, cell contents, imbalance thresholds (stacked/diagonal), size filters, session filters, POC/VA per bar — which is exactly the drawer ModFlow now ships (21 controls). Second lesson, new this pass: **ATAS is moving toward options analytics** (beta boards, strategy analyzer on Ultra). ModFlow's GEX / vol surface / option flow stack is no longer "uncontested at the top" — it is early, not unique-forever.
**Where ModFlow is ahead.** Free versus €24.95–89.95/mo before data; crypto + equities + futures-via-bridge in one window; native options analytics as a shipped pair rather than a beta board; explainability; alerts that leave the building.

### 2.3 Quantower — the modern multi-asset terminal
**Identity.** Windows-only (.NET), broker-agnostic, 60+ connections. **ALL-IN-ONE license $70/mo** (3 months −10%, 6 months −20%, annual −30%, lifetime $1,690), free limited version, 7-day full trial, 10-day money-back. **Read today:** the free tier is real but thin — **1 connection, 2 indicators per chart, no footprint/cluster chart, no volume profiles, no market replay, no trading simulator** — though some brokers flip that: AMP's build and the **Optimus Flow white label** ship all paid features free to their clients. Extension **lifetime** prices are published too (DOM Surface $650, Volume Analysis $720, Option trading $690, …). Current line: **stable 1.146.18 (7-Aug-2026), beta 1.147.3 (12-Sep-2026)**; a **Risk Management panel** arrived in 1.147.1 (1-Sep-2026) — allowed trading times, open P/L limits, data-latency limit, balance/equity floors, with settings lockout when a rule fails. The lifetime licence **rose $1,590 → $1,690** between the Jul-2025 and Feb-2026 archived captures; monthly prices did not move. Independent sentiment: Trustpilot **4.7/5 from 362 reviews**; the criticism is runtime, not features — "lag during market open, news events"; recurring "desktop freeze when vola spikes" reports; "only missing a heatmap and a Mac version". **Extensions exist à la carte** and are the most instructive price list in the market: DOM Surface **$30/mo**, Power Trades **$25**, Volume Analysis **$35**, TPO Profile **$20**, Advanced features (Renko/Kagi/P&F/HA, unlimited overlays, RTD Excel) **$30**, Option trading (Option Desk, Option Analyzer, Greeks) **$50**. Data billed separately, always.
**How it functions (digest).** Every panel is a real OS window; persistence is four-layer nesting — Workspace (XML, autosave, **Lock**) ⊃ Bind (super-panel) ⊃ Group (tabs) ⊃ Panel (Template, Set-as-Default); right-click is universal with per-panel Help deep-links; parameterised hotkeys scoped focused-vs-global, trading keys behind an "Enable Keyboard Trading" arm; templates are shareable files. Documented pain is runtime trust (delays scaling with window count, memory growth over days) and **no settings search anywhere**.
**Take / avoid.** Take: per-panel defaults (ModFlow per-view defaults), armed trading keys (have), layout lock (have), template sharing (have via profiles/layouts versions), ala-carte feature pricing as a *market signal* — buyers pay separately for DOM Surface, Volume Analysis and Options. Avoid: the bind/group gesture hierarchy, entitlement-gated basics, settings sprawl without search.

### 2.4 NinjaTrader — execution with order flow attached
**Identity.** Futures execution platform + brokerage. **Free plan**: $0.39 micro / $1.29 standard **per side**; **Monthly $99**: $0.29/$0.99; **Lifetime $1,499**: $0.09/$0.59. Every plan includes top-of-book data, advanced charting, free simulated trading, third-party tool integration, and Desktop + **Web + Mobile**. **Order Flow+, Market Replay and real-time data unlock when the live account is funded** ("add funds… to unlock"); the Pulse indicator is the no-funding exception. $50 intraday margins on micros; exchange/clearing/NFA fees on top. **Read today:** ownership is the story — **Kraken announced the $1.5B acquisition 2025-03-20 and completed it 2025-05-01**, running NinjaTrader as a standalone platform ("by PAYWARD" now sits in the footers); **NinjaTrader itself bought Tradovate in 2022 ($115M)**, so the futures-brokerage lane (NinjaTrader + Tradovate) sits under a crypto exchange. Order Flow+ can be bought **standalone at $59/mo without funding**; release line **8.1.8 (8.1.8.2, 11-Aug-2026)** added Single Stock Futures; the **Static SuperDOM became free for all users in 8.1.7**. Order-entry safety: a **"Confirm order placement" popup** option, hot keys must be explicitly enabled, 10 retained workspace versions. Independent sentiment: Trustpilot **3.8/5 (1,226 reviews)** — "give it a facelift" is the standing critique; a **$35/mo inactivity fee** applies without round trades.
**How it functions (digest + prior passes).** Control Center is the always-on shell; every surface an independent OS window; ~20 window constructors in a flat catalogue; workspaces with 10 retained versions; context-valid right-click (order types limited to what the brokerage accepts on that side); freeze-on-hover on the ladder; graded ladder grammar (limit / MIT / stop-limit with a two-step modify); the Hot Keys window as the reference standard; dynamic title tokens; Safe Mode = hold Ctrl at launch.
**Take / avoid.** Take: title tokens (have), context-valid menus (have), freeze-on-hover (have), the Hot Keys standard (have), workspace version history (have via layout versions). The 2026 lesson stands: **mobile parity is expected** where the platform has a broker behind it. Avoid: account/server coupling, modal-heavy flows, add-on liability.

### 2.5 MetaTrader 5 — the industry default
**Identity.** The distribution play: free at point of use because the broker pays; desktop/web/mobile; MQL5 market/signals/VPS as upsells. No native footprint — every order-flow read on MT5 comes from third-party indicators, which is the hole **ModFlow's MT5 bridge fills** (it reads MT5's feed and does the order-flow work itself).
**How it functions (digest + 2026 reads).** Dense compound shell: main menu, three toolbars, Market Watch, Navigator tree, chart switch bar (up to 100 charts), one Toolbox window, status bar carrying the active **template and profile names — always visible**. Position-aware menus (above/below price ⇒ sell/buy variants, pre-validated), drag-to-set SL/TP with live P/L tooltip, zero-confirmation destructive actions, user hotkeys silently outranking defaults. **Onboarding, corrected in this pass:** the earlier digest credited MT5 with a ">100 novelty-gated tips" system; the fresh read of metatrader5.com (Help table of contents + 2025–26 release notes) found **no such documented system and no Tip-of-the-Day** — what *is* documented is contextual tooltips (hovering a deal icon shows ticket/type/volume/symbol/prices) and the rebuilt web Help (the CHM format was retired in build 5800). The "novelty tips" claim is now marked **unverified**; ModFlow's own `ui/tips.js` stands on its merits, not on this sourcing. **2026 direction is AI, not order flow:** builds 6060–6180 (latest **6180, 3-Sep-2026**) add a built-in **AI Assistant with MCP tools** that can add indicators and read tester reports; build 5800 (16-Apr-2026) opens "the first stage of enhancements to the main trading dialog" — a built-in DOM and one-click toggles — and build 5430 (Nov 2025) replaced the legacy GDI chart renderer with Blend2D. Chronic wounds: no global font scaling; provenance never shown (the broker feed usually to blame but MT5 wears it). Independent sentiment: Trustpilot **1.4/5 (206 reviews)** — "the charts look like they were drawn by hand", "nearly as clumsy and frustrating as its predecessor".
**Take / avoid.** Take: novelty-gated tips (**already shipped here — `ui/tips.js`, "Try next" cards gated on the store, selftested**), position-aware menus as a *paper-ladder* pattern, always-visible active-profile name (still a small open nicety), per-symbol provenance depth (shipped §125 — the last-tick age rides the symbol titles). Avoid: zero-confirm destructives, broker-anchored shell, duplicated menus.

### 2.6 Sierra Chart — the power tool
**Identity.** Since 1996; dense, fast, deliberately unattractive; **monthly packages only — 26 / 36 / 36 / 46 / 56 USD per month** (12-month rates from ~16.9 USD/month; 35% multi-month discount), and the vendor states plainly there is **no one-time purchase, "never"** (page modified 2026-09-08). MBO data sits at the top package (12); external feeds are gated behind Integrated tiers. **Read today:** the gating is sharper than "Integrated tiers" — packages 3/5 are **Base** and **cannot connect to any external data/trading service (IB, CQG, Rithmic) or to the Denali feed at all**; external connectivity starts at package 10. **Numbers Bars, TPO Chart and the Market Depth Historical Graph are Advanced features** (5/11/12); **Market by Order is package 12 only** and, notably, **only orders ≥3 lots are transmitted and no historical MBO is recorded**. Every package includes the historical data service, FX/CFD data, a delayed exchange feed *with depth and MBO*, and the server-side **Simulated Trading Service** (unlimited sim on real-time or delayed data). Denali exchange fees, non-pro examples: CME with depth **$13.50/mo**, full CME Group with depth **$40.50**, EUREX EOBI $25, NASDAQ TotalView $17 — professional/no-trading-account rates run to **$145/mo** per CME exchange. **Current build 2954 (20-Sep-2026)**; 21-day full-feature trial.
**How it functions (digest).** The abstraction is the **chartbook, not the window**; one visible per instance; menus are the API (every line prints its shortcut, menus user-editable); the settings-panel grammar is the study's most copyable asset — modeless panels, per-field **A (accept)/C (revert)**, panel-level **OK / Cancel / Revert All / Apply All**, **View ▸ Show Original Values** diff, tokenised in-panel search; analysis units are instances, not types; study collections travel. Replay scales 0.1×–100,000× with synchronised charts and sim trading inside replay; the API is **ACSIL (C++ only)** plus an open **DTC protocol server** (headers updated 18-Sep-2026) so external apps can take its data or trade it. Failure modes: window traps (title-bar-less windows users can't reattach), settings overwhelm, per-object colour tables.
**Take / avoid.** Take: the window-recovery kit (ModFlow's master window list + reset + safe start is that capability shipped), explicit error states naming a help topic, depth-history graph (now shipped here), the Show-Original-Values diff (**still the open nicety in ModFlow's staged settings**). Avoid: menu-as-API without docs, per-object colour tables, multi-instance architecture.

### 2.7 The adjacent tier and how tools die
- **Jigsaw Trading (daytradr)** — DOM/counter-trading specialist; **lifetime licences for 2 PCs — Independent $579 (vendor-stated), Professional $879 / Institutional $1,979 (independent sources)** — and *execution* still costs **$50/mo or $500/yr** on top (SIM, demo and prop-eval trading free forever). Windows-only 64-bit (Macs via Bootcamp/Parallels); depth & sales ladder with automatic order-type and exit attachment, Reconstructed Tape, Pace-of-Tape gauges, Auction Vista heatmap history, cumulative-delta charts; brokers CQG/Rithmic/NinjaTrader/Tradovate/IB/MT5. The lesson stands: even a DOM-only tool charges for the execution half — ModFlow's paper desk mirrors the practice half of this product honestly.
- **Exocharts** — crypto-first order flow, dxFeed for CME/Eurex/Nasdaq. **Desktop Pro €49/mo (€43 3-monthly, €38 6-monthly), Web Premium €28/mo, free tier = 3 pairs on desktop**; footprint, DOM + tape, profiles, stacked imbalances, liquidations; **v3.7.0 (4-Jun-2026) added Rithmic — and trading is still disabled: "the Trading feature is not available on the Exocharts Desktop Pro platform"**. In crypto order flow, a missing number reads as a weak number: Exocharts sells on published rendering numbers (~60 FPS claim).
- **Aggr.trade** — free, no-login browser tape: price/volume/CVD/liquidation panels, big-trade and liquidation thresholds, 16 aggregated markets; the "free tier exists" bar in crypto. No pricing page located — "free" is observed access, not a published price.
- **MotiveWave** — multi-asset charting with an **Order Flow edition at $45/mo** (Community free / Standard $23 / PRO $94 / Ultimate $146; $105 buys an extra year of updates); Windows, macOS, Linux and mobile. Its footprint is renamed "Volume Imprint" (the MarketDelta trademark story below); MBO and a trade copier in the Order Flow edition. Segment: Mac/Linux traders who want order flow off Windows-only stacks — "best orderflow product for Mac users" is a recurring review line.
- **Investor/RT (Linnsoft)** — "Home of the Footprint": Core $50/mo, Professional Trader $125/mo, à-la-carte Profile $20 / Volume Analysis $20 / **Footprint $25** (VolumeScope RTX + Footprint RTX); RTL scripting + C++ RTX SDK; IQFeed/Rithmic/CQG/IB. Segment: veteran equities/futures data tinkerers — and historically the white-label engine that carried MarketDelta's Footprint.
- **TradingView (+ the Tradovate correction)** — Free / Essential $12.95 / Plus $29.95 / Premium $59.95 / Ultimate $199.95 (annual billing); **native volume footprint from Essential upward** (value area, POC, delta, imbalances, alerts; 1-tick intrabar data is "professional plans"), DOM pane only when the linked broker carries Tier 2 data. **Correction to the previous pass: TradingView does not own Tradovate.** Tradovate was acquired by **NinjaTrader (Jan 2022, $115M)** and NinjaTrader by **Kraken (completed 2025-05-01)**; Tradovate survives as a brand/brokerage (a Tradovate login opens NinjaTrader's desktop/web/mobile) and as a **TradingView broker partner** — a partnership lane, not ownership. The acquisition lesson holds twice over: platform continuity is an ownership question, and in this niche the acquirer has repeatedly been a *broker or exchange*, not a charting app.
- **CoinGlass** — the crypto derivatives data layer (OI, liquidations, funding, LSR) plus Legend footprint/heatmap; the audience *pays for aggregated derivatives context* — ModFlow's funding/OI/basis panel and `crossvenue` work is the seed of a stronger version of this. *(Carried from the prior pass; not re-read today.)*
- **The defunct case — MarketDelta (2003 → 2018 → absorbed).** The company that **created the Footprint® chart** (Trevor Harnett, 2003; white-labelled Investor/RT, then CQG from 2016) **filed for Chapter 7 in 2018** (single independent source — flagged; Wayback shows marketdelta.com redirecting from Nov 2016 and erroring 2019–2022). Users migrated platform-by-platform — Optimus Futures routed clients to Optimum Flow, Sierra Chart, CQG Desktop, MotiveWave, Bookmap and Jigsaw — and the *feature* migrated everywhere under local names: Sierra Chart "Numbers Bars", NinjaTrader "Volumetric Bars", MotiveWave "Volume Imprint", MultiCharts "Volume Delta", because "Footprint" remains a MarketDelta trademark. Its desktop lineage survives inside CQG — and CQG itself was **acquired by Broadridge (announced 2026-02-06, completion reported 2026-05-01)**. Checked and *not* dead: **Volumetrica** (reborn as Deepchart/DeepDom) and **Nanex** (NxCore feed business still operating, page stamped 2026-08-30).
- **How tools die:** TradingLite — dead, technology for sale; MarketDelta — dead, idea absorbed into every surviving competitor. The lesson, now with two case studies: **the moat is data and connectivity, not pixels** — which is why ModFlow's sharpest wedge is being the free, honest *layer* rather than pretending to be the pipe.
- **Trading Technologies** — institutional OMS/ADL/autospreader; not a competitor, but the vocabulary ("spreaders", "algos", "risk gates") ModFlow now meets in its orders layer. *Described from market knowledge; site fetch rate-limited previously — treat TT specifics as unverified.*

---

## 3. ModFlow as it stands (live tree + live receipts, 2026-09-21)

**Platform & architecture.** Single-window desktop app — pywebview/WebView2 shell over a FastAPI + SQLite backend, vanilla-JS UI with no bundler, Windows-only, open-source, local-first, keyless by default. Terminal mode turns panels into native widget windows; `--safe` starts without restoring them; headless mode and CLI exist for scripted runs. `0eedc0d` carries the full wave: 219 files changed, +55,210/−1,026 lines.

**Navigation & layout.**
- 43 views walk on the §148 audit walker with **0 flags** (`audit_views.json`); 40 carry `data-view` anchors in `index.html` today.
- Classic mode: rail + top bar (File · View · Layout · Drawings · Chart · Data · Profiles · Run · Keys · Tools · Help) + command palette + status bar. Terminal mode: widgets with tabs as OS windows.
- Persistence stack: **terminal layouts** (named, locked, versioned ×10, per-screen), **profiles** over **13 config blocks** (`PROFILE_BLOCKS`: data_source, instruments, atlas, ofx, studies, expression, ui, layouts, workspaces, watchlist, risk, audio, calendar — credentials and machine paths excluded by construction, restart subset = 4), per-view workspaces, template gallery, per-view "remember my settings" defaults.
- Window trust: master **Windows & layouts…** dialog (screens; open/close; Focus / Pin / Reset / Remove), `reset` re-places on the primary screen; unplug rescue **"Bring them home"** for stranded windows; hotkeys `Ctrl+Alt+W`, `Ctrl+Alt+Shift+→/←`; 10 snap shapes.

**Interaction.** One shortcut registry (`keys.js`): **39 dispatchable bindings + 6 documented rows across 12 modules** (re-counted today), scopes + priorities + typing guard, **Change / Reset / Reset all** with conflict refusal naming every owner; an **armed gate** for danger-marked bindings; `?` sheet renders from the same map. Per-panel help (`?` injected into every panel head, F1 answers for the panel in focus). Canvas grammar on the liquidity map: cursor-anchored wheel zoom, pan (middle/shift-drag), arrow nudge, Home = live, box select + export, hold-to-freeze on hover.

**Analytics breadth.** Heatmap/depth (leashed ceiling, percentile or exact cut, dim/highlight, global apply, time anchor, live Detail 100 ms–5 s), footprint (**21-control drawer** — live read today: cell metric, colour-by, imbalance mode incl. diagonal, two ratios, stack counts, min print/row size, absorption size + body limit, per-bar POC/VA, ticks/row, session filter/window, annotation marks), CVD + divergence, TPO/Profile incl. area profile, frames (six families), depth ladder, tape with freshness chips, trackers, the level radar, unfinished business + node persistence, VWAP bands, signals/strategy/performance, journal with the deep read (R from the row's own stop, expectancy, MAE/MFE writer, per-setup/session splits, P&L calendar, sentences), replay, alerts (rules + builder + Inbox + Telegram/ntfy/email/webhook + sounds), **depth history** (price×time strip, pull/add marks, gaps, band profile; live read: retention 30 min, 1,800 columns/symbol, counters for late/future/stale skips — the §148 fixes), **data quality** (A–F scorecards), **sessions** (template library + phase/countdown + **roll calendar, 20 roots**), **synthetic instruments** (3 shipped definitions incl. ETH/BTC ratio and BTC perp basis), **derivatives** (funding/OI/basis per venue; live read this pass: Bybit funding 0.00772%/8h → 8.45% APR, basis −4.31 bps, OI 56,552 BTC ≈ $4.61 bn, 4/4 venues OK), options stack (GEX/vol/flow/chains), fundamentals, news/calendar, scanner, market watch, performance sheet.

**The execution layer (the practice loop).** Paper + refusal-only bridge: `DRIVERS = ("paper", "bridge")`; risk gates (size, max size, max positions, daily loss cap) bound to the session router (§148 fixed the binding defect — a refusal records a refused row and keeps the ledger's id); **ATM templates** live-read today: `scalp` (8/12), `intraday` (8/20, BE 6, partial 50% at 8), `runner` (8/32, BE 8, trail 10/step 2, time stop 30 min, partial 50% at 8); `atm.oco()` cancels siblings by group; the ladder draws planned legs; **Lock trading** (`ui.paper_lock`) with flatten/cancel always live; one `submit()` door gating on armed + unlocked; the session ledger exports CSV. Refusals are sentences, not errors: *"live routing is off — this build has no broker connection, so orders only ever reach the paper account"*; *"no live account is configured in this build — a live order is refused here rather than filled"*; *"no paper session is open — start one on the Replay view first"*. Broker execution remains deliberately absent; no real order path exists anywhere.

**Data & feeds.** Exchange feeds (Bybit, Binance, OKX, Hyperliquid), MetaTrader 5, Alpaca (keyless equities lane), NinjaTrader (`ModFlowBridge.dll`), Bookmap (`OfapBridge.java`), Quantower DTC — an adapter for every competitor in this report as a data source, which no competitor offers back. News/calendar, SEC EDGAR, CoinGecko, Deribit options. The identity copy speaks the market's language: *"what a broker or exchange charges for its own data is between you and them"*.

**Help / onboarding / explainability.** Help Centre **94 topics / 8 groups** with search + autofill + Simple/Advanced, per-panel doors, F1-in-focus; the Guide; the wizard (12 express + 10 professional); **novelty-gated "Try next" tips** (`tips.js` — gated on the store, never on clicks, retire when the feature is used); the **why-registry** (`why.js`, 25 reads labelled measured / inferred / computed, 19 wired readouts, `test_why.py` fails the build if a `data-why` has no explanation). Per-symbol provenance depth (§125): the symbol's own title carries last-tick age and source.

**Storage & housekeeping (§149/§149b).** Storage card: usage breakdown (DB, WAL, logs, exports, backups, WebView2 caches), **Clear app cache**, **archive open / delete quarantine**, retention controls, a 2 GB size budget with an alert-shaped message; the Overview's Systems board folds and the fold is a **config setting** (`ui.systems_hidden`) — deliberately not localStorage, because the cache clear would wipe it.

**Quality gates re-run in this pass (final bytes, `0eedc0d`).**
- pytest **2,494 passed / 3 skipped / 0 failed** (90.01 s, `.venv` interpreter).
- **ruff 0.16.7 — all checks passed** (re-run this pass).
- `audit_ui_refs.py` **CLEAN** — 346 ids used by modules; 686 html ids + 380 created; **0 missing, 0 duplicate**; 154 modules parse.
- `audit_metric_hygiene.py` **CLEAN**.
- **57/57 node selftests green** (56 UI + dashboard).
- Live sandbox (scratch `APPDATA`, ports 8097/8098, stopped after): 13 of 15 probe paths answered 200 (the two 404s were my wrong guesses — `/api/control/version` does not exist, and `/api/atlas/derivatives` needs its `/SYMBOL` suffix, fetched successfully after); **192 API paths** in the live OpenAPI schema; trading status/templates, footprint config, depth-history, data-quality, sessions, synthetic, alert-rules, storage usage, monitor page — all served as described above.

---

## 4. Head-to-head matrices

### 4.1 All-metrics matrix

| Capability | ModFlow (today) | Quantower | Bookmap | NinjaTrader 8 | MT5 | Sierra Chart | ATAS |
|---|---|---|---|---|---|---|---|
| **Platform** | Win (pywebview; widgets as native windows; headless/CLI) | Win (.NET) | Win/mac/Linux (Java) | Win + Web/Mobile | Win/mac/Linux/web/mobile | Win (native) | Win (+macOS beta) |
| **Cost to trader** | **Free · open-source · keyless · no account** | $70/mo all-in (extensions $20–50) · lifetime $1,690 | Free → $19 → $49 → $99/mo · lifetimes $990/$1,990 · symbols 1/3/10/20 | Free ($0.39/$1.29 per side) → $99/mo → $1,499 lifetime | Free (broker-distributed) | $26–56/mo, **no perpetual ever** | €0 → €24.95 → €69.95 → €89.95/mo · lifetimes €999/€1,799/€1,999 |
| **Data cost on top** | exchange/broker APIs (free tiers); no subscription | billed separately | $34–79 (BookmapData) · $37/exch (dxFeed) · $40–101 (Rithmic) | $50–100+/mo typical | broker-defined | exchange-dependent, Denali first-class | own provider required |
| **Order-flow spine** | heatmap + footprint (21-control drawer) + CVD + TPO/profile + area profile + depth + tape + trackers + level radar + depth history | DOM Surface + footprint + profile + DOM Trader (DOM Surface & Volume Analysis paid) | heatmap-first + columns rail + CVD/footprint/DOM Pro gated by tier | footprint + cum delta + profile + SuperDOM (Order Flow+ needs funding) | third-party only | DOM + Numbers Bars + volume-by-price + **depth graph** + MBO (pack 12) | footprint + Smart DOM/Tape + profile + heatmap + **Ultra: MBO bundle, options beta** |
| **Order execution** | **paper only** (templates/ATM/OCO/BE/trail/time-stop, risk gates, ledger; live refused in one sentence — deliberate) | full | full (one-click gated at Global+) | full — its core | full | full | full (one-click + Lock, held-modifier) |
| **Brackets/OCO/ATM** | paper: 3 ATM templates, OCO, BE, trail, time stop, partial; live: none | ✓ | ✓ | ✓ (ATM rule sets) | pending management, no native OCO | OCO pairs | ✓ |
| **Workspace persistence** | layouts (+lock, versions ×10, per-screen) + profiles (13 blocks) + workspaces + templates | Workspace⊃Bind⊃Group⊃Panel + Lock | .bmw workspaces (shareable) | workspaces, 10 versions, one visible | profiles + templates (cycle keys) | chartbooks (portable files) | workspaces + layouts + templates |
| **Cross-view sync** | link groups A–D (symbol + timeframe), cursor spine | link colour on titles | master-slave charts | link buttons + Link All | chart switch bar | global cursor + chart linking | colour groups |
| **Hotkeys** | one registry, rebindable, conflict refusal, armed gate, printable sheet | parameterised, scoped, trading arm | one editable table | Hot Keys window | assignable; user keys outrank | global rebindable + trading gate | five sections, conflict warn |
| **Replay + practice** | replay + paper session; ledger records orders (tape + wall clocks) + CSV | paid simulator | ✓ (3 modes) | Market Replay (funded) | Strategy Tester | replay 0.1×–100,000×(stated) | tiered replay, resettable account |
| **Multi-monitor & window trust** | any monitor; per-screen layouts; master list + reset; unplug rescue; safe start | OS windows everywhere | detach w/ history of fragility | OS windows | detach | **window traps** (support board) | not documented |
| **Onboarding & help** | 94-topic Centre + F1-per-panel + wizard + Guide + novelty tips + why-registry | launcher + per-panel Help; **no settings search** | launchpad; steep curve | F1 + videos; "facelift" critique | tooltips only, no tip system (verified); dated UI | numbered docs, settings overwhelm | Learn Center + template gallery |
| **Alerts channels** | ui + Inbox + Telegram + ntfy + email + webhook + sounds + evidence block | in-app + telegram | in-app | in-app + email | alarms + push | in-app + email | audio + Telegram |
| **Settings discovery** | "Find a setting" + staging (Apply/Revert) + registry (param_registry ~80 knobs) | none | scattered | modal-heavy | none | modeless + A/C + Apply All/Revert All + **Show Original Values** | per-surface panels |
| **Data feeds & sources** | 9-value source matrix incl. adapters for **every competitor here** | 60+ brokers | BookmapData/dxFeed/Rithmic | brokerage + Kinetick | broker feed | Denali + external (gated) | own feed required |
| **Provenance & honesty** | inferred tags, freshness chips, live/warming/demo pill, last-tick age, why-registry (measured/inferred/computed) | status dots | **estimated depth labelled** | sim surfaces painted | never shown | n/a | limits documented |
| **Mobile / reach** | monitor page (read-only, **loopback only**) | — | — | Web + iOS/Android | web + mobile | — | ATAS X beta (desktop) |
| **Ecosystem / scripting** | internal modules + HTTP API; **no third-party market** | C# API + extensions | ~3 dozen add-ons + marketplace | **1,000s of add-ons** | **MQL5 market** | ACSIL C++ + study store | connectors + API + KB |

### 4.2 Feature matrix (the checklist a paid user runs)

Legend: **✓** have · **~** partial · **✗** gap · *(s)* vendor-stated.

| Capability | ModFlow | Bookmap | Quantower | NT8 | ATAS | Sierra | MT5 |
|---|---|---|---|---|---|---|---|
| Footprint chart | ✓ | ✓ (tier-gated) | ✓ (paid ext) | ✓ (OF+, funding) | ✓✓ | ✓ (Numbers Bars) | ✗ native |
| Footprint configuration depth | ✓ (21 controls) | ~ | ~ | ~ | ✓✓ | ✓✓ | ~ |
| Liquidity heatmap over time | ✓ | ✓✓ | ✓ (paid ext) | ~ | ✓ | ✓ (depth graph) | ✗ |
| Historical depth replay graph | ✓ (depth history) | ✓ | ~ | ~ | ~ | ✓ | ✗ |
| DOM/ladder | ✓ (paper) | ✓ | ✓ | ✓✓ | ✓ | ✓ | ✓ |
| Click-to-trade (live) | ✗ (refused by design) | ✓ (Global+) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Brackets/OCO/ATM | ✓ paper | ✓ | ✓ | ✓✓ | ✓ | ✓ | ✓ |
| MBO data | ✗ (MBP; inferences labelled) | ✓ | ~ | ~ | ✓ (Ultra bundle) | ✓ (pack 12) | ✗ |
| CVD / delta / absorption | ✓ | ✓ | ✓ (paid) | ✓ | ✓ | ✓ | ~ |
| Volume profile / TPO | ✓ | ✓ | ✓ (paid) | ✓ | ✓ | ✓ | ~ |
| Tick/volume/range/renko/reversal/delta frames | ✓ (6 families) | ~ | ~ (paid) | ✓ | ✓ | ✓✓ | ~ |
| Market replay + sim | ✓ | ✓ | ✓ | ✓ (funded) | ✓ | ✓✓ | ✓ |
| Alerts → Telegram/ntfy/email/webhook | ✓✓ (+evidence block) | ~ | ~ | ~ | ~ | ~ | ~ |
| Options analytics | ✓✓ (GEX/vol/flow/chains) | ~ (SpotGamma add-on) | ✓ (paid ext) | ✗ | ~ (beta, Ultra) | ~ | ✗ |
| Crypto derivatives context (funding/OI/basis) | ✓✓ (live, 4 venues) | ~ | ~ | ✗ | ✗ | ✗ | ✗ |
| Synthetic/spread instruments | ✓ | ~ | ✓ | ~ | ~ | ~ (spreads via studies) | ✓ (CFD) |
| Session templates + roll calendar | ✓ | ~ | ✓ (sessions manager) | ✓ | ✓ | ✓ | ✓ |
| Data-quality cockpit | ✓ | ~ | ~ | ~ | ✓ ("reload data") | ~ | ✗ |
| Crypto + equities + futures + FX in one UI | ✓ | ✓ | ✓ | ✗ | ✓ | ~ | ✓ |
| Multi-monitor + window recovery | ✓ (+ reset/unplug rescue) | ✓ | ✓ | ✓ | ~ | ~ (traps) | ✓ |
| Command palette / search-everything | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Settings search + staged edits | ✓ | ✗ | ✗ | ✗ | ✗ | ~ (+Show-Original-Values) | ✗ |
| Explainability of reads | ✓✓ (why-registry) | ✗ | ✗ | ✗ | ✗ | ~ (formulas documented) | ✗ |
| Third-party indicator ecosystem | ✗ | ✓✓ | ✓ | ✓✓ | ✓ | ✓ | ✓✓ |
| Mobile/web companion | ~ (loopback page) | ✗ | ✗ | ✓ | ✗ (ATAS X = desktop beta) | ✗ | ✓ |
| Free tier | ✓ (all of it) | ✓ (delayed, 1 symbol) | ✓ (limited) | ✓ (sim, chart) | ✓ (crypto, limited) | ✗ (trial only) | ✓ |
| **All-in monthly cost, futures trader** | **$0** | $49–99 + $34–101 data | $70 (+data) | $99 (+$50–100 data) or $1,499 once | €24.95–89.95 (+your data) | $26–56 (+exchange fees) | broker-defined |

---

## 5. Market norms — the industry-standards conformity table, re-tested

The expectations of experienced users in this niche, mined from the six digests and re-scored against today's build. Legend: **Met** · **Mostly** (one refinement named) · **Partial** (real piece still open) · **N/A-by-design** (deliberate divergence, stated as such).

| # | Area | Norm (who sets it) | Status | Receipt / note |
|---|---|---|---|---|
| 1 | Identity | Explicit "analytics layer beside your terminal", or BE a terminal | **Met** | `start.identity` topic, Guide, README; identity copy ($117) |
| 2 | Identity | "Market data is billed separately" in the market's own language | **Met** | identity copy; venue terms referenced |
| 3 | Identity | A free tier / trial is expected | **Met (leads)** | free, keyless, no account; replay + paper free — no competitor gives replay + order recording free |
| 4 | Identity | Cross-platform increasingly expected | **Gap (accepted)** | Windows-only; stated openly |
| 5 | Pricing | No entitlement gating of the product's own features | **N/A-by-design (leads)** | nothing tier-gated; keep it that way |
| 6 | Layout | Saved layouts survive restart; set up once, reuse | **Met** | layouts store + boot adoption |
| 7 | Layout | Named, versioned, restorable, exportable arrangements | **Met** | version rings ×10, restore-one-click, import/export, profiles |
| 8 | Layout | Layout lock | **Met** | `ui.layout_lock` + status chip |
| 9 | Layout | Multi-window/multi-monitor without traps + recovery path | **Met** | widgets on any monitor; master list + reset; stranded-window rescue; `--safe` |
| 10 | Layout | Templates/profiles travel between symbols/views and as files | **Met** | profiles (13 blocks, export-safe) + gallery + per-view defaults |
| 11 | Interaction | Comprehensive, rebindable, conflict-aware hotkeys | **Met** | registry + Change/Reset/Reset-all + conflict refusal |
| 12 | Interaction | Armed state for live-action keys | **Met** | armed gate + badge + spoken refusal |
| 13 | Interaction | Right-click menus offer only valid actions | **Met** | context-validity (§99 T6) |
| 14 | Interaction | Freeze a live canvas in place | **Met** | freeze-on-hover |
| 15 | Interaction | Cursor-anchored zoom, drag/arrow panning | **Met** | §120–§122 grammar |
| 16 | Interaction | Position-aware menus near order entry; held-modifier override with a cursor tooltip | **Partial** | paper token/ladder grammars exist; ATAS's held-modifier + pre-fire tooltip is **the one ATAS grammar still open** |
| 17 | Interaction | Drag with consequence preview (live P/L while dragging) | **N/A yet** | no drag-to-trade in the paper desk; applies when it lands |
| 18 | Interaction | Cross-view symbol sync | **Met** | link groups A–D + cursor spine |
| 19 | Analytics | Footprint + CVD + profile + DOM/depth + heatmap minimum | **Met** | plus area profile, radar, unfinished business |
| 20 | Analytics | Footprint configurability depth | **Met** | 21-control drawer; parity cases pinned Python↔JS |
| 21 | Analytics | Historical depth graph | **Met** | depth-history strip; retention now persists (§148) |
| 22 | Analytics | Session templates, exchange mechanics, roll dates | **Met** | sessions engine + 20-root roll table; DST/holiday boundaries pinned |
| 23 | Analytics | Synthetic/spread instruments | **Met** | ratio/spread/basket/basis; z-score refuses on unmoved composites |
| 24 | Analytics | Replay/practice loop with order recording | **Met (leads)** | replay + paper ledger (orders, tape + wall clocks, CSV); ATM templates on top |
| 25 | Analytics | Trade analytics: R, expectancy, MAE/MFE, per-setup splits | **Met** | `journal.py` deep read; MAE/MFE writer exists (§148) |
| 26 | Analytics | Alerts with conditions → actions, audio + push | **Met (leads)** | builder + evidence block on every channel; §148 hardened the block's honesty (AB-01…16) |
| 27 | Execution | Live routing from the DOM | **Partial (deliberate)** | layer + gates + refusals shipped; no counterparty — the standing gate |
| 28 | Execution | Brackets/OCO/ATM vocabulary | **Met (paper)** | 3 templates, OCO by group, BE/trail/time-stop/partials; identical semantics live when routing ships |
| 29 | Execution | Order-type breadth (limit/MIT/stop-limit…) | **Mostly** | paper: market/limit/stop; NT-style stop-limit/MIT not yet in the paper grammar |
| 30 | Data | Feed breadth + honest capability display | **Met** | 9-value matrix; adapters for every competitor; venue hints |
| 31 | Data | Per-symbol provenance (source, last tick, gaps, backfill) | **Met** | last-tick age on symbol titles; freshness chips; data-quality scorecards |
| 32 | Data | Data-quality tooling with repairable actions | **Met** | A–F scorecards, gap ranges, repair hints naming real routes |
| 33 | Data | MBO (market-by-order) for honest iceberg/spoof reads | **Gap (labelled)** | MBP only; inferred reads carry their tag — the honest ceiling |
| 34 | Visual | Dark default + theming + density | **Met** | dark/light/contrast palettes, density, accents |
| 35 | Visual | Perceptual heatmap controls (Bookmap-grade) | **Met** | percentile/exact + floor + gamma + smoothing + dim + large-highlight + global apply + leashed ceiling + time anchor + Detail |
| 36 | Visual | Global UI scale + DPI correctness | **Met** | `setScale` 0.75–1.5, `--ui-scale`, canvas DPI law |
| 37 | Visual | Colour never alone; colour-blind affordances | **Met — and unique** | Okabe–Ito palettes with **measured** separation (ΔE) in `expression.js`; no competitor in the study documents one |
| 38 | Visual | Estimated/synthetic data labelled | **Met** | inferred tags; freshness chips; demo pill; why-registry |
| 39 | Visual | Hover-to-number mirrored in a persistent info line | **Mostly** | hint cards + info lines; Bookmap's Information Bar mirror still the nicety |
| 40 | Settings | Modeless, searchable settings; staged edits | **Met** | "Find a setting" + staging (Apply/Revert) + param registry |
| 41 | Settings | Show-original-values diff | **Partial — still open** | staging exists; the diff view does not |
| 42 | Onboarding | Per-panel help deep-links; F1 in focus | **Met** | §96 T1 |
| 43 | Onboarding | Searchable help with autofill | **Met** | 94 topics, autofill, Simple/Advanced |
| 44 | Onboarding | Tips that fire only for never-performed actions | **Met** | `tips.js`, selftested; gated on the store, not clicks |
| 45 | Onboarding | Layout packs + first-run checklist | **Partial** | topics landed; packs/checklist open |
| 46 | Reach | Mobile/web companion | **Partial** | read-only monitor page exists; **loopback binds until the host policy lands** |
| 47 | Ecosystem | Third-party extendability | **Partial (deliberate)** | internal modules + HTTP API; no store — study packs are the honest seed |
| 48 | Performance | Published rendering numbers | **Partial** | ingest/snapshot/alert numbers published and honest; render-side FPS harness still missing |
| 49 | Trust | No telemetry, local-first, write-only credentials, CSP, non-blocking updater | **Met (leads)** | SEC-09 mask protocol, checksummed backups, CSP, update policy |

**Score:** of 49 norms, **36 Met (4 of them leaders)**, **8 Mostly/Partial**, **3 deliberate gaps** (live routing, MBO, cross-platform), **2 intentional divergences** (no entitlement gating, no ecosystem sprawl yet). Compared with the last pass, the *execution*, *footprint depth*, *depth graph*, *session mechanics*, *synthetic instruments*, *analytics depth*, *alert builder*, *data-quality*, *novelty tips* and *derivatives* rows have all moved from Partial/Gap to Met.

---

## 6. Findings — the honest remainder

### 6.1 Internal (ours, verified today)

The §148 register closed **113 findings, 0 open** (all P1s fixed; the last were alert-block honesty defects AB-01…AB-16 and the standalone fix that a builder failure can no longer be reported as "empty snapshot"). What the audits leave is the small standing queue:

1. **Chart tabs / 2×2 grid / per-pane linking matrix** — the deliberate deferral of §147 P1-4; the only structural layout surface an experienced user will look for and not find.
2. **Footprint-region export** — the heatmap exports regions/markers/events as CSV; the footprint drawer's selections do not (no export path in `orderflow.js`).
3. **Study-pack gallery + user-scripted studies** — needs a sandboxing story before a gallery; the internal study/strategy pipeline exists as the foundation.
4. **Layout packs + interactive first-run checklist** — a config-defaults job against the shipped workspaces; the onboarding copy is already there.
5. **Render-side FPS harness** — `PERFORMANCE.md` measures ingest/snapshots/alerts and says plainly a render figure will not be quoted until measured the same way the competitors claim theirs.
6. **Mobile host policy** — the companion page binds loopback; the page and help topic both say so.
7. **Standing follow-ups (handoff):** radar walls / big-trade zones · spent-state persistence · config slots.
8. **Paper-grammar gaps vs the field:** stop-limit/MIT order types; drag-to-amend; a held-modifier override with a pre-fire cursor tooltip (the one ATAS grammar not yet mirrored); position-aware context menus on the ladder (MT5 pattern).
9. **The Show-Original-Values diff** in the staged settings surface (Sierra's most-cited nicety; staging exists, the pre-change diff doesn't).
10. **Release hygiene:** dist/zip/SBOM/Setup were last rebuilt at §129c (pre-§147); a frozen rebuild over `0eedc0d` is owed before any publish, and commit/push is on the owner's word.

### 6.2 Field-derived (what the six still have that ModFlow doesn't)

1. **Live order routing.** Bookmap gates it at $99; Jigsaw charges $50/mo for it; NT/MT5/Sierra exist to route. ModFlow's refusal is correct today — but this is the axis the market's money actually buys, and it is the difference between "the practice loop" and "the desk".
2. **MBO data.** The ceiling for honest iceberg/spoof reads (Bookmap BookmapData, Sierra pack 12, ATAS Ultra's MBO bundle). Data-contract decision, not code.
3. **Third-party ecosystems.** NT's 1,000s of add-ons, MQL5 market, Sierra's study store, ATAS's API + KB, Bookmap's marketplace — none of which ModFlow should copy wholesale, but the *curated core* (a signposted, versioned study pack) is the honest half.
4. **Mobile parity.** NT ships iOS/Android; MT5 ships web+mobile. ModFlow's monitor page is the seed; the host policy is the gate.
5. **Rendering numbers.** Exocharts/ATAS/Bookmap sell on FPS and cluster counts; a published, re-runnable render benchmark is the missing half of `PERFORMANCE.md`.
6. **Chart-grid and linking depth** (Sierra's global cursor and chart linking; Quantower's per-panel defaults across a grid): ModFlow's link groups cover symbol/timeframe, not a per-pane matrix.
7. **Footprint metrics extras** (visible in the paid gates): OI-weighted cells, delta-by-price-row export, per-cell "time at price" — ATAS/Sierra territory; cheap additions to the new drawer.
8. **Coach/education depth** (Bookmap's courses, ATAS's KB, Jigsaw's education-led positioning): ModFlow's help corpus is already better than everyone's *reference* material, but there is no video walkthrough lane.
9. **Continuous-futures mechanics** (Sierra's back-adjusted continuous contracts; ATAS's "reload back-adjusted data"): ModFlow's roll calendar names dates but does not splice contracts — say so, or build the splice.

### 6.3 Where the last pass's alarm was wrong, or already answered — do not "fix" these

- **"No execution layer"** — now a shipped layer with gates, templates, refusals and a ledger; the *absence of a counterparty* is the policy, not a missing feature.
- **"Alerts are shallow"** — the builder + evidence block + §148's honesty hardening (scope gates, quarantine of malformed conditions, legal cap, window bounds) put this ahead of every competitor's alerting in the study.
- **"No performance numbers"** — published, measured, with the one honest hole named.
- **"No onboarding"** — Centre + Guide + wizard + inline cards + novelty tips; the tips layer now ships here with a stricter gate (store state, not click history) — note the MT5 attribution for it is unverified (§2.5).

---

## 7. Improvement suggestions, ranked

**Priority 1 — the cheap closes (days each, all internal):**

1. **Chart tabs + 2×2 grid + per-pane linking** — the last structural layout gap. Land it as a layout mode (grid of chart panes, each pane a link-group participant), reuse `links.js`, add one route + one selftest, extend `test_layouts.py`.
2. **Footprint-region export** — mirror the heatmap's region CSV: select a cluster/row range → export CSV through the existing `/export/save` path; pin the column shape in `test_footprint_config.py`.
3. **Render-side FPS harness** — drive the real page over CDP (the established probe pattern), measure frames/s at N clusters on the heatmap and the footprint, append a section to `PERFORMANCE.md`; publish only what the harness prints.
4. **Mobile host policy** — an explicit, off-by-default "allow LAN access" switch with a warning sentence, a README/help update, and a pinned refusal when off. This turns the companion page from an honesty liability into a shipped feature.
5. **Study-pack gallery (curated) + layout packs + first-run checklist** — one wave: a versioned pack manifest, three shipped layout packs (scalper, intraday, crypto-perp), and a first-run checklist wired to the existing wizard.

**Priority 2 — grammar parity and the small niceties (a polish wave):**

6. **Paper-ladder grammar:** held-modifier override with a pre-fire cursor tooltip (ATAS), stop-limit/MIT types, position-aware context menus (MT5), interval auto-centre + double-click centring.
7. **Show-Original-Values diff** in the staged-settings surface (Sierra).
8. **Footprint metrics extras:** OI-weighted cell metric, per-cell time-at-price, delta-row export.
9. **Continuous-futures splice** (or an explicit note in the roll card saying there is none).
10. **Active profile name in the status bar** (MT5's always-visible template/profile line) — the Profiles rail row carries a dirty badge; the name in the status bar is the missing half.
11. **Error-toast → help-topic wiring** (Sierra's numbered-topic habit, applied to runtime toasts).

**Priority 3 — the two gates and release hygiene (owner's timing):**

12. **Live routing** — only as one complete, gated mode: a broker adapter (DTC first) verified end-to-end against a simulator/real account, credentials story answered (the §146 feed-keys card is the pattern), risk gates + reconciliation + journal integration whole. Until then the refusal stays.
13. **MBO** — a data-contract decision; revisit when a feed is chosen; keep labelling iceberg/spoof reads as inferred until then.
14. **Rebuild dist/zip/SBOM/Setup over `0eedc0d`** and re-run the frozen battery; commit/publish on his word, drafts first.
15. **Cross-platform** — stays closed; revisit only on a concrete demand signal.

**What NOT to build (carried forward, still true):** entitlement gating of anything; OS-window bind/group gesture hierarchies; dock-manager clones; per-object colour tables; menu-as-API without docs; update mechanisms that block or restart; account/server coupling; an open add-on marketplace before a sandboxed SDK; density-by-default. And *do not* advertise the companion page as "mobile" until the host policy lands.

---

## 8. Positioning and pricing (unchanged direction, one addition)

- **Free core, forever.** Still the sharpest wedge against an $80–200/month all-in futures setup; the practice loop (replay + paper + ATM + journal) is now part of that free core, which no competitor matches.
- **Monetise the edges, not the basics:** cloud sync of workspaces/journal, hosted data for instruments the user cannot self-serve, education/drills. Keep footprint/DOM/practice free.
- **Advertise the two axes nobody else can claim:** "options flow and order flow in one window, on crypto *and* equities, with every read explained" and "your DOM, your data, your machine — no subscription, no telemetry". **Addition this pass:** the third claim — "a practice loop with real ATM grammar and a ledger, before you ever risk a cent" — is now demonstrably true and is exactly what prop-firm-era beginners are told to find.
- **State numbers** — now partially done (PERFORMANCE.md); finish with the render harness before quoting against ATAS/Exocharts/Boomap's FPS claims.

---

## 9. Sequenced roadmap

**Phase E — the cheap closes (next wave, days-to-two-weeks):** items 1–5 (chart tabs/grid, footprint export, render harness, host policy, packs). Each independently shippable, each test-pinnable, none touching the ingest engine.
**Phase F — grammar parity polish (a wave of its own):** items 6–11; the paper ladder's grammar made best-in-class while it is still cheap.
**Phase G — the gates (owner's timing):** item 12 (routing as one whole mode), item 13 (MBO decision), item 14 (rebuild + publish), item 15 (cross-platform on demand only).
**Standing:** the handoff follow-ups (radar walls / big-trade zones, spent-state persistence, config slots) and the CI/docs resync habit after each wave.

---

## 10. What ModFlow already beats every competitor on

- **Free, keyless, local-first, no account, open-source** — every competitor is paid, broker-owned, or funding-gated.
- **Adapters for every competitor in this report as data sources** — no competitor ingests the others.
- **Unified breadth in one window** — heatmap + footprint + CVD + TPO + area profile + depth + depth history + tape + trackers + level radar + sessions/roll + synthetic + derivatives + options + replay + paper desk + alerts + journal; competitors split this across price tiers and add-ons (Quantower's own price list is the proof: DOM Surface $30, Volume Analysis $35, Option trading $50, separately).
- **The practice loop, free and complete** — replay + paper with ATM templates, gates, ledger and R-analytics; Bookmap/ATAS/NT gate replay or trading by tier/funding.
- **Explainability as infrastructure** — 25 reads labelled measured/inferred/computed, enforced by a test; the market sells black boxes.
- **Colour-blind-aware palettes with measured separation** (Okabe–Ito, ΔE-checked) — none of the six documents one.
- **A window-recovery kit** — the exact class of failure Sierra's board loses days to.
- **Nothing one-click irreversible; armed + locked safety posture** — the opposite of MT5's zero-confirm deletes.
- **Settings search + staging, command palette, F1-per-panel, novelty-gated tips** — Quantower and MT5 have no settings search at all.
- **Test-enforced honesty** — `test_guide.py`, `test_why.py`, the audit pair, the pin-proof harness (155 cases, every pin proven to bite): the reason the help corpus and the refusals cannot silently rot.

---

## 11. Coverage, method and re-run recipe

**Inspected this pass (all read at the tree, this date):** `git` state and the `797eea0..0eedc0d` diffstat; `index.html` (40 `data-view` sections); `keys.js` (39 binds + 6 documented rows, 12 modules); `config_store.py` (`PROFILE_BLOCKS` = 13); `help-data.js` (94 topics / 8 groups / 42 mappings, counted via Node); `ui/` module list (87 flat non-selftest, 56 selftests); `atlas/` + `desktop/` module lists (40 / 27); `desktop/orders.py` (drivers, refusals, gates), `desktop/atm.py` (templates, OCO), `desktop/paper.py` (order types, MAE/MFE excursion writer), `desktop/journal.py`, `atlas/sessions.py` (`ROOTS` = 20), `atlas/footprint_config.py`, `atlas/depth_history.py`, `atlas/dataquality.py`, `atlas/derivatives.py`, `atlas/synthetic.py`, `ui/tips.js`, `ui/why.js`, `ui/expression.js` (Okabe–Ito palettes), `docs/PERFORMANCE.md`, `docs/UPGRADE_PACKAGE_2026-09.md`, `docs/COMPETITIVE_ANALYSIS_2026-09.md`, the §148 register (`AUDIT_REGISTER.md`) and the §149/§149b records.
**Gates re-run this pass:** pytest 2,494 / 3 / 0 (90.01 s) · ruff 0.16.7 clean · `audit_ui_refs` CLEAN (346 ids; 154 modules) · `audit_metric_hygiene` CLEAN · 57/57 selftests · live sandbox on scratch APPDATA (ports 8097/8098, stopped): 13 of 15 probe paths answered 200 (both 404s were wrong path guesses, resolved after), **192 API paths** in the live OpenAPI schema, trading/footprint/depth-quality/sessions/synthetic/alert-rules/storage/monitor all answering as quoted, and a **live four-venue funding/OI/basis read** for BTCUSDT.
**Vendor pages read 2026-09-21 (vendor-stated):** bookmap.com/pricing (tiers, symbol caps, data plan prices, backfill caps, add-on gates) · atas.net/pricing (Start/Plus/Pro/Ultra, lifetimes, Ultra MBO bundle + options beta) · quantower.com/pricing (all-in-one $70, extensions list with prices) · ninjatrader.com/pricing (free/monthly/lifetime commissions, funding-gated tools, margins) · sierrachart.com Packages page (26/36/36/46/56 USD, "no one-time purchase option… never", page dated 2026-09-08) · metatrader5.com (footprint absence; current build **6180, 3-Sep-2026**; trading-dialog redesign stage 1 in build 5800; Blend2D renderer in 5430) · **adjacent tier read today:** exocharts.com/pricing · jigsawtrading.com (+ Independent $579) · motivewave.com/products (Order Flow $45; /pricing.htm is 404) · linnsoft.com/pricing · tradingview.com/pricing + Tradovate broker page · aggr.trade · **ownership chain:** kraken.com + businesswire (Kraken/NinjaTrader completion 2025-05-01; NinjaTrader/Tradovate 2022 $115M) · prnewswire (Nelogica/Bookmap) · businesswire/broadridge (CQG).
**Second-tier evidence:** the six digests in `docs/ux-study/digests-2026-09-19/` (each claim carrying its source URL), the four same-day fact-refresh digests filed this pass at **`docs/ux-study/digests-2026-09-21/`** (bookmap-atas · quantower-sierra · ninjatrader-mt5 · adjacent-tier-and-defunct-case — each claim tagged vendor-stated/independent with its URL, and an explicit "could not verify" list), and the two independent 2026 comparisons named in `docs/COMPETITIVE_ANALYSIS_2026-09.md` §10 (treat vendor-authored comparisons as marketing).
**Caveats, stated plainly:** no live-app drive of the windowed UI this pass (the last live receipts are §148's; this pass drove a headless instance); competitor prices and gating move monthly — re-verify before public copy; the six named platforms' facts were read from their own pages today, and the adjacent tier (§2.7) was fact-refreshed from its own pages the same day (Exocharts, Jigsaw, MotiveWave, Investor/RT, TradingView, Aggr) with two corrections logged — **Tradovate's acquirer is NinjaTrader (2022), not TradingView, and Bookmap is majority-owned by Nelogica**; the MarketDelta Chapter-7 date rests on a single independent source; the MT5 ">100 novelty tips" claim from the prior digest could not be re-verified today and is marked unverified; the Trading Technologies note remains market-knowledge only; nothing here changed code or artifacts, and nothing was committed.

*End of report. Previous pass: `docs/COMPETITIVE_ANALYSIS_2026-09.md`; its application: `docs/UPGRADE_PACKAGE_2026-09.md`; its audit: the §148 register in `runtime/ofap_s148/AUDIT_REGISTER.md`.*
