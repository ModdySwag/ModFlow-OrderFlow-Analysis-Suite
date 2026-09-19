<!-- Reading notes for docs/FLOWSURFACE_FOLD_IN_PLAN.md. Source: github.com/flowsurface-rs/flowsurface
     @ c1388d4 (2026-09-16), cloned read-only. GPL-3.0: these notes describe behaviour only —
     no flowsurface code appears here and none may be copied into this repo. -->

# flowsurface `exchange/` — the feed layer (WS sessions, heartbeats, five venues, proxy, units)

# flowsurface `exchange/` crate — data-feed ingestion briefing (IDEAS for a Python feed layer)

Source: `C:\Users\<you>\AppData\Local\Temp\flowsurface_ref` @ c1388d4, GPL-3.0.
**Ideas/designs only — no code may be copied into OFAP.**
Target: ModFlow OrderFlow Analysis Suite (`orderflow_system/data/bybit_feed.py`, alpaca feeds, WS manager, atlas layer).
Line refs are `path:line` relative to repo root. Nothing was run; everything below is read from source.

---

## 0. Crate map (what is where)

| Area | File | Notes |
|---|---|---|
| Domain types, Timeframe, Ticker, Trade/Kline/Volume, TickerStats | `exchange/src/lib.rs` (765 L) | ms timestamps only |
| Stream/venue enums, `StreamKind`, `UniqueStreams`, `Event` | `exchange/src/adapter.rs` (552 L) | dedupe + capability tables |
| WS transport + session loop + heartbeats + reconnect | `exchange/src/adapter/ws.rs` (1034 L) | the core |
| REST worker, limiter plumbing, error text | `adapter/http.rs`, `adapter/limiter.rs`, `error.rs` | |
| Venue adapters (REST + WS) | `adapter/hub/{binance,bybit,hyperliquid,okex,mexc}/` | |
| Orderbook container + diff application | `exchange/src/depth.rs` (183 L) | BTreeMap<Price,Qty> |
| Units | `exchange/src/unit/{price,qty,time}.rs` | int atomic units |
| Proxy (CONNECT/SOCKS) | `adapter/proxy.rs` (753 L) | |
| Network UI | `src/modal/network_editor.rs`, `src/connector/client.rs`, `data/src/config/auth.rs` | |

Topology: per (venue, market, stream-group) there is **one WsSession task** producing a `Stream<Event>`; the UI batches distinct sessions with `Subscription::batch` (`src/screen/dashboard.rs:1330-1392`).

---

## 1. WS adapter framework (`adapter/ws.rs`)

### 1.1 Session lifecycle & reconnect
- `WsSession::run(adapter)` spawns a tokio task; the returned `ChannelStream` aborts the task on `Drop` (`ws.rs:139-143`, `215-358`). One task owns one socket forever — reconnect is *inside* the loop, so consumers never see churn.
- Empty stream payload short-circuits to `Event::Disconnected(streams, "Empty stream payload")` (`ws.rs:221-227`).
- Event channel: **bounded 512, send failures ignored** (`ws.rs:216`, `270-279`). An opt-in `unbounded-channel` cargo feature documents the tradeoff: "events are never dropped under load… useful for database ingestion or audit trails where every tick matters" (`exchange/Cargo.toml:10-16`). **Design lesson for OFAP: a UI-oriented lossy channel and a persistence-oriented lossless channel are two different products — pick per consumer, do not silently drop for SQLite ingestion.**
- Reconnect/backoff (`ws.rs:939-976`): initial 500 ms, ×2 per failure, cap 30 s, **±25% multiplicative jitter** ("spread reconnections across streams when multiple disconnect at once", `ws.rs:942-943`). Crucially `record_success()` is called **only when a real frame was parsed** (`ws.rs:267`), not on TCP connect — a socket that connects and dies instantly keeps escalating backoff. `record_failure()` runs after every disconnect (`ws.rs:349-350`).
- Connect failures emit `Disconnected(reason)` then sleep+continue (`ws.rs:232-240`) — the consumer always learns *why*, including the pre-connect path.

### 1.2 Heartbeats: venue-aware policy objects
- `HeartbeatPolicy` has exactly three shapes (`ws.rs:375-402`):
  1. `PeriodicClientPing { ping: PingPayload, every, silence_timeout }` — scheduled *after* the previous write succeeds; close if no complete inbound frame within `silence_timeout`.
  2. `PingAfterIdle { ping, idle_for, response_timeout }` — send only after inbound traffic has been idle; after sending, wait `response_timeout` for *any* complete inbound frame.
  3. `ServerDriven { silence_timeout }` — never ping proactively, but still answer protocol Pings.
- `PingPayload` distinguishes an application text frame from a WebSocket control Ping (`ws.rs:361-368`, `734-749`).
- State machine lives in `WsHeartbeat` (`ws.rs:468-601`): `Periodic{next_ping} | IdleMonitoring | IdleAwaitingResponse{deadline} | ServerDriven`; `next_deadline()` is `min(last_activity + silence_timeout, next_ping)` for the periodic policy (`ws.rs:491-520`); `mark_activity()` both refreshes the silence deadline and moves `IdleAwaitingResponse → IdleMonitoring` (`ws.rs:571-576`); `record_ping_sent()` re-arms either `next_ping = now+every` or the response deadline (`ws.rs:578-600`).
- Every *complete inbound frame* — including control frames — counts as activity (`ws.rs:670`, docstring `ws.rs:370-374`).
- Concrete venue policies:

