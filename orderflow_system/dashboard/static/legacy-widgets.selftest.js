/* legacy-widgets.selftest.js — pins the two legacy dashboard widgets in Node (no browser).
   Run: node orderflow_system/dashboard/static/legacy-widgets.selftest.js
   Prints "legacy widgets selftest: N ok, M failed" and exits non-zero on failure, so
   orderflow_system/test_legacy_widgets.py can gate it.

   D-07: the footprint chart's teardown is symmetric (every container listener it adds, it
         removes) and its series is capped.
   D-08: the performance board's list is capped and its stats come from running accumulators —
         the numbers must equal a from-scratch recompute after 10,000 adds.
*/
'use strict';
const fs = require('fs');
const path = require('path');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(`${name}${detail ? ` — ${detail}` : ''}`);
}
const near = (a, b, tol = 1e-9) => Math.abs(a - b) <= tol;

/* ── the smallest DOM the two widgets touch ─────────────────────────────────────────────── */
function makeCtx(owner) {
    const noop = () => {};
    const store = {};
    return new Proxy(store, {
        get(target, key) {
            if (key === 'canvas') return owner;
            if (key in target) return target[key];
            return noop;
        },
        set(target, key, value) { target[key] = value; return true; },
    });
}

function makeElement(tag, id) {
    const listeners = new Map();
    const el = {
        tagName: String(tag || 'div').toUpperCase(), id: id || '', className: '',
        innerHTML: '', innerText: '', textContent: '', value: '', title: '', href: '', src: '',
        style: {}, dataset: {}, children: [], listeners,
        width: 800, height: 400, clientWidth: 800, clientHeight: 400,
        offsetWidth: 800, offsetHeight: 400, scrollWidth: 800, scrollHeight: 400,
        offsetLeft: 0, offsetTop: 0, parentNode: null, disabled: false, checked: false,
        addEventListener(type, fn) { listeners.set(type, (listeners.get(type) || []).concat(fn)); },
        removeEventListener(type, fn) {
            const list = listeners.get(type) || [];
            const i = list.indexOf(fn);
            if (i >= 0) list.splice(i, 1);
            listeners.set(type, list);
        },
        appendChild(child) { el.children.push(child); if (child) child.parentNode = el; return child; },
        insertBefore(child) { el.children.unshift(child); if (child) child.parentNode = el; return child; },
        removeChild(child) { const i = el.children.indexOf(child); if (i >= 0) el.children.splice(i, 1); return child; },
        remove() { if (el.parentNode) el.parentNode.removeChild(el); },
        querySelector() { return null; },
        querySelectorAll() { return []; },
        getElementsByTagName() { return []; },
        getBoundingClientRect() { return { width: 800, height: 400, left: 0, top: 0, right: 800, bottom: 400, x: 0, y: 0 }; },
        getContext() { return makeCtx(el); },
        setAttribute() {}, removeAttribute() {}, getAttribute() { return null; },
        hasAttribute() { return false; },
        classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
        dispatchEvent() { return true; },
        focus() {}, blur() {}, click() {}, scrollTo() {}, setPointerCapture() {}, releasePointerCapture() {},
        toDataURL() { return ''; }, getContextAttributes() { return {}; },
        closest() { return null; }, matches() { return false; },
        parentElement: null, nextSibling: null, previousSibling: null, firstChild: null,
        animate() { return { cancel() {}, finish() {} }; },
    };
    // a chart looks up through parentElement for its box; give every stub one that answers
    el.parentElement = {
        style: {}, children: [],
        getBoundingClientRect() { return { width: 800, height: 400, left: 0, top: 0, right: 800, bottom: 400 }; },
        appendChild(child) { el.children.push(child); return child; },
        removeChild(child) { return child; },
        addEventListener() {}, removeEventListener() {},
        querySelector() { return null; }, querySelectorAll() { return []; },
        clientWidth: 800, clientHeight: 400,
    };
    return el;
}

const elements = new Map();
const windowListeners = new Map();
function boundAdd(map) {
    return (type, fn) => map.set(type, (map.get(type) || []).concat(fn));
}
function boundRemove(map) {
    return (type, fn) => {
        const list = map.get(type) || [];
        const i = list.indexOf(fn);
        if (i >= 0) list.splice(i, 1);
        map.set(type, list);
    };
}

