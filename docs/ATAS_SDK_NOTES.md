# the reference layout SDK documentation — what it gave this build

`docs.atas.net` is the reference layout's technical documentation for custom indicator and strategy
development: the object model of the platform, how indicators receive and process
data, the rendering contract, and the heatmap indicator author guide. It is written
for C# authors shipping DLLs into the reference layout, so nothing transfers directly — but the
**architecture and the performance rules do**, and three of them were folded into
this build.

Source pages read for this pass:

- `md_DataFeedsCore_2Docs_2en_20000__Introduction.html` (index of the whole manual)
- `md_DataFeedsCore_2Docs_2en_20025__ReceivingProcessingData.html` (data callbacks, statistics provider)
- `md_DataFeedsCore_2Docs_2en_20030__IndicatorEvents.html` (trading events, `TradingManager`)
- `md_DataFeedsCore_2Docs_2en_20050__Dataseries.html` (data series types, price selection, object series)
- `md_DataFeedsCore_2Docs_2en_20125__Performance.html` (the performance contract)
- `md_Indicators_2Heatmap_2README.html` (heatmap indicator author guide, v2 API)

---

## 1. Performance guidance → measured fixes in `atlas/tapeflow.py`

The manual is blunt about the per-event path: *"the code inside it must be as
lightweight as possible"*, *"avoid allocations"*, *"do not recompute what has not
changed"*, *"draw only what is visible"*, *"call RedrawChart() sparingly"*.

Profiling our ingest path against that advice found 99% of the cost inside one
class. Measured with `scripts/profile_atlas.py` and `scripts/bench_atlas.py`:

| Hot spot | What it was doing | Fix |
|---|---|---|
| `TapeFlow.speed()` | sorted up to 600 keys and ran `statistics.mean/pstdev` per tick — those convert every element to an exact `Fraction` (~450 µs/tick) | plain float maths over the last 300 seconds in insertion order |
| `TapeFlow.big_threshold()` | sorted the whole 4,000-print ring per tick to take a quantile | rebuilt at most every 25 prints (`_THRESHOLD_EVERY`), which is the same threshold in practice |
| `TapeFlow._update_stop_run()` | rescanned the whole print ring per tick (~356 µs) | per-second aggregates `[first, last, lo, hi, volume, prints]` maintained on ingest; the detector reads ~4 buckets |
| second-bucket trimming | `sorted(dict)` per tick once the ring filled | evict in insertion order (dicts preserve it; the keys are seconds) |

**Result: 935 → 7,774 ticks/second** through the full five-analyser stack
(1,069 µs → 128.6 µs per tick), with all 89 tests green and identical detector
semantics (the second-bucket window is documented as second-granular).

## 2. Heatmap author guide → version-stamped payloads + repaint governor

The guide describes a front/back buffer with a **lease** for writers, a **Version**
the renderer compares per frame, and a strict rule that the render side only draws.
Both ideas are now in this build:

- **Backend** (`atlas/depthmap.py`): every ingest bumps a `version`; `snapshot()`
  caches the built payload against `(version, columns, rows)` and returns a shallow
  copy so the API can still attach its own keys. Callers get `version` and `cached`
  in the payload, and `snapshot_builds` in stats.
  Measured: a cached poll costs **0.3 µs against 0.76 ms** to build — ~2,500×.
- **Frontend** (`desktop/ui/market-pressure.js`): `drawHeatmap` is wrapped so a
  payload with an unchanged version (and unchanged overlay flags and canvas size)
  **does not repaint**, and repaints are coalesced to a 400 ms frame budget. The
  counters live on the canvas tooltip — verified live: identical payloads produced
  `2 skipped`, and the title reports paints/skips/coalesced.

## 3. Reference indicators → Market Pressure panel

The guide's reference list names `HeatmapMarketPressureIndicator` (paired buy/sell
sub-panel) and `HeatmapCvdIndicator`. We had CVD but not the paired pressure view,
so the CVD view now carries a **Market pressure** card: buy above the midline, sell
below, delta line across it, plus window totals, share-of-volume and the time span.
It reads the per-bucket `buy`/`sell` volumes the CVD tracker already produces, and
redraws only when the series signature changes.

