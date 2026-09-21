/* data-quality.js — the Data quality cockpit: coverage, gaps, duplicates, staleness, one letter each.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/dataquality.py — read its header first):
 *   GET /api/atlas/data-quality                  {ok, at, kind, window_h, settings, count, rows[],
 *                                                 note} — one row per instrument, worst verdict first
 *   GET /api/atlas/data-quality/{symbol}?hours=  the full scorecard for one instrument:
 *                                                 {ok, symbol, verdict, coverage_pct, present_slots,
 *                                                  expected_slots, samples, window_s, capped,
 *                                                  gaps[], biggest_gap, duplicates{}, out_of_order{},
 *                                                  stale_ms, fresh, sentence, notes[], repairs[]}
 *   A refusal is {ok: false, detail} — and the banner prints the SERVER'S own sentence, never a
 *   number invented here.
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - The numbers are the server's. This module formats them (a duration, a percentage, a clock) and
 *     paints them; it computes nothing about the data it is looking at.
 *   - The verdict is a letter with one plain sentence under it, because "96% complete, biggest gap
 *     4 m 12 s at 03:04, three duplicate stamps" is what a user can act on, and a table of raw counts
 *     is not.
 *   - The repair list is the server's own: each hint carries the route the app can run, and the two
 *     repairs this build has no path for say so. No button is drawn for a hint with no route.
 *   - The detail follows the app-wide instrument (the shell's picker) unless a row is clicked, so
 *     opening this panel on a symbol the user is already looking at shows that symbol.
 *   - Read-only: two GETs per pass (the list, then the selected instrument), 15 s cadence while the
 *     view is on screen, and the cadence is handed to OFAPPause so P clears it like every other poll.
 */
