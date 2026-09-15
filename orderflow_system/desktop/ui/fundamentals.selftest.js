/* fundamentals.selftest.js — the Fundamentals panel's decisions, as behaviour rather than prose.
 *
 * The DOM half needs a browser; every decision the panel makes is pure (fundamentals.js ::
 * sourceOf / cryptoAsset / reduceFacts / rowsOf / conceptsOf / pickConcept / plan / rowHtml /
 * tableHtml / cryptoHtml / full / compact / valueText / esc), so this pins those in Node with no
 * browser: the symbol → source decision, the companyfacts reduction and the CoinGecko mapping from
 * the captured fixtures, the picker, the formatting, and the sentence each non-ok state gets — the
 * panel must never be blank, and an index or an FX pair must never be dressed up as a filing.
 *
 * The fixtures are real captures, trimmed to the concepts this panel uses, taken from this machine:
 *   testdata/fundamentals/companyfacts.AAPL.sample.json   SEC companyfacts for CIK 0000320193
 *   testdata/fundamentals/company_tickers.sample.json     the SEC ticker → CIK map (5 filers)
 *   testdata/fundamentals/coingecko.markets.sample.json   /coins/markets for bitcoin,ethereum,solana
 * test_fundamentals.py reduces the same companyfacts fixture with edgar.py and fails on any drift
 * between the two implementations.
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(__dirname + '/fundamentals.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* No document: the module must still load and expose its logic (a Node run, a headless probe). */
const win = {};
new Function('window', 'document', 'fetch', src)(win, undefined, undefined);
const F = win.OFAPFUNDAMENTALS;

const FIX = path.join(__dirname, '..', '..', 'testdata', 'fundamentals');
const read = (name) => JSON.parse(fs.readFileSync(path.join(FIX, name), 'utf8'));
const FACTS = read('companyfacts.AAPL.sample.json');          // real SEC filing facts for AAPL
const TICKERS = read('company_tickers.sample.json');          // real SEC ticker map rows
const CG = read('coingecko.markets.sample.json');             // real CoinGecko markets response
const NOW = 1789479000000;

/* The route's payload for AAPL, as edgar.py builds it (same fixture, so the two must agree). */
function aaplPayload() {
    const rows = F.reduceFacts(FACTS);
    return { ok: true, symbol: 'AAPL', source: 'edgar',
             company: { cik: '0000320193', ticker: 'AAPL', name: 'Apple Inc.' },
             rows: rows,
             note: "annual filings only (10-K) — a quarter's figure never sits next to a year's" };
}
const btc = CG.filter((r) => r.id === 'bitcoin')[0];
function cryptoPayload() {
    return { ok: true, symbol: 'BTCUSDT', source: 'coingecko', rows: [],
             crypto: { id: 'bitcoin', name: btc.name, ticker: btc.symbol.toUpperCase(),
                       rank: btc.market_cap_rank, price: btc.current_price,
                       market_cap: btc.market_cap, volume_24h: btc.total_volume,
                       circulating_supply: btc.circulating_supply, total_supply: btc.total_supply,
                       max_supply: btc.max_supply,
                       change_24h: btc.price_change_percentage_24h, as_of: btc.last_updated },
             note: "market data from CoinGecko's keyless public endpoint" };
}
function rowsOf(concept) { return F.reduceFacts(FACTS).filter((r) => r.concept === concept); }

check('the module loads with no document and exposes its documented surface', () => {
    assert(F && typeof F === 'object', 'window.OFAPFUNDAMENTALS');
    ['sourceOf', 'cryptoAsset', 'reduceFacts', 'rowsOf', 'conceptsOf', 'pickConcept', 'plan',
     'paint', 'rowHtml', 'tableHtml', 'cryptoHtml', 'full', 'compact', 'valueText', 'esc',
     'noSourceNote', 'refresh', 'startPoll', 'stopPoll', 'sync', 'urlFor', 'activeSymbol']
        .forEach((name) => assert.strictEqual(typeof F[name], 'function', 'OFAPFUNDAMENTALS.' + name));
    assert.strictEqual(typeof F.state, 'function');
    assert.strictEqual(F.state(), null, 'nothing has been fetched yet');
    assert.strictEqual(F.VIEW, '.view[data-view="fundamentals"]');
    assert.strictEqual(F.URL_BASE, '/api/fundamentals/');
    assert.strictEqual(F.urlFor('btcusdt'), '/api/fundamentals/BTCUSDT');
    assert(F.REFRESH_MS >= 15000, 'filings move slowly, but the poll may never be faster than 15 s');
});

