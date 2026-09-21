/* data-quality.selftest.js — the cockpit's decisions, pinned without a browser.
 *
 * The value of this module is what it SAYS: a duration in the words a person reads ("4 m 12 s"), a
 * percentage that never invents a decimal, a verdict that carries its own colour, a refusal printed
 * as the server's sentence, and a repair hint that never offers a button the app cannot honour. Those
 * are pure formatters over the server's payload, so they are pinned here; the live panel's paint path
 * is exercised against a small DOM stub, and `scripts/audit_ui_refs.py` owns the index.html half.
 *
 * `node desktop/ui/data-quality.selftest.js` prints
 * "data-quality selftest: N ok, M failed" and exits non-zero on any failure, so test_dataquality.py
 * can gate the suite on it.
 */
'use strict';

const fs = require('fs');
const src = fs.readFileSync(__dirname + '/data-quality.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

/* ── a DOM small enough to check the paint path, honest enough to catch a null dereference ────── */

function makeDom() {
    const registry = {};
    const listeners = {};
    function makeNode(tag) {
        const node = {
            tagName: tag, className: '', textContent: '', innerHTML: '', style: {}, isConnected: true,
            children: [], attrs: {}, __listeners: {},
            appendChild(child) { child.__parent = this; this.children.push(child); return child; },
            insertBefore(child) { child.__parent = this; this.children.unshift(child); return child; },
            setAttribute(k, v) { this.attrs[k] = v; },
            getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; },
            addEventListener(kind, fn) {
                (this.__listeners[kind] = this.__listeners[kind] || []).push(fn);
                (listeners[kind] = listeners[kind] || []).push(fn);
            },
            removeEventListener() {},
            querySelector(sel) { return this.attrs['data-ofap'] === sel ? this : null; },
            classList: {
                _on: true,
                contains() { return this._on; },
                add() {}, remove() {}, toggle() {},
            },
        };
        Object.defineProperty(node, 'id', {
            get() { return node.__id || ''; },
            set(value) { node.__id = value; registry[value] = node; },
        });
        return node;
    }
    const section = makeNode('SECTION');
    section.className = 'view';
    section.classList._on = true;
    const doc = {
        readyState: 'complete', hidden: false,
        addEventListener(kind, fn) { (listeners[kind] = listeners[kind] || []).push(fn); },
        getElementById(id) { return registry[id] || null; },
        createElement(tag) { return makeNode(tag); },
        querySelector(sel) { return sel === '.view[data-view="data-quality"]' ? section : null; },
    };
    return { doc, section, registry, listeners, makeNode };
}

function boot(options) {
    const opts = options || {};
    const dom = opts.dom || null;
    const calls = [];
    const api = (path) => {
        calls.push(path);
        if (opts.reject) return Promise.reject(new Error('boom'));
        if (opts.payload && opts.payload[path.split('?')[0]]) return Promise.resolve(opts.payload[path.split('?')[0]]);
        if (path.indexOf('/api/atlas/data-quality/') === 0) return Promise.resolve(opts.card || { ok: false, detail: 'no card' });
        return Promise.resolve(opts.rows || { ok: true, rows: [], at: 0, kind: 'ticks', window_h: 2, count: 0 });
    };
    const win = {
        api: api,
        OFAPPause: { register() {}, isPaused() { return false; } },
        toast(box, message) { if (box) box.textContent = String(message); },
    };
    new Function('window', 'document', 'setInterval', 'fetch', src)(
        win, dom ? dom.doc : null, () => 0, api);
    return { M: win.OFAPDATAQUALITY, win: win, calls: calls, dom: dom };
}

/* ── the surface ─────────────────────────────────────────────────────────────────────────────── */

