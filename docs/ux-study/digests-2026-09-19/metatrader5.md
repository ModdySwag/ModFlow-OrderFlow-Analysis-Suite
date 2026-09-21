# MetaTrader 5 — digest for the 2026-09-19 reanalysis

Source: `docs/ux-study/metatrader5.md` (compiled 2026-09-18); all claims are in that brief; items it flags unread are tagged [unverified].

## 1. At a glance
- Native desktop terminal: multi-asset, hedging+netting, 2 market / 6 pending / 2 stop orders, Trailing Stop, 38 indicators, 44 analytical objects, MQL5 + MetaEditor IDE; Blend2D rendering for crisp HiDPI/4K lines.
- **Money/distribution = the positioning**: free to traders; the buyer is the broker/service side. Broker licences tier by account capacity (Entry 1,000 / Standard 25,000 / Enterprise 200,000); fees unpublished; the "$2,000.00 per month" listing is a GDM catalogue estimate, **not MetaQuotes**. In-platform paid: Market (buy *or rent* robots/indicators), Signals (subscriptions), Virtual hosting (in-terminal VPS).
- **Vendor admission of UI debt**: Build 5800 (16 Apr 2026) — "We have started a comprehensive redesign of the trading dialog to make it more intuitive and functional."
- Broker-configured UI (brokers can disable whole sections "to optimize resources and terminal workspace"); account-anchored, order-routing by design; volume "has now eclipsed MT4 (as of April 2025)". Trustpilot 1.4/5 (206) — a complaints channel.

## 2. Layout & persistence
- Main menu "contains almost all commands"; three toolbars duplicate it. Market Watch left (tabbed; configurable columns+fonts). Navigator: accounts + tree of robots/indicators/scripts, Market purchases, Code Base downloads, VPS rental.
- Chart area: chart switch bar; up to 100 charts. Toolbox bottom (one window): positions, news, history, alerts, logs, journals. Status bar: connection, price data, **active template and profile name**.
- Windowing: per-chart `Docked` toggle; undocked charts detach to another monitor; service windows undock too — MetaQuotes later patched them being lost off-screen ("cannot be dragged beyond terminal borders").
- Profiles vs templates: templates = chart appearance/objects; profiles = the open-chart set; `Ctrl+F5`/`Shift+F5` cycle; names always visible in the status bar [unverified persistence failures reported].

## 3. Interaction grammar
- Hotkeys: assignable to any Navigator element except Accounts; **user keys silently outrank defaults** (assign an indicator to `Ctrl+O` and it "will not call the platform setup window any more"). Also `F9` order window, `Ctrl+Z` undo object deletion, `Backspace` deletes the newest object.
- Order entry: `F9` dialog; One-Click Trading panel on chart / Market Watch / DOM; unavailable under "Request" execution. Zero-confirm acts: close position / delete pending / delete SL-TP "without additional confirmation" — "power is bought with irreversibility"; undo exists for **chart objects only**.
- Drag & direct manipulation: symbol→chart plain drag **closes the currently open charts**; `Ctrl`+drag is additive but undiscoverable. Dragging a trade level sets SL/TP with a tooltip of "potential profit (or loss) in the deposit currency and pips".
- Position-aware menus: above the current price "a user can place Sell Limit and Buy Stop orders", below it "Buy Limit and Sell Stop" — stop-level distance validated before the command appears.
- Tips system: "over 100 interactive tips" on a toolbar progress bar; **"Tips only appear for the actions which you have never performed in the platform"**; each tip links to the target UI.
- Build 5800: trading dialog gained a built-in Depth of Market; order-type switching moved to a **side panel** also hosting one-click on/off controls previously only in settings.

## 4. GUI & visual system
- Dense compound app (tight table/tree/tab widgets, small fixed text); density tunable **per panel** but **not globally**.
- **No font scaling — the most-cited visual failure**: "You cannot change basic things like the font size, so you can only guess at the market price on the coordinates…why?"; "The charts… look like they were drawn by hand."
- **HiDPI: a decade of patches** — "Fixed UI display errors on HiDPI displays" (b.2715); "All icons… updated to support HiDPI monitors" (b.2615); users still report text "too small" to read. Canvas datum: custom in-chart panels don't scale — text "overlapping or getting cut off… tried implementing DPI awareness… it didn't fix the issue."
- Theming: chart schemes per-template; a global dark theme came late and is still patched. 40+ localisations.

