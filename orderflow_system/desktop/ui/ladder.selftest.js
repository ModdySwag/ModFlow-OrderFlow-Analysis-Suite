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

/* ── order templates: the list, and the one the next entry carries ─────────── */

{
    const { L } = boot();
    check('templates: the three shipped ones are there, with their sizes',
        L.templates().map((t) => t.id).join(',') === 'scalp,intraday,runner'
        && L.templates()[2].size === 2, L.templates().map((t) => t.id).join(','));
    check('templates: a description reads the same words atm.describe uses',
        L.describe(L.template('runner')) === 'Runner — 2 contracts, stop 8t, target 32t, '
            + 'break-even at 8t, trail 10t/2t, time stop 30 min, 50% off at 8t',
        L.describe(L.template('runner')));
    check('templates: nothing is picked until something picks it',
        L.active() === null && L.template('nope') === null);

    check('templates: selecting one names it', L.select('RUNNER').id === 'runner'
        && L.active().id === 'runner');
    check('templates: an unknown id changes nothing', L.select('moon').id === 'runner');
    check('templates: "none" is no plan', L.select('none') === null && L.active() === null
        && L.select('runner').id === 'runner' && L.select('') === null);

    const coerced = L.setTemplates([{ id: 'My Plan!', name: '', size: '3', stop_ticks: '4.6',
        partial_ticks: 8, partial_pct: 0, trail_step_ticks: 0 }]);
    check('templates: a hand-edited list is coerced, never trusted',
        coerced.length === 1 && coerced[0].id === 'myplan' && coerced[0].name === 'myplan'
        && coerced[0].size === 3 && coerced[0].stop_ticks === 5 && coerced[0].partial_ticks === 0
        && coerced[0].trail_step_ticks === 1, JSON.stringify(coerced));
    check('templates: setTemplates(null) restores the shipped three',
        L.setTemplates(null).length === 3 && L.templates()[0].id === 'scalp'
        && L.setTemplates('nonsense').length === 3);
}

/* The app's own config block wins over the shipped list — a template edited in the config file
   has to reach these buttons without a second list kept in step by hand. */
{
    global.S = { config: { atm: { active: 'Mine', templates: [
        { id: 'Mine', name: 'Mine', size: 4, stop_ticks: 6, target_ticks: 18 },
        { id: '', name: 'nameless' }] } } };
    const { L } = boot();
    check('templates: the config block is the list in force',
        L.templates().length === 1 && L.templates()[0].id === 'mine' && L.templates()[0].size === 4);
    check('templates: the config block picks the first plan too', (L.active() || {}).id === 'mine');
    delete global.S;
    const plain = boot().L;
    check('templates: with no config the shipped three come back',
        plain.templates().length === 3 && plain.active() === null);
}

/* ── the template rides the decision, and owns the size ───────────────────── */

{
    const { L } = boot();
    const base = { running: true, locked: false, armed: true, size: 5, last_price: 5000, tick_size: 1 };
    const picked = L.select('runner');

    let d = L.decide(Object.assign({}, base, { price: 4999, button: 0, template: picked }));
    check('decide: the plan owns the size and travels with the order',
        d.ok && d.size === 2 && d.template.id === 'runner' && d.template.stop_ticks === 8
        && d.side === 'buy' && d.kind === 'limit' && d.price === 4999);
    d = L.decide(Object.assign({}, base, { price: 4999, button: 0 }));
    check('decide: without a plan the ticket size stands and nothing rides along',
        d.ok && d.size === 5 && d.template === null);
    d = L.decide(Object.assign({}, base, { price: 4999, button: 0, template: picked, locked: true }));
    check('decide: the lock refuses the same way with a plan picked', !d.ok
        && d.why === 'trading is locked — unlock with Lock trading');
    d = L.decide(Object.assign({}, base, { price: 4999, button: 0, template: { id: 'bare' } }));
    check('decide: a plan with no size falls back to one contract',
        d.ok && d.size === 1 && d.template.id === 'bare');
}

/* ── the plan's legs, drawn on the grid ───────────────────────────────────── */