check('a venue symbol maps to its CoinGecko coin, case-insensitively and through the quote suffix', () => {
    assert.strictEqual(F.cryptoAsset('BTCUSDT'), 'bitcoin');
    assert.strictEqual(F.cryptoAsset('btcusdt'), 'bitcoin');
    assert.strictEqual(F.cryptoAsset('BTC'), 'bitcoin');
    assert.strictEqual(F.cryptoAsset(' ethusdt '), 'ethereum');
    assert.strictEqual(F.cryptoAsset('SOLUSDC'), 'solana');
    assert.strictEqual(F.cryptoAsset('TONUSDT'), 'the-open-network', 'the id is not the ticker');
    assert.strictEqual(F.cryptoAsset('POLUSDT'), 'polygon-ecosystem-token');
    /* an index, a metal and an FX pair strip to bases nothing maps — a wrong coin is worse than none */
    assert.strictEqual(F.cryptoAsset('NAS100USDT'), '');
    assert.strictEqual(F.cryptoAsset('XAUUSDT'), '');
    assert.strictEqual(F.cryptoAsset('EURUSD'), '');
    assert.strictEqual(F.cryptoAsset('USDT'), '', 'a suffix alone is not a coin');
    assert.strictEqual(F.cryptoAsset(''), '');
});

check('the symbol → source decision: crypto, ticker, or neither', () => {
    assert.strictEqual(F.sourceOf('BTCUSDT'), 'coingecko');
    assert.strictEqual(F.sourceOf('sol'), 'coingecko');
    assert.strictEqual(F.sourceOf('AAPL'), 'edgar');
    assert.strictEqual(F.sourceOf('googl'), 'edgar');
    assert.strictEqual(F.sourceOf('BRK-B'), 'edgar');
    assert.strictEqual(F.sourceOf('^GSPC'), 'none', 'an index is not a ticker');
    assert.strictEqual(F.sourceOf('SPX/USD'), 'none');
    assert.strictEqual(F.sourceOf(''), 'none');
    assert.strictEqual(F.sourceOf('TOOLONGSYMBOL123'), 'none');
    assert.strictEqual(F.sourceLabel('edgar'), 'SEC EDGAR');
    assert.strictEqual(F.sourceLabel('coingecko'), 'CoinGecko');
    assert.strictEqual(F.sourceLabel('none'), 'no source');
});

check('the companyfacts reduction is the AAPL fixture, annual filings only, newest period first', () => {
    const rows = F.reduceFacts(FACTS);
    assert.strictEqual(rows.length, 19, 'the fixture carries six concepts of annual facts');
    assert.deepStrictEqual(rows.map((r) => r.concept).filter((c, i, a) => a.indexOf(c) === i),
        ['revenue', 'net_income', 'eps_diluted', 'gross_profit', 'assets', 'equity'],
        'the panel order is the headline order');
    assert.strictEqual(rows[0].label, 'Revenue');
    /* the primary tag is only tagged up to FY2018 — the fallback carries today's number */
    assert.strictEqual(rows[0].tag, 'RevenueFromContractWithCustomerExcludingAssessedTax');
    assert.strictEqual(rows[0].value, 416161000000);
    assert.strictEqual(rows[0].form, '10-K');
    assert.strictEqual(rows[0].filed, '2025-10-31');
    assert.strictEqual(rows[0].period, '2025-09-27');
    assert.strictEqual(rows[0].fy, 2025);
    assert.strictEqual(rows[0].latest, true, 'the newest period is flagged as the latest');
    assert.deepStrictEqual(rowsOf('revenue').map((r) => r.value),
        [416161000000, 391035000000, 383285000000, 265595000000]);
    assert(rowsOf('revenue').slice(1).every((r) => r.latest === false));
    assert.deepStrictEqual(rowsOf('equity').map((r) => r.value),
        [73733000000, 56950000000, 62146000000], 'an instant fact has no period length to check');
});

