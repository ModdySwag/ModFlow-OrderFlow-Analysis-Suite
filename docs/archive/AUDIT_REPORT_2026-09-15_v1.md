ModFlow OrderFlow Analysis Suite — Audit & Enhancement Report
Combined from: desktop/code.txt (reference advice), desktop/report.txt (prior codebase audit), and a fresh line-level pass over the actual source.

Date: 2026-09-15
Scope: C:\Users\<you>\OrderFlow-Analysis-Pro — all app-authored code.

─────────────────────────────────────────────────────────────────────────────
1. WHAT YOU ALREADY HAVE THAT IS GOOD (DON'T TOUCH WITHOUT REASON)
─────────────────────────────────────────────────────────────────────────────

- Alpaca integration (desktop/alpaca.py) is the right shape: plain urllib, real
  rate limiter, staged probe that names which piece failed, key masking, honest
  capability report that explicitly says Alpaca has no order book. The JS card
  (alpaca.js) shows account + capabilities + limits in one place. This is the
  benchmark the rest of the app should match.

- Search (desktop/ui/search.js) is already the best-executed part of the UI: one
  box that indexes views, panels, actions, settings controls, select options,
  alert kinds, rules, help topics, guide sections, instruments. Scoring rewards
  title matches and position; 60-result cap; keyboard nav; hover tooltips;
  indexes live DOM controls by scraping at build time. Performance is fine.

- Config model is cleanly separated: desktop/config_store.py keeps user config in
  the per-user directory, writes atomically via tmp+replace, sanitises input,
  derives defaults from the repo settings module. The launcher translates JSON
  onto dataclasses at runtime — the user never edits Python source. Correct.

- Analytics core is sound: models.py uses slots on hot dataclasses (Tick,
  OrderbookLevel). database.py is async SQLite with WAL, busy_timeout, NORMAL
  sync, indexed tables. bybit_feed.py reconnects with exponential backoff,
  handles snapshot vs delta book, buffers ticks for batch insert. Pattern
  detectors follow Fabio logic and produce typed Signals. volume_profile.py has
  a fallback chain: live candle history → DB profiles by days, with POC/VAH/VAL
  and shape detection.

- Tests exist and are honest: test_alpaca.py (stub transport, staged probe,
  key-masking, rate-limiter behaviour), test_integration.py (pipeline on
  synthetic ticks/candles, asserts POC/delta/absorption/initiative/profile
  framing/DB insert/candle building), audit_ui_refs.py (JS API paths vs
  FastAPI routes, element ids vs DOM).

- Onboarding/docs: docs/USER_GUIDE.md is practical and in your voice. The setup
  wizard in guide.js is real and detailed. Tooltip coverage in guide.js is
  unusually thorough.

─────────────────────────────────────────────────────────────────────────────
2. THE ONE REAL DEFECT — LIVE/DEMO SPLIT (P1, HIGH)
─────────────────────────────────────────────────────────────────────────────

This is the main event. The desktop dashboard has a demo data layer that works,
and the live engine feeds some things via WebSocket (tick, candle-close only if
the callback fires, orderbook, signals), but several REST endpoints used to
initially fill views return demo data in live mode because the underlying live
data path is not fully wired.

Concrete evidence:

- main.py defines _on_candle_close_handler (line 464) — the method that inserts
  closed candles into SQLite and broadcasts candle/delta over the dashboard
  WebSocket. But nothing calls it. The pipeline's on_candle_close callback is
  never pointed at it in the live path.

- desktop/engine.py:_wire_candle_persistence (line 312) exists specifically to
  compensate for this. Its own comment (lines 313-323) describes the exact
  failure mode: "the database never accumulates candles, so the hourly volume
  profile rebuild always finds < 10 candles, no profile/bias/qualified level is
  ever produced, and the trade state machine can never fire."

- dashboard/app.py has two TODOs left in the live path:
  - /api/tape — "TODO: return real tape from live feed buffer" (line 912)
  - /api/microstructure — "TODO: pull real microstructure state from pipeline"
    (line 922)

- /api/footprint/{symbol} (line 890) falls through to
  demo_data.demo_footprint() even when system is running (line 903) — it checks
  for system but then ignores the pipeline and returns demo.

- /api/volume-profile/{symbol} reads from pipeline.candle_builder for range-based
  VP, which is correct, but the DB-profile fallback path still depends on candles
  having been persisted — which is the same gap.

The UI already warns the user about this directly:
- footprint: "in a live session /api/footprint still returns the built-in demo
  generator … Treat footprint levels as illustrative until that endpoint is wired
  to the engine."
- tape: "Initial tape fill comes from /api/tape, which is still a demo generator
  in live mode … new prints arriving over the WebSocket ARE real."

So: the engine's own analytics (delta, footprint, patterns, profile framing) do
run on real ticks. What is missing is the bridge between those live structures
and the dashboard REST/WS surface the UI reads.

What to fix, in order:

2.1 Wire the candle-close path end-to-end.

The desktop/engine.py:_wire_candle_persistence wrapper is the right shape — it
chains persistence + broadcast onto the pipeline callback without re-running the
analytics pass. Verify that it is actually being called in the desktop start
path. In engine.py line 492, _wire_candle_persistence(system) is called inside
EngineController.start() — so the desktop build does wire it. The question is
whether the original main.py path (when running without the desktop launcher) is
ever used in practice. If the desktop build is the canonical one, then the fix
is in main.py: point the pipeline's on_candle_close callback at
_on_candle_close_handler, OR move the persistence+broadcast logic into the
callback itself and delete the separate handler.

Recommended: in main.py InstrumentPipeline.__init__, the on_candle_close
parameter is already set to self._on_candle_close (line 80). The CandleBuilder
calls this callback when a candle closes. But InstrumentPipeline._on_candle_close
(line 127) only runs analytics and returns signals — it does NOT persist the
candle or broadcast it. The persistence+broadcast lives in
OrderflowSystem._on_candle_close_handler (line 464), which is a separate method
on the system that nobody calls.

Cleanest fix: have InstrumentPipeline._on_candle_close call back to the system
for persistence+broadcast, OR have the system's _on_candle_signals callback
(which IS wired at line 219) also handle the candle. The current design already
has _on_candle_signals as the wired callback — it receives signals, not
candles. The candle itself is available inside _on_candle_close before signals
are produced.

Minimal change that closes the gap: in InstrumentPipeline._on_candle_close, after
computing signals, call a system method that persists the candle and broadcasts
it. The system method already exists as _on_candle_close_handler — wire it.

2.2 Wire /api/tape and /api/microstructure to live data.

For tape: the engine already receives ticks via _on_tick. Buffer the last N ticks
per symbol in the pipeline (or system), expose them through a method, and have
/api/tape/{symbol} return them instead of demo_tape_trades when system is running
and the buffer has data.

For microstructure: /api/microstructure/{symbol} should read from the pipeline's
current state — the latest footprint bar, the delta engine's last result, the
pattern detectors' last signals, the absorption/initiative/sweep/exhaustion/
divergence detectors. All of this is already computed on every candle close. The
endpoint just needs to read it instead of falling through to demo.

2.3 Make the live/demo state visible in one place.

Right now the UI has per-panel warnings. Replace with a single coherent status
that the UI reads: "live" (all endpoints wired), "partial" (some endpoints still
demo — name which ones), "demo" (engine not running). The engine controller knows
which endpoints are wired; expose that as a capability the dashboard reports.

─────────────────────────────────────────────────────────────────────────────
3. PER-INSTRUMENT CONFIG — MECHANICALLY REPETITIVE (P2)
─────────────────────────────────────────────────────────────────────────────

config/settings.py is 1017 lines, nearly all per-instrument config factory
functions. There are ~27 functions doing a job a loop and a per-class override
map could do:

- get_nas100_config, get_sp500_config, get_dj30_config, get_uk100_config,
  get_dax40_config, get_nikkei225_config, get_cac40_config, get_asx200_config,
  get_hk50_config — indices
- get_gold_config, get_silver_config — metals
- get_usoil_config, get_ukoil_config — energy
- get_eurusd_config … get_gbpjpy_config — forex (10 functions, 8 of which are
  _forex_major_config with two overriding tick_size/vp_tick_size args)
- get_aapl_config … get_googl_config — stocks (7 functions, all identical
  _stock_config)
- get_btcusd_config + get_crypto_config for each CRYPTO_MAJOR

What's actually different between NAS100 and SP500 and DJ30? tick_size (0.1, 0.1,
1.0), a few threshold values, vp_tick_size (1.0, 1.0, 5.0), session type.

