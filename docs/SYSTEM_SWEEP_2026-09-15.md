# System sweep — ModFlow OrderFlow Analysis Suite

Directive: `Desktop/sweep.txt` (4-step protocol: interaction sweep → edge cases → optimisation →
structured output). Executed 2026-09-15 on Windows 11 against this working tree
(commit `b2ff4ee` + uncommitted local work). **Nothing was committed by this pass** — HEAD is
still `b2ff4ee`, all changes are on disk in the files named below.

Everything quoted here was measured on this machine: live Bybit BTCUSDT through a sandboxed
instance (`APPDATA` redirected, its own config + SQLite, port 8099 — your running app on 8080 was
not touched), plus synthetic matrices injected into the running engine to put the hot paths under
a realistic load (1440 bars × 200 levels × 4000 prints). Synthetic input is called out wherever
it is used; nothing here is inferred from reading alone.

---

## 0. The one-line verdict

The engine's two per-frame hot paths were 22× and 3.7× slower than they needed to be, **and the
three layers they feed — depth heatmap, execution sweeps, CVD ribbon — were never attached to
their canvases at all**, so the entire "Engine" view has been rendering the footprint matrix only.
Both are fixed and verified. The legacy Time & Sales strip rebuilt its whole table per print
(3.63 ms/print). Also fixed. What remains is backend: broadcast backpressure, order-book gap
detection, session semantics and unbounded tick retention — all documented with line numbers in
§4 rather than changed blind.

---

## 1. Architectural audit report

### 1.1 The prompt's frame vs this build (read this first)

The directive assumes a browser-native HFT terminal: Web Workers, `SharedArrayBuffer`,
`Float64Array` tapes, main-thread footprint maths. This build is a different animal, and the
audit has to be honest about that before it can be useful:

| Directive's question | This codebase | Where the risk actually is |
|---|---|---|
| Are heavy maths in a Web Worker? | **No workers exist** — `new Worker`/`postMessage`/`SharedArrayBuffer`: **0 occurrences** across all 35 UI modules | Maths live in Python (`atlas/`, `analytics/`, `signals/`) and reach the UI as REST/WS payloads. The main thread's job is display, not aggregation — so the mandate is satisfied architecturally, not by threads |
| Typed arrays for tick/DOM data? | **0 occurrences** of any typed array | Payloads are JSON object graphs (the depth matrix is ~48 k objects / 136 KB per poll — `atlas/depthmap.py:214`). That is a real parse + GC cost, and a flat `Float32Array` wire format is the right future step (§4 R6) — not a missing `Float64Array` today |
| Race between data and render thread? | Single-threaded JS + one asyncio loop | The genuine races/blocking are on the Python side: broadcast under a lock, buffer-not-cleared-on-error, no book gap detection (§1.2) |
| Canvas/WebGL loop optimised, rAF correct? | Yes in shape (one rAF loop, layered canvases, dirty flags, LOD, frame telemetry — `ofx.js`), **broken in wiring** | Fixed this pass (§2 B1/B2) |
| Drawing tools / crosshair / DOM ladder throttled? | Crosshair debounced through `intent.js` leases; the DOM ladder had a scroll fight with the user | Fixed (§2 B6) |

### 1.2 Data pipeline, ingest → UI

Verified by reading `data/bybit_feed.py`, `main.py`, `dashboard/websocket_manager.py`,
`atlas/depthmap.py`, `data/database.py`:

- **Ingest is pull-paced by analytics, with no lag/gap detection.** `async for raw_msg in ws:
  … await self._handle_message(msg)` → `await self.on_tick(...)` per print
  (`bybit_feed.py:89-98,130`). Bybit's cross-sequence `u` is used as a *timestamp*
  (`bybit_feed.py:142`) and never compared, so a dropped or reordered delta leaves the local book
  silently stale — the exact failure mode the directive asks about. Fix in §4 R3.
- **Reconnect/backoff is present and correct** (1 s → 30 s cap, `bybit_feed.py:50-63`); snapshot
  vs delta is handled (`:144-163`), and deltas before the first snapshot are dropped (`:160-161`)
  — deliberate, but it means a mid-session resync is never re-armed.
- **Broadcast path**: `WebSocketManager.broadcast()` serialises once per channel (good) and
  throttles per (channel, symbol) — tick 200 ms, orderbook 500 ms, stats 5 s, signals never
  (`websocket_manager.py:69-84`). Then it holds `self._lock` while awaiting `ws.send_text()` for
  **every** client in sequence (`:141-149`). One slow client therefore delays every other
  client's next broadcast, and there is no per-client queue, no drop policy and no write timeout:
  asyncio's transport buffer absorbs the difference. Fix in §4 R2.
- **Per-tick work on the loop**: analytics → throttled broadcast → bounded deque (500) → batch
  DB insert every 100 ticks (`main.py:465-490`). The deque bound is right; the batch buffer is
  cleared **after** the await (`:488-490`), so a persistent DB failure grows it without limit —
  one entry per tick, for the rest of the day.
- **Storage**: WAL + `busy_timeout` + `synchronous=NORMAL` (`database.py:29-32`) and correct
  indexes — the tape query plans as `SEARCH ticks USING INDEX idx_ticks_instrument_ts`
  (verified against your live DB, read-only). But: **5,804,801 tick rows / 547 MB already, and
  there is no retention, pruning or vacuum path anywhere** in `database.py`, `main.py` or
  `desktop/api.py`. At the observed ~52 prints/s across three symbols that is ≈4.5 M rows
  (~350 MB) per trading day. §4 R5.
- **Heatmap payload**: `atlas/depthmap.py:214` caches the matrix against
  `(version, shape, carry_forward, …)` (`:231`) so an unchanged poll is answered from cache —
  good. The payload itself is 136 KB of nested arrays for 48 k cells.
- **Legacy dashboard page** (`dashboard/static/app.js:51-54`): 1 s + 5 s REST polls plus a 5 s
  scanner loop, and it calls `series.setData()` with the whole candle series every second
  (`app.js:157`). The desktop UI (what you use) does not load that page; worth a deliberate
  keep-or-retire decision rather than leaving it as a slow path.

### 1.3 Rendering

`ofx.js` is genuinely well built: five layered canvases, dirty-flag scheduler, one rAF loop,
30 Hz heat cadence against a 500 ms decay constant, LOD ladder (text suppression → tick grouping
→ profile fallback), per-frame telemetry via `stats()`. Two systemic defects sat inside it:

- **Three of the five layers were never attached.** `OFX.attach(el('ofxBase'))` was the only
  canvas handed to the engine (`ofx-view.js:254` before the fix). `state.layers.heat`,
  `.live` and `.ribbon` stayed `null`, so `drawHeat`, `drawSweeps`/`drawHud` and `drawRibbon`
  never ran. Verified live: `layers: {heat: null, base: "ofxBase 996x283", live: null,
  ribbon: null}`, `ofxHeat` canvas 996×283 with **ink = 0**, while the stats strip advertised
  heat passes and sweep counts.
- **Dirty flags for those layers were never cleared**, because the clear sat after the
  `if (!canvas) continue` (`ofx.js`, `renderLayers`). Result: the loop repainted on *every*
  animation frame with nothing painted — a frame counter that reads healthy while the screen is
  static (measured: 12144 frames, `heatPasses: 0`).

The cost of the missing wiring was invisible until it was measured: with the layers attached
temporarily (before any optimisation) one forced frame cost **9.58 ms**, of which the heat pass
was **8.31 ms** at 29 929 cells, and the sweep layer **29.93 ms** at 4000 prints × 1440 bars.
Wiring the layers without fixing the maths would have replaced "nothing drawn" with "sustained
dropped frames". Both were fixed together (§2).

### 1.4 Interaction vs the live feed

The intent layer is real and correct: `intent.js` leases a surface from markup
(`data-surface="ofx"`), defers view-moving updates with `deferKeyed`, coalesces writes with
`queueWrite`, and never touches the socket or the engine (its own selftest asserts the contract —
`intent.selftest.js`, 7 ok). The Engine view's poller honours it (`ofx-view.js:296`), the
Trackers poller defers per key (`atlas-v2.js:286-291`). The legs that are *not* arbitrated are
the two legacy widgets fed straight off the WS/5 s poll — and that is where the user-visible
interaction bug was: `OrderbookLadder._render()` called `scrollIntoView({behavior:'smooth'})`
on **every** throttled repaint (10/s), queuing scroll animations against each other and dragging
the ladder back under a hand-scroll. Fixed (§2 B6).

---

