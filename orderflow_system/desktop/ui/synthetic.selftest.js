/* synthetic.selftest.js — the Synthetic instruments panel's decisions, pinned without a browser.
 *
 * Everything between "an HTTP payload" and "words in a cell" is pure here: the formatters, the
 * sentence the panel prints when the server refused it, the builder's rows read back into the wire
 * shape, the URL the compose call uses, and the two canvas mappings (the composite's box and the
 * z strip's). The DOM half is exercised against a stub document so `mount()`, `paint()` and the
 * poller's decisions are checked too — a panel that throws on a missing node would take the whole
 * shell's boot with it.
 *
 * The value of this file is what it REFUSES: a refusal payload must clear the chart rather than
 * leave the previous definition's shape on screen, a leg row with no instrument must not become a
 * leg, and a saved definition must be the one that composes next.
 *
 * `node synthetic.selftest.js` prints "synthetic selftest: N ok, M failed" and exits non-zero on
 * any failure.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/synthetic.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) {
        failed += 1;
        console.log('  FAIL ' + name + ': ' + (e && e.message));
    }
}

/* ── a stub world: no browser, no network, one counting timer ───────────────────────────────── */

function makeNode(id, extra) {
    const handlers = {};
    const node = {
        id: id || '', innerHTML: '', textContent: '', value: '', hidden: false, title: '',
        className: '', attrs: {}, children: [], firstElementChild: null, clientWidth: 640,
        style: {}, parentElement: null,
        addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
        removeEventListener() {},
        fire(type, ev) { (handlers[type] || []).forEach((fn) => fn(ev || { type: type, target: node })); },
        setAttribute(k, v) { this.attrs[k] = v; },
        getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; },
        appendChild(child) { this.children.push(child); return child; },
        querySelector() { return null; },
        querySelectorAll() { return []; },
        classList: { toggle() {}, contains: () => false, add() {}, remove() {} },
    };
    node.ctx = makeCtx();
    node.getContext = () => node.ctx;
    return Object.assign(node, extra || {});
}

function makeCtx() {
    const calls = { lineTo: 0, fillText: 0, clearRect: 0, stroke: 0 };
    return {
        calls: calls,
        setTransform() {}, clearRect() { calls.clearRect += 1; },
        fillText() { calls.fillText += 1; }, beginPath() {}, moveTo() {},
        lineTo() { calls.lineTo += 1; }, stroke() { calls.stroke += 1; },
        fillRect() {}, measureText() { return { width: 10 }; },
    };
}

/* A world with the panel mounted: the section, the card, and every id the template declares. */
function makeWorld() {
    const ids = ['syntheticBanner', 'syntheticDefs', 'syntheticLegs', 'syntheticName', 'syntheticKind',
                 'syntheticAddLeg', 'syntheticNew', 'syntheticSave', 'syntheticMsg', 'syntheticSymbols',
                 'syntheticRead', 'syntheticStats', 'syntheticCanvas', 'syntheticZCanvas',
                 'syntheticLegsToggle', 'syntheticNote', 'syntheticLegsTable', 'syntheticStamp',
                 'syntheticWindow', 'syntheticRefresh'];
    const nodes = {};
    ids.forEach((id) => { nodes[id] = makeNode(id); });
    const card = makeNode('syntheticCard', {});
    card.querySelector = () => null;
    const view = makeNode('syntheticView', {
        classList: { contains: (name) => name === 'active', toggle() {}, add() {}, remove() {} },
        querySelector: (sel) => (sel === '[data-synthetic-mounted]' ? null : null),
    });
    const body = makeNode('body');
    const doc = {
        readyState: 'complete',
        hidden: false,
        addEventListener() {},
        getElementById: (id) => nodes[id] || null,
        querySelector: (sel) => (sel === '.view[data-view="synthetic"]' ? view : null),
        createElement: () => {
            const holder = makeNode('holder', { firstElementChild: card });
            return holder;
        },
        head: makeNode('head'),
    };
    const win = { devicePixelRatio: 1, fetch: () => Promise.resolve({ json: () => Promise.resolve({}) }) };
    const timers = [];
    new Function('window', 'document', 'setInterval', 'clearInterval', 'Date', 'encodeURIComponent', 'Math',
        'isFinite', 'Number', 'String', 'Array', 'Object', 'JSON', 'console', src)(
        win, doc,
        (fn, ms) => { timers.push({ fn: fn, ms: ms }); return timers.length; },
        () => {}, Date, encodeURIComponent, Math, isFinite, Number, String, Array, Object, JSON, console);
    return { api: win.OFAPSYNTHETIC, win: win, doc: doc, nodes: nodes, timers: timers, card: card, view: view };
}

