# ATAS — UX / GUI study for ModFlow OrderFlow Analysis Suite

**Read on 18 Sep 2026.** Sources: ATAS's own knowledge base (`help.atas.net`), ATAS's marketing/pricing site
(`atas.net`), the ATAS SDK manual (already summarised in-repo), Trustpilot, AMP Futures' verified-review page,
one independent review site, and Reddit threads/comments retrieved via the PullPush archive API and via search
snippets. Every non-obvious claim below carries a link. Where something could not be verified it says **not read**.

**Relationship to `docs/ATAS_SDK_NOTES.md` (read first, read-only).** That note is about the *developer* surface:
`docs.atas.net` — data callbacks, indicator events, `TradingManager`, the performance contract, the heatmap v2
author-DLL guide, and the Liquidity Pressure formula it transferred into `atlas/tapeflow.py` / `depthmap.py`. It
explicitly excludes "Chart drawing / mouse / keyboard hooks" as "nothing to port". **This brief is the other half:
the user-facing product** — how windows are arranged, how features are found, how orders are placed, how colour and
density are managed, how users are taught, and what users complain about. It adds no platform internals and repeats
nothing about the SDK. One overlap is kept deliberately: the SDK note describes the *formula* of weighted liquidity
pressure; this brief describes the *widget UX* around it (the Smart DOM analytical columns and the Liquidity
Pressure card) only where ATAS's own help text describes behaviour rather than maths.

**Method note / limits.** ATAS's KB is a Freshdesk portal; a handful of article IDs redirect off-portal
(`72000602557-layout-settings` and `72000602229-trading-from-chart` redirected to
`sierrachart.com` on first fetch and resolved correctly on a later fetch from a clean tab — treat single-fetch
redirects as unreliable and re-fetch). Reddit is not readable directly from this host (blocked) and not supported by
the extractor, so Reddit material comes from the PullPush archive API (`api.pullpush.io`) plus search snippets, and is
quoted with permalinks.

---

## 1. Snapshot

