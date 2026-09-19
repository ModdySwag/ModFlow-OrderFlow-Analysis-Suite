# ModFlow OrderFlow Analysis Suite — v0.1b audit return

**Directive applied:** `Desktop/ai prompt.txt` (HFT footprint/heatmap spec + "expand, scrutinise to
top-tier, deliver a stepped report, don't break anything") against `Desktop/ingest.txt` — the fresh
799-line *Release Audit Report v0.1b* (Tiers 0–8, written 17:30 today).
**Tree:** `C:\Users\<you>\OrderFlow-Analysis-Pro` · HEAD `fa202d6`, nothing committed.
**Date:** 2026-09-16, ~18:00 local.

**Rule observed throughout:** every fix is isolated, lands with its own test, and was verified
before the next one started ("no change may impact the next change"). Nothing was changed on
faith — every claim below is either implemented with a passing pin, or rejected with the probe
that decides it.

---

## The headline

- **7 fixes implemented**, each pinned by a dedicated test: **8 new test files + 1 case added to
  `test_wiring.py` → 26 new cases. Suite 595 → 621 passed / 2 skipped.**
- **3 audit items rejected with evidence** — two of the audit's proposed "fixes" would have
  introduced real bugs (a wrong value-area band; a gate that demands *strengthening* selling).
  Neither was applied.
- **The README counts pass is done** (43 stale `(NNNL)` claims corrected — the §65 pending item).
- **Frozen `dist/` rebuilt after the last source edit and smoked on the artifact**: all endpoints
  200, unknown symbols serve `[]`, served UI hash-matches disk (`791f538d…`), **zero** error lines,
  numpy absent, **49.3 MB raw / 25.9 MB zipped** (494 entries).

---

## Part 1 — implemented fixes, most important first

### 1. Tier 1.5 — [FIXED] The DB candle round trip dropped the footprint

`insert_candle` always serialised the per-level bid/ask into `footprint_json`, but `get_candles`
never read that column back. Consequence (silent): the hourly volume-profile rebuild — the thing
that refreshes POC/VAH/VAL/bias on a running system — loaded candles with *empty* footprints and
fell back to "distribute the candle's volume evenly across its OHLC range", a cruder profile than
the live path, on a system that claims tick-level microstructure.

**Fix:** `data/database.py` — `get_candles` now selects `footprint_json` and deserialises it via a
new `_decode_footprint` (old rows with `{}`/NULL → empty; malformed cells skipped, never raised).
**Pin:** `test_candle_roundtrip.py` (3 cases): exact round trip incl. an exact-zero side; legacy
`''`/`'{}'`/NULL/malformed cells; and the rebuild path itself, asserting the evenly-distributed
fallback levels do NOT appear in the resulting profile.

### 2. Tier 1.4 — [FIXED] Absorption events merged distinct price levels on fine-tick instruments

`_check_level_absorption` keyed its event dict by `round(price, 4)`. Verified real, not theoretical:
**9 shipped instruments** carry ticks finer than 1e-4 (EURUSD/GBPUSD/AUDUSD/USDCAD/USDCHF/NZDUSD/
EURGBP at 1e-5, DOGEUSDT and TRXUSDT at 1e-5). An executed probe showed two levels one tick apart
being merged into one event and firing `min_attempts=2` from a *single candle* — overstated
attempts/volume on the primary entry trigger, exactly the audit's scenario (its BTC example was
arithmetically wrong, but the class of bug is real).

**Fix:** the key is now the instrument's tick-rounded price —
`round(round(price / tick_size) * tick_size, 10)` — the same bucketing footprint/volume-profile use
everywhere else. For every instrument with tick ≥ 1e-4 the new key is byte-identical to the old one.
**Pin:** `test_absorption_keying.py` (3 cases): two adjacent fine-tick levels stay two one-attempt
events; a genuine repeat still fires at `min_attempts=2`; coarse-tick keying unchanged.

### 3. Tier 8 #2 — [FIXED] Unknown symbols served an invented $1,000 chart when no engine was running

