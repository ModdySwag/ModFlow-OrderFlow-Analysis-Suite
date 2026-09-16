# Flowsurface (flowsurface-rs/flowsurface) — what it holds for this build, and the fold-in plan

Status: **EXECUTED 2026-09-16/17 — see `docs/SESSION_HANDOFF.md` §76 for the receipts.** Built: the
Binance, Hyperliquid and OKX adapters on the `FeedSession` seam (all three wired, switchable and
live-probed), both backfill paths, the four generated alert WAVs (off by default) and the
changed-digit tape tint. Deferred by decision: the heatmap "order runs" model (§2.6/§2.7, behind
its measured trigger — nothing measured says it hurts today). Not folded in again because the
panels already had them under other names: the tape pause pill, size shading, the heatmap cell
readout. Still nothing committed. *(As originally written: plan for approval — the tree sat at
`aa43f40` plus this document and the three reading briefs it cites.)*

Sources read for this pass — the repo at **`c1388d4`** (2026-09-16), cloned read-only to
`%LOCALAPPDATA%\Temp\flowsurface_ref`:

* `README.md`, `Cargo.toml` (workspace: `data/`, `exchange/`, `src/` — 132 `.rs` files, ~60 k lines)
* `exchange/` — the feed layer: `adapter/ws.rs`, `adapter/http.rs`, `adapter/limiter.rs`,
  `adapter/proxy.rs`, `adapter/hub/{binance,bybit,hyperliquid,okex,mexc}/`, `depth.rs`, `unit/`
* `data/` — aggregation, frames, heatmap model, layout/config, `src/connector/fetcher.rs`
* `src/` — panels (`screen/dashboard/**`), chart widgets (`widget/chart/**`), indicators, audio,
  persistence, settings/network modals

Three file:line-referenced briefs were produced during the pass and are kept beside this plan as
`docs/flowsurface-notes/01-exchange-feeds.md`, `02-data-aggregation-and-backfill.md`,
`03-ui-panels-and-rendering.md`. **flowsurface is GPL-3.0**: nothing may be copied from it — every
fold below is a re-implementation from described behaviour, and the briefs contain no code.

Claims I spot-checked in the clone myself (not just relayed): the pinned reader future and
`select!` heartbeat loop (`exchange/src/adapter/ws.rs:634-660`), Binance's buffered-diff depth
machine (`adapter/hub/binance/stream.rs:512,549,561,664`), `Basis::Tick => unimplemented!()` in the
heatmap (`data/src/chart/heatmap.rs:151`, `data/src/aggr/time.rs:514`), the sound trigger
(`src/main.rs:231` → `src/audio.rs`), and the `/trades.arrow` contract in their README.

---

## 0. The honest summary

Flowsurface is a native (Rust + iced/wgpu) crypto charting app — heatmap of historical DOM,
candles, footprint, tape, DOM ladder, comparison — for Binance, Bybit, Hyperliquid, OKX and MEXC,
with historical trade backfill and trade-driven sound. It is **ahead of this suite in exactly four
places**: multi-venue feed engineering, historical trade backfill, a handful of panel interaction
details, and trade-stream audio.

Everything else this suite already matches or beats: more analytics (absorption / initiative /
sweep / exhaustion / divergence, CVD, TPO, volume profile, scanner, signals, replay, intent),
alerts and Telegram, options / fundamentals / news, widget windows and per-screen layouts, an
atomic config store with a sanitiser, and a security posture (loopback guard, CSP, SBOM,
retention) flowsurface does not attempt at all. Two things flowsurface appears to have and this
suite does not: a **comparison panel** in the multi-source sense, and **trade-driven audio**.

**So the fold-in is small, precise and mostly low-risk** — with one exception (`depthmap`) that I
recommend deferring behind its existing measured trigger. The plan below is ordered so that the
cheapest, safest, highest-value items land first, each behind a flag and its own pins.

---

## 1. Feature-by-feature, so nobody folds in a duplicate

