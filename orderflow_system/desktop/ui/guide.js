/* ══════════════════════════════════════════════════════════════════
   Onboarding & help layer — additive module.

   1. Tooltips: every control gets a hover explanation (native `title`,
      which WebView2 and WKWebView both render), re-applied to nodes the
      app creates later.
   2. Help view: a "Guide" entry in the rail with the program
      explanation, a view-by-view walkthrough and setup instructions.
   3. First-run wizard: a clickable, skippable step-by-step setup that
      writes the config and can start the engine.

   Loaded by atlas-v2.js. Touches no element owned by another module:
   the nav entry, the view section, the wizard overlay and the styles are
   all created here.
   ══════════════════════════════════════════════════════════════════ */

const GUIDE = { tips: 0, step: 0, open: false, cfg: null, obs: null };

const G_ESC = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* The wizard's NinjaTrader probe box offers the terminal names the app already knows — the
   mapping the config carries from rows added on the NinjaTrader lane. The shell's own config
   copy is the source (no extra fetch); an empty list is the honest answer, and the box stays
   typeable because the terminal's own list cannot be read offline. */
const G_NT_NAMES = () => {
    const mod = (typeof window !== 'undefined' && window.OFAPINSTRUMENT) || null;
    const cfg = (typeof S !== 'undefined' && S && S.config) || null;
    return (mod && typeof mod.ninjatraderNames === 'function')
        ? mod.ninjatraderNames((cfg && cfg.instruments) || []) : [];
};

/* ══════════════════════════════════════════════════════════════════
   1. Tooltips
   ══════════════════════════════════════════════════════════════════ */

const TIPS = {
    /* rail */
    '.nav-item[data-view="overview"]': 'Session at a glance: price, delta, tick counts and the latest pattern signals.',
    '.nav-item[data-view="chart"]': 'Candlestick chart with delta histogram, value-area levels and signal markers.',
    '.nav-item[data-view="heatmap"]': 'Market-depth heatmap: resting liquidity over time, with executed-volume bubbles and spoof/stack events (the reference layout "Market Depth").',
    '.nav-item[data-view="orderflow"]': 'Footprint: bid/ask volume per price level, POC and value area.',
    '.nav-item[data-view="depth"]': 'Live order book ladder with imbalance between the best bid and ask.',
    '.nav-item[data-view="tape"]': 'Time & Sales: every executed print, big trades highlighted.',
    '.nav-item[data-view="trackers"]': 'Order-flow trackers: icebergs, sweeps, stop runs, big trades, liquidations, imbalance ladder and big-trade zones.',
    '.nav-item[data-view="cvd"]': 'Cumulative Volume Delta with multi-window deltas, slope and price/delta divergences.',
    '.nav-item[data-view="profile"]': 'Market Profile (TPO): POC, value area, initial balance, single prints, developing VA and virgin POCs.',
    '.nav-item[data-view="frames"]': 'Non-time bars: Range, Renko, Reversal, Tick and Volume.',
    '.nav-item[data-view="signals"]': 'Pattern signals with direction, grade, entry/stop/target levels.',
    '.nav-item[data-view="strategy"]': 'What the strategy pipeline is waiting for, and the current microstructure readings.',
    '.nav-item[data-view="performance"]': 'Journal of this session\u2019s signals and their outcomes.',
    '.nav-item[data-view="replay"]': 'Market replay: re-run recorded ticks or the exchange tape through the same analytics.',
    '.nav-item[data-view="alerts"]': 'Alert rules, the live alert log, persisted detection history and Telegram routing.',
    '.nav-item[data-view="instruments"]': 'Choose which instruments the engine subscribes to.',
    '.nav-item[data-view="alpaca"]': 'Optional: link a US brokerage account (stocks, ETFs, options, crypto) for its tape, news and market calendar. Alt+A opens it.',
    '.nav-item[data-view="profiles"]': 'Saved setups (playbooks): feed, instruments, analysis, layout and theme switch together — save the current set, tweak a copy, share one as a file, or auto-switch by session.',
    '.nav-item[data-view="settings"]': 'Everything the app can change at runtime \u2014 saved to your user config folder, never to the source.',
    '.nav-item[data-view="logs"]': 'Live engine log with level filtering.',
    '.nav-item[data-view="guide"]': 'This guide: what the program does, how to set it up, and what every screen shows.',

    /* top bar */
    '#symbolSelect': 'The instrument every view follows. Start the engine and enable more instruments under Instruments.',
    '#enginePill': 'Engine state. "Stopped" means no data is streaming \u2014 press Start engine.',
    '#wsPill': 'WebSocket link between the app and its own server. "WS live" means panels update in real time.',
    '#btnStart': 'Connect the data feed and begin streaming. All analysis, alerts and history start from here.',
    '#btnStop': 'Disconnect the feed. Settings, history and journal stay on disk.',
    '#btnRestart': 'Restart the engine with the currently saved settings.',

    /* overview */
    '#btnRefreshStats': 'Re-read the per-instrument counters right now.',
    '#ovTable': 'One row per enabled instrument: price, ticks, candles, cumulative delta and trade phase.',
    '#ovSignals': 'Newest pattern signals as they fire.',
    '#ovAlpacaHost': 'The optional broker account. A green pill means the keys were accepted; the card repeats only what the account really has.',
    '#ovAlpacaBanner': 'Offered once — connect Alpaca, or say “Not now” and it stays out of the way until the next start.',

    /* chart */
    '#tfSelect': 'Candle timeframe used by the chart view.',
    '#rangeSelect': 'How much history the chart loads.',
    '#ovMarkers': 'Show/hide signal markers on the candles.',
    '#ovVP': 'Draw the volume-profile POC / VAH / VAL lines on the chart.',
    '#chart': 'Scroll to zoom, drag to pan. Delta histogram sits in the lower band.',

    /* order flow / depth / tape */
    '#btnRebuildProfile': 'Rebuild the volume profile from stored candles (the engine otherwise does this once an hour).',
    '#footprintChart': 'Per-price bid/ask volume. Drag to pan, scroll to zoom.',
    '#orderbookLadder': 'Live bid/ask ladder with size bars and imbalance.',
    '#tapeContainer': 'Tick-by-tick prints; large trades are highlighted automatically.',

    /* heatmap */
    '#hmColumns': 'How much time the heatmap covers (number of 1-second columns).',
    '#hmRows': 'How many price rows to draw. The app aggregates ticks automatically so the map stays readable.',
    '#hmTrades': 'Overlay executed volume as bubbles \u2014 size is volume, colour is the aggressor side.',
    '#hmEvents': 'Overlay liquidity stack (cyan) and pull (purple) events.',
    '#hmAuto': 'Auto-refresh the map while this view is open.',
    '#heatmapCanvas': 'Brighter = more resting liquidity. Blue line = best bid, orange = best ask, white dashes = last price.',
    '#hmEventTable': 'Liquidity events: stacks (size added) and pulls (size removed near price \u2014 spoof candidates).',
    '#hmWallTable': 'Fresh price levels holding a top-percentile share of resting liquidity.',

    /* trackers */
    '#tkImbStats': 'Counts for the imbalance ladder: levels where one side dominates the other by the configured rate.',
    '#tkImbTable': 'the reference layout imbalance rule: bid volume at a price vs the ask one level above (and the mirror). Ratio is the dominance.',
    '#tkStackTable': 'Consecutive imbalanced levels in the same direction \u2014 the strongest defence/absorption reading.',
    '#tkZoneTable': 'Price zones that collected the most big-trade volume this session, best first.',
    '#tkIcebergTable': 'Iceberg inference: repeated equal prints at one price with L2 refills (no public feed exposes true order IDs).',
    '#tkSweepTable': 'Sweeps: aggressive prints that ran through several price levels inside the millisecond window.',
    '#tkStopTable': 'Stop runs: fast range expansion plus a volume burst, confirmed when liquidation clusters follow.',
    '#tkBigTable': 'Prints at or above the adaptive big-trade threshold; fragmented prints are reassembled into one trade.',
    '#tkLiqTable': 'Liquidations from the exchange feed.',

    /* cvd */
    '#cvdReanchor': 'Re-anchor CVD to now \u2014 useful after a session break.',
    '#cvdCanvas': 'Green/red line = cumulative delta; grey = price. Divergence between them is the signal.',
    '#cvdDivTable': 'Detected price/delta divergences with a 0\u2013100 strength score.',

    /* profile */
    '#tpoGrid': 'TPO letters per price. Highlighted rows are POC / value area; SP marks single prints.',
    '#mpReads': 'Session reads: developing value area, virgin POCs (untested magnets) and prior sessions.',

    /* frames */
    '#frameSelect': 'Which non-time bar family to build from the live ticks.',
    '#frameCanvas': 'Closed bars for the selected frame.',
    '#frameTable': 'The last bars with OHLC, volume, delta, tick count and duration.',

    /* replay */
    '#rpSymbol': 'Instrument to replay (must have local history, or use the exchange tape).',
    '#rpSource': 'Recorded ticks come from this app\u2019s SQLite history; the exchange tape needs no local data.',
    '#rpFrom': 'How far back the replay starts (minutes ago).',
    '#rpTo': 'Where the replay ends (minutes ago; 0 = now).',
    '#rpLoad': 'Load the session into the transport. Nothing plays until you press Play.',
    '#rpPlay': 'Feed the loaded events into the analytics at the chosen speed.',
    '#rpPause': 'Freeze the replay; the position holds until you resume or scrub.',
    '#rpStop': 'End the replay and reset the transport.',
    '#rpSpeed': 'Replay speed multiplier (0.5\u00d7 = slow motion, 500\u00d7 = fast forward).',
    '#rpSeek': 'Scrub to a position. Works while paused \u2014 Play resumes from there.',

    /* alerts */
    '#alSound': 'Play a short tone when an alert fires (severity decides the tone). Saved in this browser.',
    '#alAuto': 'Refresh the alert log automatically while this view is open.',
    '#alClear': 'Empty the alert log on the engine (rules and persisted history are untouched).',
    '#alOnlyHm': 'Show only the rules the depth map created (their id starts with hm-).',
    '#alOnlyOn': 'Show only the rules that are currently enabled.',
    '#alRuleCount': 'How many rules the filter is showing, out of how many exist \u2014 counted from the list, never assumed.',
    '#alertTable': 'Every fired alert, newest first: time, severity, kind, symbol, the level and size it happened at, and why it fired.',
    '#ruleTable': 'One row per alert rule, in words: what it watches for, where, and how often it may fire. Edit opens its fields \u2014 thresholds, level scope, hold time, channels and cooldown.',
    '#histTable': 'Detections persisted to SQLite \u2014 review a session after the window is closed.',
    '#histReload': 'Re-read the persisted history now.',
    '#tgRouting': 'Per-rule switch: which rules are allowed to send to Telegram.',

    /* instruments */
    '#btnValidate': 'Check every configured symbol against the exchange\u2019s public instrument list (no account needed).',
    '#btnEnableCrypto': 'Tick every instrument the selected venue can actually serve.',
    '#btnDisableAll': 'Untick everything.',
    '#instTable': 'Coverage per instrument: enabled, venue support and tick size. Unsupported rows stay grey.',

    /* settings */
    '#setSource': 'Which venue feeds the engine. Bybit is public and cross-platform; MetaTrader 5 needs a Windows broker terminal.',
    '#setCooldown': 'Minimum seconds between signals for the same instrument.',
    '#setScore': 'Composite score a setup must reach before it becomes a signal.',
    '#setLogLevel': 'Verbosity of the engine log.',
    '#setTgEnabled': 'Master switch for sending order-flow alerts to Telegram.',
    '#setTgToken': 'Bot token from @BotFather (free). Stored only in your user config file.',
    '#setTgChat': 'The chat id that receives the alerts (message your bot, then use @userinfobot to read your id).',
    '#btnTgTest': 'Send one test message to confirm the token and chat id work.',
    '#patGrid': 'Per-instrument thresholds for the five pattern detectors.',
    '#atlasGrid': 'Tuning for the heatmap, tape, CVD and profile analysers. Applies on the next engine start.',
    '#atlasV2Grid': 'Tuning for the imbalance ladder, tape reassembly/zones, detection history and Telegram routing.',
    '#btnSaveSettings': 'Save the settings without touching the running engine.',
    '#btnSaveRestart': 'Save and restart the engine so every change takes effect immediately.',
    '#btnReloadSettings': 'Discard unsaved edits and reload from disk.',
    '#btnResetSettings': 'Restore factory defaults (your instrument choices are rebuilt from the defaults too).',

    /* logs */
    '#logLevel': 'Filter the log by severity.',
    '#logAuto': 'Follow the log automatically.',
    '#btnLogClear': 'Clear the in-app log buffer (the log file on disk is kept).',
    '#logList': 'Newest engine lines. The full path is shown above the panel.',
};

function applyTips(root) {
    let applied = 0;
    const scope = root || document;
    Object.entries(TIPS).forEach(([sel, tip]) => {
        let nodes;
        try { nodes = scope.querySelectorAll(sel); } catch (e) { return; }
        nodes.forEach((el) => {
            if (!el.getAttribute('title')) { el.setAttribute('title', tip); applied++; }
            if (!el.getAttribute('aria-label')) {
                const label = (el.textContent || '').trim().slice(0, 60);
                el.setAttribute('aria-label', label || tip.slice(0, 60));
            }
        });
    });
    GUIDE.tips += applied;
    return applied;
}

/* re-apply to nodes the app creates later (tables, rule rows, wizard steps) */
function watchDom() {
    if (GUIDE.obs) return;
    let timer = null;
    GUIDE.obs = new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(() => applyTips(document), 1500);
    });
    GUIDE.obs.observe(document.body, { childList: true, subtree: true });
}

/* ══════════════════════════════════════════════════════════════════
   2. Help view (created here — no shared markup touched)
   ══════════════════════════════════════════════════════════════════ */

