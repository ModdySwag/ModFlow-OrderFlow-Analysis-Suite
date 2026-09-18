/* expression.selftest.js — the expression catalogue, pinned without a browser.
 *
 * The module is pure by design (a bar and a mode in, paint and words out), so everything it claims is
 * checkable here — including the two claims that would otherwise be adjectives:
 *
 *   · a colour-blind palette's pair stays apart for the dichromacy it is named after, AND for the
 *     other two, measured through the Machado (2009) simulation with the ΔE 40 floor;
 *   · the shipped green/red pair is the control that FAILS that same measurement under
 *     deuteranopia — which is why the palettes exist at all.
 *
 * Each palette also carries its measured numbers in the module; the selftest re-measures them and
 * fails on any disagreement, so a documented figure cannot drift away from the colour it describes.
 * The engine side of the same contract (the paint a renderer executes == the sentence the legend
 * prints) is pinned by `orderflow_system/test_expression.py`.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const SRC = fs.readFileSync(path.join(__dirname, 'expression.js'), 'utf8');

let ok = 0;
const failures = [];
function check(name, fn) {
    try { fn(); ok += 1; } catch (err) { failures.push(`${name} — ${err.message}`); }
}

/* Boot the IIFE with a window stub, the way the browser does. */
function boot() {
    const win = {};
    new Function('window', SRC)(win);
    return win.OFAPEXPR;
}
const E = boot();

const KINDS = ['protanopia', 'deuteranopia', 'tritanopia'];
const SHIPPED = { pos: '53,208,127', neg: '255,93,108' };     // math.theme bid/ask today

/* ── the simulation table's own self-checks ─────────────────────────────── */

check('the module exposes its whole surface', () => {
    for (const fn of ['mode', 'palette', 'pair', 'themeOverrides', 'barPaint', 'chartBars',
        'legendLines', 'simulate', 'deltaE', 'separation', 'splitVolumes', 'legibility']) {
        assert.strictEqual(typeof E[fn], 'function', fn + ' is missing');
    }
    assert.deepStrictEqual(E.MODE_KEYS, ['default', 'delta', 'split', 'heat', 'wick', 'candles']);
    assert.deepStrictEqual(E.PALETTE_KEYS, ['theme', 'deutan', 'protan', 'tritan']);
});

check('every CVD matrix is 9 numbers whose rows sum to 1 (grey in, grey out)', () => {
    for (const kind of KINDS) {
        const m = E.CVD_MATRICES[kind];
        assert.strictEqual(m.length, 9, `${kind} has ${m.length} entries`);
        for (let r = 0; r < 3; r += 1) {
            const sum = m[r * 3] + m[r * 3 + 1] + m[r * 3 + 2];
            /* The published table is rounded to six decimals, so "sums to 1" is exact only to that
               rounding — the property being checked is the neutral axis, not the sixth digit. */
            assert.ok(Math.abs(sum - 1) < 5e-5, `${kind} row ${r} sums to ${sum}`);
        }
    }
    for (const kind of KINDS) {
        const grey = E.simulate('128,128,128', kind);
        const spread = Math.max(...grey) - Math.min(...grey);
        assert.ok(spread <= 2, `${kind} shifts a neutral grey by ${spread}`);
    }
});

check('white and black survive every simulation', () => {
    for (const kind of KINDS) {
        assert.deepStrictEqual(E.simulate('255,255,255', kind), [255, 255, 255]);
        assert.deepStrictEqual(E.simulate('0,0,0', kind), [0, 0, 0]);
    }
});

check('deltaE is a real distance (black vs white = 100, order-independent)', () => {
    assert.ok(Math.abs(E.deltaE('0,0,0', '255,255,255') - 100) < 0.5, String(E.deltaE('0,0,0', '255,255,255')));
    assert.strictEqual(E.deltaE('10,20,30', '10,20,30'), 0);
    assert.ok(Math.abs(E.deltaE('86,180,233', '230,159,0') - E.deltaE('230,159,0', '86,180,233')) < 1e-9);
});

check('the metric can detect a collapse (pure red vs pure green, deuteranopia)', () => {
    const s = E.separation('255,0,0', '0,255,0', 'deuteranopia');
    assert.ok(!s.ok, `red/green measured dE ${s.dE} — the metric is not discriminating`);
});

/* ── the control: the shipped pair is why this feature exists ───────────── */

check('the shipped green/red pair collapses under deuteranopia (the control)', () => {
    const s = E.separation(SHIPPED.pos, SHIPPED.neg, 'deuteranopia');
    assert.ok(s.dE < E.MIN_PAIR_DE, `shipped pair measured dE ${s.dE}, expected under ${E.MIN_PAIR_DE}`);
    assert.ok(s.dE < 15, `shipped pair measured dE ${s.dE} — expected a near-collapse`);
});

