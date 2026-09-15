/* options.selftest.js — the Options panel's decisions, as behaviour rather than prose.
 *
 * The DOM half needs a browser; every decision this panel makes is pure, so it is injected here into
 * a stub window + stub document (with a counting fetch, a counting timer and — for the poll checks —
 * the real bus.js) and pinned in Node. The payloads are the REAL ones: `fixtures/deribit/
 * chain_btc.json` is a live `GET /api/control/deribit/chain?symbol=BTCUSDT` reply captured on
 * 2026-09-15 (21 strike rows, 11 expiries, 41 tickers read), so what these checks describe is what
 * the panel actually renders.
 *
 * No browser, no network: nothing below reaches Deribit or the app.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/options.js', 'utf8');
const busSrc = fs.readFileSync(__dirname + '/bus.js', 'utf8');
const CHAIN = JSON.parse(fs.readFileSync(__dirname + '/../../fixtures/deribit/chain_btc.json', 'utf8'));

let ok = 0, failed = 0;
function check(name, fn) {
    return Promise.resolve().then(fn).then(() => { ok += 1; }, (e) => {
        failed += 1;
        console.log('  FAIL ' + name + ': ' + e.message);
    });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(cond, ms) {
    const deadline = Date.now() + (ms || 400);
    while (Date.now() < deadline) {
        if (cond()) return true;
        await sleep(5);
    }
    return !!cond();
}

/* ── the stub world ───────────────────────────────────────────────────────────────────────────── */

function makeClassList(active) {
    const set = {};
    if (active) set.active = true;
    return {
        contains: (name) => !!set[name],
        add: (name) => { set[name] = true; },
        remove: (name) => { delete set[name]; },
    };
}

function makeNode(id, extra) {
    const handlers = {};
    const node = {
        id: id || '', innerHTML: '', textContent: '', value: '', checked: true, disabled: false,
        options: [], dataset: {}, handlers, children: [],
        addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
        removeEventListener() {},
        dispatchEvent(ev) { (handlers[ev && ev.type] || []).forEach((fn) => fn(ev)); return true; },
        fire(type, ev) { (handlers[type] || []).forEach((fn) => fn(ev || { type: type, target: node })); return true; },
        querySelectorAll() { return []; },
        appendChild(child) { this.children.push(child); return child; },
        classList: makeClassList(false),
    };
    /* A real <select> turns its innerHTML into options; the stub does the same, so "never force a
       value the control cannot hold" is testable rather than assumed. */
    Object.defineProperty(node, 'innerHTML', {
        get() { return node.__html || ''; },
        set(html) {
            node.__html = String(html);
            const options = [];
            const pattern = /<option value="([^"]*)"/g;
            let match = pattern.exec(node.__html);
            while (match) { options.push({ value: match[1] }); match = pattern.exec(node.__html); }
            if (options.length) {
                node.options = options;
                if (!options.some((option) => option.value === node.value)) node.value = options[0].value;
            }
        },
    });
    return Object.assign(node, extra || {});
}

/* The server's own reply for the row the click tests pick: `GET /api/control/deribit/ticker?
 * instrument=BTC-16SEP26-77000-C`, captured live on 2026-09-15 — the FLATTENED shape the panel
 * parses (`mark`, `iv`, `delta`, …), not the venue's raw `mark_price`/`greeks` envelope. */
const TICKER = JSON.parse(fs.readFileSync(__dirname + '/../../fixtures/deribit/ticker_77000c_reply.json', 'utf8'));

function tickerReply(name) {
    return Object.assign({}, TICKER, { instrument: String(name) });
}

/* The stub's chain answer: the captured ladder, with the expiry the request asked for stamped on it
   — which is what the live server does (it draws the ladder for the expiry you name). */
function chainReply(url) {
    const asked = /[?&]expiry=([^&]+)/.exec(String(url));
    return asked ? Object.assign({}, CHAIN, { expiry: decodeURIComponent(asked[1]) }) : CHAIN;
}

