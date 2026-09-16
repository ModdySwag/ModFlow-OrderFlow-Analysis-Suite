/* windows-ui.selftest.js — the widget-window menu's decisions, as behaviour rather than prose.
 *
 * The menu's DOM half needs a browser; this half does not, and it is the half that decides what a
 * user is offered: no controls where windows cannot exist, a row per monitor, a disabled row at the
 * cap, and never a row that would ask for something impossible.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/windows-ui.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* No document: the module must load and expose its model anyway (a Node run, a headless probe). */
function boot() {
    const win = {};
    new Function('window', 'document', src)(win, undefined);
    return win.OFAPWINDOWS;
}

const W = boot();
const MON1 = { index: 0, label: 'Monitor 1 · 2560x1440' };
const MON2 = { index: 1, label: 'Monitor 2 · 1920x1080 · 150%' };
const native = (over) => Object.assign({ native: true, screens: [MON1, MON2], open: [], windows: [], max: 8 }, over || {});

check('the module exposes its model without a document', () => {
    assert.strictEqual(typeof W.model, 'function');
});

check('a browser is offered nothing at all', () => {
    assert.deepStrictEqual(W.model({ native: false, screens: [MON1] }, 'ofx'), []);
    assert.deepStrictEqual(W.model(null, 'ofx'), []);
    assert.deepStrictEqual(W.model({}, 'ofx'), []);
});

check('with nothing open, the menu offers one new window and one row per monitor', () => {
    const rows = W.model(native(), 'ofx');
    const kinds = rows.map((r) => r.kind);
    assert.deepStrictEqual(kinds, ['open_new', 'head', 'screen', 'screen']);
    assert.strictEqual(rows[0].view, 'ofx');
    assert.strictEqual(rows[0].disabled, false);
    assert.deepStrictEqual(rows.filter((r) => r.kind === 'screen').map((r) => r.screen), [0, 1]);
    assert.strictEqual(rows[3].label, 'Monitor 2 · 1920x1080 · 150%');
});

check('no focus means an instruction, never a guess', () => {
    const rows = W.model(native(), '');
    assert.deepStrictEqual(rows.map((r) => r.kind), ['note']);
    assert.ok(/focus/i.test(rows[0].label));
});

check('open windows are listed with their widget and their pin state', () => {
    const rows = W.model(native({
        open: ['w1', 'w2'],
        windows: [{ id: 'w1', view: 'ofx', on_top: true }, { id: 'w2', view: 'tape' }],
    }), 'ofx');
    const opens = rows.filter((r) => r.kind === 'open');
    assert.deepStrictEqual(opens.map((r) => r.id), ['w1', 'w2']);
    assert.strictEqual(opens[0].on_top, true);
    assert.strictEqual(opens[1].on_top, false);
    assert.ok(/OFX/.test(opens[0].label) && /TAPE/.test(opens[1].label));
    assert.strictEqual(rows[0].kind, 'head');
    assert.ok(/2 windows open/.test(rows[0].label));
    assert.ok(rows.some((r) => r.kind === 'close_all'));
});

check('an open window with no stored record is still listed (the host is the truth)', () => {
    const rows = W.model(native({ open: ['wghost'] }), 'ofx');
    const ghost = rows.filter((r) => r.kind === 'open')[0];
    assert.strictEqual(ghost.id, 'wghost');
    assert.strictEqual(ghost.view, '');
});

check('at the cap the new-window rows are disabled and say why', () => {
    const open = ['w1', 'w2'];
    const rows = W.model(native({ open: open, windows: [{ id: 'w1', view: 'ofx' }, { id: 'w2', view: 'tape' }], max: 2 }), 'cvd');
    const fresh = rows.filter((r) => r.kind === 'open_new')[0];
    assert.strictEqual(fresh.disabled, true);
    assert.ok(/limit/.test(fresh.note));
    assert.ok(rows.filter((r) => r.kind === 'screen').every((r) => r.disabled === true));
});

check('a screen without a label falls back to its number', () => {
    const rows = W.model(native({ screens: [{ index: 3 }, {}] }), 'ofx');
    const labels = rows.filter((r) => r.kind === 'screen').map((r) => r.label);
    assert.deepStrictEqual(labels, ['Monitor 4', 'Monitor 1']);
});

check('the model never mutates the state it was given', () => {
    const state = native({ open: ['w1'], windows: [{ id: 'w1', view: 'ofx' }] });
    const snapshot = JSON.stringify(state);
    W.model(state, 'ofx');
    assert.strictEqual(JSON.stringify(state), snapshot);
});

check('a focus given in odd case or with spaces is normalised, not refused', () => {
    const rows = W.model(native(), '  OFX  ');
    assert.strictEqual(rows[0].view, 'ofx');
});

console.log('windows-ui selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
