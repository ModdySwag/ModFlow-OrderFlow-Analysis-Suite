# Upgrade action plan — ModFlow OrderFlow Analysis Suite

**Date:** 2026-09-16 · **Tree:** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · **HEAD:** `bcb94ea` · tree clean, nothing pushed
**Built from:** `report1.txt` (the engine audit on the owner's Desktop, 294 lines) — re-verified line by line
against the tree, then reconciled with `docs/SESSION_HANDOFF.md` §25–§30, `docs/SYSTEM_SWEEP_2026-09-15.md`
§4 (R2–R7), `docs/AI_AGENT_BUILD_PROMPT.md` (workstreams A–I) and `docs/RESUME.md`.
**The ask:** interpret report1's summary against what really needs enhancing/fixing, weigh professional
design norms in the decisions, and land as one sequenced plan of action.

---

## 0. How to use this document

Read §1 first — it corrects the audit. Two of report1's three headline "gaps" are already built in
`ofx-view.js`, and two of its smaller asks exist too; a plan built on the audit as-written would spend days
re-building shipped code. §2 is the plan: P0 = displayed truth and session integrity, P1 = the interaction
canon and spec alignment, P2 = measured performance, P3 = hygiene, backend and packaging. §3 states the
design principles the ranking follows, so the *why* survives the next redesign. §4 is the sequence with the
gate that closes each phase. §6 is the evidence trail for every claim above.

Baseline gates, measured while writing this plan (all green):

```
.venv/Scripts/python.exe -m pytest orderflow_system -q      -> 483 passed, 2 skipped
.venv/Scripts/python.exe scripts/audit_ui_refs.py           -> AUDIT CLEAN
node .../ui/ofx.selftest.js        -> 119 ok, 0 failed      (shell 22 · bus 12 · links 10 · watchlist 15
node .../ui/shell.selftest.js      -> 22 ok, 0 failed        news 17 · options 21 · fundamentals 18
                                                            market-pressure 12 · intent 7 · study-api 45
                                                            search-ops: all checks passed)
```

---

## 1. Verdict on report1.txt — what it got right, what it got wrong

### 1.1 Its three "gaps" against the tree

| report1 claim | Truth in the tree | Evidence |
|---|---|---|
| **P0: "no DOM floating tooltip panel consuming `state.hover`"** | **Built.** Two consumers exist: a cursor tooltip and a full metric readout panel | `ofx-view.js` `paintTip()` :401 → `#ofxTip` (`index.html:247`, `.ofx-tip` `atlas.css:99`); `paintReadout()` :320 → `#ofxReadout` (`index.html:250`, `.ofx-readout` `atlas.css:79`); wired at `ofx-view.js:492` (`OFX.state.onHover = (h) => { paintTip(h); paintReadout(h); }`) |
| **P0: "no floating 'Snap to Live Market' sparkline widget"** | **Built.** A bottom-right badge with a live sparkline, shown only when the viewport is historical, click = snap to live | `#ofxSnapFloat` + `#ofxSpark2` (`index.html:248`); `paintSpark()` `ofx-view.js:277` (last 60 closes, up/down colour); `paintChip()` :265 toggles `.on` from `OFX.state.mode`; styling + reduced-motion guard `atlas.css:103-111`; click handler `ofx-view.js:520` → `OFX.snapToLive()` |
| **P0/P3: WebGL absent** | **True, and its own conclusion is right: defer.** Canvas 2D is measured sub-frame (sweep §B3/B4: repaint 29.93→1.34 ms; heat 0.278→0.074 µs/cell; brief §6 revisits above ~2 k simultaneous cells) | P3-1 below keeps it behind a measured trigger |

The readout is not a stub — it carries the whole metric set report1 asked for and more: O/H/L/C, volume,
buy/sell, delta, CVD, POC (price + share %), max bid/ask with size, level count + imbalance count, cursor
price, level bid/ask, imbalance side + ratio (∞ handled), stacked-zone side + level count, depth at the
price under the cursor, prints + sweep volume, book events, bars in view, price band, recoveries. The
tooltip itself stays to three lines on purpose (time · price, level, flag · delta · CVD) — the comment at
`ofx-view.js:406-408` records the decision: the panel owns the metrics, the tag stays legible.

### 1.2 Smaller report1 asks — status

| report1 item | Status | Evidence |
|---|---|---|
| lambda control missing (§6-11) | **Exists** | `index.html:230` `lambda ms` (`#ofxLambda`) beside min block (`:232`), VA % (`:233`) and ramp (`:234`) |
| perf HUD missing (§6-10) | **Exists** | `ofx-view.js:256` stats line: frames · avg (EMA) · p95 · max · LOD · col width · levels · avg level volume; readout idle state adds bars in view, price band, depth cells, flow marks, recovered (`:327-335`) |
| "audit `dashboard/static/footprint.js`; remove if dead" (§6-8) | **Wrong as stated — it is live code** | It is `orderflow_system/dashboard/static/footprint.js`, loaded by `index.html:764` (`/static/footprint.js`) and instantiated by `ui.js` `ensurePanel('orderflow')` → `new FootprintChart`. The keep-or-retire question is sweep **R7**, not a delete |
| Ladder connector line (§4.4 + brief I-2) | **Built, in a better form** | `cursor-link.js` + `paintTrace()` (`ofx-view.js:379-399`) draw a DOM trace line at the cursor's price into the price rail, and `wireCursorLink()` (`:444-473`) highlights the ladder row for that price — plus an honest note when the price sits outside the drawn ladder levels. A highlight that follows the cursor beats a line that spans two coordinate spaces |
| `cell.peak` flat 0.92 → every vanished wall leaves the same ghost (§2.2 minor) | **True, open** | `ofx.js:1150` `cell.peak = Math.max(cell.peak || 0, alpha)`; consumed by `decayAlpha` at `:1156` |
| `hover()` iterates all prints per mousemove (§3.2-1) | **True, open** | `ofx.js:1778-1781`. See §1.3 — the real cost is larger than report1 measured |
| Imbalance-cell glow, stacked-zone projection alpha/label, LOD pop, heat-vs-base in one rAF (§2.1/§2.4 minors) | **True, open** — cosmetics, conditional, or design choices | `ofx.js:1287-1288` (tint), `:1234-1249` + `:1316-1325` (zones), `:1566-1612` (render order) |
| `carry_forward` has no UI indicator (§2.2 minor) | **True, open** | No `carry_forward`/`carryForward` reference under `desktop/`; it is a backend parameter with no on-screen state |
| `orderbook.js` normaliser's array/`quantity` branches may be dead (§5.2-4) | **Plausible, cosmetic** | `orderflow_system/dashboard/static/orderbook.js:85-105` — worth one look during R7, not before |

### 1.3 A gap report1 missed

`hover()` also re-scans the **whole depth matrix** and re-sums **CVD from bar 0** on every mousemove:

- `ofx.js:1774` — `for (const cell of state.data.heat)` to find the hovered row's resting size
- `ofx.js:1763-1764` — CVD rebuilt with a loop from bar 0 on each hover

So the per-mousemove cost is O(prints + heat cells + bars), not O(prints). With a 10 k-print tape and a
30 k-cell matrix that is ~40 k iterations per pointer move. It only runs on hover, but a fast sweep across
the canvas fires it continuously. P2-1 fixes all three with one index pass in `setData()`.

### 1.4 Credits due — report1's "already fixed" section matches the record

Binary-search bar lookup, palette LUT instead of per-cell colour strings, the 33 ms heat throttle and the
visible-column search are all real and were landed with measurements in the sweep pass (B3/B4). report1's
§3.1 and the sweep's §2 agree; nothing to redo.

---

## 2. The plan

Each item: **why** (the norm that justifies its rank, cross-referenced to §3), **where**, the **gate**
whose output is the evidence, and a rough **size** (S = one sitting, M = one focused session, L = multi-session).
"Live" gates run on a sandbox: `APPDATA="$LOCALAPPDATA/Temp/ofap_<name>_sandbox"
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 809x` (8090–8094 only), driven over
CDP at `http://127.0.0.1:809x/desktop/`; stop every process afterwards and grep `orderflow.log` for
`client error:` lines. `requestAnimationFrame` may never fire headless — paint directly; keep `js()` probes
under ~5 s (`RESUME.md` traps).

### P0 — displayed truth and session integrity

**Status 2026-09-16: all six closed.** The pass is recorded in `docs/SESSION_HANDOFF.md` §32 with the
evidence per item; P0-1's three visuals were seen live and exposed three further defects (the ladder's
missing `data-price`, a highlight wiped by the ladder's own re-render, an unbounded nearest-match), all
fixed and pinned. P0-2/P0-3 carry new selftest checks (watchlist 17, bus 13); P0-4/P0-5 carry
`test_book_integrity.py` (4) and `test_websocket_backpressure.py` (5). Gates after the pass: 493 passed /
2 skipped, AUDIT CLEAN.

Nothing in P1 matters while a panel can show a stale or contradictory number. Norm: truth before polish (§3.1).

**P0-1 · Prove the three unverified visuals on live data.** M
The handoff (§2) is honest that these were never *seen*: (a) stacked-zone bands (maths proven, no band
observed — the live sample had no stacked runs and the footprint was off-view), (b) the thermal ramp's
pixel effect, (c) the trace line's successor path (the ladder note said "outside the drawn levels" every
time because the ladder wasn't in the same view). Gate: a sandbox run with the footprint in view and depth
history present; evidence is a screenshot or a pixel count, not an opinion; the three checks pass or the
defect is named.

**P0-2 · Watchlist configured-instrument rows — re-check live (§27 recipe).** S
The `refreshPlaceholders()` helper is inert until the panel's real poll loop calls it; the last live check
still showed 45 demo rows and zero configured rows with `ZZZTEST` posted. Gate: post `ZZZTEST` to the
config's instrument list, reload, a row appears beside the demo list; keep the demo/configured split.

**P0-3 · Bus chip counter reconciliation (§29).** S
The chip's `sub` and `telemetry().subscribers` disagree at the same instant (measured `1 sub · 2 ch` vs 3
subscribers). Two counters, one of them mis-named. Norm: consistency (§3.4) — a status readout that
contradicts its own telemetry is worse than no readout. Gate: same-instant equality; extend
`bus.selftest.js` to pin the meaning.

