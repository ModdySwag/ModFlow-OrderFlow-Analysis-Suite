# ModFlow OrderFlow Analysis Suite — code audit + desktop GUI feasibility study

Study performed on a Windows 11 box against commit `b2ff4ee` of
`github.com/mahmoud20138/OrderFlow-Analysis-Pro` (cloned 2026-09-14).
Everything below was executed, not inferred: commands, exit codes and API
payloads are reproduced from the actual run.

Deliverable of the exercise: a **working desktop GUI prototype** for Windows and
macOS in `orderflow_system/desktop/` (see §5), plus this audit of what the code
actually does today.

---

## 1. Verdict

| Question | Answer |
|---|---|
| Can a modern, clean GUI front this codebase? | **Yes** — the backend is already an async Python service with a FastAPI + WebSocket API, which is the hard part. |
| Can it cover *all* the program's functions? | **Yes for the analyst features**, with ~10 endpoints/behaviours that need real wiring first (§4). Three endpoints currently return fake data in live mode. |
| Windows? | **Yes, proven** — native app launched, drove the engine, streamed live BTCUSDT data. |
| macOS? | **Yes for the app shell and the analytics**, but **not for the MetaTrader 5 feed**: `MetaTrader5` publishes `win_amd64` wheels only. On macOS the usable live feed is Bybit — which, as shipped, is misconfigured and delivers **zero** data (§4.1). |
| Effort | The prototype below (config store, engine controller, control API, 11-view UI, module skin — 2,703 lines) is one working day. Turning it into a shippable app is roughly 3–5 days of focused work, dominated by the data-layer fixes in §4, not by UI. |

---

## 2. What the code is

```
orderflow_system/                     8,183 lines of Python (~12k claimed in README)
├── main.py                    666    orchestrator: pipelines, feeds, periodic tasks
├── config/settings.py         946    all configuration — hardcoded dataclasses
├── data/                             mt5_feed (495) · bybit_feed (209) · candle_builder (133)
│                                     database (278) · models (290)
├── analytics/                        volume_profile (258) · delta (197) · footprint (181) · orderbook (208)
├── patterns/                         absorption (257) · exhaustion (228) · divergence (159) · sweep (142) · initiative (133)
├── signals/                          aggregator state machine (516) · profile_framing (343)
├── alerts/telegram_bot.py     202
├── dashboard/                 1,237  FastAPI app (1,015) + ws manager (186) + 9 static frontend files
└── test_integration.py        314    7 unit tests
```

Runtime shape: one asyncio process — data feed → candle builder → analytics →
5 pattern detectors → profile framing → aggregator state machine → Telegram +
FastAPI/WebSocket dashboard. SQLite (WAL) behind it. No CLI arguments, no env
vars, no config file: `config/settings.py` **is** the configuration surface.

---

## 3. What I actually ran (evidence)

| Test | Command | Result |
|---|---|---|
| Unit/integration tests | `pytest orderflow_system/test_integration.py -v` | **7 passed** in 0.11 s (the 2 async tests do run: `@pytest.mark.asyncio` is present) |
| Demo dashboard | `python -m orderflow_system.dashboard` | Serves `/` + 15 REST endpoints, all 200 with payloads (candles 173 KB, footprint 240 KB) |
| Demo dashboard in a browser | screenshots + DOM checks | Chart (the chart library lightweight-charts) renders, scanner lists 29 instruments, VP lines + markers drawn |
| Live feed, valid symbol | custom harness: `OrderflowSystem(instruments=[get_btcusd_config()], data_source=BYBIT)` | 348 ticks in 70 s, candles closing, `cum_delta` updating, dashboard API live |
| Live feed, repo default symbols | probe against `wss://stream.bybit.com/v5/public/linear` | **0 data messages** — server returns `error:handler not found,topic:publicTrade.NAS100USDT` |
| A/B on the same socket | valid-only batch vs valid+invalid batch | valid-only: 34 msgs/10 s · mixed: **0 msgs/10 s** — one bad symbol kills the whole subscribe |
| Default entry point | `python -m orderflow_system.main` (MT5 default) | MT5 import fails, all 31 instruments log `price=0.00` forever, dashboard binds `0.0.0.0:8080` |
| Packaging | `pip install -e .` and `uv pip install -e .` | **Both fail**: `BackendUnavailable: Cannot import 'setuptools.backends._legacy'` |
| Platform wheels | PyPI JSON for `MetaTrader5` | `cp310..cp314-win_amd64` — **no macOS/Linux wheel exists** |
| Prototype GUI, Windows | `python -m orderflow_system.desktop` | Native 1500×940 window ("ModFlow OrderFlow Analysis Suite"), engine started from the UI, live BTCUSDT (price/ticks/candles/delta), trade phase `watching` |

