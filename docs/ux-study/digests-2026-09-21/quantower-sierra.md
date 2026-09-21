# Order-flow platform fact refresh — READ DATE 2026-09-21

All prices, versions and gating below are as published on the vendors' own pages on 2026-09-21 unless a date is given. Every claim is tagged vendor-stated (read from the vendor page cited) or independent (third party). Pages that refused this host's fetches are flagged inline and repeated in the unverified_items field.

## Quantower (quantower.com)

### 1. Pricing as published today (vendor-stated — https://www.quantower.com/pricing)
One paid tier: **ALL-IN-ONE license** (all features, all connections, updates). Currency USD ($).

| Period | All-in-One |
|---|---|
| Monthly | $70 |
| 3 months (-10%) | $189 |
| 6 months (-20%) | $336 |
| Annually (-30%) | $588 |
| Lifetime | $1,690 |

Extensions (sold separately, add paid functions **to the Free version only**; also included in All-in-One). Monthly / lifetime, vendor-stated:
- DOM Surface $30 / $650 (3mo $81, 6mo $144, 1yr $252)
- Power Trades $25 / $490
- Volume Analysis $35 / $720 (cluster chart, volume profiles, time statistics/histogram, historical T&S, price statistics, Volume Impact, Dynamic VPOC)
- TPO Profile Chart $20 / $490
- Advanced features $30 / $650 (Renko/Kagi/P&F/Heikin-Ashi, unlimited overlays and indicators, multi-sync-connect, chart alerts, RTD Excel)
- Option trading $50 / $690
- Multi-asset package (Volume Analysis + Advanced) $50 / $1,290
- Crypto package (same two, crypto connections only) $40 / $990

