/* scopes.selftest.js — T12/B9: the per-instrument scoping maths, as behaviour.
 *
 * The DOM half needs a browser; the half that decides WHAT is remembered and WHAT is applied is
 * pure, and that half is where the honesty rules live (known paths only; undefined never stored).
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/scopes.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

const win = {};
new Function('window', 'document', src)(win, undefined);
const S2 = win.OFAPSCOPES;

check('the module is exposed without a document', () => {
    assert(S2 && Array.isArray(S2.SCOPED) && S2.SCOPED.length === 16, 'sixteen scoped dials (B5 added the dim/highlight pair per surface)');
    assert(typeof S2.capture === 'function' && typeof S2.planApply === 'function');
    assert(typeof S2.applyFor === 'function' && typeof S2.forget === 'function');
});

check('planApply keeps only known paths, in the scoped order', () => {
    const rows = S2.planApply({ evil: 1, 'atlas.heatmap.floor': 0, 'ofx.ramp': 'thermal' });
    assert.deepStrictEqual(rows.map((r) => r.path), ['ofx.ramp', 'atlas.heatmap.floor']);
    assert.strictEqual(rows[0].value, 'thermal');
    assert.deepStrictEqual(S2.planApply(null), []);
});

check('capture reads nested values and skips the missing', () => {
    const cfg = { ofx: { heat_contrast: 1.2 }, atlas: { heatmap: { smooth: 'none' } } };
    const snap = S2.capture(cfg, ['ofx.heat_contrast', 'ofx.heat_floor', 'atlas.heatmap.smooth']);
    assert.deepStrictEqual(snap, { 'ofx.heat_contrast': 1.2, 'atlas.heatmap.smooth': 'none' });
});

check('cleanSymbol accepts the shapes instruments use, and nothing else', () => {
    assert.strictEqual(S2.cleanSymbol('btcusdt'), 'BTCUSDT');
    assert.strictEqual(S2.cleanSymbol(' BTC/USD '), 'BTC/USD');
    assert.strictEqual(S2.cleanSymbol(''), '');
    assert.strictEqual(S2.cleanSymbol('bad sym'), '');
    assert.strictEqual(S2.cleanSymbol('A'.repeat(25)), '');
});

check('the module reports its state without a document', () => {
    const st = S2.state();
    assert(st && typeof st.last === 'string');
    assert.strictEqual(st.symbol, '');
});

console.log('scopes selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
