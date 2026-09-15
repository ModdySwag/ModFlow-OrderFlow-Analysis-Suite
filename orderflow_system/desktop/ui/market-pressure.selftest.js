/* market-pressure.selftest.js — the CVD card's poll decisions, as behaviour rather than prose.
 *
 * The card shares its series with the app's own CVD chart (atlas.js), so what has to be true of it is
 * arithmetic: ONE bus channel for the url, not one per subscriber; the panel's own timer only when
 * no delivery layer is loaded; the channel released the moment the panel leaves the screen (a
 * subscriber left behind is a poller nobody is watching); and the same painter whether the payload
 * came from the channel, a one-shot read or the Refresh button.
 *
 * No browser, no network: the module is injected into a stub window + stub document with a counting
 * fetch and a counting timer, against the real bus.js — exactly the harness watchlist.selftest.js
 * uses, because this is the same kind of claim.
 */
const assert = require('assert');
const fs = require('fs');
const mpSrc = fs.readFileSync(__dirname + '/market-pressure.js', 'utf8');
const busSrc = fs.readFileSync(__dirname + '/bus.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    return Promise.resolve().then(fn).then(() => { ok += 1; }, (e) => {
        failed += 1;
        console.log('  FAIL ' + name + ': ' + (e && e.message));
    });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ── the stub world ───────────────────────────────────────────────────────────────────────────── */

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
        id: id || '', innerHTML: '', textContent: '', value: '', checked: true, title: '',
        options: [], dataset: {}, children: [], clientWidth: 640,
        addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
        removeEventListener() {},
        fire(type, ev) { (handlers[type] || []).forEach((fn) => fn(ev || { type: type, target: node })); return true; },
        querySelectorAll() { return []; },
        appendChild(child) { this.children.push(child); return child; },
        classList: makeClassList(false),
    };
    return Object.assign(node, extra || {});
}

function makeCtx() {
    const noop = () => {};
    return { setTransform: noop, clearRect: noop, fillText: noop, beginPath: noop, moveTo: noop,
             lineTo: noop, stroke: noop, fillRect: noop, measureText: () => ({ width: 10 }) };
}

/* A cvd payload shaped like the real route's: series, windows, divergences, pro_multi. */
function cvdPayload(symbol, last) {
    return {
        symbol: symbol || 'BTCUSDT', cvd: -12.5, slope: 0.42, session_start_ms: 1700000000000,
        windows: { '60s': -1.5, '300s': -4.25 },
        divergences: [{ ts_ms: 1700000005000, kind: 'bullish', strength: 2.1, note: 'price lower, cvd higher' }],
        pro_multi: { bands: [[0, 1]], cvd: [-3.5] },
        series: [{ t: 1700000000000, cvd: -2, price: 60.5, buy: 2, sell: 1 },
                 { t: last || 1700000005000, cvd: -12.5, price: 61.25, buy: 3, sell: 2 }],
    };
}

function makeWorld(spec) {
    spec = spec || {};
    const canvas = makeNode('mpCanvas', { parentElement: { clientWidth: 640 }, getContext: () => makeCtx() });
    const nodes = {
        mpKpis: makeNode('mpKpis'),
        mpCanvas: canvas,
        mpStamp: makeNode('mpStamp'),
        mpNote: makeNode('mpNote'),
        mpRefresh: makeNode('mpRefresh'),
        symbolSelect: makeNode('symbolSelect', { value: spec.symbol || 'BTCUSDT' }),
    };
    const section = makeNode('section', { dataset: { view: 'cvd' } });
    const created = [];
    const doc = {
        readyState: 'complete',
        getElementById: (id) => nodes[id] || created.filter((n) => n.id === id)[0] || null,
        querySelector: (sel) => (sel === '.view[data-view="cvd"]' ? section : null),
        querySelectorAll: () => [],
        createElement: (tag) => { const node = makeNode('', { tagName: tag }); created.push(node); return node; },
        addEventListener: () => {},
        dispatchEvent: () => true,
        head: { appendChild: () => {} },
        body: makeNode('body'),
    };
    const world = {
        nodes, section, doc, calls: [], timers: [], cleared: [], observers: [], showed: [],
        payload: spec.payload === undefined ? cvdPayload('BTCUSDT') : spec.payload,
        failNext: false,
        activate() { section.classList.add('active'); },
        deactivate() { section.classList.remove('active'); },
        notify() { world.observers.slice().forEach((o) => o.callback()); },
    };
    if (spec.active !== false) world.activate();

    const fakeFetch = (url) => {
        world.calls.push(String(url));
        if (world.failNext) return Promise.reject(new Error('no cvd for BTCUSDT'));
        const body = typeof world.payload === 'function' ? world.payload(String(url)) : world.payload;
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    };
    const fakeSetInterval = (fn, ms) => {
        const timer = { fn: fn, ms: ms, id: world.timers.length + 1, fire() { return fn(); } };
        world.timers.push(timer);
        return timer;
    };
    const fakeClearInterval = (timer) => { world.cleared.push(timer); };

    const win = { devicePixelRatio: 1 };
    if (spec.bus) {
        new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', busSrc)(
            win, doc, fakeFetch, setInterval, clearInterval);
    }
    const ObserverStub = function (callback) {
        this.callback = callback;
        this.observe = () => { world.observers.push(this); };
        this.disconnect = () => {};
    };
    const expose = '\n;window.__MP__ = { PRESSURE: PRESSURE, mpApply: mpApply, mpLoad: mpLoad, mpSync: mpSync,'
        + ' mpStopPoll: mpStopPoll, mpWatch: mpWatch, mpUrl: mpUrl, mpSymbol: mpSymbol, mpMount: mpMount };';
    /* `api` is ui.js's own transport helper — a page global this module calls; the harness hands it
       the same counting fetch so a no-bus read is still measured. */
    const apiStub = (path, options) => fakeFetch(path, options).then((r) => r.json());
    new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', 'MutationObserver',
                 'setTimeout', 'esc', 'api', mpSrc + expose)(
        win, doc, fakeFetch, fakeSetInterval, fakeClearInterval, ObserverStub,
        () => 0,                                   /* the boot's own setTimeout: never fires, the checks drive it */
        (t) => String(t == null ? '' : t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])),
        apiStub);
    world.win = win;
    world.mp = win.__MP__;
    return world;
}

