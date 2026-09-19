<!-- Reading notes for docs/FLOWSURFACE_FOLD_IN_PLAN.md. Source: github.com/flowsurface-rs/flowsurface
     @ c1388d4 (2026-09-16), cloned read-only. GPL-3.0: these notes describe behaviour only —
     no flowsurface code appears here and none may be copied into this repo. -->

# flowsurface `src/` — panes, linking, tickers table, ladder, tape, heatmap renderer, comparison, indicators, audio

# flowsurface `src/` UI-layer briefing — ideas for porting into ModFlow OrderFlow Analysis Suite

Source read: `C:\Users\<you>\AppData\Local\Temp\flowsurface_ref` (Rust iced 0.14 + wgpu, GPL-3.0-or-later, v0.8.9, ~39k LOC in `src/`).
**Ideas only — no code copying.** Every claim below is `file:line`-anchored so the target work can re-derive the idea without lifting GPL text.

Target: `C:\Users\<you>\OrderFlow-Analysis-Pro` — FastAPI + pywebview (WebView2), vanilla JS/canvas, no build step, ~69 Python test modules + `*.selftest.js` JS self-tests, 11-view shell, terminal mode, aux windows, per-screen layout persistence.

---

## 0. Architecture at a glance (what the target has no equivalent of)

- `src/main.rs` is an iced **daemon** with multi-window support: `window::open`, `window::collect_window_specs`, per-window `Dashboard::view_window` (main.rs:126-200, 647-780). Main window + N *popout* windows, all sharing one layout.
- `LayoutManager` holds N named layouts, each a full `Dashboard` (panes + popouts); inactive layouts are *parked* (their popouts closed) rather than destroyed (modal/layout_manager.rs:41-62, 125-137).
- Global message union covers: WS events (`exchange::Event::{Depth,Trades,Kline}Received`), a per-frame `Tick`, window events, sidebar/theme/network/audio modal messages (main.rs:88-121).
- Per-frame `Tick` drives all panel invalidation (`main.rs:236-252` → `dashboard.tick` at screen/dashboard.rs:1196).
- Panes are `pane_grid` tiles: `min_size(240)`, 6px spacing, 8px resize handles, drag-to-swap, click-to-focus (screen/dashboard.rs:630-644).

---

## 1. Pane linking (the feature the target lacks)

**Data model.** Each pane carries `link_group: Option<LinkGroup>` (`screen/dashboard/pane.rs:117`). `LinkGroup` = 9 variants A–I, displayed as digits `"1".."9"` (`data/src/layout/pane.rs:107-147`). It is persisted with the pane (src/layout.rs:118-309).

**UI.**
- Header button: `link_group_button` renders the group digit, or `-` when unlinked, 28px wide, active style = bordered toggle (`src/widget.rs:236-262`); wired at `pane.rs:524-526` → `Event::ShowModal(Modal::LinkGroup)`.
- Modal: 3×3 grid of group buttons; clicking the *already selected* group unlinks (tooltip "Unlink") (`pane.rs:2382-2428`).

**Joining a group** (`screen/dashboard.rs:304-337`):
1. Search *all* panes across main + popout windows (`iter_all_panes`, dashboard.rs:588-604) for the first *other* pane with that identical group.
2. That peer's `stream_pair()` — the `TickerInfo` of its first ready stream (pane.rs:139-146) — becomes the target.
3. If different from this pane's current symbol: `state.link_group = group; state.modal = None; state.set_content_and_streams(vec![ticker_info], state.content.kind())` and, if a kline stream resulted, fire `fetcher::kline_fetch_task` (dashboard.rs:326-360).
   → Joining = **"adopt the group's symbol, keep my own panel type"**. The pane re-derives its own stream kinds from its own `ContentKind`.

**Propagation on symbol change** (`switch_tickers_in_group`, dashboard.rs:867-928):
- Triggered from the ticker table selection path (dashboard.rs:396-402, `pane::Effect::SwitchTickersInGroup`).
- If the focused pane has a group: collect every pane (main + popouts) with `state.link_group == Some(group)` and call `init_pane(...)` on each with `ticker_info` + **that pane's own** `content_kind` (dashboard.rs:891-912).
- **What propagates: symbol only (`TickerInfo`, exchange-qualified, incl. min-tick size). Not the interval/timeframe, not the tick multiplier, not studies.** Each pane keeps its own basis: `PaneSetup::new` re-derives `basis`, `price_step`, `depth_aggr`, `push_freq` per content kind (data/src/layout/pane.rs:248-355). Ladder/heatmap default to `Basis::default_heatmap_time(ticker)`; candlestick to M15; footprint to M5 (pane.rs:263-298).
- Mixed data sources are explicitly supported: the pane's streams are rebuilt against whatever `TickerInfo` (venue, market type) came from the group; `PaneSetup` compensates for client-agg vs server-agg venues (tick multiplier default 5 vs 10, and 10 when switching from a client-agg venue to a server-agg one — data/src/layout/pane.rs:300-312).

**Losing the link.** Any symbol change that bypasses the group clears it: `init_focused_pane` sets `state.link_group = None` when the previous ticker differs (dashboard.rs:836-840); changing pane content kind to something else also clears.

