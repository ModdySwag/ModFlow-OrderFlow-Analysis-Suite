/* ofx.selftest.js — pins the engine's math, runnable in Node (no DOM, no browser).

   `node desktop/ui/ofx.selftest.js` prints "ofx selftest: N ok, M failed" and exits non-zero
   on any failure, so `orderflow_system/test_ofx.py` can gate the whole suite on it. */
'use strict';

const OFX = require('./ofx.js');
const { math, state } = OFX;

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(`${name}${detail ? ` — ${detail}` : ''}`);
}
const near = (a, b, tol = 1e-6) => Math.abs(a - b) <= tol;

/* ── continuous variable text weight ─────────────────────────────────────── */
check('weight: no volume -> floor 300', math.fontWeight(0, 100) === 300);
check('weight: no average -> floor 300', math.fontWeight(50, 0) === 300);
check('weight: average volume -> mid range',
    math.fontWeight(100, 100) >= 500 && math.fontWeight(100, 100) <= 700, `got ${math.fontWeight(100, 100)}`);
check('weight: saturates at 900', math.fontWeight(10_000, 100) === 900);
check('weight: monotone in volume',
    math.fontWeight(50, 100) <= math.fontWeight(200, 100) && math.fontWeight(200, 100) <= math.fontWeight(400, 100));
check('weight: lands on century steps', math.fontWeight(137, 100) % 100 === 0);

/* ── diagonal processing matrix (the footprint.py convention) ──────────────
   One rule, two runtimes: analytics/footprint.py's diagonal branch is the reference. */
const ladder = [
    { price: 100, bid: 100, ask: 2 },     // sell: bid 100 / ask(101) 20 = 5x
    { price: 101, bid: 1, ask: 20 },      // quiet: ask 20 / bid(100) 100 = 0.2x
    { price: 102, bid: 2, ask: 40 },      // buy:  ask 40 / bid(101) 1   = 40x
];
const diag = math.diagonalImbalance(ladder, 4.0);
check('diagonal: buying imbalance flags ask[Y] vs bid[Y-1]', diag.rows[2].buy && diag.rows[2].side === 'buy');
check('diagonal: selling imbalance flags bid[Y] vs ask[Y+1]', diag.rows[0].sell && diag.rows[0].side === 'sell');
check('diagonal: quiet level is unflagged', diag.rows[1].side === '');
check('diagonal: counts add up', diag.buyCount === 1 && diag.sellCount === 1, JSON.stringify([diag.buyCount, diag.sellCount]));
check('diagonal: R is honoured (higher R clears the 5x row and keeps the 40x row)',
    math.diagonalImbalance(ladder, 25.0).rows[0].side === '' && math.diagonalImbalance(ladder, 25.0).rows[2].side === 'buy');
check('diagonal: the ladder edge falls back to the same-price comparison (footprint.py parity)',
    math.diagonalImbalance([{ price: 1, bid: 5, ask: 0 }, { price: 2, bid: 0, ask: 0 }], 4).rows[0].side === 'sell');
/* Pinned cross-runtime case: analytics/footprint.py answers [(100, 'sell')] for this ladder. */
const diagParity = math.diagonalImbalance(
    [{ price: 100, bid: 40, ask: 0 }, { price: 100.5, bid: 0, ask: 4 }], 4.0);
check('diagonal: matches footprint.py on the pinned ladder',
    diagParity.rows[0].side === 'sell' && diagParity.rows[1].side === '' && diagParity.buyCount === 0,
    JSON.stringify(diagParity.rows.map((r) => r.side)));

/* ── stacked imbalance zones ─────────────────────────────────────────────── */
const stacked = math.stackedZones([
    { price: 10, side: 'buy', ratio: 9 }, { price: 11, side: 'buy', ratio: 8 }, { price: 12, side: 'buy', ratio: 7 },
    { price: 13, side: '', ratio: 0 },
    { price: 14, side: 'sell', ratio: 5 }, { price: 15, side: 'sell', ratio: 5 },
], 3);
check('stacked: 3 adjacent same-side levels form a zone', stacked.length === 1 && stacked[0].count === 3);
check('stacked: the zone carries the price band',
    stacked[0].low === 10 && stacked[0].high === 12, JSON.stringify(stacked[0]));
check('stacked: 2 adjacent levels are not a stack', math.stackedZones([
    { price: 1, side: 'buy' }, { price: 2, side: 'buy' }], 3).length === 0);
check('stacked: a mixed run splits into two zones', math.stackedZones([
    { price: 1, side: 'buy' }, { price: 2, side: 'buy' }, { price: 3, side: 'buy' },
    { price: 4, side: 'sell' }, { price: 5, side: 'sell' }, { price: 6, side: 'sell' }], 3).length === 2);
check('stacked: minimum level count is respected', math.stackedZones([
    { price: 1, side: 'buy' }, { price: 2, side: 'buy' }, { price: 3, side: 'buy' }], 4).length === 0);

/* ── POC ─────────────────────────────────────────────────────────────────── */
const poc = math.poc([{ price: 1, bid: 5, ask: 5 }, { price: 2, bid: 12, ask: 3 }, { price: 3, bid: 0, ask: 0 }]);
check('poc: max(bid+ask) inside the interval', poc.price === 2 && poc.total === 15, JSON.stringify(poc));
check('poc: empty levels -> null', math.poc([]) === null);
check('glow: bounded and cell-scaled',
    math.glowRadius(40, 12) > 0 && math.glowRadius(4, 3) >= 3 && math.glowRadius(200, 200) <= 14);

/* ── liquidity decay ─────────────────────────────────────────────────────── */
check('decay: t=0 returns alpha0', near(math.decayAlpha(1, 0, 500), 1));
check('decay: one lambda is 1/e', near(math.decayAlpha(1, 500, 500), Math.exp(-1), 1e-9));
check('decay: monotone decreasing', math.decayAlpha(1, 900, 500) < math.decayAlpha(1, 500, 500));
check('decay: never negative', math.decayAlpha(1, 60000, 500) >= 0);
check('decay: scales with alpha0', near(math.decayAlpha(0.5, 500, 500), 0.5 * Math.exp(-1), 1e-9));

/* ── thermal gradient ────────────────────────────────────────────────────── */
const cold = math.heatColor01(0);
const hot = math.heatColor01(1);
check('heat: floor is slate blue', cold[2] > cold[0], JSON.stringify(cold));
check('heat: ceiling is white-hot gold', hot[0] === 255 && hot[1] > 200 && hot[2] > 150, JSON.stringify(hot));
check('heat: monotone warmth', math.heatColor01(0.6)[0] > math.heatColor01(0.2)[0]);
check('heat: clamped outside 0..1',
    JSON.stringify(math.heatColor01(-5)) === JSON.stringify(cold) && JSON.stringify(math.heatColor01(9)) === JSON.stringify(hot));
check('heat: log scale keeps small sizes visible', math.heatColor(10, 1000)[0] >= 55);

/* ── execution sweeps ────────────────────────────────────────────────────── */
check('sweep: r = c * cbrt(V)', near(math.sweepRadius(8, 1), 2, 1e-9));
check('sweep: doubling volume scales r by cbrt(2)', near(math.sweepRadius(16, 1) / math.sweepRadius(8, 1), Math.cbrt(2), 1e-9));
check('sweep: clamps tiny and huge sizes', math.sweepRadius(0) === 2 && math.sweepRadius(1e9) === 40);
check('sweep: c scales linearly', near(math.sweepRadius(27, 2), 6, 1e-9), `got ${math.sweepRadius(27, 2)}`);