**P0-4 · Order-book integrity — sweep R3.** M
Track Bybit's `u`/`seq` (`data/bybit_feed.py:142`, currently used as a timestamp and never checked for
gaps); on a gap, mark the book stale, re-subscribe for a snapshot, and say so in the view's status line.
Norm: canon #8, declare freshness (§3.6) — silently trading a stale book is the worst failure class in this
app. Gate: a test feeding deliberately gapped/reordered deltas asserts the stale flag and re-seed, plus a
live check.

**P0-5 · Broadcast backpressure — sweep R2.** M
`dashboard/websocket_manager.py:104-152` holds `_lock` across every `send_text` with no per-client queue.
Deliver: bounded per-connection queue with drop-oldest for `tick`/`orderbook` only — never drop `signal` —
and a write timeout that marks a dead client. Gate: a pytest driving one deliberately slow client while a
fast client receives a fixed message count, plus a live two-client check.

**P0-6 · Get the one `hermes` string out of the source.** S
`orderflow_system/desktop/api.py:1525` — a comment ("`hermes logs`-style tooling") — violates the brief's
non-negotiable #7. Reword it. Gate: `grep -ri hermes orderflow_system` over source/text == 0. Note for the
next gate run: `dist/` matches are only CPython's own `unicodedata.pyd`, not our code.

