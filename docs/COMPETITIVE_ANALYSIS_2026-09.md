# ModFlow vs the paid order-flow market — a competitive analysis

**Prepared:** 2026-09-20 · **Subject:** ModFlow OrderFlow Analysis Suite (OFAP), `C:\Users\Moddy\OrderFlow-Analysis-Pro`
**Bench build:** worktree at §146 (1,900 tests / 3 skipped / 0 failed · 170 API routes · 78 UI modules · 46 JS selftests · 86 help topics · 35 views · audit CLEAN, uncommitted)
**Method:** competitor facts read from the vendors' own sites and two independent 2026 comparison articles (sources at the end, all dated 2026-09-20); ModFlow facts read out of this build's own tree (file/module/route counts, feature lists, the alert-capability table in `atlas/api.py`, `PaperAccount`, the ladder's click grammar, §128 multi-monitor, §146 feed lanes). Vendor performance numbers are quoted as *stated*. Anything I could not verify is marked.

---

## 1. The one-paragraph verdict

ModFlow is **not** a weaker Bookmap or ATAS — it is a different product that has accidentally collected most of the same analytics, minus execution, minus a data empire, plus two things nobody else bundles: **equity + crypto options analytics (GEX / vol surface / option flow) inside the same order-flow window**, and **honest, testable, explainable reads** (every inferred signal is labelled inferred; every panel refuses in a sentence instead of lying). Against the five platforms you named it wins decisively on cost (free vs $19–99/mo + $34–119/mo data), on breadth per pound (35 views across crypto, equities, options, futures-via-bridge), on onboarding (86 help topics vs a docs portal), and on the options layer. It loses where the market's *paying* users actually spend their money: **live order routing from the DOM**, **market-by-order data**, **footprint configurability depth**, **third-party indicator ecosystems**, **mobile/companion access**, and **measurable microsecond-grade rendering claims**. The gap list below is ordered so that the first three items convert a "very good beta analysis tool" into "a platform an experienced paid user can live in".

---

## 2. The paid market, at a glance

| | Bookmap | Quantower | NinjaTrader 8 | ATAS | Sierra Chart | MetaTrader 5 | Jigsaw daytradr | **ModFlow** |
|---|---|---|---|---|---|---|---|---|
| Core identity | liquidity **heatmap** | multi-asset terminal, 60+ connections | futures **execution** + platform | footprint/volume analysis | configurable power platform | industry-standard multi-asset | **DOM / counter-trading** | order-flow **+ options** analytics |
| Price (stated) | Free → $19 → $49 → $99/mo; lifetime $990/$1990 | Free tier → $70/mo all-in, extensions $20–50 | platform free; lease $99/mo or lifetime $1,499 | Free → €24.95 → €69.95/mo; lifetime €999/€1,799 | ~$26–56/mo packages | free (broker carries it) | lifetime + $50/mo for live | **free** |
| Data cost on top | BookmapData $34–79, dxFeed $37/exch, Rithmic $40–101 | broker/exchange-dependent | $50–100+/mo (Kinetick/Rithmic/CQG) | exchange-dependent | exchange-dependent | broker-dependent | broker-dependent | exchange/broker APIs (mostly free tier) |
| Order-flow strength | heatmap, volume dots, stops/icebergs, Tradermap, DOM Pro | DOM Surface (paid), Volume Analysis (paid) | Order Flow+ (in licence) | footprint **leader**, Big Trades, 3D heatmap | Numbers Bars, MBO, volume-by-price | third-party only | DOM-first, tape, footprint | heatmap, footprint, CVD, TPO, VP, delta, frames, alerts |
| Execution from the DOM | yes (Global+ for futures/stocks) | yes (many brokers) | **yes — its core** | yes (cross-trading) | yes (incl. direct CME routing) | yes | yes (with live sub) | **no — paper + Alpaca read only** |
| MBO (market-by-order) | yes (BookmapData, CME/Nasdaq) | depends on feed | depends on feed | n/d | **yes** (CME/EUREX/CFE/Nasdaq TV) | no | no | **no** (MBP depth only) |
| Ecosystem / marketplace | large add-on marketplace | extensions + C# API | **1,000s of add-ons**, NinjaScript | 400+ indicators, API | ACSIL C++, store | MQL5 market (huge) | education-led | none (internal modules) |
| Mobile / web companion | web+desktop | desktop | **web + iOS + Android** | desktop | desktop | desktop/web/mobile | desktop | **none** |
| Options analytics | SpotGamma add-on | Option Desk/Analyzer (paid) | basic | — | options market support | — | — | **GEX, vol surface, option flow, chains (native)** |
| Honesty/explainability of reads | indicator marketing | indicator marketing | indicator marketing | indicator marketing | documented formulas | not applicable | documented | **inferred-vs-native labels, refusal sentences** |

Two structural facts fall out of that table:

1. **Every paid tool on this list is a subscription on top of a data bill.** The cheapest credible paid entry is ATAS Plus (€24.95) or Sierra (~$26) *before* exchange fees; the realistic all-in for a futures order-flow setup is **$80–$200/month** (NinjaTrader reviewers state $150–200/mo leasing, or $1,699–2,299 in year one on lifetime). ModFlow's marginal cost is zero. That is not a small thing in the prop-firm era, where traders pay Apex/Topstep for accounts on top of platform and data.
2. **The market's "moat" is data and connectivity, not pixels.** Bookmap's real product is BookmapData (MBO for CME/Nasdaq); NinjaTrader's is brokerage + Order Flow+ inside it; Quantower's is 60+ connections; Sierra's is DTC + direct exchange routing; MT5's is every broker on earth. Anyone comparing ModFlow to them purely on *features* will misread the market: the features exist to sell the pipe.

---

## 3. What experienced users in this niche actually expect — the 20-point norm list

Ranked by how often the norm decides a purchase (from the 2026 comparison articles and the vendor feature gates themselves — e.g. Bookmap gates *footprint, DOM Pro, one-click trading and symbol count* behind $99/mo, which tells you exactly what buyers pay for).

| # | Norm | Why it decides | ModFlow status |
|---|---|---|---|
| 1 | **Trade from the ladder** — click-to-trade with limit/stop/market, drag to amend, cancel by click | The single most-used surface in every paid DOM | **Partial** — click grammar exists (§118) but only into the paper account; no live routing, no drag-amend, no order templates |
| 2 | **Brackets / OCO / ATM strategies** (auto break-even, trail, time stops) | Risk management is the product | **Partial** — paper engine supports market/limit/stop; no OCO/bracket/ATM vocabulary exposed |
| 3 | **Footprint configurability** — bar type, cell metric (bid/ask/delta/vol/OI), imbalance ratio, stacked & diagonal imbalance, filter by size | ATAS's and Sierra's entire reputation | **Partial** — footprint + delta + imbalance + absorption exist; the *settings surface* is thin next to ATAS |
| 4 | **Liquidity heatmap over time** with pull/add detection and MM filtering | Bookmap's reason to exist | **Have** — heatmap + depthmap; no Tradermap-equivalent MM filtering |
| 5 | **Depth of market with full book** (MBP10+; ideally MBO) | Professional reads need order-level | **Partial** — MBP depth; no MBO (so iceberg reads are *inferred*, correctly labelled) |
| 6 | **CVD / delta divergence / absorption** | The bread and butter | **Have** — CVD, delta, absorption, divergence, speed of tape |
| 7 | **Volume profile & TPO** — developing POC, VAH/VAL, session + composite, extensions | Universal expectation | **Have** — profile view, volume profile + extensions, TPO |
| 8 | **Frames** — tick/volume/range/renko/reversal/delta bars | Universal; ATAS/Quantower gate some behind tiers | **Have** — range, renko, reversal, tick, volume, delta |
| 9 | **Market replay**, tick-true, with sim trading | Every platform sells this; educators live on it | **Have** — replay + paper session; speed range and depth-reconstruction depth unknown vs Sierra (0.1×–100,000×) |
| 10 | **Alerts with conditions → actions**, audio + push | Hands-free monitoring; prop risk rules | **Have (strong)** — rule kinds incl. sweeps/iceberg/stop-run/stacked imbalance/trapped traders; channels Telegram/ntfy/email/webhook; **once-only keys; eco-calendar lead alerts** |
| 11 | **Multi-monitor, detachable panels, workspaces/templates** | Desks are multi-screen | **Have** — terminal widgets, detachable windows, §128 multi-monitor shortcuts, layouts, profiles |
| 12 | **Keyboard-first operation** + command palette | Speed is the job | **Have (ahead)** — shortcut registry + a search-everything palette; most competitors have neither |
| 13 | **Charting depth** — many indicators per chart, drawing library, synced charts | Buyers compare indicator counts | **Partial** — 11 indicator modules, drawings, cursor spine; no indicator marketplace, no chart-linking matrix |
| 14 | **Sessions/exchange mechanics** — session templates, RTH/ETH shading, holidays, roll dates | Futures/equities correctness | **Partial** — calendar view + sessions data; no session-template editor, no roll calendar |
| 15 | **Data quality tooling** — backfill control, edit/repair, missing-bar flags | Traders blame the platform for bad data | **Have** — backfill, retention, freshness panel, storage audit |
| 16 | **Instrument breadth & mapping** — futures, equities, options, crypto, FX; symbol maps | "One window for my market" | **Have** — bybit/binance/okx/hyperliquid/deribit + Alpaca/Tradier/MarketData + MT5 & NT8 bridges + EDGAR; **mapping UI exists** |
| 17 | **Options analytics** — chains, greeks, GEX, vol surface, flow | Now a paid tier everywhere (Quantower $50, SpotGamma add-on) | **Have (ahead)** — GEX, volatility surface, option flow, chains; nothing else on the list bundles this |
| 18 | **Journal + trade stats** — P&L by setup, MAE/MFE, tagging | Everyone ships some; educators insist | **Partial** — journal + performance views exist; setup tagging/R-multiple analytics unverified |
| 19 | **Automation/API** for strategies and third-party work | Quantower C#, NT NinjaScript, Sierra ACSIL, ATAS API | **Partial** — internal study/strategy pipeline + HTTP API; no user-scriptable strategy host |
| 20 | **Mobile/companion + community/education** | NinjaTrader ships iOS/Android; Bookmap/ATAS sell courses | **Gap** — no companion app; help corpus is excellent but there is no video library/community |

---

## 4. Platform-by-platform: how they function, and what they'd teach us

### 4.1 Bookmap — the liquidity visualiser
**Layout/interaction.** One dominant canvas: time on X, price on Y, colour = resting size, bubbles = executed volume, BBO lane, plus panels for the book and add-on sub-charts. The entire interaction model is "point at a wall, watch it pulled, react". Nanosecond zoom (vendor-stated 40 fps) is the selling point; it exists because that is the only way to see pull/add intent before it becomes price.
**Paid gates that matter:** one-click trading and footprint only at Global+ ($99); symbol count capped (1/3/10/20) by tier — the licence is really "how many charts may I watch". Data sold separately.
**Features ModFlow should study:** Stops & Icebergs tracker (dedicated, MBO-fed), Tradermap Pro (filters market-maker noise so the human liquidity is visible), Market Pulse (large trades/sweeps/momentum in one feed), Multibook (consolidated multi-venue book), DOM Pro/Execution Pro, and the **add-on marketplace** as a revenue and retention engine.
**Where ModFlow already beats it:** crypto *and* equities *and* options in one window; inferred-signal honesty (Bookmap sells black-box indicators); free; alerts that leave the building (Telegram/ntfy/email/webhook) rather than only ringing a bell.

### 4.2 Quantower — the modern multi-asset terminal
**Layout/interaction.** Panels are first-class objects: place any panel on any screen, group them, bind them (symbol/timeframe linking), save group/bind/template, per-panel defaults. 40+ panels (chart, DOM Trader, DOM Surface, TPO, Option Analyzer, market replay, order entry, multiple order entry, positions/orders/trades, account performance, alerts log, news, reports, symbol mapping, sessions manager, backup manager, stat matrix, quote board…). 60+ connections, simultaneous, plus synthetic symbols and spreads.
**What it teaches:** the *panel**+**binding**+**template** model is exactly the workflow ModFlow's terminal/layouts/profiles already approximates — and Quantower proves buyers pay for **per-panel settings that persist as defaults** and for **synthetic instruments** (legs you define and trade as one chart). It also proves the freemium ladder: free terminal, paid extensions ($20–50 each), all-in $70.
**Where ModFlow is behind:** live order routing across brokers, synthetic/spread instruments, session manager, RTD/Excel export, copy trading.
**Where ModFlow is ahead:** the study/indicator framework is native and free; the help corpus dwarfs help.quantower.com in trader-facing language; the crypto-options stack (Deribit GEX/vol/flow) has no Quantower equivalent without the $50 option extension.

### 4.3 NinjaTrader — execution with order flow attached
**Layout/interaction.** Multi-window, SuperDOM, Chart Trader, Order Flow+ visualisations; windows are independent and multi-monitor is assumed. Ecosystem is the moat: **1,000s of third-party indicators/strategies** on a C# framework, plus web and iOS/Android companions that stay in sync.
**What it teaches:** (a) the platform is free because the brokerage is the product — the "free + data/execution monetisation" model ModFlow could adopt one day; (b) **Order Flow+ ships inside the licence** — buyers expect footprint/DPT/etc. as part of the paid tier; (c) mobile parity is expected in 2026.
**Where ModFlow is behind:** execution, add-on ecosystem, mobile.
**Where ModFlow is ahead:** no $99–$1,499 licence and no $50–100/mo data bill; footprint and DOM tools are not gated.

### 4.4 ATAS — the footprint specialist
**Layout/interaction.** Chart-first, with Smart DOM, Time&Sales (big-trade filtering), 3D heatmap + bubbles, market replay, cross-trading between connected accounts, and a documented API for custom indicators/strategies. Vendor-stated 600+ FPS and "all standard, unique, and custom frame types" — the *configurability of the footprint itself* is the product. Pricing: free START (crypto only, limited) → €24.95 Plus → €69.95 Pro; lifetime €999/€1,799; 360k-trader community claim.
**What it teaches:** the money is in **depth of configuration**, not in the number of panel names. A serious footprint buyer wants to control: bar construction, cell contents, imbalance thresholds, stacked/diagonal imbalance, filters (min size, session, exclude MM), historical depth of "Big Trades" (7 days auto-filter on Pro), and data self-repair ("reload back-adjusted data" — ATAS's stated differentiator vs Bookmap/NinjaTrader).
**Where ModFlow is behind:** the footprint settings surface, Big-Trades history depth, self-serve data reload UX.
**Where ModFlow is ahead:** options analytics, free, crypto+equity+futures-via-bridge breadth, explainability, alerts delivery.

### 4.5 MetaTrader 5 — the industry default
**Layout/interaction.** Market Watch + chart windows + Navigator, DOM ("Market Depth") per symbol, EAs, the Strategy Tester, MQL5 marketplace/signals/VPS, desktop + web + mobile. It is the lingua franca of retail FX/CFD and a huge share of brokers.
**What it teaches:** footprint is *not* native — every order-flow read on MT5 comes from third-party indicators, which is precisely the hole ModFlow's MT5 bridge fills (ModFlow reads MT5's feed and does the order-flow work itself). Also: the ecosystem (Market/Signals/VPS) is why MT5 is unkillable, and why ModFlow should treat "third-party extensions" as a roadmap item rather than a nicety.
**Where ModFlow is behind:** mobile/web reach, EA-grade automation, broker ubiquity.
**Where ModFlow is ahead:** everything order-flow; MT5 has no native footprint, no heatmap, no CVD panel.

### 4.6 Sierra Chart — the power tool
**Layout/interaction.** Everything is a window: charts, ChartDOM, spreadsheets, T&S, quote boards; chart **linking** (symbol/period/scroll/session) and a **global cursor** across charts; detachable windows for multiple monitors; chartbooks and tabs. Numbers Bars (footprint) with **stacked imbalance** highlighting, Volume-by-Price with drawn profiles, **Market Depth Historical Graph**, and **MBO** data for CME/EUREX/CFE/Nasdaq TotalView. Programmable via ACSIL (C++) and Excel-compatible spreadsheets; DTC protocol; direct CME routing at $0 transaction fees; replay 0.1×–100,000×; tick-true bars of any type (seconds…delta…renko…P&F); continuous futures with back-adjustment; CSV import/export and manual data editing; offline analysis. Interface is dated; learning curve is steep — the 2026 reviewers all say so.
**What it teaches:** (a) **chart linking + global cursor** is table stakes at the top end — ModFlow's "cursor spine" is the same idea and should be advertised as such; (b) **depth history** (store L2 over time, then replay the book as a graph) is a killer feature ModFlow can build cheaply because it already persists ticks and renders depth maps; (c) MBO is the ceiling for honest iceberg/spoof analytics.
**Where ModFlow is behind:** MBO, ACSIL-grade user programming, session templates, continuous-futures mechanics, cheapest-credible-pricing (Sierra starts ~$26).
**Where ModFlow is ahead:** UI modernity, help/onboarding, options analytics, crypto coverage, honest refusals (Sierra's UI assumes a power user; ModFlow assumes a trader).

### 4.7 The adjacent tier (context, not comparison targets)
- **Jigsaw daytradr** — DOM/counter-trading specialist; lifetime licence on 2 PCs, **$50/mo for live trading**. Lesson: even a DOM-only tool charges for *execution*.
- **Exocharts** — crypto-first professional order flow (Desktop Pro + Web), dxFeed for CME/EUREX/Nasdaq, up to 6 years of BTC tick data, vendor-stated ~60 FPS with "15M bid-ask clusters per frame" on desktop vs 10–20k on web. Lesson: **publish your rendering numbers** — the crypto order-flow market buys on them.
- **CoinGlass** — the crypto derivatives data layer (OI, liquidations, funding, LSR) plus Legend footprint/heatmap and a public API. Lesson: the crypto audience already pays for *aggregated derivatives context*; ModFlow's `crossvenue`/liquidation work is the seed of a stronger version of this.
- **TradingLite** — dead; technology for sale. Lesson: order-flow platforms without a defensible data/execution edge do not survive on rendering alone.
- **Trading Technologies** — institutional order management, ADL algos, autospreader; the professional ceiling. Not a ModFlow competitor — but it defines what "professional" means to the desks whose vocabulary (spreaders, algos, risk gates) ModFlow will eventually meet. *(Site fetch rate-limited at time of writing; described from market knowledge, not quoted — treat TT specifics as unverified here.)*

---

## 5. Feature matrix (the checklist a paid user runs)

Legend: **✓** have · **~** partial · **✗** gap · *(s)* vendor-stated.

| Capability | ModFlow | Bookmap | Quantower | NT8 | ATAS | Sierra | MT5 | Jigsaw |
|---|---|---|---|---|---|---|---|---|
| Footprint chart | ✓ | ✓ (add-on) | ✓ (paid) | ✓ (OF+) | ✓✓ | ✓ (Numbers Bars) | ✗ native | ✓ |
| Footprint configuration depth | ~ | ~ | ~ | ~ | ✓✓ | ✓✓ | ~ | ✓ |
| Liquidity heatmap over time | ✓ | ✓✓ | ✓ (paid) | ~ | ✓ | ✓ (depth graph) | ✗ | ✓ |
| Historical depth replay graph | ✗ | ✓ | ~ | ~ | ~ | ✓ | ✗ | ~ |
| DOM/ladder | ✓ | ✓ | ✓ | ✓✓ | ✓ | ✓ | ✓ | ✓✓ |
| Click-to-trade (live) | ✗ | ✓ ($99) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓($50/mo) |
| Brackets/OCO/ATM | ~ (paper) | ✓ | ✓ | ✓✓ | ✓ | ✓ | ✓ | ✓ |
| MBO data | ✗ | ✓ | ~ | ~ | n/d | ✓ | ✗ | ✗ |
| CVD / delta / absorption | ✓ | ✓ | ✓ (paid) | ✓ (OF+) | ✓ | ✓ | ~ | ✓ |
| Volume profile / TPO | ✓ | ✓ | ✓ (paid) | ✓ (OF+) | ✓ | ✓ | ~ | ✓ |
| Tick/volume/range/renko frames | ✓ | ~ | ~ (paid) | ✓ | ✓ | ✓✓ | ~ | ✓ |
| Market replay + sim | ✓ | ✓ | ✓ | ✓✓ | ✓ | ✓✓ | ✓ | ✓ |
| Alerts → Telegram/ntfy/email/webhook | ✓ | ~ (in-app) | ~ | ~ | ~ | ~ | ~ | ~ |
| Options analytics (GEX/vol/flow) | ✓✓ | ~ (SpotGamma add-on) | ✓ (paid) | ✗ | ✗ | ~ | ✗ | ✗ |
| Crypto + equities + futures + FX sharing one UI | ✓ | ✓ | ✓ | ✗ | ✓ | ~ | ✓ | ✗ |
| Multi-monitor, detachable panels | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ |
| Command palette / search-everything | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Third-party indicator ecosystem | ✗ | ✓✓ | ✓ | ✓✓ | ✓ | ✓ | ✓✓ | ~ |
| User scripting/API for strategies | ~ | ✓ | ✓✓ | ✓✓ | ✓ | ✓✓ | ✓✓ | ~ |
| Mobile/web companion | ✗ | ~ | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ |
| Free tier | ✓ (all of it) | ✓ (delayed/no trade) | ✓ (limited) | ✓ (sim/chart) | ✓ (crypto) | ✓ trial | ✓ | ✗ |
| All-in monthly cost to a futures trader | **$0** | $49–99 + $34–101 data | $70 (+data) | $99 (+$50–100 data) | €39.95–69.95 | ~$26–56 (+data) | broker-defined | $50 live |

---

## 6. Gap analysis and recommendations

Effort is a build estimate for this codebase and ModFlow's conventions (view + module + selftest + route + pytest pins + handoff section). P0 = without it, a paid competitor's user will not switch. P1 = parity that makes the switch comfortable. P2 = where ModFlow can lead.

### P0 — the three things money actually buys

**P0-1. Live order routing from the ladder (the single biggest gap).**
*Evidence of norm:* Bookmap gates one-click trading at $99; Jigsaw charges $50/mo purely for live; NinjaTrader's licence exists to route futures; Sierra routes CME directly at zero fees.
*What to build:* extend the existing `dtc_client.py` + NT8/MT5 bridge from read-only to **order routing** (DTC supports order submission; MT5 has `order_send`), add a route/adaptor layer, and wire the ladder's existing click grammar to it behind an explicit "live account" switch with dialogs. Keep paper as the default.
*Repo homes:* `orderflow_system/data/dtc_client.py`, `desktop/paper.py` (generalise `PaperAccount` into an account interface), `desktop/ui/ladder.js`, `desktop/ui/risk.js`, new `desktop/accounts.py`, Settings ▸ Feed keys-style card for account credentials (pattern already exists, §146).
*Acceptance:* an end-to-end test that submits a limit order to a simulator bridge, sees the ack, amends and cancels; a "no account configured" refusal sentence; the ladder's stray-click guard honoured; risk.js refuses an order exceeding the configured daily loss cap.

**P0-2. Brackets, OCO and ATM strategies.**
*What to build:* order templates (size, offset, stop distance, target, BE, trail, time-stop) per instrument profile; OCO pairing when a position opens; the same semantics in paper and live. Show working brackets on the ladder and chart.
*Acceptance:* paper-session pytest proving bracket legs are created, trail triggers, OCO cancels the sibling; a selftest pinning template arithmetic; the journal records the strategy id.

**P0-3. Footprint/DOM configurability surface (the ATAS lesson).**
*What to build:* a per-panel settings drawer for the footprint: construction (frame type ✓ exists, ticks/volume per row, cluster-per-bar count), cell metric (bid/ask/delta/volume/OI), imbalance ratio + **stacked** + **diagonal** imbalance, min-size filter, absorption marker threshold, session filter, "exclude market-maker-ish prints" hint (where the venue lets us tell), and POC/VA per bar. Everything numeric must land in `param_registry.py` and survive the store round-trip (there is already a test that enforces this).
*Acceptance:* the registry test extended to every new bound; a selftest pinning the cell-rendering decisions; help topic updated with screenshots-in-words.

### P1 — parity that removes friction

| # | Item | Why | Sketch |
|---|---|---|---|
| P1-1 | **Historical depth graph + depth retention** | Sierra sells it; it is the "replay the book" feature | Persist depthmap columns along with ticks; render a Sierra-style depth-over-time graph; retention knob in Settings ▸ Storage |
| P1-2 | **Order-flow alert builder (conditions → actions)** | Alerts exist; the *builder* is the paid expectation | UI over the existing rule kinds: AND/OR of conditions (delta flip, sweep size, absorption at level, speed of tape, GEX flip), actions (audio, push, webhook, journal note, **screenshot into the alert**) |
| P1-3 | **Alert payload enrichment** (screenshot + panel context) | Genuine "exceed": nobody attaches the book state to the alert | Server-side capture of the relevant panel canvas at fire time, attached to Telegram/ntfy/email; store with the alert row |
| P1-4 | **Chart linking matrix + chart tabs** | Sierra's global cursor/linking; expect on multi-monitor | Link symbol/period/scroll/crosshair across detached windows; 2×2 chart grid with independent panes |
| P1-5 | **Session templates + roll calendar** | Futures correctness; Quantower ships a sessions manager | Session editor (RTH/ETH/holidays/break shading), continuous futures with back-adjustment, roll reminders |
| P1-6 | **Synthetic instruments / spreads** | Quantower's spread builder; crypto basis is the same idea | Define legs, chart the composite, alert on it; no execution needed initially |
| P1-7 | **Trade analytics upgrade** | Every competitor ships stats; educators insist | R-multiples, expectancy, MAE/MFE, tags ("sweep-fade", "absorption-long"), P&L calendar; tag at entry with the order-flow snapshot attached |
| P1-8 | **Read-only companion/mobile** | NinjaTrader/MT5/CoinGlass parity; ntfy already gives push | Responsive monitor route (mobile-first layout, alerts + positions + a couple of panels), served by the existing local server, optional tunnel |
| P1-9 | **Data-quality cockpit** | ATAS sells "reload back-adjusted data" as a differentiator | Per-symbol completeness, gap list, one-click reload/repair, feed-vs-feed comparison (Alpaca compare route is the template) |
| P1-10 | **Publish measured performance** | Exocharts/ATAS/Bookmap all quote FPS and cluster counts | A benchmark page produced by the test suite: ticks/s ingested, ms per panel render, frames/s at N clusters, memory; regenerate per release |

### P2 — where ModFlow can actually lead

**P2-1. Options × order flow confluence (the unique asset).** Nobody in the footprint market natively pairs dealer gamma with the tape. Ship: GEX/VEX/CEX/DEX surfaces, 0DTE flow tape, gamma walls drawn on the footprint, "gamma flip → absorption" combined alerts, and a *cross-asset* read (equity options positioning vs perp funding/basis). Market the panel trio as the reason to install.
**P2-2. Explainability as a feature.** Every read gets a "why" popover: the inputs, the formula, the freshness, and whether it is *native* or *inferred* (the alert table already carries that distinction — surface it in the UI). Competitors sell black boxes; ModFlow can sell honesty, and it is already true.
**P2-3. Crypto derivatives context layer.** Liquidation feed + OI + funding + basis + cross-venue lead-lag in one place (the Coinglass audience pays for a fraction of this today). This is the cheapest "exceed" because `crossvenue.py`, `feed_extras.py` and the liquidation work already exist.
**P2-4. Local-first scripting for signals/strategies.** A sandboxed JS module API for user studies/signals (the indicator module pattern already exists) plus an in-app "study pack" gallery (shipped, versioned, testable) — the ecosystem play without a store.
**P2-5. Onboarding as a moat.** 86 help topics beat every competitor's beginner path; add 5–8 short screen-recorded walkthroughs, a "first fifteen minutes" interactive checklist, and 3–4 shipped layout packs (scalper, intraday, options, crypto-perp). Bookmap/ATAS charge for courses; ModFlow can give this away and win loyalty.

---

## 7. Positioning and pricing recommendation

- **Free core, forever.** Do not add a platform subscription; it is ModFlow's sharpest wedge against $80–200/mo all-in setups two years into a prop-firm boom.
- **Monetise the edges, not the basics:** a paid "Pro" tier is defensible for (a) cloud sync of workspaces/journal across machines, (b) hosted data for instruments the user cannot self-serve (equities depth, MBO), (c) education/drills. This mirrors Bookmap's add-on model without gating footprint/DOM/trading — the things that should stay free to compete.
- **Advertise the two axes nobody else can claim:** "options flow and order flow in one window, on crypto *and* equities, with every read explained" and "your DOM, your data, your machine — no subscription, no telemetry".
- **State numbers.** Publish the benchmark sheet (P1-10). In this market, a missing number reads as a weak number.

---

## 8. Sequenced roadmap (next ~90 days of build)

**Sprint A (2–3 weeks) — configurability + honesty:** P0-3 footprint settings surface → P1-1 depth graph/retention → P1-10 benchmark page.
**Sprint B (3–4 weeks) — execution:** P0-1 routing layer (DTC first, then MT5 bridge) → P0-2 brackets/OCO/ATM → risk gates + reconciliation + journal integration.
**Sprint C (2–3 weeks) — retention & reach:** P1-2/P1-3 alert builder + enriched payloads → P1-8 companion monitor → P1-7 analytics upgrade.
**Sprint D (ongoing) — lead plays:** P2-1 options×flow confluence → P2-2 explainability popovers → P2-3 derivatives context → P2-4 study gallery.

**Cheapest five wins to do first (highest value per day of work):** depth-history graph · alert screenshot attachments · gamma walls on the footprint · session templates · benchmark page. Each is days, each is visible in a demo, and two of them (screenshot alerts, gamma-on-footprint) are things no paid competitor ships.

---

## 9. What I would *not* copy

- **Gating the basics.** Bookmap charging $99/mo for footprint + one-click trading, NinjaTrader's $1,499 licence, Quantower's $50 option extension — these are revenue decisions that would destroy ModFlow's wedge.
- **Black-box indicators.** The market is saturated with magic arrows; ModFlow's refusal sentences and inferred/native labels are a better long-term brand than a "93% win rate" claim.
- **Ecosystem sprawl for its own sake.** A curated, tested study pack beats an open marketplace while the user base is small; marketplaces need moderation and support headcount.
- **Chasing MBO immediately.** It is real (Bookmap/Sierra have it) and it is the ceiling for honest iceberg/spoof reads, but it is a *data contract* problem before it is a code problem — do it when a feed is chosen, and keep labelling those reads as inferred until then.

---

## 10. Sources

Competitor pages (all read 2026-09-20): bookmap.com (home, features, packages-comparison, pricing tiers & add-ons, BookmapData/dxFeed/Rithmic data pricing), quantower.com (home, assets-and-brokers-features, pricing + extensions), ninjatrader.com (trading-platform, platform comparison, pricing/FAQ: lease $99, lifetime $1,499), atas.net (home, pricing: free/€24.95/€69.95, lifetime €999/€1,799), sierrachart.com (home, Features, Numbers Bars, Volume By Price, Packages), metatrader5.com (home; footprint absence is the notable point), jigsawtrading.com + discounttrading.com/daytradr info, exocharts.com, coinglass.com (+ its footprint/liquidity-heatmap explainers), tradinglite.com (defunct, asset sale).
Independent comparisons: tra-mada.de "Best Order Flow Trading Platforms: ATAS vs Sierra Chart vs Bookmap (2026)" (Feb 2026); senzoukria.com "Best Order Flow Trading Software (2026 Comparison)"; chartinglens.com NinjaTrader cost review (2026); benzinga NinjaTrader review 2026.
ModFlow evidence: this repository's tree at the §146 worktree (view list, help-data.js topics, `atlas/api.py` feature/alert tables, `desktop/paper.py`, `desktop/ui/ladder.js`, `docs/SESSION_HANDOFF.md` §119–§146).

*Caveats: competitor pricing and feature gating change monthly — re-verify before quoting in public copy. Trading Technologies was described from market knowledge because its site refused the fetch; treat TT specifics as unverified. ModFlow items marked "unverified" in the norm table (journal analytics depth, replay speed range) should be checked in-app before the report is published externally.*