| Venue | Policy | Ping payload | Timing | Ref |
|---|---|---|---|---|
| Bybit | periodic text | `{"op":"ping"}` | every 20 s, silence 60 s | `bybit/stream.rs:22-27` |
| MEXC | periodic text | `{"method":"ping"}` | every 15 s, silence 45 s | `mexc/stream.rs:28-33` |
| OKX | ping-after-idle text | `ping` (bare string) | idle 20 s, response 20 s | `okex/stream.rs:22-27` |
| Hyperliquid | ping-after-idle text | `{"method":"ping"}` | idle 30 s, response 30 s | `hyperliquid/stream.rs:24-29` |
| Binance | server-driven | — | silence 45 s spot / 240 s perps | `binance/stream.rs:26-33` |

  (Binance perps legitimately push nothing for minutes, hence 240 s; using one global timeout across venues is exactly the bug class the commit fixes.)

### 1.3 The cancellation-safe in-flight read trick (c1388d4)
`WsConnection::run` (`ws.rs:629-711`):

- The read future is created **once, outside** the inner loop and pinned: `let mut read_future = Box::pin(reader.read_frame(&mut no_control_send));` (`ws.rs:638-640`).
- The inner loop selects `biased` between **that same** `read_future` and a `sleep_until(heartbeat.next_deadline())` (`ws.rs:642-654`). If the timer fires first, the code applies the heartbeat action (send ping / declare timeout) and **loops back to poll the same read future** — the partial frame stays alive across heartbeat ticks.
- The read future is dropped only after it resolves: `drop(read_future);` (`ws.rs:656`), then a fresh one is created for the next frame.
- Rationale stated in the commit: "previous shared timeouts was able to cancel partial frame reads, mostly visible on Hyperliquid conn., leaving the frame parser out of sync and causing `Reserved bits are not zero` disconnects". A cancelled mid-frame read leaves `FragmentCollectorRead` with a half-consumed fragment/continuation state; the next bytes are interpreted as a new frame header → reserved-bit/opcode errors → disconnect loop. Making the read non-cancellable by the heartbeat removes the desync entirely.
- Supporting choices that keep control traffic deterministic:
  - `reader.set_auto_pong(false)` and `reader.set_auto_close(false)` (`ws.rs:790-791`), with `no_control_send` as the read callback (`ws.rs:638-639`) — the session, not the library, replies; nothing writes on the socket concurrently with the read future.
  - Opcode dispatch (`ws.rs:672-700`): Text → forwarded to the parser; Ping → echo Pong with the same payload (a failed write ends the connection with `"Failed to reply pong"`); Close → echo the close frame and surface a formatted reason; anything else → keep going.
  - After each message an extra `apply_heartbeat_action` runs (`ws.rs:706-709`) so a ping can go out immediately after traffic rather than waiting for the next deadline.
  - `biased` means inbound data always wins over the timer.
- Close reasons are humanised: `format_close_frame_reason` decodes the 2-byte code + UTF-8 reason, truncates at 512 chars, handles empty/1-byte/invalid-UTF-8 payloads (`ws.rs:751-777`). This is the string that reaches `Event::Disconnected`.

**Python translation:** `asyncio.wait_for(ws.recv(), timeout)` cancels `recv()` and is the exact analogue of the pre-fix bug (websockets/`aiohttp` leave the frame assembler mid-frame; you then get protocol errors and a reconnect storm). Run a dedicated reader task that never gets cancelled, and a separate heartbeat/deadline task; the deadline task only sends pings or asks the reader task to close.

### 1.4 Frame parsing, multiplexing, drain
- Fragmentation handled by `FragmentCollectorRead` (`ws.rs:604`, `793`); only Text frames are forwarded as payloads (`ws.rs:673-676`), Binary is ignored (`ws.rs:699`).
- Multiplexing is at the *subscription* level: one socket carries N topics, and the adapter routes each frame by topic/stream name → `Ticker` (Bybit `bybit/stream.rs:84-101,140-245`; Binance `binance/stream.rs:265-350`; MEXC `mexc/stream.rs:110-128`). Chunking is capped in the app: `MAX_TRADE_TICKERS_PER_STREAM = 100`, `MAX_KLINE_STREAMS_PER_STREAM = 100` (`adapter/client.rs:14-15`) applied with `.chunks(...)` (`src/screen/dashboard.rs:1344-1386`) — "keep topics per websocket conservative across venues".
- **Head-of-line drain:** after handling the first frame, the loop drains up to `MAX_DRAIN_PER_TICK = 256` more queued frames synchronously (`ws.rs:42`, `282-307`), then returns to the select. Bursts never starve the tick timer/flush, and the drain is bounded so a pathological flood still yields to timers.
- **Tick timer:** `tokio::select!` on a pinned sleep of `ADAPTER_TICK_INTERVAL = 33_333 µs` (~30 Hz) (`ws.rs:153`, `255-257`, `323-330`), reset after each fire (`ws.rs:327-329`). This same interval is the *time bucket* for trade aggregation.
- **Error surfacing:** `on_text` returning `Err(String)` becomes a disconnect reason and the session tears down + reconnects (`ws.rs:276-279`, `296-297`, `309-311`); a dead I/O task surfaces as `None` → `"I/O task exited"` (`ws.rs:312-316`). Parse errors are thus never silent and never permanent — they convert protocol desync into a reconnect (plus backoff escalation, since success requires a parsed payload). Binance additionally returns `Err("Received trade for unknown ticker")` (`binance/stream.rs:393-396`) — i.e. a routing mismatch is fatal, not a warning.

