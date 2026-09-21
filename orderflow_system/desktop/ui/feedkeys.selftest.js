/* feedkeys.selftest.js — the Feed keys card's decisions, pinned without a browser.
 *
 * Everything between "the server's masked state" and "a request body / a sentence in the row" is
 * pure: the write rule (SEC-09's blank-keeps-stored), the input shapes and their store-matching
 * bounds, the Check routes, the Check sentences, the mask-aware wording, the pill. The DOM half is
 * covered by scripts/audit_ui_refs.py (the module is on its JS_FILES list, so its paths are
 * route-checked and its syntax parsed) and by this file's last two checks, which read the source
 * for the properties that cannot be exercised here: no timers, and a page-lifetime listener set
 * that test_listener_balance.py has frozen.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/feedkeys.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPFEEDKEYS;
}
const F = boot();

check('the module exposes its whole surface', () => {
    for (const fn of ['escape', 'stateWord', 'writeBody', 'checkUrl', 'checkSentence', 'fieldHtml',
                      'rowHtml', 'rowsHtml', 'pillText', 'savedLanes', 'specFor', 'fieldId', 'msgId',
                      'consumeClears',
                      'render', 'load', 'watch', 'state']) {
        assert.strictEqual(typeof F[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(F.fieldId('tradier', 'secret'), 'fk_tradier_secret');
    assert.strictEqual(F.msgId('finnhub'), 'fk_m_finnhub');
});

check('what is stored is said in words, never shown in full', () => {
    assert.strictEqual(F.stateWord({ key_hint: 'PKTE…12 (24 chars)' }), 'saved — PKTE…12 (24 chars)');
    assert.strictEqual(F.stateWord({ has_secret: true }), 'saved — secret stored');
    assert.strictEqual(F.stateWord({}), 'not set');
    assert.strictEqual(F.stateWord(null), 'not set');
});

check('a blank credential field is omitted — the stored key survives', () => {
    const body = F.writeBody('tradier', { key_id: '', secret: '   ', chain_width: '12', sandbox: true }, {});
    assert.deepStrictEqual(body, { chain_width: 12, sandbox: true },
        'blank credentials must not travel: an empty string on the wire clears the key');
});

check('a typed credential replaces, an explicit clear empties, and both travel', () => {
    const typed = F.writeBody('marketdata', { api_key: '  abc123  ' }, {});
    assert.deepStrictEqual(typed, { api_key: 'abc123' });
    const cleared = F.writeBody('marketdata', { api_key: '' }, { api_key: true });
    assert.deepStrictEqual(cleared, { api_key: '' }, 'the × is the only path that clears a key');
});

check('a pending clear is consumed by the write that carried it, and only that one', () => {
    /* §148 / T7-F12: saveFeed used to empty the pending-clear map before the POST answered, so a
       refused or failed write silently dropped the user's × and the next Save wrote the stored
       value back. It now consumes exactly the clears the body carried, once the answer says the
       write landed. */
    assert.deepStrictEqual(F.consumeClears({ api_key: true, secret: true }, { api_key: true }),
        { secret: true }, 'only the clear that travelled is consumed');
    assert.deepStrictEqual(F.consumeClears({ api_key: true }, {}), { api_key: true },
        'a clear that did not travel stays pending');
    assert.deepStrictEqual(F.consumeClears({}, { api_key: true }), {});
    /* The consumption must sit inside the success branch, after the POST — never before it. */
    const save = src.slice(src.indexOf('async function saveFeed'));
    const post = save.indexOf('await api(');
    const consumed = save.indexOf('state.clears[feed] = consumeClears(');
    assert.ok(post > 0, 'saveFeed no longer posts');
    assert.ok(consumed > post,
        'the clears are consumed before the write lands — a failed write would drop them');
    const reset = save.indexOf('state.clears[feed] = {}');
    assert.ok(reset < 0 || reset > post,
        'the pending clears are reset before the write lands — the × would be lost on a failure');
});

check('numeric bounds are the store\'s bounds', () => {
    assert.strictEqual(F.writeBody('tradier', { chain_width: '99' }, {}).chain_width, 20);
    assert.strictEqual(F.writeBody('tradier', { chain_width: '0' }, {}).chain_width, 1);
    assert.strictEqual(F.writeBody('finnhub', { calendar_days: '45' }, {}).calendar_days, 30);
    assert.strictEqual(F.writeBody('finnhub', { calendar_days: 'abc' }, {}).calendar_days, undefined,
        'junk leaves the stored value alone');
    assert.strictEqual(F.specFor('tradier', 'chain_width').max, 20);
    assert.strictEqual(F.specFor('finnhub', 'calendar_days').max, 30);
});