The audit's own verification checklist expects `GET /api/footprint/UNKNOWNXYZ → empty, not a
1000.0 placeholder chart`. Live probe found the `models_symbol` guard had been applied only to the
*warming* branches of `/api/footprint` and `/api/tape` — the no-engine branches still leaked demo
data built on the 1000.0 placeholder. Live-verified before fix (`UNKNOWNXYZ` → a full fake chart),
after fix (`UNKNOWNXYZ` → `[]`).

**Fix:** both no-engine branches now honour `models_symbol` (an unknown symbol gets nothing; the
UI shows its warming state). **Pin:** `test_wiring.py::test_unknown_symbols_serve_nothing_from_the_demo_fillers`
plus the served-app checks; live-verified on a sandbox (8091) and on the frozen exe (8099).

### 4. Tier 2.1 — [FIXED] Candle-wiring assertion now catches MIS-ROUTING, not just absence

The audit's worry is real: `_on_candle_close` (analytics) and `_on_candle_closed` (persistence +
WS broadcast) differ by one letter; a future edit wiring the wrong one persists twice or runs
analytics twice. But instead of the audit's rename pass (pure churn across two files),
`_verify_candle_wiring` now checks **identity**: the analytics callback must sit on the pipeline's
own candle builder, and the persistence wire must point at the orchestrator's own method — which
catches the actual failure mode. **Pin:** `test_candle_wiring.py` (4 cases: good wiring silent on
error; persistence-wire→analytics mis-wire reported; missing wire reported; analytics-callback
drift reported).

### 5. Tier 2.5 — [FIXED] Bybit trade without `T` now warns once instead of substituting silently

The wall-clock fallback stays (timestamps must still order), but the substitution is announced
**once per connection** (latched, re-armed on reconnect) so a feed gap can no longer produce
quietly-wrong session timestamps. **Pin:** `test_feed_timestamps.py` (3 cases).

### 6. Demo coverage — [FIXED] Six shipped instruments had no demo data

Sweep finding beyond the audit: demo mode could not serve **NIKKEI225, CAC40, ASX200, HK50,
USOIL, UKOIL** (no base price → "no demo data" on a demo tour). Added, with a documented note that
demo tick sizes are deliberately coarser than the live banks (rendering choice, like the demo
prices themselves — the audit's parity idea would change demo visuals for no benefit).
**Pin:** `test_demo_coverage.py`: every shipped symbol (31 specs + 18 crypto majors) is modelled;
unknown symbols still serve nothing. Live-verified: `/api/footprint/NIKKEI225` → 200 bars.

### 7. Tier 2.2 — [FIXED] `_CONFIG_BANKS` rows read as destination field names

The audit's "single highest-leverage readability edit": the bank dict keys and `_bank()` parameters
are now the actual field names (`min_aggressive_volume`, `max_price_displacement_ticks`,
`min_attempts`, `big_trade_filter`, `min_delta_threshold`, `min_price_displacement_ticks`,
`volume_acceleration_min`, `min_levels_swept`, `max_volume_per_level`, `thin_book_threshold`,
`volume_decline_pct`), with an explicit Spec→bank map in `get_config_for` keeping the short Spec
rows. **Proof it is behaviour-identical:** config golden unchanged (31 factories / 18 crypto majors
/ 49 instruments) and the full suite green.

### 8. Tier 6.2 + §65 pending — [FIXED] README counts pass

All 43 `(NNNL)` claims re-derived from the tree (18 were stale — e.g. main.py 666→820, app.py
1015→1235, bybit_feed.py 209→286, database.py 278→430, footprint.py 181→349, websocket_manager
186→293, demo_data 782→806, orderbook.js 318→398, tape.js 281→414). File Inventory re-measured
under a stated method: **172 files / 26,131 Python / 35,813 UI / 61,944 total** (suite: 60 files /
11,138 lines), badge ~60k→~62k, "45 demo instruments" → "every shipped instrument", "9-channel"→
10-channel ×2, models.py 7→9 dataclasses. Provenance now names the upstream fork commit
`b2ff4ee` (authorship verified: Mahmoud Chen, the upstream author). CRLF preserved; no other
README content touched.

### Plus — the audit's suggested new golden cases, landed

`scripts/regen_analytics_golden.py` gained `poc_top_cluster` (one-sided profile — must keep
VAL < POC) and `poc_at_low` (pins `val == poc` at the extreme as CORRECT). Golden: 38 → 40 cases,
regen check `max diff 0.000e+00`; **no existing number moved** (the drift report listed only the
two new cases + the fixture hash).

---

## Part 2 — rejected audit items (with the evidence that decides them)

### Tier 1.1 — [REJECTED] "value-area inversion on one-sided profiles"

The claim: on profiles where POC sits at an extreme, VAL collapses onto POC and is "wrong"; the
suggested guard would push VAL to a level below the accumulated range. **A read of the loop plus an
executed probe (6 extreme profiles) shows:**
- The invariant `val <= poc <= vah` holds **by construction** — `lo`/`hi` start at `poc_idx` and
  only ever move outward;
- The only `val == poc` outputs are POC-at-the-extreme shapes, where a value area with no lower
  neighbour is the standard expansion's *correct* result (e.g. POC 60 of a 100 total → the 68%
  band cannot extend below it);
- The audit's own proposed test — "POC at the top 3 rows produces VAL < POC" — **already passes on
  the current algorithm** (probe: poc=12.0, val=10.0, vah=12.0).

The audit's proposed fix would report a band **wider than the 68% containment** — a new bug.
**Action instead:** behaviour pinned by `test_value_area_edges.py` (4 cases) + the two golden cases;
exact numbers recorded.

### Tier 1.3 — [REJECTED] "inverted bearish exhaustion gate"

The claim: line 176 should read `if vol_trend >= 0 or delta_roc >= 0: return None`. **That change
is wrong on the sign convention:** in a down-trend delta is negative, and "sellers exhausted /
less selling conviction" means delta rising toward zero — `delta_roc > 0`. The audit's form
(require `delta_roc < 0`) demands delta falling further = selling *strengthening* — the opposite of
exhaustion — and would additionally silence the textbook dry-up bin. Five synthetic bins were
executed against the live code: bearish fires on volume dry-up with sellers weakening; bearish
withholds while selling strengthens (the audit's "should NOT fire" case — already correct);
bullish mirrors both. **Action instead:** `test_exhaustion_gates.py` (4 cases) pins all bins, and
the sign-flip rationale is now a comment in the code so the next reader cannot "fix" it wrongly.

### Tier 1.2 — [REJECTED as stated / [FIXED] as a pin] "the cooldown knob is dead"

Not dead: `EngineController.start` overrides **both** aggregator values from the user config
`risk` block (`desktop/engine.py:591–594`, defaults 30 s / 40) — that is what a GUI user actually
runs with; the audit read only the standalone `OrderflowSystem` default and concluded the knob was
inert. What was genuinely missing: a pin. **Action:** `test_engine_wiring.py` (2 cases) drives the
controller's own start path and asserts config→aggregator end-to-end (123.0/77.0 reach the
aggregator; missing block falls back to the documented 30/40); a provenance comment was added in
`main.py`. Wiring `RiskConfig.signal_cooldown_seconds` "as the source" as the audit suggested would
have *bypassed the user's own config store* — deliberately not done.

---

## Part 3 — verified as already done (no action taken)

- **Tier 0** — LICENSE already carries the dual MIT notice (original + "Modified by ModdySwag");
  README provenance now names the fork commit (added).
- **Tier 2.3** — the JS selftests are NOT hand-run: `.github/workflows/ci.yml` (Windows, Python
  3.11+3.12) runs pytest, the UI audit **and all 19 selftests**; I also ran the 19 locally: green.
- **Tier 4.2** — `orderflow_system.log` / `orderflow_data.db` are untracked and covered by
  `.gitignore` (`git ls-files` shows none; `git check-ignore` confirms). Nothing to untrack.
- **Tier 3 (the spec-vs-built map)** — the audit's "not aligned/not built" list is **stale**:
  stacked-imbalance S/R zones (`ofx.js math.stackedZones` + drawn), execution sweep circles with
  the exact `r = c·cbrt(V)` formula (`math.sweepRadius`), the snap-to-live float with sparkline
  (`#ofxSnapFloat`, `paintSpark`), the font-weight ramp (`math.fontWeight`), the 45 px LOD ladder
  (`math.lod`) and the CVD read-out panel (`paintReadout`) are all present and wired. README
  claims were verified honest against this (nothing to downgrade).
