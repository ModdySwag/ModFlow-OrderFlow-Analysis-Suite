# ModFlow OrderFlow Analysis Suite — Audit & Enhancement Report (v2, recompiled)

**Date:** 2026-09-15 · **Scope:** `C:\Users\<you>\OrderFlow-Analysis-Pro` — all app-authored code
**Supersedes:** `AUDIT_REPORT_2026-09-15.md` v1 — archived at `docs/archive/AUDIT_REPORT_2026-09-15_v1.md`

## Changelog — what changed in this recompile

1. **`Desktop\report.txt` is now merged explicitly.** Every one of its findings (P1–P8) is carried below
   with its exact file/line anchors, not summarised.
2. **Every claim re-verified against the working tree** on 2026-09-15 (v1 was written partly from the two
   Desktop documents). Verification log in Appendix A.
3. **Three v1 findings corrected or sharpened** — see §3 (P1 wiring hazard, P7 Scanner, P2 anchor detail).
4. **New section: "Already efficient — do not rebuild"** (§4). code.txt recommends several things this
   codebase already does (per-channel WS throttling, incremental candle building, batch inserts). Rebuilding
   them would be waste; the plan now reuses them.
5. **New section: "New / more efficient implementations"** (§5) — concrete additions that make the merged
   recommendations cheaper or more robust than the source documents propose.
6. **code.txt reconciled section-by-section** against the code (§2) so "what's left to do" is unambiguous.
7. **Cross-linked to the build plan:** `docs/ALPACA_UPGRADE_EXECUTION_PLAN.md` (50 task cards, Phases 0–7)
   turns this report into execution. This report stays the *findings* document; the plan is the *work order*.

## Sources

| Document | What it contributes |
|---|---|
| `C:\Users\<you>\Desktop\code.txt` | Alpaca enhancement report: setup flow, search redesign, feed rules, error table, perf list |
| `C:\Users\<you>\Desktop\report.txt` | Codebase audit: P1–P8 findings, "what I'd fix first" order |
| `AUDIT_REPORT_2026-09-15.md` v1 | Prior merge of the two + a first source pass |
| `docs/ALPACA_INTEGRATION_PLAN.md` | Alpaca product plan (what Alpaca adds / cannot add, phases, safety, risk register) |
| `docs/ALPACA_UPGRADE_EXECUTION_PLAN.md` | The executable plan derived from this report |
| Verification pass (this recompile) | 124 tests green, UI audit clean, line-level checks — Appendix A |

---

## 1. Executive summary (merged)

**The build is solid.** The analytics core is careful (slots on hot dataclasses, WAL SQLite, batch inserts,
typed signals, incremental candle building), the config model is correctly split from source, the Alpaca
client is the best-shaped integration in the repo, the search palette is the best-executed UI surface, and
onboarding/docs are unusually honest. 124 tests pass; `scripts/audit_ui_refs.py` reports clean.

**There is exactly one defect that matters:** with the engine running, some views still show demo data —
the live engine is not fully bridged to the REST/WS surface the UI reads (P1). It is also the one thing the
UI already warns the user about, per panel, which is honest but confusing.

**There is exactly one opportunity that matters commercially:** Alpaca. The account-linking phase is built
and verified; what is missing is *discoverability* (it lives only inside Settings), the *wizard step*, and
the *search leap* from an app-index to a live-market instrument.

**Everything else** — config repetition, enum/string tolerance, two API surfaces, Scanner framing, doc
drift, CI — is real but secondary, and cheap once the two headline items are sequenced properly.

---

## 2. code.txt reconciled against the code (what is already true, what is not)

This is the merged view of the two Desktop documents; "already true" items must not be rebuilt.

