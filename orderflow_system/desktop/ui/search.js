/* ══════════════════════════════════════════════════════════════════
   Program search — the command palette (plan Phase 4).

   Two layers in one panel:

   · the original app index — views, panels, settings, actions, alert rules,
     walkthroughs — so "where is the heatmap control" keeps working;
   · the market layer — live symbol rows with honest feed chips (IEX, Delayed SIP,
     Indicative, Crypto · Bybit), market status, price/%-change and a sparkline,
     fed by /api/control/search/symbols and patched over the shared socket.

   Aliases: `/api/control/search/rows` (poll fallback), `/api/control/search/meta`
   (batcher counters, surfaced in the Logs view), `/api/control/search/active` (the
   visible rows are the subscription set), `/api/control/alpaca/chain`
   (option chain), `/api/control/alpaca/compare` (feed comparison).

   Operators live in search-ops.js (with its own Node self-test); this file only
   applies what that parser returns.
   ══════════════════════════════════════════════════════════════════ */

const ALERT_KIND_HELP = [
    ['big_trade', 'A print above the adaptive big-print threshold: size that stands out from the tape.'],
    ['block_trade', 'A big print several times the normal size — the venue may flag it as a block.'],
    ['sweep', 'Aggressive orders that took several price levels in one push: someone wanted through.'],
    ['stop_run', 'A burst of size through a level with the tape accelerating — stops being triggered. Inferred from behaviour, not order ids.'],
    ['iceberg', 'Repeated fills at one price without the level emptying: hidden size being worked. Inferred.'],
    ['speed_spike', 'The tape is printing far faster than its recent normal.'],
    ['cvd_divergence', 'Price and cumulative delta moving apart — the tape and the move disagree.'],
    ['heat_pull', 'A large resting order disappeared without being traded.'],
    ['heat_stack', 'Size built up at a level that was previously thin.'],
    ['wall', 'A resting order far larger than its neighbours — a level worth watching.'],
    ['stacked_imbalance', 'Several adjacent levels all leaning the same way.'],
    ['intent_pressure', 'Book pressure on one side reached its threshold: size committed at the touch.'],
    ['pulled_size', 'A big level near price vanished untraded — an inference about intent.'],
    ['trapped_traders', 'A break beyond the recent range that was reclaimed: whoever chased it is wrong-footed.'],
    ['vwap_cross', 'Price closed through the session VWAP line.'],
    ['depth_execution', 'A print took a large share of the size resting at its price — someone ate a wall.'],
    ['depth_refill', 'A level was eaten and came back within seconds: refreshed liquidity (inferred).'],
];

const SEARCH = {
    index: null, rows: [], active: 0, open: false, built_ms: 0,
    parsed: null, symbols: [], symbolRows: [], selected: new Set(),
    debounce: 0, fetchedFor: null, watchlist: [], meta: null,
    chain: null, compare: null, lastPatchMs: 0, activePushTimer: 0, pollTimer: 0,
};

/* T41: the timing constants live in one place so they can be asserted and tuned. */
const SEARCH_TIMING = {
    QUERY_DEBOUNCE_MS: 150,      // typing → one request
    ROW_PATCH_MS: 200,           // socket patches at most this often
    ACTIVE_PUSH_MS: 600,         // visible-set updates
    META_MS: 5000,               // batch counters in the Logs view
    INDEX_TTL_MS: 15000,         // the app index rebuild window
};

const SEARCH_VIEWS_DEFAULT = 'orderflow';

/* T12/B18: the typed overlay selector — '@TAG' tokens open any of these surfaces with the
   instrument pre-loaded, through the same activate path the symbol rows use. */
const LAUNCH_TARGETS = [
    { view: 'ofx', label: 'Engine' },
    { view: 'heatmap', label: 'Heatmap' },
    { view: 'chart', label: 'Chart' },
    { view: 'replay', label: 'Replay' },
    { view: 'depth', label: 'Depth' },
];
/* '@TAG': letters/digits . - _ / up to 18 chars (BTCUSDT, NQ1!, ESZ5, BTC/USD…) */
const LAUNCH_TAG_RE = /@([A-Za-z0-9][A-Za-z0-9._/-]{0,17})/g;

