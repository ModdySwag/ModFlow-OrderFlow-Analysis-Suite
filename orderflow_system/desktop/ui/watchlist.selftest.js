/* watchlist.selftest.js — the panel's decisions, as behaviour rather than prose.
 *
 * The DOM half of the panel needs a browser; the half that decides WHO IS ON THE BOARD, WHAT A ROW
 * SHOWS, AND WHETHER ANYTHING IS STILL POLLING is pure, and it is the half the brief is about. So the
 * module is injected into a stub window + stub document here, with a counting fetch and a counting
 * timer, and the poll lifecycle is exercised for real against the real bus.js — a watchlist that
 * kept polling after it was hidden, or after the switch was turned off, would be exactly the kind of
 * quiet cost this suite's delivery layer exists to prevent.
 *
 * No browser, no network: nothing below reaches anything the suite actually runs.
 */
const assert = require('assert');
const fs = require('fs');
const watchSrc = fs.readFileSync(__dirname + '/watchlist.js', 'utf8');
const busSrc = fs.readFileSync(__dirname + '/bus.js', 'utf8');

let ok = 0, failed = 0;
/* the check() shape links.selftest.js uses, awaiting the body so the poll checks can sleep */
function check(name, fn) {
    return Promise.resolve().then(fn).then(() => { ok += 1; }, (e) => {
        failed += 1;
        console.log('  FAIL ' + name + ': ' + e.message);
    });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* Wait for something the panel does asynchronously (a fetch landing, a timer starting). */
async function until(cond, ms) {
    const deadline = Date.now() + (ms || 400);
    while (Date.now() < deadline) {
        if (cond()) return true;
        await sleep(5);
    }
    return !!cond();
}

/* ── the stub world ─────────────────────────────────────────────────────────────────────────────
   A node is what the panel touches: innerHTML, textContent, checked, options, handlers. The section
   carries a real classList so "the panel is on screen" can be flipped the way the shell flips it. */

function makeClassList(active) {
    const set = {};
    if (active) set.active = true;
    return {
        contains: (name) => !!set[name],
        add: (name) => { set[name] = true; },
        remove: (name) => { delete set[name]; },
        toggle: (name, on) => { if (on) set[name] = true; else delete set[name]; },
    };
}

function makeNode(id, extra) {
    const handlers = {};
    const node = {
        id: id || '', innerHTML: '', textContent: '', value: '', checked: true,
        options: [], dataset: {}, handlers, children: [],
        addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
        removeEventListener() {},
        dispatchEvent(ev) { (handlers[ev && ev.type] || []).forEach((fn) => fn(ev)); return true; },
        fire(type, ev) { (handlers[type] || []).forEach((fn) => fn(ev || { type: type, target: node })); return true; },
        querySelectorAll() { return []; },
        appendChild(child) { this.children.push(child); return child; },
        classList: makeClassList(false),
    };
    return Object.assign(node, extra || {});
}

const LIVE_LIST = [
    { symbol: 'BTCUSDT', price: 64231.5, volume_24h: 4100000, tick_count: 128402, candle_count: 900, data_source: 'bybit' },
    { symbol: 'ETHUSDT', price: 3147.25, volume_24h: 820500, tick_count: 41250, candle_count: 700, data_source: 'bybit' },
    { symbol: 'ESZ6', price: 5712.5, volume_24h: 90210, tick_count: 3300, candle_count: 400, data_source: 'bybit' },
];
const LIVE_STATUS = {
    state: 'running', running: true, symbols: ['BTCUSDT', 'ETHUSDT', 'ESZ6'],
    per_symbol: [
        { symbol: 'BTCUSDT', price: 64250.25, ticks: 129000, candles: 901, cum_delta: 12304.5, trade_phase: 'markup' },
        { symbol: 'ETHUSDT', price: 3121.5, ticks: 41200, candles: 701, cum_delta: -800.0, trade_phase: 'none' },
    ],
};
const IDLE_STATUS = { state: 'stopped', running: false, symbols: [], per_symbol: [] };
const DEMO_LIST = [
    { symbol: 'EURUSD', price: 1.07917, volume_24h: 139376, tick_count: 98213, candle_count: 949, data_source: 'demo' },
    { symbol: 'GBPUSD', price: 1.26086, volume_24h: 453285, tick_count: 85973, candle_count: 383, data_source: 'demo' },
];

function makeWorld(spec) {
    spec = spec || {};
    const nodes = {
        watchlistBody: makeNode('watchlistBody'),
        watchlistCount: makeNode('watchlistCount'),
        watchlistAuto: makeNode('watchlistAuto', { checked: spec.auto !== false }),
        watchlistRefresh: makeNode('watchlistRefresh'),
        watchlistSub: makeNode('watchlistSub'),
        symbolSelect: makeNode('symbolSelect', {
            value: spec.symbol || '',
            options: (spec.options || []).map((value) => ({ value: value })),
        }),
    };
    const section = makeNode('section', { dataset: { view: 'watchlist' } });
    const doc = {
        readyState: 'complete',
        getElementById: (id) => nodes[id] || null,
        querySelector: (sel) => (sel === '.view[data-view="watchlist"]' ? section : null),
        querySelectorAll: () => [],
        createElement: (tag) => makeNode('', { tagName: tag }),
        addEventListener: () => {},
        dispatchEvent: () => true,
        head: { appendChild: () => {} },
        body: makeNode('body'),
    };
    const world = {
        nodes, section, doc,
        calls: [], requested: { instruments: 0, status: 0 },
        fails: {}, timers: [], cleared: [], observers: [],
        instruments: spec.instruments === undefined ? LIVE_LIST : spec.instruments,
        status: spec.status === undefined ? LIVE_STATUS : spec.status,
        activate() { section.classList.add('active'); },
        deactivate() { section.classList.remove('active'); },
        notify() { world.observers.forEach((o) => o.callback()); },
    };
    if (spec.active !== false) world.activate();

    const fakeFetch = (url) => {
        world.calls.push(url);
        const which = String(url).indexOf('/api/instruments') === 0 ? 'instruments' : 'status';
        world.requested[which] += 1;
        if (world.fails[which]) return Promise.reject(new Error(world.fails[which]));
        const body = which === 'instruments' ? world.instruments : world.status;
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    };
    const fakeSetInterval = (fn, ms) => {
        const timer = { fn: fn, ms: ms, id: world.timers.length + 1, fire() { return fn(); } };
        world.timers.push(timer);
        return timer;
    };
    const fakeClearInterval = (timer) => { world.cleared.push(timer); };

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
    new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', 'MutationObserver', watchSrc)(
        win, doc, fakeFetch, fakeSetInterval, fakeClearInterval, MutationObserverStub);
    world.win = win;
    return world;
}

