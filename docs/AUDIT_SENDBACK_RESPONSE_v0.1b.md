# Audit send-back — value judgement + implementation plan

**Source audit:** `C:\Users\Moddy\Desktop\sendback.txt` — a release-readiness audit of this tree,
written 2026-09-16 23:59 against `aa43f40` + the 40 uncommitted paths ("SHIP ONLY AFTER REQUIRED
FIXES"). Not to be confused with `docs/AUDIT_RETURN_v0.1b.md` (§66's earlier, different return).
**Re-verified:** 2026-09-17, against the working tree on disk — every claim below was re-tested
here; the numbers are measured, not quoted from the audit.

**Status 2026-09-17:** **executed end to end** — §76 committed in five waves (`47ae326` → `096c055` → `25efd48` → `96cd327` + the docs wave), `dist/` rebuilt from the committed tree; receipts in `docs/SESSION_HANDOFF.md` §77 and `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`. Nothing pushed, no tag.

## 1. Verdict per finding

### F-01 (P0) "Artifact is stale vs current master + dirty tree" — TRUE, highest value

Measured: `dist/` Setup exe 22:15:45, zip 22:14:00 (both §75's build), SBOM 22:25; every §76 source
file postdates them (`binance_feed.py` 22:59 … `menu.js` 23:34). A `find` over the frozen tree
returns **no** §76 module — the four-venue feed work, the backfill, the audio and the ☰ menu fix are
all absent from the shipped build. HEAD `aa43f40`'s committed tree is §75; the fold-in is entirely
uncommitted.

**Judgement — attend first.** A tag cut from today's tree publishes an exe that predates four
advertised venues; the release notes would describe code no reviewer has run. This is exactly the
standing debt ("a `dist/` rebuild is owed first") — the audit independently corroborates it, which
is its single most useful contribution. Cost: one rebuild + the verification battery below (all
recipes already exist). Benefit: a release reproducible from the tagged commit; without it, none.

### F-02 (P0) "pyproject.toml does not declare aiosqlite" — NOT TRUE; no defect to fix

Measured: `pyproject.toml` line 31 declares `"aiosqlite>=0.19"` (added in `b2ff4ee`, present at
HEAD). With the venv interpreter, `scripts/audit_ui_refs.py` ends `... 4. modules import: ok` →
`AUDIT CLEAN`. The audit's `ModuleNotFoundError` reproduces **only** with plain `python` — the
system 3.11 that does not carry the project's deps; the script's own docstring says to run it with
`.venv/Scripts/python.exe`, and CI installs from pyproject before running the same script on
3.11+3.12. Both paths were reproduced here to prove it.

**Judgement — dismiss as a defect; keep one tiny improvement.** Make the script's import gate fail
loudly with the interpreter it used and the command it wants (message-only edit). That prevents the
same phantom P0 on the next external pass. F-04 is the same artifact — same root cause, same
disposition.

### F-03 (P1) "New venue feeds advertised but fault paths not audited" — PARTLY TRUE; the gap is receipts, not code

Measured: the six new test files carry **106 cases** covering the audit's own asks — reconnect
ladder, jitter, reset-on-parsed-data (`test_feed_session.py`); snapshot/diff chains, straddle gate,
resync, pending-buffer cap (`test_binance_feed.py`); wholesale snapshot, empty-never-erases,
quiet-book budget, unknown channel (`test_hyperliquid_feed.py`); checksum top-25, seq-reset
adoption, resubscribe (`test_okx_feed.py`); window-replace idempotency, `.part` cache, prune,
ceilings (`test_backfill*.py`). §76 already ran live receipts (Hyperliquid 128 ticks / 20 s; OKX
577 / 20 s; Binance 4,759 / 20 s; sandbox backfill 9,799 ticks; 0 client errors).

**Judgement — attend as verification, not development.** The release notes claim four venues; run
the battery from the release commit (repo tree + sandbox + frozen exe) and attach the receipts.
That is the audit's option (b): keep the claim, complete the evidence. Deeper fault-injection,
long-session profiling and clean-box installer smoke stay deferred (§4) — nothing there blocks a
scoped beta tag.

### F-05 (P2) "README install/entry-point wording + module counts drift" — half wrong, half real-and-narrow

- **Entry points / install:** already accurate. README uses `python -m orderflow_system.desktop`
  (`.main`, `.dashboard`) — the real launchers; `.[dev]`/`.[mt5]` match the manifest; the pyproject
  `orderflow` script is an extra the README never claims.
- **Counts:** real drift in the two spots §66's "(NNNL)" sweep could not catch (they are not
  parenthesised): **line 231** `~30,400L across 70 files` and **line 535** `70 vanilla-JS modules`.
  Measured today: **75 `.js` files / 30,113 lines** recursively (74 parse-audited — the audit
  script excludes the vendor chart copy; 22 of the files are selftests). The File Inventory row
  (84 files / 32,469 incl. CSS+HTML) is already accurate.

**Judgement — attend; two line edits** (exact replacements in Stage 1.1).

### F-06 (P3) "Supply-chain posture should be stated explicitly" — mostly pre-covered; residual ~3 lines

Measured: `SECURITY.md` states the deployment surface (loopback default, no login by design,
market-data only, creds local, no telemetry); CI runs `pip-audit` over the locked set and emits a
CycloneDX SBOM (`uv export --frozen --format cyclonedx1.5`);
`docs/RELEASE_EVIDENCE_v0.1.0-beta.md` records "no known vulnerabilities" over 42 components plus
the reproduction path. Residual: 2–3 honest lines in the final release notes (how to reproduce the
SBOM/audit; loopback single-user default; generic transitive-CVE relevance is deployment-dependent;
no unsourced claims).

**Judgement — attend (near-zero cost), inside the already-queued release-notes review.**

### The audit's "not executed" rows — closed here

Re-ran today on the working tree: pytest **843 passed / 2 skipped** (3.12, 26.7 s);
`audit_ui_refs.py` **AUDIT CLEAN**; ruff 0.16.7 **clean**; analytics golden **0.000e+00** (40
cases); config golden **31/18/49**; UI selftests **22/22** (search-ops prints "all checks passed" —
its own format, not a failure). The remaining rows (artifact coherence, frozen-exe smoke, the
candle-wiring assertion in a live run) belong to the rebuild — Stages 1.3/2.2.
"Known limitations documented — No" is partly stale: the Desktop draft already carries them
(loopback by design; the physical multi-monitor pass post-release; MT5 fixture-covered; Windows).

## 2. The judgement in one paragraph

The audit's value is corroboration + a pre-tag checklist, not a new defect list. Of its two P0s,
one is real and already-owned (stale artifacts), one is a phantom (the manifest is fine — the
auditor used the wrong interpreter). Its P1 is a verification ask the repo has already answered in
tests and live receipts, pending a re-run at the commit. What actually remains: commit the §76
series deliberately (owner's go), rebuild + re-verify the artifacts, fix two README count lines,
add two small notes lines, and capture receipts. **Explicitly not doing:** touching `pyproject.toml`
(nothing missing), duplicating fault tests that exist, forcing a clean-env reinstall to satisfy
F-04 (CI does that on every push; this venv is uv-managed without pip), or a pre-tag CVE deep dive.

## 3. Implementation plan

### Stage 0 — verify the tree as-is (all green today; re-run at the commit)

```bash
unset PYTHONPATH
.venv/Scripts/python.exe -m pytest orderflow_system -q          # 843 passed / 2 skipped
.venv/Scripts/python.exe scripts/audit_ui_refs.py               # AUDIT CLEAN
uvx --from ruff==0.16.7 ruff check orderflow_system scripts     # All checks passed
.venv/Scripts/python.exe scripts/regen_analytics_golden.py     # OK (40 cases, 0.000e+00)
.venv/Scripts/python.exe scripts/regen_config_golden.py         # golden matches
for f in orderflow_system/desktop/ui/*.selftest.js; do node "$f"; done   # 22/22
```

- **0.2 [tiny]** `scripts/audit_ui_refs.py`: on import failure, print the interpreter used and the
  `.venv/Scripts/python.exe` invocation. Message-only; keeps F-02/F-04 from recurring.

### Stage 1 — the release blockers (minimal behavioural change)

- **1.1 README count fix** (two lines, docs-only; rule = per-file `wc -l` over `ui/**/*.js`
  recursive, 22 of the 75 are selftests; the reference audit counts 74 — it excludes the vendor
  chart copy):
  - L231: `│   └── ui/ ─── vanilla-JS modules (~30,100L across 75 files) + index.html`
  - L535: `**75 vanilla-JS modules**` (in `orderflow_system/desktop/ui/`), noting the 22 selftests.
- **1.2 Commit the §76 series** — ONLY on the owner's explicit go (repo rule: nothing is committed
  unless asked). 40+ paths → four commits, in this order, nothing mixed:
  1. feeds + session + backfill + their tests (`data/*.py`, `test_*feed*`, `test_backfill*`)
  2. desktop wiring (`api.py`, `engine.py`, `config_store.py`, `settings.py`, `main.py`, `param_registry.py`)
  3. UI + audio + menu fix + pins (`ui/*`, `dashboard/static/tape.js`, `test_wiring.py`,
     `test_source_switch.py`, `scripts/make_alert_sounds.py`)
  4. counts/docs (README, CONTRIBUTING, RESUME, SESSION_HANDOFF, `docs/FLOWSURFACE_FOLD_IN_PLAN.md`,
     `flowsurface-notes/`, this doc)
  Acceptance: gate battery green from the committed tree; `git status` clean.
- **1.3 Rebuild the artifacts from the committed tree**:
  - `.venv/Scripts/python.exe scripts/build_exe.py` → `dist/ModFlowOrderFlowAnalysisSuite/`
  - zip with Python's `zipfile` (never `Compress-Archive` — it mangles this tree's entry names,
    handoff L4090); verify `namelist()` + a `7z t` pass
  - `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File installer\make_installer.ps1`
  - `uv export --frozen --format cyclonedx1.5 --output-file dist/ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json`
  - Re-verify (the §75 battery, re-run): payload loose files byte-identical to the tree; served
    `/desktop` hash-matches the packaged `index.html`; unknown symbol → `[]`; guard probes;
    double-launch acceptance; 0 `client error` lines.
  - Refresh `docs/RELEASE_EVIDENCE_v0.1.0-beta.md`: new hashes, counts (badge 843, suite 76 files /
    15,091 lines, inventory 185 / 67,542), the new receipts.