**Edge cases observed.**
- No peer in the group yet → joining simply sets the group and leaves the pane untouched (dashboard.rs:326-328); the next group-wide symbol change includes it.
- Fallback: with no link group, symbol changes apply to the *focused* pane only; if only one pane exists it is auto-focused (dashboard.rs:875-880).
- Errors are user-visible toasts, e.g. "No link group or focused pane found" (dashboard.rs:919-925).

**Orthogonal mechanism — settings mirroring** (worth stealing separately): `borrow_synced_settings` finds any pane with the *same* `ContentKind` and copies `visual_config` + studies + cluster config into a newly initialized pane (dashboard.rs:723-744, 746-794; applied in `pane.rs:1854` `apply_synced_settings`). Every settings panel also ends with a **"Sync all"** button that pushes that config to all similar panes (modal/pane/settings.rs:846-852, `VisualConfigChanged(pane, cfg, true)`; the `true` = sync flag handled at dashboard.rs:270-300).

---

## 2. Tickers table (`screen/dashboard/tickers_table.rs`, 1872 lines)

**Structure.** Virtualized card list, `TICKER_CARD_HEIGHT = 64`, compact mode 28 (lines 56-66). One `TopBar` + optional sort/filter column + the list (view at 521-575).

**Card content** (`ticker_card`, 1011-1092) — two text rows plus a 2px left color bar:
- row 1: venue icon glyph, symbol (truncated to `...` past 11 chars, perps get suffix `P`), fill, daily change %;
- row 2: price, fill, abbrev daily volume;
- **price delta highlighting**: the price string is split at the first differing character vs the previous update; the unchanged prefix renders in normal text, the changed suffix in success/danger color (`split_price_changes`, data/src/tickers_table.rs:208-241) — cheap, high-signal, trivially portable;
- left bar alpha = `daily_price_chg / 8.0` clamped ±1 (data/src/tickers_table.rs:204).

**Expanded card** (`expanded_ticker_card`, 1094-1180): last price / daily change / daily volume rows, a favorite star, a back button, and **one button per ContentKind** (HeatmapChart, ShaderHeatmap, FootprintChart, CandlestickChart, ComparisonChart, TimeAndSales, Ladder) — this is how panes are created from the table.

**Sorting.** `SortOptions::{VolumeAsc,VolumeDesc,ChangeAsc,ChangeDesc}` (data/src/tickers_table.rs:31-37); clicking the active option flips direction (435-448); comparator at data/src/tickers_table.rs:66-77. **Sorting only runs once all selected venues' stats have landed** for that cycle (`complete_venue` returns true when the last in-flight venue finishes → `sort_ticker_rows`, lines 305-320, 1840-1849) — sorts don't jitter mid-fetch.

**Search.** `calc_search_rank` buckets matches exact(0) > prefix(1) > suffix(2) > substring(3), over both display and raw symbols, with an explicit rule that unsuffixed candidates may not score "exact" for perps; ties broken by position then length (data/src/tickers_table.rs:94-165). Query is uppercased on input (line 181).

**Favorites.** `FxHashSet<Ticker>` + `show_favorites` flag; the favorites block is rendered as a prefix section with a **synthetic gap row** injected into the virtual list (`VirtualListConfig.gap = Some((fav_n, separator_height))`, 546-560; `virtual_to_item`/`pos_to_index` mapping 1593-1641) so scrolling/positioning stays O(1).

**Update throttling.**
- Stats refresh subscription: every **13s while the table is visible, 300s while hidden** (consts 40-46; subscription 352-365).
- Per-venue cooldown = same 13s, tracked in `StatsFetchState::schedule_venues` (1804-1838); in-flight venues are never re-requested (1830-1838).
- Exchange filter toggles are **debounced 1s** with a 200ms tick that also animates a `.`/`..`/`...` loading indicator (48-54, 1775-1872); first-time enable bypasses cooldown once (`force_refresh_venues`, 1778-1786).
- Per-ticker display strings (`display_cache: FxHashMap<Ticker, TickerDisplayData>`) are computed only when stats change (463-503) — no per-frame formatting.
- Metadata: on-disk cache with freshness stamps; a cached seed is applied immediately unless something newer landed, with a background refresh replacing it (comment block 96-105, handling 316-345) — i.e. **stale-while-revalidate**.

---

## 3. Ladder / DOM panel (`screen/dashboard/panel/ladder.rs`)

**Layout — 5 horizontal bands** computed from the widget width every frame (`column_ranges`, 499-553):
`[ bid order qty | sell trades | PRICE | buy trades | ask order qty ]`
- `ORDER_QTY_COLS_WIDTH = 0.60`, `TRADE_QTY_COLS_WIDTH = 0.20` of the space left after price (20-22), split in half per side; 4 × `COL_PADDING = 4px` gutters.
- The price column width is derived from **monospace text metrics** of the longest of best bid/best ask: `chars * TEXT_SIZE * MONO_CHAR_ADVANCE(0.62) + 2 * inside_pad`, min 12px side pad (482-497) — the column never pushes price text into the numbers.
- Row height 16px; the price scale is a **centered grid**: index 0 is the spread row, `+idx` = bids below best bid, `-idx` = asks above best ask (`PriceGrid`, 890-921). `y = height/2 + idx*ROW_HEIGHT - ROW_HEIGHT/2 - scroll_px`.