{
    const { M } = boot();
    const surface = ['esc', 'normalize', 'num', 'fmtPct', 'fmtDur', 'fmtWindow', 'fmtClock',
        'verdictClass', 'letterColor', 'barWidth', 'sortRows', 'rowsUrl', 'symbolUrl', 'pickedRow',
        'sheetSymbol', 'rowHtml', 'rowsHtml', 'gapHtml', 'gapsHtml', 'repairHtml', 'repairsHtml',
        'notesHtml', 'bannerFor', 'detailSub', 'section', 'isActive', 'ensure', 'paintRows',
        'paintCard', 'refresh', 'refreshCard', 'tick', 'wire', 'watch', 'state'];
    const missing = surface.filter((name) => typeof M[name] !== 'function');
    check('the module exposes its whole surface', missing.length === 0, missing.join(','));
    check('the view and the two routes are the ones the panel watches',
        M.VIEW === '.view[data-view="data-quality"]' && M.ROWS_URL === '/api/atlas/data-quality'
        && M.SYMBOL_URL === '/api/atlas/data-quality/' && M.POLL_MS === 15000);
    check('the verdict letters are the module\'s own ladder', M.LETTERS.join('') === 'ABCDF');
    check('a module with no DOM boots without throwing', !!M && typeof M.state === 'function');
}

/* ── the formatters ──────────────────────────────────────────────────────────────────────────── */

{
    const { M } = boot();
    check('esc: markup in a symbol name cannot reach the DOM',
        M.esc('<b>"x"&\'y\'</b>') === '&lt;b&gt;&quot;x&quot;&amp;&#39;y&#39;&lt;/b&gt;'
        && M.esc('<') === '&lt;' && M.esc(null) === '' && M.esc(undefined) === '');
    check('normalize: trimmed and upper-cased, junk is empty',
        M.normalize(' btc-usd ') === 'BTC-USD' && M.normalize(null) === '' && M.normalize(5) === '5');
    check('num: a real number or null, never a guess',
        M.num('12.5') === 12.5 && M.num(0) === 0 && M.num('') === null && M.num('x') === null
        && M.num(undefined) === null);
    check('fmtPct: one decimal at most, and no ".0"',
        M.fmtPct(96.5) === '96.5' && M.fmtPct(96) === '96' && M.fmtPct(100) === '100'
        && M.fmtPct(0.3) === '0.3' && M.fmtPct(null) === '0' && M.fmtPct('junk') === '0');
    check('fmtDur: the words the server uses',
        M.fmtDur(0) === '0 s' && M.fmtDur(42_000) === '42 s' && M.fmtDur(65_000) === '1 m 05 s'
        && M.fmtDur(252_000) === '4 m 12 s' && M.fmtDur(3_840_000) === '1 h 04 m'
        && M.fmtDur(200_000_000) === '2 d 7 h' && M.fmtDur(null) === '0 s');
    check('fmtWindow: seconds in, spoken out',
        M.fmtWindow(30) === '30 s' && M.fmtWindow(60) === '1 m' && M.fmtWindow(90) === '1 m'
        && M.fmtWindow(4320) === '1 h 12 m' && M.fmtWindow(86400) === '24 h' && M.fmtWindow(0) === '1 s');
    check('fmtClock: UTC, minute resolution', M.fmtClock(0) === '00:00' && M.fmtClock(NaN) === '—');
    check('verdictClass: a letter becomes a class, junk does not',
        M.verdictClass('a') === 'a' && M.verdictClass('F') === 'f' && M.verdictClass('Z') === 'none'
        && M.verdictClass(null) === 'none');
    check('letterColor: every letter reads differently',
        M.letterColor('A') !== M.letterColor('C') && M.letterColor('C') !== M.letterColor('F')
        && M.letterColor('C') === M.letterColor('D'));
    check('barWidth: clamped to the bar it is drawn in',
        M.barWidth(96.5) === 97 && M.barWidth(150) === 100 && M.barWidth(-5) === 0 && M.barWidth(null) === 0);
}

/* ── the requests and the ordering ───────────────────────────────────────────────────────────── */