const GUIDE_SECTIONS = [
    {
        h: 'What this program is',
        body: `ModFlow OrderFlow Analysis Suite is a desktop order-flow workstation. It connects to a public
               market-data feed, streams every execution and order-book change, and turns them into the
               readings professional order-flow traders use: market-depth heatmaps, tape-flow trackers,
               cumulative delta, Market Profile, non-time bars and a replay of any recorded session.
               Everything is computed on your own machine; nothing is sent anywhere.`,
    },
    {
        h: 'No accounts, no keys',
        body: `Nothing in the core program needs a login or an API key. The default data source is the
               exchange's public market-data stream, which is free and anonymous, so a fresh install is
               fully functional the moment the engine is started.
               Two optional extras exist and both are free: a <b>Telegram bot</b> (so alerts reach your
               phone) and an outgoing <b>webhook</b> if you happen to run your own endpoint. Skip both and
               nothing is lost except phone notifications.`,
    },
    {
        h: 'Keyboard & search',
        body: `<p>The palette (<b>Ctrl+K</b> or <b>/</b>) searches two things at once: the program
               (views, panels, settings, actions, alert rules, walkthroughs) and the <b>market</b> —
               type a ticker and it returns live rows with the feed each one really comes from
               (<b>IEX</b>, <b>Delayed SIP</b>, <b>Indicative</b>, <b>Crypto · Bybit</b>), the US session
               state and the price with a sparkline.</p>
               <table class="guide-table">
                 <tr><td><b>Ctrl+K</b> / <b>/</b></td><td>Open the palette.</td></tr>
                 <tr><td><b>Alt+A</b></td><td>Jump to the <b>Alpaca</b> view (the optional broker account).</td></tr>
                 <tr><td><b>Enter</b></td><td>Open the highlighted result. On a symbol: switch the whole
                     program to it and open the view chosen in <i>Settings → search default view</i>
                     (order flow by default).</td></tr>
                 <tr><td><b>Ctrl+Enter</b></td><td>Open a symbol in a second view without losing the first.</td></tr>
                 <tr><td><b>Ctrl+Shift+Enter</b></td><td>Open the <b>option chain</b> for an equity (needs a
                     linked Alpaca account).</td></tr>
                 <tr><td><b>Ctrl+Click</b> a row</td><td>Multi-select symbols, then <b>Add to watchlist</b>
                     or <b>Compare feeds</b>.</td></tr>
                 <tr><td><b>Shift+Enter</b></td><td>Show the operator help.</td></tr>
                 <tr><td><b>Esc</b></td><td>Close the palette, the chain panel or the wizard.</td></tr>
                 <tr><td><b>↑ ↓</b></td><td>Move between results.</td></tr>
               </table>
               <p style="margin-top:8px">Operators filter instead of guessing:</p>
               <div class="help-cmd"><code>type:option underlying:AAPL strike:&gt;200 exp:max</code>
                   <button class="btn small help-copy" data-copy="type:option underlying:AAPL strike:>200 exp:max">Copy</button></div>
               <div class="help-cmd"><code>type:stock vol:&gt;1M sort:chg</code>
                   <button class="btn small help-copy" data-copy="type:stock vol:>1M sort:chg">Copy</button></div>
               <div class="help-cmd"><code>AAPL, MSFT, NVDA</code>
                   <button class="btn small help-copy" data-copy="AAPL, MSFT, NVDA">Copy</button></div>
               <p>A comma-separated list of tickers becomes a multi-select in one go. Anything the parser
               cannot read stays ordinary text (and says so), so a half-typed operator never blanks the
               palette.</p>`,
    },
    {
        h: 'Optional: a broker account (Alpaca)',
        body: `The <b>Alpaca</b> view links a real US brokerage account as an extra data source: US stocks, ETFs,
               options and crypto instruments, a real-time IEX tape, 15-minute-delayed full-market history, Benzinga
               news and the US market calendar. A <b>paper account is free</b> and needs only an email address.
               Alpaca publishes trades, quotes and bars — <b>no order book</b> — so the depth views stay on the
               exchange feed. The walkthrough with the exact clicks lives in the Guide:
               <b>Alpaca: how to get API keys</b>. Nothing in the program requires an account.`,
    },
    {
        h: 'First run',
        body: `<ol>
                 <li>Press <b>Start engine</b> in the top bar. The default setup streams BTCUSDT.</li>
                 <li>Open <b>Instruments</b> → <b>Validate against exchange</b> → <b>Enable all supported</b>
                     to stream every crypto instrument the venue lists.</li>
                 <li>Leave the app running for a couple of minutes: the heatmap, trackers and profiles need
                     a little tape before they have something to show.</li>
                 <li>Work through the views in rail order — Overview, Chart, Heatmap, Order Flow, Depth,
                     Time &amp; Sales, Trackers, CVD, Profile, Frames, Signals, Strategy, Performance.</li>
                 <li>Optional: connect Telegram under Settings, then flip <b>TG</b> per rule in the
                     Alerts view to choose what reaches your phone.</li>
               </ol>`,
    },
    {
        h: 'The views',
        body: `<table class="guide-table">
                 <tr><td>Heatmap</td><td>Resting liquidity over time. Bright = size; bubbles = executed trades;
                     cyan/purple markers = liquidity stacked or pulled. Walls are listed below the map.</td></tr>
                 <tr><td>Trackers</td><td>Icebergs, sweeps, stop runs, big trades, liquidations, the
                     imbalance ladder (the reference layout rule) and big-trade zones.</td></tr>
                 <tr><td>CVD</td><td>Cumulative delta against price, with multi-window deltas and divergence
                     detections.</td></tr>
                 <tr><td>Profile</td><td>TPO ladder: POC, value area, initial balance, single prints, plus
                     developing value area and virgin POCs from stored sessions.</td></tr>
                 <tr><td>Frames</td><td>Range, Renko, Reversal, Tick and Volume bars built live.</td></tr>
                 <tr><td>Replay</td><td>Re-run recorded ticks or the exchange tape through every analyser.</td></tr>
                 <tr><td>Alerts</td><td>Rules, the live alert log, persisted history and Telegram routing.</td></tr>
               </table>`,
    },
    {
        h: 'Where your data lives',
        body: `Settings, history and logs live in your user config folder (the path is shown in Settings and
               under the rail). The SQLite history keeps seven days of detections by default, and the app
               prunes older rows automatically. Deleting the config file returns the program to first-run
               defaults without touching the installed code.`,
    },
    {
        h: 'Optional integrations — all free, all keyless',
        body: `<p>Nothing here is required: the analytics run on public data with no account of any kind. Each item
                 below is optional, free, and switchable on its own. The setup assistant collects them in one
                 pass, and you can change any of it later in Settings.</p>
               <table class="guide-table">
                   <tr><td><b>Data feed</b></td><td>Bybit public WebSocket + REST (order book, trades,
                       liquidations). No key, no account, works worldwide. MT5 is optional and Windows-only if you
                       have a broker terminal.</td></tr>
                   <tr><td><b>ntfy push</b></td><td>Phone notifications with <i>no account at all</i>: install the
                       ntfy app, subscribe to a topic name you invent, type it in Setup → Alerts. Self-hosted server
                       URLs also work.</td></tr>
                   <tr><td><b>Telegram bot</b></td><td>Free bot via @BotFather (three steps in Setup → Alerts).
                       Alert rules route per channel: tick Telegram, ntfy, Email or Webhook for each rule in the
                       Alerts view.</td></tr>
                   <tr><td><b>Email</b></td><td>Any mailbox over SMTP. Gmail/Outlook want a 16-character
                       <i>app password</i> (their normal password will be refused) — Setup → Alerts → Email.</td></tr>
                   <tr><td><b>Webhook</b></td><td>Paste a Discord or Slack incoming-webhook URL, or any endpoint
                       that takes a JSON POST. Fired alerts arrive as JSON.</td></tr>
                   <tr><td><b>Market context</b></td><td>The venue's own funding rate, open interest and
                       long/short ratio, plus the alternative.me Fear &amp; Greed index and crypto RSS headlines —
                       all public and keyless. Shows on the Overview.</td></tr>
               </table>
               <p class="dim">Credentials live in your local config file and are sent only to the service you aimed
               them at. A "Test" button next to each field proves it works before you save.</p>`,
    },
    {
        h: 'Reading participants’ intent (the order book)',
        body: `<p>The <b>Participants’ intent</b> card on the Overview reads the order book the way a
                 desk does, and it is the one panel that can say something before the chart moves.</p>
               <table>
                   <tr><td><b>Book pressure</b></td><td>Weighted liquidity in the top levels — each level
                       discounted by distance — shown as a percentage of this instrument’s own recent
                       normal. 80%+ means size has been committed at the touch. The card counts down a
                       5-minute training period first: a percentage of normal means nothing until there is a
                       normal, so nothing alerts during training.</td></tr>
                   <tr><td><b>Absorption</b></td><td>Aggression that fails to move price. Buyers hitting the
                       ask with no rise = sellers absorbing. The score rises when price moves <i>against</i>
                       the aggressor, which is the strongest version of the read.</td></tr>
                   <tr><td><b>Depth change</b></td><td>Size added or pulled within the tracked window, per
                       side — a floor being built, or a floor being removed.</td></tr>
                   <tr><td><b>Tape quality</b></td><td>How prints arrived: at the bid, at the ask, inside the
                       spread, or through the touch ("slippage" — the passive side was not there). Prints
                       are only judged against a book younger than 1.5 s, and a print within half a tick of
                       the touch counts as <i>at</i> the touch, not as slippage.</td></tr>
                   <tr><td><b>Pulled size</b></td><td>Large orders near price that vanished without being
                       traded — one is noise, a cluster on one side is information.</td></tr>
                   <tr><td><b>Trapped side</b></td><td>A level that broke and was reclaimed: whoever chased
                       the break is now wrong-footed.</td></tr>
               </table>
               <p class="dim">Public feeds carry no participant identities. Pulled size and trapped sides are
               inferences from behaviour, and the card labels them that way. The verdict line names the level
               that matters, so the read is always attached to a price you can watch.</p>`,
    },
    {
        h: 'Scenarios worth practising',
        body: `<p>Ten worked scenarios live in <b>docs/USE_CASES.md</b> — each with its setup, what to
                 watch, and what invalidates the read. The short version:</p>
               <ul>
                 <li><b>Absorption</b> — heavy prints into a resting wall that holds (Heatmap + Order Flow).</li>
                 <li><b>Stop run</b> — a fast, wide burst that exhausts itself (Trackers + CVD).</li>
                 <li><b>Sweep &amp; reclaim</b> — levels taken in under a second, then price stalls back.</li>
                 <li><b>Block print</b> — one huge or reassembled print near the open.</li>
                 <li><b>Delta divergence</b> — price makes a new extreme, CVD does not follow.</li>
                 <li><b>Stack vs pull</b> — resting size building or vanishing near price.</li>
                 <li><b>Replay review</b> — re-run your worst hour through the same analysers.</li>
                 <li><b>Alerting hygiene</b> — only page yourself for what you actually act on.</li>
                 <li><b>Cross-instrument context</b> — is this BTC, or is it the whole market?</li>
                                <li><b>Scanner</b> — one ranked row per instrument (the Market Analyzer view): sort by delta, tape speed, book pressure, absorption, VWAP distance or the stated composite score, and click a row to switch the whole app to that instrument.</li>
                 <li><b>Reading intent before the move</b> — book pressure above 80% of normal, absorption,
                     a cluster of pulled size and a trapped side all pointing the same way.</li>
</ul>
               <p class="dim">The Performance view journals signals and outcomes: that journal is the only
               evidence about which scenario is working for you.</p>`,
    },
    {
        h: 'If something looks wrong',
        body: `<ul>
                 <li><b>Engine says Stopped</b> — press Start engine. The panels stay empty until data flows.</li>
                 <li><b>No instruments</b> — Instruments → Validate, then enable the ones marked "listed".</li>
                 <li><b>Heatmap empty for the first minute</b> — expected; it needs order-book updates to build columns.</li>
                 <li><b>Iceberg/stop-run labels say "inferred"</b> — the public feed publishes no order ids, so those two
                     are statistical inferences rather than MBO facts.</li>
                 <li><b>Alert tone is silent</b> — browsers block audio until the first click; press anywhere once, and
                     check the Sound box in the Alerts view.</li>
                 <li><b>Logs</b> — the Logs view shows the live engine log, including feed errors with reasons.</li>
               </ul>`,
    },
];

function buildGuideView() {
    if (document.getElementById('guideView')) return;

    const rail = document.querySelector('.rail');
    if (rail && !document.querySelector('.nav-item[data-view="guide"]')) {
        const btn = document.createElement('button');
        btn.className = 'nav-item';
        btn.dataset.view = 'guide';
        btn.innerHTML = '<span class="nav-icon">?</span> Guide';
        btn.onclick = () => window.showView && window.showView('guide');
        const logsBtn = rail.querySelector('.nav-item[data-view="logs"]');
        rail.insertBefore(btn, logsBtn || null);
    }

    const main = document.querySelector('main.views');
    if (!main) return;
    const section = document.createElement('section');
    section.className = 'view';
    section.dataset.view = 'guide';
    section.id = 'guideView';
    section.innerHTML = `
        <div class="view-head">
            <div class="view-title">Guide &amp; setup</div>
            <div class="view-sub">what this program does, how to get the most out of it, and how to set it up</div>
            <div class="grow"></div>
            <button class="btn small" id="guideSetupBtn" title="Re-open the step-by-step setup assistant">Run setup assistant</button>
            <button class="btn small" id="guideCentreBtn" title="Search every topic, walkthrough and screenshot in the Help Centre">Search the Help Centre</button>
        </div>
        <div id="guideBody"></div>`;

    const body = section.querySelector('#guideBody');
    body.innerHTML = GUIDE_SECTIONS.map((s) => `
        <div class="card" style="margin-bottom:12px">
            <div class="card-head"><span class="card-title">${s.h}</span></div>
            <div class="card-body guide-copy">${s.body}</div>
        </div>`).join('');

    main.appendChild(section);
    section.querySelector('#guideSetupBtn').onclick = () => openWizard(true);
    const centreBtn = section.querySelector('#guideCentreBtn');
    if (centreBtn) centreBtn.onclick = () => {
        if (window.OFAPHELP) OFAPHELP.open('');
        else toast($('#guideBody') || document.body, 'The Help Centre is not loaded in this build.', 'info');
    };
    applyTips(section);
}

/* ══════════════════════════════════════════════════════════════════
   3. First-run setup wizard
   ══════════════════════════════════════════════════════════════════ */

function guideStyles() {
    if (document.getElementById('guideStyles')) return;
    const style = document.createElement('style');
    style.id = 'guideStyles';
    style.textContent = `
        .guide-copy { line-height: 1.55; color: var(--text-secondary); }
        .guide-copy b { color: var(--text-primary); }
        .guide-copy ol, .guide-copy ul { margin: 6px 0 6px 18px; padding: 0; }
        .guide-copy li { margin: 3px 0; }
        .guide-table { width: 100%; border-collapse: collapse; margin-top: 4px; }
        .guide-table td { padding: 6px 8px; border-bottom: 1px solid rgba(34,48,73,.5); vertical-align: top; }
        .guide-table td:first-child { width: 150px; color: var(--text-primary); font-weight: 600; }
        .wiz-overlay { position: fixed; inset: 0; background: rgba(6,10,18,.72); display: grid;
            place-items: center; z-index: 500; backdrop-filter: blur(2px); }
        .wiz-card { width: min(720px, 92vw); max-height: 88vh; overflow: auto; background: var(--bg-panel);
            border: 1px solid var(--border-strong); border-radius: 14px; box-shadow: 0 24px 60px rgba(0,0,0,.5); }
        .wiz-head { display: flex; align-items: center; gap: 10px; padding: 14px 18px;
            border-bottom: 1px solid var(--border); }
        .wiz-title { font-weight: 650; font-size: 15px; }
        .wiz-sub { color: var(--text-muted); font-size: 12px; }
        .wiz-body { padding: 16px 18px; color: var(--text-secondary); line-height: 1.55; }
        .wiz-body b { color: var(--text-primary); }
        .wiz-body .field { margin-bottom: 10px; }
        .wiz-list { max-height: 260px; overflow: auto; border: 1px solid var(--border); border-radius: 8px;
            padding: 8px 10px; margin: 8px 0; }
        .wiz-list label { display: flex; gap: 8px; align-items: center; padding: 2px 0; font-family: var(--font-mono); font-size: 12px; }
        .wiz-foot { display: flex; align-items: center; gap: 8px; padding: 12px 18px;
            border-top: 1px solid var(--border); }
        .wiz-dots { display: flex; gap: 6px; margin-right: auto; }
        .wiz-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border-strong); }
        .wiz-dot.on { background: var(--blue); }
        .wiz-note { background: rgba(79,140,255,.08); border: 1px solid rgba(79,140,255,.25);
            border-radius: 8px; padding: 8px 10px; margin: 8px 0; font-size: 12.5px; }
        .wiz-ok { color: var(--green); }
        .wiz-bad { color: var(--red); }`;
    document.head.appendChild(style);
}

/* ── wizard guidance system ─────────────────────────────────────────────────
   Three layers, referenced by every step that needs them:
     wizFooter()   what this unlocks + where to go deeper, with a real deep link
     wizGo()       close the assistant, open the panel, say why
     wizGuard()    the inline banner used when a choice would leave the app empty
*/
function wizGo(view, why) {
    closeWizard();
    if (view === 'hotkeys') {                  // the keyboard map — an overlay, like the guide
        if (window.OFAPMenu) OFAPMenu.showHotkeys(true);
        return;
    }
    if (view === 'menu') {                     // the ☰ panel, not a view section
        const btn = document.getElementById('menuBtn');
        if (btn) { btn.click(); return; }
        if (typeof openGuide === 'function') { openGuide(); return; }
    }
    /* A deep link may name a surface that is not a view section (the Guide is an overlay, the
       config is a modal). Never call showView blind: a missing section used to throw
       "Cannot read properties of null (reading 'classList')" out of ui.js. */
    const section = document.querySelector(`.view[data-view="${view}"]`);
    if (section && typeof showView === 'function') showView(view);
    else if (typeof openGuide === 'function') openGuide();
    else toast($('#guideBody') || document.body, 'That panel is not open in this build.', 'info');
    toast($('#guideBody') || document.body, why || 'Opened for you.', 'info');
}

function wizFooter({ unlocks, deeper, view, label }) {
    const link = view
        ? `<div style="margin-top:6px"><button class="btn small" data-wiz-go="${G_ESC(view)}"
             data-wiz-why="${G_ESC(deeper || '')}">${G_ESC(label || 'Open ' + view)}</button></div>`
        : '';
    return `<div class="wiz-note"><b>What this unlocks:</b> ${unlocks}<br><span class="dim">Where to go
        deeper:</span> ${deeper}${link}</div>`;
}


/* The professional path is a superset, not a different wizard: wizList() decides which steps are
   in play, and every navigational read (count, dots, Next label, collect) goes through it so the
   two depths can never disagree about how long the setup is. */
function wizList() {
    return (GUIDE.mode === 'pro') ? WIZ_STEPS.concat(WIZ_PRO) : WIZ_STEPS;
}