{
    const { L } = boot();
    const state = {
        running: true, last_price: 5000.25, tick_size: 0.25,
        position: { side: 'long', size: 2, entry_price: 5000 },
        exits: { stop_loss: 4998.5, take_profit: 5008 },
        orders: [{ id: 'o2', side: 'sell', size: 1, kind: 'limit', price: 5002 }],
        plan: { ok: true, group: 'oc1', text: 'Runner — 2 contracts, stop 8t, target 32t', side: 'buy',
            entry: 5000, stop_loss: 4998.5, take_profit: 5008, breakeven_price: 5002,
            breakeven_done: false, trail_stop: 4998.5, peak: 5004, status: 'live',
            partial: { size: 1, price: 5002 }, partial_done: false,
            legs: [{ name: 'entry', price: 5000, ticks: 0, kind: 'market', size: 2, side: 'buy' },
                   { name: 'stop', price: 4998, ticks: -8, kind: 'stop', size: 2, side: 'sell' }] },
    };
    const grid = L.rows(state, 21);
    const at = (p) => grid.filter((r) => r.price === p)[0];

    check('plan: the legs read as copies', L.legs(state).length === 2
        && L.legs(state)[1].name === 'stop' && L.legs(state)[1].ticks === -8
        && L.legs(state)[0].price === 5000);
    check('plan: a state with no plan reads as none',
        L.plan({}) === null && L.legs({}).length === 0 && L.plan({ plan: { ok: false } }) === null
        && L.plan({ plan: 'nonsense' }) === null);
    check('plan: the grid still lays out 21 rows with a plan on it', grid.length === 21
        && grid[10].last === true);
    check('plan: the break-even trigger is drawn on its own row', at(5002).breakeven === true
        && at(5002).trail === false);
    check('plan: the trailing stop is drawn where it stands', at(4998.5).trail === true
        && at(4998.5).stop === true);
    const doneGrid = L.rows(Object.assign({}, state,
        { plan: Object.assign({}, state.plan, { status: 'done' }) }), 21);
    const doneAt = (p) => doneGrid.filter((r) => r.price === p)[0];
    check('plan: a done plan drops the break-even marker',
        L.rows(Object.assign({}, state, { plan: Object.assign({}, state.plan, { breakeven_done: true }) }), 21)
            .filter((r) => r.breakeven).length === 0
        && doneGrid.filter((r) => r.breakeven).length === 0);
    // §148 T1-D6: the rest of the plan was drawn anyway — the trail chip and the stop/target titles
    // read as if a closed trade were still running.
    check('plan: and a done plan drops the trail and the leg titles too',
        doneGrid.filter((r) => r.trail).length === 0
        && doneAt(4998.5).title === '' && doneGrid.filter((r) => r.title).length === 0);
    check('plan: a leg row carries its distance and the plan in the title',
        /stop — -6 ticks from entry/.test(at(4998.5).title) && /Runner/.test(at(4998.5).title), at(4998.5).title);
    // the target sits outside a grid centred on the last print, so it gets its own tape
    const held = Object.assign({}, state, { last_price: 5004.75,
        plan: Object.assign({}, state.plan, { take_profit: 5005 }) });
    const wide = L.rows(held, 21);
    check('plan: the target row carries its distance too',
        /target — 20 ticks from entry/.test(wide.filter((r) => r.price === 5005)[0].title),
        wide.filter((r) => r.price === 5005)[0].title);
    check('plan: a row that is no leg has no title', at(5000.25).title === '');
}

/* ── the plan bar, and what a click on it means ───────────────────────────── */

