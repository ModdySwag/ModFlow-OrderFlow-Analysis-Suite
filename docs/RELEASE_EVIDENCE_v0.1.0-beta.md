# Release evidence — v0.1.0-beta

One page of receipts for the release review (auditor / owner). Everything here was measured on
2026-09-16, on the committed tree (see `docs/SESSION_HANDOFF.md` §74 for the commit series).

## Artefacts (release candidates)

| Artefact | Bytes | sha256 (first 16) |
|---|---|---|
| `dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe` | 13,364,714 | `cfde70b04befd08f…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` | 27,207,924 | `b571c6551c7afe5b…` |
| `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` | 28,165,836 | `d2435b6f95c81328…` |

Provenance: all three were built from the same tree state the corpus was committed from; a full
payload check found **90/90 bundled loose files byte-identical to the committed tree**, with no
source file newer than the build. The frozen exe was smoke-run on loopback and its guard behaviour
observed live (below).

## Gates (on the committed content)

- pytest **712 passed / 2 skipped** — Python 3.12 and 3.11 (24.5 s each).
- `scripts/audit_ui_refs.py` — **AUDIT CLEAN** (71 modules, no broken calls / dead ids).
- `ruff check orderflow_system scripts` — clean.
- Analytics golden **0.000e+00** (40 cases); config golden **49 instruments**; 20/20 UI selftests.
- `pip-audit` over the locked set (`uv.lock`, 59 packages) — **no known vulnerabilities**.

## Security boundary (observed live, not inferred)

Against the frozen exe on loopback: a hostile `Host` header → **403**; cross-origin POST →
**403**; `Sec-Fetch-Site: cross-site` POST → **403**; a cross-origin WebSocket handshake →
**403**; a native WebSocket → **101**; legitimate loopback requests → **200**; the served
`/desktop` page byte-identical to disk. Source-level pins: `test_request_guard.py`,
`test_feed_value_guards.py` (the `math.isfinite` ingest gates), `test_context_hardening.py`
(news-URL scheme/size containment), `test_client_error_log.py`.

## Known limits (honest scope)

- The physical multi-monitor pass is the **owner's** (this host has one display).
- MT5 paths are covered by fixtures; no MT5 terminal exists on the build host.
- This is a beta: the app is loopback-only, market-data-only, and places no orders on any venue.

## Where to look

- `docs/SECURITY_SWEEP_v0.1b.md` — the pre-release security sweep (14 findings; SS-8 closed in §74).
- `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md` — the display audit the §72 hardening answers.
- `docs/AUDIT_RETURN_v0.1b.md` — the audit-return pass (§66–§68).
- `docs/SESSION_HANDOFF.md` §74 — the pre-tag pass: the commit series, the counts, SS-8.