const WIZ_STEPS = [
    {
        title: 'Welcome',
        render: () => `
            <p>This assistant sets the program up in about a minute. Everything it asks for is optional —
            the core analytics need <b>no account and no API key</b>.</p>
            <p>You can skip it entirely and press <b>Start engine</b> at any time; the defaults stream
            BTCUSDT from the exchange's public feed.</p>
            <div class="wiz-note">Steps: data source → instruments → <b>Alpaca (optional)</b> → feeds &amp;
            history → optional phone alerts → finish. Every step can be skipped.</div>
            <div class="wiz-note"><b>The default instrument setup.</b> Out of the box the engine streams three
            crypto majors from the exchange's <b>public</b> feed — BTCUSDT, ETHUSDT and SOLUSDT — with trades,
            order book depth and candles. No account, no key, nothing to configure: that set is enough to
            exercise every panel, and it is what the wizard leaves in place if you change nothing here.<br>
            The full catalogue is far larger. The <b>Instruments</b> panel is the control room for it: it lists
            the venue's whole perpetual set (hundreds of symbols, checked against the exchange's public
            instrument list), lets you enable or disable each one, and can pick up MetaTrader 5 symbols when
            that terminal is running. More instruments means more panels and more CPU, so add deliberately.
            <div style="margin-top:6px"><button class="btn small" id="wizOpenInstruments"
                title="Close the assistant and go to the Instruments panel where the full set lives">Open the Instruments panel</button></div></div>`,
        after: () => {
            const btn = document.getElementById('wizOpenInstruments');
            if (btn) btn.onclick = () => {
                closeWizard();
                showView('instruments');
                toast($('#guideBody') || document.body,
                    'The full instrument set lives here: validate against the venue, then enable what you need.', 'info');
            };
        },
    },
    {
        title: 'Depth',
        render: () => `
            <p>Two ways through this setup. Both end with a working program; they differ in how much
            of it you shape on the way.</p>
            <div class="wiz-grid" style="display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">
                <div class="wiz-note"><b>Express</b> &mdash; about a minute.<br>
                Public feed, the three majors, sensible engine defaults, engine running. Everything
                here is changeable later from the panels; nothing is locked in.</div>
                <div class="wiz-note"><b>Professional</b> &mdash; the full capability path.<br>
                Feed budget and staleness, the full instrument catalogue, engine internals (row size,
                aggregation, value area), analytics thresholds, the studies runtime, layout and
                workspaces, hotkeys, bridges, and a validation checklist that proves each capability
                is working before you leave.</div>
            </div>
            <div class="wiz-note"><b>What this unlocks:</b> the express path gets you streaming in a
            minute; the professional path gets you to the point where every feature in the program is
            configured, understood and verified &mdash; the state a desk user needs on day one.<br>
            <span class="dim">Where to go deeper:</span> whatever you pick, the Guide's panel map
            explains what each surface is for.
            ${wizFooter({ unlocks: 'a working engine now, or a fully configured one',
                          deeper: 'the panel map in the Guide is the index for every panel',
                          view: 'guide', label: 'Open the panel map' })}</div>
            <p class="dim">Switch depth at any time with the Express / Professional buttons at the
            bottom of this window.</p>
        `,
    },
    {
        title: 'Data source',
        render: () => {
            const src = GUIDE.cfg.data_source || 'bybit';
            const mt5 = (S.caps && S.caps.mt5) || {};
            const nt = (S.caps && S.caps.ninjatrader) || {};
            return `
            <div class="field"><label>Where should market data come from?</label>
                <label class="switch"><input type="radio" name="wizSrc" value="bybit" ${src === 'bybit' ? 'checked' : ''}>
                    Bybit — exchange public feed, free, anonymous, works on Windows and macOS <b>(recommended)</b></label>
                <label class="switch"><input type="radio" name="wizSrc" value="binance" ${src === 'binance' ? 'checked' : ''}>
                    Binance USDⓈ-M futures — public feed, no key, crypto perpetuals only</label>
                <label class="switch"><input type="radio" name="wizSrc" value="hyperliquid" ${src === 'hyperliquid' ? 'checked' : ''}>
                    Hyperliquid — public feed, no key, crypto perpetuals only</label>
                <label class="switch"><input type="radio" name="wizSrc" value="okx" ${src === 'okx' ? 'checked' : ''}>
                    OKX — public feed, no key, crypto perpetuals only</label>
                <label class="switch"><input type="radio" name="wizSrc" value="mt5" ${src === 'mt5' ? 'checked' : ''}>
                    MetaTrader 5 terminal — Windows only, needs a broker install${mt5.available === false ? ' (not detected here)' : ''}</label>
                <label class="switch"><input type="radio" name="wizSrc" value="ninjatrader" ${src === 'ninjatrader' ? 'checked' : ''}>
                    NinjaTrader 8 — futures via the bridge add-on this suite ships${nt.available ? ' (bridge running)' : ''}</label>
                <label class="switch"><input type="radio" name="wizSrc" value="both" ${src === 'both' ? 'checked' : ''}>
                    Both</label></div>
            <div class="wiz-note">Whatever you pick here, the <b>instruments</b> stay as configured: the default
            three crypto majors (BTCUSDT, ETHUSDT, SOLUSDT) until you change them in the <b>Instruments</b> panel,
            which holds the much larger venue catalogue.</div>
            <div class="wiz-note">The public feed needs no account, no key and no broker. MetaTrader 5 additionally
            requires that terminal to be installed and logged in — ${mt5.available === false ? `<span class="wiz-bad">not detected on this machine (${G_ESC(mt5.reason || 'unavailable')})</span>` : '<span class="wiz-ok">detected on this machine</span>'}.</div>
            <div class="wiz-note"><b>NinjaTrader 8</b> streams your terminal\u2019s own futures instruments
            (NQ, ES, MNQ\u2026) through the bridge add-on this suite ships as source ’ copy its .cs files into
            <i>Documents\\NinjaTrader 8\\bin\\Custom\\AddOns</i>, press <i>F5</i> in the platform’s
            own NinjaScript Editor and answer the trust prompt once
            (the Platforms \u25b8 NinjaTrader card walks through it, with a live test). The platform is
            free and demo accounts work — ${nt.available ? '<span class="wiz-ok">the bridge is answering on this machine</span>' : '<span class="dim">the bridge is not running here right now</span>'}.</div>
            <button class="btn small" id="wizTestNet">Test the public feed</button>
            <span class="dim" id="wizTestResult"></span>
            ${wizFooter({
                unlocks: 'every candle, print, order book level and profile in the app starts here — the public feed needs no account, so this is the one choice with no downside.',
                deeper: 'the engine streams what you enable under Instruments; the Connections menu (☰) shows every free source with a live status dot, and the Guide explains which panels need depth versus trades.',
                view: 'overview',
                label: 'Open Overview (and see the Guide via ⌘/?)',
            })}`;
        },
        after: () => {
            const btn = document.getElementById('wizTestNet');
            if (!btn) return;
            btn.onclick = async () => {
                const out = document.getElementById('wizTestResult');
                btn.disabled = true;
                out.textContent = 'checking the public endpoint… (validates every configured symbol, ~10 s)';
                try {
                    const caps = await api('/api/control/capabilities?refresh=true');
                    S.caps = caps;
                    const n = Object.values(caps.bybit_symbols || {}).filter(Boolean).length;
                    out.innerHTML = n ? `<span class="wiz-ok">reachable — ${n} configured instrument(s) listed</span>`
                                      : '<span class="wiz-bad">reachable, but none of the configured instruments are listed — use “Add venue instruments” on the next step</span>';
                } catch (e) { out.innerHTML = `<span class="wiz-bad">${G_ESC(String(e))}</span>`; }
                btn.disabled = false;
            };
        },
        collect: () => {
            const picked = document.querySelector('input[name="wizSrc"]:checked');
            if (picked) GUIDE.cfg.data_source = picked.value;
        },
    },
    {
        title: 'Instruments',
        render: () => {
            const bybit = (S.caps && S.caps.bybit_symbols) || {};
            const rows = (GUIDE.cfg.instruments || []).map((i) => {
                const supported = i.symbol in bybit ? !!bybit[i.symbol] : i.bybit_symbol !== '';
                return `<label><input type="checkbox" data-wiz-inst="${G_ESC(i.symbol)}" ${i.enabled ? 'checked' : ''}>
                    ${G_ESC(i.symbol)} <span class="dim">${G_ESC(i.asset_class || '')}</span>
                    ${supported ? '<span class="tag ok">listed</span>' : '<span class="tag no">n/a</span>'}</label>`;
            }).join('');
            return `
            <p>Pick what the engine should stream. More instruments means more panels and more CPU;
            the heatmap and trackers work best on the two or three you actually watch.</p>
            <div class="wiz-note">A fresh install ships one crypto instrument. The button below asks the venue
            for its public instrument list (no account needed) and adds the well-known ones with their real
            tick sizes.</div>
            <div class="row" style="margin-bottom:6px">
                <button class="btn small primary" id="wizAddMajors" title="Fetch the venue's public instrument list and add the majors">Add venue instruments</button>
                <div class="wiz-note wiz-warn" id="wizEmptyInst" style="display:none">
                    <b>⚠ No instruments enabled — every panel will render empty.</b>
                    <div style="margin-top:6px">
                        <button class="btn small" id="wizEmptyInstFix">Use the default three (BTCUSDT, ETHUSDT, SOLUSDT)</button>
                        <button class="btn small" id="wizEmptyInstSkip">Continue anyway</button>
                    </div>
                </div>
                ${wizFooter({
                    unlocks: 'the panels you can actually read: footprint depth needs a dozen liquid instruments to compare, while three majors are enough to learn every view without loading the CPU.',
                    deeper: 'Instruments → Validate checks every symbol against the venue\u2019s public list (free, ~10 s); enable the ones marked “listed”. Start with three, add a handful more once you know which panels you live in.',
                    view: 'instruments',
                    label: 'Open the Instruments panel',
                })}
                <button class="btn small" id="wizAllCrypto" title="Tick every instrument the venue can serve">Select all venue-listed</button>
                <button class="btn small" id="wizClear">Clear</button>
                <button class="btn small" id="wizJustBtc">Just BTCUSDT</button>
            </div>
            <div class="dim" id="wizAddResult" style="margin-bottom:6px"></div>
            <div class="wiz-list">${rows}</div>`;
        },
        after: () => {
            const set = (fn) => () => document.querySelectorAll('input[data-wiz-inst]').forEach(fn);
            const all = document.getElementById('wizAllCrypto');
            const clear = document.getElementById('wizClear');
            const btc = document.getElementById('wizJustBtc');
            const bybit = (S.caps && S.caps.bybit_symbols) || {};
            if (all) all.onclick = set((inp) => {
                inp.checked = inp.dataset.wizInst in bybit ? !!bybit[inp.dataset.wizInst] : true;
            });
            if (clear) clear.onclick = set((inp) => { inp.checked = false; });
            if (btc) btc.onclick = set((inp) => { inp.checked = inp.dataset.wizInst === 'BTCUSDT'; });

            const addBtn = document.getElementById('wizAddMajors');
            if (!addBtn) return;
            addBtn.onclick = async () => {
                const out = document.getElementById('wizAddResult');
                addBtn.disabled = true;
                out.textContent = 'asking the venue for its instrument list… (~10 s)';
                try {
                    const cat = await api('/api/control/instruments/catalog');
                    if (!cat.ok) { out.innerHTML = `<span class="wiz-bad">${G_ESC(cat.error || 'catalogue unavailable')}</span>`; addBtn.disabled = false; return; }
                    const keep = new Set(Array.from(document.querySelectorAll('input[data-wiz-inst]'))
                        .filter((i) => i.checked).map((i) => i.dataset.wizInst));
                    const r = await api('/api/control/instruments/add', {
                        method: 'POST',
                        body: { symbols: cat.majors.map((m) => m.symbol), enable: true },
                    });
                    const gained = new Set([...(r.added || []), ...(r.updated || [])]);
                    GUIDE.cfg.instruments = (r.config.instruments || []).map((i) => ({ ...i }));
                    // re-render from the new config, then re-tick: renderStep's collect()
                    // would otherwise reset the checkboxes to their pre-add state
                    renderStep(GUIDE.step);
                    document.querySelectorAll('input[data-wiz-inst]').forEach((inp) => {
                        if (gained.has(inp.dataset.wizInst) || keep.has(inp.dataset.wizInst)) inp.checked = true;
                    });
                    const _cur = wizList()[GUIDE.step];
                    if (_cur && _cur.collect) _cur.collect();
                    const note = document.getElementById('wizAddResult');
                    if (note) note.innerHTML = `<span class="wiz-ok">added ${(r.added || []).length}, updated ${(r.updated || []).length}` +
                        ` — the venue lists ${cat.venue_total} instruments; the new ones are ticked, untick any you do not want to stream</span>`;
                    addBtn.disabled = false;
                    return;
                } catch (e) { out.innerHTML = `<span class="wiz-bad">${G_ESC(String(e))}</span>`; }
                addBtn.disabled = false;
            };
        },
        collect: () => {
            const chosen = new Set(Array.from(document.querySelectorAll('input[data-wiz-inst]'))
                .filter((i) => i.checked).map((i) => i.dataset.wizInst));
            (GUIDE.cfg.instruments || []).forEach((i) => { i.enabled = chosen.has(i.symbol); });
        },
    },
    {
        title: 'Alpaca (optional)',
        render: () => {
            const alp = (GUIDE.cfg.alpaca = GUIDE.cfg.alpaca || {});
            const env = alp.paper === false ? 'live' : 'paper';
            const url = 'https://app.alpaca.markets/signup';
            return `
            <p><b>Optional step.</b> Alpaca Markets is a real US brokerage with an API: US stocks, ETFs, options and
            crypto, a <b>free paper-trading account</b> (email signup, virtual money, resettable), Benzinga news and the
            US market calendar. Linking adds those instruments to this program — <b>nothing here needs it</b>, and you
            can skip this step.</p>
            <div class="wiz-note">Honest limits: Alpaca publishes trades, quotes and bars, <b>not the order book</b>, so
            the heatmap, the DOM ladder and the participants'-intent reader stay on the exchange feed. Free-plan
            real-time US data is IEX (one venue); the full-market SIP tape is readable once it is older than
            15&nbsp;minutes.</div>
            <table class="guide-table" style="margin-top:8px">
                <tr><td><b>1 · Create the account</b></td><td>Sign up and choose the <b>paper</b> environment (live needs
                    identity verification; you can switch later). Copy this address into your browser:
                    <div class="help-cmd"><code>${G_ESC(url)}</code>
                    <button class="btn small help-copy" data-copy="${G_ESC(url)}" title="Copy the address">Copy</button></div></td></tr>
                <tr><td><b>2 · Generate keys</b></td><td>In the Alpaca dashboard: <b>Home → API keys → Generate</b>,
                    environment <b>Paper</b>. The secret is displayed <b>exactly once</b> — copy it before closing the
                    dialog. Paper and live keys are different pairs and do not work against each other's host.</td></tr>
                <tr><td><b>3 · Paste them here</b></td><td>Nothing is stored until Alpaca confirms the keys work.</td></tr>
            </table>
            <div class="row" style="gap:10px;flex-wrap:wrap;margin-top:8px">
                <div class="field" style="flex:1;min-width:200px"><label>API key ID</label>
                    <input type="text" id="wizAlpKey" autocomplete="off" spellcheck="false"
                        placeholder="${alp.key_id ? G_ESC(alp.key_id) : 'PK…'}"></div>
                <div class="field" style="flex:1;min-width:200px"><label>API secret</label>
                    <input type="password" id="wizAlpSecret" autocomplete="new-password"
                        placeholder="${alp.key_id ? '(saved — type to replace)' : 'your secret key'}"></div>
                <div class="field" style="flex:0 0 170px"><label>Environment</label>
                    <select id="wizAlpPaper" title="Paper is Alpaca's simulation: identical API, no funding, resettable.">
                        <option value="1" ${env === 'paper' ? 'selected' : ''}>Paper (simulation, free)</option>
                        <option value="0" ${env === 'live' ? 'selected' : ''}>Live (real money)</option></select></div>
            </div>
            <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:6px">
                <button class="btn primary" id="wizAlpSave">Test connection &amp; save</button>
                <span class="dim" id="wizAlpResult"></span>
            </div>
            <div id="wizAlpCap" class="dim" style="margin-top:8px">What the free plan reaches: IEX real-time tape
            (30 stream symbols), SIP full-market history 15 minutes delayed, indicative options, Benzinga news and the
            US market calendar. Algo Trader Plus removes the delay and the caps.</div>
            <div class="wiz-note" style="margin-top:8px">Skip it now if you are not ready — the <b>Alpaca</b> view in the
            rail (or <b>Alt+A</b>) and the “Alpaca: how to get API keys” walkthrough in the Guide stay available, and
            this assistant reopens from the setup button in the top-left.</div>`;
        },
        after: () => {
            const btn = document.getElementById('wizAlpSave');
            if (!btn) return;
            btn.onclick = async () => {
                const key = (document.getElementById('wizAlpKey') || {}).value || '';
                const secret = (document.getElementById('wizAlpSecret') || {}).value || '';
                const paperEl = document.getElementById('wizAlpPaper');
                GUIDE.cfg.alpaca = GUIDE.cfg.alpaca || {};
                GUIDE.cfg.alpaca.paper = paperEl ? paperEl.value !== '0' : true;
                if (!key || !secret) {
                    wizAlpMsg('Both the key ID and the secret are needed — or skip this step.', 'err');
                    return;
                }
                btn.disabled = true;
                // one implementation for both front doors: the settings/Alpaca card and this step
                await alpacaSubmit('save', {
                    keyId: 'wizAlpKey', secretId: 'wizAlpSecret', paperId: 'wizAlpPaper',
                    msg: wizAlpMsg, refresh: false,
                });
                try {
                    const st = await api('/api/control/alpaca/status');
                    if (st && st.configured) {
                        GUIDE.cfg.alpaca.enabled = true;
                        GUIDE.cfg.alpaca.paper = !!st.paper;
                        // the keys themselves stay server-side (never round-tripped through this form)
                        const cap = document.getElementById('wizAlpCap');
                        if (cap && st.report) cap.innerHTML = typeof alpacaCapabilitySummaryHTML === 'function'
                            ? alpacaCapabilitySummaryHTML(st.report) : cap.innerHTML;
                    }
                } catch (e) { /* the message line already says what happened */ }
                btn.disabled = false;
            };
        },
        collect: () => {
            const paperEl = document.getElementById('wizAlpPaper');
            GUIDE.cfg.alpaca = GUIDE.cfg.alpaca || {};
            if (paperEl) GUIDE.cfg.alpaca.paper = paperEl.value !== '0';
        },
    },
    {
        title: 'Feeds, history & extras',
        render: () => {
            const atlas = GUIDE.cfg.atlas || (GUIDE.cfg.atlas = {});
            return `
            <label class="switch"><input type="checkbox" id="wizExtras" ${atlas.extras_enabled !== false ? 'checked' : ''}>
                Deep order book + liquidations + block-trade flags <span class="dim">(extra public streams the
                heatmap and stop-run trackers use)</span></label>
            <label class="switch" style="margin-top:8px"><input type="checkbox" id="wizHistory" ${(atlas.history || {}).enabled !== false ? 'checked' : ''}>
                Persist detections to disk <span class="dim">(seven days, pruned automatically)</span></label>
            <div class="wiz-note">Both extras are free public data — no account involved. Turning history off
            keeps the app lighter; turning the deep book off disables the heatmap's wall/stack/pull detection.</div>`;
        },
        collect: () => {
            const atlas = GUIDE.cfg.atlas || (GUIDE.cfg.atlas = {});
            atlas.extras_enabled = !!document.getElementById('wizExtras').checked;
            (atlas.history = atlas.history || {}).enabled = !!document.getElementById('wizHistory').checked;
        },
    },
    {
        title: 'Alerts & notifications (optional)',
        render: () => {
            const tg = GUIDE.cfg.telegram || (GUIDE.cfg.telegram = {});
            const notify = GUIDE.cfg.notify || (GUIDE.cfg.notify = {});
            const ntfy = notify.ntfy || (notify.ntfy = {});
            const email = notify.email || (notify.email = {});
            const atlas = GUIDE.cfg.atlas || (GUIDE.cfg.atlas = {});
            return `
            <p>Every alert shows up in the app whatever you do here. These channels push them to a phone or
            inbox as well — all free, all optional, and none of them can trade anything.</p>

            <details open><summary><b>ntfy push — no account at all</b> <span class="dim">(easiest)</span></summary>
                <div class="wiz-note">Install the ntfy app (iOS/Android/desktop), subscribe to any topic name you
                invent, and type that same name here. Nothing to sign up for, nothing to leak.</div>
                <div class="field"><label>Topic name</label><input type="text" id="wizNtfyTopic"
                    value="${G_ESC(ntfy.topic || '')}" placeholder="e.g. orderflow-tape-7k2"
                    title="Any name you choose. Keep it hard to guess: anyone who knows the topic can read it on ntfy.sh."></div>
                <div class="field"><label>Server</label><input type="text" id="wizNtfyServer"
                    value="${G_ESC(ntfy.server || 'https://ntfy.sh')}"
                    title="Leave as-is, or point at your own self-hosted ntfy server."></div>
                <div class="row"><button class="btn small" id="wizNtfyTest"
                    title="Sends one real test notification through ntfy now">Send test push</button>
                    <span class="dim" id="wizNtfyResult"></span></div>
            </details>

            <details><summary><b>Telegram bot</b> <span class="dim">(phone alerts, needs a free bot)</span></summary>
                <ol style="margin:4px 0 8px 18px">
                    <li>In Telegram, message <b>@BotFather</b> → <code>/newbot</code> → copy the token.</li>
                    <li>Message your new bot once (any text) so it may reply to you.</li>
                    <li>Message <b>@userinfobot</b> for your numeric chat id.</li>
                </ol>
                <div class="field"><label>Bot token</label><input type="password" id="wizTgToken"
                    value="${G_ESC(tg.bot_token || '')}" placeholder="123456:ABC-DEF…"
                    title="From @BotFather. Stored in your local config file only."></div>
                <div class="field"><label>Chat id</label><input type="text" id="wizTgChat"
                    value="${G_ESC(tg.chat_id || '')}" placeholder="e.g. 123456789"
                    title="Your numeric Telegram id — the bot sends to this chat."></div>
                <div class="row"><button class="btn small" id="wizTgTest"
                    title="Sends one real Telegram message now">Send test message</button>
                    <span class="dim" id="wizTgResult"></span></div>
            </details>

            <details><summary><b>Email</b> <span class="dim">(any mailbox; Gmail/Outlook need an app password)</span></summary>
                <div class="wiz-note">Use an app password, not your normal login — most providers block plain
                passwords for third-party apps.</div>
                <div class="row">
                    <div class="field" style="flex:2"><label>SMTP host</label><input type="text" id="wizMailHost"
                        value="${G_ESC(email.host || '')}" placeholder="smtp.gmail.com"
                        title="Your mail provider's outgoing server. Gmail: smtp.gmail.com (587, STARTTLS)."></div>
                    <div class="field" style="flex:1"><label>Port</label><input type="number" id="wizMailPort"
                        value="${G_ESC(String(email.port || 587))}" title="587 = STARTTLS, 465 = implicit TLS."></div>
                </div>
                <div class="row">
                    <div class="field" style="flex:1"><label>Username</label><input type="text" id="wizMailUser"
                        value="${G_ESC(email.username || '')}" placeholder="you@gmail.com"></div>
                    <div class="field" style="flex:1"><label>App password</label><input type="password" id="wizMailPass"
                        value="${G_ESC(email.password || '')}" placeholder="16-character app password"
                        title="Generated by your provider — never your main account password."></div>
                </div>
                <div class="row">
                    <div class="field" style="flex:1"><label>Send to</label><input type="text" id="wizMailTo"
                        value="${G_ESC(email.to || '')}" placeholder="you@gmail.com"
                        title="Where alerts are delivered. Comma-separate several addresses."></div>
                    <div class="field" style="flex:1"><label>From (optional)</label><input type="text" id="wizMailFrom"
                        value="${G_ESC(email.from || '')}" placeholder="defaults to username"></div>
                </div>
                <div class="row"><button class="btn small" id="wizMailTest"
                    title="Sends one real test email now">Send test email</button>
                    <span class="dim" id="wizMailResult"></span></div>
            </details>

            <details><summary><b>Webhook</b> <span class="dim">(Discord/Slack/your own automation)</span></summary>
                <div class="wiz-note">Paste a Discord or Slack incoming-webhook URL, or any endpoint that accepts
                a JSON POST — fired alerts are sent there as JSON.</div>
                <div class="field"><label>Webhook URL</label><input type="text" id="wizWebhookUrl"
                    value="${G_ESC(atlas.webhook_url || '')}" placeholder="https://discord.com/api/webhooks/…"
                    title="Any http(s) endpoint. Discord: Channel settings → Integrations → Webhooks → Copy URL."></div>
                <div class="row"><button class="btn small" id="wizWebhookTest"
                    title="POSTs one test alert to that URL now">Send test POST</button>
                    <span class="dim" id="wizWebhookResult"></span></div>
            </details>

            <label class="switch" style="margin-top:10px"><input type="checkbox" id="wizTgEnabled"
                ${tg.enabled ? 'checked' : ''}>Route order-flow alerts to these channels</label>
            <label class="switch" style="margin-top:8px" id="wizEmailRouteWrap">
                <input type="checkbox" id="wizEmailRoute" ${''}>
                Also email me — <b>only</b> for block trades and stop runs
                <span class="dim">(email is never applied to every rule: a busy tape would mail you every few seconds)</span>
            </label>`;
        },
        after: () => {
            const wire = (btnId, outId, send, label) => {
                const btn = document.getElementById(btnId);
                if (!btn) return;
                btn.onclick = async () => {
                    const out = document.getElementById(outId);
                    btn.disabled = true;
                    out.textContent = 'sending…';
                    try {
                        const r = await send();
                        out.innerHTML = r.ok ? `<span class="wiz-ok">${G_ESC(label || 'sent')}</span>`
                                             : `<span class="wiz-bad">${G_ESC(r.error || 'failed')}</span>`;
                    } catch (e) {
                        out.innerHTML = `<span class="wiz-bad">${G_ESC(String(e))}</span>`;
                    }
                    btn.disabled = false;
                };
            };
            const val = (id) => (document.getElementById(id)?.value || '').trim();
            wire('wizNtfyTest', 'wizNtfyResult', () => api('/api/atlas/notify/test', { method: 'POST', body: {
                channel: 'ntfy', topic: val('wizNtfyTopic'), server: val('wizNtfyServer'),
                symbol: (GUIDE.cfg.instruments || []).find((i) => i.enabled)?.symbol || 'TEST',
            } }), 'test push sent — check the ntfy app');
            wire('wizTgTest', 'wizTgResult', () => api('/api/atlas/notify/test', { method: 'POST', body: {
                channel: 'telegram', bot_token: val('wizTgToken'), chat_id: val('wizTgChat'),
            } }), 'test message sent — check Telegram');
            wire('wizMailTest', 'wizMailResult', () => api('/api/atlas/notify/test', { method: 'POST', body: {
                channel: 'email', host: val('wizMailHost'), port: Number(val('wizMailPort')) || 587,
                username: val('wizMailUser'), password: val('wizMailPass'),
                to: val('wizMailTo'), from: val('wizMailFrom'),
            } }), 'test email sent — check that inbox');
            wire('wizWebhookTest', 'wizWebhookResult', () => api('/api/atlas/webhook/test', { method: 'POST', body: {
                url: val('wizWebhookUrl'),
            } }), 'test POST delivered');
        },
        collect: () => {
            const tg = GUIDE.cfg.telegram || (GUIDE.cfg.telegram = {});
            const notify = GUIDE.cfg.notify || (GUIDE.cfg.notify = {});
            const ntfy = notify.ntfy || (notify.ntfy = {});
            const email = notify.email || (notify.email = {});
            const atlas = GUIDE.cfg.atlas || (GUIDE.cfg.atlas = {});
            const val = (id) => (document.getElementById(id)?.value || '').trim();
            tg.bot_token = val('wizTgToken');
            tg.chat_id = val('wizTgChat');
            const anyChannel = !!((tg.bot_token && tg.chat_id) || val('wizNtfyTopic') || val('wizMailHost') || val('wizWebhookUrl'));
            tg.enabled = !!document.getElementById('wizTgEnabled')?.checked && anyChannel;
            ntfy.topic = val('wizNtfyTopic');
            ntfy.server = val('wizNtfyServer') || 'https://ntfy.sh';
            ntfy.enabled = !!ntfy.topic;
            email.host = val('wizMailHost');
            email.port = Number(val('wizMailPort')) || 587;
            email.username = val('wizMailUser');
            email.password = val('wizMailPass');
            email.to = val('wizMailTo');
            email.from = val('wizMailFrom');
            email.use_tls = (Number(val('wizMailPort')) || 587) !== 465;
            email.enabled = !!(email.host && email.to);
            atlas.webhook_url = val('wizWebhookUrl');
        },
    },
    {
        title: 'Market context (optional)',
        render: () => {
            const ctx = GUIDE.cfg.context || (GUIDE.cfg.context = {});
            const sym = (GUIDE.cfg.instruments || []).find((i) => i.enabled)?.symbol || 'BTCUSDT';
            return `
            <p>Free public data that makes the tape easier to read. No account, no API key — switch any of it off
            and the app is unaffected.</p>
            <label class="switch"><input type="checkbox" id="wizCtxPositioning" ${ctx.positioning !== false ? 'checked' : ''}>
                Funding rate, open interest and the long/short ratio <span class="dim">(from the venue itself)</span></label>
            <label class="switch" style="margin-top:6px"><input type="checkbox" id="wizCtxFear" ${ctx.fear_greed !== false ? 'checked' : ''}>
                Fear &amp; Greed index <span class="dim">(alternative.me, daily)</span></label>
            <label class="switch" style="margin-top:6px"><input type="checkbox" id="wizCtxNews" ${ctx.news !== false ? 'checked' : ''}>
                Crypto headlines <span class="dim">(public RSS)</span></label>
            <div class="field" style="margin-top:8px"><label>Custom news feed (optional)</label>
                <input type="text" id="wizCtxNewsUrl" value="${G_ESC(ctx.news_url || '')}"
                    placeholder="https://your-feed/rss" title="Leave empty for CoinDesk + Cointelegraph + Decrypt; paste any RSS/Atom URL to replace them."></div>
            <div class="row"><button class="btn small" id="wizCtxTest"
                title="Fetches the context for your first instrument right now">Check now</button>
                <span class="dim" id="wizCtxResult"></span></div>
            <div class="wiz-note">It appears on the Overview as a “Market context” card, refreshed every minute.</div>`;
        },
        after: () => {
            const btn = document.getElementById('wizCtxTest');
            if (!btn) return;
            btn.onclick = async () => {
                const out = document.getElementById('wizCtxResult');
                const sym = (GUIDE.cfg.instruments || []).find((i) => i.enabled)?.symbol || 'BTCUSDT';
                btn.disabled = true; out.textContent = 'fetching…';
                try {
                    const url = (document.getElementById('wizCtxNewsUrl')?.value || '').trim();
                    const d = await api(`/api/atlas/context/${encodeURIComponent(sym)}${url ? `?news_url=${encodeURIComponent(url)}` : ''}`);
                    const bits = [];
                    if (d.positioning?.ok) bits.push(`funding ${Number(d.positioning.funding_pct).toFixed(4)}%`);
                    if (d.positioning?.ok && d.positioning.long_short_ratio) bits.push(`L/S ${d.positioning.long_short_ratio}`);
                    if (d.fear_greed?.ok) bits.push(`F&G ${d.fear_greed.value} ${d.fear_greed.label}`);
                    if (d.news) bits.push(`${d.news.length} headlines`);
                    out.innerHTML = bits.length ? `<span class="wiz-ok">${G_ESC(sym)}: ${G_ESC(bits.join(' · '))}</span>`
                                                : `<span class="wiz-bad">${G_ESC(d.error || 'no data returned')}</span>`;
                } catch (e) { out.innerHTML = `<span class="wiz-bad">${G_ESC(String(e))}</span>`; }
                btn.disabled = false;
            };
        },
        collect: () => {
            const ctx = GUIDE.cfg.context || (GUIDE.cfg.context = {});
            ctx.positioning = !!document.getElementById('wizCtxPositioning')?.checked;
            ctx.fear_greed = !!document.getElementById('wizCtxFear')?.checked;
            ctx.news = !!document.getElementById('wizCtxNews')?.checked;
            ctx.news_url = (document.getElementById('wizCtxNewsUrl')?.value || '').trim();
            ctx.enabled = !!(ctx.positioning || ctx.fear_greed || ctx.news);
        },
    },
    {
        title: 'Ready',
        render: () => {
            const on = (GUIDE.cfg.instruments || []).filter((i) => i.enabled).map((i) => i.symbol);
            const atlas = GUIDE.cfg.atlas || {};
            const tg = GUIDE.cfg.telegram || {};
            const notify = GUIDE.cfg.notify || {};
            const ntfy = notify.ntfy || {};
            const email = notify.email || {};
            const ctx = GUIDE.cfg.context || {};
            const ctxBits = [ctx.positioning !== false && 'funding/OI', ctx.fear_greed !== false && 'Fear & Greed',
                             ctx.news !== false && 'headlines'].filter(Boolean);
            const dt = [];
            if (tg.bot_token && tg.chat_id) dt.push('Telegram');
            if (ntfy.topic) dt.push('ntfy push');
            if (email.host && email.to) dt.push('email');
            if (atlas.webhook_url) dt.push('webhook');
            const no = (v) => `<span class="dim">not set</span> ${v}`;
            return `
            <p>Here is what will be saved:</p>
            <table class="guide-table">
                <tr><td>Data source</td><td>${G_ESC(GUIDE.cfg.data_source)}</td></tr>
                <tr><td>Instruments</td><td>${on.length ? G_ESC(on.join(', ')) : '<span class="wiz-bad">none selected</span>'}</td></tr>
                <tr><td>Deep book + liquidations</td><td>${atlas.extras_enabled !== false ? 'on' : 'off'}</td></tr>
                <tr><td>Persisted history</td><td>${(atlas.history || {}).enabled !== false ? 'on (7 days)' : 'off'}</td></tr>
                <tr><td>Alert channels</td><td>${dt.length ? G_ESC(dt.join(', ')) : 'in-app only' + no(' — add one any time in Settings')}</td></tr>
                <tr><td>Market context</td><td>${ctxBits.length ? G_ESC(ctxBits.join(', ')) : 'off'}</td></tr>
            </table>
            <p style="margin-top:10px">After setup, three places to look: the <b>Systems</b> card on Overview
            shows every ingest path (engine, feed, MT5, NinjaTrader, Alpaca, history database, UI stream,
            alerts) as live / ready / off / error — one glance for “is everything green”. The <b>Market
            Watch</b> panel shows your source’s whole board, and mirrors your MetaTrader 5 terminal’s own
            Market Watch when MT5 is the source. The top bar’s <b>Run</b> menu switches modes (this desktop
            window · headless server on 8099 · CLI pipeline) and carries the optional MT5 and NinjaTrader
            notes plus the dev gates.</p>
            <label class="switch" style="margin-top:10px"><input type="checkbox" id="wizStartNow" ${on.length ? 'checked' : ''}>
                Start the engine as soon as setup finishes</label>
            ${wizFooter({
                unlocks: 'deep book snapshots, liquidations and the persisted history the Replay and Frames panels read — all optional, all local.',
                deeper: 'feeds and history cost disk, not money: 7 days of depth for three instruments is a few hundred MB. Turn them off here and the Depth/Heatmap panels simply show less.',
                view: 'heatmap',
                label: 'See what the depth feed renders',
            })}
            ${wizFooter({
                unlocks: 'context rows (funding, positioning, Fear &amp; Greed, headlines) beside the order flow, so a delta print has a reason attached.',
                deeper: 'context is read-only and cached; the Signals and Overview panels place it next to the tape so you never compare two windows by eye.',
                view: 'overview',
                label: 'Open Overview',
            })}
            <div class="wiz-note">Settings land in your user config file — the program's source is never modified,
            credentials stay on this machine, and you can re-run this assistant from the Guide view at any time.</div>
            <div class="wiz-note"><b>Your first ten minutes.</b>
            <ol style="margin:6px 0 0 18px; padding:0">
                <li><b>Start engine</b> (top bar) — nothing streams until you do; the header chip turns green.</li>
                <li><b>Engine</b> — the footprint matrix, DOM heatmap and sweep bubbles. This is the panel the rest of the app is built around.</li>
                <li><b>Order Flow</b> + <b>CVD</b> together — where price was accepted versus where aggression went.</li>
                <li><b>Depth</b> — the live ladder, so you can watch resting size appear and pull in real time.</li>
                <li>Press <b>P</b> when you want the board frozen while you study it, and <b>?</b> for every shortcut.</li>
            </ol>
            <span class="dim">Panels are grouped by purpose in the ☰ menu (Order flow · Analytics · Trading ·
            Information). Once you have a layout you like, name it in the menu — workspaces go in your config
            file, so they follow this machine.</span></div>
            <div style="margin-top:8px">
                <button class="btn small primary" data-wiz-go="ofx"
                    data-wiz-why="Start the engine in the top bar; this panel is the app's centrepiece.">Finish and open the Engine view</button>
            </div>`;
        },
        collect: () => { /* read at finish */ },
    },
];