{
    const host = { innerHTML: '', onclick: null, oncontextmenu: null, onauxclick: null };
    const { L } = boot({ getElementById(id) { return id === 'ladderBody' ? host : null; } });
    const api = { size: () => 3, locked: () => false, armed: () => true,
        place() {}, cancel() {}, note() {} };
    L.select('');

    L.paint({ running: true, last_price: 5000, tick_size: 1, orders: [] }, api);
    check('bar: every template has a button, and cancel-all counts nothing to cancel',
        /data-ld="tpl:runner"/.test(host.innerHTML) && /data-ld="tpl:none"/.test(host.innerHTML)
        && /cancel all \(0\)/.test(host.innerHTML) && /data-ld="cancel-all" disabled/.test(host.innerHTML));
    check('bar: the bar is wired even before a print has arrived',
        typeof host.onclick === 'function' && typeof host.oncontextmenu === 'function');
    check('bar: the status line says what the next entry will do',
        /next entry: no plan/.test(host.innerHTML));

    L.paint({ running: true, last_price: 5000, tick_size: 1,
        orders: [{ id: 'o1', side: 'buy', size: 1, kind: 'limit', price: 4999 }] }, api);
    check('bar: cancel-all counts the working orders and stops refusing',
        /cancel all \(1\)/.test(host.innerHTML) && !/data-ld="cancel-all" disabled/.test(host.innerHTML));

    L.select('runner');
    L.paint(Object.assign({ running: true, last_price: 5000, tick_size: 1, orders: [] },
        { plan: { ok: true, group: 'oc1', text: 'Runner — 2 contracts', side: 'buy', entry: 5000,
            stop_loss: 5000, take_profit: 5008, peak: 5004, status: 'live', partial_done: true,
            partial: { size: 1, price: 5002, pct: 50 }, breakeven_done: true } }), api);
    check('bar: the picked plan is lit, named, and the position\'s plan is described',
        /next entry: Runner/.test(host.innerHTML)
        && /data-ld="tpl:runner" style=/.test(host.innerHTML)
        && /position: Runner — 2 contracts live/.test(host.innerHTML)
        && /peak \+4t/.test(host.innerHTML) && /stop at break-even/.test(host.innerHTML)
        // §148 T1-D11: the share is the plan's own number, not the word "half"
        && /50% off taken/.test(host.innerHTML), host.innerHTML.slice(0, 400));

    L.paint(Object.assign({ running: true, last_price: 5000, tick_size: 1, orders: [] },
        { plan: { ok: true, group: 'oc2', text: 'Runner — 2 contracts', side: 'buy', entry: 5000,
            stop_loss: 4999, take_profit: 5008, trail_stop: 4999, breakeven_price: 5002,
            breakeven_done: false, peak: 4999, status: 'live' } }), api);
    check('bar: a live plan draws its break-even trigger and its trail',
        /ld-mark-breakeven/.test(host.innerHTML) && /ld-mark-trail/.test(host.innerHTML)
        && /the stop moves to the entry price/.test(host.innerHTML), host.innerHTML.slice(0, 300));

    // §148 T1-D11: a plan resting a 25% scale-out says 25%, not "half".
    L.paint(Object.assign({ running: true, last_price: 5000, tick_size: 1, orders: [] },
        { plan: { ok: true, group: 'oc3', text: 'Runner — 2 contracts', side: 'buy', entry: 5000,
            stop_loss: 4999, take_profit: 5008, peak: 5001, status: 'live',
            partial: { size: 1, price: 5002, pct: 25 }, partial_done: false,
            breakeven_done: false } }), api);
    check('bar: the resting share is the plan\'s own pct, not a hardcoded half',
        /25% resting/.test(host.innerHTML), host.innerHTML.slice(0, 300));

    // §148 T1-D6: a finished plan is named as finished and draws no live marks.
    L.paint(Object.assign({ running: true, last_price: 5000, tick_size: 1, orders: [] },
        { plan: { ok: true, group: 'oc1', text: 'Runner — 2 contracts', side: 'buy', entry: 5000,
            stop_loss: 4999, take_profit: 5008, trail_stop: 4999.5, breakeven_price: 5002,
            breakeven_done: true, peak: 5004, status: 'done', outcome: 'stop_loss' } }), api);
    check('bar: a done plan says done and draws no trail or break-even marks',
        /done — stop_loss/.test(host.innerHTML) && !/ld-mark-trail/.test(host.innerHTML)
        && !/ld-mark-breakeven/.test(host.innerHTML), host.innerHTML.slice(0, 300));
}

/* ── act(): what one click means, pinned with hand-made targets ───────────── */