check('the choices offered are the choices the store keeps', () => {
    assert.deepStrictEqual(F.specFor('finnhub', 'calendar_category').options,
        ['all', 'forex', 'crypto', 'indices', 'stocks']);
    assert.deepStrictEqual(F.specFor('finnhub', 'news_category').options,
        ['general', 'federalReserve', 'economic', 'company', 'markets']);
    assert.strictEqual(F.specFor('tradier', 'silent_leaf'), null);
});

check('Check asks the app\'s own routes, one per feed family', () => {
    assert.strictEqual(F.checkUrl('tradier'), '/api/options/volatility/SPY?source=tradier');
    assert.strictEqual(F.checkUrl('marketdata'), '/api/options/volatility/SPY?source=marketdata');
    assert.strictEqual(F.checkUrl('finnhub'), '/api/control/calendar?hours=24&impact=low&source=finnhub');
});

check('Check reports the server\'s sentence — success and refusal alike', () => {
    assert.strictEqual(
        F.checkSentence('tradier', { ok: true, symbol: 'SPY', n_strikes: 36, n_expiries: 5, source: 'tradier' }),
        'check ok — SPY · 36 strikes over 5 expiries · tradier');
    assert.strictEqual(
        F.checkSentence('marketdata', { ok: true, symbol: 'SPY', n_strikes: 4, n_expiries: 1, source: 'marketdata' }),
        'check ok — SPY · 4 strikes over 1 expiry · marketdata');
    assert.strictEqual(
        F.checkSentence('finnhub', { ok: true, upcoming: 3, window_hours: 24, source: 'Finnhub economic calendar (free tier, your key)' }),
        'check ok — 3 events in the next 24 h · Finnhub economic calendar (free tier, your key)');
    assert.strictEqual(
        F.checkSentence('tradier', { ok: false, error: 'no tradier key — add one to Settings ▸ Feed keys (key_id + secret from a Tradier account)' }),
        'check failed — no tradier key — add one to Settings ▸ Feed keys (key_id + secret from a Tradier account)');
    assert.strictEqual(F.checkSentence('finnhub', {}), 'check failed — the route did not answer');
});

check('a row says what a key buys, escapes it, and marks the stored path', () => {
    const row = F.rowHtml({
        id: 'tradier', label: 'Tradier', buys: 'chains — free <account>',
        leaves: ['key_id', 'secret', 'chain_width', 'sandbox'],
        key_hint: 'PKTE…12 (24 chars)', has_secret: true, values: { chain_width: 6, sandbox: false },
    });
    assert.ok(row.indexOf('free &lt;account&gt;') > 0, 'the server\'s sentence is escaped');
    assert.ok(row.indexOf('PKTE…12 (24 chars)') > 0, 'the mask is shown');
    assert.ok(row.indexOf('type="password"') > 0, 'the secret field is a password field');
    assert.ok(row.indexOf('(saved — type to replace)') > 0, 'a stored key says so in its placeholder');
    assert.ok(row.indexOf('data-fk-act="clear"') > 0, 'a stored key can be cleared deliberately');
    assert.ok(row.indexOf('value="6"') > 0, 'a stored number fills its input');
    assert.ok(row.indexOf('data-fk-act="save"') > 0 && row.indexOf('data-fk-act="check"') > 0);
    const empty = F.rowHtml({ id: 'finnhub', label: 'Finnhub', buys: 'x', leaves: ['api_key'], values: {} });
    assert.strictEqual(empty.indexOf('data-fk-act="clear"'), -1, 'nothing stored, nothing to clear');
});

check('the pill counts the feeds that are actually set', () => {
    assert.strictEqual(F.pillText({ feeds: [{ ready: true }, { ready: false }, { ready: true }] }),
        '2 of 3 feeds set');
    assert.strictEqual(F.pillText({ feeds: [{ ready: true }] }), '1 of 1 feed set');
    assert.strictEqual(F.pillText({ feeds: [] }), '0 of 0 feeds set');
});

check('the lanes default to the keyless feeds', () => {
    assert.deepStrictEqual(F.savedLanes(null), { calendar: 'builtin', news: 'feeds' });
    assert.deepStrictEqual(F.savedLanes({ lanes: { calendar: 'finnhub' } }),
        { calendar: 'finnhub', news: 'feeds' });
});

check('a payload that never arrived leaves a row honest', () => {
    assert.doesNotThrow(() => F.render({ feeds: [] }));
    assert.doesNotThrow(() => F.render(null));
    assert.ok(F.rowsHtml(null).indexOf('no optional feeds') > 0);
});

check('the module runs no timers', () => {
    assert.strictEqual(/set(Timeout|Interval)\s*\(/.test(src), false,
        'this card is read on load, on demand, and after each write — a timer would poll a file');
});

console.log('feedkeys selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
