# ModFlow OrderFlow Analysis Suite — User Guide

Everything in this guide is for the desktop app in `orderflow_system/desktop/`, which wraps the
project's analytics in a single-click interface for **Windows and macOS**.

---

## 0b. Scanner, VWAP and the depth-execution panel

**Scanner** (left rail) — one ranked row per streaming instrument: last price, change, volume,
delta and delta as a share of volume, tape speed, big prints, sweeps, stop runs, liquidations,
stacked imbalances, both sides of book pressure, absorption, executions into depth and refills,
distance from VWAP in ticks, and a composite score. Click any column header to sort; click an
instrument name to switch the whole app to it. The score is a stated heuristic — its weights are
printed under the table rather than hidden in a black box.

**VWAP** (Chart view) — a session VWAP on a rolling window with ±1σ/±2σ/±3σ bands, drawn over the
candles, plus an **anchored** VWAP you start with "Anchor here" (blue line). The anchored line
accumulates only from the moment you anchor it — a live feed cannot reconstruct the past honestly,
so nothing before the anchor is invented. Defaults: 24-hour window (crypto has no bell), one-minute
resolution, ±1σ drawn as dashed bands. A `vwap_cross` alert fires when price closes through the line
with a 60-second cooldown.

**Depth executions** (Trackers, under Participants' intent) — prints that took a large share of the
size resting at their price, i.e. someone ate a wall instead of picking off the inside. A print must
take ≥25% of a level that is itself ≥8× the median print, so ordinary trading does not fill the
panel. When the level refills within seconds without price leaving, it is tagged "refilled" — the
closest a venue without order ids gets to hidden size, and labelled as an inference.

**Delta bars** (Frames view → Frame: Delta) — bars built from effort rather than time: one closes
when the delta inside it passes the trend threshold, or reverses from its extreme. Each bar carries
its statistics (min/max delta, delta since the high, delta since the low) and the frame joins range,
renko, reversal, tick and volume.

**Tick profile** (Profile view) — a profile by *number of trades* rather than volume, so a price that
is busy in prints and quiet in size stands out, and vice versa. It ships alongside the volume and TPO
profiles in the same payload.

## 0a. Search (Ctrl+K)

One box finds everything the program can show or do. Press **Ctrl+K** (or `/`) anywhere, or click the
search box at the top of the rail, and type. Results are grouped by what they are:

| Group | What it holds |
|-------|---------------|
| Views | every view in the rail |
| Panels | the cards inside views — Participants' intent, Depth executions, Market context, Scanner, VWAP… |
| Actions | Start/Stop/Restart the engine, run the setup assistant, rebuild profiles, anchor or clear the VWAP, refresh panels, clear stored alert credentials, export detections |
| Settings | every labelled control, described and located by view (choosing one opens that view and flashes the control) |
| Options | the choices inside dropdowns — "renko", "15m", "delta bars" find the control that offers them |
| Alerts | every alert kind (what can fire, and what it means) and every rule (open the Alerts view) |
| Help | the step-by-step walkthroughs (MetaTrader 5, ntfy, Telegram, email, webhook, instruments, extras, context) |
| Guide | every documentation section, scrolled to on selection |
| Instruments | switch the whole app to a symbol |

Every row carries a hover tooltip with its full description. Keys: ↑ ↓ move, **Enter** goes, **Esc**
closes. Dropdown menus elsewhere in the program are annotated too — hover an option (a frame type, a
timeframe, a log level) to see what it does.

**Privacy:** nothing about you is stored by the program. No accounts, no keys, no personal data — the
only local files are your settings and the market data it collected, both under your own user folder.
If you ever do enter channel credentials (SMTP, Telegram, webhook), the search action
**Clear stored alert credentials** wipes them from the config file in one click.

## 0c. Updates never fight you

The program refreshes itself constantly (prices, panels, tables). None of that may interrupt what you
are doing, so refreshes obey a simple policy:

- **A dialog is open** (setup assistant, a walkthrough, a notice) → every background panel is held still.
- **You are typing or have a field focused** → the panel holding that field is not rebuilt, and neither
  is anything else for a few seconds after your last keystroke.
- **That panel contains unsaved input** → it is left alone even by a poll on another view, so a value you
  entered is never thrown away while you get to the Save button.
- **A click is in progress** → no markup is replaced under the pointer, so a button cannot change
  identity between pressing and releasing.
- **Otherwise** everything updates normally, and when a panel does rebuild, the focused field, the
  caret position and any scroll position are restored afterwards.

When the program is holding updates back, a small **"updates paused while you work"** badge appears in
the bottom-right corner. Hover it to see how many renders were held back. It is the honest answer to
"is this thing still live?" — idle, everything ticks; mid-edit, nothing moves under your hands.

## 0d. Linking an Alpaca Markets account (optional)

Alpaca is a US brokerage with an API: commission-free stocks, ETFs, options and crypto, and a
**free paper-trading account** that anyone can open with just an email address. Linking it is optional —
everything else in the program works without it.

**Where:** Settings → **Broker account — Alpaca Markets**. One card holds the whole thing: environment
(paper or live), key ID, secret, Validate, Test-without-saving, and Remove keys. The setup assistant has
a broker step that points you there, and Guide → Setup how-tos → Alpaca walks through getting keys.

**What linking adds**

- US equities, ETFs, options and crypto instruments for the scanner and the tape analytics.
- Real-time US tape on the free plan (IEX, up to 30 stream symbols) and full-market history for data
  older than 15 minutes.
- Benzinga news in the market-context panel, and the US market calendar so the app knows when equities
  are open.
- A portfolio read (positions, orders, portfolio history) and — planned, opt-in — paper order entry.

**What it cannot add:** order-book depth. Alpaca publishes trades, quotes and bars only, so the
heatmap, the DOM ladder and the participants'-intent reader stay on the exchange feed and the optional
MT5 terminal. The capability report in the card prints that line next to the features, so nothing looks
mysteriously empty.

**Keys:** create them in the Alpaca dashboard for the environment you want. Paper keys work only against
paper, live keys only against live — the app names that mismatch explicitly when it sees it. Keys are
stored in your local config file, never shown back, sent only to Alpaca, and "Remove keys" wipes them.

The full analysis and the phased build plan are in **docs/ALPACA_INTEGRATION_PLAN.md**; the feed
reference — streams, REST limits, error codes, how to switch it on as a data source — is
**docs/ALPACA_DATA_FEED.md**.

To **stream** Alpaca data: set *Settings → Data source* to **Alpaca** (US equities, ETFs, options and
crypto) or **All** (exchange feed + Alpaca together), make sure the instruments you want have an Alpaca
symbol, then press Start. The **Live feed** card in the Alpaca view shows the US session state, the REST
budget, each stream's state and the subscription set. Depth-bearing views (heatmap, DOM ladder, intent
reader) state their reason for Alpaca symbols instead of showing an empty canvas — Alpaca publishes no
order book on any plan.