| Capability | flowsurface | this suite today | verdict |
|---|---|---|---|
| Heatmap (historical DOM) | canvas on GPU; price grouping; several time-aggregation modes; fixed/visible-range profile | `atlas/depthmap.py` (1 s buckets, `max_columns` 900, row aggregation to a display step, carry-forward, version-stamped payloads) + `heatmap-pro.js` | parity; one model idea worth considering (§2.6) |
| Candles + studies | candle pane + 4 indicators | candles + a study/expression engine, drawings, VWAP, indicators library | **suite ahead** — take nothing |
| Footprint | on-chart footprint with clustering/imbalance/naked POC | `atlas/footprint` + the footprint view | parity |
| Tape (Time & Sales) | virtualized rows, size shading, **pause-on-scroll** | tape view, side colouring, infinite scroll | parity; two cheap polish items (§2.8) |
| DOM / ladder | 5-band grouped ladder, visible-range scaling | depth ladder view | parity; column-scaling idea (§2.8) |
| Non-time frames | tick bars only — and its heatmap **cannot use them** (`unimplemented!()`) | Range / Renko / Reversal / Tick / Volume bars, live (`atlas/frames.py`) | **suite ahead** — take nothing |
| Pane linking | link groups A–I, symbol-only, mixed venues | `ui/links.js` link groups (symbol + timeframe) | parity; the symbol-only rule matters only when venues multiply |
| Multi-window / monitors | multiple app windows | §73 widget windows, `?aux=` pages, per-screen layouts, geometry memory | **suite ahead** |
| Sound | trade-driven, per-symbol thresholds, overlap attenuation | none | **fold — §2.9** |
| Historical trade backfill | Binance public archives + `/trades.arrow` server protocol | none (live capture into SQLite `ticks`, 7-day retention) | **fold — §2.5** |
| Feeds / venues | 5 venues, per-venue heartbeat policies, gap-safe depth sync | Bybit (trades, `orderbook.50`, plus `orderbook.200`/liquidations/block trades in `feed_extras.py`), Alpaca, MT5 | **fold — §2.2/§2.3** |
| Proxy / network config | full proxy support, creds in OS keychain | none (loopback app, direct outbound) | note only (§2.10) |
| Persistence | one `saved-state.json`, per-field defaults | `config.json` atomic + clamped/sanitised, per-screen layout keys | **suite ahead** |
| Security / release hygiene | none of it | loopback guard, CSP, SBOM, retention, signed CI pins | **suite ahead** — take nothing |

---

## 2. The genuinely valuable folds (ranked)

Each item: what it is, why it is better than today's behaviour, where it lands, effort, risk.

### 2.1 P0 — the reader/heartbeat split, and per-venue silence policies (correctness)

**What.** In flowsurface a session runs one **pinned read future** that is *never* cancelled: the
heartbeat is a `select!` branch beside it (`adapter/ws.rs:638-660`), and heartbeats are
**per-venue policy objects** — Bybit ping 20 s / silence 60 s, MEXC 15/45, OKX 20/20 (ping after
idle), Hyperliquid 30/30, Binance server-driven with a 45 s spot / 240 s perps silence budget.

**Why it matters here.** The bug they fixed last commit is a Python-shaped bug: a shared timeout
that cancels a read mid-frame desyncs the frame parser (`Reserved bits are not zero` disconnects).
This suite is exposed the moment it grows a second venue (this plan) or any heartbeat task — the
identical trap in Python is `asyncio.wait_for(ws.recv(), t)` or a shared timeout that cancels a
partial read. Today `data/bybit_feed.py` is safe by accident (`async for` + library
`ping_interval=20`), and I checked: **no `wait_for` sits on any feed read path** in the repo
(the only one is `engine.py:656`, the stop path). So this fold is a *rule and a helper*, not a fix.

**Lands as.** A short "feed session" helper in `orderflow_system/data/` (reader task never
cancelled; heartbeat its own task; per-venue silence table) used by every new adapter, plus a
comment + pin in `bybit_feed.py` documenting why its current shape is correct. Effort **S**
(½ day). Risk **low** (additive; the working Bybit path is untouched).

