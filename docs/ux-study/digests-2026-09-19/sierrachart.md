# Sierra Chart — digest for the 2026-09-19 reanalysis
*Sole source: `OrderFlow-Analysis-Pro/docs/ux-study/sierrachart.md` (2026-09-18); Reddit quotes are snippet-only.*

## 1. The program at a glance
- Native **Windows desktop** (single EXE + DLLs, OpenGL, DPI-aware fonts); build "Sierra Chart 2950 (September 13, 2026)"; "in business since 1996". Sells data and order routing; the software is not sold separately.
- **Pricing 2026 — monthly packages only, no perpetual:** Base 26 / +Advanced 36 / Integrated 36 / Integrated+Advanced 46 / +MBO 56 USD/mo. Base tiers "do not support connections to external provided Data or Trading services"; a one-time purchase is "no… never offered".
- **Positioning:** power/speed/configurability over looks — engineering on a GUI-overhaul request: UIs "are in decline… a race to the bottom… Except Sierra Chart." Board index "[Page 1 of 2565]" threads.

## 2. Layout & persistence model
- **The Chartbook, not the window, is the abstraction** — "not a window… a collection of multiple windows" / "like a desktop/layout/workspace". **Only 1 chartbook visible per instance**; more needs extra instances (`File >> New Instance`). Chartbooks **cannot be detached**; fallback = stretch across monitors.
- Detach per window; **re-attach needs the detached window's own menu**. `Window >> Window Always Visible` pins a chart across chartbooks (docs warn not to overuse); chartbook tabs opt-in.
- **The Window menu is the window manager (MDI-style):** Cascade, Tile H/V/Grid, Always on Top, Window Always Visible, Detach/Attach, Hide Window, Hide/Restore All Trade Windows, Previous/Next Chart, Message Log.
- **Failure modes:** missing windows recover only via the CW menu → `Cascade` → `Maximize` (FAQ "Help topic 14: Window Size and Position Not Restored…"); "Make sure the windows have a title bar. Do not remove the title bars."
- **Board:** a title-bar-less window on monitor 2 "took a lot of steps to restore… and move it to my primary monitor"; "I tried to reattach it for 10mins now. Its simply impossible".

## 3. Interaction grammar
- **Menus are the API:** every menu line shows its shortcut; menus are user-editable (`Customize Menu Items`, per-chart shortcut/trade/drawing menus) — a chart's right-click menu holds **only what the user added**. **F1 is reserved for OS-level context help**; in-product citations are numbers ("Help topic 14").
- **Keyboard is global, not per-window**; any command rebindable (`Global Settings >> Customize Keyboard Shortcuts`); trading shortcuts gated by `Trade >> Trading Keyboard Shortcuts Enabled`; settings windows are keyboard-driven (Ctrl-Enter edit, Enter, Esc).
- **Chart:** right-click order entry; drag an order line to reprice (drag-back before release = no change); right-click the price scale → Interactive Scale Range/Move — also how an off-screen order is recovered.
- **Settings panels (most transferable):** **modeless** — "you can interact with other areas… This is a major advantage" — replacing OS dialogs "unreliable, very inefficient, and operating system resource heavy". Per-field **A** (accept = Enter, *not* Apply) / **C** (revert field); window-level **OK / Cancel** (revert+close) / **Revert All** (stay open) / **Apply All** (accept, stay open); **`View >> Show Original Values`** = diff of pre-change values. In-panel search is tokenised ("Mas Mod" → "Master Mode") or approximate ("alw zr vl" → "Allow Zero Values"); a hit switches tab and highlights.

## 4. GUI & visual system
- **Density is the design:** chart + scales + study values; per-chart tab colours; per-study subgraph colours; a **hundreds-of-items colour table** (>100 Graphics entries; ~180 `Chart DOM …` + ~210 `Trade DOM …`) with **threshold tiers** (quantity high-threshold, repeat-trade, pulling/stacking).
- Fonts are **per scope** (incl. `Settings Windows`), DPI-aware. **Two scopes:** per-chart `Use Global Graphics Settings Instead of These Settings` + Copy to/from Global; editing global does nothing for an "own settings" chart; saved configs (slots 1-20) store **colours only**. Theming is per-object, not per-theme.

