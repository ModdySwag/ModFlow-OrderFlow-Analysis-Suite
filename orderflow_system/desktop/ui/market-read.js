/* market-read.js — the Market read panel: regime, conviction, the score breakdown, key levels.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/api.py :: GET /api/atlas/market-read/{symbol}):
 *   → { ok, symbol, spot, at, regime{name, description, buyer_led, seller_led, absorbing,
 *       absorbing_side}, conviction, scores{trend, imbalance, absorption, liquidity, levels,
 *       profile, vwap}, levels[{price, kind, source, strength, notes}], n_levels,
 *       confluence[{price, signals[], strength}], n_confluence, summary,
 *       inputs{tape, profile, radar, heatmap, vwap, footprint{measured, note}}, note }
 *   A refusal is { ok: false, error } and the banner prints the SERVER'S own sentence.
 *
 * IT READS THE ENGINE, NOT A VENUE: every input is the running engine's own analyzer state through
 * the atlas hub (tape stats, session profile, the radar book, the depth map's walls, the VWAP
 * study). With no engine running there is no read at all and the server says so — this panel never
 * shows a fabricated regime. The `inputs` block is printed as well, because the read reports which
 * signals were actually measured: the footprint family is not wired to the hub yet, and a
 * conviction score computed without it should say so on its own face.
 *
 * Read-only: one GET per refresh, 5 s cadence while the view is on screen (it is a local read of
 * state already in memory), nothing stored.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="market-read"]';
    const URL_BASE = '/api/atlas/market-read/';
    const REFRESH_MS = 5000;
    const TICK_MS = 2000;
    const DASH = '—';

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    /* ── the decisions (pure: pinned by market-read.selftest.js under node) ───────────────────── */

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

    /* A per-signal score is 0..100 on the engine's own scale. */
    function fmtScore(value) {
        const n = num(value);
        if (n === null) return DASH;
        return n.toFixed(1);
    }

    function yesNo(flag) { return flag ? 'yes' : 'no'; }

    /* "mode" | "indifferent" — a regime the engine can name is shown verbatim, never prettified. */
    function regimeText(payload) {
        const regime = (payload && payload.regime) || {};
        const name = String(regime.name || '');
        if (!name) return DASH;
        return name.replace(/_/g, ' ') + (regime.absorbing && regime.absorbing_side
            ? ' (' + regime.absorbing_side + ' side)' : '');
    }

    function urlFor(symbol) { return URL_BASE + encodeURIComponent(normalize(symbol)); }

    function scoreRow(scores, key) {
        const row = (scores || {})[key];
        return fmtScore(row);
    }

    function rowHtml(level) {
        return '<tr><td>' + esc(fmtPrice(level && level.price)) + '</td>'
            + '<td>' + esc(String((level && level.kind) || '').replace(/_/g, ' ')) + '</td>'
            + '<td>' + esc(String((level && level.source) || '')) + '</td>'
            + '<td>' + esc(fmtScore(level && (level.strength * 100))) + '</td></tr>';
    }

    /* Strongest first: the read already ranks them, and a 40-row list is read top-down. */
    function rowsHtml(payload) {
        const rows = (payload && payload.levels) || [];
        if (!rows.length) return '<tr><td colspan="4" class="dim">no levels in this state</td></tr>';
        return rows.map(rowHtml).join('');
    }

    function levelCount(payload) {
        const levels = num(payload && payload.n_levels);
        const confluence = num(payload && payload.n_confluence);
        if (levels === null) return '0 levels';
        return levels + ' level(s)' + (confluence ? ' · ' + confluence + ' confluence' : '');
    }

    /* Which signals the read could actually measure. Printed with the read because a conviction
       score is only as good as its inputs, and this is the honest half of that sentence. */
    function inputsText(payload) {
        const inputs = (payload && payload.inputs) || {};
        const missing = Object.keys(inputs).filter((key) => (
            inputs[key] && typeof inputs[key] === 'object' && inputs[key].measured === false));
        if (!missing.length) return 'every signal measured';
        return 'not measured: ' + missing.join(', ');
    }

    function summaryText(payload) {
        const parts = [];
        const summary = String((payload && payload.summary) || '').trim();
        if (summary) parts.push(summary);
        const note = String((payload && payload.note) || '').trim();
        if (note) parts.push(note);
        return parts.join(' ') || DASH;
    }

    function bannerFor(payload) {
        if (!payload) return { text: '', kind: 'info' };
        if (payload.ok) {
            const description = String(((payload.regime || {}).description) || '');
            const inputs = inputsText(payload);
            return { text: (description || 'read complete') + ' · ' + inputs,
                     kind: (payload.inputs && payload.inputs.footprint
                            && payload.inputs.footprint.measured === false) ? 'info' : 'ok' };
        }
        return { text: String(payload.error || 'the read failed for no stated reason'), kind: 'warn' };
    }

    /* ── the panel ─────────────────────────────────────────────────────────────────────────── */

    const state = { plan: null, busy: false, at: 0, symbol: '' };

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

    function get(path) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path);
        return fetch(path).then((r) => r.json());
    }

    function say(message, kind) {
        const box = el('mrBanner');
        if (!box) return;
        if (typeof toast === 'function') { toast(box, message, kind || 'info'); return; }
        box.textContent = String(message || '');
    }

    function paint(payload) {
        if (payload) state.plan = payload;
        const current = state.plan || {};
        const banner = bannerFor(current);
        if (banner.text) say(banner.text, banner.kind);
        const symbolCell = el('mrSymbol');
        if (symbolCell) {
            symbolCell.textContent = current.ok
                ? (current.symbol + ' @ ' + fmtPrice(current.spot)) : (current.symbol || DASH);
        }
        const sub = el('mrSub');
        if (sub) {
            sub.textContent = current.ok
                ? ('deterministic read of the engine\'s live state · ' + inputsText(current))
                : (current.error || 'refresh to read');
        }
        const regime = (current.regime || {});
        const scores = current.scores || {};
        const fields = {
            mrRegime: current.ok ? regimeText(current) : DASH,
            mrConviction: current.ok ? fmtScore(current.conviction) : DASH,
            mrTrend: current.ok ? scoreRow(scores, 'trend') : DASH,
            mrImbalance: current.ok ? scoreRow(scores, 'imbalance') : DASH,
            mrAbsorption: current.ok ? scoreRow(scores, 'absorption') : DASH,
            mrLiquidity: current.ok ? scoreRow(scores, 'liquidity') : DASH,
            mrLevelsScore: current.ok ? scoreRow(scores, 'levels') : DASH,
            mrProfileVwap: current.ok
                ? (scoreRow(scores, 'profile') + ' / ' + scoreRow(scores, 'vwap')) : DASH,
            mrBuyerImpulse: current.ok ? yesNo(regime.buyer_led) : DASH,
            mrSellerImpulse: current.ok ? yesNo(regime.seller_led) : DASH,
            mrAbsorbing: current.ok ? (regime.absorbing
                ? ('yes' + (regime.absorbing_side ? ' (' + regime.absorbing_side + ')' : '')) : 'no') : DASH,
        };
        Object.keys(fields).forEach((id) => {
            const node = el(id);
            if (node) node.value = fields[id];
        });
        const count = el('mrLevels');
        if (count) count.textContent = current.ok ? levelCount(current) : '0 levels';
        const body = el('mrBody');
        if (body) body.innerHTML = rowsHtml(current.ok ? current : null);
        /* A read with no levels prints its summary sentence; the table waits for rows. */
        const table = el('mrTable');
        if (table) table.hidden = !(current.ok && ((current.levels || []).length > 0));
        const summary = el('mrSummary');
        if (summary) {
            summary.innerHTML = current.ok
                ? '<div>' + esc(summaryText(current)) + '</div>'
                : '<div class="dim">' + esc(current.error || 'refresh to generate') + '</div>';
        }
    }

    async function refresh() {
        const symbol = activeSymbol();
        if (!symbol) { say('pick an instrument first — the read is about one instrument', 'info'); return; }
        state.symbol = symbol;
        state.busy = true;
        if (!state.plan) say('reading ' + symbol + ' from the engine…', 'info');
        try {
            const payload = await get(urlFor(symbol));
            state.at = Date.now();
            paint(payload);
        } catch (err) {
            say('the market read request failed: ' + errText(err), 'err');
        } finally {
            state.busy = false;
        }
    }

    function tick() {
        if (!isActive() || (typeof document !== 'undefined' && document.hidden) || win().OFAP_PAUSED) return;
        const intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        if (activeSymbol() !== state.symbol) { void refresh(); return; }
        if ((Date.now() - state.at) < REFRESH_MS || state.busy) return;
        void refresh();
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        const button = el('mrRefresh');
        if (button) button.addEventListener('click', () => { state.at = 0; void refresh(); });
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

    win().OFAPMARKETREAD = {
        VERSION: VERSION, VIEW: VIEW, URL_BASE: URL_BASE, REFRESH_MS: REFRESH_MS, TICK_MS: TICK_MS,
        DASH: DASH, esc: esc, normalize: normalize, num: num, fmtPrice: fmtPrice, fmtScore: fmtScore,
        yesNo: yesNo, regimeText: regimeText, urlFor: urlFor, rowHtml: rowHtml, rowsHtml: rowsHtml,
        levelCount: levelCount, inputsText: inputsText, summaryText: summaryText, bannerFor: bannerFor,
        paint: paint, refresh: refresh, tick: tick, wire: wire, watch: watch,
        activeSymbol: activeSymbol, state: () => state.plan,
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
