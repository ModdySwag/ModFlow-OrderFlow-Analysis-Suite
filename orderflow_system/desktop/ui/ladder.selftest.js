/* ladder.selftest.js — the Trade DOM's own behaviour, pinned without a browser.
 *
 * The ladder earns its keep by being predictable under a fast hand: which row is which price,
 * what each click resolves to, and that every refusal carries the exact sentence the user sees.
 * `node desktop/ui/ladder.selftest.js` prints "ladder selftest: N ok, M failed" and exits
 * non-zero on any failure, so test_ladder.py can gate the suite on it.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/ladder.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

function boot(docStub) {
    const doc = docStub || { getElementById() { return null; } };
    const win = { document: doc };
    new Function('window', 'document', src)(win, doc);
    return { L: win.OFAPLADDER, doc, win };
}

/* ── the price grid ──────────────────────────────────────────────────────── */

{
    const { L } = boot();
    check('rows: no print yet means no grid', L.rows({ last_price: 0 }, 21) === null);
    check('rows: a fresh state with no session means no grid', L.rows({}, 21) === null);

    const state = {
        last_price: 5000.25, tick_size: 0.25,
        position: { side: 'long', size: 1, entry_price: 4999.5 },
        exits: { stop_loss: 4998.75, take_profit: null },
        orders: [
            { id: 'o1', side: 'buy', size: 2, kind: 'limit', price: 4999.75 },
            { id: 'o2', side: 'sell', size: 1, kind: 'stop', price: 4998.0 },
            { id: 'o3', side: 'buy', size: 1, kind: 'market', price: null },
        ],
    };
    const grid = L.rows(state, 21);
    check('rows: 21 rows are drawn', grid.length === 21, String(grid.length));
    check('rows: the centre lands on the print', grid[10].last === true && grid[10].label === '5000.25',
        grid[10].label);
    check('rows: descending, step = tick',
        grid[0].price === 5002.75 && grid[20].price === 4997.75 && grid[1].price === 5002.5,
        grid[0].price + ' → ' + grid[20].price);
    const at = (p) => grid.filter((r) => r.price === p)[0];
    check('rows: a resting order sits on its own price only', at(4999.75).orders.length === 1
        && at(4999.75).orders[0].id === 'o1' && at(5000.25).orders.length === 0);
    check('rows: a market order has no row', grid.every((r) => r.orders.every((o) => o.id !== 'o3')));
    check('rows: entry, stop and target flags land on their prices',
        at(4999.5).entry === 'long' && at(4998.75).stop === true && at(4998.75).target === false
        && at(4999.5).stop === false);
    check('rows: flat means no entry flag', L.rows({ last_price: 100, tick_size: 1, position: { side: 'flat' } }, 21)
        .every((r) => r.entry === ''));
    check('rows: the count clamps to the odd range', L.rows(state, 4).length === 5
        && L.rows(state, 500).length === 61 && L.rows(state, 0).length === 21);
    check('fmtPrice: tick decimals decide the label', L.fmtPrice(5001.25, 0.25) === '5001.25'
        && L.fmtPrice(5000.5, 0.01) === '5000.5' && L.fmtPrice(5001, 1) === '5001'
        && L.fmtPrice(1.23456, 0.00001) === '1.23456');
}

/* ── the click grammar ───────────────────────────────────────────────────── */