**Price grouping.** `step: PriceStep` (from the pane's tick multiplier); a tick-size change is *deferred* to the next depth update (`pending_tick_size`, 99-103, 166-170) and then raw trades are re-binned (`TradeStore::rebuild_grouped`, data/src/panel/ladder.rs:122-127) — cheap, no data loss.

**Trade-volume overlay on grouped levels.**
- `TradeStore` keeps `raw: VecDeque<Trade>` **and** `grouped: KlineTrades` (price → buy_qty/sell_qty) (data/src/panel/ladder.rs:92-135).
- Grouping is **side-aware**: `trade.price.round_to_side_step(trade.is_sell, step)` — sells round down, buys round up (data/src/chart/kline.rs:187-194), matching how exchanges print.
- `draw_row` (554-671) emits 4 bars per row + text: order-qty bar (alpha 0.20) growing from the outer edge inward, sell-trade bar (alpha 0.30) right-aligned growing left, buy-trade bar left-aligned growing right, price text centered in the price column, colored by side.
- **Scaling is per-visible-range, not global**: bars divide by `maxima.vis_max_order_qty` / `vis_max_trade_qty` computed over visible rows only (787-869), so the ladder stays readable when the book thins out.
- `fill_bar` clamps width to the column and skips zero/NaN (672-702).

**Extras / interactions.**
- Spread row: shown only if `config.show_spread` **and** the venue is client-side aggregated (`is_depth_client_aggr`, 811-819), because server-aggregated feeds can't give a real spread.
- Chase tracker (default on): draws a trail from the previous best bid/ask to the current one plus a filled circle; consecutive pushes within `CHASE_MIN_INTERVAL = 200ms` extend the trail, longer gaps fade it out; computed from *raw* ungrouped prices (`draw_chase_trail`, 723-767; config at data/src/panel/ladder.rs:19-34).
- Interaction: wheel scrolls (16px/line, 216-224); **left/middle/right click anywhere = reset scroll to center** (211-215). There is **no** click-to-alert, no copy, no hover readout, no right-click menu in the ladder.
- Retention: `config.trade_retention` (default **8 min** = `TRADE_RETENTION_MS = 8 * 60_000`, data/src/panel/ladder.rs:15-34; 1–60 min slider inside `ladder_cfg_view`, modal/pane/settings.rs:753-845); pruning triggers a cache invalidation (113-133; `maybe_cleanup` data/src/panel/ladder.rs:150-...).
- Rendering: one `iced::canvas::Cache` redrawn (fully) on `invalidate()` (190-196). No incremental drawing — acceptable because a ladder paints ≲100 rows.

---

## 4. Time & Sales (`screen/dashboard/panel/timeandsales.rs`)

**Columns** (drawn at `draw`, 553-585): time `%M:%S.%3f` left-aligned at `x = 0.10 × width`; price end-aligned at `0.67 × width`; abbrev qty end-aligned at `0.9 × width`. Row height 14px (25).

**Row shading** (496-530): background = side weak color with alpha `qty / max_filtered_qty` clamped `[0.02, 1.0]`; text color is `lighten(color, alpha)` on dark themes / `darken(color, alpha*0.8)` on light — the size gradient *is* the signal.

**Filtering.** `config.trade_size_filter` in quote currency when the size unit is Quote (`market_type.qty_in_quote_value(...)`, 133-140, 456-462). `max_filtered_qty` is recomputed on prune so the alpha scale follows only rows that pass the filter (204-238).

**Throttling / limits.** No row cap: retention-based. `prune_by_time` drops from the front while the oldest row is older than `retention` (default 120s, settable 1–60min) using a `high_cutoff` slack of `retention/10` so the scan is skipped on most ticks (183-238; data/src/panel/timeandsales.rs:9-32). Drawing is bounded by `visible_rows = ceil(height/row_height)` via `.rev().skip(start_index).take(visible_rows + 2)` — newest at top, newest-first iteration (455-470).

**Pause-on-scroll (the good UX bit).** Scrolling down past the header row sets `is_paused`; incoming trades then land in `paused_trades_buffer` and are **excluded from the header aggregate**; a "Paused" pill is drawn top-left (597-660) with hover highlight, and clicking it (or middle-click, or any reset) flushes the buffer into `recent_trades` + `hist_agg` and resumes (20-52, 250-290, 625-672). `mouse_interaction` returns `Pointer` over the pill so the affordance is discoverable (625-660).

**Header stacked bar** (315-425): buy/sell composition bar, compact 8px or full 18px tall, with buy qty at x=8 left-aligned and sell qty at `width-8` right-aligned in full mode; metric = `Count | Volume | AverageSize` (data/src/panel/timeandsales.rs:34-79, `HistAgg::values_for` 144-186, average = rounded sum/count 96-110).

**No copy/export.** The crate contains no clipboard writes at all (only iced trait parameters).

---

## 5. The heatmap renderer

Two implementations exist; the **shader one is the reference design**.
- CPU: `Content::HeatmapChart` → `src/chart/heatmap.rs` (canvas).
- GPU: `Content::ShaderHeatmap` → `src/widget/chart/heatmap/**`.

### What is GPU vs CPU
**GPU (wgpu)** — `scene/pipeline.rs`:
- three pipelines: a full-bleed **heatmap quad** sampling a `texture_2d<u32>` depth texture (`shaders/heatmap_tex.wgsl`), an instanced **rect** pipeline (`shaders/rect.wgsl`), an instanced **circle** pipeline (`shaders/circle.wgsl`); shared camera/params uniforms (`shaders/common.wgsl`).
- Painter's order is a tiny display list of `DrawItem{DrawLayer, DrawOp}`: `HEATMAP(0) → DEPTH_PROFILE(10) → CIRCLES(20) → VOLUME(30) → VOLUME_PROFILE(40)` (pipeline.rs:57-84; assembled in `instance.rs:30-78`). One render pass, viewport+scissor clipped to the plot (pipeline.rs:962-1055).
- Depth data lives as **two u32 channels per cell** (bid qty, ask qty) in a ring-buffer texture, uploaded with `queue.write_texture` per changed column (pipeline.rs:690-898).

**CPU** — `instance.rs` builds the overlay instance arrays each frame: trade circles, volume-strip rects, volume-profile rects, depth-profile rects. `view.rs` + `ui/overlay.rs` + `ui/axisx.rs` + `ui/axisy.rs` are ordinary iced canvases (axes, crosshair, tooltip, legend, paused pill) with their own `canvas::Cache`s.

### Depth grid (`scene/depth_grid.rs`)
- `GridRing`: `horizon_buckets = 4800` (one bucket = one time slot), texture width = `next_power_of_two(4800) = 8192`, height = `tex_h = 2048` **price bins around an anchor** (lines 8-16, 248-283). Two `Vec<u32>` planes (bid/ask) + per-column and y-block maxima caches (19-30).
- X is a ring: absolute bucket → `bucket.rem_euclid(tex_w)`; the shader converts back with `(latest_x_ring + bucket_rel) & tex_w_mask` (depth_grid.rs:394-405; `heatmap_tex.wgsl`).
- Y is anchored: the anchor price only moves when the mid drifts more than `tex_h/4` bins, at which point the grid is cleared and a full rebuild is scheduled (284-345, 438-460). The shader aligns the texture to `base_price` via `heatmap_y_start_bin = -(tex_h/2) - delta_bins` (406-434).
- Ingest: `ingest_snapshot` drops out-of-order buckets, clears the target column, scatters bid/ask levels with `qty_scale` normalisation, and **fills carried gaps with the last known presence** rather than empty columns (`retain_current_presence_in_carried_gap`, 743-792) — no white stripes after a feed hiccup.
- Dirty tracking: `mark_dirty(x)` per column, `drain_dirty_columns()`, or `mark_full_dirty()`; `build_scene_upload()` returns either a column list or a full texture (534-560, 892-928). Uploads are additionally guarded by an upload **generation** counter so a redraw with unchanged data is a no-op (pipeline.rs:616-690).

### Grouping / aggregation controls
- **Price grouping (y)**: `px_per_step = row_h × cam_scale`; `steps_per_y_bin = ceil(MIN_ROW_PX(1.0) / px_per_step)` clamped to `[1, tex_h]` (view.rs:670-680; `scene/cell.rs:2,90-155`). A heatmap row is therefore never sub-pixel; zooming out *coarsens the price bins* instead of drawing hairlines.
- **Time aggregation (x)**: `aggr_time` = the pane's basis timeframe; a column is one bucket. The stream can also be requested with `PushFrequency::Custom(tf)` for venues that support server-side push rates (data/src/layout/pane.rs:330-340), and depth aggregation can be server-side or client-side (`StreamTicksize`, exchange/src/adapter.rs:237-245).
- **Cell size** is world-space with pixel clamps: col 1–20px, row 1–20px, world bounds col 0.01–1.0, row 0.01–4.0, defaults col 0.02 / row 0.04 (`scene/cell.rs:1-16`).
- **Order coalescing** ("merge orders if sizes are similar"): consecutive runs at a price level are merged when they overlap in time, are the same side, and their sizes match within a lot-similarity ratio (default 15%, radio `Average | First | Max`, slider 5–80%) — `CoalesceKind` (data/src/chart/heatmap.rs:514-560) + `coalesced_runs` (data/src/chart/heatmap.rs:305-380); UI at modal/pane/settings.rs:113-170. This is what stops a single iceberg order from painting 50 rows.

### Overlay, legend, crosshair (`ui/overlay.rs`)
- Crosshair **snaps to the cell center** (rounds to x-bin and y-bin, then to pixel halves) — 337-425.
- Tooltip = a **4-column × 3-row neighborhood** of cell quantities (`TOOLTIP_COL_OFFSETS = [-2,-1,0,1]`, `TOOLTIP_ROW_OFFSETS = [1,0,-1]`, lines 23-24), cell contents read straight out of the CPU depth grid, coloured by dominant side, and blanked if the whole neighborhood is empty (427-483, 697-760).
- Layout is cursor-aware: tooltip flips left when near the right edge, flips below when near the top, and additionally dodges the paused control (`TooltipLayout::from_cursor` / `avoid_overlap`, 52-133).
- When the neighborhood has data, the crosshair is drawn **around** the highlighted rect (not through it) and the rect gets an outline (590-696).
- Overall scale legend: labels + max-qty annotation drawn into a separate `scale_labels_cache` (204-320).
- Paused state: a "Paused" pill with a pause icon and hover alpha; clicking resumes and re-anchors to live (26-33, 509-590).

### How trades are drawn on top of depth
- Trades are instantiated CPU-side as **circles**: for each trade inside the visible time/price window, radius scales with `qty / max_qty_in_viewport × config.trade_size_scale` (default 100%) with a fallback radius of half a row in pixels; filtered by `trade_size_filter` in quote value (`instance.rs:307-368`; constants `VOLUME_PROFILE_WIDTH_PCT 0.10`, `DEPTH_PROFILE_WIDTH_PX 160`, `STRIP_HEIGHT_FRAC 0.10` at `widget/chart/heatmap.rs:36-48`).
- They land in layer 20, i.e. **above** the depth heatmap and the depth profile, **below** the volume strip and volume profile.
- Volume strip: bottom 10% of the viewport, one buy/sell bar pair per x-bin, x-binned so bars are never thinner than 2px (`MAX_COLS_PER_X_BIN = 4096`, `instance.rs:447-...`).
- Volume profile: left-edge split bars, width ≤ 10% of viewport, `ProfileKind::VisibleRange` or `FixedWindow(n buckets)` (instance.rs:178-306; data/src/chart/heatmap.rs:677-690).
- Depth profile: right-edge bars, 160px fixed width, from the latest snapshot (instance.rs:372-446).

### How it avoids re-rendering everything
- **`RebuildPolicy` state machine** (`view.rs:287-405`): `Idle | Immediate{force_from_historical} | Debounced{last_input, force_from_historical}`. Any pan/zoom/axis input calls `mark_input(now)`; `decide(now, REBUILD_DEBOUNCE_MS = 250)` returns `(do_overlays, do_full)`: while the user is still interacting → overlays rebuild, full grid rebuild deferred; after 250ms of quiet → one immediate full rebuild; Idle → nothing (heatmap.rs:39, 856-920; view.rs:383-405).
- **Panning/zooming never rebuilds the depth texture**; only the camera uniforms change. A rebuild is forced only when the y-binning (`steps_per_y_bin`) changes, on recentring, on resume-to-live, or on an explicit `force_rebuild_from_historical` request (heatmap.rs:833-850, 921-960).
- **Depth colour normalisation** (the `max_depth` alpha denominator) is throttled: recomputed at most every 100ms while interacting, otherwise once per time bucket, keyed + generation-guarded so identical windows reuse the cached value (`view.rs:13, 767-895`).
- **Generation counters** on every GPU upload path (rects, circles, texture) make repeated draws no-ops (pipeline.rs:616-690, 690-790).
- **Stall recovery**: if the last tick is older than 750ms, the next depth update forces a full texture re-upload, assuming the GPU resource was lost/desynced (heatmap.rs:42, 946-955).
- **Live-edge clock**: an `ExchangeClock` anchors on exchange timestamps and advances with a monotonic `Instant`, so the newest column keeps animating during feed gaps and the live edge never jumps backwards (view.rs:411-460); `Anchor::{Live,Paused}` tracks follow state and auto-resumes when panning back to the live edge (view.rs:17-45, 133-242; `try_resume_if_x0_visible` heatmap.rs:956-985).
- Axis UX that falls out of the same model: wheel over an axis zooms only that dimension, dragging an axis zooms anchored (live edge if visible, else the right edge), double-click X resets zoom + column width and returns to live, double-click Y resets the price offset (widget.rs:161-307; `ui/axisx.rs:38-150`).

---

## 6. Comparison panel

- Compares **N tickers' close-price series** on one shared timeframe; each series is `Vec<(bucket_ms, close)>` built from klines (`floor_to(timeframe)`), incrementally merged with dedupe, capped at `SERIES_MAX_POINTS = 5000` with oldest-dropped (`chart/comparison.rs:140-215`).
- **Normalisation is rebased to the left edge of the visible window**, not to series start: `pct = (y / y0 − 1) × 100` where `y0 = interpolate_y_at(points, min_x)` (domain::pct_domain, `chart/comparison.rs:~100-140`; interpolation at 86-100). Zero is always included in the domain; empty/degenerate domains are padded ±1 and the whole domain gets a 5% pad.
- Axis handling: zoom is expressed **in points** (default 150, clamped 2–5000) and pan **in points** (default 8 bars of right padding) (`widget/chart/comparison.rs:27-34`); the x-window is derived as `span = (n−1)×dt` (or full data), then snapped to bar boundaries via `align_floor/align_ceil`. Y labels are percent with decimals chosen from the tick step.
- Visuals: y gutter 66px, x axis 24px; end-of-series labels at the right edge with **overlap resolution** (`resolve_label_overlaps`); a top-left legend that is compact by default and expands on hover to per-series rows with a cog (rename/recolor) and close (remove) icon; hovering a legend row suppresses the crosshair so the row stays readable (`widget/chart/comparison.rs:231-405, 1306-1518`).
- Crosshair snaps x to the nearest bar boundary and prints the % value in the y gutter; lines break across gaps wider than `3 × dt` (`GAP_BREAK_MULTIPLIER`, line 30).
- Series editing produces actions `{SeriesColorChanged, SeriesNameChanged, RemoveSeries}`, persisted in the pane config as `(SerTicker → color/name)` maps (`chart/comparison.rs:22-30, 44-70`).

---

## 7. Indicator library (`src/chart/indicator/**`)

**Kline indicators** — enum at `data/src/chart/indicator.rs:14-18`, availability by market at 21-56 (`FOR_SPOT` = Volume/BarAnalysis/CVD; `FOR_PERPS` adds OpenInterest).

| Indicator | File | What it draws |
|---|---|---|
| Volume | `kline/volume.rs` | Bar plot per bar; when the datapoint has directional volume it renders a two-part bar (total in a weaker tone + a signed overlay = buy−sell that picks success/danger); tooltip splits buy vs sell volume (volume.rs:38-62). |
| Bar Analysis | `kline/bar_analysis.rs` | Footprint summary rows per bar (delta / imbalance style metrics) as a bespoke canvas row; derived from the same footprint data the chart already holds (`FootprintSummary::from_trades`, bar_analysis.rs:59-88). |
| CVD (Cumulative Delta) | `kline/cumulative_delta.rs` | Line of cumulative buy−sell per bar, with an explicit **trust flag**: a point is reliable only inside a run of ≥ `MIN_DIRECTIONAL_RUN = 2` consecutive non-zero-delta bars, and the first bar of each run is excluded; unreliable points break the line and show a message instead of a value tooltip (cumulative_delta.rs:21-35). Stored delta is kept separately so older klines can be replaced without a full rebuild. |
| Open Interest | `kline/open_interest.rs` | Line + point markers; shifted `−1` bucket because OI is snapshotted at candle *open*; tooltip shows OI and its change to the next point (open_interest.rs:50-70). |

**Heatmap indicators** — enum at `data/src/chart/indicator.rs:60-62`: `Volume` (toggles the volume strip). Studies are separate: `HeatmapStudy::VolumeProfile(ProfileKind)` (data/src/chart/heatmap.rs:659-675).

**Configuration / plotting plumbing.**
- All indicators implement `KlineIndicatorImpl` (`kline.rs:88-150`): `element(chart, labels_always_visible, visible_range)`, `availability()`, `fetch_range()`, and event hooks `on_insert_klines / on_insert_trades / on_ticksize_change / on_basis_change / on_open_interest` — i.e. **indicators are incremental and cache-aware, not recomputed from scratch**, and they can request their own historical fetch range (used by OI).
- `indicator_row` wraps a plot in `[canvas, vertical rule, y-label canvas]`, computes y extents over the visible range **padded one bucket each side** to avoid edge clipping, and paints the crosshair value in a coloured chip in the gutter (indicator.rs:28-101, 137-185).
- Plots: `LinePlot` (padding 8%, stroke width, optional point markers, `x_shift_buckets`, `is_valid` predicate + `invalid_point_message` — how CVD breaks its line) and `BarPlot` (`Baseline::{Zero,Min,Fixed}`, `BarClass::{Single, Overlay{signed}}`) (`plot/line.rs:17-60`, `plot/bar.rs:14-45`, `plot.rs`).
- Series abstraction is basis-generic: time basis → forward ms keys, tick basis → reversed u64 index keys (`kline.rs:11-22`).
- UI: per-pane `Vec<UiIndicator>`, toggled from a modal that filters by market type and supports drag-reorder (`modal/pane/indicators.rs`; `column_drag::reorder_vec` at widget/column_drag.rs:22-38).
- Cluster (footprint) rendering is a *separate* axis of config: `ClusterKind::{BidAsk, VolumeProfile, DeltaProfile, Table}` each with a minimum footprint width, and `ClusterScaling::{VisibleRange, Hybrid{weight}, Datapoint}` (data/src/chart/kline.rs:394-470).

---

## 8. Sound effects

- Engine: **rodio**, 4 embedded WAVs decoded once into `SamplesBuffer`s and cloned per playback: Buy (`hard-typewriter-click`), HardBuy (`dry-pop-up`), Sell (`hard-typewriter-hit`), HardSell (`fall-on-foam-splash`) (`src/audio.rs:4-15, 92-160`).
- **Trigger point**: only on trade events, right after the trades are ingested into the panes — `main.rs:231` (`audio_stream.try_play_sound(&stream, &buffer)` inside `Message::MarketWsEvent` → `Event::TradesReceived`, main.rs:218-235). Depth and kline events make no sound.
- **Per-symbol config**: `data::AudioStream { volume: Option<f32>, streams: FxHashMap<SerTicker, StreamCfg> }` with `StreamCfg { enabled, threshold }`, default `Threshold::Count(10)` (data/src/audio.rs). So sound is keyed on (exchange, ticker), independent per symbol.
- **Decision logic** (`modal/audio.rs:351-410`): count buy vs sell in the incoming batch; if the larger side is below the threshold → silence; otherwise pick the louder side (ties prefer buy); if the count exceeds `4 × threshold` (`HARD_THRESHOLD = 4`, line 15) use the *hard* variant. `Threshold::Qty` is declared but unimplemented (`todo!()` at line 410).
- **Volume / overlap handling** (`src/audio.rs:145-170`): a per-sound `(last_played, count)` pair; retriggers within `OVERLAP_THRESHOLD = 10ms` increment the count and the actual gain becomes `base_volume / overlap_count` — a burst of trades degrades into one soft hit instead of a clipping machine-gun. Volume 0 disables audio entirely (`volume: None`).
- Failure handling: no output device → audio disabled with a toast at startup (`main.rs:154-160`, `AudioError::is_no_device` audio.rs:38-48) and a **Retry** button in the audio modal (`modal/audio.rs:100-130`, 155-170).
- Audio settings UI: one global volume slider + a list of *active trade streams* with a per-symbol enable checkbox and per-symbol threshold; cards expand in place for editing (`modal/audio.rs:32-38, 187-...`).

---

## 9. Persistence + themes

- **Single JSON file**, `saved-state.json`, in the OS data dir; overridable with the `FLOWSURFACE_DATA_PATH` env var (data/src/lib.rs:20, 148-162). Written **atomically**: write to `*.tmp`, `sync_all()`, then rename — a crash can never leave a truncated state (data/src/lib.rs:39-63). Read errors fall back to `SavedState::default()` (src/layout.rs:315+).
- **Contents** (`SavedState`/`data::State`, src/layout.rs:24-40; serialization in main.rs:1385-1445): `layouts[]` (name + recursive pane tree: `Split{axis,ratio,a,b}` vs `Pane{content config, stream kinds, settings, link_group}`), active layout name, `theme` + optional custom theme, main window spec (size + position), timezone, sidebar state (position, open menus, **tickers-table settings incl. favorites/filters/search**), UI scale factor, audio config, network config (secrets stripped via `for_persistence()`), volume size unit, metadata-cache flag.
- Window geometry is captured from the live windows at save time (`window::collect_window_specs`, main.rs:270-300) so popout positions survive restarts.
- **Per-pane state is deep**: each pane persists its content kind, its stream kinds (as `PersistStreamKind`, resolved later against ticker metadata), its visual config, its studies/indicators, and its link group (src/layout.rs:100-310). Streams that can't be resolved at load time stay `Waiting` and are retried once metadata arrives (`ResolveStreams` event, main.rs:376-412).
- **Themes**: `Theme` wraps the iced theme; serialization writes either a bare string (`"dark"`, `"dracula"`, … , `"flowsurface"`, `"custom"`) or `{name, palette}` when custom (data/src/config/theme.rs:9-125). Deserialization accepts **both** shapes and falls back to the default theme on unknown names (theme.rs:120-215) — a forward-compatible theme format. Default palette: background `#181616`, text `#C5C9C5`, primary `#C8C8C8`, success `#51CDA0`, danger `#C0504D`, warning `#EED88B` (theme.rs:31-45).
- Custom theme editor = 6 named palette roles (Background, Text, Primary, Success, Danger, Warning) with an HSVA picker + hex input (modal/theme_editor.rs:13-90); the app also ships a colour picker widget with decorations (widget/color_picker.rs).
- **Settings modal organisation** (worth copying wholesale): there is **no giant settings dialog**; each pane type has its own modal, all built from the same skeleton — a `cfg_view_container(max_width)` scrollable card of sections separated by rules, each section a labelled slider/checkbox/radio group, ending with a `Sync all` button pointing at `VisualConfigChanged(pane, cfg, sync=true)` (modal/pane/settings.rs:30-40, 846-852):
  - `heatmap_cfg_view` (42-283): size filters (trade $ / order $, 500-step sliders), noise filters (coalescing on/off + merge method radios + similarity slider), trade visualization (dynamic circle radius + scaling %), Studies, Sync all; max width 360.
  - `heatmap_shader_cfg_view` (284-403): same skeleton for the GPU heatmap.
  - `timesales_cfg_view` (404-579): size filter, history retention (1–60 min slider with an `≈ N min` label + an ⓘ tooltip explaining its effect on the stacked bar/scroll), stacked bar on/off → mode (Compact/Full) + metric picklist; max width 320.
  - `ladder_cfg_view` (753-845): show spread, show chase tracker (with ⓘ tooltip describing the algorithm), trade retention; max width 320.
  - `kline_cfg_view` (597-752) and `comparison_cfg_view` (580-596: series editor only).
- Global modals hang off the sidebar menu enum `{Layout, Settings, Audio, ThemeEditor, Network}` (data/src/config/sidebar.rs:67-73); the Layout manager supports add/rename/clone/drag-reorder/remove and "preview" mode (modal/layout_manager.rs:25-39, 139-200). The Network editor keeps a **draft vs effective** config and a `pending_apply` that requires a restart, with confirm states for destructive clears (modal/network_editor.rs:24-120).

---

## 10. Ranked: genuinely reusable ideas for ModFlow OrderFlow Analysis Suite

Ranking = (value to this app) ÷ (effort × risk to a shipped beta with 716 tests and no build step). All items are **ideas/structures**, no GPL text.

| # | Idea | What & why | Effort | Risk |
|---|---|---|---|---|
| 1 | **Link groups (A–I) with symbol-only propagation** | Add `linkGroup?: 'A'..'I'` to each widget's persisted config; one header chip (digit or `-`); a 3×3 picker. On "user picked a symbol", resolve `peersInGroup(group)` over *all* screens/aux windows and rebase each peer's symbol while keeping its view type. Joining a group adopts the peer's symbol immediately. Clear the link whenever a symbol is set outside the group path. Implement `peersInGroup`, `adoptSymbol(spec, peerSpec)` as **pure functions** → unit-testable, zero risk to existing paths. | M | Low |
| 2 | **Input-debounced rebuild state machine** for the canvas heatmap | `Idle/Immediate/Debounced{lastInput}`: while the pointer is moving (wheel/drag) redraw only cheap overlays; after ~250ms quiet do one full recompute. Kills the "heatmap stutters while zooming" class of bugs and is a ~60-line pure state machine with a fake-clock test. | S–M | Low |
| 3 | **Dirty-column + generation-guarded heatmap updates** | Keep columns in a ring buffer (power-of-two width), mark only the current column dirty per snapshot, keep an upload generation so a redraw with no new data is a no-op; full rebuild only on recentre, bin change, or resume-from-history. In JS: an `OffscreenCanvas` column atlas + `drawImage` blits, or a shifting write index on one big canvas. | M | Med — gate behind a flag with the current renderer as fallback |
| 4 | **Cell-quantised crosshair + 3×4 neighbourhood tooltip** | Snap the crosshair to the nearest cell centre, draw the crosshair *around* the highlighted block instead of through it, print a 4-col × 3-row qty grid, flip the tooltip near edges, and blank both when the block is empty. Pure layout math → high test coverage, big perceived-quality win. | S | Low |
| 5 | **Tape pause-on-scroll** | Scrolling into history pauses the tape, buffers incoming prints (aggregate untouched), shows a clickable "Paused" pill; resume flushes the buffer and recomputes the header aggregate. Standard in pro tapes, currently rare in web UIs. | S–M | Low |
| 6 | **Row shading by relative size** (tape) | Background alpha `qty / maxOf *filtered* rows`, clamped `[0.02, 1]`, text `lighten/darken` by the same alpha; recompute the max on prune only. One function, huge readability gain. | S | Low |
| 7 | **Per-symbol sound alerts: count threshold + hard variant + overlap attenuation** | Map symbol → `{enabled, threshold}`; per trade batch count buys vs sells; play only if the louder side ≥ threshold, play the "hard" sample at `>4× threshold`; attenuate by `1/overlapCount` when retriggered within 10ms; expose a global volume with 0 = off and a device-failure toast + Retry. WebAudio makes this easy; mock the audio node in tests. | S–M | Low |
| 8 | **DOM ladder column math** | 5 bands `[bidSize | sellPrints | price | buyPrints | askSize]`, price column width from monospace metrics of the longest of best bid/ask, order bars scaled to the max of **visible** rows only, trade bars left/right-growing with side-aware price rounding (sells round down, buys round up), spread row only when the feed is client-aggregated, deferred tick-size change re-binning stored raw prints. Port the math, keep the existing DOM widget. | M | Med — the app already has a DOM panel; land it as a new render mode, not a rewrite |
| 9 | **Settings mirroring + "Sync all"** | New pane of type T inherits visual config/studies from an existing pane of type T; each settings card gets a "Sync all" that pushes its config to all panes of that type. Cheap consistency win for an 11-view shell. | S | Low |
| 10 | **Exchange-clock "now" + live-edge follow/pause** | Anchor to feed timestamps and advance with `performance.now()` so the newest column keeps painting during feed gaps; auto-pause follow when the user pans right of live, auto-resume when they pan back. Prevents the classic "everything freezes but the clock" bug. | M | Med |
| 11 | **Percent-rebased comparison chart** | Rebase each series to its interpolated value at the *left edge of the visible window*; pad the domain 5%; percent y-axis with adaptive decimals; gap-break lines wider than 3 bars; hover-expand legend with per-series cog/remove. Directly maps onto the existing comparison view. | M | Low–Med |
| 12 | **Virtual list with a synthetic separator/gap row** | Fixed row height + overscan(3) + `virtualIndex → itemIndex` mapping so a favourites section, separators and "add" affordances can be spliced into a virtualized list without breaking scroll math. Reusable for the watchlist. | S–M | Low |
| 13 | **Indicator availability model** | Each indicator declares availability (exchange/timeframe/basis/data-present) and yields a human-readable reason; the UI disables the toggle and shows the reason instead of drawing garbage. Directly applicable to the existing studies/indicators registry. | S | Low |
| 14 | **Atomic state writes + tolerant deserialisation** | Write layouts/state to `*.tmp` → fsync → rename; every field deserialises with a default fallback; the theme accepts both a bare name and a `{name, palette}` object. Protects beta users' layouts and makes schema evolution free. | S | Low (needs one migration test) |
| 15 | **Per-pane toast manager** | Notifications rendered inside the pane that produced them, with title/body, status colour, manual close, auto-timeout and a max body height with clipping — errors stay where the user is looking. | S | Low |
| 16 | **Drag-reorder with a dedicated handle + vertical-only clamp** | Indicator/pane ordering via a 14px handle, drop index = nearest slot, clamped to the container. Watch for pointer-capture quirks in WebView2. | M | Low–Med |
| 17 | **Toast/perf-hygiene constants worth stealing verbatim** | 13s active / 300s hidden refresh cadence; 1s exchange-toggle debounce; 10% prune slack; 250ms heavy-rebuild debounce; 100ms live-normalisation throttle; 750ms stall → full resync. These numbers are battle-tested and cheap to adopt as configuration. | S | Low |

**Explicitly NOT portable** (and why): the wgpu pipelines and WGSL shaders (WebView2 + canvas 2D; the *transferable* ideas are instanced draw layers, painter's order and generation counters); iced widget internals (`pane_grid`, `MultiSplit`, `decorate`, `column_drag` — reimplement the UX, not the widget); rodio; the Arrow-IPC market-data cache; Rust's type-driven settings hierarchy (JS needs a different validation approach, e.g. JSON-schema-ish defaults per panel).

**Cross-cutting note for the 716-test requirement:** the most valuable items (1, 2, 4, 6, 7, 13, 14) are all expressible as pure functions / small state machines over plain objects — the same shape as the existing `*.selftest.js` files, so they can ship with self-tests and zero coupling to the canvas render loop.
