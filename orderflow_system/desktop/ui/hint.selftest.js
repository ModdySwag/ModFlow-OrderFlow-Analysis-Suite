/* hint.selftest.js — the explain popover's decisions, as behaviour rather than prose. */
const assert = require('assert');
const H = require('./hint.js');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

check('the module exposes the surface the views wire', () => {
    ['parse', 'actionsOf', 'cardHTML', 'skippedNotice', 'attach', 'show', 'hide', 'run', 'boot'].forEach((n) => {
        assert.strictEqual(typeof H[n], 'function', n + ' is a function');
    });
    assert(H.ACTIONS.length === 5, 'the closed action set');
});

check('a spec keeps only known actions, in the order given', () => {
    const spec = H.parse({ title: 'Why?', body: 'because', actions: ['instruments', 'nonsense', 'lookup'] });
    assert.deepStrictEqual(spec.actions, ['instruments', 'lookup']);
    assert.deepStrictEqual(H.actionsOf({ actions: 'lookup,wizard' }).map((a) => a.action), ['lookup', 'wizard']);
});

check('data attributes parse like an object', () => {
    const fake = { dataset: { title: 'Live', body: 'engine is streaming', actions: 'engine' } };
    const spec = H.parse(fake);
    assert.strictEqual(spec.title, 'Live');
    assert.deepStrictEqual(spec.actions, ['engine']);
});

check('an empty spec draws nothing', () => {
    assert.strictEqual(H.cardHTML({}), '');
    assert.strictEqual(H.cardHTML(null), '');
});

check('the card escapes server text (it can carry a broker name or a reason)', () => {
    const html = H.cardHTML({ title: '<b>x</b>', body: 'a "quote" & <script>', actions: ['lookup'] });
    assert(html.indexOf('<b>x</b>') < 0, 'title escaped');
    assert(html.indexOf('<script>') < 0, 'body escaped');
    assert(html.indexOf('&amp;') >= 0 && html.indexOf('&quot;') >= 0, '& and " escaped');
    assert(html.indexOf('data-hint-action="lookup"') >= 0, 'actions rendered');
});

check('several actions render as buttons with their labels', () => {
    const html = H.cardHTML({ title: 't', actions: ['lookup', 'instruments', 'wizard', 'menu', 'engine'] });
    (H.ACTIONS).forEach((a) => {
        assert(html.indexOf(H.ACTION_LABELS[a]) >= 0, a + ' label present');
    });
    assert.strictEqual((html.match(/<button/g) || []).length, 5);
});

check('a skipped engine start becomes one sentence with a count, never an invented one', () => {
    assert.strictEqual(H.skippedNotice({ skipped: [] }), null);
    assert.strictEqual(H.skippedNotice({}), null);
    const one = H.skippedNotice({ skipped: [{ symbol: 'NAS100USDT', reason: 'crypto only' }] });
    assert.strictEqual(one.text, 'NAS100USDT: crypto only');
    assert.strictEqual(one.action, 'lookup');
    const three = H.skippedNotice({ skipped: [
        { symbol: 'A', reason: 'r1' }, { symbol: 'B', reason: 'r2' }, { symbol: 'C', reason: 'r3' }] });
    assert(three.text.indexOf('(+2 more)') >= 0, three.text);
    const junk = H.skippedNotice({ skipped: [{}] });
    assert.strictEqual(junk.text, 'an instrument: skipped');
});

console.log('hint selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
