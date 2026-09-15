/* Contract self-test for StudyAPI + the shipped studies (`node study-api.selftest.js`).

   The runtime is the part of this build that third-party indicator code touches, so its
   contract is tested the way the app uses it: load the real modules, run them over
   synthetic bars, and assert the documented behaviour — including the failure paths, since
   a study that throws must degrade to an error message, never take the chart down. */
const path = require('path');
const StudyAPI = require('./study-api.js');

const DIR = path.join(__dirname, 'indicators');
const STUDIES = ['price-offset.js', 'ema.js', 'double-ema.js', 'atr-signal.js', 'alligator.js', 'delta-flow.js']
    .map((f) => ({ file: f, def: require(path.join(DIR, f)) }));

let passed = 0;
const failures = [];
function check(name, cond, detail) {
    if (cond) { passed += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

/* ── synthetic bars: varying prices AND tape fields ─────────────────────── */
function bars(n) {
    const out = [];
    let price = 100;
    for (let i = 0; i < n; i += 1) {
        const step = (i % 5 === 0 ? -0.9 : 0.45) + (i % 3) * 0.05;
        const open = price;
        price = Math.max(1, price + step);
        const close = price;
        const high = Math.max(open, close) + 0.3;
        const low = Math.min(open, close) - 0.3;
        const buy = 10 + (i % 7) * 2;
        const sell = 10 + (i % 4) * 3;
        out.push({ time: 1700000000 + i * 60, open, high, low, close,
                   volume: buy + sell, buy_volume: buy, sell_volume: sell, bar_delta: buy - sell });
    }
    return out;
}
const BARS = bars(60);

/* ── validation ─────────────────────────────────────────────────────────── */
check('validate: rejects non-objects', StudyAPI.validate(null).ok === false);
check('validate: requires a name', StudyAPI.validate({ calculator: { map() {} } }).errors
    .some((e) => e.includes('name is required')));
check('validate: rejects a bad name',
    StudyAPI.validate({ name: '2 bad name', calculator: { map() {} } }).errors
    .some((e) => e.includes('must start with a letter')));
check('validate: requires map()', StudyAPI.validate({ name: 'x', calculator: {} }).errors
    .some((e) => e.includes('calculator.map() is required')));
check('validate: catches an unknown param type',
    StudyAPI.validate({ name: 'x', calculator: { map() {} }, params: { p: { type: 'date' } } }).errors
    .some((e) => e.includes('unknown type')));
check('validate: enum needs options',
    StudyAPI.validate({ name: 'x', calculator: { map() {} }, params: { p: { type: 'enum' } } }).errors
    .some((e) => e.includes('without restrictions.options')));
check('validate: plotter field must exist in plots',
    StudyAPI.validate({ name: 'x', calculator: { map() {} }, plots: { a: { title: 'A' } },
        plotter: StudyAPI.plotters.singleline('b') }).errors.some((e) => e.includes('not in plots')));
check('validate: a module with no plots gets the default "value" plot, not a warning',
    (() => {
        const def = { name: 'noPlots', calculator: { map() {} } };
        const res = StudyAPI.validate(def);
        return res.ok && !res.warnings.some((w) => w.includes('no plots'))
            && !!def.plots && !!def.plots.value;
    })());
check('validate: every shipped study is valid', STUDIES.every((s) => StudyAPI.validate(s.def).ok),
    STUDIES.filter((s) => !StudyAPI.validate(s.def).ok).map((s) => s.file + ': ' + StudyAPI.validate(s.def).errors.join(', ')).join(' | '));

/* ── defaults + coercion ────────────────────────────────────────────────── */
const ema = STUDIES.find((s) => s.file === 'ema.js').def;
check('defaults come from the spec', StudyAPI.defaultsFor(ema).period === 21);
const atr = STUDIES.find((s) => s.file === 'atr-signal.js').def;
check('number params clamp to their restrictions',
    StudyAPI.coerceParams(atr, { period: 9999, threshold: -5 }).period === 1000
    && StudyAPI.coerceParams(atr, { threshold: -5 }).threshold === 0);
check('junk numeric input falls back to the default',
    StudyAPI.coerceParams(atr, { period: 'abc' }).period === 14);
const deltaFlow = STUDIES.find((s) => s.file === 'delta-flow.js').def;
check('booleans coerce from strings', StudyAPI.coerceParams(deltaFlow, { signal: 'false' }).signal === false);
const enums = { name: 'e', calculator: { map() {} }, params: { mode: StudyAPI.paramSpecs.enumDef(['a', 'b'], 'a') } };
check('enum falls back to its default', StudyAPI.coerceParams(enums, { mode: 'zzz' }).mode === 'a');
check('text is truncated to the declared limit',
    StudyAPI.coerceParams({ name: 't', calculator: { map() {} },
        params: { s: StudyAPI.paramSpecs.text('x') } }, { s: 'y'.repeat(400) }).s.length === 160);

/* ── running the shipped studies ────────────────────────────────────────── */
const offset = STUDIES.find((s) => s.file === 'price-offset.js').def;
const offRun = StudyAPI.run(offset, BARS, { offset: 2 }, { tickSize: 0.25 });
check('price offset: ok, no errors', offRun.ok && offRun.errors.length === 0);
check('price offset: value = close - offset',
    offRun.plots.value.length === BARS.length
    && Math.abs(offRun.plots.value[10].value - (BARS[10].close - 2)) < 1e-9);
check('price offset: a bare number becomes { value }', offRun.plots.value.every((p) => 'value' in p));

const emaRun = StudyAPI.run(ema, BARS, { period: 5 }, { tickSize: 0.01 });
check('ema: one point per bar, first value = first close',
    emaRun.plots.value.length === BARS.length
    && Math.abs(emaRun.plots.value[0].value - BARS[0].close) < 1e-9);
check('ema: converges towards the price', Number.isFinite(emaRun.plots.value.at(-1).value));

const dbl = STUDIES.find((s) => s.file === 'double-ema.js').def;
const dblRun = StudyAPI.run(dbl, BARS, {}, { tickSize: 0.01 });
check('double ema: two plots', Object.keys(dblRun.plots).sort().join(',') === 'fast,slow');
check('double ema: the slow average lags the fast one at a turning point',
    dblRun.plots.fast.length === BARS.length && dblRun.plots.slow.length === BARS.length);

const atrRun = StudyAPI.run(atr, BARS, { period: 5, threshold: 1 }, { tickSize: 0.25 });
check('atr: columns plot, no errors', atrRun.ok && atrRun.plots.value.length > 0);
check('atr: a tight threshold styles bars and candlesticks',
    atrRun.plots.value.some((p) => p.style && p.style.color)
    && atrRun.plots.value.some((p) => p.candlestick && p.candlestick.color));
check('atr: tick size comes from the contract context',
    StudyAPI.run(atr, BARS, { period: 5, threshold: 1e9 }, { tickSize: 0.25 })
        .plots.value.every((p) => !p.style));

const alli = StudyAPI.run(STUDIES.find((s) => s.file === 'alligator.js').def, BARS, {}, {});
check('alligator: three plots, each warm-up shorter than the bar count',
    ['jaw', 'teeth', 'lips'].every((k) => alli.plots[k].length > 40 && alli.plots[k].length < BARS.length)
    && alli.plots.jaw.length < alli.plots.lips.length);          // 13-period jaw warms up slower than the 5-period lips

const flow = StudyAPI.run(deltaFlow, BARS, { window: 10, sigma: 0.5, signal: true }, { tickSize: 0.01 });
check('delta flow: reads this build\'s tape fields',
    flow.plots.delta.some((p) => p.value > 0) && flow.plots.delta.some((p) => p.value < 0));
check('delta flow: emits signals with marker geometry',
    flow.markers.length > 0 && flow.markers.every((m) => m.time && m.shape && m.position));
check('delta flow: alerts carry side + value',
    flow.alerts.length === flow.markers.length && flow.alerts.every((a) => a.side && a.time));
check('delta flow: signal=false suppresses markers',
    StudyAPI.run(deltaFlow, BARS, { window: 10, sigma: 0.5, signal: false }, {}).markers.length === 0);
check('delta flow: noise-free when sigma is huge',
    StudyAPI.run(deltaFlow, BARS, { window: 10, sigma: 1e6, signal: true }, {}).markers.length === 0);

/* ── filter(), prior(), errors, data box ────────────────────────────────── */
const filtering = {
    name: 'warmupOnly', calculator: class {
        map(d, i) { return i < 10 ? undefined : d.value(); }
        filter(entity) { return entity.value === undefined ? true : entity.value > 0; }
    },
};
const warm = StudyAPI.run(filtering, bars(20), {}, {});
check('undefined results leave gaps, they do not throw', warm.ok && warm.errors.length === 0);

const throwing = { name: 'boom', calculator: class { map(d, i) { if (i === 3) throw new Error('boom at 3'); return d.value(); } } };
const boom = StudyAPI.run(throwing, bars(10), {}, {});
check('a throwing map() is reported, not swallowed', boom.ok === false && boom.errors[0].includes('bar 3'));
check('a throwing map() stops the run but keeps what it had', boom.plots.value.length === 3);

const usesPrior = { name: 'upDown', calculator: class { map(d) { const p = d.prior(); return p ? d.close() - p.close() : undefined; } } };
const priorRun = StudyAPI.run(usesPrior, bars(5), {}, {});
check('prior() reaches the previous bar and is undefined at the start',
    priorRun.plots.value.length === 4 && priorRun.plots.value[0].index === 1);

const noPlots = { name: 'plain', calculator: class { map(d) { return d.value(); } } };
const plain = StudyAPI.run(noPlots, bars(5), {}, {});
check('a definition without plots lands in "value"', plain.plots.value.length === 5);

const displayOnly = { name: 'hidden', description: 'Hidden',
    calculator: { map(d) { return { value: d.value(), ghost: d.close() }; } },
    plots: { value: { title: 'Shown' }, ghost: { title: 'Ghost', displayOnly: true } } };
const shown = StudyAPI.run(displayOnly, bars(5), {}, {});
const rows = StudyAPI.dataBoxRows(displayOnly, shown, 4);
check('data box: displayOnly plots are computed but kept out of the box',
    shown.plots.ghost.length === 5 && rows.length === 1 && !rows.some((r) => r.plot === 'Ghost'));
check('data box: value for the requested bar',
    rows.find((r) => r.plot === 'Shown').value === bars(5)[4].close);

check('shifts move a plot on the X axis',
    StudyAPI.shiftedTime(BARS, 5, 2) === BARS[7].time && StudyAPI.shiftedTime(BARS, 5, -2) === BARS[3].time);

/* ── the registry ───────────────────────────────────────────────────────── */
StudyAPI.registry.clear();
const reg = STUDIES.map((s) => StudyAPI.registry.register(s.def));
check('registry: every study registers', reg.every((r) => r.ok));
check('registry: no duplicates by name', new Set(STUDIES.map((s) => s.def.name)).size === STUDIES.length);
const listed = StudyAPI.registry.list();
check('registry: list() exposes UI metadata', listed.length === STUDIES.length
    && listed.every((s) => s.name && s.tags.length && typeof s.areaChoice === 'string'));
check('registry: tags group the pack', new Set(listed.flatMap((s) => s.tags)).size >= 5);
check('registry: a bad module is refused', StudyAPI.registry.register({ name: 'bad', calculator: {} }).ok === false);
check('registry: get() returns the definition', StudyAPI.registry.get('deltaFlow').name === 'deltaFlow');

console.log(`study-api selftest: ${passed} ok, ${failures.length} failed`);
failures.forEach((f) => console.log('  FAIL ' + f));
process.exit(failures.length ? 1 : 0);
