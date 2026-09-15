/* ofx-view.js — the engine's host: data plumbing, toolbars, HUD, snap-to-live.

   The engine (`ofx.js`) owns pixels and the coordinate matrix; this module owns the boring
   parts — fetching, wiring inputs, and saying what the engine cannot draw yet. */
(function () {
    'use strict';

    const SYM_FALLBACK = 'BTCUSDT';
    const POLL_MS = 2500;
    const view = { symbol: '', timer: 0, booted: false, poll: 0, lastError: '' };

    function el(id) { return document.getElementById(id); }
    function apiGet(path, options) {
        if (typeof api === 'function') return api(path, options);
        return fetch(path, options).then((r) => r.json());
    }
    function sym() {
        return (view.symbol || SYM_FALLBACK).toUpperCase();
    }

    /* ── data: fetch, merge, adapt ───────────────────────────────────────── */

    function mergeBars(footprint, candles, delta) {
        const byDelta = new Map((delta || []).map((d) => [d.time, d.bar_delta ?? d.value]));
        const byVol = new Map((candles || []).map((c) => [c.time, c]));
        return (footprint || []).map((bar) => {
            const c = byVol.get(bar.time) || {};
            const calc = bar.calc || null;
            return {
                time: bar.time, open: bar.open, high: bar.high, low: bar.low, close: bar.close,
                poc: bar.poc, volume: c.volume ?? (calc && calc.volume) ?? bar.volume ?? 0,
                delta: c.delta ?? byDelta.get(bar.time) ?? (calc && calc.delta) ?? 0,
                /* the payload computes volume/buy/sell/delta/POC share/max bid+ask/imbalances per
                   bar; the readout prints them rather than re-deriving anything client-side */
                calc,
            };
        });
    }

    async function load() {
        const s = sym();
        const [fp, candles, delta, tape, heat] = await Promise.all([
            apiGet(`/api/footprint/${s}`).catch(() => []),
            apiGet(`/api/candles/${s}?timeframe=1m`).catch(() => []),
            apiGet(`/api/delta/${s}`).catch(() => []),
            apiGet(`/api/tape/${s}?limit=200`).catch(() => []),
            apiGet(`/api/atlas/heatmap/${s}`).catch(() => ({})),
        ]);
        const bars = mergeBars(fp, candles, delta);
        const levelsByTime = new Map();
        for (const bar of fp || []) levelsByTime.set(bar.time, OFX.indexLevels(bar));
        const barSec = bars.length > 1 ? Math.max(1, bars[bars.length - 1].time - bars[bars.length - 2].time) : 60;
        const adapted = OFX.math.adaptHeat(heat, bars.map((b) => b.time), barSec);
        OFX.state.symbol = s;
        OFX.setData({ bars, levelsByTime, prints: Array.isArray(tape) ? tape : [], heat: adapted || { rows: [], scale: 1 } });
        const notes = [];
        if (!adapted) notes.push(heat && heat.note ? heat.note : 'no depth history yet — it builds while the feed runs');
        if (OFX.state.data.prints.length && !OFX.stats().printsMatched) {
            notes.push(`${OFX.state.data.prints.length} prints outside the drawn bar range — tape and bars are from different feeds right now`);
        }
        view.lastError = notes.join(' · ');
        if (OFX.state.autoFit) OFX.fitHeight();      // never re-fit a price axis the user owns
        OFX.applyLod();
        OFX.applyMode();
        paintStats();
        paintChip();
    }

    /* ── params: the config block is the source of truth ─────────────────── */

    async function loadParams() {
        try {
            const res = await apiGet('/api/control/ofx');
            const p = (res && res.ofx) || {};
            if (p.symbol) view.symbol = String(p.symbol);
            OFX.setParams({
                R: Number(p.R) || OFX.state.params.R,
                stack: Number(p.stack) || OFX.state.params.stack,
                lambda: Number(p.lambda_ms) || OFX.state.params.lambda,
                textPx: Number(p.text_px) || OFX.state.params.textPx,
                sweepC: Number(p.sweep_c) || OFX.state.params.sweepC,
            });
        } catch (err) { /* defaults stand; the engine is usable without saved params */ }
        if (el('ofxSymbol')) el('ofxSymbol').value = sym();
        if (el('ofxR')) el('ofxR').value = String(OFX.state.params.R);
        if (el('ofxStack')) el('ofxStack').value = String(OFX.state.params.stack);
        if (el('ofxLambda')) el('ofxLambda').value = String(OFX.state.params.lambda);
        if (el('ofxMinBlock')) el('ofxMinBlock').value = String(OFX.state.params.minBlock);
        if (el('ofxVaPct')) el('ofxVaPct').value = String(OFX.state.params.vaPct);
    }

    async function saveParams() {
        /* Writes are coalesced by the arbiter: a half-finished number should never reach the server,
           and two saves inside one gesture collapse into one. */
        if (window.OFAPINTENT) return OFAPINTENT.queueWrite('ofx.params', _saveParamsNow);
        return _saveParamsNow();
    }

    async function _saveParamsNow() {
        const body = {
            symbol: sym(),
            R: Number(el('ofxR') && el('ofxR').value) || OFX.state.params.R,
            stack: Number(el('ofxStack') && el('ofxStack').value) || OFX.state.params.stack,
            lambda_ms: Number(el('ofxLambda') && el('ofxLambda').value) || OFX.state.params.lambda,
            text_px: OFX.state.params.textPx,
            sweep_c: OFX.state.params.sweepC,
            min_block: Number(el('ofxMinBlock') && el('ofxMinBlock').value) || 0,
            va_pct: Number(el('ofxVaPct') && el('ofxVaPct').value) || OFX.state.params.vaPct,
        };
        OFX.setParams({ R: body.R, stack: body.stack, lambda: body.lambda_ms,
            minBlock: body.min_block, vaPct: body.va_pct });
        try { await apiGet('/api/control/ofx', { method: 'POST', body }); } catch (err) { /* params already applied */ }
        await load();
    }

    /* ── panels: stats, LOD badge, snap-to-live chip with sparkline ──────── */

    /* ── drawings on the matrix ───────────────────────────────────────────────
       The layer is view-agnostic (it only needs the coordinate transforms), so this is the whole
       integration: hand it the matrix's own transforms and let it paint on top of the stage. The
       adapter stores nothing itself — drawings live in data space (epoch seconds + price). */
    let drawingsMounted = false;
    let drawingSig = '';
    function mountDrawings() {
        if (drawingsMounted || !window.OFAPDRAW) return;
        const stage = el('ofxStage');
        if (!stage) return;
        drawingsMounted = true;
        const bars = () => (window.OFX ? OFX.state.data.bars : []);
        const barSec = () => (window.OFX && OFX.barSeconds ? OFX.barSeconds() : 60);
        OFAPDRAW.attach(stage, {
            symbol: (window.OFX && OFX.state.symbol) || 'BTCUSDT',
            view: 'ofx',
            tickSize: 0.5,
            width: () => OFX.state.view.width,
            height: () => OFX.state.view.height,
            priceToY: (p) => OFX.priceToY(p),
            yToPrice: (y) => OFX.yToPrice(y),
            timeToX: (t) => {
                const list = bars();
                if (!list.length) return 0;
                return OFX.worldX((Number(t) - list[0].time) / barSec());
            },
            xToTime: (x) => {
                const list = bars();
                if (!list.length) return 0;
                return list[0].time + OFX.xToIndex(x) * barSec();
            },
        });
        /* Drawings follow pan and zoom without a per-frame repaint: watch the transform signature. */
        setInterval(() => {
            if (document.hidden || !drawingsMounted) return;
            const v = OFX.state.view;
            const sig = [v.offX, v.offY, v.scaleX, v.scaleY, v.width, v.height]
                .map((n) => Math.round(n * 1000)).join(':');
            if (sig !== drawingSig) { drawingSig = sig; OFAPDRAW.paint(); }
        }, 250);
    }

    /* ── the legend panel ──────────────────────────────────────────────────
       Rendered from `OFX.legend()` so the keys, the layout map and the data dictionary are the
       engine's own account of what it draws, with its live parameters. Nothing here is typed twice:
       a colour the legend shows is a colour in `math.theme`, which is what the renderer reads. */
    function legendSwatch(spec) {
        if (!spec) return '';
        const rgb = spec.rgb ? `rgba(${spec.rgb},${spec.alpha || '.9'})` : '';
        if (spec.type === 'ramp') {
            const stops = [0, 0.25, 0.5, 0.75, 1]
                .map((t) => { const c = OFX.math.heatColor01(t); return `rgb(${c[0]},${c[1]},${c[2]})`; });
            return `<i class="ofx-sw ofx-sw-ramp" style="background:linear-gradient(90deg,${stops.join(',')})"></i>`;
        }
        if (spec.type === 'split') {
            return `<i class="ofx-sw ofx-sw-split"><b style="background:rgba(${spec.rgb},.85)"></b>`
                + `<b style="background:rgba(${spec.rgb2},.85)"></b></i>`;
        }
        if (spec.type === 'rail') {
            return `<i class="ofx-sw ofx-sw-rail"><b style="background:rgba(${spec.rgb},.75)"></b>`
                + `<b style="background:rgba(${spec.rgb2},.75)"></b></i>`;
        }
        if (spec.type === 'outline') return `<i class="ofx-sw ofx-sw-out" style="border-color:${rgb}"></i>`;
        if (spec.type === 'line') return `<i class="ofx-sw ofx-sw-line" style="background:${rgb}"></i>`;
        if (spec.type === 'glyph') return `<i class="ofx-sw ofx-sw-glyph" style="color:${rgb}">${spec.glyph}</i>`;
        if (spec.type === 'text') {
            return `<i class="ofx-sw ofx-sw-text" style="color:${rgb}">${spec.sample || 'abc'}</i>`;
        }
        return `<i class="ofx-sw ofx-sw-solid" style="background:${rgb}"></i>`;
    }

    function paintLegend() {
        const body = el('ofxLegendBody');
        if (!body || typeof OFX.legend !== 'function') return;
        /* Never rebuild under a selection: the panel is meant to be copied out of. */
        const sel = window.getSelection && window.getSelection();
        if (sel && String(sel).length) return;
        const L = OFX.legend();
        const entries = L.entries.map((e) => `<div class="ofx-leg-row">${legendSwatch(e.swatch)}`
            + `<div class="ofx-leg-text"><b>${e.name}</b><span>${e.meaning}</span>`
            + `<em>${e.live}</em></div></div>`).join('');
        const data = L.data.map((d) => `<div class="ofx-leg-row ofx-leg-data">`
            + `<div class="ofx-leg-text"><b>${d.field}</b><span>${d.meaning}</span><em>${d.from}</em></div></div>`).join('');
        const keys = L.interactions.map((i) => `<div class="ofx-leg-key"><kbd>${i.keys}</kbd><span>${i.action}</span></div>`).join('');
        const layout = L.layout.map((l) => `<li>${l}</li>`).join('');
        body.innerHTML = `<div class="ofx-leg-cols">
            <div class="ofx-leg-col">
                <h4>Layout, top to bottom</h4>
                <ol class="ofx-leg-layout">${layout}</ol>
                <h4>Interactions</h4>
                <div class="ofx-leg-keys">${keys}</div>
            </div>
            <div class="ofx-leg-col">
                <h4>Colour keys — what is drawn</h4>
                ${entries}
            </div>
            <div class="ofx-leg-col">
                <h4>Data in, metrics out</h4>
                ${data}
            </div>
        </div>`;
        if (el('ofxLegendSub')) {
            const p = L.params;
            el('ofxLegendSub').textContent = `${L.symbol} · R ${p.R} · stack ${p.stack} · VA ${Math.round(p.vaPct * 100)}% · `
                + `ramp ${p.ramp} · ${L.entries.length} colour keys · ${L.data.length} data fields · ${L.interactions.length} interactions`;
        }
    }

    function bindLegendToggle() {
        const btn = el('ofxLegendToggle');
        const panel = el('ofxLegendPanel');
        if (!btn || !panel) return;
        const KEY = 'ofap.ofx.legend.open';
        let open = true;
        try { open = localStorage.getItem(KEY) !== '0'; } catch (err) { /* private mode */ }
        const apply = () => {
            panel.classList.toggle('ofx-leg-collapsed', !open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            btn.textContent = open ? '▾ legend' : '▸ legend';
        };
        apply();
        btn.addEventListener('click', () => {
            open = !open;
            try { localStorage.setItem(KEY, open ? '1' : '0'); } catch (err) { /* ignore */ }
            if (open) paintLegend();
            apply();
        });
    }

    function paintStats() {
        const s = OFX.stats();
        if (!OFX.state.hover) paintReadout(null);      // keep the panel alive when nothing is hovered
        if (el('ofxStats')) {
            const read = s.aggregating
                ? `rows ${s.cellPx}px → profiles (zoom the price axis in)`
                : `rows ${s.cellPx}px → cells + numbers${s.groupK > 1 ? ` (${s.groupK} ticks/row)` : ''}`
                    + (s.divState !== 'none' ? ` · CVD divergence ${s.divState}` : '')
                    + (s.blocksFiltered ? ` · ${s.blocksFiltered} blocks filtered` : '');
            el('ofxStats').textContent = `${s.frames} frames · ${s.emaMs}ms avg · ${s.p95Ms}ms p95 · max ${s.maxFrameMs}ms · `
                + `${s.lod} · col ${s.colW}px · ${read} · levels ${s.levelCount} · avg ${s.avgLevelVolume}`;
        }
        if (el('ofxLod')) {
            el('ofxLod').textContent = s.lod === 'profile' ? 'LOD: volume profile (text suppressed)' : 'LOD: footprint cells + text';
        }
        if (el('ofxDepthNote')) el('ofxDepthNote').textContent = view.lastError || '';
    }

    function paintChip() {
        const chip = el('ofxSnap');
        if (!chip) return;
        const historical = OFX.state.mode === 'historical';
        chip.classList.toggle('ofx-chip-on', historical);
        chip.textContent = historical ? '⟲ Snap to live market' : '● live';
        const float = el('ofxSnapFloat');
        if (float) float.classList.toggle('on', historical);      // bottom-right badge, only when history is in view
        paintSpark(el('ofxSpark'));
        paintSpark(el('ofxSpark2'));
    }

    function paintSpark(spark) {
        if (!spark) return;
        const ctx = spark.getContext('2d');
        const closes = OFX.state.data.bars.slice(-60).map((b) => Number(b.close) || 0);
        ctx.clearRect(0, 0, spark.width, spark.height);
        if (closes.length < 2) return;
        const lo = Math.min(...closes), hi = Math.max(...closes);
        const up = closes[closes.length - 1] >= closes[0];
        ctx.strokeStyle = up ? '#35d07f' : '#ff5d6c';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        closes.forEach((c, i) => {
            const x = (i / (closes.length - 1)) * (spark.width - 2) + 1;
            const y = spark.height - 2 - ((c - lo) / Math.max(1e-9, hi - lo)) * (spark.height - 4);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
    }


    /* ── the readout: every metric the cursor is standing on ───────────────
       The engine hands `OFX.state.hover` a complete picture (the bar's own statistics from the
       footprint payload, the level under the cursor, its imbalance, the stacked zone it belongs to,
       depth at that price, prints and sweeps in the bar, book events in the bar). This panel prints
       it as text, so the numbers are readable, selectable and copyable — the canvas keeps the
       picture, this keeps the facts. */

    const fmtP = (v, d) => (v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d));
    const fmtV = (v) => {
        const n = Number(v);
        if (!Number.isFinite(n)) return '—';
        if (Math.abs(n) >= 1000) return n.toFixed(0);
        if (Math.abs(n) >= 1) return n.toFixed(2);
        if (Math.abs(n) >= 0.01) return n.toFixed(3);
        return n.toPrecision(2);
    };
    const fmtT = (sec) => {
        const d = new Date((Number(sec) || 0) * 1000);
        return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
            + ':' + String(d.getSeconds()).padStart(2, '0');
    };
    const row2 = (label, value, cls) => `<div class="ofx-ro-row"><span class="ofx-ro-k">${label}</span><span class="ofx-ro-v ${cls || ''}">${value}</span></div>`;

    function paintReadout(h) {
        const box = el('ofxReadout');
        if (!box) return;
        const sym = OFX.state.symbol;
        if (!h || !h.bar) {
            const s = OFX.stats();
            const lim = OFX.viewBounds ? OFX.viewBounds() : {};
            box.innerHTML = `<div class="ofx-ro-title">${sym} · engine</div>`
                + row2('bars', String(OFX.state.data.bars.length))
                + row2('in view', String(s.barsOnScreen != null ? s.barsOnScreen : s.visibleBars || '—'))
                + row2('LOD', s.lod + (s.groupK > 1 ? ` · ${s.groupK} ticks/row` : ''))
                + row2('price band', lim.lo != null ? `${fmtP(lim.lo, 2)} – ${fmtP(lim.hi, 2)}` : '—')
                + row2('depth cells', String(s.heatCells))
                + row2('flow marks', `${s.flowBubbles || 0} vol · ${s.flowEvents || 0} events`)
                + row2('recovered', String(s.recovered || 0))
                + `<div class="ofx-ro-hint">move the cursor over the matrix</div>`;
            return;
        }
        const bar = h.bar;
        const c = h.calc || {};
        const s = OFX.stats();
        const lim = OFX.viewBounds ? OFX.viewBounds() : {};
        const cls = (v) => (Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : '');
        const imbalance = c.imbalances && c.imbalances.length ? c.imbalances.length : null;
        box.innerHTML = `<div class="ofx-ro-title">${sym} · ${fmtT(h.barTime)}</div>`
            + row2('O / H', `${fmtP(bar.open, 2)} / ${fmtP(bar.high, 2)}`)
            + row2('L / C', `${fmtP(bar.low, 2)} / ${fmtP(bar.close, 2)}`)
            + row2('volume', fmtV(c.volume != null ? c.volume : bar.volume))
            + row2('buy / sell', `${fmtV(c.buy)} / ${fmtV(c.sell)}`)
            + row2('delta', `${c.delta > 0 ? '+' : ''}${fmtV(c.delta)}`, cls(c.delta))
            + row2('CVD', `${h.cvd > 0 ? '+' : ''}${fmtV(h.cvd)}`, cls(h.cvd))
            + row2('POC', c.poc ? `${fmtP(c.poc.price, 2)} · ${fmtP(c.poc.share_pct, 1)}%` : fmtP(bar.poc, 2))
            + row2('max bid / ask', c.max_bid && c.max_ask
                ? `${fmtP(c.max_bid.price, 2)} (${fmtV(c.max_bid.volume)}) / ${fmtP(c.max_ask.price, 2)} (${fmtV(c.max_ask.volume)})`
                : '—')
            + row2('levels', `${c.rows != null ? c.rows : (OFX.state.data.levels.get(bar.time) || []).length}`
                + (imbalance ? ` · ${imbalance} imb` : ''))
            + `<div class="ofx-ro-sep"></div>`
            + row2('cursor', fmtP(h.price, 2))
            + row2('level', h.level ? `${fmtP(h.level.price, 2)}` : '—')
            + row2('bid / ask', h.level ? `${fmtV(h.level.bid)} / ${fmtV(h.level.ask)}` : '—')
            + row2('imbalance', h.imbalance && h.imbalance.side
                ? `${h.imbalance.side} ${h.imbalance.ratio === Infinity ? '∞' : fmtP(h.imbalance.ratio, 1)}x`
                : 'none', h.imbalance && h.imbalance.side ? 'hot' : '')
            + row2('zone', h.zone ? `${h.zone.side} ${h.zone.count}L` : '—', h.zone ? 'hot' : '')
            + row2('depth here', fmtV(h.depth))
            + row2('prints / sweep', `${h.prints} · ${fmtV(h.sweep)}`)
            + row2('book events', h.events.length
                ? h.events.slice(0, 2).map((e) => `${e.kind}${e.direction === 'ask' ? '↑' : '↓'}`).join(' ')
                : '—')
            + `<div class="ofx-ro-sep"></div>`
            + row2('in view', `${s.barsOnScreen != null ? s.barsOnScreen : '—'} bars`)
            + row2('price band', lim.lo != null ? `${fmtP(lim.lo, 2)} – ${fmtP(lim.hi, 2)}` : '—')
            + row2('recovered', String(s.recovered || 0));
    }

    /* The trace: a DOM line at the cursor's price stretching toward the ladder, plus the price
       itself, so the eye never has to re-find the level in another panel. DOM, not canvas, so it
       cannot disturb the engine's own layers. */
    function paintTrace(h) {
        const stage = el('ofxStage');
        if (!stage) return;
        let line = el('ofxTrace');
        if (!line) {
            line = document.createElement('div');
            line.id = 'ofxTrace';
            line.className = 'ofx-trace';
            stage.appendChild(line);
        }
        const y = (h && h.y != null) ? h.y
            : (h && h.price != null && typeof OFX.priceToY === 'function') ? OFX.priceToY(h.price) : null;
        if (!h || y == null) { line.style.display = 'none'; OFAPCURSOR.clear('ofx'); return; }
        line.style.display = 'block';
        line.style.top = Math.round(y) + 'px';
        /* 77586.03620136363 is not a price anyone reads: show the instrument's granularity. */
        line.textContent = h.price != null
            ? (h.price >= 1000 ? h.price.toFixed(2) : h.price >= 1 ? h.price.toFixed(3) : h.price.toFixed(5))
            : '';
        OFAPCURSOR.move(h.price, h.time != null ? h.time : null, 'ofx');
    }

    function paintTip(h) {
        paintTrace(h);
        const tip = el('ofxTip');
        if (!tip) return;
        if (!h) { tip.style.display = 'none'; return; }
        /* Local clock, the same one the ruler and the readout use: an ISO/UTC string here read as a
           different session than the axis drawn 200 px below it. The panel carries the full metric
           set, so the tag stays to three lines. */
        const hot = h.imbalance && h.imbalance.side ? ' class="ofx-tip-hot"' : '';
        const flag = h.zone
            ? `${h.zone.side} · ${h.zone.count}L stacked`
            : (h.imbalance && h.imbalance.side
                ? `${h.imbalance.side} ${h.imbalance.ratio === Infinity ? '∞' : h.imbalance.ratio.toFixed(1)}x`
                : 'balanced');
        tip.innerHTML = `<b>${fmtT(h.barTime)} · ${fmtP(h.price, 2)}</b>`
            + (h.level ? `<div>${fmtP(h.level.price, 2)} — bid ${fmtV(h.level.bid)} / ask ${fmtV(h.level.ask)}</div>` : '')
            + `<div${hot}>${flag} · delta ${fmtV(h.bar.delta)} · CVD ${fmtV(h.cvd)}</div>`;
        tip.style.display = 'block';
        const stage = el('ofxStage');
        const w = stage ? stage.clientWidth : 0;
        tip.style.left = `${Math.min(h.x + 14, Math.max(8, w - 250))}px`;
        tip.style.top = `${Math.max(8, h.y - 12)}px`;
    }

    /* ── boot ────────────────────────────────────────────────────────────── */

    function stageSize() {
        const stage = el('ofxStage');
        if (!stage) return null;
        /* Exactly the box the layers are stretched to, with no floor and no inset.
           The engine's pointer maths reads `getBoundingClientRect`, so its internal space and this
           box have to be the same thing: the old `Math.max(240, clientHeight - 8)` made the internal
           space TALLER than a widget's stage (240 against 148 measured), which put the price under
           the cursor — and the trace line naming it — somewhere else on the chart.
           A hidden stage measures 0x0, and 0 is not a size to draw at, so it reports no size at all
           and the caller keeps the last real one. */
        const w = stage.clientWidth, h = stage.clientHeight;
        if (w < 2 || h < 2) return null;
        return { w: w, h: h };
    }

    /* The ladder's grid step: the smallest positive gap between the prices it actually draws. It is
       the only honest tolerance for 'this row is the cursor's price' — see the subscriber below. */
    function ladderStep(prices) {
        const sorted = prices.slice().sort((a, b) => a - b);
        let step = Infinity;
        for (let i = 1; i < sorted.length; i += 1) {
            const d = sorted[i] - sorted[i - 1];
            if (d > 0 && d < step) step = d;
        }
        return Number.isFinite(step) ? step : null;
    }

    /* The cursor is shared: whoever moves it, every panel can read it. The ladder highlights the
       nearest price it actually draws, and says so when that price is off its ladder. */
    function wireCursorLink() {
        /* Its own line: the view already writes to ofxDepthNote (tape/bars mismatches), and two
           writers on one element means one of them is always lost. */
        let note = el('ofxCursorNote');
        if (!note) {
            const row = el('ofxDepthNote') && el('ofxDepthNote').parentElement;
            if (row) {
                note = document.createElement('span');
                note.id = 'ofxCursorNote';
                note.className = 'dim';
                row.insertBefore(note, el('ofxDepthNote'));
            }
        }
        OFAPCURSOR.subscribe((c) => {
            const rowHost = el('orderbookLadder');
            let matched = null;
            if (rowHost && c.price != null) {
                const rows = [...rowHost.querySelectorAll('[data-price]')];
                const prices = rows.map((r) => Number(r.dataset.price)).filter((p) => Number.isFinite(p));
                /* Bounded by one step of the ladder's own grid. With a `null` tolerance the nearest
                   drawn price came back however far away it was, so a cursor 40 points off a 15-level
                   ladder was still announced as 'on the ladder'. Outside the band means outside. */
                matched = OFAPCURSOR.nearest(prices, ladderStep(prices));
                /* The ladder rebuilds its rows on every update, so hand the price to the ladder (state
                   it re-applies on each render) instead of toggling a class the next poll would drop.
                   A ladder without that hook keeps the plain class toggle. */
                if (typeof rowHost.setTrace === 'function') rowHost.setTrace(matched);
                else rows.forEach((r) => r.classList.toggle('ofx-traced', Number(r.dataset.price) === matched));
            } else if (rowHost && typeof rowHost.setTrace === 'function') {
                rowHost.setTrace(null);          /* leaving the canvas clears the row, like the line */
            }
            if (note) {
                note.textContent = c.price == null ? ''
                    : (matched != null
                        ? 'cursor ' + c.price + ' · on the ladder'
                        : 'cursor ' + c.price + ' · outside the drawn ladder levels');
            }
        });
    }

    /* ── P1-3: the selection strip ────────────────────────────────────────────────────────────────
       The engine owns the box and the arithmetic (`math.selectionStats` is selftested); this prints
       the numbers on their own line beside the stage and exports them as a real file over the same
       route the heatmap's exports use. Its own element, so a hover repaint cannot wipe it. */
    function selCell(label, value, cls) {
        return '<div class="ofx-sel-cell' + (cls ? ' ' + cls : '') + '"><span class="ofx-sel-k">' + label
            + '</span><span class="ofx-sel-v">' + value + '</span></div>';
    }

    function paintSelStrip(st) {
        const stage = el('ofxStage');
        if (!stage) return;
        let box = el('ofxSelFloat');
        if (!box) {
            box = document.createElement('div');
            box.id = 'ofxSelFloat';
            box.className = 'ofx-sel-float';
            stage.appendChild(box);
        }
        if (!st || !st.bars) {
            box.style.display = 'none';
            if (window.OFAPCURSOR) OFAPCURSOR.select(null, { source: 'ofx-selection' });
            return;
        }
        box.style.display = 'block';
        /* The tape buffer covers the last few seconds and the footprint payload publishes closed
           bars, so a window over closed bars can legitimately hold no prints. Say which it is. */
        const tapeTimes = (OFX.state.data.prints || []).map((p) => Number(p.time)).filter(Number.isFinite);
        const buffer = tapeTimes.length ? [Math.min(...tapeTimes), Math.max(...tapeTimes)] : null;
        const why = (st.prints === 0 && buffer)
            ? 'tape buffer ' + fmtT(buffer[0]) + '–' + fmtT(buffer[1]) + ' is outside the selected window '
              + '(closed bars only) — no prints to measure here'
            : '';
        const pr = (v) => (v == null ? '—' : v >= 1000 ? fmtP(v, 2) : v >= 1 ? fmtP(v, 3) : fmtP(v, 5));
        const vv = (v) => (v == null ? '—' : fmtV(v));
        const cls = (v) => (Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : '');
        box.innerHTML = '<div class="ofx-sel-head">selection'
            + '<span class="ofx-sel-dim">' + st.bars + ' bars · ' + fmtT(st.t0) + '–' + fmtT(st.t1)
            + ' · ' + pr(st.p0) + '–' + pr(st.p1) + '</span>'
            + '<button class="btn small" data-ofx-sel="export">Export CSV</button>'
            + '<button class="btn small" data-ofx-sel="clear">Clear</button></div>'
            + '<div class="ofx-sel-grid">'
            + selCell('volume', vv(st.volume))
            + selCell('delta', (st.delta > 0 ? '+' : '') + vv(st.delta), cls(st.delta))
            + selCell('buy / sell', vv(st.buy) + ' / ' + vv(st.sell))
            + selCell('prints', String(st.prints) + ' · ' + vv(st.printSize))
            + selCell('VWAP', pr(st.vwap))
            + selCell('largest', st.largest ? vv(st.largest.size) + ' @ ' + pr(st.largest.price) : '—')
            + selCell('resting', st.restingChange == null ? '—'
                : (st.restingChange > 0 ? '+' : '') + vv(st.restingChange),
                st.restingChange == null ? '' : cls(st.restingChange))
            + '</div>'
            + (why ? '<div class="ofx-sel-why">' + why + '</div>' : '')
            + '<div class="ofx-sel-note" id="ofxSelNote"></div>';
        /* A selection IS a price and a time window, so it rides on the shared cursor: every other
           panel can answer it without knowing this one exists. The price cursor itself is left
           alone — the selection is a band, not the pointer. */
        if (window.OFAPCURSOR) {
            OFAPCURSOR.select({ t0: st.t0, t1: st.t1, p0: st.p0, p1: st.p1, bars: st.bars },
                { source: 'ofx-selection' });
        }
    }

    /* The file lands in the app's own exports folder (a pywebview shell has no download shelf), and
       the path it returns is printed on the strip's own line. */
    async function exportSelection() {
        const st = OFX.selectionStats();
        if (!st || !st.bars) return;
        const note = el('ofxSelNote');
        const sym = String(OFX.state.symbol || view.symbol || 'symbol').toUpperCase();
        const iso = (t) => new Date((Number(t) || 0) * 1000).toISOString();
        const stamp = iso(st.t0).replace(/[-:]/g, '').replace(/\..+/, '');
        const rows = [
            ['# ModFlow OrderFlow Analysis Suite - engine selection export'],
            ['# symbol', sym],
            ['# window', iso(st.t0) + ' .. ' + iso(st.t1) + ' (' + st.bars + ' bars, ' + st.barSec + 's)'],
            ['# price band', String(st.p0), String(st.p1)],
            ['# volume', String(st.volume)],
            ['# delta', String(st.delta)],
            ['# buy', String(st.buy)],
            ['# sell', String(st.sell)],
            ['# prints', String(st.prints)],
            ['# print size', String(st.printSize)],
            ['# vwap', st.vwap == null ? '' : String(st.vwap)],
            ['# largest', st.largest ? st.largest.size + ' @ ' + st.largest.price : ''],
            ['# resting change', st.restingChange == null ? '' : String(st.restingChange)],
            ['# exported', new Date().toISOString()],
            [],
            ['bar_time', 'iso', 'open', 'high', 'low', 'close', 'volume', 'delta'],
        ];
        for (const b of st.barRows) {
            rows.push([String(b.time), iso(b.time), b.open, b.high, b.low, b.close, b.volume, b.delta]);
        }
        rows.push([]);
        rows.push(['print_time', 'iso', 'price', 'size', 'side']);
        for (const p of st.printRows) {
            rows.push([String(p.time), iso(p.time), p.price, p.size, p.side]);
        }
        const text = rows.map((r) => r.join(',')).join('\n') + '\n';
        const name = 'ofx-selection-' + sym + '-' + stamp + '.csv';
        if (note) note.textContent = 'saving…';
        try {
            const res = await fetch('/api/control/export/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, text: text }),
            });
            const body = await res.json().catch(() => ({}));
            if (note) {
                note.textContent = res.ok ? 'saved · ' + (body.path || name) : 'export failed (' + res.status + ')';
            }
        } catch (err) {
            if (note) note.textContent = 'export failed: ' + (err && err.message ? err.message : 'network');
        }
    }

    async function ofxInit() {
        if (view.booted) return;
        const stage = el('ofxStage');
        if (!stage) return;
        view.booted = true;

        await loadParams();
        const size = stageSize();
        OFX.attach(el('ofxBase'));
        /* Hand over the engine's other three canvases. The depth heatmap, the execution
           sweeps + crosshair HUD and the CVD ribbon each paint into their own layer, and
           they only paint when the view attaches them: with all three left null the engine
           kept computing them, kept their dirty flags set and never drew a pixel. */
        OFX.state.layers.heat = el('ofxHeat');
        OFX.state.layers.live = el('ofxLive');
        OFX.state.layers.ribbon = el('ofxRibbon');
        if (size) OFX.resize(size.w, size.h);
        OFX.state.onHover = (h) => { paintTip(h); paintReadout(h); };
        OFX.state.onMode = () => { paintChip(); };
        OFX.state.onSelection = (st) => { paintSelStrip(st); };
        OFX.start();

        if (el('ofxSnap')) el('ofxSnap').addEventListener('click', () => { OFX.snapToLive(); paintChip(); });
        if (el('ofxFit')) el('ofxFit').addEventListener('click', () => { OFX.fitSession(); paintChip(); });
        /* Double-click on the stage = show the whole session; the same thing the fit button does. */
        const stageEl = el('ofxStage');
        if (stageEl) stageEl.addEventListener('dblclick', () => { OFX.fitSession(); paintChip(); });
        /* The selection strip's own buttons. Delegated from the stage, because the strip is rebuilt
           on every selection change. */
        if (stageEl) stageEl.addEventListener('click', (ev) => {
            const btn = ev.target && ev.target.closest ? ev.target.closest('[data-ofx-sel]') : null;
            if (!btn) return;
            const what = btn.getAttribute('data-ofx-sel');
            if (what === 'clear') OFX.clearSelection();
            else if (what === 'export') void exportSelection();
        });
        if (el('ofxApply')) el('ofxApply').addEventListener('click', () => void saveParams());
        wireCursorLink();
        /* The spine's badge, beside the engine's own stats line: the engine is one of the panels that
           reads the shared cursor, so it carries the same tag as the rest. */
        if (window.OFAPCURSOR) {
            const head = document.querySelector('.view[data-view="ofx"] .view-head');
            if (head) OFAPCURSOR.badge(head);
        }
        /* The ramp is a display preference, so it lives with the view, not the engine config: it is
           applied immediately and remembered across restarts without a server round-trip. */
        if (el('ofxRamp')) {
            const saved = (() => { try { return window.localStorage.getItem('ofx.ramp'); } catch (e) { return null; } })();
            if (saved === 'thermal' || saved === 'classic') el('ofxRamp').value = saved;
            const apply = () => {
                if (typeof OFX.setParams === 'function') OFX.setParams({ ramp: el('ofxRamp').value });
                try { window.localStorage.setItem('ofx.ramp', el('ofxRamp').value); } catch (e) { /* private mode */ }
            };
            el('ofxRamp').addEventListener('change', apply);
            apply();
        }
        if (el('ofxSymbol')) el('ofxSymbol').addEventListener('change', () => {
            view.symbol = (el('ofxSymbol').value || SYM_FALLBACK).toUpperCase();
            void saveParams();
        });
        if (el('ofxSnapLive')) el('ofxSnapLive').addEventListener('click', () => { OFX.snapToLive(); paintChip(); });
        if (el('ofxSnapFloat')) el('ofxSnapFloat').addEventListener('click', () => { OFX.snapToLive(); paintChip(); });
        ['ofxMinBlock', 'ofxVaPct'].forEach((id) => {
            if (el(id)) el(id).addEventListener('change', () => void saveParams());
        });
        window.addEventListener('resize', () => {
            const s2 = stageSize();
            if (s2) OFX.resize(s2.w, s2.h);
        });
        /* A re-parent or a frame resize is NOT a window resize: the shell announces those through
           `ofap:relayout`. Without this the layers keep the size they had in Classic mode and the
           widget draws a matrix computed for a bigger stage (measured: 293x240 inside 213x148). */
        document.addEventListener('ofap:relayout', () => {
            const s3 = stageSize();
            if (s3) OFX.resize(s3.w, s3.h);
        });

        try {
            await load();
        } catch (err) {
            view.lastError = `feed error: ${err}`;
            paintStats();
        }
        /* The pause registry clears the interval on pause and calls this back on resume, so the
           callback has to rebuild the poll - registering a one-shot load here meant a single
           pause/resume stopped the Engine view's updates for the rest of the session. */
        const startPolling = () => {
            const id = setInterval(() => {
                if (window.OFAPINTENT && OFAPINTENT.held('ofx')) return;   // never reload under the user's hands
                if (document.hidden || window.OFAP_PAUSED) return;      // freeze-while-you-work
                void load();
            }, POLL_MS);
            if (window.OFAPPause) window.OFAPPause.register(id, startPolling);
            return id;
        };
        view.timer = startPolling();
        /* One timer, one cadence: the stats line every second, the legend's live numbers every
           fifth tick. (A separate timer guarded on a flag that does not exist never fired.) */
        let legendTicks = 0;
        setInterval(() => {
            paintStats();
            legendTicks += 1;
            if (legendTicks % 5 === 0) paintLegend();
        }, 1000);
        paintLegend();
        bindLegendToggle();
        mountDrawings();                 // the drawing layer rides on the matrix's own transforms
        ofxRegisterHelp();
    }

    function ofxRegisterHelp() {
        if (typeof HELP_TOPICS !== 'undefined' && !HELP_TOPICS.ofx) {
            HELP_TOPICS.ofx = {
                title: 'Order-flow engine (footprint matrix + depth heatmap)',
                lead: 'The legend panel under the stage names every colour, the layout and every data '
                    + 'field; the matrix itself: DOM liquidity behind, split-candle footprint in front, '
                    + 'sweeps and the crosshair HUD on top, CVD ribbon beneath.',
                body: [
                    'Shift+wheel zooms time only; wheel zooms price only — the two scales are independent.',
                    'Drag pans both axes. Below 45px per bar the text is suppressed and the view '
                    + 'interpolates into volume profiles (LOD).',
                    'Scrolling left of the newest bar switches to Historical Analysis Mode and raises the '
                    + 'snap-to-live chip with a live sparkline.',
                    'R is the diagonal imbalance ratio (Bid[Y] vs Ask[Y+1]); stacks need at least 3 adjacent '
                    + 'levels once R is cleared. Lambda sets the depth fade (500ms = one e-fold).',
                ],
            };
        }
    }

    /* The view can be activated by a nav click, the URL hash, or a guide link — watch the
       section's class rather than assuming a click, which is how the earlier views raced. */
    function watchView() {
        const section = document.querySelector('.view[data-view="ofx"]');
        if (!section) return;
        /* Coming back on screen re-measures. A resize that happened while the view was hidden (the
           switch to and from Terminal mode, a tab switch) is refused by `stageSize()`, so without
           this the canvas keeps whatever size it measured in the other arrangement. */
        const refit = () => {
            if (!view.booted) return;
            const size = stageSize();
            if (size) OFX.resize(size.w, size.h);
        };
        if (section.classList.contains('active')) void ofxInit();
        new MutationObserver(() => {
            if (!section.classList.contains('active')) return;
            void ofxInit();
            refit();
        }).observe(section, { attributes: true, attributeFilter: ['class'] });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchView);
    else watchView();
})();