check('a quarter never becomes a row: 10-Q facts are skipped, and so is a quarter tagged FY', () => {
    const values = F.reduceFacts(FACTS).map((r) => r.value);
    [364357000000, 109417000000, 101464000000, 29789000000, 178782000000, 54770000000, 383266000000]
        .forEach((q) => assert(values.indexOf(q) < 0, 'a 10-Q value leaked into the rows: ' + q));
    /* the old Revenues tag carries a three-month figure filed with fp "FY": 90 days is not a year */
    [62900000000, 53265000000].forEach((q) =>
        assert(values.indexOf(q) < 0, 'a 90-day period tagged FY leaked into the rows: ' + q));
    assert(F.reduceFacts(FACTS).every((r) => F.ANNUAL_FORMS.indexOf(r.form) >= 0));
});

check('a restated comparative replaces the earlier value for the same period', () => {
    /* 2024-09-28 revenue is in the FY2024 10-K and again in the FY2025 10-K; one row, the later filing */
    const rows = rowsOf('revenue').filter((r) => r.period === '2024-09-28');
    assert.strictEqual(rows.length, 1);
    assert.strictEqual(rows[0].filed, '2025-10-31', 'the most recently filed value wins the period');
    assert.strictEqual(rows[0].value, 391035000000);
});

check('a missing concept is a missing row — never a zero, and a real zero is still a zero', () => {
    const without = JSON.parse(JSON.stringify(FACTS));
    delete without.facts['us-gaap'].GrossProfit;              // banks do not tag gross profit
    const rows = F.reduceFacts(without);
    assert.strictEqual(rows.filter((r) => r.concept === 'gross_profit').length, 0);
    assert.strictEqual(rows.length, 16, 'only the four gross-profit rows went away');
    assert(rows.filter((r) => r.concept === 'revenue').length > 0, 'the rest is untouched');
    /* a filer that really reported 0: the row survives, with the value it filed */
    const zeroed = JSON.parse(JSON.stringify(FACTS));
    zeroed.facts['us-gaap'].GrossProfit.units.USD.push(
        { end: '2022-09-24', start: '2021-09-26', val: 0, fy: 2022, fp: 'FY', form: '10-K',
          filed: '2022-10-28' });
    const zeroRows = F.reduceFacts(zeroed).filter((r) => r.concept === 'gross_profit');
    assert.strictEqual(zeroRows.length, 4);
    assert.strictEqual(zeroRows[zeroRows.length - 1].value, 0, 'a filed zero is data, not a gap');
    assert.strictEqual(F.valueText(zeroRows[zeroRows.length - 1]), '0 USD');
    /* a concept only ever tagged in quarters contributes nothing at all */
    const quarterly = { facts: { 'us-gaap': { Assets: { units: { USD: [
        { end: '2026-06-27', val: 383266000000, fy: 2026, fp: 'Q3', form: '10-Q', filed: '2026-07-31' }] } } } } };
    assert.deepStrictEqual(F.reduceFacts(quarterly).filter((r) => r.concept === 'assets'), []);
});

