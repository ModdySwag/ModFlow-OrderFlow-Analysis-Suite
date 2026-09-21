/* volatility.selftest.js — the Volatility panel's decisions, pinned without a browser.
 *
 * The formatters, the term-structure line, the 25Δ wing sentence and the table's order are pure, so
 * they are pinned here; scripts/audit_ui_refs.py owns the DOM half (every element the module asks
 * for must exist in the shell).
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/volatility.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPVOLATILITY;
}
const V = boot();
const DASH = '\u2014';

check('the module exposes its whole surface', () => {
    for (const fn of ['esc', 'normalize', 'num', 'fmtPrice', 'fmtIv', 'fmtOi', 'fmtSkew', 'sourceLabel',
                      'urlFor', 'expiryLabel', 'expiryShort', 'termText', 'subText', 'ivRangeText',
                      'dteText', 'rowHtml', 'rowsHtml',
                      'bannerFor', 'paint', 'refresh', 'tick', 'wire', 'watch', 'chosenSymbol',
                      'chosenSource', 'activeSymbol', 'state']) {
        assert.strictEqual(typeof V[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(V.VIEW, '.view[data-view="volatility"]');
    assert.strictEqual(V.URL_BASE, '/api/options/volatility/');
    assert.deepStrictEqual(V.SOURCES, ['deribit', 'tradier', 'marketdata']);
});

check('IV and its wing spreads read at one scale', () => {
    assert.strictEqual(V.fmtIv(0.215), '21.50%');
    assert.strictEqual(V.fmtIv(0.012), '1.20%');    /* a quiet market, not 120% */
    assert.strictEqual(V.fmtIv(null), DASH);
    assert.strictEqual(V.fmtSkew(0.03), '+3.00pp');
    assert.strictEqual(V.fmtSkew(-0.052), '-5.20pp');
    assert.strictEqual(V.fmtSkew(null), DASH);
});

check('a stamp a formatter cannot honour gives a label, never a throw', () => {
    /* toISOString() throws a RangeError outside ±8.64e15 ms, and that RangeError would abort the
       paint loop, leaving every field after it blank. */
    assert.strictEqual(V.expiryLabel(1789891200000), '2026-09-20');
    assert.strictEqual(V.expiryLabel(99999999999999999), 'single expiry');
    assert.strictEqual(V.expiryLabel(0), 'single expiry');
    assert.strictEqual(V.expiryLabel(null), 'single expiry');
    assert.strictEqual(V.expiryLabel('nonsense'), 'single expiry');
});

check('an expiry reads as a date, and a missing one says what it means', () => {
    assert.strictEqual(V.expiryLabel(0), 'single expiry');
    assert.strictEqual(V.expiryLabel(null), 'single expiry');
    assert.strictEqual(V.expiryLabel(Date.UTC(2026, 8, 18)), '2026-09-18');
});

check('the term structure line names the front expiries and counts the rest', () => {
    const payload = { term_structure: [
        { expiry_ms: Date.UTC(2026, 8, 18), atm_iv: 0.215, skew_25d: 0.03 },
        { expiry_ms: Date.UTC(2026, 8, 25), atm_iv: 0.231 },
        { expiry_ms: Date.UTC(2026, 9, 2), atm_iv: 0.24 },
        { expiry_ms: Date.UTC(2026, 9, 9), atm_iv: 0.25 },
    ] };
    const text = V.termText(payload);
    assert.ok(text.indexOf('18SEP26 21.50% (+3.00pp)') === 0, 'front expiry leads, in contract form: ' + text);
    assert.ok(text.indexOf('+1 more') > 0, 'the rest are counted, not dropped: ' + text);
    assert.strictEqual(V.termText({ atm_iv: 0.215 }), 'single expiry · ATM 21.50%');
});

check('the wings are shown beside the skew that depends on them', () => {
    const both = V.bannerFor({ ok: true, put_25d_iv: 0.28, call_25d_iv: 0.24 });
    assert.ok(both.text.indexOf('25Δ put 28.00% vs call 24.00%') === 0, both.text);
    assert.strictEqual(both.kind, 'ok');
    const one = V.bannerFor({ ok: true, put_25d_iv: 0.28 });
    assert.ok(one.text.indexOf('not resolvable') > 0, one.text);
});

check('a refusal shows the server\'s own sentence', () => {
    const refusal = V.bannerFor({ ok: false, error: 'Market Data needs an API key' });
    assert.strictEqual(refusal.text, 'Market Data needs an API key');
    assert.strictEqual(refusal.kind, 'warn');
});

check('the table reads down the strikes, marks the money, and escapes what it prints', () => {
    const html = V.rowsHtml({ spot: 80000, smile: [
        { strike: 90000, side: 'put', iv: 0.9, delta: -0.2, oi: 1234.5, expiry_ms: 0 },
        { strike: 70000, side: 'call', iv: 0.4, delta: 0.3, oi: 12, expiry_ms: 0 },
    ] });
    assert.ok(html.indexOf('70000.00') < html.indexOf('90000.00'), 'by strike, ascending');
    assert.ok(html.indexOf('class="atm itm"') > 0, 'the nearest strike is the ATM and here in the money');
    assert.ok(html.indexOf('class="itm"') > 0, 'a put above spot is in the money too');
    assert.ok(html.indexOf('>1,235</td>') > 0, 'open interest reads as a count: ' + html);
    assert.ok(html.indexOf('90.00%') > 0, 'IV in percent');
    assert.ok(V.rowsHtml({}).indexOf('colspan="6"') > 0, 'an empty chain says so');
    assert.strictEqual(html.indexOf('<script'), -1);
});

check('the four new summary fields are pure functions of the payload', () => {
    assert.strictEqual(V.ivRangeText({ iv_min: 0.19, iv_max: 0.56 }), '19.00% – 56.00%');
    assert.strictEqual(V.ivRangeText({ iv_min: 0.19 }), DASH);
    assert.strictEqual(V.dteText({ dte: 0.5 }), '12.0 h');
    assert.strictEqual(V.dteText({ dte: 3.25 }), '3.3 d');
    assert.strictEqual(V.dteText({ dte: 45 }), '45 d');
    assert.strictEqual(V.dteText({}), DASH);
    assert.strictEqual(V.fmtOi(1234567), '1,234,567');
    assert.strictEqual(V.fmtOi(null), DASH);
});

check('an expiry label is the venue contract form, and a broken stamp throws nothing', () => {
    assert.strictEqual(V.expiryShort(1789891200000), '20SEP26');
    assert.strictEqual(V.expiryShort(0), '');
    assert.strictEqual(V.expiryShort(99999999999999999), '');
    assert.strictEqual(V.expiryShort(null), '');
});

check('the request carries symbol and source', () => {
    assert.strictEqual(V.urlFor(' btcusdt '), '/api/options/volatility/BTCUSDT?source=deribit');
    assert.strictEqual(V.urlFor('spy', 'marketdata'), '/api/options/volatility/SPY?source=marketdata');
});

check('a refusal paints without touching a DOM that is not there', () => {
    assert.doesNotThrow(() => V.paint({ ok: false, error: 'no engine' }));
    assert.doesNotThrow(() => V.tick());
    assert.deepStrictEqual(V.state(), { ok: false, error: 'no engine' });
});

console.log('volatility selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