Live-session totals from the prototype run: **19,054 ticks, 12 candles, 2 signals,
1 volume profile, 3 qualified levels** with no crash over ~10 minutes.

---

## 4. Defects that block "a smooth GUI over all functions"

Ordered by how badly they hurt. Each one was reproduced.

### 4.1 The Bybit feed delivers no data (severity: critical)
`main.py:284` builds `BybitFeed(symbols=list(self.pipelines.keys()))` — the
*internal* names (`NAS100USDT`, `XAUUSDT`, `EURUSD`, …). Bybit perpetual topics
are `publicTrade.BTCUSDT` etc.; every non-crypto name is rejected, and because
Bybit fails the **whole** subscribe request, even `BTCUSDT` gets nothing.
Effect: the README's "Quick Start (Bybit — No Account Needed)" yields a
dashboard that never updates. Fix: a per-instrument `bybit_symbol` map, only
subscribe validated symbols, and surface the server's `success:false` reply.

### 4.2 Candle persistence + WebSocket candle/delta broadcasts are dead code (severity: critical)
`OrderflowSystem._on_candle_close_handler` (`main.py:460`) is the only place
that writes candles to SQLite and broadcasts `candle`/`delta` — and **nothing
ever calls it** (`CandleBuilder.on_candle_close` points at
`InstrumentPipeline._on_candle_close`). Chain of consequences in every live run:

1. `candles` table stays empty → 2. `_rebuild_volume_profile` requires ≥10
candles from the DB → 3. no volume profile → 4. no daily bias → 5. no qualified
levels → 6. the aggregator never enters `WATCHING` → 7. **no entry signal can
ever fire**, and the dashboard's chart only ever sees candles via REST polling,
never pushed.

Measured before/after wiring the missing call: `candles: 0`
→ `candles: 12, profiles: 1, bias: neutral, qualified_levels: 3, watching: 2`.

### 4.3 Three endpoints serve demo data while trading live (severity: high)
`/api/footprint/{symbol}` (app.py:899/903), `/api/tape/{symbol}` (911–913) and
`/api/microstructure/{symbol}` (921–923) return `demo_data.*` even when the
system is running — two of them marked `# TODO`. Footprint and tape are exactly
the two panels an orderflow trader stares at, so "the GUI shows numbers" is not
the same as "the GUI shows the market". The prototype labels these panels as
demo-fed rather than hiding it.

### 4.4 Six of nine frontend modules are never loaded (severity: high)
`index.html` includes only `app.js`. `footprint.js`, `orderbook.js`, `tape.js`,
`signals.js`, `performance.js`, `microstructure.js` (~2,250 lines) are shipped
but unreferenced — and **223 of the CSS classes they emit are absent from
`style.css`**, so they would render as unstyled HTML even if loaded. Re-enabling
them therefore means wiring them *and* writing their stylesheet (the prototype
does both: see `desktop/ui/modules.css`).

### 4.5 No runtime configuration, no CLI (severity: high for a GUI product)
Data source, MT5 credentials, Telegram token, thresholds, ports and the
instrument list are Python literals in `config/settings.py`; changing anything
means editing source and restarting. A GUI needs a settings store (prototype:
JSON in the per-user config directory, with clamping so a bad value can't kill
the engine).

### 4.6 MT5 is a Windows-only dependency (severity: high for the macOS goal)
`pip install MetaTrader5` is Windows-only (§3). On macOS the MT5 feed is
impossible, so the "both platforms" goal is really "shared app + analytics,
different feeds": MT5 on Windows, Bybit (crypto only) elsewhere. A broker-API
or data-vendor feed (OANDA/Polygon/Databento/Twelve Data) is the only route to
indices/FX on macOS — that is new code, not a port.

### 4.7 Packaging is broken (severity: medium)
`pyproject.toml` declares `build-backend = "setuptools.backends._legacy:_Backend"`,
which does not exist → `pip install -e .` fails on pip *and* uv. The dependency
list also omits **fastapi** and **uvicorn**, which the dashboard imports
unconditionally, so even a successful install cannot start the dashboard.
Fix: `build-backend = "setuptools.build_meta"` + add both deps (+ `pywebview`
for the GUI).