/* ── LOD ─────────────────────────────────────────────────────────────────── */
check('lod: below 45px suppresses text entirely', math.lod(44, 45).text === false && math.lod(44, 45).mode === 'profile');
check('lod: at the threshold text returns', math.lod(46, 45).text === true && math.lod(46, 45).mode === 'footprint');
check('lod: labels fade in rather than pop', math.lod(50, 45).labelAlpha < 1 && math.lod(80, 45).labelAlpha === 1);
check('lod: never negative', math.lod(0, 45).labelAlpha === 0);
check('text: a cell too thin for glyphs suppresses the numbers', math.textFits(6) === false && math.textFits(8.9) === false);
check('text: a cell with room keeps them', math.textFits(9) === true && math.textFits(22) === true);
check('cell height: tick step x price scale', math.cellHeightPx(0.5, 2.05) > 1.02 && math.cellHeightPx(0.5, 2.05) < 1.03);
check('cell height: a session-wide BTC fit is unreadable as cells', math.textFits(math.cellHeightPx(0.5, 2.05)) === false);
check('cell height: zooming the price axis restores legibility', math.textFits(math.cellHeightPx(0.5, 26)) === true);
check('text: the threshold is configurable', math.textFits(11, 14) === false && math.textFits(14, 14) === true);
check('degrade: engages below the text threshold', math.degradeDecision(44, 45, 15, false) === true && math.degradeDecision(46, 45, 15, false) === false);
check('degrade: holds across the hysteresis band', math.degradeDecision(46, 45, 15, true) === true && math.degradeDecision(52, 45, 15, true) === true);
check('degrade: releases past the band', math.degradeDecision(53, 45, 15, true) === false);

/* ── viewport state machine ──────────────────────────────────────────────── */
check('viewport: right edge at newest data is live', math.viewportMode(0, 100, 100) === 'live');
check('viewport: scrolled left of newest is historical', math.viewportMode(0, 90, 100) === 'historical');
check('viewport: tiny overscroll past the newest bar stays live', math.viewportMode(5, 100, 100) === 'live');

/* ── coordinate matrix: asymmetric scales stay independent ───────────────── */
state.view.offX = 10; state.view.scaleX = 20;
state.view.offY = 100; state.view.scaleY = 2; state.view.height = 400;
check('matrix: worldX -> xToIndex round-trips', near(OFX.xToIndex(OFX.worldX(17)), 17, 1e-9));
check('matrix: priceToY -> yToPrice round-trips', near(OFX.yToPrice(OFX.priceToY(150)), 150, 1e-9));
const xBefore = OFX.worldX(17);
state.view.scaleY = 8;                       // zoom price only
check('matrix: Y zoom leaves X alone', OFX.worldX(17) === xBefore);
const yBefore = OFX.priceToY(150);
state.view.scaleX = 55;                      // zoom time only
check('matrix: X zoom leaves Y alone', OFX.priceToY(150) === yBefore);

/* ── depth-history adapter ───────────────────────────────────────────────── */
/* §56: the snapshot contract — values[price row][time col], prices the flat ladder */
const heatPayload = { step: 1, buckets: [1700000000, 1700000060], prices: [10, 11], values: [[5, 0], [9, 14]] };
const adapted = OFX.math.adaptHeat(heatPayload, [1700000000, 1700000060], 60);
check('adaptHeat: columns land on the bars containing their timestamp',
    adapted && adapted.rows.length === 3 && adapted.rows.filter((r) => r.col === 1).length === 1
    && adapted.rows.find((r) => r.col === 1).size === 14,
    JSON.stringify(adapted && adapted.rows));
const sumPayload = { step: 1, buckets: [1700000000, 1700000030], prices: [10], values: [[5, 7]] };
const summed = OFX.math.adaptHeat(sumPayload, [1700000000, 1700000060], 60);
check('adaptHeat: sub-bar columns sum into one bar cell (payload is finer than the bar axis)',
    summed && summed.rows.length === 1 && summed.rows[0].size === 12 && summed.rows[0].col === 0,
    JSON.stringify(summed && summed.rows));
check('adaptHeat: scale is the largest resting size seen', adapted && adapted.scale === 14);
check('adaptHeat: rows carry a price band, not just a price', adapted && adapted.rows[0].hi === 11 && adapted.rows[0].lo === 10);
check('adaptHeat: empty payload -> null (say so, do not guess)', OFX.math.adaptHeat({ values: [] }, [1], 60) === null);
check('adaptHeat: no column timestamps -> null (cannot place them honestly)',
    OFX.math.adaptHeat({ values: [[1, 2]] }, [1, 2], 60) === null);

/* ── sizes as the reader sees them, and the legend contract ──────────────── */
check('fmtSize: crypto prints keep their digits', math.fmtSize(0.0035) === '0.0035' && math.fmtSize(0.04) === '0.040');
check('fmtSize: contract sizes stay whole', math.fmtSize(148.4) === '148' && math.fmtSize(12.25) === '12' && math.fmtSize(1.5) === '1.5');
check('fmtSize: thousands compress', math.fmtSize(1480) === '1.5k' && math.fmtSize(24000) === '24k');
check('fmtSize: an empty level is empty, not zero', math.fmtSize(0) === '' && math.fmtSize(null) === '');
check('theme: the documented colours are real rgb triplets', Object.values(math.theme).every((c) => /^\d{1,3},\d{1,3},\d{1,3}$/.test(c)));
check('theme: rgba() builds from the table', math.rgba('poc', '.95') === 'rgba(255,214,102,.95)');
const legend = OFX.legend();
check('legend: every entry names itself, says what it means and carries a swatch',
    legend.entries.length >= 14 && legend.entries.every((e) => e.name && e.meaning && e.swatch && e.swatch.type));
check('legend: swatches resolve to colours the table owns',
    legend.entries.filter((e) => e.swatch.rgb).every((e) => Object.values(math.theme).includes(e.swatch.rgb)),
    JSON.stringify(legend.entries.filter((e) => e.swatch.rgb && !Object.values(math.theme).includes(e.swatch.rgb)).map((e) => e.name)));
check('legend: layout, data dictionary and interactions are all stated',
    legend.layout.length >= 5 && legend.data.length >= 8 && legend.interactions.length >= 6);
check('legend: carries the live parameters it describes',
    legend.params && typeof legend.params.R === 'number' && typeof legend.params.vaPct === 'number'
    && typeof legend.params.ramp === 'string' && legend.params.symbol === OFX.state.symbol);

/* ── aggregation used by the LOD fallback ────────────────────────────────── */
OFX.setData({
    bars: [{ time: 1, open: 1, high: 2, low: 1, close: 1.5, volume: 10, delta: 4 },
        { time: 2, open: 1.5, high: 3, low: 1, close: 2, volume: 20, delta: -6 }],
    levelsByTime: new Map([[1, [{ price: 1, bid: 5, ask: 6 }]], [2, [{ price: 2, bid: 1, ask: 2 }]]]),
    prints: [],
});
const prof = OFX.profileBars();
check('profile: bid/ask aggregate per interval', prof.length === 2 && prof[0].bid === 5 && prof[0].ask === 6 && prof[0].total === 11);
check('profile: carries the bar delta through', prof[1].delta === -6);
check('profile: session average level volume is computed',
    near(OFX.state.avgLevelVolume, (11 + 3) / 2, 1e-9), `got ${OFX.state.avgLevelVolume}`);
check('stats: report shape is stable',
    ['frames', 'emaMs', 'p95Ms', 'mode', 'lod', 'colW'].every((k) => k in OFX.stats()),
    JSON.stringify(Object.keys(OFX.stats())));

/* ── proportional shading, value area, HVN ───────────────────────────────── */
const shares = math.rowShares([
    { price: 10, bid: 4, ask: 6 },      // 10  -> 25% of the candle
    { price: 11, bid: 20, ask: 10 },    // 30  -> 75%, the node
    { price: 12, bid: 0, ask: 0 },      // 0   -> outside the value area
], 0.7);
check('shares: each row carries its own fraction of the candle',
    Math.abs(shares.rows[0].share - 0.25) < 1e-9 && Math.abs(shares.rows[1].share - 0.75) < 1e-9,
    JSON.stringify(shares.rows.map((r) => r.share)));
check('shares: the value area takes the heaviest rows first',
    shares.rows[1].inVA === true && shares.rows[0].inVA === false && shares.vaCount === 1);