## 0. The Setup wizard button

At the top of the left rail, above Overview, there is a **Setup wizard** button. It opens the
step-by-step assistant at any time (Guide → Run setup assistant does the same thing).

Its colour is the state of your setup:

| Colour | Meaning |
|--------|---------|
| Amber | The assistant has not been completed on this install. Nothing is broken — the defaults stream data out of the box — but the walkthrough is where you choose instruments, feeds, and any optional extras. |
| Green | You reached the end and pressed Finish. The button stays green; click it again whenever you want to change something. |

Skipping or closing the assistant leaves it amber: the colour records that the walkthrough was
completed, not that a window was opened.

## 1. What this program is

An order-flow analysis workstation that runs on your machine. It connects to the exchange's public
market-data feed, streams every execution and order-book change, and turns them into the readings
order-flow traders use:

* **Market-depth heatmap** — resting liquidity over time, executed-volume bubbles, spoof/stack detection.
* **Tape-flow trackers** — icebergs, sweeps, stop runs, big trades, liquidations, speed of tape.
* **Imbalance ladder** — the 150 % bid/ask imbalance rule with stacked-level clusters.
* **CVD** — cumulative volume delta with multi-window deltas and price/delta divergences.
* **Market Profile (TPO)** — POC, value area, initial balance, single prints, developing VA, virgin POCs.
* **Non-time frames** — Range, Renko, Reversal, Tick, Volume bars.
* **Market replay** — re-run a recorded session through every analyser.
* **Alerts** — rules over every detection, with sound, a log, durable history and optional delivery to
  Telegram, ntfy, email or your own webhook.
* **Market context** — free, keyless: funding rate, open interest, long/short ratio, Fear & Greed and
  RSS headlines on the Overview.

It is a **read-only analyst**: it places no orders and holds no keys.

---

## 2. What you need

