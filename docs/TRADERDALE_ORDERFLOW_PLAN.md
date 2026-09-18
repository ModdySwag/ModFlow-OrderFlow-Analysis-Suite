# Trader Dale's order-flow guides — study, assessment against this build, and the fold-in plan

**Status:** Phases 1–5 **EXECUTED** (approved 2026-09-18 — "go with everything"; receipts in `docs/SESSION_HANDOFF.md` §104–§107). Only Phase 6 (packaging, on his word) remains; every §8 decision was taken as recommended. Written 2026-09-18 after Moddy's brief ("read the article and its
linked articles, collate, assess against ModFlow OrderFlow Analysis Suite, and gather the
feature-enhancing conclusions — additions, upgrades, and any 'golden feature' that sets it above
the market"). **Phases 1–5 are built on disk** (status line above; receipts in §104–§107) —
this document's phase table (§6) is now a completed record, with only Phase 6 (packaging, on his
word) outstanding, and §2's two-column table is the record of what was already shipped before
any of it.

**How claims are made here.** Every "already in the build" claim carries a `file:line` cite from
this tree. Every "not in the build" claim is a repo-wide grep from this pass; §9 lists the exact
patterns so they can be re-run. The course's own software is described only from the articles
actually read; promotional or video-only pages are listed as not read rather than guessed at.

**Sources read 2026-09-18:**
- Beginners Guide to Order Flow, Parts 1–4 — `trader-dale.com/beginners-guide-to-order-flow-part-1-what-is-order-flow/` … `-2-special-features/` … `-3-trading-strategies/` … `-4-platform-data-instruments/`
- Beginners Guide to Volume Profile Parts 1–2 + the POC bonus guide (`how-to-trade-the-point-of-control-poc/`)
- Beginners Guide to VWAP Parts 1–2
- *Not read, deliberately:* VP Part 3 / VWAP Part 3 (purchase-and-setup pages), the webinar/video
  links, and "Complete guide to reversal trades" (video-only — its rules exist only in the video).
