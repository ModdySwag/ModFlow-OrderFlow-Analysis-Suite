/* ramp.selftest.js — the heat-scheme module's own behaviour, pinned without a browser.

   `node desktop/ui/ramp.selftest.js` prints "ramp selftest: N ok, M failed" and exits non-zero on
   any failure, so `test_b2_ramps.py` can gate the suite on it. */
'use strict';

const R = require('./ramp.js');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}
const near = (a, b, tol = 1e-9) => Math.abs(a - b) <= tol;

/* ── contrast ────────────────────────────────────────────────────────────── */
check('contrast: 1 is the identity at every sample',
    [0, 0.1, 0.5, 0.9, 1].every((t) => near(R.contrastT(t, 1), t)));
check('contrast: above 1 darkens the middle', R.contrastT(0.5, 2) < 0.5 && near(R.contrastT(0.5, 2), 0.25));
check('contrast: below 1 lifts the middle',
    R.contrastT(0.5, 0.5) > 0.5 && near(R.contrastT(0.5, 0.5), Math.sqrt(0.5)));
check('contrast: endpoints stay pinned', near(R.contrastT(0, 2.5), 0) && near(R.contrastT(1, 2.5), 1));
check('contrast: monotone in t', R.contrastT(0.2, 1.5) < R.contrastT(0.8, 1.5));
check('contrast: junk gamma behaves as 1',
    near(R.contrastT(0.3, 'junk'), 0.3) && near(R.contrastT(0.3, null), 0.3));
check('contrast: out-of-range clamps, never extrapolates',
    near(R.contrastT(0.5, 99), R.contrastT(0.5, R.CONTRAST_MAX)));
check('contrast: negative t floors at 0', near(R.contrastT(-3, 1.5), 0));

/* ── percentiles / floor ─────────────────────────────────────────────────── */
const list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
check('percentile: p0 is the minimum', R.percentile(list, 0) === 1);
check('percentile: p100 is the maximum', R.percentile(list, 100) === 10);
check('percentile: p25 of ten elements', R.percentile(list, 25) === 3);
check('percentile: p75 of ten elements', R.percentile(list, 75) === 8);
check('percentile: an empty list is null',
    R.percentile([], 50) === null && R.percentile(null, 50) === null);
check('percentile: junk p floors at 0', R.percentile(list, 'junk') === R.percentile(list, 0));
check('floor: the exact size passes through', R.floorValue(list, 4, 0) === 4);
check('floor: the share alone resolves from the list', R.floorValue(list, 0, 50) === 6);
check('floor: the larger of the two wins',
    R.floorValue(list, 7, 50) === 7 && R.floorValue(list, 1, 50) === 6);
check('floor: both off is zero', R.floorValue(list, 0, 0) === 0);
check('floor: junk is off', R.floorValue(list, 'x', 'y') === 0);

/* ── T10/B3: vertical smoothing ────────────────────────────────── */
check('smooth: strength 0 is the identity', (() => {
    const v = [1, 5, 2, 8, 3];
    const out = R.smoothVector(v, 0);
    return v.every((x, i) => Math.abs(out[i] - x) < 1e-12);
})());
check('smooth: a constant vector stays constant', (() => {
    const out = R.smoothVector([4, 4, 4, 4], 0.6);
    return out.every((x) => Math.abs(x - 4) < 1e-12);
})());
check('smooth: a spike spreads to its neighbours and lowers the peak', (() => {
    const out = R.smoothVector([0, 0, 9, 0, 0], 0.6);
    return out[2] < 9 && out[1] > 0 && out[3] > 0 && out[1] === out[3] && out[0] === 0 && out[4] === 0;
})());
check('smooth: mirrored input gives mirrored output', (() => {
    const a = R.smoothVector([1, 2, 9, 2, 1], 0.6);
    return Math.abs(a[0] - a[4]) < 1e-12 && Math.abs(a[1] - a[3]) < 1e-12;
})());
check('smooth: empty and junk vectors are safe',
    R.smoothVector([], 0.6).length === 0 && R.smoothVector(['x', 2], 0.6).every(Number.isFinite));
check('smooth: decision engages below the band',
    R.smoothDecision(2.0, false) === true && R.smoothDecision(3.0, false) === false);
