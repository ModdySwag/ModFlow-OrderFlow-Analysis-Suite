/* colrail.selftest.js — T14/B4: the columns rail's maths, as behaviour. */
const assert = require('assert');
require(__dirname + '/colrail.js');
const CR = globalThis.OFAPCOLRAIL;

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

function snap(buckets, values, traded) {
    return { buckets: buckets, values: values, traded: traded };
}

check('totalOf sums a column of the chosen matrix', () => {
    const d = snap([1, 2], [[10, 1], [20, 2], [30, 3]], [[1, 9], [2, 9], [3, 9]]);
    assert.strictEqual(CR.totalOf(d, 0, 'resting'), 60);
    assert.strictEqual(CR.totalOf(d, 1, 'traded'), 27);
});

check('the first observation seeds the baseline; deltas accumulate after it', () => {
    const cfg = { metric: 'traded', reset: 'manual' };
    let st = CR.reduce({}, snap([1000], [[5]], [[10]]), 0, cfg);
    assert.strictEqual(st['1000'].acc, 0, 'nothing to diff against yet');
    st = CR.reduce(st, snap([1000], [[5]], [[14]]), 1000, cfg);
    assert.strictEqual(st['1000'].acc, 4);
    st = CR.reduce(st, snap([1000], [[5]], [[19]]), 2000, cfg);
    assert.strictEqual(st['1000'].acc, 9, 'deltas keep adding');
});

check('scheduled resets zero on the clock, never between', () => {
    const cfg = { metric: 'traded', reset: 'scheduled', reset_s: 30 };
    let st = CR.reduce({}, snap([1], [[1]], [[10]]), 0, cfg);
    st = CR.reduce(st, snap([1], [[1]], [[15]]), 10000, cfg);
    assert.strictEqual(st['1'].acc, 5);
    st = CR.reduce(st, snap([1], [[1]], [[18]]), 40000, cfg);
    assert.strictEqual(st['1'].acc, 3, 'zeroed at the period, then the delta since');
});

check('conditional resets when the accumulation crosses the threshold', () => {
    const cfg = { metric: 'traded', reset: 'conditional', threshold: 10 };
    let st = CR.reduce({}, snap([1], [[1]], [[0]]), 0, cfg);
    st = CR.reduce(st, snap([1], [[1]], [[12]]), 1000, cfg);
    assert.strictEqual(st['1'].acc, 0, 'crossed 10 → reset');
    st = CR.reduce(st, snap([1], [[1]], [[15]]), 2000, cfg);
    assert.strictEqual(st['1'].acc, 3);
});

check('manual never resets on its own', () => {
    const cfg = { metric: 'resting', reset: 'manual' };
    let st = CR.reduce({}, snap([1], [[4]], [[0]]), 0, cfg);
    st = CR.reduce(st, snap([1], [[9]], [[0]]), 999999, cfg);
    assert.strictEqual(st['1'].acc, 5);
});

check('stale columns leave the map; manual resets only touch what asked', () => {
    let st = CR.reduce({}, snap([1, 2], [[1, 2]], [[3, 4]]), 0, { metric: 'traded' });
    st = CR.reduce(st, snap([2], [[2]], [[4]]), 1, { metric: 'traded' });
    assert.deepStrictEqual(Object.keys(st), ['2'], 'the window drops what it no longer carries');
    let st2 = CR.reduce(st, snap([2], [[2]], [[9]]), 2, { metric: 'traded' });
    assert.strictEqual(st2['2'].acc, 5);
    st2 = CR.resetEntry(st2, '2', 3);
    assert.strictEqual(st2['2'].acc, 0);
    st2 = CR.reduce(st2, snap([2], [[2]], [[11]]), 4, { metric: 'traded' });
    st2 = CR.resetAll(st2, 5);
    assert.strictEqual(st2['2'].acc, 0);
});

console.log('colrail selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
