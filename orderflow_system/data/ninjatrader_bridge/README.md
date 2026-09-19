# ModFlow Bridge — the NinjaTrader 8 side of the integration

The suite reads NinjaTrader through **one small read-only add-on**. NinjaTrader publishes no
market-data-out API to external programs, so — exactly like the Bookmap bridge — the add-on runs
*inside* NinjaTrader (their own supported AddOn framework), subscribes to the platform's own
market-data callbacks, and republishes them on loopback in NUL-framed JSON. The suite connects
to it.

```
NinjaTrader 8  (your licence, your feed: Simulated / Kinetick free / NinjaTrader Brokerage demo or live)
   └── this add-on                  (NinjaScript AddOnBase; MarketData + MarketDepth subscriptions)
         └── 127.0.0.1:8790         (NUL-terminated JSON frames, one client at a time)
               └── MODDYS OrderFlow Analysis suite   (orderflow_system/data/ninjatrader_feed.py)
```

## What it does, and what it will never do

* Reads: quotes (last/bid/ask + sizes, day stats), trades, **level-2 market depth**, instrument
  look-ups (the master-instrument database), and historical bars (NinjaTrader's own data).
* Loopback only (`127.0.0.1`): nothing is sent anywhere else, ever.
* **No orders.** No placing, modifying or cancelling — no account credentials, no files read from
  your install. Read-only by construction; the wire protocol has no write verbs.
* One reader at a time — the suite. A second connection replaces the first.

## Build it (once — the built DLL travels with the suite)

You need the **.NET SDK** (free; `winget install Microsoft.DotNet.SDK.8`, or any 8/9/10 SDK —
no Visual Studio, no admin):

```bat
cd orderflow_system\data\ninjatrader_bridge
powershell -ExecutionPolicy Bypass -File build.ps1
```

produces `ModFlowBridge.dll` in this folder. It is compiled **against the NinjaTrader 8 assemblies
in `C:\Program Files\NinjaTrader 8\bin`** (verified against **8.1.8.2**), so the API surface is
whatever your NinjaTrader actually runs.

> A prebuilt `ModFlowBridge.dll` **ships in this folder** — a fresh user needs no SDK at all,
> only the two install steps below.

## Install it into NinjaTrader (once)

The **source lane is the verified one on 8.1.8.2** — the platform compiles the add-on itself:

1. Copy `src\ModFlowBridge.cs`, `src\ModFlowJson.cs` and `src\ModFlowProbe.cs` to:

   ```
   Documents\NinjaTrader 8\bin\Custom\AddOns\
   ```

   (create the `AddOns` folder if it does not exist).
2. In NinjaTrader open **New ▸ NinjaScript Editor** and press **F5**.
3. On the first compile the platform asks *“…has detected new add-on(s)… ensure these are from
   trusted sources”* — answer **Yes**. That prompt is NinjaTrader's own gate for third-party code
   on current builds; it replaces the older `Tools ▸ Options ▸ … ▸ Allow custom assembly loading`
   switch, which 8.1.8's Settings no longer lists.
4. The platform's **Log tab** then shows `[ModFlow Bridge] listening on 127.0.0.1:8790
   (read-only market data)`; the same line is appended to `%LOCALAPPDATA%\ModFlow\ntbridge.log`.
5. In this suite: **Platforms ▸ NinjaTrader ▸ Bridge ▸ Test connection** — or pick NinjaTrader as
   the data source in the setup assistant.

**Prebuilt-DLL lane (advanced / older builds).** `ModFlowBridge.dll` in this folder is the same
code compiled ahead of time — copy it into the same `AddOns` folder and restart the platform once.
Older 8.0.x builds loaded loose DLLs once `Allow custom assembly loading` was enabled; on 8.1.8.2 a
loose DLL sat ignored in testing, which is why the source lane above is the one the suite teaches.

If the port is taken, the bridge logs the bind failure to `ntbridge.log` and to the Log tab —
change `Port` in `ModFlowBridge.cs` (and the port in the suite's bridge card) or free the port.

**Install one lane at a time.** The source lane (F5) and the prebuilt-DLL lane are two copies of
the same bridge. A NinjaScript recompile reloads the add-on *in place* and the previous copy can
keep the port and its threads, so a bridge installed through both lanes — or an F5 reload over a
running one — ends with two copies in the process and possibly one zombie holding 8790. The
bridge no longer tries to work around that at load time; if the log says the port is held after a
recompile, restart NinjaTrader. To switch lanes, remove the old copy first.

## What the tier decides

The bridge republishes **whatever your NinjaTrader is connected to**, so the honest tier map is:

| What you run | What the suite receives |
|---|---|
| **Simulated Data Feed** (no account) | synthetic quotes/trades/depth at ~2 ticks/s — enough to test the whole path |
| **Kinetick – End Of Day (Free)** | EOD history; no real-time stream |
| **NinjaTrader Brokerage demo/live** (market-data entitlements) | real-time CME quotes, trades and — when your data subscription carries it — level-2 depth |
| **Order Flow +** | not republished by this bridge (the suite computes its own footprint/delta from trades + depth) |

Depth availability is a fact of your feed, not of this add-on: subscribe and watch the suite's
Order Book panel — if the ladder fills, your connection carries level 2; if it stays empty, your
feed does not (the suite's bridge card says so in your own tier's words).

## Frame format

NUL-terminated JSON, UTF-8, one message per frame; `Type` is matched case-insensitively and
unknown types are ignored (so the bridge can grow without breaking the reader):

```json
{"Type":"hello","Addon":"modflow-nt-bridge","Version":"1.0","NT":"8.1.8.2","Port":8790,"Mode":"read-only","Connection":{"Name":"Simulation","Status":"Connected"},"Accounts":[{"Name":"Sim101","Sim":true}]}
{"Type":"quote","Instrument":"NQ 12-26","Last":25431.25,"Bid":25431.0,"Ask":25431.25,"BidSize":3,"AskSize":2,"Volume":184233,"Ts":1789425000123}
{"Type":"trade","Instrument":"NQ 12-26","Price":25431.25,"Size":1,"Aggressor":"buy","Ts":1789425000123}
{"Type":"depth","Instrument":"NQ 12-26","Side":"bid","Price":25431.0,"Size":14,"Operation":"update","Position":0,"Ts":1789425000123}
{"Type":"depthsnapshot","Instrument":"NQ 12-26","Bids":[[25431.0,14],[25430.75,9]],"Asks":[[25431.25,2]]}
{"Type":"heartbeat","Ts":1789425000123}
```

Commands the suite sends: `subscribe` (Instrument, Channels, DepthLevels) · `unsubscribe` · `ping` ·
`quote` · `instruments` (Filter, Kind) · `bars` (Instrument, Period, Interval, Count) ·
`capabilities` · `resolve` (Instrument — `NQ`, `NQ1`, `NQ1!` and `NQ 12-26` all answer with the
front-month contract `NQ 12-26`). Request/reply messages carry the caller's `RequestId`.

`src/ModFlowProbe.cs` is a diagnostics add-on that writes the platform's API facts (loaded
assemblies, accounts, instrument look-ups) to `%LOCALAPPDATA%\ModFlow\ntbridge-probe.log` on every
start — useful when NinjaTrader "does not seem to load" the DLL at all.

The suite's reader (`orderflow_system/data/ninjatrader_feed.py`) is written to this format and is
tested against a mock bridge server, so a change here is a change in both places on purpose.
