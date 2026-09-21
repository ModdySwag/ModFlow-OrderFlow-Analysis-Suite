/* depth-history.selftest.js — the strip's own behaviour, pinned without a browser.
 *
 * The two things that are measured here rather than asserted in prose: the canvas backing store is
 * its CSS box TIMES devicePixelRatio (with every path painted at the logical size), and a poll only
 * happens while the panel is on screen and only through the timer the pause registry holds. The
 * rest is the mapping from the store's payload to what gets drawn — bands, colours, markers — plus
 * the refusal path, which must never turn into a chart with invented numbers on it.
 *
 * `node desktop/ui/depth-history.selftest.js` prints "depth history selftest: N ok, M failed" and
 * exits non-zero on any failure.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/depth-history.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

/* ── the stub world ─────────────────────────────────────────────────────────────────────────── */

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

function makeCanvas(id, width, height) {
    const writes = [];
    const node = {
        id: id, clientWidth: width, clientHeight: height, style: {}, calls: [], texts: [],
        getContext() {
            const self = this;
            const noop = () => {};
            return {
                setTransform: (...args) => { self.calls.push(['setTransform'].concat(args)); },
                clearRect: (...args) => { self.calls.push(['clearRect'].concat(args)); },
                fillRect: (...args) => { self.calls.push(['fillRect'].concat(args)); },
                beginPath: noop, moveTo: noop, lineTo: noop, stroke: noop, fill: noop, arc: noop,
                strokeRect: noop,
                measureText: (t) => ({ width: String(t).length * 5 }),
                fillText: (t) => { self.texts.push(String(t)); },
                set font(v) {}, get font() { return ''; },
                set fillStyle(v) {}, get fillStyle() { return ''; },
                set strokeStyle(v) {}, get strokeStyle() { return ''; },
                set lineWidth(v) {}, get lineWidth() { return 1; },
            };
        },
    };
    /* the backing store: every assignment is counted, because a redundant one blanks the canvas */
    let w = 0, h = 0;
    Object.defineProperty(node, 'width', {
        get: () => w,
        set: (v) => { writes.push(['width', v]); w = v; },
    });
    Object.defineProperty(node, 'height', {
        get: () => h,
        set: (v) => { writes.push(['height', v]); h = v; },
    });
    node.storeWrites = writes;
    return node;
}

function makeNode(id, extra) {
    const handlers = {};
    const node = {
        id: id || '', innerHTML: '', textContent: '', value: '', checked: true, title: '',
        dataset: {}, children: [], attrs: {}, style: {},
        setAttribute(k, v) { this.attrs[k] = v; },
        appendChild(child) { this.children.push(child); return child; },
        addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
        removeEventListener(type, fn) {
            const list = handlers[type] || [];
            const i = list.indexOf(fn);
            if (i >= 0) list.splice(i, 1);
        },
        fire(type, ev) { (handlers[type] || []).slice().forEach((fn) => fn(ev || { type, target: node })); },
        listeners: () => Object.keys(handlers).reduce((n, k) => n + handlers[k].length, 0),
        querySelector: () => null,
        classList: makeClassList(false),
    };
    return Object.assign(node, extra || {});
}

function bandsFixture() {
    return [99, 99.25, 99.5, 99.75, 100, 100.25, 100.5, 100.75, 101];
}