Recommended: a single class-level default map plus a small override table.

from dataclasses import dataclass, field
from typing import ClassVar

@dataclass
class InstrumentDefaults:
    tick_size: float
    vp_tick_size: float
    session: SessionType
    absorption: AbsorptionConfig
    initiative: InitiativeConfig
    sweep: SweepConfig
    exhaustion: ExhaustionConfig
    divergence: DivergenceConfig

class DefaultBank:
    INDICES = InstrumentDefaults(tick_size=0.1, vp_tick_size=1.0, session=SessionType.NY_CASH, ...)
    METALS = InstrumentDefaults(...)
    FOREX_MAJOR = InstrumentDefaults(...)
    STOCKS = InstrumentDefaults(...)
    CRYPTO = InstrumentDefaults(...)

INSTRUMENT_OVERRIDES = {
    Instrument.NAS100USDT: {"tick_size": 0.1},
    Instrument.DJ30: {"tick_size": 1.0, "vp_tick_size": 5.0},
    Instrument.NIKKEI225: {"tick_size": 1.0, "vp_tick_size": 50.0, "session": SessionType.ASIAN},
    Instrument.USDJPY: {"tick_size": 0.001, "vp_tick_size": 0.05},
    ...
}

def get_config_for(instrument: Instrument) -> InstrumentConfig:
    bank = _pick_bank(instrument)
    overrides = INSTRUMENT_OVERRIDES.get(instrument, {})
    return InstrumentConfig(
        instrument=instrument,
        tick_size=overrides.get("tick_size", bank.tick_size),
        ...
    )