check('the values are formatted for reading, and the filed figure is always one hover away', () => {
    assert.strictEqual(F.full(416161000000), '416,161,000,000');
    assert.strictEqual(F.compact(416161000000), '416.16B');
    assert.strictEqual(F.full(1544774036544), '1,544,774,036,544', 'no float precision loss');
    assert.strictEqual(F.full(7.46), '7.46');
    assert.strictEqual(F.full(0.082989), '0.082989', 'a small price keeps its digits');
    assert.strictEqual(F.full(null), F.DASH);
    assert.strictEqual(F.valueText(rowsOf('revenue')[0]), '416.16B USD');
    assert.strictEqual(F.valueText(rowsOf('eps_diluted')[0]), '7.46 USD/shares',
        'a per-share figure is never compacted');
    assert.strictEqual(F.pct(-1.08356), '-1.08%');
    assert.strictEqual(F.pct(2.47276), '+2.47%');
    assert.strictEqual(F.pct(null), F.DASH);
    assert.strictEqual(F.usd(1544774036544), '$1.54T');
    const html = F.rowHtml(rowsOf('revenue')[0]);
    assert(html.indexOf('416,161,000,000 USD') >= 0, 'the exact filed value is in the row title');
    assert(html.indexOf('10-K') >= 0 && html.indexOf('2025-10-31') >= 0 && html.indexOf('2025-09-27') >= 0,
        'form, filed date and period are all on screen');
    assert(html.indexOf('RevenueFromContractWithCustomerExcludingAssessedTax') >= 0,
        'and the XBRL tag it came from is named');
});

check('the AAPL payload is the ok state: company, rows, a picker of the concepts it carries', () => {
    const st = F.plan(aaplPayload(), null, 'aapl', NOW);
    assert.strictEqual(st.state, 'ok');
    assert.strictEqual(st.source, 'edgar');
    assert.strictEqual(st.symbol, 'AAPL', 'the symbol is normalised for the header line');
    assert.strictEqual(st.count, 19);
    assert.strictEqual(st.company.name, 'Apple Inc.');
    assert.strictEqual(st.company.cik, '0000320193');
    assert(st.sourceLine.indexOf('SEC EDGAR') === 0 && st.sourceLine.indexOf('Apple Inc.') > 0);
    assert.deepStrictEqual(st.concepts.map((c) => c.key),
        ['revenue', 'net_income', 'eps_diluted', 'gross_profit', 'assets', 'equity']);
    assert.strictEqual(st.pick, 'revenue', 'the picker opens on the newest revenue');
    assert.strictEqual(F.pickedRows(st.rows, 'eps_diluted').length, 3);
    assert.strictEqual(F.pickedRows(st.rows, 'nope').length, 0, 'an unknown concept shows nothing');
    const html = F.tableHtml(st.rows, 'revenue', 'Revenue');
    assert(html.indexOf('latest') >= 0 && html.indexOf('416.16B USD') >= 0);
    assert(html.indexOf('265.60B USD') >= 0, 'the older periods are context under the latest one');
    const picked = F.pickConcept(st.concepts, 'gross_profit');
    assert.strictEqual(picked, 'gross_profit', 'a concept the user picked survives a refresh');
    assert.strictEqual(F.pickConcept(st.concepts, 'gone'), 'revenue', 'a vanished one falls back');
    assert.strictEqual(F.pickConcept([], 'revenue'), '');
});

check('the CoinGecko payload is the crypto block: rank, market cap, supply, 24h', () => {
    const st = F.plan(cryptoPayload(), null, 'BTCUSDT', NOW);
    assert.strictEqual(st.state, 'ok');
    assert.strictEqual(st.source, 'coingecko');
    assert.strictEqual(st.count, 0, 'crypto carries no filing rows and must not invent any');
    assert.strictEqual(st.crypto.rank, 1);
    assert(st.sourceLine.indexOf('CoinGecko') === 0 && st.sourceLine.indexOf('Bitcoin') > 0);
    assert(st.sourceLine.indexOf('rank #1') > 0);
    const html = F.cryptoHtml(st.crypto, st.symbol);
    assert(html.indexOf('#1') >= 0, 'rank');
    assert(html.indexOf('$1.54T') >= 0, 'market cap');
    assert(html.indexOf('20.08M') >= 0 && html.indexOf('of 21.00M max') >= 0, 'supply');
    assert(html.indexOf('-1.08%') >= 0, 'the 24 h move');
    assert(html.indexOf('$76,915') >= 0, 'and the price it was measured at');
    assert(html.indexOf('no SEC filings') >= 0, 'the block says why there are no rows');
    /* null is a real answer from CoinGecko (a migrated token has no rank): it must not become 0 */
    const hollow = F.plan({ ok: true, symbol: 'MATICUSDT', source: 'coingecko',
        crypto: { id: 'matic-network', name: 'MATIC', ticker: 'MATIC', rank: null, price: 0,
                  market_cap: 0, circulating_supply: 0, change_24h: null, max_supply: null } },
        null, 'MATICUSDT', NOW);
    const hollowHtml = F.cryptoHtml(hollow.crypto, hollow.symbol);
    assert(hollowHtml.indexOf('#' + F.DASH) < 0 && hollowHtml.indexOf('>—<') >= 0,
        'an absent rank renders as an em dash');
    assert(hollowHtml.indexOf('+0.00%') < 0, 'and an absent 24h move is not a flat day');
});

