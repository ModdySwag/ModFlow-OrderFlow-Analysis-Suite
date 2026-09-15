# Alpaca Markets → ModFlow OrderFlow Analysis Suite: analysis and integration plan

Researched from alpaca.markets and docs.alpaca.markets, with the API's own behaviour
verified live from this machine (keyless crypto history, a rejected key pair, the news
endpoint's auth wall). Free-tier facts below are quoted from Alpaca's documentation, not
guessed.

---

## 1. What Alpaca actually is

Not a charting platform — a **brokerage exposed as an API**, and that is exactly what makes
it interesting for this program. Alpaca Clearing is a FINRA member and self-clears
(DTCC/FICC/OCC), with SIPC coverage; the Trading API is for individuals, the Broker API for
firms embedding investing.

Products that matter here:

| Product | What it gives a free account |
|---|---|
| **Trading API** | Commission-free US stocks & ETFs; multi-leg options; crypto 24/7; market/limit/stop/stop-limit/trailing-stop and bracket orders; fractional shares ($1 minimum, market orders); margin up to 4× intraday / 2× overnight; short selling |
| **Paper trading** | A full simulation environment, free to *anyone globally* with just an email address — same endpoints, virtual money, resettable at will |
| **Market Data API (Basic, free)** | US stocks & ETFs, history since 2016. Real-time = **IEX only**; full-market **SIP readable but older than 15 minutes**; **200 REST calls/min**; **30 websocket symbols**; options on the indicative feed |
| **News API** | Benzinga headlines (symbols, source, timestamps) — free with plan rate limits (200/min on Basic) |
| **Account/Portfolio APIs** | Account, positions, orders, account activities (fills, dividends, fees), **portfolio history** (equity curve), watchlists, **market calendar + clock**, assets (tradability, fractionability) |
| **Streams** | `trades`, `quotes`, `bars`, `updatedBars`, `dailyBars`, `statuses`, `luld` (halts), `corrections`; order updates via the trading stream; news stream. One connection per user on free plans |
| **Auth** | Key/secret pair per environment (`APCA-API-KEY-ID`, `APCA-API-SECRET-KEY`), or **OAuth ("Alpaca Connect")** for third-party apps holding a user's token |

Two facts that shape everything else:

1. **Alpaca publishes no order book.** Trades, quotes and bars only — no L2 depth, no DOM.
2. **The free feed is IEX** (one venue, a small share of consolidated volume), with the full
   tape available *delayed* by 15 minutes.

---

## 2. What it adds to this program — and what it cannot

### Adds

| Our module | What Alpaca unlocks |
|---|---|
| Instrument universe | US equities, ETFs, options and crypto — the largest reachable market this app has ever had, keyless **paper** trading included |
| Tape analytics (delta, footprint, VWAP, profiles, speed, big prints) | Feed from Alpaca trades+quotes instead of (or alongside) Bybit: real equities order-flow reads, aggressor classification against the NBBO quote |
| Scanner | Same columns, now including equities — one ranked table across crypto *and* stocks |
| Market context | Benzinga news replaces/joins the RSS headlines; the **market calendar and clock** finally tell the app when US equities are open (the app currently assumes a 24/7 market) |
| Portfolio (new) | Positions, open orders, fills, dividends/fees, and an **equity curve** from portfolio history — a broker view the program has never had |
| Trading (new, opt-in) | Orders through paper (default) or live: market/limit/stop/stop-limit/trailing, TIF, fractional/notional, close-position, cancel/replace — with the safety design in §5 |
| Alerts | Signal → paper order hooks, fill notifications back through the existing 4-channel notifier |
| Replay/history | Long, deep historical bars since 2016 for backtesting the equity instruments (IEX intraday); crypto history is keyless |

### Cannot add (stated plainly, in the UI too)

- **Order-book depth.** No heatmap, no DOM ladder, no stack/pull, no participants'-intent pressure on Alpaca symbols. Those views stay on the exchange feed + optional MT5 terminal, which do publish depth. The capability report in the app says this in the same list as the features.
- **Full-volume real-time tape on the free plan.** IEX is one venue; the consolidated tape is 15 minutes behind. Fine for context and for delayed study, thinner for live scalping — the app labels which feed a panel shows.
- **Options depth/real-time.** Indicative feed only on Basic.
- **US market hours.** Unlike crypto, equities close — the engine, alerts and UI must know it (`clock`).
- **Unlimited symbols on a stream.** 30 stream symbols on Basic: needs explicit, visible subscription management rather than "stream everything".

---

## 3. Architecture (how it lands in this codebase)

```
orderflow_system/
  desktop/alpaca.py            ← BUILT: client (urllib only), staged probe, capability report,
                                          positions/orders/portfolio history, rate limiter
  desktop/api.py               ← BUILT: /api/control/alpaca/{status,test,save,clear,portfolio}
  desktop/config_store.py      ← BUILT: alpaca block (paper flag, keys, view symbols)
  desktop/ui/alpaca.js         ← BUILT: the "add account" card, capability table, help hooks
  data/alpaca_feed.py          ← PHASE 1: bars/trades/quotes/stream adapter, session gating
  atlas/…                      ← PHASE 1+: the same analyzers fed by an Alpaca source
  desktop/ui/portfolio.js      ← PHASE 2: positions, orders, equity curve
  desktop/ui/trade.js          ← PHASE 3: order ticket + guardrails (paper first)
```

Design rules carried over from the rest of the app: no new dependencies (plain `urllib`),
secrets stay in the local config and are never displayed back, every capability failing
soft, and every screen that depends on a paid entitlement labelled as such.

---

## 4. Phased plan

**Phase 0 — Account linking (BUILT, verified)**
Key entry with environment toggle, `Validate` against the live API, staged errors
(`keys → auth → api → ready`) where the auth stage names the paper/live mismatch, capability
report (IEX realtime, SIP-delayed, news, calendar, options, positions, portfolio, crypto),
masked key display, "Remove keys", a how-to walkthrough, a wizard step, and search entries.
*Acceptance:* real invalid keys produce Alpaca's own 401 mapped to a human explanation
(done — verified against `paper-api.alpaca.markets`).

**Phase 1 — Data source (2-3 days)**
`AlpacaFeed`: REST polling for bars/trades within the 200/min budget, websocket streaming for
≤30 symbols with explicit subscription management, session gating via `clock`, symbol/tick-size
from `assets`, and a capability flag that disables depth-dependent views with a visible reason.
Kill switch: the engine simply does not start an Alpaca source without linked keys.
*Acceptance:* a US symbol streams through the existing analyzers (tape/delta/VWAP/profile/CVD),
the depth views say why they are unavailable, and the app survives a market close without noise.

**Phase 2 — Portfolio view (1-2 days, read-only)**
Positions with unrealised P&L, open orders, recent fills, dividends/fees from activities, and
the equity curve from portfolio history; refresh on demand. Endpoint already built.
*Acceptance:* numbers reconcile against the Alpaca dashboard for the linked account.

**Phase 3 — Paper trading (3-4 days, opt-in)**
Order ticket (symbol, side, qty or notional, type, TIF, optional bracket), order management
(cancel, replace, close position), order-lifecycle stream for fills, and guardrails: paper by
default, live requires an explicit second confirmation + a typed phrase, per-order notional cap,
daily order cap, a global kill switch, and a banner that cannot be missed when live is armed.
*Acceptance:* a paper round-trip (entry → fill → close) from the app, with the guardrails
refusing an over-cap order in a test.

**Phase 4 — Context and automation (2 days)**
Benzinga news into the market-context panel; calendar/holiday awareness surfaced in the UI
("market closed — next open 13:30 UTC"); alert rules gain an optional "paper order" action
(kind `alpaca_order`) with the same guardrails and a mandatory dry-run mode.

**Phase 5 — Optional / later**
OAuth (Alpaca Connect) instead of raw keys, if the app is ever distributed as a registered
OAuth app; crypto via Alpaca as a secondary venue; options chain analytics (indicative feed
limits the value, so this ranks last).

---

## 5. Safety and governance (the part that must not be skipped)

The program has been deliberately **read-only** until now — no orders, no account, nothing to
lose. Adding a brokerage changes that, so the trading path is designed with the same honesty
as the analytics:

1. **Paper is the default, and live needs a ceremony**: separate confirmation, a typed phrase,
   and a persistent red banner while armed.
2. **Hard caps**: max notional per order, max orders per day, allowed symbols list, and a kill
   switch that cancels nothing but refuses everything.
3. **No advice, no auto-pilot by default**: alert-driven orders are opt-in per rule, dry-run
   first, and every order is visible in a log with the reason it was placed.
4. **Data licensing**: SIP data may not be redistributed; the app displays it, never republishes
   it, and labels the 15-minute delay. Attribution stays visible.
5. **Not investment advice** stays in the UI, unchanged from the existing disclaimer position.
6. **Secrets**: keys live in the local config only, are never echoed back, and the search action
   "Clear stored alert credentials" is joined by "Remove keys" in the account card.

---

## 6. Risk register

| Risk | Mitigation |
|---|---|
| IEX-only free data misread as the whole market | Label the feed per panel; show IEX share of volume in context notes |
| 15-minute delay unnoticed | Any SIP-sourced panel shows its timestamp and delay |
| 30-symbol stream limit hit silently | Subscription manager refuses silently-ignored symbols and reports the list |
| Rate limit (200/min) exceeded by polling | Client-side limiter at 150/min (built), backoff on 429 |
| Wrong-environment keys | Staged probe names it (built, verified) |
| Paper vs live confusion | Environment pill in the account card and in the title bar when live |
| Market closed → empty panels look broken | Clock-driven "market closed" state instead of an empty table |
| Options indicative data treated as real | Labelled, and ranked last in the plan for that reason |

---

## 7. Bottom line

Alpaca is the first integration in this project that brings an **execution surface and a real
broker account** rather than more data. It complements what is already here instead of
overlapping it: Bybit and MT5 keep the depth-dependent order-flow reads, Alpaca brings US
equities/ETF/options instruments, a real-time (if single-venue) tape, full-market delayed
history, news, the market calendar, and — through paper trading — a way to act on the reads
without risking a cent.

Phase 0 is built, wired into the app and verified against Alpaca's real API. Phases 1-4 are
scoped in §4 with acceptance criteria; the honest constraint that shapes them all is the one
in §2: no order book, so no heatmap on these symbols.
