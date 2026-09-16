# ModFlow OrderFlow Analysis Suite — final release assurance audit (v0.1.0-beta)

**Directive applied:** `C:\Users\Moddy\Desktop\final security audit prompt.txt` — *Executive final
release assurance audit — Security, Reliability, Correctness, and Zero-Leak Gate* (treat the repo as
untrusted data; no speculative rewrites; produce the 14 required sections; never claim more than was
verified).
**Tree:** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · **HEAD** `4b603dc` · **Date:** 2026-09-17.
**Rule observed:** nothing committed (repo rule); everything this pass changed is on disk and listed
below. Nothing in the app's runtime *behaviour* changed, with one deliberate exception: the server
now prints a WARNING when `dashboard/static` is missing (it never fires in a correct build).

**Baseline at pass start.** HEAD `4b603dc`, working tree with **two uncommitted comment-only edits**
(`orderflow_system/config/settings.py`, `orderflow_system/desktop/config_store.py`, mtime 01:19 —
their provenance is recorded in no pass document; see F-03). All gates were run before any change:
pytest **843/2**, `AUDIT CLEAN`, ruff clean, **22/22** selftests, `pip-audit` clean — see §12.

**What this pass changed on disk**

| Path | Change |
|---|---|
| `scripts/build_exe.py` | the defect in F-01 — now ships `dashboard/static` (required, refuses to build without it) |
| `orderflow_system/dashboard/app.py` | fail-loud WARNING when `dashboard/static` is missing |
| `orderflow_system/test_wiring.py` | +1 regression pin (assets on disk + every root the shell loads is in the build) |
| `orderflow_system/test_platforms.py` | the add-on pin follows the build script's renamed constant |
| `orderflow_system/config/settings.py`, `orderflow_system/desktop/config_store.py` | comment rewording (F-03) |
| `docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md` (this file), `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`, `docs/SESSION_HANDOFF.md` §78, `docs/RESUME.md`, `installer/README.md` | records |
| `dist/` exe + zip + Setup, `installer/ModFlowOrderFlowAnalysisSuite.ism` | rebuilt from the fixed tree; new hashes in `RELEASE_EVIDENCE` |

---

## 1. Executive release decision

**READY TO SHIP v0.1.0-beta.**

- **No Critical or High security vulnerabilities were found.** The security posture verified in the
  §70 sweep holds on the current tree, and every claim below was re-tested live, not inferred.
- **One High release-integrity defect was found and fixed in this pass** (F-01): the frozen
  artefacts shipped without `orderflow_system/dashboard/static`, which left six views dead in the
  packaged app while every test stayed green. It is fixed at the build script, pinned by a test that
  was proven to bite, and the artefacts were rebuilt and re-verified end to end — including a full
  silent install → smoke → silent uninstall journey of the rebuilt Setup.
- **Resource ownership is proven for every long-lived structure inspected** — 31/31 deques bounded,
  every task cancelled on its stop path, client queues capped, the UI's timers/observers/listeners
  flat under an 8-cycle view-churn soak on the frozen exe (see §7).
- **Market-data validity fails safe and visibly**: non-finite venue values are rejected at ingest,
  unknown symbols serve `[]` (never invented data), and staleness/demo states are labelled in the
  UI.
- **Build, test and release procedures are reproducible**: pytest 844/2 on **both** interpreters,
  `AUDIT CLEAN`, ruff clean, 22/22 selftests, lockfile check green, CI pinned to immutable SHAs with
  least-privilege permissions.
- The beta framing is the explicit-limitation envelope (§14) — loopback-only, market-data-only,
  places no orders, MT5 paths fixture-covered.

**Non-blocking owner queue (release-process steps, not code):** the push decision, the physical
multi-monitor pass, the release-notes review, then tag `v0.1.0-beta` with the zip + Setup + SBOM.

---

## 2. Executive risk summary

