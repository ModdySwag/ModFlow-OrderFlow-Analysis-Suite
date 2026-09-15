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

/* ── diagonal processing matrix ──────────────────────────────────────────── */
const ladder = [
    { price: 100, bid: 100, ask: 2 },     // 100 / ask(101)=20 = 5x   -> buying
    { price: 101, bid: 1, ask: 20 },      // 20  / bid(102)=2  = 10x  -> selling
    { price: 102, bid: 2, ask: 3 },       // nothing above: neither side can be judged
];
const diag = math.diagonalImbalance(ladder, 4.0);
check('diagonal: buying imbalance flags bid[Y] vs ask[Y+1]', diag.rows[0].buy && diag.rows[0].side === 'buy');
check('diagonal: selling imbalance is the reciprocal comparison', diag.rows[1].sell && diag.rows[1].side === 'sell');
check('diagonal: quiet level is unflagged', diag.rows[2].side === '');
check('diagonal: counts add up', diag.buyCount === 1 && diag.sellCount === 1, JSON.stringify([diag.buyCount, diag.sellCount]));
check('diagonal: R is honoured (higher R clears the flag)',
    math.diagonalImbalance(ladder, 25.0).rows[0].side === '');
check('diagonal: a zero next level does not fake an imbalance',
    math.diagonalImbalance([{ price: 1, bid: 5, ask: 0 }, { price: 2, bid: 0, ask: 0 }], 4).rows[0].side === '');

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
const heatPayload = { step: 1, buckets: [1700000000, 1700000060], prices: [[10, 11], [10, 11]], values: [[5, 9], [0, 14]] };
const adapted = OFX.math.adaptHeat(heatPayload, [1700000000, 1700000060], 60);
check('adaptHeat: columns land on the bars containing their timestamp',
    adapted && adapted.rows.length === 3 && adapted.rows.filter((r) => r.col === 1).length === 1
    && adapted.rows.find((r) => r.col === 1).size === 14,
    JSON.stringify(adapted && adapted.rows));
const sumPayload = { step: 1, buckets: [1700000000, 1700000030], prices: [[10], [10]], values: [[5], [7]] };
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
check('group: a group keeps the price of its last tick and its tick count',
    groupedRows[0].price === 2 && groupedRows[0].ticks === 2 && groupedRows[1].ticks === 1);
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

console.log(`ofx selftest: ${ok} ok, ${failures.length} failed`);
for (const f of failures) console.log('  FAIL', f);
process.exit(failures.length ? 1 : 0);