/* ── what the program can do, in words ─────────────────────────── */
function searchActions() {
    const st = vwapState();
    return [
        { cat: 'Actions', title: 'Start the engine', desc: 'Begin streaming the enabled instruments from the selected data source.',
          keywords: 'run launch feed live begin', run: () => api('/api/control/engine/start', { method: 'POST', body: {} }) },
        {
          id: 'lookup', title: 'Instrument look-up \u2014 why won\u2019t my symbol stream?',
          keywords: 'nq nq1 crypto only mt5 broker symbol data missing not streaming enable instrument',
          run: () => { if (window.OFAPHINT) OFAPHINT.run('lookup'); },
        },
        { cat: 'Actions', title: 'Stop the engine', desc: 'Stop streaming; everything already collected stays on screen and on disk.',
          keywords: 'halt pause end', run: () => api('/api/control/engine/stop', { method: 'POST', body: {} }) },
        { cat: 'Actions', title: 'Restart the engine', desc: 'Re-read the configuration and rebuild the pipelines (needed after changing instruments).',
          keywords: 'reload rebuild apply settings', run: () => api('/api/control/engine/restart', { method: 'POST', body: {} }) },
        { cat: 'Actions', title: 'Run the setup assistant', desc: 'The step-by-step first-run wizard: data source, instruments, Alpaca, feeds, alerts, extras.',
          keywords: 'wizard onboarding setup first run', run: () => openWizard(true) },
        { cat: 'Actions', title: 'Open Alpaca setup', desc: 'Link a US brokerage account — keys, paper vs live, symbol list and the capability report.',
          keywords: 'alpaca broker account keys paper trading link connect stocks equities options', run: () => {
                window.showView && window.showView('alpaca');
                setTimeout(() => { const el = document.getElementById('alpKey'); if (el && el.focus) el.focus(); }, 300);
            } },
        { cat: 'Actions', title: 'Alpaca: how to get API keys', desc: 'The walkthrough: create the account, generate keys, paper vs live, and the free-plan limits.',
          keywords: 'alpaca broker keys paper trading signup account how to create generate', run: () => {
                if (typeof openHelp === 'function') { window.showView && window.showView('guide'); setTimeout(() => openHelp('alpaca'), 260); }
            } },
        { cat: 'Actions', title: 'Open the Guide', desc: 'What the program is, how each view works, and every walkthrough in one place.',
          keywords: 'documentation help manual docs', run: () => window.showView && window.showView('guide') },
        { cat: 'Actions', title: 'Profiles: switch playbook',
          desc: 'Your saved setups as named playbooks — the switch previews exactly what changes first.',
          keywords: 'profiles playbook switch setup playbooks',
          run: () => { showView('profiles'); if (window.OFAPPROFILES) OFAPPROFILES.refresh(); } },
        { cat: 'Actions', title: 'Profiles: save the current setup as…',
          desc: 'Name what you are running now — feed, instruments, analysis, layout and theme — and choose what it carries.',
          keywords: 'profile playbook save setup snapshot',
          run: () => { if (window.OFAPPROFILES) OFAPPROFILES.saveAs(); } },
        { cat: 'Actions', title: 'Rebuild the volume profiles', desc: 'Recompute the profiles from the stored candle history instead of waiting for the hourly pass.',
          keywords: 'profile rebuild poc value area', run: () => api('/api/control/profiles/rebuild', { method: 'POST', body: {} }) },
        { cat: 'Actions', title: 'Anchor the VWAP here', desc: 'Start the anchored VWAP at this moment (the blue line on the Chart view).',
          keywords: 'vwap anchor mark now', run: () => api(`/api/atlas/vwap/${(st || {}).symbol || 'BTCUSDT'}/anchor`, { method: 'POST', body: {} }) },
        { cat: 'Actions', title: 'Clear the VWAP anchor', desc: 'Remove the anchored VWAP line.',
          keywords: 'vwap anchor clear remove', run: () => api(`/api/atlas/vwap/${(st || {}).symbol || 'BTCUSDT'}/anchor`, { method: 'POST', body: { clear: true } }) },
        { cat: 'Actions', title: 'Refresh every panel now', desc: 'Force a re-pull of the visible panels instead of waiting for the next poll.',
          keywords: 'reload refresh update', run: () => { const v = document.querySelector('.nav-item.active'); if (v && window.showView) window.showView(v.dataset.view); } },
        { cat: 'Actions', title: 'Pause all external alerts', desc: 'Set every alert rule back to in-app only: nothing is pushed to a phone, mailed or posted to a webhook until you re-tick a channel on a rule. The quickest way to stop a flood.',
          keywords: 'mute stop silence pause disable alerts email push flood', run: pauseExternalAlerts },
        { cat: 'Actions', title: 'Clear stored alert credentials', desc: 'Erase the saved SMTP / Telegram / webhook credentials and any linked broker keys from the local config file. The ntfy topic is kept (it is the channel’s address, not a credential), so phone push keeps working; the other channels stay configured but unauthenticated until you re-enter them.',
          keywords: 'privacy forget password token smtp telegram security wipe', run: () => clearStoredCredentials() },
        { cat: 'Actions', title: 'Export detections to CSV', desc: 'Download the alert and detection history as a spreadsheet-friendly file.',
          keywords: 'csv export download alerts history', run: () => { const b = document.querySelector('[data-export-csv], #exportCsv, #alertsExport'); if (b) b.click(); else window.showView && window.showView('alerts'); } },
        { cat: 'Actions', title: 'Open the option chain', desc: 'Strikes × expiries for an equity, with indicative quotes — needs a linked Alpaca account.',
          keywords: 'option chain calls puts strike expiry options contract', run: () => searchChainOpen() },
        { cat: 'Actions', title: 'Compare two feeds', desc: 'IEX vs SIP (or Alpaca crypto vs the exchange) side by side, with the discrepancy.',
          keywords: 'compare feed iex sip delayed discrepancy arbitrage', run: () => searchCompareOpen(S.symbol) },
        { cat: 'Actions', title: 'Toggle the table-component trial (Watchlist)',
          desc: 'Render the Watchlist through the shared table component — sortable headers, a column chooser, drag-reorder and grouping; the layout is remembered per table.',
          keywords: 'table component one table sort columns group reorder trial watchlist migrate',
          run: () => {
                const cfg = S.config || (S.config = {});
                cfg.ui = cfg.ui || {};
                const list = Array.isArray(cfg.ui.table_component) ? cfg.ui.table_component.slice() : [];
                const at = list.indexOf('watchlist');
                if (at >= 0) list.splice(at, 1); else list.push('watchlist');
                cfg.ui.table_component = list;
                void api('/api/control/config', { method: 'POST', body: { ui: { table_component: list } } });
                if (typeof toast === 'function') toast(document.body,
                    'the one-table component for the Watchlist is ' + (at >= 0 ? 'OFF' : 'ON') + ' — reopen the Watchlist', 'info');
            } },
        { cat: 'Actions', title: 'Open the instrument look-up across feeds',
          desc: 'One overlay over every connection: search Bybit, MetaTrader 5 and Alpaca together, and add what the venue confirms.',
          keywords: 'instrument lookup find symbol across feeds venue mt5 bybit alpaca search add enable',
          run: () => { if (window.OFAPLOOKUP && OFAPLOOKUP.open) OFAPLOOKUP.open(); else if (window.OFAPHINT) OFAPHINT.run('lookup'); } },
        { cat: 'Actions', title: 'Forget this instrument’s display settings',
          desc: 'Drop the remembered heat recipe for the instrument on screen — the next visit starts from the last-used values again.',
          keywords: 'instrument scope reset forget per symbol heat settings remembered',
          run: () => { if (window.OFAPSCOPES && OFAPSCOPES.forgetCurrent) OFAPSCOPES.forgetCurrent(); } },
    ];
}

async function pauseExternalAlerts() {
    try {
        const rules = (await api('/api/atlas/alert-rules')).rules || [];
        let changed = 0;
        for (const r of rules) {
            const cur = r.channels || ['ui'];
            if (cur.length === 1 && cur[0] === 'ui') continue;
            await api('/api/atlas/alert-rules', {
                method: 'POST',
                body: { id: r.id, name: r.name, kind: r.kind, params: r.params, enabled: r.enabled,
                        cooldown_s: r.cooldown_s, channels: ['ui'] },
            });
            changed += 1;
        }
        if (typeof toast === 'function') toast(document.body, changed
            ? `${changed} rule${changed === 1 ? '' : 's'} set back to in-app only`
            : 'every rule was already in-app only', 'ok');
    } catch (e) {
        if (typeof toast === 'function') toast(document.body, 'Could not pause alerts: ' + e, 'err');
    }
}

async function clearStoredCredentials() {
    try {
        const cfg = await api('/api/control/config');
        cfg.telegram = { ...(cfg.telegram || {}), bot_token: '', chat_id: '' };
        cfg.notify = cfg.notify || {};
        if (cfg.notify.email) { cfg.notify.email.password = ''; }
        cfg.atlas = cfg.atlas || {};
        cfg.atlas.webhook_url = '';
        cfg.alpaca = { ...(cfg.alpaca || {}), key_id: '', secret: '', enabled: false };
        const r = await api('/api/control/config', { method: 'POST', body: cfg });
        if (vwapState()) vwapState().config = r.config;
        if (typeof toast === 'function') toast(document.body, 'Stored alert credentials cleared from the local config file', 'ok');
    } catch (e) {
        if (typeof toast === 'function') toast(document.body, 'Clear failed: ' + e, 'err');
    }
}

/* ── the index ─────────────────────────────────────────────────── */
const SEARCH_PANELS = [
    ['Participants’ intent', 'overview', 'Book pressure, absorption, depth change, tape quality, pulled size and trapped sides — the order-book read.', 'intent book pressure absorption dom'],
    ['Depth executions', 'overview', 'Prints that ate a large share of the resting size at their price, and refills of those levels.', 'trade detector ate wall refill iceberg'],
    ['Market context', 'overview', 'Funding, open interest, long/short ratio, Fear & Greed and headlines.', 'funding oi sentiment news fear greed'],
    ['Session summary', 'overview', 'Where the instrument is, what the tape is doing and what fired since the session started.', 'summary kpi session'],
    ['Latest signals', 'overview', 'The most recent detections with their severity, newest first.', 'signals detections latest'],
    ['Heatmap + market pressure', 'heatmap', 'Liquidity by price over time, with walls, stack/pull events and the paired buy/sell pressure panel.', 'heatmap book map walls liquidity pressure'],
    ['Order flow footprint', 'orderflow', 'Bid/ask volume per price inside each bar, with imbalance highlighting and bar statistics.', 'footprint volumetric bid ask imbalance'],
    ['Depth ladder', 'depth', 'The live book around the touch, with the intent columns (adds, pulls, refills).', 'dom ladder level 2 book'],
    ['Time & sales', 'tape', 'Every print with size, side and speed; adaptive big prints are highlighted.', 'tape prints time sales speed'],
    ['Trackers', 'trackers', 'Icebergs, sweeps, stop runs, liquidations and big trades in one board (inferred where the venue has no order ids).', 'iceberg sweep stop run liquidation big trades'],
    ['Cumulative delta', 'cvd', 'Delta accumulated over the session, plus the CVD Pro size-band lines.', 'cvd delta cumulative pro size band'],
    ['Volume profile', 'profile', 'Volume, TPO and tick profiles with the point of control and the value area.', 'profile tpo poc value area tick profile'],
    ['Frames', 'frames', 'The same tape as range, renko, reversal, tick, volume or delta bars.', 'range renko reversal tick volume delta bars'],
    ['Replay', 'replay', 'Replay the recorded session with speed control and seek.', 'replay playback speed seek review'],
    ['Alerts', 'alerts', 'The rule engine: what fired, and every rule with its parameters and channels.', 'alerts rules notifications history'],
    ['Scanner', 'scanner', 'One ranked row per instrument across every order-flow column.', 'scanner market analyzer ranking screener'],
    ['Chart + VWAP', 'chart', 'Candles, delta histogram, value-area levels, VWAP with sigma bands and the anchored line.', 'chart candles vwap anchor bands'],
    ['Guide & setup', 'guide', 'The documentation, the walkthroughs and the setup assistant.', 'guide help setup wizard docs'],
    ['Logs', 'logs', 'The application log, newest last, with a level filter — plus the palette batch counters.', 'log diagnostics errors tail search counters'],
    ['Settings', 'settings', 'Engine, data source, instruments, feeds, alerts and display options.', 'settings config options preferences'],
    ['Alpaca setup', 'alpaca', 'Link a US brokerage account: stocks, ETFs, options and crypto instruments, news, calendar, portfolio — free paper trading.', 'alpaca broker account keys stocks equities paper trading link connect symbols feed routing'],
];

