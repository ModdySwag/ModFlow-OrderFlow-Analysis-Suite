/* depth-history.js — the depth-over-time graph: resting size by price and time, with the levels
 * that were pulled or stacked marked on it.
 *
 * The heatmap draws the book as it is, inside a rolling drawn window. This panel is the record
 * behind it: server-side columns (atlas/depth_history.py) folded into buckets, read back over
 * /api/atlas/depth-history/<symbol>. X is time, Y is price, colour is resting size in that price
 * band, and the markers are the level events the store detected between consecutive columns —
 * a filled dot where size was pulled, a hollow ring where it was stacked.
 *
 * What it will not do: invent a chart. An instrument with nothing recorded gets the store's own
 * refusal sentence on the canvas and in the note, and a band with no depth is left unpainted
 * (an empty cell means "no depth reported here", never "zero size").
 *
 * Display rules this module follows, because both are measured defects elsewhere in the app:
 *   * the canvas backing store is sized to its CSS box TIMES devicePixelRatio, and every path is
 *     painted in CSS pixels (a backing store left at CSS size blurs on a 125/150/200% monitor);
 *   * assigning width/height reallocates and blanks the canvas even when it is unchanged, so the
 *     backing store is only touched when the box actually changed.
 *
 * Its one timer is registered with OFAPPause, and a poll only asks while the panel is on screen.
 */
