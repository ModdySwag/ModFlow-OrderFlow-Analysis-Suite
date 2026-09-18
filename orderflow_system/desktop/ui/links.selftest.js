/* links.selftest.js — the link groups' decision, as behaviour rather than prose.
 *
 * The DOM half needs a browser; the half that decides WHO MOVES is pure, and it is the half the
 * phase-3 gate is about ("changing a group moves every member; non-members unaffected").
 */
const assert = require('assert');
const fs = require('fs');
const shellSrc = fs.readFileSync(__dirname + '/shell.js', 'utf8');
const linksSrc = fs.readFileSync(__dirname + '/links.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* No document: both modules must load and expose their logic (a Node run, a headless probe). */
function boot(members) {
    const win = {};
    new Function('window', 'document', shellSrc)(win, undefined);
    new Function('window', 'document', linksSrc)(win, undefined);
    win.OFAPSHELL.linkMembers = () => (members || []).slice();
    return { links: win.OFAPLINKS, shell: win.OFAPSHELL };
}

const MEMBERS = [
    { view: 'ofx', sym: 'A', tf: '', link: 'A/' },
    { view: 'tape', sym: 'A', tf: '', link: 'A/' },
    { view: 'depth', sym: 'A', tf: '', link: 'A/' },
    { view: 'chart', sym: 'B', tf: 'A', link: 'B/A' },
    { view: 'logs', sym: '', tf: '', link: '' },
    { view: 'heatmap', sym: 'A', tf: 'B', link: 'A/B' },
];
const t = boot(MEMBERS);

check('the links module is exposed without a document', () => {
    assert(t.links && typeof t.links.plan === 'function', 'plan');
    assert(typeof t.links.setGroup === 'function' && typeof t.links.sweep === 'function', 'group API');
    assert(t.links.GROUPS.join('') === 'ABCD', 'four groups');
});

check('a symbol change reaches every member of that group only', () => {
    const rows = t.links.plan('sym', 'A', 'ETHUSDT', MEMBERS);
    const views = rows.map((r) => r.view).sort();
    assert.deepStrictEqual(views, ['depth', 'heatmap', 'ofx', 'tape'], 'members of A: ' + views.join(','));
    assert(rows.every((r) => r.value === 'ETHUSDT'));
    assert(!rows.some((r) => r.view === 'chart'), 'a B member must not move');
    assert(!rows.some((r) => r.view === 'logs'), 'a panel that never joined must not move');
});

check('the Engine view takes its own symbol select', () => {
    const row = t.links.plan('sym', 'A', 'ETHUSDT', MEMBERS).find((r) => r.view === 'ofx');
    assert.strictEqual(row.control, 'ofxSymbol');
});

check('panels on the app-wide instrument share one change, not one each', () => {
    const rows = t.links.plan('sym', 'A', 'ETHUSDT', MEMBERS);
    assert.strictEqual(rows.length, 4, 'four members of group A');
    const controls = t.links.controlsOf(rows).map((r) => r.control).sort();
    assert.deepStrictEqual(controls, ['ofxSymbol', 'symbolSelect'],
        'three of those members follow #symbolSelect, and it is one control');
    /* the order the rows arrive in decides which member owns the shared change, not how many run */
    assert.strictEqual(t.links.controlsOf(rows.concat(rows)).length, 2, 'a doubled plan still touches two controls');
});

check('a timeframe change only moves panels that have a timeframe control', () => {
    const rows = t.links.plan('tf', 'A', '300', MEMBERS);
    assert.deepStrictEqual(rows.map((r) => r.view), ['chart']);
    assert.strictEqual(rows[0].control, 'tfSelect');
    /* heatmap is linked to timeframe group B, and nobody but the chart can take a timeframe at all */
    assert.deepStrictEqual(t.links.plan('tf', 'B', '300', MEMBERS), []);
});

check('an unknown group or an empty value moves nothing', () => {
    assert.deepStrictEqual(t.links.plan('sym', 'Z', 'X', MEMBERS), []);
    assert.deepStrictEqual(t.links.plan('sym', '', 'X', MEMBERS), []);
});

check('setGroup records the value and reports the group back', () => {
    assert.strictEqual(t.links.setGroup('sym', 'A', 'SOLUSDT'), true);
    const g = t.links.groups();
    assert.strictEqual(g.A.symbol, 'SOLUSDT');
    /* membership is either half: chart joined A on its timeframe, so it IS one of A's members */
    assert.deepStrictEqual(g.A.members.sort(), ['chart', 'depth', 'heatmap', 'ofx', 'tape']);
    assert.strictEqual(g.B.symbol, '', 'B was never set');
    assert.strictEqual(t.links.setGroup('sym', 'Z', 'x'), false, 'only A-D exist');
});

check('the link string is parsed and formatted by one rule, shared with the store', () => {
    const M = t.shell.math;
    assert.deepStrictEqual(M.parseLink('A/B'), { sym: 'A', tf: 'B' });
    assert.deepStrictEqual(M.parseLink('a'), { sym: 'A', tf: '' });
    assert.deepStrictEqual(M.parseLink('/b'), { sym: '', tf: 'B' });
    assert.deepStrictEqual(M.parseLink(''), { sym: '', tf: '' });
    assert.deepStrictEqual(M.parseLink('/'), { sym: '', tf: '' }, 'slashes alone are not a link');
    assert.deepStrictEqual(M.parseLink('E/zzz'), { sym: '', tf: '' }, 'outside A-D is not a link');
    assert.strictEqual(M.formatLink({ sym: 'A', tf: 'B' }), 'A/B');
    assert.strictEqual(M.formatLink({ sym: 'a', tf: '' }), 'A/', 'the shape the store accepts, verbatim');
    assert.strictEqual(M.formatLink({ sym: '', tf: 'c' }), '/C');
    assert.strictEqual(M.formatLink({ sym: '', tf: '' }), '', 'join nothing, store nothing');
    assert.strictEqual(M.formatLink({ sym: 'E', tf: 'x' }), '');
    /* round trip through both readers */
    ['A/B', 'A/', '/B'].forEach((text) => assert.strictEqual(M.formatLink(M.parseLink(text)), text));
});

check('timeframe values are shown the way the chart labels them', () => {
    assert.strictEqual(t.links.tfLabel('60'), '1m');
    assert.strictEqual(t.links.tfLabel(3600), '1H');
    assert.strictEqual(t.links.tfLabel(''), '');
    assert.strictEqual(t.links.tfLabel('7'), '7', 'an unknown value shows itself, never a guess');
});

check('a sweep with no members is not a crash', () => {
    const empty = boot([]);
    assert.deepStrictEqual(empty.links.sweep('test'), []);
    assert.strictEqual(empty.links.members().length, 0);
    const st = empty.links.state();
    assert.strictEqual(st.applying, false);
    assert(st.groups && st.groups.A && st.groups.A.members.length === 0);
});

check('colour: every group has a distinct fallback and the cycle wraps', () => {
    const F = t.links.FALLBACK_COLORS;
    assert.deepStrictEqual(Object.keys(F), ['A', 'B', 'C', 'D']);
    assert.strictEqual(new Set(Object.values(F)).size, 4, 'four distinct colours');
    assert.notStrictEqual(t.links.nextColor(F.A).toLowerCase(), String(F.A).toLowerCase(),
        'the cycle steps off the current colour');
    assert.strictEqual(t.links.nextColor('#c3a6ff'), '#6ec1ff', 'and wraps');
    assert.strictEqual(new Set(t.links.COLOR_CYCLE).size, t.links.COLOR_CYCLE.length, 'cycle colours are distinct');
});

check('colour: colorOf falls back without config, and rejects unknown groups', () => {
    assert.strictEqual(t.links.colorOf('A'), t.links.FALLBACK_COLORS.A);
    assert.strictEqual(t.links.colorOf('z'), '', 'no group, no colour');
});

console.log('links selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
