# QUANTOWER — UX / GUI study for ModFlow OrderFlow Analysis Suite

Read-date for everything below: **18 September 2026**. Vendor docs are GitBook; every help page has a `.md` twin
(`…/<path>.md`) and the whole manual is indexed in `https://help.quantower.com/quantower/llms.txt` (**245 pages**,
counted from `…/sitemap-pages.xml`). Claims that could not be verified are marked **not read** — no price, tier
content or hotkey count is guessed.

**What the in-repo study already covered** (`docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md`, read-only — §§1–15): the widget
shell host and re-parenting model, the layout store shape and sanitiser, the Layout menu, link groups A–D, the channel
bus with refcounts, the Bookmap fold-in, and Quantower as a **platform-parity surface** (workflow steps, plan toggle,
install detection). It cites Quantower's workspace/templates/licence pages only as a *layout language reference*.
**What this brief adds:** the GUI itself — how their panels dock, group, bind and persist; how features are
discovered; the pointer/keyboard contract; the visual system; onboarding; and what real users say, with URLs.
Nothing here re-states the architecture findings.

---

## 1. Snapshot

| Fact | Value | Source |
|---|---|---|
| Product | Desktop trading terminal, order-flow/volume-analysis heavy, Windows-only, broker-agnostic (60+ connections claimed by a third party) | Quantower installation page (Windows 10/11, .NET Desktop Runtime 10); review "60+ broker connections" — completetradersedge.com |
| Shell / install model | "Installer" is a folder extractor: **no AppData/Program Files writes and no registry writes**, so it runs portable from a removable drive; uninstall = delete the folder | [Installation](https://help.quantower.com/quantower/getting-started/installation) |
| Main executable | `Starter.exe` (firewall prompt on first run) | [Installation](https://help.quantower.com/quantower/getting-started/installation) |
| Persistence | A `Settings` folder inside the install: workspaces are **XML** files under `Settings → Workspaces`; templates live in `Settings → Templates`; settings autosave every 5 min and on exit | [Workspaces](https://help.quantower.com/quantower/general-settings/workspaces-binds-groups), [Templates](https://help.quantower.com/quantower/general-settings/templates), [General settings](https://help.quantower.com/quantower/general-settings/general-settings-1) |
| Extension layer | C# API + Visual Studio / VS Code / Atom integration; vendor-built paid extensions (DOM Surface, Power Trades, Volume Analysis, TPO, Advanced features, Option trading, Multi-asset, Crypto) sold à la carte, **plus** "Third-party extensions produced and supported by the standalone development teams" | [Quantower Algo](https://help.quantower.com/quantower/quantower-algo/introduction), [pricing page](https://www.quantower.com/pricing) |
| Localisation / theming | 17 languages claimed on the settings page (the localisation page says "14 other languages" — the two pages disagree); themes are user-editable colour-variable sets | [General settings](https://help.quantower.com/quantower/general-settings/general-settings-1), [Localization](https://help.quantower.com/quantower/customization/localization), [Themes editor](https://help.quantower.com/quantower/miscellaneous-panels/themes-editor) |
| Release cadence | Two parallel streams, Beta and Stable. Website release notes top out at **1.147.3 (Beta)**, entries dated to 12 September 2026, with **1.146.18** the current Stable; ~23 versions on one page | [quantower.com/release-notes](https://www.quantower.com/release-notes) (read 18 Sep 2026) |
| Doc-lag fact | The help centre's own "Release Notes" page still headlines *"Latest release — v1.146.11 (Beta · June 13, 2026)"* while the website shows 1.147.3 — **the manual trails the product by months** | [help: Release Notes](https://help.quantower.com/quantower/updates/latest-version) vs [site release notes](https://www.quantower.com/release-notes) |

**Pricing model, as read from source.** The All-in-One licence block renders `pr-main-price = 70` for **Monthly**, and
the same `data-price` set carries 3 months = 189 (−10 %), 6 months = 336 (−20 %), Annual = 588 (−30 %), Lifetime =
1690; the sibling `data-profit` attributes (full price, $-prefixed: $210 / $420 / $840) match 3× / 6× / 12× the monthly
figure, so 70 is the monthly figure in the page's default currency. The served HTML contains **no currency symbol or
currency selector** (currency is applied client-side), so I quote the numbers as published and do not assert a
currency. Same page: "10 days money back guarantee", "⚠ the Quantower license price does not include third-party
market data that must be purchased additionally", a **free edition with no registration** (2 indicators per chart,
1 overlay, 1 connection), a **7-day full-featured trial** on registration, and "buy pro-features apart". Licence
tiers in the comparison table: **Free / Crypto / Multi-Asset / All-in-One**. ([pricing page](https://www.quantower.com/pricing),
[License comparison](https://help.quantower.com/quantower/getting-started/account-and-licensing/license-comparison),
[Licenses](https://help.quantower.com/quantower/getting-started/account-and-licensing/quantower-licenses), read 18 Sep 2026.)

---

## 2. Layout & windowing model

**The unit is an OS window, not a cell.** "Standalone panels … behave just like any usual PC window": free
resize/position anywhere, **stick to each other within their borders when close enough**, "stick its size to repeat
the dimensions of other panels" while resizing, and collapse to the **OS taskbar** like a normal window. Each panel's
own menu lives in its **top-left corner, immediately before the title**. ([Single Panel](https://help.quantower.com/quantower/general-settings/standalone-panels))

**Four nesting layers, all persisted:**

1. **Workspace** — the top level, one XML file each; a manager list with the active entry colour-marked and dot-prefixed;
   actions **Lock / Rename / Create new**; a new workspace is either **Blank** or seeded with a predefined panel set
   (their first-start ships one of these). Auto-saves every 5 minutes and on exit; `Ctrl+S` forces a save.
   *Lock* "disables an ability to add, remove, move or resize any panel". ([Workspaces](https://help.quantower.com/quantower/general-settings/workspaces-binds-groups))
2. **Bind** — a "Super-panel": rectangle-select several panels ("hold the left mouse button and drag over the panels"),
   then `CREATE BIND` or **Enter**. A bind resizes proportionally as one unit, inner separators can be dragged and
   **separators that line up in one column stick and resize together**, and it can only be edited by unbinding
   ("Unbind"). Non-resizable screens (Connections manager, Settings) cannot be bound; intersected panels cannot be
   bound. ([Binds](https://help.quantower.com/quantower/general-settings/binds))
3. **Group** — nested tabs: "click and drag one Panel's header over another" to group, "drag an active Panel's tab out
   of group tabs bar" to ungroup; tabs reorder, close and rename (default name "Group"). ([Group of panels](https://help.quantower.com/quantower/general-settings/group-of-panels))
4. **Panel** — with **Template** and **Set as Default** as the reuse layer (details in §6).

**Chrome & always-on-top.** Every panel's corner menu carries: Link · Create Bind · **Create Panel** (a sub-menu that
spawns Order Entry, Chart, DOM Trader, Market Depth, Time&Sales, DOM Surface, TPO Chart, Symbol Info *on the current
symbol*) · Duplicate Panel · Save as Template · Apply Template · Save as default · Setup Actions (table panels) ·
**Always on Top** · Export Data · Make Screenshot · **Help** · Settings. ([Single Panel](https://help.quantower.com/quantower/general-settings/standalone-panels))

**The Control Center (main toolbar) is itself a docked panel** — draggable across screens, always pinned to the top of
the screen, width-adapting, and other panels can stick to it; its **Minimize** collapses *every* panel on *every*
screen to the taskbar. Its controls are individually hideable via right-click → **View** (time zones, workspaces,
connections…). ([Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar))

**Chart linking is colour-based, and separate from layout.** "Link allows linking several panels by common symbol
using the Color definition. Just select one link color in two panels and they will have a synchronized symbol
parameter. Once linkage is applied, **the panel's title will be colored** to the respective color." How many colours
exist is **not documented** on that page. Chart crosshair sync is a *second*, per-chart setting (current chart / all
charts with the same symbol / charts with different symbols) that you must configure on each chart. ([Link panels](https://help.quantower.com/quantower/general-settings/link-panels),
[Chart view settings](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/view-settings))

**Multi-monitor:** documented for the toolbar (drag among screens) and for the panel model (OS windows), and asserted
by users for binds/groups ("move them to different monitors", u/akinon). Pop-out windows in the web sense do not
exist — every panel *is* a window. ([Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar),
[user report](https://www.reddit.com/r/FuturesTrading/comments/1998fkc/sierra_chart_vs_quantower/kifi5mi/))

---

## 3. Navigation & information architecture

* **One launcher, not many menus.** The whole catalogue of panels lives behind the **logo icon** on the Control
  Center: a "Sidebar" of panel icons **grouped by function, each group colour-coded**, collapsible, launching by left
  click; the footer holds About/Exit — and when an update is detected, a **"NEW VERSION" button replaces the About
  link**. ([Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar))
* **Favourites as the fast path.** A star on any Sidebar tile pins that panel to a "Favorite panels" bar on the
  toolbar; a star on a connection pins it to "Favorite connections", each shown as a tile with connection name, status
  text (message *or* ping in ms) and a **status dot: grey = disconnected, yellow = connecting, green = active**.
  ([Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar))
* **Settings are a screen, not a dialog tree:** the gear opens General settings with nine tab groups (General, Control
  Center, Sounds, Confirmations & Warnings, Time zone, Excel RTD, Messengers, Hotkeys, Trading protection). "Most
  changes are applied automatically, but complex settings require confirmation". ([General settings](https://help.quantower.com/quantower/general-settings/general-settings-1))
* **There is no command search / settings search** in anything I read (245-page index, settings page, toolbar page,
  table page, hotkeys pages — checked 18 Sep 2026). Discovery is by menu tree, star favourites, per-panel **Help**
  deep-links, and search *inside* specific surfaces: symbol lookup, table quick filters, indicators/drawing pickers.
  A user states the cost plainly: "Configuration is difficult. You'll often have to Google how to configure
  something." ([u/masilver](https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/nj4a84h/))
* **Instrument lookup is a designed screen**, not a dropdown: symbol field (pre-fills the search) + a "⋮" lookup that
  opens unfiltered; three-part screen (search toolbar / tree of Connections → Exchange → Type → Subtype / footer);
  secondary filters by connection, symbol type and exchange that **persist between invocations while the search field
  resets** (their own docs warn "Be careful"); `Ctrl`-click for multi-select confirmed by a blue circle button;
  footer mass expand/collapse plus a **count readout that shows both totals and selection** ("3/235").
  ([Symbols lookup](https://help.quantower.com/quantower/general-settings/instruments-lookup))
* **Notifications are a sidebar with its own IA:** the toolbar icon shows an unread count and is the *only* way in
  ("Should you choose to remove or hide this icon from the Control Center, accessing the complete list of notifications
  becomes impossible"), the sidebar overlays panels and auto-hides on outside interaction, and it has a quick-action
  row: **disable ALL pop-ups ("No disturb") · Read → Delete (two clicks clears everything, ignoring filters) ·
  category filter · settings**. Notifications are New/Read, tiles carry title/description/timestamp/category/accent
  colour, clicking one *acts* (opens detail, or the About screen for update notices), pop-ups have a max-count,
  auto-hide timer and **hover-holds them open**. History is **erased on restart**. ([Notifications center](https://help.quantower.com/quantower/general-settings/notifications-center))
* **Support is a panel** (Live Support chat, bindable with other panels, with an "email the dialog to yourself"
  option), alongside a website chat. ([Live Support](https://help.quantower.com/quantower/miscellaneous-panels/live-support))

---

## 4. Interaction model

### Mouse
* **Panel drag** is by the title/header area — the only user report of a hardware-level ergonomics defect I found is
  about this: "only being able to drag windows near top of their edges … really makes me question the developers
  attention and care" ([u/Protonverse](https://www.reddit.com/r/OrderFlow_Trading/comments/1qokf7f/is_quantower_a_buggy_mess_or_is_it_just_me/p5ewmzi/)).
* **Right-click is the universal secondary surface:** on a panel → its corner menu; on a table (anywhere in the body)
  → Group by / Add symbols / column set / setup actions; on a column header → column set; on the Order Entry sidebar
  → Set order as default, Save order template, Settings; on the DOM price scale → display options; on the toolbar →
  View (show/hide controls). ([Table management](https://help.quantower.com/quantower/general-settings/table-management),
  [Chart trading](https://help.quantower.com/quantower/trading-panels/chart-trading), [DOM columns](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-columns))
* **Hover → reveal:** workspace trash icon and notification delete "×" appear on hover; sidebar stars appear on tile
  hover.
* **Drag-to-compose is the layout gesture set:** drag a header onto another panel to form a tab group; rectangle-drag
  over panels to select them for a Bind; drag column headers to reorder and their borders to resize; drag the DOM's
  inner separators.

### Keyboard
* **Four hotkey categories** in chart/DOM settings — panel-specific custom hotkeys, **General**, **Drawing Tool**, and
  **Trading** — and the docs explicitly say "you can assign almost any action to your preferred key combination".
  ([Chart hotkeys](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/hotkeys))
* **Arming is a safety layer:** only *trading* hotkeys require the **"Enable Keyboard Trading"** toggle on the panel
  toolbar (a keyboard icon); everything else fires on the active panel. ([Chart hotkeys](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/hotkeys),
  [Chart trading](https://help.quantower.com/quantower/trading-panels/chart-trading))
* **Scope is explicit:** panel-specific hotkeys "trigger for the focused panel only" and apply to *all panels of the
  same type*; global custom hotkeys "trigger no matter in what panel … you are working in". Custom hotkeys currently
  exist in Chart and Watchlist panels plus General settings, as a collapsible block at the top of the Hotkeys section.
  Actions are **parameterised and re-usable**: change to symbol, set period, add indicator, add any drawing, open a
  specific panel, **open a template**, **place a pre-configured order** (configured through an embedded Order Entry
  panel and saved), and **run a strategy** — several actions may be added more than once with different parameters,
  others are unique. ([Custom hotkeys](https://help.quantower.com/quantower/general-settings/custom-hotkeys))
* **A hotkey count is not published** anywhere I read (chart hotkeys, DOM hotkeys, custom hotkeys, General settings —
  checked 18 Sep 2026): **not read / no count**.
* **Confirmations you can see and re-arm:** nine toggles — order placement, cancellation, order/position modification,
  position reversing, application close, bind close, group close, deal tickets, **"Confirm hotkeys action"** — and
  a hotkey-placed order inherits the order-placement confirmation (so disabling confirmations also silences the
  hotkey path, which the docs call out). ([General settings](https://help.quantower.com/quantower/general-settings/general-settings-1))
* `Ctrl+S` saves the workspace; `Ctrl`-click multiplies mouse-placed orders; `Shift`+click places a stop instead of a
  limit in the DOM; `Ctrl`+wheel changes the DOM price step.

### Order entry flows (four overlapping ones, deliberately)
1. **DOM Trader mouse mode** — "Left-click at a specific price in the left column will place a Buy Limit order … in the
   right column … a Sell Limit"; a click that crosses the market executes at market; **Stop = hold `Shift` + click**.
   ([DOM Trader](https://help.quantower.com/quantower/trading-panels/dom-trader))
2. **DOM/Chart/Market-Depth Order Entry sidebars** — Bid / Ask / Market buttons, bracket SL/TP, then a summary
   confirmation dialog with a "Do not show again" that is re-armed from General settings. Each sidebar is configured
   **independently** (standalone OE ≠ chart sidebar ≠ DOM sidebar ≠ DOM Surface ≠ TPO). ([Order Entry](https://help.quantower.com/quantower/trading-panels/order-entry),
   [DOM OE sidebar](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/order-entry))
3. **Chart mouse trading** — one icon to arm; **above price: left = Buy Stop, right = Sell Limit; below price:
   left = Buy Limit, right = Sell Stop**; hold `Ctrl` to place several in a row. ([Chart trading](https://help.quantower.com/quantower/trading-panels/chart-trading))
4. **Keyboard trading** — arm with the keyboard icon, then fire (docs point at the same hotkey list).

Reusable entry parameters: **quick quantity buttons** that accept a **divider `;` list, multiple rows, and formulas
and signs to "increase, decrease, or reset the current value"**; a quantity reset-to-default after each order; a
**dollar-value slider** for size (with a leverage warning); **order templates** saved from the sidebar's context menu
and applied from a dropdown; and per-row **crypto sizing modes** (quantity / total balance / % of balance).
([DOM OE sidebar](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/order-entry),
[Chart trading](https://help.quantower.com/quantower/trading-panels/chart-trading))

### Chart interaction
The panel is documented as five zones: top toolbar (symbol lookup, timeframe+chart type, history depth, chart style,
volume-analysis toggle, *keyboard trading* toggle, *mouse trading* toggle, quick order entry at best bid/offer,
sidebar order entry with qty+TIF) · the chart area · the sidebar (drawings, indicators, overlays, **object manager**),
· order entry · bottom volume-analysis toolbar. Price scale has **four auto modes** (Auto, Auto centered, Keep in
view, Manual — dragging flips it to Manual, right-click the scale for the menu), a **"Time to next bar"** readout and
a **"Snap to Last"** button that appears only when you have scrolled into history. **Mouse wheel behaviour is
configurable per modifier**: plain / `Ctrl` / `Shift` wheels each map to Scroll, Zoom of the chart area, Zoom to
cursor, or Price-scale zoom. Drawings can be scoped **"All Charts with the Same Symbol"**, starred onto the sidebar,
and saved as **drawing templates** (since v1.126) that are switched from the drawing's context menu. An **Info
Window** has its own content/font settings. ([Chart overview](https://help.quantower.com/quantower/analytics-panels/chart/general-overview),
[Chart view settings](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/view-settings),
[Drawing tools](https://help.quantower.com/quantower/analytics-panels/chart/drawing-tools),
[Info Window](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/info-window))

**DOM Trader as a dense instrument:** three trading paths, a **refresh-rate in ms** ("value 1 = process every level-2
change; we recommend 50"), **ticks-to-scroll**, custom tick size (also `Ctrl`+wheel), short price format, abbreviation
rules (Default / Round to / Abbreviate), a sessions template, and a column set the user composes — price, optional
split Bids/Asks, optional Buy/Sell, **Liquidity changes (pulling/stacking)**, **Number of changes**, **Cumulative
changes**, Comments, Last/Bid/Ask trade size, Cumulative size, Imbalance, P&L, Profiles. The vendor's own scalping
recipe is a good template of *how* they expect it to be tuned: 100 levels, fonts to Arial 12 per column, **merge
bid/ask into one column** (which requires closing and reopening the settings panel!), remove the volume gradient, set
a big-volume threshold, quick buttons 1/2/5/10/20, and hotkeys for close/flip. ([DOM view settings](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/view-settings),
[DOM columns](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-columns),
[DOM for scalping](https://help.quantower.com/quantower/trading-panels/dom-trader/how-to-set-up-dom-for-scalping),
[DOM hotkeys](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/hotkeys))

**Market Depth** separates "look" from "click": Level-1 bar + position bar (contracts, average price, live P/L) +
optional columns, with **three colouring schemes** (by price level / relative to volume / step-to-max-volume with a
configurable max and the two extreme colours), plus "aggregate size by price" to merge the same price across ECNs.
([Market depth](https://help.quantower.com/quantower/trading-panels/market-depth))

**Order semantics are capacity-aware, not generic:** the order-type page is a per-connection matrix — CQG: Market/
Limit/Stop/Stop-Limit, **server-side brackets (single and multiple)**, server-side OCO, algorithmic orders (Iceberg,
Trailing Limit), *no* Trailing Stop; Rithmic: adds server-side Trailing Stop, MIT/LIT, brackets **single only**;
Binance Spot: no brackets, no OCO; Binance Futures: server-side brackets only for an *existing* position. TIF set
includes DAY/FOK/GTC/IOC/GTD and "the TIF list can be different depends on connection, order type or instrument
type!". ([Order types](https://help.quantower.com/quantower/trading-panels/order-entry/order-types),
[Order Entry](https://help.quantower.com/quantower/trading-panels/order-entry))

---

## 5. Visual design language

* **Eight shipped themes**: Default Blue, Dark Autumn, Dark Forest, Dark Gold, **Grayscale**, Light Forest, Light
  Gold, Light Water — i.e. five dark-ish, three light, plus a desaturated option that is the closest thing to a
  colour-blind/neutral palette they ship. No colour-blind mode is documented as such (**not read / not documented**).
  ([General settings](https://help.quantower.com/quantower/general-settings/general-settings-1))
* **Themes are variables with a stated precedence rule**: "each panel, screen, or technical message uses these
  variables as color defaults and then applies the custom colors set by the user via settings". Switching theme
  **overrides all in-panel custom colours and resets them** — deliberately, "to keep the overall UI presentation
  complete and persistent (especially when switching between dark and light themes)" — and the only way to survive a
  theme switch is to have saved per-panel **Set as Default** or a **Template**. The Themes editor exposes the
  variables, supports save/duplicate/apply/discard, only on custom themes (defaults are read-only), and sharing is
  copy-the-folder. ([Themes editor](https://help.quantower.com/quantower/miscellaneous-panels/themes-editor))
* **Density knobs at panel level, not just globally:** the order-entry sidebar has **Slim mode** and **No labels**;
  panels accept a custom title; abbreviation rules for sizes appear in both chart and DOM; "Abbreviate volume & ticks"
  and "Abbreviate crypto prices" are global; margins (top/bottom/right) and plate alignment (vertical/horizontal) are
  chart settings. ([DOM OE sidebar](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/order-entry),
  [Chart view settings](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/view-settings))
* **Legibility is a first-class complaint at both ends:** two 4K-screen reports of blurry text ("The text looks pretty
  blurry, especially on light themes", u/at-de-money) answered by another user ("change the text properties" /
  "no HiDPI change required" on four 4K displays), *and* footprint numbers too small to read at compressed zoom
  ("hard to read due to sizing and scaling issues. Is there a setting to increase the font size for the numbers shown
  in the footprint?"). Vendor mitigation is real but blunt: fonts per column, a **software render mode** for chart
  flicker, and "hide part of an account name". ([blurry text thread](https://www.reddit.com/r/Quantower/comments/1t9tabg/blurry_text_on_hidpi_screen/),
  [footprint sizing](https://www.reddit.com/r/Quantower/comments/1ns1tfq/footprint_chart_sizing_and_scaling/),
  [General settings](https://help.quantower.com/quantower/general-settings/general-settings-1))
* **Trust signals are visual and per-panel:** data-latency threshold (user sets ms; "a message about market data
  delays will be displayed in the trading panels"), connection status dot colours, per-account and global **Lock
  trading**, an inactivity PIN lock and an order-rate limiter under "Trading protection", and a Beta-version toggle.
  ([General settings](https://help.quantower.com/quantower/general-settings/general-settings-1), [Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar))
* **Colour carries meaning in the data layer, and it is configurable** — DOM asks/balance colouring modes, DOM Surface
  brightness tied to a max-level-2 size, notification accent colours, link colours on panel titles.

---

## 6. Onboarding & discoverability

* **First launch is a chooser, not a blank canvas**: after extraction the platform starts itself and asks you to pick
  the default **connection** (dxFeed Simulated — limited symbols, **24-hour delayed**, "meant only for getting to know
  the platform"; or Binance in **Info mode**, real-time crypto data, trading disabled) and the default **workspace**;
  then the terms window. ([Installation](https://help.quantower.com/quantower/getting-started/installation))
* **The default state has data in it**: "Out of the box you get: a ready-to-use workspace, **a bind that links a few
  of the most popular trading panels**, and a live connection … so there's real data on your charts from the first
  second." ([First start](https://help.quantower.com/quantower/getting-started/first-start))
* **Learn-by-inspecting, not by a wizard run-through**: every panel's corner menu ends with **Help**, which "will
  immediately redirect to the documentation for this panel" — the manual is addressed per panel, and every page has a
  `.md` twin plus an `?ask=` natural-language query endpoint (GitBook). ([Single Panel](https://help.quantower.com/quantower/general-settings/standalone-panels),
  [llms.txt](https://help.quantower.com/quantower/llms.txt))
* **Templates are the "don't configure this twice" mechanism**: save *any* panel, Group or Bind as a named template,
  stored under Sidebar → **Templates**, launchable from there, star-able onto the toolbar, editable/deletable from a
  context menu; a template stores "sizes, coloring, internal elements visibility, a predefined symbol of accounts
  values, additional specific settings"; templates are **plain files you can share** (and users do — the docs point
  people at a Discord thread for themes). A panel inside a Bind can only be templated as the Bind. ([Templates](https://help.quantower.com/quantower/general-settings/templates),
  [Themes editor](https://help.quantower.com/quantower/miscellaneous-panels/themes-editor))
* **"Set as Default" redefines the factory preset** for a panel *type* — and it is deliberately destructive: "In the
  latest version of the platform, we have removed the 'Reset to Default' option. Therefore, each time clicking on the
  'Set as Default' you redefine the previous settings." Their own warning shows the cost model: saving volume tools as
  default makes **every new chart** load tick/volume data. ([Set as Default](https://help.quantower.com/quantower/general-settings/set-as-default))
* **Practice surfaces are sold, not given** — and that's a discoverability decision worth noting: **Market Replay**
  (History Player) and the **Trading Simulator** (emulated fills on *any* connection, including non-tradable ones) are
  All-in-One features (Crypto-only on the Crypto tier), so a free user's "try it before risking money" path is
  limited to the demo/sim assets their broker provides. Users rate the replay anyway: "the Replay feature is
  ridiculously good". ([License comparison](https://help.quantower.com/quantower/getting-started/account-and-licensing/license-comparison),
  [Market Replay](https://help.quantower.com/quantower/trading-panels/market-replay), [Trading simulator](https://help.quantower.com/quantower/trading-panels/trading-simulator),
  [u/Kdogg_456](https://www.reddit.com/r/FuturesTrading/comments/1998fkc/sierra_chart_vs_quantower/kjw8egn/))
* **Update flow, with a cautionary tale:** About shows version/rollback/update checker and swaps to a **"NEW VERSION"**
  button; a Beta toggle opts into pre-release builds; the docs say updates are automatic checks, one-click downloads
  and rollback to a previous version. One user's experience is the counter-example: a post titled *"Stuck at force
  update window"*. ([Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar),
  [llms.txt description of Platform update](https://help.quantower.com/quantower/llms.txt),
  [r/Quantower post](https://www.reddit.com/r/Quantower/comments/1kz5yik/stuck_at_force_update_window/))

---

## 7. What users actually say

### Praise (with URLs)
1. **Windowing/snapping is the differentiator.** "Quantower is the sexiest platform out there. Lots of functionality
   and love the **window management/snapping**, top notch aesthetics." — u/ashlee837, r/FuturesTrading.
   <https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/mu48u95/>
2. **The three layout layers, specifically.** "The **window management is simply superb**. You can create binds or
   groups and move them to different monitors. Moreover, all windows come with snap features." — u/akinon.
   <https://www.reddit.com/r/FuturesTrading/comments/1998fkc/sierra_chart_vs_quantower/kifi5mi/>
3. **Configured-out-of-the-box order flow, easy start.** "It's great, all the order flow tools are already
   configured, and everything is pretty easy to use. There are complex things you can do in 30 seconds" (same author
   then reports the lag, below). — u/Tetra-drachm.
   <https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/mu4qonw/>
4. **Low learning curve for candle traders.** "QT is smooth … if you are into candle trading QT has a **easy learning
   curve** and very easy to get used to". — u/00_Kaizen.
   <https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/mu59khy/>
5. **Intuitiveness vs NinjaTrader.** "I have been trying to learn NT but it is unusually difficult … **QT is
   intuitive**." — u/yhpark5. <https://www.reddit.com/r/FuturesTrading/comments/194u66e/quantower_vs_ninjatrader/kwpgc6o/>
6. **UI/customisation as the reason to stay.** "QT **nails the UI** part, especially when it comes to customization of
   color schemes, font sizes etc. … I've been using QT for several years now and don't have to think about doing
   anything within the application." — u/vaxdatex.
   <https://www.reddit.com/r/Quantower/comments/1v1eb7w/ram_usage_on_quantower_using_multiple_charts/oyov96j/>
   Same user, elsewhere: "Quantower nails the UI … the rest is just IMHO the best option when it comes to ease of use
   and intuitive UI." <https://www.reddit.com/r/Quantower/comments/1udnvn1/update_to_14613_breaks_cluster_charts/otfgmyw/>
7. **Third-party review verdict.** "one of the most customizable workspace environments available to retail traders";
   "Modern and well-designed by professional trading platform standards … workspace panels snap together logically";
   weaknesses named as "Windows only, steep learning curve for beginners, and market data subscriptions cost extra"
   ("expect to spend a week or more getting comfortable"). — completetradersedge.com review (8.5/10).
   <https://completetradersedge.com/quantower-review/>
8. **Support via chat when it works.** "Customer support is impressive. I receive a reply as soon as I send a message
   through their Telegram channel." — u/akinon (same comment as #2).

### Complaints (with URLs)
9. **Lag under volatility, scaling with window count.** "sometimes I get a **20-second delay** and have to close and
   relaunch the platform. It gets worse when you load a lot of windows with volume data. I wanted a window split into
   4 with NQ/ES/RTY/YM and their volume profiles, but the software just can't handle that during high volatility." —
   u/Tetra-drachm. <https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/mu4qonw/>
10. **Freezing + resource use, blamed on the feed stack.** "latency / freezing up issues especially with Rithmic
    connections is a major pain … It's also a **resource hog with RAM and cpu**." — u/Kdogg_456.
    <https://www.reddit.com/r/FuturesTrading/comments/1998fkc/sierra_chart_vs_quantower/kjw8egn/>
11. **A failed exit in live conditions.** "I put in a short, got in and **could not close position** … lost out on a
    100 point run and blew a prop account." Same comment flags an interaction defect: "only being able to drag
    windows near top of their edges". — u/Protonverse, r/OrderFlow_Trading.
    <https://www.reddit.com/r/OrderFlow_Trading/comments/1qokf7f/is_quantower_a_buggy_mess_or_is_it_just_me/p5ewmzi/>
12. **"Buggy mess" thread, UI praised in the same breath.** "I've been using this for 3 months **because the UI is
    great**, yet I suffer from delays and weird bugs every day … the order system also broke and I lost around
    $1,000." — u/Curious-Spare-5724.
    <https://www.reddit.com/r/OrderFlow_Trading/comments/1qokf7f/is_quantower_a_buggy_mess_or_is_it_just_me/p31jfzy/>
13. **Memory growth over days.** "increasing usage by QT which I've seen grow from ~2GB at startup to **over 7GB
    after several days**" — u/vaxdatex, whose own fix was OS-level (high-priority flag, core limiting).
    <https://www.reddit.com/r/Quantower/comments/1v1eb7w/ram_usage_on_quantower_using_multiple_charts/oywvcqs/>
    Counterweight from the same thread: a user running two monitors, 3 tabbed charts + DOM + panes + TPO + options
    chain reports "all about 5–8 Gb", and "It's written in c# so when markets get volatile qt lags really bad no
    matter how much ram you have" (u/NoCommunicationPro) vs "I had 64Gb ram … and it still couldn't keep QT running
    smoothly" (u/UrbanRhinoNZ). <https://www.reddit.com/r/Quantower/comments/1v1eb7w/ram_usage_on_quantower_using_multiple_charts/>
14. **Configuration friction and settings sprawl.** "Configuration is difficult. You'll often have to **Google how to
    configure something** … It's currently a list of **100 different graphical features** that you can set the color
    on … They replaced [their Windows-forms dialogs] with their own dialogues that are **countless lists of
    settings**." (He still calls it "an excellent platform to trade with".) — u/masilver.
    <https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/nj4a84h/>
15. **A breaking UI change shipped without a compatibility path.** On 1.146.13's new cluster chart: "changing the UI
    with **no backward compatibility** is a bad idea"; another user: "not all of my settings carried over, as they
    seem to have **reformatted the setup dialogue boxes** … I've had to rebuild some of those indicators." —
    u/vaxdatex, u/dnadeau. <https://www.reddit.com/r/Quantower/comments/1udnvn1/update_to_14613_breaks_cluster_charts/>
16. **HiDPI legibility.** 4K screen, "text looks pretty blurry, especially on light themes". —
    <https://www.reddit.com/r/Quantower/comments/1t9tabg/blurry_text_on_hidpi_screen/>
17. **Density/readability of the footprint at zoom.** Request for bigger footprint numbers and fewer, larger bars. —
    <https://www.reddit.com/r/Quantower/comments/1ns1tfq/footprint_chart_sizing_and_scaling/>
18. **Hotkey coverage gaps, asked for by a fan.** "I'm **loving Quantower**! … I've not found a way to make that exact
    same adjustment via hotkey … I've found the hotkey for Adjust SL/TP and for the life of me I can't figure out what
    it does." <https://www.reddit.com/r/Quantower/comments/1pp8mv8/question_about_hotkeys/>
19. **State that doesn't stick.** "Do you know how to disable the checkbox for 'Trigger OTH'? I've tried deselecting it
    and **saving the layout but it doesn't save**." <https://www.reddit.com/r/Quantower/comments/1v2inb3/trigger_oth_disable/>
20. **Broker-integration trust damage.** A lifetime-licence holder: "my platform has been completely 'bricked' due to
    critical problems in integration of both Alpaca and Tradier's API … **infinite crash loop on startup** … support has
    officially informed me that they have 'no specific timeline' to resolve this." (1ux17r1)
    <https://www.reddit.com/r/Quantower/comments/1ux17r1/stockequityoptions_trading_with_quantower_alpaca/>
21. **API documentation thinness.** "The **documentation is very lacking**. Is there any other good resources besides
    the examples on the github?" <https://www.reddit.com/r/Quantower/comments/1kun1l9/how_to_get_current_timeframe_with_quantower_api/>
22. **Support route disagreements.** One power user refuses chat-based support ("If I have an issue with a product I
    deal directly with the producer … Their Discord server did not to seem to be worth it"), while another user says
    the website chat is good and "usually you get one of the developers replying".
    <https://www.reddit.com/r/Quantower/comments/1v1eb7w/ram_usage_on_quantower_using_multiple_charts/oyxhpw1/>,
    <https://www.reddit.com/r/Quantower/comments/1u6t5xx/unknown_checkbox/ouy3i3j/>
23. **The vendor's own release notes corroborate a UI-polish cadence as well as rough edges** — e.g. "**DOM Trader:
    auto-scroll pauses while you hover the Comments column**" (a hover-vs-autoscroll conflict), "Drawings: locked
    drawing tools can be copied again", "Watchlist: table alerts restore after a restart when using custom-indicator
    columns", "General: application settings restore reliably". ([release notes page](https://help.quantower.com/quantower/updates/latest-version),
    [site release notes](https://www.quantower.com/release-notes))

**Reading of the signal:** the layout/windowing model is what users love and what wins comparisons against
Sierra/NinjaTrader; the recurring damage is **runtime trust** — throughput under volatility, memory over days, and
state/entitlement fragility — plus **settings sprawl** and **small legibility/drag-affordance defects**. Note also one
r/Trading post that reads as promotional/AI-composed ("True Modular Design … Order Flow Native …") — I cite it only as
an example of how the layout story circulates, not as an independent finding.
<https://www.reddit.com/r/Trading/comments/1sbfxxz/anyone_here_actually_using_quantower_for_order/or2j2gk/>

---

## 8. UX patterns worth adopting into a vanilla-JS single-window desktop app

Scored for ModFlow: multiple rail views, terminal mode with OS widget windows, layouts + workspaces, a keyboard
registry + Keys menu, hover/right-click explain cards, per-surface pause/resume, dark + colour-blind palettes, an
onboarding wizard, ~90 help topics. Nothing in the list below is already built in that form; the "why" column names
what it fixes in *our* app.

| # | Pattern (as Quantower does it) | Why it earns its place here | Effort | Risk |
|---|---|---|---|---|
| 1 | **Per-panel "Help" entry in the panel menu that deep-links that panel's own doc topic** ([Single Panel](https://help.quantower.com/quantower/general-settings/standalone-panels)) | We already have ~90 help topics and a hover/explain system; routing the *panel's own* menu to *its* topic turns the corpus into contextual help with zero teaching overhead | **S** | Low — pure mapping table; wrong/stale mapping is visible and cheap to fix |
| 2 | **"Lock layout/workspace" toggle** that blocks add/remove/move/resize until unlocked ([Workspaces](https://help.quantower.com/quantower/general-settings/workspaces-binds-groups)) | Live-trading misclicks on a grid we already persist; one boolean in the layout store + a disabled state in the drag handlers | **S** | Low — must not block the switch back to Classic; keep the lock out of the drag math, not inside it |
| 3 | **Armed state for trading hotkeys** — a visible toggle ("Enable Keyboard Trading") gating only order-placing hotkeys, plus a per-action "confirm hotkey action" ([Chart hotkeys](https://help.quantower.com/quantower/analytics-panels/chart/chart-settings/hotkeys)) | Our keyboard registry is always live; a stray key that submits an order is the worst failure this app can have. Two states, one badge, one setting | **S** | Medium — an armed/disarmed mode can confuse if the badge isn't unmistakable; default OFF and show it in the status bar |
| 4 | **Data-latency threshold with an on-panel badge** — user sets ms, panels say "market data delayed" ([General settings](https://help.quantower.com/quantower/general-settings/general-settings-1)) | We have feed state and 9 feeds incl. bridges; a threshold turns an invisible staleness into a visible one — directly answers the "is this data live?" question users ask of order-flow tools | **S** | Low — needs one honest threshold source per feed; do not fabricate latency when unknown |
| 5 | **Link-group colour on the frame itself** — the panel title takes the group colour, no chip interaction needed ([Link panels](https://help.quantower.com/quantower/general-settings/link-panels)) | We already have A–D link groups + a chip; colouring the title makes group membership readable at a glance and in screenshots | **S** | Low — must stay legible in the colour-blind palettes (pair colour with the existing letter) |
| 6 | **"Set as default" per panel type, replacing factory presets** — with the deletion of "reset to default" taken as a deliberate, documented trade-off ([Set as Default](https://help.quantower.com/quantower/general-settings/set-as-default)) | Our surfaces currently reset to a shipped default; letting a user promote their tuned DOM/Chart/OFX open-state to the default removes per-session re-tuning | **M** | Medium — needs a config-versioned default store and an explicit "reset to factory" escape hatch (Quantower's removal of it is the mistake to not copy) |
| 7 | **Per-surface density switches** — "Slim mode" and "No labels" on the order-entry sidebar ([DOM OE sidebar](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/order-entry)) | Cheap space recovery on a laptop, and it's the exact knob users ask for in dense DOM/tape layouts; CSS-class level change per surface | **S** | Low — two toggles on one panel; keep them in the parameter registry so they persist per surface |
| 8 | **Quick size buttons with arithmetic and formulas** (`;`-separated, signs to add/subtract/reset, multiple rows) ([same page](https://help.quantower.com/quantower/trading-panels/dom-trader/dom-trader-settings/order-entry)) | Our DOM/Strategy surfaces take numeric size; sign- and formula-aware buttons turn a keyboard trip into one click and encode position sizing | **S** | Low — parse in one pure function, refuse silently-bad input loudly |
| 9 | **Instrument lookup with tree + persistent secondary filters + selection count readout** ([Symbols lookup](https://help.quantower.com/quantower/general-settings/instruments-lookup)) | We have an Instruments view and a watchlist; a proper lookup overlay (connection → venue → type tree, filters, "3/235" style counters, Ctrl multi-select) fixes "how do I find X across 9 feeds" | **M** | Medium — must stay keyless and offline-safe; never block on a feed to render the tree |
| 10 | **One table component for every table surface** — column set via right-click header, quick filter by data type, sort, group-by, drag-reorder/resize ([Table management](https://help.quantower.com/quantower/general-settings/table-management)) | We have many table-ish views (Tape, Tape-like watchlist, Journal, Logs, Trackers…). A single documented table behaviour means one set of interactions to learn and one place to fix | **M–L** | Medium — retro-fitting shared behaviour into existing views risks regressions; adopt per new view first, migrate behind a flag |
| 11 | **Notifications as a first-class inbox with categories, priority weights, a global "no disturb", and an act-on-click tile** ([Notifications center](https://help.quantower.com/quantower/general-settings/notifications-center)) | Our alert engine fires to Telegram/ntfy/email/webhook but the *in-app* story is thinner; a category/priority inbox also documents why something fired | **M** | Medium — one more store to persist; Quantower's own design flaw is instructive here (see #12 and §9) |
| 12 | **Update UX that never blocks use** — About swaps to a "NEW VERSION" button; Beta is an opt-in toggle ([Main Toolbar](https://help.quantower.com/quantower/general-settings/main-toolbar)) — **and the anti-pattern to avoid**: a "force update window" that strands the app ([user report](https://www.reddit.com/r/Quantower/comments/1kz5yik/stuck_at_force_update_window/)) | We ship an in-app updater; the rule "the app always starts and always shows data, update is a button" is cheap insurance and the user report is the proof of the failure mode | **S** | Low — mostly a policy, plus a never-blocking error path |

**Deliberately not recommended below rank 12:** Bind-style super-panels with proportional resize and sticky separators,
and the workspace/group/bind triple hierarchy. Both are genuinely good ideas in a multi-window desktop shell, and both
are large, gesture-heavy, high-blast-radius changes in our single-window + grid model — the 1.146.13 episode (§7 #15)
is what a layout change without a compatibility story costs.

---

## 9. Where their model does NOT fit

1. **Plugin/extension ecology.** Quantower's depth comes from a paid, third-party extension layer (vendor extensions
   à la carte *plus* "Third-party extensions produced and supported by the standalone development teams") on top of a
   C# API with Visual Studio/VS Code/Atom tooling ([pricing](https://www.quantower.com/pricing),
   [Quantower Algo](https://help.quantower.com/quantower/quantower-algo/introduction)); users even trade in
   marketplace listings for indicators. A single-developer, keyless-first app cannot staff, vet, or support that.
   Our analogue is the studies/expression API — keep it in-repo, versioned with the app, and never a load-bearing
   surface for third-party DLLs we don't ship.
2. **Entitlement servers and per-feature gating.** Their free edition is limited by counting (1 connection, 2
   indicators, 1 overlay) and upgraded by a licence tied to an account ([Licenses](https://help.quantower.com/quantower/getting-started/account-and-licensing/quantower-licenses)).
   That is a network dependency in the *core* of the app. The failure mode is documented by their users: an
   integration bug left a lifetime licence holder's install "completely bricked" and unusable **even for charting**
   ([1ux17r1](https://www.reddit.com/r/Quantower/comments/1ux17r1/stockequityoptions_trading_with_quantower_alpaca/)).
   Our rule — keyless-first, local-first, the app works with the network unplugged — is worth more than any tiering.
3. **Staffed live support as a designed feature.** "Live Support" is a bindable panel plugged into a human queue plus a
   website chat ([Live Support](https://help.quantower.com/quantower/miscellaneous-panels/live-support)). One
   developer cannot promise a queue; the honest equivalent is logs + a diagnostics bundle + the help corpus + a
   "copy panel state" action, and saying plainly that it's self-service.
4. **Vendor demo feeds as the onboarding hook.** Their first-run answer is a *connection* (dxFeed Simulated,
   24-hour-delayed, limited symbols) plus a paid data subscription path ([Installation](https://help.quantower.com/quantower/getting-started/installation)).
   We must onboard with **sample/local data and replay**, never a vendor feed, and never a screen that implies real
   market data is flowing when it isn't.
5. **A force/auto-update discipline that outruns the docs.** The help centre headlines a Beta from June 2026 while the
   website lists 1.147.3 in September ([help](https://help.quantower.com/quantower/updates/latest-version) vs
   [site](https://www.quantower.com/release-notes)); the 1.146.13 cluster-chart change broke user settings with no
   compatibility path ([thread](https://www.reddit.com/r/Quantower/comments/1udnvn1/update_to_14613_breaks_cluster_charts/)).
   With one developer, the release note *is* the contract: version the layout/parameter schema, migrate on read, and
   keep the previous build runnable.
6. **Chat-history volatility.** Notifications vanish on restart and the sidebar is the only path to the list
   ("accessing the complete list of notifications becomes impossible" if the icon is hidden)
   ([Notifications center](https://help.quantower.com/quantower/general-settings/notifications-center)). We persist to
   SQLite and should keep an exportable history — copying their inbox *pattern* must not copy this amnesia.
7. **Three-layer layout hierarchy.** Workspaces → Binds → Groups → panels is powerful for a multi-monitor audience and
   unnecessary for a single-window app with tabs and layouts already. Adopting it would add gestures (rectangle-select,
   proportional resize, sticky separators) whose edge cases we would be fixing for months.
8. **Free-form OS-window geometry as truth.** Their panels' positions are free pixels with snapping, and the known
   complaints are exactly the geometry ones ("only being able to drag windows near top of their edges"; HiDPI blur;
   footprint legibility). Our grid + terminal-mode widget windows are a smaller space with fewer failure modes; keep
   the grid as the source of truth and treat OS geometry as a view of it.

---

## Sources

Vendor docs (all `help.quantower.com/quantower/…`; every page read 18 Sep 2026, `.md` twins):
`getting-started/installation` · `getting-started/first-start` · `getting-started/account-and-licensing/quantower-licenses` ·
`…/license-comparison` · `general-settings/main-toolbar` · `…/workspaces-binds-groups` · `…/standalone-panels` ·
`…/link-panels` · `…/binds` · `…/group-of-panels` · `…/templates` · `…/set-as-default` · `…/instruments-lookup` ·
`…/table-management` · `…/general-settings-1` · `…/custom-hotkeys` · `…/notifications-center` ·
`analytics-panels/chart/general-overview` · `…/chart-settings/view-settings` · `…/chart-settings/hotkeys` ·
`…/chart-settings/info-window` · `…/chart-settings/quick-ruler` · `analytics-panels/chart/drawing-tools` ·
`analytics-panels/dom-surface` · `analytics-panels/watchlist` · `trading-panels/dom-trader` ·
`…/dom-trader/dom-trader-settings/{view-settings,order-entry,hotkeys}` · `…/dom-trader/dom-trader-columns` ·
`…/dom-trader/how-to-set-up-dom-for-scalping` · `trading-panels/market-depth` · `trading-panels/order-entry` ·
`trading-panels/order-entry/order-types` · `trading-panels/chart-trading` · `trading-panels/market-replay` ·
`trading-panels/trading-simulator` · `trading-panels/multiple-order-entry` · `portfolio-panels/positions` ·
`miscellaneous-panels/themes-editor` · `miscellaneous-panels/live-support` · `miscellaneous-panels/browser` ·
`customization/localization` · `updates/latest-version` · `quantower-algo/introduction` · `llms.txt` (245-page index).

Vendor site: <https://www.quantower.com/pricing> · <https://www.quantower.com/release-notes>.

Third-party: <https://completetradersedge.com/quantower-review/> (8.5/10 review, read 18 Sep 2026).

User discussion (Reddit, retrieved 18 Sep 2026 via thread RSS + pullpush.io):
r/FuturesTrading [`1kumjrd`](https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/),
[`1998fkc`](https://www.reddit.com/r/FuturesTrading/comments/1998fkc/sierra_chart_vs_quantower/),
[`194u66e`](https://www.reddit.com/r/FuturesTrading/comments/194u66e/quantower_vs_ninjatrader/),
[`1rmcjfq`](https://www.reddit.com/r/FuturesTrading/comments/1rmcjfq/sierra_charts_vs_quantower/);
r/OrderFlow_Trading [`1qokf7f`](https://www.reddit.com/r/OrderFlow_Trading/comments/1qokf7f/is_quantower_a_buggy_mess_or_is_it_just_me/),
[`1oc9wea`](https://www.reddit.com/r/OrderFlow_Trading/comments/1oc9wea/free_amp_quantower_too_good_to_be_true/);
r/algotrading [`12wogaq`](https://www.reddit.com/r/algotrading/comments/12wogaq/anyone_using_quantower_id_like_your_thoughts/);
r/Quantower [`1t9tabg`](https://www.reddit.com/r/Quantower/comments/1t9tabg/blurry_text_on_hidpi_screen/),
[`1sz94zk`](https://www.reddit.com/r/Quantower/comments/1sz94zk/desktop_freeze_when_vola_spikes/),
[`1v1eb7w`](https://www.reddit.com/r/Quantower/comments/1v1eb7w/ram_usage_on_quantower_using_multiple_charts/),
[`1udnvn1`](https://www.reddit.com/r/Quantower/comments/1udnvn1/update_to_14613_breaks_cluster_charts/),
[`1ux17r1`](https://www.reddit.com/r/Quantower/comments/1ux17r1/stockequityoptions_trading_with_quantower_alpaca/),
[`1pp8mv8`](https://www.reddit.com/r/Quantower/comments/1pp8mv8/question_about_hotkeys/),
[`1ns1tfq`](https://www.reddit.com/r/Quantower/comments/1ns1tfq/footprint_chart_sizing_and_scaling/),
[`1kun1l9`](https://www.reddit.com/r/Quantower/comments/1kun1l9/how_to_get_current_timeframe_with_quantower_api/),
[`1v2inb3`](https://www.reddit.com/r/Quantower/comments/1v2inb3/trigger_oth_disable/),
[`1kz5yik`](https://www.reddit.com/r/Quantower/comments/1kz5yik/stuck_at_force_update_window/);
r/Trading [`1sbfxxz`](https://www.reddit.com/r/Trading/comments/1sbfxxz/anyone_here_actually_using_quantower_for_order/) (flagged as promotional).

**Explicitly not read / not verified:** the number of link colours; any count of default hotkeys; whether a
colour-blind mode exists beyond the Grayscale theme; the currency of the pricing figures (page serves amounts without
a symbol; sibling `data-profit` values are `$`-prefixed); the deep contents of the C# API docs at `api.quantower.com`;
the platform-update page (only its `llms.txt` description was read); the r/Quantower wiki and their Discord/Telegram
channels (not crawlable here).
