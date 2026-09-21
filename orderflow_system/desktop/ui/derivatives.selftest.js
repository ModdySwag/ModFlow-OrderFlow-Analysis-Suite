/* derivatives.selftest.js — the panel's decisions, pinned without a browser.
 *
 * Everything between "an HTTP payload" and "words in a cell" is pure here: the formatters, the
 * sentence, the OI read, the strip, the table rows and the banner's choice of the server's own
 * words — so all of it is checkable under plain node with no DOM. The DOM half (wire/watch/paint
 * against real nodes) is covered by scripts/audit_ui_refs.py once the module is in JS_FILES.
 *
 * `node desktop/ui/derivatives.selftest.js` prints "derivatives selftest: N ok, M failed" and exits
 * non-zero on any failure, so test_derivatives.py can gate the suite on it.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/derivatives.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

let timers = 0;
function boot() {
    const win = {};
    new Function('window', 'setInterval', 'setTimeout', 'fetch', src)(
        win, () => { timers += 1; return 0; }, () => 0, undefined);
    return win.OFAPDERIV;
}
const D = boot();
const DASH = '\u2014';

/* One captured-level payload: what the server answers for a four-venue read with OKX down. */
const PAYLOAD = {
    ok: true,
    symbol: 'BTCUSDT',
    as_of_ms: 1789905483478,
    venues_asked: 4,
    venues_ok: 3,
    summary: 'funding is +0.010%/8h (+10.9% annualised) with OI up 3.2% on the day \u2014 longs are paying to hold',
    funding: {
        available: true, verdict: 'longs pay',
        median_rate: 0.0001, median_pct: 0.01, median_interval_h: 8,
        rate_apr_pct: 10.95, median_apr_pct: 10.8873, min_apr_pct: 6.605, max_apr_pct: 10.95, spread_apr_pct: 4.345,
        direction: 'longs_pay', crowded: [], crowded_long: false, crowded_short: false,
        per_venue: [
            { venue: 'bybit', label: 'Bybit', rate: 0.00006032, interval_h: 8, pct: 0.006032, apr_pct: 6.605 },
            { venue: 'binance', label: 'Binance', rate: 0.0001, interval_h: 8, pct: 0.01, apr_pct: 10.95 },
            { venue: 'hyperliquid', label: 'Hyperliquid', rate: 0.0000125, interval_h: 1, pct: 0.00125, apr_pct: 10.95 },
        ],
    },
    oi: {
        available: true, total_usd: 16477045523.8539, venues_usd: 3, change_pct: 3.2, span_s: 86400,
        window_s: 86400, samples: 1443, window_limited: false, reason: '',
        change_source: 'the summed open interest of the venues that publish USD',
        per_venue: { bybit: 3.2, binance: 2.8, hyperliquid: 4.1 }, unit: 'BTC',
    },
    basis: {
        available: true, median_bps: -4.8019, min_bps: -5.529, max_bps: 0.3728, spread_bps: 5.9018,
        median_apr_pct: -17.5269, note: 'the annualised basis assumes the same premium every day \u2014 a perp premium is not a yield',
    },
    venues: [
        { venue: 'bybit', label: 'Bybit', instrument: 'BTCUSDT', ok: true, error: '', notes: [],
          funding_rate: 0.00006032, funding_interval_h: 8, funding_apr_pct: 6.605,
          next_funding_in_s: 14516.5, mark: 80421.58, index: 80466.07, basis_bps: -5.529,
          basis_apr_pct: -2.018, open_interest: 55420.091, open_interest_unit: 'BTC',
          open_interest_usd: 4456971281.96, oi_change_pct: 3.2, oi_span_s: 86400,
          oi_samples: 1443, oi_change_reason: '', ts_ms: 1789905483000, age_ms: 478 },
        { venue: 'binance', label: 'Binance', instrument: 'BTCUSDT', ok: true, error: '',
          notes: ['open interest in USD is computed from this venue\u2019s own open interest and mark'],
          funding_rate: 0.0001, funding_interval_h: 8, funding_apr_pct: 10.95, next_funding_in_s: 14516.5,
          mark: 80425.5544058, index: 80466.63086957, basis_bps: -5.1048, basis_apr_pct: -1.863,
          open_interest: 108955.553, open_interest_unit: 'BTC', open_interest_usd: 8762810755.6,
          oi_change_pct: 2.8, oi_span_s: 86400, oi_samples: 1443, ts_ms: 1789905483000, age_ms: 478 },
        { venue: 'okx', label: 'OKX', instrument: 'BTC-USDT-SWAP', ok: false,
          error: 'OKX did not answer \u2014 the venue is rate-limiting this machine (HTTP 429)',
          reason: 'the venue is rate-limiting this machine (HTTP 429)', notes: [], funding_rate: null,
          funding_interval_h: 8, funding_apr_pct: null, next_funding_in_s: null, mark: null, index: null,
          basis_bps: null, basis_apr_pct: null, open_interest: null, open_interest_unit: '',
          open_interest_usd: null, oi_change_pct: null, oi_change_reason: 'no open-interest samples yet' },
        { venue: 'hyperliquid', label: 'Hyperliquid', instrument: 'BTC', ok: true, error: '',
          notes: ['Hyperliquid settles funding hourly',
                  'this venue\u2019s payload carries no timestamp, so the age of this row is unknown'],
          funding_rate: 0.0000125, funding_interval_h: 1, funding_apr_pct: 10.95, next_funding_in_s: null,
          mark: 80469, index: 80466, basis_bps: 0.3728, basis_apr_pct: 0.136,
          open_interest: 40478.48844, open_interest_unit: 'BTC',
          open_interest_usd: 3257263486.27, oi_change_pct: 4.1, oi_span_s: 86400, oi_samples: 1443 },
    ],
    errors: [{ venue: 'okx', label: 'OKX', reason: 'the venue is rate-limiting this machine (HTTP 429)' }],
    settings: { venues: ['bybit', 'binance', 'okx', 'hyperliquid'], refresh_s: 60, oi_window_s: 86400,
                crowded_apr_pct: 30, flat_apr_pct: 5, history_max: 2880 },
};