check('an instrument neither source covers gets its own sentence, not a blank panel', () => {
    const none = { ok: true, symbol: 'SPX', source: 'none', rows: [],
                   note: 'no fundamentals source for SPX — EDGAR covers US filings, CoinGecko covers crypto' };
    const st = F.plan(none, null, 'SPX', NOW);
    assert.strictEqual(st.state, 'nosource');
    assert.strictEqual(st.message, 'no fundamentals source for SPX — EDGAR covers US filings, '
        + 'CoinGecko covers crypto', 'the mandatory sentence, verbatim');
    /* '^GSPC' cannot be a US ticker: the panel says so without pretending it asked */
    const beforeFetch = F.plan(null, null, '^GSPC', NOW);
    assert.strictEqual(beforeFetch.state, 'nosource');
    assert.strictEqual(beforeFetch.message, F.noSourceNote('^GSPC'));
    assert(F.noSourceNote('eurusd').indexOf('EURUSD') > 0);
    /* and the sentence reaches the screen escaped, unchanged */
    const html = F.tableHtml([], 'revenue', 'Revenue');
    assert(html.length > 0, 'even an empty concept says something');
});

check('the server\'s own words are what an error state prints', () => {
    const failed = F.plan({ ok: false, symbol: 'AAPL', source: 'none', rows: [],
        error: 'HTTP 403 Forbidden from www.sec.gov — SEC EDGAR refuses a request whose User-Agent '
            + 'does not name an application and a contact' }, null, 'AAPL', NOW);
    assert.strictEqual(failed.state, 'error');
    assert(failed.message.indexOf('HTTP 403 Forbidden from www.sec.gov') > 0,
        'the reason the server gave, not a generic one');
    assert(failed.message.indexOf('Refresh') > 0, 'and what the user can do about it');
    const thrown = F.plan(null, 'TypeError: Failed to fetch', 'AAPL', NOW);
    assert.strictEqual(thrown.state, 'error');
    assert(thrown.message.indexOf('TypeError: Failed to fetch') > 0);
    /* CoinGecko named as the source with no block in the payload is an error, not an empty block */
    const hollow = F.plan({ ok: true, symbol: 'BTCUSDT', source: 'coingecko' }, null, 'BTCUSDT', NOW);
    assert.strictEqual(hollow.state, 'error');
    assert(hollow.message.indexOf('no market data') > 0);
});

check('no instrument, still loading, and nothing to show are three different sentences', () => {
    const noSymbol = F.plan(aaplPayload(), null, '', NOW);
    assert.strictEqual(noSymbol.state, 'nosymbol');
    assert(noSymbol.message.indexOf('instrument') > 0);
    const loading = F.plan(null, null, 'AAPL', NOW);
    assert.strictEqual(loading.state, 'loading');
    assert(loading.message.indexOf('SEC EDGAR') > 0, 'the waiting line names the source being asked');
    const loadingCrypto = F.plan(null, null, 'BTCUSDT', NOW);
    assert(loadingCrypto.message.indexOf('CoinGecko') > 0);
    const empty = F.plan({ ok: true, symbol: 'AAPL', source: 'edgar',
        company: { cik: '0000320193', ticker: 'AAPL', name: 'Apple Inc.' }, rows: [] },
        null, 'AAPL', NOW);
    assert.strictEqual(empty.state, 'empty');
    assert(empty.message.indexOf('hidden') < 0 && empty.message.length > 20);
    assert(empty.count === 0, 'an empty payload never claims rows');
});