This cuts the file from ~1000 lines to ~200 and makes adding an instrument a
one-line entry in the override map. The existing behaviour is preserved exactly.

Note: the per-instrument thresholds are already largely identical within asset
classes — the _forex_major_config and _stock_config helpers show the pattern.
The only thing keeping the per-function duplication alive is historical
thumb-tweaking of a few numbers per instrument. The override map captures that
without the boilerplate.

─────────────────────────────────────────────────────────────────────────────
4. ALPACA — MAKE IT EASY TO FIND AND ACCESS (P3)
─────────────────────────────────────────────────────────────────────────────

The Alpaca card (alpaca.js) is well-built but buried: it appears in the Settings
view, created at runtime by alpacaEnsureCard() when the settings view opens. A
user who doesn't know to look in Settings will not find it.

4.1 Put an Alpaca status card on the main dashboard landing.

Add a compact card to the Overview view (or a dedicated "Broker" rail item) that
shows:
- Status pill: Not Connected / Paper Connected / Live Connected (reuse
  alpacaStatusPill())
- One-line capability summary: "IEX real-time · SIP delayed 15min · News · Options
  (indicative)"
- A single button: "Open Alpaca setup" → jumps to the settings view and opens the
  Alpaca card.

This card is the front-page equivalent of what alpaca.js already renders in
settings. Reuse the same styling and logic; don't duplicate the capability
rendering.

4.2 Add a top-level "Alpaca" nav item.

Currently the rail has Settings as the only path to Alpaca. Add a dedicated
nav item (between Instruments and Settings, or after Settings) that opens a view
with the Alpaca card as the primary content, plus a link back to settings for the
rest of the config. The rail item gets a tooltip via TIPS in guide.js:
'.nav-item[data-view="alpaca"]': 'Link a US brokerage account: stocks, ETFs,
options, crypto, news, calendar, portfolio. Free paper trading.'

4.3 Persistent banner when Alpaca is not configured.

Show a dismissible banner on the Overview when Alpaca is not connected:
"Connect Alpaca to enable US equities, options, news and the market calendar.
[Set up now]" → opens the Alpaca view. Dismissible (store in localStorage or
config), re-appears on next session if still not connected.

4.4 Keyboard shortcut.

Alt+A (or Ctrl+Alt+A) jumps straight to the Alpaca setup view. Add to the
keyboard handlers in the UI shell.

4.5 Search already indexes "Alpaca account" — make it land on the card, not just
the settings view.

search.js line 149 indexes 'Alpaca account' under Panels → settings. The run
callback does window.showView('settings'). Improve it: after showing settings,
wait for the Alpaca card to render and focus the key input. Or, if the Alpaca
view exists (4.2), point there directly.

─────────────────────────────────────────────────────────────────────────────
5. ALPACA SETUP WIZARD FLOW (P4)
─────────────────────────────────────────────────────────────────────────────

The current wizard (guide.js WIZ_STEPS) covers: data source → instruments →
feeds/history/extras → alerts → market context → ready. Alpaca is not in the
wizard at all — it's a post-setup step in Settings.

Recommended: add an optional Alpaca step to the wizard, placed after instruments
and before alerts. It should be skippable and not block the wizard if the user
doesn't have Alpaca keys yet.

Step: "Alpaca (optional)" — content:

5.1 What Alpaca adds.

