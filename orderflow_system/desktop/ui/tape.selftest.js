/* tape.selftest.js — the changed-digit tint: WHICH digits light up on a print.
 *
 * The widget itself is a DOM animal and is exercised by the app's own smoke run; what is pinned here
 * is the small piece of arithmetic that decides which digits of a price are wrapped — the part a
 * wrong reference price would quietly get wrong (a whole row tinted, or none of it, and nobody would
 * notice until a trader misread a tape at speed).
 */
'use strict';

const fs = require('fs');
const src = fs.readFileSync(__dirname + '/../../dashboard/static/tape.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

const win = {};
new Function('window', src)(win);
const T = win.TimeAndSales;
check('tape.js exports TimeAndSales into the page', typeof T === 'function');

/* `_priceHtml` only needs `_formatPrice` — call it with a stand-in `this` so no DOM is involved. */
const pricing = { _formatPrice: T.prototype._formatPrice };
const tint = (price, ref) => T.prototype._priceHtml.call(pricing, price, ref);
const spans = (html) => (html.match(/<span class="tape-digit-changed">([^<]*)<\/span>/g) || [])
    .map((s) => s.replace(/<[^>]*>/g, ''));

check('a price with no reference is plain text', tint(75000.12, null) === '75000.1', tint(75000.12, null));
check('an unchanged price lights nothing up', spans(tint(75000.1, 75000.1)).length === 0);
check('one moved digit lights exactly that digit',
    JSON.stringify(spans(tint(75000.2, 75000.1))) === JSON.stringify(['2']),
    JSON.stringify(spans(tint(75000.2, 75000.1))));
check('two moved digits both light', spans(tint(75011.1, 75000.1)).join('') === '11',
    spans(tint(75011.1, 75000.1)).join(''));
check('the tinted digits stay in place in the string',
    tint(75000.2, 75000.1).replace(/<[^>]*>/g, '') === '75000.2');
check('the decimal point is never tinted', spans(tint(750.02, 750.01)).join('') === '2');
check('a width change is left plain (a different number of digits says nothing)',
    spans(tint(99.75, 100.0)).length === 0 && spans(tint(100.0, 99.75)).length === 0
    && tint(99.75, 100.0).replace(/<[^>]*>/g, '') === '99.75',
    tint(99.75, 100.0) + ' / ' + tint(100.0, 99.75));
check('a moved leading digit lights up', spans(tint(76000.1, 75000.1)).join('') === '6',
    spans(tint(76000.1, 75000.1)).join(''));
check('an undefined reference is treated as no reference', tint(123.45, undefined) === '123.45');

/* The class the widget emits must be the class the stylesheet defines — a rename in one file and not
   the other would leave the tint invisible with nothing to show for it. */
const css = fs.readFileSync(__dirname + '/modules.css', 'utf8');
check('modules.css defines the class tape.js emits', css.includes('.tape-digit-changed'));

console.log('tape selftest: ' + ok + ' ok, ' + failures.length + ' failed');
if (failures.length) {
    failures.forEach((f) => console.log('  FAIL ' + f));
    process.exit(1);
}
