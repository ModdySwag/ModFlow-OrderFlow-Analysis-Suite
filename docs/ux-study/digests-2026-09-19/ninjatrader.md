# NinjaTrader 8 — digest for the 2026-09-19 reanalysis

Source: `docs/ux-study/ninjatrader.md` (2026-09-18; NT8 help to 8.1.8.2, 11 Aug 2026; pricing read 2026-09; Trustpilot 1,220 rev.). Marked unread there: help screenshots, Web/Mobile UIs, TOS/commission tables, old forum, Reddit.

## 1. At a glance (what it is, pricing 2026, positioning)
- Windows desktop (WPF/XAML) + Web/Mobile, one subscription family; login required ("contacts our server on application log in for user validation"); licence keys removed in 8.1.1 (Mar 2023). Floor: Win11/Server2016+, .NET 4.8, 2 GB RAM.
- Pricing: Free $0/mo ($0.39 micro / $1.29 standard per side); Monthly $99/mo ($0.29/$0.99); Lifetime $1,499 ($0.09/$0.59). All plans: Desktop+Web+Mobile, top-of-book data, "free simulated trading"; Order Flow+, Market Replay, Pulse need a funded live account. Vendor: "always free for advanced charting, backtesting and trade simulation".
- Quirks: free licences can't disable Global Simulation Mode, and two official pages conflict on whether it needs a live licence (flagged, unresolved). Static SuperDOM free since 8.1.7 (May 2026). Local state in `Documents\NinjaTrader 8\` (vendor: exclude from cloud backup).

## 2. Layout & persistence (workspaces, windows, tabs, version history, safe mode)
- Control Center = shell + taskbar, always on: New/Tools/Workspaces/Connections menus + tabs (Orders, Strategies, Executions, Positions, Accounts, Log, Messages, Connection Status). Every surface is an independent OS window; New = flat catalogue of ~20 window constructors.
- Workspaces = saved arrangements, **one visible at a time**: "You can only have one active workspace" (SHIFT+F3) — 15 windows on three 34" monitors must fit one. Removal "cannot be undone"; Tools→Database Management→Restore Workspace keeps **10 prior versions by default**. Tabs: drag-reorder, right-click close/rename/duplicate/move, CTRL+Tab; no way to colour a tab.
- No docking documented; Windows snapping plus per-window Always on top. **Safe Mode** = hold CTRL at launch to load without add-ons. 8.1.7 fixed "First maximize extended beyond the visible monitor area".

## 3. Interaction grammar (mouse, keyboard, right-click validity; Hot Keys; title tokens)
- Context-valid right-click: "Available order types in the right click menu will be limited to those which will be accepted by a brokerage, based on the side of the market on which you right click." Right-click also opens per-surface Properties; grids share one contract (columns, CSV/Excel, print, search).
- Freeze-on-hover: dynamic ladder suspends updates on hover, turns red, pins bid/net-change/ask in the top row. Ladder mouse grammar: left=limit, Ctrl+left=MIT, middle=stop-limit, Ctrl+middle=stop-market; modify is deliberately two-step ("eliminates the potential errors… dropping an order on the wrong price").
- Chart Trader: a collapsed state keeps orders + live placement while the panel hides "to maximize screen space".
- **Hot Keys window** (Tools→Hot Keys): categories by active window + Global ("always active… except when a modal window has focus"); "Click to record hot key"; **conflicts detected**; window-sensitive (active window = red close button). "It is easy to confuse Ctrl+B with Shift+B…"; "ALL Hot Keys are inactive any time a modal form window is open".
- **Dynamic title tokens**: `@INSTRUMENT`, `@PERIOD`, `@ACCOUNT`, `@FUNCTION`, `@ATM`, `@DATASERIES` (+`_ALL`); `++MSFT` opens a pre-loaded tab. Linking: colour-matched link buttons (same colour = same instrument request), Link All, interval link.

## 4. GUI & visual system (skins, density, the facelift critique)
- Default: "a 2015-era Windows desktop application" — separate OS windows, chrome behind right-click Properties, dense grids, permanent Control Center; light/dark skins switch in Options→General **with a restart required**.
- Theming is source-level: XAML per window, edited under `templates\Skins`; custom colours "only apply to the specific Color Picker in which they are typed"; 8.1.7 added a real picker and fixed dark-on-dark theme legibility. Colour is semantic **plus** labelled; sim accounts repaint order surfaces ("Simulation color…"); fonts per-surface.
- Facelift critique: Trustpilot — "all they need to do is give it a facelift, make it more intuitive, trader friendly, give it a feel of TradinView, and how about an in-built trade analysis tool". QuantVPS: "High cost; complex interface". 8.1.7 (11 yrs after v8) marquee = volume control, colour picker, customisable toolbar; user: "basic stuff that should have been default features years ago".

