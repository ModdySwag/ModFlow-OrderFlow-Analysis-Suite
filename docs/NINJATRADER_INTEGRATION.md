# NinjaTrader 8 integration — the ModFlow bridge and the feed (§84)

*Built 2026-09-18. Nothing committed; HEAD `110c568`. Vendors' prices read 2026-09-18 from
ninjatrader.com.*

NinjaTrader publishes **no market-data-out API** — the same situation as Bookmap, and the same
answer: the suite ships a small **read-only bridge add-on** that runs inside the platform, subscribes
to NinjaTrader's own market-data callbacks, and republishes them on loopback. Unlike Bookmap, the
NinjaTrader stream is also a **full engine data source**: add `NQ` (or `NQ1`, or `MNQ 12-26`) from
the terminal's own instrument list and it streams into every panel through the same engines as the
built-in feeds.

---

## 1. The shape of it

```
 NinjaTrader 8 (running, logged in)                 The suite
 ┌─────────────────────────────────┐               ┌──────────────────────────────────┐
 │  market data  ─┐                │               │  data/ninjatrader_feed.py        │
 │  (quotes,      ├─► ModFlowBridge├── 127.0.0.1 ──►│    NinjaTraderFeed (FeedSession) │
 │  trades, L2)   │   .dll (AddOn) │   :8790       │  engine DataSource.NINJATRADER   │
 │  instruments ──┘   NUL-JSON     │               │  tape · footprint · delta · DOM  │
 └─────────────────────────────────┘               └──────────────────────────────────┘
```

