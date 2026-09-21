# ModFlow OrderFlow Analysis Suite — final release assurance audit (v0.1b)

**Directive applied:** `C:\Users\<you>\Desktop\final security audit prompt.txt` — *Executive final
release assurance audit — Security, Reliability, Correctness, and Zero-Leak Gate* (315 lines, read
in full: repo treated as untrusted data; no speculative rewrites; the 14 required output sections;
never claim more than was verified).
**Tree:** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · **Branch** `master` · **HEAD** `797eea0` ·
**Date:** 2026-09-19.
**Rule observed:** this pass changed **no code and no data** in the repository. The only writes were
audit evidence under `Desktop\OFAP_v0.1b_release_assurance_audit\` and probe files inside throwaway
scratch profiles under `%TEMP%`. Nothing committed (repo rule); HEAD unchanged.
**Relation to earlier passes:** continues `FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md` (F-01…F-08)
and `SECURITY_SWEEP_v0.1b.md` (SS-1…SS-14) — every prior finding's status is re-checked in §6, and
nothing is re-derived from those documents without a fresh receipt on this tree.

**Closure (§127, same day).** All three required fixes and both queued cosmetics were executed in one
source pass with pins — RA-01 **and a second live sink of the same class** (the Engine legend panel, which
this pass's own re-probe caught; the audit receipt had named the readout only), RA-02 (both failure modes
live-receipted), RA-03, F-05, F-08. Gates re-run green (pytest 1,673/3/0; AUDIT CLEAN; ruff; goldens;
40/40 selftests); artifacts rebuilt (Setup `0D0BF7C5…`, zip `113be091…`, SBOM `8e2fa4b0…`, dist exe
`8ae3b250…`) and the packaging battery re-run (smoke 18/18; journey 17/17). Execution receipts:
the §127 record in `SESSION_HANDOFF.md` and `Desktop\OFAP_v0.1b_release_assurance_audit\evidence\x127_*.txt`.
The push pass remains the owner's.

**Baseline at pass start.** HEAD `797eea0`, worktree dirty with **58 files** (34 tracked edits +
24 untracked additions — the §119–§125 waves incl. `tips.js`, `heatview.js`, `navreturn.js`,
`presets.js` and the audit docs). All four gates, both goldens, the dependency audit and the frozen
packaging battery were re-run on this exact tree — see §12. The packaged artifacts in `dist/` were
rebuilt earlier today over this tree (§125: Setup `5B8BF8B4…`, zip `917a48b2…`, SBOM `eb51942b…`,
dist exe `b2eb32d8…`) and the probes below ran against that frozen build.

---

## 1. Executive release decision

**SHIP ONLY AFTER REQUIRED FIXES.**

- **No Critical or High security vulnerability was found on this tree.** The guard family, the CSP
  confinement, the secrets posture, the dependency set and the CI controls all re-verified live and
  by scan (receipts throughout). Resource ownership is proven for every long-lived structure
  inspected, and the view-churn probe shows zero accumulation on the current tree (§7).
- **Two new defects were found and confirmed live; both are small, both sit in one handler family,
  and both should be fixed before the public release** (then re-verified and the artifacts rebuilt —
  the F-01 lesson: a source change = a rebuild, or the artifact lies):
  - **RA-01 (Medium)** — the Engine view's readout interpolates the instrument symbol into
    `innerHTML` unescaped, and instrument symbols are stored without a character-set clamp; a
    crafted symbol reaching the app (e.g. through an imported workspace artifact) produced a **real
    `<img>` element** in the DOM (live-proven). Script *execution* through this exact field is
    blocked today by the store's `.upper()` (JS is case-sensitive) and by CSP — so the practical
    impact is element injection, not code execution — but the escaping bug is real and one line to
    fix.
  - **RA-02 (Low)** — `/api/control/data/export`: a fresh profile (no database yet) answers
    **500** with a traceback, and a symbol containing `/` (`BTC/USDT`) builds a bogus filename path
    and answers **500**; the house filename-sanitiser used elsewhere (paper export, `/export/save`)
    is missing here. No path escape is reachable (the intermediate directory can never be created —
    proven by the error itself), so this is a reliability/hygiene defect.
- **One Low code-hardening item (RA-03):** `engine.bybit_validate` interpolates the config symbol
  into the Bybit URL unquoted (the SS-12 class; host is fixed, impact limited to a malformed query).
- **Carried, non-blocking (unchanged dispositions):** the F-05 log-noise quirk and the F-08
  lint-noise items remain queued for the next source-changing pass (they travel with the RA fixes);
  the `docs/` publication-surface judgement call stays the owner's (F-07 — now with zero real
  `C:\Users\…` paths in tracked docs, measured this pass).
- **All four final-decision inputs are otherwise met:** credentials clean (§10), ownership proven
  (§7), hot paths bounded and stable (§9), market-data validity fails safe and visibly (§8), build,
  test and release procedures reproducible (§12), public-release hygiene present (§10).

**Required before publishing:** land RA-01 + RA-02 (+ RA-03, same pass), re-run the gate stack, the
packaging battery and the reload probes, rebuild `dist`/zip/SBOM/Setup, then the owner's standing
push pass. That is one small, well-scoped change-set — it does not reopen the architecture.

---

## 2. Executive risk summary

| Priority | Finding | Confidence | Impact | Release requirement |
|---|---|---|---|---|
| Medium | **RA-01** Unescaped symbol → innerHTML in the Engine readout; symbols stored without a charset clamp (HTML element injection proven live) | Confirmed (live) | Scripting primitive inside the privileged origin — constrained by `.upper()` + CSP today; defacement/robustness regardless | **Yes — fix before publishing** (escape at sink + charset clamp; 1-line + 1-line) |
| Low | **RA-02** `/api/control/data/export`: 500 on a fresh profile (no DB) and on a `/`-bearing symbol; filename tag unsanitised | Confirmed (live) | A user hitting Export before the first engine start, or typing `BTC/USDT`, gets a traceback instead of data or a sentence | **Yes — small fix** (sanitise tag like paper export; create-or-answer; 400 not 500) |
| Low | **RA-03** `bybit_validate()` interpolates the symbol into the venue URL unquoted (SS-12 lineage) | Confirmed (code) | Malformed query for hostile symbol strings; host fixed → no SSRF | Recommended in the same pass (`quote()`) |
| Informational | **RA-04** bandit: 1 High (B324 sha1, mutex key) + 29 Medium (20× B310 fixed/loopback URLs, 7× B608 fixed identifiers, 1× B314 DTD-mitigated, 1× B104 test-only) — all disposed, none new-class | Confirmed | External reports will keep flagging them | No — dispositions recorded; the one-argument `usedforsecurity=False` rides the next source pass |
| Informational | **RA-05** `docs/` carries internal working notes (programme logs, audit trails) | Confirmed | Publication-surface judgement, no credentials, no personal paths (measured) | No — owner decision (F-07 carry) |
| Informational | **F-05 carry** `ConnectionResetError` tracebacks from aborted sockets can still reach the log (no filter applied yet — re-checked) | Confirmed | Cosmetic log noise | No |
| Informational | **F-08 carry** lint-noise dispositions unchanged (SHA1 mutex, fixed-identifier SQL, fixed-URL urlopen) | Confirmed | None; house triage lives in §6 | No |

No Critical findings. No unpatched High. Everything else from the two prior ledgers is closed or
re-verified (status table in §6).

---

## 3. Verified architecture, data-flow, trust-boundary and ownership map

**Entry points.** `orderflow_system.desktop.__main__` → `launcher.main`: resolves window geometry,
takes a single-instance mutex, starts the FastAPI app in a daemon thread bound to **127.0.0.1** on a
free port (`launcher.free_port`, exclusive-bind probe), waits for `/healthz`, opens the
pywebview/WebView2 window on `http://127.0.0.1:<port>/desktop` (browser fallback if pywebview is
missing). `python -m orderflow_system.dashboard` is the standalone demo entry (same server family,
port-robust, loopback). A second process is refused by the mutex; the aux-window host is the only
window creator besides `main()`.

