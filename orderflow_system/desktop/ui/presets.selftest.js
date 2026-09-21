/* presets.selftest.js — the pure half of the preset combobox, pinned without a browser.
 *
 * The deciding rules are small and worth pinning: what a spec parses to (junk entries are
 * dropped, never fatal), and what the select shows for the input's current value (a value is a
 * preset only when its own string appears in the spec). `node desktop/ui/presets.selftest.js`
 * prints "presets selftest: N ok, M failed" and exits non-zero on any failure.
 */
'use strict';

const fs = require('fs');
const src = fs.readFileSync(__dirname + '/presets.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

function boot() {
    const doc = { readyState: 'complete', querySelectorAll() { return []; },
                  addEventListener() { /* not called with readyState complete */ } };
    const win = { document: doc };
    new Function('window', 'document', src)(win, doc);
    return win.OFAPPRESETS;
}

const P = boot();

check('module exposes its surface', P && typeof P.parseSpec === 'function' && typeof P.pick === 'function');
check('empty spec parses to nothing', P.parseSpec('').length === 0 && P.parseSpec(null).length === 0);
check('comma junk parses to nothing', P.parseSpec(' , , ').length === 0);
check('integers parse in order', JSON.stringify(P.parseSpec('68,70,80')) === '[68,70,80]');
check('spaces and floats parse', JSON.stringify(P.parseSpec(' 0.5 , 0.75 ')) === '[0.5,0.75]');
check('words are dropped, numbers kept', JSON.stringify(P.parseSpec('abc,5,7x')) === '[5]');
check('negatives are legal', JSON.stringify(P.parseSpec('-5,10')) === '[-5,10]');
check('exponent notation parses', JSON.stringify(P.parseSpec('1e3')) === '[1000]');

check('pick: an exact preset string is chosen', P.pick('2,4,8', 4) === '4');
check('pick: a string value matches too', P.pick('2,4,8', '4') === '4');
check('pick: a value outside the spec reads Custom', P.pick('2,4,8', 6) === P.CUSTOM);
check('pick: "0.70" typed by hand is not the preset 0.7', P.pick('0.7,0.8', '0.70') === P.CUSTOM);
check('pick: empty value reads Custom', P.pick('2,4,8', '') === P.CUSTOM);
check('pick: float preset chosen by its own string', P.pick('0.68,0.7,0.8', 0.7) === '0.7');

console.log('presets selftest: ' + ok + ' ok, ' + failures.length + ' failed');
if (failures.length) {
    failures.forEach((f) => console.log('  FAIL ' + f));
    process.exit(1);
}
