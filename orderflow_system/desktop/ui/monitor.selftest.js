/* monitor.selftest.js — the companion monitor's decisions, pinned without a browser.
 *
 * Everything between "the server's payload" and "the sentence in a panel" is pure here: the number
 * and timestamp formatting, the sign colouring, the newest-first alert order, the alert context
 * line, the watchlist-to-engine-but-quotes join, the position/stat/level lines, the refusal
 * sentences, and the read's banner. orderflow_system/test_monitor.py re-runs a subset of these same
 * documented cases through node, checks the endpoint literals against the route tables, and owns the
 * self-containment half; the DOM half is the page itself.
 *
 * The cases below are the documented contract: test_monitor.py's CASES table mirrors them, so a
 * change here and a change there must agree.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/monitor.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPMONITOR;
}
const M = boot();
const DASH = '\u2014';
const NOW = 1_700_000_000_000;

check('the module exposes its whole surface, and the symbols stay inert', () => {
    for (const fn of ['esc', 'normalize', 'num', 'fmtValue', 'fmtPrice', 'group', 'fmtTicks', 'fmtPct',
                      'toneFor', 'severityTone', 'fmtAge', 'fmtClock', 'alertsNewestFirst',
                      'alertContext', 'alertSentence', 'alertRowHtml', 'alertListHtml',
                      'alertCountText', 'quoteIndex', 'watchRows', 'watchRowHtml', 'watchListHtml',
                      'watchSubText', 'positionLine', 'statsCells', 'statsHtml', 'ordersHtml',
                      'closedRows', 'closedHtml', 'paperSubText', 'readBanner', 'readInputsText',
                      'readLevelsHtml', 'readSummaryText', 'defaultSymbol', 'statusFor', 'showPanel',
                      'selectSymbol', 'onClick', 'paintBadges', 'paintStatus', 'refresh', 'tick',
                      'wire', 'state']) {
        assert.strictEqual(typeof M[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(M.DASH, DASH);
    assert.strictEqual(M.TICK_MS, 5000);
    assert.strictEqual(M.ALERT_LIMIT, 60);
    assert.strictEqual(M.PANEL_NAMES.join(','), 'alerts,paper,watch,read');
});

check('escaping and symbol normalisation are the page\'s edge', () => {
    assert.strictEqual(M.esc('<b>a</b> & "b"'), '&lt;b&gt;a&lt;/b&gt; &amp; &quot;b&quot;');
    assert.strictEqual(M.esc(null), '');
    assert.strictEqual(M.normalize(' btcusdt '), 'BTCUSDT');
    assert.strictEqual(M.normalize(null), '');
    assert.strictEqual(M.num('12.5'), 12.5);
    assert.strictEqual(M.num(''), null);
    assert.strictEqual(M.num('nope'), null);
});

check('numbers print plainly, and a missing number is a dash rather than a zero', () => {
    assert.strictEqual(M.fmtValue(12.5), '12.5');
    assert.strictEqual(M.fmtValue(3), '3');
    assert.strictEqual(M.fmtValue('buy'), 'buy');
    assert.strictEqual(M.fmtValue(0), '0');
    assert.strictEqual(M.fmtValue(null), DASH);
    assert.strictEqual(M.fmtPrice(81200), '81200.00');
    assert.strictEqual(M.fmtPrice(0.1234567), '0.123457');
    assert.strictEqual(M.fmtPrice(81200, 0), '81200');
    assert.strictEqual(M.fmtPrice(undefined), DASH);
    assert.strictEqual(M.fmtTicks(12.34), '+12.3');
    assert.strictEqual(M.fmtTicks(-3), '-3.0');
    assert.strictEqual(M.fmtTicks(0), '0.0');
    assert.strictEqual(M.fmtTicks(10000000), '+10,000,000.0');
    assert.strictEqual(M.fmtTicks(-1234567.8), '-1,234,567.8');
    assert.strictEqual(M.group(1234567), '1,234,567');
    assert.strictEqual(M.group('12.5'), '12.5');
    assert.strictEqual(M.fmtTicks(null), DASH);
    assert.strictEqual(M.fmtPct(1.256), '+1.26%');
    assert.strictEqual(M.fmtPct(-0.3), '-0.30%');
    assert.strictEqual(M.fmtPct(0), '0.00%');
    assert.strictEqual(M.fmtPct(null), DASH);
});

check('the sign colouring is one word per value', () => {
    assert.strictEqual(M.toneFor(5), 'up');
    assert.strictEqual(M.toneFor(-1), 'down');
    assert.strictEqual(M.toneFor(0), 'flat');
    assert.strictEqual(M.toneFor(null), 'flat');
    assert.strictEqual(M.severityTone('critical'), 'crit');
    assert.strictEqual(M.severityTone('warning'), 'warn');
    assert.strictEqual(M.severityTone('info'), 'info');
    assert.strictEqual(M.severityTone(undefined), 'info');
});

check('ages read in words, and a stamp from the future is never a negative age', () => {
    assert.strictEqual(M.fmtAge(NOW - 1500, NOW), '1 s ago');
    assert.strictEqual(M.fmtAge(NOW - 5000, NOW), '5 s ago');
    assert.strictEqual(M.fmtAge(NOW - (4 * 60000), NOW), '4 min ago');
    assert.strictEqual(M.fmtAge(NOW - (2 * 3600000), NOW), '2 h ago');
    assert.strictEqual(M.fmtAge(NOW + 60000, NOW), 'now');
    assert.strictEqual(M.fmtAge(0, NOW), 'never');
    assert.strictEqual(M.fmtAge(NOW - 1000, 0), 'never');
    assert.ok(/^\d\d:\d\d$/.test(M.fmtClock(NOW)), M.fmtClock(NOW));
    assert.strictEqual(M.fmtClock(0), DASH);
});

check('the alert log reads newest first, without reordering the server\'s array', () => {
    const rows = [{ ts_ms: 30, message: 'old' }, null, { ts_ms: 10, message: 'oldest' },
                  { ts_ms: 60, message: 'newest' }];
    const sorted = M.alertsNewestFirst(rows);
    assert.deepStrictEqual(sorted.map((r) => r.message), ['newest', 'old', 'oldest']);
    assert.strictEqual(rows[0].message, 'old', 'the input array is not the page\'s to reorder');
    assert.deepStrictEqual(M.alertsNewestFirst(null), []);
});

check('an alert carries its own context, and nothing else', () => {
    assert.strictEqual(M.alertContext({ data: { price: 81200, size: 12.5, side: 'buy' } }),
                       'price 81200 \u00b7 size 12.5 \u00b7 side buy');
    assert.strictEqual(M.alertContext({ data: { mystery: 1 } }), '');
    assert.strictEqual(M.alertContext({ data: { price: { nested: true } } }), '');
    assert.strictEqual(M.alertContext({}), '');
    assert.strictEqual(M.alertContext(null), '');
    assert.strictEqual(M.alertContext({ data: { price: 1, size: 2, volume: 3, side: 'buy',
                                                multiple: 4, levels: 5 } }).split(' \u00b7 ').length, 4,
                       'a context line stays a sentence: four fields at most');
});

check('the alert panel prints rows, or the honest sentence about having none', () => {
    const payload = { ok: true, alerts: [
        { rule_id: 'r1', name: 'wall', kind: 'wall_age', symbol: 'btcusdt', ts_ms: NOW - 2000,
          message: 'wall held <5 min>', severity: 'warning', data: { price: 81200, side: 'buy' } },
        { rule_id: 'r2', name: 'sweep', kind: 'sweep', symbol: '', ts_ms: NOW - 60000,
          message: 'sweep up', severity: 'info', data: {} },
    ] };
    const html = M.alertListHtml(payload, NOW);
    assert.strictEqual(html.indexOf('<5 min>'), -1, 'the message is escaped');
    assert.ok(html.indexOf('wall held &lt;5 min&gt;') > 0);
    assert.ok(html.indexOf('BTCUSDT') > 0);
    assert.ok(html.indexOf('all symbols') > 0, 'an alert with no symbol is not shown against one');
    assert.ok(html.indexOf('data-tone="warn"') > 0 && html.indexOf('data-tone="info"') > 0);
    assert.ok(html.indexOf('price 81200') > 0);
    assert.ok(html.indexOf('wall held') < html.indexOf('sweep up'), 'newest first');
    assert.strictEqual(M.alertSentence(payload), '');
    assert.strictEqual(M.alertCountText(payload), '2');
    assert.strictEqual(M.alertCountText({ ok: false, error: 'x' }), DASH);

    const empty = { ok: true, alerts: [] };
    assert.ok(M.alertListHtml(empty, NOW).indexOf('no alerts have fired') > 0);
    const refused = { ok: false, error: 'no engine is running' };
    assert.ok(M.alertListHtml(refused, NOW).indexOf('no engine is running') > 0,
              'the server\'s own sentence, verbatim');
    assert.ok(M.alertListHtml(null, NOW).indexOf('did not answer') > 0);
});

check('watchlist rows are the engine\'s quotes, and a symbol it is not streaming says so', () => {
    const quotes = M.quoteIndex([{ symbol: 'btcusdt', last: 81200, chg_pct: 1.25, delta: -4 },
                                 null, { symbol: '', last: 1 }]);
    assert.deepStrictEqual(Object.keys(quotes), ['BTCUSDT']);
    const rows = M.watchRows(['BTCUSDT', 'ETHUSDT'], quotes);
    assert.strictEqual(rows.length, 2);
    assert.strictEqual(rows[0].last, 81200);
    assert.strictEqual(rows[1].quote, null);
    assert.deepStrictEqual(M.watchRows(null, quotes), []);

    const html = M.watchListHtml({ ok: true, watchlist: ['btcusdt', 'ethusdt'] }, quotes, 'ethusdt');
    assert.ok(html.indexOf('no live readings') > 0, 'the unstreamed symbol refuses in words');
    assert.ok(html.indexOf('data-mon-symbol="BTCUSDT"') > 0, 'the row is the page\'s one control');
    assert.ok(html.indexOf('data-mon-symbol="ETHUSDT" class="mon-pick on dim"') > 0
              || html.indexOf('mon-pick on') > 0, 'the chosen symbol is marked');
    assert.ok(html.indexOf('+1.25%') > 0);
    assert.ok(html.indexOf('data-tone="down"') > 0, 'a negative delta is coloured');
    const escaped = M.watchListHtml({ ok: true, watchlist: ['<img>'] }, {}, '');
    assert.strictEqual(escaped.indexOf('<img>'), -1);
    assert.ok(M.watchListHtml({ ok: true, watchlist: [] }, {}, '').indexOf('watchlist is empty') > 0);
    assert.ok(M.watchListHtml({ ok: false, error: 'config unreadable' }, {}, '')
        .indexOf('config unreadable') > 0);
    assert.ok(M.watchListHtml(null, {}, '').indexOf('did not answer') > 0);
});

check('the watchlist sub-line counts what is streaming', () => {
    const payload = { ok: true, watchlist: ['BTCUSDT', 'ETHUSDT'] };
    assert.strictEqual(M.watchSubText(payload, M.quoteIndex([{ symbol: 'BTCUSDT', last: 1 }])),
                       '1 of 2 streaming \u00b7 change is over the engine\'s own scanner window');
    assert.strictEqual(M.watchSubText(payload, {}),
                       'no instrument here is streaming \u2014 quotes appear while the engine runs');
    assert.strictEqual(M.watchSubText({ ok: true, watchlist: [] }, {}), 'no symbols stored');
    assert.strictEqual(M.watchSubText(null, {}), 'the watchlist could not be read');
});

check('the simulated account reads in its own units (ticks), never in invented money', () => {
    const running = {
        running: true, symbol: 'btcusdt', tick_size: 0.01, last_price: 81200,
        position: { side: 'long', size: 2, entry_price: 81000, entry_ms: NOW - 120000 },
        stats: { realised_ticks: 12.34, unrealised_ticks: -3, equity_ticks: 9.34, closed: 2,
                 wins: 1, losses: 1, orders_submitted: 4, orders_filled: 3 },
        orders: [], closed: [],
    };
    assert.strictEqual(M.positionLine(running, NOW), 'long 2 @ 81000.00 \u00b7 opened 2 min ago');
    assert.strictEqual(M.paperSubText({ ok: true, state: running }),
                       'BTCUSDT \u00b7 tick 0.01 \u00b7 mark 81200.00');
    assert.strictEqual(M.paperSubText({ ok: true, state: { running: true, symbol: 'BTCUSDT',
                                                           tick_size: 0.01, last_price: 0 } }),
                       'BTCUSDT \u00b7 tick 0.01 \u00b7 no print yet',
                       'a zero mark is "no print yet", not a price of zero');
    const cells = M.statsCells(running);
    assert.deepStrictEqual(cells.map((c) => c.value),
                           ['+12.3', '-3.0', '+9.3', '2  (1 w / 1 l)', '4 in \u00b7 3 filled']);
    assert.deepStrictEqual(cells.map((c) => c.tone), ['up', 'down', 'up', 'flat', 'flat']);
    assert.ok(M.statsHtml(running).indexOf('data-tone="down"') > 0);

    const flat = { running: true, symbol: 'BTCUSDT', position: { side: 'flat', size: 0 } };
    assert.ok(M.positionLine(flat, NOW).indexOf('flat \u2014 no open position on BTCUSDT') === 0);
    const stopped = { running: false, position: { side: 'flat', size: 0 } };
    assert.ok(M.positionLine(stopped, NOW).indexOf('no simulated account is running') === 0,
              'a stopped session refuses in a sentence, not a zeroed row');
    assert.deepStrictEqual(M.statsCells(stopped), []);
    assert.strictEqual(M.statsHtml(stopped), '');
    assert.strictEqual(M.ordersHtml(stopped), '');
    assert.strictEqual(M.closedHtml(stopped), '');
    assert.strictEqual(M.paperSubText(null), 'the simulated account did not answer \u2014 is the app running?');
});

check('working orders and closed legs print what the account reports', () => {
    const state = {
        running: true,
        orders: [{ side: 'buy', kind: 'limit', size: 1.5, price: 81000, stop_loss: 80000,
                   take_profit: 83000 }],
        closed: [
            { direction: 'long', entry_price: 81000, exit_price: 81500, pnl_ticks: 50, rr_ratio: 2 },
            { direction: 'short', entry_price: 81500, exit_price: 81800, pnl_ticks: -30, rr_ratio: 0 },
        ],
    };
    const orders = M.ordersHtml(state);
    assert.ok(orders.indexOf('1.5 buy') > 0 && orders.indexOf('at 81000.00') > 0);
    assert.ok(orders.indexOf('stop 80000.00') > 0 && orders.indexOf('target 83000.00') > 0);
    assert.ok(M.ordersHtml({ running: true, orders: [] }).indexOf('no working orders') > 0);
    const closed = M.closedHtml(state);
    assert.ok(closed.indexOf('-30.0 ticks') < closed.indexOf('+50.0 ticks'), 'newest leg first');
    assert.ok(closed.indexOf('data-tone="down"') > 0 && closed.indexOf('data-tone="up"') > 0);
    assert.ok(M.closedHtml({ running: true, closed: [] }).indexOf('nothing has closed yet') > 0);
    assert.strictEqual(M.closedRows(state).length, 2);
});

check('the read panel prints the engine\'s own name and the server\'s own refusal', () => {
    const read = {
        ok: true, symbol: 'BTCUSDT', spot: 81200, conviction: 63.4,
        regime: { name: 'buyer_control', description: 'Buyers in control at the session high.' },
        levels: [{ price: 81200.5, kind: 'wall_ask', source: 'depth', strength: 0.82 },
                 { price: '<b>poc</b>', kind: 'poc', source: 'profile', strength: null }],
        summary: 'Two-sided auction.', inputs: { tape: { measured: true }, footprint: { measured: false } },
    };
    const banner = M.readBanner(read);
    assert.strictEqual(banner.text, 'buyer control \u2014 Buyers in control at the session high.');
    assert.strictEqual(banner.kind, 'ok');
    assert.strictEqual(M.readBanner({ ok: false, error: 'no live readings for this instrument' }).text,
                       'no live readings for this instrument');
    assert.strictEqual(M.readBanner({ ok: false, error: 'x' }).kind, 'warn');
    assert.strictEqual(M.readBanner(null).kind, 'warn');
    assert.strictEqual(M.readInputsText(read), 'not measured: footprint');
    assert.strictEqual(M.readInputsText({ inputs: { tape: { measured: true } } }),
                       'every signal measured');
    assert.strictEqual(M.readSummaryText(read), 'Two-sided auction.');
    assert.strictEqual(M.readSummaryText({ ok: false }), '');
    const levels = M.readLevelsHtml(read);
    assert.strictEqual(levels.indexOf('<b>poc</b>'), -1, 'no raw markup reaches the page');
    assert.ok(levels.indexOf('wall ask') > 0 && levels.indexOf('82%') > 0);
    assert.ok(M.readLevelsHtml({ levels: [] }).indexOf('no key levels') > 0);
    /* §148 / T7-F9: a read that did not answer is not a market state. This assertion used to read
       `assert.ok(M.readLevelsHtml(null).indexOf('no key levels') > 0)` — it pinned the bug: a
       failure rendered as "no key levels in this state", a claim about the market made from an
       error. A null payload now says the levels are unknown, and only an answered read with no
       levels claims there are none. */
    assert.ok(M.readLevelsHtml(null, 'BTCUSDT').indexOf('did not answer') > 0);
    assert.strictEqual(M.readLevelsHtml(null, 'BTCUSDT').indexOf('no key levels'), -1,
                       'a failed read must not render as a market claim');
    /* §148 / T7-F8: nothing asked is not the same as nothing answered — an empty watchlist with no
       session must not blame the app. */
    assert.ok(M.readBanner(null, '').text.indexOf('no symbol chosen yet') === 0);
    assert.ok(M.readLevelsHtml(null, '').indexOf('no symbol chosen yet') > 0);
    const many = M.readLevelsHtml({ levels: new Array(20).fill({ price: 1, kind: 'x', source: 'y' }) });
    assert.strictEqual(many.split('<li').length - 1, M.LEVEL_ROWS, 'the phone list is capped');
});