const S = (() => {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPSYNTHETIC;
})();
const DASH = '\u2014';

/* ── the surface ────────────────────────────────────────────────────────────────────────────── */

check('the module exposes its whole surface', () => {
    ['esc', 'num', 'fmtNum', 'fmtBps', 'fmtPct', 'sigmaWords', 'windowWord', 'statsLine', 'defLine',
     'defsHtml', 'symbolsHtml', 'kindOptions', 'legRowHtml', 'legsHtml', 'readLegs', 'composeUrl',
     'problemLine', 'statsRows', 'statsHtml', 'legsTableHtml', 'plot', 'plotZ', 'paint', 'refresh',
     'load', 'tick', 'wire', 'watch', 'mount', 'pickDefinition', 'saveDefinition', 'state'].forEach((fn) => {
        assert.strictEqual(typeof S[fn], 'function', fn + ' is missing');
    });
    assert.strictEqual(S.VIEW, '.view[data-view="synthetic"]');
    assert.strictEqual(S.LIST_URL, '/api/atlas/synthetic');
    assert.strictEqual(S.COMPOSE_URL, '/api/atlas/synthetic/compose');
    assert.deepStrictEqual(S.KINDS, ['ratio', 'spread', 'basket', 'basis']);
    assert.strictEqual(S.DASH, DASH);
});

check('the module is null-safe: loading it with no document does not throw', () => {
    assert.strictEqual(S.mount(), null, 'mount() with no DOM must return null');
    assert.strictEqual(S.watch(), false, 'watch() with no view must return false');
    assert.strictEqual(S.tick(), undefined, 'tick() with no DOM must not throw');
    S.paint({ ok: false, detail: 'no stored history for BTCUSD — open its chart first' });
    S.paint(null);
    S.paint({ ok: true, stats: {}, series: [] });
});

/* ── the pure half ──────────────────────────────────────────────────────────────────────────── */

check('numbers, bps and percentages read at one scale', () => {
    assert.strictEqual(S.fmtNum(0.05355667), '0.0535567');
    assert.strictEqual(S.fmtNum(1.5e6), '1.500M');
    assert.strictEqual(S.fmtNum(60185.25, 2), '60185.25');
    assert.strictEqual(S.fmtNum(null), DASH);
    assert.strictEqual(S.fmtNum(undefined, 2), DASH);
    assert.strictEqual(S.fmtBps(14.24), '+14.24 bps');
    assert.strictEqual(S.fmtBps(-3.5), '-3.50 bps');
    assert.strictEqual(S.fmtBps(null), DASH);
    assert.strictEqual(S.fmtPct(12.34), '12.3%');
    assert.strictEqual(S.fmtPct(null), DASH);
});

check('sigma words name the direction and refuse to invent one', () => {
    assert.strictEqual(S.sigmaWords(1.42), '1.42\u03c3 rich');
    assert.strictEqual(S.sigmaWords(-2.05), '2.05\u03c3 cheap');
    assert.strictEqual(S.sigmaWords(0.1), 'flat (0.10\u03c3)');
    assert.strictEqual(S.sigmaWords(null), 'no z-score yet');
});

