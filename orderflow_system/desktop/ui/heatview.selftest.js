/* heatview.selftest.js — the heatmap viewport maths (§121). Run: node desktop/ui/heatview.selftest.js */
'use strict';

const win = {};
global.window = win;
require('./heatview.js');
const HV = win.OFAPHEATVIEW;

let ok = 0;
let failed = 0;
function check(cond, label) {
    if (cond) { ok += 1; return; }
    failed += 1;
    console.error('FAIL:', label);
}

const NOW = 1_700_000_000_000;
const view = (over) => Object.assign({ cols: 240, rows: 200, until: null, bucket: 1000,
                                       haveFrom: NOW - 3_600_000, haveTo: NOW - 1000 }, over || {});

/* step: the same ladder semantics as everywhere else */
check(HV.step(240, 1, HV.COLS) === '360', 'step up 240 -> 360');
check(HV.step(240, -1, HV.COLS) === '180', 'step down 240 -> 180');
check(HV.step(60, -1, HV.COLS) === null, 'tight end stops');
check(HV.step(900, 1, HV.COLS) === null, 'wide end stops');
check(HV.step(999, 1, HV.COLS) === '180', 'unknown current: fall back to index 1, then step');
check(HV.step(200, -1, []) === null, 'empty ladder stops');

/* live stays live: zooming a live map keeps the right edge on the feed */
{
    const out = HV.zoomTime(view(), -1, 0.5, NOW);
    check(out.moved && out.cols === 180 && out.until === null, 'live zoom in stays live');
}
{
    const out = HV.zoomTime(view(), 1, 0.5, NOW);
    check(out.moved && out.cols === 360 && out.until === null, 'live zoom out stays live');
}

/* panned: the time under the cursor is invariant — Bookmap's zoom rule */
{
    const V = view({ until: NOW - 600_000 });          // window [T-840s, T-600s], 240 cols @1s
    const out = HV.zoomTime(V, -1, 1.0, NOW);           // pinned to the right edge
    check(out.until === V.until, 'right-edge anchor keeps the right edge');
    const outL = HV.zoomTime(V, 1, 0.0, NOW);           // pinned to the left edge
    check(outL.until === V.until - 240_000 + 360_000, 'left-edge anchor keeps the left edge');
    const outC = HV.zoomTime(V, -1, 0.5, NOW);          // centre
    check(outC.cols === 180 && outC.until === V.until - 30_000, 'centre anchor: half the narrowed width');
}
{
    /* right-edge anchored zoom-out does not move the right edge — still panned, still honest */
    const V = view({ until: NOW - 30_000, cols: 60 });
    const out = HV.zoomTime(V, 1, 1.0, NOW);
    check(out.until === V.until, 'right-edge zoom-out keeps the anchor');
}

/* pan: grab semantics, clamps at both ends */
{
    const V = view({ until: NOW - 300_000 });
    const out = HV.panBy(V, 100, 800, NOW);             // drag right = look back
    check(out.moved && out.until === V.until - 30_000, 'drag right pans back proportionally');
}
{
    const out = HV.panBy(view(), -100, 800, NOW);       // drag left from live: forward is clamped
    check(out.until === null, 'dragging forward at live stays live');
}
{
    const V = view({ haveFrom: NOW - 900_000, until: NOW - 800_000, cols: 240 });   // 240s floor
    const out = HV.panBy(V, 10_000, 800, NOW);          // absurd drag back
    check(out.until === V.haveFrom + 240_000, 'pan clamps at the oldest window');
}
{
    const V = view({ until: NOW - 1_200 });
    const out = HV.panStep(V, 1, NOW);                  // one bucket newer lands within half a bucket of now
    check(out.until === null, 'stepping to the edge snaps live');
}
{
    const V = view({ until: NOW - 600_000 });
    check(HV.panStep(V, -1, NOW).until === V.until - 1000, 'panStep -1 is one bucket older');
    check(HV.panStep(V, 1, NOW).until === V.until + 1000, 'panStep +1 is one bucket newer');
}

/* rows */
check(HV.zoomRows(view(), 1).rows === 260, 'rows up 200 -> 260');
check(HV.zoomRows(view(), -1).rows === 140, 'rows down 200 -> 140');
check(HV.zoomRows(view({ rows: 400 }), 1).moved === false, 'rows wide end stops');

/* absorb + params + label */
{
    const V = view();
    HV.absorb(V, { bucket_ms: 500, have_from_ms: 1, have_to_ms: 2 });
    check(V.bucket === 500 && V.haveFrom === 1 && V.haveTo === 2, 'absorb learns the payload bounds');
    check(HV.params(V).until === 0, 'live params carry until 0');
    check(HV.params(view({ until: 1234.6 })).until === 1235, 'panned params round the anchor');
    check(HV.label(V, NOW) === '2 min · live', 'label: window + live');
    check(HV.label(view({ until: NOW - 45_000 }), NOW) === '4 min · 45 s back', 'label: seconds back');
    check(HV.label(view({ until: NOW - 300_000 }), NOW) === '4 min · 5 min back', 'label: minutes back');
    check(HV.snapLive(V).until === null, 'snapLive clears the anchor');
    check(HV.minutesOf(900, 1000) === '15 min' && HV.minutesOf(60, 1000) === '60 s', 'minutesOf');
}

/* the ladders are the contract with index.html's selects (pinned again in pytest) */
check(HV.COLS[0] === 60 && HV.COLS[HV.COLS.length - 1] === 900, 'COLS ladder ends');
check(HV.ROWS[0] === 60 && HV.ROWS[HV.ROWS.length - 1] === 400, 'ROWS ladder ends');

const total = ok + failed;
console.log('heatview selftest: ' + total + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
