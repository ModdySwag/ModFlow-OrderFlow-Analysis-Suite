# ModFlow OrderFlow Analysis Suite — pre-release security sweep (v0.1b)

**Directive applied:** `Desktop/secure2.txt` — *Pre-Release Software Audit and Security Sweep
Directive* (Phases 1–6, required finding format, P0–P3 roadmap).
**Tree:** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · HEAD `fa202d6`, tree dirty (P1-7…§70 on disk,
uncommitted — nothing is ever committed in this repo without an explicit instruction).
**Date:** 2026-09-16.
**Rule observed throughout:** every fix is isolated, lands with a test proven to bite against the
untouched code first, and was re-verified against the full gate stack before the next one started.
Nothing is claimed that was not executed: *Confirmed* below means a pin or a live probe exists.

---

## A. Executive release assessment

The repository is in materially better shape than a typical v0.1 beta: no secrets in tree or
history, no execution-capable code paths, a disciplined escaping layer in the UI, parameterised
SQL, verified TLS everywhere, and a test suite (629 cases at the start of this pass) that already
pinned the hard market-data behaviours from the previous audit round. This sweep targeted the
attack surfaces specific to a *desktop app that runs an HTTP/WebSocket server*: every finding
below was reproducible against the untouched tree, and every one that was a release blocker is
now fixed and pinned (suite 629 → **649 passed / 2 skipped**). The two highest-risk items were
browser-native attacks on the loopback API (DNS rebinding and cross-site POSTs) plus one
market-data integrity hole (non-finite venue values were accepted by both feeds). All are closed
with evidence, not argument.

**Current release recommendation:** **Release only after the P0 blockers are resolved** — and all
P0 items listed in section I are now resolved in the working tree. Remaining before shipping is
mechanical: rebuild the frozen artefacts from the hardened source (done in this pass), and run
the owner's release sequence (commit → repo → tag → attach artefacts).