function payload(overrides) {
    const bands = bandsFixture();
    const buckets = [];
    for (let i = 0; i < 4; i += 1) {
        const rowBands = [];
        for (let r = 0; r < bands.length - 1; r += 1) {
            rowBands.push({ bid: r === 3 ? 40 : 5, ask: r === 4 ? 30 : 4 });
        }
        buckets.push({
            ts_ms: 1700000000000 + i * 5000, at_ms: 1700000000000 + i * 5000 + 4000, columns: 5,
            total_bid: 100, total_ask: 90, total: 190, best_bid: 99.75, best_ask: 100.25,
            spread: 0.5, weighted_mid: 100, levels: 8,
            biggest: { price: 99.25, size: 40, side: 'bid', share: 0.21 }, bands: rowBands,
        });
    }
    const base = {
        ok: true, symbol: 'BTCUSDT', bucket_ms: 5000, bucket_ms_requested: 5000, interval_ms: 1000,
        from_ms: 1700000000000, to_ms: 1700000015000, first_ms: 1700000000000, last_ms: 1700000015000,
        have_from_ms: 1700000000000, have_to_ms: 1700000015000,
        buckets: buckets, bands: bands, profile: [], peak_band: null, busiest_bucket: null,
        events: [
            { kind: 'pull', ts_ms: 1700000005000, price: 99.5, side: 'bid', size: 25, from: 40, to: 15, pct: 0.62 },
            { kind: 'add', ts_ms: 1700000010000, price: 100.5, side: 'ask', size: 30, from: 10, to: 40, pct: 3 },
            { kind: 'pull', ts_ms: 1700000100000, price: 99.5, side: 'bid', size: 90, from: 120, to: 30, pct: 0.75 },
            { kind: 'add', ts_ms: 1700000005000, price: 96.0, side: 'bid', size: 12, from: 0, to: 12, pct: 1 },
        ],
        gaps: { gaps: [], count: 0, largest_ms: 0, missing_ms: 0, span_ms: 15000, covered_pct: 100 },
        staleness: { last_ms: 1700000015000, age_ms: 700, state: 'fresh', text: 'recording · last column 0.7 s ago',
            fresh_ms: 3000, stale_ms: 15000 },
        span_ms: 15000, levels: 320, detail: '',
        retained: { columns: 16, levels: 320, first_ms: 1700000000000, last_ms: 1700000015000 },
        settings: { retention_minutes: 30, max_columns_per_symbol: 1800, interval_ms: 1000,
            max_levels: 40, pull_pct: 0.5, add_pct: 0.5, min_size: 1 },
    };
    return Object.assign(base, overrides || {});
}

function makeWorld(spec) {
    spec = spec || {};
    const canvas = makeCanvas('depthHistoryCanvas', spec.cssWidth === undefined ? 700 : spec.cssWidth, 260);
    const nodes = {
        depthHistoryCanvas: canvas,
        depthHistoryKpis: makeNode('depthHistoryKpis'),
        depthHistoryStamp: makeNode('depthHistoryStamp'),
        depthHistoryNote: makeNode('depthHistoryNote'),
        depthHistoryTape: makeNode('depthHistoryTape'),
        depthHistoryLegendText: makeNode('depthHistoryLegendText'),
        depthHistoryRefresh: makeNode('depthHistoryRefresh'),
        depthHistoryClear: makeNode('depthHistoryClear'),
        depthHistoryWindow: makeNode('depthHistoryWindow', { value: '30' }),
        depthHistoryBucket: makeNode('depthHistoryBucket', { value: '5000' }),
        depthHistoryKeep: makeNode('depthHistoryKeep', { value: '30' }),
        depthHistoryMarkers: makeNode('depthHistoryMarkers', { checked: true }),
        symbolSelect: makeNode('symbolSelect', { value: spec.symbol === undefined ? 'btcusdt' : spec.symbol }),
    };
    const section = makeNode('section', { dataset: { view: 'depth-history' }, classList: makeClassList(true) });
    const created = [];
    const docHandlers = {};
    const doc = {
        /* the script loads during parsing, so the panel's boot rides DOMContentLoaded — the same
           path the real page takes, and the one the module's boot listener is removed from */
        readyState: 'loading',
        head: makeNode('head'),
        body: makeNode('body'),
        getElementById: (id) => nodes[id] || created.filter((n) => n.id === id)[0] || null,
        querySelector: (sel) => (sel === '.view[data-view="depth-history"]' ? section : null),
        querySelectorAll: () => [],
        createElement: (tag) => { const node = makeNode('', { tagName: tag, innerHTML: '' }); created.push(node); return node; },
        addEventListener: (type, fn) => { (docHandlers[type] = docHandlers[type] || []).push(fn); },
        removeEventListener: (type, fn) => {
            const list = docHandlers[type] || [];
            const i = list.indexOf(fn);
            if (i >= 0) list.splice(i, 1);
        },
        listenerCount: (type) => (docHandlers[type] || []).length,
        fire: (type) => { (docHandlers[type] || []).slice().forEach((fn) => fn()); },
        dispatchEvent: () => true,
    };
    const world = {
        nodes, section, doc, calls: [], posts: [], timers: [], cleared: [], registered: [], unregistered: 0,
        payload: spec.payload === undefined ? payload() : spec.payload,
        fail: !!spec.fail, empty: !!spec.empty,
        win: { devicePixelRatio: spec.dpr === undefined ? 2 : spec.dpr },
        /* the panel's boot: what the browser does when the document finishes parsing */
        boot() { doc.readyState = 'complete'; doc.fire('DOMContentLoaded'); return world; },
    };
    if (spec.active === false) world.section.classList.remove('active');
    if (spec.ofx) {
        world.win.OFX = { math: { heatColor01: spec.ofx } };
    }
    if (spec.api) world.win.api = (path) => world.call(path).then((r) => r.json());

    const respond = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) });
    world.call = (url, options) => {
        world.calls.push({ url: String(url), options: options || null });
        if (options && String(options.method || '').toUpperCase() === 'POST') {
            world.posts.push({ url: String(url), body: options.body ? JSON.parse(options.body) : null });
            const body = typeof world.reply === 'function' ? world.reply(String(url)) : world.reply;
            return Promise.resolve(respond(body === undefined ? { ok: true, settings: { retention_minutes: 120 }, stats: {} } : body));
        }
        if (world.fail) return Promise.reject(new Error('depth record unreachable'));
        if (world.empty) return Promise.resolve(respond(null));
        const body = typeof world.payload === 'function' ? world.payload(String(url)) : world.payload;
        return Promise.resolve(respond(body));
    };
    const fakeFetch = (url, options) => world.call(url, options);
    const fakeSetInterval = (fn, ms) => {
        const timer = { id: world.timers.length + 1, ms: ms, fire: () => fn() };
        world.timers.push(timer);
        return timer;
    };
    const fakeClearInterval = (timer) => { world.cleared.push(timer); };
    const pause = {
        register: (id, restart) => { world.registered.push({ id: id, restart: restart }); return id; },
        unregister: () => { world.unregistered += 1; return true; },
        isPaused: () => false,
    };
    world.win.OFAPPause = pause;
    world.win.fetch = fakeFetch;

    new Function('window', 'document', 'fetch', 'setInterval', 'clearInterval', src)(
        world.win, doc, fakeFetch, fakeSetInterval, fakeClearInterval);
    world.dh = world.win.OFAPDEPTHH;
    return world;
}