| code.txt recommendation | Status in this tree | Notes / where |
|---|---|---|
| **§2.2 / §6.1** Isolate feed parsing behind a normalizer | Partly | Bybit parsing is already isolated inside `data/bybit_feed.py` (`_handle_trades :108`, `_handle_orderbook :132`); a *shared* normalizer is only needed when a second feed lands → `data/alpaca_normalize.py` (plan T21) |
| **§2.2** Ring buffer for recent trades | **Not done** | `main.py:233` buffers ticks only until DB flush (`_tick_batch_size = 100`, `:232/:432`); no bounded *tape* buffer exists → plan T5 (`deque(maxlen=500)`) |
| **§2.2** Incremental candle/footprint aggregation | **Already done** | `data/candle_builder.py:process_tick :41` mutates the open candle in place (`_current_candle`, `:29/:78`) |
| **§2.2 / §6.1** Throttle per channel (tick 200 ms, book 500 ms, stats 5 000 ms) | **Already done, exact values** | `dashboard/websocket_manager.py:68–78` (TICK 200, ORDERBOOK 500, DELTA 200, STATS 5000, signals never), enforced per symbol at `:114–121` |
| **§2.3 / §6.3** Canvas rendering, virtualized tables, no full re-render per message | Partial | WS pushes are throttled; the tape/footprint widgets render into DOM tables (`static/tape.js`, `static/footprint.js`) → still worth virtualization for long lists (plan T41) |
| **§2.3** Demo/offline mode | **Already done** | `dashboard/demo_data.py` (782 lines) + per-endpoint fallbacks; this is the layer P1 must *mark*, not remove |
| **§2.4 / §6.4** Secrets out of source, staged probe, masked keys | **Already done** | `desktop/alpaca.py`, `desktop/config_store.py` (per-user dir, atomic write, sanitise), `test_alpaca.py` proves masking |
| **§2.4 / §6.4** Structured per-instrument config | Already structured, but repetitive | `config/settings.py` dataclasses + 27 factories (P2) → plan Phase 5 |
| **§3.1** Landing card / nav item / banner / shortcut | **Not done** | Card exists but is created at runtime inside Settings (`alpaca.js:alpacaEnsureCard :162`); rail (`index.html:24–42`) has no `alpaca` view → plan Phase 2 |
| **§3.2** Wizard onboarding (7 steps) | **Not done** | `guide.js:WIZ_STEPS :422` has no Alpaca step → plan T19 |
| **§4.2** Single shared stream per asset class | **Not started** | No Alpaca market-data feed exists yet (`data/` has bybit/mt5 only) → plan Phase 3 |
| **§4.2.4** Autocomplete sources (assets, options chains, crypto list, local recents) | Not started | Plan T31 |
| **§4.3.1** ⌘K/Ctrl+K palette | **Already done** | `desktop/ui/search.js` (`searchEnsureUI :321`, boot `:478`); indexes views, actions, settings controls, alert kinds, rules, help, instruments |
| **§4.3.2** Expanded search + operators + multi-select | Not started | Plan T36/T37 |
| **§4.3.3** Live-updatable result rows | Not started (blocked by P1 + Phase 3) | Plan T33/T34 |
| **§4.3.4** Option chain panel | Not started | Plan T38 (REST snapshots; live quotes behind decision D-A) |
| **§4.3.5** Multi-feed comparison | Not started | Plan T39 |
| **§4.3.6** Keyboard set | Mostly done | Palette nav/Enter/Esc done; Ctrl+Enter, Ctrl+Shift+Enter, Shift+Enter, `/`-focus to add (T35/T40) |
| **§4.3.7 / §6.10** Debounce, caps, backpressure | Partly | WS throttling exists; query debounce + cap warnings + batching are new (T34/T41) |
| **§5** Reference material (clients, URLs, auth, errors, tiers) | Not written | → `docs/ALPACA_DATA_FEED.md` (T29). Note: this repo uses **no third-party SDK**; the reference is re-expressed as raw REST + `websockets` |
| **§6.2** Plan-tier awareness in the UI | Partly | `desktop/alpaca.py` already returns a capability report; the *data-source* gating (feeds, symbol limits) is new (T26) |
| **§8** Caveats (connection limit, paper vs live, MsgPack, star-subscription) | Adopted as constraints | See fixed decisions in the plan §0 |

---

## 3. Findings from report.txt, merged and verified (P1–P8)

### P1 — Live/demo split · **VERIFIED (high)** · the main event

Evidence, re-checked line by line:

- `main.py:464` `OrderflowSystem._on_candle_close_handler` — the only code that persists closed candles
  and broadcasts `candle`/`delta` — is **never called**. The wired callback is
  `main.py:219` `pipeline._on_signals_callback = self._on_candle_signals`; the pipeline's own
  `_on_candle_close` (`:127`) runs analytics and returns signals only.
- `desktop/engine.py:312` `_wire_candle_persistence` compensates by wrapping
  `pipeline.candle_builder.on_candle_close`, chaining DB insert + `broadcast_candle` + `broadcast_delta`;
  it is called from `EngineController.start` (`:492`). **So the desktop build does persist candles** —
  the v1 report's "database never accumulates candles" is true only for the repo's own `main.py` path.
- The user-visible gap is the three REST endpoints, which serve demo data **even when the system is set**:
  - `/api/footprint/{symbol}` `dashboard/app.py:890` → returns `demo_footprint` at `:903`
  - `/api/tape/{symbol}` `:909` → `# TODO` at `:912` → demo
  - `/api/microstructure/{symbol}` `:919` → `# TODO` at `:922` → demo
