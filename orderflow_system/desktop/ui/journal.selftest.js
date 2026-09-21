/* journal.selftest.js — the Journal panel's deep read, pinned without a browser.
 *
 * The module formats what /api/control/journal sent it and never invents a figure, so what matters
 * here is the formatting's own arithmetic and its null-safety: the heat level of a day against the
 * month's peak, the month stepping and its clamps, 'n/a' wherever the payload had nothing, and a
 * render that survives a page where the new blocks do not exist yet. The module is loaded with a
 * stub window/document — every `node` run of this file has no DOM at all — and a fake DOM supplies
 * the element ids for the rendering cases. `node desktop/ui/journal.selftest.js` prints
 * "journal selftest: N ok, M failed" and exits non-zero on any failure.
 */
'use strict';

const fs = require('fs');
const src = fs.readFileSync(__dirname + '/journal.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

/* ── stubs ───────────────────────────────────────────────────────────────── */

const IDS = ['jnStats', 'jnCount', 'jnTable', 'jnDaily', 'jnStrip', 'jnSetup', 'jnSessions',
    'jnCalendar', 'jnCalMonth', 'jnCalPrev', 'jnCalNext', 'jnRefresh', 'jnStatement', 'jnNote',
    'jnSaveNote', 'jnActionResult'];

function node(id) {
    return {
        id: id, innerHTML: '', textContent: '', value: '', onclick: null,
        querySelectorAll() { return []; },
    };
}

/* `ids` limits which elements exist: a page that has not been wired yet returns null for the rest,
   which is exactly the case the null-safe DOM rules exist for. */
function fakeDoc(ids) {
    const nodes = {};
    (ids || IDS).forEach((id) => { nodes[id] = node(id); });
    return {
        readyState: 'complete',
        addEventListener() {},
        createElement(tag) { return node(tag); },
        querySelector() { return null; },
        getElementById(id) { return nodes[id] || null; },
        nodes: nodes,
    };
}

function boot(doc) {
    const win = {};
    /* No-op setTimeout: the module's boot probes must not keep the Node process alive. */
    new Function('window', 'document', 'setTimeout', src)(win, doc || fakeDoc(), () => 0);
    return win.OFAPJOURNAL;
}

/* Everything a window finds itself missing: render must not throw when the view is a bare page. */
{
    const J = boot(fakeDoc([]));
    let threw = null;
    try {
        J.render({ ok: true, rows: [{ id: 1, instrument: 'ES', pnl_ticks: 3 }], stats: { count: 1 } });
        J.render(null);
        J.stepMonth(-1)();
    } catch (e) { threw = String(e); }
    check('null-safe: render and stepMonth survive a page with none of the blocks', threw === null, threw);
    check('null-safe: renderDeep with no stats is not a crash', (() => {
        try { J.renderDeep(undefined); return true; } catch (e) { return false; }
    })());
}

/* ── setupRows: the server's tags, formatted ─────────────────────────────── */

{
    const J = boot();
    const rows = J.setupRows([
        { key: 'open-drive', trades: 12, win_rate: 0.5833, avg_r: 0.9123, expectancy: 3.456, profit_factor: 2.1 },
        { key: 'fade', trades: 5, win_rate: 0, avg_r: null, expectancy: -4.0, profit_factor: 0.0 },
        { trades: 2 },
    ]);
    check('setupRows: one row per group', rows.length === 3);
    check('setupRows: the numbers are formatted, not recomputed',
        rows[0].tag === 'open-drive' && rows[0].trades === '12' && rows[0].win === '58.3%'
        && rows[0].avgR === '0.91' && rows[0].expectancy === '3.46' && rows[0].profitFactor === '2.1');
    check('setupRows: a group with no R says n/a, never 0', rows[1].avgR === 'n/a' && rows[1].win === '0%');
    check('setupRows: a group with no key still renders', rows[2].tag === 'untagged');
    check('setupRows: an absent block is an empty table', J.setupRows(undefined).length === 0);
}

/* ── the heat grid's arithmetic ──────────────────────────────────────────── */

{
    const J = boot();
    check('heatLevel: no P&L is no heat', J.heatLevel(0, 10) === 0 && J.heatLevel(null, 10) === 0);
    check('heatLevel: the month peak is always full', J.heatLevel(10, 10) === 4 && J.heatLevel(-10, 10) === 4);
    check('heatLevel: a quarter of the peak is the first step', J.heatLevel(2.5, 10) === 1);
    check('heatLevel: the steps are quarters of the peak',
        J.heatLevel(5, 10) === 2 && J.heatLevel(7.5, 10) === 3 && J.heatLevel(8.4, 10) === 4);
    check('heatLevel: a real day is never level 0', J.heatLevel(0.01, 10) === 1);
    check('heatLevel: a lost peak with a value still reads as the biggest', J.heatLevel(3, 0) === 4);
    check('heatSyntax: heatStyle tints winners and losers differently', (() => {
        const win = J.heatStyle(4, 10), loss = J.heatStyle(-4, 10), none = J.heatStyle(0, 10);
        return win.indexOf('--of-ok-rgb') > 0 && loss.indexOf('--of-err-rgb') > 0
            && none.indexOf('--of-white-rgb') > 0;
    })());
    check('heatSyntax: the tint deepens with the level', (() => {
        const alpha = (style) => Number(style.split(',').pop().replace(')', ''));
        return alpha(J.heatStyle(10, 10)) > alpha(J.heatStyle(2.5, 10));
    })());
}

/* ── calendarModel / calendarHtml ────────────────────────────────────────── */

const CAL = {
    months: [
        { month: '2023-11', label: 'November 2023', weeks: [[null, null, null, null, null, null, null]], peak: 10, pnl: 6, trades: 2, days: 2 },
        { month: '2023-12', label: 'December 2023',
          weeks: [[null, null, null, null, { day: '2023-12-01', dom: 1, pnl: 7, trades: 1 }, null, null],
                  [null, null, null, null, { day: '2023-12-08', dom: 8, pnl: -3, trades: 2 }, null, null]],
          peak: 7, pnl: 4, trades: 3, days: 2 },
    ],
    total: 10, trades: 5, days: 4,
};

{
    const J = boot();
    check('calendarModel: no months at all is null, not an empty grid', J.calendarModel({ months: [] }, null) === null
        && J.calendarModel(undefined, null) === null);
    const newest = J.calendarModel(CAL, null);
    check('calendarModel: no index means the newest month', newest.month === '2023-12' && newest.index === 1);
    check('calendarModel: an index past the end clamps to the newest', J.calendarModel(CAL, 99).index === 1);
    check('calendarModel: a negative index clamps to the oldest', J.calendarModel(CAL, -3).index === 0);
    check('calendarModel: junk falls back to the newest', J.calendarModel(CAL, 'later').index === 1);
    check('calendarModel: a short week is padded to seven cells',
        newest.weeks.every((week) => week.length === 7) && newest.weeks.length === 2);
    check('calendarModel: a day with no trade stays a hole (not a zero day)',
        newest.weeks[0][0] === null && newest.weeks[0][4].day === '2023-12-01');
    check('calendarModel: each cell carries its own heat against the month peak',
        newest.weeks[0][4].level === 4 && newest.weeks[1][4].level === 2
        && newest.weeks[1][4].style.indexOf('--of-err-rgb') > 0);
    check('calendarModel: the header numbers are passed through',
        newest.pnl === 4 && newest.trades === 3 && newest.days === 2 && newest.label === 'December 2023');
    check('cellTitle: the tooltip names the day, the P&L and the count',
        J.cellTitle({ day: '2023-12-01', pnl: 7, trades: 1 }) === '2023-12-01 · 7 ticks · 1 trade(s)');
    check('calendarHtml: no model reads as words', J.calendarHtml(null) === 'no closed trades with a date yet');
    const html = J.calendarHtml(newest);
    check('calendarHtml: the weekday header is Monday first',
        html.indexOf('<th>mon</th>') > 0 && html.indexOf('<th>sun</th>') > 0 && html.indexOf('<th>mon</th>') < html.indexOf('<th>thu</th>'));
    check('calendarHtml: every week renders seven cells',
        (html.match(/<td/g) || []).length === 14);
    check('calendarHtml: the cell carries the day, the tinted background and the number',
        html.indexOf('>1</div>') > 0 && html.indexOf('+7') > 0 && html.indexOf('--of-ok-rgb') > 0);
    check('calendarHtml: a losing day prints its sign', html.indexOf('-3') > 0 && html.indexOf('--of-err-rgb') > 0);
    const rude = J.calendarHtml(J.calendarModel({
        months: [{ month: '2023-12', label: 'December 2023', peak: 1, pnl: 1, trades: 1, days: 1,
                   weeks: [[{ day: '" onmouseover="alert(1)', dom: 1, pnl: 1, trades: 1 }, null, null, null, null, null, null]] }],
    }, 0));
    check('calendarHtml: a hostile day never escapes the tooltip attribute',
        rude.indexOf('onmouseover="alert(1)"') === -1 && rude.indexOf('&quot; onmouseover=&quot;alert(1)') > 0);
}

/* ── the strip ───────────────────────────────────────────────────────────── */

{
    const J = boot();
    const bare = J.stripItems({});
    check('stripItems: a payload with nothing in it says n/a five times',
        bare.length === 5 && bare.every((item) => item.value === 'n/a'));
    check('stripItems: the absent R is explained in words', bare[0].sub === 'no trade records a stop'
        && bare[3].sub === 'no row records mae/mfe');
    const stopped = J.stripItems({ r_count: 0, r_stops: 2 });
    check('stripItems: rows that record a stop are not told they recorded none (§148 T3-F3)',
        stopped[0].sub === '2 row(s) record a stop, none yields an R');
    const full = J.stripItems({
        expectancy_r: 0.875, r_total: 5.25, r_count: 6, r_derived: 5, r_recorded: 1,
        payoff_ratio: 1.4167, avg_win: 17, avg_loss: 12, max_win_streak: 2, max_loss_streak: 1,
        mae_mfe: { count: 4, avg_mfe: 8.75, avg_mae: 4.5 },
    });
    check('stripItems: the R figures carry their signs',
        full[0].value === '+0.88R' && full[2].value === '+5.25R');
    check('stripItems: the payoff is two decimals', full[1].value === '1.42' && full[1].sub === 'avg win 17 / avg loss 12');
    check('stripItems: the excursions read MFE over MAE', full[3].value === '8.75 MFE / 4.5 MAE' && full[3].sub === '4 row(s) record one');
    check('stripItems: the streaks are both runs', full[4].value === 'W 2 / L 1');
    check('stripItems: how the R values were read is not hidden',
        full[2].sub === '5 derived, 1 as opened');

    const html = J.stripHtml({ expectancy_r: 0.5, sentences: ['expectancy is +0.50R over 4 trades.', '<b>hostile</b>'] });
    check('stripHtml: the sentences render under the chips', html.indexOf('expectancy is +0.50R over 4 trades.') > 0);
    check('stripHtml: a hostile sentence is inert text', html.indexOf('<b>hostile</b>') === -1 && html.indexOf('&lt;b&gt;hostile&lt;/b&gt;') > 0);
    check('stripHtml: no sentences is still chips', J.stripHtml({}).indexOf('class="tag"') > 0);
}

/* ── setupHtml ───────────────────────────────────────────────────────────── */

{
    const J = boot();
    const empty = J.setupHtml([]);
    check('setupHtml: no tags is a sentence, not an empty table',
        empty.indexOf('<table') === -1 && empty.indexOf('no setup tags on these trades yet') === 0);
    const html = J.setupHtml([{ key: '<img src=x>', trades: 2, win_rate: 0.5, avg_r: 1.5, expectancy: 3, profit_factor: 2 }]);
    check('setupHtml: the columns are the five a setup is judged on',
        html.indexOf('<th>trades</th>') > 0 && html.indexOf('<th>win rate</th>') > 0
        && html.indexOf('<th>avg R</th>') > 0 && html.indexOf('<th>expectancy</th>') > 0
        && html.indexOf('<th>profit factor</th>') > 0);
    check('setupHtml: a hostile tag name is inert text',
        html.indexOf('<img') === -1 && html.indexOf('&lt;img src=x&gt;') > 0);
    check('setupHtml: the tick unit and the double-count are stated',
        html.indexOf('ticks a trade') > 0 && html.indexOf('counts in both') > 0);
}

/* ── the panel, against a fake DOM ───────────────────────────────────────── */

/* The Daily P&L card names its clock in the page copy itself, which this module never touches
   (§148 T3-F8): read index.html the way `node` can and pin the line. */
{
    const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
    check('index.html: the Daily P&L card names its clock (UTC)',
        /<span class="card-title">Daily P&amp;L<\/span>\s*<div class="spacer"><\/div><span class="dim">exit day, UTC<\/span>/.test(html));
}

function payload() {
    return {
        ok: true,
        rows: [{ id: 7, instrument: 'ES', direction: 'LONG', pnl_ticks: 4, rr_ratio: 2, notes: 'open drive' }],
        daily: [{ day: '2023-12-01', pnl: 7, trades: 1 }],
        stats: {
            count: 7, wins: 4, losses: 2, win_rate: 0.5714, expectancy: 6.29, profit_factor: 2.83,
            gross_win: 68, gross_loss: 24, avg_rr: 1.75, max_drawdown: 20,
            avg_win: 17, avg_loss: 12, payoff_ratio: 1.4167, expectancy_r: 0.875, r_total: 5.25,
            r_count: 6, r_derived: 5, r_recorded: 1, max_win_streak: 2, max_loss_streak: 1,
            mae_mfe: { count: 4, avg_mfe: 8.75, avg_mae: 4.5 },
            by_setup: [{ key: 'open-drive', trades: 4, win_rate: 0.75, avg_r: 1.2, r_count: 3, expectancy: 5, profit_factor: 3 }],
            by_session: [{ key: 'LONDON', trades: 4, win_rate: 0.5, avg_r: 0.4, expectancy: 2 }],
            calendar: CAL,
            sentences: ['7 closed trades: 57.1% win rate, expectancy +6.29 ticks a trade.'],
        },
    };
}

{
    const doc = fakeDoc();
    const J = boot(doc);
    J.render(payload());
    check('render: the four tiles keep their figures', doc.nodes.jnStats.innerHTML.indexOf('57.1%') > 0
        && doc.nodes.jnStats.innerHTML.indexOf('2.83') > 0);
    check('render: the strip carries the new figures', doc.nodes.jnStrip.innerHTML.indexOf('+0.88R') > 0
        && doc.nodes.jnStrip.innerHTML.indexOf('W 2 / L 1') > 0);
    check('render: the strip reads the server sentences', doc.nodes.jnStrip.innerHTML.indexOf('57.1% win rate') > 0);
    check('render: the setup table is filled from the payload', doc.nodes.jnSetup.innerHTML.indexOf('open-drive') > 0
        && doc.nodes.jnSetup.innerHTML.indexOf('75%') > 0);
    check('render: the session block is filled too', doc.nodes.jnSessions.innerHTML.indexOf('LONDON') > 0);
    check('render: the calendar shows the newest month', doc.nodes.jnCalendar.innerHTML.indexOf('December 2023') > 0
        && doc.nodes.jnCalMonth.textContent === 'December 2023 (2/2)');
    check('render: the rows table is still the rows table', doc.nodes.jnTable.innerHTML.indexOf('open drive') > 0);
    check('render: the daily list is still the daily list', doc.nodes.jnDaily.innerHTML.indexOf('2023-12-01') > 0);
    check('render: the avg-R tile reads as the plan it is, not as the R beside it',
        doc.nodes.jnStats.innerHTML.indexOf('Planned R:R') > 0
        && doc.nodes.jnStats.innerHTML.indexOf('Average R') < 0);
    check('render: the calendar head says which clock its days are on',
        doc.nodes.jnCalendar.innerHTML.indexOf('· UTC ·') > 0);
    check('render: a setup row shows how many rows its avg R rests on',
        doc.nodes.jnSetup.innerHTML.indexOf('(3 of 4)') > 0
        && doc.nodes.jnSetup.innerHTML.indexOf('avg R covers only the rows that yield one') > 0);

    J.stepMonth(-1)();
    check('stepMonth: one month back moves the calendar and the label',
        doc.nodes.jnCalendar.innerHTML.indexOf('November 2023') > 0
        && doc.nodes.jnCalMonth.textContent === 'November 2023 (1/2)');
    J.stepMonth(-1)();
    check('stepMonth: the oldest month is a wall, not a wrap',
        doc.nodes.jnCalMonth.textContent === 'November 2023 (1/2)');
    J.stepMonth(1)();
    J.stepMonth(1)();
    check('stepMonth: the newest month is a wall too',
        doc.nodes.jnCalMonth.textContent === 'December 2023 (2/2)');

    /* A payload from a server that predates the deep blocks: the panel degrades, it does not throw. */
    let threw = null;
    try { J.render({ ok: true, rows: [], stats: { count: 0 }, daily: [] }); } catch (e) { threw = String(e); }
    check('render: an older payload degrades to n/a and words', threw === null, threw);
    check('render: no rows still says so', doc.nodes.jnTable.textContent.indexOf('no trades yet') === 0);
    check('render: the calendar says it has nothing', doc.nodes.jnCalendar.innerHTML === 'no closed trades with a date yet');
}

console.log('journal selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
