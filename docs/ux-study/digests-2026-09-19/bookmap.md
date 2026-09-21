# Bookmap - digest for the 2026-09-19 reanalysis

Brief: full `bookmap.md` read (62.5 KB, compiled 2026-09-18 from Bookmap KB/pricing/release notes/reviews/forums). Reddit bodies not read (403); Discord/forum not read. Uncertainty marked.

## 1. At a glance
- "the market depth visualization, and high-speed trading platform" (vendor).
- Java desktop, OpenGL (UI D3D/OpenGL switch), default 40 FPS - "below 15 FPS will be visibly less smooth"; Win/mac/Linux "limited"; no mobile.
- Tiers (cross-checked once): Digital free | Digital+ $19/mo, $16/mo | Global $49/mo, $39/mo, $990 lifetime | Global+ $99/mo, $79/mo, $1990 lifetime ("Recommended"); symbols capped 1/3/10/20; some indicators "Replay mode only".
- Data billed separately: BookmapData $34-79/mo; dxFeed futures $37/mo/exchange, equities $34-119/mo; Rithmic $40-101/mo; crypto free. Add-ons: in-app Manager, `.jar`; vendor split 73%/88%.
- Min 1280x960/8 GB/i5; middle mouse for one-click add-on; heavy MBO 32 GB/i9 8+; "~8GiB free RAM"; one machine at a time.

## 2. Layout & persistence
- One window; instruments as tabs; heatmap as spine. Detach via drag&drop/double-click/right-click; closing returns the tab to the strip; no dock manager documented.
- Canvas: heatmap + dots + bars + BBO + last price, toggled from "visible components menu".
- Rails: right "Columns" (COB, CVP/SVP, CTC/STC, CQC, quote delta, T&S, DOM, Notes; right-click insert/hide); Indicator + Widget Panels; bottom Information Bar mirrors tooltip; session cluster + Data Ingest Indicator ("will first delay any recenterings" on backlog).
- `.bmw` workspaces store full layout + configuration (heatmap settings, chart components, add-ons, instruments); double-click launch; share by link; auto-launches most recent.
- Multi-monitor documented mostly via bugs ("The UI disappears when moving the window from one monitor to another") + "full support for high DPI"; master-slave chart sync (subordinate edits disrupt sync); multi-instrument crosshair; detached T&S "returned... by closing".

## 3. Interaction grammar
- Zoom: wheel over heatmap or price axis; axis-drag; "Zoom by Drag"; Ctrl+Z back out.
- Cursor-anchored: wheel "will keep the chart centered on the cursor location"; buttons anchor to chart middle.
- Drag mode: hold D (M toggles); arrows 1 px, Shift+arrows 10 px; scroll-back "1 hour or 24 hours" by tier.
- Re-centre on BBO/Trades/Last Price/"None"; "Recenter in Drag Mode"; % or absolute tolerances.
- Anti-flicker: BBO auto-hide, hysteresis `Reappear = Hide x (1+Factor)`; vertical smoothing Auto/Manual/None.
- Tooltip (bid/ask, amount+price, traded volume) mirrored in Information Bar; dot hover -> volume; cursor-on-dot -> VWAP; hover time+price -> pending orders.
- Volume dots: clustering (Smart/time/volume/price/price+aggressor), Gradient/Solid/Pie, 2D/3D, total vs delta, min size, bar width 1-15 px.
- Events list: drag range -> table (timestamp/instrument/source/side/price/size) + filters; hover-first numeric disclosure throughout.
- Hotkeys: CTRL+S screenshot | SPACE pause/resume replay | `.`/`,` speed | arrows 1/10 px | M drag | hold D drag | right-click empty toolbar -> find main window | CTRL+T subscribe | CTRL+W unsubscribe | CTRL+TAB / CTRL+SHIFT+TAB | cancel-all; one editable table.
- Trading/execution surfaces exist (context only).

## 4. GUI & visual system
- Ramp "black through blue, yellow, orange, and red"; "the redder the colour, the higher the liquidity"; legacy greyscale opt-in.
- Cut-offs: percentile ("if 95% is selected... white assigned to the top 5% order sizes") or exact contract count.
- Auto contrast scales to book max/distribution, re-adjustable ("every time the chart recentres"); manual brightness/contrast.
- Dimming darkens the heatmap "to the point where all price lines become black". Large Size Highlight slider - greyscale-only.
- "Apply color scheme globally"; otherwise per-instrument, "most recent... future instruments".
- Aggressor two-colour gradient, stronger colour = more aggressive; bid green / ask red defaults.
- Estimated depth labelled: out-of-range levels "it is only an estimation"; range lines mark extended vs active.
- Theming: colour profiles Save as/Import/Restore; per-column/element/global resets. Typography/accessibility **not read** (font zoom only) - "custom-colour-driven, not palette-driven"; GPU-accel disable for distorted charts.

