/* sessions.selftest.js — the Sessions panel's decisions, pinned without a browser.
 *
 * Everything between "the server's payload" and "a sentence on screen" is pure: the phase words, the
 * countdown and clock arithmetic, the picker and roll markup, the copy body. The DOM half is covered
 * by scripts/audit_ui_refs.py (the module is on its JS_FILES list, so its paths are route-checked and
 * its ids checked) plus the last two checks here, which read the source for what cannot be exercised
 * without a document: the id prefix, the pause-registered timer, and the section-scoped lookup.
 *
 * Fixtures are real payloads from orderflow_system/atlas/sessions.py (trimmed), so a shape change in
 * the module fails here rather than in the browser.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/sessions.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}
async function acheck(name, fn) {
    try { await fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot(win) {
    const target = win || {};
    new Function('window', src)(target);
    return target.OFAPSESSIONS;
}

const S = boot();
const DASH = '\u2014';

/* ── fixtures (real payloads, trimmed) ───────────────────────────────────────────────────────── */

function openState() {
    return {
        ok: true, at_ms: 1789999200000, template: 'cme-globex-index', timezone: 'America/Chicago',
        timezone_known: true, state: 'open', phase: 'open', reason: '', holiday: '',
        local: { date: '2026-09-21', time: '09:00', weekday: 0, weekday_name: 'mon',
                 offset_minutes: -300, minutes: 540 },
        session_date: '2026-09-20', open_ms: 1789941600000, close_ms: 1790024400000,
        next_open_ms: null, next_close_ms: 1790024400000, minutes_to_open: 0, minutes_to_close: 420,
        elapsed_minutes: 960, session_minutes: 1380, break_minutes: 0, trade_minutes: 1380,
        elapsed_share: 0.696, progress_pct: 70, breaks: [],
        hours: '17:00 \u2192 16:00 America/Chicago (+1 day)', days: [1, 2, 3, 4, 7],
        problems: [], note: 'Example: a session that wraps midnight.',
    };
}

function payload(state, extra) {
    return Object.assign({
        ok: true, detail: '', at_ms: 1789999200000, at: '2026-09-21 14:00:00 UTC',
        symbol: 'ESZ26', root: 'ES', how: "the template's own symbol list (root ES)",
        template: { name: 'cme-globex-index', title: 'CME Globex \u2014 equity index', exchange: 'CME',
                    timezone: 'America/Chicago', days: [1, 2, 3, 4, 7], open: '17:00', close: '16:00',
                    holiday_rule: '', note: 'Example: a session that wraps midnight.' },
        templates: [
            { name: 'cme-globex-index', title: 'CME Globex \u2014 equity index', exchange: 'CME',
              timezone: 'America/Chicago', days: [1, 2, 3, 4, 7], open: '17:00', close: '16:00',
              holiday_rule: '', builtin: true, active: false },
            { name: 'my-hours', title: 'My hours', exchange: '', timezone: 'UTC', days: [1, 2, 3, 4, 5],
              open: '08:00', close: '20:00', holiday_rule: '', builtin: false, active: true },
        ],
        state: state || openState(),
        holidays: [
            { date: '2026-11-26', name: 'Thanksgiving', closed: true, close: '', days_away: 66, weekday: 'thu' },
            { date: '2026-11-27', name: 'day after Thanksgiving', closed: false, close: '13:00',
              days_away: 67, weekday: 'fri' },
        ],
        rolls: [
            { ok: true, root: 'ES', kind: 'index', label: 'E-mini S&P 500', venue: 'CME',
              rule: 'the third Friday of the contract month', note: 'the last full trading day',
              at: '2026-09-21', front: 'ESZ26', next_roll: '2026-12-17', days_to_roll: 87,
              contracts: [
                  { symbol: 'ESZ26', expiry: '2026-12-18', roll: '2026-12-17', days_to_roll: 87, front: true },
                  { symbol: 'ESH27', expiry: '2027-03-19', roll: '2027-03-18', days_to_roll: 178, front: false },
              ], funding: [] },
            { ok: true, root: 'CL', kind: 'energy', label: 'WTI crude oil', venue: 'NYMEX',
              rule: 'three business days before the 25th of the month before delivery',
              note: 'volume leaves early', at: '2026-09-21', front: 'CLX26', next_roll: '2026-10-16',
              days_to_roll: 3,
              contracts: [
                  { symbol: 'CLX26', expiry: '2026-10-21', roll: '2026-10-16', days_to_roll: 3, front: true },
              ], funding: [] },
            { ok: true, root: 'BTC', kind: 'perpetual', label: 'Bitcoin perpetual', venue: 'crypto venues',
              rule: 'no expiry \u2014 a perpetual has no roll', note: 'funding every 8 h', at: '2026-09-21',
              front: '', next_roll: '', days_to_roll: null, contracts: [],
              funding: [{ at_ms: 1789920000000, at: '2026-09-20 16:00 UTC', minutes_away: 240, hours_away: 4 }] },
            { ok: false, root: 'ZZZ', kind: 'unknown', detail: 'no roll rule for ZZZ \u2014 the table knows ES, CL' },
        ],
        settings: { active: 'my-hours', months: 2, roots: ['ES', 'CL'], symbols: {} },
    }, extra || {});
}