### 1.5 Trade batching (`TradeBuffer`, `ws.rs:978-1033`)
- Per-ticker `Vec<Trade>` built in `on_text`, flushed in `on_tick`, and **also** on connect/disconnect (`bybit/stream.rs:269-271,304-310`) so buffered trades are not lost across a reconnect.
- Flush collapses each ticker's buffer into one `Event::TradesReceived(StreamKind::Trades, update_t, trades)` where `update_t = floor(max(trade.time) / interval_ms) * interval_ms` (`ws.rs:1004-1030`) — the emitted timestamp is a bucket, not a raw ts, which makes downstream aggregation idempotent.
- Non-trade adapters push events directly from `on_text` (documented flush model `ws.rs:189-201`).

---

## 2. Per-venue specifics

### 2.1 Bybit (the target app's current venue)
- Endpoint `wss://stream.bybit.com/v5/public/{spot|linear|inverse}` (`bybit.rs:14`, `stream.rs:115-123`); REST `https://api.bybit.com` (`bybit.rs:15`). Public only — no private streams anywhere in the crate.
- Subscribe: single frame `{"op":"subscribe","args":[...]}` (`stream.rs:337-340`), sent immediately after `establish()` (`stream.rs:110-137`); no ack tracking — subscription errors surface as parsing failures/reconnect.
- Topics: `publicTrade.{SYM}` (`stream.rs:331-334`), `orderbook.{depth}.{SYM}`, `kline.{interval}.{SYM}` (`stream.rs:495-499`, `626-631`), with `D` for 1d (`stream.rs:621-625`).
- **Push frequency ⇒ depth level mapping** (`stream.rs:478-499`): because Bybit's push rate is coupled to the subscribed level count, a requested 100 ms becomes depth `200` and 300 ms becomes `1000` (perps), spot uses `200/1000` for 200/300 ms. This is a nice reusable pattern: *express a desired latency as a choice of feed granularity* rather than throttling client-side.
- Parsing: single-pass iteration over the JSON object with `to_object_iter_unchecked` (`stream.rs:140-245`) instead of full deserialization; numbers arrive as strings and are parsed via `de_string_to_number` (`serde_util.rs:5-13`, used at `stream.rs:43-64`); `side` is `"Sell"`/`"Buy"` → `is_sell` (`stream.rs:290`); trade `T`, depth `cts`, kline `start` are all ms.
- Orderbook: `type == "snapshot"` **or** `u == 1` → full replace, `type == "delta"` → apply then emit (`stream.rs:423-441`). **No sequence-gap validation**: `u` is stored as `last_update_id` but never compared, so a dropped delta silently corrupts the local book until the next snapshot. Binance does the opposite (§2.4) — that asymmetry is the single biggest ingestion-quality gap to fix in a Bybit-based app.
- Snapshot timing note: on snapshot the adapter does **not** emit; it only emits on subsequent deltas (`stream.rs:423-441`) — first paint comes from the REST/other path or the next delta.
- REST (`bybit/fetch.rs`): `instruments-info?category=…&limit=1000` → `priceFilter.tickSize`, `lotSizeFilter.minOrderQty`; filters to `contractType ∈ {LinearPerpetual, InversePerpetual}` and `quoteCoin ∈ {USDT, USDC, USD}` and rejects symbols with chars outside `[A-Za-z0-9_-]` (`bybit/fetch.rs:68-122`, `adapter.rs:507-518`). Tickers → stats, 24h change ×100 into percent, volume × mark price for USD notional, inverse volume is already USD (`fetch.rs:139-181`). Klines: `limit = min((end-start)/interval, 1000)` (`fetch.rs:207-221`). Open interest max 200 points (`fetch.rs:275-304`).
- Rate limits: fixed window **600 requests / 5 s** window with **5 % headroom**, 403 = "exit" status (`bybit.rs:16-18,52-61`, `limiter.rs:150-203`).

