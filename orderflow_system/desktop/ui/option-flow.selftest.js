/* option-flow.selftest.js — the Option flow panel's decisions, pinned without a browser.
 *
 * The clock labels, the premium arithmetic, the classification order and the summary sentences are
 * pure, so they are pinned here; scripts/audit_ui_refs.py owns the DOM half.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/option-flow.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPOPTIONFLOW;
}
const F = boot();
const DASH = '\u2014';

check('the module exposes its whole surface', () => {
    for (const fn of ['esc', 'normalize', 'num', 'fmtNum', 'timeLabel', 'windowLabel',
                      'sourceLabel', 'urlFor', 'premium', 'premiumText', 'signedPremiumText', 'fmtStrike',
                      'tapeRows', 'premiumSplit', 'largestPrint', 'largestText', 'biggestSweep',
                      'rowHtml', 'rowsHtml', 'subText', 'bannerFor', 'paint', 'refresh', 'tick',
                      'wire', 'watch', 'chosenSymbol', 'chosenSource', 'activeSymbol', 'state']) {
        assert.strictEqual(typeof F[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(F.VIEW, '.view[data-view="option-flow"]');
    assert.strictEqual(F.URL_BASE, '/api/options/flow/');
    assert.strictEqual(F.WINDOW_MS, 900000);
    assert.strictEqual(F.COUNT, 100);
});

check('a print is stamped with a clock time, a window with its length', () => {
    assert.strictEqual(F.timeLabel(0), DASH);
    assert.strictEqual(F.timeLabel(null), DASH);
    assert.match(F.timeLabel(1758300000000), /^\d\d:\d\d:\d\d$/);
    assert.strictEqual(F.windowLabel(900000), 'last 15 min');
    assert.strictEqual(F.windowLabel(7200000), 'last 2 h');
    assert.strictEqual(F.windowLabel(0), DASH);
});

check('premium is the venue\'s own size times its own price', () => {
    assert.strictEqual(F.premium({ size: 10, price: 0.05 }), 0.5);
    assert.strictEqual(F.premium({ size: 10 }), null);
    assert.strictEqual(F.premium(null), null);
});

check('premium prints in money when the wire names the underlying, and in coin when it does not', () => {
    assert.strictEqual(F.premiumText(0.06, { spot: 81000, premium_unit: 'USD' }), '$4.9K');
    assert.strictEqual(F.premiumText(1.5, { spot: 81000, premium_unit: 'USD' }), '$121.5K');
    assert.strictEqual(F.premiumText(0.06, { premium_unit: 'btc' }), '0.060 BTC');
    assert.strictEqual(F.premiumText(null, { spot: 81000 }), DASH);
    /* A guess is not a quote: no spot, no dollar sign — the coin figure stands on its own. */
    assert.strictEqual(F.premiumText(0.5, { spot: null, premium_unit: 'btc' }), '0.500 BTC');
    assert.strictEqual(F.signedPremiumText(-1.2, { spot: 81000 }), '\u2212$97.2K');
    assert.strictEqual(F.signedPremiumText(1.2, { spot: 81000 }), '+$97.2K');
});

check('the tape is the table: every print, newest first, each carrying its class', () => {
    const payload = { spot: 81000, premium_unit: 'USD', tape: [
        { timestamp_ms: 2000, class: 'block', side: 'call', strike: 80000, size: 5, price: 0.1,
          premium: 0.5, expiry: '20SEP26', aggressor: 'buy' },
        { timestamp_ms: 3000, class: 'routine', side: 'put', strike: 90000, size: 2, price: 0.2,
          premium: 0.4, expiry: '20SEP26', aggressor: null },
    ] };
    const rows = F.tapeRows(payload);
    assert.strictEqual(rows.length, 2);
    assert.strictEqual(rows[0].timestamp_ms, 3000, 'newest first');
    const html = F.rowsHtml(payload);
    assert.ok(html.indexOf('class="chip routine"') > 0, 'the class is a cell of its own');
    assert.ok(html.indexOf('class="chip block"') > 0, 'a block is tagged as one');
    assert.ok(html.indexOf('$32.4K') > 0, 'premium in money: 0.4 × 81,000');
    assert.ok(html.indexOf('class="put"') > 0, 'the side colours the Type cell');
    assert.ok(Math.abs(html.indexOf('class="chip routine"') - html.indexOf('20SEP26')) < 200);
});

check('call and put premium split, and the net between them', () => {
    const payload = { spot: 81000, premium_unit: 'USD', tape: [
        { side: 'call', premium: 1.0 },
        { side: 'put', premium: 0.25 },
        { side: 'call', premium: 0.5 },
    ] };
    const split = F.premiumSplit(payload);
    assert.strictEqual(split.call, 1.5);
    assert.strictEqual(split.put, 0.25);
    assert.strictEqual(split.net, 1.25);
});