### 4.8 `/api/markers/{symbol}` always 500s in live mode (severity: medium)
`dashboard/app.py:256` references `Side` in a live-mode branch but the module
only imports `TradePhase`, so every call raises
`NameError: name 'Side' is not defined` → HTTP 500. The marker layer (signal
arrows on the chart) therefore never renders in a live session; the stock
frontend swallows the error. One-line fix: import `Side` from
`orderflow_system.data.models`. Reproduced from the server traceback during the
prototype run.

### 4.9 Smaller, still user-visible (severity: low/medium)
- `/api/candles` reads only the in-memory 5,000-candle deque — after a restart
  the chart is empty even though the DB has history.
- Volume profile is rebuilt only hourly, so a fresh session shows no bias for up
  to 60 minutes (prototype adds an on-demand "Rebuild profile" action).
- The dashboard binds `0.0.0.0` by default — a local trading terminal exposing
  the engine on the LAN; the prototype pins `127.0.0.1`.
- Working directory matters: `DB_PATH = "orderflow_data.db"` and the log file
  are relative, so where you launch from changes where data lands.
- Instrument config carries per-instrument thresholds for 31 instruments; only
  ~10 of them are reachable on the Bybit path, and no crypto other than BTCUSDT
  is even defined in `settings.py` — the GUI must own the instrument list.

---

## 5. The prototype (`orderflow_system/desktop/`)

A desktop shell that starts the existing FastAPI app in-process, adds a control
API, and renders the repo's own UI modules in a new shell. Nothing in the
original files was modified; all additions are new modules.

```
orderflow_system/desktop/
├── config_store.py    per-user JSON config (Windows %APPDATA%, macOS
│                      ~/Library/Application Support), clamping + deep merge
├── engine.py          EngineController: build OrderflowSystem from JSON config,
│                      start/stop/restart, capability discovery (MT5 presence,
│                      Bybit symbol validation), candle-persistence fix
├── api.py             /api/control/*: bootstrap, config get/set/reset,
│                      engine start/stop/restart/status, datasources,
│                      telegram test, log tail, profile rebuild/status
├── logs.py            ring buffer + rotating file handler for the GUI log view
├── launcher.py        uvicorn in a worker thread + pywebview window on the main
│                      thread (required by macOS Cocoa); --browser / --headless
│                      fallbacks
├── __main__.py        `python -m orderflow_system.desktop`
└── ui/
    ├── index.html     11 views: Overview, Chart, Order Flow, Depth, Tape,
    │                  Signals, Strategy, Performance, Instruments, Settings, Logs
    ├── ui.css         shell design system (dark tokens, rail, cards, KPI, forms)
    ├── modules.css    skin for the repo's 223 orphaned module classes
    ├── ui.js          state, REST + WebSocket client, module wiring, settings forms
    └── vendor/lightweight-charts.js   vendored chart lib (no CDN needed offline)
```

Run it (any OS with the deps installed):

```bash
python -m orderflow_system.desktop              # native window
python -m orderflow_system.desktop --browser    # default browser instead
python -m orderflow_system.desktop --headless   # server only (CI/smoke tests)
```

### Screenshots of the running prototype

| File (in `docs/screenshots/`) | Shows |
|---|---|
| `desktop-overview-live.png` | native window, Overview: BTCUSDT 77694.70, 1,838 ticks, cum Δ 7.87, trade phase `watching`, engine Running |
| `desktop-live-session.png` | native window, earlier live session (price/ticks/delta updating, Stop engine visible) |
| `desktop-chart.png` | native window, Chart view: candles + delta histogram, POC/VAH/VAL lines |
| `desktop-chart-value-area.png` | browser render of the same view with POC 77480.00 and the honest note that `/api/markers` errors in live mode |

### What is verified working

- Native 1500×940 window on Windows (pywebview → WebView2), screenshot attached
  to the session; window title "ModFlow OrderFlow Analysis Suite".
- Engine start/stop/restart from the GUI: started Bybit BTCUSDT, streamed
  19,054 ticks, 12 candles, 2 signals; status pill, KPIs and session summary all
  update live.
