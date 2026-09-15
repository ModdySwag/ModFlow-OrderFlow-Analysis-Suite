/* heatmap-pro.js - the interactive layer over the depth heatmap.
 *
 * The map already draws resting liquidity, executed aggression and spoof/stack events. What a desk
 * adds on top is interrogation: zoom the window, box the part that matters, read the numbers under
 * the cursor, pin a level, and get the selection out as a file. This module never re-implements
 * the map - a zoom drives the map's own window control so the reload goes through the same
 * pipeline - and paints only what the map does not own: readout, selection, markers.
 */
(function () {
    'use strict';

    const P = { last: null, sel: null, mode: 'inspect', markers: [], hud: null, dragging: false, symbol: null };

    const $ = (s) => document.querySelector(s);
    const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    /* Buckets arrive as epoch milliseconds; a desk reads clock time, not a 13-digit number. */
    const fmtBucket = (b) => {
        if (b == null) return '';
        if (typeof b === 'number' && b > 1e11) {
            const d = new Date(b);
            return d.toTimeString().slice(0, 8);
        }
        return String(b);
    };

    /* Canvas colours cannot be `var(--of-...)`; read the token instead of hard-coding a colour the
       light and contrast themes would leave behind. */
    const tok = (name, fallback) => {
        try {
            const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
            return v || fallback;
        } catch (e) { return fallback; }
    };
    /* The theme declares trace as an rgb triple, so build the colour from the triple. */
    const traceInk = () => {
        const t = tok('--of-trace-rgb', '') || tok('--of-cyan-rgb', '');
        return t ? 'rgb(' + t + ')' : 'rgb(140,200,255)';
    };

    const stage = () => document.getElementById('heatmapCanvas');
    const view = () => document.querySelector('.view[data-view="heatmap"]');
    const active = () => !!(view() && view().classList.contains('active'));
    const overlay = () => document.querySelector('[data-hm-pro-overlay]');
    const cols = () => parseInt((($('#hmColumns') || {}).value) || 240, 10);
    const rows = () => parseInt((($('#hmRows') || {}).value) || 200, 10);

    /* The instrument, found without reaching into another module's scope: the app's own state is
       not global, so ask the source of truth the app itself uses, then fall back to the page. */
    async function symbol() {
        if (P.symbol) return P.symbol;
        try {
            /* What the engine is streaming is the truth; bootstrap only names a default, and the
               first version of this picked that default and read an empty map for a symbol the
               engine was not feeding at all. */
            const st = await api('/api/control/engine/status');
            const live = st && (st.symbols || (st.engine && st.engine.symbols));
            if (live && live.length) P.symbol = live[0];
        } catch (e) { /* fall through */ }
        if (!P.symbol) {
            try {
                const b = await api('/api/control/bootstrap');
                P.symbol = (b && (b.symbol || (b.state && b.state.symbol) || (b.config && b.config.symbol))) || null;
            } catch (e) { /* fall through to the DOM */ }
        }
        if (!P.symbol) {
            const el = document.querySelector('[data-symbol]') || document.getElementById('searchInput');
            P.symbol = (el && (el.dataset.symbol || el.value)) || '';
        }
        return P.symbol;
    }

    /* The map's own numbers, on the same params, so the overlay can never disagree with the pixels. */
    async function pull(force) {
        if (window.OFAPINTENT && OFAPINTENT.held('heatmap') && !force) {
            /* A selection or a drag is in progress: take the data, but do not repaint over the
               gesture. The arbiter applies this the moment the surface is free again. */
            return OFAPINTENT.deferKeyed('heatmap', 'pull', () => pull(true));
        }
        if (P.busy && !force) return;
        P.busy = true;
        try {
            const sym = await symbol();
            if (!sym) return;
            if (P.markersFor !== sym) { P.markersFor = sym; P.markers = []; void markersLoad(sym); }
            P.last = await api('/api/atlas/heatmap/' + encodeURIComponent(sym) + '?columns=' + cols() + '&rows=' + rows());
            if ((!P.last || !(P.last.buckets || []).length) && !P.reResolved) {
                P.reResolved = true;                 // one retry, then accept the empty map
                P.symbol = null;
                const again = await symbol();
                if (again && again !== sym) {
                    P.last = await api('/api/atlas/heatmap/' + encodeURIComponent(again) + '?columns=' + cols() + '&rows=' + rows());
                }
            }
            draw();
            hud();
        } catch (e) { /* the map's load path reports feed trouble */ }
        finally { P.busy = false; }
    }

    /* ── geometry: same insets as the map's own draw ─────────────────────────────────────── */
    function geom() {
        const c = stage();
        if (!c) return null;
        const r = c.getBoundingClientRect();
        const nc = (P.last && P.last.buckets && P.last.buckets.length) || 1;
        const nr = (P.last && P.last.prices && P.last.prices.length) || 1;
        /* The map owns its insets (atlas.js's HEAT_INSET): reading them off the window keeps this
           overlay on exactly the same plot box, with the old numbers only as a fallback. */
        const inset = window.OFAPHEAT_INSET || { right: 74, bottom: 22 };
        const plotW = r.width - inset.right, plotH = r.height - inset.bottom;
        return { rect: r, w: r.width, h: r.height, plotW: plotW, plotH: plotH,
                 cw: plotW / nc, chh: plotH / nr, nc: nc, nr: nr };
    }

    function cellAt(ev) {
        const g = geom();
        if (!g || !P.last) return null;
        const x = ev.clientX - g.rect.left, y = ev.clientY - g.rect.top;
        if (x < 0 || y < 0 || x > g.plotW || y > g.plotH) return null;
        const ci = Math.min(g.nc - 1, Math.max(0, Math.floor(x / g.cw)));
        const ri = Math.min(g.nr - 1, Math.max(0, g.nr - 1 - Math.floor(y / g.chh)));
        const vals = P.last.values || [];
        const row = vals[ri] || [];
        const v = row[ci] || 0;
        const prev = ci > 0 ? (row[ci - 1] || 0) : 0;
        let colSum = 0;
        for (const rr of vals) colSum += (rr[ci] || 0);
        return {
            ci: ci, ri: ri, x: x, y: y,
            price: (P.last.prices || [])[ri], bucket: (P.last.buckets || [])[ci],
            size: v, delta_depth: v - prev,
            row_depth: row.reduce((s, n) => s + (n || 0), 0), bucket_depth: colSum,
            traded: ((P.last.traded || [])[ri] || [])[ci] || 0,
            events: ((P.last.events || [])[ri] || [])[ci] || 0,
        };
    }

    function draw() {
        const c = stage(), ov = overlay();
        if (!c || !ov || !P.last) return;
        const dpr = window.devicePixelRatio || 1;
        const g = geom();
        if (!g) return;
        const w = Math.round(g.w), h = Math.round(g.h);
        if (ov.width !== Math.round(w * dpr) || ov.height !== Math.round(h * dpr)) {
            ov.width = Math.round(w * dpr); ov.height = Math.round(h * dpr);
        }
        ov.style.width = w + 'px'; ov.style.height = h + 'px';
        const x = ov.getContext('2d');
        x.setTransform(dpr, 0, 0, dpr, 0, 0);
        x.clearRect(0, 0, w, h);

        /* Isolation dims what is outside the box; it never hides it - context stays readable. */
        if (P.sel) {
            const s = P.sel;
            x.fillStyle = 'rgba(6,10,18,0.62)';
            x.fillRect(0, 0, w, s.y0);
            x.fillRect(0, s.y1, w, h - s.y1);
            x.fillRect(0, s.y0, s.x0, s.y1 - s.y0);
            x.fillRect(s.x1, s.y0, w - s.x1, s.y1 - s.y0);
            x.strokeStyle = 'rgba(120,190,255,0.95)';
            x.lineWidth = 1.5;
            x.strokeRect(s.x0 + 0.5, s.y0 + 0.5, s.x1 - s.x0, s.y1 - s.y0);
        }

        /* The shared cursor: whoever published it — this map, the engine, the tape — the level and
           the moment it is on are drawn here, so leaving this panel does not lose the thread. */
        const cur = (window.OFAPCURSOR && OFAPCURSOR.state) || null;
        if (cur && cur.price != null && P.last && (P.last.prices || []).length) {
            const prices = P.last.prices;
            let ri = -1, bestD = Infinity;
            for (let i = 0; i < prices.length; i += 1) {
                const d = Math.abs(prices[i] - cur.price);
                if (d < bestD) { bestD = d; ri = i; }
            }
            const step = OFAPCURSOR.step(prices);
            if (ri >= 0 && (step == null || bestD <= step)) {
                const y = Math.round((g.nr - 1 - ri) * g.chh + g.chh / 2) + 0.5;
                x.save();
                x.strokeStyle = traceInk();
                x.globalAlpha = 0.85;
                x.lineWidth = 1;
                x.beginPath(); x.moveTo(0, y); x.lineTo(g.plotW, y); x.stroke();
                x.globalAlpha = 1;
                const ct = OFAPCURSOR.text();
                if (ct) {
                    x.font = '600 10px ui-monospace, monospace';
                    const wLab = x.measureText(ct).width + 8;
                    x.fillStyle = tok('--of-deep', 'rgb(8,12,20)');
                    x.fillRect(g.plotW - wLab - 2, y - 13, wLab, 12);
                    const t2 = tok('--of-trace-2-rgb', '');
                    x.fillStyle = t2 ? 'rgb(' + t2 + ')' : traceInk();
                    x.fillText(ct, g.plotW - wLab + 2, y - 4);
                }
                x.restore();
            }
        }

        /* A restored marker has no pixels yet, and the map it belongs to may not have been loaded
           when it arrived: place it from its price/bucket before painting (idempotent and cheap). */
        projectMarkers();

        (P.markers || []).forEach((m, i) => {
            x.beginPath();
            x.moveTo(m.x, m.y); x.lineTo(m.x, m.y - 12);
            x.strokeStyle = 'rgba(255,205,90,0.95)'; x.lineWidth = 1.5; x.stroke();
            x.beginPath(); x.arc(m.x, m.y, 3.4, 0, Math.PI * 2); x.fillStyle = 'rgba(255,205,90,0.95)'; x.fill();
            x.font = '600 10px ui-monospace, monospace';
            x.fillStyle = 'rgba(255,225,150,0.95)';
            x.fillText(String(i + 1), m.x + 5, m.y - 13);
        });
    }

    /* How long the level under the cursor has HELD, when it is one of the walls: size alone cannot
       tell a level that just appeared from one defended for ten minutes (P1-6). */
    function wallHeldLine(h) {
        const d = P.last;
        if (!d || !(d.walls || []).length || h.price == null) return '';
        const step = (d.prices && d.prices.length > 1) ? Math.abs(d.prices[1] - d.prices[0]) : null;
        let best = null, bestD = Infinity;
        (d.walls || []).forEach((w) => {
            const dd = Math.abs(Number(w.price) - h.price);
            if (dd < bestD) { bestD = dd; best = w; }
        });
        if (!best || (step != null && bestD > step)) return '';
        const ms = Number(best.held_ms) || 0;
        if (!ms) return '<div>held <b>just now</b></div>';
        const age = ms >= 60000 ? (ms / 60000).toFixed(1) + ' min' : Math.round(ms / 1000) + ' s';
        const floor = Number(d.wall_age_ms) || 120000;
        return '<div>held <b>' + age + '</b>' + (ms >= floor ? ' <span style="opacity:.75">(wall)</span>' : '') + '</div>';
    }

    /* ── markers: pinned levels, in data space, remembered per symbol ──────────────────────────────
       They were session-only; they now live in the config's `markers` block as price/bucket/size/note
       (never pixels), so a reload or a restart brings them back on the symbol they belong to. */
    function markerRows() {
        return (P.markers || []).map((m) => ({ price: m.price, bucket: m.bucket || 0, size: m.size || 0,
            note: String(m.note || '').slice(0, 120) }));
    }

    /* A stored row has no pixels: put it back on the map from the price and the bucket it names. */
    function projectMarkers() {
        const d = P.last, g = geom();
        if (!d || !g) return;
        (P.markers || []).forEach((m) => {
            if (Number.isFinite(m.x) && Number.isFinite(m.y)) return;
            const prices = d.prices || [];
            let ri = -1, bestD = Infinity;
            for (let i = 0; i < prices.length; i += 1) {
                const dd = Math.abs(prices[i] - m.price);
                if (dd < bestD) { bestD = dd; ri = i; }
            }
            if (ri < 0) return;
            /* Bounded, like every other nearest() in this app: a marker whose price is outside the
               drawn rows is not pinned to the edge row pretending to be there. */
            const step = prices.length > 1 ? Math.abs(prices[1] - prices[0]) : 0;
            if (step > 0 && bestD > step) return;
            let ci = -1, bestC = Infinity;
            (d.buckets || []).forEach((b, i) => { const dd = Math.abs(b - m.bucket); if (dd < bestC) { bestC = dd; ci = i; } });
            m.x = ci >= 0 ? (ci + 0.5) * g.cw : g.plotW * 0.5;
            m.y = (g.nr - 1 - ri) * g.chh + g.chh / 2;
        });
    }

    async function markersLoad(sym) {
        try {
            const res = await api('/api/control/markers?symbol=' + encodeURIComponent(sym));
            const rows = ((res && res.block && res.block.markers) || [])
                .filter((m) => m && Number.isFinite(Number(m.price)));
            P.markers = rows.map((m) => ({ price: Number(m.price), bucket: Number(m.bucket) || 0,
                size: Number(m.size) || 0, note: String(m.note || '') }));
            projectMarkers();
            draw(); hud(); paintStats();
        } catch (err) { /* no stored markers for this symbol: nothing to restore */ }
    }

    async function markersSave() {
        const sym = P.markersFor || null;
        if (!sym) return;
        try {
            await api('/api/control/markers', { method: 'POST', body: { symbol: sym, markers: markerRows() } });
        } catch (err) { /* the mark stays in this session either way; the store is the record */ }
    }

    /* ── the readout: what a depth map is asked for and normally does not show ───────────── */
    function hud() {
        const tip = document.querySelector('[data-hm-pro-tip]');
        const info = document.querySelector('[data-hm-pro-info]');
        if (!info || !P.last) return;
        const d = P.last;
        const newest = (d.buckets || [])[d.buckets.length - 1];
        info.innerHTML = 'window <b>' + (d.buckets || []).length + '</b> buckets · <b>' + (d.prices || []).length + '</b> rows' +
            (d.bucket_ms ? ' · <b>' + d.bucket_ms + '</b> ms' : '') +
            (newest ? ' · newest <b>' + esc(fmtBucket(newest)) + '</b>' : '') +
            ' · markers <b>' + (P.markers || []).length + '</b>';
        if (!tip) return;
        if (!P.hud) { tip.style.display = 'none'; return; }
        const h = P.hud;
        const col = h.delta_depth >= 0 ? '#7ee0a8' : '#ff8f8f';
        tip.style.display = 'block';
        tip.innerHTML = '<div><b>' + h.price + '</b> · ' + esc(fmtBucket(h.bucket)) + '</div>' +
            '<div>resting <b>' + h.size.toFixed(2) + '</b></div>' +
            '<div>&Delta; vs prev <b style="color:' + col + '">' + (h.delta_depth >= 0 ? '+' : '') + h.delta_depth.toFixed(2) + '</b></div>' +
            '<div>this price, whole window <b>' + h.row_depth.toFixed(1) + '</b></div>' +
            '<div>whole book, this bucket <b>' + h.bucket_depth.toFixed(1) + '</b></div>' +
            (h.traded ? '<div>executed here <b>' + h.traded.toFixed(2) + '</b></div>' : '') +
            (h.events ? '<div>spoof/stack here <b>' + h.events.toFixed(2) + '</b></div>' : '')
            + wallHeldLine(h);
        const g = geom() || { plotW: 320 };
        tip.style.left = Math.max(4, Math.min(h.x + 14, g.plotW - 10)) + 'px';
        tip.style.top = Math.max(6, h.y - 70) + 'px';
    }

    /* ── selection: box it, read it, isolate it, export it ──────────────────────────────── */
    function regionIndex() {
        const s = P.sel, g = geom();
        if (!s || !g) return null;
        const c0 = Math.max(0, Math.floor(s.x0 / g.cw)), c1 = Math.min(g.nc - 1, Math.floor(s.x1 / g.cw));
        const r1 = Math.min(g.nr - 1, g.nr - 1 - Math.floor(s.y0 / g.chh));
        const r0 = Math.max(0, g.nr - 1 - Math.floor(s.y1 / g.chh));
        return { c0: c0, c1: c1, r0: r0, r1: r1, g: g };
    }

    function regionStats() {
        const ix = regionIndex(), d = P.last;
        if (!ix || !d) return null;
        let depth = 0, worst = { size: 0, price: null }, top = null, topDepth = -1;
        const grid = { prices: [], buckets: [], values: [] };
        for (let r = ix.r0; r <= ix.r1; r++) {
            const row = (d.values || [])[r] || [];
            grid.prices.push((d.prices || [])[r]);
            let rowTotal = 0;
            const keep = [];
            for (let c = ix.c0; c <= ix.c1; c++) {
                const v = row[c] || 0;
                depth += v; rowTotal += v;
                if (v > worst.size) worst = { size: v, price: (d.prices || [])[r] };
                keep.push(v);
            }
            grid.values.push(keep);
            if (rowTotal > topDepth) { topDepth = rowTotal; top = (d.prices || [])[r]; }
        }
        grid.buckets = (d.buckets || []).slice(ix.c0, ix.c1 + 1);
        return { buckets: ix.c1 - ix.c0 + 1, rows: ix.r1 - ix.r0 + 1, total_depth: depth,
                 heaviest: worst, top_price: top, top_depth: Math.max(0, topDepth), grid: grid, ix: ix };
    }

    function markersInRegion() {
        const ix = regionIndex(), d = P.last, out = [];
        if (!d) return out;
        const c0 = ix ? ix.c0 : 0, c1 = ix ? ix.c1 : ((d.buckets || []).length - 1);
        const r0 = ix ? ix.r0 : 0, r1 = ix ? ix.r1 : ((d.prices || []).length - 1);
        const walk = (grid, kind) => {
            if (!grid) return;
            for (let r = r0; r <= r1; r++) {
                const row = grid[r] || [];
                for (let c = c0; c <= c1; c++) if (row[c] > 0) {
                    out.push({ kind: kind, price: (d.prices || [])[r], bucket: (d.buckets || [])[c], size: row[c], note: '' });
                }
            }
        };
        walk(d.traded, 'executed');
        walk(d.events, 'spoof/stack');
        (P.markers || []).forEach((m, i) => out.push({ kind: 'mine #' + (i + 1), price: m.price, bucket: m.bucket, size: m.size, note: m.note || '' }));
        return out;
    }

    function csvForRegion(st) {
        const lines = ['# ModFlow OrderFlow Analysis Suite - heatmap region export',
                       '# symbol,' + (P.symbol || ''),
                       '# exported,' + new Date().toISOString(),
                       '# buckets,' + st.buckets + ' rows,' + st.rows + ' total_resting,' + st.total_depth.toFixed(2),
                       '# heaviest_price,' + st.heaviest.price + ' heaviest_size,' + st.heaviest.size.toFixed(2),
                       '# top_price,' + st.top_price + ' top_price_total,' + st.top_depth.toFixed(2),
                       ['price'].concat(st.grid.buckets.map(fmtBucket)).join(',')];
        st.grid.values.forEach((row, i) => lines.push([st.grid.prices[i]].concat(row.map((v) => (v || 0).toFixed(3))).join(',')));
        return lines.join('\n');
    }

    function csvForMarkers() {
        const rows = [['kind', 'price', 'bucket', 'size', 'note'].join(',')];
        markersInRegion().forEach((m) => rows.push([m.kind, m.price, fmtBucket(m.bucket), Number(m.size || 0).toFixed(3), String(m.note || '').replace(/,/g, ';')].join(',')));
        return rows.join('\n');
    }

    function say(html) {
        /* Its own element on purpose: the readout line is rewritten on every hover and poll, and a
           path written there vanished before it could be read. */
        let box = document.querySelector('[data-hm-pro-msg]');
        if (!box) {
            box = document.createElement('div');
            box.setAttribute('data-hm-pro-msg', '1');
            box.className = 'hm-pro-msg';
            const bar = document.querySelector('[data-hm-pro-bar]');
            (bar ? bar.parentElement : document.body).appendChild(box);
        }
        box.innerHTML = html;
        clearTimeout(P.sayTimer);
        P.sayTimer = setTimeout(() => { box.innerHTML = ''; }, 30000);
    }

    async function save(name, text) {
        try {
            /* Exports and alerts are writes: the arbiter holds them until the gesture ends. */
            const res = window.OFAPINTENT
                ? await new Promise((resolve, reject) => OFAPINTENT.queueWrite('hm.export.' + name,
                    () => api('/api/control/export/save', { method: 'POST', body: { name: name, text: text } })
                        .then(resolve).catch(reject)))
                : await api('/api/control/export/save', { method: 'POST', body: { name: name, text: text } });
            if (res && res.path) say('saved <b>' + esc(res.path) + '</b> (' + (res.bytes || 0) + ' bytes)');
            return res;
        } catch (e) {
            say('<span style="color:#ff8f8f">export failed</span>');
        }
    }

    /* ── zoom: through the map's own window control, so the reload is the real one ───────── */
    /* The price step of this instrument, for a level tolerance that makes sense on BTC and on
       an altcoin alike: two of the smallest gaps the map is drawn on. */
    function levelTolerance() {
        const px = (P.last && P.last.prices) || [];
        let step = 0;
        for (let i = 1; i < px.length; i++) {
            const d = Math.abs(px[i] - px[i - 1]);
            if (d > 0 && (!step || d < step)) step = d;
        }
        return Number((step ? step * 2 : 0.5).toFixed(6));
    }

    async function alertOnLevel(price, size, kind, opts) {
        if (price == null) { say('box a region (or hover a level) first'); return null; }
        opts = opts || {};
        const minSize = Number(Math.max(0.01, (size || 0) * (opts.sizeShare || 0.8)).toFixed(4));
        /* Tolerance defaults to two drawn price steps, and the user can set their own: a level
           alert on a 0.5-grid instrument and on a 0.0001 one should not share a number. It is asked
           for in a FIELD, never with window.prompt: the frozen WebView is not guaranteed to render
           one, and a button that silently does nothing is worse than no button. */
        let tol = levelTolerance();
        const tolEl = document.querySelector('[data-hm-pro-tol]');
        /* An EMPTY field means "use the default", not "zero": Number('') is 0, which would have
           created a rule that fires only at the exact cent. */
        const typed = (tolEl && String(tolEl.value).trim() !== '') ? Number(tolEl.value) : NaN;
        if (Number.isFinite(typed) && typed > 0) tol = typed;
        const rule = {
            id: 'hm-' + String(P.symbol || 'sym') + '-' + String(price).replace('\.', '_') + '-' + Date.now().toString().slice(-6),
            name: (P.symbol || '') + ' ' + price + ' · ' +
                  (kind === 'wall_age' ? 'holds ≥ ' + opts.minAgeS + 's'
                                       : (kind === 'heat_stack' ? 'stacking' : 'pulled') + ' ≥ ' + minSize) +
                  ' (±' + tol + ')',
            kind: kind,
            enabled: true,
            params: Object.assign({ min_size: minSize, at_price: price, at_tol: tol },
                                  opts.minAgeS ? { min_age_s: opts.minAgeS } : {}),
            cooldown_s: opts.minAgeS ? 60 : 30,
            channels: ['ui'],
        };
        try {
            await api('/api/atlas/alert-rules', { method: 'POST', body: rule });
            say('alert created: <b>' + esc(rule.name) + '</b> — fires only at that level, UI channel. See the Alerts view.');
            return rule;
        } catch (e) {
            say('<span style="color:#ff8f8f">could not create the alert</span>');
            return null;
        }
    }

    /* The replay transport already loads a window (start_ms/end_ms). Drive its own form so the
       panel shows what is being replayed instead of silently disagreeing with it. */
    function sendRegionToReplay() {
        const ix = regionIndex(), d = P.last;
        if (!ix || !d) { say('box a region first'); return; }
        const stamps = (d.buckets || []).slice(ix.c0, ix.c1 + 1).filter((x) => typeof x === 'number');
        if (!stamps.length) { say('this window has no timestamps to replay'); return; }
        const start = Math.min.apply(null, stamps), end = Math.max.apply(null, stamps);
        const now = Date.now();
        const fromMin = Math.max(1, Math.round((now - start) / 60000));
        const toMin = Math.max(0, Math.round((now - end) / 60000));
        const symEl = document.getElementById('rpSymbol'), srcEl = document.getElementById('rpSource');
        const fromEl = document.getElementById('rpFrom'), toEl = document.getElementById('rpTo');
        const load = document.getElementById('rpLoad');
        if (!symEl || !fromEl || !toEl || !load) { say('the replay panel is not in this build'); return; }
        symEl.value = P.symbol || '';
        if (srcEl && srcEl.value === 'exchange') {
            const other = [...srcEl.options].map((o) => o.value).find((v) => v !== 'exchange');
            if (other) srcEl.value = other;
        }
        fromEl.value = String(fromMin);
        toEl.value = String(toMin);
        [symEl, fromEl, toEl].forEach((el) => el.dispatchEvent(new Event('change')));
        showView('replay');
        setTimeout(() => {
            load.click();
            say('replaying <b>' + esc(fmtBucket(start)) + ' \u2192 ' + esc(fmtBucket(end)) + '</b> (' + fromMin + ' \u2192 ' + toMin + ' min ago)');
        }, 450);
    }

    const WINDOWS = [120, 240, 480, 900];
    function zoom(dir) {
        const sel = $('#hmColumns');
        if (!sel) return;
        const cur = parseInt(sel.value, 10);
        let i = WINDOWS.indexOf(cur);
        if (i < 0) i = 1;
        i = Math.min(WINDOWS.length - 1, Math.max(0, i + dir));
        if (WINDOWS[i] === cur) return;
        sel.value = String(WINDOWS[i]);
        sel.dispatchEvent(new Event('change'));
        setTimeout(() => pull(true), 280);
    }
    function zoomRows(dir) {
        const sel = $('#hmRows');
        if (!sel) return;
        const opts = [...sel.options].map((o) => o.value);
        let i = opts.indexOf(sel.value);
        if (i < 0) i = 1;
        i = Math.min(opts.length - 1, Math.max(0, i + dir));
        if (opts[i] === sel.value) return;
        sel.value = opts[i];
        sel.dispatchEvent(new Event('change'));
        setTimeout(() => pull(true), 280);
    }

    function paintStats() {
        const box = document.querySelector('[data-hm-pro-stats]');
        if (!box) return;
        const st = regionStats();
        if (!st) {
            box.innerHTML = 'Wheel = zoom window · shift+wheel = price rows · drag = box a region · Mark = pin a level · ' +
                'hover a level then Alert to watch it';
            return;
        }
        box.innerHTML = 'selected <b>' + st.buckets + ' &times; ' + st.rows + '</b> cells · resting <b>' + st.total_depth.toFixed(1) +
            '</b> · heaviest <b>' + (st.heaviest.price == null ? '--' : st.heaviest.price) + '</b> (' + st.heaviest.size.toFixed(2) + ')' +
            '<input class="hm-note" data-hm-pro-tol type="number" step="0.1" min="0" placeholder="± tol" title="price tolerance for the alert level — leave empty for the default, two drawn price steps">' +
            '<input class="hm-note" data-hm-pro-mins type="number" step="1" min="1" placeholder="min" title="how many minutes the level must hold before the hold-alert fires (default 2)">' +
            ' <button class="btn small" data-hm-pro="alert-heavy">Alert: heaviest level</button>' +
            ' <button class="btn small" data-hm-pro="alert-hold">Alert: if this level holds</button>' +
            ' <button class="btn small" data-hm-pro="alert-stack">Alert: stacking here</button>' +
            ' <button class="btn small" data-hm-pro="to-replay">Send region to replay</button>' +
            ' <button class="btn small" data-hm-pro="export-region">Export region CSV</button>' +
            ' <button class="btn small" data-hm-pro="export-markers">Export markers CSV</button>' +
            ' <button class="btn small" data-hm-pro="clear-sel">Clear</button>';
    }

    function build() {
        const c = stage();
        if (!c || overlay()) return;
        const host = c.parentElement;
        host.style.position = 'relative';
        const ov = document.createElement('canvas');
        ov.setAttribute('data-hm-pro-overlay', '1');
        ov.style.position = 'absolute';
        ov.style.left = c.offsetLeft + 'px';
        ov.style.top = c.offsetTop + 'px';
        ov.style.pointerEvents = 'none';
        ov.style.zIndex = '3';
        host.appendChild(ov);
        const tip = document.createElement('div');
        tip.setAttribute('data-hm-pro-tip', '1');
        tip.className = 'hm-pro-tip';
        tip.style.display = 'none';
        host.appendChild(tip);
        c.style.cursor = 'crosshair';

        c.addEventListener('mousemove', (ev) => {
            P.hud = cellAt(ev);
            hud();
            /* Publish the level under the pointer: this is where the whole spine starts — the engine,
               the ladder, the tape and the profile all follow what is published here. */
            if (window.OFAPCURSOR) {
                if (P.hud) OFAPCURSOR.move(P.hud.price, P.hud.bucket, 'heatmap');
                else OFAPCURSOR.clear('heatmap');
            }
            if (P.dragging && P.sel) {
                const r = geom().rect;
                P.sel.x1 = Math.max(0, Math.min(ev.clientX - r.left, geom().plotW));
                P.sel.y1 = Math.max(0, Math.min(ev.clientY - r.top, geom().plotH));
                draw();
            }
        });
        c.addEventListener('mouseleave', () => {
            P.hud = null;
            hud();
            if (window.OFAPCURSOR) OFAPCURSOR.clear('heatmap');
        });
        c.addEventListener('wheel', (ev) => {
            if (!active()) return;
            ev.preventDefault();
            if (ev.shiftKey) { zoomRows(ev.deltaY > 0 ? -1 : 1); return; }
            zoom(ev.deltaY > 0 ? -1 : 1);
        }, { passive: false });
        c.addEventListener('mousedown', (ev) => {
            if (P.mode === 'mark') {
                const cell = cellAt(ev);
                if (!cell) return;
                /* No window.prompt in this app: the frozen WebView is not guaranteed to render one,
                   and a mark that silently does nothing is worse than no mark button. */
                const noteEl = document.querySelector('[data-hm-pro-note]');
                const note = noteEl ? String(noteEl.value || '').slice(0, 120) : '';
                if (noteEl) noteEl.value = '';
                P.markers.push({ x: cell.x, y: cell.y, price: cell.price, bucket: cell.bucket, size: cell.size, note: note });
                draw(); hud(); paintStats();
                void markersSave();
                return;
            }
            const r = geom().rect;
            P.dragging = true;
            P.sel = { x0: Math.max(0, ev.clientX - r.left), y0: Math.max(0, ev.clientY - r.top),
                      x1: Math.max(0, ev.clientX - r.left), y1: Math.max(0, ev.clientY - r.top) };
            draw();
        });
        window.addEventListener('mouseup', () => {
            if (P.dragging) { P.dragging = false; paintStats(); }
        });
        c.addEventListener('dblclick', () => { P.sel = null; draw(); paintStats(); });
    }

    function toolbar() {
        const anchor = document.getElementById('hmAuto');
        if (!anchor || document.querySelector('[data-hm-pro-bar]')) return;
        const bar = document.createElement('div');
        bar.setAttribute('data-hm-pro-bar', '1');
        bar.className = 'hm-pro-bar';
        bar.innerHTML = '<button class="btn small" data-hm-pro="zoom-in">zoom +</button>' +
            '<button class="btn small" data-hm-pro="zoom-out">zoom &minus;</button>' +
            '<button class="btn small" data-hm-pro="rows-up">rows +</button>' +
            '<button class="btn small" data-hm-pro="rows-down">rows &minus;</button>' +
            '<button class="btn small" data-hm-pro="mark">mark level</button>' +
            '<input class="hm-note" data-hm-pro-note type="text" maxlength="120" placeholder="note (optional)" />' +
            '<button class="btn small" data-hm-pro="clear-markers">clear markers</button>' +
            '<button class="btn small" data-hm-pro="fit">fit</button>' +
            '<button class="btn small" data-hm-pro="alert-here">alert on cursor level</button>' +
            '<span class="dim" data-hm-pro-info="1"></span>';
        anchor.parentElement.appendChild(bar);
        if (window.OFAPCURSOR) OFAPCURSOR.badge(bar);
        const clearBtn = bar.querySelector('[data-hm-pro="clear-markers"]');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                P.markers = [];
                draw(); hud(); paintStats();
                void markersSave();
            });
        }
        const stats = document.createElement('div');
        stats.setAttribute('data-hm-pro-stats', '1');
        stats.className = 'hm-pro-stats dim';
        anchor.closest('.view').querySelector('.view-head').appendChild(stats);
    }

    document.addEventListener('click', (ev) => {
        const b = ev.target.closest('[data-hm-pro]');
        if (!b) return;
        const act = b.dataset.hmPro;
        if (act === 'zoom-in') return zoom(1);
        if (act === 'zoom-out') return zoom(-1);
        if (act === 'rows-up') return zoomRows(1);
        if (act === 'rows-down') return zoomRows(-1);
        if (act === 'mark') {
            P.mode = P.mode === 'mark' ? 'inspect' : 'mark';
            b.style.outline = P.mode === 'mark' ? '1px solid #ffcd5a' : '';
            return;
        }
        if (act === 'fit') { P.sel = null; zoom(0); return; }
        if (act === 'clear-sel') { P.sel = null; draw(); paintStats(); return; }
        if (act === 'alert-heavy') {
            const st = regionStats();
            if (st && st.heaviest.price != null) alertOnLevel(st.heaviest.price, st.heaviest.size, 'heat_pull');
            else if (P.hud) alertOnLevel(P.hud.price, P.hud.size, 'heat_pull');
            return;
        }
        if (act === 'alert-hold') {
            /* "Tell me when this level has held for X minutes" - a duration question, which the
               detection side answers with its own wall_age kind and this rule's level scope. */
            const st = regionStats();
            const price = (st && st.heaviest.price != null) ? st.heaviest.price : (P.hud ? P.hud.price : null);
            const size = (st && st.heaviest.price != null) ? st.heaviest.size : (P.hud ? P.hud.size : 0);
            if (price == null) { say('box a region (or hover a level) first'); return; }
            const minsEl = document.querySelector('[data-hm-pro-mins]');
            const typedMins = minsEl ? Number(minsEl.value) : NaN;
            const mins = Number.isFinite(typedMins) && typedMins > 0 ? typedMins : 2;
            if (minsEl && !minsEl.value) minsEl.value = String(mins);
            alertOnLevel(price, size, 'wall_age', { minAgeS: Math.round(mins * 60), sizeShare: 0.5 });
            return;
        }
        if (act === 'alert-stack') {
            const st = regionStats();
            if (st && st.putative) { /* never */ }
            if (st && st.heaviest.price != null) alertOnLevel(st.heaviest.price, st.heaviest.size, 'heat_stack');
            else if (P.hud) alertOnLevel(P.hud.price, P.hud.size, 'heat_stack');
            return;
        }
        if (act === 'alert-here') {
            if (!P.hud) { say('hover a level first'); return; }
            alertOnLevel(P.hud.price, P.hud.size, 'heat_pull');
            return;
        }
        if (act === 'to-replay') { sendRegionToReplay(); return; }
        if (act === 'export-region') {
            const st = regionStats();
            if (st) save('heatmap_region_' + Date.now() + '.csv', csvForRegion(st));
            return;
        }
        if (act === 'export-markers') { save('heatmap_markers_' + Date.now() + '.csv', csvForMarkers()); return; }
    });

    function refresh() {
        if (!active()) return;
        build();
        toolbar();
        const ov = overlay(), c = stage();
        if (ov && c) { ov.style.left = c.offsetLeft + 'px'; ov.style.top = c.offsetTop + 'px'; }
        paintStats();
        pull(true);
    }

    /* The cursor moving anywhere repaints this overlay only when the drawn level actually changed.
       heatmap-pro.js loads before cursor-link.js, so this waits for the module rather than silently
       skipping the subscription. */
    const onCursor = () => {
        const st = OFAPCURSOR.state;
        const sig = String(st.price) + '|' + String(st.timeMs);
        if (sig === P.cursorSig) return;
        P.cursorSig = sig;
        if (active()) draw();
    };
    if (window.OFAPCURSOR) OFAPCURSOR.subscribe(onCursor);
    else {
        let tries = 0;
        const wait = () => {
            if (window.OFAPCURSOR) return OFAPCURSOR.subscribe(onCursor);
            if ((tries += 1) < 60) setTimeout(wait, 50);
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wait, { once: true });
        else setTimeout(wait, 50);
    }

    document.addEventListener('ofap:relayout', () => setTimeout(refresh, 140));
    document.addEventListener('click', (ev) => { if (ev.target.closest('[data-view="heatmap"]')) setTimeout(refresh, 280); });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(refresh, 900));
    else setTimeout(refresh, 900);

    window.HEATMAP_PRO = { state: P, refresh: refresh, pull: pull, zoom: zoom, zoomRows: zoomRows,
                       alertOnLevel: alertOnLevel, sendRegionToReplay: sendRegionToReplay, levelTolerance: levelTolerance,
                           regionStats: regionStats, csvForRegion: csvForRegion, csvForMarkers: csvForMarkers,
                           cellAt: cellAt };
})();
