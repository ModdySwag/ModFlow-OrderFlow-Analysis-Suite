# ModFlow OrderFlow Analysis Suite — v0.1b final release audit (open-source ship gate)

**Directive applied:** `C:\Users\Moddy\Desktop\final audit prompt.txt` — *FINAL RELEASE AUDIT — v0.1b
OPEN-SOURCE SHIP GATE* (phases 0–5, ten prescribed report sections).
**Audited content ("the build as it stands"):** HEAD `797eea06c34a6ea23f9db1ec56cf75e344e5b496`
(`master`, also `moddy/master`) **+ the 96-entry dirty worktree** = 66 tracked files changed
(+4,338 / −443 lines) and 30 untracked files (the §119–§134 delta).
**Rule observed:** this pass changed **no code**. It inspects, reports, plans and defines validation;
every remedy below waits for an explicit instruction.
**Evidence:** `Desktop\OFAP_v0.1b_final_audit\` — `00_EVIDENCE_LOG.md`, `evidence\` (raw receipts),
`receipts\` (aggregates). Every number in this report traces to a file in that tree.

---

## 1. Release Decision

# SHIP ONLY AFTER REQUIRED FIXES

All four required items are **release mechanics, not product defects** — no P0/P1 defect was found on
this content.

1. **No blocking defect found.** The security controls, resource ownership, hot paths and
   market-data gates were re-verified **on this exact content** — live, on both the dev server and
   the frozen exe — and the full gate stack is green (1,753 passed / 3 skipped / 0 failed on Python
   3.11 **and** 3.12; 41/41 Node selftests; `AUDIT CLEAN`; ruff clean; both goldens exact). **One
   caveat, stated plainly (FG-08):** one full-suite run in five produced a single intermittent
   failure in `test_hyperliquid_feed.py::…rest_call_fails`, which then passed 3/3 in isolation and
   in both subsequent full runs — a flaky gate, tracked below, not a product defect.
2. **Required 1 — commit the content.** The release candidate exists only as a dirty worktree:
   nothing since `797eea0` is committed (`git status --porcelain | wc -l` = 96), so **CI has never
   seen this delta**. A public release must be a commit; that is also the owner's standing gate.
3. **Required 2 — re-derive the README's measured claims (FG-01).** Eight File-Inventory rows and
   three badges are stale (badge `tests 1584` vs measured 1,753; `115 vanilla-JS modules` vs 126;
   `~45,567L` vs 48,502; Desktop UI `125 files / 49,112` vs 136 / 52,157; Total `246 / 98,326` vs
   248 / 97,356; suite `146 files / 27,729` vs 160 / 30,274; plus four line-count rows). The API
   badge **is** correct (185 OpenAPI operations + the `/ws` websocket = 186).
4. **Required 3 — decide the version identity (FG-02).** `pyproject.toml` says `0.1.0`, the README
   says `v0.1.0-beta`, the release is called `v0.1b`; `git tag -l` is empty. Pick one, tag it at
   publish time.
5. **Required 4 — decide the distributable (FG-03).** `dist/` + zip + SBOM + Setup are the **§129c
   build** (`BUILD_INFO` commit `797eea0`, dirty, built 2026-09-19T20:20:02+0930; Setup
   `37,693,744 B` sha256 `e39e3adc…`). Six UI files plus the new `engine-progress.js` are newer in
   the source tree, so the §130–§134 fixes (widget titles follow the instrument; the whole-panel
   hover tooltip; the engine progress bar; the menu-close fix) are **not** in the download. The
   artifact is internally consistent and passed every probe (23/23) — shipping the snapshot is a
   legitimate choice, but it must be a deliberate one. A rebuild is the cheap default.
6. **One behaviour deserves an explicit decision, not a fix (FG-05).** After the Engine view has
   been opened once, **picking an instrument in the top bar starts the live engine** (reproduced
   live: engine `stopped` → `running ['BTCUSDT']` within 2.5 s of the pick; a fresh page that never
   opened the Engine view does nothing). It is designed behaviour (§82) with visible feedback (the
   pill and the §132 progress bar), but it opens a live venue connection from a selection.
7. **Two small cleanups are deferred by choice (FG-06, FG-07)** — both quantified, neither a
   release risk: the chart's 5-second retry watch, and one duplicate status fetch per poll.
8. **Prior ledger re-verified on this tree.** RA-01/02/03 are fixed and re-proven live (a hostile
   symbol driven through the app's own store renders as TEXT, `__RA_XSS` never set, 0 parsed
   elements; a fresh-profile export answers `400 + sentence`); F-05 and F-08 landed (bandit now
   shows **0 High** — the B324 sha1 is gone — and the log filter drops aborted sockets); SS-1…SS-14
   re-checked, all closed or carried with unchanged disposition.
9. **Honest limits.** One physical display (no real multi-monitor pass); no long soak (owner's
   standing instruction — the bounded live soak and the prior runs are quoted instead); no broker
   accounts exercised (MT5 / NinjaTrader / Alpaca); CI not yet run on this content; the frozen
   artifact predates §130–§134.
10. **This pass changed nothing** — the working app the owner launches is untouched, and the
    worktree still counted 96 entries at audit time.

**§135 fix pass — closure (2026-09-19).** On the owner's word ("go for all fixes") every fix
this report names was executed in one source pass, pinned, re-gated and re-packaged. What
changed: **FG-01** — README + CONTRIBUTING claims re-derived from the tree (10 `(NNNL)` values,
3 badges, both prose module claims, all eight File Inventory rows + the total, the suite line;
the re-derivation ships as a token-based script so it can be re-run); **FG-02** — a *Release
identity* line in the README pins package/artifact `0.1.0` to the release tag `v0.1.0-beta`
(the tag itself is created in the publish pass); **FG-03** — `dist`/zip/SBOM/Setup rebuilt on
this content (hashes in §7/§8); **FG-04** — open by design: the commit/publish pass is the
owner's word (the standing gate), and after it a `--release` build becomes possible (the build
script refuses a dirty worktree by design); **FG-05** — documentation-only, the least-invasive
of the three options: the instrument selector's tooltip and the Instruments help topic now say
that a pick can start the engine; **FG-06** — `CHART_RETRY_MAX = 12` bounds the chart retry
watch, the chart head says so when it stops, and a landed load or a new selection resets the
budget; **FG-07** — `refreshLiveChip(status)` reuses the shell's own payload (a bare call still
fetches); **FG-08** — the flaky case's capture now hangs off the feed's own logger with its
level pinned (assertion unchanged, per the never-widen-a-flake rule). Three pins added
(`test_t4_trust.py`). Gates after the pass: **1,756 passed / 3 skipped / 0 failed** on both
interpreters, **41/41** node selftests, **AUDIT CLEAN** (125 modules), ruff clean, both goldens
exact. Nothing is committed; the worktree carries the pass.

---

## 2. Executive Risk Summary

| Priority | Finding | Impact | Confidence | Ship Requirement |
|---|---|---|---|---|
| **P2** | **FG-03** Distributable lag — `dist`/zip/SBOM/Setup are the §129c build; 6 UI files + `engine-progress.js` newer in source (`alpaca-card.js`, `index.html`, `menubar.js`, `shell.js`, `ui.css`, `ui.js`) | A downloader gets a build without the §130–§134 fixes; the artifact itself is consistent and passes every probe | **Confirmed** (measured, both file sets hashed) | **Required decision before publishing** (rebuild recommended) |
| **P2** | **FG-04** The release content is uncommitted (96-entry worktree, +4,338/−443 over `797eea0`); CI has never run it | You cannot publish a worktree; CI-only failure classes (machine-reading pins, real-time checks, locale codecs) are unexercised | **Confirmed** (`git status`, `git log`) | **Required before release** — commit, then watch CI to green |
| **P3** | **FG-01** README measured claims stale (8 rows + 3 badges) | The public README understates the test count and misstates module/line counts; the File Inventory is the page engineers check | **Confirmed** (re-derived against the tree) | **Required before publishing** (one documentation pass) |
| **P3** | **FG-02** Release identity: no git tag; three labels (`0.1.0`, `v0.1.0-beta`, `v0.1b`) | A release without a tag cannot be re-identified later; three names invite confusion in issues | **Confirmed** (`pyproject.toml:7`, README:109, `git tag -l` empty) | **Required before publishing** (decide + tag) |
| **P3** | **FG-05** A top-bar symbol pick starts the engine (after the Engine view has been visited once) | A live venue connection + tick persistence from a selection; discoverable (pill, progress bar) but implicit | **Confirmed** (reproduced live, case A) | Owner decision; document or gate it |
| **P3** | **FG-06** `chartLoadWatch()` retries `loadChart()` every 5 s, unbounded, while the chart view is open and the series do not match the selection | 1 request / 5 s while a permanently failing endpoint keeps mismatching | **Confirmed** (code, `ui.js:416-424`) | Can defer |
| **P3** | **FG-07** `refreshLiveChip()` issues one extra `GET /api/control/engine/status` per status application (2 s cadence; 480 ms during transitions) | ≤0.5 req/s extra on loopback; each carries the per-symbol gap computation (bounded: 500 retained ticks/symbol) | **Confirmed** (code, `ui.js:296-325`) | Can defer; measure before changing |
| **P3** | **FG-08** One intermittent test failure observed in a full-suite run (`test_hyperliquid_feed.py::test_the_listing_does_not_stop_the_mapping_when_the_rest_call_fails`), not reproducible in isolation or in either re-run | A flaky gate: costs a CI re-run and erodes trust in a green suite | **Confirmed** (1 of 5 full runs; 6/6 green in isolation afterwards) | Can defer; capture the assertion on the next occurrence |

**Carried ledger (re-verified this pass; full table in §5):** RA-01 → fixed (re-proven live);
RA-02 → fixed (fresh profile `400`); RA-03 → fixed (bandit/dispositions unchanged, pin green);
F-05 → landed (`logs.AbortedSocketFilter`); F-08 → landed (0 High in bandit); SS-1…SS-14 → closed /
carried unchanged. No Critical; no High; nothing unpatched from the prior two ledgers.

---

## 3. Verified Architecture Map

**Entry points.** `orderflow_system.desktop.__main__` → `launcher.main` (window geometry →
single-instance mutex → FastAPI in a daemon thread, **loopback only** → `/healthz` wait →
pywebview/WebView2 on `http://127.0.0.1:<port>/desktop`, browser fallback). Standalone demo:
`python -m orderflow_system.dashboard` (same server family, port-robust). Frozen build: the same
`launcher.main` under PyInstaller (onedir), `sys.frozen` true.

