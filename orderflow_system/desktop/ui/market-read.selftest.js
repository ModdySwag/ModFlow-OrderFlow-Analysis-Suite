/* market-read.selftest.js — the Market read panel's decisions, pinned without a browser.
 *
 * The read's own words (the regime sentence, the score cells, the "not measured" line, the level
 * table's order) are pure formatters over the server's payload, so they are pinned here;
 * scripts/audit_ui_refs.py owns the DOM half.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/market-read.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPMARKETREAD;
}
const M = boot();
const DASH = '\u2014';

check('the module exposes its whole surface', () => {
    for (const fn of ['esc', 'normalize', 'num', 'fmtPrice', 'fmtScore', 'yesNo', 'regimeText',
                      'urlFor', 'rowHtml', 'rowsHtml', 'levelCount', 'inputsText', 'summaryText',
                      'bannerFor', 'paint', 'refresh', 'tick', 'wire', 'watch', 'activeSymbol',
                      'state']) {
        assert.strictEqual(typeof M[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(M.VIEW, '.view[data-view="market-read"]');
    assert.strictEqual(M.URL_BASE, '/api/atlas/market-read/');
    assert.strictEqual(M.REFRESH_MS, 5000);
});

check('the read is requested for one instrument, and it must be named', () => {
    assert.strictEqual(M.urlFor(' btcusdt '), '/api/atlas/market-read/BTCUSDT');
    assert.strictEqual(M.normalize('spy'), 'SPY');
    assert.strictEqual(M.normalize(null), '');
});

check('scores print on the engine\'s own 0..100 scale, and null is not zero', () => {
    assert.strictEqual(M.fmtScore(63.456), '63.5');
    assert.strictEqual(M.fmtScore(0), '0.0');
    assert.strictEqual(M.fmtScore(null), DASH);
    assert.strictEqual(M.fmtScore(undefined), DASH);
});

check('the regime is the engine\'s own name, never prettified into another', () => {
    assert.strictEqual(M.regimeText({ regime: { name: 'buyer_control' } }), 'buyer control');
    assert.strictEqual(M.regimeText({ regime: { name: 'buyer_control', absorbing: true,
                                                absorbing_side: 'sell' } }), 'buyer control (sell side)');
    assert.strictEqual(M.regimeText({ regime: {} }), DASH);
    assert.strictEqual(M.yesNo(true), 'yes');
    assert.strictEqual(M.yesNo(false), 'no');
});

check('the level count carries the confluence count when there is one', () => {
    assert.strictEqual(M.levelCount({ n_levels: 12, n_confluence: 3 }), '12 level(s) · 3 confluence');
    assert.strictEqual(M.levelCount({ n_levels: 4 }), '4 level(s)');
    assert.strictEqual(M.levelCount({}), '0 levels');
});

check('the read names the signals it could not measure', () => {
    const payload = { inputs: { tape: { measured: true }, profile: { measured: true },
                                footprint: { measured: false, note: 'not wired to the hub' } } };
    assert.strictEqual(M.inputsText(payload), 'not measured: footprint');
    assert.strictEqual(M.inputsText({ inputs: { tape: { measured: true } } }), 'every signal measured');
    assert.strictEqual(M.inputsText({}), 'every signal measured');
});

check('the summary carries the read\'s own sentences, and the server\'s refusal verbatim', () => {
    assert.strictEqual(M.summaryText({ summary: 'Two-sided auction.', note: 'Tape warm.' }),
                       'Two-sided auction. Tape warm.');
    assert.strictEqual(M.summaryText({}), DASH);
    const refusal = M.bannerFor({ ok: false, error: 'no engine is running' });
    assert.strictEqual(refusal.text, 'no engine is running');
    assert.strictEqual(refusal.kind, 'warn');
});

check('a read without the footprint input says so on the banner, not in a footnote', () => {
    const payload = {
        ok: true,
        regime: { name: 'buyer_control', description: 'Buyers in control at the session high.' },
        inputs: { tape: { measured: true }, footprint: { measured: false } },
    };
    const banner = M.bannerFor(payload);
    assert.strictEqual(banner.kind, 'info');
    assert.ok(banner.text.indexOf('Buyers in control') === 0, banner.text);
    assert.ok(banner.text.indexOf('not measured: footprint') > 0, banner.text);
});

check('the level table prints levels as they arrive, escaped', () => {
    const payload = { levels: [
        { price: 81200, kind: 'wall_ask', source: 'depth', strength: 0.82 },
        { price: 80500.5, kind: '<b>poc</b>', source: 'profile', strength: 1 },
    ] };
    const html = M.rowsHtml(payload);
    assert.strictEqual(html.indexOf('<b>poc</b>'), -1, 'no raw markup reaches the DOM');
    assert.ok(html.indexOf('wall ask') > 0, 'a kind reads as words');
    assert.ok(html.indexOf('81200.00') > 0);
    assert.ok(M.rowsHtml({}).indexOf('colspan="4"') > 0, 'an empty read says so');
});

check('a refusal paints without touching a DOM that is not there', () => {
    assert.doesNotThrow(() => M.paint({ ok: false, error: 'no engine' }));
    assert.doesNotThrow(() => M.tick());
    assert.deepStrictEqual(M.state(), { ok: false, error: 'no engine' });
});

console.log('market-read selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