- **Tier 7.10** — the `data` block (session-start-hour / retention / prune) is deliberately not in
  the display registry; the menubar says "History & retention — phase 3". Backend, `/api/control/
  storage`, clamps and the Logs chip all exist. Left as the planned phase-3 item.
- **Bybit orderbook `u`-as-timestamp** — the audit didn't raise it; my sweep checked: it is a
  **known, centrally-normalised** condition (`atlas/clock.py as_epoch_ms`, with tests) — update ids
  are replaced by the caller's own clock everywhere a duration is computed. Working as designed;
  not touched.

---

## Part 4 — my own sweep findings (owner decisions, deliberately NOT changed)

### [RESOLVED — executed in Part 7, handoff §67] The displacement divisor clamp — the one real strategy-level question

`patterns/absorption.py:167` and `patterns/initiative.py:83` compute price displacement as
`... / max(tick_size, 0.01)`. For the **25 instruments with tick < 0.01** this silently redefines
"ticks": for EURUSD, a 0.02 move counts as "2.0 ticks" against a `max_price_displacement_ticks = 2`
threshold — in real ticks it is **2,000**. The absorption "low displacement" gate is therefore
effectively vacuous at candle scale for FX/JPY/silver/crypto-fine instruments, and the initiative
body requirement is 30 pips rather than ~3 for FX. Evidence: probe + per-instrument tick table.
**Why not changed:** correcting it STRICTLY narrows when absorption can fire on 25 instruments —
a live signal-behaviour change that needs the owner's call and, if taken, a bank-threshold retune.
Recommended: one decision, then one small patch + a test, done under §66's isolation rules.