- Settings round-trip: JSON config written atomically, reloaded, clamped; the
  engine picks up data source / instrument / threshold changes on restart
  without touching Python source.
- Instrument coverage view that knows what each feed can actually serve (greys
  out indices/FX under Bybit, disables MT5 entirely on non-Windows) — this is
  what stops the silent zero-data trap of §4.1.
- All 11 views render with no JS console errors; the repo's own footprint,
  order book ladder, tape, signal cards, performance dashboard and
  microstructure panel are instantiated and fed from the live API.
- On-demand volume-profile rebuild: returned `candles: 12 → profiles: 1`,
  bias `neutral`, 3 qualified levels, `watching: 2` — the state machine came
  alive only because the missing candle handler (§4.2) was wired.
- Log view tails both the in-memory ring buffer and the rotating log file.
- Deep links (`--view chart` or `#depth`) and a `/desktop` no-cache header so the
  webview never shows a stale build; the UI also re-pulls every panel the moment
  the engine starts, so demo numbers never linger on screen after start-up.
- `python -m orderflow_system.desktop --headless` (used for all automated checks)
  and `--browser` fallbacks, so the same build runs with or without a GUI stack.

### Honest limitations of the prototype

- Footprint / tape-fill / microstructure panels are wired but their upstream
  endpoints still return demo data in live mode (§4.3) — the UI says so.
- Performance/journal view derives rows from the signal feed; a real trade
  journal needs the aggregator's closed trades persisted (small task).
- pywebview window exited once by itself mid-test on this machine and behaved
  normally on relaunch — treat WebView2 lifecycle as something to retest during
  packaging, not as a known bug.
- macOS was **not** executed here (no Mac available). Evidence for macOS is:
  every Python dependency is platform-neutral except MetaTrader5 (which is
  Windows-only by publisher), pywebview ships a pure-Python wheel and uses
  WKWebView on macOS, the launcher keeps the GUI on the main thread as macOS
  requires, and nothing in the codebase imports a Windows-only API
  (`sys.platform` is checked once, for signal handlers).
- Telegram self-test exists but was not exercised (no bot token).

---

## 6. Cross-platform matrix

| Capability | Windows | macOS |
|---|---|---|
| Desktop window (pywebview) | ✅ WebView2 | ✅ WKWebView (untested here) |
| Analytics engines, patterns, state machine | ✅ | ✅ pure Python |
| Dashboard + control API + UI | ✅ | ✅ |
| Bybit feed | ✅ (after §4.1 fix + valid symbols) | ✅ same |
| MT5 feed | ✅ (needs terminal + Windows wheels) | ❌ impossible |
| Indices / FX / metals live data | ✅ via MT5 | ❌ needs a new feed (vendor API) |
| Telegram alerts | ✅ | ✅ |
| Packaging | PyInstaller `--windowed` | py2app / pywebview bundle |

---

## 7. Recommended order of work

1. **Fix the data layer first** (§4.1, §4.2) — without these the GUI is a
   beautiful window onto nothing. Both are small, surgical changes.