What the free tier gates (vendor-stated, https://help.quantower.com/quantower/getting-started/license-comparison): free = 1 connection, 2 indicators per chart, 1 chart overlay, no footprint/cluster chart, no volume profiles, no market replay, no trading simulator (crypto-only on the Crypto package), no RTD Excel, screener excluded, Option Analytics limited to 4 strikes. Free needs no registration; a 7-day full-featured trial is available; 10-day money-back on initial orders, **no refunds on lifetime** licenses.

Market data: billed separately. Vendor states plainly: 'the Quantower license price does not include third-party market data that must be purchased additionally' (pricing page) and 'third-party market data fees are not included in any Quantower license' (extensions section). **Quantower publishes no data-fee table** — cost comes from the chosen broker/feed. Free-of-charge options on the vendor site: dxFeed Simulated (limited symbols, 24-hour delay) and Binance in info-only mode (https://help.quantower.com/quantower/getting-started/installation.md).

Free/white-label routes (vendor-stated, https://www.quantower.com/connections): a column headed 'ALL PAID FEATURES for FREE with these connections', with caveats — AMP requires a special AMP Quantower build; Topstep may withhold some premium features; Optimus Flow is 'a Quantower's white label' used to get all premium features free. Brokers repeat this: AMP says 'Normally $100 per month - AMP Customers get all the Trading Features available in Quantower for FREE' (https://www.ampfutures.com/trading-platform/quantower-free, broker-stated), and Optimus Futures (2025-12-18) wrote that the full platform 'costs $70 a month or $1,590 for a lifetime license' but is free via Optimus Flow (https://optimusfutures.com/blog/quantower-for-free-in-2026-no-license-fees-same-platform/, independent).

Re-pricing evidence: archived snapshots of the pricing page show lifetime at **$1,590 on 2025-07-17** and **$1,690 on 2026-02-17 and 2026-09-13**; the $70 monthly and every extension monthly price are unchanged across those snapshots (snapshot provenance: web.archive.org captures listed in Sources). So the lifetime All-in-One licence rose $100 between those dates; monthly did not.

### 2. Platform support and current build
- Windows only: 'For Windows 10/11 64-bit'; system requirements Windows 10 or 11, .NET Desktop Runtime 10, ≥1 GB disk, recommends 16 GB RAM / 4-core CPU / SSD. No macOS or Linux build published (vendor-stated, https://www.quantower.com/download and https://help.quantower.com/quantower/getting-started/installation.md). Portable install: no Program Files/AppData copies, no registry writes, can run from removable media.
- Current builds (vendor-stated, https://www.quantower.com/release-notes): latest **beta 1.147.3 (2026-09-12)**; latest listed **stable 1.146.18 (2026-08-07)**.

### 3. Order-flow feature set (vendor-stated)
Free-tier order-flow: DOM Trader panel, Market Depth panel, Time & Sales, Stat matrix, Market Heatmap panel (exchange/market heatmap, not depth). Paid: **DOM Surface** heat-map of the order book plus executed trades with three colouring modes, imbalance and absolute/cumulative size per level, detail inspector (https://www.quantower.com/dom-surface); **Cluster chart (footprint)** with footprint imbalances, delta chart, all volume profile types (Right, Left, Custom, Step), Time Statistics, Time Histogram, Historical Time & Sales, VWAP/anchored VWAP, Dynamic VPOC (https://www.quantower.com/volumeanalysistools, https://help.quantower.com/quantower/analytics-panels/chart/volume-analysis-tools/cluster-chart.md); **Power Trades** scanner for large aggressive orders (https://help.quantower.com/quantower/analytics-panels/chart/power-trades.md); TPO Profile. Delta appears as per-bar/cluster delta and as indicators (Delta Flow, Delta Rotation, Delta Divergence Reversal, COT High/Low, Depth of Bid/Ask, Level2), documented at https://help.quantower.com/quantower/llms.txt — no indicator literally named 'cumulative delta' in the license table or docs index.
Replay/simulator: **Market Replay** (history player; tick/1-min/1-day data, Last or Bid/Ask/Last execution) and **Trading Simulator** are paid (https://help.quantower.com/quantower/trading-panels/market-replay.md, .../trading-simulator.md).
API: free C# API in every tier — Quantower Algo, core classes documented at https://api.quantower.com/ and a Visual Studio extension; order placement/modification/cancel via Core.PlaceOrder/ModifyOrder/CancelOrder/ClosePosition (https://help.quantower.com/quantower/quantower-algo/trading-operations.md).

### 4. Layout, hotkeys, theming (vendor-stated)
- **Every panel is effectively an OS window** — 'Single panel … they behave just like any usual PC window': resize, reposition, snap to other panels, collapse to the OS taskbar (https://help.quantower.com/quantower/general-settings/standalone-panels.md).
- Nesting model: Workspace (top level; XML file per workspace, auto-saved every 5 min and on exit, Ctrl+S manual, workspace **Lock** disables add/remove/move/resize) → **Binds** ('super-panels': any set of panels stuck together and resized as one) → Groups → panels → templates and colour-coded **Linking** of panels by symbol (workspaces-binds-groups.md, binds.md, link-panels.md).
- Hotkeys: per-panel hotkey lists (Chart, DOM Trader — general and trading shortcuts) plus terminal-wide **custom hotkeys** that can be bound to actions such as change symbol, set period, place a pre-configured order, open a panel/template, run a strategy; panel-specific hotkeys fire only for the focused panel, global ones anywhere (custom-hotkeys.md, dom-trader-settings/hotkeys.md).
- Theming: Themes editor in the Control Center, global colour variables, custom themes saved/duplicated/shared by copying files into Settings/Themes and swapping in the vendor Discord; switching a theme resets per-panel custom colours, so those must be saved as panel templates first (miscellaneous-panels/themes-editor.md).

### 5. 2025–2026 changes (vendor-stated)
- **Risk Management** release line: 1.147.1 (2026-09-01) adds a Risk Management panel with rules for allowed trading time, open P/L limits (account and per position), data-latency limit, max/min balance/equity, plus locking settings when a rule fails; vendor blog 2026-09-10 (https://www.quantower.com/blog, release notes).
- Copy Trading (Beta) now listed across all licences incl. free (license comparison, 'last updated 3 months ago').
- New/expanded broker connections in Aug–Sep 2026 releases: Finotive prop firm, multiple Alpaca instances, Bybit Brazil/Argentina endpoints, Plus500 and dxFeed fixes (release notes).
- Regionalised distribution: quantower.ua and quantower.in sites; two connections are sold only through the Indian build (connections page).
- Ownership: no acquisition or ownership change found in searches; the site footer names QUANTOWER WEST LTD (Sheffield, England) and QUANTOWER LLC (Dnipro, Ukraine), copyright Quantower LLC (quantower.com/pricing footer). dxFeed also markets a co-branded 'dxFeed Quantower' platform (https://dxfeed.com/platforms/dxfeed-quantower/) — vendor-distributed branding, no equity event stated.

### 6. Independent criticism and praise
Praise
- Trustpilot profile: **4.7/5 from 362 reviews**, 60 reviews in the last 12 months; reviewers repeatedly cite fast/attentive support and a modern, fast, customisable UI; one 2026-04-15 review: 'Great software, amazing customer's service!' (https://www.trustpilot.com/review/quantower.com).
- r/FuturesTrading (archived): 'It's great, all the order flow tools are already configured, and everything is pretty easy to use'; another: 'Quantower is the sexiest platform out there. Lots of functionality and love the window management/snapping, top notch aesthetics.' (https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/…, Wayback capture listed in Sources).
- CompleteTradersEdge review (updated 2026-07-26, 8.5/10): calls DOM Surface 'one of the best tools available at this price point', praises 60+ broker/feed connections and broker-neutrality; discloses a referral link (https://completetradersedge.com/quantower-review/).

Criticism
- Same r/FuturesTrading thread, same user: 'The downside is the lag during market open, news events, a Trump tweet, or just a random spike'; another: 'Quantower is good ... if you don't mind the occasional lag' (URL above).
- r/OrderFlow_Trading, thread title 'Is Quantower a buggy mess or is it just me?' — search-result excerpt: 'In my first week I didn't experience any problems … But today the whole platform was just a mess. During London …'. **Page blocked this host**; excerpt only (https://www.reddit.com/r/OrderFlow_Trading/comments/1qokf7f/…).
- r/OrderFlow_Trading, 'Rant: For Anyone Trying to Find a REAL Orderflow Platform': 'Quantower is a joke for serious orderflow trading. The footprint charts are weak, the volume profiles aren't impressive…'. Blocked; excerpt only (https://www.reddit.com/r/OrderFlow_Trading/comments/1t3w3f3/…).
- r/Quantower subreddit listing shows a recurring 'Desktop freeze when vola spikes' complaint: 'For at least two months now I've experienced issues with the whole desktop freezing when volatility spikes…'. Blocked; excerpt only (https://www.reddit.com/r/Quantower/).
- Trustpilot: 'Some reviewers were not happy with response times, mentioning long email delays, ticketing issues'; the summary also notes 'certain desired features or specific chart tools were currently missing'; one 2026-04-08 review: 'only missing a heatmap and a Mac version!'; one user reports a platform 'completely bricked' for 90+ days by Alpaca/Tradier integration problems (vendor reply disputes the cause).
- CompleteTradersEdge: 'it runs on Windows only, and the pricing model can be confusing at first glance'; lists 'Windows only, steep learning curve for beginners, and market data subscriptions cost extra' as the biggest weakness.

## Sierra Chart (sierrachart.com)

### 1. Pricing as published today (vendor-stated — https://www.sierrachart.com/index.php?page=doc/Packages.php, page last modified 2026-09-08)
USD/month, five service packages:

| Package | 1 mo | 3 mo (-15%) | 6 mo (-25%) | 12 mo (-35%) |
|---|---|---|---|---|
| 3 — Base Standard | $26 | $66.30 ($22.10/mo) | $117 ($19.50/mo) | $202.80 ($16.90/mo) |
| 5 — Base Advanced | $36 | $91.80 | $162 | $280.80 ($23.40/mo) |
| 10 — Integrated Standard | $36 | $91.80 | $162 | $280.80 |
| 11 — Integrated Advanced | $46 | $117.30 | $207 | $358.80 ($29.90/mo) |
| 12 — Integrated Advanced + Market by Order | $56 | $142.80 | $252 | $436.80 ($36.40/mo) |

Gating: **Base packages (3, 5) cannot connect to any external data/trading service (IB, CQG, Rithmic…) nor to the Denali Exchange Data Feed**; only Packages 10/11/12 can. Advanced gating (5/11/12 over 3/10): TPO Chart study, Numbers Bars, Numbers Bars Calculated Values, Market Depth Historical Graph; the Volume Profile Interactive Drawing Tool is 'now allowed in all Packages as of version 2778'. **Market by Order is Package 12 only.** No lifetime or one-time option: 'the answer is _no_, and this is something that would never be offered'.
Included with any package (vendor): Sierra Chart historical data service, FX/CFD data service, market statistics feed, crypto data/trading, delayed exchange feed (with depth and market-by-order), and the server-side **Simulated Trading Service** for unlimited simulated trading on real-time or delayed data.
Data billed separately: the Denali Exchange Data Feed has published exchange fees (USD/month, read 2026-09-21, https://www.sierrachart.com/index.php?page=doc/DenaliExchangeDataFeed.php#SupportedExchanges): CME non-pro top-of-book $2.00; CME with market depth non-pro $13.50 (CBOT/COMEX/NYMEX identical); **full CME Group non-pro with depth $40.50**; full CME Group non-pro without depth $6.00; CME/CBOT/COMEX/NYMEX professional or no-trading-account $145.00 (CME E-mini $78.00, CBOT E-mini $53.00); EUREX EOBI $25.00 (professional $130.00); CFE top-of-book $10 / depth $12 (professional $25 / $50); NASDAQ TotalView $17.00 (pro $90.00); US Equities Consolidated Tape $10.00 (pro $100.00); CBOE Global Indexes $6.00 + $3.00 additional. Fees are billed in full each month whenever activated; CME Group exchanges are free in the month first activated. Non-professional CME fees require a live funded futures account connected at least monthly.
Free trial: 21 days (vendor-stated, https://www.sierrachart.com/index.php?page=doc/helpdetails59.php), full software functionality, 10 days of intraday chart history / 186 days daily, denial of external services (IB/CQG/Rithmic) during trial.

### 2. Platform support and current build
- Operating systems: Windows 7, 8, 10, 11, Server 2008-2016 and higher; **64-bit only**. Linux/CrossOver via Wine is supported — with mandatory 'Resolution of Poor Network IO Performance under Linux/Wine' instructions. Apple M-series CPUs require the 64-bit ARM build. Portable, self-contained folder install; must not be installed to Program Files (https://www.sierrachart.com/index.php?page=doc/SoftwareDownload.php).
- Carries **Current Version: 2954 (September 20, 2026)**; PreRelease 2954 same date (Software Download page). The What's New log documents 2948 (2026-09-08) as the newest entry and states the log 'has mostly been abandoned … It only represents a very small percentage of the actual development' and that releases are made 'nearly weekly or several times a week' (https://www.sierrachart.com/index.php?page=doc/Whats_New.php).

### 3. Order-flow feature set (vendor-stated)
- **Footprint: Numbers Bars** — numeric volume/ask/bid/ask-bid difference per price level within each bar, with colour coding and volume-profile display (https://www.sierrachart.com/index.php?page=doc/NumbersBars.php); gated to the Advanced packages.
- **Heatmap: Market Depth Historical Graph** study (Studies Reference ID 375) and Bid & Ask Depth Bars; also a DOM Graph drawn on charts (https://www.sierrachart.com/index.php?page=doc/TradeMenu.html#DrawDOMGraph). Depth Historical Graph is Advanced-gated.
- **Cumulative delta**: documented studies Cumulative Delta Bars – Trades (ID 296), – Volume (ID 292), – Up/Down Tick Volume (ID 323) at https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=292; plus a 'Delta Volume' bar type and Delta/Diagonal-difference DOM market-data columns. These studies are not named in the paid Advanced-features list.
- Volume: Volume by Price, Volume Value Area Lines, TPO Profile charts, 'Draw Volume Profile' drawing tool; DOM market-data columns include bid/ask depth, last trade size, cumulative last trade size, recent bid/ask volume, current traded volumes and depth pulling/stacking (Features page; Packages page).
- **Market by Order** (Package 12): per-order queue display in Trade/Chart DOM columns; only orders ≥3 lots are transmitted (changeable upward per symbol), no historical MBO recording/download, and MBO is available from Sierra Chart feeds only (https://www.sierrachart.com/index.php?page=doc/MarketByOrder.php).
- **Replay**: any number of intraday charts replayed at 0.1x to 100,000x with synchronised charts, no pre-recorded data needed, simulated trading during replay (https://www.sierrachart.com/index.php?page=doc/ReplayChart.html). **Simulation**: Trade Simulation mode plus the server-based Simulated Trading Service (https://www.sierrachart.com/index.php?page=doc/TradeSimulation.php).
- API: **ACSIL is C++ only** — 'C++ based coding language', usable from Visual Studio or the built-in editor (https://www.sierrachart.com/index.php?page=doc/DevelopingCustomStudiesAndSystems.php); plus Excel/Calc-compatible spreadsheet studies/systems, and the **DTC protocol** (open spec, binary/JSON/GPB encodings, C++ headers updated 2026-09-18, DTC Test Client, and a DTC Server so other instances or external apps can take Sierra Chart data/trading) — https://www.sierrachart.com/index.php?page=doc/DTCProtocol.php. No C# study API is documented.

### 4. Layout, hotkeys, theming (vendor-stated)
- A **Chartbook is a collection of windows, not a window itself**; chart windows, Trade DOM, Time & Sales, Market Depth, Trade and Spreadsheet windows are MDI child windows of the main Sierra Chart window, each detachable (float, always-on-top, always-visible) — https://www.sierrachart.com/index.php?page=doc/Chartbooks.html and .../DetachingandAttachingChartWindows.html.
- Only one chartbook can be visible per instance; multiple visible chartbooks require multiple instances via the DTC Server, although multiple chartbooks can be open with clickable tabs (F7/F8 to switch). Cascade/Tile; z-order edited in Window >> Windows and Chartbooks; the 2025-26 changelog is largely window-state fixes for these MDI/detached windows.
- Hotkeys: keyboard shortcuts map to **menu commands** and are global; assigned in Global Settings >> Customize Keyboard Shortcuts; trading shortcuts must be enabled per chart; the vendor recommends AutoHotkey if you need shortcuts targeted at specific windows (https://www.sierrachart.com/index.php?page=doc/KeyboardCommands.html, GlobalSettingsMenu.html#CustomizeKeyboardShortcuts).
- Theming: per-element colours, fonts and widths via Global Settings >> Graphics Settings (Colors/Fonts/Other) with per-chart overrides; no theme system is documented (https://www.sierrachart.com/index.php?page=doc/GraphicsSettings.php). The sierrachart.com website itself has a Dark Mode toggle.

### 5. 2025–2026 changes (vendor-stated, What's New)
- 24 documented releases across 2026 (2859 → 2948); the page covers only 2859 back to 2774 for 2025 — the changelog is explicitly incomplete.
- MFC removal completed for the main window, MDI child windows and detachable windows (2846, 2025-12-29, completing work started in 2829); **two-factor authentication added** (2829, 2025-12-11); named trade accounts for sim/live (2822).
- Volume/quantity types migrating from integer to double precision, breaking older compiled ACSIL studies (2897, 2026-04-07); chart update interval down to 1 ms (2871); OpenGL fixes (2867, 2940); window-state fixes (2859, 2874, 2936); AM/PM time display (2895); DOM volume bars across combined price levels plus a new Notes column in the Chart/Trade DOM (2923, 2927); **Quote Board attachable in the main window** (2948, 2026-09-08); replay jump-forward synchronisation across charts (2941).
- Ownership: About Us states Sierra Chart 'has been in business since 1996', is 'not a clearing firm or broker', and runs its own data/order-routing infrastructure. No ownership change found in searches (https://www.sierrachart.com/index.php?page=doc/AboutUs.php).

### 6. Independent criticism and praise
Praise
- AMP Futures review page (Reviews.io, **4.80/5 from 543 reviews**, read 2026-09-21): 'The charting is extremely fast, stable, and highly customizable … The platform has a learning curve, but once configured, it provides exceptional performance and reliability' (2026-08); 'Very fast, applaudable execution time with miniscule data delay (near zero lag)' (2026-08); another: 'Over the years I've tried any software that works with Rithmic and they cant hold a candle to Sierra' (https://www.ampfutures.com/reviews/sierra-chart).
- EliteTrader, 'Which trading platform has the best level 2?': 'For Level 2 and order-flow work, Sierra Chart with Denali is hard to beat in my opinion' (https://www.elitetrader.com/et/threads/which-trading-platform-has-the-best-level-2.380582/).
- r/FuturesTrading (archived): 'Sierra is the most stable thus far, haven't had a single crash'; 'in 5 years there is absolutly ZERO times the platfrom crashed'; 'Sierra Chart is extremely customizable … It's also highly stable with its own datafeed & order routing' (thread URL above).

Criticism
- Same thread: 'Sierra Chart and it's absolutely the worst user experience I have ever had. Almost nothing is intuitive and requires a Google search or ChatGPT prompt. However, every gd pixel can be customized'; 'the configuration is honestly a joke. For almost every minor change, you'll have to do a Google search on how to get it done'; 'Sierras big plus is Denali, but, for that you have to tolerate an outdated UI, fairly unhelpful customer service'; one user notes the chart refresh rate is limited to 10 ms and 'Sierra seems a little slow' versus Tradovate/NinjaTrader (URL above).
- AMP reviews page complaints: 'If you are using Footprint charts and Heat Maps, understand that they are tedious to set up, as there are a plethora of micro settings'; 'You have to check for new versions manually'; 'Handling Custom vs Global Graphics could be more intuitive'; 'Data can lag if you are not on a solid and stable if not juiced up machine'; 'Old Design'; support ticket-only, no phone.
- BullishBears review, updated 2026-03-27 (4.6/5): 'Though their GUI is mid-90s'; 'Sierra Chart can be resource-intensive for an older PC; intra-day scans can be especially slow'; lists desktop-only, external data requirement and ACSIL learning curve as cons (https://bullishbears.com/sierra-chart-review/).
- r/FuturesTrading, 'Why is Sierra Charts so clunky and slow?' — **page blocked this host**; search excerpt only: 'Sierra Chart loads an absurd amount of data. if you are looking at an intraday chart make sure you are loading only a few days worth of data' (https://www.reddit.com/r/FuturesTrading/comments/1iuf9i6/…). r/SierraChart hosts 'Sierra Chart's UI and website is ridiculously bad' and 'Sierra chart is pure shit and a scam company' (titles only; pages blocked this host).

## Sources
- Quantower — pricing, extensions, refunds, data-exclusion warning: https://www.quantower.com/pricing (read 2026-09-21)
- Quantower — free vs Crypto vs Multi-Asset vs All-in-One gating table ('last updated 3 months ago'): https://help.quantower.com/quantower/getting-started/license-comparison
- Quantower — builds/dates: https://www.quantower.com/release-notes; system requirements and Windows-only: https://help.quantower.com/quantower/getting-started/installation.md and https://www.quantower.com/download
- Quantower — connections and free-with-broker premium: https://www.quantower.com/connections
- Quantower — order-flow panels: https://www.quantower.com/dom-surface; https://www.quantower.com/volumeanalysistools; https://help.quantower.com/quantower/trading-panels/market-replay.md; .../trading-simulator.md; https://help.quantower.com/quantower/analytics-panels/chart/power-trades.md
- Quantower — layout/hotkeys/theming: .../general-settings/workspaces-binds-groups.md; .../general-settings/binds.md; .../general-settings/standalone-panels.md; .../general-settings/custom-hotkeys.md; .../trading-panels/dom-trader/dom-trader-settings/hotkeys.md; .../miscellaneous-panels/themes-editor.md
- Quantower — API: https://api.quantower.com/ and https://help.quantower.com/quantower/quantower-algo/trading-operations.md
- Quantower — price history (snapshots): https://web.archive.org/web/20250717060215/https://www.quantower.com/pricing ($70 / $1,590); https://web.archive.org/web/20260217032428/... and https://web.archive.org/web/20260913182356/... ($70 / $1,690)
- Sierra Chart — packages, gating, discounts, data notes, no-lifetime policy: https://www.sierrachart.com/index.php?page=doc/Packages.php (last modified 2026-09-08)
- Sierra Chart — Denali exchange fee table: https://www.sierrachart.com/index.php?page=doc/DenaliExchangeDataFeed.php#SupportedExchanges
- Sierra Chart — current version: https://www.sierrachart.com/index.php?page=doc/SoftwareDownload.php (2954, 2026-09-20); changelog: https://www.sierrachart.com/index.php?page=doc/Whats_New.php
- Sierra Chart — replay, simulation, DOM columns, ACSIL, spreadsheets: https://www.sierrachart.com/index.php?page=doc/Features.php; .../ReplayChart.html; .../TradeSimulation.php; .../ChartTrading.html; .../AdvancedCustomStudyInterfaceAndLanguage.php
- Sierra Chart — MBO: https://www.sierrachart.com/index.php?page=doc/MarketByOrder.php; cumulative delta: .../StudiesReference.php&ID=292 (also ID 296, ID 323); Numbers Bars: .../NumbersBars.php
- Sierra Chart — layout: https://www.sierrachart.com/index.php?page=doc/Chartbooks.html; .../DetachingandAttachingChartWindows.html; hotkeys: .../KeyboardCommands.html; graphics/theming: .../GraphicsSettings.php; DTC: .../DTCProtocol.php; trial: .../helpdetails59.php; company: .../AboutUs.php
- Independent — AMP Futures Sierra Chart reviews (Reviews.io, 4.80/543): https://www.ampfutures.com/reviews/sierra-chart; AMP Quantower free offer: https://www.ampfutures.com/trading-platform/quantower-free
- Independent — Trustpilot Quantower (4.7/362): https://www.trustpilot.com/review/quantower.com
- Independent — CompleteTradersEdge Quantower review (updated 2026-07-26): https://completetradersedge.com/quantower-review/; BullishBears Sierra Chart review (updated 2026-03-27): https://bullishbears.com/sierra-chart-review/
- Independent — EliteTrader 'best level 2' thread: https://www.elitetrader.com/et/threads/which-trading-platform-has-the-best-level-2.380582/; Optimus Futures blog (2025-12-18): https://optimusfutures.com/blog/quantower-for-free-in-2026-no-license-fees-same-platform/
- Independent — Reddit r/FuturesTrading 'What's so special about Quantower and Sierra Charts?' recovered via Wayback: https://web.archive.org/web/2026/https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/ (live URL https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/…). Other Reddit URLs cited from search-result excerpts only (pages blocked): https://www.reddit.com/r/OrderFlow_Trading/comments/1qokf7f/…, https://www.reddit.com/r/OrderFlow_Trading/comments/1t3w3f3/…, https://www.reddit.com/r/Quantower/, https://www.reddit.com/r/FuturesTrading/comments/1iuf9i6/…