function makeWorld(spec) {
    spec = spec || {};
    const nodes = {
        optionsBody: makeNode('optionsBody'),
        optionsCount: makeNode('optionsCount'),
        optionsSub: makeNode('optionsSub'),
        optionsDetail: makeNode('optionsDetail'),
        optionsExpiry: makeNode('optionsExpiry', { disabled: false }),
        optionsRefresh: makeNode('optionsRefresh'),
        optionsAuto: makeNode('optionsAuto', { checked: spec.auto !== false }),
        symbolSelect: makeNode('symbolSelect', {
            value: spec.symbol === undefined ? 'BTCUSDT' : spec.symbol,
            options: (spec.options || []).map((value) => ({ value: value })),
        }),
    };
    const section = makeNode('section', { dataset: { view: 'options' } });
    const doc = {
        readyState: 'complete',
        getElementById: (id) => nodes[id] || null,
        querySelector: (sel) => (sel === '.view[data-view="options"]' ? section : null),
        querySelectorAll: () => [],
        createElement: (tag) => makeNode('', { tagName: tag }),
        addEventListener: () => {},
        dispatchEvent: () => true,
        head: { appendChild: () => {} },
        body: makeNode('body'),
    };
    const world = {
        nodes, section, doc,
        asked: [], timers: [], cleared: [], observers: [],
        chain: spec.chain === undefined ? chainReply : spec.chain,
        ticker: spec.ticker === undefined ? tickerReply : spec.ticker,
        tickerFail: spec.tickerFail || '',
        activate() { section.classList.add('active'); },
        deactivate() { section.classList.remove('active'); },
        notify() { world.observers.forEach((o) => o.callback()); },
    };
    if (spec.active !== false) world.activate();

    const fakeFetch = (url) => {
        const text = String(url);
        world.asked.push(text);
        if (text.indexOf('/ticker') >= 0) {
            if (world.tickerFail) return Promise.reject(new Error(world.tickerFail));
            const name = decodeURIComponent((text.split('instrument=')[1] || '').split('&')[0]);
            const body = (typeof world.ticker === 'function') ? world.ticker(name) : world.ticker;
            return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
        }
        const body = (typeof world.chain === 'function') ? world.chain(text) : world.chain;
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    };
    const fakeSetInterval = (fn, ms) => {
        const timer = { fn: fn, ms: ms, cleared: false, fire() { return timer.cleared ? null : fn(); } };
        world.timers.push(timer);
        return timer;
    };
    const fakeClearInterval = (timer) => {
        if (timer) timer.cleared = true;                 /* a cleared timer really cannot fire */
        world.cleared.push(timer);
    };

    const win = {};
    if (spec.bus) {
        new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', busSrc)(
            win, doc, fakeFetch, setInterval, clearInterval);
    }
    const MutationObserverStub = function (callback) {
        this.callback = callback;
        this.observe = function () { world.observers.push(this); };
        this.disconnect = function () {};
    };
    new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', 'MutationObserver', src)(
        win, doc, fakeFetch, fakeSetInterval, fakeClearInterval, MutationObserverStub);
    world.win = win;
    return world;
}

/* No document at all: the pure layer must load and expose its decisions (a Node run, a headless probe). */
function bare() {
    const win = {};
    new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', 'MutationObserver', src)(
        win, undefined, () => Promise.reject(new Error('no fetch')), setInterval, clearInterval, undefined);
    return win.OFAPOPTIONS;
}