/* ── the surface and the constants ─────────────────────────────────────────────────────────── */

check('the module exposes its whole surface', () => {
    for (const fn of ['esc', 'pad', 'phaseWord', 'phaseClass', 'fmtDuration', 'fmtOffset', 'localClock',
                      'countdownText', 'progressPct', 'hoursText', 'daysText', 'stateLine', 'queryFor',
                      'templateOption', 'pickerHtml', 'holidayRows', 'contractRows', 'rollSection',
                      'templateBlockWith', 'shellHtml', 'paint', 'paintClock', 'load', 'wire', 'watch',
                      'state']) {
        assert.strictEqual(typeof S[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(S.VIEW, '.view[data-view="sessions"]');
    assert.strictEqual(S.TICK_MS, 1000);
    assert.strictEqual(S.REFRESH_MS, 30000);
    assert.strictEqual(S.ROLL_SOON, 5);
});

check('the six phases have words and a lamp class, and anything else reads unknown', () => {
    assert.strictEqual(S.phaseWord('open'), 'open');
    assert.strictEqual(S.phaseWord('break'), 'break');
    assert.strictEqual(S.phaseWord('pre-open'), 'pre-open');
    assert.strictEqual(S.phaseWord('post-close'), 'post-close');
    assert.strictEqual(S.phaseWord('holiday'), 'holiday');
    assert.strictEqual(S.phaseWord('closed'), 'closed');
    assert.strictEqual(S.phaseWord(''), 'unknown');
    assert.strictEqual(S.phaseClass('open'), 'is-open');
    assert.strictEqual(S.phaseClass('break'), 'is-break');
    assert.strictEqual(S.phaseClass('nonsense'), 'is-closed');
});

check('the countdown reads in minutes, then h + m, then d + h — and never invents one', () => {
    assert.strictEqual(S.fmtDuration(0), '0 min');
    assert.strictEqual(S.fmtDuration(1), '1 min');
    assert.strictEqual(S.fmtDuration(59), '59 min');
    assert.strictEqual(S.fmtDuration(60), '1 h 00 m');
    assert.strictEqual(S.fmtDuration(125), '2 h 05 m');
    assert.strictEqual(S.fmtDuration(1439), '23 h 59 m');
    assert.strictEqual(S.fmtDuration(1440), '1 d 0 h');
    assert.strictEqual(S.fmtDuration(4320), '3 d 0 h');
    assert.strictEqual(S.fmtDuration(null), DASH);
    assert.strictEqual(S.fmtDuration(undefined), DASH);
    assert.strictEqual(S.fmtDuration('junk'), DASH);
});

check('the UTC offset prints as the exchange writes it, half-hours included', () => {
    assert.strictEqual(S.fmtOffset(-240), 'UTC-04:00');
    assert.strictEqual(S.fmtOffset(-300), 'UTC-05:00');
    assert.strictEqual(S.fmtOffset(0), 'UTC+00:00');
    assert.strictEqual(S.fmtOffset(330), 'UTC+05:30');
});

check('the local clock ticks seconds between payloads, from the payload\'s own stamp', () => {
    const clock = openState();
    const line = S.localClock(clock, clock.at_ms);
    assert.ok(line.indexOf('09:00:00 America/Chicago (UTC-05:00)') === 0, line);
    const later = S.localClock(clock, clock.at_ms + 65000);
    assert.ok(later.indexOf('09:01:05') === 0, later);
    const midnight = S.localClock(Object.assign({}, clock, { local: { time: '23:59', offset_minutes: 60 } }),
                                  clock.at_ms + 120000);
    assert.ok(midnight.indexOf('00:01:00') === 0, midnight);
    assert.strictEqual(S.localClock(null, 0), DASH);
});

check('the countdown line is the server\'s state, in words', () => {
    assert.strictEqual(S.countdownText(openState()), 'closes in 7 h 00 m');
    assert.strictEqual(
        S.countdownText(Object.assign(openState(), { state: 'closed', phase: 'break', minutes_to_open: 45 })),
        'reopens in 45 min \u00b7 closes in 7 h 00 m');
    assert.strictEqual(
        S.countdownText(Object.assign(openState(), { state: 'closed', phase: 'holiday',
                                                    reason: 'Thanksgiving', minutes_to_open: 1410 })),
        'closed for Thanksgiving \u00b7 opens in 23 h 30 m');
    assert.strictEqual(
        S.countdownText(Object.assign(openState(), { state: 'closed', phase: 'closed', reason: 'the weekend',
                                                    minutes_to_open: 3120 })),
        'the weekend \u00b7 opens in 2 d 4 h');
    assert.strictEqual(S.countdownText(null), DASH);
});

check('progress is the server\'s share, and nothing at all while no session runs', () => {
    assert.strictEqual(S.progressPct(openState()), 70);
    assert.strictEqual(S.progressPct(Object.assign(openState(), { elapsed_share: null })), null);
    assert.strictEqual(S.progressPct(Object.assign(openState(), { elapsed_share: 1.4 })), 100);
    assert.strictEqual(S.progressPct(Object.assign(openState(), { elapsed_share: -0.2 })), 0);
    assert.strictEqual(S.progressPct({}), null);
});

check('the hours line is the server\'s own (it knows about a session that wraps)', () => {
    const clock = openState();
    assert.strictEqual(S.hoursText(clock, { name: 'x', open: '17:00', close: '16:00' }),
                       '17:00 \u2192 16:00 America/Chicago (+1 day)');
    assert.strictEqual(S.hoursText({}, { name: 'x', open: '09:30', close: '16:00', timezone: 'America/New_York' }),
                       '09:30 \u2192 16:00 America/New_York');
    assert.strictEqual(S.hoursText({}, {}), DASH);
});

check('the weekday list is said in words', () => {
    assert.strictEqual(S.daysText([1, 2, 3, 4, 5]), 'mon-fri');
    assert.strictEqual(S.daysText([1, 2, 3, 4, 7]), 'mon, tue, wed, thu, sun');
    assert.strictEqual(S.daysText([1, 2, 3, 4, 5, 6, 7]), 'every day');
    assert.strictEqual(S.daysText([]), '');
    assert.strictEqual(S.daysText(null), '');
});

check('the state line says the phase and, when closed, why', () => {
    assert.strictEqual(S.stateLine(openState()), 'the session is open');
    assert.strictEqual(S.stateLine(Object.assign(openState(), { phase: 'holiday', reason: 'Thanksgiving' })),
                       'the session is holiday \u00b7 Thanksgiving');
    assert.strictEqual(S.stateLine(null), DASH);
});

/* ── the request and the picker ────────────────────────────────────────────────────────────── */

check('the query carries only what is set, encoded', () => {
    assert.strictEqual(S.queryFor('', ''), '');
    assert.strictEqual(S.queryFor('fx-sydney', ''), '?template=fx-sydney');
    assert.strictEqual(S.queryFor('', 'CL'), '?root=CL');
    assert.strictEqual(S.queryFor('my hours', 'ES'), '?template=my%20hours&root=ES');
});

check('an option marks the built-ins, the user\'s copies and what is shown now', () => {
    const builtin = S.templateOption({ name: 'cme-globex-index', title: 'CME Globex', exchange: 'CME',
                                       timezone: 'America/Chicago', builtin: true }, 'cme-globex-index');
    assert.ok(builtin.indexOf('value="cme-globex-index"') > 0, builtin);
    assert.ok(builtin.indexOf(' selected') > 0, builtin);
    assert.ok(builtin.indexOf('(mine)') < 0, builtin);
    const mine = S.templateOption({ name: 'my-hours', title: 'My hours', timezone: 'UTC', builtin: false }, '');
    assert.ok(mine.indexOf('(mine)') > 0, mine);
    assert.ok(mine.indexOf(' selected') < 0, mine);
});

check('the picker lists every template and refuses when there are none', () => {
    const html = S.pickerHtml(payload());
    assert.ok(html.indexOf('id="sessionsPick"') > 0, html);
    assert.strictEqual((html.match(/<option /g) || []).length, 2);
    assert.ok(html.indexOf('selected') > 0, html);
    assert.ok(S.pickerHtml({ templates: [] }).indexOf('no templates are configured') > 0);
    assert.ok(S.pickerHtml(null).indexOf('no templates are configured') > 0);
});

/* ── the holidays and the roll table ───────────────────────────────────────────────────────── */

check('a holiday row names the day, the reason and the early close', () => {
    const html = S.holidayRows(payload().holidays);
    assert.ok(html.indexOf('Thanksgiving') > 0, html);
    assert.ok(html.indexOf('(early close 13:00)') > 0, html);
    assert.ok(html.indexOf('66 d') > 0, html);
    assert.ok(S.holidayRows([]).indexOf('no holidays are set') > 0);
});

check('a contract row highlights the roll that is close and marks the front month', () => {
    const html = S.contractRows(payload().rolls[1]);
    assert.ok(html.indexOf('CLX26') > 0, html);
    assert.ok(html.indexOf('sessions-soon') > 0, 'a 3-day roll must be highlighted');
    assert.ok(html.indexOf('sessions-front') > 0, 'the front month must be marked');
    const far = S.contractRows(payload().rolls[0]);
    assert.ok(far.indexOf('sessions-soon') < 0, 'an 87-day roll must not be highlighted');
    assert.ok(S.contractRows({ contracts: [] }).indexOf('no contracts in this window') > 0);
});

check('the roll table prints each root\'s rule, its front month, and a perpetual has none', () => {
    const html = S.rollSection(payload().rolls);
    assert.ok(html.indexOf('the third Friday of the contract month') > 0, html);
    assert.ok(html.indexOf('front ESZ26') > 0, html);
    assert.ok(html.indexOf('rolls 2026-12-17') > 0, html);
    assert.ok(html.indexOf('no roll \u00b7 funding in 4 h 00 m') > 0, html);
    assert.ok(html.indexOf('no roll rule for ZZZ') > 0, 'a refused root prints the server\'s sentence');
    assert.ok(S.rollSection([]).indexOf('no roots are configured') > 0);
});

check('the copy body keeps the user\'s copies, drops the built-ins, and appends the copy', () => {
    const data = payload();
    const copy = { name: 'cme-globex-index-copy', title: 'CME Globex (copy)', open: '17:00', close: '16:00' };
    const block = S.templateBlockWith(copy, data);
    assert.strictEqual(block.templates.length, 2);
    assert.strictEqual(block.templates[0].name, 'my-hours');
    assert.strictEqual(block.templates[0].builtin, undefined, 'the flag is not part of a template');
    assert.strictEqual(block.templates[0].active, undefined);
    assert.strictEqual(block.templates[1].name, 'cme-globex-index-copy');
    assert.strictEqual(S.templateBlockWith(copy, {}).templates.length, 1);
});

/* ── the shell, the paints, and the source-level pins ──────────────────────────────────────── */

check('the shell carries every id the module paints into, all prefixed', () => {
    const html = S.shellHtml();
    for (const id of ['sessionsHow', 'sessionsLamp', 'sessionsPhase', 'sessionsCountdown',
                      'sessionsLocal', 'sessionsProgressFill', 'sessionsProgress', 'sessionsHours',
                      'sessionsProblems', 'sessionsPickBox', 'sessionsCount', 'sessionsNote',
                      'sessionsMsg', 'sessionsActivate', 'sessionsCopy', 'sessionsRefresh',
                      'sessionsRolls', 'sessionsRollAt', 'sessionsHolidays', 'sessionsHolidayRule',
                      'sessionsInputs']) {
        assert.ok(html.indexOf('id="' + id + '"') > 0, id + ' is missing from the shell');
    }
});

check('paint is null-safe with no document, and keeps the payload as its state', () => {
    const win = {};
    const M = boot(win);
    const data = payload();
    const out = M.paint(data);
    assert.strictEqual(out, data);
    assert.strictEqual(M.state(), data);
    assert.doesNotThrow(() => M.paintClock());
    assert.doesNotThrow(() => M.paint({ ok: false, detail: 'no session template matches ZZZ', templates: [] }));
});

check('every element id in the module is prefixed, and none is a bare [data-view=] lookup', () => {
    const ids = new Set();
    let match;
    const pattern = /id="([A-Za-z0-9_-]+)"/g;
    while ((match = pattern.exec(src)) !== null) ids.add(match[1]);
    const assigned = /\.id\s*=\s*'([A-Za-z0-9_-]+)'/g;
    while ((match = assigned.exec(src)) !== null) ids.add(match[1]);
    assert.ok(ids.size >= 20, 'only ' + ids.size + ' ids found');
    for (const id of ids) assert.ok(id.indexOf('sessions') === 0, id + ' is not prefixed');
    assert.ok(src.indexOf("querySelector('[data-view=") < 0, 'the section lookup must be scoped to .view');
    assert.ok(src.indexOf(".view[data-view=\"sessions\"]") > 0, 'the view constant is gone');
});

check('the clock timer is handed to the pause registry, and it is the only timer', () => {
    const sites = (src.match(/setInterval\s*\(/g) || []).length;
    assert.strictEqual(sites, 1, 'the panel has exactly one timer');
    const at = src.indexOf('setInterval(');
    const window = src.slice(Math.max(0, at - 400), at + 400);
    assert.ok(window.indexOf('OFAPPause.register') > 0, 'the timer must be on the pause registry');
    assert.ok(src.indexOf("'/api/atlas/sessions'") > 0,
        'the route literal must sit at its call site — the audit reads literals');
    assert.ok(src.indexOf("el('sessionsBanner')") > 0, 'the banner id must be prefixed and read once');
    assert.ok(src.indexOf('window.fetch') > 0, 'the fallback must name the shell\'s own fetch');
});

check('the copy body keeps a user copy that shadows a built-in — the flag decides', () => {
    /* sessions.py marks a shadowing user copy `builtin: false`; this module's filter must then
       carry it in the body it posts. Measured before the fix (both halves together): the row came
       back `builtin: true`, the filter dropped it, and the POST deleted the user's copy. */
    const data = payload(null, { templates: [
        { name: 'jp-equities', title: 'My own jp-equities', timezone: 'Asia/Tokyo',
          days: [1, 2, 3, 4, 5], open: '09:00', close: '15:00', builtin: false, active: true },
        { name: 'cme-globex-index', title: 'CME Globex', timezone: 'America/Chicago',
          days: [1, 2, 3, 4, 7], open: '17:00', close: '16:00', builtin: true, active: false },
    ] });
    const copy = { name: 'my-hours-copy', title: 'My hours (copy)', open: '08:00', close: '20:00' };
    const block = S.templateBlockWith(copy, data);
    assert.deepStrictEqual(block.templates.map((row) => row.name), ['jp-equities', 'my-hours-copy']);
    assert.strictEqual(block.templates[0].builtin, undefined, 'the flag is not part of a template');
});

(async () => {
    await acheck('load() with a stubbed fetch paints the payload and never throws', async () => {
        const data = payload();
        let asked = '';
        const win = { fetch: (path) => { asked = path; return Promise.resolve({ json: () => Promise.resolve(data) }); } };
        const M = boot(win);
        const out = await M.load(true);
        assert.strictEqual(out, data);
        assert.strictEqual(asked, '/api/atlas/sessions');
        assert.strictEqual(M.state(), data);
    });

    await acheck('load() prints the server\'s refusal sentence through the banner path', async () => {
        const refusal = { ok: false, detail: 'no session template matches ZZZZ \u2014 add one in Settings', templates: [] };
        const win = { fetch: () => Promise.resolve({ json: () => Promise.resolve(refusal) }) };
        const M = boot(win);
        const out = await M.load(true);
        assert.strictEqual(out.ok, false);
        assert.ok(String(out.detail).indexOf('no session template matches') === 0);
    });

    await acheck('a failed request is reported, not thrown', async () => {
        const win = { fetch: () => Promise.reject(new Error('the app is not answering')) };
        const M = boot(win);
        const out = await M.load(true);
        assert.strictEqual(out, null);
    });

    console.log('sessions selftest: ' + ok + ' ok, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
})();
