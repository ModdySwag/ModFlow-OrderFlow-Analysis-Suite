/* shell.selftest.js — the terminal host's maths and layout rules, as behaviour rather than prose.
 *
 * The DOM half of shell.js needs a browser; this half does not, and it is the half that decides
 * whether a stored arrangement can be honoured: rect clamping, slot finding, tiling, and the
 * normaliser that drops panels this build does not have.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/shell.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* No document: the module must load and expose its maths anyway (a Node run, a headless probe). */
function boot() {
    const win = {};
    new Function('window', 'document', src)(win, undefined);
    return win.OFAPSHELL;
}

const SHELL = boot();
const M = SHELL.math;
const GRID = { cols: 12, rows: 8 };

function inside(rect, grid) {
    const g = grid || GRID;
    return rect.x >= 0 && rect.y >= 0 && rect.x + rect.w <= g.cols && rect.y + rect.h <= g.rows
        && rect.w >= 1 && rect.h >= 1;
}

check('the shell is exposed without a document', () => {
    assert(SHELL && typeof SHELL.switchTo === 'function', 'switchTo');
    assert(typeof SHELL.focusView === 'function' && typeof SHELL.openWidget === 'function', 'widget API');
    assert(typeof SHELL.stats === 'function' && typeof SHELL.activateTab === 'function', 'telemetry');
    assert(typeof SHELL.bounds === 'function' && typeof SHELL.maximise === 'function', 'chrome API');
    assert(typeof SHELL.addTab === 'function' && typeof SHELL.closeTab === 'function'
           && typeof SHELL.reorderTabs === 'function', 'tab API');
    assert(M && typeof M.normaliseLayout === 'function', 'math');
});

check('it reports classic mode when it cannot see a page', () => {
    const st = SHELL.stats();
    assert.strictEqual(st.mode, 'classic');
    assert.strictEqual(st.widgets, 0);
    assert.deepStrictEqual(st.unplaced, []);
});

check('a rect is clamped size-first, then position', () => {
    assert.deepStrictEqual(M.clampRect({ x: 99, y: 99, w: 12, h: 8 }, GRID), { x: 0, y: 0, w: 12, h: 8 });
    assert.deepStrictEqual(M.clampRect({ x: -5, y: -5, w: 6, h: 4 }, GRID), { x: 0, y: 0, w: 6, h: 4 });
    /* x is clamped against the width the same call produced, so a wide widget is pulled in */
    assert.deepStrictEqual(M.clampRect({ x: 9, y: 7, w: 6, h: 4 }, GRID), { x: 6, y: 4, w: 6, h: 4 });
    assert.deepStrictEqual(M.clampRect({ w: 0, h: 0 }, GRID), { x: 0, y: 0, w: 1, h: 1 });
    assert.deepStrictEqual(M.clampRect({ w: 'wide', h: null, x: 'left' }, GRID), { x: 0, y: 0, w: 6, h: 4 });
});

check('overlap is strict intersection, not touching', () => {
    const a = { x: 0, y: 0, w: 6, h: 4 };
    assert.strictEqual(M.overlaps(a, { x: 5, y: 3, w: 6, h: 4 }), true);
    assert.strictEqual(M.overlaps(a, { x: 6, y: 0, w: 6, h: 4 }), false, 'edge-to-edge is not overlap');
    assert.strictEqual(M.overlaps(a, { x: 0, y: 4, w: 6, h: 4 }), false);
});

check('a tile never overlaps and never leaves the grid, for any widget count', () => {
    for (let n = 1; n <= 24; n += 1) {
        const rects = M.tile(n, GRID);
        assert.strictEqual(rects.length, n, 'n=' + n);
        rects.forEach((r) => assert(inside(r), 'n=' + n + ' rect outside the grid: ' + JSON.stringify(r)));
        for (let i = 0; i < rects.length; i += 1) {
            for (let j = i + 1; j < rects.length; j += 1) {
                assert(!M.overlaps(rects[i], rects[j]), 'n=' + n + ': ' + JSON.stringify(rects[i]) + ' overlaps ' + JSON.stringify(rects[j]));
            }
        }
    }
    assert.deepStrictEqual(M.tile(0, GRID), []);
});

check('a tile of a square count covers the grid exactly', () => {
    [[1, 96], [4, 24], [9, 96 / 9]].forEach(([n, area]) => {
        const rects = M.tile(n, GRID);
        const total = rects.reduce((sum, r) => sum + r.w * r.h, 0);
        assert.strictEqual(total, area * n, 'n=' + n + ' covers ' + total + ' cells');
    });
});

