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
                + 'axis, and a crosshair HUD that reads out the level under your cursor.',
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
                    '**VA %** sets the share of a bar that counts as its value area.',
                    '**bars** chooses the expression (default · delta tint · split candle · heat body · '
                    + 'wick + footprint), **palette** the colour vocabulary (theme or a measured '
                    + 'colour-blind-safe pair) and **ramp** the depth-heat ramp — both ramps are '
                    + 'monotone in luminance, so magnitude never rides on hue alone.',
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
                + 'and report their values in its data box.',
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
                + 'are greyed out rather than silently streaming nothing.',
            blocks: [
                { h: 'The controls', table: [
                    ['Validate against Bybit', 'Asks the venue which of these symbols it actually lists, '
                        + 'so a typo is caught here instead of showing up as a dead panel later.'],
                    ['Enable all supported', 'Ticks everything the current source can serve — the fast '
                        + 'way to a broad watchlist.'],
                    ['Clear', 'Un-ticks everything. The engine then streams nothing, which the system '
                        + 'check will tell you about.'],
                ] },
                { h: 'Tick size matters', p: 'Every analytics module works in price ticks. Instruments '
                    + 'imported from a venue carry the venue\'s real tick size; a guessed one would '
                    + 'make "three ticks away" mean the wrong distance in every detector.' },
                { note: 'A change here takes effect on the engine\'s next start — the panel tells you '
                    + 'when a restart is needed, and the top bar\'s ⟳ does it.' },
            ],
            actions: [
                { label: 'Open Instruments', kind: 'view', value: 'instruments' },
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
                        + 'posts a real message so you know it works before you rely on it.'],
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
            tags: ['window', 'second monitor', 'aux', 'pin', 'always on top', 'multi monitor'],
            aliases: ['send to monitor', 'floating panel', 'auxiliary window'],
            summary: 'Any panel can be opened as its own real window and placed on any monitor — the '
                + 'way you keep a depth map on a second screen while the footprint stays on the first.',
            blocks: [
                { h: 'Opening one', list: [
                    '**Windows ▸ Open** (menu bar) opens the panel you are looking at as a separate '
                    + 'window; **Windows ▸ Send to monitor ▸** places it on a specific display.',
                    'The window chip beside the top bar lists what is open, focuses a window, pins it '
                    + 'above others, or closes it.',
                    'Each window is one panel: it cannot itself open further windows, and it never '
                    + 'writes to your layout — closing it by its own ×, the OS\'s ×, or the app\'s '
                    + 'control all mean the same thing.',
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
            tags: ['layouts', 'workspaces', 'save layout', 'arrangement', 'profiles'],
            aliases: ['save my setup', 'screens setup'],
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
            tags: ['menu', 'menu bar', 'file menu', 'tools', 'view menu', 'commands'],
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
                    ['Tools', 'The command palette, the hotkey sheet, render telemetry, the '
                        + 'diagnostics copy, and the client-error log.'],
                    ['Help', 'The Help Centre, the mode switch, the setup assistant, the hotkey map '
                        + 'and the About card — see *About, credits and links*.'],
                ] },
                { h: 'Driving it from the keyboard', p: '**Alt** focuses the bar, ← → walk the menus, '
                    + 'Enter opens one, ↑ ↓ walk its items, and typing a letter jumps to the next item '
                    + 'starting with it. Every item shows its accelerator on the right; an item that is '
                    + 'not built yet is greyed out with the reason in its tooltip rather than silently '
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
            tags: ['shortcuts', 'hotkeys', 'keyboard', 'keys', 'accelerators'],
            aliases: ['hotkey map', 'key map'],
            summary: 'The list below is generated from the program\'s own shortcut map, so every key '
                + 'it honours is here and no key is listed that does nothing. **?** opens it as an '
                + 'overlay at any time.',
            blocks: [
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
            tags: ['pause', 'freeze', 'hold updates', 'quiet'],
            aliases: ['stop refreshing', 'freeze the screen'],
            summary: '**P** (or the ▶ live button in the status bar) holds every background refresh '
                + 'while you work on the board, so the numbers stop moving under your hands.',
            blocks: [
                { p: 'Ingest never stops: the engine keeps streaming and recording, the panels simply '
                    + 'stop repainting. Coming out of pause repaints everything at once, so nothing '
                    + 'you missed is lost — it was only the drawing that was held.' },
                { note: 'Being in a text field, a drag or a menu holds the affected panel '
                    + 'automatically; pause is for the deliberate, program-wide case.' },
            ],
            actions: [
                { label: 'Open the Help Centre search', kind: 'search', value: 'pause' },
            ],
            related: ['work.keys', 'fix.slow'],
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
                    ['volume', 'Its own level, independent of the system volume.'],
                ] },
                { note: 'Audio is generated locally — no sound files to ship, nothing downloaded.' },
            ],
            actions: [
                { label: 'Open Settings', kind: 'view', value: 'settings' },
                { label: 'Help: alerts', kind: 'topic', value: 'view.alerts' },
            ],
            related: ['view.alerts', 'view.settings'],
        },
        {
            id: 'work.exports', group: 'workflow', mode: 'both',
            title: 'Exports and screenshots',
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
    ];

    /* The coverage contract: every view the shell has, and the topic that explains it.
       test_help.py reads this app's own markup ([data-view] in index.html, the rail's nav items) and
       fails when a view has no entry here — so a new panel cannot ship undocumented. */
    const VIEWS = {
        overview: 'view.overview',
        chart: 'view.chart',
        heatmap: 'view.heatmap',
        studies: 'view.studies',
        orderflow: 'view.orderflow',
        ofx: 'view.ofx',
        depth: 'view.depth',
        tape: 'view.tape',
        trackers: 'view.trackers',
        cvd: 'view.cvd',
        profile: 'view.profile',
        frames: 'view.frames',
        signals: 'view.signals',
        strategy: 'view.strategy',
        performance: 'view.performance',
        replay: 'view.replay',
        alerts: 'view.alerts',
        instruments: 'view.instruments',
        alpaca: 'view.alpaca',
        platforms: 'view.platforms',
        settings: 'view.settings',
        logs: 'view.logs',
        watchlist: 'view.watchlist',
        news: 'view.news',
        fundamentals: 'view.fundamentals',
        options: 'view.options',
        guide: 'start.help',
        help: 'start.help',
    };

    if (typeof window !== 'undefined') {
        window.OFAPHELPDATA = { version: 1, groups: GROUPS, topics: TOPICS, views: VIEWS };
    } else if (typeof module !== 'undefined' && module.exports) {
        module.exports = { version: 1, groups: GROUPS, topics: TOPICS, views: VIEWS };
    }
})();
