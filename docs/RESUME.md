# Resume here — ModFlow OrderFlow Analysis Suite

> ## ▶ RE-ATTENDANCE (latest, 2026-09-21 — **§150: competitive reanalysis v3 — report filed, nothing changed.** The owner's brief re-ran the market analysis against HEAD `0eedc0d` (now committed; clean tree, 81 ahead of `origin/master`): **`docs/COMPETITIVE_REANALYSIS_v3_2026-09-21.md`** — the §146 gap list mapped item-by-item to status (P0-1 is now a shipped *structure* with routing refused by policy; P0-2/P0-3, P1-1…P1-3, P1-5…P1-10, P2-2/P2-3 shipped and re-verified in the tree; P1-4 chart tabs, P2-1 confluence, P2-4 study packs open), the industry-norms model re-scored (**49 norms: 36 Met — 4 of them leaders — 8 Mostly/Partial, 3 deliberate gaps, 2 intentional divergences**), and the remainder ranked (chart tabs/grid · footprint-region export · render-side FPS harness · mobile host policy · study/layout packs · paper-grammar parity · Show-Original-Values diff · futures-splice note · status-bar profile name). Gates re-run on the final bytes: **2,494 / 3 / 0 · ruff 0.16.7 clean · AUDIT CLEAN (346 ids) · metric hygiene CLEAN · 57/57 selftests · live sandbox: 192 API paths, ATM templates + refusals + footprint/depth-history/quality/sessions/synthetic read live, four-venue BTCUSDT funding/OI/basis read.** Owed: commit/publish on his word, the physical multi-monitor pass, the SignPath Foundation application (route 1 chosen — pack at `docs/SIGNPATH_APPLICATION.md`; after approval, repository variable `SIGNPATH_ORGANIZATION_ID` + secret `SIGNPATH_API_TOKEN` switch the CI `sign` job live), and the word to commit+push the CI-red fix (the encoding sweep + the cross-loop test fix + the new `test_encoding_hygiene.py` pin — test/scripts only, no app code, so the shipped Setup/zip/SBOM stay valid; public HEAD `0eedc0d` carries a red CI run until it goes up) — plus, optionally, a clean BUILD_INFO re-stamp so the frozen build names `0eedc0d` (the 14:34 build carries the committed bytes but stamps `797eea0`/dirty; journey re-verified on it 11/11, Setup sha256 `abd78b3e…`).)
>
> **Resume prompt:** `OFAP: §150 filed — docs/COMPETITIVE_REANALYSIS_v3_2026-09-21.md (49 norms re-scored, 36 Met; §2 refreshed from four same-day digests filed in docs/ux-study/digests-2026-09-21/; remainder ranked in §7; §150 record in SESSION_HANDOFF). Gates 2494/3/0 · ruff + both audits clean · 57 selftests. Owed: commit/push on his word, the physical multi-monitor pass, the SignPath application (pack: docs/SIGNPATH_APPLICATION.md — then SIGNPATH_ORGANIZATION_ID + SIGNPATH_API_TOKEN turn the CI sign job on), the CI-red fix push (encoding sweep + cross-loop test fix + test_encoding_hygiene pin; 2496/3/0 verified both ways) (optional: BUILD_INFO re-stamp so the frozen build names 0eedc0d — journey re-verified 11/11 on the current Setup). Next wave per the report: chart tabs, footprint export, render FPS harness, mobile host policy, study/layout packs.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-21 — **§148: the final audit — CLOSED; every register row fixed and receipted, the public docs' counts re-derived and synced.** Baseline HEAD `797eea0`
> (2,389/3/0) re-derived against §147's claims and confirmed; the brief's seven steps are under way —
> every in-repo gate re-run green, seven read-only module audits consolidated, and each confirmed defect
> fixed **with its missing regression pin, proven to bite**. **70 fixed / 42 open (P1 0 · P2 4 · P3 38); ALL P1s are fixed** —
> the seven headline P1s (marks layer, ladder template, risk-gate binding, retention persistence,
> entry-time R, DST zones, the two why-card honesty P1s), plus **AB-01** (the alert rehearsal/test-fire
> now runs the same `at_price`/`min_age_s` scope gates the live engine refuses on, from one shared
> `_scope_gates`), **AB-02** (malformed `conditions` were silently dropped, so a typo made the rule
> fire LOUDER than authored; entries are now quarantined as never-met at the single parse point, the
> authored text kept for a save round-trip), **AB-03** (`_cap_lines` could empty the evidence
> block to make room for its `+N more` note — at the legal cap (40) the block came back "" and the
> panel claimed "the snapshot was empty"; the marked first-line cut now sits after the pop loop, so
> a block with rows never returns nothing) and **AB-04** (the block's window had no upper bound — a
> snapshot held NOW, read against an older event, dragged the current tape and the provider's own
> delta into the old event's block, making a two-minute-old event's block identical to a now event's;
> both bounds now, and a delta that ends after the block's window is not used — every live receipt
> includes its pre-fix run caught against the still-running old server, and AB-04's also covers two
> real wire fires; one new own finding filed along the way: the window labels' span claim vs the tape
> ring's real coverage), and **AB-05** (a rule authored with a non-numeric threshold threw straight
> out of `evaluate()` and rode the per-tick detection path into the feed's catch — 31 tracebacks in
> 83 s live with that tick's wire/emit/DB output lost; unreadable rules are now counted and skipped
> in `evaluate` and `evaluate_touch`, the rehearsal refuses with a sentence, and `hub._dispatch` is
> armoured — old build 31 error lines in-window, fixed build 0, `unreadable: {'ab05-typo': 303}`),
> and **AB-06** (legacy rule shapes were misread or fatal: `"channels": "telegram"` came back as
> per-letter noise while the save route answered 200, a params string or `"30s"` clock 500'd the
> save, and — the severe half — the same shapes in the stored rules failed the engine START itself;
> all shapes now read quiet: strings are lists, unreadable reads off/default, authored text is kept
> verbatim, and a junk entry becomes a visible disabled placeholder — old build start 'error',
> fixed build start running with 23/23 rules loaded), and **AB-07** (the side catalogue promises
> "bid/ask are read as the same thing": `==`/`!=` honoured it while the text `in`/`not_in` branch
> compared raw strings — an author listing "bid" built a condition that could never meet a buy, and
> `not_in ["bid"]` fired on exactly the buys it excluded; both sides of the list ops now read
> through the same `_side_word` normalisation the equality ops use — old build `in ['bid']` False on
> a buy while `not_in ['bid']` fired, fixed build True/quiet, `==` and `in` agreeing on every
> spelling), and **AB-08** (a delta over a window that held no prints printed as a measured zero —
> the block's bare "+0.00" and a `<= 0` condition meeting on it; measured as **latent on the
> shipped wiring** (both live ctx sources carry no delta, so the live kind walk showed no delta line
> at all) and real at the contract level every helper accepts — now "delta 60s: no prints", that
> delta reads unreadable so it never meets, while a genuinely balanced window keeps its
> "+0.00 (buy 50% / sell 50%)"), and **AB-09** (`notification_text()` was dead — zero production
> callers — with a docstring claiming "notify.py's formatters use this", while the real appender is
> `notify._with_context`; and the dead render had drifted: a sentence-less alert came back with a
> leading blank line and the block unstripped. It now delegates to the one appender, so a whole-alert
> render and a channel body are the same text by construction — receipted live through a real
> rehearsal answer's sentence + block and all three channel formatters), and **AB-10** (the
> conditions gate's sentence ignored the rule's `match` — an `any` rule that met one condition
> claimed "every condition is met", and any-fail said "at least one condition is not met" as if the
> bar were every; now keyed on the same reader the evaluation uses: any-pass "at least one condition
> is met", any-fail "no condition is met", `all` unchanged — live, the full matrix true over its own
> rows), and **AB-11** (the rehearsal rendered the evidence block unconditionally — a rule whose
> evidence was switched off, or whose channels wake nobody, was shown a block no notification would
> carry; pre-fix, all three shapes returned the identical block. One gate, two consumers:
> `_block_ride` decides the render in the delivery path and is reported to the client as
> `context_gate`, so the answer carries no block when none would ride — and the client names the gate
> that held it back), and **AB-12** (the JS header documented a fallback that exists nowhere — "the
> block is then the last real alert's own"; nothing supplies it, the answer carries no block, and the
> header now says so, with the invariant asserted in the selftest), and **AB-13** (the CSV block's cap
> used the text capper — a bare "+N more" line among three-field rows, a malformed table; the CSV cap
> now drops whole rows, writes the marker as a row of the same shape, and keeps the column header
> uncut — live, one-field marker rows before, three fields throughout after), and **AB-14** (the
> rehearsal read the alert log's scalarised copy of an event that fired — a cooling kind's newest
> event was invisible; it now reads the newest raw event the engine itself evaluated, same shape the
> live path read, with the log as the documented fallback; the age face was live-measured, the shape
> face is a contract matter — and one frozen assertion met the update-and-strengthen rule). **AB-15**
> made a set param a member list (a typo can no longer become a rule that can never match, and the
> panel names it — a selftest assertion that had frozen the defect was corrected, 8th instance), and
> **AB-16** re-measured the upgrade package's alert-builder counts (77 tests / 17 checks) with the
> fine print its "legacy rules behave exactly as before" claim earned. The pin-proof harness itself
> was hardened to edit and hash bytes (a CRLF file's endings had been at risk). **T5-F01..F03**: the
> funding sentence paired one venue's rate with the cross-venue median annualised (live:
> "+0.010%/8h (+9.9% annualised)" while the rate annualises to 10.95%) — the payload now carries
> `rate_apr_pct` and the sentence's parenthetical comes from it, both halves; the OI fallback no
> longer claims a span nobody measured ("over the last 0 s" → no span claim, the number's source
> named instead); OKX's contract count is no longer published under the coin's label. **T6-F02/F03/
> F06**: a folded depth cell is now the interval's newest snapshot, not a union (live: 147 levels in
> a 40-level cell → exactly 40), late-stamped books are skipped and counted (`late_skipped`), the
> ladder key is half-up everywhere (four sites; fuzz 120/240 → 0/240), the store's future-stamped
> books fall back to the stream's own clock and are counted (`future_skipped`; the day-ahead face is
> a defence the live tape cannot produce — carried by pin + harness and said so), and the panel's
> markers are drawn on their own cell's SLOT in the bucket array, newest-first under a cap (measured
> live: 154 of 400 markers one column off on the old reading, over a tape that skipped one cell).
> **T4-F2..F5** (the last four P2s): a non-finite number in `config.json` no longer 500s every
> read — and the save-time sanitiser (`config_store._feature_sanitise`, a blanket `except Exception:
> return`) that had been silently aborting mid-write now completes, so the poison no longer reaches
> the file either (`months: inf` -> `6`, measured); a user template that shadows a built-in is no
> longer deleted by the panel's copy flow; an unbounded leg weight is clamped to the panel's own
> 1000 cap; the documented `"12:00-13:00 lunch"` break keeps its label. Live two phases: the old read
> off the still-running pre-fix server (before the first edit; pre-fix shas reconstructed and
> matched), the new off the relaunched fixed build.
> **T5 wave 1 (F-04..F-10)**: the is-flat chip now reads the threshold from the settings the route
> already sends (the payload never carried it; live, the served panel went from `is-long` to
> `is-flat` on a 0.2% venue beside a 5% setting); the flat words no longer throw / print
> "undefined%" with a bare cfg; Hyperliquid's computed OI-USD is now labelled computed; the capped
> read no longer counts its own probe row (an exact-budget store read as capped); the capped note
> and trim hint quote the read's own split budget (the rows route said `capped at 60000` against its
> own 20000); and the route's order now mirrors the panel's (worst first, an unreadable letter
> leading — live, `ZZZNOSUCH` before `BTCUSDT`; the prepared helper had sorted best-first and the
> new pin caught it on its first run).
> **T5 wave 2 (F-11..F-17)**: the capped row's advice now names the setting a user can change
> (Settings ▸ Data quality ▸ Data-quality window — `param_registry` really shows it) and says why
> a retention prune cannot uncap the read (it trims the OLD end; the read counts from the
> newest); `ROUTE_PRUNE` went with its only user. The header stopped claiming `count_ticks`
> among this route's reads and now names all six repair actions. The derivatives cache carries a
> bound (`CACHE_MAX = 32`, oldest first) and the route stores through it. The dead
> `weekend_days` counter is gone — its weekday note lives at `session_open_ms`, the only live
> reader, which behaves unchanged. The gap table's header says "Last print before the gap
> (UTC)" (the selftest paints it and asserts it). And the id audit walks every module and every
> UI page — which caught a real bug the old three-file scan could not see: vwap.js mounted the
> Depth-executions card under `inCard`, an id that has never existed in this repo's history, so
> the panel never mounted; `logBody` was a stale read of the `logList` scroller; `monStatus`
> lives on monitor.html. All fixed (the intent card carries `id="tkIntentCard"`), the guide's
> "Overview" line corrected to Trackers, and the audit's own report moved from 162 ids to 344,
> missing 0 either way.
> **Closed 2026-09-21.** The last six opens landed in batch 29 (T6-F7..F11 + the AB-04-era own
> finding), then the switcher notifier + convergence waves, the program-wide control-pair matching
> audit, and the close-out: the `BLOCK_FAILED` fallback with its proven pin, every count the public
> docs claim re-derived (README/CONTRIBUTING/upgrade package), and the register's stale NEXT lines
> corrected. Register: **113 [FIXED] / 0 open** (P1 0 · P2 0 · P3 0) + 1 [VERIFIED] compose check.
> **Gates (final, 2026-09-21, §149b re-run): 2,494 passed / 3 skipped / 0 failed · ruff clean · AUDIT CLEAN (346 ids;
> 192 /api routes) · metric hygiene CLEAN · 57 selftests, 0 nonzero · pin-proof harness 154 cases, 0 problem(s) — every pin bites — and the §149b fold case makes it **155, 0 problem(s), every pin bites** (re-run complete).** Full
> record: `AUDIT_REGISTER.md` (its head carries `§148 — CLOSED`); boot map: `RESUME.md` — both in
> `C:\Users\Moddy\AppData\Local\hermes\profiles\deepseek\runtime\ofap_s148\`. **Nothing committed.**
> **Live state at close:** the windowed app was relaunched at his launch form on 127.0.0.1:8081; the engine is running on bybit, streaming 7 instruments (APTUSDT, BTCUSDT, ETHUSDT, SOLUSDT, SUIUSDT, TRXUSDT, XRPUSDT), 7 advancing.
>
> **§149/§149b supplement (same day):** the storage card gained **Clear app cache** (WebView2 caches are freed live — what the open window holds goes at the next start, through a boot flag the launcher honours) and **archive open / delete quarantine** controls (`/storage/clear_cache`, `/storage/clear_archive`, `folder/open {folder:'archive'}`); the DB size budget is set (2 GB). The Overview's **Systems board gained its hide/show button** (`#systemsHide`; the folded state persists as `ui.systems_hidden` — config, never localStorage, which the cache clear would wipe). Gates re-run: 2,494 / 3 skipped / 0 failed · ruff + both audits clean (**346 ids**) · 57 selftests · served == disk on the relaunched app · live round-trip `ui.systems_hidden` true → false. Harness re-run complete: **155 cases, 0 problems** (`runtime/ofap_s148/pin_run_s149b.txt`; the §149b scripts sit in `runtime/ofap_s149/s149b_*.py`).
>
> **Resume prompt:** `OFAP: §148 is CLOSED — 113 [FIXED] / 0 open, suite 2494/3/0, docs re-derived; §149 storage-card follow-ups + §149b systems-fold button landed (nothing committed). Read AUDIT_REGISTER.md + RESUME.md in C:\Users\Moddy\AppData\Local\hermes\profiles\deepseek\runtime\ofap_s148; owed on his word: rebuild, commit/push, the physical multi-monitor pass.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-20 — **§147: the upgrade package, applied.** The competitive
> analysis (`docs/COMPETITIVE_ANALYSIS_2026-09.md`) compiled into `docs/UPGRADE_PACKAGE_2026-09.md` and
> applied — paid features excluded by instruction. Ten workstreams, twelve new test suites (~490 tests),
> nine config blocks owned by their modules, seven routers, five new views, 13 UI selftests (455 checks),
> `docs/PERFORMANCE.md`, seven help topics. **Gates: 2,389 passed / 3 skipped / 0 failed, ruff clean,
> AUDIT CLEAN (187 routes, 0 missing), live smoke 36 route objects with every new surface 200 — including
> a `runner` template on the paper order receipt and a live Bybit funding read.** Self-caught: the
> footprint block's `clean()` does not seed keys (registered as DEFAULTS), a depth-history bound that
> disagreed with its own clamp, two dead help relations, and a shipped assertion that raised instead of
> skipping. The honest remainder is §3 of the package: broker adapters, MAE/MFE writers, chart tabs,
> study packs, options×flow confluence, depth-history retention persistence, a render-side FPS harness,
> the mobile host policy.)
>
> **State.** Full record: SESSION_HANDOFF **§147**.
>
> **Owed.** The §129c frozen rebuild (dist/zip/SBOM/Setup) · commit/publish on his word · the physical
> multi-monitor pass.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §147 closed (upgrade package applied and verified: 2389/3/0, AUDIT CLEAN 187 routes, live smoke green). Owed: the §129c rebuild, commit/publish on his word, the physical multi-monitor pass.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§136: the owner's "go for all fixes" executed — the §135 audit's whole register, in one pass with pins. FG-01 README/CONTRIBUTING claims re-derived (tests badge 1,584→1,753; 115→126 modules; total 98,326→102,412L; suite 146→160 files) · FG-02 release identity pinned in the README (`0.1.0` ⇄ tag `v0.1.0-beta`; the tag is the publish act) · FG-05 documented (selector tooltip + Instruments help say a pick can start the engine) · FG-06 chart retry bounded (`CHART_RETRY_MAX = 12`, spoken, reset on selection) · FG-07 the live chip reuses the shell's payload · FG-08 the flaky case's capture isolated to the feed's logger (assertion unchanged; no recurrence). Gates 1,756/3/0 both interpreters, 41/41 selftests, AUDIT CLEAN, ruff clean, goldens exact, a 5-run flake loop all green. Rebuilt + re-batteried: smoke 18/18 (79 shell refs) · features 20/20 · journey 11/11 · guard probe 23/23; Setup `D921D58E…` (37,699,102 B), zip `6a1926a7…`, SBOM `26dad36f…`, dist exe `bb503bcd…` (BUILD_INFO `797eea0`, dirty, 22:42:07). The audit report is annotated CLOSED; nothing committed.**)
>
> **State.** Full record: SESSION_HANDOFF **§136**. Two process defects self-caught and fixed (a wiring script that claimed unwritten edits — read-backs are mandatory; a line-number claim map that broke when an earlier edit shifted the file — the claim pass is token-based now). Dirty count 99 (68 modified + 31 untracked).
>
> **Owed.** Commit/publish on his word (the push pass then watches CI to green) · his physical multi-monitor pass.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §136 closed (all §135 fixes executed, gates 1756/3/0, smoke 18/18, features 20/20, journey 11/11, probe 23/23; report annotated CLOSED). Owed: commit/publish on his word + the physical multi-monitor pass.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§135: the final release audit (the owner's Desktop `final audit prompt.txt`) — SHIP ONLY AFTER REQUIRED FIXES, and all four required items are release mechanics, not defects: the content is uncommitted (96 entries; CI has never run it), the distributables are the §129c build (§130–§134 not in them), the README's measured claims are stale (tests badge 1,584 vs 1,753; 115 modules vs 126), and the version identity is unpinned (no tag). No P0/P1 found; guards/fresh-profile/CSP/churn re-verified live, frozen-exe probe 23/23, gates 1,753/3/0 both interpreters, 41/41 selftests. One behaviour for his call: a top-bar symbol pick starts the engine once the Engine view has initialised. Report `docs/FINAL_RELEASE_AUDIT_v0.1b.md`; evidence `Desktop\OFAP_v0.1b_final_audit\`. Report-only: no code changed, nothing committed.**)
>
> **State.** Full record: SESSION_HANDOFF **§135**. New findings: FG-01 README drift · FG-02 identity/tag · FG-03 artifact lag (6 UI files + `engine-progress.js`) · FG-04 uncommitted content · FG-05 pick-starts-engine · FG-06 chart retry cap · FG-07 duplicate status fetch · FG-08 a 1-in-5-run flaky test case (hyperliquid feed, green 6/6 in isolation). Receipts: `receipts\audit_summary.json` + `evidence\` (26 files) + `ev\` (13 re-runnable probes). No source file was touched: the audit's baseline held 96 entries and the tree now counts 97 — the one new file is the report itself.
>
> **Owed.** The four required items on his word: (1) the push pass (commit the 96-entry delta, watch CI to green), (2) the README re-derivation pass, (3) the version/tag decision, (4) the rebuild-or-ship-the-snapshot decision · the FG-05 call (document / gate / say-it-in-the-toast) · unchanged: his physical multi-monitor pass, commit/publish on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §135 closed (final release audit: SHIP ONLY AFTER REQUIRED FIXES, no P0/P1; required items = commit the delta, re-derive the README counts, pin the version/tag, decide the rebuild; FG-05 = a symbol pick starts the engine). Owed: those four on his word + the FG-05 call.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§134: the menu closing by itself, root-caused — the app scrolls ITSELF (the strips pin to the newest print, the signal log sticks to its bottom) and the menubar obeyed every `scroll` event, so the menu died mid-reach once data flowed: "fine at first, broken after 10-20 s". The closer is now the real gesture — `wheel`/`touchmove` outside the bar — with the dropdown exempt; mousedown/focusin/blur/Tab/Escape untouched. Receipts: 12 app-generated scrolls in 3 s with the menu open for 6 s (was: closed at once); wheel inside stays, wheel outside closes; a pin now fails if a scroll-event closer ever returns. Gates 1,753/3/0 both interpreters, 41/41 selftests, AUDIT CLEAN, ruff clean. Source-only.**)
>
> **State.** Full record: SESSION_HANDOFF **§134**. Diagnosed by instrumenting the page (capture hooks on scroll/focusin/blur/ofap:relayout/Tab) — the killer was `scroll` on `div.wf-body | inBar=false` at t+49 s; the scrollers are `strips.js` (pinned to the newest print) and `ui.js` (the signal log's sticky bottom). `test_listener_balance` moved menubar.js 20 → 21 with the reason recorded. Probes `runtime/ofap_s134*`.
>
> **Owed.** A rebuild if §130–§134 should ride in the distributables · his call on the §130 picker semantics · his physical multi-monitor pass · commit/publish on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §134 closed (menu-closed-by-itself: the app's own scrolling closed it; closer now wheel/touchmove; gates 1753/3/0). Owed: a rebuild decision for §130–§134, his call on the picker semantics, the physical multi-monitor pass, commit/publish.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§133: the engine bar's placement fixed — the owner's screenshot showed it covering the Classic/Terminal switch. An absolute anchor off the button cluster lands on a neighbour (measured: bar 1928→2080 over the switch 1949→2080); the bar is now the cluster's FIRST child, in flow with its width RESERVED (`flex: 0 1 152px`, `visibility: hidden` when idle, `hidden`'s `display: none` overridden), so the top bar's spacer absorbs it and nothing to its right ever moves — `overlaps: []` and an EMPTY moved-controls list, idle vs visible. Crowded bars give way (152 → 118 → 96 px) with the caption ellipsising. Gates 1,753/3/0 both interpreters, 41/41 selftests, AUDIT CLEAN, ruff clean. Source-only.**)
>
> **State.** Full record: SESSION_HANDOFF **§133** (and §132 for the bar itself). Probes `runtime/ofap_s133*` — geometry by boxes: every top-bar control's rect idle vs visible identical, the bar's box intersected against each (`overlaps: []`); narrow widths via CDP `Emulation.setDeviceMetricsOverride` (1200 px already collides pill-to-pill with the bar HIDDEN — pre-existing, and why the media give-way exists).
>
> **Owed.** A rebuild if §130–§133 should ride in the distributables · his call on the §130 picker semantics · his physical multi-monitor pass · commit/publish on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §133 closed (engine bar placement: in flow, reserved width, no overlap; gates 1753/3/0, 41/41 selftests). Owed: a rebuild decision for §130–§133, his call on the picker semantics, the physical multi-monitor pass, commit/publish.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§132: the engine progress bar (the owner's ask) — a live stage readout beside Start/Stop: green up, red down, honest about a stop that really takes ten seconds. The engine now publishes its own stages (`config · instruments · build · connect` / `feeds · history · release`) with measured durations; the bar names the stage, ticks the seconds, creeps while a stage runs, says "live" only after a real print, and fades when settled. Measured: start 0.47 s + ~1.8 s to first tick; stop 10.3 s of which `release` is 10.0 s. Five defects found by driving the real page and fixed; the bar's one beat is handed to the pause registry. Gates 1,753/3/0 both interpreters, 41/41 selftests, AUDIT CLEAN, ruff clean. Source-only.**)
>
> **State.** Full record: SESSION_HANDOFF **§132**. `EngineController.STAGE_PLAN` + `_mark()` (the route serves `stage`, `stage_at`, `stage_ms`, `stage_plan`, `stage_log`); the bar is `desktop/ui/engine-progress.js` (pure half + selftested fill/caption/settle maths) mounted into the new `#engineCtl` cluster and styled in `ui.css` — absolutely positioned in the top bar's empty spacer so nothing shifts when it appears. Green up (`reading your setup → preparing instruments → building the run → connecting the feed → waiting for ticks → live`), red down (`closing the feed → flushing history → finishing the shutdown → stopped`), 1.4 s hold on the closing word, hidden in zen. The buttons arm it on click; it polls the route itself while a transition runs (the shell's poll is held during user intent) and its single beat is registered with `OFAPPause` so `P` freezes the bar with the board.
>
> **Gates + receipts.** pytest **1,753 / 3 skipped / 0 failed** (+2 pins) · same under `PYTHONUTF8=0` · **41/41 node selftests** · AUDIT CLEAN · ruff clean · live (sandbox 8094 + CDP 9223, real clicks): stop t+0.01 `stopping the engine` 3 % → `finishing the shutdown` ticking to 95 % → t+10.3 `stopped` 100 % → hidden; start t+0.03 → `waiting for ticks` → t+1.9 `live`; 8 s quiet watch = 0 re-flashes; 0 client errors · probes `runtime/ofap_s132*`.
>
> **Owed.** A rebuild if §130–§132 should ride in the distributables · his call on the §130 picker semantics · his physical multi-monitor pass · commit/publish on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §132 closed (engine progress bar + engine stage marks; gates 1753/3/0, 41/41 selftests). Owed: a rebuild decision for §130–§132, his call on the picker semantics, the physical multi-monitor pass, commit/publish.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§131: the owner's "3×2 cells on hover" find — a whole-panel tooltip (`placeFrame` set a native title on the FRAME, so every widget in the suite showed `view · w×h cells` wherever the pointer sat, over its own chart or prose). Fixed: the frame carries no title, the size moved to the resize grip (`Drag to resize this widget — now 6×4 cells`, refreshed on every placement change); the same class swept mechanically app-wide (both modes, menus, the windows dialog) — the frame was the only structural instance; two untitled Alpaca buttons given their own one-liners. Gates 1,751/3/0 both interpreters, 40/40 selftests, AUDIT CLEAN, ruff clean. Source-only.**)
>
> **State.** Full record: SESSION_HANDOFF **§131**. The rule applied: hover text belongs to a CONTROL, never to a container that spans content — a container's `title` silently becomes every untitled child's tooltip (measured: `<section class="widget-frame" title="Overview · 6×4 cells">` on every widget). The sweep: 78 visible hover texts in terminal mode, 92 in classic, ~190 per menu, plus the dialog; internal-vocabulary and "container is the only help for a control" classes both checked (0 remaining structural hits). Probes `runtime/ofap_s131*`.
>
> **Gates + receipts.** pytest **1,751 / 3 skipped / 0 failed** (+1 pin in `test_t4_trust.py`) · same under `PYTHONUTF8=0` · 40/40 node selftests · AUDIT CLEAN · ruff clean · live: frames `frameTitle: null`, bar `Drag to move this widget`, grip `… now 6×4 cells`, pointer over a panel body resolves to that panel's own inner control.
>
> **Owed.** His call on the §130 picker semantics · a rebuild if §130+§131 should ride in the distributables · unchanged: his physical multi-monitor pass, commit/publish on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §131 closed (whole-panel hover text moved to the grip + app-wide hover-text sweep; gates 1751/3/0). Owed: his call on the picker semantics, a rebuild decision, the physical multi-monitor pass, commit/publish.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§130: the symbol row answered + one defect fixed — the widget frame titles never followed the instrument (every frame kept the symbol it was BUILT with; the fix asks the shell's own `paintStatus` on a top-bar change, pinned; gates 1,750/3/0 both interpreters, 40/40 selftests, AUDIT CLEAN, ruff clean). Two honesty gaps recorded for the owner's call: the picker's `selected` follows the TYPED box (uncommitted typing reads as current, and a re-pick of the same option fires no `change`), and the box+Enter path moves only the panel while a picker pick also mirrors the top bar. Source-only: the §129c artifacts predate this fix.**)
>
> **State.** Full record: SESSION_HANDOFF **§130**. Reproduced against a COPY of his config (his real `%APPDATA%\OrderFlowAnalysisPro\config.json` untouched): 49 instruments, engine streaming 7. Verified working: top bar = the streaming instruments and drives every panel; the engine's picker = all 49 configured grouped `streaming now / enabled / configured — off` with `SYMBOL — AssetClass` labels; picks move the panel and mirror the app-wide symbol (~1 s, store confirmed); unusable picks answer honestly (`◌ not enabled`, `⚠ not on this source`, `? unknown`). Broken: titles never repainted on a symbol change — the owner's "panel ETHUSDT / title BTCUSDT" contradiction. Fixed in `ui.js` (`OFAPSHELL.paintStatus()` after `ofap:symbol`), pinned in `test_t4_trust.py`, re-verified live.
>
> **Gates + receipts.** pytest **1,750 / 3 skipped / 0 failed** (+1 pin) · same under `PYTHONUTF8=0` · 40/40 node selftests · AUDIT CLEAN · ruff clean · receipts in `runtime/ofap_s130*` (config-copy recon, the row matrix with +0.3/+2.4/+6.4 s reads, the fetch-hooked pick trace, the group probes, the fix's live check). Skill: `orderflow-app-ops` → `references/instrument-symbol-row.md`.
>
> **Owed.** His call on the two honesty gaps (picker `selected` semantics; box vs picker path parity) · a rebuild if the fix should ride in the distributables · unchanged: his physical multi-monitor pass, commit/publish on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §130 closed (symbol-row audit + the stale widget-titles fix; gates 1750/3/0). Owed: his call on the picker semantics + a rebuild decision, the physical multi-monitor pass, commit/publish.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§129c: the owner's "rebuild" done — §128+§129+§129b frozen into dist/zip/SBOM/Setup (exe `1863553f…` · zip `b51b1c9f…` · SBOM `cc88e4cc…` · Setup `E39E3ADC…`, 37,693,744 B), battery green (frozen smoke 18/18, frozen features 20/20, installer journey 11/11), and one defect found by the rebuild itself: every `POST /api/control/layouts` answered with a DEFAULTED `autocull` flag instead of the stored one — fixed (parameter now mandatory), pinned, and re-shipped; gates 1,749/3/0 on both interpreters, AUDIT CLEAN, 40/40 selftests, ruff clean; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§129c** (and §129/§129b for the waves it carries). Launch reality check: the owner runs the DEV shortcut (`pythonw -m orderflow_system.desktop`), not the frozen build, and the page he was clicking predates §128 — so his "old" version menu was a stale page, not a stale artifact. The rebuild chain, in order, all on the same tree: gates → `build_exe.py --clean` (896 payload files, 232 pruned, 62 licence texts) → frozen smoke **18/18** → frozen features **20/20** → `make_release.py` → `installer/make_installer.ps1` → `verify_installer.ps1` **11/11**. `BUILD_INFO.json`: commit `797eea0`, worktree dirty, built 2026-09-19T20:20:02+0930. Numbers + receipts: `installer/README.md` → "Verified journey (Inno pipeline, the §129b rebuild)".
>
> **The defect the rebuild caught.** `POST /api/control/layouts {autocull:false}` answered `autocull: True` while the store held `False` — `layouts_post`'s returns relied on `_layouts_state(...)`'s DEFAULT for the new flag. Invisible to the tree's tests and to the UI (which re-reads state after acting). Fixed by making the parameter mandatory and passing the flag at every call site; pinned (`test_layout_versions.py` 12→13, including a source grep that fails if a default returns or a call site drops the flag). The wave's first build (exe `7aa420d2…`, 20:14) was superseded; the shipped artifacts are the 20:20 build.
>
> **Gates + receipts.** pytest **1,749 / 3 skipped / 0 failed** · same under `PYTHONUTF8=0` · AUDIT CLEAN (123 modules) · ruff clean · **40/40 node selftests** · frozen smoke **18/18** · frozen features **20/20** · the artifact's own WebView2 driven over CDP: wheel inside the open dropdown keeps it open (`scrollTop 260`) and the below-the-fold Rail row acts; the Layout menu's `✓Auto-cull old versions` row flips the route flag · installer journey **11/11** (install → ARP/Start Menu → headless boot → uninstall → all gone; `%APPDATA%\OrderFlowAnalysisPro` and his dev shortcut untouched) · nothing left installed, all scratch cleaned.
>
> **Owed.** The owner's **physical multi-monitor pass** (§128); commit/publish on his word (drafts first). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §129c closed (rebuild shipped + the stale-flag write answer fixed and pinned; gates 1749/3/0; smoke 18/18, features 20/20, journey 11/11). Owed: the owner's physical multi-monitor pass, commit/publish on his word.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§128: the multi-monitor system audit — send-to-any-monitor + 10 snap shapes + the unplug rescue for every panel window, in BOTH views (widget ⧉ button, menu ⇥ panel, dialog rows + "another panel" pickers, aux-window self-move, Ctrl+Alt+W / Ctrl+Alt+Shift+←→); four defects found and fixed with pins and live receipts (the View-menu dialog was unreachable — one global per module now; the stranded detector missed live off-screen windows; the single-monitor send key re-centred a hand-placed window; the aux hash came back); gates green (1,740/3/0 on both interpreters, AUDIT CLEAN, 40/40 selftests, ruff clean); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§128**; audit doc `docs/MULTIMONITOR_SYSTEM_AUDIT.md`. What a user can do now, both modes: every widget frame carries **⧉** (its own window menu, expanded to that window's send/snap panel); any open window goes to any monitor or snaps to any of 10 shapes in one click (menu ⇥, dialog buttons, the aux window's own "⇥ monitor"); the dialog's "Another panel, on any monitor" row opens ANY panel on ANY monitor already placed (Classic's route, where there is no focused widget); a window whose monitor is gone is flagged (menu ⚠ + dialog banner) with **Bring them home**; hotkeys `Ctrl+Alt+W`, `Ctrl+Alt+Shift+→/←`. Route: `POST /api/control/windows {action: move|arrange}`; state answers `open_geometry` + `stranded` (store AND live rects).
>
> **Gates + receipts.** pytest **1,740 / 3 skipped / 0 failed** (start 1,696/3; +44 in `test_aux_windows.py` + `test_windowing_ui.py`) · same under `PYTHONUTF8=0` · AUDIT CLEAN (123 modules) · ruff clean · **40/40 node selftests** · goldens untouched · live on a sandboxed launcher (8094, scratch APPDATA, CDP 9223, EnumWindows): fill → OS (0,0,2560,1384), left half → (0,0,1280,1384), stranded push (9000,40) → banner → Bring them home → (640,0), both hotkeys fired, WM_CLOSE swept every aux window, **0 client errors**. `dist/`/zip/SBOM/Setup NOT rebuilt (source+tests+docs only; §127's artifacts still the release candidates).
>
> **Owed.** The owner's **physical multi-monitor pass**; commit/publish on his word (drafts first). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §128 closed (multi-monitor audit + send/snap/rescue in both views, 4 defects fixed, gates 1740/3/0). Owed: the owner's physical multi-monitor pass, commit/publish on his word.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§127: the release-assurance fix pass — RA-01 fixed (+ its second live sink: the legend panel, caught by the re-probe) · RA-02 fixed (400 + sentence; sanitised filename; live 10/10) · RA-03 · F-05 · F-08 · gates green (1,673/3/0) · dist/zip/SBOM/Setup rebuilt + battery re-run (smoke 18/18, journey 17/17); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§127**; receipts `Desktop\OFAP_v0.1b_release_assurance_audit\evidence\x127_*.txt`. Every fix the §126 audit named is executed with pins (`test_ra_fixes.py`, 8): the readout AND the legend escape the symbol (the re-probe caught the legend as a second sink of the same class — `OFX.legend().live` carries `"${state.symbol} · Ns bars"`), the store clamps `instruments[].symbol` (the palette lanes keep `BTC/USD`), the export tag is a filename-safe component and a missing store answers `400 + sentence`, the Bybit URL is quoted, aborts are filter-dropped from the logs, and the sha1/SQL lint-noise items are annotated/static. Live: crafted symbol = TEXT in both sinks (0 parsed elements), fresh-profile export 400, `ticks-BTCUSDT-…csv` rows=1, 10/10 HTTP receipts.
>
> **Gates + artifacts.** pytest **1,673 / 3 skipped / 0 failed** · AUDIT CLEAN (123 modules) · ruff clean · 40/40 selftests · goldens exact · rebuild: Setup **37,661,860 B** sha256 `0D0BF7C5…`, zip `113be091…` (43,001,835 B), SBOM `8e2fa4b0…`, dist exe `8ae3b250…`; frozen smoke **18/18**, Setup journey **17/17 ALL PASS**.
>
> **Owed.** **Commit/publish** on his word (drafts first). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §127 closed (release-assurance fix pass + rebuilt artifacts, all receipts green). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§126: the final release assurance audit — decision: SHIP ONLY AFTER REQUIRED FIXES — RA-01 (symbol → innerHTML element injection proven live; escape + charset clamp owed) — RA-02 (data/export 500s on a fresh profile and on '/' symbols; sanitise + 400s owed) — everything else re-verified: guard family live, CSP 0 violations over 33 views, churn flat, secrets/deps/CI clean, smoke 18/18 + journey 17/17; report-only pass, nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§126**; report `docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1b.md`; evidence `Desktop\OFAP_v0.1b_release_assurance_audit\`. The audit re-derived every claim from this tree and re-checked both prior ledgers (SS-1→SS-14 all closed incl. SS-8 now done; F-01→F-04 closed/re-verified; F-05/F-07/F-08 are the only carries). Two new findings, both confirmed live on the frozen build: **RA-01** — the Engine readout's unescaped `${sym}` + no symbol charset clamp (crafted symbol produced a real `<img>` in the DOM; `.upper()` + CSP block execution); **RA-02** — `/api/control/data/export` 500s (fresh DB; '/' symbol; filename tag unsanitised). **RA-03** — `bybit_validate()` URL quoting. Ownership table complete; soak receipts in the evidence dir (harness quirk noted: its RSS column reads the launcher shim; the child's real RSS is recorded separately).
>
> **Gates.** Full stack re-run today: pytest **1,665 / 3 skipped / 0 failed** (1,668 collected) · AUDIT CLEAN (123 modules) · ruff clean · 40/40 selftests · goldens exact · security subset 83 passed · pip-audit clean · bandit triaged · smoke 18/18 · journey 17/17 · guard probe 15/17 (both failures = RA-02) · churn flat · CSP sweep clean.
>
> **Owed.** The Stage-1 fixes (RA-01 + RA-02 + RA-03) with pins → re-run gates + packaging battery → **rebuild**. Then the standing **commit/publish** on his word (drafts first). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §126 closed (release-assurance audit: ship only after RA-01/RA-02/RA-03 fixes). Owed: the fix pass + rebuild, then commit/publish on his word.`
> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§125: the last staged three + the rebuild — MT5-style novelty-gated tips ("Try next", retires by itself) · the ingest-gap provenance counter on the data pill · Bookmap's range-to-table events list + CSV · dist/zip/SBOM/installer rebuilt over the whole tree (frozen smoke 18/18, Setup journey 17/17 ALL PASS); live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§125**. The v2 reanalysis is now fully executed. **tips.js** mounts a "Try next" card in the Guide view — four tips (layouts / workspaces / alerts / journal) gated on the STORE, each a launcher (view / help topic / ☰ menu), `N of 4 un-tried`, the card removes itself once everything is tried. **`tick_gaps()`** (engine.py) + the data-pill tooltip answer "was the feed inside the tape I just read?" — a gap is wider than max(5 s, 10 × the symbol's own median), so a thin symbol's cadence is never miscalled; live: 425 ticks, 135 intervals, 0 gaps, worst 3.7 s. The heatmap's selection strip gained **"Events in region"** — the boxed band's own walls/grows/pulls/spikes from the payload's `events` (no new route), with the honest empty sentence and **Export events CSV** through `/export/save`. Then the **rebuild**: dist exe `b2eb32d8…`, Setup `5B8BF8B4…` (37,659,252 bytes), zip `917a48b2…`, SBOM `eb51942b…`; frozen smoke **18/18** (asset parity 78 shell refs byte-identical), Setup journey **17/17 ALL PASS** (silent install → installed-exe hash == dist → smoke → silent uninstall → his dev desktop shortcut untouched, `%APPDATA%` untouched).
>
> **Gates.** pytest **1665 / 3 skipped / 0 failed** (start 1653/3; +12 = engine_gaps 7 · heatmap_pro 1 · tips 4); AUDIT CLEAN (123 modules); 40/40 node selftests; ruff clean; goldens exact. Live pass on the sandbox (8099, scratch APPDATA, engine running) — pill tooltip, tips card, events box + export; no client errors. Crash note: the pass died at its certification batch's `taskkill /F /IM python.exe` (killed the agent host, not any app process); the certification was re-run identically on the frozen tree.
>
> **Owed.** **Commit/publish** on his word (drafts first). Standing follow-ups unchanged: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §125 closed (tips, ingest provenance, range-to-table, rebuild + packaging receipts; tree certified 1665/3/0). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§124: the staged fixes executed — Trackers wired (5 dark routes → 5 live cards) · control surface closed (delta family, distinct Bars labels, DEBUG filter, hover-help coverage, 9-value source list, calendar persistence) · bounds unified + the enum round-trip pin (caught a second lie) · Tools ▸ Export door · stubs decided (Recent real, list editor real, Exit truthful) · 19 preset comboboxes · toast Help→ door · profile chip; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§124**. Everything staged in `docs/COMPETITIVE_REANALYSIS_v2_2026-09-19.md` §7 that could be built this pass is built and receipt-backed: Trackers' five advertised reads (crossvenue/correlation/dots/intent/recent-trades) render on the 4 s beat; the control-surface audit's whole one-liner class closed (delta option & copy, "default"/"classic candles" split, DEBUG in the Logs filter, case-insensitive hover-help covering all four selects, Settings source list built from `/api/control/sources` → 9 live options, calendar hours/impact persisted); registry=markup=store bounds unified and pinned, and the new enum round-trip pin caught `search.default_view` (13 views offered, 6 kept — store now accepts all 13); Tools ▸ Export writes the three server CSVs through `/export/save`; the stub list decided (Reset rail order removed; **Recent** promoted — config `ui.recent`, live write→read; **list editor** real — `/params` takes lists; Exit disabled-with-reason); settings staged rows show the **was**-value; **presets.js** decorates the 19 controls; toasts carry a **Help →** door; the status bar carries the **active profile name**. Prune button, columns-rail reset modes and the ladder's ⇧-market grammar verified as already shipped (audit lines were stale — addendum added).
>
> **Gates.** pytest **1653 / 3 skipped / 0 failed** (start 1631/3; +22 across control_surface, param_registry, menus_pass, trackers_wiring, presets); AUDIT CLEAN (121 modules); 39/39 node selftests; ruff clean; live pass on the sandbox (port 8099, scratch APPDATA) — no client errors.
>
> **Owed.** **Commit/publish** on his word (drafts first). Rebuild dist/zip/SBOM/installer over this tree. Staged open: novelty-gated tips layer · MT5-ingest provenance counter · range-to-table events list.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §124 closed (staged fixes executed: Trackers wired, control surface closed, bounds pinned, Export door, stubs decided, presets, chrome). Owed: rebuild + commit/publish on his word; open: tips layer, provenance counter, range-to-table.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§123: the wizard & help audit (wizard.txt) — Esc/Enter/Tab + focus-in for every overlay · truthful ✕ (keeps your place, says so) · visited dots navigate · the dead-click class closed (bridges/start.identity were silent) · every inline card + the Guide view carry "Open in the Help Centre →" · 7 dead menu rows are doors · a new test_guide.py gate; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§123**. Audited `guide.js` (wizard + Guide view + inline cards + notices — no gate at all before this) and the Help Centre against industry norms. Fixed: overlay keyboard grammar (Esc through the overlay's own close → wizard keeps its place + speaks; Enter advances on dialog focus; Tab trapped; focus enters the dialog), the lying ✕ tooltip, inert progress dots (visited ones now navigate back), two genuinely dead `data-help` clicks (bridges, start.identity — unknown ids returned silently; now `OFAPHELP.open(id)` lands them in the Centre; note `studies` was fine — its inline topic is added at runtime by studies.js), inline cards and the Guide view now carry "Open in the Help Centre →" (`CENTRE_QUERY` covers static + runtime ids), and seven menu rows that named real panels stop saying "planned" (Replay…→Replay, Studies library→Studies, Import profile…→Profiles, Export data…→exports folder, Notifications…/History & retention…/Performance…→Settings + a spoken pointer). New `test_guide.py` pins the whole layer (door targets must be real views; inline ids must have Centre continuations; step contract; the promoted rows).
>
> **Gates.** pytest **1631 / 3 skipped / 0 failed** (start 1623/3; +8); AUDIT CLEAN; ruff clean; 38/38 node selftests; ledger guide.js (4,0); live: focus-in + Enter + Esc-toast + dot jump + Tab wrap + all four data-help clicks + both doors + three menu rows, each with receipts. Owner's app relaunched on the current tree. Push-pass deltas: tests→1631.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §123 closed (wizard/help audit: overlay keyboard, truthful close, dead clicks closed, Centre doors, 7 menu doors, test_guide gate). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§122: the dulling explained and leashed (ceiling drift measured x1.84/4 min → capped at 5%/min, smooth, pin still instant) · the Detail control (100 ms–5 s column width, live-applied) → zoom range 6 s … 75 min · atlas dials apply without restart; live-verified on his own install; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§122**. "Initially bright then dulls" was the colour ceiling (top 5% of the visible window) drifting x1.84 in 3.75 min as the window fills — measured, then leashed: the percentile stays the target, the applied ceiling walks 25% of the gap per build, capped 5%/min (a heap-light); an explicit pin bypasses the leash; `clear()` resets it; payload carries `scale_target`. Deep zoom: the **Detail** select (bucket 100 ms–5 s) now exists in the heat bar, posts the registered param and applies **live** (params endpoint re-tunes the running hub); a width change restarts the buffer with a spoken note; Window labels are time = cols × width and follow the payload. Range: 6 s … 75 min (+ `max_columns` dial → ~5.5 h).
>
> **Gates.** pytest **1623 / 3 skipped / 0 failed** (start 1614/3; +9); AUDIT CLEAN; ruff clean; 38/38 node selftests; live receipts both in the sandbox (drift x1.18 post-fix, 0.3%/14 s steps) and on the owner's install (engine streaming, heatmap ingesting, applied 3.80→3.772 vs target 3.80→3.688). Worktree dirty; HEAD `797eea0`. Push-pass deltas: tests→1623.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, config slots. Refinement notes: the Engine view's heat rides the same leashed payload (one fix, both surfaces); windows beyond 15 min need the `max_columns` dial raised.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §122 closed (ceiling leash + Detail control + live dial apply; dulling measured and fixed). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§121: the liquidity map at industry standard — the missing time anchor (server `until`) · cursor-anchored wheel zoom · middle/shift-drag pan · click-off clears the box · more zoom options (8 windows / 7 row steps) · the live chip; and the real reason zoom looked dead: the intent gate deferred the repaint behind the wheel's own 900 ms lease — deliberate paths now force past it; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§121**. His second report ("still not seeing any correct zoom… shift middle scroll wheel does nothing… box does not disappear on off click") led to a full mechanics audit — and the headline cause was in `intent.js`: every wheel leases the heatmap surface for **900 ms** and `loadHeatmap` **deferred** while held (each tick re-leased and replaced the deferred run), so with real input the repaint only landed ~1 s after the wheel stopped. §120's probe slept past the lease and counted the deferred fetch — masked. Fix: `loadHeatmap(force)` — deliberate paths (wheel, pan, dropdown) force; auto/slow poll still defers. Plus the missing server primitive: `snapshot(…, until_ms)` + `?until=` (epoch ms; payload carries `bucket_ms`/`have_from_ms`/`have_to_ms`; before-buffer answers a spoken note) and the new `ui/heatview.js` viewport module (pure zoom/pan/snap maths, 31 selftest checks; ladders 1–15 min × 60–400 rows, pinned equal to index.html's dropdowns). Grammar now Bookmap-style: wheel up = zoom in (inverted), shift+wheel / wheel on the price gutter = rows, deltaX read too; middle- or shift+drag = pan (throttled, final load on release); ←/→ pan (shift ×10); Home = live; click = clear the box (spoken); live chip + info line show "live" vs "N back"; fit snaps live.
>
> **Gates.** pytest **1614 / 3 skipped / 0 failed** (start 1599/3; +15); AUDIT CLEAN (119 modules); ruff clean; **38/38** node selftests; live receipts incl. **1 fetch within 300 ms of a wheel** (was ~1 s deferred), cursor-time drift 952 ms ≈ 1 bucket on anchored zoom, pan clamp at `haveFrom+W`, auto-pause while panned (0 fetches/6 s), shift+← exactly −10 buckets, click-off clear, Home/chip/fit → live. HEAD `797eea0`, nothing committed. Push-pass deltas: tests→1614, selftests→38, audit modules→119.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §121 closed (liquidity map: server until-anchor, heatview module, cursor-anchored zoom, pan, click-off clear, live chip; intent-deferral force path). Owed: commit/publish on his word, the standing follow-ups.`
> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§120: the liquidity map audited and made seamless — click no longer dims the map · one fetch per window change (was two) with sequenced loads and the overlay adopting the painted payload · drag tracks on the window · end-stops answer; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§120**. His report: "when i click anywhere in the liquidity map it goes darker … the scroll wheen + shift doesnt function sealessly or at all." Root causes, live-proven: the selection was **born on mousedown** — a zero-size box whose outside-dim (`rgba(6,10,18,.62)`) covered the whole canvas, so any click darkened the map; every wheel/select change fetched the heatmap **twice** (the change's `loadHeatmap` + a 280 ms `pull`) on an **unsequenced** loader (a fast scroll could land stale columns); the click-refresh hook spent a fetch per click; the drag only tracked on the canvas (a box stopped extending at its edge). Fixes: clicks anchor, boxes are born only after 4 css px of real movement and track on the **window**; one fetch per settled change — `loadHeatmap` dispatches `ofap:heat-offer` and the overlay adopts that exact payload (`state.last === A.heat.last`); `A.heatSeq` drops stale answers; refresh repaints from cache; rapid scrolls coalesce to one fetch via `deferKeyed('heatmap','snap')`; wheel/rows end-stops say their window; mark/clear-markers speak; fit = one reload. New `heatmap-pro.selftest.js` + `test_heatmap_pro.py`; ledger (14,0).
>
> **Gates.** pytest **1599 / 3 skipped / 0 failed** (start 1594/3; +5); AUDIT CLEAN (117 modules — the new selftest joins the parse sweep); ruff clean 0.16.7; **37/37** node selftests (14 new); goldens untouched; live sandbox (real engine feed, auto-refresh off): click → 0 fetches, alpha 0; drag → box + dim 158 + "selected 21 × 57 cells"; wheel/shift/keys → 1 fetch per step, payload identity true; 3 rapid → 1 fetch, correct end state; stops 0 fetches; mark 0→1 no box; clear 2→0. HEAD `797eea0`, nothing committed. Push-pass count deltas: tests →1599, selftests →37.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §120 closed (liquidity map: click/drag/wheel/shift audited and made seamless; one-fetch path; end-stops). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§119: the owner's list.txt — one menu hide (the boxed topbar toggle) · heatmap minimal no longer hides its own way back + fit really fits + m/wheel docs · the “← Back to X” context chip across help opens and task jumps; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§119**. From `Desktop\list.txt`: (1) the menu bar's duplicate in-bar hide is gone — one control, the boxed topbar toggle, B on the keys; (2) the reported “click fit → it hides, no way back” root-caused to minimal mode hiding the very field that carries the pro bar (its restore button included) — the field is now exempt (`:not(:has(.hm-pro-bar))`), the face reads “minimal: on — restore”, `m` toggles, and `fit` clears the selection + resets Window/Rows through their own dials with a message (it was a silent no-op); (3) the heatmap wheel (zoom window / shift+wheel rows) existed — now documented in the tip + `m`; the hide-sweep verified rail/zen/menu/card ways back (card folds gained a title hint); (4) new `ui/navreturn.js`: one slot of context memory around `showView` — every route into help records the origin, registered jumps (`OFAPNAV.jump`) cover the hint card, the Engine look-up, heatmap→Replay and seven menu task rows; the “← Back to …” chip paints first in the destination head; manual nav clears it.
>
> **Gates.** pytest **1594 / 3 skipped / 0 failed** (start 1584/3); AUDIT CLEAN (116 modules); ruff clean; **36/36** node selftests; both goldens; live sandbox all four items + chip visual QA; sandbox stopped, port clear. HEAD `797eea0`, nothing committed. Push-pass deltas: tests →1594, UI modules →116, selftests →36.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §119 closed (list.txt: one menu hide, heatmap minimal way-back + fit semantics + m/wheel docs, the “← Back to X” navreturn chip). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§118: the audit's safe remainder — the paper desk (Trade DOM ladder · bracket editing after entry · session ledger + CSV export · the Chart strip) · heat dimming + large-size highlight on both surfaces · the fresh-DB journal fix; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§118**; item-by-item diff: `docs/COMPETITIVE_AUDIT_DIFF.md`. Scope was "all safe and genuinely enhancing" from §117's not-built list: the **paper-only** half of Phase C (broker execution stays out — no real order path exists; every placement walks the armed switch + Lock + the one `submit()` door) plus B5's paint pair. New: `ui/ladder.js` (Trade DOM — print-centred, click grammar left=buy/right=sell, limit below / stop above, print row = market, shift = market, chips cancel; 30-check selftest; live-refused in its exact sentences, resting orders + fills + chip cancel on tape) · `paper.set_exits` + `/replay/paper/exits` + the ticket's exits row (Apply · Stop to entry · Clear — live: stop-outs and the breakeven fill) · the **session ledger** (start/submit/reject/fill/cancel/exits/end; tape clock + wall clock; card + **CSV export to the exports folder**, verified on disk) · the **Chart strip** (same account quick-fire) · `state.tick_size` on the wire + the session tick from the instrument record · `ofx.heat_dim/heat_highlight` + `atlas.heatmap.dim/highlight` (registry · store · scope editor mirrored · both bars · Engine palette alphas + live-cell outlines · Heatmap alpha pass + outlines; pixel-measured: dim 0.6 = −59 % luminance, exact restore) · the fresh-DB **journal fix** (`TRADE_JOURNAL_DDL` beside `TRADE_COLUMNS`; `paper_close` creates the table it writes to — the 500 is gone).
>
> **Gates.** pytest **1584 / 3 skipped / 0 failed** (session start 1561/3; +23 net); AUDIT CLEAN; ruff clean 0.16.7; **35/35** node selftests (ladder 30, ramp 49, scopes 5); both goldens; live sandbox (8099) with 0 `client error:` lines; sandbox stopped, port clear; HEAD `45172b1`, nothing committed.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, config slots. Future-execution notes: ladder ±10-tick window (a "N ticks per row" step is the refinement), session persistence still unused (the ledger CSV is the record).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §118 closed (paper desk: ladder/brackets/ledger/strip; heat dim+highlight both surfaces; fresh-DB journal fix; diff doc at docs/COMPETITIVE_AUDIT_DIFF.md). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§117: competitive-audit response — per-view pause completed (heatmap/CVD/Profile/Frames), user-rebindable shortcuts with conflict refusal, study collections, identity copy; live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§117**; the item-by-item diff with receipts: `docs/COMPETITIVE_AUDIT_DIFF.md`. The audit (`Desktop/audit.txt` ← `docs/COMPETITIVE_REANALYSIS_2026-09-19.md`) had been written from the stale inventory — layouts, link groups, the shortcut registry and the heat-ramp controls were already shipped; this pass built what was genuinely missing: the four remaining per-view Pause chips + arbiter gates (shared-channel deferral included); shortcut rebinding (**Change / Reset / Reset all** in the sheet, `ui.keys` config with a rebuild-sanitiser so Reset removes, capture-phase listener, boot apply, conflicts refused with the owner named); `studies.collections` (save/apply/delete + the Studies view's **Saved setups** card); the identity framing (help topic `start.identity`, Guide section, README paragraph). Phase C (terminal mode) stays out by the audit's own scoping; B5's dimming/large-size knobs deferred behind a measured need.
>
> **Gates.** pytest **1561 / 3 skipped / 0 failed** (final tree; session start 1552/3); AUDIT CLEAN; ruff clean; **34/34** node selftests (keys 57); both goldens; live sandbox (8099): hold→defer→resume on all four new chips, a rebind persisted across a page reload, a conflict refused naming `freeze (Global)`, collections save/apply/delete round trip, 0 `client error:` lines; sandbox stopped, port clear.
>
> **Owed.** **Commit/publish** on his word (unchanged; drafts first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §117 closed (competitive-audit response: per-view pause completion, shortcut rebinding, study collections, identity copy; diff doc at docs/COMPETITIVE_AUDIT_DIFF.md). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§116: Profiles shipped (switchable playbooks: save/preview/switch/update/rename/duplicate/delete/export/import + auto-switch rules + boot auto-apply + per-profile metrics incl. journal tagging) · install fix (`install.cmd`/`run.cmd`, README installer-first + per-shell table + the exact `.venv is not recognized` explainer) · artefacts rebuilt — exe `0cce8602…` · zip `b0670d36…` · Setup `bb971599…` · SBOM `2aeb2db b…`**)
>
> **State.** Full record: SESSION_HANDOFF **§116**. Profiles = a new config block + `desktop/profiles.py` + `GET/POST /api/control/profiles` (12 actions) + a rail view (`ui/profiles.js`, Alt+P) + `profiles.selftest.js`; a profile carries the 13 analysis blocks and NEVER credentials/machine paths (export-safe by construction); switch previews changed blocks + the engine-restart split; drift shows as a chip + `●` badge; journal rows are tagged with the active profile (`profile_id` column + migration); `launcher.main` applies the startup profile before serving. Install fix: the published quick start's POSIX `.venv/Scripts/activate` is the reported error in cmd.exe — `install.cmd`/`run.cmd` do the whole job with no activation step (verified by running them against a clean copy of the tree), and the README now leads with the ready-built Setup, then a per-shell activation table, then a section naming the exact error and both fixes.
>
> **Gates.** pytest **1481 / 3 skipped**; AUDIT CLEAN; ruff clean; **34/34** node selftests; payload 177 pairs clean; zip sets == dist (1,562 files, 0 diffs); journey 11/11 (1,564 files); frozen profiles round trip + CSP assertions green.
>
> **Owed.** **Commit/publish** — the GitHub page keeps showing the broken install commands until the README + `install.cmd`/`run.cmd` are pushed (his gate); the rebuilt **Setup `bb971599…` is the upload candidate** for the beta lane. Standing follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §116 closed (Profiles shipped; install fix staged; artefacts rebuilt). Owed: commit/publish on his word (README fix + Setup upload), the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§115: the audit's three weeks-tier items attended — SEC-08 CSP hash (inline gone; eval residual documented + pinned) · SEC-09 credentials write-only · SEC-32 licence texts in the build + MIT on the binaries lane; artefacts rebuilt over the hardened tree — exe `3634ab0d…` · zip `92238aa7…` · Setup `432b5e5c…` · SBOM `594872dc…`**)
>
> **State.** Full record: SESSION_HANDOFF **§115**. SEC-08: `script-src 'self' 'sha256-KK54MqkY…' 'unsafe-eval'` — the one inline block is hash-allowed, an injected inline script cannot run; frozen app re-hashes its own served bytes → `policyAllows: true`, 0 violation events; `unsafe-eval` stays on purpose (Studies runs user JS via `new Function`) with a tripwire pin; `style-src 'unsafe-inline'` stays (66 paint-only style attrs). SEC-09: `GET /config` + `/bootstrap` mask six credential paths (`••••••••`); a mask posted back = "unchanged" (merge restores stored); `""` clears; the frozen whole-config round trip leaves `config.json` byte-identical; test routes fall back to stored on a masked field; SECURITY.md updated. SEC-32: `collect_licences()` ships 62 licence files from 19 dists in `_internal/THIRD_PARTY_LICENCES/` + LICENSE/notices beside the exe; extended notices in tree (pending commit); lane `ModdySwag/ModFlow-beta-builds` now detects **MIT** (`c8af9571…`, raw hash == source LICENSE).
>
> **Gates.** pytest **1458 / 3 skipped**; AUDIT CLEAN; ruff clean; 33/33 node selftests; payload 175/175 byte-identical; zip 1,904 entries == dist set (extract-rehash 0 diffs); installer journey 11/11 (1,563 files); frozen CSP probe green; `freeze.js` 404.
>
> **Owed.** **Commit/publish** on his word (release drafts reviewed first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots. Adjacent cleanup noted: unreferenced `dashboard/static/index.html` (no CSP + unpkg script; reachable at `/static/index.html`).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §115 closed (SEC-08/09/32 attended; artefacts rebuilt & verified on the hardened tree). Owed: commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-19 — **§114: freeze-on-hover removed (owner's call, after measurement); SEC-14 derived-profile label; 3 boot-blocking wave defects + 1 build regression (numpy) fixed; the owed rebuild chain completed — exe `a35c9f60…` · zip `71b0b5c2…` · Setup `3FA88161…` · SBOM `b955acc2…` (45 comps)**)
>
> **State.** Full record: SESSION_HANDOFF **§114**. The built-in "frozen" (T4/A7 freeze-on-hover) is gone: hovering no longer suspends any canvas (measured before: heatmap hash-stable under the pointer while the feed advanced, box-select drew 0 ink; after: repaint under the pointer, box-select 40515 ink). Explicit holds untouched (P + §89 chips), re-verified live. SEC-14: profiles built from footprint-less candles are counted, persisted (legacy-DB migration), on the wire and labelled "derived" in the Profile view — live receipt 7 → shown, 0 → hidden. Wave defects fixed: `/bootstrap` + `/engine/status` 500 with any running engine (pipeline.stats), heatmap `flat` ReferenceError (never painted), storage `import os` (ruff F821). Build: `--collect-all numpy` restored the frozen MT5 bridge (frozen capability `available: true`; before: "package not installed"); pin strengthened. Frozen probes clean, installer journey 11/11, `%APPDATA%` untouched, the machine's dev desktop shortcut hash unchanged.
>
> **Gates.** pytest **1455 / 3 skipped**; AUDIT CLEAN; ruff clean; 33/33 node selftests; payload 175/175 byte-identical; zip 1,716 entries (= dist set; extract-rehash 0 diffs); `freeze.js` 404 from the frozen app.
>
> **Owed.** **SEC-08/09/32** (deliberately open, weeks-tier: CSP nonce needs the expression feature's `unsafe-eval` redesigned; SEC-09 is a read/write protocol change; SEC-32 needs the notices commit + licence texts in the build + the repo licence field). **Commit/publish** on his word (release drafts reviewed first). Standing follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §114 closed (freeze-on-hover removed; SEC-14 label; wave + build defects fixed; artefacts rebuilt & verified). Owed: SEC-08/09/32, commit/publish on his word, the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§113: private lane retired — ModFlow-beta-builds is PUBLIC; tester-gating wording removed; anonymous downloads hash-verified**)
>
> **State.** Full record: SESSION_HANDOFF **§113**. `gh repo edit --visibility public` (anonymous API confirms public; no pending invites existed). Repo description + README de-gated (`1214a606…`). Receipts without auth: the release and all three assets reachable; SBOM and Setup downloaded anonymously and hash-matched (`8c3c0683…`, `76f53ead…`). The "invite testers" item is obsolete — nothing on GitHub is gated any more.
>
> **Gates.** (unchanged) pytest 1400 / 2 skipped; AUDIT CLEAN; ruff clean; 33/33 selftests; CI green on `42ad195`.
>
> **Owed.** Follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §113 closed (beta lane public; everything downloadable without auth). Owed: the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§112: third CI flake fixed — the websocket never-drop drain budget raced the Windows timer tick (4.1 s measured vs a 5 s deadline); budget now a 30 s hang guard, assertion untouched**)
>
> **State.** Full record: SESSION_HANDOFF **§112**. `1112b5e` (docs-only) went red on 3.11 only; root cause measured: 296 fake writes × the 15.6 ms platform tick = a 4.1 s drain against a 5 s deadline. Fixed in `test_websocket_backpressure.py` (30 s hang-guard budget, same assertion); file green 4×; suite **1400/2**.
>
> **Gates.** pytest 1400 / 2 skipped; AUDIT CLEAN; ruff clean; 33/33 selftests.
>
> **Owed.** (carried) Invite beta testers as Read collaborators on the private lane; follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §112 closed (websocket drain-budget flake fixed at the root). Owed: tester invites; the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§111: the release cut — v0.1.0-beta published (prerelease) in the private lane with zip + Setup + SBOM; digests verified**)
>
> **State.** Full record: SESSION_HANDOFF **§111**. `ModdySwag/ModFlow-beta-builds` seeded (README, commit `4d6135ff…`), release published: https://github.com/ModdySwag/ModFlow-beta-builds/releases/tag/v0.1.0-beta — Setup `76f53ead…` (41,759,968 B), zip `f11450d7…` (40,830,501 B), SBOM `8c3c0683…` (448,822 B); API digests == local sha256s; the SBOM was downloaded back and hash-verified. Notes name the source commit `0123cc1`.
>
> **Gates.** (unchanged — packaging/release only) pytest 1400 / 2 skipped; AUDIT CLEAN; ruff clean; 33/33 selftests; frozen smoke 18/18; journey clean.
>
> **Owed.** Invite the beta testers as **Read collaborators** on the lane (his call). Follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §110–§111 closed (packaging + release cut: v0.1.0-beta live in the private lane, digests verified). Owed: tester invites; the standing follow-ups.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§110: packaging pass done — dist 600 files · zip 600 entries · SBOM 45 comps · Setup `76F53EAD…`, smoke 18/18, journey green; the release cut (tag v0.1.0-beta) awaits his word**)
>
> **State.** Full record: SESSION_HANDOFF **§110**. Rebuilt on the full fold-in payload: exe `e83f579b…` (15,536,784 B), zip `f11450d7…` (40,830,501 B / 600 entries), Setup `76F53EAD…` (41,759,968 B), SBOM `8c3c0683…` (45 comps, mt5 + numpy). Frozen smoke **18/18** incl. asset parity 73/73, 11/11 help PNGs, "fold-in inside" (radar endpoint + education corpus), WS native/cross refused, log clean. Journey: install 600/600, installed exe == dist, ARP `{FA4E31A6-…}` found + fully cleaned, `%APPDATA%` untouched, dev shortcut restored. Reusable scripts: `profiles/deepseek/runtime/ofap_{smoke.py,journey.ps1}`.
>
> **Gates.** pytest 1400 / 2 skipped; AUDIT CLEAN; ruff clean; 33/33 selftests (no source edits in this pass — packaging only).
>
> **Owed.** The **release cut** on his word (tag `v0.1.0-beta` with zip + Setup + SBOM assets). Follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §110 closed (packaging pass done: dist/zip/SBOM/installer rebuilt, smoke 18/18, journey green). Owed: release cut (tag v0.1.0-beta) on Moddy's word.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§109: PUSHED — fold-in + waves on ModdySwag/ModFlow-OrderFlow-Analysis-Suite (`91f337c`, CI fix `0bd9836`); CI GREEN both jobs; worktree clean; packaging still owed**)
>
> **State.** Full record: SESSION_HANDOFF **§109**. His word landed it: everything since `110c568` pushed to `moddy` (205 files, +33.5k) with **docs/GOLDEN_FEATURES.md**, a README Golden Features section and two 1920×1080 shots in `docs/screenshots/`; counts re-derived (tests 1400, code ~84k, API 180, help 81 topics). First CI run red on two CI-only failures — the P2-3 frame-yield checks (real-time flake, red since `110c568`) and the machine-dependent NT bridge test (`ok=True` needs a live NinjaTrader AddOns state) — fixed in `0bd9836` (fake clock; stubbed detect; sources now resolve under `src/`). CI run `35293195447` green on 3.11 + 3.12.
>
> **Gates.** pytest **1400 passed / 2 skipped**; AUDIT CLEAN; ruff clean; 33 node selftests / 0 failing; ofx 208/0 ×15 reruns.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt** — Phase 6 on his word. Follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §109 closed (fold-in + waves PUSHED, CI green, worktree clean). Owed: packaging pass (Phase 6) on Moddy's word.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§108: hotfix — the Help search's stale-results crash (help.js:476) fixed + pinned; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§108**. Symptom: `Cannot read properties of null (reading 'results')` at `help.js:476:43` in the error strip. Cause: clearing the search nulled `state.results` but the pane re-rendered only when a topic was open — leftover result buttons stayed clickable and the handler read the null set. Repro'd live, fixed (pane always replaces; handler guards), pinned (`test_help.py` 33/33), verified clean after. Pre-existing latent bug, surfaced by Phase 5's heavy Help use.
>
> **Gates.** pytest **1399 passed / 2 skipped**; AUDIT CLEAN; ruff clean; 33 node selftests / 0 failing.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, dirty 188). **Next: Phase 6 packaging — only on his word.**
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §107–§108 closed (Trader Dale fold-in COMPLETE; Help search crash hotfixed). Owed: packaging pass (Phase 6) on Moddy's word; nothing committed (110c568).`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§107: Trader Dale fold-in Phase 5 executed — the education layer (U4); fold-in Phases 1–5 COMPLETE, packaging (Phase 6) remains; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§107**; plan: `docs/TRADERDALE_ORDERFLOW_PLAN.md` (Phases 1–5 all executed). Help Centre gains the **Reading the market** group — six topics (`method.reading_order`, `method.confirmations`, `method.first_test`, `method.levels`, `method.radar`, `method.vwap`) teaching the workflow, the side convention, first-test discipline, the level sources, the radar states and the VWAP band playbook; a wizard step ("Reading the market (optional)") spliced before the wizard's ending with Scanner/Engine/topic buttons; two real screenshots (`help/scanner-radar.png`, `help/area-profile.png`). test_help 32/32.
>
> **Gates.** pytest **1398 passed / 2 skipped**; AUDIT CLEAN; ruff clean; 33 node selftests / 0 failing.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, dirty 188). Follow-ups: radar walls / big-trade zones, spent-state persistence, B5 migrations, config slots. **Next: Phase 6 packaging — only on his word.**
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §107 closed (Trader Dale fold-in COMPLETE, Phases 1–5; education shipped). Owed: packaging pass (Phase 6) on Moddy's word; nothing committed (110c568).`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§106: Trader Dale fold-in Phase 4 executed — the Level Radar (G1) + signals-machine widening (U3); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§106**; plan: `docs/TRADERDALE_ORDERFLOW_PLAN.md` (Phases 1–4 done; Phase 5 education remains). **G1 shipped:** `atlas/radar.py` — one lifecycle (armed → approaching → defended/confirmed → spent/failed) over every level source (unfinished, nodes, virgin POCs, week/month POC ladder, area-POC watch rules, VWAP band pair, stacked zones), merged sources = confluence, held-first vs broke-later kept distinct (defended vs failed). Hub steps it on ticks and dispatches `radar_level`; Scanner gains a sortable **Radar** column; endpoints `GET /api/atlas/radar[/{symbol}]`; alert kind `radar_level` + `states` param + default `radar-held` rule; 6 Settings dials under "Level radar". **U3:** `hub.level_hook` → `aggregator.set_watching` for every new level (behind `atlas.radar.feed_signals`), `LevelType` widened. Live (sandbox 8097, real-DB candle sample via replay): armed → approaching → spent, then a genuine defended (2 touches); 10 plain-sentence firings; Scanner row `0 armed · 0 approaching · 1 held`; served hashes == disk; 0 client errors.
>
> **Gates.** pytest **1398 passed / 2 skipped**; AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing** (ofx 208, alert-format 20); config golden regenerated.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, dirty 186). Follow-ups: radar walls / big-trade zones as sources, spent-state persistence, B5 migrations, config slots. Next: **Phase 5 — education** (U4 help topics + guide step), then packaging on his word.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §106 closed (Trader Dale fold-in Phase 4: Level Radar + U3 shipped; plan at docs/TRADERDALE_ORDERFLOW_PLAN.md). Owed: packaging pass; nothing committed (110c568). Next: Phase 5 education.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§105: Trader Dale fold-in Phase 3 executed — the Area Volume Profile + "Watch this level" hand-off (G3/A3); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§105**; plan: `docs/TRADERDALE_ORDERFLOW_PLAN.md` (Phases 1–3 done; Phase 4 Level Radar + Phase 5 education remain). A3 shipped: shift+drag a region on the Engine → volume-at-price over the box — `math.areaVolumeProfile` (pure, pinned; ofx selftest 197→208), POC solid + VAH/VAL dashed on the stage, the strip's own "area profile" block (cells + dpr-correct histogram + honest "no depth rows" wording), Export CSV carries the rows, **Watch this level** writes an `ap-` rule. New alert kind **`level_touch`**: `AlertEngine.evaluate_touch` fires on the outside→inside transition only (re-arms on leave, cooldown applies); `hub.on_tick` carries it through the extracted `_emit_fired` (detections and touches share one firing path). Live (sandbox 8096, real demo ladder): 7-bar selection → 128-row profile, POC 99078.44, watch rule `at_tol 0.44872` (=2×step) created + deleted, export file verified end-to-end, canvas law holds, 0 client errors.
>
> **Gates.** pytest **1385 passed / 2 skipped**; AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing** (ofx 208, alert-format 20); config golden untouched.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, dirty 182). Next: **Phase 4 — the Level Radar** (the golden one), then Phase 5 education.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §105 closed (Trader Dale fold-in Phase 3: area VP + level_touch watch shipped; plan at docs/TRADERDALE_ORDERFLOW_PLAN.md). Owed: packaging pass; nothing committed (110c568). Next: Phase 4 Level Radar, Phase 5 education.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§104: Trader Dale fold-in Phases 1–2 executed — level reads (unfinished business + node persistence) shipped; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§104**; the study + plan: `docs/TRADERDALE_ORDERFLOW_PLAN.md` (approved "go with everything"; Phases 3–4 pending). Phase 1 detectors: `atlas/unfinished.py` / `nodes.py` / `confluence.py`, `profiles.period_pocs`, shape stories — pure + pinned. Phase 2: hub `feed_bar` fed from candle close; alert kinds `unfinished_business` / `node_zone` with sentences; config `atlas.unfinished` / `atlas.nodes`; `GET /api/atlas/levels/{symbol}` (unfinished + nodes + confluence + the week/month POC ladder); Engine overlay (dashed magnets + amber node bands, theme-owned colours, legend rows), Profile shape read; one live-caught bug (promise order swap) fixed and proven by served-module markers + the honest note flowing. Live sandbox 8095: 0 client errors; served hashes == disk.
>
> **Gates.** pytest **1378 passed / 2 skipped**; AUDIT CLEAN; ruff (0.16.7) clean; **33 node selftests / 0 failing** (ofx 197, alert-format 20); config golden regenerated.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`). Next per the plan: **Phase 3 Area Volume Profile** → **Phase 4 Level Radar** → Phase 5 education.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §104 closed (Trader Dale fold-in Phases 1–2: level reads shipped; plan at docs/TRADERDALE_ORDERFLOW_PLAN.md). Owed: packaging pass; nothing committed (110c568). Next: Phase 3 Area VP, Phase 4 Level Radar.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§103: Wave B complete — B3–B18 shipped (T10–T15); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§103**. Six packages, display/settings only, each with pins + a node selftest where a pure half exists + live receipts on one sandbox (0 client errors; the canvas law holds at zoom 1 / 1.25 / 1 — 824=824, 581=581, 824=824; `@BTCUSDT` → five deep-launch rows; the artifact refusal text; the rail observe → three rows). Headlines: **B3/B13/B16** heat smoothing + candle degrade (defaults **auto/on** — one word to flip) + the price-scale menu (Ctrl+Shift+R reset); **B14/B15/B17** UI scale (Ctrl± / Ctrl+0) + contrast tiers + link-group colours (the letter always stays); **B18** `@TAG` deep-launch + **B9** per-instrument scoping (`ofap:scopes`) + **B10** config artifacts (schema-stamped; refusals touch nothing); **B11** ticks consequence chip + **B12** bounded undo & multi-select; **B6** look-up overlay + **B7** Inbox view (reads the engine's own firings); **B4** columns rail (reset semantics pinned) + **B5** the one-table component (Watchlist trial behind `ui.table_component`).
>
> **Gates.** pytest **1354 passed / 2 skipped** (+42 across T10–T15); AUDIT CLEAN; ruff (CI pin 0.16.7, via `uvx`) clean; **33 node selftests / 0 failures** (+4 files); goldens green in-suite; live pass 0 client errors; sandbox stopped, port clear, real config untouched.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, **168 dirty entries**). Wave B follow-ups per the study: B5 migrations (tape/journal/logs/trackers onto the table component), named config slots.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §103 closed (Wave B complete: B3–B18, SESSION_HANDOFF §103). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: B5 migrations, named config slots, or the packaging pass.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§102: B2 shipped — the heat ramp controls (T9): one shared scheme vocabulary on both heat surfaces; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§102**. **B2:** new `ui/ramp.js` (+ selftest) — four **named schemes** (Balanced = the shipped recipe, pinned equal as values; Wall hunt; Thin-book detail; Quiet book) with **custom** once a dial is hand-edited; **ceilings** (percentile or exact size) resolved backend-side into the snapshot's `scale_max` (absolute beats percentile; `applies: restart`, proven live); exact/share **floors** and a **contrast** gamma read at paint time; **Apply globally** broadcasting between the Engine's depth layer and the Heatmap view; seven new registered display variables (registry + sanitiser clamps; defaults = the old look). Display-only — no value, feed or ingest touched. Fixed on the way: the Engine ramp select's persistence, the pct ceiling's dishonest `applies: "live"`, and the Heatmap scheme handler's repaint path.
>
> **Gates.** pytest **1312 passed / 2 skipped** (+8 pins); AUDIT CLEAN (**101 modules**); ruff (CI pin 0.16.7, via `uvx`) clean; **29 node selftests / 0 failures** (the old “30” was count-drift — 29 files on disk, all green, none ever missing); goldens green; live pass 0 client errors; sandbox stopped, ports clear.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 143 dirty entries). **Next in Wave B (his pick):** B3 smoothing, B4 columns rail, B5 one-table, B6 instrument lookup, B7 notifications inbox, B9–B18 per the study.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §102 closed (B2/T9: heat ramp controls — shared named schemes, ceilings/floors/contrast, apply-globally; SESSION_HANDOFF §102). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: Wave B — his pick of B3–B7 / B9–B18.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§101: B8 shipped — the template gallery (T8); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§101**. **B8 (T8):** a **Start from a template** card in the Guide — six entries (3 boards: Fast tape / Context / Replay study desk — 12×8 rects, pinned to the store’s rules; 3 settings bundles: Laptop minimal / Colour-blind palettes / Still scales — every path pinned as registered), each linked to its help topic. Boards load as **new layouts** (never replace anything) and the shell switches to Terminal with the board’s own view focused; bundles write through the `/params` gate and stay reversible. Two load-path bugs found live and fixed (shell cache vs direct save; foreign current view appended → full-grid re-tile).
>
> **Gates.** pytest **1304 passed / 2 skipped**; AUDIT CLEAN (**99 modules**); ruff (CI pin) clean; **all 30 node selftests pass**; live pass 0 client errors; sandbox stopped, ports clear.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 138 dirty entries). **Next in Wave B (his pick):** B2 ramps, B3 smoothing, B4 columns rail, B5 one-table, B6 instrument lookup, B7 notifications inbox…
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §101 closed (T8/B8: template gallery; SESSION_HANDOFF §101). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: Wave B — B2–B18 per the study.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§100: B1 shipped — the settings search & staging surface (T7); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§100**. **B1 (T7):** a modeless **Find a setting** card in Settings — the whole registry (101 settings) with **tokenised search** (plain words match label/meaning/path/group/unit; `group:` · `view:` · `path:` axes), **Show original values** (factory defaults + amber changed-dots), **staged edits** with per-field **✓ write-now** / **↺ drop**, **Apply staged** (through the `/params` registry gate, refusals surfaced) and **Revert staged**. Every row carries `path · view`; per-surface scope lives in View ▸ This view — settings (T6), and named config slots are a recorded candidate, not built.
>
> **Gates.** pytest **1299 passed / 2 skipped**; AUDIT CLEAN (**98 modules**); ruff (CI pin) clean; **all 30 node selftests pass**; live pass 0 client errors (first clean live pass since T3); sandbox stopped, ports clear.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 136 dirty entries). **Next in Wave B:** B8 template gallery (recommended next), then B2–B18 per the study’s §5.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §100 closed (T7/B1: settings search & staging surface; SESSION_HANDOFF §100). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: Wave B, recommended B8 template gallery.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§99: T6 — Wave A COMPLETE (context-validity menus + per-view remember/restore/factory); nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§99**. **A8:** the Keys menu disables rows whose own gate is false (`OFAPKEYS.canDispatch`) and shows each binding’s `why` as the row title; the paper ticket disables a panic button with nothing to act on. **A15:** the View menu’s trio — Remember / Restore / Reset-to-factory — for the live active view, backed by `GET /config/defaults`, `config_store.VIEW_DEFAULT_MAP` and the validated `ui.view_defaults` block; the JS/Python maps are pinned equal. **Wave A is complete** (T1–T6); the one deferral is A6’s gap count (needs an ingest counter).
>
> **Gates.** pytest **1294 passed / 2 skipped**; AUDIT CLEAN (**97 modules**); ruff (CI pin) clean; **all 30 node selftests pass**; live pass 0 client errors; sandbox stopped, ports clear.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 134 dirty entries). **Next:** Wave B — the study’s medium items; the recommended first is **B1** (settings: modeless + tokenised search + Show Original Values + Apply-All/Revert-All) with **B8** (template gallery) composing with the help corpus.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §99 closed (T6: Wave A complete — context-validity menus + per-view defaults; SESSION_HANDOFF §99). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: Wave B from UX_COMPARATIVE_STUDY §5 (recommended first: B1 settings UX, B8 template gallery).`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§98: T5 “canvas craft” — auto-fit hysteresis, the nudge kit on both canvases, the values divider, minimal mode + card collapse; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§98**. **A11:** `math.fitDecision` + `atlas.ofx.fit_tolerance` (0.25 default; 0 = old behaviour) — the Engine's price scale stops breathing; live 0.5 → read → restored. **A12:** Engine arrows nudge the stage 1 px (Shift 10) on both axes (`OFX.nudge`); Heatmap arrows step rows and the depth window; eight + four bindings in the Keys menu. **A20:** `atlas.heatmap.values_min_px` (0 = off) — cell values draw only when cells are wide enough; the gate refused at 2.5/7.7 px (honest; the HUD stays the value read otherwise). **A10:** heatmap **minimal** toggle (`ui.heatmap_minimal`, registered for `/params`) + dbl-click-a-card-head collapse (session-only). **Live-caught fixes:** the `window.S` trap (S is a top-level `let`), the `/params` registry gate, the over-constrained fit rule.
>
> **House-keeping:** six files with mixed line endings (from earlier writes) normalised to CRLF — the tree's convention (`core.autocrlf=true`); verified against HEAD.
>
> **Gates.** pytest **1287 passed / 2 skipped**; AUDIT CLEAN (**97 modules**); ruff (CI pin) clean; **all 30 node selftests pass**; live pass 0 client errors; sandbox stopped, ports clear.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 133 dirty entries). **Next package:** Wave A's last pair — **A8** context-validity menus · **A15** set-as-default + factory reset.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §98 closed (T5 canvas craft: fit hysteresis, nudge keys, values divider, minimal + collapse; SESSION_HANDOFF §98). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: Wave A last pair A8 · A15 from UX_COMPARATIVE_STUDY §5.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§97: T4 “trust & legibility” — freshness thresholds + delayed badge, inferred labels, freeze-on-hover, watermarks/titles, ambient strip, update policy, sound card, rail digit fix; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§97**. **A5:** `atlas.freshness` (seconds, 0 = built-in; display-only) renders in Settings, is clamped by the sanitiser, registered in the param registry, and reaches the chips (`setWindows`, boot + after save) — live: 45 s → 45000 ms → persisted → restored. **A6:** Sweeps/Stop-runs/scanner now say **inferred** like the icebergs always did; the gap count is deferred (no ingest counter). **A7:** freeze-on-hover on the canvases (`freeze.js`; painters guard; frozen chip; newest state paints on unfreeze). **A9:** watermarks (**instrument · view · mode**, hidden when unreadable) + widget-title tokens. **A16:** status strip gains the **market-data-delayed badge** (on-screen panels only — parked panels stay quiet), a **feeds-paused** chip and the **oldest-sample** readout. **A17:** `docs/UPDATE_POLICY.md` + the `work.updates` help topic + a card link. **A19:** Settings ▸ **Sound** (enable · volume · Test sound). **A-corr:** the Setup button no longer shifts the 1–9 rail digits (four scans fixed + pinned).
>
> **Gates.** pytest **1281 passed / 2 skipped**; AUDIT CLEAN (**97 modules**); ruff (CI pin) clean; **all 30 node selftests pass**; live pass on 8089 with 0 client errors; sandbox stopped, ports clear.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 131 dirty entries). **Next package candidates:** Wave A's remaining canvas/preset set (A8 · A10 · A11 · A12 · A15 · A20).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §97 closed (T4 trust & legibility: freshness thresholds+badge, inferred labels, freeze-on-hover, watermarks, ambient strip, update policy, sound card, rail digit fix; SESSION_HANDOFF §97). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next: Wave A remainder (A8–A12, A15, A20) from UX_COMPARATIVE_STUDY §5.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§96: the UX study's first package — T1 contextual help, T2 window & layout trust, T3 the order-safety trio — built and live-verified; nothing committed**)
>
> **State.** Full record: SESSION_HANDOFF **§96**. **T1:** every panel head carries its own "?", `[data-helptopic]` links open their topic (blank states wired: replay fills, journal, calendar), and **F1 answers for the panel in focus**. **T2:** layout **versions** (recoverable saves/deletes, restore from the Layout menu), a persisted **layout lock** (move/resize/add/remove/reorder gated; status chip), the **Windows & layouts** dialog with per-window **Reset position** (the "unreachable window" rescue) and **`--safe`** start (no windows restored, Classic boot, store untouched). **T3:** **armed order keys** (danger rows inert until armed; badge; Keys-menu toggle), paper keys **Alt+B/Alt+S/Alt+X** (view+session+lock gated), the menu **legend rendered from the live registry** (`keyId` → `accelOf`; engine rows converted; Copy-the-list), and the ticket's **Lock trading** + danger row (flatten/cancel stay live). Live receipts over CDP: 31 panel-help buttons; ?/F1/blank links route correctly; 3 versions kept; lock persisted; disarmed Alt+B inert + hint; armed Alt+B placed the order; locked refused both click and key.
>
> **Gates.** pytest **1269 passed / 2 skipped** (+28 pins); AUDIT CLEAN (**95 JS modules**); ruff clean; **28 node selftests / 0 failures** (keys 45). Sandbox stopped, ports clear, 0 client errors.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt**; nothing committed (HEAD `110c568`, 121 dirty entries); UX study Wave A (remaining), B, C await approval.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §96 closed (UX-study T1–T3: contextual help, window/layout trust, armed order keys + paper lock; SESSION_HANDOFF §96). Owed: dist/zip/SBOM/installer rebuild; nothing committed (110c568). Next from approval: UX_COMPARATIVE_STUDY waves.`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§95: the toggle move, the ingest audit + its six closures, the storage system, the industry sweep, and the R-build (updater · data port · paper · journal · calendar) — all verified live after a session crash; nothing committed**)
>
> **State.** The full record is SESSION_HANDOFF **§95**. One line per cluster: the topbar's menu-bar toggle now lives at the topbar's right end as a labelled pill beside the live chip; the five-auditor ingest sweep landed **17 fixes** (MT5 broker clock, Bybit book stamps, reconnect ladder, Alpaca dedupe, NT top-of-book, DB-error isolation, extras/capability gates, collector path + log rotation, retention for all tables, real vacuum, offline storage snapshot, bus-level freeze, demo chips); the six open items are closed (both/all partition — one instrument, one venue; MT5 zero-volume counted + warned; Market Watch per-venue boards; ofx poll view-scoped; 80 MB strays archived out of the repo; ntfy visibility flag); the **storage system** shipped (Settings ▸ Storage + Backup & reports; online-backup folder sets with manifest + SHA-256; UNC/drive/synced targets proved by writing; rotation; scheduling; email; headless CLI); the industry sweep verdict + ranked shortlist were delivered; and the **R-build** landed — R7 updater + top-bar **Update** menu, R8 data port (CSV in/out), R9 paper simulator + ticket on Replay, R10 journal + HTML statement view, R11 keyless economic calendar view. **The build session crashed at the first step of its final live pass**; the recovery re-ran the whole pass on a fresh sandbox AND fixed two real defects found on the way — the data-port dedupe key (`trade_id`; `bad_rows 0` on a 5,988-row round trip) and the paper account's fantasy fill (an already-through limit/stop is refused at submit now, pinned; live: the refusal sentence + a real −232-tick session saved to the journal).
>
> **Gates (at save).** pytest **1241 passed / 2 skipped**; AUDIT CLEAN (**94 JS modules**); ruff clean; **28 node selftests / 0 failures**.
>
> **Owed.** `dist/` · zip · SBOM · installer **NOT rebuilt** (payload changed heavily — payload parity + installer journey next packaging pass); nothing committed (HEAD `110c568`, 108 dirty entries); the toggle-tooltip cosmetic; the BTCUSDm-on-MetaQuotes-demo note (rename the mapping or let crypto ride the exchange); update/backup defaults conservative by design.
>
> **Owed (addendum).** **Awaiting approval: `docs/UX_COMPARATIVE_STUDY.md`** — the seven-brief UX/GUI comparison against the paid platforms (briefs in `docs/ux-study/`); proposed first package T1–T3; also a code-observed item to verify: the rail-top Setup button shifts the 1–9 digit view mapping by one.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §95 closed (toggle move + ingest audit/17 fixes + six closures + storage system + R-build: updater/data-port/paper/journal/calendar; SESSION_HANDOFF §95). Owed: dist/zip/SBOM/installer rebuild + payload parity + installer journey; nothing committed (HEAD 110c568).`
>
> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§87: the Market Watch board, the Run switcher, and the wizard/help reflection — all live-verified; nothing committed**)
>
> **State.** Three owner directives shipped together (§87 in SESSION_HANDOFF). **(a) Market Watch:** a first-class rail view + `GET /api/control/marketwatch` — the source's own board. With MT5 as the source it **mirrors the running terminal's own Market Watch, read-only** (`SymbolInfo.visible`; 35 symbols on the owner's demo — Forex → indices → metals → stocks in the terminal's own path order), live bid/ask + daily change per page off the terminal; pinned by a booby-trapped fake that fails the test if the panel ever writes to the terminal (`symbol_select`). Bybit = one cached whole-board snapshot (877 instruments); NinjaTrader = the terminal's master list. Formatting follows MT5 by magnitude (1.14776 / 155.944 / 29440.70), slanted arrows, right-click a row = the look-up verdict. **(b) Run switcher:** the top bar's **Run** menu — Desktop app (this window) · Headless server on port 8099 · CLI pipeline (feeds → detectors → Telegram) — each launched in its own console window via `POST /api/control/launch` (closed set; refuses frozen-CLI and a busy 8099; warns both modes share the history store); below the divider the Optional reminders (MT5, NinjaTrader, dev tooling) + a Market watch short-cut. Mode #2 was proven live: the whole §87 receipt ran on a sandbox headless instance on 8099. **(c) Wizard/help reflection:** the suite's own coverage test (a view without a help topic fails the suite) caught the gap — new `view.marketwatch` topic + map entry; `view.instruments` corrected (the toggle self-saves and applies — same path as Enable & restart), `view.ofx` documents the symbol picker, `work.menubar` documents Run; the wizard's Ready step recaps Systems / Market Watch / Run. Receipt numbers from the terminal: `AUDUSD 0.71123 ↘ −0.27% · EURGBP ↗ 0.39% · EURUSD ↘ −0.58%`. **(d) §88 — the board is LIVE:** it re-reads on a ~1.5 s timer with in-place cell updates, green/red last-move tints + flash, a live-age badge, and a **Pause/Resume** that freezes it exactly as it stands (mid-flight reads are dropped); the MT5 daily-change basis is cached server-side (300 s) so a poll is just ticks, and the Bybit snapshot TTL is 1.5 s. Verified live: values moved between idle snapshots, pause froze them across 5 s, resume picked the market back up. **(e) §89 — per-surface pause:** every wired live panel (Overview, Chart, Order Flow, Engine, Market depth, Time & Sales, Market Watch, Signals, Trackers) carries its own **Pause/Resume** button in its view head, built on intent.js sticky user holds: a parked panel's updates are **queued** (the chip counts them: *\u201c⏸ tape \u00b7 marketwatch paused — feed live \u00b7 1 update waiting\u201d*) and applied on resume; holds persist per browser; the global chip + P still holds everything. CVD/heatmap/profile/frames deliberately have NO button yet (their paint paths do not consult the arbiter — a lying button is worse than none); Atlas-V2's poll and the Market Watch timers were registered with the global pause (two real gaps closed). **Front-end only — reload, not restart.** **(f) §90 — the live-tick layer:** new `ui/ticks.js` (shared direction/tint/flash primitive, 9-check selftest) wired through the price/delta KPIs, depth strip, POC/VAH, CVD value, tracker badge, signal-card arrival, Systems tiles and the whole **Scanner** view (which also gained §89's Pause button, a `held('scanner')` guard and global-pause registration — the audit's one miss). A dash must never read as a zero — caught by the layer's own pin. Live receipt: the KPI price cycled *· 76809.00 → tick-down → ↗ 76809.10 tick-up*. Honest remainder: canvas surfaces are inherently live; the L2 ladder's inner cells and CVD/heatmap/profile/frames pause buttons remain follow-ups. **(g) §91 — frame hide/show:** View menu + keys **B** (top menu bar) and **R** (side rail), owned by new `ui/chrome.js`, persisted per browser, recoverable by design (the way back never lives in the hidden thing). Receipt: B/R hid and restored both; a reload kept the rail parked. **(h) §92 — Keys menu + shortcut prompts + UX audit:** top-bar **Keys** menu built from the live registry (click a row to run it); program-wide shortcut prompts (tooltips, aria-keyshortcuts, hover-card line — rail items show 1…9); audit caught the File menu's Ctrl+Alt+R lie (now bound) and added Ctrl+Alt+S/X, Ctrl+F look-up, Ctrl+PgUp/PgDn panel cycling; duplicate zen binding removed (Alt+Z in menubar stands). **Physical hide/show buttons on both bars** (menubar \u201c\u2303 hide\u201d + topbar reveal; rail footer \u201c\u276e hide rail\u201d + left-edge \u2771 reveal). Verified live: keys menu rows, prompts read-back, all four buttons + reveals, cycle overview → chart → heatmap → back. **§92b postscript:** chrome controls unified — persistent topbar toggles **◧ rail / ▤ menu bar** beside the ModFlow mark (they cannot hide with their bars; `aria-pressed` faces), in-bar one-way "hide" controls (menubar's plain *hide*, rail's discreet *‹*), state-dependent reveals removed; a caught live bug (literal `\uXXXX` glyphs in markup — second occurrence) is now clamped by a dedicated pin. Verified: functional pass + served-bytes check (`>◧ >▤ >‹`). **§93:** the rail's return arrow is back at the left edge (visible only while hidden; ❯) and the topbar toggles flip directionally (⇤/⇥, ⌃/⌄); the menu audit lives in **docs/MENU_RECONCILIATION.md** with the rail/menubar inventories, the 13 unexposed routes, findings F1–F7 and the upgrade queue (headline F1: Trackers advertises dots/correlation/cross-venue it never fetches — five live routes, no caller). **§94:** the stuck "Close" remnant after quitting = aux widget windows still up while the process exited (ghost frame, not a crash, not app UI — WER empty, clean log end). Fixed with an ordered quit sweep (`NativeWindowHost.close_all()`, records kept so widgets return; main window's `closed` event + tail call). Verified live: tape parked while Market Watch kept moving, both parked froze the board, resume snapped current.
>
> **Gates:** pytest **1040 passed / 2 skipped** (+13 marketwatch, +6 pause-surfaces, +3 ticks, +4 chrome, +5 keys pins; intent selftest 12 checks, keys 42, ticks 9), AUDIT CLEAN (**89 JS modules**), ruff clean, **28 node selftests / 0 failures**, OpenAPI **147 operations**; badges re-derived (tests 1039, API 147).
>
> **Live on the owner's machine:** one fresh instance (also picking up the new backend routes), engine streaming BTCUSDT/ETHUSDT/SOLUSDT/TRXUSDT, Systems board **4 of 8 — 50%**.
>
> **Owed:** `dist/` · zip · SBOM · installer **NOT rebuilt** (payload changed — next packaging pass re-runs payload parity + the installer journey); NT bridge click-through with the platform open; nothing committed; HEAD `110c568`.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §87 closed (Market Watch board + the Run switcher + wizard/help reflection; SESSION_HANDOFF §87). Owed: dist/zip/SBOM/installer rebuild + payload parity + installer journey; NT bridge click-through; nothing committed (HEAD 110c568).`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-18 — **§86: the Systems board — one graphical answer to "are the systems 100%?" — plus the capability-reflection audit; live-verified in the sandbox; nothing committed**)
>
> **State.** The owner asked whether the app correctly activates toggles/switches/menus when a subscription/module/plugin or ingest is added, and for a small display of every live ingest interaction + optional capability. **The audit:** the capability-driven surfaces were verified live (Instruments greying, Engine states/actions, Platforms cards, wizard notes, Alpaca link state, top-bar chips) — two lies found and fixed across §85/§86: the Instruments toggle not persisting, and the MT5 board row saying "feeding the engine now" while the exchange was the source (caught by this pass's own screenshot; pinned). **The board:** new `GET /api/control/systems` (+1 route → 145) + the Overview **Systems** card (`ui/systems.js` pure + selftest, wired in `ui.js`, registered in the audit): fixed-order rows — Engine, Feed — \<source\>, MT5, NinjaTrader bridge, Alpaca, History database, UI stream, Alerts — states `live|ready|off|error`, score over expected rows only, optional capabilities (Bookmap, Sierra) kept apart, every tile routes to its fix view, a Re-check button, first paint on a status tick. The **History database** row is a real write-lock probe — it shows the §85 `database is locked` condition and names the way out. Live: *1 of 8 live (13%)* pre-start → *4 of 8 (50%)* with the engine running; tile click verified to navigate.
>
> **Gates (at §86 close):** pytest **1008 passed / 2 skipped** (+1 §86b pin), AUDIT CLEAN, ruff clean, **26 node selftests**, OpenAPI **145 operations**.
>
> **Pending:** reload the app to pick the board up (front-end files + one backend route — a backend restart is needed for this pass, unlike §85); the §85 "duplicate instance" was a misread, corrected in §86b (venv shim + child, one launch; the lock storms were restart-flush collisions on the 776 MB store); `dist/` · zip · SBOM · installer **NOT rebuilt**; NT bridge click-through with the platform open. Nothing committed; HEAD `110c568`.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §86 closed (Systems board + capability audit; SESSION_HANDOFF §86). Owed: dist/zip/SBOM/installer rebuild + packaging journey; NT bridge click-through; close the duplicate app instance on the owner's machine. Nothing committed.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-17 — **§83 CLOSED: the app explains itself (hover / right-click / banners) and user input persists — the Alpaca "re-enter my keys" report was a real config-wiping bug, fixed and live-verified; nothing committed**)
>
> **State.** Two things shipped together on the owner's directive (full record: `docs/EXPLAIN_AND_PERSIST.md`; handoff §83). **(a) The reported bug:** the Alpaca view's *Validate & save* called `config_store.save_config()` with **only the alpaca block**, and `save_config` merges over the factory defaults — so saving keys rewrote the file as defaults + stray top-level keys, leaving `alpaca` empty (**the keys vanished on the next launch: "had to re-enter"**) and silently resetting every other setting. Fixed (whole-config load→update→save), plus `engine/start|restart` bodies now merge, Settings saves start from the on-disk config, the Alpaca feed selector posts a one-field patch, the **dead Telegram master switch** is wired, and `ui.chart`/`ui.logs` view state is persisted. A **guard test** now fails the suite if any `save_config(X)` is handed a block instead of the whole config. Live receipt: key save → **process restart** → `configured: true`, `key_masked PK83…E2`, marker + 51 instruments + source intact, no stray top-level keys. **(b) The explainer:** new `ui/hint.js` (+ selftest, 7 checks) — hover shows a card, **right-click pins it**, buttons run real actions (closed set `lookup · engine · instruments · wizard · menu`); wired to the Engine chip (its card is the live verdict, e.g. *"⚠ not on this source | NQ1! → NAS100USDT — Bybit perps list crypto only — switch to MT5 (Windows) …"*), the top-bar pills, the Instruments header (**Look up an instrument…**) and **right-click on any instrument row**; the engine's skip banner now carries **Open the instrument look-up** (measured: it opened the Engine view with that verdict); menu entry **Data ▸ Instrument look-up…** + a palette command whose keywords include `crypto only`. Help guide amended: `start.sources`, `connect.mt5_map`, `view.instruments`, `view.alpaca` (*"Your keys stay saved — nothing to re-enter"*), `fix.no_data`, `fix.skipped_symbols`, `view.settings`.
>
> **Gates.** pytest **962 passed / 2 skipped** (+18 new pins: `test_settings_persistence.py` 10, `test_hint_ui.py` 8), AUDIT CLEAN (**82 JS modules**, `hint.js` registered), ruff clean (via `uvx`), goldens OK, **25 node selftests**, OpenAPI **140 operations** unchanged.
>
> **Owed:** `dist/` · zip · SBOM · installer **NOT rebuilt** (payload changed — rebuild + payload parity + journey next packaging pass); README/CONTRIBUTING counts re-derivation; installer polish still parked mid-IDE (IS IDE open at the Shortcuts view).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §83 closed (explain-in-UI hover/right-click module + the Alpaca key-persistence fix and the settings sweep; see docs/EXPLAIN_AND_PERSIST.md and SESSION_HANDOFF §83). dist/ + installer NOT rebuilt (payload changed): rebuild exe/zip/SBOM + Setup, re-run payload parity + the installer journey, re-derive the README counts, then the release cut.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-17 — **§82 BUILT: the Engine panel's instrument look-up + venue-confirmed adds; the "can't switch to NQ" report is answered; nothing committed**)
>
> **State.** The owner's report — a suite user could not change the Engine panel to NQ — was triaged to root cause and then built out as he directed (**Tier A + B full**, plan + log in `docs/INSTRUMENT_SWITCH_PLAN.md`; full record in SESSION_HANDOFF §82). The Engine symbol box is now an *answered* control: a state chip (streaming / enabled / not enabled / available / not on this source / unknown), a `find` look-up panel with the server's own reason, ranked suggestions, and the actions **Use · Enable & restart · Add & restart · Start the engine · Map the broker symbol · Open Instruments** — and the silent 404 is gone (the view prints the server's sentence and the app follows the row after an add). Backend: `desktop/instrument_lookup.py` (new, pure: alias table + `resolve()` + the engine's refusal words), `engine.venue_stamp_for()` (a matrix-unknown symbol streams on its own venue stamp: mt5 / alpaca / bybit / binance / hyperliquid / okx), `engine.mt5_symbol_names/mt5_symbols/mt5_validate_symbols` (broker discovery off the real terminal: 12,388 symbols), `GET /api/control/instruments/resolve`, `GET /api/control/mt5/symbols`, source-aware `POST /api/control/instruments/add`, and `POST /ofx` now answers with a `stream` block. Live receipt: `resolve("NQ1!")` → **live · NAS100USDT (alias)** with `NAS100USDT 38,045 ticks / 181 candles` from MT5; panel-driven adds proven in a real browser (`USTECH100M` 32,896 ticks / 121 candles; `TDAX`; `US500M` remap). MT5 `symbol_info` is **case-sensitive** — MetaQuotes lists `US500M`/`USTEC` where the shipped defaults are Exness-style `US500m`/`USTECm`, and the look-up now offers that remap instead of a dead end.
>
> **Gates.** pytest **942 passed / 2 skipped** (+51 new pins), AUDIT CLEAN (**80 modules**), ruff clean, goldens OK, **24/24 selftests**, OpenAPI **140 operations**. Counts re-derived: badges **942 / ~74k / API 140**; File Inventory **193 / 31,763 py / 42,180 UI / 73,943**; suite **82 files / 16,351 lines**; JS **81 modules / 34,779 lines** (24 selftests).
>
> **Owed:** `dist/` · zip · SBOM · installer are **NOT rebuilt** — the payload changed, so the next packaging pass rebuilds and re-runs payload parity + the installer journey (installer polish still in flight, IS IDE open).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §82 is closed (Engine instrument look-up + venue-confirmed adds; SESSION_HANDOFF §82 + docs/INSTRUMENT_SWITCH_PLAN.md). dist/ + installer NOT rebuilt (payload changed): rebuild exe/zip/SBOM + Setup, re-run payload parity and the installer journey, then the release cut. Installer polish state: IS IDE open at the Shortcuts view.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-17 late — **THE REPO IS PUBLIC (push done, screenshots live); the installer-polish pass is IN FLIGHT mid-IDE**)
>
> **State.** Directive 1 executed: the full package is pushed to **ModdySwag/ModFlow-OrderFlow-Analysis-Suite** (`master`; the shallow clone was unshallowed first — `git fetch --unshallow origin`; commits `25f5fd8` screenshots + `7584ca8` release state) with **30 live screenshots + a 2.12 MB tour GIF** (`docs/screenshots/`, gallery `docs/SCREENSHOTS.md`, README *See It Running*) and **obvious credit** to mahmoud20138/OrderFlow-Analysis-Pro (*Credit & Lineage*). Private lane **ModdySwag/ModFlow-beta-builds** created (release cut after the polish). Directive 2 (installer polish: x64 + WebView2 + Start Menu in one seed template) is **half-done** — the recipe is proven and prepped (handoff's PUBLISH+POLISH section has coordinates, the elevated-driver trio, and both fallbacks); the InstallShield IDE is OPEN at the Shortcuts view. Next: clear the stray Keywords text (`x64;1033`), add the Start Menu shortcut (right-click Programs Menu), add the WebView2 `.prq` (Redistributables view), File→Save As the seed, rewrite make_installer.ps1 as a seed-updater, rebuild + full journey.
>
> **Watch:** `gh run list` — the push triggered CI's first-ever run on the new repo (outcome unknown).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — repo is PUBLIC now (ModdySwag/ModFlow-OrderFlow-Analysis-Suite; screenshots + credit live). Installer polish IN FLIGHT: IS IDE open at Shortcuts view (clear stray Keywords=x64;1033 first!), add Start Menu shortcut + WebView2 .prq, Save As seed, rewrite make_installer.ps1 as seed-updater, rebuild + journey. Recipe + coordinates + fallbacks in SESSION_HANDOFF's PUBLISH+POLISH section.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-17 night — **MT5 SHIPS: numpy + the bridge bundled, verified against a real MT5 terminal; a live DOM defect found and fixed**; nothing committed, nothing pushed, no tag)
>
> **State.** The owner's directive — *"i want the packaged app to ship MT5 … bundle numpy (+27 MB) and verify against a real MT5 terminal"* — is executed (handoff's MT5-ships addendum): numpy + MetaTrader5 are **bundled** again, the frozen "portable build" branches and their messaging are deleted, guide/help reworded, pins replaced (2 removed, 5 added). A real terminal was installed (`C:\Program Files\MetaTrader 5`, MetaQuotes-Demo login 112751745) — root cause learned on the way: **the official terminal needs one completed account login before `initialize()` stops returning `(-10005, 'IPC timeout')`**. Verification: tree engine 20k+ ticks/symbol, feed driver with **192 DOM snapshots/symbol**, frozen exe 30k+ ticks/symbol and **0 errors** — and the real terminal **caught a live defect**: `BookInfo` has no `volume_real` (measured fields: type/price/volume/volume_dbl), so DOM had been silently dead; fixed + 5 new pins (`test_mt5_feed.py` — the feed had zero coverage).
>
> **Artefacts (third same-day rebuild).** exe **15,020,151 B `d6287ef2…`** → zip **39,884,552 B `2dc1817d…`** (**565 entries**) → Setup **40,826,742 B `1a1a9f49…`** → **SBOM regenerated `--extra mt5`** (`28811a2d…`, 45 components) with the CI audit+SBOM steps updated to match.
>
> **Verified.** pytest **881/2 on 3.12 AND 3.11** (the parity venv now carries the `mt5` extra); AUDIT CLEAN; ruff clean; goldens 0.000e+00 / 31-18-49; **23/23 selftests**; payload **120/120**; **frozen smoke 31/31** (mt5 available:true, numpy+bridge asserted in `_internal`, stdout empty); pip-audit clean incl. the extra. **Installer journey:** 565 files, installed exe sha == dist, smoke clean (173,389 B candles, hostile Host 403, 0 client errors), uninstall clean via `{820D9A42-…}` (both hives — no manual step), dev shortcut restored. Counts re-derived: badge **881**, File Inventory **191 / 30,981 py / 41,631 UI / 72,612**; suite **78 files / 15,664 lines**.
>
> **Owner's queue, in order:** 1. push (the remote decision). 2. His **physical multi-monitor pass** (**§80** if it finds anything). 3. The release-notes review. 4. Then **tag `v0.1.0-beta`** with the zip + Setup exe + SBOM.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — MT5 ships now (numpy+bridge bundled, verified against a real terminal; BookInfo defect fixed; nothing committed/pushed/tagged). Next: the owner's queue — push, the physical multi-monitor pass, the release-notes review, then tag v0.1.0-beta with the zip + Setup + SBOM.`

