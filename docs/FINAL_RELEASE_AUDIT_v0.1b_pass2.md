# Final Release Audit — v0.1b, second pass (the partial-build integration)

**Directive:** the owner's Desktop `final audit prompt.txt` ("FINAL RELEASE AUDIT — v0.1b OPEN-SOURCE
SHIP GATE"), run again on a tree that has since gained a partial feature build: four new analytics
modules, three new data feeds, four new views. The brief's own line one: *"audit and survey for any
changes made and partial build of anything … formulate and implement a plan and non program braking
fix and continuation of the concepts … remember DONT BREAK FUNCTIONALITY. ONLY ENHANCE."*

**Baseline.** Branch `master`, HEAD **`797eea0`**, worktree **dirty** (this pass rides it — nothing
committed; the standing rule is that nothing is committed or pushed without the owner's word).
The pass touched **26 paths** — 10 new files, 15 changed, 1 removed (§6). Prior reports this one builds on, not repeats:
`docs/FINAL_RELEASE_AUDIT_v0.1b.md` (§135, report-only) and the §136 execution block in
`docs/SESSION_HANDOFF.md` (the "go for all fixes" pass).

**Interpreter / runners.** `.venv/Scripts/python.exe` (the project venv) — the agent venv has no
pytest; `node` v22 for the JS gates. `ruff` is **not installed** in this environment (§7, "Not
executed").

---

# 1. Release Decision

## SHIP ONLY AFTER REQUIRED FIXES

- **No P0 and no P1 defect remains on this content.** The one P1 this pass found — a whole feature
  family that existed as files but was reachable from nothing — is fixed and verified live.
- The required items are **release mechanics, not product defects**: the content is uncommitted
  (CI has never seen it), the distributables predate this build, and the new panels only exist in
  source until the next rebuild.
- Every gate the repository defines for itself is green on this content: **1,899 passed / 3 skipped
  / 0 failed**, `audit_ui_refs.py` **AUDIT CLEAN** (169 routes, 133 modules), **45/45** node
  selftests, goldens exact.
- Four new panels now answer with **real venue data** through real routes (GEX, IV surface, option
  flow off Deribit's public tape; the market read off the running engine), each with a
  server-authored refusal on the paths that cannot work — no fabricated numbers anywhere.
- The new panels are **documented where the app looks for documentation**: nav items, four Help
  topics wired into the coverage contract (`VIEWS`), and the README/MENU_RECONCILIATION counts and
  rows re-derived in one pass.
- The two repository guards that police UI resources (`test_listener_balance.py`,
  `test_timer_guards.py`) **were satisfied by integrating**, not by weakening: each new poller is
  registered with `OFAPPause` so `P` clears it, and each panel's page-lifetime listeners are frozen
  with their count and reason.
- **Required before a public release:** (1) the commit/push pass on the owner's word — the delta's
  first CI run; (2) a **rebuild** so `dist`/zip/SBOM/Setup carry §137; (3) the README badge
  re-check after the rebuild (`tests` = 1,899 on this content); (4) the owner's physical
  multi-monitor pass, unchanged from §135.
- **Honest limits** (unchanged shape): one physical display was available; no MT5 / NinjaTrader /
  Alpaca account was exercised; equity option chains were exercised only on their **no-key refusal
  path**; no long-duration soak was run (bounded stores + the §135 memory audit stand in).
- Nothing in this pass changed an existing workflow, route path, config key, saved file or visual
  default: the changes are additive routes, four new panels, and pins.

---

# 2. Executive Risk Summary

| Priority | Finding | Impact | Confidence | Ship Requirement |
|---|---|---|---|---|
| **P1** | FG2-01 — the four analytics modules were unreachable (no routes, no panels, no nav/help wiring) | the advertised feature family was dead weight; a user could see four empty views and no data | Confirmed | **Fixed** (§6 C1–C4); verified live |
| **P2** | FG2-02 — `atlas/api_new_endpoints.py` was dead code nothing imported | a false impression of a wired feature; two competing implementations of one API surface | Confirmed | **Fixed** (§6 C1, removed after its concepts landed in `options_api.py`) |
| **P2** | FG2-03 — duplicate element id `ofBanner` (order-flow view and option-flow view each declared it) | the first-DOM-match rule makes the second view's banner text land in the wrong view | Confirmed | **Fixed** (§6 C3, the new panel's id is `ofvBanner`) |
| **P2** | FG2-04 — `market_read.py` built radar levels from **placeholder prices** (`spot * (1+0.001·n)`) when the tracker had real rows | a fabricated price in an analytical read is worse than a missing one | Confirmed | **Fixed** (§6 C5); placeholders remain only as a documented fallback for callers with no tracker |
| **P2** | FG2-05 — NaN could cross the JSON boundary into the read's dataclasses | one NaN turns a whole read into `null`-poisoned JSON | High | **Fixed** (§6 C5, `_num_or_none`) |
| **P3** | FG2-06 — the GEX/volatility banner's chain note read "(0 read, 0 failed)" whenever the 3 s ticker cache answered | reads like a failure on a healthy chain | Confirmed | **Fixed** (§6 C6) |
| **P3** | FG2-07 — README/CONTRIBUTING claims were stale again after the partial build (module/selftest counts, badges, five inventory rows) | the release's own numbers were untrue | Confirmed | **Fixed** (§6 C7, re-derived in one pass) |
| **P3** | FG2-08 — the new panels' polling and listeners were outside the repository's own resource guards | the guards failed; a reviewer could not tell intent from accident | Confirmed | **Fixed** (§6 C8, integrated + frozen with reasons) |
| P3 | Carried from §135/§136 and still true: FG-04 content uncommitted; distributables lag; owner's multi-monitor pass | release mechanics | Confirmed | Required before release (§8) |

---

# 3. Verified Architecture Map (delta since §135)

- **Entry:** `orderflow_system/desktop/launcher.py :: build_app(port)` builds the app the UI talks
  to: `dashboard.app.app` + `desktop.api.router` (`/api/control/*`) + `atlas.api.router`
  (`/api/atlas/*`) + **`atlas.options_api.router`** (`/api/options/*`, new this pass) +
  `desktop.edgar.router` (fundamentals). Measured from that function: **189 OpenAPI operations**,
  172 paths, **76 under `/api/`**, plus `/ws` → the README's API badge is now **190**.
- **New REST surface (this pass):**
  - `GET /api/options/gex/{symbol}?source=deribit|tradier|marketdata[&spot=&width=&wall_quantile=]`
  - `GET /api/options/volatility/{symbol}?source=…[&expiry=&width=]`
  - `GET /api/options/flow/{symbol}?source=deribit&count=&window_ms=`
  - `GET /api/atlas/market-read/{symbol}` (payload completed; the route existed)
  Each returns `{ok:true, …}` or `{ok:false, error:"<sentence naming what is missing>"}` — **every
  refusal is a sentence a user can act on**, and none of them is a stack trace.
- **Chain sources:** `desktop/deribit.py` (public, keyless; per-instrument tickers; greeks +
  volume) and `data/tradier_feed.py` / `data/marketdata_feed.py` (keyed OPRA chains). The GEX path
  needs gammas: Deribit and Market Data carry them, **Tradier's OPRA chain does not** and the
  route says so instead of returning a map of zeros.
- **Print source for option flow:** `deribit` only. The classification lives in
  `atlas/option_flow.py` (pinned by `test_option_flow.py`); the equity venues carry quotes, not
  prints, and the route names that.
- **UI:** `desktop/ui/{gex,volatility,option-flow,market-read}.js` (new), each with a
  `*.selftest.js`, a nav item, a view section, a Help topic and a `VIEWS` entry. Polling: 20 s for
  the three chain panels, 5 s for the market read — each registered with `OFAPPause` and each
  additionally gated on `document.hidden`, `OFAP_PAUSED` and `OFAPINTENT.anyHeld()`.
- **State ownership (the new modules):** one module-scoped `state` object per panel (last payload,
  busy flag, last-fetch timestamp); no globals, no cross-panel state, nothing written to
  localStorage; every payload is discarded wholesale on the next refresh.
- **Data flow for the new panels:** HTTP poll → `window.api()` → pure formatter → DOM write. No
  bus subscription, no shared cache touch, no engine coupling except the market read, which reads
  the hub's own analyzer state server-side.

---

# 4. Full Findings Register

## [FG2-01] [P1] The partial build's four analytics modules were unreachable from the product

- **Confidence:** Confirmed
- **Audit domain:** Architecture / integration (directive domains B, F)
- **Affected files and symbols:** `orderflow_system/atlas/{gex,volatility,market_read,option_flow}.py`
  (engines, ~4,000 lines total), `atlas/api_new_endpoints.py` (never imported), `desktop/ui/index.html`
  (four view sections present, referenced by nothing), `desktop/ui/help-data.js` (no topics), the
  launcher's router mounts.
- **Preconditions and trigger:** open any of the four views in the shell.
- **Expected behaviour:** the view fills from a route the module claims.
- **Observed / code-proven behaviour:** no route served the engines (measured: a reconstructed app
  exposed **0** `/api/options/*` paths); `grep '<script' index.html` matched no module for these
  views (exit 1); the Help coverage contract had no entry, so `test_help.py` had nothing to check.
- **Evidence:** route enumeration before/after (`0 → 3` options paths, `+ /api/atlas/market-read`
  payload), the audit's own two counts, and the live probes in §7.
- **Root cause:** the engines and views were written as separate deliverables; nothing owned the
  seam between them (no route, no module, no nav, no help topic).
- **Lifecycle analysis:** n/a (static wiring), but the absence also meant the two repository
  resource guards had nothing to police for these panels.
- **Impact:** a user opening the four views saw empty panels; a reviewer saw a feature that did
  not exist. For an open-source v0.1b whose README sells these reads, that is the difference
  between a feature and a claim.
- **Minimal safe remediation:** additive only — mount a new options router, complete the
  market-read payload, add four modules + nav items + help topics + `VIEWS` entries + script tags.
- **Compatibility/regression risk:** low; no existing route, id or file was renamed except the one
  id collision of FG2-03.
- **Required tests/measurements:** the repo's own gates plus a live probe per route (done).
- **Rollback:** delete the four module files, revert the launcher mount line, the four nav items,
  the script tags and the help entries.
- **Dependency/order:** first — everything else in §6 builds on it.
- **Ship status:** **Fixed** on this content.

## [FG2-02] [P2] `atlas/api_new_endpoints.py` was dead code

- **Confidence:** Confirmed (nothing in the tree imports it; `grep -r` over `*.py`/`*.js`)
- **Audit domain:** Build/operational quality (F), dead code
- **Affected files:** `orderflow_system/atlas/api_new_endpoints.py` (16,914 bytes).
- **Expected behaviour:** a module that defines REST endpoints is either mounted or is a stub with
  a named owner.
- **Observed:** never imported by the launcher, the desktop api, or any test.
- **Root cause:** a first attempt at the same feature set that was overtaken by the engines.
- **Impact:** two competing implementations of one API surface would diverge; a reader cannot tell
  which is authoritative.
- **Minimal safe remediation:** fold its concepts into one module (`atlas/options_api.py`) and
  remove the orphan.
- **Risk:** low — the removal is verified by the gates (audit: 0 missing references; 1,899 tests
  green).
- **Ship status:** **Fixed** (removed; concepts live in `options_api.py`).

## [FG2-03] [P2] Duplicate element id `ofBanner` across two views

- **Confidence:** Confirmed
- **Audit domain:** UI/state correctness (B)
- **Affected files:** `desktop/ui/index.html` — the order-flow view's banner and the new
  option-flow view's banner both declared `id="ofBanner"`.
- **Trigger:** any code path that writes banner text via `getElementById('ofBanner')` for either
  view.
- **Expected:** view-local ids are unique in the document (the shell keeps a duplicate-id check).
- **Observed:** first-match-wins; the second view's messages would land in the first view's node.
- **Root cause:** the four new sections were added by hand alongside existing markup.
- **Impact:** a mis-delivered status sentence — a user reading the wrong panel's refusal.
- **Minimal safe remediation:** rename the **new** id to `ofvBanner` (the pre-existing id keeps its
  consumers) and point the new module at it.
- **Risk:** minimal; verified by the audit's duplicate-id check (now 0) and the wiring tests.
- **Ship status:** **Fixed**.

## [FG2-04] [P2] The market read could report radar levels that carry fabricated prices

- **Confidence:** Confirmed (code-proven)
- **Audit domain:** Data correctness (B/C)
- **Affected files/symbols:** `orderflow_system/atlas/market_read.py` — the radar section of
  `RadarSnapshot` and the level builder (`add(spot * (1.0 + 0.001 * (len(levels)+1)), "radar_armed",
  …)`).
- **Preconditions:** a read taken while the tracker had armed/approaching levels whose prices were
  not being carried through.
- **Expected:** a level's price is the tracker's price.
- **Observed:** the read emitted a price derived from spot and the level's ordinal — a number no
  venue ever printed.
- **Root cause:** the snapshot wanted counts (`armed_levels`, `approaching_levels`) and the level
  list was completed from those counts instead of from the rows.
- **Impact:** an analytical read inventing price levels is the worst failure mode this app has —
  it is the one thing a trader would act on.
- **Minimal safe remediation:** prefer the tracker's real rows (which carry actual prices); keep the
  count-anchored placeholders only for callers that have no tracker data, documented as such.
- **Required tests:** `test_market_read.py` (green) — plus the live refusal path when no engine is
  attached (probe, §7).
- **Ship status:** **Fixed**.

## [FG2-05] [P2] NaN could cross the JSON boundary into the read's dataclasses

- **Confidence:** High (code-proven)
- **Affected files:** `atlas/api.py` (the market-read payload assembly).
- **Trigger:** an analyzer producing `float('nan')` for a score or level (empty windows do this in
  pandas-derived code).
- **Expected:** `None` — the read's dataclasses take `None`, and JSON has no NaN.
- **Observed (before the fix):** a raw `float('nan')` could be handed to a dataclass field that
  serialises into the response.
- **Root cause:** one conversion path that trusted its input to be finite.
- **Minimal safe remediation:** `_num_or_none(value)` at the boundary ("a finite float or None").
- **Impact:** one NaN makes a response unparseable in strict JSON clients (`json.loads` accepts
  NaN by extension; most other parsers do not).
- **Ship status:** **Fixed**.

## [FG2-06] [P3] The chain note read "(0 read, 0 failed)" on a healthy cached chain

- **Confidence:** Confirmed
- **Affected files:** `desktop/desktop/deribit.py :: chain()` (note assembly).
- **Observed:** `tickers()` returns the count it **fetched**; a warm 3 s cache answers the whole
  window with 0 fetches, so the note read like an empty chain.
- **Impact:** a misleading status line in the GEX/volatility banner (the panels print the note).
- **Remediation:** say it — "(0 read, 0 failed — all of them from the 3 s ticker cache)".
- **Ship status:** **Fixed**.

## [FG2-07] [P3] README / CONTRIBUTING claims were stale again after the partial build

- **Confidence:** Confirmed (measured)
- **Affected files:** `README.md` (badges, tree figure, File Inventory table, module/selftest counts),
  `CONTRIBUTING.md` (gate baselines).
- **Observed vs re-derived:** code badge ~102k → **~108k**; API 186 → **190** (189 operations + `/ws`,
  measured from `build_app(8097)`); tests 1,753 → **1,899**; modules 126/41 → **130/45**; tree figure
  `~48,502L across 126 files` → **~50,285L across 133 files**; inventory rows Config 842→892,
  Data 17/7,372→**20/8,407**, Atlas 30/9,672→**35/11,673**, Desktop app 20,091→**20,188**,
  Desktop UI 136/52,157→**143/54,108**, Orchestrator 1,350→**1,387**, Total 258/45,199/57,213/102,412 →
  **273/48,419/59,164/107,583**, suite 160/30,274 → **167/31,907**.
- **Method:** the rule set was validated against the rows that could not have changed — Analytics
  (17/3,206 exact), Legacy dashboard (15/7,722 exact), Desktop app file count (39 exact) — and only
  then applied to the rest. One pass, one swap.
- **Ship status:** **Fixed**.

## [FG2-08] [P3] The new panels sat outside the repository's resource guards

- **Confidence:** Confirmed (the guards failed, then passed)
- **Affected files:** `test_listener_balance.py`, `test_timer_guards.py`.
- **Observed:** `4 unpaired listener(s) … not on the allow-list` (gex 5/0, volatility 5/0,
  option-flow 5/0, market-read 3/0) and `unguarded setInterval site(s)` ×4.
- **Root cause:** new page-lifetime panels without their declarations.
- **Remediation (integration, not exemption):** each poller now hands its timer to
  `OFAPPause.register(id, restart)` — `P` clears it and resume rebuilds it, the suite's own rule —
  and the four modules are frozen in the listener allow-list **with their counts and reasons**;
  the timer counts are frozen too, so a *new* unguarded timer in these modules still fails.
- **Ship status:** **Fixed**.

---

# 5. No-Issue Coverage

| Area | Evidence reviewed | Conclusion | Remaining uncertainty |
|---|---|---|---|
| JS → route integrity | `scripts/audit_ui_refs.py` (AUDIT CLEAN, 169 routes, 160 ids used, 0 missing, 0 duplicate ids, 133 modules parse) | no broken call or dead element reference | none for the checked class |
| View coverage contract | `test_wiring.py` (nav item + a script that claims each view), `test_help.py` (every view has a topic), `test_guide.py`, `test_menus_pass.py` — 213 passed with the new-module tests | the four new views are wired and documented where the app looks | none |
| Panel logic (pure halves) | 4 new selftests, 40 checks; the whole suite 45/45 | formatters, ordering, refusal text and the honesty rules are pinned | DOM-flow behaviour rests on the audit + live probes, as the repo intends |
| Live route behaviour | probe: real Deribit chain (36 strikes, forward-anchored window), IV surface (ATM 20.97, 25Δ 19.09/28.38, skew −9.29pp), option flow (33 prints, 2 blocks, 0 sweeps) | the panels answer with venue data | venue availability at the user's moment |
| Refusal paths | probe: no-key Tradier/Market Data, quote-venue flow, engine-less market read | four distinct, actionable sentences; no traceback, HTTP 200 + `ok:false` | none |
| Golden/analytics pins | `run of the full suite` incl. the golden tests | exact | none |
| Config plumbing | `config_store.py` sanitisers for the three new feed blocks + `engine.apply_settings` writing them into `settings.*` | a hand-edited config cannot put a non-string in a header; chain width clamped 1–20 | the source-list whitelist mentions feeds no UI sends yet (benign, forward-looking) |

---

# 6. Remediation Plan in Safe Merge Order (as executed)

| Change | Findings | Files | Why safe here | Validation after the change | Rollback |
|---|---|---|---|---|---|
| **C1** — one options REST module | FG2-01, FG2-02 | `atlas/options_api.py` (new), `launcher.py` (mount), `deribit.py` (note), `gex.py`/`volatility.py` (rows carry delta, OI, volume, expiry) | additive; no existing route touched | route enumeration + live probe | un-mount the router; delete the file |
| **C2** — the market read's payload completed | FG2-01, FG2-04, FG2-05 | `atlas/api.py`, `atlas/market_read.py` | route existed; the callers then get every field the read computes | `test_market_read.py` + probe (engine-less refusal) | revert the two functions |
| **C3** — four UI panels + shell wiring | FG2-01, FG2-03 | `ui/{gex,volatility,option-flow,market-read}.js` (new), `index.html` (nav, sections, script tags, banner id, table headers), `help-data.js` (4 topics + `VIEWS`) | additive; one id renamed (the new one) | audit + wiring/help tests + selftests | delete the modules, revert the shell hunks |
| **C4** — documentation truth | FG2-07 | `README.md`, `CONTRIBUTING.md`, `docs/MENU_RECONCILIATION.md` | arithmetic only, one pass | the re-derivation counts in §4 FG2-07 | revert the hunks |
| **C5** — resources inside the guards | FG2-08 | the four panels + `test_listener_balance.py` + `test_timer_guards.py` | the guards get *stricter*, not looser | both guard tests green; 45/45 selftests | revert the registration blocks and the allow-list entries |
| **C6** — the cached-chain note | FG2-06 | `desktop/deribit.py` | string only | `test_deribit.py` (suite) | revert the line |

**Process note (mine, not the repo's).** While wiring the four Help topics I ran a repair script
with a mis-chosen anchor and it spliced ~1.3 KB of `help-data.js` into itself. It was caught by the
patch tool's syntax check, diagnosed with a HEAD↔disk opcode diff, and cut; the file now differs
from HEAD only by the other LLM's legitimate topic edits plus the four new topics and `VIEWS`
entries (87 topics, 8 groups, 37 views, no duplicate ids, `node --check` clean). Recorded here
because the file's diff is large and a reviewer deserves to know why — and because the lesson is
the same one the repo already documents: **anchor on structure you have verified, then read back.**

---

# 7. Validation Matrix

| Validation | Command or scenario | Expected | Actual | Status |
|---|---|---|---|---|
| Full suite (project venv) | `.venv/Scripts/python.exe -m pytest orderflow_system -q -p no:randomly` | green | **1,899 passed, 3 skipped, 0 failed** in 68.6 s | Pass |
| Targeted gates | the four new-module tests + feed tests + wiring/help/guide/menus | green | **213 passed** in 1.6 s | Pass |
| Resource guards | `test_listener_balance.py`, `test_timer_guards.py` | green | **4 passed** (was 2 failed) | Pass |
| UI audit | `.venv/Scripts/python.exe scripts/audit_ui_refs.py` | AUDIT CLEAN | **AUDIT CLEAN** — 169 routes · 160 ids · 0 missing · 0 duplicate ids · 133 modules parse | Pass |
| Node selftests | `for f in …/*.selftest.js; do node "$f"; done` | 45/45 | **45 passed, 0 failed** (4 of them new) | Pass |
| Module syntax | `node --check` on the four new modules and on `help-data.js` | clean | clean | Pass |
| Live: GEX | `GET /api/options/gex/BTCUSDT?source=deribit` via TestClient | real chain | 36 strikes · forward-anchored · walls + zero-gamma + DEX/VEX/theta · every row carries volume · vanna/charm flagged `carried:false` | Pass |
| Live: volatility | `GET /api/options/volatility/BTCUSDT?source=deribit` | real surface | ATM 20.97% · 25Δ put 19.09 / call 28.38 · skew −9.29pp · `n_expiries 1` · smile rows carry delta/OI/expiry | Pass |
| Live: option flow | `GET /api/options/flow/BTCUSDT?source=deribit&count=100` | real prints | 33 trades read, 2 blocks with venue reasons, 0 sweeps in the window | Pass |
| Live: refusals | Tradier/Market Data without keys; flow off a quote venue; market read with no engine | actionable sentences | four distinct sentences, `ok:false`, HTTP 200, no traceback | Pass |
| API surface | `build_app(8097).openapi()` | — | 189 operations · 172 paths · 76 under `/api/` · badge 190 | Pass |
| README claims | re-derivation script (rules validated on unchanged rows) | consistent | all rows/badges updated in one pass | Pass |
| Lint baseline | `ruff check orderflow_system scripts` | clean | **Not executed** — ruff is not installed in this environment (neither on PATH nor in `.venv`); CI owns it on the delta's first run | Not executed |
| Frozen-artifact probes (`build_exe` smoke, installer journey, frozen guard probe) | required a rebuild | — | **Not executed** — the distributables predate this build; they are the next pass's first step | Not executed |
| Multi-monitor pass | physical | — | **Not executed** — one display on this host; the owner's own pass stands | Not executed |
| Long soak | bounded stores stand in (owner's standing instruction) | — | Not executed by design | Not executed |

---

# 8. Release Checklist

- [x] **Working tree reviewed** — 125 dirty paths at pass start; this pass touched 26 paths (10 new, 15 changed, 1 removed); nothing committed.
- [ ] **Version/tag/package metadata** — `pyproject` 0.1.0 and the README's Release identity line agree; `git tag -l` is still empty (the tag is the publish pass's act).
- [x] **License present** — unchanged.
- [x] **README accurate** — badges, tree figure, inventory, module counts and the four new panels re-derived on this content.
- [x] **No secrets committed** — nothing of the kind appears in the diff; the new code reads keys from config only, and the refusal sentences never echo a key.
- [ ] **Lockfile present and consistent** — unchanged since §135 (nothing added to the dependency graph this pass).
- [ ] **Clean installation works** — not re-run this pass (unchanged dependency set).
- [x] **Tests / audit / selftests pass** — 1,899 / AUDIT CLEAN / 45 green.
- [ ] **Lint** — `ruff` absent in this environment; CI is the runner (see §7).
- [ ] **Production smoke test** — requires the rebuild (§8, next line).
- [ ] **P0/P1 findings resolved** — the one P1 is fixed and verified live; **no P0 exists**.
- [x] **Runtime validation completed** — the live probes in §7 exercised every new route, its refusal path, and the audit's DOM/route contract.
- [x] **Known limitations documented** — §1's honest limits + the panels' own refusal sentences.
- [ ] **Release artifact inspected** — the artifact predates this content (**rebuild required**).
- [x] **Rollback/release plan documented** — §6's per-change rollback column; nothing pushed.

---

# 9. Deferred Work

- **The other LLM's unfinished roadmap items** (found in the tree's own notes, not part of this
  gate): the AI copilot panel; a backtest engine + view; journal enhancements (screenshot, tags,
  Track Score). None of them is referenced by a view, a route or a test today, so none can be
  half-broken in the product — recommending they stay deferred until someone owns each end-to-end.
- **The equity option-chain paths** (`tradier`, `marketdata`) are implemented and pinned at the
  refusal boundary only. Deferred: a live pass with keys, and the greeks gap for Tradier (its OPRA
  chain carries IV/OI/volume but no gammas, so GEX has nothing to compute from — a decision for the
  owner, not a defect).
- **`ui.lookup.source` whitelist** in `config_store.py` accepts the three new feed names while no
  lookup path sends them yet — harmless, forward-looking; wire or trim when the lookup grows a
  source selector.
- **A soak of the new panels** (20 s cadences; four panels) — cheap to run inside the next live
  session; the bounded-store argument covers it in the meantime.

---

# 10. Audit Coverage Matrix

| Area | Inspected | Risks examined | Gaps |
|---|---|---|---|
| Release baseline (git, manifests, scripts, CI) | Full (§135 + this pass) | dirty tree, identity, CI-never-seen delta | CI result on this delta (uncommitted) |
| New engines (`atlas/gex|volatility|market_read|option_flow`) | Full (sources read, tests run, live behaviour) | fabricated values, NaN, unit scale, refusal honesty | long-run drift of the derived metrics |
| New feeds (`tradier`, `marketdata`, `finnhub`) | Surfaces + no-key paths | credential handling, chain shapes | live calls with real keys |
| Options REST surface | Full (mounted, live-probed, refusals) | payload truthfulness, error text, route count | none for this class |
| Desktop UI (four new panels) | Full (source, audit, selftests, wiring/help gates) | id collisions, listener/timer discipline, escaping, empty states | browser-run visual pass (no display here) |
| Desktop UI (existing modules) | Not re-inspected this pass | — | carried from §135/§136 |
| Docs (README, CONTRIBUTING, MENU_RECONCILIATION, handoff) | Full (claims re-derived) | stale numbers, undocumented features | none known |
| Dashboard legacy page | Not re-inspected | — | unchanged by this build |
| Packaging / distributables | Inventory only | the artifact predates this content | the rebuild |
| Security posture | Carried from §135 (bandit 0 High, pip-audit clean, secrets clean; job to re-run on the delta is CI's) | — | not re-run this pass — stated, not implied |

---

**Final operating instruction, honoured:** every change above is additive or a truth fix; nothing
existing was renamed except one duplicate id the new code owned; the four new panels follow the
suite's own rules for polls, listeners, help coverage and refusal language; and every claim in this
document is either a command's output or is labelled as carried/not executed.

---

## Appendix A — the GEX module audit and repair (the owner's screenshot, §138)

The owner sent a screenshot of the new **Gamma Exposure** panel and asked whether anything was
wrong with it. The panel rendered correctly; the data underneath it did not add up. Method: a real
browser (Playwright, webkit venv) against a headless instance of the app on a scratch profile
(`APPDATA=…\runtime\ofap_gex_audit\appdata`, port 8095, `--headless`) — rail click, Refresh, source
switch to Tradier, symbol box to ETHUSDT and back, the injected `?` chip, then the Volatility panel.
**0 console messages, 0 page errors, 0 failed requests** on every run.

| id | sev | finding | evidence | ship status |
|---|---|---|---|---|
| FG3-01 | P1 | Deribit's `mark_iv` (a **percentage**) was fed to engines documented and tested for **fractions**; the panel hid the mismatch behind a `n <= 1.5 ? n*100 : n` heuristic that prints a real 1.2% IV as 120% | live `iv` 19.33…56.24 vs `test_gex.py:163 assert r.atm_iv == 0.15`; `deribit.py:350 mark_iv` | fixed at the boundary — `from_deribit_ladder` converts once, both routes publish `iv_unit: "fraction"`, panels scale for display only; live after: `iv` 0.1894…0.5624, `atm_iv` 0.205 |
| FG3-02 | P1 | `gamma_exp`/`dex` were rounded to **4 dp** while crypto exposures run 1e-4…1e2 — most strikes quantised to `0.0000`, flattening the ΓEX column, turning the "widest first" sort into a tie, and coarsening the wall threshold | pre-fix probe: `gamma_exp` sample `[0.0, -0.0, …]`, max −0.158100 | fixed to 8 dp; live ΓEX column now −0.161744 / −0.063878 / +0.057342 / −0.042504 in strict descending order |
| FG3-03 | P2 | no unit anywhere: "Σ DEX 1.33K" of what | market → engine → payload review | `unit` on the wire (BTC / shares); table head **ΓEX (BTC)**; card line names ΔEX/ΓEX per 1-point move and leaves VEX/Θ in the venue's units |
| FG3-04 | P2 | γ printed as 8 fixed decimals (`0.00041000`); ΓEX's small end collapsed to `0.000000` | repo convention (`options.js fmtGreek`) | greek-rule formatting: `4.40e-4`, exponential below 1e-4 |
| FG3-05 | P3 | `total_vex` docstring/comment claimed `|gamma| * oi * iv`; the code multiplies by **vega** | `atlas/gex.py` | text aligned to the code |
| FG3-06 | P3 | `subText` escaped text that is written through `textContent` (would print `&amp;`) | `gex.js`/`volatility.js` review | plain text; `esc()` kept for table rows |
| FG3-07 | P3 | `expiryLabel` guarded `getTime()` but not `toISOString()`, which throws outside ±8.64e15 ms — a throw aborts the paint loop and blanks every later field | one frozen-moment read caught that shape once (four fields set, `volTerm` empty); a 21-sample series showed the field painted from t=2 s on | hardened (bounds check + try/catch, pinned by the selftest). Observed once, cause unproven — the only code path that could produce it is gone |

Also corrected: the Volatility smile column's **"Δ proxy"** label became **"Δ"** with a title — the
engine prefers the venue's real delta and only falls back to the linear proxy.

Deliberately not changed: the engine's exposure math (coins on Deribit, shares on a 100-share lot —
now labelled, not rewritten) and the ±10-strike ladder whose "25Δ" wings are really ±1.2%-from-spot
strikes (a wider `?width=` is the lever; claiming otherwise would be the kind of lie this pass
removes).

**Gates after the repair.** pytest **1,899 / 3 skipped / 0 failed** · **AUDIT CLEAN** (169 routes ·
160 ids · 0 missing · **0 duplicate ids** · 133 modules) · **45/45** node selftests · `node --check`
clean on both edited modules · live browser pass clean. Files: `atlas/gex.py`,
`atlas/options_api.py`, `ui/gex.js`, `ui/volatility.js`, `ui/index.html`, `ui/gex.selftest.js`,
`ui/volatility.selftest.js`. Nothing committed.

---

## Appendix B — The GEX/Volatility/Option-flow panels, second pass (§139): the panels as an options desk reads them

**Trigger.** The owner sent a screenshot of the two pop-out windows (Volatility surface · BTCUSDT and
Option flow · BTCUSDT) with one line: *audit, optimize, streamline and make these two panels
industry-standard*.

**Method.** Both pop-outs reproduced exactly as he has them — the launcher's `?aux=<view>&win=<id>`
serves an auxiliary window (`window.OFAPAUX === true`, `body.term-mode`, one widget, no Classic
switch) — plus the same panels in the Classic shell. Playwright (webkit venv) against a headless
instance on a scratch profile (port 8095): DOM text, computed styles (`display`, `text-align`, cell
colour), geometry, screenshots, console/network. **0 console messages, 0 page errors, 0 failed
requests** across all four loads.

| # | Sev | Finding | Evidence | Outcome |
|---|-----|---------|----------|---------|
| FG4-01 | P1 | The four §137 tables were written `class="grid"`, a name `ui.css:197` owns for the **layout** utility `.grid { display: grid }`. A table given `display: grid` loses table layout — header cells and rows flow as inline text, which is the owner's crop (`2026-09-20 77000.00 put 41.49% -0.0003 82.4000`, no header, no alignment) | computed `display` = `grid` on `#volTable` (and the `thead` = `block`) in the aux window; his screenshot | all four tables now carry the app's own data-table class (`table.data`, as the other 24 tables do) → `display: table` measured in all four renders |
| FG4-02 | P2 | Chain tables read as a text dump: no numeric alignment, OI in price-format decimals (`1234.57`), ISO dates, no ATM/ITM marking, no side colour | DOM + computed styles | `th.num`/`td.num` right-alignment (added beside `table.data`); `fmtOi` whole grouped counts (`1,235`); venue contract form (`20SEP26`, ISO in the title); `tr.atm` marked with an accent bar, `tr.itm` shaded; `td.call`/`td.put` coloured; strikes ascending, call and put adjacent; the smile's sort rule is now **by strike** |
| FG4-03 | P2 | The Volatility panel showed no chain totals: no P/C ratio, no total open interest, no IV range, no time to expiry — the numbers an options desk reads beside a smile | payload had none | new `_chain_stats(chain)` in `atlas/options_api.py` (computed from the same rows the engines read) → `call_oi · put_oi · total_oi · put_call_oi · iv_min · iv_max · dte`; Surface card row 2: **P/C OI · Total OI · IV range · Days to expiry**. Live: 0.529 · 2,692 · 21.28%–56.24% · 15.4 h |
| FG4-04 | P2 | The flow table listed only classified prints, so a quiet window read as an empty panel while 62 prints had traded; no row said which side paid, and premium was a bare coin number (`0.0022`) | live aux render: 1 block, 0 sweeps, empty-looking table; his screenshot's "91 trade(s)" with no tape under it | the route now publishes **`tape`** (every print in the window, newest first, tagged sweep > block > unusual > routine) + `spot`/`spot_from`/`premium_unit`; the table **is** the tape: Time · Expiry · Strike · Type · Size · Price · Premium · Side · Class, class as a chip, premium in **dollars** against the currency's perpetual mark, contract currency when the wire could not name one |
| FG4-05 | P2 | No money fields: nothing said which side paid more, or which print mattered | payload/summary card | **Call premium · Put premium · Net premium (signed) · Largest print**. Live: $497.4K / $96.2K / **+$401.2K** / `84,000C ×125 · $378.8K` — and they reconcile with the counts (0+1+0+99 = 100) |
| FG4-06 | P3 | The sub-line said `100 prints read` while the banner said `62 trade(s)`; both true, different meanings, and one alone reads as a bug | his screenshot (`100 prints read` vs `91 trade(s)`) | the sub prints both when they differ: `100 prints read · 62 in the window` |
| FG4-07 | P3 | The term-structure line used the ISO date while the table used the contract form | panel render | both read the contract form (`18SEP26`) |

**Not changed, deliberately.** The engines' maths (exposure and premium arithmetic), the ±10-strike
ladder width, and auxiliary-window placement (§128's multi-monitor pass owns that).

**Gates after this pass.** pytest **1,899 / 3 skipped / 0 failed** · **AUDIT CLEAN** (169 routes ·
0 missing · **0 duplicate ids** · 133 modules) · node selftests **49/49** in the four panel files
(whole UI suite: 45 files, 996 checks, 0 failed) · `node --check` clean on every edited module ·
live browser pass clean in both window shapes.

**Numbers re-derived.** README inventory: Atlas 35/**11,803**; Desktop UI 143/**54,498**; **Total
273 / 48,549 / 59,554 / 108,103**; suite 167 / 31,907 unchanged; UI suite 130 modules (45 selftests)
unchanged.

**Files.** `atlas/options_api.py` · `ui/volatility.js` · `ui/option-flow.js` · `ui/index.html` ·
`ui/ui.css` · `ui/help-data.js` · `ui/volatility.selftest.js` · `ui/option-flow.selftest.js` ·
`README.md` · `docs/SESSION_HANDOFF.md` (§139) · this appendix. Nothing committed.

## ## Appendix C — §140 findings register (depth map: hover, legend, empty state)

| id | area | defect | fix |
|----|------|--------|-----|
| FG4-08 | Market depth heatmap / hover | The canvas tooltip carried the repaint governor's counters and a developer note ("reference layout performance guidance") — diagnostics on a user surface. | Counters moved to `data-repaints` + `window.OFAPGOVERNOR`; the tooltip is the map's description again (`market-pressure.js`). |
| FG4-09 | Hover / empty squares | A hovered square with nothing recorded printed `undefined ·` and `resting 0.00` — absence rendered as data. | One honest sentence: "no resting size recorded in this square yet — the map is still gathering book updates" (`heatmap-pro.js`); pinned. |
| FG4-10 | Colour scale | The map's brightness had no on-screen legend; the scale cap and the saturating share lived in the dials only. | Legend bar painted from the map's own ramp (contrast dial applied) + `cap <n> · top <pct>% saturates`, written once per ramp/cap change (`atlas.js`, `atlas.css`, `index.html`). |
| FG4-11 | Hover readout | Absolutes only: a size, a Δ, a window total — nothing tying a cell to the scale, nothing quoted from the book. | Share of scale, Δ as a share of the level it moved from, and `bid · ask · spread` from the payload's own book, with decimals from the instrument's tick (`heatmap-pro.js`). |
| FG4-12 | Empty payload | `step undefined · 0 book updates` in the status line and `undefined` in the Depth KPI before the first book frames. | The wire's own `note`, a dash for an unstated step, `no book yet` for the range sub-line (`atlas.js`). |

Verification for this appendix: `node --check` on the five files; `heatmap-pro` 26 ok (12 new),
`market-pressure` 13 ok (1 new); whole UI suite 1,009 ok / 0 failed over 45 files;
`scripts/audit_ui_refs.py` AUDIT CLEAN; live headless pass `ofap_gex_audit/audit_heatmap.py`
(5 hover points, 0 diagnostics in the tooltip, status line = the wire's note). The map with live
book data was not exercisable in the audit sandbox (no engine/replay up: payload note "no data yet
— start the engine or a replay").

## ## Addendum to Appendix C — §141 findings register (engine panel)

| id | area | defect | fix |
|----|------|--------|-----|
| FG4-13 | Shared-cursor badge (5 panels) | Idle reading was `— · —`: three dashes naming nothing, which the owner read as `-.-`. | Idle badge reads what it waits for — `cursor: hover a chart` — while the title keeps explaining the mechanism (`cursor-link.js`, pin updated). |
| FG4-14 | Engine price precision | Prices were written by the price's magnitude (1000 → 2 dp, ≥1 → 3 dp, else 5 dp), so a 0.5-tick venue printed two decimals and a sub-1 price five. | Decimals come from the instrument's own tick, carried by the payload (`heat.tick`) into `OFX.state.data.tick`; one module-scope `pr()` serves the hover readout, the selection readout and every band/level line; the magnitude rule survives only as the no-tick fallback (`ofx.js: math.dpFromTick`, `ofx-view.js`). |
| FG4-15 | Engine drawings snap grid | The drawing layer was attached with a literal `tickSize: 0.5` — correct for one instrument by luck, a wrong grid for every other (the default symbol's tick here is 0.01). | `tickSize` reads the wire's tick; 0.5 only when a payload has never stated one. |

Pass note (kept deliberately): the first cut of FG4-14 placed `pr()` inside the selection readout's
scope while three of its call sites live in `paintReadout`, which the live audit reported as
`ReferenceError: Can't find variable: pr` on the engine panel. Fixed inside the same pass to a
module-scope `pr()` and re-verified console-clean.

## ## Appendix D — §142 sweep register (metric hygiene, whole app)

| id | class | what the sweep found | disposition |
|----|-------|----------------------|-------------|
| FG4-16 | price-by-magnitude | 2 sites still writing prices from the number's size: `ofx-view.js:684` (a §141 leftover) and `dashboard/static/footprint.js:_fmtPrice`. | Both tick-aware now; the magnitude chain survives only as a documented fallback, and the gate allows it only when a tick reference sits in the same statement. |
| FG4-17 | absence glyph | `--` used as the absent-value glyph in 41 module sites + 74 inline HTML cells + the legacy widgets' markup, against the em dash the readouts already used. | Consolidated to the em dash (desktop UI + `dashboard/static`). Time masks (`--:--:--`) kept and allow-listed. |
| FG4-18 | sweep coverage | The desktop UI renders two legacy dashboard widgets (`OrderbookLadder`, `MicrostructurePanel`) from `orderflow_system/dashboard/static/`. | The in-repo gate scans both trees; the widgets' own placeholders were fixed. |
| FG4-19 | diagnostics | The `Logs` view carries the palette stream's own counters ("0 messages seen · 0 coalesced · 0 dropped"). | Deliberate: the Logs view *is* the diagnostics surface. Nothing else in 38 views writes diagnostics to a user surface. |
| FG4-20 | classes triaged clean | instrument constants (7), percent-vs-fraction (4), counts-with-decimals (8) — all false positives on inspection. | Recorded with reasons so the next sweep does not re-litigate them. |

Verification for this appendix: `scripts/audit_metric_hygiene.py` exits 0; the view walker reports
38 views / 0 forbidden tokens / 0 console errors; pytest 1,899 passed / 3 skipped / 0 failed; UI
suite 1,024 ok / 0 failed over 45 files; `scripts/audit_ui_refs.py` AUDIT CLEAN.


## Appendix E — §143 findings (Drawings menu vs the charting-tool standard)

| id | finding | disposition |
| --- | --- | --- |
| FG4-21 | The menu exposed figure tools and one colour while the layer already supported width, dash and fill. | Menu gained a "Style for new drawings" section (width 1–4, solid/dashed/dotted, fill 0/10/20/35% from the line colour). |
| FG4-22 | No redo existed anywhere in the drawings layer although undo entries carried the state. | Redo stack added; every structural undo entry states its re-apply; Ctrl+Shift+Z / Ctrl+Y; menu rows show both depths. |
| FG4-23 | Nothing acted on a selection as a set: no duplicate, no selected-count, no delete row. | Duplicate selected (Ctrl+D, one undoable step, five-tick offset) + Delete selected (Del) + the count in the header. |
| FG4-24 | 45° snapping was Shift-at-drag only, and the latch did not persist. | "Snap to 45°" mode added; `snap45` now stored by the sanitiser and read back by `load()`. |
| FG4-25 | The drawing defaults' round-trip was never exercised end to end. | Proven live after a server restart: width 4, dashed, fill 0.2, snap45 true all return through `save(true)` → `load()`. |


## Appendix F — §144 findings (the panels drawer as a navigation surface)

| id | finding | disposition |
| --- | --- | --- |
| FG4-26 | Drawer search matched only name + hint; vocabulary the palette already indexes ("ladder", "dom", "vah") found nothing. | Keyword vocabulary per panel, every-token AND across name + hint + keywords + id, matches highlighted. |
| FG4-27 | No arrow/Enter walk although the Ctrl+K palette has one. | Walk over the visible rows in DOM order: ↑↓/Home/End, Enter opens, mouse follows, scrollIntoView, aria-activedescendant. |
| FG4-28 | No result count and no miss state. | Head chip ("21 panels" / "N matches") and an empty state naming the query, with a clear button. |
| FG4-29 | Nothing marked the panel already open. | "· open" on the row, in the directory and in the Recent rail. |
| FG4-30 | The drawer painted only at boot: opened on CVD it still marked Overview and showed no recents. | Repaints on open. |
| FG4-31 | No memory of what gets opened. | Recent rail (top five, newest first, per browser), fed by drawer clicks and nav-rail navigation. |
| FG4-32 | Row layout split name and description across a wide gap; placeholder explained nothing. | Hint adjacent + ellipsis (drawer-scoped CSS), footer key line, placeholder states what can be typed. |


## Appendix G — §145 findings (the Chart menu / display-variable settings)

Registry data quality first: 130 variables, **0** missing meanings, 0 enum without choices, 0 number
without bounds, 0 without a store default, 0 default outside its choices, 0 bad applies-flag, 0
duplicate path, 0 odd label. Everything below is the surface or the wiring around it.

| id | finding | disposition |
| --- | --- | --- |
| FG4-33 | 46 numeric variables stated no unit; the dimension lived only in the prose. | 34 state it (x / quantile / share / opacity / gain / size / score), reusing the meaning's own words; 12 keep the label as the unit ("levels", "columns", "prints" …). `atlas.footprint.equal_tolerance` awaits the owner's word. |
| FG4-34 | Stored ids printed raw in rows, submenus and options. | Human labels everywhere; raw ids stay the option values; labels come from one table (`window.OFAPVIEWS`). |
| FG4-35 | No changed/default state. | "· changed" on the row; restore offered only when it would do something, else "already at the default (…)". |
| FG4-36 | Numbers shown as stringified by the engine. | Printed at the control's own step precision. |
| FG4-37 | The editor did not state its range/choices. | Range · step for numbers, the choices list for enums, the format for lists. |
| FG4-38 | Markup bounds vs registry: `ofxLambda` min, `ofxMinBlock` max, `ofImbThresh` min; registry offered `imbalance_mode: "both"` that nothing implements. | Markup follows the registry (the enforced authority); the unimplemented mode removed from the choices and the meaning. Two tests pin this and are green. |


### Appendix G addendum — bounds that lied (found by the follow-up probe)

| id | finding | disposition |
| --- | --- | --- |
| FG4-39 | Seven numeric variables printed bounds the store rewrites (R, stack, text px, sweep c, lambda ms, imbalance threshold, equal tolerance), so the menu offered values that were silently clamped. | Registry states the store's bounds; the two markup lines bent the other way restored; pinned by `test_every_registry_bound_survives_the_store`. |
| FG4-40 | `atlas.footprint.equal_tolerance` had no unit and its registry ceiling was 10× what the store accepts. | Unit `share` (the comparison `analytics/footprint.py` makes is relative to the row's size); ceiling 1.0. |
