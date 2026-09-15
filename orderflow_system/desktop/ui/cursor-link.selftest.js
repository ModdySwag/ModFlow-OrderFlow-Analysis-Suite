/* cursor-link.selftest.js — the spine's own behaviour, pinned without a browser.
 *
 * The value of this module is that every panel reads ONE cursor; the tests below hold the parts that
 * are easy to get wrong: who may clear it, what a tolerance means, that unsubscribing really stops
 * delivery, and that the badge every panel shows is driven by the store (so no panel can drift).
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/cursor-link.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    return Promise.resolve().then(fn).then(() => { ok += 1; }, (e) => {
        failed += 1;
        console.log('  FAIL ' + name + ': ' + e.message);
    });
}

function makeNode() {
    const classes = new Set();
    return {
        textContent: '', className: '', title: '', isConnected: true, children: [], attrs: {},
        setAttribute(k, v) { this.attrs[k] = v; },
        getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; },
        appendChild(c) { this.children.push(c); return c; },
        insertBefore(c) { this.children.unshift(c); return c; },
        querySelector() { return this.children.find((c) => c.attrs && c.attrs['data-ofap-badge']) || null; },
        classList: {
            toggle(name, on) { if (on === undefined) { classes.has(name) ? classes.delete(name) : classes.add(name); } else if (on) { classes.add(name); } else { classes.delete(name); } },
            contains(name) { return classes.has(name); },
        },
    };
}

function boot() {
    const doc = {
        createElement() { return makeNode(); },
        documentElement: makeNode(),
    };
    const win = { document: doc, getComputedStyle: () => ({ getPropertyValue: () => '' }) };
    new Function('window', 'document', 'getComputedStyle', src)(win, doc, win.getComputedStyle);
    return win.OFAPCURSOR;
}

(async function run() {
    await check('a publish notifies subscribers with price, time and source', () => {
        const C = boot();
        const seen = [];
        C.subscribe((s) => seen.push([s.price, s.timeMs, s.source]));
        C.move(76500.5, 1789488000000, 'heatmap');
        assert.deepStrictEqual(seen, [[76500.5, 1789488000000, 'heatmap']]);
        C.move(76500.5, 1789488000000, 'heatmap');
        assert.strictEqual(seen.length, 1, 'an unchanged publish does not wake the panels');
        C.set(76501, { timeMs: null, source: 'tape' });
        assert.strictEqual(seen.length, 2);
        assert.strictEqual(seen[1][2], 'tape');
    });

    await check('one panel cannot clear another panel\'s cursor', () => {
        const C = boot();
        C.move(100, null, 'heatmap');
        C.clear('tape');
        assert.strictEqual(C.state.price, 100, 'a foreign clear is ignored');
        C.clear('heatmap');
        assert.strictEqual(C.state.price, null, 'the owner can clear it');
    });

    await check('nearest is bounded by the tolerance and step reports the grid', () => {
        const C = boot();
        C.move(100.4, null, 'x');
        const prices = [100, 100.5, 101];
        assert.strictEqual(C.nearest(prices, null), 100.5, 'unbounded: the closest drawn price');
        assert.strictEqual(C.step(prices), 0.5);
        assert.strictEqual(C.nearest(prices, C.step(prices)), 100.5, 'within one step: a match');
        C.move(140, null, 'x');
        assert.strictEqual(C.nearest(prices, C.step(prices)), null, 'far outside: no match, no false claim');
        assert.strictEqual(C.nearest([], 1), null);
        assert.strictEqual(C.nearest(prices, null), 101, 'still reports the closest when unbounded');
    });

    await check('unsubscribe stops delivery for that panel only', () => {
        const C = boot();
        const a = [], b = [];
        const off = C.subscribe((s) => a.push(s.price));
        C.subscribe((s) => b.push(s.price));
        C.move(1, null, 'x');
        off();
        C.move(2, null, 'x');
        assert.deepStrictEqual(a, [1], 'the panel that left heard nothing more');
        assert.deepStrictEqual(b, [1, 2], 'the panel that stayed kept reading');
    });

    await check('the badge shows price and time, and every badge follows the one store', () => {
        const C = boot();
        const hostA = makeNode(), hostB = makeNode();
        const a = C.badge(hostA), b = C.badge(hostB);
        assert(a && b, 'badges are created');
        assert.strictEqual(hostA.children.length, 1, 'one badge per host, not one per call');
        assert.strictEqual(C.badge(hostA), a, 'calling badge again returns the same element');
        assert.strictEqual(a.textContent, '— · —', 'clear cursor reads as no-reading');
        C.move(76500.5, 1789488000, 'engine');            // seconds, as the engine publishes
        assert(/76500\.50 · \d\d:\d\d:\d\d/.test(a.textContent), a.textContent);
        assert.strictEqual(a.textContent, b.textContent, 'both panels read the same instant');
        assert.strictEqual(a.classList.contains('on'), true);
        C.clear('engine');
        assert.strictEqual(a.textContent, '— · —');
        assert.strictEqual(a.classList.contains('on'), false);
    });

    await check('a selection rides with the cursor without waking the panels that ignore it', () => {
        const C = boot();
        const seen = [];
        C.subscribe((s) => seen.push(s.selection));
        C.set(100, { source: 'x' });
        C.select({ t0: 1, t1: 2, price: 100 }, { source: 'x' });
        assert.strictEqual(seen.length, 2, 'the selection change is a change');
        assert.deepStrictEqual(C.state.selection, { t0: 1, t1: 2, price: 100 });
    });

    console.log('cursor-link selftest: ' + ok + ' ok, ' + failed + ' failed');
    process.exit(failed ? 1 : 0);
})();