### 2.2 P0 — backoff resets only on *parsed data*, with jitter (small, real)

**What.** flowsurface calls `record_success()` only after a decoded frame (`ws.rs:267`), so a
connect-and-die loop keeps escalating; and its backoff carries ±25 % jitter so a mass disconnect
does not stampede the venue.

**Why it matters here.** `data/bybit_feed.py:118` resets `_reconnect_delay = 1.0` immediately
after the socket opens, and there is no jitter anywhere. One accepted connection that dies at the
handshake costs a full 1→2→4→… ladder reset every time; and once this suite speaks to three venues,
a local network blip reconnects them all in lockstep. Both are one-liners with a test.

**Lands as.** A tiny change in `bybit_feed.py` (+ the new adapters): reset the ladder on the first
decoded message, jitter the sleep (±25 %). Pin: a fake socket that accepts and dies must *escalate*
(the test fails before the change). Effort **S**. Risk **low** (it touches a working feed, so:
flag-free but test-first, and a sandbox live probe after).

### 2.3 P1 — the gap-safe depth machine, generalised for new venues

**What.** Binance's adapter buffers diffs while the REST snapshot is in flight (`VecDeque`, cap
512), validates the chain (`prev_final_id` / `first_id == prev+1`), replays, and resyncs on any
break (`adapter/hub/binance/stream.rs:528-693`). Their Bybit and OKX adapters do **not** do this —
they store `u` and never compare it.

**Why it matters here.** This suite's Bybit feed already has real sequence discipline (`u` tracked
per symbol, stale marking, re-subscribe for a fresh snapshot — arguably stricter than flowsurface's
Bybit path). The value is **not** fixing Bybit; it is that every new venue must arrive with the
same discipline, and the machine (buffer → validate → replay → resync) is the cleanest version of
it seen so far. Fold it as a small, pure, tested helper — `data/depth_sync.py` — and use it in the
new adapters; leave `bybit_feed.py` alone. Effort **M** (1 day incl. tests). Risk **low** (new
file; no existing path).

### 2.4 P1 — the new venue adapters: Hyperliquid, Binance Futures, OKX (the real feature)

**What.** `desktop/api.py` already lists these as **reachable, free, "no feed adapter in this
build yet"** — `FREE_SOURCES` (`api.py:320-332`) with a `wired` flag that the UI reads. Adding an
adapter flips one row from honest-absence to honest-presence, behind the machinery that already
exists (`data_source` switch, engine restart, capability greying in `datasources()`).

Per-venue specifics learned from flowsurface (each one is a real trap avoided):

| Venue | Endpoint shape | Heartbeat | Depth specifics |
|---|---|---|---|
| **Hyperliquid** | WS + `/info` REST | 30 s ping / 30 s silence | REST `l2Book` seed **before** subscribing; tick size is *derived* from price + `szDecimals` (5-significant-figure rule); depth granularity via subscription `nSigFigs`/`mantissa`; "internal" symbol vs display symbol split |
| **Binance Futures** | `fstream.binance.com` | server-driven; perps silence budget 240 s | REST snapshot + buffered diffs with `pu` chain validation; aggTrade stream is directional (`is_buyer_maker` inverted convention) |
| **OKX** | public WS | 20 s ping **after idle** (not periodic) | diff-depth with seq numbers; snapshot emitted on subscribe |

**Why it matters here.** This is the single largest genuine capability gain available from
flowsurface: a second and third live crypto venue (a) makes the existing cross-venue top-of-book
(`atlas/crossvenue.py`) a true two-book view instead of quotes-plus-one-book, (b) gives an
independent tape to sanity-check Bybit prints, and (c) matches what the `sources` view already
promises. Alpaca stays for equities; MT5 stays as-is.