check('the first free slot is found around what is already placed', () => {
    assert.deepStrictEqual(M.firstSlot([], 6, 4, GRID), { x: 0, y: 0 });
    assert.deepStrictEqual(M.firstSlot([{ x: 0, y: 0, w: 6, h: 4 }], 6, 4, GRID), { x: 6, y: 0 });
    assert.deepStrictEqual(M.firstSlot([{ x: 0, y: 0, w: 12, h: 4 }], 6, 4, GRID), { x: 0, y: 4 });
});

check('a full grid reports no slot instead of overlapping', () => {
    assert.strictEqual(M.firstSlot([{ x: 0, y: 0, w: 12, h: 8 }], 6, 4, GRID), null);
    const packed = M.tile(4, GRID);
    assert.strictEqual(M.firstSlot(packed, 6, 4, GRID), null, 'four 6x4 widgets fill the grid');
    assert.deepStrictEqual(M.firstSlot(packed, 3, 2, GRID), null, 'no 3x2 hole survives a 2x2 tiling');
});

check('the normaliser drops panels this build does not have', () => {
    const raw = { id: 'ly1', name: 'Mine', tabs: [{ id: 'main', name: 'Main', widgets: [
        { view: 'ofx', x: 0, y: 0, w: 6, h: 4 },
        { view: 'no-such-panel', x: 6, y: 0, w: 6, h: 4 },
    ] }] };
    const out = M.normaliseLayout(raw, ['ofx', 'tape'], GRID);
    assert.deepStrictEqual(out.tabs[0].widgets.map((w) => w.view), ['ofx']);
});

check('one section means one frame: a repeated view is dropped', () => {
    const raw = { id: 'ly1', tabs: [{ id: 'main', widgets: [
        { view: 'ofx', x: 0, y: 0, w: 6, h: 4 },
        { view: 'ofx', x: 6, y: 0, w: 6, h: 4 },
        { view: 'tape', x: 0, y: 4, w: 6, h: 4 },
        { view: 'tape', x: 6, y: 4, w: 6, h: 4 },
    ] }] };
    const out = M.normaliseLayout(raw, ['ofx', 'tape'], GRID);
    assert.deepStrictEqual(out.tabs[0].widgets.map((w) => w.view), ['ofx', 'tape']);
});

check('an unready DOM keeps the arrangement instead of emptying it', () => {
    const raw = { id: 'ly1', tabs: [{ id: 'main', widgets: [{ view: 'ofx', x: 0, y: 0, w: 6, h: 4 }] }] };
    const out = M.normaliseLayout(raw, [], GRID);
    assert.strictEqual(out.tabs[0].widgets.length, 1, 'no known views means "keep what is stored"');
});

check('the normaliser clamps geometry and always yields a usable layout', () => {
    const out = M.normaliseLayout({ id: 'LY 9', name: '', tabs: [{ id: 'main', widgets: [
        { view: 'ofx', x: 99, y: -3, w: 400, h: 400, link: 'abcdefghijklmnopqrstuvwxyz' },
    ] }] }, ['ofx'], GRID);
    assert.strictEqual(out.id, 'ly-9', 'ids are slugs');
    assert.strictEqual(out.name, 'Layout');
    assert(inside(out.tabs[0].widgets[0]));
    assert.strictEqual(out.tabs[0].widgets[0].link.length, 16);
    assert.strictEqual(M.normaliseLayout({}, ['ofx'], GRID).tabs.length, 1, 'at least one tab');
    assert.deepStrictEqual(M.normaliseLayout({ tabs: [] }, [], GRID).tabs[0].id, 'main');
});

check('tab ids are made unique and a layout keeps at most twelve', () => {
    const tabs = [];
    for (let i = 0; i < 20; i += 1) tabs.push({ id: 'tab', name: 'T' + i, widgets: [] });
    const out = M.normaliseLayout({ id: 'ly1', tabs: tabs }, [], GRID);
    assert.strictEqual(out.tabs.length, 12);
    const ids = out.tabs.map((t) => t.id);
    assert.strictEqual(new Set(ids).size, ids.length, 'ids must be unique: ' + ids.join(','));
});

check('a widget keeps its own settings, and only its own view', () => {
    const out = M.normaliseLayout({ id: 'ly1', tabs: [{ id: 'main', widgets: [
        { view: 'ofx', x: 0, y: 0, w: 6, h: 4, settings: { symbol: 'BTCUSDT', R: 5 }, link: 'A' },
    ] }] }, ['ofx'], GRID);
    const w = out.tabs[0].widgets[0];
    assert.deepStrictEqual(w.settings, { symbol: 'BTCUSDT', R: 5 });
    assert.strictEqual(w.link, 'A');
});