### 2.2 Hyperliquid (candidate feed)
- One endpoint for everything: `wss://api.hyperliquid.xyz/ws` (`hyperliquid.rs:16`); REST is **POST `https://api.hyperliquid.xyz/info` with JSON bodies** (`hyperliquid.rs:15`, `fetch.rs:107-117`) — no REST paths per resource.
- Subscribe **one frame per coin** (`{"method":"subscribe","subscription":{"type":"trades","coin":"BTC"}}`, `stream.rs:218-233`; candles `stream.rs:525-541`); channels `trades`, `l2Book`, `candle` (`stream.rs:169-199`).
- **Depth has no deltas**: every `l2Book` message is a complete 2-sided snapshot (`stream.rs:419-456`, arrays `levels[0]=bids`, `levels[1]=asks`). Server-side aggregation is requested at *subscribe* time instead: `nSigFigs` (2–5) and, when `nSigFigs == 5`, `mantissa` ∈ {1,2,5} (`stream.rs:379-402`), computed from the user's tick multiplier by `config_from_multiplier` / `snap_multiplier_to_125` (`stream.rs:53-107`). `allowed_multipliers_for_min_tick` encodes observed HL tick rules — fractional-tick, integer-tick and "exactly 1" ambiguity cases (`hyperliquid.rs:26-43`).
- **Snapshot-before-subscribe** (`stream.rs:354-417`): `connect()` first REST-fetches `l2Book`, seeds `LocalDepthCache`, records `pending_snapshot_emit_ms`, *then* opens the WS and subscribes; `on_connected()` emits the seeded book. Result: a painted book even if the socket dies immediately, and a deterministic resync path on every reconnect (the whole `connect()` is re-run per attempt).
- Tick size is **derived, not published**: `compute_tick_size(price, szDecimals, market)` implements the 5-significant-figure rule with a 6-decimal cap for perps, integer prices above 5 sig figs, and a leading-zeros branch for sub-1 prices (`fetch.rs:403-441`); `min_qty = 10^-szDecimals` (`fetch.rs:367-374`). Metadata comes from `metaAndAssetCtxs` / `spotMetaAndAssetCtxs` / `perpDexs` — including **multiple perp DEXes**, each fetched and merged with per-DEX failure tolerance (`fetch.rs:132-209`).
- Symbology: spot pairs are `@107`-style internally with a **display symbol** (`HYPEUSDC`) attached (`lib.rs:282-286`, `fetch.rs:376-393`); perp symbols get a synthetic display symbol from the collateral token (`fetch.rs:313-333`). Internal key ≠ display key is a good idea for any venue with numeric IDs.
- Klines: `candleSnapshot` with default range "500 candles back" when no range is given (`fetch.rs:518-528`); volume normalized through `QtyNormalization` (`fetch.rs:544-567`).
- Rate limits: 1200 / 60 s window, 429 = exit (`hyperliquid.rs:20-22,68-76`).

### 2.3 OKX & MEXC (delta venues with the same weak contract)
- OKX: `wss://ws.okx.com/ws/v5/{public|business}` (`okex.rs:14`, `stream.rs:52-71`); ping is the bare text `ping` (`stream.rs:22-27`); depth from channel `books` with `seqId` (`stream.rs:106-127`) and the identical `snapshot || last_update_id == 1` → replace, `delta` → apply+emit logic, again **without gap detection** (`stream.rs:325-341`). Rate limit 20/2 s (`okex.rs:16-18`).
- MEXC: futures WS path (`mexc.rs:14-19`); heartbeat `{"method":"ping"}` 15 s/45 s (`stream.rs:28-33`); depth carries a monotonic `version` and uses a full copy of the Binance-style sync machine (`stream.rs:470-640`) — pending diffs are **sorted by version** before replay (`stream.rs:541-542`) and stale diffs (`version <= local_last_version`) are dropped (`stream.rs:574-576`). Subscription-time errors are surfaced by tracking whether *any* subscribe frame was written, else `Err("No supported MEXC kline timeframes requested")` (`stream.rs:699-738`). Rate limit 10/2 s with **0 % headroom** (`mexc.rs:17-19`).

### 2.4 Binance (the reference implementation for orderbook integrity)
- Domains/paths per market: `stream.binance.com/stream`, `fstream.binance.com/{public,market}/stream`, `dstream.binance.com/...` with combined-stream `?streams=a@aggTrade/b@kline_1m` (`binance/stream.rs:35-72`, `426-439`, `822-833`). Depth WS is `{sym}@depth@100ms` (`stream.rs:717`).
- `DepthSyncMachine` (`binance/stream.rs:528-693`) — **the most directly transferable algorithm in the crate**:
  - States: `WaitingSnapshot(oneshot::Receiver<…>)` and `Live` (`stream.rs:534-542`).
  - `begin_resync()` spawns the REST snapshot fetch and stores the *receiver*, it never awaits it (`stream.rs:565-580`).
  - While waiting, incoming diffs are pushed to a `VecDeque` capped at `MAX_PENDING_DEPTH_EVENTS = 512`, dropping the oldest (`stream.rs:646-652`, `:24`).
  - `poll_snapshot_if_ready()` uses `oneshot::try_recv()` **at the top of `on_text`** (`stream.rs:654-678`, called at `502-504`) — the reader task never blocks on REST.
  - On snapshot arrival: replace book, reset `prev_id`, replay the pending deque in order, then go `Live` (`stream.rs:582-619`).
  - Chain validation per event (`stream.rs:119-193`): drop if `final_id <= last_update_id`; first event must satisfy `first_id <= last_update_id+1 <= final_id`; subsequently `prev_final_id` (perps, field `pu`) must equal the previous `final_id`, spot instead requires `first_id == prev+1`. Any mismatch → `NeedsResync`: log, clear the deque, push the offending event back, `begin_resync()` (`stream.rs:621-644`). Live diffs are never applied out of order.
