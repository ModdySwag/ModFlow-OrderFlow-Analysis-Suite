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

    const P = { last: null, sel: null, mode: 'inspect', markers: [], hud: null, dragging: false, symbol: null, anchor: null };
    /* §120: a selection box is born only after the pointer really moves this far (css px) — so a
       plain click can never leave a zero-size box whose outside-dim darkens the whole map. */
    const DRAG_PX = 4;

    const $ = (s) => document.querySelector(s);
    /* SEC-18: the apostrophe is escaped too — `title='…'` contexts exist. */
    const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    /* Buckets arrive as epoch milliseconds; a desk reads clock time, not a 13-digit number. */
    const fmtBucket = (b) => {
        if (b == null) return '';
        if (typeof b === 'number' && b > 1e11) {
            const d = new Date(b);
            return d.toTimeString().slice(0, 8);
        }
        return String(b);
    };

    /* Price decimals follow the instrument's own tick, never the price's magnitude: a half-tick
       instrument prints one decimal, a cent tick two, a whole-number tick none, and a tick nobody
       stated falls back to two rather than guessing a scale from the size of the number. */
    const dpFor = (tick) => {
        const t = Number(tick);
        if (!isFinite(t) || t <= 0) return 2;
        const text = String(t);
        const dec = text.indexOf('.') >= 0 ? text.split('.')[1].replace(/0+$/, '').length : 0;
        return Math.min(8, Math.max(0, dec));
    };

    /* How much of the colour scale one cell fills, in percent — the number that ties a hovered
       cell to the legend. Null when the payload carries no cap: no percentage is invented. */
    const shareOfScale = (size, scaleMax) => {
        const s = Number(size), cap = Number(scaleMax);
        if (!isFinite(s) || !isFinite(cap) || cap <= 0 || s <= 0) return null;
        return Math.round(Math.min(100, (s / cap) * 100) * 10) / 10;
    };

    /* A level's change against the bucket before it, as a share of that bucket: +14% is an
       absorption read, +0.42 is a number without a scale. Null when there was nothing to move
       from. */
    const deltaPct = (delta, prev) => {
        const d = Number(delta), p = Number(prev);
        if (!isFinite(d) || !isFinite(p) || p <= 0) return null;
        return Math.round((d / p) * 100 * 10) / 10;
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
    /* §121: the loader-side twin of heatview's params() — the overlay's own fetch respects the
       pan anchor too, or a relayout pull would silently snap the map back to the live edge. */
    const untilQ = () => (window.OFAPHEATVIEW && OFAPHEATVIEW.state.until != null)
        ? '&until=' + Math.round(OFAPHEATVIEW.state.until) : '';

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
        const seq = (P.pullSeq || 0) + 1;      // D-10: a forced pull must not be overtaken
        P.pullSeq = seq;
        try {
            const sym = await symbol();
            if (!sym) return;
            if (seq !== P.pullSeq) return;
            if (P.markersFor !== sym) { P.markersFor = sym; P.markers = []; void markersLoad(sym); }
            const payload = await api('/api/atlas/heatmap/' + encodeURIComponent(sym) + '?columns=' + cols() + '&rows=' + rows() + untilQ());
            if (seq !== P.pullSeq) return;     // a newer pull is in flight: its answer wins
            P.last = payload;
            if (window.OFAPHEATVIEW) OFAPHEATVIEW.absorb(OFAPHEATVIEW.state, payload);
            if ((!P.last || !(P.last.buckets || []).length) && !P.reResolved) {
                P.reResolved = true;                 // one retry, then accept the empty map
                P.symbol = null;
                const again = await symbol();
                if (again && again !== sym) {
                    P.last = await api('/api/atlas/heatmap/' + encodeURIComponent(again) + '?columns=' + cols() + '&rows=' + rows() + untilQ());
                }
            }
            /* P1-10: the map's sample clock is its newest depth bucket — a silent feed grows this. */
            if (window.OFAPFRESH) {
                const buckets = (P.last && P.last.buckets) || [];
                OFAPFRESH.stamp('heatmap', { lastMs: buckets.length ? Number(buckets[buckets.length - 1]) : 0, kind: 'depth' });
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
        const box = c.getBoundingClientRect();
        /* C-05: the SIZE comes from the same box prepCanvas used (clientWidth/clientHeight — no
           border, no scrollbar); only the origin comes from the rect. The border box disagreed
           with the canvas by the border and mis-registered this overlay on narrow layouts. */
        const r = { left: box.left, top: box.top, width: c.clientWidth, height: c.clientHeight };
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
            (window.OFAPHEATVIEW ? ' · <b>' + esc(OFAPHEATVIEW.state.until == null ? 'live'
                : OFAPHEATVIEW.label(OFAPHEATVIEW.state, Date.now()).split(' · ').pop()) + '</b>' : '') +
            ' · markers <b>' + (P.markers || []).length + '</b>';
        chip();
        /* §122: the labels and the Detail dial follow the payload's true column width. */
        if (window.OFAPHEATVIEW && P.labelBucket !== OFAPHEATVIEW.state.bucket) {
            P.labelBucket = OFAPHEATVIEW.state.bucket;
            relabelWindows();
            const bsel = $('#hmBucket');
            if (bsel && parseInt(bsel.value, 10) !== OFAPHEATVIEW.state.bucket
                && [100, 250, 500, 1000, 2000, 5000].indexOf(OFAPHEATVIEW.state.bucket) >= 0) {
                bsel.value = String(OFAPHEATVIEW.state.bucket);
            }
        }
        if (!tip) return;
        if (!P.hud) { tip.style.display = 'none'; return; }
        const h = P.hud;
        const col = h.delta_depth >= 0 ? '#7ee0a8' : '#ff8f8f';
        /* §140: a square with nothing recorded is not a square with "undefined" in it. Before the
           first book updates land — or on a cell the map has no row for — the readout says so
           instead of printing the absence as data. */
        const empty = !isFinite(Number(h.price)) || !isFinite(Number(h.size));
        tip.style.display = 'block';
        /* §140: the same read in the desk's own terms — the cell's share of the colour scale beside
           the legend, the change as a share of the level it moved from, and the spread where the
           payload has a book to quote one. */
        const share = shareOfScale(h.size, d.scale_max);
        const pct = deltaPct(h.delta_depth, h.size - h.delta_depth);
        const dp = dpFor(d.tick);
        const best = ((d.best || [])[h.ci]) || null;
        const bid = best ? Number(best.bid) : NaN;
        const ask = best ? Number(best.ask) : NaN;
        const bookLine = (isFinite(bid) && isFinite(ask) && bid > 0 && ask >= bid)
            ? '<div>bid <b>' + bid.toFixed(dp) + '</b> · ask <b>' + ask.toFixed(dp)
              + '</b> · spread <b>' + (ask - bid).toFixed(dp) + '</b></div>'
            : '';
        tip.innerHTML = empty
            ? '<div class="dim">no resting size recorded in this square yet — the map is still '
              + 'gathering book updates</div>'
            : '<div><b>' + h.price + '</b> · ' + esc(fmtBucket(h.bucket)) + '</div>' +
            '<div>resting <b>' + h.size.toFixed(2) + '</b>'
            + (share === null ? '' : ' · <b>' + (share >= 10 ? share.toFixed(0) : share.toFixed(1))
                               + '%</b> of scale') + '</div>' +
            '<div>&Delta; vs prev <b style="color:' + col + '">' + (h.delta_depth >= 0 ? '+' : '') + h.delta_depth.toFixed(2) + '</b>'
            + (pct === null ? '' : ' (' + (pct > 0 ? '+' : '') + pct.toFixed(0) + '%)') + '</div>' +
            bookLine +
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

    /* v2 §7-11b (Bookmap's range-to-table): the book's own record — walls, grows, pulls, spikes —
       listed for exactly the boxed band, and the boxed time columns when the payload dates them.
       The map keeps the last 120 events and the payload ships them verbatim; nothing here invents
       a row. */
    function regionEvents() {
        const ix = regionIndex(), d = P.last;
        if (!ix || !d) return null;
        const px = d.prices || [];
        const all = Array.isArray(d.events) ? d.events : [];
        const lo = Math.min(px[ix.r0], px[ix.r1]);
        const hi = Math.max(px[ix.r0], px[ix.r1]);
        const bts = d.buckets || [];
        const t0 = bts[ix.c0] || 0;
        const width = (window.OFAPHEATVIEW && OFAPHEATVIEW.state && OFAPHEATVIEW.state.bucket) || 1000;
        const t1 = bts[ix.c1] ? bts[ix.c1] + width : 0;
        const evs = all.filter((e) => e && e.price >= lo && e.price <= hi
            && (!t0 || e.ts_ms >= t0) && (!t1 || e.ts_ms <= t1));
        return { evs: evs, total: all.length, lo: lo, hi: hi, t0: t0, t1: t1 };
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

    function csvForEvents() {
        const r = regionEvents();
        if (!r) return '';
        const rows = [['ts_ms', 'time', 'kind', 'price', 'direction', 'size', 'detail'].join(',')];
        r.evs.slice().sort((a, b) => a.ts_ms - b.ts_ms).forEach((e) => rows.push([
            e.ts_ms, new Date(e.ts_ms).toISOString(), e.kind, e.price, e.direction || '',
            Number(e.size || 0).toFixed(3), String(e.detail || '').replace(/,/g, ';'),
        ].join(',')));
        return rows.join('\n');
    }

    function eventsBox() { return document.querySelector('[data-hm-pro-events]'); }

    function paintEvents() {
        const r = regionEvents();
        if (!r) { say('box a region first'); return; }
        let box = eventsBox();
        if (!box) {
            box = document.createElement('div');
            box.setAttribute('data-hm-pro-events', '1');
            box.className = 'hm-pro-msg';
            const stats = document.querySelector('[data-hm-pro-stats]');
            (stats ? stats.parentElement : document.body).appendChild(box);
        }
        const rows = r.evs.slice(-100).reverse().map((e) => '<tr><td>' + new Date(e.ts_ms).toLocaleTimeString() + '</td>'
            + '<td>' + esc(String(e.kind)) + '</td><td>' + e.price + '</td><td>' + esc(String(e.direction || '')) + '</td>'
            + '<td>' + Number(e.size || 0).toFixed(2) + '</td><td class="dim">' + esc(String(e.detail || '')) + '</td></tr>').join('');
        box.innerHTML = '<b>Events in region</b> — ' + r.evs.length + ' of ' + r.total + ' level events in the boxed band ('
            + r.lo + '–' + r.hi + ')'
            + (rows ? '<table class="data" style="margin-top:6px"><thead><tr><th>Time</th><th>Kind</th><th>Price</th><th>Side</th><th>Size</th><th>Detail</th></tr></thead><tbody>'
                     + rows + '</tbody></table>'
                    : '<div class="dim" style="margin-top:6px">no level events in this box — the record holds walls, grows, pulls and spikes as the book makes them.</div>')
            + ' <button class="btn small" data-hm-pro="export-events">Export events CSV</button>'
            + ' <button class="btn small" data-hm-pro="close-events">Close</button>';
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
        void handRegionToReplay(symEl, srcEl, fromEl, toEl, load, start, end, fromMin, toMin);
    }

    /* The write half, after the picker's list ask: the picker fills its options lazily (view entry,
       focus), and a bare `sel.value = …` into a list that does not carry the symbol lands on
       NOTHING — the transport would then replay whatever the fallback resolves, i.e. another
       instrument than the boxed region. Ask the filler first; if the list still has no such
       instrument, say so instead of letting the form disagree with the map. */
    async function handRegionToReplay(symEl, srcEl, fromEl, toEl, load, start, end, fromMin, toMin) {
        if (window.OFAPREPLAY && typeof OFAPREPLAY.fillSymbols === 'function') {
            try { await OFAPREPLAY.fillSymbols(); } catch (e) { /* the list keeps its last fill */ }
        }
        const wanted = String(P.symbol || '');
        symEl.value = wanted;
        if (wanted && String(symEl.value || '').toUpperCase() !== wanted.toUpperCase()) {
            say('the replay list does not carry <b>' + esc(wanted) + '</b> — enable it on its source first');
            return;
        }
        if (srcEl && srcEl.value === 'exchange') {
            const other = [...srcEl.options].map((o) => o.value).find((v) => v !== 'exchange');
            if (other) srcEl.value = other;
        }
        fromEl.value = String(fromMin);
        toEl.value = String(toMin);
        [symEl, fromEl, toEl].forEach((el) => el.dispatchEvent(new Event('change')));
        /* rpFrom/rpTo were written programmatically: re-pair their preset chips. */
        if (window.OFAPPRESETS && OFAPPRESETS.refresh) OFAPPRESETS.refresh();
        if (window.OFAPNAV) OFAPNAV.jump('replay', 'Heatmap'); else showView('replay');
        setTimeout(() => {
            load.click();
            say('replaying <b>' + esc(fmtBucket(start)) + ' \u2192 ' + esc(fmtBucket(end)) + '</b> (' + fromMin + ' \u2192 ' + toMin + ' min ago)');
        }, 450);
    }

    const WINDOWS = [120, 240, 480, 900];
    /* §120: the pure half of stepping a select — the value a step lands on, or null at the end.
       Pinned by heatmap-pro.selftest.js. */
    function listStep(cur, dir, list) {
        const L = (list || []).map((v) => String(v));
        if (!L.length) return null;
        let i = L.indexOf(String(cur));
        if (i < 0) i = 1;
        const ni = Math.min(L.length - 1, Math.max(0, i + dir));
        return L[ni] === String(cur) ? null : L[ni];
    }
    /* §121/§122: the Window labels are TIME = columns x column width, so they follow the Detail
       dial; a width change tells the hub (a live apply) and refetches on the new grid. */
    function relabelWindows() {
        const sel = $('#hmColumns');
        if (!sel || !window.OFAPHEATVIEW) return;
        const b = OFAPHEATVIEW.state.bucket;
        for (let i = 0; i < sel.options.length; i++) {
            const c = parseInt(sel.options[i].value, 10);
            if (c) sel.options[i].textContent = OFAPHEATVIEW.minutesOf(c, b);
        }
    }

    function wireBucket() {
        const sel = $('#hmBucket');
        if (!sel || sel.__wired) return;
        sel.__wired = true;
        sel.addEventListener('change', async () => {
            const ms = parseInt(sel.value, 10) || 1000;
            if (window.OFAPHEATVIEW) OFAPHEATVIEW.state.bucket = ms;
            relabelWindows();
            try {
                await api('/api/control/params', { method: 'POST', body: { path: 'atlas.heatmap.bucket_ms', value: ms } });
            } catch (err) { /* the config write is the record; the running width already changed */ }
            say('detail ' + ms + ' ms — the depth buffer restarts on the new grid');
            applyView();
        });
    }

    /* §121: the view talk. Every zoom/pan ends in applyView(): the selects are the zoom READOUT
       (written from the state, so the dropdown and the gesture can never disagree), the live chip
       flips, and ONE change event drives the loader — which the deliberate path forces past the
       intent gate. That gate is why the zoom read as dead: a wheel leases the surface for 900 ms
       and the loader deferred its repaint away for the whole of it. */
    function applyView() {
        if (!window.OFAPHEATVIEW) return;
        const V = OFAPHEATVIEW.state;
        const colsSel = $('#hmColumns');
        const rowsSel = $('#hmRows');
        if (colsSel && String(V.cols) !== colsSel.value) colsSel.value = String(V.cols);
        if (rowsSel && String(V.rows) !== rowsSel.value) rowsSel.value = String(V.rows);
        chip();
        const driver = colsSel || rowsSel;
        if (driver) driver.dispatchEvent(new Event('change'));
    }

    function chip() {
        const b = document.querySelector('[data-hm-pro="live"]');
        if (!b || !window.OFAPHEATVIEW) return;
        const live = OFAPHEATVIEW.state.until == null;
        b.textContent = live ? '\u25cf live' : '\u25b6 back to live';
        b.title = live ? 'The map follows the live edge'
                       : 'Click (or Home) to snap back to the live edge';
    }

    /* dir -1 = zoom in = a narrower window; the ends answer out loud. */
    function zoom(dir) {
        if (!window.OFAPHEATVIEW) return;
        const V = OFAPHEATVIEW.state;
        const out = OFAPHEATVIEW.zoomTime(V, dir, 0.5, Date.now());
        if (!out.moved) {
            say(dir < 0 ? 'tightest window already — ' + OFAPHEATVIEW.minutesOf(V.cols, V.bucket)
                        : 'widest window already — ' + OFAPHEATVIEW.minutesOf(V.cols, V.bucket));
            return;
        }
        V.cols = out.cols;
        V.until = out.until;
        applyView();
    }

    function zoomRows(dir) {
        if (!window.OFAPHEATVIEW) return;
        const V = OFAPHEATVIEW.state;
        const out = OFAPHEATVIEW.zoomRows(V, dir);
        if (!out.moved) {
            say(dir > 0 ? 'most rows already — ' + V.rows : 'fewest rows already — ' + V.rows);
            return;
        }
        V.rows = out.rows;
        applyView();
    }

    /* §121: keyboard pan — one bucket a press, the shift pair ten (Bookmap's own nudge). */
    function panStep(n) {
        if (!window.OFAPHEATVIEW) return;
        const V = OFAPHEATVIEW.state;
        const out = OFAPHEATVIEW.panStep(V, n, Date.now());
        if (!out.moved) return;
        V.until = out.until;
        applyView();
        say(OFAPHEATVIEW.label(V, Date.now()));
    }

    function liveNow() {
        if (!window.OFAPHEATVIEW) return;
        const V = OFAPHEATVIEW.state;
        if (V.until == null) { say('already at the live edge'); return; }
        OFAPHEATVIEW.snapLive(V);
        applyView();
        say('back to the live edge');
    }

    /* §119: "fit" in the desk sense — drop the selection and put the view back on its defaults.
       The panel's two dials ARE the view state, so the reset walks through them (one pipeline).
       It always answers, even when nothing moved: a button that silently does nothing reads as
       broken, which is how the old no-op fit was reported. */
    function fitAll() {
        P.sel = null;
        const colsSel = $('#hmColumns');
        const rowsSel = $('#hmRows');
        let touched = null;
        if (colsSel && colsSel.value !== '240') { colsSel.value = '240'; touched = colsSel; }
        if (rowsSel && rowsSel.value !== '200') { rowsSel.value = '200'; touched = touched || rowsSel; }
        /* §121: fit means the factory view AND the live edge — a fit that left you panned would
           be the very trap it was built to end. */
        const V = window.OFAPHEATVIEW ? OFAPHEATVIEW.state : null;
        const wasPanned = !!(V && V.until != null);
        if (V) { V.cols = 240; V.rows = 200; OFAPHEATVIEW.snapLive(V); chip(); }
        /* One reload for the pair: the loader reads both dials fresh, so a single change suffices. */
        if (touched) touched.dispatchEvent(new Event('change'));
        else if (wasPanned) applyView();
        draw();
        paintStats();
        say((touched || wasPanned) ? 'view fitted — 4 min window · 200 rows · live' : 'already fitted — 4 min window · 200 rows · live');
    }

    function paintStats() {
        const box = document.querySelector('[data-hm-pro-stats]');
        if (!box) return;
        const st = regionStats();
        if (!st) {
            box.innerHTML = 'Wheel = zoom (at the cursor when panned) · shift+wheel or wheel on the price gutter = rows · drag middle / shift = pan · ←/→ = pan · ↑/↓ = rows · Home = live · ' +
                'Detail = column width (100 ms micro → 5 s long history) · drag = box a region · click = clear it · Mark = pin a level · ' +
                'fit = reset the view · m = minimal · hover a level then Alert to watch it';
            return;
        }
        box.innerHTML = 'selected <b>' + st.buckets + ' &times; ' + st.rows + '</b> cells · resting <b>' + st.total_depth.toFixed(1) +
            '</b> · heaviest <b>' + (st.heaviest.price == null ? '—' : st.heaviest.price) + '</b> (' + st.heaviest.size.toFixed(2) + ')' +
            '<input class="hm-note" data-hm-pro-tol type="number" step="0.1" min="0" placeholder="± tol" title="Price tolerance for the alert level — leave empty for the default, two drawn price steps">' +
            '<input class="hm-note" data-hm-pro-mins type="number" step="1" min="1" placeholder="min" title="How many minutes the level must hold before the hold-alert fires (default 2)">' +
            ' <button class="btn small" data-hm-pro="alert-heavy">Alert: heaviest level</button>' +
            ' <button class="btn small" data-hm-pro="alert-hold">Alert: if this level holds</button>' +
            ' <button class="btn small" data-hm-pro="alert-stack">Alert: stacking here</button>' +
            ' <button class="btn small" data-hm-pro="to-replay">Send region to replay</button>' +
            ' <button class="btn small" data-hm-pro="export-region">Export region CSV</button>' +
            ' <button class="btn small" data-hm-pro="events-region">Events in region</button>' +
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
        });
        c.addEventListener('mouseleave', () => {
            P.hud = null;
            hud();
            if (window.OFAPCURSOR) OFAPCURSOR.clear('heatmap');
        });
        /* §121: the industry grammar. Wheel up = zoom IN; over the price gutter (or with shift) the
           wheel zooms the price rows; tilt wheels and shift-converted axes deliver deltaX, so the
           axis of the delta is read, never assumed. A panned map zooms under the cursor; a live
           map keeps its right edge on the feed. */
        c.addEventListener('wheel', (ev) => {
            if (!active()) return;
            ev.preventDefault();
            const d = ev.deltaY !== 0 ? ev.deltaY : ev.deltaX;
            if (!d || !window.OFAPHEATVIEW) return;
            const g = geom();
            const overGutter = g ? (ev.clientX - g.rect.left) >= g.plotW : false;
            const dir = d < 0 ? -1 : 1;                 // -1 = zoom in
            if (ev.shiftKey || overGutter) { zoomRows(dir); return; }
            const V = OFAPHEATVIEW.state;
            const frac = g ? Math.min(1, Math.max(0, (ev.clientX - g.rect.left) / g.plotW)) : 0.5;
            const out = OFAPHEATVIEW.zoomTime(V, dir, frac, Date.now());
            if (!out.moved) {
                say(dir < 0 ? 'tightest window already — ' + OFAPHEATVIEW.minutesOf(V.cols, V.bucket)
                            : 'widest window already — ' + OFAPHEATVIEW.minutesOf(V.cols, V.bucket));
                return;
            }
            V.cols = out.cols;
            V.until = out.until;
            applyView();
            say(OFAPHEATVIEW.label(V, Date.now()));
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
            /* §121: middle-drag (or shift+left-drag) PANs — Bookmap's own grammar; the plain left
               button stays the region box. This sits before the anchor so a pan is never a box. */
            if (ev.button === 1 || (ev.button === 0 && ev.shiftKey)) {
                ev.preventDefault();
                if (!window.OFAPHEATVIEW) return;
                P.pan = { x0: ev.clientX, until0: OFAPHEATVIEW.state.until, t: 0 };
                try { c.style.cursor = 'grabbing'; } catch (err) { /* ignore */ }
                return;
            }
            /* §120: a CLICK is not a selection — anchor here, box on real movement (mousemove).
               The old code made a zero-size box on mousedown, whose outside-dim covered the
               whole canvas: "click anywhere and it goes darker". */
            P.dragging = true;
            P.born = false;
            P.anchor = { x: Math.max(0, Math.min(ev.clientX - r.left, geom().plotW)),
                         y: Math.max(0, Math.min(ev.clientY - r.top, geom().plotH)) };
        });
        /* §120: the drag tracks on the WINDOW — a box that stops extending at the canvas edge
           (or under the rail/pill) reads as broken; the release and the tracking belong together. */
        window.addEventListener('mousemove', (ev) => {
            if (P.pan) {
                /* §121: live pan — the state follows every move (the chip updates), the fetch is
                   throttled to ~7 Hz so a drag cannot machine-gun the loader, and the release
                   always lands a final load. */
                if (!window.OFAPHEATVIEW) return;
                const g = geom();
                if (!g) return;
                const V = OFAPHEATVIEW.state;
                const probe = { cols: V.cols, rows: V.rows, bucket: V.bucket,
                                haveFrom: V.haveFrom, haveTo: V.haveTo, until: P.pan.until0 };
                const out = OFAPHEATVIEW.panBy(probe, ev.clientX - P.pan.x0, g.plotW, Date.now());
                if (!out.moved) return;
                V.until = out.until;
                const ts = (window.performance && performance.now()) || Date.now();
                if (ts - (P.pan.t || 0) >= 140) { P.pan.t = ts; applyView(); }
                else chip();
                return;
            }
            if (!P.dragging || !P.anchor) return;
            const r = geom().rect;
            const nx = Math.max(0, Math.min(ev.clientX - r.left, geom().plotW));
            const ny = Math.max(0, Math.min(ev.clientY - r.top, geom().plotH));
            if (!P.sel) {
                if (Math.abs(nx - P.anchor.x) >= DRAG_PX || Math.abs(ny - P.anchor.y) >= DRAG_PX) {
                    P.sel = { x0: P.anchor.x, y0: P.anchor.y, x1: nx, y1: ny };
                    P.born = true;
                    draw();
                }
                return;
            }
            P.sel.x1 = nx;
            P.sel.y1 = ny;
            draw();
        });
        window.addEventListener('mouseup', () => {
            if (P.pan) {
                /* §121: the release lands the final load; the label says where the map sits. */
                P.pan = null;
                try { c.style.cursor = ''; } catch (err) { /* ignore */ }
                if (window.OFAPHEATVIEW) {
                    applyView();
                    say(OFAPHEATVIEW.label(OFAPHEATVIEW.state, Date.now()));
                }
                return;
            }
            if (P.dragging) {
                P.dragging = false;
                P.anchor = null;
                /* §121: a plain click is the industry's deselect — a box must disappear on the
                   next click, never linger until a double-click discovers it. */
                if (P.born) { P.born = false; paintStats(); }
                else if (P.sel) {
                    P.sel = null;
                    draw();
                    paintStats();
                    say('selection cleared');
                }
            }
        });
        c.addEventListener('dblclick', () => { P.sel = null; draw(); paintStats(); });
    }

    /* T5/A10: minimal mode — the study's Bookmap pattern: hide the chrome, keep the map and
       every interaction on it. CSS-only, so nothing is switched off behind the user's back;
       the choice itself persists (ui.heatmap_minimal). */
    function minimalOn() {
        const s = document.querySelector('.view[data-view="heatmap"]');
        return !!(s && s.classList.contains('hm-minimal'));
    }
    function setMinimal(on, persist) {
        const s = document.querySelector('.view[data-view="heatmap"]');
        if (s) s.classList.toggle('hm-minimal', !!on);
        const b = document.querySelector('[data-hm-pro="minimal"]');
        if (b) {
            b.classList.toggle('on', !!on);
            b.textContent = on ? 'minimal: on — restore' : 'minimal';
            b.title = on ? 'Bring the panel back (m)' : 'Heatmap + traded volume only — hide the rest of the chrome';
        }
        if (on) say('minimal on — this button stays; click it (or press m) to bring the panel back');
        if (persist && typeof api === 'function') {
            /* /api/control/params takes {path, value} — the registry is the gate, which is why
               ui.heatmap_minimal is registered there. */
            void api('/api/control/params', { method: 'POST', body: { path: 'ui.heatmap_minimal', value: !!on } })
                .catch(function () { /* the toggle still holds for this session */ });
        }
        return !!on;
    }

    function toolbar() {
        const anchor = document.getElementById('hmAuto');
        if (!anchor || document.querySelector('[data-hm-pro-bar]')) return;
        const bar = document.createElement('div');
        bar.setAttribute('data-hm-pro-bar', '1');
        bar.className = 'hm-pro-bar';
        bar.innerHTML = '<button class="btn small" data-hm-pro="zoom-in">zoom +</button>' +
            '<button class="btn small" data-hm-pro="zoom-out">zoom &minus;</button>' +
            '<button class="btn small" data-hm-pro="pan-back" title="pan back in time (\u2190)">\u25c0</button>' +
            '<button class="btn small" data-hm-pro="pan-fwd" title="pan forward in time (\u2192)">\u25b6</button>' +
            '<button class="btn small" data-hm-pro="live" title="The map follows the live edge">\u25cf live</button>' +
            '<button class="btn small" data-hm-pro="rows-up">rows +</button>' +
            '<button class="btn small" data-hm-pro="rows-down">rows &minus;</button>' +
            '<button class="btn small" data-hm-pro="mark">mark level</button>' +
            '<input class="hm-note" data-hm-pro-note type="text" maxlength="120" placeholder="note (optional)" />' +
            '<button class="btn small" data-hm-pro="clear-markers">clear markers</button>' +
            '<button class="btn small" data-hm-pro="fit">fit</button>' +
            '<button class="btn small" data-hm-pro="minimal" title="Heatmap + traded volume only — hide the rest of the chrome">minimal</button>' +
            '<button class="btn small" data-hm-pro="alert-here">alert on cursor level</button>' +
            '<span class="dim" data-hm-pro-info="1"></span>';
        anchor.parentElement.appendChild(bar);
        if (window.OFAPCURSOR) OFAPCURSOR.badge(bar);
        chip();
        const clearBtn = bar.querySelector('[data-hm-pro="clear-markers"]');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                P.markers = [];
                draw(); hud(); paintStats();
                void markersSave();
                say('level markers cleared');
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
        if (act === 'zoom-in') return zoom(-1);      // §121: "in" = fewer minutes, more detail
        if (act === 'zoom-out') return zoom(1);
        if (act === 'pan-back') return panStep(-1);
        if (act === 'pan-fwd') return panStep(1);
        if (act === 'live') { liveNow(); return; }
        if (act === 'rows-up') return zoomRows(1);
        if (act === 'rows-down') return zoomRows(-1);
        if (act === 'mark') {
            P.mode = P.mode === 'mark' ? 'inspect' : 'mark';
            b.style.outline = P.mode === 'mark' ? '1px solid #ffcd5a' : '';
            say(P.mode === 'mark' ? 'mark mode: on — click a level to pin it' : 'mark mode: off');
            return;
        }
        if (act === 'fit') { fitAll(); return; }
        if (act === 'minimal') { setMinimal(!minimalOn(), true); return; }
        if (act === 'clear-sel') {
            P.sel = null; draw(); paintStats();
            const eb = eventsBox(); if (eb) eb.remove();       /* a stale list never stands over an empty map */
            return;
        }
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
        if (act === 'events-region') { paintEvents(); return; }
        if (act === 'export-events') { save('heatmap_events_' + Date.now() + '.csv', csvForEvents()); return; }
        if (act === 'close-events') { const eb = eventsBox(); if (eb) eb.remove(); return; }
    });
    /* P1-9: the heatmap's own keys, registered into the app's one shortcut map. Each one CLICKS
       the real control (found by its data-hm-pro value), so a key can never take a different
       path than the button. */
    if (window.OFAPKEYS) {
        const heatAct = (act) => {
            const b = document.querySelector('[data-hm-pro="' + act + '"]');
            if (b) b.click();
        };
        OFAPKEYS.bind({ id: 'heatmap-zoom-in', keys: ['=', '+'], scope: 'Heatmap', priority: 5,
            label: 'zoom in (depth window)', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => heatAct('zoom-in') });
        OFAPKEYS.bind({ id: 'heatmap-zoom-out', keys: ['-', '_'], scope: 'Heatmap', priority: 5,
            label: 'zoom out (depth window)', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => heatAct('zoom-out') });
        OFAPKEYS.bind({ id: 'heatmap-selection-clear', keys: ['x'], scope: 'Heatmap', priority: 5,
            label: 'clear the selection',
            when: () => OFAPKEYS.inView('heatmap') && P.sel != null, why: 'box a region first', run: () => heatAct('clear-sel') });
        OFAPKEYS.bind({ id: 'heatmap-export', keys: ['ctrl+e'], scope: 'Heatmap', priority: 5,
            label: 'export the selected region as CSV',
            when: () => OFAPKEYS.inView('heatmap') && P.sel != null, why: 'box a region first', run: () => heatAct('export-region') });
        OFAPKEYS.bind({ id: 'alert-from-cursor', keys: ['a'], scope: 'Heatmap', priority: 5,
            label: 'alert on the cursor level', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => heatAct('alert-here') });
        /* §119: the minimal toggle must never be hard to reach again — 'm' is free, obvious,
           and rides the same click-the-real-button path as every other Heatmap key. */
        OFAPKEYS.bind({ id: 'heatmap-minimal', keys: ['m'], scope: 'Heatmap', priority: 5,
            label: 'minimal chrome — the map alone (and back)', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => heatAct('minimal') });
        /* T5/A12: the keyboard reach for what the bar does — rows on the vertical pair, the
           depth window on the horizontal pair, so a reader can step the map without leaving
           the keys. (Shift variants are deliberately absent: rows and windows are stepped
           selectors, there is no 10-px to mean.) */
        OFAPKEYS.bind({ id: 'heatmap-rows-more', keys: ['arrowup'], scope: 'Heatmap', priority: 5,
            label: 'more price rows', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => heatAct('rows-up') });
        OFAPKEYS.bind({ id: 'heatmap-rows-fewer', keys: ['arrowdown'], scope: 'Heatmap', priority: 5,
            label: 'fewer price rows', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => heatAct('rows-down') });
        /* §121: the horizontal arrows PAN — the industry grammar (Bookmap moves the chart with
           them; zoom belongs to the wheel and the +/− pair). The shift pair jumps ten buckets. */
        OFAPKEYS.bind({ id: 'heatmap-pan-back', keys: ['arrowleft'], scope: 'Heatmap', priority: 5,
            label: 'pan back in time', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => panStep(-1) });
        OFAPKEYS.bind({ id: 'heatmap-pan-back-10', keys: ['shift+arrowleft'], scope: 'Heatmap', priority: 5,
            label: 'pan back ten buckets', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => panStep(-10) });
        OFAPKEYS.bind({ id: 'heatmap-pan-fwd', keys: ['arrowright'], scope: 'Heatmap', priority: 5,
            label: 'pan forward in time', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => panStep(1) });
        OFAPKEYS.bind({ id: 'heatmap-pan-fwd-10', keys: ['shift+arrowright'], scope: 'Heatmap', priority: 5,
            label: 'pan forward ten buckets', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => panStep(10) });
        OFAPKEYS.bind({ id: 'heatmap-live', keys: ['home'], scope: 'Heatmap', priority: 5,
            label: 'return to the live edge', when: () => OFAPKEYS.inView('heatmap'), why: 'acts on the Heatmap panel', run: () => liveNow() });
    }

    /* §120: one fetch per window change. atlas.js's loadHeatmap owns the fetch (and the KPI strip,
       the rail and the freshness stamp); this overlay adopts the payload that was just painted
       instead of re-fetching the same endpoint — the old double fetch read as a sluggish wheel,
       and its unsequenced twin could land stale columns on a fast scroll. */
    document.addEventListener('ofap:heat-offer', (ev) => {
        const d = ev && ev.detail && ev.detail.data;
        if (!d || !active()) return;
        P.last = d;
        draw(); hud(); paintStats();
    });

    function refresh() {
        if (!P.minimalSeen) {
            P.minimalSeen = true;
            setMinimal(!!((S.config && S.config.ui && S.config.ui.heatmap_minimal)), false);   // S = ui.js's binding
        }
        if (!active()) return;
        build();
        toolbar();
        const ov = overlay(), c = stage();
        if (ov && c) { ov.style.left = c.offsetLeft + 'px'; ov.style.top = c.offsetTop + 'px'; }
        paintStats();
        /* §120: a click or a relayout repaints from the cache — the map's own auto-refresh keeps
           the data fresh and the offer event keeps this overlay in step; only a cold overlay
           (no data yet) fetches here. Every click used to spend a heatmap fetch. */
        if (P.last) { draw(); hud(); } else { pull(true); }
        wireBucket();
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

    window.HEATMAP_PRO = { state: P, refresh: refresh, pull: pull, zoom: zoom, zoomRows: zoomRows, fitAll: fitAll, listStep: listStep,
                       alertOnLevel: alertOnLevel, sendRegionToReplay: sendRegionToReplay, levelTolerance: levelTolerance,
                           regionStats: regionStats, csvForRegion: csvForRegion, csvForMarkers: csvForMarkers,
                           cellAt: cellAt, dpFor: dpFor, shareOfScale: shareOfScale,
                           deltaPct: deltaPct };
})();