/* ── every palette earns its name, under its own dichromacy AND the others ─ */

for (const key of E.PALETTE_KEYS) {
    const p = E.PALETTES[key];
    if (!p.pos) {
        check(`${key}: the theme palette writes no overrides`, () => {
            assert.deepStrictEqual(E.themeOverrides(key), {});
        });
        continue;
    }
    check(`${key}: its pair clears the floor under all three dichromacies`, () => {
        for (const kind of KINDS) {
            const s = E.separation(p.pos, p.neg, kind);
            assert.ok(s.ok, `${kind} measured dE ${s.dE} (floor ${E.MIN_PAIR_DE})`);
        }
    });
    check(`${key}: its own dichromacy is the one it is named for`, () => {
        assert.ok(KINDS.indexOf(p.cvd) >= 0, `${key} names cvd=${p.cvd}`);
        const own = E.separation(p.pos, p.neg, p.cvd);
        assert.ok(own.ok && own.dE >= 40, `${p.cvd} measured dE ${own.dE}`);
    });
    check(`${key}: the numbers it documents are the numbers it measures`, () => {
        for (const kind of KINDS) {
            const measured = E.separation(p.pos, p.neg, kind).dE;
            const documented = p.measured[kind];
            assert.ok(Math.abs(measured - documented) < 0.5,
                `${kind}: documented ${documented}, measured ${measured}`);
        }
    });
    check(`${key}: both colours are legible on the stage at the shading alpha`, () => {
        for (const c of [p.pos, p.neg]) {
            const l = E.legibility(c);
            assert.ok(l.ok, `rgb(${c}) lifts the ground ${l.ratio}x at alpha ${E.LEGIBILITY_ALPHA}`);
        }
    });
    check(`${key}: two hues only — every override is the palette's own pair`, () => {
        const over = E.themeOverrides(key);
        const keys = Object.keys(over);
        assert.ok(keys.length >= 8, `only ${keys.length} overrides: ${keys.join(',')}`);
        for (const k of keys) {
            assert.ok(over[k] === p.pos || over[k] === p.neg, `${k} -> ${over[k]} is a third hue`);
        }
        for (const k of ['bid', 'ask', 'up', 'down', 'imBuy', 'imSell', 'stackUp', 'stackDown']) {
            assert.ok(k in over, `no override for ${k}`);
        }
    });
    check(`${key}: pair() ignores the theme pair, the theme palette inherits it`, () => {
        assert.strictEqual(E.pair(key, { pos: '1,1,1', neg: '2,2,2' }).pos, p.pos);
        assert.deepStrictEqual(E.pair('theme', SHIPPED), { pos: SHIPPED.pos, neg: SHIPPED.neg });
        assert.deepStrictEqual(E.pair('nonsense', SHIPPED), { pos: SHIPPED.pos, neg: SHIPPED.neg });
    });
}

/* ── the six modes ─────────────────────────────────────────────────────── */

check('every mode names itself, its encoding and how the sign is carried', () => {
    for (const k of E.MODE_KEYS) {
        const m = E.MODES[k];
        assert.ok(m.label && m.says && m.pairing, `${k} is missing words`);
        assert.ok(m.chrome && typeof m.chrome.framing === 'boolean', `${k} has no chrome gates`);
    }
});

check('a junk mode or palette falls back to the default rather than drawing nothing', () => {
    assert.strictEqual(E.mode('nonsense').label, E.MODES.default.label);
    assert.strictEqual(E.barPaint({ open: 1, close: 2 }, {}).mode, 'default');
    assert.strictEqual(E.barPaint({ open: 1, close: 2 }, { mode: 'delta', palette: 'junk' }).palette, 'theme');
});

check('barPaint says exactly what its mode says (legend == drawing, by construction)', () => {
    for (const k of E.MODE_KEYS) {
        const paint = E.barPaint({ open: 1, close: 2, volume: 10, delta: 4 }, { mode: k, theme: SHIPPED });
        assert.strictEqual(paint.encoding, E.MODES[k].says, k);
        assert.strictEqual(paint.pairing, E.MODES[k].pairing, k);
        assert.strictEqual(paint.chrome.framing, E.MODES[k].chrome.framing, k);
    }
});

/* ── the paint decisions ────────────────────────────────────────────────── */

const upBar = { time: 1, open: 100, high: 110, low: 95, close: 105, volume: 20, delta: 5 };
const downBar = { time: 2, open: 105, high: 110, low: 95, close: 100, volume: 20, delta: -5 };