**Lands as.** One adapter per venue, each its own file (`data/hyperliquid_feed.py`, …), its own
pins (parsing, sequence, reconnect), its own live probe on a scratch sandbox port, and one
`FREE_SOURCES` flag flip. Order: **Hyperliquid first** (smallest surface, teaches the helper seam),
then **Binance** (heaviest, but the archive path in §2.5 depends on it), then **OKX**. Effort **M
per venue** (1–2 days each with tests + live probe). Risk **low-medium**: no existing source path
is modified; the risk is new surface area, contained by the per-venue flag and the capability
greying.

### 2.5 P1 — historical trade backfill (two independent paths)

**What.** flowsurface backfills historical trades two ways: (a) **exchange archives** —
`data.binance.vision/{spot|futures/um|cm}/daily/aggTrades/SYMBOL/SYMBOL-aggTrades-YYYY-MM-DD.zip`,
cache-first, prune >4 days, intraday REST after UTC midnight; (b) **any server** that answers
`GET /trades.arrow?venue&market&symbol&from&to&limit` with an Arrow IPC stream
(`ts int64, price float64, qty float64, is_sell bool`), optional bearer token, limit 400 000,
client cursor = `last_ts+1`, per-request state machine with a 30 s failure cooldown.

**Why it matters here.** This suite's charts start where the engine started — nothing before it.
Backfill turns a fresh launch into a full picture for footprint, heatmap and CVD windows; and the
`/trades.arrow` shape is a natural **read** endpoint over the `ticks` table this suite already
writes (SQLite, 7-day retention) — the day he wants a second machine or a replay source, the
protocol is defined. Python cost is genuinely low: `httpx` + `zipfile` are enough for (a);
pyarrow is *optional* (a JSON fallback on our side is fine since only flowsurface consumes Arrow).

**Lands as.** `data/backfill.py` (archives) behind a Settings toggle, writing into the existing
`ticks` table so every reader benefits without changes; plus a documented read endpoint
(`/api/atlas/trades.binance-archive` semantics — exact route naming decided in the pass) that
serves the same columns from SQLite. Effort **M** (1–2 days). Risk **medium** (it writes to the
DB: batch inserts, retention interplay, and a pure-function core with fixtures, plus a cap on how
much a single backfill may pull).

### 2.6 P2 — the heatmap depth model: order *runs*, not per-bucket snapshots — **measure first**

**What.** flowsurface stores the historical DOM as `BTreeMap<Price, Vec<OrderRun>>` — a level that
does not change is **one row**, not one entry per time bucket — and derives retention from its ring
size. This suite's `atlas/depthmap.py` stores per-bucket `price → (bid, ask)` across up to 900
columns.

**Why it matters here — and why not now.** The run representation is genuinely leaner (payload and
build cost scale with *changes*, not with *cells*). But it touches the single hottest contract in
the app: `depthmap.snapshot()`, the `/bin` heat wire, `heatmap-pro.js`/`market-pressure.js`
consumption, and the tests around all of them. The standing measurements say the current path is
**not** a problem: build 0.76 ms cold / 0.3 µs cached, heat pass 0.6–0.7 ms against a 6.94 ms
budget, drawn cells capped at ~6 k. The existing trigger for revisiting the wire is a snapshot's
JSON text passing ~2 MB or an adapt pass passing ~8 ms.

**Verdict: defer.** If the trigger fires, the run model is the design to copy — behind a payload
version key, in one pass, with the golden/selftest battery as the gate.

### 2.7 P2 — per-column invalidation for heat payloads — same verdict

