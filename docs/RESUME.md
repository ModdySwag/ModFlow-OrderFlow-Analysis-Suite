# Resume here — ModFlow OrderFlow Analysis Suite

> ## ▶ RE-ATTENDANCE (latest, 2026-09-17 night — **MT5 SHIPS: numpy + the bridge bundled, verified against a real MT5 terminal; a live DOM defect found and fixed**; nothing committed, nothing pushed, no tag)
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