### Stage 2 — F-03 receipts (no new code)

- **2.1 From the release commit:** 3.11 parity run (`uv venv --python 3.11`); per-venue probes from
  the repo tree (bybit / binance / hyperliquid / okx, ~20 s tick counts each); sandbox pass on port
  809x — source switch, backfill round trip, audio params via `/api/control/params`, then scan
  `orderflow.log` for `client error:`.
- **2.2 Frozen-exe smoke + live guard battery** (the 21/21 shape); confirm the engine's
  `_verify_candle_wiring` assertion in the smoke log. Attach all receipts to the evidence page.

### Stage 3 — notes + release sequence (owner)

- **3.1 Release notes final:** add the F-06 lines; confirm the limitations section; owner reviews
  the Desktop draft.
- **3.2 Owner queue as recorded:** push decision (the remote is still the original author's repo) →
  the owner's physical multi-monitor pass (§77 if it finds anything) → tag `v0.1.0-beta` with the
  zip + Setup exe + SBOM attached.

### Stage 4 — deferred (agreed with the audit)

Per-venue fault-injection beyond the pinned tests; long-session / resource profiling;
multi-monitor aux-window stress; clean-box installer smoke; per-CVE deep dive (post-tag, against
the new SBOM). None of these block a scoped beta tag.

## 4. Exit gate (binary — mirrors the audit's §8)

| Checklist row | Current state | Closes with |
|---|---|---|
| Tree collapsed to v0.1b scope | dirty (40 paths) | Stage 1.2 (owner go) |
| Tag cut from a clean commit | untagged | Stage 1.2 / 3.2 |
| License present | YES | no change |
| README accurate | 2 stale count lines | Stage 1.1 |
| No secrets committed | YES (per-user config) | no change |
| Lockfile present/consistent | YES (`uv.lock`) | no change |
| Clean install works | CI installs from pyproject on 3.11+3.12 | F-02 withdrawn |
| Lint / tests / build pass | 843-2, ruff clean, goldens OK, 22/22 | re-run at commit (Stage 0 / 1.3) |
| Production smoke | not yet on the new build | Stage 1.3 / 2.2 |
| P0/P1 resolved | F-01 = rebuild; F-02/F-04 withdrawn; F-03 = receipts | Stage 1–2 |
| Known limitations documented | Desktop draft | Stage 3.1 |
| Release artifact inspected | stale today | Stage 1.3 |
| Rollback / release plan | retag · rebuild from the audited commit | unchanged |