check('the read follows the simulated account, else the first watchlist symbol', () => {
    assert.strictEqual(M.defaultSymbol({ running: true, symbol: 'btcusdt' }, ['ETHUSDT']), 'BTCUSDT');
    assert.strictEqual(M.defaultSymbol({ running: true, symbol: '' }, ['ethusdt']), 'ETHUSDT');
    assert.strictEqual(M.defaultSymbol({ running: false }, ['ethusdt', 'BTCUSDT']), 'ETHUSDT');
    assert.strictEqual(M.defaultSymbol(null, []), '');
});

check('the header says live or names the reads that failed', () => {
    const live = M.statusFor([], NOW);
    assert.strictEqual(live.kind, 'ok');
    assert.ok(live.text.indexOf('read only \u00b7 updated ') === 0, live.text);
    const bad = M.statusFor(['alerts', 'read'], NOW);
    assert.strictEqual(bad.kind, 'warn');
    assert.ok(bad.text.indexOf('2 of 4 reads failed (alerts, read)') === 0, bad.text);
});

check('without a DOM every painter and the tab switch stay harmless', () => {
    assert.strictEqual(M.wire(), false, 'no monitor markup on the page means nothing to poll');
    assert.doesNotThrow(() => M.tick());
    assert.doesNotThrow(() => M.paintBadges());
    assert.doesNotThrow(() => M.paintStatus());
    assert.doesNotThrow(() => M.onClick({}));
    assert.doesNotThrow(() => M.onClick({ target: {} }));
    assert.strictEqual(M.showPanel('nope'), 'alerts');
    assert.strictEqual(M.selectSymbol(' ethusdt '), 'ETHUSDT');
    assert.strictEqual(M.state().symbol, 'ETHUSDT');
    assert.strictEqual(M.selectSymbol(''), '');
});