One paragraph: "Alpaca is a real US brokerage with an API — commission-free stocks,
ETFs, options and crypto, plus a free paper-trading account you can open with just
an email address. Linking adds US equities, options and crypto instruments to the
scanner, a real-time IEX tape (30 symbols on the free plan), 15-minute-delayed
full-market history, Benzinga news, the US market calendar, and — later — orders,
positions and P&L. Nothing here requires it; the app works without one."

5.2 Step 1 — Sign up / paper account.

Call-to-action: "Create a free Alpaca paper-trading account" with a link to
https://app.alpaca.markets/signup. Note: paper trading is free, no funding needed,
just an email. If the user's country isn't listed under Country of Tax Residence,
they get paper-only access.

5.3 Step 2 — Get API keys.

Walk through: log in → Home → generate API Key and Secret Key. Critical warning:
Secret Key is shown only once — store it securely. If regenerated, all connected
apps must be updated.

5.4 Step 3 — Paper vs Live toggle.

Explain the difference. Paper: paper-api.alpaca.markets, free IEX real-time data,
$100k default paper balance, resettable. Live: api.alpaca.markets, requires funded
brokerage account (Alpaca Securities LLC, FINRA/SIPC member), KYC/onboarding.
Provide a toggle. When Paper is selected, pre-fill the environment.

5.5 Step 4 — What the account can reach (capability preview).

Before the user even pastes keys, show what each plan tier gives:
- Free / Paper: IEX real-time stocks only, SIP history 15-min delayed, Indicative
  options feed, 30 WebSocket symbols, 200 REST calls/min, news included.
- Algo Trader Plus ($99/mo): all US exchanges (SIP) real-time, OPRA options feed,
  unlimited WebSocket symbols, 1000 option quotes, 10000 REST calls/min, no
  historical restriction.

Note: Alpaca publishes trades, quotes and bars — no order book. The heatmap, DOM
ladder and participants'-intent reader cannot run on Alpaca data. This is the
honest caveat the backend already reports; surface it here too.

5.6 Step 5 — Paste keys and test.

Two text fields (key ID, secret) with show/hide toggle. Environment toggle
(paper/live). "Test connection" button → calls /api/control/alpaca/test,
displays the staged result (keys → auth → api → ready), shows the capability
report. On success: "Connected to Alpaca Paper Account. Your account has IEX
real-time stock data and Indicative options data." → save.

5.7 Step 6 — Done / upgrade path.

If on paper and the user wants live: link to Alpaca's live account onboarding.
Note the $2,000 equity threshold for margin and short selling, $30,000 minimum for
business accounts.

Wizard persistence: if the user needs to go sign up for Alpaca mid-flow, save the
wizard state so they can resume.

─────────────────────────────────────────────────────────────────────────────
6. SEARCH FUNCTION — REDESIGN FOR ORDER-FLOW POWER USERS (P5)
─────────────────────────────────────────────────────────────────────────────

The current search is already slick. The missing leap is live, updatable targets
and deeper symbol reach. This section is the "slick for experienced users" work.

6.1 What the search should reach, beyond what it already does.

Currently indexes: views, panels, actions, settings controls, select options,
alert kinds, rules, help topics, guide sections, instruments.

Add:

6.1.1 Live Alpaca symbol search.

A new result category: "Alpaca symbols". When the user types a ticker, the search
returns Alpaca symbols (stocks, ETFs, options contracts, crypto) with:
- Symbol, name, asset type (equity/option/crypto).
- Live bid/ask/last if the Alpaca stream is connected and the symbol is
  subscribed.
- Feed chip: IEX / SIP / Indicative / OPRA / Crypto Alpaca / Crypto Kraken /
  Delayed SIP — honest about what the user's plan supports.
- Market status dot: open / pre-market / after-hours / closed / halted.
- Mini sparkline from recent bars.

This requires the shared Alpaca stream connection (see 6.3) and the search
subscribing to the queried symbol on the existing stream, not opening a new
socket.

6.1.2 Search result → live view.

A search result for a symbol should do more than switch the app to that symbol.
It should:
- Switch the instrument selector to that symbol.
- Open the most relevant view (footprint for order-flow users, tape for tape
  users, chart for chart users — or a configurable default).
- If the symbol is an equity with options, offer "View option chain" as a
  secondary action.

6.1.3 "Open Alpaca setup" as a first-class search result.

Right now "Alpaca account" is under Panels → settings. Promote it: a dedicated
Actions result "Open Alpaca setup" that jumps to the Alpaca view (or settings +
Alpaca card focused).