## 5. Standout features / advantages
1. **Direct manipulation of risk** — "modifying TP and SL by simply dragging and dropping".
2. **Multi-chart monitoring without extra hardware** — "multiple charts of different pairs all at once" (up to 100 charts).
3. **Strategy Tester** — visual testing of EAs *and* indicators; Market demos testable before purchase.
4. **Signals / Market / Virtual hosting** — fixed-price copy trading; buy *or rent* robots; a VPS keeps robots/alerts alive when the desktop closes.
5. **Free at point of use, wide broker choice** ("Advanced tools to use and absolutely free!").

## 6. Documented pain points (with quirk/failure mode)
- Hard to locate tools: "difficult to locate some of the tools that are critical to trading" (Software Advice, Sept 2023); "can't be used by beginners."
- "I spent half an hour just trying to figure out how to see the chart. Don't get me started on trying to change any settings…" (2★).
- "The trade management system is old-fashioned and lacks the intuitive flow found in modern platforms". (1★, Mar 2026)
- Desktop neglect: "The app is terrible on computer. Slow, buggy, always updating…"; a freeze blocks the protective step — "the app freeze and I can't put SL and TP".
- Provenance never shown: "Gaps in data/chart - sometimes hours… missing candles…"; "not confident that the data… is up to date" — the broker feed is usually to blame, but MT5 wears it.
- "A feature that exists but isn't found is, for the user, absent."

## 7. Market norms this platform establishes
Experienced users of this niche therefore expect:
1. The tool free at point of use; monetisation behind it.
2. A provider-configured shell — symbol universe and sections are switches the user never owns.
3. Direct manipulation of risk levels, with live P/L while dragging.
4. Position-aware menus offering only legal actions where you clicked, pre-validated.
5. Zero-confirmation closes/deletes; undo only for chart objects.
6. Profiles (open-chart set) vs templates (chart appearance), hotkey-cycleable, names always visible.
7. Detachable windows with placement remembered; up to 100 charts, switch bar, jump-to-symbol.
8. Global search over products/forum/docs with grouped results.
9. Tips gated on never-performed actions, that are themselves launchers.
10. Always-on automation surviving desktop close (or a rented VPS); desktop/web/mobile parity; forum support at the free tier.

## 8. Transferable upgrade ideas (ranked; evidence named)
1. **Global UI scale via CSS custom properties** (`--ui-scale`, rem panels) — evidence: no in-app font-size control is MT5's most-cited visual failure.
2. **Canvas DPI correctness on resize/monitor move** (`devicePixelRatio` + `ResizeObserver`) — evidence: MQL5 490513 EA-panel scaling ("overlapping or getting cut off"; DPI-awareness attempt failed).
3. **Position-aware context menus** — evidence: above/below-price pending-order menu with stop-level pre-validation.
4. **Consequence-preview drag tooltips** — evidence: live P/L "in the deposit currency and pips" during SL/TP and pending drags.
5. **Modifier-key drag semantics, hinted in-surface** — evidence: MT5 symbol drag closes charts; `Ctrl`+drag additive but undiscoverable.
6. **One "no-confirm" class + undo instead of dialogs** — evidence: MT5 zero-confirm deletes vs `Ctrl+Z`-undoable chart objects.
7. **Per-symbol data-provenance chip** (source, last-tick age, backfill, gaps) — evidence: "missing candles" / "not confident that the data… is up to date"; elevated because ModFlow ingests MT5 read-only.
8. **Named layout profiles + cycle hotkeys + always-visible name** — evidence: `Ctrl+F5`/`Shift+F5`, template+profile in the status bar.
9. **Side-panel-as-mode** — evidence: Build 5800 side rail for order-type switching + one-click toggles.
10. **Novelty-gated progressive tips that are launchers** — evidence: tips fire only for un-performed actions; links open the target UI.
Also: global search; detach-to-OS-window recovery; per-panel settings.

## 9. Key sources
metatrader5.com/en/terminal/help/ (interface, hotkeys, one_click_trading, market_watch, charts, charts_manage); /en/releasenotes/terminal/ (+2436, page4); /en/brokers/buy. trustpilot.com/review/metatrader5.com; softwareadvice.com/hedge-fund/metatrader-5-profile/; capterra.com/p/230413/MetaTrader-5/reviews/; mql5.com/en/forum/490513, /414447/page2, /154437.

**Unverified**: MetaQuotes licence prices/fees; the $2,000/month estimate; Navigator→chart drag as documented; Reddit bodies (login wall); the Market Watch scaling-persistence sentence; mobile UX beyond quotes.
