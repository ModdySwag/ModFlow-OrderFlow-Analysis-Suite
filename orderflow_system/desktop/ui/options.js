/* options.js — the Options panel: Deribit's public crypto option chain, one expiry at a time.
 *
 * WHERE THE DATA COMES FROM — nothing here is invented. Both routes are this app's own server (the
 * venue sends no CORS header, so the browser can never call Deribit directly):
 *   GET /api/control/deribit/chain?symbol=BTCUSDT[&expiry=16SEP26][&width=10]
 *     → { ok, symbol, currency, expiry, expiry_instrument, expiries: [{code,label,ms,days,strikes,
 *         calls,puts}], strikes: [{strike, call, put}], forward, width, tickers, ticker_errors,
 *         quoted_sides, note, coverage, error }
 *       Each `call`/`put` side is one instrument's ticker: { instrument, bid, ask, mid, iv, delta,
 *       gamma, theta, vega, rho, oi, volume, underlying, ts, state }.
 *   GET /api/control/deribit/ticker?instrument=BTC-16SEP26-68000-C
 *     → the same shape for one contract, read when a ladder row is picked (that is where the full
 *       Greek set lives; the ladder carries it too, for the window it drew).
 *
 * THE THREE STATES THAT MATTER, each with its own sentence:
 *   - the symbol maps to no Deribit currency (an index, FX, an equity) → the mandatory sentence
 *     "crypto only via Deribit — no options feed for <SYMBOL>", and NO request is made for it;
 *   - the venue refuses or is unreachable → the server's own words, not a generic one;
 *   - a currency with no chain today (Deribit lists SOL spot but no SOL options) → the server's own
 *     sentence again. A panel that cannot say which of these it is would be guessing.
 *
 * WHAT IT COSTS: an option ladder is only honest with live bid/ask/IV/Greeks, and Deribit exposes
 * those per instrument (its batch endpoint refuses an array — "invalid json", checked live), so the
 * server reads the window's tickers through a bounded pool. That is why this panel refreshes at
 * 20 s and not at the tape's rate: ~40 requests every 20 s on a public API is a polite cadence, and
 * a client-side 10 s TTL answers an expiry flip-flop without touching the wire at all.
 *
 * Read-only by construction: two GETs, no sockets, no engine verb, nothing stored anywhere.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const CHAIN_URL = '/api/control/deribit/chain';
    const TICKER_URL = '/api/control/deribit/ticker';
    const INTERVAL_MS = 20000;      /* a public API's cadence, not a tick chart's */
    const CACHE_MS = 10000;         /* a payload this fresh is not fetched twice */
    const WIDTH = 10;               /* strikes each side of the forward, the server's default */
    const VIEW = '.view[data-view="options"]';
    const DASH = '—';
    /* The currencies Deribit quotes options on. This mirrors the server's table on purpose: the
       panel must be able to answer "no feed for this symbol" without asking anyone. */
    const OPTION_CURRENCIES = ['BTC', 'ETH', 'SOL'];
    const QUOTE_SUFFIXES = ['PERPUSDT', 'PERP', 'USDT', 'USDC', 'USD'];

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    /* ── the decisions (pure: pinned by options.selftest.js, no DOM in reach) ───────────────────── */

    /* BTCUSDT → BTC, ethusdt → ETH, BTC-USD → BTC, SOLUSDT → SOL; an index, FX or equity → ''. */
    function currencyFor(symbol) {
        const text = String(symbol == null ? '' : symbol).toUpperCase().replace(/[^A-Z0-9]/g, '');
        if (!text) return '';
        if (OPTION_CURRENCIES.indexOf(text) >= 0) return text;
        for (let i = 0; i < QUOTE_SUFFIXES.length; i++) {
            const suffix = QUOTE_SUFFIXES[i];
            const base = text.slice(0, text.length - suffix.length);
            if (text.length > suffix.length && text.slice(-suffix.length) === suffix
                && OPTION_CURRENCIES.indexOf(base) >= 0) {
                return base;
            }
        }
        return '';
    }

    /* The one sentence this panel must never get wrong: the honest answer for a market Deribit does
       not quote options on. The server's own refusal carries the same lead, so a drift between the
       two tables shows up as a failing test rather than as a silent blank panel. */
    function coverageSentence(symbol) {
        return 'crypto only via Deribit — no options feed for ' + String(symbol == null ? '' : symbol).trim()
            + ' — Deribit lists BTC and ETH option chains today (SOL is spot only)';
    }

    /* Newest expiry first is a mistake a feed can make; the panel sorts what it is handed. */
    function expiriesFrom(payload) {
        const raw = (payload && Array.isArray(payload.expiries)) ? payload.expiries : [];
        const out = [];
        raw.forEach((entry) => {
            if (!entry || typeof entry !== 'object') return;
            const code = String(entry.code || '').trim();
            if (!code) return;
            const ms = num(entry.ms);
            out.push({
                code: code,
                instrument: String(entry.instrument || ''),
                ms: ms === null ? 0 : ms,
                label: String(entry.label || code),
                strikes: num(entry.strikes) || 0,
                days: num(entry.days) || 0,
            });
        });
        out.sort((a, b) => (a.ms - b.ms) || (a.code < b.code ? -1 : (a.code > b.code ? 1 : 0)));
        return out;
    }

    /* One side of a ladder row, or null when that strike was not quoted: an unquoted strike is not a
       zero, and the cell says 'no quote' rather than '0.0000'. */
    function sideOf(raw) {
        if (!raw || typeof raw !== 'object') return null;
        const instrument = String(raw.instrument || '').trim();
        if (!instrument) return null;
        return {
            instrument: instrument,
            bid: num(raw.bid), ask: num(raw.ask), mid: num(raw.mid), mark: num(raw.mark),
            iv: num(raw.iv), delta: num(raw.delta), gamma: num(raw.gamma), theta: num(raw.theta),
            vega: num(raw.vega), rho: num(raw.rho),
            oi: num(raw.oi), volume: num(raw.volume), underlying: num(raw.underlying), ts: num(raw.ts),
        };
    }

    function ladderFrom(payload) {
        const raw = (payload && Array.isArray(payload.strikes)) ? payload.strikes : [];
        const rows = [];
        raw.forEach((entry) => {
            const strike = num(entry && entry.strike);
            if (strike === null || strike <= 0) return;      /* a row without a strike is not a row */
            rows.push({ strike: strike, call: sideOf(entry.call), put: sideOf(entry.put) });
        });
        rows.sort((a, b) => a.strike - b.strike);
        return rows;
    }

    /* Which row the forward sits on — the money row is marked, never invented. */
    function atmIndex(rows, forward) {
        const at = num(forward);
        if (at === null || at <= 0 || !rows.length) return -1;
        let best = 0;
        rows.forEach((row, index) => {
            if (Math.abs(row.strike - at) < Math.abs(rows[best].strike - at)) best = index;
        });
        return best;
    }

    /* ── formatting: the edge where venue numbers become text ───────────────────────────────────── */

    function fmtStrike(value) {
        const n = num(value);
        if (n === null) return DASH;
        const text = String(Math.round(n));
        return n % 1 === 0 ? text.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : text;
    }
    function fmtPrice(value) {
        const n = num(value);
        if (n === null) return DASH;
        const abs = Math.abs(n);
        if (abs === 0) return '0';                    /* a real zero is a fact on a quoted contract */
        if (abs < 0.001) return n.toFixed(6);
        if (abs < 1) return n.toFixed(4);
        if (abs < 1000) return n.toFixed(2);
        return n.toFixed(1);
    }
    function fmtPct(value) {
        const n = num(value);
        return n === null ? DASH : n.toFixed(2) + '%';
    }
    function fmtGreek(value) {
        const n = num(value);
        if (n === null) return DASH;
        if (Math.abs(n) >= 100) return n.toFixed(1);
        /* a non-zero greek below a milli-unit would round to '0.000' and read as no exposure at all */
        if (n !== 0 && Math.abs(n) < 0.001) return n.toExponential(2);
        return n.toFixed(3);
    }
    function fmtDelta(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n > 0 ? '+' : '') + fmtGreek(n);
    }
    function fmtSize(value) {
        const n = num(value);
        if (n === null) return DASH;
        const abs = Math.abs(n);
        if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        if (abs === 0) return '0';
        return String(Math.round(n * 100) / 100);
    }
    function clockOf(ms) {
        const n = num(ms);
        if (n === null || n <= 0) return '';
        try { return new Date(n).toLocaleTimeString(); } catch (e) { return ''; }
    }

    /* ── the client-side TTL cache: what a fresh payload saves ─────────────────────────────────── */

    function cacheKey(symbol, expiry, width) {
        return [String(symbol || '').trim().toUpperCase(), String(expiry || '').trim().toUpperCase(),
            String(width || WIDTH)].join('|');
    }
    function cacheGet(key, now) {
        const item = state.cache[key];
        if (!item) return null;
        const at = num(now) === null ? Date.now() : num(now);
        if (at - item.at >= CACHE_MS) { delete state.cache[key]; return null; }
        return item.payload;
    }
    /* D-01: reads expire by access, so a (symbol, expiry) key nobody asks for again stayed
       resident for the session. A put past the cap sweeps the expired keys, then the oldest. */
    const CACHE_MAX = 24;

    function cachePut(key, payload, now) {
        const at = num(now) === null ? Date.now() : num(now);
        state.cache[key] = { at: at, payload: payload };
        if (cacheSize() > CACHE_MAX) {
            Object.keys(state.cache).forEach(function (k) {
                if (at - state.cache[k].at >= CACHE_MS) delete state.cache[k];
            });
            while (cacheSize() > CACHE_MAX) {
                let oldest = null;
                Object.keys(state.cache).forEach(function (k) {
                    if (oldest === null || state.cache[k].at < state.cache[oldest].at) oldest = k;
                });
                if (oldest === null) break;
                delete state.cache[oldest];
            }
        }
        return payload;
    }
    function cacheSize() { return Object.keys(state.cache).length; }
    /* A test hook: the panel never needs to drop its own cache, the TTL does it. */
    function cacheClear() {
        const dropped = cacheSize();
        state.cache = {};
        return dropped;
    }

    /* ── the state machine: one object the renderer and the selftest both read ─────────────────── */

    function plan(payload, err, symbol, now, expiry) {
        const at = num(now) === null ? Date.now() : num(now);
        const st = {
            state: 'loading', symbol: String(symbol == null ? '' : symbol).trim(),
            currency: '', message: '', note: '', expiries: [], expiry: String(expiry || ''),
            rows: [], count: 0, forward: null, width: WIDTH, source: 'deribit',
            tickers: 0, tickerErrors: 0, tickerErrorSample: [], quoted: 0, fromCache: false, updatedAt: 0,
        };
        if (!st.symbol) {
            st.state = 'nosymbol';
            st.message = 'no instrument is active yet — pick one in the top bar and its Deribit chain loads here.';
            return st;
        }
        if (err) {
            st.state = 'error';
            st.message = 'the chain request failed: ' + String(err) + ' — press Refresh to try again.';
            return st;
        }
        if (!payload || typeof payload !== 'object') {           /* before the first answer */
            st.message = 'loading the Deribit chain…';
            return st;
        }
        st.source = String(payload.source || 'deribit');
        st.currency = String(payload.currency || currencyFor(st.symbol));
        st.expiries = expiriesFrom(payload);
        st.rows = ladderFrom(payload);
        st.count = st.rows.length;
        st.forward = num(payload.forward);
        st.width = num(payload.width) || WIDTH;
        st.tickers = num(payload.tickers) || 0;
        st.tickerErrors = num(payload.ticker_errors) || 0;
        st.tickerErrorSample = (Array.isArray(payload.ticker_error_sample) ? payload.ticker_error_sample : [])
            .filter((note) => typeof note === 'string' && note.trim()).slice(0, 2);
        st.quoted = num(payload.quoted_sides) || 0;
        st.note = String(payload.note || '');
        st.updatedAt = num(payload.at) || at;
        st.expiry = String(payload.expiry || st.expiry || '');
        if (payload.coverage === false) {
            st.state = 'nocoverage';
            /* the server's own refusal when it sent one — its sentence carries the same lead */
            st.message = String(payload.error || '').trim() || coverageSentence(st.symbol);
            return st;
        }
        if (payload.ok === false) {
            st.state = 'error';
            st.message = String(payload.error || 'the chain request was refused').trim();
            return st;
        }
        if (!st.count) {
            st.state = 'empty';
            st.message = 'Deribit listed no ' + (st.currency || '') + ' strikes for '
                + (st.expiry || 'this expiry') + ' — the expiry list above came from the same reply.';
            return st;
        }
        st.state = 'ok';
        return st;
    }

    function subText(st) {
        if (!st) return 'idle';
        const parts = [];
        const section = sectionEl();
        const onScreen = !!(section && section.classList && section.classList.contains('active'));
        if (!onScreen) parts.push('paused — this panel is not on screen');
        else if (!autoRefreshOn()) parts.push('auto-refresh off — press Refresh for a one-off read');
        else if (state.polling === 'bus') parts.push('polling ' + (INTERVAL_MS / 1000) + 's via the shared bus');
        else if (state.polling === 'timer') parts.push('polling ' + (INTERVAL_MS / 1000) + 's from this panel\'s own timer (no bus)');
        else parts.push('auto-refresh on');
        if (st.fromCache) parts.push('from the 10s cache');
        if (st.state === 'ok') {
            parts.push(st.symbol + (st.currency ? ' → ' + st.currency : '') + ' ' + st.expiry);
            parts.push('±' + st.width + ' strikes around ' + fmtStrike(st.forward));
            parts.push(st.count + ' strike row(s), ' + st.quoted + ' quoted side(s)');
            if (st.tickers) parts.push(st.tickers + ' ticker(s) read');
            if (st.tickerErrors) {
                /* The count alone would leave a reader guessing: the venue's own refusal rides along. */
                parts.push(st.tickerErrors + ' quote(s) unavailable');
                if (st.tickerErrorSample.length) parts.push(st.tickerErrorSample[0]);
            }
            parts.push('updated ' + (clockOf(st.updatedAt) || 'never'));
        } else {
            parts.push(st.message);
        }
        return parts.join(' · ');
    }

    /* ── the markup (every venue string goes through esc) ─────────────────────────────────────── */

    const HEAD = '<thead><tr><th class="opt-label" rowspan="2">strike</th>'
        + '<th colspan="6">calls</th><th colspan="6">puts</th></tr>'
        + '<tr><th>bid</th><th>ask</th><th>IV</th><th>Δ</th><th>OI</th><th>vol</th>'
        + '<th>bid</th><th>ask</th><th>IV</th><th>Δ</th><th>OI</th><th>vol</th></tr></thead>';

    function headHtml() { return HEAD; }

    function sideCells(side, label) {
        if (!side) {
            return '<td class="opt-none" colspan="6">no ' + esc(label) + ' quote listed</td>';
        }
        const tip = esc(side.instrument + ' — click for its full Greeks');
        const cell = (text) => '<td data-instrument="' + esc(side.instrument) + '" title="' + tip + '">'
            + esc(text) + '</td>';
        return cell(fmtPrice(side.bid)) + cell(fmtPrice(side.ask)) + cell(fmtPct(side.iv))
            + cell(fmtDelta(side.delta)) + cell(fmtSize(side.oi)) + cell(fmtSize(side.volume));
    }

    function rowHtml(row, isAtm) {
        return '<tr' + (isAtm ? ' class="opt-atm"' : '') + '>'
            + '<td class="opt-strike">' + esc(fmtStrike(row.strike)) + '</td>'
            + sideCells(row.call, 'call') + sideCells(row.put, 'put') + '</tr>';
    }

    function bodyHtml(st) {
        if (!st || st.state === 'loading') {
            return '<div class="dim">Loading…</div>';
        }
        if (st.state !== 'ok') {
            const tag = '<span class="tag ' + (st.state === 'error' ? 'no' : 'warn') + '">'
                + (st.state === 'nocoverage' ? 'no coverage' : st.state) + '</span>';
            return '<div class="log-line">' + tag + '<span class="opt-msg">' + esc(st.message) + '</span></div>';
        }
        const atm = atmIndex(st.rows, st.forward);
        const rows = st.rows.map((row, index) => rowHtml(row, index === atm)).join('');
        const foot = '<div class="dim opt-note">' + esc(st.note) + '</div>';
        return '<div class="opt-wrap"><table class="opt-table">' + headHtml() + '<tbody>' + rows
            + '</tbody></table></div>' + foot;
    }

    /* The row a click asked about: the contract's own numbers, from the venue's ticker. */
    function detailHtml(payload, err, instrument) {
        const name = String(instrument || '').trim();
        if (!name) return '';
        if (err) {
            return '<span class="tag no">ticker</span><span class="opt-msg">' + esc(name + ' — ' + err) + '</span>';
        }
        if (!payload || typeof payload !== 'object') {
            return '<span class="tag warn">ticker</span><span class="opt-msg">reading ' + esc(name) + '…</span>';
        }
        if (payload.ok === false) {
            return '<span class="tag no">ticker</span><span class="opt-msg">' + esc(name + ' — ' + (payload.error || 'refused')) + '</span>';
        }
        const bits = ['mark ' + fmtPrice(payload.mark), 'IV ' + fmtPct(payload.iv),
            'Δ ' + fmtDelta(payload.delta), 'Γ ' + fmtGreek(payload.gamma), 'Θ ' + fmtGreek(payload.theta),
            'V ' + fmtGreek(payload.vega), 'ρ ' + fmtGreek(payload.rho),
            'OI ' + fmtSize(payload.oi), 'vol ' + fmtSize(payload.volume),
            'forward ' + fmtPrice(payload.underlying), clockOf(payload.ts) ? 'as of ' + clockOf(payload.ts) : ''];
        return '<span class="tag ok">ticker</span><span class="opt-msg"><b>' + esc(name) + '</b> · '
            + bits.filter(Boolean).map(esc).join(' · ') + '</span>';
    }

    /* ── state ─────────────────────────────────────────────────────────────────────────────────── */

    const state = {
        plan: null,              /* the last plan() result, what render() paints */
        symbol: '',              /* the symbol the current plan belongs to */
        expiry: '',              /* the expiry the user picked ('' = the server's nearest) */
        cache: {},               /* key → {at, payload}, the 10s TTL */
        ticker: null,            /* the last ticker payload a row click asked for */
        detail: '',              /* the instrument whose ticker is on screen */
        detailError: '',
        polling: 'idle',         /* 'idle' | 'bus' | 'timer' */
        unsubscribe: null,
        timer: null,
        selectCodes: '',         /* what the expiry <select> was built from */
        section: null,
        bound: false,
        booting: false,
    };

    function sectionEl() {
        if (state.section) return state.section;
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector(VIEW);
    }
    function isActive() {
        const section = sectionEl();
        return !!(section && section.classList && section.classList.contains('active'));
    }
    /* Defensive by request: the engine's symbol when it is there, the app's own select otherwise. */
    function activeSymbol() {
        const fromState = (typeof S !== 'undefined' && S) ? S.symbol : '';
        const select = el('symbolSelect');
        return String(fromState || (select && select.value) || '').trim();
    }
    function autoRefreshOn() {
        const box = el('optionsAuto');
        return box ? !!box.checked : true;
    }
    function paramsNow() {
        const params = { symbol: activeSymbol(), width: WIDTH };
        if (state.expiry) params.expiry = state.expiry;
        return params;
    }
    function urlNow() {
        const params = paramsNow();
        let url = CHAIN_URL + '?symbol=' + encodeURIComponent(params.symbol) + '&width=' + WIDTH;
        if (params.expiry) url += '&expiry=' + encodeURIComponent(params.expiry);
        return url;
    }
    function stateNow() {
        const st = state.plan;
        return {
            version: VERSION,
            symbol: activeSymbol(),
            currency: currencyFor(activeSymbol()),
            expiry: state.expiry,
            plan: st ? st.state : 'idle',
            rows: st ? st.count : 0,
            expiries: st ? st.expiries.length : 0,
            polling: state.polling,
            auto: autoRefreshOn(),
            cache: cacheSize(),
            detail: state.detail,
            updatedAt: st ? st.updatedAt : 0,
            error: (st && st.state === 'error') ? st.message : '',
        };
    }

    /* ── the DOM half ─────────────────────────────────────────────────────────────────────────── */

    function render() {
        const st = state.plan;
        const body = el('optionsBody');
        if (body) body.innerHTML = bodyHtml(st);
        const count = el('optionsCount');
        if (count) count.textContent = st ? String(st.count) : '0';
        const sub = el('optionsSub');
        if (sub) sub.textContent = subText(st);
        const detail = el('optionsDetail');
        if (detail) detail.innerHTML = detailHtml(state.ticker, state.detailError, state.detail);
        syncSelect(st);
        return st;
    }

    /* The expiry control mirrors what the server sent, and never invents an option: a <select> only
       holds what it offers. Rebuilt only when the codes change, so a repaint cannot steal a pick. */
    function syncSelect(st) {
        const select = el('optionsExpiry');
        if (!select) return false;
        const expiries = (st && st.expiries) || [];
        const codes = expiries.map((entry) => entry.code).join(',');
        if (codes !== state.selectCodes) {
            select.innerHTML = expiries.map((entry) => '<option value="' + esc(entry.code) + '">'
                + esc(entry.code + ' · ' + entry.label + (entry.days ? ' · ' + entry.days + 'd' : ' · today')
                    + ' · ' + entry.strikes + ' strikes') + '</option>').join('');
            state.selectCodes = codes;
        }
        select.disabled = !expiries.length;
        const wanted = String((st && st.expiry) || state.expiry || '');
        if (!wanted) return false;
        const offered = Array.prototype.slice.call(select.options || [])
            .some((option) => String(option.value) === wanted);
        if (!offered) return false;                  /* never force a value the control cannot hold */
        if (select.value !== wanted) select.value = wanted;
        return true;
    }

    function onChain(payload) {
        const symbol = activeSymbol();
        if (payload && typeof payload === 'object' && payload.ok !== false) {
            /* Cached twice on purpose: under the key we asked with, and under the expiry the server
               answered with — so re-picking that expiry after a symbol round-trip is a cache hit. */
            const answered = String(payload.expiry || state.expiry || '');
            cachePut(cacheKey(symbol, state.expiry, WIDTH), payload, Date.now());
            cachePut(cacheKey(symbol, answered, WIDTH), payload, Date.now());
            if (!state.expiry) state.expiry = answered;
        }
        state.symbol = symbol;
        state.plan = plan(payload, null, symbol, Date.now(), state.expiry);
        render();
        return payload;
    }

    function loading() {
        state.plan = plan(null, null, activeSymbol(), Date.now(), state.expiry);
        render();
    }

    async function loadChain(options) {
        const force = !!(options && options.force);
        const symbol = activeSymbol();
        const key = cacheKey(symbol, state.expiry, WIDTH);
        state.symbol = symbol;
        if (!symbol) { render(); return null; }               /* nothing to ask for */
        if (!currencyFor(symbol)) {                          /* no request for a market with no feed */
            state.plan = plan({ coverage: false }, null, symbol, Date.now(), state.expiry);
            render();
            return state.plan;
        }
        if (!force) {
            const hit = cacheGet(key, Date.now());
            if (hit) {
                state.plan = plan(hit, null, symbol, Date.now(), state.expiry);
                state.plan.fromCache = true;
                render();
                return state.plan;
            }
        }
        let payload = null;
        try {
            payload = await getJson(urlNow());
        } catch (err) {
            payload = null;
            state.plan = plan(null, errText(err), symbol, Date.now(), state.expiry);
            render();
            return state.plan;
        }
        /* P1-10: a chain that arrived is a fresh sample; a dead poll ages past two intervals. */
        if (window.OFAPFRESH && payload) OFAPFRESH.stamp('options', { ageMs: 0, windowMs: 2 * INTERVAL_MS });
        return onChain(payload);
    }

    async function getJson(url) {
        const w = win();
        if (typeof w.api === 'function') return Promise.resolve(w.api(url));
        if (typeof fetch !== 'function') return Promise.reject(new Error('no fetch available'));
        return fetch(url, { headers: { Accept: 'application/json' } }).then((response) => {
            if (!response || !response.ok) {
                throw new Error(url + ' → HTTP ' + (response ? response.status : 'no response'));
            }
            return response.json();
        });
    }

    /* A picked row asks for that one contract's ticker — where the whole Greek set lives. */
    async function loadTicker(instrument) {
        const name = String(instrument || '').trim();
        if (!name) return null;
        state.detail = name;
        state.ticker = null;
        state.detailError = '';
        render();
        const bus = win().OFAPBUS;
        try {
            const payload = (bus && typeof bus.request === 'function')
                ? await bus.request(TICKER_URL, { instrument: name })
                : await getJson(TICKER_URL + '?instrument=' + encodeURIComponent(name));
            if (payload && payload.ok === false) {
                state.detailError = String(payload.error || 'the venue refused it');
            } else {
                state.ticker = payload;
            }
        } catch (err) {
            state.detailError = errText(err);
        }
        render();
        return state.ticker;
    }

    /* ── polling: the shared channel first, this panel's own timer only when there is no bus ────── */

    function startPoll() {
        if (state.polling !== 'idle') return false;
        const symbol = activeSymbol();
        if (!symbol || !currencyFor(symbol)) return false;     /* no feed: nothing to poll for */
        const bus = win().OFAPBUS;
        if (bus && typeof bus.subscribe === 'function') {
            state.unsubscribe = bus.subscribe({ url: CHAIN_URL, params: paramsNow(), intervalMs: INTERVAL_MS }, onChain);
            state.polling = 'bus';
            return true;
        }
        state.polling = 'timer';
        void loadChain();
        state.timer = setInterval(() => { void loadChain(); }, INTERVAL_MS);
        return true;
    }

    function stopPoll() {
        const was = state.polling;
        if (state.unsubscribe) {
            try { state.unsubscribe(); } catch (err) { /* the delivery layer is gone; nothing to release */ }
            state.unsubscribe = null;
        }
        if (state.timer) {
            clearInterval(state.timer);
            state.timer = null;
        }
        state.polling = 'idle';
        return was !== 'idle';
    }

    /* One place decides it: the visible section and the switch, in that order. */
    function sync() {
        if (isActive() && autoRefreshOn()) startPoll();
        else stopPoll();
        return render();
    }

    /* The symbol or the expiry moved: the channel key moved with it, so release and rejoin. */
    function rekey() {
        stopPoll();
        const symbol = activeSymbol();
        /* No feed for this market: state that at once. A panel left reading "loading…" for a symbol
           that will never load is the one lie this view must not tell (found live: switching the
           top bar from BTCUSDT to NAS100USDT never resolved, because nothing polls for it). */
        if (!currencyFor(symbol)) return loadChain();
        const hit = cacheGet(cacheKey(symbol, state.expiry, WIDTH), Date.now());
        if (hit) {
            state.plan = plan(hit, null, symbol, Date.now(), state.expiry);
            state.plan.fromCache = true;
            sync();
            return render();
        }
        /* Otherwise keep what is on screen while the read is in flight — the sub line names the
           symbol and expiry the ladder belongs to, so a stale ladder is never passed off as the new
           one — and blank the panel only when there has never been a read at all. */
        if (!state.plan) loading();
        sync();
        return render();
    }

    /* ── the panel's own controls ─────────────────────────────────────────────────────────────── */

    function setExpiry(code) {
        const wanted = String(code || '').trim();
        if (wanted === state.expiry) return false;
        state.expiry = wanted;
        return rekey();
    }

    function rowClick(ev) {
        const target = ev && ev.target;
        const node = (target && typeof target.closest === 'function') ? target.closest('[data-instrument]') : null;
        if (!node || !node.dataset) return false;
        void loadTicker(node.dataset.instrument);
        return true;
    }

    function bindControls() {
        if (state.bound) return false;
        state.bound = true;
        const body = el('optionsBody');
        if (body && body.addEventListener) body.addEventListener('click', rowClick);
        const select = el('optionsExpiry');
        if (select && select.addEventListener) select.addEventListener('change', () => { setExpiry(select.value); });
        const box = el('optionsAuto');
        if (box && box.addEventListener) box.addEventListener('change', () => { sync(); });
        const button = el('optionsRefresh');
        if (button && button.addEventListener) {
            button.addEventListener('click', () => { void loadChain({ force: true }); });
        }
        const symbolSelect = el('symbolSelect');
        if (symbolSelect && symbolSelect.addEventListener) {
            symbolSelect.addEventListener('change', () => {
                if (!isActive()) return;
                state.expiry = '';                             /* another currency: the nearest expiry */
                state.detail = '';
                state.ticker = null;
                state.detailError = '';
                rekey();
            });
        }
        return true;
    }

    function injectStyles() {
        if (typeof document === 'undefined' || !document || !document.createElement || !document.head) return false;
        if (document.getElementById('optStyleSheet')) return false;
        const style = document.createElement('style');
        style.id = 'optStyleSheet';
        style.textContent = `
            .opt-wrap { overflow: auto; max-height: 54vh; }
            .opt-table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
            .opt-table th, .opt-table td { padding: 2px 7px; text-align: right; white-space: nowrap;
                border-bottom: 1px solid rgba(255,255,255,.05); }
            .opt-table thead th { position: sticky; top: 0; background: var(--bg-panel,#12151a);
                color: var(--text-secondary); font-weight: 600; }
            .opt-table th.opt-label, .opt-table td.opt-strike { text-align: left; font-weight: 600; }
            .opt-table td[data-instrument] { cursor: pointer; }
            .opt-table tr.opt-atm { background: rgba(79,140,255,.12); }
            .opt-none { color: var(--text-muted); font-style: italic; text-align: left; }
            .opt-msg { color: var(--text-secondary); }
            .opt-note { padding: 4px 2px 0; font-size: 11px; }
        `;
        document.head.appendChild(style);
        return true;
    }

    /* ── boot: only while the section is on screen, like every other panel in this suite ────────── */

    async function boot() {
        if (state.booting) return;
        state.booting = true;
        try {
            injectStyles();
            bindControls();
            sync();                                   /* visibility and the switch decide the poll */
            /* The poll's first tick already reads. Only when nothing is polling — the switch is off,
               or the symbol has no feed — does this panel read once itself, and only if what it is
               showing is not what the top bar is on. */
            if (isActive() && state.polling === 'idle'
                && (!state.plan || state.symbol !== activeSymbol())) await loadChain();
            render();
        } finally {
            state.booting = false;
        }
    }

    function watch() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return false;
        const section = document.querySelector(VIEW);
        if (!section) return false;
        state.section = section;
        bindControls();
        if (section.classList && section.classList.contains('active')) void boot();
        if (typeof MutationObserver === 'function') {
            new MutationObserver(() => {
                if (section.classList && section.classList.contains('active')) void boot();
                else { stopPoll(); render(); }
            }).observe(section, { attributes: true, attributeFilter: ['class'] });
        }
        return true;
    }

    if (typeof document !== 'undefined' && document && document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', watch);
    } else {
        watch();
    }

    window.OFAPOPTIONS = {
        VERSION, CHAIN_URL, TICKER_URL, INTERVAL_MS, CACHE_MS, WIDTH, VIEW, DASH,
        OPTION_CURRENCIES, QUOTE_SUFFIXES,
        esc, num, currencyFor, coverageSentence, expiriesFrom, sideOf, ladderFrom, atmIndex,
        fmtStrike, fmtPrice, fmtPct, fmtGreek, fmtDelta, fmtSize, clockOf,
        cacheKey, cacheGet, cachePut, cacheSize, cacheClear,
        plan, subText, headHtml, rowHtml, sideCells, bodyHtml, detailHtml,
        render, syncSelect, state: stateNow, activeSymbol, paramsNow, urlNow,
        onChain, loadChain, loadTicker, getJson, startPoll, stopPoll, sync, rekey, setExpiry,
        rowClick, bindControls, injectStyles, boot, watch,
    };
})();
