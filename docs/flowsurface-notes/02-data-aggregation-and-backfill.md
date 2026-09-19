<!-- Reading notes for docs/FLOWSURFACE_FOLD_IN_PLAN.md. Source: github.com/flowsurface-rs/flowsurface
     @ c1388d4 (2026-09-16), cloned read-only. GPL-3.0: these notes describe behaviour only —
     no flowsurface code appears here and none may be copied into this repo. -->

# flowsurface `data/` + `src/connector/fetcher.rs` — aggregation, frames, heatmap model, backfill, persistence

# flowsurface (Rust) → OFAP: aggregation / backfill / persistence briefing (B)

Source: `C:\Users\<you>\AppData\Local\Temp\flowsurface_ref` (GPL-3.0, read-only, **ideas only — no code copying**).
Target: `C:\Users\<you>\OrderFlow-Analysis-Pro` (Python FastAPI + pywebview + JS/canvas + SQLite; 7-day tick retention; heatmap `max_columns 900 @ 1s`).

Correction up front: `data/src/chart/ticks/x.rs` is **not** the tick-bar module. It is the **time-axis label grid** (time labels + thinning). Tick *bars* live in `data/src/aggr/ticks.rs`; `data/src/chart/ticks/y.rs` is the price-axis grid. Both are covered below.

---

## 1. Tick-based intervals (`data/src/aggr/ticks.rs`, `data/src/aggr.rs`, `data/src/chart.rs`)

**Definition.** A tick bar = a fixed count of *trades* (aggTrade events), not ticks/quotes, not volume.
- `TickCount(pub u16)` newtype, presets 10/20/50/100/200/500/1000/2000/5000/10000 — `data/src/aggr.rs:6-26`; `Display` = `"{n}T"` (`aggr.rs:28-32`).
- `TickAccumulation { tick_count, kline, footprint }` — `data/src/aggr/ticks.rs:9-14`. `new()` seeds OHLC from the first trade and qty from it (`ticks.rs:17-35`); `update_with_trade` increments `tick_count`, does `high.max/low.min`, sets `close = price`, adds qty (`ticks.rs:37-46`); full when `tick_count >= interval.0` (`ticks.rs:57-59`).
- `TickAggr { datapoints: Vec<TickAccumulation>, interval: TickCount, tick_size: PriceStep }` — `ticks.rs:92-96`.

**State kept / algorithm.** `insert_trades` (`ticks.rs:134-165`) is a strict **append-only** fold: if `datapoints` is empty → push new; else if the *last* DP is full (`ticks.rs:145`) → push new; else mutate the last DP. No index math, no time key, no random access. POC recomputed only for touched indices (`ticks.rs:158-162`), then the naked-POC status pass (`ticks.rs:167-202`) which is index-based and deliberately *reverses* indices for the renderer (`ticks.rs:186-191`).

**Interaction with the time path.** Both live behind one enum: `Basis::Time(Timeframe) | Basis::Tick(TickCount)` (`data/src/chart.rs:84-92`) and `PlotData::TimeBased(TimeSeries<D>) | PlotData::TickBased(TickAggr)` (`chart.rs:25-28`). Everything downstream is basis-aware by key type only: visible price range maps `UnixMs` for time and plain `usize` **indices** for tick (`chart.rs:54-66`); derived series are `BasisSeries<T>::Time(BTreeMap<UnixMs,T>) | Tick(BTreeMap<u64,T>)` keyed by **bar index** (`chart.rs:141-185`), and `TickAggr → BTreeMap<u64, Volume>` uses the enumerate index as key (`ticks.rs:315-324`). So the tick path has **no x-time at all** — x is ordinal.