---

## What the SDK documentation covers that this build deliberately does not

| Area | Why not |
|---|---|
| Order/position/trade management (`TradingManager`, `Order`, `Position`, `MyTrade`) | this program is deliberately read-only: no broker connection, no keys, no orders. That is a design decision, not a missing feature. |
| Statistics provider (equity curve, historical trades) | it exposes *your account's* fills; we have no account. Our Performance view journals the app's own signals instead. |
| Custom indicator distribution / licensing (`IHeatmapIndicator` DLLs, access management) | the reference layout ships compiled DLLs with its own licensing. This project's extension model is plain Python modules under `orderflow_system/atlas/`. |
| Heatmap v2 API (`BeginUpdate` leases, typed series, sub-panel scalars) | the lease model exists because the reference layout renders on a separate native thread with lock-free readers. Our renderer is a browser canvas fed by JSON, so the *idea* (version + skip repaint) transfers; the API does not. |
| Chart drawing / mouse / keyboard hooks | nothing to port: the browser owns input and layout. |

## Where to look in the source

- Performance work: `orderflow_system/atlas/tapeflow.py` (`big_threshold`, `speed`,
  `_update_stop_run`), `scripts/bench_atlas.py`, `scripts/profile_atlas.py`
- Versioning/caching: `orderflow_system/atlas/depthmap.py` (`snapshot`,
  `_build_snapshot`), `orderflow_system/desktop/ui/market-pressure.js`
- Regression tests: `orderflow_system/test_atlas_analytics.py`
  (`test_heatmap_snapshot_is_version_stamped_and_cached`,
  `test_stop_run_aggregates_match_the_underlying_prints`,
  `test_stop_run_window_drops_prints_older_than_the_window`)


## Participants' intent (from the help site, not the SDK)

The video material on "what order flow analysis reveals" demonstrates the reference layout's
order-book reading: the Smart DOM ladder with its analytical columns, and the
**Liquidity Pressure** widget beside it. Those are user-facing features, so the
developer docs do not describe them — the help site does, and it is specific enough
to reimplement honestly.

**What transferred, exactly.**

| the reference layout | Ours |
|------|------|
| Weighted liquidity `Σ(Order Volume × e^(−Level Number / Weight Decay))` | Same formula, same defaults (10 levels, decay 3, 5-level minimum, 50-level maximum). Verified against the live ladder: an independent recomputation from `/api/orderbook` matched the module to six decimals. |
| Training period (default 5 min) with alerts disabled until it ends | Same, plus a 30-update floor — a "percentage of normal" before there is a normal is a made-up number. |
| Sliding window that keeps updating the maximum | Same, as a genuine window: a single spike stops pinning the scale once it ages out. |
| Threshold alerts per side (default 80%) | `intent_pressure` rule — 80% share of normal, 60 s cooldown per side. |
| Smart DOM "Trades" column: at bid / at ask / in-spread / through the touch | Tape-quality counters, with two honesty rules the reference layout does not need: prints are only judged against a book younger than 1.5 s, and a print within half a tick of the touch counts as *at* the touch, not as slippage. |
| Depth-change highlighting in the ladder | Per-level add/remove tallies per side (who is building, who is retreating). |

**What we added because the help site describes the widget but not the inference:**
absorption scoring (aggression that fails to move price, weighted higher when price
moves *against* the aggressor), pulled-size inference (a level that loses its size
without being traded, only when it was large relative to its neighbours and near
price), and trapped-side inference (a break beyond the prior range that is reclaimed
within a minute). The help site sells these as observations; publishing the scoring
is the difference between a read and a black box.

**Deliberately not copied.** the reference layout's widget is validated on CME futures with a real
15-minute chart and a real ladder. Bitcoin's top ten levels on Bybit are thin and
the tape is fast, so a pressure reading on crypto is a *relative* statement — which
is why the card says "of normal" rather than showing a raw dollar figure.