## 2. Critical bug fixes (applied, with evidence)

### B1 — Engine layers never attached: heatmap, sweeps, HUD and CVD ribbon could not render
*`ofx-view.js:254-263`.* The view now hands over all three canvases before `OFX.resize()`.
Evidence after the fix (fresh tab, cache disabled, live feed): `layers: {heat:"ofxHeat",
base:"ofxBase", live:"ofxLive", ribbon:"ofxRibbon"}`, dirty flags clearing, `heatPasses` tracking
at ~30 Hz, and canvas ink proof — `ofxHeat 17888-27404`, `ofxBase 17856-44432`,
`ofxRibbon 6651-9915` (sampled over the full canvas).

### B2 — A missing canvas kept its layer dirty for ever
*`ofx.js` `renderLayers`.* The flag is now cleared whether or not a canvas is attached, so a
layer that cannot paint no longer pins the loop at display rate (and the frame counter no longer
reads healthy while nothing is drawn).

### B3 — Sweep layer: O(prints × bars) per repaint → O(log n)
*`ofx.js:306` (`math.barIndex`), `ofx.js:720` (`drawSweeps`).* `bars.find(...)` + `bars.indexOf(bar)`
per print became one binary search. Same 1440-bar × 4000-print load, same 4000 matches:

| | before | after |
|---|---|---|
| live-layer repaint | **29.93 ms** | **1.34 ms** (22×) |

New selftest cases pin the semantics (exact-open ownership, out-of-range refusal, agreement with
a linear scan over 1440 bars).

### B4 — Heat pass: per-cell colour strings → column index + palette LUT
*`ofx.js:324` (`math.heatColumns`), `:341` (`math.heatPalette`), `:478` (`heatPaletteFor`),
`:492` (`drawHeat`).* Two changes: the matrix is indexed by column once per payload, so the pass
touches visible columns only (binary search for the visible range); and every
(density bucket, alpha bucket) colour is pre-rendered into one rgba string table, so a cell costs
an index instead of `heatColor` + a template string.

| | before | after |
|---|---|---|
| heat pass | **8.31 ms** @ 29 929 cells (0.278 µs/cell) | **3.58 ms** @ 48 400 cells (0.074 µs/cell) |

Behaviour preserved: live cells stamp `alpha=0.92`, `seen`, `peak` and (new) `lastSize`, and
decayed cells keep the colour of the size that was there while the alpha decays exponentially.
Comparison is quantised (64 density × 32 alpha buckets) and the selftest pins the table.

### B5 — Time & Sales: full table rebuild per print
*`tape.js` (live path rewritten).* Was: `unshift` + `slice` (new array per print), filter + map +
`innerHTML` for up to 50 rows, `toLocaleTimeString` per row per render, `scrollTop = 0`.
Now: one row in, one row out (`_prependRows`/`_trimRows`), the clock time formatted once per
second and cached (`_timeText`), and `addTrades()` inserts a whole batch in one pass.
Measured head-to-head against the pre-fix implementation, identical input, production config
(`maxTrades 100`, `displayTrades 50`), both rendering 50 rows and holding 100 trades:

| | before | after |
|---|---|---|
| per print (`addTrade`) | **3.628 ms** | **0.284 ms** (12.8×) |
| 120-row view open (`addTrades`) | **237.3 ms** | **7.1 ms** (33×) |

Filters, big-trade tagging, cumulative volume and the auto-scroll toggle behave as before
(verified: same row count, same trade count, footer totals update).

### B6 — DOM ladder: no sizes at all, NaN footer, and a scroll fight
*`orderbook.js:91` (`_levels`), `:326` (`_scrollToCurrentPrice`).* The engine's REST payload sends
`{price, quantity}` (`dashboard/app.py:825,829`) while the ladder read `.size` — so against the
live feed every level rendered without a size, every bar was 0 px wide and the footer printed
`NaN`/`NaN` (verified live: `bidTotal: "NaN"`). The ladder now normalises `size|quantity` (and
`[price, size]` arrays) and drops non-finite deltas. Verified live after the fix: rows read
`77211.0 0.0030`, `77210.0 0.523`, footer `Bid 2 / Ask 3`, ratio `0.66x`. The scroll now runs
once per *price change* with `behavior:'auto'` instead of once per repaint with smooth scrolling.

### B7 — Sub-unit sizes displayed as `0`
*`tape.js` `_formatSize`, `orderbook.js` `_formatSize`.* `Math.round(size)` turned every crypto
print (0.001–0.15 observed) into `0` on the tape and every book level into `0`. Values below 1
now show 3 decimals / 2 significant digits. Verified live: tape rows now read `0.040` and
`0.0010`; the ladder reads `0.0030`.

### Housekeeping
- `state.ribbonPath` was only reset inside the visible-bar loop, so an empty viewport kept the
  previous viewport's coordinates (`ofx.js` `drawRibbon`) — reset moved before the loop.
- `tape.js` carried `this.paused = false`, never read anywhere in the tree — removed.

---

## 3. Optimised code modules

| Module | What it is now | Why (the number that forced it) |
|---|---|---|
| `desktop/ui/ofx.js` | `math.barIndex` (binary search), `math.heatColumns` (column index), `math.heatPalette` (colour table), `heatPaletteFor` (cached per scale+ramp), `drawHeat` column-culled, `drawSweeps` O(log n), dirty flags always cleared, ribbon path reset | 29.93 ms → 1.34 ms per sweep repaint; 0.278 → 0.074 µs per heat cell |
| `desktop/ui/ofx-view.js` | attaches `ofxHeat`, `ofxLive`, `ofxRibbon` before `OFX.resize()` | three layers had no canvas: heatmap/sweeps/HUD/ribbon could not draw |
| `desktop/ui/ofx.selftest.js` | +14 checks (bar lookup semantics, column index, palette table/index bounds) → 94 ok | the maths contract is the gate `test_ofx.py` runs |
| `dashboard/static/tape.js` | row-in/row-out live path, per-second time cache, batched `addTrades`, sub-unit sizes, dead flag removed | 3.628 → 0.284 ms per print; 237 → 7.1 ms for the 120-row load |
| `dashboard/static/orderbook.js` | level-shape normaliser (`size|quantity`), finite-number guards, one scroll per price change, sub-unit sizes | live payload key mismatch: no sizes, NaN footer |

Still not optimal, and known:
- The heat pass is 3.58 ms at 48 k cells every 33 ms (~11 % of one core while the Engine view is
  open). Next win is an incremental decay pass (only cells whose alpha actually moved), §4 R6.
- The heat payload is 136 KB of objects; a `Float32Array` + column/price header would cut parse
  and GC. Wire-format change, so it is on the roadmap, not in this pass.
- Crosshair `hover()` recomputes imbalance for one bar and walks the price axis: measured
  **0.12 ms** per call at 1440 bars — not material today, revisit at 10 k bars.

---

## 4. Implementation roadmap

Sequenced, each step ending in a gate whose output is the evidence. Nothing below has been
changed; the line numbers are where the work lands.

**R1 — Relaunch and look (5 minutes, yours).** The pywebview window keeps the JavaScript it
loaded, so the fixes only appear after a restart of the app. Expect: the Engine view gains the
depth heatmap behind the footprint, sweep bubbles and the crosshair reference line, and the
VOL/DELTA/CVD ribbon underneath; the Depth ladder gains sizes; the tape prints sub-unit sizes.
Gate: the Engine view's own stats line stops reading `heatPasses 0`, and `ofxHeat`/`ofxRibbon`
have ink.

**R2 — Broadcast backpressure (backend).** Per-connection bounded queue with drop-oldest for
throttleable channels (`tick`, `orderbook`), never drop `signal`; never hold `_lock` across
`send_text`; a write timeout that marks a client dead. Gate: a pytest driving one deliberately
slow client while a fast client receives a fixed number of messages, plus a live two-client
check. Files: `dashboard/websocket_manager.py:104-152`.

**R3 — Order-book integrity.** Track Bybit's `u`/`seq` (`data/bybit_feed.py:142`) and on a gap
mark the book stale and re-subscribe for a fresh snapshot; announce it in the view's status line
rather than silently trading a stale book. Gate: a test feeding deliberately gapped/reordered
deltas asserting the book is marked stale and re-seeded.

**R4 — Session model.** `session_date` is UTC-today with a rolling 24 h profile
(`main.py:682-690`), so at the UTC boundary "today's" value area mixes two sessions, and RTH/ETH
is not modelled at all (matters for Alpaca/MT5 instruments, not for crypto). Make the session
boundary a config value with a UTC default, and compute profiles per session. Gate: unit tests on
the session-window function + a VP comparison across a simulated boundary.