**What breaks if done naively.**
1. **No historical backfill exists.** `PlotData::TickBased(_) => { // TODO: implement trade fetch }` (`src/chart/kline.rs:458-460`) and `insert_raw_trades` early-returns for tick-based (`src/chart/kline.rs:705-710`): fetched history is *silently discarded* on tick charts. A partial tick bar cannot be reconstructed from klines — you need the full trade stream.
2. **The heatmap refuses it**: `Basis::Tick(_) => unimplemented!()` in `HistoricalDepth::new` (`data/src/chart/heatmap.rs:146-152`) and in `TimeSeries::<HeatmapDataPoint>::new` (`data/src/aggr/time.rs:510-522`) — wiring tick basis into the depth chart **panics**.
3. **Late/out-of-order trades corrupt everything.** Because `insert_trades` only ever appends to the last DP, a backfilled batch with older timestamps is written as *newest*: bar boundaries, OHLC and volume all shift. Fixing this requires re-sorting by time and re-partitioning the whole series, which is why they don't attempt it.
4. **Unbounded open bar.** The live bar stays open for an arbitrary wall-clock duration; any time-keyed downstream (SQLite retention cutoff, 1 s heatmap buckets, time axis, session aggregation) misplaces it. Persisting the in-progress bar means its meaning changes on restart.
5. **Tick-size changes force a rebuild from raw trades**: `change_tick_size(&mut self, tick_size, raw_trades)` clears all datapoints and re-folds (`ticks.rs:113-121`); the time path only re-bins existing buckets (`data/src/aggr/time.rs:329-337`). So the app must retain every raw trade for the whole visible tick-bar span — at 7-day retention that's not free.

---

## 2. Time aggregation (`data/src/aggr/time.rs`)

**Model.** `TimeSeries<D> { datapoints: BTreeMap<UnixMs, D>, interval, tick_size }` (`time.rs:28-32`). BTreeMap is the whole design: ordered iteration, and cheap `range(earliest..=latest)` scans for every visible-range query (`time.rs:103, 391, 500, 528, 559, 988 in widget`). No sort step anywhere on the hot path.

**Bucketing / alignment.** Bucket key = `trade.time.floor_to(interval)` (`time.rs:274, 312`); klines are keyed by the exchange's `kline.time` (`time.rs:255`). Trade buckets and kline buckets are assumed to be the same grid. There is no explicit phase/offset field: alignment is implicit in `floor_to`, but `check_kline_integrity` recovers it as `phase = series_earliest % interval` (`time.rs:212`) and aligns via `align_down_to_phase` (`time.rs:146-154`) so a series that begins off-grid (e.g. first kline at 12:00:17) is checked on *its own* phase. Integrity scan is guarded by `MAX_INTEGRITY_SCAN = 1_000_000` and runs in two passes (detect, then collect) (`time.rs:156-199`).

**Live vs historical stitching — the key rule.** Two insert verbs:
- `insert_trades_or_create_bucket` (`time.rs:267-303`): creates a missing bucket, seeding OHLC from the first trade. Used for **live** trades.
- `insert_trades_existing_buckets` (`time.rs:305-327`): writes **only** into buckets that already exist; trades for unknown buckets are dropped. Used for **backfilled** trades (`src/chart/kline.rs:687, 727, 752`).
Consequence: only klines (from the exchange) may define the bar grid; a backfilled trade can never invent a bar. And for the time path, `KlineDataPoint::add_trade` only touches the footprint (`data/src/chart/kline.rs:23-25`) — backfilled trades cannot corrupt candle OHLC. Live kline updates overwrite the whole `Kline` (`time.rs:261`).
Overlap safety at the consumer: the dashboard compares the batch's last trade time against `until_time`; if `>= until_time` it filters `trade.time <= until_time` and marks the fetch done, otherwise it forwards as a mid-batch (`src/screen/dashboard.rs:957-980`).

**Gaps and out-of-order.**
- Gap detection: `find_trade_gap` scans **in reverse** for the newest bucket whose footprint is empty, then finds `last_trade_time` before it and `first_trade_time` after it (`time.rs:463-487`).
- Gap → fetch range: `suggest_trade_fetch_range` (`time.rs:407-461`) clamps to the visible window, **floors `gap_start` to the interval** so the first bucket is fully covered (`time.rs:427-430`), and when the next known trade *after* the gap exists, fetches the entire gap in one shot rather than truncating at `visible_latest` — the comment explains fast scrolling otherwise leaves a trailing gap refetched on every scroll (`time.rs:432-441`). Sub-interval slivers caused by clamping are skipped (`time.rs:443-455`).
- Out-of-order/late data is rejected at the ingest boundary, not sorted in: depth snapshots with `time < last_snapshot_time` are dropped (`data/src/chart/heatmap.rs:164-169`), late heatmap buckets dropped (`depth_grid.rs:338-343`).