**Findings by severity / confidence:** Critical 0 · High 3 (all fixed) · Medium 5 (all fixed) ·
Low 5 (all fixed) · Informational 1 (fixed) — 14 findings, 13 fixed in this pass, 1 recommendation
still open by design (SS-8, dependency scanning/SBOM tooling; see section I). Confirmed 12 ·
Likely 1 (SS-5's *exploitability from a real venue*; the code path itself is Confirmed) ·
Suspected 0 · Not verified 1 (SS-8 item scope, listed in L).

---

## B. Repository, architecture and trust-boundary map

**Stack.** Python 3.11+ (CI: 3.11 + 3.12), no build step for the UI. FastAPI/Starlette + uvicorn;
pywebview (WebView2) shell; vanilla-JS modules in `desktop/ui/` (~35.8k lines); stdlib-only
analytics engines (numpy deliberately excluded from the frozen build); SQLite (aiosqlite);
outbound clients: `urllib`, `websockets`, `aiohttp` (webhooks only), `python-telegram-bot`.

**Components and entry points.**

| Component | Path | Notes |
|---|---|---|
| Desktop shell | `orderflow_system/desktop/launcher.py` | binds **127.0.0.1** (`free_port`, `serve`); pywebview window at `/desktop`; **no `js_api` / native bridge exposed** |
| Control API | `desktop/api.py` (79 routes) | settings, engine control, exports, workspaces, layouts, search, Alpaca, MT5, Telegram |
| Analytics API | `atlas/api.py` (41 routes) | heatmap, tape, CVD, profile, frames, replay, alerts, exports, webhook settings, market context |
| Legacy dashboard app | `dashboard/app.py` (19 routes + `/ws`) | same origin, serves the desktop shell; legacy page retired behind 307 |
| Market-data feeds | `data/bybit_feed.py`, `data/alpaca_feed.py`, `data/mt5_feed.py`, `atlas/feed_extras.py` | Bybit = default public feed (no key); Alpaca keys optional |
| Config store | `desktop/config_store.py` | per-user `%APPDATA%\OrderFlowAnalysisPro\config.json`, sanitised + clamped |
| Persistence | `data/database.py` | SQLite, WAL, 7-day retention default |
| Frozen build | `scripts/build_exe.py`, `installer/` | PyInstaller onedir + InstallShield MSI, per-user install |

**Data-flow (text).**

```
venues (Bybit wss / MT5 terminal / Alpaca https+wss)
        │  untrusted frames
        ▼
data/*_feed ── value containment (NEW: finite/positive) ──► analytics engines
        │                                                    (footprint, delta, CVD, profiles)
        ▼                                                          │
dashboard/app  ──►  WebSocket /ws ──► browser page ──► canvas      │
   ▲   ▲                        (same origin)                      │
   │   └──────── /api/* (control + atlas + fundamentals) ◄── user gestures / polls
   │
loopback HTTP server (uvicorn, 127.0.0.1)  ◄── GUARD (NEW): Host allowlist + Origin/Sec-Fetch on
   │                                              mutating methods; WS handshake checked
   └── user config file (keys live here, never in logs/commits)
outbound-only extras: RSS/news URL (NEW: http(s) only, 4 MiB cap, no internal-DTD), EDGAR,
CoinGecko, Deribit, ntfy/webhook/e-mail/Telegram (user's own channels)
```

**Trust transitions.** (1) venue frame → analytics (untrusted → numeric aggregates);
(2) browser page → loopback API (any page on the machine can *reach* it — this sweep's main
theme); (3) user-pasted study module → `new Function` in the page (accepted, documented);
(4) user config file → API responses (secrets are served to the page — accepted, see F).

---

## C. Threat model

**Assets.** (a) Market-data credentials (Alpaca key/secret, Telegram bot token, DTC/email
credentials) in the user config file; (b) analytic integrity — footprint/delta/CVD/POC outputs
that inform trading decisions; (c) availability of the app during busy markets; (d) the user's
machine as an origin for outbound requests; (e) release integrity (repo, artefacts, CI).

**Actors.** (1) An unauthenticated internet/website — the dominant actor for a loopback server:
a page the user visits can *send* requests and open websockets to 127.0.0.1 even though it cannot
read cross-origin replies. (2) A malicious or broken venue endpoint / feed payload. (3) A
malicious imported file or pasted module. (4) A local unprivileged process (out of scope as a
security boundary — same user ⇒ same file access; see SECURITY.md). (5) Supply chain (CI, deps).

**Highest-risk boundaries (and their status after this sweep):**

| # | Boundary / abuse case | Status |
|---|---|---|
| 1 | Website → loopback API via DNS rebinding (read config incl. keys) | **closed** (SS-1) |
| 2 | Website → body-less mutating POSTs (engine stop, config reset, logs clear, prune) | **closed** (SS-2) |
| 3 | Website → `ws://127.0.0.1/ws` stream (not CORS-gated) | **closed** (SS-3) |
| 4 | `news_url` GET parameter → blind SSRF / `file://` / memory growth | **closed** (SS-4) |
| 5 | Venue frame with NaN/Inf/negative price or size → silent aggregate corruption | **closed** (SS-5) |
| 6 | Legacy pipeline binding 0.0.0.0 → LAN exposure | **closed** (SS-6) |
| 7 | Pasted study module → code in page | accepted, documented (SECURITY.md) |
| 8 | Local process → API | accepted for a single-user desktop tool (no auth boundary exists there) |

**Special scenarios walked.** Malformed/duplicated/gapped orderbook frames (already handled:
sequence tracking + stale marking + re-subscribe, `test_book_integrity.py`); reconnect storms
(bounded exponential backoff, 1→30 s, `bybit_feed.start`); reconnect race with trade timestamps
(warn-once fallback, `test_feed_timestamps.py`); unknown symbols on every demo filler (closed in
§66/§68, `test_demo_symbol_guards.py`); oversize/!http feed URLs (SS-4); public clone run by an
untrusted user (works: no absolute paths, no keys, no telemetry); token exposure via logs
(searched: none — the only credential-shaped strings in logs are the *names* of the settings).

---

## D. Findings table

| ID | Severity | Confidence | Release blocker | Category | Short title | Affected area |
|---|---|---|---|---|---|---|
| SS-1 | High | Confirmed | Yes (fixed) | Security | DNS rebinding reads the local API (config secrets) | `dashboard/app.py` (new guard), `api.py` |
| SS-2 | High | Confirmed | Yes (fixed) | Security | Cross-site POSTs can mutate state on the loopback API | `dashboard/app.py` (new guard) |
| SS-3 | Medium | Confirmed | Yes (fixed) | Security | WebSocket handshake accepted any origin | `dashboard/app.py` `/ws` |
| SS-4 | Medium | Confirmed | Yes (fixed) | Security / availability | User-supplied feed URL: any scheme, unbounded read | `atlas/context.py` |
| SS-5 | High | Confirmed | Yes (fixed) | Market-data integrity | NaN/Infinity/negative values entered analytics | `data/bybit_feed.py`, `data/alpaca_normalize.py` |
| SS-6 | Medium | Confirmed | Yes (fixed) | Security / release | Legacy pipeline default bind `0.0.0.0` | `config/settings.py`, README |
| SS-7 | Medium | Confirmed | No (fixed) | Supply chain | CI actions unpinned, default token permissions | `.github/workflows/ci.yml` |
| SS-8 | Medium | Confirmed | No (open) | Supply chain | No lockfile / SBOM / dependency-scan step | `pyproject.toml`, CI |
| SS-9 | Low | Confirmed | No (fixed) | Privacy / release | Windows username in a published screenshot | `docs/phase4/logs-batch-counters.png` |
| SS-10 | Low | Confirmed | No (fixed) | Security | Client-error endpoint could forge log lines | `desktop/api.py` |
| SS-11 | Low | Confirmed | No (fixed) | Security (D-i-D) | No CSP on the shell | `desktop/ui/index.html` |
| SS-12 | Low | Confirmed | No (fixed) | Market-data integrity | Symbol interpolated into venue URLs unquoted | `atlas/context.py`, `desktop/deribit.py` |
| SS-13 | Low | Confirmed | No (fixed) | Market-data integrity | XML entity class in the RSS parser | `atlas/context.py` |
| SS-14 | Informational | Confirmed | No (fixed) | Release quality | No SECURITY.md / disclosure path | repo root, CONTRIBUTING |

---

## E. Detailed findings

### SS-1 — DNS rebinding reads the local API (including configured credentials)
**Classification:** Security · **Confidence:** Confirmed · **Severity:** High · **Release blocker:** Yes
**Evidence:** `desktop/launcher.py:174` binds `127.0.0.1`; no Host validation existed anywhere
(`grep -rn "TrustedHost\|allow_origins" → 0 hits`). `GET /api/control/config` (`desktop/api.py:58`)
and `/api/control/bootstrap` return the full config — including `alpaca.secret`, `telegram.bot_token`,
`notify.email.password`, DTC password. A rebinding name (attacker-controlled DNS → 127.0.0.1) makes
the attacker's page **same-origin** with that API, and it can read every reply.
**Scenario:** user opens `evil.example`; its script re-resolves the name to 127.0.0.1 after the
browser caches the connection; `fetch('/api/control/config')` answers with the secrets; exfiltrated.
**Impact:** full config disclosure (live brokerage data credentials, alert tokens), full API control
(engine start/stop, exports, layouts) from any web page; reputational damage on a public release.
**Remediation (implemented):** `LocalRequestGuard` middleware (`dashboard/app.py:132-148`) refuses any
request whose `Host` is not `127.0.0.1`/`localhost`/`::1`/(test client) — `local_hostname()` normalises
host:port, IPv6 literals and URLs. **Validation:** `test_request_guard.py` (403 for `Host: evil.example`
on both `/healthz` and the config payload; loopback hosts keep answering); live socket probe made the
same request against a real uvicorn sandbox → `403 forbidden: non-loopback Host` (access log).

### SS-2 — Cross-site POSTs can mutate state on the loopback API (CSRF)
**Classification:** Security · **Confidence:** Confirmed · **Severity:** High · **Release blocker:** Yes
**Evidence:** body-less mutating routes are "simple requests" (no preflight, browser sends them from any
page): `POST /api/control/config/reset`, `/engine/stop`, `/engine/restart`, `/logs/clear`,
`/storage/prune`, `/api/atlas/alerts/clear`, `/replay/stop`, `/profiles/rebuild`, … (route inventory in
`desktop/api.py`); no Origin/Sec-Fetch checks existed.
**Scenario:** a page the user visits fires `fetch('http://127.0.0.1:8080/api/control/config/reset', {method:'POST'})`
with `mode:'no-cors'`; the response is unreadable but the settings are wiped; same trick stops the engine.
**Impact:** denial of service, destructive settings loss, alert rules cleared — remotely triggered while
the user browses; no local compromise needed.
**Remediation (implemented):** same guard: mutating methods must either carry no browser `Origin`
(native clients, curl, the test client) or a loopback one, and must never declare `Sec-Fetch-Site:
cross-site` (`dashboard/app.py:136-146`). **Validation:** `test_request_guard.py` (cross-origin POST → 403,
cross-site POST → 403, same-origin and native POSTs → 200 with the endpoint's own answer); live proof —
a `file://` page in a real Chromium fired the POST; the server answered `403` for
`POST /api/control/logs/clear` and nothing executed.

### SS-3 — WebSocket handshake accepted any origin
**Classification:** Security · **Confidence:** Confirmed · **Severity:** Medium · **Release blocker:** Yes
**Evidence:** `dashboard/app.py` `/ws` called `ws_manager.connect(ws)` unconditionally; websockets are
not subject to CORS, so any page can open `ws://127.0.0.1:PORT/ws` and read the live broadcast
(stats, bias, trade state, ticks).
**Scenario:** a page opens the socket, receives the app's stream, and forwards it; no reply needed.
**Impact:** live market/analysis signal stream leaked to any visited page (no credentials, but a
user-private analytical surface; also a reconnaissance base for localhost probing).
**Remediation (implemented):** `is_trusted_ws_handshake()` (`app.py:120-130`) — Origin, when present,
must be loopback; `Sec-Fetch-Site: cross-site` always fails; the handshake is closed (1008) pre-accept
(`app.py:1313`). Native clients send no Origin and are unaffected. **Validation:** live proof — the
hostile page got `WS-closed:1006` and the server logged `WebSocket /ws 403 / connection rejected`,
while the app's own page stayed `WS live`; `test_request_guard.py` pins both directions.

### SS-4 — User-supplied news-feed URL: any scheme, unbounded read
**Classification:** Security / availability · **Confidence:** Confirmed · **Severity:** Medium · **Release blocker:** Yes
**Evidence:** `atlas/context.py` `_fetch_text()` called `urlopen()` on whatever URL it was given;
the URL arrives as a GET query parameter (`/api/atlas/context/{symbol}?news_url=…`, `atlas/api.py:711-738`)
and from `context.news_url` in the config. `file://` was accepted (a probe read a local file and fed it
to the RSS parser); the body was read with no size ceiling; redirects were followed wherever they led.
**Scenario:** (a) cross-site GET with `news_url=file:///C:/Users/…/secrets.xml` (blind file probe);
(b) `news_url=http://attacker/big` streaming gigabytes into the worker thread (memory pressure/DoS);
(c) redirect to a non-http scheme.
**Impact:** blind SSRF from the user's machine, local-file reads attempted, memory exhaustion; no
response is readable by the attacker cross-origin, which bounds severity.
**Remediation (implemented):** scheme allowlist for every context fetch, http(s)-only redirects
(custom redirect handler), and a 4 MiB read ceiling (`context.py:59-95`); failures degrade to the
UI's "unavailable" as before. **Validation:** `test_context_hardening.py` (file/ftp/data refused
before any read; 300 KiB body read whole under the default cap, refused under a 1 KiB test cap;
loopback HTTP server used, no external network).

### SS-5 — Non-finite venue values entered the analytics path
**Classification:** Market-data integrity · **Confidence:** Confirmed · **Severity:** High · **Release blocker:** Yes
**Evidence:** Python's `json` accepts the bare tokens `NaN`/`Infinity`, and `float(x) <= 0` cannot
catch NaN (all comparisons are False). `bybit_feed._handle_trades` built `Tick(price=float(trade["p"]),
size=float(trade["v"]))` with no validation; `_apply_delta`/snapshot parsing `float()`ed venue levels
unchecked; `alpaca_normalize._num()` returned NaN happily and `normalize_bar`'s `price <= 0` gate let it
through — **executed proof:** a NaN close produced a candle dict on the untouched tree.
**Scenario:** a compromised/misbehaving feed endpoint (or corrupt replay file) sends
`{"p": NaN}` or a negative size; the print enters footprint/delta/CVD, corrupting every downstream
aggregate silently — no exception, no log line.
**Impact:** displayed and stored analytics become wrong without any visible failure — the exact class
the directive calls out ("incorrect results can influence financial decisions").
**Remediation (implemented):** one gate per feed — `_finite()`/`_level()` in `bybit_feed.py:34-58`
(trades, snapshots, deltas; refused values are counted in `book_health()["junk_values"]`, so a bad
socket is visible), and `_num()` is now finite-or-default in `alpaca_normalize.py:85-97` (covers bars,
trades, quotes). **Validation:** `test_feed_value_guards.py` (NaN/Inf/negative/zero price or size
dropped, good print passes, counters exact; book keeps only finite levels; Alpaca NaN close → no
candle, NaN size → 0.0 size, never NaN), plus the existing book-integrity and normalizer suites.

### SS-6 — Legacy pipeline defaulted to binding all interfaces
**Classification:** Security / release · **Confidence:** Confirmed · **Severity:** Medium · **Release blocker:** Yes
**Evidence:** `config/settings.py:178` — `DashboardConfig.host = "0.0.0.0"`; `main.py:357-369` starts
uvicorn with it. The repo's own feasibility notes already called it out
(`docs/DESKTOP_GUI_FEASIBILITY.md:59,149`: "a local trading terminal exposing…"). The desktop shell
binds loopback itself, but `python -m orderflow_system.main` and the `orderflow` console script did not.
**Impact:** the unauthenticated API/UI served to the whole LAN (the new Host guard blocks non-loopback
Host names, but a LAN client can simply send `Host: 127.0.0.1`); an unauthenticated trading terminal
on a shared network.
**Remediation (implemented):** default is `127.0.0.1` with a docstring on how to expose deliberately;
README example updated. **Validation:** `test_request_guard.py::test_the_shipped_dashboard_default_is_loopback`.

### SS-7 — CI: unpinned actions, default token permissions
**Classification:** Supply chain · **Confidence:** Confirmed · **Severity:** Medium · **Release blocker:** No
**Evidence:** `.github/workflows/ci.yml` used `actions/checkout@v4` / `actions/setup-python@v5`
(movable tags) with no `permissions:` block.
**Impact:** a retagged/compromised upstream action or an over-scoped default token could alter CI or
the release it builds.
**Remediation (implemented):** both actions pinned to release-commit SHAs (verified via the GitHub
API: `11bd719…` = v4.2.2, `a26af69…` = v5.6.0) with `persist-credentials: false`, and
`permissions: contents: read`. **Validation:** YAML parsed after the change; workflow logic unchanged
(same steps; the pins are the only behavioural delta).

### SS-8 — No lockfile, no SBOM, no dependency scan in CI (open)
**Classification:** Supply chain · **Confidence:** Confirmed · **Severity:** Medium · **Release blocker:** No
**Evidence:** `pyproject.toml` uses lower-bound ranges; no `uv.lock`/`requirements*.txt`; CI installs
`-e .[dev]` unpinned; no `pip-audit`/`gitleaks`/SBOM step.
**Mitigating facts (executed):** the *shipped* artefact is a frozen build (dependencies are baked in,
not resolved at user install time); a manual `pip-audit` over the build environment's 59 packages
reported **no known vulnerabilities** (2026-09-16); `uvx bandit -ll` reported 0 High findings.
**Remediation (recommended, not applied):** commit a `uv.lock` (the venv is uv-managed; one command),
add a CI step `pip-audit -r <lock>` + optional SBOM artifact (e.g. `uv export` → CycloneDX). Held
back deliberately: a lockfile changes the release diff surface and deserves the owner's eyes; it is
not required to ship v0.1b safely.

### SS-9 — Windows username published in a screenshot
**Classification:** Privacy / release · **Confidence:** Confirmed · **Severity:** Low · **Release blocker:** No
**Evidence:** `docs/phase4/logs-batch-counters.png` displayed the full log path
`C:\Users\Moddy\AppData\Roaming\OrderFlowAnalysisPro\orderflow.log` (verified by reading the image).
**Impact:** minor PII (home directory/username) in a public repo; a reviewer-visible hygiene miss.
**Remediation (implemented):** the path was re-rendered in-place as
`C:\Users\<you>\AppData\Roaming\OrderFlowAnalysisPro\orderflow.log` (same font/size/colour; verified
by re-reading the image; the original file was preserved outside the repo). A vision pass over the
highest-risk screenshots (credential fields, log views, path-displaying headers — 17 of 50) found no
other exposure.

### SS-10 — Client-error endpoint could forge log lines
**Classification:** Security (log integrity) · **Confidence:** Confirmed · **Severity:** Low · **Release blocker:** No
**Evidence:** `desktop/api.py:1666` folded the stack but stored `message`, `source`, `line`, `col` raw;
an embedded CR/LF writes fake entries (with fake timestamps/levels) into the log used for debugging.
**Remediation (implemented):** every field is CR/LF-folded and length-capped (`api.py:1666-1690`).
**Validation:** `test_client_error_log.py` (one report ⇒ one log call, no CR/LF in any argument,
content preserved).

### SS-11 — No Content-Security-Policy on the shell
**Classification:** Security (defence in depth) · **Confidence:** Confirmed · **Severity:** Low · **Release blocker:** No
**Evidence:** `desktop/ui/index.html` had no CSP; an injected script could load/beacon anywhere.
**Remediation (implemented):** a meta CSP (`index.html:12`) that allows only self + loopback WS
targets (`default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; … connect-src 'self'
ws://127.0.0.1:* ws://localhost:*; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action
'self'`). `'unsafe-inline'`/`'unsafe-eval'` are required by the app's own inline boot script and the
Studies engine — stated in a comment; what the policy still guarantees is that an injected script
cannot fetch, beacon or load from any other host. **Validation:** live Chromium run with a
pre-document violation collector: **0 violations, 0 page errors**, 28 view sections, 57 script loads,
WS `WS live`, after exercising 12 views; pinned by
`test_wiring.py::test_the_shell_carries_a_csp_that_forbids_remote_hosts`.

### SS-12 — Symbol interpolated into venue URL templates unquoted
**Classification:** Market-data integrity · **Confidence:** Confirmed · **Severity:** Low · **Release blocker:** No
**Evidence:** `atlas/context.py` built Bybit URLs with `_BYBIT_TICKERS.format(symbol=sym)` from a path
parameter; `desktop/deribit.py:405` did the same for the chain currency. A symbol containing
`&`/`=`/`?` could add or change query parameters (e.g. pivot the venue request to different data).
**Remediation (implemented):** `_venue_symbol()` quotes every symbol (`context.py:62`), and the
Deribit currency is quoted/uppercased (`deribit.py:405`). **Validation:**
`test_context_hardening.py` (hostile symbol leaves no `&=?/`, templates carry exactly the one
intended `&`; captured Deribit URL shows `%26`), normal symbols byte-identical.

### SS-13 — XML entity class in the RSS parser
**Classification:** Market-data integrity / DoS · **Confidence:** Confirmed (mitigated) ·
**Severity:** Low–Medium · **Release blocker:** No
**Evidence:** `ElementTree.fromstring` on feed text (B314 in the bandit run). Modern expat has
amplification limits and ElementTree resolves no external entities, but an *internal* DTD subset is
the classic entity-trick carrier and feeds never need one.
**Remediation (implemented):** documents carrying `<!DOCTYPE … [ … ]>` are refused before parsing
(`context.py:118`); plain/external DOCTYPEs still parse. Combined with the SS-4 4 MiB cap and the
8 s timeout, the XML attack class is closed without adding a dependency to the frozen build.
**Validation:** `test_context_hardening.py` (entity document → `[]`, SYSTEM-DOCTYPE feed → parsed,
ordinary feed → parsed).

### SS-14 — No SECURITY.md / disclosure path
**Classification:** Release quality · **Confidence:** Confirmed · **Severity:** Informational · **Release blocker:** No
**Evidence:** repo root had no security policy; CONTRIBUTING routed all reports to public issues.
**Remediation (implemented):** `SECURITY.md` (private reporting via GitHub advisories, scope, the
loopback/no-execution/no-telemetry design, disclosure expectations), linked from CONTRIBUTING and
README. **Validation:** `test_wiring.py::test_the_repo_ships_a_security_policy`.

---

## F. Secrets, PII and public-GitHub release hygiene

**Confirmed exposure: none.** What was searched and how:

- **Tracked files:** regex sweep for `AKIA…`, `sk-…`, `ghp_…`, `xox[baprs]-…`, PEM private keys,
  plus `secret|token|password|key_id` context reads — zero real values (the only hits are config
  *field names* and documentation examples).
- **Git history:** `git log --all --diff-filter=A --name-only` filtered for `.env|secret|credential|
  .pem|.p12|token|password` — nothing was ever added.
- **Working tree:** `git status --porcelain --ignored` shows `orderflow_data.db*`, `orderflow.log`,
  `dist/`, `build/`, `.venv/`, egg-info and caches are all ignored; `git check-ignore` confirms.
- **Logs:** the live log contains only informational lines; credential-shaped strings appear only as
  the names of settings to configure (`"Set TELEGRAM bot_token and chat_id…"`).
- **Screenshots (sample of 17 of 50, chosen for credential fields / log views / path-displaying
  headers, read with vision):** one username exposure found and redacted (SS-9); every credential
  field seen was empty or explicitly masked (`•••• saved`, `PK…`, `(saved — type to replace)`).
- **Build output:** the frozen tree contains no keys (config lives in the user profile, not the dist);
  `pip-audit` over the build environment: no known vulnerabilities.

**Suspected exposure: none.** **Not verified:** exhaustive OCR of all 50 screenshots (see L).

**Deliberate design that a reviewer will notice (with rationale — not defects):**

1. **`GET /api/control/config` returns the stored secrets.** The settings UI and the wizard round-trip
   these values (e.g. `ui.js:1144` fills the Telegram token field from the config; saving posts the
   field back), so masking the API would silently blank a saved token on the next unrelated save.
   The correct mitigation for a single-user local app is boundary control, which is exactly SS-1/SS-2:
   a browser from another origin can no longer read the API or fire mutating calls. Documented in
   `SECURITY.md`.
2. **No authentication.** Anyone who can reach 127.0.0.1 as the user can call the API — the same
   privilege level as reading the config file directly. Auth would add ceremony, not a boundary.
3. **Studies engine (`new Function`).** A deliberate plugin surface: users paste JS modules that run
   in their own page, like the reference platform's study editor; documented in `SECURITY.md`.
4. **User-configured outbound targets** (alert webhook, ntfy server, DTC/Bookmap host):
   the feature *is* "send my alerts to my endpoint"; defaults are loopback or the public ntfy service.

**Required checks before publish (per directive):** revocation list — *not applicable, no exposure*;
history cleanup — *not applicable*; `.gitignore` — verified; source-map publication — *none exist*;
logging — verified clean; release-artifact content — verified (no config/DB in the dist; 494 entries,
checked during the §69 installer pass and again in §66/§67/§68 smokes).

---

## G. Market-data and analytical-integrity assessment

**Verified by execution (this pass):** venue values are now validated finite/positive before they can
enter any aggregate (SS-5, pinned); the Alpaca normalisers cannot emit NaN (pinned); the analytics
goldens (40 cases / 2,196 numeric leaves) are byte-identical after every change in this sweep — no
calculation moved; the config golden (31 factories / 18 crypto majors / 49 instruments) is unchanged.

**Verified in previous rounds and re-run here (still green):** orderbook sequence gaps
(`u` monotonicity, duplicate/late deltas dropped, stale marking + re-subscribe — `test_book_integrity.py`);
trade timestamps with warn-once fallback (`test_feed_timestamps.py`); displacement unit = true tick
steps (`test_displacement_ticks.py`); absorption keying on tick-rounded prices (`test_absorption_keying.py`);
value-area invariants at extremes (`test_value_area_edges.py`); candle footprint round trip
(`test_candle_roundtrip.py`); demo fillers silent for unknown symbols (`test_demo_symbol_guards.py`).

**Conditions under which displayed data could still mislead (unchanged, disclosed):** feed outage or
vendor gap (panels degrade to explicit "warming/unavailable" states with freshness chips); demo mode
(the UI is explicit: source `demo`, and an engine-less unknown symbol gets nothing); indicator/stop-run
trackers are labelled INFERRED in-view (Bybit publishes no market-by-order feed); Bybit's `u`-as-timestamp
normalisation is centralised (`atlas/clock.py`). **Execution-capable code: none** — the Alpaca client is
read-only (account/positions/order-*history* GETs, `desktop/alpaca.py:110-152`); a full-tree search for
order-placement verbs returns nothing; the only outbound POSTs are the user's own notification channels
(ntfy/webhook/e-mail/Telegram). This is stated in `SECURITY.md` as a scope promise.

---

## H. Performance and stability assessment

**Structures already in place and re-verified:** bounded per-client WS queues (`QUEUE_MAX = 256`, trim
policies per channel class, drop accounting — `dashboard/websocket_manager.py`; pinned by
`test_websocket_backpressure.py`, including the 3.11 cancellation fix); retention pruning with WAL
checkpointing and incremental autovacuum (`data/database.py`, `test_retention.py`); heat payload caps
(`max_columns` 900, rows ≤ 400, drawn cells ~6 k); frame-yield measurement at 4K from §51 (max warm
frame 12.4 ms) and the heat-pass measurement from §58/§59 (0.6–1.7 ms against a 6.94 ms budget at
2560×1440@144 Hz) — unchanged by this sweep.

**New in this sweep:** every user-reachable fetch is now bounded — 4 MiB read ceiling + 8 s timeout +
http(s) redirect confinement on the context fetchers (SS-4); news feed parsing refuses entity-carrying
XML (SS-13). Network reads previously had no ceiling at all on that path.

**Recommended acceptance criteria (unchanged from measured baselines; for CI soak work):**
WS queue ≤ 256 with drop counts reported; event-processing stays off the event loop (all fetchers use
`asyncio.to_thread`); memory growth over a 24 h replay < 50 MB with retention on; warm frame < 13 ms
at 2560×1440; heat pass < 3.5 ms on the owner's hardware; reconnect backoff capped at 30 s with no
more than one snapshot fetch per gap.

---

## I. Remediation roadmap

**P0 — must fix before any public release (all DONE in this pass, each with a pin):**
1. SS-1 + SS-2 loopback request guard (`dashboard/app.py`) — the single highest-leverage change.
2. SS-3 WebSocket handshake check (same guard family).
3. SS-5 feed value containment (`bybit_feed`, `alpaca_normalize`).
4. SS-4 feed-URL scheme/size/redirect confinement (`atlas/context.py`).
5. SS-6 loopback default for the standalone pipeline.
*Ordering rationale:* guard first (it protects every other endpoint, including the config payload and
the new SECURITY.md claims), then the data-integrity gates, then the release-hygiene pieces — each
landed alone on a green suite before the next.

**P1 — before broader adoption (DONE / one open):**
6. SS-7 CI pinning + least privilege (done). 7. SS-14 SECURITY.md (done).
8. **SS-8 open:** commit `uv.lock`; add `pip-audit` + (optionally) a CycloneDX SBOM artifact to CI.
   *Safe for a patch release; touches only the build pipeline.*
9. Optional: extend the finite-value gate to `mt5_feed` (needs a broker fixture to pin; MT5 is an
   optional dependency not exercised in CI — deliberately left until it can be tested).

**P2 — reliability/maintainability:** soak-test harness (24 h replay with memory watermark assertion);
a CI job that runs the two goldens plus selftests on 3.12 too (already in matrix); containerised
fuzz fixtures for feed frames.

**P3 — backlog:** re-shoot the legacy-branded screenshots (some still show the pre-P62 window title
"OrderFlow Analysis Pro"); UPX evaluation stays deferred per §63 (AV false-positive trade-off).

---

## J. Test and verification plan (executed unless marked)

| Check | Command / method | Result |
|---|---|---|
| Unit/integration suite | `.venv/Scripts/python.exe -m pytest orderflow_system -q` | **649 passed / 2 skipped** (was 629; +20 pins) |
| UI reference audit | `scripts/audit_ui_refs.py` | AUDIT CLEAN |
| Lint | `uvx ruff check orderflow_system scripts` | All checks passed |
| Analytics golden | `scripts/regen_analytics_golden.py` | OK — 40 cases, 2196 leaves, max diff 0.000e+00 |
| Config golden | `scripts/regen_config_golden.py` | matches (31/18/49) |
| UI selftests | 19 × `node *.selftest.js` | 19 pass, 0 failed |
| New security pins | `test_request_guard.py`, `test_context_hardening.py`, `test_feed_value_guards.py`, `test_client_error_log.py`, +2 in `test_wiring.py` | all green; each was run red against the untouched tree first |
| Dependency audit | `uvx pip-audit` over the 59-package build env | No known vulnerabilities |
| Static security lint | `uvx bandit -r orderflow_system -ll` | 0 High; 13 Medium — every one reviewed (9× B310 fixed-URL `urlopen`, 3 of which are the now-hardened context fetchers; B608 = fixed table-name `COUNT(*)`; B104 fixed by SS-6) |
| Live sandbox (source) | headless on 8092, real Chromium via CDP | guard 403s on the wire; CSP: 0 violations / 0 page errors across 12 views; WS live; hostile `file://` page refused (POST 403 in access log, WS 1006) |
| Frozen build | rebuilt after the last source edit; headless smoke on 8099 | see §"Build" below |
| Fuzz/load/soak | not run in this pass | listed under P2; fixtures exist for feed frames |

**Frozen build (rebuilt from the hardened source):** `dist/ModFlowOrderFlowAnalysisSuite/`
(PyInstaller onedir, numpy excluded) + re-zipped `dist/ModFlowOrderFlowAnalysisSuite-win64.zip`
(494 entries, 25.9 MB) + rebuilt installer `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`
(28,119,760 bytes; sha256 `E71C53C1BE30393ECD9E86187E759C8E9AD8166C0CA53B451618347525F65DD7`) —
exe smoke receipts and the full journey record in `docs/SESSION_HANDOFF.md` §69/§70.

---

## K. Final release checklist (v0.1b)

- [x] P0 security findings fixed and pinned (SS-1…SS-6)
- [x] Full gates green after every change; suite 649/2
- [x] No secrets in tree/history/logs; `.gitignore` verified
- [x] Disclosure path published (SECURITY.md), linked from README/CONTRIBUTING
- [x] CI least-privilege + actions SHA-pinned
- [x] CSP live-verified in a real browser
- [x] Screenshot PII redacted (SS-9)
- [x] Frozen dist + zip rebuilt from hardened source and smoked
- [x] Installer rebuilt from the same dist and install/uninstall-verified
- [ ] Owner release sequence: commit → create GitHub repo → push → tag `v0.1.0-beta` → attach
      `ModFlowOrderFlowAnalysisSuite-win64.zip` + `ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`
- [ ] (P1, recommended) `uv.lock` + `pip-audit`/SBOM CI step (SS-8)
- [ ] (P3) re-shoot legacy-branded screenshots when convenient

---

## L. Audit limitations

- **What was not inspected:** the vendored `lightweight-charts.js` bundle (read as a dependency, not
  audited line-by-line — report upstream); the InstallShield-generated `.ism` internals (the wrapper
  script and journey were verified in §69); PyInstaller bootloader internals (dependency of the build
  tool, same for every frozen app).
- **What was not runnable here:** live MetaTrader 5 sessions (terminal not present in the sandbox —
  the MT5 path is exercised only where a fixture exists; hence the deliberate OS-level gate above);
  Alpaca live account calls (no credentials used — by directive, no live brokerage interaction;
  the client is covered by stub-transport tests); Bybit live reconnect storms (the handlers are unit-
  probed; sustained-load behaviour is the P2 soak work).
- **Environment access needed for full confidence:** a machine with MT5 installed, and a soak-test
  window against live Bybit during a busy session.
- **Independently validate:** the two browser-native exploits (SS-1/SS-2) on a machine with a
  different browser family; the CSP under the actual WebView2 runtime (verified here in Chromium —
  same engine, different host); the installer journey on a clean VM.
- **Screenshots:** 17 of 50 were read with vision (credential fields, log views, headers); the rest
  are the same panels without those surfaces. A pre-release re-shoot is recommended anyway (P3).
- **No claim of completeness.** This sweep found and closed the classes it could reach with evidence;
  it does not certify the absence of other issues, and it is not a compliance attestation (no
  SLSA/NIST/OWASP certification is claimed — only alignment with standard practice where stated).

---

*Sweep executed against HEAD `fa202d6` + the working tree; every fix is uncommitted, isolated and
reversible by reverting its own diff. Nothing was sent to any live venue or brokerage account.*