| | |
|---|---|
| OS | Windows 10/11 or macOS 12+ (Linux works too) |
| Python | 3.12 (the install below creates its own environment) |
| Accounts | **None.** No exchange login, no API key, no subscription. |
| Internet | Any connection that can reach the exchange's public endpoints |
| Disk | ~600 MB for the environment; history is pruned to 7 days automatically |

Four **optional, free** integrations can be added later — ntfy push (no account at all), a Telegram
bot, email, and a webhook for your own endpoint — plus the free market-context sources. Skipping all
of them costs nothing except phone notifications.

---

## 3. Install

From a terminal (PowerShell, Terminal.app, or bash):

```bash
git clone https://github.com/ModdySwag/ModFlow-OrderFlow-Analysis-Suite
cd ModFlow-OrderFlow-Analysis-Suite

# create an isolated environment (uv is a single binary: https://docs.astral.sh/uv/)
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe websockets aiohttp pandas numpy scipy \
    python-telegram-bot aiosqlite pytz pyyaml fastapi "uvicorn[standard]" pywebview \
    pytest pytest-asyncio
```

On macOS the interpreter path is `.venv/bin/python` instead of `.venv/Scripts/python.exe`.

## 4. Run

```bash
python -m orderflow_system.desktop              # native desktop window
python -m orderflow_system.desktop --browser    # open in your default browser instead
python -m orderflow_system.desktop --headless   # server only (no window)
python -m orderflow_system.desktop --view heatmap   # open straight on a view
```

The first launch opens the **setup assistant** (see §5). After that, the app opens on the Overview.

---

## 5. First-run setup assistant

The assistant runs once and takes about a minute. Nothing is mandatory; you can press **Skip** and the
defaults stream BTCUSDT immediately. It asks, in order:

1. **Welcome** — what the program is.
2. **Data source** — exchange public feed (free, no account, Windows + macOS) or a MetaTrader 5
   terminal (Windows only, needs a broker install). There is a **Test the public feed** button that
   checks reachability and counts the listed instruments.
3. **Instruments** — pick what to stream. *Select all venue-listed* enables everything the exchange
   can serve; the heatmap and trackers are happiest with two or three instruments you actually watch.
4. **Feeds, history & extras** — the deeper order book (needed for heatmap walls/stack/pull), and
   whether detections are persisted to disk for post-session review.
5. **Alerts & notifications (optional)** — ntfy push (no account), Telegram bot, email (SMTP app
   password) and a webhook, each with its own **Test** button; all can be skipped.
6. **Market context (optional)** — funding/OI/long-short, Fear & Greed and crypto headlines, with a
   *Check now* button that fetches live data before you commit.
7. **Ready** — a summary, a *Start the engine now* checkbox, and Save.

Settings are written to your user config file — **the program's source is never modified**. Re-run the
assistant any time from **Guide → Run setup assistant**.

---

## 6. Everyday use

1. **Start engine** (top bar). The status pill turns green and data starts flowing.
2. Give the heatmap ~a minute — it builds one column per second of order-book history.
3. Use the **Instrument** dropdown to switch symbols; every view follows it.
4. Pick views from the rail. Hover any control for a one-line explanation — every button, selector and
   table in the app has a tooltip.

| View | What it shows |
|---|---|
| Overview | Price, cumulative delta, tick/candle counts, trade phase, newest signals. |
| Chart | Candles + delta histogram with value-area lines and signal markers. |
| Heatmap | Liquidity map; bubbles = executed trades, cyan/purple = stacking/pulling, walls listed below. |
| Order Flow | Footprint: bid/ask volume per price, POC and value area. |
| Depth | Live ladder with bid/ask imbalance. |
| Time & Sales | Tick-by-tick prints with big trades highlighted. |
| Trackers | Icebergs, sweeps, stop runs, big trades, liquidations, imbalance ladder, big-trade zones. |
| CVD | Cumulative delta vs price, multi-window deltas, divergence table. |
| Profile | TPO ladder, POC/VA/IB/single prints, developing VA and virgin POCs. |
| Frames | Range / Renko / Reversal / Tick / Volume bars. |
| Signals / Strategy / Performance | Pattern signals, pipeline state, and this session's journal. |
| Replay | Load recorded ticks (or the exchange tape) and replay through the analytics. |
| Alerts | Rules, live log, persisted history, per-rule routing to Telegram/ntfy/email/webhook. |
| Instruments | Enable/disable symbols, validate them against the venue. |
| Settings | Data source, risk, thresholds, analyser tuning, notification channels. |
| Logs | The live engine log. |
| **Guide** | This document, plus the setup assistant. |