**Frontend/backend boundary.** The page is served by the origin it calls: `desktop/ui` mounted at
`/desktop/`, legacy widget modules at `/static/`; REST + one `/ws` websocket; `Cache-Control:
no-store`; meta CSP (`script-src 'self' <hash> 'unsafe-eval'`, `connect-src 'self' ws://127.0.0.1:*`,
`object-src/frame-src/base-uri 'none'`). No `js_api` bridge. `LocalRequestGuard` (installed at
import in `dashboard/app.py`) refuses non-loopback Host and cross-origin/cross-site mutations.
Interactive docs are **on in a source checkout and off in the frozen build**
(`dashboard/app.py:42-54 endpoint_policy()`; `OFAP_OPENAPI=1` re-enables) — measured: `/docs`,
`/redoc`, `/openapi.json` = 200 on the dev server, **404 on the frozen exe**.

**UI composition.** 34 view sections (31 static rail + `guide`/`scanner`/`help` injected at
runtime), one terminal/classic layout system (`ui.layouts` in the config store, 5-deep version
rings with auto-cull), one widget-window host (`desktop/windows.py` + `launcher.NativeWindowHost`,
10 snap presets, move/arrange/rescue), overlay layers: wizard, hints, help, look-up, nav-return
(single-slot), presets, tips. Every panel module self-inits on first activation; pollers guard on
visibility and on the `intent.js` lease.

**Data flow.**
```
venue WS/REST ─► data/*_feed.py (finite gates; FeedSession reconnect ladder + heartbeat)
                     │
                     ├─ primary book (50 lvl) ──┐   atlas/hub.on_orderbook: the PRIMARY book is
                     │                          │   skipped while a FRESH extras book exists
                     └─ extras: ONE socket for │   (4 s→20 s TTL, hub.py:524-531)
                        all symbols (trades,   │
                        deep 200-lvl book,     ▼
                        liquidations, BT)  atlas/depthmap.py (time-bucketed columns, leashed
                                          colour ceiling §122, `until` anchor §121)
                                                     │
      atlas/api.py ── heatmap/tape/cvd/frames/trackers ──┐
      desktop/api.py ── control surface (110 ops) ───────┤ FastAPI (loopback) ── /ws broker
      dashboard/* ── legacy pipeline + demo fallback ────┘        (bounded queues)
                                                     │
                              UI modules (fetch `api()` + OFAPBUS dedupe + OFAPINTENT leases)
                                                     │
                        canvas 2D renderers (ofx.js, heatmap-pro, atlas) + DOM readouts
```
**Engine.** `EngineController` publishes stage marks (`STAGE_PLAN` `engine.py:1316`, `_mark()`
`:1337`) — `config · instruments · build · connect` up, `feeds · history · release` down — which the
§132 progress bar renders (`engine-progress.js`, one 120 ms beat registered with `OFAPPause`).

**State + persistence.** One per-user config under `%APPDATA%\OrderFlowAnalysisPro` (atomic writes,
every field clamped by `config_store._sanitise`), one SQLite DB (WAL, retention + checkpointing),
logs with a rotation ring, exports under `exports\`. Secrets are **write-only** at the API: the
`SEC-09` mask protocol returns placeholders from `GET /config`/`/bootstrap` and adopts the stored
value when the mask is posted back (`config_store.mask_secrets` / `secret_or_stored`).

---

## 4. Full Findings Register

### [FG-01] [P3] The README's measured claims are stale by one wave of work

- **Confidence:** Confirmed
- **Audit domain:** E — open-source readiness / documentation accuracy (Phase 2F)
- **Affected files and exact references:** `README.md` lines 5–10 (badges), 353, 657 (module
  claims), the `## File Inventory` table; `CONTRIBUTING.md` baseline line.
- **Preconditions and trigger:** reading the published README; the drift is visible to any engineer
  who counts.
