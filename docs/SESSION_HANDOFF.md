# Session handoff — ModFlow OrderFlow Analysis Suite

**Date:** 2026-09-21 · **Tree:** `C:\Users\<you>\OrderFlow-Analysis-Pro` · **HEAD:** `0eedc0d`
**Committed:** the §119–§149b wave is committed as `0eedc0d` (219 files, +55,210/−1,026 lines vs `797eea0`); working tree clean, 81 commits ahead of `origin/master`, nothing pushed. Everything after this line was written before that commit and is kept as the record.

**Run it:** `orderflow_system.desktop` (the owner's shortcut: `.venv\Scripts\pythonw.exe -m
orderflow_system.desktop`, binds 127.0.0.1:8080). Frozen build: `dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe`
(`scripts/build_exe.py`). Scratch scripts belong in `$LOCALAPPDATA/Temp`, not the repo.

---

## §150 (2026-09-21) — competitive reanalysis v3 (the owner's brief; report only, nothing changed)

Ran the owner's brief (`Desktop\now are you able to reanalyse all t.txt`) against HEAD `0eedc0d`
(clean tree, 81 ahead): re-derived ModFlow from the tree, re-read the six vendors' own pricing and
feature pages the same day, and re-scored the market-norms model against the build that came out of
§147/§148/§149b. Deliverable: **`docs/COMPETITIVE_REANALYSIS_v3_2026-09-21.md`** — §0 maps every
item of the 20 Sep analysis to its current status, §5 re-scores **49 industry norms (36 Met — 4 of
them leaders — 8 Mostly/Partial, 3 deliberate gaps, 2 intentional divergences)**, §7 ranks what
remains. No code, no artifacts, nothing committed.

**Gates re-run on the final bytes.** pytest **2,494 passed / 3 skipped / 0 failed** (90.01 s) ·
**ruff 0.16.7 — all checks passed** · `audit_ui_refs` **CLEAN** (346 ids; 686 html + 380 created;
0 missing; 0 duplicate; 154 modules parse) · `audit_metric_hygiene` **CLEAN** · **57/57 selftests** · live sandbox (scratch APPDATA, ports 8097/8098, stopped after): 13 of 15 probe
paths read 200 (the two 404s were wrong path guesses, both resolved after), **192 API paths** in the live OpenAPI schema, and live reads of the trading status/templates
(refusals verbatim), footprint config (21 controls), depth-history (retention 30 min / 1,800
columns), data-quality, sessions (crypto-247 + 20-root roll table), synthetic, alert-rules, storage
usage and the monitor page — plus a **four-venue funding/OI/basis read for BTCUSDT** (Bybit
0.00772%/8h → 8.45% APR, basis −4.31 bps, OI 56,552 BTC).

**Headline findings.** The §146 gap list is closed or deliberately refused: P0-2/P0-3 and P1-1…P1-3,
P1-5…P1-10, P2-2/P2-3 are shipped and were re-verified in the tree; P0-1 is now a shipped
*structure* (drivers, risk gates bound to the session router, refusal sentences) with routing kept
out by policy; still open: chart tabs/2×2 grid + per-pane linking (P1-4), options×flow confluence
(P2-1), study-pack gallery + scripting (P2-4), layout packs + first-run checklist (P2-5's remainder).
New remainder ranked in §7: chart tabs · footprint-region export · render-side FPS harness · mobile
host policy · study/layout packs · paper-grammar parity (stop-limit/MIT, held modifier + pre-fire
tooltip, drag-amend) · Show-Original-Values diff · continuous-futures splice note · status-bar active
profile. The two gates stand: **live routing and MBO stay out until each can ship whole.**
**Recommendation: ship the analytics layer with the practice loop as shipped; the next wave is the
cheap closes in §7 Priority 1.**

**The final build (record corrected).** The frozen rebuild is **not** owed — it ran at **14:34:39 today**, from the pass's final bytes (last source edit 14:26; the 14:56:53 commit `0eedc0d` captured that same tree; no source file was touched after the build; payload parity spot-checked byte-identical on `ui.js` / `menubar.js` / `tips.js` / `why.js` / `help-data.js`). Artifacts, hashed on read-back 2026-09-21: **Setup `dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` — 38,201,838 B, sha256 `ABD78B3E3E9F283AD60217D678A73012B7379C9EB341B3644ECD5629F6986F52`** (the `.sha256` sidecar matches) · zip `…-win64.zip` — 43,599,366 B, `ec50468f1799ef78d36ab66ae349945f80c2565d1390e66ffa9e59c015dcc156` · SBOM `…win64.sbom.cdx.json` — 448,822 B, `3d13b50ddb25d350cbc5c253a31703c9960450d669a44ef8434d08fdb6906f71` · dist exe — 16,484,958 B, `bfd3d603cf258a30f7fd263786ac63e0c13a79a0b432e4e1ac97ff5a15b1aaf8` (matches `BUILD_INFO.json`). **Install journey re-run this hour on that exact Setup: 11/11 PASS** (receipt: `runtime/ofap_s150/final_build_journey_2026-09-21.log`; the dated journey paragraph is now in `installer/README.md`). Two wrinkles, stated plainly: `BUILD_INFO.json` still stamps `797eea0` / `worktree dirty` (the build predates the commit; a clean re-stamp is the only rebuild-shaped work left, and only matters if the release copy names `0eedc0d`), and the frozen smoke/features batteries were not re-run for this build.

**Owed (owner's word).** Commit/push of this pass's docs, the optional clean re-stamp over `0eedc0d`, and the physical multi-monitor pass. Nothing in this pass changed code; nothing committed — the standing rule.

**§150 supplement (same day) — the signing route, made real.** Asked "how do I sign this package?", the local half was exercised end-to-end on **copies** (the upload artifact untouched — sha256 still `abd78b3e…6f52`). Two defects/limits in `scripts/sign_release.ps1` were found and fixed: (1) the `-Thumbprint` path **always passed `/sm`** (machine store) while the script's own instructions say *user* store — a user-store certificate could never be found; it now detects which store holds the certificate and passes `/sm` only for `Cert:\LocalMachine\My`, with a clear error when it is in neither. (2) Added **`-AllowSelfSigned`**: a self-signed signature can never pass `/pa` on an untrusted machine (that is the root-store gap, not a signing failure), so with the switch the script accepts "signature present, from our own certificate" and says so — without it the file still counts as failed. A self-signed code-signing certificate was created for the beta lane: `CN=ModFlow OrderFlow Analysis Suite (self-signed beta), O=Moddy, C=AU`, thumbprint `B03BB7D895832B73D0717AA62F986BEC01D63407` (CurrentUser\My, 3 years, exportable); its public half was exported to `C:\Users\Moddy\keystores\modflow-selfsigned.cer`. Proof (copies of the Setup and the app exe): `signtool` → *Successfully signed*, Authenticode type, DigiCert timestamp present, signer as above; `sign_release.ps1` exit 0. The routes stay as `docs/RELEASE_CHECKLIST.md` §6 records — **SignPath Foundation** (free; the application and the two repo settings are the only blockers), an **OV certificate** (~AU$300–400/yr), or this self-signed lane for a private beta. Order of operations for a *signed* release: sign the dist exe → re-zip → rebuild the Setup → sign the Setup → re-take every hash (signing changes the bytes; `BUILD_INFO.json`'s `exe_sha256` then describes the pre-sign exe).

**Route 1 (SignPath Foundation) — readiness verified, application pack written.** Chosen route: the free Foundation lane, no purchase. Re-verified against the live public copy today: repo `ModdySwag/ModFlow-OrderFlow-Analysis-Suite` public + MIT (public `master` = `797eea0`, one commit behind local `0eedc0d`), last CI runs green (2026-09-19), the artifact configuration is committed and public (blob `53824a40122b…`), and the `sign` job already carries the exact slugs the organization must use (`ModFlow-OrderFlow-Analysis-Suite` / `release-signing` / `default`). Every input the job passes was checked against the action's own v3 schema (`signpath/github-action-submit-signing-request`) — they match; nothing in the workflow needs changing. The only blockers are outside the repo: the Foundation application (owner's identity and consent) and then repository variable `SIGNPATH_ORGANIZATION_ID` + secret `SIGNPATH_API_TOKEN`. Application pack with paste-ready answers, readiness evidence and the post-approval steps: **`docs/SIGNPATH_APPLICATION.md`**. Once the two values exist, the sign job stops being skipped and signs both binaries on the next `master` push / tag / dispatch, failing the run unless every file verifies `Valid`.

**§150 supplement — the public push and the CI red, root-caused and fixed.** On the owner's word local `master` went public (`797eea0..0eedc0d`, 219 files, +55,210/−1,026; pre-flight: no secret-looking filenames or strings in the delta). CI run `35570525622` came back **red**: `test (3.11)` and `test (3.12)` failed — 4 × `test_the_python_and_javascript_readings_agree` on an em dash plus 1 × `test_extras_start_one_connection_for_many_symbols` (`RuntimeError: Event loop is closed`); `build` and `churn` green, `soak`/`sign` skipped as designed. Two root causes, each reproduced or receipted:

1. **Encoding — a whole class.** The runner uses Python's locale default (cp1252); this machine sets `PYTHONUTF8=1`, which hid it. A process call in text mode with no explicit encoding decodes node's UTF-8 output as cp1252, so the em dashes in the refusal strings became mojibake and the parity tests disagreed with the JS side. Reproduced here with `PYTHONUTF8=0` — the same 4 failures. Fixed: **13 process-text call sites across 8 files** gained `encoding="utf-8"` (`test_footprint_config` 2, `test_dataquality` 2, `test_depth_history` 2, `test_legacy_widgets`, `test_why`, `test_windowing_ui`, `audit_ui_refs`, `build_exe` 3), plus `scripts/soak.py:57` (found by the new pin). Checked and clean: no runtime `open()` in `orderflow_system` lacks an encoding (AST-precise scan, 0 findings).
2. **A cross-loop gather in a test.** `test_atlas_integration.py` ran `start_feeds` and `stop_feeds` through two separate `asyncio.run` calls; `start_feeds` creates the feed tasks with `asyncio.create_task` (`hub.py:625`) and `stop_feeds` gathers them (`hub.py:652`) — on Python 3.11.9 the second loop is already closed and the gather raises. Fixed **test-side** (one loop for both calls, as the app runs the hub) with a new assertion that the tasks actually unwound (`h._feed_tasks == []` — the A-06 guarantee). Production code untouched; the app's shipped bytes are unaffected.
3. **A pin so the class cannot come back**: `orderflow_system/test_encoding_hygiene.py` — scans the suite and the scripts for process calls in text mode and textual `open()` calls without an explicit encoding, and plants the exact shapes it must catch (a pin that cannot fail is decoration).

Verified on the final bytes: full suite **2,496 passed / 3 skipped / 0 failed** both with UTF-8 off (CI-equivalent, 87.5 s) and UTF-8 on (88.0 s); ruff clean. **Nothing committed or pushed** — the fix pass awaits the owner's word; the public HEAD carries the red run until it does.

**Fact-refresh fold-in (same day).** The four delegated vendor digests landed and are folded into §2
of the report, receipts filed at **`docs/ux-study/digests-2026-09-21/`** (bookmap-atas ·
quantower-sierra · ninjatrader-mt5 · adjacent-tier-and-defunct-case). Material changes: **Bookmap is
now majority-owned by Nelogica (Oct 2024)** and its deepest order-flow set (Footprint, DOM Pro,
Execution Pro, Multibrackets) is Global+-only; **ATAS warns the Ultra MBO bundle "may become paid for
all subscription types later this year"**; **Kraken completed the NinjaTrader acquisition 2025-05-01**
— and the previous pass's "TradingView owns Tradovate" line was **wrong** (NinjaTrader bought
Tradovate in 2022; TradingView is a broker *partner*) and is corrected; **Sierra Chart's Base packages
cannot connect to any external service**, and MBO transmits only orders ≥3 lots; the defunct case is
**MarketDelta (Chapter 7, 2018)** whose "Footprint" survives as the trademark every competitor renames
around; the MT5 ">100 novelty tips" claim could not be re-verified and is now marked unverified.
Research scratch files (`batch*.json`) were removed from the repo root at close-out.

## §148 (2026-09-21) — the final audit, closed

Ran the brief in `C:\Users\Moddy\Desktop\final audit prompt.txt` against HEAD `797eea0` (dirty tree,
213 entries): the true baseline re-established (2,389/3/0 → 2,489/3/0 as pins landed), every in-repo
gate re-run, the seven read-only module audits consolidated into `AUDIT_REGISTER.md`, and each
confirmed defect fixed with its missing regression pin, proven to bite. Register: **113 [FIXED] / 0
open** + 1 [VERIFIED] compose check.

**Headline fixes.** The seven P1s (footprint marks layer, ladder route template, risk-gate binding,
retention persistence, entry-time R, DST zones, the two why-card honesty items) · the alert block's
scope gates, quarantine, legal-cap and window-bound defects (AB-01..AB-04) · the T3 journal cluster
(13), the sessions/synthetic tail, both T5 waves (derivatives + data-quality; the id audit 162→344) ·
T6 wave 1 (bar-time reader, depth-history poll + new-level + retention keys, covered-span labels) ·
the switcher waves (steadyGuard's promise contract, the ring owning the settle, the Engine picker's
notifier, `adoptSymbol`/`persistSymbolNow`/`refreshPicker`) · the program-wide control-pair matching
audit (dials adopt the store's answer, chips re-sync, replay verifies its symbol, the source switch
re-seeds Settings) · the close-out (`context_block`'s crash fallback says `evidence block failed:
internal error`, never "").

**Gates (final bytes).** pytest **2,494 passed / 3 skipped / 0 failed** · 57/57 node selftests ·
`audit_ui_refs` CLEAN (346 ids; the live app's own table: 201 paths / 192 `/api` + `/ws`) ·
`audit_metric_hygiene` CLEAN · ruff 0.16.7 clean · pin-proof harness **154 cases, 0 problem(s) — every pin bites**; the §149b fold case makes it **155** — re-run complete: **0 problem(s), every pin bites**.

**Docs re-derived.** README badges (2,494 / ~129k lines / 192 routes), the file-inventory table (296
files / 129,624 lines), the UI paragraph (154 modules, 56 selftests), CONTRIBUTING's baseline + its
57-selftest command (now matching CI), and the upgrade package's per-module tallies.

**§149 supplement (same day).** The storage card gained **Clear app cache** (WebView2 caches freed
live; the locked rest goes at the next start through a boot flag the launcher honours) and **archive
open / delete quarantine** controls — routes `/storage/clear_cache`, `/storage/clear_archive`, plus
`archive` in the folder-open allow-list; the DB size budget was set to 2 GB (his call, wired live).
Gates re-run on the final bytes: **2,493 passed / 3 skipped / 0 failed**, harness **154 cases /
0 problems**; the four new pins live in `test_storage.py`.

**§149b supplement (same day).** The Overview's Systems board gained a **hide/show button**
(`#systemsHide` in the card head; `applySystemsHidden` / `saveSystemsHidden` in `ui.js`, the fold
in `modules.css`, default + sanitize `ui.systems_hidden` in `config_store.py`). The fold is a
config setting, not a browser one — the storage card's cache clear wipes webview2's localStorage,
and a view choice that vanished with the caches would read as a bug. Verified live on the running
app: served == disk on all three files, `ui.systems_hidden` round-trips true → false through
`/api/control/config`, the id audit counts 346 with 0 missing, and the suite is **2,494 / 3 / 0**
with the pin `test_the_systems_board_fold_is_a_ui_setting` (the 155th harness case proves it
bites).

**Receipts.** `runtime/ofap_s148/`: `AUDIT_REGISTER.md` (head carries `§148 — CLOSED`) + the batch
receipts (t6a verification/live, switcher notifier + convergence, program-wide matching) +
`pin_run_s148_close.txt`.

**Owed (owner's word).** The rebuild, the commit/push, and the physical multi-monitor pass. Nothing
committed — the standing rule.

## §147 (2026-09-20) — the upgrade package, applied

The competitive analysis (`docs/COMPETITIVE_ANALYSIS_2026-09.md`) compiled into an upgrade package and
applied to the build (`docs/UPGRADE_PACKAGE_2026-09.md` is the package). **Paid features excluded by
instruction**: nothing added needs a subscription or a paid key.

**What it delivered.** Nine workstreams plus the cross-cutting items: the execution layer
(`desktop/atm.py` templates/brackets/OCO/break-even/trail/time-stop, `desktop/orders.py` with risk
gates and a refusal-only bridge, the paper account extended, the ladder's plan bar) · footprint
configurability (`atlas/footprint_config.py`, 21 controls, an in-panel drawer, annotation marks) ·
depth history (`atlas/depth_history.py` + strip panel) · the alert condition builder and the evidence
snapshot on every channel (`atlas/alerts.py`, `atlas/notify.py`, the builder card) · deep trade
analytics (`desktop/journal.py`, per-setup/session stats, P&L calendar, sentences) · the data-quality
cockpit (`atlas/dataquality.py`) · session templates and the roll calendar (`atlas/sessions.py`) ·
crypto derivatives context (`atlas/derivatives.py`, live public endpoints) · synthetic instruments
(`atlas/synthetic.py`) · the companion monitor page (`ui/monitor.html` + `ui/monitor.js`, five GETs) ·
the explainability registry (`ui/why.js`, 25 reads labelled measured/inferred/computed, wired to 19
readouts) · `docs/PERFORMANCE.md` · seven help topics.

**Gates.** pytest **2,389 passed / 3 skipped / 0 failed** (baseline 1,900) · ruff clean on every
touched file · 13 UI selftests, 455 checks, 0 failed · `audit_ui_refs` **CLEAN** (187 routes, 0 missing
calls/ids, 0 duplicate ids) · `ast.parse` sweep clean · config golden, param registry, wiring, timer
guards and the listener ledger all green · live smoke through the real app on a throwaway config:
36 route objects, ten GETs 200, the refusal sentence on the live route, a template on the paper order
receipt, a live funding read.

**Wiring facts worth keeping.** Seven new routers mount in `launcher.py`; nine config blocks are owned
by their modules (`config_store._feature_defaults` / `_feature_sanitise` — each feature cleans its own
block); the registry states the store's bounds (five were auto-aligned to the modules' real clamps);
`index.html` carries five new views, nine script tags and 19 `data-why` readouts (25 across 11 views as
of §148 — `test_why.py` measures the live page, and the count only grows); the listener ledger
and the audit's module/route lists gained the new files.

**Self-caught in this pass.** `atlas/footprint_config.clean()` does not seed missing keys, so the
footprint block is registered as the module's DEFAULTS in `default_config` (the registry test reads
that path) · a depth-history bound (200 ms) disagreed with its own clamp (1000 ms) — the registry now
states the store's numbers · two help `related` ids pointed at topics that never existed · a shipped
alert-builder assertion raised `ValueError` instead of skipping when there is no `alerts.js` (the `or`
fallback could never run after `index()`); rewritten to check absence first.

**Owed.** The §129c frozen rebuild (dist/zip/SBOM/Setup) — already owed, unchanged by this pass ·
commit/publish on his word · the physical multi-monitor pass. The honest remainder (broker adapters,
MAE/MFE writers, chart tabs, study packs, options×flow confluence, depth-history retention persistence,
a render-side FPS harness, mobile host policy) is listed in `docs/UPGRADE_PACKAGE_2026-09.md` §3.

---

## 1. What this session delivered

### Setup wizard — a guidance system, then a professional path
- Every decision step now carries **what it unlocks · where to go deeper · a real deep link** into
  the panel that answers the next question (`guide.js`; `wizFooter`, `wizGo`).
- **Guards**: a choice that would leave the app empty raises an inline banner with the one-click fix
  (the Instruments step's "no instruments enabled" is the model).
- **Depth step**: Express (12 steps) ↔ Professional (22). `wizList()` is the single source of truth for
  navigation; every `collect()` site is list-correct and bounds-safe; the express path ends with a
  door into the professional leg; resume works.
- Professional leg (10 steps): feed budget · instruments · engine internals (live fields) · analytics
  thresholds · studies runtime · layout & workspaces · hotkeys · bridges (never asks for a secret) ·
  performance & hygiene · **prove it works** (8-point checklist).

### Heatmap and engine
- `heatmap-pro.js`: wheel/shift-wheel zoom driving the map's own window control, drag-select with
  isolate + stats, cursor readout (resting, Δ vs previous bucket, row total, bucket total, executed,
  events), markers with notes, region/marker CSV export, and an instant repaint on `ofap:relayout`
  (the one-second blank after a resize is gone).
- Exports land as real files via `POST /api/control/export/save` → `%APPDATA%\OrderFlowAnalysisPro\exports\`
  (the desktop shell has no download shelf; export has to mean a file).
- Engine: **thermal ramp** (slate → orange → white-hot gold) selectable and remembered; **stacked-zone
  bands** drawn with a leading rail and a label; **cursor link** (`cursor-link.js`) with a DOM trace
  line at the cursor's price and a ladder highlight; **pinch** parity (ctrl+wheel = price-axis zoom,
  page zoom cancelled).

### Alerts
- Rules can be **bound to a price**: `params.at_price` / `at_tol` added to the alert evaluator
  (any rule kind), plus `min_age_s`.
- **Wall-age detection**: `DepthHeatmap` tracks a streak (`_wall_first`) and emits `wall_age` with
  "held N min"; `wall_durations()` lists walls by how long they have held.
- Rule management: the alerts list shows each rule's scope in words and can delete one.

### Interaction vs live feed — the system-wide answer
- `intent.js` (`OFAPINTENT`): a **lease** on a surface from real input (pointer/wheel/key/focus),
  time-boxed and auto-renewed; updates that would move the view, scroll a strip or replace a
  selection are **DEFERRED and applied on release — never dropped**; writes are coalesced per key;
  the freeze is two-level (view held ≠ feed stopped) and the arbiter never touches ingest.
- `strips.js`: scrolling strips **hold the reader's place**. The guard discovers any element in the
  visible view that actually scrolls (not hand-picked selectors), counts arrivals for appending
  lists and **counts top-row changes for capping lists** (the tape), shows `↓ N prints · jump to
  newest`, and returns on click. It can never move a scroll it cannot anchor.
- Surfaces are tagged in markup (`data-surface="…"` on 12+ view sections) so panels don't need to
  know the arbiter exists. Every poller in the program now consults it (ofx, heatmap, slow panels,
  v2, alpaca, scanner, market-pressure, context).
- One **status cluster** top-right: the pause chip and the hold chip sit together and report
  "… · feed live · N strips holding your place".

### Scaling and packaging
- `scale.js` (`OFAPScale`): the one authority on window change — resize/maximise/restore/orientation/
  fullscreen/dpr + ResizeObserver, debounced, zero-size guard for minimised windows, `ui-compact`
  under 760 px height, `ofap:relayout` for consumers.
- Fixed two measured faults: the topbar could not wrap (315 px overflow at 1024 wide) and the status
  bar sat *below* a 100vh shell (invisible at every size). Now: 0 px overflow, status bar visible, at
  2560×1440 / 1920×1080 / 1366×768 / 1280×800 / 1024×640.

### The tape was empty by its own filter (found and fixed)
`dashboard/static/tape.js` (loaded by the shell as `/static/tape.js`): the Min Size input had
`min="1" value="1"` and the handler did `parseInt(value) || 1` — **0 is falsy, so the floor could never
go below 1**, and 40 sampled live BTCUSDT prints were 0.001–0.15: the tape showed nothing while its
footer tallied them. Now `min="0" value="0"`, 0 means every print, and the default shows the real
tape. Verified: rows 2 → 51, body 19 px → 1 239 px in a 513 px box, guarded, chip counted, click
returned to newest.

### The agent brief
`docs/AI_AGENT_BUILD_PROMPT.md` (~370 lines) — written for another agent to continue this build:
inventory of what exists, the eight non-negotiables (error-free means *proven*; fail-loud edits;
the contracts that must not break; secrets; free data only; original work; Hermes stays out; the app
must always run), the Windows/Material design language read from the owner's reference image, the
order-flow interaction canon, workstreams A–I with gates, and the inherited gaps. Workstream I is
already built (see §1) — the brief predates the last two sessions' work in places; reconcile before
following it literally.

---

## 2. Verified vs unverified — do not blur this line

**Verified live**
- Wizard: depth switch 12 ↔ 22, the door into the professional leg, deep links, resume.
- Heatmap pro: zoom (240 → 120 buckets), selection (81 × 102 cells, resting 8 544.51, heaviest
  77 630 @ 16.85), cursor readout with real numbers, region + marker CSV on disk, "saved to …" line.
- Alerts: a level-scoped rule created, persisted (`at_price`/`at_tol` read back) and deleted.
- Arbiter: lease from a real gesture, deferral (queued, not dropped), write coalescing, two-level
  freeze with `feed.live` true, release flushing everything, chip text.
- Strips: the Logs strip held scrollTop 30 across activity, chip "↓ 1 log line · jump to newest",
  click returned to newest and cleared. Tape: 51 rows, guarded, counted chip, click returned.
- Scaling: five window sizes, no overflow, status bar visible, canvases not stale; engine view kept
  its backing store matched to the CSS box at 1600×900 and 1100×660; pinch changed `scaleY` with the
  page zoom cancelled.
- Gates: **311 passed · 2 skipped**, `intent.selftest.js` 7 ok / 0 failed, `ofx.selftest.js` 80 ok /
  0 failed, `audit_ui_refs.py` CLEAN, `node --check` on every touched JS, no `client error:` lines in
  the log for any of these runs.

**Unverified — say so before claiming otherwise**
- **Stacked-zone bands on live data.** The maths is proven (a forced same-side run yields one zone
  with the right shape) but no band has been *seen*: the live samples had no stacked runs, and the
  engine's view was zoomed to the live price while the bars' levels sat ~80 points away, so nothing
  of the footprint was on screen at all. Test it with the footprint visible.
- **The thermal ramp's pixel effect.** The switch and persistence are verified; the visual change was
  not observed because the heat layer had no depth history and the footprint was off-view.
- **The trace line's successor-path** (ladder highlight) — the note said "outside the drawn ladder
  levels" every time because the ladder was not in the same view. Verify with Depth and the engine
  side by side.
- **Tape scroll position across a rebuild.** The tape rebuilds its row table, so the offset can reset
  to the top on a rebuild; it never yanks the reader to the newest line and the chip appears. The
  Logs strip (append-style) held exactly. Restoring by row index is the fix if wanted.
- **4K at Windows 150 % scaling** — untested; fractional DPI costs a full re-raster.
- The **hidden-sweep count readout** next to the min-block filter (deferred; the engine already
  tallies it, the telemetry block's shape needs a real look).
- The **DTC socket flake** (`test_platforms.py::test_probe_handshake_against_a_spec_conformant_server`)
  — failed twice, passed in isolation both times. Worth a look before it hides a real failure.

---

## 3. Pitfalls that cost time today (read before debugging)

1. **A live page keeps the JavaScript it loaded.** Patching a file does nothing for an open window;
   probes then measure the OLD code and produce confident nonsense. Two fix attempts and three
   verification passes were wasted this way. Restart the app (or open a fresh page with cache
   disabled) after every edit, and say which build a result came from.
2. **Read `%APPDATA%\OrderFlowAnalysisPro\orderflow.log` first.** Client exceptions are POSTed to
   `/api/control/client-error` with `file:line:col` and a stack. That log named two of this session's
   real bugs within minutes; guessing from a screenshot cost far more.
3. **Fail-loud anchor edits.** Every scripted edit asserts its anchor matches exactly once and aborts
   without writing otherwise. Two edits landed in the wrong scope today (helpers inserted mid-class
   split a dataclass; a heading was swallowed by a patch) and the asserts are what caught them.
4. **`parseInt(x) || N` is a falsy trap** whenever 0 is meaningful. The tape's floor of 1 came from it.
5. **Long heredocs mangle.** Write scratch scripts with `write_file` to `$LOCALAPPDATA/Temp` and run
   them, rather than piping multi-line Python through bash.
6. **Browser harness quirks:** each `js()` call is capped at ~5 s (put waits in Python, not JS);
   a locked `bu-*.port` file needs a new session name; a backgrounded tab throttles rAF but DOM
   updates continue.
7. **Never commit.** The owner's standing rule; report "nothing committed" with the HEAD hash.

---

## 4. Where to go next, in priority order

1. **See the three unverified visuals** (§2) with a long-running instance: footprint in view, depth
   history present. If any is wrong, the evidence is a screenshot or a pixel count, not an opinion.
2. **Tape offset across rebuilds** — restore by row index rather than pixel offset (small, contained).
3. **Workstream A–H of `docs/AI_AGENT_BUILD_PROMPT.md`** — theme/token layer first (its gate is a
   grep for raw hex outside the token block), then the cursor-link spine (partly built: `cursor-link.js`
   exists and the engine publishes), then the strips/tape/alert-log refinements, then bar/candle
   expression modes, then replay parity, then the Windows installer.
4. **Harden the DTC test** so the flake stops muddying every gate run.

---

## 5. Gate commands

```
.venv/Scripts/python.exe -m pytest orderflow_system -q           # 311 passed, 2 skipped baseline
.venv/Scripts/python.exe scripts/audit_ui_refs.py                # CLEAN
node --check orderflow_system/desktop/ui/<file>.js               # every JS touched
node orderflow_system/desktop/ui/ofx.selftest.js                 # engine: 80 ok / 0 failed
node orderflow_system/desktop/ui/intent.selftest.js              # arbiter: 7 ok / 0 failed
.venv/Scripts/python.exe scripts/regen_config_golden.py          # only when config defaults change
```

## 6. New files from this session

| File | What it is |
|---|---|
| `desktop/ui/intent.js` + `intent.selftest.js` | the interaction/feed arbiter and its behaviour tests |
| `desktop/ui/strips.js` | scrolling-strip anchoring (holds the reader's place, counts arrivals) |
| `desktop/ui/cursor-link.js` | one price/one time, shared by every panel |
| `desktop/ui/heatmap-pro.js` | heatmap interaction layer (zoom, select, markers, exports) |
| `desktop/ui/scale.js` | the window-change authority (`OFAPScale`) |
| `desktop/ui/ofx.js`, `ofx-view.js`, `atlas.js`, `atlas-v2.js`, `ui.js`, `pause.js`, `guide.js` | extended (ramp, zones, pinch, trace, gates, freeze, wizard) |
| `dashboard/static/tape.js` | tape floor fixed (0 is a real floor now) |
| `orderflow_system/atlas/alerts.py`, `depthmap.py` | level-scoped rules, wall-age detection |
| `desktop/api.py` | `POST /api/control/export/save`, `POST /api/control/client-error` |
| `orderflow_system/test_{intent,strips,workstream_i,wall_age,tape_floor}.py` | the tests that hold all of the above |
| `docs/AI_AGENT_BUILD_PROMPT.md` | the agent brief for the next build phase |

---

## 7. 2026-09-15 — system sweep pass (report: `docs/SYSTEM_SWEEP_2026-09-15.md`)

A full four-step sweep (audit → edge cases → optimisation → roadmap) run against the live Bybit
feed in a sandboxed instance (`APPDATA` redirected, port 8099). Everything below is on disk and
verified; nothing is committed.

| Area | Change | Measured |
|---|---|---|
| `desktop/ui/ofx-view.js` | the Engine view now attaches `ofxHeat`, `ofxLive`, `ofxRibbon` — three of five layers had no canvas, so the depth heatmap, sweeps, crosshair line and CVD ribbon had never painted | canvas ink 0 → 17.9 k/27.4 k (heat), 6.7 k/9.9 k (ribbon) |
| `desktop/ui/ofx.js` | `math.barIndex` (binary search per print), `math.heatColumns` + `math.heatPalette` (column index + colour table), dirty flags always cleared, ribbon path reset | sweep repaint 29.93 → 1.34 ms; heat 0.278 → 0.074 µs/cell |
| `desktop/ui/ofx.selftest.js` | +14 checks for the new maths | 80 → 94 ok |
| `dashboard/static/tape.js` | row-in/row-out live path, per-second clock cache, batched `addTrades`, sub-unit sizes, dead flag removed | 3.628 → 0.284 ms per print; 237 → 7.1 ms per 120-row load |
| `dashboard/static/orderbook.js` | `size\|quantity` normaliser (the REST payload sends `quantity`), finite guards, one scroll per price change | NaN footer / no sizes → real sizes and totals |

Backend findings with line numbers (deliberately not applied — they need their own gates):
broadcast holds `_lock` across every `send_text` with no per-client queue; the tick batch buffer is
cleared after the await; Bybit's `u`/`seq` is used as a timestamp and never checked for gaps; no
retention anywhere (5.8 M tick rows / 547 MB today). Roadmap R2–R5 in the sweep report.

Fixed after three delegated read-throughs (each claim re-verified before acting — full detail in
`docs/SYSTEM_SWEEP_2026-09-15.md` §7):

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/index.html` | `intent.js` is loaded once: the eager tag now sits above `atlas-v2.js` and carries `data-atlas-intent="1"`, so the module's loader no longer injects a second copy (two arbiter instances, two flush timers, doubled listeners) | live: 1 script tag, `frozen:false` |
| `desktop/ui/pause.js` + `ofx-view.js` | the restart contract is real: `pause.js` keeps a `starters` set, empties dead ids on pause, iterates snapshots and exports `unregister`; the Engine view rebuilds its poll on resume (one pause/resume cycle used to stop its updates for the session) | live: 30 fetches/10 s → 0 paused → 25/9 s after resume |
| `desktop/ui/ui.js` | one restartable status poll that honours `OFAP_PAUSED`/`anyHeld()`, plus a logs poll that does the same; the duplicate 3 s status fetch is gone and the tick-rate chip is fed from `per_symbol` (the old code read a `ticks` field the payload does not carry, so the rate was always 0) | live: 0 fetches in 9 s paused; chip reads `{ticks: 2821, rate: 8}` |
| `data/bybit_feed.py` | the undrained `_tick_buffer` (one entry per trade, `flush_tick_buffer` had no caller anywhere) is gone — ~136 bytes/tick at ~52 ticks/s ≈ 250 MB per 10-hour day | grep repo-wide: no consumer; suite green |
| `data/database.py` | volume profiles no longer accrete per rebuild and reads return one row per session (his DB held 81 rows for 2026-09-14, so "last 5 sessions" was one day repeated); rebuilds delete-then-insert, reads take `MAX(id)` per session | new `test_volume_profiles.py`, suite 311 → 313 passed |

### 8. 2026-09-15 — Engine view: bounded navigation + interaction redesign

His report, verbatim: "design a system that prevents the user from scrolling outside draw distances ...
redesign a much better interaction implementation ... consider all metric ingest and output variables".

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/ofx.js` | the viewport is bounded in both axes and re-fits itself: `math.viewLimits()` derives hard limits from the data, `clampView()` clamps **zoom then offsets** (two phases, because the price window depends on `scaleY`) and is called from drag, wheel, pinch, resize, LOD, `snapToLive`, `fitSession` and `setData`; a data-identity change re-fits only when the new price band no longer overlaps the user's window, and a zero-bars-on-screen guard re-fits and counts the recovery | forced clamps by +/-1e6 on offsets and 1e5/1e-6 on zoom read `within: true` with 3-6 bars still on screen; the original blank stage (200 bars at ~99k replaced by 1 bar at ~77k) now lands the bar at x 56 y 108 |
| `desktop/ui/ofx.js` | no axis existed: the base pass now draws gridlines, a right price rail, a bottom clock ruler at adaptive stride, dimmed "no data" bands labelled `no bars after HH:MM:SS`, and the live pass a last-price tag; timestamps are the local clock everywhere (the tip printed ISO/UTC beside a local ruler) | ink probe on `#ofxBase`: rail 1 116 px, ruler 5 976 px; reads `76940 … 76860` and `18:39 … 18:47` |
| `desktop/ui/ofx.js` | `math.adaptHeat` sums the depth matrix onto the bar axis (resting depth + executed volume per `(bar, price)`, one best-bid/ask point per bar, events deduped per `(bar, price, kind)`) — the payload's ~1 s columns were each drawn one bar wide and smeared | heat cells 48 400 -> 593, p95 4.6 -> 0.3 ms, cells per bar `[5:12, 6:69, 7:207, 8:209, 9:96]`; selftest 106 -> 109 checks |
| `desktop/ui/ofx.js` + `ofx-view.js` | the ingest the view ignored is drawn: `calc{}` (volume/buy/sell/delta/POC share/max bid+ask/imbalances), `traded[][]` as flow bubbles, `best[]` as a spread line, `events[]` as stack/pull marks | live: `traded 208 cells`, `best 57`, readout shows POC 20.9 %, max bid/ask with sizes |
| `desktop/ui/index.html` + `atlas.css` + `ofx-view.js` | `#ofxReadout` panel beside the stage (flex row, 20 rows) with the full metric set, `#ofxFit` button, double-click = fit session, an interaction legend, value clipping | overlap check: stage x 240 w 784, panel x 1032 w 206, `overlaps: false`; `#ofxTip` three lines in local time |

Open item deliberately not changed: **the footprint endpoint publishes closed bars only**, so the newest
drawn bar trails the live tape by 45-196 s (newest print 1789464016 vs bar end 1789463940) and
`prints`/`sweep` read 0 for the forming bar. The view says so in its status line; drawing a live forming
bar changes what the view shows and is his call. Backend hardening items from §7 remain unapplied, and
the DTC flake stands.

### 9. 2026-09-15 — Engine legend system + cleaner bars

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/ofx.js` | footprint cells drew `Math.round(bid/ask)` — on crypto sizes (0.001-3) the matrix said "0" almost everywhere (16 of 86 levels on the sampled bar). Now `math.fmtSize` (0.002 / 0.045 / 2.6 / 1.2k) and an empty half is a faint dot | live cell samples; selftest cases for sub-unit, contract and kilo bands |
| `desktop/ui/ofx.js` | bars are framed and annotated: alternating column band + 1px separator, per-column `Δ / V` badge above each bar's high | `columnBadges: 4` at the default `scaleX` 52 |
| `desktop/ui/ofx.js` | colours consolidated into `math.theme` (17 keys), read by the renderers (21 literals replaced) and by `OFX.legend()` — one table, two readers | selftest asserts every legend swatch resolves to a theme colour (first run failed on two that quoted axes literals) |
| `desktop/ui/ofx.js` | `OFX.legend()` — the panel's only source: layout (8 lines), 19 colour keys with meaning + live value, 10 data fields with source + refresh, 9 interactions, live params + stats | selftest + live reads |
| `desktop/ui/ofx-view.js` + `index.html` + `atlas.css` | `#ofxLegendPanel`: three columns, collapsible (remembered), refreshes every fifth 1-second tick, skips while text is selected | 29 rows / 19 swatches / 9 keys / 3 columns measured; collapse toggles; `C = 2.50` followed a param change |

Two bugs of my own, found by probing and fixed: the badge threshold (56px) exceeded the default column
width (52px) so it never drew; and the legend refresh timer was guarded on `view.init`, a flag that does
not exist in this module, so the panel held its birth values (an R change was invisible in it while
`OFX.state.params.R` had moved). It now rides the existing stats timer with no invented guard.

Not rendering-related but worth knowing: **his app instance was closed at ~19:06** — the log ends on
routine signal lines with no traceback, and no OrderFlow process is running. The sandbox on 8099 is
stopped too.

### 10. 2026-09-15 — menu bar / sidebar / profile system plan

`docs/UI_MENU_AND_PROFILES_PLAN.md` — a plan for approval, built from the reference platform and the DTC platform
reference screenshots in `Desktop\New Folder` (register of all 15 in section 1) plus the reference platform
volume-dots knowledge-base page, the reference platform's Open-The-Main-Window, the conventional Chartbooks/Global-Settings/
Transfer pages and the reference platform's workspaces/templates docs, against an inventory of this app's own chrome,
config store and control API.

Headlines: no menu bar exists today (one ☰ overlay); workspaces persist but capture only three fields;
`/api/control/profiles/*` is already the volume-profile feature so the new one is specified as
`/api/control/user-profiles`; credentials stay out of profiles by rule and by test. The plan proposes a
registry-driven menu bar (File/View/Chart/Data/Profiles/Tools/Help), the rail plus per-view Options dock
and workspace tabs, one `param-registry.js` behind every settings dialog, and a schema-versioned profile
store with save/load/rename/duplicate/import/export/backup/restore, five shipped templates, autosave and
quick-switch hotkeys. Five build phases, each with a gate, and six decisions waiting on him (menu style,
profile scope, auto-load, tabs timing, naming, secrets policy).

### 11. 2026-09-15 — Menu bar phases 0 and 1 (plan: docs/UI_MENU_AND_PROFILES_PLAN.md)

Decisions he made: classic menu bar + toolbar; profiles carry alerts + watchlist (opt-out at save);
ask "restore last session?" with a "don't ask again"; tabs in phase 5.

| Area | Change | Verified by |
|---|---|---|
| `desktop/param_registry.py` (new) | the display-variable registry: 81 variables, 17 groups, 14 views, each with kind/bounds/unit/meaning/`applies`; values read from `config_store` at call time, never duplicated | `test_param_registry.py`: 9 tests including **coverage** — every display-relevant leaf in `default_config()` must be registered (suite 313 -> 322) |
| `desktop/api.py` | `GET /params` (registry + live values + defaults), `POST /params` (registered paths only, coerced, clamped by the store, returns the adopted value), `POST /folder/open` (whitelisted config/logs/exports) | live: set R 5.5 -> `stored R = 5.5`; restore -> `stored R = 4` |
| `desktop/ui/menubar.js` (new) | File/View/Chart/Data/Profiles/Tools/Help with accelerators, ticks, disabled-with-reason, inline submenus, Alt/arrow/Enter/Esc navigation, zen mode; **Chart = the active view's own variables** from the registry, with an inline editor (number+slider / bool / enum) and per-variable Restore default | live probes: 7 menus, File 15 items (6 disabled with reasons), View 32 items with ticks, Data sources with "Bybit . active", Chart values inline, editor round trip, keyboard walk, view-switch re-pointing |
| `desktop/ui/index.html` + `modules.css` + `scripts/audit_ui_refs.py` | the `#menuBar` row, its styles (dropdown as a layer of the bar so nothing clips it), the script tag, and `menubar.js` registered in the audit | AUDIT CLEAN; the audit **caught** the one template-literal route the module used |

Three self-inflicted defects the probes caught, all fixed: the dump had no `default` (Restore default
(undefined) and a refused write); `closeAll()` ran before `run()` so `Change…` never opened its editor;
and the engine route was a template literal the audit could not match. Next phase: per-view settings
dialogs from the registry, starting with Engine.

### 12. 2026-09-15 — top-menu dismissal, the ADX/RSI/MACD/OBV/Williams%R add-on pack, drawing layer

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/menubar.js` | the dropdown now closes on any outside touch: `closeAll()` clears the **slot's** class (it only cleared the dropdown's, so menus never shut) and dismissal is a **capture-phase mousedown** plus focusin/blur/scroll/Tab | click the matrix `true -> false`; click the rail -> closed; Escape -> closed; Alt focus, Arrow keys, Escape behave; the matrix still pans (overlay `pointer-events:none` when idle) |
| `desktop/ui/indicators/{adx,rsi,macd,obv,williams-r}.js` (new) | the requested indicators as add-on modules on the existing contract, each carrying `pack`/`version` (OrderFlow indicator pack v0.4.1) | `indicators.selftest.js` 25 checks 0 failed (RSI 100/0 extremes, OBV arithmetic, %R edges, MACD histogram identity, ADX 0-100 + DI dominance); `test_indicators.py` (suite 322 -> 325); live: 5 of 11 modules listed as the pack |
| `desktop/ui/study-api.js` + `studies.js` | `registry.list()` reports pack/version and the library row shows them | live registry dump |
| `desktop/ui/drawings.js` (new) | view-agnostic drawing layer: 11 figures (line, ray, hline, vline, rectangle with extend, ellipse, channel, Fibonacci, text, measure), Shift-45 constraint, endpoint handles, right-click context menu, single-figure mode, hide/clear, axis highlighting, data-space storage | live: gesture-drawn line in data space, persisted via the API, single-figure returned to Select, context menu with six actions, drawings survived a view switch |
| `desktop/api.py` + `config_store.py` | `GET/POST /api/control/drawings` per view+symbol with a strict sanitiser (kinds whitelisted, finite points, hex/rgba colours only, width 1-8, 500 rows/slot, 64 slots) | sanitiser probe: width 99 -> 8, dash 'wobbly' -> solid, a script-url colour -> default, bad rows dropped |
| `desktop/ui/menubar.js` + `modules.css` + `ofx-view.js` | a **Drawings** menu (figures with ticks, modes, colours, the view's drawing list) and the Engine-view mount | live: menu lists 11 figures + modes + `Clear all drawings (2)`; layer mounted with 11 tool buttons |

Known staging: the layer is mounted on the Engine view; the candle chart (lightweight-charts) and the
Heatmap follow through the same adapter contract. `mountDrawings()` was defined but never called at
first — the live probe caught it (layer absent), fixed and re-verified. Next phase remains the
per-view settings dialogs from the parameter registry.

### 13. 2026-09-15 — ModFlow OrderFlow Analysis Suite rename + third-party strip

Display name `OrderFlow Analysis Pro` → **ModFlow OrderFlow Analysis Suite** in 30 files (36
occurrences) and in the chrome: page/window title, rail brand (mark `MF`, name `ModFlow`, sub
`OrderFlow Analysis Suite`), top bar, launcher title, frozen-build `APP_NAME`.

Deliberately unchanged so his install keeps working: the `orderflow_system` package, the config dir
`%APPDATA%\OrderFlowAnalysisPro`, the log/DB names, the repo path, and the config key
`platforms.sierra` (his saved DTC block lives there). The DTC route path *was* neutralised —
`/platforms/bridge/dtc` (+ `/test`); the old `/platforms/sierra/dtc` and `/platforms/open` are gone.

Third-party material removed: the plan/link/install-detection content of `platforms.py` (the module
is now just `dtc_defaults()` + `suggested_symbols()`), the promo halves of `platforms.js` and
`/api/control/platforms`, six reference documents (`PLATFORM_BRIDGES`, `PLATFORM_INTEGRATION_PLAN`,
`NINJATRADER_NOTES`, `TRADOVATE_STUDY_BRIDGE`, `ATAS_COMPARISON`, `ATAS_FEATURE_INTEGRATION`), the
29 MB `.scratch/` research folder, and **612 prose pointers across 77 files** reworded to neutral
wording. The vendored chart library was left alone: third-party code under its own licence.

Repairs after the sweep (it broke two things, both found by the gates): an apostrophe inserted into a
single-quoted JS string in `test_studies.py` (`'ATR (the suite's …-shaped)'` → `'ATR (contract-shaped)'`),
and "the the …" double articles in 15 files from mid-sentence token replacement. A follow-up scan
reports no vendor product words left in our files.

Verified: **316 passed / 2 skipped** (the nine removed catalogue tests account for the drop from
325), `AUDIT CLEAN`, all modules parse, both selftests green; live: sandbox boots, the page serves the
new title/brand, the bridge payload is DTC-only, `/platforms/open` → 404, the neutral DTC route → 200.
Nothing committed — HEAD `b2ff4ee`.
### 14. 2026-09-15 late — Sierra Chart integration (free-first, with a plan toggle)

`platforms.py` + `platforms.js` + `/api/control/plans|open` rebuilt as the suite's own integration
surface: a 6-step free-path workflow (7 with the activation step for paid), 12 allow-listed links
(download, trial, delayed feed, create account, control panel, activate package, pricing, payment,
DTC protocol, setup, support, futures data), plans listed free-first with the published monthly
prices (`0 / 26 / 36 / 36 / 46 / 56` USD) quoted as read 8 September 2026 with the source link and the
exchange-fee caveat, local-install detection, and a "load into my workflow" toggle whose stored facts
(`platforms.sierra.plan`, `.integrated`) change the workflow, the data-quality wording and the status
line. Verified live: p10 switch → 7 steps + real-time wording, then back to free; the link opener
refuses non-allow-listed hosts; install detected at `C:\SierraChart` build 2950. Tests:
`test_sierra_integration.py` (8), suite 324/2, AUDIT CLEAN.
### 15. 2026-09-15 late — dxFeed-style terminal shell + Quantower: plan

`docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md`. Key finding: the panels are already widget-shaped
(`<section class="view">` + own MutationObserver), so the terminal mode **re-parents** them into widget
frames instead of forking them — the switch costs a detach, and Classic stays byte-for-byte today's
DOM. Adds: `shell.js` host, layout store (named layouts/tabs/per-screen, config-backed), widget
chrome, tab strip, symbol/timeframe link groups, and a refcounted channel bus so N widgets on one
symbol share one subscription. New additive widgets: Watchlist, News, Fundamentals, Options/Greeks
(the last states plainly when no Greeks feed is configured). Top bar gains Layout ▸ and the
Classic|Terminal switch (Ctrl+Alt+T) plus a status-bar mode/tab/widget/feed readout. Quantower gets
the same treatment as Sierra in phase 6, held until its licence prices can be read from source rather
than guessed.

### 16. 2026-09-15 late — Terminal shell **phase 0** (plan: `docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md`)

The host that re-parents panels, the layout store behind it, and the round-trip gate. Nothing
committed — HEAD `b2ff4ee`.

| Area | Change | Verified by |
|---|---|---|
| `desktop/config_store.py` | new `layouts` block: `{mode, active, items{id:{name, mode, screen_key, theme, saved, tabs:[{id,name,widgets:[{view,x,y,w,h,link,settings}]}]}}}`. One grid constant set (`LAYOUT_GRID_COLS/ROWS` 12×8, 24 layouts, 12 tabs, 24 widgets/tab). Geometry clamped in two phases (size, then position) so a widget can never be stored hanging off the grid; ids/tab ids must be slugs; unknown views, duplicate tab ids and non-scalar settings are dropped; `active` must name a stored layout | `test_layouts.py` (17 tests) |
| `desktop/api.py` | `GET/POST /api/control/layouts` — one write per call (`mode · save · import · duplicate · rename · delete · activate`, `export` returns a bundle and writes nothing). Every response carries the state the store *accepted*, and a refused save is reported instead of vanishing | live: `{"mode":"terminal","save":…,"activate":…}` → `actions: ["mode","save","activate"]`; bad-id save → `ok:false` + reason |
| `desktop/ui/shell.js` (new, 765 lines) | the host: `OFAPSHELL` with `switchTo/focusView/openWidget/closeWidget/activateTab/arrange/saveNow/stats/math`. Panels are **re-parented** into `.widget-frame`s inside a 12×8 CSS grid; every section stays in the document (hidden tabs use `.wf-off`, never detach); a section carries `.active` exactly while a frame showing it is visible, which is the meaning that class already had. `showView` is wrapped (Classic = straight delegation; Terminal = open/focus that panel's widget) and a capture-phase rail listener covers the case where a module re-wraps it later. Widgets auto-save through `OFAPINTENT.queueWrite` (never mid-gesture) | see the round trip below |
| `desktop/ui/shell.selftest.js` (new) | the layout maths in Node: rect clamping (incl. the falsy-zero family — `null`/`''` are *missing*, not 0), overlap, first-fit slotting, dense tiling (no overlap, inside the grid, exact cover for square counts), the normaliser (drops unknown/duplicate panels, clamps, unique tab ids, ≥1 tab), idempotence of `normaliseLayout(defaultLayout(…))` | `18 ok, 0 failed` |
| `desktop/ui/index.html`, `atlas.css`, `scripts/audit_ui_refs.py` | script tag (+ `shell.js` registered in `JS_FILES`), the rail-footer **◫ Terminal mode** button, and the terminal CSS block (grid, frame chrome, bar, tab chips) + container queries | AUDIT CLEAN |
| `orderflow_system/test_shell.py` (new) | gates the above: parses, selftest passes, documented surface exists, loaded in `index.html` and registered with the audit, grid/cap numbers agree with `config_store`, the module contains no engine/socket/feed call, Classic is delegation-only, it announces `ofap:relayout` (and the Engine view acts on it), and no `localStorage`/`sessionStorage`/`indexedDB` anywhere | suite **351 passed / 2 skipped** |

**The round trip (the phase-0 gate), measured live in a sandboxed instance on 8099 with the Bybit
feed running** — Classic → open widgets → Terminal (two tabs) → Classic:

* Classic: 24 sections in `main.views`, no host, no body class, one `.active`.
* Terminal: 10 frames, 7 visible on Main and 3 on Macro; `.view.active` count == the number of
  visible widgets (7 then 3 after clicking the Macro chip) — hidden tabs really do pause their panels.
* A rail click in Terminal mode placed *and* focused the clicked panel (11 placed afterwards).
* `order_exact: true` — all 24 sections came back in the exact recorded order; host gone, body class
  gone, frame count 0, one active view.
* Ingest was never touched: `OFAPINTENT.status().feed.ticks` 0 → 4 426 across the terminal leg and
  4 480 after the return, with `feed.live` true throughout.
* Mode persists: after switching to Terminal and reloading, the app boots **in** Terminal with the
  same 10 widgets (7 visible), and switching back restores 24 sections.
* `client error:` lines in the sandbox log over the whole session: **0**.

**Two defects found by the probe and fixed (they were mine, both in `shell.js`):** the first restore
re-inserted each section "before its recorded next sibling" — a sibling still inside a frame reads as
absent, so the node was appended instead and the 24 sections came back **shuffled** (the fix is a
DocumentFragment re-append in recorded order, which cannot depend on where the nodes happen to be);
and the Engine view's fixed 238 px readout starved its canvas to **79 px** inside a 327 px frame
(container queries on the frame — `container-type: inline-size` — now size the panel by the frame:
295 px stage, 293 px canvas). Grid rows also changed from `minmax(120px,1fr)` to `minmax(56px,1fr)`
so a full board fits the window instead of always scrolling.

**A third defect the same probe found, in the Engine view's own geometry** (`ofx-view.js`): the
engine's pointer maths reads `getBoundingClientRect`, so its internal space and the stage box have to
be one thing — `stageSize()` returned `max(240, clientHeight - 8)`, and in a 148 px-tall widget that
made the hovered price (and the trace line naming it) land elsewhere on the drawn matrix. It now
returns the exact box, `null` when the stage is hidden (0×0 is not a size to draw at, and the caller
keeps the last real one), the view re-measures whenever it comes back on screen, and the shell
announces every re-parent/arrangement change as `ofap:relayout` — a re-parent is invisible to the
window resize listeners the views already have, so without that the canvas kept its Classic size
(measured: 293×240 inside a 213×148 stage). Verified live: stage == internal == canvas at
750×260 (Classic), 293×148 (widget) and back; hover offset **0.00 px** (34 px before the fix); a
hidden Engine view keeps 750×260 instead of collapsing to 1×1.

**The DTC flake from §2 is fixed.** `test_probe_handshake_against_a_spec_conformant_server` asserted
the mock server had *recorded* the client's LOGOFF while the server thread was still reading it —
about one full-suite run in four failed on that last line. The test now waits (up to 1.5 s) for the
logoff to arrive before asserting. Four consecutive full-suite runs: `351 passed / 2 skipped` each.

**Deliberately still open:** drag/resize/maximise/float and the tab strip's add/rename/reorder/close
(phase 1); the Layout menu, per-screen profiles and status-bar fields (phase 2); link groups (3);
the channel bus (4); Watchlist/News/Fundamentals/Options (5); Quantower, held on its licence read
(6). The active tab is session state (it resets to the first tab on reload) — the store has no field
for it yet. A layout whose panel does not exist in the build is dropped with a line in the bar, and
the drop is not persisted until the user changes the arrangement.

### 17. 2026-09-15 late — Terminal shell **phase 1**: widget chrome, tab strip, keyboard

`shell.js` 765 → 1185 lines, `shell.selftest.js` 18 → 22 checks. Nothing committed — HEAD `b2ff4ee`.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/shell.js` | **drag by title bar** and **resize from the corner grip**, snapped to grid cells through two new pure functions (`math.moveRect`, `math.resizeRect` — size limited by the distance to the edge, position kept), with the clamp applied on every pointermove, so no gesture can leave the grid; the widget you just placed is brought to the front | live: a 2-cell/1-cell drag landed exactly at (6,1); a drag 3× the board past the corner stopped at (8,6) = the edge; `bounds().outside` 0 throughout |
| `desktop/ui/shell.js` | **⛶ maximise** fills the grid and **Esc/the button restores** — the pre-maximise rect rides in the widget's own `settings` (`px/py/pw/ph/max`), so it survives a reload; **⚙** opens the parameter registry for THAT panel | live: 12×8 + `.wf-max` + `settings {px:8,py:6,pw:2,ph:1,max:true}`; Esc → 2×1 at (8,6); the gear opened the Chart menu with the ofx panel's variables (`ofx.R`, "Stacked run (levels)", 65 items) |
| `desktop/ui/menubar.js` | `OFAPMenuBar.setView/openFor` — the shell moves the registry's notion of "active view" to the widget the user is working in (several panels are on screen at once in Terminal mode) | live: the gear's menu carried the focused panel's variables, not the previous view's |
| `desktop/ui/shell.js` | **tab strip editing**: `+` adds a tab, double-click renames in place (the input stops its own keys so a tab named "1" is not the tab hotkey), drag reorders, `×` on the active chip closes it (and says how many panels went with it) | live: add → `t3 "Tab 3"` → renamed to "Scalper"; drag `main` onto `macro` → `[macro, main, t3]`; `×` closed Main with "8 panel(s) went with it"; 1 tab minimum, 12 maximum |
| `desktop/ui/shell.js` | **keyboard**: `Alt+1…9` switch tab, `F11` fills the grid with the focused widget (first widget if none), `Esc` restores it then drops the focus ring; typing is never a hotkey | live: Alt+1/Alt+2 switched tabs; F11/Esc round-tripped the maximise |
| `desktop/ui/shell.js` | `bounds()` telemetry (per-widget rect + `inside`, `outside` count) for the gate | the gate below |
| `desktop/ui/atlas.css` | frame chrome styles (`.wf-btn`, `.wf-grip`, `.wf-move`, `.wf-max`), tab chips (`.tt-name/.tt-x/.tt-add/.tt-input`), `body.wf-gesture` (no text selection; the panel under the pointer stops receiving it) | visual probe + no client errors |

**The phase-1 gate**: *twelve widgets on one tab stay inside the frame bounds; frames persist across a
reload.* A layout with twelve panels on one tab (tiled 4×3) loaded from the store: 12 frames, **none
outside the board** (board 998×504 px, frames 120–248 px; the check compares against the board's
*content* box, because the board scrolls), `bounds().outside === 0`, 12 `.view.active`, and all 24
sections still in the document. A drag and a resize then survived an **immediate** reload, and
switching Classic → Terminal → Classic restored the 24 sections in the exact recorded order with
`OFAPINTENT` ticks rising throughout and **0** `client error:` lines.

**Three defects the probe caught and this session fixed** (two mine, one a real persistence hole):
1. `math.resizeRect` first used the store's storage clamp, so a long rightward resize **jumped the
   widget to the left edge at full width** instead of stopping at the edge — caught by a self-test
   expectation, not by eye.
2. **A dragged arrangement could be lost.** Writes are deferred behind the arbiter's gesture lease
   (by design), so a drag followed by a reload within ~1.6 s reverted (measured). `pagehide` /
   `visibilitychange` now run the pending save immediately with `keepalive`, and a dirty stamp means
   a save in flight never swallows later edits.
3. Probe-side, worth remembering: "widgets inside the board" must be measured against the board's
   scrollable *content* box — comparing against the visible box flagged the bottom row as outside.

**Deliberately still open in this area:** *float* (free-pixel windows that hover over the board) is
not built — **⛶ fills the grid**, which is the same thing within the 12×8 model this suite uses; the
symbol/timeframe link chip belongs with phase 3's `links.js`; the ⚙ button opens the registry's own
Chart-menu editor rather than a new per-panel dialog (phase 2 builds those); the active tab is still
session state, and maximising a widget stores the full-grid rect plus the pre-maximise rect.

### 18. 2026-09-15 late — Terminal shell **phase 2**: Layout menu, workspace switch, status fields

Nothing committed — HEAD `b2ff4ee`. Suite **352 passed / 2 skipped** (one new test), AUDIT CLEAN,
`shell.selftest.js` 22 ok.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/menubar.js` | a **Layout** menu built from the store on every paint: Workspace (Classic ⇄ Terminal with a tick), This layout (Name · Save now · Save as… · Duplicate · Delete…), Auto-arrange this tab (disabled with its reason in Classic mode), Reset to the starter board, Save for this screen (`1920x1080@1.25`), Export current…, Import (paste a bundle)…, then every saved layout with `· active` / `· this screen` / `saved on <key>` and its widget/tab counts, and `N of 24 layouts` | the menu listed all three headers + 15 items; the Saved-layouts rows carried the counts |
| `desktop/ui/menubar.js` | text answers happen **in place** (`mbPromptInput`, Enter applies · Esc cancels · Ctrl+Enter for the multiline paste box) instead of `window.prompt`, which the frozen shell's WebView is not guaranteed to render | typed "Evening board" into the prompt with real keystrokes and Enter → saved, active, `screen_key 800x600@1`, status line "saved as “Evening board”" |
| `desktop/ui/shell.js` | layout CRUD the menu calls: `saveAs / renameLayout / duplicateLayout / deleteLayout / activateLayout / saveForScreen / resetBoard / exportLayout / importLayout / layouts / refreshLayouts / screenKey`; every action adopts **what the store accepted**, and Delete asks for the layout's own name first | rename → "Evening desk"; duplicate → "Evening desk copy"; delete with a wrong name **refused** ("the name did not match"), with the right name → stepped onto the next layout; reset → the 4-widget starter board; arrange → a 2×2 tiling with `outside: 0` |
| `desktop/ui/shell.js` | export writes a **real file** (store bundle → `POST /api/control/export/save`), import takes a pasted bundle under a fresh id with a de-duplicated name, and an unparseable bundle is refused by name | `layout-Start.json`, 1 066 bytes on disk (keys `["layout"]`, one tab, 4 widgets); the same bundle imported as "Start 2"; `'not json at all'` → "that is not a layout bundle (invalid JSON)" |
| `desktop/ui/index.html` + `atlas.css` | the **workspace switch** in the top bar's right cluster (`#modeSwitch`, segmented, `aria-pressed`, one click, no menu) and four status-bar fields: **mode · tab · widgets · feed** | live: clicking Terminal switched the mode, the segmented control followed, and the status line read `Terminal / Twelve / 12 / Bybit · free feed` |
| `desktop/ui/shell.js` | the **feed** field follows the stored plan (Sierra `plan` + `integrated` from `/api/control/platforms`) and falls back to the built-in source from `/api/control/sources` — the wording the platform module itself promises ("free feed" / "delayed data" / "real-time data") | `Bybit · free feed` with no Sierra integration on; the wording is the platform module's own |
| `desktop/ui/menubar.js` | **defect found and fixed:** ArrowDown inside an open menu did nothing — the only ArrowDown branch opened a menu from a *title*, so with an item focused the keyboard could reach the **first item of every menu and no further**. Added the in-menu walk (with the ArrowUp branch that already existed) | walked all 13 Layout items with real CDP keystrokes (Alt → → → ↓ then 12 × ↓), each step reading `document.activeElement` |

**The phase-2 gate** — *every menu item reachable by keyboard; switches and layouts round-trip through
the config*: the Layout menu is reachable at Alt → → → ↓ and every item walks with ↓ (and ↑), the
in-place prompt takes typing and applies on Enter; the top-bar switch and the Layout menu both write
the mode, and the arrangement writes go to the config store — after a reload the app came back in
**Classic** (24 sections, no host) and then, with "Twelve" active, in **Terminal with all 12 widgets**
and the status bar reading `Terminal / Twelve / 12`. Classic → Terminal → Classic still restores the
24 sections in the exact recorded order, and the sandbox log has **0** `client error:` lines.

**Harness note for the next session:** a CDP `Input.dispatchKeyEvent` Enter does **not** synthesise the
default activation of a focused `<button>` (a real Enter does); the item path was verified by the same
`click` a real Enter produces, and the keystroke path was verified on the walk and in the prompt input.


### 19. 2026-09-15 late — Terminal shell **phase 3**: link groups (symbol / timeframe A–D)

Nothing committed — HEAD `b2ff4ee`. Suite **361 passed / 2 skipped** (9 new tests), AUDIT CLEAN,
`shell.selftest.js` 22 ok, `links.selftest.js` 10 ok.

The shape of the phase, in one line: **membership is stored, meaning is derived.** A widget's link
lives in the layout (`config_store` sanitises `"<symbol group>/<timeframe group>"`, A–D, either side
optional) so it survives a reload and travels in an exported bundle; what a group's symbol and
timeframe *are* is seeded from the panels already on screen, because the panels' own controls are the
only place those values really live.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/links.js` (new) | `window.OFAPLINKS`: groups A–D, `plan/controlsOf` (pure: who moves, onto which controls), `setGroup/apply/seed/sweep`, `groups/members/state/tfLabel`. Reach for a panel through its **own** control where it has one (`ofx → #ofxSymbol`), the app-wide instrument (`#symbolSelect`) otherwise, and `#tfSelect` for timeframes — the chart is the only panel with one | `links.selftest.js` 10 checks: members of A move, a B member does not, a panel that joined nothing does not; three app-wide members are **one** control; a timeframe plan only reaches the chart |
| `desktop/ui/links.js` | two-way: a user change of the app instrument moves every group linked to it; a panel's own select moves only its own group. Every write the module makes is wrapped in `state.applying` so its own change cannot bounce back as user input | live: dispatching a `change` on `#symbolSelect` (BTCUSDT) moved group A and left group B on SOLUSDT |
| `desktop/ui/shell.js` | the **link chip** in every widget's title bar (`⇄ A·B`, `⇄ –·–` when independent) with a popover of `– A B C D` per kind, the current choice marked, and a note naming the group's values **and where they land** ("(the app-wide instrument)" vs "(this panel)") | chip + note read back for all five panels; picking timeframe group B from the popover wrote `B/B` through store, chip and note in one click |
| `desktop/ui/shell.js` | `linkSpec / setLink / linkMembers / paintLinkChip`, `math.parseLink / math.formatLink` (the one reader/writer of the link shape), and `ofap:links` announced on a membership change so the module re-reads | membership set on a live layout and read back from `config.json`: `Start → [ofx A/, tape A/, depth B/]`, `Twelve → [ofx B/B, tape A/, depth A/, chart A/A]` |
| `desktop/config_store.py` | `LAYOUT_LINK_RE` — the link is now **validated**, not just truncated: `"A/B"`, `"A/"`, `"/B"` kept as written; `"E/Z"`, `"1/B"`, `"A/B/C"`, `"/"` stored as no link (a link that is not a link is nothing, not text) | `test_links.py::test_the_membership_shape_matches_the_store` (JS writer and Python sanitiser accept exactly the same strings) |
| `orderflow_system/test_links.py` (new) | 9 tests: the module loads and parses, its self-test passes (≥10 checks), it exposes the documented surface, it is loaded **after** the shell, the shape agrees with the store, and — the invariant this layer exists for — **it never reaches for the engine** (no `/api/`, no `fetch(`, no WebSocket) | full suite 361 passed / 2 skipped |
| `scripts/audit_ui_refs.py` | `links.js` added to `JS_FILES` | AUDIT CLEAN |

**The phase-3 gate** — *changing a group moves every member widget; non-members unaffected*:
`setGroup('sym','A','ETHUSDT')` moved the app instrument (`#symbolSelect` **and** `S.symbol` — the
app's own handler ran, so every engine-following panel really did re-read) while the group-B panel kept
BTCUSDT and the panel that joined nothing stayed independent; `setGroup('sym','B','SOLUSDT')` moved only
the Engine's own select, no cross-talk; `setGroup('tf','A','300')` moved `#tfSelect` and `S.tf`. With
the engine **running**, a group symbol change left ingest alone: ticks **146 → 266**, engine still
`Running`, and the sandbox log holds **0** `client error:` lines and **0** engine stop/restart calls
across the whole phase.

**Two defects the gate caught, both fixed:** (1) a value a select cannot hold (an instrument this
installation does not list) *cleared* it — `control.value` was assigned before it was checked, so the
instrument went blank; the control is now put back to what it held, nothing is dispatched, and the
refusal is reported (`"sym A → NOTLISTED: 1 control(s) refused it"`), with a good value applying
normally right after. (2) the chip's timeframe note read `timeframe B ·` with nothing after the dot
when the group had no value yet — now `—`.

**Also fixed while testing (phase-2 surface):** `activateLayout` took an **id** only and failed
*silently* when handed a name, while the menu shows names; it now resolves an id or a unique name
(`resolveLayoutKey`) and refuses to guess when two layouts share one.

### 20. 2026-09-15 late — Bookmap folded in beside Sierra (side task; phase 4 not started)

Nothing committed — HEAD `b2ff4ee`. Suite **374 passed / 2 skipped** (13 new platform tests), AUDIT
CLEAN, sandbox log 0 `client error:` lines.

**The read, from the installed Bookmap 7.8.0 build:13** (not from marketing pages alone): build number
from `Bookmap.jar`'s manifest; API jars in `C:\Program Files\Bookmap\lib` (`bm-l1api`,
`bm-simplified-api-wrapper` + javadocs, `bmmp-history-data-library-jvm`, `api-jvm-0.1.22-alpha`); API
folders `%LOCALAPPDATA%\Bookmap\API\Layer0ApiModules` (adapters, `…---name---version.jar` + `.metadata`)
and `Layer1ApiModules` (add-ons). It listens on **no local port** and publishes **no data-out API** —
its API is in-process, so an add-on is the only way out.

| Area | Change | Verified by |
|---|---|---|
| `data/bookmap_client.py` (new) | the suite's end of the add-on wire: NUL-framed JSON, `bookmap_probe()` shaped like `dtc_probe` (ok/stage/messages/sample/rejects/detail), symbol filter, unknown types tolerated, never raises, 1 MiB frame ceiling | 9 tests vs a mock add-on (hello/no-hello/garbage/filtered/dead-port/bad-port) **and** a live run through the UI button: *"add-on ofap-bookmap-bridge 0.1 on Bookmap 7.8.0 build:13 · licence Digital — hello 1, snapshots 9, trades 9, depth 9"* |
| `data/bookmap_addon/` (new) | the Bookmap side as a template: `OfapBridge.java` (read-only, loopback-only, `Layer1SimpleAttachable` + `CustomModuleAdapter` + trade/depth listeners, names and signatures taken from the **installed** javadocs), `build.gradle` compiling against `fileTree(C:/Program Files/Bookmap/lib)`, README (build, install via *Settings → Configure API plugins → Add*, licence gates, frame format) | **not compiled here — no JDK on this machine** (Bookmap ships a JRE); the README and the UI say so rather than implying it runs |
| `desktop/platforms.py` | Bookmap as a second catalogue row: 13 allow-listed links (portal, packages-comparison, knowledgebase, bmdata, dxfeed, addons-info, the API tutorial, the Python-API GitHub repo), 4 tiers with published prices **read 15 September 2026**, the free-first workflow (incl. the add-on step and the licence-gate step), caveats naming the separate data bill and the one-instrument free tier, and `bookmap_defaults()` (loopback 8791, no credentials at all) | live: tiers `$0/1 ins`, `$19/3`, `$49/10`, `$99/20`; detection `7.8.0 build:13` + api jars + 3 L0 adapters |
| `desktop/platforms.py` | `detect_installs()` now returns both platforms; the Bookmap version comes from `Bookmap.jar`'s manifest and the API module folders are listed by filename only — **licence/account/config files are never opened** | a test plants `Keys/licence.key` and a token-bearing config in a fake install and asserts neither value nor the folder name appears in the result |
| `desktop/api.py` | `/platforms` keeps every Sierra key and adds `bookmap`, `bookmap_plans/_links/_caveats/_prices_as_of/_limits/_workflow/_note`; `/platforms/plan` takes `platform:"bookmap"`; new `/platforms/bridge/bookmap` + `…/test` | live: tier `globalplus` stored, workflow grew the activation step; Save stored `{enabled, port 8791, plan, addon_built}` |
| `desktop/ui/platforms.js` | five Bookmap cards under the five Sierra ones (integration header + tier select, setup steps, tier cards with instrument caps and backfill, "Bookmap on this machine", the loopback bridge card with Save/Test), a Bookmap result line, and updated help topics | live: 10 cards rendered; the bridge Test line; `path not on the allow-list: /someone/else` for a non-Bookmap GitHub path |
| `test_platforms.py` | 13 tests: catalogue order and free-first invariants for both platforms, tier caps/limits, caveats naming the gates, the two-vendor allow-list (incl. the `github.com` path trap and a lookalike host), the Bookmap workflow, credential-free defaults, the mock add-on suite, and detection vs the real disk | 374 passed / 2 skipped |

**Defect the tests caught:** the reader's counter map was singular/plural-wrong (`trade` never reached
`trades`; `snapshot` fell to `other`), so a live add-on would have read "0 trades" while streaming.
Fixed with an explicit frame-type → counter map (`quote` and `snapshot` share one bucket).

**Left open, deliberately:** the add-on cannot be built or installed from here (no JDK, and Bookmap
running on this machine is the user's live instance — nothing was installed into it). The suite side is
complete and tested; the Bookmap side is a build-and-add-once step for the user, with the licence gate
named on the card.

**Next: phase 4** (the channel bus with refcounts + telemetry) — not started in this run.

### 21. 2026-09-15 late — the bridge jar, actually built (JDK installed, compiler-verified)

The add-on is no longer a template-only claim: a JDK was installed and the jar built and statically
verified. Nothing committed — HEAD `b2ff4ee`.

**The build.** No JDK existed on this machine and Bookmap ships a JRE (its `jre/bin` has `java.exe` and
`keytool.exe` only), so a portable **Temurin 25.0.4.1** was unpacked to `C:\Users\<you>\tools\jdk-25`
(no installer, no admin, nothing on PATH). Bookmap's bundled runtime is **Temurin 25.0.2**, so the target
is Java 25 — `build.gradle` was corrected from the earlier Java-8 assumption (class files are major
version **69** on purpose; they only ever load inside Bookmap 7.8+).

**What the compiler corrected in the template** (this is why the build is the test):

| Was | Is | Why |
|---|---|---|
| `extends CustomModuleAdapter` | `implements CustomModuleAdapter` | `javap` on the installed jar: `CustomModuleAdapter` is an **interface** (`extends CustomModule`) whose `initialize(...)` and `stop()` are **default** methods. It was never a base class. |
| a leftover identity `frame(String)` helper | removed | dead weight; the JSON strings go straight to the socket |

Everything else compiled against the installed jars unchanged: `initialize(String, InstrumentInfo, Api,
InitialState)`, `stop()`, `onTrade(double, int, TradeInfo)`, `onDepth(boolean, int, int)` — all four
override the real interfaces.

**Verified artifact** `orderflow_system/data/bookmap_addon/ofap-bridge.jar` (7 027 bytes):
`javap -v` shows major version 69, `RuntimeVisibleAnnotations` carrying
`Layer1SimpleAttachable`, `Layer1StrategyName(value="OFAP bridge")`, `Layer1ApiVersion`; the class header
reads `implements velox.api.layer1.simplified.CustomModuleAdapter, TradeDataListener, DepthDataListener`
with the exact signatures, and its constant pool references Bookmap's own
`velox/api/layer1/data/{InstrumentInfo,TradeInfo}` — it cannot load anywhere but inside Bookmap.

**The licence question, answered from his own log rather than guessed:** Bookmap's current
`Logs/log_20260915_122952_560-common-01.txt` shows it loading and unloading
`velox.api.layer1.layers.Layer1ApiLargeTradesAlerter` — a Layer-1 strategy that the pricing table sells
with the paid tiers — so the API-plugins path is open on this licence. The log also shows his live
sources (`ESZ6.CME@BMD`, `BTC-USDT:MB:SP@BMD`, `AAPL@DXFEED`), so the bridge will carry real data for
whichever chart it is attached to.

**Left for the user (GUI only, nothing automatable):** Settings → Configure API plugins → Add → the jar →
enable → attach "OFAP bridge" to a chart → then Platforms → Bookmap → Test connection (127.0.0.1:8791).

### 22. 2026-09-15 late — Terminal shell **phase 4**: the channel bus, and the jar ships with the app

Nothing committed — HEAD `b2ff4ee`. Suite **388 passed / 2 skipped** (14 new tests), AUDIT CLEAN,
`shell.selftest.js` 22 ok, `links.selftest.js` 10 ok, `bus.selftest.js` 10 ok.

| Area | Change | Verified by |
|---|---|---|
| `desktop/ui/bus.js` (new) | `window.OFAPBUS`: channel = (method, url, params) with cache-busters dropped; **one timer and one in-flight request per channel**, refcounted; late subscribers start from the live payload; a tick during a slow response is skipped, not queued; `subscribe/poll/request/stop/stopAll/install/uninstall/telemetry/summary/reset/canon` | `bus.selftest.js` 10 checks: the key rules, 12 subscribers → 1 channel, a late subscriber, skips on a slow server, one-shot sharing, the wrapper's coalescing, failure + recovery, the interval floor |
| `desktop/ui/bus.js` | `install(['/api/…'])` wraps the global fetch for chosen prefixes only: concurrent identical GETs become one request, everything unmatched passes through untouched, `Response` handed back is real | live: 12 concurrent identical GETs → **1 request, 11 coalesced, 92 % saved** |
| `desktop/ui/index.html`, `shell.js` | a **bus** field in the status bar, written by `paintStatus` only when `OFAPBUS` is present (no bus, no crash) | status line reads `bus: 12 sub · 1 ch · 6 fetches` while polling, `bus: idle` after |
| `desktop/ui/bus.js` + `test_bus.py` | the invariants: exactly one `setInterval`/`clearInterval` in the module and it lives on the channel record; no storage; no engine/socket calls; loaded after shell+links; registered with the audit | `test_bus.py` 7 tests |
| `scripts/build_exe.py` + `platforms.py` + `api.py` + `ui/platforms.js` | the Bookmap add-on **ships with the app** (PyInstaller data, beside the UI), the suite reads the shipped jar's class-file version and the local Bookmap's `jre/release` and **compares** them, the card shows the jar line + path + "Show the jar", the wizard step says "no compiler needed" | live: *shipped with this app · built for Java 25 · your Bookmap runs 25.0.2* + "it will load as-is"; a fake install at Java 17 warns to rebuild; 7 new tests |

**The phase-4 gate** — *twelve same-symbol widgets produce one fetch per interval, three different
symbols produce three*: twelve subscribers on `/api/atlas/klines/BTCUSDT` at 1 s gave **one channel, one
immediate fetch, 6 fetches in 5.6 s and 72 deliveries**; removing them left `channels: 0` and the server
quiet. Three symbols × four widgets gave **three channels, three immediate fetches, 15 fetches in 4.3 s —
5 per symbol**, and the sandbox's own access log agrees (5 / 5 / 5). 0 `client error:` lines throughout.

**Stated plainly: the panels are not routed through the bus yet.** The gate was the bus's arithmetic,
and that is what exists — a delivery layer, its telemetry and an opt-in wrapper. Converting each view's
poll loop into a `subscribe` is the next per-panel step, not something this phase silently claimed.

**Defects caught by the self-test:** the `Math.max(100, intervalMs)` floor made 30 ms test intervals
untestable — the floor is now pinned as a rule and the checks run at/above it; and the flaky-transport
check was asserting against a `window.fetch` the module never reads (it uses the injected transport) —
rewritten to fail and heal the real seam.

### 23. 2026-09-15 late — phase 4b verified live, and phase 5's first two widgets (Watchlist, News)

Nothing committed — HEAD `b2ff4ee`. Suite **407 passed / 2 skipped** (19 new tests: 8 watchlist, 11
news), AUDIT CLEAN, `watchlist.selftest.js` 15 ok, `news.selftest.js` 17 ok, `bus.selftest.js` 11 ok.

**Phase 4b, re-verified in a live app** (sandbox 8098, my own run, not a self-report): the app boots
(26 views, 27 nav items, no error banner) and the delivery layer is installed for
`[/api/control/engine/status, /api/instruments, /api/status, /api/atlas/]`; the status bar reads
`bus: idle · watching …`, and with the Watchlist open the telemetry reads
**`bus: 1 sub · 1 ch · 17 fetches (4 saved)`** — the "4 saved" are real duplicate GETs the wrapper
coalesced in the running app, which is the app-wide adoption doing its job.

**The two panels** (built as parallel workstreams, each on its own three files; I verified the files,
ran every gate myself and checked both panels live):

| Panel | Files | Live evidence (mine) |
|---|---|---|
| Watchlist | `ui/watchlist.js` (477), `ui/watchlist.selftest.js` (415), `test_watchlist.py` (144) | 45 rows, count `45`, sub line *"polling 2s via the shared bus · engine stopped — no live rows · the server is answering with its demo list, not your feed"*, and **1 bus channel** — the panel shares one poll instead of adding its own timer |
| News | `ui/news.js` (348), `ui/news.selftest.js` (240), `test_news.py` (136) | 8 headlines rendered from the app's own context endpoint, source labelled *"built-in: decrypt.co, coindesk.com"*, first title real (*Why an AI Slowdown Could Collapse Under Commercial and US-China Pressure*) |

**What the workstreams found in the app** (recorded here because they matter more than the panels):

1. **`GET /api/status` does not exist** — it answers 404. The real route is
   `GET /api/control/engine/status` (which is also the route my phase-4b adoption had already been
   polling). My original brief named the wrong endpoint; the panel uses the right one.
2. **`GET /api/instruments` is not "your enabled instruments"** — with the engine stopped it returns the
   dashboard's own demo list (45 rows), and while running it returns the streaming set. The panel tags
   every row with the source the server reported and says so in its sub line, rather than dressing the
   demo up as a feed. (`GET /api/control/bootstrap` carries the literal enabled list — the obvious
   follow-up if "enabled instruments" is meant literally.)
3. **The engine status payload has no per-symbol volume** (symbol, price, ticks, candles, cum_delta,
   trade_phase, trade_direction) — so an engine-fed row shows `—` for volume.
4. **An unset `news_url` does not mean "no news"**: `atlas/context.py` falls back to its built-in public
   feeds (CoinDesk, Cointelegraph, Decrypt) and returns real headlines. The panel therefore labels them
   *built-in* and names the config key (`context.news_url`, set through the setup wizard's "Custom news
   feed"), reserving the literal "not configured" state for a genuinely sourceless server. Also:
   `stats.feeds` always lists the built-ins even while a custom feed is serving, so it must not be used
   to name the configured feed — the panel derives that from `context.news_url` plus each item's own
   `source` host.
5. **A real app defect, reported by the news workstream and structurally confirmed by me:** the setup
   wizard's **Skip** button posts the page's in-memory `S.config` back
   (`finishWizard({skip:true})` → `POST /api/control/engine/restart|start` with `S.config`), so a config
   changed elsewhere since page load is silently reverted — in the live run it flipped
   `context.news` back to `false`. Not fixed here; it is one 'Load before you save' change in `guide.js`
   and belongs in its own small pass.

**The 3 `client error:` lines in the sandbox log are mine, not the panels'**: timestamps 22:35:58–59,
i.e. the window when `watchlist.js`/`news.js` were wired into `index.html` before their files existed
(§13) — `failed to load` ×2 plus the downstream `Cannot set properties of null`. After the files
landed the same log has none, and both panels render.

**Still open:** Fundamentals and Options (phase 5's other two). Both need a data decision before a panel
is worth building — a fundamentals source, and a real options feed for Greeks/IV (dxFeed class). That
question is with the user; nothing was built speculatively.


### 24. 2026-09-15 late — Phase 5 complete: Options (Deribit) and Fundamentals (EDGAR + CoinGecko)

Nothing committed — HEAD `b2ff4ee`. Final gates, **all run by me on the wired tree**: full suite
**467 passed / 2 skipped**, `AUDIT CLEAN`, `options.selftest.js` 21 ok, `fundamentals.selftest.js` 18 ok,
`test_options.py` 27 passed, `test_fundamentals.py` 33 passed.

**Wiring applied in one pass** (the six hunks the Fundamentals workstream reported, plus the correction it
could not have known about): `index.html` nav item + section + script tag (both panels), `JS_FILES` for
both modules, and — the part that would otherwise have turned the audit red — the audit's hardcoded route
table now also scans `desktop/edgar.py`. The fundamentals router is mounted at **app level** in
`launcher.py` (a nested `include_router` inside the control router both breaks `test_live_bridge.py`'s
`{route.path for route in router.routes}` comprehension and inverts the URL, per the Options workstream's
own defect note; the Options panel's routes are plain `@router.get`s in `api.py` instead, which is why its
paths read `/api/control/deribit/…`).

**My own live render** (sandbox 8094, real network, then stopped): app boots 28 views / 29 nav, no error
banner. Options: 11 expiries, 21 strike rows, sub line *"polling 20s via the shared bus · BTCUSDT → BTC
16SEP26 · ±10 strikes around 76269 · 21 strike row(s), 42 quoted side(s)…"*. Fundamentals on BTCUSDT: the
CoinGecko branch — 5 rows, *"BTCUSDT · CoinGecko · Bitcoin · rank #1"*, first row `Rank #1`. The EDGAR
branch was verified live at the module level (Apple's real FY2025 10-K: revenue 416 161 000 000 USD, EPS
7.46, filed 2025-10-31) but not yet rendered in the DOM, because the sandbox's active symbol is crypto.

**Defects the workstreams found and fixed** (all pinned by their gates): the Options panel stuck on
"Loading…" when the active symbol has no chain (fixed in `rekey()`); Deribit lists **no SOL options** (the
brief's assumption was wrong — SOL is a recognised currency with an empty chain, a third honest state);
Deribit has no batch ticker endpoint, so the ladder is windowed ±10 strikes and pooled (≈2 req/s while
open, stated in the module header); `router.include_router` in FastAPI 0.141 breaks a pre-existing status
test; strike spacing is not uniform and the ladder never assumes a step; CoinGecko's ticker ≠ id
(POLUSDT → `polygon-ecosystem-token`, not the migrated `matic-network` husk that answers zero); EDGAR's
`fp: FY` is not a period length (90-day facts filed as FY must be dropped); a refusal is never cached as
an answer.

**Not verified, plainly:** neither panel has been run inside the frozen `.exe`/pywebview window; terminal
mode re-parenting of the two new sections is untested; the Options detail line did not surface in my own
probe click (the workstream's live run did show it with real Greeks — mark 0.0959 · IV 93.28 % · Δ +0.991 ·
Γ 0.000 · Θ −37.619 · V 0.807), which I put down to my selector rather than a gap, but I did not re-test it.


### 25. 2026-09-15 late — the seven-item sweep (what closed, what did not)

Gates at the end of this pass, all run by me: suite **473 passed / 2 skipped**, AUDIT CLEAN,
`watchlist.selftest.js` 15 ok, `shell.selftest.js` 22 ok, `options.selftest.js` 21 ok,
`fundamentals.selftest.js` 18 ok. HEAD `b2ff4ee`, nothing committed.

**Closed:**
1. **Wiring guards** (`test_wiring.py`, now 6 tests): every `/desktop` script tag must resolve to a file
   (vendor subfolders included), every `data-view` needs a nav item and a module that claims it, the four
   new panels must stay wired, `bus.js` must load before them, every panel must be in the audit's
   `JS_FILES`, and **every panel must scope its section lookup to `.view[data-view=…]`**. The last guard
   caught a real bug on its first run: `watchlist.js` matched the **nav button** (line 47) instead of its
   section (line 711), so in terminal mode — where no nav button is ever `.active` — the panel thought it
   was off-screen and paused. `platforms.js` had the same latent lookup; both are fixed.
3. **The wizard's stale-config write** (`guide.js`): it now snapshots the config at open and, before
   writing, re-reads the live config and merges three ways (keys the wizard edited win; every other key
   takes the live value). Proven live both ways: a `context.news=false` set by curl survived a real Skip
   click, while a key walked through the wizard (`context.news=true`) won over the live value.
2. The **Options detail line** is confirmed populated (a data cell click → mark 0.0976 · IV 90.30 % ·
   Δ +0.994 · Θ −25.656 · V 0.568 · OI 0, agreeing with the ticker route). The earlier "empty" reading was
   the probe's own fault: `#optionsBody tr` returns the `<thead>` row.
5. **Terminal-mode re-parenting**: five new panels in widgets, a second tab, away-and-back — every panel
   re-booted with no stuck "Loading…", bus channels 2 → 0 (hidden panels release) → 2, and the classic
   round-trip restored all 28 sections in the exact original order.
6. **The frozen app is rebuilt**: `dist/ModFlowOrderFlowAnalysisSuite/` (note the app name, not the old
   `OrderFlowAnalysisPro` folder, which is stale) now carries all four panels plus
   `data/bookmap_addon/ofap-bridge.jar`, the exe serves modules byte-identical to source, and a real
   window opened.
4. **The real pywebview window** shows both new panels with live data (Options: 21 strikes, real IV/Δ;
   Fundamentals: CoinGecko rank/mcap/supply) — but it cannot be driven programmatically: WebView2 exposes
   no CDP port here, and desktop clicks were denied by the approval gate, so no click-through in that
   window is verified.

**Open, with the fix known and the evidence recorded:**
* **Terminal mode leaves legacy panels empty** (measured on tape; the same mechanism applies to orderflow,
  depth, signals, performance, strategy, chart): those instances are built lazily by `ensurePanel()` in
  `ui.js`, which only the classic `showView` path calls — the terminal wrapper bypasses it. Calling
  `ensurePanel('tape')` by hand made the tape widget paint live prints immediately. The fix is one guarded
  call (`window.ensurePanel?.(view)`) at the point the shell mounts a section into a frame; it is NOT
  applied yet, because a blind insert into `shell.js` could not be verified in the time left.
* **`POST /api/control/config` writes over DEFAULTS, not as a patch** (`save_config` deep-merges
  `default_config()` with the body), so a partial post silently resets every key it omits. This also
  bounds the wizard fix above: its three-way merge is per **top-level** key, so a live edit to a different
  leaf inside a block the wizard touched is still reverted (`context.fear_greed` did). Worth a doc line in
  the API surface and, later, either a real PATCH or per-key merge.
* **Cosmetic, recorded not fixed:** the Fundamentals circulating-supply cell prints a literal
  `<span class="dim">of 21.00M max</span>` (a fragment built as text then escaped — `fundamentals.js`
  ~381-393), and the Options gamma shows `0.000` for a venue gamma of `1e-05` (3-decimal formatter).
* Step 7's optional items stand: the Watchlist's demo-list source when the engine is idle (use
  `/api/control/bootstrap` for the literal enabled list), per-panel bus adoption, and a commit boundary —
  67 dirty paths, HEAD still `b2ff4ee`.


### 26. 2026-09-15 — the last two fixes, applied and proven

**A. Legacy panels as terminal widgets** (`shell.js`, `buildFrame`): those instances are created lazily by
`ui.js ensurePanel()`, which only the classic `showView` path calls — the terminal wrapper never ran it, so
a tape/orderflow/depth/signals/performance/strategy/chart widget sat empty (measured: 0 children, `S.inst`
`[]`). A guarded `window.ensurePanel(view)` now runs once the section is in its frame (idempotent, so it is
a no-op for panels that build themselves from their observer). **Proven live**: after `openWidget('tape')`
the frame's container went 0 → 1 child carrying the tape's own *Min Size* scaffold, and a second legacy
panel (`depth`) built its instance the same way. Not re-measured per panel: orderflow, signals, performance,
strategy, chart — same mechanism, same call site.

**B. `POST /api/control/config` patches** (`config_store.merge_config` + `api.put_config`): the write merged
the body over the DEFAULTS, so a partial POST reset every key it omitted. **Proven live** on a sandbox:
after posting `{"search": {"default_view": "chart"}, "context": {"news": false, "fear_greed": false}}`, a
second post of `{"ui": {"banner_dismissed_alpaca": true}}` read back `view=chart, news=false,
fear_greed=false, banner=true` — before the fix the first three would have gone back to factory values.
`save_config` keeps its whole-block semantics **on purpose**: the layout delete path removes an entry by
writing the remaining block, and a disk-based merge would resurrect the deleted key (that is exactly how
`test_layouts.py::test_duplicate_rename_and_delete` failed on the first attempt at this). Reset is
unchanged. Pinned by two tests in `test_config_store.py`.

Gates after both: **475 passed / 2 skipped**, AUDIT CLEAN, `shell.selftest.js` 22 ok. HEAD `b2ff4ee`,
nothing committed.


### 27. 2026-09-15 — the three remaining fixes: two proven, one NOT fixed

Gates after this pass: **475 passed / 2 skipped**, AUDIT CLEAN, `watchlist.selftest.js` 15 ok,
`options.selftest.js` 21 ok, `fundamentals.selftest.js` 18 ok. HEAD `b2ff4ee`, nothing committed.

**Fixed and proven.**
* **Fundamentals supply cell** (`fundamentals.js`): the one value this panel builds as markup carries an
  explicit `r[3] === true` flag; everything else stays escaped. Live: the cell now holds
  `20.08M BTC <span class="dim">of 21.00M max</span>` — a real child element (`elementChildren: 1`), no
  literal tag in the text.
* **Options greeks** (`options.js fmtGreek`, shared by gamma/theta/vega/rho): a non-zero value below a
  milli-unit renders `n.toExponential(2)` instead of rounding to `0.000`, because "no gamma" and "1e-05
  gamma" are different statements. Pinned in `options.selftest.js` (`fmtGreek(0.00021) === '2.10e-4'`,
  `fmtGreek(1e-5) === '1.00e-5'`, exact zero still `'0.000'`). NOTE: the live click-through was **not**
  captured — the probe waited 6 s inside one `js()` call and the harness times out at ~5 s. The rule is
  test-pinned, not eyeballed.

**NOT fixed — stated plainly.** The watchlist's "configured instruments" rows do not appear.
* What is right: `config.instruments` really is the instrument **list** (50 objects after the test
  instrument was added), not a settings block with a `symbols` key — the reader now handles both shapes and
  was verified against the live bootstrap response.
* Correction, same session: the cause was the 2 s poll beat — `setInterval(() => { void loadStatus(); })`
  reloads only the engine status and never called `refresh()`, the helper's sole caller. The beat now runs
  `loadStatus → refreshPlaceholders → render`. Live re-check pending (the ZZZTEST recipe above); this
  paragraph replaces the "NOT fixed" verdict below, which was written before the loop was read.
* What failed: `configuredSymbols()` was never reached in practice. The live sandbox kept showing 45 demo
  rows with **zero** configured rows even after a configured instrument the demo list does not carry
  (`ZZZTEST`) was posted into the config — so the panel's poll path does not go through `refresh()`, which
  is the only caller of the new `refreshPlaceholders()`. The helper is therefore inert. Next step (one
  look, not a guess): find the actual poll loop in `watchlist.js`, call `refreshPlaceholders()` from it, and
  re-run the ZZZTEST check. Until then this is an open item, not a delivered one.


### 28. 2026-09-16 — the bus refactor, and the two delivery-layer defects it exposed

The refactor (child pass): 5 independent pollers across 4 modules collapsed onto **3 shared channels** —
CVD series 5000 ms (market-pressure + atlas.js), tape series 5000 ms (atlas-v2 + atlas.js trackers), engine
status 2000 ms (the shell + watchlist, which were the same URL asked twice at 60 req/min). Measured on the
wire, 45 s windows: CVD 27.8/min → 12.0/min, tape 26.7/min → 12.0/min, status 60.0/min → 30.0/min with one
channel and two subscribers. Everything else was deliberately left: unique-dataset pollers, DOM/UI timers,
or pairs whose URL params differ so they are different channel keys. New gates: `market-pressure.selftest.js`
(12 checks), `test_market_pressure.py` (8 tests).

**Defect it found, mine, fixed here — the worst kind: a silent freeze.**
`bus.js install()` never released a settled request (`inFlight.delete(key)` existed on the error and
non-JSON paths but not the success one), and `canon` drops cache-busters, so the first answer for a wrapped
URL stood in for that URL for the life of the page. With the shipped configuration
(`install(['/api/atlas/', …])` — four prefixes) a CVD panel counted 7 fetches while the server logged **0**,
and its stamp froze. Fixed: the key is released as the body lands; callers that joined while it was in
flight already hold the promise, so nobody is cut off. **Live now: `inFlightRequests` 0, fetches 19 → 37
across 13 s, channels answering.** Pinned by a new `bus.selftest.js` check (12 ok) — the old check pinned
only the concurrent case, so it would have kept passing through the freeze.

**Second defect, same pass — a closed widget kept polling.**
`shell.js releaseFrame()` returned the section to Classic but left `.active` on it: measured
`.active true, offsetParent null, 0x0, in no frame`, so every panel of that view — and now its bus
channel — kept polling for a view nobody was looking at. Fixed: the class is cleared on the return trip.
Live: heatmap widget before `{active: true, inFrame: true}` → after `{active: false, inFrame: false}`, and
the channel count falls with it.

**Third, cosmetic, left:** the status bar's bus chip repaints on shell events only, so it can lag a channel
that opens on a view switch.

Gates after all of it: **483 passed / 2 skipped**, AUDIT CLEAN, bus selftest 12 ok, shell 22 ok,
market-pressure 12 ok, watchlist 15 ok, options 21 ok, fundamentals 18 ok. HEAD `b2ff4ee`, nothing committed.

Still open from §27: the watchlist's configured-instrument rows were wired to the 2 s poll beat after that
note was written and have not been re-checked live (the ZZZTEST recipe is in §27).


### 29. 2026-09-16 — the bus chip lag (the "cosmetic" from §28)

Fixed, and it took three findings rather than one:
1. `bus.js` never announced channel transitions — it dispatched `ofap:bus` once at boot and nothing else, so
   no observer could know a channel had opened or closed. It now announces `open`/`close` with the channel
   key and the live counts (guarded: the module still loads where there is no document).
2. The first wiring of the shell's listener landed inside `applyTab()`, which does not run at boot — the
   listener was never registered until a tab switch. `watchBus()` is now idempotent (`S.busWatcher`) and is
   called from `paintStatus()`, which runs on the first paint.
3. The repaint was queued behind `requestAnimationFrame`, and in a headless page that callback never fired —
   the queue flag stayed set and the chip went permanently stale. The listener now paints directly; a
   channel transition happens a handful of times per view switch, so coalescing bought nothing and cost
   correctness.

Verified live on a sandbox with the page freshly loaded: chip `bus: 1 sub · 1 ch · 2 fetches (1 saved)` →
open the CVD view → `1 sub · 2 ch · 2 fetches` (telemetry: 2 channels) → back to Overview →
`1 ch · 8 fetches` (telemetry: 1 channel) → a terminal round-trip → `1 ch · 12 fetches`. The chip follows
the bus, not just shell events.

**Found while proving it, not fixed:** the chip's `sub` number and `telemetry().subscribers` disagree at the
same instant — measured chip `1 sub · 2 ch` while telemetry reported 3 subscribers. Two channels each with
listeners cannot hold one subscriber, so the bus's internal counter counts something else (channels with a
listener) than what `telemetry()` reports (subscriber references). One of the two is mis-named; worth a
one-line reconciliation so the number means one thing.

Gates: 483 passed / 2 skipped, AUDIT CLEAN, shell selftest 22 ok, bus 12 ok.


### 30. 2026-09-16 — the working tree is committed (local only, nothing pushed)

`master` moved off `b2ff4ee` for the first time, in seven commits grouped by area — not by phase, because
`api.py`, `ui.js` and `index.html` were each touched by several phases and a phase split would have needed
`git add -p` to leave a file half-staged. Nothing here is pushed: `origin` is
`github.com/mahmoud20138/OrderFlow-Analysis-Pro` (the original project), and the branch is 7 ahead of it.

  `4b142f1` docs: session handoff, terminal/Quantower plan and audit report                  (58 files)
  `639dd00` feat(desktop): terminal mode, panels, platform realm                             (76)
  `d848421` feat(data): Alpaca and DTC feeds, enums, Bookmap reader and add-on                 (9)
  `4776ac0` feat(atlas): analytics package and its gates                                      (23)
  `bd3cbd5` test: the suite, fixtures and testdata                                            (54)
  `a5d9909` chore(tooling): UI audit, exe packaging, workflows, assets                        (10)
  `e967d02` chore: earlier-session work in settings, dashboard, analytics and data            (15)

The last commit is the pre-existing uncommitted work from earlier sessions (~1,900 changed lines in
`config/settings.py`, `main.py`, `dashboard/`, `analytics/`, `data/`, README, CONTRIBUTING), kept in its
own commit so it stays separable from this work. Identity is repo-local: `ModdySwag
<ModdySwag@users.noreply.github.com>` — no real address, and nothing global was changed.

Verified after the last commit, against the committed tree: **483 passed / 2 skipped**, AUDIT CLEAN,
`git status` empty, and no `*.db`, `*.log`, `.env`, `dist/`, `build/`, `.venv/` or `__pycache__` in the
tracked files (largest tracked files are two docs screenshots and the vendored lightweight-charts bundle).

Open, unchanged by this: the chip's `sub` count vs `telemetry().subscribers` disagreement (§29), the
watchlist's configured-instrument rows (§27) and the two cosmetics in §25.


### 31. 2026-09-16 — report1.txt reconciled, and the upgrade plan written

The owner asked for a plan of action built from `report1.txt` (the audit comparing `ai prompt.txt` to the
build). It was re-verified against the tree before planning, because it was written before the engine view's
wiring landed and two of its three headline gaps no longer exist:

| report1 said | the tree says |
|---|---|
| no DOM tooltip panel consuming `state.hover` | `ofx-view.js:492` → `paintTip` (:401, `#ofxTip`) + `paintReadout` (:320, `#ofxReadout`, the full metric set) |
| no "snap to live" sparkline widget | `#ofxSnapFloat` + `#ofxSpark2` (`index.html:248`), `paintSpark` (`ofx-view.js:277`), shown in historical mode only, click = `snapToLive()` |
| no lambda control; no perf HUD | `#ofxLambda` (`index.html:230`); the stats line (`ofx-view.js:256`) carries frames · EMA · p95 · max · LOD · col width · levels |
| `footprint.js` looks dead — remove | it is `orderflow_system/dashboard/static/footprint.js`, still loaded by `index.html:764` and built by `ui.js ensurePanel('orderflow')` — the keep/retire call is sweep R7, not a delete |

What report1 had right and is still open: `hover()` costs O(prints + heat cells + bars) per mousemove
(`ofx.js:1778` — and `:1774` re-scans the whole depth matrix, `:1763` re-sums CVD from bar 0, neither of
which the audit saw); `cell.peak`'s flat 0.92 ghost (`:1150`); the stacked-zone projection and
imbalance-glow cosmetics; `carry_forward` has no on-screen indicator. One new compliance find:
`desktop/api.py:1525` is the only `hermes` match in source (non-negotiable #7).

Plan: **`docs/UPGRADE_ACTION_PLAN.md`** — P0 trust pass (the three unverified visuals, watchlist rows, bus
counter, sweep R2/R3, the hermes string), P1 the interaction canon and spec alignment (theme/token layer
first — `atlas.css` holds zero `--of-` tokens today), P2 measured performance, P3 backend/packaging/
deferred, each with its gate, the design principles the ordering follows, and the evidence appendix.
Gates at writing: 483 passed / 2 skipped, AUDIT CLEAN; selftests ofx 119, shell 22, bus 12, links 10,
watchlist 15, news 17, options 21, fundamentals 18, market-pressure 12, intent 7, study-api 45,
search-ops pass.


### 32. 2026-09-16 — the P0 trust pass from the upgrade plan (all six, with evidence)

Run on a sandbox (`ofap_p0_sandbox`, a copy of the §27 state so `ZZZTEST` is in its instrument list,
port 8093, engine live on Bybit BTCUSDT). Every line below is a measurement, and the gate block at the
end was run after all of it.

| P0 item | Result | Evidence |
|---|---|---|
| **P0-1** the three unverified visuals (§2) | **Seen** | *Stacked zone*: zoomed past the 54 px label gate, the draw-call capture holds `STACK 3L`, the per-bar band `rgba(86,214,255,0.12)` at 62×26 px and 11 projected row bands `rgba(64,224,255,0.18)`. *Thermal ramp*: palette stops `rgb(26,38,58) → rgb(96,70,58) → rgb(186,110,46) → rgb(232,176,84) → rgb(255,244,214)`; the same hottest cell (col 1, size 189) reads `255,236,187,179` on classic and `251,178,73,179` on thermal. *Trace line*: `#ofxTrace` at the cursor's price, tip and readout populated, note `on the ladder` with the row highlighted — and `outside the drawn ladder levels`, with no row, when 140 points away |
| **P0-1 exposed three defects, all fixed** | **Fixed** | (1) The ladder never emitted `data-price` — the attribute `ofx-view.js:461` queries — so no row could ever match, in any view (`orderbook.js`, pinned in `test_wiring.py`). (2) A class toggled by the consumer was wiped by the ladder's next rebuild; the highlight is now state the ladder re-applies in its own render (`setTrace`, verified still present after a poll). (3) `nearest(prices, null)` accepted any distance, so a cursor 41 points off a 15-level ladder read `on the ladder`; the match is bounded by one grid step now |
| **P0-2** watchlist configured rows (§27) | **Fixed, proven both ways** | Engine **stopped**: 45 demo rows + 7 configured rows, incl. `ZZZTEST — ticks — vol — Δ — — configured`, sub line `the server is answering with its demo list, not your feed · 7 configured instrument(s) with no feed`. Engine **running**: 1 row, source `engine`, 0 configured rows. Root cause, measured: `refreshPlaceholders()` was reached only from `refresh()` and the no-bus timer — never from the bus beat — and the bootstrap read called a bare global `api()` that exists only inside a real page, so the read had never worked under test. Selftest 15 → 17 |
| **P0-3** bus chip vs telemetry (§29) | **Fixed** | `announce()` dispatched `subscribers: state.subscribers` — a field this module has never had, so every `ofap:bus` event carried `undefined`, and the one number nobody could verify was the one that appeared to disagree. One `subscriberCount()` now feeds `telemetry()` and the event, and the open event fires after the join. Live: event `{action:'open', channels:2, subscribers:2}`; chip, `summary()` and `telemetry()` agree on subscribers and channels at the same instant. (The chip's *fetch* count still lags between repaints — it is a snapshot, by design.) Selftest 12 → 13 |
| **P0-4** order-book integrity (sweep R3) | **Implemented** | Bybit's `u` is tracked per symbol: duplicates and reorders are dropped, a gap marks the book stale, drops the deltas that follow and re-subscribes for a snapshot (`OrderbookSnapshot.stale`, `book_health()`, `live_status()["endpoints"]["orderbook"] == "stale"`). 4 new tests (`test_book_integrity.py`). Live: 25 s of engine, `orderbook: live`, 0 gap warnings, 684 ticks — no false staleness |
| **P0-5** broadcast backpressure (sweep R2) | **Implemented** | Per-client bounded queue + writer task; nothing is written under the manager's lock; a full queue trims the oldest for `tick/orderbook/delta/stats` only and never for `signal`; a write that times out drops the client. 5 new tests (`test_websocket_backpressure.py`). Live: WS accepted, client count 1, no timeouts or tracebacks in the log |
| **P0-6** `hermes` in source (non-negotiable #7) | **Fixed** | `desktop/api.py:1525` comment reworded; `grep -ri hermes` over source is 0 matches. (`dist/` matches are CPython's own `unicodedata.pyd` — noted so the gate is not misread.) |

Gates after everything: **493 passed / 2 skipped**, AUDIT CLEAN, `node --check` on every touched JS,
selftests ofx 119 · shell 22 · bus 13 · links 10 · watchlist 17 · news 17 · options 21 · fundamentals 18 ·
market-pressure 12 · intent 7 · study-api 45 · search-ops pass; no `client error:` lines in the sandbox
log. New tests: `test_book_integrity.py` (4), `test_websocket_backpressure.py` (5), one wiring guard.

What the pass did **not** cover, stated plainly: the stacked-zone band was seen at one zoom level (not
across zoom/resize/symbol change); the tape's scroll across a rebuild and 4K at Windows 150 % are still
unverified (§2), and they were not part of P0. The `stale` state has not been exercised against a real
venue gap — the unit tests drive the handler, the live run shows no false positives.

Next per the plan: **P1-1, the theme/token layer** (its grep gate is cheap and every colour decision
below it needs the tokens to exist).


### 33. 2026-09-16 — P1-1: the theme and token layer (the brief's gate at zero)

Workstream A of the agent brief, delivered as one pass.

**What landed**

- **One token block** (`atlas.css`): ~110 tokens declared as rgb triples (`--of-bg-rgb: 10,14,22`) with
  the solid form beside each (`--of-bg: rgb(var(--of-bg-rgb))`), because the shell leans on translucent
  overlays and `rgba(var(--of-steel-rgb),.35)` themes while a hard-coded `rgba(120,150,190,.35)` cannot.
- **Every raw colour in the shell converted onto it** — 117 hex literals and ~170 `rgba()` literals
  across `atlas.css`, `ui.css` and `modules.css`. ui.css's own small token block became an alias block
  (`--bg-panel: var(--of-surface)`, …) so the ~1000 lines of existing rules became theme-aware without
  being rewritten. A script did the conversion and aborts on any unmapped colour, so nothing was
  silently missed.
- **`themes/`**: `dark.css` (the anchor), `light.css`, `contrast.css`, `accents.css` (the eight Windows
  accents — cobalt, teal, green, lime, amber, orange, magenta, violet), `density.css`
  (comfortable 32 / compact 26 / dense 22, all on `--of-row-h`; the row rules read the token, so a
  density is a number, not a rewrite).
- **`theme.js`** + an inline `<head>` script: the appearance is `data-theme` / `data-accent` /
  `data-density` on `<html>`. The config (`ui.theme`, `ui.accent`, `ui.density`, clamped on write) is
  the record; localStorage is only the **pre-paint mirror**, so the first paint is already the right
  theme and the config wins where they disagree (verified below).
- **Settings → Appearance**: three selects, wired through the intent arbiter's write queue, so a user
  flipping through them writes once.
- Guards: `test_wiring.py` gains the appearance guard and *the raw-colour guard* (the brief's grep as a
  test); `test_config_store.py` pins the three defaults and their clamps; `audit_ui_refs.py` audits
  `theme.js` with every other module.

**The brief's gate** — `grep -nE '#[0-9a-fA-F]{3,8}\b' atlas.css | grep -v -- '--of-'` → **0 lines**.
Also 0 for `ui.css`, `modules.css` and all five theme files.

**Measured live** (sandbox 8093; screenshots in `docs/screenshots/p11-theme-{dark,light}-{1024x640,2560x1440}.png`):

| state | body bg | ink | accent | `--of-row-h` | nav row | statusbar | doc overflow |
|---|---|---|---|---|---|---|---|
| dark (default) | rgb(10,14,22) | rgb(233,238,248) | rgb(79,140,255) | 32px | 32px | visible | 0 |
| light | rgb(242,245,250) | rgb(20,26,38) | rgb(79,140,255) | 32px | 32px | visible | 0 |
| light + dense | rgb(242,245,250) | rgb(20,26,38) | rgb(79,140,255) | 22px | 22px | visible | 0 |
| light + compact | rgb(242,245,250) | rgb(20,26,38) | rgb(79,140,255) | 26px | 26px | visible | 0 |
| light + dense + magenta | rgb(242,245,250) | rgb(20,26,38) | rgb(216,0,115) | 22px | 22px | visible | 0 |
| contrast | rgb(0,0,0) | rgb(255,255,255) | rgb(216,0,115) | 32px | 32px | visible | 0 |

The dark default renders exactly as it did before the pass (body bg `rgb(10,14,22)`, ink
`rgb(233,238,248)`) — a token pass that moves no pixel. At **1024×640** and **2560×1440**: document
overflow 0, status bar in view (41px, wrapped, at the small size), rail fills the height, 0
`client error:` lines in the log. Config-wins proof: with the localStorage mirror deleted and the page
reloaded, the config's `light`/`teal` came up (`source: 'config'`).

**Two decisions, on the record**

1. **The chart canvases keep their dark ground in the light shell.** The engine's palette
   (`ofx.js math.theme`) is drawn light-on-dark — grid, labels and ramps would be unreadable on a light
   stage. Re-theming the canvas palette is expression work (P1-8), not a token swap; the light shell
   themes the chrome, the panels and the readouts.
2. **The config stays the record.** `config_store` says browser storage is never the source of truth;
   that holds — the mirror never wins, it only paints first.

Gates after the pass: **496 passed / 2 skipped**, AUDIT CLEAN, `node --check` on every module, and all
twelve selftests unchanged (ofx 119 · shell 22 · bus 13 · links 10 · watchlist 17 · news 17 ·
options 21 · fundamentals 18 · market-pressure 12 · intent 7 · study-api 45 · search-ops).

Not covered, plainly: the engine's canvas palette is still its own dark set (decision 1); the
colour-blind ramps are P1-8; and the light shell has been looked at on the two sizes above only.

Next: **P1-2, the cursor-link spine** — one hover lighting the profile, CVD, depth, tape and imbalance
strip at once, surviving repaint, resize and a symbol switch.


---

## §34 — P1-2: the cursor spine adopted by six panels (2026-09-16)

**What this closes.** P1-2 asked for one hover lighting the profile, CVD, depth, tape and imbalance at
once, surviving repaint, resize and a symbol switch. The store (`cursor-link.js`) existed; what was
missing was *adoption* — only the engine published, and only the ladder listened.

**The module now carries the whole contract.** `move(price, timeMs, source)` / `clear(source)` /
`set` / `select` / `subscribe(fn) → unsubscribe` / `nearest(prices, tol)` / `step(prices)` /
`text()` / `badge(host)`, one `state` of `{price, timeMs, source, selection, at}`. Two of those are
new and both matter:

* **`unsubscribe`** — panels subscribe for their lifetime and a panel torn down in terminal mode has
  to let go; the old `subscribe` returned the callback and there was no way out.
* **`badge(host)`** — one badge element per host, driven by the one store, so six panels cannot
  disagree about what the cursor is on. The badge reads `price · time` with `tabular-nums`, is
  silent (`— · —`) when the cursor is clear, and takes the trace token's colour when it is not.

A field the caller did not mention is *not* a change: `move()` carries no `selection`, and treating
that `undefined` as "cleared" woke every panel on every mouse move (caught by the new selftest).

**Six panels, one price.**

| Panel | Publishes | Follows |
|---|---|---|
| Heatmap (`heatmap-pro.js`) | level + bucket under the pointer; clears on leave | draws the shared level as a line + price tag at both edges; repaints only when the drawn level changed |
| Depth ladder (`orderbook.js`) | the rung under the pointer | `setTrace(nearest)` — now with an early-out on an unchanged level |
| Tape (`tape.js`) | the print under the pointer (price + time) | marks rows at the cursor's price; rows carry `data-price`/`data-time`; re-applied on every insert, skipping the pass when the level has not moved |
| Profile (`atlas.js`) | — | marks TPO rows at the cursor's price; re-applied after each rebuild |
| Engine (`ofx.js` / `ofx-view.js`) | already did | already did; now carries the badge |
| CVD / trackers / heatmap / profile heads | — | badge |

**Script order is a build detail, not behaviour.** `atlas.js` and `heatmap-pro.js` load *before*
`cursor-link.js` in `index.html`, so their subscriptions and badges were silently skipped (found
live: 4 badges instead of 8). Both now wait for the module (`whenCursorReady`), and the live pass
shows 8/8.

**The gate, measured.** Hovering the heatmap canvas with a real pointer event:

* at **76332.12** — the engine's readout `cursor 76332.12 · on the ladder`; the ladder rung at
  `76332` traced; **10** tape rows marked (76332.3, 76332.2, 76332.2 …); four badges reading
  `76332.12 · 02:05:02`.
* at **76398.84** — **9** profile rows marked (76399.3 … 76398.4), `8/8` badges agreeing on one text;
  the engine says `outside the drawn ladder levels`, which is true — the ladder draws ~15 levels
  around the mid, the profile's published bracket is 76388.4–76411.6, and a panel that is not
  showing the level says so instead of inventing a match.
* Persistence: the same marks and the same price survived a **1366×900** resize and a forced
  `loadMarketProfile()` rebuild (both panels re-derive the mark from the store — canon #3).

Screenshot: `docs/screenshots/p12-cursor-spine.png` (the map carrying the shared level + badge).

**Decisions on the record**

1. **The cursor is transient; the pointer leaving the owning panel clears its claim.** Verified: a
   view switch away from the heatmap leaves every badge at `— · —` rather than a stale level. A
   *sticky* level (park it and walk to the ladder) is a selection, and that is P1-3's click model —
   two different intents should not share one state.
2. **A panel marks only what it draws.** Out-of-window hovers produce an explicit "outside the drawn
   ladder levels" note, not a nearest-row fudge.

**Not covered, plainly.** The CVD canvas and the imbalance strip carry the badge but no drawn cursor
line yet (they need the series→time index mapping, which belongs with P1-3's selection maths); the
sandbox has one symbol, so the **symbol-switch** half of the gate is unproven; and the terminal-mode
grid overlapped frames in the sandbox layout, which is why the four-panels-at-once pass was measured
in a 6-widget composition and the visual record is the classic view.

Gates after the pass: **496 passed / 2 skipped**, AUDIT CLEAN (now auditing `cursor-link.js` too),
`node --check` on every module, and all **thirteen** selftests green — the new `cursor-link` one at
**6 ok**, ofx 119 · shell 22 · bus 13 · links 10 · watchlist 17 · news 17 · options 21 ·
fundamentals 18 · market-pressure 12 · intent 7 · study-api 45.

Next: **P1-3, selection is measurement everywhere** — a drag over bars, a level, a time range or
markers yields the statistics strip, with the `selection` slot that P1-2 put in the store.


---

## §35 — P1-3: a selection on the engine is a measurement (2026-09-16)

**What this closes.** P1-3 asked for a drag over bars, a level, a time range or markers to yield the
statistics strip and an export, with markers remembered per symbol. The heatmap already had the
mechanism; the engine had none, and markers were session-only.

**The gesture.** Shift+drag on the engine stage boxes a time × price region. A plain drag still pans,
so nothing existing changed; the box is drawn on the live layer (`drawSelection`, above the crosshair
HUD), so it survives every repaint and camera move, and the outside dims rather than hides.

**The arithmetic is pure and pinned.** `math.selectionStats({bars, levels, prints, i0, i1, p0, p1})`
does the sums — volume, delta, buy/sell, prints (count + size), VWAP by size, largest trade with its
price, and the resting-depth change (last bar minus first bar, in the band). `math.selectionRange`
clips *and* orders the two cursor positions. Both are selftested in Node: the ofx selftest went
**119 → 134** checks. `OFX.selection()`, `OFX.selectionStats()` and `OFX.clearSelection()` are the
module's own surface; `legend()` does not carry them (the first attempt anchored on the wrong
`return { symbol: state.symbol,` and the methods landed on the legend object — caught by probing the
page, not by reading the diff).

**The strip and the file.** `ofx-view.js` paints `#ofxSelFloat` — its own line beside the stage, so a
hover repaint cannot wipe it — with volume, delta, buy/sell, prints, VWAP, largest and the resting
change, plus `Export CSV` and `Clear`. The export POSTs `/api/control/export/save` and the path the
server returns is printed on the strip's own note line. The strip is `pointer-events: none` with
`pointer-events: auto` on its two buttons: a measurement readout must not eat the gesture that makes
the next one (found live — the strip, sitting over the stage's bottom-left, blocked re-selection
through it).

**The gate, measured.** Shift+drag over the traded band on live Bybit data: a 4-bar selection at
76346.11–76461.95 read **volume 86.39, delta +14.58, buy/sell 50.48/35.91, resting +4.83**, and the
file landed on disk under the sandbox's exports folder —
`ofx-selection-BTCUSDT-20260915T165000.csv`, 22 lines: a header block (symbol, window, price band,
each figure, exported stamp) then one row per bar (ts, iso, OHLC, volume, delta) and a prints section.
A second export from the first pass (164900) is there too. Screenshot:
`docs/screenshots/p13-engine-selection.png`.

**The selection rides the shared cursor.** `OFAPCURSOR.select({t0, t1, p0, p1, bars})` — the slot P1-2
put in the store — so any panel can answer the window without knowing the engine exists.
`publish()` now distinguishes *not mentioned* from *explicit null*: `select()` carries no price, and
the old comparison treated that absence as "cleared", which would have wiped the cursor every panel
was reading. Pinned in `cursor-link.selftest.js` (now **7 ok**).

**Two defects found live, both fixed in the pass.**

1. **A one-sided index clamp.** Dragging from mid-stage to the right edge resolved to `i0 = 11,
   i1 = 4` — the start index was clamped only at 0, the end index only at `bars.length - 1`. An
   inverted range reads as "the strip measures nothing". `math.selectionRange` now clips both ends
   and orders the pair; five selftest checks cover past-the-edge, reversed, negative and empty-data
   drags.
2. **The strip blocked its own gestures** (above).

**A token read that should have been a triple.** `--of-trace`/`--of-trace-2` exist only as `-rgb`
triples, so `color: var(--of-trace-2)` on the badge was invalid at computed-value time (it fell back
to inherited ink) and the heatmap's canvas cursor line never left its hard-coded fallback. Both now
build the colour from the triple.

**Markers are remembered per symbol.** New store block `markers` (`{SYM: {markers: [{price, bucket,
size, note}]}}`), sanitised in `config_store` (price finite and positive, bucket/size finite, note ≤
120 chars, 500 per symbol, an empty list leaves no slot, the key upper-cased and clamped) behind
`GET/POST /api/control/markers`; the route answers with the block the store *accepted*. The panel
loads them once per symbol on its own poll and saves on mark/clear, and a stored row (data space,
never pixels) is placed back on the map by a **bounded** nearest — a marker whose price is outside the
drawn rows is not pinned to the edge row pretending to be there.

**`window.prompt` is gone from the mark action.** The packaged WebView is not guaranteed to render
one, and a Mark button that silently does nothing is worse than no button; the note is now a field in
the pro toolbar (cleared after each mark), with a `clear markers` button beside it.

Measured live: `POST /api/control/markers` stored the valid row and dropped a junk price; the panel
restored **2** rows after a reload — the one inside the drawn range placed at y=121, the one 67 points
outside it left unplaced and honest.

**Not covered, plainly.** The plan's "extend it to walls" half is not done: the heatmap's region
stats and CSV still carry cells and markers, not the fresh-walls table (**open**). The tape buffer
holds only the last few seconds while the footprint payload publishes closed bars, so a selection over
closed bars legitimately holds no prints — the strip now names that on its own line ("tape buffer
02:24:54–02:24:55 is outside the selected window (closed bars only)") instead of leaving a dash
that reads as a bug. The CVD canvas and the imbalance strip still carry the badge without a drawn
cursor line, and the symbol-switch half of P1-2's gate remains unproven (one symbol in the sandbox).

Gates after the pass: **504 passed / 2 skipped** (`test_markers.py` adds 8), AUDIT CLEAN, ofx selftest
**134 ok**, cursor-link selftest **7 ok**, every touched JS parses.

Next: **P1-4, strips — keyboard stepping and click-to-locate completion** (brief C).


---

## §36 — P1-4: the reader's hands on a strip (2026-09-16)

**What this closes.** `strips.js` could hold a reader's place but not move it, and a print could not
be acted on. Now the strips have keys and a locate.

**Keys.** ArrowUp/ArrowDown step one row (measured 24 px on the tape), PageUp/PageDown a screenful,
Home/End jump to the newest/oldest end. The handler is a document-level capture listener guarded like
the shell's own hotkeys (never while a field has focus; only when a strip is hovered or the event came
from inside one), and it `preventDefault`s what it uses. **No Escape binding on purpose**: `shell.js`
owns that key (menus, restoring from maximise), and a strip stealing it would close the wrong thing —
the release paths are the chip's own click and Home. Stepping engages the hold deliberately, so the
chip now shows even with nothing new to count ("↑ prints held · jump to newest"): a keystroke that
looked like it did nothing was worse.

**Pause on hover.** The gate's phrase, and it did not exist: a fast tape kept pulling rows out from
under a pointer parked on them — the same jump the module exists to prevent, one gesture earlier. While
the pointer is on a strip the follow branch counts arrivals and leaves the rows alone; when the pointer
leaves, a reader who never scrolled resumes following (their hover was transient) and a reader who had
scrolled keeps their place and their chip.

**Click-to-locate.** A click on any row carrying `data-time`/`data-price` publishes that print to the
shared cursor (source `locate`) and calls `OFX.seekToTime()` — the engine's new viewport seek, which
centres the bar containing that moment, clamps a live print to the newest drawn bar, and returns null
for a moment older than the session rather than inventing a place. The click also releases the hold:
the reader has picked the line they were reading.

**Three defects found live, and this is the interesting part of the phase.**

1. **"On the newest line" was measured in pixels, not rows.** `NEAR_BOTTOM_PX = 28` against a 24 px
   row meant a single ArrowDown step still read as "at the end": `step()` released the hold it had just
   engaged and the next arriving print followed, snapping the reader back by the very keystroke they
   used to escape. Measured: three steps landed at 48 px instead of 72. The epsilon is now at most half
   a row (`nearEnd()`), in both the scroll handler and the step.
2. **A scroll event decided against a re-resolved anchor, not its own scroller.** The tape's tbody is
   emptied for a frame while its rows rebuild; `scrollerOf()` then walked up to the PARENT and the
   parent's offset (0) read as "the reader is on the newest line", silently releasing the hold. The
   anchor is now sticky (`keepScroller()`: keep it while it is still the strip's own node).
   Both were found with a property trap on the strip's state that recorded a stack on every `held`
   transition — the stack pointed at the exact line, twice, after guessing had failed.
3. **The tape had its own auto-scroll and it fought the strip.** `tape.js` pins `scrollTop = 0` on
   every render and every batch ("pinned to the newest print"), which released every hold the strip
   engaged. Two owners of one offset. The tape now asks `OFAPSTRIPS.holds(el)` first and leaves the
   offset alone while a reader is parked; the strip's chip is the way back. (Same family as the
   scroll-anchoring fight recorded in the skill — the offset belongs to whoever the reader is
   interacting with.)

**The gate, measured live.** Hover the tape (spin paused, rows steady while prints arrive), two to
three ArrowDown steps → `top` 72 px, `held: true`, `pending: 1` after five seconds of live arrivals,
chip shown ("↑ 1 print · jump to newest"), `OFAPSTRIPS.holding()` 1, and the status chip reads
`✋ held — feed live · 1 tick/s · 1 strip holding your place`. A real click on a print row →
`locate: {price: 76223.9, time: 1789492506772, bar: 9, reached: 2}`, the cursor took that price and
time (`source: 'locate'`), the engine's viewport moved to bar 9, and the strip cleared: chip hidden,
`holding()` 0, offset back to 0. Screenshot: `docs/screenshots/p14-strip-held.png` (the held tape with
the located print marked and the status chip naming the hold).

**Files.** `strips.js` (keys, hover-pause, locate, the held chip, `holds()`, `math.stepTarget`),
`strips.selftest.js` (new: 9 checks on the step arithmetic and the ends), `test_strips.py` (new gate:
selftest green, registered with the audit, renderer-agnostic, no Escape binding, typing guard present),
`ofx.js` (`seekToTime`), `tape.js` (the ownership guard), `atlas.css` (the held chip).

**Not covered, plainly.** The locate path seeks the engine when its module is loaded, whatever view is
on screen; a strip whose rows carry no `data-time` (alerts, the log) has nothing to locate and says
nothing — the wiring for those is theirs to add. Stepping has been exercised on the tape only, and the
"one row" step assumes rows of a uniform height (a wrapped row steps by the first row's height).

Gates after the pass: **508 passed / 2 skipped** (`test_strips.py` adds 7), AUDIT CLEAN (now auditing
`strips.js`), strips selftest **9 ok**, ofx **134 ok**, cursor-link **7 ok**, all twelve others
unchanged, every touched JS parses.

Next: **P1-5, spec-alignment cosmetics redesigned as token-driven feedback** (ghost brightness by size,
imbalance-cell glow, and the rest of report1's minor list, each re-argued rather than copied).


---

## §37 — P1-5: the cosmetics, as feedback (2026-09-16)

Five items from report1's minor lists, each re-argued before it was built. The gate for the phase is a
live reading per item, so every one below carries what the running engine actually painted.

**1. Ghost brightness by size.** The heat pass stamped every live cell `peak = 0.92`, so a level that
was pulled left the same ghost whether it had held a wall or a rounding error — the picture asserted
all liquidity was equal. `math.peakAlpha(size, scale)` maps a cell's own density bucket (the same
`log1p` mapping `heatPalette` uses for colour) onto the ghost's starting alpha: floor 0.32, top 0.92,
`sqrt` between them. Live cells keep their full-strength stamp — the pass moved no live pixel.
Measured on live Bybit depth: 252 painted cells spread over **0.867–0.920 across 6 distinct peaks**
(under the old code: 1 distinct value), and a controlled pull on the real renderer — the window's
heaviest cell (153.43) peaked at 0.920 and a mid cell (69.2) at 0.871 — left two ghosts at exactly
those alphas. Selftested (5 checks): monotone in size, never below the floor or above the top, a
nonsense scale is 1 rather than NaN.

**2. Imbalance-cell glow, and the POC keeps the strong one.** The imbalance tint was a flat
`rgba(imBuy, .18)` fill on the text half. It now goes through `glowCell()`, which adds a glow in the
*imbalance* colour at a third of the POC's radius (`glowRadius × 0.35`, floor 3 px) — accent stays
scarce (§3.3), and the engine's own legend colour table supplies the colour. Measured live with a trap
on `fillRect`: **27 glowed cells in one window — 21 sell, 6 buy — all at blur 3.0**, against the POC's
`glowRadius` of **7.2** on the same stage. The screenshot shows the matrix still readable, which was
the clause that would have cancelled the item.

**3. The stacked-zone projection reads across the chart.** The projected bands went from
`0.10 + min(0.10, count·0.02)` to `0.12 + min(0.12, count·0.025)`, and each distinct zone now carries a
right-edge label where the band *ends* — "BUY 3L projected" / "SELL 4L projected" — deduped per pass so
the per-bar draw does not stack the same words. Measured live with a trap on `fillText`: the label
painted on every base pass in the window (`SELL 4L projected`, 3 passes), which is what "once per
distinct zone per pass" means.

**4. `carry_forward` is on the panel.** The depth map carries liquidity forward between windows; the
payload has said so all along (`carry_forward`) and nothing displayed it. The view now puts the flag on
the engine's state and its notes line: **"ghost liquidity carried forward — levels that left the drawn
window are still shown"**, measured live after setting `atlas.heatmap.carry_forward: true` in the
sandbox config and reading the panel's own note text — a mark whose explanation is only in the code is
a lie of omission (§3.6).

**5. The hidden-block count sits beside the min-block floor.** The engine already tallied
`blocksFiltered`; the count now prints next to the control that causes it (`#ofxHiddenBlocks`), on the
existing one-second stats tick: **empty at floor 0** (a filter that hides nothing says nothing),
**"nothing hidden"** with the floor at 5 and nothing in view below it, and it turns warning-coloured
with "N hidden" and a tooltip naming the floor when the filter *is* hiding executions. Measured live at
both floors; visible in the screenshot beside the field.

**A config-shape finding, on the record.** The engine's hub reads its depth-map knobs from
`atlas.heatmap` (`engine.py` hands it the atlas subtree), while `config_store`'s defaults also declare a
top-level `heatmap` block for the GUI. Setting `carry_forward` at the top level does nothing —
measured: the payload stayed `false` through an engine restart until the flag went in under
`atlas.heatmap`. Worth knowing before the next depth-map knob is added; the sandbox was cleaned back
to its original state afterwards (stray key removed, flag removed).

Gates: **ofx selftest 139 ok** (five new `peakAlpha` checks), pytest **508 passed / 2 skipped**,
AUDIT CLEAN (the new `ofxHiddenBlocks` id is referenced by the view and exists in `index.html`),
`node --check` on every touched module.

Next: **P1-6, the heatmap answers duration** — `wall_age` / `wall_durations()` as a held-time column,
an optional wall-age tint, and the 74/22 px plot insets promoted to one shared constant.


---

## §38 — P1-6: the heatmap answers duration (2026-09-16)

**What this closes.** The depth map knew how long each level had HELD (`wall_durations()`, and a
`wall_age` alert kind on the same streak) and the payload carried none of it, so a level defended for
ten minutes looked exactly like one that appeared a second ago — the map could only answer *how much*.

**One join, three readers.** `atlas/api.py` gains `attach_wall_ages(snapshot, heatmap)`: the walls the
map draws, each with `held_ms`, plus `wall_age_ms` (the engine's own threshold — the UI says "held"
with the engine's definition rather than inventing one). The walls table, the cursor readout and the
age tint all read that one shape.

**Where it shows.**

* **Fresh-walls table** — a fourth column, "Held" (`1.3 min`, `47 s`, `—` when the streak restarted).
* **The cursor readout** — `held 1.2 min` under the rest of the level's numbers, with `(wall)` once it
  has passed the engine's threshold. Nearest drawn price within one step, bounded like every other
  nearest in this app.
* **The age tint** — an optional `wall age` switch in the heat view's overlay row (remembered in the
  view's own storage, off by default): a warm wash on the rows whose level has held past the
  threshold, `0.10` at 2 min rising to `0.22` at 10 min, warm rather than one of the ramp's own
  colours so it cannot be read as density.
* **One shared inset constant** — the 74/22 px plot insets were written twice (the map's `axisR/axisB`
  and the overlay's `geom()`); they are now `HEAT_INSET` in `atlas.js`, exposed as
  `window.OFAPHEAT_INSET`, and `heatmap-pro` reads the map's numbers with the old ones only as a
  fallback. A second copy is how a map and its overlay drift apart.

**Two `window.prompt` sites removed on the way (the P1-3 lesson, same file).** The alert tolerance and
the hold-alert's minutes were asked for with `window.prompt`, which the packaged WebView is not
guaranteed to render — a button that silently does nothing. Both are fields beside the alert buttons
now (empty = the default: two drawn price steps, two minutes), and the tooltips name the defaults.
One defect in my own first cut, found by running it: an empty field read as `Number('') === 0`, which
created a rule with `at_tol: 0` (fires only at the exact cent) — an empty field now means "use the
default". Three more `window.prompt` sites remain outside this phase (the drawing text tool at
`drawings.js:365,417` and the workspace-name prompt at `menubar.js:557`); they need their own in-place
affordances and are **open**.

**The gate, measured.**

* The payload's walls carry `held_ms` and `wall_age_ms: 120000` (curl), and the table rendered real
  holds on live data: `1.3 min`, `1.7 min`, `47 s` across three walls in one window.
* The cursor readout on a held wall read `held 1.2 min`.
* The tint's arithmetic is exact (`0` below the floor, `0.10` at 120 s, `0.145` at 300 s, `0.22` at
  600 s and above), and on the real canvas a wall given a 5-minute hold painted `rgb(255,193,117)` on
  its own row while six rows away stayed `rgb(0,0,0)`.
* The alert: created from the selected level through the new fields —
  `hm-BTCUSDT-77148_72-101555`, kind `wall_age`, `{min_size: 0.504, at_price: 77148.72, at_tol: 3.96,
  min_age_s: 120}`, channel `ui` — "fires only at that level", and the scope is enforced by the
  evaluator generically (`atlas/alerts.py:179-182`) and pinned in `test_wall_age.py`
  (`test_rule_bound_to_a_price_fires_only_there`: 100.0 fires, 103.0 does not, 100.4 does, no price
  means no evidence). It was then deleted through the route (200) and the list read back: 16 rules, no
  `hm-` left.
* **A live 2-minute hold did happen, and the engine said so.** A 20 s poller caught the engine's own
  event: `{kind: wall_age, price: 76800.0, size: 3.538, detail: "held 2.4 min", direction: ask}`. Two
  honest notes about it: the payload's `events` list carries the last 120 events (a couple of minutes
  of pull/stack churn), so a wall_age event rolls out of it quickly — a later query shows none, which
  is why the poller existed; and the Held *column* covers the 12 heaviest walls (`wall_prices(top=12)`),
  so a held level outside that set shows its age in the engine's event list rather than the table
  (76800.0 was not in the top 12 at the time). The level-bound rule did not fire for that unrelated
  event (0 alerts matching the rule), which is the "at that level only" half; its own firing at its own
  level was not observed while it existed, so that last step rests on the evaluator's pinned scope
  rather than a live alert.

Gates: pytest **509 passed / 2 skipped** (the new `test_wall_ages_ride_the_payload_the_map_draws`),
AUDIT CLEAN, `node --check` on every touched module.

Next: **P1-7, alerts — manage, scope and read like sentences** (rule editor, every rule rendered with
its scope in words, a "created from heatmap" filter, and a log that names symbol, level, size and why).


## §39 — P1-7 recon: where the alerts stand, and what to build

Scoped from the tree on 2026-09-16, read-only: no code changed for this entry. It exists so the next
session starts from the measurements instead of re-deriving them.

**What exists now.** The Alerts view is `index.html:522-542` (view `alerts`), rendered by `atlas.js`
(~534-590) with `atlas-v2.js` doing the persisted-history card (`loadHistory`, ~170). Four routes, all
real: `GET /api/atlas/alerts?limit&symbol` → `{alerts, stats}`; `POST /api/atlas/alerts/clear`;
`GET /api/atlas/alert-rules` → `{rules}`; `POST /api/atlas/alert-rules` (upsert by `id`) and
`DELETE /api/atlas/alert-rules/{id}` (`atlas/api.py:445-470`). The engine side is
`atlas/alerts.py`: `AlertRule {id, name, kind, params, enabled, cooldown_s, channels, fired,
last_fired_ms}` and `Alert {rule_id, name, kind, symbol, ts_ms, message, severity, data, channels}`,
with `evaluate()` checking every enabled rule of that kind, the generic level scope at
`alerts.py:179-182` (`at_price`/`at_tol`), per-rule cooldown, and `_message()` (line ~320) writing one
English sentence per kind with `{symbol}: {rule.name}` as the fallback.

**Kinds the engine emits** (from `_message()`'s branches plus the severity list): `big_trade`,
`block_trade`, `sweep`, `stop_run`, `iceberg`, `speed_spike`, `cvd_divergence`, `heat_pull`,
`heat_stack`, `vwap_cross`, `depth_execution`, `depth_refill`, `stacked_imbalance`, `intent_pressure`,
`pulled_size`, `trapped_traders`, and `wall_age` (from the depth map — the kind the heatmap's level
alerts create; it is not in the severity list, so it reads `info`).

**Params the evaluator actually reads** (`evaluate()`, lines 277-316): `min_multiple`, `sides`;
`min_size`; `min_levels`; `min_ticks`; `min_fills`; `min_zscore`; `kinds` (cvd); `min_strength`;
`min_share`; `min_volume`; `min_pct`; `max_distance_ticks`; `min_beyond_ticks` — plus the generic
`at_price` / `at_tol` scope and `min_age_s` where the emitting detector uses it.

**Three defects in the alerts UI, measured:**
1. `alClear` (`atlas.js:585`) writes the row `cleared locally` and never calls the server. The route
   `POST /api/atlas/alerts/clear` exists and is wired to nothing. A button that says it cleared a log
   it did not clear is worse than no button (canon: the UI may not claim what it did not do).
2. `Params (JSON)` is an editable text input of raw JSON (`atlas.js:556`) — every rule is read and
   written in the engine's vocabulary, and a typo is accepted silently by `JSON.parse` failure paths
   (`continue` — the rule is simply not saved, with no message).
3. There is no editor for the fields that make a rule a rule — level scope (`at_price`/`at_tol`),
   hold time, channels — no "created from heatmap" filter (the heatmap's rules are the `hm-` ids), and
   the log table has no Level or Size column: `data.price`/`data.size` are in the payload of every
   fired alert and the table renders only the pre-written message.

**Build spec (decisions taken, so the next session does not re-open them):**
- A pure module `orderflow_system/desktop/ui/alert-format.js` (global `OFAPALERTS`), the one place that
  turns a rule into words: `kindLabel(kind)`, `paramSpec(kind)` (each field's key, label, unit,
  default, min), `sentence(rule)` (e.g. *"Big trade — a single print ≥ 3× the block threshold · any
  level · UI · 30 s cooldown"*), `scopeWords(rule)` (`any level` vs `at 77070.24 ± 3.96`), and
  `why(row)` (the log row's reason, from `data.detail`/`note` with the kind's own sentence as the
  fallback). The editor's fields and the sentence both read `paramSpec`/`sentence`, so the form and
  the words cannot disagree — the same one-source rule as `HEAT_INSET` and the cursor store.
- The Rules card: Keep the On toggle and the Fired count; replace the JSON input with the sentence plus
  an inline **Edit** row built from `paramSpec` (named inputs with units), the level scope (price +
  tolerance), channels (ui / telegram / webhook checkboxes — the channels are the rule's, and
  `dispatch_webhooks` only forwards rules that opt in), and the cooldown. Save posts the whole rule
  back (the route already upserts), reads the rules back, and reports what the store kept.
- A filter row on the Rules card: `created from heatmap` (id starts with `hm-`) and `enabled only`,
  with an honest count line — *"3 of 16 rules · 3 from the heatmap"*, computed from the list, not
  asserted.
- The log table gains **Level** and **Size** columns read from `data.price` / `data.size` (a `—` when
  the detection has none: `speed_spike` and `cvd_divergence` carry no level), and the message column
  becomes the row's *why*, so every row names symbol, level, size and why regardless of kind.
- `alClear` calls `POST /api/atlas/alerts/clear`, re-reads, and says what came back (the count the
  server reports, not "cleared locally").
- Gates for this phase: a `alert-format.selftest.js` (sentences, scopes, the per-kind spec coverage,
  blank-field defaults) + `orderflow_system/test_alert_format.py` (run the selftest under pytest like
  `test_strips.py` does), plus registering `alert-format.js` in `scripts/audit_ui_refs.py`.

**The plan's gate (P1-7)**: live — edit a rule, fire it, read it in the log naming the level, delete it.

**Live recipe that works here** (paid for in P1-2…P1-6): sandbox
`APPDATA="$LOCALAPPDATA/Temp/ofap_p0_sandbox" .venv/Scripts/python.exe -m orderflow_system.desktop
--headless --port 8093`, `POST /api/control/engine/start`, then CDP to
`http://127.0.0.1:8093/desktop/`. Set `Network.setCacheDisabled` before believing any edit, dismiss
`#wizOverlay` and hide `#mt5Notice` (the notice swallows pointer events), and remember the sandbox's
instrument list holds `ZZZTEST` as its marker. Stop the app and leave the sandbox in place afterwards.

**State at this writing.** Branch `master`, clean, **29 ahead of origin**, nothing pushed. Gates:
pytest **509 passed / 2 skipped**; `audit_ui_refs.py` **AUDIT CLEAN**; the fifteen UI selftests —
shell 22, bus 13, links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12,
indicators 25, intent 7, study-api 45, search-ops all-pass, **ofx 139**, **cursor-link 7**,
**strips 9**.

## §40 — P1-7 built: the alerts card reads, edits and fires like the engine means it

Built 2026-09-16 in the sandbox on live Bybit BTCUSDT. Nothing committed: the change set is on disk
(13 modified files, 4 new — listed at the end of this entry) and HEAD is the §39 docs commit.

**What landed.**

* `desktop/ui/alert-format.js` — global `OFAPALERTS`, pure (a rule in, words out: no DOM, no API, no
  storage): `kindLabel`, `kinds()`, `paramSpec(kind)` (that kind's own fields plus the three scope
  fields `at_price` / `at_tol` / `min_age_s`), `sentence(rule)`, `scopeWords`, `channelWords`,
  `cooldownWords`, `why(row)`, `isHeatmapRule`, and the formatters (`fmtSize` never rounds a crypto
  size to zero). The editor builds its fields from `paramSpec` and the row renders `sentence(rule)`,
  so the form and the words cannot disagree. `alert-format.selftest.js` (20 checks) plus
  `test_alert_format.py` (12) gate it — including the check that matters: per kind, the params the
  JS offers against the params `AlertEngine._passes()` reads, compared from the engine's own source,
  both directions.
* The Rules card (`atlas.js`, rewritten block): every rule is its sentence, with an inline editor
  (name, kind, thresholds, level scope + tolerance, min hold, cooldown, state, channels) that
  replaces the rule's own row and previews what it will save ("saves as: …"). Save / delete / toggle
  post through the route and render what the store KEPT. The filter row counts honestly — "1 of 17
  rules · 1 from the heatmap · 17 enabled", computed from the list — and the poll leaves the rules
  alone while an editor is open or the arbiter holds the surface (the section already carries
  `data-surface="alerts"`).
* The log table: Time · Severity · Kind (in words) · Symbol · **Level** · **Size** · **Why** — the
  why from the detection's own `detail`/`note`, else the engine's message with the symbol prefix
  dropped (the Symbol column already names it). `—` where a kind has no level.
* `alClear` calls `POST /api/atlas/alerts/clear` and says what the server answered ("log cleared —
  the engine now holds 0 rows"). "cleared locally" is gone.
* Engine work the phase's gate could not be met without: **the depth map's own events were never
  dispatched to the alert engine.** `hub._dispatch` has mapped `pull`/`stack` to `heat_pull`/
  `heat_stack` since the atlas package landed, and nothing ever called it with those kinds — so every
  rule the heatmap's alert buttons create, and the two default heat rules, could never fire.
  `DepthHeatmap.on_orderbook` now returns the events it recorded and the hub dispatches them;
  `min_age_s` is enforced generically in `evaluate()` (an event that does not say how long it held is
  no evidence — the same shape as the price scope), and `wall_age` got the `min_size` branch the form
  offers plus a message that names the hold.

**A second defect, found in the log's own Why column.** Refills read "level 76887.9 refilled
-1789344734.5s after being eaten": the book feed stamps snapshots with the venue's **update id**
while the print feed stamps epoch ms, and the detector subtracted one from the other. That normaliser
already existed twice and divergently (`depthmap._as_epoch_ms` did not scale seconds,
`intent._as_epoch_ms` did); it is one module now — `atlas/clock.py` (`as_epoch_ms`, `EPOCH_MS_FLOOR`)
— used by depthmap, intent and tradedepth, and `TradeDetector` keeps a monotonic event clock so a
duration cannot go backwards. Regression:
`test_a_refill_latency_is_a_duration_not_a_sequence_number`.

**Live evidence (sandbox 8093, engine on live BTCUSDT, measured in this pass).**

* The two dead kinds fire: `heat_pull` at 76842.9 (size 10.36) and `heat_stack` at 76847.9 inside the
  first minute of the run — dispatched by the new hub path, not by anything the UI did.
* **The plan's gate, walked end to end.** An `hm-` rule created through `HEATMAP_PRO.alertOnLevel`
  (kind `wall_age`, bound to 76902.80 ± 1.70, `min_age_s` 120) then its tolerance edited to 30 in the
  new editor (the preview and the store both read "at 76830.60 ± 30.00") and **it fired**:
  `hm-BTCUSDT-76830_6-976549` at level 76840.0, size 4.572, "-3.24 pulled near price", read in the
  log's own DOM as `03:43:19 | info | Liquidity pulled near price | BTCUSDT | 76840.00 | 4.57 |
  -3.24 pulled near price`, then deleted (the banner names the id, the list reads 16 rules, 0 `hm-`).
* An empty field is "not mentioned", verified in the direction that matters: clearing `heat-pull`'s
  min_size and saving removed the key — the store kept `params: {}`, not a zero.
* `alClear`: banner "log cleared — the engine now holds 0 rows", the table repainted, the server read
  back at 1 (the next alert arrived within seconds).
* The refill fix, live: `level 76593.4 refilled 0.7s after being eaten (0.041 traded)`. The heat map
  after the clock promotion: 31 columns accumulating, newest 6.9 s old, version 8160 to 9451, 12
  walls carrying `wall_age_ms: 120000`.
* No `client error:` line in the sandbox log; the sandbox was stopped afterwards and its config left
  as found (16 default rules).

**Gates (measured this pass).** pytest **526 passed / 2 skipped** (was 509 / 2 at §39);
`audit_ui_refs.py` **AUDIT CLEAN**; the sixteen UI selftests — alert-format **20**, shell 22, bus 13,
links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12, indicators 25,
intent 7, study-api 45, search-ops all-pass, ofx 139, cursor-link 7, strips 9.

**Decisions taken (do not re-open).** The kind catalogue lives in `alert-format.js` and is held
against `atlas/alerts.py` by a test, so a new kind or a renamed param fails the suite instead of
drifting. The three scope fields are generic — the evaluator checks them before any kind-specific
threshold — and `scopeWords` speaks them, not the field loop. Channels are the rule's own, and the
sentence always says "UI log" because every alert reaches it. `cooldown_s` 0 reads "no cooldown".
The editor saves the whole rule and re-renders from the response, never from the form.

**Recipe notes for the next session.** `Network.setCacheDisabled` is the cache-bust — putting a query
on the hash (`#alerts?cb=…`) is a same-document navigation: nothing reloads and the app's router no
longer matches the view, so the panel silently never polls. Navigate to plain `#<view>` and drive it
with `showView('<view>')`. If the heatmap's overlay/bar is not mounted, call `HEATMAP_PRO.refresh()`
(it mounts on a view activation it noticed). The harness caps one `js()` evaluation at about 5 s —
sleep in Python between probes.

**Open / not verified.** `wall` (large resting level) is in the catalogue with its own note, "no live
detector emits this kind yet"; `wall_age` is the event the map emits. There is no "new rule"
affordance in this card — rules come from the heatmap's alert buttons or the shipped defaults. The
*first* level-bound rule (the 76902.80 `wall_age` with a 2-minute hold) never fired while it existed:
its level did not hold two minutes in that window — the bound-scope firing evidence is the later
`heat_pull` rule. The three `window.prompt` sites from §38 are still open.

**The change set.** Modified: `orderflow_system/atlas/alerts.py`, `atlas/depthmap.py`, `atlas/hub.py`,
`atlas/intent.py`, `atlas/tradedepth.py`, `desktop/ui/atlas.css`, `desktop/ui/atlas.js`,
`desktop/ui/guide.js`, `desktop/ui/index.html`, `desktop/ui/search.js`, `test_atlas_v2.py`,
`test_wall_age.py`, `scripts/audit_ui_refs.py`. New: `atlas/clock.py`, `desktop/ui/alert-format.js`,
`desktop/ui/alert-format.selftest.js`, `test_alert_format.py`.

## §41 — P1-8 recon: how bars are expressed today, and what the modes need

Scoped from the tree on 2026-09-16, read-only — no code changed for this entry. It exists so the build
starts from measurements: what already draws a bar, where a mode can live, what the payload really
carries, and the four defects found on the way.

**Two surfaces draw bars, and they share nothing.**

| Surface | Renderer | Bar expression today |
|---|---|---|
| Engine view (`data-view="ofx"`) | `desktop/ui/ofx.js` — layered canvases, one rAF loop | `drawFootprint()` (`ofx.js:1276-1488`): one column per bar, per-level split cells (bid left half, ask right half), alternating framing band + right-edge separator (`:1362-1365`), stacked-zone bands (`:1342-1357`), POC box (`:1449-1461`), a 1px high→low wick (`:1463-1468`), Δ/V column badge above the high (`:1472-1486`). **There is no open→close body anywhere.** |
| Chart view (`data-view="chart"`) | vendored TradingView Lightweight Charts **v4.1.3** (`desktop/ui/vendor/lightweight-charts.js`), created in `ui.js:526-546` | `addCandlestickSeries({upColor:'#35d07f', downColor:'#ff5d6c', …})`; data set in `loadChart()` (`ui.js:556-611`), which already maps `{time, open, high, low, close}` only. Studies re-paint the same series (`studies.js:221-232`). |

**What the payloads already carry** (this is what makes split/heat modes honest instead of invented):
`/api/candles/{symbol}` returns per bar `{time, open, high, low, close, volume, buy_volume, sell_volume,
delta, tick_count}` — the side volumes (`dashboard/app.py:317`, aggregated path `:337-361`). The
engine view's `mergeBars()` (`ofx-view.js:23-38`) drops `buy_volume`/`sell_volume` on the floor; the
footprint payload's own per-bar `calc` (`{volume, buy, sell, delta, poc, max_bid, max_ask, …}`) is
already merged. `/api/delta/{symbol}` carries `bar_delta` + running `value`. The demo path
(`dashboard/demo_data.py:121-156`) has `volume` + `delta` only — no side volumes, so a split mode
reading demo data must derive `buy=(vol+delta)/2, sell=(vol-delta)/2` and say which source it used.

**Where a mode and a palette can live.**
- `OFX.state.params` (`ofx.js:670`) holds the display parameters; `OFX.setParams()` (`:2119`) marks the
  base and live layers dirty. `math.theme` (`:458-478`) is the one colour table, and both the renderers
  and `OFX.legend()` read it — the legend's own selftest asserts every swatch resolves to a colour
  that table owns (`ofx.selftest.js:148-150`). A palette therefore has to *be* `math.theme`, not a
  parallel table, or the legend invariant breaks.
- `GET/POST /api/control/ofx` (`api.py:555-573`) is the engine's persisted parameter pair; the store's
  clamp list is `config_store.py:540-546` (+ `:684-685` for `min_block`/`va_pct`). `DISPLAY_ROOTS`
  (`param_registry.py:26`) is `("ofx", "atlas", "risk", "studies.data_box", "search.default_view")`, and
  `test_param_registry.py` fails the suite when a display-relevant leaf under those roots is not
  registered — so a new block outside those roots needs its own registration decision, not an
  accidental one.
- `localStorage` is *not* a record: `ofx-view.js:679-688` persists the heat ramp as `ofx.ramp` in
  browser storage, which `config_store`'s own rule (§33 decision 2) says never wins. The ramp is
  also absent from the registry, so no Chart menu can show it and no Restore-default can reach it.

**Four defects found, all measured.**
1. **The heat ramp has no server-side record and no registry entry.** `ofx-view.js:680` reads
   `localStorage['ofx.ramp']`; `math.heatColor01(t, ramp)` (`ofx.js:114`) accepts `classic|thermal`, and
   `ofx-view.js:681` hard-codes the same two strings — a third ramp added to the engine would be
   silently unreachable from the control (the two lists have no test holding them together).
2. **The engine view discards the side volumes the feed already sends** (`ofx-view.js:23-38`), so no
   bar-level up/down readout is possible there today even though the data is in flight.
3. **`state.stats` has no expression counters.** Every other renderer decision is countable
   (`columnBadges`, `heatCells`, `textStarved`, `aggregated`) precisely so a feature can be asserted
   from telemetry instead of from pixels (§38's rule); a new expression pass must add its own count
   or it can only be "verified" by looking.
4. **Nothing in the shell names the encoding.** `#chartSub` is a typed string
   (`index.html:145`: "candles · delta · value-area levels · signal markers") and the
   engine's legend has no expression entry, so a picture drawn with a tinted body has no text anywhere
   saying what the tint means — canon #5's pairing obligation without the words for it.

**Decisions (do not re-open).**
- **One pure module owns the encoding:** `desktop/ui/expression.js`, global `OFAPEXPR`, in the
  `alert-format.js` shape (pure, no DOM/API/storage, `new Function('window', src)` bootable in Node).
  It holds: the five modes (`default`, `delta`, `split`, `heat`, `wick`), the palette catalogue
  (`theme`, `deutan`, `protan`, `tritan`), the per-bar paint decision
  (`barPaint(bar, {mode, palette})` → what to fill, what to stroke, the split fractions, the glyph,
  the chrome gates, and the `encoding` sentence), the chart-series projection
  (`chartBars(bars, {mode, palette})` → per-bar `{color, borderColor, wickColor}`), and the words
  (`modeWords`, `paletteWords`, `legendLines`). The renderers execute; they do not decide.
- **A palette is `math.theme`, applied.** `OFAPEXPR.resolve(palette)` returns `{themeKey: 'r,g,b'}`
  overrides; `OFX.setExpression({mode, palette})` copies the frozen base table back and overlays them,
  so switching palettes is lossless and the legend's swatch invariant survives by construction. Default
  palette = today's colours exactly — the default mode must move no pixel.
- **Five modes, defined once, executed on both surfaces.**
  `default` — today's painting (footprint cells, framing, POC, wick, badges), unchanged.
  `delta` — a body rectangle from open→close tinted by the bar's delta bucket, outlined in the
  direction colour, with the direction glyph; the cells stay readable underneath (body alpha ≤ 0.26).
  `split` — the bar's high→low range carries two sub-bars: left = sell volume, right = buy
  volume (the app's own convention — bid left, ask right, `ofx.js:824-838`), heights = share of the
  bar's side-volume total; side volumes from `calc`/`candles` when present, derived from
  `volume`/`delta` when not, and the mode's words name which source was used.
  `heat` — the open→close body filled on the palette's diverging ramp by `|delta| / volume`.
  `wick` — the wick and the footprint cells only: the bar chrome (framing band, VA/HVN grounds,
  zone bands, POC box) is off, badges stay (they are the text carrier for the sign).
- **Persistence is the config, per chart:** a new `expression` block
  `{engine: {mode, palette}, chart: {mode, palette}}`, clamped by `config_store` against the same
  catalogues `expression.js` declares (one test holds the two lists equal), served by
  `GET/POST /api/control/expression` (partial per chart, returning the block the store accepted), and
  registered in `param_registry` as enums owned by `ofx` / `chart` so both Chart menus show them.
  The heat ramp moves into the same record (`ofx.ramp`, enum, clamp list shared with the JS) — the
  localStorage mirror goes away rather than growing a second one.
- **Colour is never the sole carrier.** delta/heat pair their tint with the direction glyph and the
  existing `Δ`/`V` badge; split pairs its colours with position (left/right) and the ↑/↓
  glyphs; the imbalance cells keep their rail/label. The legend prints the pairing sentence for the
  active mode, from the same object the renderer drew from.
- **Colour-blind palettes are measured, not asserted.** `deutan`/`protan`/`tritan` are seeded from the
  Okabe–Ito set (#0072B2 blue, #56B4E9 sky blue, #009E73 bluish green, #E69F00 orange, #D55E00
  vermillion, #F0E442 yellow, #CC79A7 reddish purple — Okabe & Ito 2008; Wong, *Nature Methods*
  2011), and the selftest simulates each palette's up/down pair through the Viénot–Brettel–Mollon
  (1999) dichromat matrices and requires a minimum separation, with today's green/red pair as the
  control that must *fail* under deutan/protan. A palette claim that is not measured is a claim.
- **A colour-blind palette overrides a hue-only heat ramp and says so.** `classic` walks red→green;
  when a CB palette is active the engine draws the depth heat on the palette's own monotone ramp and the
  legend states the override ("ramp cividis — classic is not colour-blind safe"). Silent substitution
  would be exactly the kind of invisible change the canon forbids.

**Build spec (files, in order).** New: `desktop/ui/expression.js`, `desktop/ui/expression.selftest.js`,
`test_expression.py`. Modified: `config_store.py` (block + sanitiser + `EXPRESSION_*` catalogues),
`param_registry.py` (five enum entries), `api.py` (`/api/control/expression` pair; `ramp` joins the
`/api/control/ofx` key list), `ofx.js` (palette application, mode-driven bar pass, legend section,
`stats().expression` counters), `ofx-view.js` (mode + palette controls, config load/save, mergeBars
carries side volumes), `ui.js` (chart-view projection), `index.html` (controls, legend line, script
tag), `audit_ui_refs.py` (`expression.js` in `JS_FILES`), `test_config_store.py` / `test_param_registry.py`
where the new block touches their contracts.

**Live recipe** (unchanged from §40): sandbox `APPDATA="$LOCALAPPDATA/Temp/ofap_p0_sandbox"
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 8093`,
`POST /api/control/engine/start`, CDP at `http://127.0.0.1:8093/desktop/` with
`Network.setCacheDisabled` set before believing any edit; dismiss `#wizOverlay`, hide `#mt5Notice`;
drive views with `showView('<view>')`, never a query on the hash. The engine view's telemetry is the
proof surface: `OFX.stats().expression` must count the bodies/splits actually painted per mode, and the
legend text is read back from the live DOM (`#ofxLegendBody`).

**Known risk, named now.** The chart view can express default/delta/heat/wick with the vendored
candlestick `color`/`borderColor`/`wickColor` per-bar overrides (v4.1.3 accepts them —
`Js('Candlestick')` maps `color`, `borderColor`, `wickColor`), but *split* needs pixels inside the
range, which the vendor only allows through `addCustomSeries` (`v4.1.3` exposes it). That contract is
probed live before it is built on: if the renderer's time→x path proves unusable, split ships on the
engine view and the chart view says so in its own legend line rather than drawing something that is not
a split candle.

## §42 — P1-8 built and verified: five bar expression modes, measured palettes, the legend that names them

Built and verified 2026-09-16 on live Bybit BTCUSDT in the sandbox. Nothing committed: HEAD is still
`fa202d6` (the §39 docs commit) and the tree carries P1-7 and P1-8 together (P1-8's change set at the
end of this entry; §40 lists P1-7's). The build landed first; a second pass finished the verification
and fixed the three defects verification surfaced — each is pinned by a new test.

**What landed.**

* `desktop/ui/expression.js` — `window.OFAPEXPR`, pure (no DOM, no API, no storage; Node-bootable):
  `MODES` (`default | delta | split | heat | wick`, each with `label`, `says`, `pairing` and chrome
  gates), `PALETTES` (`theme | deutan | protan | tritan`, each with its pair and its MEASURED
  separation numbers), `barPaint(bar, {mode, palette, theme})` (the whole decision for one engine bar:
  fills, strokes, split fractions, glyph, chrome gates, `encoding` + `pairing`), `chartBars(bars, opts)`
  (the Lightweight Charts projection — per-bar `color` / `borderColor` / `wickColor`), `splitVolumes`
  (side volumes from `calc` / `buy_volume` when the feed carries them, else derived from volume and
  delta, and it says which), `legendLines`, and the CVD machinery (`simulate` / `deltaE` / `separation`
  / `legibility`).
* The engine view paints from it: `ofx.js` applies a palette INTO `math.theme` (frozen `BASE_THEME`
  copy → assign → overlay the palette's keys), `setExpression` resolves/clamps and returns what the
  control then displays, the bar pass executes `barPaint` (bodies, split candles, glyphs, the chrome
  gates), `stats().expression` counts `bodies` / `splits` per pass, and the legend carries both a
  layout line (`bar expression (<mode>): <says>`) and a colour-key entry (`<says> · sign: <pairing>`,
  live `mode … · palette <label> · N bodies, M splits drawn in the last pass`).
* The chart view projects through the same catalogue: `#chartMode` / `#chartPalette` selects, the
  `#chartExpr` line renders `legendLines` verbatim (encoding + pairing + palette + the palette's own
  mapping sentence; `split` adds "the chart view cannot draw this mode — candles stay plain here"),
  and the delta lane takes the palette's pair (`rgba(pair, .55)`).
* Persistence is the config, per chart: an `expression` block `{engine, chart} × {mode, palette}`
  clamped by `config_store` against `EXPRESSION_MODES` / `EXPRESSION_PALETTES` (tests hold JS ↔ store ↔
  the `<select>` option lists equal), served by `GET`/`POST /api/control/expression` (partial per
  surface; the response carries the value the store ACCEPTED), registered in `param_registry` (the 4
  leaves + `ofx.ramp` — the ramp is a config value now, **81 → 86** variables, an 18th group), and the
  menubar's Chart-menu writes announce themselves (`ofap:expression`) so both surfaces reload from the
  store rather than being called into.
* The heat ramps are data: `RAMPS = classic | thermal`, **monotone in luminance** measured at 21
  samples per ramp in the gate (`dips == 0`, range > 0.3) — a magnitude never rides on hue.

**The three defects verification found (all fixed and pinned in this pass).**

1. **A bare `r,g,b` colour string makes Lightweight Charts THROW, not fall back.** `chartBars` handed
   the vendor `'230,159,0'` / `'86,180,233'` as per-bar colours; the vendor's parser answers
   `Error: Cannot parse color: 230,159,0` (uncaught, from inside its own paint path — the first paint
   dies; the scratch chart's canvases sampled empty). Route to a wiped app: defect 2. Reproduced
   deterministically on a fresh page: chart `default` + palette `deutan` → the log gains
   `Cannot parse color: 86,180,233` and the window is one red banner within 5 s. Fix: `chartBars`
   wraps the pair in `rgb(...)` at every un-alpha'd site, and `expression.selftest.js` now asserts
   every colour the projection emits is CSS-parseable across all 5×4 mode × palette combinations.
2. **(Pre-existing, app-wide.) `toast()` assigned `innerHTML` to its target, and seven call sites
   aimed it at `document.body`** (the client-error reporter, two in `guide.js`, four in `search.js`) —
   so ANY uncaught error replaced the entire UI with one banner. Fix in `toast()` itself: a
   body-level notice is routed into its own fixed `#noticeStrip` (created once, reused; `ui.css`),
   the call sites unchanged. Live probe: a deliberate throw shows
   "module error: Uncaught Error: …" in the strip (`position:fixed; bottom:10px; z-index:9999`) while
   `#chartMode` still exists and view switching keeps working.
3. **`default` mode + a colour-blind palette settled on theme candles.** `studiesApply()` repaints the
   candle series from the raw bars (it runs with zero studies too), and the chart's re-assert read only
   the MODE — `default` was exempt — so every poll stripped the deutan palette back to theme green/red
   under a legend claiming sky blue / orange (measured: 0 of 28 rows coloured; pane reads `sky 0 /
   orange 0 / green 1858 / red 2570`). Fix: the re-assert fires unless `mode === 'default' && palette
   === 'theme'` — the one combination the studies pass cannot move — pinned in `test_expression.py`.

**Live evidence (sandbox 8093, engine on live BTCUSDT).**

* Engine view, five modes on 13 bars (`stats().expression` counters; ink = opaque px on `#ofxBase`):
  default 0 bodies / 0 splits, ink 141,878 → delta 13/0, 140,525 → split 0/13, 63,344 → heat 13/0,
  140,449 → wick 0/0, 51,140 → back to default 141,862. The legend's sentence per mode is the
  catalogue's own `says`, read back from `#ofxLegendBody`.
* Palettes through the control write the same 8 keys (`bid ask up down imBuy imSell stackUp
  stackDown`): deutan `86,180,233 / 230,159,0`, protan `240,228,66 / 86,180,233`, tritan
  `64,176,166 / 220,50,32`; `theme` restores `53,208,127 / 255,93,108` exactly (sentinel: a hand-set
  `bid = '1,2,3'` comes back green). The control → store round trip measures **~1.2 s** on a busy
  sandbox — probes must sleep ≥3 s or they read the previous adopt (that race produced a false
  "restore is broken" reading once).
* Config round-trip, both directions, both surfaces: `POST` junk → the response carries the CLAMPED
  value (`default/theme`), never the junk; partial writes never blank the other surface; a bad surface
  answers `ok:false`; values written by curl are adopted on the next reload (engine read back at
  `heat/protan`, chart at `wick` for wick-mode wicks with transparent bodies).
* Chart view A/B on the same bars: `default` + theme paints the theme pair (exact `53,208,127` /
  `255,93,108`: 1112 / 3013 px); `default` + deutan paints `86,180,233` / `230,159,0` (1119 / 2636 px);
  the settled state (12 s and 18 s after load, ≥2 polls later, reads identical) is 29 of 30 rows
  coloured with pane `sky 1420 / orange 2280 / green 0` — defect 3's fix holding across polls.
* Client-error log: in the clean window (≥04:31, after the fixes) there is exactly ONE line — the
  deliberate strip probe. The pre-fix repro's 619 lines sit at 04:29–04:30.
* The sandbox was stopped afterwards and its config left at `default/theme` on both surfaces.

**Gates (measured this pass).** pytest **553 passed / 2 skipped** (526/2 at §40; `test_expression.py`
carries 27 of them); `audit_ui_refs.py` **AUDIT CLEAN** (116 routes, 65 modules, created ids 229);
**seventeen** UI selftests green — **expression 50**, ofx 139, alert-format 20, shell 22, bus 13,
links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12, indicators 25,
intent 7, study-api 45, search-ops all-pass, cursor-link 7, strips 9.

**Deviations from §41's spec (decisions taken — do not re-open).**

* The CVD model is **Machado–Oliveira–Fernandes 2009** (severity 1.0, applied in linear RGB; each row
  sums to 1, asserted), not the recon's Viénot–Brettel–Mollon set: the VBM matrices are injective on
  (r,g), so no red/green pair ever collapses under them and a bad palette measures "safe" — the metric
  could not detect the failure it exists for. The shipped green/red pair is the control that must FAIL
  the measurement (ΔE 9.1 deutan / 35.0 protan), and every shipped pair's numbers are re-measured in
  the selftest.
* The recon's "a CB palette overrides a hue-only heat ramp (`cividis`)" was **superseded**: both
  shipped ramps are monotone in luminance (measured, dips == 0), so there is no hue-only ramp left to
  override and no silent substitution to announce; the legend names the active ramp instead.
* `split` stays on the chart control on purpose: `CHART_SUPPORT.split` is `false` and the chart's
  legend prints the reason instead of drawing something else under the same name.

**Open / not verified.** The newest chart bar loses its per-bar expression colours between polls (the
WS `series.update()` path writes plain OHLC; ≤5 s until the next fetch; all modes, pre-existing path,
left alone). Chart markers (the optional overlay) keep their own colours under a CB palette — the
palette maps the candles, wicks and the delta lane, which is what the legend's mapping sentence
enumerates. The menubar's Chart-menu items for the expression are registry-verified (the params route
serves all four leaves with values and defaults) but were not clicked live this pass. The three
`window.prompt` sites from §38 are still open.

**The change set (P1-8's own files; P1-7's are listed in §40).** New: `desktop/ui/expression.js`,
`desktop/ui/expression.selftest.js`, `test_expression.py`. Modified: `desktop/config_store.py`,
`desktop/param_registry.py`, `desktop/api.py`, `desktop/ui/menubar.js`, `desktop/ui/ofx.js`,
`desktop/ui/ofx-view.js`, `desktop/ui/ui.js`, `desktop/ui/ui.css`, plus the two shared with P1-7
(`desktop/ui/index.html`, `scripts/audit_ui_refs.py`).

## §43 — P1-9 recon: where the keyboard stands, and what one map has to carry

Read-only against the tree on 2026-09-16 — no code changed for this entry. It exists so the build
starts from a measured inventory: every keydown listener that exists, the eight actions the plan
names, the five defects found on the way, and the decisions that must not be re-opened.

**The ask (plan item P1-9, keyboard-first completion).** One shortcut map with scopes: palette,
freeze, view switch, zoom, selection clear, replay seek, export, alert-from-cursor; discoverable
in-app; never fires inside a text field. Gate: a live pass where every action is reachable with no
mouse and a text field swallows none of them.

**Inventory — every keydown listener in the UI** (grep `addEventListener('keydown'` over `desktop/ui/*.js`).

| File:lines | Keys | Guard today | Notes |
|---|---|---|---|
| `ui.js:105-113` | Alt+A → `showView('alpaca')` | fields checked + rejects ctrl/meta/shift | global nav |
| `pause.js:74-79` | P → pause/resume | fields + ctrl/meta (alt/shift NOT rejected) | the freeze action, exists |
| `search.js:481-489` | input-local ↑/↓/Enter/Esc/Shift+? | field-scoped by construction | palette field |
| `search.js:491-497` | Ctrl+K and `/` → focus `#programSearch` | fields checked for `/` only | the palette, exists |
| `menu.js:289-300` | Esc; ?/F1 → hotkey sheet; `/` → open menu + focus its filter; 1-9 → rail click | Esc runs even while typing (by design); rest field-guarded | the sheet's owner; `/` collides with search.js |
| `menubar.js:755-757` | Tab → close the open menu | state-gated | menu-bar walk |
| `menubar.js:758-791` | Esc; Alt → focus title; ←/→/↑/↓/Enter walk | focus-gated on `.mb-title`/items | menu-bar walk |
| `menubar.js:792-794` | Alt+Z → zen | none — no field check | defect #2 |
| `shell.js:1574-1611` | Ctrl+Alt+T both modes; Escape/F11/Alt+1-9 in Terminal | typing checked only after Ctrl+Alt+T | terminal keys |
| `strips.js:379-407` | ↑/↓ PgUp/PgDn Home/End | fields + hover / inside-strip scoped, capture phase | the reader's keys (P1-4) |
| `drawings.js:516-530` | Esc chain; Delete/Backspace | fields checked | drawing-tool keys |
| `atlas.js:492-530` | none — replay is buttons + range inputs only | — | replay has no keys |
| `heatmap-pro.js` | none (buttons via `[data-hm-pro]`) | — | alert/export are mouse-only |
| `ofx.js:2021-2057` | none — wheel only (time ×1.12/0.89, price ×1.09/0.92; clamps 2.5-90 / 0.02-40) | — | zoom has no keys |
| `intent.js:202-207` | observes keydown to lease a surface | n/a | the arbiter, not a binding |

**The eight required actions, against that inventory.**

| Action | Today | Verdict |
|---|---|---|
| palette | Ctrl+K and `/` (search.js) | exists; `/` has two owners |
| freeze | P (pause.js) | exists |
| view switch | 1-9 (menu.js) | exists |
| zoom | wheel only; the heatmap's `zoom +/-` buttons | no keys |
| selection clear | `Clear` on the sel strip (`ofx-view.js:603`, handler `:714` → `OFX.clearSelection()`); heatmap `clear-sel` | no keys |
| replay seek | `#rpSeek` + `#rpPlay/Pause/Stop` (atlas.js:492-530) | no keys |
| export | `Export CSV` (`ofx-view.js:603` handler `:714`, `exportSelection()` `:629`) + heatmap `export-region/markers` | no keys |
| alert-from-cursor | `alert on cursor level` button (`heatmap-pro.js:633`, act `:693`, `alertOnLevel` `:431`) | no keys |

**Defects found (measured).**
1. **Two owners of `/`.** `menu.js:294` opens the ☰ panel and focuses `#menuFilter`; `search.js:493`
   focuses `#programSearch`. Both are document listeners, both `preventDefault()` — one press does
   both things.
2. **Alt+Z (zen) has no typing guard.** `menubar.js:792` is a capture-phase listener that checks
   `ev.key === 'z' && ev.altKey` and nothing else — it fires while a field has focus.
3. **P's guard is loose.** `pause.js:74-79` rejects only ctrl/meta, so Alt+P and Shift+P also
   pause today: the chords that exist are wider than the ones the sheet advertises.
4. **The discoverable sheet is hand-maintained and already stale.** `menu.js:56-65` lists 8 rows;
   the tree honours a dozen more bindings the sheet never mentions (Alt+Z, Ctrl+Alt+T, F11,
   Alt+1-9, Alt+A, the strip's six keys, drawings Esc/Delete, the menu-bar walk), and nothing
   keeps the two in sync.
5. **The guide's "Open the hotkey map" button does not open the map.** `guide.js:2345-2348` passes
   `view: 'guide'` — `wizGo` lands on the Guide view, so the button the step advertises as "the
   hotkey map" never shows one.

**Decisions (do not re-open).**
- **One registry, one dispatcher, one sheet source.** New `desktop/ui/keys.js` (global `OFAPKEYS`)
  owns the map: `bind({id, keys[], label, scope, when?, run, inField?, priority?})` for
  centrally-dispatched keys, `document([{keys, label, scope}])` for keys that stay local because
  they are scoped to hover state, a focused field or an open menu (strips, drawings, the menu-bar
  walk, the palette field, Terminal F11/Esc/Alt+digits). ONE document-level keydown listener; the
  sheet renders from `OFAPKEYS.list()`; menu.js's hand-written HOTKEYS array is deleted.
- **Chord form** is `[ctrl+][alt+][meta+]key` with the key lowercased; shift is part of a chord
  only when it changes the character (`?` vs `/`, `+` vs `=`, `_` vs `-`). Bindings list aliases
  (`['=', '+']`).
- **The typing guard is the dispatcher's job**, not each handler's: target `INPUT`/`TEXTAREA`/
  `SELECT`/`isContentEditable` swallows every binding except the ones opting in with
  `inField: true` (exactly one: Escape-closes-the-menu, today's behaviour). `Space` is additionally
  skipped when the focused element is a `BUTTON`/`A`/`SUMMARY` — the browser owns that activation.
- **Scope collisions resolve by priority, deterministically**: engine keys 6 > heatmap 5 > replay 5;
  ties → first registered. Contexts come from `OFAPKEYS.inView(view)`: the section must be
  `.active`, and in Terminal mode with a focused panel, that panel must be the one.
- **The new chords.** Engine: `=`/`+` time zoom in, `-`/`_` out (×1.12/0.89, the wheel's factors),
  `]`/`[` price zoom in/out (×1.09/0.92), `X` clear the selection, Ctrl+E export the selection.
  Heatmap: `=`/`-` drive its own `zoom +/-` buttons, `X` clears its selection, Ctrl+E exports the
  region, `A` runs `alert on cursor level`. Replay: `Space` toggles play/pause, `,`/`.` seek -/+2%.
  `/` now belongs to the palette only (defect #1's resolution); the ☰ menu keeps its button and
  Ctrl+K stays the palette's primary chord.
- **Zoom maths get one home**: `math.zoomScale(value, factor, min, max)` + `math.anchorOffset(...)`
  (pure, selftested); `OFX.zoomTime/zoomPrice` compose them around an anchor (stage centre for
  keys, the cursor for the wheel) and the wheel handler is refactored onto them — no second copy
  of the anchor arithmetic.
- **Ctrl+Alt+T migrates into the map and therefore becomes field-guarded** (today it fires while
  typing — `shell.js:1574-1579` checks typing only after it). Intended change; the shell keeps its
  own listener for Escape/F11/Alt+digits (mode-entangled) and documents those rows via the map.

**Build spec.** New: `desktop/ui/keys.js`, `desktop/ui/keys.selftest.js`, `test_keys.py`.
Edits: `index.html` (one script tag after `theme.js`, ahead of every module that registers at
parse time); `menu.js` (drop the static HOTKEYS + the keydown block; sheet renders from the map);
`search.js` (drop its document keydown; register Ctrl+K + `/`); `pause.js` (export a `toggle()`;
register P); `menubar.js` (export `toggleZen`; drop the Alt+Z listener; register it; document the
walk); `ui.js` (drop the Alt+A listener — keys.js core binds it); `shell.js` (drop Ctrl+Alt+T from
its listener; register it; document Terminal rows); `ofx.js` (zoom maths + exports); `ofx-view.js`
(register engine zoom / X / Ctrl+E; add the engine legend's keyboard rows); `heatmap-pro.js`
(register X / Ctrl+E / A); `atlas.js` (register Space and `,`/`.`; track `A.replay.playing`);
`strips.js` + `drawings.js` (document their local rows); `guide.js` (the hotkey step's button
opens the sheet; copy names the new keys); `test_wiring.py` (its audit-list tuple gains keys.js).
No CSS additions — the sheet reuses the existing `hk-*` classes.

**Live recipe (sandbox).** `APPDATA="$LOCALAPPDATA/Temp/ofap_p19_sandbox" .venv/Scripts/python.exe
-m orderflow_system.desktop --headless --port 8092`, driven over CDP with
`Network.setCacheDisabled`. Per action: keys dispatched as real CDP input events, effects read
from the app's own state — `OFAPPause.state.paused`, `.view.active`, `OFX.state.view.scaleX/Y`,
`OFX.selection()`, `#rpSeek.value` + the replay status route, the exports folder listing, the
alert-rules count. The text-field probe focuses `#programSearch`, presses every new chord, and
asserts `OFAPKEYS.recent` gained nothing and no state moved. Created state (an exported file, a
test alert rule) is counted and deleted afterwards; the sandbox log is grepped for `client error:`.

**Gates at recon time (measured this pass).** pytest **553 passed / 2 skipped**;
`audit_ui_refs.py` **AUDIT CLEAN** (116 routes, 65 modules, 144 used ids, created 229); seventeen
selftests green (ofx 139, expression 50, alert-format 20, shell 22, bus 13, links 10, watchlist 17,
news 17, options 21, fundamentals 18, market-pressure 12, indicators 25, intent 7, study-api 45,
search-ops all-pass, cursor-link 7, strips 9).

## §44 — P1-9 built and verified: the one shortcut map, and the palette crash it uncovered

Built on disk 2026-09-16, uncommitted like everything since P1-7. `desktop/ui/keys.js`
(`window.OFAPKEYS`) is now the app's single registry and dispatcher for keyboard bindings: one
document listener, a chord canonicaliser, the shared typing guard, scope gates with priorities, a
`recent` ring of the last firings, and `list()` — the hotkey sheet renders from it, so a key and its
documentation cannot drift. 29 → 31 rows live (the two Drawings rows join when the engine view first
mounts its drawing layer; every other row is present from boot).

**The eight actions, all reachable with no mouse (measured, sandbox :8092).**
palette — Ctrl+K focused `#programSearch` (`recent: palette`). freeze — `P` → paused true → false.
view switch — `4` → `.view.active` became `heatmap` = rail[3]. zoom — `=` / `-` / `]` / `[` moved
`scaleX 52 → 58.24 → 51.8336` and `scaleY 0.8988 → 0.9796 → 0.9013` (the wheel's exact multipliers,
`recent` naming each binding). selection clear — a real shift+drag box → strip shown → `X` → selection
null, strip hidden, `recent: selection-clear`. export — `Ctrl+E` → `ofx-selection-BTCUSDT-20260916T023100.csv`
(19 lines; volume 12.58 / delta 8.05 matching the strip) in the sandbox exports folder; deleted after,
count read back to 0. replay seek — exchange tape loaded (1000 events), `Space` → playing → paused,
`.` seeked `318 → 338`; a focused `#rpStop` + `Space` left the browser its activation and fired no
binding. alert-from-cursor — hovered level `75968.08`, `A` created
`hm-BTCUSDT-75968_08-073188 {kind heat_pull, at_price, at_tol 1.52, channels ['ui']}`; deleted, rules
16 → 17 → 16. The sheet itself: `?` opened it with **31 rows = `OFAPKEYS.list().length`**, every one
of the eight action labels present, 8 Global rows highlighted; `Esc` closed it.

**"A text field swallows none of them":** focus in `#programSearch`, then twelve chords dispatched as
real key events (`p 4 = - x a , space ] ? Ctrl+K Ctrl+Alt+T`) — `recent` stayed 0, paused/hash/mode/
scaleX all unchanged, the characters landed in the field only.

**Terminal mode:** `Ctrl+Alt+T` there and back; `4` focused the heatmap widget and `=` ran
`heatmap-zoom-in` (its window 169 → 180 buckets); `7` focused the engine and `=` ran `zoom-time-in`
(52 → 58.24); `P` froze and resumed inside the mode. Scope collisions resolve by focus, as designed.

**Defects found and fixed in this pass (all measured).**
1. **The palette threw on every non-empty query.** `studies.js`'s Guide section was pushed as
   `{title, lead, body}` while `GUIDE_SECTIONS` entries are `{h, body}` — the Guide renders `s.h` and
   `searchBuildIndex` indexes it, so `searchScore` hit `undefined.toLowerCase` for every query
   (25 `client error:` lines, all 12:01:59-12:02:00, before the fix; the Guide card would have read
   "undefined" had it rendered). Fixed to the `h`/`body` shape; `test_studies.py` now guards the `h:`
   at both push sites. After the fix: typing into the palette renders results and the log gained
   **zero** further client errors; the Guide renders 13 cards with "Writing your own studies" at 12.
2. **The same push never refreshed `#guideBody`** (the guide view is built once, before the push),
   so the section was invisible even in the data. Mirrored the how-to section's refresh.
3. Recon-time defects fixed in the build: the two owners of `/` (palette now owns it; menu.js's copy
   gone), Alt+Z's missing typing guard, `Ctrl+Alt+T` firing mid-typing (now guarded — intended
   behaviour change), and `P`'s loose guard (Alt+P/Shift+P no longer pause; the chord is exact).

**Deviations from §43's spec (do not re-open).** Engine bindings register at MODULE scope in
ofx-view.js, not inside the lazy `ofxInit()` — the live map read 22 rows without them until the view
was opened once, which is exactly the user the sheet exists for. Engine clear/export RUN click the
selection strip's own buttons (`[data-ofx-sel="clear|export"]`) — driving beats duplicating, same as
the heatmap and replay bindings. `test_workstream_i.py`'s pinch test was updated to pin the new
routing (it asserted `scaleY` inside a 700-char window after `ev.ctrlKey`; the maths now live in
`zoomPrice()`, pinned by ofx selftest 139 → 145).

**Gates (measured this pass).** pytest **563 passed / 2 skipped** (553 + `test_keys.py` 9 +
`test_studies.py` 1); `audit_ui_refs.py` **AUDIT CLEAN** (67 modules now, was 65); **eighteen** UI
selftests green — **keys 42** (new), **ofx 145**, expression 50, alert-format 20, shell 22, bus 13,
links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure 12, indicators 25,
intent 7, study-api 45, search-ops all-pass, cursor-link 7, strips 9. Sandbox client-error log: 25
lines, all the fixed crash, zero after.

**Open / not verified.** The wheel's zoom was refactored onto the same `math.zoomScale` /
`math.anchorOffset` helpers the keys use — a lift of the original formulas, but the wheel itself was
not re-driven visually this pass (its numbers are the selftest's and the keys' live multipliers).
The sheet lists the Drawings rows only after the engine view first mounts that layer. Two `X clear
the selection` rows are by design (Engine and Heatmap scopes). `1` maps to rail[0], which carries no
`data-view` — pre-existing mapping, unchanged (`2` is Overview … `7` is Engine). The harness's CDP
`Input.dispatchMouseEvent` timed out against the sandbox daemon (both sessions); the selection and
heatmap-hover gestures were therefore synthesized in-page for SETUP only — every key under test was
a real CDP key event, and every reading came from the app's own state. The frozen build still
predates P1-7/8/9. Nothing was committed; HEAD stays `fa202d6`.

**The change set (P1-9's own files; P1-7's are listed in §40, P1-8's in §42).** New:
`desktop/ui/keys.js`, `desktop/ui/keys.selftest.js`, `test_keys.py`. Modified: `desktop/ui/index.html`,
`menu.js`, `search.js`, `pause.js`, `menubar.js`, `ui.js`, `shell.js`, `ofx.js`, `ofx.selftest.js`,
`ofx-view.js`, `heatmap-pro.js`, `atlas.js`, `strips.js`, `drawings.js`, `guide.js`, `studies.js`,
`test_wiring.py`, `test_workstream_i.py`, `test_studies.py`, `scripts/audit_ui_refs.py`.

## §45 — P1-10 recon: what young data exists, where age dies, and what stale-out has to mean

Read-only against the tree on 2026-09-16 — no code changed for this entry. Scoped so the build
starts from what is already true: the age policy exists but never reaches a screen, and "stop the
feed" has two opposite behaviours with no shared wording.

**The ask (plan item P1-10).** Show the age of what is displayed (depth 5 s / quote 60 s windows;
`age_known:false` when the clock is unknown) and make a panel visibly stale-out instead of freezing.
Gate: live — stop the feed, watch panels age and say so; restart, watch recovery.

**What exists.**
- **The policy already has one home: `atlas/crossvenue.py`.** `STALE_DEPTH_MS = 5_000`,
  `STALE_QUOTE_MS = 60_000` (`:35-36`), `stale_window_ms(kind)` (`:39-41`), and
  `VenueTop.to_dict()` (`:59-88`) emitting `age_ms`, `age_known`, `stale_after_ms`, `stale`, `ok` —
  with the rule "an unknown age is reported as unknown, not as stale". **No UI reads crossvenue**
  (grep: zero consumers) — the only age semantics in the build are API-only and invisible.
- **`engine.live_status()` (`engine.py:653-708`)** is the UI's live/demo source: a per-endpoint
  string map (`live` / `warming` / `demo`, plus `stale` for a book that lost sequence continuity,
  `bybit_feed` sets the flag). Consumed by `ui.js` as `#livePill` ("data: live|warming|demo", no age,
  `ui.js:235-246`) and `panelIsLive()` (two gates: footprint `:908`, tape `:960`). **No timestamps
  anywhere in the payload.**
- **The clock exists server-side but is dropped.** `main.py:252-257` keeps
  `_recent_ticks[sym]: deque[Tick]`, `_last_candles[sym]: Candle`, `_recent_signals[sym]`;
  `Tick.timestamp_ms` / `Candle.timestamp_ms` (`data/models.py:46,184`). The status payload
  (`engine.py:710-727`) carries symbol/price/ticks/candles/cum_delta/trade_phase/trade_direction —
  no times. `atlas/clock.py` is the one venue-clock normaliser.
- **Payload sample times the UI already holds**: heatmap `buckets` are epoch ms
  (`DepthMap.snapshot`, live value `1789525971000`), tape prints carry `time`, candles carry
  `timestamp_ms`, news items carry their own times. Most panels could know their age today; none
  display it.
- **Existing stale-flavoured behaviours**: footprint/tape demo banners (`ui.js:908-912`), the
  `panelIsLive` gates, `book_state`'s `stale`, atlas rows with `ts_ms=0` = "age unknown"
  (`atlas/api.py:300`), `fresh_book` at a 1500 ms window (`intent.py:463`). Nothing anywhere says
  "this was live and is now N seconds old".
- **The stop-the-feed trap**: on engine stop every `dashboard/app.py` route returns `demo_data.*`
  (`:1097` footprint, `:1119-1126` tape, `:277` candles, `:811` orderbook, …), while the **atlas hub
  keeps serving its last recorded state** (heatmap/cvd/profile/tape are hub reads, no demo fallback).
  So stopping the feed produces two different pictures — a silent demo swap and a silent freeze —
  with no shared wording for either.
- **Claims surface**: `guide.js:2390` says "the logs panel and the status bar show freshness" —
  today neither shows an age (`#statusFeed` carries the stored plan's feed wording, `shell.js:1448`).
- **Chip pattern to reuse**: `OFAPCURSOR.badge(host)` (`cursor-link.js`) — a `.view-head` span owned
  by one store and repainted centrally. The freshness chip is its sibling: one module, chips on
  view-heads, repainted on a shared 1 s tick so a silent feed AGES without any new payload.

**Defects found.**
1. **Age never reaches the screen.** live_status has no times, the status payload drops
   `_recent_ticks`/`_last_candles` stamps, and no panel renders an age. Freshness is a policy
   without a clock.
2. **The one real age vocabulary has no consumer.** crossvenue's `age_ms`/`age_known`/`stale` rows
   exist for API callers only.
3. **"Stop the feed" has two opposite behaviours and one silent one.** Demo-swap panels announce
   demo; hub-backed panels freeze on their last picture and say nothing; neither names a time.
4. **A claim in the copy that is not true today** (guide.js:2390) — the build either makes it true
   or the sentence changes; leaving it is the kind of drift this suite exists to stop.

**Decisions (do not re-open).**
- **One policy module.** Extract the constants + the assessment into `atlas/freshness.py`:
  `window_ms(kind)` and `assess(kind, last_ms, now_ms=None)` → `{age_ms, age_known, window_ms,
  stale}`; kinds depth 5 s, quote 60 s, trades 5 s (a continuous feed), candles 60 s.
  `crossvenue.py` imports it and its payload keys stay byte-identical.
- **The server exposes ages where a real clock exists.** `engine.status()` per_symbol gains
  `last_tick_ms` + `last_candle_ms` (0 = never); `live_status()` gains an additive `age` block per
  endpoint (tape → last tick, footprint/candles → last candle, orderbook → `age_known:false` — its
  timestamp is the venue's own clock, the existing `atlas/api.py:300` note stands; the rest unknown).
  `endpoints` stays the string map `panelIsLive` gates on.
- **One UI store: `desktop/ui/freshness.js` (`OFAPFRESH`)** in the cursor-link shape —
  `stamp(panel, {lastMs|ageMs, ageKnown, windowMs, source})`, `chip(head)` (`.view-head` span,
  class `ofap-fresh-chip`), a 1 s repaint tick, and a pure `pick(state)` → `fresh`/`aging`/`stale`/
  `unknown`/`demo`/`held`. Thresholds: quiet age under half the window, amber to the window, then
  "stale — no update for Ns" plus a section class `ofap-stale` that DIMS the data area (never hides
  it). Demo renders "demo data" — an age on demo numbers would be a lie. `age_known:false` renders
  "age unknown".
- **A user-invoked hold is not a fault.** With `OFAPPause` paused, chips render `held · Ns` (muted),
  not amber — the pause chip already says updates are held; the age still counts because it is real.
- **Windows come from the payload where they exist** (crossvenue rows, the new engine age block);
  the JS default table covers client-only sources (news/options/fundamentals fetch stamps) and a
  pytest pins it to the Python constants so the two can never drift.
- **Stamp call sites are each panel's own paint** (the panel owns its claim): ofx-view
  (footprint poll), watchlist (status paint), atlas.js loads via its 962-971 beat
  (heatmap/cvd/profile/frames/trackers), heatmap-pro (pull), news, options, fundamentals, scanner,
  chart, tape. The **pill** gains the newest-tick age; `#statusFeed` keeps the plan wording.

**Build spec.** New: `atlas/freshness.py`, `desktop/ui/freshness.js`,
`desktop/ui/freshness.selftest.js`, `orderflow_system/test_freshness.py`. Edits: `atlas/crossvenue.py`
(import the policy), `desktop/engine.py` (status + live_status ages), `desktop/ui/index.html` (one
tag + the pill's title copy), `ui.js` (pill age from the age block), `watchlist.js`, `ofx-view.js`,
`atlas.js`, `heatmap-pro.js`, `news.js`, `options.js`, `fundamentals.js`, `scanner.js`,
`ui.css` (`.ofap-fresh-chip`, `.ofap-stale` — tokens only), `scripts/audit_ui_refs.py`,
`test_wiring.py` (audit tuple), `guide.js` (the freshness claim, now made true).

**Live recipe (sandbox).** Engine start → panels' chips read their ages; **stop the feed** = engine
stop: hub-backed panels (heatmap/CVD/profile) must age past the 5 s window and print "stale — no
update for Ns" while demo-served panels must print "demo data"; curl the status + live-status routes
for the age fields; **restart** → every chip returns to fresh. The 1 s tick is the proof the age is
real rather than stamped per payload: with no payload arriving, the number keeps rising.

**Gates at recon time (measured this pass).** pytest **563 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN** (67 modules); eighteen selftests green (keys 42, ofx 145, expression 50, alert-format
20, shell 22, bus 13, links 10, watchlist 17, news 17, options 21, fundamentals 18, market-pressure
12, indicators 25, intent 7, study-api 45, search-ops all-pass, cursor-link 7, strips 9).

## §46 — P1-10 build: the age of every panel's data, declared

**What it does now.** Every panel view-head carries a freshness chip: `live · 2 s`, `aging · 4 s`,
`stale — no update for 17 s`, `demo data`, `age unknown`, `held · 9 s` (the last when `P` is holding
updates — a deliberate hold is not a fault and does not read as one). The chip repaints on its own
**1 s tick**, so a panel that stops receiving samples ages and then stales out visibly instead of
freezing. A stale panel's data area dims (`opacity: .6`) — dimmed, never hidden — and the chip says
how long. The status bar's pill reads `data: live · 2 s` (the newest tape sample's age), with every
endpoint's age in its title.

**One policy, one store.**
- `atlas/freshness.py` — the one reading of "how old is this": `window_ms(kind)` (depth 5 s, quote
  60 s, trades 5 s, candles 60 s — the numbers `crossvenue.py` had, moved here and re-exported so its
  payload keys stay byte-identical) and `assess(kind, last_ms, now_ms)` → `{age_ms, age_known,
  window_ms, stale}`. An unknown clock (`ts_ms` 0/None, the venue-time case) stays **unknown** —
  never invented, never stale.
- `desktop/ui/freshness.js` (`window.OFAPFRESH`) — `stamp(id, spec)` / `chip(head, id)` / `pick` /
  `fmtAge` / `list()`; chips auto-attach to all fourteen panel view-heads at boot (the scanner
  attaches its own — its view is built by its module after boot), and `pick()` gives demo and unknown
  their own verdicts ahead of any age.
- The JS windows mirror the Python ones and `test_freshness.py` pins them **the-equal**.

**Server.** `engine.status()` per-symbol gains `last_tick_ms` / `last_candle_ms` (raw clocks, 0 =
never); `engine.live_status()` gains an `age` block keyed like `endpoints` — tape/microstructure from
the tick clock, footprint/candles/scanner/strategy/volume_profile/bias from the candle clock,
orderbook `age_known: false` (venue clock, the api.py note stands). Additive: `endpoints` keeps its
string map and `panelIsLive()` is untouched.

**The defect this pass found (live, then fixed).** `_last_candles` holds the newest **closed** 1m
candle (`main.py` stores it on close), so its `timestamp_ms` is the OPEN time — a healthy 1m feed is
legitimately 60–120 s "old" by open, and the first live read showed `footprint: 67s` against a 60 s
window, i.e. a false stale on a live feed. Fixed by ageing from the CLOSE everywhere a closed bar is
the sample: `live_status` adds `CANDLE_INTERVAL_MS` to the newest open; `ofx-view.js` stamps
`(bar.time + barSec) * 1000` with `barSec` measured from the series; the chart does the same from its
last two bars; frames/alerts/profile/trackers and the slow panels (news 10 min, fundamentals 10 min,
options 2× interval, scanner its own `as_of`) use their own honest clocks — a volume-bar panel that
closes on volume, not the clock, measures its fetch flow and says so in the comment.

**The live gate (sandbox :8093), verbatim reads.**
- Engine started, heatmap + engine views staged: `ofx: live · 9 s`, `tape: live · 0 s`;
  server `age.tape` 2 s, `age.candles` 12 s (healthy, no false stale after the clock fix).
- **Stop the feed** (engine stop clicked): tape `live · 1 s` → `stale — no update for 10 s` →
  `stale — no update for 17 s` (rising with no payload — the 1 s tick is the proof the age is real);
  the tape and heatmap sections gained `.ofap-stale`; ofx went `aging · 39 s → 46 s` (its poll
  continues; the closed bar ages).
- **Restart**: tape back to `live · 0 s`; heatmap (re-shown; hidden panels do not poll — they age
  until the view is shown again, then the load re-stamps) back to `live · 1 s`, chip class
  `is-fresh`, `.ofap-stale` cleared. Server `overall: live`, `tape` 2 s.
- 0 client errors in the sandbox log; sandbox killed; port free.

**Files.** New: `orderflow_system/atlas/freshness.py`, `desktop/ui/freshness.js` (166),
`desktop/ui/freshness.selftest.js` (26 checks), `orderflow_system/test_freshness.py` (10 tests).
Edited: `atlas/crossvenue.py` (imports the policy, keys unchanged), `desktop/engine.py` (age
payloads + `CANDLE_INTERVAL_MS`), `index.html`, `atlas.css` (chip + dim), `ui.js` (`liveState`,
pill age, tape + chart stamps), `watchlist.js`, `ofx-view.js`, `heatmap-pro.js`, `atlas.js`
(heatmap/cvd/profile/frames/trackers/alerts stamps), `news.js`, `options.js`, `fundamentals.js`,
`scanner.js` (self-attached chip), `guide.js` (the freshness claim is now true of the chips),
`scripts/audit_ui_refs.py`, `test_wiring.py`.

**Limits, stated.** (a) The "engine running + feed silently dead" state cannot be induced in-sandbox;
the stop-feed pass demonstrates the same machinery (frozen stamps, ages rising). (b) A panel whose
view is hidden keeps ageing until re-shown — by design, and why the heatmap's recovery needed its
view back. (c) The `demo data` chip path is wired and unit-tested; the stop-feed pass did not catch a
panel mid-demo (ofx read `aging` through the stop), so it awaits a live sighting. (d) `news` /
`fundamentals` windows are 10 min by judgement (their feeds are slow); tune on the first complaint.

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped** (563 + test_freshness
9); `audit_ui_refs.py` **AUDIT CLEAN** (69 modules); **nineteen** selftests green —
`freshness 26` new, keys 42, ofx 145, expression 50, study-api 45, shell 22, alert-format 20, options 21,
fundamentals 18, watchlist 17, news 17, bus 13, market-pressure 12, links 10, strips 9, intent 7,
cursor-link 7, indicators 25, search-ops all-pass.

## §47 — P2-1 recon: where the hover path spends its per-mousemove time

**The ask (plan §2, verbatim).** "Build `printsByBar` in `setData()`; index heat cells by column (or
reuse the visible-column search); maintain CVD incrementally. Gate: a measurement on a 10 k-print tape
— mousemove cost before/after, and `ofx.stats()` p95 unchanged or better under the standard synthetic
load." The plan's §1.3 adds the measured shape of the cost: "the per-mousemove cost is O(prints + heat
cells + bars), not O(prints). With a 10 k-print tape and a 30 k-cell matrix that is ~40 k iterations
per pointer move."

**Where the time goes — `ofx.js` `hover()` (2,180–2,223), three full scans per call.**
1. **CVD from bar 0** (`:2,187-2,188`): `for (let k = 0; k <= i; k += 1) cvd += …bars[k].delta` — O(i)
   per move; a sweep across the canvas pays it hundreds of times.
2. **The whole depth matrix** (`:2,198-2,203`): `for (const cell of state.data.heat)` filtering
   `cell.col !== i` — the full 30 k cells to find one column. Note the RENDERER already solved this:
   `setData()` builds `state.data.heatIndex = math.heatColumns(state.data.heat)` — `{cols, groups:
   Map(col → cells)}` — once per payload (`ofx.js:890`), and `drawHeat` walks `groups`/visible cols.
   Hover simply never used it.
3. **The whole print list** (`:2,205-2,208`): `for (const p of state.data.prints)` with the window test
   `p.time >= bar.time && p.time < bar.time + barSeconds()` — O(prints) per move.
4. A fourth, smaller one the report did not name: `state.data.flowEvents.filter((e) =>
   Number(e.col) === i)` (`:2,210`) — O(events) per move, same column question as (2).

**What the surrounding code already provides.**
- `barSeconds()` (`:1,726-1,731`) is derived from the LAST TWO bar times (stable for a payload) — so a
  print→bar assignment is a stable function of the payload.
- Prints from the live path carry **seconds**: `_live_tape_rows` (`dashboard/app.py:923`) emits
  `t.timestamp_ms / 1000`. But `math.selectionStats` still defends against millisecond stamps
  (`raw > 1e11 ? raw / 1000 : raw`, `ofx.js:641`) while **`hover()` does not** — a ms-stamped source
  fed to the engine view would silently show 0 prints in every bar (the view even has a note for
  "prints outside the drawn bar range", so the failure would look like a feed mismatch, not a bug).
- `stats()` (`:2,286`) exposes `p95Ms`/`framesMs` from render passes; `renderLayers(true)` is exported
  (`:2,282`), which matters because rAF can be dead in a headless page (RESUME trap) — the gate's
  frame numbers must be driven by direct renders, not by waiting on rAF.
- `hover(mx, my)` is exported (`:2,282`) and touches no DOM geometry it does not already hold in
  `state.view` — so a Node/sandbox measurement can call it directly without synthesising mouse events
  (which this host's CDP cannot deliver — see the P1-9 limit).

**One live defect found while reading the payload path.** `ofx-view.js:46` requests
`/api/tape/{s}?limit=200`, but the route (`app.py:1,114-1,116`) declares `count` (default 60, `le=200`)
— the query param is ignored and the view always gets **60** prints. The engine's hover print window
is therefore 60 rows wide no matter what the view asks for. Fix rides along with this item (one word:
`count=200`).

**Decisions (do not re-open).**
- Reuse, don't rebuild: hover's depth read becomes `state.data.heatIndex.groups.get(i)` — the index the
  renderer already pays for; no second structure, no drift.
- One index pass in `setData()`, keyed on the payload flags it already receives:
  `state.idx = { printsByBar, cvd, flowByCol }` — rebuilt when `prints` **or** `bars` change (bar
  boundaries define the buckets), when `bars` change (`cvd` prefix sums), and when `heat` changes
  (`flowByCol`, alongside the existing `heatIndex` build). Rebuild cost is one O(prints+heat+bars)
  pass per 2.5 s poll instead of per mousemove.
- Print stamps are normalised **once**, in the index, with the `selectionStats` rule
  (`raw > 1e11 → /1000`). Live seconds-stamped rows are unaffected; ms-stamped rows stop silently
  reading as zero. This is a fix, stated as one.
- `hover()`'s OUTPUT must not change: same fields, same numbers for the same payload. The selftest's
  parity checks compare the new path against the old loops implemented inline as the oracle.
- `drawRibbon()`'s per-draw CVD rebuild (`ofx.js:1,765-1,768`, an O(bars) run over ALL bars every
  ribbon pass) reuses the same prefix — same numbers, one fewer per-frame scan. The max-volume/max-
  delta spreads in that function stay untouched (rendering change, out of scope).
- The bridge table (`hover: null` state, `onHover` callback, `state.dirty.live`) is untouched.

**Gate recipe (measured before the build, re-measured after).**
Sandbox `:8093` → engine view open → `OFX.setData()` with a synthetic payload: 10 k prints over 300
bars (seconds stamps) + 30 k heat cells + flow events → call `OFX.hover(x, y)` 200 times across the
canvas width (staying inside the bar range) timing each with `performance.now()` → per-call
p50/p95/max, plus one `renderLayers(true)` pass timed after. **Correctness parity first**: the same
probe records `prints`, `sweep`, `depth`, `cvd` at 5 sampled bar indices; before/after must be equal
(or explicitly explained). BEFORE numbers are taken on the unmodified tree; AFTER on the built one.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN (69 modules); nineteen selftests
(ofx 145 — which do NOT yet exercise `hover()` at all; this build adds the first hover coverage).

## §48 — P2-1 build: the hover path is indexed

**What changed.** `hover()` no longer rescans the payload on every pointer move. One index pass in
`setData()` builds three structures, and a fourth is reused:

- `buildPrintIndex()` → `state.idx.printsByBar[i] = {prints, sweep}` (binary search per print —
  order-independent, unlike a merge walk).
- `buildCvdPrefix()` → `state.idx.cvd[i + 1]` = cumulation THROUGH bar i (Float64Array, summed in
  bar order — the same arithmetic order as the loop it replaces, so the bits match).
- `buildFlowIndex()` → `state.idx.flowByCol = Map(col → events)`.
- hover's depth read now uses **`state.data.heatIndex.groups`** — the column index the RENDERER
  already builds (`math.heatColumns`). No second structure exists, so the layer that paints the
  cells and the layer that reports them can never disagree about which column it is.

Rebuild rules live in `setData()`: `bars || prints` → print buckets (bar boundaries define them);
`bars` → CVD prefix; `heat` → flow index. `drawRibbon()` also reads the shared prefix now (its
per-draw O(bars) rebuild is gone; `cvd[i + 1]` where it used to read `cvd[i]`).

**Two fixes rode along, both found in recon (§47).**
1. **Millisecond prints counted as zero.** The index normalises stamps with the `math.selectionStats`
   rule (`raw > 1e11 → /1000`); the live tape is seconds (`_live_tape_rows` divides `timestamp_ms`
   by 1000) so live numbers are unchanged, but a ms-stamped source used to silently read 0 prints
   in every bar while claiming the tape was from a different feed.
2. **The tape fetch asked for rows the route ignores**: `ofx-view.js` sent `?limit=200` while the
   route declares `count` (default 60, `le=200`) — the engine's print window was always 60 rows.
   Now `?count=200`: verified live, 60-request → 60 rows, 200-request → **200 rows**.

**The measured gate (sandbox :8093, synthetic 10 k prints / 300 bars / 30 k heat cells, 200 timed
`OFX.hover()` calls, same probes before and after).**

| | BEFORE | AFTER |
|---|---|---|
| hover p50 | 2.2 ms | 2.1 ms |
| hover p95 | **6.2 ms** | **3.3 ms** |
| hover max | 10.6 ms | 7.2 ms |
| 200 hovers, total | 556.7 ms | 442.8 ms |
| `setData` (once per payload) | 6 ms | 14.3 ms |
| `renderLayers(true)` frames | 4.0–16.8 ms | 4.1–16.8 ms |

**Correctness parity is exact** — the six probe samples (`x` = 40/100/200/320/500/700, `y` = 200)
agree byte-for-byte before/after: index 286/287/289/292/295/299 · prints 33 each · sweep
77.25/79/82.5/87.75/83.25/77.25 · depth 9/28.6667/20/30/14.3333/19.3333 · cvd 0/−3/−6/−3/−5/−3 ·
events 2. The honest reading of the timing: the three scans cost ~0.57 ms per move on this payload
(the rest of the 2.8 ms was level maths and object building), so p50 barely moves while p95 — the
sweep-tail this item exists for — nearly halves; the cost is now flat in tape/matrix size rather
than linear. `setData` pays ~8 ms once per 2.5 s poll for that.

**New selftest coverage (the first `hover()` coverage the file has ever had).** `ofx.selftest.js`
gains a P2-1 block whose oracle is the OLD algorithm written out verbatim: bucket parity for
prints/sweep, CVD prefix parity from bar 0, depth from the column groups, flow-by-column parity,
one end-to-end `hover()` read, the ms-stamp normalisation, and a bars-only rebuild check. **152 ok,
0 failed** (was 145).

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN**; `ofx selftest 152 ok, 0 failed`; 0 client errors in the sandbox log; sandbox killed,
port 8093 free.

**Files.** `ofx.js` (state.idx, three builders, setData calls, hover rewrite, ribbon prefix),
`ofx-view.js` (`?count=200`), `ofx.selftest.js` (P2-1 block, +7 checks).

**Limits, stated.** (a) `buildPrintIndex` assumes bars arrive in time order (the payload contract;
prints themselves may be unsorted — the binary search handles that). (b) The synthetic gate is a
desktop-class probe: the sandbox's own `renderLayers` timings are unchanged, as they should be —
this item moved hover work only. (c) p50's small delta is reported as measured, not rounded up
into a story.

## §49 — P2-2 recon: the heat pass at 30 Hz over an unchanged matrix

**The ask (sweep §4 R6, verbatim).** "Incremental heat decay; `Float32Array` heat wire format; coalesce
`hover()` into the rAF tick. Gate: `ofx.stats()` p95 under the same synthetic load must improve on
today's numbers (heat 3.58 ms / live 1.34 ms)."

**The baseline and its recipe (sweep §3, §8 — the gate must reuse these exactly).** heat **3.58 ms**
at 48 400 cells, every 33 ms — "~11 % of one core while the Engine view is open" (`SYSTEM_SWEEP_2026-09-15.md:207`);
live/sweep layer **1.34 ms**; the heat payload "136 KB of objects; a `Float32Array` + column/price
header would cut parse and GC" (`:209`); hover measured 0.12 ms/call at 1440 bars (`:210`). The
reproduction recipe is quoted in §8 (`time(heat, 10)` / `time(live, 5)` over `mk(1440, 200, 4000)`,
with `window.OFAP_PAUSED = true` so the view's 2.5 s poll cannot overwrite the injection).

**What the engine actually does today (`ofx.js`).**
- `tick()` (the one rAF loop, `:2,077-2,091`): `heatAccum >= 33 && state.data.heat.length` → set
  `dirty.heat` — **unconditionally, every 33 ms, for as long as a heat matrix exists**, whether or
  not anything changed. Renderer-busy or not, the pass runs.
- `renderLayers()` heat branch (`:2,028-2,047`): `clearRect` the whole canvas → `drawHeat(ctx)` →
  increment `heatPasses`. No version check, no change detection.
- `drawHeat()` (`:1,359-1,482`): binary-search the visible columns, then every visible cell goes
  through live-paint or the ghost branch — so the pass cost is proportional to VISIBLE cells
  (~10-15 k on a 48 k matrix), 30×/s.
- The ghost branch (`size == 0 && alpha > 0.004`, `:1,470-1,475`) is **unreachable from live data**:
  `math.adaptHeat` drops `value <= 0` (`:282`), and the server's `carry_forward` FORWARD-FILLS a
  vanished level with its last size (`depthmap.py:281-291`) rather than zeroing it. The fading-ghost
  machinery is exercised by synthetic zeros (the sweep decorated the matrix with them) and by
  `cell.peak`/`decayAlpha`, not by the live payload — worth knowing before optimising it.

**The lever the server already hands the UI.** The snapshot payload carries **`version`**
(`depthmap.py:306`) and its docstring says so: "the UI can use `version` to skip a repaint entirely
(see the reference layout heatmap author guide's front/back-buffer model)". Nobody reads it yet
(`grep version` under `desktop/ui/` — nothing). The cached-snapshot path re-serves an unchanged
`version` for an unchanged matrix, which is exactly the skip key R6 needs.

**Hover today.** The `mousemove` listener inside `attach()` calls `hover(...)` **synchronously per
event** — a fast sweep fires it many times per frame; P2-1 made each call cheap (p95 3.3 ms on the
10 k gate) but the call COUNT is still unbounded per frame.

**Decisions (do not re-open).**
1. **Heat passes become change-gated, not cadence-gated.** `dirty.heat = true` keeps its name but
   its meaning becomes "repair if needed": the pass runs a FULL repaint only when the heat epoch
   moved (new payload version, view transform, params, resize, expression) and a PATCH pass only
   while fading ghosts exist; otherwise the 33 ms tick does not even set the flag. The full pass
   keeps today's code path (and its cost), so the win is frequency, not per-pass magic — and the
   gate's forced-dirty recipe then measures a no-op when nothing changed, which is the item's own
   language ("only cells whose alpha actually moved").
2. **`version` is threaded through**: `ofx-view` passes `heat.version` into `setData`; a repeated
   version does not bump the epoch (the server's cached-snapshot case). A payload WITHOUT a version
   behaves like today (every delivery bumps) — synthetic tests stay honest.
3. **Ghost patches are bounded and per-cell**: the full pass rebuilds a list of visible ghosts
   (cell + its screen rect); the 33 ms tick patch-repaints only those, and only when a quantised
   alpha step actually changed; a ghost that drops below the 0.004 floor gets its rect cleared and
   leaves the list. `heatPatches`/`heatSkips` join `heatPasses`/`decayCells` in `stats()`.
4. **`resize()` must bump the epoch** — it sets `canvas.width`, which CLEARS the canvas; with
   change-gating a resize without a bump would leave a blank heat layer. Same for `setParams`
   (lambda changes the decay curve; ramp changes the palette — neither dirties heat today) and
   `setExpression` (already dirties).
5. **Hover coalescing**: the `mousemove` listener stores `pendingHover` + `dirty.live`; `tick()`
   runs `hover()` once, immediately before `renderLayers`, so the HUD paints the newest position.
   The selection-drag path keeps its direct `renderLayers` (it is a drag, not a hover).
6. **The `Float32Array` wire waits for its number** (canon §8: "heat-wire formats wait for a number
   that demands them"). Recon measures JSON parse + `adaptHeat` for the live 136 KB payload
   in-page; if that lands under ~5 ms per 2.5 s poll it is deferred WITH the measurement in §50,
   not built on principle.

**Build spec.** `ofx.js`: heat epoch state + `heatNeedsPass()` gate in `tick()`; renderLayers heat
branch full-vs-patch-vs-skip; `drawHeat` records the painted epoch and rebuilds the ghost list;
`patchHeat()` patch pass; `resize`/`setParams` bumps; hover coalescing (listener + tick).
`ofx-view.js`: pass `heat.version`. Tests: `ofx.selftest.js` — epoch-gating unit checks (paint once,
no-op seconds, version reuse skips, resize forces), ghost patch parity (a synthetic zero-cell fades
and its rect clears), hover coalescing (pend + one tick = one hover). Gate harness: the sweep's
recipe before/after, plus a steady-state number and a full-pass number so frequency and per-pass
cost are reported separately.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN; nineteen selftests (ofx 152).

## §50 — P2-2 build: the heat pass stopped running on a stopped matrix (R6)

**What changed.** Three things, one of them with a measured deferral.

1. **The heat layer is change-gated, not cadence-gated.** `state.heatEpoch` moves on a new payload
   version, a view transform, a resize, a parameter or an expression change; `renderLayers`' heat
   branch then paints in full only when the painted epoch lags. `tick()`'s 33 ms cadence asks first
   ("did anything move?") and leaves the flag alone when the answer is no; a forced pass with
   nothing changed counts itself a **skip** (`heatSkips`) instead of a repaint. `resize()` bumps the
   epoch because `canvas.width = …` clears the canvas — the one place where "nothing changed" would
   have been a lie. The server's own `version` field is threaded from ofx-view through `setData`:
   a repeated version (the cached-snapshot case the depthmap docstring invites clients to use) does
   not repaint; a payload without a version always rebuilds, so synthetic tests stay honest.
2. **Ghost decay became a patch pass.** A full pass remembers every fading cell WITH its screen
   rect; `patchHeat()` then repaints only ghosts whose quantised alpha actually moved (≥ 0.008),
   each inside its own rect on the existing canvas, clears a ghost's rect when it dies below the
   0.004 floor, and paints nothing at all when nothing moved. Cost is proportional to what is
   fading, not to what is on screen.
3. **`hover()` is coalesced into the frame.** The `mousemove` listener stores `pendingHover`; the
   tick runs `hover()` once with the newest position, immediately before the layers paint. A fast
   sweep no longer pays one hover per raw pointer event.
4. **`adaptHeat`'s merge keys are numeric.** The old pass built a string key per wire cell
   (`'12|114.39'`) and sliced it apart again; now `barIndex * 1e5 + Math.round(price / step)` with
   the record carrying the price, and the per-column linear scans are binary searches. Off-grid
   float noise now merges with its grid neighbour instead of making a twin row.

**The measured gate (sandbox :8093, same synthetic load both runs: 48 400 cells / 1 440 bars /
4 000 prints, 450 cells visible in the fitted view; the sweep's §8 recipe method).**

| Same load | BEFORE | AFTER |
|---|---|---|
| recipe `heat()` — forced dirty, matrix unchanged | 0.36 ms | **0.02 ms** (counted skip) |
| one real heat repaint (epoch bump, no setData) | 0.36 ms | **0.12 ms** |
| `live()` — sweeps + HUD (recipe method, warm) | 1.52 ms | 1.00 ms (median of 3 rounds; 1.63/1.00/0.97) |
| `adaptHeat`, 48.4 k cells, 3-call average | **36.47 ms** | **25.50 ms** |
| `JSON.parse` of the 842 KB wire | 1.53 ms | 2.37 ms (unchanged code, noise) |
| `setData`'s heat component per payload | (in the old 6–14 ms composite) | 2.6 ms |

**The frequency number is the real win:** the heat pass used to run 30×/s for as long as a matrix
existed — 3.58 ms at 48 k cells on the sweep's own measurement, ~11 % of a core, forever. It now
runs once per payload (0.4×/s at the view's 2.5 s poll) plus patch passes while something fades.

**The `Float32Array` wire — measured, and deferred WITH its number (canon §8).** The sweep expected
"parse and GC" to be the cost. Measured: `JSON.parse` is **1.5–2.4 ms** for 842 KB — not the
problem. The problem was `adaptHeat` (36.5 → 25.5 ms after the numeric-key rewrite; the residual is
per-cell object + Map allocation, ~0.5 µs/cell). A typed wire would delete exactly that allocation —
so the item now has its trigger number instead of a hunch, and the transport rewrite is a follow-up
card rather than a rushed change in this pass. Stated plainly: one third of R6's named scope is
deferred, and this paragraph is why.

**New selftest coverage: 152 → 169 checks (all green).** The first heat-gate and coalescing coverage:
a stubbed heat canvas counts full clears vs rect clears; a new version paints once; an unchanged
epoch is a counted skip; a repeated server version does not bump; resize and lambda changes do bump;
a ghost patch-repaints only on quantised movement, keeps its alpha, and clears its rect on death;
`adaptHeat` parity for merge/summation/events/float-noise/boundary buckets; and `mousemove` pends
(newest wins) without running hover per event, with out-of-canvas moves ignored.

**Files.** `ofx.js` (state epochs + ghosts + pendingHover, `markHeatFull`, setData versioning,
markViewDirty/resize/setParams/setExpression bumps, renderLayers heat branch, tick gate + hover
consumption, drawHeat ghost rects, `patchHeat`, stats fields, adaptHeat rewrite), `ofx-view.js`
(version threading), `ofx.selftest.js` (+17 checks).

**Limits, stated.** (a) The patch pass clears each ghost's rect; with the 1 px minimum row height a
rect can nibble a neighbour's edge pixel — accepted, invisible, noted. (b) The ghost path is still
synthetic-only in live data (`carry_forward` forward-fills; `adaptHeat` drops zeros) — R6 made it
cheap and tested, not live; that is the separate carry-forward item. (c) rAF can be dead in a
headless page, so the tick's own consumption of `pendingHover` and the cadence gate are pinned by
the selftest and the code path, not by a real frame loop in the sandbox. (d) The sweep's 3.58 ms
was measured at ~10–15 k visible cells; this pass's matrix shows 450 in the fitted view, so the
BEFORE/AFTER pair above is the comparison, with the sweep's figure quoted as the historical
reference for the same code.

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN**; `ofx selftest 169 ok, 0 failed`; 0 client errors in the sandbox log; sandbox killed,
port 8093 free.

## §51 — P2-3 recon: the yielding question is a measurement, and nothing else

**The ask (plan §2, verbatim).** "**P2-3 · Heat-layer yielding — conditional.** S. Render heat in one
rAF and base+live in the next *only if* a 30 k-cell / 4K measurement crosses the 16 ms frame budget.
Norm: defer complexity behind a measurement (§3.8). Gate: the measurement itself."

**What "the measurement" has to be, stated before taking it.** Post-P2-2 the only heavy frame the
engine can produce is a **payload-arrival frame**: `setData` dirties all four layers, so heat + base +
live + ribbon repaint inside one `renderLayers()` call at 4K (3840×2160) with a 30 k-cell matrix.
Steady-state frames are already gated to near-zero (§50). So the number that decides this item is
that one frame's cost, compared against the 16 ms budget — plus its heat/live decomposition so a
"yes" would know where to yield (heat first, base+live next).

**What exists to yield with (if the number says yes).** The scheduler already has the shape for it:
`renderLayers()` takes an explicit job list; `tick()` calls it once per frame; every layer is
independently dirty-flagged. The minimal yielding change would be: when a frame's job list contains
heat AND (base or live) AND the frame budget is at risk, paint heat this frame and leave base+live
dirty for the next tick — with stats telling the truth about the split (a `yielded` counter, and the
frame's `lastMs` still the real cost of what it painted).

**What the plan itself says about the bar.** Brief §6: "The engine is Canvas2D by design (4.5 ms full
repaint, 3 layers, 200 bars × ~128 levels). Revisit only for > 2 k simultaneous cells or forced
4K/144 Hz". The sweep's optimised per-cell constants: 0.074 µs/cell heat after the palette LUT, 1.34 ms
live repaint. On those numbers a 30 k-cell matrix is ~2.2 ms of heat work plus canvas clear costs —
which is why the item is phrased as *conditional*: the honest expectation is a sub-budget frame, and a
custom yielding layer would be complexity nobody asked for. This pass will not build it on a hunch —
the measurement is the deliverable either way, and if it lands under budget the item closes as a
measured no-op with the numbers recorded.

**Also noted, for the record.** Brief §6 flags "4K at Windows 150% scaling is untested; fractional DPI
costs a full re-raster on resize". The resize path (`ofx-view.js:707/770/777/846` → `OFX.resize(w, h)`)
uses the stage element's CSS pixels — the app does not multiply by `devicePixelRatio`, so a 4K screen
at 150 % presents a ~2560×1440 canvas, and the 3840×2160 case measured below is the DPR-1 worst case,
not what that machine runs. The canvas is whatever `resize()` is handed; the measurement uses both.

**The recipe (sandbox :8093, both runs on the same page).**
1. Build the §50 synthetic load: 1440 bars × 200 levels × 4000 prints; 30 k heat cells (150 columns ×
   200 rows) shaped like the live matrix, sized so a 4K viewport actually shows ~30 k of them.
2. `OFX.resize(3840, 2160)`; verify the canvas dimensions took (`state.view.width/height`).
3. Set the view (scaleX/scaleY/offX/offY) so the matrix fills the viewport; count visible cells
   through the same cull `drawHeat` uses.
4. Time, 3 rounds each, with a fresh heat version per round:
   (a) the full arrival frame — `setData(heat vN)` + `renderLayers(false)` with all layers dirty;
   (b) heat alone — epoch bump + heat-only job;
   (c) live alone — the sweep recipe's `live()`.
5. Verdict rule: (a) ≤ 16 ms → P2-3 closes as a measured no-op. (a) > 16 ms → build the yield split
   (heat this frame, base+live next), re-measure, and require (a-split) frames under budget with the
   same picture.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN; nineteen selftests (ofx 169).

## §52 — P2-3 build: the frame yields, and the number said it had to

**The measurement crossed the bar (§51's rule applied).** 30 000 cells, all visible, canvases
3840×2160 (`dims` verified for all three layers): one payload-arrival frame measured **17.5 ms** —
over the 16 ms budget — decomposed heat **6.8** + base **5.9** + live **1.57** + ribbon **0.77**.
So P2-3 built the yield.

**What changed (`ofx.js`, ~20 lines).** `renderLayers()` now walks its job list with an index and,
once a frame has painted something and spent `YIELD_MS = 6` ms (a third of the 16.7 ms budget),
**breaks before the next layer**: the deferred layers keep their dirty flags, so the next tick — one
rAF later — re-queues and paints them. A single-layer job can never yield (nothing to defer to), and
the two-tick picture is identical, one frame later. `stats()` gains `yields` so the split is visible,
and every frame's `lastMs`/p95 remains the REAL cost of what that frame painted.

**Same-session A/B (the honest pair — earlier cross-session numbers wobbled ±30 % with page state,
so the pre-build file was swapped in briefly and the identical script run on the same page).**

| Arrival frame(s), warmed, same page | PRE-YIELD | POST-YIELD |
|---|---|---|
| frame 1 | **13.9–14.1** (cold 20.1) | 11.5–12.4 (cold 17.1) |
| frame 2 | — (nothing left) | 6.0–8.1 |
| frame 3 | — | 0.3–1.5 |
| max frame | 14.1 (20.1 cold) | **12.4 (17.1 cold)** |

**The honest read.** The stacking is gone — nothing ever adds base+live to the heat frame again, so
the worst warm frame is the heat pass itself (~11.5–12) and the rest drains in two small frames. The
cold first arrival still touches ~17 ms because the heat pass alone at 4K/30k is the remainder, and
**no frame split can divide one layer** — that residue is exactly what brief §6's revisit condition
(>2 k simultaneous cells / forced 4K) hands to P3-1's trigger, not to more splitting. Per-frame p95
under the same load: 12.4 vs 14.1 warm, 17.1 vs 20.1 cold.

**Picture parity.** After the split, a subsampled ink scan of all three 4K canvases: heat 836, base
12 361, live 10 sample hits — every layer painted; nothing ended up blank when its frame was deferred.
(The live layer's ink is genuinely sparse — a handful of sweep bubbles — in both the 4K and the fitted
view; checked both.) Two earlier probes that read zero were my own geometry mistakes (a centre crop
that missed the heat band; a centring computed for the wrong price), not the engine — recorded so the
next reader does not chase them.

**New selftest coverage: 169 → 174 (all green).** The yield's contract is pinned with a stubbed heat
canvas that spends 7 ms in its first clear: the frame defers base+live (yields +1, flags left SET),
the next frame finishes them and clears the flags, a fast frame paints the whole job in one pass, a
single-layer frame never yields even when slow, and `stats()` reports `yields`. The stub uses a
self-returning callable Proxy for the 2D context — fifty no-ops for free.

**Files.** `ofx.js` (YIELD_MS, the renderLayers loop + yield, stats.yields), `ofx.selftest.js` (+5).

**Gates after the build (measured this pass).** pytest **572 passed / 2 skipped**; `audit_ui_refs.py`
**AUDIT CLEAN**; `ofx selftest 174 ok, 0 failed`; 0 client errors in the sandbox log; sandbox killed,
port 8093 free.

## §53 — P3-2 recon: the session boundary and the 807 MB that nobody prunes

**The ask (plan §2 P3-2, verbatim).** "P3-2 · Session model (R4) and storage retention (R5). M"
— rendered in the plan as: "sessions at the UTC boundary; make the boundary a config value and
compute profiles per session. Retention: no pruning exists — 5.8 M rows / 547 MB and ~4.5 M rows/day;
add an age/size retention job with incremental vacuum and surface the DB size in Logs. Gate: unit
tests on the session-window function; run retention, read row counts and file size before/after."

**The number has moved.** The live DB at `%APPDATA%\\OrderFlowAnalysisPro\\orderflow_data.db`
measured **807 755 776 bytes (807.7 MB) today**, up from the sweep's 547 MB five days of uptime ago —
the growth estimate is holding. There is still no retention path anywhere (`database.py`, `main.py`,
`desktop/`).

**What exists — session side.**
- `main.py:_rebuild_volume_profile` (`:677-692`): takes `now_ms - 24 h` of 1 m candles and labels
  the profile `session_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")` — a rolling 24 h
  window wearing a calendar-day name. At the UTC boundary the "day's" value area mixes two sessions;
  anything else would need the label to lie differently.
- `analytics/volume_profile.py` carries `session_date` strings through
  `compute_from_candles/ticks` and `combine_profiles` (which merges labels into
  `"{first}_to_{last}"`); `atlas/profiles.py` exposes them read-only. No other session semantics
  exist anywhere — no session-window function, no boundary config.

**What exists — storage side.**
- Schema: `ticks(id, instrument, timestamp_ms, price, size, side, trade_id)` with the index
  `idx_ticks_instrument_ts(instrument, timestamp_ms)`; `candles` (idx by instrument+ts+tf),
  `volume_profiles`, `signals`, `trade_journal`. Insert path: batched every 100 ticks
  (`main.py:_handle_tick`).
- Pragmas (`database.py:26-34`): `journal_mode=WAL`, `busy_timeout=15000` (plus the P1-era
  `synchronous=NORMAL` note). **No `auto_vacuum`** — so a delete alone will never shrink the file;
  `PRAGMA incremental_vacuum` is a no-op until the DB is converted once with a full `VACUUM`.
- The periodic home exists: `main.py:_periodic_tasks` (`:628+`) — a 10 s loop that already flushes
  tick buffers and rebuilds the VP hourly. A retention pass slots in as one more interval block.
- Surfacing: the Logs view renders from `GET /api/control/logs` (`ui.js:1227` `loadLogs()`,
  clear at `:1238`); the storage numbers have no route and no line anywhere.

**Decisions (do not re-open).**
1. **One session function, one config value.** New `analytics/session.py`:
   `session_window(now_ms, start_hour) -> (start_ms, end_ms, label)` — pure UTC, boundary hour on the
   most recent day at or before `now`, label = the session's start date (`YYYY-MM-DD`, the same
   string shape `session_date` always carried, so stored profiles stay comparable). Config:
   `data.session_start_hour`, default 0 (UTC midnight), clamped 0–23, junk falls back to 0.
   `_rebuild_volume_profile` fetches `[session_start, now)` candles and labels with the window's
   label — the boundary mixing dies there.
2. **Retention is age-based on `ticks` only** (the table that grows: 1 m candles × 3 symbols ≈ 4 k
   rows/day, signals smaller). Config `data.retention_days` (default 30; 0 = keep forever) and
   `data.prune_interval_hours` (default 6; the first pass prunes at system start).
3. **Batched deletes through the existing index** — SQLite here has no `DELETE … LIMIT` (not
   compiled in), so each batch is `DELETE FROM ticks WHERE rowid IN (SELECT rowid FROM ticks WHERE
   instrument = ? AND timestamp_ms < ? LIMIT 50000)` — per instrument, because the index leads with
   `instrument`. One commit per batch; the writer never blocks for long.
4. **Vacuum is explicit.** First prune after the config lands: convert once
   (`PRAGMA auto_vacuum=INCREMENTAL` + full `VACUUM` — bounded, logged, once), then
   `PRAGMA incremental_vacuum` after every prune. If the conversion fails on a locked DB it is
   reported and retried next interval, never faked.
5. **Numbers surfaced where the user looks for them**: `GET /api/control/storage` (30 s cache —
   `COUNT(*)` over 8 M rows is not free) → `{db path, bytes, wal bytes, per-table counts,
   oldest/newest tick, retention settings, last prune summary}`; `POST /api/control/storage/prune`
   runs one pass now (the gate's trigger, and a real button later); one line in the Logs panel.
6. **Gate**: unit tests on `session_window` + a VP comparison across a simulated boundary (R4);
   retention run against a COPY of the live 807.7 MB DB with row counts and file size read back
   before/after (R5), plus a live sandbox pass for the route + the panel line.

**Gates at recon time.** pytest 572/2; `audit_ui_refs.py` CLEAN; nineteen selftests (ofx 174).

## §54 — P3-2 build: the session has a boundary, the database has a window

**R4 — session model.** `analytics/session.py` is new: `session_window(now_ms, start_hour)` returns
`(start_ms, end_ms, label)` — the boundary hour on the most recent day at or before now, UTC, with the
session's start date as the label (`YYYY-MM-DD`, the shape `session_date` always carried, so stored
profiles stay comparable). Junk hours fall back to 0 rather than raising (it reads config).
`_rebuild_volume_profile` now fetches `[session_start, now)` candles and labels them with the window —
the rolling 24 h wearing a "today" label is gone. Config: `data.session_start_hour` (default 0),
clamped by the pure `clamp_data_settings()` the tests call directly.

The boundary demonstration is a test, not a claim: with sessions at 100.0 and 110.0 across a simulated
UTC midnight, the mixed profile (old behaviour) POCs at **100.0** while the windowed profile POCs at
**110.0** and contains only the new session's candles.

**R5 — storage retention.** The copy of the live DB spans 2.15 days at **7 810 787 tick rows**; the
job is now real:

- `database.prune_ticks(cutoff, instruments, batch)` — per instrument (the index leads with it), in
  50 k-row rowid-subquery batches (this SQLite has no `DELETE … LIMIT`), one commit each.
- The instrument list comes from the DB itself (`SELECT DISTINCT instrument FROM ticks`), not from the
  boot's enabled symbols — the first draft pruned only BTCUSDT, caught before the gate.
- Vacuum: one-time `auto_vacuum=INCREMENTAL` + full `VACUUM` on the first prune that deletes anything
  (`vacuum: converted`), then `PRAGMA incremental_vacuum` + **`wal_checkpoint(TRUNCATE)`** per pass.
- The job lives in `_periodic_tasks` (first pass at engine start, then `data.prune_interval_hours`,
  default 6 h; `retention_days: 0` disables). It never kills the loop: failures warn and retry.
- Surfacing: `GET /api/control/storage` (30 s cache; counts need the engine, sizes never do — and with
  the engine stopped the RETENTION line reads the config file, not the Python defaults, because a
  display lie is a lie), `POST /api/control/storage/prune` (409 without an engine), and one live line
  in the Logs panel.

**The gate, at real scale (a copy of the live 807.7 MB DB; the original verified untouched at
807 755 776 bytes after the pass).**

| | before | after |
|---|---|---|
| ticks | 7 810 787 | 2 264 231 (−4 446 640) |
| plain `.db` | 808.6 MB | **336.4 MB** |
| `.db` + WAL footprint | 845.5 MB | **336.7 MB** (after the checkpoint fix) |
| pass time | — | **15.6 s** (delete + convert + vacuum) |
| second pass | — | 769 boundary rows, `vacuum: already`, 0.4 s |

Live reads: the Logs line renders `storage: 336.8 MB · 2.3 M ticks · keep 1 d · last prune −33 rows`,
and the −33 is the periodic job's own unattended pass. Two fixes came out of the gate itself: the
WAL balllooned to 677 MB mid-prune until `wal_checkpoint(TRUNCATE)` was added (the file "shrank"
while the footprint did not — the exact kind of half-truth this program keeps deleting), and the
stopped-engine retention display read defaults instead of the config.

**The default that had to change.** Retention shipped at 30 days until the gate arithmetic: 2.15 days
measures 808 MB, so ~376 MB/day — 30 days is an **~11 GB** steady state, wrong for this app. The
default is **7 days (~2.6 GB)** in `settings.py`, the config block, the clamp and the tests.

**Behaviour change for the owner's install, stated plainly.** With no `data` block in
`%APPDATA%\\OrderFlowAnalysisPro\\config.json`, the next launch applies the 7-day default; **nothing
in the current DB is older than that**, so the first live prune deletes nothing today and the DB holds
at 7 days going forward. `"retention_days": 0` in the config keeps everything. The retention job only
ever touches `ticks`; candles, signals and volume profiles are kept (tiny, and history the profiles
need).

**Files.** New: `analytics/session.py`, `test_session.py` (6), `test_retention.py` (3). Edited:
`config/settings.py`, `data/database.py`, `main.py`, `desktop/engine.py` (`clamp_data_settings`),
`desktop/config_store.py` (`data` block), `desktop/api.py` (storage routes), `ui.js` +
`index.html` (the Logs line).

**Gates after the build (measured this pass).** pytest **580 passed / 2 skipped** (572 + 8); `audit_ui_refs.py`
**AUDIT CLEAN**; nineteen selftests green; 0 client errors in the sandbox log; sandbox killed, port free,
the 800 MB sandbox copy deleted.

## §55 — P3-3 (R7) build: the legacy page retires behind a redirect

**The decision (the owner's, from the retirement options laid out in the session).** The legacy
dashboard page — `dashboard/static/index.html` + `app.js` + `style.css`, the one-screen "Orderflow
Trading Terminal" with its 1 s whole-series price chart and scanner — stops being the front door.
**Redirect**, not delete: `GET /` answers **307 → `/desktop`**, the desktop shell. Reversible by
deleting one block; nothing on disk removed.

**Why redirect was the right shape.** Recon found the retirement is nearly free: the desktop server
is built ON the dashboard app (`launcher.py` imports `dashboard.app.app`, includes the control/atlas/
fundamentals routers into it, and mounts the shell at `/desktop`), and **six of the nine static
files are shared modules the desktop UI loads itself** (`footprint.js`, `orderbook.js`, `tape.js`,
`signals.js`, `performance.js`, `microstructure.js` — `desktop/ui/index.html:818-823`). Only the
three shell files are "the page", and both of its panels are superseded (the desktop's chart view
with the expression modes; the rebuilt scanner). The legacy page also still works standalone
(`main.py`'s own dashboard), which is why the redirect lives in the LAUNCHER — the standalone
dashboard is not redirected to a path it does not mount.

**The build.** One block in `launcher.build_app()`, inside the desktop-mount guard (now idempotent —
a second call no longer double-mounts): remove the dashboard app's own `GET /` route, register
`legacy_root_redirect()` returning `RedirectResponse("/desktop", status_code=307)`. 307 preserves the
method and is not sticky-cached, so undoing the retirement is deleting the block.

**The gate (live, sandbox).** `GET /` → **307**, `location: /desktop`; following it lands on the
desktop shell (`ModFlow OrderFlow Analysis Suite`, and *not* "Orderflow Trading Terminal") — pinned
as a test as well (`test_wiring.py::test_legacy_root_redirects_to_the_desktop_shell`, via
`TestClient(build_app(8099))`). The static files remain served (shared modules); the standalone
dashboard keeps its own page.

**Gates after the build (measured this pass).** pytest **581 passed / 2 skipped** (580 + 1);
`audit_ui_refs.py` **AUDIT CLEAN**; nineteen selftests green.

## §56 — the deferred Float32Array wire + the carry-over list: recon and decisions

**A. The heat wire (deferred from §50 with its number).** §50 measured `adaptHeat` at 36.5 → 25.5 ms
per 48.4 k-cell payload after the numeric-key rewrite; parse was only ~2 ms. The residual is the
per-cell work: JSON arrays-of-arrays traversal, `Number()` conversions, the Map merge, and — found in
this recon — **two allocations per cell** (`acc.set(key, {v, price, col})` and then a second row object
in the row-build loop). Decisions:
1. **Halve the allocations in the JSON path first**: the Map value IS the row object (mutated
   `size +=`), pushed directly — one object per cell, same merge semantics.
2. **A binary sibling route** `GET /api/atlas/heatmap/{symbol}/bin` (atlas/api.py, same params):
   `atlas/wire.py:pack_heatmap_bin(snapshot) -> bytes` — magic `OFHB` + u32 header length + header
   JSON (symbol, version, step, tick, cols, rows, carry_forward, carried_cells, scale_max,
   wall_age_ms, walls, events, traded flag, note) + sections: buckets `f64[cols]` (epoch ms —
   Float32 cannot hold them exactly), prices `f32[cols×rows]`, values `f32[cols×rows]`, traded
   `f32[cols×rows]` (skipped when absent), best as 12 B/col (`f32 bid, f32 ask, i32 trades`). JSON
   events/walls ride in the header — they are small and keep one source of truth.
   `Response(media_type="application/octet-stream")` + `Cache-Control: no-store` on the response.
3. **The client** (`ofx.js math`): `decodeHeatBin(buffer)` (DataView header, `slice`-copied typed
   sections so alignment is guaranteed) and `adaptHeatBin(decoded)` producing the SAME
   `{rows, scale, traded, best, events, version}` shape with the same numeric-key merge and the same
   `mapCol` fallback; `ofx-view.load()` fetches the bin route with a **raw fetch and JSON fallback**
   on any failure. `heatmap-pro.js` / `atlas.js` keep the JSON route (their DOM paths were never the
   measured cost).
4. **Gates**: a Python round-trip test (pack → decode → sections equal the dict), a node parity test
   (a fabricated bin buffer through `decodeHeatBin`+`adaptHeatBin` deep-equals `adaptHeat` on the
   equivalent dict, empty case included), and a live sandbox measurement of the real hub payload both
   ways.

**B. Carry-overs, by site.**
1. **Chart's newest bar loses expression colours between polls.** `ui.js:403` — the WS `candle`
   handler calls `S.candleSeries.update({time, open, high, low, close})` plainly. The broadcast
   payload also carries `volume` and `delta` (main.py:565-573), and the expression module
   (`E.chartBars`) is already in scope at other call sites in the same file. Fix: run the single bar
   through `E.chartBars([bar], {mode, palette, theme})[0]` before `update()`, falling back to the
   plain point when the expression module or data is missing. Gate: live — with a delta/expression
   mode set, the newest bar's `color`/`borderColor` as returned by `series.data()` must match the
   mode after a `candle` broadcast.
2. **Three `window.prompt` sites.** `drawings.js:365` (Edit text…, inside the draw context menu),
   `drawings.js:417` (the text tool's canvas click), `menubar.js:562` (workspace save as). The house
   pattern already exists twice: `menubar.js:276 askText()` renders an in-place editor INSIDE the open
   menu (used by the layout menus), and heatmap-pro's note field commits without any dialog. Fix:
   menubar's own site uses `askText` directly; the two drawings sites get a small in-place editor
   drawn into the draw-menu (an input + Apply/Cancel row, Enter/Esc/blur semantics) — no system
   dialogs, nothing that can silently no-op in the frozen WebView.
3. **Bus chip `sub` count.** `bus.js:344-346 summary()` reads `telemetry().subscribers` — the same
   `subscriberCount()` the tests compare against — and the comments at `:134-178` record the
   announce-after-join fix that closed the old drift. Verdict: likely already fixed; **verify live**
   (chip text vs `OFAPBUS.telemetry()`), and close the carry-over row as already-fixed with the
   evidence if it holds.
4. **Alerts card has no "new rule" affordance.** The rules table (`atlas.js` `AL.rules`,
   `renderRuleRows`, the row-replacing editor `openEditor(id)` — P1-7) can edit existing rules and
   save via `POST /api/atlas/alert-rules` (`:780-783`, upsert by id). Fix: a "+ New rule" button in
   the rules head that pushes a DRAFT rule (`ui-<ts>` id, first kind from `F.kinds()`, `enabled:
   false`, `channels: ['ui']`, empty params), opens the existing editor on it, and drops the draft
   from the list if the editor is cancelled (a draft must never silently become a saved rule).
5. **`wall` kind has no live detector.** `atlas/alerts.py` already matches `kind == "wall"`
   (size ≥ min_size) but `depthmap.py` only ever emits `wall_age` (and stack/pull). The ingest block
   (`:164-195`) already computes the quantile threshold and tracks `_walls`/`_wall_first`. Fix: emit
   `wall` **on entry** — a price whose previous size was below the threshold and whose current size
   meets it — with the visible-book share in the detail. Entry-triggered, so a standing wall fires
   once and `wall_age` keeps the hold. Gate: a unit test feeding two synthetic snapshots (below →
   above) asserts exactly one `wall` event with the share, plus the no-requalify case.
6. **Watchlist configured-instrument rows.** Verification-only, per the RECIPE row: add a symbol to
   the sandbox config's instrument list, reload, and the watchlist must show its row beside the demo
   set. No code change unless the row is missing.

**Gates at recon time.** pytest 581/2; audit CLEAN; nineteen selftests (ofx 174).

## §57 — the Float32Array wire (measured, kept as machinery), the carry-over list, and two defects the live gate found

**The wire, built and then measured out of the default path.** `atlas/wire.py:pack_heatmap_bin`
(magic `OFHB` + u32 header length + header JSON + f64 buckets + f32 prices/values/traded + 12 B best
per column) serves `GET /api/atlas/heatmap/{symbol}/bin`; `math.decodeHeatBin` / `adaptHeatBin` read
it; `test_heat_wire.py` round-trips the layout and the ofx selftest pins bin-vs-JSON parity. The live
sandbox then priced it: **json parse+adapt 0.8 ms vs bin decode+adapt 0.7 ms at 29 k cells (610
rows), and 1.7 vs 1.2 ms at 51 k cells** — and **the bin is BIGGER than the JSON on sparse books**
(229 KB of JSON vs 296 KB of bin: fixed 4 B per cell per section beats nothing when most cells are
`0,`). The verdict: the JSON route stays the engine view's path (the view was reverted to it); the
wire stays on the shelf, tested and one fetch away, with its trigger written down — **re-measure when
a snapshot's JSON text passes ~2 MB or an adapt pass passes ~8 ms**. The §50 number that motivated
the wire (adapt 25.5 ms / 48.4 k cells) did not survive §56's own rewrite of the adapter; that is
stated here so nobody quotes it again.

**The defect the wire's parity gate exposed — the depth payload's axes.** The snapshot contract is
`values[PRICE ROW][TIME COLUMN]` with `prices` the flat ladder (`depthmap._build_snapshot`:
`values = [[0.0] * len(cols) for _ in range(rows)]`, `prices = [price_min + i * step …]`), and
`heatmap-pro` has always read it that way (`vals[ri][ci]`). **`adaptHeat` had the axes transposed** —
it iterated the outer array as columns, so a live payload was drawn as "the first ~33 price rows at
the bottom of the ladder": the heat sat in the wrong price band, and §52's "ink probes read 0 twice /
heat centred on the wrong price" were **this defect**, not a crop mistake (that §52 note is hereby
corrected). Fixed in `adaptHeat` (row-major: price row outer, bucket column inner, per-column price
fallback kept) and every fixture in the selftest rewritten to the real contract. Live A/B on the same
payload: **old rows n=253 median 75 808 (ladder bottom 75 780.6) vs new rows n=483 median 75 846 —
the ladder mid — with the live best bid/ask at 75 844.3/75 844.4**; the view's own render path
(`setData` with spanning bars) produced 939 rows centred on the book and the heat layer painted
(`heatPasses` 35→36). The wire packer/decode were built on the same contract; the ofx selftest now
pins the row-major fixtures, both modes, and the bin↔json deep-equality.

**The bus fetch wrapper ate binary bodies (found live).** `bus.js` wraps `window.fetch` for
`/api/atlas/` and reads every response as JSON — for the octet-stream `/bin` payload that consumed the
body and the non-JSON fallback then handed the caller the **consumed** original: every bin fetch died
with `body stream already read` and the engine view silently fell back (a fallback that worked only
because the view still had the JSON path). Fixed: non-JSON content types now pass through **unread**,
each caller gets its own `response.clone()`; the JSON-parse-failure branch returns an empty rebuilt
body instead of a consumed response. `bus selftest 13 ok, 0 failed`.

**The new-rule affordance, and the silent no-op it uncovered.** `+ New rule` (index.html, bound in
atlas.js) pushes a draft (`ui-…`, first kind from `F.kinds()`, disabled, `channels:['ui']`) and opens
the existing row editor; cancelling drops the draft. Live: the draft→editor→save flow first **no-opped
in total silence** — the rules auto-refresh adopts the server list (line 634's direct
`AL.rules = r.rules || []` — `alAdopt`'s guard alone was not the site) and clobbered the draft out of
`AL.rules` seconds after it was created, so `saveRule` found no stored rule and returned. Both adopt
sites now preserve drafts. Live, after the fix: banner `saved · Big trade — at least 1.00K in size ·
any level · UI log only · no cooldown`, the server list at 17 with `P56 live check` (kind `big_trade`,
`min_size: 1000`); cancel took the row count 18→17 with no draft left.

**The rest of the carry-over list, verified live.**
- **Chart's newest bar keeps its expression colours** — the WS `candle` handler now paints the single
  bar through the same `E.chartBars` pass as the full repaint (plain-bar fallback on any throw). The
  audit resolves the call; the broadcast payload carries `volume`/`delta` (main.py:565-573); the
  handler's own live wake-up is **not observed** — the WS lives in `ui.js`'s closure with no reachable
  handle for a second listener, so this one is verified by audit + the expression suite, stated as such.
- **All three `window.prompt` sites are gone.** The workspace name now goes through the menubar's own
  `askText` (in-place, in the open menu; both workspace items set `keepOpen` — without it the menu
  closed before the editor could render). Live: File → Save workspace opened the in-place editor, Apply
  saved `P56 live workspace` to `/api/control/workspaces` (view + ofx params + stamp). The two drawing
  text sites use a new `inlineText` editor: the draw menu gets an input row (Enter/Apply/Esc/×; the
  menu stays open), the canvas text tool gets a floating field at the click point (Apply/Enter commits
  and finishes the figure; Esc/× removes the placeholder). Live: menu path — editor prefilled
  `P56 inline`, Apply → text updated, menu closed; canvas path — float appeared, Enter committed
  `{kind:'text', text:'P56 inline'}`; both editors gone after commit. `window.prompt` now appears only
  in comments (5 references, all copy explaining why it is not used).
- **Bus chip** — live `bus: 1 sub · 1 ch · 1 fetches` against `telemetry()` `{subscribers: 1,
  channels: 1}`: they agree. The §29 mismatch row was stale (the announce-after-join fix closed it);
  row retired with this evidence.
- **`wall` kind has a live detector** — `depthmap` now emits a `wall` event when a price ENTERS the
  quantile band (previous size below the same threshold), carrying its share of the visible book in the
  detail; a standing wall fires once and `wall_age` keeps the hold. Unit-pinned (entry once, no
  re-fire, fresh crossing adds exactly one); live: **76 `wall` events in the rolling 120-event window**
  with 12 held walls in the snapshot.
- **Watchlist configured-instrument rows** — the recipe ran live: `ZZZTEST` (copy of a real instrument
  block, `pipelines: []`) in the sandbox config → reload → the watchlist renders its row
  (`SPAN.wl-sym: 'ZZZTEST'`). No code change needed; row retired.

**Gates at close.** pytest **585 passed / 2 skipped** (581 + `test_heat_wire.py`'s 4); **AUDIT CLEAN**;
the nineteen selftests green (ofx **178** ok — +4 wire checks; bus 13; the rest unchanged); 0 page
errors in the live pass (error + rejection collectors installed). Sandbox killed, port 8093 free, the
temp tree deleted; the real APPDATA was never touched (the sandbox ran its own 45 KB DB — the config
copy carries no absolute paths). Tree: **49 modified + 19 new**, HEAD `fa202d6`, nothing committed.

## §58 — P3-1's trigger, measured on the owner's actual hardware; and the options/fundamentals residue

**The trigger text.** Brief §6: "revisit only for > ~2 k simultaneous cells or forced 4K/144 Hz; if you
do, keep the coordinate matrix". Plan §P3-1: "WebGL for the heat layer only — deferred with a trigger.
… port only `drawHeat()` to a point-sprite mesh". Plan addendum: "Do not port WebGL without the trigger
conditions being met and measured."

**The measurement that decides it.** The owner's panel (this machine, queried via `Win32_VideoController`)
is a **2560×1440 @ 144 Hz** display — the 144 Hz case is his DEFAULT, not a hypothetical, and 144 Hz is
a **6.94 ms** frame budget. Against that: §52 measured the post-yield warm frame at **11.5–12.4 ms at
30 k cells / 4 K**, of which the **heat pass alone is the residue** (`no frame split can divide one
layer`), and cold arrival at 17.1. On this pass's readings the *interactive* case is worse than the
arrival frame implies: a pan/zoom drag sets `state.dirty.heat` every mousemove, so **every drag frame
paints 30 k `fillRect`s** — the heat pass runs per frame, and on a 144 Hz panel that is ~1.7× over
budget for the whole duration of the gesture. Simultaneous cells: a default 300×260 heat request on
the live book is ~29 k cells — an order past the brief's "> 2 k". **Both sides of the revisit
condition are met, on his machine, today.** Decision: build P3-1 — port ONLY `drawHeat()` to a WebGL
mesh, keep the coordinate matrix, keep the Canvas2D painter as the fallback.

**Why the code shape is friendly to this.** P2-3 already split the engine into per-layer canvases
(`ofxHeat` / `ofxBase` / `ofxLive` / `ofxRibbon`), so the heat layer is its own DOM canvas with exactly
one 2D consumer; a canvas may hand out only one context type, so the port means `ofxHeat` gets a
`webgl2`/`webgl` context and the 2D heat path is skipped wholesale when it succeeds. The heat canvas
has no 2D-only work: ghosts (decay) can ride the same shader as a small dynamic buffer. The transform
stays CPU-side for everything else (hover, cookies, axes); the shader receives it as the linear map
`x = ax·col + bx, y = cy·price + dy` — the mesh itself is therefore **scale-independent and rebuilt
only when the payload changes**, which is the entire point: pan/zoom becomes two uniform writes.

**Fallback rules.** No WebGL context (headless probes, old drivers) → the existing 2D painter runs
untouched; the selftests keep exercising the 2D path through their stub contexts; `stats().heatBackend`
says which one painted. The 4 selftest checks for the heat layer (P2-2 epoch/patch/skip/ghosts) must
stay green on the 2D path and the live pass must pin the GL path by pixels (`readPixels` ink) and by
the same epoch/gating counters.

**The options/fundamentals residue.** §25 fixed both entries (the Fundamentals supply cell builds its
`of 21.00M max` fragment as a real child element, flagged, everything else escaped; `options.js
fmtGreek` renders a non-zero sub-milli value as `n.toExponential(2)` so "no gamma" and "1e-05 gamma"
stay different statements) — but recorded the honest gap: **"the live click-through was not captured —
the probe waited 6 s inside one js() call and the harness times out at ~5 s. The rule is
test-pinned, not eyeballed."** This pass captures both live in the sandbox (the fixed tooling polls
outside the `js()` call, so the timeout no longer applies), reading the rendered DOM of the
Fundamentals supply cell and the Options gamma/greeks cells.

**Gates at recon time.** pytest 585/2; AUDIT CLEAN; nineteen selftests green (ofx 178).

## §59 — P3-1: the trigger measured against the owner's hardware (NOT triggered); the options/fundamentals residue closed

**The hardware.** This machine's panel (queried this pass via `Win32_VideoController`): **2560×1440 @
144 Hz** on an RTX 4050 laptop. A 144 Hz frame is **6.94 ms**; his app runs windowed (the app's stage
measured 2022×780 in classic full view at that window size).

**The measurements (all warm; forced heat passes via `state.heatEpoch += 1`; sync-block timing; the
current build — post-P2-3, post-§57).**

| shape | viewport | drawn cells | heat pass med / p95 / max |
|---|---|---|---|
| real payload, max server shape (900 buckets × 400 rows → merged) | 2022×780 (his panel) | 1,694 | **0.6 / 0.7 / 0.7 ms** |
| real payload | emulated 4K-wide (3336×898) | 1,809 | **0.7 / 0.8 / 0.8 ms** |
| synthetic 30 k cells (§52 shape) | 2022×780 | 30,000 | 1.3 / 1.6 / 1.7 ms |
| synthetic 30 k cells | emulated 4K-wide | 30,000 | 2.2 / 2.6 / 2.6 ms |

Full forced frame (heat+base+live in one frame) with this pass's thin fixture: 0.7–0.9 ms (real, his
res), 1.4–1.6 ms (30 k). The base layer's own share with real footprint/print data is not the heat's
and P2-3's yield already splits multi-layer arrival frames.

**Why the real drawn count is ~1.7 k, not 30 k.** The payload contract bounds it: his config (read
this pass) is `atlas.heatmap: { bucket_ms: 1000, max_columns: 900 }` — 15 minutes = ≤ ~15 merged bar
columns × ≤ 400 price rows ≈ **≤ 6,000 drawn cells mechanically**, measured 1,694–1,809 on live data.
The 30 k shape is a synthetic stress the pipeline cannot produce. §52's "17.5 ms arrival / 11.5–12.4
warm" was that synthetic shape pre-yield on a ~2× larger plot; today it costs 2.2–2.6 ms on a 3.0 Mpx
viewport (~4.8–5.6 scaled to that plot — the P2-2/P2-3 work improved the shape ~1.4×).

**Decision.** Per the plan's own rule ("Do not port WebGL without the trigger conditions being met
and measured") **P3-1 stays deferred** — the heat's share of any frame he can produce is ≤ 1.7 ms
against a 6.94 ms budget (4× headroom), and on real payloads 0.6–0.7 ms (10× headroom). **Re-open
conditions, sharpened:** (1) drawn heat cells > ~8 k at his resolution; (2) the app's target becomes
a true-4K canvas (> 3,000 CSS px wide); or (3) the heat's own share of a warm frame exceeds **3.5 ms**
(half the 144 Hz budget) at his resolution. If he wants the port anyway as a preference, it is an
L-sized change (quad mesh, pan/zoom matrix as uniforms, ghost buffer on the same shader) that starts
FROM this measurement — not instead of it.

**Bench traps (recorded so the next measurement is not wrong twice).**
1. **Price-spanning bars or everything culls.** The heat painter skips cells outside the viewport;
   synthetic bars at price 1.0 culled every ~75 k-price cell and the "pass" measured 0.0 ms. Two runs
   this pass were invalid before that was caught (cells read 0 or the pass read 0.0–0.1 ms).
2. **The P2-2 epoch gate makes a naive loop measure the SKIP path.** A forced pass needs
   `OFX.state.heatEpoch += 1`; `dirty.heat = true` alone skips the heat (counted in `heatSkips`).
3. **Measure in one sync block.** The view's 2.5 s poll reloads its own data between awaited turns and
   the merged cell count changes under the bench.
4. **Terminal vs classic size.** The default terminal layout gave the ofx widget a 354×148 stage;
   realistic full-view numbers need classic mode (`OFAPSHELL.switchTo('classic')`).
5. **`Browser.setWindowBounds` clamps to the screen** (~2556 px on this panel); a true 4K-width
   canvas needs `Emulation.setDeviceMetricsOverride`.

**The options/fundamentals residue — closed with live captures.**
- Fundamentals supply cell: `20.09M BTC` + a real child element (`of 21.00M max`;
  `elementChildren: 1`) — no literal tag in the text.
- Options gamma: selecting the ATM strike live put the ticker strip at
  `BTC-16SEP26-76000-C · mark 0.0015 · IV 29.29% · Δ +0.385 · Γ 8.80e-4 · Θ -83.256 · V 5.685 ·
  ρ 0.112 · OI 82 · vol 103.5 · forward 75871.2 · as of 2:07:54 pm` — the sub-milli gamma renders as
  the exponential exactly as `fmtGreek` pins it. §25's one un-eyeballed item now has a live example,
  not just a test.

**Ops note (cost time this pass): the automation browser is not immortal.** The harness drives a
Chromium-family browser over CDP. A process cleanup that catches the browser leaves the daemon unable
to recover (`DevToolsActivePort not found`), and stacked half-started daemons then block new calls
(the client reads an empty response). Recovery that works: launch **Edge** with
`--remote-debugging-port=9222 --user-data-dir=<throwaway dir>` — the harness probes 9222/9223
directly and attaches. No Chrome is installed on this machine; Edge is the Chromium family here.

**Gates at close.** pytest **585 / 2 skipped**; **AUDIT CLEAN**; nineteen selftests green; the tree is
untouched by this pass (**49 modified + 19 new**, HEAD `fa202d6` — measurement and documentation
only); sandbox deleted, the scratch Edge closed.

## §60 — the ModFlow badge as the app's iconography, and the new desktop shortcut

**The ask.** Adapt `Desktop/modflow.png` to "seamlessly replace the icons in the build", and add a new
desktop shortcut to the program carrying the new iconography.

**The source and the adaptation.** `modflow.png` is 1664×928, RGB, no alpha — the circular ModFlow
badge (navy disc, ring ensemble, honeycomb + circuit texture, teal M monogram, arced
"Modflow"/"OrderFlow Analysis Suite") on a cream banner (~`#F4F1E7`). Pipeline (PIL): a not-cream mask
(far-from-background threshold 25) gave the badge bbox `(438,69,1227,849)`; 144 rays refined the
centre + radius (median 394, spread 391–396 — a clean circle); a 792² crop was scaled to 96.5 % of a
1024 master and cut with a 4×-supersampled circular alpha mask (≈2 source px inside the edge so no
cream fringe survives — the edge audit shows the boundary pixels are the badge's own thin white ring,
plus 158 fractional-alpha boundary samples for a smooth rim).

**What was produced.** `assets/orderflow.ico` (replacing a 16–128 px stock bar-chart placeholder —
sizes 16/24/32/48/64/128/256, 256 PNG-compressed), `assets/modflow-icon-1024.png` (design master),
`orderflow_system/desktop/ui/app.ico` (**the path `build_exe.py` looks for** — the build had NO custom
icon at all until now, so the frozen exe carried PyInstaller's default), and `ui/app-icon.png` (512)
+ 32/64 PNGs for the web. Size falloff judged from a rendered sheet: 48 px reads fully, 32 legible,
24 recognisable, 16 reads as the round teal emblem — the standard falloff for a detailed badge, and
one consistent design was kept (no separate simplified ≤24 variant).

**Where they were wired.**
- **The web UI**: `index.html` gains `<link rel="icon" … app-icon.png>` + `… app.ico`. Live: both
  serve 200 from the desktop mount (the 512² PNG downloads whole), and the served page carries the
  link.
- **The window/taskbar icon (dev + frozen)**: `launcher.py` — and here the smoke test earned its
  keep twice. `webview.create_window(icon=…)` is **not a parameter in this pywebview** (TypeError at
  launch); `webview.start(icon=…)` is. And the WindowsForms backend refuses the PNG
  (`ArgumentException: 'picture' must be a picture that can be used as a Icon`) — it needs a real
  `.ico`. Final shape: `webview.start(icon=str(ui/app.ico) if it exists else None)`; the subsequent
  dev launch runs clean (the UI client connects in the log). The path resolves in the frozen build
  too: `build_exe.py` already `--add-data`s the whole `ui/` dir, so `Path(__file__).parent/ui/app.ico`
  is there through `_MEIPASS`.
- **The frozen exe itself**: its icon resources were replaced **without a rebuild** (nothing else in
  the build changes) via the classic Win32 path — `BeginUpdateResourceW` →
  `UpdateResourceW(RT_ICON × 7 + RT_GROUP_ICON, group id 1)` → `EndUpdateResourceW` (ctypes). Backup
  taken first (`%LOCALAPPDATA%\Temp\p60_exe_backup.exe` — deliberately OUTSIDE `dist/` so the ship
  folder stays clean). Verified by extraction: the exe's icon now reads 506 navy + 180 cyan pixels
  against the old bar-chart's palette, and the exe runs (the patch cannot have corrupted it).
- **The desktop**: a new shortcut **`ModFlow OrderFlow Analysis Suite.lnk`** (target
  `.venv\Scripts\pythonw.exe -m orderflow_system.desktop`, workdir the repo, icon
  `assets\orderflow.ico`, description set). The pre-existing `OrderFlow Analysis Pro.lnk` pointed at
  the same icon file and therefore picked the new artwork up automatically.

**A rebuild note.** The frozen exe's embedded icon is now the badge, but its bundled code predates
P1-7→§60; a future `scripts/build_exe.py` run picks up both the new `ui/app.ico` (via the ICON
constant) and the `start(icon=)` wiring, so the rebuilt app carries the iconography end to end.

**Traps for the record.** (1) pywebview's icon kwarg lives on `start()`, not `create_window()`, and
the WinForms backend takes an `.ico` (a PNG raises from .NET, not from pywebview). (2) A resource
patch needs `LoadLibraryEx(LOAD_LIBRARY_AS_DATAFILE)` + `EnumResourceNames` to find the existing
group id; orphan old RT_ICON entries beyond the new count are harmless. (3) Verify an icon in an exe
by extraction, not by the write return codes — and smoke-run the exe afterwards.

**Gates.** pytest 585/2, AUDIT CLEAN, nineteen selftests green (the UI change is one `<link>` pair;
the launcher change is verified by the two smoke runs). Tree: 50 modified + 24 new, HEAD `fa202d6`,
nothing committed.

## §61 — the two-tier icon: a simplified 16/24 px variant (the §60 offer, accepted)

**The ask.** §60's review noted the detailed badge mushes at 16 px and offered a simplified small-size
variant — the owner said build it.

**The pick.** Four centre crops of the badge (0.50R / 0.58R / 0.66R / 0.74R, each circle-cut and
rendered for review) were compared: 0.66R clips "Modflow" back in at the top, 0.74R shows the full
text, 0.50R sits tight on the M. **0.58R** won — the text is fully excluded and the M is complete with
breathing room. That crop was scaled to the same 96.5 % circular canvas as the badge master (so the
silhouette is identical) and kept as `assets/modflow-icon-small-1024.png` (1024 master for future
edits).

**The two-tier file.** PIL cannot emit different artwork per size in one `.ico`, so the set was
assembled at the byte level: two PIL-written ICOs (16+24 from the variant; 32/48/64/128/256 from the
badge) were merged into one directory with offsets adjusted — `assets/orderflow.ico` and
`orderflow_system/desktop/ui/app.ico` now carry the mixed set (16/24 simplified, 32+ the badge), and
the desktop shortcuts follow the assets file automatically.

**Verified.** PIL reads all seven sizes back; the exe's icon resources were re-patched with the merged
file and a **.NET** extraction (a second, independent icon parser) shows the badge at 32 px — the same
double-parse agreement that validates the hand-rolled ICO layout; the review sheet shows the variant
clearly more legible than the shrunken badge at 16 and 24 px; the exe smoke-runs; the fresh exe
backup was moved out of `dist/` again. The Explorer icon-cache caveat from §60 stands (a stale
thumbnail refreshes on its own).

**Gates.** Nothing in the app code changed this pass (icon assets only): pytest 585/2, AUDIT CLEAN
and the selftests carry over untouched. Tree: 50 modified + 25 new (`assets/modflow-icon-small-1024.png`
added), HEAD `fa202d6`, nothing committed.

## §62 — the rail brand: the text tile becomes the badge, and the wording modernises

**The ask (verbatim).** "replace the icon in the modflow order analysis suite build with the capital MF
in the top left with the new one you built and modernize the wording ModFlow ORDERFLOW ANALYSIS SUITE"

**What was there.** The rail's top-left block was a *painted* tile — a 32 px div, blue→violet gradient,
the literal text `MF` — above `ModFlow` and an all-caps `ORDERFLOW ANALYSIS SUITE` whose casing came
from the stylesheet (`.brand-sub { text-transform: uppercase; letter-spacing: .09em }`).

**The pick, from a rendered sheet.** The badge master and its §61 0.58R small variant were rendered at
24/28/32/36/40 px over the rail's own background (the dark gradient `rgb(13,20,32)` → `rgb(10,14,22)`,
and the light rail) and judged: at the rail's 32 px the **badge** reads best — its white ring gives the
mark an edge the variant lacks on the dark rail (navy-on-navy there; the variant stays the ICO 16/24
tier). Sheet and scratch scripts kept in `%LOCALAPPDATA%\Temp\p62_*`.

**What changed.**
- `ui/brand-icon.png` (new): the badge master at 128 px LANCZOS, alpha kept, 37 290 bytes — DPR-proof
  for a 32 px slot; `build_exe.py` ships the whole `ui/` dir, so a rebuild carries it exactly as
  `app.ico` already is.
- `index.html`: `<div class="brand-mark">MF</div>` → `<img class="brand-mark"
  src="/desktop/brand-icon.png" alt="ModFlow" width="32" height="32">`; the sub now reads
  **Orderflow Analysis Suite** — sentence case, the badge's own lettering.
- `ui.css`: `.brand-mark` is an image slot now (fixed 32 px, `flex: 0 0 auto`; no tile, no radius —
  the artwork is the disc); `.brand-name` 13.5 → 14 px; `.brand-sub` 10.5 → 11 px with the caps
  transform and the wide tracking removed.
- `test_wiring.py`: a P62 guard — the mark is the icon asset, `>MF<` is gone, the sub is sentence
  case, the caps transform is out of the rule, and the asset is served (`GET /desktop/brand-icon.png`
  → 200 `image/png`). The guard exposed a real trap: **`build_app()` may run once per process** (the
  FastAPI app it decorates is a module-level singleton; a second `add_middleware` raises "Cannot add
  middleware after an application has started" once any client has exercised it) — the file's two
  served-page tests now share one `_desktop_app()` build, green in any order.

**Verified live.** Headless on 8099: the served page carries the new markup; `GET /desktop/brand-icon.png`
→ 200 `image/png` and the downloaded bytes hash-match the file on disk (sha256 `a9d8789b…`; a first
`curl -w %{size_download}` read 0 bytes — a curl artefact: the saved download is the full 37 290).
Browser render: the badge crisp at 32 px in dark AND light themes, the sub aligned and quiet;
**0 `client error:` lines** in the app log; `config.json` byte-identical to a pre-smoke backup. The
frozen exe still carries the pre-§61 `ui/`, so the rail there changes with the pending `dist/` rebuild,
not before.

**Gates.** pytest **586 passed / 2 skipped** (585 + the P62 guard), `audit_ui_refs.py` **AUDIT CLEAN**,
nineteen selftests green (ofx 178). Tree: 50 modified + 26 new (`ui/brand-icon.png` added), HEAD
`fa202d6`, nothing committed.

---

## §63 — The package diet: stage 0 (dead build products) + stage 2 (numpy out, stdlib in)

Trigger: "maximizing pure efficiency of code and file ultimate file size? NOT BREAKING ANYTHING is paramount."
Two stages ran; a third (UPX) stays a separate owner decision.

**Stage 0 — build scratch, nothing referenced it.** `build/` (48.8 MB, 17 files: PyInstaller work dir,
which `build_exe.py --clean` deletes on every build anyway) and `dist/OrderFlowAnalysisPro/` (80.7 MB,
1690 files: the pre-rename Sep 15 onedir build) were removed. Evidence trail:
`%LOCALAPPDATA%\Temp\ofap_stage0_manifest_20260916.txt` (HEAD, file counts/bytes, sha256 of both exes
and the spec) + the spec kept at `%LOCALAPPDATA%\Temp\ofap_stage0_kept\`. No shortcut or launch path
references either folder — the desktop shortcut runs `.venv\Scripts\pythonw.exe`, and a scan of all 106
Desktop/Start-Menu shortcuts found none pointing into `dist/`. Repo: 487 MB → 360 MB. The kept build's
exe hash (`f0884c19…`) was identical before and after.

**Stage 2 — the analytics engines no longer need numpy (27 MB + hook collateral).** numpy was imported
by exactly two runtime files, for four sums, an `argmax`, a `std()` and a five-term line fit:
`analytics/delta.py` (polyfit slope ×2) and `analytics/volume_profile.py` (argmax/mean/std ×5). Both are
stdlib-only now (`_slope`, `_argmax`, `_mean`, `_pstd` — numpy's tie and ddof semantics preserved).
Safe-by-proof, not by promise: `scripts/regen_analytics_golden.py` captured 38 cases / 2138 numeric
leaves from the numpy implementations *before* the edit (fixtures sha256 `88cc0f8e…`), and the rewrite
reproduces them with a worst-case difference of **2.27e-13** (LAPACK vs plain summation; every POC/VAH/VAL,
LVN list, shape, peak index and cumulative delta identical). The pin is permanent:
`test_analytics_golden.py` (drift → the exact case and delta) and `test_no_numpy.py` (source scan of the
runtime tree + a subprocess that blocks numpy via `sys.modules` and then imports *and computes* the whole
pipeline chain, `main.OrderflowSystem` included). `build_exe.py` now excludes numpy/pandas/scipy/plotly/
kaleido/matplotlib/pytz/tzdata/watchfiles. The frozen package: **68 MB → 51 MB**, numpy/pytz/tzdata/
watchfiles all confirmed absent from `_internal` (the exe itself grew 0.5 → 12.7 MB because the CLI build
embeds the Python archive in the exe while the old hand-tuned spec used `exclude_binaries=True` — the
package total is the metric that moved, −17 MB / −25%).

**Verified live (frozen exe).** `dist/…/ModFlowOrderFlowAnalysisSuite.exe --headless --port 8095` with
`APPDATA` sandboxed (`%LOCALAPPDATA%\Temp\ofap_frozen_sandbox` — the live config/DB/log were never
touched): `/healthz`, `/desktop`, `/api/atlas/status`, `/api/atlas/capabilities`, `/api/control/config`
all **200**; the served `/desktop` and `/desktop/ofx.js` **hash-match the files on disk**
(`a238f36c…`, `791f538d…`); `api/atlas/status` returns a real payload; **0 `client error:` lines, 0
tracebacks, 0 ImportErrors** in the sandbox log. Process stopped afterwards (port closed, verified).

**Gates.** pytest **591 passed / 2 skipped** (586 + the five new pins), `audit_ui_refs.py` **AUDIT
CLEAN**, nineteen UI selftests green (ofx 178). Nothing committed; HEAD `fa202d6`.

**Still open.** Stage 1 rode along inside stage 2 (same exclude list, same rebuild). **UPX: NOT pursued —
measured 2026-09-16.** The earlier "~10-14 MB" was an unverified estimate; the measurement says the lever is
mostly imaginary: a plain zip of the shipped folder is **25.8 MB from 49.2 MB raw (−23.5 MB)** with zero
risk, and UPX-packed DLLs barely compress further inside that zip — so the artifact a user actually
downloads gains ~2 MB for Windows Defender/SmartScreen heuristics on packed binaries and a slower cold
start. Ship the zip if the app is ever published; the folder stays as built.

---

## §64 — Release-readiness pass (0.1.0 beta): leaks, lint, packaging — and one live bug the smoke found

Scope asked for: "final debug and file integrity scan … first release 0.1 beta … nothing must be broken",
with a reviewer LLM auditing the code and the build. Everything below is on disk; nothing committed.

**Integrity scan — clean.** No credentials in source (only README's `your_password` / `your_bot_token`
placeholders); no `sk-` / `ghp_` / `xox` / `AKIA` shapes; no `C:\Users\<you>` in source **and no "Moddy"
string in the shipped payload** (0 hits across the 494 files of the built package); the root
`orderflow_data.db*` / `*.log` are gitignored and untracked; `.gitignore` gained `.pytest_cache/`,
`.ruff_cache/`, `.mypy_cache/`. One cosmetic residue, for the record: 29 packaged files carry the *build
machine's Python path* (`C:\Users\<you>\AppData\Roaming\uv\python\…`) inside CPython's own binaries —
`python312.dll`, the `.pyd` files, `base_library.zip` — which is how a locally-built CPython stamps itself,
not project data; a Python installed at a neutral path would remove it if that ever matters.

**Release blockers fixed** (a reviewer's tooling would have hit each one):
1. **3.12-only syntax.** `desktop/api.py:399` used a nested same-quote f-string (PEP 701). The tree did not
   parse on 3.11 while pyproject claimed `>=3.10` and CI pinned 3.11 — first push would have been red.
   Hoisted into a local; an AST sweep with the 3.11 interpreter now reports **0 parse failures**.
2. **The dependency set was wrong in both directions.** pyproject declared pandas/numpy/scipy/plotly/
   kaleido/pytz/pyyaml (none imported anywhere) and declared none of fastapi/starlette/uvicorn/pywebview/
   pythonnet (all imported). `pip install -e .[dev]` on a clean machine could not run the app. Rewritten:
   only what the tree imports; `mt5` extra for the Windows-only MetaTrader5 feed; `dev` gained pyinstaller;
   `requires-python = ">=3.11"`; MIT license + classifiers; backend `setuptools.build_meta` (was the
   private `setuptools.backends._legacy:_Backend`); package-data for `desktop/ui`, `testdata`,
   `data/bookmap_addon`; `[tool.ruff]` block. Verified by building a wheel (220 files, UI + testdata inside).
3. **A real user-facing bug, found by exercising the endpoint.** `POST /api/control/source` called
   `engine.state()` while `EngineController.state` is a **property** → `TypeError: 'str' object is not
   callable`, swallowed by the endpoint's `except`. Picking a data source in the menu saved the config,
   never restarted the engine, and showed "the restart failed (…)". Fixed (one line) and pinned by the new
   `orderflow_system/test_source_switch.py` — 3 tests, **proven to bite**: with the bug reintroduced
   2 failed / 1 passed, with the fix 3 passed (`%LOCALAPPDATA%\Temp\ofap_pin_check.py`).

**Lint baseline (new).** `ruff check orderflow_system scripts` → **All checks passed** (was 143 findings).
70 auto-fixed (unused imports, f-strings without placeholders); hand-fixed via fail-loud scripts
(`%LOCALAPPDATA%\Temp\ofap_lint_fixes{,2,3,4}.py`): 12 unused locals — the *call* kept wherever it has an
effect (`hub.ensure()`, `orderbook_tracker.update()`, `webview.create_window()`) — 8 unused loop control
variables, 2 undefined annotation names in `atlas/cvd.py` (`Iterable`/`Sequence` were never imported), and
1 loop variable shadowing the stdlib `signal` import in `main.py`. `B008` (FastAPI's `Depends()`/`Query()`
in argument defaults) and `B905` (`zip(strict=)` is a behaviour change, not a style one) are documented
ignores. CONTRIBUTING now carries the lint baseline, the no-numpy rule and the node requirement.

**Public-face corrections.** README: badges + body corrected against measurements (3.11+, 49 instruments,
~60k lines, 131 operations / 119 paths as actually served per `/openapi.json`, 594 tests); the tree now
shows `atlas/` and `desktop/`; File Inventory is a measured table (163 files / 60,636 lines excl. tests;
the suite is 51 files / 10,477 lines); Installation rewritten around the real dependency set and the
desktop app (`python -m orderflow_system.desktop`, `--headless --port 8099`), with the MT5 extra, demo
mode and `scripts/build_exe.py`; License section states the fork relationship. LICENSE keeps the upstream
MIT notice **and** adds Moddy's copyright line. Test output de-emoji'd (12 sites in `test_integration.py`);
`test_no_numpy.py` no longer names a person in its docstring.

**Gates at close (3.12 venv).** pytest **594 passed / 2 skipped** · `audit_ui_refs.py` **AUDIT CLEAN** ·
ruff clean · analytics golden OK (2.27e-13) · config golden OK (31/18/49) · 19 UI selftests green (ofx 178).

**IMMEDIATE NEXT ACTIONS**
1. ~~Rebuild the frozen dist~~ — **DONE 16:28**, exe now newer than the `api.py` fix, and smoked on the
   shipped artifact (sandboxed `APPDATA`, port 8095): `/healthz`, `/desktop`, `/api/atlas/status`,
   `/api/control/config` all **200**; `POST /api/control/source` answers
   `{"ok":true,…,"engine":{"restarted":false,"reason":"engine was not running"},"note":"source saved;
   press Start engine to stream it"}` — the old `'str' object is not callable` note is gone; the served
   `/desktop` hash-matches disk (`a238f36c…`); **0** error lines in the sandbox log; numpy and the hook
   collateral still absent; package **49.2 MB raw / 25.8 MB zipped** (re-measured on this artifact).
   Process stopped, port closed.
2. **Settle the Python 3.11 question before the first push.** `test_websocket_backpressure.py::
   test_a_broadcast_never_waits_on_a_slow_client` never returns on 3.11 (3.12 completes in <1 s and cancels
   both writer tasks cleanly; the 3.11 venv stalls inside the scenario and, in another run, inside
   `asyncio.run`'s `_cancel_all_tasks` — a faulthandler dump is in `%LOCALAPPDATA%\Temp\ofap_stack.txt`).
   Either root-cause it (real 3.11-vs-manager behaviour) or set `.github/workflows/ci.yml` to 3.12 only and
   `requires-python = ">=3.12"` — the current matrix is `[3.11, 3.12]`, so an unresolved hang burns a job.
3. Then the release proper (owner's call; nothing committed, HEAD `fa202d6`): commit → create the GitHub
   repo → push → tag `v0.1.0-beta` → attach a **zip** of `dist/ModFlowOrderFlowAnalysisSuite/` (measured
   25.8 MB from 49.2 MB raw; UPX closed, not pursued — §63). InstallShield follows, and needs: WebView2
   runtime prerequisite, per-user `%APPDATA%\OrderFlowAnalysisPro` config (leave it on uninstall),
   `ui/app.ico`, version 0.1.0, publisher string.

**Housekeeping left open.** `AUDIT_REPORT_2026-09-15.md` at the repo root carries a `C:\Users\<you>\…`
path and a few "Moddy" references — move into `docs/` or leave (decision); the docs/ trail keeps its
"Moddy"-flavoured narration by design; the README's ASCII box says "132 REST/WS routes" while the badge and
the served schema say 131 (make exact if it matters).

**Evidence in `%LOCALAPPDATA%\Temp\`**: `ofap_py311.log` (3.11 venv, pytest stalls at 96%),
`ofap_stack.txt` (faulthandler dump), `ofap_taskprobe.py` (3.12 control vs 3.11 blank),
`ofap_lint_fixes*.py`, `ofap_emoji_clean.py`, `ofap_pin_check.py`, `ofap_engine_repro{,2}.py`,
`ofap_release_sandbox/` (first-run sandbox), `ofap_wheel_test/`, `ofap_stage0_manifest_20260916.txt`,
`ofap_stage0_kept/`, `ofap311/` (the 3.11 venv itself).

---

## §65 — The Python 3.11 hang: root cause (a stdlib cancellation swallow), the fix, and the release-face exactness pass

Scope asked for: settle the §64 open item 2 — `test_websocket_backpressure.py::test_a_broadcast_never_waits_on_a_slow_client`
never returns on 3.11 — then the release-face housekeeping. Everything below is on disk; nothing committed.

**The hang, located.** On 3.11 the scenario body completes; the stall is in `asyncio.run`'s shutdown
(`runners._cancel_all_tasks`: cancel the survivors with the loop stopped, then gather them — faulthandler
shows the loop idle in `windows_events._poll`). The two writer tasks are the survivors: one parked in
`asyncio.wait_for(send_text, 5.0)`, one in `queue.get()`. Cancel-while-running always worked; the hang
needs cancel-while-stopped plus one specific state: the write-timeout's `waiter` future already FINISHED
with the writer's wake-up still queued (`ofap_probe65d.py` ticker: `fut_waiter=[Future done=True
state=FINISHED]`, writer alive forever, parked back in `queue.get()`).

**Why.** 3.11's `asyncio.wait_for` (`Lib/asyncio/tasks.py:477`): `except CancelledError: if fut.done():
return fut.result()` — when the awaited write already finished, the caller task's cancellation is
*answered with the write's result*. `Task.cancel()` had already consumed its one shot (`_must_cancel`
can't cancel an already-done `_fut_waiter`), so the writer looped back to `queue.get()` and never died;
`_cancel_all_tasks`'s gather waited forever. 3.12 rewrote `wait_for` as `async with
timeouts.timeout(timeout): return await fut` (same file, line 519) — no swallow clause — which is why
3.12 completed in <1 s. The manager's own contract (producer never waits on a slow socket, bounded
queues, oldest-first trim) was never at fault.

**The fix.** `websocket_manager._writer` and `_offer` no longer use `wait_for`: a plain deadline,
`async with asyncio.timeout(WRITE_TIMEOUT_S)` (3.11+, the same primitive 3.12's `wait_for` is built on).
Semantics unchanged: write deadline → drop the client; offer deadline → `dropped += 1`. Cancellation now
propagates like any other exception, on both interpreters.

**The pin.** `test_a_cancelled_writer_dies_even_when_its_write_just_finished` builds the exact state
deterministically (a gated write completes while the loop is stopped; one settle cycle; cancel; a
bounded gather) so a regression **fails in ~2 s instead of hanging the suite**. Proven to bite: with the
original `wait_for` code it fails (1 failed in 2.29 s, AssertionError at the bounded shutdown, writer
parked in `queue.get()`); with the fix: 6/6 in the file, the formerly-hanging test 10 consecutive runs
at ~0.61 s. The full suite on 3.11 — the thing §64 could not get — now runs: **595 passed / 2 skipped in
26.5 s** (3.12: 595 / 2 in 26.4 s). **CI's `[3.11, 3.12]` matrix and `requires-python = ">=3.11"` stay;
no pin to 3.12 was needed.**

**The one 3.11-only failure found, and why it was not the code.** `test_wiring.py`'s rail-brand test
asserted the served `content-type` of `brand-icon.png`; on this host `HKCR\.png\Content Type` is *empty*
(Media Center residue — the real value sits in `MediaCenter.36.ContentType.BAK`), and 3.11's `mimetypes`
honours the empty registry value while 3.12 falls back — so 3.11 served `application/octet-stream` where
3.12 served `image/png`. The assertion was a statement about the host, not the app; replaced with byte
identity (`res.content == file.read_bytes()`) — strictly stronger and host-independent. The frozen build
is 3.12, so the shipped app never sees it.

**Release-face exactness (all measured this session).**
- README tests badge 591 → 595; CONTRIBUTING baseline 591 → 595 (both interpreters measure 595 / 2).
- "Supported Instruments (29)" → (49) (ToC + heading) plus one clarifying line: 49 = the 31 base specs
  tabled below + 18 crypto majors (config golden 31/18/49); "…for all 29 instruments" → "…for all 49
  configured instruments"; the demo-generator line → 45 (`demo_data.demo_instruments()` measures 45).
- `config/settings.py` tree notes: 29 → 31 instrument configs, 10 → 14 dataclasses, 946L → 777L
  (the File Inventory's Config row — 2 files / 777 — corroborates).
- The §64 route-count question resolved as **no change needed**: measured 119 paths / 131 operations /
  1 WebSocketRoute (`/ws`) → 132 REST/WS routes, exactly what the badge and the box say; `/api/atlas/*`
  = 45 and `/api/control/*` = 70 confirmed exact.
- **Found and recorded, not edited**: the README's tree/diagram `(NNNL)` annotations are broadly stale —
  a read-only audit of the 43 claims found **26 wrong** (main.py 666→815, app.py 1015→1235,
  websocket_manager.py 186→293, …); the File Inventory table (§64) is the accurate set. A dedicated
  docs pass should re-derive them (script: `%LOCALAPPDATA%\Temp\ofap_readme_count_audit65.py`).
- `AUDIT_REPORT_2026-09-15.md` moved from the repo root to `docs/` (its v1 already lives in
  `docs/archive/`); the live pointer in `docs/ALPACA_UPGRADE_EXECUTION_PLAN.md` (source table S3)
  updated. The docs/ trail keeps its "Moddy"-flavoured narration by design.

**The frozen dist is current again.** Rebuilt 16:54:45 (exe newer than the fix) and smoked on the
artifact (sandboxed `APPDATA`, port 8095): `/healthz`, `/desktop`, `/api/atlas/status`,
`/api/control/config` all **200**; `POST /api/control/source` answers `{"ok":true,…,"engine":
{"restarted":false,"reason":"engine was not running"},"note":"source saved; press Start engine to
stream it"}` — the §64 bug stays fixed; the served `/desktop` and `/desktop/ofx.js` **hash-match disk**
(`a238f36c…`, `791f538d…`, unchanged); **0** `client error:` lines, 0 tracebacks; numpy still absent
(0 of 55 `_internal` entries); **49.2 MB raw (51 MB on disk) / 25.8 MB zipped** (494 entries, re-measured on this
artifact). Process stopped, port closed. (Note for the shell: `taskkill //F` is not a valid form here —
it errors and a redirected stderr hides it; `powershell -NoProfile -Command "Stop-Process -Id <pid>
-Force"` is the reliable stop, and PyInstaller's onedir build runs a parent+child pair — the PID
holding the port is the one that must die.)

**Gates at close.** pytest **595 passed / 2 skipped** on both 3.11 and 3.12 · `audit_ui_refs.py`
**AUDIT CLEAN** · ruff clean · analytics golden OK (2.274e-13) · config golden OK (31/18/49) · 19 UI
selftests green (ofx 178).

**Tree.** Nothing committed; HEAD `fa202d6`; `git status --porcelain` = 129 entries. §65 touched:
`orderflow_system/dashboard/websocket_manager.py` (the fix), `orderflow_system/test_websocket_backpressure.py`
(the pin), `orderflow_system/test_wiring.py` (host-independent assertion), `README.md`, `CONTRIBUTING.md`,
`docs/ALPACA_UPGRADE_EXECUTION_PLAN.md`, plus the `AUDIT_REPORT_2026-09-15.md` move (root → `docs/`) and
this section + `docs/RESUME.md`. `dist/` rebuilt (gitignored).

**IMMEDIATE NEXT ACTIONS**
1. Owner's call (unchanged): commit → create the GitHub repo → push → tag `v0.1.0-beta` → attach a zip
   of `dist/ModFlowOrderFlowAnalysisSuite/` (25.8 MB; UPX closed, not pursued — §63). Nothing committed.
2. Optional docs pass: re-derive the README's tree/diagram `(NNNL)` counts (26 of 43 stale as of §65).
3. InstallShield after that (WebView2 prerequisite, per-user `%APPDATA%\OrderFlowAnalysisPro` config,
   `ui/app.ico`, version 0.1.0, publisher string).

**Evidence in `%LOCALAPPDATA%\Temp\`**: `ofap_probe65.py`, `ofap_probe65b.py`, `ofap_probe65c.py`,
`ofap_probe65d.py` (the decisive ticker), `ofap_py311_hang65.log` (the fresh pytest hang + faulthandler),
`ofap_wm_orig.py` / `ofap_wm_fixed.py` (red/green copies), `ofap_taskprobe.py`, `ofap_stack.txt`,
`ofap_doc_edits65.py`, `ofap_readme_count_audit65.py`, `ofap_stage65_build.log`, `ofap_stage65_sandbox/`,
`ofap_stage65_dist.zip`, `ofap_routecount_sandbox/`, `ofap311/` (the 3.11 venv).


## §66 — v0.1b audit return: ingest.txt verified item-by-item, 7 fixes pinned, 3 rejected with evidence

**Context.** `Desktop/ai prompt.txt` (the footprint/heatmap spec + "scrutinise, stepped report, don't
break anything") applied to `Desktop/ingest.txt` — a fresh 799-line "RELEASE AUDIT REPORT v0.1b"
(Tiers 0–8). The full return document is `docs/AUDIT_RETURN_v0.1b.md`; this entry is the worklog.

**Fixed, each with its own pin (8 new test files + 1 case in test_wiring.py; suite 595 → 621 / 2).**
- **1.5 DB footprint round trip** — `get_candles` never read `footprint_json`, so the hourly VP
  rebuild ran the even-distribution fallback on real data. Now read+decoded (`_decode_footprint`;
  `{}`/NULL → empty, malformed cells skipped). Pin: `test_candle_roundtrip.py`.
- **1.4 absorption keying** — `round(price, 4)` merged adjacent levels on the 9 fine-tick
  instruments (forex 1e-5, DOGE, TRX); a probe showed a single candle firing `min_attempts=2` from
  two distinct prices. Keyed by tick-rounded price now. Pin: `test_absorption_keying.py`.
- **Tier 8 #2 unknown-symbol leak** — the `models_symbol` guard sat only on the warming branches of
  `/api/footprint` and `/api/tape`; the no-engine branches served the invented $1,000 chart. Both
  guarded; live-verified (source 8091 + frozen exe 8099): `UNKNOWNXYZ` → `[]`. Pin: `test_wiring.py`.
- **2.1 candle-wiring assertion** — now checks identity (analytics callback on the pipeline's own
  builder; persistence wire == `system._on_candle_closed`), catching the one-letter mis-wire class;
  the audit's rename pass was not taken (churn; the assertion now guards the failure mode). Pin:
  `test_candle_wiring.py`.
- **2.5 Bybit `T` fallback** — one latched warning per connection, re-armed on reconnect. Pin:
  `test_feed_timestamps.py`.
- **2.2 bank-key rename** — `_CONFIG_BANKS`/`_bank` read as destination field names; Spec→bank map
  in `get_config_for`; config golden proves equivalence (31/18/49).
- **demo coverage** — added NIKKEI225/CAC40/ASX200/HK50/USOIL/UKOIL base prices (demo-only content;
  ticks deliberately coarser than live banks, documented). Pin: `test_demo_coverage.py`.
- **README counts pass** — all 43 `(NNNL)` claims re-derived (18 stale); File Inventory re-measured
  (172 files / 26,131 py / 35,813 UI / 61,944 total; suite 60 / 11,138); badge ~62k; "45 demo
  instruments" → every shipped instrument; 9→10 channels ×2; 7→9 dataclasses; provenance now names
  the upstream fork commit `b2ff4ee` (author verified: Mahmoud Chen).
- **Analytics golden** — +2 edge cases (`poc_top_cluster` keeps VAL<POC; `poc_at_low` pins `val==poc`
  at the extreme as correct); 40 cases, regen check max diff 0.000e+00, no existing number moved.

**Rejected, with probe evidence (no change made).**
- **1.1 value-area "inversion"** — the invariant `val <= poc <= vah` holds by construction; the
  audit's own proposed test already passes on the live algorithm; its "fix" would widen the band
  past the 68% containment. Pinned by `test_value_area_edges.py` + the golden cases instead.
- **1.3 exhaustion "inverted gate"** — the proposed gate demands `delta_roc < 0` (delta falling =
  selling STRENGTHENING for bearish exhaustion) and silences the textbook dry-up bin; a 5-bin probe
  shows the live gates correct. Pinned by `test_exhaustion_gates.py`; the sign-flip is documented.
- **1.2 "dead cooldown knob"** — it is wired for the app (`desktop/engine.py:591–594` overrides both
  aggregator values from the user's `risk` config); what was missing was a pin →
  `test_engine_wiring.py` + a provenance comment in `main.py`.

**Verified-already-done (no action):** Tier 0 (dual LICENSE present; provenance line added),
2.3 (selftests ARE in CI — `.github/workflows/ci.yml` runs pytest + audit + all 19), 4.2 (log/db
untracked + ignored), Tier 3 (stacked-SR zones, cbrt sweep circles, snap-to-live float, font ramp,
45 px LOD, CVD readout all present in `ofx.js`/`ofx-view.js` — that section of the audit is stale),
7.10 (the `data` block is deliberately phase-3; backend + /storage + Logs chip exist).

**Open (owner decisions; Part 4 of the return doc).** The `max(tick_size, 0.01)` displacement clamp
in absorption/initiative (25 fine-tick instruments; fixing it narrows when absorption fires — needs
a decision + bank retune), and extending the unknown-symbol guard to the other demo-fill endpoints.

**Gates.** pytest **621 passed / 2 skipped** · AUDIT CLEAN · ruff clean · analytics golden OK
(40 cases, max diff 0.0) · config golden OK (31/18/49) · 19 UI selftests green · source smoke on a
sandbox (8091) and frozen-exe smoke (8099) as recorded in the return doc.

**Frozen dist.** Rebuilt 18:00 (after the last source edit) and smoked sandboxed on 8099: all
endpoints 200; `/api/footprint/UNKNOWNXYZ` → `[]`; served `/desktop/ofx.js` hash-matches disk
(`791f538d…`); log 16 lines, 0 client errors; numpy absent (0 of 494 `_internal` entries);
**49.3 MB raw / 25.9 MB zipped**; `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` written. Port
closed (PowerShell `Stop-Process` — `taskkill //F` remains unreliable here).

**Tree.** Nothing committed; HEAD `fa202d6`; `git status --porcelain` = 139 entries. §66 touched:
`data/database.py`, `patterns/absorption.py`, `patterns/exhaustion.py` (comments), `data/bybit_feed.py`,
`desktop/engine.py`, `main.py` (comment), `config/settings.py`, `dashboard/demo_data.py`,
`dashboard/app.py`, `README.md`, `scripts/regen_analytics_golden.py`,
`orderflow_system/testdata/analytics_golden.json`, `orderflow_system/test_wiring.py`,
plus eight new test files (`test_candle_roundtrip`, `test_absorption_keying`, `test_feed_timestamps`,
`test_exhaustion_gates`, `test_value_area_edges`, `test_demo_coverage`, `test_candle_wiring`,
`test_engine_wiring`), this section, `docs/AUDIT_RETURN_v0.1b.md` and `docs/RESUME.md`. `dist/`
rebuilt + zipped (gitignored).

**IMMEDIATE NEXT ACTIONS**
1. Owner's decision on the displacement clamp (evidence: `docs/AUDIT_RETURN_v0.1b.md`, Part 4).
2. Release sequence (unchanged): commit → create the GitHub repo → push → tag `v0.1.0-beta` →
   attach `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` (25.9 MB).
3. Optional: extend the unknown-symbol guard to the remaining demo-fill endpoints; InstallShield.

## §67 — the displacement unit restored in absorption/initiative (true tick steps), 6 pins, dist rebuilt again

**Ask.** Owner approved attending to the §66/Part-4 finding: displacement in absorption's
"price displaced little" gate and initiative's body gate was divided by `max(tick_size, 0.01)`,
silently redefining "ticks" on the 25 instruments with tick < 0.01 (on EURUSD "2 ticks" meant
0.02 = 2,000 real ticks; absorption's gate was vacuous at candle scale and initiative could
not fire).

**Decision (with its argument).** Restore TRUE tick steps, because that is the unit every
instrument with tick >= 0.01 has always run in (the old floor was inert there): a level N
ticks from the current price is N footprint levels away; a body of N ticks spans N price
levels. The unit is scale-free, so NO bank retune was needed — 2 and 3 mean the same thing on
EURUSD as on NAS100. The alternative (keep the floor, inflate thresholds per class) hides the
unit and re-breaks on the next odd tick; rejected.

**Proven to bite.** `test_displacement_ticks.py` (6 cases) was written FIRST and run against
the untouched code: the three fine-tick cases failed exactly as predicted (EURUSD absorption
admitted a level 5 ticks away; initiative could not fire), while the coarse-tick cases passed
on both sides (they pin what must NOT move). The zero-tick guard case also exposed a latent
ZeroDivisionError in the §66 event-keying line — closed by the same guarded local
(`tick_size if tick_size and tick_size > 0 else 0.01`).

**Change.** `patterns/absorption.py` (guarded local + `/ tick_size`) and `patterns/initiative.py`
(same). For tick >= 0.01 the divisor is mathematically identical — coarse behaviour
bit-unchanged. Live-path proof: an EURUSD InstrumentPipeline (real config) closed 4 candles
end-to-end through all detectors without an exception.

**Gates.** pytest **627 passed / 2 skipped** (621 + 6) · AUDIT CLEAN · ruff clean · analytics
golden OK (40 cases, 0.0e0) · config golden OK (31/18/49) · 19 UI selftests. `docs/AUDIT_RETURN_v0.1b.md`
gained Part 7 (execution record); its Part 4 marker now reads [RESOLVED]. Nothing committed;
HEAD `fa202d6`.

**Frozen dist.** Rebuilt 18:16 after this change; sandboxed 8099 smoke: endpoints 200 (incl. a
EURUSD fine-tick demo footprint), `/api/footprint/UNKNOWNXYZ` → `[]`, served `/desktop/ofx.js`
hash-matches disk (`791f538d…`), log 11 lines, 0 client errors, numpy absent; **49.3 MB raw /
25.9 MB zipped** (494 entries); `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` refreshed. Port
closed (`Stop-Process`).

**Tree.** Nothing committed; `git status --porcelain` = 140 entries. §67 touched:
`patterns/absorption.py`, `patterns/initiative.py`, `test_displacement_ticks.py` (new),
`docs/AUDIT_RETURN_v0.1b.md`, `docs/SESSION_HANDOFF.md`, `docs/RESUME.md`; `dist/` rebuilt +
re-zipped (gitignored).

**IMMEDIATE NEXT ACTIONS** — now ONLY the release sequence (owner): commit → create the GitHub
repo → push → tag `v0.1.0-beta` → attach `dist/ModFlowOrderFlowAnalysisSuite-win64.zip`.
Optional follow-ups unchanged: unknown-symbol guard on the remaining demo-fill endpoints;
InstallShield.

## §68 — the demo-fill guard generalised to all eight remaining symbol endpoints

**Why.** §66 fixed footprint/tape: an UNKNOWN symbol gets NOTHING with no engine running, not
the old invented $1,000 fiction. The same Tier 8 #2 rule belonged to every other demo filler the
desktop shell polls, because the shell clones the active symbol across every panel.

**Prove-it-bites.** `test_demo_symbol_guards.py` (2 tests) written first, run against the
untouched code: the unknown-symbol test FAILED exactly as expected (first: /api/markers returned
8 invented markers), while the modeled-symbol test PASSED — pinning both halves ("nothing
invented" and "nothing moved").

**The change.** `dashboard/app.py`, nine edits, all confined to `if not system:` (and
microstructure's two fill branches): markers / candles / volume-profile / delta → `[]`;
bias → the engine's neutral no-bias shape tagged demo; strategy-status → the existing
OFFLINE checklist tagged demo; orderbook → the engine's empty-book shape; microstructure →
a new `_empty_microstructure()` (the live payload's shape, zeroed) — with the engine-mode
branches tagged "engine" and demo-mode branches tagged "demo", mirroring each mode's own
empty-state convention. For every modeled symbol (all 49 shipped) the fills are byte-identical.

**Gates.** pytest **629 passed / 2 skipped** (627 + 2) · AUDIT CLEAN · ruff clean · analytics
golden OK (40, 0.0e0) · config golden OK (31/18/49). Live sandbox smoke (source on 8092, then
the frozen exe on 8099): all ten endpoints — including footprint/tape — answer UNKNOWNXYZ with
empty-of-shape; BTCUSDT and EURUSD (fine-tick) fully populated; served UI hash-matches disk.

**Dist.** Rebuilt 18:45 after the change; exe smoked on 8099 (0 error lines, port closed);
`dist/ModFlowOrderFlowAnalysisSuite-win64.zip` refreshed — 494 entries, 25.8 MB zipped /
49.3 MB raw. Nothing committed; HEAD `fa202d6`; tree dirty (141 entries).

**IMMEDIATE NEXT ACTIONS.** InstallShield installer (§69, in progress): generated .ism +
IsCmdBld pipeline; then the release sequence (commit → repo → push → tag `v0.1.0-beta` →
attach zip + setup.exe) on the owner's word.

## §69 — the Windows installer: built, verified, and documented

**What.** `installer/` now carries the whole InstallShield pipeline: `make_installer.ps1`
(regenerates the .ism from the blank Basic MSI template, sets identity + per-user context,
adds the payload via one dynamic folder link + a static exe entry, creates the desktop
shortcut, builds with IsCmdBld, copies the artifact to `dist`, prints the hash),
`SetupPrerequisites\WebView2.prq` (ready-to-enable prerequisite), and `README.md` documenting
the design, the eight measured automation traps, and how to rebuild.

**Artifact.** `dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` — 28,094,985 bytes
(26.79 MB), sha256 `0153B20DBB3048937547DFBBD9D7248F910C4786CAE68CB49DE662FDA2D11599`,
built from the current frozen dist (494 files / 49.28 MB), 0 build errors.

**Verified journey (every step receipts-on-disk).** Silent install (`/s /v"/qn"`) → 494 files
under `%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`, exe under its own name, desktop
shortcut `ModFlow OrderFlow Analysis Suite.lnk` with target = installed exe and the right
description → installed app launched headless on 8098 (healthz 200, BTCUSDT candles 200,
UNKNOWNXYZ `[]` — §68 guard holds in the frozen build) → silent uninstall → install dir,
shortcut and ARP entry all gone. The machine's pre-existing development shortcut was backed up
and restored around the tests.

**Traps found and encoded (the hard-won list, full details in installer/README.md).** Automation
is 32-bit only; CreateProject's binder is broken (copy the blank template instead);
AttachComponent needs the object; AddFile must be called natively; a file's DisplayName IS its
destination filename (setting it to the product name installs the exe extension-less — and
orphans the shortcut); AddShortcut's Target defaults to the FEATURE (an advertised shortcut a
silent install drops) and must be `[#<FileKey>]`; the Shortcut.Name cell needs an 8.3 short
name (`MODFLO~1|ModFlow OrderFlow Analysis Suite`); IsCmdBld wants backslash paths; and
InstallShield runs in **evaluation mode** on this machine (compressed setup.exe only — which is
exactly the artifact wanted).

**Deliberately not taken (documented, not silently skipped).** Start Menu shortcut: the
automation cannot create shortcut-folder roots (probed exhaustively — folder set fixed to
TaskBar/SendTo/Desktop); one-click IDE step documented in installer/README.md. WebView2: chain
package cannot source its bootstrapper payload via automation; the .prq ships ready to enable.
Both noted in the report and README.

**Gates.** No app source changed in this pass — pytest remains **629 passed / 2 skipped**,
AUDIT CLEAN, ruff clean, goldens unchanged. Tree dirty (142 entries) with the new `installer/`
files; nothing committed; HEAD `fa202d6`.

**IMMEDIATE NEXT ACTIONS.** The release sequence itself (owner's word): commit → repo → push →
tag `v0.1.0-beta` → attach `ModFlowOrderFlowAnalysisSuite-win64.zip` + the Setup exe. Optional
polish thereafter: the IDE one-click Start Menu/WebView2 enable; .gitignore for
`installer\build\`.

## §70 — the secure2 pre-release security sweep: loopback boundary, feed-value gates, release hygiene

**What.** `Desktop/secure2.txt` (the expanded pre-release audit & security sweep directive) applied
to the whole tree. The report is `docs/SECURITY_SWEEP_v0.1b.md` — directive format A–L, 14 findings
(0 Critical / 3 High / 5 Medium / 5 Low / 1 Informational), every fix with a pin, every claim with a
receipt. 13 fixed in this pass; 1 open by design (SS-8: lockfile/SBOM/dependency-scan tooling).
Each fix landed alone on a green suite, test-first: the new tests were run against the untouched
tree first and failed exactly as predicted, then went green.

**The headline class this sweep targeted: the loopback API is reachable by any web page.** A page
the user visits can *send* requests and open websockets to 127.0.0.1 even though it cannot read
cross-origin replies (readback requires same-origin — which DNS rebinding hands the attacker).

**P0 fixes (each with its pin file).**
1. **DNS rebinding → API read** (High): no Host validation existed; `/api/control/config` returns
   the Alpaca key/secret, Telegram token, e-mail password. Fixed by `LocalRequestGuard`
   (`dashboard/app.py:81-148`, module-level so every consumer of the app singleton gets it):
   non-loopback `Host` → 403 (`local_hostname()` handles host:port, IPv6, URLs). Live proof on the
   real socket: `Host: evil.example` → 403; loopback → 200. Pin: `test_request_guard.py`.
2. **Cross-site POSTs** (High): body-less mutating routes (config/reset, engine/stop, logs/clear,
   storage/prune, alerts/clear, replay…) are "simple requests" — a visited page could fire them.
   Same guard: mutating methods must carry no browser Origin or a loopback one, and never
   `Sec-Fetch-Site: cross-site`. Live hostile-page proof (a real `file://` page in Chromium):
   its POST → `403` in the access log, nothing executed.
3. **WS handshake** (Medium): a websocket is not CORS-gated, so `ws://127.0.0.1:PORT/ws` accepted
   any origin. `is_trusted_ws_handshake()` refuses non-loopback Origin / cross-site before accept.
   Live proof: hostile page got close 1006 + server `"WebSocket /ws" 403`; the app's own page
   stays `WS live` (no Origin works too — native clients).
4. **Feed-value gates** (High, market-data integrity): Python's `json` accepts bare `NaN`/`Infinity`
   and every NaN comparison is False, so `float(x) <= 0` could not catch it — **executed proof: a
   NaN close became a candle before the fix**. `bybit_feed._finite()/_level()` now gate trades,
   snapshots and deltas (refused values counted in `book_health()["junk_values"]`), and
   `alpaca_normalize._num()` is finite-or-default. Pin: `test_feed_value_guards.py`.
5. **News-feed URL** (Medium): `?news_url=` was fetched with `urlopen()` — any scheme (a probe read
   a local file as a "feed"), unbounded read (memory DoS), redirects unchecked. Now http(s)-only,
   http(s)-only redirects, 4 MiB cap (`atlas/context.py:59-95`). Pin: `test_context_hardening.py`.
6. **Legacy bind** (Medium): `config/settings.py` defaulted the standalone pipeline to `0.0.0.0`
   (the repo's own feasibility notes had flagged it). Now `127.0.0.1`, README example updated.

**Also fixed, pinned.** Venue URL templates quote the symbol/currency (context.py `_venue_symbol`,
deribit.py:405) — path-param query injection; RSS parser refuses internal-DTD documents
(entity class, `context.py:118`); `/api/control/client-error` folds CR/LF in every field (log
forging); `SECURITY.md` added (private disclosure path, linked from README/CONTRIBUTING);
CI: actions pinned to verified commit SHAs (`11bd719…` v4.2.2, `a26af69…` v5.6.0) + `contents: read`
+ `persist-credentials: false`; a meta CSP on the shell (`index.html:12`) that forbids every remote
target while keeping the inline boot script and the Studies engine's `new Function`;
`docs/phase4/logs-batch-counters.png` re-rendered to drop the maintainer's username from the path
(the only PII found; 17 of 50 screenshots read with vision — credential fields everywhere else were
empty or masked).

**Accepted / documented, not changed (with the reasons in the report).** `GET /api/control/config`
serves the stored secrets: the settings UI and wizard round-trip those fields (masking would blank a
saved token on the next unrelated save) — the mitigation is the boundary guard, and SECURITY.md says
so. No auth by design (same-user ⇒ same file access). Studies `new Function` engine = the plugin
surface. Webhook/ntfy/DTC targets are user-configured on purpose. No lockfile yet (SS-8).

**Verification.** pytest **649 passed / 2 skipped** (629 + 20 pins) · AUDIT CLEAN · ruff clean ·
analytics golden OK (40 cases, 0.0e0) · config golden OK (31/18/49) · 19 UI selftests green
(search-ops prints "all checks passed"). `uvx pip-audit` over the build env: **no known
vulnerabilities**; `uvx bandit -ll`: **0 High**, 13 Medium — all reviewed (9× fixed-URL B310,
B608 = the fixed table-name COUNT(*), B104 fixed by the loopback default, B314 mitigated).
Live Chromium run against a sandbox: guard 403s on the wire, **0 CSP violations / 0 page errors
across 12 views**, WS live; hostile `file://` page refused on both doors. Frozen exe rebuilt and
smoked on 8099: all probed endpoints 200, unknown symbol `[]`, served page carries the CSP and
hash-matches the packaged `index.html` (2d51c1b9…), 0 client-error lines, numpy absent.

**Artifacts.** `docs/SECURITY_SWEEP_v0.1b.md` (the report), `SECURITY.md`, four new pin files +
two new tests in `test_wiring.py`; frozen `dist/` rebuilt from the hardened source
(`ModFlowOrderFlowAnalysisSuite.exe`, 12.7 MB), re-zipped (494 entries, 25.9 MB), installer
rebuilt: `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, 28,119,760 bytes (26.82 MB),
sha256 `E71C53C1BE30393ECD9E86187E759C8E9AD8166C0CA53B451618347525F65DD7` (InstallShield, 0 build
errors). Nothing committed; HEAD `fa202d6`.

**IMMEDIATE NEXT ACTIONS.** Owner's release sequence unchanged: commit → repo → push →
tag `v0.1.0-beta` → attach zip + Setup exe. Recommended P1 follow-up: `uv.lock` + a `pip-audit`/SBOM
CI step (SS-8). Optional: re-shoot the pre-P62 branded screenshots (P3).

## §71 — the display / multi-monitor audit (actionables first; nothing changed)

**What.** The owner asked whether every monitor/display scenario is supported — widget stacks dragged
across monitors, custom layouts combined over one or many displays, full break-apart windows — and
for an audit + actionables before any adjustment. Report: `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md`.
Read-only pass: no source touched, gates stay 649/2.

**Method.** Live probe matrix over CDP against a sandboxed server (port 8092): 16 viewport/DPI
scenarios (4K@100/200 … 1024×640, ultrawide, portrait, 5120-wide dual-span, 1920×700), real
reloads, per-canvas backing-vs-box measurements, a live devicePixelRatio swap with no reload
(the "window moved to a 150% monitor" signal), widget drag/resize driven through the shell's own
handlers (synthetic PointerEvents — the harness's raw CDP input never reached the page; stated in
the report), and a grid of claims checked against source.

**Verified working (receipts in the report).** A 10-widget board built at 5120×1440 re-opens at
1024×640 with every widget intact (grid scrolls, page never overflows); drag `+3 cols/+1 row` →
`x=3,y=1`, grip `+2 cols` → `w=8`, edge drags clamp, at 1024/1920/5120 alike; `ui-compact` engages
below 760 px height; `scale.js` detects a live DPR change (reason `resize-observer`, dpr updated)
and the dpr-aware panels (atlas/chart/heatmap/orderflow) are crisp at 150%; layouts auto-save with
`screen_key`; the whole session logged **0 client errors**.

**Defects found (P0, each with a measured receipt).** (A1) `ofx.js`/`ofx-view.js` contain **zero**
`devicePixelRatio` references — the Engine layers are sized in CSS px, so the flagship view is
blurry on any 125/150/200% display (measured 1406×624 backing vs 2109×936 correct at 150%).
(A2) `mpCanvas` (CVD view, Market Pressure) has **no CSS size**, so the generic fit pass is
self-referential: 480×285 → 720×428 in one `OFAPScale.fit()` at 150%, and it grows again each pass.
(A3) `ofxRibbon` backing ≠ its CSS box in both axes (1652×82 vs 1406×84 in a widget) — stretched
lanes wherever panel width ≠ stage width. (A4) `scale.js fitView()` refits only `.view.active` and
`OFAPScale.register` has **zero callers**; `market-pressure.js` and `drawings.js` have no
`ofap:relayout` listener.

**Structural gaps (P1/P2, features not defects).** The window has no memory: fixed 1500×940, min
1080×680 (bigger than a 1024×640 or 1366×768@150% work area), no x/y/screen, no persistence
(config `ui` block verified to hold theme/accent/density only); `screen_key` is saved but **never
applied at boot** (boot trusts the store's `active` only); no second window, no detach, no pinning
anywhere. pywebview 6.2.1 already ships the APIs needed (`webview.screens` measured on this host;
`create_window(x,y,screen,on_top)`; `Window.move/resize/on_top/events`) — and WebView2 **cannot**
start an OS window drag from inside the page, so the workable form of "drag a widget to another
monitor" is a Send-to-monitor/detach command plus aux windows (stated honestly in the report).

**Next.** Owner's call: land P0 (A1–A3 + the refit-scope loop, each with pins and a dpr=1
regression check), then P1 (window geometry + per-screen layout apply), then P2 (widget windows /
send-to-monitor / pinning). A physical multi-monitor pass by the owner is required after P1 — this
host has one display, so placement/unplug/RDP behaviour is simulated, not observed.

---

## §72 — display hardening landed: the dpr canvas law, document-wide refit, window memory, per-screen layouts

The §71 audit's P0 list and P1 items 5/6 are implemented, pinned and live-verified. Everything is
additive: no panel, control, endpoint or stored shape was removed, and the dpr = 1 path is
byte-identical to what shipped before (that is the regression pin, asserted in the modules'
own selftests).

**A1 — the Engine carries the display scale.** `ofx.js` gained the one place the backing-store
maths lives — `math.layerSize(cssW, cssH, dpr)` (dpr = 1 returns the CSS size unchanged) — plus
`layerDpr()`, `sizeLayer()` (own CSS box first, stage box as the fallback) and
`resetLayer(ctx, canvas, dpr)` (clear at 1:1, then paint in CSS pixels). `resize()` stores
`state.view.dpr`; `drawRibbon()` derives its logical size as `canvas.width / dpr`. Every painter's
coordinate maths is untouched — that was the point of clearing at 1:1 and setting the transform,
rather than rewriting twelve painters. `ofx-view.js paintSpark()` keeps the spark's fixed 90×20 /
88×18 CSS box and carries dpr in the backing store (it used to display at its backing size, so a
scaled monitor drew it soft and a fit pass could resize the element).

**A2 — `mpCanvas` has a CSS box and a redraw path.** `market-pressure.js` sets
`style.width = '100%'` / `style.height = '190px'` before measuring, so the fit pass can no longer
read the backing store back as the box (measured growth before: 480×285 → 720×428 in one fit at
150%, then again each pass). It stores `PRESSURE.lastSeries` and repaints from it on
`ofap:relayout`, skipped while a gesture holds the view (`OFAPINTENT.anyHeld()`).

**A3 — the ribbon is stage-width.** The legend's contract is "volume, delta, CVD on the same X as
the bars", and the ribbon paints in the stage's coordinate space (`worldX`/`xToIndex`) — so its CSS
box is now pinned to the stage width in `resize()` (`r.style.width = boxW + 'px'`), and its
backing store is `round(box × dpr)`. Before: a stage-wide backing store displayed across
`width:100%`, i.e. a ~17% horizontal stretch wherever the readout column was visible.

**A4 — the refit covers the board, not the focus.** `scale.js fitView()` now walks every canvas in
the document (default scope `document`); hidden sections and unpainted tabs have a zero box and are
skipped inside `fitCanvas`, so a non-focused terminal widget is refitted after a window or
display-scale change. `drawings.js` and `market-pressure.js` now listen to `ofap:relayout` too
(the audit's verified listener list was `atlas.js`, `heatmap-pro.js`, `ofx-view.js`, `strips.js`).

**B1 — the window remembers its geometry.** `config_store` ships `ui.window`
(`{width, height, x, y, maximised}`, `x`/`y` None until first close) and `clean_window()` clamps it
(640…10000 × 420…6000, position kept only while ±20000 — a monitor left of the primary is
negative). `launcher.pick_window_geometry(stored, screens)` is the pure choice, unit-tested through
every branch: a stored position wins while a screen still contains it, otherwise the primary; the
size and the minimum clamp to that screen's work area; the pre-§72 geometry is unchanged when no
screen can be measured. The design minimum is now 720×480 with a hard floor of 320×240 **under the
work area** — a 1366×768 display at 150% reports ~911×512, and the old fixed 1500×940 with a
1080×680 minimum could not fit it at all (the test that caught this is
`test_a_display_at_150_percent_is_usable`). `remember_window()` subscribes to the window's
moved/resized/maximized/restored events, keeps the last *normal* rect while maximised, and writes
the config **once, on close**.

**B2 — the layout for this screen is applied at boot.** `shell.js math.screenKeyOf()` composes the
screen identity: `WxH@dpr` at the primary origin (so layouts saved before this still match it) and
`WxH@dpr@x,y` anywhere else, where x/y are the screen's own origin from `window.screen.availLeft/
availTop` — two identical monitors are then two different screens. `math.pickScreenLayout(items,
key, active)` returns the id to switch to (most recently `saved` wins; empty when this screen has
no layout of its own or that layout is already active), and `boot()` adopts it in terminal mode
with a visible notice: `this screen's layout: "…"`.

**Receipts.** Suite **679 passed / 2 skipped** (was 649/2; +30 = `test_display_geometry.py`),
AUDIT CLEAN, ruff clean, both goldens byte-identical, 20 selftests green (ofx 180 → 183, shell
22 → 30). Live on a sandbox (scratch `APPDATA`, so the owner's real config was never touched),
1440×900:
- engine layers: box `1086×520` → backing `1358×650` / `1629×780` / `2172×1040` at 125/150/200%
  (= `round(box × dpr)`, exactly); `OFX.state.view.dpr` tracks the display.
- ribbon: box `1084×82` → backing `1084×82` at 100% (no stretch), `1626×123` at 150%, with
  `style.width = 1086px` = the stage width.
- `mpCanvas`: box `1304×190` → backing `1956×285` at 150%, **identical across three consecutive
  fit passes** (proving the self-referential growth is gone).
- four-widget terminal board at 150%: every visible canvas box × dpr, **zero mismatches**
  (`ofxHeat`, `ofxBase`, `ofxLive`, `ofxRibbon`, `ofxSpark`, `ofxSpark2` + one anonymous canvas).
- a synthetic heat frame painted at 200% (`heatPasses` 0 → 1) with no error; the whole session
  logged **0 client errors**.
- per-screen layouts: a layout saved through the shell's own writer carries `screen_key
  '800x600@1.5'`; with `active` pointed at a different layout, a reload adopted "Probe Screen
  Layout" and showed the notice in the bar.

**Files.** Changed: `desktop/ui/ofx.js`, `ofx-view.js`, `scale.js`, `market-pressure.js`,
`drawings.js`, `shell.js`, `desktop/config_store.py`, `desktop/launcher.py`; pins:
`desktop/ui/ofx.selftest.js` (+5, incl. the dpr = 1 identity), `desktop/ui/shell.selftest.js` (+8),
`test_display_geometry.py` (new, 30 tests). **Remains open:** B3 (always-on-top toggle), P2
(detached widget windows / send-to-monitor / pinning — a feature build, pywebview's
`create_window(screen=, on_top=)` and `Window.move/resize` are the APIs), and the owner's physical
multi-monitor pass (this host has one display). The frozen `dist/` artifacts were rebuilt after
these changes so the release candidate matches the source.

---

## §73 — widget windows: one panel per native window, placed on a monitor, restored on launch

The §71/§72 audit's P2 item and its P1 item 7 (always-on-top) are built. A power user can now pull
any panel out of the board into its own real native window, put it on another monitor, pin it above
other windows, and find the whole arrangement back after a restart. Everything is additive: with no
native host (a browser, a headless run, a test) the endpoints say `native: false` and the UI draws no
window controls at all — the browser experience is byte-for-byte what it was.

**The seam, and why it is shaped this way.** The page decides *what* should be in a window; the
launcher owns *how* a window comes into existence. Between them:

- `desktop/windows.py` — `place_aux(record, screens, count, screen_index)` is the pure placement
  choice (an explicit monitor wins; a stored position wins **while a screen still contains it**, so
  an unplugged monitor can never place a window off-desktop; size and position clamp to that
  screen's work area; a fresh window cascades by 28 px so two opens do not stack). The module also
  carries the `WindowHost` contract, the installed host, and the record persistence (`records`,
  `add_record`, `drop_record`, `update_geometry` — throttled to one config write per 2 s).
- `config_store` — `ui.windows` is the **desired set**: opening adds, closing (from either side)
  removes, and a launch restores exactly what was open. `clean_window_record`/`clean_windows` clamp
  it (identified ids, view slugs, 360…6000 × 300…4000, unique, capped at 8).
- `desktop/api.py` — `GET/POST /api/control/windows`: the state (screens labelled "Monitor 1 ·
  2560×1440 · 150%", what is open, the stored set, the cap), and the actions `open / close / focus /
  ontop / close_all`. Every answer carries the *resulting* state; `native: false` is a first-class
  answer, not an error.
- `desktop/launcher.py` — `NativeWindowHost` creates the real pywebview window (`?aux=<view>&win=<id>`,
  `on_top`, `min_size`), keeps the store's geometry current from the window's own moved/resized
  events, and drops the record when the window closes (including the OS's X).
  `restore_windows(port)` reinstalls the host and reopens the stored set **before**
  `webview.start()`, re-placing anything whose monitor is gone.
- `desktop/ui/windows-ui.js` (new) — everything the user touches: the menu is built from a pure
  `OFAPWINDOWS.model(state, focus)` (unit-tested in Node), the terminal bar and the Classic top bar
  each carry the control (exactly one visible, following the mode), and the auxiliary window's own
  bar carries its pin and its close.
- `desktop/ui/shell.js` — `?aux=<view>` is detected as `AUX`: the window renders a synthetic
  one-widget layout, **never** reads or writes a layout, never changes the mode, never adopts a
  screen's layout, clears its hash at boot and refuses to add a second widget.

**Receipts (live, on the owner's desktop, scratch `APPDATA` so his config was never touched).**
Real windows enumerated with `EnumWindows` at each step:
- opened `ofx` → a visible window "… — OFX" at (680, 282) 1200×820 — the placed centre of the
  2560×1440 screen; a second window (`cvd`) cascaded to (758, 340); a third from the board's
  terminal-bar control after focusing it.
- pin → `on_top` in the store, and the aux window's own 📌 button flipped it (CDP-driven UI click).
- close from the API, close from the aux window's own ×, and close from the **OS** (WM_CLOSE, i.e.
  as if the user clicked the title-bar X): each removed the window and its record.
- quit and relaunch → both stored windows came back at their exact stored rects, pinned state
  intact (`open after restore: ['w303bd2c', 'w7185c6f']`).
- the UI itself, driven over CDP into WebView2 (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port`):
  Classic shows `⧉ Windows · 1` in the app's top bar and the terminal bar shows nothing; switching
  to terminal mode moves the control to the board's bar and empties the top bar; the menu listed the
  open windows, "Close every widget window", "Open OVERVIEW in its own window" and "Send OVERVIEW
  to ▸ Monitor 1 · 2560x1440"; clicking a row really opened the window. An auxiliary window renders
  **exactly one widget** with no tabs, its name in the title, its pin and close — and its note says
  `this window is fixed to Time & Sales` if anything tries to add a second panel.
- Two real defects the live pass found and closed: `#overview` (the previous window's hash) made the
  aux window open a **second widget** through the shell's `showView` hook → guarded in `openWidget`
  and the hash is cleared at aux boot; and in Classic mode the control did not exist at all (the
  terminal bar is a terminal-mode object) → the app's top bar now carries a copy, and the target for
  "open/send" in Classic is the view being looked at.

**Gates.** Suite 679 → **712 passed / 2 skipped** (+33 = `test_aux_windows.py`), AUDIT CLEAN (275
html ids + 229 created, 0 missing), ruff clean, both goldens byte-identical, **21** selftests green
(new: `windows-ui.selftest.js`, 10 checks).

**Honest limits.** Literal drag-a-widget-out-of-the-window is impossible on WebView2 — there is no
OS-level drag initiation from inside the page — so the shipped form is the command path
(Windows ▸ Open / Send to monitor ▸), which is also what a keyboard user gets. Moving an *aux* window
between monitors is the OS's own drag, and its geometry is remembered when it lands. As with §71/§72,
the physical multi-monitor pass is the owner's: this host has one display, so "a second monitor" was
exercised as a second *window* on one screen plus the placement maths under test for every screen
shape.

**Files.** New: `desktop/windows.py`, `desktop/ui/windows-ui.js`, `desktop/ui/windows-ui.selftest.js`,
`test_aux_windows.py`. Changed: `desktop/api.py` (endpoints), `desktop/config_store.py`
(`ui.windows` + clamps), `desktop/launcher.py` (`NativeWindowHost`, `restore_windows`, wired into
`main()`), `desktop/ui/shell.js` (AUX mode, aux bar, guards), `desktop/ui/index.html` (script tag +
`#topWins`), `desktop/ui/atlas.css` (§73 styles).

---

## §74 — the pre-tag pass: the corpus is committed, the counts refreshed, SS-8 closed

**What this pass is.** With the owner's go, the fixed tree went into history and the release face
was made exact: commits, docs/counts, CI, lockfile. No source semantics changed.

**The series — 18 commits, `fa202d6..14b4759`** (`git log --oneline fa202d6..14b4759` is the register):

```
1aa2a17 atlas: the alerts card reads, edits and fires like the engine means it (P1-7)
a5b0086 desktop: five bar expression modes, measured palettes, and the legend that names them (P1-8)
457bc28 desktop: the one shortcut map, and the palette crash it uncovered (P1-9)
b6e63ec desktop: the age of every panel's data, declared (P1-10)
3b3ff83 desktop: the hover path is indexed, the heat pass change-gated, the frame yields (P2)
26930fe data: the session has a boundary, the database has a window (P3-2)
01f2204 atlas: the heat wire, the carry-overs, and the inline text editors (§56/§57)
efb86a1 desktop: the ModFlow badge becomes the iconography (§60–§62)
272f85c chore: the package diet — numpy out, stdlib in (§63)
0b3507c fix: the source switch called a property; the Python 3.11 hang — the release passes (§64/§65)
c35dd59 chore: the lint pass — unused imports and dead aliases dropped (§64)
350d360 tests: the v0.1b audit return — seven fixes pinned, three probes rejected (§66–§68)
f822052 installer: the Windows installer built, verified, documented (§69)
ea83c48 security: the secure2 sweep — the loopback boundary, feed gates, release hygiene (§70)
4110ea6 desktop: display hardening — the dpr canvas law, refit, window memory (§71/§72)
c25f36d desktop: widget windows — one panel per native window, placed and restored (§73)
fcd0a21 docs: the trail through §73, and the pre-release count pass (handoff, plan, resume, readme)
14b4759 chore: the dependency lock, the CI audit, and the third-party notices (SS-8)
```

**How it was split.** One commit per wave, each file staged exactly once (verified: 166/166 dirty
entries assigned, no file in two commits). A file touched by several waves carries its **final**
content in the latest wave's commit — `index.html` rides in the §73 commit, `dashboard/app.py` in
the §70 commit. The per-section change sets at the end of §§40–65, §70, §72, §73 remain the
authoritative file→section map; the messages carry the §-refs.

**The release face, made true (the audit's N-2/N-3).**
- `SECURITY.md` — the vendored chart library is **Apache-2.0** (was mislabelled "MIT"); the version
  string is `v0.1.0-beta`. New `THIRD_PARTY_NOTICES.md` at the root: the vendored copy (banner
  retained) + the Python dependency licence story (the frozen build carries
  `_internal/*.dist-info/licenses/`).
- Counts re-derived (2026-09-16): suite **712/2 on both interpreters**; UI selftests **20** (shell
  30, ofx 183, + windows-ui 10 — RESUME's list updated); README badges true (tests 644→712, code
  ~62k→~64k, API 132→**133** routes — measured from the running app's OpenAPI: 45 atlas + 72
  control + 16 legacy); File Inventory re-measured (**175 files / 27,237 py / 36,583 UI / 63,820
  total**; suite 68 files / 12,371 lines); the tree diagram's `(NNNL)` claims re-checked — five
  drifted since §66 and were corrected (app.py 1371, bybit_feed.py 329, absorption.py 266,
  initiative.py 136, settings.py 815); CONTRIBUTING baseline updated.

**SS-8 closed.** `uv.lock` committed (59 packages, `uv` 0.12.8); CI gains a pinned dependency-audit
step: `uv export --frozen` (lockfile integrity) → `pip-audit` over the locked set — clean on
2026-09-16. `.gitignore` covers the tool caches. An SBOM artifact remains optional.

**Receipts.** pytest **712 passed / 2 skipped** on 3.12 (24.5 s) *and* 3.11 (24.5 s) — on the exact
committed content; `audit_ui_refs.py` **AUDIT CLEAN** (71 modules); ruff clean; analytics golden
**0.000e+00** (40 cases); config golden **49 instruments**; **20/20** selftests; API surface **133**
operations. Frozen artefacts re-verified against the committed tree: **90/90 bundled loose files
byte-identical**, no source file newer than the build — **no rebuild needed** (docs/CI-only pass);
the zip/setup exe hashes in the RE-ATTENDANCE block remain the release candidates.

**Next (owner).** Push (the remote decision), the physical multi-monitor pass, release-notes
review, then the tag `v0.1.0-beta` + attach zip + Setup exe.

## §75 — the post-beta left-overs: N-1 in the build, CI lint/SBOM parity, and the screenshot re-shoot (closed)

**Why.** After §74 this pass picked up the plan's optional left-overs, asked for in one breath:
(1) the N-1 single-instance guard, (2) ruff-in-CI step parity (N-4), (3) an SBOM artifact (SS-8
was pip-audit only), and (4) re-shooting the pre-§62-branded screenshots in `docs/screenshots/`
(the Sep 14 batch still shows the retired OF tile / "OrderFlow Analysis Pro" wording; the Sep 16
p-series already carries the ModFlow badge). The owner paused the pass mid-way to bank the state
(`b0681a2` was the save point); the **re-attendance closed it** — screenshots landed, counts
re-measured, `dist/` rebuilt and re-verified, gates green on both interpreters — and the closing
commits are `58101f4` (the shots, the counts, the release evidence) and this record.

**Landed and committed.**

* `12211e2` — **the single-instance guard (N-1).** `desktop/single_instance.py`: a named mutex keyed
  to the config directory (sha1 of the casefolded path), taken on windowed launches only — headless
  runs stay exempt because every smoke recipe opens its own scratch APPDATA and runs alongside the
  owner's app; non-Windows is a no-op; unexpected OS errors fail open. A second windowed launch
  finds the mutex held, brings the existing window forward (EnumWindows by window title, best
  effort) and exits 0; if no window can be found it says so in a message box. 4 pins in
  `test_single_instance.py` (name stability across case/slashes/trailing separator, a second
  acquisition of a held name refused, reacquisition after release, a quiet focus miss). Wiring:
  `launcher.main`, after config load, `if not args.headless`. Suite: **716 passed / 2 skipped**
  (3.12, 24.4 s — 712 + the four new pins; the 3.11 re-run belongs to this pass's end).
* `d4fe370` — **CI parity + SBOM (N-4; SS-8's artifact).** CI now pins `ruff==0.16.7` and runs the
  lint baseline on 3.11 and 3.12 (the step CONTRIBUTING always described but CI skipped), and the
  dependency-audit job gains a lockfile SBOM: `uv export --frozen --format cyclonedx1.5`, uploaded
  with `actions/upload-artifact` pinned to v4.6.2 (`ea165f8d`). CONTRIBUTING's intro sentence now
  reads "the lint baseline and a dependency audit". The release SBOM for this build was generated
  beside the zip: `dist/ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json` (CycloneDX 1.5, 42
  components) — attach it to the GitHub release with the zip and the Setup exe.

**The screenshot re-shoot — landed.**

Eleven shots (the Sep 14/15 batch: 4 atlas-* + 7 desktop-*) were re-captured from one live sandbox
session at their original dimensions and are now in `docs/screenshots/` (1264×569 for the atlas-*
set, desktop-heatmap-live and desktop-chart-value-area; 1500×940 for the desktop-* set — every
frame matching the size of the file it replaced, header-checked), all from one clean run (green
Setup dot, no wizard, no MT5 notice). **All eleven were vision-checked**, one was re-shot:

| file | size | state |
|---|---|---|
| atlas-heatmap.png | 1264×569 | verified — map canvas full |
| atlas-cvd.png | 1264×569 | verified — divergence series + table drawn |
| atlas-profile.png | 1264×569 | verified — TPO ladder + volume bars drawn |
| atlas-trackers.png | 1264×569 | verified — live prints + ladder |
| desktop-heatmap-live.png | 1264×569 | verified — full liquidity map (240 buckets × 200 rows) |
| desktop-chart-value-area.png | 1264×569 | **re-shot this pass** — card note + POC/Δ-V chips, no clip |
| desktop-overview-live.png | 1500×940 | verified — KPIs, session summary, market context |
| desktop-live-session.png | 1500×940 | verified — live session, Stop engine visible |
| desktop-window-overview.png | 1500×940 | verified — live session + headlines |
| desktop-window-heatmap.png | 1500×940 | verified — full liquidity map |
| desktop-chart.png | 1500×940 | verified — candles + VWAP band + the POC line |

**One re-shoot, and the rule it taught.** `desktop-chart-value-area.png` first came back with the
Price-action card's note clipped mid-line at the top edge — the previous session had scrolled the
view's scroller ~297 px to bring the chart canvas up. Fix (now in the skill's screenshot
reference): **align the card head to the scroller top by measuring** (`.views` scroller +=
`card.top − views.top`), never by a fixed amount — and read the 70–100 px band under the toolbar as
chrome, not as a clip: the toolbar's own controls (`Classic|Terminal` segment, `Stop engine`, the
live chip) stick ~16 px into the content area and look like clipped content in a crop.


The sandbox: `APPDATA="$LOCALAPPDATA/Temp/ofap_shots_sandbox" .venv/Scripts/python.exe -m
orderflow_system.desktop --headless --port 8093`, engine started via `POST
/api/control/engine/start`; PID 20564 at save time (`taskkill /PID 20564 /F` to stop — scratch
APPDATA only, nothing of the owner's touched). Sandbox config carries `onboarding_done: true`,
`setup_complete: true`, `mt5.notice: seen`, so a reload carries no wizard, a green rail dot and no
MT5 notice.

The capture recipe (browser tool; the daemon session was named `shots`):

1. `goto_url('http://127.0.0.1:8093/desktop/')`, wait; switch views with **`showView('<slug>')`**
   (slugs = the rail's `button.nav-item[data-view]` values — overview, chart, heatmap, cvd,
   profile, trackers, …; no hash navigation).
2. Size via CDP `Emulation.setDeviceMetricsOverride` — **1264×569** for the atlas-* set, heatmap-live
   and chart-value-area; **1500×940** for the desktop-* set. The override persists across calls in
   a session — reset it before each size group.
3. Heatmap views: scroll the view's scroller so the biggest canvas sits ~30 px below the scroller
   top (the map otherwise sits below the cards fold).
4. Chart shots: `#ovVP` (the POC/VAH/VAL overlay checkbox) on.
5. Overlays: wizard `#wizClose`; MT5 notice `#mt5NoticeNever`. Both fire on a fresh load until
   their config flags are set.
6. Capture with CDP `Page.captureScreenshot` (PNG) → write the bytes to the staging dir.

**How the re-attendance closed (in order).**

1. **Screenshots** — the six "check due" frames vision-checked plus the five eye-verified ones
   reviewed; one re-shoot (`desktop-chart-value-area.png`, above); all eleven copied into
   `docs/screenshots/`, and the caption rows in `docs/DESKTOP_GUI_FEASIBILITY.md` re-written to
   describe these files (kept timeless where the numbers moved) with a line recording the re-shoot.
2. **Counts** — README tests badge 712 → **716**; File Inventory re-measured (**176 files /
   27,407 py / 36,583 UI / 63,990 total** — the Desktop-app row 23 → 24 files, 8,895 → 9,065 lines:
   `single_instance.py`'s 162 plus `launcher.py`'s +8 net); suite **69 files / 12,422 lines**;
   CONTRIBUTING's baseline 716. The `launcher.py` (NNNL) row the plan expected does not exist — the
   Project Structure tree carries no per-file counts for `desktop/`; the File Inventory row is where
   the growth shows. One stale count turned up while re-measuring: the architecture diagram's
   "132 REST/WS routes" (the badge already read 133) — corrected.
3. **Rebuild.** The guard touched a bundled file, so the frozen `dist/` (zip `b571c655…`, Setup
   `d2435b6f…`, exe `cfde70b0…`) was stale as a release candidate since `12211e2`. Rebuilt the
   chain — exe (`build_exe.py`) → zip → Setup (`installer/make_installer.ps1`, 0 errors) — re-ran
   the payload check (90/90), the live probe battery (21/21) and the new double-launch acceptance
   on the frozen exe, and re-ran the installer journey. New hashes in
   `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`; the stale ones are gone from this file.
4. **Gates on the final tree** — full pytest on **both** interpreters (716/2 each), audit_ui_refs
   (AUDIT CLEAN), both goldens, 20 selftests, ruff, `pip-audit`: all green (receipts below).

**Receipts.** Suite **716 passed / 2 skipped on both interpreters** (3.12 in 24.4 s, 3.11 in
24.6 s); `audit_ui_refs.py` AUDIT CLEAN (71 modules); ruff 0.16.7 clean; analytics golden 0.000e+00
(40 cases, 2196 numeric leaves); config golden 31/18/49; **20/20 UI selftests**; `pip-audit` over
the locked set (42 packages) clean. Screenshots 11/11 vision-verified at their original sizes and
landed in `docs/screenshots/` (+ captions). Frozen artefacts rebuilt from the hardened tree: exe
`10e6bdf8755abb0e…` (13,371,238 B), zip `00b96304e54949e0…` (27,229,338 B — 496 files, 7-Zip test
OK, extraction byte-identical to the folder), Setup `c3a14576a5a5a5b5…` (28,173,338 B, 0 errors /
4 warnings, ships the same exe), SBOM CycloneDX 1.5 (42 components); all four hashed into
`docs/RELEASE_EVIDENCE_v0.1.0-beta.md`. Payload check: **90/90 loose files byte-identical** to the
tree, no source file newer than the build. Probe battery against the frozen exe: **21/21** — hostile
`Host` → 403 on `/healthz` and `/api/control/bootstrap` (nothing leaked), cross-origin + cross-site
POST → 403, cross-origin + cross-site WS handshake → 403, native WS → 101 with the app's own
`pong`, same-origin/native POST → 200, cross-origin read → 200, `/desktop` byte-identical to the
packaged `index.html` (sha256 `d61ebc1f8c2c33d3…`) and carrying the CSP, unknown symbol → `[]`
(candles + markers), 0 numpy entries in 586 `_internal` entries, 0 `client error:` lines.
Double-launch acceptance (windowed, scratch APPDATA): first launch opens the window on 8080; the
second **exits 0** and focuses it — still one process, one window, one port; a third is refused the
same way; WM_CLOSE closes in ~2 s, frees the port, and the next launch comes up (the guard releases
on close). Installer journey: silent install 496 files, installed exe hash == dist exe, shortcut
targeting the installed exe, ARP entry `0.1.0` (`{197F9514-…}`); the installed app smoked on 8098
(healthz 200, BTCUSDT candles 200, unknown symbol `[]`, hostile Host refused, 0 client errors);
silent uninstall cleaned dir + shortcut + ARP; `%APPDATA%` untouched and the owner's development
shortcut restored.

**Two build-tool lessons (both measured here).** (1) PowerShell 5.1's `Compress-Archive` **mangles
this tree's archive entry names** (truncated prefixes, the main exe entry lost) — the release zip is
built with Python's `zipfile` (or 7-Zip) instead; verify with `namelist()` + a `7z t` pass. (2) The
installer's Add/Remove Programs entry registers under the **32-bit** registry view
(`HKLM\Software\WOW6432Node\…\Uninstall`), so a native-view query reports "no ARP entry" while the
product is installed — query the WOW6432Node key (or `Win32_Product`) before concluding anything
about the install.

**Nothing pushed.** The owner's queue is unchanged: push (the remote decision — `origin` is still
the original author's repo), his **physical multi-monitor pass** (§77 if it finds anything — §76 is
the fold-in below), the release-notes/tag review, then the tag `v0.1.0-beta` + attach the zip + Setup
exe + SBOM.

---

## §76 — the flowsurface fold-in: Binance ingest, trade audio, archive backfill, two more venues (closed 2026-09-17; nothing committed)

**Why.** The owner approved a subset of `docs/FLOWSURFACE_FOLD_IN_PLAN.md` (ideas only — flowsurface
is GPL-3.0, so not one line of its code is in this tree): **Binance first**, **ship four generated
finance-alert samples**, **both** backfill paths, and the heatmap "order runs" model **deferred**
behind its measured triggers. This section is the receipt for what is on disk; nothing is committed.

**Gate status at the end of the pass (measured, one run):** **839 passed / 2 skipped** (3.12) ·
`audit_ui_refs.py` AUDIT CLEAN (74 modules) · **22/22** JS selftests · `ruff check` clean.
`HEAD` is still `aa43f40`, **36 paths** modified or new (these two docs included), `dist/` **not**
rebuilt.

**1. The feed-session rule (`data/feed_session.py`, new) and the Bybit hardening.**
The flowsurface bug at its newest commit is a Python-shaped bug: a read future cancelled mid-frame by
a shared timeout desyncs the parser and the socket dies with a protocol error that looks like a venue
problem. The rule is now a module: the **reader is never cancelled**, the **heartbeat is its own
task**, each venue's liveness is **data** (`VENUE_POLICIES`: bybit client-ping 20/60, binance
server-driven 240, hyperliquid ping-after-idle 30/…, okx ping-after-idle 20/40), the reconnect ladder
**resets only on a parsed frame** and carries **±25 % jitter** so several adapters cannot stampede a
venue at once. `data/bybit_feed.py` got the same two-line treatment (the ladder no longer resets when
a socket merely *opens* — a connect-and-die loop used to hammer the venue at 1 s forever).
*Pins:* `test_feed_session.py` (11) — including the replayed-cancellation detector and the Bybit
ladder, both driven by a **virtual clock** so the timing contract is tested without waiting.

**2. Binance USDⓈ-M futures (`data/binance_feed.py`, new).** Public streams + REST snapshot with the
chain rules the venue actually documents: buffer diffs while the snapshot lands, drop `u < lastUpdateId`,
require the first applied event to straddle (`U ≤ lastUpdateId+1 ≤ u`), then require `pu == previous u`;
on a break, mark stale, clear the buffer and refetch — deduped and rate-limited (`snapshot_cooldown_s`),
so a stale book always has exactly one fetch outstanding and heals itself. 1000 levels/side from the
REST snapshot (Bybit gives 50 base / 200 extras).
*Live-verified, and the live check earned its keep:* **on futures the documented `@aggTrade` stream
does not flow — `@trade` does.** The adapter subscribes `@trade` (individual fills, which is also the
better input for footprint/CVD than a 100 ms aggregate) and parses both shapes (`e: trade`/`aggTrade`,
id from `t`/`a`). Live: 4,759 ticks / 20 s over BTCUSDT+ETHUSDT, 382 book publishes, both books
1000×1000, 0 gaps, 0 junk, 0 reconnects; the pre-snapshot stale window behaves as designed.
*Wiring:* `settings.DataSource.BINANCE`, the config allow-list, `main.py`'s feed branch,
`FREE_SOURCES` `wired=True`, `datasources()` + `binance_capable()`/`binance_validate()` (one
`exchangeInfo` call), the guide wizard radio, and **`_start_atlas_extras` skips the Bybit extras feed
when Binance is the primary source** — the extras book is a Bybit book, and mixing it under another
venue's prints would be a lie the heatmap tells.

**3. Trade audio (new; his explicit choice).** `scripts/make_alert_sounds.py` (stdlib only) generates
four WAVs into `desktop/ui/audio/`: soft buy/sell blips (90 ms, 1.18 kHz / 880 Hz bells over a
tape-tick transient) and rising/falling two-tone alerts (225 ms, 1046↔1568 Hz). `ui/audio.js` is a
decide/play split: `decide()` is pure (master switch, `min_size` threshold, the two-tone variant at
`min_size × hard_multiple`, overlap attenuation halving per retrigger down to `overlap_floor`, the
active-symbol rule) and `play()` owns the elements (one per sample, `play()` rejections counted and
announced as `ofap:audio-failed`, never a crash). Config: an `audio` block, clamped **twice** —
`config_store._sanitise` (strict: only a real `True` enables, a hand-edited `"yes"` cannot) and the
player. Eight registry parameters put it in the **Tape** view's Chart menu; `applyLocally` adopts the
accepted value without a round trip. Off by default.
*Pins:* `audio.selftest.js` (39) + `test_alert_audio.py` (11) — the WAVs' format, that they are four
different sounds, audible-and-not-clipped, that the shipped files are **byte-reproducible from the
generator**, and the clamp contract.

**4. Archive backfill (both paths).** `data/backfill.py` + `POST/GET /api/control/backfill` +
`GET /api/control/trades` + `Database.delete_ticks_window/count_ticks/get_recent_ticks`.
Four rules worth keeping: a **window is replaced, never appended** (delete + insert for the same
window, so re-running an interrupted day cannot double-count volume); the parse runs in **one worker
thread feeding a bounded queue** (a day of a liquid instrument is millions of rows — never parse it on
the event loop); the timestamp's **unit is detected, not assumed** (16-digit ⇒ µs ⇒ ÷1000; verified
live that the current futures file is ms); and junk rows are gated (integer trade id, plausible
timestamp ≥ 2019-06, positive price/size) because a mangled line quietly poisoning a volume profile is
exactly the failure nobody sees. Downloads land in `.part` and are renamed on completion, so a
half-download can never become a cache hit; the cache prunes by age; the job is **one at a time** with
a stage/ticks progress channel.
*Live end-to-end:* a real DYDXUSDT archive (150 KB, 2026-09-13) → **9,799 rows** into a scratch DB,
first ts 00:00:04Z / last 23:59:57Z, every row inside the day, sides 4,591 buy / 5,208 sell.
*Pins:* `test_backfill.py` (18) + `test_backfill_api.py` (11).

**5. Two more venues, delegated (files only, NOT wired).** `data/hyperliquid_feed.py` (+27 tests) and
`data/okx_feed.py` (+23 tests), both built on `FeedSession` with their own policies, both run against
their real venues by their authors before being reported. The venue realities they found (each is a
documented behaviour that is **not** what the docs say):
- **Hyperliquid:** frames *are* wrapped (`{channel, data}`); trades arrive as **arrays**; `side` is the
  taker side (`B`/`A` — confirmed against the book's mid); the **l2Book is a 20-level snapshot**, not a
  diff stream (~2.6–5.6 s cadence, hence a 10 s stale window, configurable); the REST `meta` listing is
  the only real gate — an **unknown coin does not error, the venue drops the socket ~0.2 s later**, and a
  **delisted coin acks and then streams a dead backlog** (MATIC prints from 2024), so `isDelisted` is
  read and skipped; no coin name in the listing contains "USD" (so `BTCUSDT → BTC` cannot collide);
  the venue answers the library's protocol pings *and* the documented `{"method":"ping"}`, so the
  session stays the single liveness owner (`ping_interval=None`); `tick = 10^-(6-szDecimals)` verified
  live (BTC one decimal, MATIC five). The 5-significant-figures half of the venue's price rule is
  **documented but deliberately not enforced** (rounding could alter a legitimate print).
- **OKX:** the `crc32` checksum is **dead** — every live frame carries `checksum: 0` and the venue now
  marks the field deprecated in favour of `seqId`/`prevSeqId`, so the documented algorithm is
  implemented and tested (self-consistent vector + mutation rejection) but a `0` is read as "no
  verdict" and **continuity comes from `seqId`/`prevSeqId`** — verified live (snapshot `seqId` == the
  next update's `prevSeqId`). `{"op":"ping"}` is **rejected** (`60012`); a bare text `ping` is answered
  by a bare `pong` — which is exactly what `FeedSession` sends by default, so the policy drives it
  untouched and the frame handler counts pongs instead of logging a parse error. Re-subscribing is only
  re-acked; the working resync is **unsubscribe → subscribe** (verified live: an immediate fresh
  400×400 snapshot, other symbols untouched). REST needs a **User-Agent** (a bare urllib request is
  403'd) and the listing's coin-margined swaps are filtered out via `settleCcy`. Live adapter run:
  644 ticks, 286 book publishes, 400×400 books, 0 gaps, 0 reconnects.
  **Open concern flagged by its author and NOT acted on:** `VENUE_POLICIES["okx"].silence_budget_s = 40`
  is shorter than the venue's documented ~60 s quiet-instrument keepalive — worth a look when OKX is
  wired (no live evidence of harm; the quietest listed USDT swap still pushed ~10 updates/s).

**6. The polish pass — and the finding that most of it already existed.** Of the plan's four tape/heatmap
"gems", **three were already implemented here under other names**: the pause-on-scroll + "N new" pill is
`OFAPSTRIPS` (per-strip chips with counts and click-to-resume), size shading is `isBig` →
`tape-row-big`, and the heatmap cell readout is `heatmap-pro.cellAt()` + its HUD. Only the
**changed-digit price tint** was genuinely missing and landed: `tape.js` wraps only the digits that
moved against the older print (`_priceHtml`, a width change is left plain, the decimal point never
tinted), threaded through `_prependRows`/`_renderTrades` with a `_topPrice` tail so the tint is
continuous across batches. `tape.selftest.js` (11) pins the rule **and** that `modules.css` defines the
class the widget emits. (Read the panel before believing a feature list — three of four "gaps" were not
gaps, and folding them in again would have been duplicate work.)

**What is NOT done (the next session's list, in order):**
1. **Wire Hyperliquid + OKX exactly like Binance** — `settings.DataSource`, the config allow-list,
   `main.py`, `FREE_SOURCES` wired flags, `datasources()` rows, the capabilities/validate pair, the
   extras gate, the wizard radios — then live-probe both **from the repo tree**.
2. **Sandbox end-to-end**: source switch to Binance through the control API, the audio parameters
   through `/api/control/params`, a backfill round trip over the API, then `orderflow.log` for
   `client error:` lines.
3. **Counts/docs pass**: README badge 716 → 839, CONTRIBUTING baseline, File Inventory (py files +~6,
   four WAVs, the new modules), the selftest list 20 → 22, and `docs/FLOWSURFACE_FOLD_IN_PLAN.md`
   marked as executed (with what was deferred and why).
4. **Then the owner's queue**: push, his physical multi-monitor pass (**§77** if it finds anything),
   release-notes review, tag `v0.1.0-beta` + attach zip + Setup exe + SBOM. A `dist/` rebuild is owed
   before any release artefact is replaced — nothing in this pass was built into it.
5. The 3.11 parity run for this build (839/2 was measured on 3.12 only).

---

**§76 closed (2026-09-17).** The list above is done — plus what the verification found on the way:

1. **Hyperliquid + OKX wired exactly like Binance, then live-probed from the repo tree.**
   `DataSource.HYPERLIQUID/OKX`, the config allow-list, `main.py`'s feed branches, `FREE_SOURCES`
   `wired=True` (hints now say what the adapters actually do), `datasources()` rows, the
   `hyperliquid_capable/validate` + `okx_capable/validate` pair (`/api/control/capabilities?
   refresh=true`, the one-implementation rule Binance set), the extras gate widened to
   `("binance", "hyperliquid", "okx")`, the wizard radios + its MT5 step, and the `settings.py`
   DataSource comment block re-aligned (it had been missing BINANCE).
   *Live:* Hyperliquid **128 ticks / 20 s** (20×20 books, 0 junk, 0 reconnects); OKX **577 ticks /
   20 s** (400×400 books, 0 gaps, 0 reconnects). *Pins:* +3 tests in `test_source_switch.py`
   (wired-and-switchable for both; the refusal path re-pinned via a patched table row), +1 in
   `test_wiring.py` — 839 → **843**.
2. **Two flagged concerns turned into work:**
   - **The reachability probe speaks the venue's method now.** Hyperliquid's `/info` answers a bare
     GET with **405** — the old probe painted it "unreachable" while healthy. `_probe_source` takes
     an optional POST payload (`_PROBE_PAYLOADS`); the Connections menu shows **ok** (live-verified).
   - **The OKX silence budget is 75 s** (was 40): the venue's documented quiet-instrument keepalive
     is ~60 s, so 40 tripped first. Insurance, not a fix for an observed failure — pinned.
3. **A live defect surfaced while verifying, and it sat right on this wiring's front door:** the ☰
   menu (`desktop/ui/menu.js`) had a local `api()` whose guard tested `typeof api` — itself — so
   every call recursed and the `RangeError` died in each caller's `catch`. The menu ran entirely on
   fallback data (`/sources` never loaded; switching answered "source switch failed: RangeError:
   Maximum call stack size exceeded"). Fixed to `typeof window.api`; pinned by
   `test_wiring.py::test_a_module_local_api_helper_must_name_the_shells_helper`; re-verified live
   over CDP (Edge :9223) — the menu lists the six server rows and real clicks switch OKX → Binance
   (`Engine started: source=okx|binance` in the log).
4. **The sandbox pass (scratch `APPDATA`, port 8094):** source switch to Binance (tape + orderbook
   live), the eight audio parameters driven through `/api/control/params` (adopted values read
   back; the config block matches), a backfill round trip — DYDXUSDT 2026-09-13 → **9,799 ticks /
   150,613 B downloaded fresh**, `/api/control/trades` returns all 9,799 inside the day with sides
   4,591 / 5,208 *(identical to §76's module-level receipt)* — then engine switches to okx →
   hyperliquid → binance with per-symbol ticks > 0 (394 / 91 / 1,159). `orderflow.log`: **0
   `client error:` / 0 ERROR / 0 Traceback**, with the extras-gate line for all three venues.
5. **Counts/docs:** README badge **843**; File Inventory **185 files / 30,406 py / 37,136 UI /
   67,542 total** (Config 2/821 · Data 16/6,058 · Analytics 17/3,077 · Atlas 26/7,558 · Desktop
   app 25/9,529 · Desktop UI 84/32,469 · Legacy dashboard 14/2,506+4,667 · `main.py` 857); suite
   **76 files / 15,091 lines**; five drifted tree counts re-derived (main.py 857, settings.py 821,
   bybit_feed.py 339, database.py 472, dashboard tape.js 448); CONTRIBUTING baseline 843 + 22
   selftests; `FLOWSURFACE_FOLD_IN_PLAN.md` marked executed (order-runs model deferred by decision).
6. **The 3.11 parity run measured the same: 843 passed / 2 skipped** in 25.3 s (3.11.16, the
   `%LOCALAPPDATA%\Temp\ofap311` venv from §65).

**Gates at close (2026-09-17):** 843 passed / 2 skipped on **3.11 and 3.12** · AUDIT CLEAN ·
ruff clean · both goldens OK · 22/22 selftests. `HEAD` still `aa43f40`, **40 paths** touched
(the 38 above plus `README.md` and `CONTRIBUTING.md` from the counts pass),
`dist/` untouched (a rebuild is owed before any release artefact is replaced). Still **nothing
committed, nothing pushed**.

---

## §77 — the audit send-back: the judgement, §76 committed, artefacts rebuilt (closed 2026-09-17; nothing pushed, no tag)

**Why.** The owner's Desktop carried `sendback.txt` — a release-readiness audit ("SHIP ONLY AFTER
REQUIRED FIXES") of `aa43f40` + the 40 uncommitted §76 paths. Every finding was re-verified against
the tree before acting; the value judgement + staged plan live in
`docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md`. The owner's instruction: "go with plan .. no final commit
to github".

**The judgement (what the audit got right / wrong).** F-01 (artefacts stale vs the tree) — **true**:
`dist/` predated every §76 source file and contained none of the fold-in; closed by the rebuild
below. F-02/F-04 (the "pyproject.toml missing aiosqlite" P0) — **withdrawn**: the manifest has
declared it since `b2ff4ee`, and the audit's `ModuleNotFoundError` reproduces only with the bare
system `python` (no project deps). Both failure modes were reproduced; `scripts/audit_ui_refs.py`
now prints the interpreter it used and the venv command when its import gate fails. F-05 —
install/entry-point wording was already accurate; two **un-tagged** count claims were genuinely
stale (README L231/L535: "70 files / ~30,400L" → 75 files / 30,113 lines) and were fixed. F-03 —
the six new feed/backfill test files already carry 106 fault-path cases; the residual is receipts
(delivered below). F-06 — the supply-chain posture is already in SECURITY.md + CI + the evidence
page; 2–3 notes lines remain for the release-notes review.

**What landed (5 commits, then the docs wave).**
1. `47ae326` feeds: Binance, Hyperliquid and OKX adapters — the session rule, snapshot chains,
   archive backfill, fault-path tests (§76).
2. `096c055` desktop: the four-venue switch — config, capabilities, engine branches,
   source-switch pins (§76).
3. `25efd48` ui: trade audio, the tape tint, and the ☰ menu's self-recursive api() fixed (§76).
4. `96cd327` scripts: the reference audit names its interpreter when the import gate fails (§77).
5. The docs wave: README counts, CONTRIBUTING, this §77 record + RESUME, the send-back response
   doc, the refreshed release-evidence page, installer/README's latest-build line.

**Artefacts (rebuilt from the committed tree).** exe 13,550,202 B `2731442153…` · zip 27,419,732 B
`111198918d…` (503 entries; +7 = the §76 payload: four WAVs + `audio.js` + `audio.selftest.js` +
`tape.selftest.js`) · Setup 28,412,633 B `b2309cc9…` (0 errors / 4 warnings) · SBOM 430,051 B
`97184c0b…` (CycloneDX 1.5, 42 components). No source file newer than the build; the served
`/desktop` is byte-identical to the packaged `index.html` (`369fbbc6…`).

**Verified.** pytest **843/2** on 3.12 (24.6 s) and 3.11 (25.2 s — the §76 venv at
`%LOCALAPPDATA%\Temp\ofap311` was half-corrupted (pygments stub, typing_extensions missing) and
was recreated with `--clear`); AUDIT CLEAN (74 modules); ruff 0.16.7 clean; both goldens; 22/22
selftests; `pip-audit` 2.10.1 clean over the locked set. **Frozen exe smoke 18/18** (hostile Host
403, cross-origin + cross-site POST 403, loopback POST 200, native WS ping/pong, cross-origin WS
403, `/desktop` hash-match + CSP, unknown symbols `[]`, six venue rows with binance/okx/hyperliquid
wired, 0 client errors). **Sandbox from the tree:** engine start + four venue switches (ticks on
every venue, fresh `last_tick_ms`; tape `live` on bybit); backfill round trip BTCUSDT 2026-09-13 →
512,737 ticks / 6,390,912 B, read back via `/api/control/trades` total 512,737 (page capped at
50,000, truncated); the eight audio params set through `/api/control/params` and read back from the
registry + `config.json`; demo guards `[]`/neutral for `UNKNOWNXYZ`; 0 client errors.

**Nothing pushed; no tag.** The owner's queue stands: the push decision, his physical
multi-monitor pass (§79 if it finds anything — §78 was the release-assurance audit below),
the release-notes review (with the F-06 lines),
then tag `v0.1.0-beta` with the zip + Setup + SBOM.

---

## §78 — the final release assurance audit: the packaged-UI defect found, fixed, and the artefacts rebuilt (closed 2026-09-17; nothing committed, nothing pushed, no tag)

**Why.** The owner ran the `Desktop/final security audit prompt.txt` directive ("Executive final
release assurance audit" — security, reliability, correctness, zero-leak; 14 required sections) for
real against the tree and the package; hard constraint: nothing in the app may break. The full
report is `docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md`.

**The finding that mattered (F-01).** The §77 artefacts shipped **without**
`orderflow_system/dashboard/static`. `scripts/build_exe.py` shipped `desktop/ui` and the Bookmap
add-on but never listed that folder — and the **desktop shell's own `index.html` loads six widget
modules from `/static/`** (`footprint`, `orderbook`, `tape`, `signals`, `performance`,
`microstructure`) and instantiates their classes in `ui.js`. In the packaged app all six answered
**404**, the classes stayed `undefined`, and six views (Footprint, Depth, Tape, Signals, Performance,
Microstructure) silently never initialised — the Tape measured **0 rows** live. The repo tree was
perfect (47/47 assets), which is exactly why every previous gate stayed green: the old script-tag
guard only inspected `/desktop/` tags, and 404s never reach the app's client-error channel.

**What landed (nothing committed).**
1. `scripts/build_exe.py` — `REQUIRED_DATA_RELS` (ui + `dashboard/static`), refuses to build when a
   required root is missing; the add-on stays optional.
2. `orderflow_system/dashboard/app.py` — fail-loud WARNING when `dashboard/static` is absent
   (cannot fire in a correct build).
3. `orderflow_system/test_wiring.py` — +1 regression pin: every local asset `index.html` loads
   exists on disk, and every root it loads from is inside the build's `REQUIRED_DATA_RELS`
   (bite-proven twice — a renamed module and a doctored build list both fail it).
4. `orderflow_system/test_platforms.py` — the add-on pin follows the renamed build constant.
5. F-03 (comment drift): the two uncommitted 01:19 comment edits referenced a config key that does
   not exist (`dashboard.expose_lan`) — reworded to the real `dashboard.host` mechanism.
6. Docs: the audit report, this §78, RESUME, `RELEASE_EVIDENCE` (new hashes),
   `installer/README.md`'s latest-build line.

**Artefacts (rebuilt from the fixed tree).** exe 13,552,324 B `8016d948…` · zip 27,385,320 B
`f8f58706…` (**512 entries** = 503 + the nine static files; `namelist()` + `testzip()` clean) ·
Setup 28,455,930 B `35e3887e…` (0 errors / 4 warnings) · SBOM unchanged 430,051 B `97184c0b…`.
No source file newer than the build.

**Verified.** pytest **844/2** on 3.12 (24.6 s) and 3.11 (24.8 s); AUDIT CLEAN (74 modules); ruff
clean; 22/22 selftests; `pip-audit` clean; `uv lock --check` green; bandit reviewed (1 High =
non-security SHA1 mutex digest; 17 Medium = B314/B310/B608 false-positive classes — dispositions in
the report §F-08). **Soak on the frozen exe** (8 × 28-view cycles + 96 s live bybit, instrumented
CDP): intervals 24 **flat**, observers 13 **flat**, canvases 19 **flat**, DOM stabilised, heap
5.7–22 MB **GC sawtooth no trend**, 0 page errors. **Frame time** (Engine view, live): median
**16.7** / p95 16.7 / p99 16.8 / max 16.8 ms on both tree and exe. **Post-fix package:** **47/47**
assets 200 (was 41/47), six widget classes live, Tape renders rows, guards 403/403/403/200, served
`/desktop` hash-match `369fbbc6…`, 0 client errors. **Installer journey re-run on the rebuilt
Setup:** silent install → **512 files**, installed exe sha256 == dist exe, installed smoke on 8096
(healthz 200, hostile 403, 47/47, widgets live, 0 client errors) → silent uninstall clean (install
dir + shortcut + ARP entry gone); the machine's dev shortcut backed up and restored; `%APPDATA%`
untouched.

**Queued (cosmetic, next source-changing pass).** `ConnectionResetError` log-noise filter (loop
exception handler; logging-only) and `usedforsecurity=False` on the mutex digest — deliberately not
landed here so this pass's artefact verification chain stays exact.

**Nothing committed; nothing pushed; no tag.** The owner's queue: the push decision, his physical
multi-monitor pass (§79 if it finds anything), the release-notes review, then tag `v0.1.0-beta`
with the zip + Setup + SBOM.



---

## §79 — the Help Centre: two interfaces, one corpus, a live system check (built 2026-09-17; **nothing committed, nothing pushed, no tag**)

**Why.** The owner's `Desktop/help.txt` directive: a comprehensive in-app help system in two selectable
modes — **(1) Advanced user**, a menu-based, program-wide, searchable help with in-app clickable
shortcuts, external links, screenshot guides and step-by-steps for the genuinely difficult areas;
**(2) Simple**, the same search power minus what a first-time user should not be steered into, with
configuration errors and system irregularities surfaced as warnings and a way up to the advanced
topics for their own advancement. Both need **autofill suggestions as you type**, a **drop to the
taskbar system**, and a **Help entry in the top nav menu bar with a short About underneath it**
(program version, made by, thanks, relevant links) carrying his logo — with the logo also woven subtly
into the help module itself.

**What landed (nothing committed).**

1. `orderflow_system/desktop/ui/help-data.js` — the corpus, and the deliverable's centre of gravity:
   **68 topics** in 7 groups (Getting started · Panels, one by one · Working with the app ·
   Connections and setup · Data, files and storage · Under the hood · Fixes and support), of which
   **10 are `mode: 'advanced'`** (the under-the-hood material, the danger zone, security exposure,
   the build). Each topic carries tags/aliases/summary/blocks/actions/links/related, and a block may
   be a heading, paragraph, list, table, note, caution, numbered step (with copyable commands),
   screenshot, *or* a live element: the shortcut map (`keys: true`) and the system check
   (`check: true`), rendered from the app itself. A `VIEWS` map names the topic for every view the
   shell has — **the coverage contract**, pinned by a test that reads index.html's own markup.
2. `orderflow_system/desktop/ui/help-search.js` — the search engine, pure (no DOM, no API, no
   storage): tokenise (case/punctuation/camelCase/snake, light stem, `ctrl+k`/`mt5`/`p99` survive),
   weighted index (title 6 > tags 4 > alias 3.5 > summary 2.5 > heading 2 > body 1), AND-across-the-
   query ranking with prefix hits, phrase bonuses and a `kindRank` that lets an explanation outrank a
   program command on a tie, **type-ahead suggestions**, a bounded one-pass **"did you mean"** repair,
   and highlight segments. `help-search.selftest.js` pins it under node — **26 checks, 0 failed**.
3. `orderflow_system/desktop/ui/help.js` — the panel: the Advanced/Simple switch, the browsable tree
   (advanced topics hidden in Simple, with a **gate** that explains and one-clicks up to Advanced
   rather than a silent refusal), the search box with its autofill list, the article renderer, the
   live **system check**, the **About page** (version, build shape, made by, thanks, links, the folders
   it writes to, diagnostics), and the **launcher**: docked in the status bar (the app's taskbar, with
   its own search box and an upward-opening autofill list), floating (`?` button → quick panel), or
   hidden. `help.dock`/`help.mode` are config, mirrored to localStorage only for the first paint.
   **F1** opens the Help Centre through keys.js's own map (bound `inField: true`, so it works
   mid-typing), and the sheet lists it like every other key.
4. `orderflow_system/desktop/ui/help.css` — module-scoped styles (`.help-*`) plus the menu bar's About
   card (`.mb-about*`). Theme tokens only, so all three themes and eight accents carry it.
5. `orderflow_system/desktop/ui/help/*.png` — nine screenshots, byte-identical to their
   `docs/screenshots/` originals (1.7 MB total), used only where a picture beats a paragraph:
   Overview, Chart, the Engine's selection readout and hidden-block count, the Heatmap (live +
   wall-age tint), the held tape, an aux widget window, and the shared cursor spine.
6. `orderflow_system/desktop/help.py` — what the browser cannot invent: **the facts** (name, version
   `0.1.0-beta`, MIT, python/platform/frozen, the five paths), **the credits** (LICENSE's own words:
   Mahmoud — original work; Moddy (ModdySwag) — this distribution; Fabio Testa's methodology; a
   thanks list naming the venues and the open-source stack) and **the system check**: 18 checks over
   the engine, the configured source, the optional integrations, storage, the log tail and how the
   app is exposed. `check_report()` is a pure function of injected state, each finding naming at most
   one topic, one view and one action from a closed `ACTIONS` set.
7. `orderflow_system/desktop/api.py` — `GET /api/control/help` (facts + credits + links + the check +
   the stored prefs; read-only: never starts an engine, never touches the network) and
   `POST /api/control/help` (patched preferences; a value outside the allowed set is ignored rather
   than resetting what is stored; both lists bounded by the store).
8. `orderflow_system/desktop/config_store.py` — the `help` block (`mode`, `dock`, `recents`,
   `dismissed`) with clamps and a save/load round trip.
9. `orderflow_system/desktop/ui/menubar.js` — the **Help menu rewritten**: Help Centre… (F1), Search
   the help… (Ctrl+Shift+H), the two interfaces (checked), **Where help lives** (status bar /
   floating / hidden), the system check item (named with its counts), the setup assistant, the legend,
   the hotkey map, the platforms reference, and — the owner's ask — **an About card at the bottom of
   the dropdown**, rendered from the live facts: the rail's own brand mark, the version, made-by with
   the link, the thanks line, the first three links, and buttons for the About page, the diagnostics
   and the user folder.
10. `orderflow_system/desktop/ui/menu.js` — a Help Centre entry in the ☰ menu's Help group; **F1
    released** (it used to open the hotkey sheet, and a tie goes to the first registration, so F1
    would have kept the old behaviour).
11. `orderflow_system/desktop/ui/index.html` — the two script tags + the stylesheet (order pinned:
    after keys.js/menubar.js/menu.js).
12. `orderflow_system/test_help.py` — **30 tests**: the modules parse, the selftest is green and has
    not shrunk, the wiring (load order, audit coverage, F1 claimed once, no self-recursive `api`
    guard, the boot adopts the stored preferences), the corpus is well-formed and **covers every view
    in the shell**, every check topic/view/action resolves against the corpus and the UI's handler
    table, the config block defaults + clamps + round trip, the check engine branch by branch, and
    the two endpoints.
13. `scripts/audit_ui_refs.py` — the three new modules added to `JS_FILES`.

**Verified.** pytest **874 passed / 2 skipped** (24.8 s) — was 844/2, so +30; **AUDIT CLEAN** (78
modules parse); **23/23 node selftests** (help-search 26 checks). **Live sandbox** (headless, port
8097, scratch `APPDATA`): served `help.css` / `help-data.js` / `help.js` / `help/overview-live.png`
all **hash-identical to disk**; the rail item, the 68-topic tree, the autofill list (topics, keywords
and commands, ranked), 17 results for a three-letter query with the topic ranked first, an article
with two screenshots loading at their real pixel size, the topic's action buttons, the **Simple**
interface hiding exactly 10 topics and the **gate** firing on an advanced one (with "Read it anyway"
escalating to Advanced), the **system check** rendering live rows with working dismiss + "show
dismissed", the **About page** (logo 128 px, version `0.1.0-beta`, paths, links), **F1** (including
with the cursor inside a field) focusing the search box, the **`#help` deep link**, the **status-bar
dock** with its upward autofill popup (geometry asserted: list bottom ≤ field top) and Enter opening
the top hit, the **floating launcher** + quick panel, the **Help dropdown** with the About card, and
the ☰ menu's Help Centre button. **30 views cycled with zero page errors**; the sandbox log carries
**0 error / client-error / traceback lines**; `mode`, `dock`, `recents` and `dismissed` all read back
from the sandbox `config.json` (the API is the writer).

**Teething problems fixed mid-pass (all found by the receipts, not by reading):** an advanced-only
tie-break that let a menu command outrank the topic it was explaining (fixed by `kindRank`); a
block renderer that dropped the step list of a heading+steps block; the boot never adopting the
stored preferences (mode/recents/dismissals would have reset on every launch — now pinned by a
wiring test); an idle server holding the pre-patch `help.py` in memory while the browser held the
pre-patch `menubar.js` — both worth remembering when verifying a help change live.

**Not done (the queue for the next session, in order).**
1. **`dist/` is NOT rebuilt** — the exe/zip/Setup still carry §78. The Help Centre adds ~1.7 MB of
   screenshots plus three modules and needs a payload-changing rebuild, which re-owes the Setup
   journey (silent install → installed hash == dist → smoke → silent uninstall) and a refreshed
   `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`.
2. **README counts** were not re-derived (the tree gained 6 files under `ui/` + 9 assets): the
   `(NNNL)` per-file counts, the File Inventory totals and the JS-file/line claims all drift.
3. The owner's queue from §78 still stands: the push decision, his physical multi-monitor pass
   (**§80** if it finds anything), the release-notes review, then the tag `v0.1.0-beta`.
4. Cosmetic carry-overs unchanged: the client-abort `ConnectionResetError` log filter and bandit's
   SHA1 `usedforsecurity=False`.

**Resume prompt:** `OFAP: continue from docs/RESUME.md — §79 (the Help Centre) is built and verified
in the tree but nothing is committed/pushed/tagged and dist/ is NOT rebuilt. Next: re-derive the
README counts, rebuild dist + re-run the installer journey, then the owner's queue (push,
multi-monitor pass, release notes, tag v0.1.0-beta).`

---

**§79 closed (2026-09-17).** The two owed items are done on disk — the counts pass and the payload rebuild — plus what verifying them turned up:

1. **README/CONTRIBUTING counts re-derived from the tree** (the §79 additions: 6 counted files + 9 assets):
   - Badges: tests **843 → 874**, code **~68k → ~73k**, API **133 → 138** (re-measured from the running app's OpenAPI: 45 atlas + **77** control + 16 legacy — control grew by §76's backfill/trades (+3) and §79's help (+2), which the §74-era 133 never carried).
   - `(NNNL)` tree/diagram claims: two had drifted — `dashboard/app.py` 1371 → **1381** (§78's log warning) and `config/settings.py` 821 → **822** (§78's comment fix), each in both blocks; every other claim re-verified equal.
   - JS claim: **79 vanilla-JS modules / 34,270 lines** (was 75 / 30,113 at §77); the selftest note 22 → **23**.
   - File Inventory: **191 files / 30,955 py / 41,629 UI / 72,584 total** (Config 2/822 · Data 16/6,058 · Analytics 17/3,077 · Atlas 26/7,558 · Desktop app 26/10,067 · Desktop UI 89/36,962 · Legacy 14/2,516+4,667 · main.py 857); suite **77 files / 15,593 lines**; CONTRIBUTING baseline 874 + 23 selftests. The row definitions were calibrated against §76's measured totals before trusting the new sums (a raw recount had swept `__pycache__` in and inflated every row).
2. **The `dist/` chain rebuilt from the current tree** — exe **13,583,295 B `7a9f53ed…`** → zip **29,265,214 B `e6ef3992…`** (**526 entries** = 512 + the 14 Help Centre files) → Setup **30,257,125 B `ab1854aebe…`** (0 errors / 4 warnings) → SBOM unchanged `97184c0b…`. Loose payload **120/120 byte-identical** (ui + dashboard/static + the add-on — static included for the first time, the §78 lesson); no source newer than the build; served `/desktop` == packaged == tree (`eceebf07…`). `installer/README.md`'s Latest-build line updated; the `.ism` regenerated (codes re-minted).
3. **Verified, one battery each.** Gates: pytest **874/2 on 3.12 (25.1 s) and 3.11 (25.4 s)**; AUDIT CLEAN (78 modules, 123 routes, 0 dead ids); ruff 0.16.7 clean; goldens OK; **23/23 selftests**; `pip-audit` clean over the 59-package freeze; `uv lock --check` ok. Frozen exe **smoke 27/27**: guards 403/403/403/200, WS native + cross-origin, unknown `[]` ×2, sources 3 venues, **help assets byte-identical (4 files + 9/9 PNGs)**, `/api/control/help` facts+check (frozen true), **asset parity 50/50**, log 0/0/0. The packaged shell was also driven in a real browser: OFAPHELP boots, the dock renders, 68 topics, mode/dock adopted from the API, 16 search suggestions, 0 page errors. **Installer journey re-run**: silent install → **526 files**, installed exe sha256 == dist exe, shortcut → installed exe; installed smoke on 8098 (healthz 200, candles 200, unknown `[]`, hostile Host refused, 0 client errors); silent uninstall → dir + shortcut + ARP gone (this run registered the ARP entry under **HKLM WOW6432Node** — the setup self-elevated; the §75 script's HKCU-only scan missed it, so the uninstall ran against the product code `{B2B7FE32-…}` directly); `%APPDATA%` untouched; the dev desktop shortcut backed up + restored.
4. **A real defect the close-out's own gate caught:** §79 had never run ruff on its new module — `desktop/help.py` carried an unused `import json` (**F401**). Removed before the rebuild (-1 line, folded into the counts above); ruff clean now.
5. **One finding, queued (not fixed):** the frozen build cannot `import MetaTrader5` — its native core wants numpy, which the §63 diet excludes — so `bootstrap`/`help` read MT5 as "not installed" in the packaged app, and the pyd prints a bare `ModuleNotFoundError: No module named 'numpy'` to stdout on each attempt (invisible in a windowed run; the app log stays clean). Measured **identical on the §65-era frozen zip** → pre-existing since §63, not a §79 regression. Owner decision: bundle numpy (≈ +27 MB), exclude MetaTrader5 from the build and reword the card, or leave as-is.
6. **Cosmetic carry-overs stay queued** (client-abort `ConnectionResetError` filter; bandit SHA1 note) — each would force a second full rebuild + journey cycle on the owner's machine for a logging filter and a kwarg; the owner's call whether to fold them into the next source-changing pass.

**Gates at close:** 874/2 on both interpreters · AUDIT CLEAN · ruff clean · goldens OK · 23/23 selftests · pip-audit clean · frozen exe 27/27 · asset parity 50/50 · installer journey clean. **Nothing committed; nothing pushed; no tag.** `docs/RELEASE_EVIDENCE_v0.1.0-beta.md` refreshed with the new hashes.

**The owner's queue stands:** the push decision, his **physical multi-monitor pass** (**§80** if it finds anything), the release-notes review, then **tag `v0.1.0-beta`** with the zip + Setup + SBOM.

**Resume prompt:** `OFAP: continue from docs/RESUME.md — §79 is closed (counts re-derived, dist/ rebuilt, frozen exe 27/27, installer journey clean, gates 874/2 on both interpreters; nothing committed/pushed/tagged). Next: the owner's queue — push, the physical multi-monitor pass, the release-notes review, then tag v0.1.0-beta with the zip + Setup + SBOM.`

---

---

**§79 close-out addendum — the MT5 finding attended (2026-09-17; nothing committed).**

The close-out block's item 5 (the frozen build cannot load MetaTrader5 — numpy excluded by §63) was attended on the owner's go. Resolved by **excluding the bridge from the build and saying so honestly** — not by re-bundling numpy: that is +27 MB (undoing the §63 diet) for a feed whose terminal path cannot be exercised on this build host, while the exclusion is verifiable today.

1. `scripts/build_exe.py` — `--exclude-module MetaTrader5` (reason in a comment). Verified after the rebuild: `_internal` holds **no MetaTrader5 files** (was a 112 KB `_core.pyd` + hooks).
2. `engine.mt5_status()` / `engine.mt5_probe()` — a `sys.frozen` branch: the card and the wizard's test step say "Not available in the portable build: the MT5 bridge needs numpy, which this build leaves out. Run the app from source to use the MT5 feed — the exchange feeds work here."; no `pip install` command in that branch.
3. `data/mt5_feed.py` — the same honest message in its frozen ImportError log line.
4. UI copy — the guide's MT5 topic and the Help Centre's `connect.mt5` topic now mark the install step **"source installs only"**; the wizard's own "not detected here (reason)" line already flows from `capabilities.mt5.reason` (no edit needed).
5. Pins (3 new, 874 → **877**): `test_atlas_v2.py::test_mt5_status_names_the_portable_build` + `::test_mt5_probe_names_the_portable_build` (frozen + blocked import → the portable message, empty command), `test_platforms.py::test_the_frozen_build_excludes_the_mt5_bridge` (build script must carry the exclusion).

**Re-verified from the current tree.** pytest **877/2 on 3.12 (25.2 s) and 3.11 (25.1 s)**; AUDIT CLEAN; ruff clean; goldens OK; 23/23 selftests; payload **120/120**; **frozen smoke 29/29** — the two new checks: `bootstrap.mt5.reason` names the portable build and the exe's captured **stdout is empty** (no `ModuleNotFoundError`; was 3+ bare numpy lines per capability probe). **Artefacts rebuilt:** exe 13,580,019 B `a1e31865…` · zip 29,220,818 B `145a708b…` (**525 entries**) · Setup 30,213,471 B `8526f59d…` (0 errors / 4 warnings) · SBOM unchanged. **Installer journey re-run:** silent install → **525 files**, installed exe sha256 == dist exe, shortcut → installed exe; installed smoke on 8098 (healthz 200, candles 200/173,477 B, unknown `[]`, hostile Host refused, 0 client errors); silent uninstall clean via the HKLM WOW6432Node product code `{722FDD16-…}` (the setup self-elevates; the HKCU-only scan misses that view — same as the close-out run); `%APPDATA%` untouched; dev shortcut backed up + restored. Counts re-derived again: File Inventory **191 / 30,980 py / 41,631 UI / 72,611 total**; suite **77 files / 15,627 lines**; JS 79 modules / 34,272 lines; tests badge **877** (CONTRIBUTING updated). `installer/README.md`'s Latest-build line updated; `docs/RELEASE_EVIDENCE_v0.1.0-beta.md` refreshed with the new hashes + the MT5-fix record.

**Nothing committed; nothing pushed; no tag.** The owner's queue stands: the push decision, his physical multi-monitor pass (§80 if it finds anything), the release-notes review, then **tag `v0.1.0-beta`** with the zip + Setup + SBOM.


---

### MT5-SHIPS PASS (2026-09-17, same day — **numpy + the bridge now SHIP in the portable build**; supersedes the MT5-fix addendum above)

**Owner's directive (verbatim):** *"i want the packaged app to ship MT5, that's a scoped pass: bundle numpy (+27 MB) and verify against a real MT5 terminal."*

**Source changes.** `scripts/build_exe.py` bundles numpy + MetaTrader5 again (numpy rides with the bridge; the analytics engines stay stdlib-only, pinned). The frozen "portable build" branches in `engine.mt5_status()` / `engine.mt5_probe()` / `data/mt5_feed.py` are deleted — frozen behaves like a source install. Guide + Help Centre MT5 topics reworded ("the portable Windows build already includes the bridge — nothing to install there"; the source-install line kept). Pins: the two portable-build tests + the exclusion test replaced by `test_atlas_v2.py::test_mt5_status_does_not_special_case_the_frozen_build` and `test_platforms.py::test_the_frozen_build_ships_the_mt5_bridge`.

**A real defect, caught by the real terminal and fixed.** `mt5_feed._poll_book` read `entry.volume_real`; live `BookInfo` (package 5.0.6180, measured) is a structseq with `type, price, volume, volume_dbl` — `volume_real` exists on nothing real, so every DOM poll raised (1,558 ERROR+traces in minutes) and the book was dead. Fix: version-tolerant `_book_quantity()` (volume_dbl → volume_real → volume), an honest warning when `market_book_add` fails (it used to log a false "Market book enabled" even for a nonexistent symbol), and a **new `orderflow_system/test_mt5_feed.py` with 5 pins** (the feed had zero unit coverage — why this lived). Counts: pytest **874→877→881** across the day; suite grows to **78 files / 15,664 lines**; badge **881**.

**The real-terminal verification (three levels).** Official MetaTrader 5 terminal installed silently (`mt5setup.exe /auto`) to `C:\Program Files\MetaTrader 5` (build 6199, x64). Root cause found on the way: a fresh official terminal refuses `mt5.initialize()` with `(-10005, 'IPC timeout')` until an account login has completed once (`config/accounts.dat` absent = never logged in; the mql5 forums' standing answer matches) — after a MetaQuotes-Demo demo registration (login **112751745**, virtual 100,000 USD) `initialize()` works from every process, path-optional. Then: **tree engine** `source=mt5` → NAS100USDT 20,953 / XAUUSDT 20,871 / EURUSD 19,933 ticks in 25 s (alternatives: `USTECm→USTEC`, `XAUUSDm→XAUUSD`, `EURUSDm→EURUSD`; BTCUSDT honestly unmatched — no BTC on that demo server). **Feed driver** (20 s): EURUSD 32,686 ticks / **192 DOM snapshots** / 10×10 book; XAUUSD 72,939 / 192 / 7×7. **Frozen exe** (the star receipt): 30,940 / 30,842 / 30,817 ticks in 32 s, **0 `Error polling`**.

**Artefacts (same-day third rebuild).** exe **15,020,151 B `d6287ef2…`** · zip **39,884,552 B `2dc1817d…`** (**565 entries**) · Setup **40,826,742 B `1a1a9f49…`** (0 errors / 4 warnings) · **SBOM regenerated with `--extra mt5`** (**448,822 B `28811a2d…`**, 45 components: metatrader5 5.0.6180 + numpy 2.4.6/2.5.3) — it was a base-only lockfile export and never listed the extra; the **CI audit + SBOM steps carry `--extra mt5`** too (`.github/workflows/ci.yml`). Gate battery on the final tree: pytest **881/2 on 3.12 and 3.11**, AUDIT CLEAN, ruff clean, goldens OK, **23/23 selftests**, **payload 120/120**, **smoke 31/31** (mt5 available in the frozen build + numpy/MT5 asserted in `_internal`), pip-audit clean incl. the extra. Counts re-derived: File Inventory **191 / 30,981 py / 41,631 UI / 72,612 total**; suite **78 / 15,664**; tests badge **881**. **Installer journey:** silent install → **565 files**, installed exe sha == dist exe `d6287ef2…`; installed smoke (healthz 200, candles 200/173,389 B, unknown `[]`, hostile Host 403, 0 client errors); silent uninstall clean via `{820D9A42-F2D4-4CFA-B28D-AB629F5CFB5E}` — found in **both** HKCU and HKLM WOW6432Node (the journey script now scans all three hives, so no manual step this time); dev shortcut backed up + restored; `%APPDATA%` untouched.

**Host note.** The nightly Storage Sense sweep emptied `%LOCALAPPDATA%\Temp` mid-pass (scratch helpers + the parity venv died; §78's raw soak JSON went with it — the evidence page notes it). Scratch now lives in `profiles/deepseek/runtime/ofap_work/`.

**Nothing committed; nothing pushed; no tag.** Owner's queue unchanged: the push decision, his physical multi-monitor pass (§80 if it finds anything), the release-notes review, then **tag `v0.1.0-beta`** with the zip + Setup + SBOM.


---

### PUBLISH + POLISH PASS (2026-09-17, later — **the repo is PUBLIC and the screenshots are live; the installer-polish is IN FLIGHT**)

**Owner's directives (verbatim):** *"ok 1. push full package to github ( if you dont have my creds i can provide them) make sure that in availabe web space within the allowable area you include as many screenshots of the program in action or a slideshow setup displaying same. make sure you give obvious credit to https://github.com/mahmoud20138/OrderFlow-Analysis-Pro. then do a scoped installer polish pass — my suggestion: x64 package + WebView2 chaining + Start Menu shortcut in one seed template, one rebuild, full journey. Signing I'd wire as configuration only (it needs a cert before it does anything)."*

**THE PUSH IS DONE.** Public repo: **https://github.com/ModdySwag/ModFlow-OrderFlow-Analysis-Suite** (branch `master`, 64 commits). The first push was rejected (`did not receive expected object 0206ef7c…`) because the local clone was **shallow** — fixed with `git fetch --unshallow origin` (root commit pulled), then `git push` succeeded. Remote added as **`moddy`** (`origin` remains mahmoud20138's upstream). Two commits this pass: **`25f5fd8`** (screenshots tour) and **`7584ca8`** (the release state: 40 files, +6,777/−139 — the whole §78–§81 arc + the presentation). Private beta lane created: **ModdySwag/ModFlow-beta-builds** (empty — the release cut comes after the polish). **CI note:** `.github/workflows/ci.yml` triggers its **first-ever run** on this repo — check `gh run list` next session (outcome unknown; a red CI on the public face needs attention).

**Screenshots (as ordered).** 30 captures at 1920×1080 of the desktop app on the live Bybit feed (tree app, scratch profile `…/ofap_work/shots_appdata`, 3 symbols), covering all 29 view pages + the Help Centre search + the terminal board. Shipped: `docs/screenshots/*.png` (5.36 MB), `docs/screenshots/ofap-tour.gif` (2.12 MB, 15-slide walkthrough), gallery `docs/SCREENSHOTS.md` with captions, README **See It Running** (GIF + six-grid + link) and **Credit & Lineage** (mahmoud20138/OrderFlow-Analysis-Pro, MIT, forked from `b2ff4ee`, original copyright retained) near the top. Capture tech notes: the aux vision summaries are unreliable for canvas-heavy pages — every shipped image was verified by reading pixels directly; the shell's **classic mode** (`OFAPSHELL.switchTo('classic')`) is what renders single full-page views (the default is the terminal board, where every "view" looks the same).

**INSTALLER POLISH — IN FLIGHT (the next session's job).** Goal: x64 package + WebView2 prereq chaining + Start Menu shortcut in ONE seed template, one rebuild, full journey; signing as configuration only.
- **IDE state at save time:** `isdev.exe` (~pid 17252) is OPEN with the §77 generated project loaded, sitting on the **Shortcuts view** (explorer: Taskbar / Start Menu → **Programs Menu** / Startup / Send To / Desktop → ModFlow OrderFlow Analysis Suite / Tile Configurations). ⚠️ **The Keywords field in General Information currently holds the stray text `x64;1033` — clear it before Save As** (the grid focus fought back mid-edit; Template Summary is still `Intel;1033`).
- **Next IDE steps:** right-click **Programs Menu** (image (318,218) ≈ native (587,434)) → New Shortcut → name `ModFlow OrderFlow Analysis Suite` → target the installed exe; then the **Redistributables** view (left tree, image (66,326) ≈ native (254,576)) → add the WebView2 `.prq`; then **File → Save As → `installer/ModFlowOrderFlowAnalysisSuite.seed.ism`**.
- **Driving recipe (proven this pass):** the IDE runs High-IL → background input is UIPI-blocked; drive it with the elevated trio in `…/ofap_work/`: **elev.ps1** (silently auto-elevates; `-Script <name>` picks the inner script), **drive_is.ps1** (activate → click/type; transcript `drive_is.log`), **rclick_shot.ps1** (right-click + in-process screenshot ~0.8 s later — catches context menus). Coordinates: main window native rect **(167,146,2087,1205)**; captures are 1455×802 → **native = (167 + x×1.3196, 146 + y×1.3196)**. Tree clicks and standard dialogs accept input fine; the property GRID resists F2/typing (focus sticks to the previously focused cell — that is how `x64;1033` landed in Keywords instead of Template Summary).
- **x64 template fallback (offline, deterministic):** patch the `\x05SummaryInformation` stream in the `.ism` — `Intel;1033` → `x64;1033  ` (same 10 bytes, all offsets stay valid); prove it by building, then checking the journey's ARP hive (x64 template ⇒ native HKLM view). The **component 64-bit flag is plain scriptable** (`Attrib64BitComponent` set→save→reopen, proven on a copy).
- **WebView2 prereq (prepped, not yet in the repo):** model `.prq` = `Microsoft .NET Framework 4.8.1 Web.prq`; condition semantics decoded — condition TRUE = already installed → skip; use a key-existence check (`Type=1 Comparison=2 Bits=2`, path `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`); bootstrapper downloaded to `…/ofap_work/MicrosoftEdgeWebview2Setup.exe` (**1,844,944 B, MD5 `7310A0F48396B5A5A64672E50CD71558`**, URL `https://go.microsoft.com/fwlink/p/?LinkId=2124703`, switches `/silent /install`, `returncodetoreboot="3010"`); preplace the exe at `<ISProductFolder>\SetupPrerequisites\Microsoft WebView2\` so the build embeds it.
- **make_installer.ps1 rework (planned):** seed-updater — copy the seed → COM sets the identity fields + `Attrib64BitComponent` → save → `IsCmdBld`; assert feature/component/exe presence; the constructor-side setup (feature/component/files/link/shortcut/string table) is owned by the seed from then on. **Journey extensions:** Start Menu shortcut check (per-user + all-users), ARP hive check, WebView2 skip-if-present.
- **Artefacts unchanged** (exe `d6287ef2…` 15,020,151 B · zip `2dc1817d…` 39,884,552 B / 565 entries · Setup `1a1a9f49…` 40,826,742 B · SBOM `28811a2d…` 45 components). The polish rebuild mints new hashes → then the private-lane release (**tag `v0.1.0-beta`**: zip + Setup + SBOM; testers added as Read collaborators).
- **Standing rule:** the polish commit + this docs update stay **local** until the owner says push. Nothing else is pending publication.

**Processes at save time:** lean shots app on 8097 (disposable — kill it), InstallShield IDE (~pid 17252, **leave open** — the next session resumes from the Shortcuts view), MT5 terminal minimized (leave), elevated-input one-shot child (done).


---

## §82 — Instrument switching, full pass: the Engine panel's look-up + venue-confirmed adds (built 2026-09-17; **nothing committed, nothing pushed, no tag**)

**Owner's directive (verbatim):** *"a user of modflow orderflow suite reports not being able to change to NQ instrument on this panel.. why would this be what improvements code changes could enable this function and the backend functioning of the change?"* — then, on the options offered: *"b full install … tier A + B full."* Plan + log: `docs/INSTRUMENT_SWITCH_PLAN.md`.

**Root cause (measured first, scratch APPDATA, headless 8099).** The Engine view's `#ofxSymbol` was a *display filter*, not a subscription: `POST /api/control/ofx {"symbol":"NQ1!"}` stored any string (`config_store` validates nothing), and the five read endpoints answered for a symbol no wired venue carries — `[]` in demo mode, `404 {"error":"Unknown symbol: NQ1!"}` with the engine running, swallowed by the view's `.catch(() => [])` and replaced by a misleading "no depth history yet — it builds while the feed runs" note. Subscriptions come only from `cfg["instruments"]` (enabled + source-capable, pipelines built once in `OrderflowSystem.__init__`), and the app ships **no** futures instrument: its Nasdaq row is `NAS100USDT` ("proxy for NASDAQ futures", MT5 default `USTECm`). `mt5_feed.list_available_symbols()` existed with **zero callers**.

**What shipped (Tier A + B full).**
- `desktop/instrument_lookup.py` (new, pure): `normalise` / `alias_target` (NQ1!→NAS100USDT, US100, USTEC, GOLD, WTI, …; TradingView `1!` and broker `M` suffixes as *lookups*), `resolve()` → state (`live|ready|disabled|available|unsupported|unknown`) + reason + closed action set + ranked suggestions + `broker_name`, `source_reason()` (the engine's own refusal words), `alias_keys_for()`.
- `engine.venue_stamp_for()` (§82): a symbol the shipped matrix has never heard of now builds a profile from the venue stamp for the ACTIVE source (`mt5_symbol` / `alpaca_symbol` / bybit / binance / hyperliquid / okx) — the "unknown instrument" refusal stays for rows with no evidence, so a typo still dies.
- `engine.mt5_symbol_names()` / `mt5_symbols()` / `mt5_validate_symbols()`: broker discovery off the cached `symbols_get()` list (TTL 120 s), honest `ok:false` + reason when there is no terminal.
- `api.py`: `GET /instruments/resolve`, `GET /mt5/symbols`, source-aware `POST /instruments/add` (bybit | binance | hyperliquid | okx | mt5 | alpaca; venue evidence required; `ticks` / `mt5_symbols` / `alpaca_symbols` / `enable`; skips reported), and `POST /ofx` now returns a **`stream`** block so a save can never be silently un-streamable.
- Panel (`ui/instrument.js` (new) + `instrument.selftest.js` + `ofx-view.js` + `index.html` + `atlas.css`): a state chip beside the symbol box, a `find` button and a look-up panel (state sentence, ranked suggestions, actions **Use / Enable & restart / Add & restart / Start the engine / Map the broker symbol / Open Instruments**), the 404 surfaced with the server's own words, and the view **follows the row** after a successful add. Help Centre Engine topic updated; `scripts/audit_ui_refs.py` JS_FILES registers the module.
- Broker-spelling rule found live: MT5 `symbol_info` is **case-sensitive** (MetaQuotes demo lists `US500M`/`USTEC`, the shipped defaults are Exness-style `US500m`/`USTECm`; `symbol_info("US500m")` → None). The look-up now offers the remap — typed exact hit first, else the row's own alias keys searched against the broker list — so "enable" can never walk into a refusal the panel could have prevented.

**The live chain (real terminal, real data).** `POST /instruments/add {NAS100USDT, source:mt5, mt5_symbols:{NAS100USDT:USTEC}, enable}` → `POST /engine/start` → `NAS100USDT 38,045 ticks / 181 candles`, footprint bars live (`close 29,366`), and **`resolve("NQ1!") → {state: live, symbol: NAS100USDT, via: alias}`** — the reported query, answered. Panel-driven in a real browser: `USTECH100M` (broker-only) → chip "＋ available" → **Add & restart** → `32,896 ticks / 121 candles`, chip "● streaming"; `US500M` → "its broker symbol (US500m) is not one of your broker's names — it lists US500M" → Add & restart → `SP500` enabled + remapped; `TDAX` → add → live, panel reads "TDAX is streaming from mt5." Log: 300 lines, 0 client errors.

**Gates.** pytest **942 passed / 2 skipped** (891 + 51 new pins: `test_instrument_lookup.py` 27, `test_instrument_api.py` 14, `test_instrument_ui.py` 6 incl. the JS↔Python action/state vocabulary pins, `test_instrument_matrix.py` +3 venue-stamp + 1 from the earlier pass); AUDIT CLEAN (**80 modules**, 125 routes discovered); ruff clean; goldens OK (analytics `0.000e+00`; config 31 factories / 18 majors / 49 instruments); **24/24 selftests**; OpenAPI from the running app: **140 operations** (control 79, atlas 45, legacy 16).

**Counts re-derived in the same pass.** README/CONTRIBUTING badges **942 / ~74k / API 140 routes**; File Inventory **193 / 31,763 py / 42,180 UI / 73,943 total**; suite **82 files / 16,351 lines**; JS **81 modules / 34,779 lines** (24 selftests); diagram line 140 routes; `/api/control/*` 79 routes.

**Owed (not in this pass).** `dist/` + zip + SBOM + the installer are NOT rebuilt (the installer-polish is still in flight with the IS IDE open — the payload now differs from the packaged build, so the next packaging pass must rebuild and re-run the payload-parity + journey checks). Nothing committed; nothing pushed; no tag. The owner's queue stands (installer polish → release cut).

**Addendum — the user's own words.** The original report was *"i was trying to view the nq chart but it says crpto only"*: that app is on the **exchange feed** (Bybit — crypto perpetuals only), so the sentence was the engine's own gate, not a defect. The addendum closes exactly that gap: the look-up now checks the **source's gate before the enabled flag**, so a refused symbol answers with the engine's sentence **and the way out** (`hint`: switch the data source / map the broker symbol) instead of "enable it and restart" (which would only have the engine skip the row with the same words). Measured on the bybit source with the running app: `resolve("NQ1!")` → `unsupported · NAS100USDT (alias)`, reason *"Bybit perps list crypto only — switch to MT5 (Windows) for this instrument"*, hint *"switch the data source to MetaTrader 5 … and map the broker symbol"*; panel chip **⚠ not on this source**, one action (**Open Instruments**), stage note now the refusal itself. Pins: `test_the_reported_case_nq_on_the_exchange_feed_answers_crypto_only_and_the_way_out`, `test_an_enabled_row_on_a_source_that_cannot_carry_it_is_not_called_ready`, JS `panelText` hint check. Gates after the addendum: pytest **944 passed / 2 skipped**, selftest 14 checks, ruff clean. **A keyless crypto venue cannot carry NQ — MT5 (or a paid futures venue, tier C) is the requirement; the pass makes the path explicit, not the data appear.**

---

## §83 — "Explain it in the UI" + the settings sweep (built 2026-09-17; **nothing committed, nothing pushed, no tag**)

**Owner's directive (verbatim, one message):** *"could you build in a pop up window / hover over message or similar explaining this to the user if the right "click" conditions are made and pointers to how to fix/enable this funtionality. also ammend the help guide to reflect changes. also add any other menu options wherever they are needed to make this scenario easy to navigate and assist the user. one more thing the user reports "And how do i make sure my Alpaca api keys save i had to re enter when i restared it" so i think we need a sweep to ensure all relevant user cahnges inputs and any other relevany conditions where user input needs to be saved is saved and there is no "reinputting" of details config changesa etc necessary"*. Record: `docs/EXPLAIN_AND_PERSIST.md`.

**Root cause of the reported bug (read every write path, then measured).** The Alpaca view's *Validate & save* calls `POST /api/control/alpaca/test {save:true}`; that handler built `cfg = _alpaca_cfg()` — the **alpaca block** — and called `config_store.save_config(cfg)`. `save_config` merges its argument over `default_config()`, so the write produced **defaults everywhere + `key_id`/`secret`/`paper` at the TOP level**, leaving `alpaca` empty: the key pair was gone on the next launch (the report: "had to re enter") **and** every other setting silently reverted to factory. The Alpaca pair was not special — the class was "a block saved as a whole config".

**What shipped.**

- **Persistence fixes:** `alpaca_test(save=True)` loads→updates→saves the whole config; `engine/start` / `engine/restart` bodies **merge** (`merge_config`) instead of replacing; Settings' collect/save reads the **on-disk** config before patching (a stale page copy rolled back newer writes); Alpaca's feed selector posts a one-field patch; the Settings **Telegram master switch** — a control nothing read, while the engine honours `telegram.enabled` — is now restored + collected; `ui.chart {range, markers, vp}` and `ui.logs {auto, level}` are persisted with sanitiser clamps and saved on change.
- **Guard for the class:** `test_settings_persistence.py` — a static scan fails if any `save_config(X)` in the desktop package is handed a block rather than the whole config (nearest-assignment check inside the enclosing function), plus behavioural pins: a key save keeps everything else; an empty secret never erases a stored one; a partial engine-start body patches; settings round-trip; the view state is saved on change and restored.
- **The explainer:** new `ui/hint.js` (+ `hint.selftest.js`, 7 checks; registered in `scripts/audit_ui_refs.py`). Hover shows a card, **right-click pins it**, buttons run real actions from a closed set (`lookup · engine · instruments · wizard · menu`); `data-hint-*` attributes are re-read at show-time so the Engine chip's card is never stale; `skippedNotice()`/`paintNotice()` turn a skip report into a banner that carries the button. Wired: the Engine symbol chip (live verdict card), the `find` box, the three top-bar pills, the Instruments header button **Look up an instrument…**, **right-click on any instrument row** (measured on a 51-row table: *"NAS100USDT — unsupported | Bybit perps list crypto only — switch to MT5 (Windows) for this instrument · switch the data source to MetaTrader 5 … | Open the instrument look-up | Open Instruments"*), the engine skip banner, Data ▸ **Instrument look-up…**, and a palette command whose keywords include `crypto only`.
- **Help guide:** `start.sources` (*"an exchange feed is crypto-only — by nature"*), `connect.mt5_map` (case-sensitive broker names + Add & restart), `view.instruments` (three-step look-up block + action), `view.alpaca` (*"Your keys stay saved — nothing to re-enter"* + Test saved keys + Remove stored keys), `fix.no_data` (the "market needs another source" row), `fix.skipped_symbols` (the banner + look-up), `view.settings` (the Telegram switch is stored).

**Live receipts (headless 8099, scratch APPDATA, real restart mid-check).** Key save → restart → `configured: true`, `key_masked "PK83…E2"`, secret present, marker + `data_source bybit` + 51 instruments intact, **no stray top-level keys**; a one-field patch changed only that field; key-id-only re-save kept the secret. Browser: the chip's hover card read *"⚠ not on this source | NQ1! → NAS100USDT — Bybit perps list crypto only — switch to MT5 (Windows) for this instrument · switch the data source to MetaTrader 5 … | Open the instrument look-up | Open Instruments"*; the skip banner read *"NAS100USDT: Bybit perps list crypto only — switch to MT5 (Windows) for this instrument (+3 more) | Open the instrument look-up"* and its button opened the Engine view's look-up panel with that verdict; Data ▸ Instrument look-up… also navigated + opened it.

**Gates.** pytest **962 passed / 2 skipped** (+18 pins: `test_settings_persistence.py` 10, `test_hint_ui.py` 8); AUDIT CLEAN (**82 JS modules** parse); ruff clean (via `uvx ruff check` — the venv has no ruff module); goldens OK (config 31/18/49; analytics `0.000e+00`, 40 cases); **25 node selftests**; OpenAPI **140 operations** unchanged.

**Owed.** `dist/` · zip · SBOM · installer NOT rebuilt (payload changed again — rebuild + payload parity + the installer journey in the next packaging pass); README/CONTRIBUTING counts re-derivation; installer polish still parked mid-IDE. Nothing committed; HEAD `110c568`.


---

## §84 — NinjaTrader 8 integration: the shipped read-only bridge + a full engine data source + the platform card (built 2026-09-18; **nothing committed, nothing pushed, no tag**)

**Owner's directive (verbatim, one message):** *"reagarding the modflow build. i want to integrate ninja trader support for frr and paid accounts. i would ultimatel like NQ1 and all further data feeds and ingest from ninja trader platform inetgration. i would like a scnario wher when plugged into the ninja trader platform data ingestion module scenarios like adding NQ1 to the Instruments panel is possible as well as any other otions the paid/free tire from ninja trader offers. i would like the reflected incresed data souces and streams to be folded into the program in relevant section and the help menu and setup for the ninja trader plugin/adiition in the wizard and setup sequence. all relevant documentation switches and panels needed for the integration to function will be beneficial."* — plus: *"i have ninja trader running on my computer and im logged into my ninja trader demo account so use those points of access to derive whatever needed code/information you need to build."*

**Full record:** `docs/NINJATRADER_INTEGRATION.md` (architecture, the wire format, tiers, install, troubleshooting, security block).

**What shipped.**

- **The bridge add-on (the NinjaTrader-side half).** `orderflow_system/data/ninjatrader_bridge/` — `src/ModFlowBridge.cs` (875L) + `src/ModFlowProbe.cs` (213L, diagnostics companion) + `build.ps1` + README + the **built `ModFlowBridge.dll` (60,928 B)**. Compiled with Roslyn (a user-scope .NET SDK at `%LOCALAPPDATA%\dotnet-sdk` — no Visual Studio, no admin) against NinjaTrader 8.1.8.2's own assemblies, `net48`, x64. A `TcpListener` on **127.0.0.1:8790**, one reader at a time, NUL-terminated JSON frames (the Bookmap bridge's framing convention). Reads quotes, trades, **Level-2 depth**, the instrument database and historical bars; the protocol has **no order verbs** and the DLL never touches account/licence/config files. Deployed to `Documents\NinjaTrader 8\bin\Custom\AddOns\ModFlowBridge.dll`.
- **The platform facts, discovered on the live install.** NT **8.1.8.2**; the platform presents a **login window on every start and exits if it is closed** (his in-memory session died with the first restart — credential handling stayed with the owner throughout); third-party DLLs load from `bin\Custom\AddOns` **only when Tools ▸ Options ▸ General ▸ Miscellaneous ▸ Allow custom assembly loading is enabled** (silently ignored otherwise — that option is a real gate on current builds); the Log tab + `%LOCALAPPDATA%\ModFlow\ntbridge.log` + `ntbridge-probe.log` are the diagnostics; the connection in use was the **Simulated Data Feed** (complete quotes/trades/depth, no payment — ideal for verification). Docs basis: the officially documented `MarketData`/`MarketDepth` AddOn classes (snapshot-on-subscribe, `instrument.Dispatcher` threading).
- **The feed (the suite-side half).** `orderflow_system/data/ninjatrader_feed.py` (629L): `NinjaTraderFeed` on the repo's reconnect ladder (silence budget 30 s vs 5 s heartbeats; **frames reassembled across reads** — a regression pin covers the straddling case); app-symbol ↔ terminal-name mapping (the bridge resolves `NQ`/`NQ1` → the front-month full name, exactly as typing it into the terminal would); aggressor from the bridge's last-vs-book comparison; a locally maintained L2 ladder emitted as throttled sorted snapshots; junk-guarded numbers with counters; `ninjatrader_probe()` (the card's Test connection) and one-shot request/reply helpers.
- **Wiring (the venue touch-list, none skipped).** `settings.py` (`DataSource.NINJATRADER`, `NinjaTraderConfig`); `main.py` feed branch + stop path; `engine.py` (`ninjatrader_status/capable/symbol_names/validate`, `venue_stamp_for` gains `ninjatrader`, the `select_instruments` gate, `capabilities()`); `config_store.py` (source allow-list, `platforms.ninjatrader` block with plan/port clamps, `ninjatrader_symbol` kept verbatim — terminal names are case- and space-exact, futures roots in `ASSET_CLASS`); `desktop/platforms.py` (links/plans/caveats with prices-as-of, `ninjatrader_workflow()`, install detection reading the platform's version from its own log line, `ninjatrader_bridge_state()` comparing the shipped DLL to the AddOns copy by sha256, `reveal_bridge_dll()`); **api.py +4 routes** (`/platforms` rows, plan accept, bridge save, live test, DLL state, DLL folder); `instrument_lookup.py` NinjaTrader branch (rows without a stamp answer with the terminal route; a look-up against the terminal's list turns `NQ1`/`NQ` into **available → NQ 12-26** with the add action); UI (wizard radio + note, walkthrough topic with a **live bridge test panel**, the Platforms card — plans, workflow, DLL state, Test connection — and `tcp://` probe support in the free-sources row).
- **Help + docs.** New Help Centre topics `connect.ninjatrader` (both modes) and `under.nt_bridge` (advanced — filed under `under`, which the corpus test enforces for advanced topics); the Platforms help topic now covers all three integrations. `docs/NINJATRADER_INTEGRATION.md` is the operator + developer record.
- **The NQ1 scenario, exactly.** Engine look-up `NQ1` (source ninjatrader) → the suite asks the bridge for the terminal's list → answer **available · symbol NQ · terminal name NQ 12-26** → **Add** creates the row **stamped** (`ninjatrader_symbol: "NQ 12-26"`, tick size from the terminal's database, class from the futures-roots table) → restart → the feed subscribes `NQ 12-26` and every panel (tape, footprint, delta, ladder) streams it under `NQ`.

**Errors/fixes on the way.** The first API-surface probe — loading NinjaTrader's (obfuscated, Agile-protected) assemblies into PowerShell — crashed with a *guard-page* dialog; abandoned in favour of an in-process diagnostics add-on (**never load NT assemblies outside NT**). The first sample DLL was deployed to `bin\Custom` instead of `bin\Custom\AddOns` before the platform-folder rule was found; a taskkill-under-MSYS quoting miss made the first NT restart race (both instances exited; relaunched cleanly). The frame reader originally parsed each TCP read as whole frames — fixed with a per-connection buffer + regression test. A test-authoring slip (expected `plan_kind "paid"` where the Lifetime plan's kind is `"integrated"`; a fixture row making an "add" an "update") was caught by the pins themselves.

**Gates.** pytest **996 passed / 2 skipped** (+34 pins: `test_ninjatrader_feed.py` **18** incl. the frame-straddle regression, `test_ninjatrader_api.py` **9** incl. a live probe against the mock on a real socket, `test_platforms.py` +**7**); AUDIT CLEAN (**82 JS modules**); ruff clean (via `uvx`); goldens OK (config 31 factories / 18 crypto majors / 49 instruments; analytics `0.000e+00`); **25/25 node selftests**; OpenAPI **144 operations** (control 83 / atlas 45 / legacy 16 — +4, exactly the new routes).

**Counts re-derived (this pass, method unchanged).** README/CONTRIBUTING badges **996 / ~76k / API 144 routes**; tagline now names seven venue integrations; diagram line 144; `/api/control/*` 83 routes; File Inventory **198 / 33,197 py / 43,147 UI / 76,344 total**; suite **86 files / 17,467 lines**; settings annotation 842L/15 dataclasses; main.py 883L; bridge C# excluded from the columns and noted; `ui/*.js` **71 files / 35,152 lines** + 25 selftests.

**Owed (not in this pass).** **The live platform receipt** — one owner login: 1. open NinjaTrader and sign in; 2. **Tools ▸ Options ▸ General ▸ Miscellaneous ▸ Allow custom assembly loading** (the suite's card and help say this too); 3. restart it once (the DLL is already in `Custom\AddOns`); 4. Platforms ▸ NinjaTrader ▸ **Test connection** (expect the NT build, the live connection, quotes/trades/depth counts); 5. Engine look-up `NQ1` → **Add & restart** — then the NQ row streams from the terminal. Also owed: `dist/` · zip · SBOM · installer **NOT rebuilt** (payload changed; the installer-polish pass is still parked mid-IDE, untouched this session). Nothing committed; HEAD `110c568`.

**Processes at save time.** NinjaTrader 8 is **closed** (its login window was closed during recon — it exits by design); the DLL sits in `Custom\AddOns` ready for the next start. InstallShield IDE: untouched this session (still parked wherever the polish pass left it). No sandbox running.

---

## §84b — the live receipt; the install lane corrected (2026-09-18, same day as §84; **nothing committed, nothing pushed, no tag**)

**The live pass ran against the owner's own terminal (NT 8.1.8.2, NTB demo) and it changed three build facts — §84's text above is superseded where it disagrees.**

- **The install lane is the platform's own NinjaScript editor, not a loose DLL.** 8.1.8.2's Settings
  dialog exposes only General ▸ Preferences/Sounds — **no "Allow custom assembly loading" exists on
  this build**, and a DLL sitting in `bin\Custom\AddOns` was ignored silently across a restart (no
  prompt, no log line). What works, verified live: copy `ModFlowBridge.cs` + `ModFlowJson.cs` +
  `ModFlowProbe.cs` into `Custom\AddOns`, press **F5** in `New ▸ NinjaScript Editor`; the platform
  compiles them in-place and asks its own **trust prompt** ("detected new add-on(s) … ensure these
  are from trusted sources") — answer Yes and the bridge is **live without a restart**. Every
  user-facing copy now teaches this lane: bridge README, `docs/NINJATRADER_INTEGRATION.md`, the
  Platforms card + walkthrough (`platforms.py`/`platforms.js`), the wizard note (`guide.js`), both
  Help topics (`help-data.js`), the probe refusal text (`ninjatrader_feed.py`) and the engine's
  no-bridge reason (`engine.py`). The pins moved with them.
- **No Newtonsoft dependency.** NinjaScript's compiler does not reference `Newtonsoft.Json`, so the
  bridge now carries its own tiny JSON layer — new `src/ModFlowJson.cs` (writer over anonymous
  objects/dicts/lists + a tolerant flat-object reader). The prebuilt `ModFlowBridge.dll` was rebuilt
  from the dependency-free source (71,168 B, sha256 `17ddf96f…`).
- **The front-month resolver reads NinjaTrader's own roll calendar** (`MasterInstrument.RolloverCollection`;
  the entry whose `Date` is the latest one not in the future). Live answers: `NQ1`/`NQ` → **NQ DEC26**,
  `MNQ` → **MNQ DEC26**, `ES` → **ES DEC26** (and *not* the Eversource Energy stock of the same
  ticker — futures roots win), `CL` → **CL NOV26**, matching the platform's own Market Analyzer to the
  contract. A fixed expiry-minus-8-days heuristic (shipped earlier that evening) got crude wrong; the
  calendar is authoritative. The instrument-database listing now also confirms the roots
  (NQ: tick 0.25, $20/point).
- **The live receipt itself.** Bridge bound `127.0.0.1:8790` from inside the platform; the suite's own
  reader (`data/ninjatrader_feed.py` against the real socket): **NQ DEC26 — 23 trades / 20 quotes /
  1,765 depth updates in 2.5 s** (bid 29708.25 / ask 29709); **ES DEC26 — 69 trades / 307 depth
  updates in 1.5 s** (7699.50 / 7699.75); hello named the platform build, the "Simulation" connection
  and all four accounts (Backtest/Playback/Sim101/DEMO…); **Level-2 depth flows** on the owner's
  connection. The bridge logs to `%LOCALAPPDATA%\ModFlow\ntbridge.log` and the probe to
  `ntbridge-probe.log` (both verified live). A sandbox boot of the full desktop app additionally
  proved the app's own resolve/add/engine routes answer correctly with the platform down (honest
  refusals naming the bridge) — the click-through with the platform up remains the one cosmetic gap.
- **One mid-pass edit incident, recorded for honesty.** A marker-based slice while rewriting
  `platforms.py`'s card copy mismatched (an end marker hit a later card) and briefly mangled the
  card list. It was reconstructed the same hour from `git show HEAD:` plus the test suite's own
  expectations, then re-verified: `catalogue()` returns sierra/bookmap/ninjatrader with full key
  sets, `test_platforms.py` 35/35, `bridge_state` now recognises **both** install lanes (source
  present → ok, with the compile-once note). No user-visible residue; nothing was committed at any
  point.
- **Gates after the live pass:** pytest **996 passed / 2 skipped**; AUDIT CLEAN (**82 JS modules**);
  ruff clean (via `uvx`); **25/25 node selftests**; OpenAPI **144 operations** unchanged.

**Owed (unchanged from §84 plus this pass's payload):** the literal panel click-through with the
platform open (routes already proven end-to-end at the wire level); `dist/` · zip · SBOM · installer
**NOT rebuilt** (payload changed twice — §84 and this pass); installer-polish still parked mid-IDE.
Nothing committed; HEAD `110c568`.

---

## §85 — the toggle that only painted, the Engine picker, and reachable hover cards (2026-09-18, live-verified in a sandbox; **nothing committed**)

**The report (owner, live):** a row toggled ON in the Instruments panel, then selected in the Engine view's symbol box, answered *"not enabled"* — while the toggle sat green. Plus: add a quick-pick dropdown to the Engine's symbol section, and a scope question — a dropdown "disappears" when travelling toward it; program-wide or local?

**Root causes, both measured.**
- **The Instruments coverage table had no save path at all.** `collectInstruments()` was reachable only from the Settings view's Save button, so a toggle changed the checkbox and nothing else: the owner's config.json read `enabled=false` for every row he had flipped. The Engine chip was truthful the whole time — *the toggle was the liar*. (His "Enable & restart" route worked because it goes through `POST /instruments/add` + `/engine/restart`.)
- **The disappearing dropdown is `hint.js`, and it is program-wide.** Hover cards hid on the trigger's own `mouseleave` while the card floats below with an 8 px gap — the pointer leaving the trigger mid-travel killed the card before it could be clicked. It affects every `data-hint-*` surface (engine chip, find box, top-bar pills, instrument rows, notice buttons). The top menus are click-based and the look-up panel persists, so those were never the flake.

**Fixes (all front-end files; served fresh on reload — no engine or app restart needed).**
- **`ui.js` — a toggle IS the change.** Delegated `change` on `#instTable`: 450 ms debounce → one write built from the config **on disk** (never the page's possibly-stale copy — §83 discipline), merging the DOM's `enabled`/`tick_size` per row → `POST /config` → adopt `r.config` → cached caps refresh → re-render → **apply**: a running engine restarts (exactly the Engine view's "Enable & restart" path), with banner progress (`"… restarting the engine to apply…"` → `"… the engine covers it now"`); a stopped one says "saved. Start the engine to stream it." Applies are serialized (a second toggle rides the next slot so the newest state lands last — measured: two quick flips interleaved before this). The bulk buttons (*Enable all supported*, *Clear*) queue the same apply.
- **The Engine picker.** New `<select id="ofxSymPick">` in the widget's symbol row beside the chip: pure builder `pickerRows()` in `instrument.js` (groups: **streaming now → enabled → configured — off**, dedup, class-labelled), `refreshPicker()` re-reads config + engine status on focus, `pickSymbol()` switches the view, resolves, and runs the same enable/start/add action the look-up's buttons use — a pick is *"refresh and enable"*, and *Enable & restart* stays exactly where it was.
- **`hint.js` — reachable cards.** `LEAVE_GRACE` (260 ms) on leaving either side, the card's own `mouseenter` cancels the pending hide, `mouseleave` re-arms it; right-click pinning unchanged.

**Live receipt (sandbox on 8099, a copy of the owner's own config; driven over CDP).**
- Toggle DOGEUSDT on → persisted (`enabled=true` in config.json), banner confirmed.
- Toggle DOGEUSDT **off while the engine ran** → banner *"DOGEUSDT disabled — restarting the engine to apply…"* → *"… the engine covers it now"* → engine restarted with exactly the enabled set (`BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT, TRXUSDT` — DOGE gone).
- Picker: 49 options grouped correctly; picking DOGEUSDT (enabled, engine stopped) started the engine and it **streamed live** (Bybit prints, depth ladder filled).
- Hint card, real CDP mouse moves: hover chip → card visible; six-step travel down into the card → **still visible** (previously vanished); move away → hidden.
- Gates: pytest **997 passed / 2 skipped** (+1 pin; one full-run flake in `test_hyperliquid_feed.py` — its real REST call — passed isolated); AUDIT CLEAN (82 modules); ruff clean; **25/25 selftests** (`instrument.selftest.js` now 15 checks incl. the picker grouping; `hint.selftest.js` 7). README/CONTRIBUTING test badge re-derived to 997.

**Also observed on the owner's machine (CORRECTED in §86b — this was a misread):** what looked like two instances (`pythonw -m orderflow_system.desktop` ×2) is **one launch**: uv-style venv shims — `.venv\Scripts\pythonw.exe` is a ~7 MB redirector that spawns the real interpreter (~150 MB, the window) as its child and waits for it. No second server ever ran; the `database is locked` storms came from restart cycles over the 776 MB store (see §86b).

**Owed:** `dist/` · zip · SBOM · installer rebuild (payload grew again — the §84 bridge + this pass); the NT bridge click-through with the platform open. Nothing committed; HEAD `110c568`.

---

## §86 — the Systems board, and the "does the app reflect what I added" pass (2026-09-18, live-verified in the sandbox; **nothing committed**)

**The owner's ask:** when a subscription/module/plugin or ingest is added, do the toggles/switches/menus activate as they should — and add a small graphical display of every live ingest interaction plus the optional capabilities, so "are the systems 100%?" is answerable at a glance.

**The audit half (what already activated, verified against the live capabilities).** Sources: the Instruments table greys unsupported rows and marks the exchange listing per row; the Engine panel's state chip, suggestions and actions are capability-driven (§82); the Platforms cards read real installs and bridge states (and the NT card teaches the current lane); the wizard notes read `/capabilities` at render (MT5/NT availability with reasons); the Alpaca view reflects the linked state; the top-bar chips (source · data · WS · Running) read the live status. Gaps found and fixed: the Instruments toggle not persisting (that was §85), and **one lie caught by this pass's own screenshot** — with the engine running on Bybit, the MT5 tile said "feeding the engine now"; fixed and pinned (`test_mt5_never_claims_the_feed_when_the_exchange_is_the_source`).

**The board (the new display).** `engine.systems_report()` behind **`GET /api/control/systems`** (+1 route → **145**), painted by the Overview's **Systems** card: pure model `ui/systems.js` (+ `systems.selftest.js`, 5 checks; registered in `scripts/audit_ui_refs.py`), wiring in `ui.js` (`renderSystems`, boot, the Overview view hook, the card's own **Re-check**). Rows, fixed order: **Engine · Feed — \<source\> · MetaTrader 5 · NinjaTrader 8 (bridge) · Alpaca Markets · History database · UI stream (WebSocket) · Alerts — Telegram**; kept apart and never counted: **Bookmap bridge · Sierra Chart (DTC)** ("optional capabilities"). States are a closed set the UI only paints — **live | ready | off | error** — the score counts the expected rows only ("4 of 8 systems live — 50% · 3 need attention"), and every tile carries the live sentence for its state and routes to the view that owns the fix. First paint rides a status tick: fired inside the boot burst its fetch queued **~25 s** behind the page's own boot calls (measured: the browser's six-socket pool; no resource entry until it started) — the board must not fight the app's start-up for the wire.

**The database row is the honest one.** A write-lock probe (`BEGIN IMMEDIATE`, two short attempts), because reads pass under WAL even while another writer holds the store — exactly how an engine can answer `database is locked` while its own panels keep reading (and how the owner's engine did, mid restart-flush; no duplicate instance was involved — §86b). The row says it and names the way out.

**Live receipt (sandbox 8099, the owner's config copy, driven over CDP).** Pre-start: *1 of 8 live — 13% · 5 need attention* (History database ● live, "writable · 73.6 MB"). After Start engine: *4 of 8 — 50%* — Engine ● live ("streaming 5 instruments · 1,447 ticks · up 14s"), Feed — Bybit ● live ("feeding the engine now · 5 instruments"), UI stream ● live ("1 client(s) attached"); NinjaTrader ● off with the live bridge reason; MT5 ◎ ready; Bookmap/Sierra shown as optional ("installed · add the bridge in Platforms"). Tile click → the Alpaca view went active.

**Gates.** pytest **1007 passed / 2 skipped** (+10 pins in `test_systems.py`), AUDIT CLEAN, ruff clean, **26/26 selftests**; README/CONTRIBUTING test badge re-derived to 1007; API badge 145 routes.

**Owed (unchanged).** `dist/` · zip · SBOM · installer rebuild (payload grew again); the NT bridge click-through with the platform open; the two-instance DB-lock note for the owner's machine from §85 still applies until he closes the duplicate.

---

## §86b — the duplicate instance that never was, and the lock forensics (2026-09-18; **nothing committed**)

**The question:** why do two app processes appear — asked after §85/§86 flagged "two instances on the same database".

**The answer, proven live:** there is no duplicate. A launch of this project's venv interpreter produces **two processes by design**: `.venv\Scripts\pythonw.exe` is a small redirector (measured 7 MB, no window, no ports) that spawns the real interpreter (uv's cpython, ~150 MB, the window) as its **child** and waits for its lifetime. Re-produced on demand: both processes share the same creation second, child's `ParentProcessId` = the shim's, and the window title lives on the child. The single-instance guard (`desktop/single_instance.py` — a named mutex per config directory, windowed launches only, fails open) never had to fire; no second server ever bound a port, and no second engine ever appears in the logs. **§85's "close one instance" advice was a misread and is retracted here.**

**The `database is locked` storms (01:44 and 01:55 tonight, `bybit_feed: Error handling message: database is locked` ×hundreds):** the store is **776 MB with an 18 MB WAL** after long sessions. When a session ends (window closed — or End-tasked while a flush was running) and the app is started again promptly, the fresh engine's per-tick writes collide with the previous session's WAL recovery/checkpoint; SQLite serialises, the writes time out, and the engine lands in `state=error` (visible in §86's History-database tile, which is exactly why that row exists). Nothing was corrupted: a write-lock probe on the live store right now reports **writable · 776.2 MB**, and a fresh single instance started with the engine up and no error (`symbols: BTCUSDT, ETHUSDT, SOLUSDT, TRXUSDT`, ticks flowing).
**Practices from this:** close the app and give it a moment (the WAL flush) before relaunching; prefer the window's own close over End-task; if the engine lands in error, one `Start engine` after the close finishes clears it — the store recovers itself.

**Hardening shipped with this pass:** the already-running notice now bounds itself (`NOTICE_MS = 10 s`, `MessageBoxTimeoutW`, plain `MessageBoxW` as the fallback) — an unfocused second launch can no longer strand an invisible modal process, which is what an earlier 7 MB windowless process would have been if the guard HAD fired. Pin added (`test_the_already_running_notice_is_bounded`). Gates: pytest **1008 passed / 2 skipped**; badge re-derived.

**State at save:** one clean instance runs (window up, new code live — `/api/control/systems` answering), engine running without error, board at **4 of 8 live — 50%** (engine · feed · history database · UI stream green; MT5 ready; NinjaTrader off — platform closed; Alpaca and Telegram not configured).

---

## §87 — Market Watch, the Run switcher, and the wizard/help reflection (2026-09-18; **nothing committed**)

**§87a — the Market Watch board.** `GET /api/control/marketwatch` + a first-class view (rail: between Time & Sales and Trackers) showing the source's own board. The **MT5 branch mirrors the terminal's own Market Watch, read-only** — `SymbolInfo.visible` marks the terminal's list (35 symbols on the owner's MetaQuotes demo, sorted by the terminal's own paths: Forex → indices → metals → stocks), quotes and the daily change are computed per page off the running terminal, and the panel **never calls `symbol_select`**: browsing cannot change the terminal's watch list (a booby-trapped fake in the tests fails if it ever does). The **Bybit branch** is one cached REST snapshot of the whole linear board (877 instruments). The **NinjaTrader branch** lists the terminal's master instruments and says its bridge only carries subscribed ones. Table model `ui/marketwatch.js` (13-check selftest, MT5-style formatting by magnitude: 1.14776 / 155.944 / 29440.70 / 0.57326), Python pins `test_market_watch.py` (11).

**§87b — the Run switcher.** The top bar gains a **Run** menu: *Desktop app — this window* (checked — this is the mode you are in), *Headless server on port 8099*, *CLI pipeline — feeds → detectors → Telegram*; below the divider the Optional reminders (MT5 feed support, NinjaTrader bridge, dev tooling) and a Market watch short-cut. `POST /api/control/launch` validates a closed set, refuses a frozen build asked for the CLI pipeline ("source tree only"), refuses when 8099 already answers, and spawns the mode in its own console (`CREATE_NEW_CONSOLE`) with the honest sentence that both modes share the profile's history store — the §86b lock lesson, wired into the feature instead of the docs.

**§87c — wizard and help reflection.** The suite's own coverage contract (`test_help.py::test_every_view_in_the_shell_has_a_topic`) caught the new view shipping without a help topic — one red test, exactly what it exists for. Now: **`view.marketwatch`** topic + `VIEWS` map entry; **`view.instruments`** corrected (the **On** toggle saves itself and applies — same path as Enable & restart; the old "takes effect on the engine's next start" sentence is gone); **`view.ofx`** documents the symbol picker (streaming now → enabled → configured → off); **`work.menubar`** documents the Run menu; the wizard's **Ready** step recaps the Systems card, Market Watch and the Run menu.

**Fixed in passing.** The Market Watch markup first shipped with literal `\u2019`/`\u2026` text (HTML does not interpret JS escapes) — decoded to real characters the moment the receipt screenshot showed `source\u2019s` on screen.

**Receipt.** A sandbox headless instance on 8099 (which also exercised run mode #2 end-to-end) answered `/marketwatch?source=mt5` with 35 live rows; the browser receipt showed the Run menu open with all three modes plus the Optional rows, and the panel rendering `AUDUSD 0.71123 ↘ −0.27% · EURGBP ↗ 0.39% · EURUSD ↘ −0.58%` — the terminal's own numbers in MT5's own format. The owner's instance was then relaunched fresh (also picking up the new backend routes), engine restarted on BTCUSDT/ETHUSDT/SOLUSDT/TRXUSDT, Systems board **4 of 8 — 50%**.

**Gates at save.** pytest **1019 passed / 2 skipped**; AUDIT CLEAN (**86 JS modules**); ruff clean; **27 node selftests / 0 failures**; OpenAPI **147 operations**; goldens OK. Badges re-derived (tests 1019, API 147).

---

## §88 — the Market Watch board goes live (2026-09-18; **nothing committed**)

**The directive:** the board should show real-time movement without a manual refresh — and if real-time input is displayed, a pause control is needed.

**Built.** The view now re-reads on its own **~1.5 s timer** while it is visible (the duplicate fetch on the slow tick was removed). Rows update **in place** — same symbol set → cells patched, no innerHTML rebuild, no flicker; a price cell **tints green/red by its last move** and flashes on every change (a forced reflow restarts the animation when a move repeats in the same direction); the change column keeps its day-colour + arrow. A **live badge** beside the title shows the read's age in seconds (*live · 1 s*) — when reads stall, the age grows, which is the honest signal — and turns red with *paused · last read N s ago* while frozen. **Pause** freezes the board exactly as it stands: auto reads stop, a read that lands mid-pause is **dropped**, and view-entry respects the pause; **Resume** snaps it current with one forced read; **Refresh** takes a single fresh read even while paused; source/filter changes remain explicit actions and re-read under either state.

**Server cost.** The MT5 path now caches the **daily-change basis** per symbol (`_MT5_OPEN`, 300 s TTL) — the live part of a poll is the tick, nothing else — and the Bybit snapshot TTL dropped 4 s → **1.5 s** to match the panel's cadence. New pins: the basis is fetched once across two polls, and expires when the TTL says so (`test_market_watch.py` 11 → **13**); the table model pins `bidDir` (unquoted/first paints never tint) — selftest 13 → **18 checks**.

**Receipt (live, against the owner's terminal).** Snapshot → 4.5 s later with no interaction: `EURGBP 0.85965→0.85964 tick-down · EURJPY 179.116→179.117 tick-down,tick-up · EURUSD 1.14769→1.1477 tick-up` — values moved and tints applied; Pause → two snapshots 5 s apart **identical**, badge *paused · last read 0 s ago*; Resume → values moving again. Help topic updated (live + pause bullets; tags `live/real time/pause/freeze`).

**Gates at save.** pytest **1021 passed / 2 skipped**; AUDIT CLEAN; ruff clean; **27 node selftests / 0 failures**; badges re-derived (tests 1021).

---

## §89 — per-surface pause for the live panels (§89; 2026-09-18; **front-end only — a reload, not a restart**; nothing committed)

**The directive:** audit every live feed / UI data visualization for a helpful Pause, so the user can stop and study while paused — the §88 Market Watch button's idea, program-wide.

**The audit's finding.** The program already had the right halves — `pause.js` (the GLOBAL hold: top-bar chip + **P**, clearing registered timers) and `intent.js` (the per-surface arbiter: gesture leases, **defer queues that apply on release**, `freezeView` wired to the global pause, surfaces named by `data-surface` markup). Missing: a **sticky** per-user hold (a lease is transient), the buttons, and — on several panels — any consultation of the arbiter at the paint path. Two real global-pause gaps were also found and closed: **Atlas-V2's 4 s poll** (now registered with `pause.js`) and, by folding §88's bespoke Market Watch flag into the shared machinery, the board's timers; and the **WS paint cases** (`tick`/`candle`/`delta`/`signal`/`orderbook`/`stats`) painted regardless of any hold.

**Built.** `intent.js` gains **sticky user holds**: `setUser/toggleUser/userHeld/onUserHold`, persisted per browser (`ofap.userholds`), chip text distinguishing *"⏸ tape · marketwatch paused — feed live · N update(s) waiting"*, `paintButtons()` keeping every button's face honest from the effective state, one delegated click listener. **Nine wired surfaces, each with a button in its view head: Overview, Chart, Order-flow (footprint), Engine (ofx), Market depth, Time & Sales, Market Watch, Signals, Trackers.** The freeze is REAL on every one — ofx's poll and Trackers' v2 poll already consulted the arbiter; the others got guards at their WS paint cases and at their loaders (every caller benefits), and resuming applies the queued update exactly once. The §88 Market Watch pause was refactored onto the shared mechanism — **one pause system, not two** (pinned).

**The honesty rule, stated.** CVD / heatmap / profile / frames got **no button**: their paint paths do not consult the arbiter yet, and a button that lies is worse than none — follow-up noted. Replay keeps its own transport; Strategy / Performance / News / Watchlist / Scanner follow the global pause.

**Pins.** `test_pause_surfaces.py` (5): every button ↔ a real `held()` in code, every wired surface declared on its section, no parallel `mwPaused`, the intent API ships, holds persist with honest repaint. `intent.selftest.js` 7 → **12** (park one panel while others stay live; toggle; persistence round-trip; hold-adapter callbacks once each way; sticky across a view freeze).

**Receipt (live, owner instance).** Tape parked via its button → chip *"⏸ tape paused — feed live · 23 tick/s"*, button face flips **Resume**, Market Watch keeps moving (AUDUSD 0.71126 → 0.71129 across readings). Both parked → board frozen, chip *"⏸ tape · marketwatch paused — feed live · 15 tick/s · 1 update waiting"*. Resume → *"Pause"*, chip clears, row snaps current.

**Deploy note:** front-end files only — **Ctrl+R reload, no app restart needed.**

**Gates at save.** pytest **1026 passed / 2 skipped**; AUDIT CLEAN; ruff clean; **27 node selftests / 0 failures** (intent 12 checks); badges re-derived (tests 1026).

---

## §90 — the live-tick layer: nothing that moves may move silently (§90; 2026-09-18; **front-end only — reload**; nothing committed)

**The directive:** audit every live display for static-looking values that could be ticking, and give movement a graphical voice — arrows for direction, colour, flashing — with good-GUI norms kept. The §88 Market Watch look (slanted arrows, green/red, flash) was the reference.

**Built — one shared layer, one look.** New `ui/ticks.js` (+ 9-check selftest): `OFAPTICK.tick(el, text, {arrow})` compares against the element's own remembered reading (`data-tick-prev`), tints green/red in the direction of the move, flashes on **every** change (forced reflow restarts the animation), and prefixes a slanted arrow; `OFAPTICK.arrival(el)` announces freshly inserted cards. `dir()` treats a dash/blank as *not a zero* — a caught bug (the em-dash on a quiet symbol was reading as 0 and flashing phantom rises; pinned). CSS generalises Market Watch's rules to the whole program (`.tick-up/.tick-down` + `tick-in` arrival).

**Wired (all verified live):** Overview **price** and **cumulative delta** KPIs (and their chart-strip twins), the **depth strip** (best bid/ask arrows, imbalance tick), chart + order-flow **POC/VAH**, **CVD (session)** value, the **Trackers nav badge** (flashes on increment), **signal cards** (newest slides in), **Systems tiles** (only the tile whose state changed flashes), and the whole **Scanner view** — its rows tint the moved price and flash on number changes (rows are rebuilt per poll, so the comparison lives between renders in `SCAN.prev`). Live receipt: price cycled `· 76809.00 → tick-down → ↗ 76809.10 tick-up → tick-down` on real ticks.

**Scanner also joined §89** (the audit's one miss): it now declares `data-surface="scanner"`, carries its own **Pause** button, consults `held('scanner')` (defer + snap on resume) and registers its 4 s poll with the global hold — a silent global-pause gap closed. Its loader was already gesture-aware; the pin set grew accordingly.

**The audit's honest remainder.** Already inherently live and left as they are: the chart/heatmap/footprint/CVD **canvases** (they redraw continuously), the tape's buy/sell colouring and large-print emphasis, freshness chips (already age-ticking), and the order-flow stats line (frame telemetry, not market data). Still on the follow-up list: per-cell ticks inside the L2 ladder body (its component builds cells outside the tick layer), and CVD/heatmap/profile/frames pause buttons (§89's note).

**Gates at save.** pytest **1030 passed / 2 skipped** (+1 scanner pin, +3 tick pins), AUDIT CLEAN (**88 JS modules**), ruff clean, **28 node selftests / 0 failures** (ticks 9 checks); badges re-derived (tests 1030).

---

## §91 — hide/show for the frame: menu bar, rail, status bar (§91; 2026-09-18; **front-end only — reload**; nothing committed)

**The ask:** a hide/show option for the side and top menu bars. The View menu already carried **Rail**, **Status bar** and **Full screen (zen)** toggles (class-only, no persistence, no keys); the **top menu bar itself** had none — and hiding the menu bar is the trap case, because the View menu lives in it.

**Built.** New `ui/chrome.js` owns the three toggles: `.app.menubar-hidden/.rail-hidden/.status-hidden` (+ zen), persisted per browser (`ofap.chrome`), applied **before first paint** where possible (`restore()` at load), events on `ofap:chrome`. Keys **B** (menu bar) and **R** (rail) are bound in the same module — so the way back can never depend on the thing that was hidden — and the menu bar's toggle even says so in the status line: *"menu bar hidden — press B to bring it back"*. `menubar.js` now delegates its three wrappers to the owner (the View menu items show persisted check states, with B/R accelerator hints); `modules.css` gained `.app.menubar-hidden .menubar { display: none; }` beside its siblings. Help: the menu-bar topic documents B/R.

**Receipt (live).** `B` → menubar `display:none`, rail untouched, flags `[true,false,false]`; `R` → rail gone too (screenshot: full panel grid, topbar and status bar intact, no File/View row, no rail); `B`+`R` → both back; hide rail, **reload** → rail stayed hidden (persistence), one press restored it.

**Pins.** `test_chrome_ui.py` (4): the module ships and is registered; the B key exists in the same module that hides the bar ("can never trap"); the View menu offers all three and delegates; every CSS rule exists.

**Gates at save.** pytest **1034 passed / 2 skipped**; AUDIT CLEAN (**89 JS modules**); ruff clean; **28 node selftests / 0 failures**; badges re-derived (tests 1034).

**Incident note (own it).** During the receipt a self-matching process filter (`CommandLine -match 'browser_harness'` matched my own shell's command text) killed shell wrappers and took the running app down with them at 03:05:47 — a clean exit per the log, not a crash. The app was relaunched and the receipt redone. Lesson: never filter on command-line text that contains the filter itself; match exe name + a distinctive argument instead.

---

## §92 — the Keys menu, shortcut prompts, and the UX/shortcut audit (§92; 2026-09-18; **front-end only — reload**; nothing committed)

**The ask:** a keyboard-shortcut helper menu in the top menu bar; program-wide hover prompts wherever a shortcut exists; and an audit of the main/common journeys with shortcuts mapped onto them. Plus, mid-task: **physical hide/show buttons on both bars**.

**The audit found two real lies and two real gaps.** The File menu always displayed **Ctrl+Alt+R** for the engine restart and no such binding existed; start/stop had neither key nor hint. And every session needs "find an instrument" and "move through the panels" without the mouse — neither had a key. New bindings: **Ctrl+Alt+S** start, **Ctrl+Alt+X** stop, **Ctrl+Alt+R** restart (the displayed accelerator is now true), **Ctrl+F** the look-up (OFAPHINT), **Ctrl+PgUp/PgDn** previous/next rail panel (terminal-focus aware, verified: overview → chart → heatmap → back). A duplicate zen binding was caught by the receipt and removed — **menubar.js's Alt+Z stands** (lesson recorded: check the registry before binding; same ids replace silently).

**The Keys menu** (top bar, between Run and Tools): built from `OFAPKEYS.list()` — the same registry the dispatcher and the hotkey sheet read, so it cannot drift — grouped by scope; **clicking a dispatched row runs that action**; documented-but-local rows show their scope instead of pretending. Receipt: the menu opened listing *Shortcut sheet (?), Keyboard help topic, GLOBAL, … start the engine Ctrl+Alt+S … find an instrument Ctrl+F … freeze/resume P*.

**The prompts.** New `OFAPKEYS.annotate()` (re-runnable; called at boot, after every menubar render and from chrome's wire): controls that have a shortcut carry it on their **tooltip** (`title` ends "· Shortcut P"), for screen readers (**aria-keyshortcuts**) and inside their **hover card** (hint.js appends a "⌨ Shortcut …" line when the target has one). Wired to: pause chip (P), ☰ (Ctrl+K / /), engine start/stop, terminal-mode button, the four chrome controls (B/R) and the **rail items 1…9** by order. Receipt read-back: `pause:P · railHide:R · menubarReveal:B · menuBtn:Ctrl+K / / · rail0:1`.

**The physical buttons.** The menu bar carries its own **"⌃ hide"** at its right end; the topbar gains a **"⌃ Menu bar"** reveal that exists only while the bar is hidden; the rail footer gains **"❮ hide rail"**; a slim left-edge **"❯"** reveal appears only while the rail is hidden. All four go through chrome.js's owner toggles; CSS shows each reveal exactly when (and only when) its bar is hidden — verified live: `mbHide → [hidden, reveal visible]`, `railHide → [hidden, reveal visible]`, restore clears both.

**Pins.** `test_keys_ui.py` (5): the menu is built from the live registry and runs rows; every advertised accelerator has a binding (the Ctrl+Alt trio); the common-journey keys exist; annotate + hint-card shortcut line; the physical controls exist on both bars with their reveal CSS. `keys.selftest.js` unchanged at 42 checks.

**Gates at save.** pytest **1039 passed / 2 skipped**; AUDIT CLEAN (**89 JS modules**); ruff clean; **28 node selftests / 0 failures**; badges re-derived (tests 1039).

---

## §92b — postscript: the chrome controls, unified (2026-09-18; front-end only; nothing committed)

**The owner's follow-up, verbatim in spirit:** keep the menu bar's own "hide" (without a leading symbol), add a control for the left rail that works in/out, and attend the lesson that a control should not vanish together with the thing it controls — the rail's in-bar button disappears with the rail, so the menu bar must not repeat that trap.

**The unified model (shipped).** Each bar now has exactly two controls, each with a single clear job:
- **A persistent in/out toggle in the topbar**, beside the ModFlow mark — **◧ rail** and **▤ menu bar** — always visible (the topbar never hides with either bar), `aria-pressed` + a pressed face kept honest by chrome.js, annotated with their B/R shortcuts. These are the controls that *cannot* hide with what they control.
- **One-way "hide" quick actions in place**: the menu bar's plain **"hide"** at its right end (the ⌃ symbol removed per the follow-up), and the rail's discreet **‹** beside its logo.
The state-dependent reveal buttons (`#menubarReveal`, `#railReveal`) were **removed** — with persistent toggles they were the confusing half of the dance.

**A live-caught bug, and the clamp that ends it.** The first receipt of the new toggles showed them rendering as literal `\u25e7` text: the glyphs had been written into index.html as JS-style escapes, which HTML does not interpret (the §87 class of bug, shipped again). Fixed with real glyphs (◧ ▤ ‹) and — instead of trusting care — **a new pin** (`test_the_markup_never_ships_literal_escape_text`) fails the suite if any `\uXXXX` literal appears in index.html. The served bytes were then verified directly: `>◧`, `>▤`, `>‹`.

**Receipt.** Functional pass (browser): railToggle and menubarToggle hide/show their bars with `aria-pressed` tracking both ways; **B** and **mbHide** agree with the toggle's pressed state; while the menu bar was hidden the toggles stayed visible and usable (the point of the model); old reveals absent; the rail's ‹ sits in the brand row. Bytes pass (curl on the live server): the three glyphs are real characters in the served markup. *(The browser daemon flaked on the final screenshot attempt; every claim above is grounded in the earlier live session or in the served bytes.)*

**Gates at save.** pytest **1040 passed / 2 skipped** (the new escape pin); AUDIT CLEAN (**89 JS modules**); ruff clean; **28 node selftests / 0 failures**; badges re-derived (tests 1040).

---

## §93 — the rail's return arrow + the menu reconciliation document (2026-09-18; front-end only; nothing committed)

**Owner's report:** the rail's hide works (the ‹ by the logo) but the way back was not visible — the persistent topbar toggle was too subtle to find.

**Fixed.** The left-edge **return arrow** is back and styled to be found: a 22×84 px tab at the rail's edge reading **❯**, shown exactly while the rail is hidden (CSS ``.app.rail-hidden .rail-reveal``), wired to the same chrome owner, annotated with R. The topbar toggles now carry **directional faces** — ⇤ hides / ⇥ shows the rail; ⌃ hides / ⌄ shows the menu bar — so each button states what pressing it will do, and its title follows the state. Verified from the served bytes: `id="railReveal" … >❯`, `railToggle … >⇤`, `menubarToggle … >⌃`.

**The reconciliation document (the standing deliverable for the menu audit): `docs/MENU_RECONCILIATION.md`** — method (re-runnable extraction), the rail table (28 views: updater, pause button, key, notes), the menubar inventory (11 menus; 26 planned stubs classified into stale-now-promotable / real-unbuilt / environment-dependent; 3 honest disabled rows), the **unexposed-route table** (13 routes with no UI caller), findings **F1–F7** and a scoped upgrade queue. Headline finding **F1**: the Trackers view advertises "correlation, dots, cross-venue reads" and fetches none of them — five live `/api/atlas` routes (`dots`, `correlation`, `crossvenue`, `intent`, `trades/recent`) have no caller; the CSV exports (F2) and `storage/prune` (F3) sit dark as well.

**Gates at save.** pytest **1040 passed / 2 skipped**; AUDIT CLEAN; ruff clean; 28 node selftests / 0 failures.

---

## §94 — the stuck "Close" remnant after quitting: the aux-window sweep (2026-09-18; nothing committed)

**Owner's report (with a photo):** a small black window carrying a white "Close" button sat on the desktop after ModFlow was closed.

**Forensics.** Not a crash: Windows' Application-Error/WER logs hold no python events in the window, the app log ends 03:41:47 with the ordinary "Dashboard client disconnected" line, and the screenshot timestamp (03:42:47) matches exactly one minute later — the remnant appeared as the app went down. Not app UI either: no "Close" control exists anywhere in the app's code (`Close` text buttons live only *inside* panels — chain/compare cards). The architecture answers it: in Terminal mode the widgets are **real auxiliary OS windows** (`NativeWindowHost`, `create_window` per widget), and the quit path closed the MAIN window and returned out of `webview.main()` **without taking the aux windows down** — a widget window still up while the process exits survives as a **ghost frame** (owner gone ⇒ clicks do nothing; it clears when the desktop repaints).

**Fixed (§94).** `NativeWindowHost.close_all()`: destroys every aux window, and — the part that matters — sets `_quitting` so the per-window `forget` bookkeeping **keeps the store's records** (the widgets still come back where they were on the next start). `main()` now captures the host (`host = restore_windows(port)`), chains the MAIN window's `closed` event to `host.close_all()`, and calls it once more idempotently before returning; the WebView2-fallback path is covered by the same tail sweep.

**Pins.** `test_aux_windows.py`: `close_all` destroys all three fakes, empties the registry and provably does NOT drop records; plus a file-level pin that main() holds the host and sweeps on quit.

**Gates at save.** pytest **1042 passed / 2 skipped**; AUDIT CLEAN; ruff clean; 28 node selftests / 0 failures. The fix takes effect on the next app start.

---

## §95 — the toggle move, the ingest audit + its six closures, the storage system, the industry sweep, and the R-build (updater · data port · paper · journal · calendar) — built 04:00–05:34, the session crashed at the first step of its final live pass, and the recovery verified everything after fixing two real defects it surfaced (2026-09-18; **nothing committed**)

**The crashed session, and the recovery.** The work below was built in the 04:00–05:34 session, which died during the FIRST step of its final live-verification pass (the process vanished; the sandbox it had just restarted survived). This session reconstructed the in-flight step from the session DB (the last messages + the exact verify script), re-ran the entire verification pass on a fresh sandbox, and fixed + pinned two real defects the pass surfaced. Nothing was lost. Recipes: `session DB → messages tail` for the in-flight step; big API payloads go via a *script file* run with the venv python (a ~500 KB body through a heredoc fails on the Windows command-line limit — that is why the crashed pass's import call died client-side).

**(a) The topbar toggle move (the 04:00 ask).** The top-menu-bar toggle left its bare caret spot beside Instrument for the topbar's right end, immediately right of the "▶ live — updates running" chip, as a labelled pill ("⌃ menu bar"; glyph flips ⌃/⌄, pressed face while the bar is hidden). Verified live over CDP (x 1160–1248 vs the live chip ending at 1140; click hides/restores; aria-pressed/title/face all track; B key still toggles). Files: `index.html`, `modules.css`, `chrome.js`. Open cosmetic: first-load tooltip reads "… (B) · Shortcut B" (the annotate pass appends; after a click it reads "(B)") — owner's call.

**(b) The full data-feed & storage audit.** Five parallel read-only auditors swept the ingest core, engine wiring, front-end consumption and the cross-feed matrix against the owner's live instance; **17 changes across 19 files** landed and were re-verified line-by-line: MT5 stamps ticks with the BROKER clock (+3 h on the demo) — now learned + converted (live ticks, historical ticks, bars; 7 pins; the evidence was a stray collector DB whose newest stamp was mtime + 180 min); Bybit book snapshots were stamped with the update sequence id — now the envelope ts; the reconnect ladder resets on data only (acks/pongs no longer count); Alpaca REST snapshots deduped (phantom volume/delta); the NinjaTrader quote book is a true top-of-book; a DB write error inside a tick/periodic handler can no longer tear down the websocket or kill retention for the session; the Bybit extras feed is bybit-only (logged when skipped); binance/okx/hyperliquid capability rules are asset-class based with an honest skip reason; engine settings apply BEFORE instrument selection; the standalone collector's DB resolves per-user and its log rotates 2 MB × 4 — the cause of the 76 MB repo stray; retention now ages out candles, signals, profiles and atlas events on the same window; `incremental_vacuum` actually reclaims (and refuses politely on no-space); the Logs panel's storage snapshot works with the engine stopped (sizes, WAL, page accounting, per-instrument tick span, persisted last-prune); the P button freezes bus channels (not just the paint); the chart freshness chip says "demo data" for demo bars. Live: fresh profile, engine boots clean (382/614/261/3 ticks in 30 s, tape age 1.7 s, /sources 2.49 s → 0.005 s cached, zero ERRORs). Gates at that point: pytest **1068**.

**(c) The six open items, closed** (owner: *"if 1-6 are fixable and valid to fix then go ahead"*). (1) **both/all venue mixing** — `engine.partition_instruments()` is the single rule: one instrument = one venue (explicit stamp wins per started leg; crypto never rides Alpaca's quote-only lane; a broker mapping beats the class default); `all` now truly runs every leg; the first live boot caught my own first cut assigning wizard-mapped crypto to a leg `both` never starts (0 ticks, no error) and it was re-proved — source=both on the owner's config: Bybit leg [ETHUSDT, SOLUSDT, TRXUSDT], MT5 leg [BTCUSDm], extras follow the exchange leg. (2) **MT5 zero-volume prints** are still carried as 1 lot (order flow cannot hold a zero fill) but counted and warned once per session. (3) **Market Watch** answers okx/binance/hyperliquid with their OWN listings (cached 5 min, fetched off the event loop), each labelled with its venue — the old test was pinning the bug. (4) **the ofx 2.5 s poll** is view-scoped (server log: hidden 20 s → 0 requests, shown → 50). (5) **the 80.5 MB strays** left the repo for `%APPDATA%\OrderFlowAnalysisPro\archive\stray-repo-data-2026-09-18\` (the only copy of those 880k MT5-class ticks — the erase call is the owner's); the stray log is deleted. (6) **the Systems board's Alerts row** now names the channels and flags the PUBLIC ntfy.sh topic. Gates: pytest **1075** (+33 pins). Note left for the owner: BTCUSDm does not exist on the MetaQuotes-Demo terminal — rename the mapping or let crypto ride the exchange.

**(d) The storage management system** (owner's request). `desktop/storage.py` + two new Settings cards (**Storage**; **Backup & reports**) + the engine's own job + a headless CLI. Usage monitor (DB/WAL/logs/exports/backups, real bytes); growth sampling + honest forecast (~437 MB/day at a 7-day window ≈ 3 GB steady state); user-definable retention (days / prune hours / session hour — re-read each pass; proven live); a size budget with a once-a-day alert (Systems board, log, Telegram/ntfy, email); Prune now / Reclaim / Sweep buttons; backups: one ISO-stamped folder per run — hot SQLite copy via the database's online-backup API (ONE file: the WAL-sidecar defect found while verifying, fixed), analyst tables as RFC 4180 CSV, ticks-summary, `manifest.json` (row counts, sizes, SHA-256, quick_check verdict); targets any writable path incl. UNC/drive/synced folder, proved by writing first (bad path answers with the OS reason); rotation by manifest, automatic scheduling, email report (plain text + CSV), and `python -m orderflow_system.desktop.storage backup|report` for Task Scheduler. Defaults conservative (automatic backups OFF). Gates: pytest **1089** (+14 pins).

**(e) The industry sweep** (three cited inventories: MT5's help tree; Bookmap/ATAS/Sierra/Jigsaw/Exocharts/Quantower/MotiveWave vendor docs). Verdict delivered: ModFlow is not behind on analytics — it already covers the surfaces those platforms are sold on; the six addable clusters were ranked (paper+ticket → journal+statement → CSV import → update check → calendar → depth niceties) and the not-worth-adding list was named. Two of my own would-be-wrong claims caught before writing (TPO Market Profile and non-time bars already exist).

**(f) The R-build** (owner: *"build them all + a real time update system with update checks on load/regular, background, download … add the update section to the top menu bar"*). New modules + routes + views, all pinned:
- **R7 updater** (`desktop/updater.py`, `ui/updates.js`): checks the public repo's releases on load and on a timer (hours configurable), channel/mode/skip settings, download on request + open folder, never interrupts the work; the top bar gained the **Update** menu (running build, newest release, one-click fetch; the title badges "Update ●" while one waits).
- **R8 data port** (`desktop/dataport.py`): CSV import (the app's own export shape, MT5/Sierra/Databento-style or headerless; epoch s/ms/ISO; delimiter sniffed; unreadable rows counted with reasons) into the suite's own DB, and per-table / per-instrument CSV export. **The crash's last fix lives here**: two genuine same-millisecond prints share (instrument, ms, price, size) — the dedupe key now includes `trade_id`, and the counts split `deduped` from `bad_rows` (the 261-row file read 115 "bad" before; the recovery's 5,988-row and 217-row round trips read `bad_rows: 0`, every row named as existing).
- **R9 paper simulator** (`desktop/paper.py`, `ui/paper.js`, ticket on the Replay view): market/limit/stop + SL/TP, fills from the tape's own prints, flatten / cancel / end; ended sessions write `trade_journal` rows. **The recovery's fix lives here**: a limit/stop whose level the tape had already passed was accepted as "working" and then filled at its own price — a sell limit at 1.0 on a ~2,450 tape booked a **-244,699-tick fantasy loss** into the journal. It is now refused at submit with the reason (*"a sell limit at 1 would fill the moment it is placed — at a price the tape never traded (last 2451.53)"*), pinned in `test_paper.py`, and verified live.
- **R10 journal** (`desktop/journal.py`, `ui/journal.js`, rail view): stats (win rate, gross win/loss, profit factor, expectancy, Sharpe), per-trade notes saved, daily P&L, and a broker-style self-contained **HTML statement** written to the exports folder.
- **R11 economic calendar** (`desktop/calendar.py`, `ui/calendar.js`, rail view): the keyless Forex Factory weekly JSON (this + next week), cached 4 h, impact/currency filters, optional lead-time alerts through the existing channels; honest stale/error handling (events show clean while a supplementary file fails; "unreachable — nothing shown rather than guessed" when both fail).

Integration: the rail gained Journal + Calendar; every new view carries a Help topic (the suite's own coverage pin caught the two missing ones — written at 05:27); the audit registered the new modules; the top bar carries Update.

**The recovery verification (this session, live on sandbox 8089 — fresh profile + the owner's config).** Engine bybit, 4 symbols; calendar live (3 upcoming high-impact; the crash-minute 429 was venue-side rate limiting, not the app); data-port round trips `bad_rows 0`; paper: the refusal sentence live, then a real session — buy 2 market filled at 2452.69, flatten at 2451.53, **-232 ticks booked correctly** (arithmetic checks out), *"saved to the Journal view"*, journal row + HTML statement written; updater status/check live; storage snapshot live; **0 client errors** in the sandbox log.

**Gates at save (post-fix).** pytest **1241 passed / 2 skipped**; `audit_ui_refs.py` **AUDIT CLEAN** (94 JS modules); **28 node selftests / 0 failures**; ruff clean.

**Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt** (the payload changed heavily — next packaging pass re-runs payload parity + the installer journey); **nothing committed** (HEAD `110c568`, 108 dirty entries); the toggle-tooltip cosmetic; the BTCUSDm-on-demo note; update/backup defaults conservative by design (the owner switches them on).

**Addendum (same day, after the recovery): the UX comparative study.** The owner asked for a deep layout/UX/GUI comparison against the paid order-flow platforms. Seven parallel cited briefs were produced and cross-checked (Quantower, Bookmap, NinjaTrader 8, MetaTrader 5, Sierra Chart, ATAS + a measured inventory of ModFlow's own surface) and are copied into the repo at `docs/ux-study/`; the synthesis is `docs/UX_COMPARATIVE_STUDY.md` — a plan for approval with waves A/B/C and a proposed first package (T1 contextual help wiring · T2 window/layout trust · T3 armed-hotkey/legend/paper-safety trio). Headline transferable assets: Sierra's modeless-searchable settings UX, Bookmap's canvas-precision vocabulary (cursor-anchored zoom, held-key drag, pixel nudge, hysteresis), the field-wide "unreachable window" failure class (our aux windows have no clamp/restore yet), and Bookmap's explicit synthetic-data labelling (our inferred analytics don't mark themselves). Also found, code-observed: the rail-top Setup button shifts the 1–9 digit view mapping by one (`keys.js:236-242` vs `guide.js:2314`) — verify + fix when convenient. Nothing in the app was changed by the study; approval pending.

---

## §96 — the UX study's first package, built and live-verified: T1 contextual help · T2 window & layout trust · T3 the order-safety trio (2026-09-18; **nothing committed**)

**The ask:** "T1–T3 go" — the proposed first package from `docs/UX_COMPARATIVE_STUDY.md` (the seven-brief UX/GUI comparison; briefs in `docs/ux-study/`). All three were built to the standard gates and verified live over CDP on a fresh sandbox (8089, owner config copied, stopped afterwards; 0 client errors in its log).

**(a) T1 — contextual help.** `help.js` gained the layer the field's best products have and ours lacked: **`focusedTopic()`** (the shell's focused widget, else the visible view section, mapped through the corpus' VIEWS table); **one "?" injected into every panel head** (idempotent, debounced `MutationObserver` sweep so runtime-injected views get theirs too); **a delegated `[data-helptopic]` click** opening that topic in the Help Centre; **`OFAPHELP.topicLink()`** for modules that render blank states; and **F1 now answers for the panel in focus** (falling back to the Help Centre home). Blank/error states wired: the replay ticket's empty fills (static + the runtime branch), the journal's empty table, and the calendar's unreachable-feed state. Live receipts: **31 panel-help buttons** on the page; `?` on Heatmap → `view.heatmap`; **F1 on Chart → `view.chart`**; the replay blank-state link → `view.replay`. Pins: `test_help.py` +2 (every data-helptopic resolves against the corpus; the wiring exists) → 32.

**(b) T2 — window & layout trust.** Four parts, each pinned:
* **Layout versions (recoverable saves and deletes):** `config_store` keeps a per-layout ring of previous versions (`LAYOUT_VERSIONS_MAX = 10`, sanitised — newest first; a version of a deleted layout survives on purpose); `POST /api/control/layouts` snapshots the old entry before a save-overwrite and before a delete, and gained **`restore_version`**; `GET /layouts` carries a versions summary; the Layout menu lists **"This layout — previous versions"** rows (restore in one click, via `OFAPSHELL.restoreVersion`). Live: two saves kept **3 versions**. Pins: `test_layout_versions.py` (8).
* **Layout lock:** one switch holds the arrangement still — move, resize, **add, remove, tab reorder** all gated (`setLocked`/`refuseLocked` in shell.js), persisted as **`ui.layout_lock`**, toggled from the Layout menu, shown by a **status-bar chip**. Live: locked → chip visible + persisted to config; gates hold. Pins: `test_layout_lock.py` (4).
* **Windows & layouts dialog (new `ui/windowing.js` + audit registration; 95 modules now):** the master list the field's bug reports demand — screens, every window in the set (open/closed), **Focus / Pin / Reset position / Close / Remove**, and Close-all, all through `POST /api/control/windows`. The route gained the **`reset`** action: geometry dropped, window re-placed on the primary screen, reopened there when open — the in-app rescue for "the window became unreachable". View menu → **Windows & layouts…**. Live: the dialog renders ("auxiliary windows need the desktop app" in the headless session); the reset behaviour is pinned against the fake host in `test_aux_windows.py`. Pins: `test_windowing_ui.py` (4) + 2 aux-window route pins.
* **Safe start:** `--safe` on the desktop entry — `restore_windows(restore=False)` (host installed, nothing comes back) and the layouts route answers **Classic + `safe: true`** without writing the store. Pins: `test_safe_start.py` (3; one pre-existing pin updated to the new restore call).

**(c) T3 — the order-safety trio.**
* **Armed order keys:** `keys.js` gained the armed gate — a row marked `danger: true` **cannot dispatch until armed** (visible per-session switch, default OFF), the status bar carries the **"⌨ order keys armed"** badge, the Keys menu carries the arm/disarm toggle, and a disarmed press of an order chord explains itself ("that key places a simulated order — arm the order keys in the Keys menu first"). The pure half is pinned in `keys.selftest.js` (+3 = 45 checks: danger row inert disarmed, fires armed, inert again after disarm).
* **The paper order keys:** **Alt+B buy · Alt+S sell · Alt+X flatten** — danger-gated, and `when`-gated to the Replay view being on screen, a session running, and trading unlocked.
* **The registry legend:** menubar rows may name a binding id (`keyId`) and the accelerator **renders from the live registry** (`OFAPKEYS.accelOf`) — the §92 File-menu lie is now structurally impossible; the engine start/stop/restart rows were converted; the Keys menu gained **"Copy the shortcut list"**.
* **Paper lock + danger row:** the ticket carries **Lock trading** (persisted as `ui.paper_lock`); locked kills Buy/Sell clicks AND the armed keys, while **flatten / cancel / end stay live** (the panic controls); the row is styled as the danger strip. Live receipts: disarmed Alt+B → **no order** + the hint sentence shown; **armed Alt+B → the order lands** (`recent` proves `paper-buy` fired; orders 0→1); locked → click disabled and the key refused; badge + persistence confirmed; disarm/unlock tidy. The live pass caught one real bug in this very code — `toast()` takes its target first, and the hint passed the text as the target — fixed and re-verified. Pins: `test_safety_ui.py` (6) + the selftest checks.

**Gates at save.** pytest **1269 passed / 2 skipped** (+28 pins across the three packages); `audit_ui_refs.py` **AUDIT CLEAN** (**95 JS modules**, windowing.js registered); **28 node selftests / 0 failures** (keys 45); ruff clean. Live pass on sandbox 8089: every receipt above, 0 client errors; sandbox stopped, ports clear.

**A pitfall measured during the live pass (now in the skill):** a headless CDP page reports `document.hidden === true`, so every view-scoped gate and poll (by design) refuses — `Emulation.setFocusEmulationEnabled` makes the page count as visible before driving view-scoped behaviour.

**Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 121 dirty entries); the study's remaining Wave A items, Wave B and Wave C await approval (`docs/UX_COMPARATIVE_STUDY.md` §5).

---

## §97 — UX study Wave A, second package: “trust & legibility” (T4) — A5 · A6 · A7 · A9 · A16 · A17 · A19 + the rail digit-map fix (2026-09-18; **nothing committed**)

**The ask:** “i want the next package” — the next batch from `docs/UX_COMPARATIVE_STUDY.md` §5 after T1–T3. T4 took the trust/legibility half of Wave A; every item was built to the standing gates and verified live over CDP on a fresh sandbox (8089, owner config, 0 client errors, stopped afterwards).

**A5 — user-settable freshness thresholds + the delayed-data badge.** The freshness spine already existed (`freshness.js` chips + verdicts); what was missing was the user's own threshold and one honest global signal. `atlas.freshness` (seconds, 0 = built-in window; **display-only** — the server tables in `atlas/freshness.py` are untouched and `test_freshness.py` still holds the two tables equal) now flows: sanitiser rebuilds + clamps it; `ATLAS_FIELDS` renders four rows in Settings; `param_registry` registers them (that gate caught the omission); `freshness.js` consumes via `setWindows()` (payload-owned windows still win), re-judges existing rows instantly, adopts at boot and after every save/reload. Live: form → 45 → `window('depth')` 45000 → persisted 45 → restored 5000.

**A6 — inferred analytics say so, everywhere.** Icebergs were already labelled (tile “(inferred)”, card tag, empty-row text — the study's inventory had missed them). Completed the set: the Sweeps tile + card and the Stop-runs card now carry `inferred` tags with tooltips (stop runs: “confirmed” still means liquidations corroborated it); the scanner's Sweeps / Stop runs / Absorb column helps end “Inferred from the tape.”; the sweeps/stop-run empty rows say where the rows come from. Provenance: venue chips and `statusSource` were already live; the chip-source mechanism accepts a label. **Deferred, honestly:** the per-symbol *gap count* has no ingest counter to read — recorded as a Wave B-sized piece, not faked.

**A7 — freeze-on-hover (new `ui/freeze.js`).** Hovering a listed canvas section suspends that view's repaint (guards in `drawHeatmap`, `drawSeries`, heatmap-pro's `draw`, the OFX tick), marks it `.ofap-frozen` and shows a “frozen — move away to resume” chip. Payloads are not queued or replayed: the newest state paints on the tick after the pointer leaves. Live: mouseenter → frozen + chip; leave → cleared.

**A9 — dynamic titles + canvas watermarks (new `ui/watermark.js`).** One faint label per canvas card — **instrument · view · mode** (· held) — read from live state and **hidden when no instrument is readable** (a watermark that invents a symbol is worse than none). Terminal widget titles gained the same token (`titleToken`, refreshed in `paintBar`). Live: “BTCUSDT · Market depth heatmap · terminal”.

**A16 — the ambient strip.** Status bar gains the **delayed-data badge**, a **feeds-paused** chip and the **oldest-sample** readout. The badge obeys the honest rule (live learning from the live pass): it judges **only panels being watched** — `onScreen()` skips parked sections (a parked panel does not poll, so its age is expected, not a fault), and demo/held/unknown ages never raise it. Live: on-screen stale → badge + named panels; fresh → hidden; parked panel aged → stays quiet.

**A17 — the update policy, written down.** `docs/UPDATE_POLICY.md` (never blocks · never restarts itself · never forced · what-changed notes are part of the update · SHA-256 verification · quiet retries · no account/telemetry), plus a **`work.updates` help topic** (“Updates never block”) and the update card now links it through the T1 help-link machinery. Live: click → topic opens.

**A19 — sound controls.** The player already had volume/enabled in config; the missing half was the door. Settings ▸ **Sound** card (enable · volume % · **Test sound** — which plays at the current volume even while the master switch is off, because that is what a test is for), wired through single-path config merges and adopted straight back. The audio help topic's stale claim (“no sound files”) corrected. Live: card paints 60 %, save persists 0.35, restore works.

**A-corr — the rail digit map (the study's code-observed finding #8), verified and fixed.** The injected Setup button was counted by **four** rail list scans: the 1–9 view switch, Ctrl+PgUp/Dn cycling, the digit annotations, the View menu's panel list, and the command index (a bogus “view:” palette row). All now count `.rail .nav-item[data-view]` only, pinned. Live: Setup carries no digit; Overview=1, Heatmap=3; digit 3 lands on the Heatmap; the wizard stays shut.

**Bugs the live pass caught in T4's own code** (fixed and re-verified; same discipline as T3's `toast` find): the sound card's paint called a `config()` that never existed (module boot threw); the delay badge nagged about off-screen panels until `onScreen()` was added.

**Gates at save.** pytest **1281 passed / 2 skipped**; `audit_ui_refs` **AUDIT CLEAN** (**97 JS modules** — freeze.js + watermark.js registered); ruff (CI pin 0.16.7) clean; **all 30 node selftests pass** (freshness 37, keys 45, audio 39). Live pass on sandbox 8089: every receipt above; 0 client errors; stopped, ports clear.

**Left in Wave A for the next package:** A8 (context-validity menus), A10 (minimal mode / collapsed state), A11 (anti-flicker controls), A12 (canvas precision kit), A15 (set-as-default + factory reset), A20 (data-density knobs), plus A6's gap-count piece (needs an ingest counter first).

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 131 dirty entries).

---

## §98 — UX study Wave A, third package: “canvas craft” (T5) — A11 · A12 · A20 · A10, plus the line-ending repair (2026-09-18; **nothing committed**)

**The ask:** “go for next wave” — the canvas/preset remainder of Wave A after T4. T5 took the four interaction-craft items; A8 (context-validity menus) and A15 (set-as-default + factory reset) are named as the next package.

**A11 — auto-fit hysteresis (the anti-flicker shape).** The Engine stage refit its price scale on every payload while `autoFit` was on — a scale that breathes. There is now a pure verdict (`math.fitDecision(view, band, factor)`, pinned in `ofx.selftest.js`): hold while the data band sits inside the visible range with slack at both edges and the view is not 3× emptier than the band; refit when it reaches an edge or the data shrinks away. `atlas.ofx.fit_tolerance` (0.25 default, 0 = the old always-refit) is read live from the page config; the explicit fit button / snap-to-live / resize still refit unconditionally (`fitHeight(true)`). Live: form 0.5 → `OFX.fitTolerance()` 0.5 → restored 0.25.

**A12 — the canvas precision kit.** The Engine already had cursor-anchored wheel zoom, drag-pan and a shift grammar (verified, not rebuilt). What was missing: **arrow nudges** — Engine scope arrows pan time (left/right) and price (up/down) one pixel, Shift ten (`OFX.nudge`, clamp-aware, disengages autoFit on the price axis); Heatmap scope arrows step its rows (up/down) and its depth window (left/right) through the same actions as the bar buttons. Eight Engine + four Heatmap bindings land in the Keys menu like every other key. Live: `offX 195.0000 → 194.9808` (one pixel at the live scale) and Shift+ArrowRight back to `195.0000`; `autoFit` false after a price nudge; `recent` proves the ids; heatmap rows 200→300, window 240→480.

**A20 — the values divider.** `atlas.heatmap.values_min_px` (0 = off) draws each cell's own size once a cell is at least that wide, contrast flipping against the cell's own ramp colour — the heatmap's answer to the footprint's `text_px` gate. Live, three geometries (2.5 px cells in terminal mode, 7.7 px in classic at a 1920 emulated viewport): **the gate refused every time — honestly**, because a 2-minute window yields sub-10 px cells; the numbers earn their keep on wide-cell geometries only, and the map's HUD remains the value read otherwise. The config round-trip and the renderer's read are live (→60) and pinned; the painted-text receipt is the one thing this pass could not produce, and it says so.

**A10 — minimal mode + the collapsed card.** The heatmap's pro bar carries a **minimal** toggle (persisted as `ui.heatmap_minimal` via `/api/control/params`): CSS hides the window/rows/overlays fields and every bar button except the toggle — hide the chrome, keep the map and every interaction on it (the help button and freshness chip stay). Any card folds by **double-clicking its head** (delegated in `chrome.js`, session-only — a collapse is a reading posture, not a setting). Live: minimal on → class + button text + persisted true; off → false; a trackers card folded and unfolded.

**Bugs the live pass (and the pins) caught in T5's own code — all fixed and re-verified:**
1. **The `window.S` trap.** `S` is ui.js's top-level `let`, not a window property — three new config readers (ofx fit tolerance, the values divider, the minimal adoption) guarded on `window.S &&` and therefore silently pinned their fallbacks. Fixed to read the page binding with a `typeof` guard; a pin now forbids `window.S &&` in those files.
2. **`/params` is a registry gate.** The single-path write takes `{path, value}` and refuses unregistered paths — the minimal toggle's first shape wrote nothing. `ui.heatmap_minimal` is now registered (kind bool) and the pin holds that registration to the persistence path.
3. **The fit rule was over-constrained** (the ‘too empty’ test could never hold at 0.25) — caught by the new selftest checks before any live run; the empty rule is now a factor-independent 3× and the test band that could never hold was corrected (the rule was right, the test was wrong).

**House-keeping — line endings repaired.** A per-file scan found six files carrying **mixed** endings from earlier writes (config_store.py, api.py, param_registry.py, shell.js, freshness.selftest.js, ofx.selftest.js): the working tree is CRLF by convention (`core.autocrlf=true`; every untouched file checked is 100% CRLF), so all six were normalised to CRLF and verified against HEAD's store. The lesson (detect per file; six files can hide it) is in the skill reference.

**Gates at save.** pytest **1287 passed / 2 skipped** (+6 T5 pins); `audit_ui_refs` **AUDIT CLEAN** (97 modules); ruff (CI pin 0.16.7) clean; **all 30 node selftests pass** (ofx 189); live pass on sandbox 8089 with 0 client errors; sandbox stopped, ports clear.

**Left in Wave A:** **A8** (context-validity menus — right-click offers only actions legal at that point/side/price, disabled ones carrying the why) and **A15** (per-surface set-as-default + factory reset), plus A6's gap-count piece (needs an ingest counter first). Then Wave B/C.

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 133 dirty entries).

---

## §99 — UX study Wave A completed: T6 — context-validity menus (A8) + per-view defaults (A15) (2026-09-18; **nothing committed**)

**The ask:** “im saying the word” — the promised last pair of Wave A. With T6, **every Wave A item has shipped or is honestly deferred** (A6's gap-count piece needs an ingest counter first; it is named below, not faked).

**A8 — context-validity menus.** The Keys menu now evaluates the SAME gate the dispatcher uses: `OFAPKEYS.canDispatch(id)` (run present, armed for danger rows, `when` true) decides whether a row renders as a live command or a disabled row carrying the binding’s own **`why`** (bound specs gained `why`; rendered as the row’s title, so the menu teaches the model by omission instead of swallowing a click). `why` strings were added across the Engine (zooms, nudges, selection actions), Heatmap (rows, window, selection, alert), Replay (play/seek) and paper bindings. The **paper ticket** grew the same honesty: Flatten is disabled with “nothing to flatten — the position is flat and no orders are working” and Cancel-working with “no working orders to cancel” until there is something to act on. Live: with the Engine as the view (classic) the zoom row is enabled; on Overview it is disabled with `title=“acts on the Engine panel”`; the ticket’s two buttons disabled/enabled exactly as the state changed.

**A15 — per-view settings: remember / restore / factory.** The View menu’s long-planned “Reset all view settings” placeholder became the real trio. New read-only **`GET /api/control/config/defaults`** (the reset route writes; this one only answers). `config_store` gained **`VIEW_DEFAULT_MAP`** (which config paths each view’s snapshot covers) and the **`ui.view_defaults`** block — validated in the sanitiser (known views only, known paths only, junk dropped, everything else untouched). The menu’s trio resolves the **live active view** (“This view — settings (heatmap)”): remember snapshots the view’s paths as a deep copy, restore posts them back and adopts the result (freshness windows re-applied, canvases re-measured via relayout), factory fetches the defaults and writes the same subtrees — “engine-side values apply at the next engine start” said out loud. The JS map mirrors the Python map; `test_t6_menus.py` pins the two equal, so a snapshot can never name a path the store would refuse. Live: trio present with the restore row disabled + “nothing remembered for this view yet”; remember stored the full `atlas.heatmap` subtree; a change then restore round-tripped exactly; factory returned the shipped default; the menu closes on action.

**Caught live in T6’s own code:** the trio initially read `state.view`, which only tracks **rail clicks** — a view reached by the palette, the scanner or a script left the menu talking about the wrong panel. It now resolves `.view.active[data-view]` itself (pinned).

**Gates at save.** pytest **1294 passed / 2 skipped** (+7 T6 pins); `audit_ui_refs` **AUDIT CLEAN** (97 modules); ruff (CI pin 0.16.7) clean; **all 30 node selftests pass**; live pass on sandbox 8089 with 0 client errors; sandbox stopped, ports clear.

**Wave A status — complete.** A1–A20: shipped in T1–T6 (T1 help wiring · T2 window/layout trust · T3 safety trio · T4 trust & legibility · T5 canvas craft · T6 context menus + per-view defaults), with **one honest deferral**: A6’s per-symbol gap count has no ingest counter to read — a small Wave B-sized piece, recorded rather than faked.

**Next decision point:** Wave B (the study’s medium items; B1 — modeless settings with tokenised search, Show Original Values, Apply-All/Revert-All — is the study’s single strongest transferable asset, and B8’s template gallery composes with the help corpus). Awaiting his pick.

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 134 dirty entries).

---

## §100 — Wave B begins: B1 — the settings search & staging surface (T7) (2026-09-18; **nothing committed**)

**The ask:** “go b1” — Wave B’s first item, the study’s single strongest transferable asset: Sierra’s modeless settings with tokenised search, Show Original Values, Apply-All / Revert-All and per-field accept/cancel.

**What shipped (new `ui/settings-pro.js`, audit count 97 → 98):** a **Find a setting** card at the top of the Settings view — modeless by construction (a card with inline editors; nothing modal, nothing written until asked). It renders the whole registry (`GET /api/control/params`, **101 settings** browsable) with **tokenised search**: plain words match label + meaning + path + group + unit (so “iceberg” finds the geometry knobs by their meaning), and `group:` / `view:` / `path:` narrow by the registry’s own axes — every token must match. **Show original values** reveals each row’s factory default (changed rows carry an amber dot unconditionally, so what-you-changed is visible without the toggle). Edits are **staged** (“N staged” in the header, amber rows); **✓ writes one field now**, **↺ drops that field’s edit**, **Apply staged** writes every staged path through the same `{path, value}` registry gate the Chart menus use (refusals come back with the reason and stay staged), **Revert staged** clears the lot. Each row carries `path · view`, the scope line — see the scope note below.

**Scope and slots — mapped honestly, not re-invented.** The study’s “explicit scope switch (this surface vs global) with copy-to/from-global” lands on the T6 machinery rather than a second store: the per-row `path · view` line names what a variable drives, and per-surface save/restore lives in **View ▸ This view — settings** (remember / restore / factory). “Saved config slots” is covered by those per-view snapshots plus the R6 storage/backup system; **named slots were not built** — recorded as a candidate rather than faked.

**Live receipts (sandbox 8089, 0 client errors):** 101 rows rendered; `iceberg` → 3 hits by meaning; `group:tape` → 5; `view:heatmap wall` → 1 (axes combine); the defaults chip went hidden → shown with `aria-pressed`; `atlas.heatmap.bucket_ms` 1000 → staged +500 → **Apply → config holds 1500** (“staged changes written”, apply re-disabled); per-field **✓ → 1750**; per-field **↺** and **Revert staged** both cleared staging and restored the field to what the config holds; the scratch config was tidied back to 1000.

**First clean live pass since T3** — no bug in T7’s own code this time. (Two generator-quoting slips while writing the module were caught at compile time; nothing was written.)

**Gates at save.** pytest **1299 passed / 2 skipped** (+5 T7 pins); `audit_ui_refs` **AUDIT CLEAN** (**98 JS modules**); ruff (CI pin 0.16.7) clean; **all 30 node selftests pass**; live pass 0 client errors; sandbox stopped, ports clear.

**Next in Wave B (his pick):** B8 template gallery + starter layouts (composes with the help corpus) · B2 heatmap ramp controls · B3 vertical smoothing · B4 columns rail · B5 the one-table component · B6 instrument lookup overlay · B7 notifications inbox · B9 per-instrument scoping · B10 config artifacts · B11 drag tooltips · B12 markings undo · B13 zoom degradation · B14 UI scale/font zoom · B15 contrast tiers · B16 price-scale object · B17 link-group colours · B18 palette deep-launch.

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 136 dirty entries).

---

## §101 — Wave B: B8 — the template gallery (T8) (2026-09-18; **nothing committed**)

**The ask:** “go b8” — “load a working layout, then mutate it”: boards and tuned settings bundles a newcomer can load in one click, each linked to its help topic (the gallery is the Learn Center’s door).

**What shipped (new `ui/templates.js`, audit count 98 → 99):** a **Start from a template** card injected into the Guide view (the onboarding surface) with **six entries** — three boards (Fast tape board, Context board, Replay study desk) and three settings bundles (Laptop minimal, Colour-blind palettes, Still scales). Non-destructive by construction: a board is POSTed as a **new layout with a client-side id** (`tpl-…`, so the gallery knows what it created), then the shell is asked to switch to it; a settings bundle writes through the same registered `/params` gate the Settings search uses — every value visible in Settings ▸ Find a setting and reversible (View ▸ This view — settings / factory). Each row links its help topic via the T1 `data-helptopic` machinery, and the card’s hint links the Help Centre.

**Pins (`test_t8_templates.py`, 5):** every board rect fits the stored 12×8 grid (x+w ≤ 12, y+h ≤ 8, view slug legal); every board view exists as a panel; **every settings path is in `param_registry.BY_PATH`** (an unregistered path would be refused by the gate — pinned rather than discovered live); every linked topic exists in the help corpus; the catalogue count and the load’s shell contract (`refreshLayouts().then`, result checked, `showView(firstView)` before the switch).

**Two live bugs caught and fixed (both mine, both in the load path):**
1. **The shell resolves layout ids against its own cache.** The direct server-side save left the shell blind, `activateLayout` answered `{ok:false}` — and my `.then` never looked, so the toast claimed a switch that never happened (mode stayed classic). Fixed: refresh the cache first, check the result, fall back to an honest “find it in Layout ▸ Saved layouts” note.
2. **Entering Terminal focuses the CURRENT view, and a view the board does not contain gets appended as a widget** — on a full grid that re-tiles every rect the board came with (live: loading from the Guide added the Guide and tiled the 4-widget board into 5). Fixed: the board’s own first view goes on screen *before* the switch, so Terminal focuses a view that already has a frame. Re-verified live: classic + Guide current → load → **exactly the board’s five views, no foreign widget, no re-tiling**; and in Terminal mode the board’s rects render as stored (chart 663×312 · cvd 327×312 · profile 495×184 · watchlist 495×184).

**Also caught:** an apostrophe inside a single-quoted JS blurb (node --check refused the module before it shipped); a syntax error was “fixed silently” earlier by the generator writing LF into the CRLF file (the T5 mixed-endings trap — 35 bare LF lines found by repr and normalised back to CRLF, 0 remaining).

**Live receipts:** guide card present with 6 rows; board save → `tpl-scout-i6zw` *new* layout (0 → 1, nothing replaced) → activated → mode classic → terminal; settings bundle → `expression.engine.palette` and `expression.chart.palette` theme → **deutan** (restored to theme after); the `work.appearance` help link opened its topic; every scratch layout deleted afterwards (tpl- count back to 0).

**Gates at save.** pytest **1304 passed / 2 skipped** (+5 T8 pins); `audit_ui_refs` **AUDIT CLEAN** (**99 JS modules**); ruff (CI pin 0.16.7) clean; **all 30 node selftests pass**; live pass 0 client errors; sandbox stopped, ports clear.

**Next in Wave B (his pick):** B2 heatmap ramp controls · B3 vertical smoothing · B4 columns rail · B5 the one-table component · B6 instrument lookup overlay · B7 notifications inbox · B9 per-instrument scoping · B10 config artifacts · B11 drag tooltips · B12 markings undo · B13 zoom degradation · B14 UI scale/font zoom · B15 contrast tiers · B16 price-scale object · B17 link-group colours · B18 palette deep-launch.

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 138 dirty entries).

---

## §102 — Wave B: B2 — the heat ramp controls (T9) (2026-09-18; **nothing committed**)

**The ask:** “go” · “b2” · “your call” — Wave B's second item after B8, with design latitude on my side; the study's brief: numeric + percentile cut-offs, a contrast dial, “apply scheme globally”, and data-semantic named schemes (Bookmap/ATAS semantics).

**What shipped (new `ui/ramp.js` + `ramp.selftest.js` — audit count 99 → 101):** one shared heat-scheme vocabulary for **both** heat surfaces — the Engine's depth layer (`ofx.js`) and the Heatmap view (`atlas.js`) — as two control clusters (scheme · contrast · floor · **Apply globally** each), every write through the registered `/params` gate:
* **Named schemes** (the ATAS model — name the meaning, then give it two dials): **Balanced depth** (the shipped recipe — pinned equal to the defaults as values), **Wall hunt** (top 2% saturate · bottom 6% unpainted · gamma 1.35), **Thin-book detail** (12% spread · 0.8), **Quiet book** (bottom 15% unpainted · 1.15). Choosing a scheme writes its dials; a hand-edited dial reads **custom** until a scheme matches again.
* **Ceilings:** the percentile cut-off gains an exact-size sibling (`upper_cutoff_abs`); the backend resolves either into the snapshot's `scale_max` — a pin beats the percentile (the flat guard keeps a low pin from zeroing the map) — so both surfaces saturate alike. Restart semantics proven live below.
* **Floors + contrast:** exact (`heat_floor` / `floor`) or a bottom share of the surface's own matrix (`heat_floor_pct` / `floor_pct`; the larger wins), read at paint time; contrast is a gamma over the ramp position — 1 is the identity, the shipped look to the pixel.
* **Apply globally** broadcasts the dials to the other surface through the same gate (`ofap:heat-scheme` does the adoption).
* **Seven new display variables** registered with bounds (`ofx.heat_contrast/heat_floor/heat_floor_pct` · `atlas.heatmap.upper_cutoff_abs/contrast/floor/floor_pct`), sanitiser-clamped, defaults = the old look. Display-only — nothing touches a value, a feed or the ingest.

**Pins (`test_b2_ramps.py`, 8; `ramp.selftest.js`, 37 checks):** the seven variables registered with bounds + presentation; every scheme dial inside the registered bounds; **`balanced` == the shipped defaults** (a values equality, not a comment); the sanitiser clamps junk back to the shipped look; the absolute ceiling overrides the percentile and un-pins back; the module parses + its selftest runs; all eight controls live in the page and `ramp.js` parses before `atlas.js`; the audit knows the module. Selftest: clamps (`null`/`''` take the fallback — the falsy-zero trap), gamma identity, percentile, floor winner, scheme matching, dotted-path get/set.

**Stumbles in B2's own code (all fixed and re-verified):**
1. `ramp.js`'s first clamp passed `null` through as 0 (`Number(null)` — the falsy-zero trap); the guard is pinned now.
2. The depthmap's snapshot **cache key didn't carry the new absolute ceiling** — its own comment demands that flipping the ceiling takes effect immediately.
3. My test's epoch-0 timestamps hit the depthmap's falsy-zero bucketing — house tests carry a realistic `T0`; fixed.
4. **The repaint path (the pass's one real find).** The scheme handler repainted via a bare `drawHeatmap(A.heat.last)` and could visually stall behind the live refresh in the sandbox; it now goes through the map's **own load path** (`loadHeatmap()` — fetch + paint, the same call the auto refresh makes; a brief force-argument excursion was reverted — the function takes no args). The closing trace proves the path end-to-end: **five `{path,value}` POSTs → a fresh GET → repaint → the scheme note**, canvas signature moving.
5. The pct ceiling entry's `applies: "live"` was a lie (see the restart proof) — now `applies: "restart"`; my own comment citing a `() => loadHeatmap(true)` house deferral that doesn't exist (the flush is heatmap-pro's `pull(true)`) — rewritten to say what the call is. Also fixed on the way: the Engine's ramp select never persisted (`thermal` now stores to `ofx.ramp`).

**A pitfall measured during the live pass:** a headless CDP tab throttles the app's 5-second slow loop to ~1 tick per 2 minutes in bursts while bus-driven polls keep running — a quiet canvas reads as frozen when it is only throttled. One identical-hash readback along the way was a headless flake, contradicted by every other receipt.

**Live receipts (sandbox 8089, scratch APPDATA + a copy of the owner's config; 0 client errors in the whole log; error-collector `[]` across the full exercise pass):** depth live at 76 cols / 8,867 cells / `scale_max 5.991`; **Wall hunt** from the Heatmap → config `{pct 2, contrast 1.35, floor_pct 6}` with the status note verbatim; the floor measured on the real canvas (**Quiet hides 2,678 painted px**); the Engine adopts the scheme (`1.35 / 0 / 6`) with its canvas signature moving (E1≠E2); **broadcast both ways** (Engine global → Heatmap; Heatmap contrast 2.0 + global → the Engine adopts 2.0 and reads custom); ramp `thermal`→`classic` round-trip with persistence; the ceiling/restart proof — write → `applies: "restart"` note → running hub unchanged (`6.05`) → engine restart → **`scale_max 3.0` exactly, pct picked up** — then the tidy revert (dials to defaults → restart → `4.048 / pct 5.0`). Sandbox stopped, ports clear, scratch removed.

**Crash recovery (same day).** The build session crashed at the teardown step — sandbox still up holding its temp files, docs unwritten. The recovery killed the stuck instance (the kill route is now in the skill), removed the scratch tree, re-ran the full battery on the frozen tree — identical numbers — and wrote this record.

**Gates at save.** pytest **1312 passed / 2 skipped** (+8 B2 pins); `audit_ui_refs` **AUDIT CLEAN** (**101 JS modules** — `ramp.js` registered); ruff (CI pin 0.16.7, via `uvx`) clean; **29 node selftests / 0 failures** (`ramp` 37 checks; the long-standing “30” was doc count-drift — 29 files on disk, all green, none ever missing); both goldens green (in-suite); live pass 0 client errors.

**Next in Wave B (his pick):** B3 vertical smoothing · B4 columns rail · B5 the one-table component · B6 instrument lookup overlay · B7 notifications inbox · B9 per-instrument scoping · B10 config artifacts · B11 drag tooltips · B12 markings undo · B13 zoom degradation · B14 UI scale/font zoom · B15 contrast tiers · B16 price-scale object · B17 link-group colours · B18 palette deep-launch.

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, 143 dirty entries).

## §103 — Wave B completed: B3–B18 (T10–T15) (2026-09-18; **nothing committed**)

"go with all the B's" — six packages in one running session, every item display/settings only (no value, feed or ingest path touched), each with its pins, its pure half (node selftest) and live receipts on one sandbox.

**T10 — B3 vertical smoothing · B13 zoom-level candle degrade · B16 the price-scale object.**
- B3: `ramp.js` gains `smoothVector` (kernel blend, constant-preserving) + `smoothDecision` (hysteresis: engage below ~2.5 px rows, release past 4). Applied in the Heatmap paint (columns pre-smoothed) and the Engine's depth heat (per-column cell sizes; ghosts exempt — a memory is not a live reading). New enums `ofx.heat_smooth` / `atlas.heatmap.smooth` (auto|manual|none, default **auto**), selects in both heat clusters.
- B13: `expression.js` gains the sixth mode **candles** (body+wick, direction colour; `chrome.cells:false` is the gate the matrix painter honours). When the zoom drops a column under the text threshold the Engine draws candles instead of the volume-profile fallback — `atlas.ofx.degrade` (default **on**, checkbox beside the bars select), hysteresis in `math.degradeDecision`; HUD reads "LOD: candles — auto-degraded"; the saved mode is untouched.
- B16: the value scale is an object — right-click the price rail for **Auto / Free** (drag the rail itself to move prices; the menu only appears for that zone) / **Reset scales**; Ctrl+Shift+R = reset scales (registered; Keys sheet); `OFX.scales()` for reads.
- Pins `test_b3_b13_b16.py` (9). **Defaults note:** smoothing = auto and degrade = on — one word to flip either.

**T11 — B14 UI scale · B15 contrast tiers · B17 link-group colours.**
- B14: `ui.scale` (0.75–1.5, step .05, default 1) → `--ui-scale` + root `zoom`, applied by theme.js; pre-paint mirror extended; **Ctrl+= / Ctrl+- / Ctrl+0** registered ("Interface"); Appearance card gains the field. Canvases re-fit **synchronously** on a scale change (rAF pass kept for settle) — measured live: backing == round(clientWidth×dpr) at zoom 1, 1.25 and back (headless throttles rAF, so deferred-only left stale backings — the fix and its evidence are in the skill).
- B15: `ui.contrast` calm|standard|aggressive → `data-contrast` + token overrides in atlas.css (calm quiets the chrome, aggressive hardens lines/lifts secondary ink; standard = no overrides). Live receipt: aggressive reads `--of-ink-dim-rgb: 176,190,212`.
- B17: `ui.link_colors` (A–D, #rrggbb clamped) + `links.js` `colorOf/nextColor/setColor/cycleColor`; widget chips colour their group **letters** (the letter always stays — CVD pairing); the link pop gains a Colour row cycling the palette; the SHELL owns the store write — links.js must never reach the network (`test_links.py::test_linking_never_touches_ingest` caught the first draft; the layered fix is the shipped one).
- Pins `test_b14_b15_b17.py` (7); links selftest 12.

**T12 — B18 palette deep-launch · B9 per-instrument scoping · B10 config artifacts.**
- B18: `@TAG` tokens in the palette become **Deep launch** rows — "Open Engine/Heatmap/Chart/Replay/Depth — SYMBOL"; an Engine launch pre-loads `#ofxSymbol` through its own change path. Live: `searchRender('@BTCUSDT')` → cat "Deep launch", five rows, exact copy; the empty-panel hint teaches the syntax.
- B9: per-instrument display scoping — `SCOPED_DISPLAY_PATHS` (12 heat/ramp/degrade paths; the store sanitiser's allow-list held equal with `scopes.js`); last-used wins for a new instrument, the block applies when a known one returns; capture on leave + a debounced fold of `ofap:heat-scheme` broadcasts; palette "Forget this instrument's display settings"; applied blocks re-read via the `ofap:scopes` event on both heat surfaces.
- B10: **configuration artifacts** — `GET /api/control/config/artifact?kind=workspace|studies` + `POST /api/control/config/import`; schema-stamped (`ofap-config` v1), blocks applied whole, refusals readable and touch nothing; Settings gains a Configuration artifacts card (export rides `/export/save`; import is a file input). Live: refusal "this file is not JSON — an artifact is a .json export of the program's own settings."
- Pins `test_b9_b18.py` (6), `test_b10.py` (5 — the routes exercised directly against a tmp config).

**T13 — B11 consequence-preview drag tooltips · B12 markings undo + multi-select.**
- B11: `risk.js` (pure — verdict/text in the paper account's OWN unit): with a position open, the P/L in ticks at the dragged price, size-weighted; flat, an honest distance, labelled as one. The drawings' drag shows a `.risk-chip` at the cursor; the paper ticket prices stop/target as you type (`#ppRisk`). Live: "+2.0 ticks/unit · +4.0 total (size 2)".
- B12: bounded undo (50) over add / remove / multi-remove / clear / move / reshape / text / duplicate — Ctrl+Z, toolbar ↶, context-menu item, shortcut sheet; shift-click multi-select, group move (origin snapshots), Del deletes the whole set in one reversible step, "select all" (▣) in the toolbar; `undoDepth/deleteSelection/selectAll/isSelected` exported.
- Pins `test_b11_b12.py` (4); risk selftest 6.

**T14 — B6 instrument look-up overlay · B7 notifications inbox.**
- B6: `lookup.js` — one overlay over every connection (Bybit catalogue / MT5 broker search / the Alpaca map), groups with honest counters (X shown of Y listed), the last filters in `ui.lookup`, actions Use (the app's own switch) and Enable (the venue-confirmed `/instruments/add`); absences said, not faked ("no Alpaca account is linked…"). Three doors: the Instruments button (the walkthrough stays as the palette fallback), the palette action.
- B7: **Inbox** — new rail view + `inbox.js` + `GET/POST /api/atlas/notifications` (reads the engine's own `AlertEngine.history`; reading state `ui.notifications` {read_ms, dnd, priority}). Tiles with severity stripe, kind, category chips (one category per kind — pinned against the palette's alert-kind list); "priority first" sort; act-on-click marks read and opens the evidence panel; DND silences the badge, never the record; the badge rides the socket dispatcher via the established `atlasOnEvent` chaining. `view.inbox` help topic + corpus view-map row (test_help caught the missing map entry — the coverage contract working).
- Pins `test_b6.py` (3), `test_b7.py` (4).

**T15 — B4 columns rail · B5 the one-table component.**
- B4: `colrail.js` — a rail right of the Map canvas: one row per column with an accumulation (`traded`, or net `resting` Δ) whose **reset semantics are the feature** — manual (button, double-click), scheduled (30 s), conditional (threshold) — each branch pinned in `reduce()`; fed by every fresh snapshot (`OFAPCOLRAIL.observe` beside `drawHeatmap`); dials in `atlas.columns` (registered, clamped). Live: three observed buckets → three rail rows, note "traded since reset · manual".
- B5: `table.js` (OFAPTABLE) — header click sorts (asc→desc→off), right-click header for the column set / group-by / layout reset, drag-reorder ("the dragged header takes the target's slot", `moveColumn` pinned), layout per table id in `ui.tables`. **Adopted on the Watchlist only**, behind `ui.table_component` (palette action toggles; the built-in renderer stays the default). Migrating tape/journal/logs/trackers remains the study's follow-up.
- Pins `test_b4_b5.py` (4); selftests colrail 6, table 5.

**Common threads.** `test_param_registry::test_display_coverage` forced registry entries for the rail's numeric dials; `test_wiring`'s no-raw-colour gate rejected the first inbox CSS (tokens `--of-warn`/`--of-err` instead) — both doors doing exactly what they exist for. Four new selftest files (scopes, risk, colrail, table) take the suite 29 → 33; new modules six (scopes, risk, lookup, inbox, colrail, table) all registered in index.html.

**Live pass (one sandbox; APPDATA-redirected copy of the owner config; port 8089; real config untouched — verified by mtime).** Boot clean, **0 client errors** (the app's own client-error route logged none; window error trap empty). Receipts: all nine modules present; rail + controls in the DOM; contrast tier computed-token check; **canvas law at zoom 1 / 1.25 / 1** (824=824, 581=581, 824=824); links colour set/restore; risk text exact; `@BTCUSDT` → five deep-launch rows; scopes/undo APIs alive; notifications route + inbox view; artifact refusal text; colrail observe → three rows. Sandbox stopped, port cleared, scratch removed.

**Gates at save.** pytest **1354 passed / 2 skipped**; AUDIT CLEAN (all modules); ruff (CI pin 0.16.7 via `uvx`) clean; **33 node selftests / 0 failures**; goldens green in-suite.

**Owed, unchanged.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, **168 dirty entries**). Wave B is complete — the study's remaining flagged follow-ups are B5 migrations (tape/journal/logs/trackers onto the table component) and named config slots.

---

**§104 — the Trader Dale fold-in, Phases 1–2 executed (§3 "level reads": unfinished business + node persistence; nothing committed).**

- **The study + plan.** `docs/TRADERDALE_ORDERFLOW_PLAN.md` — the four-part Order Flow guide plus the linked VP / POC / VWAP guides collated and assessed two-column against the build (22 rows, file:line cites, re-runnable absence greps in §9). **Moddy approved every §8 decision ("go with everything")**; Phases 1–2 are now built; Phases 3 (Area Volume Profile) and 4 (Level Radar) remain per the doc.
- **Phase 1 — detectors (pure, pinned).** New `atlas/unfinished.py` (zero-on-bid / zero-on-ask convention; a magnet resolves when a later bar reaches the level or a tick returns to it — never its own bar; lifecycle `arms`; one-shot `unfinished_from_bars` + `UnfinishedTracker`), `atlas/nodes.py` (consecutive-bar POC runs; events only at the 2/3-bar crossings; `NodeTracker`), `atlas/confluence.py` (level clustering + ranking with adapters for pocs/nodes/unfinished); `atlas/profiles.py` gains `period_pocs()` (week/month aggregates summed from stored `volume_at_price`; POC/VA recomputed on the aggregate with the engine's own rule); `analytics/volume_profile.py` gains `SHAPE_STORIES` / `shape_story()` (every value `_classify_shape` can return has words — source-scanned pin). Pins: `test_unfinished.py` (8), `test_nodes.py` (6), `test_htf_confluence.py` (6).
- **Phase 2 — surfaces.** Hub: `SymbolFeatures` gains `nodes` / `unfinished` (enabled flags, apply_config dials, `clear()`, `status()` counters) and `FeatureHub.feed_bar(symbol, ts_ms, levels, tick_size)` dispatches events through the same `_dispatch` every other detection rides; `main.py._on_candle_closed` feeds each closed footprint bar (guarded — a tracker fault can never take the feed down). Alerts: `KINDS` +2 (`unfinished_business`, `node_zone`), `DEFAULT_RULES` +2 (UI-only, 60 s), `_passes` +2 branches, `_message` +2 sentences; `alert-format.js` catalogue +2 offering exactly the engine's params (the params-equality pin holds both ways). Config: `atlas.unfinished {enabled, max_open, merge_ticks}` + `atlas.nodes {enabled, tol_ticks}` (defaults + sanitiser clamps); config golden regenerated; 5 param-registry entries under a new **Level reads** group. REST: `GET /api/atlas/levels/{symbol}` — the unfinished + nodes snapshots plus confluence over virgin POCs and the week/month POC ladder; an honest note when the symbol has not been fed. The profile route now also serves the **shape story**. UI: `ofx.js` gains `setReads` / `levelReadSegments` / `drawLevelReads` (dashed magnets to the live edge, amber node bands; theme keys `unfinished` + `hvn` so every swatch resolves to the table; two legend rows; `stats().levelReads` for receipts), `ofx-view.js` polls `/api/atlas/levels` and feeds the engine, `atlas.js` shows the Profile shape read. Pins: `test_level_reads.py` (4); ofx selftest 195 → **197**.
- **Found live, fixed live (the pass earning its keep).** The view's new `Promise.all` grab landed out of order against its destructure — `heat` and `reads` swapped, so the panel showed the heatmap's note as its own. Caught on the sandbox, fixed, and proven with served-module markers plus the honest note flowing (`no live readings yet — the level trackers fill while the engine runs`).
- **Live pass (§3 receipts).** Sandbox 8095 (scratch APPDATA, real config untouched): `/api/atlas/levels/BTCUSDT` → the honest no-engine note; `/api/atlas/alert-rules` → both new default rules; served `ofx.js` / `ofx-view.js` sha256 == disk; in a real browser: `OFX.setReads` live, a fed payload → `stats().levelReads {lines:2, bands:1}`, legend 32 rows, notice strip clean, canvas law holds; **0 client errors**; server stopped, port clear, sandbox deleted.
- **Gates at save.** pytest **1378 passed / 2 skipped**; AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing**; goldens green; config golden regenerated (31 factories / 18 majors / 49 instruments).
- **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`). Next per the plan: **Phase 3 — Area Volume Profile** (selection → VP histogram + POC/VA lines + Watch-this-level hand-off), then **Phase 4 — the Level Radar** (level lifecycle across the watchlist), then Phase 5 education.

---

**§105 — the Trader Dale fold-in, Phase 3 executed: the Area Volume Profile + the "Watch this level" hand-off (A3/G3; nothing committed).**

- **What it is.** Box a region on the Engine (the P1-3 shift+drag) → volume-at-price over the box: POC/VAH/VAL lines on the stage, the profile's own numbers and histogram on the strip, one-click "Watch this level", and the Export CSV carries the whole area.
- **Maths (pure, pinned).** `math.areaVolumeProfile` (ofx.js): every drawn ladder row inside `[i0..i1] x [p0..p1]` carries its bid+ask; POC = the heaviest row; the value area is the heaviest rows until `vaPct` of the area's volume is covered — the same rule `math.rowShares` uses per bar, same 0.1–0.95 clamp; `step` = the smallest positive row gap (the watch tolerance bases on it); an empty ladder or empty band returns **null, never zeros**. 11 new pins in `ofx.selftest.js` (197 → **208 ok**).
- **Surfaces.** `OFX.areaProfile()` (cached by selection-seq + vaPct — a repaint storm never re-sums the window); `drawSelection` draws POC solid + VAH/VAL dashed from the theme's own `poc`/`vaEdge` keys, labels just outside the box edge; the strip gains its "area profile" block — POC (+share), VAH/VAL, area volume, row step cells + a dpr-correct histogram canvas painted from the same rows (`paintSelHist`), with honest "no depth rows in this window" wording for degraded feeds; `exportSelection` appends the area section (the three prices + one row per price, `in_va` flagged).
- **The hand-off runs on a new kind — `level_touch`.** `AlertEngine.evaluate_touch` fires on the outside→inside transition only (one per approach, leaving re-arms it, the rule's cooldown still applies, `at_price ± at_tol` inclusive, a rule without a level can never fire). `FeatureHub.on_tick` carries it through the extracted one firing path (`_emit_fired`; `_dispatch` reuses it, so detections and touches record, emit and notify identically). Catalogue entry + `_passes`/`_message` branches; the JS↔engine params-equality and scope pins hold. The Watch button writes `ap-` rules with `at_tol` = 2 × the area's row step (the heatmap's own "two priced steps" default). Pins: `test_level_touch.py` (7 tests).
- **Build-time catch (fail-loud guard earning its keep).** The strip's `const cls` anchor matched twice in ofx-view.js — the write aborted before touching a line; widened to the three-line combo unique to the selection strip. No live defects found this pass. *(Env note: the browser harness had wedged on a locked `bu-default.port`; ~20 stale `browser_harness` processes cleared, daemon restarted — see the handoff note.)*
- **Live receipts (sandbox 8096, scratch APPDATA, real config untouched).** Served `ofx.js` / `ofx-view.js` sha256 == disk; **real demo ladder** (200 bars, 200 level maps) — 7-bar shift-drag selection → profile **128 rows, total 18248, POC 99078.43709, VAH/VAL 99096.71/99039.65, step 0.22436**; strip rendered (`AREA PROFILE 128 rows · VA70 · Watch this level · POC 99078.44 · 3% · VAH/VAL …`); Watch → rule `ap-BTCUSDT-99078_43709-001347` kind `level_touch` `at_tol 0.44872` (= 2 × step), then **DELETE → 200**, list back to the 18 defaults; Export → file in the sandbox exports folder carrying the exact 128 area rows; canvas law holds; **0 client errors**; server stopped, port clear, sandbox deleted. (Firing *at* the level is pinned in pytest through the hub tick path — the sandbox has no tick source, stated plainly.)
- **Gates at save.** pytest **1385 passed / 2 skipped** (+7); AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing** (ofx 208, alert-format 20); config golden untouched (no config change this phase).
- **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, dirty 168 → **182**). Next: **Phase 4 — the Level Radar** (the golden one — level lifecycle across the watchlist, now with `level_touch` as its armed trigger), then Phase 5 education.

---

**§106 — the Trader Dale fold-in, Phase 4 executed: the Level Radar (G1) + the signals-machine widening (U3); nothing committed.**

- **The machine.** New `atlas/radar.py` — one lifecycle over every level source: **armed → approaching → defended / confirmed → spent / failed**. Conventions pinned in `test_radar.py` (13): `tol = tol_ticks × tick` (or the rule's own); the approach band is `approach_mult × tol`; a test ends the tick price leaves ±tol — leaving on the entry side is a hold (`touches++`, `first_test`), the far side is **failed** if it ever held, else **spent**; a big-jump crossing spends without a test; `armed ↔ approaching` falls back silently; live levels expire at `max_age`, spent/failed are kept for `spent_keep` (dim-and-label before they drop); registration merges within half the tighter tolerance — merged sources are the confluence count, and a defense on a 2-source level reads **confirmed**.
- **The wire-in.** `SymbolFeatures` gains `radar` + `last_price`; `hub.on_tick` steps the book and dispatches every transition as a `radar_level` detection (same `_dispatch` pipe as everything); `hub.feed_bar` registers the bar's own magnets and nodes, then sweeps the VWAP band pair and stacked zones; `ap-` watch rules register as `area_poc` levels; `main.py`'s VP rebuild registers the stored profiles' virgin POCs and the week/month POC ladder — the same sources the levels endpoint serves, so endpoint and radar cannot disagree.
- **U3 — the machine's net widens.** `hub.level_hook` (set in `desktop/engine.py`) → `OrderflowSystem._on_radar_level` → `aggregator.set_watching(QualifiedLevel(...))` with `LevelType` widened (NODE / UNFINISHED / VIRGIN_POC / HTF_POC / AREA_POC / VWAP_BAND / STACKED); behind `atlas.radar.feed_signals` (default on); direction = the level's side (below price = support). One level pipeline, not a second machine.
- **Surfaces.** Scanner **Radar column** (+ `radar_armed` / `radar_approaching` / `radar_held` / `radar_score` / `radar_note`; sortable by `radar_score` — the scanner's documented score heuristic untouched); `GET /api/atlas/radar/{symbol}` and `/api/atlas/radar`; new alert kind **`radar_level`** with the `states` set param, a default rule (`radar-held`, defended/confirmed, UI, 60 s) and sentences ("…spent — traded through", "…held — first test"); 6 Settings dials under a new **Level radar** group; catalogue + selftest (alert-format 20 ok).
- **Receipts.** pytest **1398 passed / 2 skipped** (+13); AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing**; config golden regenerated (31/18/49 — unchanged coverage; the atlas block lives outside the factory golden).
- **LIVE (sandbox 8097; scratch APPDATA + a 1,500-candle BTCUSDT sample extracted read-only from the real DB — his DB untouched).** Honest endpoint before any data; watch rule + radar watcher created (ASCII bodies — the MSYS shell mangles a `±` in `curl -d`; the UI's own fetch is unaffected); replay load (candles mode, 1500) → seek 690 → play 500× → the radar traced its first tracked level **armed → approaching → spent — traded through**, re-registered, then genuinely **defended (2 touches)** — **10 plain-sentence firings** in the alert log; Scanner view live: 20 columns with **Radar**, BTCUSDT row reading `0 armed · 0 approaching · 1 held`; served `scanner.js` sha256 == disk; **0 client errors**; replay stopped, server stopped, sandbox deleted. (The defense is replayed market behaviour, not a synthetic prize.)
- **Honest gaps (recorded, not hidden).** Source set v1 = unfinished, node, virgin POC, HTF POC (week/month), area POC, VWAP bands, stacked zones — heatmap **walls** and **big-trade zones** are follow-ups (wall events are event-shaped; better wired deliberately than half-now). The book is in-memory like every tracker — spent/defended persistence across restarts stays a follow-up. U3's live path (engine wiring) is pinned by pytest; the sandbox runs replay-only, so the hook itself wasn't exercised live.
- **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, dirty 182 → **186**). Next: **Phase 5 — education** (U4 help topics + guide step), then the packaging pass on his word.

---

**§107 — the Trader Dale fold-in, Phase 5 executed: the education layer (U4); nothing committed.**

- **What.** A new Help Centre group — **Reading the market** — six topics, one wizard step, and two real screenshots. The fold-in plan's Phases 1–5 are now all executed; only the packaging pass (Phase 6) remains, on his word.
- **The corpus (`help-data.js`).** `method.reading_order` (profile first → pick one level → confirm at it → one test per level; the reversed-order warning), `method.confirmations` (the side convention — aggressive orders show on the side they hit, limits sit on the opposite side of their intent; resting liquidity via walls / refills; absorption; the level-scoping note), `method.first_test` (virgin POCs, "held — first test", spent/failed as context, the second-test break), `method.levels` (every source family and its panel; confluence = the strong read; area-POC shot), `method.radar` (the six states in plain words, the Scanner column, the alerts and the watch hand-off; scanner shot), `method.vwap` (fair value; rotation vs trend; confluence; where in the app). Every relation/action resolves into existing views and kinds — **test_help.py 32/32**.
- **The Guide (`guide.js`).** A "Reading the market (optional)" step spliced in **just before the wizard's own ending** (`WIZ_STEPS.length - 1`) so the earlier runtime splices can never push it out of place; four buttons — Scanner, Engine, and the two topics — the topic buttons ride the app's own `data-helptopic` delegation. It collects and configures nothing.
- **The screenshots.** `help/scanner-radar.png` (125 KB — the Scanner with the Radar column live, radar cell `1 armed · 0 approaching · 0 held`) and `help/area-profile.png` (147 KB — the Engine with a boxed region, POC/VA lines and the area-profile strip), both captured on the sandbox from real replay/demo data. While capturing, two bad frames were caught and redone properly: the first engine capture was **empty** (bars had not polled yet), and the first scanner recapture measured the Radar `th` at **0×0** (a hash navigation had not activated the view) — both recaptured after asserting the state; the final shot places the column at x 890–1077 inside a 1264 px viewport.
- **Gates.** pytest **1398 passed / 2 skipped** (stable on rerun; one anomalous run self-skipped five node-guarded tests — node briefly unresolvable from that python's PATH — recorded, not hidden); AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing**; `test_help.py` **32/32** (coverage contract, unique-keys/checks guards intact).
- **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; **nothing committed** (HEAD `110c568`, dirty 186 → **188**). Remaining follow-ups stand: radar walls / big-trade zones as sources, spent-state persistence, B5 migrations, config slots — and **Phase 6 packaging**, which waits for his word.

---

**§108 — hotfix: the Help search's stale-results crash (`help.js:476`); nothing committed.**

- **Symptom (his screenshots, live).** `module error in help.js:476:43: Uncaught TypeError: Cannot read properties of null (reading 'results')` in the app's error strip.
- **Root cause (reproduced before touching anything).** Clearing the search box calls `runSearch('')`, which nulls `state.results` — but the pane re-rendered **only when a topic was open** (`if (state.open)`). With no topic opened yet, the previous result buttons stayed on screen, still clickable, with the data behind them gone; the click handler read `state.results.results[...]` unguarded → the crash. Live repro: type "radar" → clear the box → click the leftover result → the identical error at `help.js:476:43`.
- **Fix.** The empty-query path now always replaces the pane (last-opened topic, else the start topic); the click handler refuses to read a missing result set — belt and braces, both commented with the live trace. Pre-existing latent bug (this session's edits touched only `help-data.js` / `guide.js`; `help.js` was untouched by Phases 1–5), surfaced by the Help Centre's new heavy use.
- **Pin.** `test_help.py` +1 — `test_clearing_the_search_never_leaves_stale_results_clickable` (source-text gate in the house style): the empty path must replace the pane, the re-render must not be gated on `state.open`, and the handler must guard. → **33/33**.
- **Verified after.** Same repro steps on a cache-disabled reload: **0 stale buttons**, pane replaced, **zero errors**; the normal flow intact — search "radar" → click → opens *"The level radar: armed, held, spent"*. The one `client error` line in the sandbox log is the crash from the deliberate before-fix repro — the app's own reporter working.
- **Gates.** pytest **1399 passed / 2 skipped** (+1); AUDIT CLEAN; ruff (0.16.7) clean; 33 node selftests / 0 failing. Nothing committed (HEAD `110c568`, dirty 188).


---

**§109 — PUSHED: the fold-in and the waves land on the public suite repo; CI red → green.**

- **What.** On his word (“ok now push to github including relevant new screenshots and "Golden Features" explanation”): everything since `110c568` committed and pushed to **`moddy` → ModdySwag/ModFlow-OrderFlow-Analysis-Suite master** — commit **`91f337c`**, 205 files, +33,510 / −495 (waves A–B, the Trader Dale fold-in Phases 1–5, the §108 hotfix, the help screenshots). Staged after a junk sweep: the 2-byte `mt5_fetched.json` stray went to `.gitignore`; worktree clean after.
- **Docs + shots for the push.** New **`docs/GOLDEN_FEATURES.md`** (the three golden reads — the level radar lifecycle, the area volume profile, unfinished business + node persistence — plus the reading order and the education layer); the README gains a **Golden Features** section (ToC + a table of the two shots); counts re-derived: tests badge **1400**, code **~84k**, API **180 routes** (107 desktop + 56 atlas + 17 dashboard decorators), “thirty-two screenshots”, Help Centre **81 topics** (the old caption's 68 was stale). `docs/SCREENSHOTS.md` +2 rows. Both shots re-captured at **1920×1080** into `docs/screenshots/` — `level-radar.png` (199 KB; the Scanner's Radar column live at x 1078–1319, cell `0 armed · 0 approaching · 1 held`) and `area-volume-profile.png` (149 KB; a boxed 317-row profile, POC 99469.76). Raw-URL receipt: downloaded from GitHub, sha256 == disk.
- **CI round 1 (both jobs red — and the previous head was red too).** (a) The **P2-3 frame-yield flake** — `ofx selftest: 207 ok, 1 failed — “the next frame finishes the deferred layers and clears their flags” [false,true,1]`: the checks burned REAL time to cross the 6 ms share, and on a loaded runner a second stub layer crosses it too, deferring one frame further out (the pre-push `110c568` run was red on exactly this). (b) **`test_dll_endpoint_reports_the_shipped_bridge`** asserted `ok=True`, which is only true on a machine whose NinjaTrader AddOns state holds the bridge sources; on CI the honest verdict is the “copy it into AddOns” one. The push also exposed that `sources.exists/complete` had always been False: the .cs files ship under `ninjatrader_bridge/src/` but the state checked the folder root (masked locally by the AddOns copies).
- **Fix commit `0bd9836`** (5 files). The NT API test now stubs `detect_installs` and pins BOTH verdicts (no platform → the copy instruction with the DLL's own facts intact; sources in AddOns → ok with the one-time compile step). `platforms.ninjatrader_bridge_state` resolves `sources` under `src/` at call time — so `test_platforms`' `ADDON_DIR` monkeypatches still redirect the whole picture. The P2-3 block drives `performance.now()` from a fake clock (the “slow” layer advances it 7.5 ms past the share — deterministic on any runner), restored after the block.
- **CI round 2: GREEN** — run `35293195447`: `test (3.11)` and `test (3.12)` both success. Local gates: pytest **1400 passed / 2 skipped**; ofx selftest **208 ok / 0 failed, 15/15 reruns**; AUDIT CLEAN; ruff (0.16.7) clean; 33/33 selftests.
- **Ops receipts.** `git push moddy master` rides the gh credential helper. **`gh run view`/`gh api` here must carry `--repo ModdySwag/ModFlow-OrderFlow-Analysis-Suite`** — without it gh resolves the directory's `origin`, which is upstream `mahmoud20138/OrderFlow-Analysis-Pro`, and 404s (`gh run list` printed nothing while the api saw the runs; use the api).
- **Owed.** `dist/` · zip · SBOM · installer **still NOT rebuilt** (Phase 6 — on his word). Follow-ups stand: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.

---

**§110 — the packaging pass executed: dist · zip · SBOM · installer rebuilt on the full fold-in payload; journey green.**

- **Frozen build.** `scripts/build_exe.py` (onedir) — `dist/ModFlowOrderFlowAnalysisSuite/` **600 files**, exe **15,536,784 B** sha256 `e83f579b…` (was 565 files / 15,020,151 B at §79–81; the fold-in grew the payload), build printed “built … (14.8 MB)”.
- **Frozen smoke: 18/18** (scratch APPDATA, headless; reusable script `profiles/deepseek/runtime/ofap_smoke.py`): healthz 200; `/api/candles/BTCUSDT` 200 / 1440 rows; unknown → `[]` on `/api/footprint/<sym>` + `/api/tape/<sym>`; hostile Host 403; `/api/control/sources` 7 venues; **fold-in inside** — `/api/atlas/radar/BTCUSDT` answers AND the served help corpus carries `method.radar` + `method.reading_order`; **asset parity 73/73** shell refs byte-identical (the shell mounts ui at `/desktop/` and `dashboard/static` at `/static/`); **11/11 help PNGs** + `help-data.js`/`help-search.js`/`help.js` byte-identical; `/api/control/help` with `app.frozen = true` + the check block; WS native 101 / cross-origin 403; frozen log 0 client errors. Battery URL lessons: routes are **symbol-in-path** (`/api/candles/{symbol}`), and the authoritative list is the app's own `/openapi.json`.
- **Zip.** `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` — **600 entries** (old layout mirrored: exe + `_internal/…` at the root, deflated), **40,830,501 B** sha256 `f11450d7…`.
- **SBOM.** `uv export --frozen --format cyclonedx1.5 --extra mt5` → `…win64.sbom.cdx.json`, **448,822 B** sha256 `8c3c0683…`, **45 components** (metatrader5 + numpy present) — byte count identical to §81's because the lockfile has not moved.
- **Installer.** `make_installer.ps1` under the 32-bit host PowerShell — **0 errors / 4 warnings** (the known set), setup.exe → `dist/…-Setup-0.1.0.exe` **41,759,968 B** sha256 `76F53EAD…`; `installer/ModFlowOrderFlowAnalysisSuite.ism` regenerated (the only tracked file the run changes). The script does **not** touch `installer/README.md` — its “Latest build” line was refreshed by hand with these numbers + a second dated journey paragraph.
- **Setup journey (clean, reusable `profiles/deepseek/runtime/ofap_journey.ps1`).** silent install exit 0 → **600/600 files**, installed exe sha == dist exe → desktop shortcut created → installed app headless on 8097: healthz 200, `/api/candles/BTCUSDT` 200 / 173,439 B, UNKNOWNXYZ `[]` → ARP found in `HKLM\SOFTWARE\WOW6432Node\…\Uninstall\{FA4E31A6-840E-4581-A1E0-4C950A96E0FD}` → silent uninstall exit 0 → install dir gone, shortcut gone, **ARP 0 left**, `%APPDATA%` untouched → the machine's dev shortcut restored from the backup. Journey-script lessons: use **direct** `Start-Process $setup '/s','/v"/qn"'` (the `cmd /c` form mangles quoting → exit 1 while the MSI log shows a healthy install), and **PS 5.1 reads UTF-8 as ANSI** — one non-ASCII glyph inside a string breaks the whole file (ASCII-only, comments included).
- **Not done (deliberately).** No tag, no GitHub release: that is the release cut, which awaits his word (tag `v0.1.0-beta` with zip + Setup + SBOM as assets).

---

**§111 — the release cut: v0.1.0-beta published (prerelease) in the private lane with zip + Setup + SBOM.**

- **Lane.** `ModdySwag/ModFlow-beta-builds` (private; created §81 for exactly this, empty until now) — seeded with a README (first commit `4d6135ff…`), default branch `main`.
- **Cut.** `gh release create v0.1.0-beta --target main --prerelease` with the three dist artefacts and hand-written notes (natural voice: what the suite is, what this build adds, install/good-to-know, the sha256 of each asset, source commit `0123cc1`, the sign-off). URL: **https://github.com/ModdySwag/ModFlow-beta-builds/releases/tag/v0.1.0-beta** — published 2026-09-18T01:18:07Z.
- **Verified from GitHub's side.** Asset `digest` fields read back == local sha256s (Setup `76f53ead…` 41,759,968 B; zip `f11450d7…` 40,830,501 B; SBOM `8c3c0683…` 448,822 B; all `state: uploaded`, not draft); the SBOM was **downloaded from the release and re-hashed** — match. Tag ref `v0.1.0-beta` → `4d6135ff…`.
- **Deliberate.** No tag on the public source repo (the lane carries the release; the notes name the commit). **Owed:** invite the beta testers as **Read collaborators** on the lane — his call, no names on record.

---

**§112 — the third CI-only flake, fixed at the root: the websocket never-drop test's drain budget raced the Windows timer tick.**

- **Symptom.** The docs-only commit `1112b5e` (code identical to the green `0123cc1`) went red on the **3.11 job only**: `test_websocket_backpressure.py::test_a_signal_is_never_dropped_for_a_slow_client` — “every signal arrived, in order”.
- **Root cause (measured, not guessed).** The test drains 296 signals through a fake socket whose 1 ms writes are, on Windows, stretched to the platform timer tick (~15.6 ms): the drain measures **4.10 s** on this machine (`--durations`) against a **5 s** deadline — ~20% headroom, crossed on a loaded runner. The never-drop path itself was never implicated (`dropped == 0` held).
- **Fix.** The budget is now a **30 s hang guard** with a comment explaining the tick; the assertion is untouched — every signal, in order, or the test fails. File green 4× locally (durations confirm the 4.1 s drain); full suite **1400/2**.
- **Pattern note.** Third of the same class this session (P2-3 real-time yield checks → fake clock; the NT bridge test → machine-independent stub; this one → a budget that stopped racing the platform timer). All three were real-time or machine-state dependence in the TEST, never the code under test.

---

**§113 — the private lane is gone: ModFlow-beta-builds made public, tester-gating wording removed, anonymous downloads verified.**

- **His word:** “remove all blocks for private testers/users on github and make evrything public.”
- **The flip.** `gh repo edit ModdySwag/ModFlow-beta-builds --visibility public --accept-visibility-change-consequences`. No pending invitations existed; the only collaborator was the owner. Read back: `visibility: public, private: false` — and an **anonymous** API call (no token) sees it as public.
- **De-gated the copy.** Repo description and README drop “for invited testers” (README commit `1214a606…`: “Make the lane public: drop the tester-gating wording”); the floor of the README now says feedback goes through the main repository. The release notes never carried gating wording.
- **Anonymous receipts (no auth at all).** The release `v0.1.0-beta` fetched anonymously — `prerelease: true` (kept; it is a beta), `draft: false`, all three assets `uploaded`. **SBOM downloaded anonymously → sha256 == local** (`8c3c0683…`); **Setup downloaded anonymously (41,759,968 B) → sha256 == local** (`76f53ead…`).
- **Owed (resolved).** The “invite testers as Read collaborators” item is obsolete — the lane is open to anyone. Everything the product publishes on GitHub is public: the suite repo (source, docs, releases-of-record) and this binaries lane.

---

**§114 — freeze-on-hover removed (owner's call, after measurement), SEC-14 label shipped, three boot-blocking wave defects + one build regression fixed, and the owed rebuild chain completed.** (2026-09-19; **nothing committed**)

- **The ask → the verdict.** The built-in "frozen" was T4/A7 freeze-on-hover: hovering the four canvas sections (heatmap / ofx / profile / cvd) suspended that view's repaint with a "frozen — move away to resume" chip. Verdict after measurement: not necessary — removed. The freeze *capability* stays, explicit: `P`/topbar chip (queues + replays) and the §89 per-surface chips are untouched and re-verified.
- **Why it went (measured live, headless on a scratch profile, real market data).** With the pointer on the map the canvas hash stayed byte-identical for 6.5 s while the feed's newest bucket advanced (stale decision surface under the cursor); a heatmap box-select drag painted **0 ink** while hovering vs **52,887** with the guard off (same drag, same data) — the selection did not appear until the pointer left the panel; the Engine pan painted nothing mid-drag while its shift-select (a different paint path) did. Two freeze semantics in one surface, the silent one on the pointer.
- **Removal shape.** `ui/freeze.js` deleted; script tag, both `atlas.js` guards, `heatmap-pro.js` guard, `ofx.js` tick guard, `modules.css` rules, and the A7 pin test all removed together. Suite delta **1455 → 1454** (the removed pin). Served `freeze.js` now **404s**; 0 client errors; hover shows no chip; canvases repaint under the pointer (heatmap hash changed while entered; box-select **0 → 40,515 ink**; OFX pan hash moved mid-drag). Explicit holds re-verified live: P chip toggles, view held while the feed advanced, resume repaints.
- **SEC-14 (derived profiles) closed.** `compute_from_candles` counts footprint-less candles (the even-smear fallback), `merge_profiles` carries the sum; the count is a real DB column (legacy files get it via a `connect()` migration — `CREATE TABLE IF NOT EXISTS` never alters), rides the ws broadcast and the `/api/atlas/profile` route, and shows in the Profile view as a "Profile basis" line: **derived — N footprint-less candles, volume spread evenly, not a measured distribution**. Pinned in `test_security_fixes.py` (builder, merge, DB round trip, route + UI text). Live receipt on scratch: 7 → label shown; 0 → hidden.
- **Three wave defects found by booting the app — the four gates were green through all three.** (a) `InstrumentPipeline.stats` read a system-level `self.mt5_feed` → `/api/control/bootstrap` AND `/engine/status` **500 for any running engine** (the UI came up with an empty instrument list); the misplaced key is dropped with a comment (the counters live in `live_status()`'s `quality`). (b) a WIP edit hoisted `const flat` inside a block while `RP.floorValue(flat, …)` still read it → ReferenceError on **every** heatmap paint (swallowed by the loader's catch — the map never drew a pixel); fixed with a lazy `sizes()` that keeps the PF-02 no-rebuild intent. (c) `storage.validate_target` (SEC-30) called `os.path.expandvars` with **no `import os`** → ruff F821 + NameError on the backup path; refusals verified (`C:\`, `C:\Windows\Temp`, `C:\ProgramData\x`, relative → refused; user paths pass).
- **A build regression caught only by verifying the ARTIFACT.** The frozen payload silently lost **numpy**: nothing in the tree imports it any more (by design), so PyInstaller's graph stopped reaching it — while `build_exe.py`'s comment and `test_platforms` ("not excluded") still promised it. The frozen app answered `capabilities.mt5 = "MetaTrader5 package not installed"` **with `MetaTrader5/` sitting in `_internal`**. Fix: explicit `"--collect-all", "numpy"` + the pin strengthened to assert the positive flag. Rebuilt: exe **16,019,370 B** (was 12,375,538 without numpy), frozen capability **`available: true`**.
- **Rebuild chain (the owed set), all re-run on the final tree.** exe → **payload check 175/175 byte-identical**, no tree file newer than the exe, `freeze.js` absent, numpy + MetaTrader5 present → zip **1,716 entries (1,496 files)**, namelist == dist set, `testzip` OK, extract + re-hash **0/1,496 different** → SBOM `uv export --frozen --format cyclonedx1.5 --extra mt5` (**45 components; numpy + metatrader5 covered**) → Setup via ISCC (**0 errors**, WebView2 bootstrapper verified). Frozen probes (8097, scratch APPDATA): healthz 200 · hostile `Host` 403 (healthz + bootstrap) · cross-site POST 403 · native POST 200 · `/desktop` byte-identical to the packaged `index.html` + CSP · `freeze.js` 404 · 0 organic client errors. Installer journey **11/11**: 1,498 files, installed exe hash == dist, ARP + Start Menu fully cleaned, `%APPDATA%` intact, the machine's dev desktop shortcut **hash unchanged** (`03b7b960…`). Hashes recorded in `docs/RELEASE_EVIDENCE_v0.1.0-beta.md` (exe `a35c9f60…`, zip `71b0b5c2…`, Setup `3FA88161…`, SBOM `b955acc2…`; BUILD_INFO commit `45172b1`, worktree `dirty`, Python 3.12.14).
- **Gates.** pytest **1455 / 3 skipped**; AUDIT CLEAN; ruff clean; **33/33** node selftests; `node --check` on every edited module.
- **Still open, deliberately untouched (reported, not silently skipped):** SEC-08 (CSP nonce would require redesigning the user-expression feature that needs `'unsafe-eval'`), SEC-09 (masked config reads — a read/write protocol change across API + UI), SEC-32 (needs the notices commit + licence texts in the build + the repo licence field) — all weeks-tier, non-blockers by the audit's own ranking. **Commit/publish: not done** (his review gate).
- **Nothing committed** — HEAD `45172b1`, worktree dirty (~100 files); docs/SESSION_HANDOFF/RESUME history left intact; the durable lessons live in the `orderflow-app-ops` skill (`references/boot-check-and-harness.md`).

---

**§115 — the audit's three "weeks"-tier items attended on his word: SEC-08 (CSP), SEC-09 (write-only credentials), SEC-32 (licence disclosure) — and the artefacts rebuilt over the hardened tree.** (2026-09-19; **nothing committed**)

- **SEC-08 · the shell's CSP no longer allows arbitrary inline script.** `script-src` went from `'self' 'unsafe-inline' 'unsafe-eval'` to **`'self' 'sha256-KK54MqkYnU6k/djgxPR/Rj2KkgC9wjFztAF+efLlY7g=' 'unsafe-eval'`** — the one inline block (the pre-paint appearance mirror) is allowed by **hash**, not by class. That is the audit's exploit step gone: an injected inline script has no policy path to run. Live receipt on the **frozen** app: it re-computes the hash from its own served bytes (`crypto.subtle`) — `policyAllows: true`, `unsafeInlineInScriptSrc: false` — and **0 `securitypolicyviolation` events** while driving settings → overview → engine → heatmap.
- **SEC-08 · what stays, and why (not silently).** `'unsafe-eval'` remains **deliberately**: the Studies view executes user-authored JavaScript by design (`study-api.js` compiles each pasted module with the `Function` constructor; `atlas-v2.js` lazily loads it). Removing it means redesigning that feature, not tightening a header — it is documented in the CSP comment and the SEC-08 pin fails the day someone drops the flag without that redesign. `style-src 'unsafe-inline'` stays too: 66 style attributes + 2 inline blocks, paint-only, and CSP hashes cannot cover attributes.
- **SEC-08 · pins.** New test (`test_security_fixes`): no `'unsafe-inline'` in script-src; the hash **recomputed from the file** matches the policy exactly (CRLF→LF, the parser's normalisation); the eval flag present. `test_wiring`'s CSP pin updated to the new directive set (it hard-coded the old one — intended change, pin moved with it). Adjacent finding, left alone: `dashboard/static/index.html` (121 lines) is reachable via `/static/index.html`, carries **no CSP** and an `unpkg.com` script; unreferenced by the app (root 307s to `/desktop`) — flagged for a cleanup pass rather than half-fixed.
- **SEC-09 · credentials are write-only over the control API (the config_store comment's promise is now true in code).** `config_store` gains `SECRET_MASK` (8 bullets), `SECRET_PATHS` (telegram bot token · notify email password · Sierra DTC password · Alpaca key id + secret · MT5 password), `mask_secrets()`, `unmask_patch()` and `secret_or_stored()`. `GET /api/control/config` and `/bootstrap` return the mask; **a mask posted back on a write means "unchanged"** (`merge_config` restores the stored value before merging); `""` clears; a typed value replaces. `/telegram/test` and `/alpaca/test` treat a masked/blank field as "test the stored credential" instead of posting bullets to the provider. `SECURITY.md` states the protocol (SEC-38's copy-to-behaviour mismatch resolved — the guide's "never displayed back" claim is finally accurate).
- **SEC-09 · receipts, source and frozen.** Source scratch: all six read masked (`chat_id` stays plain — an identifier, not a credential); masked write → secret kept + the carried change applied; empty → cleared; real → replaced. **Frozen app:** served masked; the **wizard's exact flow** (GET the whole config → POST it straight back) → 200 with `config.json` **byte-identical**, no mask on disk; settings field shows the mask; the Telegram pill still reads "configured — switch off".
- **SEC-32 · three parts, all closed.** (1) the extended `THIRD_PARTY_NOTICES.md` is in the worktree (51 lines vs 22 at HEAD; pending his commit); (2) **the licence TEXTS now travel in the build** — new `collect_licences()` in `build_exe.py` copies every bundled distribution's licence files (its dist-info `licenses/` tree + `LICENSE`/`COPYING`/`NOTICE` records) to `_internal/THIRD_PARTY_LICENCES/<dist>/` and drops `LICENSE` + `THIRD_PARTY_NOTICES.md` beside the exe — **62 files from 19 distributions** (the audit counted **9 dirs for 21 bundled modules**); pinned functionally in `test_platforms` (fake payload + fake site-packages: licences copied, `RECORD` not copied, README written) and spot-asserted in the payload check (`aiohttp`/`certifi`/`yarl`); (3) **the binaries lane carries the licence** — `ModdySwag/ModFlow-beta-builds` got the MIT `LICENSE` (commit `c8af9571…`); GitHub `licenseInfo` now detects **MIT**, and the raw file fetched back from the lane hashes **== the source repo's `LICENSE`** (`889a289a05d27036…`).
- **Rebuild chain, third full cycle on the hardened tree.** exe **16,020,993 B** `3634ab0d…` → payload 175/175 byte-identical, 0 newer, `freeze.js` absent, numpy + MetaTrader5 present, licence tree **185 entries** → zip **1,904 entries (1,561 files)** `92238aa7…`, sets == dist, `testzip` clean, extract+re-hash 0 diffs → SBOM **45 components** (numpy + metatrader5 covered) `594872dc…` → Setup **38,928,756 B** `432b5e5c…` (ISCC 0 errors) → journey **11/11** (installed **1,563 files** — +65 = 62 licence files + `LICENSE` + notices + README; installed hash == dist; ARP + Start Menu fully cleaned; `%APPDATA%` intact; the dev desktop shortcut hash unchanged `03b7b960…`). Frozen probes **now assert the CSP** (`csp_has_hash: true`, `csp_no_unsafe_inline: true`) plus the standing battery (hostile `Host` 403 ×2, cross-site POST 403, native POST 200, `/desktop` byte-identical + header, `freeze.js` 404, MT5 `available: true`, 0 organic client errors — the 3 log lines are the probe's own markers).
- **Gates.** pytest **1458 / 3 skipped / 0 failed** (1455 → +3, exactly the new SEC-08/09/32 pins); AUDIT CLEAN; ruff clean; **33/33** node selftests. HEAD `45172b1`, worktree dirty, **nothing committed**.
- **Audit status now.** SEC-08 **closed** (inline half; the eval half is a documented feature-design dependency with a tripwire test), SEC-09 **closed**, SEC-32 **closed** (notices pending his commit; texts shipped; lane licence live). Owed: **commit/publish on his word** + the standing follow-ups (radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots).

---

**§116 — Profiles: the switchable-playbook system (his ask: "a profile handling module … industry-leading for an order-flow platform"), and the source-install fix for the reported `.venv is not recognized` error.** (2026-09-19; **nothing committed**)

- **What a profile is.** A named bundle of the 13 analysis blocks (`config_store.PROFILE_BLOCKS`): feed, instruments, atlas/ofx/studies/expression, UI+theme, layouts+workspaces, watchlist, risk, audio, calendar. **Never credentials, machine paths or network settings** — capture reads only the whitelist, so an exported profile is shareable by construction (pinned by value against the SEC-09 secret paths). `data_source`/`instruments`/`atlas`/`ofx` are the `PROFILE_RESTART_BLOCKS`: the switch preview says they land on the next engine start, the same wording the settings view already uses.
- **Lifecycle** (`desktop/profiles.py` + `GET/POST /api/control/profiles`, 12 actions): save (from current or factory defaults, optional block subset) · **preview** (dry-run: exactly which blocks change, restart split) · apply (replace semantics through `save_config`, stats + active-clock updated) · update-from-current (banks the old snapshot in a version ring — a delete also pushes one, layouts' T2 pattern) · rename · duplicate · delete · restore_version · default + auto_apply · rules · export/import. The store's sanitiser stays the authority: every response carries the state the store ACCEPTED.
- **Metrics & integration.** Per-profile stats: times applied, last applied, accumulated **time in play** (banked on every switch incl. boot), **trades journaled under the playbook** (new `trade_journal.profile_id` column, one-statement migration on connect, both insert paths tag it — the paper-close path reads `profiles.active`; `_journal_rows` falls back to `'' AS profile_id` so a legacy DB never blanks the journal). Live drift: the active profile reports **dirty/dirty_blocks**, surfaced as a card chip and a `●` nav badge. Boot: `launcher.main` applies the default profile via `boot_apply()` **before serving**, so the first `/bootstrap` already reflects it.
- **UI.** New rail view **Profiles** (nav before Settings), `ui/profiles.js` (~390 lines): cards with active/startup/drifted chips + block-chip rows, Switch… preview card (changed blocks + engine-restart warning) → Apply (toast + reload — a switch can change the layout/theme/instruments the shell booted with), Update from current, Rename/Duplicate/Export(→`/export/save`)/Delete (two-click confirm), startup selector + apply-at-launch, and the **auto-switch rules** editor: feed bindings (source wins) + clock windows with day masks (overnight windows wrap; `[from, to)` exact — all pinned in `profiles.selftest.js`, 7 checks). Alt+P opens the view; guide tooltip + help topic `view.profiles` shipped. No inline handlers anywhere (the SEC-08 hash remains the only inline block).
- **Two real bugs the build caught in itself.** (a) `{"ok": False, …, **state()}` — the spread overwrote `ok` with state's `True`, so twelve error returns claimed success; reordered at all 17 sites + both routes (the import-junk test caught it). (b) "Dirty" originally only existed for the active profile, which made a freshly saved profile blind to drift — saving now makes the profile the ACTIVE playbook (clock starts, `applied` counts switches not saves), which is also what makes the save→drift→update story coherent.
- **Tests.** `test_profiles.py` **18**: the two promises (capture can never carry a credential; a switch replaces only carried blocks — token+chat_id+port survive), dirty/preview/apply round trip, restart split, version ring + restore, rename/duplicate/delete (+pointer clearing), boot auto-apply, active-time banked across switches, rules clamp + die-with-target, scoped saves, from-defaults, export/import (+junk rejection), sanitiser caps (60 items → 40; over-size block dropped; `telegram` inside a raw snapshot dropped), route round trip on the real app, and the journal-column legacy migration. Plus `test_install_bootstrap.py` **5** (below). Suite **1458 → 1476 → 1481**.
- **Live receipts (scratch 8093, real UI).** Saved "London FX" through the view → card with tags/stat line/7 block chips; changed `atlas.heatmap.bucket_ms` → **drifted** chip + nav badge; Switch… preview: "this switch changes 1 block: analysis" + the engine-restart banner; Apply → reload → bucket back to the profile's value (1234 → 1000), stats `applied 1×`, `dirty false`; Export via UI → `profile-London_FX.json` in the exports folder with **zero credential-shaped keys** and exactly the 13 whitelist blocks; **0 securitypolicyviolation events**; Alt+P registered. Frozen app (8097): `profiles` GET/save/preview/delete all 200-true, `profiles.js` served, CSP hash assertions still green.
- **The install fix (his second ask).** Root cause of the reported error: the published README's quick start used a POSIX-style path — `.venv/Scripts/activate` — and `cmd.exe` reads that as a program named `.venv` (its error is exactly `'.venv' is not recognized as an internal or external command`). PowerShell hits the sibling class (script policy). The fix, all in the worktree:
  - **`install.cmd` + `run.cmd`** at the repo root: one command each, **no activation step at all** (they call `.venv\Scripts\python.exe` by full path), safe to re-run, `py -3`/`python` probing with a friendly no-Python branch pointing at python.org **and** the ready-built installer lane, arguments pass through (`run.cmd --headless --port 8099`). Verified for real: run in a clean copy of the tree (no `.venv`) — creates the venv, installs `.[dev]`, and the app boots from it.
  - **README Installation rewritten**: **installer-first** ("Easiest — the ready-built installer (no Python needed)", linking the Setup on the beta lane), then "From source — clone, one command, run", a manual **per-shell activation table** (cmd.exe `.venv\Scripts\activate.bat` · PowerShell `.\.venv\Scripts\Activate.ps1` + policy note · Git Bash `source …` · no-activation row), and a troubleshooting section that names the **exact reported error**, explains the cause, and gives both fixes — plus the `python is not recognized` sibling. Pinned by `test_install_bootstrap.py` (5 tests: script shape, CRLF, no-activation invariant, table rows, installer-first ordering, and "the bare POSIX line must never appear as a Windows instruction again").
  - **Known gap, stated:** the public GitHub page still shows the old commands until the README + scripts are committed/pushed — that is his gate; the rebuilt **Setup exe is the upload candidate** for the beta lane.
  - **Batch lesson (recorded):** a nested `( … )` block containing `(3,11)` inside quotes *and* an echo with an unquoted `(` inside a block both make cmd die with ": was unexpected at this time" — `install.cmd` is deliberately flat (labels, no nested blocks, no parens-in-echo).
- **Rebuild chain on the final tree.** exe **16,041,731 B** `0cce8602…` → payload **177 pairs, 0 missing/mismatch**, `freeze.js` absent, numpy+MT5 present, licence tree 185 entries (62 files/19 dists) → zip **45,045,959 B** `b0670d36…` (sets == dist, extract+rehash 0 diffs, 1,562 files) → SBOM 45 components `2aeb2db b…` → Setup **38,955,478 B** `bb971599…` (ISCC 0 errors) → journey **11/11** (1,564 files; installed hash == dist; ARP/Start Menu cleaned; `%APPDATA%` intact; dev shortcut `03b7b960…` unchanged). Frozen probes: full battery + profiles route round trip green.
- **Gates.** pytest **1481 / 3 skipped / 0 failed**; AUDIT CLEAN; ruff clean; **34/34** node selftests (profiles.selftest included). One observed one-off: `test_hyperliquid_feed` failed once mid-session, its file passes 27/27 and two subsequent full runs were clean — watch it, don't chase it (yet).
- **Owed.** **Commit/publish** (his review gate; drafts first). Standing follow-ups unchanged. HEAD `45172b1`, worktree dirty, nothing committed.

---

**§117 — The competitive audit, attended: per-view pause completed · user-rebindable shortcuts with conflict refusal · study collections · the identity copy. (2026-09-19; nothing committed, live-verified)**

- **The audit first, the diff second — because the audit had been read against a stale inventory.** `Desktop/audit.txt` condenses `docs/COMPETITIVE_REANALYSIS_2026-09-19.md`, whose ModFlow section was written from `docs/ux-study/modflow_inventory.md` (a snapshot), not the tree. Against `45172b1` + this worktree, the headline "gaps" were largely already built: **terminal layouts** (named arrangements, tabs/widgets, per-screen keys, save/save-as/duplicate/delete/reset/export/import/versions/restore + a layout lock; `GET/POST /api/control/layouts`; Layout menu; boot adoption), **profiles** (the playbook store, §116), **link groups A–D** with symbol+timeframe membership and config'd colours (`ui/links.js`, chips via `shell.paintLinkChip`), the **one-registry shortcut map** + sheet + Keys menu (§43/§92) and the **heat-ramp controls** (§102: schemes, percentile/exact ceilings, floors, contrast, apply-globally). The item-by-item diff with receipts is `docs/COMPETITIVE_AUDIT_DIFF.md`; the rest of this entry is what was genuinely missing and is now built.
- **Per-view pause completed (the §89/F6 remainder).** Heatmap, CVD, Profile and Frames gained the same `Pause` chip their ten siblings carry, and their paint paths now consult the arbiter: `loadHeatmap`/`loadCvd`/`loadMarketProfile`/`loadFrames` defer via `deferKeyed(surface, 'snap', …)` while held and snap current once on resume; the shared CVD/tape channel's paint is deferred too (the channel never stops — only the paint waits). `test_pause_surfaces.py`'s WIRED map names all four (heatmap pinned against BOTH its overlay and the map's own loader). Live on the sandbox: click → `held true`, the deferred counter rises and the loader queues; resume → flush, chip face repaints (rAF-scheduled, read after a frame).
- **User-rebindable shortcuts + conflict refusal (the audit's "Hot Keys panel" remainder).** New `ui.keys` config block (`{version, overrides}`) whose sanitiser **rebuilds** the block on every save — that is what lets a reset actually remove a stored chord, since a deep merge cannot drop a key; `keys.js` gains `keysFor · applyOverrides · rebind · clearOverride · clearAllOverrides · overrides · conflicts` (the pure half pinned by 8 new selftest checks — keys 57/0); the hotkey sheet's dispatched rows carry **Change / Reset** and the header **Reset all**; the capture listener runs in the **capture phase** so an armed capture never reaches the dispatcher (and `test_keys.py`'s migrated-modules contract was taught the difference — bubble-phase binds still fail it; `test_listener_balance.py` carries menu.js 4/0 with its reason); boot applies the saved overrides (`ui.js`), and a Menubar Keys row ("Change a shortcut…") names the way in. Live: rebind `view-next → Ctrl+Alt+9` through the sheet → persisted to `ui.keys.overrides` → **survived a page reload** (`bootResolved`); stealing `p` was refused naming `freeze / resume every background refresh (Global)` (both the capture line and the refusal visible — fixed after the first live probe showed the refusal hidden while capture stayed armed); **Reset** removed the chord from the live config; junk chords refused.
- **Study collections (analysis-config reuse).** `studies.collections` in the store — each entry clamped by the shared `_clean_study_list` (the same rule the live list uses; 24 sets × 40 studies); `POST /api/control/studies` gains the `collection` verb (save · apply · delete, one write per call); the Studies view gains **Saved setups** (select + Apply/Delete, name + Save current as…, status line, draft preserved across re-renders). Live: save → config carried it; apply → status "applied"; delete → gone from the config. `test_studies.py` 14 (2 new).
- **Identity copy (Phases B8/D12/D13 merged).** New help topic **`start.identity`** ("What this program is — and is not": analytics layer, not a broker terminal; no orders/money; the data story in the market's own language — "what a broker or exchange charges for its own data is between you and them"; open source), a Guide section carrying the same framing and linking the topic, a README "Where it sits" paragraph, and sentences for the new affordances in `work.keys` / `view.studies`. No counts moved (help topic count is the one growth: 82 → 83).
- **Deliberately not built (reasons recorded in the diff doc).** Phase C (terminal mode: ladder, chart-order panel, brackets/OCO, broker execution; replay order recording) stays out — the audit itself scopes it separately and warns against a half-built order path; the paper ticket + replay are the foundation. B5's remaining Bookmap knobs (dimming, large-size highlight, auto-contrast frequency) are paint-path changes deferred behind a measured need. B7 (view-head symbol/link badges) is covered by the topbar symbol + canvas watermarks + widget link chips; a second badge surface would be noise.
- **Gates.** pytest **1561 / 3 skipped / 0 failed** over the final tree (session start: 1552/3; +9 net = 7 rebind pins + 2 studies pins); AUDIT CLEAN; ruff clean; **34/34** node selftests; both goldens; live sandbox pass on 8099 with **0 `client error:` lines**; sandbox stopped, port 8099 clear. HEAD `45172b1`, worktree dirty (199), **nothing committed**.
- **Owed.** Unchanged: **commit/publish on his word** (drafts first), then the standing follow-ups (radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots).

**§118 — The audit's safe remainder, attended: the paper desk (Trade DOM · bracket editing · session ledger + CSV · chart strip) · heat dimming + large-size highlight on both surfaces · the fresh-DB journal fix. (2026-09-19; nothing committed, live-verified)**

- **The scope call, stated before the build.** "All safe and genuinely program-enhancing" = the *paper-only* half of the audit's Phase C (ladder, chart strip, bracket editing, replay order recording) plus B5's deferred paint pair (dimming, large-size highlight). **Broker execution (C11) stays out** — no real order path exists anywhere in the product, and the audit's own warning against a half-built execution stack stands. Every new placement surface walks the existing gates: the armed order-keys switch, `Lock trading`, and the one `submit()` door in `paper.js` (the ticket walks it unarmed, the ladder walks it armed — a dense price grid is where a stray click finds a resting order).
- **The Ladder (Trade DOM) — new `ui/ladder.js` + 30-check selftest.** Print-centred grid spaced on the **session tick** (`rows()`/`decide()` pure; the painter hands clicks back to paper.js). Grammar, in the card as a subtitle and pinned in the selftest: left-click below the print = buy limit, above = buy stop; right-click mirrored; the print's own row trades at market; shift forces market; middle-click gets the grammar sentence (real browsers fire `auxclick`, so it is wired there too); clicking an order's chip cancels it by id (ledger `cancel`). Live on the sandbox: "start a paper session first" / "arm the order keys…" / "trading is locked…" all refused in their exact sentences; armed placements rested (buy limit, sell limit), filled on the tape, and the chip cancel wrote its ledger line. `test_listener_balance` untouched (properties, not listeners).
- **Bracket editing after entry.** `paper.set_exits()` — the pair applied in one call (a price sets, `None` clears), junk refused without clearing anything, refused while flat with its sentence; `POST /replay/paper/exits` records an `exits` ledger line; the ticket gains the **Stop loss / Take profit (open position)** row — Apply exits · **Stop to entry** · Clear exits + a hint that flips with flat. Live: SL applied → the tape stopped the position out at it; breakeven → SL = entry → the tape filled it; the hint read the pair until flat.
- **Replay order recording — the session ledger.** `_paper["events"]` (start · submit · reject · fill · cancel · exits · end), each carrying the **tape clock** (`at_ms`, the last print's stamp) *and* the wall clock, capped at 300, surviving session close; carried in the state payload and drawn as the **Session ledger** card (last 14, reversed, kind-coloured); **Export CSV** writes the real file to the exports folder — verified on disk: `n,event,tape_time,action_time,order,side,size,price,order_kind,note`, tape time first so a reviewed session lines up with the chart it traded on.
- **The chart strip (Chart Trader pattern, collapsed by design).** The Chart view gains a one-line **Paper desk**: session pill, open P/L, live stop/target, Size (mirrors the ticket's), Buy/Sell/Flatten/Lock. The poller watches `replay` **or** `chart`, the session-control keys' `why` text was updated, and the strip states its own empty case ("no session — the Replay view starts one; this strip trades the same account"). Live: pill/hint painted from the real account, buy + flatten through the strip with their messages.
- **The session tick is real now.** The state payload carries `tick_size` (top-level) and the session starts on the **instrument record's** tick (`tickFor()` reads `S.config.instruments`) instead of a hardcoded 0.01 — the ladder's row spacing and the risk read-out's "ticks" unit both ride it. (Caught live: the ladder was spacing rows on a guess.)
- **Heat dimming + large-size highlight (B5's remainder), both surfaces.** New registered dials `ofx.heat_dim`/`ofx.heat_highlight` and `atlas.heatmap.dim`/`atlas.heatmap.highlight` (registry entries with meanings; store defaults 0, clamps 0–0.8 / 0–1, `SCOPED_DISPLAY_PATHS` extended **and mirrored in `scopes.js`** — the B9 "one list" pin enforces that pairing). Engine: the palette's alpha column scales with the dial (cache key carries it) and live cells at/above the share-of-ceiling threshold get an outline — a fading ghost is a memory, never outlined. Heatmap view: one `globalAlpha` over the heat pass + the same outline rule. Bars: `dim`/`big` on the Engine, two inputs on the Heatmap's heat row; **apply globally** carries the pair too. Measured on real canvas pixels through the real paint path: dim 0.6 cut heat luminance **59 %** (270.35 → 111.34), highlight raised it 6 % with the outlines drawn, dim 0 restored **exactly**; the Engine bar wrote 9 → the store clamped to 0.8 in input, params and config.
- **The live pass caught a real bug, and it is fixed: "End & save to journal" 500'd on a fresh database** (`no such table: trade_journal` — a clean install's first session end). The journal DDL now lives beside `TRADE_COLUMNS` in `desktop/journal.py` (`TRADE_JOURNAL_DDL`, pinned against both the column list and `data/database.py`'s schema) and `paper_close` creates the table it writes to. Re-verified live: the session ended ("1 trade(s) saved"), and the row is in the sandbox DB (`BTCUSDT long 81079.1→81078.1, −100 ticks, "simulated session"`).
- **Two internal measurements the next live pass should not re-learn.** (1) The Heatmap's paint governor (`market-pressure.js` `GOVERNOR`) **skips same-signature repaints** within its 400 ms frame budget — pixel probes must vary `data.version` and space paints ≥ ~600 ms, or every reading is the previous paint (this cost three false "no change" readings). (2) The Engine bar's listeners attach **lazily in `ofxInit` on the first Engine-view visit** — dispatching a change event before opening the view proves nothing (also cost a false negative).
- **Gates.** pytest **1584 / 3 skipped / 0 failed** over the final tree (session start 1561/3; +23 net = ladder 11 · ledger 5 + 2 journal · paper 3 · B2 2); AUDIT CLEAN; ruff clean (0.16.7); **35/35** node selftests (ladder 30 new · ramp 49 · scopes 5); both goldens regenerated; live sandbox (8099) with **0 `client error:` lines in the final run**; sandbox stopped, port 8099 clear. HEAD `45172b1`, worktree dirty, **nothing committed**.
- **Owed.** Unchanged: **commit/publish on his word** (drafts first), then the standing follow-ups (radar walls / big-trade zones, spent-state persistence, config slots). Notes for a future execution pass: the ladder's window is ±10 ticks (recentres on the print — a coarse "N ticks per row" step is the refinement if crypto ladders want it), and session persistence (`to_dict`/`from_dict`) is still unused — the ledger CSV is the record today.

**§119 — The owner's list.txt, attended: one menu hide · the heatmap panel's way back · wheel/fit polish · the "← Back to X" context chip. (2026-09-19; nothing committed, live-verified)**
- **One menu hide.** The bar carried its own “hide” button beside the boxed topbar toggle (§94) — two controls for one action, and a hide that folds its own face away with the bar. Removed: the in-bar button + its listener (`menubar.js`), its chrome pair and shortcut prompt (`chrome.js`, `keys.js`), its styles (`modules.css`); the boxed “menu hide / menu show” toggle is the single control (B on the keys). `test_keys_ui` now pins the inversion.
- **The heatmap's “fit… it hides and no way back” — reproduced and fixed.** The real trap: minimal mode hid `.view-head .field` wholesale, and the interactive panel (the pro bar, carrying its own “minimal: on” restore) lives inside one of those fields — the way back hid itself (live receipt: zero visible bar children while minimal was on). Fix: the field carrying the pro bar is exempt (`:not(:has(.hm-pro-bar))`); the on-face reads “minimal: on — restore”; a `say()` hint teaches the return; **`m`** toggles (OFAPKEYS, Heatmap scope, clicking the real button); the stats tip names fit/m. And `fit` — a silent no-op when the window was already a list value — now truly fits: clears the selection, resets Window/Rows through their own dials (one pipeline), and always answers (“view fitted — 4 min window · 200 rows”).
- **Wheel on the heatmap: already there, now discoverable.** wheel = zoom window · shift+wheel = price rows (live-verified 240 → 480 → 240); the tip + `m` join the documented controls. The hide-sweep confirmed every hide keeps a visible way back: rail (edge reveal + R), menu bar (boxed toggle + B), zen (Alt+Z, live-checked), card-fold (a title now states “Double-click to unfold this card”, live-checked).
- **The “← Back to X” chip (list.txt item 4).** New `ui/navreturn.js` (+ selftest, + `test_navreturn.py`, + listener-ledger entry): one slot of context memory wrapped around `window.showView`; every route INTO help records the origin (menu, F1, buttons, palette), and registered task-transfer jumps call `OFAPNAV.jump(to)` — wired at the hint card's “instruments”, the Engine look-up → Instruments, heatmap region → Replay, and seven menu task rows (MT5 → Market Watch, the NinjaTrader and Platforms rows, Show log file, Instruments…, Feed health, Client errors). The chip paints first in the destination head (“← Back to Heatmap”, the rail's own label); plain navigation clears the slot; it never ping-pongs. Live: help jump → chip → return; jump → replay → chip → return; manual nav → slot cleared, 0 chips anywhere.
- **Gates.** pytest **1594 / 3 skipped / 0 failed** (session start 1584/3; +10 = `test_navreturn`); AUDIT CLEAN (116 modules — navreturn joins JS_FILES); ruff clean 0.16.7; **36/36** node selftests (navreturn 12 new); both goldens clean; live sandbox (8099, scratch APPDATA): all four items verified in-browser + a visual QA of the chip. HEAD `797eea0`, worktree dirty, **nothing committed**. Count deltas for the push pass: tests 1584→1594, UI modules 115→116, selftests 35→36.
- **Owed.** Commit/publish on his word (drafts first — his gate). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§120 — The liquidity map, audited end to end: click, box, wheel, one fetch. (2026-09-19; nothing committed, live-verified)**
- **Reported:** "when i click anywhere in the liquidity map it goes darker and i have to click again to return the colours and the scroll wheen + shift doesnt function sealessly or at all." Four defects, all reproduced live before any edit:
  1. **The click-darken.** `mousedown` built the selection immediately — a zero-size box whose outside-dim (`rgba(6,10,18,0.62)` over everything outside it) covered the whole canvas, so any click darkened the map; a second click made another degenerate box; only a dblclick cleared it. Receipt: `sel = {x0:733,y0:259,x1:733,y1:259}` after one synthetic click.
  2. **The double fetch.** Every wheel tick / select change ran the change handler's `loadHeatmap` AND a `setTimeout(() => pull(true), 280)` — two fetches of the same endpoint, with the overlay only aligning on the second (the sluggish wheel).
  3. **The unsequenced loader.** `loadHeatmap` had no in-flight guard — overlapping responses could land out of order and paint the wrong window under a fast scroll.
  4. **The canvas-only drag.** Box extension lived on the canvas listener, so a drag stopped extending at the plot edge (and the click-refresh hook spent a fetch on every click inside the view).
- **Fixes (all in `heatmap-pro.js` + `atlas.js`):** mousedown anchors; the box is born only after `DRAG_PX` (4 css px) of real movement and tracks on the **window** (mirroring mouseup — the box now follows the pointer past the canvas edge); `loadHeatmap` owns the single fetch, is sequence-guarded (`A.heatSeq`), and dispatches `ofap:heat-offer` — the overlay adopts that exact payload (`HEATMAP_PRO.state.last === A.heat.last`, live identity check) instead of re-fetching; the refresh hook repaints from cache (`if (P.last) { draw(); hud(); } else { pull(true); }`); rapid scrolls coalesce to one fetch through the repo's own `deferKeyed('heatmap','snap')`; stepping is pure (`listStep`) and end-stops answer out loud ("widest window already — 15 min" / "tightest… — 2 min" / "most rows already — 300"); `fit` fires ONE change for the pair (the loader reads both dials fresh); mark toggle and clear-markers speak. New `heatmap-pro.selftest.js` (14 checks) + `test_heatmap_pro.py` (5 pins); listener ledger `heatmap-pro.js (14,0)`.
- **Live receipts (8099, real engine feed, auto-refresh off so counts isolate):** click → `sel:null`, overlay alpha 0, **0 fetches**; drag → box + outside-dim alpha 158 + "selected 21 × 57 cells · resting 2443.3 · heaviest 81361"; wheel ×1 → cols 240→480, **1 fetch**, `state.last === A.heat.last` true; 3 rapid ticks → end state cols 120, **1 fetch** (coalesced), correct stop message; shift+wheel → rows 200→300, 1 fetch; keys `-`/`=`/ArrowUp → 1 fetch each; at 900 wider → "widest window already — 15 min", 0 fetches; fit → both dials reset, 1 fetch, "view fitted"; mark mode → click pins a marker (0→1) with no box; clear-markers → 2→0 with its message.
- **Audit sweep (checked, found sound):** hover readout + OFAPCURSOR publish, region stats + the Alert hand-off (live: stats row populated, alert button present), markers save/load per symbol, region/markers CSV export (queueWrite path), to-Replay jump (§119 chip present), minimal + fit (§119 fixes hold), pause chip, auto refresh toggle, columns rail observe, freshness stamp.
- **Gates.** pytest **1599 / 3 skipped / 0 failed** (session start 1594/3; +5 = `test_heatmap_pro`); AUDIT CLEAN (**117 modules** — the new selftest joins the parse sweep); ruff clean 0.16.7; **37/37** node selftests (`heatmap-pro.selftest.js` 14 new); both goldens untouched; sandbox stopped, port 8099 clear. HEAD `797eea0`, worktree dirty, **nothing committed**. Count deltas for the push pass: tests 1594→1599, selftests 36→37, audit module line 116→117.
- **Owed.** Commit/publish on his word (drafts first — his gate). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§121 — The liquidity map, at industry standard: the real zoom, pan, and the anchor that was missing. (2026-09-19; nothing committed, live-verified)**
- **Reported, round two:** "still not seeing any correct zoom functions and the shift middle scroll wheel does nothing… drawing a box does not disappear on off click… compare it against market and competitor norms… REALLY fix." This time the mechanics were audited end to end, server included — and the headline cause was NOT in the map at all.
- **THE root cause of "zoom does nothing" (real input only): the intent gate deferred it away.** `intent.js` leases the surface on every wheel event for **900 ms** (`ev === 'wheel' ? 900 : 1400`) and `loadHeatmap` refused to load while the lease was held — it filed a `deferKeyed('heatmap','snap')` instead. Every further wheel tick re-leased and REPLACED that deferred run, so with continuous wheeling the repaint only landed ~1 s AFTER the user stopped — and a single tick looked like nothing happened for a full second. §120's live test missed it because the probe slept 1.2 s per tick (past the lease) and counted the deferred fetch as if it were immediate. **Law: a user-commanded view change (wheel, pan, dropdown) must FORCE past the hold; the hold exists to keep the FEED's pollers from fighting a gesture, never to mute the user.** `loadHeatmap(force)` now skips the gate for deliberate paths; the auto/slow poll keeps deferring.
- **The missing primitive — a time anchor — now exists server-side.** `depthmap.snapshot(columns, max_rows, until_ms)` slices the store so the window ENDS at the anchor; `/api/atlas/heatmap/{symbol}` takes `until` (epoch ms, 0 = live edge); the payload carries `bucket_ms`, `have_from_ms`, `have_to_ms`, `until_ms`; an anchor before the buffer answers empty + `note` ("no depth history at this time — the buffer holds N min"). Pinned by `test_heatmap_anchor.py` (10 tests: slice ends at the anchor, matrix columns follow the slice, clamps, cache key, route/hub threading).
- **The viewport module — `desktop/ui/heatview.js`** (+ node selftest, 31 checks; `test_heatview.py` gates the wiring): owns `{cols, rows, until, bucket, haveFrom, haveTo}` and the pure maths: `zoomTime` (live stays live — right edge pinned to the feed; panned anchors the time under the cursor), `zoomRows`, `panBy` (grab semantics), `panStep`, `snapLive`, `absorb`, `params`, `label`. Ladders widened to what "more zoom options" means: windows **1/2/3/4/6/8/12/15 min**, rows **60–400 in 7 steps** — index.html's dropdowns and the module's arrays are compared by a pin (the three-places-drift class that opened this audit).
- **The industry grammar, Bookmap-grounded** (their KB: wheel zooms centered on the cursor, drag pans, arrows nudge, zoom-by-drag, live edge): wheel up = zoom IN (was inverted); shift+wheel OR the wheel over the price gutter = rows; wheel reads deltaX too (tilt wheels / shift-converted axes); **middle-drag or shift+left-drag = pan** (throttled live state, final load on release); `←/→` pan one bucket, `shift+arrows` ten; `Home` = live; `fit` also snaps live; a **live chip** ("● live" / "▶ back to live") sits in the pro bar and is clickable; the info line reads `… · live` or `… · 3 min back`; tooltip documents the grammar. Click-off CLEARS a lingering box (his exact ask: "does not disappear on off click") — a plain click on the map deselects, with a spoken confirmation; the box is still born only on a real drag (4 px).
- **Live receipts (real engine feed; synthetic events DO lease — the immediacy measurement is the proof):** wheel tick → **1 fetch within 300 ms** (the old code: 0 until ~1 s — the deferral), cols 240→180→120→60 with "tightest window already — 60 s" at the floor; shift+wheel → rows 200→140; wheel on the gutter → rows; box → off-click → `sel:null` + "selection cleared"; middle-drag → `until` set, say "60 s · 6 s back", chip "▶ back to live", map's last bucket = the panned edge; `Home` → live; cursor-anchored zoom while panned: cols 240→180 with cursor-time drift **952 ms ≈ one bucket** (the grid's own resolution); pan clamps at `haveFrom+W`; auto-refresh paused while panned (**0 fetches / 6 s** with auto on); `shift+ArrowLeft` moved exactly −10 buckets (the first probe read 0 — it was already clamped at the oldest window; sequence artifact, not a bug); chip → live; `fit` → "view fitted — 4 min window · 200 rows · live".
- **Gates.** pytest **1614 / 3 skipped / 0 failed** (session start 1599/3; +15 = anchor 10 · heatview 5); AUDIT CLEAN (**119 modules**); ruff clean 0.16.7 (caught one unused var in the new test — fixed); **38/38** node selftests (heatview 31 new); goldens untouched; the T5/A12 pin updated to the new arrow grammar (arrows pan; zoom = wheel + the ± pair). Sandbox stopped, port 8099 clear. HEAD `797eea0`, worktree dirty, **nothing committed**. Count deltas for the push pass: tests 1599→1614, selftests 37→38, audit modules 117→119.
- **Owed.** Commit/publish on his word (drafts first — his gate). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots. Open refinement notes: vertical pan (Bookmap auto-recenters; ours does too — manual vertical pan would need a price-centre param), and the ladder could add 30 min / 1 h if the store's 900-bucket retention grows (`atlas.heatmap.max_columns`).

**§122 — Why the map dulled, and the deep end of zoom. (2026-09-19; nothing committed, live-verified on the owner's own install)**
- **Reported:** "why does the market depth indicator map initially look bright and then dulls to a lesser colour… and is there ENOUGH zoom and map control for a really deep and examinatory view?" Both answers were measurable, and one was a genuine defect.
- **The dulling, measured before any edit:** the colour ceiling is "the top share of the visible window" (`upper_cutoff_pct` = 5% saturate; balanced scheme). While the window fills, that statistic drifts hard — sampled live every 14 s from engine start: **3.27 → 6.02 (x1.84) over 3.75 minutes**, with jump-steps (3.47 → 4.76 inside one 14 s sample). Every cell slides from bright to dull as the ceiling rises underneath it. `scale_max` == the recomputed p95 in every sample, so the percentile mechanism is confirmed as the source.
- **The fix — a leashed ceiling (`_stabilise_scale`).** The percentile stays the TARGET; the APPLIED ceiling walks toward it by 25% of the gap per build, capped at **5% of itself per minute of wall time** (a heap-light, like a level meter). Post-fix re-measure, same recipe: raw target 3.45 → 4.24 (still free) while applied moved 3.452 → 4.069 = **x1.18 over 3.7 min in smooth 0.3%-per-14 s steps** — no jumps, no visible recalibration; the map you see at minute 1 looks like the map at minute 4. An explicit pin (`upper_cutoff_abs`) is NOT leashed — it applies at once (the user's own number). `clear()` forgets the regime (a fresh buffer is a fresh start); the payload now carries `scale_target` (the raw statistic) beside `scale_max` (applied) for exactly this kind of receipt. Pinned by `test_heatmap_scale.py` (9 tests: cap maths, 4-minute bound, pin instant, reset on clear, integration via a fake clock).
- **The deep end of zoom: the Detail control (column width).** The zoom range was capped by the fixed 1 s bucket — the real key to deep examination is `atlas.heatmap.bucket_ms` (registry: 100–10000 ms), which existed only in Settings and did not apply to a running hub. Now: a **Detail** select in the heat bar (100 ms / 250 / 500 / 1 s / 2 s / 5 s) posting the registered param, which — new — **applies live to the running hub**: the params endpoint re-tunes the atlas block after a save (`hub.configure`). A width change RESTARTS the depth buffer (mixing widths under one time axis would lie about time) with a spoken note; the Window dropdown's labels are TIME = columns × width and are relabelled from the running width (they follow the payload's own `bucket_ms`). Range now: **6 s (60 × 100 ms) … 75 min (900 × 5 s)**, with 8 window steps and rows 60–400; raising `max_columns` (dial, up to 4000) extends the long end to ~5.5 h. Verified live: switch to 250 ms → labels re-derived (60 s → 15 s at 60 cols), buffer restarted, `bucket_ms: 250` on the wire; wheel to the tightest window reads "tightest window already — 15 s".
- **Also live-proven on the owner's own installation** (his app, his profile, port 8080): engine streaming, heatmap ingesting (40 → 65 cols while sampling), applied 3.80 → 3.772 against target 3.80 → 3.688 — the leash visibly holding on the real desk.
- **Gates.** pytest **1623 / 3 skipped / 0 failed** (session start 1614/3; +9 = the scale battery); AUDIT CLEAN; ruff clean 0.16.7; 38/38 node selftests; the T5 pin and the listener ledger updated for the Detail dial (`heatmap-pro.js (15,0)`). Worktree dirty, **nothing committed**. Count deltas for the push pass: tests 1614→1623.
- **Ops lesson this pass paid for (the hard way): a diagnostic script that ENDS with a destructive call is a loaded gun.** The window-check helper carried its `Close` line from the close helper, so every "is it visible?" invocation sent WM_CLOSE — it killed the owner's app three times (each exit logged the app's own clean "Engine stop requested at exit", which is why it read as a mystery crash until the script was re-read). Read-only checks and actions live in separate files; never `Invoke-Expression` a script whose tail is an action.

**§123 — The wizard, the help and the guides, audited against industry norms (owner's wizard.txt). (2026-09-19; nothing committed; every change live-verified)**
- **The brief:** strict review of the wizard module, the help module and the in-app guides against "industry norms and expected user interactions"; correct abnormal or confusing paths; make the help/wizard a star feature; sound, safe, stream-lining fixes only. Full autonomy granted.
- **Recon first:** `guide.js` (2619 lines) owns the tooltips, the Guide view, the first-run wizard (12 express steps = 9 static + 3 runtime splices; +10 professional), the inline walkthrough cards (HELP_TOPICS, **extended at runtime by studies.js / platforms.js / ofx-view.js**), the MT5/NinjaTrader notices, and the delegated `data-help` handler. `help.js` is the Help Centre (rail view + dock + FAB + About), `help.py` the facts/check engine. guide.js had **no gate of any kind**.
- **Findings (each live-reproduced before any edit):**
  1. **The wizard had no keyboard interface at all** — Esc did nothing, Enter did nothing, focus stayed on `BODY` at open (aria-modal without focus management). Industry: Esc dismisses, Enter advances, focus enters the dialog, Tab stays inside.
  2. **The ✕ lied:** "Close without changing anything" — closing keeps your place (it persists the resume step) and can collect the step's edits. The truth is the nicer behaviour.
  3. **Progress dots were decorative** — a 12+ step wizard with no way back except N clicks of Back.
  4. **Dead clicks (real):** `data-help="bridges"` (Platforms) and `data-help="start.identity"` (About card) opened nothing — `openHelp()` returned silently on an unknown id. (`studies` looked dead to a static audit but its inline topic is added at runtime by studies.js — a static read of guide.js alone gives false negatives.)
  5. **Inline walkthrough cards were dead ends** — no path from the quick card to the full searchable topic in the Centre.
  6. **Seven menu rows named real panels and said "planned"** (Replay…, Notifications…, Performance…, History & retention, Studies library, Import profile…, Export data…) — dead rows for things that exist; the internal hints even said "the Replay view exists".
  7. **focus/F1 were fine** — F1 answers for the panel in focus (verified via `help.recents`), the Simple/Advanced gate, dock, system check and About all behave.
- **Fixes shipped:**
  - **`overlayKeys`** (one document keydown, top-most `.wiz-overlay` only): **Esc** dismisses through the overlay's OWN close control (so a wizard close keeps its place), **Enter** advances when the dialog holds focus (native behaviour wins on buttons/inputs), **Tab** wraps inside the dialog. Focus now rides into the card on open and on every step change (a step mid-typing keeps its focus).
  - **Truthful close:** ✕ tooltip "Close — your place is kept; the assistant resumes at this step" + a spoken confirmation ("Setup assistant closed — it resumes at this step next time.") on both ✕ and Esc.
  - **Visited dots go back** — clickable, titled ("Step N — click to go back"), jumping through the ordinary renderer (collect runs).
  - **Dead-click class closed:** a `data-help` id with no inline topic now continues in the Help Centre via `OFAPHELP.open(id)` (navigates + searches; `openTopic`'s unknown-id path searched invisibly and landed nowhere). Live: bridges → Centre searching "bridges"; start.identity → Centre searching "start.identity"; studies → its inline card (runtime topic) as before.
  - **Every inline card carries a door:** "Open in the Help Centre →" (`CENTRE_QUERY` covers the 10 static ids + the 3 runtime-extended ones; exact Centre topics where they exist, queries elsewhere). The **Guide view** gained the same door ("Search the Help Centre").
  - **Seven menu rows are doors now:** Replay…→Replay view (via the navreturn jump), Notifications…/History & retention…/Performance…→Settings with a spoken pointer to the exact section, Studies library→Studies, Import profile…→Profiles, Export data…→opens the exports folder. Live: Replay→replay view; Studies library→studies view; History & retention→settings view.
  - **A gate for the whole layer: `test_guide.py` (8 tests)** — module parses; the overlay keyboard contract; the truthful close copy; focus + dot wiring; **every wizard door target must be a real view** (index.html ∪ runtime-created views); **every inline topic (static + runtime-extended) must have a Centre continuation**; the step contract (9 static + ≥3 runtime splices, the footer labels); the promoted menu rows (no dead rows for existing panels). The layer that could silently rot now cannot.
- **Mechanics worth remembering:** the visible "Step N of 12" = 9 static steps + 3 `WIZ_STEPS.splice` additions (MT5, broker, before-the-end); `wizGo`'s `openGuide()` fallback is dead code (no such function — the deep-link check already guards); a wiring script that mutates its buffer and writes at the END loses every edit when a later anchor aborts (two of this pass's scripts did exactly that and were re-applied — write per edit, or verify after).
- **Gates.** pytest **1631 / 3 skipped / 0 failed** (session start 1623/3; +8 = test_guide); AUDIT CLEAN; ruff clean 0.16.7; 38/38 node selftests; listener ledger `guide.js (3,0) → (4,0)` for the overlay keyboard layer. Sandbox stopped, port 8099 clear; the owner's app relaunched from the current tree (visible, engine streaming). Worktree dirty, **nothing committed**. Count deltas for the push pass: tests 1623→1631.
- **Owed.** Commit/publish on his word (drafts first — his gate). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§124 — The staged fixes, executed: the truth close-out after the v2 reanalysis. (2026-09-19; nothing committed; every change live-verified on a sandboxed install — port 8099, scratch APPDATA)**

- **The brief:** the owner's word — *"go for all staged fixes"*: execute the fix list staged in `docs/COMPETITIVE_REANALYSIS_v2_2026-09-19.md` §7 (Priority 1 items 1–5, Priority 2 items 6/8/10/11/12), under the standing gates (broker execution out; Windows-only accepted).
- **Shipped, each receipt-backed (file · test · live):**
  1. **Trackers wired (F1, item 1).** Five live `/api/atlas` routes had no UI caller while the view's own menu copy promised "correlation, dots, cross-venue reads": **cross-venue book, correlation, trade clusters, feed history, participants' intent** now render as five cards on the module's own 4 s beat. Live: cross-venue answered *"best bid 81012.40 (alpaca) · spread 3.0 bps"*; 30 live Bybit prints in the feed-history card; honest empty states everywhere else. `test_trackers_wiring.py` (3 tests).
  2. **Control-surface one-liners (F-1…F-7, item 2).** *Frames* gains the sixth family — `delta` (option + view copy + route docstring); the *Bars* menu no longer lists "candles" twice ("default" / "classic candles"); the Logs filter can name **DEBUG**; hover-help resolves case-insensitively and covers every option of all four decorated selects ('1W'/'1M' finally have their helps; the `all levels` row does too); the Settings Data-source dropdown is built from `/api/control/sources` at boot (live: **9 options** — 7 venues + both + all — replacing a five-value fallback); registry `both` dropped (store + engine never had it); calendar filters persist (store defaults + clamps + save/restore). `test_control_surface.py` (6) + the markup-bounds pin.
  3. **Bounds unified + pinned (item 3).** registry = markup = store for `ofx.lambda_ms` (100–5000), `ofx.min_block` (0–1e6, step 0.01), `imbalance_threshold` (1–50). A generic round-trip pin now proves **every registry enum choice survives the store** — and immediately caught a second lie: `search.default_view` offered 13 landing views, the store kept 6; the store now accepts all 13.
  4. **Tools ▸ Export (F2, item 4).** The three server CSV routes (tape / heatmap / alerts) have their door: fetch → `/api/control/export/save` → the saved path is reported. **Prune was already shipped** — `storage.js` wires `/storage/prune` + vacuum + sweep; the audit's F3 line was stale (status addendum added to `CONTROL_SURFACE_AUDIT.md`).
  5. **Stubs decided (item 5).** 'Reset rail order' removed (rail order isn't user-editable; view defaults cover it); **'Recent' promoted** to a real recents list (config `ui.recent`, whitelisted + clamped + capped; written by workspace/profile/layout opens; File ▸ Recent re-applies — live write→read proven through the config); **'Edit list' built** (list-kind params editable end-to-end — `/params` accepts lists); 'Exit' is a disabled-with-reason row ("close the window (✕) — no in-app quit by design"); 'Record session…' stays an honest phase-5 stub.
  6. **Show-original tightened (item 6).** The staging surface already had Show-original-values; a **staged row now says what the value WAS** — the number Revert restores.
  7. **Preset comboboxes (item 10).** `presets.js` (new; 39th selftest) decorates **19 controls** from `data-presets` specs — pick a common value, or "Custom…" hands the field back; decorations drive the input's own change path. Live: 19 wraps, specs intact.
  8. **Wiring + chrome (item 12).** Toasts carry a **Help →** door (one delegated click; wired: engine fault, skipped instruments, instrument-save failure); the status bar carries the **active profile name** (click → Profiles).
  9. **Verified already-shipped (item 11a + part of 8):** the columns rail's manual/scheduled/conditional resets, double-click reset and "Reset all" exist; the ladder already has held-⇧ = market, position grammar (limit/stop by side, last-price = market) and a decision line. The *remaining* halves of 7/8/9/11 are the open set below.
- **Found while executing (both fixed in-pass):** the source-list fill only fired when Settings first rendered (moved to boot; live re-verified 9/9); the `search.default_view` enum lie (store widened to the registry's 13).
- **Gates.** pytest **1653 / 3 skipped / 0 failed** (pass start 1631/3; +22 = control_surface 6 · param_registry +2 · menus_pass 5 · trackers_wiring 3 · presets 6); AUDIT CLEAN (**121 modules**); **39/39** node selftests (38 + presets); ruff clean 0.16.7; ledger: ui.js (10,0) with reasons, presets.js (4,0); live pass on the sandbox — no client errors in the sandbox log.
- **Open (staged; unchanged gates).** Novelty-gated tips layer (§7-7); MT5-ingest provenance counter (§7-9); range-to-table events list (§7-11b); rebuild dist/zip/SBOM/installer (§7-13, owed); commit/publish (his word; drafts first). Broker execution stays out; Windows-only accepted.
- **Nothing committed; HEAD `797eea0`** — 52-file dirty worktree (was 33 at session start).

**§125 — The last staged three and the rebuild: novelty-gated tips, the ingest-provenance counter, Bookmap's range-to-table; dist/zip/SBOM/installer rebuilt over the whole tree. (2026-09-19; nothing committed; live-verified on a sandboxed install — port 8099, scratch APPDATA; packaging receipts on the frozen artifacts)**

- **The brief:** the owner's word — *"go for all"*: the remaining staged set from `docs/COMPETITIVE_REANALYSIS_v2_2026-09-19.md` §7 (7 tips · 9 provenance counter · 11b range-to-table) and the rebuild (13); commit/publish stays on his word.
- **Shipped, each receipt-backed (file · test · live):**
  1. **Ingest-gap provenance counter (§7-9).** `engine.tick_gaps()` — a pure function of the retained tick window: a gap is an interval wider than `max(5000 ms, 10 × the symbol's own median)`, so a thin symbol's cadence is never miscalled and a real silence in a busy tape is; an empty window answers `{"window": 0}` (claims nothing); unsorted/duplicate stamps are safe. `/api/control/engine/status` carries `gaps` per symbol; the data pill's tooltip appends `BTCUSDT: last tick 6.4 s ago — gaps ≥ 5.0 s in the last 133 ticks: 0 (worst 4.2 s)`. `test_engine_gaps.py` (7 tests). Live, engine on 8099: `ticks 425 · window 135 · median 72 ms · threshold 5000 · count 0 · worst 3686 ms`; tooltip read on the running page.
  2. **Range-to-table events list (§7-11b).** `heatmap-pro.js` `regionEvents()` — the boxed band's own record, straight from the payload's `events` (no new route): price band from the selected rows, time window from the boxed columns × the live bucket width. "Events in region" in the selection strip paints the table (time/kind/price/side/size/detail, ≤100 rows, newest first) with an honest empty sentence, and "Export events CSV" writes through the same `/export/save` door. `test_heatmap_pro.py` (+1 = 6 pins; the strip lists events in region and loses the list with the selection). Live: strip → *"Events in region — 0 of 120 level events in the boxed band (80971–81028.2)"* + the honest note — the record held **118 walls + 2 stacks** (`eventPriceRange 80947.3–81004`), the box simply spanned older columns, the time filter correctly strict; export wrote `exports/heatmap_events_1789798377359.csv` (43 bytes — header only, the band held none) through export/save.
  3. **Novelty-gated tips (§7-7).** `tips.js` (new module; the 40th node selftest): the "Try next" card mounts into the Guide view; four tips (layouts · workspaces · alerts · journal) gated on the STORE, never on clicks — each retires when the feature genuinely exists in the config/data; each tip is a launcher (view · help topic · ☰ menu — doors are object properties, the module owns no views); `N of 4 un-tried`; the card empties and removes itself; a check that cannot run must not nag. Registered in `index.html`, `audit_ui_refs.py` JS_FILES, listener ledger `tips.js (1, 0)`. `test_tips.py` (4). Live: card painted *"TRY NEXT — 3 of 4 un-tried"* with its remaining doors.
- **Gates.** pytest **1,665 / 3 skipped / 0 failed** (pass start 1,653/3; +12 = engine_gaps 7 · heatmap_pro 1 · tips 4); AUDIT CLEAN (**123 modules**); **40/40** node selftests; ruff clean 0.16.7; goldens exact (analytics 40 cases / 2,196 leaves, max diff 0.000e+00; config 31 factories / 18 crypto majors / 49 instruments). Live pass on the sandbox (port 8099, scratch APPDATA, real engine feed) — pill tooltip, tips card, events box, export; **no client errors**. Sandbox stopped, ports clear.
- **The crash, stated plainly:** the pass died at its certification batch — its first command was `taskkill /F /IM python.exe` (intended as a stray-process sweep; it killed the agent host itself, not any app process). The sandbox stop before it had succeeded; the certification was re-run on the frozen tree with identical results and the failure cost only time. **Law: never `taskkill /F /IM python.exe` on this machine — kill by PID or by cmdline match** (the sandbox's own stop is `process(kill)` on its session id).
- **The rebuild (§7-13).** `scripts/build_exe.py` (15.3 MB exe; 232 developer files pruned; 896-file payload; `BUILD_INFO.json` = commit `797eea0`, worktree dirty, built 2026-09-19T16:03:35+0930) → `installer/make_installer.ps1` (Inno Setup 6) → `scripts/make_release.py`. Artifacts: **Setup 37,659,252 bytes, sha256 `5B8BF8B46DEAB5F7F004E58530353D340F353EBEC076EEFD7C625A8E2ACE699A`**; zip 42,998,781 bytes, sha256 `917a48b2556633f5a23662e365a43efd75662c38896e498f573706baec5beb9a`; SBOM sha256 `eb51942bd71e95d92aaae290e19fa3293cc5b373ee2cb129dd768cf0485c9bac`; dist exe sha256 `b2eb32d8f6fb15064fa6cd92f071332024a701e573c63d17295c01abcc31b8e2`. `installer/modflow.iss` needed no edit; `installer/README.md` carries the dated journey paragraph.
- **Packaging receipts (rerun on this pass).** Frozen smoke **18/18** — incl. asset parity **78 shell refs** + 11 help PNGs + corpus/search/pane byte-identical to the tree, WS 101/403, `frozen=true`, 0 client errors. **Setup journey 17/17 ALL PASS** — silent install exit 0 (898 files = 896 payload + unins000.exe/.dat; installed exe hash == dist exe; Start Menu entry created; desktop icon correctly skipped; ARP `HKCU\...\Uninstall\{C2042089-3E19-410D-ABA6-C32BC9C13D80}_is1`), installed smoke (healthz / candles 200 / unknown → `[]` / /desktop 200), silent uninstall exit 0 (dir, ARP and Start Menu gone; `%APPDATA%\OrderFlowAnalysisPro` untouched; his dev desktop shortcut backed up first and left as found).
- **Nothing committed; HEAD `797eea0`** — 58-file dirty worktree (34 tracked + 24 untracked; was 52 at the §124 record). Count deltas for the push pass: tests 1,653→1,665; selftests 39→40; audit modules 121→123; smoke shell refs 73→78.
- **Owed.** Commit/publish on his word (drafts first — standing gate). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§126 — The final release assurance audit (the Desktop directive): SHIP ONLY AFTER REQUIRED FIXES — two new defects confirmed live, everything else re-verified on this tree; report-only pass, nothing committed. (2026-09-19)**

- **The brief:** the owner's word — *"final security audit prompt.txt"*: an executive final-release assurance audit (security / zero-leak / market-data integrity / performance / public-GitHub ship readiness; the 14 prescribed sections; evidence only; no code changes). Report: `docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1b.md`; evidence log: `Desktop\OFAP_v0.1b_release_assurance_audit\00_EVIDENCE_LOG.md`.
- **Decision: SHIP ONLY AFTER REQUIRED FIXES** — one small source pass (RA-01 + RA-02; RA-03 in the same pass), then the gates + packaging battery + rebuild:
  1. **RA-01 (Medium, confirmed live).** The Engine readout interpolates the symbol into `innerHTML` unescaped (`ofx-view.js:597/614`) and instrument symbols are stored without a charset clamp (`config_store.py:1466`; the house rule already exists at `:1690`). A crafted symbol driven through the app's own controls produced a REAL element in the DOM: `<img src="X" onerror="WINDOW.__RA_XSS=1">`. Script execution on this field blocked by the store's `.upper()` (JS case-sensitivity) + CSP — element injection, not RCE; escape-at-sink + clamp + pins required.
  2. **RA-02 (Low, confirmed live).** `/api/control/data/export` answers 500 on a fresh profile (no DB yet: `sqlite3.OperationalError`) and on a `/`-bearing symbol (`BTC/USDT` → `FileNotFoundError` on a bogus `ticks-BTC/USDT-…csv` path); the filename tag lacks the paper-export sanitiser. No traversal reachable (the error itself proves the intermediate dir is never created). Fix: sanitise + graceful 400s.
  3. **RA-03 (Low, code).** `engine.bybit_validate()` interpolates the symbol into the venue URL unquoted (the SS-12 class, one site) → `quote()`.
- **Re-verified green on this tree (fresh receipts):** guard family live on the frozen exe (hostile Host 403, cross-origin POST 403, cross-site POST 403, loopback POST 200, WS 101/403, `/docs|/redoc|/openapi.json` 404, served `/desktop` hash == packaged, CSP meta present); CSP sweep over 33 driven views → **0 violations / 0 page errors**; churn probe **flat** (timers 14→14, 0 same-node accumulation, 0 detached-retained); secrets clean four ways (worktree incl. untracked / full history pickaxe / frozen payload / `git add -An` dry-run); `uv lock --check` green; `pip-audit` clean (59 pkgs); SBOM 45 components; zip 896 entries / 0 corrupt; frozen smoke **18/18** + Setup journey **17/17** (the §125 artifacts); 30/30 non-test deques bounded; no execution-capable code (Alpaca orders = read-only history); newest screenshots re-sampled clean (only the Telegram placeholder `12345:ABC-DEF`); bandit dispositions refreshed (1 High B324 SHA1-mutex + 29 Medium, all triaged — 20 fixed/loopback urlopen, 7 fixed-identifier SQL, 1 DTD-mitigated, 1 test-only).
- **Carry (unchanged, non-blocking):** F-05 log-noise filter and F-08 `usedforsecurity=False` queue with the RA fixes; F-07 docs-publication decision stays the owner's.
- **This pass changed no code** — records only (this block, RESUME, the report + its evidence tree). **Owed:** the Stage-1 fixes on his word → gates + battery + **rebuild**, then the standing commit/publish pass. Worktree now 59 files (was 58; +the report; the evidence tree lives outside the repo).

**§127 — The release-assurance fix pass: RA-01 (+ its second live sink), RA-02, RA-03, F-05, F-08 in one source pass with pins; gates green; dist/zip/SBOM/installer rebuilt and re-batteried. (2026-09-19; nothing committed; live-verified on a sandboxed dev server — port 8099, scratch APPDATA)**

- **The brief:** the owner's word — *"GO WITH ALL FIXE, NO VERY LONG SOAK TESTS THOUGH"*: execute every fix the §126 audit named (Stage 1 + the queued Stage-2 cosmetics); no long soaks.
- **Fixed, each receipt-backed (file · pin · live):**
  1. **RA-01 (Medium).** The readout branches escape the symbol (`` ${esc(sym)} ``) — **plus RA-01b, found by this pass's own live re-probe: the Engine legend panel** renders `OFX.legend()`'s `live` string (built as `` `${state.symbol} · Ns bars` `` at `ofx.js:1502`) into innerHTML at `ofx-view.js:427`; after the readout fix the crafted symbol still parsed into a real `<img>` under `#ofxLegendBody`. `paintLegend()` now escapes every interpolated field (+ the swatch glyph/sample). Store-side clamp `_clean_symbol` (A-Z 0-9 `. _ -`, ≤24; rows that clean to nothing are dropped) on `instruments[].symbol` — the palette lanes keep their own contract (`BTC/USD` survives; pinned by `test_config_store`). Live: crafted symbol driven through the app's own controls renders as TEXT in both sinks, `imgs[src=X] = 0`, no execution, no paint errors (`evidence\x127_sink_receipt.txt`; the receipt also records the stale-cache false alarm and its cache-cleared re-probe).
  2. **RA-02 (Low).** `dataport.export_rows` clamps the filename tag (the `ticks-BTC/USDT-…csv` bogus-subpath class); `api.data_export` catches `sqlite3.OperationalError`/`OSError` → 400 + sentence. Live 10/10 (`evidence\x127_http_receipt.txt`): fresh profile → `400 {"detail":"no tick history to export yet — start the engine or import a CSV first (OperationalError)"}`; symbol `BTC/USDT` → `ticks-BTCUSDT-20260919-073357.csv` (rows=1) inside `exports/`; all-symbols → `ticks-ALL-…`; the exports folder stays flat.
  3. **RA-03 (Low).** `engine.bybit_validate` → `urllib.parse.quote(str(sym), safe='')`; the pin drives a fake `urlopen` and asserts `%26/%2F/%3D` on the wire.
- **Stage-2 cosmetics, executed:** **F-05** — `logs.AbortedSocketFilter` drops `ConnectionResetError`/`ConnectionAbortedError` records at every sink (unit pin; live attempt: 6 aborted sockets, 0 reset tracebacks in the log). **F-08** — `usedforsecurity=False` on the mutex sha1; the count/prune loops in `database.py` use static statement strings.
- **Pins:** `orderflow_system/test_ra_fixes.py` (8 tests). **Gates:** pytest **1,673 / 3 skipped / 0 failed** (start 1,665/3; +8) · AUDIT CLEAN (123 modules) · ruff clean 0.16.7 · 40/40 node selftests · goldens exact. One battery run transiently read 1,668/8 — the 5 extra skips did not reproduce across three identical-tree reruns (reasons not captured); noted, not hidden.
- **The rebuild.** `build_exe.py` (15.3 MB exe; 896-file payload; `BUILD_INFO` = commit `797eea0`, dirty, built 2026-09-19T17:06:16+0930) → `installer/make_installer.ps1` → `scripts/make_release.py`. Artifacts: **Setup 37,661,860 B sha256 `0D0BF7C57329ADC02B642CF07B187A398CC8666AA4481CA0662E563981D692E2`**; zip 43,001,835 B sha256 `113be091cd0befb22e187b21b292337e399fa2a80ee6ad45ce060a80d06b4f2f`; SBOM sha256 `8e2fa4b02096d45c00511b7e436eec078a16396a14843bfc4ce6e1ab890f3130`; dist exe sha256 `8ae3b25018dfd89643b23a3b289de28fb18fbd7e45e8e21871ef1e4c26c8896e`. `installer/README.md` carries the dated §127 journey paragraph.
- **Packaging receipts (this pass).** Frozen smoke **18/18** (asset parity 78 shell refs byte-identical; WS 101/403; `frozen=true`; 0 client errors). Setup journey **17/17 ALL PASS** (silent install exit 0 — 898 files = 896 payload + unins000.exe/.dat; installed exe hash == dist exe; Start Menu created; desktop icon correctly skipped; ARP created; installed smoke 4/4; silent uninstall clean; `%APPDATA%\OrderFlowAnalysisPro` untouched; his dev desktop shortcut left as found).
- **Nothing committed; HEAD `797eea0`** — 64-file dirty worktree (38 tracked + 26 untracked; was 59 at the §126 record). Deltas for the push pass: tests 1,665→1,673; +`test_ra_fixes.py`; UI/store/api/dataport/engine/logs/single_instance/database touched by the fixes.
- **Owed.** Commit/publish on his word (drafts first — standing gate). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§128 — The multi-monitor system audit (owner's Desktop `monitor.txt`): send-to-any-monitor, snap, pin and the unplug rescue for every panel window in BOTH views; four defects found and fixed (one held the dialog shut entirely, one was introduced and caught in this same pass). (2026-09-19; nothing committed; live-verified on a sandboxed launcher — port 8094, scratch APPDATA, WebView2 driven over CDP, OS windows enumerated)**

- **The brief:** the owner's word — *"a full system audit of the capabilities of the program for multi monitor and complete support for unpinning/moving from any monitor or display of panels from the TERMINAL view to any combination of monitor/screens … creative and 100% functional solutions for BOTH 'TERMINAL' and 'CLASSIC' views."* Audit doc: `docs/MULTIMONITOR_SYSTEM_AUDIT.md`.
- **What was already there** (§71–§73, §96): the pure placement maths + `WindowHost` seam, the `ui.windows` set restored on launch, the `/api/control/windows` route, the widget-window menu (terminal bar + Classic top bar + the aux window's own bar), the Windows & layouts dialog, §72's window geometry + per-screen layouts, §72's DPI refit.
- **What was built (the solution set, both views):**
  1. **Send + snap.** `windows.PRESETS` (10 shapes: four halves, four corners, `fill`, `center`) resolved by the pure `preset_rect` inside any screen's work area; `move_placement` picks the screen (explicit index → `step` monitors over, cyclic → the screen containing the position → primary). New host method `move()` (real `window.move` + `resize`), route actions **`move`** (`{id, screen?/step?/preset?}` — works on an OPEN window and on a stored one from a safe start) and **`arrange`** (Bring them home for every stranded window), `preset` accepted on `open`. The state now answers **`open_geometry`** (each open window's live rect + the monitor it is ON, labelled) and **`stranded`**.
  2. **The widget's own door.** Every terminal widget frame carries **⧉** on its title bar → `OFAPWINDOWS.openFor(view, btn)` opens the window menu aimed at THAT widget (straight into its send/snap panel when it has a window). Terminal bar menu rows gained a **⇥** per open window; the auxiliary window's bar can move **itself** ("⇥ monitor"), and now says which window it is and which monitor it sits on.
  3. **Any panel → any monitor, without a focused widget** (Classic's route): the dialog's "Another panel, on any monitor" row (panel · monitor · shape pickers, built from the document's own view sections; live: 34 / 1 / 10) opens it already placed. Every dialog row gained Send buttons (one per monitor, "· here" on its own) and the 10 shape buttons.
  4. **The rescue.** The dialog banner names the stranded window(s) with **Bring them home**; the menu shows a ⚠ on the Windows chip and offers the same; `reset` stays the per-window version.
  5. **Keyboard.** `Ctrl+Alt+W` — the focused widget's window menu; `Ctrl+Alt+Shift+→ / ←` — send its window one monitor over (opening it there when it has none). Both modes; both registered in the Keys sheet.
- **Defects found by the audit, each fixed with a pin and a live receipt:**
  1. **F-1 (high):** `windowing.js` and `windows-ui.js` both assigned `window.OFAPWINDOWS`; the later load won and the View menu's "Windows & layouts…" called an undefined `open` — the dialog was unreachable. One global per module now (`OFAPWINMGR` / `OFAPWINDOWS`), pinned, re-proven from the real menu in Terminal AND Classic.
  2. **F-2 (high):** `stranded()` read only the store. Measured live: a window pushed to (9000, 40) kept a record saying (0, 0) (the store trails the window) → the app said "nothing stranded" while a window was off every screen. `stranded(records, screens, live=…)` now takes both; live: banner + Bring them home returning the real window to (640, 0).
  3. **F-3 (medium, found by running it):** "send to next monitor" on a ONE-monitor machine resolved cyclically to the same screen and re-centred a hand-placed window. Fixed at both layers (UI no-op with `screens.length < 2`; API answers `moved: ""` + "already on that monitor" for a step-move with nowhere to go; an explicit `preset` still centres). Live: geometry identical across the real keystroke.
  4. **F-4 (low):** an aux window re-acquired `#view` after §73 cleared it — two writers (`ui.js showView`, `shell.js focusView`); both skip when `window.OFAPAUX`. Live: `location.hash == ''` on a fresh aux window.
  5. **F-5 (medium, self-inflicted, caught live):** the dialog rewrite gated every row on `payload.view`, killing every button in it (Bring them home clicked, nothing moved). Fixed; pinned; re-proven live.
- **Receipts (sandbox, scratch APPDATA, 8094; CDP 9223; `EnumWindows` as OS truth — the store and the OS window agreed exactly in every check):** widget ⧉ menu rows; open → real window (730, 312) 1100×760; aux bar "⧉ Overview · window w9ef12e4 · Monitor 1 · 2560x1440 · ⇥ monitor · 📍 pin · × Close" with exactly 1 frame / 1 active section; **fill → OS (0, 0, 2560, 1384)** and **left → (0, 0, 1280, 1384)**; dialog from the View menu in both modes; TAPE opened left-half from the dialog; hotkeys in `OFAPKEYS.recent`; the stranded banner + rescue; the single-monitor send key changing nothing; WM_CLOSE sweeping every aux window (§94 intact); **0 client errors**.
- **Gates.** pytest **1,740 / 3 skipped / 0 failed** (start 1,696/3; +44 = `test_aux_windows.py` 31→69 collected, `test_windowing_ui.py` 4→10) · identical counts under CI semantics (`PYTHONUTF8=0`) · AUDIT CLEAN (123 modules) · ruff (0.16.7 via uvx) clean · **40/40 node selftests** (`windows-ui.selftest.js` 10→16 checks) · goldens untouched.
- **Honest limits.** One physical display on this host: cross-monitor moves and mixed-DPI migration were exercised as pinned maths over every screen shape plus real OS windows on the one screen; the physical two-monitor pass stays the owner's. Literal tear-out dragging remains impossible inside WebView2 (no OS drag can start from the page) — the commands are the shipped form (§73's statement stands). No rebuild: source + tests + docs only, so `dist/`, the zip, the SBOM and the Setup are untouched (§127's artifacts remain the release candidates).
- **Files.** New: `docs/MULTIMONITOR_SYSTEM_AUDIT.md`. Changed: `desktop/windows.py`, `desktop/launcher.py`, `desktop/api.py`, `desktop/ui/windows-ui.js`, `desktop/ui/windowing.js`, `desktop/ui/shell.js`, `desktop/ui/ui.js`, `desktop/ui/keys.js`, `desktop/ui/menubar.js`, `desktop/ui/atlas.css`, `desktop/ui/guide.js`, `desktop/ui/help-data.js`, `test_aux_windows.py`, `test_windowing_ui.py`.
- **Owed.** The physical multi-monitor pass (owner). Commit/publish on his word (drafts first — standing gate), and with it the standing question of whether to rebuild `dist/` for a source-only wave. Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§129 — Layout ▸ Previous versions, made legible: one submenu of the five newest (each naming its time to the second, its age and what it holds), an Auto-cull switch that also culls what is already stored, restores that are themselves recorded, and the why / why-five / auto-cull story told in the help centre, the setup assistant and the Guide. (2026-09-19; nothing committed; live-verified on a sandboxed launcher — port 8094, scratch APPDATA, WebView2 over CDP)**

- **The brief (the owner's screenshot + words):** the Layout menu's bottom section listed `Restore "Moddy" — saved 06:54 pm` three times over, saying nothing about what a version IS, why they exist or how many are kept. The ask: a separate dropdown with only five "saves", an auto-cull option, and an explanation programme-wide (wizard, help) of why the option exists, why five, and the auto-cull.
- **The menu now.** One row — **Previous versions of this layout**, its value reading `5 kept · auto-cull on` — opening a submenu: `Undo history · <name>`; up to five rows newest-first, each `Restore the 07:52:06 pm version · newest` with `just now · 1 widget · 1 tab` beside it; the **Auto-cull old versions** switch (ticked state); and a last line saying why the feature is there at all (`a save-over, an auto-arrange, a reset or a delete is one click — this is the one click back`). The old shape (a flat `versions.slice(0, 3)` wall) is gone; the row exists even with no versions yet, where it says `nothing kept yet` and explains that one is kept each time.
- **The store now.** `config_store.LAYOUT_VERSIONS_KEEP = 5` (auto-cull depth) beside the hard ceiling `LAYOUT_VERSIONS_MAX = 10`; new `ui.layout_versions_autocull` (default **ON**, clamped bool) read through `config_store.layout_versions_autocull(cfg)`. Every push obeys it (`_push_layout_version(..., keep)`); `POST /layouts {autocull: true|false}` writes the flag and, when turning it ON, culls what is already stored in the same call (answers `culled: n`); the state answers `autocull`/`keep`/`max` and each version row now carries the shape it would restore (`widgets`, `tabs` — counted from the stored entry, no new storage).
- **Restores are recorded.** The arrangement a restore replaces is pushed as a version first, so stepping back is itself steppable-forward — the state you were just looking at was previously the one state with no way back (pinned).
- **The story, programme-wide** (the owner's ask): help topic `work.layouts` gained the block *Previous versions — the one-click undo for a layout* (what it is · why it exists: auto-arrange, reset, save-over, delete, import · why only five: the handful people reach for, and every version is a full copy in the config file · auto-cull: on keeps five, off keeps up to ten, turning it on culls immediately) plus searchable aliases (`undo my layout`, `roll back my layout`, `older version`); the setup assistant's **Professional · Layout & workspaces** step gained the same note; the Guide's identity block mentions the five states.
- **Receipts (live, sandbox 8094 + CDP 9223).** Seeded a ring through the real route: state `autocull/keep/max = [true, 5, 10]`; with auto-cull off the ring grew to 10; the menu row read **`Previous versions of this layout · 5 kept · auto-cull on`**; the submenu listed `Undo history · Probe v8` + five `Restore the 07:52:06 pm version` rows (age + `1 widget · 1 tab`) + the ticked **Auto-cull** row + the why-line; clicking Auto-cull with eight stored flipped the flag and left exactly 5 (culled 3, via the route's own `culled`); clicking a restore row moved the layout `Probe v8 → Probe v7` and the ring's newest row became `Probe v8` (the replaced state, as designed); the Help Centre rendered all three phrases; **0 client errors**; WM_CLOSE swept and the sandbox was cleaned.
- **Gates.** pytest **1,747 / 3 skipped / 0 failed** (start 1,740/3; +7 = `test_layout_versions.py` 6→12, `test_menus_pass.py` +2) · identical counts under CI semantics (`PYTHONUTF8=0`) · AUDIT CLEAN (123 modules) · ruff (0.16.7) clean · **40/40 node selftests** · goldens untouched.
- **Files.** `desktop/config_store.py` (KEEP + the flag + `layout_versions_autocull()`), `desktop/api.py` (state rows with shape, `keep`/`autocull`/`max`, the `autocull` action + cull, restores recorded, per-push depth), `desktop/ui/menubar.js` (the submenu, the switch, `versionStamp`/`versionAge`), `desktop/ui/help-data.js`, `desktop/ui/guide.js`, `test_layout_versions.py`, `test_menus_pass.py`.
- **Owed.** The owner's physical multi-monitor pass (§128) and commit/publish on his word (drafts first). Rebuild decision for the source-only waves (§128+§129) still his. Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.

**§129b — The owner's "the top menu bar randomly hides while I change options" report, traced and fixed: every dropdown's own scrollbar closed it. (2026-09-19; nothing committed; live-verified with REAL mouse and wheel events over CDP — 8094/9223)**

- **The report:** *"when clicking the top menu bar now the focus is wrong and randomly hides the bar while trying to change options."*
- **Measured cause, not a guess.** The dropdowns have grown scrollable — **View: 1,114 px of rows in a 665 px panel; Layout: 787 px** (§129's version submenu added the rows that tipped Layout over). The menubar's close guards run a CAPTURE-phase `scroll` listener that closed every open menu on ANY scroll event — *including a scroll INSIDE the panel*. So every row below the fold (Legend panel, Menu bar, Rail, Status bar, Full screen/zen…) could only be reached by scrolling, and the first wheel tick closed the menu: the owner's "randomly hides while I try to change options". A click aimed at one of those rows then landed on the app underneath — the "focus is wrong" half of the report. Earlier probes had missed it because they used `element.click()`, which neither focuses nor produces a wheel; the reproduction needed real `Input.dispatchMouseEvent` clicks and a real `mouse.wheel`.
- **The fix** (`desktop/ui/menubar.js`, one guard): the scroll closer now ignores scrolls whose target sits inside `#menuBar` (`ev.target.closest('#menuBar')`) — a scroll in the open dropdown is the user reaching for rows, not "touching something else". The rest of the contract is untouched and now PINNED so it cannot quietly disappear with it: mousedown-outside (capture), focusin-outside, window blur, Tab, Escape.
- **Receipts (live, sandbox 8094 + CDP 9223).** Wheel over the open View panel (+300) → menu STAYED open, `scrollTop` 300 → the below-the-fold **Status bar** row clicked → status bar hidden (action ran); wheel over the open Layout panel (+400) → stayed open → **Auto-cull** clicked → route answered the flag true→false; a scroll OUTSIDE the bar still closed the menu (`[]` open) while a scroll INSIDE kept it (`['view']`); 0 client errors. Panel geometry measured (`top 25 · bottom 691 · innerHeight 901` — the panel fits the window; nothing was clipped).
- **Gates.** pytest **1,748 / 3 skipped / 0 failed** (+1: `test_menus_pass.py::test_scrolling_the_open_dropdown_keeps_it_open`) · identical under `PYTHONUTF8=0` · AUDIT CLEAN · ruff (0.16.7) clean · 40/40 node selftests.
- **Files.** `desktop/ui/menubar.js`, `test_menus_pass.py`. No store, route or layout changes.
- **Owed.** Unchanged: the owner's physical multi-monitor pass (§128), commit/publish on his word (drafts first), the `dist/` rebuild decision (§128+§129+§129b are source-only).

**§129c — The owner's "rebuild": §128+§129+§129b frozen into dist/zip/SBOM/Setup, and one defect the rebuild itself found. (2026-09-19; nothing committed; battery green — frozen smoke 18/18, frozen features 20/20, installer journey 11/11)**

- **The word.** The owner looked at the build he actually clicks and the version section was the OLD wall of `Restore "Moddy" — saved 06:54 pm` rows: he launches the DEV shortcut (`pythonw -m orderflow_system.desktop` in the repo) and that page had not been reloaded since before §128, so §129's menu was never in front of him. He asked for the rebuild; the artifacts (which he does not run, but which are the release candidates) now carry all three waves.
- **The rebuild chain, in order** (each step on the SAME tree, so the artifact carries the last source change): gates (1,749/3/0 both interpreters, AUDIT CLEAN, ruff clean, 40/40 selftests) → `scripts/build_exe.py --clean` (payload **896 files**, 232 developer files pruned, 62 licence texts from 19 distributions) → **frozen smoke 18/18** → **frozen features 20/20** → `scripts/make_release.py` (zip + CycloneDX SBOM) → `installer/make_installer.ps1` (Inno 6) → `scripts/verify_installer.ps1` (**11/11 PASS**).
- **The artifact hashes (this rebuild).** dist exe `1863553f…` (15.3 MB) · zip `b51b1c9f…` (43,032,010 B) · SBOM `cc88e4cc…` (448,822 B) · Setup `E39E3ADC…` (37,693,744 B; WebView2 bootstrapper unchanged at `83004A28…`). `BUILD_INFO.json`: commit `797eea0`, `worktree_state: dirty`, built 2026-09-19T20:20:02+0930. Full numbers + the journey: `installer/README.md` → "Verified journey (Inno pipeline, the §129b rebuild)".
- **The defect the rebuild caught** (this is why the artifact is probed, not just the tree): `POST /api/control/layouts {autocull: false}` answered **`autocull: True`** while the store held `False` — the return paths of `layouts_post` called `_layouts_state(block_out)` and the helper's `autocull` parameter had a DEFAULT of True, so every write (and the export/refusal paths) reported a state the store had refused. Invisible to the tree's own tests (they pinned the switch's request body, not the answer's flag) and to the UI (it re-reads the state after acting). Fixed by REMOVING the default (the parameter is now mandatory) and passing the flag at every call site — `_layouts_state(block, config_store.layout_versions_autocull(cfg))` — with a new pin (`test_layout_versions.py::test_every_write_answer_reports_the_flag_it_just_stored`, 12→13) that also greps the source for a re-added default or a call site that dropped the flag. The first build of this wave (exe `7aa420d2…`, 20:14) was superseded by the fix and rebuilt; the shipped artifacts are the 20:20 build.
- **The frozen UI, driven for real.** The artifact's own WebView2 (app 8104, CDP 9224) served the §129b fix: the View menu stayed open through a real wheel (`scrollTop 260`) and the below-the-fold **Rail** row clicked → the rail toggled; the Layout menu stayed open through a wheel, the row read `✓Auto-cull old versions`, clicking it flipped the route's flag. Payload parity checks prove `menubar.js` / `windows-ui.js` / `windowing.js` / `help-data.js` in `_internal/` are byte-identical to this tree, and the route checks prove the Python half (`.py` sources live in the PYZ, so file hashes cannot stand in for them).
- **Gates.** pytest **1,749 / 3 skipped / 0 failed** (+1 pin) · identical under `PYTHONUTF8=0` · AUDIT CLEAN · ruff (0.16.7) clean · 40/40 node selftests · installer journey 11/11 · nothing installed on this machine afterwards (no ARP entry, no Start Menu entry — his dev shortcut untouched), `%APPDATA%\OrderFlowAnalysisPro` intact, all scratch cleaned.
- **Owed.** Unchanged: the owner's physical multi-monitor pass (§128), commit/publish on his word (drafts first). To SEE §128+§129+§129b himself he only has to relaunch his dev shortcut (or Ctrl+R the open page) — the rebuild is for the distributable lane.

**§130 — The owner's question about the Order-flow engine's symbol row: "is this functioning correctly, and is there a need for a drop-down with correct associated selections?" — answered by measurement, and one real defect fixed (the frame titles never followed the instrument). (2026-09-19; nothing committed; source-only — the dist/zip/SBOM/Setup built at §129c do NOT carry this fix)**

- **The report.** A screenshot of the engine head: the frame bar reading `ORDER-FLOW ENGINE · BTCUSDT` over a panel whose own symbol box read `ETHUSDT`, beside the quick picker showing `ETHUSDT — Crypto`, with the freshness chip at `aging · 35 s`.
- **Reproduced against a COPY of his config** (scratch APPDATA, his real `%APPDATA%\OrderFlowAnalysisPro\config.json` never written): 49 instruments, ETHUSDT configured + enabled, engine streaming 7 (BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, TRXUSDT, SUIUSDT, APTUSDT).
- **What is functioning (verified live, not inferred).** The top bar lists exactly the STREAMING instruments and drives every panel; the engine's picker lists all 49 configured, grouped `streaming now` → `enabled` → `configured — off`, each labelled `SYMBOL — AssetClass`; picking a streamed symbol moves the panel's own symbol AND mirrors the app-wide one (~1 s, store confirmed through `/api/control/ofx`); picking a switched-off crypto one answers `◌ not enabled` + the Enable&restart sentence; a Stock the feed cannot serve answers `⚠ not on this source`; an unconfigured symbol answers `? unknown` with the reason and the look-up row.
- **The defect: the widget titles never followed the instrument.** `titleToken()` reads the top bar at paint time, but the refresh lives in the shell's status pass and NOTHING called it on a symbol change — measured: minutes after moving to ETHUSDT / SOLUSDT / XRPUSDT every frame still read `· BTCUSDT`, the symbol it was BUILT with. That is precisely the owner's photographed contradiction (panel on ETHUSDT, title on BTCUSDT). **Fixed**: the top bar's `onchange` now calls `OFAPSHELL.paintStatus()` (the shell's own exported pass) after announcing `ofap:symbol`; pinned in `test_t4_trust.py` (11→12) including the assertion that the shell still exports the pass. Live re-verified: titles follow the top bar and the engine picker, and return when the symbol does.
- **Two honesty gaps left OPEN for his call (not changed).** (1) The picker's `selected` option is computed from the typed BOX value on focus, so an uncommitted typed symbol reads as the current selection while the app is still on the old one — and a re-pick of that same option fires no `change` at all. (2) The box + Enter path moves only the panel (no top-bar mirror), while a picker pick mirrors — one intent, two behaviours. Both are UX decisions (the Engine deliberately keeps its own symbol, persisted separately), so they are recorded, not silently redesigned.
- **Gates.** pytest **1,750 / 3 skipped / 0 failed** (+1 pin) · identical under `PYTHONUTF8=0` · 40/40 node selftests · AUDIT CLEAN · ruff (0.16.7) clean · probe receipts `runtime/ofap_s130*` (config-copy recon, the row matrix, the fetch-hook pick trace, the group behaviour, the fix's live verification).
- **Owed.** A decision on the two honesty gaps; a rebuild if he wants the fix inside the distributables (§129c artifacts predate it); unchanged otherwise: his physical multi-monitor pass, commit/publish on his word.

**§131 — The owner's "3×2 cells on hover" find: a whole-panel tooltip, swept out, and the same class audited app-wide. (2026-09-19; nothing committed; source-only — the §129c artifacts predate this and §130)**

- **The find.** His screenshot: `Guide & setup · 3×2 cells` floating over the panel's own prose. Measured cause: `placeFrame()` set a native `title` on the FRAME element — and a frame spans the entire widget, so every untitled thing inside it (chart, text, table, canvas) showed that box wherever the pointer sat. The suite's own sweep (both modes, menus open, the windows dialog) counted it on EVERY widget: `<section class="widget-frame"> title="Overview · 6×4 cells"` and so on, the single largest hover surface in the app.
- **The rule applied.** Hover text belongs to a CONTROL, never to a container that spans content — and a container's `title` silently becomes every untitled child's tooltip. The widget's size was the one genuinely useful fact in that string, so it moved to the resize grip, where a user reaches for it: `Drag to resize this widget — now 6×4 cells`, refreshed in `placeFrame()` on every placement change. The frame bar keeps its own `Drag to move this widget`; the frame element now carries no title at all.
- **The app-wide sweep** (mechanical, not eyeballed): every visible element with a `title`/`data-hint-title` in terminal mode (78), classic mode (92), each top-bar menu (~190 each) and the windows dialog; flagged two classes — internal vocabulary (`px`, `cells`, ids, paths) and "hover text that is the only help for a control" (containers ≥ 4,000 px² holding untitled buttons/inputs/selects). Result: **the frame was the only structural instance**; the remaining flagged strings are deliberate prose the app means to show (the Alpaca card's explanation, the Overview table's column legend, the heatmap smoothing label at 2.5/4 px, the data pill's per-endpoint ages, the storage line's `db:` path) — each on a surface whose content IS that explanation.
- **Two smaller gaps the static pass found and closed**: the Alpaca banner's *Set up now*, the symbol list's *Add* and *Save list* had no hover text of their own, so hovering them showed the CARD's paragraph (the same class at button scale) — each now says its own one-liner.
- **Receipts.** pytest **1,751 / 3 skipped / 0 failed** (+1 pin: `test_t4_trust.py::test_a_widgets_hover_text_lives_on_its_grip_not_over_its_content`, which fails if `frame.title` returns, if the grip loses `gripTip()`, or if the bar loses its move hint) · identical under `PYTHONUTF8=0` · 40/40 node selftests · AUDIT CLEAN · ruff clean · live: all four frames `frameTitle: null`, bars `Drag to move this widget`, grips `… now 6×4 cells`, and a pointer over the panel body resolves to the panel's OWN inner control (a `sy-tile`) instead of the frame. Probes `runtime/ofap_s131*`.
- **Owed.** Unchanged: his call on the §130 picker semantics, a rebuild if these source-only fixes should ride in the distributables, his physical multi-monitor pass, commit/publish on his word.

**§132 — The engine progress bar (the owner's ask): a live stage readout beside Start/Stop — green on the way up, red on the way down, honest about a stop that takes ten seconds. (2026-09-19; nothing committed; source-only — the §129c artifacts predate §130–§132)**

- **The ask.** *"Add a small loading bar near the 'START ENGINE' button that real time shows the loading stage the engine is at whilst loading to a working state… green for loading and red for shutting down… the user may get confused as to the state of the engine progression."*
- **The measurements that shaped it** (sandbox, his config copied): **START** answers in **0.47 s**, first tick **~1.8 s**; **STOP blocks the request for 10.3 s**, and the stage log shows where: `feeds` 271 ms → `history` 9 ms → **`release` 10,021 ms** (the run's own drain in `system.stop()`), then `closed`. The old shell had nothing to show for any of it — a disabled button and a pill that said "Running" until the stop landed.
- **The engine now publishes its own stages** (`EngineController.STAGE_PLAN` — keys, not sentences; the route stays the source of truth, the UI owns the words): `starting → config · instruments · build · connect`, `stopping → feeds · history · release`. `_mark()` records each boundary with a measured duration into `stage_log`; `/engine/status` serves `stage`, `stage_at` (epoch, so a bar can interpolate between polls), `stage_ms`, `stage_plan` and `stage_log`.
- **The bar** (`desktop/ui/engine-progress.js` + `.selftest.js`, mounted into the new `#engineCtl` cluster, styled in `ui.css`): a 152 px caption + 4 px track, **absolutely positioned in the top bar's empty spacer to the left of the buttons — nothing shifts when it appears**, tabular figures so the seconds never twitch, `pointer-events: none`, hidden in zen. Green up (`reading your setup → preparing instruments → building the run → connecting the feed → waiting for ticks → live`), red down (`closing the feed → flushing history → finishing the shutdown → stopped`), a hold of 1.4 s on the closing word, then it fades. **"live" is only ever written after a real print has landed** — until then it says "waiting for ticks" and creeps, and after an 8 s grace it settles honestly as "connected — no ticks yet".
- **Three defects found by driving the real page** (all fixed and re-verified): (1) the bar **re-flashed "live" every 2 s poll** while running — it now arms only on a transition it witnessed and stays quiet after settling; (2) a **stale status read already in flight when Stop was pressed painted "live / 100 %" over the fresh red bar** and stopped its fast poll, freezing the red bar for five seconds — an `expect` direction guard now drops reads of the state just left (with a 90 s TTL); (3) the **shell's own poll is held during user intent**, so the bar's first frame of a stop arrived ~4 s late — the bar now polls `/engine/status` itself while a transition runs, paints only itself, and the buttons arm it instantly on click (`begin('up'|'down')`) so even a 0.5 s start shows. A fourth, caught by the suite's own timer guard (`test_timer_guards`): the shell cannot carry the bar's beats (ui.js is frozen at 4 timers) — they live in `engine-progress.js` as ONE 120 ms beat (the status re-poll rides every fourth one) handed to `OFAPPause.register`, so `P` freezing the board never leaves a bar animating over it. A fifth, in the last live pass: the pre-click "stopped" read flashed over a fresh green bar — the stale-read guard is now bounded (1.5 s), so a start that FAILS can still land in stopped/error and say so.
- **Receipts (live, sandbox 8094 + CDP 9223, real clicks).** STOP: t+0.01 `stopping the engine` 3 % (red) → t+0.45 `finishing the shutdown` → seconds tick, fill 69→94 % → t+10.28 `stopped` 100 % (red, done) → hidden at t+13.2. START: t+0.03 `starting the engine` (green) → t+0.24 `waiting for ticks` → t+1.88 `live` 100 % → hidden. An 8 s quiet watch after settling: **0 re-flashes**. 0 client errors. The stop also produced the evidence for the docs' claim: `release` 10,018 ms of a 10.0 s stop.
- **Gates.** pytest **1,753 / 3 skipped / 0 failed** (+2 pins: `test_wiring` bar wiring incl. the one-beat + pause-registration assertions, `test_control_surface` stage plan + marks + payload) · identical under `PYTHONUTF8=0` · **41/41 node selftests** (the new `engine-progress.selftest.js` covers the phase, the captions, the fill's monotone/bounded arithmetic, the settlement text) · AUDIT CLEAN · ruff clean · probes `runtime/ofap_s132*`.
- **Files.** `desktop/engine.py` (STAGE_PLAN, `_mark`, the marks, status fields), `desktop/ui/engine-progress.js` + `.selftest.js` (new — the bar, its beat and its pause registration), `desktop/ui/ui.js` (the mount, the payload handover, button visibility through a stop, the three `begin()` calls), `desktop/ui/index.html` (`#engineCtl`, the script tag), `desktop/ui/ui.css` (the bar), `test_wiring.py`, `test_control_surface.py`.
- **Owed.** A rebuild if §130–§132 should ride in the distributables; his call on the §130 picker semantics; his physical multi-monitor pass; commit/publish on his word.

**§133 — The owner's screenshot: the §132 bar covered the Classic/Terminal switch. Placement fixed, measured. (2026-09-19; nothing committed; source-only)**

- **The report:** a picture of the progress bar's caption ("waiting for ticks · 3 s") drawn straight over the mode switch. My §132 placement assumed the space left of the button cluster was the top bar's empty spacer; it is not — the `.grow` spacer is 577 px wide and sits LEFT of `#modeSwitch`, so an absolutely-positioned bar anchored off the cluster (`right: calc(100% + 12px)`) landed on the switch. Measured before the fix: bar 1928→2080, mode switch 1949→2080, overlap true.
- **The fix:** the bar is now the cluster's **first child, in flow, with its width reserved** (`flex: 0 1 152px; min-width: 0`, `visibility: hidden` when idle with the `hidden` attribute's `display: none` overridden so the box never collapses). The top bar's spacer absorbs the width, so nothing to its right ever moves — and nothing can ever be overlapped. Crowded bars give way instead of pushing: the slot shrinks via media queries (152 → 118 → 96 px) with the caption ellipsising.
- **Receipts (live, sandbox 8094 + CDP 9223).** At the app's own width: bar 1934→2086, mode switch ends 1922 — `overlaps: []` idle AND visible, and the list of controls that moved when the bar appeared is **empty**. Narrow-width checks via `Emulation.setDeviceMetricsOverride` (1400/1200/1000 px): at 1200 px the top bar collides with ITSELF (sourcePill ↔ livePill) with the bar hidden — pre-existing, and the reason the media-query give-way exists. A real stop/start still behaves: stop t+0.01 red → `finishing the shutdown` ticking → `stopped` 100 % → faded at ~13 s; start → `waiting for ticks` → `live` at ~2.5 s; 8 s quiet watch = 0 re-flashes; 0 client errors.
- **Gates.** pytest **1,753 / 3 skipped / 0 failed** · identical under `PYTHONUTF8=0` · 41/41 node selftests · AUDIT CLEAN · ruff clean · probes `runtime/ofap_s133*`.
- **Files.** `desktop/ui/ui.css` (in-flow slot + media give-way), `desktop/ui/engine-progress.js` (insert as the cluster's first child). Skill: `references/progress-bars.md` gained the placement rule ("the space left of a right-anchored cluster is not empty; reserve the width in flow").
- **Owed.** Unchanged: a rebuild if §130–§133 should ride in the distributables, his call on the §130 picker semantics, his physical multi-monitor pass, commit/publish on his word.

**§134 — The owner's report: the top menu closed by itself, "fine at first, broken after 10-20 s… or after clicking around the menu bar a lot." Cause: the app scrolls ITSELF, and the menu obeyed every scroll event. (2026-09-19; nothing committed; source-only)**

- **Reproduced by instrumenting the page** (capture hooks for every closer the menubar obeys: scroll / focusin / blur / ofap:relayout / Tab, plus the menu's own state). Early (t+4 s) the menu opened and stayed; late (t+35 s) it closed within the attempt and the log showed why: **`scroll` on `div.wf-body | inBar=false`** — a panel, outside the bar. Registered on the strip scrollers: the suite's strips pin their scroller to the newest print (`strips.js: scroller.scrollTop = newestEnd(st)`) and the signal log sticks to its bottom (`ui.js`), so as soon as data flows a scroll fires every few seconds. My §129b fix had exempted only scrolls INSIDE the dropdown — a scroll event from anywhere else still closed the menu, and the app generates them constantly. The "clicking around a lot" version of the report is the same defect on the same clock (plus the normal toggle: clicking an already-open title closes it).
- **The fix** (`desktop/ui/menubar.js`): the closer is now the REAL user gesture — **`wheel` / `touchmove` outside the bar** (capture, passive), with the dropdown itself exempt — instead of a scroll event. The other closers are untouched: mousedown-outside (capture), focusin-outside, window blur, Tab, Escape. Tooltips of the change: a dragged scrollbar still lands on the mousedown guard; keyboard scrolling only happens after focus has left the bar, which the focus guard closes first; a programmatic/auto scroll now dismisses nothing.
- **Receipts (live, sandbox 8094 + CDP 9223).** Instrumented page counted **12 app-generated scroll events within 3 s**; a menu opened during that live scrolling **stayed open for 6 s** (was: closed immediately). A real wheel INSIDE the dropdown → stays open (§129b preserved); a real wheel OUTSIDE → closes (the rule survives); five title clicks in sequence (`view → layout → view → layout → help`) each leave that title's menu open. The original repro re-run: menu at t+35 s now reads `open: ['layout']` (was `[]`).
- **Guards updated deliberately.** `test_menus_pass.py::test_scrolling_the_open_dropdown_keeps_it_open` now FAILS if a scroll-event closer ever returns (this regression has now bitten twice) and pins the wheel/touchmove pair with the in-bar exemption and the surviving closers. `test_listener_balance.py` frozen count for `menubar.js` moved 20 → 21 with the reason recorded in the entry (one scroll listener out, two real-gesture listeners in).
- **Gates.** pytest **1,753 / 3 skipped / 0 failed** · identical under `PYTHONUTF8=0` · 41/41 node selftests · AUDIT CLEAN · ruff clean · probes `runtime/ofap_s134*` (the menubar-closer instrument and the four-point verification).
- **Files.** `desktop/ui/menubar.js`, `test_menus_pass.py`, `test_listener_balance.py`.
- **Owed.** Unchanged: a rebuild if §130–§134 should ride in the distributables, his call on the §130 picker semantics, his physical multi-monitor pass, commit/publish on his word.

**§135 — The final release audit (the owner's Desktop `final audit prompt.txt`, the 435-line "FINAL RELEASE AUDIT — v0.1b OPEN-SOURCE SHIP GATE"): SHIP ONLY AFTER REQUIRED FIXES — no P0/P1 defect found on this content; the four required items are release mechanics, not product defects. (2026-09-19; report-only — **no code changed**, nothing committed)**

- **The brief:** the owner's word — *"your directive is at final audit prompt.txt"*: phases 0–5 (baseline integrity · architecture map · domains A–F · runtime validation · finding template · staged remediation) with ten prescribed report sections. This directive had never been run on this tree (§126 was the *security* variant).
- **Decision: SHIP ONLY AFTER REQUIRED FIXES.** Report `docs/FINAL_RELEASE_AUDIT_v0.1b.md`; evidence `Desktop\OFAP_v0.1b_final_audit\00_EVIDENCE_LOG.md` (raw receipts in `evidence\`, aggregates in `receipts\audit_summary.json`, re-runnable probes in `ev\`).
- **Required before a public release** (all mechanics, no defects):
  1. **The content is uncommitted (FG-04/P2)** — 96 dirty entries (+4,338/−443 over `797eea0`), so CI has never seen it; the standing push pass is the first step, and its head run is the delta's first CI execution.
  2. **The distributables lag §130–§134 (FG-03/P2)** — `dist`/zip/SBOM/Setup are the §129c build (`BUILD_INFO` `797eea0`, dirty, 20:20:02; Setup `e39e3adc…`, 37,693,744 B); six UI files differ from source (`alpaca-card.js`, `index.html`, `menubar.js`, `shell.js`, `ui.css`, `ui.js`) and `engine-progress.js` is absent (the packaged `index.html` does not reference it — the artifact is internally consistent and passed the guard probe 23/23). A rebuild is the cheap default; shipping the snapshot is legitimate but must be a decision.
  3. **README measured claims are stale (FG-01/P3)** — badge `tests 1584` vs **1,753**; `115 vanilla-JS modules (35 selftests)` vs **126/41**; `~45,567L` vs **48,502**; File Inventory rows (Desktop UI 125/49,112 → 136/52,157; Total 246/98,326 → 248/97,356; suite 146/27,729 → 160/30,274; four line-count rows) — one simultaneous re-derivation pass, the one-pass swap rule.
  4. **Release identity (FG-02/P3)** — `pyproject 0.1.0` / README `v0.1.0-beta` / the release's own name `v0.1b`; `git tag -l` empty. Decide, then tag at the publish commit. (The **API badge is correct**: 185 OpenAPI operations + `/ws` = 186, measured from a running app.)
- **One behaviour for the owner's call (FG-05/P3, reproduced live):** with the Engine view initialised, **picking an instrument in the top bar starts the engine** — measured `stopped` → `running ['BTCUSDT']` in 2.5 s; a page that never opened the Engine view does nothing (its `ofap:symbol` listener registers on first init). Chain: `ui.js` topbar change → `ofap:symbol` → `ofx-view.js:1300` → `pickSymbol()` → `resolve` `ready` → `runInstrumentAction('start_engine')`. Designed (§82) with visible feedback (pill + the §132 bar) — document it, gate it, or say it in the toast; not a blocker.
- **Two small cleanups deferred by choice (P3):** `chartLoadWatch()` retries `loadChart()` every 5 s with no attempt cap while the chart view is open (`ui.js:416-424`); `refreshLiveChip()` spends one duplicate `GET /engine/status` per poll for its tooltip (`ui.js:296-325`; payload cost bounded by `_recent_ticks_max = 500`/symbol).
- **One flaky gate observed and characterised (FG-08/P3):** the third full-suite run of the pass showed `1 failed / 1,752 passed` — `test_hyperliquid_feed.py::test_the_listing_does_not_stop_the_mapping_when_the_rest_call_fails`; the single test then passed 3/3, the whole file 3× (27 each) and two further full runs green (`evidence/flake_check.txt`). The suite is therefore **green in 4 of 5 full runs**; the assertion text was not captured (the run was tailed), so the cause (cross-test logging state vs an async ordering race) is a hypothesis, not a conclusion. Capture `--tb=long -v` + the test order if it recurs; do not widen the assertion.
- **Re-verified live on this content (fresh receipts):** gates **1,753/3/0 on both interpreters**, **AUDIT CLEAN** (125 modules), ruff clean, **41/41 selftests**, goldens exact (analytics max diff 0.0) · fresh-profile **21/21** on a virgin `%APPDATA%` · **frozen-exe guard probe 23/23** (docs 404 ×3, served==packaged ×8, hostile Host / cross-origin / cross-site 403, loopback 200, WS 101/403) · **CSP sweep 0 violations / 0 page errors over 34 views** · **churn probe: 0 same-node accumulation, 0 detached-retained**, timers 13→14 with the Δ traced to a lazy one-time `context.js` poller (trip-diff: options-view poll released on every leave) · bounded live soak (Bybit BTCUSDT): JS heap 4.51→4.61 MB, listeners 809→810, 0 errors · secrets clean four ways · pip-audit clean (59 pkgs) · SBOM 45 components · zip 896 entries OK · **bandit now 0 High** (the B324 sha1 is gone) with 27 Medium triaged · a plain page load does **not** start the engine.
- **Carried ledger:** RA-01/02/03 fixed and **re-proven live** (hostile symbol → clamped to `IMGSRCXONERRORWINDOW.__R`, renders as TEXT, 0 parsed elements, `__RA_XSS` unset; fresh-profile export `400 + sentence`); F-05 (`AbortedSocketFilter`) and F-08 (`usedforsecurity=False`) landed; SS-1…SS-14 closed/carried with unchanged dispositions. No Critical; no High; no unpatched prior finding.
- **Honest limits stated in the report:** one physical display (no real multi-monitor pass); no long soak (owner's standing instruction — bounded stores + the memory audit stand in); no MT5 / NinjaTrader / Alpaca accounts exercised; CI has not run the delta; the frozen artifact predates §130–§134.
- **Files.** New: `docs/FINAL_RELEASE_AUDIT_v0.1b.md`. Changed: this block, `docs/RESUME.md`. Nothing else — no source file was modified: the audit's own baseline held 96 entries (66 modified + 30 untracked) and the tree now counts 97, the one new file being the report itself. All sandboxes and the frozen-exe probe were stopped; ports 8098/8099 free; scratch profiles under `%LOCALAPPDATA%\Temp\ofap_fa\`.
- **Owed.** The four required items on the owner's word (commit → README re-derivation → identity → rebuild decision); the FG-05 decision; unchanged: the owner's physical multi-monitor pass, commit/publish on his word.

**§136 — The owner's "go for all fixes": every finding the §135 release audit named, executed in one source pass with pins — README/CONTRIBUTING claims re-derived, the release identity pinned, the pick-starts-engine behaviour documented, the chart retry bounded, the duplicate status fetch removed, the flaky case's capture isolated — then re-gated and re-packaged (frozen smoke 18/18 · features 20/20 · installer journey 11/11 · frozen guard probe 23/23). (2026-09-19; nothing committed — the pass rides the worktree)**

- **The word:** *"go for all fixes"* — the standing trigger to execute the audit's register (required items + the queued cleanups) in one pass, then re-gate, re-package and close the report.
- **Fixed, each receipt-backed (file · pin · receipt):**
  1. **FG-01 — README/CONTRIBUTING claim re-derivation.** 10 `(NNNL)` values (database.py 669→673 ×3, aggregator 530→540 ×3, dashboard/app.py 1453→1461 ×2, static/footprint.js 726→749, static/orderbook.js 398→451), the three badges (code ~98k→**~102k**, tests 1,584→**1,753**; API 186 verified **correct**), both prose claims (115 modules/~45,567L → **126/~48,502L**; 35 → **41** selftests), all eight File Inventory rows + the total (246/98,326 → **258/102,412**) and the suite line (146/27,729 → **160/30,274**); CONTRIBUTING's gate baselines (1,584→1,753 passed; 35→41 selftests).
  2. **FG-02 — the release identity, in-tree.** A **Release identity** line in the README pins the package/artifact version `0.1.0` to the release tag **`v0.1.0-beta`** (the tag itself is the publish pass's act); `SECURITY.md` already used that label.
  3. **FG-05 — pick-starts-engine, documentation-only** (the least-invasive of the three options; gating it would have changed a §82 workflow the owner built on purpose): the instrument selector's own tooltip and the Instruments help topic now say it.
  4. **FG-06 — the chart retry is bounded.** `CHART_RETRY_MAX = 12`; the watch stops, the chart head reads *"the chart did not load — reselect the instrument to retry"*, and a landed load or a new selection resets the budget (`ui.js`).
  5. **FG-07 — one status read per cycle.** `refreshLiveChip(status)` reuses the payload `applyStatus` already holds; a bare call still fetches.
  6. **FG-08 — the flaky case's capture isolated.** The hyperliquid test attaches its handler to the feed's own logger with the level pinned for the duration (assertion unchanged — never widen one to chase a flake).
- **Pins:** `test_t4_trust.py` +3 (the chart-retry bound incl. the selection reset · the live chip's payload hand-over · the pick-starts-engine copy in both the tooltip and the help topic).
- **Two self-caught process defects worth the next pass's memory:** (a) my first wiring script's `apply_edit` **returned before writing** on the newline-free-anchor path — five single-line edits were reported "replaced 1x" and left untouched; only the mandatory read-back caught it. (b) the same script mapped README `(NNNL)` claims **by absolute line number**, and the release-identity line added earlier in the pass shifted every line below it, so all ten claim lookups missed with a `!!` warning that a filtered `grep` hid. Both fixed (the claim pass is now token-based and line-number-free; every wiring run's FULL output is read).
- **Gates after the pass.** pytest **1,756 / 3 / 0** on both interpreters (1,753 + 3 pins) · **41/41** node selftests · **AUDIT CLEAN** (125 modules) · ruff clean · goldens exact · a 5-run full-suite loop all green (the flake did not recur) · the README claim pass re-verifies **29 claims `ok`, 0 outstanding**.
- **The rebuild (this content).** `build_exe.py --clean` (233 developer files pruned, 62 licence texts, exe 15.3 MB) → frozen smoke **18/18** (asset parity now **79** shell refs — `engine-progress.js` is in the payload) → frozen features **20/20** → `make_release.py` → `make_installer.ps1` → `verify_installer.ps1` **11/11** → the release audit's frozen guard probe **23/23** → payload markers served from the artifact (selector tooltip, `CHART_RETRY_MAX`, `refreshLiveChip(payload)`, the help sentence).
- **Artifact hashes (this rebuild).** dist exe `bb503bcd9d9421710699ab39833afe651e1f254a0018933e2b481ae9dc88d15d` (15.3 MB) · zip `6a1926a7411818387d5f60bc0aa4dbdb406507988288102bcaec19b27d2c4907` (43,040,670 B) · SBOM `26dad36f93ee74ac56b8da8e46760c70dfbff5f9fd4b9f113a7904896f377bba` (448,822 B) · Setup `D921D58EF76394879377D978C6A2DA6F4B39AE00A259EEEED05F5B693B3C0A9F` (37,699,102 B; WebView2 bootstrapper unchanged at `83004A28…`). `BUILD_INFO.json`: commit `797eea0`, worktree dirty, built 2026-09-19T22:42:07+0930 — a `--release` build refuses a dirty tree by design, so the release build stays **one commit away**.
- **The audit report is CLOSED in place:** the closure paragraph sits in §1, each finding's ship status reads CLOSED/HARDENED (FG-04 OPEN-by-design), the validation matrix carries the post-fix gates + the new-artifact battery, and the release checklist ticks items 2, 4, 8, 9, 12, 13.
- **Nothing committed.** The pass rides the worktree (**dirty count 99** = 68 modified + 31 untracked; the pass touched `README.md`, `CONTRIBUTING.md`, `desktop/ui/ui.js`, `desktop/ui/index.html`, `desktop/ui/help-data.js`, `test_t4_trust.py`, `test_hyperliquid_feed.py` — the last two newly dirty — plus the annotated report and records).
- **Owed.** Commit/publish on his word (drafts first — the standing gate): the push pass then derives the README/CONTRIBUTING counts (already re-derived here), commits, pushes to `moddy` and watches CI to green. Unchanged: his physical multi-monitor pass.
- **Files.** `README.md`, `CONTRIBUTING.md`, `desktop/ui/ui.js`, `desktop/ui/index.html`, `desktop/ui/help-data.js`, `test_t4_trust.py`, `test_hyperliquid_feed.py`, `installer/README.md`, `docs/FINAL_RELEASE_AUDIT_v0.1b.md` (annotated), this block, `docs/RESUME.md`; `dist/` + zip + SBOM + Setup rebuilt.

**§137 — The owner's Desktop `final audit prompt.txt` re-run on the partial build: SHIP ONLY AFTER REQUIRED FIXES — the four analytics modules that existed as files and reached nothing are wired end to end (3 new REST routes + 4 UI panels + nav/help/contract entries), every repo gate is green on this content (1,899/3/0 · AUDIT CLEAN 169 routes/133 modules · 45/45 selftests), the README/CONTRIBUTING claims are re-derived again, and the new panels sit inside the listener/timer guards by integration (each poller on `OFAPPause`). (2026-09-19/20; **nothing committed** — the pass rides the worktree)**

- **The brief.** The same 434-line directive as §135, but the tree has moved: a partial build by another LLM (four engines `atlas/{gex,volatility,market_read,option_flow}.py`, three feeds `data/{tradier,marketdata,finnhub}_feed.py`, four view sections in `index.html`, an orphan `atlas/api_new_endpoints.py`) — and the owner's line one: *"audit and survey for any changes made and partial build of anything … remember DONT BREAK FUNCTIONALITY. ONLY ENHANCE."*
- **The P1 it found.** The four engines were unreachable: **no route served them** (measured 0 `/api/options/*` paths), no `*.js` claimed the views, no Help topic covered them, no `VIEWS` entry — four empty views, and a README that never mentioned the feature at all.
- **Fixed (each receipt-backed):**
  1. `atlas/options_api.py` (new, 443 lines) mounted by `launcher.build_app` → `GET /api/options/gex|volatility|flow/{symbol}`; the orphan `api_new_endpoints.py` removed after its concepts landed there; `atlas/api.py`'s `/api/atlas/market-read/{symbol}` payload completed (`_num_or_none` at the boundary).
  2. `atlas/gex.py` / `volatility.py`: rows now carry **delta, open interest, volume and the expiry stamp** (the surface's 25Δ wings were unresolvable without them; `n_expiries` read 0 on a single-expiry chain), and vanna/charm report **"not published"** rather than a fake `$0.00` (`carried` flags + `not published` in the panel).
  3. `atlas/market_read.py`: radar levels take the **tracker's real prices**; the `spot * (1+0.001·n)` placeholders survive only as a documented fallback.
  4. `ui/{gex,volatility,option-flow,market-read}.js` (new) + `index.html` (nav items, script tags, table headers, one **duplicate-id fix**: the new option-flow banner is `ofvBanner`) + `help-data.js` (4 topics + 4 `VIEWS` entries; the file repaired after a mis-anchored edit script spliced it — see the entry's process note in the report).
  5. `desktop/deribit.py`: the chain note now says when the tickers came from the 3 s cache ("(0 read, 0 failed)" read like a failure on a healthy chain).
  6. README/CONTRIBUTING/MENU_RECONCILIATION re-derived in one pass (badges ~108k / **190** API / 1,899 tests; modules 130 (45 selftests); tree `~50,285L across 133 files`; inventory rows incl. Atlas 35/11,673, Data 20/8,407, Total **273/48,419/59,164/107,583**, suite 167/31,907; rail rows 29–32 for the new views).
- **Gates after the pass.** pytest **1,899 / 3 skipped / 0 failed** (the pass began at 2 failed: `test_listener_balance.py` + `test_timer_guards.py`, both now green **by integrating** — every new poller registers with `OFAPPause`, the four modules frozen in the allow-lists with counts and reasons) · **AUDIT CLEAN** (169 routes · 160 ids · 0 missing · **0 duplicate ids** · 133 modules) · **45/45** node selftests (4 new files, 40 checks) · goldens exact · targeted gate set 213 passed.
- **Live receipts (real data, not fixtures):** GEX BTCUSDT — 36 strikes, forward-anchored window, walls + zero-gamma + DEX/VEX/theta, every row with volume, vanna/charm flagged unpublished; volatility — ATM 20.97%, 25Δ put 19.09 / call 28.38, skew −9.29pp, term structure populated; option flow — 33 prints read, 2 blocks with the venue's own reasons; the four refusal paths (no-key Tradier, no-key Market Data, quote-venue flow, engine-less market read) each answer with an actionable sentence and HTTP 200 + `ok:false`; `build_app(8097)` = **189 OpenAPI operations + /ws = 190**.
- **Report.** `docs/FINAL_RELEASE_AUDIT_v0.1b_pass2.md` — the directive's ten sections, with a findings register (FG2-01…FG2-08), a validation matrix that says **Not executed** where that is the truth (ruff absent in this environment; frozen-artifact probes need the rebuild; no physical multi-monitor pass), and a coverage matrix.
- **Files.** New: `atlas/options_api.py`, `ui/{gex,volatility,option-flow,market-read}.js` + their four selftests, `docs/FINAL_RELEASE_AUDIT_v0.1b_pass2.md`. Changed: `launcher.py`, `atlas/api.py`, `atlas/gex.py`, `atlas/volatility.py`, `atlas/market_read.py`, `desktop/deribit.py`, `desktop/engine.py` (the three new feed blocks applied to `settings`), `ui/index.html`, `ui/help-data.js`, `README.md`, `CONTRIBUTING.md`, `docs/MENU_RECONCILIATION.md`, `test_listener_balance.py`, `test_timer_guards.py`. Removed: `atlas/api_new_endpoints.py`. Scratch probes live under `profiles/deepseek/runtime/ofap_*`.
- **Owed.** Unchanged and now larger: commit/publish on his word (the delta's first CI run), a **rebuild** so `dist`/zip/SBOM/Setup carry §137 (the four panels exist only in source until then), the README badge re-check after that rebuild, his physical multi-monitor pass, and the decision list: Tradier's greeks gap for GEX, and whether the equity chain paths get a live keyed pass.

**§138 — The owner sent a screenshot of the new GEX panel and asked for an audit + repair of that module. What the audit found (the panel renders; the DATA UNDER IT did not add up), and what was repaired.**

- **Method.** A real browser against a headless instance of the app on a scratch profile (`APPDATA=profiles/deepseek/runtime/ofap_gex_audit/appdata`, port **8095**, `--headless`), driven with Playwright from the webkit venv (`profiles/deepseek/runtime/ofap_gex_audit/audit_gex.py`): rail click, Refresh, source switch to Tradier, symbol box to ETHUSDT and back, the injected `?` chip, then the same for the Volatility panel. Measured geometry, DOM text, console/network, and a 21-sample series on the Volatility term field. **0 console messages, 0 page errors, 0 failed requests** on every run.
- **FG3-01 (P1, units).** `desktop/deribit.py` hands the chain Deribit's `mark_iv`, which is a **PERCENTAGE** (13.87), while every engine in the package takes a **FRACTION** and its tests pin one (`test_gex.py:163 assert r.atm_iv == 0.15`). The live payload proved it: per-strike `iv` 19.33…56.24, `atm_iv` 20.5, `skew_25d` −10.26. The panel had hidden this behind a magnitude heuristic (`n <= 1.5 ? n*100 : n`) that mis-renders any genuinely small IV (a real 1.2% printed as **120%**). **Repaired at the boundary:** `from_deribit_ladder` converts the venue's percentage once (its docstring now says so), and both routes publish `"iv_unit": "fraction"`; both panels scale by 100 for display only, no guessing (`gex.selftest` pins `fmtIv(0.012) === '1.20%'` and `fmtIv(1.2) === '120.00%'`). Live after: `iv` 0.1894…0.5624, `atm_iv` 0.205, `skew_25d` −0.1026 — the same percentages on screen, now correct under the hood.
- **FG3-02 (P1, data loss).** `compute_gex` rounded `gamma_exp`/`dex` to **4 dp** while a crypto chain's exposures run 1e-4…1e2 — most strikes quantised to exactly `0.0000`, which flattened the ΓEX column, made its "widest exposure first" sort a tie, and coarsened the wall threshold that reads those same values. **Repaired** to 8 dp. Live after: ΓEX renders **−0.161744 / −0.063878 / +0.057342 / −0.042504** in strict descending |value| order, where before the top of the column was `−0.158100` and most rows read `0.000000`.
- **FG3-03 (P2, honesty).** Nothing said what the Σ figures were made of ("Σ DEX 1.33K" of what). The wire now carries `unit` (the coin the contract is written on — `BTC` — or `shares` for an OPRA 100-share lot) and the panel labels it: table head **ΓEX (BTC)**, card head *"ΔEX and ΓEX: BTC per 1-point move (VEX and Θ stay in the venue's own vega/theta units)"* — VEX/Θ deliberately not claimed as per-point, because the venue's vega/theta units are the venue's.
- **FG3-04 (P2, formatting).** The γ column printed 8 fixed decimals (`0.00041000`) and the ΓEX column's small end collapsed to `0.000000`. Both now follow the Options panel's own greek rule: **4.40e-4**, exponential below 1e-4, K/M/B above.
- **FG3-05 (P3, doc/code drift).** `total_vex`'s docstring and inline comment said `|gamma| * oi * iv` while the code multiplies by **vega**; the dataclass line, the comment and the legend now describe what the code does.
- **FG3-06 (P3, latent).** `subText` escaped `spot_from` before writing it through `textContent`, so an `&` in a venue's own words would have printed as `&amp;`. Plain text now; `esc()` stays where it belongs (table rows).
- **FG3-07 (P3, hardening + one observed anomaly).** `expiryLabel` guarded `getTime()` but not `toISOString()`, which **throws** a RangeError outside ±8.64e15 ms — a throw there aborts the paint loop and leaves every field after it blank. A single frozen-moment read of the Volatility panel caught exactly that shape once (all four earlier fields set, `volTerm` empty); a 21-sample series afterwards showed the field painted from t=2 s onward, and the throw path is now impossible (bounds check + try/catch, pinned in the selftest). Recorded as observed-once, cause unproven — the hardening removes the only code path that could produce it.
- **Also corrected while in there:** the Volatility smile column labelled **"Δ proxy"** now labels itself **"Δ"** with a title — the engine prefers the venue's real delta (`from_deribit_ladder` passes it) and only falls back to the linear proxy, so the old label understated the column.
- **Gates after §138.** pytest **1,899 / 3 skipped / 0 failed** · **AUDIT CLEAN** (169 routes · 160 ids · 0 missing · 0 duplicate ids · 133 modules) · **45/45** selftests · `node --check` clean on both edited modules · live browser pass clean. Files: `atlas/gex.py`, `atlas/options_api.py`, `ui/gex.js`, `ui/volatility.js`, `ui/index.html`, `ui/gex.selftest.js`, `ui/volatility.selftest.js`. Still nothing committed.
- **What was deliberately NOT changed:** the engine's delta/dex/vega math (the exposure scale is `delta/gamma × OI × multiplier`, so it is coins on Deribit and shares on a 100-share lot — now labelled, not rewritten), and the narrow ±10-strike ladder whose "25Δ" wings are really ±1.2%-from-spot strikes: a wider `?width=` is the lever, and claiming otherwise would be the kind of lie this pass exists to remove.

**§139 — The owner photographed the Volatility + Option-flow pop-outs and asked to audit, optimize, streamline and make both industry-standard. The defect behind his crop was a class-name collision (`<table class="grid">` met the layout utility `.grid { display: grid }`), and the pass rebuilt both panels around what an options desk actually reads: a real table header with right-aligned figures, ATM/ITM marking, call/put colour, open interest as counts, the venue's own contract form, a flow **tape** with premium quoted in money, and the desk numbers each panel was missing (P/C OI, total OI, IV range, days to expiry · call/put/net premium, largest print). (2026-09-20; **nothing committed** — the pass rides the worktree)**

- **Method.** Both pop-outs reproduced exactly as he has them — the launcher's `?aux=<view>&win=<id>` path serves an auxiliary window (`window.OFAPAUX === true`, `body.term-mode`, one widget, no Classic switch) — plus the same panels in the Classic shell. Playwright (webkit venv) drove each load against a headless instance on the scratch profile (port **8095**), capturing DOM text, computed styles (`display`, `text-align`, cell colours), geometry and screenshots. **0 console messages, 0 page errors, 0 failed requests** on all four loads; the two Classic view switches were real clicks (the first-run Setup assistant was skipped through its own control, as a user does).
- **FG4-01 (P1 — the defect in the screenshot).** The four §137 tables were written `class="grid"`, and `ui.css:197` owns that name for a *layout* utility (`.grid { display: grid; gap: 14px }`). A table given `display: grid` loses table layout: its `thead`/`tr` become grid items and the cells flow as inline text, which is exactly his crop — `2026-09-20 77000.00 put 41.49% -0.0003 82.4000` with no header row and no column alignment. **Fixed:** all four tables now carry the app's own data-table class (`<table class="data">`, the class the other 24 tables use). Measured live: `display: table` in all four renders (aux + classic × both panels).
- **FG4-02 (P2 — reading rules, Volatility).** Numeric columns are right-aligned (`th.num`/`td.num` added beside `table.data`); the Type cell carries the side's colour (`td.call`/`td.put`); the strike nearest spot is marked (`tr.atm`, an accent bar) and in-the-money rows are shaded (`tr.itm`); strikes read ascending with the same strike's call and put adjacent; expiry prints in the venue's contract form (**20SEP26**, ISO date kept in the cell's title); open interest prints as whole grouped counts (`fmtOi` — `1,235`, never `1234.57`). The smile's sort rule changed from steepest-IV-first to **by strike** — a smile is read left to right — and the card head says so (`34 strike(s) · by strike`).
- **FG4-03 (P2 — the chain's own desk numbers, Volatility).** New `_chain_stats(chain)` in `atlas/options_api.py` derives them from the same rows the engines read, and the volatility payload now publishes `call_oi · put_oi · total_oi · put_call_oi · iv_min · iv_max · dte`. The Surface card gained a second row: **P/C OI · Total OI · IV range · Days to expiry**. Live: P/C 0.529, total OI 2,692, IV 21.28%–56.24%, DTE 15.4 h.
- **FG4-04 (P2 — a flow panel must show the tape, not a filtered list).** The old table listed only the classified prints, so a quiet window read as an empty panel while 62 prints had actually traded, and no row said which side paid what. The route now publishes **`tape`** — every print in the window, newest first, each tagged with the class the engine gave it (sweep beats block beats unusual when a print qualifies for more than one) — plus `spot` / `spot_from` / `premium_unit`. The panel's table *is* the tape: **Time · Expiry · Strike · Type · Size · Price · Premium · Side · Class**, with the class as a chip and premium quoted in **money** against the currency's perpetual mark (the contract every crypto desk quotes against), falling back to the contract's own currency when the wire could not name one — never a guessed rate.
- **FG4-05 (P2 — the fields a flow read exists to produce).** Summary gained **Call premium · Put premium · Net premium** (signed) **· Largest print**. Live and reconciling: 0 sweeps + 1 block + 0 unusual + 99 routine = 100 prints; calls $497.4K, puts $96.2K, net **+$401.2K**; largest `84,000C ×125 · $378.8K`.
- **FG4-06 (P3 — the count that looked wrong).** The sub-line printed `100 prints read` while the banner said `62 trade(s)`. Both numbers are true and mean different things (what the venue handed back vs what fell inside the window), and a reader who sees one of them alone concludes the panel is broken. The sub now prints both when they differ: `100 prints read · 62 in the window`.
- **FG4-07 (P3 — one label per expiry).** The term-structure line still used the ISO date while the table used the contract form; both now read **18SEP26**.
- **Gates after §139.** pytest **1,899 / 3 skipped / 0 failed** · **AUDIT CLEAN** (169 routes · 0 missing · **0 duplicate ids** · 133 modules) · node selftests **49/49** in the four panel files (the whole UI suite: 45 files, 996 checks, 0 failed) · `node --check` clean on every edited module · the live browser pass clean in both window shapes.
- **Numbers re-derived (README).** Atlas row 35/**11,803** (+130, this pass's `options_api.py`) · Desktop UI row 143/**54,498** (+390: `volatility.js`, `option-flow.js`, `index.html`, `ui.css`, `help-data.js`, both selftests) · **Total 273 / 48,549 / 59,554 / 108,103** · suite unchanged at 167 / 31,907 · UI suite unchanged at 130 modules (45 selftests).
- **Files.** `atlas/options_api.py` · `ui/volatility.js` · `ui/option-flow.js` · `ui/index.html` · `ui/ui.css` · `ui/help-data.js` (both panels' topics rewritten to describe the new reading rules) · `ui/volatility.selftest.js` · `ui/option-flow.selftest.js` · `README.md` · this block · the pass-2 report's Appendix B.
- **Not changed, deliberately.** The engines' maths (exposure/premium arithmetic), the ±10-strike ladder width, and the aux windows' own geometry behaviour (§128's multi-monitor pass still owns window placement).
- **Owed.** Unchanged: commit/publish on his word; the **rebuild** so `dist`/zip/SBOM/Setup carry §137–§139; the badge re-check after that rebuild; his physical multi-monitor pass.

## ### §140 — the depth map: the hover's own truth, a scale legend, and the empty state

Owner screenshot: hovering the Market depth heatmap read the paint governor's counters and a
developer note ("Repaints: 344 painted · 6 skipped · 1 coalesced (400 ms frame budget) … This is the
reference layout performance guidance") — diagnostics on a user surface. Asked for that plus any
metric that could line the panel up with industry practice. Changes:

  * `market-pressure.js` — `GOVERNOR.note()` no longer touches `title`; the counters ride
    `data-repaints` on the canvas and `window.OFAPGOVERNOR`. The tooltip is index.html's description
    of the map again. (This was the *second* pass at that bug: the first moved the counters from
    replacing the description to being appended to it, which still left a paint budget in a hover.)
  * `atlas.js` — the map now states its colour scale: a legend bar painted from the map's own ramp
    (`heatColour` through the contrast dial, written once per ramp/cap change so it stays on the
    governed budget) plus the cap actually in force and the saturating share (`cap 42.10 · top 1%
    saturates`). A depth map whose brightness has no legend cannot be read at a glance.
  * `atlas.js` — an empty payload is a state, not a number: the panel printed `step undefined · 0
    book updates` before the first book frames and a Depth KPI of `undefined`. It now prints the
    wire's own `note` ("no data yet — start the engine or a replay"), a dash for a step the payload
    did not state, and `no book yet` for the range sub-line.
  * `heatmap-pro.js` — the readout gained the desk's own terms: each cell's share of the colour
    scale (`resting 3.42 · 76% of scale`), the change as a share of the level it moved from
    (`Δ vs prev +0.42 (+14%)`), and the book's own quote where the payload carries one (`bid · ask ·
    spread`, decimals from the instrument's tick, never from the price's magnitude). A square with
    nothing recorded says so instead of printing `undefined ·` and `resting 0.00`.

Verified: `node --check` clean on all five files; `heatmap-pro.selftest.js` **26 ok** (12 new pins —
tick decimals, share-of-scale, delta-percent, and the null guard for a payload with no cap),
`market-pressure.selftest.js` **13 ok** (one new pin: the tooltip is the map's, no `el.title =`, no
guidance sentence); whole UI suite **45 files / 1,009 ok / 0 failed**; `scripts/audit_ui_refs.py`
**AUDIT CLEAN** (133 modules, no dead ids — the legend ids included); live headless audit
(`ofap_gex_audit/audit_heatmap.py`, screenshots `hm_view.png` / `hm_page.png`): all five hover points
read the honest empty-cell sentence, **0 diagnostics in the tooltip**, status line reading the
wire's note.

Not exercised here: the map with live book data — this sandbox has no engine/replay running, so the
payload's own note (`no data yet — start the engine or a replay`) is what the map renders. The legend
paint and the data lines are pinned by the selftests and land on the pixels only when the map has
columns; on a machine with the engine up they render as described at the first book frame.

## ### §141 — the engine panel: the `– . –` badge, tick-true prices, and a snap grid that follows the instrument

Owner question: the Order-flow engine's chrome carries a small `– . –` (his reading of `— · —`) beside
the `?` — necessary, or can it be expanded? It is the shared-cursor badge (`cursor-link.js`), the tag
every panel shows for "what the crosshair is on right now"; its idle reading was three dashes naming
nothing. Plus: an industry-standard pass over the engine panel.

  * `cursor-link.js` — the idle badge says what it waits for: **`cursor: hover a chart`** (title kept:
    "the shared cursor: what every panel is reading right now"). Five panels carry it; they now read
    the same sentence in the same instant, which is what the badge was built for.
  * `ofx.js` — new `math.dpFromTick(tick)` (returns `null` = no opinion when the tick is unusable), so
    price precision comes from the instrument's own statement.
  * `ofx-view.js` — the tick the payload states (`heat.tick`) is kept in `OFX.state.data.tick`, and one
    module-scope **`pr()`** formats every price the panel prints: hover readout, selection readout, the
    `price band`/`level` lines. Decimals come from that tick (0.5 → one, 0.01 → two, 1 → none); the old
    magnitude rule (1000 → 2 dp, ≥1 → 3 dp, else 5 dp) stands in only while no tick is known.
  * `ofx-view.js` — the drawing layer's attach passed a literal **`tickSize: 0.5`**: the drawings'
    snap grid was right by luck for one instrument and wrong for every other (BTCUSDT's tick here is
    0.01). It now reads the wire's tick, with 0.5 only as the never-stated last resort.

Verified live (`ofap_gex_audit/audit_engine.py`, shots `eng_view.png` / `eng_page.png`, real feed
`data: live · 2 s`): five idle badges reading `cursor: hover a chart`, a hover filling the badge with
the same price the stage shows (`81678.11`), and prices printing at the instrument's tick (state tick
0.01 → two decimals). One regression of my own was caught by that run and fixed inside the pass: the
first `pr()` landed inside the selection readout's scope while three call sites sat in `paintReadout`,
so the engine panel reported `ReferenceError: Can't find variable: pr` (ofx-view.js) on my first live
load. `pr()` is now module-scope and the second live run is console-clean.

Gates: `ofx.selftest.js` **220 ok** (8 new `dpFromTick` pins), `cursor-link.selftest.js` **7 ok** (idle
text pin rewritten), whole UI suite **45 files / 1,024 ok / 0 failed**, `scripts/audit_ui_refs.py`
**AUDIT CLEAN** (133 modules), pytest unchanged 1,899/3/0.

Owner approved the wording (`cursor: hover a chart`, 2026-09-20) — it stays on all five panels. Open:
whether the drawings' snap grid moving from the literal 0.5 to the symbol's real tick should be
re-verified visually on a non-BTC instrument (NQ/ES at 0.25, an equity at 0.01).

## ### §142 — the standing metric sweep (owner: "purely industry standard under EVERY metric")

Asked for a sweep he does not have to re-request panel by panel. Built the instruments first, then
worked from what they proved:

  * `scripts/audit_metric_hygiene.py` (**in-repo**, stdlib, same shape as `audit_ui_refs.py`) — the
    three mechanically decidable classes: H1 a price written from the size of the number instead of
    the instrument's tick, H2 a bare `--` standing in for an absent value, H3 a paint/transfer
    counter or developer note written onto a user surface. Exit 1 means findings.
  * runtime `ofap_metric_sweep.py` / `ofap_metric_sweep2.py` (agent side, not shipped) — the wider
    passes over all 135 UI files + 106 Python modules, including "does this numeric key leave a route
    without saying its unit", with registers at `metric_sweep.json` / `metric_sweep2.json`.
  * runtime `ofap_gex_audit/audit_views.py` — the **view walker**: clicks all 38 views, reads each
    panel's rendered text and console, flags `undefined`/`NaN`/`null`/`Infinity`/stray dots.

Fixed this pass: the last price-by-magnitude site in the engine view (`ofx-view.js:684`, a §141
leftover); the absence glyph consolidated to the em dash across the desktop UI (35 JS literals, 74
inline HTML cells, 7 labelled placeholders) **and** across the legacy dashboard widgets the desktop
embeds (31 more: `OrderbookLadder`'s Bid/Ask Total and Ratio, `MicrostructurePanel`'s level/session
rows, `app.js`, `performance.js`); and `footprint.js:_fmtPrice` made tick-aware, its magnitude rule
kept only as the documented fallback.

Coverage hole the sweep found on its own: the desktop UI renders two widgets from
`orderflow_system/dashboard/static/`, so the sweep had to be extended there — both trees are now
scanned by the in-repo gate.

Deliberate exception (allow-listed in the gate): **time masks keep their shape** — `--:--:--`, `--:--`.
A pending timestamp showing its width is a convention, not an absence placeholder.

Triage of the classes that came back clean (recorded so the next sweep does not re-litigate them):
instrument constants 7 hits → 0 real (drawings.js learns `tickSize` from its adapter at `:811`, and
§141 made the engine feed it the wire's tick; `alert-format.js`'s 0.5s are operator spin-button
steps; `atr-signal.js`'s comes from `contractInfo`). Percent-vs-fraction 4 → 0 real (`gex.py`'s
`/100` *is* the §138 fix; the rest are `int(time.time()*1000)` and a comment). Counts-with-decimals
8 → 0 real (coin sizes legitimately carry decimals; the two market-pressure hits are percentages).
Unit-not-stated: 28 numeric route keys state a unit in the same payload; the remaining raw hits are
internal dicts and file-listing rows, not route payloads.

Live evidence: **38 views walked, 0 forbidden tokens, 0 console errors**; the thin views were read by
eye and are honest waiting states (`—`, `Waiting for signals...`, `no book yet`), not blanks.
pytest 1,899/3/0, UI suite 45 files / 1,024 ok / 0 failed, `audit_ui_refs.py` AUDIT CLEAN.

What this does and does not prove: it proves no user surface prints a placeholder, an absence, a
diagnostic or an unguarded value, and that no view throws. It does not by itself prove every metric's
*arithmetic* — that is the 1,899 tests plus the live reconciliations of §138–§141 (IV fraction, the
premium sum 0+1+0+99=100, book/venue cross-checks), and the per-panel reviews continue on that basis.


### §143 — the Drawings menu, audited against the charting-tool standard

Owner's ask: audit the Drawings menu (figure list + modes + line colour) and align it to industry
standard, correcting and expanding where the layer already had the capability but the surface did
not. The layer (`ui/drawings.js`) mounts on the engine stage (`ofx-view.js`), not on the `chart`
view — a live probe there finds `OFAPDRAW` loaded but detached.

Added to the surface, all backed by what the layer already supported:
- **Line width 1–4, line solid/dashed/dotted, fill off/10/20/35%** — a "Style for new drawings"
  section. Fill alpha is derived from the line colour, so a shape's wash matches its stroke.
- **Snap to 45° as a mode** — it was Shift-at-drag only; the latch now drives the same
  `snap45()` for trend line, ray and channel.
- **Undo / Redo rows with their depths**, and the redo stack itself: the undo entries are closures,
  so each structural entry now states how to re-apply itself (add re-adds the same object, move and
  reshape re-apply the geometry they ended on, remove/delete/clear re-drop). A new edit clears the
  branch, as an editor does. Keys: Ctrl+Shift+Z and Ctrl+Y.
- **Duplicate the selection (Ctrl+D)** — one undoable step, copies offset five ticks and become the
  selection; **Delete selected (Del)** and the selection count now appear in the menu.

Found while verifying, fixed in the same pass:
- The drawing **defaults did not round-trip for the snap latch**: the stored block never carried
  `snap45`, so the value survived a reload only because `load()` never wrote it back. The sanitiser
  (`desktop/config_store.py`) and `load()`/`serialize()` now carry it, and the round-trip is proven
  live (set → `save(true)` → wipe locally → `load()` → all five defaults plus the latch back).
- Pass note: `save()` is debounced 700 ms; `save(true)` is the immediate path. A first round-trip
  attempt raced the debounce and looked like a persistence bug — it was the test. Recorded so the
  next pass does not re-litigate it.

Live evidence: engine view mounted (16 tool buttons, layer canvas connected); a horizontal line placed
by a real toolbar click + mouse drag (count 1); Ctrl+D → 2; Ctrl+Z → 1; Ctrl+Shift+Z → 2;
select + Delete → 0; Ctrl+Z → back to 1; zero page errors. Gates: pytest **1,899 passed /
3 skipped / 0 failed**; `scripts/audit_ui_refs.py` AUDIT CLEAN (169 routes, 0 missing, 0 duplicate,
133 modules); `scripts/audit_metric_hygiene.py` METRIC HYGIENE CLEAN; UI selftests 45 files / 0 failed.


### §144 — the panels drawer (☰), audited as a navigation surface

Owner's ask: scan and audit the panel-directory drawer, reference industry standards, and make it
friendly, useful and tidy. The bar used is the app's own command palette (Ctrl+K, `search.js`), which
already had arrows/Enter and a keyword vocabulary per view — a second navigation surface should not be
worse than the first.

What was wrong, and what it is now:
- **Search only read the name and the one-line hint.** "ladder", "dom", "vah", "poc", "screener"
  found nothing. Each panel now carries a keyword vocabulary (the palette's own terms), matched as
  every-token-must-appear across name + hint + keywords + id, with the matched text highlighted.
- **No keyboard walk.** Now ↑↓/Home/End move a painted cursor over the visible rows in DOM order,
  Enter opens it, the cursor follows the mouse, the row scrolls into view, and the input carries
  `aria-activedescendant` — the same promises the Ctrl+K palette makes.
- **No result count, no empty state.** The head now shows "21 panels" (or "N matches"), and a miss
  says which query missed and offers a clear button.
- **Nothing showed which panel you are already on.** Rows for the open panel now say "· open".
- **The drawer painted once at boot.** Found live: opened while the app sat on CVD, it still marked
  Overview as open and showed no recents. It repaints on open now.
- **No memory.** A **Recent** rail (top five, most recent first, per browser) fills from drawer clicks
  and from ordinary nav-rail navigation; the row for where you are says so.
- **Rows read badly**: name left, description far right across a wide gap. The hint now sits next to
  the name and ellipsises; a footer line states the keys (↑↓ move · Enter open · Esc close ·
  Ctrl+K the full palette). Scoped to the drawer, so the atlas menus keep their layout.
- The placeholder was "filter panels… (type here)" — it now says what can be typed.

Verified live: drawer opens with 21 panels / 31 walkable rows; "ladder" → Depth, "poc" → Order Flow +
Profile, "volume" → Profile, "zzz" → the empty state; Home + ↑↑↑ + Enter moved the app to the
Engine; typing "heat" + ↓ + Enter landed on Heatmap; Recent rail read
`Engine · open / you are here`, `Time & Sales`, `Heatmap`; Escape and click-outside both still close;
zero console errors. Gates: pytest **1,899 passed / 3 skipped / 0 failed**; `audit_ui_refs.py` AUDIT
CLEAN (169 routes, 0 missing, 0 duplicate, 133 modules); `audit_metric_hygiene.py` METRIC HYGIENE
CLEAN; UI selftests 45 files / 0 failed. Screenshots: `drawer_full.png`, `drawer_empty.png`,
`drawer_final.png` (runtime).


### §145 — the Chart menu's rows (the view-variable settings), audited as a settings surface

Owner's ask: the same deep dive on this panel — the menubar's Chart tab, which lists the active view's
registered variables ("Enter lands on", "Imbalance ratio (R)", "Engine bar mode" …) — against industry
standards, with every metric checked and the result tidy.

The registry behind it was already sound: 130 variables, and an audit of the data found **zero**
defects — every one has a meaning, a default the store actually keeps, bounds, a valid applies-flag,
and (for enums) choices the store accepts. The surface and the wiring around it were where it fell
short:

- **Stored ids were printed raw** — `orderflow`, `same_price`, `deutan`. Rows, submenus and the editor's
  options now show human labels (Order Flow, Same price, Deuteranopia-safe), with the raw id still the
  option's value and the `path:` line unchanged. The labels come from the drawer's one view table
  (`window.OFAPVIEWS`), so a panel rename cannot drift.
- **Nothing said whether a value was still the default.** A changed row now says "· changed", offers
  "Restore default (Default)", and when it is at the default says "already at the default (…)" instead
  of an action that would do nothing.
- **Numbers printed as JavaScript stringified them.** They now print at the precision of the control's
  own step (0.7, not 0.6999999999999999).
- **The editor never stated what it was editing inside.** It now carries the registry's own words:
  "range 1 – 20 · step 0.5", "6 choices: Default · Delta body · …", "comma-separated numbers" —
  beside the applies-live / needs-restart note it already had.
- **46 numeric variables carried no unit.** 34 now state the dimension the meaning already named (x,
  quantile, share, opacity, gain, size, score); the other 12 name it in the label ("levels", "columns",
  "prints", "fills", "samples", "rows") where a unit would be noise. `atlas.footprint.equal_tolerance`
  is the one left: its dimension is not stated anywhere, so it needs your word rather than a guess.
- **Three hand-written bounds in the markup disagreed with the registry the store enforces**
  (`ofxLambda` min 100 vs 50, `ofxMinBlock` max 1,000,000 vs 1,000, `ofImbThresh` min 1 vs 0), and the
  registry offered an imbalance mode (`"both"`) that the store, the dashboard route and
  `analytics/footprint.py` do not implement. The markup now follows the registry and the third mode is
  gone — an option that silently does nothing is worse than no option. Two tests pin exactly this
  (`test_param_registry.py`); they were red in the tree when this pass started (verified red with this
  pass's registry change stashed away, so they were not this pass's doing) and are green now.

Verified live on the Engine view: rows read "Imbalance ratio (R) (x) = 4", "Value area (share) = 0.7",
"Engine bar mode — Default ›"; the submenu reads meaning, "range 1 – 20 · step 0.5", "Change…",
"already at the default (4)", "path: ofx.R"; the editor lists six labelled options whose values are the
raw ids; changing the bar mode gave "Delta body · changed" and a "Restore default (Default)" action, and
restoring returned the row to "Default" with "already at the default (Default)". Zero console errors.
Screenshots (runtime): `chartmenu.png`, `chartmenu_sub.png`, `chartmenu_editor.png`, `enum_editor2.png`.
Gates: pytest **1,899 passed / 3 skipped / 0 failed**; `audit_ui_refs.py` AUDIT CLEAN (169 routes, 0
missing, 0 duplicate, 133 modules); `audit_metric_hygiene.py` METRIC HYGIENE CLEAN; UI selftests 45
files / 0 failed.


### §145 addendum — the answer to the one open question, and the seven bounds it uncovered

The owner's word on `atlas.footprint.equal_tolerance` came back as "best option", and the code already
states it: `analytics/footprint.py` compares `abs(bid - ask) <= tol * (bid + ask)` with the comment
that the tolerance "is relative to the row's own size, so it behaves the same on a 0.0001-lot crypto
row and a 100-lot futures row" — a **share**, bounded 0–1 by the store and by the dashboard route.
So it carries `unit="share"`, and its meaning now says what the code says.

That question turned out to be the tip: the registry printed bounds the store rewrites. A probe that
writes every numeric variable's registry minimum and maximum through the real store (temp config dir,
the test fixture's own isolation) found **seven**:

| variable | registry said | the store keeps |
| --- | --- | --- |
| `ofx.R` | 1.0 – 20 | **1.5** – 20 |
| `ofx.stack` | 2 – 12 | 2 – **8** |
| `ofx.text_px` | 8 – 60 | **20** – 60 |
| `ofx.sweep_c` | 0.2 – 5.0 | 0.2 – **4.0** |
| `ofx.lambda_ms` | 50 – 5000 | **100** – 5000 |
| `atlas.footprint.imbalance_threshold` | 0.0 – 50 | **1.0** – 50 (0 is rewritten to the 3.0 default) |
| `atlas.footprint.equal_tolerance` | 0.0 – 10.0 | 0.0 – **1.0** |

The store is the enforcement point — it clamps every write — so the registry now states the store's
numbers; the two markup lines this pass had bent the other way (lambda ms 50, threshold 0) are back to
the floors the store enforces, and `ofxMinBlock`'s markup ceiling stays at the registry's 1,000 (the
store clamps no ceiling there, so the registry is the authority). The pass's own bounds change to
`ofx.R` (1.0 → 1.5) also corrected a stale constant in `test_dump_shape_and_live_values`, which had
pinned the old registry value while the markup already said 1.5.

Then the invariant is pinned, not just fixed: `test_every_registry_bound_survives_the_store` writes
every numeric variable's bounds through the store and requires them back unchanged — the same promise
`test_every_registry_enum_choice_survives_the_store` makes for choices. 12 tests in that file, all
green; the full suite is 1,900 passed / 3 skipped / 0 failed.

Verified live, Engine view Chart menu: "Imbalance ratio (R) (x) = 4 — range 1.5 – 20 · step 0.5";
"Liquidity decay (ms) = 500 — range 100 – 5000 · step 50"; **"Equal tolerance (share) = 0 — range 0 –
1 · step 0.1"**; "Imbalance threshold (x) = 3 — range 1 – 50 · step 0.5"; "Cell text threshold (px) = 45
— range 20 – 60 · step 1"; "Stacked run (levels) = 3 — range 2 – 8 · step 1". Zero console errors.
Screenshot (runtime): `bounds_live.png`.