global.window = {
    devicePixelRatio: 1,
    innerWidth: 1600, innerHeight: 900,
    addEventListener: boundAdd(windowListeners),
    removeEventListener: boundRemove(windowListeners),
    requestAnimationFrame: (fn) => setTimeout(fn, 0),
    cancelAnimationFrame: (h) => clearTimeout(h),
    setTimeout, clearTimeout, setInterval, clearInterval,
    matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
    PerformanceDashboard: null, FootprintChart: null,
};
global.document = {
    addEventListener: boundAdd(windowListeners),
    removeEventListener: boundRemove(windowListeners),
    getElementById(id) {
        if (!elements.has(id)) elements.set(id, makeElement('div', id));
        return elements.get(id);
    },
    createElement(tag) { return makeElement(tag, ''); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementsByTagName() { return []; },
    hidden: false, visibilityState: 'visible',
    body: null,
    documentElement: makeElement('html', ''),
};
global.document.body = makeElement('body', '');
try { Object.defineProperty(global, 'navigator', { value: { userAgent: 'node' }, configurable: true }); }
catch (err) { /* Node 21+ ships its own read-only navigator; fine. */ }
global.requestAnimationFrame = global.window.requestAnimationFrame;
global.cancelAnimationFrame = global.window.cancelAnimationFrame;
global.getComputedStyle = global.window.getComputedStyle;
global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
global.MutationObserver = class { observe() {} disconnect() {} takeRecords() { return []; } };
global.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
global.Image = class { constructor() { this.onload = null; this.onerror = null; } };

function loadScript(file) {
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8');
    try {
        // the widgets are classic scripts: they publish their constructor on `window`
        (0, eval)(src + '\n//# sourceURL=' + file);
        return true;
    } catch (err) {
        failures.push(`${file} did not evaluate in the DOM stub — ${err && err.message}`);
        return false;
    }
}

/* ── D-07: the footprint chart's teardown ──────────────────────────────────────────────── */
check('the legacy widgets evaluate in the stub', loadScript('footprint.js') && loadScript('performance.js'),
    failures[failures.length - 1] || '');

const Footprint = global.window.FootprintChart;
check('D-07: FootprintChart is published', typeof Footprint === 'function');

if (typeof Footprint === 'function') {
    const container = global.document.getElementById('fpSelftest');
    const chart = new Footprint('fpSelftest', {});
    const added = ['mousedown', 'mousemove', 'mouseup', 'mouseleave', 'wheel',
                   'touchstart', 'touchmove', 'touchend'].filter((t) => (container.listeners.get(t) || []).length);
    check('D-07: the chart subscribes every pointer path it handles', added.length === 8, added.join(','));
    const resizeBefore = (windowListeners.get('resize') || []).length;
    chart.destroy();
    const leftover = ['mousedown', 'mousemove', 'mouseup', 'mouseleave', 'wheel',
                      'touchstart', 'touchmove', 'touchend']
        .filter((t) => (container.listeners.get(t) || []).length);
    check('D-07: destroy() removes every container listener it added', leftover.length === 0, leftover.join(','));
    check('D-07: destroy() removes its window resize listener',
        (windowListeners.get('resize') || []).length === resizeBefore - 1,
        String((windowListeners.get('resize') || []).length));

    const chart2 = new Footprint('fpSelftest2', {});
    for (let i = 0; i < 1200; i += 1) {
        chart2.updateBar({ time: 1700000000000 + i * 60000, open: 100, high: 101, low: 99, close: 100 + (i % 3), volume: 10 });
    }
    check('D-07: updateBar keeps the series bounded (600 bars, visible window + margin)',
        chart2.data.length === 600, String(chart2.data.length));
}

/* ── D-08: the performance board's stats ───────────────────────────────────────────────── */
const Board = global.window.PerformanceDashboard;
check('D-08: PerformanceDashboard is published', typeof Board === 'function');

if (typeof Board === 'function') {
    const make = () => {
        const board = new Board('perfSelftest', {});
        if (typeof board._render === 'function') board._render = () => {};   // the stub cannot paint
        return board;
    };
    const board = make();
    let recomputes = 0;
    const realRecalc = board._recalculateStats.bind(board);
    board._recalculateStats = function () { recomputes += 1; return realRecalc(); };

    const trades = [];
    for (let i = 0; i < 10000; i += 1) {
        const pnl = ((i * 37) % 211) - 100;                       // -100..110, deterministic
        const trade = { id: i, pnl, rMultiple: pnl / 50, pattern: ['A', 'B', 'C'][i % 3],
                        timestamp: Date.now() - (i % 5) * 60000 };
        trades.push(trade);
        board.addTrade(trade);
    }
    check('D-08: 10,000 adds leave the list capped at 2,000', board.trades.length === 2000,
        String(board.trades.length));
    check('D-08: no add re-ran the stats pass (the debounce owns it)', recomputes === 0,
        `${recomputes} recomputes during the adds`);

    board._recalculateStats();                                     // flush the debounced pass
    check('D-08: the flush computes once', recomputes === 1, String(recomputes));

    // parity: the same 2,000 trades through a board that builds its stats from scratch
    const fresh = make();
    fresh.setTrades(board.trades.slice());
    const a = board.stats, b = fresh.stats;
    check('D-08: the incremental stats equal a from-scratch recompute',
        a.totalTrades === b.totalTrades && a.wins === b.wins && a.losses === b.losses
        && a.breakevens === b.breakevens && near(a.totalPnL, b.totalPnL)
        && near(a.maxDrawdown, b.maxDrawdown) && near(a.currentDrawdown, b.currentDrawdown)
        && near(a.avgWin, b.avgWin) && near(a.avgLoss, b.avgLoss) && near(a.avgRR, b.avgRR)
        && near(a.expectancy, b.expectancy) && a.tradesToday === b.tradesToday,
        JSON.stringify([a, b]));
    const canonical = (table) => JSON.stringify(Object.keys(table).sort().map((k) => [k, table[k]]));
    check('D-08: the pattern table matches too (same keys, same numbers)',
        canonical(a.byPattern) === canonical(b.byPattern),
        JSON.stringify([a.byPattern, b.byPattern]));
}

console.log(`legacy widgets selftest: ${ok} ok, ${failures.length} failed`);
failures.forEach((f) => console.log(`  FAIL ${f}`));
process.exit(failures.length ? 1 : 0);