---

## 7. Alerts

* **In the app** — the Alerts view lists every fired alert with severity and the rule that matched.
  The counter in the rail shows the total; the **Sound** box plays a short tone per alert (severity
  decides the tone). Browsers block audio until your first click somewhere on the page.
* **Rules** — one row per rule: on/off, thresholds as JSON, cooldown seconds, fire count. Edit and
  press **Save rules**. Defaults cover big trades, blocks, sweeps, stop runs, icebergs, speed spikes,
  CVD divergence, liquidity pull/stack and stacked imbalance.
* **Telegram, ntfy, email, webhook (all free, all optional)** — every channel is described in
  section 7b below. Each has a **Test** button that sends a real message before you rely on it.
  Then, in the Alerts view, tick the channels per rule; bursts are throttled per channel.
* **History** — every detection and alert is written to SQLite (7-day retention, pruned automatically)
  and can be reviewed in **Alerts → Persisted history**, or via `/api/atlas/history/{symbol}`.

## 7b. Notification channels — and the market-context card

| Channel | What you need | Notes |
|---|---|---|
| **ntfy push** | The ntfy app (iOS/Android/desktop) — **no account, no key** | Subscribe to a topic name you invent, type the same name in Setup → Alerts. Self-hosted servers work too. |
| **Telegram** | A free bot from @BotFather | Token + numeric chat id; message the bot once so it may reply. |
| **Email** | Any mailbox over SMTP | Gmail/Outlook need a 16-character **app password**, not your login password. |
| **Webhook** | A Discord/Slack incoming-webhook URL, or your own endpoint | Fired alerts are POSTed as JSON. |

**Market context** (Overview, refreshed every 60 s — free and keyless): funding rate and next funding
time, open interest, 24 h change/turnover and the long/short account ratio straight from the venue,
the alternative.me Fear & Greed index, and headline feeds (CoinDesk / Cointelegraph / Decrypt, or
your own RSS URL). Switch any part off in Setup → Market context; each section fails soft, showing
"unavailable" instead of breaking the view.

## 8. Replay

