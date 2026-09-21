/* derivatives.js — the crypto-derivatives cockpit: funding, open interest and basis per venue.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/derivatives.py :: GET /api/atlas/derivatives/{symbol}):
 *   ?venues=bybit,binance,okx,hyperliquid[&refresh=1]
 *   → { ok, symbol, as_of_ms, venues_asked, venues_ok, summary,
 *       funding{available, median_rate, median_pct, median_interval_h, rate_apr_pct,
 *               median_apr_pct, min_apr_pct,
 *               max_apr_pct, spread_apr_pct, direction, verdict, crowded[], per_venue[]},
 *       oi{total_usd, venues_usd, change_pct, change_source, window_s, span_s, samples, reason,
 *          window_limited, per_venue{}, unit},
 *       basis{available, median_bps, min_bps, max_bps, spread_bps, median_apr_pct, note},
 *       venues[{venue, label, instrument, ok, error, reason, notes[], funding_rate, funding_pct,
 *               funding_interval_h, funding_apr_pct, next_funding_ms, next_funding_in_s, mark, index,
 *               basis_bps, basis_apr_pct, open_interest, open_interest_unit, open_interest_usd,
 *               oi_change_pct, oi_span_s, oi_samples, oi_change_reason, ts_ms, age_ms}],
 *       errors[{venue, label, reason}], settings{} }
 *   A refusal is { ok: false, detail } and the banner prints the SERVER'S own sentence.
 *
 * THE SENTENCE IS THE SERVER'S. `summaryText()` prints the server's own words and only rebuilds the
 * sentence from the two read blocks when the payload has none (an older server, a cached page) — the
 * rewrite is the same rule, pinned against the Python one by test_derivatives.py, so the two halves
 * cannot drift apart on the wording.
 *
 * WHAT THE PANEL REFUSES TO PRETEND: a venue that did not answer keeps its row and gets the server's
 * sentence in place of numbers (never a 0.00 that would read as a flat rate); the open-interest
 * change reads "not known yet" with the reason until this app has really watched the window (no
 * venue here publishes a change, so a "24 h" figure from one snapshot would be an invention); and
 * every annualised basis figure carries the sentence that it assumes the premium holds.
 *
 * Read-only apart from one POST that stores the venue list. One GET per refresh, at the settings'
 * cadence (60 s by default) while the view is on screen and never while the app is paused, hidden or
 * holding intent. Nothing is stored anywhere.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="derivatives"]';
    const URL_BASE = '/api/atlas/derivatives/';
    const REFRESH_MS = 60000;      /* funding and open interest are slow numbers, unlike the tape */
    const TICK_MS = 5000;          /* the cheap "should we ask again" check */
    const DASH = '\u2014';
    const VENUES = ['bybit', 'binance', 'okx', 'hyperliquid'];

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);

    /* Paint a read-out into whatever the shell's markup put there: a readonly input (the house style
       for a value the app computes) carries it in `.value`, a span or div in `.textContent`. Doing
       both keeps this panel working against either shape instead of silently showing nothing. */
    function put(node, text) {
        if (!node) return;
        if ('value' in node) node.value = String(text); else node.textContent = String(text);
    }
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    /* ── the decisions (pure: pinned by derivatives.selftest.js under node, no DOM in reach) ───── */

    function normalize(symbol) { return String(symbol == null ? '' : symbol).trim().toUpperCase(); }

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }

    /* A signed number at a fixed number of decimals: the sign is never dropped, because on funding
       the sign is the whole story (who pays whom). */
    function signed(value, digits) {
        const n = num(value);
        if (n === null) return DASH;
        const body = Math.abs(n).toFixed(digits);
        if (n > 0) return '+' + body;
        return (n < 0 ? '-' : '') + body;
    }

    /* A funding rate is a fraction of the position per settlement, printed as a percentage at three
       decimals: at one decimal the +0.006% a day that adds up to 20%/yr would read as +0.0%. */
    function fmtRate(rate) {
        const n = num(rate);
        return n === null ? DASH : signed(n * 100, 3) + '%';
    }

    function fmtApr(aprPct) {
        const n = num(aprPct);
        return n === null ? DASH : signed(n, 1) + '%/yr';
    }

    function fmtBps(bps) {
        const n = num(bps);
        return n === null ? DASH : signed(n, 2);
    }

    function fmtChange(pct) {
        const n = num(pct);
        return n === null ? DASH : signed(n, 1) + '%';
    }

    function fmtUsd(value) {
        const n = num(value);
        if (n === null) return DASH;
        const abs = Math.abs(n);
        const sign = n < 0 ? '-' : '';
        if (abs >= 1e9) return sign + (abs / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return sign + (abs / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return sign + (abs / 1e3).toFixed(2) + 'K';
        return sign + abs.toFixed(2);
    }

    function fmtCoin(value, unit) {
        const n = num(value);
        if (n === null) return DASH;
        const text = Math.abs(n) >= 1e3 ? (n / 1e3).toFixed(2) + 'K' : n.toFixed(2);
        return unit ? text + ' ' + unit : text;
    }

    function fmtPrice(value) {
        const n = num(value);
        if (n === null) return DASH;
        return n.toFixed(Math.abs(n) >= 100 ? 2 : 6);
    }

    /* The cross-venue open interest is USD by construction — it sums the venues' own USD figures —
       so the read-out says USD. A venue's coin unit belongs to that venue's column, not to the sum. */
    function oiTotalText(oi) {
        const usd = num(oi && oi.total_usd);
        return usd === null ? DASH : fmtUsd(usd) + ' USD';
    }

    function intervalText(hours) {
        const n = num(hours);
        if (n === null || n <= 0) return '';
        if (n < 1) return Math.round(n * 60) + 'm';
        return (Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : n.toFixed(1)) + 'h';
    }

    /* Time until the next settlement: "due now" when it is behind us — the venues' clocks and this
       machine's are not the same clock, and a negative countdown would read as an error. */
    function fmtIn(seconds) {
        const n = num(seconds);
        if (n === null) return DASH;
        if (n <= 0) return 'due now';
        const total = Math.round(n);
        const h = Math.floor(total / 3600);
        const m = Math.floor((total % 3600) / 60);
        if (h >= 24) return Math.floor(h / 24) + ' d ' + (h % 24) + ' h';
        if (h >= 1) return h + ' h ' + (m < 10 ? '0' : '') + m + ' m';
        const s = total % 60;
        if (m >= 1) return m + ' m ' + (s < 10 ? '0' : '') + s + ' s';
        return s + ' s';
    }

    function spanText(spanS, windowS) {
        const span = num(spanS);
        const window = num(windowS) || 0;
        if (span === null || span < 1) return '';
        if (span >= 20 * 3600 && window >= 22 * 3600) return 'on the day';
        if (span >= 3600) {
            const hours = Math.round(span / 360) / 10;
            return 'over the last ' + (hours % 1 === 0 ? String(hours) : hours.toFixed(1)) + ' h';
        }
        if (span >= 540) return 'over the last ' + Math.round(span / 60) + ' m';
        return 'over the last ' + Math.round(span) + ' s';
    }

    /* The rate the sentence quotes is a percentage of the position per settlement (the payload's
       `median_pct`), printed at three decimals: at one decimal the +0.006% a day that adds up to
       20%/yr would read as +0.0%. The Python half formats it identically — see funding_text() in
       orderflow_system/atlas/derivatives.py, pinned equal by the parity test.

       The parenthetical is the QUOTED venue's own annualised figure (`rate_apr_pct`), never the
       cross-venue median (`median_apr_pct`): the sentence's two numbers must imply each other
       (T5-F01 — the median is the mean of the two middle venues at an even venue count). */
    function fundingText(funding) {
        if (!funding || !funding.available) return 'funding is not known';
        const interval = intervalText(funding.median_interval_h);
        const pct = num(funding.median_pct);
        const piece = (pct === null ? DASH : signed(pct, 3) + '%') + '/' + interval;
        const apr = num(funding.rate_apr_pct);
        return apr === null ? piece : piece + ' (' + signed(apr, 1) + '% annualised)';
    }

    function oiText(oi) {
        const pct = num(oi && oi.change_pct);
        if (pct === null) {
            const reason = String((oi && oi.reason) || 'the app has not watched long enough');
            return 'the open-interest change not known yet (' + reason + ')';
        }
        let where = spanText(oi && oi.span_s, oi && oi.window_s);
        if (!where) {
            /* No measured span — a venue-median fallback has none — so the number's own source is
               named instead of quoting "0 s" (T5-F02). */
            const source = String((oi && oi.change_source) || '');
            where = source ? '(' + source + ')' : '';
        }
        if (Math.abs(pct) < 0.05) return ('OI flat ' + where).trim();
        return ('OI ' + (pct > 0 ? 'up' : 'down') + ' ' + Math.abs(pct).toFixed(1) + '% ' + where).trim();
    }

    function directionText(funding, cfg) {
        const settings = cfg || {};
        const direction = String((funding && funding.direction) || '');
        if (direction === 'longs_pay') {
            return (funding.crowded_long ? 'a crowded long: ' : '') + 'longs are paying to hold';
        }
        if (direction === 'shorts_pay') {
            return (funding.crowded_short ? 'a crowded short: ' : '') + 'shorts are paying to hold';
        }
        if (direction === 'mixed') return 'the venues disagree about which side is paying';
        if (direction === 'flat') {
            /* Mirrors DEFAULTS['flat_apr_pct'] — a settings-less caller says the default, never
               "undefined" (§148 T5-F-08). */
            const flatAt = settings.flat_apr_pct == null ? 5 : settings.flat_apr_pct;
            return 'neither side is paying much (under ' + String(flatAt) + '% annualised)';
        }
        return 'funding is not known';
    }

    /* The server's sentence when it sent one; otherwise the same rule, rebuilt here. */
    function summaryText(payload) {
        if (!payload) return '';
        if (payload.summary) return String(payload.summary);
        const funding = payload.funding || {};
        if (!funding.available) return '';
        return 'funding is ' + fundingText(funding) + ' with ' + oiText(payload.oi || {})
            + ' \u2014 ' + directionText(funding, payload.settings || {});
    }

    function verdictText(funding) {
        const name = String((funding && funding.verdict) || '');
        return name || DASH;
    }

    /* The OI read: the size, and where the change came from — one venue's own series or the summed
       total — so a number in the strip can always be traced to the rows under it. */
    function oiLine(oi) {
        if (!oi || !oi.available) return 'no venue answered with an open-interest figure';
        const parts = [];
        if (num(oi.total_usd) !== null) {
            parts.push(fmtUsd(oi.total_usd) + ' USD across ' + String(num(oi.venues_usd) || 0)
                + (num(oi.venues_usd) === 1 ? ' venue' : ' venues'));
        }
        if (num(oi.change_pct) === null) {
            parts.push('the change needs a baseline this app has not built yet');
        } else {
            parts.push(fmtChange(oi.change_pct) + ' ' + spanText(oi.span_s, oi.window_s)
                + (oi.change_source ? ', from ' + String(oi.change_source) : ''));
        }
        if (oi.window_limited) parts.push('the window is still filling');
        return parts.join(' \u00b7 ');
    }

    function venueQuery(venues, force) {
        const list = Array.isArray(venues) ? venues.join(',') : String(venues || '');
        const parts = [];
        if (list) parts.push('venues=' + encodeURIComponent(list));
        if (force) parts.push('refresh=1');
        return parts.length ? '?' + parts.join('&') : '';
    }

    function venueList(raw) {
        const parts = String(raw == null ? '' : raw).replace(/,/g, ' ').split(/\s+/);
        const kept = [];
        parts.forEach((part) => {
            const name = part.trim().toLowerCase();
            if (name && VENUES.indexOf(name) >= 0 && kept.indexOf(name) < 0) kept.push(name);
        });
        return kept;
    }

    function stripHtml(funding, settings) {
        const rows = (funding && funding.per_venue) || [];
        if (!rows.length) return '<span class="dim">no venue answered with a funding rate</span>';
        return rows.map((row) => {
            const apr = num(row.apr_pct);
            /* The threshold is the user's setting (the server carries it in `settings`, never
               on the funding read): read from the payload it was always undefined, so no venue
               could ever be painted flat (§148 T5-F-04). */
            const flatAt = num(settings && settings.flat_apr_pct);
            const flat = apr !== null && flatAt !== null && Math.abs(apr) < flatAt;
            const crowded = (funding.crowded || []).some((c) => c.venue === row.venue);
            const cls = crowded ? ' is-crowded'
                : (flat ? ' is-flat' : (apr !== null && apr < 0 ? ' is-short' : ' is-long'));
            const rate = fmtRate(row.rate) + '/' + (intervalText(row.interval_h) || '?');
            return '<span class="derivatives-chip' + cls + '" title="' + esc(
                String(row.label || row.venue) + ' funding ' + rate + ', annualised ' + fmtApr(row.apr_pct))
                + '"><b>' + esc(String(row.label || row.venue)) + '</b> ' + esc(fmtApr(row.apr_pct))
                + ' <span class="dim">' + esc(rate) + '</span></span>';
        }).join('');
    }

    function rowHtml(row) {
        if (!row) return '';
        const label = String(row.label || row.venue || '');
        if (!row.ok) {
            return '<tr class="dim"><td>' + esc(label) + '</td><td colspan="9">'
                + esc(String(row.error || 'this venue did not answer, for no stated reason')) + '</td></tr>';
        }
        const notes = (row.notes || []).join(' \u00b7 ');
        const oiChange = num(row.oi_change_pct) === null
            ? '<span class="dim" title="' + esc(String(row.oi_change_reason || '')) + '">'
              + DASH + ' (no baseline)</span>'
            : esc(fmtChange(row.oi_change_pct));
        return '<tr><td title="' + esc(notes) + '">' + esc(label)
            + (row.instrument ? ' <span class="dim">' + esc(String(row.instrument)) + '</span>' : '')
            + '</td>'
            + '<td>' + esc(fmtRate(row.funding_rate)) + '<span class="dim">/' + esc(intervalText(row.funding_interval_h) || '?') + '</span></td>'
            + '<td>' + esc(fmtApr(row.funding_apr_pct)) + '</td>'
            + '<td>' + esc(fmtIn(row.next_funding_in_s)) + '</td>'
            + '<td>' + esc(fmtCoin(row.open_interest, row.open_interest_unit)) + '</td>'
            + '<td>' + oiChange + '</td>'
            + '<td>' + esc(fmtPrice(row.mark)) + '</td>'
            + '<td>' + esc(fmtPrice(row.index)) + '</td>'
            + '<td>' + esc(fmtBps(row.basis_bps)) + '</td>'
            + '<td>' + esc(fmtApr(row.basis_apr_pct)) + '</td></tr>';
    }

    function rowsHtml(payload) {
        const rows = (payload && payload.venues) || [];
        if (!rows.length) {
            return '<tr><td colspan="10" class="dim">no venue has answered yet</td></tr>';
        }
        return rows.map(rowHtml).join('');
    }

    /* Every caveat a venue's payload carried, once, with the venue named — the panel's honesty
       layer (Hyperliquid's hourly funding, Binance's missing interval, an optional call that
       failed) belongs somewhere readable, and a tooltip is not a place to hide it. */
    function notesText(payload) {
        const out = [];
        const seen = {};
        ((payload && payload.venues) || []).forEach((row) => {
            ((row && row.notes) || []).forEach((note) => {
                const text = String(note || '');
                if (!text || seen[text]) return;
                seen[text] = true;
                out.push(String(row.label || row.venue) + ': ' + text);
            });
        });
        const basis = (payload && payload.basis) || {};
        if (basis.available && basis.note) out.push(String(basis.note));
        return out.join(' \u00b7 ');
    }

    /* The banner is the server's own words whenever it refused — never a generic one. */
    function bannerFor(payload) {
        if (!payload) return { text: '', kind: 'info' };
        if (payload.ok) {
            const missing = (payload.errors || []).map((e) => String(e.label || e.venue) + ': ' + String(e.reason || ''));
            const dropped = payload.dropped_venues || [];
            const parts = [];
            if (missing.length) parts.push('no answer from ' + missing.join(', '));
            if (dropped.length) parts.push('not a venue this panel covers: ' + dropped.join(', '));
            return { text: parts.join(' \u00b7 '), kind: parts.length ? 'warn' : 'ok' };
        }
        return { text: String(payload.detail || payload.error || 'the derivatives read failed for no stated reason'), kind: 'warn' };
    }

    /* ── the panel ─────────────────────────────────────────────────────────────────────────── */

    const state = { plan: null, error: '', busy: false, at: 0, symbol: '', venues: [] };

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
        const box = el('derivativesSymbolBox');
        return normalize((box && box.value) || '') || activeSymbol();
    }
    function chosenVenues() {
        const box = el('derivativesVenues');
        const typed = box ? venueList(box.value) : [];
        if (typed.length) return typed;
        const stored = (state.plan && state.plan.settings && state.plan.settings.venues) || [];
        return stored.length ? stored.slice() : VENUES.slice();
    }

    /* The shell's own api() when it is there (ui.js), the browser's fetch otherwise. The module-local
       helper is named `api` on purpose: scripts/audit_ui_refs.py resolves the panel's routes from the
       literal path that follows `api(` at each call site, and the guard names the SHELL's function
       (`typeof window.api`) — a guard on the bare name would recurse into this very function. */
    function api(path, opts) {
        if (typeof window !== 'undefined' && typeof window.api === 'function' && window.api !== api) {
            return window.api(path, opts || {});
        }
        return fetch(path, opts || {}).then((r) => r.json());
    }

    function say(message, kind) {
        const box = el('derivativesBanner');
        if (!box) return;
        const text = String(message || '');
        if (!text && typeof clearToast === 'function' && typeof toast === 'function') {
            clearToast(box);                                        /* a healthy read leaves no stale caution */
            return;
        }
        if (typeof toast === 'function') { toast(box, text, kind || 'info'); return; }
        put(box, text);
    }

    function paint(payload) {
        if (payload) state.plan = payload;
        const current = state.plan || {};
        const funding = current.funding || {};
        const oi = current.oi || {};
        const basis = current.basis || {};
        state.error = current.ok ? '' : String(current.detail || current.error || '');
        const banner = bannerFor(current);
        if (banner.text || current.ok) say(banner.text, banner.kind);
        const summary = el('derivativesSummary');
        if (summary) {
            put(summary, current.ok
                ? (summaryText(current) || 'no venue answered with a funding rate')
                : (current.detail || current.error || 'no read yet'));
        }
        const strip = el('derivativesStrip');
        if (strip) strip.innerHTML = current.ok ? stripHtml(funding, current.settings) : '';
        const fields = {
            derivativesOiTotal: current.ok ? oiTotalText(oi) : DASH,
            derivativesOiChange: current.ok ? fmtChange(oi.change_pct) : DASH,
            derivativesBasis: current.ok ? fmtBps(basis.median_bps) : DASH,
        };
        Object.keys(fields).forEach((id) => {
            put(el(id), fields[id]);
        });
        put(el('derivativesOiNote'), current.ok ? oiLine(oi) : '');
        put(el('derivativesNotes'), current.ok ? notesText(current) : '');
        const sub = el('derivativesSub');
        if (sub) {
            put(sub, current.ok
                ? (String(current.symbol || '') + ' \u00b7 ' + String(current.venues_ok || 0) + ' of '
                   + String(current.venues_asked || 0) + ' venues answered'
                   + (funding.verdict ? ' \u00b7 ' + String(funding.verdict) : ''))
                : (String(current.detail || '') || 'funding, open interest and basis for the active instrument'));
        }
        put(el('derivativesCount'), current.ok ? verdictText(funding) : 'no read');
        put(el('derivativesSymbol'), String(current.symbol || chosenSymbol() || DASH));
        const body = el('derivativesRows');
        if (body) body.innerHTML = rowsHtml(current.ok ? current : null);
        const table = el('derivativesTable');
        if (table) table.hidden = !(current.ok && ((current.venues || []).length > 0));
        state.at = current.ok ? Number(current.as_of_ms) || Date.now() : state.at;
    }

    function ageText() {
        const node = el('derivativesAt');
        if (!node) return;
        if (!state.at) { put(node, ''); return; }
        const secs = Math.max(0, Math.round((Date.now() - state.at) / 1000));
        put(node, 'read ' + fmtIn(secs) + ' ago');
    }

    async function refresh(force) {
        const symbol = chosenSymbol();
        if (!symbol) { say('pick an instrument first — the derivatives read needs one', 'info'); return null; }
        const venues = chosenVenues();
        state.venues = venues;
        state.busy = true;
        try {
            const payload = await api('/api/atlas/derivatives/' + encodeURIComponent(symbol)
                + venueQuery(venues, force));
            paint(payload);
            return payload;
        } catch (err) {
            const message = 'the derivatives request failed: ' + errText(err);
            state.error = message;
            say(message, 'err');
            return null;
        } finally {
            state.busy = false;
        }
    }

    /* Store the venue list. The list is the user's choice, so it is written to the config block by
       the server (the one POST this panel makes) and the read is repeated against it at once. */
    async function setVenues() {
        const venues = chosenVenues();
        if (!venues.length) { say('name at least one venue — one of bybit, binance, okx, hyperliquid', 'info'); return null; }
        try {
            const answer = await api('/api/atlas/derivatives/venues',
                { method: 'POST', body: { venues: venues } });
            say(String((answer && (answer.detail || answer.error)) || ''), answer && answer.ok ? 'ok' : 'warn');
            return await refresh(true);
        } catch (err) {
            say('the venue list could not be saved: ' + errText(err), 'err');
            return null;
        }
    }

    /* The one timer the panel owns: asks again on the settings' cadence, and only while it is the
       visible view, the window is not hidden, the app is not paused and no pointer intent is holding
       the UI. A moved instrument refreshes immediately. */
    function tick(now) {
        if (!isActive() || (typeof document !== 'undefined' && document.hidden) || win().OFAP_PAUSED) return;
        const intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        ageText();
        const symbol = chosenSymbol();
        if (symbol !== state.symbol) { void refresh(true).then(() => { state.symbol = symbol; }); return; }
        const period = Number((state.plan && state.plan.settings && state.plan.settings.refresh_s) || 0);
        const every = period > 0 ? period * 1000 : REFRESH_MS;
        if ((Number(now) || Date.now()) - state.at < every) return;
        if (state.busy) return;
        void refresh(false);
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        const button = el('derivativesRefresh');
        if (button) button.addEventListener('click', () => { void refresh(true); });
        const apply = el('derivativesVenuesApply');
        if (apply) apply.addEventListener('click', () => { void setVenues(); });
        const symbolSelect = el('symbolSelect');
        if (symbolSelect) symbolSelect.addEventListener('change', () => { if (isActive()) void refresh(true); });
        /* The panel's own cadence, handed to the app's pause registry: P (or the topbar chip) clears
           the timer and resume rebuilds it — the suite's rule for every poller. */
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
        const box = el('derivativesVenues');
        if (box) {
            const stored = (state.plan && state.plan.settings && state.plan.settings.venues) || [];
            if (!box.value) box.value = (stored.length ? stored : VENUES).join(',');
        }
        state.symbol = chosenSymbol();
        if (isActive()) void refresh(false);
        new MutationObserver(() => { if (isActive()) void refresh(false); })
            .observe(view, { attributes: true, attributeFilter: ['class'] });
        return true;
    }

    win().OFAPDERIV = {
        VERSION: VERSION, VIEW: VIEW, URL_BASE: URL_BASE, REFRESH_MS: REFRESH_MS,
        TICK_MS: TICK_MS, DASH: DASH, VENUES: VENUES, put: put, oiTotalText: oiTotalText,
        esc: esc, normalize: normalize, num: num, signed: signed, fmtRate: fmtRate, fmtApr: fmtApr,
        fmtBps: fmtBps, fmtChange: fmtChange, fmtUsd: fmtUsd, fmtCoin: fmtCoin, fmtPrice: fmtPrice,
        fmtIn: fmtIn, intervalText: intervalText, spanText: spanText,
        fundingText: fundingText, oiText: oiText, directionText: directionText, summaryText: summaryText,
        verdictText: verdictText, oiLine: oiLine, notesText: notesText,
        stripHtml: stripHtml, rowHtml: rowHtml, rowsHtml: rowsHtml, bannerFor: bannerFor,
        venueQuery: venueQuery, venueList: venueList, ageText: ageText,
        paint: paint, refresh: refresh, setVenues: setVenues, tick: tick, wire: wire, watch: watch,
        chosenSymbol: chosenSymbol, chosenVenues: chosenVenues, activeSymbol: activeSymbol,
        state: () => state.plan,
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