**R5 — Storage retention.** No pruning exists; 5.8 M rows / 547 MB today, ~4.5 M rows/day at the
current rate. Add a retention job (age- or size-based) with incremental vacuum, and surface the
DB size in the Logs view. Gate: run it, read back row counts and file size before/after.

**R6 — Engine next round.** Incremental heat decay; `Float32Array` heat wire format; coalesce
`hover()` into the rAF tick. Gate: `ofx.stats()` p95 under the same synthetic load must improve
on today's numbers (heat 3.58 ms / live 1.34 ms).

**R7 — Legacy dashboard page decision.** `dashboard/static/app.js` polls REST at 1 s/5 s and
rewrites whole series per tick. Either retire that page (the desktop UI supersedes it) or give it
the same incremental treatment as the tape. Gate: whichever is chosen, the page either 404s in
the desktop shell's nav or its poll cadence drops to a documented number.

**Build note.** `dist/` still contains the pre-fix copies of these modules; the frozen build will
keep showing the old behaviour until `scripts/build_exe.py` is re-run.

---

## 5. Verification log

Run in this order, on this machine, after the edits:

```
node orderflow_system/desktop/ui/ofx.selftest.js          -> ofx selftest: 94 ok, 0 failed
node orderflow_system/desktop/ui/intent.selftest.js       -> 7 ok, 0 failed
node orderflow_system/desktop/ui/study-api.selftest.js    -> 45 ok, 0 failed
node orderflow_system/desktop/ui/search-ops.selftest.js   -> all checks passed
.venv/Scripts/python.exe scripts/audit_ui_refs.py         -> AUDIT CLEAN (35 modules parse)
.venv/Scripts/python.exe -m pytest orderflow_system -q    -> 311 passed, 2 skipped (11.3 s)
node --check on every touched module                      -> parses
```

Live verification: sandboxed headless instance (own config dir, port 8099) with the real Bybit
BTCUSDT feed; Engine, Depth and Time & Sales views driven in a real browser with cache disabled;
layer attachment, canvas ink, tape rows/sizes, ladder sizes and totals read back from the DOM;
`client error:` lines in the sandbox log after the edits: **none**.

Full-suite honesty note: five full pytest runs on the finished tree gave 313 passed / 2 skipped
three times and one failure of `test_platforms.py::test_probe_handshake_against_a_spec_conformant_server`
in the other two (a loopback socket-timing mock with a 2.0 s message window against a 3.0 s connect
timeout; it passes 3/3 alone, in its own file, and as a single test — 6 isolated runs, 0 failures).
It is the known flake documented in `docs/AI_AGENT_BUILD_PROMPT.md`; the baseline line there was
stale (297) and now reads 313. Two failures in five runs is frequent enough that hardening the mock
(a longer window, or a readiness handshake instead of a fixed `seconds=2.0`) is worth doing —
`SESSION_HANDOFF.md` already carries it as an open item.

**Not verified (stated plainly):**
- Nothing was validated in your *running* window — it still executes the pre-edit JavaScript
  (R1: relaunch).
- The frozen `dist/` build was not rebuilt, so it still behaves the old way.
- The soak is short: 40 s windows with heap 2.81 → 2.91 MB and DOM nodes flat at 2863, plus
  ~40 minutes of earlier sessions with no growth trend. A 4-hour soak was not possible here
  (the browser harness daemon dies on long sessions); the 10-hour-day leak question is answered
  from code paths, not from a 10-hour run.
- MT5, Alpaca and the DTC platform/DTC bridge paths were read, not exercised (no feed credentials in
  the sandbox).
- The Python-side items in §4 R2–R5 are findings with line numbers, deliberately not applied:
  they change runtime behaviour of a live app and each needs its own gate.

### Addendum — the tape's scroll contract (found while verifying the scroll behaviour)

The recall note about "the tape's scroll position across a rebuild" was worth chasing: the rewrite
changed how rows arrive, and that exposed a defect underneath.

- **A capping tape can never be held by browser scroll anchoring.** With `overflow-anchor` left at
  `auto`, a wrapped `scrollTop` setter showed **no JavaScript writer at all** while the reader's
  offset marched 200 → 726 (max) in 25 s: anchoring compensates for rows inserted above, and because
  the tape removes one row at the bottom for every row it adds at the top, the height never grows, so
  the compensation accumulates until the strip hits the end of its scroll range. The widget now owns
  the offset (`tape.js` `_applyAnchoring` disables anchoring in both modes; `_afterAppend(added)`
  writes `0` when pinned and `+= added` when the reader has scrolled away).
- **Verified after the change**: pinned mode holds `scrollTop 0` for 20 s of prints with no chip;
  reader mode holds the *line the reader is looking at* — the top-of-viewport row stayed identical
  (`16:49:10 77239.2 0.0`) across 7 s of incoming prints while the offset moved 144 → 312, which is
  the correct compensation. Reader mode cannot outlive the tape's own window (`displayTrades 50`,
  `maxTrades 100`): after roughly 18 prints at this rate the strip reaches its end and everything the
  reader was on has been trimmed — that is a sizing property of the tape, not a scroll bug.
- **Still not right, and stated as such**: the per-strip "holding" chip does **not** appear for the
  tape. `OFAPSTRIPS.state` reports `pending: 1`, the chip element exists but stays
  `display: none` with empty text, so the only signal is the shell-level counter
  (`OFAPINTENT.status().strips` → the status cluster says one strip is holding). Two writers is also
  one too many: `strips.js` restores `want = lastTop` in an rAF while the widget compensates by the
  inserted height — both preserve the reader, but the offset ping-pongs between them. Reconcile to a
  single owner (strip holds, widget only pins) before calling this finished.

## 7. Delegated audits — what they found, what was verified, what was fixed

Three parallel read-throughs (backend pipeline; ui.js/atlas.js/heatmap-pro.js; the remaining UI
modules) were run alongside this pass. Their reports are self-reports, so every claim below was
re-checked against the code or the live instance before acting. Split into outcomes:

### Verified and fixed in this pass

| Finding | Evidence | Fix |
|---|---|---|
| `intent.js` loaded twice — the arbiter IIFE ran twice (two `OFAPINTENT` instances, two 1500 ms flush timers, doubled capture-phase listeners). `atlas-v2.js` executes *before* the eager tag is parsed, so its injector guard saw nothing and injected a second copy. | live: `document.querySelectorAll('script[src*="intent.js"]').length === 2` | eager tag moved above `atlas-v2.js` (`index.html`) and carries `data-atlas-intent="1"`; verified live: **1** module, `frozen:false` |
| The pause registry killed the Engine view's poll for the rest of the session: `register(id, () => load())` replaced an interval that pause had already cleared, and `ofxInit` is `booted`-gated, so it never came back. | `pause.js:41-43` + `ofx-view.js:307`; live: 0 `/api/footprint` fetches after a pause/resume cycle | `ofx-view.js` registers a `startPolling` that rebuilds the interval and re-registers; `pause.js` now keeps a `starters` set, empties dead ids on pause, iterates snapshots (a restart callback registers its new id), and exports `unregister`. Verified live: 30 fetches/10 s visible → **0** while paused → 25/9 s after resume |
| Two shell pollers ignored the pause control: `/api/control/engine/status` every 2 s plus a second timer hitting the same endpoint every 3 s, both running behind a "updates held" chip. | `ui.js:129-137`; live: 13 status fetches in 9 s while paused | one restartable status poll that returns early on `OFAP_PAUSED`/`anyHeld()`, and `OFAPINTENT.setFeed` fed from the payload it already fetched. Verified live: **0** fetches in 9 s paused, tick chip now reads a real rate (`{ticks: 2821, rate: 8}` — the old code read a `ticks` field the payload does not have, so the rate was always 0) |
| Bybit feed leaked every tick: `_tick_buffer` grew one entry per trade and its only drain (`flush_tick_buffer`) had **no caller anywhere in the repo**. | `bybit_feed.py:44,127,205`; grep repo-wide: no consumer | buffer, per-trade append and the dead flush method removed. ~136 bytes/tick measured (`sizeof(Tick)` 72 + trade-id string) at the observed ~52 ticks/s ≈ **25 MB/hour, ~250 MB per 10-hour day** |
| Volume profiles accreted per rebuild and were read back unordered: one session had **81 rows**, so `get_volume_profiles(days=5)` returned five copies of one day and every "last 5 sessions" level was one session repeated. | live DB (read-only): `(BTCUSDT, 2026-09-14, 81)`, `(ETHUSDT, …, 36)`; `database.py:204` plain INSERT, `days` used as a row LIMIT | rebuild deletes its `(instrument, session_date)` then inserts; the read takes `MAX(id)` per session before the limit. New test `test_volume_profiles.py` (2 tests) pins both — suite 311 → **313 passed** |