## 5. Standout advantages
1. Heatmap-first depth at 40 FPS + nanosecond updates - "industry leader for the best heatmap".
2. Replay + simulator: 3 run modes; record sessions, speed control, "Skip To Next Data Point"; orders replay too.
3. Master-slave cross-chart sync + multi-instrument crosshair.
4. ~3 dozen add-ons (CVD, Footprint, Market Profile, DOM Pro, Tradermap...) + API + "Vibe Coding" guide.
5. Data coupling: "Stops & Icebergs... requires MBO data from Rithmic"; Execution Pro live "only Rithmic and CQG".
6. `.bmw` share-by-link + education surface.

## 6. Documented pain points
1. Steep curve/overload - most-repeated; "like handing someone a cockpit"; forum "info overload..."
2. Resource heaviness: 32 GB/i9 heavy spec, ~8GiB, CPU climbs with detached charts / high-res / high FPS / deep zoom; "Hardware-Intensive".
3. 40 FPS ceiling used competitively: Reddit "ATAS at 600 FPS vs Bookmap at 40 FPS > Heatmap Showdown" (snippet).
4. Cost stacking: 1-star "marks [Nasdaq TotalView] up to $300 a month" (user arithmetic; separate billing vendor-verified); "best features... only at the highest tier".
5. Look-and-feel minority: "outdated software from the early 2000s... the interface hurts the eyes"; no smartphone app.
6. Setup friction + artefacts: "...a lot of false orders on the heat[map]" (snippet).
7. Time-to-competence: "2-3 months to really lock in" (snippet).
8. Community advice: "Disable everything except the heatmap and volume dots. That's it." (forum AI account).
9. Trustpilot 4.4/5 (603 reviews; 5-star 78%, 1-star 8%); "scalpers paradise... does not work well with ETFs".

## 7. Market norms (test against ModFlow)
1. Heatmap is the primary canvas; the rest are rails/panels.
2. Wheel zoom anchors to the cursor; axis-drag zoom; Ctrl+Z back out.
3. Held key = drag mode (hold D / M) + 1/10 px arrow nudge.
4. Ramp tunable: percentile or absolute cut-offs, auto-contrast, dimming, global apply.
5. Colliding overlays anti-flicker via hysteresis.
6. Hover-to-number everywhere, mirrored in a persistent info bar.
7. Workspace file captures layout+settings+instruments; auto-restores; detached windows return home on close.
8. Replay (data and orders) is the practice loop.
9. Estimated depth labelled as estimation - provenance on canvas.
10. Shortcuts one editable table; per-instrument settings, "last applied wins".
11. Density on by default, all toggleable.
12. Right-side per-price rail expected (book, session vs chart-range profile, counters, quote delta, DOM).
13. Free tier exists; deep history entitlement-gated (1 h vs 24 h scroll-back).

## 8. Transferable upgrades (ranked)
1. Percentile + absolute ramp cut-offs, global-apply broadcast - evidence: KB Heatmap settings (top-5% slider; contract count; "Apply color scheme globally").
2. Anti-flicker hysteresis + tolerance sliders - evidence: KB Main Chart `Reappear = Hide x (1+Factor)`; KB Supporting Features tolerances.
3. Cursor-anchored zoom + hold-D drag + arrow nudge - evidence: KB Supporting Features; KB Hotkeys.
4. Synthetic/stale/estimated data labelling - evidence: KB Heatmap settings ("only an estimation"; range lines). Highest-integrity pattern in the study.
5. One-click minimal/focus mode per surface - evidence: community strip-down (§6.8), overload (§6.1).
6. Dimming + large-size highlight - evidence: KB Heatmap settings.
7. Columns rail with per-column reset modes (Manual/Scheduled/Conditional/double-click) - evidence: KB Columns.
8. Workspace file contract + auto-restore - evidence: KB Export/Import; KB Open The Main Window.
9. Range-to-table events list - evidence: KB Supporting Features.
10. Status/telemetry cluster with backlog semantics - evidence: KB Information Bar.
Anti-patterns to skip: scattered settings, detached-window fragility, entitlement-gated time-travel, density-by-default.

## 9. Key sources
1. https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapSettings
2. https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapSupportingFeatures
3. https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapMainChart
4. https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-Columns
5. https://bookmap.com/knowledgebase/docs/KB-Appendices-AI-KeyboardHotkeys
6. https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-ExportImportBookmapFiles
7. https://bookmap.com/knowledgebase/docs/KB-IntroductionToBookmap-SystemRequirements
8. https://bookmap.com/pricing/
9. https://www.trustpilot.com/review/bookmap.com
Also: KB Release Notes, KB Traded Volume Visualization; DayTrading.com, WallStreetZen, Bullish Bears, JAW Trades.
