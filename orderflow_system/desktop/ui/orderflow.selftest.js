/* orderflow.selftest.js — the footprint drawer's contract, pinned without a browser.
 *
 * What this pins: the settings block coerces garbage the way the server does, the session window
 * reads the clock the way the server does, the marks (imbalance, stacks, diagonal, absorption, POC,
 * value area, the row filter, the count metric) follow the fixtures hand-checked in
 * `test_footprint_config.py`, and the panel refuses in one sentence instead of inventing a cell.
 * It also holds this module's DEFAULTS/CATALOG key set and its route literal against the Python
 * module's own text, so the two copies cannot drift apart silently.
 *
 * Run: node orderflow_system/desktop/ui/orderflow.selftest.js
 * Prints "orderflow selftest: N ok, M failed" and exits non-zero on any failure — pytest's
 * test_footprint_config.py gates the suite on that verdict and runs the two implementations side by
 * side on shared fixtures.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');

const MODULE = __dirname + '/orderflow.js';
const PYTHON = __dirname + '/../../atlas/footprint_config.py';
const src = fs.readFileSync(MODULE, 'utf8');
const python = fs.readFileSync(PYTHON, 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

/* The module is an IIFE that reads `window`; a bare object is enough for the pure half, and
   `document` is left undefined on purpose — nothing here may need a DOM at load time. */
function boot(doc, win) {
    const target = win || {};
    new Function('window', 'document', src)(target, doc);
    return target.OFAPFOOTPRINT;
}

const F = boot();

/* ── the fixtures, shared with test_footprint_config.py ─────────────────────────────────────── */

const SAME_PRICE = [
    { price: 100.0, bid: 20, ask: 20 },
    { price: 100.5, bid: 5, ask: 15 },
    { price: 101.0, bid: 4, ask: 16 },
    { price: 101.5, bid: 3, ask: 15 },
    { price: 102.0, bid: 30, ask: 5 },
    { price: 102.5, bid: 18, ask: 6 },
];
const DIAGONAL = [
    { price: 100.0, bid: 5, ask: 10 },
    { price: 100.5, bid: 20, ask: 30 },
    { price: 101.0, bid: 10, ask: 9 },
];
const ABSORPTION = [
    { price: 100.0, bid: 10, ask: 10 },
    { price: 100.5, bid: 10, ask: 10 },
    { price: 101.0, bid: 100, ask: 100 },
    { price: 101.5, bid: 10, ask: 10 },
    { price: 102.0, bid: 10, ask: 10 },
];
const QUIET_BAR = { open: 101.0, high: 101.4, low: 100.9, close: 101.05 };
const RANGE_BAR = { open: 100.0, high: 102.0, low: 99.9, close: 101.9 };
const CLUSTER = [
    { price: 100.0, bid: 10, ask: 10, count: 4 },
    { price: 100.25, bid: 12, ask: 8, count: 6 },
    { price: 100.5, bid: 5, ask: 30, count: 3 },
    { price: 100.75, bid: 5, ask: 30, count: 5 },
];

function sides(block) {
    const out = {};
    block.rows.forEach((row) => { if (row.imbalance) out[row.price] = row.imbalance; });
    return out;
}

/* ── the block: coercion and clamping, exactly like the server's ─────────────────────────────── */

{
    check('clean: junk reads as the shipped block', JSON.stringify(F.clean(null)) === JSON.stringify(F.DEFAULTS));
    check('clean: a list of keys is not a patch', JSON.stringify(F.clean(['x'])) === JSON.stringify(F.DEFAULTS));
    const unknown = F.clean({ nope: 1, imbalance_threshold: 4 });
    check('clean: unknown keys are dropped', !('nope' in unknown) && unknown.imbalance_threshold === 4);
    check('clean: numbers clamp to their bound', F.clean({ imbalance_threshold: 99 }).imbalance_threshold === 50);
    check('clean: a low number clamps up', F.clean({ imbalance_threshold: -3 }).imbalance_threshold === 1);
    check('clean: numeric strings count', F.clean({ imbalance_threshold: '2.5' }).imbalance_threshold === 2.5);
    check('clean: junk numbers keep the default', F.clean({ imbalance_threshold: 'junk' }).imbalance_threshold === 3);
    check('clean: whole-row counts are made whole', F.clean({ stack_min_levels: 3.7 }).stack_min_levels === 4);
    check('clean: an empty list is not the number zero', F.clean({ ticks_per_row: [] }).ticks_per_row === 1);
    check('clean: switches take 0/1/on/off', F.clean({ poc_per_bar: 0 }).poc_per_bar === false
        && F.clean({ poc_per_bar: 'on' }).poc_per_bar === true
        && F.clean({ poc_per_bar: 'junk' }).poc_per_bar === true);
    check('clean: enums take hand-typed spellings',
        F.clean({ imbalance_mode: 'same-price' }).imbalance_mode === 'same_price'
        && F.clean({ imbalance_mode: 'Both' }).imbalance_mode === 'both'
        && F.clean({ cell_metric: 'prints' }).cell_metric === 'count');
    check('clean: an unknown enum keeps the default', F.clean({ cell_metric: 'nonsense' }).cell_metric === 'bid_ask');
    check('clean: a null value keeps its default', F.clean({ cell_metric: null }).cell_metric === 'bid_ask');
}