- REST snapshot sizes/costs: spot limit 5000 (weight 250), perps 1000 (weight 20), with weight table per limit bracket (`binance/fetch.rs:79-140`). Snapshot timestamps: perps use the venue `T`, spot substitutes local `now()` because the REST payload has none (`fetch.rs:131-166`).
- Klines exploit `taker_buy_base_asset_volume` to emit directional volume `Volume::BuySell(buy, sell)` where `sell = volume - taker_buy` (`binance/stream.rs:74-92`, `769-783`) — the only venue in the crate with buy/sell kline volume; every other venue emits `Volume::TotalOnly`.

### 2.5 Cross-venue rate-limit handling (`adapter/limiter.rs`, `http.rs`)
- Two limiter kinds behind one `RateLimiter` trait (`limiter.rs:4-13`): `FixedWindowRateLimiter` (token bucket + wall-clock-period refill, `limiter.rs:16-66`) and `HeaderDynamicRateLimiter` (reads a `X-MBX-USED-WEIGHT-*`-style header and derives the wait as "rest of the current period + 500 ms", falling back to the fixed bucket when the header is stale, `limiter.rs:74-148`, `235-276`).
- Effective limit is shaved by `limiter_buffer_pct` (3–5 % per venue) so the client self-throttles before the venue 429s (`limiter.rs:174-188`, `242-254`).
- Designated "exit" status codes (429/403) short-circuit into a typed error (`limiter.rs:200-203`, `273-276`, `http.rs:96-109`).
- **All REST for a venue is serialised through one worker task**: `mpsc(128)` command channel + `oneshot` reply channel; the worker owns the client *and* the limiter (`http.rs:303-316`, `322-373`, `375-407`). Callers get `Result<T, AdapterError>` with no shared-state locking. This is the cheapest correct way to rate-limit in a single-process Python app too (one asyncio task per venue owning its own `aiohttp`/`httpx` client + limiter).
- HTTP error text is deliberately two-tier (`error.rs:33-62`, `126-135`): the `detail` (method, URL, status, content-type, body preview ≤200 chars, io kind/os error, source chain ≤8 deep — `http.rs:169-214`, `216-250`, `error.rs:185-285`) goes to logs, while `ui_message()` returns short non-technical strings ("Rate limited. Check logs for details.") for the UI. Non-JSON/HTML bodies are explicitly detected (`http.rs:192-201`) — very useful when a proxy or CDN returns a login page instead of JSON.

---

## 3. Network / proxy handling

- `ProxyScheme { Http, Https, Socks5, Socks5h }` (`proxy.rs:85-109`). Construction validates non-empty host, port 1–65535, and *mutual* auth presence ("Provide both username and password (or neither)", `proxy.rs:151-220`).
- **Four distinct string renderings** (`proxy.rs:320-383`) — a hygiene pattern worth copying verbatim in spirit:
  - `to_url_string()` (with credentials) — only for socks config,
  - `to_url_string_no_auth()` — used as the *key* for credential storage,
  - `to_log_string()` — `scheme://***:***@host:port`, never includes secrets,
  - `to_ui_string()` — may show username, never the password.
  IPv6 literals are bracketed for both URL-authority and socket-address forms (`proxy.rs:298-318`).
- WebSocket path (`proxy.rs:385-532`): HTTP/HTTPS proxies perform a real **CONNECT tunnel** with `Proxy-Connection: keep-alive` and Basic auth, reading headers until CRLFCRLF with a 16 KB cap, mapping 200 → ok, 407 → "proxy auth required", everything else → status in the error (`proxy.rs:644-716`); both TCP connect and tunnel have 10 s timeouts (`proxy.rs:15-16`). `Socks5` resolves DNS **locally** and tries every resolved address in turn; `Socks5h` hands the hostname to the proxy (`proxy.rs:460-530`) — the difference matters exactly when a venue geo-blocks via DNS.
- TLS: rustls + `webpki-roots`, one `LazyLock` connector (`ws.rs:44-61`); the upgraded stream is a two-variant `ProxyStream` (`Plain` / `TlsToProxy`) with hand-written `AsyncRead/AsyncWrite` delegation (`proxy.rs:19-83`) so the WS code is proxy-agnostic.
- Handshake hardening on the WS side (`ws.rs:803-936`): the URL host must equal the `domain` argument (`814-818`, catches misconfigured endpoints), TCP 10 s / TLS 10 s / WS 15 s timeouts (`37-40`, `828-853`), Host header includes a non-default explicit port (`911-921`).
- REST path: `try_apply_proxy` on the reqwest builder — socks credentials ride in the URL, http/https use `basic_auth` (`proxy.rs:718-753`).
- Two HTTP clients with different trust (`src/connector/client.rs:44-71`): the exchange client is strict; the *user's own* market-data server client sets `danger_accept_invalid_certs(true)` for self-signed certs. Both 30 s request / 10 s connect timeouts.
- Credentials live in the **OS keychain**, service `flowsurface.proxy`, entry keyed by the proxy URL *without* auth; load happens lazily at layout time and re-attaches silently (`data/src/config/auth.rs:5-110`, `src/layout.rs:382-386`).
- UI (`src/modal/network_editor.rs`): scheme `pick_list` + host + port + optional username + masked password with a "hide" checkbox (`287-427`); the Apply button only appears when the draft differs from the effective config (`245-263`, `874-876`); clearing needs a two-step confirm row (`828-856`); both an "Effective:" and a "Pending:" line are shown plus an info tooltip ("Pending changes require a full restart") and a modal banner (`146-162`). Applying writes the config immediately but the change takes effect after restart (`src/main.rs:574-584`). Same modal also hosts the historical-backfill server config (exchange vs self-hosted server + optional auth token, `501-826`).