- **New hazard found in this recompile (not in v1):** wiring `_on_candle_close_handler` as-is would call
  `pipeline._on_candle_close(candle)` at `:470` → the analytics pass would run **twice per candle**
  (once via the candle builder callback, once via the handler). The fix must fold persistence+broadcast
  into a *new* system callback invoked *by* `_on_candle_close`, mirroring the existing
  `_on_signals_callback` pattern. (Plan T6.)
- The UI's per-panel warnings (`ui.js`) are accurate but scattered → replace with one status map (T12).

### P2 — Per-instrument config repetition · **VERIFIED**

`config/settings.py` = 1017 lines; factories `get_nas100_config :249` … `get_googl_config :853`, with the
shared helpers `_forex_major_config :703` (10 wrappers at `:741–790`, 8 of them pure `tick_size` variants),
`_stock_config :795` (7 identical wrappers `:829–857`), `CRYPTO_MAJORS :898`. Differences between
instruments are a handful of numbers (`tick_size`, `vp_tick_size`, session, thresholds).
→ Plan Phase 5: golden-snapshot test first, then an `InstrumentDefaults` bank + `INSTRUMENT_OVERRIDES`
map behind the same public `get_*_config()` names.

### P3 — Two API surfaces · **VERIFIED**

`dashboard/app.py` (the original REST+WS app, `get_system()` at `:58`) and `desktop/api.py`
(`/api/control/*`, `router = APIRouter(prefix="/api/control")` `:22`) are both mounted by
`desktop/launcher.py:build_app :39–50`. The dashboard app knows pipeline internals (imports `Side`,
detectors) which is why "add a live endpoint" means touching pipeline internals today. The plan keeps the
split (it works) and fixes the *ownership* of live-vs-demo through one status map (T12).

### P4 — Live/demo ambiguity in the UI · **VERIFIED**

Per-panel notices exist for tape and footprint (accurate), but there is no single state. → T12 (one chip;
per-endpoint `source` fields; per-view badges derived from the same map).

### P5 — `hasattr(x, 'value')` tolerance across hot paths · **VERIFIED (many sites)**

Enum-or-string tolerance is scattered through `dashboard/app.py` and the atlas modules. Works, ages badly.
→ T3: one boundary helper (`data/enums.py:as_value`) applied at the serialisation boundary; enums stay
enums inside detectors.

### P6 — Footguns · **VERIFIED**

- `desktop/engine.py:201` `def capabilities(cymbols: …)` — typo, harmless (called with no args from
  `desktop/api.py:71`), fixed in T2.
- Two asyncio lifecycles: `main.py:650` `asyncio.new_event_loop()` in the CLI path vs the launcher's own
  server loop (`launcher.py:serve :98`). Workable; the plan documents which one is authoritative (T4).

### P7 — Scanner · **CORRECTED (v1 said "not exposed")**

The Scanner **is** wired at runtime: `desktop/ui/scanner.js` creates its own nav button
(`:68` → `showView('scanner')`) and mounts the view (`scanEnsureView`, section appended at `:95`), and its
loop (`:161–167`) refreshes while the view is active. `/api/scanner` (`dashboard/app.py:134–150`) has a
**live branch** today (it ranks `system.pipelines` by strategy status; demo only when no system).
The true finding: the *static* `index.html` has no scanner nav item, so audits and readers conclude it is
missing. → Keep the feature; document the runtime-injection pattern once (T46/T47). Optional enhancement:
expose `atlas/hub.py:snapshot_scanner :443` behind a `mode=` parameter for the order-flow column ranking
the guide promises (§5.8).

### P8 — Documentation-to-code drift · **VERIFIED**

Guide and search describe the runtime layer; the static HTML doesn't show the wizard button or the scanner
item because modules inject them. Strategy/Performance exist in the rail (`index.html:35–36`) and are
partly live (P1). → T47 (make every promise true or label it) + T48 (docs).

---

## 4. Already efficient — do not rebuild these

1. **Per-channel WS throttling with a per-symbol window** (`websocket_manager.py:68–78`, `:114–121`) —
   the exact table code.txt recommends; the new `search` channel should reuse this class, not a new one.