check('shares: the HVN is the heaviest row', shares.hvn === 11);
check('shares: the VA band is the min/max price of its rows', shares.vaLow === 11 && shares.vaHigh === 11);
check('shares: an empty candle does not divide by zero', math.rowShares([], 0.7).candleTotal === 0);
check('shares: a wider value area pulls more rows in', math.rowShares([
    { price: 1, bid: 5, ask: 5 }, { price: 2, bid: 4, ask: 4 }, { price: 3, bid: 1, ask: 1 }], 0.95).vaCount >= 2);

/* ── dynamic tick grouping ───────────────────────────────────────────────── */
check('group: one row already fits, so k = 1', math.tickGroup(0.5, 26, 9) === 1);
check('group: a session-wide BTC fit groups ticks', math.tickGroup(0.5, 2.05, 9) === 9, `got ${math.tickGroup(0.5, 2.05, 9)}`);
check('group: k shrinks as the price axis zooms in', math.tickGroup(0.5, 2.05, 9) > math.tickGroup(0.5, 9, 9));
check('group: no tick step means no grouping', math.tickGroup(0, 2, 9) === 1);
const groupedRows = math.groupLevels([{ price: 1, bid: 2, ask: 3 }, { price: 2, bid: 4, ask: 5 }, { price: 3, bid: 1, ask: 1 }], 2);
check('group: grouped rows sum bid and ask', groupedRows.length === 2 && groupedRows[0].bid === 6 && groupedRows[0].ask === 8,
    JSON.stringify(groupedRows));
check('group: a group is centred on its band and keeps its tick count (C-04)',
    groupedRows[0].price === 1.5 && groupedRows[0].label === 2 && groupedRows[0].ticks === 2
    && groupedRows[1].ticks === 1);
check('group: k=1 is a pass-through', math.groupLevels([{ price: 1, bid: 2, ask: 3 }], 1)[0].bid === 2);

/* ── two-sided blocks ────────────────────────────────────────────────────── */
const split = math.sideSplit(70, 30);
check('split: fractions reflect the two sides', Math.abs(split.buyFrac - 0.7) < 1e-9 && split.twoSided === true);
check('split: a one-sided block is not drawn as a pie', math.sideSplit(100, 0).twoSided === false);
check('split: an empty block is inert', math.sideSplit(0, 0).twoSided === false && math.sideSplit(0, 0).buyFrac === 0);

/* ── CVD divergence ──────────────────────────────────────────────────────── */
const diverge = math.cvdDivergence([
    { close: 100, delta: 5 }, { close: 101, delta: 4 }, { close: 102, delta: 3 },
    { close: 103, delta: -8 }, { close: 104, delta: -9 }, { close: 105, delta: -8 }], 6);
check('divergence: price up with aggressive selling is a bearish read', diverge.state === 'bear', JSON.stringify(diverge));
check('divergence: strength is reported, not just a flag', diverge.strength > 0.15 && diverge.strength <= 1);
const agree = math.cvdDivergence([
    { close: 100, delta: 5 }, { close: 101, delta: 6 }, { close: 102, delta: 7 }, { close: 103, delta: 8 }], 4);
check('divergence: agreement reads as none', agree.state === 'none');
check('divergence: too short a window is none', math.cvdDivergence([{ close: 1, delta: 1 }], 12).state === 'none');

/* ── print → bar indexing (the sweep layer's lookup) ─────────────────────── */
const barsT = [{ time: 100 }, { time: 160 }, { time: 220 }, { time: 280 }];
check('barIndex: a print inside a bar returns that bar', math.barIndex(barsT, 170) === 1);
check('barIndex: a print on the bar open belongs to that bar', math.barIndex(barsT, 160) === 1);
check('barIndex: a print before the first bar is refused', math.barIndex(barsT, 99) === -1);
check('barIndex: a print after the last open lands on the last bar', math.barIndex(barsT, 999) === 3);
check('barIndex: no bars means no index', math.barIndex([], 5) === -1);
const bigBars = Array.from({ length: 1440 }, (_, i) => ({ time: 1000 + i * 60 }));
check('barIndex: agrees with a linear scan over 1440 bars',
    bigBars.every((b, i) => math.barIndex(bigBars, b.time + 30) === i));

/* ── heat matrix indexing + the colour table ─────────────────────────────── */
const heatRows = [{ col: 2, price: 1 }, { col: 2, price: 2 }, { col: 0, price: 1 }, { col: 5, price: 3 }];
const hIdx = math.heatColumns(heatRows);
check('heatColumns: column keys are ordered and unique',
    JSON.stringify(hIdx.cols) === '[0,2,5]', JSON.stringify(hIdx.cols));
check('heatColumns: each column keeps its own rows',
    hIdx.groups.get(2).length === 2 && hIdx.groups.get(0).length === 1);
check('heatColumns: an empty matrix is inert', math.heatColumns([]).cols.length === 0);
const pal = math.heatPalette(100, 'classic', 4, 4);
check('palette: one ready rgba string per bucket pair',
    pal.strings.length === 16 && pal.strings[0].startsWith('rgba('), pal.strings[0]);
check('palette: density and alpha both move the index', pal.index(1, 0.1) < pal.index(100, 1.0));
check('palette: the index stays inside the table',
    pal.index(1e9, 5) < pal.strings.length && pal.index(-5, -1) === 0);
check('palette: an identical key reproduces the table',
    math.heatPalette(100, 'classic', 4, 4).strings[5] === pal.strings[5]);
check('palette: thermal and classic differ',
    math.heatPalette(100, 'thermal', 4, 4).strings[15] !== pal.strings[15]);

/* ── viewport authority (navigation can never leave the data) ────────────── */
check('niceStep: lands on a 1/2/2.5/5 decade', math.niceStep(60, 6) === 10 || math.niceStep(60, 6) === 10.000000000000002,
    String(math.niceStep(60, 6)));
check('niceStep: a bigger span asks for a bigger step', math.niceStep(1000, 6) > math.niceStep(10, 6));
check('niceStep: a zero span still returns a usable step', math.niceStep(0, 6) === 1);
const bandBars = [{ time: 1, low: 100, high: 110 }, { time: 2, low: 105, high: 130 }, { time: 3, low: 90, high: 95 }];
check('dataBand: covers the requested bars', math.dataBand(bandBars, 0, 2).lo === 100 && math.dataBand(bandBars, 0, 2).hi === 130);
check('dataBand: a sub-range only sees its own bars', math.dataBand(bandBars, 2, 3).lo === 90 && math.dataBand(bandBars, 2, 3).hi === 95);
check('dataBand: no bars means no band', math.dataBand([], 0, 5) === null);
const lim = math.viewLimits({ bars: bandBars, view: { width: 1000, height: 400, scaleX: 50, scaleY: 1 }, step: 0.5 });
check('viewLimits: at least four bars stay visible at full zoom', 1000 / lim.maxScaleX >= 3.9, `maxScaleX ${lim.maxScaleX}`);
check('viewLimits: zoom-out is bounded by the bar budget', 1000 / lim.minScaleX <= 400.1);
check('viewLimits: the newest bar stays reachable', lim.maxOffX >= bandBars.length - 3, `maxOffX ${lim.maxOffX}`);
check('viewLimits: the data band stays in view at both clamp extremes', (() => {
    const visSpanLim = 400;                       // view.height / scaleY used above
    const inView = (w) => w[0] <= lim.hi && w[1] >= lim.lo;
    return inView([lim.minOffY, lim.minOffY + visSpanLim]) && inView([lim.maxOffY, lim.maxOffY + visSpanLim]);
})(), JSON.stringify([lim.minOffY, lim.maxOffY, lim.lo, lim.hi]));
check('viewLimits: the price zoom is bounded by the data range', lim.maxScaleY > lim.minScaleY && lim.maxScaleY <= 400 / (0.5 * 8) + 1e-6);
const limTiny = math.viewLimits({ bars: [{ time: 1, low: 100, high: 101 }], view: { width: 1000, height: 400, scaleX: 52, scaleY: 1 }, step: 0.5 });
check('viewLimits: the left margin is at most a quarter of the dataset, floor one bar',
    -limTiny.minOffX <= 1 + 1e-9, `minOffX ${limTiny.minOffX}`);
check('viewLimits: a one-bar dataset keeps its bar on screen at the left clamp',
    (-limTiny.minOffX) * 52 <= 1000, `first bar x ${(-limTiny.minOffX) * 52}`);