---

## 4. Data model (`exchange/src/unit/**`, `lib.rs`) — exact fields & units

| Type | Fields | Units / notes | Ref |
|---|---|---|---|
| `UnixMs(pub u64)` | — | **ms everywhere, never seconds**; `serde(transparent)`. Helpers: `now()`, `floor_to(Timeframe)`, `offset_by_timeframe`, `try_from_seconds`, `from_seconds_saturating`, `as_seconds_floor`, checked/saturating add/sub, `is_within`/`ensure_within` | `unit/time.rs:5-183` |
| `Price { units: i64 }` | — | **fixed atomic scale 1e-11**; `from_f64` rounds to nearest atomic unit; `round_to_min_tick(MinTicksize)`; `round_to_side_step(is_sell_or_bid, step)` floors bids/sells and ceils asks/buys; `ratio_in_range`, `steps_between_inclusive` | `unit/price.rs:5-211`, `143-149` |
| `PriceStep { units: i64 }` | — | step in atomic units; `decimal_places()`, `to_ui_string()` (trailing-zero trimmed) | `unit/price.rs:266-327` |
| `Qty { units: i64 }` | — | **atomic scale 1e-8**; `round_to_min_qty`, `to_lots`, `scale_or_one` guard | `unit/qty.rs:37-139` |
| `Power10<MIN,MAX>{power:i8}` | — | precision as a *power of ten*; aliases: `ContractSize = Power10<-4,6>`, `MinTicksize = Power10<-11,2>`, `MinQtySize = Power10<-6,8>`; serde as plain float | `unit.rs:9-86` |
| `SizeUnit { Base, Quote }` + global | — | `SIZE_CALC_UNIT: AtomicU8` set via `set_preferred_currency`, read via `volume_size_unit()` — a process-wide display preference consulted at subscription time | `unit/qty.rs:15-35` |
| `RawQtyUnit { Base, Quote, Contracts }` | — | what the venue's raw volume means | `unit/qty.rs:205-214` |
| `QtyNormalization { size_in_quote_ccy, contract_size: Option<f64>, market_kind, raw_qty_unit }` | — | the single conversion choke point: raw × unit-kind × market kind (linear/inverse) × contract size × user Base/Quote preference; inverse perps are always quote-denominated; `scale_or_one` guards zero prices | `unit/qty.rs:197-306` |
| `Ticker { bytes:[u8;28], exchange, display_bytes:[u8;28], has_display_symbol }` | — | fixed-size inline symbol + separate display symbol; `SerTicker` = `"Exchange:Ticker"` string key with back-compat deserializer for an old 6-bit packed format | `lib.rs:190-508` |
| `TickerInfo { ticker, min_ticksize, min_qty, contract_size: Option }` | — | subscription-time metadata; `is_perps()` | `lib.rs:515-550` |
| `Trade { time: UnixMs, is_sell: bool, price: Price, qty: Qty }` | — | aggressor side as a bool; no trade id | `lib.rs:552-558` |
| `Kline { time: UnixMs, open/high/low/close: Price, volume: Volume }` | — | constructed via `Kline::new` which **rounds all four prices to min tick**; `time` is the bucket open | `lib.rs:560-591` |
| `Volume::TotalOnly(Qty) \| BuySell(Qty,Qty)` | — | `total()`, `buy_qty()/sell_qty()`, `delta()`, `is_directional()`, `add_trade_qty(is_sell, qty)`; only Binance can populate `BuySell` from klines | `lib.rs:593-668` |
| `TickerStats { mark_price: Price, daily_price_chg: f32, daily_volume: Qty }` | — | change in **percent** (already ×100); volume is **USD notional** | `lib.rs:670-679` |
| `OpenInterest { time: UnixMs, value: f64 }` | — | raw number, not Qty | `lib.rs:681-685` |
| `DepthPayload { last_update_id: u64, time: UnixMs, bids: Vec<DeOrder>, asks: Vec<DeOrder> }` / `DepthUpdate::{Snapshot,Diff}` | | `DeOrder { price: f64, qty: f64 }` accepts `["p","q"]` arrays **or** `{"0":…,"1":…}` objects | `depth.rs:12-54` |
| `Depth { bids: BTreeMap<Price,Qty>, asks: BTreeMap<Price,Qty> }` | — | deletion = `qty == 0` → `remove(price)`; keys are always min-tick-rounded so float drift cannot duplicate a level; `mid_price()` | `depth.rs:56-146` |
| `LocalDepthCache { last_update_id: u64, time: UnixMs, depth: Arc<Depth> }` | — | `update(DepthUpdate)` → wholesale replace on Snapshot, patch on Diff; `Arc<Depth>` clone is O(1) for fan-out | `depth.rs:148-183` |
| `Event` | `Connected(Arc<[StreamKind]>)`, `Disconnected(Arc<[StreamKind]>, String)`, `DepthReceived(StreamKind, UnixMs, Arc<Depth>)`, `TradesReceived(StreamKind, UnixMs, Box<[Trade]>)`, `KlineReceived(StreamKind, Kline)` | one enum for every feed; `Arc`/`Box` payloads keep the hot path allocation-light | `adapter.rs:521-528` |
| `StreamKind` | `Kline{ticker_info, timeframe}`, `Depth{ticker_info, depth_aggr: StreamTicksize, push_freq: PushFrequency}`, `Trades{ticker_info}` | the subscription identity; also the *scope key* echoed on connect/disconnect | `adapter.rs:86-139` |
| `StreamTicksize { ServerSide(TickMultiplier) \| Client }`, `PushFrequency { ServerDefault \| Custom(Timeframe) }`, `TickMultiplier(u16)` with `multiply_step/unscale_step/_or_min_tick` | | user aggregation intent, resolved per venue | `adapter.rs:236-245`, `lib.rs:26-30`, `687-764` |
| `UniqueStreams` / `StreamSpecs` | — | global dedupe: `exchange → ticker_info → set<StreamKind>` with derived `Specs{depth, trade, kline}` per exchange, so N panes share one socket | `adapter.rs:141-234` |
| Capability tables | — | `is_depth_client_aggr` (HL only aggregates server-side), `is_custom_push_freq` (Bybit), `supports_heatmap_timeframe` / `supports_kline_timeframe` (per-venue exclusions incl. MEXC's missing 3m/2h/12h) | `adapter.rs:414-454` |

Timestamp rule of thumb (worth encoding as a Python invariant): **WS payloads are already ms** (`T`, `cts`, `start`, `ts`, `time`); the only seconds→ms conversions are `UnixMs::try_from_seconds` and binance's spot snapshot timestamp substitution.

---

## 5. Ranked reusable ideas for the OFAP Python feed layer

Ranking = (impact on data correctness/latency) × (fit to a FastAPI + pywebview app). "Risk" = risk of destabilising the working app if done incrementally.

| # | Idea | Why it beats the naive approach | Effort | Risk |
|---|---|---|---|---|
| 1 | **Never cancel an in-flight `recv()`** — dedicated reader task + separate heartbeat/deadline task; reconnect instead of desyncing (`ws.rs:629-711`, `784-797`). | `asyncio.wait_for(ws.recv(), t)` (or a shared "timeout" wrapper) cancels mid-frame, corrupts the frame assembler, then loops protocol errors → reconnect storms. Exactly the c1388d4 bug. | S–M | **Low** (isolated to the feed module) |
| 2 | **Depth sync state machine**: `WaitingSnapshot` buffers diffs (bounded, e.g. 512) while a REST snapshot is fetched *non-blockingly*, then replays in order; any sequence break → clear, resync, drop the offending event (`binance/stream.rs:528-693`, `mexc/stream.rs:470-640`). | Today's Bybit path applies deltas blindly (`bybit/stream.rs:423-441`) — one dropped frame silently corrupts the book and every atlas metric derived from it (CVD, liquidity, imbalances). | M | **Medium** (touches the live Bybit feed; ship behind a flag) |
| 3 | **Add Bybit `u` sequence-gap detection** (store `u`, require `u == prev_u+1`, else resync from a fresh snapshot). | Cheapest correctness win available for the existing venue; no protocol change, ~30 lines. | S | **Low–Medium** |
| 4 | **Heartbeat policy objects per venue** (periodic-text / ping-after-idle / server-driven, each with its own silence timeout) instead of a global timeout (`ws.rs:375-402`; per-venue table §1.2). | A global 30 s timeout kills healthy Binance perps sockets and masks slow Hyperliquid ones; per-venue policy is a one-file, data-driven change. | S | Low |
| 5 | **Backoff that only resets on real parsed data**, 500 ms→30 s, ±25 % jitter (`ws.rs:939-976`). | Naive "reset on connect" hammers dead venues and thundering-herds reconnects after a network blip. | S | Low |
| 6 | **Integer atomic units for price/qty** (price ×1e11, qty ×1e8) with explicit `round_to_step` and **side-aware** grouping (floor bids, ceil asks). | Kills float-key drift in the book and makes footprint/price-bucket keys exact; side-aware rounding removes the classic 1-tick mismatch between trades and book. | M–L | **Medium–High** (pervasive; do it for *new* storage + adapt at the boundary, not as a big-bang refactor) |
| 7 | **Trade batching per tick bucket** (per-ticker buffer, flush at a fixed ~33 ms tick; emitted timestamp = max trade time floored to the bucket) (`ws.rs:153`, `978-1033`). | Matches OFAP's channel throttling but with *correct* semantics: one event per symbol per frame, idempotent bucket timestamps, and buffered trades flushed on connect/disconnect so no gap at reconnects. | S | Low |
| 8 | **Bounded head-of-line drain** (handle up to N queued frames per wake) (`ws.rs:42`, `282-307`). | Bursts stop starving timers/flushes without unbounded work in one wake; protects the UI thread/async loop under a snapshot storm. | S | Low |
| 9 | **Snapshot-seed-before-subscribe** (`hyperliquid/stream.rs:354-417`): fetch the REST book, seed the cache, subscribe, emit the seeded book on connect. | First paint is deterministic and every reconnect self-heals; removes the "book appears only when a delta happens to arrive" problem. | S | Low |
| 10 | **REST per-venue worker: one task per venue owning client + limiter, `mpsc` + `oneshot` replies** (`adapter/http.rs:303-407`) with % headroom and header-driven dynamic weight (`limiter.rs:16-276`). | Serialises all REST for a venue with zero locks and a single place for retry/throttle policy; header-driven mode self-corrects when the venue changes weights. | M | Low–Medium |
| 11 | **Two-tier error surfacing**: rich log detail (method/URL/status/content-type/body preview/source chain) + a short user-facing message; detect HTML/non-JSON bodies (`error.rs:33-135`, `http.rs:169-250`). | Turns "feed is broken" into an actionable diagnosis (proxy page vs 429 vs venue outage) without leaking payloads into the UI. | S | Low |
| 12 | **Catalog metadata as subscription-time truth**: pull tickSize/minQty/contractSize (or derive them: HL 5-sig-fig rule, `hyperliquid/fetch.rs:403-441`) and gate the UI on venue capability tables (`adapter.rs:414-454`). | Prevents rendering impossible options (e.g. Bybit spot 200 ms heatmap) and makes price/qty rounding correct per instrument. | M | Low–Medium |
| 13 | **Global subscription dedupe + topic chunking** (unique streams across panes; ≤100 topics/socket) (`adapter.rs:141-234`, `client.rs:14-15`, `dashboard.rs:1344-1386`). | N panes on the same symbol cost one socket; chunking avoids venue-side topic limits. Partially present in OFAP already. | M | Medium (rewires subscription bookkeeping) |
| 14 | **Proxy/socks + credential hygiene**: CONNECT tunneling, socks5 vs socks5h (local vs remote DNS), four URL renderings (log/UI/key/full), creds in the OS keychain keyed by the no-auth URL, and a UI that shows Effective vs Pending with an explicit restart banner (`adapter/proxy.rs:85-753`, `data/src/config/auth.rs`, `src/modal/network_editor.rs`, `src/layout.rs:382-386`). | Users behind geo-blocks or corporate proxies currently have no path at all; the hygiene rules prevent credentials reaching logs or the DOM. | M | Low |
| 15 | **Single normalization choke point for volume** (`QtyNormalization`) + a process-wide Base/Quote display preference read at subscribe time (`unit/qty.rs:15-35`, `197-306`). | One place to fix when a venue reports contracts vs base vs quote; prevents "volume off by 1000×" classes of bug from spreading into the atlas. | M | Medium |
| 16 | **Internal vs display symbol split** (HL `@107` → `HYPEUSDC`) (`lib.rs:282-286`, `hyperliquid/fetch.rs:376-393`). | Essential if OFAP ever adds a venue with numeric/obfuscated IDs; keeps the internal key stable while the UI shows a real pair. | S | Low |
| 17 | **Venue capability/`market_kind` axis in the type system** (`Exchange` = venue × market kind; `QtyNormalization` branches on it) (`adapter.rs:309-419`). | Prevents inverse-perp math from silently reusing linear formulas when a new venue is added. | S–M | Low |
| 18 | **`Arc`-style cheap fan-out + event enum as the single feed contract** (`Event`, `Arc<Depth>`) (`adapter.rs:521-528`, `depth.rs:148-183`). | In Python: emit one immutable snapshot object per symbol per tick and let the atlas/UI subscribe; avoids N× copying of the book. | M | Low |

### What NOT to port
- **Silent drop of events on a full channel** (`ws.rs:216` + `let _ = send`). Fine for a chart, wrong for SQLite persistence and for atlas deltas; OFAP should use a bounded queue with an *explicit* overflow policy (block, or drop-with-counter, or the crate's `unbounded-channel` semantics) and record drops.
- **No-gap-delta application** (Bybit `stream.rs:423-441`, OKX `stream.rs:325-341`) — deliberately *not* a pattern to copy.
- **Per-venue parser tech** (`sonic_rs`, unsafe iterators, borrow tricks) — irrelevant in Python; the *design* is "single pass over the object, unknown keys ignored, unknown topic → log + continue, unknown-ticker event → fatal".
- Any literal code: the crate is GPL-3.0, so only ideas/algorithms cross into OFAP.

### Suggested landing order in OFAP (smallest safe steps first)
1. Reader/heartbeat task split + per-venue heartbeat policy (#1, #4, #5) — pure `bybit_feed.py` rewrite, testable with a local echo/fault-injecting WS server.
2. Bybit `u` gap detection + resync state machine (#3, then #2) — measure "resyncs/hour" as the health metric.
3. Trade bucket batching + drain + connect/disconnect flush (#7, #8).
4. Two-tier errors + REST worker/limiter (#11, #10).
5. Integer units at the *new* storage boundary and side-aware rounding (#6) — last, because it touches analytics.