### [OPEN] Remaining demo-fill endpoints for unknown symbols

`/api/candles`, `/api/markers`, `/api/volume-profile`, `/api/bias`, `/api/orderbook`,
`/api/delta`, `/api/microstructure`, `/api/strategy-status` still serve demo fills for unknown
symbols in no-engine mode. Footprint/tape were fixed (audit-named); extending the same guard to
the rest is a small, coherent follow-up — flagging rather than widening scope unasked.

---

## Part 5 — gates and verification at close

```
pytest orderflow_system -q                    621 passed / 2 skipped  (was 595 / 2; +26 pins)
scripts/audit_ui_refs.py                      AUDIT CLEAN
ruff check orderflow_system scripts           All checks passed
scripts/regen_analytics_golden.py             OK — 40 cases, 2196 numeric leaves, max diff 0.000e+00
scripts/regen_config_golden.py                golden matches: 31 factories, 18 crypto majors, 49 instruments
19 × node *.selftest.js                       19 passed, 0 failed
```

**Source smoke (sandboxed APPDATA, headless, port 8091):** healthz 200; `/api/instruments` 51 rows;
`/api/scanner` 51; `/api/volume-profile/NAS100USDT` real profile; `/api/bias` short + 4 qualified
levels; `/api/footprint/NIKKEI225` 200 bars (new coverage); `/api/footprint/UNKNOWNXYZ` → `[]`;
`/api/tape/UNKNOWNXYZ` → `[]`; 0 client-error lines.

**Frozen exe smoke (rebuilt after the last source edit, sandboxed, port 8099):** all endpoints
above → 200/`[]`; served `/desktop/ofx.js` **hash-matches disk** (`791f538d42…`, 146,254 bytes);
`/desktop` 200; numpy absent (0 of 494 `_internal` entries); log = 16 lines, all INFO, **0** client
errors / tracebacks; **49.3 MB raw / 25.9 MB zipped** (25.87 MiB), 494 entries. Process
stopped via PowerShell `Stop-Process` (the reliable stop on this host), port closed.

**Isolation discipline:** each fix landed alone on top of the previous verified state; goldens show
no unintended movement (config golden byte-identical in meaning; analytics golden diff = exactly
the two deliberate new cases); the suite count is the only number that changed.

---

## Part 6 — what remains (the release is the owner's call)

1. ~~Decide the displacement-clamp question~~ — **done (Part 7, handoff §67)**: unit restored, six pins, dist rebuilt again.
2. Release sequence (unchanged, now safe to run): commit → create the GitHub repo → push →
   tag `v0.1.0-beta` → attach `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` (already built:
   `dist/ModFlowOrderFlowAnalysisSuite-win64.zip`, 25.9 MB).
3. Optional: extend the unknown-symbol guard to the remaining demo-fill endpoints; InstallShield
   packaging (per the §65 plan).

**Nothing in this pass requires any further code change to ship; every fix is contained, tested,
and reversible.**
---

## Part 7 — Update: the Part 4 decision executed (the displacement unit, §67)

The owner approved attending to the Part 4 item. Executed with the same isolation discipline —
test first, proven to bite, then the fix.

**The convention chosen, and the argument for it.** Displacement is measured in TRUE tick
steps. That is not a new convention: it is the unit every instrument with tick >= 0.01 has
always run in (the old `max(tick_size, 0.01)` floor was inert there), so the fix puts the 25
fine-tick instruments back into the same, scale-free units as the rest of the tool — a level
N ticks from the current price is N footprint levels away; a candle body of N ticks spans N
price levels. Because the unit is scale-free, **no bank retuning was needed**: 2 and 3 mean
the same thing on EURUSD as on NAS100. (The alternative — keep the floor, inflate thresholds
per class — hides the unit and re-breaks on the next unusual tick; rejected.)