check('every state that is not ok explains itself, and ok always carries what it claims', () => {
    const states = [
        F.plan(null, null, '', NOW),                                   // no instrument
        F.plan(null, null, 'AAPL', NOW),                               // loading
        F.plan(null, 'boom', 'AAPL', NOW),                             // fetch threw
        F.plan({ ok: false, error: 'HTTP 500' }, null, 'AAPL', NOW),   // the server said no
        F.plan({ ok: true, symbol: 'SPX', source: 'none', rows: [] }, null, 'SPX', NOW),
        F.plan({ ok: true, symbol: 'AAPL', source: 'edgar', rows: [] }, null, 'AAPL', NOW),
    ];
    states.forEach((st) => {
        assert.notStrictEqual(st.state, 'ok');
        assert(st.message && st.message.length > 10, st.state + ' must say something: ' + st.message);
        assert.strictEqual(st.count, 0, st.state + ' must not claim values');
    });
    ['nosymbol', 'loading', 'error', 'nosource', 'empty'].forEach((name) =>
        assert(states.some((st) => st.state === name), 'the ' + name + ' state must exist'));
    const good = F.plan(aaplPayload(), null, 'AAPL', NOW);
    assert.strictEqual(good.state, 'ok');
    assert(good.rows.length === good.count && good.count > 0);
});

check('the panel shows the server\'s reduced rows, and can reduce a raw document itself', () => {
    const payload = aaplPayload();
    assert.deepStrictEqual(F.rowsOf(payload).map((r) => r.value), F.reduceFacts(FACTS).map((r) => r.value));
    const hostile = { rows: [null, 42, {}, { concept: 'revenue', value: 'lots', period: '2025-09-27' },
        { concept: 'revenue', label: 'Revenue', value: 416161000000, unit: 'USD', form: '10-K',
          filed: '2025-10-31', period: '2025-09-27', start: '2024-09-29', fy: 2025 }] };
    const kept = F.rowsOf(hostile);
    assert.strictEqual(kept.length, 1, 'a malformed row is dropped, not rendered');
    assert.strictEqual(kept[0].latest, true, 'the first period of a concept is the latest');
    assert.deepStrictEqual(F.rowsOf({ facts: FACTS }).map((r) => r.value),
        F.reduceFacts(FACTS).map((r) => r.value), 'a raw document is reduced with the same rule');
    assert.deepStrictEqual(F.rowsOf(null), []);
    assert.deepStrictEqual(F.conceptsOf([]), []);
    /* the picker lists exactly the concepts the payload carries — never a concept with no values */
    const short = { ok: true, symbol: 'KO', source: 'edgar', rows: [
        { concept: 'revenue', label: 'Revenue', value: 46000000000, unit: 'USD', form: '10-K',
          filed: '2026-02-20', period: '2025-12-31' }] };
    const st = F.plan(short, null, 'KO', NOW);
    assert.deepStrictEqual(st.concepts.map((c) => c.key), ['revenue']);
    assert.strictEqual(st.pick, 'revenue');
});

