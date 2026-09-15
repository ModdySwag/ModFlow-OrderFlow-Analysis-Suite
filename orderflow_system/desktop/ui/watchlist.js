/* watchlist.js — the Watchlist panel: one quote line per instrument, from the engine's own status route.
 *
 * WHAT IT IS: a quote board. The instruments come from /api/instruments; the numbers come from the
 * suite's read-only status route (per_symbol rows: price, ticks, candles, cumulative delta, trade
 * phase) — the same route ui.js polls to paint the Overview table. The engine's number wins for a
 * symbol it carries; when it carries nothing for that symbol the row says so instead of inventing a
 * quote. A field no payload has renders as '—', never as 0 and never as a blank cell: on a quote
 * board a blank is a lie about the data.
 *
 * WHY IT POLLS THROUGH THE BUS: a watchlist is the panel people leave open. It joins window.OFAPBUS
 * when that layer is present, so its status poll is the SAME channel every other panel shares — one
 * fetch per interval no matter how many panels look at status — and it leaves the channel the moment
 * the panel is hidden or the auto-refresh switch goes off, because an off-screen board has no
 * business costing anyone bandwidth. With no bus loaded the panel owns exactly one timer of its own
 * (the suite must run without the delivery layer) and clears it on the same two events.
 *
 * WHY /api/control/engine/status: this panel's brief called it `/api/status`; the server does not
 * serve that path — it answers 404 (checked against a running instance). The route below IS the
 * suite's engine status (ui.js and heatmap-pro.js read the same one) and it is READ-ONLY: this module
 * never calls an engine control verb (start/stop/restart), never opens a socket, and stores nothing
 * outside its own memory. The two URLs are literals in one place so scripts/audit_ui_refs.py and
 * test_watchlist.py can both resolve them against the real route table.
 *
 * THE DEMO CASE IS STATED, NOT HIDDEN: with the engine stopped the dashboard answers /api/instruments
 * with its own demo list. Those rows are tagged with the source the server reported and the sub line
 * says the rows are not your feed — demo numbers never pass for quotes here.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const STATUS_URL = '/api/control/engine/status';     /* read-only; see the header */
    const INSTRUMENTS_URL = '/api/instruments';
    const BOOTSTRAP_URL = '/api/control/bootstrap';   /* the configured symbol list, engine or not */
    const INTERVAL_MS = 2000;                            /* the board is a glance, not a tick chart */
    const DASH = '—';                                    /* what an absent field renders as */

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }

    /* ── the numbers ────────────────────────────────────────────────────────────────────────────
       Every formatter answers '—' for a value that is not a finite number, so a missing field can
       never arrive on screen as NaN, an empty cell, or a zero dressed up as a quote. */

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }
    function price(value) {
        const n = num(value);
        /* ui.js formats a price the same way, and a 0 from the engine means "no print yet" */
        if (n === null || n === 0) return DASH;
        return n > 100 ? n.toFixed(2) : n.toFixed(4);
    }
    function compact(value) {
        const n = num(value);
        if (n === null) return DASH;
        const abs = Math.abs(n);
        if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return String(Math.round(n * 100) / 100);
    }
    function signed(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n > 0 ? '+' : '') + compact(n);
    }
    function phase(value) {
        const text = String(value == null ? '' : value).trim();
        return (!text || text === 'none' || text === 'unknown') ? DASH : text;
    }

    /* ── rows: the decision half, pinned by watchlist.selftest.js ───────────────────────────────── */

    function symbolOf(item) {
        return item && item.symbol != null ? String(item.symbol).trim() : '';
    }

    /* The active instrument leads, then the app's own instrument order, then anything the engine is
       streaming that the list did not name — dropping a live row would hide data we already have.
       The active symbol gets a row even when neither payload carries it: the app is on that symbol,
       so the board shows it with '—' rather than silently leaving it out. */
    function orderSymbols(listSymbols, statusSymbols, active) {
        const tail = [];
        listSymbols.forEach((s) => { if (s !== active) tail.push(s); });
        statusSymbols.forEach((s) => { if (s !== active && tail.indexOf(s) < 0) tail.push(s); });
        return (active ? [active] : []).concat(tail);
    }

    function buildRow(symbol, item, statusRow, active) {
        const list = item || null;
        const live = statusRow || null;
        /* one source per row, never mixed: the engine's row if it has one, else the list's own fields */
        const src = live || list || {};
        const ticksValue = src.ticks !== undefined ? src.ticks : src.tick_count;
        const volumeValue = src.volume_24h !== undefined ? src.volume_24h : src.volume;
        const source = live ? 'engine'
            : (list && list.data_source ? String(list.data_source) : (list ? 'list' : 'none'));
        const candles = live && num(live.candles) !== null ? live.candles : (list ? list.candle_count : null);
        const where = live ? 'the engine status route'
            : (list ? 'the instrument list itself' + (list.data_source ? ' (' + String(list.data_source) + ')' : '')
                : 'neither the engine status route nor the instrument list');
        return {
            symbol: symbol,
            active: !!active,
            source: source,
            cells: {
                price: price(src.price),
                ticks: compact(ticksValue),
                volume: compact(volumeValue),
                delta: live ? signed(live.cum_delta) : DASH,
                phase: phase(src.trade_phase),
            },
            title: 'Switch the app to ' + symbol + ' — numbers from ' + where,
        };
    }

    /* What the user configured, independent of the engine. Read defensively: the config block has moved
       before, and a missing list must never turn into an error on screen — just no rows. */
    async function configuredSymbols() {
        try {
            const data = await api(BOOTSTRAP_URL);
            const cfg = (data && (data.config || data)) || {};
            /* Measured: config.instruments is the instrument LIST itself (49 objects under numeric keys),
               not a settings block holding a `symbols` key — so read the list first and fall back to the
               other shapes, because this block has moved before and a miss must mean "no rows", not an error. */
            let list = cfg.instruments;
            if (list && !Array.isArray(list) && typeof list === 'object') {
                list = list.symbols || list.list || list.items || list.matrix || null;
            }
            if (!Array.isArray(list)) list = cfg.symbols || [];
            if (typeof list === 'string') list = list.split(/[,\s]+/);
            if (!Array.isArray(list)) return [];
            return list.map((item) => {
                if (item && typeof item === 'object') {
                    return String(item.symbol || item.name || item.ticker || '').trim().toUpperCase();
                }
                return String(item || '').trim().toUpperCase();
            }).filter(Boolean).slice(0, 60);
        } catch (e) { return []; }
    }

    /* With the engine stopped the server answers /api/instruments with its own demo list. The demo rows
       stay (they are tagged), but the user's own instruments are shown alongside as placeholders so the
       board still answers "what am I watching" — every number is '—', because there is no feed. */
    async function refreshPlaceholders() {
        const running = !!(state.status && String(state.status.state) === 'running');
        if (running || !demoNote()) { state.placeholders = []; return; }
        const symbols = await configuredSymbols();
        const have = new Set((state.instruments || []).map((i) => String((i && i.symbol) || '').toUpperCase()));
        state.placeholders = symbols.filter((s) => !have.has(s)).map((s) => ({ symbol: s, data_source: 'configured' }));
    }

    function buildRows(instruments, status, active) {
        const list = Array.isArray(instruments) ? instruments : [];
        const bySymbol = {};
        const listOrder = [];
        list.forEach((item) => {
            const s = symbolOf(item);
            if (!s || s in bySymbol) return;
            bySymbol[s] = item;
            listOrder.push(s);
        });
        const liveBySymbol = {};
        const liveOrder = [];
        ((status && status.per_symbol) || []).forEach((row) => {
            const s = symbolOf(row);
            if (!s || s in liveBySymbol) return;
            liveBySymbol[s] = row;
            liveOrder.push(s);
        });
        const activeSymbol = active == null ? '' : String(active);
        return orderSymbols(listOrder, liveOrder, activeSymbol).map((symbol) =>
            buildRow(symbol, bySymbol[symbol] || null, liveBySymbol[symbol] || null, symbol === activeSymbol));
    }

    /* ── the states: loading / empty / note / row, never a blank panel ─────────────────────────── */

    function loadingHtml() { return '<div class="dim">Loading…</div>'; }
    function emptyHtml() {
        return '<div class="dim">Nothing to watch — enable an instrument under Instruments and it appears here.</div>';
    }
    function noteRow(kind, text) {
        const tag = kind === 'err' ? '<span class="tag no">error</span>' : '<span class="tag warn">warn</span>';
        return '<div class="log-line">' + tag + '<span class="wl-msg">' + esc(text) + '</span></div>';
    }
    function errorHtml(message) { return noteRow('err', message); }

    function rowHtml(row) {
        const badge = row.active ? '<span class="tag ok">active</span>' : '';
        return '<div class="log-line wl-row' + (row.active ? ' on' : '') + '" data-symbol="' + esc(row.symbol)
            + '" title="' + esc(row.title) + '">'
            + '<span class="wl-sym">' + esc(row.symbol) + '</span>'
            + '<span class="wl-price">' + esc(row.cells.price) + '</span>'
            + '<span class="wl-cell">ticks ' + esc(row.cells.ticks) + '</span>'
            + '<span class="wl-cell">vol ' + esc(row.cells.volume) + '</span>'
            + '<span class="wl-cell">Δ ' + esc(row.cells.delta) + '</span>'
            + '<span class="wl-cell dim">' + esc(row.cells.phase) + '</span>'
            + badge + '<span class="wl-tag">' + esc(row.source) + '</span></div>';
    }

    function bodyHtml(rows) {
        const notes = [];
        if (state.instrumentError) {
            notes.push(errorHtml('could not read ' + INSTRUMENTS_URL + ' — ' + state.instrumentError));
        }
        if (state.statusError && state.instruments) {
            notes.push(noteRow('warn', 'engine status unavailable (' + state.statusError
                + ') — these rows carry only what the instrument list itself reports'));
        }
        if (!state.instruments && !state.instrumentError) return loadingHtml();
        if (!rows.length) {
            if (!notes.length) notes.push(emptyHtml());
            return notes.join('');
        }
        return notes.join('') + rows.map(rowHtml).join('');
    }

    function demoNote() {
        return (state.instruments || []).some((item) => item && String(item.data_source) === 'demo');
    }

    function subText(rows) {
        const parts = [];
        const section = sectionEl();
        const onScreen = !!(section && section.classList && section.classList.contains('active'));
        if (!onScreen) parts.push('paused — this panel is not on screen');
        else if (!autoRefreshOn()) parts.push('auto-refresh off — press Refresh for a one-off update');
        else if (state.polling === 'bus') parts.push('polling ' + (INTERVAL_MS / 1000) + 's via the shared bus');
        else if (state.polling === 'timer') parts.push("polling " + (INTERVAL_MS / 1000) + "s from this panel's own timer (no bus)");
        else parts.push('auto-refresh on');
        const st = state.status;
        if (st && typeof st === 'object') {
            if (st.running) parts.push('engine running' + ((st.symbols || []).length ? ' · ' + (st.symbols || []).length + ' instrument(s)' : ''));
            else parts.push('engine ' + (st.state || 'stopped') + ' — no live rows');
        }
        if (state.statusError) parts.push('status unavailable: ' + state.statusError);
        if (demoNote()) parts.push('the server is answering with its demo list, not your feed');
        if ((state.placeholders || []).length) {
            parts.push(state.placeholders.length + ' configured instrument(s) with no feed — those rows show —');
        }
        parts.push(rows.length + ' row(s)');
        parts.push(state.statusAt ? 'updated ' + new Date(state.statusAt).toLocaleTimeString() : 'never updated');
        return parts.join(' · ');
    }

    /* ── state ─────────────────────────────────────────────────────────────────────────────────── */

    const state = {
        instruments: null,      /* last /api/instruments payload, null until one arrives */
        placeholders: [],       /* configured symbols shown as — rows when the server is demoing */
        status: null,           /* last status payload */
        instrumentError: '',
        statusError: '',
        statusAt: 0,
        polling: 'idle',        /* 'idle' | 'bus' | 'timer' */
        unsubscribe: null,      /* the way out of the shared channel, while we hold it */
        timer: null,            /* our own timer, only when there is no bus */
        section: null,
        bound: false,
        booting: false,
    };

    function sectionEl() {
        if (state.section) return state.section;
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector('.view[data-view="watchlist"]');
    }
    function activeSymbol() {
        const sel = el('symbolSelect');
        return sel && sel.value ? String(sel.value) : '';
    }
    function autoRefreshOn() {
        const box = el('watchlistAuto');
        return box ? !!box.checked : true;                    /* no switch on the page: keep watching */
    }
    /* The user's configured instruments, as rows with no numbers, for the engine-stopped case: the board
       still answers "what am I watching" while the demo rows answer "what could the feed look like". */
    function placeholderRows() {
        return (state.placeholders || []).map((item) => ({
            symbol: item.symbol,
            active: false,
            title: item.symbol + ' — configured instrument, no feed while the engine is stopped',
            cells: { price: DASH, ticks: DASH, volume: DASH, delta: DASH, phase: DASH },
            source: 'configured',
        }));
    }

    function rowsNow() {
        const rows = state.instruments ? buildRows(state.instruments, state.status, activeSymbol()) : [];
        return rows.concat(placeholderRows());
    }
    function stateNow() {
        return {
            version: VERSION,
            loaded: !!state.instruments,                 /* has the instrument list been read at all */
            instruments: state.instruments ? state.instruments.length : 0,
            engine: state.status ? (state.status.state || 'unknown') : 'unknown',
            rows: rowsNow().length,
            polling: state.polling,
            auto: autoRefreshOn(),
            instrumentError: state.instrumentError,
            statusError: state.statusError,
            statusAt: state.statusAt,
        };
    }

    function render() {
        const rows = rowsNow();
        const host = el('watchlistBody');
        if (host) host.innerHTML = bodyHtml(rows);
        const count = el('watchlistCount');
        if (count) count.textContent = String(rows.length);
        const sub = el('watchlistSub');
        if (sub) sub.textContent = subText(rows);
        return rows;
    }

    /* ── reading ───────────────────────────────────────────────────────────────────────────────── */

    function getJson(url) {
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

    function getStatus() {
        const bus = win().OFAPBUS;
        /* the bus coalesces a one-shot with anyone asking the same thing in the same moment */
        if (bus && typeof bus.request === 'function') return bus.request(STATUS_URL);
        return getJson(STATUS_URL);
    }

    function onStatus(payload) {
        state.statusAt = Date.now();
        if (payload && payload.error) {
            state.statusError = String(payload.error);
        } else if (payload && typeof payload === 'object') {
            state.status = payload;
            state.statusError = '';
        } else {
            state.statusError = 'empty status payload';
        }
        render();
        return payload;
    }

    async function loadStatus() {
        let payload = null;
        try {
            payload = await getStatus();
        } catch (err) {
            payload = { error: errText(err) };
        }
        return onStatus(payload);
    }

    async function loadInstruments() {
        try {
            const list = await getJson(INSTRUMENTS_URL);
            if (!Array.isArray(list)) throw new Error('the instrument list was not a list');
            state.instruments = list;
            state.instrumentError = '';
        } catch (err) {
            /* keep the last good list on screen and say what failed above it */
            state.instrumentError = errText(err);
        }
        render();
        return state.instruments;
    }

    async function refresh() {
        await Promise.all([loadInstruments(), loadStatus()]);
        await refreshPlaceholders();
        return render();
    }

    /* ── polling: the shared channel first, our own timer only when there is no bus ─────────────── */

    function startPoll() {
        if (state.polling !== 'idle') return false;
        const bus = win().OFAPBUS;
        if (bus && typeof bus.subscribe === 'function') {
            state.unsubscribe = bus.subscribe({ url: STATUS_URL, intervalMs: INTERVAL_MS }, onStatus);
            state.polling = 'bus';
            return true;
        }
        state.polling = 'timer';
        void loadStatus();
        /* the 2 s beat reloads the engine status; the configured-instrument rows depend on it
           (they only exist while the engine is stopped), so they are refreshed on the same beat */
        state.timer = setInterval(() => {
            void loadStatus().then(() => refreshPlaceholders()).then(() => render());
        }, INTERVAL_MS);
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

    function sync() {
        const section = sectionEl();
        const onScreen = !!(section && section.classList && section.classList.contains('active'));
        if (onScreen && autoRefreshOn()) startPoll();
        else stopPoll();
        return render();
    }

    /* ── the panel's own controls ──────────────────────────────────────────────────────────────── */

    function activate(symbol) {
        const sel = el('symbolSelect');
        if (!sel || !symbol) return false;
        const options = sel.options ? Array.prototype.slice.call(sel.options) : [];
        const offered = options.some((opt) => opt && String(opt.value) === String(symbol));
        if (!offered) return false;              /* never force it: the app's own list is the authority */
        if (sel.value === symbol) return true;   /* already the app's instrument — nothing to dispatch */
        sel.value = symbol;
        sel.dispatchEvent(new Event('change'));  /* the app's own handler does the switching */
        return true;
    }

    function rowClick(ev) {
        const target = ev && ev.target;
        const node = target && typeof target.closest === 'function' ? target.closest('[data-symbol]') : null;
        if (!node || !node.dataset) return false;
        const changed = activate(node.dataset.symbol);
        if (changed) render();                   /* the row that is now active belongs at the top */
        return changed;
    }

    function bindControls() {
        if (state.bound) return false;
        state.bound = true;
        const host = el('watchlistBody');
        if (host && host.addEventListener) host.addEventListener('click', rowClick);
        const box = el('watchlistAuto');
        if (box && box.addEventListener) box.addEventListener('change', () => { sync(); });
        const button = el('watchlistRefresh');
        if (button && button.addEventListener) button.addEventListener('click', () => { void refresh(); });
        return true;
    }

    function injectStyles() {
        if (typeof document === 'undefined' || !document || !document.createElement || !document.head) return false;
        if (document.getElementById('wlStyleSheet')) return false;
        const st = document.createElement('style');
        st.id = 'wlStyleSheet';
        st.textContent = `
            .wl-row { align-items: baseline; cursor: pointer; }
            .wl-row.on { background: rgba(79,140,255,.12); }
            .wl-sym { flex: 0 0 118px; font-weight: 600; }
            .wl-price { flex: 0 0 92px; }
            .wl-cell { flex: 0 0 108px; color: var(--text-secondary); }
            .wl-msg { color: var(--text-secondary); }
            .wl-tag { margin-left: auto; color: var(--text-muted); }
        `;
        document.head.appendChild(st);
        return true;
    }

    /* ── boot: only while the section is on screen, like every other panel in this suite ────────── */

    async function boot() {
        if (state.booting) return;                  /* one activation, one read of the list */
        state.booting = true;
        try {
            injectStyles();
            bindControls();
            sync();                                 /* visibility + the switch decide the poll */
            await loadInstruments();                /* fresh per activation: an engine started in
                                                       Overview must show up as soon as this opens */
            render();
        } finally {
            state.booting = false;
        }
    }

    function watch() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return false;
        const section = document.querySelector('.view[data-view="watchlist"]');
        if (!section) return false;
        state.section = section;
        bindControls();
        if (section.classList && section.classList.contains('active')) void boot();
        if (typeof MutationObserver === 'function') {
            new MutationObserver(() => {
                if (section.classList && section.classList.contains('active')) void boot();
                else { stopPoll(); render(); }      /* hidden: leave the shared channel to the others */
            }).observe(section, { attributes: true, attributeFilter: ['class'] });
        }
        return true;
    }

    if (typeof document !== 'undefined' && document && document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', watch);
    } else {
        watch();
    }

    window.OFAPWATCHLIST = {
        VERSION, STATUS_URL, INSTRUMENTS_URL, INTERVAL_MS, DASH,
        esc, num, price, compact, signed, phase,
        orderSymbols, buildRow, buildRows, rowHtml,
        loadingHtml, emptyHtml, errorHtml, noteRow, bodyHtml, subText,
        render, rows: rowsNow, state: stateNow,
        getJson, getStatus, onStatus, loadStatus, loadInstruments, refresh,
        startPoll, stopPoll, sync, activate, rowClick, bindControls, injectStyles,
        boot, watch,
    };
})();
