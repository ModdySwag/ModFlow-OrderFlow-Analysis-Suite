/* synthetic.js — synthetic instruments: build a composite from legs, chart it, read the spread.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/synthetic.py):
 *   GET  /api/atlas/synthetic                     → { ok, definitions[], symbols[{symbol,live,history}],
 *                                                     settings, kinds[], note }
 *   GET  /api/atlas/synthetic/compose?definition=…&window_min=…&points=…
 *                                                 → { ok, definition, stats{value, spread_abs, spread_bps,
 *                                                     reference, reference_kind, z, z_stretch,
 *                                                     beyond_stretch_pct, correlation, carried_pct, samples,
 *                                                     window_minutes, value_unit}, legs[], series[{t,v,z}],
 *                                                     read, note } on success
 *                                                 → { ok: false, detail } on refusal
 *   POST /api/atlas/synthetic                     → { ok, definition, definitions[], saved, detail }
 *                                                   for the builder's Save (id replaces, name makes one)
 *
 * WHAT THE PANEL REFUSES TO PRETEND: a leg with no stored history is not a line of zeros. The
 * server's sentence ("no stored history for BTCUSD — open its chart first") is printed on the
 * banner AND on the canvas, the chart keeps no stale shape from the previous definition, and the
 * symbols the builder offers come from the payload (live / has history) rather than from a guess.
 * How much of each leg was carried forward travels in `carried_pct`, and the panel prints it.
 *
 * One timer, on the app's pause registry: composes again while the view is on screen, the window is
 * visible and the app is not paused or held. Every read is read-only; the only write is Save.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="synthetic"]';
    const LIST_URL = '/api/atlas/synthetic';
    const COMPOSE_URL = '/api/atlas/synthetic/compose';
    const TICK_MS = 2000;            /* the cheap "should we ask again" check */
    const DASH = '\u2014';
    const WINDOWS = [30, 60, 240, 720, 1440];
    const KINDS = ['ratio', 'spread', 'basket', 'basis'];
    const KIND_WORDS = {
        ratio: 'ratio (leg A / leg B)',
        spread: 'spread (leg A \u2212 leg B)',
        basket: 'basket (weighted average)',
        basis: 'basis (premium as bps)',
    };
    const MAX_LEGS = 8;

    function el(id) {
        return (typeof document !== 'undefined' && document) ? document.getElementById(id) : null;
    }
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }
    function num(value) {
        if (value === null || value === undefined || value === '') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }

    /* ── the pure half (pinned by synthetic.selftest.js under node) ─────────────────────────── */

    function fmtNum(value, digits) {
        const n = num(value);
        if (n === null) return DASH;
        const places = num(digits);
        if (places !== null) return n.toFixed(places);
        const abs = Math.abs(n);
        if (abs >= 1e6) return (n / 1e6).toFixed(3) + 'M';
        if (abs >= 1e3) return (n / 1e3).toFixed(3) + 'K';
        if (abs >= 1) return n.toFixed(4);
        return n.toPrecision(6);
    }

    function fmtBps(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n >= 0 ? '+' : '') + n.toFixed(2) + ' bps';
    }

    function fmtPct(value) {
        const n = num(value);
        if (n === null) return DASH;
        return n.toFixed(1) + '%';
    }

    function sigmaWords(z) {
        const n = num(z);
        if (n === null) return 'no z-score yet';
        if (Math.abs(n) < 0.2) return 'flat (' + n.toFixed(2) + '\u03c3)';
        return Math.abs(n).toFixed(2) + '\u03c3 ' + (n > 0 ? 'rich' : 'cheap');
    }

    function windowWord(minutes) {
        const n = num(minutes);
        if (n === null || n <= 0) return DASH;
        if (n < 60) return n.toFixed(0) + 'm';
        if (n < 1440) return (n / 60).toFixed(n % 60 ? 1 : 0) + 'h';
        return (n / 1440).toFixed(n % 1440 ? 1 : 0) + 'd';
    }

    /* The headline the trader reads. The server sends the same sentence (`read`) and the panel
       prefers it — this is the local fallback for a payload that arrived without one. */
    function statsLine(stats) {
        const s = stats || {};
        const parts = ['spread ' + fmtNum(s.spread_abs), fmtBps(s.spread_bps), sigmaWords(s.z)];
        if (s.beyond_stretch_pct !== null && s.beyond_stretch_pct !== undefined) {
            parts.push(fmtPct(s.beyond_stretch_pct) + ' of the window beyond ' +
                fmtNum(s.z_stretch, 1) + '\u03c3');
        }
        return parts.join(' \u00b7 ');
    }

    function defLine(definition) {
        const d = definition || {};
        const legs = Array.isArray(d.legs) ? d.legs : [];
        const text = legs.map((leg) => (leg.side > 0 ? '+' : '\u2212') + String(leg.symbol || '') +
            (num(leg.weight) && num(leg.weight) !== 1 ? '\u00d7' + fmtNum(leg.weight, 2) : '')).join(' ');
        return String(d.kind || '') + '  ' + text;
    }

    function defsHtml(defs, selected) {
        const rows = Array.isArray(defs) ? defs : [];
        if (!rows.length) return '<div class="dim">no synthetic instruments yet — build one below</div>';
        return rows.map((d) => {
            const id = String((d && d.id) || '');
            const on = id === selected ? ' is-on' : '';
            return '<div class="syn-def' + on + '" data-synthetic-def-row="' + esc(id) + '">'
                + '<button type="button" class="btn small' + on + '" data-synthetic-act="pick" '
                + 'data-synthetic-def="' + esc(id) + '" title="Compose this one from the legs\' stored '
                + 'history">' + esc(String((d && d.name) || id)) + '</button>'
                + '<span class="syn-def-line dim">' + esc(defLine(d)) + '</span>'
                + '<button type="button" class="btn small" data-synthetic-act="edit" '
                + 'data-synthetic-def="' + esc(id) + '" title="Load this definition into the builder '
                + '(Save keeps listening, so it replaces it)">edit</button></div>';
        }).join('');
    }

    function symbolsHtml(symbols) {
        const rows = Array.isArray(symbols) ? symbols : [];
        return rows.map((row) => '<option value="' + esc(String((row && row.symbol) || '')) + '">'
            + esc(String((row && row.symbol) || '') + (row && row.live ? ' (live)' : '')
                + (row && row.history ? ' \u00b7 has history' : '')) + '</option>').join('');
    }

    function kindOptions(selected) {
        return KINDS.map((kind) => '<option value="' + kind + '"'
            + (kind === selected ? ' selected' : '') + '>' + esc(KIND_WORDS[kind] || kind)
            + '</option>').join('');
    }

    function legRowHtml(index, leg, symbols) {
        const row = leg || {};
        const side = num(row.side) === -1 ? -1 : 1;
        const weight = num(row.weight) === null ? 1 : num(row.weight);
        const known = (Array.isArray(symbols) ? symbols : []).some(
            (s) => String((s && s.symbol) || '').toUpperCase() === String(row.symbol || '').toUpperCase());
        return '<div class="syn-leg" data-synthetic-leg="' + index + '">'
            + '<label>instrument</label><input type="text" data-synthetic-field="symbol" '
            + 'list="syntheticSymbols" value="' + esc(row.symbol || '') + '" maxlength="32" '
            + 'placeholder="BTCUSDT" title="Any symbol this build stores candles for'
            + (row.symbol && !known ? ' \u2014 the server has no history for this one yet' : '') + '">'
            + '<label>side</label><select data-synthetic-field="side" title="Added to the composite, '
            + 'or subtracted from it">'
            + '<option value="1"' + (side === 1 ? ' selected' : '') + '>add +</option>'
            + '<option value="-1"' + (side === -1 ? ' selected' : '') + '>subtract \u2212</option>'
            + '</select>'
            + '<label>weight</label><input type="number" data-synthetic-field="weight" min="0.01" '
            + 'max="1000" step="0.1" value="' + esc(String(weight)) + '" title="How much of this leg '
            + 'the composite carries (0 is not a leg)">'
            /* The drop button carries its own attribute name: [data-synthetic-leg] must select the
               leg ROWS and nothing else, or reading the builder back walks buttons as well. */
            + '<button type="button" class="btn small" data-synthetic-act="drop-leg" '
            + 'data-synthetic-drop="' + index + '" title="Remove this leg">\u00d7</button></div>';
    }

    function legsHtml(legs, symbols) {
        const rows = (Array.isArray(legs) && legs.length) ? legs : [{ symbol: '', side: 1, weight: 1 }];
        return rows.map((leg, index) => legRowHtml(index, leg, symbols)).join('');
    }

    /* The builder's rows, read back into the wire shape. A row with no instrument is not a leg. */
    function readLegs(host) {
        if (!host || typeof host.querySelectorAll !== 'function') return [];
        const out = [];
        const rows = host.querySelectorAll('[data-synthetic-leg]');
        for (let i = 0; i < rows.length; i += 1) {
            const row = rows[i];
            const field = (name) => (typeof row.querySelector === 'function'
                ? row.querySelector('[data-synthetic-field="' + name + '"]') : null);
            const symbol = field('symbol');
            const side = field('side');
            const weight = field('weight');
            const name = String((symbol && symbol.value) || '').trim().toUpperCase();
            if (!name) continue;
            const amount = num(weight && weight.value);
            out.push({
                symbol: name,
                side: String((side && side.value) || '1') === '-1' ? -1 : 1,
                weight: amount === null ? 1 : amount,
            });
        }
        return out;
    }

    function composeUrl(ident, windowMin, points) {
        const params = ['definition=' + encodeURIComponent(String(ident || ''))];
        /* 0 and null both mean "the server's own setting" — the route reads them that way, so the
           panel does not send a parameter it has no opinion about. */
        const window_ = num(windowMin);
        if (window_ !== null && window_ > 0) params.push('window_min=' + Math.round(window_));
        const cap = num(points);
        if (cap !== null && cap > 0) params.push('points=' + Math.round(cap));
        return COMPOSE_URL + '?' + params.join('&');
    }

    function problemLine(payload) {
        const p = payload || {};
        const problems = Array.isArray(p.problems) ? p.problems : [];
        if (problems.length > 1) return String(p.detail || problems[0]) + ' (+' + (problems.length - 1) + ' more)';
        return String(p.detail || problems[0] || p.error || 'the read failed for no stated reason');
    }

    function statsRows(payload) {
        const p = payload || {};
        const stats = p.stats || {};
        const rows = [
            ['composite', fmtNum(stats.value) + (stats.value_unit === 'ratio' ? ' (ratio)' : '')],
            ['vs ' + (stats.reference_kind === 'short_leg' ? 'the subtracted leg' : 'window median'),
                fmtNum(stats.reference)],
            ['spread', fmtNum(stats.spread_abs) + ' \u00b7 ' + fmtBps(stats.spread_bps)],
            ['z-score', sigmaWords(stats.z) + (stats.z_reason === 'flat' ? ' \u00b7 no move in the window' : '')],
            ['beyond ' + fmtNum(stats.z_stretch, 1) + '\u03c3', fmtPct(stats.beyond_stretch_pct)],
            ['leg correlation', fmtNum(stats.correlation, 3) + (stats.correlation_pairs
                ? ' (' + stats.correlation_pairs + ' pair' + (stats.correlation_pairs === 1 ? '' : 's') + ')'
                : '')],
            ['carried forward', fmtPct(stats.carried_pct)],
            ['window', windowWord(stats.window_minutes) + ' \u00b7 ' + fmtNum(stats.samples, 0) + ' points'],
        ];
        if (!p.ok) return [];
        return rows;
    }

    function statsHtml(payload) {
        const rows = statsRows(payload);
        if (!rows.length) return '';
        return rows.map((pair) => '<div class="syn-stat"><span class="lbl">' + esc(pair[0])
            + '</span><span class="val">' + esc(pair[1]) + '</span></div>').join('');
    }

    function legsTableHtml(legs) {
        const rows = Array.isArray(legs) ? legs : [];
        if (!rows.length) return '';
        return rows.map((leg) => '<tr><td>' + esc(String(leg.symbol || '')) + '</td>'
            + '<td>' + esc(leg.side > 0 ? '+' : '\u2212') + '</td>'
            + '<td>' + esc(fmtNum(leg.weight, 2)) + '</td>'
            + '<td>' + esc(fmtNum(leg.samples, 0)) + '</td>'
            + '<td>' + esc(fmtPct(leg.carried_pct)) + '</td></tr>').join('');
    }

    /* ── geometry (pure: the same mapping the canvas uses, checkable without a browser) ─────── */

    /* Maps a composite series onto a box. The highest value sits on the top edge and the lowest on
       the bottom, so a flat series is drawn across the middle rather than as a zero-height line. */
    function plot(series, width, height, pad) {
        const inset = pad || { left: 8, right: 8, top: 10, bottom: 12 };
        const rows = (Array.isArray(series) ? series : []).filter((point) => point && num(point.v) !== null);
        const outer = { x: inset.left, y: inset.top,
                        w: Math.max(1, num(width) - inset.left - inset.right),
                        h: Math.max(1, num(height) - inset.top - inset.bottom) };
        if (!rows.length) return { points: [], inner: outer, min: null, max: null, mean: null };
        const values = rows.map((point) => num(point.v));
        const min = Math.min.apply(null, values);
        const max = Math.max.apply(null, values);
        const span = (max - min) || Math.abs(max) || 1;
        const points = rows.map((point, index) => ({
            x: outer.x + (rows.length === 1 ? outer.w / 2 : (index / (rows.length - 1)) * outer.w),
            y: outer.y + ((max - num(point.v)) / span) * outer.h,
            t: num(point.t),
            v: num(point.v),
            z: num(point.z),
        }));
        const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
        return { points: points, inner: outer, min: min, max: max, mean: mean };
    }

    /* The z strip: 0 on the middle line, ±`stretch` where the band lines are drawn. */
    function plotZ(series, width, height, stretch) {
        const band = Math.max(0.5, num(stretch) || 1);
        const rows = (Array.isArray(series) ? series : []).filter((point) => point && num(point.z) !== null);
        const edge = Math.max(band * 1.5, rows.reduce(
            (top, point) => Math.max(top, Math.abs(num(point.z))), band));
        const inner = { x: 2, y: 2, w: Math.max(1, num(width) - 4), h: Math.max(1, num(height) - 4) };
        const zero = inner.y + inner.h / 2;
        const points = rows.map((point, index) => ({
            x: inner.x + (rows.length === 1 ? inner.w / 2 : (index / (rows.length - 1)) * inner.w),
            y: zero - (num(point.z) / edge) * (inner.h / 2),
            z: num(point.z),
        }));
        const bandY = (sign) => zero - (sign * band / edge) * (inner.h / 2);
        return { points: points, inner: inner, zero: zero, edge: edge,
                 bandTop: bandY(1), bandBottom: bandY(-1) };
    }

    /* ── the panel ─────────────────────────────────────────────────────────────────────────── */

    const state = {
        defs: [], symbols: [], settings: null, selected: '', editId: '', payload: null,
        error: '', busy: false, at: 0, windowMin: 0, wired: false, timer: null, pendingKind: 'ratio',
    };

    const STYLE = `
.syn-card { margin-top: 12px; }
.syn-grid { display: grid; grid-template-columns: minmax(240px, 1fr) minmax(320px, 2fr); gap: 14px; }
.syn-defs { display: flex; flex-direction: column; gap: 6px; }
.syn-def { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.syn-def.is-on .btn { border-color: var(--accent, #4aa8ff); }
.syn-def-line { font-size: 11.5px; }
.syn-legs { display: flex; flex-direction: column; gap: 6px; }
.syn-leg { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.syn-leg label { font-size: 11px; opacity: .7; }
.syn-leg input[type="text"] { width: 130px; }
.syn-leg input[type="number"] { width: 78px; }
.syn-read { font-size: 15px; font-weight: 600; margin: 8px 0 4px; }
.syn-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin: 6px 0; }
.syn-stat { background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06);
    border-radius: 8px; padding: 6px 9px; }
.syn-stat .lbl { font-size: 10.5px; opacity: .65; display: block; }
.syn-stat .val { font-size: 13px; font-weight: 600; }
.syn-msg { font-size: 11.5px; opacity: .85; }
.syn-note { font-size: 11.5px; opacity: .6; }
.syn-table { width: 100%; font-size: 11.5px; }`;

    function section() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector(VIEW);
    }
    function isActive() {
        const view = section();
        return !!(view && view.classList && view.classList.contains('active'));
    }
    function card() {
        const view = section();
        if (!view || typeof view.querySelector !== 'function') return null;
        return view.querySelector('[data-synthetic-mounted]');
    }

    function get(path, options) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options).then((res) => res.json());
    }

    function say(message, kind) {
        const box = el('syntheticBanner');
        if (!box) return;
        /* The banner carries the SERVER'S sentence verbatim (textContent, so an escaped entity is
           never printed as one). */
        box.textContent = String(message || '');
        box.classList.toggle('syn-bad', kind === 'bad');
    }

    function TEMPLATE() {
        return `
<div class="card syn-card" data-synthetic-mounted="1">
    <div class="card-head">
        <span class="card-title">Synthetic instruments <span class="dim" style="font-weight:400">\u00b7 build a composite from legs, chart the spread</span></span>
        <div class="spacer"></div>
        <span class="dim" id="syntheticStamp"></span>
        <label class="dim" for="syntheticWindow" style="font-size:11px">window</label>
        <select id="syntheticWindow" data-synthetic-act="window" title="How much stored history the composite is built from."></select>
        <button class="btn small" id="syntheticRefresh" data-synthetic-act="refresh" title="Compose the selected instrument again now">Refresh</button>
    </div>
    <div class="card-body">
        <div id="syntheticBanner" class="hint"></div>
        <div class="syn-grid">
            <div>
                <div class="dim" style="font-size:11.5px">Definitions (from your config) — pick one to compose</div>
                <div class="syn-defs" id="syntheticDefs"></div>
            </div>
            <div>
                <div class="dim" style="font-size:11.5px">Builder — Save stores it, then it composes</div>
                <div class="syn-legs" id="syntheticLegs"></div>
                <div class="syn-leg">
                    <label for="syntheticName">name</label>
                    <input type="text" id="syntheticName" maxlength="60" placeholder="BTC perp basis" title="What the panel and the read sentence call it.">
                    <label for="syntheticKind">kind</label>
                    <select id="syntheticKind" title="The arithmetic the legs are composed with."></select>
                </div>
                <div class="syn-leg" style="margin-top:6px">
                    <button class="btn small" id="syntheticAddLeg" data-synthetic-act="add-leg" title="Add another leg (up to 8)">add leg</button>
                    <button class="btn small" id="syntheticNew" data-synthetic-act="new" title="Start a new definition in the builder">new</button>
                    <button class="btn small" id="syntheticSave" data-synthetic-act="save" title="Store this definition in your config — the same id replaces.">Save</button>
                    <span class="syn-msg" id="syntheticMsg"></span>
                </div>
                <datalist id="syntheticSymbols"></datalist>
            </div>
        </div>
        <div class="syn-read" id="syntheticRead">${DASH}</div>
        <div class="syn-stats" id="syntheticStats"></div>
        <canvas id="syntheticCanvas" height="220" title="The composite series: the legs' stored closes aligned on one timeline."></canvas>
        <canvas id="syntheticZCanvas" height="58" title="The z-score strip: how far the composite sits from its own window mean, with the \u00b11\u03c3 band."></canvas>
        <div class="syn-leg" style="margin-top:6px">
            <button class="btn small" id="syntheticLegsToggle" data-synthetic-act="toggle-legs" title="The per-leg sample counts and how much of each leg was carried forward.">leg detail</button>
            <span class="syn-note" id="syntheticNote"></span>
        </div>
        <table class="data syn-table" id="syntheticLegsTable" hidden></table>
    </div>
</div>`;
    }

    function paintWindowOptions() {
        const select = el('syntheticWindow');
        if (!select) return;
        const current = state.windowMin || (state.settings && state.settings.window_min) || 240;
        select.innerHTML = WINDOWS.map((minutes) => '<option value="' + minutes + '"'
            + (minutes === current ? ' selected' : '') + '>' + windowWord(minutes) + '</option>').join('');
        select.value = String(current);
    }

    function paintDefs() {
        const host = el('syntheticDefs');
        if (host) host.innerHTML = defsHtml(state.defs, state.selected);
        const list = el('syntheticSymbols');
        if (list) list.innerHTML = symbolsHtml(state.symbols);
        const kind = el('syntheticKind');
        if (kind && !kind.innerHTML) {
            kind.innerHTML = kindOptions(KINDS.indexOf(state.pendingKind) >= 0 ? state.pendingKind : 'ratio');
        }
    }

    function paintBuilder(legs) {
        const host = el('syntheticLegs');
        if (host) host.innerHTML = legsHtml(legs, state.symbols);
    }

    /* Draw a sentence on a canvas rather than leaving a blank box: the panel's own refusal has to
       be visible where the chart would have been. */
    function noteOnCanvas(id, height, text) {
        const canvas = el(id);
        if (!canvas || typeof canvas.getContext !== 'function') return;
        const dpr = num(win().devicePixelRatio) || 1;
        if (canvas.style) { canvas.style.width = '100%'; canvas.style.height = height + 'px'; }
        const cssW = Math.max(320, canvas.clientWidth || (canvas.parentElement && canvas.parentElement.clientWidth) || 640);
        const w = Math.floor(cssW * dpr), h = Math.floor(height * dpr);
        if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, height);
        ctx.fillStyle = '#67758f';
        ctx.font = '12.5px system-ui';
        ctx.fillText(String(text || DASH).slice(0, 120), 12, Math.round(height / 2) + 4);
    }

    function drawComposite(series) {
        const canvas = el('syntheticCanvas');
        if (!canvas || typeof canvas.getContext !== 'function') return null;
        const dpr = num(win().devicePixelRatio) || 1;
        const cssH = 220;
        if (canvas.style) { canvas.style.width = '100%'; canvas.style.height = cssH + 'px'; }
        const cssW = Math.max(320, canvas.clientWidth || (canvas.parentElement && canvas.parentElement.clientWidth) || 640);
        const w = Math.floor(cssW * dpr), h = Math.floor(cssH * dpr);
        if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);
        const shape = plot(series, cssW, cssH, { left: 10, right: 10, top: 14, bottom: 16 });
        if (!shape.points.length) {
            ctx.fillStyle = '#67758f';
            ctx.font = '13px system-ui';
            ctx.fillText('no composite yet — compose one above', 14, 28);
            return shape;
        }
        const last = shape.points[shape.points.length - 1].v;
        const colour = last >= shape.mean ? '#4ade80' : '#f87171';
        /* The window mean is the reference line the z-score is measured from. */
        const meanValueY = shape.inner.y + ((shape.max - shape.mean) / ((shape.max - shape.min) || 1)) * shape.inner.h;
        ctx.strokeStyle = 'rgba(255,255,255,.18)';
        ctx.beginPath();
        ctx.moveTo(shape.inner.x, meanValueY);
        ctx.lineTo(shape.inner.x + shape.inner.w, meanValueY);
        ctx.stroke();
        ctx.strokeStyle = colour;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        shape.points.forEach((point, index) => {
            if (index === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,.45)';
        ctx.font = '11px system-ui';
        ctx.fillText(fmtNum(shape.max), shape.inner.x, 11);
        ctx.fillText(fmtNum(shape.min), shape.inner.x, cssH - 4);
        ctx.fillStyle = '#67758f';
        ctx.fillText(windowWord(((series || []).length - 1) * (num(state.settings && state.settings.align_ms) || 60000) / 60000) + ' \u00b7 mean ' + fmtNum(shape.mean), shape.inner.x + shape.inner.w - 150, 11);
        return shape;
    }

    function drawZ(series) {
        const canvas = el('syntheticZCanvas');
        if (!canvas || typeof canvas.getContext !== 'function') return null;
        const dpr = num(win().devicePixelRatio) || 1;
        const cssH = 58;
        if (canvas.style) { canvas.style.width = '100%'; canvas.style.height = cssH + 'px'; }
        const cssW = Math.max(320, canvas.clientWidth || (canvas.parentElement && canvas.parentElement.clientWidth) || 640);
        const w = Math.floor(cssW * dpr), h = Math.floor(cssH * dpr);
        if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);
        const stretch = num(state.settings && state.settings.z_stretch) || 1;
        const strip = plotZ(series, cssW, cssH, stretch);
        if (!strip.points.length) {
            ctx.fillStyle = '#67758f';
            ctx.font = '12px system-ui';
            ctx.fillText('no z-score yet', 12, 32);
            return strip;
        }
        ctx.strokeStyle = 'rgba(255,255,255,.18)';
        ctx.beginPath();
        ctx.moveTo(strip.inner.x, strip.zero);
        ctx.lineTo(strip.inner.x + strip.inner.w, strip.zero);
        ctx.stroke();
        ctx.strokeStyle = 'rgba(251,191,36,.35)';
        [strip.bandTop, strip.bandBottom].forEach((y) => {
            ctx.beginPath();
            ctx.moveTo(strip.inner.x, y);
            ctx.lineTo(strip.inner.x + strip.inner.w, y);
            ctx.stroke();
        });
        ctx.fillStyle = '#fbbf24';
        ctx.font = '11px system-ui';
        ctx.fillText('\u00b1' + fmtNum(stretch, 1) + '\u03c3', strip.inner.x + strip.inner.w - 34, strip.bandTop + 11);
        ctx.strokeStyle = '#8ab4ff';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        strip.points.forEach((point, index) => {
            if (index === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();
        return strip;
    }

    function paint(payload) {
        state.payload = payload || null;
        const p = payload || {};
        state.error = p.ok ? '' : problemLine(p);
        if (!p.ok) {
            say(state.error, 'bad');
            const read = el('syntheticRead');
            if (read) read.textContent = state.error;
            const stats = el('syntheticStats');
            if (stats) stats.innerHTML = '';
            const legsTable = el('syntheticLegsTable');
            if (legsTable) { legsTable.hidden = true; legsTable.innerHTML = ''; }
            const note = el('syntheticNote');
            if (note) note.textContent = '';
            noteOnCanvas('syntheticCanvas', 220, state.error);
            noteOnCanvas('syntheticZCanvas', 58, 'no z-score to draw');
            return;
        }
        say(p.read ? '' : 'composed — no read sentence in the payload', 'ok');
        const read = el('syntheticRead');
        if (read) read.textContent = String(p.read || statsLine(p.stats));
        const stats = el('syntheticStats');
        if (stats) stats.innerHTML = statsHtml(p);
        const note = el('syntheticNote');
        if (note) {
            note.textContent = [String(p.note || ''), String(p.detail || ''),
                                'legs: ' + (Array.isArray(p.legs) ? p.legs.length : 0)].filter(Boolean).join(' \u00b7 ');
        }
        const legsTable = el('syntheticLegsTable');
        if (legsTable) {
            legsTable.innerHTML = '<thead><tr><th>leg</th><th>side</th><th>weight</th><th>points</th>'
                + '<th>carried</th></tr></thead><tbody>' + legsTableHtml(p.legs) + '</tbody>';
        }
        drawComposite(p.series);
        drawZ(p.series);
        /* The composite's newest SAMPLE is the age that matters — the engine can stop writing
           candles while the app stays open. Handed to the shell's freshness store; a page without
           it stamps nothing and nothing breaks. */
        const fresh = win().OFAPFRESH;
        const lastMs = num(p.stats && p.stats.last_ms);
        if (fresh && typeof fresh.stamp === 'function' && lastMs !== null) {
            fresh.stamp('synthetic', { kind: 'candles', lastMs: lastMs,
                                       windowMs: num(p.settings && p.settings.align_ms) || 60000 });
        }
    }

    function chosenWindow() {
        const select = el('syntheticWindow');
        const value = num(select && select.value);
        return value === null ? 0 : value;
    }

    async function refresh() {
        const ident = String(state.selected || '');
        if (!ident) { say('pick or build a synthetic instrument first', 'bad'); return; }
        state.busy = true;
        state.windowMin = chosenWindow();
        if (!state.payload) say('composing ' + ident + '\u2026', 'info');
        try {
            const payload = await get(composeUrl(ident, state.windowMin, 0));
            state.at = Date.now();
            paint(payload);
        } catch (err) {
            const message = 'the compose request failed: ' + errText(err);
            state.error = message;
            say(message, 'bad');
        } finally {
            state.busy = false;
        }
    }

    async function load() {
        try {
            const payload = await get(LIST_URL);
            if (!payload || payload.ok !== true) {
                say(problemLine(payload || {}), 'bad');
                return null;
            }
            state.defs = Array.isArray(payload.definitions) ? payload.definitions : [];
            state.symbols = Array.isArray(payload.symbols) ? payload.symbols : [];
            state.settings = payload.settings || null;
            paintWindowOptions();
            paintDefs();
            if (!state.selected && state.defs.length) {
                state.selected = String(state.defs[0].id || '');
                paintDefs();
                paintBuilder(state.defs[0].legs);
                const name = el('syntheticName');
                if (name) name.value = String(state.defs[0].name || '');
                void refresh();
            } else {
                paintDefs();
            }
            const stamp = el('syntheticStamp');
            if (stamp) {
                stamp.textContent = state.defs.length + ' definition' + (state.defs.length === 1 ? '' : 's')
                    + ' \u00b7 ' + state.symbols.length + ' instrument' + (state.symbols.length === 1 ? '' : 's');
            }
            return payload;
        } catch (err) {
            say('the synthetic instruments could not be read: ' + errText(err), 'bad');
            return null;
        }
    }

    function pickDefinition(ident) {
        state.selected = String(ident || '');
        state.at = 0;
        paintDefs();
        const found = state.defs.filter((d) => String(d.id) === state.selected)[0];
        if (found) paintBuilder(found.legs);
        void refresh();
    }

    function editDefinition(ident) {
        const found = state.defs.filter((d) => String(d.id) === String(ident || ''))[0];
        if (!found) return;
        state.editId = String(found.id || '');
        paintBuilder(found.legs);
        const name = el('syntheticName');
        if (name) name.value = String(found.name || '');
        const kind = el('syntheticKind');
        if (kind) kind.value = String(found.kind || 'ratio');
        const msg = el('syntheticMsg');
        if (msg) msg.textContent = 'editing ' + String(found.name || found.id) + ' — Save replaces it';
    }

    function newDefinition() {
        state.editId = '';
        paintBuilder([{ symbol: '', side: 1, weight: 1 }]);
        const name = el('syntheticName');
        if (name) name.value = '';
        const msg = el('syntheticMsg');
        if (msg) msg.textContent = 'new definition — fill the legs and name it';
    }

    function addLeg() {
        const host = el('syntheticLegs');
        if (!host) return;
        const legs = readLegs(host);
        if (legs.length >= MAX_LEGS) {
            const msg = el('syntheticMsg');
            if (msg) msg.textContent = 'at most ' + MAX_LEGS + ' legs';
            return;
        }
        legs.push({ symbol: '', side: 1, weight: 1 });
        paintBuilder(legs);
    }

    function dropLeg(index) {
        const host = el('syntheticLegs');
        if (!host) return;
        const legs = readLegs(host);
        legs.splice(num(index) === null ? -1 : num(index), 1);
        if (!legs.length) legs.push({ symbol: '', side: 1, weight: 1 });
        paintBuilder(legs);
    }

    async function saveDefinition() {
        const host = el('syntheticLegs');
        const name = el('syntheticName');
        const kind = el('syntheticKind');
        const msg = el('syntheticMsg');
        const body = {
            name: String((name && name.value) || '').trim(),
            kind: String((kind && kind.value) || 'ratio'),
            legs: readLegs(host),
        };
        if (state.editId) body.id = state.editId;
        if (msg) msg.textContent = 'saving\u2026';
        try {
            const answer = await get(LIST_URL, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ definition: body }),
            });
            if (!answer || answer.ok !== true) {
                if (msg) msg.textContent = problemLine(answer || {});
                return;
            }
            state.defs = Array.isArray(answer.definitions) ? answer.definitions : state.defs;
            state.selected = String((answer.definition && answer.definition.id) || state.selected);
            state.editId = state.selected;
            paintDefs();
            if (msg) {
                msg.textContent = (answer.saved ? 'saved' : 'accepted, but not stored — ' + String(answer.detail || ''))
                    + ' \u00b7 composing ' + state.selected;
            }
            state.at = 0;
            void refresh();
        } catch (err) {
            if (msg) msg.textContent = 'the save failed: ' + errText(err);
        }
    }

    /* One delegated click for the whole card (definition rows, the builder's buttons, Refresh) and
       one delegated change for the window select — two page-lifetime listeners instead of one per
       control, and every control's behaviour is visible in the same place. */
    function onClick(ev) {
        const button = ev.target && ev.target.closest ? ev.target.closest('[data-synthetic-act]') : null;
        if (!button) return;
        const act = button.getAttribute('data-synthetic-act');
        const ident = button.getAttribute('data-synthetic-def');
        if (act === 'pick') { pickDefinition(ident); return; }
        if (act === 'edit') { editDefinition(ident); return; }
        if (act === 'drop-leg') { dropLeg(button.getAttribute('data-synthetic-drop')); return; }
        if (act === 'add-leg') { addLeg(); return; }
        if (act === 'new') { newDefinition(); return; }
        if (act === 'save') { void saveDefinition(); return; }
        if (act === 'refresh') { state.at = 0; void refresh(); return; }
        if (act === 'toggle-legs') {
            const table = el('syntheticLegsTable');
            if (table) table.hidden = !table.hidden;
        }
    }

    function onChange(ev) {
        const control = ev.target && ev.target.closest ? ev.target.closest('[data-synthetic-act="window"]') : null;
        if (!control) return;
        state.at = 0;
        void refresh();
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        const panel = card();
        if (panel) panel.addEventListener('click', onClick);
        if (panel) panel.addEventListener('change', onChange);
        /* The panel's own cadence, handed to the app's pause registry: P clears it and resume
           rebuilds it, the suite's rule for every poller. */
        const startPolling = () => {
            const id = setInterval(tick, TICK_MS);
            if (window.OFAPPause && window.OFAPPause.register) window.OFAPPause.register(id, startPolling);
            return id;
        };
        state.timer = startPolling();
    }

    function tick() {
        if (!isActive() || (typeof document !== 'undefined' && document.hidden) || win().OFAP_PAUSED) return;
        const intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        if (state.busy || !state.selected) return;
        const refreshMs = num(state.settings && state.settings.refresh_ms) || 20000;
        if ((Date.now() - state.at) < refreshMs) return;
        void refresh();
    }

    function ensureStyles() {
        if (typeof document === 'undefined' || !document || typeof document.createElement !== 'function') return;
        if (document.getElementById('syntheticStyles')) return;
        const tag = document.createElement('style');
        tag.id = 'syntheticStyles';
        tag.textContent = STYLE;
        if (document.head && typeof document.head.appendChild === 'function') document.head.appendChild(tag);
    }

    function mount() {
        const view = section();
        if (!view || typeof document === 'undefined' || !document) return null;
        const existing = card();
        if (existing) { wire(); return existing; }
        if (typeof document.createElement !== 'function') return null;
        ensureStyles();
        const holder = document.createElement('div');
        holder.innerHTML = TEMPLATE();
        const node = holder.firstElementChild;
        if (!node) return null;
        if (typeof view.appendChild === 'function') view.appendChild(node);
        paintWindowOptions();
        state.pendingKind = 'ratio';
        const kind = el('syntheticKind');
        if (kind) kind.innerHTML = kindOptions('ratio');
        wire();
        return node;
    }

    function watch() {
        if (!mount()) return false;
        void load();
        return true;
    }

    win().OFAPSYNTHETIC = {
        VERSION: VERSION, VIEW: VIEW, LIST_URL: LIST_URL, COMPOSE_URL: COMPOSE_URL, TICK_MS: TICK_MS,
        DASH: DASH, KINDS: KINDS, WINDOWS: WINDOWS, MAX_LEGS: MAX_LEGS,
        esc: esc, num: num, fmtNum: fmtNum, fmtBps: fmtBps, fmtPct: fmtPct, sigmaWords: sigmaWords,
        windowWord: windowWord, statsLine: statsLine, defLine: defLine, defsHtml: defsHtml,
        symbolsHtml: symbolsHtml, kindOptions: kindOptions, legRowHtml: legRowHtml, legsHtml: legsHtml,
        readLegs: readLegs, composeUrl: composeUrl, problemLine: problemLine, statsRows: statsRows,
        statsHtml: statsHtml, legsTableHtml: legsTableHtml, plot: plot, plotZ: plotZ,
        paint: paint, refresh: refresh, load: load, tick: tick, wire: wire, watch: watch,
        mount: mount, pickDefinition: pickDefinition, saveDefinition: saveDefinition,
        state: () => state.payload,
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
