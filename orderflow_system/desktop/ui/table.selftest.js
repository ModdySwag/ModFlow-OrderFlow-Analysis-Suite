/* table.selftest.js — T15/B5: the one-table component's pure half, as behaviour. */
const assert = require('assert');
require(__dirname + '/table.js');
const T = globalThis.OFAPTABLE;

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

const COLS = [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }, { key: 'c', label: 'C' }];

check('applyOrder honours the saved order and hides what was hidden', () => {
    const out = T.applyOrder(COLS, { order: ['c', 'a', 'b'], hidden: ['b'] });
    assert.deepStrictEqual(out.map((c) => c.key), ['c', 'a']);
    assert.deepStrictEqual(T.applyOrder(COLS, {}).map((c) => c.key), ['a', 'b', 'c'], 'no prefs, natural order');
});

check('sort cycles asc → desc → off', () => {
    let s = T.cycleSort(null, 'a');
    assert.deepStrictEqual(s, { key: 'a', dir: 'asc' });
    s = T.cycleSort(s, 'a');
    assert.deepStrictEqual(s, { key: 'a', dir: 'desc' });
    s = T.cycleSort(s, 'a');
    assert.strictEqual(s, null);
    assert.deepStrictEqual(T.cycleSort({ key: 'a', dir: 'desc' }, 'b'), { key: 'b', dir: 'asc' }, 'a new key starts asc');
});

check('sortRows is numeric where the values are, lexical where they are not', () => {
    const rows = [{ v: '10' }, { v: '2' }, { v: '30' }];
    assert.deepStrictEqual(T.sortRows(rows, { key: 'v', dir: 'asc' }).map((r) => r.v), ['2', '10', '30']);
    assert.deepStrictEqual(T.sortRows(rows, { key: 'v', dir: 'desc' }).map((r) => r.v), ['30', '10', '2']);
    const names = [{ n: 'pear' }, { n: 'apple' }];
    assert.deepStrictEqual(T.sortRows(names, { key: 'n' }).map((r) => r.n), ['apple', 'pear']);
    assert.strictEqual(T.sortRows(rows, null).length, 3);
});

check('groupRows keeps first-seen order and labels blanks', () => {
    const rows = [{ g: 'x', i: 1 }, { g: 'y', i: 2 }, { g: 'x', i: 3 }, { g: null, i: 4 }];
    const groups = T.groupRows(rows, 'g');
    assert.deepStrictEqual(groups.map((g) => g.label), ['x', 'y', '—']);
    assert.deepStrictEqual(groups[0].rows.map((r) => r.i), [1, 3]);
    assert.strictEqual(T.groupRows(rows, '').length, 1, 'no group key, one bucket');
});

check('moveColumn lifts a header and drops it before the target', () => {
    assert.deepStrictEqual(T.moveColumn(['a', 'b', 'c'], 'c', 'a'), ['c', 'a', 'b']);
    assert.deepStrictEqual(T.moveColumn(['a', 'b', 'c'], 'a', 'c'), ['b', 'c', 'a']);
    assert.deepStrictEqual(T.moveColumn(['a', 'b'], 'z', 'a'), ['a', 'b'], 'unknown source is a no-op');
});

console.log('table selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