### Verified, not changed (each needs its own gate — added to the roadmap)

- **MT5 blocking calls in the async loop**: `mt5_feed.py:281` `copy_ticks_from(...)` and `:340`
  `market_book_get(...)` are synchronous C calls executed on the event loop every poll cycle, and
  `start()` abandons the feed forever if the first `initialize()` fails (`:86`). Windows-only path.
- **MT5 tick loss is real**: the poll caps at 1000 ticks but always advances the watermark to the
  newest fetched tick (`:332`), so a burst beyond the cap is silently dropped; dedupe is by
  millisecond (`:289`), and `volume = 1.0` is substituted when the broker sends no volume (`:318`).
- **Bybit sequence/gap**: `u` is used as a timestamp (`:142`) and deltas are applied uncompared
  (`:162`) — already roadmap R3, now with the delegated confirmation.
- **Draw-path costs in the *atlas* heatmap** (`atlas.js`): a sorted 48 k-value copy per repaint
  before the server's `scale_max` is consulted (`:59-64`), a linear price-axis scan per event
  (`:107`), and a `fill()`/`stroke()` pair per lit cell (`:86`) — each on a 5 s cadence.
- **`heatmap-pro.js` mousemove**: 4-5 `getBoundingClientRect`/`geom()` calls, an `innerHTML`
  tooltip rewrite and a full overlay redraw per mouse event with no rAF throttle (`:437`) — the
  same class of defect fixed in the tape, on the heatmap overlay.
- **`heatmap-pro.js` pulls always pass `force=true`** (`:378, 390, 555`), so its own
  `held('heatmap')` deferral and re-entrancy guard can never fire.
- **Timers that ignore the pause/arbiter apart from the two fixed above**: `search.js:1000`
  (500 ms palette poll), `vwap.js:206` (chart overlays while `held('chart')`), `scanner.js:185`,
  `alpaca-card.js:389/422`, `guide.js:1787/2186`, `strips.js:206`. `pause.js` now has
  `unregister` and a correct restart contract, so wiring these is a one-liner each.
- **`strips.js` guard map is never evicted** (`:81`) — a replaced scroller keeps its observer,
  listeners and detached nodes. Low frequency here (the tape body persists), but real.
- **`overview` and `logs` sections carry no `data-surface`** (`index.html:84, 676`), so no lease
  can ever be held on them while their 2 s / 3 s rebuilds replace `innerHTML` under the user's
  cursor (and destroy text selection).
- **An O(n) lookup per crosshair move in the studies path**: `studies.js:266` linear `findIndex`
  over bars plus `study-api.js:375` linear point search per plot, with a full Data-Box rebuild per
  event. Not material at today's bar counts; the same shape of fix as the sweep layer.

### Reported but not reproducible here

- `atlas.js:534` `A.liveTicks++` — incremented per detection, never read (dead counter).
- `ui.js:1047` `window.addEventListener('resize', () => { S.vpLines = S.vpLines; })` — a no-op
  resize listener; the real path is `scale.js`'s `ofap:relayout`, which `ui.js` does not listen to.
- `atlas.js:603` relayout redraws only the heatmap, so `cvdCanvas` and `frameCanvas` stay blank
  after a resize until the next 5 s poll (confirms the standing "re-fit clears the canvas" pitfall).

## 8. Appendix — how to reproduce the numbers
Sandbox instance (does not touch your install):

```bash
cd C:/Users/Moddy/OrderFlow-Analysis-Pro
APPDATA="C:/Users/Moddy/AppData/Local/Temp/ofap_sweep" .venv/Scripts/python.exe \
    -m orderflow_system.desktop --headless --port 8099
curl -X POST http://127.0.0.1:8099/api/control/engine/start -H 'Content-Type: application/json' -d '{}'
```