{
    const { L } = boot();
    const base = { running: true, locked: false, armed: true, size: 2, last_price: 5000, tick_size: 1 };
    const decide = (over) => L.decide(Object.assign({}, base, over));

    let d = decide({ price: 4999, button: 0 });
    check('below + left = buy limit', d.ok && d.side === 'buy' && d.kind === 'limit' && d.price === 4999);
    d = decide({ price: 5001, button: 0 });
    check('above + left = buy stop', d.ok && d.side === 'buy' && d.kind === 'stop' && d.price === 5001);
    d = decide({ price: 5001, button: 2 });
    check('above + right = sell limit', d.ok && d.side === 'sell' && d.kind === 'limit');
    d = decide({ price: 4999, button: 2 });
    check('below + right = sell stop', d.ok && d.side === 'sell' && d.kind === 'stop');
    d = decide({ price: 5000, button: 0 });
    check('the last-price row trades at market (buy)', d.ok && d.side === 'buy' && d.kind === 'market'
        && d.price === null);
    d = decide({ price: 5000, button: 2 });
    check('the last-price row trades at market (sell)', d.ok && d.side === 'sell' && d.kind === 'market');
    d = decide({ price: 4999, button: 0, shift: true });
    check('shift + left = buy market anywhere', d.ok && d.side === 'buy' && d.kind === 'market');
    d = decide({ price: 5001, button: 2, shift: true });
    check('shift + right = sell market anywhere', d.ok && d.side === 'sell' && d.kind === 'market');

    check('refusal: no session', L.decide(Object.assign({}, base, { running: false, price: 4999, button: 0 }))
        .why === 'start a paper session on the Replay view first');
    check('refusal: no print', L.decide(Object.assign({}, base, { last_price: 0, price: 4999, button: 0 }))
        .why === 'no print has arrived yet — press Play first');
    check('refusal: locked', L.decide(Object.assign({}, base, { locked: true, price: 4999, button: 0 }))
        .why === 'trading is locked — unlock with Lock trading');
    check('refusal: disarmed says which switch', L.decide(Object.assign({}, base, { armed: false, price: 4999, button: 0 }))
        .why === 'that click places a simulated order — arm the order keys in the Keys menu first');
    check('refusal: junk size', L.decide(Object.assign({}, base, { size: 0, price: 4999, button: 0 }))
        .why === 'size must be a positive number');
    check('refusal: middle button', L.decide(Object.assign({}, base, { price: 4999, button: 1 }))
        .why === 'left-click buys, right-click sells — shift makes it a market order');
    check('every refusal carries a non-empty sentence',
        [decide({ running: false }), decide({ last_price: 0 }), decide({ locked: true }), decide({ armed: false }),
         decide({ size: 0 }), decide({ button: 1 })].every((r) => !r.ok && typeof r.why === 'string' && r.why.length > 10));
}

/* ── the painter ─────────────────────────────────────────────────────────── */

{
    const { L } = boot();
    // No host element (the Replay view is closed): paint must not throw.
    let threw = false;
    try { L.paint({ last_price: 5000, tick_size: 1 }, {}); } catch (err) { threw = true; }
    check('paint: a missing host is a quiet no-op', threw === false);

    const host = { innerHTML: '', onclick: null, oncontextmenu: null };
    const { L: L2 } = boot({ getElementById(id) { return id === 'ladderBody' ? host : null; } });
    L2.paint({ last_price: 0 }, {});
    check('paint: the empty state speaks', /no print yet/.test(host.innerHTML));
    L2.paint({
        running: true, last_price: 5000, tick_size: 1,
        position: { side: 'long', size: 1, entry_price: 5000 },
        exits: { stop_loss: 4999, take_profit: 5001 },
        orders: [{ id: 'o1', side: 'sell', size: 3, kind: 'limit', price: 5002 }],
    }, { size: () => 1, locked: () => false, armed: () => true, place() {}, cancel() {}, note() {} });
    check('paint: rows, marks and chips render', (host.innerHTML.match(/class="ld-row/g) || []).length === 21
        && /ld-last/.test(host.innerHTML) && />LONG</.test(host.innerHTML) && />SL</.test(host.innerHTML)
        && /data-id="o1"/.test(host.innerHTML));
    check('paint: click wiring replaces every paint (never stacks)',
        typeof host.onclick === 'function' && typeof host.oncontextmenu === 'function'
            && typeof host.onauxclick === 'function');
}

console.log('ladder selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
