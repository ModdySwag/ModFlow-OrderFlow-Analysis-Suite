/* engine-progress.selftest.js — the pure half of §132's engine progress bar.
 * Run: node orderflow_system/desktop/ui/engine-progress.selftest.js
 */
'use strict';

const fs = require('fs');
const path = require('path');

let failed = 0;
function check(name, ok) {
    if (ok) { console.log('ok   ' + name); return; }
    failed += 1;
    console.log('FAIL ' + name);
}

/* The module is a browser IIFE that assigns to window; run it against a stub and take the pure half. */
const src = fs.readFileSync(path.join(__dirname, 'engine-progress.js'), 'utf8');
const sandbox = { window: {} };
new Function('window', src)(sandbox.window);
const P = sandbox.window.OFAPENGINEPROGRESS.pure;
check('module exposes its pure half', !!P && typeof P.fill === 'function');
check('and answers to the app\'s own global name', !!sandbox.window.OFAPENGINEPROGRESS);

/* ── phase ────────────────────────────────────────────────────────────────────────────────── */
check('starting is the up direction', P.phase('starting', 'connect') === 'up');
check('stopping is the down direction', P.phase('stopping', 'history') === 'down');
check('running + ready is the warming window', P.phase('running', 'ready') === 'warm');
check('error is a failed start', P.phase('error', 'failed') === 'fail');
check('running + closed shows nothing', P.phase('running', 'closed') === null);
check('stopped shows nothing', P.phase('stopped', 'closed') === null);

/* ── labels ───────────────────────────────────────────────────────────────────────────────── */
check('every start stage has words', ['config', 'instruments', 'build', 'connect', 'ready', 'failed']
    .every((k) => P.label(k) && P.label(k) !== k));
check('every stop stage has words', ['feeds', 'history', 'release', 'closed']
    .every((k) => P.label(k) && P.label(k) !== k));
check('an unknown stage falls back to its own key, never blank', P.label('weird') === 'weird');

/* ── fill: monotone, bounded, never complete inside a stage ───────────────────────────────── */
const plan = ['config', 'instruments', 'build', 'connect'];
const t0 = 1_000_000;
check('first stage starts near zero', P.fill(plan, 'config', t0, t0) < 0.02);
check('and creeps but stays inside its slot', (() => {
    const v = P.fill(plan, 'config', t0, t0 + 60_000);
    return v > 0.15 && v < 1 / plan.length;
})());
check('a later stage starts at its own slot, not above', (() => {
    const v = P.fill(plan, 'connect', t0, t0);
    return Math.abs(v - 3 / 4) < 1e-9;
})());
check('fill never exceeds one', P.fill(plan, 'connect', t0, t0 + 3600_000) <= 1);
check('fill is monotone in elapsed time', (() => {
    let prev = -1;
    for (let ms = 0; ms < 12_000; ms += 250) {
        const v = P.fill(plan, 'build', t0, t0 + ms);
        if (v < prev) return false;
        prev = v;
    }
    return true;
})());
check('an empty plan answers zero, not NaN', P.fill([], 'config', t0, t0) === 0);
check('a stage outside the plan answers zero', P.fill(plan, 'feeds', t0, t0 + 1000) === 0);

/* ── caption ──────────────────────────────────────────────────────────────────────────────── */
check('under a second the caption is words only', P.caption('connect', 400) === 'connecting the feed');
check('from one second it counts seconds', P.caption('connect', 4200) === 'connecting the feed · 4 s');
check('the seconds are whole (no twitch)', P.caption('history', 1999).indexOf('.') < 0);

/* ── settle: 'live' only after a real print ───────────────────────────────────────────────── */
check('running with ticks is live', P.settle('running', 3) === 'live');
check('running without ticks is honest about it',
    P.settle('running', 0) === 'connected — no ticks yet');
check('stopped says stopped', P.settle('stopped', 0) === 'stopped');
check('a failed start says so', P.settle('error', 0) === 'start failed');
check('the ticks grace is bounded', P.TICKS_GRACE_MS > 0 && P.TICKS_GRACE_MS <= 15000);

console.log(failed ? '\n' + failed + ' FAILED' : '\nall engine-progress checks passed');
process.exit(failed ? 1 : 0);