6.1.4 Index the Guide's "How to get keys" entries as individual searchable
targets.

alpaca.js line 108 has data-help="alpaca" on the "How to get keys" button. The
search indexes HELP_TOPICS (walkthroughs) but the how-to section is built
separately. Add the Alpaca how-to as a searchable Help result: title "Alpaca:
how to get API keys", desc "Create a paper account, generate keys, paper vs live,
what the free plan can reach.", keywords "alpaca broker keys paper trading signup
account".

6.2 Command-palette style (⌘K / Ctrl+K / /) — already done.

The current search already opens on Ctrl+K and /. That's the command palette. The
work here is enriching the results, not changing the entry.

6.3 Single shared Alpaca stream connection for live search.

Most Alpaca plans (including Algo Trader Plus) allow only 1 WebSocket stream
connection per endpoint. The search must not open a new socket per symbol lookup.

Architecture:
- On Alpaca connect: open one authenticated stream per asset class the user wants
  live data for (StockDataStream for equities, OptionDataStream for options,
  CryptoDataStream for crypto, NewsDataStream for news). The connection limit
  applies per endpoint — for a Basic user, you may only keep one alive. The UI
  should let the user prioritise which live feed to keep active.
- On search: subscribe to the queried symbol on the relevant stream via the
  existing connection (action: "subscribe", quotes: [symbol], trades: [symbol]),
  update the result row's live fields, keep the subscription for as long as the
  symbol is in the active set (recently searched, watched list).
- On search clear / symbol leave: unsubscribe (action: "unsubscribe").
- Throttle UI updates to ~200-500ms per symbol row.
- Authenticate once at stream startup, within 10 seconds of connect. On reconnect,
  re-auth immediately.

This is exactly the multiplexing pattern described in code.txt section 4.2.3.

6.4 Symbol discovery / autocomplete source.

For autocomplete as the user types, combine:
- Local cache of previously searched / watched symbols (fast, offline).
- Alpaca asset lookup: TradingClient.get_assets() to enumerate available
  stocks/ETFs, filter by symbol/name match.
- Options contract search: for an underlying like AAPL, query
  OptionHistoricalDataClient.get_option_chain() to list available strikes/
  expirations. Show in an expandable sub-list under the underlying.
- Crypto symbol list: Alpaca's crypto universe (~20 symbols: BTC/USD, ETH/USD,
  AVAX/USD, BAT/USD, MKR/USD, CRV/USD, etc.). Show with venue badge (Alpaca US
  vs Kraken US vs Kraken EU).
- Fuzzy matching: for partial/approximate symbols (e.g. NAS100, USTEC, NQ), fuzzy
  match against the asset list and against any internal instrument aliases the
  system maintains.

6.5 "Expanded search" — advanced operators.

A collapsible section (click a chevron or press Shift+Enter) that exposes:

Multi-symbol entry: type or paste a comma-separated list (AAPL,MSFT,GOOGL) and add
all at once to a comparison view or watchlist.

Search operators (mini query language):
- exchange:iex / exchange:sip / exchange:opra / exchange:indicative — filter by
  available feed.
- type:stock / type:option / type:crypto.
- underlying:AAPL — for options, show all contracts for that underlying.
- exp:max / exp:min — sort options by expiration.
- strike:>200 / strike:<50 — filter options by strike.
- vol:>1M — filter stocks by approximate volume.

Sort options: by symbol, by name, by last price, by % change, by volume, by feed
priority.

Watchlist quick-add: Ctrl/Cmd+Click multi-select rows, apply all to a watchlist or
multi-symbol view.

Recent / pinned section: recently searched symbols and user-pinned favorites at
the top, above live results.

6.6 Live-updatable result rows.

When a symbol is in the active set, its row updates live:
- Quote updates: bid/ask from the quotes channel, with bid/ask size.
- Trade updates: last sale from the trades channel; highlight big trades.
- Bar updates: minute bars from bars, daily bars from dailyBars, late-trade
  updates from updatedBars (important for order-flow accuracy — a trade
  timestamped 16:49:59.998 arriving after 16:50:00 triggers an updatedBars
  message).
- Status updates: trading halts, LULDs, order imbalances — surface prominently
  (red "HALTED" badge).
- News badge: if the news stream delivers an article mentioning the symbol, show a
  small "NEWS" badge with headline snippet.

6.7 Option chain search.