const limEmpty = math.viewLimits({ bars: [], view: { width: 100, height: 100 }, step: 0 });
check('viewLimits: an empty book is inert', limEmpty.maxOffX === limEmpty.minOffX && limEmpty.lo === null);

/* ── P1-5: the ghost's peak tracks the cell's density ─────────────────────────
   A pulled wall must leave a strong ghost and a thin level a faint one; a uniform peak says every
   level held the same liquidity. */
check('peakAlpha: the largest cell in the window peaks at the top', math.peakAlpha(100, 100) === 0.92,
    String(math.peakAlpha(100, 100)));
check('peakAlpha: a small cell leaves a fainter ghost than a wall',
    math.peakAlpha(1, 100) < math.peakAlpha(50, 100) && math.peakAlpha(50, 100) < math.peakAlpha(100, 100),
    JSON.stringify([math.peakAlpha(1, 100), math.peakAlpha(50, 100), math.peakAlpha(100, 100)]));
check('peakAlpha: never below the floor and never above the top',
    math.peakAlpha(0, 100) === 0.32 && math.peakAlpha(1e9, 100) === 0.92,
    JSON.stringify([math.peakAlpha(0, 100), math.peakAlpha(1e9, 100)]));
check('peakAlpha: a nonsense scale is treated as 1, not as NaN', Number.isFinite(math.peakAlpha(5, 0))
    && Number.isFinite(math.peakAlpha(5, null)), JSON.stringify([math.peakAlpha(5, 0), math.peakAlpha(5, null)]));
check('peakAlpha: monotone in size, so "bigger" is never "fainter"',
    [1, 5, 20, 60, 100].every((v, i, a) => i === 0 || math.peakAlpha(a[i - 1], 100) <= math.peakAlpha(v, 100)));

/* ── P1-3: the selection's arithmetic ─────────────────────────────────────────
   A selection is measurement, so the sums are pinned here rather than trusted to the strip. */
check('selectionRange: a range past the last bar clips to it', JSON.stringify(math.selectionRange(0, 11, 5)) === '[0,4]',
    JSON.stringify(math.selectionRange(0, 11, 5)));
check('selectionRange: a reversed drag comes back ordered', JSON.stringify(math.selectionRange(4, 1, 5)) === '[1,4]',
    JSON.stringify(math.selectionRange(4, 1, 5)));
check('selectionRange: a start past the end clips too', JSON.stringify(math.selectionRange(11, 2, 5)) === '[2,4]',
    JSON.stringify(math.selectionRange(11, 2, 5)));
check('selectionRange: negatives clamp to the first bar', JSON.stringify(math.selectionRange(-3, 0, 5)) === '[0,0]',
    JSON.stringify(math.selectionRange(-3, 0, 5)));
check('selectionRange: no bars is a degenerate range, not a crash', JSON.stringify(math.selectionRange(0, 9, 0)) === '[0,0]',
    JSON.stringify(math.selectionRange(0, 9, 0)));

const selBars = [{ time: 1000, volume: 10, delta: 4 }, { time: 1060, volume: 20, delta: -6 }, { time: 1120, volume: 5, delta: 1 }];
const selLevels = new Map([
    [1000, [{ price: 100, bid: 5, ask: 5 }, { price: 101, bid: 9, ask: 1 }]],
    [1120, [{ price: 100, bid: 2, ask: 3 }, { price: 101, bid: 1, ask: 1 }]],
]);
const selPrints = [
    { time: 1000, price: 100, size: 2, side: 'buy' },
    { time: 1030, price: 101, size: 3, side: 'sell' },
    { time: 1119, price: 500, size: 9, side: 'buy' },    // outside the price band
    { time: 9999, price: 100, size: 7, side: 'buy' },    // outside the time range
    { time: 1000 * 1000, price: 100, size: 4 },          // ms stamps must not leak into a seconds window
];
const sel = math.selectionStats({ bars: selBars, levels: selLevels, prints: selPrints, i0: 0, i1: 2, p0: 100, p1: 101 });
check('selection: volume sums the bars in range', sel.volume === 35, String(sel.volume));
check('selection: delta sums signed bar delta', sel.delta === -1, String(sel.delta));
check('selection: prints outside the price band or the window are not counted',
    sel.prints === 2 && sel.printSize === 5, JSON.stringify([sel.prints, sel.printSize]));
check('selection: VWAP weights by size', near(sel.vwap, 100.6), String(sel.vwap));
check('selection: the largest print is reported with its price',
    sel.largest && sel.largest.size === 3 && sel.largest.price === 101, JSON.stringify(sel.largest));
check('selection: resting depth change is last bar minus first, in the band',
    sel.resting0 === 20 && sel.resting1 === 7 && sel.restingChange === -13,
    JSON.stringify([sel.resting0, sel.resting1, sel.restingChange]));
check('selection: the CSV detail carries one row per bar and per counted print',
    sel.barRows.length === 3 && sel.printRows.length === 2, JSON.stringify([sel.barRows.length, sel.printRows.length]));
const selNoDepth = math.selectionStats({ bars: selBars, levels: new Map(), prints: [], i0: 0, i1: 2, p0: 100, p1: 101 });
check('selection: no depth history reads null, never a zero change', selNoDepth.restingChange === null);
check('selection: a range with no bars is null, not an empty strip',
    math.selectionStats({ bars: selBars, levels: selLevels, prints: [], i0: 5, i1: 7 }) === null);
const selOne = math.selectionStats({ bars: selBars, levels: selLevels, prints: [], i0: 1, i1: 1, p0: 100, p1: 101 });
check('selection: a single-bar range is legal (its own bar, no neighbours required)',
    selOne.bars === 1 && selOne.t0 === 1060 && selOne.t1 === 1060, JSON.stringify([selOne.bars, selOne.t0]));

/* ── Phase 3 / A3: the area's volume profile, pinned ─────────────────────── */
const area = math.areaVolumeProfile({ bars: selBars, levels: selLevels, i0: 0, i1: 2, p0: 100, p1: 101, pct: 0.7 });
check('area: one row per price, bid+ask summed across the window', area.rows.length === 2 && area.total === 27,
    JSON.stringify([area.rows.length, area.total]));
check('area: the POC is the heaviest row and carries its share',
    area.poc === 100 && area.pocVolume === 15 && near(area.pocShare, 15 / 27), JSON.stringify([area.poc, area.pocVolume]));
check('area: the value area is the heaviest rows up to the share', area.val === 100 && area.vah === 101,
    JSON.stringify([area.val, area.vah]));
check('area: the row step is the smallest positive gap', area.step === 1, String(area.step));
check('area: a one-bar window profiles only that bar',
    math.areaVolumeProfile({ bars: selBars, levels: selLevels, i0: 0, i1: 0, p0: 100, p1: 101 }).total === 20);
const areaBand = math.areaVolumeProfile({ bars: selBars, levels: selLevels, i0: 0, i1: 2, p0: 100, p1: 100 });
check('area: the price band restricts the rows', areaBand.total === 15 && areaBand.rows.length === 1,
    JSON.stringify([areaBand.total, areaBand.rows.length]));
check('area: a one-row area has no step', areaBand.step === 0, String(areaBand.step));
check('area: an empty ladder is null, never a zero profile',
    math.areaVolumeProfile({ bars: selBars, levels: new Map(), i0: 0, i1: 2, p0: 100, p1: 101 }) === null);
check('area: a band with no rows is null too',
    math.areaVolumeProfile({ bars: selBars, levels: selLevels, i0: 0, i1: 2, p0: 500, p1: 600 }) === null);
check('area: the VA share clamps to the same bounds rowShares uses',
    math.areaVolumeProfile({ bars: selBars, levels: selLevels, i0: 0, i1: 2, p0: 100, p1: 101, pct: 0.02 }).vaPct === 0.1);
check('area: tied rows keep a deterministic POC (the lower price wins)',
    math.areaVolumeProfile({ bars: [{ time: 1 }, { time: 2 }],
        levels: new Map([[1, [{ price: 100, bid: 5, ask: 5 }]], [2, [{ price: 101, bid: 5, ask: 5 }]]]),
        i0: 0, i1: 1, p0: 100, p1: 101 }).poc === 100);