/** The wizard's own message line (the Alpaca card has one of its own). */
function wizAlpMsg(text, kind) {
    const el = document.getElementById('wizAlpResult');
    if (el) el.innerHTML = `<span class="${kind === 'err' ? 'wiz-bad' : kind === 'ok' ? 'wiz-ok' : ''}">${G_ESC(text)}</span>`;
}

/** Remember the step so someone who leaves to sign up at Alpaca can resume here. */
async function wizPersistResume() {
    try {
        if (!S.config) return;
        if (((S.config.ui || {}).wizard_resume_step || 0) === GUIDE.step) return;
        const cfg = JSON.parse(JSON.stringify(S.config));
        cfg.ui = cfg.ui || {};
        cfg.ui.wizard_resume_step = GUIDE.step;
        const r = await api('/api/control/config', { method: 'POST', body: cfg });
        S.config = r.config;
    } catch (e) { /* a lost resume point is not worth an error message */ }
}

function openWizard(force) {
    /* Two silent early-returns used to live here, and both present as "the button is dead": the
       flag could be left true with no overlay on screen, and a config that had not arrived yet
       retried forever without saying anything. Recover the first, narrate the second, and mark
       the wizard open only once its overlay actually exists. */
    if (GUIDE.open && document.getElementById('wizOverlay')) return;
    GUIDE.open = false;
    if (!S.config) {
        openWizard.tries = (openWizard.tries || 0) + 1;
        if (openWizard.tries === 1 && typeof toast === 'function') {
            toast(document.body, 'Waiting for the configuration to load…', 'info');
        }
        if (openWizard.tries <= 8) { setTimeout(() => openWizard(force), 400); return; }
        if (typeof toast === 'function') {
            toast(document.body, 'The setup assistant needs the app configuration, which did not load — reload the window (F5).', 'err');
        }
        return;
    }
    openWizard.tries = 0;
    GUIDE.mode = GUIDE.mode || 'express';          // express by default; the pro path is opt-in
    guideStyles();
    GUIDE.cfg = JSON.parse(JSON.stringify(S.config));
    /* What the config looked like when the wizard opened: the finishing write is a whole-config
       POST, so it must be able to tell the keys the user actually edited here from the ones it
       merely held while other views (or another window) moved on. */
    GUIDE.snapshot = JSON.parse(JSON.stringify(GUIDE.cfg));
    GUIDE.cfg.atlas = GUIDE.cfg.atlas || {};
    // resume where a previous run stopped (only if it was left mid-flow)
    const resume = Number(((S.config || {}).ui || {}).wizard_resume_step || 0);
    GUIDE.step = (Number.isFinite(resume) && resume > 0 && resume < wizList().length) ? resume : 0;

    const overlay = document.createElement('div');
    overlay.className = 'wiz-overlay';
    overlay.id = 'wizOverlay';
    overlay.innerHTML = `
        <div class="wiz-card" role="dialog" aria-modal="true" aria-label="Setup assistant" tabindex="-1">
            <div class="wiz-head"><div>
                <div class="wiz-title" id="wizTitle">Setup</div>
                <div class="wiz-sub" id="wizSub"></div>
            </div><div class="grow" style="flex:1"></div>
            <button class="btn small" id="wizClose" title="Close — your place is kept; the assistant resumes at this step">✕</button></div>
            <div class="wiz-body" id="wizBody"></div>
            <div class="wiz-foot">
                <div class="wiz-dots" id="wizDots"></div>
                <button class="btn small" id="wizSkip" title="Skip the assistant — the defaults work out of the box">Skip</button>
                <button class="btn small" id="wizBack" title="Previous step">Back</button>
                <button class="btn primary" id="wizNext" title="Continue to the next step">Next</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);
    GUIDE.open = true;                      // open only once it is really on screen

    overlay.querySelector('#wizClose').onclick = () => {
        closeWizard();
        toast(document.body, 'Setup assistant closed — it resumes at this step next time.', 'info');
    };
    overlay.querySelector('#wizSkip').onclick = () => finishWizard({ skip: true });
    overlay.querySelector('#wizBack').onclick = () => { renderStep(GUIDE.step - 1); };
    overlay.querySelector('#wizNext').onclick = () => {
        if (GUIDE.step >= wizList().length - 1) return finishWizard({});

        /* Guard: advancing past Instruments with nothing enabled would hand the user an empty app.
           The banner offers the one-click fix; a second Next is treated as an informed choice. */
        if ((wizList()[GUIDE.step].title || '').startsWith('Instruments')) {
            const on = ((GUIDE.cfg.instruments) || []).filter((i) => i.enabled);
            const banner = document.getElementById('wizEmptyInst');
            if (!on.length && banner && banner.style.display === 'none') {
                banner.style.display = 'block';
                banner.scrollIntoView({ block: 'nearest' });
                return;
            }
        }
        renderStep(GUIDE.step + 1);
    };
    renderStep(GUIDE.step);
    applyTips(overlay);
}

function renderStep(i) {
    const step = wizList()[i];
    if (!step) return;
    /* Collecting the step being left: it must come from the same list the index belongs to,
       and a depth switch that shortened the list must not leave a dangling index here.
       Reading the express array with a professional index threw 'undefined (reading collect)'
       and closed the wizard. */
    const _leaving = GUIDE.step >= 0 ? wizList()[GUIDE.step] : null;
    if (_leaving && _leaving.collect) _leaving.collect();
    GUIDE.step = i;

    document.getElementById('wizTitle').textContent = step.title;
    document.getElementById('wizSub').textContent = `Step ${i + 1} of ${wizList().length} \u00b7 ${GUIDE.mode === 'pro' ? 'professional' : 'express'}`;
    const body = document.getElementById('wizBody');
    body.innerHTML = step.render();
    if (step.after) step.after();

    /* §123: a visited dot goes back there — the one navigation move a long wizard must have. */
    document.getElementById('wizDots').innerHTML = wizList()
        .map((_, n) => n <= i
            ? `<span class="wiz-dot on" data-wiz-dot="${n}" style="cursor:pointer" title="Step ${n + 1} — click to go back"></span>`
            : `<span class="wiz-dot" title="Step ${n + 1}"></span>`).join('');
    document.getElementById('wizBack').disabled = i === 0;
    document.getElementById('wizNext').textContent = i === wizList().length - 1 ? 'Save & finish' : 'Next';

    /* Depth switch, drawn (not templated) so it always reflects the real mode. */
    let dz = document.querySelector('[data-wiz-depth]');
    if (!dz) {
        dz = document.createElement('span');
        dz.setAttribute('data-wiz-depth', '1');
        dz.style.marginLeft = '10px';
        dz.style.whiteSpace = 'nowrap';
        document.getElementById('wizDots').parentNode.appendChild(dz);
    }
    dz.innerHTML = ['express', 'pro'].map((m) =>
        `<button class="btn small" data-wiz-mode="${m}"${GUIDE.mode === m ? ' style="outline:1px solid #5aa9ff"' : ''}>${m === 'pro' ? 'Professional' : 'Express'}</button>`
    ).join(' ');

    /* Express ends with a door, not a wall: the last express step offers the full path. */
    if (GUIDE.mode !== 'pro' && i === wizList().length - 1) {
        const body = document.getElementById('wizBody');
        if (body && !body.querySelector('[data-wiz-pro]')) {
            const box = document.createElement('div');
            box.className = 'wiz-note';
            box.innerHTML = '<b>Go further:</b> the professional path configures feed budgets, engine '
                + 'internals, analytics thresholds, the studies runtime, layout, hotkeys and bridges, '
                + 'and ends with a checklist that proves each one works.<br>'
                + '<div style="margin-top:6px"><button class="btn small" data-wiz-pro="1">Continue into the professional setup \u2192</button></div>';
            body.appendChild(box);
        }
    }
    applyTips(document.getElementById('wizOverlay'));

    /* renderStep is not nested in openWizard: it must look the overlay up, never close over it.
       A bare `overlay` here was a ReferenceError the moment the wizard tried to draw. */
    const ov = document.getElementById('wizOverlay');
    /* §123: focus rides into the dialog so Esc/Enter/Tab work without a mouse; a step that is
       mid-typing (an input focused) keeps its focus. */
    if (ov) {
        const card = ov.querySelector('.wiz-card');
        const ae = document.activeElement;
        if (card && (!ae || ae === document.body || ov.contains(ae))
            && !/^(INPUT|SELECT|TEXTAREA)$/.test((ae || {}).tagName || '')) {
            card.focus({ preventScroll: true });
        }
    }
    if (ov && !ov.$wizWired) {
        ov.$wizWired = true;                          // wire once per overlay, not per step
        ov.addEventListener('click', (ev) => {
            const dot = ev.target.closest('[data-wiz-dot]');
            if (dot) { renderStep(parseInt(dot.dataset.wizDot, 10)); return; }
            const modeBtn = ev.target.closest('[data-wiz-mode]');
            if (modeBtn) {
                GUIDE.mode = modeBtn.dataset.wizMode === 'pro' ? 'pro' : 'express';
                if (wizList()[GUIDE.step] && wizList()[GUIDE.step].collect) wizList()[GUIDE.step].collect();
                if (GUIDE.step > wizList().length - 1) GUIDE.step = wizList().length - 1;
                renderStep(GUIDE.step);
                return;
            }
            const wsBtn = ev.target.closest('[data-wiz-save-ws]');
            if (wsBtn) {
                const name = wsBtn.dataset.wizSaveWs || 'research';
                wsBtn.disabled = true;
                api('/api/control/workspaces', { method: 'POST', body: { action: 'save', name: name } })
                    .then(() => { wsBtn.textContent = 'Saved workspace "' + name + '"'; })
                    .catch(() => { wsBtn.disabled = false; wsBtn.textContent = 'Could not save — open Workspaces in the menu'; });
                return;
            }
            if (ev.target.closest('[data-wiz-pro]')) {
                GUIDE.mode = 'pro';
                if (wizList()[GUIDE.step] && wizList()[GUIDE.step].collect) wizList()[GUIDE.step].collect();
                GUIDE.step = Math.min(WIZ_STEPS.length, wizList().length - 1);   // first pro-only step
                renderStep(GUIDE.step);
                return;
            }
            const go = ev.target.closest('[data-wiz-go]');
            if (go) { wizGo(go.dataset.wizGo, go.dataset.wizWhy); return; }
            if (ev.target.id === 'wizEmptyInstFix') {
                GUIDE.cfg.instruments = (GUIDE.cfg.instruments || []).map((i) => ({ ...i, enabled: true }));
                document.querySelectorAll('[data-wiz-inst]').forEach((box) => { box.checked = true; });
                const b = document.getElementById('wizEmptyInst');
                if (b) b.style.display = 'none';
                return;
            }
            if (ev.target.id === 'wizEmptyInstSkip') {
                const b = document.getElementById('wizEmptyInst');
                if (b) b.style.display = 'none';
                renderStep(GUIDE.step + 1);           // informed skip
            }
        });
    }
}

function closeWizard() {
    const overlay = document.getElementById('wizOverlay');
    if (overlay) overlay.remove();
    GUIDE.open = false;
    // leaving mid-flow (✕) keeps the place; finishing clears it
    wizPersistResume();
}

async function finishWizard({ skip }) {
    const _final = wizList()[GUIDE.step];
    if (!skip && _final && _final.collect) _final.collect();
    const startNow = !skip && !!document.getElementById('wizStartNow')?.checked;

    /* Re-read before writing, and merge three ways. This function posts the WHOLE config, so a copy
       taken when the wizard opened would silently revert anything changed elsewhere since — measured:
       a Skip click flipped context.news back to false after it had been changed by something else.
       Keys the wizard actually changed (vs its opening snapshot) win; every other key takes the value
       the server holds right now. If the re-read fails, the old behaviour stands. */
    try {
        const live = await api('/api/control/config');
        const server = (live && (live.config || live)) || null;
        const snap = GUIDE.snapshot || {};
        if (server && typeof server === 'object' && GUIDE.cfg) {
            const merged = Object.assign({}, server);
            Object.keys(GUIDE.cfg).forEach((key) => {
                const changed = JSON.stringify(GUIDE.cfg[key]) !== JSON.stringify(snap[key]);
                if (changed) merged[key] = GUIDE.cfg[key];
            });
            GUIDE.cfg = merged;
        }
    } catch (e) { /* offline: write what we hold, as before */ }

    closeWizard();

    if (skip) {
        GUIDE.cfg.onboarding_done = true;
        GUIDE.cfg.ui = GUIDE.cfg.ui || {};
        GUIDE.cfg.ui.wizard_resume_step = 0;
        try { await api('/api/control/config', { method: 'POST', body: GUIDE.cfg }); } catch (e) { /* ignore */ }
        toast($('#ovBanner') || $('#guideBody'), 'Setup assistant skipped — the defaults are ready; press Start engine when you are.', 'info');
        return;
    }

    GUIDE.cfg.onboarding_done = true;
    GUIDE.cfg.ui = GUIDE.cfg.ui || {};
    GUIDE.cfg.ui.wizard_resume_step = 0;          // done — start at the top next time
    try {
        const r = await api('/api/control/config', { method: 'POST', body: GUIDE.cfg });
        S.config = r.config;
        toast($('#guideBody') || document.body, `Settings saved to ${r.config_path}`, 'ok');
    } catch (e) {
        toast($('#guideBody') || document.body, `Save failed: ${e}`, 'err');
        return;
    }
    if (startNow) {
        try {
            const cfg = await api('/api/control/bootstrap');
            S.config = cfg.config; S.status = cfg.status;
            // a running engine must restart to pick up new instruments/thresholds
            const running = !!(cfg.status && cfg.status.running);
            const r = running
                ? await api('/api/control/engine/restart', { method: 'POST', body: S.config })
                : await api('/api/control/engine/start', { method: 'POST', body: S.config });
            if (r.ok) toast($('#ovBanner') || document.body,
                `Engine ${running ? 'restarted' : 'running'}: ${(r.symbols || []).join(', ')} — give the heatmap ~a minute to build up.`, 'ok');
        } catch (e) {
            toast($('#ovBanner') || document.body, `Engine start failed: ${e}`, 'err');
        }
    }

    /* Channel set-up only counts if the rules actually route to it.
       Two rules learned the hard way here:
         * push channels (telegram / ntfy / webhook) can join every rule that already
           alerts externally — that is what they are for;
         * EMAIL must never be blanket-applied. It was, once, and six rules then mailed
           every big trade, sweep, stop run and imbalance: a busy tape means dozens of
           messages an hour. Email now goes only where the user explicitly asks, and
           only on the quiet, high-signal kinds (blocks and stop runs).
    */
    try {
        const tg = GUIDE.cfg.telegram || {};
        const notify = GUIDE.cfg.notify || {};
        const atlas = GUIDE.cfg.atlas || {};
        const external = [];
        if (tg.bot_token && tg.chat_id) external.push('telegram');
        if ((notify.ntfy || {}).topic) external.push('ntfy');
        if (atlas.webhook_url) external.push('webhook');
        const emailReady = !!((notify.email || {}).host && (notify.email || {}).to);
        const emailWanted = emailReady && !!document.getElementById('wizEmailRoute')?.checked;
        const quietKinds = ['block_trade', 'stop_run'];
        if (external.length || emailWanted) {
            const rules = (await api('/api/atlas/alert-rules')).rules || [];
            let changed = 0;
            let emailed = 0;
            for (const r of rules) {
                const current = r.channels || ['ui'];
                const alreadyExternal = current.some((c) => c !== 'ui');
                const emailHere = emailWanted && quietKinds.includes(r.kind)
                    && (alreadyExternal || current.includes('ntfy') || current.length > 1);
                if (!alreadyExternal && !emailHere) continue;
                const next = [...new Set(['ui', ...(alreadyExternal ? external : []),
                                          ...(emailHere ? ['email'] : [])])];
                if (next.sort().join() === [...current].sort().join()) continue;
                await api('/api/atlas/alert-rules', {
                    method: 'POST',
                    body: { id: r.id, name: r.name, kind: r.kind, params: r.params,
                            enabled: r.enabled, cooldown_s: r.cooldown_s, channels: next },
                });
                changed += 1;
                if (next.includes('email')) emailed += 1;
            }
            if (changed) {
                const what = [...external, ...(emailed ? ['email'] : [])].join(', ');
                toast($('#ovBanner') || document.body,
                    `${changed} alert rule${changed === 1 ? '' : 's'} routed to ${what}` +
                    `${emailed ? ' (email only on ' + quietKinds.join(' + ') + ')' : ''} — tune per rule in the Alerts view.`, 'ok');
            } else if (emailReady && !emailWanted) {
                toast($('#ovBanner') || document.body,
                    'Email stays unrouted — a busy tape would mail every few seconds. Tick it per rule in the Alerts view, or re-run setup with the email option.', 'info');
            }
        }
    } catch (e) {
        toast($('#ovBanner') || document.body, `Rule routing not applied: ${e}`, 'warn');
    }

    if (typeof window.renderSettings === 'function') window.renderSettings();
    if (typeof window.refreshInstruments === 'function') window.refreshInstruments();
}

/* ══════════════════════════════════════════════════════════════════
   Boot: build the view, apply tips, offer setup on a fresh install
   ══════════════════════════════════════════════════════════════════ */

/* §123: the industry keyboard grammar for every overlay this layer owns. Esc dismisses through
   the overlay's OWN close control (so a wizard close still keeps its place), Enter advances a
   wizard step when the dialog itself holds focus, and Tab stays inside the dialog. One listener,
   and only the top-most overlay answers — a notice stacked over the wizard owns the keys. */
function overlayKeys(ev) {
    const overlays = document.querySelectorAll('.wiz-overlay');
    if (!overlays.length) return;
    const ov = overlays[overlays.length - 1];
    if (ev.key === 'Escape') {
        const closer = ov.querySelector('#wizClose, #helpClose, #mt5NoticeClose');
        if (!closer) return;
        ev.preventDefault();
        closer.click();
        return;
    }
    if (ev.key === 'Enter') {
        if (ov.id !== 'wizOverlay') return;
        const tag = (document.activeElement || {}).tagName || '';
        if (/^(INPUT|SELECT|TEXTAREA|BUTTON|A)$/.test(tag)) return;   // native behaviour owns those
        ev.preventDefault();
        const next = document.getElementById('wizNext');
        if (next && !next.disabled) next.click();
        return;
    }
    if (ev.key === 'Tab') {
        const f = Array.prototype.filter.call(
            ov.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'),
            (el) => el.offsetParent !== null || el === document.activeElement);
        if (!f.length) return;
        const first = f[0];
        const last = f[f.length - 1];
        if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
    }
}

function guideBoot() {
    document.addEventListener('keydown', overlayKeys);   // §123: one listener, every overlay
    buildGuideView();
    guideStyles();
    applyTips(document);
    watchDom();

    // keep tips flowing when the user navigates
    if (typeof window.showView === 'function' && !window.showView.__guideWrapped) {
        const base = window.showView;
        const wrapped = function (name) {
            const out = base.apply(this, arguments);
            setTimeout(() => applyTips(document), 60);
            return out;
        };
        wrapped.__guideWrapped = true;
        window.showView = wrapped;
    }

    // first run? offer the assistant once the bootstrap data is in
    let tries = 0;
    const wait = setInterval(() => {
        tries++;
        if (S.config || tries > 40) {
            clearInterval(wait);
            if (S.config && !S.config.onboarding_done) setTimeout(() => openWizard(true), 600);
        }
    }, 250);

    window.GUIDE = GUIDE;
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', guideBoot);
else guideBoot();

/* ══════════════════════════════════════════════════════════════════
   6. Setup how-tos — every optional add-on explained, with real steps

   The brief for this section: the data-source step offers MetaTrader 5, so the install
   should SAY the option exists, and anyone who wants it should get a
   step-by-step walkthrough — the same for every other add-on the assistant
   names (instruments, feeds, phone alerts, email, webhook, market context).

   Everything here is additive: it wraps the wizard steps that already exist
   rather than rewriting them, and reuses the wizard's overlay styling.
   ══════════════════════════════════════════════════════════════════ */

function helpStyles() {
    if (document.getElementById('helpStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'helpStyleSheet';
    st.textContent = `
        .help-card { max-width: 780px; }
        .help-lead { color: var(--fg); margin: 0 0 10px; }
        .help-needs { background: rgba(255,255,255,0.04); border: 1px solid var(--line);
                      border-radius: 6px; padding: 8px 10px; margin: 0 0 12px; font-size: 12px; }
        .help-needs b { color: var(--fg); }
        .help-step { display: flex; gap: 10px; margin: 0 0 12px; }
        .help-num { flex: 0 0 22px; height: 22px; border-radius: 50%; background: rgba(90,180,255,0.16);
                    border: 1px solid rgba(90,180,255,0.45); color: var(--fg); font-size: 12px;
                    display: flex; align-items: center; justify-content: center; }
        .help-txt { flex: 1; min-width: 0; }
        .help-txt .t { font-weight: 600; }
        .help-txt .d { color: var(--dim); font-size: 12px; margin-top: 3px; }
        .help-cmd { display: flex; gap: 6px; align-items: center; margin-top: 6px; }
        .help-cmd code { flex: 1; background: #0b0f14; border: 1px solid var(--line); border-radius: 4px;
                         padding: 5px 8px; font-size: 12px; overflow-x: auto; white-space: nowrap; }
        .help-note { border-left: 3px solid rgba(255,190,90,0.6); padding: 6px 10px; margin: 10px 0 0;
                     color: var(--dim); font-size: 12px; background: rgba(255,190,90,0.05); }
        .help-test { border: 1px solid var(--line); border-radius: 6px; padding: 10px; margin-top: 12px; }
        .help-test .r { font-size: 12px; margin-top: 6px; }
        .help-topic { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0;
                      border-bottom: 1px solid var(--line); }
        .help-topic:last-child { border-bottom: 0; }
        .help-topic .grow { flex: 1; }
        .help-topic b { display: block; }
        .help-topic .dim { font-size: 12px; }
        .notice-card { max-width: 620px; }
    `;
    document.head.appendChild(st);
}

/* ── the topics ─────────────────────────────────────────────────── */
/* §123: where each inline walkthrough continues. Exact Centre topic ids where one exists, else
   a query that lands on the right topics — the card's door (and openTopic's own fallback) run it. */
const CENTRE_QUERY = {
    mt5: 'MetaTrader 5', ninjatrader: 'NinjaTrader', alpaca: 'Alpaca', telegram: 'Telegram',
    ntfy: 'ntfy', email: 'email alerts', webhook: 'webhook', extras: 'deep book liquidations',
    context: 'market context', instruments: 'instruments',
    /* the view modules extend HELP_TOPICS at runtime — their cards get the door too */
    studies: 'studies library', platforms: 'platforms', ofx: 'the engine view',
};

const HELP_TOPICS = {
    mt5: {
        title: 'MetaTrader 5 data source',
        lead: 'MetaTrader 5 is this program\u2019s second data source. The exchange feed covers crypto '
            + 'perpetuals; an MT5 terminal covers what a crypto venue cannot — indices (NAS100, US500, DAX), '
            + 'gold and silver, FX, commodity CFDs, and equity CFDs — using the exact instrument names your '
            + 'broker publishes.',
        needs: ['<b>Windows</b> (the MetaTrader5 Python package ships Windows wheels only)',
                'an <b>MT5 account</b> with any broker — demo accounts work',
                'the <b>terminal installed</b> and <b>left running</b>'],
        steps: [
            { t: 'Install the terminal from your broker', d: 'Not from this app. Every MT5 broker ships its own '
                + 'branded terminal (IC Markets, Pepperstone, FTMO, Vantage\u2026) and each publishes its own '
                + 'symbol names. Keep the installer\u2019s default location in mind — you may need it in step 4.' },
            { t: 'Log in and leave it running', d: 'Open the terminal and sign in (File \u2192 Login to Trade '
                + 'Account). The Python bridge talks to the <i>running</i> terminal, so a closed terminal means no '
                + 'data. Demo and live accounts behave identically here.' },
            { t: 'Install the Python bridge (source installs)', d: 'The portable Windows build already '
                + 'includes the bridge \u2014 nothing to install there; go to the test below. In a '
                + 'source install, run this from the program folder \u2014 pick the line that matches '
                + 'how this environment was built (the test below prints the right one for this '
                + 'machine).',
              cmds: ['.venv\\Scripts\\python.exe -m pip install MetaTrader5',
                     'uv pip install --python .venv\\Scripts\\python.exe MetaTrader5'] },
            { t: 'Terminal path — only if it is not found automatically', d: 'Leave blank and the bridge looks '
                + 'in the usual places. If your broker installs somewhere unusual, paste the executable path, e.g. '
                + 'C:\\Program Files\\MetaTrader 5\\terminal64.exe (broker-specific).' },
            { t: 'Login and server — only for a specific account', d: 'Leave both blank to use whatever account '
                + 'the running terminal is signed in to. Fill them only when you want the bridge to sign in itself '
                + '(found in the terminal under Tools \u2192 Options \u2192 Server).' },
            { t: 'Map the symbols', d: 'The app knows an instrument by its own name (NAS100USDT, XAUUSDT); each '
                + 'broker calls the same market something else (USTEC / US100 / NAS100\u2026, XAUUSD / GOLD\u2026). '
                + 'The table below maps one to the other — the app ships sensible defaults and you can correct '
                + 'them per instrument.' },
            { t: 'Test the bridge', d: 'The button below connects with these exact settings, reports the terminal, '
                + 'the account and which of your mapped symbols the broker actually lists, then disconnects again. '
                + 'Nothing is saved until you finish the assistant.' },
        ],
        note: 'Honest limits: MT5 data comes from your broker\u2019s terminal, so quality and depth are '
            + 'broker-dependent — some publish a full DOM, some publish almost none. The order-book views '
            + '(heatmap, participants\u2019 intent) are at their best on the exchange feed; MT5 is how you get the '
            + 'instruments the exchange does not list. Historical ticks download from the broker on first use, '
            + 'which can take a moment.',
        test: 'mt5',
    },
    ninjatrader: {
        title: 'NinjaTrader 8 data source',
        lead: 'NinjaTrader is a futures platform with its own data feeds. This program reads it through a '
            + 'small read-only bridge add-on that ships with the app \u2014 install it once and the '
            + 'terminal\u2019s own instruments (NQ, ES, MNQ\u2026) stream into every panel like any other '
            + 'venue. The platform is free; demo accounts work.',
        needs: ['<b>Windows</b>',
                'NinjaTrader Desktop installed (free) \u2014 and its account, the login it asks for on every start',
                'the <b>bridge add-on</b>, installed once (one copy, one platform option, one restart)'],
        steps: [
            { t: 'Install NinjaTrader and log in', d: 'Download it from ninjatrader.com \u2014 installing and '
                + 'using it in simulation is free. Version 8.1+ presents a log-in window on every start and '
                + 'exits if it is closed, so create the free account first; it is the login.' },
            { t: 'Get data flowing in the platform', d: 'The <b>Simulated Data Feed</b> streams synthetic but '
                + 'complete quotes, trades and depth \u2014 ideal to verify this whole path. A funded '
                + 'NinjaTrader brokerage account adds complimentary real-time CME/EUREX Level I while funded; '
                + 'Kinetick End-Of-Day is free.' },
            { t: 'Install the bridge add-on (once)', d: 'Open the bridge folder (Platforms \u25b8 NinjaTrader '
                + '\u25b8 Show the DLL folder); it holds the bridge source and the compiled '
                + 'ModFlowBridge.dll. Copy the .cs files (ModFlowBridge.cs, ModFlowJson.cs, '
                + 'ModFlowProbe.cs) into Documents\\NinjaTrader 8\\bin\\Custom\\AddOns '
                + 'then press <i>F5</i> in NinjaTrader\u2019s own NinjaScript Editor (New \u2192 '
                + 'NinjaScript Editor) and answer the trust prompt. The platform\u2019s Log tab '
                + 'then shows the bridge listening on 127.0.0.1:8790.' },
            { t: 'Test the bridge', d: 'The button below connects to the bridge inside NinjaTrader, subscribes '
                + 'to one instrument and reports the NinjaTrader build, the live connection and what actually '
                + 'streamed \u2014 quotes, trades, and level-2 depth if your feed carries it. Nothing is saved '
                + 'by the test.' },
            { t: 'Add instruments from the terminal\u2019s own list', d: 'Type NQ (or NQ1, or a full name like '
                + 'MNQ 12-26) in the Instruments panel\u2019s look-up: it offers the front-month contract the '
                + 'terminal itself would use, stamped with the terminal\u2019s name so the engine streams it '
                + 'like any other venue.' },
            { t: 'Pick NinjaTrader as the data source', d: 'In the setup assistant\u2019s Data source step (or '
                + '\u2630 \u25b8 sources). Every panel then reads your terminal: tape, footprint, delta, '
                + 'profiles, the ladder \u2014 all from the same engines as the built-in feeds.' },
        ],
        note: 'Honest limits: level-2 depth arrives only when your data subscription carries it \u2014 the '
            + 'bridge card reports what actually arrived instead of promising a ladder. Order Flow+ ($59/mo '
            + 'standalone, complimentary while funded, included with Lifetime) changes NinjaTrader\u2019s own '
            + 'charts; this suite computes its own footprint/delta from the raw trades and depth the bridge '
            + 'republishes and does not need it. The bridge is read-only and loopback-only.',
        test: 'ninjatrader',
    },
    alpaca: {
        title: 'Alpaca Markets — linking your account',
        lead: 'Alpaca is a US brokerage with an API. A paper-trading account is free, needs only an email '
            + 'address, and behaves exactly like a live one — same API, virtual money, resettable.',
        needs: ['an email address (paper account) — or an approved live account for real money',
                'nothing else: no funding, no card, for paper'],
        steps: [
            { t: 'Create the account', d: 'Sign up at app.alpaca.markets. Choose the <b>paper</b> account for '
                + 'simulation; it is created instantly and needs no identity documents.' },
            { t: 'Open the API keys page', d: 'In the dashboard switch to the environment you want (paper or live)—'
                + 'the key page belongs to the environment you are in — then generate a key pair.' },
            { t: 'Copy both values', d: 'The <b>key ID</b> (starts with PK for paper) and the <b>secret</b>. The '
                + 'secret is shown once; if you lose it, generate a new pair.' },
            { t: 'Paste them into Settings → Broker account', d: 'Pick the matching environment in the dropdown. '
                + 'Paper keys only work against the paper host and live keys only against the live host — the wrong '
                + 'pair is the single most common error, and the app says so when it happens.' },
            { t: 'Press Validate', d: 'The app asks Alpaca to confirm the keys, then reports the account and exactly '
                + 'what it can reach: real-time tape, delayed full-market history, news, calendar, options, positions '
                + 'and portfolio history.' },
            { t: 'Know where the keys live', d: 'They are stored in this program’s local config file on your machine, '
                + 'never displayed back, and are sent only to Alpaca. “Remove keys” wipes them.' },
        ],
        note: 'Alpaca publishes trades, quotes and bars — no order book. That is why the heatmap, DOM ladder and '
            + 'participants’-intent reader stay on the exchange feed and the optional MT5 terminal: they need depth, '
            + 'which Alpaca does not publish. Free-plan real-time US data is the IEX venue only; full-market SIP data '
            + 'is available but delayed by 15 minutes, and the app labels which feed a panel is showing.',
    },
    telegram: {
        title: 'Telegram alerts',
        lead: 'A free bot that messages you when a rule fires. Takes about two minutes and needs no card.',
        needs: ['a phone with Telegram', 'nothing else — bots are free'],
        steps: [
            { t: 'Create the bot', d: 'Open Telegram, message <b>@BotFather</b>, send /newbot, pick a name and a '
                + 'username ending in "bot". BotFather answers with an HTTP API token — that goes in the '
                + '\u201cbot token\u201d field.' },
            { t: 'Get the chat id', d: 'Send your new bot any message first (it cannot start a conversation). '
                + 'Then message <b>@userinfobot</b> and copy the numeric id it gives you into the \u201cchat id\u201d '
                + 'field.' },
            { t: 'Test it', d: 'Press Test next to the fields: the app sends a real message through Telegram. '
                + 'If it arrives, tick the channel on the alert rules you want pushed.' },
        ],
        note: 'The token and chat id are credentials: they live in your local config file and are sent only to '
            + 'Telegram. Never paste them anywhere else.',
    },
    ntfy: {
        title: 'Phone push (ntfy)',
        lead: 'Push notifications with no account at all — you choose a topic name and subscribe to it.',
        needs: ['the free ntfy app (iOS, Android, desktop) or the web page'],
        steps: [
            { t: 'Pick a private topic name', d: 'Anything long and unguessable, e.g. ofp-9f3k7-tape. Anyone who '
                + 'knows the name can read it, so treat it as a secret.' },
            { t: 'Subscribe in the app', d: 'Open ntfy, press +, paste the same topic name. On ntfy.sh leave the '
                + 'server as-is unless you self-host.' },
            { t: 'Paste it here and Test', d: 'The Test button sends a real push; you should see it on the phone '
                + 'within a second or two.' },
        ],
        note: 'The public server rate-limits bursts (HTTP 429). This program backs its own throttle off when that '
            + 'happens and tells you in the channel stats, so a busy tape cannot silently stop your alerts.',
    },
    email: {
        title: 'Email alerts',
        lead: 'Useful for a daily digest or when a rule must leave a paper trail.',
        needs: ['a mailbox that allows SMTP', 'an app password (never your main password)'],
        steps: [
            { t: 'Turn on SMTP in your provider', d: 'Most providers (Zoho, Fastmail, Gmail, or your host’s own SMTP) let you send '
                + 'via SMTP with a per-app password. Gmail needs 2-step verification first, then an App Password.' },
            { t: 'Enter host, port and user', d: '587 with STARTTLS is the common pairing; 465 uses SSL instead. '
                + 'The username is usually the full email address.' },
            { t: 'Recipient', d: 'Where the alerts go — usually your own address, or a filtered folder.' },
            { t: 'Test', d: 'Sends one real message. Because a busy market can fire alerts every few seconds, '
                + 'email is deliberately left unticked on the rules by default — opt in per rule.' },
        ],
        note: 'The password is stored in your local config file only — the file the suite keeps on this machine. '
            + 'It leaves the machine only in the login to your own mail server.',
    },
    webhook: {
        title: 'Webhook (Slack, Discord, your own script)',
        lead: 'POSTs a JSON payload when a rule fires — the hook for anything the built-in channels do not cover.',
        needs: ['an endpoint that accepts a JSON POST'],
        steps: [
            { t: 'Get an incoming-webhook URL', d: 'Slack: App directory \u2192 Incoming Webhooks. Discord: '
                + 'Channel settings \u2192 Integrations \u2192 Webhooks. Or point it at your own small server.' },
            { t: 'Paste the URL and Test', d: 'The test posts a sample payload with the same shape the rules use.' },
            { t: 'Route rules to it', d: 'Tick \u201cwebhook\u201d on the rules you want forwarded.' },
        ],
    },
    extras: {
        title: 'Deep book, liquidations and history',
        lead: 'Three extras that come from the same public venue feed — no account involved.',
        needs: [],
        steps: [
            { t: 'Deep order book', d: 'The exchange\u2019s 200-level book. It is what makes the heatmap work: '
                + 'walls, stacked orders, size that appears (stack) or vanishes (pull), and the participants\u2019 '
                + 'intent pressure reading. With it off, those views have less to chew on — everything else still runs.' },
            { t: 'Liquidations', d: 'Forced closes published by the venue. They mark where leveraged positions '
                + 'gave way, which is often where a move accelerates. Low rate, high signal.' },
            { t: 'Persist detections to disk', d: 'Writes the detections (not the raw ticks) to a local SQLite '
                + 'file, seven days, pruned automatically, so the Alerts view and history survive a restart. '
                + 'Turn it off and the app keeps everything in memory only.' },
        ],
        note: 'Turning the extras off does not break anything — it makes the app lighter and the book-based '
            + 'reads unavailable.',
    },
    context: {
        title: 'Market context panel',
        lead: 'Free, public, keyless: what the wider market is positioned for while you read the tape.',
        needs: [],
        steps: [
            { t: 'Funding, open interest, long/short ratio', d: 'From the exchange itself. Funding is what '
                + 'leveraged traders pay to hold; rising open interest means participation is growing; the '
                + 'long/short account ratio shows which side is crowded.' },
            { t: 'Fear & Greed', d: 'alternative.me\u2019s daily index (0\u2013100). A sentiment gauge, not a '
                + 'signal — useful mostly at the extremes.' },
            { t: 'Headlines', d: 'Public RSS from CoinDesk, Cointelegraph and Decrypt. Paste any RSS/Atom URL to '
                + 'replace them with a feed you trust more.' },
        ],
        note: 'All three fail soft: if the network is down the card says \u201cunavailable\u201d and nothing else '
            + 'is affected.',
    },
    instruments: {
        title: 'Instruments',
        lead: 'What the engine streams. Eighteen crypto majors ship enabled-ready; the assistant can import the '
            + 'venue\u2019s own list (with the venue\u2019s tick sizes) in one click.',
        needs: ['for crypto: nothing', 'for MT5 instruments: a terminal and a symbol mapping'],
        steps: [
            { t: '\u201cAdd venue instruments\u201d', d: 'Asks the exchange which perpetuals exist and imports '
                + 'them with their real tick sizes. Then tick the ones you want and finish — the engine restarts '
                + 'itself so they start streaming immediately.' },
            { t: 'Tick size matters', d: 'Every analytics module works in price ticks. Importing the venue\u2019s '
                + 'own tick size is why imported instruments behave correctly where a guessed one would not.' },
            { t: 'MT5 symbols', d: 'An MT5 instrument also needs your broker\u2019s name for it — set that in the '
                + 'MT5 step or later in Settings. The Instruments view shows the mapping the engine is using.' },
        ],
    },
};

/* ── the how-to modal ───────────────────────────────────────────── */
function openHelp(id) {
    const topic = HELP_TOPICS[id];
    if (!topic) return;
    helpStyles();
    const prev = document.getElementById('helpOverlay');
    if (prev) prev.remove();

    const overlay = document.createElement('div');
    overlay.className = 'wiz-overlay';
    overlay.id = 'helpOverlay';
    const steps = (topic.steps || []).map((s, i) => `
        <div class="help-step">
            <div class="help-num">${i + 1}</div>
            <div class="help-txt"><div class="t">${s.t}</div><div class="d">${s.d}</div>
                ${(s.cmds || (s.cmd ? [s.cmd] : [])).map((c) => `<div class="help-cmd">
                    <code>${G_ESC(c)}</code>
                    <button class="btn small help-copy" data-copy="${G_ESC(c)}"
                        title="Copy this line to the clipboard">Copy</button></div>`).join('')}
            </div>
        </div>`).join('');

    overlay.innerHTML = `
        <div class="wiz-card help-card" role="dialog" aria-modal="true" aria-label="${G_ESC(topic.title)}">
            <div class="wiz-head"><div>
                <div class="wiz-title">${topic.title}</div>
                <div class="wiz-sub">step by step — nothing here is required to use the program</div>
            </div><div style="flex:1"></div>
            <button class="btn small" id="helpClose" title="Close this walkthrough">\u2715</button></div>
            <div class="wiz-body">
                <p class="help-lead">${topic.lead}</p>
                ${(topic.needs && topic.needs.length) ? `<div class="help-needs"><b>You will need:</b>
                    <ul style="margin:6px 0 0 16px">${topic.needs.map((n) => `<li>${n}</li>`).join('')}</ul></div>` : ''}
                ${steps}
                ${topic.note ? `<div class="help-note">${topic.note}</div>` : ''}
                ${topic.test === 'mt5' ? mt5TestPanel() : topic.test === 'ninjatrader' ? ninjatraderTestPanel() : ''}
                <div class="wiz-note" style="margin-top:12px">
                    <button class="btn small" id="helpToCentre"
                        title="Search every topic, walkthrough and screenshot in the Help Centre">Open in the Help Centre →</button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#helpClose').onclick = () => overlay.remove();
    const toCentre = overlay.querySelector('#helpToCentre');
    if (toCentre) toCentre.onclick = () => {
        overlay.remove();
        if (window.OFAPHELP) OFAPHELP.open(CENTRE_QUERY[id] || id);
        else toast(document.body, 'The Help Centre is not loaded in this build.', 'info');
    };
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    overlay.querySelectorAll('.help-copy').forEach((b) => {
        b.onclick = () => copyText(b.dataset.copy || '', b);
    });
    if (topic.test === 'mt5') wireMt5TestPanel(overlay);
    if (topic.test === 'ninjatrader') wireNinjatraderTestPanel(overlay);
}

