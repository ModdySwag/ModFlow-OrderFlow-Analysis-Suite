# Quantower — digest for the 2026-09-19 reanalysis

Source: `docs/ux-study/quantower.md`, read 18 Sep 2026 (vendor GitBook, 245-page index; Reddit via RSS/pullpush). Claims from that brief only; gaps it marks "not read" stay unasserted; amounts as published (no currency symbol served).

## 1. At a glance
- Windows-only (Win 10/11, .NET 10) desktop terminal, broker-agnostic ("60+ broker connections"), order-flow heavy; install = folder extractor with **no AppData/registry writes** → portable; uninstall = delete folder.
- Pricing (18 Sep 2026): All-in-One Monthly **70**; 3/6/12 mo **189/336/588** (−10/−20/−30%); Lifetime **1690**; "the Quantower license price does not include third-party market data". Tiers **Free / Crypto / Multi-Asset / All-in-One**; Free (no registration) = 2 indicators/chart, 1 overlay, 1 connection; 7-day full trial.
- Beta+Stable streams; site tops at **1.147.3 (Beta)** (entries to 12 Sep 2026), stable 1.146.18; help centre still headlines 1.146.11 (June) — "the manual trails the product by months".
- Review 8.5/10: "one of the most customizable workspace environments available to retail traders"; wounds: "Windows only, steep learning curve… market data subscriptions cost extra".

## 2. Layout & persistence
- **Unit is an OS window, not a cell**: free position/resize, panels "stick" when close, size-match while resizing; panel menu top-left before the title; the Control Center toolbar Minimize collapses *every* panel on *every* screen.
- Four nested persisted layers: **Workspace** (one XML under `Settings→Workspaces`; autosave 5 min + exit; **Lock** "disables an ability to add, remove, move or resize any panel") → **Bind** ("Super-panel": rectangle-drag select → CREATE BIND/Enter; proportional resize; column separators stick together; edit only via Unbind) → **Group** (tabs; drag header onto a panel, tab out to ungroup) → **Panel** (Template + Set as Default).
- **Colour linking, separate from layout**: same link colour = synced symbol; "the panel's title will be colored"; colour count **not read**.
- Every panel *is* a window; no web-style pop-outs.

## 3. Interaction grammar
- **Right-click is universal**: panel → corner menu (incl. Create Panel, Template actions, **Help**, Settings); table → Group by/columns; toolbar → View.
- **Hotkeys**: 4 categories (panel/General/Drawing/Trading); "you can assign almost any action to your preferred key combination"; actions parameterised (**open template**, **pre-configured order**); **no published count (not read)**. Trading keys need arming ("Enable Keyboard Trading"); 9 confirmations incl. "Confirm hotkeys action".
- **Discovery**: logo icon → colour-coded panel Sidebar; stars pin favourites. **No command/settings search anywhere read** — "Configuration is difficult. You'll often have to Google how to configure something."
- **Instrument lookup is a designed screen** (Connections→Exchange→Type→Subtype tree, persistent filters, multi-select, "3/235" count). Notifications sidebar: "No disturb"; **history erased on restart**. **Per-panel Help**: every corner menu ends with Help → "immediately redirect to the documentation for this panel". Drag quirk: "only being able to drag windows near top of their edges".

