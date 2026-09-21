/* volatility.js — the Volatility panel: the IV smile, the 25Δ wings and the term structure.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/options_api.py :: GET /api/options/volatility/{symbol}):
 *   ?source=deribit|tradier|marketdata[&spot=][&width=]
 *   → { ok, symbol, source, expiry, spot, spot_from, n_strikes, n_expiries, rows_shown, rows_total,
 *       atm_iv, skew_25d, put_25d_iv, call_25d_iv, iv_unit, call_oi, put_oi, total_oi, put_call_oi,
 *       iv_min, iv_max, dte,
 *       smile[{strike, side, iv, delta, oi, expiry_ms}], term_structure[{expiry_ms, atm_iv, skew_25d}], note }
 *   A refusal is { ok: false, error } and the banner prints the SERVER'S own sentence.
 *
 * EVERY SOURCE HERE CARRIES IV, which is why this panel answers for all three: Deribit's chain
 * (one expiry per read), and the Tradier / Market Data OPRA chains (many expiries at once — those
 * are the ones that give the term structure something to draw). The 25Δ wings are shown beside
 * the skew, because a spread alone cannot say which wing moved.
 *
 * Read-only: one GET per refresh, 20 s cadence while the view is on screen, nothing stored.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="volatility"]';
    const URL_BASE = '/api/options/volatility/';
    const REFRESH_MS = 20000;
    const TICK_MS = 2000;
    const DASH = '—';
    const SOURCES = ['deribit', 'tradier', 'marketdata'];

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    /* ── the decisions (pure: pinned by volatility.selftest.js under node) ────────────────────── */

    function normalize(symbol) { return String(symbol == null ? '' : symbol).trim().toUpperCase(); }

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }

    function fmtPrice(value, digits) {
        const n = num(value);
        if (n === null) return DASH;
        const places = Number(digits);
        return n.toFixed(isFinite(places) ? places : (Math.abs(n) >= 100 ? 2 : 6));
    }

    /* IV arrives as a FRACTION — the engines' unit, stated on the wire under `iv_unit` — and is
       printed as a percentage. One rule, no magnitude guessing: the old "below 1.5 means a
       decimal" heuristic assumed no real IV is under 1.5%, which is simply not true of a quiet
       market, and it silently printed a real 1.2% IV as 120%. */
    function fmtIv(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n * 100).toFixed(2) + '%';
    }

    /* Counts (open interest, contract counts) read as counts: whole contracts, grouped in threes.
       An OI column that says "1234.57" makes the reader check whether it is looking at a count or a
       price; the wire's OI is a whole number, so the cell is one. */
    function fmtOi(value) {
        const n = num(value);
        if (n === null) return DASH;
        const whole = Math.round(n);
        return String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    /* A signed figure in percentage points: the skew is a difference of two IVs (fractions), so
       it is scaled by 100 once, here — the sign is the whole message (put skew vs call skew). */
    function fmtSkew(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n >= 0 ? '+' : '') + (n * 100).toFixed(2) + 'pp';
    }

    function sourceLabel(source) {
        const text = String(source || '').toLowerCase();
        if (text === 'deribit') return 'Deribit';
        if (text === 'tradier') return 'Tradier';
        if (text === 'marketdata') return 'Market Data';
        return text || DASH;
    }

    function urlFor(symbol, source) {
        return URL_BASE + encodeURIComponent(normalize(symbol)) + '?source='
            + encodeURIComponent(String(source || 'deribit'));
    }

    /* An epoch-ms expiry as a date; an unknown expiry says so rather than printing "Invalid Date". */
    function expiryLabel(ms) {
        const n = num(ms);
        /* Two guards, not one: `getTime()` is finite for an out-of-range stamp too, and
           `toISOString()` then THROWS a RangeError — which would abort the caller's paint loop
           mid-way and leave the fields after it blank rather than showing a label. */
        if (n === null || !(n > 0) || n > 8.64e15) return 'single expiry';
        const date = new Date(n);
        if (!isFinite(date.getTime())) return 'single expiry';
        try {
            return date.toISOString().slice(0, 10);
        } catch (err) {
            return 'single expiry';
        }
    }

    /* Deribit's own contract form (20SEP26, the label the venue's instruments carry) — the shape an
       options desk reads; the ISO date stays in the cell's title for anything that wants it. */
    function expiryShort(ms) {
        const n = num(ms);
        if (n === null || !(n > 0) || n > 8.64e15) return '';
        const date = new Date(n);
        if (!isFinite(date.getTime())) return '';
        const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        return String(date.getUTCDate()).padStart(2, '0') + months[date.getUTCMonth()]
            + String(date.getUTCFullYear()).slice(2);
    }

    /* The term structure line: the front three expiries, ATM IV and skew each — the shape the
       table cannot show in one glance. */
    function termText(payload) {
        const rows = (payload && payload.term_structure) || [];
        if (!rows.length) {
            const atm = fmtIv(payload && payload.atm_iv);
            return atm === DASH ? DASH : ('single expiry · ATM ' + atm);
        }
        return rows.slice(0, 3).map((row) => (
            /* The same contract form the table uses — one label for one expiry on the whole panel. */
            (expiryShort(row && row.expiry_ms) || expiryLabel(row && row.expiry_ms)) + ' '
            + fmtIv(row && row.atm_iv)
            + (num(row && row.skew_25d) === null ? '' : ' (' + fmtSkew(row.skew_25d) + ')')
        )).join(' · ') + (rows.length > 3 ? ' · +' + (rows.length - 3) + ' more' : '');
    }

    function subText(payload) {
        const parts = [String((payload && payload.symbol) || '') || DASH, sourceLabel(payload && payload.source)];
        const spot = fmtPrice(payload && payload.spot);
        /* textContent carries the sub-line, so no esc() here — an escaped entity would print. */
        if (spot !== DASH) parts.push('spot ' + spot + (payload.spot_from ? ' (' + String(payload.spot_from) + ')' : ''));
        const expiries = num(payload && payload.n_expiries);
        parts.push(expiries === 1 ? 'single expiry'
            : (expiries && expiries > 1 ? expiries + ' expiries' : 'no expiries read'));
        return parts.join(' · ');
    }

    /* One smile row. The option market's own reading rules, not decoration: the Type cell carries
       the side's colour, the row the chain says is in the money is shaded, and the strike nearest
       spot is marked — a chain where the reader has to compare 36 strikes against spot in their
       head is a chain that has not been finished. */
    function rowHtml(row, ctx) {
        const side = String((row && row.side) || '');
        const strike = num(row && row.strike);
        const spot = num(ctx && ctx.spot);
        const atm = num(ctx && ctx.atm);
        const flags = [];
        if (strike !== null && atm !== null && strike === atm) flags.push('atm');
        if (strike !== null && spot !== null && spot > 0) {
            const itm = (side === 'call' && strike < spot) || (side === 'put' && strike > spot);
            if (itm) flags.push('itm');
        }
        return '<tr' + (flags.length ? ' class="' + flags.join(' ') + '"' : '') + '>'
            + '<td title="' + esc(expiryLabel(row && row.expiry_ms)) + '">'
            + esc(expiryShort(row && row.expiry_ms) || expiryLabel(row && row.expiry_ms)) + '</td>'
            + '<td class="num">' + esc(fmtPrice(row && row.strike)) + '</td>'
            + '<td' + (side === 'call' || side === 'put' ? ' class="' + side + '"' : '') + '>'
            + esc(side) + '</td>'
            + '<td class="num">' + esc(fmtIv(row && row.iv)) + '</td>'
            + '<td class="num">' + esc(fmtPrice(row && row.delta, 4)) + '</td>'
            + '<td class="num">' + esc(fmtOi(row && row.oi)) + '</td></tr>';
    }

    /* By strike, ascending: a smile is read left to right, and the same strike's call and put sit
       beside each other. The strike nearest spot is the one row the panel marks — scanned over the
       sorted rows, so a chain whose two nearest strikes are equidistant always marks the lower. */
    function rowsHtml(payload) {
        const rows = (payload && payload.smile) || [];
        if (!rows.length) return '<tr><td colspan="6" class="dim">no strikes in this chain</td></tr>';
        const spot = num(payload && payload.spot);
        const sorted = rows.slice()
            .sort((a, b) => (num(a && a.strike) || 0) - (num(b && b.strike) || 0));
        let atm = null;
        let best = Infinity;
        sorted.forEach((r) => {
            const strike = num(r && r.strike);
            if (strike === null || spot === null) return;
            const gap = Math.abs(strike - spot);
            if (gap < best) { best = gap; atm = strike; }
        });
        const ctx = { spot: spot, atm: atm };
        return sorted.map((r) => rowHtml(r, ctx)).join('');
    }

    /* The IV range across the whole chain: where the cheapest and the dearest strike sit, in the
       same percent form as every other IV on the panel. */
    function ivRangeText(payload) {
        const lo = num(payload && payload.iv_min);
        const hi = num(payload && payload.iv_max);
        if (lo === null || hi === null) return DASH;
        return fmtIv(lo) + ' – ' + fmtIv(hi);
    }

    /* Days left on the expiry the surface was read from — the number every option position's risk
       is scaled by, stated plainly instead of left to be worked out from the date. */
    function dteText(payload) {
        const dte = num(payload && payload.dte);
        if (dte === null) return DASH;
        if (dte < 1) return (dte * 24).toFixed(1) + ' h';
        return dte.toFixed(dte < 10 ? 1 : 0) + ' d';
    }

    function bannerFor(payload) {
        if (!payload) return { text: '', kind: 'info' };
        if (payload.ok) {
            const wings = (num(payload.put_25d_iv) === null || num(payload.call_25d_iv) === null)
                ? '25Δ wings not resolvable in this chain'
                : '25Δ put ' + fmtIv(payload.put_25d_iv) + ' vs call ' + fmtIv(payload.call_25d_iv);
            return { text: wings + (payload.note ? ' · ' + payload.note : ''), kind: 'ok' };
        }
        return { text: String(payload.error || 'the volatility read failed for no stated reason'), kind: 'warn' };
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
        const box = el('volSymbol');
        return normalize((box && box.value) || '') || activeSymbol();
    }
    function chosenSource() {
        const select = el('volSource');
        const value = String((select && select.value) || state.source || 'deribit').toLowerCase();
        return SOURCES.indexOf(value) >= 0 ? value : 'deribit';
    }

    function get(path) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path);
        return fetch(path).then((r) => r.json());
    }

    function say(message, kind) {
        const box = el('volBanner');
        if (!box) return;
        if (typeof toast === 'function') { toast(box, message, kind || 'info'); return; }
        box.textContent = String(message || '');
    }

    function paint(payload) {
        if (payload) state.plan = payload;
        const current = state.plan || {};
        const banner = bannerFor(current);
        if (banner.text) say(banner.text, banner.kind);
        const sub = el('volSub');
        if (sub) sub.textContent = current.ok ? subText(current) : (current.error || 'no read yet');
        const spot = el('volSpot');
        if (spot) spot.textContent = current.ok ? ('spot ' + fmtPrice(current.spot)) : DASH;
        const fields = {
            volAtmIv: current.ok ? fmtIv(current.atm_iv) : DASH,
            volSkew25dPut: current.ok ? fmtIv(current.put_25d_iv) : DASH,
            volSkew25dCall: current.ok ? fmtIv(current.call_25d_iv) : DASH,
            volSkew25d: current.ok ? fmtSkew(current.skew_25d) : DASH,
            /* The chain's own desk numbers: how much open interest sits on each side (the classic
               put/call ratio), where the whole surface's IV range sits, and the time left. */
            volPcoi: current.ok ? fmtPrice(current.put_call_oi, 3) : DASH,
            volTotalOi: current.ok ? fmtOi(current.total_oi) : DASH,
            volIvRange: current.ok ? ivRangeText(current) : DASH,
            volDte: current.ok ? dteText(current) : DASH,
            volTerm: current.ok ? termText(current) : DASH,
        };
        Object.keys(fields).forEach((id) => {
            const node = el(id);
            if (node) node.value = fields[id];
        });
        const count = el('volSmileRows');
        if (count) {
            count.textContent = current.ok
                ? (num(current.rows_total || current.n_strikes) || 0) + ' strike(s) · by strike'
                : '0 strikes';
        }
        const body = el('volBody');
        if (body) body.innerHTML = rowsHtml(current.ok ? current : null);
        /* No chain, no table: the empty state is the banner's sentence, not a header over nothing. */
        const table = el('volTable');
        if (table) table.hidden = !(current.ok && ((current.smile || []).length > 0));
    }

    async function refresh() {
        const symbol = chosenSymbol();
        if (!symbol) { say('pick an instrument first — the surface needs one', 'info'); return; }
        const source = chosenSource();
        state.source = source;
        state.symbol = symbol;
        state.busy = true;
        if (!state.plan) say('reading ' + symbol + ' from ' + sourceLabel(source) + '…', 'info');
        try {
            const payload = await get(urlFor(symbol, source));
            state.at = Date.now();
            paint(payload);
        } catch (err) {
            say('the volatility request failed: ' + errText(err), 'err');
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
        const button = el('volRefresh');
        if (button) button.addEventListener('click', () => { void refresh(); });
        const source = el('volSource');
        if (source) source.addEventListener('change', () => { state.at = 0; void refresh(); });
        const box = el('volSymbol');
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

    win().OFAPVOLATILITY = {
        VERSION: VERSION, VIEW: VIEW, URL_BASE: URL_BASE, REFRESH_MS: REFRESH_MS, TICK_MS: TICK_MS,
        DASH: DASH, SOURCES: SOURCES, esc: esc, normalize: normalize, num: num,
        fmtPrice: fmtPrice, fmtIv: fmtIv, fmtOi: fmtOi, fmtSkew: fmtSkew, sourceLabel: sourceLabel,
        urlFor: urlFor, expiryLabel: expiryLabel, expiryShort: expiryShort, termText: termText,
        subText: subText, ivRangeText: ivRangeText, dteText: dteText,
        rowHtml: rowHtml, rowsHtml: rowsHtml, bannerFor: bannerFor,
        paint: paint, refresh: refresh, tick: tick, wire: wire, watch: watch,
        chosenSymbol: chosenSymbol, chosenSource: chosenSource, activeSymbol: activeSymbol,
        state: () => state.plan,
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