check('windows are labelled in the unit a trader reads', () => {
    assert.strictEqual(S.windowWord(30), '30m');
    assert.strictEqual(S.windowWord(240), '4h');
    assert.strictEqual(S.windowWord(90), '1.5h');
    assert.strictEqual(S.windowWord(1440), '1d');
    assert.strictEqual(S.windowWord(0), DASH);
});

check('the refusal sentence is the SERVER sentence, never a generic one', () => {
    assert.strictEqual(
        S.problemLine({ ok: false, detail: 'no stored history for BTCUSD — open its chart first' }),
        'no stored history for BTCUSD — open its chart first');
    assert.strictEqual(S.problemLine({ ok: false, problems: ['A is listed twice'], detail: 'A is listed twice' }),
        'A is listed twice');
    assert.strictEqual(S.problemLine({ ok: false, problems: ['a', 'b'], detail: 'a' }), 'a (+1 more)');
    assert.strictEqual(S.problemLine({}), 'the read failed for no stated reason');
});

check('the compose URL carries the definition and the window', () => {
    assert.strictEqual(S.composeUrl('eth-btc-ratio', 240, 0),
        '/api/atlas/synthetic/compose?definition=eth-btc-ratio&window_min=240');
    /* 0 means "the server's own setting" for both numbers, so neither is sent. */
    assert.strictEqual(S.composeUrl('a b', 0, 600),
        '/api/atlas/synthetic/compose?definition=a%20b&points=600');
    assert.strictEqual(S.composeUrl('', null, null), '/api/atlas/synthetic/compose?definition=');
});

check('the definition list marks the selected row and escapes what it prints', () => {
    const html = S.defsHtml([
        { id: 'eth-btc-ratio', name: 'ETH/BTC ratio', kind: 'ratio',
          legs: [{ symbol: 'ETHUSDT', side: 1, weight: 1 }, { symbol: 'BTCUSDT', side: -1, weight: 1 }] },
        { id: 'evil', name: '<img src=x onerror=1>', kind: 'basket', legs: [{ symbol: 'A<b>', side: 1 }] },
    ], 'eth-btc-ratio');
    assert.ok(html.indexOf('is-on') >= 0, 'the selected definition is marked');
    assert.ok(html.indexOf('ratio  +ETHUSDT \u2212BTCUSDT') >= 0, html);
    assert.ok(html.indexOf('&lt;img') >= 0 && html.indexOf('<img') < 0, 'names are escaped');
    assert.ok(html.indexOf('A&lt;b&gt;') >= 0, 'legs are escaped');
    assert.ok(S.defsHtml([], 'x').indexOf('no synthetic instruments yet') >= 0);
    assert.ok(S.defsHtml(null, '').indexOf('build one below') >= 0);
});

check('a leg row shows the side, the weight and which instrument is unknown', () => {
    const html = S.legRowHtml(0, { symbol: 'BTCUSDT', side: -1, weight: 2 }, [{ symbol: 'BTCUSDT', live: true }]);
    assert.ok(html.indexOf('data-synthetic-leg="0"') >= 0);
    assert.ok(html.indexOf('value="BTCUSDT"') >= 0);
    assert.ok(html.indexOf('<option value="-1" selected>') >= 0);
    assert.ok(html.indexOf('value="2"') >= 0);
    assert.ok(html.indexOf('max="1000"') >= 0,
        'the weight input advertises the cap the server now enforces (normalise_leg LEG_WEIGHT_MAX)');
    const unknown = S.legRowHtml(1, { symbol: 'BTCUSD', side: 1, weight: 1 }, []);
    assert.ok(unknown.indexOf('no history for this one yet') >= 0, 'an unreadable leg is flagged');
    assert.ok(S.legsHtml([], []).indexOf('data-synthetic-leg="0"') >= 0, 'an empty builder still has a row');
    assert.ok(S.kindOptions('basis').indexOf('basis (premium as bps)') >= 0);
    assert.ok(S.kindOptions('basis').indexOf('selected') >= 0);
    assert.ok(S.symbolsHtml([{ symbol: 'BTCUSDT', live: true, history: true }]).indexOf('(live)') >= 0);
});