(function () {
    'use strict';

    var VIEW = '.view[data-view="depth-history"]';
    var URL_BASE = '/api/atlas/depth-history';
    var POLL_MS = 5000;                 /* the record fills at book speed; 5 s is plenty to watch it */
    var CSS_H = 260;
    var MAX_MARKERS = 400;
    var WINDOWS = [5, 15, 30, 60];      /* minutes of record to draw */
    var BUCKETS = [1000, 5000, 15000, 60000];
    var KEEPS = [30, 120, 480, 1440];   /* minutes of record to keep (the POSTed retention) */

    var DEPTHH = {
        symbol: '', minutes: 30, bucket_ms: 5000, keep: 30, markers: true,
        timer: null, last: null, polling: 'idle', reads: 0, skipped: 0, refusals: 0, written: 0,
        /* §148 / D2: the note line is shared with the poll's legend, so a confirmation the user
           just caused can hold it for a few seconds and not be wiped by the 5 s repaint. */
        noteUntil: 0
    };

    /* How long a confirmation the user just caused holds the note line (§148 / D2): the poll's
       legend yields for this long so a 5 s repaint cannot wipe the acknowledgement. */
    var NOTE_HOLD_MS = 8000;

    /* ── small helpers ───────────────────────────────────────────────────── */

    function dhNum(n, digits) {
        var v = Number(n);
        if (!isFinite(v)) return '—';
        var abs = Math.abs(v);
        if (abs >= 1e9) return (v / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return (v / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'K';
        return v.toFixed(digits === undefined ? 2 : digits);
    }

    function dhEl(id) {
        if (typeof document === 'undefined' || !document || typeof document.getElementById !== 'function') return null;
        return document.getElementById(id);
    }

    function dhClock(ms) {
        var v = Number(ms);
        if (!isFinite(v) || v <= 0 || typeof Date === 'undefined') return '—';
        var d = new Date(v);
        return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2)
            + ':' + ('0' + d.getSeconds()).slice(-2);
    }

    function dhSpan(ms) {
        var s = Math.max(0, Math.round((Number(ms) || 0) / 1000));
        if (s < 60) return s + ' s';
        var m = Math.floor(s / 60);
        if (m < 60) return m + ' m';
        return Math.floor(m / 60) + ' h ' + ('0' + (m % 60)).slice(-2) + ' m';
    }

    /* ── the pure half (selftested under plain node) ─────────────────────── */

    function dhDpr() {
        var v = (typeof window !== 'undefined' && window.devicePixelRatio) ? Number(window.devicePixelRatio) : 1;
        return v > 0 ? v : 1;
    }

    /* The canvas box: the CSS size is the layout's, the backing store carries the display scale. */
    function dhFit(el, cssH, dpr) {
        var box = Math.max(320, Number((el && (el.clientWidth || (el.parentElement && el.parentElement.clientWidth))) || 0) || 640);
        var scale = Number(dpr) > 0 ? Number(dpr) : 1;
        var height = Number(cssH) > 0 ? Number(cssH) : CSS_H;
        return { cssW: box, cssH: height, dpr: scale, w: Math.floor(box * scale), h: Math.floor(height * scale) };
    }

    /* Slate blue -> orange -> white-hot gold: the app's own depth ramp, re-derived here so the
       panel paints on a page that has not loaded the engine module. */
    function dhStops(t, alpha) {
        var stops = [[0, [55, 80, 122]], [0.45, [201, 106, 31]], [0.78, [255, 182, 77]], [1, [255, 242, 196]]];
        var x = Math.min(1, Math.max(0, Number(t) || 0));
        for (var i = 1; i < stops.length; i += 1) {
            if (x <= stops[i][0]) {
                var a = stops[i - 1], b = stops[i];
                var k = b[0] === a[0] ? 0 : (x - a[0]) / (b[0] - a[0]);
                return 'rgba(' + Math.round(a[1][0] + (b[1][0] - a[1][0]) * k) + ','
                    + Math.round(a[1][1] + (b[1][1] - a[1][1]) * k) + ','
                    + Math.round(a[1][2] + (b[1][2] - a[1][2]) * k) + ',' + alpha + ')';
            }
        }
        return 'rgba(255,242,196,' + alpha + ')';
    }

    function dhColour(value, ceiling) {
        var size = Number(value) || 0;
        if (!(size > 0)) return '';
        var top = Number(ceiling) > 0 ? Number(ceiling) : 1;
        /* log scale: a level ten times the size is not ten times the ink, it is a shade brighter */
        var t = Math.min(1, Math.max(0, Math.log1p(size) / Math.log1p(Math.max(top, 1))));
        var engine = (typeof window !== 'undefined' && window.OFX && window.OFX.math
            && typeof window.OFX.math.heatColor01 === 'function') ? window.OFX.math : null;
        if (engine) {
            var out = engine.heatColor01(t, 'classic');
            if (typeof out === 'string' && out) return out;
            if (out && out.length >= 3) {
                return 'rgba(' + out[0] + ',' + out[1] + ',' + out[2] + ',0.92)';
            }
        }
        return dhStops(t, 0.92);
    }

    /* The band a price falls into, or -1 for a price the window's bands do not cover. */
    function dhBandRow(price, bands) {
        var list = bands || [];
        if (list.length < 2) return -1;
        var low = Number(list[0]);
        var high = Number(list[list.length - 1]);
        var p = Number(price);
        if (!isFinite(p) || !(high > low)) return -1;
        var width = (high - low) / (list.length - 1);
        var idx = Math.floor((p - low) / width);
        if (idx < 0) return -1;
        return Math.min(list.length - 2, idx);
    }

    /* The colour ceiling: the biggest band total in the window, so the ramp uses its whole range. */
    function dhSizeMax(payload) {
        var buckets = (payload && payload.buckets) || [];
        var top = 0;
        for (var i = 0; i < buckets.length; i += 1) {
            var bands = buckets[i].bands || [];
            for (var j = 0; j < bands.length; j += 1) {
                var total = (Number(bands[j].bid) || 0) + (Number(bands[j].ask) || 0);
                if (total > top) top = total;
            }
        }
        return top > 0 ? top : 1;
    }

    /* Where each event marker belongs on the strip: which bucket column, which price band. */
    function dhMarkerCells(payload, limit) {
        var out = [];
        var events = (payload && payload.events) || [];
        var buckets = (payload && payload.buckets) || [];
        var bands = (payload && payload.bands) || [];
        if (!events.length || !buckets.length || bands.length < 2) return out;
        var width = Number(payload.bucket_ms) > 0 ? Number(payload.bucket_ms) : 5000;
        var cap = Number(limit) > 0 ? Number(limit) : MAX_MARKERS;
        /* A cell's own stamp -> its slot in the bucket ARRAY. The array skips the cells the store
           never recorded, so an offset on the time grid is NOT an array index: computed from the
           grid, a marker landed one cell per gap away from the depth it belongs to (T6-F05). */
        var slot = {};
        for (var b = 0; b < buckets.length; b += 1) {
            var own = Number(buckets[b].ts_ms) || 0;
            if (!(own in slot)) slot[own] = b;
        }
        /* Walk newest-first, so a cap drops the OLDEST markers: the newest are the ones a live
           strip is watched for. The list is reversed back into drawing order before returning. */
        for (var i = events.length - 1; i >= 0 && out.length < cap; i -= 1) {
            var e = events[i] || {};
            var cell = Math.floor(Number(e.ts_ms) / width) * width;
            var column = slot[cell];
            if (!(column >= 0)) continue;              /* its own cell was never recorded */
            var row = dhBandRow(e.price, bands);
            if (row < 0) continue;                                     /* a price the bands miss */
            out.push({ kind: String(e.kind || ''), pull: String(e.kind) === 'pull',
                price: Number(e.price) || 0, size: Number(e.size) || 0, column: column, band: row });
        }
        out.reverse();
        return out;
    }

    /* The refusal sentence, or '' when there is something to draw. */
    function dhRefusal(payload) {
        if (!payload) return 'no depth record to read yet';
        if (payload.ok === false) return String(payload.detail || 'no depth recorded for this instrument yet');
        if (!payload.buckets || !payload.buckets.length) {
            return String(payload.detail || 'no depth columns in this window yet — widen it or wait a minute');
        }
        return '';
    }

    /* The panel's head numbers, all read off the payload (never recomputed from nothing). */
    function dhSummary(payload) {
        var p = payload || {};
        var events = p.events || [];
        var sums = { pulls: 0, adds: 0, pull_size: 0, add_size: 0, top: null };
        for (var i = 0; i < events.length; i += 1) {
            var e = events[i] || {};
            if (String(e.kind) === 'pull') { sums.pulls += 1; sums.pull_size += Number(e.size) || 0; }
            else if (String(e.kind) === 'add') { sums.adds += 1; sums.add_size += Number(e.size) || 0; }
            if (!sums.top || (Number(e.size) || 0) > (Number(sums.top.size) || 0)) sums.top = e;
        }
        var last = (p.buckets && p.buckets.length) ? p.buckets[p.buckets.length - 1] : null;
        sums.buckets = (p.buckets || []).length;
        sums.columns = (p.retained && p.retained.columns) || 0;
        sums.levels = (p.retained && p.retained.levels) || 0;
        sums.span_ms = Number(p.span_ms) || 0;
        sums.gap_ms = ((p.gaps && p.gaps.missing_ms) || 0);
        sums.covered = (p.gaps && p.gaps.covered_pct !== undefined) ? p.gaps.covered_pct : 100;
        sums.state = (p.staleness && p.staleness.state) || 'unknown';
        sums.state_text = (p.staleness && p.staleness.text) || '';
        sums.total_bid = last ? Number(last.total_bid) || 0 : 0;
        sums.total_ask = last ? Number(last.total_ask) || 0 : 0;
        sums.biggest = last ? last.biggest : null;
        sums.from_ms = Number(p.from_ms) || 0;
        sums.to_ms = Number(p.to_ms) || 0;
        sums.have_from_ms = Number(p.have_from_ms) || 0;
        return sums;
    }

    function dhUrl(symbol, opts) {
        var o = opts || {};
        var parts = [];
        if (Number(o.minutes) > 0) parts.push('minutes=' + Number(o.minutes));
        if (Number(o.bucket_ms) > 0) parts.push('bucket_ms=' + Number(o.bucket_ms));
        if (o.events === false) parts.push('events=0');
        return URL_BASE + '/' + encodeURIComponent(String(symbol || '').toUpperCase())
            + (parts.length ? '?' + parts.join('&') : '');
    }

    function dhLegendText(payload) {
        var s = dhSummary(payload);
        if (!s.buckets) return '';
        return s.buckets + ' buckets · ' + dhSpan(s.span_ms) + ' of record · '
            + s.columns + ' columns kept · ' + s.pulls + ' pulled / ' + s.adds + ' stacked'
            + (s.gap_ms > 0 ? ' · ' + dhSpan(s.gap_ms) + ' missing' : '');
    }

    /* ── transport ───────────────────────────────────────────────────────── */

    function dhGet(path) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path);
        if (typeof fetch !== 'function') return Promise.resolve(null);
        return fetch(path, { headers: { accept: 'application/json' } }).then(function (r) { return r.json(); });
    }

    function dhPost(path, body) {
        if (typeof fetch !== 'function') return Promise.resolve(null);
        return fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); });
    }

    /* ── the strip ───────────────────────────────────────────────────────── */

    function dhPaintMessage(ctx, fit, text) {
        ctx.fillStyle = '#67758f';
        ctx.font = '13px system-ui';
        ctx.fillText(String(text || ''), 14, 30);
        return fit;
    }

    function dhDraw(payload) {
        var el = dhEl('depthHistoryCanvas');
        if (!el || typeof el.getContext !== 'function') return null;
        var dpr = dhDpr();
        var fit = dhFit(el, CSS_H, dpr);
        if (el.style) { el.style.width = '100%'; el.style.height = CSS_H + 'px'; }
        if (el.width !== fit.w || el.height !== fit.h) { el.width = fit.w; el.height = fit.h; }
        var ctx = el.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, fit.cssW, fit.cssH);

        var refusal = dhRefusal(payload);
        if (refusal) return dhPaintMessage(ctx, fit, refusal);

        var buckets = payload.buckets || [];
        var bands = payload.bands || [];
        var rows = bands.length - 1;
        var padL = 64, padR = 10, padT = 14, padB = 22;
        var plotW = Math.max(40, fit.cssW - padL - padR);
        var plotH = Math.max(40, fit.cssH - padT - padB);
        var cellW = plotW / Math.max(1, buckets.length);
        var cellH = plotH / Math.max(1, rows);
        var ceiling = dhSizeMax(payload);

        for (var c = 0; c < buckets.length; c += 1) {
            var rowBands = buckets[c].bands || [];
            for (var r = 0; r < rows; r += 1) {
                var band = rowBands[r];
                if (!band) continue;
                var bid = Number(band.bid) || 0;
                var ask = Number(band.ask) || 0;
                var total = bid + ask;
                if (!(total > 0)) continue;                       /* no depth reported: leave it blank */
                var y = padT + plotH - (r + 1) * cellH;           /* the lowest band sits at the bottom */
                var x = padL + c * cellW;
                var cw = Math.max(1, Math.ceil(cellW));
                var ch = Math.max(1, Math.ceil(cellH));
                ctx.fillStyle = dhColour(total, ceiling);
                ctx.fillRect(x, y, cw, ch);
                /* which side is resting there: the bid share along the top, the ask share along the
                   bottom of the cell. A band is a price range, not a side. */
                ctx.fillStyle = 'rgba(74,222,128,.6)';
                ctx.fillRect(x, y, Math.max(0, (bid / total) * cw), Math.max(1, ch * 0.16));
                ctx.fillStyle = 'rgba(248,113,113,.6)';
                ctx.fillRect(x + cw - Math.max(0, (ask / total) * cw), y + ch - Math.max(1, ch * 0.16),
                    Math.max(0, (ask / total) * cw), Math.max(1, ch * 0.16));
            }
        }

        if (DEPTHH.markers) {
            var markers = dhMarkerCells(payload);
            var biggest = 1;
            for (var m = 0; m < markers.length; m += 1) biggest = Math.max(biggest, markers[m].size);
            for (var i = 0; i < markers.length; i += 1) {
                var mk = markers[i];
                var mx = padL + (mk.column + 0.5) * cellW;
                var my = padT + plotH - (mk.band + 0.5) * cellH;
                var rad = 1.6 + 2.6 * Math.min(1, Math.sqrt(mk.size / biggest));
                ctx.beginPath();
                ctx.arc(mx, my, rad, 0, Math.PI * 2);
                if (mk.pull) { ctx.fillStyle = 'rgba(248,113,113,.95)'; ctx.fill(); }
                else { ctx.strokeStyle = 'rgba(74,222,128,.95)'; ctx.lineWidth = 1.4; ctx.stroke(); }
            }
        }

        ctx.font = '10px system-ui';
        ctx.fillStyle = '#67758f';
        ctx.fillText(dhNum(bands[bands.length - 1], 2), 6, padT + 8);
        ctx.fillText(dhNum(bands[Math.floor(rows / 2)], 2), 6, padT + plotH / 2 + 3);
        ctx.fillText(dhNum(bands[0], 2), 6, padT + plotH - 2);
        ctx.fillText('price', 6, padT - 2);
        ctx.fillText(dhClock(buckets[0].ts_ms), padL, fit.cssH - 6);
        var midLabel = dhClock(buckets[Math.floor(buckets.length / 2)].ts_ms);
        ctx.fillText(midLabel, padL + plotW / 2 - ctx.measureText(midLabel).width / 2, fit.cssH - 6);
        var lastLabel = dhClock(buckets[buckets.length - 1].ts_ms);
        ctx.fillText(lastLabel, padL + plotW - ctx.measureText(lastLabel).width, fit.cssH - 6);
        return fit;
    }

    /* ── the panel ───────────────────────────────────────────────────────── */

    var STYLE = '.dh-wrap { display: flex; flex-direction: column; gap: 8px; }'
        + '.dh-controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; font-size: 12px; }'
        + '.dh-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }'
        + '.dh-kpi { background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06); border-radius: 8px; padding: 7px 10px; }'
        + '.dh-kpi .lbl { font-size: 11px; opacity: .65; display: block; }'
        + '.dh-kpi .val { font-size: 15px; font-weight: 600; }'
        + '.dh-kpi .sub { font-size: 11px; opacity: .55; }'
        + '.dh-bid { color: #4ade80; } .dh-ask { color: #f87171; }'
        + '.dh-legend { display: flex; gap: 14px; font-size: 11.5px; opacity: .7; }'
        + '.dh-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }'
        + '.dh-tape { font-size: 12px; }'
        + '.dh-tape .row { display: flex; gap: 10px; opacity: .85; }'
        + '.dh-tape .pull { color: #f87171; } .dh-tape .add { color: #4ade80; }';

    function dhOption(value, label, selected) {
        return '<option value="' + value + '"' + (selected ? ' selected' : '') + '>' + label + '</option>';
    }

    function dhSelect(id, title, pairs, current) {
        var html = '<select id="' + id + '" title="' + title + '">';
        for (var i = 0; i < pairs.length; i += 1) {
            html += dhOption(pairs[i][0], pairs[i][1], Number(pairs[i][0]) === Number(current));
        }
        return html + '</select>';
    }

    function dhMount() {
        if (typeof document === 'undefined' || !document || typeof document.querySelector !== 'function') return null;
        var view = document.querySelector(VIEW);
        if (!view || dhEl('depthHistoryCard')) return null;
        if (document.head && typeof document.head.appendChild === 'function') {
            var style = document.createElement('style');
            style.id = 'depthHistoryStyles';
            style.textContent = STYLE;
            document.head.appendChild(style);
        }
        var winPairs = WINDOWS.map(function (m) { return [m, 'last ' + m + ' min']; });
        var bucketPairs = BUCKETS.map(function (b) { return [b, (b / 1000) + ' s buckets']; });
        var keepPairs = KEEPS.map(function (k) { return [k, k < 60 ? (k + ' min kept') : ((k / 60) + ' h kept')]; });
        var card = document.createElement('div');
        card.className = 'card';
        card.id = 'depthHistoryCard';
        card.style.marginTop = '12px';
        card.innerHTML = '<div class="card-head">'
            + '<span class="card-title">Depth over time <span class="dim" style="font-weight:400">· resting size by price and time</span></span>'
            + '<div class="spacer"></div>'
            + '<span class="dim" id="depthHistoryStamp"></span>'
            + '<button class="btn small" id="depthHistoryRefresh" title="Read the depth record again now">Refresh</button>'
            + '<button class="btn small" id="depthHistoryClear" title="Forget the recorded depth for this instrument">Clear</button>'
            + '</div>'
            + '<div class="card-body dh-wrap">'
            + '<div class="dh-controls">'
            + '<label>Window ' + dhSelect('depthHistoryWindow',
                'How much of the recorded depth to draw', winPairs, DEPTHH.minutes) + '</label>'
            + '<label>Buckets ' + dhSelect('depthHistoryBucket',
                'Bucket width — how much book time one column of the strip holds', bucketPairs, DEPTHH.bucket_ms) + '</label>'
            + '<label title="How much depth history the engine keeps in memory. A shorter window frees it at once. These are presets — Settings ▸ Depth history takes any value from 1 to 1440.">Keep '
            + dhSelect('depthHistoryKeep', 'Recorded depth to keep (minutes), stored by the engine',
                keepPairs, DEPTHH.keep) + '</label>'
            + '<label title="Draw the levels that were pulled (filled dot) or stacked (ring) between columns.">'
            + '<input type="checkbox" id="depthHistoryMarkers"' + (DEPTHH.markers ? ' checked' : '') + '> markers</label>'
            + '<span class="dim" id="depthHistoryNote"></span>'
            + '</div>'
            + '<div class="dh-kpis" id="depthHistoryKpis"><div class="dim">reading the depth record…</div></div>'
            + '<canvas id="depthHistoryCanvas" height="260" title="Resting depth by price over time: brighter cells are bigger levels, the green edge is the bid side, the red edge the ask side, dots are pulled levels and rings are stacked ones."></canvas>'
            + '<div class="dh-legend">'
            + '<span><span class="dh-swatch" style="background:#37507a"></span>thin</span>'
            + '<span><span class="dh-swatch" style="background:#ffb24d"></span>heavy</span>'
            + '<span><span class="dh-swatch" style="background:#f87171;border-radius:50%"></span>pulled level</span>'
            + '<span><span class="dh-swatch" style="background:transparent;border:1.5px solid #4ade80;border-radius:50%"></span>stacked level</span>'
            + '<span class="dim" id="depthHistoryLegendText"></span>'
            + '</div>'
            + '<div class="dh-tape" id="depthHistoryTape"></div>'
            + '</div>';
        view.appendChild(card);
        return card;
    }

    function dhKpis(payload) {
        var el = dhEl('depthHistoryKpis');
        if (!el) return;
        var s = dhSummary(payload);
        if (dhRefusal(payload)) {
            el.innerHTML = '<div class="dh-kpi"><span class="lbl">record</span>'
                + '<span class="val">—</span><span class="sub">nothing to read yet</span></div>';
            return;
        }
        el.innerHTML = '<div class="dh-kpi" title="The newest bucket: resting bid size across the drawn price bands.">'
            + '<span class="lbl">Resting bid</span><span class="val dh-bid">' + dhNum(s.total_bid) + '</span>'
            + '<span class="sub">newest bucket</span></div>'
            + '<div class="dh-kpi" title="The newest bucket: resting ask size across the drawn price bands.">'
            + '<span class="lbl">Resting ask</span><span class="val dh-ask">' + dhNum(s.total_ask) + '</span>'
            + '<span class="sub">newest bucket</span></div>'
            + '<div class="dh-kpi" title="The single biggest resting level in the newest bucket.">'
            + '<span class="lbl">Biggest level</span><span class="val">'
            + (s.biggest ? dhNum(s.biggest.size) : '—') + '</span><span class="sub">'
            + (s.biggest ? dhNum(s.biggest.price, 2) + ' · ' + s.biggest.side : 'none in view') + '</span></div>'
            + '<div class="dh-kpi" title="Levels that lost at least the configured share of their size between two columns.">'
            + '<span class="lbl">Pulled</span><span class="val dh-ask">' + s.pulls + '</span>'
            + '<span class="sub">' + dhNum(s.pull_size) + ' lots withdrawn</span></div>'
            + '<div class="dh-kpi" title="Levels that grew by at least the configured share between two columns.">'
            + '<span class="lbl">Stacked</span><span class="val dh-bid">' + s.adds + '</span>'
            + '<span class="sub">' + dhNum(s.add_size) + ' lots added</span></div>'
            + '<div class="dh-kpi" title="Where the record has holes: a stopped engine, a dropped feed.">'
            + '<span class="lbl">Coverage</span><span class="val">' + Math.round(s.covered) + '%</span>'
            + '<span class="sub">' + (s.gap_ms > 0 ? dhSpan(s.gap_ms) + ' missing' : 'no gaps') + '</span></div>'
            + '<div class="dh-kpi" title="How much depth history the engine is holding for this instrument.">'
            + '<span class="lbl">Record held</span><span class="val">' + dhSpan(s.span_ms) + '</span>'
            + '<span class="sub">' + s.columns + ' columns · ' + dhNum(s.levels, 0) + ' levels</span></div>';
    }

    function dhTape(payload) {
        var el = dhEl('depthHistoryTape');
        if (!el) return;
        var events = (payload && payload.events) || [];
        if (!events.length) {
            el.innerHTML = '<span class="dim">no level was pulled or stacked by the configured shares in this window</span>';
            return;
        }
        var rows = events.slice().sort(function (a, b) { return (Number(b.size) || 0) - (Number(a.size) || 0); }).slice(0, 8);
        var html = '';
        for (var i = 0; i < rows.length; i += 1) {
            var e = rows[i];
            html += '<div class="row"><span class="' + (String(e.kind) === 'pull' ? 'pull' : 'add') + '">'
                + (String(e.kind) === 'pull' ? 'pulled' : 'stacked') + '</span><span>' + dhNum(e.size)
                + '</span><span class="dim">@ ' + dhNum(e.price, 2) + ' ' + String(e.side || '')
                /* §148 T6-F9: `|| 0` turned the server's absent share into "0%" — a reading of
                   its own. A level that was not there before says so. */
                + ' · ' + (e.pct === null || typeof e.pct === 'undefined'
                    ? 'new level' : Math.round(Number(e.pct) * 100) + '%')
                + ' · ' + dhClock(e.ts_ms) + '</span></div>';
        }
        el.innerHTML = html;
    }

    /* §148 / D2: `hold` (ms) keeps the poll's legend off this line until it expires — a retention
       confirmation used to vanish on the next 5 s repaint, in the same breath as it was shown. */
    function dhNote(text, hold) {
        var el = dhEl('depthHistoryNote');
        if (Number(hold) > 0) DEPTHH.noteUntil = Date.now() + Number(hold);
        if (el) el.textContent = String(text || '');
    }

    function dhNoteHeld() {
        return Number(DEPTHH.noteUntil || 0) > Date.now();
    }

    /* The poll's own line. It yields to a held confirmation and takes the line back afterwards. */
    function dhNoteLegend(text) {
        if (dhNoteHeld()) return;
        dhNote(text);
    }

    function dhApply(payload) {
        if (!payload) return null;
        DEPTHH.last = payload;
        DEPTHH.symbol = String(payload.symbol || DEPTHH.symbol || '');
        if (payload.settings && Number(payload.settings.retention_minutes) > 0) {
            DEPTHH.keep = Number(payload.settings.retention_minutes);
        }
        var refusal = dhRefusal(payload);
        if (refusal) DEPTHH.refusals += 1;
        var stamp = dhEl('depthHistoryStamp');
        if (stamp) {
            stamp.textContent = 'read ' + dhClock(Date.now()) + (payload.staleness ? ' · ' + payload.staleness.state : '');
            stamp.title = (payload.staleness && payload.staleness.text) || '';
        }
        dhNoteLegend(dhLegendText(payload));
        var legend = dhEl('depthHistoryLegendText');
        if (legend) legend.textContent = 'bucket ' + dhSpan(payload.bucket_ms) + ' · kept ' + DEPTHH.keep + ' min';
        dhKpis(payload);
        dhTape(payload);
        dhDraw(payload);
        var keep = dhEl('depthHistoryKeep');
        if (keep && Number(keep.value) !== DEPTHH.keep) keep.value = String(DEPTHH.keep);
        return payload;
    }

    function dhSymbol() {
        var box = dhEl('symbolSelect');
        var fromBox = box && box.value ? String(box.value) : '';
        if (fromBox) return fromBox.toUpperCase();
        if (typeof S !== 'undefined' && S && S.symbol) return String(S.symbol).toUpperCase();
        return '';
    }

    function dhPoll(force) {
        if (!force && !dhOnScreen()) { DEPTHH.skipped += 1; return Promise.resolve(null); }
        var symbol = dhSymbol();
        if (!symbol) { dhNote('pick an instrument — the depth record follows the symbol box'); return Promise.resolve(null); }
        var url = dhUrl(symbol, { minutes: DEPTHH.minutes, bucket_ms: DEPTHH.bucket_ms,
            events: DEPTHH.markers });
        /* §148 T6-F8: the counter was kept and never compared — a slow answer for the OLD instrument
           could repaint the strip while the note named the new one (the heatmap's D-10 guard, the
           same shape). Only the newest ask, for the instrument it asked about, may paint. */
        var seq = (DEPTHH.reads += 1);
        return dhGet(url).then(function (data) {
            if (!data) {
                dhNote('the depth record answered nothing — the strip still shows the last read', NOTE_HOLD_MS);
                return null;
            }
            if (seq !== DEPTHH.reads) return null;
            if (String(data.symbol || '').toUpperCase() !== symbol) return null;
            return dhApply(data);
        }).catch(function () {
            dhNote('the depth record did not answer — the strip still shows the last read', NOTE_HOLD_MS);
            return null;
        });
    }

    function dhSetRetention(minutes) {
        var wanted = Number(minutes) > 0 ? Number(minutes) : DEPTHH.keep;
        return dhPost(URL_BASE + '/retention', { retention_minutes: wanted }).then(function (res) {
            if (!res || res.ok === false) {
                dhNote('the engine refused the retention change: ' + ((res && res.detail) || 'no answer'), NOTE_HOLD_MS);
                return null;
            }
            DEPTHH.written += 1;
            DEPTHH.keep = Number((res.settings && res.settings.retention_minutes) || wanted);
            dhNote('keeping ' + DEPTHH.keep + ' min of depth', NOTE_HOLD_MS);
            return res;
        }).catch(function () {
            dhNote('the retention change did not reach the engine', NOTE_HOLD_MS);
            return null;
        });
    }

    function dhClear() {
        var symbol = dhSymbol();
        return dhPost(URL_BASE + '/clear', { symbol: symbol }).then(function () {
            DEPTHH.last = null;
            return dhPoll(true);
        }).then(function (data) {
            /* said after the re-read, so the message is not immediately overwritten by the legend —
               and held, so the next poll cannot overwrite it either (§148 / D2) */
            dhNote(symbol ? ('forgot the depth recorded for ' + symbol) : 'forgot every depth record',
                   NOTE_HOLD_MS);
            return data;
        }).catch(function () {
            dhNote('the clear did not reach the engine', NOTE_HOLD_MS);
            return null;
        });
    }

    /* On screen means the section is the active view, or it lives in a floating frame. A parked
       section does not poll — the record is server-side, so it loses nothing by waiting. */
    function dhOnScreen() {
        if (typeof document === 'undefined' || !document || typeof document.querySelector !== 'function') return false;
        var section = document.querySelector(VIEW);
        if (!section) return false;
        if (typeof section.closest === 'function' && section.closest('.widget-frame')) return true;
        if (section.classList && typeof section.classList.contains === 'function') {
            return section.classList.contains('active');
        }
        return true;
    }

    function dhReadApply() {
        return dhPoll(true);
    }

    /* One delegated listener pair on the section: the controls are found by id inside the handler,
       so a re-render of the card cannot leave a listener pointing at a dead node. */
    function dhClick(ev) {
        var target = ev && ev.target ? ev.target : {};
        var id = String(target.id || '');
        if (id === 'depthHistoryRefresh') { dhReadApply(); return; }
        if (id === 'depthHistoryClear') { dhClear(); return; }
    }

    function dhChange(ev) {
        var target = ev && ev.target ? ev.target : {};
        var id = String(target.id || '');
        var value = target.value;
        if (id === 'depthHistoryWindow') { DEPTHH.minutes = Number(value) || DEPTHH.minutes; dhReadApply(); return; }
        if (id === 'depthHistoryBucket') { DEPTHH.bucket_ms = Number(value) || DEPTHH.bucket_ms; dhReadApply(); return; }
        if (id === 'depthHistoryKeep') { dhSetRetention(value); return; }
        if (id === 'depthHistoryMarkers') {
            DEPTHH.markers = !!target.checked;
            if (DEPTHH.last) dhDraw(DEPTHH.last);
            dhReadApply();
        }
    }

    function dhStart() {
        if (DEPTHH.timer) return DEPTHH.timer;
        DEPTHH.timer = setInterval(function () { dhPoll(false); }, POLL_MS);
        /* the panel's one timer is on the pause registry, so P holds it with every other refresh */
        if (typeof window !== 'undefined' && window.OFAPPause && window.OFAPPause.register) {
            window.OFAPPause.register(DEPTHH.timer, dhStart);
        }
        DEPTHH.polling = 'timer';
        return DEPTHH.timer;
    }

    function dhStop() {
        if (DEPTHH.timer) {
            clearInterval(DEPTHH.timer);
            if (typeof window !== 'undefined' && window.OFAPPause && window.OFAPPause.unregister) {
                window.OFAPPause.unregister(DEPTHH.timer);
            }
            DEPTHH.timer = null;
            DEPTHH.polling = 'idle';
        }
        if (typeof document !== 'undefined' && document && typeof document.querySelector === 'function') {
            var section = document.querySelector(VIEW);
            if (section && typeof section.removeEventListener === 'function') {
                section.removeEventListener('click', dhClick);
                section.removeEventListener('change', dhChange);
            }
            /* the boot hook comes off with the rest, so a stopped panel leaves nothing registered */
            if (typeof document.removeEventListener === 'function') {
                document.removeEventListener('DOMContentLoaded', dhWire);
            }
        }
    }

    function dhWire() {
        if (typeof document === 'undefined' || !document || typeof document.querySelector !== 'function') return null;
        var section = document.querySelector(VIEW);
        if (!section || typeof section.addEventListener !== 'function') return null;
        section.addEventListener('click', dhClick);
        section.addEventListener('change', dhChange);
        dhMount();
        dhStart();
        dhReadApply();
        return section;
    }

    var OFAPDEPTHH = {
        DEPTHH: DEPTHH, VIEW: VIEW, URL_BASE: URL_BASE, POLL_MS: POLL_MS, CSS_H: CSS_H,
        WINDOWS: WINDOWS, BUCKETS: BUCKETS, KEEPS: KEEPS,
        num: dhNum, clock: dhClock, span: dhSpan, dpr: dhDpr, fit: dhFit,
        colour: dhColour, stops: dhStops, bandRow: dhBandRow, sizeMax: dhSizeMax,
        markerCells: dhMarkerCells, refusal: dhRefusal, summary: dhSummary, url: dhUrl,
        legendText: dhLegendText, mount: dhMount, apply: dhApply, draw: dhDraw, poll: dhPoll,
        symbol: dhSymbol, onScreen: dhOnScreen, start: dhStart, stop: dhStop, wire: dhWire,
        setRetention: dhSetRetention, clear: dhClear, note: dhNote
    };

    if (typeof window !== 'undefined') window.OFAPDEPTHH = OFAPDEPTHH;
    if (document && typeof document.addEventListener === 'function') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', dhWire);
        else dhWire();
    }
})();