2. Wire the three demo-only endpoints (§4.3) to the pipeline buffers
   (`/api/tape` from the feed's tick buffer, `/api/microstructure` from the
   detectors' state, `/api/footprint` from `FootprintEngine.history`).
3. Persist closed trades so the performance view is real.
4. Fix packaging (§4.7) and pin the dashboard to `127.0.0.1` by default.
5. Ship the desktop shell (`pyproject` extra `gui = ["pywebview"]`, a
   `orderflow-desktop` entry point, PyInstaller spec for Windows, py2app or a
   `.app` wrapper for macOS).
6. Only then consider a richer UI (multi-instrument grid, alert rules editor,
   drawing tools) — the current prototype already covers the existing feature
   surface.

---

*Prototype code, audit notes and test harnesses live in the working copy at
the project directory (scratch probes under `.scratch/`).*

---

## 8. Update — the reference layout feature layer (2026-09-14)

A follow-up pass added the reference-style analysis surface on top of this desktop
shell: `orderflow_system/atlas/` (market-depth heatmap, tape-flow trackers, CVD,
TPO profile, non-time frames, replay, alert rules) plus eight new UI views and a
tuning card in Settings. Nothing in the upstream pipeline was modified — the
layer wraps the system's own callbacks and mounts its own router.

Details, the feature-by-feature the reference layout comparison and the verification evidence:
**`docs/the reference layout_COMPARISON.md`**. Screenshots: `docs/screenshots/atlas-*.png` and
`desktop-window-*.png`.

## 9. Update — end-user onboarding (2026-09-15)

The install now stands on its own for someone who has never seen the repo.

- **`docs/USER_GUIDE.md`** — what the program is, install, first run, every view,
  alerts, Telegram (optional and free), data/privacy, troubleshooting.
- **Setup assistant** (`orderflow_system/desktop/ui/guide.js`) — six steps on first
  launch (Welcome → data source → instruments → feeds/history → alerts → finish,
  with "start the engine now"). Re-openable from the **Guide** view. Reads live
  venue data, so it can import instruments and their tick sizes from Bybit's public
  `instruments-info` endpoint — no key, no account.
- **Guide view** — the reference inside the app, including a "run setup again"
  button and the no-account statement.
- **Tooltips** — every nav entry, button, input and table control carries a hover
  explanation (104 applied at last count), re-applied to anything rendered later.
- **18 crypto majors out of the box** — `settings.py`'s instrument enum and
  `get_all_configs()` now include the Bybit majors, tagged `Crypto` in
  `config_store`, so a fresh config can stream BTC/ETH/SOL… with one tick.
  Verified live: BTCUSDT + ETHUSDT + SOLUSDT streaming, zero skipped.
- **Durable history retention** — `atlas/history.py` prunes events older than
  `retention_days` (default 7) so a long-running install cannot grow the DB forever.
- **`scripts/audit_ui_refs.py`** — end-of-build check that every API path the UI
  calls resolves to a real route and every element id the modules use exists.
  Current: 62 routes, 112 ids, 0 missing, 0 duplicate ids.

## 10. Update — free integrations + guided first run (2026-09-15)

Everything below is optional, free, and keyless-or-account-free. The app's core still needs nothing:
public Bybit data + local SQLite.

- **`atlas/notify.py` grows three channels** next to Telegram: **ntfy** (phone push with *no account
  at all* — a topic name is the whole setup), **email** (any SMTP mailbox; app password for
  Gmail/Outlook) and the existing **webhook** now persists and is settable from Setup. One
  `NotifierHub` fans an alert out per rule; a channel without credentials simply is not built, so a
  fresh install is UI-only and silent, never broken.
- **`atlas/context.py`** — free market context: venue funding rate / next funding / open interest /
  24h turnover / long-short account ratio, alternative.me Fear & Greed, and RSS headlines
  (CoinDesk / Cointelegraph / Decrypt or a user feed). Every source TTL-cached, every source fails
  soft, all in worker threads.
- **Endpoints**: `GET /api/atlas/context/{symbol}`, `GET /api/atlas/notify/status`,
  `POST /api/atlas/notify/test` (one-shot field overrides so the wizard can test *before* saving).
- **UI**: a Market-context card on the Overview (funding/OI/long-short/F&G + headlines, 60 s refresh),
  four-channel routing per rule in the Alerts view, and Setup steps for channels (with Test buttons)
  and context. Finishing Setup also routes the externally-alerting rules to whatever channels were
  configured — a channel nobody routes to is a channel that never fires.
- **Verified live**: funding 0.0035 % / OI 53.9k / L-S 1.38 / F&G 57 / 8 headlines with 0 failures;
  a real ntfy push read back from ntfy.sh's API; a real webhook POST captured by a local receiver;
  and a full pipeline run — live ETH big-trade, BTC block-trade and ETH sweep detections arrived on
  ntfy with the right priorities (urgent/high/default). Email delivery is unit-tested through an
  injected transport; a live send needs a real mailbox.
- **Break found and fixed by that run**: the hub's dispatch gate tested for the literal channel name
  `telegram`, so a ntfy-only or email-only setup sent nothing at all. It now fires whenever any
  non-UI channel is requested and lets the hub decide which are live.

## 11. Update — the reference layout SDK documentation pass (2026-09-15)

Source: `docs.atas.net` (the custom-indicator/strategy manual) plus the help-site
index. Full write-up in **`docs/the reference layout_SDK_NOTES.md`**; scenarios in
**`docs/USE_CASES.md`**. What came out of it:

- **A measured performance pass.** The manual's per-event rules (avoid allocations,
  do not recompute what has not changed, budget the render) exposed 99% of our ingest
  cost in one class: `statistics.mean/pstdev` per tick, a 4,000-print quantile sort
  per tick, and a full-ring rescan per tick for stop runs.
  **935 → 7,774 ticks/s** through the five-analyser stack (128.6 µs/tick), all tests
  green. Benchmarks: `scripts/bench_atlas.py`, `scripts/profile_atlas.py`.
