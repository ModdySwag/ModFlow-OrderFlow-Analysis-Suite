# Alpaca data feed — reference

How Alpaca feeds this program, what it can and cannot do, and every limit that
shapes the design. Written for whoever has to debug it next (probably me, six
months from now).

The account side — keys, environments, capability probe, portfolio read — lives in
`orderflow_system/desktop/alpaca.py` and the Alpaca view. The market-data side lives
in `orderflow_system/data/alpaca_feed.py` (+ `alpaca_normalize.py`), and is what this
document covers.

---

## 1. Where Alpaca sits in the data model

    AlpacaFeed ── REST (urllib, budgeted) ──▶ snapshots / bars / history
               └─ Stream (websockets)     ──▶ trades, quotes  ──▶ on_tick(app_symbol, Tick)
                                                                        │
                            OrderflowSystem._on_tick ─────────────────────┘
                                    │
              candles · footprint · delta · CVD · VWAP · profile · scanner · alerts · DB

The feed speaks the same contract as the Bybit and MT5 feeds: an async
`on_tick(app_symbol, tick)` callback. Everything downstream is unchanged, which is
the point — Alpaca adds instruments, not a second analytics stack.

**Only mapped symbols are ever requested.** The map is `app symbol → Alpaca symbol`
(`ALPACA.symbols` in `config/settings.py`, overridable per instrument with
`alpaca_symbol` in `config.json`):

| app | Alpaca |
|---|---|
| AAPL, MSFT, NVDA, SPY, QQQ … | the same ticker |
| BTCUSDT | BTC/USD |
| ETHUSDT | ETH/USD |
| SOLUSDT | SOL/USD |

## 2. What Alpaca publishes — and the one thing it does not

| data | available | notes |
|---|---|---|
| trades (tape) | ✅ | equities IEX-only on Basic; crypto 24/7 |
| quotes (NBBO) | ✅ | used for trade-side classification |
| bars (1Min…) | ✅ | history back to 2016 |
| snapshots | ✅ | cheapest way to warm a chart (batched, 1 call per 1000 symbols) |
| news, calendar | ✅ | via `desktop/alpaca.py` |
| **order book (depth)** | ❌ | **not published on any plan.** The heatmap, the DOM ladder and the participants'-intent reader cannot run on Alpaca data |

That last row is the honest limit, and it is reported in
`/api/control/capabilities → alpaca.depth = false` + `depth_reason`, and shown in
the heatmap/depth views for Alpaca symbols instead of an empty canvas.

## 3. REST client (`AlpacaData`)

| endpoint | path | auth |
|---|---|---|
| market clock | `api.alpaca.markets/v2/clock` | keys |
| assets | `api.alpaca.markets/v2/assets` | keys, cached 24 h on disk |
| bars | `data.alpaca.markets/v2/stocks/{sym}/bars` | keys |
| trades | `data.alpaca.markets/v2/stocks/{sym}/trades` | keys |
| snapshot(s) | `data.alpaca.markets/v2/stocks/{sym}/snapshot`, `/v2/stocks/snapshots?symbols=…` | keys |
| crypto bars | `data.alpaca.markets/v1beta3/crypto/{loc}/bars` | **no keys** |

Rules the client enforces:

* **Client budget 150 calls/min** (`RateBudget`, below the plan's 200/min) with 429
  backoff that honours `Retry-After`. The app also polls its own panels; a
  self-inflicted 429 would look like an outage.
* **Bars need an explicit window.** Alpaca pages *forward* from `start`, so a bare
  `limit` returns the **oldest** bars it has. `seed_history()` always sends
  `start = now − history_minutes` and `end = now` (a first smoke seeded yesterday's
  tape before this was fixed).
* **No clock, no hot loop.** The clock is re-read each poll; when the session is
  closed the snapshot cadence drops to ≥30 s (≥60 s without keys, since every call
  would be a 401).
* **Keyless means no polling at all.** Crypto *history* works without keys; every
  other call is refused with 401, so `poll_once()` short-circuits with
  `needs_keys = true` instead of burning the budget.

## 4. Stream client (`AlpacaStream`)

One socket per asset class, never `*` subscriptions:

| stream | URL | channels used |
|---|---|---|
| equities | `wss://stream.data.alpaca.markets/v2/{iex\|sip\|delayed_sip}` | `trades`, `quotes` (also available: `bars`, `dailyBars`, `updatedBars`, `statuses`, `lulds`, `imbalances`) |
| crypto | `wss://stream.data.alpaca.markets/v1beta3/crypto/us` | `trades` |
| sandbox | `wss://stream.data.alpaca.markets/v2/test` | `trades` (`FAKEPACA`) |

* **Auth goes first**, deadline 10 s, and every reconnect re-authenticates
  immediately (tokens are per-connection).
* **Reconnect** with exponential backoff (1 s → 30 s max). Credential/plan errors
  (401/402/403) are **fatal** — retrying a wrong key pair forever is a bug, not
  resilience.
* **The sandbox stream needs keys too.** Verified live: a keyless connect to
  `/v2/test` is refused with `[401]`. `RUN_ALPACA_TESTSTREAM=1` runs the check.

### Stream error codes → what the user is told

| code | meaning | message shown |
|---|---|---|
| 400 | malformed message | unknown symbol or channel name |
| 401 | not authenticated | the key pair was rejected (paper keys only work on paper) |
| 402 | auth failed | re-check the secret in the Alpaca view |
| 403 | not entitled | SIP/OPRA need a paid plan |
| 404 | unknown symbol | check the ticker (`BTC/USD`) |
| 405 | too many symbols | the plan's stream limit was reached |
| 406 | channel not included | this plan does not include that channel |
| 407 | slow client | Alpaca dropped the connection; it reconnects |
| 409 | connection limit | one stream connection per key at a time |
| 413 | message too large | — |
| 500 | Alpaca internal error | reconnects automatically |

## 5. Subscriptions (`SubscriptionSet`)

* Caps: **30 stream symbols** on Basic (equity quote cap 200 for options), taken
  from the plan's own limit payload when known.
* `add`/`remove` are **idempotent** — the UI may call them on every change.
* Over-cap adds **trim the oldest symbol and say so** (`warnings`, surfaced in the
  feed card). Nothing is ever dropped silently.
* Endpoints: `GET/POST /api/control/alpaca/subscriptions`
  (`POST {channel, add:[…], remove:[…]}`).

## 6. Enabling it

1. Link the account in the **Alpaca** view (rail, or `Alt+A`) — paper keys are free.
2. Settings → **Data source** → `Alpaca` (or `All` for exchange + Alpaca together).
3. Enable the instruments (`Instruments` view) — each needs an Alpaca symbol.
4. Start the engine. The Alpaca view's **Live feed** card shows market state, the
   REST budget, per-stream state and the subscription set.

Without keys the engine still starts: crypto history seeds (real bars), and the
streams report the mapped 401 instead of failing silently.

## 7. Open items

* **Live option quotes** are out of scope (plan decision D-A): Alpaca's option
  stream is MsgPack-only and would add a dependency. Option *trades* over REST are
  available for history.
* **Equity live path needs a paper key run** (plan T30): the analyzers, subscription
  caps and error handling are all exercised offline and on crypto, but a real IEX
  session is the last unverified step.
* One anomaly is still open from the keyless smoke: `/api/footprint` served 200
  identical bars whose timestamp matched the first seeded bar, while the same run
  persisted 237 distinct per-minute candles to SQLite and an in-process replay of
  the identical seed path produced 237 distinct footprint bars. Repro notes live in
  the plan's execution log; re-test with keys before drawing conclusions.