/* ── P1-9: keyboard zoom — the wheel's own arithmetic, pinned ────────────── */
check('zoom: the time scale clamps at both limits',
    math.zoomScale(85, 1.12, 2.5, 90) === 90 && math.zoomScale(3, 0.8, 2.5, 90) === 2.5);
check('zoom: the price scale clamps at both limits',
    math.zoomScale(39, 1.09, 0.02, 40) === 40 && math.zoomScale(0.015, 0.89, 0.02, 40) === 0.02);
{
    const v = OFX.state.view;
    v.width = 800; v.height = 500; v.scaleX = 50; v.scaleY = 2; v.offX = 10; v.offY = 100;
    OFX.state.autoFit = false;
    const idx0 = OFX.xToIndex(400);
    const sx = OFX.zoomTime(1.12, 400);
    check('zoom: a time zoom keeps the anchored column under the anchor point',
        near(OFX.xToIndex(400), idx0) && near(sx, 56), JSON.stringify([idx0, sx]));
    const p0 = OFX.yToPrice(250);
    const sy = OFX.zoomPrice(1.09, 250);
    check('zoom: a price zoom keeps the anchored price under the anchor point',
        near(OFX.yToPrice(250), p0) && near(sy, 2.18) && OFX.state.autoFit === false,
        JSON.stringify([p0, sy]));
}
{
    const v = OFX.state.view;
    v.scaleX = 52; v.offX = 0; OFX.state.autoFit = false;
    const centre = OFX.xToIndex(v.width / 2);
    OFX.zoomTime(0.89);
    check('zoom: a bare key press anchors at the stage centre', near(OFX.xToIndex(v.width / 2), centre));
    const centreY = OFX.yToPrice(v.height / 2);
    OFX.zoomPrice(0.92);
    check('zoom: the price default anchor is the stage centre too', near(OFX.yToPrice(v.height / 2), centreY));
}

/* ── P2-1: the hover index — parity with the loops it replaced ───────────────
   The reference (oracle) here is the OLD algorithm written out verbatim: a full scan per bar.
   The index must answer exactly what those loops answered, for the same payload. */
{
    const T0 = 1700000000, SEC = 60, NB = 40, NP = 400;
    const hBars = [], hPrints = [], hHeat = [];
    for (let i = 0; i < NB; i += 1) {
        hBars.push({ time: T0 + i * SEC, open: 1, high: 2, low: 1, close: 1.5, volume: 5, delta: (i % 5) - 2 });
    }
    for (let k = 0; k < NP; k += 1) {
        const bi = k % NB;
        hPrints.push({ time: T0 + bi * SEC + (k % SEC), price: 1.05, size: 0.5 + (k % 7) * 0.25, side: k % 2 ? 'buy' : 'sell' });
    }
    for (let c = 0; c < NB; c += 1) {
        for (let p = 0; p < 6; p += 1) {
            hHeat.push({ col: c, lo: 1 + (p - 2) * 0.07, hi: 1 + (p - 1) * 0.07, size: 1 + (c % 5) + p });
        }
    }
    const hLevels = new Map(hBars.map((b) => [b.time, [{ price: 1.05, bid: 9, ask: 8 }]]));
    const hEvents = hHeat.map((_, k) => ({ col: k % NB, kind: 'sweep', direction: 'buy', price: 1.05, size: 1 }));
    OFX.setData({ bars: hBars, levelsByTime: hLevels, prints: hPrints,
        heat: { rows: hHeat, scale: 1, traded: [], best: [], events: hEvents } });

    const sec = OFX.barSeconds();
    const oracle = (i) => {
        let cvd = 0;
        for (let k = 0; k <= i; k += 1) cvd += Number(hBars[k].delta) || 0;
        const bar = hBars[i];
        let prints = 0, sweep = 0;
        for (const p of hPrints) {
            const raw = Number(p.time) || 0;
            const ts = raw > 1e11 ? raw / 1000 : raw;
            if (ts >= bar.time && ts < bar.time + sec) { prints += 1; sweep += Number(p.size) || 0; }
        }
        let depth = 0;
        for (const cell of hHeat) {
            if (cell.col !== i) continue;
            if (cell.lo <= 1.05 && 1.05 < cell.hi) depth += cell.size;
        }
        const events = hEvents.filter((e) => Number(e.col) === i).length;
        return { cvd: cvd, prints: prints, sweep: sweep, depth: depth, events: events };
    };

    const idx = OFX.state.idx;
    check('P2-1: prints are bucketed exactly as the unindexed scan counts them',
        [3, 16, 25, 39].every((i) => {
            const o = oracle(i);
            return idx.printsByBar[i].prints === o.prints && near(idx.printsByBar[i].sweep, o.sweep, 1e-9);
        }),
        JSON.stringify([3, 16, 25, 39].map((i) => [idx.printsByBar[i].prints, oracle(i).prints])));
    check('P2-1: the CVD prefix equals the loop from bar 0',
        [0, 7, 21, 39].every((i) => idx.cvd[i + 1] === oracle(i).cvd));
    check('P2-1: hover depth comes from the renderer column groups',
        [5, 17, 30].every((i) => {
            let depth = 0;
            for (const cell of OFX.state.data.heatIndex.groups.get(i) || []) {
                if (cell.lo <= 1.05 && 1.05 < cell.hi) depth += cell.size;
            }
            return depth === oracle(i).depth;
        }));
    check('P2-1: flow events group by column like the filter did',
        [4, 19, 33].every((i) => (idx.flowByCol.get(i) || []).length === oracle(i).events));
    {
        const hi = 16;
        const mx = OFX.worldX(hi) + OFX.state.view.scaleX / 2;
        const my = OFX.priceToY(1.05);
        OFX.hover(mx, my);
        const h = OFX.state.hover, o = oracle(hi);
        check('P2-1: hover() end to end reads the index (same numbers as the old loops)',
            !!h && h.index === hi && h.prints === o.prints && near(h.sweep, o.sweep, 1e-9)
            && near(h.depth, o.depth, 1e-9) && near(h.cvd, o.cvd, 1e-9),
            JSON.stringify([h && [h.index, h.prints, h.sweep, h.depth, h.cvd], o]));

        /* D-05: the same bar and the same parameters must not rebuild the row/zone arrays, and the
           published hover object is a reused scratch — so a second identical hover hands back the
           SAME object, with the same numbers. (Before the fix every hover frame allocated a fresh
           object plus fresh derived rows.) */
        OFX.hover(mx, my);
        check('D-05: a repeated hover reuses the scratch object (no per-frame allocation)',
            OFX.state.hover === h, OFX.state.hover === h ? '' : 'a fresh object was allocated');
        check('D-05: the repeated hover still reports the same numbers',
            OFX.state.hover.index === hi && OFX.state.hover.prints === o.prints
            && near(OFX.state.hover.sweep, o.sweep, 1e-9) && near(OFX.state.hover.depth, o.depth, 1e-9),
            JSON.stringify([OFX.state.hover.index, OFX.state.hover.prints, OFX.state.hover.sweep]));
        /* and a hover on a different bar still recomputes rather than reusing stale rows */
        const hi2 = 19;
        OFX.hover(OFX.worldX(hi2) + OFX.state.view.scaleX / 2, OFX.priceToY(1.05));
        check('D-05: a different bar recomputes (the cache is keyed, not sticky)',
            OFX.state.hover.index === hi2, String(OFX.state.hover.index));
    }
    /* Millisecond stamps: the selectionStats rule means they COUNT now (they used to read zero). */
    const msPrints = hPrints.map((p) => ({ time: Math.round(p.time * 1000), price: p.price, size: p.size, side: p.side }));
    OFX.setData({ prints: msPrints });
    const msTotal = OFX.state.idx.printsByBar.reduce((a, r) => a + r.prints, 0);
    check('P2-1: millisecond stamps are normalised once and counted', msTotal === NP, `got ${msTotal}`);
    /* Bar boundaries moving must re-bucket: the oracle recomputed against the shifted bars agrees. */
    const sBars = hBars.map((b) => ({ time: b.time + 30, open: b.open, high: b.high, low: b.low,
        close: b.close, volume: b.volume, delta: b.delta }));
    OFX.setData({ bars: sBars });
    const sSec = OFX.barSeconds();
    const sOracle = (i) => {
        const bar = sBars[i];
        let n = 0;
        for (const p of msPrints) {
            const ts = Number(p.time) / 1000;
            if (ts >= bar.time && ts < bar.time + sSec) n += 1;
        }
        return n;
    };
    check('P2-1: a bars-only change re-buckets the prints',
        [3, 16, 25, 39].every((i) => OFX.state.idx.printsByBar[i].prints === sOracle(i)),
        JSON.stringify([3, 16, 25, 39].map((i) => [OFX.state.idx.printsByBar[i].prints, sOracle(i)])));
}