- **Version-stamped heatmap payloads** (their front/back buffer + Version idea):
  `snapshot()` caches against `(version, cols, rows)` — a cached poll is 0.3 µs
  against 0.76 ms to build — and the payload now carries `version` + `cached`.
- **A repaint governor** in the UI (their "RedrawChart() sparingly"): identical
  payloads skip the canvas repaint entirely and repaints are coalesced to a 400 ms
  frame budget, with counters on the canvas tooltip. Verified live: identical
  payloads produced skips, not repaints.
- **Market pressure panel** (their `HeatmapMarketPressureIndicator`): paired buy/sell
  per bucket with a delta line, window totals and share-of-volume, on the CVD view.
- **Deliberately out of scope**, now documented rather than implied: order/position
  management, the account statistics provider, and compiled indicator distribution —
  this program stays read-only and key-free.

New in the UI: the Guide view lists the nine scenarios; the CVD view carries the
Market pressure card. Nothing in this pass touched the upstream pipeline.


## 12. Participants' intent — reading the book before the chart (build log)

Requested from the reference layout video *what order flow analysis reveals*: GUI functions that
read order-book participants' intentions **before** the move shows up on the chart.
The video's toolset is the Smart DOM ladder plus the Liquidity Pressure widget; the
help site documents both well enough to reimplement the observable behaviour.

New: `orderflow_system/atlas/intent.py` (`ParticipantIntent`), endpoint
`/api/atlas/intent/{symbol}`, GUI card `desktop/ui/intent.js` on the Overview, and
three alert rules (`intent_pressure`, `pulled_size`, `trapped_traders`).

**Bugs found and fixed while verifying against live Bybit data** — each was silent,
which is the only interesting thing about them:

1. **Non-clock timestamps.** The deeper book feed puts Bybit's update id (`u`) in the
   snapshot timestamp, and stamps snapshots in *seconds*, while the trade feed uses
   milliseconds. Comparing them made the book look decades old, so every print was
   classified "stale book" and the tape-quality panel read all zeros while looking
   healthy. Fixed with a normaliser that converts seconds and *rejects* anything that
   cannot be a 2020-or-later epoch.
2. **A max that only ever grew.** The normalisation maximum was never recomputed, so
   one spike pinned the scale low for the rest of the session (readings of 1-2% of
   normal). Now a genuine sliding window, as the help site describes.
3. **Alerts on the first observation.** With no history, the first book is by
   definition 100% of its own normal — the card alerted immediately. A 30-update
   floor now applies on top of the training period.
4. **Absorption scored its strongest case as zero.** Aggression that gets pushed
   *back* scored 0 because the formula only rewarded "price did not move". Now split
   into failure-to-follow and adverse-move terms, so the worst case for the aggressor
   reads as the strongest signal for the absorber.
5. **ntfy rate limits (HTTP 429).** Push bursts hit the free-tier limit and every
   message after that failed. The channel now widens its own throttle on a 429 and
   narrows it again once messages get through.

Verification: 100 tests pass (11 new for this layer: decay weighting, training and
observation gating, sliding-window normalisation, pulled-size with and without
traded volume, trapped-side detection, absorption scoring, tape classification with
fresh and stale books, timestamp normalisation, ntfy back-off). The weighting was
re-checked against an independent recomputation from the live ladder — exact match to
six decimals. GUI verified in a real browser against live data: card renders, verdict
line populated, pulled-size and trapped rows listed, zero JS errors.


## 13. MetaTrader 5 setup assistance (build log)

The data-source step already offered MT5, but nothing told the user it existed, nothing walked them
through it, and the wizard never collected the settings the feed actually reads (`mt5.path/login/
server/password` + per-instrument `mt5_symbol`). Three additions, all additive:

1. **An install-time notice.** On first start (and any start until dismissed) a dialog announces the
   optional source, says whether this machine is ready for it, and offers the walkthrough. "Later"
   and the ✕ keep it coming back; only "Don't show again" retires it — the flag is `mt5.notice_seen`
   in the config file.
