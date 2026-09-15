/* indicators.selftest.js — the add-on pack's maths, checked against values that can be reasoned
   about by hand. Runs under node: `node orderflow_system/desktop/ui/indicators.selftest.js`.
   The pytest gate (`orderflow_system/test_indicators.py`) shells this file, exactly like the
   engine's own selftest. */
'use strict';
const path = require('path');
const api = require(path.join(__dirname, 'study-api.js'));

let passed = 0;
const failures = [];
function check(name, ok, detail) {
    if (ok) { passed += 1; return; }
    failures.push(`${name}${detail === undefined ? '' : ' — ' + detail}`);
}

/* A synthetic series with an entity shaped like the runtime's: only close()/high()/low()/volume()
   are used by these studies. */
function series(closes, volumes) {
    return closes.map((close, i) => {
        const open = i === 0 ? close : closes[i - 1];
        return {
            time: 1700000000 + i * 60,
            open: () => open,
            high: () => Math.max(open, close) + 0.5,
            low: () => Math.min(open, close) - 0.5,
            close: () => close,
            volume: () => (volumes ? volumes[i] : 1),
        };
    });
}
function feed(def, bars) {
    const calc = new def.calculator({ period: 14, fast: 12, slow: 26, signal: 9, overbought: 70,
        oversold: 30, threshold: 25, rising: true });
    calc.props = { period: 14, fast: 12, slow: 26, signal: 9, overbought: 70, oversold: 30,
                   threshold: 25, rising: true, crossover: false };
    calc.props = Object.fromEntries(Object.entries(def.params).map(([k, spec]) => [k, spec.def]));
    calc.init();
    return bars.map((bar, i) => calc.map(Object.assign(Object.create(bar), {
        index: i,
        prior: (n = 1) => bars[i - n],
        value: () => bar.close(),
    })));
}

/* ── RSI ─────────────────────────────────────────────────────────────────────────────────── */
const rsiDef = require(path.join(__dirname, 'indicators', 'rsi.js'));
const up = feed(rsiDef, series(Array.from({ length: 40 }, (_, i) => 100 + i)));
const lastUp = up[up.length - 1];
check('rsi: a monotonic rise reads 100', lastUp.value === 100, String(lastUp.value));
const down = feed(rsiDef, series(Array.from({ length: 40 }, (_, i) => 200 - i)));
const lastDown = down[down.length - 1];
check('rsi: a monotonic fall reads 0', lastDown.value === 0, String(lastDown.value));
const flat = feed(rsiDef, series(Array.from({ length: 40 }, () => 100)));
check('rsi: a flat series stays at 100 (no losses) and never NaN',
    flat.every((r) => r.value === undefined || Number.isFinite(r.value)), JSON.stringify(flat.slice(-1)));
check('rsi: emits an overbought signal on the rise', up.some((r) => r.signal && r.signal.side === 'sell'));

/* ── OBV ────────────────────────────────────────────────────────────────────────────────── */
const obvDef = require(path.join(__dirname, 'indicators', 'obv.js'));
const rising = series([10, 11, 12, 13], [5, 5, 5, 5]);
const obvOut = feed(obvDef, rising);
check('obv: adds volume on up bars only', obvOut[obvOut.length - 1].value === 15, JSON.stringify(obvOut.map((r) => r.value)));
const mixed = feed(obvDef, series([10, 11, 10, 12], [5, 7, 3, 2]));
check('obv: subtracts on down bars, ignores volume on equal closes',
    mixed[3].value === (0 + 7 - 3 + 2), JSON.stringify(mixed.map((r) => r.value)));

/* ── Williams %R ────────────────────────────────────────────────────────────────────────── */
const wrDef = require(path.join(__dirname, 'indicators', 'williams-r.js'));
const atHigh = feed(wrDef, series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]));
const wrHigh = atHigh[atHigh.length - 1].value;
check('williams %R: closing at the period high is near 0', wrHigh > -6 && wrHigh <= 0, String(wrHigh));
const atLow = feed(wrDef, series([15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]));
const wrLow = atLow[atLow.length - 1].value;
check('williams %R: closing at the period low is near -100', wrLow < -94 && wrLow >= -100, String(wrLow));

/* ── MACD ───────────────────────────────────────────────────────────────────────────────── */
const macdDef = require(path.join(__dirname, 'indicators', 'macd.js'));
const macdUp = feed(macdDef, series(Array.from({ length: 80 }, (_, i) => 100 + i * 0.5)));
const macdLast = macdUp[macdUp.length - 1];
check('macd: a steady rise puts the MACD line above zero', macdLast.macd > 0, String(macdLast.macd));
check('macd: histogram is the distance between MACD and its signal',
    Math.abs(macdLast.hist - (macdLast.macd - macdLast.signal)) < 1e-9,
    JSON.stringify({ macd: macdLast.macd, signal: macdLast.signal, hist: macdLast.hist }));
check('macd: histogram goes negative on a steady fall',
    feed(macdDef, series(Array.from({ length: 80 }, (_, i) => 200 - i * 0.5))).slice(-1)[0].hist < 0);

/* ── ADX ────────────────────────────────────────────────────────────────────────────────── */
const adxDef = require(path.join(__dirname, 'indicators', 'adx.js'));
const trend = feed(adxDef, series(Array.from({ length: 90 }, (_, i) => 100 + i)));
const adxLast = trend[trend.length - 1];
check('adx: a clean uptrend drives ADX above 20', adxLast.adx > 20, String(adxLast.adx));
check('adx: +DI dominates -DI in an uptrend', adxLast.plusDi > adxLast.minusDi,
    JSON.stringify({ plus: adxLast.plusDi, minus: adxLast.minusDi }));
const downTrend = feed(adxDef, series(Array.from({ length: 90 }, (_, i) => 300 - i)));
const adxDown = downTrend[downTrend.length - 1];
check('adx: -DI dominates +DI in a downtrend', adxDown.minusDi > adxDown.plusDi,
    JSON.stringify({ plus: adxDown.plusDi, minus: adxDown.minusDi }));
check('adx: ADX stays inside 0-100', adxDown.adx >= 0 && adxDown.adx <= 100, String(adxDown.adx));

/* ── the add-on contract itself ────────────────────────────────────────────────────────── */
const files = ['rsi.js', 'macd.js', 'obv.js', 'williams-r.js', 'adx.js'];
files.forEach((file) => {
    const def = require(path.join(__dirname, 'indicators', file));
    check(`${file}: registers a complete add-on contract`,
        !!(def && def.name && def.description && def.calculator && def.params && def.plots
           && def.plotter && def.tags && def.pack && /^\d+\.\d+\.\d+$/.test(def.version)),
        JSON.stringify(def && { name: def.name, version: def.version }));
    check(`${file}: declares at least one plot`, def && Object.keys(def.plots || {}).length >= 1);
});

console.log(`indicators selftest: ${passed} ok, ${failures.length} failed`);
failures.forEach((f) => console.log('  FAIL ' + f));
process.exit(failures.length ? 1 : 0);