## 5. Standout technical features
- **Study Collections** — "Save Studies as Study Collection" (+ "Prompt to Remove Existing Studies"): configs travel between charts. **Instance identity** — "the same study can be added more than once"; unique unchangeable ID; inputs on a **Settings and Inputs** tab, visuals on a **Subgraphs** tab.
- **Spreadsheet studies** — formula grid (functions, cross-chart refs, sharing); spreadsheet windows are chartbook members. *(Bodies not read.)*
- **Native DLL custom studies** (Data Files Folder). **Trade DOM** — user-defined columns/order, per-tick ladder scaling, double-click order entry, studies/text on the DOM, P&L format cycles on header click.
- **Feed depth** — server-side market-data infrastructure is part of the product; users cite DOM/footprint/volume-profile depth, low lag, 300+ studies. AMP 4.80/543; Trustpilot 3.7/25 unclaimed.

## 6. Documented user pain points
1. **Dated UI** — "wall after walls"; "It's UI is ugly"; a review headline: "Old Design".
2. **Settings overwhelm and no global search** — "settings are just overwhelming"; "no search functionality for indicators or settings" (settings now search; studies don't).
3. **Window traps** — hidden/title-bar-less windows, chartbook-vs-instance rules, the 10-minute reattach.
4. **Support tone/gating** — "snarky questions and send me links with tons of sublinks"; email delayed 2 days or ignored; veterans confuse "Sierra Chart Exchange Feed" vs "Denali Exchange Feed".
5. **Scope confusion (the archetypal thread)** — tiny axis text unfixable because the user "didn't realise there are 2 types of graphic settings".
6. **Update regressions** — "Type Text tool font size changed on update to 2789"; a DOM size input that "doesn't change the font size".
7. **Learning curve** — the most repeated fact ("VERY STEEP… but worth it").

## 7. Market norms this platform establishes
1. Configuration in **modeless, searchable panels** that never block the chart.
2. **Per-field accept/cancel, panel-level Apply All / Revert All**, and a what-changed diff.
3. Commands **menu-discoverable, rebindable, shortcut-labelled**; live actions have an arm/disarm switch.
4. **Explicit labelled scopes** (this surface vs global) and copy between them.
5. **Whole-workspace persistence** reopening as left, as a **portable file** users share.
6. **Analysis units as instances, not types** — the same study twice, tuned independently.
7. **Saved named configurations** rebuild a setup by loading a file.
8. **Dense, ugly-but-fast UI** is defended over beauty.
9. **Numbered, citable docs**; errors name a doc topic; F1 = context help.
10. **Detachable windows, an always-visible pin, a recovery path for any window.**
11. **Feed/data depth is first-class**; similarly-named feed tiers confuse.
12. **Self-serve answers from a permanent searchable archive**, not 1:1 support.

## 8. Transferable upgrade ideas for an analytics-layer tool (ranked)
1. **Modeless settings panels + per-field A/C + Apply All/Revert All + original-values diff.** *evidence:* [S4].
2. **Tokenised in-panel search** ("Mas Mod" → "Master Mode"), tab-switch on select. *evidence:* [S4]; answers [S24].
3. **Explicit scope switch + Copy to/from Global + an "own settings" badge.** *evidence:* [S10]; two-scope thread [S31].
4. **Window recovery kit: master list, clamp-to-primary-monitor, always-visible pin, never a title-less window.** *evidence:* [S2][S9][S19][S20][S21].
5. **Error states naming a numbered help topic, clickable; stable topic IDs in logs; F1 help.** *evidence:* [S13][S9][S5].
6. **Shortcut legend rendered from the registry + an arm/disarm switch for live-data actions.** *evidence:* [S5][S6][S7].
7. **Instance IDs for studies: per-instance inputs, independent duplicates, visuals on a separate tab.** *evidence:* [S8].
8. **Portable versioned JSON workspace+study export/import with "prompt to remove existing".** *evidence:* [S3][S7][S8][S15].
9. **Right-click the scale → Interactive Range/Move + Reset Scales; contrast tiers over per-object colour tables.** *evidence:* [S7][S7b]; [S10][S22][S31].

**Do not copy:** right-click menus as the *only* command route [S20]; title-bar-less windows by default; no global study search [S24]; hundreds-entry colour tables [S10][S22].

## 9. Key sources
https://www.sierrachart.com/index.php?page=doc/SettingsWindowsInterface.php · https://www.sierrachart.com/index.php?page=doc/GraphicsSettings.html
https://www.sierrachart.com/index.php?page=doc/Chartbooks.html · https://www.sierrachart.com/index.php?page=doc/ChartStudies.html
https://www.sierrachart.com/index.php?page=doc/ChartTrading.html · https://www.sierrachart.com/index.php?page=doc/WindowMenu.html
Thread 90655 (reattach dead end): https://www.sierrachart.com/SupportBoard.php?ThreadID=90655
Thread 24882 (settings scopes): https://www.sierrachart.com/SupportBoard.php?ThreadID=24882
