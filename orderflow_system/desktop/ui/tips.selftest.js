/* tips.selftest.js — the deciding half of the tips layer, pinned without a browser.
 *
 * Novelty gating is the whole point: a tip shows only while its feature is genuinely unused, in
 * registry order, capped — and a check that cannot run must count as USED (a broken signal may
 * silence a tip, never produce a nag). `node desktop/ui/tips.selftest.js` prints the counts and
 * exits non-zero on any failure.
 */
'use strict';

const fs = require('fs');
const src = fs.readFileSync(__dirname + '/tips.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

function boot() {
    const doc = { readyState: 'complete', getElementById() { return null; }, addEventListener() {} };
    const win = { document: doc };
    new Function('window', 'document', src)(win, doc);
    return win.OFAPTIPS;
}

const T = boot();
const none = { layouts: 0, workspaces: 0, alertRules: 0, journal: 0 };
const some = { layouts: 2, workspaces: 0, alertRules: 0, journal: 0 };
const all = { layouts: 2, workspaces: 1, alertRules: 3, journal: 9 };

check('module exposes its surface', T && typeof T.pick === 'function' && typeof T.countOf === 'function');
check('registry carries at least four solid tips', Array.isArray(T.TIPS) && T.TIPS.length >= 4);
check('every tip has id, title, body, door and a done()', T.TIPS.every((t) =>
    t.id && t.title && t.body && t.door && (t.door.view || t.door.help || t.door.menu) && typeof t.done === 'function'));
check('tip ids are unique', new Set(T.TIPS.map((t) => t.id)).size === T.TIPS.length);
check('nothing used: the first three show, in registry order',
    JSON.stringify(T.pick(T.TIPS, none, 3).map((t) => t.id)) === JSON.stringify(T.TIPS.slice(0, 3).map((t) => t.id)));
check('a used feature retires its tip', T.pick(T.TIPS, some, 3).map((t) => t.id).join(',') === 'workspaces,alerts,journal');
check('all used: nothing shows (the card retires)', T.pick(T.TIPS, all, 3).length === 0);
check('the cap is respected', T.pick(T.TIPS, none, 2).length === 2 && T.pick(T.TIPS, none, 1).length === 1);
check('a check that throws counts as used, never a nag',
    T.pick([{ id: 'x', title: 'x', body: 'x', door: { view: 'alerts' }, done() { throw new Error('boom'); } }], none, 3).length === 0);
check('countOf reads arrays, maps and missing shapes',
    T.countOf([1, 2]) === 2 && T.countOf({ a: 1, b: 2, c: 3 }) === 3 && T.countOf(null) === 0 && T.countOf(7) === 0);
check('every door names exactly one target (view | help | menu)',
    T.TIPS.every((t) => ['view', 'help', 'menu'].filter((k) => t.door[k]).length === 1));

console.log('tips selftest: ' + ok + ' ok, ' + failures.length + ' failed');
if (failures.length) {
    failures.forEach((f) => console.log('  FAIL ' + f));
    process.exit(1);
}