/* ── the session window ─────────────────────────────────────────────────────────────────────── */

{
    const rth = { session_filter: 'rth' };
    check('session: inside the window', F.sessionVerdict('2026-09-18T14:00:00Z', rth) === 'in');
    check('session: outside the window', F.sessionVerdict('2026-09-18T02:00:00Z', rth) === 'out');
    check('session: seconds and milliseconds agree',
        F.sessionVerdict(1758205200, rth) === F.sessionVerdict(1758205200000, rth));
    check('session: the outside reading mirrors it',
        F.sessionVerdict('2026-09-18T02:00:00Z', { session_filter: 'outside_rth' }) === 'in'
        && F.sessionVerdict('2026-09-18T14:00:00Z', { session_filter: 'outside_rth' }) === 'out');
    check('session: an unknown clock is kept, not thrown away',
        F.sessionVerdict(null, rth) === 'all' && F.sessionVerdict('junk', rth) === 'all');
    const wrap = { session_filter: 'rth', session_start_min: 1200, session_end_min: 120 };
    check('session: a window that wraps past midnight',
        F.sessionVerdict('2026-09-18T22:00:00Z', wrap) === 'in'
        && F.sessionVerdict('2026-09-18T01:00:00Z', wrap) === 'in'
        && F.sessionVerdict('2026-09-18T06:00:00Z', wrap) === 'out');
    check('session: start == end is the whole day',
        F.sessionVerdict('2026-09-18T06:00:00Z',
            { session_filter: 'rth', session_start_min: 0, session_end_min: 0 }) === 'in');
}

/* ── the rows ───────────────────────────────────────────────────────────────────────────────── */

{
    const rows = F.readRows([{ price: 100 }, null, { price: 'abc' }, { price: 100.5, bid: 5, ask: 15 }]);
    check('rows: unusable entries are dropped, not guessed', rows.length === 2 && rows[0].volume === 0);
    check('rows: a missing count stays null, never zero', rows[1].count === null && rows[1].volume === 20);
    const mapping = F.readRows({ 100: [5, 15], 100.5: [5, 15] });
    check('rows: a price -> (bid, ask) mapping reads too',
        mapping.length === 2 && mapping[0].ask === 15);
    check('rows: junk input is no rows at all', F.readRows('junk').length === 0 && F.readRows(null).length === 0);
    const clustered = F.clustered(F.readRows(CLUSTER), F.clean({ ticks_per_row: 2 }), 0.25);
    check('rows: two ticks per row cluster into two rows', clustered.rows.length === 2);
    check('rows: a clustered row carries its span', clustered.rows[0].span[0] === 100 && clustered.rows[0].span[1] === 100.25);
    check('rows: a clustered row sums its sides and prints',
        clustered.rows[1].bid === 10 && clustered.rows[1].ask === 60 && clustered.rows[1].count === 8);
}

/* ── the marks ──────────────────────────────────────────────────────────────────────────────── */