function searchBuildIndex(force) {
    const now = Date.now();
    if (!force && SEARCH.index && now - SEARCH.built_ms < SEARCH_TIMING.INDEX_TTL_MS) return SEARCH.index;
    const idx = [];
    const push = (cat, title, desc, keywords, run, tag) => idx.push({ cat, title, desc, keywords: keywords || '', run, tag: tag || '' });

    /* views */
    document.querySelectorAll('.rail .nav-item[data-view]').forEach((b) => {
        const name = (b.textContent || '').replace(/\s+/g, ' ').trim();
        if (!name) return;
        push('Views', name, b.title || `Open the ${name} view.`, name.toLowerCase(), () => window.showView && window.showView(b.dataset.view));
    });

    /* panels inside views */
    SEARCH_PANELS.forEach(([title, view, desc, kw]) => push('Panels', title, desc, `${kw} ${view}`, () => window.showView && window.showView(view)));

    /* actions */
    searchActions().forEach((a) => push('Actions', a.title, a.desc, a.keywords, a.run));

    /* settings: every labelled control in every view, found at search time */
    document.querySelectorAll('.view input[id], .view select[id], .view textarea[id], .view button[id]').forEach((el) => {
        const view = el.closest('.view');
        const viewName = (view && view.dataset.view) || '';
        const labelEl = el.closest('.field')?.querySelector('label') || (view || document).querySelector(`label[for="${el.id}"]`);
        const label = labelEl ? labelEl.textContent.replace(/\s+/g, ' ').trim() : (el.title || el.placeholder || el.id);
        if (!label) return;
        push('Settings', label, `${el.title || el.placeholder || 'Setting'} — in the ${viewName} view`,
            `${label} ${el.id} ${viewName} setting option`, () => {
                if (window.showView && viewName) window.showView(viewName);
                setTimeout(() => {
                    el.classList.add('search-hit');
                    if (el.focus) try { el.focus({ preventScroll: false }); } catch (e) { /* ignore */ }
                    setTimeout(() => el.classList.remove('search-hit'), 2600);
                }, 250);
            });
    });

    /* select options: "renko", "15m", "delta" should find the control that offers them */
    document.querySelectorAll('.view select[id]').forEach((sel) => {
        const view = sel.closest('.view');
        const viewName = (view && view.dataset.view) || '';
        Array.from(sel.options).forEach((opt) => {
            const name = (opt.textContent || '').trim();
            if (!name) return;
            push('Options', name, `${opt.title || 'Option'} — in the ${viewName} view`,
                `${name} ${opt.value} option select ${viewName}`, () => {
                    if (window.showView && viewName) window.showView(viewName);
                    setTimeout(() => {
                        sel.value = opt.value;
                        sel.dispatchEvent(new Event('change'));
                        sel.classList.add('search-hit');
                        setTimeout(() => sel.classList.remove('search-hit'), 2600);
                    }, 250);
                });
        });
    });

    /* alert kinds and rules */
    const kinds = (typeof ALERT_KIND_HELP !== 'undefined') ? ALERT_KIND_HELP : [];
    kinds.forEach(([kind, desc]) => push('Alerts', kind.replace(/_/g, ' '), desc, `${kind} alert rule notify`, () => window.showView && window.showView('alerts')));
    document.querySelectorAll('#ruleTable tbody tr').forEach((row) => {
        const cell = row.querySelector('[data-rule-name]');
        const name = cell ? (cell.getAttribute('data-rule-name') || cell.textContent) : '';
        if (name) push('Alerts', `Rule: ${name.replace(/\s+/g, ' ').trim()}`, 'An armed alert rule \u2014 open it to change its thresholds, level scope, channels or cooldown.', `${name} rule cooldown channel`, () => window.showView && window.showView('alerts'));
    });

    /* help walkthroughs + guide sections */
    if (typeof HELP_TOPICS !== 'undefined') {
        Object.entries(HELP_TOPICS).forEach(([id, t]) => push('Help', t.title, `${t.lead} Step-by-step walkthrough.`,
            `${id} how to setup tutorial ${(t.steps || []).map((s) => s.t).join(' ')}`, () => openHelp(id)));
    }
    if (typeof GUIDE_SECTIONS !== 'undefined') {
        GUIDE_SECTIONS.forEach((s) => push('Guide', s.h, (s.body || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 160),
            `${s.h} documentation guide`, () => {
                if (window.showView) window.showView('guide');
                const head = Array.from(document.querySelectorAll('#guideBody .card-title')).find((el) => el.textContent.trim() === s.h);
                if (head) {
                    head.closest('.card').scrollIntoView({ behavior: 'smooth', block: 'start' });
                    head.classList.add('search-hit');
                    setTimeout(() => head.classList.remove('search-hit'), 2600);
                }
            }));
    }

    /* instruments */
    const cfg = (vwapState() || {}).config || {};
    (cfg.instruments || []).forEach((i) => {
        push('Instruments', i.symbol, `${i.asset_class || 'instrument'}${i.enabled ? ' — streaming' : ' — available (not enabled)'}`,
            `${i.symbol} ${i.asset_class || ''} symbol switch`, () => searchActivateSymbol(i.symbol));
    });

    /* the watchlist follows the config, so it is part of the index */
    SEARCH.watchlist.forEach((symbol) => push('Watchlist', symbol, 'On your watchlist — opens the configured view and joins the live set.',
        `${symbol} watchlist pinned multi compare`, () => searchActivateSymbol(symbol)));

    SEARCH.index = idx;
    SEARCH.built_ms = now;
    return idx;
}

/* ── matching ──────────────────────────────────────────────────── */
function searchScore(item, tokens) {
    const hay = `${item.title} ${item.cat} ${item.keywords} ${item.desc}`.toLowerCase();
    const title = item.title.toLowerCase();
    let score = 0;
    for (const tok of tokens) {
        if (!tok) continue;
        if (title === tok) score += 60;
        else if (title.startsWith(tok)) score += 40;
        else if (title.includes(tok)) score += 25;
        else if (hay.includes(tok)) score += 10;
        else return 0;
    }
    return score;
}

function searchQuery(q) {
    const text = (q || '').trim().toLowerCase();
    if (!text) return [];
    const tokens = text.split(/\s+/).filter(Boolean);
    const scored = [];
    const idx = searchBuildIndex(false);
    for (const item of idx) {
        const s = searchScore(item, tokens);
        if (s > 0) scored.push({ item, s });
    }
    scored.sort((a, b) => b.s - a.s || a.item.title.localeCompare(b.item.title));
    return scored.slice(0, 40).map(({ item }) => item);
}

/* ── the market layer ──────────────────────────────────────────── */

function searchFmt(v, digits = 2) {
    if (v === null || v === undefined || v === '') return '–';
    const n = Number(v);
    if (!isFinite(n)) return '–';
    if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(2) + 'K';
    return n.toFixed(digits);
}