### P1 — the interaction canon and spec alignment

**Status 2026-09-16: P1-1 through P1-6 are done** (handoff §33–§38) — the token block, `themes/`,
`theme.js`, the Appearance card and the brief's grep gate at **0** (P1-1); the cursor spine adopted by
six panels, measured live, one heatmap hover lighting the engine, the ladder, the tape and the profile
with eight badges on one text (P1-2); a shift+drag on the engine producing the statistics strip and a
real CSV on disk plus markers remembered per symbol (P1-3); the strips given keys, pause-on-hover and
click-to-locate (P1-4); and the cosmetics rebuilt as feedback — density-tracked ghosts, a low imbalance
glow with the POC keeping the strong one, a labelled zone projection, `carry_forward` on the panel and
the hidden-block count beside its control (P1-5); and the map answering duration — `held_ms` on the
walls the map draws, a Held column, a cursor line and an optional age tint, with the 74/22 px insets
shared between the map and its overlay (P1-6). **P1-7 (alerts: manage, scope, read like sentences) is
next — recon and build spec at §39 / the P1-7 item below.**

**P1-1 · Theme and token layer first (brief A). — do this before any visual polish below.** L
Unstarted: `atlas.css` contains **zero** `--of-` tokens (`grep -c -- '--of-'` → 0) and there is no
`themes/` directory; `.ofx-tip-hot` and friends hard-code raw hex. Deliver: token block + `themes/` CSS
(light/dark/high-contrast, 8 accents, Windows-8 palette) selected by config and a Settings switcher,
applied before first paint; Segoe UI Variable with `tabular-nums` wherever a number can change while
running; Metro tiles for KPI blocks; density tokens on `--of-row-h`. Norm: consistency & standards (§3.2) —
every subsequent colour decisions cites a token, so decoration drift is impossible. Gate: `grep -nE
'#[0-9a-fA-F]{3,8}' atlas.css | grep -v -- '--of-'` == 0 plus live screenshots at 1024×640 and 2560×1440,
light and dark.