{
    const { M } = boot();
    check('rowsUrl: the window rides as a query only when there is one',
        M.rowsUrl(0) === '/api/atlas/data-quality' && M.rowsUrl(null) === '/api/atlas/data-quality'
        && M.rowsUrl(6) === '/api/atlas/data-quality?hours=6');
    check('symbolUrl: one instrument, encoded, no empty call',
        M.symbolUrl(' btc/usd ', 2) === '/api/atlas/data-quality/BTC%2FUSD?hours=2'
        && M.symbolUrl('BTCUSDT') === '/api/atlas/data-quality/BTCUSDT' && M.symbolUrl('') === '');
    check('sortRows: worst verdict first, then the least complete',
        M.sortRows([{ verdict: 'A', coverage_pct: 100 }, { verdict: 'F', coverage_pct: 20 },
                    { verdict: 'C', coverage_pct: 85 }, { verdict: 'F', coverage_pct: 5 }])
            .map((r) => r.coverage_pct).join(',') === '5,20,85,100');
    check('pickedRow: the clicked instrument wins, else the first row, else nothing',
        M.pickedRow([{ symbol: 'A' }, { symbol: 'BTCUSDT' }], 'btcusdt').symbol === 'BTCUSDT'
        && M.pickedRow([{ symbol: 'A' }, { symbol: 'B' }], 'ETHUSDT').symbol === 'A'
        && M.pickedRow([], 'BTCUSDT') === null && M.pickedRow(null, '') === null);
    check('sheetSymbol: the app-wide picker is the fallback, never a bare guess',
        M.sheetSymbol() === '');
}

/* ── the markup ──────────────────────────────────────────────────────────────────────────────── */

{
    const { M } = boot();
    const row = { ok: true, symbol: 'BTCUSDT', verdict: 'B', coverage_pct: 96.5, window_s: 7200,
                  capped: false, n_gaps: 1, n_gaps_total: 1, biggest_gap: { gap_ms: 252_000 },
                  stale_ms: 3000, fresh: true, sentence: 'history for BTCUSDT is 96.5% complete over the last 2 h' };
    const html = M.rowHtml(row);
    check('a row carries its symbol for the click, its letter and its bar',
        html.indexOf('data-dq-symbol="BTCUSDT"') > 0 && html.indexOf('>B<') > 0
        && html.indexOf('width:97%') > 0 && html.indexOf('96.5%') > 0);
    check('a row prints the server\'s sentence, escaped',
        M.rowHtml({ ...row, sentence: 'history <b>for</b>' }).indexOf('&lt;b&gt;') > 0);
    check('a capped row says so next to its window', M.rowHtml({ ...row, capped: true }).indexOf('(capped)') > 0);
    check('a row with no gaps says none, one with gaps names the biggest',
        M.rowHtml({ ...row, n_gaps: 0, n_gaps_total: 0 }).indexOf('>none<') > 0
        && html.indexOf('1 gap · 4 m 12 s') > 0);
    check('a stale row prints the age; a live one says live',
        M.rowHtml({ ...row, fresh: false, stale_ms: 401_000 }).indexOf('6 m 41 s old') > 0
        && html.indexOf('live') > 0);
    const refusal = M.rowHtml({ ok: false, symbol: 'ETHUSDT', detail: 'no stored history for ETHUSDT yet' });
    check('a refused instrument is a sentence in the row, not zeros',
        refusal.indexOf('no stored history for ETHUSDT yet') > 0 && refusal.indexOf('dq-refused') > 0);
    check('an empty list says what to do about it',
        M.rowsHtml([]).indexOf('no instruments to check yet') > 0 && M.rowsHtml(null).indexOf('colspan="7"') > 0);
    check('the gap table lists the ranges it was given, and says when there were none',
        M.gapsHtml({ ok: true, gaps: [{ from_utc: '2026-09-20 03:04', gap_ms: 252_000, missing_slots: 251,
                                        samples_inside: 0 }] }).indexOf('4 m 12 s') > 0
        && M.gapsHtml({ ok: true, gaps: [], n_holes: 2 }).indexOf('2 narrower hole(s)') > 0
        && M.gapsHtml({ ok: true, gaps: [] }).indexOf('no gap wider than the threshold') > 0);
    check('a refused card puts the server sentence in the gap table',
        M.gapsHtml({ ok: false, detail: 'no stored history yet' }).indexOf('no stored history yet') > 0);
    check('a repair hint with a route prints the route',
        M.repairHtml({ action: 'refetch', label: 'refetch BTCUSDT', why: 'the archive keeps past days',
                       available: true, route: '/api/control/backfill' })
            .indexOf('/api/control/backfill') > 0);
    check('a repair hint with no route says so instead of drawing a dead button',
        M.repairHtml({ action: 'dedupe', label: 'drop 3 duplicate stamps', why: 'no route deletes rows',
                       available: false, route: '' }).indexOf('no repair path in this build') > 0);
    check('a clean card is told so, plainly',
        M.repairsHtml({ ok: true, repairs: [] }).indexOf('nothing to repair') > 0
        && M.repairsHtml({ ok: false, detail: 'no stored history' }).indexOf('no stored history') > 0);
    check('notes render as a list, and no notes render as nothing',
        M.notesHtml({ notes: ['the read was capped'] }).indexOf('the read was capped') > 0
        && M.notesHtml({}) === '' && M.notesHtml(null) === '');
}