**Frontend/backend boundary.** The page is served by the same loopback origin it calls: `desktop/ui`
is mounted at `/desktop/`, the legacy widget modules at `/static/`; REST + one `/ws` WebSocket carry
data with `Cache-Control: no-store` and a meta CSP (`script-src 'self' <hash> 'unsafe-eval'`;
`connect-src 'self' ws://127.0.0.1:*`; `object-src/frame-src/base-uri 'none'`). The pywebview shell
exposes **no** `js_api` bridge (verified in the beta audit, unchanged); WebView2 default sandbox.

**UI lifecycle topologies.** 34 view sections exist (31 static rail + `guide`/`scanner`/`help`
runtime-injected; re-counted this pass — `class="view"` union of rail items). One overlay family
(wizard `.wiz-overlay`) with a single top-most keyboard handler; hints/help/lookup/navreturn are the
other page-lifetime layers. Modules self-init on first activation (`MutationObserver` on their
section); every poller guards on visibility (`document.hidden`, `.active`/frame display, per-view
pause lease via `intent.js`).

**Data flow (text diagram).**

```
venue WS/REST ──► data/*_feed.py (finite gates: isfinite, sizes) ──► atlas/* engines
      │                     (bounded deques 30 sites; caps, ring buffers)
      │                                    │
      └── envelope parse ──► data/database.py (aiosqlite, WAL)      ▼
                                    │                        atlas/hub.py (per-symbol state)
                                    ▼                                    │
desktop/api.py (control)  ◄────────────────────────  atlas/api.py (heat/cvd/tape/frames/trackers)
      │                                                                  │
      └──────────────► FastAPI app (LocalRequestGuard at import) ──► /ws broker (bounded queues 256)
                                     │                                        │
                          UI modules (fetch/api + bus dedupe) ◄──────────────┘
                                     │
      canvas/WebGL-free renderers (ofx.js, heatmap-pro, atlas...) ──► DOM readouts/overlays
```

**Trust boundaries (status after this pass).**

| # | Boundary / abuse case | Status |
|---|---|---|
| 1 | Website → loopback API via DNS rebinding (read config incl. keys) | **closed** (SS-1; re-verified live: hostile Host 403) |
| 2 | Website → body-less/REST mutating POSTs | **closed** (SS-2; re-verified live: cross-origin 403, cross-site 403; loopback 200) |
| 3 | Website → `ws://127.0.0.1/ws` | **closed** (SS-3; re-verified live: native 101, cross-origin 403) |
| 4 | `news_url` GET parameter → SSRF/scheme abuse/unbounded read | **closed** (SS-4; DTD refusal + caps re-read) |
| 5 | Venue frame with NaN/Inf/negative | **closed** (SS-5; suites green) |
| 6 | Legacy pipeline binding 0.0.0.0 | **closed** (SS-6; `dashboard.host` pinned 127.0.0.1 in the store; help check calls the warning when 0.0.0.0 appears) |
| 7 | Crafted **workspace/studies artifact** import | validated + sanitised; **code modules require explicit consent** (SEC-02); one gap found — symbol charset (RA-01) |
| 8 | Crafted **CSV import** (`/data/import`) | text-in-body (no path), 40 MB cap, parse off-loop, bad rows counted as 400 — re-verified by read |
| 9 | Export writes (`/export/save`, paper export, journal statement, data/export) | leaf-sanitised everywhere **except** data/export's symbol tag (RA-02) |
| 10 | Update download (`/update/download`) | http(s)-only (SEC-10), byte cap (SEC-11), sha256 verify when supplied, leaf name — re-verified by read |
| 11 | Pasted study module (`new Function`) | accepted, documented (SECURITY.md) |
| 12 | Local same-user process → API | accepted by the documented threat model (same file access already) |
| 13 | Supply chain (CI, deps, artifact) | pinned + scanned (§10) |

**Resource owners.** One ownership table in §7, covering: WS queues/writers, feed sessions and
snapshot tasks, engine/replay/history tasks, aiosqlite, log ring, 30 bounded deque sites, UI
intervals/observers/listeners, canvases, blob/object URLs (none created outside help screenshots),
and the aux-window records.

---

## 4. Audit coverage matrix

