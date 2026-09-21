# ModFlow upgrade package — applied

**Date:** 2026-09-20 · **Section:** §147 · **Source of truth for the findings:** `docs/COMPETITIVE_ANALYSIS_2026-09.md`
**Status:** applied and verified in the worktree. Nothing committed — the tree is dirty on purpose.

This document is the package itself: every resolution path the competitive analysis flagged, what was
built for it, where it lives, and the evidence that it works. **Paid features were excluded by
instruction** — nothing in this pass depends on a subscription, a paid data key or a hosted service.
Where a competitor's advantage comes from a paid feed, the build takes the honest half: the structure is
in place, and the refusal sentence names exactly what is missing rather than inventing a number.

---

## 1. Resolution paths, head to head

| # | What the report asked for | What was applied | Where | Evidence |
|---|---|---|---|---|
| **P0-1** | Live order routing from the ladder | A **routing layer**: an account-driver abstraction with risk gates (size, max size, max positions, daily loss cap), a paper driver that fills from real prints, and a bridge driver that **refuses in one sentence** — live routing ships off. No broker adapter (needs a live counterparty; see §3) | `desktop/orders.py`, `desktop/atm.py`, routes `/api/control/trading/{status,templates,route,cancel}` | 31 tests · live smoke: status/templates 200, order route refuses with *"no trading session is bound here yet — open a paper session on the Replay view first"* |
| **P0-2** | Brackets, OCO and ATM strategies | **ATM engine**: three shipped templates (scalp / intraday / runner), bracket legs planned from the entry, OCO sibling cancel, break-even, trailing stop, time stop, partial off at R — identical semantics in the paper account, drawn on the ladder with leg distances | `desktop/atm.py`, `desktop/paper.py`, `desktop/ui/ladder.js` | 39 + 62 tests · ladder selftest 74 checks · live smoke: a `runner` template reaches the order receipt with all its fields |
| **P0-3** | Footprint configurability (the ATAS lesson) | **21 controls** in an in-panel drawer (cell metric, colour-by, imbalance convention incl. diagonal, two ratios, stack counts, min print/row size, absorption size + body limit, per-bar POC and value area, ticks per row, session filter + window) plus an annotation layer that draws the marks | `atlas/footprint_config.py`, `desktop/ui/orderflow.js` | 44 tests (incl. 14 Python↔JS parity cases) · 76 selftest checks · route `/api/atlas/footprint/config` 200 |
| **P1-1** | Depth-history graph + retention | **Depth record**: one column per interval per instrument (bounded, pruned by retention), read back as a price×time strip with pull/add marks, gaps, staleness and a band profile | `atlas/depth_history.py`, `desktop/ui/depth-history.js` | 42 tests · 55 selftest checks · live smoke: `/api/atlas/depth-history` reports its own retention and column counts |
| **P1-2** | Order-flow alert builder | **Condition groups**: AND/OR over 21 readings, cooldown scope (rule or symbol), aligned once-per-window, and a **Test fire** that rehearses a rule against the newest real event of its kind | `atlas/alerts.py`, `desktop/ui/alert-builder.js`, route `POST /api/atlas/alert-rules/test` | 57 tests · 16 selftest checks at delivery; **79 tests · 17 selftest checks after the §148 audit** (which also made a set param a member list — a typo can no longer become a rule that can never match, and the panel names it — and made the rehearsal read the event the engine actually evaluated) · legacy rules behave exactly as before (pinned; malformed legacy shapes now read quiet rather than raising — §148 AB-06/AB-07) |
| **P1-3** | Alert payloads with evidence | **Context block**: time, symbol, price, the trigger, window delta, biggest prints, nearest walls, session — text or CSV, hard-capped, on **every** channel (Telegram, ntfy, email, webhook) | `atlas/alerts.py` + `atlas/notify.py` | payload-key pin · the block travels in `to_dict()`/`webhook_payload()` · notify formatters append it, never substitute it |
| **P1-4** | Chart linking matrix + chart tabs | **Not applied** — see §3 | — | — |
| **P1-5** | Session templates + roll calendar | **Session engine**: template model with timezones, days, breaks, holidays and early closes; an 11-template built-in library; session state/phase/countdown; **roll calendar** for 18 futures roots + the BTC/ETH/SOL perpetuals, each date printed with its own convention | `atlas/sessions.py`, `desktop/ui/sessions.js` | 49 tests (boundaries, holidays, DST dates, roll dates) · 25 selftest checks · live smoke: `/api/atlas/sessions` 200 |
| **P1-6** | Synthetic instruments / spreads | **Composite engine**: definitions (ratio, spread, basket, basis) with weighted legs, alignment with a named carry-forward figure, spread in bps and a z-score that refuses to exist when the composite never moved | `atlas/synthetic.py`, `desktop/ui/synthetic.js` | 36 tests · 17 selftest checks · three starter definitions ship in the config block |
| **P1-7** | Trade analytics upgrade | **Deep read**: R from the row's own stop and exit (unit-free, never a fake 0R), expectancy in R, payoff, win/loss runs, MAE/MFE when a writer records them, per-setup / per-instrument / per-session breakdowns, a P&L calendar, and up to five plain sentences — in the panel and in the HTML statement | `desktop/journal.py`, `desktop/ui/journal.js` | 58 tests · 64 selftest checks · the 21 existing journal pins untouched |
| **P1-8** | Read-only companion | **Monitor page**: mobile-first, self-contained, dark, no external resources, **five GETs only** — alerts, paper positions, watchlist quotes, one order-flow read — with a sentence for every refused panel | `desktop/ui/monitor.html`, `desktop/ui/monitor.js` | 15 tests (including a no-write proof and a route-existence check) · 20 selftest checks · live: rendered 390×844 with no overflow; with every API dead it still says "4 of 4 reads failed — the rest is live" |
| **P1-9** | Data-quality cockpit | **Scorecards**: per-instrument verdict A–F from coverage / gaps / duplicate stamps / out-of-order stamps / staleness, the biggest gaps as wall-clock ranges, and repair hints that name real routes — a repair the program cannot do is a sentence, not a button | `atlas/dataquality.py`, `desktop/ui/data-quality.js` | 52 tests · 56 selftest checks · live smoke: `/api/atlas/data-quality` 200 |
| **P1-10** | Publish measured performance | **`docs/PERFORMANCE.md`**: the repo's own harness, run on this machine — 4,033 ticks/s through five analysers single-threaded, 7,273 book+tick/s, heatmap snapshot 0.78 ms cold vs 0.4 µs cached (1,940×), 624,294 alert-events/s, each line explained, plus the explicit note that a render-side FPS figure needs a harness that does not exist yet | `docs/PERFORMANCE.md`, `scripts/bench_atlas.py` | raw output pasted in the document |
| **P2-1** | Options × order flow confluence | **Partly applied**: the options stack (GEX, volatility, option flow) already existed; the *confluence* work — gamma walls drawn on the footprint, combined gamma+tape alerts — is **not applied** (see §3). The explainability registry now covers the options reads, so the overlap is at least legible | `desktop/ui/why.js` | 3 derivatives/options entries + gex/vol/optflow entries |
| **P2-2** | Explainability as a feature | **Registry + popovers**: 25 reads explained as *measured / inferred / computed*, wired to 19 readouts across 8 views, feeding the app's existing hint cards. The build fails if a `data-why` has no explanation, and the inferred reads (iceberg, stop run, pull, divergence, absorption, gamma) are pinned as inferences so the app cannot claim to measure what it only deduces | `desktop/ui/why.js`, `desktop/ui/why.selftest.js`, `orderflow_system/test_why.py` | 13 selftest checks + 3 python pins |
| **P2-3** | Crypto derivatives context | **Funding / OI / basis per venue** (Bybit, Binance, OKX, Hyperliquid — all public, keyless), annualised through each venue's own interval, OI change measured against the program's own samples with the window named, basis in bps, and one plain sentence | `atlas/derivatives.py`, `desktop/ui/derivatives.js` | 76 tests, offline via an injected transport · 31 selftest checks · **live**: *"funding is +0.010%/8h (+10.5% annualised) … longs are paying to hold"* |
| **P2-4** | Local scripting + study-pack gallery | **Not applied** — see §3 | — | — |
| **P2-5** | Onboarding as a moat | **Partly applied**: seven new help topics (the five new views, the footprint drawer, the companion page) join the 86 existing ones. Layout packs and the interactive first-run checklist are **not applied** | `desktop/ui/help-data.js` | `test_help` green: every view has a topic and every relation resolves |