2. **Incremental candle building** (`candle_builder.process_tick :41`) — no rebuild-per-tick.
3. **Batch tick inserts** (`main.py:232/:432`, 100-tick batches).
4. **Hot-dataclass `slots`** (`data/models.py:45/63`) and **WAL + busy_timeout SQLite** (`data/database.py`).
5. **Search index cost control**: 15 s rebuild throttle, DOM scrape at build time (`search.js:searchBuildIndex :152`).
6. **Alpaca client shape**: urllib only, rate limiter, staged probe (`keys→auth→api→ready`), key masking,
   honest capability report (`desktop/alpaca.py`; `test_alpaca.py` covers masking + limiter).
7. **Bounded polling in the UI**: status 2 s, logs 3 s, slow panels 5 s (`ui.js:89–91`).

---

## 5. New / more efficient implementations (added in this recompile)

These are additions beyond what either Desktop document proposes — each one is cheaper or safer than the
straight reading of the source advice.

1. **Live bridge by reuse, not by second lifecycle.** Wire persistence+broadcast through a new system
   callback set exactly like `_on_signals_callback` (`main.py:219`), and *delete* the desktop-only
   compensation (`engine.py:312`) once wired. Avoids the double-analytics hazard (§3 P1) and keeps one
   code path for CLI and desktop. (Plan T6/T7.)
2. **One capability map as the single source of truth.** The backend already knows entitlements
   (`alpaca.py` report). Extend it to a machine-readable map (`feeds`, `symbol_limit`, `quote_limit`,
   `options_feed`, `depth:false`) and drive *all* of: search feed chips, view gating, wizard preview text.
   No duplicated feed strings in JS; "honest chips" become structural, not editorial. (T26.)
3. **Reuse the throttle table for the new search channel + add a coalescing batcher.** The manager already
   does per-symbol throttling; the palette needs *batched* row updates on top (≈300 ms) plus counters
   (`messages seen / coalesced / dropped`) so backpressure is measurable instead of aspirational. (T34/T41.)
4. **Payload-parity as a test, not a convention.** Freeze `demo_data` shapes and assert live payloads
   key-for-key against them (`test_payload_parity.py`). This is the cheapest guard against the P1 class of
   bug re-appearing every time an endpoint is completed. (T8/T9/T28.)
5. **Alpaca without a new dependency.** Use the **`websockets`** library already declared in
   `pyproject.toml` for streams and plain `urllib` for REST — no `alpaca-py`, no new wheels. Options live
   quotes are MsgPack-only → explicit decision D-A (deferred; REST snapshots now). (T22/T23.)
6. **Ring buffer as `deque(maxlen=N)` per symbol** for the tape (and reuse for micro-burst metrics) instead
   of list+trim; O(1) append, no copies, bounded memory. (T5.)
7. **Golden-snapshot test before the config refactor.** Serialise all 27+ configs to JSON and diff on every
   commit; the P2 refactor then proves itself instead of being trusted. (T43.)
8. **Scanner as a two-mode endpoint.** Keep `/api/scanner` (strategy-status ranking) and add
   `mode=orderflow` backed by `hub.snapshot_scanner` — one endpoint, both rankings, no new view to build.
9. **CI on push** (pytest + `audit_ui_refs.py`) — the audit script already exists and is fast; wiring it to
   GitHub Actions is a 20-line file that catches the demo/live class of regression immediately. (T1.)
10. **FAKEPACA test-stream integration test**, env-gated for CI — the only honest way to test the stream
    layer without keys and without market hours. (T27.)
11. **Document the runtime-injection pattern once** (`atlas-v2.js:293–295` loads 9 modules that build their
    own UI). This retires a recurring false finding ("X is missing") from every future static analysis.
    (T47.)
12. **`as_value()` boundary helper + wire-once serialisation** — one function replaces the `hasattr` web and
    makes the JSON layer the single place enums are stringified. (T3.)

---

## 6. Roadmap (execution detail in `docs/ALPACA_UPGRADE_EXECUTION_PLAN.md`)

| Phase | What | Tasks | Checkpoint |
|---|---|---|---|
| 0 | Guardrails: CI, `cymbols`, enum helper, test docs | T1–T4 | 124+ tests, audit clean, CI file |
| 1 | **Live bridge** (P1): candle wiring, tape/footprint/microstructure live, one status chip, e2e test | T5–T13 | endpoints report `source=engine` on a live BTCUSDT run |
| 2 | Alpaca discoverability + wizard step (P3/P4) | T14–T20 | reachable 5 ways; wizard reaches "Paper Connected" |
| 3 | Alpaca data source: normalizer, REST (150/min, clock-gated), one stream/class, subscription caps | T21–T30 | an equity streams through the analyzers; depth gated with a reason |
| 4 | Search upgrade (P5): live symbol rows, batched updates, operators, chains, compare | T31–T42 | live rows without exceeding caps; chain opens from the palette |
| 5 | Config consolidation (P2) behind the golden test | T43–T45 | golden file unchanged; file materially smaller |
| 6 | Consistency: Scanner doc, guide/search drift, docs set, release notes, final gate | T46–T50 | promises true or labelled; docs match UI |
| 7 | Companion (deferred): portfolio, then paper trading per `ALPACA_INTEGRATION_PLAN.md` §4–5 | — | not in this run |