- **Expected behavior:** every self-measurement in the README matches the tree it describes.
- **Observed or code-proven behavior:** measured on this tree (`evidence/count_rederivation.txt`):

  | Claim | README | Measured |
  |---|---|---|
  | tests badge | 1,584 passing | **1,753 passed / 3 skipped** |
  | vanilla-JS modules | 115 (35 selftests) | **126 (41 selftests)** |
  | UI lines claim | ~45,567L across 115 files | **48,502L across 126** |
  | Desktop UI row | 125 files / 49,112 | **136 / 52,157** |
  | Desktop app row | 39 / 19,460 | 39 / **20,091** |
  | Atlas row | 30 / 9,481 | 30 / **9,672** |
  | Data feeds + storage row | 17 / 7,368 | 17 / **7,372** |
  | Analytics row | 17 / 3,196 | 17 / **3,206** |
  | Legacy dashboard row | 14 / 2,658 py / 4,859 ui | **5 py + 10 web** / **2,666** / **5,056** |
  | Total row | 246 / 98,326 | **248 / 97,356** |
  | suite line | 146 files / 27,729 | **160 / 30,274** |
  | API badge | 186 routes | **correct** (185 OpenAPI ops + `/ws`) |
- **Evidence:** `evidence/count_rederivation.txt`, `evidence/readme_claims.txt`; counting rules
  reproduced from `orderflow-analysis-pro-ops` (per-file `wc -l`, `__pycache__` excluded).
- **Root cause:** the last full re-derivation predates §119–§134 (≈11 new UI modules, 14 new test
  files, a new engine view section).
- **User/system/release impact:** none at runtime; the README is the first artifact an engineer
  checks, and a wrong File Inventory costs credibility on arrival.
- **Why this matters for a v0.1b release:** the directive's checklist includes "README accurate";
  today it fails.