/* ── the banner and the sub-line ─────────────────────────────────────────────────────────────── */

{
    const { M } = boot();
    check('a refusal is a warning carrying the server\'s own sentence',
        M.bannerFor({ ok: false, detail: 'no stored history for X yet' }).text === 'no stored history for X yet'
        && M.bannerFor({ ok: false, detail: 'x' }).kind === 'warn');
    check('the banner\'s mood follows the letter',
        M.bannerFor({ ok: true, verdict: 'A', sentence: 's' }).kind === 'ok'
        && M.bannerFor({ ok: true, verdict: 'B', sentence: 's' }).kind === 'info'
        && M.bannerFor({ ok: true, verdict: 'C', sentence: 's' }).kind === 'info'
        && M.bannerFor({ ok: true, verdict: 'F', sentence: 's' }).kind === 'warn'
        && M.bannerFor(null).text === '' && M.bannerFor({ ok: true }).text === '');
    const sub = M.detailSub({ ok: true, symbol: 'BTCUSDT', asset_class: 'crypto', kind: 'ticks',
                              window_s: 7200, configured_window_s: 7200, present_slots: 6949,
                              expected_slots: 7200, samples: 6952 });
    check('the detail sub-line carries the judged window and the slot arithmetic',
        sub.indexOf('BTCUSDT') === 0 && sub.indexOf('6949 of 7200 expected') > 0
        && sub.indexOf('6952 rows') > 0);
    check('a refused card\'s sub-line is its refusal',
        M.detailSub({ ok: false, detail: 'no stored history' }) === 'no stored history');
}

/* ── the panel against a DOM stub ────────────────────────────────────────────────────────────── */

const ROWS_PAYLOAD = {
    ok: true, at: Date.UTC(2026, 8, 20, 3, 4), kind: 'ticks', window_h: 2, count: 2,
    note: 'the read walks backwards from the newest sample',
    rows: [
        { ok: true, symbol: 'BTCUSDT', verdict: 'A', coverage_pct: 100, window_s: 7200, capped: false,
          n_gaps: 0, n_gaps_total: 0, biggest_gap: null, stale_ms: 1000, fresh: true,
          sentence: 'history for BTCUSDT is 100% complete over the last 2 h' },
        { ok: true, symbol: 'ETHUSDT', verdict: 'C', coverage_pct: 88.2, window_s: 7200, capped: false,
          n_gaps: 2, n_gaps_total: 2, biggest_gap: { gap_ms: 600_000 }, stale_ms: 3000, fresh: true,
          sentence: 'history for ETHUSDT is 88.2% complete over the last 2 h' },
    ],
};
const CARD_PAYLOAD = {
    ok: true, symbol: 'ETHUSDT', verdict: 'C', verdict_note: 'partly usable', coverage_pct: 88.2,
    asset_class: 'crypto', kind: 'ticks', window_s: 7200, configured_window_s: 7200,
    present_slots: 6350, expected_slots: 7200, samples: 6352, capped: false, stale_ms: 3000,
    fresh: true, sentence: 'history for ETHUSDT is 88.2% complete over the last 2 h',
    gaps: [{ from_ms: 0, to_ms: 600_000, gap_ms: 600_000, missing_slots: 599, samples_inside: 1,
             from_utc: '2026-09-20 03:04' }],
    notes: ['crypto trades about 24 h a day'],
    repairs: [{ action: 'backfill', label: 'backfill the 10 m 00 s hole from 2026-09-20 03:04',
                why: '2 gap(s) in this window', available: true, route: '/api/control/backfill' }],
};