const tick = () => new Promise((r) => setTimeout(r, 0));

/* ── the display scale (the canvas hard rule) ───────────────────────────────────────────────── */

(function () {
    const w = makeWorld({ dpr: 2 });
    const dh = w.dh;
    const fit = dh.fit(w.nodes.depthHistoryCanvas, 260, 2);
    check('fit: the backing store is the CSS box times devicePixelRatio',
        fit.cssW === 700 && fit.cssH === 260 && fit.dpr === 2 && fit.w === 1400 && fit.h === 520,
        JSON.stringify(fit));
    check('fit: a canvas with no measurable box falls back, never to zero',
        dh.fit(null, 260, 0).w === 640 && dh.fit(null, 260, 0).dpr === 1);
    check('dpr: the window scale, and 1 when there is none', dh.dpr() === 2);

    dh.draw(payload());
    const writes = w.nodes.depthHistoryCanvas.storeWrites;
    check('draw: the backing store carries the display scale',
        w.nodes.depthHistoryCanvas.width === 1400 && w.nodes.depthHistoryCanvas.height === 520,
        JSON.stringify([w.nodes.depthHistoryCanvas.width, w.nodes.depthHistoryCanvas.height]));
    check('draw: every path is painted at the logical size',
        w.nodes.depthHistoryCanvas.calls[0].join(',') === 'setTransform,2,0,0,2,0,0'
        && w.nodes.depthHistoryCanvas.calls[1].join(',') === 'clearRect,0,0,700,260',
        JSON.stringify(w.nodes.depthHistoryCanvas.calls.slice(0, 2)));
    check('draw: cells are painted inside the CSS box, never past it', w.nodes.depthHistoryCanvas.calls
        .filter((c) => c[0] === 'fillRect')
        .every((c) => c[1] >= 0 && c[2] >= 0 && c[1] + c[3] <= 700.5 && c[2] + c[4] <= 260.5));
    const before = writes.length;
    dh.draw(payload());
    check('draw: an unchanged box does not touch the backing store again (that would blank it)',
        writes.length === before, JSON.stringify(writes.slice(before)));
    check('draw: the legend canvas keeps a CSS box of its own',
        w.nodes.depthHistoryCanvas.style.height === '260px' && w.nodes.depthHistoryCanvas.style.width === '100%');
})();

