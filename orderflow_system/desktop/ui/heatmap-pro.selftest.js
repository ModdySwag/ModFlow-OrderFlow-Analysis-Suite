/* heatmap-pro.selftest.js — the pure half of the map's stepping maths (§120).
 * Run: node desktop/ui/heatmap-pro.selftest.js
 */
'use strict';

const win = {};
global.window = win;
global.document = {
    readyState: 'complete',
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({ setAttribute() {}, style: {}, appendChild() {}, querySelectorAll: () => [] }),
    documentElement: { style: { getPropertyValue: () => '' } },
};
global.getComputedStyle = () => ({ getPropertyValue: () => '' });
require('./heatmap-pro.js');
const HM = win.HEATMAP_PRO;

let ok = 0;
let failed = 0;
function check(cond, label) {
    if (cond) { ok += 1; return; }
    failed += 1;
    console.error('FAIL:', label);
}

check(HM && typeof HM.listStep === 'function', 'the module exported listStep');

const W = [120, 240, 480, 900];
const R = ['120', '200', '300'];

/* the middle of the window ladder steps both ways and lands on the neighbours */
check(HM.listStep(240, 1, W) === '480', 'window up: 240 -> 480');
check(HM.listStep(240, -1, W) === '120', 'window down: 240 -> 120');
check(HM.listStep('240', 1, W) === '480', 'string values step the same as numbers');

/* the ends return null — the caller says so out loud instead of doing nothing */
check(HM.listStep(120, -1, W) === null, 'widest is a stop');
check(HM.listStep(900, 1, W) === null, 'tightest is a stop');
check(HM.listStep(480, 0, W) === null, 'a zero step never moves');

/* an unknown current value behaves like the shipped stepping: fall back to index 1 */
check(HM.listStep(999, 1, W) === '480', 'unknown current: +1 lands at 480');
check(HM.listStep(999, -1, W) === '120', 'unknown current: -1 lands at 120');

/* row lists are plain strings */
check(HM.listStep(200, -1, R) === '120', 'rows down: 200 -> 120');
check(HM.listStep(200, 1, R) === '300', 'rows up: 200 -> 300');
check(HM.listStep(300, 1, R) === null, 'row top is a stop');
check(HM.listStep(120, -1, R) === null, 'row bottom is a stop');
check(HM.listStep(200, 1, []) === null, 'an empty list never moves');

/* §140: the hover readout's own arithmetic — decimals from the instrument's tick, a cell's share
   of the colour scale, and a change as a share of the level it moved from. */
check(HM.dpFor(0.5) === 1, 'a half-tick instrument prints one decimal');
check(HM.dpFor(0.01) === 2, 'a cent tick prints two');
check(HM.dpFor(1) === 0, 'a whole-number tick prints none');
check(HM.dpFor(0.0001) === 4, 'a sub-cent tick prints what it needs');
check(HM.dpFor(null) === 2, 'no tick stated: two decimals, never a guess about scale');
check(HM.dpFor(0.10) === 1, 'a trailing zero is not a decimal place');
check(HM.shareOfScale(21, 42) === 50, 'half the scale cap reads 50%');
check(HM.shareOfScale(63, 42) === 100, 'over the cap reads 100%, never more');
check(HM.shareOfScale(5, 0) === null, 'no cap in the payload: no percentage invented');
check(HM.deltaPct(0.42, 2) === 21, 'a +0.42 add on a 2.0 level is +21%');
check(HM.deltaPct(-1, 2) === -50, 'a pull is signed');
check(HM.deltaPct(0.5, 0) === null, 'nothing there before: no percentage');

const total = ok + failed;
console.log('heatmap-pro selftest: ' + total + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