**"Fixed vs visible range" volume profile.** `ProfileKind::VisibleRange | FixedWindow(usize)` (`data/src/chart/heatmap.rs:677-690`), displayed as a `HeatmapStudy` (`heatmap.rs:658-665`).
- `VisibleRange`: window = the visible x-range (`src/chart/heatmap.rs:949-953`).
- `FixedWindow(n)`: window = `latest_x.min(visible_right_edge) - n*interval` — i.e. anchored to the **live edge**, not the visible edge, so panning does not move the profile (`src/chart/heatmap.rs:954-966`; identical logic in bin space at `src/widget/chart/heatmap/instance.rs:212-222`).
Both are recomputed **on demand** per rebuild by scanning `trades.datapoints.range(...)` and binning to price rows, hard-capped: `if num_ticks > 4096 { return; }` (`src/chart/heatmap.rs:979-981`). Cluster scaling is likewise range-scoped on demand (`ClusterScaling::VisibleRange|Hybrid|Datapoint`, `data/src/chart/kline.rs:441-472`; `max_qty_ts_range` `time.rs:489-507`).

**Time-axis labels (`data/src/chart/ticks/x.rs`)** — reusable as-is conceptually: per-timeframe candidate step tables (`x.rs:16-84`), step picked by ranking *rendered* spacing against a pixel budget (`TimeSteps::pick_closest` `x.rs:141-166`), pixel-based thinning stride rounded to divide the local day (`intraday_stride` `x.rs:103-133`), grid generated one step + one max-label-width **past each edge** so labels slide in off-screen instead of popping (`x.rs:331-345`), calendar layers (day/month/year) generated separately and merged with coarsest-weight-wins dedupe (`x.rs:378-440`), then placement coarsest-first keeping a label only if the pair-specific half-width gap is respected (`x.rs:477-531`). All generation is guarded by `MAX_GRID_LINES = 1000` (`data/src/chart/ticks.rs:5`). Price axis is analogous: a `RowGrid` snapped to positive multiples of the price step (bounded by a "nice span" target, `y.rs:77-92`) vs a `FloatGrid` whose steps come from the `{1, 2, 2.5, 4, 5} × 10^k` family (`tick_span_min`, `data/src/chart/ticks/y.rs:372-377`), walked top-down under a `MAX_GRID_LINES` guard (`y.rs:189-198`); a row-grid fallback exists for ranges narrower than one row step (`y.rs:97-105`).

---

## 3. Historical DOM heatmap data model

**CPU model (`data/src/chart/heatmap.rs`).** `HistoricalDepth { price_levels: BTreeMap<Price, Vec<OrderRun>>, aggr_time, tick_size, min_order_qty, last_snapshot_time }` (`heatmap.rs:136-143`). `OrderRun { start_time, until_time, qty, is_bid }` (`heatmap.rs:109-134`) is a **rectangle in (price,time)**: a level's *presence interval*, not a per-bucket snapshot. That is the memory strategy — an unchanged level costs one run for the whole time it persisted.
Merge rule in `update_price_level` (`heatmap.rs:211-260`): same side and equal qty → extend `until_time`; qty changed → close previous run at `t`, push new; side flip → close, push; **snapshot gap** (`time > prev + aggr`) with equal qty → still extend continuity (`heatmap.rs:224-235`), otherwise close and push. Bids and asks are grouped with **side-aware** rounding (`round_to_side_step(is_bid)`, `heatmap.rs:194`), deliberately different from the footprint's nearest-bin rounding (`data/src/chart/kline.rs:184-206` documents that side-bin rounding biases bin edges and must not be used for footprint).
Queries: `iter_time_filtered` = price range × overlap test (`heatmap.rs:266-279`); `coalesced_runs` merges adjacent same-side runs whose qtys are within a **lot-similarity** threshold (`CoalesceKind::First/Average/Max`, default `Average(0.15)`; compared in lots via `min_order_qty`) (`heatmap.rs:304-375, 513-559, 569-632`); `query_grid_qtys` answers tooltip grids from (time-offset × price-offset) arrays (`heatmap.rs:377-460`).
Eviction: `cleanup_old_price_levels(oldest_time)` retains runs with `until_time >= oldest_time`, dropping empty price levels (`heatmap.rs:296-302`).

