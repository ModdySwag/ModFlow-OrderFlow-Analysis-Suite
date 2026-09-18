/* freshness.selftest.js — the store's own behaviour, pinned without a browser.
 *
 * The value of this module is the VERDICT: demo beats an age, an unknown clock stays unknown, a
 * deliberate hold is not a fault, and the age boundary (half window → aging, past window → stale)
 * is arithmetic, not vibes. `node desktop/ui/freshness.selftest.js` prints
 * "freshness selftest: N ok, M failed" and exits non-zero on any failure, so test_freshness.py
 * can gate the suite on it.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/freshness.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

function makeNode(tag) {
    const classes = new Set();
    const node = {
        tagName: tag || 'SPAN', textContent: '', className: '', title: '', isConnected: true,
        attrs: {}, children: [],
        setAttribute(k, v) { this.attrs[k] = v; },
        getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; },
        appendChild(c) { c.__parent = this; this.children.push(c); return c; },
        querySelector() { return this.children.find((c) => c.attrs && c.attrs['data-ofap-fresh']) || null; },
        closest(sel) {
            if (sel !== '.view') return null;
            let node = this;
            while (node) {
                if (node.__section) return node.__section;
                node = node.__parent;
            }
            return null;
        },
        classList: {
            toggle(name, on) { if (on === undefined) { classes.has(name) ? classes.delete(name) : classes.add(name); } else if (on) { classes.add(name); } else { classes.delete(name); } },
            contains(name) { return classes.has(name); },
        },
    };
    return node;
}

function boot() {
    const doc = {
        readyState: 'complete',
        addEventListener() {},
        createElement(tag) { return makeNode(tag); },
        querySelector() { return null; },
    };
    const win = {};
    /* A no-op setInterval: the module's 1 s tick must not keep the Node process alive. */
    new Function('window', 'document', 'setInterval', src)(win, doc, () => 0);
    return win.OFAPFRESH;
}

/* ── the verdict ─────────────────────────────────────────────────────────── */

{
    const F = boot();
    check('pick: under half the window is fresh', F.pick({ age: 2000, window: 5000, ageKnown: true }) === 'fresh');
    check('pick: half the window starts aging', F.pick({ age: 2500, window: 5000, ageKnown: true }) === 'aging');
    check('pick: past the window is stale', F.pick({ age: 5001, window: 5000, ageKnown: true }) === 'stale');
    check('pick: exactly at the window is still aging (the arrow, not the blade)',
        F.pick({ age: 5000, window: 5000, ageKnown: true }) === 'aging');
    check('pick: demo beats any age', F.pick({ age: 60000, window: 5000, ageKnown: true, source: 'demo' }) === 'demo');
    check('pick: an unknown clock stays unknown, never stale',
        F.pick({ age: 0, window: 5000, ageKnown: false }) === 'unknown');
    check('pick: a user hold is not a fault', F.pick({ age: 20000, window: 5000, ageKnown: true, paused: true }) === 'held');
    check('pick: no state at all is unknown', F.pick(null) === 'unknown');
}

/* ── display ─────────────────────────────────────────────────────────────── */

{
    const F = boot();
    check('fmtAge: seconds under 100', F.fmtAge(0) === '0 s' && F.fmtAge(2600) === '3 s' && F.fmtAge(65000) === '65 s');
    check('fmtAge: minutes past 100 s carry padded seconds', F.fmtAge(125000) === '2 m 05 s' && F.fmtAge(100000) === '1 m 40 s');
    check('fmtAge: hours', F.fmtAge(3_600_000 + 240_000) === '1 h 4 m');
    check('textFor: the words per verdict',
        F.textFor({ age: 7000 }, 'stale') === 'stale — no update for 7 s'
        && F.textFor({ age: 0 }, 'demo') === 'demo data'
        && F.textFor({ age: 0 }, 'unknown') === 'age unknown'
        && F.textFor({ age: 12000 }, 'held') === 'held · 12 s');
}

/* ── the store ───────────────────────────────────────────────────────────── */