| Item | What was read |
|---|---|
| What it is | Paid order-flow / volume-analysis trading platform: footprint (cluster) charts, Smart DOM, Smart Tape, volume & market profile, heatmap, replay, options board. 25+ exchange/broker connections claimed by a third-party review ([completetradersedge](https://completetradersedge.com/atas-review/)); the KB lists 51 connector articles ([KB folder index](https://help.atas.net/en/support/solutions/folders/72000569858)). |
| Platform | Classic ATAS = **Windows 10 or later**, x64; DirectX 11 + OpenGL 4.0 GPU with ≥4 GB VRAM; **Vulkan required for Heatmap**; 8 GB RAM min, 80 GB disk, ≥30 Mbps ([technical requirements](https://help.atas.net/en/support/solutions/articles/72000602485-technical-requirements)). |
| Rendering stack (user-visible) | Renderer is **user-selectable**: Direct2D (GPU), GDI (CPU/compat), OpenGLSkia (GPU; "required for some Liquidity Map features in DOM Levels or DOM Trader"); plus heatmap video-adapter choice, FPS-cap mode and a manual FPS cap ([Common Settings](https://help.atas.net/en/support/solutions/articles/72000602625-common-settings)). |
| Second client | **ATAS X (Beta)** — "For Windows + macOS", "2.5× faster*", "Intuitive tab system" per the pricing page; a third-party review adds that it runs on the same account as classic ATAS, is a rebuilt core with tab-based architecture, and still lacks some advanced features/backtesting ([atas.net/pricing](https://atas.net/pricing/), [completetradersedge](https://completetradersedge.com/atas-review/)). |
| Local storage layout (user-facing) | Templates/workspaces/etc. live under `%APPDATA%\ATAS\…` (`Workspaces_v3`, `Chart\Templates`, `Chart\Snapshots`, `SmartDOM\Templates`, `Logs`) and `\Documents\ATAS\` — documented for backup/restore/migration ([Workspace Setting](https://help.atas.net/en/support/solutions/articles/72000602516-workspace-setting)). |
| Pricing headline (read live from the pricing page) | Billing terms offered: 1 month / 3 months ("up to 14% off") / 1 year ("up to 44% off") / Lifetime. Plan headline prices: **START €0 "Always free"**, **PLUS €24.95/month**, **PRO €69.95/month**, **ULTRA €89.95/month (+MBO Bundle)** ([atas.net/pricing](https://atas.net/pricing/)). |
| Trial mechanics | 14-day trial; **requires a payment card**, a €1 temporary verification charge is refunded, the trial is active only once recurring payments are enabled, and the trial can be activated **once**; refund available within 14 days of first purchase ([free trial article](https://help.atas.net/en/support/solutions/articles/72000602400-how-to-register-a-free-trial), [atas.net/pricing](https://atas.net/pricing/)). |
| Tier contents | **Only one gating fact is verifiable from the KB**: "Start Plan: Replay is not available. PLUS, PRO, and ULTRA plans: Replay is available" ([Replay](https://help.atas.net/en/support/solutions/articles/72000602247-replay-trading-simulator-)). The pricing page's per-tier feature matrix parsed unreliably (the same feature block appears under several plans) — **tier matrix: not read in reliable form.** Do not quote indicator-per-chart counts or asset counts from this study. |
| Data-feed reality | The platform is analysis+execution on top of **your own** feed/broker: "To receive real-time market data, you must connect to a data provider" ([technical requirements](https://help.atas.net/en/support/solutions/articles/72000602485-technical-requirements)); dxFeed/Rithmic/CTS demo registrations are separate KB articles; ATAS SIM is a virtual-funds demo with **no quotes** ([ATAS SIM](https://help.atas.net/en/support/solutions/articles/72000602259-connecting-to-atas-sim)). |

---

## 2. Layout & windowing model

**The unit of composition is a module, and modules merge into one main window.** Chart, Smart Tape, DOM, Watchlist
and friends can be dragged onto one another; a drop marker offers **left / right / top / bottom**, and dropping on
the **centre collapses the window into a tab** ([Windows arranging](https://help.atas.net/en/support/solutions/articles/72000602278-windows-arranging)).

**Two separate persistence concepts: workspaces (layers) and layouts (instrument groupings).**

- A **workspace** is "a set of work layers and the windows within them". The Workspaces window offers
  Load / Add / Save / Delete / Rename / Copy / **Edit** / **Export** / **Import**; there is a "Save and close"
  prompt at exit, a load-on-launch option, and an explicit warning that deleting a workspace deletes the layers and
  windows inside it. "Edit" exists so you can repair an overloaded workspace **without opening it**
  ([Workspace Setting](https://help.atas.net/en/support/solutions/articles/72000602516-workspace-setting)).
- A **layout** groups the charts of traded instruments so you can "quickly switch between them… especially useful
  when trading a large number of instruments". Layouts are reached via **Home → Layouts**, can be created from
  scratch or **Cloned** (clone copies the windows of the active layout), and each layout has **working layers**
  (Add/Delete/Rename/Clone/Up/Down) — including a special **`Universal` layer whose windows "will be visible across
  all working layers"**, and a rule that collapsed windows added to a layer stay hidden when that layer opens.
  Switching is a **layout selector panel** from the Layouts window or from the main window's Settings menu
  ([Layout Settings](https://help.atas.net/en/support/solutions/articles/72000602557-layout-settings)).

**Instrument sync between windows is by colour group**, not by a rule engine: a selector in the upper-left of the
Chart window assigns a colour; any windows in the same colour group change instrument together. Colour groups are
also available in Smart DOM, Smart Tape, Bid/Ask Tape, All Prices, Heatmap, Forward Curve and Options Board
([Windows Linking](https://help.atas.net/en/support/solutions/articles/72000637162-windows-linking)).

**Per-window affordances that matter more than the docking itself:**
- **Clone window** from the right-click menu of Chart / Smart DOM / Smart Tape ([Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview), [Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-)).
- **Topmost** ("keep DOM always on top"; "Window on Top" in the tape) — a per-window pin
  ([Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview), [Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-)).
- **Freeze / Reset** on the tape: freeze the feed, or refresh the interface, from the same context menu
  ([Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-)).
- **Fullscreen** per chart is a toolbar control ([Chart window](https://help.atas.net/en/support/solutions/articles/72000602255-chart-window)); the main window has a "bar minimization button" and a status bar showing server and data-source connection status ([Main windows of ATAS](https://help.atas.net/en/support/solutions/articles/72000602420-main-windows-of-atas)).

**Multi-monitor: not documented.** KB searches for `undock` return nothing and `second monitor` returns no
windowing article, so no official statement about spreading modules across displays was read
([search: undock](https://help.atas.net/en/support/search/solutions?term=undock),
[search: second monitor](https://help.atas.net/en/support/search/solutions?term=second%20monitor)). What the docs do
show is that the composition model is *merge into one window + per-window on-top pin*, not a free-floating
multi-window desktop by default — **multi-monitor behaviour: not read**.

**Templates exist as a third, module-scoped layer of reuse**: chart templates (Save / Edit / **Set as Default** /
Export / apply), SmartDOM templates, Smart Tape templates, plus a **Recommended Templates Gallery** and a
Templates section inside the Learn Center ([Working with Templates](https://help.atas.net/en/support/solutions/articles/72000602515-working-with-templates), [Learn Center](https://help.atas.net/en/support/solutions/articles/72000637161-learn-center)).

---

## 3. Navigation & IA

**The IA is launcher-first, not menu-tree-first.** The main window's **Home tab is the launcher** for every module:
Chart, Watchlist, Smart DOM, Smart Tape, Bid/Ask Tape, All Prices, Heatmap, Option Board, Alerts, Following Manager,
Replay, Connection, Workspaces, Logs, Forward Curve — with hotkeys as an alternative path ("Main program windows can
also be opened using main window hotkeys") ([Home tab](https://help.atas.net/en/support/solutions/articles/72000602394-home-tab)).

**Menu depth is deliberately shallow — four tabs, not a ribbon of cascades:** the main window carries the workspace
name, **menu tabs** (Home / Learn / Settings / About License), a quick-access button bar, and a status bar holding
server connection status, data-source connection status, the minimisation button, What's-New changelog, license type
and expiry, feature request, contact, Help Center, language, topmost and platform version
([Main windows of ATAS](https://help.atas.net/en/support/solutions/articles/72000602420-main-windows-of-atas)).

**Settings are split into three tiers, and the split is the interesting part:**

1. **Global (main window → Settings tab)**: Hot Keys, Sound, Time Zones, Commission, Custom Modules (with a switch to
   disable automatic loading of third-party modules), and **Common Settings**
   ([Settings Menu](https://help.atas.net/en/support/solutions/articles/72000602252-settings-menu)).
2. **Common Settings = cross-module numeric policy and performance levers**: Value Area percent (default usually 70%),
   levels at a time, update interval, continuous-profile source, **Max Candles per Chart**, **DOM Levels Count** (0 =
   unlimited), rendering group (renderer, debug info, disable hidden-window rendering, render threads), heatmap
   rendering (video adapter, FPS cap), notifications, trading warnings, local cache
   ([Common Settings](https://help.atas.net/en/support/solutions/articles/72000602625-common-settings)).
3. **Module/chart-scoped tabs**: a chart's settings window holds **Visual Settings**, **Trading Settings**, cluster
   settings, footprint settings and Templates tabs side by side; Smart DOM has its own General Settings tab (row
   height, header and button font/colour, auto-centre interval and speed, update intervals)
   ([Visual settings](https://help.atas.net/en/support/solutions/articles/72000602496-visual-settings-of-the-chart), [Trading Settings](https://help.atas.net/en/support/solutions/articles/72000602491-trading-settings), [Common Smart DOM Settings](https://help.atas.net/en/support/solutions/articles/72000602544-common-smart-dom-settings)).

**Every module also exposes the same actions in a right-click context menu**, which is how "clone / layers /
settings / freeze" are reachable without hunting a toolbar (Smart DOM: "Right-click any area of the DOM (except
trading columns)"; Smart Tape: "right-click anywhere in the tape")
([Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview), [Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-)).

**Symbol selection is a modal gate rather than a per-window dropdown.** Opening a module opens the **Instruments
Manager** (Favorites / All / Info tabs, continuous or specific contract, quick-search field, "Add to Favorites");
it is also reachable any time via **Change Instrument** on the toolbar or in a window's context menu
([Instruments Manager](https://help.atas.net/en/support/solutions/articles/72000602406-instruments-manager)).
The chart window's instrument selector then changes symbol **without losing the chart setup, indicators, drawing
objects and templates** ([Chart window](https://help.atas.net/en/support/solutions/articles/72000602255-chart-window)).

**Charts are navigated by explicit mode switches, not hidden gestures**: crosshair modes Pointer / Crosshair /
**Global Crosshair** (synchronises across all open charts regardless of instrument) / **Sync Crosshair**; mouse
wheel behaviour selectable as Zoom / Scroll / ZoomXY; scale drag on axes, drag-to-pan, Page Up/Down, scrollbar,
corner arrows, Ctrl+wheel for horizontal scale, plus dedicated "return to latest bar" and "reset manual scaling"
buttons ([Crosshairs & navigation](https://help.atas.net/en/support/solutions/articles/72000602265-types-of-chart-crosshairs-navigation)).
Similarly, chart type is changed either from the toolbar icon **or** the chart context menu
([Chart Display Modes](https://help.atas.net/en/support/solutions/articles/72000602349-chart-display-modes)).

**Discoverability in the KB itself is well-engineered and worth copying structurally**: the portal index is organised
into named folders with counts (Installation 4, First start 7, Plans 7, ATAS SIM 4, Demo feeds 4, Connectors 51,
Chart window overview 11, Drawing objects 33, Indicators management 2, Order-flow/volume indicators 50, Classic &
technical indicators 231, Other modules 23, Settings 10, Trading-from-chart 6, Other trading possibilities 5), each
article page ends with **"Articles in this folder" + "You may like to read"** cross-links, and every article carries a
"Modified on" date ([KB index](https://help.atas.net/en/support/solutions)).

---

## 4. Interaction model

### 4.1 Smart DOM: a ladder configured as a spreadsheet of analysis columns
Columns are added/removed/reordered by list (Add / double-click to add / Move Up / Move Down / Remove) and split into
**common** columns (Price, Bids, Asks with display modes Volume | Number of applications | Average volume, Bid/Ask
Ladder, My orders, Queue, PNL & Orders, Latest trade quantity, DOM trader) and **analytical** columns: Histogram
profile, **Trades** (trades at bid/ask, in-spread, above ask and below bid read as slippage, delta, open interest,
configurable periods), **Buy Current Trades / Sell Current Sales** (self-cleaning, erase old data when bid returns
"unless it's within 2.5s"), **Depth changes** (additions/removals per level), Notes, Liquidity map, Order Flow,
Footprint, Rolling Footprint ([Smart DOM Window Columns](https://help.atas.net/en/support/solutions/articles/72000602469-smart-dom-window-columns)).
The docs are explicit about an honesty limit that a reimplementation should copy: the **Queue column "is an emulator
and data is approximate. Execution order is not guaranteed"** (same page).

### 4.2 Order entry: a small matrix of modes, plus a held-modifier override
- **One-Click Mode** is the master safety switch: off ⇒ "ATAS displays a confirmation dialog before sending the
  order"; on ⇒ commands are sent immediately. It is also surfaced as **Lock trading** in the DOM header ("prevents
  accidental clicks") and in the DOM context menu ([Smart DOM trading functions](https://help.atas.net/en/support/solutions/articles/72000602576-trading-functions-smart-dom), [Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview)).
- **Simple Order Entry (default on)** infers order *type* from column + level: click **below** market in Bids ⇒ Buy
  Limit, **above** ⇒ Buy Stop, **best ask** ⇒ Buy Market; mirrored for Asks. With it off, **mouse button decides**:
  left = limit, right = stop. Right-clicking an existing order at a level cancels it
  ([Smart DOM trading functions](https://help.atas.net/en/support/solutions/articles/72000602576-trading-functions-smart-dom)).
- **Held modifier instead of a mode**: in the Bid/Ask Ladder column, hold the **Stop Orders Mode hotkey (default V)**
  while clicking to place a stop instead of a limit, and an **action tooltip near the cursor "shows the operation that
  will be performed"** ([Smart DOM trading functions](https://help.atas.net/en/support/solutions/articles/72000602576-trading-functions-smart-dom)). The same held-key idea is in DOM Trader
  ("While the key is pressed, DOM Trader temporarily switches to Stop order placement")
  ([DOM Trader](https://help.atas.net/en/support/solutions/articles/72000602463-dom-trader)).
- **SL/TP is a placement mode**: enable it, move the cursor, the row shows SL or TP, click the price
  ([Smart DOM trading functions](https://help.atas.net/en/support/solutions/articles/72000602576-trading-functions-smart-dom)).
- **Moving** an order = select it, click the new level (or drag-and-drop if enabled); **Flatten** cancels everything and
  closes at market; **Reverse** closes and opens the opposite side ([Smart DOM trading functions](https://help.atas.net/en/support/solutions/articles/72000602576-trading-functions-smart-dom)).
- **Chart trading has its own mode enum**, including an auto-detection mode and a
  "Lclick: Buy. Rclick: Sell" mode, plus Stop vs Stop-Limit with a **slippage in ticks** value
  ([Trading Settings](https://help.atas.net/en/support/solutions/articles/72000602491-trading-settings)).
- **Trading Panel** (right side of chart, hotkey `T`) holds account selector, Qty, market/limit buttons, position
  block, OCO + TIF, protective strategies and a "trading from chart" toggle — with the rule that "some sections are
  shown only when they are supported by the selected connector and instrument", and a **privacy mode that hides
  sensitive account values** ([Trading panel](https://help.atas.net/en/support/solutions/articles/72000625592-trading-panel-for-classical-markets)).
- **Account context is shown, filtered and restored, not remembered blindly**: the Smart DOM keeps an account
  selector in the header **next to the instrument**; the list is filtered to accounts suitable for the current
  instrument; on instrument switch or workspace restore it updates the list and "tries to restore the previous
  selection when possible"; if nothing fits the header shows **`[no account]`** and trading commands stay unavailable
  ([Smart DOM Trading panel](https://help.atas.net/en/support/solutions/articles/72000660364-smart-dom-trading-panel)).

### 4.3 DOM Trader: the ladder embedded in the chart
A chart-attached module combining DOM, order-flow visualisation and controls: ladder, orders area, order-flow area
(Liquidity Map / bubbles / blocks), position panel (avg entry, size, PnL switchable between ticks/currency/percent),
lots selector, **auto-centre**, and an **"outside-orders area"** so orders beyond the visible price range are still
manageable ([DOM Trader](https://help.atas.net/en/support/solutions/articles/72000602463-dom-trader)).

### 4.4 Hotkeys: a sectioned binding registry with conflict handling
Hot Keys live in **five sections — Global, Trading, Charting, Smart DOM, Screenshot** — with click-the-field-then-press
assignment, **Reset** and **Clear per section**, and a **conflict warning** when a combination is already taken
("You can keep the existing assignment or replace it with the new one"). Defaults are trading-first: `W` buy market,
`S` sell market, `Q` flatten, `E` cancel all, `R` reverse, `A` buy at bid, `D` sell at ask, `Z`/`X` cancel limit/stop,
`C` temporary reduce-only, `F`/`J`/`H` SL/TP/breakeven, plus **up to five volume presets** switchable by hotkey or
interface ([Hot Keys Configuration](https://help.atas.net/en/support/solutions/articles/72000602396-hot-keys-configuration), [Trading with Hotkeys](https://help.atas.net/en/support/solutions/articles/72000637159-trading-with-hotkeys)).

### 4.5 Footprint / depth / heatmap interactions
- **The footprint has a toolbar of its own when active** (cluster display options appear on the left of the chart)
  and can be driven from the chart toolbar icon or the chart right-click menu
  ([Chart Display Modes](https://help.atas.net/en/support/solutions/articles/72000602349-chart-display-modes)).
- **Content** (Volume, Trades, Volume and Trades, Volume and Delta, Delta, Centered Delta, Bid × Ask, Centered Bid ×
  Ask, Bid/Ask, None) × **Mode** (Full Row, Bid/Ask Profile, Volume Profile, Trades Profile, Delta Profile, Bid/Ask
  Ladder, Positive/Negative Delta Profile) is a two-axis choice, plus Draw Borders
  ([Footprint settings](https://help.atas.net/en/support/solutions/articles/72000606631-footprint-settings)).
- **An "Additional Footprint" lets you draw a second footprint with a different mode/colour scheme on the same chart**
  — same page.
- **Density controls are first-class**: Values Divider ("divides displayed values by the specified number, allowing
  more compact footprint visualization"), Width to Show Text (minimum cell width before text appears), Auto Size font
  vs fixed Font Size, text colour, borders, bold text — same page. Volume formatting is a global convention:
  "Minimize Volume Values (12,345 → 12k)" and "Digits After the Decimal Point"
  ([Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-), [Visual settings](https://help.atas.net/en/support/solutions/articles/72000602496-visual-settings-of-the-chart)).
- **A zoom-level degradation rule**: "When the chart is zoomed out, Footprint charts automatically switch to Candles
  mode. This behavior can be disabled" ([Chart Display Modes](https://help.atas.net/en/support/solutions/articles/72000602349-chart-display-modes)).
- **DOM/ladder ergonomics**: double-click the price column to centre the spread (or use the Center button;
  "in one or all DOMs"), auto-centre with an interval settable up to 10 hours and a speed control, centre-line
  visibility/width/colour, row height, and per-module update intervals
  ([Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview), [Common Smart DOM Settings](https://help.atas.net/en/support/solutions/articles/72000602544-common-smart-dom-settings)).
- **Smart Tape as a reading surface**: instrument switch, **Freeze**, colour rules for Above Ask / Below Bid /
  Between (inside spread), row height, price digits, "Show Milliseconds", "Show Previous Level 1 Data", a tape-speed
  filter with a market-strength indicator, and a **cumulative-ticks mode with its own min/max volume filters**
  ([Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-)).

### 4.6 Alerts UX
Alerts are **owned by the object that owns the condition** — Smart Tape settings → Alerts tab; indicator settings →
Alerts; a drawing object's own "Approximation alert" with a ticks-from-line filter (not all objects support alerts) —
and all *triggered* alerts are read in one place, **Home → Alerts**. Delivery is **audio signal** plus Telegram
("Email alerts are no longer supported"). Two honest limitations are documented in the article itself: "Alerts will
not trigger if ATAS is closed or if your PC enters sleep mode", and "not all drawing objects support alerts"
([Alerts](https://help.atas.net/en/support/solutions/articles/72000602238-alerts), [Alerts in Smart Tape](https://help.atas.net/en/support/solutions/articles/72000636828-alerts-in-smart-tape)).

---

## 5. Visual design language

**Density model.** ATAS is a dense multi-panel terminal whose density is *tunable per surface* rather than fixed:
DOM row height and header/button fonts in Smart DOM settings; tape row height and font size in tape settings; chart
axis font size, grid style/step, crosshair colours and "Draw Borders" in Visual Settings; footprint cell text gated by
"Width to Show Text" with Auto Size. There are two global pressure-relief knobs — **Max Candles per Chart** and
**DOM Levels Count** — that trade history/depth against memory, CPU and load time
([Common Smart DOM Settings](https://help.atas.net/en/support/solutions/articles/72000602544-common-smart-dom-settings), [Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-), [Visual settings](https://help.atas.net/en/support/solutions/articles/72000602496-visual-settings-of-the-chart), [Footprint settings](https://help.atas.net/en/support/solutions/articles/72000606631-footprint-settings), [Common Settings](https://help.atas.net/en/support/solutions/articles/72000602625-common-settings)).

**Colour is a preset + two dials, not free-form.** Footprint ships **named colour-scheme presets** — Delta, Solid,
Volume Proportion, Trades Proportion, Bid/Ask Volume Proportion, Heatmap by Volume, Heatmap by Trades, Heatmap by
Delta, None — and the heatmap-ish ones expose **Upper Cut-off %** ("the strongest colour applies to the highest N% of
values") and **Contrast** ([Footprint settings](https://help.atas.net/en/support/solutions/articles/72000606631-footprint-settings)).
DOM Trader's Liquidity Map has its own scheme list plus Default Minimized Color, Contrast, Smoothing Mode, Smoothing,
Animation Speed, Power Scale and Low Level Transparency
([DOM Trader](https://help.atas.net/en/support/solutions/articles/72000602463-dom-trader)).

**Semantic colours are named by market meaning, not by hue**: Buy Color / Sell Color / Between Color (in-spread) /
Above Ask / Below Bid in the tape; Up/Down candle and bar colours plus Doji bar colour; bid/ask background colours
and Best Bid/Best Ask highlighting in the DOM; buy/sell trade marker colours on the chart
([Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-), [Visual settings](https://help.atas.net/en/support/solutions/articles/72000602496-visual-settings-of-the-chart), [Trading Settings](https://help.atas.net/en/support/solutions/articles/72000602491-trading-settings)).

**Theming and typography.** The read evidence is per-surface colours (background, gradient background option,
labels, axis background/text, current-price line colour/dash/width, crosshair label background/text) and per-module
fonts (tape font size; DOM header/button fonts; chart axis font size; DOM Trader order-flow text colour + font) —
([Visual settings](https://help.atas.net/en/support/solutions/articles/72000602496-visual-settings-of-the-chart), [Common Smart DOM Settings](https://help.atas.net/en/support/solutions/articles/72000602544-common-smart-dom-settings), [DOM Trader](https://help.atas.net/en/support/solutions/articles/72000602463-dom-trader)).
A platform-wide light/dark theme switch or a font-family picker was **not read** in the KB; the only hits for
"theme"/"font" searches are per-object and per-module colour/font settings
([search: theme](https://help.atas.net/en/support/search/solutions?term=theme), [search: font](https://help.atas.net/en/support/search/solutions?term=font)).

**Colour-blind accessibility: not present.** A KB search for `colorblind` returns **"Sorry! nothing found"**, and no
accessibility/contrast preset appears in the visual-settings or footprint colour-scheme articles
([search: colorblind](https://help.atas.net/en/support/search/solutions?term=colorblind), [Visual settings](https://help.atas.net/en/support/solutions/articles/72000602496-visual-settings-of-the-chart)). Where the platform
does address legibility, it does so through visual devices rather than palettes: **Transparent Candles** "useful when
multiple indicators and drawing objects are applied… helping reduce visual clutter", and a **Hidden** chart mode that
"hides the chart display while keeping other chart elements and indicators visible"
([Chart Display Modes](https://help.atas.net/en/support/solutions/articles/72000602349-chart-display-modes)).

---

## 6. Onboarding & discoverability

**In-product:** the **Learn Center** is reachable from the main window and contains an **Introductory** section
(tutorials, articles, videos), a **Templates** section with "ready-made configurations for platform modules: Chart,
Smart DOM, Smart Tape, and Positions tab", a **Support & Community** section (Help Center, community Telegram,
**feature base** for submitting ideas, a changelog, support bot) and a **Connections** tab
([Learn Center](https://help.atas.net/en/support/solutions/articles/72000637161-learn-center)). The main window's
**Learn tab** carries "Quick Start — brief introductory gif instructions", a Trading reading list and Templates
([Main windows of ATAS](https://help.atas.net/en/support/solutions/articles/72000602420-main-windows-of-atas)). On
first run, the platform opens an **Authorization window and platform-version selection** article series
([First start folder](https://help.atas.net/en/support/solutions/folders/72000569853)).

**Practice-first onboarding without a funded account:** ATAS SIM (virtual funds, no quotes; daily drawdown −50,000
blocks the account until the next day, minimum balance 10,000, balance resettable by right-clicking the DEMO account),
a further 15-minute-delayed SIM variant, a **Crypto sim**, and demo-feed registrations for dxFeed / Rithmic / CTS
([ATAS SIM](https://help.atas.net/en/support/solutions/articles/72000602259-connecting-to-atas-sim), [Demo data feed folder](https://help.atas.net/en/support/solutions/folders/72000569859)).

**Replay as the teaching tool**, with an explicit fidelity ladder and its own friction:
- Modes: **Generated Ticks and DOM** (fastest start, unlimited history, weak volume analysis), **Ticks + Generated
  DOM** (recommended when not using Level II, up to one week), **Ticks + DOM** (full fidelity, **one day**)
  ([Replay](https://help.atas.net/en/support/solutions/articles/72000602247-replay-trading-simulator-)).
- Playback controls: play/pause/stop, **speed slider**; a dedicated **Replay Account** that records trades and shows
  them on the chart; results land in the **Trading Journal** (profit factor, drawdown); "only one Replay Account is
  available. Each new training session resets the results of the previous session".
- Documented caveats: Replay replaces the Windows system clock so live updates and live-position info stop working —
  "we recommend separating live trading from Replay"; you must **press Stop before changing instrument, timeframe,
  template or adding indicators**; charts on dxFeed are unavailable in Replay; **Replay is not on the Start plan**.

**Off-platform education is part of the funnel**: ATAS runs a tiered free course and the KB itself is enormous
(231 classic-indicator articles alone), surfaced through the Learn tab and Learn Center
([KB index](https://help.atas.net/en/support/solutions), [Learn Center](https://help.atas.net/en/support/solutions/articles/72000637161-learn-center)).

**The learning curve is real and is acknowledged in the marketing.** An independent review's "Biggest weakness" line
is "Steep learning curve (1+ month to master), occasional freezing on Windows, and paid subscriptions required for
advanced features after 14-day trial" ([completetradersedge](https://completetradersedge.com/atas-review/)). Users say
the same from both directions: "The design, customization and settings are very intuitive (if you understand trading
and the settings values — if not, a lot of free tutorials…)" ([r/OrderFlow_Trading, "ATAS — Yes or Not?"](https://www.reddit.com/r/OrderFlow_Trading/comments/1qz5ccm/atas_yes_or_not/)),
versus a beginner who installed it and asked: "I have downloaded ATAS, but I do not know where to go from here"
([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1uvhpu8/i_am_transitioning_from_basic_supply_demand_to/)).

---

## 7. What users actually say

**Volume and headline scores read:** Trustpilot **4.1 / 5 from 444 reviews**, company replies to 100% of negative
reviews, "typically replies within 24 hours", 164 reviews in the last 12 months
([Trustpilot](https://www.trustpilot.com/review/atas.net)). AMP Futures' verified-user page reports **4.57 / 5 from
187 reviews** with sub-scores for Trading Tools, **User Interface** and Stability, and its own summary praises the
"intuitive interface" while noting "some experience occasional lag during high volatility and report high system
requirements" ([AMP Futures](https://www.ampfutures.com/reviews/atas)). Treat both as promotional-adjacent
(AMP sells ATAS; Trustpilot invites reviews at vendor request) — the *complaints* below are the useful part.

### Praise (cited)
- "I love the flexibility of ATAS. You can setup there literally everything without too much complexity. It is really
  all-in-one solution." — 5★ ([Trustpilot](https://www.trustpilot.com/review/atas.net)).
- "ATAS now includes everything a trader needs, tape, DOM, a heatmap similar to Bookmap, alerts, and an easy-to-use
  modern interface… excellent value for money, especially if you prefer having everything in a single platform."
  ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1t8q1xz/best_orderflow_softwaresetup/okxgv1p/)).
- "The interface and design are modern, and the setup and operation are very easy to learn. There is also a large
  community where you can always get help" ([AMP verified review](https://www.ampfutures.com/reviews/atas)).
- "Atas is king of orderflow. Specially with Atas X you get a native performance (on both macos and windows) and super
  clean interface" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1re5yc0/dont_buy_deepcharts_prove_me_wrong/o7agno3/)).
- Switcher from Sierra: "Switched to ATAS few months ago and already like it more personally, so much smoother to use
  and figure out… they update it often especially with atas X, which helps when I travel since I use a MacBook pro so
  no need for parallels anymore" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1scnpc8/atas_vs_bookmap_vs_sierra_charts/oedvjvx/)).
- Order-flow UI rated above peers in a long community comparison: "ATAS — 10/10 — One of the easiest footprint
  implementations to learn. Modern UI, many footprint styles, excellent visualization and **plenty of built-in
  templates**" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1uaozg1/atas_vs_deepcharts_vs_motivewave_vs_sierra_chart/)).
- Performance vs a rival: "ATAS feels faster, smoother, and significantly less resource-intensive, especially when
  running footprint charts and DOM together" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1rze7gb/clarity_requested_platforms_and_data_feeds/oblfcp5/)).
- "as a customization it is 10 times higher Atas" (vs Quantower) ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1rc6yyj/quant_tower/o6ws3mp/)).

### Complaints (cited)
- **"Good DOM and time and sales. Footprints are clean. Feeds are an issue…"** — depth/data-feed limits named in the
  same breath as the UI ([r/OrderFlow_Trading](https://www.reddit.com/r/OrderFlow_Trading/comments/1qz5ccm/atas_yes_or_not/)).
- **Stability vs a rival:** "ATAS is simpler to setup but SierraChart is way way more stable and customizable"
  ([r/OrderFlow_Trading](https://www.reddit.com/r/OrderFlow_Trading/comments/1scnpc8/atas_vs_bookmap_vs_sierra_charts/)).
- **"Windows 95 nightmare" critique aimed at this class of tool (ATAS named):** "They have all the data you need, but
  the UI looks like a Windows 95 nightmare. The learning curve is so steep that you spend more time fighting the
  software than actually analyzing the markets" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1t81jq3/is_it_just_me_or_is_the_gap_between_tradingview/)).
- **Depth without focus:** "it has more functions than most platforms… but 90% are useless and the good ones miss a
  lot of key settings that i had to code my own version of existing indicators. It looks like the platform is not made
  by real traders" ([r/ATASTrading](https://reddit.com/r/ATASTrading/comments/1v90ek5/do_not_use_atas/p0d44pn/)).
- **Bugs in the new client:** "My atas x beta heatmap is so buggy on my laptop… it just shows me the heatmap for the
  candle but nothing more" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1vzfma7/atas_heatmap_buggy/));
  "I've never had issues with ATASX outside of some delayed Hotkey issues, but today the platform will not connect"
  ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1voh3re/atas_x_not_connecting/)).
- **Silent-truth traps in analysis:** "the POC level from 5m chart and DOM is on different price level… [support] said
  it's because I use different price scale on both DOM & chart" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1uppbch/different_poc_level_on_dom_charts/));
  "The daily volume profile keeps shifting throughout the day… This makes you lose confidence on your trade"
  ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1w9mt8q/atas_volume_profile_keeps_shifting/)).
- **Price pressure:** "it is expensive at $84 and a $30 add-on for the exchange fee" ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1vbe3t0/atas_or_ninjatrader_orderflow_for_footprint/));
  "Great software for tranding. But unfortunately I personally find a bit too expensive" ([AMP verified review](https://www.ampfutures.com/reviews/atas)).
- **Support is the tail risk that drives 1★ reviews:** "Cool product, horrible customer service. The overall tone and
  helpfulness of Taras, one of their support managers was horrible" ([Trustpilot](https://www.trustpilot.com/review/atas.net)).
- **Occasional lag / heavy requirements** even in the friendly review summary: "occasional lag during high volatility
  and… high system requirements" ([AMP Futures](https://www.ampfutures.com/reviews/atas));
  "occasional freezing on Windows" ([completetradersedge](https://completetradersedge.com/atas-review/)).
- **The ceiling is elsewhere for some users:** an ex-Sierra user notes the class gap in the *opposite* direction —
  "the interface feels like Windows 95 and you'll waste weeks just trying to get your CVD to look right. ATAS is the
  way to go for what you need… It's pricey, but the 'adaptive' feature actually works for filtering noise"
  ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1q8jeja/stuck/nypqot6/)).
- **Ergonomics envy runs one way:** "skipping between TradingView for HTF general analysis with 6 charts because the
  UI is so damn good, and then ATAS & bookmap for my daily technical trading, it's very annoying"
  ([r/TradingView](https://reddit.com/r/TradingView/comments/1vccmh0/tradingviews_handing_of_volume_data_is_more/p111dxd/)).
- **Templates are a switching cost users cite first:** "the main reason is because the thought of recreating my
  templates over again seems daunting. I put a lot of time in creating my workspace on ATAS"
  ([r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1p2gszm/why_is_everyone_so_antideepcharts_and_why_is_it/npzzuu4/)).

**Reading of the sentiment:** the UI is *not* the main complaint — data feeds, price, support and the new client's
stability are. The recurring UI-shaped complaints are (a) sheer function count without focus, (b) settings depth that
assumes you already know the vocabulary, and (c) analysis artefacts whose *display context* (price scale, session,
feed) silently changes the numbers.

---

## 8. UX patterns worth adopting — ranked

Ranked by value ÷ cost for **ModFlow** (vanilla JS, no bundler, single window, Windows/WebView2, one developer,
must not break a working app). "Already have" items are excluded per brief: rail views, workspaces/layouts, keyboard
registry + Keys menu, explain cards, per-surface pause/resume, dark theme + colour-blind palettes, onboarding wizard,
help corpus, heatmap/ladder/footprint/absorption inference, Replay paper sim.

| # | Pattern (source) | Why it transfers | Effort | Risk |
|---|---|---|---|---|
| 1 | **Held-modifier order-type override + cursor action tooltip** — hold `V` while clicking to get a stop instead of a limit; a tooltip next to the cursor states the operation ([Smart DOM](https://help.atas.net/en/support/solutions/articles/72000602576-trading-functions-smart-dom), [DOM Trader](https://help.atas.net/en/support/solutions/articles/72000602463-dom-trader)) | Removes a mode toggle for the trade you make least often, and the tooltip is the confirmation dialog for people who turned confirmations off. Direct fit for the Depth ladder and paper sim | S | Low — additive to the click handler; no state |
| 2 | **Explicit danger row with a lock** — `Flatten`, `Reverse`, `Close All` in one fixed strip, plus `Lock trading` that kills click-to-trade ([Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview), [Smart DOM Trading panel](https://help.atas.net/en/support/solutions/articles/72000660364-smart-dom-trading-panel)) | The panel a user reaches for in a panic should be positional, not findable; and a lock is the cheapest mitigation for mis-clicks in a paper sim people leave open | S | Low |
| 3 | **Context menu that mirrors the header actions** (clone, settings, layers, freeze/reset, change instrument) ([Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-), [Smart DOM](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview)) | One canonical action vocabulary surfaced in two places; users learn it once per surface | S | Low |
| 4 | **Auto-centre ladder + double-click-to-centre + centre-line styling + re-centre interval/speed** ([Smart DOM overview](https://help.atas.net/en/support/solutions/articles/72000602621-smart-dom-window-overview), [Common Smart DOM Settings](https://help.atas.net/en/support/solutions/articles/72000602544-common-smart-dom-settings)) | Prevents the "ladder drifted off price" failure during fast tape without hijacking scroll; the interval control makes it predictable | S | Low — must respect manual scroll (pause re-centre after user drag) |
| 5 | **Density knobs on every data surface** — values divider, "minimise volume values" (12,345→12k), digits after comma, row height, min cell width before text draws, auto-size vs fixed font ([Footprint settings](https://help.atas.net/en/support/solutions/articles/72000606631-footprint-settings), [Smart Tape](https://help.atas.net/en/support/solutions/articles/72000602608-description-setting-templates-smart-tape-)) | Canvas renderers fail on density, not on features; these are five cheap ways to make the same payload readable | S/M | Low |
| 6 | **Zoom-level degradation rule** — footprint auto-switches to candles when zoomed out, and the rule is user-disableable ([Chart Display Modes](https://help.atas.net/en/support/solutions/articles/72000602349-chart-display-modes)) | The single best performance+legibility trick in the whole product for a canvas app: change what is drawn, not how fast it draws | S/M | Low-Med — needs a hysteresis band so it does not flicker at the threshold |
| 7 | **Semantic colour-scheme presets + two dials** — named schemes (Delta, Volume Proportion, Heatmap by Volume/Trades/Delta, Solid, None) with Upper Cut-off % and Contrast ([Footprint settings](https://help.atas.net/en/support/solutions/articles/72000606631-footprint-settings)) | ModFlow has palettes but (per the brief) not *data-semantic* presets; "colour = what the number means" is orthogonal to dark/colour-blind theming and composes with it | M | Low — additive preset list over existing paint path |
| 8 | **Alert configured on the object that owns the condition + one triggered-alerts log + honest failure line** ([Alerts](https://help.atas.net/en/support/solutions/articles/72000602238-alerts)) | Puts the rule where the user's attention already is (the level, the indicator, the tape filter); the log is the audit trail; the "won't fire when closed/asleep" line is the kind of honesty that prevents trust loss | M | Low — but must not duplicate ModFlow's existing Alerts view; frame as rule-ownership + log |
| 9 | **Replay fidelity tiers with stated trade-offs, one replay account that resets per session, results in the Journal** ([Replay](https://help.atas.net/en/support/solutions/articles/72000602247-replay-trading-simulator-)) | Users accept limits they can see; "unlimited history / one week / one day" as a visible ladder beats a spinner. Also the "press Stop before changing instrument/timeframe" rule is honest friction worth copying as a disabled-state explanation | M | Low — paper sim exists; this is a labelling + reset-semantics change |
| 10 | **Cross-surface crosshair modes: local / sync / global** ([Crosshairs](https://help.atas.net/en/support/solutions/articles/72000602265-types-of-chart-crosshairs-navigation)) | ModFlow has many symbol-aware canvases; a sync level that is *chosen per surface* is how a multi-view app stays coherent without a layout engine | S/M | Low — one shared pointer state + per-surface opt-in |
| 11 | **Conflict-aware binding editor grouped by task, with per-section Reset/Clear** — five sections (Global/Trading/Charting/Smart DOM/Screenshot), keep-or-replace prompt on a clash ([Hot Keys Configuration](https://help.atas.net/en/support/solutions/articles/72000602396-hot-keys-configuration)) | ModFlow has a keyboard registry + Keys menu; the missing affordances are *sections* and a *conflict prompt*, both cheap and both prevent silent shadowing | S/M | Low |
| 12 | **Per-module templates: Set-as-Default, Clone, Export/Import** ([Working with Templates](https://help.atas.net/en/support/solutions/articles/72000602515-working-with-templates), [Layout Settings](https://help.atas.net/en/support/solutions/articles/72000602557-layout-settings)) | Users cite re-creating templates/workspaces as the #1 switching cost; Export/Import also gives a single-dev household a support channel ("send me the file") | M | Low-Med — must version the payload or imports break across releases |
| 13 | **Ready-made template gallery shipped in-app, plus a Learn Center block (intro / templates / support / connections)** ([Learn Center](https://help.atas.net/en/support/solutions/articles/72000637161-learn-center), [Recommended Templates Gallery](https://help.atas.net/en/support/solutions/articles/72000602455-recommended-templates-gallery)) | Turns onboarding from "read the docs" into "load a working layout, then mutate it" — the fastest known cure for a 30-surface app. Fits the existing help corpus as an entry point rather than new content | M | Low |
| 14 | **Colour-scheme group linking for symbol sync between windows** ([Windows Linking](https://help.atas.net/en/support/solutions/articles/72000637162-windows-linking)) | A no-rule, no-wizard way to make N surfaces follow one instrument — one attribute on each view, instantly legible | M | Med — silent instrument changes are the classic way to misread a ladder; needs a persistent per-window badge |
| 15 | **`Universal` layer semantics** (windows assigned to it stay visible across all working layers) ([Layout Settings](https://help.atas.net/en/support/solutions/articles/72000602557-layout-settings)) | One flag answers "which surfaces should never disappear?" — cheaper than per-layout duplication, and it composes with ModFlow's existing layouts | M | Low-Med — needs a rule for conflicting per-layout settings |
| 16 | **Account-context hygiene: instrument-filtered account list, restore-on-load, explicit `[no account]`** ([Smart DOM Trading panel](https://help.atas.net/en/support/solutions/articles/72000660364-smart-dom-trading-panel)) | The pattern that stops "traded the wrong account" incidents is *showing the absence* of a valid context, not remembering the last one silently | S/M | Low-Med |

**Deliberately not recommended even though ATAS does it:** a renderer-selector UI (Direct2D/GDI/OpenGLSkia), a video-adapter
picker and an FPS-cap control — a WebView2 app cannot honestly offer those, and a fake version of them would be worse
than none ([Common Settings](https://help.atas.net/en/support/solutions/articles/72000602625-common-settings)).

---

## 9. Where ATAS's model does NOT fit ModFlow

1. **Licence-server feature gating.** ATAS's whole product shape is a paid ladder (Start free / PLUS / PRO / ULTRA,
   plus a bonus "MBO Bundle" of Iceberg/Stop-Runs/Sweeps trackers), with real gating — e.g. Replay is explicitly
   unavailable on the free Start plan and available on PLUS/PRO/ULTRA ([atas.net/pricing](https://atas.net/pricing/),
   [Replay](https://help.atas.net/en/support/solutions/articles/72000602247-replay-trading-simulator-)). ModFlow is
   local-first with nothing to phone home to: there is no tier to put a feature behind, so any "plan" concept must be
   either cosmetic or absent. Do not import their upgrade nudges, trial-expiry states or feature-locked panels.
2. **Card-gated trials and refund flows.** Their trial needs a payment card, enables recurring payments, charges €1 as
   a refunded verification, and can be activated once ([free trial](https://help.atas.net/en/support/solutions/articles/72000602400-how-to-register-a-free-trial)).
   Nothing in ModFlow's UX should assume an account, a card, a billing state or a "your trial ends in N days" banner.
3. **Multi-account execution surfaces.** Following Manager ("executing trades on multiple accounts simultaneously with
   one click") and the account-selector machinery exist because ATAS fans out to brokers
   ([Home tab](https://help.atas.net/en/support/solutions/articles/72000602394-home-tab), [Smart DOM Trading panel](https://help.atas.net/en/support/solutions/articles/72000660364-smart-dom-trading-panel)).
   ModFlow is keyless/read-only on the execution side — the transferable part is the *context-hygiene* pattern
   (§8 row 16), not the copier.
4. **Connector onboarding as a first-class workflow.** ATAS ships 51 connector articles, per-feed demo registrations,
   firewall-exception guidance and a connection-status monitor, because "you must connect to a data provider"
   ([connectors](https://help.atas.net/en/support/solutions/folders/72000569858), [technical requirements](https://help.atas.net/en/support/solutions/articles/72000602485-technical-requirements)).
   ModFlow's keyless-first design should have *no* equivalent screen: no credentials, no proxies, no ports, no
   "which account for trading and quotes" decision tree.
5. **A renderer/driver tuning surface.** Renderer choice, hidden-window rendering, render threads, heatmap GPU
   selection, FPS caps and "Vulkan required for Heatmap" are honest for a native stack
   ([Common Settings](https://help.atas.net/en/support/solutions/articles/72000602625-common-settings),
   [technical requirements](https://help.atas.net/en/support/solutions/articles/72000602485-technical-requirements)).
   In WebView2 these knobs either do nothing or lie; performance has to be solved in the data path (`version`-stamped
   payloads, skip-repaint — the parts the SDK note already established).
6. **A two-client parity story.** ATAS is mid-migration: classic Windows client vs ATAS X (Beta) with a tab-based UI,
   macOS support and a ~2.5× speed claim ([atas.net/pricing](https://atas.net/pricing/),
   [completetradersedge](https://completetradersedge.com/atas-review/)). A one-developer app cannot maintain a second
   client's parity notes, migration advice or "which client should I use" FAQ — and the confusion is a documented pain
   point of theirs. Pick one shell and never ship a second.
7. **A native docking/MDI window manager.** Their merge-to-quadrant/centre-to-tab model, per-window Topmost pins and
   undock behaviour ([Windows arranging](https://help.atas.net/en/support/solutions/articles/72000602278-windows-arranging))
   are OS-window problems. ModFlow already has the right split — an in-page grid of surfaces plus an opt-in terminal
   mode with real OS widget windows — so the dock model should be *simulated* in the single page (splitters, tabs),
   not rebuilt in the shell.
8. **DLL/indicator-ecosystem dependency.** ATAS's "Custom Modules" toggle, third-party DLL distribution and the
   community's DLL habit ([Settings Menu](https://help.atas.net/en/support/solutions/articles/72000602252-settings-menu),
   [r/OrderFlow_Trading](https://reddit.com/r/OrderFlow_Trading/comments/1uaiuyw/considering_switching_from_sierra_chart_to/ospqvqw/))
   mean any gap in the product has a marketplace-shaped workaround. ModFlow's extension model is plain Python modules
   written by one person: every gap must be closed in-house or declared, never deferred to an ecosystem.
9. **Support economics as a design input.** Their support load is met by a team with a 24-hour reply record and a
   500-article KB ([Trustpilot](https://www.trustpilot.com/review/atas.net), [KB index](https://help.atas.net/en/support/solutions)).
   A single developer must therefore push *far* harder on in-product explanation (the existing explain cards and help
   corpus are the right shape) and copy the KB's *structure* — folders by module, "articles in this folder", "you may
   like to read" cross-links, per-article modified dates — rather than its volume.
10. **A marketing-shaped UI vocabulary.** Their IA has already absorbed go-to-market language (MBO Bundle, Options
    Board Beta, Cross-Trading, "coming soon" rows) into the product's feature lists
    ([atas.net/pricing](https://atas.net/pricing/)). ModFlow's surfaces should be named for what the trader does, not
    for what the roadmap owes — and "coming soon" placeholders should not appear in a local-first app with no release
    train.

---

## Sources

**ATAS KB (help.atas.net)** — Windows arranging `…/72000602278`; Workspace Setting `…/72000602516`; Layout Settings
`…/72000602557`; Main windows of ATAS `…/72000602420`; Home tab `…/72000602394`; Settings Menu `…/72000602252`;
Common Settings `…/72000602625`; Hot Keys Configuration `…/72000602396`; Smart DOM window overview `…/72000602621`;
Smart DOM Window Columns `…/72000602469`; Trading functions Smart DOM `…/72000602576`; Common Smart DOM Settings
`…/72000602544`; Smart DOM Trading panel `…/72000660364`; DOM Trader `…/72000602463`; Trading Settings `…/72000602491`;
Trading panel for classical markets `…/72000625592`; Trading with Hotkeys `…/72000637159`; Chart window `…/72000602255`;
Chart Display Modes `…/72000602349`; Footprint settings `…/72000606631`; Visual settings of the chart `…/72000602496`;
Working with Templates `…/72000602515`; Recommended Templates Gallery `…/72000602455`; Crosshairs & navigation
`…/72000602265`; Windows Linking `…/72000637162`; Smart Tape `…/72000602608`; Alerts `…/72000602238`; Alerts in Smart
Tape `…/72000636828`; Replay `…/72000602247`; Learn Center `…/72000637161`; Instruments Manager `…/72000602406`;
ATAS SIM `…/72000602259`; Technical requirements `…/72000602485`; Free trial `…/72000602400`; plus KB searches for
`colorblind`, `color scheme`, `theme`, `font`, `monitor`, `second monitor`, `undock`.

**Vendor/marketing** — [atas.net/pricing](https://atas.net/pricing/) (read live, this session).

**Third-party review sites** — [Trustpilot atas.net](https://www.trustpilot.com/review/atas.net) (4.1 / 444);
[AMP Futures ATAS reviews](https://www.ampfutures.com/reviews/atas) (4.57 / 187);
[Complete Traders Edge ATAS review](https://completetradersedge.com/atas-review/).

**Reddit (via PullPush archive API + search snippets, quoted with permalinks)** — `1qz5ccm`, `1scnpc8`, `1s968q3`,
`1t81jq3`, `1uaozg1`, `1vrt8e3`, `1vbe3t0`, `1vzfma7`, `1voh3re`, `1uppbch`, `1w9mt8q`, `1uvhpu8`, `1srbawf`,
`1q8jeja`, `1rc6yyj`, `1re5yc0`, `1rze7gb`, `1t8q1xz`, `1p2gszm`, `1v90ek5`, `1v2zsu8`, `1uaiuyw`, `1vccmh0`.

**Primary anti-sources (things deliberately NOT used):** single-fetch redirects to `sierrachart.com` from two KB
article IDs; the pricing page's per-tier feature matrix (parsed unreliably, so tier contents are reported as
**not read**).
