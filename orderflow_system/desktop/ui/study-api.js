/* ══════════════════════════════════════════════════════════════════════════════
   Study API — the suite's own indicator model, adapted to this build.

   the contract documents its indicators as CommonJS modules that export a
   definition (name/description/calculator/params/plots/plotter/schemeStyles/
   areaChoice/inputType/tags) plus a Calculator class implementing
   `init()` / `map(d, i, history, output)` / `filter(entity)`. This file implements
   that same contract here — same module shape, same lifecycle, same helper names
   (`predef.paramSpecs.period(14)`, `predef.plotters.columns('value')`,
   `predef.styles.solidLine('#ffe270')`, `meta.InputType.BARS`, `meta.AreaChoice.NEW`)
   — so an indicator written against their documentation is a two-line change away
   from running on this chart, and everything written for this chart stays readable
   by anyone who has seen their docs.

   What is *ours* rather than theirs (all additive, none of it required):
     · `signal` in a map() result → an OFAP marker + alert event;
     · order-flow accessors on the entity (buy/sell/delta/volume), because this chart
       has tape-derived fields that a plain OHLC platform does not;
     · `StudyAPI.run()` is a pure function over a bar array, so it is unit-testable
       in Node with no chart and no DOM.

   Not implemented (documented as cards in docs/TRADOVATE_STUDY_BRIDGE.md): `dlls`
   (Windows DLL imports), the interactive `drawing-tool` framework, the full
   `graphics/*` display-object tree, and auto-scaling beyond per-plot price scales.

   Rendering targets lightweight-charts, the chart this app already uses: a plot
   becomes a line or histogram series, `areaChoice: "new"` gets its own price scale
   (lightweight-charts has no panes), and `shifts` offsets the X axis in bars.
   ══════════════════════════════════════════════════════════════════════════════ */