Pick an instrument and a source — *recorded ticks* (this app's own history) or the *exchange tape*
(no local data needed) — set the minutes-ago window, **Load session**, then Play/Pause/Stop, adjust
speed (0.5×–500×) and scrub the position. Replay ticks drive the same analysers as live data, so the
heatmap, trackers, CVD, profile and frames rebuild while it runs.

## 9. Where your files live

| | |
|---|---|
| Windows | `%APPDATA%\OrderFlowAnalysisPro\` (config.json, orderflow.log, orderflow_data.db) |
| macOS | `~/Library/Application Support/OrderFlowAnalysisPro/` |
| Linux | `~/.config/OrderFlowAnalysisPro/` |

Deleting `config.json` returns the app to first-run defaults; deleting `orderflow_data.db` clears the
tick history and persisted detections. The installed code is never changed by using the app.

## 10. Privacy

* All analysis runs locally. Nothing is uploaded.
* The analytics use **public data only** — no account, no API key, no broker link.
* The only outbound traffic is the market-data feed you selected, the free market-context lookups
  (venue funding/OI, Fear & Greed, RSS), and any notification channel / webhook you configure.
* Credentials you type (bot token, chat id, ntfy topic, SMTP password) are stored in the plain-text
  config file and sent only to the service they belong to. Keep that file private; it is not a key
  to any exchange account.

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| Status pill says Stopped | Press **Start engine**. Panels stay empty until data flows. |
| "No usable instruments" | Instruments → **Validate against exchange** → **Enable all supported**. |
| Heatmap empty for the first minute | Expected — it needs order-book updates before it can draw columns. |
| Iceberg / stop-run rows tagged "inferred" | The public feed publishes no order ids; those two are statistical inferences, not MBO facts. |
| No alert sound | Click anywhere in the window once (audio policy), and check the **Sound** box. |
| Telegram test fails | Re-copy the token; make sure you messaged the bot at least once; the chat id is numeric. |
| ntfy test does nothing | Check the topic name matches the one subscribed in the app; try the default server unless you self-host. |
| Email test fails | Use an app password (not your login), host `smtp.gmail.com`, port 587 for Gmail. |
| Market context says unavailable | A public source is unreachable — the app keeps streaming; try Refresh. |
| MT5 option unavailable | MetaTrader 5 is Windows-only and must be installed and logged in; use the public feed instead. |
| Window closed by itself | Relaunch the app; the engine and settings are unaffected. |
| Everything looks frozen | Check the Logs view — feed errors are logged with their reason; a reconnect is automatic. |

## 12. Shortcuts and small things

* The rail link **Classic terminal ↗** opens the project's original web dashboard in a browser.
* `--view <name>` opens any view directly, e.g. `--view heatmap`.
* Views are addressable by hash (`#heatmap`), so the browser mode can be bookmarked.
* Settings changes apply on the next engine start; **Save & restart engine** applies them immediately.

---

*Questions or bugs: open an issue on the project repository with the Logs view contents attached.*

## 13. MetaTrader 5: indices, gold, FX and CFDs (optional)

The program's default data source is the exchange's public feed — crypto perpetuals, no account,
no key. A second source is optional: **MetaTrader 5**, which is how you get instruments a crypto
venue does not list (NAS100, US500, DAX, gold, silver, FX, commodity and equity CFDs) using your
broker's own symbol names.

**On first start the program tells you this option exists** and offers the walkthrough. You can also
open it any time: Guide → Setup how-tos → MetaTrader 5. The setup assistant shows the same banner in
its Data source step, and adds a MetaTrader step of its own when you choose MT5 (or Both).

What the walkthrough covers, in order:

1. Install the MetaTrader 5 terminal from your broker (not from this program) — branded terminals
   differ and each broker names its markets differently.
2. Log in and **leave the terminal running** — the bridge talks to the running terminal.
3. Install the Python bridge into this program's environment. The walkthrough prints both variants
   (a pip venv and a uv venv) and the app's own test tells you which one this machine needs.
4. Terminal path — only if it is installed somewhere unusual.
5. Login and server — only if you want a specific account; blank uses whatever the terminal is
   signed in to.
6. Map your instruments to your broker's symbol names (USTEC / US100 / NAS100…, XAUUSD / GOLD…).
7. **Test the bridge** — connects with the settings you typed, reports the terminal, the account and
   which of your mapped symbols the broker lists, then disconnects. Nothing is saved by the test.

The test reports one honest stage at a time — platform → Python bridge → running terminal → ready —
so a failure names the missing piece instead of saying "it did not work". Nothing on this machine's
configuration is changed until you finish the assistant.

Honest limits: MT5 data quality and depth are broker-dependent (some brokers publish a full DOM,
some almost none), so the order-book views are at their best on the exchange feed. Historical ticks
download from the broker on first use, which can take a moment.

## 14. Setup how-tos (every optional add-on, step by step)

Guide → **Setup how-tos** lists a short walkthrough for each optional piece:

| Walkthrough | Covers |
|-------------|--------|
| MetaTrader 5 data source | install, login, bridge, path/login, symbol mapping, live test |
| Instruments | importing the venue's own list (with real tick sizes); MT5 broker-name mapping |
| Deep book, liquidations, history | what each extra unlocks; what turning it off costs |
| Phone push (ntfy) | pick a topic, subscribe, test — no account at all |
| Telegram alerts | create the bot, get the chat id, test |
| Email alerts | SMTP host/port, app password, why it starts unrouted |
| Webhook | Slack / Discord / your own endpoint, and the payload shape |
| Market context | funding, open interest, long/short, Fear & Greed, headlines — and their caveats |

Every walkthrough is reachable from the setup assistant too, right next to the option it explains.

## 15. Where to go next

* **`docs/USE_CASES.md`** — nine worked scenarios (absorption at a level, stop runs,
  sweeps and reclaims, block prints at the open, delta divergence, stack vs pull,
  session replay, alerting hygiene, cross-instrument context): setup, what to watch,
  and what invalidates the read.
* **`docs/the reference layout_SDK_NOTES.md`** — what the reference layout's developer documentation contributed to
  this build (the performance pass, the version-stamped heatmap payload, the Market
  pressure panel) and what deliberately stays out of scope (orders, accounts).
* **`docs/the reference layout_COMPARISON.md`** — the feature-by-feature comparison with the reference layout.
* **`docs/ALPACA_DATA_FEED.md`** — the Alpaca data feed: stream URLs, REST endpoints and
  budgets, the error-code table, subscription caps, and how to switch the program onto it.