Phase 5 is independent and can run in parallel with Phase 2/3 by a second agent.

---

## 7. Risk register (merged: ALPACA_INTEGRATION_PLAN §6 + new)

| Risk | Mitigation |
|---|---|
| IEX-only free data misread as the whole market | Feed chip per result/panel; IEX share noted in context |
| 15-minute SIP delay unnoticed | Any SIP-sourced panel shows its timestamp + delay label |
| 30-symbol stream cap hit silently | Subscription manager warns and never silently trims (T24) |
| Rate limit (200/min) exceeded | Client budget 150/min + 429 backoff (T22) |
| Wrong-environment keys | Staged probe already names paper/live mismatch (built) |
| Market closed → empty panels look broken | Clock-gated polling + "market closed, next open …" state (T22/T26) |
| **Double analytics on candle close** (new) | Wire via a new callback; never call `_on_candle_close` from the handler (T6) |
| **Payload drift between demo and live** (new) | Payload-parity test helper (§5.4) |
| **Hotspot merge pain** (new) | Serialize edits in `dashboard/app.py`, `search.js`, `guide.js`, `engine.py` |
| Options live quotes need MsgPack (new) | Decision D-A: REST chains now; revisit with explicit opt-in |
| Windows venv quirks | Use `.venv/Scripts/python.exe`; commit a known state before Phase 1 |

---

## 8. Bottom line

The codebase is in good shape; the two Desktop documents overstate how much is missing because code.txt
could not see the source. Merged and verified, the true work is: **(1)** finish the live bridge so "live"
means live everywhere the UI reads, **(2)** lift Alpaca out of Settings into the landing page, the rail, the
shortcuts, the palette and a wizard step, **(3)** make the palette search the *market* — live symbols,
honest feed chips, chains, operators — on the single shared stream, and **(4)** the secondary hygiene:
config consolidation behind a golden test, the enum boundary, the Scanner/doc drift, CI, docs.

Everything above is sequenced, task-carded and measurable in
`docs/ALPACA_UPGRADE_EXECUTION_PLAN.md` (Phase 0 → Phase 6, 50 tasks, checkpoints per phase).

---

## Appendix A — verification log (how every claim here was grounded)

```
$ .venv/Scripts/python.exe -m pytest orderflow_system -q        → 124 passed in 2.76s
$ .venv/Scripts/python.exe -m pytest orderflow_system/test_integration.py \
      orderflow_system/test_alpaca.py -q                        → 13 passed in 0.14s
$ .venv/Scripts/python.exe scripts/audit_ui_refs.py             → AUDIT CLEAN
                                                                  (76 routes, 130 ids, 12 JS modules)
$ git log --oneline -1                                          → b2ff4ee Comprehensive README rewrite…
$ git status --porcelain                                        → M: config/settings.py, data/database.py, main.py
                                                                  ?? atlas/ docs/ assets/ AUDIT_REPORT…
```

Line anchors cited above were read directly from the tree during this recompile (main.py:80/127/219/232/
414/432/455/464/470/636/650; engine.py:201/203/312/459/492; dashboard/app.py:58/100/134/890/903/909/912/
919/922; websocket_manager.py:22/68–78/114–121; desktop/api.py:22/70; launcher.py:39–50/98/136;
search.js:43/152/271/380/427/478 and the static entry list :144–149; alpaca.js:52/69/99/162; guide.js:422/
849/874; scanner.js:68/95/161; index.html:24–42/68; config_store.py:208–212; settings.py:249/703/795/898;
candle_builder.py:29/41/78; models.py:18/23/31/45/63).

## Appendix B — how to read the three documents together

| If you want… | Read |
|---|---|
| The findings and why they matter | **this report** |
| The exact work order (tasks, tests, commands, evidence) | `docs/ALPACA_UPGRADE_EXECUTION_PLAN.md` |
| The Alpaca product scope and safety rules | `docs/ALPACA_INTEGRATION_PLAN.md` |
| The user-facing documentation | `docs/USER_GUIDE.md` (+ `docs/ALPACA_DATA_FEED.md`, `docs/ALPACA_SEARCH_REFERENCE.md` once written) |
