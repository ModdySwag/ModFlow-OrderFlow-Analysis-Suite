/* risk.selftest.js — T13/B11: the consequence maths, as behaviour.
 *
 * Signs, size weighting, the honest distance when flat, and the refusals: a price with nothing to
 * value it against must produce no text at all rather than a made-up number.
 */
const assert = require('assert');
require(__dirname + '/risk.js');
const R = globalThis.OFAPRISK;

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

const LONG = { tick: 0.5, position: { side: 'long', size: 2, entry_price: 100 }, last: 101 };
const SHORT = { tick: 0.5, position: { side: 'short', size: 3, entry_price: 100 }, last: 99 };
const FLAT = { tick: 0.5, position: { side: 'flat', size: 0, entry_price: 0 }, last: 100 };

check('long: a higher price is a paper profit, size-weighted', () => {
    const v = R.verdict(101, LONG);
    assert.strictEqual(v.kind, 'pl');
    assert.strictEqual(v.perUnit, 2, 'one dollar over a 0.5 tick is two ticks');
    assert.strictEqual(v.total, 4, 'two ticks a unit at size 2');
    assert(R.text(101, LONG).indexOf('+2.0 ticks/unit') >= 0, R.text(101, LONG));
});

check('long: a lower price is a paper loss, with the sign intact', () => {
    assert.strictEqual(R.verdict(99, LONG).total, -4);
});

check('short: the sign flips with the side', () => {
    assert.strictEqual(R.verdict(99, SHORT).perUnit, 2);
    assert.strictEqual(R.verdict(101, SHORT).perUnit, -2);
    assert.strictEqual(R.verdict(99, SHORT).total, 6);
});

check('flat: a distance from the mark, and the text says so', () => {
    const v = R.verdict(102, FLAT);
    assert.strictEqual(v.kind, 'distance');
    assert.strictEqual(v.ticks, 4);
    assert(R.text(102, FLAT).indexOf('no position') >= 0);
});

check('nothing to value against: no text at all', () => {
    assert.strictEqual(R.text(101, null), '', 'no context');
    assert.strictEqual(R.verdict(101, null).has, false);
    assert.strictEqual(R.text('junk', LONG), '');
    assert.strictEqual(R.verdict(NaN, LONG).has, false);
    assert.strictEqual(R.text(101, { tick: 0.5, position: { side: 'flat', size: 0, entry_price: 0 }, last: 0 }), '',
        'a flat account with no mark has no distance to report');
});

check('the formatter rounds to one decimal and keeps the sign', () => {
    assert.strictEqual(R.fmt(2.04), '+2.0');
    assert.strictEqual(R.fmt(-0.06), '-0.1');
    assert.strictEqual(R.fmt(0), '0.0');
});

console.log('risk selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