**GPU/render model (`src/widget/chart/heatmap/scene/depth_grid.rs`).** `GridRing` = a fixed ring buffer: `GRID_HORIZON_BUCKETS = 4800` → `tex_w = next_power_of_two() = 8192`, `tex_h = 2048`, two `Vec<u32>` grids (bid/ask) + aux maxima (`depth_grid.rs:8-35, 248-281`). x = `bucket.rem_euclid(tex_w)` (`depth_grid.rs:333-335, 394-399`); y = `(price-anchor)/step/steps_per_y_bin` (`depth_grid.rs:381-389`). Qty is quantised to u32 at ingest via a `qty_scale` (`depth_grid.rs:209-214, 598-601`). Auxiliary maxima — `col_max_bid/ask` per column and `block_max_*` per 16-row block (`Y_MAX_BLOCK_HEIGHT_BINS`, `depth_grid.rs:8, 224-236, 690-740`) — give cheap scaling/downsampling without rescanning the grid.

**Live vs on demand.**
- Live (`ingest_snapshot`, `depth_grid.rs:284-379`): clear the newest column, `scatter_side` the book into it (`depth_grid.rs:557-644`), then **carry forward**: `advance_and_fill_columns` copies the previous column into every skipped bucket (`depth_grid.rs:854-889`) — with an explicit `TODO` that stream stalls must be handled a layer above — followed by `retain_current_presence_in_carried_gap` which zeroes carried rows absent from the current column (`depth_grid.rs:743-791`), so a vanished wall does not remain painted.
- On demand (`rebuild_from_historical`, `depth_grid.rs:118-246`): triggered by zoom/pan, binning change (`depth_grid.rs:296-305`), or y-anchor drift beyond 25 % of `tex_h` (`RECENTER_Y_MARGIN_FRAC`, `depth_grid.rs:11, 438-457`); fills each run into every bucket it overlaps (`b0..=b1`, `depth_grid.rs:177-238`), max-combining. Interaction rebuilds are debounced 250 ms (`REBUILD_DEBOUNCE_MS`, `src/widget/chart/heatmap.rs:38-39`); staleness after a 750 ms stream gap forces a resync (`src/widget/chart/heatmap.rs:42`).
- Upload protocol: full texture vs only dirty columns (`depth_grid.rs:892-925`).
- Retention is derived from the ring, not chosen: `keep_buckets = tex_w`, `keep_ms = keep_buckets * aggr_time`, `split_off(cutoff)` prunes trade buckets and `cleanup_old_price_levels` prunes runs to the same cutoff, every 64 depth updates (`src/widget/chart/heatmap.rs:585-612, 469-471`). Legacy path equivalent: `CLEANUP_THRESHOLD = 4800` datapoints, drop oldest 1/10, then prune depth to the oldest remaining bucket (`src/chart/heatmap.rs:261-279`).

---

## 4. Historical trade backfill

**Server contract (`/trades.arrow`)** — client at `src/connector/client.rs:83-236`, README `README.md:48-67`:
- `GET {base_url}/trades.arrow?venue=&market=&symbol=&from=&to=&limit=` — venue/market/symbol lowercased, `from`/`to` inclusive ms (`client.rs:178-194`).
- Optional `Authorization: Bearer <token>` (`client.rs:196-198`); token lives in the OS keychain, never in JSON (`data/src/config/auth.rs:122-213`, `data/src/config/network.rs:9-14`).
- Response `Content-Type: application/vnd.apache.arrow.stream` (warned if different, not fatal) (`client.rs:218-228`).
- Client is only constructed when mode = `Server` and URL non-empty/valid; trailing slash stripped (`client.rs:107-124, 146-154`). 30 s request / 10 s connect timeouts; the *server* client sets `danger_accept_invalid_certs(true)` for self-signed certs (exchange client does not) (`client.rs:44-71`).
- **Arrow schema**: four columns matched **by name**, order insignificant, extra columns ignored: `ts int64`, `price float64`, `qty float64`, `is_sell bool`; validated up-front and fails fast on mismatch (`client.rs:239-291`). qty is normalised per market kind (inverse → quote units, spot/linear → base) (`client.rs:325-333`). Rows with nulls in any required column are skipped, but the last *non-null* `ts` still advances the paging cursor (`client.rs:375-409`; `ParsedArrowBatch { trades, raw_row_count, last_ts }` `client.rs:298-308`).