{
    const F = boot();
    const before = Date.now();
    const row = F.stamp('ofx', { lastMs: Date.now() - 3000, kind: 'candles' });
    check('stamp: a lastMs stamp is a known age', row.ageKnown === true && row.lastMs > 0);
    check('stamp: the kind picks the window', row.windowMs === 60000);
    const st = F.state(row);
    check('stamp: the age is measured from lastMs (rising with the clock)',
        st.age >= 3000 && st.age <= Date.now() - before + 3100, String(st.age));
    const now = F.stamp('now', { ageMs: 0, kind: 'trades' });
    check('stamp: ageMs 0 is a KNOWN, fresh age (a just-now fetch)',
        now.ageKnown === true && now.windowMs === 5000 && F.pick(F.state(now)) === 'fresh');
    const demo = F.stamp('demo-panel', { source: 'demo' });
    check('stamp: a demo source has no age', demo.ageKnown === false && F.pick(F.state(demo)) === 'demo');
    const unknown = F.stamp('mystery', {});
    check('stamp: no clock at all is unknown', unknown.ageKnown === false && F.pick(F.state(unknown)) === 'unknown');
    const override = F.stamp('custom', { ageMs: 100, windowMs: 250 });
    check('stamp: an explicit window beats the kind table', override.windowMs === 250);
    check('list(): one row per stamped panel with its verdict',
        F.list().length === 5 && F.list().filter((r) => r.id === 'ofx')[0].verdict === 'fresh');
}

/* ── the chip ────────────────────────────────────────────────────────────── */

{
    const F = boot();
    const head = makeNode('DIV');
    const section = makeNode('SECTION');
    head.__section = section;
    const el = F.chip(head, 'ofx');
    check('chip: an unstamped panel reads an em dash', el.textContent === '—');
    F.stamp('ofx', { lastMs: Date.now() - 8000, kind: 'trades' });
    const el2 = head.querySelector('[data-ofap-fresh]');
    check('chip: a stale age explains itself', el2.textContent.indexOf('stale — no update for 8 s') === 0);
    check('chip: the state is a class', el2.className === 'ofap-fresh-chip is-stale');
    check('chip: the section dims, never hides', section.classList.contains('ofap-stale') === true);
    F.stamp('ofx', { lastMs: Date.now(), kind: 'trades' });
    check('chip: a fresh stamp clears the stale class',
        section.classList.contains('ofap-stale') === false && el2.className === 'ofap-fresh-chip is-fresh');
    check('chip: created once, reused on the next call', F.chip(head, 'ofx') === el2 && head.children.length === 1);
}

/* ── T4/A5: the user's thresholds ───────────────────────────────── */

{
    const F = boot();
    check('windows: the built-in table when the user set nothing',
        F.window('depth') === 5000 && F.window('candles') === 60000);
    const aged = F.stamp('aged', { lastMs: Date.now() - 8000, kind: 'depth' });
    check('windows: under the built-in window an 8 s age is stale', F.pick(F.state(aged)) === 'stale');
    F.setWindows({ depth_s: 30 });
    check('windows: a user override in seconds wins over the table', F.window('depth') === 30000);
    check('windows: unset kinds keep the table', F.window('candles') === 60000);
    check('windows: an existing row re-judges immediately', F.pick(F.state(aged)) === 'fresh');
    check('windows: a stamped window still beats the user (the payload is the truth)',
        F.stamp('payload', { ageMs: 0, windowMs: 250 }).windowMs === 250);
    F.setWindows({ depth_s: 0 });
    check('windows: zero restores the built-in window', F.window('depth') === 5000);
    F.setWindows({ depth_s: -5, quote_s: 'junk' });
    check('windows: junk is ignored, never a crash',
        F.window('depth') === 5000 && F.window('quote') === 60000);
}

/* ── T4/A16: the strip summary ──────────────────────────────────── */

{
    const F = boot();
    F.stamp('live-a', { lastMs: Date.now() - 1000, kind: 'depth' });
    F.stamp('live-b', { lastMs: Date.now() - 9000, kind: 'depth' });   // stale under the 5 s window
    F.stamp('demo-c', { source: 'demo' });
    F.stamp('unknown-d', {});
    const s = F.summary();
    check('summary: only live, aged panels are counted', s.live === 2);
    check('summary: the stale list names the panel', s.stale.length === 1 && s.stale[0] === 'live-b');
    check('summary: the oldest age is the strip number', s.oldest_ms >= 9000 && s.oldest_ms < 20000);
}

console.log('freshness selftest: ' + ok + ' ok, ' + failures.length + ' failed');
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