{
    const block = F.annotateBar(SAME_PRICE);
    check('marks: the heavy side is marked on each row',
        JSON.stringify(sides(block)) === JSON.stringify({ 100.5: 'buy', 101: 'buy', 101.5: 'buy', 102: 'sell', 102.5: 'sell' }),
        JSON.stringify(sides(block)));
    check('marks: three in a row is a stack, two is not', block.stacks.length === 1
        && block.stacks[0].levels === 3 && block.stacks[0].side === 'buy'
        && block.stacks[0].from_price === 101.5 && block.stacks[0].to_price === 100.5
        && block.stacks[0].max_ratio === 5);
    check('marks: the stack reaches the rows it covers',
        block.rows.filter((row) => row.stack).length === 3);
    check('marks: a missing row breaks the run',
        F.annotateBar(SAME_PRICE.filter((row) => row.price !== 101)).stacks.length === 0);
    check('marks: the counts match the rows', block.counts.imbalance_buy === 3
        && block.counts.imbalance_sell === 2 && block.counts.stacks === 1);
}

{
    check('marks: same-price says nothing on the diagonal fixture', Object.keys(sides(F.annotateBar(DIAGONAL))).length === 0);
    const diagonal = F.annotateBar(DIAGONAL, { imbalance_mode: 'diagonal' });
    check('marks: the diagonal reading flags what same-price cannot see',
        JSON.stringify(sides(diagonal)) === JSON.stringify({ 100.5: 'buy' }), JSON.stringify(sides(diagonal)));
    check('marks: the diagonal ratio uses the row below', diagonal.rows[1].ratios.diagonal === 6);
    check('marks: both conventions at once', F.annotateBar(DIAGONAL, { imbalance_mode: 'both' }).counts.diagonal === 1);
    const both = F.annotateBar([
        { price: 100.0, bid: 5, ask: 5 },
        { price: 100.5, bid: 1, ask: 40 },
        { price: 101.0, bid: 1, ask: 40 },
        { price: 101.5, bid: 1, ask: 40 },
    ], { imbalance_mode: 'both' });
    check('marks: both readings stack separately',
        JSON.stringify(both.stacks.map((run) => run.mode).sort()) === JSON.stringify(['diagonal', 'same_price']));
}

{
    const quiet = F.annotateBar(ABSORPTION, null, QUIET_BAR);
    check('marks: absorption needs the size and a quiet body',
        quiet.absorption.length === 1 && quiet.absorption[0].price === 101
        && quiet.absorption[0].ratio === 3.5714 && quiet.body_known === true);
    check('marks: a bar that ran did not absorb',
        F.annotateBar(ABSORPTION, null, RANGE_BAR).absorption.length === 0);
    check('marks: without OHLC the size clause alone decides',
        F.annotateBar(ABSORPTION).body_known === false && F.annotateBar(ABSORPTION).absorption.length === 1);
    check('marks: a higher absorption size marks nothing',
        F.annotateBar(ABSORPTION, { absorption_threshold: 4 }, QUIET_BAR).absorption.length === 0);
}

{
    const block = F.annotateBar(ABSORPTION);
    check('marks: POC is the heaviest row', block.poc.price === 101 && block.poc.share_pct === 71.4286);
    check('marks: the value area holds the chosen share',
        block.value_area.val === 101 && block.value_area.vah === 101 && block.value_area.rows === 1);
    check('marks: the POC row is flagged, and only it',
        block.rows.filter((row) => row.poc).length === 1 && block.rows[2].poc === true);
    const wider = F.annotateBar(ABSORPTION, { value_area_pct: 0.95 });
    check('marks: a wider share swallows the bar',
        wider.value_area.val === 100 && wider.value_area.vah === 102 && wider.value_area.rows === 5);
    const off = F.annotateBar(ABSORPTION, { poc_per_bar: false, value_area_per_bar: false });
    check('marks: the POC and value area switches turn both off',
        off.poc === null && off.value_area === null && !off.rows.some((row) => row.poc || row.value_area));
    check('marks: the row filter reads the rest of the bar',
        F.annotateBar(ABSORPTION, { min_level_volume: 50 }).filtered.levels === 4
        && F.annotateBar(ABSORPTION, { min_level_volume: 50 }).rows.length === 1);
    check('marks: equal rows and the extremes are flagged with their switches',
        F.annotateBar(ABSORPTION).counts.equal === 5
        && F.annotateBar(ABSORPTION).extremes.max_bid === 101
        && F.annotateBar(ABSORPTION, { show_extremes: false }).extremes.max_bid === null);
}