check('smooth: decision releases only past the band',
    R.smoothDecision(3.5, true) === true && R.smoothDecision(4.2, true) === false);
check('smooth: decision thresholds are settable',
    R.smoothDecision(5, false, 6, 9) === true && R.smoothDecision(7, true, 6, 9) === true && R.smoothDecision(9.5, true, 6, 9) === false);
check('smooth: mode clamps junk to auto',
    R.smoothMode('none') === 'none' && R.smoothMode('manual') === 'manual' && R.smoothMode('junk') === 'auto' && R.smoothMode(undefined) === 'auto');
check('floor: an empty surface can never gate', R.floorValue([], 0, 30) === 0);
check('floor: a share past the module bound clamps to the bound',
    R.floorValue(list, 0, 500) === R.percentile(list, R.FLOOR_PCT_MAX));

/* ── the schemes ─────────────────────────────────────────────────────────── */
check('schemes: four, unique ids',
    R.SCHEMES.length === 4 && new Set(R.SCHEMES.map((s) => s.id)).size === 4);
check('schemes: every dial inside the module bounds',
    R.SCHEMES.every((s) => s.contrast >= R.CONTRAST_MIN && s.contrast <= R.CONTRAST_MAX
        && s.floor >= 0 && s.floor_pct >= 0 && s.floor_pct <= R.FLOOR_PCT_MAX
        && s.ceiling_pct > 0 && s.ceiling_pct <= 25));
check('schemes: balanced is the shipped recipe (5 / 0 / 0 / 1)', (() => {
    const b = R.schemeById('balanced');
    return b.ceiling_pct === 5 && b.floor === 0 && b.floor_pct === 0 && b.contrast === 1;
})());
check('schemes: every entry carries a label and a sentence',
    R.SCHEMES.every((s) => s.label && s.says));
check('schemes: lookup of junk is null', R.schemeById('nope') === null);

/* matchScheme: a round trip per scheme, 'custom' for a tweak and for a pinned ceiling. */
for (const s of R.SCHEMES) {
    check('match: ' + s.id + ' matches its own dials',
        R.matchScheme({ ceiling_pct: s.ceiling_pct, ceiling_abs: 0, floor: s.floor,
            floor_pct: s.floor_pct, contrast: s.contrast }) === s.id);
}
check('match: a hand-tweaked contrast reads custom',
    R.matchScheme({ ceiling_pct: 2, ceiling_abs: 0, floor: 0, floor_pct: 6, contrast: 1.2 }) === 'custom');
check('match: a pinned absolute ceiling is custom even at scheme values',
    R.matchScheme({ ceiling_pct: 5, ceiling_abs: 250, floor: 0, floor_pct: 0, contrast: 1 }) === 'custom');
check('match: a float round trip through a config is still the scheme',
    R.matchScheme({ ceiling_pct: 5.0000001, ceiling_abs: 0, floor: 0, floor_pct: 0,
        contrast: 1.0000001 }) === 'balanced');

/* ── dotted paths ────────────────────────────────────────────────────────── */
check('paths: getIn reads a dotted path', R.getIn({ a: { b: { c: 5 } } }, 'a.b.c', 0) === 5);
check('paths: getIn falls back on the missing tail',
    R.getIn({ a: {} }, 'a.b.c', 7) === 7 && R.getIn(null, 'a', 8) === 8);
check('paths: setIn creates the missing blocks',
    (() => { const o = {}; R.setIn(o, 'a.b.c', 9); return o.a.b.c === 9; })());
check('paths: setIn overwrites a leaf',
    (() => { const o = { a: { b: 1 } }; R.setIn(o, 'a.b', 2); return o.a.b === 2; })());

/* ── B5: the dimming and highlight clamps ──────────────────────────────── */
check('clampDim: 0 is the identity, junk falls back to it',
    R.clampDim(0) === 0 && R.clampDim(null) === 0 && R.clampDim('junk') === 0 && R.clampDim('') === 0);
check('clampDim: the ceiling is 0.8', R.clampDim(99) === 0.8 && R.clampDim(-1) === 0);
check('clampHighlight: off by default, 1 at the top',
    R.clampHighlight(null) === 0 && R.clampHighlight(0.5) === 0.5 && R.clampHighlight(99) === 1
    && R.clampHighlight(-2) === 0);

console.log('ramp selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
