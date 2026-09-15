# OFAP bridge — the Bookmap side of the integration

The suite reads Bookmap through **one small add-on**, because there is no other honest way: Bookmap
publishes no market-data-out API. It exposes an in-process **add-on API** (the thing their own
"Configure API plugins" dialog loads) and a Layer-0 API for connecting data *into* Bookmap. So the
fold-in is this: a read-only add-on subscribes to Bookmap's simplified-API callbacks — trades and
depth — and republishes them on loopback in a NUL-framed JSON stream. The suite connects to it.

```
Bookmap (your licence + your data feed)
   └── this add-on            (Layer 1 API: bm-l1api.jar + bm-simplified-api-wrapper.jar)
         └── 127.0.0.1:8791   (NUL-terminated JSON frames)
               └── MODDYS OrderFlow Analysis suite   (orderflow_system/data/bookmap_client.py)
```

## What it does, and what it will never do

* Reads: trades, depth, and a 5-second heartbeat. That is the whole surface.
* Loopback only (`127.0.0.1`): nothing is sent anywhere else, ever.
* No orders, no account access, no writes into Bookmap, no files read from your install.
* One reader at a time — the suite. A second connection replaces the first.

## Build it (once)

You need a **JDK** (Bookmap ships only a JRE — its bundled runtime is Temurin 25.0.2, so build with a
**JDK 25** and the classes match what Bookmap can load). Either:

```bat
cd orderflow_system\data\bookmap_addon
gradle jar
```
produces `build/libs/ofap-bridge.jar`; or, with no Gradle:

```bat
"C:\Users\<you>\tools\jdk-25\bin\javac" -cp "C:\Program Files\Bookmap\lib\*" -d classes src\com\moddy\ofapbridge\OfapBridge.java
"C:\Users\<you>\tools\jdk-25\bin\jar" --create --file ofap-bridge.jar -C classes .
```

Both compile against the jars **inside your Bookmap install**, so the API version is whatever your
Bookmap actually runs (this template was written against **7.8.0 build:13**).

## Install it into Bookmap (once)

1. Start Bookmap and load a chart (Replay mode is the friendliest first test).
2. **Settings → Configure API plugins** (the button in the add-ons window does the same thing).
3. **Add…** → pick `ofap-bridge.jar` (or the folder containing it) → tick the add-on to enable it.
4. Bookmap prints `[ofap-bridge] listening on 127.0.0.1:8791 for the OrderFlow Analysis suite` in its
   log. Installed modules land in `%LOCALAPPDATA%\Bookmap\API\Layer1ApiModules`.
5. In this suite: **Platforms → Bookmap → Bridge → Test connection**.

If your Bookmap runs on a different port, start it with `-Dofap.bridge.port=8792` (or edit `PORT` in
the source before building) and use the same port in the suite.

## Licences: what actually gates this

* **Bookmap Digital (free, with an account)** is enough to see crypto market depth, but it shows
  **one instrument at a time**, has the shortest backfill (1 hour) and is crypto-only.
* Bookmap's **API plugins dialog is licence-gated** on some subscriptions — the "Add" button can be
  locked, and the marketplace's advanced add-ons are sold with Global Plus. If the dialog refuses the
  jar, that is Bookmap's rule about *your* subscription, not a defect in this add-on. In that case the
  suite still runs on its own free feeds and this integration stays a labelled, optional path.
* Historical ("warm-up") data also depends on the licence: this add-on only republishes what Bookmap
  is currently streaming to the chart — it does not ask Bookmap for a longer history.

## Frame format

NUL-terminated JSON, UTF-8, one message per frame; `Type` is matched case-insensitively and unknown
types are ignored (so this add-on can grow without breaking the reader):

```json
{"Type":"hello","Addon":"ofap-bookmap-bridge","Version":"0.1","Bookmap":"7.8.0 build:13","Symbol":"BTCUSDT","Port":8791}
{"Type":"trade","Symbol":"BTCUSDT","Price":61234.5,"Size":4,"Aggressor":"buy","Ts":1789425000123}
{"Type":"depth","Symbol":"BTCUSDT","Side":"bid","Price":61234.5,"Size":12,"Ts":1789425000123}
{"Type":"heartbeat","Ts":1789425000123}
{"Type":"bye"}      ← sent when the add-on is unloaded or Bookmap closes
```

The suite's reader (`bookmap_client.py`) is written to this format and is tested against a mock add-on
server, so a change here is a change in both places on purpose — the mock in `test_platforms.py` is
the contract.
