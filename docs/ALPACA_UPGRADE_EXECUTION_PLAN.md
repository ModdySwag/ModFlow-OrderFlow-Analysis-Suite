# ModFlow OrderFlow Analysis Suite — Alpaca Upgrade & Live-Bridge Execution Plan

**Plan date:** 2026-09-15
**Target:** `C:\Users\<you>\OrderFlow-Analysis-Pro` (branch `master`, HEAD `b2ff4ee`)
**Deliverable of this document:** an executable, phase-by-phase plan for implementing the upgraded/new
suggestions in `Desktop\code.txt`, grounded in the current working tree (every file/line below was
verified against the tree on 2026-09-15, not recalled).

## Sources (merged — none of these are re-litigated here)

| # | Document | Role |
|---|----------|------|
| S1 | `C:\Users\<you>\Desktop\code.txt` | The Alpaca enhancement report: setup flow, search redesign, feed rules, error codes, perf |
| S2 | `C:\Users\<you>\Desktop\report.txt` | First line-level codebase audit (P1–P8) |
| S3 | `docs/AUDIT_REPORT_2026-09-15.md` | Merged audit = S1 + S2 + a fresh pass; contains the implementation order |
| S4 | `docs/ALPACA_INTEGRATION_PLAN.md` | Alpaca product plan: what Alpaca adds/cannot add, phases 0–5, safety §5, risk register §6 |

**Gate note (execplan §"Important constraints"):** there is no `04-spec-review.md` — this project does
not use the Hermes idea-workflow doc ladder. Planning therefore proceeds on **S3 + S4 as the approved
spec**, with this warning stated once, here. Nothing in this plan adds scope beyond S1–S4; where S3
left a choice open (Scanner view, MsgPack), the decision is recorded in §0 and applied consistently.

---

## 0. Fixed decisions (do not re-litigate during execution)

1. **Demo mode stays.** Every data endpoint gains an explicit `source` field (`"engine"` / `"demo"`).
   Demo payload shapes are frozen (the JS depends on their keys) — live payloads must match them.
2. **Order of work: live bridge first (Phase 1).** The search work in Phase 4 wants *live-updatable
   rows*; those are only honest once Phase 1 makes live endpoints actually live.
3. **One shared Alpaca stream per asset class.** The search subscribes/unsubscribes on that socket;
   it never opens its own (Alpaca allows 1 stream connection per endpoint on most plans — 406 on a
   second).
4. **No new Python dependencies for REST** (plain `urllib`, matching `desktop/alpaca.py`). Streaming
   uses the **`websockets`** library already declared in `pyproject.toml` (line 8). Live *option*
   quotes are MsgPack-only → **decision D-A: deferred**; option chains in this plan come from REST
   snapshots. Revisit D-A only if the owner explicitly accepts a `msgpack` dependency.
5. **Secrets** stay in the local config (`config_store`), are never echoed back, and are masked in the
   UI — the existing behaviour stays the benchmark.
6. **Paper-first for anything that could trade** (Phase 7 only): the ceremony in S4 §5 is mandatory.
7. **Alpaca publishes no order book.** Heatmap / Depth / participants'-intent views remain
   Bybit/MT5-only; on Alpaca symbols the UI must state the reason (capability flag, not an empty view).
8. **Scanner (S3 P7): keep it, don't de-list it.** `desktop/ui/scanner.js` already creates its nav item
   and view at runtime (`scanEnsureView`, button at scanner.js:68, view mounted at :95) and
   `/api/scanner` already has a live branch (dashboard/app.py:134–150). The "missing nav item" finding
   is true only for the *static* HTML — the fix is documentation/consistency (Phase 6), not new scope.
9. **Companion work (portfolio, paper trading)** is Phase 7 — sketched, not executed in this run; it is
   already scoped in S4 §4 phases 2–3.

---

## 1. Baseline (measured today — re-measure before starting)

```
cd C:\Users\<you>\OrderFlow-Analysis-Pro
.venv/Scripts/python.exe -m pytest orderflow_system -q          → 124 passed in 2.76s
.venv/Scripts/python.exe scripts/audit_ui_refs.py               → AUDIT CLEAN (76 routes, 0 missing ids)
.venv/Scripts/python.exe -m pytest orderflow_system/test_alpaca.py -q  → 13 passed
git status                                                       → M: config/settings.py, data/database.py, main.py;
                                                                   untracked: atlas/, docs/, assets/, AUDIT_REPORT
```

Run the app (desktop shell = pywebview, `desktop/launcher.py:main`):

```
.venv/Scripts/python.exe -m orderflow_system.desktop            # native window
.venv/Scripts/python.exe -m orderflow_system.desktop --browser  # browser
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 8099   # server only (agent smoke tests)
```

App shape (verified): `orderflow_system/{data,analytics,patterns,signals,alerts,config,atlas,dashboard,desktop}`.
UI modules are injected at runtime by `desktop/ui/atlas-v2.js:293–295` (`steady.js, guide.js, context.js,
market-pressure.js, intent.js, vwap.js, scanner.js, search.js, alpaca.js`) — **any new UI module must be
added to that list.**

Key anchors this plan builds on:

| Area | Anchor |
|---|---|
| Candle close (pipeline) | `main.py:80` `on_candle_close=self._on_candle_close`; `main.py:127` `InstrumentPipeline._on_candle_close` (analytics only) |
| Candle close (system, never called) | `main.py:464` `OrderflowSystem._on_candle_close_handler` (persists + broadcasts; calls `pipeline._on_candle_close` at :470) |
| Wired callbacks | `main.py:219` `pipeline._on_signals_callback = self._on_candle_signals` |
| Tick intake | `main.py:414` `_on_tick` (batch DB insert via `_tick_buffers`, `main.py:233`) |
| Desktop compensation | `desktop/engine.py:312` `_wire_candle_persistence`, called at `:492` from `EngineController.start` (`:459`) |
| Capabilities | `desktop/engine.py:201` `def capabilities(cymbols…)` (typo) |
| Control API | `desktop/api.py` `/api/control/*` (bootstrap, config, capabilities, datasources, instruments/*, engine/*, alpaca/*, mt5/test, telegram/test) |
| Alpaca client (built) | `desktop/alpaca.py` (urllib, rate limiter, staged probe, capability report, portfolio) |
| Alpaca UI card (built) | `desktop/ui/alpaca.js` (`alpacaStatusPill :52`, `alpacaCapabilities :69`, `alpacaCardHTML :99`, `alpacaEnsureCard :162`, `alpacaLoad`, `alpacaSubmit`, `alpacaWire`) |
| Alpaca config block | `desktop/config_store.py:208–212` (`enabled, paper, key_id, secret, view_symbols`) |
| Live/demo gaps | `dashboard/app.py`: footprint `:890` (returns demo at `:903`), tape `:909` (TODO `:912`), microstructure `:919` (TODO `:922`); demo fallbacks for instruments/scanner/markers/candles/profile/bias/signals/strategy/orderbook/delta/stats |
| WS channels | `dashboard/websocket_manager.py:22` (tick, candle, signal, trade_state, volume_profile, bias, orderbook, delta, stats) |
| Search | `desktop/ui/search.js` (`searchActions :43`, `searchBuildIndex :152`, `searchQuery :271`, `searchRender :380`, `searchRun :427`); static entries incl. `['Scanner','scanner',…]` and `['Alpaca account','settings',…]` (search.js:145–149) |
| Wizard | `desktop/ui/guide.js:422` `WIZ_STEPS` (title/render/collect/after), `renderStep :849`, `finishWizard :874` |
| Rail views | `desktop/ui/index.html:24–42` (18 items; no `alpaca`, no static `scanner`) |

---

## 2. Executor & environment

- Executor: Hermes agent (this machine) or any coding agent; Windows, git-bash shell, repo venv Python.
- Working dir: `C:\Users\<you>\OrderFlow-Analysis-Pro`. Pass forward-slash native paths to tools.
- Every phase ends in a **checkpoint** (commands + expected output). Paste the evidence line into the
  build log; do not proceed past a red checkpoint.
- TDD rule for behaviour tasks: write the failing test first (RED), implement (GREEN), keep the suite
  green. UI-only tasks (pure DOM/CSS) may use an audit + manual smoke as evidence instead — stated per task.
- Hotspots (serialize edits, one task at a time; expect conflicts if two tasks touch them):
  `dashboard/app.py`, `desktop/ui/search.js`, `desktop/ui/guide.js`, `desktop/engine.py`.

---

## Phase 0 — Baseline guardrails (hygiene before the main event)

**Goal:** a pushable safety net so the large phases can't silently regress the live/demo boundary.

### T1 — CI workflow
- **Files:** create `.github/workflows/ci.yml` (none exists; `.github/` holds only templates).
- **Steps:** job on `windows-latest`, Python 3.11, `pip install -e .[dev]`, then:
  `.venv/Scripts/python.exe -m pytest orderflow_system -q` and
  `.venv/Scripts/python.exe scripts/audit_ui_refs.py`.
- **Evidence:** the workflow file exists and the same two commands pass locally (baseline §1).

### T2 — `cymbols` typo
- **Files:** `desktop/engine.py:201,203` (`def capabilities(cymbols…)` → `symbols`); confirm call sites
  in `desktop/api.py` use keyword-or-positional correctly (`capabilities()` call at api.py:70–78).
- **Evidence:** `grep -rn "cymbols" orderflow_system` → no matches; `pytest -q` still green.

### T3 — Enum/string boundary helper (S3 §8.1)
- **Files:** new `orderflow_system/data/enums.py` with `as_value(x)` (returns `x.value` for enums, the
  string otherwise); replace the `hasattr(x, 'value') ? … : …` clusters at the **serialisation
  boundary** only (`dashboard/app.py`, `atlas/api.py`, `atlas/hub.py` payload builders).
- **Test-first:** `orderflow_system/test_enums.py` — `as_value(Side.BUY) == "buy"`,
  `as_value("buy") == "buy"`, enum stays enum inside detectors.
- **Evidence:** pytest green; `grep -c "hasattr(.*'value')" orderflow_system/dashboard/app.py` drops to 0.

### T4 — Document the baseline and commands
- **Files:** `CONTRIBUTING.md` (add "Tests & audit" section with the two commands and the 124-test baseline).
- **Evidence:** file contains the commands verbatim.

**Checkpoint 0:** `pytest orderflow_system -q` → ≥124 passed; `audit_ui_refs.py` → AUDIT CLEAN.

---

## Phase 1 — Live bridge: make the running engine the real data source (S2/S3 P1 — "the main event")

**Goal:** with the engine running, `/api/tape`, `/api/footprint`, `/api/microstructure` return **engine**
data; candle closes persist + broadcast through the *repo's* path (not the desktop compensation), and the
UI can state live-vs-demo in one place.

### T5 — Per-symbol tick ring buffer
- **Files:** `main.py` (`OrderflowSystem.__init__` near `:233`, `_on_tick` `:414`).
- **Steps:** `self._recent_ticks: dict[str, deque] = {}` with `deque(maxlen=500)`; append in `_on_tick`;
  add `def recent_ticks(self, symbol, count=200) -> list[Tick]` (newest-last).
- **Test-first:** `orderflow_system/test_live_bridge.py` — feed 600 ticks, assert `len(...) == 500`,
  order preserved, unknown symbol → `[]`.

### T6 — Wire the candle-close callback end-to-end (the actual P1 fix)
- **Files:** `main.py`.
- **Design:** follow the existing wiring pattern (`main.py:219`). In `OrderflowSystem.__init__` set
  `pipeline._on_candle_closed_callback = self._on_candle_closed`; in `InstrumentPipeline._on_candle_close`
  (`:127`) call it **after** the analytics pass with `(symbol, candle)`.
  Repurpose `_on_candle_close_handler` (`:464`) into `_on_candle_closed` **removing the
  `pipeline._on_candle_close(candle)` call at `:470`** (that would double-run analytics every close).
  It must: `await self.db.insert_candle(symbol, "1m", candle)`, `ws_manager.broadcast_candle(...)`
  (same payload as `engine.py`'s wrapper), `broadcast_delta(...)`, and store `self._last_candles[symbol]`.
- **Test-first:** with a fake ws_manager + temp DB — one closed candle → exactly one `insert_candle`,
  one `broadcast_candle`, one `broadcast_delta`; analytics run once (counter on the detector).
- **Evidence:** the new test; then a live smoke: engine on BTCUSDT for 2 minutes →
  `python -c "import sqlite3;print(sqlite3.connect('orderflow_data.db').execute('select count(*) from candles').fetchone())"` > 0.

### T7 — Retire the desktop compensation
- **Files:** `desktop/engine.py` (`_wire_candle_persistence :312`, call `:492`).
- **Steps:** once T6 lands, drop the wrapper (and its call), or reduce it to an assertion that the
  pipeline callback is the system method. Update the docstring that describes the old failure mode.
- **Evidence:** `EngineController.start()` still boots; candle rows accumulate via the repo path.

### T8 — `/api/tape/{symbol}` live
- **Files:** `dashboard/app.py:909–913`; helper test module `orderflow_system/test_payload_parity.py`.
- **Steps:** when `system` and `system.recent_ticks(symbol, count)` is non-empty → return those ticks in
  the demo payload shape (compare keys against `demo_data.demo_tape_trades` — the parity test asserts
  live ⊇ demo keys) with `"source": "engine"`; else demo with `"source": "demo"`.
- **Test-first:** FastAPI `TestClient` with an injected stub system (`set_system`, used by
  `desktop/api.py` engine_start) → assert engine rows + source; without system → demo + source.

### T9 — `/api/footprint/{symbol}` live
- **Files:** `dashboard/app.py:890–903`.
- **Steps:** from the pipeline's footprint state (the analytics already build footprint levels per bar —
  use the same structures `footprint.js` expects; mirror `demo_footprint`'s payload keys exactly).
  Keep the 404 for an unknown symbol; keep `source`.
- **Evidence:** test with a stub pipeline returning 3 levels; payload key-diff vs demo == empty.

### T10 — `/api/microstructure/{symbol}` live
- **Files:** `dashboard/app.py:919–923`.
- **Steps:** build the snapshot from pipeline state — last footprint bar, `delta_engine` cumulative +
  bar delta, latest signals by detector (absorption/initiative/sweep/exhaustion/divergence), pace and
  book state when the venue publishes one (Bybit/MT5); Alpaca symbols report `book: null` with a reason.
- **Evidence:** test asserting each top-level key of `demo_microstructure` is present.

### T11 — `source` fields on the already-live endpoints
- **Files:** `dashboard/app.py` (candles `:274`, volume-profile `:377`, bias `:510`, signals `:533`,
  delta `:844`, scanner `:134`, instruments `:100`, markers `:233`).
- **Steps:** add `"source": "engine"|"demo"` to every payload whose shape is a MAPPING (bias, orderbook,
  strategy-status, stats, microstructure — implemented). List endpoints (tape, footprint, candles, delta,
  signals, instruments, scanner, markers) cannot carry a top-level key without breaking the JS, so their
  live/demo truth comes from `/api/control/live-status`; that policy is documented in `app.py`.
- **Evidence:** one test iterating the mapping endpoints with a stub system asserting the key exists,
  plus the live-status map test.

### T12 — One live-status surface (S2 §2.3)
- **Files:** `desktop/api.py` (new `GET /api/control/live-status`), `desktop/engine.py` (`capabilities()`
  gains a `live` map), `desktop/ui/ui.js` (header chip + per-view badge), `desktop/ui/guide.js` (tooltip).
- **Steps:** the map is `{"tape": "live"|"demo", "footprint": …, "microstructure": …, "candles": …,
  "scanner": …, "strategy": …, "profile": …, "book": …}` derived from engine state. UI: a single chip in
  the status bar ("live" green / "partial" amber with a hover list / "demo" grey); replace the static
  per-panel warnings in `ui.js` (tape/footprint notices) with links to that chip.
- **Test-first:** Python test builds the map for engine-stopped vs stubbed-engine states.
- **Evidence:** chip renders (manual smoke screenshot) + audit clean.

### T13 — End-to-end live-bridge test
- **Files:** `orderflow_system/test_live_bridge.py` (extend).
- **Steps:** synthetic ticks → candle close → assert DB + broadcasts + `/api/tape` + `/api/footprint` +
  `/api/microstructure` all serve engine data with `source == "engine"` in one flow.
- **Evidence:** the test in the suite; suite count grows and stays green.

**Checkpoint 1:** `pytest orderflow_system -q` green **and** manual smoke — app → Start engine (BTCUSDT)
→ in 2 minutes: Tape view fills with *real* prints (no demo notice), Footprint shows live levels, the
status chip reads "live", and `candles` table grows:
`sqlite3 orderflow_data.db "select count(*) from candles"`.

---

## Phase 2 — Alpaca discoverability + setup wizard (S1 §3, S3 P3/P4)

**Goal:** Alpaca is findable in three seconds (landing card, rail item, banner, shortcut, search) and
onboardable through one guided flow, reusing the card logic that already exists.

### T14 — Overview "Alpaca" card
- **Files:** `desktop/ui/index.html` (overview section `:68`), new `desktop/ui/alpaca-card.js`
  (added to the boot list `atlas-v2.js:293–295`), `desktop/ui/ui.js` (refresh hook).
- **Steps:** status pill (reuse `alpacaStatusPill()`), one-line capability summary from
  `alpacaCapabilities()`, and one button "Open Alpaca setup" → `showView('alpaca')`.
  Do not duplicate capability rendering — import it.
- **Evidence:** audit clean; manual smoke (card visible on Overview, pill matches the Settings card state).

### T15 — `alpaca` nav item + view
- **Files:** `desktop/ui/index.html:24–42` (nav button, e.g. between Instruments and Settings), a
  `<section class="view" data-view="alpaca">`, `desktop/ui/guide.js` TIPS entry
  (`'.nav-item[data-view="alpaca"]'`), `desktop/ui/ui.js` `ensurePanel` handling.
- **Steps:** the view hosts the full Alpaca card (keys, capability table, portfolio links) as primary
  content; a link to Settings for the rest of the config. `showView('alpaca')` must open it.
- **Evidence:** audit clean (new ids/routes referenced correctly) + smoke.

### T16 — Not-connected banner
- **Files:** `desktop/ui/ui.js` (overview render), `desktop/config_store.py` (add
  `ui.banner_dismissed_alpaca: false` to defaults).
- **Steps:** dismissible banner on Overview while `alpaca.enabled` is false: "Connect Alpaca to enable US
  equities, options, news and the market calendar. [Set up now]" → `showView('alpaca')`. Dismiss persists
  in config; re-appears next session if still not connected (per S3 §4.3).
- **Evidence:** config round-trip test (`config_store` sanitise keeps the new key) + smoke.

### T17 — Alt+A shortcut
- **Files:** `desktop/ui/ui.js` (keyboard handler section), `desktop/ui/guide.js` (keyboard table).
- **Steps:** `Alt+A` → `showView('alpaca')`; must not fire while typing in inputs.
- **Evidence:** smoke + audit clean.

### T18 — Search entries for Alpaca (S3 §4.5, §6.1.3, §6.1.4)
- **Files:** `desktop/ui/search.js` (entries list `:145–149`, `searchRun :427`).
- **Steps:** (a) change `['Alpaca account','settings',…]` → an **Actions** entry
  "Open Alpaca setup" that goes straight to `showView('alpaca')` and focuses the key input after render;
  (b) add a Help entry "Alpaca: how to get API keys" (keywords: `alpaca broker keys paper trading signup
  account`) whose run opens the guide's Alpaca how-to (`alpaca.js` data-help="alpaca" target).
- **Evidence:** audit clean + smoke (type "alpaca" → both results, both land correctly).

### T19 — Wizard step "Alpaca (optional)" (S1 §3.2, S3 §5)
- **Files:** `desktop/ui/guide.js` (`WIZ_STEPS :422`, inserted **after the Instruments step, before
  alerts**), `desktop/ui/alpaca.js` (reuse `alpacaSubmit`/`alpacaMsg`), `desktop/config_store.py`
  (wizard resume state).
- **Panels (all skippable, wizard never blocks):**
  1. What Alpaca adds (one paragraph, honest limits: no order book, IEX real-time, SIP delayed 15 min).
  2. Sign up / paper account (link `https://app.alpaca.markets/signup`, note paper-only countries).
  3. Get API keys (Home → generate; secret shown once — warning).
  4. Paper vs Live toggle (endpoints, funding, KYC; default Paper, pre-fill environment).
  5. Capability preview per tier (Basic vs Algo Trader Plus — the S1 §3.2 Step 4 table).
  6. Paste keys + "Test connection" → `/api/control/alpaca/test` → staged result (keys → auth → api →
     ready) + capability report; save via `/api/control/alpaca/save`.
  7. Done / upgrade path ($2,000 margin threshold; $30,000 business minimum) + link to the how-to.
- **Steps:** `collect()` writes `config.alpaca` (paper flag, keys) — never logs the secret; state persists
  so a user who leaves to sign up can resume mid-flow.
- **Test-first (Python):** `config_store` sanitise/merge test with the alpaca block from the wizard shape.
- **Evidence:** wizard runs end-to-end against a stub/test key (staged error surfaces correctly);
  `alpaca.enabled` flips true in the config file (read it back, don't trust the UI).

### T20 — Phase 2 evidence pack
- **Steps:** audit clean; smoke screenshots (Overview card, Alpaca view, banner, wizard step);
  `pytest -q` green.
- **Evidence:** the three artefacts above.

**Checkpoint 2:** a fresh user can find Alpaca from the landing page, the rail, the shortcut, the search
box and the wizard, and can go from zero to "Paper Connected" inside the wizard without leaving the app
except to sign up.

---

## Phase 3 — Alpaca market data: shared REST + one stream per asset class (S1 §4.2, S4 phase 1)

**Goal:** Alpaca becomes a first-class data source for the existing analyzers, with explicit subscription
management and honest capability gating. No depth views on Alpaca symbols, by design.

### T21 — Internal models + normalizer
- **Files:** `data/models.py` (add `Quote` dataclass, `slots=True`, next to `Tick :45`),
  new `data/alpaca_normalize.py`.
- **Steps:** `normalize_stock_trade(msg)->Tick`, `normalize_quote(msg)->Quote`,
  `normalize_crypto_trade`, `normalize_options_trade`; field maps per S1 §6.1 (stocks trade
  `T,S,i,x,p,s,c,t,z`; quote `ax,ap,as,bx,bp,bs`; crypto `p,s,t,i,tks`; options `T,S,t,p,s,x,c`).
  Aggressor classification against the current NBBO happens in the analytics, not here.
- **Test-first:** `test_alpaca_normalize.py` with recorded JSON fixtures (one per message type) — the
  normalized Tick/Quote carries price/size/side/timestamp/symbol.
- **Evidence:** the fixture tests.

### T22 — REST client + session gating
- **Files:** new `data/alpaca_feed.py` (`AlpacaFeed`), reusing the limiter style from `desktop/alpaca.py`.
- **Steps:** urllib calls for `/v2/clock`, `/v2/assets`, `/v2/stocks/{sym}/bars`, `/v2/stocks/{sym}/snapshot`,
  `/v2/stocks/{sym}/trades`, `/v1beta3/crypto/{loc}/…`; client-side budget 150 req/min (< the 200/min plan
  limit) with 429 backoff; `is_open()` from the clock drives polling cadence (no hot polling when closed);
  24 h disk cache for assets in the config dir.
- **Test-first:** `test_alpaca_feed.py` with a stub transport: budget never exceeded over a simulated
  minute; closed-market path does not poll bars; clock errors degrade soft.
- **Evidence:** the stub tests + one live keyless crypto-history call (works without keys).

### T23 — Stream client (one socket, auth-once)
- **Files:** `data/alpaca_feed.py` (`AlpacaStream`), using the `websockets` dependency.
- **Steps:** connect `wss://stream.data.alpaca.markets/v2/{iex|sip|delayed_sip}` and
  `wss://…/v1beta3/crypto/{us|us-1|eu-1}`; send `{"action":"auth","key":…,"secret":…}` within **10 s**;
  `subscribe`/`unsubscribe` per channel (`trades`, `quotes`, `bars`, `dailyBars`, `updatedBars`,
  `statuses`, `lulds`, `imbalances` — never `*`); reconnect with exponential backoff **and re-auth
  immediately**; map Alpaca's error frames (400/401/402/403/404/405/406/407/409/410/413/500 → S1 §5.4)
  to typed exceptions with user-facing text.
- **Test-first:** `test_alpaca_stream.py` — error-frame → exception mapping table test; auth-sent-within-10s
  assertion against a fake socket; unsubscribe idempotency.
- **Evidence:** the mapping test; optional env-gated live test against the **test stream**
  `wss://stream.data.alpaca.markets/v2/test` (symbol `FAKEPACA`, no keys) — `RUN_ALPACA_TESTSTREAM=1`.

### T24 — Subscription manager
- **Files:** `data/alpaca_feed.py` (`SubscriptionManager`), `desktop/api.py`
  (`GET/POST /api/control/alpaca/subscriptions`), `desktop/config_store.py` (active set persistence).
- **Steps:** caps: 30 stock symbols / 200 option quotes on Basic (configurable by entitlement); add/remove
  with idempotency; LRU trim when over cap **with a visible warning** (never silently drop); the active
  set is what the search and the tape view subscribe to.
- **Test-first:** caps, idempotency, trim order, warning emission.
- **Evidence:** tests + `POST` round-trip via TestClient.

### T25 — Engine wiring + capability gating
- **Files:** `orderflow_system/config/settings.py` (`DataSource` enum `:85` gains `alpaca`/`both`),
  `desktop/engine.py` (`EngineController.start` builds the feed; `capabilities()` reports per-source
  depth), `desktop/api.py` (`/datasources` `:80` reflects availability, `/instruments/catalog` `:139`
  can list Alpaca symbols once keys are linked).
- **Steps:** starting the engine with `data_source` including `alpaca` starts `AlpacaFeed` for the
  configured Alpaca symbols only; symbols from Alpaca carry a `capabilities.depth = false` + reason, and
  Heatmap/Depth views show the reason instead of an empty canvas for those symbols.
- **Evidence:** engine start with a stub feed (no network) creates pipelines for Alpaca symbols; depth
  views gated in the capability payload test.

### T26 — Capability surface for the UI (plan-tier awareness)
- **Files:** `desktop/api.py` (`/capabilities :70`), `desktop/ui/alpaca.js`, `desktop/ui/guide.js`.
- **Steps:** report `{alpaca: {feeds: ["iex"], options_feed: "indicative", delayed: true, symbol_limit: 30,
  quote_limit: 200, rest_per_min: 200}}`; the UI hides/disables SIP/OPRA selectors unless entitled and
  shows the upgrade line (S1 §8 caveats).
- **Evidence:** payload test for a Basic-shaped probe and a plus-shaped probe (stub).

### T27 — Test-stream integration test (CI-safe)
- **Files:** `test_alpaca_teststream.py`.
- **Steps:** skipped unless `RUN_ALPACA_TESTSTREAM=1`; connects, subscribes `FAKEPACA`, asserts a trade
  arrives within 30 s, disconnects cleanly.
- **Evidence:** run once locally with the env var (documented in the test docstring).

### T28 — Demo parity for Alpaca symbols
- **Files:** `dashboard/demo_data.py`.
- **Steps:** demo generator can serve plausible AAPL/SPY rows so the UI (search chips, tape) is
  exercisable with no keys — same shapes as live.
- **Evidence:** demo payload key-diff vs live payload == empty (shared with T9's test helper).

### T29 — Docs: data feed reference
- **Files:** new `docs/ALPACA_DATA_FEED.md` (from S1 §5.1–§5.4: clients, stream URLs, auth, error table,
  tier limits) linked from the user guide.
- **Evidence:** file exists; USER_GUIDE links it.

### T30 — Live smoke with paper keys
- **Steps:** link real paper keys (user provides), stream IEX for 3 of the configured symbols during
  market hours; watch the Tape/Order Flow/Delta update and the subscription list stay ≤ 30.
- **Evidence:** screenshot + the engine log line showing the feed + subscription count.

**Checkpoint 3:** `data_source: "alpaca"` streams a US equity through the existing analyzers
(tape/delta/VWAP/profile/CVD), depth views state their reason for those symbols, a market close produces
no error spam, and `pytest -q` + audit are green.

---

## Phase 4 — Search redesign for order-flow power users (S1 §4, S3 P5)

**Goal:** the command palette stops being only an app-index and becomes a **market** instrument: live
symbols, feed honesty, option chains, operators, multi-select — all fed by the one shared stream.

### T31 — Symbol universe service
- **Files:** `desktop/api.py` (new `GET /api/control/search/symbols?q=&limit=`), `data/alpaca_feed.py`
  (assets cache), `desktop/config_store.py` (`search.recents`, `search.pins`).
- **Steps:** merge sources: local recents/pins → Alpaca assets (24 h cache; equity/ETF) → crypto universe
  → local instruments (existing aliases, e.g. NAS100/USTEC fuzzy hits). Without keys: crypto + recents +
  local instruments only (honest degradation).
- **Test-first:** ranking test (exact symbol > prefix > fuzzy), limit, and the no-keys path.
- **Evidence:** pytest + one curl with the engine running.

### T32 — Palette: "Symbols" result category
- **Files:** `desktop/ui/search.js` (`searchBuildIndex :152`, `searchQuery :271`, `searchRender :380`).
- **Steps:** async fetch (150 ms debounce) merged into the render; `Enter` on a symbol result switches
  the instrument selector and opens the configured default view (order-flow default: footprint for
  tape/footprint users — expose the choice in settings).
- **Evidence:** audit clean + smoke (type "AAP", see asset rows, Enter switches the app).

### T33 — Rich result rows
- **Files:** `desktop/ui/search.js` (+ small canvas sparkline helper).
- **Steps:** symbol (large), name, asset-type badge, last/%-change, feed chip (`IEX`, `SIP`, `Delayed SIP`,
  `Indicative`, `OPRA`, `Crypto Alpaca`, `Crypto Kraken`), market-status dot (open/pre/after/closed/halted).
- **Evidence:** audit clean + smoke with a stubbed market-status payload.

### T34 — Live-updatable rows through the shared stream
- **Files:** `dashboard/websocket_manager.py` (new `search` channel + `broadcast_search_rows`),
  `desktop/api.py` (active-set ↔ subscription manager bridge), `desktop/ui/search.js` (row patcher).
- **Steps:** reuse the manager's existing throttle table (`websocket_manager.py:68–78`, per-symbol window at
  `:114–121`) for the new channel, and add a **coalescing batcher** on top: the palette's visible rows are
  the active set; backend pushes batched updates every ~300 ms (never per message — 407 slow-client
  protection); frontend patches only visible rows and throttles to 200 ms; cap warnings at 30 stocks /
  200 option quotes with an inline "remove or upgrade" hint; expose counters (`seen / coalesced / dropped`)
  for the Logs view.
- **Test-first:** batcher test (N messages in → ≤ ceil(N) batches out within the window), cap warning test,
  coalescing-counter test.
- **Evidence:** tests + smoke (open the palette on a live AAPL, watch bid/ask tick without a full re-render).

### T35 — Result → workspace navigation
- **Files:** `desktop/ui/search.js` (`searchRun :427`), `desktop/ui/ui.js` (`showView`).
- **Steps:** `Enter` = open in current workspace; `Ctrl/Cmd+Enter` = open in a new panel/tab;
  `Ctrl/Cmd+Shift+Enter` = option chain (equities only, when entitled).
- **Evidence:** audit clean + smoke for all three.

### T36 — Expanded search: operators + sort
- **Files:** new `desktop/ui/search-ops.js` (pure parser, added to `atlas-v2.js:293` boot list),
  `desktop/ui/search.js` (Shift+Enter toggles the section).
- **Steps:** operators `type:`, `exchange:`, `underlying:`, `exp:min|max`, `strike:>N|<N`, `vol:>1M`;
  sort by symbol/name/last/%change/volume/feed; comma-separated multi-symbol paste.
- **Test-first:** `search-ops.js` ships with a self-test runnable in Node
  (`node orderflow_system/desktop/ui/search-ops.selftest.js`) — skip gracefully where Node is absent;
  cases: `type:option underlying:AAPL strike:>200 exp:max`, malformed input → free text.
- **Evidence:** the self-test output + smoke.

### T37 — Recents, pins, watchlist quick-add
- **Files:** `desktop/ui/search.js`, `desktop/config_store.py` (`watchlist: []`).
- **Steps:** a "Recent / pinned" section above live results; `Ctrl/Cmd+Click` multi-select →
  "Add to watchlist" (persists) and/or "Open multi-symbol compare".
- **Evidence:** config round-trip test + smoke.

### T38 — Option chain panel
- **Files:** `desktop/ui/search.js` (+ chain renderer), `data/alpaca_feed.py` (REST chain + snapshot),
  `desktop/api.py` (`GET /api/control/alpaca/chain?underlying=&exp=`).
- **Steps:** strikes × expiries grid with bid/ask from the chain snapshot; ATM/ITM/OTM quick buttons;
  click a strike → searches that contract; per-contract "live" toggle that subscribes on the shared
  options socket — **disabled with a reason** while D-A (MsgPack) is undecided; honest `Indicative` chip.
- **Test-first:** chain payload mapping test (stub REST), expiry sorting, strike filter boundaries.
- **Evidence:** tests + smoke on an underlying with a linked account.

### T39 — Multi-feed comparison (advanced)
- **Files:** `desktop/ui/search.js` or a small compare panel; `desktop/api.py` (feed pair endpoint).
- **Steps:** IEX vs SIP (equities) / Alpaca crypto vs Bybit crypto — side-by-side last + a discrepancy
  indicator; only offered when both feeds are entitled (never promise SIP to Basic).
- **Evidence:** stub test for entitlement gating + smoke with an Algo-shaped stub.

### T40 — Keyboard set completion + tooltips
- **Files:** `desktop/ui/search.js`, `desktop/ui/guide.js` (shortcut table + tooltips per S1 §4.3.6).
- **Evidence:** audit clean; the guide's shortcut table matches the handlers.

### T41 — Performance hardening
- **Files:** `desktop/ui/search.js` (virtualize long lists, canvas sparklines, visible-row-only patching),
  `desktop/api.py`/`websocket_manager.py` (batching, backpressure counter).
- **Steps:** assert the debounce/throttle constants in code (150 ms query, 200–300 ms rows) and add a
  "messages seen / dropped / coalesced" counter surfaced in Logs.
- **Test-first:** batcher stress test (5 000 messages → bounded batches, no unbounded queue).
- **Evidence:** test + smoke on the busiest instrument available.

### T42 — Alpaca setup as first-class results (verify)
- **Steps:** re-verify T18 after the palette rework (entry still lands on the Alpaca view, focuses input).
- **Evidence:** smoke.

**Checkpoint 4:** typing a ticker in the palette returns live Alpaca symbols with honest feed chips and
market status; Enter lands on that symbol's live view; the option chain opens for an equity; operators
filter correctly; the subscription count never exceeds the plan's cap; pytest + audit green.

---

## Phase 5 — Config consolidation (S2/S3 P2)

### T43 — Golden snapshot first (the safety net)
- **Files:** new `orderflow_system/test_config_golden.py`.
- **Steps:** iterate every instrument the app supports, call its `get_*_config()`, serialise to a stable
  JSON (dataclass `asdict`, enums to `.value`), compare against a checked-in golden file
  (`orderflow_system/testdata/config_golden.json`).
- **Evidence:** the test passes against today's code (proves the net catches changes).

### T44 — Refactor to bank + overrides
- **Files:** `config/settings.py` (`:249–898`).
- **Steps:** `InstrumentDefaults` bank per class (indices, metals, energy, forex-major, stocks, crypto) +
  `INSTRUMENT_OVERRIDES` for the handful of tuned numbers (NAS100 0.1/1.0, DJ30 1.0/5.0, NIKKEI 1.0/50.0
  ASIAN session, …) + `get_config_for(instrument)`; keep the existing `get_*_config()` names as thin
  wrappers so imports elsewhere don't change.
- **Evidence:** T43 golden test green **unchanged**; `wc -l config/settings.py` drops materially.

### T45 — Prove the ergonomics
- **Steps:** add one new instrument (e.g. `get_amzn…` variant or a new index) as a one-line override +
  one wrapper; golden file grows by exactly that entry.
- **Evidence:** diff of the golden file = one new block.

**Checkpoint 5:** golden test green, suite green, new instrument added in < 5 lines.

---

## Phase 6 — Consistency, docs, final polish (S3 P6/P7/P8)

### T46 — Scanner: confirm the runtime pattern (+ optional order-flow mode)
- **Steps:** verify `scanner.js` mounts its own nav item + view (it does — `scanEnsureView`, button at
  `:68`, view mounted at `:95`), and that `/api/scanner` serves live rows when the engine runs
  (it does — `app.py:134–150`, ranking `system.pipelines` by strategy status). Record the runtime-injection
  pattern once (`atlas-v2.js:293–295` loads 9 self-mounting modules) so the static-HTML mismatch stops being
  reported as a gap. Optional enhancement: add `mode=orderflow` to `/api/scanner`, backed by
  `atlas/hub.py:snapshot_scanner :443`, for the column ranking the guide promises — one endpoint, two modes.
- **Evidence:** note in `docs/USER_GUIDE.md` + smoke (Scanner reachable from the rail at runtime); if the
  mode lands, a payload test for each mode.

### T47 — Guide/search drift pass (S3 §8.5)
- **Files:** `desktop/ui/guide.js`, `desktop/ui/search.js`.
- **Steps:** align Strategy/Performance descriptions with their endpoints' actual live state
  (post-Phase-1); fix the "wizard button above Overview" wording; make every promise either true or
  labelled "backend-ready, UI pending".
- **Evidence:** audit clean; a manual pass over the guide's claims list.

### T48 — Docs set
- **Files:** `docs/ALPACA_SEARCH_REFERENCE.md` (palette, operators, shortcuts, feed chips — from S1 §4),
  `docs/USER_GUIDE.md` updates (Alpaca view, wizard step, live/demo chip), `docs/ALPACA_DATA_FEED.md` (T29).
- **Evidence:** the three docs exist and are linked from the guide.

### T49 — Release notes for the beta build
- **Files:** `README.md` / new `docs/RELEASE_NOTES_<date>.md`; refresh the Desktop `beta_build` folder.
- **Evidence:** the folder builds and runs (shortcut smoke).

### T50 — Final gate
- **Steps:** full suite + audit + the manual smoke checklist (engine live, Alpaca linked, palette live
  rows, option chain, wizard, banner, shortcut) on a cold start.
- **Evidence:** the checklist with each line ticked and its command output.

**Checkpoint 6:** pytest + audit green; every S1/S3 promise either implemented or explicitly labelled
not-yet; docs match the UI.

---

## Phase 7 — Companion (deferred, already scoped — do not start without an explicit go)

Per S4 §4 phases 2–3, with the safety ceremony in §5: portfolio view (`portfolio.js` over the built
`/api/control/alpaca/portfolio`), then paper trading (order ticket, lifecycle stream, guardrails:
paper default, typed-phrase for live, notional/day caps, kill switch, dry-run alert-driven orders).
Task cards will be produced when this phase is picked up; they are intentionally **not** in this run's
scope.

---

## Verification map (source recommendation → proving tasks)

| Source item | Implementation | Proof |
|---|---|---|
| S1 §3.1 landing card / nav / banner / shortcut | T14, T15, T16, T17 | audit clean + smoke screenshots |
| S1 §3.2 wizard flow (steps 1–7) | T19 | wizard run against a real key; config read-back `alpaca.enabled=true` |
| S1 §4.2 shared stream, no socket-per-lookup | T23, T24, T34 | subscription-manager tests; 406 avoided (one socket asserted in tests) |
| S1 §4.2.4 autocomplete sources | T31 | ranking tests + no-keys path |
| S1 §4.3.1–4.3.2 palette + expanded search | T32, T36, T37 | ops self-test; smoke |
| S1 §4.3.3 live rows | T33, T34 | batcher tests + smoke |
| S1 §4.3.4 option chain | T38 | chain mapping tests + smoke |
| S1 §4.3.5 multi-feed comparison | T39 | entitlement-gating test |
| S1 §4.3.6 keyboard | T40 (T35) | guide table vs handlers; audit |
| S1 §4.3.7 / §6.10 performance | T5, T34, T41 | ring-buffer test; batcher stress test |
| S1 §5.3 auth rules (10 s, re-auth) | T23 | fake-socket timing test |
| S1 §5.4 error table | T23 | mapping table test |
| S1 §6.1 normalizer + ring buffer + incremental | T21, T5 | fixture tests |
| S1 §6.2 plan-tier awareness | T26 | entitlement payload tests |
| S1 §6.3 frontend canvas/virtualization | T33, T41 | code evidence + smoke |
| S1 §6.4 security/config | existing + T19 | config sanitise test; no secrets in logs |
| S1 §6.5 docs | T29, T48 | docs exist + linked |
| S1 §7 implementation order | Phases 0–6 | this plan |
| S3 P1 live/demo bridge | T5–T13 | `test_live_bridge.py` + `source` fields + status chip |
| S3 P2 config repetition | T43–T45 | golden test |
| S3 P3 Alpaca discoverability | T14–T18 | 5 entry points reachable |
| S3 P4 wizard step | T19 | wizard run |
| S3 P5 search reach | T31–T42 | per-task tests |
| S3 P6 typo / enum normalisation | T2, T3 | grep + tests |
| S3 P7 Scanner | T46 | verified runtime view + doc |
| S3 P8 doc drift | T47 | audit + guide pass |
| S3 §9 order | Phase order matches, with T1–T4 hoisted as Phase 0 | this plan |
| S4 phase 1 data source | T21–T30 | checkpoint 3 |
| S4 phases 2–3 | Phase 7 (deferred) | not in this run |

---

## Checkpoints summary

| # | Command(s) | Expected |
|---|---|---|
| 0 | `pytest orderflow_system -q` + `audit_ui_refs.py` | ≥124 passed, AUDIT CLEAN, CI file exists |
| 1 | same + live smoke (engine on BTCUSDT) | tape/footprint/microstructure `source=engine`; chip "live"; candles table grows |
| 2 | audit + wizard run | Alpaca reachable 5 ways; wizard reaches "Paper Connected"; `alpaca.enabled=true` |
| 3 | `pytest -q` + IEX smoke | equity streams through analyzers; depth gated with reason; no close-time spam |
| 4 | `pytest -q` + audit + palette smoke | live symbol rows, chain, operators; subscription cap respected |
| 5 | `test_config_golden.py` | green before and after refactor; file size cut |
| 6 | `pytest -q` + audit + cold-start checklist | all green; promises labelled; docs updated |

## Definition of done

1. With the engine running, no view silently shows demo data: every endpoint reports `source`, one
   status chip explains the state, and the per-panel warnings are gone.
2. Alpaca is findable from the landing card, rail, banner, shortcut, palette and wizard; the wizard takes
   a new user from zero to "Paper Connected" and survives a mid-flow interruption.
3. Alpaca symbols stream through the existing analyzers on **one** socket per asset class with explicit,
   capped subscription management, and depth-dependent views state their reason on those symbols.
4. The palette searches the live market (symbols, feeds, status, chains, operators, multi-select) and
   its rows update live without exceeding the plan's limits or the client's throughput budget.
5. `pytest orderflow_system -q` and `scripts/audit_ui_refs.py` are green at every checkpoint, and CI runs
   both on push.
6. No new runtime dependency beyond `websockets` (already declared); live option quotes remain behind
   decision D-A.

## Execution log

### Phase 0 — Baseline guardrails — **DONE (2026-09-15)**

| Task | Status | Evidence |
|---|---|---|
| T1 CI workflow | ✅ | `.github/workflows/ci.yml` (windows-latest, `pip install -e .[dev]`, pytest + audit) |
| T2 `cymbols` typo | ✅ | `grep -rn cymbols orderflow_system` → no matches; parameter renamed, shadowing removed |
| T3 `as_value` boundary helper | ✅ | `data/enums.py` + `test_enums.py` (6 tests); 26 mechanical edits across 9 files; `hasattr(…'value')` left only in the helper's own docstring |
| T4 CONTRIBUTING test/audit section | ✅ | section added with both commands + the 130-test baseline |

Checkpoint 0: **130 passed**, `AUDIT CLEAN`.

### Phase 1 — Live bridge — **DONE (2026-09-15)**

| Task | Status | Evidence |
|---|---|---|
| T5 tick ring buffer | ✅ | `OrderflowSystem._recent_ticks` (deque(maxlen=500)) + `recent_ticks()`; bounded/ordered test |
| T6 candle-close wiring | ✅ | new `_on_candle_closed` callback wired like `_on_signals_callback`; old `_on_candle_close_handler` deleted (its `pipeline._on_candle_close` call would have double-run analytics); test asserts exactly one analytics pass + one persist + one broadcast per candle |
| T7 retire desktop compensation | ✅ | `_wire_candle_persistence` → `_verify_candle_wiring` (assertion only); start() updated |
| T8 `/api/tape` live | ✅ | returns engine rows from the ring buffer; demo fill only while warming |
| T9 `/api/footprint` live | ✅ | `_live_footprint_bars` from the pipeline's footprint history, demo-shaped |
| T10 `/api/microstructure` live | ✅ | `_live_microstructure` (delta, absorption/initiative/exhaustion/divergence from live signals, session from the instrument config, documented market-state heuristic); `source` field |
| T11 `source` fields | ✅ (adapted) | mapping payloads (bias, orderbook, strategy-status, stats, microstructure) carry `source`; list payloads (tape, footprint, candles, delta, signals, instruments, scanner, markers) cannot without breaking the JS — the live-status map is their source of truth (documented in `app.py`) |
| T12 live-status map + UI chip | ✅ | `engine.live_status()` → `/api/control/live-status`; `#livePill` chip in the status bar; per-panel demo notices now conditional on the map; panels re-pull when the engine starts |
| T13 e2e test + parity | ✅ | `test_live_bridge.py` (10 tests) + `test_payload_parity.py` (3 tests, live ⊇ demo keys) |

Checkpoint 1 (headless live run, engine on Bybit BTCUSDT/ETHUSDT/SOLUSDT):

```
20 s → overall "live"; tape/volume_profile/bias/orderbook live, footprint/candles/microstructure warming
80 s → every endpoint "live" (first candle closed)
tape  → real prints, e.g. {"time":1789426218.357,"price":78551.4,"size":0.003,"side":"buy"}
footprint → 60 demo bars before the first close, then live bars (1 → 2 as minutes closed)
microstructure → {"source":"engine","marketState":"REBALANCING","session":{"name":"full_day",…},"delta":{"cumulative":-3.4,…}}
bias/stats → source "engine" while running, "demo" after stop
candles table → BTCUSDT 751 · ETHUSDT 126 · SOLUSDT 124 rows written via OrderflowSystem._on_candle_closed
final suite: 141 passed · audit_ui_refs: AUDIT CLEAN (routes 76→77, ids 168→169)
```

### Phase 2 — Discoverability — **DONE (2026-09-15)**

| Task | Status | Evidence |
|---|---|---|
| T14 Overview card | ✅ | new `desktop/ui/alpaca-card.js` (boot list `atlas-v2.js`); reuses `alpacaStatusPill()` / `alpacaCapabilityRow()`, no duplicated rendering; live in the browser smoke |
| T15 `alpaca` nav item + view | ✅ | rail item between Instruments and Settings, `<section data-view="alpaca">` hosting the shared card + the symbol list; `ensurePanel('alpaca')`; TIPS entries |
| T16 not-connected banner | ✅ | dismissible, persisted as `ui.banner_dismissed_alpaca` in the config (read back from `config.json` after clicking "Not now"); cleared at the next start while unlinked |
| T17 Alt+A | ✅ | real key events verified: fires from a normal view, ignored while the search box has focus |
| T18 search entries | ✅ | `searchQuery('alpaca')` returns Actions "Open Alpaca setup", Actions "Alpaca: how to get API keys", Help, Views, Guide and settings hits |
| T19 wizard step | ✅ | step 6/10 "Alpaca (optional)": what it adds, signup URL + Copy, key form, paper/live, capability preview, live test; bogus keys → Alpaca's mapped staged error and **nothing stored** (`config.json` alpaca block unchanged); `ui.wizard_resume_step` persists a mid-flow exit and clears on finish |
| T20 evidence pack | ✅ | `docs/phase2/*.png` (Overview card + banner, Alpaca view, wizard step, search results) captured from the running app |

Adaptation recorded: the plan's seven wizard "panels" ship as seven sections of one step — the wizard is a
5-step flow and splitting Alpaca into seven more steps would bury the core setup.

### Phase 3 — Alpaca market data — **DONE (2026-09-15)**, equity live run pending keys

| Task | Status | Evidence |
|---|---|---|
| T21 models + normalizer | ✅ | `Quote` in `data/models.py`; `data/alpaca_normalize.py` (trades stk/crypto/options, quotes, snapshots, bars; RFC3339→ms incl. nanoseconds; documented tick rule for the missing aggressor); `test_alpaca_normalize.py` 11 tests |
| T22 REST + session gating | ✅ | `data/alpaca_feed.py` `AlpacaData`: 150/min budget, 429 backoff, 24 h asset cache, clock-gated polling; 8 stub-transport tests; **live keyless crypto bars fetched** (5 real BTC/USD bars, budget accounted) |
| T23 stream client | ✅ | `AlpacaStream`: auth-first (10 s deadline), re-auth on reconnect, backoff 1→30 s, 401/402/403 fatal, full error table; 10 scripted-socket tests |
| T24 subscription manager | ✅ | `SubscriptionSet` caps/trim-with-warning/idempotency; `GET/POST /api/control/alpaca/subscriptions`; 3 tests |
| T25 engine wiring + gating | ✅ | `DataSource.ALPACA/ALL` + `AlpacaConfig`; `main.py` starts `AlpacaFeed` (seed → streams); `alpaca_symbol` per instrument; depth gate verified live **both ways** — with `data_source: bybit` no banner (depth exists), with `data_source: alpaca` the heatmap shows the reason for a mapped symbol and clears for unmapped ones (`docs/phase2/depth-gate-alpaca-*.png`) |
| T26 capability surface | ✅ | `engine.alpaca_capability_block()` (entitlement-aware: Basic → `["iex"]`, entitled → `+delayed_sip,sip`); 3 tests; feed card + feed selector gated by it |
| T27 test-stream test | ✅ | `test_alpaca_teststream.py`, opt-in; **ran live**: keyless connect to `/v2/test` is refused `[401]` (fatal, no retry loop) — the keyed half runs with `ALPACA_TEST_KEY/SECRET` |
| T28 demo parity | ✅ | SPY/QQQ added to `demo_data`; parity tests assert every Alpaca symbol serves demo **and** live shapes with identical keys |
| T29 docs | ✅ | `docs/ALPACA_DATA_FEED.md` (endpoints, streams, error table, caps, enabling it, open items); linked from `USER_GUIDE.md` §Alpaca and §Where to go next |
| T30 live smoke | ⏳ keys | Keyless smoke done end-to-end (below). The **equity** IEX run needs a paper key — one action for you: link keys in the Alpaca view, set Data source = Alpaca, start. |

Checkpoint 3 evidence (headless, `data_source: alpaca`, no keys):

```
engine start  → symbols AAPL, BTCUSDT, ETHUSDT, SOLUSDT · source alpaca · skipped: none
seed          → "Alpaca history seeded: 605 bars" (real keyless crypto history, now-anchored window)
pipelines     → BTCUSDT 956 ticks / 952 candles, ETHUSDT 752/748, SOLUSDT 712/708 (real Alpaca prices)
live-status   → overall "live"; tape/footprint/candles/microstructure/volume_profile/bias/scanner live
streams       → stocks + crypto both report [401] Not authenticated (mapped, fatal, no retry loop)
feed card     → needs_keys true, budget 4/150 (no 401 polling), depth false + reason
exchange run  → bybit restored: tape real prints, footprint distinct bars, every endpoint live
final: 193 passed · 2 skipped (opt-in) · audit CLEAN (79 routes, 13 modules)
```

Two real bugs the live smoke caught (both fixed, both now pinned by tests):

1. **Ticks were dropped silently.** `OrderflowSystem._on_tick` is a coroutine; the feed called it
   synchronously, so every seeded tick became an un-awaited coroutine ("720 bars seeded", 0 ticks in the
   pipelines). `AlpacaFeed._deliver()` now schedules it on the loop.
2. **History seeded the wrong window.** Alpaca's bars endpoints page forward from `start`, so a bare
   `limit` returns the *oldest* bars — the first smoke seeded yesterday's tape. `seed_history()` sends an
   explicit `now − history_minutes … now` window.

Open item — **resolved in Phase 5**: in the keyless run `/api/footprint` served 200 identical bars whose
timestamp matched the first seeded bar. Cause: the endpoint's documented warm-up fill —
`if not bars: return demo_data.demo_footprint(symbol, …)` — and `demo_footprint` is seeded by
`_stable_rng(symbol, tf, range_s)`, so it returns the *same 200 bars* for the same symbol every call, at
demo prices. The engine was running while no candle had closed for that symbol yet, so the panel showed
demo bars rather than the persisted candles. No pipeline bug at all (which is why the in-process replay of
the seed path looked fine). Phase 5 gates that fill on `demo_data.models_symbol(symbol)` — a symbol the
generator does not model now serves `[]` instead of an invented $1,028 chart (verified on `WIFUSDT`:
`[]` right after start, then one **real** bar at 0.1883). Residual, by design: a *modelled* symbol still
gets demo bars for the first minute after start.

### Phase 4 — Search redesign — **DONE (2026-09-15)**

| Task | Status | Evidence |
|---|---|---|
| T31 symbol universe | ✅ | new `desktop/search_service.py` `SymbolUniverse` (pins → recents → local → Alpaca assets 24 h cache → crypto; ranking exact 1000 / prefix 700+ / name 500 / substring 300 / fuzzy 100–200; sorts; type filter); `GET /api/control/search/symbols`; 22 tests incl. the no-keys path |
| T32 "Symbols" category | ✅ | `search.js` fetches with a 150 ms debounce and merges symbol rows above the app index; Enter switches the instrument and opens `search.default_view` (order flow by default) |
| T33 rich rows | ✅ | symbol, name, asset badge, feed chip (IEX / Delayed SIP / Indicative / Crypto · Alpaca / Crypto · Bybit), market-status dot from the clock, price with cents and a 3-decimal %-change, SVG sparkline from the live ring buffer |
| T34 live rows | ✅ | `Channel.SEARCH` + `broadcast_search_rows` + `RowBatcher` (300 ms window, per-symbol coalescing, bounded queue); UI patches visible rows at most every 200 ms, poll fallback when the socket is down. **Live proof**: 9 s of BTCUSDT → 18 batched messages, 36 rows patched, counters `seen 500 · coalesced 248 · batches 125 · rows_sent 250` |
| T35 navigation | ✅ | Enter = switch + default view (verified: ETHUSDT + orderflow); Ctrl/Cmd+Enter = second view; Ctrl/Cmd+Shift+Enter = option chain |
| T36 operators + sort | ✅ | new `search-ops.js` (+ `search-ops.selftest.js`, 50 checks, `node …selftest.js` exits 0); `type: exchange: underlying: exp: strike: vol: sort:`; multi-symbol paste; malformed input stays free text with a reason |
| T37 recents/pins/watchlist | ✅ | `search.recents` (auto, 12) · `search.pins` · `watchlist` (60) in the config with round-trip + cap tests; Ctrl+Click multi-select → "Add to watchlist" (verified: `["BTC/USD","BTCUSDT"]` persisted) and "Compare feeds" |
| T38 option chain | ✅ | `GET /api/control/alpaca/chain` + OCC parsing/sorting/expiry/strike filters (tests); panel with strikes × calls/puts, expiry select, ATM button, contract → search; per-contract live toggle **disabled with the D-A reason**; keyless → honest refusal panel |
| T39 feed comparison | ✅ | `GET /api/control/alpaca/compare` — IEX vs SIP when entitled, delayed window otherwise, and Alpaca crypto vs Bybit. **Live**: BTCUSDT Alpaca 78,395.7 vs Bybit 78,378.5 → difference 17.2 |
| T40 keyboard + tooltips | ✅ | guide's "Keyboard & search" section rewritten to match the handlers exactly (Enter / Ctrl+Enter / Ctrl+Shift+Enter / Ctrl+Click / Shift+Enter / Esc / arrows, plus the operator examples with Copy buttons) |
| T41 performance | ✅ | `SEARCH_TIMING` constants (150/200/600/5000 ms) asserted in code; batcher stress test (5,000 messages → bounded batches, `seen = rows + coalesced + dropped`); counters surfaced in the **Logs** view (`palette stream: 736 seen · 362 coalesced · 0 dropped · 184 batches / 372 rows · window 300ms · cap 200`) |
| T42 Alpaca entries re-verified | ✅ | `searchQuery('alpaca')` still returns the Actions "Open Alpaca setup" (focuses the key field) and "Alpaca: how to get API keys" (opens the walkthrough), plus the view/guide/settings hits |

Audit hardening in the same pass: `scripts/audit_ui_refs.py` now checks **14** modules instead of 4 (the palette,
scanner and Alpaca modules call just as many endpoints), and its template-hole regex handles nested braces
(`${(st || {}).symbol}`) instead of inventing a bogus path.

Evidence: `docs/phase4/*.png` (live rows + patch, multi-select/watchlist, operators, chain refusal, compare
panel, Logs counters) · `node orderflow_system/desktop/ui/search-ops.selftest.js` → 50 ok · `218 passed · 2 skipped` · audit CLEAN (86 routes, 15 modules).

Two bugs the smoke caught (both fixed, both now covered by the self-test):

1. `vol:>1M` — the plan's own example — failed to parse: the range parser had no K/M/B handling, so a
   valid operator was reported as an error. `soSizeRange()` now parses suffixed bounds (`>1M`, `<250k`, `1M-5M`).
2. Prices were compacted (`78.38K`), hiding every tick that matters; the palette now keeps cents
   (`78,402.1`) with a 3-decimal change on a quiet tape, and the change carries a tooltip naming its window
   (the last 128 prints).

### Phase 5 — Config consolidation — **DONE (2026-09-15)**

The gate from Phase 0 was honoured: the golden snapshot landed *first*, then the refactor
had to be a provable no-op.

| Task | Status | Evidence |
|---|---|---|
| T43 golden snapshot | ✅ | new `scripts/regen_config_golden.py` + `orderflow_system/test_config_golden.py` + `testdata/config_golden.json`: every factory, the whole crypto family and the ordered list the app iterates, key-by-key. `--write` to accept a deliberate change, `--check` otherwise; drift prints exactly which key moved. Coverage asserted (≥45 instruments), plus "a wrapper must agree with `get_all_configs()`" |
| T44 banks + overrides | ✅ | `settings.py` **1050 → 765 lines**: 10 class banks instead of 31 constructors, `Spec` rows for the overrides, one `get_config_for()`, thin wrappers keeping every public name. **The golden file was not touched** — byte-identical output before and after, which is the whole point of doing T43 first |
| T45 new instrument = two lines | ✅ | `TONUSDT` added as one enum member + one matrix row → golden regenerated with exactly two changed entries (`crypto_majors.TONUSDT` added, `all_configs` 48 → 49 rows) and nothing else. `scripts/regen_config_golden.py --write` + a reviewed diff is the complete workflow |

**What T45 exposed** (the reason this phase was worth running): the same major list was
hand-copied in three places, and the copies had already drifted.

- `api.VENUE_MAJORS` and `config_store.BYBIT_FALLBACK_SYMBOLS` are now **derived** from
  the matrix; a test asserts no duplicates and that every shipped major appears in both.
- A symbol added from the venue catalogue (`/api/control/instruments/add` — any of
  Bybit's 870 perpetuals) used to be accepted into the config and then refused by the
  engine as `unknown instrument`. `settings.instrument_for()` extends the enum for
  venue-only symbols, `config_for_symbol()` builds their profile from the venue's tick,
  and `select_instruments()` runs them. **Live proof**: `WIFUSDT` (never heard of by the
  repo) added through the wizard API, `skipped: []`, and streaming real prints
  (`{"price":0.1883,"size":102,"side":"buy"}`), a real order book and its own footprint bar.
- `engine.bybit_capable(spec)` replaces "is it in the shipped list?" — the config's
  venue-stamped `bybit_symbol` is the stronger evidence. Same helper now labels the
  palette row (it said "Crypto · Alpaca" for a Bybit-streamed symbol; it says
  "Crypto · Bybit").
- **Config bleed fixed**: `_apply_overrides` wrote onto the process-wide cached base
  config, so a threshold changed for one start leaked into every later one and a GUI
  reset only took effect after a restart. `select_instruments()` now hands out deep
  copies; a test starts the engine twice and checks the second start sees the bank values.
- **No invented prices**: the demo generator's `1000.0` fallback put a $1,028 chart on a
  token trading at $0.19 while it warmed up. `demo_data.models_symbol()` gates the fill —
  the endpoint now serves `[]` for a symbol it does not model (verified: `[]` right after
  start, then **one real bar at 0.1883**). The crypto majors all have demo prices now.
- An existing config file keeps the instrument list it has (new releases are added from
  the Instruments view, and a deliberately deleted instrument is never resurrected) —
  recorded as a Phase 6 release-note item.

Tests: `test_instrument_matrix.py` (8) + `test_config_golden.py` (4) new · **230 passed,
2 skipped** · audit CLEAN (86 routes, 15 modules) · `settings.py` -285 lines net.

### Phase 6+ — not started (Phase 6: consistency pass, docs set, release notes; Phase 7: portfolio + paper trading)

## Execution notes & risks

- **Do not wire `_on_candle_close_handler` as-is** (`main.py:464`): it calls `pipeline._on_candle_close`
  at `:470`, which would run the analytics pass twice per candle. T6 folds the persistence+broadcast into
  a new system callback instead.
- **Payload parity is a real hazard:** the JS reads exact demo keys. Freeze `demo_data` shapes and add
  the key-diff test helper in T8/T9/T28 before any endpoint is switched to live.
- **Windows:** use `.venv\Scripts\python.exe`; the repo is dirty (three modified files); commit or stash
  a known state before Phase 1 so checkpoint diffs are readable. The beta build folder on the Desktop is
  for the owner's smoke tests, not a build target of this plan.
- **Hotspots:** `dashboard/app.py`, `desktop/ui/search.js`, `desktop/ui/guide.js`, `desktop/engine.py` —
  one task at a time; run the audit after each UI edit.
- **Order rationale:** T1–T4 first (cheap, prevents silent regressions), Phase 1 before Phase 4 because
  "live rows" are dishonest until the bridge exists, Phase 3 before Phase 4 because the palette's live
  rows ride the shared stream, Phase 5 is independent (can run in parallel by a second agent if one is
  available), Phase 6 closes the doc/UI drift the audits flagged.
- **Decision log to keep while executing:** D-A (MsgPack/options live quotes), any new config keys added,
  which feeds the linked account actually entitled (record it in the receipt — Phase 3 T26 output).