const StudyAPI = (() => {
    const VERSION = '1.0.0';

    /* ── predef.paramSpecs — same call shapes as the indicator tutorials ───── */
    const paramSpecs = {
        period: (def = 14) => ({ type: 'number', def, restrictions: { step: 1, min: 1, max: 1000 } }),
        number: (def = 0, step = 1, min = -1e9) => ({ type: 'number', def, restrictions: { step, min } }),
        boolean: (def = false) => ({ type: 'boolean', def }),
        text: (def = '') => ({ type: 'text', def, restrictions: { maxLength: 160 } }),
        enumDef: (options = [], def = undefined) => ({
            type: 'enum', def: def === undefined ? (options[0] || null) : def,
            restrictions: { options: [...options] },
        }),
    };

    /* ── predef.styles — colour/style presets referenced by schemeStyles ───── */
    const styles = {
        solidLine: (color = '#4f8cff', width = 2) => ({ plotter: 'line', color, width }),
        dashedLine: (color = '#9aa9c1', width = 1) => ({ plotter: 'line', color, width, dash: true }),
        histogram: (color = '#4f8cff') => ({ plotter: 'columns', color }),
        columns: (color = '#4f8cff') => ({ plotter: 'columns', color }),
        dots: (color = '#ffe270') => ({ plotter: 'dots', color, width: 2 }),
        range: (color = '#8c8cff') => ({ plotter: 'range', color }),
    };

    /* ── predef.plotters — how a plot is drawn (default: lines) ───────────── */
    const plotters = {
        singleline: (field) => ({ kind: 'line', field }),
        dots: (field) => ({ kind: 'dots', field }),
        columns: (field) => ({ kind: 'columns', field }),
        range: (field) => ({ kind: 'range', field }),
        custom: (fn) => ({ kind: 'custom', fn }),
    };

    /* ── meta — the two enums the tutorials use ───────────────────────────── */
    const meta = {
        InputType: { BARS: 'bars', VOLUME: 'volume', ANY: 'any' },
        AreaChoice: { OVERLAY: 'overlay', NEW: 'new' },
    };

    /* ── tools — the tutorial helper modules (MMA, trueRange, …) ──────────── */
    const tools = {
        sma: (period) => {
            const buf = [];
            return (value) => {
                if (value === undefined || value === null || Number.isNaN(value)) return undefined;
                buf.push(value);
                if (buf.length > period) buf.shift();
                if (buf.length < period) return undefined;
                return buf.reduce((a, b) => a + b, 0) / period;
            };
        },
        ema: (period) => {
            const k = 2 / (period + 1);
            let prev;
            return (value) => {
                if (value === undefined || value === null || Number.isNaN(value)) return undefined;
                prev = prev === undefined ? value : value * k + prev * (1 - k);
                return prev;
            };
        },
        mma: (period) => tools.sma(period),
        wilders: (period) => {
            let prev, n = 0, sum = 0;
            return (value) => {
                if (value === undefined || value === null || Number.isNaN(value)) return undefined;
                n += 1;
                if (prev === undefined) { sum += value; if (n < period) return undefined; prev = sum / period; return prev; }
                prev = prev + (value - prev) / period;
                return prev;
            };
        },
        trueRange: (d, priorItem) => {
            const prior = priorItem || (d && d.prior ? d.prior() : undefined);
            const priorClose = prior && prior.close ? prior.close() : undefined;
            const high = d.high(), low = d.low();
            if (priorClose === undefined) return high - low;
            return Math.max(high - low, Math.abs(high - priorClose), Math.abs(low - priorClose));
        },
        highest: (period) => {
            const buf = [];
            return (value) => {
                buf.push(value);
                if (buf.length > period) buf.shift();
                return buf.length < period ? undefined : Math.max(...buf);
            };
        },
        lowest: (period) => {
            const buf = [];
            return (value) => {
                buf.push(value);
                if (buf.length > period) buf.shift();
                return buf.length < period ? undefined : Math.min(...buf);
            };
        },
        stdev: (period) => {
            const buf = [];
            return (value) => {
                buf.push(value);
                if (buf.length > period) buf.shift();
                if (buf.length < period) return undefined;
                const mean = buf.reduce((a, b) => a + b, 0) / period;
                return Math.sqrt(buf.reduce((a, b) => a + (b - mean) ** 2, 0) / period);
            };
        },
    };

    /* ── validation: a module that cannot run should say why, precisely ───── */
    function validate(def) {
        const errors = [];
        const warnings = [];
        if (!def || typeof def !== 'object') {
            return { ok: false, errors: ['the module must export an object'], warnings };
        }
        if (!def.name || typeof def.name !== 'string') errors.push('name is required (string)');
        else if (!/^[A-Za-z][A-Za-z0-9_-]{1,40}$/.test(def.name)) {
            errors.push('name must start with a letter and use letters, digits, "-" or "_"');
        }
        if (typeof def.calculator !== 'function' && typeof def.calculator !== 'object') {
            errors.push('calculator is required (a class or object implementing map)');
        }
        const proto = def.calculator && (def.calculator.prototype || def.calculator);
        if (!proto || typeof proto.map !== 'function') errors.push('calculator.map() is required');
        if (proto && proto.init !== undefined && typeof proto.init !== 'function') {
            errors.push('calculator.init must be a function when present');
        }
        if (proto && proto.filter !== undefined && typeof proto.filter !== 'function') {
            errors.push('calculator.filter must be a function when present');
        }
        if (def.params !== undefined) {
            if (typeof def.params !== 'object' || def.params === null) {
                errors.push('params must be an object of parameter definitions');
            } else {
                for (const [key, spec] of Object.entries(def.params)) {
                    if (!spec || typeof spec !== 'object') { errors.push(`param "${key}" must be an object`); continue; }
                    if (!['number', 'boolean', 'text', 'enum'].includes(spec.type)) {
                        errors.push(`param "${key}" has unknown type "${spec.type}"`);
                    }
                    if (spec.type === 'enum' && !(spec.restrictions && Array.isArray(spec.restrictions.options))) {
                        errors.push(`param "${key}" is an enum without restrictions.options`);
                    }
                }
            }
        }
        if (def.plots !== undefined) {
            if (typeof def.plots !== 'object' || def.plots === null) errors.push('plots must be an object');
            else for (const [key, plot] of Object.entries(def.plots)) {
                if (!plot || typeof plot !== 'object') { errors.push(`plot "${key}" must be an object`); continue; }
                if (typeof plot.title !== 'string' || !plot.title.trim()) errors.push(`plot "${key}" needs a title`);
            }
        }
        if (def.areaChoice !== undefined && !['overlay', 'new'].includes(def.areaChoice)) {
            errors.push('areaChoice must be "overlay" or "new"');
        }
        if (def.inputType !== undefined && !['bars', 'volume', 'any'].includes(def.inputType)) {
            errors.push('inputType must be "bars", "volume" or "any"');
        }
        const plotNames = Object.keys(def.plots || {});
        const declared = (def.plotter ? (Array.isArray(def.plotter) ? def.plotter : [def.plotter]) : [])
            .map((p) => (p && p.field) || null).filter(Boolean);
        for (const field of declared) {
            if (plotNames.length && !plotNames.includes(field)) {
                errors.push(`plotter refers to plot "${field}" which is not in plots`);
            }
        }
        if (!plotNames.length) {
            /* A calculator that returns a plain number is a complete, valid study — the minimal
               tutorial example is exactly that. Fill the default plot in silently rather than
               showing the author something that reads like a defect. */
            def.plots = { value: { title: def.description || def.name || 'value' } };
        }
        if (!def.description) warnings.push('no description — the UI will show the machine name');
        return { ok: errors.length === 0, errors, warnings };
    }

    /* ── parameters: defaults from the spec, user values clamped ──────────── */
    function defaultsFor(def) {
        const out = {};
        for (const [key, spec] of Object.entries((def && def.params) || {})) out[key] = spec.def;
        return out;
    }

    function coerceParams(def, user) {
        const out = {};
        for (const [key, spec] of Object.entries((def && def.params) || {})) {
            const raw = (user || {})[key];
            const value = raw === undefined || raw === null || raw === '' ? spec.def : raw;
            if (spec.type === 'number') {
                const n = Number(value);
                if (!Number.isFinite(n)) { out[key] = Number(spec.def) || 0; continue; }
                const r = spec.restrictions || {};
                out[key] = Math.min(r.max !== undefined ? r.max : Infinity,
                                    Math.max(r.min !== undefined ? r.min : -Infinity, n));
            } else if (spec.type === 'boolean') {
                out[key] = typeof value === 'string' ? value === 'true' : !!value;
            } else if (spec.type === 'enum') {
                const options = (spec.restrictions || {}).options || [];
                out[key] = options.includes(value) ? value : spec.def;
            } else {
                out[key] = String(value).slice(0, (spec.restrictions || {}).maxLength || 160);
            }
        }
        return out;
    }

    /* ── the input entity: what `map(d, …)` receives ──────────────────────── */
    function entityAt(bars, index, tickSize) {
        const bar = bars[index] || {};
        const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
        const close = num(bar.close);
        const buy = num(bar.buy_volume !== undefined ? bar.buy_volume : bar.buy);
        const sell = num(bar.sell_volume !== undefined ? bar.sell_volume : bar.sell);
        const delta = bar.bar_delta !== undefined ? num(bar.bar_delta) : (buy - sell);
        return {
            time: bar.time,
            tickSize,
            open: () => num(bar.open),
            high: () => num(bar.high),
            low: () => num(bar.low),
            close: () => close,
            volume: () => num(bar.volume),
            buy: () => buy,
            sell: () => sell,
            delta: () => delta,
            /* a plain OHLC platform offers no tape fields; here they are real, and
               an indicator that ignores them still behaves exactly as documented */
            value: () => close,
            prior: (n = 1) => (index - n >= 0 ? entityAt(bars, index - n, tickSize) : undefined),
        };
    }

    /* ── the series handed to map() as `history` ─────────────────────────────
       the indicator tutorials write `map(d, i, history)` and then either index it
       (`history[i]`) or step off it (`history.prior()`). Both work here: the view is a
       real array of entities with a cursor that follows the iteration, so `history[i]`
       is the same object the loop is passing as `d` for that bar.
       ---------------------------------------------------------------------- */
    function seriesView(bars, tickSize) {
        const view = bars.map((_, index) => entityAt(bars, index, tickSize));
        Object.defineProperty(view, 'cursor', { value: 0, writable: true, enumerable: false });
        view.prior = (n = 1) => (view.cursor - n >= 0 ? view[view.cursor - n] : undefined);
        view.current = () => view[view.cursor];
        view.bars = bars;
        return view;
    }

    /* ── the engine: run a definition over a bar array ───────────────────── */
    function run(def, bars, props, context) {
        const ctx = context || {};
        const tickSize = Number(ctx.tickSize) || 0.01;
        const params = coerceParams(def, props);
        const series = Array.isArray(bars) ? bars : [];
        const plots = {};
        for (const key of Object.keys(def.plots || {})) plots[key] = [];
        if (!Object.keys(plots).length) plots.value = [];

        const markers = [];
        const alerts = [];
        const filtered = [];
        const errors = [];
        const output = [];

        let calc;
        try {
            calc = typeof def.calculator === 'function' ? new def.calculator() : def.calculator;
            calc.props = params;
            calc.contractInfo = {
                contract: ctx.symbol || '', product: ctx.product || '',
                tickSize, underlyingType: 'MinuteBar', elementSize: 1,
            };
            if (typeof calc.init === 'function') calc.init();
        } catch (err) {
            return { ok: false, params, plots, markers, alerts, filtered, output,
                     errors: [`init() threw: ${err && err.message ? err.message : err}`] };
        }

        const historyView = seriesView(series, tickSize);

        for (let i = 0; i < series.length; i += 1) {
            let result;
            try {
                historyView.cursor = i;
                result = calc.map(entityAt(series, i, tickSize), i, historyView, output);
            } catch (err) {
                errors.push(`map() threw at bar ${i}: ${err && err.message ? err.message : err}`);
                break;                                  // one bad bar must not kill the chart
            }
            output.push(result);
            if (result === undefined || result === null) continue;

            let keep = true;
            if (typeof calc.filter === 'function') {
                try { keep = !!calc.filter(result); }
                catch (err) { errors.push(`filter() threw at bar ${i}: ${err && err.message ? err.message : err}`); }
            }
            if (!keep) { filtered.push(i); continue; }

            const time = series[i] ? series[i].time : undefined;
            const style = result.style || {};
            const candlestick = result.candlestick || (result.style && result.style.candlestick);
            if (typeof result === 'number') {
                plots.value.push({ time, value: result, style: style.value, candlestick, index: i });
            } else {
                for (const [key, value] of Object.entries(result)) {
                    if (key === 'style' || key === 'candlestick' || key === 'graphics' || key === 'signal') continue;
                    if (!plots[key]) plots[key] = [];
                    if (value === undefined || value === null) continue;
                    const plotStyle = style[key] || (style.value && key === 'value' ? style.value : undefined);
                    plots[key].push({ time, value, style: plotStyle, candlestick, index: i });
                }
            }
            if (result.signal) {
                const signal = result.signal;
                markers.push({
                    time,
                    position: signal.side === 'buy' ? 'belowBar' : 'aboveBar',
                    color: signal.color || (signal.side === 'buy' ? '#35d07f' : '#ff5d6c'),
                    shape: signal.shape || (signal.side === 'buy' ? 'arrowUp' : 'arrowDown'),
                    text: String(signal.text || signal.side || '').slice(0, 24),
                });
                alerts.push({ time, side: signal.side || '', text: String(signal.text || '').slice(0, 80),
                              value: typeof result === 'number' ? result : result.value });
            }
        }

        return {
            ok: errors.length === 0, params, plots, markers, alerts, filtered, output, errors,
            stats: { bars: series.length, filtered: filtered.length, markers: markers.length,
                     first: series.length ? series[0].time : undefined,
                     last: series.length ? series[series.length - 1].time : undefined },
        };
    }

    /* ── offsets (`shifts`) and the data-box rows ─────────────────────────── */
    function shiftedTime(bars, index, shift) {
        const target = index + (shift || 0);
        return bars[target] ? bars[target].time : undefined;
    }

    function dataBoxRows(def, result, barIndex) {
        const rows = [];
        for (const [key, points] of Object.entries(result.plots || {})) {
            const spec = (def.plots || {})[key] || {};
            if (spec.displayOnly) continue;
            const point = points.find((p) => p.index === barIndex);
            rows.push({
                study: def.description || def.name,
                plot: spec.title || key,
                value: point ? point.value : undefined,
            });
        }
        return rows;
    }

    /* ── loading a module written for the suite ─────────────────────
       Their modules are CommonJS and pull helpers with `require('./tools/predef')`,
       `require('./tools/meta')`, `require('./tools/MMA')` … A module pasted or saved
       through the Studies view arrives as source text, so it is executed here with
       exactly those names provided. That is what makes a documented example runnable
       as written, and it is also the sandbox boundary: whatever the module throws or
       fails to export is reported as text, never as a crash.
       ---------------------------------------------------------------------- */
    function requireShim(name) {
        const key = String(name || '').toLowerCase();
        if (key.includes('predef')) return { paramSpecs, plotters, styles };
        if (key.includes('meta')) return meta;
        if (key.includes('mma') || key.includes('sma')) return tools.mma;
        if (key.includes('ema')) return tools.ema;
        if (key.includes('truerange')) return tools.trueRange;
        if (key.includes('stdev')) return tools.stdev;
        throw new Error(`require('${name}') is not available — use StudyAPI.tools`);
    }

    function loadModuleSource(source, options) {
        const opts = options || {};
        const label = opts.label || 'module';
        const moduleShim = { exports: {} };
        const text = String(source || '');
        /* the suite's indicator contract's own examples open with `const predef = require('./tools/predef');`.
           Injecting that name as a parameter as well makes it a redeclaration error, so the
           injected helpers are given up one by one when a module brings its own — which is
           exactly what the engine reports in the message, so no name-guessing is needed. */
        let injected = [
            { name: 'predef', value: { paramSpecs, plotters, styles } },
            { name: 'meta', value: meta },
            { name: 'StudyAPI', value: API },
        ];
        let lastError = '';
        let ran = false;
        for (let attempt = 0; attempt <= 3 && !ran; attempt += 1) {
            const params = ['module', 'exports', 'require', ...injected.map((entry) => entry.name)];
            const args = [moduleShim, moduleShim.exports, requireShim, ...injected.map((entry) => entry.value)];
            try {
                /* eslint-disable no-new-func */
                const factory = new Function(...params, `"use strict";
${text}
;return module.exports;`);
                factory(...args);
                ran = true;
            } catch (err) {
                const message = String((err && err.message) || err);
                lastError = message;
                const offender = injected.find((entry) => message.includes(entry.name)
                    && message.includes('already been declared'));
                if (!offender) break;                       // a real error: report it as is
                injected = injected.filter((entry) => entry !== offender);
            }
        }
        if (!ran) return { ok: false, name: '', errors: [`${label}: ${lastError || 'the module did not run'}`] };
        const exported = moduleShim.exports;
        const def = exported && exported.name ? exported : null;
        if (!def) {
            return { ok: false, name: '', errors: [`${label}: the module did not export a definition with a name`] };
        }
        const result = register(def);
        if (!result.ok) return { ok: false, name: def.name || '', errors: result.errors.map((e) => `${label}: ${e}`) };
        return { ok: true, name: def.name, warnings: result.warnings, errors: [] };
    }

    /* ── registry ─────────────────────────────────────────────────────────── */
    let API = null;                       // the public object, assigned before anything calls in
    const registered = new Map();

    function register(def) {
        const check = validate(def);
        if (!check.ok) return { ok: false, name: (def && def.name) || '', errors: check.errors, warnings: check.warnings };
        registered.set(def.name, { def, warnings: check.warnings });
        return { ok: true, name: def.name, warnings: check.warnings };
    }

    function list() {
        return [...registered.values()].map((entry) => ({
            name: entry.def.name,
            description: entry.def.description || entry.def.name,
            tags: entry.def.tags || ['Uncategorised'],
            params: entry.def.params || {},
            plots: entry.def.plots || {},
            areaChoice: entry.def.areaChoice || 'overlay',
            inputType: entry.def.inputType || 'any',
            /* An add-on file declares its pack and version; the built-ins predate the field. */
            pack: entry.def.pack || 'built-in',
            version: entry.def.version || '1.0.0',
            warnings: entry.warnings,
        }));
    }

    function get(name) { return registered.has(name) ? registered.get(name).def : null; }
    function clear() { registered.clear(); }

    API = {
        VERSION, paramSpecs, styles, plotters, meta, tools,
        validate, defaultsFor, coerceParams, entityAt, run, shiftedTime, dataBoxRows,
        loadModuleSource, requireShim, seriesView,
        registry: { register, list, get, clear },
    };
    return API;
})();

/* Two consumers, two paths: Node `require()`s it (the self-test and the pytest contract
   tests), and the browser needs it on `globalThis` — a top-level `const` alone is a
   lexical binding the injected indicator modules cannot see, which silently left the
   library empty. */
if (typeof module !== 'undefined' && module.exports) module.exports = StudyAPI;
if (typeof globalThis !== 'undefined') globalThis.StudyAPI = StudyAPI;