function copyText(text, btn) {
    const done = (ok) => {
        const old = btn.textContent;
        btn.textContent = ok ? 'Copied' : 'Select it manually';
        setTimeout(() => { btn.textContent = old; }, 1600);
    };
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => done(true), () => done(false));
            return;
        }
    } catch (e) { /* fall through */ }
    done(false);
}

/* ── the live MT5 bridge test (used by the walkthrough and the wizard) ── */
function mt5TestPanel() {
    const mt5 = (GUIDE.cfg && GUIDE.cfg.mt5) || (S.config && S.config.mt5) || {};
    return `
        <div class="help-test" id="mt5TestPanel">
            <div style="font-weight:600;margin-bottom:6px">Test the bridge now</div>
            <div class="row" style="gap:8px;flex-wrap:wrap">
                <input type="text" id="mt5Path" style="flex:2;min-width:240px" placeholder="terminal path (optional)"
                    value="${G_ESC(mt5.path || '')}" title="Only needed if the terminal is installed somewhere unusual.">
                <input type="text" id="mt5Login" style="flex:1;min-width:120px" placeholder="login (optional)"
                    value="${G_ESC(mt5.login || '')}" title="Leave empty to use whatever account the running terminal is signed in to.">
            </div>
            <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:6px">
                <input type="text" id="mt5Server" style="flex:1;min-width:160px" placeholder="server (optional)"
                    value="${G_ESC(mt5.server || '')}" title="Broker server name — only needed with a login.">
                <input type="password" id="mt5Password" style="flex:1;min-width:140px" placeholder="password (optional)"
                    title="Stored in your local config file only, never displayed back.">
                <button class="btn primary" id="mt5TestBtn"
                    title="Connect with these settings, report the terminal, account and mapped symbols, then disconnect">Test the bridge</button>
            </div>
            <div class="r dim" id="mt5TestResult">Checks in order: Windows \u2192 Python bridge \u2192 running terminal \u2192 your instruments.</div>
        </div>`;
}

