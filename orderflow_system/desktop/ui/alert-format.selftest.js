/* alert-format.selftest.js — the rule-to-words half, pinned without a browser.
 *
 * The module is pure by design (a rule in, words out), so everything it does is checkable here:
 * every kind the engine evaluates has a label and a field spec, a sentence reads like the ones the
 * card shows, the scope says what it means, and a log row's why prefers the detection's own detail.
 * The engine side of the same contract (params named here == params `_passes()` reads) is pinned by
 * orderflow_system/test_alert_format.py, which reads this file's source.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/alert-format.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

/* Boot the IIFE with a window stub — the module writes its surface onto it. */
function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPALERTS;
}

const A = boot();

/* The kinds the engine can evaluate: alerts.KINDS plus wall_age (the depth map's own kind). */
const ENGINE_KINDS = [
    'big_trade', 'block_trade', 'sweep', 'stop_run', 'iceberg', 'speed_spike', 'cvd_divergence',
    'heat_pull', 'heat_stack', 'wall', 'wall_age', 'stacked_imbalance', 'intent_pressure',
    'pulled_size', 'trapped_traders', 'vwap_cross', 'depth_execution', 'depth_refill',
];

check('the module exposes its whole surface', () => {
    for (const fn of ['kindLabel', 'paramSpec', 'sentence', 'scopeWords', 'why', 'kinds']) {
        assert.strictEqual(typeof A[fn], 'function', fn + ' is missing');
    }
});

check('every engine kind carries a label and a field spec', () => {
    for (const kind of ENGINE_KINDS) {
        assert.ok(A.KINDS[kind], 'no catalogue entry for ' + kind);
        assert.ok(A.KINDS[kind].label, kind + ' has no label');
        assert.ok(Array.isArray(A.paramSpec(kind)), kind + ' has no paramSpec');
    }
});

check('a kind the engine does not know still reads as words', () => {
    assert.strictEqual(A.kindLabel('mystery_kind'), 'mystery kind');
    assert.ok(A.sentence({ kind: 'mystery_kind' }).indexOf('mystery kind') === 0);
});

check('the scope fields are part of every kind\u2019s spec', () => {
    for (const kind of ENGINE_KINDS) {
        const keys = A.paramSpec(kind).map((f) => f.key);
        for (const scope of ['at_price', 'at_tol', 'min_age_s']) {
            assert.ok(keys.indexOf(scope) >= 0, kind + ' is missing the ' + scope + ' field');
        }
    }
});

check('every field is renderable: key, label and a say() for a set value', () => {
    for (const kind of ENGINE_KINDS) {
        for (const f of A.paramSpec(kind)) {
            assert.ok(f.key && f.label, kind + ' has a field without a key or label');
            if (f.scope) continue;                        // the scope is spoken by scopeWords
            assert.strictEqual(typeof f.say, 'function', kind + '.' + f.key + ' cannot be said');
            f.say(1);                                     // must not throw
        }
    }
});

check('a rule reads as one sentence naming kind, threshold, scope, channel and cooldown', () => {
    const rule = { id: 'blocks', kind: 'block_trade', params: { min_multiple: 3.0 }, enabled: true,
                   cooldown_s: 10, channels: ['ui', 'telegram'] };
    assert.strictEqual(
        A.sentence(rule),
        'Block trade — a block ≥ 3.00× the venue threshold · any level · UI log + Telegram · 10 s cooldown');
});

check('a rule with no thresholds says so, instead of showing an empty middle', () => {
    const said = A.sentence({ kind: 'big_trade', params: {}, cooldown_s: 0, channels: ['ui'] });
    assert.ok(said.indexOf('a single print above the venue block threshold') > 0, said);
    assert.ok(said.indexOf('no cooldown') > 0, said);
    assert.ok(said.indexOf('UI log only') > 0, said);
});

check('a set that names every option adds nothing to the sentence', () => {
    assert.strictEqual(A.sentence({ kind: 'big_trade', params: { sides: ['buy', 'sell'] }, cooldown_s: 0 }), 'Big trade — a single print above the venue block threshold · any level · UI log only · no cooldown');
    assert.strictEqual(A.sentence({ kind: 'cvd_divergence', params: { kinds: ['bullish', 'bearish'], min_strength: 50 }, cooldown_s: 60 }).indexOf('strength ≥ 50') > 0, true);
    assert.strictEqual(A.sentence({ kind: 'big_trade', params: { sides: ['sell'] }, cooldown_s: 0 }).indexOf('SELL side only') > 0, true);
});

check('another kind\u2019s params are not read into this kind\u2019s sentence', () => {
    const said = A.sentence({ kind: 'sweep', params: { min_levels: 5, min_multiple: 99 }, cooldown_s: 0 });
    assert.ok(said.indexOf('5 levels') > 0, said);
    assert.ok(said.indexOf('99') < 0, 'a foreign param leaked into the words: ' + said);
});