For experienced options flow users, searching an underlying (e.g. AAPL) should
offer an expandable option chain panel:
- Strikes as columns, expirations as rows (or vice versa), with live bid/ask at
  each contract from the quotes channel (Indicative or OPRA, as available).
- Click a strike to search that specific contract symbol.
- "Search nearest OTM/ATM/ITM" quick buttons.
- Greeks / IV if available from OptionHistoricalDataClient.get_option_snapshot().

Note: option stream is MsgPack only and star-subscription is disallowed for option
quotes. The UI must subscribe to individual contract symbols and reflect the user's
quote limit (200 for Basic, 1000 for Algo Trader Plus).

6.8 Multi-feed comparison (advanced).

For users with Algo Trader Plus, allow comparing the same symbol across feeds:
- IEX vs SIP for equities.
- Indicative vs OPRA for options.
- Alpaca crypto vs Kraken crypto (us vs us-1/eu-1).
Show a small delta / discrepancy indicator between feeds when both are
subscribed.

6.9 Keyboard-driven interaction.

- ⌘K / Ctrl+K / / — open search palette (done).
- ↑ / ↓ — navigate results (done).
- Enter — open selected symbol in current workspace (done for instruments; extend
  to Alpaca symbols).
- Ctrl+Enter / Cmd+Enter — open in new panel/tab.
- Ctrl+Shift+Enter — open option chain (for equities).
- Ctrl/Cmd+Click — multi-select for watchlist.
- Esc — close palette (done).
- Shift+Enter — toggle expanded search.
- / in a symbol input field — focus search with current text as query.

6.10 Performance.

- Debounce autocomplete ~150ms; throttle live quote updates ~200ms per row.
- For Basic users, don't silently exceed the 30-symbol stock / 200-quote options
  limit. Warn when approaching the cap; suggest removing a symbol or upgrading.
- Backpressure: if the stream sends data faster than the UI can consume, Alpaca
  may send 407 slow client. Keep the frontend lean: update only visible rows, use
  canvas for sparklines, virtualize long lists. In the backend, enqueue stream
  messages to a ring buffer and let the UI poll or receive batched updates.

─────────────────────────────────────────────────────────────────────────────
7. ALPACA REFERENCE — KEY INTEGRATION POINTS (FROM CODE.TXT)
─────────────────────────────────────────────────────────────────────────────

7.1 Python SDK clients to use (alpaca-py).

- Trading (orders, account, positions): TradingClient(api_key, secret_key,
  paper=True/False)
- Stock historical bars/quotes/trades/snapshot/option chain:
  StockHistoricalDataClient(api_key, secret_key)
- Options historical bars/trades/quotes/snapshot/chain:
  OptionHistoricalDataClient(api_key, secret_key)
- Crypto historical bars/latest orderbook/trades/quotes (no keys needed):
  CryptoHistoricalDataClient()
- News historical: NewsClient() (no keys needed)
- Live stock stream: StockDataStream(api_key, secret_key, feed=DataFeed.IEX or
  .SIP, data_timeout=60)
- Live options stream: OptionDataStream(api_key, secret_key,
  feed=OptionsFeed.INDICATIVE or .OPRA) — MsgPack, no star subscription for
  quotes.
- Live crypto stream: CryptoDataStream(api_key, secret_key, raw_data=False)
- Live news stream: NewsDataStream (via alpaca.data.live.news)

7.2 Stream URLs (for raw WebSocket use).

Stocks IEX:   wss://stream.data.alpaca.markets/v2/iex
Stocks SIP:   wss://stream.data.alpaca.markets/v2/sip
Stocks delayed SIP: wss://stream.data.alpaca.markets/v2/delayed_sip
Stocks BOATS: wss://stream.data.alpaca.markets/v1beta1/boats
Stocks overnight: wss://stream.data.alpaca.markets/v1beta1/overnight
Options indicative: wss://stream.data.alpaca.markets/v1beta1/indicative
Options OPRA:      wss://stream.data.alpaca.markets/v1beta1/opra
Crypto Alpaca US:  wss://stream.data.alpaca.markets/v1beta3/crypto/us
Crypto Kraken US:  wss://stream.data.alpaca.markets/v1beta3/crypto/us-1
Crypto Kraken EU:  wss://stream.data.alpaca.markets/v1beta3/crypto/eu-1
News:               wss://stream.data.alpaca.markets/v1beta1/news
Test stream:        wss://stream.data.alpaca.markets/v2/test (symbol FAKEPACA,
                    always available, no keys needed — good for CI)
Sandbox:            replace stream.data.alpaca.markets with
                    stream.data.sandbox.alpaca.markets