function wireMt5TestPanel(root) {
    const btn = root.querySelector('#mt5TestBtn');
    if (!btn) return;
    btn.onclick = async () => {
        const out = root.querySelector('#mt5TestResult');
        const payload = {
            path: (root.querySelector('#mt5Path') || {}).value || '',
            login: (root.querySelector('#mt5Login') || {}).value || '',
            server: (root.querySelector('#mt5Server') || {}).value || '',
            password: (root.querySelector('#mt5Password') || {}).value || '',
            symbols: ((S.config && S.config.instruments) || [])
                .filter((i) => i.enabled).map((i) => i.mt5_symbol).filter(Boolean),
        };
        btn.disabled = true;
        out.innerHTML = 'connecting\u2026';
        try {
            const r = await api('/api/control/mt5/test', { method: 'POST', body: payload });
            out.innerHTML = mt5TestMessage(r);
        } catch (e) {
            out.innerHTML = `<span class="wiz-bad">request failed: ${G_ESC(String(e))}</span>`;
        }
        btn.disabled = false;
    };
}

function mt5TestMessage(r) {
    if (r && r.ok) {
        const term = r.terminal || {}, acct = r.account || {};
        const syms = Object.entries(r.symbols || {}).map(([k, v]) =>
            `${k} ${v ? '<span class="wiz-ok">listed</span>' : '<span class="wiz-bad">not found at this broker</span>'}`);
        return `<span class="wiz-ok">Connected.</span> terminal ${G_ESC(term.name || '?')}`
            + `${term.build ? ' (build ' + term.build + ')' : ''} \u00b7 ${G_ESC(term.company || '')}`
            + (acct.login ? ` \u00b7 account ${acct.login} on ${G_ESC(acct.server || '')} (${G_ESC(acct.currency || '')})` : ' \u00b7 no account signed in \u2014 the terminal is still usable')
            + (syms.length ? `<br>your instruments: ${syms.join(' \u00b7 ')}` : '')
            + '<br>Nothing was saved by this test \u2014 finishing the assistant writes the settings.';
    }
    const stage = (r && r.stage) || 'unknown';
    const msg = (r && r.message) || 'no detail returned';
    const cmd = (r && r.command) ? `<div class="help-cmd"><code>${G_ESC(r.command)}</code>
        <button class="btn small help-copy" data-copy="${G_ESC(r.command)}">Copy</button></div>` : '';
    return `<span class="wiz-bad">Stopped at: ${G_ESC(stage)}.</span> ${G_ESC(msg)}${cmd}`;
}

/* ── the live NinjaTrader bridge test (used by the walkthrough and the wizard) ── */
function ninjatraderTestPanel() {
    const nt = ((GUIDE.cfg && GUIDE.cfg.platforms && GUIDE.cfg.platforms.ninjatrader)
        || (S.config && S.config.platforms && S.config.platforms.ninjatrader) || {});
    return `
        <div class="help-test" id="ntTestPanel">
            <div style="font-weight:600;margin-bottom:6px">Test the bridge now</div>
            <div class="row" style="gap:8px;flex-wrap:wrap">
                <input type="text" id="ntHost" style="flex:1;min-width:130px" placeholder="host"
                    value="${G_ESC(nt.host || '127.0.0.1')}" title="The bridge binds loopback only; leave 127.0.0.1.">
                <input type="text" id="ntPort" style="flex:0 0 84px" placeholder="port"
                    value="${G_ESC(String(nt.port || 8790))}" title="The bridge's port \u2014 8790 unless the bridge was rebuilt with another.">
                <input type="text" id="ntSymbol" list="ntSymbolOptions" style="flex:1;min-width:110px" placeholder="instrument"
                    value="${G_ESC(nt.symbol || 'NQ')}" title="Any name your terminal lists \u2014 NQ, NQ1, ES, MNQ 12-26\u2026">
                <datalist id="ntSymbolOptions">${G_NT_NAMES().map((n) => `<option value="${G_ESC(n)}"></option>`).join('')}</datalist>
                <button class="btn primary" id="ntTestBtn"
                    title="Connect to the bridge inside NinjaTrader, subscribe, and report what arrived">Test the bridge</button>
            </div>
            <div class="r dim" id="ntTestResult">Checks in order: NinjaTrader running \u2192 bridge listening \u2192 hello \u2192 quotes/trades \u2192 depth (if your feed carries it).</div>
        </div>`;
}

function wireNinjatraderTestPanel(root) {
    const btn = root.querySelector('#ntTestBtn');
    if (!btn) return;
    btn.onclick = async () => {
        const out = root.querySelector('#ntTestResult');
        const payload = {
            host: (root.querySelector('#ntHost') || {}).value || '127.0.0.1',
            port: (root.querySelector('#ntPort') || {}).value || '8790',
            symbol: (root.querySelector('#ntSymbol') || {}).value || 'NQ',
        };
        btn.disabled = true;
        out.innerHTML = 'connecting\u2026';
        try {
            const r = await api('/api/control/platforms/bridge/ninjatrader/test', { method: 'POST', body: payload });
            out.innerHTML = ninjatraderTestMessage(r);
        } catch (e) {
            out.innerHTML = `<span class="wiz-bad">request failed: ${G_ESC(String(e))}</span>`;
        }
        btn.disabled = false;
    };
}

function ninjatraderTestMessage(r) {
    if (r && r.ok) {
        const b = r.bridge || {};
        const counts = r.messages || {};
        const got = [];
        if (counts.quotes) got.push(counts.quotes + ' quotes');
        if (counts.trades) got.push(counts.trades + ' trades');
        if (counts.depth) got.push(counts.depth + ' depth updates');
        return `<span class="wiz-ok">Connected.</span> bridge ${G_ESC(b.Addon || 'modflow-nt-bridge')} ${G_ESC(b.Version || '')}`
            + (b.NT ? ` \u00b7 NinjaTrader ${G_ESC(b.NT)}` : '')
            + (b.Connection ? ` \u00b7 connection ${G_ESC(b.Connection)} (${G_ESC(b.Status || '')})` : '')
            + (got.length ? `<br>streaming: ${got.join(' \u00b7 ')}` : '')
            + (r.depth ? `<br>${G_ESC(r.depth)}` : '')
            + '<br>Nothing was saved by this test \u2014 the bridge card in Platforms writes the settings.';
    }
    const msg = (r && (r.error || r.detail)) || 'no detail returned';
    return `<span class="wiz-bad">Not connected.</span> ${G_ESC(msg)}`;
}

