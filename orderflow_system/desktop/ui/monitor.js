/* monitor.js — the read-only companion monitor: alerts, the simulated account, the watchlist and
 * one order-flow read, sized for a phone.
 *
 * WHERE THE DATA COMES FROM — five GETs, no writes, no new server surface:
 *   /api/atlas/alerts?limit=60       the alert log (the hub keeps it oldest-first; this page prints
 *                                    it newest-first)
 *   /api/atlas/replay/paper/state    the simulated account: position, mark, stats, working orders,
 *                                    closed legs
 *   /api/control/search/watchlist    the stored watchlist symbols
 *   /api/atlas/scanner?limit=200     the engine's own one-row-per-instrument live state — the
 *                                    quotes. A symbol the engine is not streaming has no row, and
 *                                    the row says so rather than showing a placeholder price.
 *   /api/atlas/market-read/{symbol}  the engine's deterministic read of the chosen instrument
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - monitor.html is a static file the app already serves at /desktop/monitor.html. This page adds
 *     no route and holds no state of its own, so a phone can watch a running session without
 *     touching it. It is inert if the shell ever loads it: with no monitor markup on the page it
 *     boots nothing and polls nothing.
 *   - Every failure is a sentence inside the panel it belongs to. A dead endpoint, a stopped engine
 *     or an empty watchlist never leaves a blank screen, and no loader throws at the page.
 *   - The pure half (formatting, ordering, the refusal sentences) runs under plain node — pinned by
 *     monitor.selftest.js and by orderflow_system/test_monitor.py.
 *   - One poller: registered with the app's pause registry when that module is on the page, and
 *     guarded on document.hidden / OFAP_PAUSED on every tick regardless.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const TICK_MS = 5000;
    const ALERT_LIMIT = 60;
    const QUOTE_LIMIT = 200;
    const LEVEL_ROWS = 6;
    const CLOSED_ROWS = 5;
    const STORE_KEY = 'ofap.monitor.symbol';
    const DASH = '—';
    const PANEL_NAMES = ['alerts', 'paper', 'watch', 'read'];
    const PANEL_TITLES = { alerts: 'alerts', paper: 'positions', watch: 'watchlist', read: 'read' };
    /* The alert payload's own context fields, in the order they read best. Anything else in `data`
       stays out: this is a sentence, not a dump of an arbitrary object. */
    const CONTEXT_KEYS = ['price', 'size', 'volume', 'side', 'multiple', 'levels', 'delta', 'ticks'];

    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function doc() { return (typeof document !== 'undefined' && document) ? document : null; }
    /* The message behind a failed call, as words — an Error object is never printed as "Error:", and
       nothing at all is an empty string rather than the literal "null". */
    function errText(err) {
        if (!err) return '';
        if (typeof err === 'string') return err;
        return String(err.message || '');
    }

    /* One plain sentence for a read that failed: the status when the app answered with one, a plain
       "not answering" when the connection itself failed, and never a parser's own words. */
    function failWord(err) {
        const text = errText(err);
        if (/^(the app|the route|no |nothing)/i.test(text)) return text;
        if (/fetch|network|networkerror|load failed/i.test(text)) return 'the app is not answering on this address';
        return text || 'the read failed';
    }

    /* ── the pure half ─────────────────────────────────────────────────────────────────────── */

    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    function normalize(symbol) { return String(symbol == null ? '' : symbol).trim().toUpperCase(); }

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }

    /* Plain words for a value that is not a price: integers stay integers, decimals lose float noise. */
    function fmtValue(value) {
        const n = num(value);
        if (n === null) {
            return (value === null || value === undefined || value === '') ? DASH : String(value);
        }
        if (Number.isInteger(n)) return String(n);
        return String(Math.round(n * 1e6) / 1e6);
    }

    function fmtPrice(value, digits) {
        const n = num(value);
        if (n === null) return DASH;
        const places = num(digits);
        return n.toFixed(places === null ? (Math.abs(n) >= 100 ? 2 : 6) : places);
    }

    /* PnL in ticks, signed and grouped — the unit the simulated account reports in, and a funded
       balance runs to seven figures of ticks on a cheap tick size. */
    function group(value) {
        const parts = String(value).split('.');
        return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (parts[1] === undefined ? '' : '.' + parts[1]);
    }

    function fmtTicks(value) {
        const n = num(value);
        if (n === null) return DASH;
        const rounded = Math.round(n * 10) / 10;
        return (rounded > 0 ? '+' : '') + group(rounded.toFixed(1));
    }

    function fmtPct(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n > 0 ? '+' : '') + n.toFixed(2) + '%';
    }

    /* The sign colouring: one word per value, used as a data-tone attribute. */
    function toneFor(value) {
        const n = num(value);
        if (n === null || n === 0) return 'flat';
        return n > 0 ? 'up' : 'down';
    }

    function severityTone(severity) {
        const word = String(severity == null ? '' : severity).toLowerCase();
        if (word === 'critical') return 'crit';
        if (word === 'warning') return 'warn';
        return 'info';
    }

    /* How old a stamp is, in words. A stamp from the future (clock skew) reads "now", never a
       negative age. */
    function fmtAge(ts_ms, now_ms) {
        const ts = num(ts_ms);
        const now = num(now_ms);
        if (!ts || !now) return 'never';
        const seconds = (now - ts) / 1000;
        if (seconds < 1) return 'now';
        if (seconds < 60) return Math.floor(seconds) + ' s ago';
        const minutes = Math.round(seconds / 60);
        if (minutes < 60) return minutes + ' min ago';
        const hours = Math.round(minutes / 60);
        if (hours < 24) return hours + ' h ago';
        return Math.round(hours / 24) + ' d ago';
    }

    /* Clock time in the reader's own timezone — the exact hour is not pinned by any test. */
    function fmtClock(ts_ms) {
        const ts = num(ts_ms);
        if (!ts) return DASH;
        const date = new Date(ts);
        const pad = (n) => (n < 10 ? '0' : '') + n;
        return pad(date.getHours()) + ':' + pad(date.getMinutes());
    }

    /* The log arrives oldest-first; a phone reads top-down, so the newest firing is the first row. */
    function alertsNewestFirst(alerts) {
        const rows = (Array.isArray(alerts) ? alerts : []).filter((row) => row && typeof row === 'object');
        return rows.slice().sort((a, b) => (num(b.ts_ms) || 0) - (num(a.ts_ms) || 0));
    }

    /* The alert's own context, as the one line under its message. */
    function alertContext(alert) {
        const data = (alert && alert.data) || {};
        if (!data || typeof data !== 'object') return '';
        const parts = [];
        CONTEXT_KEYS.forEach((key) => {
            const value = data[key];
            if (value === null || value === undefined || value === '') return;
            if (typeof value === 'object') return;
            parts.push(key + ' ' + fmtValue(value));
        });
        return parts.slice(0, 4).join(' · ');
    }

    function alertSentence(payload) {
        if (!payload) return 'the alert log did not answer — is the app running?';
        if (payload.ok !== true) return String(payload.error || 'the alert log did not answer');
        if (!alertsNewestFirst(payload.alerts).length) {
            return 'no alerts have fired — the log fills while the engine runs';
        }
        return '';
    }

    function alertRowHtml(alert, now_ms) {
        const row = alert || {};
        const context = alertContext(row);
        const tone = severityTone(row.severity);
        return '<li class="mon-row mon-alert" data-tone="' + tone + '">'
            + '<div class="mon-row-top"><span class="mon-sym">' + esc(normalize(row.symbol) || 'all symbols')
            + '</span><span class="mon-agedim">' + esc(fmtAge(row.ts_ms, now_ms)) + '</span></div>'
            + '<div class="mon-msg">' + esc(row.message || '') + '</div>'
            + '<div class="mon-meta">' + esc([row.kind, row.name, row.severity].filter(Boolean).join(' · '))
            + (context ? ' · ' + esc(context) : '') + '</div></li>';
    }

    function alertListHtml(payload, now_ms) {
        const sentence = alertSentence(payload);
        if (sentence) return '<li class="mon-empty">' + esc(sentence) + '</li>';
        return alertsNewestFirst(payload.alerts)
            .map((alert) => alertRowHtml(alert, now_ms)).join('');
    }

    function alertCountText(payload) {
        if (!payload || payload.ok !== true) return DASH;
        return String(alertsNewestFirst(payload.alerts).length);
    }

    /* ── the watchlist and its quotes ──────────────────────────────────────────────────────── */

    function quoteIndex(rows) {
        const out = {};
        (Array.isArray(rows) ? rows : []).forEach((row) => {
            const key = normalize(row && row.symbol);
            if (key) out[key] = row;
        });
        return out;
    }

    /* The watchlist in the user's own order, each row joined to the engine's row for it (or null). */
    function watchRows(symbols, quotes) {
        const index = quotes || {};
        return (Array.isArray(symbols) ? symbols : []).map((raw) => {
            const symbol = normalize(raw);
            const quote = index[symbol] || null;
            return {
                symbol: symbol,
                quote: quote,
                last: quote ? num(quote.last) : null,
                chg_pct: quote ? num(quote.chg_pct) : null,
                delta: quote ? num(quote.delta) : null,
            };
        }).filter((row) => !!row.symbol);
    }

    function watchRowHtml(row, active) {
        const pick = row || {};
        const on = pick.symbol && pick.symbol === normalize(active);
        const right = pick.quote
            ? '<span class="mon-last">' + esc(fmtPrice(pick.last)) + '</span>'
                + '<span class="mon-chg" data-tone="' + toneFor(pick.chg_pct) + '">'
                + esc(fmtPct(pick.chg_pct)) + '</span>'
                + '<span class="mon-delta" data-tone="' + toneFor(pick.delta) + '">&#916; '
                + esc(fmtValue(pick.delta)) + '</span>'
            : '<span class="mon-none">no live readings</span>';
        return '<li><button type="button" class="mon-pick' + (on ? ' on' : '')
            + (pick.quote ? '' : ' dim') + '" data-mon-symbol="' + esc(pick.symbol)
            + '" aria-label="read ' + esc(pick.symbol) + '">'
            + '<span class="mon-sym">' + esc(pick.symbol) + '</span>'
            + '<span class="mon-quote">' + right + '</span></button></li>';
    }

    function watchListHtml(payload, quotes, active) {
        if (!payload) return '<li class="mon-empty">the watchlist did not answer — is the app running?</li>';
        if (payload.ok !== true) {
            return '<li class="mon-empty">' + esc(String(payload.error || 'the watchlist did not answer')) + '</li>';
        }
        const symbols = Array.isArray(payload.watchlist) ? payload.watchlist : [];
        if (!symbols.length) {
            return '<li class="mon-empty">the watchlist is empty — add symbols in the app and they '
                + 'appear here</li>';
        }
        return watchRows(symbols, quotes).map((row) => watchRowHtml(row, active)).join('');
    }

    function watchSubText(payload, quotes) {
        if (!payload || payload.ok !== true) return 'the watchlist could not be read';
        const total = (Array.isArray(payload.watchlist) ? payload.watchlist : []).length;
        const index = quotes || {};
        const live = watchRows(payload.watchlist, index).filter((row) => !!row.quote).length;
        if (!total) return 'no symbols stored';
        if (!live) return 'no instrument here is streaming — quotes appear while the engine runs';
        return live + ' of ' + total + ' streaming · change is over the engine\'s own scanner window';
    }

    /* ── the simulated account ─────────────────────────────────────────────────────────────── */

    function positionLine(state, now_ms) {
        const st = state || {};
        if (!st.running) {
            return 'no simulated account is running — start one in the app\'s Replay view';
        }
        const pos = st.position || {};
        const side = String(pos.side || 'flat');
        const size = num(pos.size);
        if (side === 'flat' || !size) {
            return 'flat — no open position on ' + (normalize(st.symbol) || 'this instrument');
        }
        return side + ' ' + fmtValue(size) + ' @ ' + fmtPrice(pos.entry_price)
            + ' · opened ' + fmtAge(pos.entry_ms, now_ms);
    }

    function statsCells(state) {
        const st = state || {};
        if (!st.running) return [];
        const stats = st.stats || {};
        return [
            { label: 'realised', value: fmtTicks(stats.realised_ticks), tone: toneFor(stats.realised_ticks) },
            { label: 'open', value: fmtTicks(stats.unrealised_ticks), tone: toneFor(stats.unrealised_ticks) },
            { label: 'equity', value: fmtTicks(stats.equity_ticks), tone: toneFor(stats.equity_ticks) },
            { label: 'closed', value: fmtValue(stats.closed) + '  (' + fmtValue(stats.wins) + ' w / '
                + fmtValue(stats.losses) + ' l)', tone: 'flat' },
            { label: 'orders', value: fmtValue(stats.orders_submitted) + ' in · '
                + fmtValue(stats.orders_filled) + ' filled', tone: 'flat' },
        ];
    }

    function statsHtml(state) {
        const cells = statsCells(state);
        if (!cells.length) return '';
        return cells.map((cell) => '<div class="mon-cell"><span class="mon-cell-k">' + esc(cell.label)
            + '</span><span class="mon-cell-v" data-tone="' + esc(cell.tone) + '">' + esc(cell.value)
            + '</span></div>').join('');
    }

    function ordersHtml(state) {
        const st = state || {};
        if (!st.running) return '';
        const orders = Array.isArray(st.orders) ? st.orders : [];
        if (!orders.length) return '<li class="mon-empty">no working orders</li>';
        return orders.map((order) => {
            const row = order || {};
            const level = num(row.price) === null ? 'at market' : 'at ' + fmtPrice(row.price);
            const exits = [row.stop_loss === null || row.stop_loss === undefined ? '' : 'stop ' + fmtPrice(row.stop_loss),
                           row.take_profit === null || row.take_profit === undefined ? '' : 'target ' + fmtPrice(row.take_profit)]
                .filter(Boolean).join(' · ');
            return '<li class="mon-row"><div class="mon-row-top"><span class="mon-sym">'
                + esc(fmtValue(row.size) + ' ' + String(row.side || '')) + '</span>'
                + '<span class="mon-agedim">' + esc(String(row.kind || '')) + '</span></div>'
                + '<div class="mon-meta">' + esc(level) + (exits ? ' · ' + esc(exits) : '') + '</div></li>';
        }).join('');
    }

    /* The last few closed legs, newest first, so the panel answers "how did it go" at a glance. */
    function closedRows(state) {
        const st = state || {};
        const closed = Array.isArray(st.closed) ? st.closed : [];
        return closed.slice().reverse().slice(0, CLOSED_ROWS);
    }

    function closedHtml(state) {
        const st = state || {};
        if (!st.running) return '';
        const rows = closedRows(st);
        if (!rows.length) return '<li class="mon-empty">nothing has closed yet in this session</li>';
        return rows.map((leg) => {
            const row = leg || {};
            return '<li class="mon-row"><div class="mon-row-top"><span class="mon-sym">'
                + esc(normalize(row.direction) || 'leg') + '</span>'
                + '<span class="mon-last" data-tone="' + toneFor(row.pnl_ticks) + '">'
                + esc(fmtTicks(row.pnl_ticks)) + ' ticks</span></div>'
                + '<div class="mon-meta">' + esc(fmtPrice(row.entry_price) + ' \\u2192 ' + fmtPrice(row.exit_price))
                + ' · ' + esc(fmtValue(row.rr_ratio) + ' R') + '</div></li>';
        }).join('');
    }

    function paperSubText(payload) {
        if (!payload) return 'the simulated account did not answer — is the app running?';
        if (payload.ok !== true) return String(payload.error || 'the simulated account did not answer');
        const st = payload.state || {};
        if (!st.running) return 'no session is running';
        const mark = num(st.last_price);
        return normalize(st.symbol) + ' · tick ' + fmtValue(st.tick_size) + ' · '
            + (mark ? 'mark ' + fmtPrice(mark) : 'no print yet');
    }

    /* ── the order-flow read ───────────────────────────────────────────────────────────────── */

    /* §148 / T7-F8: with no symbol chosen nothing was asked, so nothing failed. The panel says so
       instead of blaming the app ("is the app running?" on an empty watchlist). `symbol` is optional
       so the pure helpers stay callable without it. */
    function readBanner(payload, symbol) {
        if (symbol === '') {
            return { text: 'no symbol chosen yet — pick one from the watchlist or open a paper session', kind: 'warn' };
        }
        if (!payload) return { text: 'the read did not answer — is the app running?', kind: 'warn' };
        if (payload.ok !== true) {
            return { text: String(payload.error || 'the read did not answer'), kind: 'warn' };
        }
        const regime = (payload.regime || {});
        const name = String(regime.name || '').replace(/_/g, ' ') || 'no named regime';
        const description = String(regime.description || '').trim();
        return { text: name + (description ? ' — ' + description : ''), kind: 'ok' };
    }

    function readInputsText(payload) {
        const inputs = (payload && payload.inputs) || {};
        const missing = Object.keys(inputs).filter((key) => (
            inputs[key] && typeof inputs[key] === 'object' && inputs[key].measured === false));
        if (!missing.length) return 'every signal measured';
        return 'not measured: ' + missing.join(', ');
    }

    /* §148 / T7-F9: a read that did not answer is not a market state. The list says the levels are
       unknown, and only an answered read with no levels claims there are none. */
    function readLevelsHtml(payload, symbol) {
        if (symbol === '') return '<li class="mon-empty">no symbol chosen yet</li>';
        if (!payload) {
            return '<li class="mon-empty">the read did not answer — the levels are unknown, not empty</li>';
        }
        const levels = (payload && Array.isArray(payload.levels)) ? payload.levels : [];
        if (!levels.length) return '<li class="mon-empty">no key levels in this state</li>';
        return levels.slice(0, LEVEL_ROWS).map((level) => {
            const row = level || {};
            const strength = num(row.strength);
            return '<li class="mon-row"><div class="mon-row-top"><span class="mon-sym">'
                + esc(fmtPrice(row.price)) + '</span><span class="mon-agedim">'
                + esc(String(row.kind || '').replace(/_/g, ' ')) + '</span></div>'
                + '<div class="mon-meta">' + esc(String(row.source || ''))
                + (strength === null ? '' : ' · ' + esc(Math.round(strength * 100) + '%')) + '</div></li>';
        }).join('');
    }

    function readSummaryText(payload) {
        if (!payload || payload.ok !== true) return '';
        return String(payload.summary || '').trim();
    }

    /* Which instrument the read is about: the simulated account's own when one is running, else the
       first watchlist symbol. Both come from the server — this page never picks a symbol itself. */
    function defaultSymbol(paperState, symbols) {
        const st = paperState || {};
        if (st.running && normalize(st.symbol)) return normalize(st.symbol);
        const list = Array.isArray(symbols) ? symbols : [];
        return normalize(list[0] || '');
    }

    function statusFor(failures, now_ms) {
        const names = Array.isArray(failures) ? failures.filter(Boolean) : [];
        if (names.length) {
            return { text: names.length + ' of ' + PANEL_NAMES.length + ' reads failed ('
                + names.join(', ') + ') — the rest is live', kind: 'warn' };
        }
        return { text: 'read only · updated ' + fmtClock(now_ms), kind: 'ok' };
    }

    /* ── the DOM half ──────────────────────────────────────────────────────────────────────── */

    const state = {
        alerts: null, paper: null, watch: null, quotes: null, read: null,
        symbol: '', panel: 'alerts', failures: {}, at: 0, busy: false, wired: false, timer: 0,
    };

    function el(id) { const d = doc(); return d ? d.getElementById(id) : null; }
    function setText(id, text) { const node = el(id); if (node) node.textContent = String(text == null ? '' : text); }
    function setHtml(id, html) { const node = el(id); if (node) node.innerHTML = html; }
    function setTone(id, tone) { const node = el(id); if (node) node.setAttribute('data-tone', tone); }

    function storedSymbol() {
        try { return normalize(win().localStorage.getItem(STORE_KEY) || ''); } catch (e) { return ''; }
    }
    function storeSymbol(symbol) {
        try { win().localStorage.setItem(STORE_KEY, normalize(symbol)); } catch (e) { /* storage blocked */ }
    }

    /* The shell's own helper when this page is ever loaded by it, plain fetch otherwise. Every call
       site below spells its path out in full: the end-of-build audit reads those literals, and a
       path it cannot read is a path it cannot guard. A non-answer becomes one sentence, not a
       parser's complaint about the body it could not read. */
    function api(path) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path);
        return fetch(path).then((res) => {
            if (!res.ok) {
                throw new Error('the app answered ' + res.status + ' ' + (res.statusText || ''));
            }
            return res.json().catch(() => {
                throw new Error('the app did not answer with data');
            });
        });
    }

    async function loadAlerts() {
        try {
            state.alerts = await api('/api/atlas/alerts?limit=' + ALERT_LIMIT);
            delete state.failures.alerts;
        } catch (err) {
            state.alerts = null;
            state.failures.alerts = 'alerts';
            setHtml('monAlertList', '<li class="mon-empty">the alert log could not be read: '
                + esc(failWord(err)) + '</li>');
            setText('monAlertCount', DASH);
            return;
        }
        paintAlerts();
    }

    async function loadPaper() {
        try {
            state.paper = await api('/api/atlas/replay/paper/state');
            delete state.failures.paper;
        } catch (err) {
            state.paper = null;
            state.failures.paper = 'positions';
            setText('monPaperSub', 'the simulated account could not be read: ' + failWord(err));
            setHtml('monPaperPosition', '');
            setHtml('monPaperStats', '');
            setHtml('monPaperOrders', '');
            setHtml('monPaperClosed', '');
            return;
        }
        paintPaper();
    }

    async function loadWatch() {
        try {
            state.watch = await api('/api/control/search/watchlist');
            delete state.failures.watch;
        } catch (err) {
            state.watch = null;
            state.failures.watch = 'watchlist';
        }
        paintWatch();
    }

    /* The quotes are the engine's own rows; without a running engine this is an empty list and every
       watchlist row says "no live readings". */
    async function loadQuotes() {
        try {
            state.quotes = await api('/api/atlas/scanner?limit=' + QUOTE_LIMIT);
            delete state.failures.quotes;
        } catch (err) {
            state.quotes = null;
            state.failures.quotes = 'quotes';
        }
        paintWatch();
    }

    async function loadRead() {
        const symbol = normalize(state.symbol);
        if (!symbol) {
            paintRead();
            return;
        }
        try {
            state.read = await api('/api/atlas/market-read/' + encodeURIComponent(symbol));
            delete state.failures.read;
        } catch (err) {
            state.read = null;
            state.failures.read = 'read';
        }
        paintRead();
    }

    /* The symbol the read is about, decided from what the server just answered. */
    function pickSymbol(force) {
        const current = normalize(state.symbol) || storedSymbol();
        if (current && !force) return current;
        const paper = (state.paper || {}).state || null;
        const symbols = ((state.watch || {}).watchlist) || [];
        return defaultSymbol(paper, symbols) || current;
    }

    function paintAlerts() {
        const payload = state.alerts;
        setHtml('monAlertList', alertListHtml(payload, Date.now()));
        setText('monAlertCount', alertCountText(payload));
    }

    function paintPaper() {
        const payload = state.paper || {};
        const body = payload.state || {};
        setText('monPaperSub', paperSubText(payload));
        setHtml('monPaperPosition', '<div class="mon-line">' + esc(positionLine(body, Date.now()))
            + '</div>');
        setHtml('monPaperStats', statsHtml(body));
        setHtml('monPaperOrders', ordersHtml(body));
        setHtml('monPaperClosed', closedHtml(body));
    }

    function paintWatch() {
        setHtml('monWatchRows', watchListHtml(state.watch, quoteIndex(state.quotes && state.quotes.rows),
            state.symbol));
        setText('monWatchSub', watchSubText(state.watch, quoteIndex(state.quotes && state.quotes.rows)));
        setText('monBadgeWatch', String(watchRows((state.watch || {}).watchlist || [],
            quoteIndex(state.quotes && state.quotes.rows)).filter((row) => !!row.quote).length));
    }

    function paintRead() {
        const payload = state.read;
        const symbol = normalize(state.symbol);
        setText('monReadSymbol', symbol || DASH);
        const banner = readBanner(payload, symbol);
        setText('monReadBanner', banner.text);
        setTone('monReadBanner', banner.kind === 'ok' ? 'flat' : 'warn');
        const passed = payload && payload.ok === true;
        const regime = (payload || {}).regime || {};
        setText('monReadRegime', passed ? String(regime.name || DASH).replace(/_/g, ' ') : DASH);
        setText('monReadConviction', passed ? fmtValue(payload.conviction) : DASH);
        setText('monReadInputs', passed ? readInputsText(payload) : '');
        setHtml('monReadSummary', readSummaryText(payload)
            ? '<div class="mon-line">' + esc(readSummaryText(payload)) + '</div>' : '');
        setHtml('monReadLevels', readLevelsHtml(passed ? payload : null, symbol));
    }

    function paintStatus() {
        const failures = Object.keys(state.failures).map((key) => state.failures[key]);
        const status = statusFor(failures, Date.now());
        setText('monStatus', status.text);
        setTone('monStatus', status.kind === 'ok' ? 'flat' : 'warn');
        setText('monUpdated', status.kind === 'ok' && state.at
            ? 'updated ' + fmtClock(state.at) : 'waiting for the app');
    }

    function paintBadges() {
        setText('monBadgeAlerts', alertCountText(state.alerts));
        const pos = ((state.paper || {}).state || {}).position || {};
        const side = String(pos.side || '');
        setText('monBadgePaper', side && side !== 'flat' ? side : 'flat');
        setTone('monBadgePaper', side === 'long' ? 'up' : (side === 'short' ? 'down' : 'flat'));
    }

    async function refresh() {
        if (state.busy) return;
        state.busy = true;
        try {
            await Promise.all([loadAlerts(), loadPaper(), loadWatch(), loadQuotes()]);
            state.symbol = pickSymbol(false);
            await loadRead();
            state.at = Date.now();
            paintStatus();
            paintBadges();
        } finally {
            state.busy = false;
        }
    }

    function tick() {
        if (typeof document !== 'undefined' && document && document.hidden) return;
        if (win().OFAP_PAUSED) return;
        if (state.busy) return;
        void refresh();
    }

    function showPanel(name) {
        const wanted = PANEL_NAMES.indexOf(name) >= 0 ? name : 'alerts';
        state.panel = wanted;
        const d = doc();
        if (!d || !d.querySelectorAll) return wanted;
        PANEL_NAMES.forEach((panel) => {
            const section = d.querySelector('[data-mon-panel="' + panel + '"]');
            if (section) section.classList.toggle('on', panel === wanted);
            const tab = d.querySelector('[data-mon-tab="' + panel + '"]');
            if (tab) {
                tab.classList.toggle('on', panel === wanted);
                tab.setAttribute('aria-selected', panel === wanted ? 'true' : 'false');
            }
        });
        return wanted;
    }

    function selectSymbol(raw) {
        const symbol = normalize(raw);
        if (!symbol) return '';
        state.symbol = symbol;
        storeSymbol(symbol);
        showPanel('read');
        void refresh();
        return symbol;
    }

    function onClick(ev) {
        const node = ev && ev.target;
        if (!node || !node.closest) return;
        const tab = node.closest('[data-mon-tab]');
        if (tab) { showPanel(tab.getAttribute('data-mon-tab')); return; }
        const pick = node.closest('[data-mon-symbol]');
        if (pick) { selectSymbol(pick.getAttribute('data-mon-symbol')); return; }
        const act = node.closest('[data-mon-act]');
        if (act && act.getAttribute('data-mon-act') === 'refresh') void refresh();
    }

    function wire() {
        if (state.wired) return false;
        const d = doc();
        if (!d || !d.getElementById('monStatus')) return false;   // not the monitor page: stay inert
        state.wired = true;
        state.symbol = storedSymbol();
        showPanel(state.panel);
        if (d.body) d.body.addEventListener('click', onClick);
        d.addEventListener('visibilitychange', () => { if (!d.hidden) void refresh(); });
        /* The cadence, handed to the app's pause registry when that module is on the page: P (or the
           topbar chip) clears this timer and a resume rebuilds it. On the standalone page the
           document.hidden / OFAP_PAUSED checks in tick() are the guard. */
        const startPolling = () => {
            const id = setInterval(tick, TICK_MS);
            const pause = win().OFAPPause;
            if (pause && pause.register) pause.register(id, startPolling);
            return id;
        };
        state.timer = startPolling();
        void refresh();
        return true;
    }

    const surface = {
        VERSION: VERSION, TICK_MS: TICK_MS, ALERT_LIMIT: ALERT_LIMIT, QUOTE_LIMIT: QUOTE_LIMIT,
        LEVEL_ROWS: LEVEL_ROWS, CLOSED_ROWS: CLOSED_ROWS, DASH: DASH, PANEL_NAMES: PANEL_NAMES,
        PANEL_TITLES: PANEL_TITLES, CONTEXT_KEYS: CONTEXT_KEYS,
        esc: esc, normalize: normalize, num: num, failWord: failWord, fmtValue: fmtValue,
        fmtPrice: fmtPrice,
        group: group, fmtTicks: fmtTicks, fmtPct: fmtPct, toneFor: toneFor, severityTone: severityTone,
        fmtAge: fmtAge, fmtClock: fmtClock, alertsNewestFirst: alertsNewestFirst,
        alertContext: alertContext, alertSentence: alertSentence, alertRowHtml: alertRowHtml,
        alertListHtml: alertListHtml, alertCountText: alertCountText, quoteIndex: quoteIndex,
        watchRows: watchRows, watchRowHtml: watchRowHtml, watchListHtml: watchListHtml,
        watchSubText: watchSubText, positionLine: positionLine, statsCells: statsCells,
        statsHtml: statsHtml, ordersHtml: ordersHtml, closedRows: closedRows, closedHtml: closedHtml,
        paperSubText: paperSubText, readBanner: readBanner, readInputsText: readInputsText,
        readLevelsHtml: readLevelsHtml, readSummaryText: readSummaryText, defaultSymbol: defaultSymbol,
        statusFor: statusFor, showPanel: showPanel, selectSymbol: selectSymbol, onClick: onClick,
        paintBadges: paintBadges, paintStatus: paintStatus, refresh: refresh, tick: tick, wire: wire,
        state: () => state,
    };

    const w = win();
    if (w) w.OFAPMONITOR = surface;
    if (typeof module !== 'undefined' && module.exports) module.exports = surface;

    const bootDoc = doc();
    if (bootDoc) {
        if (bootDoc.readyState === 'loading') bootDoc.addEventListener('DOMContentLoaded', wire);
        else wire();
    }
})();