check('delta mode: body tinted by |delta|/volume, outline by direction, glyph by sign', () => {
    const up = E.barPaint(upBar, { mode: 'delta', theme: SHIPPED });
    const down = E.barPaint(downBar, { mode: 'delta', theme: SHIPPED });
    assert.ok(up.body && up.body.fill && up.body.stroke, 'no body');
    assert.ok(up.body.fill.indexOf('53,208,127') >= 0, up.body.fill);
    assert.ok(down.body.fill.indexOf('255,93,108') >= 0, down.body.fill);
    assert.strictEqual(up.glyph, '\u25b2');
    assert.strictEqual(down.glyph, '\u25bc');
    const weak = E.barPaint({ open: 100, close: 105, volume: 20, delta: 1 }, { mode: 'delta', theme: SHIPPED });
    const strong = E.barPaint({ open: 100, close: 105, volume: 20, delta: 20 }, { mode: 'delta', theme: SHIPPED });
    const alpha = (s) => Number(/,(0?\.\d+)\)$/.exec(s)[1]);
    assert.ok(alpha(strong.body.fill) > alpha(weak.body.fill),
        `${alpha(strong.body.fill)} should exceed ${alpha(weak.body.fill)}`);
    assert.ok(alpha(strong.body.fill) <= 0.40, 'a body alpha above 0.40 hides the cells it sits on');
});

check('heat mode: same direction, stronger and delta-driven fill', () => {
    const heat = E.barPaint(upBar, { mode: 'heat', theme: SHIPPED });
    const delta = E.barPaint(upBar, { mode: 'delta', theme: SHIPPED });
    const alpha = (s) => Number(/,(0?\.\d+)\)$/.exec(s)[1]);
    assert.ok(alpha(heat.body.fill) > alpha(delta.body.fill), 'heat should read stronger than a delta tint');
    assert.strictEqual(heat.glyph, '\u25b2');
    assert.strictEqual(heat.chrome.poc, true);
});

check('split mode: left = sell, right = buy, fractions sum to 1', () => {
    const p = E.barPaint(upBar, { mode: 'split', theme: SHIPPED });
    assert.ok(p.split, 'no split');
    assert.ok(Math.abs(p.split.left.frac + p.split.right.frac - 1) < 1e-9);
    assert.strictEqual(p.split.left.label, 'sell');
    assert.strictEqual(p.split.right.label, 'buy');
    assert.ok(p.split.left.rgba.indexOf('255,93,108') >= 0, p.split.left.rgba);
    assert.ok(p.split.right.rgba.indexOf('53,208,127') >= 0, p.split.right.rgba);
});

check('split volumes come from side volumes when the feed has them', () => {
    const v = E.splitVolumes({ volume: 20, delta: 4, buy_volume: 12, sell_volume: 8 });
    assert.deepStrictEqual([v.buy, v.sell], [12, 8]);
    assert.strictEqual(v.source, 'side volumes');
    const calc = E.splitVolumes({ volume: 20, delta: 4, calc: { buy: 13, sell: 7 } });
    assert.deepStrictEqual([calc.buy, calc.sell], [13, 7]);
});

check('split volumes are derived — and said to be derived — when they are not carried', () => {
    const v = E.splitVolumes({ volume: 20, delta: 4 });
    assert.deepStrictEqual([v.buy, v.sell], [12, 8]);
    assert.strictEqual(v.source, 'derived from volume and delta');
    const paint = E.barPaint({ open: 1, close: 2, volume: 20, delta: 4 }, { mode: 'split', theme: SHIPPED });
    assert.strictEqual(paint.split.source, 'derived from volume and delta');
});

check('split mode with no volume at all: honest, not a fake half', () => {
    const v = E.splitVolumes({ open: 1, close: 2 });
    assert.strictEqual(v.source, 'no volume in this bar');
    const p = E.barPaint({ open: 1, close: 2 }, { mode: 'split', theme: SHIPPED });
    assert.ok(Math.abs(p.split.left.frac - 0.5) < 1e-9 && Math.abs(p.split.right.frac - 0.5) < 1e-9);
});

check('split mode never divides by zero and never runs negative', () => {
    const odd = E.splitVolumes({ volume: 5, delta: 50 });
    assert.ok(odd.sell === 0 && odd.buy === 5, JSON.stringify(odd));
    const negVol = E.splitVolumes({ volume: -5, delta: -1 });
    assert.ok(negVol.buy >= 0 && negVol.sell >= 0, JSON.stringify(negVol));
});