/* ── the install-time alert: MT5 is available ───────────────────── */
function mt5NoticeSeen() {
    const cfg = S.config || {};
    return !!(cfg.mt5 && cfg.mt5.notice_seen);
}

function markMt5Notice(choice) {
    const cfg = JSON.parse(JSON.stringify(S.config || {}));
    cfg.mt5 = cfg.mt5 || {};
    cfg.mt5.notice = choice;                       // 'later' | 'seen'
    if (choice === 'seen') cfg.mt5.notice_seen = true;
    api('/api/control/config', { method: 'POST', body: cfg })
        .then((r) => { S.config = r.config; })
        .catch(() => { /* a notice flag is not worth an error dialog */ });
}

function maybeMt5Notice() {
    if (!S.config || mt5NoticeSeen()) return;
    if (document.getElementById('wizOverlay') || document.getElementById('helpOverlay')) {
        setTimeout(maybeMt5Notice, 3000);          // never stack two dialogs
        return;
    }
    helpStyles();
    const mt5 = (S.caps && S.caps.mt5) || {};
    const overlay = document.createElement('div');
    overlay.className = 'wiz-overlay';
    overlay.id = 'mt5Notice';
    overlay.innerHTML = `
        <div class="wiz-card notice-card" role="dialog" aria-modal="true" aria-label="Optional data source">
            <div class="wiz-head"><div>
                <div class="wiz-title">Optional: MetaTrader 5 data source</div>
                <div class="wiz-sub">indices, gold, FX and CFDs — if you have a broker terminal</div>
            </div><div style="flex:1"></div>
            <button class="btn small" id="mt5NoticeClose" title="Dismiss \u2014 this notice returns on the next start">\u2715</button></div>
            <div class="wiz-body">
                <p class="help-lead">This program ships with the exchange\u2019s public feed and needs no account.
                There is also a second, optional data source: <b>MetaTrader 5</b> — the road to instruments the
                exchange does not list (NAS100/US500/DAX, gold, FX, CFDs), straight from your broker\u2019s terminal.
                It is ${mt5.available === false
                    ? `<span class="wiz-bad">not ready on this machine yet</span> (${G_ESC(mt5.reason || 'not detected')})`
                    : '<span class="wiz-ok">ready on this machine</span>'}.</p>
                <p class="help-lead">Other optional add-ons, all free and all explained step by step in the Guide:
                phone push (ntfy), Telegram alerts, email, webhooks, deep-book extras and the market-context panel.</p>
            </div>
            <div class="wiz-foot">
                <div style="flex:1"></div>
                <button class="btn small" id="mt5NoticeLater" title="Decide later \u2014 the notice comes back next start">Later</button>
                <button class="btn small" id="mt5NoticeNever" title="Stop showing this notice">Don\u2019t show again</button>
                <button class="btn primary" id="mt5NoticeHow" title="Open the step-by-step MetaTrader 5 walkthrough">Show me how</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector('#mt5NoticeClose').onclick = () => { markMt5Notice('later'); close(); };
    overlay.querySelector('#mt5NoticeLater').onclick = () => { markMt5Notice('later'); close(); };
    overlay.querySelector('#mt5NoticeNever').onclick = () => { markMt5Notice('seen'); close(); };
    overlay.querySelector('#mt5NoticeHow').onclick = () => { markMt5Notice('later'); close(); openHelp('mt5'); };
}

/* ── wiring into the setup assistant ────────────────────────────── */
(function wireAssistantHelp() {
    if (typeof WIZ_STEPS === 'undefined' || !WIZ_STEPS.length) return;

    /* Data source step (index 1): say MT5 exists, and offer the walkthrough. */
    const ds = WIZ_STEPS[1];
    if (ds) {
        const render = ds.render;
        ds.render = function () {
            let html = render.apply(this, arguments);
            const mt5 = (S.caps && S.caps.mt5) || {};
            const banner = `
                <div class="help-needs" style="margin-top:10px">
                    <b>Also available: MetaTrader 5</b> \u2014 indices, gold, FX and CFDs from your broker\u2019s
                    terminal. It is ${mt5.available === false
                        ? `<span class="wiz-bad">not set up on this machine yet</span>`
                        : '<span class="wiz-ok">ready on this machine</span>'}.
                    <div class="row" style="margin-top:8px">
                        <button class="btn small" id="wizMt5How"
                            title="Open the step-by-step MetaTrader 5 setup walkthrough">How to set it up</button>
                        <button class="btn small" id="wizMt5TestNow"
                            title="Check the terminal, the Python bridge and your symbol mapping right now">Test the bridge</button>
                    </div>
                </div>`;
            const marker = '<button class="btn small" id="wizTestNet">';
            return html.includes(marker) ? html.replace(marker, banner + marker) : html + banner;
        };
        const after = ds.after;
        ds.after = function () {
            if (after) after.apply(this, arguments);
            const how = document.getElementById('wizMt5How');
            if (how) how.onclick = () => openHelp('mt5');
            const t = document.getElementById('wizMt5TestNow');
            if (t) t.onclick = () => openHelp('mt5');
        };
    }

    /* A MetaTrader step of its own, right after the data source. */
    WIZ_STEPS.splice(2, 0, {
        title: 'Broker account (optional)',
        render: () => {
            const st = ALPACA.status || {};
            return `
            <p>Alpaca Markets is a US brokerage with an API: commission-free stocks, ETFs, options and crypto,
            plus a <b>free paper-trading account</b> (email only, virtual money, resettable). Linking it adds
            those instruments and a real portfolio view to the program.</p>
            <div class="wiz-note">Current state: ${st.configured
                ? `<span class="wiz-ok">${st.paper ? 'paper' : 'live'} account linked</span> (${G_ESC(st.key_masked || '')})`
                : '<span class="wiz-bad">not linked</span> — nothing else in the program needs it'}.</div>
            <p class="dim" style="margin-top:10px">The form lives in one place so keys are only ever entered
            once: <b>Settings → Broker account</b>.</p>
            <div class="row" style="gap:8px;flex-wrap:wrap">
                <button class="btn" id="wizAlpOpen"
                    title="Jump to the account form in Settings">Open the account section</button>
                <button class="btn small" data-help="alpaca"
                    title="How to create an Alpaca account and generate keys">How to get keys</button>
            </div>`;
        },
        after: () => {
            const b = document.getElementById('wizAlpOpen');
            if (b) b.onclick = () => {
                if (typeof closeWizard === 'function') closeWizard();
                if (window.showView) window.showView('settings');
                setTimeout(() => alpacaLoad(true), 900);
            };
        },
        collect: () => { /* nothing collected: the Settings form owns the keys */ },
    });
WIZ_STEPS.splice(2, 0, {
        title: 'MetaTrader 5 (optional)',
        render: () => {
            const src = (GUIDE.cfg.data_source || 'bybit');
            const mt5 = (GUIDE.cfg.mt5 = GUIDE.cfg.mt5 || {});
            const caps = (S.caps && S.caps.mt5) || {};
            if (src === 'bybit' || src === 'binance' || src === 'hyperliquid' || src === 'okx') {
                return `
                <p>You picked the exchange\u2019s public feed \u2014 nothing to do here.</p>
                <p class="help-lead">If you ever want indices, gold, FX or CFDs as well, the MetaTrader 5 source
                can run <b>alongside</b> it (re-run this assistant and choose \u201cBoth\u201d). The walkthrough below
                covers a terminal install from scratch.</p>
                <button class="btn small" id="wizMt5How2"
                    title="Open the step-by-step MetaTrader 5 setup walkthrough">How MetaTrader 5 works</button>
                <div class="wiz-note">State on this machine: ${caps.available === false
                    ? `<span class="wiz-bad">${G_ESC(caps.reason || 'not available')}</span>`
                    : '<span class="wiz-ok">the Python bridge is installed</span>'}</div>`;
            }
            const rows = ((GUIDE.cfg.instruments) || []).filter((i) => i.enabled).map((i) => `
                <tr><td style="padding:2px 8px 2px 0">${G_ESC(i.symbol)}</td>
                    <td><input type="text" data-mt5sym="${G_ESC(i.symbol)}" value="${G_ESC(i.mt5_symbol || '')}"
                        placeholder="broker symbol" style="min-width:150px"
                        title="Your broker's name for this market, e.g. USTEC / US100 / NAS100 or XAUUSD / GOLD"></td>
                    <td class="dim" style="padding-left:8px">${i.asset_class === 'Crypto' ? 'crypto \u2014 the exchange feed already covers it' : 'needs a broker symbol'}</td></tr>`).join('');
            return `
            <p>The bridge talks to a <b>running</b> MetaTrader 5 terminal on this machine. Set the parts you need
            and test them now \u2014 the test connects, reports the terminal and the account, and disconnects again.</p>
            <div class="row" style="gap:8px;flex-wrap:wrap">
                <input type="text" id="wizMt5Path" style="flex:2;min-width:230px" placeholder="terminal path (optional)"
                    value="${G_ESC(mt5.path || '')}" title="Only if the terminal is not found automatically.">
                <input type="text" id="wizMt5Login" style="flex:1;min-width:110px" placeholder="login (optional)"
                    value="${G_ESC(mt5.login || '')}" title="Leave blank to use the account the terminal is signed in to.">
            </div>
            <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:6px">
                <input type="text" id="wizMt5Server" style="flex:1;min-width:150px" placeholder="server (optional)"
                    value="${G_ESC(mt5.server || '')}" title="Broker server name (Tools \u2192 Options \u2192 Server).">
                <input type="password" id="wizMt5Password" style="flex:1;min-width:130px" placeholder="password (optional)"
                    title="Stored in your local config file, never displayed back.">
                <button class="btn primary" id="wizMt5TestBtn"
                    title="Connect with these settings, report the terminal, account and mapped symbols, then disconnect">Test the bridge</button>
            </div>
            ${rows ? `<div style="margin-top:12px"><b>Your instruments and their broker names</b>
                <table style="margin-top:4px">${rows}</table></div>` : ''}
            <div class="r dim" id="wizMt5Result" style="margin-top:8px">State on this machine: ${caps.available === false
                ? `<span class="wiz-bad">${G_ESC(caps.reason || 'not available')}</span>` : '<span class="wiz-ok">bridge installed</span>'}</div>
            <div class="row" style="margin-top:10px">
                <button class="btn small" id="wizMt5How3"
                    title="Open the full walkthrough: install, log in, bridge, symbols">Full walkthrough</button>
            </div>`;
        },
        after: () => {
            const btn = document.getElementById('wizMt5TestBtn');
            const panel = document.getElementById('wizMt5Result');
            const how = document.getElementById('wizMt5How2') || document.getElementById('wizMt5How3');
            if (how) how.onclick = () => openHelp('mt5');
            if (!btn || !panel) return;
            btn.onclick = async () => {
                btn.disabled = true;
                panel.innerHTML = 'connecting\u2026';
                try {
                    const r = await api('/api/control/mt5/test', {
                        method: 'POST',
                        body: {
                            path: (document.getElementById('wizMt5Path') || {}).value || '',
                            login: (document.getElementById('wizMt5Login') || {}).value || '',
                            server: (document.getElementById('wizMt5Server') || {}).value || '',
                            password: (document.getElementById('wizMt5Password') || {}).value || '',
                            symbols: ((GUIDE.cfg.instruments) || []).filter((i) => i.enabled)
                                .map((i) => i.mt5_symbol).filter(Boolean),
                        },
                    });
                    panel.innerHTML = mt5TestMessage(r);
                } catch (e) {
                    panel.innerHTML = `<span class="wiz-bad">request failed: ${G_ESC(String(e))}</span>`;
                }
                btn.disabled = false;
            };
        },
        collect: () => {
            const mt5 = (GUIDE.cfg.mt5 = GUIDE.cfg.mt5 || {});
            const get = (id) => { const el = document.getElementById(id); return el ? el.value : null; };
            const path = get('wizMt5Path'); if (path !== null) mt5.path = path.trim();
            const login = get('wizMt5Login'); if (login !== null) mt5.login = parseInt(login, 10) || 0;
            const server = get('wizMt5Server'); if (server !== null) mt5.server = server.trim();
            const password = get('wizMt5Password'); if (password) mt5.password = password;   // never overwrite with ''
            document.querySelectorAll('[data-mt5sym]').forEach((el) => {
                const inst = (GUIDE.cfg.instruments || []).find((i) => i.symbol === el.dataset.mt5sym);
                if (inst) inst.mt5_symbol = el.value.trim();
            });
        },
    });

    /* Every other optional step gets its walkthrough button too. */
    const byTitle = {};
    WIZ_STEPS.forEach((s) => { byTitle[s.title] = s; });
    const addHelpButton = (step, topic, label, anchorId) => {
        if (!step) return;
        const render = step.render;
        step.render = function () {
            const html = render.apply(this, arguments);
            const btn = `<div style="margin-top:10px"><button class="btn small" data-help="${topic}"
                title="Step-by-step instructions for this optional piece">${label}</button></div>`;
            return html + btn;
        };
    };
    addHelpButton(byTitle['Instruments'], 'instruments', 'How instrument importing works');
    addHelpButton(byTitle['Feeds, history & extras'], 'extras', 'What these extras unlock');
    addHelpButton(byTitle['Alerts & notifications (optional)'], 'ntfy', 'How phone push (ntfy) works');
    addHelpButton(byTitle['Market context (optional)'], 'context', 'What these numbers mean');

    /* One delegated listener handles every help button, present or future. */
    document.addEventListener('click', (e) => {
        const b = e.target && e.target.closest && e.target.closest('[data-help]');
        if (b) {
            /* §123: 'studies', 'bridges' and 'start.identity' carried dead clicks — openHelp()
               returned silently on an unknown id. The Help Centre's openTopic falls back to a
               search by itself, so an unknown id still LANDS somewhere. */
            if (HELP_TOPICS[b.dataset.help]) openHelp(b.dataset.help);
            else if (window.OFAPHELP) OFAPHELP.open(b.dataset.help);   // lands on the search results
        }
    });

    /* The alert step names four channels: give each its own walkthrough. */
    const alerts = byTitle['Alerts & notifications (optional)'];
    if (alerts) {
        const after = alerts.after;
        alerts.after = function () {
            if (after) after.apply(this, arguments);
            const body = document.getElementById('wizBody');
            if (!body) return;
            const links = [['telegram', 'Telegram, step by step'], ['ntfy', 'ntfy push, step by step'],
                           ['email', 'Email (SMTP), step by step'], ['webhook', 'Webhook, step by step']];
            const box = document.createElement('div');
            box.style.marginTop = '10px';
            box.innerHTML = '<div class="dim" style="font-size:12px;margin-bottom:4px">Walkthroughs:</div>'
                + links.map(([id, label]) =>
                    `<button class="btn small" data-help="${id}" style="margin:0 6px 6px 0">${label}</button>`).join('');
            body.appendChild(box);
        };
    }
})();

/* ── a Guide section listing every walkthrough ──────────────────── */
(function addHowToSection() {
    if (typeof GUIDE_SECTIONS === 'undefined') return;
    const items = [
        ['mt5', 'MetaTrader 5 data source', 'indices, gold, FX and CFDs from your broker\u2019s terminal \u2014 install, login, bridge, symbol mapping, live test'],
        ['instruments', 'Instruments', 'importing the venue\u2019s own list with real tick sizes, and mapping MT5 broker names'],
        ['extras', 'Deep book, liquidations, history', 'what each extra unlocks and what turning it off costs'],
        ['ntfy', 'Phone push (ntfy)', 'no account at all \u2014 pick a topic, subscribe, test'],
        ['telegram', 'Telegram alerts', 'a free bot in two minutes'],
        ['email', 'Email alerts', 'SMTP with an app password, and why it starts unrouted'],
        ['webhook', 'Webhook', 'Slack / Discord / your own endpoint'],
        ['context', 'Market context', 'funding, open interest, long/short, Fear & Greed, headlines'],
    ];
    GUIDE_SECTIONS.push({
        h: 'Setup how-tos (step by step)',
        body: `<p>Each optional piece of this program has a short walkthrough. Nothing here is required —
                 the core analytics run on public data with no account at all.</p>
               ${items.map(([id, title, blurb]) => `
                 <div class="help-topic">
                   <div class="grow"><b>${title}</b><span class="dim">${blurb}</span></div>
                   <button class="btn small" data-help="${id}"
                       title="Open the step-by-step walkthrough">Open</button>
                 </div>`).join('')}`,
    });
    /* §117: the identity block — the competitive pass named the missing framing: a platform in
       this niche should say what it is and is not, so the gaps stop reading as deficiencies. */
    GUIDE_SECTIONS.push({
        h: 'What this program is — and is not',
        body: `<p><b>An analytics layer, not a broker terminal.</b> ModFlow reads the market in depth —
                 order flow, CVD, profile, heatmap, depth, tape, trackers, alerts, replay — and sits
                 beside whatever you execute in. It places no orders and holds no funds; your terminal
                 stays your terminal.</p>
               <p><b>The data.</b> The built-in venues (Bybit, Binance, Hyperliquid, OKX, Alpaca crypto)
                 are free public feeds needing no key; MT5 and NinjaTrader 8 ride the terminal you
                 already run. What a broker or exchange charges for its own data is between you and
                 them — exactly as with any terminal.</p>
               <p><b>The workspace is yours to keep.</b> Screen arrangements save as layouts, whole setups
                 save as playbooks, indicator sets save as collections, and every shortcut can be
                 re-bound — all in your own config file. A layout also keeps its last five states
                 (<b>Layout ▸ Previous versions</b>), so an auto-arrange, a reset or a save-over is one
                 click back.
                 <button class="btn small" data-help="start.identity">Open the topic</button></p>`,
    });
    /* §128: the multi-monitor section — the one place that says what the whole capability is,
       now that send/snap/rescue all exist in both modes. */
    GUIDE_SECTIONS.push({
        h: 'Multiple monitors',
        body: `<p>Every panel can live in its own real window, on any monitor. The quickest route is the
                 <b>⧉</b> button on a widget's title bar (Terminal mode) or <b>View ▸ Windows &amp;
                 layouts…</b>: pick a panel, a monitor and a shape, and the window opens there already
                 placed — left half of Monitor 2, full screen on the third display, anything.</p>
               <p>A window that is already open can be sent to another monitor at any time (<b>⇥</b> on
                 its row in the Windows menu, or <b>Ctrl+Alt+Shift+← / →</b>), snapped to a half, a
                 corner or the whole monitor with one click, and pinned above your other windows.
                 Positions are remembered, so tomorrow's launch reopens the same desk; a window whose
                 monitor is gone comes home to the primary instead of sitting off-screen, and
                 <b>Bring them home</b> in the dialog rescues every stranded window at once.</p>
               <p>Both modes are covered: in Terminal mode the ⧉ button sits on each widget, in Classic
                 mode the same dialog opens any panel on any monitor. What an OS drag would do is a
                 command here — Windows' own Win+Shift+Arrow, spelled with Alt so it cannot collide.</p>`,
    });
    /* the view is built lazily, but if it already exists, refresh it */
    const body = document.getElementById('guideBody');
    if (body) {
        body.innerHTML = GUIDE_SECTIONS.map((s) => `
            <div class="card" style="margin-bottom:12px">
                <div class="card-head"><span class="card-title">${s.h}</span></div>
                <div class="card-body guide-copy">${s.body}</div>
            </div>`).join('');
        if (typeof applyTips === 'function') applyTips(body);
    }
})();