**Paging** (`src/connector/fetcher.rs:585-642`): `ARROW_LIMIT = 400_000` rows/call (`fetcher.rs:18-19`); single forward loop, `cursor = last_ts + 1`, streaming each batch to the UI as it arrives; empty response ends the loop; a non-advancing cursor is a hard error to prevent an infinite loop (`fetcher.rs:630-638`). `Ok(false)` = source confirmed no data.

**Request lifecycle** (`fetcher.rs:93-169`): `FxHashMap<Uuid, FetchRequest>` keyed by exact `(start,end)`; on a repeat range — `Completed` → no-op, `Pending` → `Overlaps`, `NoData` → never retried, `Failed(ts)` → retry only after `RETRY_AFTER_MS = 30_000` (`fetcher.rs:99`) else `Failed`. `has_pending` is consulted before issuing (`src/chart/kline.rs:409`). Fetch priority order per update tick, one request at a time: klines (visible + one-visible-span prefetch) → trades (footprint only) → indicator OI → missing-klines integrity fill (`src/chart/kline.rs:380-456`; trade fetch also gated by `is_trade_fetch_enabled()`). Tick charts are excluded from all trade fetching (`src/chart/kline.rs:458-460`).

**Binance bulk mirror** (`exchange/src/adapter/hub/binance/fetch.rs:587-739`):
- paths `data/spot/daily/aggTrades/{SYMBOL}`, `data/futures/um/daily/aggTrades/{SYMBOL}`, `data/futures/cm/daily/aggTrades/{SYMBOL}` (`:596-600`); file `{SYMBOL}-aggTrades-{YYYY-MM-DD}.zip` (`:602-606`); URL `https://data.binance.vision/{path}` (`:619`). Daily granularity only — no monthly archives.
- Cache-first: if the zip exists on disk it is reused (`:616-617`); cached zips >4 days old are deleted by filename-date regex, on a startup background thread (`data/src/lib.rs:165-216, 218-230`; `src/main.rs:52`).
- Headerless CSV inside the zip; fields used = index 1 `price`, 2 `qty`, 5 `time(ms)`, 6 `is_sell` (`:658-678`).
- Dispatch: `from >= today's UTC midnight` → intraday only (`/api/v3/aggTrades` spot weight 4, `fapi/v1/aggTrades` / `dapi/v1/aggTrades` weight 20, `limit=1000&startTime=`) (`:549-585, 707-709`); otherwise fetch that day's zip and then top it up with intraday from the zip's last trade (`:717-731`); zip failure falls back to intraday-only with a warning (`:732-738`). (Klines/OI are always exchange REST; OI is clamped to Binance's 30-day window — `:503-522`.)

**Python feasibility: cheap.** `pyarrow.ipc.open_stream` reads the identical bytes; `requests`/`httpx` covers the params; a 400 k-row batch is ~10-15 MB and parses in well under a second in pyarrow; `zipfile` + `csv`/`pyarrow.csv` handles data.binance.vision. OFAP can additionally **implement** the same `/trades.arrow` contract on its FastAPI side (its SQLite tick store is the natural source), giving one stable protocol for desktop ↔ dashboard ↔ third-party tools. The one design point to copy is the cursor discipline (`last_ts + 1`, never trust row counts) plus the `until_time` overlap filter before insert (`src/screen/dashboard.rs:957-980`).

---

## 5. Persistence

- **One JSON file**, `saved-state.json`, under `data_path` = `$FLOWSURFACE_DATA_PATH` or the OS data dir + `flowsurface` (`data/src/lib.rs:29, 148-163`).
- **Atomic writes**: temp file → `write_all` → `sync_all` → `rename`, so a crash or partial write leaves the previous good state (`lib.rs:39-65`).
- **Contents**: `State { layout_manager: Layouts, selected_theme, custom_theme, main_window: WindowSpec, timezone, sidebar, scale_factor, audio_cfg, network, size_in_quote_ccy, cache_market_metadata }` (`data/src/config/state.rs:10-30`). Layouts = recursive pane tree `Split{axis,ratio,a,b}` / HeatmapChart / ShaderHeatmap / KlineChart / ComparisonChart / TimeAndSales / Ladder, each carrying `settings` (`tick_multiply`, `visual_config`, `selected_basis`), `studies`, `indicators`, `link_group`, and `stream_type: Vec<PersistStreamKind>` (`data/src/layout/pane.rs:22-104, 98-104`).
- **No version field.** Compatibility is achieved by tolerance:
  - container-level `#[serde(default)]` (`state.rs:17`) so missing top-level keys default;
  - `ok_or_default` per field: deserialise to `serde_json::Value`, then `T::deserialize(v).unwrap_or_default()` — so **one** unrecognised enum tag / malformed sub-object degrades that field to its default instead of failing the whole file (`data/src/util.rs:8-15`; used pervasively, e.g. `pane.rs:31-88`);
  - deprecated variants retained and converted on load (`PersistStreamKind::DepthAndTrades` → Depth + Trades, `data/src/stream.rs:14-17`);
  - unresolved tickers don't crash: `into_stream_kinds(resolver)` returns `Err` per stream so the pane can show an error and refetch (`stream.rs:65-106`).
  - If the file cannot be parsed at all: it is renamed to `saved-state_old.json` (backup), defaults are used, and the app continues (`lib.rs:83-111`).
- **Secrets are never in JSON**: `server_auth_token` is `#[serde(skip)]`; tokens/proxy credentials live in the OS keychain (service keys `flowsurface.server`, `flowsurface.proxy`), and proxy auth is stripped before write (`data/src/config/network.rs:9-25`, `data/src/config/auth.rs`).
- **Other on-disk state**: `metadata-cache.json` (venue → tickers + per-venue freshness stamps, merged newest-wins, only when the cache toggle is on; stale entries are still served and refreshed) (`data/src/metadata.rs:12, 85-106, 209-241, 268-280`); `market_data/binance/...` zips pruned >4 days (`lib.rs:165-230`).
- **Save triggers**: window move/resize/close and state changes call `save_state_to_disk`, which rebuilds `data::State` from live state and serialises (`src/main.rs:280-287, 1385-1445`). Note there is **no cache of market data in the state file** — only settings/layouts; market data is cached as raw downloaded zips only.

---

## 6. Ranked reusable ideas for OFAP

Each: **what → why better → effort → risk** (app must not break: shipped beta, 716 tests). Target modules referenced from `orderflow_system/`.

1. **Gap-driven backfill planner** (`aggr/time.rs:407-487`) → today the app backfills "the visible window"; instead scan reverse for the newest empty bucket, find the last trade before / first trade after the hole, floor the start to a bucket boundary, and when the next trade after the hole is known fetch the whole hole in one shot (avoids the trailing-gap refetch loop). → **S** → low. Pure read path; unit-testable against `test_retention.py`-style fixtures; no schema change.
2. **Run-length order-book model for the depthmap** (`chart/heatmap.rs:109-260`) → replace per-tick/per-second snapshots in a new `depth_runs(symbol, side, price, start_ms, until_ms, qty)` table with presence intervals; unchanged levels cost one row, eviction is `DELETE WHERE until_ms < cutoff`, and gap semantics are explicit (extend if qty unchanged, else close+new). → **M** → medium (new table + writer, old path kept). Biggest storage/complexity win; makes multi-hour DOM history affordable.
3. **Fixed ring + dirty-column render protocol** (`scene/depth_grid.rs:248-281, 854-889, 892-925`) → OFAP recomputes and re-ships snapshots; a power-of-two ring with clear-newest-column, copy-previous-column-forward for gaps, zero rows absent from the current column (kills stale walls), and column-granular payloads gives constant-cost live updates. Also makes `max_columns 900` a *view* cap rather than a data cap. → **M-L** → medium; keep the existing snapshot path as fallback.
4. **Retention horizon derived from the buffer** (`src/widget/chart/heatmap.rs:585-612`) → `keep_ms = ring_cols * bucket_ms`, pruned on the 64-update cadence, so derived depth history never exceeds what can be painted; the 7-day SQLite window then stays a raw-tick/data-compliance concern only. → **S** → low.
5. **Quantised u32 grid + column/block maxima** (`depth_grid.rs:209-236, 690-740`) → scale-compression at ingest plus cached per-column and per-16-row maxima removes per-frame max scans in the JS renderer and stabilises colour scaling. → **S-M** → low.
6. **Request lifecycle state machine** (`fetcher.rs:93-169`) → `Pending/Completed/NoData/Failed(cooldown 30 s)` keyed on exact ranges, `has_pending` before issuing, and *never* retrying a confirmed-empty range. → **S** → low; directly replaces ad-hoc in-flight flags, prevents retry storms on flaky feeds.
7. **`/trades.arrow` contract as an OFAP-side endpoint** (`client.rs:83-236`, README:48-67) → expose the app's SQLite ticks over one documented Arrow IPC schema (`ts,price,qty,is_sell`) with the same query params; desktop/dashboard/CLI all get one protocol, and the same client code can consume third-party servers (fallback chain: server → Binance mirror → none). → **S-M** → low.
8. **Binance daily-zip backfill** (`exchange/.../binance/fetch.rs:587-739`) → daily `aggTrades` zips cache-first with >4-day pruning, intraday REST for today, dispatch at UTC midnight, fallback to intraday-only on failure. → **S** → low (Binance only). Caveat to copy deliberately: the app should treat downloaded zips as *cache*, not as the source of truth (its 7-day DB is).
9. **Volume-profile window as an explicit option** (`chart/heatmap.rs:677-682, 954-966`) → add `FixedWindow(n)` anchored to the **live** edge alongside the existing visible-range profile, plus the 4096-price-level draw cap. → **S** → low.
10. **Tolerant config schema + atomic writes + keychain secrets** (`util.rs:8-15`, `layout/pane.rs:31-88`, `lib.rs:39-111`, `config/network.rs:9-25`) → per-field `unwrap_or_default` on deserialise, keep deprecated variants and convert on load, tmp+rename+fsync writes, rename-corrupt-and-continue, secrets out of JSON into the OS credential store. → **S** → very low; makes beta→beta upgrades and corrupt-config recovery uneventful for `desktop/config_store.py`.
11. **Tick bars (if adopted): live-only, never persisted, never backfilled** (`aggr/ticks.rs:10-96,134-165`; `chart.rs:84-92`; `chart/kline.rs:458-460,705-710`) → count *trades* per bar, append-only fold, index-keyed x-axis, explicit "in-progress bar is ephemeral; no historical reconstruction; do not mix with time-windowed retention" policy. → **L** → high; the current DB/time-bucket design is fundamentally time-keyed. Recommend treating this as a separate mode with its own buffer rather than extending `data/candle_builder.py`.
12. **Engine guardrails worth adopting cheaply**: `MAX_GRID_LINES = 1000` cap on any grid generator (`chart/ticks.rs:5`), hard caps on expensive builds (4096 price rows / 4096 ticks, `chart/heatmap.rs:979-981`), side-aware rounding only for book bins and nearest-bin only for footprint (`kline.rs:184-206`), and dropping late snapshots at ingest rather than sorting later (`chart/heatmap.rs:164-169`, `depth_grid.rs:338-343`). → **S** → very low.

**Explicitly not worth porting:** their GPU texture/shader upload plumbing (pywebview+canvas has a different cost model), the multi-window/iced plumbing, and the tick-bar trade-fetch TODO path.