check('wick mode: no body, no chrome, badges kept', () => {
    const p = E.barPaint(upBar, { mode: 'wick', theme: SHIPPED });
    assert.strictEqual(p.body, null);
    assert.strictEqual(p.split, null);
    assert.strictEqual(p.chrome.framing, false);
    assert.strictEqual(p.chrome.poc, false);
    assert.strictEqual(p.chrome.zones, false);
    assert.strictEqual(p.chrome.badges, true, 'the badge is the text carrier and must survive');
    assert.ok(p.wick.rgba && p.wick.lineWidth >= 1);
});

check('candles: a saturated body by direction, no cells, no chrome', () => {
    const p = E.barPaint(upBar, { mode: 'candles', theme: SHIPPED });
    assert.ok(p.body && p.body.fill && p.body.stroke, 'candles draw a body');
    assert.strictEqual(p.split, null);
    assert.strictEqual(p.chrome.cells, false, 'the cells are off — the body is the encode');
    assert.strictEqual(p.chrome.framing, false);
    assert.strictEqual(p.chrome.poc, false);
    assert.strictEqual(p.chrome.badges, false);
    assert.ok(p.wick && p.wick.lineWidth >= 1);
});
check('candles: direction rides the glyph and the wick tint', () => {
    const up = E.barPaint(upBar, { mode: 'candles', theme: SHIPPED });
    const dn = E.barPaint(downBar, { mode: 'candles', theme: SHIPPED });
    assert.ok(up.glyph && dn.glyph && up.glyph !== dn.glyph, 'direction needs a second carrier');
    assert.notStrictEqual(up.wick.rgba, dn.wick.rgba);
});
check('candles: the chart view declares support', () => {
    assert.strictEqual(E.CHART_SUPPORT.candles, true);
});

check('the default mode changes nothing about today\'s chrome', () => {
    const p = E.barPaint(upBar, { mode: 'default', theme: SHIPPED });
    assert.strictEqual(p.body, null);
    assert.deepStrictEqual(p.chrome, { framing: true, ground: true, zones: true, poc: true, badges: true });
});

check('a flat bar takes its direction from delta', () => {
    assert.strictEqual(E.dirOf({ open: 100, close: 100, delta: 3 }), 1);
    assert.strictEqual(E.dirOf({ open: 100, close: 100, delta: -3 }), -1);
    assert.strictEqual(E.dirOf({ open: 100, close: 100, delta: 0 }), 0);
    assert.strictEqual(E.barPaint({ open: 100, close: 100, delta: -3 }, { mode: 'delta' }).glyph, '\u25bc');
    assert.strictEqual(E.dirOf({ open: 100, close: 105 }), 1);
});

check('deltaShare is clipped to 0..1 and 0 without volume', () => {
    assert.strictEqual(E.deltaShare({ volume: 0, delta: 5 }), 0);
    assert.strictEqual(E.deltaShare({ volume: 10, delta: 4 }), 0.4);
    assert.strictEqual(E.deltaShare({ volume: 10, delta: 400 }), 1);
    assert.strictEqual(E.deltaShare({ volume: 10, delta: -4 }), 0.4);
});

/* ── the chart view's projection ────────────────────────────────────────── */

const bars = [
    { time: 1, open: 100, high: 110, low: 95, close: 105, volume: 20, delta: 5 },
    { time: 2, open: 105, high: 110, low: 95, close: 100, volume: 20, delta: -5 },
];

check('chartBars keeps the OHLC contract and the bar count', () => {
    for (const k of E.MODE_KEYS) {
        const rows = E.chartBars(bars, { mode: k, theme: SHIPPED });
        assert.strictEqual(rows.length, 2);
        for (let i = 0; i < 2; i += 1) {
            for (const f of ['time', 'open', 'high', 'low', 'close']) {
                assert.strictEqual(rows[i][f], bars[i][f], `${k}.${f}`);
            }
        }
    }
});

check('chartBars: default paints direction from the pair, per bar', () => {
    const rows = E.chartBars(bars, { mode: 'default', theme: SHIPPED });
    assert.ok(rows[0].color.indexOf('53,208,127') >= 0, rows[0].color);
    assert.ok(rows[1].color.indexOf('255,93,108') >= 0, rows[1].color);
    assert.strictEqual(rows[0].borderColor, rows[0].color);
});

check('chartBars: wick mode strips the body and keeps the wick', () => {
    const rows = E.chartBars(bars, { mode: 'wick', theme: SHIPPED });
    assert.strictEqual(rows[0].color, 'rgba(0,0,0,0)');
    assert.strictEqual(rows[0].borderColor, 'rgba(0,0,0,0)');
    assert.ok(rows[0].wickColor.indexOf('53,208,127') >= 0, rows[0].wickColor);
});