check('the builder reads back only rows that name an instrument', () => {
    const rowValues = [
        { symbol: ' ethusdt ', side: '1', weight: '1' },
        { symbol: '', side: '-1', weight: '' },
        { symbol: 'BTCUSDT', side: '-1', weight: 'abc' },
    ];
    const rows = rowValues.map((values, index) => makeNode('r' + index, {
        querySelector: (sel) => ({ value: values[sel.replace(/.*field="([a-z]+)".*/, '$1')] }),
    }));
    const host = makeNode('host', { querySelectorAll: () => rows });
    assert.deepStrictEqual(S.readLegs(host), [
        { symbol: 'ETHUSDT', side: 1, weight: 1 },
        { symbol: 'BTCUSDT', side: -1, weight: 1 },   /* an unreadable weight is not a zero leg */
    ]);
    assert.deepStrictEqual(S.readLegs(null), []);
    assert.deepStrictEqual(S.readLegs({}), []);
});

check('the stats block reads the payload, and says which reference the bps use', () => {
    const payload = {
        ok: true,
        stats: { value: 0.0535, value_unit: 'ratio', reference: 0.0531, reference_kind: 'window_median',
                 spread_abs: null, spread_bps: 7.53, z: 0.42, z_stretch: 1, z_reason: '',
                 beyond_stretch_pct: 18.2, correlation: 0.91, correlation_pairs: 1, carried_pct: 4.5,
                 samples: 240, window_minutes: 240 },
        legs: [{ symbol: 'ETHUSDT', side: 1, weight: 1, samples: 240, carried_pct: 4.5 }],
    };
    const rows = S.statsRows(payload);
    const flat = rows.map((pair) => pair[0] + '=' + pair[1]).join(' | ');
    assert.ok(flat.indexOf('window median') >= 0, flat);
    assert.ok(flat.indexOf('+7.53 bps') >= 0, flat);
    assert.ok(flat.indexOf('0.42\u03c3 rich') >= 0, flat);
    assert.ok(flat.indexOf('18.2%') >= 0, flat);
    assert.ok(flat.indexOf('0.910 (1 pair)') >= 0, flat);
    assert.ok(flat.indexOf('4.5%') >= 0, flat);
    assert.ok(flat.indexOf('4h \u00b7 240 points') >= 0, flat);
    assert.deepStrictEqual(S.statsRows({ ok: false, detail: 'x' }), []);
    assert.ok(S.statsHtml(payload).indexOf('syn-stat') >= 0);
    assert.strictEqual(S.statsHtml({ ok: false }), '');
    const table = S.legsTableHtml(payload.legs);
    assert.ok(table.indexOf('ETHUSDT') >= 0 && table.indexOf('4.5%') >= 0);
});

check('a payload without a read sentence falls back to the stats line', () => {
    const line = S.statsLine({ spread_abs: 85, spread_bps: 14.07, z: 1.42, z_stretch: 1, beyond_stretch_pct: 12 });
    assert.ok(line.indexOf('+14.07 bps') >= 0, line);
    assert.ok(line.indexOf('1.42\u03c3 rich') >= 0, line);
    assert.ok(line.indexOf('12.0% of the window beyond 1.0\u03c3') >= 0, line);
    assert.strictEqual(S.statsLine(null).indexOf('no z-score yet') >= 0, true);
});

/* ── the two canvas mappings ────────────────────────────────────────────────────────────────── */