const REFUSAL = { ok: false, symbol: 'BTCUSDT', detail: 'no venue answered for BTCUSDT \u2014 Bybit: the venue could not be reached', error: 'no venue answered for BTCUSDT \u2014 Bybit: the venue could not be reached' };

/* ── the surface ─────────────────────────────────────────────────────────────────────────── */

check('the module exposes its whole surface', () => {
    for (const fn of ['esc', 'normalize', 'num', 'signed', 'fmtRate', 'fmtApr', 'fmtBps', 'fmtChange',
                      'fmtUsd', 'fmtCoin', 'fmtPrice', 'fmtIn', 'intervalText', 'spanText', 'fundingText',
                      'oiText', 'directionText', 'summaryText', 'verdictText', 'oiLine', 'notesText',
                      'stripHtml', 'rowHtml', 'rowsHtml', 'bannerFor', 'venueQuery', 'venueList',
                      'paint', 'refresh', 'setVenues', 'tick', 'wire', 'watch', 'chosenSymbol',
                      'chosenVenues', 'activeSymbol', 'state']) {
        assert.strictEqual(typeof D[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(D.VIEW, '.view[data-view="derivatives"]');
    assert.strictEqual(D.URL_BASE, '/api/atlas/derivatives/');
    assert.deepStrictEqual(D.VENUES, ['bybit', 'binance', 'okx', 'hyperliquid']);
});

/* ── numbers ─────────────────────────────────────────────────────────────────────────────── */

check('a funding rate keeps its sign and prints at three decimals', () => {
    assert.strictEqual(D.fmtRate(0.00006032), '+0.006%');
    assert.strictEqual(D.fmtRate(0.0001), '+0.010%');
    assert.strictEqual(D.fmtRate(-0.00012), '-0.012%');
    assert.strictEqual(D.fmtRate(0), '0.000%');
    assert.strictEqual(D.fmtRate(null), DASH);
    assert.strictEqual(D.fmtRate('nonsense'), DASH);
});

check('annualised figures read one decimal with the sign kept', () => {
    assert.strictEqual(D.fmtApr(6.605), '+6.6%/yr');
    assert.strictEqual(D.fmtApr(-17.5269), '-17.5%/yr');
    assert.strictEqual(D.fmtApr(0), '0.0%/yr');
    assert.strictEqual(D.fmtApr(undefined), DASH);
});

check('basis keeps two decimals — it lives in single bps', () => {
    assert.strictEqual(D.fmtBps(-5.529), '-5.53');
    assert.strictEqual(D.fmtBps(0.3728), '+0.37');
    assert.strictEqual(D.fmtBps(null), DASH);
});

check('open interest and notional read at one scale', () => {
    assert.strictEqual(D.fmtUsd(16477045523.85), '16.48B');
    assert.strictEqual(D.fmtUsd(-2500000), '-2.50M');
    assert.strictEqual(D.fmtUsd(1500), '1.50K');
    assert.strictEqual(D.fmtUsd(null), DASH);
    assert.strictEqual(D.fmtCoin(55420.091, 'BTC'), '55.42K BTC');
    assert.strictEqual(D.fmtCoin(40478.48844, 'BTC'), '40.48K BTC');
    assert.strictEqual(D.fmtCoin(12.5, ''), '12.50');
    assert.strictEqual(D.fmtCoin(null, 'BTC'), DASH);
});

check('prices keep enough decimals to see a tick', () => {
    assert.strictEqual(D.fmtPrice(80421.58), '80421.58');
    assert.strictEqual(D.fmtPrice(0.00001234), '0.000012');
    assert.strictEqual(D.fmtPrice(null), DASH);
});

check('settlement spacing names its unit', () => {
    assert.strictEqual(D.intervalText(8), '8h');
    assert.strictEqual(D.intervalText(1), '1h');
    assert.strictEqual(D.intervalText(4.5), '4.5h');
    assert.strictEqual(D.intervalText(0.5), '30m');
    assert.strictEqual(D.intervalText(0), '');
    assert.strictEqual(D.intervalText(null), '');
});

check('the countdown to funding reads like a clock, and never goes negative', () => {
    assert.strictEqual(D.fmtIn(14516.5), '4 h 01 m');
    assert.strictEqual(D.fmtIn(95), '1 m 35 s');
    assert.strictEqual(D.fmtIn(30), '30 s');
    assert.strictEqual(D.fmtIn(-5), 'due now');
    assert.strictEqual(D.fmtIn(90000), '1 d 1 h');
    assert.strictEqual(D.fmtIn(null), DASH);
});

/* ── the sentence (the same rule the server applies) ─────────────────────────────────────── */

check('the funding half of the sentence carries rate, settlement and the year', () => {
    assert.strictEqual(D.fundingText(PAYLOAD.funding), '+0.010%/8h (+10.9% annualised)');
    /* the year is the quoted venue's own figure, not the cross-venue median (T5-F01): 0.010%/8h
       annualises to 10.95%, while a 9.8684% median would read +9.9 — the sentence must not mix them */
    assert.strictEqual(D.fundingText({ available: true, median_pct: 0.01, median_interval_h: 8,
                                       rate_apr_pct: 10.95, median_apr_pct: 9.8684 }),
        '+0.010%/8h (+10.9% annualised)');
    assert.strictEqual(D.fundingText({ available: false }), 'funding is not known');
    assert.strictEqual(D.fundingText(null), 'funding is not known');
    /* an older server that sends no annualised figure still reads as a rate, with no invented year */
    assert.strictEqual(D.fundingText({ available: true, median_pct: 0.01, median_interval_h: 8 }),
        '+0.010%/8h');
});

check('the OI half names the window it really measured', () => {
    assert.strictEqual(D.oiText({ change_pct: 3.2, span_s: 86400, window_s: 86400 }), 'OI up 3.2% on the day');
    assert.strictEqual(D.oiText({ change_pct: -3.2, span_s: 86400, window_s: 86400 }), 'OI down 3.2% on the day');
    assert.strictEqual(D.oiText({ change_pct: 0.01, span_s: 86400, window_s: 86400 }), 'OI flat on the day');
    /* two hours watched is two hours CLAIMED — never "the day" */
    assert.strictEqual(D.oiText({ change_pct: 1.5, span_s: 7200, window_s: 86400 }), 'OI up 1.5% over the last 2 h');
    assert.strictEqual(D.oiText({ change_pct: 1.5, span_s: 1200, window_s: 86400 }), 'OI up 1.5% over the last 20 m');
    /* no measured span (the venue-median fallback): the number's own source is named, never "0 s" */
    assert.strictEqual(D.oiText({ change_pct: 4.1, span_s: null, window_s: 86400,
                                  change_source: 'the median of the venues that had a baseline' }),
        'OI up 4.1% (the median of the venues that had a baseline)');
    assert.strictEqual(D.spanText(null, 86400), '');
    assert.strictEqual(D.oiText({ change_pct: null, reason: 'only 12 s of samples so far' }),
        'the open-interest change not known yet (only 12 s of samples so far)');
    assert.strictEqual(D.oiText(null),
        'the open-interest change not known yet (the app has not watched long enough)');
});

check('who pays whom is stated plainly, and a crowded side is named', () => {
    const cfg = PAYLOAD.settings;
    assert.strictEqual(D.directionText({ direction: 'longs_pay' }, cfg), 'longs are paying to hold');
    assert.strictEqual(D.directionText({ direction: 'shorts_pay' }, cfg), 'shorts are paying to hold');
    assert.strictEqual(D.directionText({ direction: 'longs_pay', crowded_long: true }, cfg),
        'a crowded long: longs are paying to hold');
    assert.strictEqual(D.directionText({ direction: 'shorts_pay', crowded_short: true }, cfg),
        'a crowded short: shorts are paying to hold');
    assert.strictEqual(D.directionText({ direction: 'flat' }, cfg),
        'neither side is paying much (under 5% annualised)');
    assert.strictEqual(D.directionText({ direction: 'mixed' }, cfg),
        'the venues disagree about which side is paying');
});

check('the server\'s own sentence wins, and the rebuild is the same rule', () => {
    assert.strictEqual(D.summaryText(PAYLOAD), PAYLOAD.summary);
    const rebuilt = D.summaryText({ funding: PAYLOAD.funding, oi: PAYLOAD.oi, settings: PAYLOAD.settings });
    assert.strictEqual(rebuilt, PAYLOAD.summary, rebuilt);
    assert.strictEqual(D.summaryText({ funding: { available: false } }), '');
    assert.strictEqual(D.summaryText(null), '');
});

check('the verdict reads as the strip label', () => {
    assert.strictEqual(D.verdictText(PAYLOAD.funding), 'longs pay');
    assert.strictEqual(D.verdictText({ verdict: 'crowded short' }), 'crowded short');
    assert.strictEqual(D.verdictText(null), DASH);
});

/* ── refusals ───────────────────────────────────────────────────────────────────────────── */

check('a refusal prints the server\'s own sentence, never a generic one', () => {
    assert.deepStrictEqual(D.bannerFor(REFUSAL), { text: REFUSAL.detail, kind: 'warn' });
    assert.strictEqual(D.bannerFor(null).text, '');
    const partial = D.bannerFor(PAYLOAD);
    assert.strictEqual(partial.kind, 'warn');
    assert.strictEqual(partial.text, 'no answer from OKX: the venue is rate-limiting this machine (HTTP 429)');
    assert.strictEqual(D.bannerFor({ ok: true, venues: [], errors: [] }).text, '');
});

check('a refused payload produces no sentence and no fake numbers', () => {
    assert.strictEqual(D.summaryText(REFUSAL), '');
    assert.strictEqual(D.rowsHtml(null).indexOf('no venue has answered yet') >= 0, true);
    assert.strictEqual(D.oiLine(null), 'no venue answered with an open-interest figure');
    assert.strictEqual(D.oiLine({ available: true, total_usd: null, venues_usd: 0, change_pct: null,
        reason: 'no open-interest samples yet' }),
        'the change needs a baseline this app has not built yet');
});

check('a venue that did not answer keeps its row and loses its numbers', () => {
    const html = D.rowsHtml(PAYLOAD);
    assert(html.indexOf('OKX did not answer \u2014 the venue is rate-limiting this machine (HTTP 429)') >= 0, html);
    /* the down venue's own row carries no figures at all — no 0.00 pretending to be a flat rate */
    const start = html.indexOf('<tr class="dim">');
    const okxRow = html.slice(start, html.indexOf('<tr>', start));
    assert(okxRow.indexOf('+0.000%') < 0 && okxRow.indexOf('0.00') < 0, okxRow);
    assert.strictEqual((okxRow.match(/<td/g) || []).length, 2, okxRow);
});

/* ── the strip and the table ─────────────────────────────────────────────────────────────── */

check('the strip carries one chip per venue that answered, with its state', () => {
    const html = D.stripHtml(PAYLOAD.funding, PAYLOAD.settings);
    assert.strictEqual((html.match(/derivatives-chip/g) || []).length, 3, html);
    assert(html.indexOf('Bybit') >= 0 && html.indexOf('Hyperliquid') >= 0, html);
    assert(html.indexOf('+6.6%/yr') >= 0 && html.indexOf('+10.9%/yr') >= 0, html);
    /* the chip carries the venue's own rate and settlement, not just the yearly figure */
    assert(html.indexOf('+0.001%/1h') >= 0, html);
    assert.strictEqual(D.stripHtml({ per_venue: [] }, PAYLOAD.settings)
        .indexOf('no venue answered with a funding rate') >= 0, true);
});

check('a crowded or flat venue is visibly a different state', () => {
    /* The threshold rides the settings, the shape the server actually sends (§148 T5-F-04). */
    const crowdSettings = { flat_apr_pct: 5 };
    const crowded = D.stripHtml({ per_venue: [{ venue: 'bybit', label: 'Bybit', rate: 0.0009, interval_h: 8, apr_pct: 98.6 }],
        crowded: [{ venue: 'bybit', apr_pct: 98.6 }] }, crowdSettings);
    assert(crowded.indexOf('is-crowded') >= 0, crowded);
    const flat = D.stripHtml({ per_venue: [{ venue: 'bybit', label: 'Bybit', rate: 0.000002, interval_h: 8, apr_pct: 0.2 }],
        crowded: [] }, crowdSettings);
    assert(flat.indexOf('is-flat') >= 0, flat);
    const short = D.stripHtml({ per_venue: [{ venue: 'okx', label: 'OKX', rate: -0.0001, interval_h: 8, apr_pct: -10.95 }],
        crowded: [] }, crowdSettings);
    assert(short.indexOf('is-short') >= 0, short);
    /* with no settings at all there is no threshold: the chip keeps a rate-based state */
    const unknown = D.stripHtml({ per_venue: [{ venue: 'okx', label: 'OKX', rate: 0.000002, interval_h: 8, apr_pct: 0.2 }],
        crowded: [] }, null);
    assert(unknown.indexOf('is-flat') < 0 && unknown.indexOf('is-long') >= 0, unknown);
});

check('the table row prints every column the header promises', () => {
    const html = D.rowHtml(PAYLOAD.venues[0]);
    ['Bybit', '+0.006%', '+6.6%/yr', '4 h 01 m', '55.42K BTC', '+3.2%', '80421.58', '80466.07', '-5.53', '-2.0%/yr']
        .forEach((cell) => assert(html.indexOf(cell) >= 0, cell + ' missing from ' + html));
    assert.strictEqual((html.match(/<td/g) || []).length, 10, html);
});

check('a missing figure is a dash, never a zero', () => {
    const bare = D.rowHtml({ venue: 'okx', label: 'OKX', ok: true });
    assert((bare.match(/\u2014/g) || []).length >= 6, bare);
    assert.strictEqual(bare.indexOf('0.00'), -1, bare);
    assert(bare.indexOf('no baseline') >= 0, bare);
});

check('a venue string is text, never markup', () => {
    const hostile = { venue: 'x', label: '<img src=x onerror=alert(1)>', ok: true, instrument: '"><script>',
                      open_interest_unit: '<b>BTC</b>' };
    const html = D.rowHtml(hostile);
    assert.strictEqual(html.indexOf('<img'), -1, html);
    assert.strictEqual(html.indexOf('<script'), -1, html);
    assert(html.indexOf('&lt;img') >= 0, html);
    assert.strictEqual(D.esc('a & b "c" <d>'), 'a &amp; b &quot;c&quot; &lt;d&gt;');
    assert.strictEqual(D.esc(null), '');
    const note = { venue: 'bybit', label: 'Bybit', ok: true, notes: ['<b>hourly</b>'] };
    assert(D.rowHtml(note).indexOf('<b>hourly') === -1, D.rowHtml(note));
});

check('the notes line names the venue and repeats nothing', () => {
    const text = D.notesText(PAYLOAD);
    assert(text.indexOf('Hyperliquid: Hyperliquid settles funding hourly') >= 0, text);
    assert(text.indexOf('Binance: open interest in USD is computed') >= 0, text);
    assert.strictEqual(text.indexOf('a perp premium is not a yield') > 0, true, text);
    assert.strictEqual(D.notesText({ venues: [{ venue: 'a', notes: ['same'] }, { venue: 'b', notes: ['same'] }] }),
        'a: same', 'a repeated caveat is printed once');
    assert.strictEqual(D.notesText(null), '');
});

check('the OI read says where its number came from', () => {
    assert.strictEqual(D.oiTotalText(PAYLOAD.oi), '16.48B USD',
        'the cross-venue total is USD — a venue coin unit is not a label for the sum');
    assert.strictEqual(D.oiTotalText({ total_usd: null }), D.DASH);
    assert.strictEqual(D.oiTotalText(null), D.DASH);
    assert.strictEqual(D.oiLine(PAYLOAD.oi),
        '16.48B USD across 3 venues \u00b7 +3.2% on the day, from the summed open interest of the '
        + 'venues that publish USD');
    const partial = D.oiLine({ available: true, total_usd: 1000, venues_usd: 1, change_pct: -1.2,
        span_s: 3600, window_s: 86400, change_source: 'the median of the venues that had a baseline' });
    assert(partial.indexOf('1.00K USD across 1 venue') >= 0, partial);
    assert(partial.indexOf('-1.2% over the last 1 h') >= 0, partial);
});

/* ── inputs and requests ─────────────────────────────────────────────────────────────────── */

check('symbols and venue lists are normalized before they are used', () => {
    assert.strictEqual(D.normalize(' btcusdt '), 'BTCUSDT');
    assert.strictEqual(D.normalize(null), '');
    assert.deepStrictEqual(D.venueList('bybit, Binance  OKX'), ['bybit', 'binance', 'okx']);
    assert.deepStrictEqual(D.venueList(['SONIC', 'okx', '']), ['okx']);
    assert.deepStrictEqual(D.venueList(null), []);
    assert.strictEqual(D.num('3.5'), 3.5);
    assert.strictEqual(D.num(''), null);
    assert.strictEqual(D.num(Infinity), null);
});

check('the request carries the venue list and only asks for a refresh when it means it', () => {
    assert.strictEqual(D.venueQuery(['bybit', 'okx'], false), '?venues=bybit%2Cokx');
    assert.strictEqual(D.venueQuery(['bybit'], true), '?venues=bybit&refresh=1');
    assert.strictEqual(D.venueQuery([], true), '?refresh=1');
    assert.strictEqual(D.venueQuery(null, false), '');
});

/* ── the module's own rules ──────────────────────────────────────────────────────────────── */

check('every pure function survives a payload that is missing everything', () => {
    [{}, null, undefined, { venues: null, funding: null, oi: null, basis: null }].forEach((bad) => {
        D.summaryText(bad); D.stripHtml(bad); D.rowsHtml(bad); D.bannerFor(bad);
        D.notesText(bad); D.oiLine(bad); D.fundingText(bad); D.oiText(bad); D.directionText(bad, bad);
        D.verdictText(bad); D.rowHtml(bad);
    });
    assert.strictEqual(D.rowsHtml({ venues: [] }).indexOf('no venue has answered yet') >= 0, true);
});

check('one timer, registered with the pause registry, and only one', () => {
    assert.strictEqual((src.match(/setInterval\s*\(/g) || []).length, 1, 'one timer for the panel');
    assert(src.indexOf('OFAPPause.register') >= 0, 'the timer is handed to the pause registry');
    assert(src.indexOf('document.hidden') >= 0 && src.indexOf('OFAP_PAUSED') >= 0,
        'the tick also stands down while hidden or paused');
    assert.strictEqual(D.REFRESH_MS, 60000, 'the panel cadence is the slow number funding deserves');
});

check('a read-out reaches both a readonly input and a span', () => {
    const input = { value: '' };
    const span = { value: undefined, textContent: '' };
    delete span.value;
    D.put(input, '16.48B USD');
    D.put(span, '16.48B USD');
    assert.strictEqual(input.value, '16.48B USD');
    assert.strictEqual(span.textContent, '16.48B USD');
    const blank = { value: null };
    D.put(blank, 0);
    assert.strictEqual(blank.value, '0', 'a zero is a reading, not an empty cell');
    D.put(null, 'nowhere to put it');            /* a missing element is not an error */
    D.put(undefined, 'still fine');
});

check('every element id the panel asks for is prefixed and on the wiring list', () => {
    const literal = new Set();
    let match;
    const pattern = /el\('([A-Za-z0-9_]+)'\)/g;
    while ((match = pattern.exec(src)) !== null) literal.add(match[1]);
    /* The shell's own instrument select is the one id this panel reads that is not its own. */
    const SHELL = ['symbolSelect'];
    Array.from(literal).forEach((id) => {
        if (SHELL.indexOf(id) >= 0) return;
        assert(id.indexOf('derivatives') === 0, id + ' is not prefixed with the view name');
    });
    /* The three read tiles are painted from a field map, so they are checked by name instead. */
    const wanted = ['derivativesAt', 'derivativesBanner', 'derivativesBasis', 'derivativesCount',
                    'derivativesNotes', 'derivativesOiChange', 'derivativesOiNote', 'derivativesOiTotal',
                    'derivativesRefresh', 'derivativesRows', 'derivativesStrip', 'derivativesSub',
                    'derivativesSummary', 'derivativesSymbol', 'derivativesSymbolBox',
                    'derivativesTable', 'derivativesVenues', 'derivativesVenuesApply'];
    wanted.forEach((id) => {
        assert(src.indexOf(id) >= 0, id + ' is not in the module at all');
        assert(literal.has(id) || src.indexOf(id + ':') >= 0,
            id + ' is neither looked up nor painted — the wiring and the module disagree');
    });
    assert(literal.has('symbolSelect'), 'the panel follows the shell\'s instrument select');
    assert.strictEqual(wanted.length, 18, 'the wiring list changed — update the section markup with it');
});

check('the panel stores nothing, streams nothing and reaches for no engine verb', () => {
    ['localStorage', 'sessionStorage', 'indexedDB', 'WebSocket', 'EventSource', '/api/control/engine',
     'innerHTML = payload', 'eval('].forEach((bad) => {
        assert.strictEqual(src.indexOf(bad), -1, 'derivatives.js must not touch ' + bad);
    });
    /* both routes are written literally, which is what the UI audit resolves */
    assert(src.indexOf("'/api/atlas/derivatives/'") >= 0, 'the read path is literal');
    assert(src.indexOf("'/api/atlas/derivatives/venues'") >= 0, 'the venue POST path is literal');
});

check('the section it watches is scoped to its own view', () => {
    assert(src.indexOf("'.view[data-view=\"derivatives\"]'") >= 0, 'the view selector is scoped');
    assert.strictEqual(src.indexOf("querySelector('[data-view="), -1, 'an unscoped lookup hits the nav button');
    assert(src.indexOf('typeof window.api') >= 0, 'the api() guard names the shell helper, never itself');
});

console.log('derivatives selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
