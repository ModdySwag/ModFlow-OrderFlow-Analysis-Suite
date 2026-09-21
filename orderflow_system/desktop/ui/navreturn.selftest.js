/* navreturn.selftest.js — the pure half of the back-chip's state machine.
 * Run: node desktop/ui/navreturn.selftest.js
 */
'use strict';

const win = {};
global.window = win;
global.document = { readyState: 'complete', createElement: () => ({}), querySelector: () => null, addEventListener: () => {}, documentElement: { style: {} } };
require('./navreturn.js');
const NAV = win.OFAPNAV;

let ok = 0;
let failed = 0;
function check(cond, label) {
    if (cond) { ok += 1; return; }
    failed += 1;
    console.error('FAIL:', label);
}

/* ── jump records the origin ─────────────────────────────────────────────────────────────── */
check(NAV._decide(null, { kind: 'jump', from: 'ofx', to: 'instruments', backLabel: 'Engine' }).back === 'ofx',
    'a jump remembers where it started');
check(NAV._decide(null, { kind: 'jump', from: 'ofx', to: 'instruments', backLabel: 'Engine' }).to === 'instruments',
    'the jump points at its destination');
check(NAV._decide(null, { kind: 'jump', from: 'heatmap', to: 'heatmap' }) === null,
    'a jump to the same view records nothing');

/* ── every route into help records; leaving help by navigation clears ────────────────────── */
const h = NAV._decide(null, { kind: 'navigate', from: 'engine', to: 'help', backLabel: 'Engine' });
check(h && h.back === 'engine' && h.to === 'help', 'opening help from a view records the view');
check(NAV._decide(h, { kind: 'navigate', from: 'help', to: 'help' }) === h,
    'help re-entry from help keeps the slot');
check(NAV._decide(h, { kind: 'navigate', from: 'help', to: 'depth', backLabel: 'Help' }) === null,
    'navigation away clears the slot');
check(NAV._decide(null, { kind: 'navigate', from: 'help', to: 'help' }) === null,
    'help boot from help records nothing');

/* ── ordinary navigation never invents a chip ────────────────────────────────────────────── */
check(NAV._decide(null, { kind: 'navigate', from: 'overview', to: 'chart', backLabel: 'Overview' }) === null,
    'a plain view switch records nothing');
check(NAV._decide({ back: 'a', to: 'b' }, { kind: 'navigate', from: 'b', to: 'b' }) &&
    NAV._decide({ back: 'a', to: 'b' }, { kind: 'navigate', from: 'b', to: 'b' }).back === 'a',
    'the same-view repaint keeps the slot');

/* ── back consumes the slot; the return call cannot re-record ────────────────────────────── */
check(NAV._decide({ back: 'ofx', to: 'instruments' }, { kind: 'back' }) === null, 'back clears the slot');
check(NAV._decide(null, { kind: 'navigate', from: 'instruments', to: 'ofx', backLabel: 'Instruments' }) === null,
    'the return click lands as plain navigation (no ping-pong)');

/* ── a second jump no longer offers the round trip back ──────────────────────────────────── */
const j1 = NAV._decide(null, { kind: 'jump', from: 'ofx', to: 'instruments', backLabel: 'Engine' });
const j2 = NAV._decide(j1, { kind: 'jump', from: 'instruments', to: 'replay', backLabel: 'Instruments' });
check(j2.back === 'instruments' && j2.to === 'replay', 'one slot: the newest jump wins');

const total = ok + failed;
console.log('navreturn selftest: ' + total + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