/* ── bands, colours, the ceiling ────────────────────────────────────────────────────────────── */

(function () {
    const w = makeWorld();
    const dh = w.dh;
    const bands = bandsFixture();
    check('bandRow: a price lands in its own band', dh.bandRow(99.0, bands) === 0 && dh.bandRow(99.75, bands) === 3);
    check('bandRow: the top price belongs to the last band', dh.bandRow(101, bands) === bands.length - 2);
    check('bandRow: a price outside the window is no row', dh.bandRow(98, bands) === -1);
    check('bandRow: junk is no row, never a throw',
        dh.bandRow('x', bands) === -1 && dh.bandRow(100, []) === -1 && dh.bandRow(100, [99, 99]) === -1);

    check('colour: nothing resting means no paint', dh.colour(0, 10) === '' && dh.colour(null, 10) === '');
    const thin = dh.colour(1, 100);
    const heavy = dh.colour(90, 100);
    const lum = (s) => (s.match(/\d+/g) || []).slice(0, 3).reduce((a, v) => a + Number(v), 0);
    check('colour: the ramp is monotone in luminance', lum(thin) < lum(heavy), thin + ' vs ' + heavy);
    check('colour: the ramp tops out at the engine-like gold', dh.colour(1e9, 1e9).indexOf('rgba(255,242,196') === 0);

    const engine = makeWorld({ ofx: () => [10, 20, 30] });
    check('colour: the engine ramp is used when it is loaded', engine.dh.colour(5, 10) === 'rgba(10,20,30,0.92)');
    const stringy = makeWorld({ ofx: () => 'rgb(1,2,3)' });
    check('colour: a string ramp is passed through', stringy.dh.colour(5, 10) === 'rgb(1,2,3)');

    check('sizeMax: the biggest band total in the window is the ceiling',
        dh.sizeMax(payload()) === 44, String(dh.sizeMax(payload())));
    check('sizeMax: an empty or junk payload still answers a usable ceiling',
        dh.sizeMax(null) === 1 && dh.sizeMax({ buckets: [] }) === 1);
})();

/* ── mapping the payload onto the strip ─────────────────────────────────────────────────────── */

