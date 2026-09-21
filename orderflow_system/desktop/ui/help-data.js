/* ══════════════════════════════════════════════════════════════════
   help-data.js — the Help Centre's topic corpus.

   One place that says what every part of this program is for. The Advanced interface shows all of
   it; the Simple interface shows the same entries minus the `mode: 'advanced'` ones (which are the
   ones worth reading before you touch them rather than after), plus the system check on top.

   Shape of a topic:
     id        a stable slug (`view.heatmap`, `connect.mt5`, `fix.no_data`) — checks in help.py point
               at these, so an id is a promise: renaming one means updating the check that names it
     group     the section it files under (GROUPS below)
     mode      'both' | 'advanced' — 'advanced' hides the topic from the Simple interface
     title     what the user sees
     tags      the words someone would actually type (weighted high by the search engine)
     summary   one or two sentences, shown in results and at the top of the article
     blocks    the article body: heading / paragraph / list / table / steps / note / warn / shot /
               keys / check / cmd
     actions   in-app shortcuts: buttons that open a view, run a wizard step, open a folder or run
               a search — the kinds the UI implements (help.js `ACTIONS`)
     links     external links (help.py's LINKS carries the same places for the About card)
     related   2-4 ids to read next
     shots     screenshots, only where a picture beats a paragraph (docs/ui/help/*)

   Inline markup in the text is a small subset: **bold**, `code`, *italic*. Everything else is
   escaped by the renderer, and the corpus is app-authored, never user-authored.

   The VIEWS map at the bottom is the coverage contract: every `data-view` in index.html has a
   topic. `test_help.py` reads the app's own markup and fails when one does not.
   ══════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    const GROUPS = [
        { id: 'start', label: 'Getting started', mode: 'both',
          blurb: 'What this program is, what to do first, and how to find your way around.' },
        { id: 'panels', label: 'Panels, one by one', mode: 'both',
          blurb: 'Every view in the rail: what it draws, how to read it, and what to do with it.' },
        { id: 'workflow', label: 'Working with the app', mode: 'both',
          blurb: 'The terminal layout, layouts and workspaces, drawings, keys, looks and exports.' },
        { id: 'connect', label: 'Connections and setup', mode: 'both',
          blurb: 'Data sources, MetaTrader 5, a broker account, and where alerts go.' },
        { id: 'data', label: 'Data, files and storage', mode: 'advanced',
          blurb: 'The files this program writes, how long ticks are kept, and how it is exposed.' },
        { id: 'under', label: 'Under the hood', mode: 'advanced',
          blurb: 'How the pieces fit together, the HTTP surface, the build, diagnostics.' },
        { id: 'method', label: 'Reading the market', mode: 'both',
          blurb: 'The decision order the order-flow workflow follows: profile first, then a '
              + 'confirmation at a level you chose \u2014 and which read in this program is which.' },
        { id: 'fix', label: 'Fixes and support', mode: 'both',
          blurb: 'When something looks wrong: the system check, the common causes, how to report it.' },
    ];

    const TOPICS = [

        /* ═══════════ Getting started ═══════════ */
        {
            id: 'start.first_run', group: 'start', mode: 'both',
            title: 'Your first fifteen minutes',
            tags: ['first run', 'new install', 'start here', 'beginner', 'getting started', 'setup'],
            aliases: ['onboarding', 'quick start', 'first steps'],
            summary: 'A fresh install streams the exchange\'s public market data with no account and no key. '
                + 'This is the shortest path from "just installed" to "reading the tape".',
            blocks: [
                { h: 'Five steps', steps: [
                    { t: 'Start the engine', d: 'The button in the top bar (or **Data ▸ Start engine**). '
                        + 'Until you do, the panels show demo data or their last known values, and the '
                        + 'data pill says so.' },
                    { t: 'Pick an instrument', d: 'The Instrument box in the top bar. A fresh install ships '
                        + 'BTCUSDT enabled; **Instruments** is where you add more.' },
                    { t: 'Watch the Overview', d: 'Price, cumulative delta, tick counts and the latest '
                        + 'detections for the session — the fastest way to confirm data is flowing.' },
                    { t: 'Read one order-flow panel', d: '**Time & Sales** is the simplest: every '
                        + 'execution, newest first, large prints highlighted. **Order Flow** adds the '
                        + 'bid/ask split per price.' },
                    { t: 'Then open the Engine view', d: 'The order-flow engine draws the footprint matrix '
                        + 'with a live depth heat behind it — the most information per pixel in the '
                        + 'program. Its legend panel names every colour and every control.' },
                ] },
                { note: 'Nothing is required: no account, no key, no card. Two extras are optional and '
                    + 'free — an Alpaca paper account (US stocks, ETFs and options) and a Telegram bot '
                    + 'for alerts on your phone.' },
                { shot: 'help/overview-live.png',
                  caption: 'The Overview on the Bybit feed: KPI cards, the session summary and the market-context block.' },
                { h: 'Before you rely on it', p: 'A data feed is not a promise. The Engine\'s start button '
                    + 'restarts the feed; the **data** pill in the top bar always says whether what you '
                    + 'are looking at is live, warming up, or demo. If numbers stop moving, that pill and '
                    + 'the freshness chip on each panel are the first things to read — see '
                    + '*"When a panel has no data"*.' },
            ],
            actions: [
                { label: 'Run the setup assistant', kind: 'wizard', value: '' },
                { label: 'Open Overview', kind: 'view', value: 'overview' },
                { label: 'Choose instruments', kind: 'view', value: 'instruments' },
                { label: 'Watch the tape', kind: 'view', value: 'tape' },
            ],
            related: ['start.engine', 'start.window', 'view.ofx', 'fix.no_data'],
        },
        {
            id: 'start.window', group: 'start', mode: 'both',
            title: 'The window: rail, top bar, status bar',
            tags: ['interface', 'layout', 'rail', 'status bar', 'top bar', 'panels', 'navigation'],
            aliases: ['ui', 'chrome', 'screen layout'],
            summary: 'Every screen is built from the same four pieces — the rail on the left, the menu '
                + 'bar and top bar across the top, the panel in the middle, the status bar along the '
                + 'bottom. Once those four make sense, the program is small.',
            blocks: [
                { h: 'The four pieces', table: [
                    ['Rail (left)', 'One button per panel, in the order the keyboard reaches them: '
                        + 'press **1**…**9** for the first nine. The badge counts (Trackers, Signals, '
                        + 'Alerts) show what is waiting in those panels.'],
                    ['Menu bar', 'File, View, Layout, Drawings, Chart, Data, Profiles, Tools and Help. '
                        + 'It is a real Windows menu: **Alt** focuses it, arrows walk it, Enter opens. '
                        + 'Items that are not built yet are greyed out *with the reason in the tooltip* '
                        + 'rather than hidden.'],
                    ['Top bar', 'The instrument picker, the engine buttons, and four pills that answer '
                        + '*what am I looking at*: engine state, websocket, source, and whether the data '
                        + 'is live, warming, or demo. The ☰ button (or **/**) opens the menu of panels '
                        + 'grouped by what you are doing.'],
                    ['Status bar (bottom)', 'Source, workspace, mode, tab, widget count, feed and bus — '
                        + 'plus the hint line. It is also where the Help Centre can dock its launcher.'],
                ] },
                { h: 'Two ways to arrange panels', list: [
                    '**Classic** — one panel at a time, filling the window. This is how the program opens.',
                    '**Terminal** — the same panels as widgets you can place, size, tab and pin, with '
                    + 'layouts you can save. Switch with the Classic/Terminal control or **Ctrl+Alt+T**.',
                ] },
                { note: 'The rail, the status bar and the whole chrome can be hidden for a clean '
                    + 'screenshot or a focused session: **View ▸ Rail / Status bar / Zen mode** (**Alt+Z**).' },
            ],
            actions: [
                { label: 'Open the ☰ menu', kind: 'menu', value: '' },
                { label: 'Show me the hotkeys', kind: 'keys', value: '' },
                { label: 'Help Centre: shortcuts', kind: 'topic', value: 'work.keys' },
            ],
            related: ['work.terminal', 'work.menubar', 'work.keys'],
        },
        {
            id: 'start.engine', group: 'start', mode: 'both',
            title: 'Starting and stopping the engine',
            tags: ['engine', 'start', 'stop', 'restart', 'streaming', 'connected'],
            aliases: ['go live', 'begin streaming'],
            summary: 'The engine is the part that talks to the venue. Starting it subscribes the '
                + 'enabled instruments, streams their trades and order book, and feeds every panel on '
                + 'screen — nothing else in the program needs starting.',
            blocks: [
                { h: 'What the three buttons do', list: [
                    '**▶ Start** — subscribes the enabled instruments and begins streaming. The engine '
                    + 'pill turns green and uptime starts counting.',
                    '**■ Stop** — closes the connections. Panels keep their last values; anything that '
                    + 'falls back to demo data is labelled as such.',
                    '**⟳ Restart** — a stop and a start in one, and the way to apply a settings change '
                    + 'that says it needs one (**Ctrl+Alt+R**).',
                ] },
                { h: 'Which source it uses', p: 'The engine runs on whichever source is selected — the '
                    + 'exchange feed by default, or MetaTrader 5 / an Alpaca account if you configured '
                    + 'one. Switch it from **Data ▸ Source** or from the ☰ menu\'s Connections list; '
                    + 'the switch restarts the engine for you and says what happened.' },
                { h: 'What "demo data" means', p: 'With the engine stopped, panels that can invent a '
                    + 'plausible chart still do — clearly labelled, never passed off as live. A symbol '
                    + 'the app does not model gets an empty answer rather than invented numbers.' },
                { warn: 'The engine writes ticks to a local SQLite file while it runs. That is what makes '
                    + 'replay, the alert history and the trackers\' lookback work; it also means the file '
                    + 'grows. Retention prunes it automatically (*Data, files and storage*).' },
            ],
            actions: [
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Run the system check', kind: 'check', value: '' },
                { label: 'Watch the log', kind: 'view', value: 'logs' },
            ],
            related: ['start.sources', 'view.instruments', 'data.storage', 'fix.engine_error'],
        },
        {
            id: 'start.help', group: 'start', mode: 'both',
            title: 'Using this help system',
            tags: ['help', 'search', 'find', 'docs', 'f1', 'guide', 'autofill', 'suggestions'],
            aliases: ['help centre', 'search the help', 'documentation'],
            summary: 'The whole program, searchable from one box, in two depths: **Advanced user**, '
                + 'which shows everything including the under-the-hood topics, and **Simple**, which '
                + 'shows the safe subset with a system check at the top.',
            blocks: [
                { h: 'Finding things', list: [
                    'Type in the search box — results appear as you type, ranked with titles first, and '
                    + 'the box **autofills** with the topic, keyword or command you are most likely to '
                    + 'want. ↑ ↓ walk the suggestions, Enter takes one.',
                    'Every typed word has to match something, so two words narrow rather than widen. '
                    + 'A typo is repaired for you and the search says which word it used.',
                    'The box also searches the **program**: view names and menu commands are indexed '
                    + 'alongside the topics, so "send to monitor" or "reset" lands you on the right '
                    + 'instruction and the button that does it.',
                ] },
                { h: 'The two depths', table: [
                    ['Advanced user', 'Every topic. Under-the-hood material, the danger zone (reset, '
                        + 'prune, uninstall) with its cautions spelled out, and the diagnostics.'],
                    ['Simple', 'The same search engine and the same topics minus the ones that can bite: '
                        + 'advanced entries are hidden from the list and refused from the search with a '
                        + 'warning you can override. The system check sits at the top and only shows '
                        + 'what is not right.'],
                ] },
                { h: 'Getting to it', list: [
                    '**F1** opens the Help Centre from anywhere; the **Help** menu in the menu bar has '
                    + 'the same door plus the mode switch and the About card.',
                    '**Drop it to the status bar**: the Help Centre can dock a small launcher (with its '
                    + 'own search box) into the status bar along the bottom, so help is one click away '
                    + 'from every panel without covering your work. **Help ▸ Where help lives** switches '
                    + 'between the status bar, a floating button, or nowhere.',
                    'The same content is in the **Guide** view as a plain read-through, if you would '
                    + 'rather read than search.',
                ] },
                { note: 'Every topic that names a panel has a button that opens it, and every topic that '
                    + 'names a step has the step you would otherwise have to remember. The help is meant '
                    + 'to be used *while* working, not read first.' },
            ],
            actions: [
                { label: 'Open the file Guide', kind: 'view', value: 'guide' },
                { label: 'Show the shortcut map', kind: 'keys', value: '' },
                { label: 'Run the system check', kind: 'check', value: '' },
            ],
            related: ['work.keys', 'start.first_run', 'support.syscheck'],
        },
        {
            id: 'start.identity', group: 'start', mode: 'both',
            title: 'What this program is — and is not',
            tags: ['analytics layer', 'identity', 'what it is', 'broker', 'read-only', 'no orders',
                'data feeds', 'market data', 'beside your terminal'],
            aliases: ['what is modflow', 'is this a broker', 'can i trade here'],
            summary: 'ModFlow is an **analytics layer**: it reads the market in depth and sits beside '
                + 'whatever you execute in. It places no orders and holds no funds — deliberately, '
                + 'because that removes both the licences an execution venue needs and the risk of a '
                + 'half-built order path. Your terminal stays your terminal; this is the desk around it.',
            blocks: [
                { h: 'What it is', list: [
                    'Order-flow analytics in real time — footprint, cumulative delta, volume profile, '
                    + 'heatmap, depth, tape, trackers, alerts and replay — over the same live feed.',
                    'A second screen of context your terminal does not carry: news, calendar, '
                    + 'fundamentals, options and a trade journal in the same window as the order flow.',
                    'A free, local-first, keyless window on the market: pick a venue under **Data ▸ '
                    + 'Source**, or ride the terminal you already run (MT5, NinjaTrader 8), and '
                    + 'everything stays on this machine.',
                ] },
                { h: 'What it is not', list: [
                    'Not a broker and not an execution terminal — no order tickets, no positions, no '
                    + 'account to create. Feed logins you choose to store are read-only and stay in '
                    + 'your own config file.',
                    'Not a data vendor: the built-in venues (Bybit, Binance, Hyperliquid, OKX, Alpaca '
                    + 'crypto) are free public feeds. What a broker or exchange charges for its own '
                    + 'data is between you and them — exactly as with any terminal.',
                    'Not a black box: hover anything for its explanation (right-click pins the card), '
                    + 'and the whole program is open source and inspectable.',
                ] },
                { note: 'Said plainly, because every platform in this niche should say it: trade in your '
                    + 'terminal, analyse here. That division of labour is the one this program is '
                    + 'built around.' },
            ],
            related: ['start.sources', 'connect.venues', 'work.terminal'],
        },
        {
            id: 'start.sources', group: 'start', mode: 'both',
            title: 'Where the data comes from',
            tags: ['data source', 'bybit', 'binance', 'okx', 'hyperliquid', 'feed', 'free', 'api key'],
            aliases: ['feeds', 'market data', 'venues', 'source list'],
            summary: 'Six sources, four of them keyless public venue feeds. The default (Bybit) needs '
                + 'no account and gives trades, order-book depth and candles — everything the '
                + 'order-flow panels read.',
            blocks: [
                { h: 'The free venues', table: [
                    ['Bybit', 'The default. Public websocket: trades, order book, candles, plus the '
                        + 'optional 200-level book and liquidations.'],
                    ['Binance Futures', 'Public market data — trades, depth, candles.'],
                    ['OKX', 'Public market data — trades, depth, candles.'],
                    ['Hyperliquid', 'Public API — trades, book, candles.'],
                ] },
                { h: 'The two that need something of yours', table: [
                    ['MetaTrader 5', 'Uses **your** running MT5 terminal: indices, gold, FX and the '
                        + 'instruments a crypto venue does not list. Needs the terminal installed and '
                        + 'signed in (*MetaTrader 5 in this program*).'],
                    ['Alpaca', 'A US brokerage account (a free paper account is enough): US stocks, '
                        + 'ETFs, options, crypto, news and the market calendar. Publishes no order '
                        + 'book, so the depth views stay on the venue feed (*Linking an Alpaca account*).'],
                ] },
                { note: 'Switching source never touches your settings beyond that one field, and the '
                    + 'engine restarts itself so the change is real immediately. Which instruments a '
                    + 'source can actually serve is checked against the venue itself — Instruments '
                    + 'greys out the rest instead of streaming silence.' },
                { h: 'An exchange feed is crypto-only — by nature', p: 'Bybit, Binance, OKX and '
                    + 'Hyperliquid list crypto perpetuals. **No keyless venue carries indices, FX, '
                    + 'metals or CFDs**: a name like NQ1! or US100 needs MetaTrader 5 with your broker '
                    + 'signed in, and US equities need Alpaca. When a source cannot serve a symbol the '
                    + 'app says exactly that — and the **instrument look-up** (the symbol chip in the '
                    + 'Engine view, **Instrument look-up…** in the Data menu, or the button at the '
                    + 'top of Instruments) turns the refusal into the next step.' },
            ],
            actions: [
                { label: 'Switch source (☰ menu)', kind: 'menu', value: '' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Instruments', kind: 'view', value: 'instruments' },
            ],
            related: ['connect.venues', 'connect.mt5', 'connect.alpaca', 'view.instruments'],
        },

        /* ═══════════ Panels, one by one ═══════════ */
        {
            id: 'view.overview', group: 'panels', mode: 'both',
            title: 'Overview',
            tags: ['overview', 'session', 'summary', 'kpi', 'first panel'],
            summary: 'The session at a glance: last price, cumulative delta, tick and candle counts '
                + 'for the active instrument, plus the newest detections and the session table.',
            blocks: [
                { h: 'What to read', list: [
                    '**KPI cards** — last price, cumulative delta (buy volume minus sell volume for the '
                    + 'session), ticks, candles closed.',
                    '**Session summary** — the same numbers per instrument, so a silent symbol stands out.',
                    '**Latest signals** — the newest detections with their direction and grade.',
                    '**Market context** (when enabled) — venue funding, open interest, the long/short '
                    + 'account ratio, Fear & Greed, and headlines. All keyless, all fail-soft.',
                ] },
                { p: 'This is the panel to open first when you are not sure the program is alive: if '
                    + 'ticks and delta are moving here, everything downstream has data.' },
                { shot: 'help/overview-live.png', caption: 'A live session: KPI cards, the session summary and the context block.' },
            ],
            actions: [
                { label: 'Open Overview', kind: 'view', value: 'overview' },
                { label: 'Run the system check', kind: 'check', value: '' },
            ],
            related: ['view.watchlist', 'view.signals', 'fix.no_data'],
        },
        {
            id: 'view.chart', group: 'panels', mode: 'both',
            title: 'Chart',
            tags: ['chart', 'candles', 'timeframe', 'vwap', 'value area', 'delta', 'split candle'],
            summary: 'Candles with a delta histogram under them, the POC/VAH/VAL levels, signal '
                + 'markers, the VWAP band and the values of whatever studies are active at the '
                + 'crosshair bar.',
            blocks: [
                { h: 'The controls across the top', table: [
                    ['Timeframe', '1m · 5m · 15m · 1H · 4H · 1D — the bar size.'],
                    ['Range', 'How much history is in view: 1H · 4H · 1D · 1W · 1M.'],
                    ['Overlays', 'signal markers and the value-area lines on or off.'],
                    ['Bars', 'How each bar is drawn: plain **candles**, a **delta-tinted** body, a '
                        + '**split candle** (sell left, buy right), a **heat** body, or **wick only**.'],
                    ['Palette', 'The theme\'s green/red pair, or a two-hue set chosen and measured for '
                        + 'a colour-vision deficiency.'],
                ] },
                { h: 'Reading a split candle', p: 'The left half is sell-side volume, the right half '
                    + 'buy-side, so a bar that closes where it opened but carries three times the '
                    + 'buying is visible as a shape rather than inferred from numbers.' },
                { h: 'The data box', p: 'Under the chart: the values of every active study at the bar '
                    + 'your crosshair is on — the same panel that the Studies view parameterises.' },
                { shot: 'help/chart.png', caption: 'Candles with the delta lane, the POC/VAH/VAL levels and the VWAP band.' },
            ],
            actions: [
                { label: 'Open the Chart', kind: 'view', value: 'chart' },
                { label: 'Manage studies', kind: 'view', value: 'studies' },
                { label: 'Drawings', kind: 'view', value: 'chart' },
            ],
            related: ['view.studies', 'view.orderflow', 'work.drawings'],
        },
        {
            id: 'view.orderflow', group: 'panels', mode: 'both',
            title: 'Order Flow (footprint)',
            tags: ['footprint', 'order flow', 'bid ask', 'poc', 'value area', 'imbalance', 'profile shape'],
            summary: 'Per-price bid and ask volume for the session: the footprint. POC, value-area '
                + 'high/low and the profile\'s shape as KPI cards above the grid.',
            blocks: [
                { h: 'What is on the grid', p: 'Each row is a price level; each cell carries the volume '
                    + 'traded at the bid and at the ask for that level. The point of control is the '
                    + 'level with the most volume; the value area is the band holding the configured '
                    + 'share of the session\'s volume (70% by default).' },
                { h: 'The controls', table: [
                    ['imbalance', 'The rule that marks a row as imbalanced: **same price** (this row\'s '
                        + 'ask against this row\'s bid, the depth-map convention) or **diagonal** '
                        + '(this row\'s ask against the bid one tick below — the classic numbers-bars '
                        + 'convention).'],
                    ['ratio', 'How many times the opposing side counts as imbalanced. 3 means three '
                        + 'times.'],
                    ['calc', 'The calculated values for the newest bar, in the same vocabulary the '
                        + 'numbers-bars conventions use.'],
                    ['Rebuild profile', 'Recompute the session profile from the stored ticks.'],
                ] },
                { p: 'Drag to pan, scroll to zoom. The profile is built from the engine\'s own stored '
                    + 'ticks, so it can be rebuilt at any time without touching the feed.' },
            ],
            actions: [
                { label: 'Open Order Flow', kind: 'view', value: 'orderflow' },
                { label: 'Open the Engine view', kind: 'view', value: 'ofx' },
            ],
            related: ['view.ofx', 'view.profile', 'view.depth'],
        },
        {
            id: 'view.ofx', group: 'panels', mode: 'both',
            title: 'Engine (the order-flow engine view)',
            tags: ['engine', 'ofx', 'footprint matrix', 'dom', 'heat', 'sweeps', 'hud', 'ribbon', 'crosshair'],
            aliases: ['order flow engine', 'the engine view', 'heat behind the matrix'],
            summary: 'The deepest panel in the program: a split-candle footprint matrix painted over '
                + 'a live depth heat, with execution sweeps, a CVD ribbon locked to the same time '
                + 'axis, and a crosshair HUD that reads out the level under your cursor. The '
                + 'panel’s symbol chip opens a picker grouped **streaming now → enabled → '
                + 'configured → off**: choosing an instrument switches the engine to it (with '
                + 'the engine running, the same apply path the Instruments toggles use).',
            blocks: [
                { h: 'The three layers behind the matrix', list: [
                    '**Depth heat** — resting liquidity as a heat map behind the bars. Alpha decays '
                    + 'exponentially with the **lambda ms** control (α·e^(−t/λ), 500 ms by default), so '
                    + 'the heat shows how *recent* a wall is, not just that it existed.',
                    '**Footprint matrix** — each bar split into sell-side and buy-side volume per price '
                    + 'row, with diagonal imbalances marked. **R** sets the imbalance ratio (a row: '
                    + 'the ask here against the bid one row up, and the mirror) and **stack** how many '
                    + 'consecutive imbalanced rows count as a stacked imbalance.',
                    '**Executions** — the blocks that actually traded, sized by volume, with **min '
                    + 'block** hiding the small ones (the count of what is hidden sits beside it, so a '
                    + 'filter never quietly lies about the tape).',
                ] },
                { h: 'Reading it', table: [
                    ['Sweeps', 'One aggressor taking several levels in one push — drawn as a corridor, '
                        + 'scaled by **sweepC**.'],
                    ['CVD ribbon', 'Cumulative delta along the bottom, on the same X transform as the '
                        + 'matrix, so a divergence is a shape rather than two charts to compare.'],
                    ['Crosshair HUD', 'The readout panel at the right names the bar, the level, the '
                        + 'volume and the delta under the cursor.'],
                    ['Legend', 'The collapsible panel under the stage names every colour, the layout, '
                        + 'and every data dictionary entry — generated from the renderer\'s own theme, '
                        + 'so it cannot drift from what is drawn.'],
                ] },
                { h: 'Controls worth knowing', list: [
                    '**Snap to live** (● live) follows the newest bar; scrolling away releases it and a '
                    + 'floating chip brings you back. Double-clicking the stage fits the whole session.',
                    '**symbol** takes any name — a market name, a broker spelling or the suite’s own row — '
                    + 'and the chip beside it says what the server makes of it: **streaming**, **enabled**, '
                    + '**not enabled**, **available from your broker**, or **unknown**. `find` (or the chip) '
                    + 'opens the look-up: the reason, the close matches, and the button that fixes it '
                    + '(enable & restart, start the engine, map the broker symbol on MT5). A symbol nothing '
                    + 'can stream is answered there instead of leaving an empty stage.',
                    '**VA %** sets the share of a bar that counts as its value area.',
                    '**bars** chooses the expression (default · delta tint · split candle · heat body · '
                    + 'wick + footprint · candles), **palette** the colour vocabulary (theme or a measured '
                    + 'colour-blind-safe pair) and **ramp** the depth-heat ramp — both ramps are '
                    + 'monotone in luminance, so magnitude never rides on hue alone.',
                    '**scheme** writes the whole heat recipe in one go — *balanced depth* (as shipped), '
                    + '*wall hunt* (only the top 2% saturate, the small orders unpainted), *thin-book '
                    + 'detail* (the middle lifted), *quiet book* (the bottom 15% unpainted) — then '
                    + '**contrast** and **floor** dial the result; a hand-edited dial reads *custom*. '
                    + '**⇉ global** writes these dials to every heat surface; the shared colour ceiling '
                    + 'lives in Settings ▸ Depth heat.',
                    '**smooth** adds vertical smoothing while the rows compress (auto · manual · '
                    + 'none, display only), and **auto-candles** degrades the matrix to plain '
                    + 'candles once a column falls under the text threshold — the saved bar mode '
                    + 'is untouched either way.',
                    '**The value scale is an object** — right-click it for *Auto* / *Free* (drag '
                    + 'the rail to move prices) / *Reset scales*; **Ctrl+Shift+R** resets price + '
                    + 'time from the keyboard.',
                    '**LOD** names the level of detail in use: when too many rows or bars are in view, '
                    + 'ticks group before profiles are dropped, so the panel stays honest about what '
                    + 'it is showing.',
                ] },
                { shot: 'help/engine-selection.png',
                  caption: 'A selection inside the engine: the HUD and the readout carry the measurement out of the chart.' },
                { shot: 'help/engine-hidden-blocks.png',
                  caption: 'The hidden-block count sits beside the min-block floor — a filter that says what it removed.' },
            ],
            actions: [
                { label: 'Open the Engine', kind: 'view', value: 'ofx' },
                { label: 'Open the Heatmap', kind: 'view', value: 'heatmap' },
                { label: 'Show the legend', kind: 'legend', value: '' },
            ],
            related: ['view.heatmap', 'view.cvd', 'view.orderflow', 'work.cursor'],
        },
        {
            id: 'view.heatmap', group: 'panels', mode: 'both',
            title: 'Market depth heatmap',
            tags: ['heatmap', 'liquidity', 'walls', 'spoof', 'stacking', 'depth map', 'resting size'],
            aliases: ['depth map', 'liquidity map', 'market depth heatmap'],
            summary: 'Resting liquidity over time: what was on the book, level by level, as the market '
                + 'moved through it. Executed aggression is drawn as bubbles; purple marks size that '
                + 'was pulled, cyan size that was stacked.',
            blocks: [
                { h: 'How to read the picture', list: [
                    'One row per price level, one column per time bucket. Brightness is resting size.',
                    '**Bubbles** are prints that traded there — the moment a wall met real aggression.',
                    '**Purple** marks levels where size was removed (pulled) near the price: a spoof '
                    + 'candidate, not a verdict.',
                    '**Cyan** marks levels where size was added in one go — stacking.',
                    'Rows that hold their brightness for a long time are walls; the **fresh walls** '
                    + 'table lists the biggest ones with their age and distance from price.',
                ] },
                { h: 'Controls', table: [
                    ['Window', '2 · 4 · 8 · 15 minutes of history in view.'],
                    ['Rows', '120 · 200 · 300 price rows: fewer rows means coarser levels.'],
                    ['trades', 'The execution bubbles on or off.'],
                    ['wall age', 'Tints levels the engine has watched hold past its wall-age threshold '
                        + '(two minutes by default), so age is visible without reading the table.'],
                    ['spoof/stack', 'The event markers on or off.'],
                    ['auto', 'Follows the newest column; turning it off freezes the view so you can '
                        + 'study what just happened.'],
                    ['Heat (scheme · contrast · floor)', 'The depth-heat recipe: a named scheme '
                        + '(balanced · wall hunt · thin-book · quiet) writes the ceiling, floor and '
                        + 'contrast together, and the dials then tune it — a hand-edited dial reads '
                        + '*custom*. The **floor** hides sizes below it, so the map draws where size '
                        + 'IS instead of a speckle of everything.'],
                    ['Smooth', 'Vertical smoothing while the map’s rows compress (auto · manual · '
                        + 'none); display only — *none* keeps the raw cells.'],
                    ['⇉ global', 'Writes this view’s heat dials to every heat surface — the Engine '
                        + 'and the Heatmap.'],
                ] },
                { h: 'Selected regions are measurements', p: 'Drag a rectangle over the map and the '
                    + 'selection carries its own readout: volume traded inside it, how much was pulled, '
                    + 'how much stacked. The same selection can create an alert on the level, or export '
                    + 'the region to the clipboard as an image and a CSV.' },
                { shot: 'help/heatmap-live.png',
                  caption: 'A live liquidity map — 240 time buckets over 200 price rows.' },
                { shot: 'help/heatmap-wall-age.png',
                  caption: 'The wall-age tint: levels held past the threshold are tinted for as long as they hold.' },
            ],
            actions: [
                { label: 'Open the Heatmap', kind: 'view', value: 'heatmap' },
                { label: 'Open the Engine', kind: 'view', value: 'ofx' },
                { label: 'Trackers', kind: 'view', value: 'trackers' },
            ],
            related: ['view.ofx', 'view.depth', 'view.trackers', 'view.alerts'],
        },
        {
            id: 'view.inbox', group: 'panels', mode: 'both',
            title: 'Inbox',
            tags: ['inbox', 'notifications', 'alert history', 'do not disturb', 'unread', 'tiles'],
            summary: 'Every alert the engine fired, kept as tiles \u2014 categorised, filterable and '
                + 'act-on-click: opening a tile marks it read and opens the panel that can show its evidence.',
            blocks: [
                { h: 'How it differs from Alerts', p: 'Alerts is the routing table \u2014 which rules exist '
                    + 'and where each one pushes. The Inbox is the record \u2014 what actually fired, newest '
                    + 'first, with its kind, instrument and message. Both read the same firings; nothing '
                    + 'is duplicated and nothing is invented.' },
                { h: 'Categories, priority, do not disturb', p: 'Chips filter by what the rule watches '
                    + '\u2014 tape, book, structure, execution. "Priority first" sorts critical above warning '
                    + 'above info. Do not disturb keeps the record running but silences the badge.' },
            ],
            actions: [
                { label: 'Open the Inbox', kind: 'view', value: 'inbox' },
                { label: 'Open Alerts', kind: 'view', value: 'alerts' },
            ],
            related: ['view.alerts', 'view.heatmap', 'view.tape'],
        },
        {
            id: 'view.depth', group: 'panels', mode: 'both',
            title: 'Market depth (ladder)',
            tags: ['depth', 'order book', 'ladder', 'imbalance', 'spread', 'best bid'],
            summary: 'The live order book as a ladder: size resting at each level, the spread between '
                + 'the best bid and ask, and the imbalance between the two sides.',
            blocks: [
                { h: 'What it is for', p: 'The depth map is history; this panel is the book right now. '
                    + 'Use it to see where the nearest walls are, how far the spread is, and whether '
                    + 'the book is lopsided before you read a footprint bar.' },
                { note: 'Depth needs a source that publishes it. The exchange feeds do; an Alpaca '
                    + 'account does not (it publishes no book), which is why this panel stays on the '
                    + 'venue feed even when the trading source is Alpaca.' },
            ],
            actions: [
                { label: 'Open Depth', kind: 'view', value: 'depth' },
                { label: 'Open the Heatmap', kind: 'view', value: 'heatmap' },
            ],
            related: ['view.heatmap', 'view.tape', 'connect.venues'],
        },
        {
            id: 'view.tape', group: 'panels', mode: 'both',
            title: 'Time & Sales',
            tags: ['tape', 'time and sales', 'prints', 'prints list', 'scrolling', 'hold scroll'],
            aliases: ['t&s', 'tick list'],
            summary: 'Every execution, newest first, with large prints highlighted and a size filter. '
                + 'The list is the raw material every other panel summarises.',
            blocks: [
                { h: 'Reading the tape', p: 'Side, size, price and time per print. Big trades are '
                    + 'highlighted against a threshold derived from the session\'s own distribution, '
                    + 'so "big" means big for this instrument and this session rather than a fixed '
                    + 'number.' },
                { h: 'The list holds your place', p: 'When new prints arrive while you are reading, '
                    + 'the tape adds them **without moving your scroll position** — the reader keeps '
                    + 'the row they were on. A held strip says so; scrolling back to the top releases '
                    + 'it and resumes following the newest print.' },
                { shot: 'help/tape-held.png',
                  caption: 'A held tape: new prints arrive, the reader keeps the row they were reading.' },
                { h: 'The size filter', note: 'The minimum size filter is inclusive of zero on purpose: '
                    + 'raising it hides small prints, and the panel says how many it is hiding so a '
                    + 'quiet tape and a filtered tape never look the same.' },
            ],
            actions: [
                { label: 'Open Time & Sales', kind: 'view', value: 'tape' },
                { label: 'Trackers', kind: 'view', value: 'trackers' },
            ],
            related: ['view.trackers', 'view.ofx', 'work.cursor'],
        },
        {
            id: 'view.marketwatch', group: 'panels', mode: 'both',
            title: 'Market Watch',
            tags: ['market watch', 'bid', 'ask', 'daily change', 'board', 'quotes', 'spread',
                'symbols', 'live', 'real time', 'pause', 'freeze'],
            aliases: ['the board', 'quote board', 'all symbols'],
            summary: 'The source’s own board: every instrument it lists, with live bid, ask and daily '
                + 'change — the platform’s Market Watch. On MetaTrader 5 this panel mirrors the '
                + 'terminal’s **own** Market Watch (the symbols you keep visible there), read-only.',
            blocks: [
                { h: 'What each source shows', table: [
                    ['Bybit', 'The whole perpetual board from one cached snapshot — hundreds of '
                        + 'symbols, refreshed every few seconds.'],
                    ['MetaTrader 5', 'The terminal’s own Market Watch, mirrored: exactly the symbols '
                        + 'visible in your terminal (35 on the demo account) with live quotes off the '
                        + 'running terminal. The panel never writes to the terminal — browsing it '
                        + 'cannot change your watch list.'],
                    ['NinjaTrader 8', 'The terminal’s master instrument list; live bid/ask arrives for '
                        + 'the instruments the bridge is subscribed to (open one from the Engine panel).'],
                ] },
                { h: 'Reading it', list: [
                    '**Arrows and colour** — a green ↗ or red ↘ with the day’s change in percent, the '
                    + 'same reading as the terminal’s own Market Watch.',
                    '**— instead of a price** — that source does not quote this row (yet); the footer '
                    + 'sentence always says which venue answered and what it could not give.',
                    '**The board is live** — it re-reads about every 1.5 seconds while the panel '
                        + 'is visible; a price cell tints green or red with its last move (and flashes), '
                        + 'and the badge beside the title shows how fresh the read is.',
                    '**Pause** freezes the board exactly as it stands — a read that lands while '
                        + 'paused is dropped — and **Resume** snaps it current; **Refresh** takes one '
                        + 'fresh read even while paused. **Filter** narrows as you type.',
'**Right-click a row** — the same look-up verdict the Instruments table gives, '
                    + 'without leaving the board.',
                ] },
                { note: 'The source picker defaults to the engine’s source; switching it here only '
                    + 'changes what this board mirrors, never what the engine streams.' },
            ],
            actions: [
                { label: 'Open Market Watch', kind: 'view', value: 'marketwatch' },
                { label: 'Instruments (what the engine streams)', kind: 'view', value: 'instruments' },
                { label: 'MetaTrader 5', kind: 'topic', value: 'connect.mt5' },
            ],
            related: ['view.instruments', 'connect.mt5', 'view.overview'],
        },
        {
            id: 'view.trackers', group: 'panels', mode: 'both',
            title: 'Order-flow trackers',
            tags: ['trackers', 'iceberg', 'sweeps', 'stop runs', 'liquidations', 'big trades', 'imbalance ladder', 'zones'],
            summary: 'The detections that need more than one print to see: inferred icebergs, sweeps, '
                + 'the imbalance ladder, stacked imbalances, big-trade zones, stop runs and '
                + 'liquidations — each in its own table, each with the numbers behind the verdict.',
            blocks: [
                { h: 'The tables', table: [
                    ['Icebergs (inferred)', 'Repeated equal prints at one price. Marked **inferred** '
                        + 'because no public venue feed publishes true order-level (MBO) data — this is '
                        + 'the honest inference from the tape, with refills, modal size and lifetime.'],
                    ['Sweeps', 'One aggressor crossing several levels: side, levels, size, aggressor '
                        + 'count, corridor width and duration.'],
                    ['Imbalance ladder', 'Levels where one side dwarfs the other, with the ratio, so '
                        + 'you can see the book leaning in real time.'],
                    ['Stacked imbalances', 'Consecutive imbalanced levels in the same direction — the '
                        + '150% rule, where the bid at a level is compared with the ask one level above '
                        + '(and the mirror).'],
                    ['Big-trade zones', 'Clusters of large prints by price band: buy, sell, total, '
                        + 'delta and the last time each traded.'],
                    ['Stop runs', 'Fast range expansion with a volume burst, confirmed by liquidation '
                        + 'clusters. Also **inferred**, and labelled as such.'],
                    ['Liquidations', 'Forced closes published by the venue.'],
                ] },
                { h: 'Thresholds', p: 'The big-trade threshold is derived from the session, and the '
                    + 'panel prints the number it is using, so a sudden burst of "big trades" is a '
                    + 'change in the market rather than a change in the filter.' },
            ],
            actions: [
                { label: 'Open Trackers', kind: 'view', value: 'trackers' },
                { label: 'Time & Sales', kind: 'view', value: 'tape' },
                { label: 'Signals', kind: 'view', value: 'signals' },
            ],
            related: ['view.tape', 'view.signals', 'view.cvd'],
        },
        {
            id: 'view.cvd', group: 'panels', mode: 'both',
            title: 'Cumulative volume delta (CVD)',
            tags: ['cvd', 'cumulative delta', 'delta', 'divergence', 'slope', 're-anchor'],
            aliases: ['cumulative volume delta', 'cvd pro'],
            summary: 'Cumulative delta against price, so you can see whether the buying is actually '
                + 'moving the market: session CVD, short-window deltas, the slope per bucket, and the '
                + 'divergences the engine detected.',
            blocks: [
                { h: 'What to look for', list: [
                    '**Price up, CVD flat or down** — the rise is not being paid for by aggressive '
                    + 'buying. The divergences table names when it happened and how strong it was.',
                    '**Slope per bucket** — the rate, not the level: a flattening slope after a trend '
                    + 'often precedes the turn.',
                    '**Δ 1m / Δ 5m** — the recent window, which is what a scalp actually reads.',
                ] },
                { h: 'Re-anchor', p: 'Resets the cumulative baseline to the current point, so a long '
                    + 'session\'s drift does not swamp what is happening now. The session KPI keeps '
                    + 'the absolute number; the chart shows the anchored series.' },
            ],
            actions: [
                { label: 'Open CVD', kind: 'view', value: 'cvd' },
                { label: 'Open the Engine', kind: 'view', value: 'ofx' },
            ],
            related: ['view.ofx', 'view.signals', 'view.strategy'],
        },
        {
            id: 'view.profile', group: 'panels', mode: 'both',
            title: 'Market profile (TPO)',
            tags: ['profile', 'tpo', 'market profile', 'poc', 'value area', 'initial balance', 'single prints'],
            summary: 'Time-price opportunity: which prices the market accepted, by 30-minute bracket. '
                + 'POC, value area, initial balance, range extension and single prints.',
            blocks: [
                { h: 'What the reads mean', list: [
                    '**POC** — the price with the most time traded: the fairest price of the session.',
                    '**Value area** — where ~70% of the time was spent: acceptance. Price outside it is '
                    + 'either exploring or rejecting.',
                    '**Initial balance** — the first brackets\' range. Extension beyond it is the market '
                    + 'looking for new business.',
                    '**Single prints** — prices touched by only one bracket. They mark fast moves and '
                    + 'often act as the levels a market returns to test.',
                ] },
                { p: 'The ladder draws the letter count per price; **Session reads** beside it words the '
                    + 'shape (balanced, trend, double distribution, P-shape and so on) rather than '
                    + 'leaving you to eyeball it.' },
            ],
            actions: [
                { label: 'Open Profile', kind: 'view', value: 'profile' },
                { label: 'Order Flow', kind: 'view', value: 'orderflow' },
            ],
            related: ['view.orderflow', 'view.frames', 'view.strategy'],
        },
        {
            id: 'view.frames', group: 'panels', mode: 'both',
            title: 'Frames (non-time bars)',
            tags: ['frames', 'range bars', 'renko', 'reversal', 'tick bars', 'volume bars', 'non-time'],
            aliases: ['non-time bars', 'range bar', 'renko chart'],
            summary: 'Bars built from activity rather than the clock: Range, Renko, Reversal, Tick and '
                + 'Volume. Same analytics, different sampling — useful when a quiet hour is padding '
                + 'the chart with nothing.',
            blocks: [
                { h: 'Which to use', table: [
                    ['Range', 'A new bar every N ticks of movement. Removes time; keeps shape.'],
                    ['Renko', 'A new brick only when price moves a brick size. Smooths noise, loses '
                        + 'intra-brick detail.'],
                    ['Reversal', 'Bars from reversals of a set size — reads swings rather than time.'],
                    ['Tick', 'A new bar every N ticks, however long it takes. The most honest read of '
                        + 'activity on a quiet instrument.'],
                    ['Volume', 'A new bar every N contracts. Volume is the clock.'],
                ] },
                { p: 'The **Recent bars** table carries the same numbers per bar (open/high/low/close, '
                    + 'volume, delta, tick count and the wall-clock duration), which is where the '
                    + 'difference between activity time and clock time becomes obvious.' },
            ],
            actions: [
                { label: 'Open Frames', kind: 'view', value: 'frames' },
                { label: 'Chart', kind: 'view', value: 'chart' },
            ],
            related: ['view.chart', 'view.profile'],
        },
        {
            id: 'view.studies', group: 'panels', mode: 'both',
            title: 'Studies (indicator modules)',
            tags: ['studies', 'indicator', 'study', 'module', 'parameters', 'data box'],
            aliases: ['indicators', 'study library'],
            summary: 'The indicator layer: add, parameterise and remove studies; they draw on the Chart '
                + 'and report their values in its data box. Save a whole set as a **collection** '
                + '(“Saved setups” in the view) and swap indicator setups in one click.',
            blocks: [
                { h: 'How it works', list: [
                    'Pick a study from the library, set its parameters, and it is drawn on the chart '
                    + 'with its values reported at the crosshair bar.',
                    'The **active** set is what draws; the panel lists them with their parameters '
                    + 'side by side, so comparing two settings is a read rather than a memory test.',
                    'Parameters are stored in your config file, so a study arrangement survives a '
                    + 'restart.',
                ] },
                { note: 'Studies are evaluated on this machine, on the data this panel already has — '
                    + 'adding one never costs a feed subscription.' },
            ],
            actions: [
                { label: 'Open Studies', kind: 'view', value: 'studies' },
                { label: 'Open the Chart', kind: 'view', value: 'chart' },
            ],
            related: ['view.chart', 'under.architecture'],
        },
        {
            id: 'view.signals', group: 'panels', mode: 'both',
            title: 'Signals',
            tags: ['signals', 'detections', 'grade', 'entry', 'stop', 'target'],
            summary: 'The pattern detections as cards: what was detected, in which direction, how '
                + 'strongly, with the entry, stop and target levels the pipeline derives.',
            blocks: [
                { h: 'What a card means', p: 'A single card is one detection — absorption, initiative, '
                    + 'sweep, exhaustion or divergence — with its direction, a grade, and the levels '
                    + 'that follow from the level it fired at. The badge on the rail counts the ones '
                    + 'you have not looked at yet.' },
                { note: 'A signal is a reading of the tape, not advice. The threshold for what counts '
                    + 'as a signal is yours to set (Settings ▸ signal thresholds).' },
            ],
            actions: [
                { label: 'Open Signals', kind: 'view', value: 'signals' },
                { label: 'Performance', kind: 'view', value: 'performance' },
                { label: 'Strategy pipeline', kind: 'view', value: 'strategy' },
            ],
            related: ['view.strategy', 'view.performance', 'view.trackers'],
        },
        {
            id: 'view.strategy', group: 'panels', mode: 'both',
            title: 'Strategy pipeline',
            tags: ['strategy', 'checklist', 'methodology', 'microstructure', 'state machine'],
            summary: 'The state machine, out loud: which conditions of the trading methodology are met '
                + 'right now, which are still waiting, and why — beside the microstructure readings '
                + 'the pipeline is watching.',
            blocks: [
                { h: 'The checklist', p: 'The pipeline walks qualified level → absorption → initiative '
                    + 'confirmation → momentum trail, and this panel shows that walk as a list. Each '
                    + 'step says whether it is satisfied and, when it is not, what it is waiting for.' },
                { h: 'Microstructure beside it', p: 'The panel next to the checklist carries the '
                    + 'readings the gates depend on, so a stalled pipeline is diagnosable rather than '
                    + 'mysterious: this is the panel to open when nothing has fired for an hour and you '
                    + 'want to know whether the market is quiet or a threshold is wrong.' },
            ],
            actions: [
                { label: 'Open Strategy', kind: 'view', value: 'strategy' },
                { label: 'Signals', kind: 'view', value: 'signals' },
                { label: 'Tune thresholds', kind: 'view', value: 'settings' },
            ],
            related: ['view.signals', 'view.performance', 'view.instruments'],
        },
        {
            id: 'view.performance', group: 'panels', mode: 'both',
            title: 'Performance (journal)',
            tags: ['performance', 'journal', 'outcomes', 'stats', 'session'],
            summary: 'The journal of this session\'s signals and what happened after them — the '
                + 'panel that tells you whether the current thresholds are producing anything worth '
                + 'watching.',
            blocks: [
                { p: 'Every signal the pipeline produced is tracked to its outcome, so the reading is '
                    + 'of the actual tape this session rather than of a backtest. Use it after tuning '
                    + 'thresholds: change one number, then read the journal rather than trusting the '
                    + 'change felt right.' },
            ],
            actions: [
                { label: 'Open Performance', kind: 'view', value: 'performance' },
                { label: 'Signals', kind: 'view', value: 'signals' },
            ],
            related: ['view.signals', 'view.alerts', 'view.replay'],
        },
        {
            id: 'view.journal', group: 'panels', mode: 'both',
            title: 'Journal',
            tags: ['journal', 'trades', 'statistics', 'statement', 'win rate', 'profit factor', 'sharpe'],
            aliases: ['trade journal', 'performance report', 'statement'],
            summary: 'The trades the app has recorded — simulated sessions and anything else that '
                + 'writes the journal table — with their statistics, a note per trade, and a '
                + 'broker-style statement you can write out and send.',
            blocks: [
                { h: 'The figures', list: [
                    'Trades, win rate, profit factor, average R and the maximum drawdown, all '
                    + 'computed server-side from the journal table (nothing here is estimated).',
                    'The daily table is P&L in **ticks** — points of the instrument — because that is '
                    + 'the unit the app records; multiply by your own value per tick.',
                ] },
                { h: 'Working with it', list: [
                    'Click a row to select it, write a note, then **Save note**.',
                    '**Export HTML statement** writes a self-contained file (summary, daily table, '
                    + 'every trade) into your exports folder — the shape brokers send, and readable '
                    + 'in any browser with nothing installed.',
                    'A simulated session from the Replay view lands here through **End & save to journal**.',
                ] },
            ],
            actions: [
                { label: 'Open Journal', kind: 'view', value: 'journal' },
                { label: 'Open the exports folder', kind: 'folder', value: 'exports' },
            ],
            related: ['view.replay', 'view.performance'],
        },
        {
            id: 'view.calendar', group: 'panels', mode: 'both',
            title: 'Economic calendar',
            tags: ['calendar', 'events', 'news', 'macro', 'alerts', 'impact'],
            aliases: ['economic calendar', 'releases', 'macro events'],
            summary: 'This week\'s scheduled releases by currency and impact — and, if you switch it '
                + 'on, an alert before the high-impact ones reach the market.',
            blocks: [
                { h: 'What you are looking at', list: [
                    'One keyless source: **Forex Factory\'s public weekly calendar JSON**. It is '
                    + 'cached for four hours; when it cannot be reached the panel says so and shows '
                    + 'the last good copy marked **STALE** rather than inventing dates.',
                    'The **window** and **minimum impact** filters are yours; the currency box takes '
                    + 'a list like `USD,EUR`.',
                ] },
                { h: 'Alerts', list: [
                    'Switch on **alerts ahead of high-impact events** and set the lead time; the '
                    + 'engine checks every five minutes and sends through the channels already '
                    + 'configured in Settings (Telegram, ntfy, email).',
                    'Each event alerts **once**: the key is remembered, so a restart does not repeat '
                    + 'yesterday\'s news.',
                ] },
                { note: 'A calendar is a schedule, not a promise: times are the venue\'s own and '
                    + 'revisions happen. The panel never edits the feed.' },
            ],
            actions: [
                { label: 'Open Calendar', kind: 'view', value: 'calendar' },
                { label: 'Alert channels', kind: 'view', value: 'settings' },
            ],
            related: ['view.news', 'view.alerts'],
        },
        {
            id: 'view.replay', group: 'panels', mode: 'both',
            title: 'Replay',
            tags: ['replay', 'recorded', 'backtest', 'speed', 'seek', 'play'],
            aliases: ['market replay', 'playback'],
            summary: 'Re-run recorded ticks (or the venue\'s recent tape) through the same analytics '
                + 'the live engine uses, at any speed — no broker, no risk, and the panels rebuild as '
                + 'it plays.',
            blocks: [
                { h: 'Loading a session', list: [
                    'Pick the instrument, then the source: **Recorded ticks (SQLite)** uses this app\'s '
                    + 'own history, **Exchange tape** uses the venue\'s most recent 1000 trades when '
                    + 'there is no local history yet.',
                    'Set **from** and **to** in minutes ago, then **Load session**.',
                ] },
                { h: 'Transport', list: [
                    '**▶ Play / ⏸ Pause / ■ Stop**, and a speed slider from very slow to 500×.',
                    'The position slider seeks anywhere in the loaded session; the KPI row shows '
                    + 'events loaded, position, the replay clock and the mode.',
                    '**Space** plays and pauses, **,** and **.** seek back and forward 2%.',
                ] },
                { h: 'The simulated account', list: [
                    'Place **market, limit or stop** orders with an optional stop loss and take '
                    + 'profit. The account consumes the same prints the replay delivers: a market '
                    + 'order fills at the next print, a limit when a print trades through it — the '
                    + 'fills are the tape\'s, never an invented price.',
                    '**Flatten** closes at the last print; **End & save to journal** writes the '
                    + 'closed trades into the Journal view.',
                ] },
                { note: 'Replay feeds the Heatmap, Trackers, CVD, Profile and Frames views while it '
                    + 'runs — the point of replaying through the same pipeline is that the panels '
                    + 'behave as they do live.' },
            ],
            actions: [
                { label: 'Open Replay', kind: 'view', value: 'replay' },
                { label: 'Data storage', kind: 'topic', value: 'data.storage' },
            ],
            related: ['data.storage', 'view.heatmap', 'view.frames'],
        },
        {
            id: 'view.alerts', group: 'panels', mode: 'both',
            title: 'Alerts',
            tags: ['alerts', 'rules', 'notifications', 'phone', 'telegram', 'history', 'detections'],
            aliases: ['alert rules', 'notify me'],
            summary: 'Rules over every detection the engine makes. A rule says what to watch, how big '
                + 'or how often it must be, and where it goes — on screen, to a sound, and out to '
                + 'Telegram, ntfy, email or a webhook if you configured one.',
            blocks: [
                { h: 'The three tables', table: [
                    ['Alert log', 'What fired, when, on which instrument, and the value that tripped it.'],
                    ['Rules', 'The rule list, each in words rather than raw parameters, with an inline '
                        + 'editor. **+ New rule** starts one by hand; rules created from the heatmap\'s '
                        + 'alert buttons carry an `hm-` id and can be filtered out.'],
                    ['History', 'Detections persisted to disk (when history is enabled), so the log '
                        + 'survives a restart.'],
                ] },
                { h: 'Getting alerts off the machine', p: 'A rule only leaves this computer if a '
                    + 'channel is configured and the rule is ticked for it. Telegram and ntfy are both '
                    + 'free; email and webhook are there for a paper trail. See *Where alerts go*.' },
                { h: 'Sound', p: 'The sound switch on this panel drives the trade-audio engine (its '
                    + 'own settings live in **Settings ▸ Trade audio**): prints above your size '
                    + 'threshold play a tone, so you can work with the chart covered.' },
            ],
            actions: [
                { label: 'Open Alerts', kind: 'view', value: 'alerts' },
                { label: 'Alert channels', kind: 'topic', value: 'connect.channels' },
                { label: 'Trade audio', kind: 'topic', value: 'work.audio' },
            ],
            related: ['connect.channels', 'work.audio', 'view.trackers', 'view.heatmap'],
        },
        {
            id: 'view.instruments', group: 'panels', mode: 'both',
            title: 'Instruments',
            tags: ['instruments', 'symbols', 'enable', 'tick size', 'subscription', 'validate'],
            aliases: ['symbol list', 'what is streaming'],
            summary: 'What the engine subscribes to. Tick the instruments you want; unsupported feeds '
                + 'are greyed out rather than silently streaming nothing — and **Look up an '
                + 'instrument…** answers any name you type (a market name, a broker spelling, or '
                + 'one of the suite’s own rows) before you tick anything. Ticking **On** saves itself and applies — with the engine running the panel restarts it right then (the same path as **Enable & restart**), so nothing here waits for a save button. Picking an instrument in the top bar moves every panel — and starts the engine when it is stopped (the engine pill and the progress bar narrate it).',
            blocks: [
                { h: 'The controls', table: [
                    ['Validate against Bybit', 'Asks the venue which of these symbols it actually lists, '
                        + 'so a typo is caught here instead of showing up as a dead panel later.'],
                    ['Enable all supported', 'Ticks everything the current source can serve — the fast '
                        + 'way to a broad watchlist.'],
                    ['Clear', 'Un-ticks everything. The engine then streams nothing, which the system '
                        + 'check will tell you about.'],
                    ['The On toggle', 'Saves the choice to your config the moment it flips. '
                        + 'With the engine running, the panel restarts it and narrates when the '
                        + 'change is live; with the engine stopped, the tick waits for the next '
                        + 'Start — either way you never hunt for a save.'],
                ] },
                { h: 'Tick size matters', p: 'Every analytics module works in price ticks. Instruments '
                    + 'imported from a venue carry the venue\'s real tick size; a guessed one would '
                    + 'make "three ticks away" mean the wrong distance in every detector.' },
                { h: 'Look a name up before you tick it', steps: [
                    { t: 'Type the name you know', d: 'NQ1!, US100, USTEC, GOLD — the look-up '
                        + 'translates market names and broker spellings onto the suite’s own rows.' },
                    { t: 'Read the sentence', d: 'It says whether the symbol is streaming, enabled, '
                        + 'switched off, available from your venue, or impossible on the current '
                        + 'source — in the same words the engine uses.' },
                    { t: 'Press the button it offers', d: '**Enable & restart** / **Add & restart** '
                        + 'writes the config and rebuilds the engine; **Open Instruments** takes you '
                        + 'to the table. Nothing is ever added without the venue confirming it.' },
                ] },
                { note: 'A change here **saves itself**: with the engine running the panel restarts '
                    + 'it and says when the change is live — with it stopped the tick is written '
                    + 'and waits for Start. **Enable & restart** stays for the look-up lane, and '
                    + 'the top bar\'s ⟳ does a full restart any time.' },
            ],
            actions: [
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Open the Engine (the look-up lives there)', kind: 'view', value: 'ofx' },
                { label: 'Data sources', kind: 'topic', value: 'start.sources' },
            ],
            related: ['view.instruments', 'connect.mt5_map', 'start.engine'],
        },
        {
            id: 'view.alpaca', group: 'panels', mode: 'both',
            title: 'Alpaca (broker account)',
            tags: ['alpaca', 'broker', 'stocks', 'options', 'paper', 'account', 'keys'],
            aliases: ['brokerage', 'us stocks', 'link account'],
            summary: 'Optional: link a US brokerage account for stocks, ETFs, options and crypto, plus '
                + 'its news and the market calendar. A paper account is free and needs only an email.',
            blocks: [
                { h: 'What it adds', list: [
                    'A real-time US equity tape (IEX on the free plan) and 15-minute-delayed '
                    + 'full-market history.',
                    'The option chain (open it from the command palette with **Ctrl+Shift+Enter** on a '
                    + 'row), positions and portfolio history.',
                    'Benzinga news and the market calendar.',
                ] },
                { warn: 'Alpaca publishes trades, quotes and bars — **no order book**. The heatmap, the '
                    + 'depth ladder and the intent reader need depth, so they stay on the venue feed '
                    + 'even when Alpaca is your trading source. The app labels which feed each panel is '
                    + 'showing.' },
                { p: 'The step-by-step for creating the keys is in the walkthrough: **Linking an Alpaca '
                    + 'account**. Keys live in your local config file, are never displayed back, and are '
                    + 'sent only to Alpaca.' },
                { h: 'Your keys stay saved — nothing to re-enter', list: [
                    'Once **Validate & save** reports the account linked, the key pair is stored. After '
                    + 'a restart the card shows the stored key id (masked) and the secret field says '
                    + '*“saved — type to replace”*: leave both fields empty and nothing is '
                    + 'changed.',
                    '**Test saved keys** asks Alpaca to confirm the stored pair without retyping '
                    + 'anything — that is the button to press when you only want to check.',
                    'Saving re-checks the keys and **keeps every other setting**; the environment '
                    + '(paper/live) and the feed selector are stored the same way.',
                    'To remove the pair entirely use **Remove stored keys** — that is the only '
                    + 'action that clears them.',
                ] },
            ],
            actions: [
                { label: 'Open Alpaca', kind: 'view', value: 'alpaca' },
                { label: 'How to get API keys', kind: 'topic', value: 'connect.alpaca' },
            ],
            related: ['connect.alpaca', 'view.options', 'view.news', 'view.fundamentals'],
        },
        {
            id: 'view.platforms', group: 'panels', mode: 'both',
            title: 'Platforms (optional bridges)',
            tags: ['platforms', 'bridge', 'dtc', 'integration', 'requirements'],
            aliases: ['other platforms', 'external platform'],
            summary: 'What the two optional platform bridges are, what they cost, and what this build '
                + 'covers for free — a reference page you can read before deciding you need either.',
            blocks: [
                { p: 'Both bridges are optional and both are for connecting the program to an external '
                    + 'data or trading platform. The panel compares what each requires (including which '
                    + 'package tier unlocks external connections) against what this program already '
                    + 'does on its own, which is a lot: everything except the external platform\'s own '
                    + 'data.' },
                { note: 'Nothing in this program requires either bridge. They are listed with their '
                    + 'prices and requirements precisely so the answer to "do I need this?" can be '
                    + '"no".' },
            ],
            actions: [
                { label: 'Open Platforms', kind: 'view', value: 'platforms' },
                { label: 'Data sources', kind: 'topic', value: 'start.sources' },
            ],
            related: ['connect.bridges', 'start.sources'],
        },
        {
            id: 'view.profiles', group: 'panels', mode: 'both',
            title: 'Profiles (switchable playbooks)',
            tags: ['profiles', 'playbook', 'setup', 'switch', 'save', 'export', 'session', 'rules'],
            aliases: ['playbook', 'saved setup', 'workspace profile'],
            summary: 'Your setup as a named object: feed, instruments, analysis parameters, layout and '
                + 'theme switch together — save what you are running, tweak a copy, share one as a file.',
            blocks: [
                { p: 'A profile carries the blocks that define **how you read a market** — the feed, the '
                    + 'instrument set, the analysis parameters (heatmap, tape, CVD, market profile, the '
                    + 'engine), the studies, the layout and workspaces, the theme, plus watchlist, risk, '
                    + 'audio and calendar settings. It never carries credentials, machine paths or network '
                    + 'settings: those stay yours alone, which is also why a profile file is safe to share.' },
                { p: '**Switch** previews exactly what changes before anything is written. Feed, instruments '
                    + 'and analysis parameters are read by the engine at start, so the preview tells you '
                    + 'what lands now and what waits for the next engine start.' },
                { list: [
                    '**Save current as…** — the setup you are running becomes a profile, and becomes the '
                    + 'active playbook; change anything it carries and it shows as **drifted**, one click '
                    + 'from “Update from current”.',
                    '**Update from current** — re-capture a profile after you fiddled with things; the '
                    + 'previous version stays recoverable on the server.',
                    '**Export / Import** — a profile is a small JSON file; send it to someone, or keep it '
                    + 'as a backup.',
                    '**Startup profile** — pick one and switch on “apply at launch” to boot into it.',
                    '**Auto-switch rules** — optional: bind a profile to a feed, or to a clock window '
                    + '(with a day mask), so sessions change playbooks for you.',
                ] },
                { note: 'This program is half tuning. Profiles are how a good tuning survives: keep one for '
                    + 'each market or session you trade, instead of one setup stretched across all of them.' },
            ],
            actions: [
                { label: 'Open Profiles', kind: 'view', value: 'profiles' },
                { label: 'Settings', kind: 'topic', value: 'view.settings' },
            ],
            related: ['view.settings', 'view.instruments'],
        },
        {
            id: 'view.settings', group: 'panels', mode: 'both',
            title: 'Settings',
            tags: ['settings', 'config', 'thresholds', 'appearance', 'log level', 'reset', 'save'],
            aliases: ['preferences', 'configuration'],
            summary: 'Everything the program can change at runtime: appearance, data source, signal '
                + 'thresholds, per-pattern numbers, Telegram, the extra streams, and the log level. '
                + 'All of it is written to your user config file, never to the program.',
            blocks: [
                { h: 'The blocks', table: [
                    ['Appearance', 'Theme (dark · light · contrast), accent and density.'],
                    ['Engine', 'Data source, signal cooldown, minimum composite score, log level.'],
                    ['Telegram', 'Bot token and chat id, with a **Send test message** button that '
                        + 'posts a real message so you know it works before you rely on it. The '
                        + '**route order-flow alerts to Telegram** switch is stored with them — '
                        + 'the pill in the top bar says when it is off.'],
                    ['Extra streams', 'The venue\'s 200-level book, liquidations and block flags — '
                        + 'what makes the heatmap and the trackers richer.'],
                    ['Pattern thresholds', 'The numbers behind absorption, initiative, sweep, '
                        + 'exhaustion and divergence, per instrument.'],
                ] },
                { h: 'Save, or save and restart', p: 'Most changes apply on save. The ones the engine '
                    + 'reads at start are marked, and **Save & restart engine** applies them in one '
                    + 'action. **Reload** discards your edits; **Reset to defaults** puts every block '
                    + 'back to the shipped numbers (it keeps a copy of the file it replaces).' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Where settings live', kind: 'topic', value: 'data.config_file' },
            ],
            related: ['data.config_file', 'work.appearance', 'view.alerts'],
        },
        {
            id: 'view.logs', group: 'panels', mode: 'both',
            title: 'Logs',
            tags: ['logs', 'errors', 'troubleshooting', 'log file', 'level', 'clear'],
            aliases: ['log', 'console'],
            summary: 'What the program is doing, as it does it: the live engine log with a level '
                + 'filter, plus a line for the database size and the last retention pass.',
            blocks: [
                { h: 'Reading a problem out of it', list: [
                    'Filter to **WARNING** or **ERROR** first — the INFO stream is the whole story and '
                    + 'rarely the one you want.',
                    'Lines that start **client error:** come from the interface itself rather than the '
                    + 'engine: an error inside a panel, reported back to the same log.',
                    'The storage chip on the card is the quick read of whether the database is '
                    + 'healthy, and links to the retention settings.',
                ] },
                { h: 'Sharing a log', p: '**Tools ▸ Copy diagnostics** gathers the version, the config '
                    + 'paths, the source and the engine\'s counters into the clipboard — usually more '
                    + 'useful than the raw log, and safe to paste because keys are never included.' },
            ],
            actions: [
                { label: 'Open Logs', kind: 'view', value: 'logs' },
                { label: 'Copy diagnostics', kind: 'copy', value: 'diagnostics' },
                { label: 'Reporting a problem', kind: 'topic', value: 'support.report' },
            ],
            related: ['support.report', 'data.logs', 'under.diagnostics'],
        },
        {
            id: 'view.watchlist', group: 'panels', mode: 'both',
            title: 'Watchlist',
            tags: ['watchlist', 'quotes', 'multiple symbols', 'symbols at once'],
            summary: 'Quotes for several instruments at once — one shared poll rather than one per '
                + 'row, so a twenty-symbol watchlist costs what a one-symbol watchlist costs.',
            blocks: [
                { p: 'Rows show price and change for the instruments you enabled, with the feed each '
                    + 'row is really coming from. Symbols can also be added from the command palette '
                    + '(**Ctrl+K**), including several at a time by typing them comma-separated.' },
                { note: 'In Terminal mode the watchlist is also available as a widget, so it can sit '
                    + 'beside a chart instead of replacing it.' },
            ],
            actions: [
                { label: 'Open Watchlist', kind: 'view', value: 'watchlist' },
                { label: 'Open the palette', kind: 'palette', value: '' },
            ],
            related: ['work.palette', 'view.instruments', 'work.terminal'],
        },
        {
            id: 'view.news', group: 'panels', mode: 'both',
            title: 'News',
            tags: ['news', 'headlines', 'rss', 'context'],
            summary: 'Headlines for the active instrument from whatever news source this install is '
                + 'configured with — the venue-independent one is public RSS, and you can point it at '
                + 'a feed you trust more.',
            blocks: [
                { p: 'The headline list is deliberately plain: title, source, age. It is there to '
                    + 'answer "why did that move" without leaving the window, not to be a newsreader.' },
                { note: 'A linked Alpaca account adds Benzinga headlines; without one, the public RSS '
                    + 'feed is used. Fetches are capped and fail soft — a news source that is down '
                    + 'says so and affects nothing else.' },
            ],
            actions: [
                { label: 'Open News', kind: 'view', value: 'news' },
                { label: 'Market context', kind: 'topic', value: 'view.overview' },
            ],
            related: ['view.overview', 'view.fundamentals'],
        },
        {
            id: 'view.fundamentals', group: 'panels', mode: 'both',
            title: 'Fundamentals',
            tags: ['fundamentals', 'edgar', 'sec', 'filings', 'coingecko', 'market cap'],
            aliases: ['financials', 'filings'],
            summary: 'Filed numbers for the active instrument: SEC EDGAR annual filings for US filers, '
                + 'CoinGecko market data for crypto. No key, no account.',
            blocks: [
                { p: 'The concept selector chooses which headline figure to read the annual filing '
                    + 'facts for; the list is drawn from what the filer actually reported, so it does '
                    + 'not invent concepts for instruments that file nothing.' },
                { note: 'A crypto instrument gets the CoinGecko read instead of a filing. Both paths '
                    + 'are read-only public endpoints.' },
            ],
            actions: [
                { label: 'Open Fundamentals', kind: 'view', value: 'fundamentals' },
                { label: 'News', kind: 'view', value: 'news' },
            ],
            related: ['view.news', 'view.options'],
        },
        {
            id: 'view.options', group: 'panels', mode: 'both',
            title: 'Options',
            tags: ['options', 'deribit', 'chain', 'strikes', 'expiry', 'greeks', 'iv'],
            summary: 'Deribit\'s public crypto option chain: expiries, strikes, implied volatility and '
                + 'the Greeks — no key and no account.',
            blocks: [
                { p: 'Pick an expiry from the venue\'s own list; the chain fills with strikes and their '
                    + 'IV and Greeks, and the detail line under the table reads the row your cursor is '
                    + 'on. The chain is BTC/ETH/SOL by currency.' },
                { note: 'For **equity** options you need a linked Alpaca account — those live in the '
                    + 'option chain the command palette opens, not here.' },
            ],
            actions: [
                { label: 'Open Options', kind: 'view', value: 'options' },
                { label: 'Alpaca account', kind: 'view', value: 'alpaca' },
                { label: 'Open the palette', kind: 'palette', value: '' },
            ],
            related: ['connect.alpaca', 'view.alpaca'],
        },

        {
            id: 'view.gex', group: 'panels', mode: 'both',
            title: 'Gamma exposure (GEX)',
            tags: ['gex', 'gamma', 'dealers', 'walls', 'zero gamma', 'options', 'charm', 'vanna'],
            summary: 'Per-strike dealer gamma from an option chain: the zero-gamma line, the call and '
                + 'put walls, and the DEX / VEX / theta / vanna / charm totals.',
            blocks: [
                { p: 'Pick a **chain source** (Deribit is public and keyless for crypto; Tradier and '
                    + 'Market Data read US equity OPRA chains and need a key in the app\'s config) and '
                    + 'leave **Symbol** empty to follow the active instrument, or type a name to read '
                    + 'another one. The table lists each strike\'s gamma, exposure, open interest and '
                    + 'traded volume, widest exposure first.' },
                { h: 'What needs what', p: 'Gamma exposure requires a chain that actually carries '
                    + 'gammas. Deribit publishes them per instrument, Market Data sends them with its '
                    + 'chains, and **Tradier\'s chain carries IV, open interest and volume but no '
                    + 'greeks** — the panel then prints that sentence instead of a map of zeros. The '
                    + 'same honesty applies to vanna and charm: Deribit does not publish them, so '
                    + 'those two fields read **not published** rather than $0.00.' },
                { note: 'Every number comes from the venue\'s own chain and nothing is modelled: a '
                    + 'synthetic gamma would be this app\'s opinion, not the market\'s.' },
            ],
            actions: [
                { label: 'Open GEX', kind: 'view', value: 'gex' },
                { label: 'Open Volatility', kind: 'view', value: 'volatility' },
                { label: 'Open Options', kind: 'view', value: 'options' },
            ],
            related: ['view.options', 'view.volatility', 'method.levels'],
        },

        {
            id: 'view.volatility', group: 'panels', mode: 'both',
            title: 'Volatility surface',
            tags: ['volatility', 'iv', 'smile', 'skew', '25 delta', 'term structure', 'options'],
            summary: 'The implied-volatility smile per expiry, the 25Δ put and call wings, the skew '
                + 'between them and the term structure.',
            blocks: [
                { p: 'The surface reads the same three chain sources as the GEX panel, and **every one '
                    + 'of them carries implied volatility** — so this panel answers for all three; '
                    + 'only the expiries on offer differ (Deribit sends one expiry per read, the OPRA '
                    + 'chains send everything they list, which is what gives the term structure '
                    + 'something to draw).' },
                { h: 'Reading it', p: '**ATM IV** is the strike nearest spot; **25Δ put** and **25Δ '
                    + 'call** are the two wings the skew is the difference of — a skew alone cannot '
                    + 'say which wing moved. Beside them sit the chain\'s own desk numbers: **P/C OI** '
                    + '(how much open interest sits on puts against calls), **total OI**, the **IV '
                    + 'range** across the strikes read, and the **days to expiry** the whole surface '
                    + 'is scaled by.' },
                { h: 'The smile table', p: 'Strikes read left to right, ascending, with the same '
                    + 'strike\'s call and put beside each other. The strike nearest spot is marked, '
                    + 'in-the-money rows are shaded, and the Type cell carries the option market\'s '
                    + 'own colour. Open interest prints as whole contracts (1,235, never 1234.57) and '
                    + 'the IV column is a percentage of the same fraction every engine in this build '
                    + 'passes around.' },
            ],
            actions: [
                { label: 'Open Volatility', kind: 'view', value: 'volatility' },
                { label: 'Open GEX', kind: 'view', value: 'gex' },
            ],
            related: ['view.gex', 'view.options'],
        },

        {
            id: 'view.optionflow', group: 'panels', mode: 'both',
            title: 'Option flow (sweeps, blocks, unusual premium)',
            tags: ['option flow', 'sweeps', 'blocks', 'unusual premium', 'prints', 'tape', 'deribit',
                   'net premium', 'call premium', 'put premium', 'largest print'],
            summary: 'Deribit\'s public option tape classified into sweeps, blocks and unusual-premium '
                + 'prints, read as a tape: every print in the window, newest first, with the call and '
                + 'put premium each side paid.',
            blocks: [
                { p: 'The panel reads the venue\'s most recent option prints for the active '
                    + 'instrument\'s currency and classifies every one of them: a **sweep** is several '
                    + 'strikes traded in one burst, a **block** is a single large print, and '
                    + '**unusual premium** is a print that stands out against the open interest it '
                    + 'landed on. The window is the last 15 minutes, refreshed on the panel\'s own '
                    + 'cadence.' },
                { h: 'The tape is the table', p: 'Every print in the window is listed, newest first, '
                    + 'each one tagged with the class the engine gave it — a classified event reads '
                    + 'better inside the sequence that produced it than torn out of it. Sweep beats '
                    + 'block beats unusual when a print qualifies for more than one, because that is '
                    + 'the stronger statement about it.' },
                { h: 'Premium and the money fields', p: '**Premium** is the venue\'s own size × price. '
                    + 'The panel quotes it in dollars whenever the wire names the underlying it '
                    + 'priced against (the currency\'s perpetual mark, the contract crypto premium is '
                    + 'quoted against) and falls back to the contract\'s own currency — never a '
                    + 'guessed rate. **Call premium** and **put premium** split the tape, and **net '
                    + 'premium** is the difference: positive means calls paid more than puts over '
                    + 'this window. **Largest print** names the single biggest one.' },
                { p: 'The sub-line prints both counts on purpose — the prints the venue handed back '
                    + 'and how many fell inside the window — because they are different numbers and '
                    + 'a reader who sees only one of them will think it is wrong.' },
                { note: 'Flow needs **prints**, not quotes. Deribit publishes a keyless public option '
                    + 'tape and it is the only print source this build reads; the equity venues\' '
                    + 'chains carry quotes, so the panel names what would be needed rather than '
                    + 'showing sample trades — an invented sweep table would be worse than an empty '
                    + 'one.' },
            ],
            actions: [
                { label: 'Open Option Flow', kind: 'view', value: 'option-flow' },
                { label: 'Open the tape', kind: 'view', value: 'tape' },
            ],
            related: ['view.tape', 'view.options', 'view.trackers'],
        },

        {
            id: 'view.marketread', group: 'panels', mode: 'both',
            title: 'Market read',
            tags: ['market read', 'regime', 'conviction', 'levels', 'confluence', 'read'],
            summary: 'A deterministic read of the engine\'s live state: regime, conviction score and '
                + 'its per-signal breakdown, key levels and confluence points — no AI anywhere.',
            blocks: [
                { p: 'The read is a pure function of what the engine already knows about the active '
                    + 'instrument: tape stats, the session profile, the radar\'s levels, the depth '
                    + 'map\'s walls and the VWAP study. **With the engine stopped there is no read** '
                    + 'and the panel says so — it never invents a regime to fill the space.' },
                { h: 'What the scores are', p: 'The conviction score is a weighted sum of seven '
                    + 'signals (trend, imbalance, absorption, liquidity, levels, profile, VWAP), each '
                    + 'printed separately. The `not measured` line under the read names the inputs '
                    + 'that had nothing to read — the footprint family is not wired to the hub yet, '
                    + 'so a score computed without it says so on its own face.' },
            ],
            actions: [
                { label: 'Open Market Read', kind: 'view', value: 'market-read' },
                { label: 'Open Trackers', kind: 'view', value: 'trackers' },
            ],
            related: ['view.trackers', 'view.signals', 'method.levels'],
        },


        /* ═══════════ Working with the app ═══════════ */
        {
            id: 'work.terminal', group: 'workflow', mode: 'both',
            title: 'Terminal mode: widgets, tabs and layouts',
            tags: ['terminal', 'widgets', 'tabs', 'multi panel', 'dashboard', 'arrange'],
            aliases: ['widget mode', 'terminal layout'],
            summary: 'The same panels, arranged as widgets you place yourself: resize, drag, tab them '
                + 'together, and save the arrangement as a named layout.',
            blocks: [
                { h: 'Switching', p: 'The **Classic | Terminal** control in the top bar, the rail\'s '
                    + '**◫ Terminal mode** button, or **Ctrl+Alt+T**. Classic is one panel at a time; '
                    + 'Terminal is as many as your screen can usefully hold.' },
                { h: 'What a widget can do', list: [
                    'Resize and drag it; widgets snap together and can share a region as tabs.',
                    '**Link groups (A–D)** — a widget can join a group so that changing the symbol or '
                    + 'timeframe once moves every member, while unlinked panels stay where they are. '
                    + 'That is how you watch one instrument on three panels and another on two without '
                    + 'clicking each one.',
                    'Every widget is a real panel: it keeps its own state and its own keys.',
                ] },
                { h: 'Layouts', p: '**Layout ▸ Save current layout** names the arrangement. Layouts are '
                    + 'remembered per screen, so a laptop and a desk monitor can each reopen the way '
                    + 'you left each of them.' },
            ],
            actions: [
                { label: 'Help: layouts and workspaces', kind: 'topic', value: 'work.layouts' },
                { label: 'Help: widget windows', kind: 'topic', value: 'work.windows' },
            ],
            related: ['work.layouts', 'work.windows', 'work.display'],
        },
        {
            id: 'work.windows', group: 'workflow', mode: 'both',
            title: 'Widget windows (a panel in its own window)',
            tags: ['window', 'second monitor', 'aux', 'pin', 'always on top', 'multi monitor',
                   'snap', 'send to monitor'],
            aliases: ['send to monitor', 'floating panel', 'auxiliary window', 'move window',
                      'snap window', 'unpin'],
            summary: 'Any panel can be opened as its own real window and placed on any monitor — the '
                + 'way you keep a depth map on a second screen while the footprint stays on the first.',
            blocks: [
                { h: 'Opening one', list: [
                    '**Windows ▸ Open** (menu bar) opens the panel you are looking at as a separate '
                    + 'window; **Windows ▸ Send to monitor ▸** places it on a specific display.',
                    'In Terminal mode every widget carries a **⧉** button: it opens this menu on the '
                    + 'widget itself, already expanded to that window.',
                    'The window chip beside the top bar lists what is open, focuses a window, pins it '
                    + 'above others, or closes it.',
                    'Each window is one panel: it cannot itself open further windows, and it never '
                    + 'writes to your layout — closing it by its own ×, the OS\'s ×, or the app\'s '
                    + 'control all mean the same thing.',
                ] },
                { h: 'Moving, snapping, rescuing', list: [
                    '**⇥** on a window\'s row sends it to any monitor, or snaps it to a half, a '
                    + 'corner, centred or the whole monitor — one click each, right now.',
                    '**Ctrl+Alt+Shift+← / →** send the focused panel\'s window one monitor over; '
                    + '**Ctrl+Alt+W** opens its window menu. Both work in Classic mode too.',
                    '**View ▸ Windows & layouts…** is the whole desk in one dialog: every window with '
                    + 'the monitor it is on, Send and shape buttons per row, and a panel/monitor/shape '
                    + 'row that opens any panel anywhere.',
                    'A window whose monitor is not there any more is flagged, with **Bring them home** '
                    + 'to place it back on a live screen — the answer to the field\'s "my window is '
                    + 'off-screen" failure.',
                ] },
                { h: 'What is remembered', p: 'Open windows and their positions are remembered, so a '
                    + 'launch restores exactly the arrangement you had — and if a monitor is not '
                    + 'present this time, the window comes back on the primary rather than off-screen.' },
                { shot: 'help/window-heatmap.png',
                  caption: 'A depth map in its own window — the same panel, placed on its own monitor.' },
            ],
            actions: [
                { label: 'Open Windows (menu bar)', kind: 'menu', value: 'window' },
                { label: 'Help: display and DPI', kind: 'topic', value: 'work.display' },
            ],
            related: ['work.display', 'work.terminal', 'work.layouts'],
        },
        {
            id: 'work.layouts', group: 'workflow', mode: 'both',
            title: 'Layouts and workspaces',
            tags: ['layouts', 'workspaces', 'save layout', 'arrangement', 'profiles',
                   'previous versions', 'undo layout', 'version history', 'auto-cull'],
            aliases: ['save my setup', 'screens setup', 'undo my layout', 'roll back my layout',
                      'restore layout', 'older version'],
            summary: 'Two kinds of saved state: **layouts** (where the widgets are) and **workspaces** '
                + '(which panel you are on and how it is configured). Both live in your config file.',
            blocks: [
                { h: 'Which is which', table: [
                    ['Layout', 'The Terminal-mode arrangement: which widgets, where, tabbed how, and '
                        + 'which are pinned. Saved and reloaded from the **Layout** menu, keyed to the '
                        + 'screen it was made on.'],
                    ['Workspace', 'A quicker thing: the active panel and its parameters, saved from the '
                        + '☰ menu\'s Workspaces box or **File ▸ Save workspace** (**Ctrl+S**).'],
                ] },
                { h: 'Previous versions — the one-click undo for a layout', list: [
                    '**What it is.** Every time a layout is saved over (or deleted), the arrangement '
                    + 'it had a moment before is kept. **Layout ▸ Previous versions of this layout** '
                    + 'lists those snapshots — newest first, each with the time to the second, how '
                    + 'long ago it was kept, and what it holds ("6 widgets · 2 tabs"). One click puts '
                    + 'that arrangement back.',
                    '**Why it exists.** This app can change a whole screen with one click — '
                    + '**Auto-arrange this tab**, **Reset to the starter board**, a save-over, a '
                    + 'delete, an import. Any of those can land on an arrangement you liked. The '
                    + 'version ring is the cheap way back, and a restore is itself recorded, so you '
                    + 'can step forward again to what you had.',
                    '**Why only the last five.** Five is what people actually reach for: the last '
                    + 'few edits, not the whole history. It also keeps your config file honest — '
                    + 'every version is a full copy of the layout, so an unbounded history would '
                    + 'grow the file forever for versions you would never read.',
                    '**Auto-cull** (on by default) is what enforces the five: older copies are '
                    + 'dropped as you save. Turn it off and the store keeps up to ten — the same '
                    + 'command then also stops culling, and turning it back on drops the extra ones '
                    + 'immediately. The choice is saved in your config file with everything else.',
                ] },
                { note: 'Both are stored in your user config file, so they follow the machine and '
                    + 'survive a restart. Nothing about your arrangement is kept in the repository.' },
            ],
            actions: [
                { label: 'Open the ☰ menu', kind: 'menu', value: '' },
                { label: 'Help: terminal mode', kind: 'topic', value: 'work.terminal' },
            ],
            related: ['work.terminal', 'data.config_file'],
        },
        {
            id: 'work.menubar', group: 'workflow', mode: 'both',
            title: 'The menu bar and the ☰ menu',
            tags: ['menu', 'menu bar', 'file menu', 'tools', 'view menu', 'commands', 'run',
                'headless server', 'cli pipeline', 'desktop app'],
            aliases: ['top nav', 'nav bar', 'main menu'],
            summary: 'Two front doors with the same aim. The menu bar across the top holds the '
                + 'program\'s commands by category; the ☰ button (or **/**) opens a menu of panels '
                + 'grouped by what you are doing, with a filter box.',
            blocks: [
                { h: 'The menu bar', table: [
                    ['File', 'Workspaces, the user/exports/log folders, and the engine buttons.'],
                    ['View · Layout · Drawings · Chart', 'Which panel, where the widgets sit, the '
                        + 'drawing tools, and the settings of the chart you are on — the Chart menu is '
                        + 'the active panel\'s own variables, so it cannot drift from the panel.'],
                    ['Data', 'The source, the extra streams, and the instruments.'],
                    ['Run', 'The three ways the program runs — this desktop window, a '
                        + 'headless server on port 8099, or the CLI pipeline (feeds → '
                        + 'detectors → Telegram) — each launched in its own console. Below the '
                        + 'divider: the optional add-ons (MT5, NinjaTrader) and the dev gates.'],
                    ['Keys', 'The shortcut helper: every binding from the program\'s own map, '
                        + 'grouped by scope; clicking a row runs its action. **B** hides/shows the '
                        + 'bar, **R** the side rail.'],
                    ['Tools', 'The command palette, the hotkey sheet, render telemetry, the '
                        + 'diagnostics copy, and the client-error log.'],
                    ['Help', 'The Help Centre, the mode switch, the setup assistant, the hotkey map '
                        + 'and the About card — see *About, credits and links*.'],
                ] },
                { h: 'Driving it from the keyboard', p: '**Alt** focuses the bar, ← → walk the menus, '
                    + 'Enter opens one, ↑ ↓ walk its items, and typing a letter jumps to the next item '
                    + 'starting with it. Every item shows its accelerator on the right; an item that is '
                    + '**B hides or shows the top menu bar and R the side rail** (the View menu carries the '
                    + 'same toggles; both choices are remembered, and B always brings the bar back). An '
                    + 'item that is not built yet is greyed out with the reason in its tooltip rather than silently '
                    + 'doing nothing.' },
            ],
            actions: [
                { label: 'Open the ☰ menu', kind: 'menu', value: '' },
                { label: 'Open the palette', kind: 'palette', value: '' },
                { label: 'Show the shortcut map', kind: 'keys', value: '' },
            ],
            related: ['work.palette', 'work.keys', 'start.window'],
        },
        {
            id: 'work.palette', group: 'workflow', mode: 'both',
            title: 'The command palette (search everything)',
            tags: ['palette', 'ctrl+k', 'search', 'symbols', 'find symbol', 'command'],
            aliases: ['command palette', 'quick search', 'find a symbol'],
            summary: '**Ctrl+K** or **/** opens one box that searches two worlds at once: the program '
                + '(panels, actions, alert rules, walkthroughs) and the market (symbols, with live '
                + 'quotes and the feed each one really comes from).',
            blocks: [
                { h: 'Using it', table: [
                    ['Enter', 'Opens the highlighted result. On a symbol: switches the whole program to '
                        + 'it and opens the view you chose in Settings ▸ search default view.'],
                    ['Ctrl+Enter', 'Opens a symbol in a second view without losing the first.'],
                    ['Ctrl+Shift+Enter', 'Opens the option chain for an equity (needs a linked Alpaca '
                        + 'account).'],
                    ['Ctrl+Click', 'Multi-select rows, then add them all to the watchlist or compare '
                        + 'their feeds.'],
                ] },
                { h: 'Operators', p: 'The box accepts filters rather than guessing: `type:option` '
                    + '`underlying:AAPL` `vol:>1M` `sort:chg`. A comma-separated list of tickers '
                    + 'becomes a multi-select in one go, and anything the parser cannot read stays '
                    + 'ordinary text instead of blanking the list.' },
                { note: 'Every row says which feed its price came from — IEX, delayed SIP, indicative, '
                    + 'or the crypto venue — because two symbols with the same name are not always the '
                    + 'same instrument.' },
            ],
            actions: [
                { label: 'Open the palette', kind: 'palette', value: '' },
                { label: 'Help: watchlist', kind: 'topic', value: 'view.watchlist' },
            ],
            related: ['view.watchlist', 'view.instruments', 'connect.alpaca'],
        },
        {
            id: 'work.keys', group: 'workflow', mode: 'both',
            title: 'Keyboard shortcuts',
            tags: ['shortcuts', 'hotkeys', 'keyboard', 'keys', 'accelerators', 'keys menu',
                'hover', 'prompts'],
            aliases: ['hotkey map', 'key map'],
            summary: 'The list below is generated from the program\'s own shortcut map, so every key '
                + 'it honours is here and no key is listed that does nothing. **?** opens it as an '
                + 'overlay at any time, and the top bar\'s **Keys** menu is the same list grouped by '
                + 'scope — a row with a shortcut key on the right runs its action when clicked.'
                + ' In the sheet, **Change** on a row captures your own combination — a conflict'
                + ' is refused with the owner named, and Reset (or Reset all) puts the shipped'
                + ' keys back.',
            blocks: [
                { h: 'Where to find them', list: [
                    '**The Keys menu** (top menu bar) — the whole map, grouped by scope; click a '
                    + 'dispatched row to run that action right there.',
                    '**Hover any control** — controls that carry a shortcut say so: the tooltip '
                    + 'ends with it and the hover card adds a "\u2328 Shortcut …" line.',
                    '**The sheet** (**?**) — the same registry as an overlay; it cannot drift '
                    + 'from what the keyboard honours.',
                ] },
                { keys: true },
                { note: 'A key never fires while your cursor is in a text field, with two deliberate '
                    + 'exceptions: **Esc** closes the open menu or overlay even mid-typing, and **F1** '
                    + 'always reaches the Help Centre. Keys scoped '
                    + 'to a panel only act in that panel — the Engine\'s zoom keys do nothing in the '
                    + 'Heatmap, and the menu bar\'s arrows only act while it is focused.' },
            ],
            actions: [
                { label: 'Show the overlay', kind: 'keys', value: '' },
                { label: 'Open the Help Centre search', kind: 'search', value: 'shortcut' },
            ],
            related: ['work.palette', 'work.menubar', 'start.help'],
        },
        {
            id: 'work.drawings', group: 'workflow', mode: 'both',
            title: 'Drawings and annotations',
            tags: ['drawings', 'lines', 'annotations', 'fib', 'measure', 'tools'],
            summary: 'Figures drawn on the chart — trend lines, levels, rectangles, measurements — '
                + 'kept per instrument and per view, in price and time space, so they stay where you '
                + 'put them as the chart scales.',
            blocks: [
                { h: 'How it works', list: [
                    'Pick a tool from the **Drawings** menu (or the view\'s own toolbar), then draw on '
                    + 'the chart. **Esc** returns you to selecting, and each tool says when it is '
                    + 'finished rather than leaving you in an invisible mode.',
                    'Figures live in your config, keyed to the instrument and the view, so switching '
                    + 'instruments does not merge one symbol\'s levels into another\'s.',
                ] },
                { note: 'On the Engine view the same gesture becomes a **measurement**: select a '
                    + 'region and the HUD reads out the volume, delta and time inside it.' },
            ],
            actions: [
                { label: 'Open the Chart', kind: 'view', value: 'chart' },
                { label: 'Open the Engine', kind: 'view', value: 'ofx' },
            ],
            related: ['view.chart', 'view.ofx', 'work.cursor'],
        },
        {
            id: 'work.cursor', group: 'workflow', mode: 'both',
            title: 'One level, every panel (the cursor spine)',
            tags: ['cursor', 'crosshair', 'linked', 'level', 'compare', 'spine'],
            aliases: ['linked crosshair', 'shared cursor'],
            summary: 'Move the crosshair on one panel and the price/time you are on is carried to the '
                + 'others — the fastest way to check whether a level the tape printed is the same '
                + 'level the heatmap shows holding.',
            blocks: [
                { p: 'The shared level appears as a marker plus its value on each participating panel '
                    + '(the chart, the heatmap, the depth map, CVD, the profile and the tape), so '
                    + 'reading two panels at once stops being an act of memory.' },
                { shot: 'help/cursor-spine.png',
                  caption: 'The shared level carried across panels: one cursor, one price, every panel marked.' },
            ],
            actions: [
                { label: 'Open the Heatmap', kind: 'view', value: 'heatmap' },
                { label: 'Open the Engine', kind: 'view', value: 'ofx' },
            ],
            related: ['view.heatmap', 'view.ofx', 'work.terminal'],
        },
        {
            id: 'work.pause', group: 'workflow', mode: 'both',
            title: 'Pausing the live updates',
            tags: ['pause', 'freeze', 'hold updates', 'quiet', 'per panel', 'hold', 'study', 'resume'],
            aliases: ['stop refreshing', 'freeze the screen', 'park a panel'],
            summary: '**P** (or the ▶ live button in the top bar) holds every background refresh — '
                + 'and every live panel carries its own **Pause** beside its title, so one chart, the '
                + 'tape or the whole book can be parked for study while the rest of the board keeps '
                + 'moving.',
            blocks: [
                { h: 'The two levels', table: [
                    ['The ▶ live chip (top bar) · P', 'Holds everything at once: the whole board '
                        + 'freezes exactly as it stands. The chip names what is held and how many '
                        + 'updates are waiting.'],
                    ['A panel\'s own **Pause**', 'Parks just that panel. Its updates are **queued**, '
                        + 'never dropped — the chip counts them — and they apply the moment you '
                        + 'resume: a parked tape snaps current, a parked board re-reads.'],
                ] },
                { p: 'Ingest never stops either way: the engine keeps streaming and recording, the '
                    + 'socket keeps feeding; it is the drawing that is held. That is what makes a '
                    + 'frozen panel safe to study — and why resuming loses nothing. Panels with the '
                    + 'button: Overview, Chart, Order Flow, the Engine, Market depth, Time & Sales, '
                    + 'Market Watch, Signals and Trackers.' },
                { note: 'Being in a text field, a drag or a menu holds the affected panel '
                    + 'automatically; the buttons are for the deliberate case. A parked panel stays '
                    + 'parked across a reload, and its button always shows Resume while it is held.' },
            ],
            actions: [
                { label: 'Open the Help Centre search', kind: 'search', value: 'pause' },
            ],
            related: ['work.keys', 'fix.slow', 'view.marketwatch'],
        },
        {
            id: 'work.appearance', group: 'workflow', mode: 'both',
            title: 'Themes, accents and density',
            tags: ['theme', 'dark', 'light', 'contrast', 'accent', 'colour', 'appearance', 'density'],
            aliases: ['look and feel', 'colours', 'dark mode'],
            summary: 'Three themes (dark, light, contrast), eight Windows accents and three densities, '
                + 'changeable at runtime from **Settings ▸ Appearance** — nothing needs a restart and '
                + 'nothing needs a rebuild.',
            blocks: [
                { h: 'What to pick', list: [
                    '**Contrast** is for bright rooms and bad screens: maximum separation, no subtlety.',
                    '**Light** for a daylight office; **dark** for a trading evening.',
                    '**Density**: comfortable, compact or dense. Dense fits more rows in a tape without '
                    + 'shrinking the text to unreadable.',
                ] },
                { h: 'Colour-blind-safe palettes', p: 'The chart and the engine offer **deutan**, '
                    + 'protan** and **tritan** palettes in addition to the theme\'s own green/red pair. '
                    + 'They are not guesses: each set is measured under a simulated deficiency, and the '
                    + 'depth ramps are monotone in luminance so magnitude never rides on hue alone.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Help: display and DPI', kind: 'topic', value: 'work.display' },
            ],
            related: ['view.settings', 'work.display', 'view.ofx'],
        },
        {
            id: 'work.display', group: 'workflow', mode: 'both',
            title: 'Display scale, DPI and multi-monitor',
            tags: ['dpi', 'scaling', '4k', 'multi monitor', 'second screen', 'blurry', 'crisp'],
            aliases: ['display scaling', 'high dpi', 'screen size'],
            summary: 'The window and every canvas are sized from the display it is actually on, so a '
                + '4K screen at 150% is sharp rather than blurry, and moving the window between '
                + 'monitors re-fits the panels instead of stretching them.',
            blocks: [
                { h: 'What is remembered', list: [
                    'The window\'s position and size — reopened on the monitor you left it on, and '
                    + 'placed on the primary if that monitor is gone.',
                    'Each screen\'s Terminal layout, keyed to the screen\'s size and scale, so a laptop '
                    + 'and a desk monitor keep their own arrangements.',
                    'Widget windows and their positions.',
                ] },
                { h: 'If a panel looks wrong after a display change', p: 'Move the window, or resize it '
                    + 'once: the fit runs again from the panels\' own CSS boxes. If something is still '
                    + 'mis-drawn, it is a bug worth reporting — the app is measured against the rule '
                    + '"a canvas is always backed at its box size times the display scale", and every '
                    + 'panel participates.' },
            ],
            actions: [
                { label: 'Help: widget windows', kind: 'topic', value: 'work.windows' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
            ],
            related: ['work.windows', 'work.terminal', 'fix.slow'],
        },
        {
            id: 'work.audio', group: 'workflow', mode: 'both',
            title: 'Trade audio',
            tags: ['audio', 'sound', 'beep', 'tone', 'trade sound', 'alert sound'],
            aliases: ['sound settings', 'trade sounds'],
            summary: 'A tone when a print crosses a size you care about — so you can hear the market '
                + 'while looking at something else. Off by default, with a size floor and a volume of '
                + 'its own.',
            blocks: [
                { h: 'The settings', table: [
                    ['enabled', 'On or off, and the Alerts panel\'s own sound switch.'],
                    ['min size', 'Prints below this never make a sound — the floor that keeps a busy '
                        + 'crypto tape from becoming a drone.'],
                    ['hard multiple', 'A harder, higher tone for prints this many times above the '
                        + 'threshold: normal tension and real tension sound different.'],
                    ['volume', 'Its own level, independent of the system volume — set it in '
                        + 'Settings ▸ Sound, where **Test sound** plays the buy sample at the '
                        + 'current level even while the switch is off.'],
                ] },
                { note: 'The four alert samples ship with the app (four small WAVs) — nothing '
                    + 'is downloaded and nothing is generated at runtime.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Help: alerts', kind: 'topic', value: 'view.alerts' },
            ],
            related: ['view.alerts', 'view.settings'],
        },
        {
            id: 'work.updates', group: 'workflow', mode: 'both',
            title: 'Updates never block',
            tags: ['update', 'updater', 'upgrade', 'new version', 'release notes', 'changelog',
                'what changed'],
            aliases: ['update policy', 'what changed'],
            summary: 'Checking for a newer build never interrupts: the app asks **when you are not '
                + 'typing**, shows what is new, and downloads only if you ask it to. Nothing restarts '
                + 'itself and no window ever stands in your way.',
            blocks: [
                { h: 'How it behaves', list: [
                    '**The check** — on load and on a timer (Settings ▸ Updates sets the interval and '
                        + 'the channel: stable or pre-releases). A found update waits for a quiet moment '
                        + 'before it says so.',
                    '**The note** — the release’s own notes are shown beside the update (“What’s in X”), '
                        + 'so a moved button is never a mystery.',
                    '**The download** — fetch it yourself with **Update** in the top bar, or let the app '
                        + 'fetch the installer in the background; the choice is a setting.',
                    '**The verification** — a downloaded installer is checked against the release’s own '
                        + 'SHA-256 when GitHub publishes one.',
                    '**The failure path** — offline or a broken channel simply means no update today; '
                        + 'the check retries later and never nags.',
                ] },
                { note: 'Written down as policy in `docs/UPDATE_POLICY.md`: an update never blocks the '
                    + 'app, never restarts it, and never needs an account.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
            ],
            related: ['view.settings', 'work.exports'],
        },
        {
            id: 'work.exports', group: 'workflow', mode: 'both',            title: 'Exports and screenshots',
            tags: ['export', 'csv', 'png', 'clipboard', 'screenshot', 'save image'],
            aliases: ['save a picture', 'download data'],
            summary: 'Panels that show measurements can hand them over: a region of the heatmap or the '
                + 'engine exports as a PNG and a CSV, and the App\'s own exports folder is the default '
                + 'destination.',
            blocks: [
                { list: [
                    '**Engine and Heatmap** — select a region, then **Ctrl+E** (or the export button in '
                    + 'the selection readout) writes the picture and the underlying numbers.',
                    '**Exports folder** — **File ▸ Open exports folder** takes you to where they land.',
                    '**Diagnostics** — **Tools ▸ Copy diagnostics** copies a text summary for a bug '
                    + 'report rather than a file.',
                ] },
                { note: 'Exports are written to your own machine only. Nothing in this program uploads '
                    + 'anything anywhere.' },
            ],
            actions: [
                { label: 'Open the exports folder', kind: 'folder', value: 'exports' },
                { label: 'Help: heatmap', kind: 'topic', value: 'view.heatmap' },
            ],
            related: ['view.heatmap', 'view.ofx', 'data.folders'],
        },

        /* ═══════════ Connections and setup ═══════════ */
        {
            id: 'connect.venues', group: 'connect', mode: 'both',
            title: 'What each venue publishes',
            tags: ['venue', 'bybit', 'binance', 'okx', 'hyperliquid', 'depth', 'trades', 'limits'],
            aliases: ['which exchange', 'feed comparison'],
            summary: 'The four keyless venues differ in what they stream and how deep the book goes. '
                + 'The default carries everything the order-flow panels need; the others are there for '
                + 'a market you care about specifically.',
            blocks: [
                { h: 'In practice', list: [
                    '**Bybit** streams trades, order book and candles, and is the only source the '
                    + 'optional **extra streams** (200-level book and liquidations) attach to — that is '
                    + 'why it is the default.',
                    '**Binance Futures**, **OKX** and **Hyperliquid** stream trades, depth and candles '
                    + 'from their own public endpoints. The panels behave identically; the difference '
                    + 'is which instruments exist and how deep the book is published.',
                    'Every venue value is checked for sanity at ingest, so a venue publishing a junk '
                    + 'number cannot quietly poison an average.',
                ] },
                { note: 'Reachability is probed the way the adapter actually calls each venue, so a '
                    + '"reachable" verdict in the connections list means the feed really works from '
                    + 'this machine — not merely that the host answers a ping.' },
            ],
            actions: [
                { label: 'Switch source (☰ menu)', kind: 'menu', value: '' },
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
            ],
            related: ['start.sources', 'view.instruments', 'fix.no_data'],
        },
        {
            id: 'connect.mt5', group: 'connect', mode: 'both',
            title: 'MetaTrader 5 in this program',
            tags: ['mt5', 'metatrader', 'indices', 'gold', 'forex', 'broker terminal', 'install bridge'],
            aliases: ['metatrader setup', 'mt5 bridge'],
            summary: 'MetaTrader 5 is the second data source: your own broker\'s terminal for indices, '
                + 'gold and silver, FX, commodity CFDs and equity CFDs — the instruments a crypto '
                + 'venue does not list.',
            blocks: [
                { h: 'You will need', list: [
                    '**Windows** — the MetaTrader5 Python package ships Windows wheels only.',
                    'An **MT5 account** with any broker; demo accounts work identically.',
                    'The **terminal installed and left running** — the bridge talks to the running '
                    + 'terminal, not to the broker directly.',
                ] },
                { h: 'Steps', steps: [
                    { t: 'Install the terminal from your broker', d: 'Not from this app: every broker '
                        + 'ships its own branded terminal and publishes its own symbol names.' },
                    { t: 'Sign in and leave it running', d: 'File ▸ Login to Trade Account. A closed '
                        + 'terminal means no data, demo or live alike.' },
                    { t: 'Install the bridge (source installs)', d: 'The portable Windows build already includes '
                        + 'the bridge \u2014 skip to the test below. In a source install, one line, '
                        + 'and only if you want MT5 data: pick the line that matches how this '
                        + 'environment was built; the setup assistant\'s MT5 step prints the right '
                        + 'one for this machine.',
                      cmd: ['.venv\\Scripts\\python.exe -m pip install MetaTrader5',
                            'uv pip install --python .venv\\Scripts\\python.exe MetaTrader5'] },
                    { t: 'Point the app at the terminal', d: 'Usually not needed — the bridge looks in '
                        + 'the standard places. Fill the path only if your broker installs somewhere '
                        + 'unusual, e.g. C:\\Program Files\\MetaTrader 5\\terminal64.exe.' },
                    { t: 'Map the symbols', d: 'The app knows an instrument by its own name (NAS100USDT, '
                        + 'XAUUSDT); your broker calls the same market something else (USTEC, US100, '
                        + 'GOLD…). Sensible defaults ship per instrument and you can correct them — see '
                        + '*Mapping MT5 symbols*.' },
                    { t: 'Test the bridge', d: 'The wizard\'s MT5 step connects with these exact '
                        + 'settings, reports the terminal, the account and which mapped symbols the '
                        + 'broker actually lists, then disconnects.' },
                ] },
                { warn: 'Honest limits: MT5 data comes from your broker\'s terminal, so quality and '
                    + 'depth are broker-dependent — some publish a full order book, some publish almost '
                    + 'none. The depth views are at their best on the exchange feed; MT5 is how you get '
                    + 'the instruments the exchange does not list. Historical ticks download from the '
                    + 'broker on first use.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Run the setup assistant', kind: 'wizard', value: '' },
            ],
            links: [{ label: 'MetaTrader 5 download', url: 'https://www.metatrader5.com/en/download' }],
            related: ['connect.mt5_map', 'start.sources', 'view.instruments'],
        },
        {
            id: 'connect.ninjatrader', group: 'connect', mode: 'both',
            title: 'NinjaTrader 8 in this program',
            tags: ['ninjatrader', 'nt8', 'futures', 'nq', 'es', 'mnq', 'cme', 'bridge', 'dll',
                   'ninjascript editor'],
            aliases: ['ninjatrader setup', 'nt bridge'],
            summary: 'NinjaTrader is the futures data source: the terminal\'s own instruments — NQ, ES, '
                + 'MNQ and everything else your data subscription carries — stream into every panel '
                + 'through a small read-only bridge add-on this program ships.',
            blocks: [
                { h: 'You will need', list: [
                    '**Windows**.',
                    'NinjaTrader Desktop installed (free) and its **account** — version 8.1+ asks you '
                    + 'to log in on every start and exits if the log-in window is closed.',
                    'The **bridge add-on**, installed once: a file copy, one platform option, one '
                    + 'restart — the suite ships the DLL, no compiler needed.',
                ] },
                { h: 'Steps', steps: [
                    { t: 'Install NinjaTrader and log in', d: 'From ninjatrader.com; installing and '
                        + 'running it in simulation is free.' },
                    { t: 'Get data flowing in the platform', d: 'The **Simulated Data Feed** needs no '
                        + 'payment and is complete (quotes, trades, depth) — ideal to verify this whole '
                        + 'path. A funded NinjaTrader brokerage account adds complimentary real-time '
                        + 'CME/EUREX Level I while funded; Kinetick End-Of-Day is free to everyone.' },
                    { t: 'Install the bridge add-on (once)', d: 'Open the bridge folder from '
                        + '**Platforms ▸ NinjaTrader ▸ Show the DLL folder**, copy **ModFlowBridge.cs**, **ModFlowJson.cs** and **ModFlowProbe.cs** '
                        + 'into Documents\\NinjaTrader 8\\bin\\Custom\\AddOns, then press **F5** in '
                        + 'its own NinjaScript Editor and answer the trust prompt once. Its Log tab then shows the bridge listening on '
                        + '127.0.0.1:8790.' },
                    { t: 'Test the bridge', d: 'The Platforms card\'s **Test connection** (and the '
                        + 'walkthrough\'s own panel) connects, subscribes to one instrument and reports '
                        + 'the NinjaTrader build, the live connection and what actually streamed — '
                        + 'quotes, trades, and depth if your feed carries it.' },
                    { t: 'Add instruments from the terminal\'s own list', d: 'Type **NQ** (or NQ1, or a '
                        + 'full name like MNQ 12-26) in the Instruments panel\'s look-up — it offers '
                        + 'the front-month contract the terminal itself would use and stamps it so the '
                        + 'engine streams it like any other venue.' },
                    { t: 'Pick NinjaTrader as the data source', d: 'In the setup assistant\'s Data '
                        + 'source step, or ☰ ▸ sources. The tape, footprint, delta, profiles and ladder '
                        + 'then read your terminal.' },
                ] },
                { warn: 'Honest limits: **level-2 depth arrives only when your data subscription '
                    + 'carries it** — the bridge card reports what actually arrived instead of '
                    + 'promising a ladder. Order Flow+ ($59/month standalone; complimentary while an '
                    + 'account is funded; included with the Lifetime plan) changes NinjaTrader\'s own '
                    + 'charts — this program computes its own footprint/delta from the raw trades and '
                    + 'depth the bridge republishes and does not need it. The bridge is read-only and '
                    + 'loopback-only: no orders, no account details, nothing beyond host/port/plan is '
                    + 'stored.' },
            ],
            actions: [
                { label: 'Open Platforms', kind: 'view', value: 'platforms' },
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Run the setup assistant', kind: 'wizard', value: '' },
            ],
            links: [{ label: 'NinjaTrader — plans and pricing', url: 'https://ninjatrader.com/pricing/' },
                    { label: 'Subscribing to market data (their article)',
                      url: 'https://support.ninjatrader.com/s/article/How-do-I-register-for-data-feeds-for-my-account' }],
            related: ['under.nt_bridge', 'view.platforms', 'start.sources'],
        },
        {
            id: 'under.nt_bridge', group: 'under', mode: 'advanced',
            title: 'The NinjaTrader bridge — install and diagnose',
            tags: ['ninjatrader bridge', 'ntbridge log', 'addon folder', 'custom assembly loading',
                   '8790', 'troubleshoot ninjatrader'],
            summary: 'The bridge is a small read-only add-on that runs inside NinjaTrader, subscribes to '
                + 'the platform\'s own market-data callbacks and republishes them on loopback. This is '
                + 'how to install it, what it writes, and what to check when it stays silent.',
            blocks: [
                { h: 'What it is, precisely', list: [
                    'A DLL built against NinjaTrader\'s own assemblies (verified against 8.1.8.2), '
                    + 'shipped with this suite; the source and its build script travel beside it.',
                    'It binds **127.0.0.1:8790** only, accepts **one reader at a time** (this program), '
                    + 'and speaks NUL-terminated JSON frames.',
                    'It reads: quotes, trades, level-2 depth, the instrument database and historical '
                    + 'bars. It cannot place, modify or cancel an order — the protocol has no write '
                    + 'verbs and the DLL never touches account files.',
                ] },
                { h: 'Install, in order', steps: [
                    { t: 'Copy the bridge source', d: 'Platforms ▸ NinjaTrader ▸ **Show the DLL folder**→ copy the three bridge files '
                        + 'into Documents\\NinjaTrader 8\\bin\\Custom\\AddOns (create the AddOns folder if it is missing).' },
                    { t: 'Compile it + trust it once', d: 'In NinjaTrader: New ▸ NinjaScript Editor → **F5**. The first load asks you to trust the newly compiled add-on — answer **Yes**. That prompt is how the platform gates third-party code, its own replacement for the old settings toggle.' },
                    { t: 'Watch the platform Log tab', d: 'The bridge starts as soon as the compile finishes; the Log tab shows *[ModFlow Bridge] listening on 127.0.0.1:8790*.' },
                    { t: 'Verify from this program', d: 'Platforms ▸ NinjaTrader ▸ **Test connection** '
                        + 'names the NinjaTrader build, the connection and the message counts.' },
                ] },
                { h: 'When it stays silent', list: [
                    '**ntbridge.log** in `%LOCALAPPDATA%\\ModFlow` — every bind, accept, subscribe and '
                    + 'error the bridge writes. A bind failure (port taken) is recorded here.',
                    '**ntbridge-probe.log** in the same folder — a diagnostics companion that dumps the '
                    + 'platform facts (loaded assemblies, accounts, instrument look-ups) on every '
                    + 'start; if even this file is absent, NinjaTrader is not loading the DLL at all '
                    + '(recheck the folder and the platform option).',
                    'The port: 8790 is this suite\'s convention. If something else owns it, rebuild '
                    + 'the bridge from the source folder with another `Port` value and set the same '
                    + 'port on the card.',
                    'Only the connection the platform is on matters — a terminal showing Kinetick '
                    + 'End-Of-Day carries no live stream to republish.',
                ] },
                { note: 'The deliverables live in the app folder under '
                    + '`orderflow_system/data/ninjatrader_bridge/`: the DLL, the C# source, '
                    + '`build.ps1` (needs only the free .NET SDK — no Visual Studio) and the README '
                    + 'with the full wire format.' },
            ],
            actions: [
                { label: 'Open Platforms', kind: 'view', value: 'platforms' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
            ],
            links: [{ label: 'General options page (where the platform option lives)',
                      url: 'https://ninjatrader.com/support/helpguides/nt8/general_section.htm' }],
            related: ['connect.ninjatrader', 'connect.bridges', 'fix.no_data'],
        },
        {
            id: 'connect.mt5_map', group: 'connect', mode: 'both',
            title: 'Mapping MT5 symbols',
            tags: ['mt5 symbols', 'mapping', 'broker symbol', 'symbol name'],
            summary: 'An instrument has two names: the one this program uses and the one your broker '
                + 'uses. The mapping table is where you say which is which.',
            blocks: [
                { list: [
                    'The app ships defaults for the common brokers, so the mapping is usually already '
                    + 'right.',
                    'A wrong mapping is the most common reason an MT5 instrument stays silent — the '
                    + 'engine cannot subscribe a symbol your broker does not list.',
                    'The Instruments view shows the mapping the engine is using, and the system check '
                    + 'flags any enabled MT5 instrument with no broker symbol at all.',
                    'Broker names are **case-sensitive** and differ per broker (“US500M” on one '
                    + 'terminal, “US500m” on another). The instrument look-up offers the '
                    + 'spelling your own broker lists, and **Add & restart** writes it and restarts the '
                    + 'engine in one step.',
                ] },
                { p: 'To find your broker\'s name for an instrument: in the terminal, right-click the '
                    + 'Market Watch and choose **Symbols**, then search. The exact spelling is what '
                    + 'goes in the mapping.' },
            ],
            actions: [
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Run the system check', kind: 'check', value: '' },
            ],
            related: ['connect.mt5', 'view.instruments', 'fix.skipped_symbols'],
        },
        {
            id: 'connect.alpaca', group: 'connect', mode: 'both',
            title: 'Linking an Alpaca account',
            tags: ['alpaca', 'paper account', 'api key', 'stocks', 'etf', 'free', 'link'],
            aliases: ['alpaca keys', 'broker account setup'],
            summary: 'A real US brokerage account as an extra data source. A **paper** account is free, '
                + 'needs only an email address, and behaves exactly like a live one: same API, virtual '
                + 'money, resettable.',
            blocks: [
                { h: 'Steps', steps: [
                    { t: 'Create the account', d: 'Sign up at app.alpaca.markets. Choose the **paper** '
                        + 'account for simulation: it is created instantly and needs no identity '
                        + 'documents.' },
                    { t: 'Open the API keys page', d: 'In the dashboard, switch to the environment you '
                        + 'want — the key page belongs to the environment you are in — then generate a '
                        + 'key pair.',
                      cmd: [] },
                    { t: 'Copy both values', d: 'The **key ID** (starts with PK for paper) and the '
                        + '**secret**. The secret is shown once; if you lose it, generate a new pair.' },
                    { t: 'Paste them into Settings ▸ broker account', d: 'Pick the matching environment '
                        + 'in the dropdown. Paper keys only work against the paper host and live keys '
                        + 'only against the live host — the wrong pair is the single most common error, '
                        + 'and the app says so when it happens.' },
                    { t: 'Press Validate', d: 'The app asks Alpaca to confirm the keys, then reports '
                        + 'the account and exactly what it can reach: real-time tape, delayed '
                        + 'full-market history, news, calendar, options, positions and portfolio '
                        + 'history.' },
                ] },
                { h: 'Where the keys live', p: 'In this program\'s local config file on your machine. '
                    + 'They are never displayed back, and they are sent only to Alpaca. **Remove keys** '
                    + 'wipes them.' },
                { warn: 'Alpaca publishes no order book, so the heatmap, the depth ladder and the '
                    + 'participants\' intent reader stay on the exchange feed. Free-plan real-time US '
                    + 'data is the IEX venue only; full-market SIP data is readable once it is 15 '
                    + 'minutes old, and the app labels which feed a panel is showing.' },
            ],
            actions: [
                { label: 'Open Alpaca', kind: 'view', value: 'alpaca' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Run the setup assistant', kind: 'wizard', value: '' },
            ],
            links: [{ label: 'Alpaca — API keys page',
                      url: 'https://app.alpaca.markets/paper/dashboard/overview' }],
            related: ['view.alpaca', 'data.security', 'view.options'],
        },
        {
            id: 'connect.channels', group: 'connect', mode: 'both',
            title: 'Where alerts go',
            tags: ['telegram', 'ntfy', 'email', 'webhook', 'notifications', 'bot token', 'chat id', 'push'],
            aliases: ['alert channels', 'phone notifications', 'notify'],
            summary: 'Four optional ways off this machine: **Telegram**, **ntfy**, **email** and a '
                + '**webhook**. All free at the level this program uses, and each one has a Test '
                + 'button that sends a real message.',
            blocks: [
                { h: 'Telegram (about two minutes)', steps: [
                    { t: 'Create the bot', d: 'In Telegram, message **@BotFather**, send /newbot, pick a '
                        + 'name and a username ending in "bot". BotFather answers with an HTTP API '
                        + 'token.' },
                    { t: 'Get the chat id', d: 'Send your new bot any message first (it cannot start a '
                        + 'conversation), then message **@userinfobot** and copy the numeric id.' },
                    { t: 'Paste and test', d: 'Settings ▸ Telegram: paste the token and chat id, press '
                        + '**Send test message**, and the message arrives on your phone.' },
                ] },
                { h: 'ntfy (no account at all)', p: 'Choose a long, unguessable topic name, subscribe '
                    + 'to the same topic in the ntfy app, paste it here and press Test. Anyone who '
                    + 'knows the topic name can read it, so treat it as a secret.' },
                { h: 'Email and webhook', p: 'Email suits a daily digest or a paper trail — use an app '
                    + 'password, never your main one. A webhook posts JSON to an endpoint you control, '
                    + 'which is the hook for anything the built-in channels do not cover (Slack, '
                    + 'Discord, your own script).' },
                { note: 'Nothing is sent unless you configure a channel **and** tick it on the rules '
                    + 'that should use it. Credentials live in your local config file, are never '
                    + 'displayed back, and go only to the service you configured.' },
            ],
            actions: [
                { label: 'Open Alerts', kind: 'view', value: 'alerts' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
            ],
            links: [
                { label: 'Telegram @BotFather', url: 'https://t.me/BotFather' },
                { label: 'ntfy', url: 'https://ntfy.sh' },
            ],
            related: ['view.alerts', 'data.security', 'under.api'],
        },
        {
            id: 'connect.bridges', group: 'connect', mode: 'both',
            title: 'Do you need a platform bridge?',
            tags: ['bridge', 'dtc', 'platform', 'do i need', 'requirements'],
            summary: 'Short answer: no, unless you already run one of those platforms and want its '
                + 'data here. The Platforms view lists the requirements and prices honestly, including '
                + 'which package tier unlocks external connections.',
            blocks: [
                { p: 'The bridges connect this program to an external data or trading platform when '
                    + 'that platform is your primary environment: the panel inside the app compares '
                    + 'what each requires against what this program does on its own.' },
                { note: 'If what you want is order-flow data, the keyless venues and your own MT5 '
                    + 'terminal already cover it. A bridge buys you the other platform\'s specific '
                    + 'data, not a better version of what is here.' },
            ],
            actions: [
                { label: 'Open Platforms', kind: 'view', value: 'platforms' },
                { label: 'Help: data sources', kind: 'topic', value: 'start.sources' },
            ],
            related: ['view.platforms', 'start.sources'],
        },

        /* ═══════════ Data, files and storage (advanced) ═══════════ */
        {
            id: 'data.config_file', group: 'data', mode: 'advanced',
            title: 'Your settings file (config.json)',
            tags: ['config', 'json', 'settings file', 'backup', 'reset', 'apdata'],
            aliases: ['where are my settings', 'config location', 'user folder'],
            summary: 'Everything the program remembers — instruments, thresholds, keys, layouts, '
                + 'window positions, help preferences — lives in one JSON file under your user '
                + 'profile. Never in the program folder, never in the repository.',
            blocks: [
                { h: 'The file', list: [
                    '**Location** — `%APPDATA%\\OrderFlowAnalysisPro\\config.json` (the About card and '
                    + 'the system checkprint the exact path on this machine).',
                    '**Written atomically** — a partial write can never leave a broken file behind; the '
                    + 'app writes a temporary file and replaces the original.',
                    '**Clamped on read and write** — a hand-edited value that is not legal falls back '
                    + 'to the default instead of breaking a panel. Enum values (theme, source, help '
                    + 'mode) are checked against the list of what this build supports.',
                ] },
                { h: 'Backup and restore', p: 'Copy the file to back up your setup — instruments, '
                    + 'thresholds, layouts, drawn figures, alert rules — and copy it back to restore. '
                    + 'It is the whole state of the program apart from the tick database.' },
                { h: 'Reset', p: '**Reset to defaults** in Settings writes a fresh file from the '
                    + 'shipped defaults; the previous file is kept alongside it, so a reset is '
                    + 'recoverable. Nothing else on the machine is touched.' },
                { warn: 'The file holds credentials if you configured any (Telegram token, Alpaca keys, '
                    + 'SMTP password, webhook URL). Treat a copy of it as a secret. The control API '
                    + 'never returns those values — it redacts them on read.' },
            ],
            actions: [
                { label: 'Open the config folder', kind: 'folder', value: 'config' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
            ],
            related: ['data.folders', 'data.security', 'under.diagnostics'],
        },
        {
            id: 'data.folders', group: 'data', mode: 'advanced',
            title: 'The folders this program uses',
            tags: ['folders', 'paths', 'log', 'database', 'exports', 'user folder'],
            aliases: ['where does it write', 'file locations'],
            summary: 'Four places on your machine, and the reason each exists. The About card prints '
                + 'the real paths for this install.',
            blocks: [
                { table: [
                    ['Config', '`%APPDATA%\\OrderFlowAnalysisPro` — settings, layouts, drawings, alert '
                        + 'rules, exports subfolder.'],
                    ['Log', '`orderflow.log` in the same folder, rotated, plus the live in-memory tail '
                        + 'the Logs view shows.'],
                    ['Database', '`orderflow_data.db` (SQLite, with its WAL files) — the ticks and the '
                        + 'detection history. This is the file that grows.'],
                    ['Program folder', 'The application itself: the packaged app\'s own directory, or '
                        + 'the repository when running from source. Read-only by design — nothing you '
                        + 'change in the app is written here.'],
                ] },
                { note: 'Two menu items open them for you: **File ▸ Open user folder** and **File ▸ Open '
                    + 'exports folder**. **File ▸ Show log file** opens the log\'s folder and switches '
                    + 'to the Logs view.' },
            ],
            actions: [
                { label: 'Open the config folder', kind: 'folder', value: 'config' },
                { label: 'Open the logs folder', kind: 'folder', value: 'logs' },
                { label: 'Open the exports folder', kind: 'folder', value: 'exports' },
            ],
            related: ['data.config_file', 'data.storage', 'data.logs'],
        },
        {
            id: 'data.storage', group: 'data', mode: 'advanced',
            title: 'Ticks, retention and the database',
            tags: ['storage', 'database', 'sqlite', 'retention', 'prune', 'disk space', 'size'],
            aliases: ['db size', 'delete old data', 'storage settings'],
            summary: 'While the engine runs it records ticks locally. Retention deletes the oldest '
                + 'automatically, on a schedule, so the file stays a working size instead of growing '
                + 'until the disk notices.',
            blocks: [
                { h: 'The knobs', table: [
                    ['retention days', 'How long ticks are kept (7 by default). **0 keeps everything** — '
                        + 'which is a decision, not a default.'],
                    ['prune interval', 'How often the retention pass runs while the engine is up (6 '
                        + 'hours by default).'],
                    ['session start hour', 'Where a trading session begins, in UTC, which is what the '
                        + 'session-scoped views (CVD, profile, delta) call "today".'],
                ] },
                { h: 'What is stored and what is not', list: [
                    '**Stored**: trades/ticks, closed candles, and detections (when history is enabled).',
                    '**Not stored**: the order book. Depth is live-only; the heatmap keeps its own '
                    + 'window in memory.',
                    'The detection history is what makes the Alerts view and its log survive a '
                    + 'restart.',
                ] },
                { p: 'The **Storage** numbers (file size, row counts, oldest and newest tick, the last '
                    + 'prune) are on the Logs view\'s storage chip and in Settings. A prune can be run '
                    + 'by hand; it needs a running engine because it uses the live database handle '
                    + 'rather than opening a second writer.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
            ],
            related: ['view.replay', 'data.folders', 'under.architecture'],
        },
        {
            id: 'data.logs', group: 'data', mode: 'advanced',
            title: 'The log file and client errors',
            tags: ['log file', 'rotation', 'client error', 'crash', 'audit'],
            aliases: ['error log', 'what happened'],
            summary: 'One rotating log file for the engine and the app, and a second channel for '
                + 'errors raised inside the interface itself.',
            blocks: [
                { list: [
                    'Engine and app lines carry a level (INFO · WARNING · ERROR) and a timestamp; the '
                    + 'Logs view filters them and the file keeps the whole history.',
                    '**Client errors** — anything the interface itself raised — are reported back to '
                    + 'the same log with a `client error:` prefix. That is deliberate: a panel that '
                    + 'throws in the browser would otherwise be invisible in a packaged app.',
                    '**Clear** empties the view, and **Tools ▸ Copy diagnostics** gathers the parts '
                    + 'worth attaching to a report.',
                ] },
                { note: 'Logs never contain your keys: the app redacts credentials before they reach '
                    + 'anything that writes to disk or to the screen.' },
            ],
            actions: [
                { label: 'Open Logs', kind: 'view', value: 'logs' },
                { label: 'Open the logs folder', kind: 'folder', value: 'logs' },
                { label: 'Reporting a problem', kind: 'topic', value: 'support.report' },
            ],
            related: ['support.report', 'view.logs', 'under.diagnostics'],
        },
        {
            id: 'data.security', group: 'data', mode: 'advanced',
            title: 'How the program is exposed',
            tags: ['security', 'loopback', 'lan', 'localhost', 'keys', 'privacy', 'csp', 'redaction'],
            aliases: ['is it safe', 'network exposure', 'privacy'],
            summary: 'The app runs a local web server and a native window on the same machine. By '
                + 'default only this machine can reach it, a foreign page cannot drive it, and no '
                + 'credential is ever displayed back.',
            blocks: [
                { h: 'The rules the app enforces about itself', list: [
                    '**Loopback by default** — the server binds 127.0.0.1. Requests whose Host header is '
                        + 'not a loopback name are answered 403, and a cross-site request that tries to '
                        + 'make the app *do* something is refused even from the same machine.',
                    '**Serving the LAN is opt-in** — changing `dashboard.host` to an interface address '
                        + 'is the only way to expose it, and the system check tells you when that '
                        + 'choice is active.',
                    '**Credentials are redacted on read** — the API never returns a stored key, token '
                        + 'or password; the interface shows a masked placeholder.',
                    '**Fetched content is confined** — external fetches (news, market context, filings) '
                        + 'are http(s) only with a byte cap, and the page itself may load nothing from '
                        + 'another host, so injected content has nowhere to send anything.',
                ] },
                { p: 'Market data goes out as plain public requests to the venue you selected; nothing '
                    + 'is sent to the author of this program, and there is no telemetry of any kind.' },
            ],
            actions: [
                { label: 'Help: the config file', kind: 'topic', value: 'data.config_file' },
                { label: 'Run the system check', kind: 'check', value: '' },
            ],
            related: ['data.config_file', 'under.api', 'under.build'],
        },

        /* ═══════════ Under the hood (advanced) ═══════════ */
        {
            id: 'under.architecture', group: 'under', mode: 'advanced',
            title: 'How the pieces fit together',
            tags: ['architecture', 'engine', 'analytics', 'how it works', 'pipeline', 'python', 'webview'],
            aliases: ['how does it work', 'internals'],
            summary: 'One Python process: a FastAPI server, the streaming engine and its analytics, and '
                + 'a native window showing a local web interface. Everything is computed on this '
                + 'machine.',
            blocks: [
                { h: 'The path a print takes', list: [
                    'The **feed adapter** subscribes the venue (websocket, with REST for snapshots and '
                    + 'history) and normalises every message into one internal shape.',
                    'The **pipeline** per instrument folds trades into candles, keeps the per-price '
                    + 'volume buckets, and hands each event to the analytics: absorption, initiative, '
                    + 'sweep, exhaustion, divergence, the profile, the trackers, the delta series.',
                    'The **server** pushes updates to the interface over a websocket and serves the '
                    + 'REST surface the panels read on demand.',
                    'The **interface** is plain JavaScript and canvas — no framework, no build step — '
                    + 'so a panel is a file you can read.',
                ] },
                { h: 'Why it is built this way', p: 'Local-first: no account, no cloud, no telemetry, '
                    + 'and the whole state on your disk. The same Python process also runs headless, '
                    + 'which is how the automated tests exercise the real pipeline instead of a mock.' },
            ],
            actions: [
                { label: 'Help: the HTTP surface', kind: 'topic', value: 'under.api' },
                { label: 'Help: storage', kind: 'topic', value: 'data.storage' },
            ],
            related: ['under.api', 'data.storage', 'under.build'],
        },
        {
            id: 'under.api', group: 'under', mode: 'advanced',
            title: 'The local HTTP surface',
            tags: ['api', 'endpoints', 'rest', 'websocket', 'http', 'automation'],
            aliases: ['rest api', 'local server', 'port'],
            summary: 'The same interface the window uses is a plain HTTP API on your machine, which is '
                + 'why the app can also be driven headless, scripted, or opened in a browser.',
            blocks: [
                { list: [
                    '**/api/control/…** — the desktop control surface: config, engine start/stop, the '
                        + 'panels\' data, the storage numbers, the windows, the help report.',
                    '**/api/atlas/…** — the analysis surface: footprint, depth map, tracker detections, '
                        + 'profile, frames, replay.',
                    '**Interactive docs** — FastAPI serves its own schema at `/docs` while the app is '
                        + 'running, so the exact shape of any answer is readable rather than guessed.',
                    '**Websocket** — one connection carries the live stream to the window; the WS pill '
                        + 'in the top bar is its state.',
                ] },
                { p: 'Because it is HTTP on a loopback port, a script can start the engine, pull the '
                    + 'tape and read the footprint without the window — which is also how the '
                    + 'documentation screenshots are taken.' },
            ],
            actions: [
                { label: 'Help: how it is exposed', kind: 'topic', value: 'data.security' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
            ],
            related: ['data.security', 'under.architecture', 'under.build'],
        },
        {
            id: 'under.build', group: 'under', mode: 'advanced',
            title: 'Source, frozen build, installer',
            tags: ['build', 'exe', 'installer', 'pyinstaller', 'source', 'version', 'release'],
            aliases: ['packaging', 'standalone', 'how is it shipped'],
            summary: 'Three shapes of the same program: run from source, a frozen .exe you can copy '
                + 'anywhere, and an installer that puts it under your user profile with a desktop '
                + 'shortcut.',
            blocks: [
                { list: [
                    '**From source** — a Python environment with the project\'s dependencies; the entry '
                        + 'point is the same one the packaged build uses.',
                    '**Frozen** — one executable carrying Python, the server and the interface. No '
                        + 'Python needed on the machine. All state still goes to your user profile.',
                    '**Installed** — the installer is per-user (no administrator prompt), installs '
                        + 'under `%LOCALAPPDATA%\\Programs`, and creates a desktop shortcut. '
                        + 'Uninstalling removes the program and leaves your settings and data alone.',
                ] },
                { note: 'The About card says which shape this is (`frozen: true/false`), alongside the '
                    + 'version and the Python it is running on — the first thing a bug report needs.' },
            ],
            actions: [
                { label: 'About this program', kind: 'about', value: '' },
                { label: 'Open the program folder', kind: 'folder', value: 'app' },
            ],
            related: ['under.diagnostics', 'data.folders', 'support.report'],
        },
        {
            id: 'under.diagnostics', group: 'under', mode: 'advanced',
            title: 'Diagnostics and telemetry',
            tags: ['diagnostics', 'telemetry', 'frame time', 'performance counters', 'support bundle'],
            aliases: ['render telemetry', 'copy diagnostics'],
            summary: 'The program measures itself: frame time, level of detail, cell counts, recovery '
                + 'counts, and the client-error channel. **Tools ▸ Render telemetry** prints the '
                + 'current numbers; **Copy diagnostics** puts the useful summary on the clipboard.',
            blocks: [
                { h: 'What the numbers mean', table: [
                    ['frame time', 'Median / p95 / max milliseconds per painted frame while the engine '
                        + 'view is live. A healthy machine sits at the display\'s refresh interval.'],
                    ['LOD', 'Which level of detail the engine is currently drawing — the honest label '
                        + 'for how much is being summarised rather than drawn.'],
                    ['cells / bars', 'How much is actually on screen, which is what the frame time '
                        + 'depends on.'],
                    ['recoveries', 'How many times the renderer had to re-fit or rebuild rather than '
                        + 'paint incrementally. A number that climbs during ordinary work is worth '
                        + 'reporting.'],
                ] },
                { p: 'A support bundle is a copy of the diagnostics plus the log tail plus the config '
                    + 'file **with credentials redacted** — the report instructions in *Reporting a '
                    + 'problem* walk through it.' },
            ],
            actions: [
                { label: 'Copy diagnostics', kind: 'copy', value: 'diagnostics' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
                { label: 'Reporting a problem', kind: 'topic', value: 'support.report' },
            ],
            related: ['support.report', 'data.logs', 'fix.slow'],
        },
        {
            id: 'under.danger', group: 'under', mode: 'advanced',
            title: 'The things that change or delete data',
            tags: ['danger', 'reset', 'prune', 'clear', 'delete', 'uninstall', 'wipe'],
            aliases: ['destructive actions', 'start over'],
            summary: 'Four actions can lose something. Each one is deliberate, each one is reversible '
                + 'or explained here, and none of them touches anything outside this program\'s own '
                + 'files.',
            blocks: [
                { h: 'What each one does', table: [
                    ['Reset to defaults (Settings)', 'Rewrites your config from the shipped numbers. '
                        + 'The drawings, layouts, alert rules and instruments you set up go back to '
                        + 'default. The previous file is kept beside the new one, so it is '
                        + 'recoverable.'],
                    ['Prune storage now', 'Deletes ticks older than the retention window immediately '
                        + 'instead of waiting for the schedule. The window is what it is because you '
                        + 'set it; nothing inside the window is touched.'],
                    ['Clear the log', 'Empties the in-memory log view. The log file on disk is not '
                        + 'truncated, so nothing is truly lost — it is a view-clearing action.'],
                    ['Uninstall', 'Removes the program. Your config, database and exports are left in '
                        + 'place: reinstalling finds your setup again. Delete that folder yourself if '
                        + 'you want a true clean slate.'],
                ] },
                { warn: 'The one that bites: **Reset to defaults** on a machine where you spent an '
                    + 'afternoon tuning thresholds and drawing levels. Copy `config.json` to a backup '
                    + 'file first — it is one file and it is the whole setup.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Open the config folder', kind: 'folder', value: 'config' },
            ],
            related: ['data.config_file', 'data.storage', 'under.diagnostics'],
        },

        /* ═══════════ Fixes and support ═══════════ */
        {
            id: 'fix.no_data', group: 'fix', mode: 'both',
            title: 'A panel has no data, or the numbers stopped moving',
            tags: ['no data', 'stale', 'not updating', 'frozen', 'empty panel', 'demo', 'broken'],
            aliases: ['nothing shows', 'panels are blank', 'stuck'],
            summary: 'Nine times out of ten this is one of four things, and the app already says which: '
                + 'the engine is stopped, the engine has no instruments, the chosen source cannot '
                + 'serve this symbol, or the feed went quiet.',
            blocks: [
                { h: 'Read these three things first', list: [
                    'The **data pill** in the top bar: live, warming, or demo. Demo means the engine is '
                    + 'not feeding this panel and the numbers are illustrative.',
                    'The **freshness chip** on the panel itself: it says how old the newest sample is '
                    + 'and names which panel it belongs to.',
                    'The **WS pill**: if the socket is down the engine may be fine and only the '
                    + 'drawing is starved — the log will say so.',
                ] },
                { h: 'Then the common causes', table: [
                    ['Engine stopped', 'Press ▶ Start.'],
                    ['No instruments enabled', 'Instruments → tick one. The system check flags this as '
                        + 'an error because the engine really can stream nothing.'],
                    ['Source cannot serve it', 'The venue does not list that symbol — Validate against '
                        + 'the venue in Instruments catches it. Symbols skipped at start are named in '
                        + 'the log.'],
                    ['The market itself needs another source', 'An exchange feed is crypto-only: a name '
                        + 'like NQ, US100 or GOLD can never stream from Bybit/Binance/OKX/Hyperliquid. '
                        + 'Type it into the Engine view\'s symbol box and press **find** — the look-up '
                        + 'says which source can serve it and how to switch.'],
                    ['Depth-only panels on a bookless source', 'Alpaca publishes no order book: the '
                        + 'heatmap and the ladder need the venue feed.'],
                    ['Engine running, no prints', 'A quiet market, a blocked network, or the venue '
                        + 'changed something. The Logs view at WARNING level says which.'],
                ] },
                { note: 'A panel that is wrongly *empty* is a different bug from a panel that is stale — '
                    + 'the freshness chip distinguishes them for you.' },
            ],
            actions: [
                { label: 'Run the system check', kind: 'check', value: '' },
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
            ],
            related: ['fix.engine_error', 'fix.skipped_symbols', 'view.logs', 'support.syscheck'],
        },
        {
            id: 'fix.engine_error', group: 'fix', mode: 'both',
            title: 'The engine stopped with an error',
            tags: ['engine error', 'crash', 'stopped', 'exception', 'why did it stop'],
            summary: 'The engine says what stopped it. The top bar carries the short version; the Logs '
                + 'view holds the full trace, and the system check repeats it with the panel that '
                + 'explains the fix.',
            blocks: [
                { steps: [
                    { t: 'Read the error where it is', d: 'Open **Logs**, filter to ERROR. The last '
                        + 'line before the stop is usually the whole story: a symbol the venue '
                        + 'rejected, a network failure, or a bad value in the config.' },
                    { t: 'Try the cheap fix first', d: 'Press the restart button. A feed that dropped '
                        + 'mid-session recovers on a fresh start more often than not.' },
                    { t: 'Check what changed', d: 'If it started after you edited settings, the config '
                        + 'file is the suspect — **Reload** in Settings or restore your backup.' },
                    { t: 'If it repeats', d: 'Copy the diagnostics and the log tail into a report; both '
                        + 'are safe to paste.' },
                ] },
                { note: 'The app tries to keep the engine\'s failure away from the interface: a crashed '
                    + 'feed shows as panels that stop updating rather than a frozen window, and the '
                    + 'state pill says the engine is down.' },
            ],
            actions: [
                { label: 'Open Logs', kind: 'view', value: 'logs' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Reporting a problem', kind: 'topic', value: 'support.report' },
            ],
            related: ['view.logs', 'fix.no_data', 'support.report'],
        },
        {
            id: 'fix.skipped_symbols', group: 'fix', mode: 'both',
            title: 'Instruments were skipped at start',
            tags: ['skipped', 'symbol not found', 'unsubscribe', 'missing data'],
            summary: 'The engine subscribes what the source can serve; anything it cannot is listed '
                + 'with a reason instead of quietly streaming nothing.',
            blocks: [
                { list: [
                    '**Check the spelling** — Instruments ▸ Validate against the venue is the honest '
                        + 'test, not a guess.',
                    '**MT5 instruments need your broker\'s name** — an empty mapping is the usual '
                        + 'cause; see *Mapping MT5 symbols*.',
                    '**The venue may have delisted it** — a symbol that exists in your config but no '
                        + 'longer exists at the venue will be skipped every start until you remove it.',
                ] },
                { list: [
                    '**A start that skips something says so** — the banner names the first symbol '
                    + 'and its reason, with a button straight into the look-up.',
                    '**The look-up answers the name you typed** (Engine view ▸ symbol chip / find, '
                    + 'or Data ▸ Instrument look-up…): it names the row, the reason and the '
                    + 'action — enable, remap the broker symbol, or switch source.',
                ] },
                { p: 'The system check lists the skipped symbols and points at the log for each '
                    + 'reason, so this is a two-click diagnosis rather than a hunt.' },
            ],
            actions: [
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
            ],
            related: ['view.instruments', 'connect.mt5_map', 'fix.no_data'],
        },
        {
            id: 'fix.no_instruments', group: 'fix', mode: 'both',
            title: 'Nothing is enabled in Instruments',
            tags: ['no instruments', 'empty engine', 'nothing streaming', 'config error'],
            summary: 'With an empty instrument list the engine starts and streams nothing — the most '
                + 'common "it is running but nothing happens".',
            blocks: [
                { list: [
                    '**Instruments ▸ Enable all supported** ticks everything the current source can '
                        + 'serve in one action.',
                    'Or tick one instrument and restart the engine from the top bar.',
                    'If the list is empty of *instruments* (not just unticked), restore the shipped '
                        + 'defaults with **Settings ▸ Reset to defaults**, or import a venue\'s list '
                        + 'from the setup assistant.',
                ] },
                { note: 'The system check reports this as an **error** rather than a notice, because it '
                    + 'is one: a running engine with nothing subscribed is indistinguishable from a '
                    + 'broken feed until you look here.' },
            ],
            actions: [
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
                { label: 'Run the setup assistant', kind: 'wizard', value: '' },
            ],
            related: ['view.instruments', 'start.first_run', 'fix.no_data'],
        },
        {
            id: 'fix.stale_window', group: 'fix', mode: 'both',
            title: 'The window shows an old version of the interface',
            tags: ['stale', 'old build', 'relaunch', 'modules not loaded', 'blank panel', 'cache'],
            summary: 'The window keeps the code it loaded when it opened. After an update — or if a '
                + 'panel reports a missing module — the fix is to close and reopen the app, not to '
                + 'change anything.',
            blocks: [
                { list: [
                    '**Close the window and start the app again.** A panel that says a module is '
                        + 'missing, or a view that is blank with the rest working, is almost always '
                        + 'this.',
                    'The interface is served **no-store** on purpose: once the app has been relaunched, '
                        + 'a surviving symptom is a real defect rather than a cached one. The log\'s '
                        + '`client error:` lines are then the place to look.',
                    'A **fresh install or update** replaces the program files; your settings and data '
                        + 'are untouched, so a relaunch costs nothing.',
                ] },
                { note: 'Two adjacent symptoms that are *not* this: a panel that is empty because the '
                    + 'engine is stopped (see the data pill) and a canvas mid-resize (move the window '
                    + 'once).' },
            ],
            actions: [
                { label: 'Open Logs', kind: 'view', value: 'logs' },
                { label: 'Reporting a problem', kind: 'topic', value: 'support.report' },
            ],
            related: ['support.report', 'data.logs', 'work.display'],
        },
        {
            id: 'fix.slow', group: 'fix', mode: 'both',
            title: 'The program feels slow',
            tags: ['slow', 'lag', 'stutter', 'cpu', 'frame rate', 'performance', 'heavy'],
            aliases: ['laggy', 'sluggish', 'high cpu'],
            summary: 'Almost always the same three causes: too much on screen at once, a display at a '
                + 'high scale with several panels live, or a very wide instrument list recording every '
                + 'tick.',
            blocks: [
                { h: 'In order of effect', list: [
                    '**Fewer live panels.** Every visible panel is work. Terminal mode with ten widgets '
                        + 'is ten times one panel; close what you are not reading.',
                    '**Density and range.** A heatmap at 300 rows × 15 minutes is 4,500 cells per '
                        + 'repaint; a smaller window answers immediately.',
                    '**Instruments.** Each enabled instrument is a subscription, a pipeline and disk '
                        + 'writes. Disable the ones you are not watching.',
                    '**Retention.** A database measured in gigabytes slows the first reads of a '
                        + 'session; a prune or a shorter window fixes it.',
                    '**Pause.** **P** holds every background refresh while you work on something else.',
                ] },
                { p: 'If it is still slow with one panel and one instrument, that is worth reporting '
                    + 'with the telemetry numbers — they are measured precisely so a real defect can be '
                    + 'told apart from a loaded screen.' },
            ],
            actions: [
                { label: 'Copy diagnostics', kind: 'copy', value: 'diagnostics' },
                { label: 'Tools: render telemetry', kind: 'menu', value: 'tools' },
                { label: 'Help: storage', kind: 'topic', value: 'data.storage' },
            ],
            related: ['under.diagnostics', 'data.storage', 'work.pause'],
        },
        {
            id: 'support.report', group: 'fix', mode: 'both',
            title: 'Reporting a problem (and what to include)',
            tags: ['report', 'bug', 'support', 'diagnostics', 'attach', 'help me'],
            aliases: ['submit a bug', 'contact support'],
            summary: 'Three things make a report actionable: what you did, what happened instead, and '
                + 'the diagnostics. The program gathers the third itself, with nothing secret in it.',
            blocks: [
                { steps: [
                    { t: 'Note the version', d: 'The About card (Help ▸ About) prints the version, '
                        + 'whether this is the packaged build, the Python it runs on and the exact '
                        + 'paths — the first three lines of any useful report.' },
                    { t: 'Copy the diagnostics', d: '**Tools ▸ Copy diagnostics** puts a summary on the '
                        + 'clipboard: version, paths, source, engine counters, render telemetry. Keys '
                        + 'are never included.' },
                    { t: 'Grab the log tail', d: 'The Logs view filtered to WARNING/ERROR, or the log '
                        + 'file itself. The last few lines before the symptom are usually the whole '
                        + 'answer.' },
                    { t: 'Say what you were doing', d: 'Which panel, which instrument, which source, '
                        + 'and whether it is reproducible. "The heatmap was empty after I switched to '
                        + 'Alpaca" is a diagnosis; "the app is broken" is a hunt.' },
                ] },
                { note: 'If the app was updated recently, mention it and relaunch once first: a window '
                    + 'holding old interface code produces symptoms no code reading can explain — see '
                    + '*"The window shows an old version of the interface"*.' },
            ],
            actions: [
                { label: 'About this program', kind: 'about', value: '' },
                { label: 'Copy diagnostics', kind: 'copy', value: 'diagnostics' },
                { label: 'Open Logs', kind: 'view', value: 'logs' },
            ],
            links: [{ label: 'moddys.net', url: 'https://moddys.net' }],
            related: ['under.diagnostics', 'data.logs', 'fix.stale_window'],
        },
        {
            id: 'support.syscheck', group: 'fix', mode: 'both',
            title: 'What the system check looks at',
            tags: ['system check', 'health', 'warnings', 'diagnose', 'errors'],
            aliases: ['health check', 'what is wrong'],
            summary: 'The Simple interface opens on a live check of the whole program: configuration '
                + 'errors and irregularities, worst first, each naming the one thing to do about it. '
                + 'The same check is readable from the Advanced interface.',
            blocks: [
                { check: true },
                { note: 'Nothing is guessed: every row is derived from the running state, the config '
                    + 'file, the log tail and the database file, and a row that names a setting names '
                    + 'the panel that owns it. Dismissing a row hides it until the condition changes.' },
            ],
            actions: [
                { label: 'Run the system check', kind: 'check', value: '' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
            ],
            related: ['fix.no_data', 'fix.engine_error', 'data.config_file'],
        },

        /* ═══════════ Reading the market ═══════════ */
        {
            id: 'method.reading_order', group: 'method', mode: 'both',
            title: 'The reading order: profile first, then order flow',
            tags: ['reading order', 'workflow', 'how to trade', 'method', 'profile first',
                   'confirmation', 'playbook'],
            aliases: ['how to read this', 'trading workflow'],
            summary: 'The order-flow workflow this program follows: direction and levels come from the '
                + 'profile, a level is chosen before any order flow is read, and only then does a '
                + 'confirmation at that level mean anything. Every panel is arranged around it.',
            blocks: [
                { h: 'The three steps', p: '**First, the profile decides.** The session\u2019s volume '
                    + 'profile \u2014 its shape (P, b, D, thin) and its value area \u2014 says who is '
                    + 'in control and where the heavy prices are; that is the bias the Profile view '
                    + 'and its shape read show. **Second, choose one level** \u2014 POC, value-area '
                    + 'edge, a node, an unfinished extreme, a band: see \u201cThe level sources\u201d. '
                    + '**Third, wait for order flow at that level** \u2014 absorption, a wall, a '
                    + 'failed break \u2014 which the confirmations topic describes.' },
                { list: [
                    '**Profile first** \u2014 Profile view: shape badge, story, POC / VAH / VAL, the '
                    + 'weekly and monthly POC ladder.',
                    '**Choose the level** \u2014 the level-sources topic lists every family and which '
                    + 'panel draws it.',
                    '**Confirm at the level** \u2014 the confirmations topic; the Rules card scopes any '
                    + 'alert to a single level with \u201cat this price\u201d.',
                    '**One test per level** \u2014 the first-test topic, and the radar states that '
                    + 'count tests for you.',
                ] },
                { warn: 'Reversed, the order turns noise into reasons: order flow is interesting '
                    + 'everywhere, and only meaningful where you had already decided to watch.' },
            ],
            actions: [
                { label: 'Open the Profile view', kind: 'view', value: 'profile' },
                { label: 'The level sources', kind: 'topic', value: 'method.levels' },
            ],
            related: ['method.levels', 'method.confirmations', 'view.profile'],
        },
        {
            id: 'method.confirmations', group: 'method', mode: 'both',
            title: 'Confirmations at a level you chose',
            tags: ['absorption', 'limit orders', 'confirmation', 'walls', 'depth', 'intent',
                   'side convention'],
            aliases: ['how to confirm', 'absorption read'],
            summary: 'The two confirmations the workflow waits for at a chosen level \u2014 resting '
                + 'liquidity (limit orders) and absorption \u2014 and the side convention that makes '
                + 'them readable.',
            blocks: [
                { h: 'The side convention', p: 'Aggressive (market) orders show on the side they hit: '
                    + 'buys on the ask, sells on the bid. **Limit orders sit on the opposite side of '
                    + 'their intent**: a large limit sell rests on the ask at resistance, a large '
                    + 'limit buy rests on the bid at support. When you look for a wall at a level, '
                    + 'look on that side of the ladder.' },
                { h: 'Resting liquidity', p: 'Size that stays at a level \u2014 refuses to be eaten, '
                    + 'refills after a bite, or simply holds for minutes \u2014 is liquidity '
                    + 'defending it. In the app: the Heatmap\u2019s walls and its \u201cif this '
                    + 'level holds\u201d alert, and the Eaten / Refilled columns in the Scanner.' },
                { h: 'Absorption', p: 'Unusually heavy volume printing on **both** sides at the '
                    + 'level while price stops moving is aggression being absorbed \u2014 the turn '
                    + 'read. In the app: the Absorb column, the absorption score card, and the '
                    + 'absorption alert kind.' },
                { note: 'Scope it: a confirmation only counts at the level you chose. The Rules card '
                    + 'takes \u201cat this price\u201d, so an alert can watch one level and ignore '
                    + 'the same print everywhere else.' },
            ],
            actions: [
                { label: 'Open the Heatmap', kind: 'view', value: 'heatmap' },
                { label: 'Open Alerts', kind: 'view', value: 'alerts' },
            ],
            related: ['method.reading_order', 'method.first_test', 'view.heatmap'],
        },
        {
            id: 'method.first_test', group: 'method', mode: 'both',
            title: 'Trade a level once',
            tags: ['first test', 'spent level', 'virgin poc', 'retest', 'level discipline'],
            aliases: ['one test', 'second test'],
            summary: 'The first test of a level carries the edge; re-tests are worth less. The '
                + 'program keeps the counters for you \u2014 virgin POCs, first-test alerts, and '
                + 'spent levels that stay visible only as context.',
            blocks: [
                { p: 'A level\u2019s first revisit is where the resting orders and the trapped '
                    + 'positions are; by the second and third test both sides have seen it. The '
                    + 'discipline is to trade the first test and read the rest as information.' },
                { list: [
                    '**Virgin POCs** \u2014 the Profile view flags POCs no later session has traded '
                    + 'through: the cleanest untested levels.',
                    '**First test, counted** \u2014 when a radar level is defended on its first '
                    + 'test the alert says so: \u201cheld \u2014 first test\u201d.',
                    '**Spent levels** \u2014 traded through, they dim and then expire from the '
                    + 'radar instead of pulling you back in: \u201cspent \u2014 traded '
                    + 'through\u201d.',
                    '**A level that held once and then broke** is a *failed* level, and the radar '
                    + 'says exactly that \u2014 the classic second-test break.',
                ] },
            ],
            actions: [
                { label: 'Open the Profile view', kind: 'view', value: 'profile' },
                { label: 'The level radar', kind: 'topic', value: 'method.radar' },
            ],
            related: ['method.radar', 'method.levels', 'view.profile'],
        },
        {
            id: 'method.levels', group: 'method', mode: 'both',
            title: 'The level sources, and which is which',
            tags: ['levels', 'poc', 'node', 'unfinished business', 'vwap bands', 'stacked imbalance',
                   'confluence'],
            aliases: ['what is a level', 'level types'],
            summary: 'Every family of level this program computes \u2014 POCs, nodes, unfinished '
                + 'extremes, bands, stacked zones, area POCs \u2014 what each one means, and the one '
                + 'list they all feed.',
            blocks: [
                { list: [
                    '**POC and value area** \u2014 the session\u2019s heaviest price and the band '
                    + 'holding the bulk of its volume: acceptance. A virgin POC has not been '
                    + 're-tested yet.',
                    '**The POC ladder** \u2014 the same computation over weeks and months; where '
                    + 'daily, weekly and monthly POCs coincide, that is the strongest kind of level.',
                    '**Node runs** \u2014 consecutive bars whose heaviest price is the same: repeat '
                    + 'acceptance, drawn as double (2) and triple (3) bands.',
                    '**Unfinished business** \u2014 an extreme that never completed its auction (no '
                    + 'zero on the finishing side): a magnet price tends to revisit, and the line '
                    + 'clears itself when it does.',
                    '**VWAP bands and stacked zones** \u2014 fair value \u00b1 k\u03c3, and runs of '
                    + 'same-direction imbalance: where the book showed its hand.',
                    '**Area POCs** \u2014 profile any region you box on the Engine and watch its '
                    + 'point of control: the trend leg\u2019s cluster, or the rotation\u2019s heavy '
                    + 'line.',
                ] },
                { h: 'Confluence is the strong read', p: 'When two independent families sit at the '
                    + 'same price within a tick or two, the level is stronger than either alone '
                    + '\u2014 a band stacking on a POC, a node on an unfinished extreme. The radar '
                    + 'counts the sources for you, and marks a held level with two or more as '
                    + '*confirmed*.' },
                { shot: 'help/area-profile.png',
                  caption: 'Boxing a region on the Engine profiles it and hands its POC to the watch list.' },
            ],
            actions: [
                { label: 'Open the Engine', kind: 'view', value: 'ofx' },
                { label: 'The level radar', kind: 'topic', value: 'method.radar' },
            ],
            related: ['method.radar', 'method.first_test', 'view.ofx'],
        },
        {
            id: 'method.radar', group: 'method', mode: 'both',
            title: 'The level radar: armed, held, spent',
            tags: ['radar', 'level lifecycle', 'armed', 'approaching', 'defended', 'spent',
                   'failed', 'scanner column'],
            aliases: ['level states', 'what is arming where'],
            summary: 'Every tracked level on every instrument: the Scanner\u2019s Radar column and '
                + 'the lifecycle behind it \u2014 what each state means and what to do with it.',
            blocks: [
                { h: 'The states', p: '**Armed** \u2014 registered, price away from it. '
                    + '**Approaching** \u2014 price inside the approach band; the level is live. '
                    + '**Defended** \u2014 price tested it and left on the side it came from: the '
                    + 'level held. **Confirmed** \u2014 the same hold where two or more sources '
                    + 'agree. **Spent** \u2014 traded straight through without holding. '
                    + '**Failed** \u2014 it held once, then broke: the second-test break.' },
                { h: 'Reading the Scanner\u2019s Radar column', p: 'Each row shows that '
                    + 'instrument\u2019s levels in plain counts \u2014 e.g. \u201c2 armed '
                    + '\u00b7 1 approaching \u00b7 1 held\u201d \u2014 and sorts by what is '
                    + 'arming where. A quiet market reads \u201c0 armed \u00b7 0 approaching '
                    + '\u00b7 0 held\u201d; a busy one walks you to the instrument that needs '
                    + 'eyes.' },
                { h: 'The alerts, and the watch hand-off', p: 'Transitions fire as sentences into '
                    + 'the Inbox and Alerts: \u201cnew node level armed at \u2026\u201d, '
                    + '\u201c\u2026 held \u2014 first test\u201d, \u201c\u2026 spent \u2014 '
                    + 'traded through\u201d. The default rule interrupts only for held or '
                    + 'confirmed levels. And the Engine\u2019s area profile can hand one over: '
                    + '**Watch this level** turns the area POC into a watched level that fires '
                    + 'when price simply returns to it.' },
                { shot: 'help/scanner-radar.png',
                  caption: 'The Radar column on the Scanner: what every instrument is arming.' },
            ],
            actions: [
                { label: 'Open the Scanner', kind: 'view', value: 'scanner' },
                { label: 'Open Alerts', kind: 'view', value: 'alerts' },
            ],
            related: ['method.levels', 'method.first_test', 'method.reading_order'],
        },
        {
            id: 'method.vwap', group: 'method', mode: 'both',
            title: 'VWAP: fair value and the band playbook',
            tags: ['vwap', 'bands', 'deviation', 'rotation', 'trend', 'fair value'],
            aliases: ['vwap bands', 'deviation bands'],
            summary: 'VWAP as the magnet and the \u00b1k\u03c3 bands as the traded tool: flat bands '
                + 'mean rotation, sloped bands mean trend, and a band stacking on a profile level is '
                + 'the confluence read.',
            blocks: [
                { p: 'VWAP is the volume-weighted fair price of the session \u2014 the line price '
                    + 'tends to rotate around. The traded tool is the first (and second) deviation '
                    + 'band, \u00b1k\u03c3 away from it.' },
                { list: [
                    '**Flat bands \u2192 rotation** \u2014 sideways sessions: fade the band edges '
                    + 'back toward VWAP, which is the natural take-profit.',
                    '**Sloped bands \u2192 trend** \u2014 a trending session walks its band: enter '
                    + 'pullbacks *to* the band in the trend direction, exit at the line.',
                    '**Confluence** \u2014 a band sitting on a profile level (POC, value edge, '
                    + 'node) is the strongest version of either read.',
                ] },
                { note: 'The app computes session, anchored and \u00b1k\u03c3 bands (the Studies '
                    + 'panel\u2019s VWAP suite); the band pair also feeds the level radar, and the '
                    + 'VWAP-cross alert kind watches the line itself.' },
            ],
            actions: [
                { label: 'Open the Studies panel', kind: 'view', value: 'studies' },
                { label: 'Open the Scanner', kind: 'view', value: 'scanner' },
            ],
            related: ['method.levels', 'method.reading_order', 'view.studies'],
        },
        {
            id: 'view.depth-history', group: 'panels', mode: 'both',
            title: 'Depth history',
            tags: ['depth history', 'depth over time', 'liquidity', 'pull', 'stack', 'resting size',
                   'market depth historical graph'],
            aliases: ['depth over time', 'where did the liquidity go'],
            summary: 'Resting size over time: price rows, time along the bottom, brightness for size \u2014 '
                + 'plus the levels that were pulled or stacked while the market sat there.',
            blocks: [
                { h: 'How to read the strip', list: [
                    'Brightness is resting size: how much was sitting on that price at that moment. A hole means no depth was reported then \u2014 never zero size.',
                    'A filled dot marks a level that was **pulled** (size vanished without prints); a ring marks one that was **stacked** (size appeared). Both are read from the difference between two recorded columns, and both are candidates to look into, not verdicts.',
                    'The record starts when the engine starts, and only covers what retention keeps \u2014 the newest columns are always the ones on screen.',
                ] },
                { h: 'Controls', table: [
                    ['window', 'How much of the record the strip shows (5 / 15 / 30 / 60 minutes).'],
                    ['bucket', 'How much time one cell covers; a wider bucket smooths a busy book.'],
                    ['keep', 'How long columns are kept before pruning \u2014 the same number the settings block holds.'],
                    ['events', 'The pull and stack markers; turn them off to read pure resting size.'],
                    ['forget', 'Drops this instrument\'s recorded columns. Nothing outside this panel uses them.'],
                ] },
                { note: 'One column is kept per interval (default one second), bounded per instrument \u2014 a '
                    + 'day of history costs about a megabyte, not a gigabyte.' },
            ],
            actions: [{ label: 'Open Depth history', kind: 'view', value: 'depth-history' }],
            related: ['view.depth', 'method.levels'],
        },
        {
            id: 'view.sessions', group: 'panels', mode: 'both',
            title: 'Sessions',
            tags: ['sessions', 'session clock', 'rth', 'eth', 'globex', 'holidays', 'early close',
                   'roll date', 'expiry', 'is the market open'],
            aliases: ['when does the market open', 'when does it close', 'roll day', 'expiry day'],
            summary: 'Says which session a symbol is trading in, how long until it opens or closes, and '
                + 'when the futures contract rolls \u2014 from session templates you own, with holidays and '
                + 'breaks, not a guess.',
            blocks: [
                { p: 'The clock is the server\'s arithmetic, not the browser\'s: the panel re-reads the '
                    + 'session on its own cadence and counts the seconds down locally, so the state word '
                    + '(open, break, pre-open, post-close, holiday, closed) is always the program\'s answer '
                    + 'about the active symbol.' },
                { h: 'Templates', list: [
                    'The picker lists the built-in library and your own copies. **Copy into my templates** '
                    + 'appends a copy; **Set as active** makes the picked one the default every view reads.',
                    'A template is name, timezone, days of the week, open/close, optional breaks, optional '
                    + 'holidays and an optional exchange label. Shipping examples: crypto 24/7, US equities '
                    + 'RTH plus pre/post, CME Globex for index, energy and metals, Tokyo cash, and the '
                    + 'Sydney/London/New York FX day.',
                    'A symbol with no template says so rather than assuming \u2014 add one in Settings or copy '
                    + 'a built-in.',
                ] },
                { h: 'Rolls', list: [
                    'The roll table writes the convention beside every date: equity index rolls the Thursday '
                    + 'before the third Friday, energy expires three business days before the 25th of the '
                    + 'month before delivery, metals on the third-to-last business day, and a crypto '
                    + 'perpetual has no roll at all \u2014 only its next funding stamp.',
                    '**Days to roll** is highlighted from five days out, and each root prints its own rule, '
                    + 'so a date is never a number without the convention next to it.',
                ] },
                { note: 'An unknown timezone is read as UTC and the clock card says so \u2014 it never '
                    + 'silently pretends to know a market\'s hours.' },
            ],
            actions: [
                { label: 'Open Sessions', kind: 'view', value: 'sessions' },
                { label: 'Open Settings', kind: 'view', value: 'settings' },
            ],
            related: ['view.marketread', 'fix.no_data'],
        },
        {
            id: 'view.data-quality', group: 'method', mode: 'both',
            title: 'Is the stored history good enough to read?',
            tags: ['data quality', 'coverage', 'gap', 'duplicate stamps', 'stale', 'backfill', 'verdict'],
            aliases: ['is my data complete', 'missing bars', 'bad data'],
            summary: 'The Data quality view scores the history this program stored for each instrument '
                + '\u2014 coverage, gaps, duplicate and out-of-order stamps, staleness \u2014 gives it a '
                + 'letter, and names the one repair the program can actually do.',
            blocks: [
                { p: 'Coverage counts the cadence slots the venue expected over the window and how many of '
                    + 'them have a stored sample. The expectation is scaled to the instrument\'s own hours: '
                    + 'a stock is not missing anything on a Saturday night.' },
                { p: 'Gaps are runs of empty slots wider than a few cadence steps; the list gives the '
                    + 'wall-clock range, how many slots were empty, and how many rows sat inside the hole. '
                    + 'Duplicate stamps are counted as extra rows, out-of-order stamps as a stored-order '
                    + 'problem.' },
                { p: 'The repairs are the ones the program has a route for: refetch for a stale or thin '
                    + 'window, backfill for a named hole. A repair the program cannot do yet is printed as '
                    + 'a sentence, not a button.' },
                { p: 'A capped read (the read budget is per instrument) can never score an A \u2014 it did '
                    + 'not look at everything, and it says so.' },
            ],
            actions: [{ label: 'Open Data quality', kind: 'view', value: 'data-quality' }],
            related: ['fix.no_data', 'view.instruments'],
        },
        {
            id: 'view.derivatives', group: 'panels', mode: 'both',
            title: 'Funding and open interest',
            tags: ['funding', 'funding rate', 'open interest', 'oi', 'basis', 'perp', 'annualised',
                   'carry', 'crowded', 'bybit', 'binance', 'okx', 'hyperliquid'],
            aliases: ['funding rate', 'open interest', 'basis'],
            summary: 'Per-venue funding and its annualised rate, open interest and its change, and the '
                + 'perpetual\'s basis against its own index \u2014 with one plain sentence saying who is '
                + 'paying to hold.',
            blocks: [
                { p: 'Funding is the rate a perpetual\'s longs and shorts pay each other every settlement. '
                    + 'The panel annualises it through the venue\'s own interval (8 hours on Bybit and '
                    + 'Binance, read off OKX\'s next-funding stamp, hourly on Hyperliquid) \u2014 it is a '
                    + 'rate, not a yield.' },
                { p: 'Open interest is each venue\'s own figure in its own unit, with a USD total across '
                    + 'venues. The change is measured against **this program\'s own samples**: until it has '
                    + 'watched long enough the sentence says exactly what it saw, never zero.' },
                { p: 'The basis is the perp\'s mark against its index in basis points, annualised only as a '
                    + 'shorthand so venues can be compared.' },
                { note: 'Every endpoint is public and keyless (Bybit v5 tickers, Binance premiumIndex and '
                    + 'openInterest, OKX funding-rate / open-interest / mark-price / index-tickers, '
                    + 'Hyperliquid metaAndAssetCtxs). A venue that rate-limits or serves HTML keeps its row '
                    + 'and gets a sentence naming it.' },
            ],
            actions: [{ label: 'Open Funding & OI', kind: 'view', value: 'derivatives' }],
            related: ['view.gex', 'view.options'],
        },
        {
            id: 'view.synthetic', group: 'panels', mode: 'both',
            title: 'Synthetic instruments',
            tags: ['synthetic', 'spread', 'ratio', 'basket', 'basis', 'perp', 'relative value',
                   'cross-venue', 'arbitrage'],
            aliases: ['ratio chart', 'spread chart'],
            summary: 'Ratios, spreads, baskets and basis series composed from each leg\'s own stored '
                + 'candles \u2014 with a z-score against the window\'s own mean, and a sentence that says '
                + 'how rich or cheap the composite is right now.',
            blocks: [
                { h: 'Building one', list: [
                    'A definition is a name, a kind (ratio, spread, basket, basis) and its legs: a symbol, '
                    + 'a side (added or subtracted) and a weight. Three starters ship with the program \u2014 '
                    + 'an ETH/BTC ratio, a majors basket and a BTC-perp basis.',
                    'Every leg must have stored candles: a leg with no history is refused by name \u2014 '
                    + '"open its chart first" \u2014 rather than quietly charting one leg fewer.',
                ] },
                { h: 'Reading it', list: [
                    'The composite is the weighted sum of the aligned legs, on a grid you set. The '
                    + '\"carried forward\" figure says how much of each leg had to be filled in to align them.',
                    'The read compares the composite against the subtracted leg in basis points, or against '
                    + 'its own window median for a one-sided composite, and gives a z-score over the window '
                    + 'plus the share of time it spent beyond one sigma.',
                    'A composite that never moved gets no z-score at all \u2014 the panel says why instead '
                    + 'of printing 0.00.',
                ] },
            ],
            actions: [
                { label: 'Open Synthetic', kind: 'view', value: 'synthetic' },
                { label: 'Open Chart', kind: 'view', value: 'chart' },
            ],
            related: ['view.chart', 'method.levels'],
        },
        {
            id: 'view.monitor', group: 'panels', mode: 'both',
            title: 'Companion monitor (phone)',
            tags: ['monitor', 'phone', 'mobile', 'companion', 'read only', 'remote', 'second screen',
                   'alerts on my phone'],
            aliases: ['mobile view', 'phone page'],
            summary: 'A small read-only page the program already serves: the alert log, the simulated '
                + 'account, the watchlist quotes and one order-flow read, arranged for a phone. It reads '
                + 'the same local server the desktop window does, and it writes nothing.',
            blocks: [
                { h: 'Opening it', list: [
                    'On this machine: **/desktop/monitor.html** (the Settings view links it), or the same '
                    + 'address on whatever port the program is running on.',
                    'From a phone: the program listens on 127.0.0.1 only, so a phone on the same network '
                    + 'cannot reach it until the host setting points at the machine\'s LAN address. Until '
                    + 'then the page is a second-screen view on this computer.',
                    'The page refreshes every 5 s while it is in front; hiding the tab stops the reads.',
                ] },
                { h: 'What it shows, and what it refuses', list: [
                    'Alerts come from the same log the Alerts view exports, newest first.',
                    'Positions are the **simulated** account the Replay view runs \u2014 no broker anywhere.',
                    'Watchlist quotes are the engine\'s own rows: a symbol it is not streaming says "no live '
                    + 'readings" rather than showing a price nobody printed.',
                    'With no engine running the read panel prints the server\'s own sentence instead of a '
                    + 'state of zeros.',
                ] },
            ],
        },
        {
            id: 'view.orderflow.settings', group: 'panels', mode: 'both',
            title: 'Footprint settings (the drawer)',
            tags: ['footprint', 'settings', 'imbalance', 'diagonal', 'stacked imbalance', 'absorption',
                   'poc', 'value area', 'ticks per row', 'session filter', 'cell metric'],
            aliases: ['footprint settings', 'imbalance ratio'],
            summary: 'Every reading the footprint draws is set in one drawer under the grid: what a cell '
                + 'is read for, the imbalance ratios, stacked and diagonal imbalance, absorption, the '
                + 'per-bar POC and value area, rows per price, and the session window.',
            blocks: [
                { h: 'Where it is', p: 'Under the grid as **Footprint settings**. It starts collapsed and '
                    + 're-reads itself when opened, so a second window changing the same block is picked up '
                    + 'rather than shown stale.' },
                { h: 'The controls', table: [
                    ['cell metric', 'What a cell is read for: bid and ask as shipped, one side, the row\'s '
                        + 'delta, its volume, or its print count. **count** refuses with a sentence when the '
                        + 'feed carries no print counts \u2014 nothing is invented.'],
                    ['imbalance convention', '**Same price** compares a row\'s own two sides; **diagonal** '
                        + 'compares a row\'s ask with the bid one row below; **both** draws each and bands '
                        + 'them separately.'],
                    ['stacked imbalance', 'How many imbalanced rows in a row in one direction make a stack, '
                        + 'counted separately for the diagonal reading.'],
                    ['absorption', 'A row this many times the bar\'s average row that did not move the '
                        + 'price: size with no result.'],
                    ['POC and value area', 'Marked per bar: the row it traded most at, and the rows holding '
                        + 'the chosen share of its volume.'],
                    ['rows per price', 'Clustering two or four ticks into one row for coarser reading.'],
                    ['session window', 'Which bars the marks are drawn on: all, only inside the window, or '
                        + 'only outside it.'],
                ] },
                { note: 'Each control saves the moment it changes and says what the config store kept. The '
                    + 'drawer never writes the file itself.' },
            ],
            actions: [{ label: 'Open Order Flow', kind: 'view', value: 'orderflow' }],
            related: ['view.orderflow', 'view.ofx', 'view.profile'],
        },

    ];

    /* The coverage contract: every view the shell has, and the topic that explains it.
       test_help.py reads this app's own markup ([data-view] in index.html, the rail's nav items) and
       fails when a view has no entry here — so a new panel cannot ship undocumented. */
    const VIEWS = {
        // §147 (upgrade package): the new panels, mapped like every view above.
        'depth-history': 'view.depth-history',
        sessions: 'view.sessions',
        'data-quality': 'view.data-quality',
        derivatives: 'view.derivatives',
        synthetic: 'view.synthetic',
        overview: 'view.overview',
        chart: 'view.chart',
        heatmap: 'view.heatmap',
        studies: 'view.studies',
        orderflow: 'view.orderflow',
        ofx: 'view.ofx',
        depth: 'view.depth',
        tape: 'view.tape',
        marketwatch: 'view.marketwatch',
        trackers: 'view.trackers',
        cvd: 'view.cvd',
        profile: 'view.profile',
        frames: 'view.frames',
        signals: 'view.signals',
        strategy: 'view.strategy',
        performance: 'view.performance',
        journal: 'view.journal',
        calendar: 'view.calendar',
        replay: 'view.replay',
        alerts: 'view.alerts',
        inbox: 'view.inbox',
        instruments: 'view.instruments',
        alpaca: 'view.alpaca',
        platforms: 'view.platforms',
        profiles: 'view.profiles',
        settings: 'view.settings',
        logs: 'view.logs',
        watchlist: 'view.watchlist',
        news: 'view.news',
        fundamentals: 'view.fundamentals',
        options: 'view.options',
        gex: 'view.gex',
        volatility: 'view.volatility',
        'option-flow': 'view.optionflow',
        'market-read': 'view.marketread',
        guide: 'start.help',
        help: 'start.help',
    };

    if (typeof window !== 'undefined') {
        window.OFAPHELPDATA = { version: 1, groups: GROUPS, topics: TOPICS, views: VIEWS };
    } else if (typeof module !== 'undefined' && module.exports) {
        module.exports = { version: 1, groups: GROUPS, topics: TOPICS, views: VIEWS };
    }
})();
