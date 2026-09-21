/* gex.selftest.js — the GEX panel's decisions, pinned without a browser.
 *
 * Everything the panel does between "an HTTP payload" and "words in a cell" is pure (formatters, the
 * wall/greek honesty rules, the table's order, the banner's choice of the server's own sentence), so
 * all of it is checkable here. The DOM half (wire/watch/paint against real nodes) is covered by
 * scripts/audit_ui_refs.py, which fails when a module asks for an element the shell does not have.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/gex.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPGEX;
}
const G = boot();
const DASH = '\u2014';

check('the module exposes its whole surface', () => {
    for (const fn of ['esc', 'normalize', 'num', 'fmtBig', 'fmtPrice', 'fmtIv', 'fmtCount',
                      'sourceLabel', 'urlFor', 'wallText', 'carriedText', 'subText', 'rowHtml',
                      'rowsHtml', 'bannerFor', 'paint', 'refresh', 'tick', 'wire', 'watch',
                      'chosenSymbol', 'chosenSource', 'activeSymbol', 'state']) {
        assert.strictEqual(typeof G[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(G.VIEW, '.view[data-view="gex"]');
    assert.strictEqual(G.URL_BASE, '/api/options/gex/');
    assert.strictEqual(G.DASH, DASH);
});

check('symbols and numbers are normalized before they are used', () => {
    assert.strictEqual(G.normalize(' btcusdt '), 'BTCUSDT');
    assert.strictEqual(G.normalize(null), '');
    assert.strictEqual(G.num('3.5'), 3.5);
    assert.strictEqual(G.num(''), null);
    assert.strictEqual(G.num(null), null);
    assert.strictEqual(G.num('abc'), null);
    assert.strictEqual(G.num(Infinity), null);
});

check('exposures read at one scale across nine orders of magnitude', () => {
    assert.strictEqual(G.fmtBig(1.5e9), '1.50B');
    assert.strictEqual(G.fmtBig(-2.5e6), '-2.50M');
    assert.strictEqual(G.fmtBig(1500), '1.50K');
    assert.strictEqual(G.fmtBig(3.5), '3.50');
    assert.strictEqual(G.fmtBig(0.0000004), '0.000000');
    assert.strictEqual(G.fmtBig(null), DASH);
});

check('IV is a fraction on the wire and prints as a percentage', () => {
    assert.strictEqual(G.fmtIv(0.215), '21.50%');
    assert.strictEqual(G.fmtIv(0.012), '1.20%');   /* the old <=1.5 heuristic printed this as 120% */
    assert.strictEqual(G.fmtIv(1.2), '120.00%');   /* and this one as 1.20% */
    assert.strictEqual(G.fmtIv(null), DASH);
});

check('the γ column and the ΓEX column hold their precision', () => {
    assert.strictEqual(G.fmtGamma(0.00043), '4.30e-4');   /* a plain 0.000 would read as no gamma */
    assert.strictEqual(G.fmtGamma(0.0121), '0.012');
    assert.strictEqual(G.fmtGamma(0.5), '0.500');
    assert.strictEqual(G.fmtGamma(null), DASH);
    assert.strictEqual(G.fmtGammaExp(0.1581), '0.158100');
    assert.strictEqual(G.fmtGammaExp(0.00004), '4.00e-5');  /* fmtBig's 0.000000 would read as zero */
    assert.strictEqual(G.fmtGammaExp(2.5e6), '2.50M');
    assert.strictEqual(G.fmtGammaExp(-1500), '-1.50K');
});

check('a strike keeps its venue precision, a count stays a count', () => {
    assert.strictEqual(G.fmtPrice(76500), '76500.00');
    assert.strictEqual(G.fmtPrice(0.5, 8), '0.50000000');
    assert.strictEqual(G.fmtPrice(null), DASH);
    assert.strictEqual(G.fmtCount(1234.5678), '1234.57');
    assert.strictEqual(G.fmtCount(null), DASH);
});

check('the request carries the symbol and the source', () => {
    assert.strictEqual(G.urlFor(' btcusdt '), '/api/options/gex/BTCUSDT?source=deribit');
    assert.strictEqual(G.urlFor('spy', 'tradier'), '/api/options/gex/SPY?source=tradier');
    assert.strictEqual(G.sourceLabel('marketdata'), 'Market Data');
});

check('a wall reads as its price, plus how far it sits from spot', () => {
    const text = G.wallText([{ strike: 80000 }], 81615.05);
    assert.ok(text.indexOf('80000.00') === 0, 'the price leads: ' + text);
    assert.ok(text.indexOf('(-1.98%)') > 0, 'the gap is signed and relative: ' + text);
    assert.strictEqual(G.wallText([], 100), DASH);
    assert.strictEqual(G.wallText(null, 100), DASH);
});

check('a greek the venue never sent reads "not published", never a zero', () => {
    assert.strictEqual(G.carriedText({ carried: { vanna: false } }, 'vanna', 0), 'not published');
    assert.strictEqual(G.carriedText({ carried: { vanna: true } }, 'vanna', 1234567), '1.23M');
    assert.strictEqual(G.carriedText({}, 'vanna', 0), '0.000000');
});

check('the table widens the biggest exposure and escapes the venue\'s own text', () => {
    const payload = {
        ok: true,
        per_strike: [
            { strike: 70000, side: '<b>call</b>', iv: 0.5, gamma: 0.0001, gamma_exp: 2e5, oi: 10 },
            { strike: 80000, side: 'put', iv: 0.6, gamma: 0.0002, gamma_exp: 9e6, oi: 20 },
        ],
    };
    const html = G.rowsHtml(payload);
    assert.ok(html.indexOf('&lt;b&gt;call&lt;/b&gt;') > 0, 'the side is escaped');
    assert.strictEqual(html.indexOf('<b>'), -1, 'no raw markup reaches the DOM');
    assert.ok(html.indexOf('80000.00') < html.indexOf('70000.00'), 'wide exposure first');
    assert.ok(G.rowsHtml({}).indexOf('colspan="7"') > 0, 'an empty chain says so');
});

check('the banner prefers the server\'s own refusal to a generic one', () => {
    const refusal = G.bannerFor({ ok: false, error: 'Tradier chains carry no gammas' });
    assert.strictEqual(refusal.text, 'Tradier chains carry no gammas');
    assert.strictEqual(refusal.kind, 'warn');
    const good = G.bannerFor({ ok: true, note: 'chain read', n_strikes: 36 });
    assert.strictEqual(good.text, 'chain read');
    assert.strictEqual(good.kind, 'ok');
});

check('a refusal paints without touching a DOM that is not there', () => {
    assert.doesNotThrow(() => G.paint({ ok: false, error: 'no engine' }));
    assert.doesNotThrow(() => G.tick());
    assert.deepStrictEqual(G.state(), { ok: false, error: 'no engine' });
});

console.log('gex selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