/* ── announce the option once per install, after onboarding ─────── */
(function scheduleMt5Notice() {
    let tries = 0;
    const tick = () => {
        tries += 1;
        if (S.config && (S.config.onboarding_done || tries > 40)) {
            if (!S.config.onboarding_done) setTimeout(tick, 3000);
            else setTimeout(maybeMt5Notice, 800);
            return;
        }
        if (tries > 200) return;
        setTimeout(tick, 1500);
    };
    setTimeout(tick, 2500);
})();

/* ══════════════════════════════════════════════════════════════════
   7. The setup-wizard button in the rail (above Overview)

   The brief for this section: a shortcut to the wizard in the top-left nav, tinted gently
   amber while setup is unfinished and green once it has been completed.

   "Completed" means the assistant was actually finished (Next/Finish on the last
   step) — skipping or closing it leaves the button amber, which is the honest
   reading. The flag lives in the saved config as `setup_complete`.
   ══════════════════════════════════════════════════════════════════ */

function setupButtonStyles() {
    if (document.getElementById('setupNavStyle')) return;
    const st = document.createElement('style');
    st.id = 'setupNavStyle';
    st.textContent = `
        .nav-setup { display: flex; align-items: center; gap: 8px; }
        .nav-setup .nav-setup-label { flex: 1; text-align: left; }
        .nav-setup .nav-dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 8px;
                              box-shadow: 0 0 0 3px rgba(255,255,255,0.03); }
        /* gently tinted, not loud: a soft wash plus a 3px edge */
        .nav-setup.is-todo { background: rgba(232, 190, 84, 0.10);
                             box-shadow: inset 3px 0 0 rgba(232, 190, 84, 0.85); }
        .nav-setup.is-todo .nav-dot { background: #e8be54; }
        .nav-setup.is-todo .nav-icon { color: #e8be54; }
        .nav-setup.is-done { background: rgba(88, 200, 130, 0.10);
                             box-shadow: inset 3px 0 0 rgba(88, 200, 130, 0.85); }
        .nav-setup.is-done .nav-dot { background: #58c882; }
        .nav-setup.is-done .nav-icon { color: #58c882; }
        .nav-setup:hover { background: rgba(255,255,255,0.06); }
        .nav-setup.is-todo:hover { background: rgba(232, 190, 84, 0.16); }
        .nav-setup.is-done:hover { background: rgba(88, 200, 130, 0.16); }
    `;
    document.head.appendChild(st);
}

function setupIsComplete() {
    return !!(S.config && S.config.setup_complete);
}

function refreshSetupButton() {
    const btn = document.getElementById('navSetupBtn');
    if (!btn) return;
    const done = setupIsComplete();
    btn.classList.toggle('is-done', done);
    btn.classList.toggle('is-todo', !done);
    btn.title = done
        ? 'Setup wizard — completed on this install. Click to re-run it any time; '
          + 'your answers are saved to the local config file. (Green = complete.)'
        : 'Setup wizard — not finished on this install. Click to walk through data source, '
          + 'instruments, feeds, alerts and the optional extras. (Amber = not complete; it turns '
          + 'green when you reach the end and press Finish.)';
    const dot = btn.querySelector('.nav-dot');
    if (dot) dot.title = done ? 'Setup complete' : 'Setup not complete yet';
}

function mountSetupButton() {
    const rail = document.querySelector('.rail') || document.querySelector('nav.rail') || document.querySelector('aside');
    if (!rail) return false;
    if (document.getElementById('navSetupBtn')) { refreshSetupButton(); return true; }
    setupButtonStyles();
    const btn = document.createElement('button');
    btn.className = 'nav-item nav-setup';
    btn.id = 'navSetupBtn';
    btn.setAttribute('aria-label', 'Setup wizard');
    btn.innerHTML = '<span class="nav-icon">\u2726</span>'
        + '<span class="nav-setup-label">Setup wizard</span><span class="nav-dot"></span>';
    btn.onclick = () => {
        if (typeof openWizard === 'function') openWizard(true);
        setTimeout(refreshSetupButton, 1200);      // in case they finish immediately
    };
    /* directly above Overview — i.e. the first nav item in the rail */
    const first = rail.querySelector('.nav-item');
    if (first) rail.insertBefore(btn, first);
    else rail.appendChild(btn);
    refreshSetupButton();
    return true;
}

/* a real finish (not Skip) records completion, and finishWizard saves it */
(function wrapFinishWizard() {
    if (typeof finishWizard !== 'function') return;
    const original = finishWizard;
    finishWizard = async function (opts) {
        const skipped = !!(opts && opts.skip);
        if (!skipped && GUIDE.cfg) GUIDE.cfg.setup_complete = true;
        const out = await original.call(this, opts || {});
        refreshSetupButton();
        setTimeout(refreshSetupButton, 800);
        setTimeout(refreshSetupButton, 2500);
        return out;
    };
})();

/* mount as soon as the rail exists, then keep it honest */
(function bootSetupButton() {
    let tries = 0;
    const tick = () => {
        tries += 1;
        if (mountSetupButton()) { refreshSetupButton(); return; }
        if (tries < 40) setTimeout(tick, 500);
    };
    tick();
    setInterval(refreshSetupButton, 8000);          // follows config changes from anywhere
})();

/* ── the professional leg ───────────────────────────────────────────────────────────────────────
   Ten steps that take a desk user from "it streams" to "every capability is configured and proven".
   Each one says what it unlocks, what a professional sets here, and where to go deeper. Nothing in
   here can break the express path: it is only reachable when GUIDE.mode === 'pro'. */
/* The playbook step (fold-in plan \u00a74 \u2192 U4): placed just before the wizard\u2019s own
   ending, wherever the earlier splices have pushed \u201cReady\u201d to. It is a map, not a
   form: the four surfaces the order-flow workflow lives on, and the topic that explains the
   reading order. Nothing here changes configuration. */
WIZ_STEPS.splice(Math.max(0, WIZ_STEPS.length - 1), 0, {
    title: 'Reading the market (optional)',
    render: () => `
        <p>Setup done \u2014 the rest is reading. The program arranges itself around one workflow:
        <b>profile first</b> (direction and levels), <b>then order flow</b> (a confirmation at a
        level you chose), and <b>one test per level</b>.</p>
        <div class="wiz-note">Everything below already works on the public feed. Nothing here is
        required \u2014 it is where the reads live when you want them.</div>
        <div class="row" style="gap:8px;flex-wrap:wrap">
            <button class="btn small" id="wizPbScanner"
                title="The ranked table: every instrument, with the level radar column">Open the Scanner</button>
            <button class="btn small" id="wizPbEngine"
                title="Footprint, level reads and the area profile">Open the Engine</button>
            <button class="btn small" data-helptopic="method.reading_order"
                title="How the reads stack: profile, level, confirmation, one test">How to read it</button>
            <button class="btn small" data-helptopic="method.radar"
                title="Armed, approaching, held, spent \u2014 what the radar states mean">The level radar</button>
        </div>`,
    after: () => {
        const s = document.getElementById('wizPbScanner');
        if (s) s.onclick = () => {
            if (typeof closeWizard === 'function') closeWizard();
            if (window.showView) window.showView('scanner');
        };
        const e = document.getElementById('wizPbEngine');
        if (e) e.onclick = () => {
            if (typeof closeWizard === 'function') closeWizard();
            if (window.showView) window.showView('ofx');
        };
    },
    collect: () => { /* nothing collected: this step is a map, not a form */ },
});

const WIZ_PRO = [
    {
        title: 'Professional · Feed budget',
        render: () => `
            <p>The engine ingests public exchange data over REST and websocket, under budgets that keep
            it a good citizen and predictable under load. This is what a desk tunes first.</p>
            <div class="wiz-note"><b>What a professional sets:</b> depth freshness at 5 s and quote
            freshness at 60 s (the windows the app treats as "live" before it flags staleness),
            symbols capped at 30, quotes at 200, and REST at 200/min with 150 held in reserve for
            interactive calls. The reserve is the important one: it is what keeps your clicks
            responsive while background refreshes run.</div>
            ${wizFooter({
                unlocks: 'staleness you can see and trust, and a feed that stays responsive under load',
                deeper: 'the Connections panel names every venue, its wires and its budgets',
                view: 'platforms', label: 'Open Connections' })}
            <p class="dim">Live values are on the Connections panel; the status bar shows the active
            source and freshness at all times.</p>
        `,
    },
    {
        title: 'Professional · Instruments',
        render: () => `
            <p>The express path enables three majors. A desk runs its own set &mdash; the venue
            catalogue is the whole point of this step.</p>
            <div class="wiz-note"><b>What a professional sets:</b> one instrument per strategy leg
            (the pair you actually trade, plus the reference you compare against), and nothing else.
            Every enabled symbol costs feed budget and a slice of render time; a 25-symbol watchlist
            looks impressive and answers nothing.</div>
            ${wizFooter({
                unlocks: 'the right universe of symbols, with the budget spent where you look',
                deeper: 'the Instruments panel validates against the venue catalogue, so a symbol it accepts is one the engine can actually stream',
                view: 'instruments', label: 'Open Instruments' })}
        `,
    },
    {
        title: 'Professional · Engine internals',
        render: () => `
            <p>These are the numbers behind the footprint and heatmap. Defaults are good; desks have
            opinions.</p>
            <div class="wiz-grid" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))">
                <label class="dim">Row size (ticks per drawn row)<br><input id="wzR" type="number" min="1" max="8" placeholder="from config"></label>
                <label class="dim">Stack depth (levels)<br><input id="wzStack" type="number" min="10" max="400" placeholder="from config"></label>
                <label class="dim">Decay lambda (ms)<br><input id="wzLambda" type="number" min="100" max="5000" step="50" placeholder="from config"></label>
                <label class="dim">Value area %<br><input id="wzVA" type="number" min="50" max="95" placeholder="from config"></label>
                <label class="dim">Minimum block (contracts)<br><input id="wzBlock" type="number" min="1" max="500" placeholder="from config"></label>
                <label class="dim">Cell text threshold (px)<br><input id="wzText" type="number" min="1.5" max="20" step="0.5" placeholder="from config"></label>
            </div>
            <div class="wiz-note"><b>What a professional sets:</b> row size to the instrument's tick
            grid (BTC at 0.5 is not ES at 0.25), value area to the session convention you publish
            against (70 % is the CME default), and the text threshold so numbers appear exactly when
            they are readable &mdash; the engine hides text before it draws it illegibly, which is why
            zooming out shows profiles and zooming in shows numbers.</div>
            ${wizFooter({
                unlocks: 'a footprint calibrated to your instrument and your session convention',
                deeper: 'the Engine view shows the live aggregation factor, rows and cells as you zoom — the Guide explains the ladder',
                view: 'ofx', label: 'Open the Engine view' })}
            <p class="dim">Blank fields keep the current value; ranges are clamped by the program.</p>
        `,
        collect: () => { wzWrite(); },
    },
    {
        title: 'Professional · Order-flow analytics',
        render: () => `
            <p>The analytics read the same tape as the engine, so this is where you decide what
            "signal" means on your instrument.</p>
            <div class="wiz-note"><b>What a professional sets:</b> an imbalance ratio that matches the
            venue's typical lot size (a 3:1 threshold is noise on BTC, information on a thin
            altcoin), absorption against the resting side, and CVD divergence as an accent rather
            than an alarm &mdash; it marks where price and cumulative delta disagree, not where to
            trade.</div>
            <div class="wiz-note"><b>What you will see:</b> the heatmap for liquidity over time, the
            split-cell footprint for aggression per level, CVD for net pressure, the profile for where
            value built. Each is a different question about the same tape.</div>
            ${wizFooter({
                unlocks: 'thresholds that match your instrument, so signals mean something',
                deeper: 'the Guide walks the panel map: liquidity, aggression, pressure, value',
                view: 'guide', label: 'Open the panel map' })}
        `,
    },
    {
        title: 'Professional · Studies runtime',
        render: () => `
            <p>The studies runtime accepts indicator modules in this suite's own form &mdash; plots,
            parameters, a calculator &mdash; and runs them over the same bars the charts use, so a
            study and the tape never disagree about time.</p>
            <div class="wiz-note"><b>What a professional does here:</b> load the starters as reference
            implementations, then paste your own. A module that returns a plain number is complete: the
            runtime gives it an implicit value plot rather than complaining. Warm-up is honest &mdash;
            a period-14 average deliberately leaves the first 13 bars unplotted.</div>
            ${wizFooter({
                unlocks: 'your own indicators running over live tape, with parameters editable in place',
                deeper: 'the Studies panel has the library, the parameter forms, the paste box and a Data Box feed',
                view: 'studies', label: 'Open Studies' })}
        `,
    },
    {
        title: 'Professional · Layout & workspaces',
        render: () => `
            <p>Panels are grouped by purpose &mdash; Order flow, Analytics, Trading, Information &mdash;
            and a named workspace is the whole arrangement, not a single toggle.</p>
            <div class="wiz-note"><b>What a professional sets:</b> one workspace per task. A scalping
            workspace is the engine, depth and order flow; a research workspace is profile, CVD and
            studies. Save each by name and switch with two keystrokes instead of rebuilding a screen
            after every context change.</div>
            <div class="wiz-note"><b>Starting layout:</b> the engine view is the centrepiece and the
            one to learn first; everything else is a lens on the same tape.<br>
            <div style="margin-top:6px"><button class="btn small" data-wiz-save-ws="research">Save a
            "research" workspace from the current layout</button></div></div>
            <div class="wiz-note"><b>If a layout change goes wrong:</b> <b>Layout ▸ Previous versions
            of this layout</b> holds the last five states of the layout you are on — one click puts
            one back. Arranging a board, resetting it, saving over it or deleting it is one click
            each, so the undo is one click too. Five is the depth because that is the handful people
            actually reach for, and because every version is a full copy in your config file; the
            <b>Auto-cull</b> switch inside that submenu is what keeps it at five (turn it off to keep
            up to ten). A restore is recorded as well, so you can step forward again if the older
            arrangement was not the one you wanted.</div>
            ${wizFooter({
                unlocks: 'a screen you can rebuild instantly, arranged for the task at hand',
                deeper: 'the ☰ menu groups panels by purpose and the Workspaces group saves and recalls them',
                view: 'menu', label: 'Open the menu' })}
        `,
    },
    {
        title: 'Professional · Hotkeys & workflow',
        render: () => `
            <p>Speed on a desk is muscle memory. Every binding here has a scope, so a key means the
            same thing in the same context and nothing surprising outside it.</p>
            <div class="wiz-note"><b>Defaults worth knowing:</b> <b>Ctrl+K</b> the command palette
            (every panel, one box), <b>P</b> freeze the background refreshes the moment you want to
            read a static screen, <b>?</b> or <b>F1</b> the map of every binding, <b>1&hellip;9</b>
            switch views in rail order &mdash; and on the panels themselves <b>X</b> clears a
            selection, <b>Ctrl+E</b> exports it, <b>=</b> / <b>&minus;</b> and <b>[</b> / <b>]</b>
            zoom the engine, <b>A</b> alerts on the heatmap cursor, <b>Space</b> plays and pauses
            the replay.</div>
            <div class="wiz-note"><b>What a professional sets:</b> one habit &mdash; freeze before you
            read, unfreeze before you trade. Live panels that repaint under your eyes are for
            monitoring; a frozen screen is for deciding.</div>
            ${wizFooter({
                unlocks: 'navigation without the mouse, and a freeze key you will use constantly',
                deeper: 'the hotkey map lists every binding and its scope',
                view: 'hotkeys', label: 'Open the hotkey map' })}
        `,
    },
    {
        title: 'Professional · Bridges & accounts',
        render: () => `
            <p>The program stands alone on public data. Bridges are for what public data cannot give
            you: your broker's fills and, for the DTC platform users, the DTC feed.</p>
            <div class="wiz-note"><b>Kept out of this wizard, deliberately:</b> API keys and passwords
            are entered on the Connections panel&mdash;inside the program, in its own config&mdash;and
            are never typed into a setup assistant or sent anywhere else. The wizard will not ask for a
            secret, and neither should anything else that offers to.</div>
            <div class="wiz-note"><b>What a professional sets:</b> DTC pointed at a local the DTC platform
            instance (host and port only, off by default until the port answers), Alpaca for the
            crypto tape where the venue publishes no book, and nothing else until it earns its
            place.</div>
            ${wizFooter({
                unlocks: 'your own fills and a second opinion on the tape, without putting keys in a form',
                deeper: 'Connections shows every venue: wired, reachable, or honestly refused by name',
                view: 'platforms', label: 'Open Connections' })}
        `,
    },
    {
        title: 'Professional · Performance & hygiene',
        render: () => `
            <p>An order-flow screen is a real-time renderer. These are the habits that keep it at
            frame rate on a desk machine.</p>
            <div class="wiz-note"><b>What a professional does:</b> keeps the engine view on one
            display at 100 % scaling (fractional scaling costs a full re-raster, not just a resize),
            freezes background refreshes when reading a static screen, keeps the symbol set small, and
            lets the aggregation ladder do its job instead of fighting it with zoom. The engine is
            built to sit at 144&nbsp;Hz with the default view; it degrades by design &mdash; profiles
            first, then text &mdash; rather than dropping frames.</div>
            ${wizFooter({
                unlocks: 'a screen that stays smooth under load, instead of one that looks impressive and stutters',
                deeper: 'every panel\'s freshness chip and the status bar\'s data pill show the age of what you are reading',
                view: 'logs', label: 'Open Logs' })}
        `,
    },
    {
        title: 'Professional · Prove it works',
        render: () => `
            <p>Setup is not done when the settings are right. It is done when you have watched each
            capability do its job. Run this list now; it takes two minutes and it is the difference
            between a configured program and one you can trust.</p>
            <div class="wiz-note">
                ☐ <b>Engine streaming</b> &mdash; press Start engine, then confirm price and delta move
                and the freshness line says live.<br>
                ☐ <b>Footprint</b> &mdash; open the engine view and zoom the price axis: numbers appear
                on the big rows only, and the values stay legible.<br>
                ☐ <b>Heatmap</b> &mdash; liquidity bands refresh without the stage jumping.<br>
                ☐ <b>CVD</b> &mdash; a divergence accent appears where price and delta disagree.<br>
                ☐ <b>Studies</b> &mdash; a starter study plots, and its parameters change the series.<br>
                ☐ <b>Freeze</b> &mdash; P holds the screen still; P resumes the refresh.<br>
                ☐ <b>Workspace</b> &mdash; save your arrangement, switch away, switch back, and land in
                the same screen.<br>
                ☐ <b>Resize</b> &mdash; drag, maximise, restore from minimised: charts re-fit and stay
                sharp, never cropped or stretched.
            </div>
            <div class="wiz-note"><b>Where to go deeper:</b> the panel map explains what each surface
            is for; the hotkey map lists every binding and its scope.</div>
            ${wizFooter({
                unlocks: 'proof, not hope: every capability you paid attention to, confirmed working',
                deeper: 'the Guide holds the panel map, the aggregation ladder and the study contract',
                view: 'guide', label: 'Open the Guide' })}
        `,
    },
];

/* Writes the engine-internals step into the config block the finish step saves. */
function wzWrite() {
    const num = (id) => {
        const el = document.getElementById(id);
        const v = el && el.value !== '' ? Number(el.value) : null;
        return Number.isFinite(v) ? v : null;
    };
    const ofx = (GUIDE.cfg.ofx = GUIDE.cfg.ofx || {});
    const map = [['wzR', 'R'], ['wzStack', 'stack'], ['wzLambda', 'lambda_ms'], ['wzVA', 'va_pct'],
                 ['wzBlock', 'min_block'], ['wzText', 'cell_text_px']];
    map.forEach(([id, key]) => { const v = num(id); if (v !== null) ofx[key] = v; });
}