check('the starter layout only claims panels this build has', () => {
    const out = M.defaultLayout(['overview', 'ofx', 'tape', 'depth', 'logs'], GRID, 'lystart');
    assert.deepStrictEqual(out.tabs[0].widgets.map((w) => w.view), ['overview', 'ofx', 'tape', 'depth']);
    out.tabs[0].widgets.forEach((w) => assert(inside(w), JSON.stringify(w)));
    for (let i = 0; i < out.tabs[0].widgets.length; i += 1) {
        for (let j = i + 1; j < out.tabs[0].widgets.length; j += 1) {
            assert(!M.overlaps(out.tabs[0].widgets[i], out.tabs[0].widgets[j]), 'starter widgets overlap');
        }
    }
    assert.strictEqual(M.countWidgets(out), 4);
});

check('a build with none of the starter panels still gets a usable layout', () => {
    const out = M.defaultLayout(['logs', 'settings', 'guide', 'alerts', 'replay'], GRID, '');
    const views = out.tabs[0].widgets.map((w) => w.view);
    assert.deepStrictEqual(views, ['logs', 'settings', 'guide', 'alerts']);
    assert.strictEqual(out.id, 'lystart', 'a missing id falls back to a slug');
});

check('normalising a starter layout changes nothing (it is already canonical)', () => {
    const starter = M.defaultLayout(['overview', 'ofx', 'tape', 'depth'], GRID, 'lyabc');
    const again = M.normaliseLayout(starter, ['overview', 'ofx', 'tape', 'depth'], GRID);
    assert.deepStrictEqual(again.tabs, starter.tabs);
    assert.strictEqual(again.id, starter.id);
});

check('countWidgets counts across every tab', () => {
    assert.strictEqual(M.countWidgets(M.defaultLayout(['overview', 'ofx'], GRID, 'x')), 2);
    assert.strictEqual(M.countWidgets({ tabs: [{ widgets: [{}, {}] }, { widgets: [{}] }] }), 3);
    assert.strictEqual(M.countWidgets(null), 0);
});

check('a pointer maps to a grid cell, clamped at the edges', () => {
    const box = { left: 100, top: 50, width: 1200, height: 800 };
    assert.deepStrictEqual(M.cellAt({ x: 100, y: 50 }, box, GRID), { col: 0, row: 0 });
    assert.deepStrictEqual(M.cellAt({ x: 700, y: 450 }, box, GRID), { col: 6, row: 4 });
    assert.deepStrictEqual(M.cellAt({ x: 10, y: 10 }, box, GRID), { col: 0, row: 0 }, 'outside the box clamps in');
    assert.deepStrictEqual(M.cellAt({ x: 5000, y: 5000 }, box, GRID), { col: 11, row: 7 });
    assert.deepStrictEqual(M.cellAt({}, { width: 0, height: 0 }, GRID), { col: 0, row: 0 }, 'no box is not a crash');
});

check('moving a widget is clamped to the grid, however far the pointer went', () => {
    const start = { x: 2, y: 1, w: 4, h: 3 };
    assert.deepStrictEqual(M.moveRect(start, 3, 2, GRID), { x: 5, y: 3, w: 4, h: 3 });
    assert.deepStrictEqual(M.moveRect(start, 999, 999, GRID), { x: 8, y: 5, w: 4, h: 3 }, 'stops at the edge');
    assert.deepStrictEqual(M.moveRect(start, -99, -99, GRID), { x: 0, y: 0, w: 4, h: 3 });
    assert.deepStrictEqual(M.moveRect(start, 'sideways', null, GRID), { x: 2, y: 1, w: 4, h: 3 }, 'junk is no movement');
});

check('resizing keeps the corner and clamps the size', () => {
    const start = { x: 2, y: 1, w: 4, h: 3 };
    assert.deepStrictEqual(M.resizeRect(start, 2, 1, GRID), { x: 2, y: 1, w: 6, h: 4 });
    assert.deepStrictEqual(M.resizeRect(start, 99, 99, GRID), { x: 2, y: 1, w: 10, h: 7 }, 'the grid edge is the limit');
    assert.deepStrictEqual(M.resizeRect(start, -99, -99, GRID), { x: 2, y: 1, w: 1, h: 1 }, 'never below one cell');
    assert.deepStrictEqual(M.resizeRect({ x: 11, y: 7, w: 1, h: 1 }, 4, 4, GRID), { x: 11, y: 7, w: 1, h: 1 });
});

check('reordering is a pure move, and out of range changes nothing', () => {
    const tabs = ['a', 'b', 'c', 'd'];
    assert.deepStrictEqual(M.reorder(tabs, 0, 2), ['b', 'c', 'a', 'd']);
    assert.deepStrictEqual(M.reorder(tabs, 3, 0), ['d', 'a', 'b', 'c']);
    assert.deepStrictEqual(M.reorder(tabs, 1, 1), tabs);
    assert.deepStrictEqual(M.reorder(tabs, 9, 0), tabs);
    assert.deepStrictEqual(tabs, ['a', 'b', 'c', 'd'], 'the input list is never mutated');
});

console.log('shell selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
