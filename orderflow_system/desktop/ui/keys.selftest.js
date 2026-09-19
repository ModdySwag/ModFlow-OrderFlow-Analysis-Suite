/* keys.selftest.js — the shortcut map's own behaviour, pinned without a browser.
 *
 * The map earns its name by being the ONE place a binding lives: what a chord canonicalises to,
 * who the typing guard protects, how two matching bindings resolve, and that a documented local
 * row can never dispatch. `node desktop/ui/keys.selftest.js` prints "keys selftest: N ok, M failed"
 * and exits non-zero on any failure, so `test_keys.py` can gate the suite on it.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/keys.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

function node(tag, opts) {
    return Object.assign({
        tagName: tag || 'DIV', isContentEditable: false,
        classList: { contains() { return false; } },
    }, opts || {});
}

function keyEv(key, mods) {
    const m = mods || {};
    const ev = {
        key, ctrlKey: !!m.ctrl, altKey: !!m.alt, metaKey: !!m.meta, shiftKey: !!m.shift,
        target: m.target || node('DIV'), prevented: false,
        preventDefault() { this.prevented = true; },
    };
    return ev;
}

/* A stub page: no real DOM, exactly the surface keys.js touches (listener attach, activeElement,
   querySelector for scope sections, querySelectorAll for the rail). */
function boot(opts) {
    const o = opts || {};
    const doc = {
        activeElement: o.active || null,
        listeners: [],
        addEventListener(kind, fn) { if (kind === 'keydown') this.listeners.push(fn); },
        querySelector(sel) { return (o.sections && o.sections[sel]) || null; },
        querySelectorAll() { return []; },
    };
    const win = { document: doc };
    new Function('window', 'document', src)(win, doc);
    return { K: win.OFAPKEYS, doc, win };
}

/* ── chord canonicalisation ──────────────────────────────────────────────── */

{
    const { K } = boot();
    check('canonical: a bare letter lowercases', K.canonical(keyEv('P')) === 'p');
    check('canonical: ctrl joins', K.canonical(keyEv('k', { ctrl: true })) === 'ctrl+k');
    check('canonical: shift is the character for punctuation', K.canonical(keyEv('?', { shift: true })) === '?');
    check('canonical: shifted "+" is its own chord', K.canonical(keyEv('+', { shift: true })) === '+');
    check('canonical: shift is kept for letters', K.canonical(keyEv('P', { shift: true })) === 'shift+p');
    check('canonical: space has a name', K.canonical(keyEv(' ')) === 'space' && K.canonical(keyEv('Spacebar')) === 'space');
    check('canonical: named keys lowercase', K.canonical(keyEv('Escape')) === 'escape' && K.canonical(keyEv('F11')) === 'f11');
    check('canonical: meta joins', K.canonical(keyEv('w', { meta: true })) === 'meta+w');
}

/* ── what the typing guard calls a field ─────────────────────────────────── */

{
    const { K } = boot();
    check('guard: INPUT / TEXTAREA / SELECT are fields',
        K.isTypingTarget(node('INPUT')) && K.isTypingTarget(node('TEXTAREA')) && K.isTypingTarget(node('SELECT')));
    check('guard: a contenteditable is a field', K.isTypingTarget(node('DIV', { isContentEditable: true })));
    check('guard: a div, a body and null are not',
        !K.isTypingTarget(node('DIV')) && !K.isTypingTarget(node('BODY')) && !K.isTypingTarget(null));
    check('guard: lowercase tag names still match', K.isTypingTarget(node('input')));
}

/* ── display formatting ──────────────────────────────────────────────────── */

