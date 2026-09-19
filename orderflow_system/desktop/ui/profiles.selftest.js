/* profiles.selftest.js — the auto-switch rule maths, as behaviour rather than prose.
 *
 * The DOM half of profiles.js needs a browser; this half does not, and it is the half that
 * decides when a playbook fires: source bindings beat clock windows, day masks filter, windows
 * that cross midnight wrap, and the half-open [from, to) boundary is exact. Pin it here so a
 * "pr[o]file did not switch" report can start from arithmetic instead of guesswork.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/profiles.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* No document: the module must load and expose its maths anyway (a Node run, a headless probe). */
function boot() {
    const win = {};
    new Function('window', 'document', src)(win, undefined);
    return win.OFAPPROFILES;
}

const P = boot();

/* September 20 2026 is a Sunday (getDay() === 0): offset 0 = Sun … offset 6 = Sat. */
const at = (offset, h, m) => new Date(2026, 8, 20 + offset, h, m);

check('the module exposes its rule maths without a document', () => {
    assert(P && typeof P.matchRule === 'function', 'matchRule');
    assert(typeof P.spent === 'function' && typeof P.when === 'function', 'formatters');
});

check('no rules, or rules switched off, never fire', () => {
    assert.strictEqual(P.matchRule(null, 'bybit', at(1, 10, 0)), '');
    assert.strictEqual(P.matchRule({ enabled: false, sources: { bybit: 'pfa' } }, 'bybit', at(1, 10, 0)), '');
    assert.strictEqual(P.matchRule({ enabled: true }, 'bybit', at(1, 10, 0)), '', 'no rules = no switch');
});

check('a feed binding beats a clock window', () => {
    const rules = {
        enabled: true,
        sources: { bybit: 'pfa' },
        windows: [{ from: '00:00', to: '23:59', days: [], profile: 'pfb' }],
    };
    assert.strictEqual(P.matchRule(rules, 'bybit', at(1, 10, 0)), 'pfa');
    assert.strictEqual(P.matchRule(rules, 'BYBIT', at(1, 10, 0)), 'pfa', 'the feed name is case-blind');
    assert.strictEqual(P.matchRule(rules, 'mt5', at(1, 10, 0)), 'pfb', 'other feeds still follow the clock');
});

check('the day mask filters (Thursday rule does not fire on Wednesday)', () => {
    const rules = { enabled: true, windows: [{ from: '00:00', to: '23:59', days: [4], profile: 'pfthu' }] };
    assert.strictEqual(P.matchRule(rules, '', at(4, 9, 0)), 'pfthu');
    assert.strictEqual(P.matchRule(rules, '', at(3, 9, 0)), '', 'Wednesday is not Thursday');
    const every = { enabled: true, windows: [{ from: '00:00', to: '23:59', days: [], profile: 'pfany' }] };
    assert.strictEqual(P.matchRule(every, '', at(3, 9, 0)), 'pfany', 'no days = every day');
});

check('a window that crosses midnight wraps', () => {
    const rules = { enabled: true, windows: [{ from: '22:00', to: '06:00', days: [], profile: 'pfnight' }] };
    assert.strictEqual(P.matchRule(rules, '', at(1, 23, 30)), 'pfnight');
    assert.strictEqual(P.matchRule(rules, '', at(1, 5, 30)), 'pfnight');
    assert.strictEqual(P.matchRule(rules, '', at(1, 12, 0)), '');
    assert.strictEqual(P.matchRule(rules, '', at(1, 6, 0)), '', 'to is exclusive');
});

check('the [from, to) boundary is exact', () => {
    const rules = { enabled: true, windows: [{ from: '09:00', to: '17:00', days: [], profile: 'pfday' }] };
    assert.strictEqual(P.matchRule(rules, '', at(1, 8, 59)), '');
    assert.strictEqual(P.matchRule(rules, '', at(1, 9, 0)), 'pfday');
    assert.strictEqual(P.matchRule(rules, '', at(1, 16, 59)), 'pfday');
    assert.strictEqual(P.matchRule(rules, '', at(1, 17, 0)), '');
});

check('the formatters keep their bounds', () => {
    assert.strictEqual(P.spent(0), 'less than a minute');
    assert.strictEqual(P.spent(90000), '2 min');
    assert.strictEqual(P.spent(7200000), '2.0 h');
    assert.strictEqual(P.when(0), 'never');
});

if (failed) { console.log(failed + ' failed, ' + ok + ' passed'); process.exit(1); }
console.log('profiles.selftest: ' + ok + ' passed');
