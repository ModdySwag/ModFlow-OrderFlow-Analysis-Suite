# ATAS — digest for the 2026-09-19 reanalysis
From `docs/ux-study/atas.md` (read 18 Sep 2026); "not read" = brief could not verify; refs §9.

## 1. The program at a glance
Paid order-flow/volume platform: footprint (cluster) charts, Smart DOM, Smart Tape, volume/market profile, heatmap, replay, options board; analysis+execution on **your own feed/broker** ("you must connect to a data provider"); ATAS SIM demo: no quotes. Classic: **Win 10+ x64**, DX11+OpenGL4, **Vulkan required for Heatmap**. **ATAS X (Beta)**: "Windows + macOS", "2.5× faster*", rebuilt core; lacks some features. Pricing 2026: **START €0 "Always free" / PLUS €24.95 / PRO €69.95 / ULTRA €89.95 per month**; 14-day trial **needs a card** (€1 refunded), one activation. Only reliable gating: **Replay not on Start** (PLUS+); tier matrix unreliable — **not read**.

## 2. Layout & persistence model
- **Docking**: modules drag-merge into one window (quadrant targets); **centre-drop collapses to a tab**. Multi-monitor **not documented**.
- **Two-tier persistence**: *workspaces* = "a set of work layers and the windows within them" (Load/Save/**Edit**/Export; **Edit repairs an overloaded workspace without opening it**); *layouts* = traded-instrument chart groupings (Home → Layouts; a **`Universal` layer whose windows "will be visible across all working layers"**).
- **Template layer**: chart/DOM/Tape (**Set as Default**, Export) + a **Recommended Templates Gallery**.
- Symbol sync **by colour group** (one selector; same-colour windows switch together). Per-window clone/topmost/freeze/reset.
- Config under `%APPDATA%\ATAS\` + `\Documents\ATAS\`.

## 3. Interaction grammar
- **Order-entry safety grammar.** One-Click Mode = master switch (off ⇒ "displays a confirmation dialog before sending"; on ⇒ immediate), mirrored as **Lock trading**. Type from column+level (**below** market in Bids ⇒ Buy Limit, **above** ⇒ Buy Stop, best ask ⇒ Buy Market; Simple Order Entry, default on). **Held-modifier**: hold **Stop Orders Mode hotkey (default `V`)** while clicking the ladder ⇒ stop instead of limit; a cursor tooltip "shows the operation that will be performed". **Flatten** = cancel all + close at market; **Reverse** = close + open opposite. Account selector filters to suitable accounts; if none fits ⇒ **`[no account]`**.
- **Hotkeys**: five sections (Global/Trading/Charting/Smart DOM/Screenshot); **conflict warning** (keep-or-replace); per-section Reset/Clear; trading-first defaults (`W`/`S` market, `Q` flatten, `E` cancel, `R` reverse, `Z`/`X` cancel, `F`/`J`/`H` SL/TP/BE).
- **Mouse**: explicit modes over gestures — crosshair local/global/sync; wheel Zoom/Scroll/ZoomXY; ladder recentres on double-click; auto-centre **up to 10 h**.
- **Smart DOM = spreadsheet of columns**: Trades (bid/ask, in-spread, slippage, delta), Buy/Sell Current Trades (self-cleaning), **Depth changes**, Liquidity map, Order Flow, Footprint, Rolling Footprint; Queue is "an emulator… Execution order is not guaranteed".
- **Tape**: Above Ask/Below Bid/Between colours, **Show Milliseconds**, tape-speed filter, Freeze. **Alerts** sit on the object owning the condition; one triggered log (Home → Alerts); audio + Telegram; won't fire closed/asleep.

## 4. GUI & visual system
- **Colour = named data-semantic preset + two dials.** Footprint schemes: Delta, Solid, Volume/Trades/Bid×Ask Proportion, Heatmap by Volume/Trades/Delta, None; heatmap-ish ones expose **Upper Cut-off %** ("the strongest colour applies to the highest N% of values") + **Contrast**.
- Colours named **by market meaning, not hue**: Buy/Sell/Between, Above Ask/Below Bid. Theming: per-surface colours + per-module fonts; no global theme/font picker **read**.
- **Density per surface**: row heights + fonts (DOM/tape), footprint text gated by "Width to Show Text" (Auto Size vs fixed); global **Max Candles per Chart** + **DOM Levels Count** trade history vs memory. Conventions: "12,345 → 12k".
- **Colour-blind gap**: `colorblind` search ⇒ "Sorry! nothing found"; no accessibility/contrast preset. Legibility via **Transparent Candles** + a **Hidden** chart mode.

## 5. Standout technical features / advantages
- **Footprint set**: Content×Mode (Volume, Trades, Delta, Centered Delta, Bid×Ask × Full Row/Profile/Ladder); **Additional Footprint** = second footprint, different scheme, same chart; **zoom degradation** — "When the chart is zoomed out, Footprint charts automatically switch to Candles mode. This behavior can be disabled." Users: "10/10 … easiest footprint implementations to learn".
- **Smart DOM** columns (Liquidity map, Order Flow, Footprint); **Heatmap** (Bookmap-like; Vulkan); **DOM Trader** = chart-embedded ladder + order-flow + position panel.
- **Replay ladder**: Generated Ticks+DOM (fastest, unlimited history, weak volume) / Ticks+Generated DOM (≤1 week) / Ticks+DOM (full fidelity, **one day**); one **Replay Account**; **Trading Journal** results; **press Stop before changing instrument/timeframe/template/indicators**; paid-only.
- **Performance**: "faster… less resource-intensive" than a rival; 51 connectors; demo feeds.

## 6. Documented user pain points
Trustpilot **4.1/5 (444)**; AMP verified 4.57/5 (187). Sentiment: **the UI is not the main complaint** — feeds, price, support, ATAS X stability are.
- Feeds: "Feeds are an issue…"
- "SierraChart is way way more stable"; "occasional freezing on Windows"; ATAS X: heatmap "so buggy", "delayed Hotkey issues", "will not connect".
- "**Windows 95 nightmare**" (ATAS named): "you spend more time fighting the software than actually analyzing the markets".
- Bloat: "90% are useless".
- **Silent-truth traps**: POC differs between 5m chart and DOM *because of different price scales*; "daily volume profile keeps shifting… lose confidence on your trade".
- Price "$84 + $30 add-on"; "horrible customer service"; "Steep learning curve (1+ month)".
- **Templates = switching cost**: "recreating my templates… seems daunting"; hop to TradingView for HTF "because the UI is so damn good".

## 7. Market norms this platform establishes
1. **Dock-anything single window** — drag-merge modules, quadrant targets, centre-drop→tab; clone, pin, freeze.
2. **Two-tier persistence + templates** — workspaces + layouts (groupings, `Universal` layer) + module templates.
3. **Colour-group symbol linking** — one colour attribute, N surfaces follow one instrument.
4. **Launcher-first Home + shallow menus + live connection health.**
5. **Order-entry safety grammar** — one-click switch + visible Lock; held modifier + cursor tooltip; fixed Flatten/Reverse strip.
6. **Task-grouped conflict-aware hotkeys** — keep-or-replace, Reset/Clear per section, volume presets.
7. **Explicit modes over gestures** — crosshair local/sync/global; interval-bounded auto-centre respecting scroll.
8. **Data-semantic colour schemes + two dials**; colours named by meaning.
9. **Density knobs on every data surface** + global perf-vs-history knobs.
10. **Honest documented limits** — Queue emulator disclaimer; alerts dead closed/asleep; replay trade-off ladder.
11. **Replay as paid, tiered teaching tool** with resettable account + journal.
12. **In-product learning** — Learn Center, template gallery, modular KB.
13. **Not yet a norm — colour-blind affordances**: ATAS has none; open flank, not table stakes.

## 8. Transferable upgrade ideas for an analytics-layer tool (ranked)
1. **Held-modifier order-type override + cursor tooltip** — one mode fewer; tooltip = confirmation. *evidence:* Smart DOM trading (hold `V` ⇒ stop).
2. **Danger row + Lock** — Flatten/Reverse fixed strip; Lock kills click-to-trade. *evidence:* Smart DOM overview.
3. **Context menu mirrors header actions**. *evidence:* Smart Tape; Smart DOM overview.
4. **Auto-centre ladder + double-click centring + interval/speed** — stops drift; respects drag. *evidence:* Common Smart DOM Settings.
5. **Density knobs everywhere** — divider, 12k, digits, row height, auto-size. *evidence:* Footprint settings; Smart Tape.
6. **Zoom-level degradation** — dense render auto-lightens when zoomed out; hysteresis. *evidence:* Chart Display Modes.
7. **Semantic colour presets + cut-off + contrast.** *evidence:* Footprint settings.
8. **Alerts owned by their object; one triggered log; honest limits line.** *evidence:* Alerts.
9. **Replay tiers + resetting account + Journal results.** *evidence:* Replay.
Also: #11 conflict-aware binding editor; #12 templates Set-as-Default/Clone/Export (top switching cost). **Rejected: renderer/FPS knobs** — WebView2 can't offer them.

## 9. Key sources
KB base `https://help.atas.net/en/support/solutions/articles/`: 72000602576 (entry grammar); 72000602621 (Lock); 72000602516 (workspaces); 72000602557 (layouts); 72000606631 (colour/density); 72000602396 (hotkeys); 72000637162 (linking); 72000602238 (alerts); 72000602247 (replay). Plus https://atas.net/pricing/; https://www.trustpilot.com/review/atas.net; https://completetradersedge.com/atas-review/.