check('the largest print is the biggest one by premium, and reads as a line', () => {
    const payload = { spot: 81000, premium_unit: 'USD', tape: [
        { strike: 80000, side: 'call', size: 5, premium: 0.1 },
        { strike: 84000, side: 'put', size: 111, premium: 1.2 },
    ] };
    assert.strictEqual(F.largestPrint(payload).strike, 84000);
    assert.strictEqual(F.largestText(payload), '84,000P ×111 · $97.2K');
    assert.strictEqual(F.largestText({ tape: [] }), DASH);
});

check('the sub-line names both counts, so neither looks like the wrong one', () => {
    const both = F.subText({ symbol: 'BTCUSDT', source: 'deribit', window_ms: 900000,
                             prints_read: 100, total_trades: 91 });
    assert.ok(both.indexOf('100 prints read') > 0, both);
    assert.ok(both.indexOf('91 in the window') > 0, both);
    /* Same number twice is one fact, not two: it prints once. */
    const same = F.subText({ symbol: 'BTCUSDT', source: 'deribit', window_ms: 900000,
                             prints_read: 91, total_trades: 91 });
    assert.ok(same.indexOf('in the window') < 0, same);
});

check('a strike reads as a strike, a size as a size', () => {
    assert.strictEqual(F.fmtStrike(82000), '82,000');
    assert.strictEqual(F.fmtStrike(612.5), '612.5');
    assert.strictEqual(F.fmtStrike(null), DASH);
    /* The magnitude shorthand must never reach a strike column: 82,000 is not 82.00K. */
    assert.strictEqual(F.rowsHtml({ tape: [{ strike: 82000, side: 'call', size: 1, price: 0.01,
                                             premium: 0.01, timestamp_ms: 1 }] }).indexOf('82.00K'), -1);
});

check('an empty window says which kind of empty it is', () => {
    assert.ok(F.rowsHtml({ prints_read: 0 }).indexOf('no option prints') > 0);
    assert.ok(F.rowsHtml({ prints_read: 12 }).indexOf('none inside this window') > 0);
    assert.ok(F.rowsHtml({ prints_read: 12 }).indexOf('12 prints read') > 0);
    assert.ok(F.rowsHtml({}).indexOf('colspan="9"') > 0);
});

check('the biggest sweep is the one the summary names', () => {
    const payload = { sweeps: [
        { sweep_id: 'a', total_premium: 1e4 },
        { sweep_id: 'b', total_premium: 9e5 },
        { sweep_id: 'c', total_premium: 3e4 },
    ] };
    assert.strictEqual(F.biggestSweep(payload).sweep_id, 'b');
    assert.strictEqual(F.biggestSweep({ sweeps: [] }), null);
    assert.strictEqual(F.biggestSweep(null), null);
});

check('a quiet window is not dressed up as a signal', () => {
    const quiet = F.bannerFor({ ok: true, total_trades: 9, n_sweeps: 0, n_blocks: 0, n_unusual: 0,
                                window_ms: 900000 });
    assert.strictEqual(quiet.kind, 'info');
    assert.ok(quiet.text.indexOf('a quiet window: 9 trade(s)') === 0, quiet.text);
    const busy = F.bannerFor({ ok: true, total_trades: 40, n_sweeps: 2, n_blocks: 1, n_unusual: 3,
                               window_ms: 900000 });
    assert.strictEqual(busy.kind, 'ok');
    assert.ok(busy.text.indexOf('2 sweep(s) · 1 block(s) · 3 unusual-premium print(s) in last 15 min') === 0, busy.text);
});

check('a refusal shows the server\'s own sentence', () => {
    const refusal = F.bannerFor({ ok: false, error: 'option flow needs a print tape; Tradier sends quotes' });
    assert.strictEqual(refusal.text, 'option flow needs a print tape; Tradier sends quotes');
    assert.strictEqual(refusal.kind, 'warn');
});

check('the request carries the symbol, the source and the window', () => {
    const url = F.urlFor(' btcusdt ', 'deribit');
    assert.strictEqual(url, '/api/options/flow/BTCUSDT?source=deribit&count=100&window_ms=900000');
    assert.strictEqual(F.sourceLabel('deribit'), 'Deribit');
});

check('a refusal paints without touching a DOM that is not there', () => {
    assert.doesNotThrow(() => F.paint({ ok: false, error: 'no tape' }));
    assert.doesNotThrow(() => F.tick());
    assert.deepStrictEqual(F.state(), { ok: false, error: 'no tape' });
});

console.log('option-flow selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