2. **A step-by-step walkthrough** (`Guide → Setup how-tos`, and from the wizard) covering broker
   terminal install, login, the Python bridge, optional path/login/server, broker symbol mapping and
   a live test. Seven steps, with copyable commands.
3. **A MetaTrader step in the wizard** (inserted after Data source, shown only when MT5/Both is
   chosen) that collects the path/login/server/password, maps every enabled instrument to its broker
   symbol, and tests the connection. Sibling steps gained their own walkthrough buttons: instruments,
   extras, phone push, Telegram, email, webhook, market context.

**Backend:** new `POST /api/control/mt5/test` → `engine.mt5_probe()`, which reports one honest stage
at a time (platform → package → terminal → ready), returns the terminal/build/company plus
login/server/currency/leverage (deliberately no account-holder name), checks which mapped symbols the
broker lists, and always shuts the bridge down again. The password is used and never echoed back.

**Traps hit and fixed:**

- **Pip is not universal.** This repo's venv is uv-built and has no `pip` module — the "pip install
  MetaTrader5" advice in the README and the walkthrough would fail on the very machine the app is
  installed on. The probe now checks `importlib.util.find_spec("pip")` and returns the command that
  fits the environment (`python -m pip install …` or `uv pip install --python … …`).
- **A capability probe that only checks the package lies by omission.** `mt5_status()` said
  "available" the moment the wheel was installed, while the terminal was absent. The two are now
  separate calls: cheap package detection for the capability banner, and a real connect-test for the
  user. Verified live on this machine: package `metatrader5==5.0.6180` installed, probe stops at
  `stage: terminal` with MetaTrader's own `-10003 IPC initialize failed, MetaTrader 5 x64 not found`.
- **JS string escaping.** The venv path needs exactly two backslashes in source to display one; a
  doubled pair renders a path nobody can paste. Verified by reading `textContent` back out of the DOM.

Tests: 5 new (four probe stages incl. a stubbed terminal for success/refusal/no-account, plus the
environment-appropriate install command). Total 105 passing. GUI verified in a real browser: notice,
walkthrough, wizard step (both variants), per-step help buttons, live bridge test, zero JS errors.


## 14. A persistent setup-state button in the nav rail

Requested follow-up: the assistant should be one click away from anywhere, and its state should be
visible without opening it.

- The button is injected as the **first** `.nav-item` in the rail (above Overview), so it inherits the
  existing nav styling and sits where a new user looks first.
- State is a saved config flag, `setup_complete`, written by the wizard's own "Next/Finish" path —
  **not** by Skip or by closing the dialog. The colour therefore means "the walkthrough was completed",
  which is the honest reading; a skipped wizard would have shown green while nothing was chosen.
  The wrapper sets the flag on `GUIDE.cfg` *before* the original `finishWizard()` performs its save,
  so it lands in the same POST as the rest of the settings — no second write, no race.
- Amber (`rgba(232,190,84,0.10)` wash + a 3px inset edge + an 8px dot) for incomplete, green
  (`rgba(88,200,130,…)`) once finished; both hover states lighten instead of flashing.
- `refreshSetupButton()` runs on mount, after the wizard closes, and on an 8 s interval, so a change
  made anywhere (or a config edit) shows up without a reload. Tooltips differ per state.
- Verified in a live browser: mounted first in the rail, amber with the right tint/dot/tooltip, click
  opens the wizard, and a real Finish persisted `setup_complete: true` to the config file with the
  button flipping to green — then the flag was removed again so the user sees the amber state and the
  transition for himself.


## 15. Program-wide search, and a privacy scrub (build log)

**Search (`ui/search.js`).** A Ctrl+K box in the rail that indexes the live program rather than a
hard-coded list: views (from the rail), panels (a curated table), actions (engine control, wizard,
profiles, VWAP anchor, credential clear, export), settings (every labelled control, discovered at
search time with its view), select options (so "renko"/"15m"/"delta" find their control), alert kinds
and rules, help walkthroughs, guide sections and instruments. Results are grouped, ranked by a simple
token score, keyboard-driven (↑ ↓ Enter Esc), and every row carries a hover tooltip with the full
description. `/` focuses it too, and every dropdown option in the app gained a `title` explaining it.