Version-stamped payloads and repaint skipping already exist here (the ATAS pass). flowsurface's
extra is *per-column* dirty tracking. Only worth doing if profiling (after §2.6's decision) shows
the repaint path is the cost. Defer with the same trigger.

### 2.8 P2 — panel polish set (pure JS, cheap, high-delight)

Four small things, each independent, each testable in an existing `*.selftest.js`:

1. **Tape pause-on-scroll** — scrolling past the header freezes the list (prints buffer without
   touching the header aggregates) and shows a clickable "Paused · N new" pill; resume flushes.
   Fixes the real problem of losing your place in a fast tape.
2. **Tape row shading by relative size** — row background alpha = `qty / max(visible rows)`,
   clamped — the tape reads as a size profile at a glance (side colouring already exists).
3. **Changed-digit price highlighting** in the tape/tape-like lists (only the digits that moved
   are tinted) — a well-known readability trick, local to the row renderer.
4. **Cell-snapped crosshair + neighbourhood tooltip** on the heatmap (crosshair snaps to the
   bucket/price cell and a small grid shows the cells around it) — the map is hard to read
   precisely today; this is the cheapest fix.

Effort **S–M total** (½–1 day). Risk **low** (view-local JS; DOM ids/classes unchanged so the
audit stays clean).

### 2.9 P2 — trade-driven audio (the one feature this suite simply does not have)

**What.** flowsurface plays four short WAVs (buy / hard-buy / sell / hard-sell) on trade events,
per-(venue, symbol) `{enabled, threshold}` where threshold is a **print count**, the "hard"
variant at >4× the threshold, and rare-but-real touches: retriggers inside 10 ms **attenuate
overlapping gains** instead of stacking, and a dead audio device surfaces as a toast with Retry.
Settings live in their own Audio modal.

**Why it matters here.** A tape watcher's second channel. It is also the lowest-risk fold in this
list: it reads a stream that already exists (`/ws` trade frames or the tape poll), touches no
Python analytics, and is entirely off by default.

**Lands as.** `desktop/ui/audio.js` (pure JS over the existing feed; thresholds in `config.json`
under a new `audio` block, off by default), a Settings card, and four self-generated WAVs in
`desktop/ui/audio/` (no third-party samples — no licence question). Pin: a selftest for the
threshold/hard/attenuation rules; live check with a sandbox feed. Effort **S** (½–1 day). Risk
**low**.

### 2.10 P3 — the smaller ones (take or leave)

* **Comparison normalisation** — `alpaca/compare` exists; flowsurface's rule (percent rebased to
  the **left edge of the visible window**, linearly interpolated y0) is a better default than a
  full-history rebase. Effort **S**, risk **low**, UI-only.
* **Profile window mode** — flowsurface's `ProfileKind::VisibleRange` vs `FixedWindow(n)` anchored
  to the live edge (recomputed on demand). This suite's profile is session-relative; a
  visible/fixed toggle is a genuine small addition. Effort **S–M**, risk **low-medium** (touches
  `atlas/profiles.py` + the profile view).
* **Settings mirroring / "Sync all"** for widgets of the same view — pairs naturally with the
  widget windows; UI-only. Effort **S**, risk **low**.
* **Proxy support** — flowsurface carries a full CONNECT/SOCKS implementation with credentials in
  the OS keychain and an "effective vs pending, restart required" UI. This suite is loopback-only
  and does not need it today; note it for the day someone runs it behind a corporate proxy.
  Effort **M**, risk **medium** — P3, not now.

---

## 3. What we deliberately do NOT take, and why

* **Any code.** GPL-3.0. Every fold above is a re-implementation from described behaviour; the
  briefs contain no source. This is a hard rule, not a preference.
* **The GPU renderer (wgpu/WGSL/iced).** This suite's canvas measures inside its budget (max warm
  frame 12.4 ms; heat pass 0.6–0.7 ms), and P3-1 (WebGL heat) was measured **not triggered** on
  his hardware (§59). Re-opening that work needs a measured trigger, not a port.
* **The integer-atomic price/qty model** (`i64` at 1e-11 / 1e-8). It is the right cure for
  float-key drift, but it would touch every aggregate, every payload and the JS. This suite's
  equivalent discipline is already pinned (`analytics_golden`, `_finite` ingest gates, payload
  parity). If a real float-key defect ever appears, copy this design **at the storage/wire
  boundary only**.