7.3 Authentication reference.

- Trading API headers: APCA-API-KEY-ID and APCA-API-SECRET-KEY.
- WebSocket auth (message): {"action":"auth","key":"{KEY_ID}","secret":"{SECRET}"}
  — must be sent within 10 seconds of connect. For OAuth:
  {"action":"auth","key":"oauth","secret":"{TOKEN}"}.
- WebSocket auth (headers): set APCA-API-KEY-ID and APCA-API-SECRET-KEY as headers
  on connect (alpaca-py does this).
- Broker API: Client Credentials flow — POST to
  https://authx.alpaca.markets/v1/oauth2/token with grant_type=client_credentials,
  then Authorization: Bearer <token>. Tokens valid 15 minutes.

7.4 Common errors to handle in the search/connection flow.

400 invalid syntax — bad subscribe message or invalid symbol format. Validate
  symbol format before sending; catch and surface to user.
401 not authenticated — tried to subscribe before auth. Ensure auth message sent
  within 10s; retry auth on reconnect.
402 auth failed — wrong credentials. Surface "Invalid API key or secret" — prompt
  user to re-enter.
403 already authenticated — auth already done in this session. Ignore; don't
  re-auth.
404 auth timeout — didn't auth in time. Reconnect and auth immediately.
405 symbol limit exceeded — subscription would exceed plan limit. For Basic: 30
  stocks, 200 option quotes. Warn user; trim subscriptions.
406 connection limit exceeded — already have max connections. Don't open a second
  stream socket. Multiplex on the existing one.
407 slow client — client too slow processing messages. Throttle UI; batch updates;
  don't process every message synchronously.
409 insufficient subscription — feed not in user's plan. E.g. trying SIP on Basic.
  Show "Your plan doesn't include SIP. Upgrade to Algo Trader Plus for all-exchange
  coverage."
410 invalid subscribe action for this feed — e.g. subscribing bars on option stream.
  Don't subscribe to unsupported channels per feed.
412 option messages are only available in MsgPack — need
  Content-Type: application/msgpack. Use OptionDataStream (handles it) or set
  content type manually.
413 star subscription not allowed for option quotes — can't subscribe * to option
  quotes. Subscribe to individual contracts only.
500 internal error — Alpaca-side error. Log, retry with backoff, surface if
  persistent.

7.5 Feed availability depends on subscription tier.

Equities real-time: Basic/Paper = IEX only; Algo Trader Plus = all US exchanges
(SIP).
Options real-time: Basic/Paper = Indicative Pricing Feed; Algo Trader Plus = OPRA
Feed.
WebSocket symbol limit (stocks): Basic = 30; Algo Trader Plus = unlimited.
WebSocket symbol limit (options quotes): Basic = 200; Algo Trader Plus = 1000.
Historical data: Basic = since 2016, latest 15 min restriction; Algo Trader Plus =
since 2016, no restriction.
Historical API calls: Basic = 200/min; Algo Trader Plus = 10000/min.

The search UI must reflect what the user's account actually supports, not promise
feeds they can't access.

─────────────────────────────────────────────────────────────────────────────
8. CODE QUALITY — SMALLER FINDINGS (P6–P8)
─────────────────────────────────────────────────────────────────────────────

8.1 hasattr on enum-ish values (P5 in report.txt).

Across the atlas modules and dashboard app there are many
hasattr(x, 'value') ? x.value : x and hasattr(x, 'name') checks on signal
direction, side, bias direction, trade phase, signal type. This tolerates both
enum values and raw strings in the same path. It works but is a candidate for a
small normalisation layer — either everything is an enum at the boundary or
everything is a string, not both. A new detector or refactor can silently
introduce a path that returns a raw string where another returns an enum, and the
hasattr saves you from crashing but not from confusion.

Recommendation: pick one normalisation for side, signal type, trade phase, bias
direction in the hot paths. The cleanest approach: a small helper that normalises
at the boundary — when a signal is created, store it as an enum; when it crosses
into the dashboard/JS layer, serialise to its string value once. After that, the
hot paths deal in one type.

8.2 cymbols typo in capabilities() (P6 in report.txt).

desktop/engine.py:capabilities() signature line 201: cymbols instead of symbols.
It is called correctly from desktop/api.py, so it does not break anything, but a
future refactor will misread it. Fix: rename to symbols.

8.3 Two lifecycle models for asyncio.

main.py uses asyncio.new_event_loop() and loop.run_until_complete directly in
main(), and the desktop launcher also manages its own asyncio loop for the server.
The two-lifecycle model is workable but easy for a future feature to pick the
wrong loop or assume the main.py loop is the one running.

