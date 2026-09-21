/* option-flow.js — the Option flow panel: sweeps, blocks and unusual premium from the tape.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/options_api.py :: GET /api/options/flow/{symbol}):
 *   ?source=deribit&count=100&window_ms=900000
 *   → { ok, symbol, source, currency, window_ms, window_start_ms, window_end_ms, total_trades,
 *       prints_read, n_sweeps, n_blocks, n_unusual, n_routine, spot, spot_from, premium_unit,
 *       tape[{expiry, strike, side, size, price, timestamp_ms, aggressor, instrument, class, premium}],
 *       tape_shown,
 *       sweeps[{sweep_id, start_ms, end_ms, strikes[], total_size, total_premium, n_trades}],
 *       blocks[{expiry, strike, side, size, price, reason, aggressor, timestamp_ms}],
 *       unusual_premium[…same shape…], note }
 *   A refusal is { ok: false, error } and the banner prints the SERVER'S own sentence.
 *
 * THE TAPE IS THE TABLE: every print in the window, newest first, each carrying the class the
 * engine gave it — a classified event highlighted inside the sequence that produced it reads
 * better than a table with the routine prints deleted, and it is what a flow desk actually looks
 * at. Premium prints in money when the wire named the underlying (premium_unit), and in the
 * contract's own currency when it did not.
 *
 * WHY DERIBIT IS THE ONLY FEED: option flow needs PRINTS, not quotes. Deribit publishes a keyless
 * public option tape (one request, whole currency, newest first) and this build reads it; the
 * equity venues' chains carry quotes, so the server names what would be needed instead of filling
 * a table with sample trades — an invented sweep table would be worse than an empty one.
 *
 * Read-only: one GET per refresh, 20 s cadence while the view is on screen, nothing stored.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="option-flow"]';
    const URL_BASE = '/api/options/flow/';
    const REFRESH_MS = 20000;
    const TICK_MS = 2000;
    const DASH = '—';
    const WINDOW_MS = 900000;      /* 15 minutes: the panel's default slice of the tape */
    const COUNT = 100;             /* prints asked of the venue per refresh */

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    /* ── the decisions (pure: pinned by option-flow.selftest.js under node) ───────────────────── */

    function normalize(symbol) { return String(symbol == null ? '' : symbol).trim().toUpperCase(); }

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }

    function fmtNum(value, digits) {
        const n = num(value);
        if (n === null) return DASH;
        const places = Number(digits);
        if (isFinite(places)) return n.toFixed(places);
        if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(2) + 'K';
        return String(Math.round(n * 100) / 100);
    }

    /* A print's clock time — the table is read as a sequence, so the time leads the row. */
    function timeLabel(ms) {
        const n = num(ms);
        if (n === null || n <= 0) return DASH;
        const date = new Date(n);
        if (!isFinite(date.getTime())) return DASH;
        const pad = (value) => (value < 10 ? '0' : '') + value;
        return pad(date.getHours()) + ':' + pad(date.getMinutes()) + ':' + pad(date.getSeconds());
    }

    function windowLabel(ms) {
        const n = num(ms);
        if (n === null || n <= 0) return DASH;
        const minutes = n / 60000;
        if (minutes < 60) return 'last ' + (Math.round(minutes * 10) / 10) + ' min';
        return 'last ' + (Math.round((minutes / 60) * 10) / 10) + ' h';
    }

    function sourceLabel(source) {
        const text = String(source || '').toLowerCase();
        if (text === 'deribit') return 'Deribit';
        if (text === 'tradier') return 'Tradier';
        if (text === 'marketdata') return 'Market Data';
        if (text === 'finnhub') return 'Finnhub';
        return text || DASH;
    }

    function urlFor(symbol, source) {
        return URL_BASE + encodeURIComponent(normalize(symbol))
            + '?source=' + encodeURIComponent(String(source || 'deribit'))
            + '&count=' + COUNT + '&window_ms=' + WINDOW_MS;
    }

    /* A contract's premium: size × price, in the contract's own currency terms. The venue's own
       numbers, multiplied once — no multiplier is invented for a contract type this build has not
       been told about. */
    function premium(row) {
        const size = num(row && row.size);
        const price = num(row && row.price);
        if (size === null || price === null) return null;
        return size * price;
    }

    /* Premium in money when the wire named the underlying it priced against, and in the contract's
       own currency when it did not. The payload says which (premium_unit) — a dollar figure built
       on a guessed rate is exactly the kind of number that gets a desk into trouble. */
    function premiumText(coin, payload) {
        const value = num(coin);
        if (value === null) return DASH;
        const spot = num(payload && payload.spot);
        if (spot !== null && spot > 0) {
            const money = value * spot;
            if (money >= 1e6) return '$' + (money / 1e6).toFixed(2) + 'M';
            if (money >= 1e3) return '$' + (money / 1e3).toFixed(1) + 'K';
            return '$' + money.toFixed(0);
        }
        const unit = String((payload && payload.premium_unit) || '').toUpperCase();
        return fmtNum(value, value < 10 ? 3 : 1) + (unit ? ' ' + unit : '');
    }

    function signedPremiumText(value, payload) {
        const n = num(value);
        if (n === null) return DASH;
        return (n > 0 ? '+' : (n < 0 ? '−' : '')) + premiumText(Math.abs(n), payload);
    }

    /* The tape as the panel draws it: every print the window holds, newest first, each carrying the
       class the engine gave it. This is the industry reading of a flow feed — the classified events
       highlighted inside the sequence that produced them, not torn out of it. */
    function tapeRows(payload) {
        const rows = (payload && payload.tape) || [];
        return rows.slice().sort((a, b) => (num(b && b.timestamp_ms) || 0) - (num(a && a.timestamp_ms) || 0));
    }

    /* Call and put premium over the tape, and the net between them: the one number a flow desk
       reads first, because it says which side paid more. */
    function premiumSplit(payload) {
        let calls = 0;
        let puts = 0;
        tapeRows(payload).forEach((row) => {
            const value = num(row && row.premium);
            if (value === null) return;
            if (String(row.side) === 'call') calls += value;
            else if (String(row.side) === 'put') puts += value;
        });
        return { call: calls, put: puts, net: calls - puts };
    }

    function largestPrint(payload) {
        let best = null;
        let value = -Infinity;
        tapeRows(payload).forEach((row) => {
            const coin = num(row && row.premium);
            if (coin !== null && coin > value) { value = coin; best = row; }
        });
        return best;
    }

    /* The largest print as one line: contract, size, money. The row exists because "what was the
       biggest thing that traded" is the first question asked of any flow window. */
    function largestText(payload) {
        const row = largestPrint(payload);
        if (!row) return DASH;
        const side = String((row && row.side) || '');
        const mark = side === 'call' ? 'C' : (side === 'put' ? 'P' : '');
        return fmtStrike(row.strike) + mark + ' ×' + fmtNum(row.size)
            + ' · ' + premiumText(row.premium, payload);
    }

    /* A strike is a strike, not a magnitude: 82,000 never reads as "82.00K". Whole strikes print
       whole and grouped; a chain that quotes halves keeps them. */
    function fmtStrike(value) {
        const n = num(value);
        if (n === null) return DASH;
        if (Math.abs(n - Math.round(n)) < 1e-9) {
            return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        }
        return fmtNum(n);
    }

    /* Time, contract, size, price and premium — the order a print is read in. The Type cell carries
       the side's colour, the Class cell the classification, and premium prints in money whenever
       the wire could say what the underlying was worth. */
    function rowHtml(row, payload) {
        const side = String((row && row.side) || '');
        const klass = String((row && row.class) || 'routine');
        const mark = side === 'call' ? 'C' : (side === 'put' ? 'P' : '');
        return '<tr>'
            + '<td>' + esc(timeLabel(row && row.timestamp_ms)) + '</td>'
            + '<td>' + esc(String((row && row.expiry) || '')) + '</td>'
            + '<td class="num">' + esc(fmtStrike(row && row.strike)) + '</td>'
            + '<td' + (mark ? ' class="' + (mark === 'C' ? 'call' : 'put') + '"' : '') + '>'
            + esc(side) + '</td>'
            + '<td class="num">' + esc(fmtNum(row && row.size)) + '</td>'
            + '<td class="num">' + esc(fmtNum(row && row.price, 4)) + '</td>'
            + '<td class="num">' + esc(premiumText(row && row.premium, payload)) + '</td>'
            + '<td>' + esc(String((row && row.aggressor) || DASH)) + '</td>'
            + '<td class="chip ' + esc(klass) + '">' + esc(klass) + '</td></tr>';
    }

    function rowsHtml(payload) {
        const rows = tapeRows(payload);
        if (!rows.length) {
            const read = num(payload && payload.prints_read) || 0;
            return '<tr><td colspan="9" class="dim">'
                + (read ? read + ' prints read, none inside this window'
                        : 'no option prints in this window')
                + '</td></tr>';
        }
        return rows.map((row) => rowHtml(row, payload)).join('');
    }

    /* The biggest sweep (by premium), which is the one the summary line exists to name. */
    function biggestSweep(payload) {
        const rows = (payload && payload.sweeps) || [];
        if (!rows.length) return null;
        return rows.slice().sort((a, b) => (num(b && b.total_premium) || 0) - (num(a && a.total_premium) || 0))[0];
    }

    function subText(payload) {
        const parts = [String((payload && payload.symbol) || '') || DASH,
                       sourceLabel(payload && payload.source),
                       windowLabel(payload && payload.window_ms)];
        const prints = num(payload && payload.prints_read);
        const landed = num(payload && payload.total_trades);
        if (prints !== null) parts.push(prints + ' prints read');
        /* Two counts, two meanings: what the venue handed back and what fell inside the window.
           Printing both is what stops a reader thinking one of them is wrong. */
        if (prints !== null && landed !== null && landed !== prints) parts.push(landed + ' in the window');
        return parts.join(' · ');
    }

    function bannerFor(payload) {
        if (!payload) return { text: '', kind: 'info' };
        if (payload.ok) {
            const sweeping = num(payload.n_sweeps) || 0;
            const blocks = num(payload.n_blocks) || 0;
            const unusual = num(payload.n_unusual) || 0;
            if (!sweeping && !blocks && !unusual) {
                return { text: 'a quiet window: ' + (num(payload.total_trades) || 0)
                    + ' trade(s), none classified as sweeps, blocks or unusual premium', kind: 'info' };
            }
            return { text: sweeping + ' sweep(s) · ' + blocks + ' block(s) · ' + unusual
                + ' unusual-premium print(s) in ' + windowLabel(payload.window_ms), kind: 'ok' };
        }
        return { text: String(payload.error || 'the flow read failed for no stated reason'), kind: 'warn' };
    }

    /* ── the panel ─────────────────────────────────────────────────────────────────────────── */

    const state = { plan: null, busy: false, at: 0, source: 'deribit', symbol: '' };

    function section() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector(VIEW);
    }
    function isActive() {
        const view = section();
        return !!(view && view.classList && view.classList.contains('active'));
    }
    function activeSymbol() {
        const fromState = (typeof S !== 'undefined' && S) ? S.symbol : '';
        const select = el('symbolSelect');
        return normalize(fromState || (select && select.value) || '');
    }
    function chosenSymbol() {
        const box = el('ofSymbol');
        return normalize((box && box.value) || '') || activeSymbol();
    }
    function chosenSource() {
        const select = el('ofFeed');
        const value = String((select && select.value) || state.source || 'deribit').toLowerCase();
        return value || 'deribit';
    }

    function get(path) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path);
        return fetch(path).then((r) => r.json());
    }

    function say(message, kind) {
        const box = el('ofvBanner');
        if (!box) return;
        if (typeof toast === 'function') { toast(box, message, kind || 'info'); return; }
        box.textContent = String(message || '');
    }

    function paint(payload) {
        if (payload) state.plan = payload;
        const current = state.plan || {};
        const banner = bannerFor(current);
        if (banner.text) say(banner.text, banner.kind);
        const sub = el('ofSub');
        if (sub) sub.textContent = current.ok ? subText(current) : (current.error || 'no read yet');
        const windowCell = el('ofWindow');
        if (windowCell) windowCell.textContent = current.ok ? windowLabel(current.window_ms) : DASH;
        const split = premiumSplit(current);
        const fields = {
            ofTotal: current.ok ? fmtNum(current.total_trades, 0) : DASH,
            ofSweeps: current.ok ? fmtNum(current.n_sweeps, 0) : DASH,
            ofBlocks: current.ok ? fmtNum(current.n_blocks, 0) : DASH,
            ofUnusual: current.ok ? fmtNum(current.n_unusual, 0) : DASH,
            ofRoutine: current.ok ? fmtNum(current.n_routine, 0) : DASH,
            /* Which side paid, and how much: the numbers a flow read exists to produce. */
            ofCallPremium: current.ok ? premiumText(split.call, current) : DASH,
            ofPutPremium: current.ok ? premiumText(split.put, current) : DASH,
            ofNetPremium: current.ok ? signedPremiumText(split.net, current) : DASH,
            ofLargest: current.ok ? largestText(current) : DASH,
        };
        Object.keys(fields).forEach((id) => {
            const node = el(id);
            if (node) node.value = fields[id];
        });
        /* The sweep summary row only exists when there is a sweep to describe. */
        const sweepRow = el('ofSweepRows');
        const sweep = current.ok ? biggestSweep(current) : null;
        if (sweepRow) sweepRow.style.display = sweep ? '' : 'none';
        if (sweep) {
            const strikes = (sweep.strikes || []).map((s) => fmtNum(s)).join(' / ');
            const pairs = [['ofSweepId', String(sweep.sweep_id || DASH)],
                           ['ofSweepStrikes', strikes || DASH],
                           ['ofSweepSize', fmtNum(sweep.total_size)],
                           ['ofSweepPremium', premiumText(sweep.total_premium, current)]];
            pairs.forEach((pair) => {
                const node = el(pair[0]);
                if (node) node.value = pair[1];
            });
        }
        const count = el('ofRows');
        const rows = current.ok ? tapeRows(current) : [];
        if (count) {
            count.textContent = current.ok
                ? (rows.length + ' of ' + (num(current.total_trades) || 0) + ' prints · newest first')
                : '0 prints';
        }
        const body = el('ofBody');
        if (body) body.innerHTML = rowsHtml(current.ok ? current : null);
        /* The tape appears with the first print and hides again on an empty window. */
        const table = el('ofTable');
        if (table) table.hidden = !(current.ok && rows.length > 0);
    }

    async function refresh() {
        const symbol = chosenSymbol();
        if (!symbol) { say('pick an instrument first — the flow read needs one', 'info'); return; }
        const source = chosenSource();
        state.source = source;
        state.symbol = symbol;
        state.busy = true;
        if (!state.plan) say('reading the option tape for ' + symbol + '…', 'info');
        try {
            const payload = await get(urlFor(symbol, source));
            state.at = Date.now();
            paint(payload);
        } catch (err) {
            say('the flow request failed: ' + errText(err), 'err');
        } finally {
            state.busy = false;
        }
    }

    function tick() {
        if (!isActive() || (typeof document !== 'undefined' && document.hidden) || win().OFAP_PAUSED) return;
        const intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        if (chosenSymbol() !== state.symbol) { void refresh(); return; }
        if ((Date.now() - state.at) < REFRESH_MS || state.busy) return;
        void refresh();
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        const button = el('ofRefresh');
        if (button) button.addEventListener('click', () => { void refresh(); });
        const source = el('ofFeed');
        if (source) source.addEventListener('change', () => { state.at = 0; void refresh(); });
        const box = el('ofSymbol');
        if (box) box.addEventListener('change', () => { state.at = 0; void refresh(); });
        const symbolSelect = el('symbolSelect');
        if (symbolSelect) symbolSelect.addEventListener('change', () => { if (isActive()) { state.at = 0; void refresh(); } });
        /* The panel's own cadence, handed to the app's pause registry: P (or the topbar chip)
           clears the timer and resume rebuilds it — the suite's rule for every poller. */
        const startPolling = () => {
            const id = setInterval(tick, TICK_MS);
            if (window.OFAPPause && window.OFAPPause.register) window.OFAPPause.register(id, startPolling);
            return id;
        };
        state.timer = startPolling();
    }

    function watch() {
        const view = section();
        if (!view) return false;
        wire();
        if (isActive()) void refresh();
        new MutationObserver(() => { if (isActive()) void refresh(); })
            .observe(view, { attributes: true, attributeFilter: ['class'] });
        return true;
    }

    win().OFAPOPTIONFLOW = {
        VERSION: VERSION, VIEW: VIEW, URL_BASE: URL_BASE, REFRESH_MS: REFRESH_MS, TICK_MS: TICK_MS,
        WINDOW_MS: WINDOW_MS, COUNT: COUNT, DASH: DASH, esc: esc, normalize: normalize, num: num,
        fmtNum: fmtNum, fmtStrike: fmtStrike, timeLabel: timeLabel, windowLabel: windowLabel,
        sourceLabel: sourceLabel,
        urlFor: urlFor, premium: premium, premiumText: premiumText,
        signedPremiumText: signedPremiumText, tapeRows: tapeRows, premiumSplit: premiumSplit,
        largestPrint: largestPrint, largestText: largestText, biggestSweep: biggestSweep,
        rowHtml: rowHtml, rowsHtml: rowsHtml, subText: subText, bannerFor: bannerFor,
        paint: paint, refresh: refresh, tick: tick, wire: wire, watch: watch,
        chosenSymbol: chosenSymbol, chosenSource: chosenSource, activeSymbol: activeSymbol,
        state: () => state.plan,
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