check('the scope says where a rule watches, and how long a level must hold', () => {
    assert.strictEqual(A.scopeWords({ params: {} }), 'any level');
    assert.strictEqual(A.scopeWords({ params: { at_price: 77070.24, at_tol: 3.96 } }), 'at 77070.24 ± 3.96');
    assert.strictEqual(A.scopeWords({ params: { at_price: 100 } }), 'at 100.00 (exact)');
    assert.strictEqual(A.scopeWords({ params: { min_age_s: 120 } }), 'any level · holds ≥ 2.0 min');
    assert.strictEqual(A.scopeWords({ params: { at_price: 0.0456, at_tol: 0.0002 } }), 'at 0.0456 ± 0.0002');
});

check('channels are named, and the log is never left out', () => {
    assert.strictEqual(A.channelWords({ channels: ['ui'] }), 'UI log only');
    assert.strictEqual(A.channelWords({ channels: [] }), 'UI log only');
    assert.strictEqual(A.channelWords({ channels: ['telegram'] }), 'UI log + Telegram');
    assert.strictEqual(A.channelWords({ channels: ['ui', 'telegram', 'webhook'] }), 'UI log + Telegram + Webhook');
});

check('a cooldown reads in seconds under two minutes and minutes above', () => {
    assert.strictEqual(A.cooldownWords({ cooldown_s: 0 }), 'no cooldown');
    assert.strictEqual(A.cooldownWords({ cooldown_s: 30 }), '30 s cooldown');
    assert.strictEqual(A.cooldownWords({ cooldown_s: 300 }), '5.0 min cooldown');
    assert.strictEqual(A.fmtDur(120), '2.0 min');
    assert.strictEqual(A.fmtDur(45), '45 s');
});

check('a size is never rounded into a zero', () => {
    assert.strictEqual(A.fmtSize(0.0456), '0.046');
    assert.strictEqual(A.fmtSize(0.0012), '0.0012');
    assert.strictEqual(A.fmtSize(2.6), '2.60');
    assert.strictEqual(A.fmtSize(1200), '1.20K');
    assert.notStrictEqual(A.fmtSize(0.0012), '0');
});

check('a price keeps the precision its magnitude needs', () => {
    assert.strictEqual(A.fmtPrice(77070.24), '77070.24');
    assert.strictEqual(A.fmtPrice(0.0456), '0.0456');
    assert.strictEqual(A.fmtPrice(0.00012), '0.00012');
});

check('why prefers the detection\u2019s own detail', () => {
    assert.strictEqual(A.why({ kind: 'wall_age', symbol: 'BTCUSDT', message: 'BTCUSDT: rule', data: { detail: 'held 2.4 min' } }), 'held 2.4 min');
    assert.strictEqual(A.why({ kind: 'cvd_divergence', symbol: 'ETHUSDT', message: 'x', data: { note: 'bearish, 3 lower highs' } }), 'bearish, 3 lower highs');
});

check('why drops the symbol the Symbol column already names', () => {
    assert.strictEqual(A.why({ kind: 'big_trade', symbol: 'BTCUSDT', message: 'BTCUSDT: SELL 12.5 @ 77000.0', data: {} }), 'SELL 12.5 @ 77000.0');
    assert.strictEqual(A.why({ kind: 'big_trade', symbol: 'BTCUSDT', message: 'SELL 12.5 @ 77000.0', data: {} }), 'SELL 12.5 @ 77000.0');
});

check('why falls back to the kind when a row carries nothing else', () => {
    assert.strictEqual(A.why({ kind: 'sweep', symbol: 'BTCUSDT', data: {} }), 'Sweep — an aggressive run through the book');
    assert.strictEqual(A.why(null), 'rule');
});

check('the heatmap\u2019s own prefix is recognised, and nothing else is', () => {
    assert.strictEqual(A.isHeatmapRule({ id: 'hm-BTCUSDT-77000-123456' }), true);
    assert.strictEqual(A.isHeatmapRule({ id: 'blocks' }), false);
    assert.strictEqual(A.isHeatmapRule(null), false);
});

check('the select lists the whole catalogue with a note where nothing emits it', () => {
    const list = A.kinds();
    assert.strictEqual(list.length, ENGINE_KINDS.length);
    const wall = list.find((k) => k.kind === 'wall');
    assert.ok(wall && wall.note.indexOf('no live detector') >= 0, 'the wall kind must say it has no emitter');
    assert.strictEqual(list.find((k) => k.kind === 'big_trade').note, '');
});

check('set values survive arrays and comma strings', () => {
    assert.deepStrictEqual(A.setValue(['buy', 'sell']), ['buy', 'sell']);
    assert.deepStrictEqual(A.setValue('buy, sell'), ['buy', 'sell']);
    assert.deepStrictEqual(A.setValue(''), []);
    assert.strictEqual(A.hasValue([]), false);
    assert.strictEqual(A.hasValue(0), true);
});

console.log('alert-format selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
