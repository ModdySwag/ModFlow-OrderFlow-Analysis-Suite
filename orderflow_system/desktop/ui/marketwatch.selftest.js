const assert = require('assert');
const M = require('./marketwatch.js');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.error('FAIL', name, e.message); } }

check('fx five decimals: 1.14776', () => assert.strictEqual(M.priceText(1.14776), '1.14776'));
check('sub-one five decimals: 0.57326', () => assert.strictEqual(M.priceText(0.57326), '0.57326'));
check('three-range trims trailing zero: 550.09', () => assert.strictEqual(M.priceText(550.09), '550.09'));
check('three-range keeps thirds: 155.944', () => assert.strictEqual(M.priceText(155.944), '155.944'));
check('large two decimals: 29440.7', () => assert.strictEqual(M.priceText(29440.7), '29440.70'));
check('zero / missing price: em dash', () => assert.strictEqual(M.priceText(0), '\u2014'));
check('positive slant up', () => assert.strictEqual(M.arrow(0.12), '\u2197'));
check('negative slant down', () => assert.strictEqual(M.arrow(-0.23), '\u2198'));
check('flat stays neutral', () => { assert.strictEqual(M.arrow(0), '\u00b7'); assert.strictEqual(M.sideClass(0), ''); });
check('pct text', () => { assert.strictEqual(M.pctText(0.12), '0.12%'); assert.strictEqual(M.pctText(-0.26), '-0.26%'); });
check('unquoted row shows em dashes', () => {
    const r = M.rowModel({ symbol: 'NQZ25', bid: 0, ask: 0, change_pct: 0, quoted: false });
    assert.strictEqual(r.bid, '\u2014'); assert.strictEqual(r.ask, '\u2014');
});
check('rows map a payload', () => {
    const out = M.rows({ rows: [{ symbol: 'EURUSD', bid: 1.14763, ask: 1.14764, change_pct: -0.58, quoted: true }] });
    assert.strictEqual(out.length, 1); assert.strictEqual(out[0].cls, 'down');
});
check('missing payload is empty, never a throw', () => assert.deepStrictEqual(M.rows(null), []));
check('tick up tints', () => assert.strictEqual(M.bidDir(1.1, 1.2), 'up'));
check('tick down tints', () => assert.strictEqual(M.bidDir(1.2, 1.1), 'down'));
check('no move, no tint', () => assert.strictEqual(M.bidDir('1.14763', '1.14763'), ''));
check('unquoted never tints', () => { assert.strictEqual(M.bidDir('\u2014', '1.2'), ''); assert.strictEqual(M.bidDir(0, 5), ''); });
check('formatted strings compare numerically', () => assert.strictEqual(M.bidDir('0.71132', '0.71134'), 'up'));

console.log('marketwatch selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