/* ── P2-2 (R6): the heat change gate, the ghost patch pass, hover coalescing ──
   The gate's contract: a pass runs when the epoch moved or ghosts are fading, and a no-op pass
   must COUNT as a no-op (heatSkips), so a benchmark cannot mistake it for work. */
{
    const heatRows = [
        { col: 0, lo: 1.0, hi: 1.01, size: 5 },
        { col: 1, lo: 1.0, hi: 1.01, size: 7 },
    ];
    const calls = { clear: 0, fullClear: 0, fill: 0 };
    const heatStub = {
        fillStyle: '',
        setTransform() {},
        clearRect(x, y) { if (x === 0 && y === 0) calls.fullClear += 1; calls.clear += 1; },
        fillRect() { calls.fill += 1 },
    };
    heatStub.getContext = () => heatStub;
    OFX.state.layers.heat = heatStub;

    OFX.setData({ heat: { rows: heatRows, scale: 1, version: 'v1' } });
    const s0 = OFX.stats();
    OFX.renderLayers(false);
    const s1 = OFX.stats();
    check('P2-2: a new heat version paints once (heatPasses +1, full clear ran)',
        s1.heatPasses === s0.heatPasses + 1 && calls.fullClear > 0, JSON.stringify([s0.heatPasses, s1.heatPasses]));

    /* nothing changed: the same dirty flag now costs a counted no-op, not a repaint */
    OFX.state.dirty.heat = true;
    const before = calls.fullClear;
    OFX.renderLayers(false);
    const s2 = OFX.stats();
    check('P2-2: an unchanged epoch is a counted skip, never a repaint',
        s2.heatPasses === s1.heatPasses && s2.heatSkips === s1.heatSkips + 1 && calls.fullClear === before,
        JSON.stringify([s2.heatPasses, s2.heatSkips, calls.fullClear - before]));

    /* the same version delivered twice is not a change */
    const e0 = OFX.state.heatEpoch;
    OFX.setData({ heat: { rows: heatRows, scale: 1, version: 'v1' } });
    check('P2-2: a repeated server version does not bump the epoch', OFX.state.heatEpoch === e0);
    OFX.setData({ heat: { rows: heatRows, scale: 1, version: 'v2' } });
    check('P2-2: a new version bumps the epoch', OFX.state.heatEpoch === e0 + 1);

    /* resize clears the canvas, so it must force a full repaint */
    OFX.state.heatPainted = OFX.state.heatEpoch;
    OFX.resize(900, 480);
    check('P2-2: resize forces a full repaint (canvas content is gone)', OFX.state.heatEpoch > OFX.state.heatPainted);
    OFX.state.heatPainted = OFX.state.heatEpoch;
    OFX.setParams({ lambda: 700 });
    check('P2-2: a lambda change forces the decay curve to repaint', OFX.state.heatEpoch > OFX.state.heatPainted);

    /* §72: the backing store carries the display scale. dpr = 1 is the identity the engine has
       always painted at; a real display scale must shape the backing stores and nothing else. */
    check('§72: math.layerSize is the one place that maths lives', (() => {
        const one = OFX.math.layerSize(900, 480, 1);
        const mid = OFX.math.layerSize(900, 480, 1.5);
        const two = OFX.math.layerSize(900, 480, 2);
        const zero = OFX.math.layerSize(900, 480, 0);
        return one.w === 900 && one.h === 480 && mid.w === 1350 && mid.h === 720
            && two.w === 1800 && two.h === 960 && zero.w === 900 && zero.h === 480;
    })());
    {
        const savedWindow = (typeof globalThis.window === 'undefined') ? undefined : globalThis.window;
        const savedBase = OFX.state.layers.base;
        const savedRibbon = OFX.state.layers.ribbon;
        try {
            const layer = { width: 10, height: 10, style: {}, getContext: () => ctxt, addEventListener: () => {} };
            OFX.state.layers.base = layer;
            OFX.state.layers.ribbon = null;
            globalThis.window = { devicePixelRatio: 1.5 };
            OFX.resize(900, 480);
            check('§72: a 150% display backs the layers at 1.5×', layer.width === 1350 && layer.height === 720,
                `got ${layer.width}x${layer.height}`);
            globalThis.window = { devicePixelRatio: 1 };
            OFX.resize(900, 480);
            check('§72: dpr = 1 is the identity — the exact sizes the engine always used',
                layer.width === 900 && layer.height === 480, `got ${layer.width}x${layer.height}`);
            const boxed = { width: 1, height: 1, clientWidth: 250, clientHeight: 125, style: {}, getContext: () => ctxt };
            OFX.state.layers.base = boxed;
            globalThis.window = { devicePixelRatio: 2 };
            OFX.resize(900, 480);
            check('§72: a canvas with its own CSS box is sized from that box × dpr',
                boxed.width === 500 && boxed.height === 250, `got ${boxed.width}x${boxed.height}`);
            const ribbon = { width: 1, height: 1, clientWidth: 700, clientHeight: 82, style: { width: '' }, getContext: () => ctxt };
            OFX.state.layers.ribbon = ribbon;
            globalThis.window = { devicePixelRatio: 2 };
            OFX.resize(720, 480);
            check('§72: the ribbon box is the stage width and its backing carries the scale',
                ribbon.style.width === '720px' && ribbon.width === 1400 && ribbon.height === 164,
                JSON.stringify([ribbon.style.width, ribbon.width, ribbon.height]));
        } finally {
            if (savedWindow === undefined) delete globalThis.window; else globalThis.window = savedWindow;
            OFX.state.layers.base = savedBase;
            OFX.state.layers.ribbon = savedRibbon;
        }
    }

    /* the ghost patch pass: repaint on quantised change, keep fading while it lasts, clear on death */
    OFX.setParams({ lambda: 500 });          // restore the constant the ghost maths below assumes
    OFX.state.heatPainted = OFX.state.heatEpoch;
    const ghostCell = { size: 0, alpha: 0.5, peak: 0.9, seen: Date.now() - 200, lastSize: 5 };
    OFX.state.heatGhosts = [{ cell: ghostCell, x: 10, yTop: 10, h: 5 }];
    const p0 = OFX.stats();
    const fills0 = calls.fill;
    const clears0 = calls.clear;
    OFX.state.dirty.heat = true;
    OFX.renderLayers(false);
    const p1 = OFX.stats();
    check('P2-2: a moved ghost is patch-repainted inside its own rect (no full clear)',
        p1.heatPatches === p0.heatPatches + 1 && calls.fill === fills0 + 1
        && calls.fullClear === before && calls.clear === clears0 + 1,
        JSON.stringify([p1.heatPatches, p0.heatPatches, calls.fill - fills0, calls.clear - clears0]));
    check('P2-2: the ghost keeps its new alpha', Math.abs(ghostCell.alpha - 0.603) < 0.01, String(ghostCell.alpha));
    const fills1 = calls.fill;
    OFX.state.dirty.heat = true;
    OFX.renderLayers(false);
    check('P2-2: an invisible move paints nothing (quantised)', calls.fill === fills1);
    ghostCell.seen = Date.now() - 10000;
    OFX.state.dirty.heat = true;
    OFX.renderLayers(false);
    check('P2-2: a dead ghost is cleared and leaves the list', OFX.state.heatGhosts.length === 0,
        JSON.stringify(OFX.state.heatGhosts.length));

    /* ── adaptHeat: the numeric-key rewrite must answer exactly what the string keys did ── */
    const T0 = 1700000000;
    const barTimes = [T0, T0 + 60];
    const wire = {
        step: 0.01, tick: 0.01,
        buckets: [T0 * 1000, (T0 + 65) * 1000, (T0 + 61) * 1000],
        prices: [1.0, 1.01],
        values: [[3, 5, 2], [4, 6, 0]],
        traded: [[1, 0, 3], [0, 2, 0]],
        best: [{ bid: 1, ask: 1.02, trades: 1 }],
        events: [
            { ts_ms: T0 * 1000 + 500, price: 1.0, kind: 'stack', size: 5, direction: 'buy' },
            { ts_ms: T0 * 1000 + 700, price: 1.0, kind: 'stack', size: 9, direction: 'buy' },
            { ts_ms: (T0 + 61) * 1000, price: 1.0, kind: 'pull', size: 4, direction: 'sell' },
        ],
    };
    const wireAdapted = OFX.math.adaptHeat(wire, barTimes, 60);
    const rowAt = (col, price) => (wireAdapted.rows.find((r) => r.col === col && Math.abs(r.price - price) < 1e-9) || {}).size;
    check('P2-2: adaptHeat merges per (bar, price) with numeric keys',
        rowAt(0, 1.0) === 3 && rowAt(0, 1.01) === 4 && rowAt(1, 1.0) === 7 && rowAt(1, 1.01) === 6,
        JSON.stringify(wireAdapted.rows));
    check('P2-2: adaptHeat merges traded volume the same way',
        wireAdapted.traded.some((r) => r.col === 1 && Math.abs(r.price - 1.0) < 1e-9 && r.size === 3)
        && wireAdapted.traded.filter((r) => r.col === 1).length === 2,
        JSON.stringify(wireAdapted.traded));
    check('P2-2: events keep the largest size per (bar, price, kind) and stay distinct by kind',
        wireAdapted.events.length === 2
        && wireAdapted.events.some((e) => e.kind === 'stack' && e.size === 9)
        && wireAdapted.events.some((e) => e.kind === 'pull' && e.size === 4),
        JSON.stringify(wireAdapted.events.map((e) => [e.kind, e.size])));
    check('P2-2: a bucket past the last window is not placed', OFX.math.adaptHeat({
        step: 0.01, buckets: [(T0 + 120) * 1000], prices: [1.0], values: [[5]] }, barTimes, 60) === null);
    const noisy = OFX.math.adaptHeat({
        step: 0.01, buckets: [T0 * 1000], prices: [1.0000000001, 1.0], values: [[2], [3]] }, barTimes, 60);
    check('P2-2: off-grid float noise merges with its grid price',
        noisy && noisy.rows.length === 1 && noisy.rows[0].size === 5, JSON.stringify(noisy && noisy.rows));

    /* ── hover coalescing: many moves, no hover until the frame runs it ── */
    const wx = {}, cx2 = {};
    global.window = { addEventListener: (type, fn) => { wx[type] = fn; } };
    const canvas2 = {
        addEventListener: (type, fn) => { cx2[type] = fn; },
        getBoundingClientRect: () => ({ left: 0, top: 0, right: 900, bottom: 480 }),
    };
    OFX.attach(canvas2);
    const hoverBefore = OFX.state.hover;
    wx.mousemove({ clientX: 123, clientY: 45 });
    const first = OFX.state.pendingHover;
    wx.mousemove({ clientX: 200, clientY: 60 });
    const second = OFX.state.pendingHover;
    check('P2-2: moves pend (newest wins) and do not run hover per event',
        !!first && first.x === 123 && first.y === 45 && !!second && second.x === 200 && second.y === 60
        && OFX.state.hover === hoverBefore,
        JSON.stringify([first, second]));
    check('P2-2: a move outside the canvas still pends nothing new',
        (() => { const keep = OFX.state.pendingHover; wx.mousemove({ clientX: 5000, clientY: 5000 });
            return OFX.state.pendingHover === keep; })());
}