**Privacy scrub.** The config held a mailbox address in three fields plus its password and a
name-bearing ntfy topic. All of it is gone: the identity fields are blank, the channel is disabled
until credentials are re-entered, the ntfy topic is neutral, and the repo/docs/temp-scratch/DB were
scanned for identifiers (name, hostname, user paths, provider, email, password pattern) — the DB hits
were coincidental digits inside trade-id UUIDs, verified individually. The search box carries a
one-click **Clear stored alert credentials** action so this is repeatable without hand-editing files.

**The failure worth recording:** the scrub replaced a provider example with text containing an
apostrophe *inside a single-quoted JS string*, which made the browser drop the entire guide module —
no error, no console message, the Guide view and the wizard simply did not exist. Two fixes: (1) the
loader now installs a capture-phase `window` error listener that surfaces "module error in <file>" in
the app's log view and as a toast; (2) `scripts/audit_ui_refs.py` gained a **JS syntax gate**
(`node --check` over every front-end module) as step 5, so this class of breakage fails the audit
instead of hiding. Both were added because the bug was only visible by diffing the rendered DOM.


## 16. Steady — refreshes that never fight the user

The complaint: a poll lands mid-edit, the panel rebuilds, a toggle flips back, the screen redraws while
a menu or config form is open. Fixing it properly meant finding *every* refresh path, not just the
noisy one. Sixteen polled renders exist across the app (the repo's `refreshSlowPanels`, per-view
loaders, the Logs tail, and this session's six card refreshers), driven by five intervals plus the
status poll.

`ui/steady.js` wraps each of them (24 functions, wrapped by name whether or not they exist yet, and
re-checked as late-defined modules appear) with one decision function, in this order:

1. a dialog is open → skip;
2. the user is editing inside the container that render would replace → skip;
3. that container holds a field changed in the last 30 s → skip (unsaved input is never discarded);
4. the pointer is down or a key was pressed in the last 4 s → skip;
5. otherwise render — and restore focus, caret and every scroll position afterwards (twice for async
   loaders, since they rebuild after the `await`, which is where focus was really being lost).

A bottom-right badge says "updates paused while you work" whenever the guard is holding something back,
with counters in its tooltip, so the behaviour is visible rather than mysterious.

Verified in a live browser against real poll cycles:

| Check | Result |
|---|---|
| type into a settings field, wait 15 s through several polls | value `STEADY-TEXT-1` intact, focus intact, 35 renders held back |
| same field, unguarded rebuild (the old behaviour) | value wiped to `""` |
| flip an instrument toggle, wait 13 s | still as flipped, element not replaced |
| leave it alone for 12 s | renders resume (allowed 64 → 84): the app is not frozen, just polite |
| dialog open (wizard) for 12 s | background renders skipped, step and inputs untouched |


## 17. Alpaca Markets — account linking (build log)

Requested: analyse alpaca.markets for a free account, plan how it folds into this program, and add a
simple account section that links the user's account. Deliverable: a deep plan
(`docs/ALPACA_INTEGRATION_PLAN.md`) **plus** the working Phase 0 so the plan is not just prose.

Built: `desktop/alpaca.py` (dependency-free client, staged probe, capability report, positions/orders/
portfolio read, 150/min self-limiter under Alpaca's 200/min), five `/api/control/alpaca/*` endpoints,
the `alpaca` config block, `ui/alpaca.js` (account card with capability table and honesty notes),
a six-step help walkthrough, a wizard step that points at the single form (no duplicated key fields to
drift out of sync), and search entries.

Verified against Alpaca's real servers, not mocks:

| Check | Result |
|---|---|
| keyless crypto history (`/v1beta3/crypto/us/bars`) | HTTP 200, real BTC/USD bars |
| news without keys | HTTP 401 — confirms it is entitlement-gated |
| invalid key pair → `probe()` | Alpaca's own 401 mapped to `stage: auth` naming the paper/live mismatch |
| same through the HTTP endpoint | identical answer, key masked as `PKTE…00 (19 chars)` |
| card in the live app | renders with status pill, 3 fields, 4 buttons, 8 tooltips, Adds / Cannot-add table |
| account form → real API call | returns the environment hint, no JS errors |

Two implementation notes worth keeping: the probe tests the free plan's SIP window by requesting bars
that *end* 20 minutes ago (that distinguishes "no SIP" from "SIP with a 15-minute delay", which is the
honest description of the free tier), and the capability report states the absence of order-book depth
in the same list as the features — Alpaca cannot feed a heatmap, and the UI says so rather than leaving
the user to wonder.