| Subsystem / directory | Status | Risks checked | Remaining unknowns |
|---|---|---|---|
| `orderflow_system/atlas/` (engines, hub, api) | Inspected | boundedness sweep, NaN gates, `until=` clamps, webhook URL policy, replay load ports | long-session soak beyond §7's window |
| `orderflow_system/data/` (feeds, database, backfill) | Inspected | finite gates, sequence handling (carried suites), retention prune allowlists, WAL health | vendor-side silent wrongness (not locally detectable) |
| `orderflow_system/desktop/` (api, engine, launcher, updater, storage, dataport, journal, profiles) | Inspected | guard family live, file-writing routes, import paths, update policy, backup target validation, export filenames | — |
| `orderflow_system/dashboard/` (legacy page + widgets + app) | Partially Inspected | guard middleware home, no-store, widget asset parity (frozen smoke) | legacy page interaction depth (carried; unchanged) |
| `orderflow_system/desktop/ui/` (34 views, 123 parsed modules) | Inspected + live-driven | XSS sinks per external-data module, CSP ≤ 0 violations over 33 views, escaping audit, listener ledger | exotic pointer/hover corners under real hardware |
| `orderflow_system/` tests (margin: 1,668 collected) | Executed | full suite + security subset (83) + goldens | — |
| `scripts/` (build, release, probes, gates) | Inspected | frozen build contents, asset roots, prune honesty | — |
| `installer/` + `dist/` artifacts | Executed | §125 battery rerun (smoke 18/18, journey 17/17), zip integrity 896 entries, payload scans | WebView2 missing-runtime branch on a clean image (no clean image here) |
| `.github/workflows/` | Inspected | SHA pins, permissions, persist-credentials, lockfile install, pip-audit/SBOM/churn jobs | GitHub-side settings (outside the tree) |
| `docs/` (publication surface) | Inspected | secrets/PII scans, internal-notes judgement, screenshot PII sample incl. the newest shots | exhaustive OCR of all images (sweep sampled 17/50; this pass re-sampled the newest) |
| `orderflow_system/fixtures/` (194 KB) | Sampled | fake-credential fixtures are deliberate and keyword-searchable; no personal data | — |
| Vendored third-party files | Excluded | licence headers intact; not edited by policy | — |
| WebView2 runtime on other machines / multi-monitor | Not Verifiable | — | hardware outside this host |

---

## 5. Threat model and protected assets

**Assets.** (a) Market-data credentials (Alpaca key/secret, Telegram bot token, DTC/email
credentials) in the per-user config; (b) analytic integrity — every footprint/delta/CVD/POC/heatmap
output that informs decisions; (c) availability during busy markets; (d) the user's machine as an
origin for outbound requests; (e) release integrity (repo, CI, artifacts).

**Actors.** (1) An unauthenticated internet/website — can *send* requests and open sockets to
127.0.0.1 but cannot read cross-origin replies; the guard closes the reach entirely (verified
live). (2) A malicious/broken venue payload. (3) A crafted imported file (workspace, studies, CSV,
replay data) — the artifact path now validated, code behind explicit consent. (4) A local
unprivileged process — accepted (same-user ⇒ same file access; stated in SECURITY.md). (5) Supply
chain.

**Special scenarios walked this pass.** Fresh-profile first run (produced RA-02); a hostile symbol
through the app's own controls (produced RA-01's element injection); 33-view churn with the CSP
collector armed (0 violations, 0 errors); the frozen build's guard boundary under curl (15/17 with
both failures = RA-02); dependency set + CI secrets usage re-read; whole-history secret pickaxe.

---

## 6. Detailed findings

### RA-01 [Medium] Instrument symbols reach `innerHTML` unescaped (Engine readout) — and the store accepts any string as a symbol

- **Classification:** Security — stored input → HTML injection (escape-at-sink missing; upstream
  charset clamp missing).
- **Confidence:** **Confirmed** (live DOM proof on the frozen exe), with the executable-JS
  escalation on this field **not achieved** (blocked by `.upper()` + CSP; stated plainly).
- **Release blocker:** Yes (small fix; see ship decision).
- **Affected files, symbols, lines:** `orderflow_system/desktop/ui/ofx-view.js` — `paintReadout()`
  at `:597` and `:614` (`box.innerHTML = \`<div class="ofx-ro-title">${sym} · …\``); symbol path
  `ui.js refreshInstruments` → `ofap:symbol` → `ofx-view.js:1278-1281 pickSymbol()` →
  `OFX.state.symbol`; store: `orderflow_system/desktop/config_store.py:1466`
  (`inst["symbol"] = str(...).upper()` — no charset restriction, unlike the alpaca lane at `:1690`).
- **Trust boundary or resource involved:** imported-artifact/config → page DOM (the app's own
  privileged origin, where `GET /api/control/config` answers with stored credentials).
- **Preconditions:** a crafted symbol string in the config — reachable through the artifact import
  (`/config/import`, workspace kind; importing data does *not* require the code-consent flag) or a
  hand-edited config; then the user selects it and opens the Engine view with a hover repaint.
- **Failure or attack sequence:** import a crafted workspace → symbol stored verbatim (uppercased)
  → topbar select change → `pickSymbol` → next poll `load()` → `OFX.state.symbol` = crafted →
  readout repaint → `${sym}` parsed as HTML.
- **Evidence:** live on the frozen build (scratch profile): store accepted
  `<IMG SRC=X ONERROR=window.__ra_xss=1>`; after the app's own control path, the DOM contained
  `<div class="ofx-ro-title"><img src="X" onerror="WINDOW.__RA_XSS=1"> · 15:36:40</div>`
  (`imgs: 1`). Full receipt: `evidence/xss_inject_cfg.txt`, `evidence/xss_receipt.txt`.
- **Root cause:** the readout builds HTML with template interpolation and never escapes; the store
  never constrains the character set of a symbol.
- **Security impact:** element/HTML injection in the privileged origin. Today: no script execution
  via this field (the uppercase transform breaks case-sensitive JS identifiers; CSP blocks external
  fetch/img/iframe/form exfiltration). Residual: visual defacement, layout abuse, and a latent
  escalation the day a lower-cased or differently-validated field reaches the same sink.
- **Privacy impact:** none by itself.
- **Data-integrity impact:** none (rendering only).
- **Reliability/performance impact:** none.
- **User/reputational impact:** a public report of “unescaped innerHTML from imported data” reads
  badly for a security-conscious release.