{
    const el = (attrs, classes) => {
        const node = { attrs: attrs || {}, classes: classes || [] };
        node.getAttribute = (name) => (node.attrs[name] === undefined ? null : String(node.attrs[name]));
        node.closest = (selector) => {
            if (selector === '[data-ld]') return node.attrs['data-ld'] ? node : null;
            if (selector === '.ld-order') return node.classes.indexOf('ld-order') >= 0 ? node : null;
            if (selector === '.ld-row') return node.classes.indexOf('ld-row') >= 0 ? node : null;
            return null;
        };
        return node;
    };
    const recorder = (over) => {
        const calls = [];
        const api = Object.assign({
            size: () => 3, locked: () => false, armed: () => true,
            place: (b) => calls.push(['place', b]), cancel: (id) => calls.push(['cancel', id]),
            note: (t) => calls.push(['note', t]) }, over || {});
        return { calls, api };
    };
    const { L } = boot();
    const state = { running: true, last_price: 5000, tick_size: 1,
        orders: [{ id: 'o1', side: 'buy', size: 1, kind: 'limit', price: 4999 },
                 { id: 'o2', side: 'sell', size: 1, kind: 'limit', price: 5002 }] };
    const barButton = (what) => el({ 'data-ld': what }, ['ld-order']);

    let rec = recorder();
    check('act: a template button picks the plan for the next entry',
        L.act(barButton('tpl:runner'), state, rec.api) === 'template'
        && (L.active() || {}).id === 'runner' && rec.calls.length === 0);
    check('act: the no-plan button puts the ticket back in charge',
        L.act(barButton('tpl:none'), state, rec.api) === 'template' && L.active() === null);

    rec = recorder();
    check('act: cancel all cancels each working order when there is no cancelAll',
        L.act(barButton('cancel-all'), state, rec.api) === 'cancel-all'
        && rec.calls.map((c) => c[1]).join(',') === 'o1,o2');
    rec = recorder({ cancelAll: () => rec.calls.push(['cancelAll']) });
    check('act: one cancelAll call when paper.js hands us its own',
        L.act(barButton('cancel-all'), state, rec.api) === 'cancel-all'
        && rec.calls.length === 1 && rec.calls[0][0] === 'cancelAll');
    rec = recorder();
    check('act: cancel all on an empty book only says so',
        L.cancelAll({ orders: [] }, rec.api).length === 0 && rec.calls[0][0] === 'note'
        && /no working orders to cancel/.test(rec.calls[0][1]));

    rec = recorder();
    check('act: a working order\'s chip cancels that order',
        L.act(el({ 'data-id': 'o2' }, ['ld-order', 'ld-order-sell']), state, rec.api) === 'cancel-chip'
        && rec.calls.length === 1 && rec.calls[0][0] === 'cancel' && rec.calls[0][1] === 'o2');
    check('act: the bar\'s own background places and cancels nothing',
        L.act(el({}, ['dim']), state, rec.api) === 'none'
        && L.act(el({ 'data-ld': 'bar' }), state, rec.api) === 'none' && rec.calls.length === 1);
    check('act: a click on nothing at all is not a click',
        L.act(null, state, rec.api) === 'none' && L.act({}, state, rec.api) === 'none'
        && L.act(el({ 'data-price': '5000' }, []), state, rec.api) === 'none' && rec.calls.length === 1);

    const row = el({ 'data-price': '4999' }, ['ld-row']);
    L.select('runner');
    rec = recorder();
    check('act: a row click sends the picked plan and its size',
        L.act(row, state, rec.api, 0, false) === 'place' && rec.calls.length === 1
        && rec.calls[0][0] === 'place' && rec.calls[0][1].side === 'buy'
        && rec.calls[0][1].kind === 'limit' && rec.calls[0][1].price === 4999
        && rec.calls[0][1].size === 2 && rec.calls[0][1].template.id === 'runner');
    L.select('');
    rec = recorder();
    check('act: without a plan the ticket size goes and nothing rides along',
        L.act(row, state, rec.api, 0, false) === 'place' && rec.calls[0][1].size === 3
        && rec.calls[0][1].template === undefined);
    rec = recorder({ armed: () => false });
    check('act: a disarmed row click says which switch and places nothing',
        L.act(row, state, rec.api, 0, false) === 'note' && rec.calls.length === 1
        && rec.calls[0][0] === 'note' && /arm the order keys/.test(rec.calls[0][1]));
}

console.log('ladder selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
