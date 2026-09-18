const assert = require('assert');
const T = require('./ticks.js');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.error('FAIL', name, e.message); } }

function fakeEl() {
    const cls = new Set();
    return { dataset: {}, textContent: '', offsetWidth: 1,
             classList: { remove: (a, b) => { cls.delete(a); cls.delete(b); },
                          add: (c) => cls.add(c), has: (c) => cls.has(c), _all: () => [...cls] } };
}

check('direction of a move', () => {
    assert.strictEqual(T.dir(100, 101), 'up');
    assert.strictEqual(T.dir('', 5), '');
    assert.strictEqual(T.dir('\u2014', 5), '');
    assert.strictEqual(T.dir('1.147', '1.146'), 'down');
    assert.strictEqual(T.dir(5, 5), '');
    assert.strictEqual(T.dir('\u2014', 5), '');
});
check('first reading never flashes', () => {
    const el = fakeEl();
    assert.strictEqual(T.tick(el, '100', { arrow: true }), '');
    assert.strictEqual(el.classList.has('tick-up'), false);
    assert.strictEqual(el.textContent, '\u00b7 100');
});
check('a rise tints up and flashes', () => {
    const el = fakeEl();
    T.tick(el, '100', { arrow: true }); T.tick(el, '101', { arrow: true });
    assert.strictEqual(el.classList.has('tick-up'), true);
    assert.ok(el.textContent.indexOf('\u2197') === 0, el.textContent);
});
check('a fall tints down', () => {
    const el = fakeEl();
    T.tick(el, '100', { arrow: true }); T.tick(el, '99', { arrow: true });
    assert.strictEqual(el.classList.has('tick-down'), true);
});
check('direction flips clean both ways', () => {
    const el = fakeEl();
    T.tick(el, '100'); T.tick(el, '101'); T.tick(el, '100');
    assert.strictEqual(el.classList.has('tick-down'), true);
    assert.strictEqual(el.classList.has('tick-up'), false);
});
check('arrow: false keeps the text clean', () => {
    const el = fakeEl();
    T.tick(el, '5', { arrow: false }); T.tick(el, '6', { arrow: false });
    assert.strictEqual(el.textContent, '6');
    assert.strictEqual(el.classList.has('tick-up'), true);
});
check('equal readings do not re-flash or rewrite', () => {
    const el = fakeEl();
    T.tick(el, '42', { arrow: true }); T.tick(el, '42', { arrow: true });
    assert.strictEqual(el.textContent, '\u00b7 42');
    assert.strictEqual(el.classList.has('tick-up') || el.classList.has('tick-down'), false);
});
check('arrival marks a fresh card', () => {
    const el = fakeEl();
    T.arrival(el);
    assert.strictEqual(el.classList.has('tick-in'), true);
});
check('missing element never throws', () => { T.tick(null, '1'); T.arrival(null); });

console.log('ticks selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