(function () {
    'use strict';

    var VERSION = '0.1.0';
    var VIEW = '.view[data-view="data-quality"]';
    var ROWS_URL = '/api/atlas/data-quality';
    var SYMBOL_URL = '/api/atlas/data-quality/';
    var POLL_MS = 15000;
    var DASH = '\u2014';

    var LETTERS = ['A', 'B', 'C', 'D', 'F'];

    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function doc() { return (typeof document !== 'undefined' && document) ? document : null; }
    function el(id) { var d = doc(); return (d && d.getElementById) ? d.getElementById(id) : null; }
    function errText(err) { return String(err && err.message ? err.message : err); }

    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    /* ── the formatters (pure: pinned by data-quality.selftest.js under node) ─────────────────── */

    function normalize(symbol) { return String(symbol == null ? '' : symbol).trim().toUpperCase(); }

    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        var n = Number(value);
        return isFinite(n) ? n : null;
    }

    /* Mirrors dataquality.fmt_pct: 96.5 -> "96.5", 96 -> "96", junk -> "0". */
    function fmtPct(value) {
        var n = num(value);
        if (n === null) return '0';
        var rounded = Math.round(n * 10) / 10;
        return (Math.abs(rounded - Math.round(rounded)) < 0.05) ? String(Math.round(rounded))
            : rounded.toFixed(1);
    }

    /* Mirrors dataquality.fmt_duration: "42 s", "4 m 12 s", "3 h 07 m", "2 d 4 h". */
    function fmtDur(ms) {
        var total = Math.max(0, Math.round((Number(ms) || 0) / 1000));
        if (total < 60) return total + ' s';
        var m = Math.floor(total / 60), s = total % 60;
        if (m < 60) return m + ' m ' + (s < 10 ? '0' : '') + s + ' s';
        var h = Math.floor(m / 60);
        if (h < 24) return h + ' h ' + pad(m % 60) + ' m';
        return Math.floor(h / 24) + ' d ' + (h % 24) + ' h';
    }

    function pad(n) { return (n < 10 ? '0' : '') + n; }

    /* Mirrors dataquality.fmt_window: seconds in, "24 h" / "1 h 12 m" / "45 m" out. */
    function fmtWindow(seconds) {
        var total = Math.max(1, Math.round(Number(seconds) || 0));
        if (total < 60) return total + ' s';
        if (total < 3600) return Math.max(1, Math.floor(total / 60)) + ' m';
        var h = Math.floor(total / 3600), rest = total % 3600;
        if (rest < 60) return h + ' h';
        return h + ' h ' + pad(Math.floor(rest / 60)) + ' m';
    }

    /* The clock of a stamp, minute resolution, the same words the server uses. */
    function fmtClock(ms) {
        var n = num(ms);
        if (n === null) return DASH;
        var d = new Date(n);
        if (isNaN(d.getTime())) return DASH;
        return pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes());
    }

    function verdictClass(letter) {
        var v = String(letter || '').toUpperCase();
        return LETTERS.indexOf(v) >= 0 ? v.toLowerCase() : 'none';
    }

    /* The palette the verdict wears. Inline, because this panel owns no stylesheet of its own and a
       letter that renders the same colour as the next one is not a verdict. */
    function letterColor(letter) {
        var v = String(letter || '').toUpperCase();
        if (v === 'A') return 'var(--m-up, #31a24c)';
        if (v === 'B') return 'var(--m-accent, #4a9df8)';
        if (v === 'C' || v === 'D') return 'var(--orange, #e8a33d)';
        return 'var(--m-down, #e5484d)';
    }

    function barWidth(pct) {
        var n = num(pct);
        if (n === null) return 0;
        return Math.max(0, Math.min(100, Math.round(n)));
    }

    /* Worst first: F..A, then the least complete inside a letter. */
    function sortRows(rows) {
        var order = { F: 0, D: 1, C: 2, B: 3, A: 4 };
        return (rows || []).slice().sort(function (a, b) {
            var ra = order[String((a || {}).verdict || '').toUpperCase()];
            var rb = order[String((b || {}).verdict || '').toUpperCase()];
            ra = (ra === undefined) ? -1 : ra;
            rb = (rb === undefined) ? -1 : rb;
            if (ra !== rb) return ra - rb;
            return (num((a || {}).coverage_pct) || 0) - (num((b || {}).coverage_pct) || 0);
        });
    }

    function rowsUrl(hours) {
        var h = num(hours);
        return h && h > 0 ? ROWS_URL + '?hours=' + encodeURIComponent(h) : ROWS_URL;
    }

    function symbolUrl(symbol, hours) {
        var sym = normalize(symbol);
        if (!sym) return '';
        var path = SYMBOL_URL + encodeURIComponent(sym);
        var h = num(hours);
        return h && h > 0 ? path + '?hours=' + encodeURIComponent(h) : path;
    }

    /* The instrument the detail should show: a clicked row wins, else the app-wide picker, else the
       first row the server sent. Empty string means "nothing to show yet". */
    function pickedRow(rows, symbol) {
        var list = rows || [];
        var want = normalize(symbol);
        if (want) {
            for (var i = 0; i < list.length; i += 1) {
                if (normalize(list[i] && list[i].symbol) === want) return list[i];
            }
        }
        return list.length ? list[0] : null;
    }

    function sheetSymbol() {
        var shell = win().S;
        if (shell && shell.symbol) return normalize(shell.symbol);
        var select = el('symbolSelect');
        return normalize(select && select.value);
    }

    /* ── the markup (pure strings, everything escaped) ────────────────────────────────────────── */

    function barCell(row) {
        var pct = fmtPct((row || {}).coverage_pct);
        var color = letterColor((row || {}).verdict);
        return '<div class="dq-bar" title="' + esc(pct + '% of the expected samples arrived') + '" '
            + 'style="position:relative;height:6px;border-radius:999px;overflow:hidden;'
            + 'background:rgba(255,255,255,.08);min-width:60px">'
            + '<div class="dq-bar-fill is-' + esc(verdictClass((row || {}).verdict)) + '" '
            + 'style="height:100%;width:' + barWidth((row || {}).coverage_pct) + '%;'
            + 'background:' + color + '"></div></div>'
            + '<span class="dq-pct">' + esc(pct) + '%</span>';
    }

    function windowCell(row) {
        var r = row || {};
        var text = fmtWindow(r.window_s);
        return esc(text) + (r.capped ? ' <span class="dim">(capped)</span>' : '');
    }

    function gapCount(row) {
        var r = row || {};
        var total = num(r.n_gaps_total);
        if (total === null) total = num(r.n_gaps) || 0;
        if (!total) return '<span class="dim">none</span>';
        var biggest = r.biggest_gap || {};
        return esc(total + (total === 1 ? ' gap' : ' gaps') + ' \u00b7 ' + fmtDur(biggest.gap_ms));
    }

    function staleCell(row) {
        var r = row || {};
        var ms = num(r.stale_ms);
        if (ms === null) return DASH;
        return r.fresh ? '<span class="dim">live \u00b7 ' + esc(fmtDur(ms)) + '</span>'
            : esc(fmtDur(ms) + ' old');
    }

    function rowHtml(row) {
        var r = row || {};
        if (r.ok === false) {
            return '<tr class="dq-refused"><td class="name">' + esc(r.symbol || DASH) + '</td>'
                + '<td colspan="6" class="dim">' + esc(r.detail || r.error || 'no stored history')
                + '</td></tr>';
        }
        var letter = String(r.verdict || '').toUpperCase();
        return '<tr data-dq-symbol="' + esc(normalize(r.symbol)) + '">'
            + '<td class="name">' + esc(r.symbol || DASH) + '</td>'
            + '<td><span class="dq-verdict is-' + esc(verdictClass(letter)) + '" style="'
            + 'font-weight:600;color:' + letterColor(letter) + '">'
            + esc(letter || DASH) + '</span></td>'
            + '<td>' + barCell(r) + '</td>'
            + '<td>' + windowCell(r) + '</td>'
            + '<td>' + gapCount(r) + '</td>'
            + '<td>' + staleCell(r) + '</td>'
            + '<td class="dim">' + esc(r.sentence || '') + '</td></tr>';
    }

    function rowsHtml(rows) {
        var list = sortRows(rows);
        if (!list.length) {
            return '<tr><td colspan="7" class="dim">no instruments to check yet \u2014 enable one in '
                + 'Instruments and let the engine store some history</td></tr>';
        }
        return list.map(rowHtml).join('');
    }

    function gapHtml(gap) {
        var g = gap || {};
        return '<tr><td>' + esc(g.from_utc || fmtClock(g.from_ms)) + '</td>'
            + '<td>' + esc(fmtDur(g.gap_ms)) + '</td>'
            + '<td>' + esc(String(num(g.missing_slots) === null ? DASH : num(g.missing_slots))) + '</td>'
            + '<td>' + esc(String(num(g.samples_inside) === null ? 0 : num(g.samples_inside)))
            + '</td></tr>';
    }

    function gapsHtml(card) {
        var c = card || {};
        if (c.ok === false) {
            return '<tr><td colspan="4" class="dim">' + esc(c.detail || c.error || '') + '</td></tr>';
        }
        var gaps = c.gaps || [];
        if (!gaps.length) {
            return '<tr><td colspan="4" class="dim">no gap wider than the threshold in this window'
                + (num(c.n_holes) ? ' \u2014 ' + esc(c.n_holes) + ' narrower hole(s) counted' : '')
                + '</td></tr>';
        }
        return gaps.map(gapHtml).join('');
    }

    /* The repairs the server offered. A hint with a route is printed WITH the route (that is the
       honest half); a hint without one says why there is nothing to press. */
    function repairHtml(hint) {
        var h = hint || {};
        var tail = h.available && h.route
            ? '<span class="dim"> \u00b7 ' + esc(h.route) + '</span>'
            : '<span class="dim"> \u00b7 no repair path in this build</span>';
        return '<li><b>' + esc(h.label || h.action || 'repair') + '</b>' + tail
            + '<div class="dim">' + esc(h.why || '') + '</div></li>';
    }

    function repairsHtml(card) {
        var c = card || {};
        if (c.ok === false) return '<div class="dim">' + esc(c.detail || c.error || '') + '</div>';
        var hints = c.repairs || [];
        if (!hints.length) return '<div class="dim">nothing to repair \u2014 the stored history reads '
            + 'clean for this window</div>';
        return '<ul class="dq-repairs">' + hints.map(repairHtml).join('') + '</ul>';
    }

    function notesHtml(card) {
        var notes = ((card || {}).notes) || [];
        if (!notes.length) return '';
        return '<ul class="dq-notes">' + notes.map(function (n) {
            return '<li class="dim">' + esc(n) + '</li>';
        }).join('') + '</ul>';
    }

    /* One refusal, one clean sentence, one warning — the banner's own decision. */
    function bannerFor(payload) {
        if (!payload) return { text: '', kind: 'info' };
        if (payload.ok === false) {
            return { text: String(payload.detail || payload.error || 'the check failed for no stated reason'),
                     kind: 'warn' };
        }
        var sentence = String(payload.sentence || '').trim();
        if (!sentence) return { text: '', kind: 'info' };
        var letter = String(payload.verdict || '').toUpperCase();
        if (letter === 'A') return { text: sentence, kind: 'ok' };
        if (letter === 'B' || letter === 'C') return { text: sentence, kind: 'info' };
        return { text: sentence, kind: 'warn' };
    }

    function detailSub(card) {
        var c = card || {};
        if (c.ok === false) return String(c.detail || c.error || '');
        var parts = [String(c.symbol || ''), String(c.asset_class || ''), String(c.kind || '')];
        parts.push(fmtWindow(c.window_s) + ' judged of ' + fmtWindow(c.configured_window_s));
        parts.push(String(num(c.present_slots) === null ? 0 : num(c.present_slots)) + ' of '
            + String(num(c.expected_slots) === null ? 0 : num(c.expected_slots)) + ' expected');
        if (num(c.samples) !== null) parts.push(String(num(c.samples)) + ' rows');
        return parts.filter(function (p) { return String(p || '').length; }).join(' \u00b7 ');
    }

    /* ── the panel ────────────────────────────────────────────────────────────────────────────── */

    var state = { rows: [], card: null, at: 0, busy: false, symbol: '', windowH: 0, wired: false, timer: 0 };

    function section() {
        var d = doc();
        return (d && d.querySelector) ? d.querySelector(VIEW) : null;
    }

    function isActive() {
        var view = section();
        return !!(view && view.classList && view.classList.contains('active'));
    }

    /* The parent's markup owns the ids; when a container is missing the panel builds that one piece
       inside its own section, so a half-wired view still works. */
    function make(tag, id, className, html) {
        var d = doc();
        if (!d || !d.createElement) return null;
        var node = d.createElement(tag);
        if (id) node.id = id;
        if (className) node.className = className;
        if (html) node.innerHTML = html;
        return node;
    }

    function ensure() {
        var view = section();
        if (!view || !view.appendChild) return null;
        if (!el('dataQualityRows')) {
            var card = make('div', '', 'card');
            var body = make('div', '', 'card-body');
            var table = make('table', '', 'data', '<thead><tr><th>Instrument</th><th>Verdict</th>'
                + '<th>Coverage</th><th>Window</th><th>Gaps</th><th>Newest sample</th>'
                + '<th>What it says</th></tr></thead>');
            var tbody = make('tbody', 'dataQualityRows', '', '');
            if (table && tbody) { table.appendChild(tbody); }
            if (body && table) { body.appendChild(table); }
            if (card && body) { card.appendChild(body); view.appendChild(card); }
        }
        if (!el('dataQualityGaps')) {
            var gcard = make('div', '', 'card');
            var gbody = make('div', '', 'card-body');
            /* §148 T5-F-16: `from_utc` is the LAST PRINT BEFORE the hole, not its start —
               the header must not promise the other reading. */
            var gtable = make('table', '', 'data', '<thead><tr><th>Last print before the gap (UTC)</th><th>For</th>'
                + '<th>Missing slots</th><th>Samples inside</th></tr></thead>');
            var gtbody = make('tbody', 'dataQualityGaps', '', '');
            if (gtable && gtbody) { gtable.appendChild(gtbody); }
            if (gbody && gtable) { gbody.appendChild(gtable); }
            if (gcard && gbody) { gcard.appendChild(gbody); view.appendChild(gcard); }
        }
        if (!el('dataQualityRepairs')) {
            view.appendChild(make('div', 'dataQualityRepairs', 'card-body', ''));
        }
        if (!el('dataQualityBanner')) {
            var banner = make('div', 'dataQualityBanner', 'hint', '');
            if (banner) view.insertBefore(banner, view.firstChild && view.firstChild.nextSibling);
        }
        return view;
    }

    function say(message, kind) {
        var box = el('dataQualityBanner');
        if (!box) return;
        if (typeof win().toast === 'function') { win().toast(box, message, kind || 'info'); return; }
        box.textContent = String(message || '');
    }

    function get(path) {
        if (typeof win().api === 'function') return win().api(path);
        return fetch(path).then(function (r) { return r.json(); });
    }

    function paintRows(payload) {
        var body = el('dataQualityRows');
        if (body) body.innerHTML = rowsHtml((payload && payload.rows) || []);
        var sub = el('dataQualitySub');
        if (sub) {
            var kind = String((payload && payload.kind) || 'ticks');
            var hours = num(payload && payload.window_h);
            sub.textContent = 'stored history, per instrument \u00b7 ' + kind
                + (hours ? ' \u00b7 a ' + fmtWindow(hours * 3600) + ' window' : '')
                + ' \u00b7 ' + (payload && payload.note ? String(payload.note) : 'the store is the judge');
        }
        var stamp = el('dataQualitySince');
        if (stamp) {
            var at = num(payload && payload.at);
            stamp.textContent = at ? ('checked ' + fmtClock(at) + ' UTC') : DASH;
        }
    }

    function paintCard(card) {
        state.card = card || null;
        var current = card || {};
        var banner = bannerFor(current);
        if (banner.text) say(banner.text, banner.kind);
        var title = el('dataQualityDetail');
        if (title) {
            title.textContent = current.ok === false ? (current.symbol || DASH)
                : (String(current.symbol || '') + ' \u00b7 ' + String(current.verdict || ''));
        }
        var sub = el('dataQualitySummary');
        if (sub) sub.textContent = detailSub(current);
        var body = el('dataQualityGaps');
        if (body) body.innerHTML = gapsHtml(current);
        var repairs = el('dataQualityRepairs');
        if (repairs) repairs.innerHTML = repairsHtml(current) + notesHtml(current);
        return current;
    }

    async function refreshCard(symbol) {
        var url = symbolUrl(symbol, state.windowH);
        if (!url) return null;
        state.symbol = normalize(symbol);
        try {
            return paintCard(await get(url));
        } catch (err) {
            say('the data-quality check failed: ' + errText(err), 'err');
            return null;
        }
    }

    async function refresh() {
        if (state.busy) return null;
        state.busy = true;
        if (!state.rows.length) say('reading the store\u2026', 'info');
        try {
            var payload = await get(rowsUrl(state.windowH));
            state.at = Date.now();
            if (payload && payload.ok === false) {
                state.rows = [];
                paintRows({ ok: false, rows: [], kind: '', window_h: state.windowH, at: state.at });
                paintCard(payload);
                return payload;
            }
            var hours = num(payload && payload.window_h);
            if (hours) state.windowH = hours;
            /* Worst first, both for the table and for what the detail follows by default: a cockpit
               that opens on its cleanest instrument has buried the reason it exists. */
            state.rows = sortRows((payload && payload.rows) || []);
            paintRows(payload);
            var row = pickedRow(state.rows, state.symbol || sheetSymbol());
            if (row && row.symbol) await refreshCard(row.symbol);
            return payload;
        } catch (err) {
            say('the data-quality request failed: ' + errText(err), 'err');
            return null;
        } finally {
            state.busy = false;
        }
    }

    /* One timer, and it is handed to the app's pause registry: P (or the topbar chip) clears it and
       resume rebuilds it — the suite's rule for every poller. */
    function tick() {
        var d = doc();
        if (!isActive() || (d && d.hidden) || win().OFAP_PAUSED) return;
        var intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        if ((Date.now() - state.at) < POLL_MS) return;
        void refresh();
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        var button = el('dataQualityRecheck');
        if (button) button.addEventListener('click', function () { state.at = 0; void refresh(); });
        var select = el('symbolSelect');
        if (select) {
            select.addEventListener('change', function () {
                if (!isActive()) return;
                state.symbol = sheetSymbol();
                if (state.symbol) void refreshCard(state.symbol);
            });
        }
        var body = el('dataQualityRows');
        if (body) {
            body.addEventListener('click', function (event) {
                var node = event.target;
                while (node && node !== body && !(node.getAttribute && node.getAttribute('data-dq-symbol'))) {
                    node = node.parentNode;
                }
                var symbol = node && node.getAttribute ? node.getAttribute('data-dq-symbol') : '';
                if (symbol) void refreshCard(symbol);
            });
        }
        var startPolling = function () {
            var id = setInterval(tick, POLL_MS);
            if (window.OFAPPause && window.OFAPPause.register) window.OFAPPause.register(id, startPolling);
            return id;
        };
        state.timer = startPolling();
    }

    function watch() {
        var view = section();
        if (!view) return false;
        ensure();
        wire();
        if (isActive()) void refresh();
        if (typeof MutationObserver === 'function') {
            new MutationObserver(function () { if (isActive()) void refresh(); })
                .observe(view, { attributes: true, attributeFilter: ['class'] });
        }
        return true;
    }

    win().OFAPDATAQUALITY = {
        VERSION: VERSION, VIEW: VIEW, ROWS_URL: ROWS_URL, SYMBOL_URL: SYMBOL_URL, POLL_MS: POLL_MS,
        DASH: DASH, LETTERS: LETTERS,
        esc: esc, normalize: normalize, num: num, fmtPct: fmtPct, fmtDur: fmtDur, fmtWindow: fmtWindow,
        fmtClock: fmtClock, verdictClass: verdictClass, letterColor: letterColor, barWidth: barWidth,
        sortRows: sortRows,
        rowsUrl: rowsUrl, symbolUrl: symbolUrl, pickedRow: pickedRow, sheetSymbol: sheetSymbol,
        rowHtml: rowHtml, rowsHtml: rowsHtml, gapHtml: gapHtml, gapsHtml: gapsHtml,
        repairHtml: repairHtml, repairsHtml: repairsHtml, notesHtml: notesHtml, bannerFor: bannerFor,
        detailSub: detailSub, section: section, isActive: isActive, ensure: ensure, paintRows: paintRows,
        paintCard: paintCard, refresh: refresh, refreshCard: refreshCard, tick: tick, wire: wire,
        watch: watch, state: function () { return state.card; },
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