check('a failed read says so in plain words, never in a parser\'s', () => {
    assert.strictEqual(M.failWord(new Error('Failed to fetch')), 'the app is not answering on this address');
    assert.strictEqual(M.failWord(new Error('NetworkError when attempting to fetch resource.')),
                       'the app is not answering on this address');
    assert.strictEqual(M.failWord(new Error('the app answered 503 Service Unavailable')),
                       'the app answered 503 Service Unavailable');
    assert.strictEqual(M.failWord(new Error('the app did not answer with data')),
                       'the app did not answer with data');
    assert.strictEqual(M.failWord(null), 'the read failed');
    assert.strictEqual(M.failWord(new Error('')), 'the read failed');
});

check('the module polls on one guarded cadence and never writes', () => {
    const sites = src.match(/setInterval\s*\(/g) || [];
    assert.strictEqual(sites.length, 1, 'one poller for four panels');
    const at = src.indexOf('setInterval(');
    const window = src.slice(Math.max(0, at - 400), at + 600);
    assert.ok(window.indexOf('OFAPPause') > 0, 'the cadence is handed to the pause registry');
    assert.ok(src.indexOf('document.hidden') > 0, 'and a hidden page does not poll');
    assert.ok(src.indexOf('OFAP_PAUSED') > 0, 'nor does a paused app');
    assert.strictEqual(/method\s*:/.test(src), false, 'the page sends no request options at all');
    assert.strictEqual(/(POST|PUT|DELETE|PATCH)\b/.test(src), false, 'read-only means read-only');
    const paths = (src.match(/'\/(?:api)\/[^']*'/g) || []).map((raw) => raw.slice(1, -1));
    assert.deepStrictEqual(Array.from(new Set(paths)), [
        '/api/atlas/alerts?limit=', '/api/atlas/replay/paper/state', '/api/control/search/watchlist',
        '/api/atlas/scanner?limit=', '/api/atlas/market-read/',
    ], 'the five documented endpoints, and no others');
});

check('the footer names the one thing the page does write', () => {
    /* §148 / T7-F13: the footer said the page "only reads" while storeSymbol keeps the chosen
       symbol in localStorage — a write, on the user's own device. The sentence and the code have
       to agree: the page carries the write, and the footer says it does. */
    const html = fs.readFileSync(__dirname + '/monitor.html', 'utf8');
    assert.ok(/localStorage\.(get|set)Item/.test(src), 'the page no longer writes — the disclosure would be stale');
    const footer = html.slice(html.indexOf('mon-foot'));
    assert.ok(footer.indexOf('remembered in this browser') > 0,
        'the footer claims the page only reads, but it remembers the picked symbol');
});

check('the footer names the policy the server actually keeps', () => {
    /* §148 / T7-F16: the monitor page said nothing about who can reach the server it reads. It now
       says loopback-only — and that claim is checked against the launcher's own bind, so the two
       cannot drift apart. */
    const html = fs.readFileSync(__dirname + '/monitor.html', 'utf8');
    const launcher = fs.readFileSync(__dirname + '/../launcher.py', 'utf8');
    const footer = html.slice(html.indexOf('mon-foot'));
    assert.ok(footer.indexOf('answers on 127.0.0.1 only') > 0,
        'the footer does not state the loopback policy');
    /* The desktop server is the one this page reads: it is handed loopback at the call site, not
       read from a setting — so "nothing on the LAN can reach it" is checkable, not a hope. */
    assert.ok(/target=serve, args=\(app, "127\.0\.0\.1", port, started\)/.test(launcher),
        'the desktop server no longer binds loopback — the footer claim would be false');
});

console.log('monitor selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