/* The module with no document at all: the pure layer must still load and expose its decisions. */
function bare() {
    const win = {};
    new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', 'MutationObserver', watchSrc)(
        win, undefined, () => Promise.reject(new Error('no fetch')), setInterval, clearInterval, undefined);
    return win.OFAPWATCHLIST;
}

(async function run() {
    const api = bare();

    await check('the module loads without a document and exposes the surface it documents', () => {
        assert(api, 'window.OFAPWATCHLIST missing');
        for (const name of ['esc', 'price', 'compact', 'signed', 'phase', 'orderSymbols', 'buildRow',
                            'buildRows', 'rowHtml', 'loadingHtml', 'emptyHtml', 'errorHtml', 'noteRow',
                            'bodyHtml', 'subText', 'render', 'rows', 'state', 'getJson', 'getStatus',
                            'onStatus', 'loadStatus', 'loadInstruments', 'refresh', 'startPoll',
                            'stopPoll', 'sync', 'activate', 'rowClick', 'bindControls', 'injectStyles',
                            'boot', 'watch']) {
            assert.strictEqual(typeof api[name], 'function', name + ' must be a function');
        }
        assert.strictEqual(api.VERSION, '0.1.0');
        assert.strictEqual(api.STATUS_URL, '/api/control/engine/status');
        assert.strictEqual(api.INSTRUMENTS_URL, '/api/instruments');
        assert.strictEqual(api.INTERVAL_MS, 2000);
        assert.strictEqual(api.DASH, '—', 'an absent field renders as an em dash');
        assert.strictEqual(api.state().polling, 'idle', 'and nothing polls in a page that has no panel');
    });

    await check('the active instrument leads, then the app own instrument order', () => {
        const rows = api.buildRows(LIVE_LIST, LIVE_STATUS, 'ETHUSDT');
        assert.deepStrictEqual(rows.map((r) => r.symbol), ['ETHUSDT', 'BTCUSDT', 'ESZ6']);
        assert.strictEqual(rows[0].active, true);
        assert.strictEqual(rows[1].active, false);
        assert.deepStrictEqual(api.buildRows(LIVE_LIST, LIVE_STATUS, '').map((r) => r.symbol),
            ['BTCUSDT', 'ETHUSDT', 'ESZ6'], 'with no active instrument the app order stands');
    });

    await check('the engine row wins for a symbol, and a field nobody carries is an em dash', () => {
        const rows = api.buildRows(LIVE_LIST, LIVE_STATUS, 'ETHUSDT');
        const btc = rows.find((r) => r.symbol === 'BTCUSDT');
        const eth = rows.find((r) => r.symbol === 'ETHUSDT');
        const esz = rows.find((r) => r.symbol === 'ESZ6');
        assert.strictEqual(btc.source, 'engine');
        assert.strictEqual(btc.cells.price, '64250.25', 'the engine price, not the lists 64231.5');
        assert.strictEqual(btc.cells.ticks, '129.0K');
        assert.strictEqual(btc.cells.delta, '+12.3K');
        assert.strictEqual(btc.cells.phase, 'markup');
        assert.strictEqual(eth.cells.price, '3121.50');
        assert.strictEqual(eth.cells.delta, '-800');
        assert.strictEqual(eth.cells.phase, '—', 'a phase of "none" is not a phase');
        assert.strictEqual(esz.cells.price, '5712.50', 'no engine row: the list own price stands in');
        assert.strictEqual(esz.cells.volume, '90.2K');
        assert.strictEqual(esz.cells.delta, '—', 'the list carries no delta, so the board says nothing');
        assert.strictEqual(esz.cells.phase, '—');
        assert.strictEqual(esz.cells.ticks, '3.3K');
    });

    await check('a price of zero is "no print yet", never a quote, and junk is not a number', () => {
        const rows = api.buildRows(
            [{ symbol: 'X', price: 0, tick_count: 0, volume_24h: null }],
            { per_symbol: [{ symbol: 'X', price: 0, ticks: 0, cum_delta: null, trade_phase: '' }] }, 'X');
        assert.strictEqual(rows[0].cells.price, '—');
        assert.strictEqual(rows[0].cells.ticks, '0', 'zero ticks is a fact, and it shows');
        assert.strictEqual(rows[0].cells.volume, '—');
        assert.strictEqual(rows[0].cells.delta, '—');
        const junk = api.buildRow('J', { symbol: 'J', price: 'n/a', tick_count: 'x' }, null, false);
        assert.strictEqual(junk.cells.price, '—');
        assert.strictEqual(junk.cells.ticks, '—');
        assert.strictEqual(api.state().rows, 0);
    });

    await check('the active instrument gets a row even when no payload carries it', () => {
        const rows = api.buildRows(LIVE_LIST, LIVE_STATUS, 'NAS100USDT');
        assert.strictEqual(rows[0].symbol, 'NAS100USDT', 'the app is on it, so the board shows it');
        assert.strictEqual(rows[0].source, 'none');
        assert.strictEqual(rows[0].cells.price, '—');
        assert.strictEqual(rows[0].active, true);
        assert.strictEqual(rows.length, 4);
        const live = api.buildRows(LIVE_LIST, { per_symbol: [{ symbol: 'SOLUSDT', price: 155.5, ticks: 9 }] }, '');
        assert.strictEqual(live[live.length - 1].symbol, 'SOLUSDT',
            'a symbol the engine streams is not dropped because the list did not name it');
    });

    await check('rows are escaped, so a symbol is text on the board and not markup in the page', () => {
        const evil = api.buildRows([{ symbol: '<img src=x onerror=alert(1)>', price: 1.5 }], null, '');
        const html = api.rowHtml(evil[0]);
        assert(html.indexOf('<img') < 0, 'the tag must not survive: ' + html);
        assert(html.indexOf('&lt;img') >= 0);
        assert(html.indexOf('data-symbol="&lt;img') >= 0, 'and the click target is escaped too');
        assert(api.esc('a & b "c" <d>') === 'a &amp; b &quot;c&quot; &lt;d&gt;');
        assert(api.esc(null) === '');
    });

    await check('loading, empty and error are states, never a blank panel', async () => {
        const world = makeWorld({ instruments: [], status: IDLE_STATUS });
        const panel = world.win.OFAPWATCHLIST;
        assert.strictEqual(panel.bodyHtml(panel.rows()), panel.loadingHtml(),
            'nothing read yet: the panel says it is loading');
        assert(panel.loadingHtml().indexOf('Loading') >= 0);
        await until(() => panel.state().loaded && world.requested.instruments > 0);
        const empty = panel.bodyHtml(panel.rows());
        assert(empty.indexOf('Nothing to watch') >= 0, 'an empty list says so: ' + empty);
        world.fails.instruments = 'HTTP 500';
        await panel.loadInstruments();
        const broken = panel.bodyHtml(panel.rows());
        assert(broken.indexOf('could not read /api/instruments') >= 0, broken);
        assert(broken.indexOf('HTTP 500') >= 0, 'the reason travels with the error');
        assert(broken.indexOf('tag no') >= 0, 'and it is an error row');
        assert.notStrictEqual(broken.trim(), '');
    });

    await check('the panel paints the count, the rows, and the active instrument first', async () => {
        const world = makeWorld({ instruments: LIVE_LIST, status: LIVE_STATUS, options: ['BTCUSDT', 'ETHUSDT', 'ESZ6'] });
        const panel = world.win.OFAPWATCHLIST;
        assert(await until(() => world.requested.instruments >= 1 && world.requested.status >= 1),
            'both endpoints were read');
        await sleep(10);
        world.nodes.symbolSelect.value = 'ESZ6';
        panel.render();
        assert.strictEqual(world.nodes.watchlistCount.textContent, '3', 'the count is the row count');
        const html = world.nodes.watchlistBody.innerHTML;
        assert(html.indexOf('data-symbol="ESZ6"') < html.indexOf('data-symbol="BTCUSDT"'),
            'the app instrument leads the board');
        assert(html.indexOf('data-symbol="BTCUSDT"') >= 0 && html.indexOf('data-symbol="ETHUSDT"') >= 0);
        assert(html.indexOf('>engine<') >= 0, 'rows fed by the engine say so');
        assert.strictEqual(world.nodes.watchlistBody.handlers.click.length, 1, 'one click listener, not one per row');
        assert.strictEqual(panel.state().rows, 3);
    });

    await check('the shared bus carries the poll, and the way out really stops it', async () => {
        const world = makeWorld({ bus: true, instruments: LIVE_LIST, status: LIVE_STATUS, active: false });
        const panel = world.win.OFAPWATCHLIST;
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0, 'hidden: nothing is polled');
        assert.strictEqual(world.requested.status, 0);
        assert.strictEqual(panel.state().polling, 'idle');
        world.activate();
        world.notify();
        assert(await until(() => panel.state().polling === 'bus' && world.requested.status >= 1),
            'becoming visible subscribes');
        assert.strictEqual(world.requested.status, 1, 'one immediate fetch, not one per row');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 1, 'one shared channel');
        assert.strictEqual(world.win.OFAPBUS.telemetry().subscribers, 1);
        panel.stopPoll();
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0, 'the way out releases the channel');
        const after = world.requested.status;
        await sleep(40);
        assert.strictEqual(world.requested.status, after, 'and nothing polls once it is released');
        world.win.OFAPBUS.stopAll();
    });

    await check('unchecking auto-refresh stops the poll and says so in the sub line', async () => {
        const world = makeWorld({ bus: true, instruments: LIVE_LIST, status: LIVE_STATUS });
        const panel = world.win.OFAPWATCHLIST;
        assert(await until(() => panel.state().polling === 'bus'), 'it polls while the switch is on');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 1);
        world.nodes.watchlistAuto.checked = false;
        world.nodes.watchlistAuto.fire('change');
        assert.strictEqual(panel.state().polling, 'idle');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0, 'the channel went with the switch');
        assert(world.nodes.watchlistSub.textContent.indexOf('auto-refresh off') >= 0,
            'the sub line says it: ' + world.nodes.watchlistSub.textContent);
        const after = world.requested.status;
        await sleep(40);
        assert.strictEqual(world.requested.status, after, 'and no fetch happens behind the switch');
        world.win.OFAPBUS.stopAll();
    });

    await check('hiding the panel stops the poll, and the bus keeps the only timer', async () => {
        const world = makeWorld({ bus: true, instruments: LIVE_LIST, status: LIVE_STATUS });
        const panel = world.win.OFAPWATCHLIST;
        assert(await until(() => panel.state().polling === 'bus'));
        assert.strictEqual(world.timers.length, 0, 'with a bus the panel owns no timer at all');
        world.deactivate();
        world.notify();
        assert.strictEqual(panel.state().polling, 'idle');
        assert.strictEqual(world.win.OFAPBUS.telemetry().channels, 0);
        assert(world.nodes.watchlistSub.textContent.indexOf('paused') >= 0,
            'and the board says it is not on screen: ' + world.nodes.watchlistSub.textContent);
        world.win.OFAPBUS.stopAll();
    });

    await check('with no bus the panel owns exactly one timer of its own, and clears it', async () => {
        const world = makeWorld({ instruments: LIVE_LIST, status: LIVE_STATUS });
        const panel = world.win.OFAPWATCHLIST;
        assert(await until(() => panel.state().polling === 'timer'));
        assert.strictEqual(world.timers.length, 1, 'one timer, whatever the number of rows');
        assert.strictEqual(world.timers[0].ms, 2000);
        assert.strictEqual(world.requested.status, 1, 'and it reads once immediately, not after 2s');
        assert(world.nodes.watchlistSub.textContent.indexOf('own timer') >= 0,
            'the panel admits it has no bus: ' + world.nodes.watchlistSub.textContent);
        world.timers[0].fire();
        assert(await until(() => world.requested.status >= 2), 'the timer fires a read');
        panel.stopPoll();
        assert.deepStrictEqual(world.cleared, [world.timers[0]], 'and the timer is cleared');
        assert.strictEqual(world.timers.length, 1, 'no second timer is created on the way out');
        world.nodes.watchlistAuto.checked = false;
        world.nodes.watchlistAuto.fire('change');
        assert.strictEqual(panel.state().polling, 'idle');
        world.nodes.watchlistAuto.checked = true;
        world.nodes.watchlistAuto.fire('change');
        assert.strictEqual(panel.state().polling, 'timer', 'and a restored switch restores the poll');
        assert.strictEqual(world.timers.length, 2);
    });

    await check('Refresh reads both endpoints at once, with the switch off and without restarting polls', async () => {
        const world = makeWorld({ bus: true, instruments: LIVE_LIST, status: LIVE_STATUS });
        const panel = world.win.OFAPWATCHLIST;
        assert(await until(() => panel.state().polling === 'bus' && world.requested.instruments >= 1));
        world.nodes.watchlistAuto.checked = false;
        world.nodes.watchlistAuto.fire('change');
        const before = { i: world.requested.instruments, s: world.requested.status };
        world.nodes.watchlistRefresh.fire('click');
        assert(await until(() => world.requested.instruments === before.i + 1 && world.requested.status === before.s + 1),
            'one press is one read of each endpoint');
        await sleep(10);
        assert.strictEqual(panel.state().polling, 'idle', 'and a one-off read does not start a poll');
        world.nodes.watchlistRefresh.fire('click');
        assert(await until(() => world.requested.instruments === before.i + 2), 'it works more than once');
        world.win.OFAPBUS.stopAll();
    });

    await check('a row switches the app only when the topbar offers that instrument', async () => {
        const world = makeWorld({ instruments: LIVE_LIST, status: LIVE_STATUS, options: ['BTCUSDT', 'ETHUSDT', 'ESZ6'] });
        const panel = world.win.OFAPWATCHLIST;
        const changes = [];
        world.nodes.symbolSelect.addEventListener('change', (ev) => changes.push(ev.type));
        assert(await until(() => panel.state().rows === 3));
        const row = (symbol) => ({ target: { closest: () => ({ dataset: { symbol: symbol } }) } });

        assert.strictEqual(panel.rowClick(row('BTCUSDT')), true);
        assert.strictEqual(world.nodes.symbolSelect.value, 'BTCUSDT');
        assert.deepStrictEqual(changes, ['change'], 'the apps own change path runs, once');
        assert.strictEqual(world.nodes.watchlistCount.textContent, '3');

        assert.strictEqual(panel.rowClick(row('NAS100USDT')), false, 'not offered: nothing happens');
        assert.strictEqual(world.nodes.symbolSelect.value, 'BTCUSDT', 'never forced to an unknown symbol');
        assert.deepStrictEqual(changes, ['change'], 'and no change event is invented');
        assert.strictEqual(panel.rowClick({ target: { closest: () => null } }), false, 'a click off the rows is not one');
        assert.strictEqual(panel.rowClick({}), false);
        assert.strictEqual(panel.activate(''), false);
    });

    await check('the demo case is stated, never passed off as quotes', async () => {
        const world = makeWorld({ instruments: DEMO_LIST, status: IDLE_STATUS });
        const panel = world.win.OFAPWATCHLIST;
        assert(await until(() => panel.state().rows === 2 && world.requested.status >= 1));
        await sleep(10);
        assert.strictEqual(world.nodes.watchlistCount.textContent, '2');
        const html = world.nodes.watchlistBody.innerHTML;
        assert(html.indexOf('>demo<') >= 0, 'each row carries the source the server reported: ' + html);
        assert(world.nodes.watchlistSub.textContent.indexOf('demo list') >= 0,
            'and the sub line says these are not your feed: ' + world.nodes.watchlistSub.textContent);
        assert(world.nodes.watchlistSub.textContent.indexOf('engine stopped') >= 0,
            'nor does it dress a stopped engine as a live one');
        assert(html.indexOf('€') < 0 && html.indexOf('NaN') < 0 && html.indexOf('undefined') < 0,
            'no placeholder garbage on the board');
    });

    console.log('watchlist selftest: ' + ok + ' ok, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
})();