- App-side evidence: `docs/ux-study/modflow_inventory.md` (the measured surface inventory), then
  direct reads: `analytics/footprint.py`, `atlas/imbalance.py`, `atlas/profiles.py`,
  `atlas/scanner.py`, `atlas/vwap.py`, `atlas/dots.py`, `atlas/api.py`, `signals/profile_framing.py`,
  `signals/aggregator.py`, `desktop/api.py:1075-1091`, `desktop/ui/atlas.js`, `alert-format.js`,
  `help-data.js`, `guide.js`, `README.md` (bias table), `docs/FLOWSURFACE_FOLD_IN_PLAN.md` (house
  precedent for this document's shape).

---

## 0. The honest summary

1. **The build already does most of what the course's software advertises — and in several places
   does more.** Footprint with per-bar POC, same-price *and diagonal* imbalances, equal-side and
   min/max reads; live stacked-imbalance clusters; level-scoped alerts; virgin POCs; single prints;
   VWAP with ±kσ deviation bands; a ranked multi-instrument scanner. The course's "special
   features" list maps almost 1:1 onto shipped modules (§2 is the anti-duplication table).

2. **Seven things in the guides are genuinely not here** — chief among them *Unfinished Business*
   as a live drawn read, *multiple-HVN / node persistence*, and *volume profile over an arbitrary
   selection* ("Flexible Volume Profile", the course's most-used tool). §3.

3. **The golden opportunity is not another indicator — it is the level lifecycle.** The app's
   Fabio state machine (`signals/aggregator.py:5-13`: WATCHING → ABSORPTION_DETECTED →
   POSITION_OPEN → BREAK_EVEN → TRAILING → CLOSED) already watches qualified levels and enters on
   absorption at them. What neither this build nor (as far as the guides show) the course's
   software does, is treat **every level from every source** as a tracked object whose state
   (armed → price approaching → defended/confirmed → spent/failed) is visible across the whole
   watchlist in plain sentences. That is the "above the competition" fold (§4, G1), and it is
   composed almost entirely of parts this build already ships.

4. **Everything folds in additively**: new modules behind config flags, the existing renderers
   extended (no second renderer), the existing alert / sentence / help machinery reused. Phases
   and gates in §6; nothing committed without his word.

---

## 1. What the source teaches (the collated picture)

### 1.1 Order Flow Parts 1–2 — the interface and its special reads

- Footprint cells = traded volume per price per bar. Ask side = aggressive buys, bid side =
  aggressive sells. A cell is green when ask > bid, red when bid > ask.
- **High Volume Node** per bar = the heaviest-volume price. **Multiple HVNs meeting at the same
  price in consecutive bars ("Double/Triple Node") are auto-highlighted — strong support/
  resistance**.
- Delta under each bar; a configurable footprint summary (the author uses Delta / CVD / Volume).
- Daily Volume Profile beside the tape (bid/ask colouring) for the bigger picture.
- Forex caveat: FX feeds without bid/ask give volume-only cells (shading) and disable some reads.
- Special features: imbalance (ask ≫ bid → blue, and vice versa); stacked imbalances (3+ levels)
  auto-highlighted; **Unfinished Business / Failed Auction** — a properly auctioned high needs 0
  traded on the bid and a proper low needs 0 on the ask; a turn without that is an imperfection
  the market tends to revisit — auto-detected, a line drawn **until price revisits and fixes it**;
  a **Trades Filter** (show only trades above X lots — "the big guys"); Cumulative Delta as a
  bonus indicator, watched especially for price × delta divergences at S/R.

### 1.2 Part 3 — the strategies (the playbook layer)

- **Volume Cluster setup**: heavy-volume area formed in a trend or a rejection → price leaves one
  or two footprints → pullback to the cluster → enter at its start/heaviest point, with the trend.
- **Trades Filter setup**: same structure, zones built from the biggest prints (min lot size set
  by the trader).
- **Confirmations at a level found by a primary method** (for the author: Volume Profile):
  – *Limit-order confirmation*: a big limit sell appears on **ask** at resistance / a big limit buy
  on **bid** at support (the opposite side convention to market orders). It can take minutes to
  print in full.
  – *Absorption confirmation*: unusually heavy volume on **both** sides at the level = pressure
  absorbed → likely turn.
- Level discipline: "I only trade a level once" — second tests have a lower win rate (stated in
  the POC guide too).

### 1.3 Part 4 — platform & data

- The course runs on NinjaTrader 8 (free tier) with a broker demo feed (FXCM), analysis in NT8,
  execution at the broker. Instruments: currency futures, indices, metals, oil, stocks; forex
  possible with the volume-only caveat. Centralised futures data is called the best case.

### 1.4 Volume Profile guides + POC bonus

- Volume-at-price vs time-based volume; heavy zones = where institutions positioned; thin zones
  = fast movement.
- **Profile shapes** as direction context: D (balance), P (buyers in control), b (sellers), thin/I
  (trend).
- **POC**: heaviest-volume level; drawn per timeframe (daily/weekly/monthly/yearly); **POC
  confluence across timeframes is the strongest level**; trade the pullback in the direction price
  left the POC; **first test only**; a failed POC suggests a reversal trade (video-only detail).
- Setups: **Volume Accumulation** (rotation → heavy-volume line → enter on first touch) and
  **Trend setup** (a volume cluster inside a trend = the line). **Flexible Volume Profile** =
  profile any area you select, not fixed to a time period.

### 1.5 VWAP guide

- VWAP = fair value / magnet. The traded tool is the **1st (and 2nd) deviation bands (±kσ)**:
  sideways bands = rotation → trade band edges back toward VWAP; vertical bands = trend → trade
  pullbacks to the band; VWAP line as take-profit.
- **VWAP + Volume Profile confluence** (both pointing at the same level) = the strongest setups.

### 1.6 The cross-cutting reads worth automating (synthesis)

1. Auction completeness is exact and computable (0 on one side of an extreme row) — perfect for a
   detector with an auto-clear.
2. Persistence is a property of *levels over bars* (double/triple nodes) — a level-lifecycle
   problem, not a bar problem.
3. The first test carries the edge; repeat tests are worse — a per-level **touch state** is worth
   tracking.
4. A confirmation only counts **at a level you chose** — the app already scopes alerts to levels;
   the gap is making the lifecycle visible.
5. Confluence (two independent level sources agreeing) is treated as a stronger level — and is
   computable.

---

## 2. Feature-by-feature — the guides vs this build (the two-column check)

Verdicts: **MATCH** = shipped; **EXCEEDS** = shipped and beyond what the articles show;
**PARTIAL** = machinery exists, the user-facing read does not; **ABSENT** = not in the build.

| # | Capability (from the guides) | This build today (cite) | Verdict |
|---|---|---|---|
| 1 | Footprint matrix, bid×ask per price | Engine view `ofx.js`; legacy footprint; numbers-bars analysis pack `analytics/footprint.py:6-11` | MATCH |
| 2 | Green/red cells (side dominance) | `analyse_levels` returns `dominant` (`footprint.py:161`); bar expression modes (`expression.js`) | MATCH |
| 3 | Per-bar delta & totals | `footprint.py:151-152`; Engine readout | MATCH |
| 4 | High Volume Node per bar | bar POC = max-volume row, with share % & delta (`footprint.py:168-175`); readout shows POC price + share | MATCH |
| 5 | Multiple HVN (Double/Triple Node) auto-highlight | nothing — grep §9 #2 | ABSENT |
| 6 | Same-price imbalance | `footprint.py:52-98`, `analyse_levels` imbalance rows; imbalance glow; Trackers "Imbalance ladder" | MATCH |
| 7 | Diagonal imbalance | `imbalance_levels(mode="diagonal")` — the articles only show single-cell | EXCEEDS |
| 8 | Stacked imbalances auto-highlight | live clusters `atlas/imbalance.py:13,213-235` + fresh-cluster event; Trackers "Stacked imbalances"; `stacked_imbalance` alert kind | MATCH |
| 9 | Unfinished Business — auto-detect + line until revisited | ABSENT as a drawing/alert. Its own docstring claims "unfinished auction levels" (`footprint.py:4`) but the file implements none — the claim is ahead of the code. `atlas/profiles.py:181-183` single prints are a TPO cousin (shown as a count, `atlas.js:511`); `profile_framing.py:204-213` "hooks" are daily-bias notes only | ABSENT |
| 10 | Trades Filter (min size) | print-size filter at aggregation `footprint.py:239-246` + settings route `desktop/api.py:1075-1091`; tape big-print floor `param_registry.py:197`; audio min-size `audio.js`; Big trades + Big-trade zones trackers | MATCH (deliberately build-time — see §5) |
| 11 | Volume clusters / density shading | ramps + LOD ladder; dots cluster map with `min_size` drop `atlas/dots.py:2-29` | MATCH |
| 12 | Limit-order confirmation at a level | walls / iceberg / `depth_refill` events; alerts scoped to a level via `at_price`/`at_tol`/`min_age_s` (§38/§40 receipts); editor `alert-format.js` | MATCH |
| 13 | Absorption confirmation at a level | `patterns/absorption.py`; `absorption` alert; Strategy view card | MATCH |
| 14 | CVD + price×delta divergence | CVD view ("CVD vs price", "Divergences"); `cvd_divergence` alert kind; `analytics/delta.py` | MATCH |
| 15 | Forex / volume-only handling | venue capability system + degrade-out-loud canon; no named volume-only footprint mode | PARTIAL |
| 16 | POC per timeframe (D/W/M/Y) + confluence | session/developing profiles + virgin POCs (`atlas/profiles.py`, `atlas/api.py:194-205`); nothing weekly/monthly; no confluence | PARTIAL |
| 17 | First-test-only discipline / spent levels | virgin POCs identify untested levels (`profiles.py:243-248`) but there is no touch counter / spent state | PARTIAL |
| 18 | Flexible VP (profile any selected area) | selection gives statistics incl. VWAP (`math.selectionStats`) but no VP-over-selection anywhere | ABSENT |
| 19 | Profile shapes (D/P/b/thin) as a named read | classifier exists — P/b/D/double → daily bias (`profile_framing.py:130-141`), wired to signals (`main.py:317-319`) and Telegram (`telegram_bot.py:149`); not surfaced on the Profile view | PARTIAL |
| 20 | VWAP + ±kσ deviation bands | `atlas/vwap.py:1-11` (session + anchored + bands); chip `ui/vwap.js:87`; `vwap_cross` alert; `param_registry.py:261` | MATCH |
| 21 | VWAP rotation/trend reads + VP confluence | bands exist; slope-based rotation/trend label and confluence-with-profile detector not found | PARTIAL |
| 22 | Platform/data model (NT8 + demo feed) | build is its own platform, keyless-first free feeds; NT8 optional bridge; MT5 ships; Platforms view documents external plans | N/A (build ahead — no NT8 requirement, no data subscription) |

---

## 3. The conclusions — additions and upgrades

### 3.1 Additions (not in the build at all)

**A1 · Unfinished Business, live.** At bar close, compute completeness of the bar's extreme rows:
a bar high whose row carries only ask-side volume, and a bar low whose row carries only bid-side
volume, are *complete*; a turn away without that is *unfinished*. Store as magnet levels, project
a line, **auto-clear when price trades through**, emit a new `unfinished_business` alert kind with
a sentence from the existing formatter. Where: new pure module in `atlas/` + feed from the
footprint engine + Engine-view overlay + alert kind + Settings toggle. Effort **M**.
Risk **low-medium** (new overlay on the busiest view — behind a toggle; no feed or page change).

**A2 · Node persistence (double/triple HVN).** Per bar take the max-volume row (exists: POC); a
price that is the max-volume row within half-tick tolerance across N consecutive bars accumulates
a node-strength N. Draw the band at N ≥ 2 ("double"), N ≥ 3 ("triple"); rank by strength; alert on
touch of an N ≥ 2 node. Feeds the Radar (A5/G1). Effort **S-M**. Risk **low** (pure arithmetic,
new layer).

**A3 · Area Volume Profile ("Flexible VP").** Reuse the existing selection (shift+drag on the
engine; drag-select on the heatmap) → compute volume-at-price over the region → histogram in the
selection float + POC/VAH/VAL lines on the stage + a **"Watch this level"** button that creates a
level-scoped alert. Also serves the Trend setup (select the trend leg; its cluster is the line)
and the Accumulation setup (select the rotation; its heavy line). Effort **M-L**. Risk **medium**
(touches selection + a new overlay; the maths is a pinned pure function).

**A4 · HTF POC ladder + confluence.** Aggregate stored session profiles into week/month POC
(pure function over existing data) and, where the history allows, quarter/year; highlight where
≥ 2 POCs coincide within tolerance as "POC confluence"; list on the Profile view; feed levels to
the Radar. Effort **S-M**. Risk **low**.

**A5 · Level confluence detector.** Given the level sources the app already computes (POC/VAH/VAL,
virgin POC, node band, VWAP bands, heatmap walls, big-trade zones, dots clusters), score overlaps
within k·tick tolerance; show a confluence badge on the level + optional stronger alert. Effort
**S-M**. Risk **low** (pure function over already-computed levels).

**A6 · VWAP deviation surfaces.** (a) band-touch alert kind (side-aware); (b) a slope-based
rotation/trend label for the 1st-deviation pair (horizontal vs vertical over a window); (c)
confluence with profile levels = A5 instance. Effort **S-M**. Risk **low** (bands already
computed in `atlas/vwap.py`).

**A7 · Volume-only mode.** When the active feed carries no side, the Engine renders single-sided
cells with the density ramp and prints one honest note naming the feed's limitation; imbalance
controls grey out with their reason (the existing capability-greying pattern). Effort **S-M**.
Risk **low**.

### 3.2 Upgrades (exist — make them reach the trader)

**U1 · Surface the profile-shape read.** Profile view badge (D / P / b / thin via the existing
classifier) + one-sentence story + a help topic; pin that the shape's words match the engine's
classification. Effort **S**. Risk **low**.

**U2 · POC/level touch lifecycle.** Extend virgin detection into a per-level state: untested →
touched-once → spent. Persist across sessions (the `markers` store is the precedent), dim spent
levels, and offer "stop alerting a spent level". Effort **M**. Risk **low-medium** (persistence +
UI).

**U3 · Widen the state machine's level sources.** Feed nodes, unfinished-business magnets,
virgin-POC levels and area-POC levels into the existing WATCHING pathway
(`aggregator.py` flow :49-56) so the machine's net widens beyond profile qualifiers. This is the
Radar's engine side (§4, G1). Effort **M**. Risk **medium** (touches the signal flow; behind
config; pinned by replay-driven tests).

**U4 · Education layer.** Help topics for the reading order (profile decisions first → order-flow
confirmations at chosen levels; the limit-vs-market ASK/BID side convention; first-test
discipline) + one Guide step pointing at the playbook features. Effort **S**. Risk **none** (the
help corpus is data; the coverage test enforces the wiring).

---

## 4. The golden features (why these set it above the competition)

**G1 · Level Radar — the level lifecycle, watchlist-wide.** A first-class level registry: every
level from every source (POC/Virgin POC/HTF POC, node bands, stacked-imbalance zones, big-trade
zones, unfinished-business magnets, VWAP bands, area-profile POCs, heatmap walls) becomes a
tracked object with state — *armed → approaching → defended / confirmed → spent / failed* — and
expiry/dedup rules. Surfaces: a Radar column ranking instruments by "what is arming where" (the
`atlas/scanner.py` table is the natural host), the Signals view, and alerts phrased like sentences
through the existing `alert-format.js` machinery, with help links to the methodology topics.
*Why golden:* the compared tools (our own `docs/ux-study/*` studies) alert on events; Bookmap is
event-centric heatmap; Sierra/DTC-style numbers-bar studies are configuration-heavy and paid;
none of them tracks **level lifecycles across the watchlist with plain sentences and in-app
education**. It also composes ~80% shipped parts (scanner, alert scoping, state machine sents.,
sentence engine) — the fold is mostly the registry + states + surfaces.

**G2 · Unfinished Business live layer (A1).** A futures-grade precision read (rare outside pro
numbers-bars toolchains) computed live on every feed this app carries — crypto, FX (with the
volume caveat stated), equities. It draws, alerts, and clears itself; it pairs naturally with
absorption confirmation at the magnet. Nothing in the compared retail platforms surfaces it.

**G3 · Area Volume Profile (A3).** The course's most-used tool, made interactive: drag a region →
profile + POC/VA lines → one-gesture "watch this level". Uniquely natural here because selection,
cursor-link, profile maths and level-scoped alerts already exist; the gesture-to-alert hand-off is
the loop no compared platform closes.

Ordering reality: G1's inputs are A1/A2/A4/A5 — which is why they are Phase 1.

---

## 5. What we deliberately do not take

- **NT8 / FXCM / any paid-data dependency.** The build stays keyless-first; NT8 remains the
  optional bridge it already is (`references/ninjatrader-bridge.md`).
- **Vendor text, screenshots, palettes, trade dress.** Concepts and standard auction arithmetic
  only — the same function-level-rebuild discipline already applied to the numbers-bars pack
  (`footprint.py:6-11`). Node highlight uses the token amber, not literal yellow.
- **Display-time trade filtering that would make a bar's totals lie.** The build-time filter is
  the honest design (`footprint.py:239-246`) and stays; big prints are *highlighted* elsewhere
  (tape floor, trackers), never silently dropped from a bar.
- **A second renderer, a framework, or a build step.** Overlays extend the existing layers.
- **Re-building shipped items** — footprints, imbalances, stacked clusters, alert scoping, CVD
  divergence, VWAP bands. §2 is the anti-duplication record.
- **A futures-only pivot.** The suite stays multi-venue, free-data-first.

---

## 6. Phases and gates

| Phase | Content | Effort | Gate |
|---|---|---|---|
| **0 — this plan** | The doc; no code | — | his approval |
| **1 — detectors (pure, pinned)** | A1 unfinished-business core; A2 node persistence; A4 HTF POC; A5 confluence core; U1 shape-words. New `atlas/` modules + `node` selftests | 1-2 days | full pytest (1354/2 at last save) + AUDIT CLEAN + ruff 0.16.7 + every selftest + goldens untouched |
| **2 — surfaces v1** | Engine overlays (A1 lines, A2 bands, A5 badges); alert kinds + sentences; Profile view U1 + U2 states; Scanner columns | 1-2 days | live sandbox pass (scratch `APPDATA`, 809x, CDP, cache disabled), zero `client error:`; §-record |
| **3 — Area Volume Profile (G3)** | A3 selection → VP maths + overlay + Watch-this-level hand-off | 2-3 days | pure-function pins; live selection on the engine; export includes the area profile; hand-off fires a level-scoped alert |
| **4 — Level Radar (G1)** | Level registry + state transitions + scanner/Radar surface + sentences + expiry/dedup; U3 feed | 3-5 days | replay-driven transition tests; live pass; sentences pinned by `test_alert_format`-style test |
| **5 — education + polish** | U4 help topics + guide step; screenshots; docs | 1 day | help coverage test; docs regenerated |
| **6 — release (only on his word)** | dist/zip/SBOM/installer rebuild | — | the standing acceptance battery |

---

## 7. Ranked action table

| Candidate | Value | Effort | Risk | Phase |
|---|---|---|---|---|
| A1 Unfinished Business live module | High | M | Low-Med | 1-2 |
| A2 Node persistence (double/triple HVN) | High | S-M | Low | 1-2 |
| G1 Level Radar (state machine extension) | **Highest (golden)** | L | Med | 4 |
| A3 Area Volume Profile (golden) | **High (golden)** | M-L | Med | 3 |
| A4 HTF POC ladder + confluence | Med-High | S-M | Low | 1-2 |
| A5 Level confluence detector | Med-High | S-M | Low | 1-2 |
| U2 POC/level touch lifecycle | Med | M | Low-Med | 2 |
| U1 Profile-shape surfaced | Med | S | Low | 1-2 |
| A6 VWAP deviation surfaces | Med | S-M | Low | 2 |
| U3 Widen state-machine level sources | High (part of G1) | M | Med | 4 |
| A7 Volume-only mode | Med | S-M | Low | 2 |
| U4 Education topics + guide step | Med | S | None | 5 |

---

## 8. Decisions I need from you

1. **Phase order** — detectors → surfaces → Area VP → Radar (recommended), or Radar first?
2. **Unfinished-business overlay default** — on (recommended; it draws nothing when the condition
   is absent), or off until seen live?
3. **Node highlight colour** — token amber (recommended, theme law) or literal yellow?
4. **Spent levels** — dim + label (recommended), or remove once spent?
5. **Let node/unfinished/area-POC levels join the existing WATCHING state** — yes (recommended,
   behind config), or keep the machine's level sources as-is for now?
6. **Radar surface** — start as a Scanner column + Signals feed (recommended), promote to its own
   view later behind a gate?
7. **In-app naming** — generic ("level playbook"), vendor names kept out of the UI (recommended;
   matches the numbers-bars rebuild precedent)?

---

## 9. Evidence appendix (re-runnable)

Absence greps used in this pass (run from the repo root):

1. `grep -rin "unfinished" orderflow_system` → 3 files only: `analytics/footprint.py` (docstring),
   `atlas/profiles.py` (single-print comment), `desktop/ui/guide.js` (cosmetic wizard text).
2. `grep -rinE "HVN|high volume node|double node|triple node|volume cluster" .` → **0**.
3. `grep -rinE "\bnodes?\b|hvn" orderflow_system/atlas/profiles.py` → **0**.
4. `grep -rin "playbook" .` → **0**.
5. `grep -rinE "weekly|monthly" orderflow_system` → calendar ("weekly feed"), platforms
   (NT8 plans), storage/demo strings — no weekly/monthly **profile** aggregation anywhere.
6. `grep -rinE "auction" orderflow_system` → initiative-auction detector + profile-framing hooks +
   legacy microstructure label — no unfinished-auction module, overlay, or alert.

The already-here side: cites in §2; the measured surface inventory is
`docs/ux-study/modflow_inventory.md`; the level-scoped-alert receipts are §38/§40 of
`docs/SESSION_HANDOFF.md` (as recorded in `docs/UPGRADE_ACTION_PLAN.md` §P1-6/P1-7).