{
    const { K } = boot();
    check('pretty: chords read like the sheet always read', K.pretty('ctrl+alt+t') === 'Ctrl+Alt+T'
        && K.pretty('alt+z') === 'Alt+Z');
    check('pretty: named keys get their glyphs', K.pretty('escape') === 'Esc' && K.pretty('arrowup') === '\u2191'
        && K.pretty('space') === 'Space');
    const digits = { keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'] };
    check('keysText: a run of digits collapses to 1 \u2026 9', K.keysText(digits) === '1 \u2026 9');
    /* Hover-info audit: alternatives now read " or " — "= / +" was ambiguous, and a binding whose
       key IS the slash rendered as "Ctrl+K / /". */
    check('keysText: aliases render in full', K.keysText({ keys: ['=', '+'] }) === '= or +');
    check('keysText: a slash key is unambiguous', K.keysText({ keys: ['ctrl+k', '/'] }) === 'Ctrl+K or /');
    /* The rail digits are spoken as an instruction, not as a key called 8, and the same helper
       feeds the tooltip suffix and the hover card's line (one source of truth). */
    check('shortcutPhrase: a digit reads as a press instruction',
        K.shortcutPhrase('8') === 'Press 8 to switch to this panel', K.shortcutPhrase('8'));
    check('shortcutPhrase: a chord reads as a shortcut',
        K.shortcutPhrase('Ctrl+Alt+T') === 'Shortcut Ctrl+Alt+T', K.shortcutPhrase('Ctrl+Alt+T'));
    check('shortcutPhrase: nothing in, nothing out', K.shortcutPhrase('') === '');
}

/* ── resolution rules ────────────────────────────────────────────────────── */

{
    const { K } = boot();
    K.bind({ id: 'a', keys: ['t'], label: 'a', scope: 'Global', run() {} });
    K.bind({ id: 'b', keys: ['t'], label: 'b', scope: 'Global', priority: 5, run() {} });
    check('resolve: the higher priority wins', K.resolve('t', keyEv('t'), {}).id === 'b');

    const { K: K2 } = boot();
    K2.bind({ id: 'first', keys: ['t'], label: 'first', scope: 'Global', run() {} });
    K2.bind({ id: 'second', keys: ['t'], label: 'second', scope: 'Global', run() {} });
    check('resolve: a tie goes to the first registered', K2.resolve('t', keyEv('t'), {}).id === 'first');

    const { K: K3 } = boot();
    K3.bind({ id: 'gated', keys: ['t'], label: 'gated', scope: 'Global', when: () => false, run() {} });
    check('resolve: a false gate never fires', K3.resolve('t', keyEv('t'), {}) === null);

    const { K: K4 } = boot();
    K4.bind({ id: 'plain', keys: ['t'], label: 'plain', scope: 'Global', run() {} });
    K4.bind({ id: 'field', keys: ['t'], label: 'field', scope: 'Global', inField: true, run() {} });
    check('resolve: typing swallows everything but the inField opt-in',
        K4.resolve('t', keyEv('t'), { inField: true }).id === 'field'
        && K4.resolve('t', keyEv('t'), { inField: false }).id === 'plain');

    const { K: K5 } = boot();
    K5.document([{ keys: 'F5', label: 'a local row', scope: 'Strips' }]);
    check('resolve: a documented row never dispatches', K5.resolve('f5', keyEv('F5'), {}) === null);
}

/* ── dispatch behaviour ──────────────────────────────────────────────────── */

{
    const { K } = boot();
    let fired = 0;
    K.bind({ id: 't-frozen', keys: ['p'], label: 'test', scope: 'Global', run() { fired += 1; } });
    const ev = keyEv('p');
    K.dispatch(ev);
    check('dispatch: fires, records the firing and prevents the default',
        fired === 1 && K.recent.length === 1 && K.recent[0].id === 't-frozen' && ev.prevented === true);

    const typing = keyEv('p', { target: node('INPUT') });
    K.dispatch(typing);
    check('dispatch: a field swallows the key', fired === 1 && K.recent.length === 1 && typing.prevented === false);

    const onButton = keyEv(' ', { target: node('BUTTON') });
    let spaced = 0;
    K.bind({ id: 't-space', keys: ['space'], label: 'test space', scope: 'Global', run() { spaced += 1; } });
    K.dispatch(onButton);
    check('dispatch: Space on a focused button is left to the browser', spaced === 0);
    K.dispatch(keyEv(' '));
    check('dispatch: Space elsewhere fires', spaced === 1 && K.recent[K.recent.length - 1].id === 't-space');

    const viaFieldFallback = keyEv('p', { target: node('BODY') });
    K.dispatch(viaFieldFallback);
    check('dispatch: a field-free body target fires like the letter pressed',
        fired === 2 && viaFieldFallback.prevented === true);

    const { K: K6 } = boot({ active: node('INPUT') });
    let aware = 0;
    K6.bind({ id: 't-aware', keys: ['p'], label: 'test aware', scope: 'Global', run() { aware += 1; } });
    K6.dispatch(keyEv('p', { target: node('BODY') }));
    check('dispatch: focus in a field is honoured even when the target is not one', aware === 0);
}

/* ── the sheet's source: list() ──────────────────────────────────────────── */

{
    const { K } = boot();
    K.bind({ id: 'z', keys: ['x'], label: 'clear', scope: 'Engine', priority: 6, run() {} });
    K.bind({ id: 'g', keys: ['p'], label: 'freeze', scope: 'Global', run() {} });
    K.document([{ keys: 'F5', label: 'local row', scope: 'Strips' }]);
    const rows = K.list();
    const scopes = rows.map((r) => r.scope);
    const gIdx = scopes.lastIndexOf('Global');
    check('list: Global sorts before Engine before Strips',
        gIdx < scopes.indexOf('Engine') && scopes.indexOf('Engine') < scopes.indexOf('Strips'),
        JSON.stringify(scopes));
    const doc = rows.filter((r) => r.scope === 'Strips')[0];
    check('list: documented rows keep their text verbatim and are not dispatched',
        doc.keys === 'F5' && doc.dispatched === false);
    const g = rows.filter((r) => r.id === 'g')[0];
    check('list: bindings are marked dispatched', g.dispatched === true && g.keys === 'P');
}

/* ── registration rules ──────────────────────────────────────────────────── */

{
    const { K } = boot();
    K.bind({ id: 'dup', keys: ['a'], label: 'one', scope: 'Global', run() {} });
    K.bind({ id: 'dup', keys: ['b'], label: 'two', scope: 'Global', run() {} });
    const dups = K.list().filter((r) => r.id === 'dup');
    check('bind: the same id re-registers in place (view init may run twice)',
        dups.length === 1 && dups[0].label === 'two' && dups[0].keys === 'B');

    let threw = false;
    try { K.bind({ id: 'bad', keys: ['a'], run() {} }); } catch (e) { threw = /label/.test(e.message); }
    check('bind: a spec without a label is refused', threw);

    let threwRun = false;
    try { K.bind({ id: 'bad2', keys: ['a'], label: 'x', scope: 'Global' }); } catch (e) { threwRun = true; }
    check('bind: a spec without a run is refused', threwRun);

    K.document([{ keys: 'F5', label: 'local row', scope: 'Strips' }]);
    K.document([{ keys: 'F5', label: 'local row', scope: 'Strips' }]);
    check('document: the same local row twice is still one row',
        K.list().filter((r) => r.scope === 'Strips').length === 1);
}

/* ── the scope gate ──────────────────────────────────────────────────────── */

{
    const onScreen = { classList: { contains() { return true; } } };
    const offScreen = { classList: { contains() { return false; } } };
    const { K } = boot({ sections: { '.view[data-view="ofx"]': onScreen, '.view[data-view="replay"]': offScreen } });
    check('inView: a view section that is not active fails', K.inView('replay') === false);
    check('inView: an active section passes', K.inView('ofx') === true);

    const { K: K2 } = boot({ sections: { '.view[data-view="ofx"]': onScreen, '.view[data-view="heatmap"]': onScreen } });
    K2.bind({ id: 'e', keys: ['='], label: 'engine zoom', scope: 'Engine', priority: 6, when: () => K2.inView('ofx'), run() {} });
    K2.bind({ id: 'h', keys: ['='], label: 'heatmap zoom', scope: 'Heatmap', priority: 5, when: () => K2.inView('heatmap'), run() {} });
    check('inView: with no focused panel both visible scopes pass', K2.inView('heatmap') === true);
    check('inView: the engine outranks the heatmap on a shared chord', K2.resolve('=', keyEv('='), {}).id === 'e');

    const b2 = boot({ sections: { '.view[data-view="ofx"]': onScreen, '.view[data-view="heatmap"]': onScreen } });
    b2.win.OFAPSHELL = { state: () => ({ mode: 'terminal', focus: 'heatmap' }) };
    b2.K.bind({ id: 'e', keys: ['='], label: 'engine zoom', scope: 'Engine', priority: 6, when: () => b2.K.inView('ofx'), run() {} });
    b2.K.bind({ id: 'h', keys: ['='], label: 'heatmap zoom', scope: 'Heatmap', priority: 5, when: () => b2.K.inView('heatmap'), run() {} });
    check('inView: terminal focus narrows both scopes to the focused panel',
        b2.K.inView('ofx') === false && b2.K.resolve('=', keyEv('='), {}).id === 'h');
}

/* ── one dispatcher, and the app-core bindings ───────────────────────────── */

{
    const { K, doc } = boot();
    check('wiring: exactly one keydown listener is attached', doc.listeners.length === 1);
    const core = K.list().map((r) => r.id);
    check('core: escape, view-switch and the alpaca jump are in the map',
        core.indexOf('escape') >= 0 && core.indexOf('view-switch') >= 0 && core.indexOf('alpaca') >= 0);
    const esc = K.map().filter((b) => b.id === 'escape')[0];
    check('core: Escape is the one binding that fires while typing', esc.inField === true
        && K.map().filter((b) => b.inField).length === 1);
}

/* ── the armed gate (T3) ─────────────────────────────────────────────────── */

{
    const { K, doc } = boot();
    let fired = 0;
    K.bind({ id: 'selftest-danger', keys: ['alt+j'], scope: 'Global', danger: true,
             label: 'a dangerous test action', run: () => { fired += 1; } });
    const press = () => doc.listeners.forEach((fn) => fn(keyEv('j', { alt: true })));
    press();
    check('armed gate: a danger row never fires while disarmed', fired === 0);
    K.setArmed(true);
    press();
    check('armed gate: the same row fires once armed', fired === 1 && K.armed() === true);
    K.setArmed(false);
    press();
    check('armed gate: disarming takes it inert again', fired === 1);
}

/* ── the user’s own chords: rebinding, conflicts, reset (§117) ── */

{
    const { K } = boot();
    K.bind({ id: 'rb', keys: ['t'], label: 'rebind me', scope: 'Global', run() {} });
    check('rebind: the override replaces the chord and resolution follows it',
        K.rebind('rb', ['ctrl+alt+9']) === true
        && K.resolve('ctrl+alt+9', keyEv('9', { ctrl: true, alt: true }), {}).id === 'rb'
        && K.resolve('t', keyEv('t'), {}) === null);

    const row = K.list().filter((r) => r.id === 'rb')[0];
    check('rebind: the sheet marks the row custom and keeps the shipped default readable',
        row.custom === true && row.keys === 'Ctrl+Alt+9' && row.defaults === 'T');

    check('conflicts: a taken chord names its owner, and never the edited row itself',
        K.conflicts('ctrl+alt+9', 'someone-else').length === 1
        && K.conflicts('ctrl+alt+9', 'rb').length === 0);

    check('rebind: junk chords are refused (nothing is cleared behind the user’s back)',
        K.rebind('rb', ['']) === false && K.rebind('rb', ['a b']) === false
        && K.overrides().rb[0] === 'ctrl+alt+9');

    K.clearOverride('rb');
    check('reset: the shipped chord is back and the row is no longer custom',
        K.resolve('t', keyEv('t'), {}).id === 'rb'
        && K.list().filter((r) => r.id === 'rb')[0].custom === false);

    check('reset: the emptied override still travels (the config drops it on save)',
        Array.isArray(K.overrides().rb) && K.overrides().rb.length === 0);

    const { K: K2 } = boot();
    K2.bind({ id: 'rb2', keys: ['y'], label: 'apply me', scope: 'Global', run() {} });
    check('applyOverrides: config chords take effect on the registry',
        K2.applyOverrides({ rb2: ['ctrl+y'] }) === 1
        && K2.resolve('ctrl+y', keyEv('y', { ctrl: true }), {}).id === 'rb2');
    K2.applyOverrides({});
    check('applyOverrides: an empty map restores the registry',
        K2.resolve('ctrl+y', keyEv('y', { ctrl: true }), {}) === null
        && K2.resolve('y', keyEv('y'), {}).id === 'rb2');
}

console.log('keys selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
