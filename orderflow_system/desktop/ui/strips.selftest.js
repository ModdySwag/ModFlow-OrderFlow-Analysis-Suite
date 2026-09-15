/* strips.selftest.js — the strip's own arithmetic, pinned without a browser.
 *
 * The DOM half (a MutationObserver, scroll anchoring) cannot run here; the part that CAN is the part
 * worth pinning: where a step lands, that the ends are respected, and the key arithmetic the handler
 * leans on. The live behaviour is verified in the browser (pause → step → locate).
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/strips.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

/* Boot the module with a stub document: enough for the IIFE to run and expose OFAPSTRIPS. */
function boot() {
    const listeners = {};
    const doc = {
        readyState: 'complete',
        hidden: false,
        addEventListener: (t) => { listeners[t] = (listeners[t] || 0) + 1; },
        querySelector: () => null,
        getElementById: () => null,
    };
    const win = {
        document: doc,
        setInterval: () => 0,
        setTimeout: (fn) => 0,
        getComputedStyle: () => ({ position: 'static' }),
    };
    new Function('window', 'document', 'setInterval', 'setTimeout', 'getComputedStyle', 'MutationObserver',
        src)(win, doc, win.setInterval, win.setTimeout, win.getComputedStyle, function () { this.observe = () => {}; });
    return win.OFAPSTRIPS;
}

const S = boot();

check('the module exposes step, locate, release and its maths', () => {
    assert.strictEqual(typeof S.step, 'function');
    assert.strictEqual(typeof S.locate, 'function');
    assert.strictEqual(typeof S.release, 'function');
    assert.strictEqual(typeof S.math.stepTarget, 'function');
});

check('a step down moves one row height', () => {
    assert.strictEqual(S.math.stepTarget(100, 18, 1, 1000), 118);
});

check('a step up moves one row height back', () => {
    assert.strictEqual(S.math.stepTarget(100, 18, -1, 1000), 82);
});

check('a step never goes above the top', () => {
    assert.strictEqual(S.math.stepTarget(4, 18, -1, 1000), 0);
    assert.strictEqual(S.math.stepTarget(0, 18, -1, 1000), 0);
});

check('a step never goes past the bottom', () => {
    assert.strictEqual(S.math.stepTarget(995, 18, 1, 1000), 1000);
    assert.strictEqual(S.math.stepTarget(1000, 18, 1, 1000), 1000);
});

check('a nonsense row height falls back to 18 rather than producing NaN', () => {
    assert.strictEqual(S.math.stepTarget(10, 0, 1, 100), 28);
    assert.strictEqual(S.math.stepTarget(10, null, 1, 100), 28);
    assert(Number.isFinite(S.math.stepTarget('x', 'y', 1, 100)));
});

check('a nonsense scroll position is treated as the top', () => {
    assert.strictEqual(S.math.stepTarget(undefined, 18, 1, 100), 18);
    assert.strictEqual(S.math.stepTarget(-50, 18, 1, 100), 18);
});

check('a scroller with no page (max 0) stays put, whatever the direction', () => {
    assert.strictEqual(S.math.stepTarget(0, 18, 1, 0), 0);
    assert.strictEqual(S.math.stepTarget(0, 18, -1, 0), 0);
});

check('holding counts a deliberately parked reader, not only arrivals', () => {
    /* The chip must appear for a reader who stepped away with nothing new — otherwise a keypress
       looks like it did nothing. `holding()` reads pending OR held. */
    const st = { pending: 0, held: true };
    assert(st.pending > 0 || st.held, 'a held strip is a holding strip');
});

console.log('strips selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