check('chartBars: delta/heat carry a body colour and a direction outline', () => {
    for (const k of ['delta', 'heat']) {
        const rows = E.chartBars(bars, { mode: k, theme: SHIPPED });
        assert.ok(rows[0].color && rows[0].borderColor && rows[0].wickColor, k);
        assert.ok(rows[0].borderColor.indexOf('53,208,127') >= 0, `${k} border ${rows[0].borderColor}`);
        assert.ok(rows[1].borderColor.indexOf('255,93,108') >= 0, `${k} border ${rows[1].borderColor}`);
    }
});

check('chartBars: every colour it hands the vendor parses as CSS', () => {
    /* Lightweight Charts parses colours and THROWS on a bare 'r,g,b' triplet -- measured live:
       `Error: Cannot parse color: 86,180,233` out of the vendor's own paint path, and the shell's
       fatal handler turned that into a wiped app. The pair table keeps triplets (the canvas
       renderers compose them with alpha); the chart projection must wrap them. */
    const isCss = (c) => typeof c === 'string'
        && (c.indexOf('rgb(') === 0 || c.indexOf('rgba(') === 0 || c.indexOf('#') === 0 || c === 'transparent');
    let checked = 0;
    for (const k of E.MODE_KEYS) {
        for (const p of E.PALETTE_KEYS) {
            const rows = E.chartBars(bars, { mode: k, palette: p, theme: SHIPPED });
            for (const row of rows) {
                for (const f of ['color', 'borderColor', 'wickColor']) {
                    assert.ok(isCss(row[f]), `${k}/${p} ${f} = ${JSON.stringify(row[f])}`);
                    checked += 1;
                }
            }
        }
    }
    assert.strictEqual(checked, E.MODE_KEYS.length * E.PALETTE_KEYS.length * 2 * 3);
});

check('the chart surface declares which modes it cannot draw', () => {
    assert.strictEqual(E.CHART_SUPPORT.split, false, 'split has no vendor equivalent — say so');
    for (const k of ['default', 'delta', 'heat', 'wick']) {
        assert.strictEqual(E.CHART_SUPPORT[k], true, k);
    }
});

/* ── the words ──────────────────────────────────────────────────────────── */

check('legendLines names the mode, the sign and the palette in use', () => {
    const lines = E.legendLines('split', 'deutan', { ramp: 'thermal', splitSource: 'side volumes' });
    assert.ok(lines[0].indexOf('split candle') >= 0, lines[0]);
    assert.ok(lines[0].indexOf(E.MODES.split.says) >= 0, lines[0]);
    assert.ok(lines.some((l) => l.indexOf('deutan-safe') >= 0), lines.join(' | '));
    assert.ok(lines.some((l) => l.indexOf('two') >= 0 || l.indexOf('palette maps') >= 0), lines.join(' | '));
    assert.ok(lines.some((l) => l.indexOf('depth ramp: thermal') >= 0), lines.join(' | '));
    assert.ok(lines.some((l) => l.indexOf('split volumes: side volumes') >= 0), lines.join(' | '));
});

check('legendLines says the theme palette is the measured weak one', () => {
    const lines = E.legendLines('default', 'theme', {});
    assert.ok(lines.some((l) => l.indexOf('palette note:') >= 0 && l.indexOf('collapse') >= 0), lines.join(' | '));
});

check('a chart gap is spoken, never silent', () => {
    const lines = E.legendLines('split', 'tritan', { chartGap: 'chart view cannot draw split' });
    assert.ok(lines.some((l) => l.indexOf('chart view cannot draw split') >= 0));
});

check('legendLines never returns an empty or undefined line', () => {
    for (const k of E.MODE_KEYS) {
        for (const p of E.PALETTE_KEYS) {
            const lines = E.legendLines(k, p, {});
            assert.ok(lines.length >= 3, `${k}/${p}`);
            for (const l of lines) assert.ok(typeof l === 'string' && l.length > 3 && l.indexOf('undefined') < 0, `${k}/${p}: ${l}`);
        }
    }
});

/* ── purity ─────────────────────────────────────────────────────────────── */

check('the module is pure: no DOM, no API, no storage, no timer', () => {
    for (const banned of ['document', 'fetch(', 'localStorage', 'setInterval', 'XMLHttpRequest', 'api(']) {
        assert.ok(SRC.indexOf(banned) < 0, `expression.js mentions ${banned}`);
    }
});

const failed = failures.length;
console.log(`expression selftest: ${ok} ok, ${failed} failed`);
for (const f of failures) console.log('  FAIL ' + f);
process.exit(failed ? 1 : 0);