* **Tick-count bars as a new family** — already present here (five frame families), and
  flowsurface's own heatmap cannot consume its tick basis (`unimplemented!()`).
* **Silent event drops on a full channel** — the crate itself offers an unbounded channel for
  "every tick matters" ingestion; anything feeding SQLite here must stay lossless-or-counted.
* **Their tape retention cap, ladder column widths, layout file format, theme model** — this
  suite's stores are richer (atomic write, sanitiser, per-screen keys, version guards).
* **Their venue credentials / keychain flow** until proxy support is actually wanted.

---

## 4. The "don't break anything" protocol (how every fold lands)

1. **Additive only.** No existing default changes without a config value and a documented trigger.
2. **Test-first.** Every fold lands with pins that fail before it (the house rule), then the full
   gate battery on **both** interpreters: pytest, `audit_ui_refs`, both goldens, the 20 selftests,
   ruff 0.16.7, pip-audit.
3. **Hot paths land one at a time**, each behind its own flag or venue toggle, each with a live
   sandbox probe on a scratch `APPDATA` (809x), and a cold read of `orderflow.log` for
   `client error:` lines.
4. **The Bybit path is not touched** beyond §2.2's one-liner (pinned, live-probed). New venues are
   new files; `data_source` keeps `bybit` as the default.
5. **Each phase ends with the frozen-build re-verify** (payload 90/90, probe battery, double-launch)
   before any release artefact is rebuilt — never ship from a dirty verification.
6. **Nothing is committed or pushed without his word**; each phase banks its own §-record in
   `docs/SESSION_HANDOFF.md`, and RESUME is updated at each hand-back.

---

## 5. Phased plan of action

| Phase | Content | Effort | Gate |
|---|---|---|---|
| **0 — ground truth** | This plan + the briefs in `docs/`; the feed-session helper + the backoff/jitter fix (§2.1/§2.2) | ½–1 day | full suite on 3.11+3.12; sandbox probe; no visible change |
| **1 — first new venue** | Hyperliquid adapter (§2.4) on the helper seam; `FREE_SOURCES` flip; capability greying verified | 1–2 days | adapter pins; live sandbox probe; cross-venue BBO reads two real books |
| **2 — the heavy venue + backfill** | Binance Futures adapter (§2.4) with the gap-safe machine (§2.3); Binance archive backfill (§2.5) behind a Settings toggle | 2–3 days | sequence/gap pins; DB batch pins; backfill cap verified; retention interplay checked |
| **3 — breadth + polish** | OKX adapter; tape pause/shading, changed-digit prices, heatmap crosshair tooltip; audio panel (§2.8/§2.9) | 2 days | selftests; live probe; audit clean |
| **4 — only if measured** | depthmap run-model and/or per-column invalidation (§2.6/§2.7); comparison + profile-window upgrades (§2.10) | 2–3 days | the existing payload/build triggers must actually fire first |
| **5 — release** | Rebuild `dist/` (exe → zip → Setup + SBOM), re-run the acceptance battery, update `RELEASE_EVIDENCE` | ½ day | the §75 battery, all green |

---

## 6. Decisions I need from you

1. **Which venue first** — Hyperliquid (small, novel, teases the multi-venue seam) or Binance
   Futures (biggest liquidity, and required for the archive backfill)? My recommendation:
   **Hyperliquid, then Binance**.
2. **Audio shape** — four self-generated samples with per-symbol thresholds (as flowsurface does),
   or a silent-by-default panel where you drop in your own WAVs? My recommendation: **ship the
   four generated samples, global off by default**.
3. **Backfill scope** — Binance public archives as well, or only "serve our own ticks" from
   SQLite? My recommendation: **both, archives first** (it is the one that fills a fresh chart).
4. **§2.6/§2.7** — leave the heatmap model alone until its existing trigger fires? My
   recommendation: **yes, defer** — nothing measured says it hurts today.

*(At the plan's writing: nothing above had been built and nothing in the app had changed yet —
see the status line at the top for what has since landed.)*
