/* ofx-view.js — the engine's host: data plumbing, toolbars, HUD, snap-to-live.

   The engine (`ofx.js`) owns pixels and the coordinate matrix; this module owns the boring
   parts — fetching, wiring inputs, and saying what the engine cannot draw yet. */
(function () {
    'use strict';

    const SYM_FALLBACK = 'BTCUSDT';
    const POLL_MS = 2500;
    const view = { symbol: '', timer: 0, booted: false, poll: 0, lastError: '' };
    /* §82: the look-up's last answer for the typed symbol — the chip, the panel and the
       stage note all read this one object, so they can never disagree. */
    let streamState = null;

    function instrumentMod() { return window.OFAPINSTRUMENT || null; }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

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
        /* §82: a failed read is remembered, never swallowed. The footprint route answers 404
           "Unknown symbol" for anything the engine does not stream, and the old blanket
           `.catch(() => [])` turned that sentence into a blank stage with a note about depth
           history "building" — a promise nothing would keep. The first error is what the
           panel says when no bar came back. */
        const fetchErrors = [];
        const grab = (path, fallback) => apiGet(path).catch((err) => {
            fetchErrors.push(`${path}: ${(err && err.message) ? err.message : err}`);
            return fallback;
        });
        const [fp, candles, delta, tape, heat, reads] = await Promise.all([
            grab(`/api/footprint/${s}`, []),
            grab(`/api/candles/${s}?timeframe=1m`, []),
            grab(`/api/delta/${s}`, []),
            grab(`/api/tape/${s}?count=200`, []),            /* §56 measured: the JSON route parses+adapts a 29 k-cell snapshot in 0.8 ms and the
               typed /bin sibling in 0.7 ms — and the bin is BIGGER on sparse books (fixed 4 B per
               cell per section vs "0,"). The JSON route stays the view's path; the wire is built,
               tested and available, re-measure it when a snapshot's JSON text passes ~2 MB or an
               adapt pass passes ~8 ms. (What §56 actually fixed here was the axis contract — see
               adaptHeat's note.) */
            grab(`/api/atlas/heatmap/${s}`, {}),
            /* §3 level reads: unfinished auctions + node runs. `null` (not []) so a symbol the
               trackers have not seen draws nothing rather than an invented level. */
            grab(`/api/atlas/levels/${s}`, null),
        ]);
        const bars = mergeBars(fp, candles, delta);
        const levelsByTime = new Map();
        for (const bar of fp || []) levelsByTime.set(bar.time, OFX.indexLevels(bar));
        const barSec = bars.length > 1 ? Math.max(1, bars[bars.length - 1].time - bars[bars.length - 2].time) : 60;
        const adapted = OFX.math.adaptHeat(heat, bars.map((b) => b.time), barSec);
        /* P2-2: the server's matrix version rides along — an unchanged version (the cached
           snapshot) is not repainted again. */
        if (adapted) adapted.version = heat && heat.version;
        OFX.state.symbol = s;
        OFX.setData({ bars, levelsByTime, prints: Array.isArray(tape) ? tape : [], heat: adapted || { rows: [], scale: 1 } });
        OFX.setReads(reads || {});
        /* P1-10: the age of what this view drew — the newest merged bar's own clock; a demo fill
           (the server says 'demo') is labelled from the live map instead of aged. */
        if (window.OFAPFRESH) {
            /* A closed bar's `time` is its OPEN — the sample is the CLOSE (open + the bar's own
               interval, measured from the series), or a healthy 1m panel would read stale. */
            OFAPFRESH.stamp('ofx', { lastMs: bars.length ? (Number(bars[bars.length - 1].time) + barSec) * 1000 : 0, kind: 'candles',
                source: (typeof liveState === 'function' && liveState('footprint') === 'demo') ? 'demo' : '' });
        }
        /* The depth map carries liquidity forward between windows; ghost levels with no explanation
           are a lie of omission, so the flag rides on the state and the note below says it. */
        OFX.state.data.heatCarry = !!(heat && heat.carry_forward);
        /* §82: one sentence about what this symbol IS outranks every "give it time" note — the
           look-up's verdict (not enabled / not on this source / unknown), then a real failed
           read, and only then the warming-up explanations. */
        const notes = [];
        const instrument = instrumentMod();
        const stateName = (streamState && instrument) ? instrument.state(streamState) : '';
        const streamable = !stateName || stateName === 'live' || stateName === 'ready';
        if (!streamable && instrument) {
            notes.push(instrument.emptyNote(streamState));
        } else if (!bars.length && fetchErrors.length) {
            notes.push(fetchErrors[0]);
        } else if (!adapted) {
            notes.push(heat && heat.note ? heat.note : 'no depth history yet — it builds while the feed runs');
        }
        if (OFX.state.data.heatCarry && adapted) {
            notes.push('ghost liquidity carried forward — levels that left the drawn window are still shown');
        }
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
                /* B2: the heat dials ride the same block; an absent key is skipped by setParams'
                   own guards, so an older config keeps the shipped look. */
                heatContrast: p.heat_contrast, heatFloor: p.heat_floor, heatFloorPct: p.heat_floor_pct,
                heatSmooth: p.heat_smooth,
                /* P1-8: the depth ramp is a stored display parameter now — it used to live only in
                   browser storage, which config_store's own rule says is never the record. */
                ramp: p.ramp || OFX.state.params.ramp,
            });
        } catch (err) { /* defaults stand; the engine is usable without saved params */ }
        if (el('ofxSymbol')) el('ofxSymbol').value = sym();
        if (el('ofxR')) el('ofxR').value = String(OFX.state.params.R);
        if (el('ofxStack')) el('ofxStack').value = String(OFX.state.params.stack);
        if (el('ofxLambda')) el('ofxLambda').value = String(OFX.state.params.lambda);
        if (el('ofxMinBlock')) el('ofxMinBlock').value = String(OFX.state.params.minBlock);
        if (el('ofxVaPct')) el('ofxVaPct').value = String(OFX.state.params.vaPct);
        if (el('ofxRamp')) el('ofxRamp').value = String(OFX.state.params.ramp);
        syncHeatControls();
    }

    /* ── P1-8: the bar expression, read and written through the config ───────────────────────
       GET gives the stored value; every change is applied locally FIRST (so the picture follows the
       control immediately) and then reconciled with what the store accepted — the store is the
       authority, and `adopt` is what puts its answer back on the control. */
    async function loadExpression() {
        let block = null;
        try {
            const res = await apiGet('/api/control/expression');
            block = (res && res.expression) || null;
        } catch (err) { /* the catalogue's defaults stand; the engine is usable without saved state */ }
        const eng = (block && block.engine) || {};
        adoptExpression({ mode: eng.mode, palette: eng.palette });
        return eng;
    }

    function adoptExpression(next) {
        if (!window.OFAPEXPR) return;
        const applied = OFX.setExpression({ mode: next.mode, palette: next.palette });
        if (el('ofxMode')) el('ofxMode').value = applied.mode;
        if (el('ofxPalette')) el('ofxPalette').value = applied.palette;
        paintLegend();
    }

    async function saveExpression(patch) {
        try {
            const res = await apiGet('/api/control/expression', {
                method: 'POST', body: Object.assign({ chart: 'engine' }, patch),
            });
            if (res && res.ok === false) { view.lastError = `expression refused: ${res.error}`; paintStats(); return; }
            /* Adopt the value the STORE accepted: a junk mode comes back as `default`, and the
               control has to show that rather than the word that was typed. */
            const value = (res && res.value) || {};
            adoptExpression({ mode: value.mode, palette: value.palette });
        } catch (err) {
            view.lastError = `expression save failed: ${err}`;
            paintStats();
        }
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
            /* B2 fix: the ramp select saved a body WITHOUT `ramp`, so the stored value never left
               the shipped default — the store has always accepted the key; nobody sent it. */
            ramp: OFX.state.params.ramp,
        };
        OFX.setParams({ R: body.R, stack: body.stack, lambda: body.lambda_ms,
            minBlock: body.min_block, vaPct: body.va_pct });
        try { await apiGet('/api/control/ofx', { method: 'POST', body }); } catch (err) { /* params already applied */ }
        await load();
    }

    /* ── B2: the heat scheme, one write path for both surfaces ──────────────────────────────────
       Every dial is a registered display variable, so it persists through /api/control/params —
       the registry is the gate, and the answer echoes what the store ACCEPTED (clamped), which is
       what the controls adopt. Nothing here touches the feed or the ingest: it is drawing only. */

    const HEAT_PATHS = {
        ofx: { contrast: 'ofx.heat_contrast', floor: 'ofx.heat_floor', floorPct: 'ofx.heat_floor_pct' },
        heatmap: { contrast: 'atlas.heatmap.contrast', floor: 'atlas.heatmap.floor',
            floorPct: 'atlas.heatmap.floor_pct' },
    };

    function heatCfg() {
        return (typeof S !== 'undefined' && S && S.config) || null;
    }

    function heatNote(text) {
        if (!text) return;
        view.lastError = text;
        paintStats();
    }

    function heatDials(surface) {
        const cfg = heatCfg() || {};
        const P = HEAT_PATHS[surface] || HEAT_PATHS.ofx;
        const mod = window.OFAPRAMP;
        const hm = (cfg.atlas && cfg.atlas.heatmap) || {};
        const get = mod ? (path, fb) => mod.getIn(cfg, path, fb) : (path, fb) => fb;
        const dials = {
            ceiling_pct: Number(hm.upper_cutoff_pct) || 5.0,
            ceiling_abs: Number(hm.upper_cutoff_abs) || 0,
            floor: Number(get(P.floor, 0)) || 0,
            floor_pct: Number(get(P.floorPct, 0)) || 0,
            contrast: Number(get(P.contrast, 1)) || 1,
        };
        dials.scheme = mod ? mod.matchScheme(dials) : 'custom';
        return dials;
    }

    async function writeHeatParam(path, value) {
        const mod = window.OFAPRAMP;
        if (!mod) return null;
        return mod.writeParam(path, value, heatCfg(), heatNote);
    }

    async function writeHeatDial(path, rawValue) {
        const applied = await writeHeatParam(path, Number(rawValue));
        if (applied === null) { syncHeatControls(); return; }
        if (path === HEAT_PATHS.ofx.contrast) OFX.setParams({ heatContrast: applied });
        if (path === HEAT_PATHS.ofx.floor) OFX.setParams({ heatFloor: applied });
        if (path === HEAT_PATHS.ofx.floorPct) OFX.setParams({ heatFloorPct: applied });
        paintLegend();
        syncHeatControls();
    }

    /* T10: enum/bool dials ride the same gate; the value passes through untouched (the store
       coerces per the registry kind) and the accepted answer is adopted. */
    async function writeHeatFlag(path, value) {
        const applied = await writeHeatParam(path, value);
        if (applied === null) { syncHeatControls(); return; }
        if (path === 'ofx.heat_smooth') OFX.setParams({ heatSmooth: applied });
        if (path === 'atlas.ofx.degrade') OFX.setParams({ degrade: applied !== false });
        syncHeatControls();
    }

    async function applyHeatScheme(id, surface) {
        const mod = window.OFAPRAMP;
        const scheme = mod && mod.schemeById(id);
        if (!scheme) { syncHeatControls(); return; }   // 'custom' chosen: nothing to write
        const P = HEAT_PATHS[surface] || HEAT_PATHS.ofx;
        /* The ceiling is shared — the backend resolves one scale for every surface — so a scheme
           replaces a pinned absolute ceiling with its own share of the book. */
        await writeHeatParam('atlas.heatmap.upper_cutoff_abs', 0);
        await writeHeatParam('atlas.heatmap.upper_cutoff_pct', scheme.ceiling_pct);
        await writeHeatParam(P.contrast, scheme.contrast);
        await writeHeatParam(P.floor, scheme.floor);
        await writeHeatParam(P.floorPct, scheme.floor_pct);
        if (surface === 'ofx') {
            await loadParams();
            paintLegend();
        }
        syncHeatControls();
        heatNote('scheme: ' + scheme.label + ' — ' + scheme.says);
        document.dispatchEvent(new CustomEvent('ofap:heat-scheme', { detail: { from: surface } }));
    }

    async function broadcastHeat(fromSurface) {
        const other = fromSurface === 'ofx' ? 'heatmap' : 'ofx';
        const d = heatDials(fromSurface);
        const O = HEAT_PATHS[other];
        await writeHeatParam(O.contrast, d.contrast);
        await writeHeatParam(O.floor, d.floor);
        await writeHeatParam(O.floorPct, d.floor_pct);
        syncHeatControls();
        heatNote('heat scheme written to the Engine and the Heatmap view');
        document.dispatchEvent(new CustomEvent('ofap:heat-scheme', { detail: { from: fromSurface } }));
    }

    function syncHeatControls() {
        const d = heatDials('ofx');
        if (el('ofxHeatScheme')) el('ofxHeatScheme').value = d.scheme;
        if (el('ofxHeatContrast')) el('ofxHeatContrast').value = String(d.contrast);
        if (el('ofxHeatFloor')) el('ofxHeatFloor').value = String(d.floor);
        if (el('ofxHeatSmooth')) el('ofxHeatSmooth').value = String(OFX.state.params.heatSmooth || 'auto');
        if (el('ofxDegrade')) el('ofxDegrade').checked = OFX.state.params.degrade !== false;
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
            /* B2: the swatch carries the live scheme — including the contrast dial — so the legend
               describes the colours on the canvas, not the ones in the manual. */
            const g = Number(OFX.state.params.heatContrast);
            const stops = [0, 0.25, 0.5, 0.75, 1]
                .map((t) => {
                    const c = OFX.math.heatColor01(OFX.math.rampT(t, Number.isFinite(g) ? g : 1));
                    return `rgb(${c[0]},${c[1]},${c[2]})`;
                });
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

    /* A filter that hides data says how much: the engine's own tally, beside the control that set
       the floor. Zero reads "nothing hidden" rather than an empty space, so an absent number is
       never ambiguous. */
    function paintHiddenBlocks() {
        const out = el('ofxHiddenBlocks');
        if (!out || !window.OFX) return;
        const n = (OFX.stats() || {}).blocksFiltered || 0;
        const floor = Number((OFX.state.params || {}).minBlock) || 0;
        out.textContent = n ? n + ' hidden' : (floor > 0 ? 'nothing hidden' : '');
        out.classList.toggle('on', n > 0);
        out.title = n
            ? n + ' execution blocks below the min-block floor of ' + floor + ' are not drawn'
            : 'every execution block in view is drawn';
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
            const degraded = s.degraded === true;
            const exprNote = degraded ? ' · candles (auto-degraded — zoom in for the matrix)'
                : (s.expression.mode !== 'default' && s.lod === 'profile')
                    ? ' · bar expression not drawn at this LOD' : '';
            el('ofxLod').textContent = (s.lod === 'profile'
                ? (degraded ? 'LOD: candles (auto-degraded)' : 'LOD: volume profile (text suppressed)')
                : 'LOD: footprint cells + text') + (degraded ? '' : exprNote);
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
        paintSpark(el('ofxSpark'), 90, 20);
        paintSpark(el('ofxSpark2'), 88, 18);
    }

    function paintSpark(spark, cssW, cssH) {
        if (!spark) return;
        const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) ? window.devicePixelRatio : 1;
        /* §72: the spark keeps its small fixed CSS box (90×20 / 88×18) and carries the display scale
           in its backing store. It used to have no CSS size at all, so it displayed at its backing
           size: a 125/150/200% monitor drew it soft, and a fit pass could resize the element. */
        if (spark.style && spark.style.width !== cssW + 'px') {
            spark.style.width = cssW + 'px';
            spark.style.height = cssH + 'px';
        }
        const wantW = Math.max(1, Math.round(cssW * dpr)), wantH = Math.max(1, Math.round(cssH * dpr));
        if (spark.width !== wantW || spark.height !== wantH) { spark.width = wantW; spark.height = wantH; }
        const ctx = spark.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, spark.width, spark.height);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const closes = OFX.state.data.bars.slice(-60).map((b) => Number(b.close) || 0);
        if (closes.length < 2) return;
        const lo = Math.min(...closes), hi = Math.max(...closes);
        const up = closes[closes.length - 1] >= closes[0];
        ctx.strokeStyle = up ? '#35d07f' : '#ff5d6c';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        closes.forEach((c, i) => {
            const x = (i / (closes.length - 1)) * (cssW - 2) + 1;
            const y = cssH - 2 - ((c - lo) / Math.max(1e-9, hi - lo)) * (cssH - 4);
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

    /* A3: the area profile's histogram — one bar per drawn price row, the value area shaded, the
       POC solid, drawn from the same rows the strip's numbers come from. Colours resolve through
       the engine's own table (OFX.math.rgba), so the picture cannot describe a colour the stage
       does not use; the backing store carries the display scale, like every other canvas. */
    function paintSelHist(canvas, prof) {
        if (!canvas || !prof || !prof.rows.length) return;
        const M = OFX.math;
        if (!M || typeof M.rgba !== 'function') return;
        const dpr = Math.max(1, Number(window.devicePixelRatio) || 1);
        const w = Math.max(120, canvas.clientWidth || 220), h = 118;
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        const rows = prof.rows;
        const span = Math.max(1e-9, (prof.to - prof.from) || 1e-9);
        const top = rows.reduce((m, r) => Math.max(m, r.volume), 0) || 1;
        const band = h - 8;
        for (const r of rows) {
            const y = 4 + (1 - (r.price - prof.from) / span) * (band - 2);
            const len = Math.max(1, Math.round((r.volume / top) * (w - 10)));
            const isPoc = r.price === prof.poc;
            ctx.fillStyle = M.rgba(isPoc ? 'poc' : 'vaEdge', isPoc ? '.95' : (r.inVA ? '.6' : '.28'));
            ctx.fillRect(5, Math.round(y), len, Math.max(1, Math.round(band / rows.length) - 1));
        }
        ctx.strokeStyle = M.rgba('vaEdge', '.9');
        ctx.setLineDash([3, 2]);
        for (const edge of [prof.vah, prof.val]) {
            if (edge == null) continue;
            const y = Math.round(4 + (1 - (edge - prof.from) / span) * (band - 2)) + 0.5;
            ctx.beginPath();
            ctx.moveTo(2, y);
            ctx.lineTo(w - 2, y);
            ctx.stroke();
        }
        ctx.setLineDash([]);
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
        /* A3: the area profile's block — read from the same cache the stage's lines are drawn
           from, so the strip and the picture cannot disagree. `null` means the window has no
           depth rows (a degraded feed), and the block says so instead of showing zeros. */
        const prof = (typeof OFX.areaProfile === 'function') ? OFX.areaProfile() : null;
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
            + '<div class="ofx-sel-prof">'
            + (prof
                ? '<div class="ofx-sel-head2">area profile'
                  + '<span class="ofx-sel-dim">' + prof.rows.length + ' rows · VA' + Math.round(prof.vaPct * 100) + '</span>'
                  + '<button class="btn small" data-ofx-sel="watch">Watch this level</button></div>'
                  + '<div class="ofx-sel-grid">'
                  + selCell('POC', pr(prof.poc) + ' · ' + Math.round(prof.pocShare * 100) + '%')
                  + selCell('VAH / VAL', pr(prof.vah) + ' / ' + pr(prof.val))
                  + selCell('area volume', vv(prof.total))
                  + selCell('row step', pr(prof.step))
                  + '</div>'
                  + '<canvas class="ofx-sel-hist"></canvas>'
                : '<div class="ofx-sel-why">no depth rows in this window — the area profile reads the '
                  + 'per-bar ladder, so it fills once the engine feeds levels</div>')
            + '</div>'
            + '<div class="ofx-sel-note" id="ofxSelNote"></div>';
        paintSelHist(box.querySelector('.ofx-sel-hist'), prof);
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
        /* A3: the area profile rides the same file — its rows and its three prices, so the export
           answers the question the strip was asked. Absent when the window had no depth rows. */
        const prof = (typeof OFX.areaProfile === 'function') ? OFX.areaProfile() : null;
        if (prof) {
            rows.push([]);
            rows.push(['# area profile']);
            rows.push(['# rows', String(prof.rows.length)]);
            rows.push(['# va share', String(prof.vaPct)]);
            rows.push(['# poc', String(prof.poc)]);
            rows.push(['# vah', String(prof.vah)]);
            rows.push(['# val', String(prof.val)]);
            rows.push(['# area total', String(prof.total)]);
            rows.push(['# row step', String(prof.step)]);
            rows.push(['area_price', 'area_volume', 'in_va']);
            for (const r of prof.rows) {
                rows.push([String(r.price), String(r.volume), r.inVA ? '1' : '0']);
            }
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

    /* ── A3: the area profile's hand-off — a POC becomes a watched level ──────────────────────
       The rule is a `level_touch`: the engine fires when price comes back into the level's band
       (outside-to-inside, once per approach). Tolerance defaults to two drawn row steps — the
       same "two priced steps" default the heatmap's level alerts use — and the rule lands in the
       same Rules card as every other, scope and sentence included. */
    async function watchAreaLevel() {
        const st = OFX.selectionStats();
        const prof = (typeof OFX.areaProfile === 'function') ? OFX.areaProfile() : null;
        const note = el('ofxSelNote');
        if (!st || !prof) {
            if (note) note.textContent = 'a watch needs a measured window with depth rows';
            return null;
        }
        const sym = String(OFX.state.symbol || view.symbol || 'symbol').toUpperCase();
        const tol = Number(((prof.step || 0.1) * 2).toFixed(6));
        const rule = {
            id: 'ap-' + sym + '-' + String(prof.poc).replace('.', '_') + '-' + Date.now().toString().slice(-6),
            name: sym + ' area POC ' + prof.poc + ' · touch (±' + tol + ')',
            kind: 'level_touch',
            enabled: true,
            params: { at_price: prof.poc, at_tol: tol },
            cooldown_s: 60,
            channels: ['ui'],
        };
        if (note) note.textContent = 'creating the watch…';
        try {
            const res = await fetch('/api/atlas/alert-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rule),
            });
            if (note) {
                note.textContent = res.ok
                    ? 'watching ' + prof.poc + ' — an alert fires when price returns (±' + tol + ') · Alerts view'
                    : 'watch failed (' + res.status + ')';
            }
            return res.ok ? rule : null;
        } catch (err) {
            if (note) note.textContent = 'watch failed: ' + (err && err.message ? err.message : 'network');
            return null;
        }
    }

    /* ── §82: the instrument look-up ──────────────────────────────────────────
       The symbol box writes a display symbol; this is what makes the write answerable.
       `GET /api/control/instruments/resolve` says what the typed name IS (live / ready /
       disabled / available / unsupported / unknown) with a reason and a closed action set,
       and every action below is an app path that already exists: the symbol change (use),
       the config write + restart (enable / add), the engine start, and the Instruments view.
       Nothing here subscribes anything itself — the engine is the only thing that streams. */

    async function resolveSymbol(symbol, opts) {
        const options = opts || {};
        const instrument = instrumentMod();
        const query = String(symbol || sym() || '').trim();
        if (!query || !instrument) { streamState = null; paintSymbolState(); return null; }
        let payload = null;
        try {
            payload = await apiGet('/api/control/instruments/resolve?symbol=' + encodeURIComponent(query));
        } catch (err) {
            view.lastError = `instrument look-up failed: ${(err && err.message) ? err.message : err}`;
            paintStats();
            return null;
        }
        streamState = (payload && payload.ok !== false) ? payload : null;
        paintSymbolState();
        /* A panel that is open must not keep describing the previous answer (measured: after
           "Add & restart" the chip said streaming while the panel still said "available"). */
        const panel = el('ofxSymbolPanel');
        if (panel && !panel.hidden) paintSymbolPanel();
        paintStats();
        const state = streamState ? instrument.state(streamState) : '';
        if (options.openWhenStuck && state && state !== 'live' && state !== 'ready') openSymbolPanel();
        return streamState;
    }

    function paintSymbolState() {
        const chipEl = el('ofxSymbolState');
        if (!chipEl) return;
        const instrument = instrumentMod();
        if (!instrument || !streamState) {
            chipEl.textContent = '';
            chipEl.className = 'ofx-sym-chip';
            chipEl.title = '';
            return;
        }
        const chip = instrument.chip(streamState);
        chipEl.textContent = chip.text;
        chipEl.className = 'ofx-sym-chip ' + chip.kind;
        chipEl.title = instrument.title(streamState) || 'instrument look-up';
        chipEl.setAttribute('data-state', chip.state);
        /* §83: hovering or right-clicking the chip explains this exact state, with the button
           that fixes it — re-read at show-time by hint.js, so it is never stale. */
        chipEl.setAttribute('data-hint-title', chip.text || 'Instrument look-up');
        chipEl.setAttribute('data-hint-body',
            instrument.panelText(streamState) || 'Hover for what the server makes of this symbol.');
        chipEl.setAttribute('data-hint-actions',
            (chip.state === 'live' || chip.state === 'ready') ? 'engine instruments' : 'lookup instruments');
    }

    function setSymbolMsg(message, kind) {
        const line = el('ofxSymMsg');
        if (!line) return;
        line.textContent = message || '';
        line.className = 'ofx-sym-msg' + (kind ? ' ' + kind : '');
    }

    function openSymbolPanel() {
        const panel = el('ofxSymbolPanel');
        if (!panel) return;
        paintSymbolPanel();
        panel.hidden = false;
    }

    function closeSymbolPanel() {
        const panel = el('ofxSymbolPanel');
        if (panel) panel.hidden = true;
    }

    /* §85: the symbol section's quick picker. Options come from the config + the engine's own
       status; picking one switches the view and — when the instrument is not covered yet — runs
       the same enable/add/start path the look-up's buttons use, so a pick is "refresh and
       enable", not a dead jump to a symbol the engine then refuses. */
    async function refreshPicker() {
        const sel = el('ofxSymPick');
        const instrument = instrumentMod();
        if (!sel || !instrument || typeof instrument.pickerRows !== 'function') return;
        let cfg = {};
        let status = {};
        try { cfg = await apiGet('/api/control/config'); } catch (err) { /* nothing to list yet */ }
        try { status = await apiGet('/api/control/engine/status'); } catch (err) { /* ditto */ }
        const rows = instrument.pickerRows({ instruments: (cfg && cfg.instruments) || [],
            streaming: (status && status.symbols) || [] });
        const current = String(el('ofxSymbol') ? el('ofxSymbol').value : (view.symbol || '')).toUpperCase();
        let html = '<option value="">pick…</option>';
        let group = '';
        rows.forEach((row) => {
            if (row.group !== group) {
                if (group) html += '</optgroup>';
                html += `<optgroup label="${esc(row.group)}">`;
                group = row.group;
            }
            html += `<option value="${esc(row.value)}"${row.value.toUpperCase() === current ? ' selected' : ''}>`
                + `${esc(row.label)}</option>`;
        });
        if (group) html += '</optgroup>';
        sel.innerHTML = html;
    }

    async function pickSymbol(symbol) {
        const name = String(symbol || '').toUpperCase();
        if (!name) return;
        if (el('ofxSymbol')) el('ofxSymbol').value = name;
        view.symbol = name;
        await saveParams();
        const payload = await resolveSymbol(name);
        const state = payload ? String(payload.state || '') : '';
        if (state === 'disabled') await runInstrumentAction('enable', payload);
        else if (state === 'ready') await runInstrumentAction('start_engine', payload);
        else if (state === 'available') await runInstrumentAction('add', payload);
        await refreshPicker();
    }

    function paintSymbolPanel() {
        const instrument = instrumentMod();
        if (!instrument) return;
        const payload = streamState || {};
        if (el('ofxSymTitle')) el('ofxSymTitle').textContent = (instrument.chip(payload).text || 'instrument').trim();
        if (el('ofxSymReason')) el('ofxSymReason').textContent = instrument.panelText(payload);
        const actionsEl = el('ofxSymActions');
        if (actionsEl) {
            actionsEl.innerHTML = '';
            instrument.actions(payload).forEach((spec) => {
                const button = document.createElement('button');
                button.className = 'btn small' + (spec.primary ? ' primary' : '');
                button.textContent = spec.label;
                button.addEventListener('click', () => void runInstrumentAction(spec.action, payload));
                actionsEl.appendChild(button);
            });
        }
        const rowsEl = el('ofxSymRows');
        if (rowsEl) {
            rowsEl.innerHTML = '';
            instrument.rows(payload).forEach((row) => {
                const item = document.createElement('div');
                item.className = 'ofx-sym-row';
                item.innerHTML = `<span class="sym">${esc(row.symbol)}</span>`
                    + `<span class="meta">${esc(row.meta)}</span>`
                    + `<span class="go">${row.streaming ? '● streaming' : (row.enabled ? 'enabled' : 'off')} ›</span>`;
                item.addEventListener('click', () => {
                    if (el('ofxSymbol')) el('ofxSymbol').value = row.symbol;
                    view.symbol = row.symbol;
                    void saveParams().then(() => resolveSymbol(row.symbol, { openWhenStuck: true }));
                });
                rowsEl.appendChild(item);
            });
        }
    }

    async function runInstrumentAction(action, payload) {
        const instrument = instrumentMod();
        const p = payload || streamState || {};
        const symbol = String(p.symbol || p.query || '').trim().toUpperCase();
        if (!instrument || !action) return;
        if (action === 'use') {
            if (el('ofxSymbol')) el('ofxSymbol').value = symbol;
            view.symbol = symbol;
            closeSymbolPanel();
            await saveParams();
            await resolveSymbol(symbol);
            return;
        }
        if (action === 'open_instruments' || action === 'map_broker') {
            if (typeof window.showView === 'function') window.showView('instruments');
            return;
        }
        if (action === 'start_engine') {
            setSymbolMsg('starting the engine…');
            try {
                const res = await apiGet('/api/control/engine/start', { method: 'POST', body: {} });
                const ok = !(res && res.ok === false);
                setSymbolMsg(ok ? 'engine started — waiting for data'
                    : `engine refused: ${(res && res.error) || 'unknown'}`, ok ? 'ok' : 'bad');
                await resolveSymbol(symbol || sym());
            } catch (err) {
                setSymbolMsg(`engine start failed: ${(err && err.message) ? err.message : err}`, 'bad');
            }
            return;
        }
        if (action === 'enable' || action === 'add') {
            if (!symbol) { setSymbolMsg('type an instrument name first', 'bad'); return; }
            const instrumentRow = p.instrument || {};
            /* §82-ext: the resolve answer may name its own venue — an Alpaca asset found from a
               Bybit session — and the add must go to THAT venue or the venue catalog refuses it. */
            const addSource = p.add_source || p.source || '';
            const body = { symbols: [symbol], source: addSource, enable: true };
            /* A row that carries the broker's own name keeps it; a broker-only add maps the
               typed name onto itself. */
            if (addSource === 'mt5') body.mt5_symbols = { [symbol]: p.broker_name || instrumentRow.mt5_symbol || symbol };
            if (addSource === 'alpaca') body.alpaca_symbols = { [symbol]: instrumentRow.alpaca_symbol || symbol };
            setSymbolMsg(`${action === 'add' ? 'adding' : 'enabling'} ${symbol}…`);
            try {
                const res = await apiGet('/api/control/instruments/add', { method: 'POST', body });
                if (!res || res.ok === false) {
                    setSymbolMsg(`refused: ${(res && res.error) || 'unknown'}`, 'bad');
                    return;
                }
                const skipped = res.skipped || [];
                if (skipped.length) { setSymbolMsg(`refused: ${skipped[0].reason}`, 'bad'); return; }
                /* A running engine built its pipelines at start: restart it so the instrument is
                   actually subscribed — the same path the source switch uses. */
                const status = await apiGet('/api/control/engine/status').catch(() => ({}));
                if (status && status.running) {
                    setSymbolMsg('restarting the engine…');
                    const restarted = await apiGet('/api/control/engine/restart', { method: 'POST', body: {} });
                    if (restarted && restarted.ok === false) {
                        setSymbolMsg(`restart failed: ${restarted.error || 'unknown'}`, 'bad');
                        return;
                    }
                }
                setSymbolMsg((p.add_source && p.add_source !== p.source)
                    ? `${symbol} added on ${p.add_source} — switch the data source to ${p.add_source} (☰ ▸ sources) and start the engine to stream it`
                    : `${symbol} is on — the engine covers it now`, 'ok');
                /* The view was showing whatever was typed; a broker name is not an app symbol,
                   so the stage would keep asking for a symbol nothing streams (measured: the
                   footprint 404 note stayed on screen after a successful add). Follow the row. */
                if (symbol && symbol !== view.symbol) {
                    if (el('ofxSymbol')) el('ofxSymbol').value = symbol;
                    view.symbol = symbol;
                    await saveParams();
                }
                await resolveSymbol(symbol);
                await load();
            } catch (err) {
                setSymbolMsg(`failed: ${(err && err.message) ? err.message : err}`, 'bad');
            }
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
            else if (what === 'watch') void watchAreaLevel();
        });
        if (el('ofxApply')) el('ofxApply').addEventListener('click', () => void saveParams());
        /* §82: the look-up's controls — find answers, the chip re-opens the last answer, and the
           panel's × closes it. */
        const symbolInput = el('ofxSymbol');
        if (el('ofxSymbolFind')) el('ofxSymbolFind').addEventListener('click', () => {
            void resolveSymbol(symbolInput ? symbolInput.value : sym())
                .then(() => openSymbolPanel());
        });
        if (el('ofxSymbolState')) el('ofxSymbolState').addEventListener('click', () => {
            void resolveSymbol(symbolInput ? symbolInput.value : sym()).then(() => openSymbolPanel());
        });
        if (el('ofxSymClose')) el('ofxSymClose').addEventListener('click', () => closeSymbolPanel());
        /* §85: the picker — focus re-reads the states (the config moves under it), a pick
           switches + enables as needed. */
        if (el('ofxSymPick')) {
            el('ofxSymPick').addEventListener('focus', () => void refreshPicker());
            el('ofxSymPick').addEventListener('change', () => void pickSymbol(el('ofxSymPick').value));
        }
        void refreshPicker();
        wireCursorLink();
        /* The spine's badge, beside the engine's own stats line: the engine is one of the panels that
           reads the shared cursor, so it carries the same tag as the rest. */
        if (window.OFAPCURSOR) {
            const head = document.querySelector('.view[data-view="ofx"] .view-head');
            if (head) OFAPCURSOR.badge(head);
        }
        /* The ramp is a stored display parameter (config_store clamps it to `RAMP_KEYS`), so it is
           applied immediately AND persisted through the same route the other parameters use. It
           used to be a localStorage preference, which is not the record anywhere else in this app. */
        if (el('ofxRamp')) {
            el('ofxRamp').addEventListener('change', () => {
                OFX.setParams({ ramp: el('ofxRamp').value });
                paintLegend();
                void saveParams();
            });
        }
        /* ── B2: the heat scheme, on the Engine's side ──────────────────────────────────────────
           Scheme and dials write through the registry gate (/api/control/params — the same route
           the Settings search uses), adopt the value the store accepted, and repaint. The scheme
           select reads 'custom' whenever the dials match no preset. `apply globally` copies this
           surface's dials to the other heat surfaces through the same gate. */
        if (el('ofxHeatScheme')) {
            el('ofxHeatScheme').addEventListener('change', () => {
                void applyHeatScheme(el('ofxHeatScheme').value, 'ofx');
            });
        }
        [['ofxHeatContrast', 'ofx.heat_contrast'], ['ofxHeatFloor', 'ofx.heat_floor']].forEach((pair) => {
            if (!el(pair[0])) return;
            el(pair[0]).addEventListener('change', () => void writeHeatDial(pair[1], el(pair[0]).value));
        });
        if (el('ofxHeatSmooth')) {
            el('ofxHeatSmooth').addEventListener('change',
                () => void writeHeatFlag('ofx.heat_smooth', el('ofxHeatSmooth').value));
        }
        if (el('ofxDegrade')) {
            el('ofxDegrade').addEventListener('change',
                () => void writeHeatFlag('atlas.ofx.degrade', el('ofxDegrade').checked));
        }
        if (el('ofxHeatGlobal')) {
            el('ofxHeatGlobal').addEventListener('click', () => void broadcastHeat('ofx'));
        }
        document.addEventListener('ofap:heat-scheme', (ev) => {
            if (ev && ev.detail && ev.detail.from === 'ofx') return;
            /* The other surface wrote the shared paths; re-read the block rather than guess. */
            void loadParams();
            paintLegend();
            heatNote('the heat scheme was applied to the Engine');
        });
        document.addEventListener('ofap:scopes', () => {
            /* T12/B9: an instrument-scope block was applied — re-read rather than guess. */
            void loadParams();
            paintLegend();
            heatNote('this instrument’s heat settings were applied');
        });
        /* T10/B13: the degrade switch lives in `atlas.ofx` (the renderer block the canvases
           read, like fit_tolerance); adopt it at wiring time and paint the new controls. */
        if (typeof S !== 'undefined' && S && S.config) {
            OFX.setParams({ degrade: (((S.config.atlas || {}).ofx || {}).degrade) !== false });
        }
        syncHeatControls();
        /* Bars and palette: applied on change, then reconciled with the store's answer. */
        ['ofxMode', 'ofxPalette'].forEach((id) => {
            if (!el(id)) return;
            el(id).addEventListener('change', () => {
                void saveExpression({ mode: el('ofxMode').value, palette: el('ofxPalette').value });
            });
        });
        /* The Chart menu writes the same registry paths through /api/control/params; that arrives as
           an event rather than a direct call, because the menu has no idea which view is live. */
        document.addEventListener('ofap:expression', () => {
            /* The menu writes the config, not this module's memory: re-read the block and adopt
               it, rather than re-resolving parameters that never changed. */
            void loadExpression();
        });
        if (el('ofxSymbol')) el('ofxSymbol').addEventListener('change', () => {
            view.symbol = (el('ofxSymbol').value || SYM_FALLBACK).toUpperCase();
            /* §82: the change is answered, not just saved — a symbol nothing streams opens the
               look-up with the reason and the action instead of leaving a blank stage. */
            void saveParams().then(() => resolveSymbol(view.symbol, { openWhenStuck: true }));
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

        await loadExpression();
        try {
            await load();
        } catch (err) {
            view.lastError = `feed error: ${err}`;
            paintStats();
        }
        /* §82: the boot answer — non-blocking, so a slow broker lookup never delays first paint. */
        void resolveSymbol(sym());
        /* The pause registry clears the interval on pause and calls this back on resume, so the
           callback has to rebuild the poll - registering a one-shot load here meant a single
           pause/resume stopped the Engine view's updates for the rest of the session. */
        const startPolling = () => {
            const id = setInterval(() => {
                if (window.OFAPINTENT && OFAPINTENT.held('ofx')) return;   // never reload under the user's hands
                if (document.hidden || window.OFAP_PAUSED) return;      // freeze-while-you-work
                /* Hidden panels age by design (the freshness store's rule): a 2.5 s engine poll
                   behind another view is five endpoints of pure waste, and the view reloads on
                   the next tick after it is shown again. Terminal mode hosts the section in a
                   frame, which shows it with display:flex rather than `.active` — the same pair
                   scanner.js tests. */
                const section = document.querySelector('.view[data-view="ofx"]');
                if (!section || !(section.classList.contains('active') || section.style.display === 'flex')) return;
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
            paintHiddenBlocks();
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

    /* P1-9: the engine's keys, registered into the app's one shortcut map — at module scope, so the
       map is complete before the view has ever been opened. Zoom anchors at the stage centre (the
       wheel keeps the cursor); priority 6 outranks the heatmap's 5 when Terminal mode shows both
       views at once. Clear and export drive the selection strip's own buttons, so a key can never
       take a different path than the click it stands for. */
    if (window.OFAPKEYS) {
        const stripBtn = (what) => document.querySelector('.view[data-view="ofx"] [data-ofx-sel="' + what + '"]');
        OFAPKEYS.bind({ id: 'zoom-time-in', keys: ['=', '+'], scope: 'Engine', priority: 6,
            label: 'zoom time in', when: () => OFAPKEYS.inView('ofx'), why: 'acts on the Engine panel', run: () => OFX.zoomTime(1.12) });
        OFAPKEYS.bind({ id: 'zoom-time-out', keys: ['-', '_'], scope: 'Engine', priority: 6,
            label: 'zoom time out', when: () => OFAPKEYS.inView('ofx'), why: 'acts on the Engine panel', run: () => OFX.zoomTime(0.89) });
        OFAPKEYS.bind({ id: 'zoom-price-in', keys: [']', '}'], scope: 'Engine', priority: 6,
            label: 'zoom price in', when: () => OFAPKEYS.inView('ofx'), why: 'acts on the Engine panel', run: () => OFX.zoomPrice(1.09) });
        OFAPKEYS.bind({ id: 'zoom-price-out', keys: ['[', '{'], scope: 'Engine', priority: 6,
            label: 'zoom price out', when: () => OFAPKEYS.inView('ofx'), why: 'acts on the Engine panel', run: () => OFX.zoomPrice(0.92) });
        /* T10/B16: the reset-scales command — price back to auto, time back to live. */
        OFAPKEYS.bind({ id: 'reset-scales', keys: ['ctrl+shift+r'], scope: 'Engine', priority: 6,
            label: 'reset the price and time scales',
            when: () => OFAPKEYS.inView('ofx'), why: 'acts on the Engine panel',
            run: () => OFX.snapToLive() });
        OFAPKEYS.bind({ id: 'selection-clear', keys: ['x'], scope: 'Engine', priority: 6,
            label: 'clear the selection',
            when: () => OFAPKEYS.inView('ofx') && OFX.selection() != null, why: 'box a region on the Engine first',
            run: () => { const b = stripBtn('clear'); if (b) b.click(); } });
        OFAPKEYS.bind({ id: 'export', keys: ['ctrl+e'], scope: 'Engine', priority: 6,
            label: 'export the selection as CSV',
            when: () => OFAPKEYS.inView('ofx') && OFX.selection() != null, why: 'box a region on the Engine first',
            run: () => { const b = stripBtn('export'); if (b) b.click(); } });
        /* T5/A12 — the canvas precision kit: the arrows nudge the stage one pixel, Shift ten.
           Time and price are separate journeys, so each axis gets its own pair. Registered like
           every other Engine key, so the Keys menu and the hover prompts can never drift. */
        [['arrowleft', -1, 0, 'nudge the view back in time'],
         ['shift+arrowleft', -10, 0, 'nudge the view back in time (10 px)'],
         ['arrowright', 1, 0, 'nudge the view forward in time'],
         ['shift+arrowright', 10, 0, 'nudge the view forward in time (10 px)'],
         ['arrowup', 0, 1, 'nudge the view towards higher prices'],
         ['shift+arrowup', 0, 10, 'nudge the view towards higher prices (10 px)'],
         ['arrowdown', 0, -1, 'nudge the view towards lower prices'],
         ['shift+arrowdown', 0, -10, 'nudge the view towards lower prices (10 px)']].forEach((row) => {
            OFAPKEYS.bind({ id: 'engine-nudge-' + row[0].replace('shift+', 's-'), keys: [row[0]],
                scope: 'Engine', priority: 6, label: row[3], why: 'acts on the Engine panel',
                when: () => OFAPKEYS.inView('ofx'), run: () => OFX.nudge(row[1], row[2]) });
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchView);
    else watchView();
})();