Synthetic load generator + timings (paste into the page console / a CDP harness, with
`window.OFAP_PAUSED = true` so the view's own 2.5 s poll does not overwrite it):

```js
const mk = (nBars, nLevels, nPrints) => { /* bars, levelsByTime, prints as in §1.3 */ };
const d = mk(1440, 200, 4000); OFX.setData(d);
const time = (f, n) => { const t0 = performance.now(); for (let i = 0; i < n; i++) f(); return (performance.now() - t0) / n; };
const live = () => { const s = OFX.state; s.dirty.heat = s.dirty.base = s.dirty.ribbon = false; s.dirty.live = true; OFX.renderLayers(false); };
live(); console.log('live ms', time(live, 5));       // 1.34 after, 29.93 before
const heat = () => { const s = OFX.state; s.dirty.live = s.dirty.base = s.dirty.ribbon = false; s.dirty.heat = true; OFX.renderLayers(false); };
heat(); console.log('heat ms', time(heat, 10));      // 3.58 after, 8.31 before
```

Canvas ink probe (the only reliable "it actually drew" assertion):

```js
const c = document.getElementById('ofxHeat'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
let ink = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 8) ink++; console.log(ink);
```

Edit scripts used by this pass (fail-loud, anchor-checked, kept outside the repo):
`C:/Users/Moddy/AppData/Local/Temp/ofap_edit_ofx.py`, `ofap_edit_pass2.py`, `ofap_edit_pass3.py`,
`ofap_edit_pass4.py`; DB probe `ofap_dbprobe.py`.


---

## 8. Engine view — bounded navigation and the interaction redesign (2026-09-15, later the same day)

His words: "design a system that prevents the user from scrolling outside draw distances ... look at the
output scenario on my screen ... redesign a much better interaction implementation for it calling on all
needed and available metrics ... consider all metric ingest and output variables in the final redo".

### 8.1 What the screen was actually showing

The engine's own stage was blank, and the stats line said 1600+ frames at 0.02 ms — a healthy frame
counter painting nothing. Measured in the live page (`OFX.state`, `OFX.stats()`):

| Reading | Value | Meaning |
|---|---|---|
| `bars` | 1 | one bar in the dataset |
| `offX` / `scaleX` | 180.85 / 52 | the transform fitted to a **200-bar history** |
| `offY` / `scaleY` | 99031.1 / 0.9732 | the price axis fitted to that history at **~99 000** |
| first bar x | `(0 - 180.85) * 52` = **-9404 px** | the single live bar was 9 404 px off the left edge |
| bar price vs window | 76 876-76 930 vs 99 031-99 323 | and ~22 000 points below the price window |

Cause, in order: the view polls `/api/footprint` every 2.5 s and replaces the dataset; the endpoint
serves stored history (200 bars at an older price level) and then live bars at the current level. Nothing
re-fitted or clamped the transform when the data changed, and the only clamp in the code ran inside the
drag handler — so a poll could park the view outside its own data permanently, with no indication.

### 8.2 Bounded navigation

- `math.viewLimits({bars, view, step})` (pure, selftested) returns hard bounds derived from the data:
  at least 4 bars and at most 400 bars visible (zoom limits from the stage width), a price-offset window
  that keeps the data band on screen at both clamp extremes, a zoom range bounded by the session range
  (at least ~8 rows of detail, never past 3x the session), and a left margin of
  `min(visible * 0.05, bars * 0.25)` with a one-bar floor.
- `clampView()` clamps in **two phases — zoom first, then offsets** — because the price-offset window is
  derived from `scaleY`. The forced test caught the one-phase version: with `scaleY` forced to 1e5 the
  offsets were bounded for that scale and ended up outside their own bound (`offY 77006.4` against
  `maxOffY 77000.6`).
- It is called from every mutation point: drag, both wheel branches, pinch, `resize()`, `applyLod()`,
  `snapToLive()`, `fitSession()` and `setData()`. Additions this pass: `fitSession()` (whole session in
  one action, bound to the new **fit** button and to a stage double-click) and the data-identity re-fit.
- **Data-identity re-fit**: `setData` compares a key of `symbol | bar count | first bar time | last bar
  time`. On a change it re-fits when the new band no longer overlaps the user's window, and otherwise
  leaves the user's window alone (a poll that merely appends bars must not move the screen). A last
  guard: if the clamps ever leave zero bars on screen, the view re-fits and increments
  `stats().recovered` — the blank stage is now impossible without a visible reason.

Forced verification (live page, synthetic data, `OFAP_PAUSED` during injection):

| Probe | Result |
|---|---|
| `offX/offY = 1e6`, `scaleX/scaleY = 1e5`, then `clampView()` | `within: true`, `scaleX 240` (max), 3 bars on screen |
| `offX/offY = -1e6`, `scaleX/scaleY = 1e-6`, then `clampView()` | `within: true`, `scaleX 2.49` (min), 6 bars on screen |
| 40 wheel-in + 40 shift-wheel-out + a 12 000 px drag fling | `inBounds: true`, 6 bars on screen, `recovered: 0` |
| the original blank-stage scenario (200 bars at ~99k, then 1 bar at ~77k) | bar lands at x 56, y 108 — on screen |

### 8.3 The redesign — ingest inventory first

Every field the four payloads carry, and where it now surfaces (all of it was already arriving; the view
used a fraction):

| Payload | Fields | Where it now goes |
|---|---|---|
| `/api/footprint` | `time, open, high, low, close, poc, levels[{price,bid,ask}]` | footprint matrix, ribbon, readout |
| `/api/footprint` (per bar) | `calc{volume, buy, sell, delta, rows, poc{price,volume,share_pct,delta}, max_bid, max_ask, extremes, imbalances[]}` | **previously dropped** — now the readout's bar block (POC share %, max bid/ask with sizes, level + imbalance counts) |
| `/api/candles`, `/api/delta` | `volume`, `delta` | VOL / DELTA / CVD ribbon |
| `/api/tape` | `time, price, size, side` | sweep bubbles, prints + sweep totals in the readout |
| `/api/atlas/heatmap` | `values[][]` (resting depth) | heat layer behind the matrix (now bar-aligned) |
| | `traded[][]` (executed volume) | **previously dropped** — drawn as flow bubbles (208 cells live) |
| | `best[]` (bid/ask per column) | **previously dropped** — one best-bid/ask point per bar (57 live) |
| | `events[]` (stack/pull) | **previously dropped** — chevrons, deduped per `(bar, price, kind)` |
| | `step, tick, scale_max, buckets, prices` | row height, LOD grouping, colour scale, column mapping |

- **Axes.** The engine drew no axis of any kind. The base pass now paints gridlines, a right-hand price
  rail (nice steps, tabular numerals), a bottom clock ruler with adaptive stride, the last-price tag on
  the live pass, and a dimmed "no data" band labelled `no bars after HH:MM:SS` wherever the view sits
  past the end of the dataset. Ink probe: rail 1 116 px, ruler 5 976 px, matrix 131 417 px.
- **Readout panel.** A DOM panel beside the stage (flex row: stage `flex:1` + panel `flex:0 0 238px`,
  20 rows live) with the full metric set; the cursor tag stays three lines and now prints the **local**
  clock (it printed ISO/UTC beside a local ruler before). The panel was an overlay in the first cut: the
  screenshot showed it covering the price rail and clipping its own values — moved out of the stage,
  values clipped with `min-width:0; overflow:hidden; text-overflow:ellipsis`.
- **Interaction legend** under the stage: wheel = price zoom, shift+wheel = time zoom, ctrl+wheel/pinch
  = price, drag = pan, double-click = fit session, `● live` = snap to newest, `P` = hold updates.

### 8.4 Bar-aligning the depth matrix (found from the redesign screenshot)

The heat layer smeared: the depth payload's columns are ~1 s buckets while the engine's X axis is one
column per **bar**, so ~60 sub-columns were each painted one bar-width wide over the same bar and bled
across their neighbours. `math.adaptHeat` now sums resting depth and executed volume per `(bar, price)`,
keeps one best-bid/ask point per bar and dedupes book events per `(bar, price, kind)`.

| Measure | Before | After |
|---|---|---|
| Heat cells drawn (live feed) | 48 400 | 593 |
| Frame cost (p95 with all layers) | 4.6 ms | **0.3 ms** |
| Cells per bar column | 147 columns smeared over 10 bars | `[5:12, 6:69, 7:207, 8:209, 9:96]` |

The selftest contract changed with it (`adaptHeat` rows 4 → 3 on the fixture, plus a new check that
sub-bar columns sum into one cell) — 106 → 109 checks.

### 8.5 Verified, and what is not

Gates after the pass: `node orderflow_system/desktop/ui/ofx.selftest.js` **109 ok / 0 failed**;
`.venv/Scripts/python.exe -m pytest orderflow_system -q` **313 passed / 2 skipped**;
`scripts/audit_ui_refs.py` **AUDIT CLEAN**; `node --check` on both engines; zero `client error:` lines in
the sandbox log for the whole pass; `OFX.stats()` telemetry cross-checked against DOM reads
(`#ofxReadout`, `#ofxStats`, `#ofxTip`).

Not verified / not changed, stated plainly:

- **The footprint endpoint publishes closed bars only.** Newest print measured at 1789464016 against a
  last bar ending 1789463940 (and 1789463985 against 1789463940 earlier): the newest drawn bar trails
  the live tape by 45-196 s, so `prints` and `sweep` read 0 for the forming bar and the view's own note
  ("tape and bars are from different feeds right now") is the honest answer. Drawing a live forming bar
  is a functional change to what the view shows and was left for his call.
- The two backend hardening items from §7 (broadcast lock / no send policy; MT5 blocking calls) remain
  unapplied by decision.
- The DTC handshake flake stands as documented (fails 2/5 full runs, passes 6/6 isolated).
- The readout's "depth here 0.0" on a level is real data (that price held no resting size in that bar),
  confirmed against the payload rather than assumed.

Edit scripts for this pass (fail-loud, anchor-checked, kept outside the repo):
`ofap_edit_pass11a.py` … `ofap_edit_pass11f.py`, docs `ofap_docs_pass11.py`.

Nothing committed — HEAD is still `b2ff4ee`.


---

## 9. Engine view — the legend system and cleaner bars (2026-09-15, same evening)

His words: "needed is a legend system for the engine layout ... clearer more intuitive bars and viewing
experience. The legend must be very specific but explains the layout and colouring and data collected
and output as an experienced orderflow analysis programme user would expect".

### 9.1 The bar rendering defect the ask uncovered

The footprint cells drew `String(Math.round(level.bid))`. On this instrument a resting size at a level is
typically 0.001-3 contracts, so the matrix was decorated with zeros and the numbers that carry
information were rounded into them. On the sampled bar, 16 of 86 levels were exactly 0 and most of the
rest were sub-unit — the display said "0" almost everywhere. Fixed with `math.fmtSize` (0.002 / 0.045 /
1.5 / 2.6 / 1.2k) and an empty half is now a faint dot, never a zero.

Bar framing was also absent: with no band and no separator, adjacent bars read as one slab. Each column
now carries an alternating band and a 1px right separator, and each bar hangs its own Δ and V above its
high (the per-column stats row an order-flow reader expects). The badge is drawn only where the column
can carry it — see 9.4 for the threshold bug that found.

### 9.2 One colour table, two readers

The colours the legend has to explain lived as ~20 scattered string literals. They are now
`math.theme` (17 keys: bid, ask, imBuy, imSell, poc, hvn, vaGround, vaEdge, sweepTwo, stackUp,
stackDown, pull, spread, vol, cvdBody, wick, grid, axisLabel, empty), read by the renderers **and** by
`OFX.legend()`. The selftest asserts that every legend swatch resolves to a colour the table owns — the
first run of that check failed on two swatches ("Bar range", "Price rail") that quoted literals from the
axes code, which is exactly the drift the table exists to prevent.

### 9.3 `OFX.legend()` and the panel

`OFX.legend()` returns the whole account, with live values:

| Section | Content |
|---|---|
| `layout` | 8 lines, top to bottom: depth heat → matrix (bid left half, ask right half, POC boxed, VA shaded, STACK bands) → sweeps → book events → spread line → rail/ruler → readout → ribbon |
| `entries` | 19 colour keys, each with what it means and the live value that governs it (ramp + scale + cells drawn, R, stack, VA %, C, bubble count, event marks, CVD divergence state, recoveries) |
| `data` | 10 fields: what arrives, from which endpoint, on what refresh, and what the engine derives from it (VA rows, imbalance ratio, zones, tick grouping, LOD, binary-search bar index) |
| `interactions` | 9: wheel / shift+wheel / ctrl+wheel / drag / double-click / fit / ● live / P / hover |
| `params`, `stats` | the live parameter block and the counters the panel quotes |

The panel (`#ofxLegendPanel`, three columns, collapsible and remembered in `localStorage`) renders
exactly that: measured 29 rows, 19 swatches, 9 interaction rows, 8 layout lines at a 1264px window
(columns 241 / 362 / 338 px). It refreshes on every fifth 1-second tick and skips while text is
selected, so the numbers move with the feed but a copy-out is never yanked.

### 9.4 Two bugs in my own additions, caught by probing rather than reading

- **The badge threshold exceeded the default column width.** `colW >= 56` never fires at the default
  zoom (measured `scaleX` 52), so the counter read `columnBadges: 0` and nothing was drawn. Lowered to
  48 with compact text (`Δ+12` / `V16`): 4 badges at the same zoom.
- **The legend's refresh timer never fired.** It was guarded on `view.init`, a flag that does not exist
  in this module — the panel rendered once and then held the values it was born with (the R change was
  invisible in it while `OFX.state.params.R` had moved). Now it rides the existing 1-second stats timer,
  every fifth tick, with no invented guard: verified `C = 2.50` in the panel after a sweep-constant
  change.

Both are the class of defect that reading the code does not surface, and both were found because the
verification asked the DOM and the telemetry what they held.

### 9.5 Verified

| Check | Result |
|---|---|
| cell text on live data | `0.002 / 0.045 / 2.6` pairs, `·` for an empty half |
| per-column badges | `columnBadges: 4` at `scaleX` 52, default zoom |
| legend DOM | 29 rows, 19 swatches, 9 keys, 8 layout lines, 3 columns; subtitle `BTCUSDT · R 4 · stack 3 · VA 70% · ramp classic · 19 colour keys · 10 data fields · 9 interactions` |
| legend follows params | `C = 2.50 · 0 bubbles` after the change; `sweepC` restored to 1.15 |
| collapse | `ofx-leg-collapsed` + `display: none`, restored on second click |
| frame cost with everything on | p95 0.3 ms, max 1.0 ms (`columnBadges: 4`, `flowEvents: 72`, `heatCells: 637`) |
| gates | selftest 119 ok / 0 failed, pytest 313 passed / 2 skipped, AUDIT CLEAN, both engines parse, 0 `client error:` lines |
| environment | sandbox on 8099 stopped; **his instance is also no longer listening — its log ends normally at 19:06:07 with routine signal lines and no traceback** (not my doing: my kill targeted the 8099 listener PID only) |

Nothing committed — HEAD is still `b2ff4ee`.


---

## 10. UI menu bar, sidebar and user-profile system — plan (2026-09-15, same evening)

Deliverable: `docs/UI_MENU_AND_PROFILES_PLAN.md` (plan for approval; nothing built from it yet).

Input: the 15 reference screenshots in `Desktop\New Folder` — the reference platform (no1 main window, no2 File menu, no3
Settings menu, no5 plugin manager + connection configuration, no6 drawing-tools dropdown, no7 Studies
configuration for Volume Dots) and the DTC platform (no8 File, no9 Chart, no10 Trade, no11 quote-window
context menu, no12 Window, no13 spreadsheet + Alerts submenu, no14 open-chart list, no15 Help) — plus the
the reference platform knowledge-base link supplied with `no7.jpg` (volume dots/bars: minimal displayed volume, dot size,
transparency, drawing type, 2D/3D, total vs delta, **clustering by Smart/time/volume/price/price+aggressor**,
apply-to-bars / inherit-from-bars), the reference platform's Open-The-Main-Window page (File/Connections/Settings/Help,
`Open user folder`, workspaces) and the DTC platform's Chartbooks/Global-Settings/Transfer pages (`the DTC platform4.config`
holds all global settings and is shareable *because account settings are not in it*; chartbooks hold
per-chart settings; `Make Backup`; versioned chartbook compatibility) and the reference platform's workspaces/templates
docs (auto-save every 5 minutes into a settings folder, templates, reset-folder).

