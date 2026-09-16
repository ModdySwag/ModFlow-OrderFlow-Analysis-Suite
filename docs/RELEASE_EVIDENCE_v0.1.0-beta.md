# Release evidence — v0.1.0-beta

One page of receipts for the release review (auditor / owner). Everything here was **re-measured on
2026-09-17** on the §76-committed tree and its rebuilt artefacts (§77 — the audit send-back pass:
`docs/SESSION_HANDOFF.md` §77; the judgement that drove it: `docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md`).

## Artefacts (release candidates)

| Artefact | Bytes | sha256 (first 16) |
|---|---|---|
| `dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe` | 13,550,202 | `2731442153522d4f…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` | 27,419,732 | `111198918df88176…` |
| `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` | 28,412,633 | `b2309cc97aa61da4…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json` | 430,051 | `97184c0bc6f3eea4…` |

Full hashes:

```
2731442153522d4f8f298e0f60427d8bae31d57aca060620948141c84a792bfa  ModFlowOrderFlowAnalysisSuite.exe
111198918df881767c7f16f37d97ab74a8065c6d8a2443ef3483bc771f4e30cf  ModFlowOrderFlowAnalysisSuite-win64.zip
b2309cc97aa61da4473e204a84a70d1b9633620bece71caac5bb8f549fb87ef5  ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe
97184c0bc6f3eea4c7bc64a103e68d8214a2484f21ea2817b61ccb1e3c83d5d3  ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json
```

Provenance: **rebuilt in §77 from the §76-committed tree** (the exe → zip → Setup chain, all from
the same frozen folder). Checked: **no source file newer than the build**; the zip holds **503
entries**, `namelist()` + `testzip()` OK (+7 files vs §75 — exactly the §76 payload: the four alert
WAVs, `audio.js`, `audio.selftest.js`, `tape.selftest.js`); the Setup was built from the same frozen
folder (`installer/make_installer.ps1`, 0 errors / 4 warnings, sizes above); the SBOM is a fresh
CycloneDX 1.5 export of the unchanged lockfile (42 components). The frozen exe was smoke-run on
loopback and its guard behaviour observed live (below). *(The §75 installer journey — silent
install/uninstall on this machine — was not re-run in §77; the Setup's mechanics are untouched and
only its payload changed.)*

Dist sizes: 503 files / 52,039,333 bytes (49.6 MB) raw → 27,419,732 bytes (26.2 MB) zipped.

## Gates (on the committed content)

- pytest **843 passed / 2 skipped** — Python 3.12 (24.6 s) and 3.11 (25.2 s; fresh venv).
- `scripts/audit_ui_refs.py` — **AUDIT CLEAN** (74 modules, no broken calls / dead ids).
- `ruff check orderflow_system scripts` — clean (ruff 0.16.7, the version CI pins).
- Analytics golden **0.000e+00** (40 cases, 2196 numeric leaves); config golden **31/18/49**;
  **22/22 UI selftests** (search-ops reports "all checks passed" — its own format).
- `pip-audit` 2.10.1 over the locked set (42 packages) — **no known vulnerabilities** (re-run in
  §77).

## Security boundary (observed live, not inferred — §77 smoke on the rebuilt exe, 18/18)

Headless on 8093, scratch `APPDATA`: a hostile `Host` header → **403** (raw-socket request);
cross-origin POST → **403**; `Sec-Fetch-Site: cross-site` POST → **403**; loopback-origin POST →
**200**; a native WebSocket → **accepted + ping/pong**; a cross-origin WebSocket handshake →
**refused (403)**; the served `/desktop` page **byte-identical to the packaged `index.html`**
(sha256 `369fbbc6e36e1332…`) and carrying the CSP; unknown symbols → **`[]`** (markers + candles on
the exe; candles, markers, volume-profile, delta and bias re-observed on the tree's demo branch);
the `/api/control/sources` list carries all six venues with binance/okx/hyperliquid `wired:true`;
**0 `client error:` / 0 `ERROR` / 0 `Traceback`** in the app log. Source-level pins:
`test_request_guard.py`, `test_feed_value_guards.py`, `test_context_hardening.py`,
`test_client_error_log.py`, `test_demo_symbol_guards.py`.

## §76 receipts (the fold-in, driven through the app in §77's sandbox)

- **Four venues, one switch:** binance / okx / hyperliquid / bybit each switched via
  `/api/control/source` (`ok=True`), engine `running`, BTCUSDT ticks flowing on every venue (fresh
  `last_tick_ms`); tape `live` on bybit with a live print at 75610.7.
- **Archive backfill, round trip:** `POST /api/control/backfill` BTCUSDT `2026-09-13` → **512,737
  ticks / 6,390,912 B** downloaded, job `done`; read back through `/api/control/trades`
  (`total = 512,737`, page capped at 50,000, `truncated = true`).
- **Trade audio, param round trip:** the **eight** `audio.*` variables set through
  `/api/control/params` (volume 0.55, min_size 25000) and read back from the registry **and**
  `config.json` (block matches).
- **Sandbox log: 0 client errors, 0 ERROR, 0 Traceback.**

## Frozen-build acceptance (§75, carried — not re-run in §77)

- **Double-launch (N-1) acceptance:** as measured in §75 (windowed; second launch exits 0; still
  one process, one window, one port).
- **Installer journey (§75):** silent install 496 files → installed exe hashes to the dist exe →
  smoke on 8098 (healthz 200, BTCUSDT candles 200, unknown symbol `[]`, hostile Host refused,
  0 client errors) → silent uninstall clean; `%APPDATA%` untouched. §77 ships the same Setup
  mechanics with the rebuilt payload; a fresh re-run is recommended once if the owner wants it.
- **0 numpy entries** in `_internal` (§75 measurement; §76 adds no math dependency — the analytics
  golden and `test_no_numpy.py` still gate this).

## Known limits (honest scope)

- The physical multi-monitor pass is the **owner's** (this host has one display).
- MT5 paths are covered by fixtures; no MT5 terminal exists on the build host.
- This is a beta: the app is loopback-only, market-data-only, and places no orders on any venue.

## Where to look

- `docs/SESSION_HANDOFF.md` §77 — this pass: the send-back judgement, the §76 commit series, the
  rebuild and its receipts.
- `docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md` — the value judgement + the implementation plan.
- `docs/SESSION_HANDOFF.md` §75 — the post-beta left-overs (N-1 guard, CI lint/SBOM, screenshots).
- `docs/SECURITY_SWEEP_v0.1b.md` — the pre-release security sweep (14 findings; SS-8 closed in §74).
- `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md` — the display audit the §72 hardening answers.
- `docs/AUDIT_RETURN_v0.1b.md` — the audit-return pass (§66–§68).