| Half | Lives here | Built with |
|------|-----------|------------|
| Bridge add-on | `orderflow_system/data/ninjatrader_bridge/` (DLL + C# source + `build.ps1` + README) | `dotnet build` against NinjaTrader's own assemblies — no Visual Studio needed |
| Feed adapter | `orderflow_system/data/ninjatrader_feed.py` | Python; talks the wire below |
| Platform card | `orderflow_system/desktop/platforms.py` (+ api + `ui/platforms.js`) | plans/tiers, workflow, install detection, DLL state, live test |

The DLL shipped in the repo was compiled against NinjaTrader **8.1.8.2** (Roslyn, `net48`, x64).
NinjaTrader assemblies are not strong-named, so the DLL binds by simple name and keeps working
across 8.x builds as long as the documented API surface exists.

---

## 2. What each side gives you — free tier, demo, funded, paid

The platform itself is free on every plan; what a plan changes is the per-contract commission.
(Figures read from the vendor's pages on 2026-09-18; the Platforms card carries the same numbers
with links.)

| Level | Cost | What it gives the integration |
|-------|------|-------------------------------|
| **Free plan** | $0 | Full platform + unlimited simulation. The **Simulated Data Feed** streams synthetic but complete quotes, trades and depth — ideal to verify this path. 14-day real-time trial when an account opens. Commissions $0.39/micro · $1.29/standard per side. |
| **Kinetick End-Of-Day** | free | Daily data only — not a live stream. |
| **Funded brokerage account** | (funding) | **Complimentary real-time CME & EUREX Level I while funded** on any plan, plus complimentary Order Flow+ and TradingView. This is the honest route to live futures data. |
| **Monthly plan** | $99/mo | Lower commissions ($0.29/$0.99). |
| **Lifetime plan** | $1,499 once | Lowest commissions ($0.09/$0.59) + **Order Flow+ included**. |
| **Order Flow+** | $59/mo standalone | NinjaTrader's own order-flow chart tools. **The suite does not need it** — footprint/delta/heat are computed from the raw trades + depth the bridge republishes. |
| **Level II depth** | depends on data subscription | The bridge streams whatever depth the platform receives; the card and `Test connection` **report what actually arrived** instead of promising a ladder. |

Notes that bite: the platform asks you to **log in on every start** (closing the login window exits
it); the Free plan carries an **inactivity fee** (one round turn per month waives it); exchange,
clearing and NFA fees apply on every plan.

---

## 3. Installing the bridge (the one-time step)

For the *user*: the suite walks through it (setup assistant ▸ Data source, Platforms ▸ NinjaTrader
card, Help ▸ “NinjaTrader 8 in this program”). The short version:

1. Copy the bridge source (`orderflow_system/data/ninjatrader_bridge/src/ModFlowBridge.cs`,
   `ModFlowJson.cs`, `ModFlowProbe.cs`) into `Documents\NinjaTrader 8\bin\Custom\AddOns\`
   (create `AddOns` if missing).
2. In NinjaTrader open **New ▸ NinjaScript Editor** and press **F5**. On the first compile the
   platform asks *"…has detected new add-on(s)… trusted sources?"* — answer **Yes**.
3. The bridge loads as soon as the compile finishes; the platform's **Log** tab shows
   `[ModFlow Bridge] listening on 127.0.0.1:8790`. No restart needed.

Diagnostics the bridge writes:

| File | What it is |
|------|------------|
| `%LOCALAPPDATA%\ModFlow\ntbridge.log` | every bind, accept, subscribe, disconnect the bridge performs |
| `%LOCALAPPDATA%\ModFlow\ntbridge-probe.log` | the probe companion: platform facts (assemblies, accounts, instrument look-ups) dumped at every start; **if this file does not exist, NinjaTrader is not loading the DLL at all** |

Uninstall: delete the bridge files from `Custom\AddOns` (and recompile once in the NinjaScript Editor), then restart the platform. Nothing else is written by the bridge.

### The trust prompt (why it exists)

Current NinjaTrader builds gate third-party code with a **trust prompt at first load** — the dialog
that appears the first time the platform sees a newly compiled add-on ("…has detected new
add-on(s)… ensure these are from trusted sources"). Answer **Yes** only for code you trust; the
shipped bridge is the modest case: read-only, loopback-only, full source in this repo. The older
`Tools ▸ Options ▸ … ▸ Allow custom assembly loading` switch this integration used to reference does
**not exist in 8.1.8.2** — its Settings dialog exposes no such option, and loose DLLs in
`Custom\AddOns` were ignored silently in testing. The NinjaScript-editor lane above is the one that
ships verified.

---

## 4. The wire protocol (what the suite and the DLL speak)

Loopback TCP, **one reader at a time** (this suite), UTF-8 JSON frames **terminated by a NUL byte**
(`\x00`) — the same framing convention as the Bookmap bridge. Every message carries `Type`.
Message fields are PascalCase. The full tables also live in `ninjatrader_bridge/README.md`.

**Server → client, unprompted**

| Type | Fields | When |
|------|--------|------|
| `hello` | Addon, Version, NT, Machine, Port, Mode (`read-only`), Connection, Status, Accounts[], Ts | immediately on accept |
| `heartbeat` | Ts | every 5 s |
| `quote` | Instrument, Last, Bid, Ask, BidSize, AskSize, Volume, High, Low, Opening, Settlement, Ts | on subscription, on request, on bid/ask changes (throttled ≥100 ms) |
| `trade` | Instrument, Price, Size, Aggressor (`buy`/`sell`/``), Ts | every last-print |
| `depth` | Instrument, Side (`bid`/`ask`), Price, Size, Operation (`add`/`update`/`remove`), Position, Ts | every L2 change |
| `depthsnapshot` | Instrument, Bids[[p,s],…], Asks[[p,s],…], Ts | right after a depth subscription |
| `instruments` / `bars` / `quote` / `capabilities` / `resolve` / `error` / `pong` | reply to the matching request (same `RequestId` back) | on request |

**Client → server**

| Type | Fields | Meaning |
|------|--------|---------|
| `subscribe` | Instrument, Channels[quote/trade/depth], DepthLevels | start streaming one instrument |
| `unsubscribe` | Instrument | stop it |
| `instruments` | RequestId, Filter?, Kind? | the terminal's own instrument database (masters; filter by name substring or `Future`/`Stock`/…) |
| `bars` | RequestId, Instrument, Period (Minute/Day/…), Interval, Count | historical bars from the platform's own data |
| `quote` | RequestId, Instrument | one-shot snapshot |
| `capabilities` | RequestId | accounts, connections, depth-events-seen counters |
| `resolve` | RequestId, Instrument | name resolution (`NQ1`, `NQ 12-26`, `NQ` → the front-month full name) |
| `ping` | — | liveness |

**Name resolution is the bridge's job**, because only the platform knows its contracts: the reader
sends whatever the row carries (`NQ`, `NQ1`, `MNQ 12-26`) and the bridge resolves it through
`Instrument.GetInstrument()` — a root resolves to the front month, exactly as typing it into
NinjaTrader would.

**Threading model.** All platform calls run on NinjaTrader's dispatcher (per-instrument for
subscriptions — the documented pattern, with `HasShutdownStarted` guards); market-data callbacks
only enqueue frames; a single writer thread does all socket writes. The socket side never blocks the
platform's UI thread.

---

## 5. What the suite side does with it

### 5.1 The feed (`data/ninjatrader_feed.py`)

* `NinjaTraderFeed` — same contract as the other venue feeds (`connect/start/stop`, `on_tick`,
  `on_orderbook`), built on the repo's reconnect ladder; silence budget 30 s against the bridge's
  5 s heartbeats; **frames reassembled across reads** (a regression pin covers the straddling case).
* **Symbol map**: app symbol → terminal name (`settings.NINJATRADER.symbols`, filled from the config
  rows' `ninjatrader_symbol`). `NQ` → `NQ 12-26` resolves once, on the bridge; every frame coming
  back maps to the app symbol.
* **Trades** carry the aggressor the bridge computed (last vs live bid/ask); sizes/prices are
  junk-guarded (NaN/inf rejected, counters exposed).
* **The ladder** is maintained locally from `depth` events (add/update/remove), emitted as sorted
  `OrderbookSnapshot`s (throttled ≥100 ms, forced on `depthsnapshot`).
* `ninjatrader_probe()` — the Platform card's Test connection: connect → hello → subscribe → count
  quotes/trades/depth for N seconds, report the NinjaTrader build, connection and depth verdict.
  Never throws; every failure names the next step.
* `ninjatrader_instruments()` / `ninjatrader_request()` — one-shot request/reply over the same wire
  (used by the look-up and by `engine.ninjatrader_validate()`).

### 5.2 Wiring (the venue touch-list)

| Where | What §84 added |
|-------|----------------|
| `config/settings.py` | `DataSource.NINJATRADER`, `NinjaTraderConfig` (host/port/symbols), singleton |
| `main.py` | the feed branch (builds the symbol map from config rows, starts the session) + stop path |
| `engine.py` | `ninjatrader_status()` (TCP probe), `ninjatrader_capable()` (stamp or shipped roots), `ninjatrader_symbol_names()` (120 s-cached terminal list), `ninjatrader_validate()`, `venue_stamp_for` gains `ninjatrader`, `select_instruments` gate, `capabilities()` carries `ninjatrader` |
| `config_store.py` | `ninjatrader` in the data-source allow-list; `platforms.ninjatrader` block (plan clamped to free/monthly/lifetime, port clamped 1–65535); `ninjatrader_symbol` kept verbatim (terminal names are case- and space-exact) |
| `desktop/platforms.py` | links/plans/caveats (prices as-of + source links), `ninjatrader_workflow()` (free-first), `detect_installs()` entry (version read from the platform's own log line — never config/accounts), `ninjatrader_bridge_state()` (shipped DLL vs AddOns copy, sha256), `reveal_bridge_dll()` |
| `api.py` | `GET /platforms` gains the NinjaTrader rows; `POST /platforms/plan` accepts `ninjatrader`; **`POST /platforms/bridge/ninjatrader`** (save), **`POST …/ninjatrader/test`** (live probe), **`GET …/ninjatrader/dll`** (state), **`POST …/ninjatrader/dll/open`** (reveal folder); `FREE_SOURCES` row + `tcp://` probe support; `datasources()` row; source-aware add lane |
| `desktop/instrument_lookup.py` | `NinjaTrader` branch: rows without a stamp answer with *“add it from the terminal's list (source: NinjaTrader)”*; a look-up against the terminal's own list turns `NQ1`/`NQ` into **available → NQ 12-26** with the add action |
| UI | wizard radio + note; walkthrough topic (with live test panel); Platforms card (plans, workflow, DLL state, Test connection); Help Centre topics `connect.ninjatrader` + `under.nt_bridge` |

### 5.3 The instrument story (NQ1, precisely)

Type `NQ1` (or `NQ`, or `NQ1!`) into the Engine panel's look-up with the source on NinjaTrader:

1. No app row matches → the look-up asks the bridge for the terminal's list.
2. The terminal lists `NQ 12-26` → answer: **available**, symbol `NQ`, terminal name `NQ 12-26`,
   actions **Add · Open Instruments**.
3. Add (with enable): the row is created **stamped** (`ninjatrader_symbol: "NQ 12-26"`, tick size
   from the terminal's database, asset class from the futures-roots table), the engine restarts,
   and the feed subscribes `NQ 12-26` on the bridge while the engines (tape, footprint, delta,
   ladder) key everything under `NQ`.

Only instruments you add — and only what your data subscription carries — become rows. Nothing is
guessed from the matrix: the venue stamp is the proof.

---

## 6. Configuration reference

```jsonc
// config.json — written by the Platforms card / setup assistant; no credentials exist in it
"data_source": "ninjatrader",
"platforms": {
  "ninjatrader": {
    "enabled": true,
    "host": "127.0.0.1",          // loopback only, by construction
    "port": 8790,                 // this suite's convention; bridge + card must agree
    "protocol": "modflow-nt-jsonl",
    "symbol": "NQ",               // instrument used by Test connection
    "plan": "free",               // free | monthly | lifetime
    "integrated": true,
    "bridge_built": false         // informational (built DLL shipped; rebuilds flip nothing)
  }
},
"instruments": [
  { "symbol": "NQ", "ninjatrader_symbol": "NQ 12-26", "tick_size": 0.25, "enabled": true, … }
]
```

---

## 7. Rebuilding the bridge (port changes, platform upgrades)

```powershell
# once: a user-scope .NET SDK (no admin, no Visual Studio)
# the project builds targets net48 and references NinjaTrader's own assemblies

cd orderflow_system\data\ninjatrader_bridge
powershell -ExecutionPolicy Bypass -File build.ps1
# → ModFlowBridge.dll beside the README; copy it to
#   Documents\NinjaTrader 8\bin\Custom\AddOns\ and restart the platform
```

To move the port, change `BridgePort` in `src/ModFlowBridge.cs`, rebuild, and set the same port on
the Platforms card.

---

## 8. Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `Test connection`: *no bridge at 127.0.0.1:8790* | NinjaTrader is not running, or the bridge is not in `Custom\AddOns` / was never compiled (NinjaScript Editor ▸ F5). Check the Log tab and `ntbridge.log`. |
| No `ntbridge-probe.log` at all after restarts | The platform never loaded the bridge: files not in `Custom\AddOns`, or the compile never ran (NinjaScript Editor ▸ F5), or the trust prompt was answered No. |
| Bridge loaded, `Test connection` ok, but no depth verdict | Your data subscription (or the Simulated feed on some builds) does not carry Level II. Quotes and trades are unaffected; the depth heat stays dark on purpose. |
| Kinetick End-Of-Day selected | No live stream exists to republish — the bridge is honest: no quotes. |
| Platform closed its login window | Current builds exit. Reopen and log in; the bridge loads with the next start. |
| Port conflict | Something else owns 8790 — rebuild the bridge on another `BridgePort` and set the card to match. |

---

## 9. Security & privacy (the honest block)

* The bridge is **read-only**: the protocol has no order verbs, and the DLL never reads account,
  licence, workspace or config files of the platform. It reports connection *names* and account
  *names* only.
* The socket is **loopback only** (`127.0.0.1`) and speaks to **one reader at a time**.
* The suite stores nothing but host/port/symbol/plan — **no credentials exist anywhere in this
  integration**, on either side.
* Answering NinjaTrader's **trust prompt** for the bridge is a real security decision — it
  compiles and runs C# inside your platform. Answer Yes only for code you trust; the full C#
  source ships in this repo beside the build script, so you can read exactly what it does first.

---

## 10. Verification status at build time

* Bridge: compiles cleanly (Roslyn, `net48`, x64) against NinjaTrader 8.1.8.2's own assemblies;
  DLL sha256 recorded by `ninjatrader_bridge_state()`; deployed to
  `Documents\NinjaTrader 8\bin\Custom\AddOns\`.
* Protocol + feed: **18 pins** (`test_ninjatrader_feed.py`) against a mock bridge that speaks the
  shipped wire format — hello/quotes/trades/depth bursts, request/reply, garbage, reconnect, the
  frame-straddling regression, symbol mapping, junk rejection.
* Routes + platform card: **9 pins** (`test_ninjatrader_api.py`) incl. a live probe against the
  mock on a real socket, port/plan clamping, the DLL state endpoint and the add lane’s stamping.
* Platform module: **6 new pins** in `test_platforms.py` (tiers, caveats, workflow, defaults,
  DLL comparison in tmp trees, allow-list).
* **LIVE (2026-09-18, the owner's own terminal, NT 8.1.8.2 + the NTB demo):** the bridge compiled and
  loaded through the NinjaScript editor, bound `127.0.0.1:8790` inside the platform, and the suite's
  reader pulled real CME data through it — **NQ DEC26**: 23 trades / 20 quotes / **1,765 depth
  updates** in 2.5 s (bid 29708.25 / ask 29709); **ES DEC26**: 69 trades / 307 depth in 1.5 s
  (7699.50 / 7699.75). Quotes, trades, Level-2 depth, the instrument database (NQ: tick 0.25,
  $20/point) and the roll calendar all answered live.
* **The front-month resolver uses NinjaTrader's own roll calendar** (`MasterInstrument.RolloverCollection`
  — the entry whose roll date is the latest one not in the future): `NQ1`/`NQ` → `NQ DEC26`,
  `CL` → `CL NOV26` (a fixed expiry-offset heuristic got crude wrong; the platform's own calendar is
  authoritative), `ES` resolves to the *future*, not the Eversource Energy stock that shares the ticker.