| Priority | Finding | Confidence | Impact | Release requirement |
|---|---|---|---|---|
| High | **F-01** Frozen artefacts shipped without `dashboard/static` — six views (Footprint, Depth, Tape, Signals, Performance, Microstructure) dead in the exe/zip/Setup | Confirmed (measured) | Users get a broken half-UI with no error; tests stay green | **Yes — FIXED this pass, artefacts rebuilt + re-verified** |
| Low | **F-02** Missing widget scripts degrade silently at the UI level (wiring guards return; the loader's loud error path only covers `/desktop/` modules) | Confirmed | Symptoms look like "the view just doesn't work" | No — addressed by build refusal + startup warning + pin; optional UI notice deferred |
| Low | **F-03** Comment-level doc drift: uncommitted comments referenced a config key that does not exist (`dashboard.expose_lan`) | Confirmed | Misleads whoever configures LAN exposure next | No — **FIXED** (comments reworded to the real `dashboard.host` mechanism) |
| Informational | **F-04** `/docs`, `/redoc`, `/openapi.json` served on loopback | Confirmed | Requires local access; no credential or data exposure | No — accepted as-is (option recorded) |
| Informational | **F-05** `ConnectionResetError` tracebacks from aborted client sockets appear in the app log | Confirmed | Cosmetic log noise; no leak, no failed request follows from it | No — log-hygiene fix specified, queued (not applied: cosmetic only) |
| Informational | **F-06** Platforms view attaches ~29 listeners per activation | Confirmed (measured; **not a leak**) | None — nodes are rebuilt wholesale; heap/DOM/canvas flat under soak | No — no change |
| Informational | **F-07** `docs/` carries internal working notes incl. local paths | Confirmed | Privacy-judgement call for a public repo; no credentials (scans clean) | No — owner decision, flagged for the release-notes review |
| Informational | **F-08** bandit: 1 High (SHA1, non-security use) + 17 Medium (reviewed: B314/B310/B608 false-positive classes) | Confirmed | None; external reports will keep flagging them | No — one-argument fix queued; triage recorded here |

No Critical findings. No unpatched High remains: F-01 was the only High and is fixed and re-verified.

---

## 3. Verified architecture, data-flow, trust-boundary and ownership map

**Entry points.** `orderflow_system.desktop` (`__main__.py` → `launcher.main`): starts the FastAPI
app in a daemon thread bound to **127.0.0.1** on a free port, waits for `/healthz` readiness, then
opens the pywebview/WebView2 window on `http://127.0.0.1:<port>/desktop` (fallback: the system
browser). `orderflow_system.main`: the CLI pipeline (MT5/Bybit paths). `orderflow_system.dashboard`:
the legacy terminal page — retired as the front door (`/` → 307 → `/desktop`), files kept because six
of its modules are load-bearing for the desktop shell.

**Process/layer boundaries.**

```
venue feeds (wss/rest)          pywebview window (WebView2, same user)
  binance / okx / hyperliquid     └─ http://127.0.0.1:PORT/desktop   (74 audited JS modules)
  bybit / alpaca + archive        ▲        │ fetch/WS (loopback only, CSP-pinned)
        │  (finite-value gates)    │        ▼
        ▼                     uvicorn thread (FastAPI app, LocalRequestGuard middleware)
  FeedSession (reconnect ladder)  ├─ /api/*        control + data (parameterised SQL)
  atlas/ engines (pure maths)     ├─ /desktop      desktop shell (StaticFiles, no-store)
  OrderflowSystem pipelines       ├─ /static       six widget modules (F-01) + legacy page
        │                         └─ /ws          one writer task per client (maxsize 256)
        ▼
  aiosqlite (WAL, busy_timeout)   per-user config: %APPDATA%\OrderFlowAnalysisPro (redacted on GET)
```

**UI lifecycle.** One page per window; views are `<section class="view" data-view="X">`; modules
self-init through class-MutationObservers with one-shot guards (`view.booted`, `NEWS.wired`,
`state.wired`); pollers stop when their view hides or a gesture holds the view (the intent layer);
aux windows (`?aux=`) render a synthetic single-widget layout and never write one.

**Long-lived resource owners.** See the ownership table in §7 — WS client queue + writer task, feed
sessions + heartbeat, snapshot tasks, replay/history/engine tasks, the aiosqlite handle, the log
handler (rotating), the in-app log ring buffer, atlas deques (all maxlen), and the UI's page-scope
timers/observers.

**Rendering architecture.** Canvas 2D only (no WebGL); backing store = `round(CSS box × dpr)`
(engine law §71/§72); LOD ladder in `ofx.js`; `fitView` walks the whole document; resize granularity:
window resize + `ofap:relayout` (re-parent/frame resize).

---

## 4. Audit coverage matrix

| Subsystem / directory | Status | Risks checked | Remaining unknowns |
|---|---|---|---|
| `data/` feeds (binance, okx, hyperliquid, bybit, alpaca, feed_session, backfill) | Inspected + live-tested | reconnect, snapshot chains, NaN/Inf gates, queue bounds, task lifetime, archive writes | venue-side behaviour under rare rate-limit regimes (fault paths are fixture-tested) |
| `atlas/` engines (+ `vwap`, `intent`, `tapeflow`, `depthmap`, …) | Inspected | deque bounds (31/31), prune logic, task start/stop, NaN handling | numerical edge cases are golden-tested; no runtime soak per engine |
| `analytics/`, `patterns/`, `signals/`, `main.py` | Inspected (not dead code — the desktop path imports them) | input validation, bounds, no numpy dependency | — |
| `dashboard/` (app, websocket_manager, static, demo_data) | Inspected + live-tested | guard middleware, WS backpressure, static mount (**F-01**), demo fillers | — |
| `desktop/` (launcher, api, engine, windows, single_instance, logs, ui/*.js) | Inspected + live-tested (CDP) | resource lifetime, listener/timer accumulation, DPR law, PSAPI/API surface, aux windows | platforms-form re-render under typing (F-06: cannot fire mid-view) |
| `scripts/` (build_exe, audit_ui_refs, build helpers) | Inspected + executed | frozen-build payload completeness (**F-01**), audit interpreter hint | — |
| `installer/` | Inspected + journey re-run | silent install/uninstall, payload hash identity, ARP cleanup | Start-Menu shortcut + WebView2 chaining (documented automation-API limits) |
| `docs/`, `README`, `SECURITY.md`, `LICENSE`, `THIRD_PARTY_NOTICES` | Inspected | secrets, claims vs measurements, publication surface (F-07) | — |
| `.github/workflows/ci.yml` | Inspected | permissions, SHA pinning, supply-chain steps | GitHub-side settings (branch protection) are outside the repo |
| `dist/` artefacts | Inspected + executed | complete payload, guards, hash identity, zip integrity, install identity | — |
| `orderflow_system/desktop/ui/vendor/` | Excluded (third-party chart copy) | — | excluded from the JS parse audit by design (74 of 75 `.js` files audited) |

---

## 5. Threat model and protected assets

**Assets.** (1) Market-data integrity — the app's output is trading analysis; silently wrong numbers
are the worst failure. (2) Per-user credentials in `%APPDATA%\OrderFlowAnalysisPro\config.json`
(Alpaca keys, vendor passwords, notification tokens). (3) The user's machine and other local data.
(4) Release integrity (the artefact users download). (5) Reputation of the public repo.

**Trust boundaries.**
- **Browser ↔ loopback API.** Any web page in any local browser can attempt requests to
  `127.0.0.1:<port>`. Defences (verified live, §12): non-loopback `Host` → 403 (DNS-rebinding);
  cross-origin and `Sec-Fetch-Site: cross-site` mutations → 403; WS handshake origin check; CSP on
  the shell (`default-src 'self'`, loopback WS only, `object-src/frame-src 'none'`). Residual: a
  same-user local process (out of scope — it could already read `config.json`).
- **Venue/news bytes ↔ engines.** All numbers pass `math.isfinite` gates at ingest; junk is counted,
  not propagated. User-supplied feed URL: http(s)-only, http(s)-only redirects, 4 MiB cap, internal
  DTD subsets refused before parsing.
- **Archives ↔ filesystem.** Backfill writes only under its cache dir, `.part` → renamed on
  completion; symbols are validated against the configured instrument set at the API layer.
- **Screenshots/docs ↔ public repo.** Sampled screenshots contain no PII (spot-checked this pass);
  docs carry local paths but no credentials (scans below).

**Out of scope, stated honestly:** an attacker who already runs code as the user; MT5 terminal
internals (no terminal on this host, fixture-covered); GitHub repository settings.

---

## 6. Detailed findings

### F-01 [High] The frozen artefacts shipped without `orderflow_system/dashboard/static` — six views dead in the packaged app

- **Classification:** Release-integrity / packaging defect (not a security vulnerability).
- **Confidence:** Confirmed — measured live on the shipped artefacts, both sides compared.
- **Release blocker:** Yes — **resolved in this pass.**
- **Affected files/symbols:** `scripts/build_exe.py` (the payload list); `orderflow_system/desktop/ui/index.html:833-838`
  (`<script src="/static/{footprint,orderbook,tape,signals,performance,microstructure}.js">`);
  `orderflow_system/dashboard/app.py` (`/static` mount, now fail-loud);
  `orderflow_system/desktop/ui/ui.js` (`window.FootprintChart`, `window.OrderbookLadder`,
  `window.TimeAndSales`, `window.MicrostructurePanel` instantiation sites);
  `orderflow_system/desktop/ui/tape.selftest.js` (reads `../../dashboard/static/tape.js`).
- **Trust boundary or resource involved:** build/release pipeline (the artefact users download).
- **Preconditions:** running the packaged exe/zip/Setup as shipped before this pass.
- **Failure sequence:** app boots → shell loads → six `/static/*.js` requests answer **404** → the
  widget classes stay `undefined` → `ui.js`'s guards (`!window.TimeAndSales` etc.) return silently →
  Footprint / Depth / Tape / Signals / Performance / Microstructure views render nothing, with no
  error anywhere the user looks.
- **Evidence (measured):** pre-fix frozen exe — six 404s (`/static/footprint.js`, `orderbook.js`,
  `tape.js`, `signals.js`, `performance.js`, `microstructure.js`); all six `window.*` classes
  `undefined`; Tape view **0 rows** live. Repo tree, same probe — **47/47 assets 200**, all six
  classes `function`, Tape rows present, Footprint canvas built (1342×600). `dist/…/_internal/orderflow_system/dashboard/static/`
  absent; the release zip's `namelist()` contained no `dashboard/static` entry.
- **Root cause:** `build_exe.py` shipped `orderflow_system/desktop/ui` and the Bookmap add-on as
  `--add-data`, but not `dashboard/static`; `app.py` mounts `/static` only `if os.path.isdir(...)`,
  so the missing directory degraded to plain 404s; and the existing script-tag guard in
  `test_wiring.py` only inspected `/desktop/` tags, so the repo-side check stayed green.
- **Security impact:** none directly. Integrity impact: the shipped binary did not match the
  advertised feature set.
- **Privacy impact:** none.
- **Data-integrity impact:** the dead views included the Tape (time & sales) and Depth (ladder) —
  both read-only, no writes; no data corruption.
- **Reliability/performance impact:** none on the server; six failed requests per page load.
- **User/reputational impact:** a user's first impression of six views is "it's broken" — on a
  public release this is the failure reviewers would find first.
- **Minimal safe remediation (applied):** `build_exe.py` now ships both required data roots and
  **refuses to build** if one is missing; `dashboard/app.py` logs a WARNING naming the missing
  directory and the six affected widgets (the only runtime change; cannot fire in a correct build);
  a new pin in `test_wiring.py` asserts (a) every local asset `index.html` loads exists on disk and
  (b) every root it loads from is inside the build's `REQUIRED_DATA_RELS`.
- **Compatibility/regression risks:** none to runtime behaviour; the artefacts grow by the nine
  files (~0.6 MB raw). The new test previously failed only because the fix was absent — both bite
  proofs recorded (§12).
- **Required tests/acceptance:** the pin (green post-fix; red with a renamed module and with the
  build list doctored — both measured); post-rebuild live verification (§12 rows 5–10).
- **Rollback plan:** revert `build_exe.py`/`app.py`/`test_wiring.py`, rebuild — the pre-fix state is
  reproducible.
- **Implementation order/dependencies:** fixed first (nothing else was worth landing until the
  release artefact was whole).
- **Ship decision for this finding:** **fixed — verified on the rebuilt exe, zip and Setup.**

### F-02 [Low] Missing widget scripts degrade silently at the UI level

- **Classification:** Observability.
- **Confidence:** Confirmed (the pattern is in every module's wire guard).
- **Release blocker:** No.
- **Affected:** `orderflow_system/desktop/ui/ui.js` (guard-and-return sites), module loader in
  `shell.js` (its loud error path covers `/desktop/` modules only).
- **Failure sequence:** a widget class is never defined → the view simply stays empty.
- **Evidence:** F-01's measurements — that is exactly how six dead views looked from the outside.
- **Root cause:** the load-failure banner was built for the shell's own modules; `/static` widget
  modules have no counterpart.
- **Remediation (applied, layered):** build refuses to produce an incomplete package; the server
  warns at startup when the directory is missing; the pin makes the repo state impossible to drift.
  **Deferred (post-beta, weighed):** a visible per-view "module failed to load" note would be the
  full fix, but it touches the shell's render path — deliberately not bundled into a release-freeze
  pass.
- **Ship decision:** acceptable for beta with the three layers above; revisit after v0.1.0-beta.

### F-03 [Low] Comment-level doc drift — a config key that does not exist

- **Classification:** Documentation drift (pre-existing uncommitted edits).
- **Confidence:** Confirmed.
- **Release blocker:** No.
- **Affected:** `orderflow_system/config/settings.py` (DashboardConfig docstring),
  `orderflow_system/desktop/config_store.py` (default-config comment) — both uncommitted, mtime
  01:19, provenance not recorded in any pass document.
- **Evidence:** both comments referenced `dashboard.expose_lan`; the only real control is
  `dashboard.host` (loopback default) — the key appears nowhere else in the tree.
- **Remediation (applied):** both comments reworded to the actual mechanism (`dashboard.host`,
  loopback default, `LocalRequestGuard` behaviour stated correctly). Comment-only — zero runtime
  effect.
- **Ship decision:** fixed.

### F-04 [Informational] `/docs`, `/redoc`, `/openapi.json` on loopback

- **Evidence:** the FastAPI app is constructed without `docs_url=None`; the endpoints answer on
  loopback and are subject to the same `LocalRequestGuard`.
- **Assessment:** no credential or config exposure (the control API redacts secrets on GET and the
  docs pages are static schema). Reaching them already requires local, same-user access.
- **Option (recorded, not taken):** disable in packaged builds; adds a singleton-app caveat the
  tests share — not worth a release-freeze change.

### F-05 [Informational] `ConnectionResetError` tracebacks from aborted client sockets in the log

- **Evidence:** `orderflow.log` carried `ConnectionResetError: [WinError 10054] … _call_connection_lost`
  tracebacks — reproduced by simply aborting a curl/browser request. The app's own request handling
  and error path are unaffected; 0 `client error:` lines were recorded in every sandbox.
- **Assessment:** cosmetic, but a user reading their log may mistake it for a failure. Cleanest fix
  (queued, one place): a loop exception handler that logs `ConnectionResetError` at DEBUG and
  delegates everything else to the default handler.
- **Why not applied now:** it touches event-loop wiring for a purely cosmetic gain; a logging-only
  change riding the next source-changing pass keeps this pass's verification chain exact.

### F-06 [Informational] Platforms view re-attaches ~29 listeners per activation — verified NOT a leak

- **Evidence (instrumented CDP probe, exe):** activation 1/2/3 each add ~29 listeners and remove 0 —
  **but** the listeners are attached to nodes that `plRender()` rebuilds wholesale
  (`host.innerHTML = …`) on every load, so the old nodes and their listeners become garbage each
  time. The 8-cycle soak shows retention flat: DOM 7209→7253, canvases 19, JS heap a 5.7–22 MB GC
  sawtooth with no trend; intervals 24 steady, observers 13 steady.
- **Residual wrinkle (documented):** a re-render while the user is mid-typing would clear in-progress
  form state. Measured trigger: re-renders happen on view activation only (no poll timer), so this
  cannot fire while the user stays in the view.
- **Ship decision:** no change.

### F-07 [Informational] Publication-surface review of `docs/`

- **Evidence:** `SESSION_HANDOFF.md` (4,334 lines), `RESUME.md` and the audit records carry internal
  working notes, local paths (`C:\Users\Moddy\…`) and machine names. Secret scans (below) are clean;
  screenshots sampled clean.
- **Options weighed:** (a) ship as-is — transparency, and the paths are non-sensitive in context;
  (b) trim/move the internal notes before publishing; (c) keep the working notes but add a one-line
  "internal engineering notes" disclaimer atop the biggest file.
- **Recommendation:** (a) or (c) — this is the owner's judgement at the release-notes review; no
  change made.

### F-08 [Informational] Static-analysis dispositions (bandit)

- **B324 High ×1** — `desktop/single_instance.py:43`: SHA1 digests a profile path to mint a **mutex
  name** (stability, not secrecy). Non-security use. Queued one-argument fix
  (`usedforsecurity=False`) for the next source-changing pass; behaviour-identical (same digest).
- **B314 ×1** — `atlas/context.py:122`: XML parsed with the internal-DTD-subset refusal ahead of it
  and a 4 MiB byte cap; stdlib ElementTree does not resolve external entities. Accepted.
- **B310 ×15** — fixed venue URLs (binance/okx/hyperliquid/alpaca/ntfy) plus the news fetcher, whose
  http(s)-only + redirect + byte-cap containment is pinned by `test_context_hardening.py`. Accepted.
- **B608 ×1** — `data/database.py:261`: f-string table name drawn from a **fixed tuple literal**
  (`("ticks", "candles", "volume_profiles", "signals", "trade_journal")`) — no user input reaches
  it. Accepted (optional static-SQL hardening recorded).
- **pip-audit:** 59 packages in the freeze, **no known vulnerabilities**.

---

## 7. Zero-leak / resource-lifetime report

**Ownership table** (verified by code read + live probes; soak receipts in
`%LOCALAPPDATA%\Temp\ofap_secaudit\soak_metrics.json`, `view_activation.json`).

| Resource | Created at | Owner | Release path | Failure/cancel cleanup | Bounded | Evidence |
|---|---|---|---|---|---|---|
| WS client queue | `websocket_manager._Client` | per client | drop on disconnect | writer `finally` forgets client | Yes — `maxsize=256`, droppable channels trim | code + pins |
| WS writer task | `connect()` | per client | `disconnect()` cancels | `finally: _forget` | Yes — 5 s `asyncio.timeout` per write | `test_websocket_backpressure.py` |
| Feed session + heartbeat | `FeedSession.run()` | feed | `stop()` | `finally`: heartbeat cancelled, conn closed, hook fired | Yes | `test_feed_session.py` (106 fault cases) |
| Venue snapshot task | `binance_feed._schedule_snapshot` | per symbol | completion | dedup: replaced only when done | Yes — 1/symbol + cooldown | tests |
| Archive backfill producer | `backfill` generator | job | consumer `finally` | drains queue, awaits producer | Yes — `maxsize=4`, ≤7 days/request, single-job guard | tests + §77 receipts |
| Replay / history tasks | `atlas/replay.py`, `atlas/history.py` | engine | `stop()` cancels + awaits | yes | Yes | code |
| Engine task | `desktop/engine.py` | app | `stop()` (`wait_for` 15 s → cancel) | yes | Yes | code |
| aiosqlite connection | `Database.connect()` | app/job | `close()` in `finally` | yes | Yes — WAL, busy_timeout 15 s | code + tests |
| Log handler + in-app log ring | `desktop/logs.py` | app | rotation | — | Yes — `RotatingFileHandler` + `deque(maxlen=MAX_LINES)` | code |
| Atlas deques (31 sites) | engines | engines | `maxlen` eviction | — | **31/31 bounded**; `vwap._order` prunes by time (`_history_s`) | script scan |
| UI intervals | page load / view boot | module | one-shot guards; pause registry | `clearInterval` via `OFAPPause` | Yes — 24 live, flat across 8 cycles | soak |
| UI observers / listeners | view boot | module | one-time `watch()`; observers live with the page | n/a (page = process lifetime) | Yes — MOs 13 steady; net adds stop after warm-up | soak + probe |
| Canvas contexts | 19 fixed | views | — | n/a | Yes — count steady at 19 | soak |

**Soak (frozen exe, live Bybit feed, scratch APPDATA):** 8 full cycles × 28 views, then 12 samples
over ~96 s on the busy views. Intervals 20→24 then **flat**; observers 11→13 then **flat**; canvases
**flat at 19**; DOM 6308→7253 then **flat**; JS heap 5.7–22.2 MB **sawtooth (GC), no upward trend**;
0 page errors; the only console entries were the six F-01 404s (now gone; post-fix run: 0 of 6).
Actor-side: engine live throughout (ticks 5,840 → second run 6,061+), 0 `client error:` lines.

**Verdict:** no unbounded growth found on any inspected structure; the F-01 defect was the only
thing the soak surfaced, and it was fixed and re-measured.

---

## 8. Market-data integrity assessment

- **Ingest gates:** every venue value passes `math.isfinite` (`bybit_feed._finite`,
  `alpaca_normalize._num`, binance/okx/hyperliquid equivalents); junk is counted in
  `book_health()["junk_values"]`, never propagated. NaN cannot slip through comparison gates —
  exact failure mode covered.
- **Unknown symbols serve nothing:** all ten demo-fill endpoints return `[]`/the mode-tagged empty
  shape for a symbol the pipeline does not model (`test_demo_symbol_guards.py`); verified live again
  this pass on the sandbox (unknown symbol → `[]`, modelled symbol unchanged).
- **Ordering/reconnects:** snapshot/diff chains with straddle gates, resync, sequence-reset
  adoption, checksum top-25 (OKX) — 106 fault-path cases across the four new venue feeds.
- **Tick discipline:** absorption events key on the tick-rounded price (never a fixed 4-dp round);
  displacement is true tick steps; fine-tick instruments (1e-5) verified with real EURUSD cases.
- **Labelling:** freshness chips (`fresh/aging/stale/held/unknown/demo`), the `data:` chip and the
  demo-data notices make derived/partial data visible; the app's rule is "degrade out loud".
- **Persistence round trip:** the DB candle round trip now carries footprint through
  (`test_candle_roundtrip.py`) — closed in the §66 audit return.
- **Residual:** vendor-side silent inconsistencies (e.g. a venue serving internally-consistent but
  wrong data) cannot be detected locally; the app's answer is cross-venue switching, which is one
  click and was exercised live in §77.

---

## 9. Rendering, concurrency, memory, CPU, GPU stability assessment

- **Frame behaviour (measured this pass, live feed):** Engine view, rAF deltas over 6 s —
  **median 16.7 ms, p95 16.7, p99 16.8, max 16.8 ms** — flat 60 Hz cadence on **both** the repo tree
  and the frozen exe; no missed-frame tail on this host. (Headless Chromium vsync; the honest claim
  is "no stall > 16.8 ms observed on this machine".)
- **Canvas law:** backing store = `round(CSS box × dpr)`; `math.layerSize(w,h,1)` identity pinned;
  the §72 regression pins (self-referential fit) are in `ofx.selftest.js`.
- **Concurrency:** one writer task per WS client, outside every lock; droppable channels trim, the
  signal channel never drops; the 3.11 `wait_for`-swallows-cancel hazard is pinned away (delivery
  uses `asyncio.timeout`); engine/feed/replay stop paths cancel and await.
- **Memory/CPU:** soak results in §7 — no growth trend; JS heap sawtooth; Python-side workers are
  event-loop tasks with bounded buffers; the analytics engines are stdlib-only (no numpy) so the
  frozen package carries no BLAS/OpenBLAS threads.
- **GPU:** Canvas 2D only (no WebGL contexts to leak); canvas count steady at 19 under churn; DPR
  changes handled by the §72 resize path.

---

## 10. Security, privacy, dependency, CI and public-GitHub release assessment

- **Secrets:** clean. Scans this pass: secret-shaped patterns over all tracked files (AWS keys,
  `sk-`/`ghp_`/`xox-`/Telegram bot-token shapes, private-key headers, Google API keys), credential
  assignments, and the **entire git history** (`git log --all -G…`) — zero hits. The only match was
  a deliberate test fixture (`dtc-secret-value`). `orderflow_data.db*` and `*.log` are gitignored.
- **Guard, live (rebuilt exe + installed copy):** hostile `Host` → **403**, cross-origin POST →
  **403**, `Sec-Fetch-Site: cross-site` POST → **403**, loopback POST → **200**; CSP present; served
  `/desktop` byte-identical to the packaged `index.html` (`369fbbc6…`).
- **Injection surfaces:** parameterised SQL throughout (the single f-string is the fixed-literal
  tuple, F-08); **no upload/import endpoints exist** (no archive-extraction class); the URL fetcher's
  containment is pinned; config GET redacts credentials (pinned).
- **Desktop runtime:** pywebview without `js_api` (no Python bridge exposed to the page), no debug
  flag, WebView2 default sandbox; the single-instance mutex (F-08 note).
- **Dependencies/supply chain:** `uv.lock` present and consistent (`uv lock --check` green);
  `pip-audit` clean over the frozen set (59 packages); CycloneDX SBOM exported in CI and shipped
  (`97184c0b…`, 42 components); CI (`ci.yml`) pins every action to a commit SHA, runs with
  `permissions: contents: read` + `persist-credentials: false`, and executes the full gate stack on
  3.11 + 3.12.
- **Privacy:** no telemetry; screenshots sampled this pass contain no PII; docs paths reviewed
  (F-07, owner decision).
- **Public-release hygiene:** LICENSE (upstream MIT + owner's copyright), `THIRD_PARTY_NOTICES.md`,
  `SECURITY.md` with the private reporting route and the loopback-only statement; README counts were
  re-derived in §77; the artefact set is reproducible from the tree.

---

## 11. Dependency-safe remediation roadmap

**Stage 0 — baseline/observability (DONE this pass):** the regression pin + build refusal + startup
warning (F-01/F-02). One commit's worth of change; rolled back by reverting three files.

**Stage 1 — release-integrity fix (DONE):** `build_exe.py` payload completeness; artefacts rebuilt;
install journey re-run. Rollback: revert + rebuild.

**Stage 2 — correctness of records (DONE):** F-03 comment rewording. Zero runtime effect.

**Stage 3 — queued, cosmetic, next source-changing pass (owner-visible only):**
(a) F-05 log-hygiene exception filter (one handler; logging-only); (b) F-08 `usedforsecurity=False`
(one argument). Both are behaviour-identical in effect; deliberately not landed in this pass so the
verified artefact chain stays exactly reproducible. Each must travel with a full rebuild + the
gate stack (the F-01 lesson: a source change = a rebuild, or the artefact lies).

**Stage 4 — post-beta (weighed, deferred):** the per-view "module failed to load" notice (F-02's
full form); optional `/docs` off in packaged builds (F-04); static-SQL for the table-count helper
(F-08 optional); deeper venue fault injection + long-session profiling (carried from §76 notes).

---

## 12. Validation matrix

| Validation | Command/scenario | Expected | Actual | Status |
|---|---|---|---|---|
| Full suite, 3.12 | `.venv/Scripts/python.exe -m pytest orderflow_system -q` | green | **844 passed / 2 skipped (24.6 s)** | PASS |
| Full suite, 3.11 | `%LOCALAPPDATA%\Temp\ofap311\…\python.exe -m pytest …` | green | **844 / 2 (24.8 s)** | PASS |
| New pin bites (missing file) | rename `dashboard/static/tape.js`, run pin | FAIL | FAILED as required; restored | PASS |
| New pin bites (build drops root) | doctored `REQUIRED_DATA_RELS`, run pin | FAIL | FAILED as required; restored | PASS |
| UI reference audit | `.venv/Scripts/python.exe scripts/audit_ui_refs.py` | AUDIT CLEAN | **AUDIT CLEAN** (74 modules) | PASS |
| Lint | `uvx ruff check orderflow_system scripts` | clean | **All checks passed** | PASS |
| UI selftests | 22 × `node …/*.selftest.js` | 22 ok | **22/22 (search-ops: "all checks passed")** | PASS |
| Dependency audit | `uv pip freeze` → `uvx pip-audit -r …` | none | **No known vulnerabilities** | PASS |
| Static analysis | `uvx bandit -r orderflow_system -ll` | reviewed | 1 High / 17 Medium — all dispositions F-08 | REVIEWED |
| Lockfile | `uv lock --check` | consistent | exit 0 | PASS |
| Assets — repo tree | 47 local refs fetched | 200 | **47/47** | PASS |
| Assets — frozen exe (pre-fix) | same | — | **41/47 (6× 404)** — the defect | FAILED→FIXED |
| Assets — frozen exe (rebuilt) | same | 200 | **47/47** | PASS |
| Widget classes — exe pre-fix | CDP probe | defined | 6× `undefined`, Tape 0 rows | FAILED→FIXED |
| Widget classes — exe rebuilt | CDP probe | defined | **6/6 `function`**, Tape rows live, footprint canvas built | PASS |
| Guards — rebuilt exe | hostile Host / cross-origin POST / cross-site POST / loopback POST | 403/403/403/200 | **403/403/403/200** | PASS |
| Served shell identity | `sha256` of `/desktop` vs packaged file | equal | **equal (`369fbbc6…`)** | PASS |
| Soak — view churn + live feed | 8 cycles × 28 views + 96 s live | flat | intervals/MOs/canvases flat; heap sawtooth; 0 errors | PASS |
| Frame time | rAF deltas, Engine view, live | stable | median/p95/p99/max = **16.7/16.7/16.8/16.8 ms** (tree + exe) | PASS |
| Zip integrity | `zipfile.namelist()` + `testzip()` | 512 entries, clean | **512 entries, no corrupt member, 27,385,320 B** | PASS |
| Installer build | `installer/make_installer.ps1` (32-bit PS) | 0 errors | **0 errors / 4 warnings**, 28,455,930 B | PASS |
| Install journey (rebuilt Setup) | silent install → verify → smoke → silent uninstall | clean | **512 files installed; exe hash == dist (`8016d948…`); shortcut → installed exe; healthz 200 / hostile 403 / 47/47 assets / widgets live / 0 client errors; uninstall removed dir+shortcut+ARP; `%APPDATA%` untouched; dev shortcut restored** | PASS |
| Build freshness | `find … -newer dist/…exe` | none | **no source newer than the build** | PASS |
| Demo guards (sandbox) | unknown symbol on footprint/tape/… | `[]` | `[]` (carried + re-observed) | PASS |

Raw receipts: `%LOCALAPPDATA%\Temp\ofap_secaudit\` (`soak_metrics.json`, `view_activation.json`,
`assets_*.json`, `bandit.json`, `*_stdout.log`) and the sandboxes (`appdata`, `appdata2`,
`appdata_tree`, `appdata_inst`).

---

## 13. Final release checklist

- [x] Working tree reviewed (7 tracked files modified, all deliberate and listed above)
- [x] Version/tag/package metadata correct (0.1.0 beta; `v0.1.0-beta` is the owner's tag action)
- [x] License present (MIT, upstream notice + owner line)
- [x] README accurate (counts re-derived §77; installation paths verified against the tree)
- [x] No secrets committed (tree + full history scans clean)
- [x] Lockfile present and consistent (`uv lock --check`)
- [x] Clean install path exercised (CI runs 3.11 + 3.12 from `pyproject`; **and** the rebuilt Setup's
      silent install on this machine)
- [x] Lint / tests / audit / build pass (rows above)
- [x] Production smoke passes (frozen exe + installed copy + repo tree)
- [x] P0/P1 findings resolved (F-01 fixed and re-verified; no P0s existed)
- [x] Runtime validation completed (soak, guards, assets, widgets, install journey)
- [x] Known limitations documented (§14 + README + SECURITY.md)
- [x] Release artefacts inspected (hashes recorded; zip integrity; installed-file identity)
- [x] Rollback/release plan documented (rebuild recipe in `RELEASE_EVIDENCE`, stage plan §11)

---

## 14. Audit limitations and residual risk statement

**Not claimed:** this is not a proof of "zero bugs" or "fully secure". What is claimed is enumerated
above, each item tied to a command or probe that ran on this machine today.

**What could not be verified here:** physical multi-monitor behaviour (single display on this host —
the owner's pass); MT5 terminal paths (fixtures only — no terminal present); GitHub-side settings
(branch protection, secret scanning alerts) — repository settings live outside the tree; runtime
behaviour under adversarial market conditions beyond the fixture suite; the WebView2 runtime as
shipped on other machines (this host has it).

**Residual risk, stated:** (1) a same-user local process can reach the loopback API — inherent to a
no-login desktop app; the guard's scope is remote/cross-site reach, and that scope held under test.
(2) F-02's silent-degradation class can still occur for *widget* modules if a future build drops
them — now defended by the pin + build refusal + startup warning, but the UI itself still cannot
say "this view's module failed". (3) Cosmetics (F-05) and lint-noise (F-08) remain until the next
source-changing pass. (4) The docs publication-surface decision (F-07) is the owner's.

**Residual risk acceptance:** acceptable for a scoped v0.1.0-beta that is loopback-only,
market-data-only, and places no orders — and it is materially lower than at the start of this pass,
because the one defect that would have shipped a half-broken UI is fixed, pinned, and verified on
the actual artefacts users will download.
