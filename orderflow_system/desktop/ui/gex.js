/* gex.js — the GEX panel: dealer gamma per strike, the zero-gamma line and the call/put walls.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/options_api.py :: GET /api/options/gex/{symbol}):
 *   ?source=deribit|tradier|marketdata[&spot=][&width=][&wall_quantile=]
 *   → { ok, symbol, source, expiry, spot, spot_from, multiplier, unit, iv_unit, n_strikes,
 *       rows_shown, rows_total, zero_gamma, call_walls[], put_walls[], total_dex, total_vex,
 *       total_theta, total_vanna, total_charm, call_oi, put_oi, put_call_oi, atm_iv, skew_25d,
 *       carried{vanna,charm},
 *       per_strike[{strike, side, iv, gamma, dealer_gamma, gamma_exp, dex, oi, volume,
 *                   vega, theta, vanna, charm}], note }
 *   A refusal is { ok: false, error } and the banner prints the SERVER'S own sentence.
 *
 * UNITS, read from the payload and never guessed from magnitudes: `iv` is a FRACTION (0.205 =
 * 20.5%, see `iv_unit`) and `unit` names what one unit of `dex`/`gamma_exp` is (the coin the
 * contract is written on, or shares for a 100-share lot) — those two figures are per 1-point move
 * of the underlying. The panel multiplies by 100 to print a percentage and labels the ΔEX/ΓEX
 * columns with `unit`; VEX and Θ keep the venue's own vega/theta units and the units line says so.
 * A magnitude heuristic used to guess "0.19 means 19%" would print a real 1.2% IV as 120%.
 *
 * WHAT THE PANEL REFUSES TO PRETEND: only a chain that carries gammas can answer, so Tradier's
 * OPRA chain (IV, open interest, volume — no greeks) gets that sentence instead of a map of
 * zeros; vanna and charm, which Deribit does not publish, read "not published" rather than $0.00.
 *
 * Read-only: one GET per refresh, at a polite 20 s cadence while the view is on screen and never
 * while the app is paused or hidden. Nothing is stored anywhere.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="gex"]';
    const URL_BASE = '/api/options/gex/';
    const REFRESH_MS = 20000;       /* an option chain's own cadence, not the tape's */
    const TICK_MS = 2000;           /* the cheap "should we ask again" check */
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

    /* ── the decisions (pure: pinned by gex.selftest.js under node, no DOM in reach) ─────────── */

    function normalize(symbol) { return String(symbol == null ? '' : symbol).trim().toUpperCase(); }

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }

    /* An exposure can be millions and can be a fraction: one formatter for both, so a column of
       numbers never mixes "0.0000004" with "1.2M" in the same table. */
    function fmtBig(value) {
        const n = num(value);
        if (n === null) return DASH;
        const abs = Math.abs(n);
        if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return (n / 1e3).toFixed(2) + 'K';
        if (abs >= 1) return n.toFixed(2);
        return n.toFixed(6);
    }

    function fmtPrice(value, digits) {
        const n = num(value);
        if (n === null) return DASH;
        const places = Number(digits);
        return n.toFixed(isFinite(places) ? places : (Math.abs(n) >= 100 ? 2 : 6));
    }

    /* The gamma column: the venue's per-contract gamma runs 1e-4..1e-2 on a crypto chain and
       ~0.5 near the money on an equity one, so it follows the Options panel's greek rule — a
       non-zero greek below a milli-unit printed as a plain 0.000 would read as no gamma at all. */
    function fmtGamma(value) {
        const n = num(value);
        if (n === null) return DASH;
        if (Math.abs(n) >= 100) return n.toFixed(1);
        if (n !== 0 && Math.abs(n) < 0.001) return n.toExponential(2);
        return n.toFixed(3);
    }

    /* ΓEX is an exposure like DEX/VEX (K/M/B) but can also be genuinely tiny ten strikes out;
       fmtBig's "0.000000" for 4e-5 reads as a zero, so the small end goes exponential. */
    function fmtGammaExp(value) {
        const n = num(value);
        if (n === null) return DASH;
        if (n !== 0 && Math.abs(n) < 1e-4) return n.toExponential(2);
        return fmtBig(n);
    }

    /* IV arrives as a FRACTION (the engines' unit; the payload says so under `iv_unit`) and is
       printed as a percentage. One rule, no magnitude guessing: a real 1.2% IV is 0.012 and must
       not be read as "1.2" and left alone — that is what the old <=1.5 heuristic did. */
    function fmtIv(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n * 100).toFixed(2) + '%';
    }

    function fmtCount(value) {
        const n = num(value);
        if (n === null) return DASH;
        return String(Math.round(n * 100) / 100);
    }

    function sourceLabel(source) {
        const text = String(source || '').toLowerCase();
        if (text === 'deribit') return 'Deribit';
        if (text === 'tradier') return 'Tradier';
        if (text === 'marketdata') return 'Market Data';
        return text || DASH;
    }

    function urlFor(symbol, source) {
        const path = URL_BASE + encodeURIComponent(normalize(symbol));
        return path + '?source=' + encodeURIComponent(String(source || 'deribit'));
    }

    /* The nearest wall's price, and how far it sits from spot — a wall a third away from spot is
       a different statement from one two ticks away, and the panel says which it is. */
    function wallText(walls, spot) {
        const rows = Array.isArray(walls) ? walls : [];
        if (!rows.length) return DASH;
        const row = rows[0] || {};
        const price = num(row.strike);
        const at = num(spot);
        if (price === null) return DASH;
        const gap = (at && at > 0) ? ((price - at) / at) * 100 : null;
        const base = fmtPrice(price);
        return gap === null ? base : base + ' (' + (gap >= 0 ? '+' : '') + gap.toFixed(2) + '%)';
    }

    /* A greek the venue does not publish is NOT a zero. Deribit sends no vanna and no charm, and
       the server flags that in `carried`; the field then reads "not published" instead of $0.00. */
    function carriedText(payload, key, value) {
        const carried = (payload && payload.carried) || {};
        if (carried[key] === false) return 'not published';
        return fmtBig(value);
    }

    function subText(payload) {
        const spot = fmtPrice(payload && payload.spot);
        const parts = [String((payload && payload.symbol) || '') || DASH,
                       sourceLabel(payload && payload.source)];
        /* The sub-line is written with textContent, so escaping here would PRINT the entity
           (an "&" in a venue's own words would read "&amp;"); esc() is for the table rows only. */
        if (spot !== DASH) parts.push('spot ' + spot + (payload.spot_from ? ' (' + String(payload.spot_from) + ')' : ''));
        if (payload && payload.expiry) parts.push('expiry ' + payload.expiry);
        return parts.join(' · ');
    }

    function rowHtml(row) {
        return '<tr><td>' + esc(fmtPrice(row && row.strike)) + '</td>'
            + '<td>' + esc(String((row && row.side) || '')) + '</td>'
            + '<td>' + esc(fmtIv(row && row.iv)) + '</td>'
            + '<td>' + esc(fmtGamma(row && row.gamma)) + '</td>'
            + '<td>' + esc(fmtGammaExp(row && row.gamma_exp)) + '</td>'
            + '<td>' + esc(fmtCount(row && row.oi)) + '</td>'
            + '<td>' + esc(fmtCount(row && row.volume)) + '</td></tr>';
    }

    function rowsHtml(payload) {
        const rows = (payload && payload.per_strike) || [];
        if (!rows.length) {
            return '<tr><td colspan="7" class="dim">no strikes in this chain</td></tr>';
        }
        /* Widest absolute gamma exposure first: the strikes that can move the underlying are the
           ones the panel exists for, and a 400-row chain cannot be read top-down. */
        const sorted = rows.slice().sort((a, b) => Math.abs(num(b && b.gamma_exp) || 0) - Math.abs(num(a && a.gamma_exp) || 0));
        return sorted.map(rowHtml).join('');
    }

    /* The banner is the server's own words whenever it refused — never a generic one. */
    function bannerFor(payload) {
        if (!payload) return { text: '', kind: 'info' };
        if (payload.ok) {
            const note = String(payload.note || '');
            return { text: note || (fmtCount(payload.n_strikes) + ' strikes read'), kind: 'ok' };
        }
        return { text: String(payload.error || 'the GEX read failed for no stated reason'), kind: 'warn' };
    }

    /* ── the panel ─────────────────────────────────────────────────────────────────────────── */

    const state = { plan: null, error: '', busy: false, at: 0, source: 'deribit', symbol: '' };

    function section() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector(VIEW);
    }
    function isActive() {
        const view = section();
        return !!(view && view.classList && view.classList.contains('active'));
    }
    /* The engine's own symbol first, the app's instrument select as the fallback — the same rule
       every panel of this family follows. */
    function activeSymbol() {
        const fromState = (typeof S !== 'undefined' && S) ? S.symbol : '';
        const select = el('symbolSelect');
        return normalize(fromState || (select && select.value) || '');
    }
    function chosenSymbol() {
        const box = el('gexSymbol');
        return normalize((box && box.value) || '') || activeSymbol();
    }
    function chosenSource() {
        const select = el('gexSource');
        const value = String((select && select.value) || state.source || 'deribit').toLowerCase();
        return SOURCES.indexOf(value) >= 0 ? value : 'deribit';
    }

    function get(path) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path);
        return fetch(path).then((r) => r.json());
    }

    function say(message, kind) {
        const box = el('gexBanner');
        if (!box) return;
        if (typeof toast === 'function') { toast(box, message, kind || 'info'); return; }
        box.textContent = String(message || '');
    }

    function paint(payload) {
        if (payload) state.plan = payload;
        const current = state.plan || {};
        state.error = current.ok ? '' : String(current.error || '');
        const banner = bannerFor(current);
        if (banner.text) say(banner.text, banner.kind);
        const sub = el('gexSub');
        if (sub) sub.textContent = current.ok ? subText(current) : (current.error || 'no read yet');
        const spot = el('gexSpot');
        if (spot) spot.textContent = current.ok ? ('spot ' + fmtPrice(current.spot)) : DASH;
        const fields = {
            gexZeroGamma: current.ok ? fmtPrice(current.zero_gamma) : DASH,
            gexCallWall: current.ok ? wallText(current.call_walls, current.spot) : DASH,
            gexPutWall: current.ok ? wallText(current.put_walls, current.spot) : DASH,
            gexDex: current.ok ? fmtBig(current.total_dex) : DASH,
            gexVex: current.ok ? fmtBig(current.total_vex) : DASH,
            gexTheta: current.ok ? fmtBig(current.total_theta) : DASH,
            gexVanna: current.ok ? carriedText(current, 'vanna', current.total_vanna) : DASH,
            gexCharm: current.ok ? carriedText(current, 'charm', current.total_charm) : DASH,
            gexPcoi: current.ok ? fmtPrice(current.put_call_oi, 3) : DASH,
        };
        Object.keys(fields).forEach((id) => {
            const node = el(id);
            if (node) node.value = fields[id];
        });
        const rows = el('gexRows');
        if (rows) {
            rows.textContent = current.ok
                ? (fmtCount(current.rows_total || current.n_strikes) + ' strikes'
                   + (current.rows_shown && current.rows_total && current.rows_shown < current.rows_total
                       ? ' (showing ' + fmtCount(current.rows_shown) + ')' : ''))
                : '0 strikes';
        }
        const body = el('gexBody');
        if (body) body.innerHTML = rowsHtml(current.ok ? current : null);
        /* The Σ figures and the ΓEX column are exposures, and "1.33K" of what is exactly the
           question the payload's `unit` answers (the coin the contract is written on, or shares).
           Only the delta/gamma figures are per 1-point move — VEX and Θ carry whatever unit the
           venue quoted vega and theta in — so the line names the two it can vouch for. No unit on
           the wire → the labels stay bare rather than inventing one. */
        const unit = String((current && current.unit) || '');
        const gammaHead = el('gexGammaExpHead');
        if (gammaHead) gammaHead.textContent = unit ? 'ΓEX (' + unit + ')' : 'ΓEX';
        const unitsLine = el('gexUnits');
        if (unitsLine) {
            unitsLine.textContent = (current.ok && unit)
                ? 'ΔEX and ΓEX: ' + unit + ' per 1-point move (VEX and Θ stay in the venue’s own '
                  + 'vega/theta units)' : '';
        }
        /* An empty first paint is a header row and nothing else; the table itself steps aside
           until there is a chain behind it. */
        const table = el('gexTable');
        if (table) table.hidden = !(current.ok && ((current.per_strike || []).length > 0));
    }

    async function refresh() {
        const symbol = chosenSymbol();
        if (!symbol) { say('pick an instrument first — the GEX read needs one', 'info'); return; }
        const source = chosenSource();
        state.source = source;
        state.symbol = symbol;
        state.busy = true;
        if (!state.plan) say('reading ' + symbol + " from " + sourceLabel(source) + '…', 'info');
        try {
            const payload = await get(urlFor(symbol, source));
            state.at = Date.now();
            paint(payload);
        } catch (err) {
            const message = 'the GEX request failed: ' + errText(err);
            state.error = message;
            say(message, 'err');
        } finally {
            state.busy = false;
        }
    }

    /* The one timer the panel owns: asks again on the panel's own cadence, and only while it is
       the visible view, the window is not hidden, the app is not paused and no pointer intent is
       holding the UI. A moved instrument refreshes immediately. */
    function tick() {
        if (!isActive() || (typeof document !== 'undefined' && document.hidden) || win().OFAP_PAUSED) return;
        const intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        if (chosenSymbol() !== state.symbol) { void refresh(); return; }
        if ((Date.now() - state.at) < REFRESH_MS) return;
        if (state.busy) return;
        void refresh();
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        const button = el('gexRefresh');
        if (button) button.addEventListener('click', () => { void refresh(); });
        const source = el('gexSource');
        if (source) source.addEventListener('change', () => { state.at = 0; void refresh(); });
        const box = el('gexSymbol');
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

    win().OFAPGEX = {
        VERSION: VERSION, VIEW: VIEW, URL_BASE: URL_BASE, REFRESH_MS: REFRESH_MS, TICK_MS: TICK_MS,
        DASH: DASH, SOURCES: SOURCES, esc: esc, normalize: normalize, num: num, fmtBig: fmtBig,
        fmtPrice: fmtPrice, fmtIv: fmtIv, fmtGamma: fmtGamma, fmtGammaExp: fmtGammaExp,
        fmtCount: fmtCount, sourceLabel: sourceLabel,
        urlFor: urlFor, wallText: wallText, carriedText: carriedText, subText: subText,
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