**Proven-to-bite receipt.** The new pin file `test_displacement_ticks.py` (6 cases) was
written first and run against the untouched code: the three fine-tick cases failed exactly as
predicted (EURUSD absorption admitted a level 5 ticks away; initiative could not fire), while
the coarse-tick and fallback cases passed on both sides — they pin what must NOT move. The
zero-tick guard case also exposed a latent `ZeroDivisionError` in the §66 event-keying line;
the same guarded local closes it (`tick_size if tick_size and tick_size > 0 else 0.01`).

**The change.** Two expressions: `patterns/absorption.py` and `patterns/initiative.py` — the
guarded local + `/ tick_size` instead of `/ max(tick_size, 0.01)`. For tick >= 0.01 the
divisor is mathematically identical, so coarse-instrument behaviour is bit-unchanged. Effects
on the 25 fine-tick instruments: absorption's "price displaced little" gate finally means what
its name says (EURUSD: within 2 ticks, not a 200-pip-vacuous band), and initiative on
EURUSD/GBPUSD is reachable again (3-tick body, not a ~300-pip requirement). Live-path proof:
an EURUSD `InstrumentPipeline` (real config) closed 4 candles end-to-end through all detectors
without an exception.

**Gates after the change.** pytest **627 passed / 2 skipped** (621 + 6) · AUDIT CLEAN · ruff
clean · analytics golden OK (40 cases, max diff 0.0e0) · config golden OK (31/18/49) · 19 UI
selftests green.

**Frozen dist (second rebuild of the day, after this change).** Rebuilt 18:16 and re-smoked
sandboxed on 8099: all endpoints 200 (including a EURUSD fine-tick demo footprint),
`/api/footprint/UNKNOWNXYZ` → `[]`, served `/desktop/ofx.js` hash-matches disk (`791f538d…`),
log 11 lines / 0 client errors, numpy absent, **49.3 MB raw / 25.9 MB zipped** (494 entries);
`dist/ModFlowOrderFlowAnalysisSuite-win64.zip` refreshed. Port closed.

**With this, no code item is pending: the release sequence itself is the only remaining step.**

---

## Part 8 — Update: the unknown-symbol guard generalised (handoff §68)

§66 fixed /api/footprint + /api/tape; the same Tier 8 #2 rule belonged to the other eight
demo fillers the desktop shell clones the active symbol into — and each of them answered an
unknown symbol with invented data. Fixed with the same discipline: `test_demo_symbol_guards.py`
written first, failed on the untouched code (8 invented markers, then more), green after the
change; every modeled symbol's fill is byte-identical. pytest **629 passed / 2 skipped** ·
AUDIT CLEAN · ruff clean · both goldens OK · sandbox smoke on source AND the frozen exe
(all ten endpoints empty-of-shape for UNKNOWNXYZ; BTCUSDT/EURUSD populated). Dist rebuilt
18:45 and re-zipped (25.8 MB zipped / 49.3 MB raw, 494 entries).

---

## Part 9 — Update: the Windows installer built and verified (handoff §69)

The §65 follow-up "InstallShield after that" is done. `installer/make_installer.ps1` regenerates
a Basic MSI project from InstallShield 2026's blank template, wires per-user install
(%LOCALAPPDATA%\Programs, no UAC), the dynamic payload link, and the desktop shortcut, then
builds and hashes **`dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`** — 26.79 MB, sha256
`0153B20DBB3048937547DFBBD9D7248F910C4786CAE68CB49DE662FDA2D11599`, 0 build errors.

Verified end to end on this machine: silent install → 494 files, exe correct, desktop shortcut
created (correct target, correct description) → installed app runs (healthz 200; the §68
unknown-symbol guard holds in the frozen build) → silent uninstall → everything clean. Eight
automation traps were found and encoded (32-bit COM, template-copy creation, object-only
AttachComponent, native AddFile, DisplayName-as-filename, AddShortcut Target `[#FileKey]` +
8.3-name string fix, IsCmdBld path form, evaluation-mode build type) — documented in
`installer/README.md`. Start Menu shortcut and the WebView2 chain are the two deliberately
documented follow-ups (automation API limits; .prq ships ready). No app source changed:
gates still 629/2, AUDIT CLEAN, ruff clean, goldens unchanged.
