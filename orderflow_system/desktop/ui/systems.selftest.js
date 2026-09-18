/* systems.selftest.js — the Systems board's model, pinned under Node (§86). */
const assert = require('assert');
const S = require('./systems.js');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

const report = {
    rows: [
        { id: 'engine', name: 'Engine', state: 'live', detail: 'streaming 5 instruments', view: 'ofx' },
        { id: 'source', name: 'Feed \u2014 Bybit', state: 'ready', detail: 'selected', view: 'settings' },
        { id: 'ninjatrader', name: 'NinjaTrader 8 (bridge)', state: 'off', detail: 'no bridge', view: 'instruments' },
        { id: 'database', name: 'History database', state: 'error', detail: 'locked', view: 'logs' },
    ],
    optional: [{ id: 'bookmap', name: 'Bookmap bridge', state: 'off', detail: 'not installed', optional: true }],
};

check('the module exposes the surface the card wires', () => {
    ['tiles', 'score', 'summary'].forEach((n) => assert.strictEqual(typeof S[n], 'function', n));
    assert(S.STATES.live && S.STATES.ready && S.STATES.off && S.STATES.error, 'the closed state set');
});

check('tiles keep rows first and mark the optional ones', () => {
    const t = S.tiles(report);
    assert.deepStrictEqual(t.map((x) => x.id), ['engine', 'source', 'ninjatrader', 'database', 'bookmap']);
    assert.strictEqual(t[4].optional, true);
    assert.strictEqual(t[0].optional, false);
    assert.strictEqual(t[2].kind, 'no');
    assert.strictEqual(t[3].kind, 'err');
});

check('an unknown state paints as off, never as live', () => {
    const t = S.tiles({ rows: [{ id: 'x', name: 'X', state: 'wat' }] });
    assert.strictEqual(t[0].state, 'off');
});

check('the score counts the systems in play, not the optional capabilities', () => {
    const s = S.score(report);
    assert.strictEqual(s.total, 4);
    assert.strictEqual(s.live, 1);
    assert.strictEqual(s.percent, 25);
    const m = S.summary(report);
    assert(m.line.indexOf('1 of 4') === 0, 'the summary line: ' + m.line);
    assert.strictEqual(m.attention, 2);   // ninjatrader (off) + database (error); ready is not attention
});

check('an empty or broken payload scores zero and stays wordless-safe', () => {
    assert.deepStrictEqual(S.score(null), { live: 0, total: 0, percent: 0 });
    assert.deepStrictEqual(S.tiles(null), []);
    const t = S.tiles({ rows: [{}] });
    assert.strictEqual(t[0].name, 'system');
});

console.log('systems selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