Findings that shape the plan:

- The app has **no menu bar**: one ☰ overlay (`menu.js`) carries panels, connections, hotkeys and the
  existing *workspaces* feature. Workspaces persist via `/api/control/workspaces` into `config.json`,
  but the snapshot is `{view, ofx params + symbol, saved}` — three fields against a profile's worth.
- The config store already has the right bones: schema defaults + sanitisers in `desktop/config_store.py`,
  **atomic writes** (`*.json.tmp` then `os.replace`), and `POST /config/reset`.
- `/api/control/profiles/*` is **already taken** by order-flow volume profiles (rebuild/status), so the
  new feature is specified as UI "Profiles" on API `/api/control/user-profiles`.
- Credentials live in `config.json` (telegram, alpaca, mt5) — the plan excludes them from profiles and
  makes a test enforce it, following the conventional own shareability rule.

The plan specifies: the full menu tree (File / View / Chart / Data / Profiles / Tools / Help) with every
item mapped to an existing endpoint or flagged as new; the rail kept as primary navigation plus group
headers, a per-view Options dock and workspace tabs; a single `param-registry.js` so settings dialogs,
the palette and the menu bar all read one typed table; the profile system's scope table, file format
(`profiles/<name>.ofap.json` + index, schema-versioned with migrations), API surface, templates
(Scalper / Day trader / Swing / Research / Low-resource), autosave, backup/restore, import/export and
failure-mode tests; a five-phase build order where each phase ends in a gate; twelve flagged improvements
(command palette unification, hideable menu bar, Open-user-folder/log doors, recents, hotkey editor,
Performance submenu + safe mode, clustering as a settings family, chart templates separate from profiles,
diagnostics/About, per-view reset, tabs, recording); and six decisions needed before Phase 1.

Nothing committed; no code changed for this deliverable.


---

## 11. Menu bar — phases 0 and 1 built (2026-09-15, late evening)

Plan: `docs/UI_MENU_AND_PROFILES_PLAN.md`. His decisions: classic menu bar + toolbar; profiles carry
alerts + watchlist with an opt-out at save time; launch asks "restore last session?" with a "don't ask
again"; workspace tabs in phase 5. Naming (`/api/control/user-profiles`) and the no-credentials rule
stand as recommended.

### 11.1 Phase 0 — the display-variable registry (gate: nine new tests)

`orderflow_system/desktop/param_registry.py`: **81 variables in 17 groups across 14 views**, each with
a label, group, owning view, kind, bounds, unit, a one-line meaning and an `applies` flag
(`live`/`restart`). Values are **not duplicated** — the registry reads them from `config_store` at call
time. `GET /api/control/params` serves the table with live values and defaults.

`orderflow_system/test_param_registry.py` — the gate that matters is coverage: every numeric/boolean
leaf under the display roots (`ofx`, `atlas`, `risk`, `studies.data_box`, `search.default_view`) must be
registered, or the suite fails. That is what stops the app drifting back to "80 knobs, five controls".
Also asserted: unique paths, every path resolves, kinds match the config, numbers carry sane bounds,
descriptions are real, dump is JSON-safe, `applies` flags are known.

Gate run: 9 passed; full suite **313 → 322 passed / 2 skipped**.

### 11.2 Phase 1 — the menu bar (verified live)

`desktop/ui/menubar.js` + `#menuBar` markup + styles in `modules.css`, loaded after `ofx-view.js` and
registered in `audit_ui_refs.py`. File / View / Chart / Data / Profiles / Tools / Help, every item with
its accelerator, checkable items ticked, **unbuilt items disabled with the reason in the tooltip**
(never a mystery), submenus rendered inline and indented, Alt focuses the bar, arrows walk it, Enter
opens, Esc closes, and the whole bar hides under View ▸ Full screen (zen).

The Chart menu is the **active view's** menu and renders from `/api/control/params`; `Change…` opens an
inline editor (number + slider, checkbox, or select by kind) with the variable's meaning and its
`applies` flag; `Restore default` writes the store's own default.

Live verification (sandbox on 8099, cache disabled, fresh page):

| Probe | Result |
|---|---|
| bar renders | 7 titles, 7 slots, registry loaded |
| File menu | 15 items, 6 disabled with reasons; workspaces list honest ("no saved workspaces yet") |
| View menu | 32 items: the 22 rail views (with icons and 1-9 accelerators) + Legend/Rail/Status/zen toggles, ticks on the active ones |
| Data menu | live sources with **Bybit · active**; instruments, feed health, extra-stream switch |
| Chart menu (Engine) | groups Footprint + Depth heat, values inline (`Imbalance ratio (R) (x) = 4`, `Stacked run (levels) = 3`, `Value area = 0.7`) |
| **change a variable** | `Change…` → editor (value 4, bounds 1-20, "applies live") → set 5.5 → **engine R 5.5, note "Imbalance ratio (R) = 5.5", server `stored R = 5.5`** |
| **restore** | `Restore default (4)` → engine 4, **server `stored R = 4`** (the test value cleaned up) |
| keyboard | Alt → focus "File", ArrowRight → "View", Enter → opens the View menu |
| view switch | from the View menu → Chart menu re-points to the new view's own variables (`depth` → honest "depth has no registered display variables") |
| Profiles menu | every entry disabled with "phase 3/4 — the profile store" (no dead buttons) |