- **Minimal safe remediation:** (1) escape at the sink — use the module's `esc()` for `sym` at
  `ofx-view.js:597/614` (and audit the two other `${sym}` string builders at `:895/:973`, which
  feed CSV/alert-name text); (2) clamp symbols at the store to
  `[A-Za-z0-9._-]{1,24}` in the instruments block (the alpaca lane's existing rule), watchlist, and
  profile blocks. No behaviour change for any real instrument (all ≤24 chars, charset-safe).
- **Compatibility/regression risks:** a clamp could reject exotic but legitimate broker names —
  `ninjatrader_symbol` already has its own 48-char, case-preserving field and is exempt; MT5/Alpaca
  remaps live in their own keys.
- **Required test/acceptance:** a pin asserting no `innerHTML` in `ofx-view.js` interpolates `sym`
  without `esc(`; a store pin round-tripping a hostile symbol to a clamped value; live reload probe:
  crafted symbol renders as text.
- **Rollback:** revert two files (+ pins); zero data migration.
- **Order/dependencies:** do together with RA-02 (one source pass + rebuild).
- **Ship decision for this finding:** fix before the public release; after the fix the finding
  closes to Informational (defence-in-depth maintained).

### RA-02 [Low] `/api/control/data/export` answers 500 on a fresh profile and on a `/`-bearing symbol; filename tag unsanitised

- **Classification:** Reliability — unhandled exceptions on a user-reachable route; filename
  hygiene.
- **Confidence:** **Confirmed** (live on the frozen exe; both variants).
- **Release blocker:** Yes-by-fix (small): the failure is user-visible on first run.
- **Affected files:** `orderflow_system/desktop/api.py:3115-3143` (`data_export`),
  `orderflow_system/desktop/dataport.py:312-368` (`export_rows` — no try, no tag sanitisation).
- **Trust boundary:** local user → exports folder. **Preconditions:** (a) DB not yet created
  (fresh install, engine never started); (b) a symbol containing `/` or similar path characters.
- **Failure sequence:** POST `/api/control/data/export` → (a) `sqlite3.OperationalError: unable to
  open database file` → 500; (b) `FileNotFoundError: …exports\ticks-BTC\USDT-…csv` → 500.
- **Evidence:** log tracebacks + status codes in `evidence/guard_probe.txt` and the scratch
  `orderflow.log`; benign runs returned 200 with sane files (`ticks-BTCUSDT-…csv`, `ticks-ALL-…csv`).
- **Root cause:** the route wraps nothing; `export_rows` composes `f"ticks-{symbol.upper()}-…csv"`
  without the house leaf-sanitiser; a read-only connect to a missing DB raises instead of answering
  “nothing recorded yet”.
- **Security impact:** none proven — the write cannot escape the exports folder because the bogus
  intermediate directory is never created (the FileNotFoundError *is* the proof); do not overstate
  this as traversal.
- **Privacy / data-integrity / perf impact:** none.
- **User/reputational impact:** first-run Export shows nothing (traceback in the log); `BTC/USDT`,
  a very common spelling, 500s.
- **Minimal safe remediation:** sanitise the tag with the paper-export rule
  (`"".join(ch for ch in symbol if ch.isalnum() or ch in "._-")[:24] or "all"`); catch
  `sqlite3.OperationalError`/`OSError` → 400 with a sentence (“no tick history recorded yet —
  start the engine or import a CSV first”); optionally `mkdir(parents=True)` on the final parent.
- **Compatibility/regression risks:** none — the happy paths keep their exact filenames.
- **Required test/acceptance:** route tests for both failure modes (fresh profile, slash symbol) and
  the two happy paths; live re-probe equals the §12 rows.
- **Rollback:** revert the handler; scratch files only.
- **Order/dependencies:** same pass as RA-01.
- **Ship decision:** fix before publishing.

### RA-03 [Low] `bybit_validate()` interpolates the symbol into the venue URL unquoted

- **Classification:** Market-data integrity / input handling (SS-12 lineage).
- **Confidence:** Confirmed (code read: `engine.py:570-588`, `f"?category=linear&symbol={sym}"`).
- **Release blocker:** No (fix recommended in the same pass).
- **Preconditions:** a symbol string containing `&`, `#` or spaces reaches the capabilities
  refresh.
- **Impact:** malformed queries against a fixed host — no SSRF, no redirect; worst case a wrong
  "listed?" answer for a hostile string. Evidence: code; SS-12 fixed the sibling sites in
  `atlas/context.py` and `desktop/deribit.py` with `quote()`, this one remained.
- **Remediation:** `urllib.parse.quote(sym, safe="")`; one line.
- **Ship decision:** include in the same pass; not release-blocking alone.

### RA-04 [Informational] Static-analysis dispositions (bandit), refreshed

1 High B324 — `single_instance.py:43` uses `hashlib.sha1` for a **mutex digest**, not security;
the one-argument `usedforsecurity=False` is still queued (F-08 carry). 29 Medium: **20 B310**
`urlopen` sites — every one is a fixed https constant (venues, GitHub, EDGAR, calendar) or loopback
(launcher healthz); the two user-configurable ones (ntfy/webhook, DTC) are the documented features.
**7 B608** — fixed table/column identifiers only (`database.py:310-318,414-418` hard-coded tuples;
`api.py:2951` a PRAGMA-gated literal; `dataport.py` `?`-placeholders with literal columns;
`storage.py` fixed names). **1 B314** — `ElementTree.fromstring` in `atlas/context.py`, mitigated by
the internal-DTD refusal (`:118-120`, re-read). **1 B104** — `test_help.py:381` asserts the help
check warns on a `0.0.0.0` config; test-only. No new classes; count growth vs the beta audit is
more `urlopen` call sites, all fixed-URL.

### RA-05 [Informational] `docs/` publication-surface review (F-07 carry)

Internal working notes (programme logs, audit trails, reconciliation ledgers) will publish with the
repo. Measured this pass: **zero real `C:\Users\…` paths in tracked docs** (they use
`C:\Users\<you>`), no credentials, no personal data outside the owner's own public handle. Still a
judgement call for the release-notes pass; no code impact.

### Prior findings ledger (status re-checked on this tree)

| ID | Title | Status now |
|---|---|---|
| SS-1/2/3 | Loopback guard family (DNS rebind / CSRF / WS origin) | **Closed — re-verified live** (403/403/403; WS 101/403) |
| SS-4 | Feed-URL scheme/size/redirect confinement | Closed — code re-read (`context._fetch_text` caps + http(s) only) |
| SS-5 | NaN/Inf/negative gates at ingest | Closed — suites green (`test_feed_value_guards` etc.) |
| SS-6 | Legacy bind default | Closed — `dashboard.host` pinned loopback in the store |
| SS-7 | CI action pins + permissions | Closed — every `uses:` SHA-pinned; `permissions: contents: read`; `persist-credentials: false` |
| SS-8 | Lockfile / SBOM / dependency scan | **Closed** — `uv lock --check` green; CI runs `uv export --frozen` + pip-audit + CycloneDX upload; SBOM ships in `dist/` (45 components, reproduced this pass) |
| SS-9 | Username in a screenshot | Closed (the sweep's fix stands; newest shots re-sampled clean, §10) |
| SS-10 | Client-error log forging | Closed — CR/LF folded in every field (`api.py:3248-3256`, re-read) |
| SS-11 | No CSP | Closed — strict meta CSP incl. hash + `object-src 'none'`; live sweep 0 violations |
| SS-12 | Symbol into venue URL unquoted | Closed for the swept sites; **one site remained → RA-03** |
| SS-13 | XML entity class | Closed — DTD-subset refusal re-read |
| SS-14 | SECURITY.md / disclosure | Present (`SECURITY.md`, 4.1 KB, re-read: loopback-only + no-orders scope promises still accurate) |
| F-01 | Frozen build missing `dashboard/static` | Closed; frozen smoke re-verifies asset parity (78 refs byte-identical, today) |
| F-02 | Silent widget degradation | Mitigated (build refusal + startup warning + pin; UI notice still deferred) |
| F-03 | Comment drift | Closed |
| F-04 | `/docs` on loopback | **Re-verified 404 on the frozen build** (docs/redoc/openapi) |
| F-05 | `ConnectionResetError` log noise | **Open (cosmetic)** — no filter applied yet; re-checked |
| F-06 | Platforms listeners per activation | Carried (verified not a leak; ledger-frozen) |
| F-07 | Docs publication surface | Open — owner decision (see RA-05) |
| F-08 | bandit dispositions | Open/carried (see RA-04) |

---

## 7. Zero-leak / resource-lifetime report

**Ownership table** (code read + the probes below; receipts under
`Desktop\OFAP_v0.1b_release_assurance_audit\evidence\`).

| Resource | Creation site | Owner | Expected release trigger | Actual release path | Failure/cancel cleanup | Bounded? | Evidence |
|---|---|---|---|---|---|---|---|
| WS client queue | `websocket_manager._Client` | per client | disconnect | writer `finally: _forget` | drop-on-full, per-channel trim | Yes — 256 + drop counters | pins (`test_websocket_backpressure.py`) |
| WS writer task | `connect()` | per client | `disconnect()` | cancels + awaits | 5 s `asyncio.timeout` per write (not `wait_for`) | Yes | pin incl. cancelled-writer case |
| Feed session + heartbeat | `FeedSession.run()` | feed | `stop()` | `finally` closes conn, cancels heartbeat, fires hook | yes | Yes | `test_feed_session.py` |
| Snapshot tasks | venue feeds | per symbol | completion | dedup when done | cooldown | Yes | tests |
| Backfill producer/queue | `backfill` | job | consumer `finally` | drains + awaits producer | single-job guard | Yes (`maxsize=4`, ≤7 days) | tests + §77 |
| Engine / replay / history tasks | `desktop/engine.py`, `atlas/replay.py`, `atlas/history.py` | app | `stop()` | cancel + await (15 s timeout → cancel) | yes | Yes | code + pins |
| aiosqlite connection | `Database.connect()` | app | `close()` | `finally` | WAL, busy_timeout, prune + WAL checkpointing | Yes | code + `test_retention.py` |
| Log ring + file handler | `desktop/logs.py` | app | rotation | `RotatingFileHandler` + `deque(maxlen=MAX_LINES)` | — | Yes | code |
| Engine/intent/tape/etc. deques | 30 non-test `maxlen=` sites | engines | eviction | `maxlen` | — | **30/30 bounded** (re-counted this pass; spot-checked the new ones: `_events` 400, paper ledger cap 300, tips MAX_SHOWN 3) | scan + code |
| UI intervals | page/view boot | module | pause/teardown registry | `OFAPPause` + visibility guards | — | Yes — churn-flat | churn probe (below) |
| UI observers / listeners | view boot | module | page lifetime | ledger-frozen per module | — | Yes — 0 same-node accumulation | churn probe |
| Canvas contexts | views | page | — | n/a | — | Yes (fixed set; count steady) | churn probe + §72 pins |
| Aux-window records | `desktop/windows.py` | launcher | window close / quit sweep | `drop_record` (keep-on-quit flag) | yes | Yes | `test_aux_windows.py` |

**View-churn probe (today, frozen exe, live Bybit feed, 5 cycles × 28 views, `scripts/churn_probe.py`):**
timers alive `d1 14 → d2 14` (**flat**); **same-node accumulation: none** (section B empty);
**detached-but-retained: 0** (section C empty; `alive_detached_d2 = 0`); 529 nodes tracked at d2,
231 alive+connected, 298 collected. One transient timer observed mid-run
(`OrderbookLadder._scheduleRender`, 100 ms, a one-shot render) — not retained. Receipt:
`evidence/churn_probe_receipt.json`, `evidence/churn_probe.txt`.

**CSP/page-error sweep (today, frozen exe, 33 views driven):** 0 `securitypolicyviolation`,
0 `window.onerror`, 0 unhandled rejections; live pill “data: live”.

**Soak (13-minute live-feed run on the dev tree, `scripts/soak.py --minutes 13 --interval 30`,
engine streaming from minute ~1):** harness verdict **pass** — post-warm-up slope **+0.009 MB/min**
against the +0.500 gate over 9.8 min, 20 post-warm-up samples (26 total), WAL grew to 4.19 MB then
held flat. **Harness caveat, measured this pass:** its RSS column reads the launcher **shim**
(5.27→5.36 MB), so the serving **child** was sampled separately at 30 s cadence
(`evidence/soak_child_rss_samples.csv`): working set **97.1 → 144.4 MB over 9.0 min ≈ +5.3 MB/min**,
private 431→478 MB. That climb is the **documented early bounded-store fill** (the memory audit
traced `depthmap.py` columns as the dominant site; every store is capped — 30/30 deques, heat
columns ≤900, event/tape/trade rings in the hundreds), and the longer-window flatness evidence
(idle 4.5 min flat; 272 view switches = heap/listeners/timers constant; JS-side churn flat again
today) stands beside it. **Stated honestly: this pass did not run to the RSS plateau** — the
13-minute window shows the expected warm-up slope, not a flat tail, and the bound is evidenced by
the caps + the memory audit rather than by a fresh multi-hour run.

**Verdict:** no unbounded growth found on any inspected structure; the only new defects the live
passes surfaced are RA-01/RA-02, both handled above.

---

## 8. Market-data integrity assessment

- **Ingest gates:** every venue value passes `math.isfinite` before any aggregate
  (`bybit_feed._finite`, `alpaca_normalize._num`, binance/okx/hyperliquid equivalents); junk is
  counted in `book_health()["junk_values"]`, never propagated (SS-5, suites green today).
- **Unknown symbols serve nothing:** the demo fillers return `[]`/mode-tagged empties for
  unmodelled symbols (`test_demo_symbol_guards.py`; live `[]` re-observed in the §125 journey and
  the guard probe).
- **Ordering/reconnects:** snapshot/diff chains with straddle gates and resync; bounded backoff
  1→30 s; the 106-fault-case feed suite is green on this tree.
- **Tick discipline:** absorption keyed on tick-rounded prices; displacement = true tick steps
  (pins green); `atlas/clock.py` remains the single timestamp normaliser.
- **Freshness/labelling:** chips (`live/warming/stale/demo/held`) + the data pill's provenance
  tooltip (new §125: last-tick age + gap count over the retained window — “gaps ≥ 5.0 s in the last
  133 ticks: 0 (worst 4.2 s)” observed live); “degrade out loud” holds.
- **New this era, verified:** the heat-scale leash (`test_heatmap_scale.py`) — the ceiling can no
  longer re-grade under the user (drift ×1.84 pre-fix → ×1.18 post-fix, §122 receipts); the
  range-to-table events list filters strictly on the boxed time/price band (live: “0 of 120 …
  the record holds walls, grows, pulls and spikes” — honest empty, no invented rows).
- **Execution-capable code: none.** Re-grepped for order-placement verbs: the only `/v2/orders`
  call is Alpaca's **read-only order history** (`desktop/alpaca.py:137`, status/limit/direction
  GET); the paper desk is simulated end-to-end and its refusals are spoken (e.g. “a sell limit at
  1 would fill the moment it is placed — at a price the tape never traded”, §125-era pin).
- **Could still mislead (disclosed):** vendor-side silent wrongness (cross-venue switching is the
  answer), demo-mode labelling on an engine-less fresh profile, partial-depth inferences labelled
  INFERRED.

---

## 9. Rendering, concurrency, memory, CPU, GPU stability assessment

- **Frame behaviour:** last full measurements stand (§51: max warm frame 12.4 ms at 4K; §58/§59:
  heat pass 0.6–1.7 ms against a 6.94 ms budget at 2560×1440@144 Hz; the beta audit re-measured
  16.7 ms rAF cadence). **Not re-benched this pass** (no rendering-path regression candidate: the
  recent waves touched overlays/READMEs and were re-verified by their own receipts §119–§125);
  stated as not-executed rather than inferred.
- **Concurrency:** one writer per WS client outside every lock; droppable channels trim, signals
  never drop; the 3.11 `wait_for`-swallows-cancel hazard stays pinned away; engine/feed/replay stop
  paths cancel and await (ownership table §7).
- **Memory:** churn-flat JS side (§7); Python side is event-loop tasks with bounded buffers; the
  analytics engines are stdlib-only (no BLAS threads in the frozen package). The §115-era memory
  audit's baselines (idle flat 4.5 min; 272 switches = JSEventListeners constant 918; live ingest
  +1–5 MB/min bounded stores) plus today's 13-min soak cover the requested windows; the long (24 h)
  run stays opt-in per the standing harness notes.
- **GPU:** Canvas 2D only (no WebGL contexts to lose); canvas count steady under churn; DPR/resize
  handled by the §71/§72 law (`backing = round(box × dpr)`; identity pinned).
- **Interactions under load:** intent leases + per-view pause (never mute the user's own command —
  the §121 force-path law) keep gestures off the feed's pollers; the heat governor's frame budget
  (400 ms) reviewed in §118-era probes.
- **Stability under churn:** zero page errors, zero violations across 33 views (§7), zero
  `client error:` lines in the frozen logs during every probe today.

---

## 10. Security, privacy, dependency, CI and public-GitHub release assessment

- **Secrets:** **clean, re-verified four ways today** — (1) secret-shaped regex over the whole
  worktree (tracked + the 24 untracked additions): zero real values (only deliberate fixtures:
  `PKTESTKEY…`, `dtc-secret-value`, `SECRET-CONFIG-TOKEN`, `hunter2-not-echoed`); (2) full-history
  pickaxe (`git log --all -G` for AWS/GitHub/PEM/`sk-` shapes) + “ever-added suspicious filenames”:
  nothing; (3) the **frozen payload** (`dist/…/_internal/orderflow_system`): zero hits; (4)
  `git add -An` dry-run: a push would stage only source/test/doc files (no db/log/dist/config).
  `.gitignore` re-read: `*.db*`, `*.log`, `dist/`, `build/`, `.env*`, `*.pfx/p12/pem/key/snk/cer`,
  `installer/prereq/` all covered.
- **Guard family, live on the frozen build:** hostile `Host` → **403**; cross-origin `Origin`
  POST → **403**; `Sec-Fetch-Site: cross-site` POST → **403**; loopback-origin POST → **200**; WS
  native **101** / cross-origin **403**; `/docs`, `/redoc`, `/openapi.json` → **404** (F-04
  re-verified); served `/desktop` **sha256 == packaged index.html** (77f20a1a…); CSP meta present.
  The guard implementation re-read: port-aware origin check (SEC-24), `is_trusted_ws_handshake`,
  middleware installed at import.
- **CSP confinement, live:** strict policy (script-src self+hash+unsafe-eval for the studies
  engine; connect-src loopback ws only; object/frame/base-uri none) with **0 violations over 33
  driven views** (collector armed before load).
- **Injection surfaces:** parameterised SQL everywhere (the 7 bandit B608 sites re-triaged to
  fixed identifiers, §RA-04); the artifact import validates then applies through the store
  sanitisers with code behind consent (SEC-02); CSV import is text-in-body with a 40 MB cap; the
  news renderer escapes every feed-supplied value incl. links (`nwEsc`); the palette rows escape
  (`escapeHtml`); **the one escaping miss is RA-01**.
- **Desktop runtime:** pywebview without `js_api`; no node/electron surface at all; single-instance
  mutex; `folder/open` whitelisted names only (`config/logs/exports/backups` — never a caller
  path); `platforms/*/open` open the app's own files; `launch` spawns fixed argument lists (no
  shell); `update/open` = folder-or-release-page only.
- **Dependencies/supply chain:** `uv lock --check` green; `pip-audit` over the frozen env (59
  packages) → **no known vulnerabilities**; SBOM reproducible (`uv export --frozen … cyclonedx1.5`,
  **45 components**); zip integrity 896 entries / 0 corrupt; artifact hashes recorded in
  `installer/README.md` (dated journey).
- **CI:** every action SHA-pinned with version comments; top-level `permissions: contents: read`;
  `persist-credentials: false`; installs from `uv.lock`; jobs: test (3.11+3.12) · build · sign
  (gated on SignPath secrets) · soak · churn (frozen-build probe uploading its JSON receipt) ·
  pip-audit + SBOM upload. The only `secrets.*` reference is the SignPath token in the gated sign
  job.
- **Privacy & credentials:** no telemetry anywhere; the control API is **write-only for secrets** —
  live receipt on the frozen build: a seeded `TEST-SECRET-12345` returned as `••••••••` from both
  `GET /config` and `GET /bootstrap`, and re-posting the mask left the stored secret unchanged
  (the mask protocol supersedes the sweep-era "config GET returns stored secrets" disposition — the
  build hardened since; receipt: `evidence/config_mask_probe.txt`); screenshots: the sweep sampled
  17/50; this pass re-sampled the **newest** shots (logs.png, settings.png) — no usernames/paths/
  emails; the only credential-looking text is the Telegram **placeholder** `12345:ABC-DEF…`.
- **Public-release hygiene:** LICENSE (MIT + upstream notice), SECURITY.md (private reporting +
  scope promises verified accurate), THIRD_PARTY_NOTICES (also shipped in `dist/`), CONTRIBUTING,
  release checklist + evidence docs current for the §125 artifacts.

---

## 11. Dependency-safe remediation roadmap

**Stage 1 — required fixes (one small source pass, then rebuild + re-receipt).**
Addresses RA-01, RA-02, RA-03. Modules: `orderflow_system/desktop/ui/ofx-view.js` (escape `sym`),
`orderflow_system/desktop/config_store.py` (symbol charset clamp), `orderflow_system/desktop/api.py`
+ `desktop/dataport.py` (export sanitise + 400s), `orderflow_system/desktop/engine.py`
(`quote()` in `bybit_validate`), plus pins (`test_*.py` route/store/escape pins).
Why safe here: behaviour-preserving for every real instrument/filename (charsets and filename sets
verified in this pass); no schema or API-shape change. Compatibility: none for publishers/UI.
Tests required before merge: new pins above + the full stack (pytest, audit, ruff, goldens,
selftests) + the packaging battery (smoke + journey) + the live reload probes (crafted symbol
renders as text; both export failure modes answer 400; happy paths 200). Own commit: yes — one
coherent pass, **followed by a rebuild** (F-01 discipline). Rollback: revert the files + rebuild.

**Stage 2 — the queued cosmetics (same pass or next).** F-05 exception filter (logging-only),
F-08 `usedforsecurity=False` + (optional) static SQL for the count helper. Behaviour-identical;
travel with Stage 1 or the next source-changing pass.

**Stage 3 — deferred / owner.** F-02's full “module failed to load” UI notice; F-04's
`/docs`-off in packaged builds; F-07 docs-publication decision; deeper venue fault injection +
long-session profiling carried from earlier notes; WebView2 missing-runtime branch on a clean
image.

---

## 12. Validation matrix

| Validation | Command / scenario | Expected | Actual (2026-09-19) | Status |
|---|---|---|---|---|
| Baseline recorded | `git rev-parse HEAD`, `git status --porcelain` | recorded | `797eea0`, master, 58-file worktree | PASS |
| Full suite | `.venv/Scripts/python.exe -m pytest orderflow_system -q` | green | **1,665 passed / 3 skipped / 0 failed** (1,668 collected, 67 s) | PASS |
| Security-focused subset | `-k "request_guard or security or backpressure or …"` | green | **83 passed / 1 skipped** | PASS |
| UI reference audit | `scripts/audit_ui_refs.py` | AUDIT CLEAN | **AUDIT CLEAN — 123 modules parse** | PASS |
| Lint | `uvx ruff@0.16.7 check orderflow_system scripts` | clean | **All checks passed** | PASS |
| UI selftests | 40 × `node …/*.selftest.js` | 40 ok | **40/40** | PASS |
| Analytics golden | `scripts/regen_analytics_golden.py` | no drift | **40 cases / 2,196 leaves, max diff 0.000e+00** | PASS |
| Config golden | `scripts/regen_config_golden.py` | no drift | **31 factories / 18 crypto majors / 49 instruments** | PASS |
| Secret scan — worktree | regex sweep (keys/tokens/PEM) incl. untracked | none | **0 real hits** (fixtures only) | PASS |
| Secret scan — history | `git log --all -G'…'` + added-filenames filter | none | **nothing ever added** | PASS |
| Secret scan — payload | regex over `dist/…/_internal/orderflow_system` | none | **0 hits** | PASS |
| Push-surface dry-run | `git add -An` | source/docs only | **source/test/doc files only** | PASS |
| Lockfile | `uv lock --check` | consistent | green | PASS |
| Dependency audit | `uv pip freeze` → `uvx pip-audit -r` | none | **No known vulnerabilities found** (59 pkgs) | PASS |
| SBOM reproduction | `uv export --frozen --format cyclonedx1.5 --extra mt5` | parity | **45 components, spec 1.5** | PASS |
| Static analysis | `uvx bandit -r orderflow_system -ll` | reviewed | 1 High / 29 Medium — all dispositions RA-04 | REVIEWED |
| Zip integrity | `zipfile.testzip()` | clean | **896 entries, 0 corrupt** | PASS |
| Frozen smoke | `evidence` battery (§125 rerun) | 18/18 | **18/18** (asset parity 78 refs byte-identical) | PASS |
| Setup journey | silent install → hash → smoke → uninstall | clean | **17/17 ALL PASS** | PASS |
| Guard probe — frozen exe | hostile Host / cross-origin POST / cross-site POST / loopback POST / WS ×2 / docs 404 / served-hash / CSP | 403×3, 200, 101/403, 404×3, equal | **all PASS** (15 checks) | PASS |
| Export failure modes | fresh profile + `BTC/USDT` on `/data/export` | graceful | **500 / 500 — RA-02** | **FAIL→FIX** |
| Export sanitiser | `/export/save` with `../../name` | inside exports | landed as `.._.._ra_evil.csv` inside exports | PASS |
| CSP sweep | collector pre-load, 33 views driven | 0 violations | **0 violations / 0 page errors, engine live** | PASS |
| Churn probe | 5 × 28 views, frozen exe | flat | **timers 14→14; 0 same-node; 0 detached-retained** | PASS |
| Live soak | `scripts/soak.py --minutes 13 --interval 30` (engine streaming) | bounded slope | harness **pass** (+0.009 MB/min vs +0.500 gate; 20 post-warmup samples); child RSS 97→144 MB ≈ +5.3 MB/min = documented early bounded-store fill — see §7 caveat | PASS (with caveat) |
| Screenshot PII | newest shots (logs, settings) read | no PII | clean; placeholder token only | PASS |

Raw receipts: `Desktop\OFAP_v0.1b_release_assurance_audit\` (`evidence\`: guard_probe.txt,
secrets_scan.txt, supply_chain.txt, bandit.json + triage, churn_probe*, soak_125*, xss_*; scratch
profiles under `%TEMP%\ofap_ra_*`).

---

## 13. Final release checklist

- [x] Baseline recorded (HEAD, branch, dirty set) and preserved — no code changed by this pass
- [x] Architecture / data-flow / trust-boundary map re-derived from the tree
- [x] No secrets in tree, history, payload or push surface (four scans)
- [x] Guard family verified live on the frozen build (403/403/403/200, WS 101/403)
- [x] CSP strict; 0 violations across 33 driven views
- [x] Lockfile consistent; pip-audit clean; SBOM reproducible; zip integrity clean
- [x] CI pinned + least-privilege; churn/soak jobs present; single gated secret
- [x] Resource ownership table complete; churn probe flat; soak instrumented
- [x] Market-data integrity suites green; unknown symbols empty; no execution code
- [x] Packaging battery re-run (smoke 18/18; journey 17/17)
- [x] **RA-01 fixed** (escape + charset clamp) with pins — §127: escape at the readout AND at the legend (the live re-probe caught a second sink of the same class, RA-01b); store charset clamp `_clean_symbol`
- [x] **RA-02 fixed** (export sanitise + graceful 400s) with pins — §127: filename tag clamped; fresh-profile export answers 400 + sentence (live receipt)
- [x] RA-03 `quote()` (same pass) and the queued F-05/F-08 cosmetics — §127: quoted Bybit URL (functional pin), abort filter, `usedforsecurity=False`, static count/prune SQL
- [x] Re-run gates + packaging battery + reload probes; **rebuild dist/zip/SBOM/Setup** — §127: pytest 1,673/3/0 · AUDIT CLEAN · ruff · goldens · 40/40 selftests · smoke 18/18 · journey 17/17 · Setup sha256 `0D0BF7C5…` (rebuilt 2026-09-19T17:06)
- [ ] Owner's push pass (drafts first) → tag `v0.1b`

---

## 14. Audit limitations and residual risk statement

**Not claimed:** “zero bugs”, “fully secure”, “production-safe”. What is claimed is enumerated
above, each row tied to a command or probe that ran on this machine today or to a file:line read.

**What could not be verified here:** GitHub-side repository settings (branch protection, secret
scanning alerts) — outside the tree; the WebView2 missing-runtime installer branch (runtime present
on this host); adversarial market conditions beyond the fixture suite; behaviour of the shipped
WebView2 runtime on other machines; physical multi-monitor behaviour (single display); a full 24 h
soak (the standing harness is opt-in; a 13-minute live run is recorded); exhaustive OCR of every
historical screenshot (sample-based, as the sweep defined).

**Residual risk, stated.** (1) Same-user local processes can reach the loopback API — inherent to a
no-login desktop app and documented in SECURITY.md. (2) RA-01: until fixed, HTML element injection
is possible from crafted imported data — no script execution demonstrated on this field (case
folding + CSP), and the fix is small. (3) RA-02: Export on a fresh profile answers 500 until fixed.
(4) The F-02 silent-degradation class remains mitigated-not-eliminated for widget modules. (5) The
docs publication-surface decision (F-07) is the owner's. (6) Vendor-side data wrongness is not
locally detectable.

**Residual risk acceptance:** **acceptable after the Stage-1 fixes** for a scoped v0.1b that is
loopback-only, market-data-only, and places no orders; without the fixes, publish is not
recommended because both defects are user-visible and one is a security-hardening regression
against the project's own standard (every other renderer escapes).

*Audit performed 2026-09-19 against HEAD `797eea0` + the 58-file worktree; artifacts probed are the
`dist/` build of the same date (§125 hashes). Evidence: `Desktop\OFAP_v0.1b_release_assurance_audit\`.
No code was changed in this pass; nothing committed.*