- **Minimal safe remediation:** one documentation pass re-deriving all rows/badges from the tree —
  the one-pass swap rule (apply every replacement simultaneously; a new value can be another
  claim's old value).
- **Compatibility and regression risk:** documentation only.
- **Required tests/measurements before merge:** re-run the count script
  (`OFAP_v0.1b_final_audit/rederive_counts.py`) and the OpenAPI count from a running app.
- **Rollback:** revert the doc commit.
- **Dependency/order:** must land **before** the release commit so the published README is true.
- **Ship status:** **Required before release** (documentation; non-blocking to code). — **CLOSED
  in the §135 fix pass**: re-derived and rewritten (`evidence/fg01_tokens.txt`; 29 claims
  re-verified `ok`, 10 rewritten; the script is the re-runnable pin — no unit test reads doc
  counts by design).

### [FG-02] [P3] Release identity: no tag, three version labels

- **Confidence:** Confirmed
- **Audit domain:** F — build/operational release quality
- **Affected files:** `pyproject.toml:7` (`version = "0.1.0"`), `README.md:109`
  ("**v0.1.0-beta.**"), `installer/modflow.iss` + artifacts (`…-Setup-0.1.0.exe`), the directive and
  handoff consistently say **v0.1b**; `git tag -l` → empty.
- **Preconditions/trigger:** publishing the repository as it stands.
- **Expected behavior:** one release identity that a user, a bug report and a future maintainer can
  all resolve (tag ⇄ package version ⇄ artifact name).
- **Observed:** three names in play, no tag.
- **Evidence:** `evidence/gates_battery.txt` (HEAD block), `git tag -l`, `dist/` listing in
  `evidence/supply_chain.txt`.
- **Root cause:** nothing has been released yet, so the identity never had to be pinned.
- **Impact:** support/issue triage ambiguity; no runtime effect.
- **Why it matters:** the checklist item "version/tag/package metadata correct" cannot pass today.
- **Minimal safe remediation:** choose the label (suggest `v0.1.0-beta` to match README + artifacts,
  or rename the artifacts to `0.1.0b`), then `git tag -a` at the publish commit.
- **Compatibility/regression risk:** renaming artifacts would change download URLs; prefer
  aligning the README/directive wording to the artifact name if unsure.
- **Required tests:** none (metadata).
- **Rollback:** delete/retag before publishing.
- **Dependency/order:** same commit as the release tag.
- **Ship status:** **Required before release** (metadata). — **CLOSED in-tree in the §135 fix
  pass**: the README now carries the *Release identity* line (`0.1.0` ⇄ `v0.1.0-beta`); creating
  the tag is a publish-pass step.

### [FG-03] [P2] The distributables lag the source tree by the §130–§134 waves

- **Confidence:** Confirmed
- **Audit domain:** F — build/release quality (artifact truthfulness)
- **Affected files:** `dist/ModFlowOrderFlowAnalysisSuite/…` (exe `1863553f…`), `dist/…-win64.zip`
  (896 entries), `dist/…-win64.sbom.cdx.json` (45 components), `dist/…-Setup-0.1.0.exe`
  (`e39e3adc…`, 37,693,744 B), `BUILD_INFO.json` (`commit 797eea0`, `worktree_state: dirty`, built
  `2026-09-19T20:20:02+0930`).
- **Preconditions/trigger:** downloading and installing the shipped Setup.
- **Expected behavior:** the shipped artifact contains the source state of its own `BUILD_INFO`
  commit **plus** any source wave the owner intends to ship.
- **Observed (measured by hashing both file sets):** 76 UI files identical, **6 differ** —
  `alpaca-card.js`, `index.html`, `menubar.js`, `shell.js`, `ui.css`, `ui.js` — and
  `engine-progress.js` (+ `.selftest.js`) is absent from the payload. The packaged `index.html` does
  **not** reference `engine-progress.js`, so the artifact is internally consistent (no 404 class;
  the 41 missing `*.selftest.js` files are pruned by the build on purpose).
- **Evidence:** `evidence/frozen_guard_probe.txt` (23/23 on the artifact), the file-set diff quoted
  in §7 (`packaging lag` receipt), `evidence/supply_chain.txt` (hashes).
- **Root cause:** §130–§134 were recorded as source-only waves; the rebuild decision is still open
  in `docs/RESUME.md`.
- **Ownership/lifecycle:** none — packaging.
- **User impact:** a user who installs from the download does not get the §130 instrument-title fix,
  the §131 hover-text fix, the §132/§133 engine progress bar or the §134 menu-close fix.
- **Why it matters:** the download is the product for most users; a documented lag is acceptable, an
  undocumented one is not. It **is** documented (RESUME "Owed"), which keeps this P2 and not higher.
- **Minimal safe remediation:** rebuild the chain on the final source state
  (`build_exe.py --clean` → frozen smoke → `make_release.py` → `make_installer.ps1` →
  `verify_installer.ps1`), then re-run the guard probe against the new exe.
- **Compatibility/regression risk:** a rebuild re-owes the Setup journey; keep the current artifact
  hashes in the record for rollback.
- **Required tests:** frozen smoke 18/18, frozen features 20/20, installer journey, this report's
  guard probe (23/23).
- **Rollback:** keep the §129c `dist/` copy; restore and re-publish the old hashes.
- **Dependency/order:** **after** FG-01/FG-02 and after the release commit, so `BUILD_INFO` names a
  real commit rather than a dirty tree.
- **Ship status:** **Required decision**; a rebuild is recommended before publishing. — **CLOSED
  in the §135 fix pass**: rebuilt on this content (dist exe `bb503bcd…`; zip
  `6a1926a7…` (43,040,670 B); Setup `D921D58E…`
  (37,699,102 B); SBOM `26dad36f…`), with the battery green
  (smoke 18/18, features 20/20, journey 11/11, frozen
  guard probe 23/23).

### [FG-04] [P2] The release content exists only as a dirty worktree

- **Confidence:** Confirmed
- **Audit domain:** F — release integrity
- **Affected:** the whole 96-entry delta (66 modified + 30 untracked; `evidence/delta_inventory.txt`).
- **Preconditions/trigger:** any attempt to publish, tag or have CI validate this content.
- **Expected behavior:** the thing being audited/released exists as a commit; CI has executed it.
- **Observed:** `git log -1` = `797eea0` (2026-09-19 10:48); `git status --porcelain | wc -l` = 96;
  no CI run has ever seen the delta (CI runs on push; the delta is uncommitted).
- **Evidence:** `evidence/delta_inventory.txt`, `evidence/gates_battery.txt`.
- **Root cause:** the standing rule — commits happen only on the owner's explicit word.
- **Impact:** publishing as-is would ship a worktree snapshot; the documented CI-only failure
  classes (a pin that reads the machine; a check that measures real time; the locale codec) are
  unexercised by the local green suite.
- **Mitigation already in place:** the local gate stack runs the CI-equivalent steps (both
  interpreters, ruff 0.16.7, the UI audit, all selftests, both goldens) — green on this content.
- **Minimal safe remediation:** the standing push pass (junk sweep → `git add -A` → house-style
  commit → push to remote `moddy`) and watch the head run to green; fix CI with a small `ci:` commit
  if wiring fails.
- **Compatibility/regression risk:** none (process).
- **Required tests:** CI green on the pushed commit.
- **Rollback:** n/a (nothing published).
- **Dependency/order:** first step of the release sequence; FG-01/FG-02 should ride the same commit.
- **Ship status:** **Required before release.** — **OPEN by design**: the commit/publish pass is
  the owner's word (the standing gate). Everything else in this register is closed.

### [FG-05] [P3] A top-bar instrument pick can start the live engine

- **Confidence:** Confirmed (reproduced live, twice)
- **Audit domain:** B — UI/interaction and state correctness (and D — external side effects)
- **Affected files/symbols:** `orderflow_system/desktop/ui/ui.js:760-780` (`#symbolSelect` onchange →
  `ofap:symbol`), `orderflow_system/desktop/ui/ofx-view.js:1300-1304` (listener → `pickSymbol`),
  `ofx-view.js:1124-1137` (`pickSymbol` → `resolveSymbol` → `state==='ready'` →
  `runInstrumentAction('start_engine')`), `ofx-view.js:1193-1205` (the start itself).
- **Preconditions/trigger:** the Engine view has been initialised at least once in the session (its
  `ofap:symbol` listener registers on first activation), the engine is stopped, and the picked
  instrument is configured + enabled ("ready").
- **Expected behavior (as an auditor sees the top bar):** picking an instrument changes what the
  panels show. Nothing in the top bar's own copy says the feed starts.
- **Observed:** engine `stopped` → `running ['BTCUSDT']` within 2.5 s of the pick (receipt below);
  with the Engine view never opened, the same pick does nothing.
- **Evidence:** `evidence/symbol_pick_autostart.txt`; corroborated by the sandbox log
  (`Engine started: source=bybit symbols=['BTCUSDT']` five seconds after the page's first load,
  which is how the audit found it — traced to a probe that visited the Engine view and picked a
  symbol).
- **Root cause:** `pickSymbol()` deliberately auto-runs the resolved action so a pick "just works"
  (§82 design). It is not a defect in isolation — the panel prints `engine started — waiting for
  data` and the §132 bar shows the transition — but the *top bar* offers no such wording.
- **Ownership/lifecycle:** the engine's owned resources (feed sessions, hub, DB writes) are entered
  through the normal start path, and stop remains explicit.
- **User/release impact:** an unintended live venue session (and tick persistence) from a selection;
  for a broker-backed source (Alpaca/MT5) that is a session the user did not knowingly open.
- **Why it matters for v0.1b:** "no failure mode that silently presents misleading data" is a
  governing principle; this is not misleading, but it is *surprising* for a trading surface.
- **Minimal safe remediation (pick one):** (a) document it — one line in the `symbolSelect` title +
  the help topic `work.instruments`; or (b) gate `start_engine` behind an explicit click (drop that
  one branch in `pickSymbol`, keep the button in the look-up panel); or (c) keep the auto-start and
  say it in the toast the pick produces.
- **Compatibility/regression risk:** (b) changes a workflow the owner built on purpose; (a)/(c) are
  copy-only.
- **Required tests:** a pin that asserts the chosen behaviour (auto-start present **or** absent) so
  it cannot drift silently.
- **Rollback:** revert the one branch/copy line.
- **Dependency/order:** independent; do not bundle with the release commit unless it is copy-only.
- **Ship status:** **Can defer** — owner decision; not a blocker. — **CLOSED in the §135 fix
  pass**: the least-invasive option, documentation-only (selector tooltip + the Instruments help
  topic; behaviour preserved by design), pinned in `test_t4_trust.py`.

### [FG-06] [P3] `chartLoadWatch()` retries the chart load every 5 s without a stop condition

- **Confidence:** Confirmed (code) 
- **Audit domain:** B/A — UI lifecycle and bounded work
- **Affected:** `orderflow_system/desktop/ui/ui.js:416-424` (`chartLoadWatch`), called from
  `applyStatus` (`ui.js:440`).
- **Preconditions/trigger:** the Chart view is active, and either `S.chartSymbol !== S.symbol` or
  `S.lastDeltaSymbol !== S.symbol` — i.e. a load that never landed (endpoint erroring, series for
  another instrument).
- **Expected:** retries stop or back off when the failure is permanent.
- **Observed:** a fixed 5 s floor, no attempt cap, for as long as the view is open.
- **Evidence:** code (cited lines); the retry shape is deliberate ("retry until it lands", §127's
  record) and mirrors the Systems-board pattern.
- **Root cause:** retry-until-it-lands chosen over a backoff because the failure mode it fixes is a
  transient boot-burst stall.
- **Impact:** one request / 5 s against a local server in the worst case; no growth.
- **Why it matters:** bounded but unbounded-in-time work on a hot view; worth a cap (e.g. 12 tries)
  when someone next touches this file.
- **Minimal safe remediation:** add an attempt counter with a spoken failure after N tries.
- **Compatibility/regression risk:** low; the counter must reset on a symbol change.
- **Required tests:** a pin driving a failing loader and asserting the retries stop.
- **Rollback:** revert the counter.
- **Dependency/order:** independent.
- **Ship status:** Can defer. — **CLOSED in the §135 fix pass**: bounded
  (`CHART_RETRY_MAX = 12`), spoken in the chart head, reset on a new selection, pinned in
  `test_t4_trust.py`.

### [FG-07] [P3] One duplicate status fetch per poll while the engine runs

- **Confidence:** Confirmed (code)
- **Audit domain:** C/D — hot-path cost
- **Affected:** `orderflow_system/desktop/ui/ui.js:296-325` (`refreshLiveChip`, called from
  `applyStatus`) issues `GET /api/control/engine/status` although the shell's own poll just carried
  the same payload; `desktop/engine.py:1283` (`tick_gaps`) is computed per symbol on every status
  read.
- **Preconditions/trigger:** engine running; every status application (2 s cadence; 480 ms while
  the progress bar's fast poll is armed).
- **Expected:** one status read per cycle.
- **Observed:** two (the extra one only for the tooltip's provenance line).
- **Evidence:** code + the payload cost basis: `_recent_ticks_max = 500` (`main.py:322`) bounds
  `tick_gaps` to a ≤500-element sort per symbol per read.
- **Impact:** ≈0.5 req/s extra on loopback; <1 ms of Python per read at 7 symbols. Measured baseline
  (soak): JS heap flat 4.51→4.61 MB, listeners 809→810.
- **Why it matters:** it is the kind of duplication that grows if copied; measure before changing.
- **Minimal safe remediation:** pass the `st` payload into `refreshLiveChip(st)`; keep the extra
  fetch only when no payload is available.
- **Compatibility/regression risk:** low; the tooltip must still update on a bare visit.
- **Required tests:** a source pin that the function accepts a payload.
- **Rollback:** revert.
- **Dependency/order:** independent.
- **Ship status:** Can defer. — **CLOSED in the §135 fix pass**: the payload hand-over landed
  (`refreshLiveChip(status)`), pinned in `test_t4_trust.py`.

### [FG-08] [P3] One intermittent failure in the suite's full-run mode

- **Confidence:** Confirmed (observed once); cause not established
- **Audit domain:** F — test/release quality
- **Affected:** `orderflow_system/test_hyperliquid_feed.py::test_the_listing_does_not_stop_the_mapping_when_the_rest_call_fails`
  (the test itself drives a deterministic `meta=offline` callable and asserts on `caplog.records`).
- **Preconditions/trigger:** observed in the third full-suite run of this pass (after the two green
  runs quoted in §7); not seen in the two runs that followed.
- **Expected:** a deterministic test.
- **Observed:** `1 failed, 1752 passed, 3 skipped`; the failure line only (the assertion text was not
  captured — the run was tailed). Re-runs: the single test 3/3 green, the whole file 3× (27 tests
  each) green, two further full runs green.
- **Evidence:** `evidence/flake_check.txt` (both re-runs green) + the failing run's tail in the
  session log; the flake is 1 in 5 full runs.
- **Root cause (hypotheses, not conclusions):** cross-test logging state — the assertion reads
  `caplog.records`, and the suite contains tests that install the app's logging stack
  (`desktop/logs.py`) with handler filters; or an async ordering race inside the test's own
  `_run_feed` session. Not established — report-only pass did not instrument the failure.
- **Impact:** a CI re-run and a dent in the "green suite" claim.
- **Why it matters for v0.1b:** the release gate is the suite; a flaky case makes every future red
  result ambiguous (flake vs regression).
- **Minimal safe remediation:** on the next occurrence, capture `--tb=long -v` and the preceding
  test order; then either assert on a dedicated handler attached to the feed's logger (removing the
  dependency on global caplog state) or pin the ordering. Do not "fix" it by widening the assertion.
- **Compatibility/regression risk:** test-only.
- **Required tests:** the file itself, run 10× in a loop, plus one full-suite run.
- **Rollback:** revert the test change.
- **Dependency/order:** independent; before the release push, one more full run should be green.
- **Ship status:** Can defer (the suite is green in 4 of 5 runs and green in isolation). —
  **HARDENED in the §135 fix pass**: the capture is attached to the feed's own logger with its
  level pinned for the duration (the assertion is unchanged — never widen one to chase a flake);
  the defect has not recurred in the 10 full runs since (5-run flake loop: all green).

---

## 5. No-Issue Coverage (inspected, nothing found)

| Area | Evidence reviewed | Conclusion | Remaining uncertainty |
|---|---|---|---|
| Loopback guard family | live on dev server + **frozen exe**: hostile `Host` 403, cross-origin POST 403, `Sec-Fetch-Site: cross-site` POST 403, loopback POST 200, WS 101 native / 403 cross-origin (`evidence/fresh_profile_probe.txt`, `frozen_guard_probe.txt` 23/23) | Closed, re-verified on the artifact | none observed |
| Secrets posture | 4-way scan: worktree incl. untracked / full-history pickaxe (`ghp_`, `sk-`, `AKIA`, key files) / frozen payload / `git add -An` dry-run — clean; only test fixtures + example strings + the author's GitHub noreply address | Clean; no revocation needed | repo history outside this clone not examined |
| CSP + page errors | 34 views driven with a `securitypolicyviolation` collector installed pre-navigation: **0 violations, 0 page errors, 0 unhandled rejections**; live pill `data: live` | Confinement verified | inline `'unsafe-eval'` remains by design (studies engine) |
| XSS sinks (RA-01 class) | hostile symbol `<img src=X onerror="…">` planted through the store route → clamped to `IMGSRCXONERRORWINDOW.__R`; 0 parsed `img[src=X]`, `window.__RA_XSS` unset; the engine treats it as an unknown instrument and skips it with a reason | Closed and re-proven live | a second sink class could exist in a module not driven (all 34 views were) |
| Listener/timer accumulation | `churn_probe` 8 cycles × 34 views: **0 same-node accumulation, 0 detached-but-retained**; timers 13→14 with the Δ traced to a lazy one-time `context.js` 60 s poller; trip-diff probe: options-view poll released on every leave | No leak | longest observed window ≈3 min |
| Unbounded collections | 30 non-test `maxlen=` deque sites (re-counted); new stores bounded by construction (`_stage_log` 24, window records ≤ `WINDOWS_MAX`, layout version rings ≤10/5, `ui.recent` ≤8, tip list 4) | Bounded | a store added later could escape the pattern |
| Canvas/GPU/worker lifecycle | **No WebGL, no OffscreenCanvas, no Workers, no service worker, no IndexedDB** anywhere in `ui/` or `dashboard/static` (grep) — the stack is canvas **2D** + DOM; canvas law `backing == round(box × dpr)` pinned (§72) | Frame-stability class items N/A by construction | context-loss class cannot apply |
| Canvas fit/DPR | `math.layerSize(w,h,1)` identity pinned in `ofx.selftest.js`; the §72 audit's 16-scenario results stand (no canvas has no CSS box) | Verified by pin + prior live battery | not re-run physically this pass |
| Presets scan cost | measured in a busy page: 1.9 scans/s, avg 0.10 ms, worst 0.30 ms (`evidence/presets_scan_probe.txt`) | Negligible (<0.02% of a core) | a much heavier DOM could scale it linearly |
| Analytics correctness | goldens exact: analytics 40 cases / 2,196 numeric leaves / max diff 0.0; config golden 31 factories / 49 instruments | Numbers unchanged | replay-path analytics covered by suite, not re-measured live |
| Ingest gates | `math.isfinite` at every venue seam (`bybit_feed._finite`, `alpaca_normalize._num`), counts in `book_health()["junk_values"]`; suites green | Closed | venue behaviour beyond the adapters' contract not testable |
| WS delivery | bounded queues + drop counters; cancelled-writer pin; `asyncio.timeout` (not `wait_for`) in the delivery path | Closed | — |
| Aux windows | `test_aux_windows.py` (69 collected) + `windows-ui.selftest.js`; live §128 battery stands; headless answers `native:false` and the UI draws no controls (re-verified) | Closed | one physical display only |
| Config secrets masking | `mask_secrets`/`secret_or_stored` read + live: `GET /config` on a virgin profile carries no cleartext secret; masked re-post preserves the stored value (§126 battery) | Closed | — |
| Interactive docs exposure | dev 200 / frozen 404, deliberate and documented (`app.py:42-54`) | Accepted (loopback-only) | if the product is ever bound beyond loopback, re-open this |
| Supply chain | `uv lock --check` green (62 pkgs); `pip-audit` clean (59 pkgs); SBOM 45 components, CycloneDX 1.5, reproduced in `dist/`; zip `testzip()` OK on 896 entries; every CI `uses:` SHA-pinned; `permissions: contents: read`; `persist-credentials: false` | Closed | CI has not run the delta (FG-04) |
| Static analysis (bandit, `-ll`) | 27 Medium, **0 High** (the B324 sha1 is gone): 20× B310 urlopen (19 fixed/loopback/vendor URLs incl. two `# noqa: S310` annotations, 1 test-only), 5× B608 (fixed identifiers / column list from a frozen tuple), 1× B314 (DTD-refused XML), 1× B104 (a test asserting the 0.0.0.0 warning) | All dispositions stand; nothing new-class | external scanners will keep flagging them |
| Tree hygiene | no stray probe artifacts; the audit itself left the worktree at exactly 96 entries | Clean | — |

---

## 6. Remediation Plan in Safe Merge Order

Nothing below is executed by this pass. Each change is isolated, reversible and lands with its own
pin. **Do not bundle** FG-C4 (behaviour change) with the release commit; do not bundle FG-C5/FG-C6
with each other (different modules, different failure modes).

**Stage 0 — Baseline + observability (nothing user-visible).**
- **FG-C0.1 · 96-entry baseline commit.** Commit the current content exactly as it stands (house
  message style), push to remote `moddy`, and watch the head CI run to green. *Why here:* it turns
  the audited worktree into an addressable revision, gives CI its first sight of the delta, and
  makes every later change a diff against a known-good baseline. *Rollback:* nothing published yet;
  a commit can be amended before pushing. *Tests:* CI green (pytest 3.11+3.12, UI audit, selftests,
  ruff, pip-audit, SBOM), i.e. the local gate stack failing here names the CI wiring, not content.

**Stage 1 — Release blockers, minimal behavioural change.**
- **FG-C1.1 · README/CONTRIBUTING claim re-derivation (FG-01).** Re-derive the eight File-Inventory
  rows, the three badges, the module/line claims and the suite line in one simultaneous pass;
  re-count OpenAPI ops from a running app for the API badge. *Files:* `README.md`,
  `CONTRIBUTING.md`. *Rollback:* revert the doc commit. *Tests:* the count script + a served-app
  OpenAPI count. *Must be its own commit.*
- **FG-C1.2 · Release identity (FG-02).** Pick the label, align README wording, create the
  annotated tag at the release commit. *Rollback:* retag before publishing.
- **FG-C1.3 · Distributable rebuild (FG-03).** `build_exe.py --clean` → frozen smoke (18/18) →
  frozen features → `make_release.py` (zip + SBOM) → `make_installer.ps1` → `verify_installer.ps1`;
  then re-run the frozen guard probe and quote the new hashes. *Why after FG-C0.1:* `BUILD_INFO`
  then names a real commit and `worktree_state: clean`. *Rollback:* keep the §129c `dist/` aside.
  *Must be its own commit(s) + artifacts.*

**Stage 2 — High-confidence reliability/correctness cleanups.**
- **FG-C2.1 · `chartLoadWatch` attempt cap (FG-06).** Counter + spoken failure; reset on symbol
  change. *Tests:* drive a failing loader, assert retries stop. *Rollback:* revert.
- **FG-C2.2 · Single status read per cycle (FG-07).** `refreshLiveChip(st)`; keep the fallback
  fetch for the no-payload path. *Tests:* source pin + a live check that the tooltip still fills.
  *Isolate from FG-C2.1.*
- **FG-C2.3 · Flake capture (FG-08).** Before the release push, run the suite once more green; if the
  hyperliquid case recurs, capture `--tb=long -v` + the test order and pin it (dedicated log handler
  instead of `caplog`). *Test-only; do not widen the assertion.*

**Stage 3 — Owner decisions (not code-first).**
- **FG-C3.1 · Symbol-pick engine start (FG-05).** Decide: document (copy-only) or gate (one branch).
  If gated, add the pin that asserts the chosen behaviour. *Do not bundle with the release commit.*

**Stage 4 — Documentation and hygiene.**
- **FG-C4.1 ·** `docs/` publication-surface pass (carried F-07/RA-05) — owner's call; the docs carry
  programme logs and audit trails but no credentials and no personal paths (re-measured).
- **FG-C4.2 ·** `SECURITY.md`/README "known limitations" line refreshed with this pass's honest
  limits (bounded soak, one display, no broker accounts).

**Stage 5 — Deferred post-v0.1b.**
- Backlog items unchanged: radar walls / big-trade zones, spent-state persistence, config slots;
  plus this report's §9 list.

---

## 7. Validation Matrix

All commands ran in `C:\Users\Moddy\OrderFlow-Analysis-Pro` with `PYTHONPATH` unset. "Not executed"
is used wherever a check did not run — never inferred.

| Validation | Command or scenario | Expected result | Actual result | Status |
|---|---|---|---|---|
| Pytest (3.11) | `.venv/Scripts/python.exe -m pytest orderflow_system -q` | all green | **1,753 passed, 3 skipped, 0 failed** (68.4 s) | PASS |
| Pytest re-runs (flake check) | two further full runs after the record edits (`evidence/flake_check.txt`) | green | 1,753/3/0 and 1,753/3/0; an intervening third run showed **1 failed / 1,752 passed** in `test_hyperliquid_feed.py` (FG-08) | PASS (4 of 5 runs) |
| Pytest (CI semantics) | `PYTHONUTF8=0 … -m pytest orderflow_system -q` | identical | **1,753 / 3 / 0** (69.1 s) | PASS |
| Skip inventory | `-q -rs` | every skip documented | 3 skips = 2 opt-in Alpaca live-stream tests + 1 network test, all env-gated | PASS |
| UI reference audit | `scripts/audit_ui_refs.py` | `AUDIT CLEAN` | AUDIT CLEAN — 125 modules parse, imports ok | PASS |
| Lint | `uvx ruff@0.16.7 check orderflow_system scripts` | clean | `All checks passed!` | PASS |
| Node selftests | `node orderflow_system/desktop/ui/*.selftest.js` | all pass | **41/41** (`… 0 failed` each; `engine-progress`, `heatview`, `navreturn`, `presets`, `tips` included) | PASS |
| Goldens | `scripts/regen_analytics_golden.py` / `regen_config_golden.py` | exact | analytics: 40 cases / 2,196 leaves / **max diff 0.000e+00**; config: 31 factories / 49 instruments | PASS |
| Fresh-profile first run | `fresh_probe.py` vs a virgin scratch `%APPDATA%` (21 checks) | no 500s; sentences not tracebacks | **21/21 PASS** (incl. `data/export` → `400 "no tick history…"`, `journal` 200 on a virgin DB, `layouts` state `autocull/keep/max`) | PASS |
| Local guard family (dev) | hostile Host / cross-origin / cross-site / loopback POST; WS 101/403 | 403/403/403/200, 101/403 | exactly that | PASS |
| Local guard family (frozen exe) | `frozen_guard_probe.py` on 8098, scratch APPDATA | all hold on the artifact | **23/23 PASS** (docs 404 ×3, served==packaged for 8 shell files, CSP meta, export traversal name stays inside `exports\`, `app.frozen=true`) | PASS |
| CSP + page errors | 34 views driven, collector installed pre-navigation | 0/0 | **0 violations, 0 page errors**, WS live | PASS |
| Route inventory | `GET /openapi.json` on the dev server | badge source | **185 operations** (control 110, atlas 59, rest legacy) + `/ws` = 186 | PASS |
| Secrets scan (4 ways) | worktree+untracked / history pickaxe / frozen payload / `git add -An` | clean | clean (only fixtures, examples, the author's noreply address) | PASS |
| Supply chain | `uv lock --check`; `uv pip freeze` → `uvx pip-audit -r`; bandit `-ll`; `zipfile.testzip()`; SBOM parse | lock green, no vulns, dispositions only | lock resolved 62 pkgs; pip-audit: no known vulnerabilities (59 pkgs); bandit 27 Medium / **0 High**; zip 896 entries OK; SBOM CycloneDX 1.5 / 45 components | PASS |
| Churn probe (8 cycles × 34 views) | `churn_probe.py --port 8099 --cycles 8` | 0 accumulation | **0 same-node, 0 detached-retained**, timers 13→14 (one lazy `context.js` poller, proven one-time) | PASS |
| Poll-release probe (5 round trips) | `poll_release_probe.py`, `which_interval.py`, `interval_diff.py` | view polls released on leave | options-view bus interval created/cleared per visit; no growth after trip 2 (new=0, gone=0) | PASS |
| Presets scan cost | `presets_scan_probe.py` (20 s busy window) | negligible | 38 scans, avg 0.10 ms, worst 0.30 ms | PASS |
| Live soak (bounded, live venue) | `soak.py --phase feed --engine-cycles 2 --engine-live-s 40` (scratch profile; Bybit BTCUSDT; one cycle inherited an already-running engine) | flat JS, no growth in listeners | JS heap 4.51→4.61 MB, listeners 809→810, DOM ~14.7k, **0 console / 0 page errors**; serving RSS 131.1→136.0 MB over ~100 s (documented early bounded-store fill) | PASS (bounded) |
| Auto-start probe | `autostart_probe.py` — plain page load, engine stopped | no silent start | engine stayed `stopped` for 30 s | PASS |
| Symbol-pick behaviour | `symbol_pick_autostart.py` — case A (Engine view visited) / case B (never opened) | characterise | A: `stopped` → **`running ['BTCUSDT']`** in 2.5 s; B: no change | **FINDING FG-05** |
| Packaging lag | hash both UI file sets | quantify | 76 identical, **6 differ**, `engine-progress.js` absent (41 selftests pruned by design) | **FINDING FG-03** |
| New-artifact battery | `ofap_smoke.py` / `ofap_frozen_features.py` / `verify_installer.ps1` / `frozen_guard_probe.py` on the §135 rebuild | smoke 18/18, features 20/20, journey 11/11, probe 23/23 | 18/18 · 20/20 · 11/11 · 23/23 | PASS |
| Fix-pass pins | `test_t4_trust.py` (3 new pins: chart-retry bound, payload hand-over, pick-starts-engine copy) | pass | 1,756 = 1,753 + 3 | PASS |
| Flake loop (5 × full suite) | `evidence/flake_repro.txt` | all green | 1,753/3/0 five times | PASS |
| Frozen smoke | (not re-run this pass) | 18/18 | prior §129c run: 18/18 + features 20/20 + journey 11/11 | Not executed (artifact unchanged; guarded by probe 23/23) |
| Installer journey | (not re-run) | install→uninstall clean | prior run 11/11 | Not executed |
| Long soak (≥1 h) | — | flat tail | not run (owner's standing instruction) | Not executed |
| Physical multi-monitor | — | real move/snap on two displays | not run (one display on this host) | Not executed |
| Broker accounts (MT5/NT/Alpaca) | — | live session | not run (no accounts) | Not executed |
| CI on this content | push the delta | green head run | CI has never seen the delta | Not executed (FG-04) |

---

## 8. Release Checklist

| # | Item | Status | Receipt |
|---|---|---|---|
| 1 | Working tree reviewed | **YES** — 96 entries enumerated at audit time, nothing changed by the *audit*; the §135 fix pass then landed 7 files + the report/records | `evidence/delta_inventory.txt`, §135 closure |
| 2 | Version / tag / package metadata correct | **YES in-tree** — the README's *Release identity* line pins `0.1.0` ⇄ `v0.1.0-beta`; **the tag is created in the publish pass** | §135 closure; `README.md` |
| 3 | License present | **YES** — `LICENSE` (MIT) + `THIRD_PARTY_NOTICES.md` in tree and in `dist/` | `supply_chain.txt` |
| 4 | README accurate | **YES** — re-derived: 10 `(NNNL)` claims, 3 badges, 8 rows + total, the suite line (29 claims re-verified, 10 rewritten) | `evidence/fg01_tokens.txt` |
| 5 | No secrets committed | **YES** — 4-way scan clean; `.gitignore` covers `.env*`, keys, DBs, logs, build dirs | `secrets_scan.txt` |
| 6 | Lockfile present and consistent | **YES** — `uv.lock` (374,898 B), `uv lock --check` green | `supply_chain.txt` |
| 7 | Clean installation works | **YES (source)** — fresh-profile boot 21/21 on a virgin `%APPDATA%`; frozen exe boots and answers 23/23 | `fresh_profile_probe.txt`, `frozen_guard_probe.txt` |
| 8 | Lint / tests / build pass | **YES** — after the fix pass: **1,756/3/0** ×2 interpreters (+3 pins), 41/41 selftests, AUDIT CLEAN, ruff, goldens; **build re-run** on this content | `evidence/gates_after_fixes.txt` |
| 9 | Production smoke test passes | **YES on the rebuilt artifact** — smoke 18/18, features 20/20, installer journey 11/11, frozen guard probe 23/23 | `evidence/rebuild_135_*.txt` |
| 10 | P0/P1 findings resolved | **YES** — none open (two P2, five P3; no P0/P1) | §4 |
| 11 | Runtime validation completed | **PARTIAL** — bounded soak, churn, CSP, guards, fresh profile; long soak + physical multi-monitor outstanding | §7 |
| 12 | Known limitations documented | **YES** — the README's alpha/beta block plus this report's §1 bullet 9 (bounded soak, one display, no broker accounts, CI-not-yet-run) | README §Status; §1 |
| 13 | Release artifact inspected | **YES** — the §135 rebuild: hashes, BUILD_INFO, zip integrity, SBOM, served-vs-packaged parity, guard probe 23/23, payload markers | `evidence/rebuild_135_*.txt` |
| 14 | Rollback / release plan documented | **YES** — §6 carries per-change rollback; artifact rollback = keep the §129c `dist/` | §6 |

**Decision inputs (after the §135 fix pass):** 1–10, 12–14 pass; 11 stays partial by scope (long
soak + the owner's physical multi-monitor pass). Items 2, 4 and 9 now read YES **in-tree / on the
rebuilt artifact**; the only things still owed are the owner's acts — commit, tag and publish.
That is the whole basis of **SHIP ONLY AFTER REQUIRED FIXES** → now *READY TO SHIP* on the
owner's word.

---

## 9. Deferred Work (safe to defer — why)

1. **FG-06 chart retry cap** — worst case is 1 request / 5 s on loopback while a view is open; no
   growth, no user-visible defect. Defer until the file is touched.
2. **FG-07 duplicate status fetch** — measured ≤0.5 req/s and <1 ms/s of Python; the tooltip it
   feeds is a provenance nicety.
2b. **FG-08 flaky test case** — 1 failure in 5 full runs, green 6/6 in isolation; defer until it
   recurs with the assertion captured (pinning it now would fix the wrong thing).
3. **FG-05 symbol-pick auto-start** — the behaviour is deliberate, discoverable and harmless in the
   keyless default venue; it needs a decision, not a fix.
4. **F-07 / RA-05 `docs/` publication surface** — programme logs and audit trails are legitimate
   open-source artifacts for a maintainer-run project; no credentials or personal paths (re-measured
   this pass). Owner's call.
5. **bandit Medium dispositions** — fixed/loopback URLs, frozen-identifier SQL, DTD-refused XML, a
   test-only bind assertion. An external report will flag them again; the triage is recorded here.
6. **Multi-monitor physical pass** — one display on this host; the placement maths is pinned over
   every screen shape (§128) and the OS window battery ran on the one real screen.
7. **Long soak / RSS plateau** — the owner's standing instruction; the bounded stores (30 `maxlen`
   sites, capped rings) plus the memory audit's traced cap evidence stand in for it.
8. **Vendor-account lanes (MT5 / NinjaTrader / Alpaca live)** — no accounts on this machine; the
   adapters' probes and tests are green and the add/remap paths are pinned.

---

## 10. Audit Coverage Matrix

| Subsystem / directory | Status | Risks examined | Unreviewed gaps |
|---|---|---|---|
| `orderflow_system/desktop/` (launcher, api, engine, config_store, windows, dataport, logs, storage, single_instance, param_registry, help, journal, paper, profiles, updater, alpaca, platforms, edgar, calendar, marketwatch) | Inspected (delta read line-by-line; prior audits for the rest) | lifecycle, clamps, masking, export paths, window ownership, stage marks, URL quoting, atomic writes | `updater.py` download path re-read only (prior audit), `edgar.py` cache caps carried |
| `orderflow_system/desktop/ui/` (126 `.js` incl. 41 selftests, CSS, HTML) | Inspected (delta + new modules read; 34 views driven live; sinks swept) | escaping, listeners/timers, view state, canvas fit, intent leases | modules not on the driven path (e.g. `options.js` deep internals) read only where the probe touched them |
| `orderflow_system/atlas/` (hub, api, depthmap, feed_extras, replay, history, context, notify…) | Partially inspected (delta + hubs read; heatmap/until/scale verified by tests) | single-socket extras, book authority TTL, scale leash, time anchor | live replay soak not re-run |
| `orderflow_system/data/` (feeds, database, feed_session) | Partially inspected (prior audits carried; `database.py` delta read) | ingest gates, reconnect ladder, SQL identifiers | per-venue live behaviour beyond probes |
| `orderflow_system/analytics/`, `patterns/`, `signals/`, `alerts/`, `main.py` | Inspected via pins + goldens | numeric drift, iterator/dtype removal, aggregator symbol tagging | no fresh live replay of the legacy pipeline |
| `orderflow_system/dashboard/` (app + static) | Inspected (delta read; guard + docs policy verified live) | guard family, signals filter, demo guards | legacy page not re-driven in a browser |
| `orderflow_system/scripts/` (`audit_ui_refs.py`, `build_exe.py`, `make_release.py`, `verify_installer.ps1`, `churn_probe.py`, goldens) | Inspected | gate integrity, packaging asset roots, probe hygiene | build not re-run this pass |
| `installer/` (Inno pipeline) | Partially inspected (carried; journey not re-run) | per-user install, ARP, uninstall, `CloseApplications` | journey re-run owed on a rebuild |
| `dist/` (exe, zip, SBOM, Setup) | Inspected (hashes, integrity, guard probe, packaging lag) | artifact truthfulness | none beyond the lag finding |
| `.github/workflows/ci.yml` | Inspected | action pins, permissions, matrix, build gating, SBOM job | never executed on this content (FG-04) |
| `docs/` | Partially inspected (ledgers + this pass's re-derivations) | stale claims, publication surface | deep copy-edit of programme logs |
| `%APPDATA%\OrderFlowAnalysisPro` (runtime state) | Inspected via scratch profiles only | first-run behaviour, atomic writes, retention | owner's real profile deliberately untouched |
| Tests (160 files / 30,274 lines) | Inspected via execution (1,753 cases) | coverage of the delta (14 new files) | no coverage metric computed |
| Third-party / native (MT5, NinjaTrader bridge, WebView2) | Not verifiable here | — | needs the owner's terminals; the bridge ships as source + DLL with notices |

---

## Appendix — what a reviewer should re-run to reproduce this report

```
# gates
.venv/Scripts/python.exe -m pytest orderflow_system -q          # 1,753 / 3 / 0
PYTHONUTF8=0 .venv/Scripts/python.exe -m pytest orderflow_system -q
.venv/Scripts/python.exe scripts/audit_ui_refs.py               # AUDIT CLEAN
uvx ruff@0.16.7 check orderflow_system scripts
.venv/Scripts/python.exe scripts/regen_analytics_golden.py ; .venv/Scripts/python.exe scripts/regen_config_golden.py
for f in orderflow_system/desktop/ui/*.selftest.js; do node "$f"; done   # 41/41
# live
APPDATA=<scratch> .venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 8099
python OFAP_v0.1b_final_audit/ev/fresh_probe.py        # 21/21
python OFAP_v0.1b_final_audit/ev/csp_probe.py          # 0 violations / 34 views
python OFAP_v0.1b_final_audit/ev/churn_probe.py --port 8099 --cycles 8
# frozen artifact
APPDATA=<scratch2> dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe --headless --port 8098
python OFAP_v0.1b_final_audit/ev/frozen_guard_probe.py # 23/23
```

*Report generated 2026-09-19 by the release-audit pass (§135). No source file was modified; the
working tree still counts the same 96 entries it held at the start of the audit.*