(async function run() {
    await check('the module loads and exposes the pieces the poll decisions live in', () => {
        const w = makeWorld();
        const mp = w.mp;
        assert(mp, 'the module did not expose its poll surface');
        for (const name of ['mpApply', 'mpLoad', 'mpSync', 'mpStopPoll', 'mpWatch', 'mpUrl']) {
            assert.strictEqual(typeof mp[name], 'function', name + ' must be a function');
        }
        assert.strictEqual(typeof mp.PRESSURE, 'object', 'the panel state must be inspectable');
    });

    await check('with no delivery layer the panel owns exactly one timer, at its own cadence', async () => {
        const w = makeWorld();
        w.mp.mpWatch();
        assert.strictEqual(w.mp.PRESSURE.polling, 'timer', 'no bus: the panel is the asker');
        assert.strictEqual(w.timers.length, 1, 'one timer, not two');
        assert.strictEqual(w.timers[0].ms, 4000, 'and it is the 4 s this card has always used');
        assert.strictEqual(w.calls.length, 1, 'the first read happens at once');
        assert.strictEqual(w.calls[0], '/api/atlas/cvd/BTCUSDT');
        await w.timers[0].fire();
        assert.strictEqual(w.calls.length, 2, 'and the timer keeps asking');
        w.mp.mpStopPoll();
        assert.strictEqual(w.cleared.length, 1, 'leaving the screen clears it');
        assert.strictEqual(w.mp.PRESSURE.polling, 'idle');
    });

    await check('with the bus the panel subscribes — one channel, its cadence, no timer of its own', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        const t = w.win.OFAPBUS.telemetry();
        assert.strictEqual(w.mp.PRESSURE.polling, 'bus', 'a delivery layer is loaded: join it');
        assert.strictEqual(t.channels, 1, 'one channel');
        assert.strictEqual(t.subscribers, 1, 'held by this card');
        assert.strictEqual(t.rows[0].key, 'GET /api/atlas/cvd/BTCUSDT', 'keyed by the url it reads');
        assert.strictEqual(t.rows[0].intervalMs, 5000, 'at the shared cadence');
        assert.strictEqual(w.timers.length, 0, 'the bus owns the timer, the panel owns none');
        assert.strictEqual(w.win.OFAPBUS.telemetry().fetches, 1, 'and it fetched at once');
        w.win.OFAPBUS.stopAll();
    });

    await check('the CVD chart joining the same url does NOT make a second channel', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        const off = w.win.OFAPBUS.subscribe({ url: '/api/atlas/cvd/BTCUSDT', intervalMs: 5000 }, () => {});
        const t = w.win.OFAPBUS.telemetry();
        assert.strictEqual(t.channels, 1, 'two panels on one series = one channel, not two');
        assert.strictEqual(t.subscribers, 2, 'both of them are counted on it');
        assert.strictEqual(w.win.OFAPBUS.telemetry().fetches, 1, 'and the url was asked for once');
        off();
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, 1, 'the sibling leaving must not take it down');
        w.mp.mpStopPoll();
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, 0, 'the last one out stops it');
    });

    await check('hidden: the card releases its subscription and the channel drops with it', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, 1);
        w.deactivate();
        w.notify();
        assert.strictEqual(w.mp.PRESSURE.polling, 'idle', 'off screen: nothing is polled for this card');
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, 0, 'and the channel went with it');
        w.activate();
        w.notify();
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, 1, 'coming back on screen rejoins');
        assert.strictEqual(w.mp.PRESSURE.polling, 'bus');
        w.win.OFAPBUS.stopAll();
    });

    await check('the instrument moves the channel key, not the channel count', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        const first = w.win.OFAPBUS.telemetry().rows[0].key;
        w.nodes.symbolSelect.value = 'ETHUSDT';
        w.nodes.symbolSelect.fire('change');
        const t = w.win.OFAPBUS.telemetry();
        assert.strictEqual(t.channels, 1, 'still one channel, on the new key');
        assert.notStrictEqual(t.rows[0].key, first, 'the key moved');
        assert(t.rows[0].key.indexOf('ETHUSDT') > 0, 'to the new instrument: ' + t.rows[0].key);
        assert.strictEqual(w.mp.mpUrl(w.mp.mpSymbol()), '/api/atlas/cvd/ETHUSDT');
        w.win.OFAPBUS.stopAll();
    });

    await check('the sub line says which cadence is actually running', async () => {
        const withBus = makeWorld({ bus: true });
        withBus.mp.mpWatch();
        await sleep(20);
        assert(withBus.nodes.mpNote.textContent.indexOf('polling 5s via the shared bus') > 0,
            'a shared channel must say so: ' + withBus.nodes.mpNote.textContent);
        withBus.win.OFAPBUS.stopAll();

        const alone = makeWorld();
        alone.mp.mpWatch();
        await sleep(20);
        assert(alone.nodes.mpNote.textContent.indexOf("this panel's own timer (no bus)") > 0,
            'and with no bus the wording names the timer: ' + alone.nodes.mpNote.textContent);
    });

    await check('an unchanged payload does not repaint; a manual read and a moved series do', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        await sleep(20);
        const same = cvdPayload('BTCUSDT', 1700000005000);
        assert.strictEqual(w.mp.mpApply(same, false), false, 'same last bucket: nothing new to show');
        assert.strictEqual(w.mp.mpApply(same, true), true, 'the Refresh button always repaints');
        assert.strictEqual(w.mp.mpApply(cvdPayload('BTCUSDT', 1700000009000), false), true,
            'a new bucket repaints');
        w.win.OFAPBUS.stopAll();
    });

    await check('a failed read is stated, never blanked into a zero', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        assert.strictEqual(w.mp.mpApply({ error: 'HTTP 503' }, false), false);
        assert(w.nodes.mpKpis.innerHTML.indexOf('pressure unavailable') >= 0,
            'the failure is named on the card: ' + w.nodes.mpKpis.innerHTML.slice(0, 80));
        assert(w.nodes.mpKpis.innerHTML.indexOf('503') > 0, 'with the reason');
        w.win.OFAPBUS.stopAll();
    });

    await check('the Refresh button reads once through the bus, without disturbing the channel', async () => {
        const w = makeWorld({ bus: true });
        w.mp.mpWatch();
        const before = w.win.OFAPBUS.telemetry().channels;
        const calls = w.calls.length;
        await w.mp.mpLoad(true);
        assert.strictEqual(w.calls.length, calls + 1, 'one read, on the spot');
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, before, 'and the shared channel is untouched');
        w.win.OFAPBUS.stopAll();
    });

    await check('a hidden card asks for nothing, even when the timer fires', async () => {
        const w = makeWorld({ bus: true, active: false });
        w.mp.mpWatch();
        assert.strictEqual(w.mp.PRESSURE.polling, 'idle', 'not on screen: not subscribed');
        assert.strictEqual(w.win.OFAPBUS.telemetry().channels, 0);
        await w.mp.mpLoad(false);
        assert.strictEqual(w.calls.length, 0, 'and a direct read refuses too');
        assert.strictEqual(w.mp.mpSync(), false);
        w.win.OFAPBUS.stopAll();
    });

    await check('the arbiter is consulted: a held surface is never repainted under the user', () => {
        const src = mpSrc;
        assert(src.indexOf("OFAPINTENT.anyHeld()") > 0, 'the own-timer tick must ask the arbiter');
        assert(src.indexOf('OFAPBUS') > 0 && src.indexOf('bus.subscribe') > 0, 'and it must use the delivery layer');
        assert.strictEqual((src.match(/setInterval\(/g) || []).length, 1,
            'one timer at most — the no-bus fallback');
        assert.strictEqual((src.match(/clearInterval\(/g) || []).length, 1, 'and it is cleared by the same code');
    });

    console.log('market-pressure selftest: ' + ok + ' ok, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
})();