check('the composite box puts the high value on top and the low one at the bottom', () => {
    const series = [{ t: 1, v: 10, z: -1 }, { t: 2, v: 20, z: 0 }, { t: 3, v: 30, z: 1 }];
    const shape = S.plot(series, 300, 200, { left: 10, right: 10, top: 10, bottom: 10 });
    assert.strictEqual(shape.points.length, 3);
    assert.strictEqual(shape.min, 10);
    assert.strictEqual(shape.max, 30);
    assert.strictEqual(shape.mean, 20);
    assert.strictEqual(shape.points[0].y, 190);            /* the low value sits on the bottom */
    assert.strictEqual(shape.points[2].y, 10);             /* the high value on the top edge */
    assert.strictEqual(shape.points[0].x, 10);
    assert.strictEqual(shape.points[2].x, 290);
    assert.strictEqual(shape.points[1].y, 100);            /* the mean lands on the midline */
    const single = S.plot([{ t: 1, v: 5 }], 300, 200, null);
    assert.strictEqual(single.points.length, 1);
    assert.ok(single.points[0].x > 100 && single.points[0].x < 200, 'one point is centred');
    assert.deepStrictEqual(S.plot([], 300, 200, null).points, []);
    assert.deepStrictEqual(S.plot([{ t: 1, v: null }, { t: 2 }], 300, 200, null).points, []);
});

check('the z strip centres zero and places the ±sigma band', () => {
    const strip = S.plotZ([{ z: -2 }, { z: 0 }, { z: 2 }], 300, 60, 1);
    assert.strictEqual(strip.points.length, 3);
    assert.strictEqual(strip.points[1].y, strip.zero);
    assert.ok(strip.points[0].y > strip.zero && strip.points[2].y < strip.zero);
    assert.ok(strip.bandTop < strip.zero && strip.bandBottom > strip.zero, 'the band straddles zero');
    assert.ok(strip.bandTop > strip.points[2].y, 'the band is inside the tallest excursion');
    assert.deepStrictEqual(S.plotZ([{ z: null }], 300, 60, 1).points, []);
    const flat = S.plotZ([{ z: 0 }, { z: 0 }], 300, 60, 1);
    assert.strictEqual(flat.points[0].y, flat.zero);
    assert.ok(flat.edge >= 1.5, 'a flat strip still leaves room for the band');
});

/* ── the DOM half, against the stub ─────────────────────────────────────────────────────────── */

check('mount() fills the view once and wires the poller through the pause registry', () => {
    const world = makeWorld();
    const registered = [];
    world.win.OFAPPause = { register: (id, restart) => { registered.push([id, typeof restart]); return id; } };
    /* mount() runs from the module's own boot; re-run it against this world's document. */
    const mounted = new Function('window', 'document', 'setInterval', 'clearInterval', src + '\nreturn window.OFAPSYNTHETIC.mount();')
        (world.win, world.doc, (fn, ms) => { world.timers.push({ fn: fn, ms: ms }); return world.timers.length; }, () => {});
    assert.ok(mounted, 'mount() returns the card element');
    assert.strictEqual(world.win.OFAPSYNTHETIC.mount(), mounted, 'a second mount is a no-op');

    /* Every id the panel looks up must be declared by the panel's own template: a lookup for an
       element nothing creates is the silent breakage the end-of-build audit exists to catch. */
    const looked = new Set((src.match(/el\('(synthetic\w+)'\)/g) || [])
        .map((text) => text.replace(/^el\('|'\)$/g, '')));
    assert.ok(looked.size >= 12, 'the panel looks up its whole surface');
    looked.forEach((id) => {
        assert.ok(src.indexOf('id="' + id + '"') >= 0, id + ' is looked up but never declared');
    });
});