(function () {
    const w = makeWorld();
    const dh = w.dh;
    check('url: the route the store serves, with the panel\'s options',
        dh.url('btcusdt', { minutes: 30, bucket_ms: 5000 })
            === '/api/atlas/depth-history/BTCUSDT?minutes=30&bucket_ms=5000',
        dh.url('btcusdt', { minutes: 30, bucket_ms: 5000 }));
    check('url: markers off is an explicit events=0 (the store then sends no event tail)',
        dh.url('BTCUSDT', { minutes: 5, bucket_ms: 1000, events: false }).indexOf('events=0') > 0);
    check('url: a blank symbol is refused by the caller, not fetched as a path', dh.url('', {}).indexOf('//') < 0);

    const cells = dh.markerCells(payload());
    check('markerCells: only the events inside the drawn window survive', cells.length === 2, JSON.stringify(cells));
    check('markerCells: a pull maps to its column and price band, and carries its kind',
        cells[0].kind === 'pull' && cells[0].pull === true && cells[0].column === 1 && cells[0].band === 2,
        JSON.stringify(cells[0]));
    check('markerCells: a stack maps to a ring, at its own cell',
        cells[1].kind === 'add' && cells[1].pull === false && cells[1].column === 2 && cells[1].band === 6,
        JSON.stringify(cells[1]));
    check('markerCells: no buckets means no markers (never a scatter on an empty strip)',
        dh.markerCells({ buckets: [], bands: bandsFixture(), events: [{ kind: 'pull', ts_ms: 1, price: 99, size: 1 }] }).length === 0);
    check('markerCells: a cap keeps the read bounded',
        dh.markerCells(payload({ events: new Array(50).fill({ kind: 'pull', ts_ms: 1700000005000, price: 99.5, size: 1 }) }), 5).length === 5);

    /* T6-F05: the store's bucket list SKIPS the cells it never recorded, so a marker must map to its
       cell's own slot in the array — not to its offset on the time grid — and a cap must drop the
       OLDEST markers, never the newest. */
    const kept = payload().buckets;
    const gapped = payload({
        buckets: [
            Object.assign({}, kept[0], { ts_ms: 1700000000000 }),
            Object.assign({}, kept[1], { ts_ms: 1700000005000 }),
            Object.assign({}, kept[2], { ts_ms: 1700000015000 }),      /* 1700000010000 skipped */
        ],
        events: [
            { kind: 'pull', ts_ms: 1700000000500, price: 99.5, size: 1 },     /* cell 0 -> slot 0 */
            { kind: 'pull', ts_ms: 1700000010500, price: 99.5, size: 2 },     /* the gap -> dropped */
            { kind: 'add', ts_ms: 1700000015500, price: 99.5, size: 3 },      /* cell 3 -> slot 2 */
        ],
    });
    const mapped = dh.markerCells(gapped);
    check('markerCells: an event in a cell the store never recorded is dropped, not shifted',
        mapped.length === 2 && mapped[0].size === 1 && mapped[1].size === 3,
        JSON.stringify(mapped));
    check('markerCells: the surviving markers sit on their own cells (slot, not grid offset)',
        mapped[0].column === 0 && mapped[1].column === 2 && mapped[1].kind === 'add',
        JSON.stringify(mapped));
    const newest = payload({ events: [
        { kind: 'pull', ts_ms: 1700000000500, price: 99.5, size: 1 },
        { kind: 'add', ts_ms: 1700000010500, price: 99.5, size: 2 },
        { kind: 'pull', ts_ms: 1700000015500, price: 99.5, size: 3 },
    ] });
    const capped = dh.markerCells(newest, 2);
    check('markerCells: a cap keeps the NEWEST markers, the oldest fall off',
        capped.length === 2 && capped[0].size === 2 && capped[1].size === 3,
        JSON.stringify(capped));

    const s = dh.summary(payload());
    check('summary: the head numbers come off the payload',
        s.pulls === 2 && s.adds === 2 && s.pull_size === 115 && s.add_size === 42 && s.buckets === 4,
        JSON.stringify([s.pulls, s.adds, s.pull_size, s.add_size]));
    check('summary: the newest bucket is the live book',
        s.total_bid === 100 && s.total_ask === 90 && s.biggest.size === 40);
    check('summary: coverage and state are the store\'s words, not the panel\'s',
        s.covered === 100 && s.state === 'fresh' && s.columns === 16 && s.levels === 320);
    check('legendText: one line of what is drawn', dh.legendText(payload()).indexOf('4 buckets') === 0,
        dh.legendText(payload()));
})();

/* ── the refusal path ───────────────────────────────────────────────────────────────────────── */

(function () {
    const w = makeWorld();
    const dh = w.dh;
    check('refusal: the store\'s own sentence is what the panel shows',
        dh.refusal({ ok: false, detail: 'no depth recorded yet for NOPEUSDT — leave the heatmap open for a minute and it will start filling' })
            .indexOf('no depth recorded yet for NOPEUSDT') === 0);
    check('refusal: a readable record with an empty window still says why',
        dh.refusal({ ok: true, buckets: [], detail: 'BTCUSDT has depth recorded from 10:00 — ask for a window overlapping it, or widen the range' })
            .indexOf('ask for a window') > 0);
    check('refusal: a record with buckets has nothing to refuse', dh.refusal(payload()) === '');
    check('refusal: no payload at all is a plain sentence', dh.refusal(null).length > 10);

    w.dh.draw({ ok: false, detail: 'no depth recorded yet for NOPEUSDT — leave the heatmap open for a minute and it will start filling' });
    check('draw: a refused instrument paints the sentence, not a chart',
        w.nodes.depthHistoryCanvas.texts.join('|').indexOf('leave the heatmap open') > 0
        && w.nodes.depthHistoryCanvas.calls.filter((c) => c[0] === 'fillRect').length === 0,
        JSON.stringify(w.nodes.depthHistoryCanvas.texts));

    w.dh.apply({ ok: false, symbol: 'NOPEUSDT', detail: 'no depth recorded yet for NOPEUSDT — leave the heatmap open for a minute and it will start filling',
        buckets: [], events: [] });
    check('apply: a refusal counts itself and leaves the KPIs empty',
        w.dh.DEPTHH.refusals === 1 && w.nodes.depthHistoryKpis.innerHTML.indexOf('nothing to read yet') > 0);
})();