Recommendation: if the desktop build is the canonical one, document which loop is
authoritative and add a sanity check in main.py that warns if it's being run in a
context where another loop is already running.

8.4 Scanner view referenced but not fully wired (P7 in report.txt).

The search index and the guide talk about a Scanner view ("one ranked row per
instrument"), hub.snapshot_scanner exists in atlas/hub.py, and atlas/scanner.py
exists, but the rail in index.html does not have a Scanner nav item and the UI
does not have a Scanner module wired up yet. The feature is partially present in
the backend but not exposed as a view.

Recommendation: either wire up the Scanner view (add the nav item, wire the panel
into the scanner view, connect to the backend endpoint) or remove its promises
from the search index and guide until it exists. The gap between docs/search
promises and actual UI is visible.

8.5 Documentation-to-code drift (P8 in report.txt).

- The guide and search index describe a "Scanner" view and a "Market Analyzer"
  that the rail does not yet expose.
- The guide lists a "Strategy" view and a "Performance" view; those exist in the
  rail as empty stubs that render panels via ui.js ensurePanel, but the underlying
  live endpoints they call (/api/strategy-status, performance journal) are only
  partially live (see P1).
- The guide says the setup wizard button lives "above Overview"; in the current
  index.html there is no such button in the rail — it is added by guide.js at
  runtime. The docs describe the runtime result, which is fine, but a reader
  looking at the static HTML will not find it.

These are not errors, just places where the static HTML, the guide, and the
runtime UI are different layers. The fix is to make the guide consistently
describe the runtime layer, and to note where a feature is "backend-ready, UI
pending."

─────────────────────────────────────────────────────────────────────────────
9. IMPLEMENTATION ORDER
─────────────────────────────────────────────────────────────────────────────

1. Wire the live candle-close path end-to-end (P1). This is the main event.
   Specifically: make InstrumentPipeline._on_candle_close persist the candle and
   broadcast it, OR wire _on_candle_close_handler into the callback chain. Then
   wire /api/tape and /api/microstructure to read from the pipeline's live state
   instead of falling through to demo. Then make the live/demo state visible in
   one place rather than per-panel warnings.

2. Add an Alpaca status card to the Overview, a top-level Alpaca nav item, a
   persistent banner when not connected, and Alt+A shortcut (P3). Reuse the
   existing alpaca.js card logic; don't duplicate the capability rendering.

3. Add an optional Alpaca step to the setup wizard (P4): sign up → get keys →
   paper/live toggle → capability preview → paste and test → done/upgrade path.
   Skips gracefully if the user doesn't have keys yet.

4. Enrich the search function for order-flow power users (P5): live Alpaca symbol
   search with feed chips and market status, command-palette entries for Alpaca
   symbols, expanded search with operators, multi-select, watchlist quick-add,
   recent/pinned section, option chain panel, multi-feed comparison, keyboard
   shortcuts. Wire it to a single shared Alpaca stream connection (not one socket
   per lookup).

5. Consolidate per-instrument config into a class-level default map plus a small
   override table (P2). Same behaviour, far less repetition, easier to add an
   instrument.

6. Fix the cymbols typo (P6). Pick one normalisation for enum-vs-string in the
   hot paths. Either wire up the Scanner view or remove its promises from the
   search index and guide until it exists. Make the guide consistently describe
   the runtime layer.

7. Add a small CI step (pytest + audit_ui_refs) if this lives on a pushable repo.

─────────────────────────────────────────────────────────────────────────────
10. BOTTOM LINE
─────────────────────────────────────────────────────────────────────────────

This is a solid, honest build. The analytics core, the config model, the
onboarding/docs, the Alpaca integration, and the search/UI layer are all
genuinely well done. The one real defect is that the live engine is not fully
bridged to the dashboard REST/WS surface the UI reads, so several views fall back
to demo data while the engine runs — that's the part that most affects "does it
actually work live," and it's also the part the UI already warns about.

The Alpaca work you asked for — make it easy to find, add a setup wizard flow,
reference it in search, make search link to live-updatable feeds with all relevant
feeds listed, and design a slick expanded search for experienced order-flow
users — is all achievable on top of what's already there. The search function in
particular is already the best-executed part of the UI; the work is less about the
search box itself and more about what it can reach (live Alpaca symbols, feed
chips, option chains, multi-feed comparison) and how directly it navigates
(Alpaca setup as a first-class result, not buried in Settings).