/* ── P2-3: the frame yield (measured at 4K: 17.5 ms arrival frame -> split) ────────────
   The contract: a frame that has spent its share paints what it can and leaves the rest
   QUEUED (dirty), so the next frame finishes the job instead of the first one blowing the
   budget. A single-layer job can never yield — there is nothing to defer to. */
{
    /* a self-returning callable proxy: satisfies every 2D-context method call and property
       read without writing fifty no-ops. */
    const ctxt = new Proxy(function () {}, {
        get: (target, key) => (key === Symbol.toPrimitive ? () => 0 : ctxt),
        set: () => true,
        apply: () => ctxt,
    });
    const canvasFor = () => ({ width: 100, height: 100, getContext: () => ctxt, addEventListener: () => {}, getBoundingClientRect: () => ({ left: 0, top: 0, right: 100, bottom: 100 }) });
    OFX.state.layers.base = canvasFor();
    OFX.state.layers.live = canvasFor();
    OFX.state.layers.ribbon = canvasFor();

    /* The frame budget reads performance.now(); on a loaded runner a stub paint can cross
       6 ms of REAL time and push the deferral one frame further out — the check must measure
       the contract, not the machine. Drive the budget from a fake clock: the "slow" layer
       advances it past the share, deterministically, wherever this runs. */
    const realNow = performance.now;
    let clockMs = 1000;
    performance.now = () => clockMs;

    let spin = true;
    const heatStub = {
        fillStyle: '',
        setTransform() {},
        clearRect() { if (spin) { spin = false; clockMs += 7.5; /* the slow layer: over the 6 ms share */ } },
        fillRect() {},
        getContext() { return heatStub; },
    };
    OFX.state.layers.heat = heatStub;

    OFX.setData({ heat: { rows: [{ col: 0, lo: 1.0, hi: 1.01, size: 5 }], scale: 1, version: 'y1' } });
    const y0 = OFX.stats();
    OFX.state.dirty.heat = OFX.state.dirty.base = OFX.state.dirty.live = true;
    OFX.renderLayers(false);
    const y1 = OFX.stats();
    check('P2-3: a frame that spends its share defers the rest (yield counted, flags left set)',
        y1.yields === y0.yields + 1 && OFX.state.dirty.base === true && OFX.state.dirty.live === true
        && y1.heatPasses === y0.heatPasses + 1,
        JSON.stringify([y1.yields, OFX.state.dirty.base, OFX.state.dirty.live]));

    OFX.renderLayers(false);
    const y2 = OFX.stats();
    check('P2-3: the next frame finishes the deferred layers and clears their flags',
        OFX.state.dirty.base === false && OFX.state.dirty.live === false && y2.yields === y1.yields,
        JSON.stringify([OFX.state.dirty.base, OFX.state.dirty.live, y2.yields - y1.yields]));

    /* a fast frame paints everything in one go */
    OFX.state.heatEpoch += 1;
    OFX.state.dirty.heat = OFX.state.dirty.base = OFX.state.dirty.live = true;
    const y3before = OFX.stats();
    OFX.renderLayers(false);
    const y3 = OFX.stats();
    check('P2-3: a frame under its share paints the whole job in one pass',
        y3.yields === y3before.yields && OFX.state.dirty.base === false && OFX.state.dirty.heat === false,
        JSON.stringify([y3.yields - y3before.yields]));

    /* a single-layer job never yields, even when that one layer is slow */
    spin = true;
    OFX.state.heatEpoch += 1;
    OFX.state.dirty.heat = true;
    const y4before = OFX.stats();
    OFX.renderLayers(false);
    const y4 = OFX.stats();
    check('P2-3: a single-layer frame cannot defer to itself — no yield',
        y4.yields === y4before.yields && OFX.state.dirty.heat === false,
        JSON.stringify([y4.yields - y4before.yields, OFX.state.dirty.heat]));

    check('P2-3: stats() reports yields', 'yields' in OFX.stats());

    performance.now = realNow;   /* back to the real clock for everything after this block */
}

