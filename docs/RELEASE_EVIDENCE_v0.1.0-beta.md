# Release evidence — v0.1.0-beta

One page of receipts for the release review (auditor / owner). Everything here was measured on
2026-09-16, on the committed tree (see `docs/SESSION_HANDOFF.md` §74 for the commit series and §75
for the post-beta left-overs — the N-1 guard, CI lint/SBOM parity, the screenshot re-shoot, and the
rebuild this page describes).

## Artefacts (release candidates)

| Artefact | Bytes | sha256 (first 16) |
|---|---|---|
| `dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe` | 13,371,238 | `10e6bdf8755abb0e…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` | 27,229,338 | `00b96304e54949e0…` |
| `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` | 28,173,338 | `c3a14576a5a5a5b5…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json` | 430,051 | `34fb03c49752de6f…` |

Full hashes:

```
10e6bdf8755abb0e2c1a9556fbbe213a5c46955d1a3126158ad29a355dd64ad5  ModFlowOrderFlowAnalysisSuite.exe
00b96304e54949e0f3bd42cfb0b329a1ffd9e4596d631b93fcb3fe8af16a1f43  ModFlowOrderFlowAnalysisSuite-win64.zip
c3a14576a5a5a5b5320addb69b32823c99d61b77bb5fa7705eac2c4f9e9f743d  ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe
34fb03c49752de6ff02c9b249ff6edf46783d44c843611af80003a5578baa7e9  ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json
```

Provenance: **rebuilt in §75 after the N-1 guard touched a bundled file** (the exe → zip → Setup
chain, all three from the same frozen dist). The payload check found **90/90 bundled loose files
byte-identical to the committed tree**, with no source file newer than the build; the zip extracts
to 496/496 files byte-identical to the frozen folder (7-Zip test: everything OK); the Setup ships
the same exe (installed copy hashes to the dist exe). The frozen exe was smoke-run on loopback and
its guard behaviour observed live (below). The SBOM is a CycloneDX 1.5 export of the lockfile (42
components); a fresh `uv export --frozen --format cyclonedx1.5` is content-identical apart from its
timestamp/serial.

Dist sizes: 496 files / 51,777,966 bytes (49.4 MB) raw → 27,229,338 bytes (26.0 MB) zipped.

## Gates (on the committed content)

- pytest **716 passed / 2 skipped** — Python 3.12 (24.4 s) and 3.11 (24.6 s).
- `scripts/audit_ui_refs.py` — **AUDIT CLEAN** (71 modules, no broken calls / dead ids).
- `ruff check orderflow_system scripts` — clean (ruff 0.16.7, the version CI pins).
- Analytics golden **0.000e+00** (40 cases, 2196 numeric leaves); config golden **31/18/49**;
  **20/20 UI selftests** (each prints "N ok, 0 failed").
- `pip-audit` over the locked set (`uv.lock`, 42 packages in the audit export) — **no known
  vulnerabilities**.

## Security boundary (observed live, not inferred)

Against the freshly built frozen exe on loopback (21/21 probes, headless on 8099): a hostile `Host`
header → **403** on `/healthz` and on `/api/control/bootstrap`, with the refusal body leaking
nothing; cross-origin POST → **403**; `Sec-Fetch-Site: cross-site` POST → **403**; a cross-origin
WebSocket handshake → **403**; a cross-site-declared handshake → **403**; a native WebSocket →
**101** (the app's own `pong` came back); loopback-origin and native POSTs → **200**; cross-origin
read → **200**; the served `/desktop` page **byte-identical to the packaged `index.html`**
(sha256 `d61ebc1f8c2c33d3…`) and carrying the CSP; unknown symbols → **`[]`** on candles and
markers; **0 numpy entries** in the 586 `_internal` entries; **0 `client error:` lines** in the
app log. Source-level pins: `test_request_guard.py`, `test_feed_value_guards.py` (the
`math.isfinite` ingest gates), `test_context_hardening.py` (news-URL scheme/size containment),
`test_client_error_log.py`.

## Frozen-build acceptance (§75)

- **Double-launch (N-1).** Windowed launches, scratch `APPDATA`: the first opens the window on
  port 8080; a second launch in the same profile **exits 0 immediately**, bringing the existing
  window forward — afterwards still one process, one window, one listening port. A third launch
  while the first still holds the profile is refused the same way. Closing the window (WM_CLOSE,
  the title-bar X) releases the profile: the process is gone in ~2 s, the port is free, and the
  next launch comes up normally.
- **Installer journey.** Silent install (`/s /v"/qn"`): **496 files** under
  `%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`, the installed exe hashing to the dist
  exe above, desktop shortcut targeting the installed exe, ARP entry `0.1.0`. The installed app
  smoked headless on 8098 (healthz 200, BTCUSDT candles 200, unknown symbol `[]`, hostile Host
  refused, 0 client errors). Silent uninstall (`msiexec /X {197F9514-8159-4736-80E3-8B9D758E0BB0}
  /qn`): install dir, shortcut and ARP entry all gone, `%APPDATA%` untouched. The owner's
  development shortcut was backed up and restored around the journey.

## Known limits (honest scope)

- The physical multi-monitor pass is the **owner's** (this host has one display).
- MT5 paths are covered by fixtures; no MT5 terminal exists on the build host.
- This is a beta: the app is loopback-only, market-data-only, and places no orders on any venue.

## Where to look

- `docs/SESSION_HANDOFF.md` §75 — the post-beta left-overs: the N-1 guard, the CI lint/SBOM
  parity, the screenshot re-shoot, the counts, and this rebuild.
- `docs/SECURITY_SWEEP_v0.1b.md` — the pre-release security sweep (14 findings; SS-8 closed in §74).
- `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md` — the display audit the §72 hardening answers.
- `docs/AUDIT_RETURN_v0.1b.md` — the audit-return pass (§66–§68).