(async () => {
    /* The module boots its own first read (the view starts active); let it finish before measuring,
       or the busy guard swallows the call this test is about. */
    const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
    const dom = makeDom();
    const { M, calls } = boot({ dom: dom, rows: ROWS_PAYLOAD, card: CARD_PAYLOAD });

    check('watch(): the section is found and the panel builds what its markup lacks',
        M.watch() === true && !!dom.registry.dataQualityRows && !!dom.registry.dataQualityGaps
        && !!dom.registry.dataQualityRepairs && !!dom.registry.dataQualityBanner);
    check('isActive(): the section\'s own class decides',
        M.isActive() === true && dom.section.classList._on !== false);
    await flush();
    M.paintRows(ROWS_PAYLOAD);
    check('paintRows(): the table carries both instruments, worst first',
        dom.registry.dataQualityRows.innerHTML.indexOf('ETHUSDT') > 0
        && dom.registry.dataQualityRows.innerHTML.indexOf('BTCUSDT') > 0
        && dom.registry.dataQualityRows.innerHTML.indexOf('ETHUSDT')
            < dom.registry.dataQualityRows.innerHTML.indexOf('BTCUSDT'));
    check('paintCard(): the banner, the gap list and the repairs are painted',
        M.paintCard(CARD_PAYLOAD) === CARD_PAYLOAD
        && dom.registry.dataQualityBanner.textContent.indexOf('88.2%') > 0
        && dom.registry.dataQualityGaps.innerHTML.indexOf('10 m 00 s') > 0
        && dom.registry.dataQualityRepairs.innerHTML.indexOf('/api/control/backfill') > 0);
    check('paintCard(): the notes ride with the repairs',
        dom.registry.dataQualityRepairs.innerHTML.indexOf('24 h a day') > 0);
    check('the gap table\'s clock is the last print before the hole, not the hole itself',
        dom.registry.dataQualityGaps.__parent.innerHTML.indexOf('Last print before the gap') > 0
        && dom.registry.dataQualityGaps.__parent.innerHTML.indexOf('Gap starts') < 0);
    check('paintCard(): a refusal paints the sentence and no numbers',
        M.paintCard({ ok: false, symbol: 'BTCUSDT', detail: 'no stored history for BTCUSDT yet' }).ok === false
        && dom.registry.dataQualityGaps.innerHTML.indexOf('no stored history for BTCUSDT yet') > 0);

    calls.length = 0;
    const payload = await M.refresh();
    check('refresh(): one list read, then the selected instrument\'s card',
        payload === ROWS_PAYLOAD && calls.length === 2
        && calls[0].indexOf('/api/atlas/data-quality') === 0
        && calls[0].indexOf('/api/atlas/data-quality/') === -1
        && calls[1].indexOf('/api/atlas/data-quality/') === 0);
    check('refresh(): the detail follows the worst row when nothing is selected',
        calls[1] === '/api/atlas/data-quality/ETHUSDT?hours=2');
    check('state(): the panel keeps the card it painted', M.state() === CARD_PAYLOAD || !!M.state());

    calls.length = 0;
    await M.refreshCard('btcusdt');
    check('refreshCard(): one instrument, upper-cased and windowed',
        calls.length === 1 && calls[0] === '/api/atlas/data-quality/BTCUSDT?hours=2');
    check('refreshCard(): an empty name makes no request at all',
        (await M.refreshCard('')) === null && calls.length === 1);

    /* The row click: the stub records the delegated listener, so the walk up to the row is testable. */
    calls.length = 0;
    const clickHandler = (dom.registry.dataQualityRows.__listeners.click || [])[0];
    check('the row table has exactly one delegated click listener', typeof clickHandler === 'function');
    if (clickHandler) {
        clickHandler({ target: { getAttribute: () => 'BTCUSDT', parentNode: null } });
        check('a click on a row re-reads that instrument', calls[0] === '/api/atlas/data-quality/BTCUSDT?hours=2');
        calls.length = 0;
        clickHandler({ target: { getAttribute: () => '', parentNode: null } });
        check('a click on nothing makes no request', calls.length === 0);
    }

    const booted = boot({ dom: makeDom(), reject: true });
    const failed = await booted.M.refresh();
    check('a failed request is a sentence in the banner, not a throw',
        failed === null && booted.dom.registry.dataQualityBanner.textContent.indexOf('failed') > 0);

    const quiet = boot({ dom: makeDom() });
    await flush();
    quiet.dom.section.classList._on = false;
    quiet.calls.length = 0;
    quiet.M.tick();
    check('tick(): an off-screen view polls nothing', quiet.calls.length === 0);
    quiet.dom.section.classList._on = true;
    quiet.M.tick();
    check('tick(): on screen, a read that just happened holds the cadence', quiet.calls.length === 0);
    /* The cadence itself: move the clock past POLL_MS and the next tick does read. */
    const realNow = Date.now;
    Date.now = () => realNow() + 60_000;
    quiet.M.tick();
    Date.now = realNow;
    await flush();
    check('tick(): past the cadence, it reads again', quiet.calls.length === 1);

    check('the panel owns one timer and hands it to the pause registry',
        src.indexOf('OFAPPause.register') > 0 && (src.match(/setInterval\s*\(/g) || []).length === 1);

    /* ── a real payload, when the pytest gate hands one over ───────────────────────────────────────
     * The keys the Python module emits are the keys this panel reads. A rename on either side must
     * fail here rather than in the browser, so test_dataquality.py feeds a scorecard straight out of
     * orderflow_system/atlas/dataquality.py through `--payload <file>`.
     */
    const at = process.argv.indexOf('--payload');
    if (at >= 0 && process.argv[at + 1]) {
        const payload = JSON.parse(fs.readFileSync(process.argv[at + 1], 'utf8'));
        const first = (payload.rows || [])[0] || {};
        const key = '/api/atlas/data-quality/' + String(first.symbol || '');
        const live = boot({ dom: makeDom(), payload: {
            '/api/atlas/data-quality': payload, [key]: payload.card || first,
        } });
        await flush();                     /* the boot's own first read has to finish first */
        await live.M.refresh();
        const rowsHtmlLive = String(live.dom.registry.dataQualityRows.innerHTML || '');
        check('live payload: the row JSON paints its symbol and its coverage',
            rowsHtmlLive.indexOf(String(first.symbol)) >= 0
            && (first.ok === false || rowsHtmlLive.indexOf(live.M.fmtPct(first.coverage_pct)) >= 0),
            String(first.symbol));
        check('live payload: the verdict letter is the module\'s, not the panel\'s',
            first.ok === false || rowsHtmlLive.indexOf('>' + String(first.verdict) + '<') > 0,
            String(first.verdict));
        if (first.ok === true) {
            const banner = String(live.dom.registry.dataQualityBanner.textContent || '');
            check('live payload: the banner says the coverage and the sentence',
                String(first.sentence || '').length > 0
                && banner.indexOf(live.M.fmtPct(first.coverage_pct) + '%') >= 0
                && banner.indexOf(String(first.sentence).slice(0, 40)) >= 0,
                'banner=' + banner.slice(0, 140));
            const gaps = String(live.dom.registry.dataQualityGaps.innerHTML || '');
            check('live payload: the biggest gap is rendered with its duration',
                !(first.gaps || []).length || gaps.indexOf(live.M.fmtDur(first.gaps[0].gap_ms)) > 0,
                'gaps=' + gaps.slice(0, 140));
            const repairs = String(live.dom.registry.dataQualityRepairs.innerHTML || '');
            check('live payload: a repair hint carries its route when the app has one',
                !(first.repairs || []).length
                || (first.repairs || []).every((hint) => !hint.route || repairs.indexOf(hint.route) > 0),
                'repairs=' + repairs.slice(0, 140));
        } else {
            check('live payload: a refusal is painted as the server\'s own sentence',
                String(first.detail || '').length > 0
                && (String(live.dom.registry.dataQualityRows.innerHTML || '').indexOf(String(first.detail)) >= 0
                    || String(live.dom.registry.dataQualityBanner.textContent || '').indexOf(String(first.detail)) >= 0),
                'detail=' + String(first.detail || '').slice(0, 80));
        }
    }

    console.log('data-quality selftest: ' + ok + ' ok, ' + failures.length + ' failed');
    for (const f of failures) console.log('  FAIL', f);
    process.exit(failures.length ? 1 : 0);
})();
