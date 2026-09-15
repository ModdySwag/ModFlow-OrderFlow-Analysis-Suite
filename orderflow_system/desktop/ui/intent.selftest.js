/* intent.selftest.js - the arbiter's rules, as behaviour rather than prose. */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/intent.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* Run the module against a stub document/window so the logic is exercised, not just parsed. */
function boot() {
    const listeners = {};
    const doc = {
        addEventListener: (ev, fn) => { (listeners[ev] = listeners[ev] || []).push(fn); },
        dispatchEvent: () => true,
        getElementById: () => null,
        querySelector: () => null,
        createElement: () => ({ style: {}, classList: { toggle: () => {} }, appendChild: () => {} }),
        body: { appendChild: () => {} },
    };
    const win = {};
    const sandbox = { window: win, document: doc, CustomEvent: function (n, o) { this.type = n; this.detail = (o || {}).detail; },
                      setTimeout: (f, ms) => setTimeout(f, ms), clearTimeout: clearTimeout, setInterval: () => 0,
                      Date: Date, Object: Object, Math: Math, console: console };
    const fn = new Function('window', 'document', 'CustomEvent', 'setTimeout', 'clearTimeout', 'setInterval', 'Date', 'console',
        src.replace('window.OFAPINTENT', 'window.OFAPINTENT'));
    fn(sandbox.window, sandbox.document, sandbox.CustomEvent, sandbox.setTimeout, sandbox.clearTimeout, sandbox.setInterval, sandbox.Date, console);
    return { api: win.OFAPINTENT, listeners: listeners };
}

const t = boot();
check('the arbiter is exposed', () => assert(t.api && typeof t.api.lease === 'function'));
check('a free surface runs immediately', () => {
    let ran = false;
    const deferred = t.api.defer('ofx', () => { ran = true; });
    assert.strictEqual(deferred, false); assert.strictEqual(ran, true);
});
check('a leased surface defers, then applies on release', () => {
    let ran = false;
    t.api.lease('ofx', 5000);
    const deferred = t.api.defer('ofx', () => { ran = true; });
    assert.strictEqual(deferred, true); assert.strictEqual(ran, false, 'must not run during the lease');
    t.api.release('ofx');
    assert.strictEqual(ran, true, 'must run the moment the lease ends');
});
check('keyed deferrals collapse to the last one only', () => {
    let count = 0;
    t.api.lease('heatmap', 5000);
    t.api.deferKeyed('heatmap', 'pull', () => { count += 1; });
    t.api.deferKeyed('heatmap', 'pull', () => { count += 1; });
    t.api.deferKeyed('heatmap', 'pull', () => { count += 1; });
    t.api.release('heatmap');
    assert.strictEqual(count, 1, 'three polls, one apply');
});
check('writes wait for the gesture and collapse by key', () => {
    const sent = [];
    t.api.lease('ofx', 5000);
    t.api.queueWrite('ofx.params', () => sent.push('first'));
    t.api.queueWrite('ofx.params', () => sent.push('second'));
    assert.strictEqual(sent.length, 0, 'nothing may be sent mid-gesture');
    t.api.release('ofx');
    assert.deepStrictEqual(sent, ['second'], 'last value wins');
});
check('the view freeze holds every surface, and release never touches the feed', () => {
    t.api.freezeView(true);
    assert.strictEqual(t.api.held('anything'), true);
    let ran = false;
    t.api.defer('cvd', () => { ran = true; });
    assert.strictEqual(ran, false);
    t.api.freezeView(false);
    assert.strictEqual(ran, true, 'held updates apply when the view is released');
    const st = t.api.status();
    assert.strictEqual(st.frozen, false);
    assert.strictEqual(st.feed.live, true, 'the feed is never stopped by this layer');
});
check('input events lease the surface under the pointer', () => {
    const down = t.listeners['pointerdown'] || [];
    assert(down.length, 'the module must listen for pointer input');
    const target = { getAttribute: (n) => (n === 'data-surface' ? 'ofx' : null), parentElement: null };
    down[0]({ target: target });
    assert.strictEqual(t.api.held('ofx'), true);
    t.api.release('ofx');
    assert.strictEqual(t.api.held('ofx'), false);
});

console.log('intent selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