## 4. GUI & visual system
- **Eight themes** (5 dark-ish, 3 light, incl. **Grayscale**); no colour-blind mode documented (**not read**).
- Themes are colour **variables**; switching theme **resets in-panel custom colours** — survives only via Set as Default or a Template; editor saves/duplicates; sharing = copy folder.
- Languages: 17 claimed vs "14 other languages" — **pages disagree**. Density per panel: **Slim mode**/**No labels** (order entry), custom titles, abbreviation rules.
- Legibility complaints at both ends: 4K blur "especially on light themes"; footprint too small at zoom (per-column fonts; software render mode).
- **Trust signals are visual**: latency threshold (ms → market-data-delay message), status dots, per-account + global Lock trading, inactivity PIN.

## 5. Standout features/advantages
- OS-window panels with snapping — users' differentiator: "window management is simply superb".
- Templates + Set as Default + layout layers → configured-out-of-the-box order flow: "all the order flow tools are already configured… complex things you can do in 30 seconds"; templates are **sharable files**.
- Order-flow depth: DOM Trader composable columns (Liquidity changes = pulling/stacking, changes counts, Imbalance, Profiles…), refresh-rate in ms (recommend 50), Market Depth 3 colouring schemes + "aggregate size by price".
- Order semantics are per-connection (brackets/OCO/algorithmic types differ by connection). Market Replay ("ridiculously good") + Trading Simulator — All-in-One paid: practice sold, not given.

## 6. Documented pain points (quirk → failure)
- **Lag scales with window count**: "sometimes I get a 20-second delay and have to close and relaunch".
- **Freezing + resource use** blamed on the feed stack esp. Rithmic ("resource hog"); **memory growth** ~2 GB → "over 7GB after several days"; "no matter how much ram you have".
- **Failed exit**: "could not close position … blew a prop account"; **"buggy mess" despite UI love**: "delays and weird bugs every day … the order system also broke and I lost around $1,000".
- **Settings sprawl**: "100 different graphical features that you can set the color on"; **breaking UI change, no compatibility path** (1.146.13): "not all of my settings carried over… had to rebuild some indicators".
- **State doesn't stick**: "saving the layout but it doesn't save" (Trigger OTH); a lifetime licence "completely 'bricked'" by Alpaca/Tradier bugs — "infinite crash loop on startup".
- Signal: layout wins comparisons; recurring damage is **runtime trust**, sprawl, legibility/drag defects, thin API docs.

## 7. Market norms this platform establishes
1. Panels are real OS windows: free geometry, snapping, multi-monitor, minimise-all.
2. Layout persists in layers (workspace ⊃ bind ⊃ group ⊃ panel), autosaved, with a Lock.
3. "Don't configure twice": sharable templates + promoting a panel to its type's default.
4. Panels link by colour to share a symbol, visible on the panel title.
5. Right-click contextual surfaces everywhere; panel menu ends with a Help deep-link.
6. Hotkeys are parameterised and scoped; confirmations are per-action, re-armable.
7. First run shows data: ready workspace + bind of popular panels + demo/delayed connection.
8. Instrument discovery is a first-class screen (tree, persistent filters, multi-select).
9. Notifications are an in-app inbox (categories, "no disturb", act-on-click tiles).
10. Themes are variable-driven, user-editable; 12+ UI languages normal.
11. Data trust is shown: status dots, latency thresholds, trading locks.
12. Replay/simulation is judged; settings sprawl expected; discovery by menu tree, not search.

## 8. Transferable upgrade ideas (ranked)
1. Per-panel Help deep-link to its own doc topic. evidence: Single Panel corner-menu Help. S.
2. "Lock layout" toggle blocking add/remove/move/resize. evidence: Workspaces Lock. S.
3. Armed state for action hotkeys + per-action "confirm hotkey action". evidence: "Enable Keyboard Trading". S.
4. Data-latency threshold + on-panel "market data delayed" badge. evidence: General settings latency threshold. S.
5. Link-group colour on the frame/title, no chip. evidence: link colour colours the panel title. S.
6. "Set as default" per panel type — **keep a reset-to-factory escape hatch**. evidence: Set as Default. M.
7. Quick size buttons with arithmetic/formulas (`;`-lists, signs, multi-row). evidence: DOM OE sidebar. S.
8. Instrument lookup overlay (tree, filters, multi-select, counters). evidence: Symbols lookup. M.
9. Notifications inbox (categories, "no disturb") **with persistent exportable history**. evidence: Notifications center. M.
10. About → "NEW VERSION"; never strand a user on a forced update. evidence: Main Toolbar + "Stuck at force update window". S.
Low-ranked here: bind super-panels + the workspace/bind/group hierarchy (high-blast-radius in a single-window app; 1.146.13 = the cost of layout change without a compatibility story).

## 9. Key sources
Docs base: `help.quantower.com/quantower/`; paths below are under it (read 18 Sep 2026).
1. https://www.quantower.com/pricing
2. getting-started/installation
3. general-settings/{workspaces-binds-groups, standalone-panels}
4. general-settings/{templates, set-as-default, link-panels, custom-hotkeys}
5. miscellaneous-panels/themes-editor
6. https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/
7. https://www.reddit.com/r/Quantower/comments/1v1eb7w/ram_usage_on_quantower_using_multiple_charts/
8. https://completetradersedge.com/quantower-review/