> ## ▶ RE-ATTENDANCE (previous, 2026-09-17 — **§79 CLOSED: counts re-derived, `dist/` rebuilt + re-verified (incl. the MT5 fix), installer journey clean; nothing committed, nothing pushed, no tag**)
>
> **State.** The two items §79 owed are done on disk (handoff §79's close-out block): the
> README/CONTRIBUTING counts were re-derived from the tree — badges **877** / **~73k** / **138 routes**;
> File Inventory **191 / 30,980 py / 41,631 UI / 72,611**; suite 77 files / 15,627 lines; JS
> **79 modules / 34,272 lines** (22 → 23 selftests); two drifted `(NNNL)` claims fixed
> (`app.py` 1381, `settings.py` 822) — and the whole `dist/` chain was rebuilt:
> exe **13,580,019 B `a1e31865…`** → zip **29,220,818 B `145a708b…`** (**525 entries**) →
> Setup **30,213,471 B `8526f59d…`** → SBOM unchanged. Then the close-out's MT5 finding was
> attended the same day: the frozen build now **excludes** the MetaTrader5 bridge (it cannot load
> without numpy) and says so honestly — rebuilt and re-verified a second time. Payload **120/120**
> byte-identical (ui + dashboard/static + add-on; static parity now included); no source newer than
> the build.
>
> **Verified.** pytest **877/2 on 3.12 and 3.11**; AUDIT CLEAN (78 modules); ruff clean (after
> fixing an F401 §79's pass had left in `desktop/help.py` — the close-out's own gate caught it);
> goldens OK; **23/23 selftests**; pip-audit clean over the frozen set. Frozen exe **29/29**
> (guards, WS, unknown `[]` ×2, Help Centre assets byte-identical 4 + 9/9 PNGs,
> `/api/control/help` facts+check, **asset parity 50/50**, `bootstrap.mt5` names the portable build,
> stdout has no numpy `ModuleNotFoundError`, log 0/0/0) and the packaged shell driven
> in a real browser (OFAPHELP boots, dock renders, 68 topics, 16 suggestions, 0 page errors).
> **Installer journey re-run:** silent install → **525 files**, installed exe sha256 == dist exe →
> installed smoke on 8098 (healthz 200, candles 200, unknown `[]`, hostile Host refused, 0 client
> errors) → silent uninstall clean (the ARP entry registered under the HKLM WOW6432Node view this
> run — the setup self-elevates; the §75 script's HKCU-only scan missed it and the product code was
> used directly); `%APPDATA%` untouched; dev shortcut backed up + restored.
>
> **The MT5 finding — attended the same day:** the frozen build now **excludes** the MetaTrader5
> bridge (it cannot load without numpy, excluded by §63) and says "run the app from source for the
> MT5 feed" in the card, the wizard's test and the log — no pip advice, and the stdout noise is
> gone (smoke asserts an empty stdout; 3 new pins). Re-bundling numpy (+27 MB) to ship MT5 in the
> package remains a possible future pass. Cosmetic carry-overs unchanged.
>
> **The owner's queue, in order:** 1. push (the remote decision). 2. His **physical multi-monitor
> pass** (**§80** if it finds anything). 3. The release-notes review. 4. Then **tag `v0.1.0-beta`**
> with the zip + Setup exe + SBOM attached.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §79 is closed (counts re-derived, dist/
> rebuilt and re-verified incl. the MT5 fix: frozen exe 29/29, installer journey clean, gates 877/2
> on both interpreters; nothing committed/pushed/tagged). Next: the owner's queue — push, the
> physical multi-monitor pass, the release-notes review, then tag v0.1.0-beta with the zip + Setup
> + SBOM.`

> ## ▶ RE-ATTENDANCE (2026-09-17 — **§79 the Help Centre is BUILT and verified in the tree**; nothing committed, nothing pushed, no tag, **`dist/` NOT rebuilt**)
>
> **State.** The owner's `Desktop/help.txt` directive was executed (§79): a two-interface in-app help
> system — **Advanced user** (every topic) and **Simple** (the safe subset + the system check), one
> corpus, one pure search engine with **autofill as you type**, in-app clickable shortcuts, external
> links, screenshot guides for the in-depth areas, and the launcher **docked into the status bar**
> (the app's taskbar) with floating and hidden alternatives. The menu bar's **Help** menu now carries
> the Help Centre, the search, the two interfaces, *Where help lives*, the system check, the setup
> assistant and the hotkey map — with the owner's **About card in the dropdown** (his logo, version,
> made by, thanks line, links) and the same mark used subtly in the module itself.
>
> **What it is made of.** `desktop/ui/help-data.js` (the 68-topic corpus + the view→topic coverage
> map) · `help-search.js` (pure engine, `help-search.selftest.js` 26 checks) · `help.js` (the panel,
> the two interfaces, the gate, the dock/launcher, the About page) · `help.css` · `help/*.png`
> (nine screenshots, byte-identical to `docs/screenshots`) · `desktop/help.py` (facts, credits,
> credits-from-LICENSE, and an 18-check pure **system check**) · `GET|POST /api/control/help` · the
> config's `help` block · `test_help.py` (30 tests incl. the coverage contract).
>
> **Verified.** pytest **874/2** (was 844/2); **AUDIT CLEAN** (78 modules); **23/23 selftests**; live
> sandbox on 8097 — served assets hash-match disk, the tree/dock/search/autofill/gate/check/About all
> driven for real, **30 views cycled with 0 page errors**, sandbox log 0 errors, and `mode`/`dock`/
> `recents`/`dismissed` read back from `config.json`.
>
> **The next moves, in order:** 1. **Re-derive the README counts** (the tree gained 6 files + 9
> assets). 2. **Rebuild `dist/`** (exe + zip + Setup) — payload-changing, so re-run the installer
> journey and refresh `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`. 3. **The owner's queue** — the push
> decision, his physical multi-monitor pass (§80 if it finds anything), the release-notes review,
> then tag `v0.1.0-beta`.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §79 (the Help Centre) is built and
> verified in the tree; nothing committed/pushed/tagged and dist/ is NOT rebuilt. Next: re-derive the
> README counts, rebuild dist + installer journey, then the owner's queue (push, multi-monitor pass,
> release notes, tag v0.1.0-beta).`

> ## ▶ RE-ATTENDANCE (2026-09-17 — the release-assurance audit ran: the packaged-UI defect found + FIXED, artefacts rebuilt and re-verified; **nothing committed, nothing pushed, no tag**)
>
> **State.** The owner's `Desktop/final security audit prompt.txt` directive was executed (§78): the full
> report is `docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md` (14 sections, the directive's order).
> **The headline finding:** the §77 artefacts shipped **without `orderflow_system/dashboard/static`** —
> the desktop shell's own `index.html` loads six widget modules from `/static/` — so six views
> (Footprint, Depth, Tape, Signals, Performance, Microstructure) were dead in the exe/zip/Setup while
> every gate stayed green (the repo tree was fine, and 404s never reach the app's error channel).
> Fixed at `scripts/build_exe.py` (required data roots — it now refuses to build without them), a
> fail-loud WARNING in `dashboard/app.py`, and a regression pin in `test_wiring.py` (bite-proven
> twice: renamed module, doctored build list).
>
> **Artefacts (rebuilt).** exe 13,552,324 B `8016d948…` · zip 27,385,320 B `f8f58706…` (**512**
> entries) · Setup 28,455,930 B `35e3887e…` · SBOM unchanged 430,051 B `97184c0b…`. Full hashes +
> receipts: `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`.
>
> **Verified:** pytest **844/2** on 3.12 (24.6 s) and 3.11 (24.8 s); AUDIT CLEAN (74 modules); ruff
> clean; 22/22 selftests; `pip-audit` clean. **Frozen-exe soak** (8×28-view cycles + 96 s live):
> intervals/observers/canvases flat, heap GC sawtooth no trend, 0 page errors; **frame time** median
> 16.7 / p99 16.8 ms. **Post-fix package:** 47/47 assets, six widget classes live, Tape renders,
> guards 403/403/403/200, `/desktop` hash-match `369fbbc6…`, 0 client errors. **Installer journey
> re-run:** silent install → 512 files, installed exe hash == dist, installed smoke, silent uninstall
> clean (dir + shortcut + ARP gone; dev shortcut restored; `%APPDATA%` untouched).
>
> **The next moves, in order:** 1. **The owner's queue** — the push decision, his physical
> multi-monitor pass (**§79** if it finds anything — §78 is this pass), the release-notes review,
> then the tag `v0.1.0-beta` + the zip + Setup + SBOM. 2. Cosmetic carry-overs ride the next
> source-changing pass (client-abort `ConnectionResetError` log filter; bandit SHA1
> `usedforsecurity=False`).
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — the release-assurance audit is done
> (§78): the packaged-UI defect fixed, artefacts rebuilt + re-verified (install journey clean),
> report at docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md; nothing committed/pushed/tagged.
> Next: the owner's queue — the push decision, his multi-monitor pass, the release-notes review,
> then tag v0.1.0-beta.`

> ## ▶ RE-ATTENDANCE (2026-09-17 — the audit send-back EXECUTED: §76 committed, `dist/` rebuilt, receipts in handoff §77; **nothing pushed, no tag**)
>
> **State.** The Desktop send-back's plan ran end to end. `HEAD` is ahead of `aa43f40` by this
> pass's commits — the §76 fold-in in five waves (`47ae326` feeds+tests → `096c055` desktop wiring →
> `25efd48` UI/audio → `96cd327` script hint → the docs wave last) — and `dist/` is rebuilt from
> that committed tree. **Nothing pushed, no tag** — the GitHub end is off per the owner's call.
>
> **What landed:**
> - **The send-back answered** (`docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md`): F-01 (stale artefacts) is
>   real and was closed by this rebuild; **F-02/F-04 withdrawn with evidence** (the manifest is
>   correct — the audit ran `scripts/audit_ui_refs.py` with the wrong interpreter; the script now
>   names its interpreter on import failure); F-05 = two README count lines (75 JS files /
>   30,113 lines); F-03/F-06 = receipts + notes lines.
> - **`dist/` rebuilt from the committed tree**: exe 13,550,202 B `2731442153…` · zip 27,419,732 B
>   `111198918d…` (503 entries, +7 = the §76 payload) · Setup 28,412,633 B `b2309cc9…` · SBOM
>   430,051 B `97184c0b…`. Full hashes: `docs/RELEASE_EVIDENCE_v0.1.0-beta.md` (refreshed).
>
> **Verified:** pytest **843 passed / 2 skipped** on 3.12 (24.6 s) and 3.11 (25.2 s); AUDIT CLEAN
> (74 modules); ruff clean; both goldens; **22/22** selftests; `pip-audit` clean. **Frozen exe,
> 18/18**: hostile Host 403 / cross-origin + cross-site POST 403 / native WS ping-pong /
> cross-origin WS refused / `/desktop` byte-identical to the packaged file + CSP / unknown symbols
> `[]` / six venue rows / 0 client errors. **Sandbox, from the tree:** four venue switches each with
> fresh ticks; backfill BTCUSDT 2026-09-13 → **512,737 ticks / 6.39 MB**, read back via
> `/api/control/trades` (total 512,737); the eight audio params set through `/api/control/params`
> and read back from the registry + `config.json`; log 0 errors.
>
> **The next moves, in order:** 1. **The owner's queue** — the push decision, his physical
> multi-monitor pass (**§79** if it finds anything — §78 is the release-assurance audit), the release-notes
> review (fold in the F-06 supply-chain lines), then the tag `v0.1.0-beta` + the zip + Setup + SBOM.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — the audit send-back is executed (§77):
> §76 committed in five local commits, dist/ rebuilt from the tree, gates 843/2 on both
> interpreters, frozen-exe smoke 18/18, sandbox receipts in handoff §77; nothing pushed, no tag.
> Next: the owner's queue — the push decision, his multi-monitor pass, the release-notes review,
> then tag v0.1.0-beta.`

> ## ▶ RE-ATTENDANCE (2026-09-17 — the fold-in is CLOSED: Hyperliquid + OKX wired, sandbox-verified, counts landed; **nothing committed**)
>
> **State.** The fold-in's follow-ups are done on disk and green; `HEAD` is still **`aa43f40`** and
> **40 paths** are changed or new (§76's 36, plus `desktop/ui/menu.js` and
> `orderflow_system/test_wiring.py` from the defect found on the way, and `README.md` +
> `CONTRIBUTING.md` from the counts pass). Nothing committed, nothing
> pushed; `dist/` is still the §75 build, so a rebuild stays owed before any release artefact is
> replaced.
>
> **What landed since the last block:**
> - **Hyperliquid + OKX wired exactly like Binance** — `settings.DataSource` members, the config
>   allow-list, `main.py` feed branches, `FREE_SOURCES` `wired=True` with honest hints,
>   `datasources()` rows, the `hyperliquid_capable/validate` + `okx_capable/validate` pairs feeding
>   `/api/control/capabilities?refresh=true`, the extras gate widened to **binance|hyperliquid|okx**
>   (each carries its own depth), the guide wizard radios, and a **POST-aware reachability probe**
>   (Hyperliquid's `/info` answers a bare GET with 405 — the old GET probe painted it "unreachable"
>   while healthy).
> - **The OKX silence budget the adapter author flagged: 40 → 75 s** (the venue's documented
>   quiet-instrument keepalive is ~60 s, so 40 tripped first). Pinned in `test_feed_session.py`.
> - **A live defect found while verifying and fixed: the ☰ menu's `api()`** (`desktop/ui/menu.js`)
>   tested `typeof api` — itself — so every call recursed and the `RangeError` died in each
>   caller's `catch`: `/sources` never loaded and switching a source answered "source switch
>   failed: RangeError: Maximum call stack size exceeded". Fixed to `typeof window.api`, pinned by
>   `test_wiring.py::test_a_module_local_api_helper_must_name_the_shells_helper`, re-verified live
>   over CDP (the menu now shows the six server rows; real clicks switched OKX ⇄ Binance).
>
> **Verified:** **843 passed / 2 skipped** on **3.12 and 3.11** (the parity run landed
> 2026-09-17), AUDIT CLEAN, ruff clean, both goldens OK, **22/22** selftests. **Live, from the repo
> tree:** feed probes — Hyperliquid 128 ticks / 20 s (20×20 books, 0 junk, 0 reconnects), OKX 577
> ticks / 20 s (400×400 books, 0 gaps, 0 reconnects, budget 75 s); engine switches to okx /
> hyperliquid / binance each with ticks > 0; sandbox — source switch to Binance (tape + orderbook
> live), the eight audio parameters through `/api/control/params` (read back; config block
> matches), backfill round trip DYDXUSDT 2026-09-13 → **9,799 ticks / 150,613 B downloaded
> fresh** and `/api/control/trades` returns all 9,799 inside the day (identical to §76's receipt),
> `orderflow.log` **0 client errors / 0 ERROR / 0 Traceback**. Counts: badge 843; File Inventory
> 185 files / 30,406 py / 37,136 UI / 67,542 total; suite 76 files / 15,091 lines; tree counts
> re-derived (main.py 857, settings 821, bybit_feed 339, database 472, dashboard tape.js 448).
>
> **The next session's first moves, in order:**
> 1. **The owner's queue** — push (the remote decision), his physical multi-monitor pass (§77 if
>    it finds anything), the release-notes review, then **tag `v0.1.0-beta`** with the zip + Setup
>    exe + SBOM attached. A **`dist/` rebuild is owed first** — nothing in the fold-in or this pass
>    is inside the frozen build.
>
> **His decisions — do not re-ask:** Binance first · ship the four generated finance-alert samples ·
> **both** backfill paths (archives + serving our own ticks) · the heatmap "order runs" model stays
> **deferred** behind its measured triggers.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — the flowsurface fold-in is closed (HL +
> OKX wired like Binance, the sandbox pass ran clean, counts landed; HEAD aa43f40, nothing
> committed). Next: the owner's queue — push, the physical multi-monitor pass, the release-notes
> review, then tag v0.1.0-beta. A dist/ rebuild is owed before any artefact is replaced.`
>
> ---
>
> ## ▶ RE-ATTENDANCE (2026-09-16 late night — the flowsurface fold-in: BUILT, TESTED, LIVE-VERIFIED, **nothing committed**)
>
> **State.** The approved fold-in is on disk and green; `HEAD` is still **`aa43f40`** (24 commits from
> `fa202d6`) and **36 paths** are changed or new (the two docs that record this pass included). Nothing
> is committed, nothing is pushed, `dist/` has **not** been rebuilt for this build.
>
> **What landed (all on disk):**
> - **Binance USDⓈ-M futures ingest** — `data/binance_feed.py` (aggTrade + diff-depth, REST-snapshot
>   chain with `U`/`u`/`pu` validation, bounded self-healing resync, 1000×1000 levels) and
>   `data/feed_session.py` (the rule that a cancelled `recv()` mid-frame is the bug: reader never
>   cancelled, heartbeat its own task, per-venue policies, jittered ladder that resets only on a
>   **parsed** frame). `data/bybit_feed.py` was hardened to that same rule. Wired end to end:
>   `DataSource.BINANCE`, config allow-list, the `main.py` feed branch, `FREE_SOURCES.wired=True`,
>   `datasources()` + `binance_capable()`/`binance_validate()`, the wizard radio, and the Bybit extras
>   feed gated **off** when Binance is the primary source (never mix one venue's depth under another's
>   prints).
> - **Trade audio** — `scripts/make_alert_sounds.py` generates four WAVs into `desktop/ui/audio/`
>   (soft buy/sell blips, rising/falling two-tone alerts), `ui/audio.js` + `audio.selftest.js`
>   (39 checks), 8 registered Tape-view parameters, a config block with a strict `_sanitise` clamp.
>   **Off by default.**
> - **Archive backfill (both paths he chose)** — `data/backfill.py` (window-replace so a re-run can
>   never double-count, `.part`-then-rename cache, µs/ms detection, junk-proof parse) +
>   `POST/GET /api/control/backfill` + `GET /api/control/trades` + `Database.delete_ticks_window /
>   count_ticks / get_recent_ticks`.
> - **Two more venue adapters, delegated and verified by me in a combined run**:
>   `data/hyperliquid_feed.py` (+27 tests) and `data/okx_feed.py` (+23 tests). **Not wired yet.**
> - **Tape changed-digit price tint** + `tape.selftest.js`. (Of the plan's four polish "gems", **three
>   already existed here** under other names — the pause + "N new" pill = `OFAPSTRIPS` chips, size
>   shading = `isBig`/`tape-row-big`, heatmap cell readout = `cellAt` + HUD — so only the tint was
>   folded in rather than duplicated.)
>
> **Verified:** **839 passed / 2 skipped** in one run (3.12; the 3.11 parity run is still owed for this
> build), `audit_ui_refs.py` **AUDIT CLEAN**, **22/22** JS selftests, `ruff check` clean. **Live:**
> Binance 4,759 ticks / 20 s across BTCUSDT+ETHUSDT with both books at 1000×1000, 0 gaps, 0 junk, 0
> reconnects; both new adapters were run against their real venues by their authors (their receipts,
> including the venue surprises, are in handoff §76); the backfill ran end to end against a real
> DYDXUSDT archive — 9,799 rows into a scratch DB, every row inside the day.
>
> **The next session's first moves, in order:**
> 1. **Wire Hyperliquid + OKX exactly like Binance** (`settings.DataSource`, the config allow-list,
>    `main.py`, `FREE_SOURCES` wired flags, `datasources()`/capabilities, the extras gate, the wizard
>    radios), then live-probe each **from the repo tree**.
> 2. **Sandbox end-to-end**: switch the source to Binance, drive the audio parameters through the
>    registry, run a backfill round trip over the API, then read `orderflow.log` for `client error:`.
> 3. **Counts/docs pass** (README badge 716→839, CONTRIBUTING baseline, File Inventory, the selftest
>    list 20→22) — then, **only when he asks**, a `dist/` rebuild and a commit.
> 4. Then his own queue: **push**, the physical multi-monitor pass (**takes §77** if it finds anything —
>    §76 is this fold-in), the release-notes review, then tag `v0.1.0-beta` with the zip + Setup exe +
>    SBOM attached.
>
> **His decisions — do not re-ask:** Binance first · ship the four generated finance-alert samples ·
> **both** backfill paths (archives + serving our own ticks) · the heatmap "order runs" model stays
> **deferred** behind its measured triggers.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — the flowsurface fold-in is built, tested and
> live-verified on disk but NOT committed (HEAD aa43f40, 34 paths). First wire Hyperliquid + OKX like
> Binance, then the sandbox end-to-end, then the counts/docs pass.`
>
> ---
>
> ## ▶ RE-ATTENDANCE (2026-09-16 late night — §75 closed, release candidates rebuilt)
>
> **State.** §75 — the post-beta left-overs — is **done and committed** (nothing pushed): the
> **single-instance guard (N-1)** `12211e2`, the **CI lint (ruff 0.16.7) + CycloneDX SBOM** work
> `d4fe370`, the mid-pass save `b0681a2`, then the closing pass `58101f4` + its record —
> **screenshots re-shot and landed** (11/11 vision-verified, one re-shot), **counts re-measured**
> (badge 716; File Inventory 176 files / 27,407 py / 36,583 UI / 63,990 total; suite 69 files /
> 12,422 lines), and **`dist/` rebuilt and re-verified** from the hardened tree. Suite **716 passed
> / 2 skipped on both interpreters** (3.12 and 3.11); gates all green.
>
> **The release candidates (rebuilt in §75; full hashes in `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`):**
> `ModFlowOrderFlowAnalysisSuite.exe` 13,371,238 B `10e6bdf8755abb0e…` ·
> `…-win64.zip` 27,229,338 B `00b96304e54949e0…` (496 files, 49.4 MB raw) ·
> `…-Setup-0.1.0.exe` 28,173,338 B `c3a14576a5a5a5b5…` ·
> `…-win64.sbom.cdx.json` 430,051 B `34fb03c49752de6f…`. Payload check 90/90 loose files
> byte-identical to the tree; live probe battery **21/21** on the frozen exe (Host 403, cross-origin
> POST/WS 403, native WS 101 + pong, `/desktop` byte-identical + CSP, unknown symbol `[]`, 0 client
> errors); **double-launch acceptance** passed (the second windowed launch exits 0, one window and
> one port); the installer journey was re-run on the new Setup (496 files, installed exe hashes to
> the dist exe, silent uninstall clean, the dev shortcut restored).
>
> **Next — the owner's queue, in order:**
> 1. **Push** — the remote decision: `origin` is still `github.com/mahmoud20138/OrderFlow-Analysis-Pro`.
> 2. His **physical multi-monitor pass** (§76 if it finds anything).
> 3. Release-notes review — `ModFlow v0.1.0-beta release notes (DRAFT).md` sits on his Desktop.
> 4. Then the tag `v0.1.0-beta` + attach the zip + Setup exe + SBOM.
>
> **Resume prompt:** `OFAP: continue from docs/RESUME.md — §75 is closed and the release candidates
> are rebuilt and verified. Next is the owner's queue: push, the physical multi-monitor pass, the
> release-notes review, then tag v0.1.0-beta and attach the zip + Setup exe + SBOM.`

One page for picking this up cold. The full trail lives in `docs/SESSION_HANDOFF.md`
(§24–§38 cover the terminal-mode build, the bus, the panels, the commit series, the P0 trust pass, the
theme/token layer, the cursor spine, selection-as-measurement, the strips' keys, the feedback cosmetics
the map's duration answer; §39/§40 the P1-7 alerts build; §41/§42 P1-8's bar expression modes;
§43/§44 P1-9's shortcut map; §45/§46 P1-10's freshness chips; §47/§48 P2-1's indexed hover path;
§49/§50 P2-2 (R6) — the heat pass change-gated, ghost decay patched, hover coalesced, numeric adapt
keys; §51/§52 P2-3 — the frame yields at 4K (max warm frame 12.4); §53/§54 P3-2 — the session
boundary is a config value and the DB has a 7-day retention window (measured: 4.4 M rows /
845 MB -> 336 MB on a copy of the live DB); §55 P3-3 — the legacy page retires behind a
307 redirect to /desktop; §56/§57 — the Float32Array heat wire (built, parity-pinned, measured
slower than the JSON path at real sizes: kept as machinery with a trigger) and the carry-over list
(all rows closed live, including two defects the gate found: the depth payload's axis transposition
in `adaptHeat` and the bus fetch wrapper eating binary bodies); §58/§59 — P3-1's trigger measured on
the owner's hardware (2560×1440 @ 144 Hz): NOT triggered (heat pass 0.6–0.7 ms on real payloads,
≤1.7 ms on the synthetic 30 k shape, against a 6.94 ms budget; the payload caps drawn cells at
~6 k), and the options/fundamentals residue closed with live captures; §60 — the ModFlow badge became
the app's iconography (`assets/orderflow.ico`, `ui/app.ico` + `ui/app-icon.png`, favicon, pywebview
window icon, and the frozen exe's resources patched in place) plus a new desktop shortcut); §61 — the two-tier ICO set (16/24 px = the text-free 0.58R
variant, 32 px+ = the badge); §62 — the rail brand: the `MF` text tile became
`ui/brand-icon.png` and the wording reads sentence case (`Orderflow Analysis Suite`); §63/§64 — the package diet and the
release-readiness pass (leaks, lint, packaging; one live bug fixed); §65 — the Python 3.11
hang root-caused and fixed, plus the release-face exactness pass; §66 — the v0.1b audit return (`docs/AUDIT_RETURN_v0.1b.md`:
every audit Tier-1/2 item verified — 7 fixes pinned, 3 rejected with probe evidence, README counts
re-derived, dist rebuilt); §67 — the displacement unit restored (true tick steps in absorption/initiative;
six pins); §68 — the unknown-symbol guard extended to the remaining eight demo fillers (all ten endpoints verified empty-of-shape for unknown symbols on source and the frozen exe); §69 — the Windows installer built and verified (installer/make_installer.ps1; setup.exe with full install/uninstall receipts; artifact hashed); §70 — the secure2 pre-release security sweep (`docs/SECURITY_SWEEP_v0.1b.md`: loopback request guard + WS handshake, feed-value NaN/neg gates, news-URL scheme/size containment, legacy bind fixed to loopback, SECURITY.md, CI SHA pins, shell CSP, screenshot PII redacted; suite 629 → 649); §71 — the display / multi-monitor audit (`docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md`: 16 viewport/DPI scenarios, two real canvas-geometry defects, drag/resize clamp verified at 1024/1920/5120); §72 — display hardening landed (Engine layers carry `devicePixelRatio`, `mpCanvas` gets a CSS box + relayout redraw, the ribbon is stage-width, `fitView` covers the whole board, the window remembers its geometry, and the layout saved for a screen is applied at boot; suite 649 → 679); §73 — widget windows (one panel per native window: `desktop/windows.py` placement + host seam, `GET/POST /api/control/windows`, `ui.windows` as the desired set, `NativeWindowHost` + restore on launch, `windows-ui.js` menu in both bars, `?aux=` mode that never writes a layout; suite 679 → 712);
`docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md` is the phase plan
with the decisions behind it, and `docs/UPGRADE_ACTION_PLAN.md` is the prioritised plan of action —
from `report1.txt`, corrected against the tree. **P0 (§32), P1-1 through P1-10 (§33–§46), P2-1 through P2-3 (§47–§52), P3-2 (§53–§54), P3-3 (§55),
the §56/§57 wire + carry-over pass, the §58/§59 P3-1 measurement, the §63 package diet and the
§64/§65 release passes and the §66 v0.1b audit return (7 audit fixes pinned, 3 rejected with probe
the §67 displacement-unit fix are done — the frozen `dist/` has been rebuilt and is current (49.4 MB raw /
26.0 MB zipped, numpy excluded). What remains is the owner's
call**: items staying behind their measured
triggers: P3-1 (WebGL — NOT triggered on his hardware, §59), the `/bin` heat wire (re-measure at
~2 MB JSON text or ~8 ms adapt), and UPX (§63 — ~10-14 MB, at the price of AV false positives).
**The §66 displacement-divisor clamp was resolved in §67**: true tick steps restored on the 25
fine-tick instruments (6 new pins; no bank retune needed — the unit is scale-free).
NOTE: the next live launch applies the 7-day retention default; nothing in today's DB is older than that.**
*(Superseded by the ▶ RE-ATTENDANCE block at the top of this file — the frontier is now the release
sequence (commit → push → tag `v0.1.0-beta`), not these trigger-gated items.)*

## Where it stands

- **The flowsurface fold-in (§76) is closed on disk — and deliberately UNCOMMITTED.** `HEAD` is
  `aa43f40`, 24 commits from `fa202d6`; **40 paths** are modified or new — §76's 36 plus
  `desktop/ui/menu.js` (the ☰ menu's self-recursive `api()` fix), `orderflow_system/test_wiring.py`
  (its pin), and `README.md` + `CONTRIBUTING.md` (the counts). Binance, Hyperliquid and OKX are wired, switchable and live-probed; the sandbox pass ran
  clean; the counts landed. Gate status: **874 passed / 2 skipped on both interpreters**, AUDIT CLEAN,
  23/23 selftests, ruff clean. **Nothing pushed.**
- **Branch `master`; the committed tree is clean.** The P1-7 → §73 corpus is **committed** — 18 per-wave
  commits from `fa202d6`, each file staged exactly once; §74 records the pre-tag pass, §75 adds the
  N-1 guard, the CI lint/SBOM work, the screenshot re-shoot, the counts, the rebuilt release
  evidence and its record — **24 commits from `fa202d6`**.
  **Nothing is pushed.** New in §56/§57:
  §63/§64 added `test_analytics_golden.py`, `test_no_numpy.py`, `test_source_switch.py`,
  `scripts/regen_analytics_golden.py` and `testdata/analytics_golden.json`; §66–§68 added ten audit-pin
  test files and `docs/AUDIT_RETURN_v0.1b.md`; §70 added `SECURITY.md`, `docs/SECURITY_SWEEP_v0.1b.md`,
  `test_request_guard.py`, `test_context_hardening.py`, `test_feed_value_guards.py`, `test_client_error_log.py`
  (plus two tests in `test_wiring.py`); §71/§72 added `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md` and
  `test_display_geometry.py` (window geometry + the canvas law + the per-screen layout, 30 tests);
  §73 added `desktop/windows.py`, `desktop/ui/windows-ui.js` (+ its selftest) and
  `test_aux_windows.py` (33 tests: the store's window set, pure placement, and the endpoints).
- **Nothing is pushed.** `origin` is `github.com/mahmoud20138/OrderFlow-Analysis-Pro` — the original
  project, not Moddy's. Putting this on his own GitHub is a remote/fork decision, one command when asked.
- Local identity is `ModdySwag <ModdySwag@users.noreply.github.com>` (repo-local, nothing global changed).

## Gates — run these before believing anything

```bash
unset PYTHONPATH
.venv/Scripts/python.exe -m pytest orderflow_system -q        # expect 881 passed / 2 skipped (measured 2026-09-17 on 3.12 and 3.11; the parity venv needs the mt5 extra)
.venv/Scripts/python.exe scripts/audit_ui_refs.py             # expect AUDIT CLEAN (78 modules)
ruff check orderflow_system scripts                           # expect: All checks passed
.venv/Scripts/python.exe scripts/regen_analytics_golden.py    # expect: OK (40 cases, max diff 0.000e+00)
.venv/Scripts/python.exe scripts/regen_config_golden.py       # expect: golden matches
# the twenty-three UI selftests (each prints "N ok, 0 failed"):
for f in orderflow_system/desktop/ui/*.selftest.js; do node "$f"; done
#   expression 50 · alert-format 20 · shell 30 · bus 13 · links 10 · watchlist 17 · news 17
#   options 21 · fundamentals 18 · market-pressure 12 · indicators 25 · intent 7 · study-api 45
#   search-ops all-pass · ofx 183 · cursor-link 7 · strips 9 · keys 42 · freshness 26 · windows-ui 10
#   help-search 26 (§79) · audio 39 (§76) · tape 11 (§76)
```

Live checks are done against a **sandbox**: `APPDATA="$LOCALAPPDATA/Temp/ofap_<name>_sandbox"
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 809x` (ports 8090–8094 only, never
Moddy's own install), driven over CDP at `http://127.0.0.1:809x/desktop/`. Stop every process afterwards and
check `orderflow.log` for `client error:` lines. A control → store round trip measures **~1.2 s** on a busy
sandbox — sleep ≥3 s between a control change and the read, or you read the previous adopt.

## Open items

| What | Where |
|---|---|
| **The flowsurface fold-in is CLOSED (§76, 2026-09-17)** — Binance, Hyperliquid and OKX all wired
and switchable (the `FeedSession` seam, POST-aware reachability probes, the extras gate widened),
sandbox end-to-end receipts (backfill 9,799 ticks / audio params / 0 client errors), counts landed.
The ☰ menu's self-recursive `api()` was found and fixed en route (`menu.js` + the `test_wiring.py`
pin). Still nothing committed. | handoff §76 |
| **Audit send-back answered (2026-09-17)** — the Desktop's `sendback.txt` audit re-verified claim by claim: F-01 (stale artifacts) is real and equals the owed `dist/` rebuild; F-02/F-04 withdrawn with evidence (manifest is correct; the audit ran the script with the wrong interpreter); F-05 = two README count lines; F-03/F-06 = receipts + notes lines. Value judgement + staged plan. | `docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md` |
| **Storage retention is live (7-day default; `data.retention_days` in config.json, 0 = keep forever)** — the next launch applies it; nothing in today's DB is older than 7 days. `POST /api/control/storage/prune` prunes now; the Logs panel shows the numbers. | handoff §54 |
| **The legacy page is retired (P3-3 done, §55)**: `GET /` → 307 → `/desktop`; the page's files stay on disk and the redirect is one reversible block in `launcher.build_app`. | handoff §55 |
| **The `/bin` heat wire is built, tested and NOT the view's default** — measured slower than the JSON path at real sizes (0.7 vs 0.8 ms @29 k cells; the bin is bigger on sparse books). Re-measure when a snapshot's JSON text passes ~2 MB or an adapt pass passes ~8 ms. | handoff §57 |
| **P3-1 (WebGL heat) stays deferred — now measured on his hardware**: 2560×1440 @ 144 Hz = 6.94 ms budget; the heat pass measures 0.6–0.7 ms (real payload, 1.7 k cells) and 1.3–1.7 ms (synthetic 30 k) at his resolution; the payload caps drawn cells at ~6 k (`max_columns: 900` @ 1 s buckets → ≤15 merged bars). Re-open: >~8 k drawn cells at his res, a true-4K canvas, or a >3.5 ms heat share of a warm frame. | handoff §59 |
| **The options/fundamentals residue is closed** — live captures: the supply cell's real child element (`20.09M BTC` + `of 21.00M max`), and the ATM strike's ticker strip shows `Γ 8.80e-4` (the exponential branch in live venue data, exactly as `fmtGreek` pins it). | handoff §59 |
| **The frozen build is current and on a diet (§63)**: `dist/ModFlowOrderFlowAnalysisSuite/` is 51.8 MB raw (68 MB before the diet; the §79 Help Centre added ~2.5 MB of screenshots and modules) — numpy (27 MB with OpenBLAS) and hook collateral (pytz/tzdata/watchfiles) are excluded from `scripts/build_exe.py`, and the analytics engines are stdlib-only (pinned by `test_analytics_golden.py` + `test_no_numpy.py`). Verified by a headless smoke of the exe itself. **UPX measured and not pursued** — a plain zip is 26.0 MB (−23.4 MB, zero risk) and packed DLLs barely zip further. | handoff §63 |
| **The release candidates are rebuilt and current (§79 close-out + MT5 fix)** — every hash in this file was re-measured after the rebuilds. `dist/ModFlowOrderFlowAnalysisSuite/` (525 files / 54,153,949 B raw) → zip `145a708b45ffc2ea…` (29,220,818 B, 525 entries, `namelist` + `testzip` OK) → Setup `8526f59dea125e80…` (30,213,471 B, 0 errors / 4 warnings, ships the same exe) → SBOM CycloneDX 1.5 (430,051 B, 42 components, unchanged). Verified: payload **120/120** loose files byte-identical to the tree, frozen-exe **smoke 29/29** (incl. the Help Centre assets, `/api/control/help`, asset parity 50/50, the MT5-portable checks), the double-launch acceptance passed (§75), and the installer journey re-run (silent install 525 files, installed exe hash == dist exe, silent uninstall clean). Ship the zip + Setup exe + SBOM as the release attachments. | handoff §79 |
| **The secure2 security sweep is applied (§70)** — report `docs/SECURITY_SWEEP_v0.1b.md` (14 findings, 13 fixed with pins; SS-8 open by design: lockfile/SBOM/dependency-scan CI). Loopback request guard + WS handshake check + feed-value gates + news-URL containment live in source, live sandbox and the frozen exe. | handoff §70 |
| **Display / multi-monitor audit is done (§71) — actionables first, NOTHING changed** — report `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md`: 16-size DPI matrix + drag/resize probes all pass (0 errors), but P0 fixes are needed before multi-monitor polish is worth doing: (A1) the Engine view paints at 1× — no `devicePixelRatio` in `ofx.js`/`ofx-view.js`, blurry on 125/150/200% displays; (A2) `mpCanvas` has no CSS size → inflates ×dpr per fit pass (measured 480×285→720×428 in one pass); (A3) `ofxRibbon` backing ≠ CSS box; (A4) generic refit covers only `.view.active` and `OFAPScale.register` has zero callers. P1: window geometry persistence + adaptive `min_size` + per-screen layout auto-apply (`screen_key` is stored but never applied at boot); P2: aux widget windows / send-to-monitor / pinning (pywebview 6.2.1 supports all of it; WebView2 cannot drag a window out of the page — the command form is the workable one). | handoff §71 |
| **The Python 3.11 question is settled (§65)**: the hang was 3.11's `asyncio.wait_for` answering a shutdown cancellation with the finished write's result (`if fut.done(): return fut.result()`) — the writer looped back to `queue.get()` and `asyncio.run`'s gather waited forever. The write deadline and the queue offer use `asyncio.timeout` now, pinned by `test_a_cancelled_writer_dies_even_when_its_write_just_finished` (proven to bite: 1 failed in 2.3 s with the old code). Full suite on 3.11: **595 passed / 2 skipped in 27 s** — the CI matrix and `requires-python = ">=3.11"` stay. | handoff §65 |
| **README counts are re-derived and current for the release (§79 close-out)** — all `(NNNL)` claims re-measured from the tree (two that had drifted since §76 were corrected: app.py 1381, settings.py 822); the File Inventory is the measured set (**191 files / 30,981 py / 41,631 UI / 72,612 total**; suite **78 files / 15,664 lines**; the JS claim **79 modules / 34,272 lines**); badges read ~73k lines, **881** tests, **138** API routes — re-derived again in the MT5-ships pass (the port ran to 565 entries). | handoff §79 + MT5-ships |
| **The docs screenshots are current (§75)**: the eleven Sep 14/15 shots were re-shot on 2026-09-16 against the ModFlow-branded build (same names, same sizes) and landed in `docs/screenshots/` — all eleven vision-verified, one re-shot mid-pass (`desktop-chart-value-area.png`); the caption rows in `docs/DESKTOP_GUI_FEASIBILITY.md` describe these files. | handoff §75 |
| **The §64 release pass is done** on disk: README/LICENSE/CONTRIBUTING/pyproject/CI corrected against measurements, `ruff check` clean, one live bug fixed (the source switch called a property) and pinned by `test_source_switch.py`. Gates: **594 passed / 2 skipped**, AUDIT CLEAN, ruff clean, both goldens OK, 19 selftests. | handoff §64 |
| **Closed in §57 (live-verified; kept so nobody reopens them)**: chart newest-bar colours (WS `candle` paints through `chartBars`; its own live wake-up not observed — no handle on the WS client, stated in §57); all three `window.prompt` sites (menubar `askText` + the drawings `inlineText` editors); alerts "new rule" affordance (draft→editor→save; drafts survive the poll); `wall` live detector (76 events live; entry-triggered); bus chip vs telemetry (agree 1/1 — the §29 row was stale); watchlist `ZZZTEST` row; the §38/§40 held-level visibility note (bounded by design, unchanged). | handoff §57 |

## Traps that cost time here (all measured, none theoretical)

- **A property called like a method reads as "the feature is broken", not as a code error.**
  `EngineController.state` is a `@property`, so `engine.state()` raised `TypeError: 'str' object is not
  callable` — and the endpoint's broad `except` turned that into "the restart failed", which is why
  switching data source saved the config but never restarted the engine (§64). When a call sits inside a
  catch-all, a `TypeError` is invisible: call the path in a test (`test_source_switch.py`).
- **A hanging pytest shows nothing in a pipe.** Piped output is buffered, so a stalled test prints zero
  lines; `-v` flushes per test and names the stall, `python -u` helps the same way, and a manual
  `loop.run_until_complete(...)` probe with a watchdog thread (`%LOCALAPPDATA%\Temp\ofap_taskprobe.py`)
  names the task that refuses to die. `test_websocket_backpressure.py` does exactly this on 3.11 (§64).
- **A module-local helper named `api` that guards with `typeof api` is checking itself.** The ☰
  menu's `menu.js` did exactly that: the guard was always true, every call recursed, and the
  `RangeError` died in each caller's `catch` — so the menu ran on its hardcoded fallback without a
  visible error (`/sources` never loaded; switching answered "source switch failed: RangeError:
  Maximum call stack size exceeded"). `menubar.js` names it correctly (`typeof window.api`);
  `test_wiring.py` now scans every `ui/*.js` for the shadowed form. When a list still renders, check
  the state behind it has *length*.
- **A reachability probe must speak the venue's own method.** Hyperliquid's `/info` is POST-only — a
  bare GET answers 405, which the old probe read as "unreachable" while the venue was healthy (the
  probe table now carries POST bodies, `_PROBE_PAYLOADS`). Check a new venue's REST semantics with
  `curl -w '%{http_code}'` before wiring its status dot.
- **This tree is mixed-EOL: older files are CRLF, §76's new files LF.** A wiring script whose
  anchors come from `read_file` must try `\n` then `\r\n` per edit and assert exactly one hit — else
  half the anchors "vanish" and the script aborts on a tree that is actually fine.
- **This venv has no pip** (uv-managed): `python -m pip …` answers "No module named pip". Use
  `uv pip install --python .venv/Scripts/python.exe …`, `uv venv --python 3.11 …`, `uv build --wheel`, and
  `uvx ruff check …` for the lint baseline. PyInstaller, pytest and every runtime dep are already in the venv.

- **SQLite here has no `DELETE … LIMIT`** — batch big deletes with a rowid subquery; and after a large
  delete+VACUUM, `PRAGMA wal_checkpoint(TRUNCATE)` or the WAL keeps the footprint the file lost
  (measured: 677 MB of WAL that the .db "shrink" hid).
- **Timestamps come in seconds or ms.** Bars are seconds; prints may be either. Normalise with the
  rule `raw > 1e11 → raw / 1000` (`math.selectionStats`, `buildPrintIndex`) — hover once read ms
  stamps as zero prints while blaming the feed.
- **A `<script>` tag with no file behind it takes the whole UI down** — the module loader replaces the
  shell with a "module error" banner. Land the file, then wire `index.html` and the audit. `test_wiring.py`
  now guards this.
- **Scope every panel's section lookup to `.view[data-view=…]`** — a bare `[data-view="x"]` matches the nav
  button first, and in terminal mode no nav button is ever `.active`, so the panel thinks it is off-screen
  and pauses. Guarded in `test_wiring.py`.
- **The bus coalesces requests that are still in flight** — a settled promise must leave the in-flight map,
  or its first answer stands in for that URL for the page's life (it froze every atlas panel once).
- **`requestAnimationFrame` may never fire in a headless page.** A repaint queued behind it never happens;
  paint directly. Same for `js()` probes: keep each under ~5 s or the CDP call times out.
- **A CDP `Enter` key event does not synthesise a focused button's click** — verify items by what the click
  produces.
- **The depth snapshot's axes are `values[PRICE ROW][TIME COLUMN]` with a flat `prices` ladder** —
  `heatmap-pro` reads `vals[ri][ci]`; anything walking that payload column-major draws the heat at the
  bottom of the ladder (it cost §52 a mis-diagnosis, corrected in §57). `adaptHeat`/`adaptHeatBin` are
  row-major; the ofx selftest fixtures are the real contract.
- **The bus fetch wrapper consumes every coalesced response body.** A non-JSON payload under a wrapped
  `/api/…` prefix must pass through UNREAD (each caller its own clone) or the caller sees
  `body stream already read` — and if the caller has a fallback, the failure is silent. `bus.selftest`
  pins the pass-through.
- **The rules auto-refresh adopts the server list directly** (`loadRules`) — anything client-only (a
  draft rule) must be re-merged after every adopt, or it is dropped out from under its open editor and
  the save no-ops in silence.
- **The browser caches the UI's JS while you patch live files.** Seen in §57: the patched `atlas.js`
  was in every served file and still not running in the page — drive checks with
  `Network.setCacheDisabled` before concluding a fix does not work.
- **A heat bench measures ZERO unless the bars span the cells' prices.** The heat painter culls
  off-viewport cells: synthetic bars at price 1.0 culled every 75 k-price cell and the pass read
  0.0 ms (§59, twice). And a forced heat pass needs `OFX.state.heatEpoch += 1` — `dirty.heat = true`
  alone measures the P2-2 SKIP path. Measure in one sync block (the 2.5 s poll reloads the view's own
  data between awaited turns), and use classic mode (`OFAPSHELL.switchTo('classic')`) — the terminal
  layout can leave the ofx stage at 354×148.
- **pywebview: the `icon` kwarg lives on `start()`, not `create_window()`**, and the WinForms
  backend takes a real `.ico` (a PNG raises `ArgumentException` from .NET). `build_exe.py`
  `--add-data`s the whole `ui/` dir, so `Path(__file__).parent/ui/<asset>` resolves in dev and
  through `_MEIPASS` in the frozen build.
- **Icon assets live at:** `assets/orderflow.ico` (shortcut icons; desktop shortcuts point here),
  `orderflow_system/desktop/ui/app.ico` (the path `build_exe.py` reads — a rebuild embeds it),
  `ui/app-icon.png` (favicon + 512 master), `assets/modflow-icon-1024.png` (badge master),
  `assets/modflow-icon-small-1024.png` (the simplified variant's master), `ui/brand-icon.png`
  (the rail brand mark — the badge at 128 px for its 32 px slot). The ICOs are **two-tier**:
  16/24 px = the text-free 0.58R centre zoom, 32 px+ = the full badge (PIL cannot mix artwork per
  size in one save — merge two ICOs at the byte level with adjusted offsets).
- **Patching a frozen exe's icon without a rebuild**: `BeginUpdateResourceW` + `UpdateResourceW`
  (RT_ICON × N, then RT_GROUP_ICON at the id found via `EnumResourceNames` on a
  `LOAD_LIBRARY_AS_DATAFILE` handle) + `EndUpdateResourceW`; back the exe up first, verify by
  extraction, and smoke-run the exe afterwards.
- **The automation browser is not immortal.** A process cleanup that catches it leaves the daemon
  unable to recover (`DevToolsActivePort not found`) and stacked daemons block new calls. Recovery:
  launch **Edge** `--remote-debugging-port=9222 --user-data-dir=<throwaway>` — the harness probes
  9222/9223 directly. No Chrome is installed here; Edge is the Chromium family on this box.
- **`POST /api/control/config` patches** (`merge_config`) while `save_config` writes what it is given over
  the defaults — the layout delete path depends on the latter.
- **Terminal mode bypasses `ui.js showView`**, so legacy panels created lazily by `ensurePanel()` need the
  hand-off in `shell.js buildFrame`, and a closed widget's section must drop `.active` (`releaseFrame`).
- **The cache-bust is `Network.setCacheDisabled`, never a query on the hash.** `#alerts?cb=…` is a
  same-document navigation: nothing reloads, and the app's own router no longer matches the view, so the
  panel silently never polls and the table stays empty. Navigate to plain `#<view>` and drive the view with
  `showView('<view>')`.
- **A checkbox has no value of its own.** Reading `b.value` from a channel checkbox answers the literal
  "on": an edited rule's sentence read `UI log + on + on` and a save would have stored a channel named
  "on". Read the key the markup wrote (`data-channel`); `test_alert_format.py` pins it.
- **A colour handed to Lightweight Charts must be CSS, not a bare triplet.** `'230,159,0'` makes the
  vendor THROW (`Error: Cannot parse color: …`) inside its own paint path — it does not fall back — and
  the thrown error used to take the whole UI with it (see the next trap). `chartBars` wraps every colour
  in `rgb(...)`/`rgba(...)`; `expression.selftest.js` asserts every emitted colour parses.
- **`toast()` REPLACES its target's `innerHTML`** — aim it at `document.body` and the banner becomes the
  app. Seven call sites did (the client-error reporter, guide ×2, search ×4). Fixed in `toast()` itself:
  a body-level notice lands in the fixed `#noticeStrip` instead. Never "fix" a caller back to body.
- **`studiesApply()` repaints the candle series from the raw bars on every load — with zero studies
  installed too.** The chart re-asserts the expression afterwards unless `default` + `theme`. A chart
  palette that "does not stick" is this pass winning; the condition lives in `ui.js` beside the call and
  is pinned by `test_expression.py`.
- **A cancelled task can be swallowed by 3.11's `wait_for`.** Its cancellation handler returns the
  awaited result when that future has already finished (`if fut.done(): return fut.result()`), so a task
  cancelled at shutdown — right after its write completed — loops forever and `asyncio.run` hangs in
  `_cancel_all_tasks`. Use `asyncio.timeout`, never `wait_for`, on any path a cancellation reaches (§65).
- **Windows serves a content type from the host's registry.** `mimetypes` reads `HKCR`; this host's
  `\.png\Content Type` is empty (3.11 → `application/octet-stream`, 3.12 falls back to `image/png`),
  so tests assert served bytes, not headers (§65).
- **`taskkill //F` is not a valid form in this shell** — it errors and a redirected stderr hides it;
  stop processes with `powershell -NoProfile -Command "Stop-Process -Id <pid> -Force"`, and remember
  PyInstaller's onedir build runs a parent+child pair (kill the PID that holds the port) (§65).
- **Python's `json` accepts the bare tokens `NaN`/`Infinity`, and every comparison with NaN is False** —
  `float(x) <= 0` cannot catch one, so a non-finite venue value sails into the aggregates and corrupts
  every downstream number without raising. Gate venue values with `math.isfinite` at ingest
  (`bybit_feed._finite`, `alpaca_normalize._num`); shown biting in §70 (`test_feed_value_guards.py`).
- **The local-request guard's Host allowlist must include `testserver`.** `LocalRequestGuard`
  (`dashboard/app.py`) is added at import time so the legacy dashboard and the desktop shell are both
  covered, and a loopback-only allowlist makes TestClient (whose Host is `testserver`) 403 on every
  request — the suite reads as broken, not the guard. `test_request_guard.py` pins both sides.
- **A CSP on a static shell is a meta tag with honest allowances.** `frame-ancestors` is ignored in a
  meta CSP; the app needs `'unsafe-inline'` (inline boot script/styles) and `'unsafe-eval'` (the
  Studies engine's `new Function`) — so the policy's real value is confinement: no remote script/
  image/connect target may be reached even if script is injected. Verify it live with a
  `securitypolicyviolation` collector (`Page.addScriptToEvaluateOnNewDocument`), never by eye (§70).
- **A canvas must have a CSS box, and its backing store must be `round(box × dpr)`** — the law is now
  enforced in all three places it matters (§72). A canvas with no CSS size displays at its *backing*
  size, so a fit pass that reads `clientWidth` and writes `width = clientWidth × dpr` becomes
  self-referential: the CVD view's `mpCanvas` used to grow 480×285 → 720×428 per pass at 150%
  (§71) — it now sets `style.width/height` before measuring and repaints from `PRESSURE.lastSeries`
  on `ofap:relayout`. `ofx.js` sizes every layer from its own CSS box through `math.layerSize()`,
  clears at 1:1 and paints in CSS pixels via `resetLayer()`; the ribbon's box is pinned to the stage
  width because it paints in the stage's coordinate space (a `width:100%` box with a stage-wide
  backing store is a ~17% stretch). `scale.js fitView()` walks the whole document — not
  `.view.active` — so a non-focused terminal widget is refitted after a window or display-scale
  change; `drawings.js` and `market-pressure.js` listen to `ofap:relayout` as well as `atlas.js`,
  `heatmap-pro.js`, `ofx-view.js` and `strips.js`.
- **The dpr = 1 path is the regression pin for anything display-scaled.** `math.layerSize(w, h, 1)`
  returns `w`/`h` unchanged and the selftests assert it (`ofx.selftest.js` §72 cases) — so when
  touching ofx sizing, market-pressure sizing or the ribbon, that identity must still hold.
- **A remembered window geometry is a choice, not a number — keep it a pure function.** The stored
  `ui.window` block is clamped by `config_store.clean_window()` (640…10000 × 420…6000, position only
  while ±20000); `launcher.pick_window_geometry(stored, screens)` then decides: a stored position
  wins while a screen still *contains* it, otherwise the primary, and the size AND the minimum clamp
  to that screen's work area (screen height − `WINDOW_CHROME_H`). The work area must always be able
  to win — a 1366×768 display at 150% reports ~911×512, where the pre-§72 fixed 1500×940 / 1080×680
  minimum could not fit at all. `remember_window()` writes the config once, on close, and keeps the
  last *normal* rect while maximised.
- **`screen_key` is `WxH@dpr`, plus `@x,y` when the screen's origin is not the primary's.** The
  primary keeps the original shape so layouts saved for it still match; the origin (from
  `window.screen.availLeft/availTop`) is what tells two identical monitors apart. `shell.js boot()`
  adopts the most recently saved layout tagged with this screen's key, in terminal mode, with a
  visible notice — a layout the store marks `active` is overridden by the screen's own.
- **An auxiliary window (`?aux=<view>&win=<id>`) must never write.** It renders a synthetic
  one-widget layout, is refused by `openWidget` (the shell's `showView` hook routes nav clicks into
  it — measured: a `#overview` hash from the previous window added a second widget) and clears its
  hash at boot. Its whole API surface is `/api/control/windows`: `open/close/focus/ontop/close_all`,
  each answering with the resulting state, and `native: false` where there is no host (browser,
  headless, tests) — in which case the UI draws **no** window control at all.
- **`ui.windows` is the desired set, not a history.** Opening adds a record, closing removes it
  (`close` from the API, the window's own ×, or the OS's X all land in `drop_record`), and a launch
  restores exactly what was open through `restore_windows()` **before** `webview.start()`.
  `place_aux` re-places anything whose monitor is gone onto the primary, so an unplugged display can
  never strand a window.
- **pywebview can create a window from the API thread.** Verified live: `webview.create_window` called
  from a uvicorn request thread produced a real, visible WinForms window at the requested rect on
  pywebview 6.2.1 / WebView2. `Window.destroy/move/resize/on_top/show/restore` are all usable from
  the same thread.
- **Verify WebView2 UI over CDP.** Launch with
  `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9223`, then
  `playwright.chromium.connect_over_cdp("http://127.0.0.1:9223")` from the webkit venv's python —
  that reaches the real windows (main, and each `?aux=` page), so menu clicks, pins and closes are
  tested as a user performs them, not inferred. OS-side window existence and geometry come from a
  small `EnumWindows` P/Invoke (and `SendMessage WM_CLOSE` simulates the title-bar X).
  Two probe rules from §128: a **new** aux window is only visible to a **fresh** `connect_over_cdp`
  (the existing connection does not surface it), and a menubar click must target the panel that is
  actually open (`.mb-title` → its own `.mb-menu`), because every menu's `.mb-item`s sit in the DOM
  and a stale panel resolves through `state.itemMap` to whatever now sits at that index.
- **One global per UI module.** `windowing.js` and `windows-ui.js` both assigned
  `window.OFAPWINDOWS`; the later script won, the View menu's dialog entry called an undefined
  `open`, and the dialog was unreachable — for two releases, until §128. The dialog is
  `OFAPWINMGR`, the widget-window menu is `OFAPWINDOWS`, and `test_windowing_ui.py` fails if the
  two assignments ever collide again.
- **The window is the truth about where it is; the store trails it.** `place_aux` re-places on
  what the STORE says, but the store only learns a move from pywebview's moved/resized events
  (throttled 2 s) — a window the OS left off-desktop (unplug, or a hand push) can leave a record
  that still looks fine. `windows.stranded(records, screens, live=…)` therefore takes both sources,
  and the state serves `open_geometry` (live rects + the monitor each window is on) beside
  `stranded`. `POST {action: "move"}` moves an OPEN window (`screen` index, `step` for "one monitor
  over" — cyclic, and a deliberate **no-op** when there is nowhere to go, so a one-monitor machine
  never re-centres a hand-placed window — or `preset` for the 10 snap shapes); `{action: "arrange"}`
  is Bring-them-home for every stranded window. `place_aux` is still the only path for a NEW window.