**P1-2 · Finish the cursor-link spine (brief B).** M
The spine exists (`cursor-link.js`; the engine publishes in `paintTrace`; the ladder highlights) — the
canon's test is *four panels at once*: profile, CVD, depth, tape and the imbalance strip must all answer
the same hover/selection, and the highlight must survive repaint, resize and symbol switch. Norm:
recognition over recall (§3.4). Gate: one live pass — hover a level, count the panels that light, resize,
confirm the highlight is still there at the same price.

**Done 2026-09-16 (§34).** `cursor-link.js` owns `move`/`clear`/`set`/`select`/`subscribe` (now with a
real unsubscribe) plus `nearest`/`step`/`text`/`badge`; the heatmap publishes and draws the shared
level, the ladder publishes and traces, the tape publishes and marks its rows at the cursor's price,
the profile marks its TPO rows, the engine does both, and eight badges across six panels read from the
one store. Gate measured: 76332.12 → engine "on the ladder" + rung 76332 traced + 10 tape rows + four
badges on `76332.12 · 02:05:02`; 76398.84 → 9 profile rows + 8/8 badges; both survived a 1366×900
resize and a forced `loadMarketProfile()` rebuild. Limits: clear-on-leave by design (a sticky level is
P1-3's click-selection), no drawn cursor line in the CVD/imbalance canvases yet, symbol switch
unproven (one symbol in the sandbox).

**P1-3 · Selection is measurement everywhere (brief E).** M
A drag over bars, a level, a time range or markers yields the statistics strip (volume, delta, resting
depth change, VWAP, count, largest trade) + export — the mechanism exists in `heatmap-pro.js`
(select → isolate → stats → CSV); extend it to walls and markers, and persist markers per symbol (they are
session-only today, brief §6). Gate: live selection on the engine view producing the strip and a file on
disk under `%APPDATA%\OrderFlowAnalysisPro\exports\`.

**Done 2026-09-16 (§35).** Shift+drag on the engine stage boxes a time × price region; the box is drawn
on the live layer and survives repaint and camera moves, the outside dims rather than hides.
`math.selectionStats` (pure, selftested — ofx selftest 119 → 134) computes volume, delta, buy/sell,
prints (count + size), VWAP by size, the largest trade with its price and the resting-depth change;
`math.selectionRange` clips AND orders the two positions (a one-sided clamp produced `i0 = 11,
i1 = 4` live). `#ofxSelFloat` prints them beside the stage with `Export CSV` and `Clear`, and the file
lands in the exports folder (`ofx-selection-<SYM>-<stamp>.csv`, header + one row per bar + a prints
section). The selection rides `OFAPCURSOR.select()`, so any panel can answer it. **Markers are
remembered per symbol** (store block `markers`, sanitised, `GET/POST /api/control/markers`, the route
answering with what the store accepted, placed back on the map by a bounded nearest; measured: 2 rows
restored after a reload). The mark action no longer uses `window.prompt` (the frozen WebView is not
guaranteed to render one) — the note is a toolbar field. Open from this line: the region stats/CSV do
not yet include the fresh-walls table.

**P1-4 · Strips: keyboard stepping and click-to-locate completion (brief C).** M
`strips.js` already holds the reader's place and counts arrivals; add keyboard stepping through a strip and
wire click-to-locate so a tape print seeks the linked panels. Gate: live — pause on hover, step with the
keyboard, click a print, assert the linked panels moved and the chip cleared.

**Done 2026-09-16 (§36).** ArrowUp/ArrowDown step a row, PageUp/PageDown a screenful, Home/End either
end; stepping engages the hold and the chip says "held" even with nothing to count. Pause on hover is
in (it did not exist: a fast tape pulled rows out from under a parked pointer). A click on a row
carrying `data-time`/`data-price` publishes that print to the shared cursor and calls the engine's new
`OFX.seekToTime()`, then releases the hold. Measured: 3 steps → 72 px held with 1 arrival counted and
the status chip naming the hold; a real click → `locate {price 76223.9, bar 9}`, the viewport moved,
the chip cleared. Three defects found live and fixed in the pass: a pixel threshold that swallowed a
row-step (28 px against a 24 px row), a scroll event deciding against a re-resolved anchor (the tbody's
rebuild walked it up to the parent, whose offset 0 read as "on the newest line"), and the tape's own
auto-scroll fighting the strip for the offset (it now asks `OFAPSTRIPS.holds(el)` first). No Escape
binding: the shell owns that key.

**P1-5 · Spec-alignment cosmetics, redesigned as token-driven feedback.** S each
From report1's minor lists, each re-argued rather than copied:
- *Ghost brightness by size* (`ofx.js:1150`): make `cell.peak` track the cell's density-bucket alpha so a
  pulled wall leaves a ghost proportional to what it was (§3.6 honest degradation — a uniform 0.92 ghost
  asserts all liquidity was equal).
- *Imbalance-cell glow*: a low `shadowBlur` on imbalance cells only, with POC keeping the stronger glow —
  accent stays scarce (§3.3). Skip entirely if P1-1's tokens show it fights the ramp.
- *Stacked-zone projection*: raise the projection alpha slightly and label it at the right edge, so a
  projected zone reads across the chart, not just where it starts.
- *`carry_forward` indicator*: expose the flag on the heat panel; ghost liquidity with no explanation is a
  lie of omission (§3.6).
- *Hidden-block count next to the min-block filter*: the engine already tallies hidden blocks; print the
  number beside the control (handoff §2's deferred item). A filter that hides data must say how much (§3.6).
Gate: live screenshot per item; `node --check`; the engine selftest extended where maths changed.

**Done 2026-09-16 (§37).** Each item carried a live reading. Ghosts: `math.peakAlpha` tracks the cell's
density bucket — 252 painted cells span 0.867–0.920 over 6 distinct peaks (was: one), and a controlled
pull left a wall's ghost at 0.920 against a mid cell's 0.871; five selftest checks. Imbalance glow: a
third of the POC's radius, in the imbalance colour — 27 glowed cells at blur 3.0 against the POC's 7.2,
matrix still readable. Zone projection: stronger bands plus a deduped right-edge label
("SELL 4L projected", painted on every base pass). `carry_forward`: on the engine's state and in the
panel's own note, measured by flipping `atlas.heatmap.carry_forward` (note: the hub reads the ATLAS
subtree, not the top-level `heatmap` block the store's defaults also declare). Hidden blocks: the count
sits beside the min-block field — empty at floor 0, "nothing hidden" at floor 5 with nothing below it,
warning-coloured with "N hidden" when it is hiding executions.

**P1-6 · Heatmap answers duration, not only size (brief E).** M
Surface `wall_age` / `wall_durations()` (backend-side, already built) as a held-time column in the readout
and walls table, an optional wall-age tint, and the 74/22 px plot insets promoted to one shared constant
read by both the map and the overlay. Gate: live — a level held ≥ 2 min shows its age; an alert created
from that level fires at that level only, then is deleted.

**Done 2026-09-16 (§38).** `attach_wall_ages()` joins `wall_prices` with `wall_durations()`: each wall
the map draws carries `held_ms`, and `wall_age_ms` travels with it. The Held column, the cursor line
(`held 1.2 min`, `(wall)` past the threshold) and an optional age tint (0 below the threshold → 0.22 at
10 min, warm so it cannot read as density) all read that shape, and the 74/22 px insets are now
`HEAT_INSET` in `atlas.js`, read by the overlay instead of repeated. Two `window.prompt` sites in the
alert path became fields (an empty field means the default — found live, an empty field had produced
`at_tol: 0`). Live: real holds of 1.3/1.7 min rendered in the table; a 5-minute hold tinted its own row
`rgb(255,193,117)` while six rows away stayed black; the hold-alert created from a level carries
`at_price`/`at_tol`/`min_age_s` and the UI channel, and its scope is enforced by the evaluator and
pinned in `test_wall_age.py`. A live 2-minute hold was caught by a 20 s poller — the engine's own
`wall_age` event at 76800.0, `held 2.4 min` — with two honest notes: the payload's event list keeps the
last 120 events, so that event rolls out of it within a couple of minutes; and the Held column covers
the 12 heaviest walls, so a held level outside that set shows its age in the event list rather than the
table. The level-bound rule did not fire for that unrelated event (the "at that level only" half) and
was deleted (16 rules, no `hm-` left); its own firing at its own level was not observed while it
existed. Three `window.prompt` sites remain outside this phase
(`drawings.js:365,417`, `menubar.js:557`), open.

**P1-7 · Alerts: manage, scope, and read like sentences (brief F).** M
Rule editor (kind, threshold, level scope, hold time, channels, cooldown) in the UI; every rule rendered
with its scope in words; a "created from heatmap" filter; the log naming symbol, level, size and why.
Gate: live — edit a rule, fire it, read it in the log naming the level, delete it.

**Recon done 2026-09-16 (§39), read-only — the next session starts from this.**
Exists: the Alerts view (`index.html:522`, rendered by `atlas.js` ~534-590 + `atlas-v2.js`'s history
card), four real routes (`GET /alerts`, `POST /alerts/clear`, `GET /alert-rules`, `POST` upsert +
`DELETE /alert-rules/{id}`), the engine's `AlertRule`/`Alert` records and a per-kind `_message()`.
Kinds offered to the editor (16 + `wall_age`): `big_trade, block_trade, sweep, stop_run, iceberg,
speed_spike, cvd_divergence, heat_pull, heat_stack, vwap_cross, depth_execution, depth_refill,
stacked_imbalance, intent_pressure, pulled_size, trapped_traders`. Params the evaluator reads:
`min_multiple, sides, min_size, min_levels, min_ticks, min_fills, min_zscore, kinds, min_strength,
min_share, min_volume, min_pct, max_distance_ticks, min_beyond_ticks` plus the generic `at_price` /
`at_tol` / `min_age_s`.
Defects to fix in this phase: `alClear` claims a clear it never sends; rules are edited as raw JSON in a
text input; no level/hold/channel editor, no heatmap filter, and no Level/Size in the log although the
payload carries both.
Decisions taken (do not re-open): a pure `alert-format.js` (global `OFAPALERTS`) as the single source
for `kindLabel`/`paramSpec`/`sentence`/`scopeWords`/`why`, read by both the editor's fields and the
rendered sentence; keep On + Fired; an inline Edit row instead of the JSON cell; channels as
checkboxes (the route already carries them, and only opted-in rules reach the webhook); a filter with an
honest count line; Level/Size columns from `data.price`/`data.size` with `—` where a kind has none.
Gates: `alert-format.selftest.js` + `test_alert_format.py` (the `test_strips.py` pattern) and
`alert-format.js` registered in `scripts/audit_ui_refs.py`.

**P1-8 · Bar/candle expression modes and accessible palettes (brief D).** M
The five modes (delta-tinted candles, split candle, heat-gradient body, wick-only + footprint, plus the
current default), per-chart persistence, colour-blind-safe ramps independent of the theme, and a legend
that names the encoding actually in use. Norm: colour must never be the sole carrier of a sign (canon #5,
§3.3). Gate: each mode on live data + one colour-blind palette; legend text matches the drawing.

**P1-9 · Keyboard-first completion (canon #7).** S–M
One shortcut map with scopes: palette, freeze, view switch, zoom, selection clear, replay seek, export,
alert-from-cursor; discoverable in-app; never fires inside a text field. Gate: live pass — every action
reachable with no mouse; a text field swallows none of them.

**P1-10 · Freshness declared on every panel (canon #8).** M
Show the age of what is displayed (depth 5 s / quote 60 s windows; `age_known:false` when the clock is
unknown) and make a panel visibly stale-out instead of freezing. Gate: live — stop the feed, watch panels
age and say so; restart, watch recovery.

### P2 — performance, only where measured

**P2-1 · Index the hover path (fixes report1 §3.2-1 and §1.3 of this plan).** S–M
Build `printsByBar` in `setData()`; index heat cells by column (or reuse the visible-column search);
maintain CVD incrementally. Gate: a measurement on a 10 k-print tape — mousemove cost before/after, and
`ofx.stats()` p95 unchanged or better under the standard synthetic load.

**P2-2 · Engine next round — sweep R6.** M
Incremental heat decay, `Float32Array` heat wire format, hover coalesced into the rAF tick. Gate: p95 must
improve on today's numbers (heat 3.58 ms / live 1.34 ms) under the same synthetic load.

**P2-3 · Heat-layer yielding — conditional.** S
Render heat in one rAF and base+live in the next *only if* a 30 k-cell / 4K measurement crosses the 16 ms
frame budget. Norm: defer complexity behind a measurement (§3.8). Gate: the measurement itself.

### P3 — hygiene, backend, packaging, deferred

**P3-1 · WebGL for the heat layer only — deferred with a trigger.** L (when triggered)
Trigger, per brief §6: > ~2 k simultaneous cells or a forced 4K/144 Hz use case. Keep the coordinate
matrix; port only `drawHeat()` to a point-sprite mesh. report1 agrees ("defer until there's an actual perf
complaint").

**P3-2 · Session model (R4) and storage retention (R5).** M
`session_date` is UTC-today with a rolling 24 h profile (`main.py:682-690`), so "today's" value area mixes
sessions at the UTC boundary; make the boundary a config value and compute profiles per session. Retention:
no pruning exists — 5.8 M rows / 547 MB and ~4.5 M rows/day; add an age/size retention job with incremental
vacuum and surface the DB size in Logs. Gate: unit tests on the session-window function; run retention, read
row counts and file size before/after.

**P3-3 · Legacy dashboard page decision (R7).** S (decision) + M (whatever it implies)
`dashboard/static/app.js` polls REST at 1 s/5 s and rewrites whole series per tick — the same page that
loads `footprint.js`, which report1 wanted deleted. Decide: retire the page (desktop UI supersedes it) or
give it the tape's incremental treatment. Gate: the page either 404s in the desktop shell's nav or its poll
cadence drops to a documented number. This decision also closes report1 §5.2's "two footprint
implementations" and "two heatmap implementations" concerns.

**P3-4 · Packaging and first-run (brief H).** L
`onedir` build with icon (wire `scripts/make_icon.py` into `build_exe.py`), version resource, no console
window; NSIS/Inno installer to Program Files plus a per-user portable variant, uninstaller, jump list,
remembered window geometry/monitor, taskbar progress while the engine starts; first run = the existing
Express/Professional wizard with the theme applied. `dist/` predates the last fixes (built Sep 15 23:37) —
rebuild when this lands. Gate: launch the frozen exe from a clean path on a clean port; bootstrap 200;
engine streaming; theme applied.

**P3-5 · Replay parity (brief G).** L
`orderflow_system/atlas/replay.py` exists; there is no desktop UI path. One rendering path for live and
replay (never a second renderer), replay honours theme, cursor link, strips, modes and highlights; "send
region to replay" from any selection; a window with no recorded ticks says so. Gate: show the call path
(same functions), not just the screen.

**P3-6 · Harden the DTC test flake (handoff §4.4).** S
It muddies every gate run. Gate: N consecutive green runs.

**P3-7 · Reconcile the agent brief with reality.** S
`AI_AGENT_BUILD_PROMPT.md` §1/§8 still describe a 297-test baseline (today 483) and predate workstream I
and the commit series. Refresh it, and link this plan from `RESUME.md` so the next session starts from the
true state.

---

## 3. The design principles the ordering follows

1. **Truth before polish.** A number the user reads must be true, fresh and internally consistent: stale
   books (P0-4), contradictory counters (P0-3), invisible absence (P0-1/2) rank above every new visual.
   *Nielsen #1 (visibility of system status), #9 (help users recover); canon #8, #10; brief non-negotiables #1, #8.*
2. **Tokens before paint.** Theme/token layer (P1-1) lands before any colour work, so every later colour
   cites a token and consistency is enforced by a grep, not by discipline. *Nielsen #4 (consistency and
   standards); the owner's Windows/Material reference.*
3. **Accent is only an accent if it is scarce.** Desaturated baseline (candles, bars, grid); saturated
   colour reserved for signals; no sign carried by hue alone — pair with weight, glyph or bar. *Brief §3.1,
   canon #5.*
4. **Recognition over recall.** Linked cursor, badges, scope-in-words alerts, legends naming the encoding,
   the readout panel that spells out what the cursor is standing on. *Nielsen #6; canon #1.*
5. **Protect the user's place and flow.** The intent arbiter defers rather than drops; strips hold scroll;
   keyboard-first with discoverable shortcuts; expert accelerators (click-to-locate, fit-session
   double-click). *Nielsen #7 (flexibility and efficiency); handoff §1's arbiter contract.*
6. **Nothing degrades silently.** Filters say what they hid; ghosts and carry-forward say why; a panel with
   no data says which condition is missing; a stale panel visibly stales out. *Canon #8, #10; brief §7
   ("do not hide a failure behind a spinner, a zero or a plausible default").*
7. **Progressive disclosure.** The Express/Professional wizard pattern generalised: new controls sit beside
   the thing they change, show their current value, and persist per panel — no settings sprawl. *Nielsen #7;
   handoff §1's wizard.*
8. **Defer complexity behind a measured trigger.** WebGL (P3-1), heat yielding (P2-3) and heat-wire formats
   wait for a number that demands them. *Brief §6's revisit conditions.*
9. **Windows-native idiom.** Segoe UI Variable, tabular numerals (a running price must not shift digits —
   correctness, not taste), 4/8/12 px gutters, near-zero radius, almost no elevation, one shadow level for
   genuinely floating surfaces. *Brief §3.1, read from the owner's reference image.*
10. **Evidence gates.** Every item ends in a command whose output is the proof; unproven items are reported
    as unproven in the same breath as the proven ones. *Brief non-negotiable #1; handoff §2's
    verified/unverified split.*

---

## 4. Sequence, dependencies, and the phase gates

**Phase 0 — trust pass (P0-1 … P0-6).** **Done 2026-09-16 — see handoff §32.** No dependency on anything else. Ends when: the three visuals are
seen or their defects named, the watchlist and bus readouts are re-checked live, R2/R3 carry their tests,
and `grep -ri hermes` over source is zero — with the full gate block green.

**Phase 1 — tokens, then the spine (P1-1 → P1-2, P1-4).** P1-1 first (its grep gate is cheap and it
unblocks every colour decision). P1-2 and P1-4 can run in parallel afterwards. Ends with: the token grep at
zero, light/dark screenshots at two sizes, and one live pass showing a single hover lighting four panels.

**Phase 2 — expression and measurement (P1-3, P1-5 … P1-10).** Everything here reads tokens and the cursor
spine. Ends with: live evidence per item (mode switching with a matching legend, alert lifecycle, selection
export on disk, freshness ageing on a stopped feed).

**Phase 3 — performance (P2-1 … P2-3).** Only after Phase 2 stops moving the same files; P2-1 is small and
pays for itself immediately. Ends with: before/after numbers on the same load.

**Phase 4 — backend, packaging, documentation (P3-1 … P3-7).** R5 before any long soak (the DB grows
~4.5 M rows/day); R4 with its tests; R7's decision unlocks or retires the legacy page; H last so the
installer freezes the finished surface; G after the spine so replay inherits it.

**At every phase gate:** full pytest, the audit, `node --check` on every touched JS, the affected
selftests, and the browser evidence. If a gate is red, stop at that workstream — do not stack work on a
broken foundation (brief §5).

---

## 5. What not to do

- Do not rebuild the engine. `ofx.js` is the engine and report1's §7 agrees; the work is at the edges.
- Do not add a framework, bundler or build step to the front end — the app ships as files.
- Do not rename payload fields or config keys (the golden config stays green); add, don't rename.
- Do not introduce a second rendering path for replay, and do not let a panel draw without registering
  with `OFAPScale`.
- Do not delete `dashboard/static/footprint.js` (or `heatmap-pro.js`) before R7's decision — both are live
  code paths today.
- Do not port WebGL without the trigger conditions being met and measured.
- Do not touch `.env`, `auth.json`, `keys.db`, `Username.txt`, `Accounts*.config` — vendor keys are entered
  only inside the app's Connections panel.
- Keep committing in area-grouped batches, local only; the remote/fork remains the owner's call.

---

## 6. Evidence appendix — every claim in §1, and how to re-run the gates

Greps run while writing this plan (all against HEAD `bcb94ea`, tree clean):

```
index.html        :230 #ofxLambda · :232 #ofxMinBlock · :233 #ofxVaPct · :234 #ofxRamp
                  :236 #ofxSnap (live chip) · :247 #ofxTip · :248 #ofxSnapFloat + #ofxSpark2
                  :250 #ofxReadout · :764 /static/footprint.js  (the legacy chart, still loaded)
ofx-view.js :265 paintChip (shows #ofxSnapFloat only in historical mode)
            :277 paintSpark (last 60 closes) · :320 paintReadout (full metric set)
            :401 paintTip · :492 onHover → paintTip+paintReadout · :519-520 snap handlers
            :444-473 wireCursorLink (ladder row highlight + outside-ladder note)
ofx.js      :1150 cell.peak = max(peak, alpha) · :1156 decayAlpha(cell.peak)
            :1754 hover() · :1763 CVD sum from 0 · :1774 full heat scan · :1778-1781 all-prints loop
atlas.css   :79 .ofx-readout · :99 .ofx-tip · :103-111 .ofx-snap-float (+reduced-motion)
            `grep -c -- '--of-' atlas.css` → 0  (no token layer yet; no themes/ directory)
api.py      :1525 the one `hermes` mention in source (non-negotiable #7)
```

Gate block for the next session (copy-paste):

```bash
cd /c/Users/Moddy/OrderFlow-Analysis-Pro && unset PYTHONPATH
.venv/Scripts/python.exe -m pytest orderflow_system -q            # 483 passed / 2 skipped
.venv/Scripts/python.exe scripts/audit_ui_refs.py                 # AUDIT CLEAN
for t in ofx shell bus links watchlist news options fundamentals market-pressure intent study-api search-ops; do
  node orderflow_system/desktop/ui/$t.selftest.js | tail -1
done
```

Live evidence, per `RESUME.md`: sandbox with a redirected `APPDATA` on ports 8090–8094, CDP at
`http://127.0.0.1:809x/desktop/`, then stop every process and check `orderflow.log` for `client error:`.

**State to carry forward:** `master` is committed and clean, nothing pushed; `origin` is the original
author's repository, so a fork/remote for Moddy remains a one-command decision when he asks.