{
    const noCounts = F.annotateBar(ABSORPTION, { cell_metric: 'count' });
    check('marks: the count metric refuses when the bars carry no counts',
        noCounts.refusal === F.REFUSALS.count && noCounts.ok === false
        && noCounts.rows.every((row) => row.metric === null));
    const counted = F.annotateBar(CLUSTER, { cell_metric: 'count', ticks_per_row: 2 }, null, 0.25);
    check('marks: the count metric sums a clustered row',
        JSON.stringify(counted.rows.map((row) => row.metric)) === JSON.stringify([10, 8]));
    check('marks: the metric reads the row it names', (() => {
        const one = [{ price: 100, bid: 30, ask: 10, count: 7 }];
        return F.annotateBar(one, { cell_metric: 'bid' }).rows[0].metric === 30
            && F.annotateBar(one, { cell_metric: 'ask' }).rows[0].metric === 10
            && F.annotateBar(one, { cell_metric: 'delta' }).rows[0].metric === -20
            && F.annotateBar(one, { cell_metric: 'bid_ask' }).rows[0].metric === 40
            && F.annotateBar(one, { cell_metric: 'count' }).rows[0].metric === 7;
    })());
}

/* ── the refusals: one plain sentence, never a fabricated cell ──────────────────────────────── */

{
    const empty = F.annotateBar(null);
    check('refusal: no rows at all', empty.ok === false && empty.refusal === F.REFUSALS.noRows
        && empty.rows.length === 0 && empty.poc === null);
    check('refusal: every row is dropped by the row-volume filter',
        F.annotateBar(ABSORPTION, { min_level_volume: 500 }).refusal === F.REFUSALS.allFiltered);
    check('refusal: a bar the session filter excludes is not marked',
        F.annotateBar(SAME_PRICE, { session_filter: 'rth' }, { time: '2026-09-18T02:00:00Z' }).refusal === F.REFUSALS.session);
    check('refusal: junk never throws', (() => {
        try {
            [undefined, 'junk', 5, [null, 'x', { nope: 1 }], [['nested']], { a: { b: 1 } }]
                .forEach((garbage) => { F.annotateBar(garbage); F.annotateBars(garbage); });
            return true;
        } catch (error) { return false; }
    })());
    const payload = F.annotateBars([{ levels: SAME_PRICE }, { levels: SAME_PRICE, time: '2026-09-18T02:00:00Z' }],
        { session_filter: 'rth' });
    check('refusal: a payload reports what it kept and what it did not',
        payload.kept === 1 && payload.skipped === 1 && payload.ok === true);
    check('refusal: an empty payload refuses in one sentence',
        F.annotateBars([], null).ok === false && F.annotateBars([], null).refusal === F.REFUSALS.noBars
        && F.annotateBars(null, null).refusal === F.REFUSALS.noBars);
}

/* ── the drawer's own words ─────────────────────────────────────────────────────────────────── */

{
    check('drawer: the pill counts the changes',
        F.pillText(F.DEFAULTS, F.DEFAULTS) === 'as shipped'
        && F.pillText(F.clean({ stack_min_levels: 4 }), F.DEFAULTS) === '1 of 21 changed');
    check('drawer: the legend prints the server refusal sentence',
        F.legendText(F.annotateBar(null)) === F.REFUSALS.noRows);
    check('drawer: the legend counts the marked rows',
        F.legendText(F.annotateBar(SAME_PRICE)).indexOf('last bar: 3 buy / 2 sell imbalanced rows \u00b7 1 stack') === 0,
        F.legendText(F.annotateBar(SAME_PRICE)));
    check('drawer: a stored block that kept half the keys says so',
        (() => {
            const counted = F.keptCount(F.DEFAULTS, { cell_metric: 'bid_ask', stack_min_levels: 3 });
            return counted.total === 21 && counted.kept === 2;
        })());
    check('drawer: one control is one patch, never a bare value', (() => {
        const patch = F.patchFor('imbalance_threshold', '4.5');
        return Object.keys(patch).length === 1 && patch.imbalance_threshold === '4.5'
            && F.clean(patch).imbalance_threshold === 4.5;
    })());
    check('drawer: every control is rendered from the server row', (() => {
        const html = F.controlHtml({ key: 'cell_metric', label: 'Cell metric', kind: 'enum',
                                     choices: ['bid_ask', 'bid'], meaning: 'what a cell is read for' },
                                   'bid');
        const number = F.controlHtml({ key: 'stack_min_levels', label: 'Rows for a stack', kind: 'number',
                                       min: 1, max: 20, step: 1, unit: 'rows', meaning: 'how many rows' }, 3);
        const bool = F.controlHtml({ key: 'poc_per_bar', label: 'POC on every bar', kind: 'bool',
                                     meaning: 'mark the point of control' }, true);
        return html.indexOf('ofp_f_cell_metric') > 0 && html.indexOf('selected') > 0
            && number.indexOf('min="1"') > 0 && number.indexOf('value="3"') > 0
            && bool.indexOf('checked') > 0 && bool.indexOf('ofp-meaning') > 0;
    })());
}