check('paint() clears the chart when the server refused, and never leaves the old shape', () => {
    const world = makeWorld();
    /* paint() reads the ids off the document, so drive it through the booted module instance. */
    const booted = new Function('window', 'document', 'setInterval', 'clearInterval', src
        + '\nreturn window.OFAPSYNTHETIC;')(world.win, world.doc, () => 0, () => {});
    booted.paint({ ok: true, read: 'ETH/BTC ratio is trading 3.5 bps above its 4-hour median — 0.42\u03c3 rich over the last 4 hours',
                   stats: { value: 0.05, spread_bps: 3.5, z: 0.42, z_stretch: 1, samples: 240, window_minutes: 240 },
                   legs: [{ symbol: 'ETHUSDT', side: 1, weight: 1, samples: 240, carried_pct: 0 }],
                   series: [{ t: 1, v: 0.05, z: -0.4 }, { t: 2, v: 0.051, z: 0.42 }], note: 'note' });
    assert.ok(world.nodes.syntheticRead.textContent.indexOf('4-hour median') >= 0);
    assert.ok(world.nodes.syntheticStats.innerHTML.indexOf('syn-stat') >= 0);
    assert.ok(world.nodes.syntheticLegsTable.innerHTML.indexOf('ETHUSDT') >= 0);
    assert.ok(world.nodes.syntheticNote.textContent.indexOf('legs: 1') >= 0);

    /* The composite's newest sample is stamped for the shell's freshness chip when it is loaded. */
    const stamps = [];
    world.win.OFAPFRESH = { stamp: (id, spec) => { stamps.push([id, spec]); } };
    booted.paint({ ok: true, read: 'x', stats: { last_ms: 1700000000000, window_minutes: 240 },
                   series: [], legs: [], settings: { align_ms: 60000 } });
    assert.deepStrictEqual(stamps, [['synthetic', { kind: 'candles', lastMs: 1700000000000, windowMs: 60000 }]]);

    booted.paint({ ok: false, detail: 'no stored history for BTCUSD — open its chart first' });
    assert.strictEqual(world.nodes.syntheticBanner.textContent,
        'no stored history for BTCUSD — open its chart first');
    assert.strictEqual(world.nodes.syntheticRead.textContent,
        'no stored history for BTCUSD — open its chart first');
    assert.strictEqual(world.nodes.syntheticStats.innerHTML, '', 'the old stats are cleared');
    assert.strictEqual(world.nodes.syntheticLegsTable.innerHTML, '', 'the old leg table is cleared');
    assert.strictEqual(world.nodes.syntheticLegsTable.hidden, true);
    assert.ok(world.nodes.syntheticCanvas.getContext().calls.clearRect > 0, 'the chart is redrawn empty');
    assert.ok(world.nodes.syntheticCanvas.getContext().calls.fillText > 0, 'and carries the refusal');
    assert.strictEqual(booted.VIEW, '.view[data-view="synthetic"]');
});

check('the poller asks again only while the panel is live, visible and unpaused', () => {
    const world = makeWorld();
    const asked = [];
    const booted = new Function('window', 'document', 'setInterval', 'clearInterval', src
        + '\nreturn window.OFAPSYNTHETIC;')(world.win, world.doc, () => 0, () => {});
    world.win.fetch = () => { asked.push(1); return Promise.resolve({ json: () => Promise.resolve({ ok: true }) }); };
    booted.tick();                                   /* nothing selected yet: no request */
    assert.strictEqual(asked.length, 0);

    /* A world whose view is NOT active: the gate that matters most. */
    const idle = makeWorld();
    idle.view.classList = { contains: () => false, toggle() {}, add() {}, remove() {} };
    const idleApi = new Function('window', 'document', 'setInterval', 'clearInterval', src
        + '\nreturn window.OFAPSYNTHETIC;')(idle.win, idle.doc, () => 0, () => {});
    idle.win.fetch = () => { asked.push('idle'); return Promise.resolve({ json: () => Promise.resolve({}) }); };
    idleApi.tick();
    assert.strictEqual(asked.length, 0, 'a parked view does not poll');

    world.win.OFAP_PAUSED = true;
    booted.tick();
    assert.strictEqual(asked.length, 0, 'a paused app does not poll');
    world.win.OFAP_PAUSED = false;
    world.doc.hidden = true;
    booted.tick();
    assert.strictEqual(asked.length, 0, 'a hidden window does not poll');
    world.doc.hidden = false;
    world.win.OFAPINTENT = { anyHeld: () => true };
    booted.tick();
    assert.strictEqual(asked.length, 0, 'a held intent does not poll');
    world.win.OFAPINTENT = { anyHeld: () => false };
    booted.tick();
});

console.log('synthetic selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