Three defects my own build introduced and the probes caught: the registry dump carried no `default`
(so "Restore default (undefined)" and the write was refused — the refusal message was correct, the data
was not); the click handler called `closeAll()` before `run()`, so `Change…` never opened its editor;
and `menubar.js` used a template-literal engine route
(`/api/control/engine/${action}`) that `audit_ui_refs.py` correctly reported as a **missing route** —
now three explicit constants.

New endpoints this phase: `POST /api/control/params` (registered paths only, kind-coerced, clamped by
the store, returns the adopted value), `POST /api/control/folder/open` (whitelisted
config/logs/exports — the reference platform's "Open user folder"), and `GET /api/control/params`.

Gates: **322 passed / 2 skipped**, ofx selftest 119 ok, `AUDIT CLEAN`, both engines `node --check`,
**0 `client error:` lines** for the whole pass, sandbox stopped and no app ports left. Nothing
committed — HEAD `b2ff4ee`, 51 files changed on disk in total across the day's work.

Next: phase 2 — per-view settings dialogs rendered from this registry (Engine first, then
Heatmap/Depth/Tape/Chart) with per-group restore, plus the Depth view's variables (it has none yet).


---

## 12. Menu dismissal, the indicator add-on pack, and the drawing layer (2026-09-15, night)

### 12.1 The menu now behaves like a top menu (his complaint, root-caused)

He reported: clicking off a dropdown left it open. Two causes, both real:

1. `closeAll()` cleared `.mb-menu.open` but the dropdown's visibility is driven by the **slot's**
   class (`.mb-slot.open .mb-menu`), so the menu stayed on screen no matter what cleared state.
2. Dismissal was a bubble-phase `click` on `document`, which any panel that stops propagation
   (canvas drags, the tape) can swallow.

Fixed: `closeAll()` clears the slot class, and dismissal is now a **capture-phase `mousedown`** on
`document` (plus `focusin`, window `blur`, any scroll and Tab), so the dropdown closes the moment
anything else is touched — as a native menu does.

Verified the way a user does it: click the matrix → `before true → after false`; click the rail →
closed; Escape → closed; Alt focuses `File`, ArrowRight moves to `View`, Escape closes; the matrix
still pans (the overlay is `pointer-events: none` while idle).

### 12.2 Indicator add-ons: the pack is installed and listed

The Studies system already had an install path — plain files in `desktop/ui/indicators/*.js`, listed
by `GET /api/control/studies/library`, executed by the browser against the suite's indicator contract
in `study-api.js`. Five modules now implement the indicators he asked for, each declaring
`pack: 'OrderFlow indicator pack'` / `version: '0.4.1'`:

| Module | What it computes | Notes |
|---|---|---|
| `adx.js` | Wilder ADX(14) with +DI / -DI | three plots, `threshold` param (default 25) and a DI-flip signal |
| `rsi.js` | Wilder RSI(14) | 70/30 marks, overbought/oversold colour and signal |
| `macd.js` | 12/26/9 | three plots (MACD, signal, histogram = MACD - signal), crossover signal |
| `obv.js` | cumulative signed volume | explicit prior-bar comparison, optional turning signal |
| `williams-r.js` | %R(14) | -100 at the period low to 0 at the high, edge signals |

`study-api.js` now reports `pack`/`version` in `registry.list()` and the Studies library row shows
them ("OrderFlow indicator pack v0.4.1"), so an installed module reads as an add-on rather than an
anonymous file. Live check in the sandbox: all five registered and listed beside the six built-ins
(11 modules served).

Gate: `orderflow_system/desktop/ui/indicators.selftest.js` — **25 checks, 0 failed** on first run:
RSI reads exactly 100 on a monotonic rise and 0 on a monotonic fall, OBV's arithmetic is asserted on
a mixed series, %R lands at the range edges, the MACD histogram equals MACD - signal to 1e-9 and
flips sign with the trend, and ADX stays inside 0-100 with the DI pair dominating on the correct side
in each direction. `test_indicators.py` shells that selftest and asserts every module carries the
add-on identity (suite **322 → 325 passed**).

### 12.3 The drawing layer

`desktop/ui/drawings.js` — a view-agnostic overlay cloned from the drawing workflow in his own
program, grounded in that program's settings file (`drawingSettings`: lineColorRgb, fillColorRgb,
lineWidth, lineStyle, alwaysHighlightPrice, alwaysHighlightTime) and its documented behaviour.

Eleven figures: select/edit, trend line, ray, horizontal line, vertical line, rectangle (extendable
left/right/both), ellipse, parallel channel (widen/narrow), **Fibonacci retracement** (0 · .236 ·
.382 · .5 · .618 · .786 · 1 with prices), text, and **measure** (Δprice, ticks, % move, minutes).
Behaviours: drag to draw, **Shift constrains lines/rays/channels to 45 degrees**, click to select
with endpoint handles, drag to move or reshape, **right-click for a context menu** (text, highlight
price, highlight time, extend, widen, duplicate, style cycle, delete), single-figure mode, hide all,
clear all, Delete/Esc keys, and **axis highlighting** — a drawing's time span marked on the time axis
and its price span on the price axis while hovered, permanently when the drawing asks.

Storage is **data space** (epoch seconds + price), never pixels: pan, zoom, bar-size change and view
switches cannot move a drawing. It persists per view+symbol through `GET/POST /api/control/drawings`
into the config, sanitised by `config_store` — kinds whitelisted, points finite, colours restricted to
hex/rgba, width 1-8, dashes enumerated, text ≤240 chars, 500 rows per slot, 64 slots. Sanitiser proof:
`width 99 → 8`, `dash 'wobbly' → solid`, `line 'javascript:alert(1)' → #4f8cff`, a bad row and a NaN
point dropped (3 rows in, 1 out).

It is mounted on the **Engine view** today (the adapter hands it `OFX.worldX/priceToY/xToIndex/
yToPrice`, so the integration is about 30 lines) and a **Drawings menu** joins the top bar: figures
with a tick on the active tool, modes, six line colours, and the view's own drawing list for
one-click selection. The adapter contract is documented in the module, so wiring the candle chart
(lightweight-charts, needs `timeToCoordinate`/`priceToCoordinate`) and the Heatmap view is the next
short step rather than a rewrite.

Live verification: the layer mounted (11 figure buttons + 3 modes, `pointer-events: none` when idle),
a gesture-drawn trend line landed at `t 1789393625.46 / p 98958.60 → t 1789393856.23 / p 98858.24` and
**persisted server-side** (`rows: 1`), single-figure mode returned the tool to Select after the
Fibonacci figure, right-click opened the six-item context menu, and the drawings survived a switch to
Overview and back (`line` + `fib` still there).

Gates: **325 passed / 2 skipped**, ofx selftest 119 ok, indicators selftest 25 ok, `AUDIT CLEAN`,
zero `client error:` lines for the whole pass, sandbox stopped, no app ports left. Nothing committed;
HEAD `b2ff4ee`. One defect of my own found by the live probe: `mountDrawings()` was defined but never
called from `ofxInit()` — the layer was absent until the call was wired.


---

## 13. Renamed to ModFlow OrderFlow Analysis Suite; third-party pointers stripped (2026-09-15, night)

His instruction: rename the program, remove references to the other platforms and any bloating
pointers to build helpers or similarities, and **functionality must not be affected**.

### 13.1 The rename

Replaced the display name `OrderFlow Analysis Pro` → **ModFlow OrderFlow Analysis Suite** in **30
files, 36 occurrences** (code, UI, docs, packaging metadata), and in the app chrome itself:

| Surface | Before → after | Verified by |
|---|---|---|
| Window / page title | `<title>ModFlow OrderFlow Analysis Suite</title>` | served page read back |
| Rail brand | mark `OF` → `MF`, name `OrderFlow` → `ModFlow`, sub `Analysis Pro` → `OrderFlow Analysis Suite` | same |
| Top-bar brand | `ModFlow` | same |
| Desktop launcher | window title + `description="ModFlow OrderFlow Analysis Suite — desktop app"` | file read |
| Frozen build | `APP_NAME = "ModFlowOrderFlowAnalysisSuite"` (exe + dist folder) | `scripts/build_exe.py` |
| Installer/packaging | `pyproject` description now names the suite (the old one credited a third party's methodology) | file read |

**Deliberately NOT renamed** (renaming them would break his install, and functionality outranks
cosmetics): the import package `orderflow_system`, the per-user config directory
`%APPDATA%\OrderFlowAnalysisPro`, the log and DB file names, the repo directory, and the internal
config key `platforms.sierra` (his saved DTC connection lives under it — renaming the key would
orphan the settings). The DTC route path was neutralised where it is safe
(`/platforms/bridge/dtc`, `/platforms/bridge/dtc/test`; the old `/platforms/sierra/dtc` no longer
exists).

### 13.2 The third-party strip

| Removed | Detail |
|---|---|
| Promo data module content | `platforms.py` had plan catalogues, vendor links and install detection (scanning for other programs' folders, reading their version files) — **all deleted**; the module keeps only `dtc_defaults()` and `suggested_symbols()`, with a neutral docstring |
| Promo API surface | `/api/control/platforms` now returns the DTC block + suggested symbols + one neutral note; `/api/control/platforms/open` (vendor URL opener, with its vendor host allow-list) is **deleted** — verified 404 |
| Promo UI | `platforms.js` rewritten (304 → ~150 lines) to one card: "External data bridge — DTC connection", the same fields and the same endpoints. No plans, no prices, no vendor links, no install detection |
| Reference documents | deleted: `docs/PLATFORM_BRIDGES.md`, `PLATFORM_INTEGRATION_PLAN.md`, `NINJATRADER_NOTES.md`, `TRADOVATE_STUDY_BRIDGE.md`, `ATAS_COMPARISON.md`, `ATAS_FEATURE_INTEGRATION.md` |
| Agent scratch | `.scratch/` (29 MB of harvested research pages and one-off scripts) deleted |
| Prose pointers | **77 files, 612 occurrences** reworded to neutral wording (the study contract is "this suite's contract"; a heat author guide is "the reference layout"; a convention is "the exchange convention"; other platforms are "the reference platform" / "the DTC platform") |
| Guide/help copy | the wizard's platform step and the Platforms help topic no longer name or link other programs |

The vendored chart library was left untouched on purpose: it is third-party code under its own
licence, and its header is not ours to edit.

### 13.3 Collateral damage the sweep caused, and the repairs

A phrase sweep of this size breaks things, and two classes did:

1. **A replacement landed inside a single-quoted JS string** in `test_studies.py`
   (`'ATR (the suite's indicator contract-shaped)'`) — an apostrophe inside a JS literal, which threw
   `Unexpected identifier 's'`. Repaired to `'ATR (contract-shaped)'`.
2. **Double articles**: bare token replacements mid-sentence produced "the the …" in 15 files
   (20 places). All repaired; a follow-up scan reports **no vendor product words left in our files**.

The nine catalogue/redirect/install tests in `test_platforms.py` were removed with the surfaces they
covered; the DTC protocol tests (encoding layout, handshake, refused logon, binary insistence,
garbage, no server, missing host, empty-credential defaults) all remain and pass.

### 13.4 Verified

**316 passed / 2 skipped** (the drop from 325 is exactly the nine deleted catalogue tests),
`AUDIT CLEAN`, every UI module and every Python file parses, indicators selftest 25 ok, ofx selftest
119 ok. Live: the sandbox boots (`healthz 200`), the served page carries the new title and brand,
`/api/control/platforms` returns the bridge-only payload, `/platforms/open` is **404**, and the
neutral DTC route answers **200**. Nothing committed — HEAD `b2ff4ee`.

---

## 14. Sierra Chart integration, rebuilt free-first with a plan toggle (2026-09-15, late)

His instruction: analyse the Sierra Chart trading/charting integration; streamline the wizard
instructions, payment-plan links, forwarding information and login setup; **emphasise the free plan**;
keep full transparency on paid plans; let the user run either plan and have the suite adjust when the
integration is loaded or toggled.

Rebuilt in the suite's own voice (last pass removed the old multi-vendor catalogue on his
instruction; this is the focused single-platform surface he then asked for):

| Piece | Detail |
|---|---|
| Workflow | six steps for the free path, seven for a paid one (the extra step is package activation): install → create the account → start on the free path (trial + delayed streaming feed) → enable the DTC protocol server (JSON) → point the suite at it → load it and pick the plan. Every step carries the vendor link that completes it |
| Links | 12, all https on the vendor host, each with a one-line reason: download, trial contents, delayed feed, create account, control panel (login), activate/change package, pricing, add credit, DTC protocol, setup, support board, futures-data explainer |
| Plans | free first (`0`, "no payment"), then the published tiers — Package 3 `26`, Package 5 `36`, Package 10 `36`, Package 11 `46`, Package 12 `56` USD/month — quoted **as published 8 September 2026** with the source link beside them, plus the caveats that exchange data fees are separate, multi-month purchases are discounted on their side, and there is no one-time purchase |
| Toggle | "Load into my workflow" plus a plan selector. The stored facts live in the config (`platforms.sierra.plan`, `.integrated`, sanitised with a free fallback) and drive the workflow, the data-quality wording ("delayed data — timestamps are honest about the delay" vs "real-time data — exchange fees already apply"), the status line, and a banner when a base package cannot reach external feeds |
| Install | detection of a local install (paths plus the build-number file only; never account files, licence keys or logs) — live on this machine: found at `C:\SierraChart`, build 2950, DTC folder present |

Verified live: payload carries plans/links/workflow/installs; `POST /platforms/plan {plan:"p10",
integrated:true}` grew the workflow 6 → 7 steps and switched the data-quality line to real-time, then
returned cleanly to free; the link opener refuses anything not on the vendor allow-list
(`https://example.com/evil` → "host not on the allow-list"). New tests:
`test_sierra_integration.py` — 8 checks (free first, published dates, exchange-fee caveat present,
workflow adapts per plan, unknown plan falls back to free, links allow-listed, opener refuses the
rest, DTC defaults carry the plan fields). Suite **324 passed / 2 skipped**, `AUDIT CLEAN`. The audit
caught three slips while building this (an unrestored route, a path mismatch, a key-tuple miss) — all
fixed. One honesty fix: the adaptation claims the status bar names the plan, so `setStatusNote` is now
a global as well as a module function.

---

## 15. dxFeed-style terminal shell + Quantower parity — plan (2026-09-15, late)

Deliverable: `docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md` (plan for approval; no code changed for it).

His brief: investigate a novel approach to a complete UI switch — a multi-tab, multi-screen-aware
terminal mode a power user can toggle into, dxFeed-style in look and feel, with the existing
functionality untouched; a Top Bar integration for the switch; and Quantower account/login/help
integration built with the same diligence as the Sierra surface.

What the investigation concluded (and why it is cheap rather than a rewrite): every panel in this
suite is already a `<section class="view">` that self-registers and boots from its own
`MutationObserver`. A shell that **re-parents** those sections into widget frames preserves their DOM
and listeners, so Classic and Terminal are two arrangements of one set of panels, and switching back
is a detach, not a rebuild. The plan specifies the shell host (`shell.js`), a sanitised layout store
(named layouts, tabs, per-screen profiles, export/import) beside workspaces and drawings in the
config, widget chrome (drag/resize/maximise/float/settings), a tab strip, link groups for
symbol/timeframe, and a **widget channel bus** — one subscription per (endpoint, params) with
refcounts, so twelve widgets on one symbol cost one poll instead of twelve. New widgets (Watchlist,
News, Fundamentals, Options/Greeks) are additive; the options panel says plainly when no Greeks feed
is configured, because dxFeed is a data vendor rather than a dependency.

Quantower parity: the same structure that works for Sierra (free-first workflow, account/login links,
published plans carrying their read-date and source link, separate-data-fee caveat, install detection,
plan/integrated toggle driving the suite's wording). One dependency is called out rather than guessed:
the Quantower licence tiers and prices must be read from their own pages in a fresh pass before that
surface ships — the page reached during this investigation 404'd, and printing unread prices is the
exact thing `test_sierra_integration.py` exists to prevent.

Six phases with gates; the round-trip gate (classic → terminal → classic, every view still boots,
client-error log empty) applies to all of them. No commits; nothing built yet.