## 5. Standout technical features/advantages
1. **ATM strategies** — reusable bracket rule sets; one dropdown bearing four meanings distinguished only by iconography (None / template / **active instance marked with a lightning bolt**); server-side templates keep working disconnected ("Suspended" state).
2. **Global Simulation Mode + Trading Mode gate** (8.1.1) — explicit Live-or-Simulation at login; sim surfaces painted; free licences can't switch the guard off.
3. **Workspace version history** — 10 versions + Restore; import/export.
4. **Colour-coded linking + Link All** — the colour *is* the explanation.
5. **Safe Mode** for add-on isolation; vendor warns a bad add-on "can have adverse effects on the entire NinjaTrader application".
6. **Drawing objects first-class** — drag between panels/tabs/other windows.
7. **Scale-up path**: curated starter workspaces (8.1.7), unlimited sim accounts, free 14-day live-data sim, Nina AI coach (15 Sep 2026).

## 6. Documented user pain points
- Modal-heavy: "too many steps/clicks… Everything requires a modal dialog… slows you down during the trading day."
- Markings/layout top annoyance: no Undo for drawings, no multi-select move, no Hide-All-Indicators; "cannot have more than 1 chart in 1 window/tab is a crime".
- Performance creep: "resizing charts has become painfully sluggish… sticky and unresponsive"; workspace load + sync ">3m" (8.1.7) vs "<1m" (8.0.x).
- Stability: "Every single day I have multiple freezes/crashes/data not loading… This is not professional software" (Aug 2026); "i don't keep live orders on the same box as the charts anymore".
- Regressions: 8.1.7 broke compile/fill sounds (rollback to 8.1.6.3); 8.1.8 stale-data/custom-column crashes; theme defects survive years (dark-mode rows fixable only via `brushStrategyActive`).
- Roadmap scepticism; cost clash "$720/year" vs Free/$99/$1,499 (different things — don't conflate).

## 7. Market norms this platform establishes
1. Layouts are named, restorable, exportable, versioned objects.
2. Right-click is the primary config route, offering only actions valid *here*.
3. A live canvas can be frozen in place for inspection.
4. Destructive actions are graded by blast radius; undo is assumed.
5. Settings dialogs are instantly reversible.
6. State is encoded redundantly: colour *plus* a label that survives screenshots.
7. Related surfaces link from one visible colour-matched control.
8. Every action has a keyboard route; the registry detects conflicts.
9. Surfaces self-label from live state (title tokens).
10. Mode/health is visible before acting.
11. Curated starter layouts ship with the app, not a blank canvas.
12. Density is forgiven when the power is real; "complex interface" when it isn't.

## 8. Transferable upgrade ideas for an analytics-layer tool (ranked)
1. Dynamic title tokens on panels/tabs. evidence: Using Tabs token list. S/Low.
2. Context-validity filtering of right-click menus. evidence: Chart Trader. M/Low.
3. Freeze-on-hover for Depth/Tape/Heatmap. evidence: Static vs Dynamic ladder. S/Low.
4. Layered destructive-action depth. evidence: "only the first 3 nearest stops and targets". S/Low.
5. Collapsed panel that keeps function. evidence: Chart Trader Hidden View. S/Low.
6. Semantic colour + text label on every mark. evidence: LMT/STP/SLM/MIT beside colour. S/Low.
7. Colour-coded link groups + Link All + interval link. evidence: Window Linking. M/Low.
8. Workspace version history + import/export. evidence: Workspaces Menu (10 retained). S–M/Low.
9. Preset save/restore in every settings dialog. evidence: SuperDOM Properties. S/Low.
10. Typed overlay selector (`++SYMBOL`) + printable hot-key registry. evidence: Using Tabs; Working with Hot Keys. S/Low.
Also: Undo + multi-select for markings; one right-click grid contract (CSV/Excel, column controls, search). evidence: Discourse /2937.

## 9. Key sources
`<help>` = https://ninjatrader.com/support/helpguides/nt8/
- Help pages (all `<help>*.htm`): control_center, using_tabs, submitting_orders4, static_vs_dynamic_price_ladder, working_with_hot_keys, workspaces_menu, 8_1_7, creating_your_own_skin, using_3rd_party_add-ons
- https://ninjatrader.com/pricing/ · https://www.trustpilot.com/review/ninjatrader.com
- https://discourse.ninjatrader.com/t/what-would-you-like-to-see-in-a-new-ninja-trader-8/2937