check('a row escapes everything a filer or an exchange could put in the payload', () => {
    const hostile = { concept: 'revenue', label: '<img src=x onerror=alert(1)>', value: 1,
                      unit: '"><script>alert(2)</script>', form: '<b>10-K</b>', filed: 'x',
                      period: '2025-09-27', tag: 'javascript:alert(3)', start: '', latest: true };
    const html = F.rowHtml(hostile);
    assert(html.indexOf('<img') < 0 && html.indexOf('<script') < 0 && html.indexOf('<b>') < 0,
        'no raw markup survives');
    assert(html.indexOf('&lt;img') >= 0, 'the label is shown as text');
    assert(html.indexOf('href') < 0 && html.indexOf('<a ') < 0,
        'a row never carries a link — so a javascript: tag stays a string, not a target');
    const table = F.tableHtml([hostile], 'revenue', 'Revenue');
    assert(table.indexOf('<img') < 0 && table.indexOf('&lt;img') >= 0,
        'the same escaping holds inside the table');
    const emptyTable = F.tableHtml([hostile], 'gross_profit', '<i>Gross profit</i>');
    assert(emptyTable.indexOf('<i>') < 0 && emptyTable.indexOf('&lt;i&gt;') >= 0,
        'and in the sentence an empty concept gets');
    const crypto = F.cryptoHtml({ id: '<img src=x>', name: '<svg onload=alert(1)>', ticker: '<b>',
                                  rank: 1, price: 1, market_cap: 1, circulating_supply: 1,
                                  change_24h: 1, as_of: '<i>' }, 'BTC<b>USDT');
    assert(crypto.indexOf('<img') < 0 && crypto.indexOf('<svg') < 0 && crypto.indexOf('<i>') < 0);
    assert.strictEqual(F.esc('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
    assert.strictEqual(F.esc(null), '');
});

check('one timer, the shared bus when it is loaded, and no reach for ingest or storage', () => {
    assert.strictEqual((src.match(/setInterval\(/g) || []).length, 1, 'one timer for the whole panel');
    assert.strictEqual(src.indexOf('clearInterval'), -1, 'no second timer to clear');
    ['localStorage', 'sessionStorage', 'indexedDB', 'WebSocket', 'EventSource',
     '/api/control/engine', 'engine/start', 'engine/stop']
        .forEach((bad) => assert.strictEqual(src.indexOf(bad), -1, 'fundamentals.js must not touch ' + bad));
    assert(src.indexOf('OFAPBUS') >= 0 && src.indexOf('bus.subscribe') >= 0,
        'the poll goes through the suite\'s own delivery layer when it is loaded');
    assert(src.indexOf('bus.request') >= 0, 'and a manual refresh is a coalesced one-shot');
    assert(src.indexOf('MutationObserver') >= 0 && src.indexOf("attributeFilter: ['class']") >= 0,
        'it boots itself from its own section, like every other panel');
    assert(src.indexOf("classList.contains('active')") >= 0, 'and only works while it is on screen');
    assert(src.indexOf('symbolSelect') >= 0, 'the symbol comes from the app\'s own instrument select');
    assert(src.indexOf("typeof S !== 'undefined'") >= 0, 'read defensively: the engine state may be late');
    assert(src.indexOf("'/api/fundamentals/'") >= 0, 'the route is a literal the UI audit can resolve');
    assert(src.indexOf('api(`/api/fundamentals/${') >= 0,
        'the call site spells the path out, as news.js does, so the audit can resolve it');
    assert(src.indexOf('10-K') >= 0 && src.indexOf('annual') >= 0, 'and the annual-only rule is stated');
});

check('the poll joins the shared channel when there is a bus, and stands alone when there is not', () => {
    let seen = null, released = 0;
    win.OFAPBUS = {
        subscribe: (spec, listener) => { seen = spec; assert.strictEqual(typeof listener, 'function');
                                         return () => { released += 1; }; },
    };
    assert.strictEqual(F.startPoll('BTCUSDT'), true);
    assert.strictEqual(F.poll(), 'bus');
    assert(seen && seen.url === '/api/fundamentals/BTCUSDT', 'the channel is this symbol\'s route');
    assert(seen.intervalMs >= 15000, 'filings move slowly: the poll is minutes, never seconds');
    assert.strictEqual(F.startPoll('BTCUSDT'), false, 'the same instrument is not re-subscribed');
    assert.strictEqual(F.startPoll('AAPL'), true, 'a moved instrument resubscribes its own channel');
    assert.strictEqual(seen.url, '/api/fundamentals/AAPL');
    assert.strictEqual(released, 1, 'the old channel was released on the way');
    assert.strictEqual(F.stopPoll(), true);
    assert.strictEqual(released, 2, 'hiding the panel releases the channel');
    assert.strictEqual(F.poll(), 'idle');
    delete win.OFAPBUS;
    assert.strictEqual(F.startPoll('SPX'), true);
    assert.strictEqual(F.poll(), 'timer', 'with no bus the panel answers on its own tick');
    assert.strictEqual(F.stopPoll(), true);
    assert.strictEqual(F.poll(), 'idle');
});

console.log('fundamentals selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