/** Prices keep their cents: a compacted "78.38K" hides every tick that matters. */
function searchPrice(v) {
    if (v === null || v === undefined || v === '') return '–';
    const n = Number(v);
    if (!isFinite(n)) return '–';
    const abs = Math.abs(n);
    if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (abs >= 1000) return n.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
    if (abs >= 1) return n.toFixed(2);
    if (abs >= 0.01) return n.toFixed(4);
    return n.toPrecision(3);
}

function searchSpark(prices) {
    if (!prices || prices.length < 2) return '';
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const span = (max - min) || 1;
    const pts = prices.map((p, i) => {
        const x = (i / (prices.length - 1)) * 60;
        const y = 16 - ((p - min) / span) * 14;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const up = prices[prices.length - 1] >= prices[0];
    return `<svg class="s-spark" width="62" height="18" viewBox="0 0 62 18" aria-hidden="true">
        <polyline points="${pts}" fill="none" stroke="${up ? 'var(--up, #58c882)' : 'var(--down, #ff5d6c)'}" stroke-width="1.3"/></svg>`;
}

/** Percent with enough resolution to show a quiet tape moving (0.013%, not 0.00%). */
function searchPct(v) {
    const n = Number(v);
    if (!isFinite(n)) return '';
    const abs = Math.abs(n);
    const digits = abs < 0.1 ? 3 : 2;
    return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

function searchStatusDot(row) {
    const cls = row.status || 'unknown';
    const title = row.status_help || '';
    const label = { open: 'open', closed: 'closed', pre: 'pre/after', unknown: 'session ?' }[cls] || cls;
    return `<span class="s-status ${cls}" title="${escapeHtml(title)}">${label}</span>`;
}

function searchSymbolRowHTML(row, i) {
    const cls = (row.asset_class || '').replace(/[^a-z]/gi, '').toLowerCase() || '—';
    const badge = { usequity: 'stock', etf: 'ETF', crypto: 'crypto', option: 'option', indices: 'index', forex: 'fx', metals: 'metal', energy: 'energy', stocks: 'stock' }[cls] || row.asset_class || '—';
    const chg = (row.chg_pct === null || row.chg_pct === undefined) ? ''
        : `<b class="${row.chg_pct >= 0 ? 'up' : 'down'}">${searchPct(row.chg_pct)}</b>`;
    const sel = SEARCH.selected.has(row.symbol) ? ' selected' : '';
    const live = row.subscribed ? '<span class="s-live" title="Subscribed on the stream right now">live</span>' : '';
    return `<div class="search-row sym${sel}" data-i="${i}" data-sym="${escapeHtml(row.symbol)}"
                 title="${escapeHtml(row.name || row.symbol)} — ${escapeHtml(row.feed_help || '')}">
        <span class="s-sym">${escapeHtml(row.symbol)}</span>
        <span class="s-name">${escapeHtml(row.name || '')}</span>
        <span class="s-tags"><span class="tag">${escapeHtml(String(badge))}</span>
            <span class="chip feed" title="${escapeHtml(row.feed_help || '')}">${escapeHtml(row.feed_label || row.feed || '')}</span>
            ${searchStatusDot(row)} ${live}</span>
        <span class="s-spark">${searchSpark(row.spark)}</span>
        <span class="s-num">${searchPrice(row.last)} ${chg}</span>
    </div>`;
}

async function searchSymbolsFetch(parsed, q) {
    const params = new URLSearchParams();
    params.set('q', q || '');
    params.set('limit', parsed && parsed.ops && parsed.ops.type === 'option' ? '12' : '20');
    if (parsed && parsed.ops) {
        if (parsed.ops.type && parsed.ops.type !== 'option') params.set('types', parsed.ops.type);
        if (parsed.ops.sort) params.set('sort', parsed.ops.sort);
    }
    try {
        const payload = await api('/api/control/search/symbols?' + params.toString());
        let rows = payload.rows || [];
        if (parsed && parsed.ops) rows = searchOpsFilterRows(rows, parsed.ops);
        SEARCH.symbolRows = rows;
        SEARCH.symbolMeta = { linked: payload.linked, assets: payload.assets, total: payload.total };
        return rows;
    } catch (e) {
        SEARCH.symbolMeta = { error: String(e) };
        return [];
    }
}

/* ── rendering ─────────────────────────────────────────────────── */

function searchStyles() {
    if (document.getElementById('searchStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'searchStyleSheet';
    st.textContent = `
        .search-wrap { position: relative; display: flex; align-items: center; gap: 6px; padding: 4px 8px;
                       border: 1px solid var(--line); border-radius: 8px; background: var(--panel, #12161d); }
        .search-wrap input { flex: 1; border: 0; background: transparent; color: var(--fg); outline: none; font-size: 13px; }
        .search-wrap .kbd { color: var(--dim); font-size: 11px; }
        .search-panel { position: absolute; z-index: 60; margin-top: 4px; min-width: 420px; max-width: 720px;
                        max-height: 60vh; overflow: auto; border: 1px solid var(--line); border-radius: 8px;
                        background: var(--bg, #0d1117); box-shadow: 0 12px 30px rgba(0,0,0,0.45); display: none; }
        .search-panel.open { display: block; }
        .search-cat { padding: 6px 10px 2px; color: var(--dim); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; }
        .search-row { display: flex; gap: 8px; align-items: center; padding: 5px 10px; cursor: pointer; }
        .search-row:hover, .search-row.active { background: rgba(255,255,255,0.05); }
        .search-row .st { flex: 0 0 auto; font-weight: 600; }
        .search-row .sd { color: var(--dim); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .search-row .stag { color: var(--dim); font-size: 10px; text-transform: uppercase; }
        .search-row.sym { display: grid; grid-template-columns: 92px 1fr auto 66px 130px; align-items: center; }
        .search-row.sym .s-sym { font-weight: 700; font-size: 13px; }
        .search-row.sym .s-name { color: var(--dim); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .search-row.sym .s-tags { display: flex; gap: 6px; align-items: center; }
        .search-row.sym .s-num { text-align: right; font-size: 12px; }
        .search-row.sym .s-num b { margin-left: 4px; }
        .search-row.sym .up { color: var(--up, #58c882); } .search-row.sym .down { color: var(--down, #ff5d6c); }
        .search-row.sym.selected { outline: 1px solid rgba(79,140,255,.6); background: rgba(79,140,255,.10); }
        .search-row .chip { border: 1px solid var(--line); border-radius: 999px; padding: 0 6px; font-size: 10px; color: var(--dim); }
        .search-row .chip.feed { color: #8fb7ff; border-color: rgba(79,140,255,.4); }
        .search-row .s-live { color: var(--up, #58c882); font-size: 10px; border: 1px solid rgba(88,200,130,.5); border-radius: 999px; padding: 0 6px; }
        .search-row .s-status { font-size: 10px; color: var(--dim); }
        .search-row .s-status.open { color: var(--up, #58c882); }
        .search-row .s-status.closed { color: var(--dim); }
        .search-row .s-status.pre { color: #e8be54; }
        .search-spark { display: block; }
        .search-empty { padding: 10px; color: var(--dim); font-size: 12px; }
        .search-ops { padding: 4px 10px; color: var(--dim); font-size: 11px; border-top: 1px solid var(--line); }
        .search-ops .bad { color: var(--down, #ff5d6c); }
        .search-ops .kbd { color: var(--fg); }
        .search-foot { display: flex; gap: 8px; align-items: center; padding: 6px 10px; border-top: 1px solid var(--line); }
        .search-hit { animation: searchHit 2.4s ease-out; }
        @keyframes searchHit { from { background: rgba(79,140,255,.35); } to { background: transparent; } }
        .chain-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 90; display: flex;
                         align-items: center; justify-content: center; }
        .chain-card { background: var(--bg, #0d1117); border: 1px solid var(--line); border-radius: 10px;
                      width: min(1080px, 94vw); max-height: 86vh; overflow: auto; padding: 14px; }
        .chain-grid { width: 100%; border-collapse: collapse; font-size: 12px; }
        .chain-grid th { text-align: right; color: var(--dim); padding: 4px 8px; border-bottom: 1px solid var(--line); }
        .chain-grid td { padding: 3px 8px; text-align: right; border-bottom: 1px solid rgba(255,255,255,.04); cursor: pointer; }
        .chain-grid tr:hover td { background: rgba(255,255,255,.04); }
        .chain-grid td.c { color: var(--up, #58c882); } .chain-grid td.p { color: var(--down, #ff5d6c); }
        .chain-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
        .cmp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
        .cmp-kv { border: 1px solid var(--line); border-radius: 6px; padding: 8px; }
        .cmp-kv .k { color: var(--dim); font-size: 11px; } .cmp-kv .v { font-size: 16px; }
    `;
    document.head.appendChild(st);
}

function searchEnsureUI() {
    if (document.getElementById('programSearch')) return;
    searchStyles();
    const host = document.querySelector('header .search-wrap') || document.querySelector('header');
    if (!host) return;
    const wrap = document.createElement('div');
    wrap.className = 'search-wrap';
    wrap.style.minWidth = '240px';
    wrap.innerHTML = `<span title="Search everything and every symbol">🔍</span>
        <input id="programSearch" placeholder="Search or type a ticker…  (Ctrl+K)" autocomplete="off" spellcheck="false"
               title="Views, panels, settings and actions — and live symbols. Enter opens the first match; Ctrl+Enter opens it in a new panel; Ctrl+Shift+Enter chains it; Shift+? lists the operators.">
        <span class="kbd">Ctrl+K</span>
        <button class="btn small" id="searchClear" title="Clear the search and its filters">✕</button>`;
    host.insertBefore(wrap, host.firstChild);
    const panel = document.createElement('div');
    panel.className = 'search-panel';
    panel.id = 'searchPanel';
    document.body.appendChild(panel);

    const input = wrap.querySelector('#programSearch');
    input.addEventListener('input', () => {
        // T41: one request per 150 ms of typing, not one per keystroke
        clearTimeout(SEARCH.debounce);
        const value = input.value;
        SEARCH.debounce = setTimeout(() => searchSymbolsThenRender(value), SEARCH_TIMING.QUERY_DEBOUNCE_MS);
        searchRender(value, { symbolsPending: true });
    });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') { e.preventDefault(); searchMove(1); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); searchMove(-1); }
        else if (e.key === 'Enter') {
            e.preventDefault();
            searchRun({ newPanel: e.ctrlKey || e.metaKey, chain: e.ctrlKey && e.shiftKey });
        } else if (e.key === 'Escape') { e.preventDefault(); searchClose(); }
        else if (e.key === '?' && e.shiftKey) { e.preventDefault(); searchOpsToggle(); }
    });
    wrap.querySelector('#searchClear').onclick = () => { input.value = ''; searchSymbolsThenRender(''); searchRender(''); input.focus(); };
    /* Ctrl+K and `/` are the map's 'palette' binding (keys.js). The module that owns the input
       registers the action, the map dispatches it — one owner for `/` at last: it used to open
       the ☰ menu AND focus this input on the same press (menu.js's copy is gone). */
    function focusPalette() { input.focus(); input.select(); }
    if (window.OFAPKEYS) {
        OFAPKEYS.bind({ id: 'palette', keys: ['ctrl+k', '/'], scope: 'Global',
            label: 'command palette — search panels, settings and symbols', run: focusPalette });
        OFAPKEYS.document([
            { keys: '↑ ↓ / Enter / Esc / Shift+?', label: 'walk the results, run the highlighted one, close, operators', scope: 'Palette' },
        ]);
    }
    document.addEventListener('click', (e) => {
        if (!panel.contains(e.target) && !wrap.contains(e.target)) searchClose();
    });
}

/* ── opening a symbol: the workspace navigation rules (T35) ────── */

function searchDefaultView() {
    return ((S.config || {}).search || {}).default_view || SEARCH_VIEWS_DEFAULT;
}

function searchActivateSymbol(symbol, opts) {
    const o = opts || {};
    if (!symbol) return;
    const app = searchAppSymbol(symbol);
    const sel = document.getElementById('symbolSelect');
    if (sel) {
        const known = Array.from(sel.options).some((opt) => opt.value === app);
        if (known) {
            sel.value = app;
            sel.dispatchEvent(new Event('change'));
        } else {
            /* Not a configured instrument yet — ask the server what it IS and, when a linked
               venue confirms it (an Alpaca asset, a broker symbol), add it right here. The old
               toast sent the user to the Instruments view, which has no row to add and no
               form: the reported "keeps trying to add" loop. */
            void searchAddUnknown(app);
        }
    }
    /* T12/B18: deep-launching the Engine also pre-loads its own symbol control (the Engine's
       select is the authority for what it streams), through its own change path. */
    if (o.view === 'ofx') {
        const engineSel = document.getElementById('ofxSymbol');
        if (engineSel) {
            const known = !engineSel.options.length
                || Array.from(engineSel.options).some((opt) => opt.value === app);
            if (known) { engineSel.value = app; engineSel.dispatchEvent(new Event('change')); }
        }
    }
    window.showView && window.showView(o.view || searchDefaultView());
    searchPushActive();
    return app;
}

/* A symbol the app does not know yet: let the look-up decide, and when a venue confirms the
   name (an Alpaca asset, a broker symbol), make the add HERE — the message it replaces
   ("add it under Instruments") pointed at a view with no way to add anything. */
async function searchAddUnknown(symbol) {
    const host = document.getElementById('ovBanner') || document.body;
    const say = (msg, kind) => { if (typeof toast === 'function') toast(host, msg, kind || 'warn'); };
    let p = null;
    try { p = await api('/api/control/instruments/resolve?symbol=' + encodeURIComponent(symbol)); }
    catch (err) { p = null; }
    const actions = (p && p.actions) || [];
    if (p && actions.indexOf('add') >= 0) {
        const addSymbol = p.symbol || symbol;
        const source = p.add_source || p.source || '';
        say(`adding ${addSymbol}${source ? ' on ' + source : ''}…`, 'info');
        try {
            const res = await api('/api/control/instruments/add',
                { method: 'POST', body: { symbols: [addSymbol], source: source, enable: true } });
            const skip = (res && (res.skipped || [])[0]) || {};
            const ok = res && res.ok !== false
                && ((res.added || []).length + (res.updated || []).length) > 0;
            if (!ok) {
                say(`${addSymbol} could not be added: ${(res && res.error) || skip.reason || 'the venue did not confirm it'}`, 'err');
                return;
            }
            say(`${addSymbol} added — press Start engine (or restart it) to stream it`, 'ok');
            if (typeof refreshInstruments === 'function') void refreshInstruments();
            const sel = document.getElementById('symbolSelect');
            if (sel) {
                setTimeout(() => {
                    const known = Array.from(sel.options).some((opt) => opt.value === addSymbol);
                    if (known) { sel.value = addSymbol; sel.dispatchEvent(new Event('change')); }
                }, 400);
            }
        } catch (err) {
            say(`${addSymbol} could not be added: ${(err && err.message) ? err.message : err}`, 'err');
        }
        return;
    }
    say((p && p.reason) || `${symbol} is not an instrument this app can stream yet`, 'warn');
}

/** Alpaca spells crypto as BTC/USD; the program streams it as BTCUSDT. */
function searchAppSymbol(symbol) {
    const sym = String(symbol || '');
    if (sym.includes('/')) {
        const [base, quote] = sym.split('/');
        if (quote === 'USD') return `${base}USDT`;
    }
    const map = (S.caps && S.caps.alpaca && S.caps.alpaca.symbols) || {};
    for (const [app, alp] of Object.entries(map)) {
        if (String(alp).toUpperCase() === sym.toUpperCase()) return app;
    }
    return sym;
}

function searchPushActive() {
    clearTimeout(SEARCH.activePushTimer);
    SEARCH.activePushTimer = setTimeout(async () => {
        const visible = SEARCH.rows.filter((r) => r.symbol).map((r) => r.symbol).slice(0, 60);
        try {
            await api('/api/control/search/active', { method: 'POST', body: { symbols: visible, view: S.symbol || '', focus: S.symbol || '' } });
        } catch (e) { /* the palette keeps working without the live set */ }
        if (S.config) {
            const focus = S.symbol;
            if (focus) {
                const recents = [focus, ...((S.config.search || {}).recents || []).filter((r) => r !== focus)].slice(0, 12);
                S.config.search = { ...(S.config.search || {}), recents };
            }
        }
    }, SEARCH_TIMING.ACTIVE_PUSH_MS);
}

/* ── live patching over the shared socket (T34/T41) ────────────── */

function searchApplyRows(rows) {
    if (!rows || !rows.length) return;
    const now = Date.now();
    if (now - SEARCH.lastPatchMs < SEARCH_TIMING.ROW_PATCH_MS) return;
    SEARCH.lastPatchMs = now;
    const bySymbol = {};
    rows.forEach((r) => { bySymbol[r.symbol] = r; });
    let touched = 0;
    SEARCH.rows.forEach((row, i) => {
        const patch = bySymbol[row.symbol];
        if (!patch) return;
        Object.assign(row, { last: patch.last, chg_pct: patch.chg_pct, chg_help: patch.chg_help || row.chg_help,
                             volume: patch.volume, spark: patch.spark || row.spark, subscribed: patch.subscribed });
        const el = document.querySelector(`.search-row[data-i="${i}"]`);
        if (!el) return;
        const num = el.querySelector('.s-num');
        if (num) {
            const chg = (row.chg_pct === null || row.chg_pct === undefined) ? ''
                : `<b class="${row.chg_pct >= 0 ? 'up' : 'down'}">${searchPct(row.chg_pct)}</b>`;
            num.innerHTML = `${searchPrice(row.last)} ${chg}`;
            if (row.chg_help) num.title = row.chg_help;
        }
        const spark = el.querySelector('.s-spark');
        if (spark) spark.innerHTML = searchSpark(row.spark);
        touched += 1;
    });
    if (touched) SEARCH.lastPatchMs = now;
}

/* ── the option chain (T38) ────────────────────────────────────── */

async function searchChainOpen(underlying, expiry) {
    const sym = searchAppSymbol(underlying || (SEARCH.rows[SEARCH.active] || {}).symbol || S.symbol || 'AAPL');
    let d = null;
    try {
        const q = new URLSearchParams({ underlying: sym });
        if (expiry) q.set('expiry', expiry);
        d = await api('/api/control/alpaca/chain?' + q.toString());
    } catch (e) { d = { ok: false, reason: String(e) }; }
    SEARCH.chain = d;
    searchChainRender();
}

function searchChainRender() {
    let host = document.getElementById('searchChain');
    const d = SEARCH.chain || {};
    if (!host) {
        host = document.createElement('div');
        host.id = 'searchChain';
        host.className = 'chain-overlay';
        document.body.appendChild(host);
        host.addEventListener('click', (e) => { if (e.target === host) { host.remove(); } });
    }
    if (!d.ok) {
        host.innerHTML = `<div class="chain-card">
            <div class="chain-head"><b>Option chain</b><div style="flex:1"></div>
                <button class="btn small" id="chainClose">Close</button></div>
            <div class="banner warn">${escapeHtml(d.reason || 'The chain is unavailable.')}
                ${d.help ? `<div class="dim" style="margin-top:6px">${escapeHtml(d.help)}</div>` : ''}</div></div>`;
        const close = document.getElementById('chainClose');
        if (close) close.onclick = () => host.remove();
        return;
    }
    const rows = d.rows || [];
    const sum = d.summary || {};
    const exps = d.expiries || [];
    const expSel = `<select id="chainExp" title="Expiry">${exps.map((e) => `<option${e === d.expiry ? ' selected' : ''}>${e}</option>`).join('')}</select>`;
    const body = rows.map((r) => `<tr>
        <td class="c">${r.type === 'call' ? searchFmt(r.bid, 2) : ''}</td>
        <td class="c">${r.type === 'call' ? searchFmt(r.ask, 2) : ''}</td>
        <td><b>${searchFmt(r.strike, 2)}</b></td>
        <td class="p">${r.type === 'put' ? searchFmt(r.bid, 2) : ''}</td>
        <td class="p">${r.type === 'put' ? searchFmt(r.ask, 2) : ''}</td>
        <td data-contract="${escapeHtml(r.contract)}" title="Search this contract">${escapeHtml(r.contract)}</td>
        <td>${r.iv === null || r.iv === undefined ? '–' : (Number(r.iv) * 100).toFixed(1) + '%'}</td>
    </tr>`).join('');
    host.innerHTML = `<div class="chain-card">
        <div class="chain-head"><b>${escapeHtml(d.underlying)} option chain</b>
            <span class="chip feed" title="${escapeHtml(d.feed_label)}">${escapeHtml(d.feed_label)}</span>
            <span class="dim">${sum.contracts} contracts · ${sum.strikes} strikes · expiries ${(sum.expiries || []).join(', ')}</span>
            <div style="flex:1"></div>
            <label class="switch" title="${escapeHtml((d.live_subscription || {}).reason || '')}">
                <input type="checkbox" id="chainLive" disabled> live per-contract
            </label>
            ${expSel}
            <button class="btn small" id="chainAtm">ATM ±5</button>
            <button class="btn small" id="chainClose">Close</button></div>
        ${(d.live_subscription || {}).available === false
            ? `<div class="dim" style="margin-bottom:6px">${escapeHtml(d.live_subscription.reason)}</div>` : ''}
        <table class="chain-grid"><thead><tr>
            <th>call bid</th><th>call ask</th><th>strike</th><th>put bid</th><th>put ask</th><th>contract</th><th>IV</th>
        </tr></thead><tbody>${body || '<tr><td colspan="7" class="dim">no contracts in this window</td></tr>'}</tbody></table>
        <div class="hint">Quotes are snapshots taken when this panel opened — click “Refresh” to re-read them.</div>
        <div class="row" style="margin-top:8px"><button class="btn small" id="chainRefresh">Refresh quotes</button></div>
    </div>`;
    const close = document.getElementById('chainClose');
    if (close) close.onclick = () => host.remove();
    const refresh = document.getElementById('chainRefresh');
    if (refresh) refresh.onclick = () => searchChainOpen(d.underlying, (document.getElementById('chainExp') || {}).value);
    const exp = document.getElementById('chainExp');
    if (exp) exp.onchange = () => searchChainOpen(d.underlying, exp.value);
    const atm = document.getElementById('chainAtm');
    if (atm) atm.onclick = () => {
        const last = Number((S.status && S.status.per_symbol || []).find((p) => p.symbol === d.underlying)?.price || 0);
        if (!last) return;
        const strikes = rows.filter((r) => r.strike >= last * 0.98 && r.strike <= last * 1.02);
        if (typeof toast === 'function') toast(document.body,
            `${strikes.length} contracts within ±2% of ${searchFmt(last, 2)}`, 'info');
    };
    host.querySelectorAll('td[data-contract]').forEach((td) => {
        td.onclick = () => {
            const input = document.getElementById('programSearch');
            if (input) { input.value = td.dataset.contract; input.dispatchEvent(new Event('input')); }
            host.remove();
        };
    });
}

/* ── feed comparison (T39) ─────────────────────────────────────── */

async function searchCompareOpen(symbol) {
    const sym = symbol || S.symbol || 'AAPL';
    let d = null;
    try {
        d = await api('/api/control/alpaca/compare?symbol=' + encodeURIComponent(sym));
    } catch (e) { d = { ok: false, notes: [String(e)], pairs: [] }; }
    SEARCH.compare = d;
    searchCompareRender();
}

function searchCompareRender() {
    let host = document.getElementById('searchCompare');
    const d = SEARCH.compare || {};
    if (!host) {
        host = document.createElement('div');
        host.id = 'searchCompare';
        host.className = 'chain-overlay';
        document.body.appendChild(host);
        host.addEventListener('click', (e) => { if (e.target === host) host.remove(); });
    }
    const pairs = (d.pairs || []).map((p) => `<div class="cmp-kv">
        <div class="k">${escapeHtml(p.label || p.feed)}${p.ok ? '' : ' — unavailable'}</div>
        <div class="v">${searchPrice(p.last)}</div>
        <div class="dim" style="font-size:11px">${escapeHtml(p.as_of || (p.note || ''))}</div></div>`).join('');
    host.innerHTML = `<div class="chain-card">
        <div class="chain-head"><b>Feed comparison — ${escapeHtml(d.symbol || '')}</b>
            <div style="flex:1"></div><button class="btn small" id="cmpClose">Close</button></div>
        <div class="cmp-grid">${pairs || '<div class="dim">nothing to compare</div>'}</div>
        ${d.spread !== null && d.spread !== undefined ? `<div class="hint" style="margin-top:8px">difference across feeds: <b>${searchPrice(d.spread)}</b></div>` : ''}
        ${(d.notes || []).map((n) => `<div class="banner info" style="margin-top:8px">${escapeHtml(n)}</div>`).join('')}
    </div>`;
    const close = document.getElementById('cmpClose');
    if (close) close.onclick = () => host.remove();
}

/* ── watchlist (T37) ───────────────────────────────────────────── */

async function searchWatchlistLoad() {
    try {
        const d = await api('/api/control/search/watchlist');
        SEARCH.watchlist = d.watchlist || [];
    } catch (e) { SEARCH.watchlist = []; }
}

async function searchWatchlistAdd(symbols, remove) {
    try {
        const body = remove ? { remove: symbols } : { add: symbols };
        const d = await api('/api/control/search/watchlist', { method: 'POST', body });
        SEARCH.watchlist = d.watchlist || [];
        searchBuildIndex(true);
        if (typeof toast === 'function') {
            toast(document.getElementById('searchPanel') || document.body,
                remove ? `removed ${symbols.join(', ')} from the watchlist`
                       : `added ${symbols.join(', ')} to the watchlist`, 'ok');
        }
    } catch (e) {
        if (typeof toast === 'function') toast(document.getElementById('searchPanel') || document.body, 'watchlist save failed: ' + e, 'err');
    }
}

/* ── rendering the panel ───────────────────────────────────────── */

function searchClose() {
    const p = document.getElementById('searchPanel');
    if (p) p.classList.remove('open');
    SEARCH.open = false;
}

function searchMove(delta) {
    if (!SEARCH.rows.length) return;
    SEARCH.active = (SEARCH.active + delta + SEARCH.rows.length) % SEARCH.rows.length;
    const panel = document.getElementById('searchPanel');
    Array.from(panel.querySelectorAll('.search-row')).forEach((r, i) => r.classList.toggle('active', i === SEARCH.active));
    const active = panel.querySelector('.search-row.active');
    if (active) active.scrollIntoView({ block: 'nearest' });
}

function searchOpsToggle() {
    SEARCH.opsOpen = !SEARCH.opsOpen;
    searchRender((document.getElementById('programSearch') || {}).value || '');
}

function searchOpsHint(parsed) {
    const summary = (typeof searchOpsSummary === 'function') ? searchOpsSummary(parsed) : '';
    const errors = (parsed && parsed.errors) || [];
    const showOps = SEARCH.opsOpen || summary || errors.length;
    return `<div class="search-ops">
        ${showOps ? [
            summary ? `<span>filtering: <b>${escapeHtml(summary)}</b></span>` : '',
            errors.map((e) => `<span class="bad">${escapeHtml(e)}</span>`).join(' '),
        ].filter(Boolean).join(' · ') : 'Operators: <span class="kbd">type:</span> <span class="kbd">underlying:</span> <span class="kbd">strike:</span> <span class="kbd">exp:</span> <span class="kbd">vol:</span> <span class="kbd">exchange:</span> <span class="kbd">sort:</span> — Shift+Enter'}
    </div>`;
}

function searchRender(q, opts) {
    searchEnsureUI();
    const panel = document.getElementById('searchPanel');
    if (!panel) return;
    const o = opts || {};
    const text = (q || '').trim();
    const parsed = (typeof searchOpsParse === 'function') ? searchOpsParse(text) : { text: text, ops: {}, errors: [], symbols: [], active: false };
    SEARCH.parsed = parsed;

    if (!text) {
        const recents = ((S.config || {}).search || {}).recents || [];
        const pins = ((S.config || {}).search || {}).pins || [];
        const quick = [...new Set([...pins, ...recents, ...SEARCH.watchlist])].slice(0, 8);
        SEARCH.rows = quick.map((symbol) => ({ symbol, name: '', cat: 'Symbols' }));
        panel.innerHTML = `<div class="search-cat">Symbols</div>
            ${SEARCH.rows.map((r, i) => searchSymbolRowHTML({ symbol: r.symbol, source: 'recent' }, i)).join('')
              || '<div class="search-empty">No recents yet — type a ticker, a view or an action.</div>'}
            <div class="search-empty">Type to search the whole program — try <b>heatmap</b>, <b>stop run</b>,
                <b>vwap</b>, <b>scanner</b>, <b>replay</b>, a ticker like <b>AAPL</b>, or <b>@BTCUSDT</b>
                to open a panel pre-loaded (the typed overlay selector).</div>
            ${searchOpsHint(parsed)}`;
        panel.classList.add('open');
        SEARCH.open = true;
        panel.querySelectorAll('.search-row').forEach((el) => {
            el.onclick = () => { SEARCH.active = Number(el.dataset.i); searchRun({}); };
        });
        return;
    }

    searchBuildIndex(false);
    const indexRows = searchQuery((parsed.text || text).replace(LAUNCH_TAG_RE, ' ').trim());
    const symbolRows = o.symbolsPending ? (SEARCH.symbolRows || []) : (SEARCH.symbolRows || []);
    /* T12/B18: '@TAG' tokens become deep-launch rows — the typed overlay selector. */
    const tags = [];
    LAUNCH_TAG_RE.lastIndex = 0;
    let tagMatch;
    while ((tagMatch = LAUNCH_TAG_RE.exec(text)) && tags.length < 3) {
        if (tags.indexOf(tagMatch[1]) < 0) tags.push(tagMatch[1]);
    }
    const launchRows = [];
    tags.forEach((tag) => {
        const app = searchAppSymbol(tag);
        LAUNCH_TARGETS.forEach((target) => {
            launchRows.push({ launch: { symbol: app, view: target.view }, cat: 'Deep launch',
                title: 'Open ' + target.label + ' — ' + app,
                desc: 'opens the panel with the instrument pre-loaded (typed @ selector)' });
        });
    });
    SEARCH.rows = [...launchRows, ...symbolRows, ...indexRows];
    SEARCH.active = Math.min(SEARCH.active, Math.max(SEARCH.rows.length - 1, 0));

    if (!SEARCH.rows.length) {
        panel.innerHTML = `<div class="search-empty">nothing matches “${escapeHtml(text)}” —
            try fewer letters, a ticker, or open the <b>Guide</b>.</div>${searchOpsHint(parsed)}`;
        panel.classList.add('open');
        return;
    }

    let html = '';
    let cat = '';
    SEARCH.rows.forEach((r, i) => {
        const rowCat = r.cat || 'Symbols';
        if (rowCat !== cat) { cat = rowCat; html += `<div class="search-cat">${escapeHtml(cat)}</div>`; }
        html += r.symbol ? searchSymbolRowHTML(r, i) : `<div class="search-row${i === SEARCH.active ? ' active' : ''}" data-i="${i}"
                      title="${escapeHtml(r.title)} — ${escapeHtml(r.desc)}">
                    <span class="st">${escapeHtml(r.title)}</span>
                    <span class="sd">${escapeHtml(r.desc)}</span>
                    <span class="stag">${escapeHtml(r.cat.slice(0, 4).toLowerCase())}</span>
                 </div>`;
    });
    const meta = SEARCH.symbolMeta || {};
    const foot = [
        meta.linked === false ? 'no Alpaca account linked — symbols limited to recents, crypto and configured instruments' : '',
        meta.assets ? `${meta.assets} Alpaca assets cached` : '',
        SEARCH.selected.size ? `${SEARCH.selected.size} selected` : '',
    ].filter(Boolean).join(' · ');
    panel.innerHTML = html + (foot ? `<div class="search-ops">${escapeHtml(foot)}</div>` : '')
        + searchOpsHint(parsed)
        + (SEARCH.selected.size ? `<div class="search-foot">
            <span class="dim">${SEARCH.selected.size} symbol(s) selected</span>
            <button class="btn small" id="searchWlAdd">Add to watchlist</button>
            <button class="btn small" id="searchWlCmp">Compare feeds</button>
            <button class="btn small" id="searchWlClr">Clear</button></div>` : '');
    panel.classList.add('open');
    SEARCH.open = true;
    Array.from(panel.querySelectorAll('.search-row')).forEach((el) => {
        el.onclick = (ev) => {
            SEARCH.active = Number(el.dataset.i);
            const row = SEARCH.rows[SEARCH.active];
            if (row && row.symbol && (ev.ctrlKey || ev.metaKey)) {
                if (SEARCH.selected.has(row.symbol)) SEARCH.selected.delete(row.symbol);
                else SEARCH.selected.add(row.symbol);
                searchRender(q);
                return;
            }
            searchRun({});
        };
    });
    const wlAdd = document.getElementById('searchWlAdd');
    if (wlAdd) wlAdd.onclick = () => searchWatchlistAdd([...SEARCH.selected]);
    const wlCmp = document.getElementById('searchWlCmp');
    if (wlCmp) wlCmp.onclick = () => searchCompareOpen([...SEARCH.selected][0]);
    const wlClr = document.getElementById('searchWlClr');
    if (wlClr) wlClr.onclick = () => { SEARCH.selected.clear(); searchRender(q); };

    searchPushActive();
}

function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function searchSymbolsThenRender(q) {
    const parsed = (typeof searchOpsParse === 'function') ? searchOpsParse(q) : { text: q, ops: {} };
    const free = parsed.text || '';
    if (!free && !parsed.active) {
        // an empty query or a bare operator: still ask, the server returns the
        // user's own lists first (recents/pins/watchlist)
        if (!parsed.active) { searchRender(q); return; }
    }
    const rows = await searchSymbolsFetch(parsed, free);
    // an option-shaped query opens the chain instead of pretending to list contracts
    if (parsed.ops && parsed.ops.type === 'option') {
        const underlying = parsed.ops.underlying || (free || '').toUpperCase() || S.symbol;
        await searchChainOpen(underlying, parsed.exp && (parsed.exp.min === parsed.exp.max ? parsed.exp.min : undefined));
    }
    searchRender(q, { symbolsFetched: rows.length });
}

async function searchRun(opts) {
    const o = opts || {};
    const item = SEARCH.rows[SEARCH.active];
    if (!item) return;
    if (item.launch) {
        /* T12/B18: a deep-launch row — activate the instrument with the surface pre-loaded. */
        searchClose();
        searchActivateSymbol(item.launch.symbol, { view: item.launch.view });
        return;
    }
    if (item.symbol) {
        searchClose();
        if (o.chain) { await searchChainOpen(item.symbol); return; }
        searchActivateSymbol(item.symbol, { view: o.newPanel ? searchDefaultView() : undefined });
        return;
    }
    searchClose();
    try {
        const out = item.run && item.run();
        if (out && typeof out.then === 'function') await out;
    } catch (e) {
        if (typeof toast === 'function') toast(document.body, `“${item.title}” failed: ${e}`, 'err');
    }
    const input = document.getElementById('programSearch');
    if (input) input.blur();
}

/* ── hover help on the option menus themselves ─────────────────── */
const SELECT_HELP = {
    frameSelect: {
        range: 'Bars built from a fixed price range — a bar closes when price travels N ticks, whatever the time.',
        renko: 'Bricks that only change direction on a reversal — removes time entirely.',
        reversal: 'A bar closes on a reversal of N ticks against the extreme.',
        tick: 'A bar closes after a fixed number of prints — activity, not time.',
        volume: 'A bar closes after a fixed traded volume.',
        delta: 'Bars built from cumulative delta: closes when the delta inside the bar passes the trend threshold or reverses from its extreme. Effort, not time.',
    },
    tfSelect: {
        '1m': 'One-minute candles.', '5m': 'Five-minute candles.', '15m': 'Fifteen-minute candles.',
        '1h': 'Hourly candles.', '4h': 'Four-hour candles.', '1d': 'Daily candles.',
    },
    rangeSelect: {
        '1h': 'Load the last hour.', '4h': 'Load the last four hours.', '1d': 'Load the last day.',
        '7d': 'Load the last week.', '30d': 'Load the last month.',
    },
    symbolSelect: {},
    logLevel: { DEBUG: 'Everything, including per-message feed detail.', INFO: 'Normal operation.',
                WARNING: 'Problems worth noticing.', ERROR: 'Failures only.' },
};

function decorateSelects() {
    Object.entries(SELECT_HELP).forEach(([id, map]) => {
        const sel = document.getElementById(id);
        if (!sel) return;
        if (!sel.title) sel.title = 'Choose an option — hover one to see what it does.';
        Array.from(sel.options).forEach((opt) => {
            if (opt.title) return;
            const help = map[opt.value] || map[opt.textContent.trim()];
            if (help) opt.title = help;
        });
    });
}

/* ── the batcher counters, surfaced in the Logs view (T41) ─────── */

async function searchMetaRefresh() {
    const logs = document.querySelector('.view[data-view="logs"]');
    if (!logs || !logs.classList.contains('active')) return;
    let host = document.getElementById('searchMeta');
    if (!host) {
        host = document.createElement('div');
        host.id = 'searchMeta';
        host.className = 'hint';
        host.style.margin = '6px 0 0';
        const head = logs.querySelector('.view-head');
        if (head) head.insertAdjacentElement('afterend', host);
        else logs.insertBefore(host, logs.firstChild);
    }
    try {
        const d = await api('/api/control/search/meta');
        const c = d.counters || {};
        host.innerHTML = `palette stream: <b>${c.seen || 0}</b> messages seen · <b>${c.coalesced || 0}</b> coalesced · `
            + `<b>${c.dropped || 0}</b> dropped · ${c.batches || 0} batches / ${c.rows_sent || 0} rows · `
            + `window ${d.window_ms}ms · cap ${d.max_symbols} symbols · active ${(d.active || []).length}`
            + (d.linked ? '' : ' · Alpaca not linked (recents + crypto + local only)');
    } catch (e) {
        host.textContent = `palette stream counters unavailable: ${e}`;
    }
}

/* ── boot ──────────────────────────────────────────────────────── */

(function searchBoot() {
    let tries = 0;
    const tick = () => {
        tries += 1;
        searchEnsureUI();
        decorateSelects();
        if (!document.getElementById('programSearch') && tries < 40) setTimeout(tick, 500);
    };
    tick();
    setInterval(decorateSelects, 8000);
    setInterval(searchMetaRefresh, SEARCH_TIMING.META_MS);

    // the shared socket carries batched palette rows on its own channel
    if (typeof window.atlasOnEvent === 'function') {
        const original = window.atlasOnEvent;
        window.atlasOnEvent = function (channel, data) {
            if (typeof original === 'function') original(channel, data);
            if (channel === 'search' && data && data.rows) searchApplyRows(data.rows);
        };
    }
    searchWatchlistLoad().then(() => { if (SEARCH.open) searchRender(''); });

    // poll fallback: if the socket is down, rows still refresh twice a second
    SEARCH.pollTimer = setInterval(async () => {
        if (!SEARCH.open) return;
        if (typeof S !== 'undefined' && S.ws && S.ws.readyState === 1) return;
        try {
            const d = await api('/api/control/search/rows');
            if (d.rows && d.rows.length) searchApplyRows(d.rows);
        } catch (e) { /* ignore */ }
    }, 500);
})();

window.SEARCH = SEARCH;
window.SEARCH_TIMING = SEARCH_TIMING;
