/* Self-test for the palette operator parser (plan T36).
 *
 *     node orderflow_system/desktop/ui/search-ops.selftest.js
 *
 * Runs in Node with no browser and no build step; exits non-zero on the first
 * failure so it can gate a release. The plan asks for exactly these cases, plus the
 * malformed-input rule: a broken operator must fall back to free text, never blank
 * the palette.
 */
const { searchOpsParse, searchOpsFilterRows, searchOpsSummary, soRange, soNumber, soSizeRange } = require('./search-ops.js');

let failures = 0;
function check(name, actual, expected) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a === e) {
        console.log(`  ok    ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL  ${name}\n        expected ${e}\n        got      ${a}`);
    }
}
function ok(name, condition, detail) {
    if (condition) { console.log(`  ok    ${name}`); return; }
    failures += 1;
    console.log(`  FAIL  ${name}${detail ? '\n        ' + detail : ''}`);
}

console.log('search-ops self-test');

// ── the plan's four cases ───────────────────────────────────────────────
const options = searchOpsParse('type:option underlying:AAPL strike:>200 exp:max');
check('type:option → type', options.ops.type, 'option');
check('underlying:AAPL', options.ops.underlying, 'AAPL');
check('strike:>200 → min', options.ops.strike.min, 200);
check('strike:>200 → no max', options.ops.strike.max, null);
check('exp:max → pick', options.exp.pick, 'max');
check('nothing left as free text', options.text, '');
ok('marked active', options.active === true);
ok('no errors', options.errors.length === 0, JSON.stringify(options.errors));

const malformed = searchOpsParse('type:banana strike:abc exp:nonsense vol:??');
check('malformed keeps free text', malformed.text, 'type:banana strike:abc exp:nonsense vol:??');
ok('malformed reports each problem', malformed.errors.length === 4, JSON.stringify(malformed.errors));
ok('malformed sets no filters', !malformed.ops.type && !malformed.ops.strike && !malformed.ops.vol);

const plain = searchOpsParse('AAPL');
check('plain text survives', plain.text, 'AAPL');
ok('plain text is not an operator', plain.active === false);

const opsAndText = searchOpsParse('earnings type:stock');
check('operators and free text mix', opsAndText.text, 'earnings');
check('type filter kept', opsAndText.ops.type, 'stock');

// ── ranges ──────────────────────────────────────────────────────────────
check('<150 → max only', soRange('<150'), { min: null, max: 150, open: false });
check('190-210 → both', soRange('190-210'), { min: 190, max: 210 });
check('>=250 → open min', soRange('>=250'), { min: 250, max: null, open: true });
check('exact 200 → min=max', soRange('200'), { min: 200, max: 200 });
check('nonsense range → null', soRange('abc'), null);

// ── sizes ───────────────────────────────────────────────────────────────
check('vol:>1M', soNumber('1M'), 1000000);
check('vol:250k', soNumber('250k'), 250000);
check('vol:1.5b', soNumber('1.5b'), 1500000000);
check('vol:plain', soNumber('1200'), 1200);
check('vol:junk', soNumber('big'), null);

// the plan's own example, end to end: vol:>1M must parse (not just soNumber)
const volOp = searchOpsParse('vol:>1M');
check('vol:>1M → min', volOp.ops.vol.min, 1000000);
check('vol:>1M → no max', volOp.ops.vol.max, null);
ok('vol:>1M reports no error', volOp.errors.length === 0, JSON.stringify(volOp.errors));
check('vol:<250k → max', searchOpsParse('vol:<250k').ops.vol.max, 250000);
check('vol:1M-5M → both', searchOpsParse('vol:1M-5M').ops.vol, { min: 1000000, max: 5000000 });
ok('vol:junk still errors', searchOpsParse('vol:??').errors.length === 1);
check('soSizeRange narrow form', JSON.stringify(typeof soSizeRange === 'function' ? soSizeRange('>2M') : null), JSON.stringify({ min: 2000000, max: null, open: false }));

// ── sort + misc operators ───────────────────────────────────────────────
check('sort:last', searchOpsParse('sort:last').ops.sort, 'last');
check('sort:junk → error', searchOpsParse('sort:junk').errors.length, 1);
check('exchange filter', searchOpsParse('exchange:nasdaq').ops.exchange, 'NASDAQ');
check('exp date', searchOpsParse('exp:2026-01-16').exp.min, '2026-01-16');
check('exp:min', searchOpsParse('exp:min').exp.pick, 'min');
check('empty input', searchOpsParse(''), { text: '', symbols: [], ops: {}, errors: [], active: false, exp: { min: null, max: null, any: false } });
check('whitespace only', searchOpsParse('   ').text, '');
check('null-safe', searchOpsParse(null).text, '');

// ── multi-symbol paste ──────────────────────────────────────────────────
check('comma paste', searchOpsParse('AAPL, MSFT, NVDA').symbols, ['AAPL', 'MSFT', 'NVDA']);
check('space paste', searchOpsParse('aapl msft').symbols, ['AAPL', 'MSFT']);
ok('operators disable the paste shortcut', !searchOpsParse('AAPL, type:stock').symbols.length);

// ── client-side filtering ───────────────────────────────────────────────
const rows = [
    { symbol: 'AAPL', volume: 900000, exchange: 'NASDAQ' },
    { symbol: 'SPY', volume: 2000000, exchange: 'ARCA' },
    { symbol: 'TSLA', volume: null, exchange: 'NASDAQ' },
];
check('vol:>1M keeps one', searchOpsFilterRows(rows, { vol: { min: 1000000, max: null } }).map((r) => r.symbol), ['SPY']);
check('vol:<1M drops missing volume', searchOpsFilterRows(rows, { vol: { min: null, max: 1000000 } }).map((r) => r.symbol), ['AAPL']);
check('exchange filter', searchOpsFilterRows(rows, { exchange: 'NASDAQ' }).map((r) => r.symbol), ['AAPL', 'TSLA']);
check('no filters → unchanged', searchOpsFilterRows(rows, {}).length, 3);

// ── summary line ────────────────────────────────────────────────────────
ok('summary names the filters', searchOpsSummary(options).includes('type option'));
ok('summary includes the strike bound', searchOpsSummary(options).includes('strike') && searchOpsSummary(options).includes('200'));
ok('summary of a plain query is empty', searchOpsSummary(plain) === '');

console.log(failures ? `\nFAILED — ${failures} check(s)` : '\nall checks passed');
process.exit(failures ? 1 : 0);