/* ── §56: the typed heat wire decodes, and adapts to EXACTLY what the JSON path produces ──
   The fixture is assembled byte-by-byte here, so this also pins the layout `atlas/wire.py`
   writes (magic, u32 header length, header JSON, f64 buckets, f32 sections, 12 B best). */
{
    const T0 = 1700000000000;
    const header = {
        symbol: 'T', version: 3, step: 0.5, tick: 0.5, cols: 3, rows: 2,
        prices_mode: 'per_column', traded: true, carry_forward: false, carried_cells: 0,
        scale_max: 9, upper_cutoff_pct: 1, wall_age_ms: 120000, walls: [], note: '',
        events: [{ ts_ms: T0 + 500, price: 100.0, kind: 'wall', size: 5, direction: 'bid' }],
    };
    const hj = new TextEncoder().encode(JSON.stringify(header));
    const parts = [];
    parts.push(new Uint8Array([79, 70, 72, 66]));                       // 'OFHB'
    const lb = new Uint8Array(4);
    new DataView(lb.buffer).setUint32(0, hj.length, true);
    parts.push(lb, hj);
    const f64 = (arr) => new Uint8Array(Float64Array.from(arr).buffer);
    const f32 = (arr) => new Uint8Array(Float32Array.from(arr).buffer);
    parts.push(f64([T0, T0 + 30000, T0 + 61000]));
    parts.push(f32([100.0, 100.5, 100.0, 100.5, 100.0, 100.5]));         // prices, per column (legacy path, same ladder)
    parts.push(f32([5.0, 3.0, 4.0, 2.0, 1.0, 0.0]));                     // values, row-major
    parts.push(f32([1.0, 0.5, 2.0, 0.0, 0.0, 0.0]));                     // traded, row-major
    const bb = new Uint8Array(36);
    const bdv = new DataView(bb.buffer);
    bdv.setFloat32(0, 100.0, true); bdv.setFloat32(4, 100.5, true); bdv.setInt32(8, 4, true);
    for (let c = 1; c < 3; c += 1) { bdv.setFloat32(c * 12, 0, true); bdv.setFloat32(c * 12 + 4, 0, true); bdv.setInt32(c * 12 + 8, 0, true); }
    parts.push(bb);
    const total = parts.reduce((n, p) => n + p.length, 0);
    const buf = new Uint8Array(total);
    let off2 = 0;
    for (const p of parts) { buf.set(p, off2); off2 += p.length; }

    const wire = OFX.math.decodeHeatBin(buf.buffer);
    check('§56: decodeHeatBin reads the header and typed sections',
        !!wire && wire.header.cols === 3 && wire.header.rows === 2
        && wire.buckets.length === 3 && Math.abs(wire.buckets[0] - T0) < 1e-6
        && wire.values.length === 6 && wire.traded.length === 6
        && wire.best.length === 3 && wire.best[0].trades === 4,
        JSON.stringify(wire && { cols: wire.header.cols, v: wire.values.length }));

    const bt = [1700000000, 1700000060];
    const bin = OFX.math.adaptHeatBin(wire, bt, 60);
    const json = OFX.math.adaptHeat({
        step: 0.5, tick: 0.5,
        buckets: [T0, T0 + 30000, T0 + 61000],
        prices: [100.0, 100.5],
        values: [[5.0, 3.0, 4.0], [2.0, 1.0, 0.0]],
        traded: [[1.0, 0.5, 2.0], [0.0, 0.0, 0.0]],
        best: [{ bid: 100.0, ask: 100.5, trades: 4 }, { bid: 0, ask: 0, trades: 0 }, { bid: 0, ask: 0, trades: 0 }],
        events: header.events,
    }, bt, 60);
    check('§56: adaptHeatBin deep-equals adaptHeat on the same data',
        JSON.stringify(bin) === JSON.stringify(Object.assign({}, json, { version: 3 })),
        JSON.stringify([bin && bin.rows.length, json && json.rows.length]));
    check('§56: the wire path carries the wall event through',
        !!bin && bin.events.some((e) => e.kind === 'wall' && e.size === 5 && e.col === 0),
        JSON.stringify(bin && bin.events));
    check('§56: a garbage buffer decodes to null, never a half-map',
        OFX.math.decodeHeatBin(new ArrayBuffer(4)) === null
        && OFX.math.adaptHeatBin(null, bt, 60) === null);
}

/* ── T5/A11: the auto-fit verdict ─────────────────────────────────── */

check('fit: no tolerance always refits', math.fitDecision({ lo: 100, hi: 200 }, { lo: 120, hi: 180 }, 0) === 'refit');
check('fit: a band with slack at both edges holds',
    math.fitDecision({ lo: 100, hi: 200 }, { lo: 130, hi: 175 }, 0.25) === 'hold');
check('fit: the band reaching the bottom edge refits',
    math.fitDecision({ lo: 100, hi: 200 }, { lo: 120, hi: 160 }, 0.25) === 'refit');
check('fit: the band reaching the top edge refits',
    math.fitDecision({ lo: 100, hi: 200 }, { lo: 140, hi: 180 }, 0.25) === 'refit');
check('fit: a view far emptier than the band refits',
    math.fitDecision({ lo: 100, hi: 400 }, { lo: 240, hi: 260 }, 0.25) === 'refit');
check('fit: junk tolerance behaves as always-refit',
    math.fitDecision({ lo: 100, hi: 200 }, { lo: 140, hi: 160 }, 'junk') === 'refit');

/* ── §3 level reads: unfinished magnets + node bands (fold-in plan) ──────── */

const rbars = [{ time: 1000 }, { time: 1060 }, { time: 1120 }, { time: 1180 }];
const seg = OFX.levelReadSegments(rbars, {
    unfinished: [{ price: 100.5, side: 'above', bar_ts_ms: 1_060_000, active: true, arms: 2 },
                 { price: 99.5, side: 'below', bar_ts_ms: 1_120_000, active: false },
                 { price: 100.2, side: 'above', bar_ts_ms: 999_000, active: true }],
    nodes: [{ price: 100.5, count: 2, start_ts_ms: 1_000_000, last_ts_ms: 1_060_000 },
            { price: 101.0, count: 1, start_ts_ms: 1_120_000, last_ts_ms: 1_120_000 }],
});
check('level reads: an open magnet maps to its bar and runs to the right edge',
    seg.unfinished.length === 1 && seg.unfinished[0].from === 1 && seg.unfinished[0].to === -1,
    JSON.stringify(seg.unfinished));
check('level reads: a resolved magnet is not drawn',
    !seg.unfinished.some((l) => l.price === 99.5));
check('level reads: a magnet whose bar rolled out of the payload is counted, not guessed',
    seg.dropped === 1, String(seg.dropped));
check('level reads: node bands need two bars',
    seg.nodes.length === 1 && seg.nodes[0].count === 2 && seg.nodes[0].from === 0 && seg.nodes[0].to === 1,
    JSON.stringify(seg.nodes));
check('level reads: empty reads are an empty answer, not a throw',
    OFX.levelReadSegments(rbars, null).unfinished.length === 0
    && OFX.levelReadSegments([], {}).nodes.length === 0);

/* §141: price decimals come from the instrument's own tick, never from the price's magnitude. */
check('dpFromTick: a half-tick instrument prints one decimal', math.dpFromTick(0.5) === 1);
check('dpFromTick: a quarter tick prints two', math.dpFromTick(0.25) === 2);
check('dpFromTick: a cent tick prints two', math.dpFromTick(0.01) === 2);
check('dpFromTick: a whole-number tick prints none', math.dpFromTick(1) === 0);
check('dpFromTick: a ten-point tick prints none', math.dpFromTick(10) === 0);
check('dpFromTick: a trailing zero is not a decimal place', math.dpFromTick(0.10) === 1);
check('dpFromTick: an unknown tick has no opinion (null, not a guess)', math.dpFromTick(null) === null);
check('dpFromTick: a zero or negative tick has no opinion', math.dpFromTick(0) === null && math.dpFromTick(-1) === null);

console.log(`ofx selftest: ${ok} ok, ${failures.length} failed`);
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