/* ── the panel: mount, timer, poll, controls ────────────────────────────────────────────────── */

async function checkAsync(name, fn) {
    try {
        await fn();
        ok += 1;
    } catch (e) {
        failures.push(name + ' — ' + (e && e.message));
    }
}

(async function run() {
    await checkAsync('boot: mounts the card once and keeps one timer at the panel cadence', async () => {
        const w = makeWorld();
        assert.strictEqual(w.doc.listenerCount('DOMContentLoaded'), 1, 'the boot hook is registered');
        w.boot();
        assert.strictEqual(w.section.children.length, 1, 'one card');
        assert.strictEqual(w.nodes.depthHistoryCanvas.id, 'depthHistoryCanvas');
        assert.strictEqual(w.timers.length, 1, 'one timer, not two');
        assert.strictEqual(w.timers[0].ms, 5000, 'at the record cadence');
        assert.strictEqual(w.registered.length, 1, 'the timer is on the pause registry');
        assert.strictEqual(w.registered[0].id, w.timers[0], 'registered by id');
        await tick();
        assert.strictEqual(w.calls.length, 1, 'the first read happens at once');
        assert.strictEqual(w.calls[0].url, '/api/atlas/depth-history/BTCUSDT?minutes=30&bucket_ms=5000',
            w.calls[0].url);
        assert.strictEqual(w.section.listeners(), 2, 'two delegated handlers on the section');
        w.boot();
        assert.strictEqual(w.section.children.length, 1, 'booting twice does not mount twice');
        assert.strictEqual(w.timers.length, 1, 'and does not start a second timer');
    });

    await checkAsync('poll: a parked panel does not ask — the record is server side', async () => {
        const w = makeWorld({ active: false });
        w.boot();
        const before = w.calls.length;
        await w.dh.poll(false);
        assert.strictEqual(w.calls.length, before, 'no read while off screen');
        assert.strictEqual(w.dh.DEPTHH.skipped, 1, 'and the skip is counted');
        await w.dh.poll(true);
        assert.strictEqual(w.calls.length, before + 1, 'a forced read still happens');
    });

    await checkAsync('poll: the timer drives repeated reads and the sheet is refilled from each', async () => {
        const w = makeWorld();
        w.boot();
        await tick();
        assert.strictEqual(w.nodes.depthHistoryKpis.innerHTML.indexOf('Resting bid') > 0, true);
        assert.strictEqual(w.nodes.depthHistoryLegendText.textContent.indexOf('bucket 5 s') >= 0, true);
        assert.strictEqual(w.nodes.depthHistoryTape.innerHTML.indexOf('pulled') > 0, true);
        assert.strictEqual(w.nodes.depthHistoryStamp.textContent.indexOf('read ') === 0, true);
        await w.timers[0].fire();
        assert.strictEqual(w.calls.length, 2, 'the timer keeps reading');
    });

    await checkAsync("the window, the bucket width and the markers are the panel's own options", async () => {
        const w = makeWorld();
        w.boot();
        await tick();
        w.nodes.depthHistoryWindow.value = '5';
        w.section.fire('change', { target: w.nodes.depthHistoryWindow });
        await tick();
        assert.strictEqual(w.dh.DEPTHH.minutes, 5);
        assert.strictEqual(w.calls[w.calls.length - 1].url.indexOf('minutes=5') > 0, true);
        w.nodes.depthHistoryBucket.value = '1000';
        w.section.fire('change', { target: w.nodes.depthHistoryBucket });
        await tick();
        assert.strictEqual(w.calls[w.calls.length - 1].url.indexOf('bucket_ms=1000') > 0, true);
        w.nodes.depthHistoryMarkers.checked = false;
        w.section.fire('change', { target: w.nodes.depthHistoryMarkers });
        await tick();
        assert.strictEqual(w.dh.DEPTHH.markers, false);
        assert.strictEqual(w.calls[w.calls.length - 1].url.indexOf('events=0') > 0, true);
        const before = w.calls.length;
        w.section.fire('click', { target: w.nodes.depthHistoryRefresh });
        await tick();
        assert.strictEqual(w.calls.length, before + 1, 'the Refresh button reads again');
    });

    await checkAsync('poll: the newest ask wins — an older answer cannot repaint (the D-10 shape)', async () => {
        const w = makeWorld();
        const deferred = [];
        w.call = (url) => new Promise((resolve) => { deferred.push({ url: String(url), resolve: resolve }); });
        w.boot();
        await tick();
        assert.strictEqual(deferred.length, 1, 'the boot poll is in flight');
        w.section.fire('click', { target: w.nodes.depthHistoryRefresh });
        await tick();
        assert.strictEqual(deferred.length, 2, 'a second read is now the newest ask');
        const newer = payload({ bucket_ms: 15000, bucket_ms_requested: 15000 });
        const older = payload({ bucket_ms: 1000, bucket_ms_requested: 1000 });
        deferred[1].resolve({ ok: true, status: 200, json: () => Promise.resolve(newer) });
        await tick();
        assert.strictEqual(w.dh.DEPTHH.last.bucket_ms, 15000, 'the newest answer painted');
        deferred[0].resolve({ ok: true, status: 200, json: () => Promise.resolve(older) });
        await tick();
        assert.strictEqual(w.dh.DEPTHH.last.bucket_ms, 15000,
            'the older answer arrived last and must not repaint');
    });

    await checkAsync("poll: another instrument's answer is dropped, never adopted", async () => {
        const w = makeWorld();
        const deferred = [];
        w.call = (url) => new Promise((resolve) => { deferred.push({ url: String(url), resolve: resolve }); });
        w.boot();
        await tick();
        const foreign = payload({ symbol: 'ETHUSDT' });
        deferred[0].resolve({ ok: true, status: 200, json: () => Promise.resolve(foreign) });
        await tick();
        assert.strictEqual(w.dh.DEPTHH.last, null, "a foreign symbol may not become the strip's record");
    });

    await checkAsync('the tape: a level that was not there before says so, never a share it did not measure', async () => {
        const w = makeWorld({ payload: () => payload({ events: [
            { kind: 'add', ts_ms: 1700000010000, price: 100.5, side: 'ask', size: 30, from: 0, to: 30, pct: null },
            { kind: 'pull', ts_ms: 1700000005000, price: 99.5, side: 'bid', size: 25, from: 40, to: 15, pct: 0.62 },
        ] }) });
        w.boot();
        await tick();
        const html = w.nodes.depthHistoryTape.innerHTML;
        assert.strictEqual(html.indexOf('new level') > 0, true, 'the brand-new level is named, not scored');
        assert.strictEqual(html.indexOf('62%') > 0, true, 'a measured share still prints');
        assert.strictEqual(html.indexOf('100%') > 0, false, 'nothing claims a 100% that was never measured');
    });

    await checkAsync('the keep control: the presets say where the full range lives', async () => {
        const w = makeWorld();
        w.boot();
        await tick();
        const card = w.doc.getElementById('depthHistoryCard');
        assert.strictEqual(card.innerHTML.indexOf('any value from 1 to 1440') > 0, true,
            'the Keep control says where the full range is set');
    });

    await checkAsync('retention: the keep control POSTs, and the answer is what the panel adopts', async () => {
        const w = makeWorld();
        w.boot();
        await tick();
        const res = await w.dh.setRetention(120);
        assert.strictEqual(w.posts.length, 1, 'one POST');
        assert.strictEqual(w.posts[0].url, '/api/atlas/depth-history/retention');
        assert.deepStrictEqual(w.posts[0].body, { retention_minutes: 120 });
        assert.strictEqual(res.settings.retention_minutes, 120);
        assert.strictEqual(w.dh.DEPTHH.keep, 120, 'the applied value, not the request');
        assert.strictEqual(w.nodes.depthHistoryNote.textContent.indexOf('keeping 120 min') === 0, true);
        /* §148 / D2: the next poll must not wipe the confirmation. This is the finding: the note
           read "keeping 120 min of depth" for less than the 5 s poll interval, because dhApply
           wrote the legend onto the same line. A held note now keeps the line. */
        w.dh.apply(payload());
        assert.strictEqual(w.nodes.depthHistoryNote.textContent.indexOf('keeping 120 min') === 0, true,
            'the poll clobbered the confirmation: ' + w.nodes.depthHistoryNote.textContent);
        /* …and the legend takes the line back once the hold has expired. */
        w.dh.DEPTHH.noteUntil = 0;
        w.dh.apply(payload());
        assert.strictEqual(w.nodes.depthHistoryNote.textContent.indexOf('4 buckets') === 0, true,
            'the legend never came back: ' + w.nodes.depthHistoryNote.textContent);
    });

    await checkAsync('a refusal from the engine is shown, never swallowed', async () => {
        const w = makeWorld();
        w.reply = { ok: false, detail: 'could not change the depth retention — the settings were left alone' };
        w.boot();
        await tick();
        await w.dh.setRetention(60);
        assert.ok(w.nodes.depthHistoryNote.textContent.indexOf('engine refused') >= 0,
            w.nodes.depthHistoryNote.textContent);
        assert.strictEqual(w.dh.DEPTHH.keep, 30, 'the panel keeps what it had');
    });

    await checkAsync('clear: forgets the record for the symbol box and reads again', async () => {
        const w = makeWorld();
        w.boot();
        await tick();
        await w.dh.clear();
        const post = w.posts.filter((p) => p.url === '/api/atlas/depth-history/clear')[0];
        assert.ok(post, 'a clear POST');
        assert.deepStrictEqual(post.body, { symbol: 'BTCUSDT' });
        assert.ok(w.nodes.depthHistoryNote.textContent.indexOf('forgot the depth recorded for BTCUSDT') >= 0,
            w.nodes.depthHistoryNote.textContent);
        w.section.fire('click', { target: w.nodes.depthHistoryClear });
    });

    await checkAsync('a blank symbol box refuses politely instead of reading a path with no instrument', async () => {
        const w = makeWorld({ symbol: '' });
        w.boot();
        await tick();
        assert.strictEqual(w.calls.length, 0, 'nothing fetched');
        assert.ok(w.nodes.depthHistoryNote.textContent.indexOf('pick an instrument') >= 0,
            w.nodes.depthHistoryNote.textContent);
    });

    await checkAsync('a read that fails or answers nothing says so and keeps the last strip', async () => {
        const failed = makeWorld();
        failed.boot();
        await tick();
        const drawn = failed.nodes.depthHistoryCanvas.calls.length;
        failed.fail = true;
        await failed.dh.poll(true);
        assert.ok(failed.nodes.depthHistoryNote.textContent.indexOf('did not answer') >= 0,
            failed.nodes.depthHistoryNote.textContent);
        assert.ok(failed.nodes.depthHistoryCanvas.calls.length >= drawn, 'the strip is still there');

        const hollow = makeWorld({ empty: true });
        hollow.boot();
        await tick();
        assert.ok(hollow.nodes.depthHistoryNote.textContent.indexOf('answered nothing') >= 0,
            hollow.nodes.depthHistoryNote.textContent);
    });

    await checkAsync('stop: clears the timer, releases the pause entry, unhooks the section', async () => {
        const w = makeWorld();
        w.boot();
        await tick();
        assert.strictEqual(w.section.listeners(), 2, 'two delegated handlers + the boot listener');
        w.dh.stop();
        assert.strictEqual(w.cleared.length, 1, 'the timer is cleared');
        assert.strictEqual(w.dh.DEPTHH.timer, null);
        assert.strictEqual(w.dh.DEPTHH.polling, 'idle');
        assert.strictEqual(w.unregistered, 1, 'and handed back to the pause registry');
        assert.strictEqual(w.section.listeners(), 0, 'no handler left on the section');
        assert.strictEqual(w.doc.listenerCount('DOMContentLoaded'), 0, 'and no boot hook either');
    });

    await checkAsync('with a transport helper loaded, the panel uses it rather than a bare fetch', async () => {
        const w = makeWorld({ api: true });
        w.boot();
        await tick();
        assert.strictEqual(w.calls.length, 1);
        assert.strictEqual(w.calls[0].options, null, 'window.api(path) — no options object');
    });

    console.log('depth history selftest: ' + ok + ' ok, ' + failures.length + ' failed');
    for (const f of failures) console.log('  FAIL', f);
    process.exit(failures.length ? 1 : 0);
})();