---

## 2. Verification — the gate run

| Gate | Result |
|---|---|
| `pytest orderflow_system` | **2,389 passed · 3 skipped · 0 failed** (baseline before this pass: 1,900) |
| `ruff 0.16.7` | clean on every file this pass touched |
| JS syntax | `node --check` on all 13 touched/new modules — clean |
| UI selftests | 13 modules, **480 checks, 0 failed**: orderflow 76 · ladder 74 · journal 64 · data-quality 56 · depth-history 55 · derivatives 31 · sessions 25 · monitor 20 · news 18 · synthetic 17 · alert-builder 17 · feedkeys 14 · why 13 |
| `scripts/audit_ui_refs.py` | **AUDIT CLEAN** — 187 routes discovered (was 170), 659 html ids + 380 created, **0 missing calls, 0 missing ids, 0 duplicate ids**, 154 modules parse |
| Live smoke (real app, throwaway config) | 36 route objects · 10 GETs all **200** · the index serves all five new views, the new script tags and the `data-why` layer · the trading route refuses in one sentence · a `runner` template reaches the paper order receipt · a live Bybit funding read comes back |
| `ast.parse` sweep | every `.py` under `orderflow_system` parses |
| Config golden, param registry, wiring, timer guards, listener balance | green (the listener ledger and the audit gained the new modules' frozen counts) |

---

## 3. The honest remainder

Not built, and why — each with what it would actually take:

1. **Broker adapters for live routing.** The layer, the gates and the refusal path are in and tested;
   what is missing is a real counterparty. DTC and the MT5 bridge would each need a transport
   implementation and a live account to verify against — and I will not ship order submission I cannot
   test end to end. The build refuses instead: *"live routing is off — this build has no broker
   connection, so orders only ever reach the paper account."*
2. **MAE/MFE writers.** The analytics read those fields; nothing writes them yet, so the panel says
   `n/a` rather than estimating. A writer is a small change in the paper engine's fill path.
3. **Chart linking matrix + chart tabs (P1-4).** Deferred: the shell already links symbols across
   panels (cursor spine, detached windows, §128 multi-monitor); a 2×2 chart grid with per-pane linking
   is a UI project of its own and would have crowded this pass.
4. **Study-pack gallery and user-scripted strategies (P2-4).** Deferred: it needs a sandboxing story
   before it needs a gallery.
5. **Layout packs and the interactive first-run checklist (P2-5).** The help topics landed; the packs
   are a config-defaults job best done against the shipped workspaces.
6. **Options × flow confluence (P2-1).** Gamma walls on the footprint and combined gamma+tape rules are
   a genuinely new feature (not a gap-fill) and belong in their own pass.
7. **Depth-history retention persistence.** The block is registered and clamped; the panel's own POST
   persists in memory only, so a restart returns to the shipped retention until that handler writes the
   config (one line, flagged by the module's author).
8. **Render-side FPS harness.** `docs/PERFORMANCE.md` measures ingest, snapshots and alerts and says
   plainly that a render figure will not be quoted until it is measured the same way competitors claim
   theirs.
9. **Mobile reach.** The companion page is served by the local server, which binds `127.0.0.1`; a phone
   needs the host policy changed first. The page and the help topic both say so.

Frozen build / installer / SBOM were already owed before this pass (§129c rebuild) and still are —
`scripts/make_release.py` is the path, and it should run after this work is reviewed.

---

## 4. What was added, file by file

**Analytics (new modules):** `atlas/footprint_config.py` · `atlas/depth_history.py` · `atlas/dataquality.py` ·
`atlas/sessions.py` · `atlas/derivatives.py` · `atlas/synthetic.py`
**App (new modules):** `desktop/atm.py` · `desktop/orders.py`
**Extended in place:** `desktop/paper.py` (plan/OCO/BE/trail/time-stop) · `desktop/journal.py` (deep read) ·
`atlas/alerts.py` (conditions, cooldowns, evidence) · `atlas/hub.py` (builder settings, snapshot provider,
depth feed) · `atlas/notify.py` (the block on every channel) · `atlas/api.py` (paper plan + the rehearsal
route) · `desktop/config_store.py` (nine feature blocks, each cleaned by its own module) ·
`desktop/param_registry.py` (42 new dials) · `desktop/launcher.py` (seven routers) ·
`desktop/ui/index.html` · `desktop/ui/help-data.js` (7 topics, 5 view mappings) ·
`scripts/audit_ui_refs.py` · `orderflow_system/test_listener_balance.py`
**UI (new modules):** `ui/orderflow.js` · `ui/alert-builder.js` · `ui/depth-history.js` · `ui/data-quality.js` ·
`ui/sessions.js` · `ui/derivatives.js` · `ui/synthetic.js` · `ui/monitor.html` + `ui/monitor.js` · `ui/why.js`
**Tests (new):** `test_atm.py` · `test_orders.py` · `test_footprint_config.py` · `test_depth_history.py` ·
`test_trade_analytics.py` · `test_alert_builder.py` · `test_dataquality.py` · `test_sessions.py` ·
`test_derivatives.py` · `test_synthetic.py` · `test_monitor.py` · `test_why.py` (12 new suites, ~590 tests)

## 5. Run it

```
unset PYTHONPATH
.venv/Scripts/python.exe -m pytest orderflow_system -q          # 2,389 passed / 3 skipped
.venv/Scripts/python.exe scripts/audit_ui_refs.py               # AUDIT CLEAN
.venv/Scripts/python.exe scripts/bench_atlas.py 200000          # the numbers in docs/PERFORMANCE.md
.venv/Scripts/python.exe -m orderflow_system.desktop            # the app itself
```

New surfaces to look at first: the **Order Flow** drawer (footprint settings) · the ladder's plan bar ·
**Depth history**, **Sessions**, **Data quality**, **Funding & OI**, **Synthetic** in the rail ·
the **Condition builder** card in Alerts · the Journal's setup stats and calendar · any of the 19
`data-why` readouts (hover) · `/desktop/monitor.html` for the phone view.