/* ── null-safety: no DOM, no chart, no throw ────────────────────────────────────────────────── */

{
    check('safety: mounting without a document answers null', F.mount() === null);
    check('safety: attaching to nothing answers nothing', F.attach(null) === null);
    check('safety: drawing on a chart with no overlay is a quiet false', F.drawMarks({}) === false
        && F.drawMarks(null) === false);
    check('safety: the chart wrap is skipped with no chart class', F.wrapChart() === false);
    const withDoc = boot({ readyState: 'complete', head: { appendChild() {} },
                           createElement() { return { style: {}, setAttribute() {} }; },
                           getElementById() { return null; },
                           querySelector() { return null; } });
    check('safety: a page with no Order Flow section mounts nothing and still loads',
        withDoc.mount() === null);
    check('safety: the surface exports the pure half', typeof withDoc.annotateBar === 'function'
        && typeof withDoc.annotateBars === 'function' && typeof withDoc.clean === 'function'
        && typeof withDoc.sessionVerdict === 'function');
}

/* ── the two copies cannot drift apart: keys and route, read from the Python module ─────────── */

{
    function blockKeys(text, marker) {
        const start = text.indexOf(marker);
        if (start < 0) return null;
        const body = text.slice(start, text.indexOf('\n}', start));
        const found = [];
        const pattern = /"([a-z_]+)":/g;
        let match = pattern.exec(body);
        while (match) { found.push(match[1]); pattern.lastIndex = match.index + match[0].length; match = pattern.exec(body); }
        return found.length ? found.sort() : null;
    }
    const pyDefaults = blockKeys(python, 'DEFAULTS: dict[str, Any] = {');
    check('parity: the Python module was found', !!pyDefaults, 'no DEFAULTS block read');
    check('parity: the default key sets are equal',
        JSON.stringify(pyDefaults) === JSON.stringify(Object.keys(F.DEFAULTS).sort()),
        JSON.stringify(pyDefaults) + ' vs ' + JSON.stringify(Object.keys(F.DEFAULTS).sort()));
    const pyBounds = blockKeys(python, 'BOUNDS: dict[str, tuple[float, float, float]] = {');
    check('parity: the numeric bound tables cover the same keys',
        JSON.stringify(pyBounds) === JSON.stringify(Object.keys(F.BOUNDS).sort()));
    const pyChoices = blockKeys(python, 'CHOICES: dict[str, tuple[str, ...]] = {');
    check('parity: the enum tables cover the same keys',
        JSON.stringify(pyChoices) === JSON.stringify(Object.keys(F.CHOICES).sort()));
    const catalog = [];
    const catalogPattern = /"key": "([a-z_]+)"/g;
    let hit = catalogPattern.exec(python);
    while (hit) { catalog.push(hit[1]); hit = catalogPattern.exec(python); }
    check('parity: every catalog row is a default key', catalog.length > 0
        && catalog.every((key) => key in F.DEFAULTS) && catalog.length === Object.keys(F.DEFAULTS).length);
    check('parity: the refusal sentences are worded the same on both sides',
        python.indexOf('this bar is not in the window the session filter keeps') > 0
        && python.indexOf('no price rows to read') > 0
        && F.REFUSALS.noRows.indexOf('no price rows to read') === 0);
    check('parity: the route literal is the Python module\'s own path',
        python.indexOf('prefix="/api/atlas"') > 0
        && python.indexOf('@router.get("/footprint/config")') > 0
        && src.indexOf("'/api/atlas/footprint/config'") > 0);
}

console.log('orderflow selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const failure of failures) console.log('  FAIL', failure);
process.exit(failures.length ? 1 : 0);