(async function run() {
    const api = bare();
    const NOW = 1789478700000;

    await check('the module loads with no document and exposes its documented surface', () => {
        assert(api, 'window.OFAPOPTIONS missing');
        ['esc', 'num', 'currencyFor', 'coverageSentence', 'expiriesFrom', 'sideOf', 'ladderFrom',
         'atmIndex', 'fmtStrike', 'fmtPrice', 'fmtPct', 'fmtGreek', 'fmtDelta', 'fmtSize', 'clockOf',
         'cacheKey', 'cacheGet', 'cachePut', 'cacheSize', 'cacheClear', 'plan', 'subText', 'headHtml',
         'rowHtml', 'sideCells', 'bodyHtml', 'detailHtml', 'render', 'syncSelect', 'state',
         'activeSymbol', 'paramsNow', 'urlNow', 'onChain', 'loadChain', 'loadTicker', 'getJson',
         'startPoll', 'stopPoll', 'sync', 'rekey', 'setExpiry', 'rowClick', 'bindControls',
         'injectStyles', 'boot', 'watch'].forEach((name) => {
            assert.strictEqual(typeof api[name], 'function', 'OFAPOPTIONS.' + name + ' must be a function');
        });
        assert.strictEqual(api.VERSION, '0.1.0');
        assert.strictEqual(api.CHAIN_URL, '/api/control/deribit/chain');
        assert.strictEqual(api.TICKER_URL, '/api/control/deribit/ticker');
        assert(api.INTERVAL_MS >= 10000, 'the auto-refresh must be modest: ' + api.INTERVAL_MS);
        assert(api.CACHE_MS > 0 && api.CACHE_MS < api.INTERVAL_MS, 'the cache is shorter than the poll');
        assert.strictEqual(api.DASH, '—', 'an absent field renders as an em dash');
        assert.strictEqual(api.state().plan, 'idle', 'nothing is fetched in a page with no panel');
        assert.strictEqual(api.activeSymbol(), '', 'with no app in reach there is no active symbol');
    });

    await check('the symbol mapper answers the table, and refuses a market with no chain', () => {
        const table = {
            BTCUSDT: 'BTC', btcusdt: 'BTC', BTCUSDC: 'BTC', ETHUSDT: 'ETH', ethusd: 'ETH',
            SOLUSDT: 'SOL', BTC: 'BTC', 'BTC-USD': 'BTC', 'BTC/USDT': 'BTC',
        };
        Object.keys(table).forEach((symbol) => {
            assert.strictEqual(api.currencyFor(symbol), table[symbol], symbol + ' → ' + table[symbol]);
        });
        ['ESZ6', 'EURUSD', 'NAS100USDT', 'SPX500', 'AAPL', 'NIFTY', '', '   ', null, undefined, 42]
            .forEach((symbol) => {
                assert.strictEqual(api.currencyFor(symbol), '',
                    JSON.stringify(symbol) + ' must map to nothing — it has no Deribit chain');
            });
    });

    await check('the live chain reply becomes the ok state, with its 11 expiries and 21 rows', () => {
        const st = api.plan(CHAIN, null, 'BTCUSDT', NOW, '');
        assert.strictEqual(st.state, 'ok', st.message);
        assert.strictEqual(st.currency, 'BTC');
        assert.strictEqual(st.expiry, '16SEP26', 'the server names the expiry it drew');
        assert.strictEqual(st.count, 21, 'the window is 21 strike rows');
        assert.strictEqual(st.expiries.length, 11);
        assert.strictEqual(st.rows[0].strike, 70000);
        assert.strictEqual(st.rows[st.rows.length - 1].strike, 83000);
        assert(st.forward > 1000, 'a real forward: ' + st.forward);
        assert.strictEqual(st.quoted, 42, 'every side in the window carried a quote');
        assert.strictEqual(st.tickerErrors, 0);
        assert(api.subText(st).indexOf('16SEP26') >= 0, api.subText(st));
    });

    await check('expiries are sorted by time, whatever order the reply used', () => {
        const shuffled = JSON.parse(JSON.stringify(CHAIN));
        shuffled.expiries = shuffled.expiries.slice().reverse().concat([null, 42, { code: '' }]);
        const list = api.expiriesFrom(shuffled);
        assert.strictEqual(list.length, 11, 'a code-less entry is not an expiry');
        for (let i = 1; i < list.length; i++) {
            assert(list[i].ms >= list[i - 1].ms, 'soonest first: ' + list.map((e) => e.code).join(','));
        }
        assert.strictEqual(list[0].code, '16SEP26');
        assert.strictEqual(list[0].label, '16 Sep 2026', 'the venue code is labelled as a date');
        assert.strictEqual(list[0].strikes, 26);
        assert.strictEqual(api.expiriesFrom(null).length, 0);
        assert.strictEqual(api.expiriesFrom({}).length, 0);
    });

    await check('the ladder is built from the reply, and a strike with no quote is not a zero', () => {
        const rows = api.ladderFrom(CHAIN);
        assert.strictEqual(rows.length, 21);
        assert.strictEqual(rows[0].call.instrument, 'BTC-16SEP26-70000-C');
        assert.strictEqual(rows[0].put.instrument, 'BTC-16SEP26-70000-P');
        assert.strictEqual(rows[0].call.iv, 87.68, 'the venue IV, verbatim');
        assert.strictEqual(rows[0].call.delta, 0.99072);
        assert.strictEqual(rows[0].call.oi, 9.8);
        const broken = api.ladderFrom({ strikes: [null, 42, { strike: 'x' }, { strike: 0 },
            { strike: 70000, call: { instrument: 'C' }, put: null }, { strike: 71000 }] });
        assert.strictEqual(broken.length, 2, 'only real strikes are rows: ' + broken.length);
        assert.strictEqual(broken[0].put, null, 'an unquoted side stays null');
        assert.strictEqual(broken[1].call, null);
        assert(api.rowHtml(broken[0], false).indexOf('no put quote listed') >= 0, 'and says so');
        assert.strictEqual(api.ladderFrom({}).length, 0);
        const rows2 = api.ladderFrom({ strikes: [{ strike: 71000 }, { strike: 70000 }] });
        assert.deepStrictEqual(rows2.map((r) => r.strike), [70000, 71000], 'ascending, always');
    });

    await check('the money row is the one nearest the forward', () => {
        const rows = api.ladderFrom(CHAIN);
        const at = api.atmIndex(rows, CHAIN.forward);
        assert.strictEqual(rows[at].strike, 77000, 'the forward 76918.1 sits on the 77000 row');
        assert.strictEqual(api.atmIndex(rows, 0), -1, 'no forward, no marked row');
        assert.strictEqual(api.atmIndex([], 100), -1);
        const html = api.bodyHtml(api.plan(CHAIN, null, 'BTCUSDT', NOW, ''));
        assert.strictEqual((html.match(/opt-atm/g) || []).length, 1, 'exactly one row is marked');
    });

    await check('greek, IV and size formatting', () => {
        assert.strictEqual(api.fmtPct(98.66), '98.66%');
        assert.strictEqual(api.fmtPct(0), '0.00%');
        assert.strictEqual(api.fmtPct(null), '—');
        assert.strictEqual(api.fmtDelta(0.99688), '+0.997');
        assert.strictEqual(api.fmtDelta(-0.51184), '-0.512');
        assert.strictEqual(api.fmtDelta(0), '0.000', 'a real zero delta keeps the column width');
        assert.strictEqual(api.fmtDelta(null), '—');
        assert.strictEqual(api.fmtGreek(-381.04863), '-381.0', 'a big theta keeps one decimal');
        /* measured: Deribit returns gamma 1e-05 on near-dated strikes, and '0.000' would state "no gamma"
           when the venue is saying "very small gamma" — non-zero smalls read as tiny, not as nothing */
        assert.strictEqual(api.fmtGreek(0.00021), '2.10e-4');
        assert.strictEqual(api.fmtGreek(1e-5), '1.00e-5');
        assert.strictEqual(api.fmtGreek(0), '0.000', 'an exact zero stays a zero');
        assert.strictEqual(api.fmtGreek(null), '—');
        assert.strictEqual(api.fmtPrice(0.114), '0.1140');
        assert.strictEqual(api.fmtPrice(0.0002), '0.000200');
        assert.strictEqual(api.fmtPrice(0), '0', 'a quoted zero is a fact, not a missing field');
        assert.strictEqual(api.fmtPrice('n/a'), '—');
        assert.strictEqual(api.fmtSize(7121), '7.1K');
        assert.strictEqual(api.fmtSize(287.8), '287.8');
        assert.strictEqual(api.fmtSize(0), '0');
        assert.strictEqual(api.fmtSize(null), '—');
        assert.strictEqual(api.fmtStrike(77000), '77,000');
        assert.strictEqual(api.fmtStrike(null), '—');
    });

    await check('no options feed for a symbol with no Deribit chain — stated, not fetched', async () => {
        const world = makeWorld({ symbol: 'ESZ6' });
        const panel = world.win.OFAPOPTIONS;
        await panel.loadChain();
        const st = panel.state();
        assert.strictEqual(st.plan, 'nocoverage');
        assert.strictEqual(st.currency, '');
        assert.strictEqual(world.asked.length, 0, 'no request is made for a market with no feed');
        const html = world.nodes.optionsBody.innerHTML;
        assert(html.indexOf('crypto only via Deribit — no options feed for ESZ6') >= 0, html);
        assert(html.indexOf('<table') < 0, 'and no ladder is invented');
        assert.strictEqual(panel.coverageSentence('NAS100USDT'),
            'crypto only via Deribit — no options feed for NAS100USDT — Deribit lists BTC and ETH option chains today (SOL is spot only)');
    });

    await check('a currency with no chain today quotes the server, verbatim', () => {
        const refused = { ok: false, coverage: false, currency: 'SOL', symbol: 'SOLUSDT',
            error: 'Deribit lists no SOL options right now (BTC and ETH carry chains today; SOL has spot only)' };
        const st = api.plan(refused, null, 'SOLUSDT', NOW, '');
        assert.strictEqual(st.state, 'nocoverage');
        assert(st.message.indexOf('Deribit lists no SOL options right now') >= 0, st.message);
        assert(api.bodyHtml(st).indexOf('no coverage') >= 0, 'and the row is tagged as such');
    });

    await check('a failed request and a refused chain are errors that carry the real words', () => {
        const thrown = api.plan(null, 'TypeError: Failed to fetch', 'BTCUSDT', NOW, '');
        assert.strictEqual(thrown.state, 'error');
        assert(/TypeError: Failed to fetch/.test(thrown.message), thrown.message);
        assert(thrown.count === 0);
        const refused = api.plan({ ok: false, coverage: true,
            error: 'Deribit chain unavailable: HTTP 400: instrument not found (instrument_name)' },
            null, 'BTCUSDT', NOW, '');
        assert.strictEqual(refused.state, 'error');
        assert(refused.message.indexOf('instrument not found (instrument_name)') >= 0,
            'the venue own reason reaches the screen: ' + refused.message);
        assert(api.bodyHtml(refused).indexOf('tag no') >= 0, 'an error row is an error row');
    });

    await check('loading, no instrument and an empty ladder each say something', () => {
        const loading = api.plan(null, null, 'BTCUSDT', NOW, '');
        assert.strictEqual(loading.state, 'loading');
        assert(/loading/.test(loading.message));
        const nosymbol = api.plan(CHAIN, null, '', NOW, '');
        assert.strictEqual(nosymbol.state, 'nosymbol');
        assert(nosymbol.message.indexOf('instrument') >= 0);
        const empty = api.plan({ ok: true, coverage: true, currency: 'BTC', expiry: '16SEP26',
            expiries: CHAIN.expiries, strikes: [], forward: 76931, note: '' }, null, 'BTCUSDT', NOW, '');
        assert.strictEqual(empty.state, 'empty');
        assert.strictEqual(empty.count, 0);
        assert(empty.message.indexOf('16SEP26') >= 0, empty.message);
        [loading, nosymbol, empty].forEach((st) => {
            assert(st.message.length > 10, st.state + ' must explain itself');
            assert.strictEqual(st.count, 0);
            assert.strictEqual(api.bodyHtml(st).indexOf('<table'), -1, st.state + ' draws no ladder');
        });
    });

    await check('the client-side cache expires on its own clock', () => {
        const T = 1000;                                    /* a fixed clock, so the TTL is exact */
        const key = api.cacheKey('BTCUSDT', '16SEP26', 10);
        assert.strictEqual(api.cacheGet(key, T), null, 'nothing cached yet');
        api.cachePut(key, { ok: true }, T);
        assert.deepStrictEqual(api.cacheGet(key, T + 1), { ok: true });
        assert.deepStrictEqual(api.cacheGet(key, T + api.CACHE_MS - 1), { ok: true }, 'still inside the TTL');
        assert.strictEqual(api.cacheGet(key, T + api.CACHE_MS), null, 'and gone at the TTL');
        assert.strictEqual(api.cacheSize(), 0, 'an expired entry is dropped, not kept');
        assert.notStrictEqual(api.cacheKey('BTCUSDT', '16SEP26', 10), api.cacheKey('BTCUSDT', '17SEP26', 10));
        assert.strictEqual(api.cacheClear(), 0);
    });

    await check('a payload inside the TTL is painted without touching the wire', async () => {
        const world = makeWorld({ active: false });
        const panel = world.win.OFAPOPTIONS;
        await panel.loadChain();
        assert.strictEqual(world.asked.length, 1, 'the first read is a request');
        assert.strictEqual(panel.state().rows, 21);
        await panel.loadChain();
        assert.strictEqual(world.asked.length, 1, 'the second, inside 10 s, is not');
        assert(world.nodes.optionsSub.textContent.indexOf('from the 10s cache') >= 0,
            'and the panel says where it came from: ' + world.nodes.optionsSub.textContent);
        await panel.loadChain({ force: true });
        assert.strictEqual(world.asked.length, 2, 'Refresh forces a read regardless');
        assert(world.nodes.optionsBody.innerHTML.indexOf('BTC-16SEP26-77000-C') >= 0, 'the ladder rendered');
        assert.strictEqual(world.nodes.optionsCount.textContent, '21');
    });

    await check('the shared bus carries the poll, and the expiry moves the channel with it', async () => {
        const world = makeWorld({ bus: true, active: false });
        const panel = world.win.OFAPOPTIONS;
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0, 'hidden: nothing is polled');
        assert.strictEqual(panel.state().polling, 'idle');
        world.activate();
        world.notify();
        assert(await until(() => panel.state().polling === 'bus' && world.asked.length >= 1),
            'becoming visible subscribes');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 1, 'one shared channel');
        assert.strictEqual(world.timers.length, 0, 'with a bus the panel owns no timer');
        const first = world.win.OFAPBUS.telemetry().rows[0].key;
        assert(first.indexOf('symbol=BTCUSDT') >= 0, first);
        panel.setExpiry('17SEP26');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 1,
            'the old channel went with the old expiry: ' + JSON.stringify(world.win.OFAPBUS.telemetry().rows));
        const second = world.win.OFAPBUS.telemetry().rows[0].key;
        assert(second.indexOf('expiry=17SEP26') >= 0, 'and the new one carries the pick: ' + second);
        assert(await until(() => world.nodes.optionsExpiry.value === '17SEP26'),
            'the control shows the pick the server answered with: ' + world.nodes.optionsExpiry.value);
        panel.stopPoll();
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0, 'the way out releases the channel');
        world.win.OFAPBUS.stopAll();
    });

    await check('with no bus the panel owns one timer, clears it, and asks for the expiry it shows', async () => {
        const world = makeWorld({ active: true });
        const panel = world.win.OFAPOPTIONS;
        assert(await until(() => panel.state().polling === 'timer' && panel.state().plan === 'ok'),
            'the panel polled and painted: ' + JSON.stringify(panel.state()));
        assert.strictEqual(world.timers.length, 1, 'one timer, whatever the row count');
        assert.strictEqual(world.timers[0].ms, panel.INTERVAL_MS);
        assert(world.asked[0].indexOf('/api/control/deribit/chain') >= 0, world.asked[0]);
        assert(world.nodes.optionsSub.textContent.indexOf('own timer') >= 0,
            'the panel admits it has no bus: ' + world.nodes.optionsSub.textContent);
        const before = world.asked.length;
        panel.setExpiry('25SEP26');
        assert(await until(() => world.asked.length > before), 'the pick is read');
        assert(world.asked[world.asked.length - 1].indexOf('expiry=25SEP26') >= 0,
            world.asked[world.asked.length - 1]);
        assert(await until(() => world.nodes.optionsSub.textContent.indexOf('25SEP26') >= 0),
            'the picked ladder landed: ' + world.nodes.optionsSub.textContent);
        const live = world.timers[world.timers.length - 1];
        live.fire();
        await sleep(20);
        assert.strictEqual(world.asked.length, before + 1,
            'a tick inside the 10 s TTL is answered by the cache, not by the wire');
        assert(world.nodes.optionsSub.textContent.indexOf('from the 10s cache') >= 0,
            world.nodes.optionsSub.textContent);
        panel.cacheClear();
        live.fire();
        assert(await until(() => world.asked.length > before + 1), 'and past the TTL it reads again');
        panel.stopPoll();
        assert.strictEqual(world.cleared[world.cleared.length - 1], live, 'the live timer is the one cleared');
        const settled = world.asked.length;
        live.fire();
        await sleep(20);
        assert.strictEqual(world.asked.length, settled, 'and a cleared timer cannot fire at all');
        world.nodes.optionsAuto.checked = false;
        world.nodes.optionsAuto.fire('change');
        assert.strictEqual(panel.state().polling, 'idle');
        assert(world.nodes.optionsSub.textContent.indexOf('auto-refresh off') >= 0,
            'the sub line says it: ' + world.nodes.optionsSub.textContent);
        world.nodes.optionsAuto.checked = true;
        world.nodes.optionsAuto.fire('change');
        assert.strictEqual(panel.state().polling, 'timer', 'a restored switch restores the poll');
    });

    await check('a market with no feed never starts a poll at all', async () => {
        const world = makeWorld({ symbol: 'EURUSD', active: false });
        const panel = world.win.OFAPOPTIONS;
        world.activate();
        world.notify();
        await sleep(20);
        assert.strictEqual(panel.state().polling, 'idle', 'nothing polls for a symbol with no chain');
        assert.strictEqual(world.timers.length, 0);
        assert.strictEqual(world.asked.length, 0);
        assert(world.nodes.optionsBody.innerHTML.indexOf('crypto only via Deribit') >= 0,
            world.nodes.optionsBody.innerHTML);
        world.deactivate();
        world.notify();
        assert(world.nodes.optionsSub.textContent.indexOf('paused') >= 0,
            'a hidden panel says it is not on screen: ' + world.nodes.optionsSub.textContent);
    });

    await check('switching the top bar to a market with no feed says so instead of loading for ever', async () => {
        const world = makeWorld({ bus: true, symbol: 'BTCUSDT' });
        const panel = world.win.OFAPOPTIONS;
        assert(await until(() => panel.state().plan === 'ok'), 'the crypto chain came up first');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 1);
        /* The defect this pins: with a bus the poll is what reads, and nothing polls for a symbol
           with no Deribit chain — so the panel used to sit on "Loading…" and never resolve. */
        world.nodes.symbolSelect.value = 'NAS100USDT';
        world.nodes.symbolSelect.fire('change');
        assert(await until(() => panel.state().plan === 'nocoverage'), 'it states it at once');
        assert.strictEqual(panel.state().currency, '');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0, 'and no channel is left running');
        assert(world.nodes.optionsBody.innerHTML.indexOf('crypto only via Deribit — no options feed for NAS100USDT') >= 0,
            world.nodes.optionsBody.innerHTML);
        assert(world.nodes.optionsSub.textContent.indexOf('NAS100USDT') >= 0
            || world.nodes.optionsSub.textContent.indexOf('no options feed') >= 0,
            world.nodes.optionsSub.textContent);
        world.nodes.symbolSelect.value = 'BTCUSDT';
        world.nodes.symbolSelect.fire('change');
        assert(await until(() => panel.state().plan === 'ok' && panel.state().rows === 21),
            'and going back to a crypto symbol reads again: ' + JSON.stringify(panel.state()));
    });

    await check('picking a row reads that one contract, and its refusal is shown verbatim', async () => {
        const world = makeWorld({ active: false });
        const panel = world.win.OFAPOPTIONS;
        await panel.loadChain();
        const cell = { target: { closest: () => ({ dataset: { instrument: 'BTC-16SEP26-77000-C' } }) } };
        assert.strictEqual(panel.rowClick(cell), true);
        assert(await until(() => world.nodes.optionsDetail.innerHTML.indexOf('Δ') >= 0),
            'the ticker reply lands: ' + world.nodes.optionsDetail.innerHTML);
        const asked = world.asked[world.asked.length - 1];
        assert(asked.indexOf('/api/control/deribit/ticker') >= 0 && asked.indexOf('77000-C') >= 0, asked);
        const detail = world.nodes.optionsDetail.innerHTML;
        assert(detail.indexOf('Δ +0.493') >= 0, 'the greeks land in the detail line: ' + detail);
        assert(detail.indexOf('Γ') >= 0 && detail.indexOf('Θ') >= 0 && detail.indexOf('ρ') >= 0, detail);
        assert(panel.state().detail === 'BTC-16SEP26-77000-C');
        assert.strictEqual(panel.rowClick({ target: { closest: () => null } }), false, 'a click off the rows is not one');
        assert.strictEqual(panel.rowClick({}), false);
        world.tickerFail = 'HTTP 400: instrument not found (instrument_name)';
        await panel.loadTicker('BTC-16SEP26-77000-C');
        assert(world.nodes.optionsDetail.innerHTML.indexOf('instrument not found (instrument_name)') >= 0,
            'the venue own words reach the screen: ' + world.nodes.optionsDetail.innerHTML);
    });

    await check('a count of unavailable quotes carries the venue own reason with it', () => {
        const payload = Object.assign({}, CHAIN, {
            ticker_errors: 39, quoted_sides: 3, tickers: 41,
            ticker_error_sample: ['BTC-16SEP26-99999-C: HTTP 400: instrument not found (instrument_name)'],
        });
        const st = api.plan(payload, null, 'BTCUSDT', NOW, '');
        assert.strictEqual(st.state, 'ok');
        assert.strictEqual(st.tickerErrors, 39);
        assert.strictEqual(st.tickerErrorSample.length, 1);
        const sub = api.subText(st);
        assert(sub.indexOf('39 quote(s) unavailable') >= 0, sub);
        assert(sub.indexOf('instrument not found (instrument_name)') >= 0,
            'a dead cell has a reason, and the panel prints it: ' + sub);
        const quiet = api.plan(CHAIN, null, 'BTCUSDT', NOW, '');
        assert.strictEqual(quiet.tickerErrorSample.length, 0);
        assert(api.subText(quiet).indexOf('unavailable') < 0, 'a clean ladder says nothing about failures');
    });

    await check('everything rendered from the venue is escaped', () => {
        const hostile = { strikes: [{ strike: 100, call: { instrument: '<img src=x onerror=alert(1)>',
            bid: 1, ask: 2, iv: 50, delta: 0.5, oi: 1, volume: 1 }, put: null }] };
        const html = api.rowHtml(api.ladderFrom(hostile)[0], false);
        assert(html.indexOf('<img') < 0, 'a venue string is text, never markup: ' + html);
        assert(html.indexOf('&lt;img') >= 0);
        assert(api.esc('a & b "c" <d>') === 'a &amp; b &quot;c&quot; &lt;d&gt;');
        assert(api.esc(null) === '');
        const body = api.bodyHtml(api.plan({ ok: false, coverage: true, error: '<b>boom</b>' },
            null, 'BTCUSDT', NOW, ''));
        assert(body.indexOf('<b>boom</b>') < 0 && body.indexOf('&lt;b&gt;boom') >= 0, body);
    });

    await check('the module holds no storage, no timer of its own beyond one, and no engine verb', () => {
        assert.strictEqual((src.match(/setInterval\(/g) || []).length, 1, 'one timer for the panel');
        assert(src.indexOf('crypto only via Deribit — no options feed for ') >= 0,
            'the mandatory sentence is in the source, stated once');
        ['localStorage', 'sessionStorage', 'indexedDB', 'WebSocket', 'EventSource', '/api/control/engine']
            .forEach((bad) => assert.strictEqual(src.indexOf(bad), -1, 'options.js must not touch ' + bad));
        assert(src.indexOf('MutationObserver') >= 0 && src.indexOf("attributeFilter: ['class']") >= 0,
            'it watches its own section');
    });

    console.log('options selftest: ' + ok + ' ok, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
})();
