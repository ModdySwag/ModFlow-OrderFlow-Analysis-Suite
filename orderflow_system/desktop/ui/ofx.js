/* ofx.js — the order-flow rendering engine: DOM heatmap + footprint matrix + HUD + sweeps.

   Design rules this file exists to enforce:
     1. ONE coordinate matrix. Every layer (heatmap, footprint, sweeps, HUD rail, ribbon)
        draws through `worldX()` / `priceToY()`. Zoom and pan mutate that matrix and repaint;
        they never rebuild DOM.
     2. Layered canvases + a frame budget. Static history is painted once per viewport change;
        the live layer and the HUD repaint per frame; the heatmap's exponential decay runs on
        its own throttled tick. Every frame is measured (`ofx.stats`).
     3. Honest degradation. Missing depth history, no prints, LOD below the text threshold —
        each one changes what is drawn and says so, instead of inventing values.

   The math is pure and exported (`ofx.math`) so `ofx.selftest.js` can pin it in Node. */
(function (root) {
    'use strict';

    const NS = 'http://www.w3.org/2000/svg';

    /* ── math: every rule the spec states, as a function ─────────────────── */

    const math = {
        /* Continuous variable text weight: 300..900, mapped to volume relative to the
           session's average per level. sqrt() compresses the top so mid-sized prints stay
           legible; rounded to 100s because font-weight renders reliably on century steps. */
        fontWeight(volume, avgVolume, saturateAt = 4) {
            const v = Number(volume) || 0;
            const avg = Number(avgVolume) > 0 ? Number(avgVolume) : 0;
            if (!v || !avg) return 300;
            const ratio = Math.min(v / (avg * saturateAt), 1);
            return Math.round((300 + 600 * Math.sqrt(ratio)) / 100) * 100;
        },

        /* Diagonal processing matrix. Buying imbalance: Bid[Y] over Ask[Y+1]. Selling is the
           reciprocal comparison, so one pass over the levels yields both directions.
           Returns per-level {buy, sell, ratio, against} plus counts. */
        diagonalImbalance(levels, R = 4.0) {
            const r = Number(R) > 0 ? Number(R) : 4.0;
            const rows = (levels || []).map((l, i) => {
                const bid = Number(l.bid) || 0;
                const ask = Number(l.ask) || 0;
                const next = (levels || [])[i + 1] || {};
                const askUp = Number(next.ask) || 0;
                const bidUp = Number(next.bid) || 0;
                const buyRatio = askUp > 0 ? bid / askUp : (bid > 0 ? Infinity : 0);
                const sellRatio = bidUp > 0 ? ask / bidUp : (ask > 0 ? Infinity : 0);
                /* Both sides must exist: a level with nothing beside it is missing data,
                   not a 40x imbalance, and flagging it would paint phantom zones. */
                const buy = bid > 0 && askUp > 0 && buyRatio >= r;
                const sell = ask > 0 && bidUp > 0 && sellRatio >= r;
                return {
                    price: Number(l.price) || 0, bid, ask, buy, sell,
                    ratio: buy ? buyRatio : (sell ? sellRatio : 0),
                    side: buy && sell ? 'both' : (buy ? 'buy' : (sell ? 'sell' : '')),
                };
            });
            return {
                rows,
                buyCount: rows.filter((x) => x.side === 'buy' || x.side === 'both').length,
                sellCount: rows.filter((x) => x.side === 'sell' || x.side === 'both').length,
            };
        },

        /* Stacked imbalances: at least `minLevels` adjacent levels carrying the same side.
           Adjacency is by index in the price-ordered level list (one tick apart on the
           venue), which is what makes a stack act as a projected zone. */
        stackedZones(rows, minLevels = 3) {
            const out = [];
            let run = null;
            for (const row of rows || []) {
                const side = row.side === 'both' ? run && run.side ? run.side : 'buy' : row.side;
                if (!side) {
                    if (run && run.count >= minLevels) out.push(run);
                    run = null;
                    continue;
                }
                if (run && run.side === side) {
                    run.count += 1;
                    run.low = Math.min(run.low, row.price);
                    run.high = Math.max(run.high, row.price);
                    run.peak = Math.max(run.peak, Number(row.ratio) || 0);
                } else {
                    if (run && run.count >= minLevels) out.push(run);
                    run = { side, count: 1, low: row.price, high: row.price, peak: Number(row.ratio) || 0 };
                }
            }
            if (run && run.count >= minLevels) out.push(run);
            return out;
        },

        /* POC: the cell holding max(bid+ask) inside one bar. Glow is scaled to the cell so a
           zoomed-out view does not produce a blur larger than the bar. */
        poc(levels) {
            let best = null;
            for (const l of levels || []) {
                const total = (Number(l.bid) || 0) + (Number(l.ask) || 0);
                if (!best || total > best.total) best = { price: Number(l.price) || 0, total, bid: Number(l.bid) || 0, ask: Number(l.ask) || 0 };
            }
            return best;
        },
        glowRadius(cellW, cellH) {
            return Math.max(3, Math.min(14, 0.35 * Math.min(cellW || 0, cellH || 0) + 3));
        },

        /* Exponential liquidity decay: Alpha_t = Alpha_0 * e^(-t/lambda). */
        decayAlpha(alpha0, dtMs, lambdaMs = 500) {
            const lam = Number(lambdaMs) > 0 ? Number(lambdaMs) : 500;
            const dt = Math.max(0, Number(dtMs) || 0);
            return Math.max(0, Math.min(1, (Number(alpha0) || 0) * Math.exp(-dt / lam)));
        },
        /* Two ramps. 'classic' is the original blue->cyan->green->yellow->red; 'thermal' follows
           the research brief's monotonic heat reading (deep slate -> orange -> white-hot gold), which
           never relies on a hue change to carry magnitude. Both are functions of one 0..1 scalar, so
           switching ramps cannot change any value - only its display. */
        heatColor01(t, ramp) {
            const x = Math.max(0, Math.min(1, Number(t) || 0));
            if (ramp === 'thermal') {
                const stops = [
                    [0.00, [26, 38, 58]],      // deep slate: almost nothing resting here
                    [0.35, [96, 70, 58]],
                    [0.60, [186, 110, 46]],    // orange: real size
                    [0.82, [232, 176, 84]],
                    [1.00, [255, 244, 214]],   // white-hot gold: institutional block
                ];
                for (let i = 1; i < stops.length; i += 1) {
                    if (x <= stops[i][0]) {
                        const a = stops[i - 1], b = stops[i];
                        const k = (x - a[0]) / (b[0] - a[0] || 1);
                        const c = a[1].map((v, j) => Math.round(v + (b[1][j] - v) * k));
                        return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
                    }
                }
                return 'rgb(255,244,214)';
            }
            return math.classicRamp(x);   // sibling method: reach it through the object, not by name
        },
        classicRamp(t) {
            /* Slate blue -> orange -> white-hot gold, clamped. */
            const x = Math.max(0, Math.min(1, Number(t) || 0));
            const stops = [[0, [55, 80, 122]], [0.45, [201, 106, 31]], [0.78, [255, 182, 77]], [1, [255, 242, 196]]];
            for (let i = 1; i < stops.length; i += 1) {
                const [t1, c1] = stops[i - 1];
                const [t2, c2] = stops[i];
                if (x <= t2) {
                    const k = t2 === t1 ? 0 : (x - t1) / (t2 - t1);
                    return c1.map((c, j) => Math.round(c + (c2[j] - c) * k));
                }
            }
            return stops[stops.length - 1][1].slice();
        },
        heatColor(size, scale) {
            const s = Number(size) || 0;
            const sc = Number(scale) > 0 ? Number(scale) : 1;
            return math.heatColor01(Math.log1p(s) / Math.log1p(Math.max(sc, 1)), state.params.ramp);
        },

        /* Execution sweep bubble: r = c * cbrt(volume). */
        sweepRadius(volume, c = 1.15, min = 2, max = 40) {
            const v = Math.max(0, Number(volume) || 0);
            return Math.max(min, Math.min(max, (Number(c) || 1.15) * Math.cbrt(v)));
        },

        /* Row shares: how much of one candle each price row carries, plus the value-area band
           (the rows that hold the top `vaPct` of that candle). The proportional shading in the
           renderer is built from this, and the VA frame is these two prices. */
        rowShares(levels, vaPct = 0.7) {
            const rows = (levels || []).map((l, i) => ({
                index: i, price: Number(l.price) || 0,
                bid: Number(l.bid) || 0, ask: Number(l.ask) || 0,
                total: (Number(l.bid) || 0) + (Number(l.ask) || 0),
            }));
            const candleTotal = rows.reduce((sum, r) => sum + r.total, 0);
            const ranked = rows.slice().sort((a, b) => b.total - a.total);
            const target = candleTotal * Math.max(0.1, Math.min(0.95, Number(vaPct) || 0.7));
            let acc = 0;
            const inVA = new Set();
            for (const r of ranked) {
                if (acc >= target && inVA.size) break;
                inVA.add(r.price);
                acc += r.total;
            }
            const vaPrices = rows.filter((r) => inVA.has(r.price)).map((r) => r.price);
            const hvn = ranked.length ? ranked[0].price : 0;
            return {
                rows: rows.map((r) => ({ ...r, share: candleTotal ? r.total / candleTotal : 0, inVA: inVA.has(r.price) })),
                candleTotal, vaLow: vaPrices.length ? Math.min(...vaPrices) : 0,
                vaHigh: vaPrices.length ? Math.max(...vaPrices) : 0, hvn, vaCount: inVA.size,
            };
        },

        /* Dynamic tick grouping: how many ticks belong in one drawn row so the row can hold
           text. Zooming the price axis in lowers k; zooming out raises it. */
        tickGroup(levelStep, scaleY, minRowPx = 9) {
            const rowPx = Math.abs((Number(levelStep) || 0) * (Number(scaleY) || 0));
            if (!rowPx) return 1;
            return Math.max(1, Math.ceil(Number(minRowPx) / rowPx));
        },

        /* Sum N adjacent ticks into one drawn row, preserving the totals and the band. */
        groupLevels(levels, k) {
            const n = Math.max(1, Math.floor(Number(k) || 1));
            const out = [];
            for (let i = 0; i < (levels || []).length; i += n) {
                const chunk = (levels || []).slice(i, i + n);
                let bid = 0, ask = 0;
                for (const l of chunk) { bid += Number(l.bid) || 0; ask += Number(l.ask) || 0; }
                const last = chunk[chunk.length - 1] || {};
                out.push({
                    price: Number(last.price) || 0, bid, ask, ticks: chunk.length,
                    low: Number(chunk[0] && chunk[0].price) || 0,
                });
            }
            return out;
        },

        /* A block that took both sides: the split the bubble draws as a pie. */
        sideSplit(buy, sell) {
            const b = Math.max(0, Number(buy) || 0), sl = Math.max(0, Number(sell) || 0);
            const total = b + sl;
            if (!total) return { buyFrac: 0, sellFrac: 0, twoSided: false };
            const buyFrac = b / total;
            return { buyFrac, sellFrac: 1 - buyFrac, twoSided: buyFrac > 0.15 && buyFrac < 0.85 };
        },

        /* CVD divergence: price and cumulative delta disagreeing over a window is the signal
           the blueprint wants flashing. Returns the direction and how hard it disagrees. */
        cvdDivergence(bars, window = 12) {
            const n = Math.min(Number(window) || 12, (bars || []).length);
            if (n < 4) return { state: 'none', strength: 0 };
            const slice = (bars || []).slice(-n);
            const priceMove = slice[slice.length - 1].close - slice[0].close;
            let cvdMove = 0;
            for (const b of slice) cvdMove += Number(b.delta) || 0;
            const span = Math.max(...slice.map((b) => b.close)) - Math.min(...slice.map((b) => b.close));
            const strength = Math.min(1, Math.abs(cvdMove) / Math.max(1, span * 4));
            if (priceMove > 0 && cvdMove < 0 && strength >= 0.15) return { state: 'bear', strength, priceMove, cvdMove };
            if (priceMove < 0 && cvdMove > 0 && strength >= 0.15) return { state: 'bull', strength, priceMove, cvdMove };
            return { state: 'none', strength: 0, priceMove, cvdMove };
        },

        /* Depth-history adapter. The atlas heatmap payload is a column-per-snapshot matrix; a
           column can only be placed on the bar axis if we know when it was taken, so a payload
           without per-column timestamps returns null instead of a guess. */
        adaptHeat(payload, barTimes, barSeconds) {
            const values = (payload && payload.values) || [];
            if (!Array.isArray(values) || !values.length) return null;
            const cols = Array.isArray(values[0]) ? values : [values];
            const buckets = (payload && (payload.buckets || payload.times)) || null;
            if (!Array.isArray(buckets) || !buckets.length) return null;
            const step = Number(payload && payload.step) || Number(payload && payload.tick) || 1;
            const rows = [];
            let scale = 1;
            /* One drawn column per BAR, not per payload column. The depth payload's columns are
               ~1-second buckets; the bar axis is minutes, so ~60 sub-columns per bar were each drawn
               one bar-width wide and the layer smeared across its neighbours (visible in the
               screenshot that prompted this). Resting depth sums per (bar, price). */
            const acc = new Map();
            cols.forEach((col, ci) => {
                const stamp = Number(buckets[ci]) || 0;
                if (!stamp || !Array.isArray(col)) return;
                const ms = stamp > 1e12 ? stamp / 1000 : stamp;
                let barIndex = -1;
                for (let i = barTimes.length - 1; i >= 0; i -= 1) {
                    if (barTimes[i] <= ms && ms < barTimes[i] + Math.max(1, barSeconds)) { barIndex = i; break; }
                }
                if (barIndex < 0) return;                       // a bucket outside the drawn bars is not ours to place
                const prices = Array.isArray(payload.prices) && Array.isArray(payload.prices[ci])
                    ? payload.prices[ci] : (payload.prices || []);
                col.forEach((size, pi) => {
                    const price = Number(prices[pi]);
                    const value = Number(size) || 0;
                    if (!Number.isFinite(price) || value <= 0) return;
                    const key = barIndex + '|' + price;
                    acc.set(key, (acc.get(key) || 0) + value);
                });
            });
            for (const [key, value] of acc) {
                const cut = key.indexOf('|');
                const barIndex = Number(key.slice(0, cut));
                const price = Number(key.slice(cut + 1));
                scale = Math.max(scale, value);
                rows.push({ col: barIndex, price, lo: price, hi: price + step, size: value });
            }
            const mapCol = (colIdx) => {
                const stamp = Number((buckets || [])[colIdx]) || 0;
                const ms = stamp > 1e12 ? stamp / 1000 : stamp;
                let barIndex = -1;
                for (let i = barTimes.length - 1; i >= 0; i -= 1) {
                    if (barTimes[i] <= ms && ms < barTimes[i] + Math.max(1, barSeconds)) { barIndex = i; break; }
                }
                if (barIndex < 0 && barTimes.length) barIndex = Math.max(0, barTimes.length - 1 - (cols.length - 1 - colIdx));
                return barIndex;
            };
            /* Executed volume rides the same grid as the resting depth: without it the engine could
               only show prints the live tape still holds, and every older column lost its trades. */
            const tradedAcc = new Map();
            const tradedMatrix = Array.isArray(payload.traded) ? payload.traded : [];
            tradedMatrix.forEach((col, ci) => {
                if (!Array.isArray(col)) return;
                const barIndex = mapCol(ci);
                if (barIndex < 0) return;
                const prices = Array.isArray(payload.prices) && Array.isArray(payload.prices[ci])
                    ? payload.prices[ci] : (payload.prices || []);
                col.forEach((size, pi) => {
                    const value = Number(size) || 0;
                    if (value <= 0) return;
                    const price = Number(prices[pi]);
                    if (!Number.isFinite(price)) return;
                    const key = barIndex + '|' + price;
                    tradedAcc.set(key, (tradedAcc.get(key) || 0) + value);
                });
            });
            /* Executed volume sums per bar too, and carries the side the prints took: the ramp at the
               end of the pass paints it as flow, not as liquidity. */
            const tradedRows = [];
            for (const [key, value] of tradedAcc) {
                const cut = key.indexOf('|');
                tradedRows.push({ col: Number(key.slice(0, cut)), price: Number(key.slice(cut + 1)), size: value, side: '' });
            }
            /* Best bid/ask per column is the spread the book actually carried. */
            /* Best bid/ask: one point per bar (the last book state the bar saw). */
            const bestByBar = new Map();
            (Array.isArray(payload.best) ? payload.best : []).forEach((b, ci) => {
                const barIndex = mapCol(ci);
                if (barIndex < 0 || !b) return;
                bestByBar.set(barIndex, { col: barIndex, bid: Number(b.bid) || 0, ask: Number(b.ask) || 0, trades: Number(b.trades) || 0 });
            });
            const bestCols = [...bestByBar.values()];
            /* Book events (stack / pull) land on the bar axis the same way. */
            /* Book events: one mark per (bar, price, kind) — a wall that stacks 40 times in a minute
               is one fact about that level, not forty marks in the same pixel. Largest size wins. */
            const eventAcc = new Map();
            (Array.isArray(payload.events) ? payload.events : []).forEach((ev) => {
                if (!ev) return;
                const ms = (Number(ev.ts_ms) || 0) > 1e12 ? Number(ev.ts_ms) / 1000 : Number(ev.ts_ms) || 0;
                let barIndex = -1;
                for (let i = barTimes.length - 1; i >= 0; i -= 1) {
                    if (barTimes[i] <= ms && ms < barTimes[i] + Math.max(1, barSeconds)) { barIndex = i; break; }
                }
                if (barIndex < 0) return;
                const price = Number(ev.price) || 0;
                const kind = ev.kind || '';
                const key = barIndex + '|' + price + '|' + kind;
                const prev = eventAcc.get(key);
                const size = Number(ev.size) || 0;
                if (!prev || size > prev.size) {
                    eventAcc.set(key, { col: barIndex, kind, direction: ev.direction || '', price, size, detail: ev.detail || '' });
                }
            });
            const flowEvents = [...eventAcc.values()];
            if (!rows.length && !tradedRows.length) return null;
            return { rows, scale, traded: tradedRows, best: bestCols, events: flowEvents };
        },

        /* LOD: text is suppressed entirely below the threshold; between threshold and
           threshold+fade the labels ramp in so the transition is not a pop. */
        /* Text also needs vertical room: a cell thinner than this cannot hold a legible
           number, so the numbers are suppressed even when the column is wide enough. */
        cellHeightPx(levelStep, scaleY) {
            return Math.abs((Number(levelStep) || 0) * (Number(scaleY) || 0));
        },

        textFits(cellHeight, minPx = 9) {
            return (Number(cellHeight) || 0) >= minPx;
        },

        lod(columnWidth, textPx = 45, fadePx = 15) {
            const w = Number(columnWidth) || 0;
            if (w < textPx) return { mode: 'profile', text: false, labelAlpha: 0 };
            return { mode: 'footprint', text: true, labelAlpha: Math.min(1, (w - textPx) / Math.max(1, fadePx)) };
        },

        /* Viewport state machine: the view is historical the moment its right edge sits left
           of the newest data. */
        viewportMode(offX, viewWidth, maxPresentX) {
            return (Number(offX) || 0) + (Number(viewWidth) || 0) < (Number(maxPresentX) || 0)
                ? 'historical' : 'live';
        },

        /* Print → bar index by binary search over the (time-ordered) bar array.
           The sweep layer used to run `bars.find(...)` per print: 4000 prints against 1440 bars
           measured 29.9 ms for one repaint of the live layer, which is a dropped frame every
           time the crosshair moves. O(log n) here, with the same "last bar whose time <= t"
           semantics the linear scan had. Returns -1 when the print predates the first bar. */
        barIndex(bars, time) {
            const n = (bars || []).length;
            if (!n) return -1;
            const t = Number(time) || 0;
            if (t < Number(bars[0].time)) return -1;
            let lo = 0;
            let hi = n - 1;
            while (lo < hi) {
                const mid = (lo + hi + 1) >> 1;
                if (Number(bars[mid].time) <= t) lo = mid; else hi = mid - 1;
            }
            return lo;
        },

        /* Depth-heat matrix → column index. The rows arrive column-major (one column per
           snapshot), and the renderer only has to touch the columns inside the viewport: this
           returns the ordered column keys plus their row slices, so a 30k-cell matrix costs
           (visible columns × levels) per pass instead of a bounds test on every cell. */
        heatColumns(rows) {
            const cols = [];
            const groups = new Map();
            for (const cell of rows || []) {
                const c = Number(cell.col) || 0;
                let g = groups.get(c);
                if (!g) { g = []; groups.set(c, g); cols.push(c); }
                g.push(cell);
            }
            cols.sort((a, b) => a - b);
            return { cols, groups };
        },

        /* Heat colour table: every distinct (density bucket, alpha bucket) as one ready rgba()
           string, rebuilt only when the scale or the ramp changes. The old path called
           heatColor + template-string per cell per pass — 8.3 ms per repaint at 30k cells, all
           of it allocation. Cells now index this table. */
        heatPalette(scale, ramp, buckets = 64, alphaSteps = 16) {
            const sc = Number(scale) > 0 ? Number(scale) : 1;
            const logMax = Math.log1p(Math.max(sc, 1));
            const out = [];
            for (let b = 0; b < buckets; b += 1) {
                const rgb = math.heatColor01(b / (buckets - 1), ramp);
                for (let a = 0; a < alphaSteps; a += 1) {
                    const alpha = (a + 1) / alphaSteps;
                    out.push('rgba(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + alpha.toFixed(3) + ')');
                }
            }
            return {
                buckets, alphaSteps, strings: out, logMax,
                index(size, alpha) {
                    const v = Number(size) || 0;
                    const t = logMax > 0 ? Math.min(1, Math.log1p(Math.max(v, 0)) / logMax) : 0;
                    let b = Math.round(t * (buckets - 1));
                    if (b < 0) b = 0; else if (b >= buckets) b = buckets - 1;
                    let a = Math.round((Number(alpha) || 0) * alphaSteps) - 1;
                    if (a < 0) a = 0; else if (a >= alphaSteps) a = alphaSteps - 1;
                    return b * alphaSteps + a;
                },
            };
        },

        /* ── viewport authority ────────────────────────────────────────────────
           The stage is a window over a finite dataset, so every transform parameter has a hard
           limit and the renderer refuses to sit outside it. Without these, `offX`/`offY` were only
           bounded during a drag: a data swap (200 history bars at one price replaced by one live bar
           at another) left the stage empty, the bar 9404 px off the left edge, and nothing on screen
           said why. */

        /* Axis step that lands on 1 / 2 / 2.5 / 5 x 10^n so price and time labels read cleanly. */

        /* ── one colour table, two readers ───────────────────────────────────
           The renderers below and `OFX.legend()` both read this, so the legend cannot describe a
           colour the picture does not use. Keys are the vocabulary an order-flow reader already
           has: resting bid vs ask, diagonal imbalance, stacked zone, POC/HVN, value area, executed
           flow, book events, spread, ribbon lanes. */
        theme: {
            bid: '53,208,127',          // resting bid (cell left half, profile bar, sell aggression in sweeps is ask)
            ask: '255,93,108',          // resting ask (cell right half)
            imBuy: '64,224,255',        // diagonal imbalance, buy side (ratio >= R)
            imSell: '255,64,196',       // diagonal imbalance, sell side
            poc: '255,214,102',         // point of control of the bar
            hvn: '255,182,77',          // high-volume node row within the bar
            vaGround: '120,150,190',    // value-area ground shading
            vaEdge: '150,175,215',      // VAH / VAL edges
            sweepTwo: '140,170,210',    // sweep block that took both sides
            stackUp: '86,214,255',      // book event: liquidity stacked on the ask
            stackDown: '255,93,200',    // book event: liquidity stacked on the bid
            pull: '210,153,34',         // book event: liquidity pulled
            spread: '140,200,255',      // best bid/ask line from the depth matrix
            vol: '140,170,210',         // ribbon volume lane
            cvdBody: '120,150,190',     // CVD body fill
            wick: '200,214,232',        // bar high-low range line
            grid: '120,150,190',        // gridlines
            axisLabel: '150,170,200',   // rail and ruler labels
            empty: '8,12,20',           // no-data band
        },
        rgba(key, alpha) {
            const rgb = this.theme[key] || key;
            return `rgba(${rgb},${alpha})`;
        },
        /* Sizes as an order-flow reader reads them: crypto prints live at 0.001-0.15 and must not
           be rounded to a string of zeros; contracts in the hundreds must not grow decimals. */
        fmtSize(value, width = 0) {
            const n = Number(value);
            if (!Number.isFinite(n) || n === 0) return '';
            const abs = Math.abs(n);
            let text;
            if (abs >= 1000) text = `${(n / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`;
            else if (abs >= 10) text = String(Math.round(n));
            else if (abs >= 1) text = (Math.round(n * 10) / 10).toFixed(1);
            else if (abs >= 0.1) text = (Math.round(n * 100) / 100).toFixed(2);
            else if (abs >= 0.01) text = n.toFixed(3);
            else text = n.toFixed(4).replace(/0+$/, '');
            return width ? text.padStart(width) : text;
        },
        niceStep(span, target = 6) {
            const raw = Math.abs(Number(span) || 0) / Math.max(1, Number(target) || 6);
            if (!raw || !Number.isFinite(raw)) return 1;
            const mag = Math.pow(10, Math.floor(Math.log10(raw)));
            const norm = raw / mag;
            const mult = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
            return mult * mag;
        },

        /* Price band of the bars in [from, to) — the data's own vertical extent. */
        dataBand(bars, from, to) {
            const n = (bars || []).length;
            if (!n) return null;
            const a = Math.max(0, Math.floor(Math.min(Number(from) || 0, Number(to) || 0)));
            const b = Math.min(n, Math.ceil(Math.max(Number(from) || 0, Number(to) || 0)));
            let lo = Infinity;
            let hi = -Infinity;
            for (let i = a; i < b; i += 1) {
                const bar = bars[i];
                if (!bar) continue;
                const l = Number(bar.low);
                const h = Number(bar.high);
                if (Number.isFinite(l)) lo = Math.min(lo, l);
                if (Number.isFinite(h)) hi = Math.max(hi, h);
            }
            if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
            return { lo, hi };
        },

        /* Every transform parameter's limit for this dataset and stage size.
           - the time axis always keeps `minVisibleBars` bars on screen and never scrolls the last
             bar past the left edge (so the newest print is always reachable),
           - the price axis keeps at least `minRows` rows of resolution and never zooms out past
             `maxSpanFactor` x the session range,
           - `offY` is bounded so at least 40% of the stage still shows the data band: you can park
             the view over the data or beside it, never on an empty stage. */
        viewLimits({ bars, view, step, minVisibleBars = 4, maxVisibleBars = 400, minRows = 8, maxSpanFactor = 3 }) {
            const n = (bars || []).length;
            const w = Math.max(1, Number(view && view.width) || 1);
            const h = Math.max(1, Number(view && view.height) || 1);
            const out = {
                minScaleX: 0.05, maxScaleX: 240, minScaleY: 0.0005, maxScaleY: 500,
                minOffX: -4, maxOffX: -4, minOffY: 0, maxOffY: 0, lo: null, hi: null, span: 0, visibleBars: 0,
            };
            if (!n) {
                out.maxOffX = out.minOffX;
                return out;
            }
            out.maxScaleX = Math.max(6, Math.min(240, w / Math.max(1, minVisibleBars)));
            out.minScaleX = Math.min(out.maxScaleX, Math.max(0.05, w / Math.max(1, maxVisibleBars)));
            out.visibleBars = Math.max(1, w / out.minScaleX);
            /* A margin before the first bar gives context, but it must not scale past the data
               itself: a one-bar dataset parked 20 bars left is an empty stage with no explanation. */
            const pad = Math.max(1, Math.min(out.visibleBars * 0.05, n * 0.25));
            out.minOffX = -pad;
            /* the right end: at the widest zoom the window is `visibleBars` wide, so offX may not
               exceed n - (bars that fit at the CURRENT scale) ... use the widest case so the bound
               holds for every zoom level */
            out.maxOffX = Math.max(out.minOffX, n - (w / out.maxScaleX) * 0.5);

            const band = math.dataBand(bars, 0, n);
            const stepPx = Number(step) > 0 ? Number(step) : 0;
            if (band) {
                out.lo = band.lo;
                out.hi = band.hi;
                const span = Math.max(band.hi - band.lo, stepPx * 4, 1e-9);
                out.span = span;
                out.maxScaleY = h / Math.max(stepPx * minRows, span * 0.02);
                out.minScaleY = h / (span * Math.max(1.1, maxSpanFactor));
                const scaleY = Math.max(out.minScaleY, Math.min(out.maxScaleY, Number(view && view.scaleY) || 1));
                const visSpan = h / scaleY;
                out.minOffY = band.lo - visSpan * 0.6;
                out.maxOffY = band.hi - visSpan * 0.4;
            }
            return out;
        },
    };

    /* ── state ───────────────────────────────────────────────────────────── */

    const state = {
        symbol: 'BTCUSDT',
        params: { R: 4.0, stack: 3, lambda: 500, textPx: 45, sweepC: 1.15, levelCap: 260,
            vaPct: 0.7, minBlock: 0, minRowPx: 9, ramp: 'classic' },
        // coordinate matrix — pixels per unit, plus origin
        /* scaleX=52 keeps the default view above the 45px text threshold: the engine opens on
           footprints, and LOD takes over when the user zooms out. */
        view: { offX: 0, scaleX: 52, offY: 0, scaleY: 0.6, width: 900, height: 480 },
        data: { bars: [], levels: new Map(), prints: [], heat: [], heatScale: 1, sessions: [],
            heatIndex: null, palette: null, traded: [], best: [], flowEvents: [], key: '' },
        layers: { heat: null, base: null, live: null, ribbon: null, hud: null },
        mode: 'live',
        lod: { mode: 'footprint', text: true, labelAlpha: 1 },
        dirty: { heat: true, base: true, live: true, ribbon: true, hud: true },
        stats: { frames: 0, lastMs: 0, emaMs: 0, p95Ms: 0, heatPasses: 0, decayCells: 0, framesMs: [], misses: 0,
            recovered: 0, flowBubbles: 0, flowEvents: 0,
            printsSeen: 0, printsMatched: 0, sweepBubbles: 0, heatCells: 0, textStarved: 0,
            cellPx: 0, aggregating: false, groupK: 1, divState: 'none', blocksFiltered: 0 },
        hover: null,
        autoFit: true,
        avgLevelVolume: 0,
        avgBarVolume: 0,
        lastPaint: 0,
    };

    /* ── coordinate matrix ───────────────────────────────────────────────── */


    /* Clock labels for the time ruler: epoch seconds -> local HH:MM:SS, cached per second (the
       ruler repaints on every pan/zoom and toLocaleTimeString is the expensive part). */
    const _clockCache = new Map();
    function clock(sec) {
        const s = Math.floor(Number(sec) || 0);
        const hit = _clockCache.get(s);
        if (hit !== undefined) return hit;
        const d = new Date(s * 1000);
        const text = String(d.getHours()).padStart(2, '0') + ':'
            + String(d.getMinutes()).padStart(2, '0') + ':'
            + String(d.getSeconds()).padStart(2, '0');
        if (_clockCache.size > 4000) _clockCache.clear();
        _clockCache.set(s, text);
        return text;
    }

    /* Nearest drawn level to a price: rows are price-sorted (indexLevels), so binary search. */
    function nearestLevel(rows, price) {
        const n = (rows || []).length;
        if (!n) return null;
        let lo = 0;
        let hi = n - 1;
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1;
            if (rows[mid].price <= price) lo = mid; else hi = mid - 1;
        }
        const cand = [rows[lo], rows[Math.min(n - 1, lo + 1)]];
        let best = cand[0];
        let dist = Math.abs(best.price - price);
        for (const row of cand) {
            const d = Math.abs(row.price - price);
            if (d < dist) { best = row; dist = d; }
        }
        return { level: best, dist };
    }

    function worldX(index) { return (index - state.view.offX) * state.view.scaleX; }
    function xToIndex(x) { return state.view.offX + x / state.view.scaleX; }
    function priceToY(price) { return state.view.height - (price - state.view.offY) * state.view.scaleY; }
    function yToPrice(y) { return state.view.offY + (state.view.height - y) / state.view.scaleY; }

    /* ── data plumbing ───────────────────────────────────────────────────── */

    function indexLevels(bar) {
        const rows = (bar.levels || []).map((l) => ({ price: Number(l.price) || 0, bid: Number(l.bid) || 0, ask: Number(l.ask) || 0 }));
        rows.sort((a, b) => a.price - b.price);
        return rows;
    }

    function computeSessionAverages() {
        let sum = 0, n = 0, bars = 0, barSum = 0;
        for (const bar of state.data.bars) {
            const rows = state.data.levels.get(bar.time) || [];
            if (!rows.length) continue;
            bars += 1;
            let barTotal = 0;
            for (const l of rows) { sum += l.bid + l.ask; n += 1; barTotal += l.bid + l.ask; }
            barSum += barTotal;
        }
        state.avgLevelVolume = n ? sum / n : 0;
        state.avgBarVolume = bars ? barSum / bars : 0;
    }

    function setData({ bars, levelsByTime, prints, heat }) {
        if (bars) state.data.bars = bars;
        if (levelsByTime) state.data.levels = levelsByTime;
        if (prints) state.data.prints = prints;
        if (heat) {
            state.data.heat = heat.rows || [];
            state.data.heatScale = heat.scale || 1;
            state.data.traded = heat.traded || [];
            state.data.best = heat.best || [];
            state.data.flowEvents = heat.events || [];
            /* Column index built once per payload, not per repaint: the renderer walks
               visible columns only, so a 30k-cell matrix no longer costs 30k iterations a pass. */
            state.data.heatIndex = math.heatColumns(state.data.heat);
        }
        computeSessionAverages();
        /* Data identity: symbol + bar span + count. A new identity means the previous transform may
           fit nothing at all, so the view is re-anchored on the newest bars unless the price window
           the user owns still overlaps the new band. */
        const key = `${state.symbol}|${state.data.bars.length}|${(state.data.bars[0] || {}).time || 0}`;
        const changed = key !== state.data.key;
        state.data.key = key;
        if (state.data.bars.length && (!state.fitted || changed)) {
            state.fitted = true;
            state.autoFit = true;
            snapToLive();
        }
        /* One load: anchor on the newest bars. offX starts at the left edge of the session,
           which would open the engine on history nobody asked for. */
        if (state.data.bars.length && !state.fitted) {
            state.fitted = true;
            state.view.offX = Math.max(0, state.data.bars.length - state.view.width / state.view.scaleX);
        }
        state.dirty.heat = state.dirty.base = state.dirty.live = state.dirty.ribbon = true;
        /* rAF is throttled to zero in a background tab and can be deferred until the window is
           mapped; one direct paint closes that gap without changing the frame schedule. */
        const guard = setTimeout(() => {
            if (!state.stats.frames) renderLayers(true);
        }, 250);
        if (typeof clearTimeout === 'function' && state.paintGuard) clearTimeout(state.paintGuard);
        state.paintGuard = guard;
    }

    /* ── the legend ─────────────────────────────────────────────────────────
       The panel renders exactly this: what the layout is, what every colour means, which payload
       feeds each layer, and every interaction. It reads the live parameters and the live stats, so
       it describes the picture on screen — not a picture from the documentation. Add a colour to
       `math.theme` and it belongs here too, or the reader is guessing. */
    function legend() {
        const p = state.params;
        const s = state.stats;
        const t = math.theme;
        const rampKey = p.ramp === 'thermal' ? 'thermal' : 'classic';
        const fmt = (v, d = 2) => (Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—');
        const entries = [
            {
                name: 'Resting depth heat',
                swatch: { type: 'ramp', ramp: rampKey },
                meaning: 'Liquidity resting in the book, drawn behind the matrix. One column per bar; '
                    + 'the column is the sum of every depth snapshot inside that bar. Saturation is '
                    + 'the deepest cell in view.',
                live: s.heatScale
                    ? `ramp ${rampKey} · scale ${fmt(s.heatScale, 2)} · ${s.heatCells} cells drawn`
                    : 'no depth history in view yet',
            },
            {
                name: 'Footprint cell — resting BID (left half)',
                swatch: { type: 'solid', rgb: t.bid },
                meaning: 'Volume resting on the bid at that price during that bar, inside the bar\'s '
                    + 'price range. Left half of the column row.',
                live: s.avgLevelVolume
                    ? `cells of ${math.fmtSize(s.avgLevelVolume)} and up read brightest`
                    : 'no levels drawn yet',
            },
            {
                name: 'Footprint cell — resting ASK (right half)',
                swatch: { type: 'solid', rgb: t.ask },
                meaning: 'Volume resting on the ask at that price during that bar. Right half of the '
                    + 'column row. The pair reads as the book\'s shape inside the bar.',
                live: `best bid/ask row per bar: ${state.data.best.length} bars`,
            },
            {
                name: 'Empty half (·)',
                swatch: { type: 'solid', rgb: t.vaEdge, alpha: '.35' },
                meaning: 'Nothing resting on that side at that price. A dot, not a zero — the digits '
                    + 'in a cell are real sizes, never placeholders.',
                live: `LOD: ${state.lod.mode}${s.aggregating ? ' (aggregated)' : ''}`,
            },
            {
                name: 'Diagonal imbalance — buy',
                swatch: { type: 'solid', rgb: t.imBuy },
                meaning: `Bid at that price ≥ ${fmt(p.R, 2)}× the ask one row up (the classic diagonal `
                    + 'read: aggressive buyers lifting offers into resting bids).',
                live: `R = ${fmt(p.R, 2)} · threshold moves with the R control`,
            },
            {
                name: 'Diagonal imbalance — sell',
                swatch: { type: 'solid', rgb: t.imSell },
                meaning: `Ask at that price ≥ ${fmt(p.R, 2)}× the bid one row down.`,
                live: `stack = ${p.stack} levels for a zone`,
            },
            {
                name: 'Stacked zone',
                swatch: { type: 'rail', rgb: t.stackUp, rgb2: t.stackDown },
                meaning: `${p.stack}+ consecutive imbalanced rows in one direction, banded with a `
                    + 'leading rail and labelled STACK. Strongest read of one-sided intent in the view.',
                live: `${s.zones === undefined ? 'see STACK labels' : s.zones + ' zones'}`,
            },
            {
                name: 'POC (point of control)',
                swatch: { type: 'outline', rgb: t.poc },
                meaning: 'The price with the largest total volume inside the bar — boxed, with a rail '
                    + 'on the right edge. The newest bar is drawn brighter.',
                live: `${state.data.bars.length} bars · 1 POC each`,
            },
            {
                name: 'HVN row',
                swatch: { type: 'solid', rgb: t.hvn },
                meaning: 'High-volume node: the heaviest row of the bar, warm-tinted under the numbers.',
                live: 'per bar',
            },
            {
                name: 'Value area',
                swatch: { type: 'line', rgb: t.vaEdge },
                meaning: `The ${fmt(p.vaPct * 100, 0)}% of the bar's volume around the POC (market ` +
                    'profile convention). Ground shaded, VAH/VAL edges drawn.',
                live: `VA ${fmt(p.vaPct * 100, 0)}% of each bar's volume`,
            },
            {
                name: 'Bar range',
                swatch: { type: 'line', rgb: t.wick },
                meaning: 'High→low of the bar down the column centre: the profile against the bar it '
                    + 'was traded in.',
                live: 'per bar',
            },
            {
                name: 'Column stats Δ / V',
                swatch: { type: 'text', sample: 'Δ+12.1  V 16.3', rgb: t.bid },
                meaning: 'The bar\'s own delta (aggressive buy minus sell, signed and coloured) and '
                    + 'total volume, hung above its high. Shown when the column is wide enough to '
                    + 'carry the text.',
                live: `text from ${p.textPx}px row height upward`,
            },
            {
                name: 'Sweep / block bubble',
                swatch: { type: 'split', rgb: t.bid, rgb2: t.ask },
                meaning: 'Executed size at one price inside one bar. Radius grows with size; a block '
                    + 'that took both sides is drawn split green/red by the side that traded.',
                live: `C = ${fmt(p.sweepC, 2)} · ${s.sweepBubbles} bubbles`,
            },
            {
                name: 'Book event — stack (▲)',
                swatch: { type: 'glyph', glyph: '▲', rgb: t.stackUp },
                meaning: 'Liquidity piled onto a level while the bar formed. Cyan on the ask, magenta '
                    + 'on the bid. One mark per level per bar, largest size.',
                live: `${state.data.flowEvents.length} marks in view · ${s.flowEvents} drawn`,
            },
            {
                name: 'Book event — pull (✕)',
                swatch: { type: 'glyph', glyph: '✕', rgb: t.pull },
                meaning: 'Liquidity pulled from a level — the wall that left before price arrived.',
                live: 'same source as stacks',
            },
            {
                name: 'Best bid/ask line',
                swatch: { type: 'line', rgb: t.spread },
                meaning: 'Mid of the best bid and ask per bar, from the depth matrix: the path price '
                    + 'actually had liquidity around.',
                live: `${state.data.best.length} bars`,
            },
            {
                name: 'Ribbon — volume / delta / CVD',
                swatch: { type: 'split', rgb: t.vol, rgb2: t.cvdBody },
                meaning: 'Under the stage: per-bar volume, per-bar delta (two-tone when the bar swings '
                    + 'hard against the previous one), and cumulative delta as a filled trace. The '
                    + 'trace breathes neon when price and aggressive flow disagree.',
                live: `CVD divergence: ${s.divState}`,
            },
            {
                name: 'Price rail / clock ruler / last price',
                swatch: { type: 'text', sample: '76940 · 18:41:00', rgb: t.axisLabel },
                meaning: 'Right rail: price at 1/2/2.5/5 steps, local clock under the stage, last '
                    + 'traded price tagged on the rail.',
                live: `${state.symbol} · ${barSeconds()}s bars`,
            },
            {
                name: 'No-data band',
                swatch: { type: 'solid', rgb: t.empty },
                meaning: 'Outside the drawn bars: dimmed, labelled "no bars after HH:MM:SS". The view '
                    + 'cannot be scrolled there — it can only be seen while the data ends.',
                live: s.recovered ? `${s.recovered} auto re-fits this session` : '0 auto re-fits',
            },
        ];
        const data = [
            { field: 'bars', from: '/api/footprint (poll 2.5 s)', meaning: 'OHLC + POC + levels per bar; closed bars only, so the newest bar can trail the tape' },
            { field: 'levels[]', from: 'same payload', meaning: 'resting size per price step: {price, bid, ask}' },
            { field: 'calc', from: 'same payload', meaning: 'per-bar volume, buy, sell, delta, rows, POC {price, volume, share_pct, delta}, max bid/ask level, extremes, imbalance list' },
            { field: 'candles + delta', from: '/api/candles, /api/delta (poll 5 s)', meaning: 'per-bar volume and delta; CVD is the running sum over drawn bars' },
            { field: 'prints', from: '/api/tape + WS ticks', meaning: 'every trade {time, price, size, side} — bubbles and sweep totals come from these' },
            { field: 'values[][]', from: '/api/atlas/heatmap (poll ~1 s)', meaning: 'resting depth matrix, ~1 s buckets × price rows; summed onto the bar axis' },
            { field: 'traded[][]', from: 'same payload', meaning: 'executed volume matrix, drawn as flow bubbles' },
            { field: 'best[], events[], walls[]', from: 'same payload', meaning: 'best bid/ask per bucket, stack/pull events with size and direction, largest resting walls' },
            { field: 'step, tick, buckets, scale_max', from: 'same payload', meaning: 'row height, instrument tick, column timestamps, colour saturation' },
            { field: 'derived', from: 'engine maths (selftested)', meaning: 'VA rows, imbalance ratio, stacked zones, tick grouping k, cell px, LOD mode, bar index by binary search' },
        ];
        const interactions = [
            { keys: 'wheel', action: 'price zoom (bounded by the data range)' },
            { keys: 'shift + wheel', action: 'time zoom (4–400 bars on screen)' },
            { keys: 'ctrl + wheel / pinch', action: 'price zoom' },
            { keys: 'drag', action: 'pan — clamped so the data cannot leave the stage' },
            { keys: 'double-click', action: 'fit the whole session' },
            { keys: 'fit button', action: 'same as double-click' },
            { keys: '● live (chip)', action: 'snap to the newest bar and follow' },
            { keys: 'P', action: 'hold updates while you work (feed keeps ingesting)' },
            { keys: 'hover', action: 'cursor tag on the canvas + full metric panel beside the stage' },
        ];
        const layout = [
            'depth heat — behind the matrix, one column per bar',
            'footprint matrix — one column per bar: bid left half, ask right half, POC boxed, VA shaded, STACK bands',
            'executed flow — sweep bubbles sized by print size, split when both sides traded',
            'book events — ▲ stacks and ✕ pulls at the price they happened',
            'best bid/ask line — the spread path across the bars',
            'price rail (right) / clock ruler (bottom) / last-price tag',
            'readout panel (right of the stage) — every metric at the cursor',
            'ribbon (under the stage) — volume, delta, CVD on the same X as the bars',
        ];
        return {
            symbol: state.symbol,
            entries, data, interactions, layout,
            params: {
                R: p.R, stack: p.stack, vaPct: p.vaPct, ramp: rampKey, minBlock: p.minBlock,
                levelCap: p.levelCap, sweepC: p.sweepC, minRowPx: p.minRowPx, lambda: p.lambda,
                symbol: state.symbol,
            },
            stats: {
                heatScale: Number(s.heatScale) || 0, heatCells: s.heatCells, sweepBubbles: s.sweepBubbles,
                flowEvents: s.flowEvents, divState: s.divState, recovered: s.recovered || 0,
                avgLevelVolume: s.avgLevelVolume, groupK: s.groupK, cellPx: s.cellPx, lod: state.lod.mode,
            },
        };
    }

    /* Aggregated view when LOD suppresses text: one bar per interval, split by direction. */
    function profileBars() {
        return state.data.bars.map((bar, i) => {
            const rows = state.data.levels.get(bar.time) || [];
            let bid = 0, ask = 0;
            for (const l of rows) { bid += l.bid; ask += l.ask; }
            return { i, time: bar.time, bid, ask, total: bid + ask, delta: (Number(bar.delta) || 0) };
        });
    }

    /* ── renderers ───────────────────────────────────────────────────────── */

    /* ── axes: what price, what time, and where the data actually is ─────── */

    function drawAxes(ctx) {
        const v = state.view;
        const bars = state.data.bars;
        const railW = 62;
        const rulerH = 14;
        const gridCol = math.rgba('grid', '.10');
        const labelCol = math.rgba('axisLabel', '.85');
        const warnCol = 'rgba(210,153,34,.9)';
        ctx.save();
        ctx.font = '500 10px ui-monospace, monospace';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        /* Price rail: labels at nice steps over the visible range, with a tick and a gridline. */
        const visSpan = v.height / Math.max(1e-9, v.scaleY);
        const step = math.niceStep(visSpan, 6);
        const decimals = step < 0.5 ? 2 : step < 5 ? 1 : 0;
        const bottom = v.offY;
        const top = v.offY + visSpan;
        for (let p = Math.ceil(bottom / step) * step; p <= top; p += step) {
            const y = priceToY(p);
            if (y < 8 || y > v.height - rulerH - 2) continue;
            ctx.fillStyle = gridCol;
            ctx.fillRect(0, y, v.width - railW, 1);
            ctx.fillRect(v.width - railW, y, 4, 1);
            ctx.fillStyle = labelCol;
            ctx.fillText(p.toFixed(decimals), v.width - railW + 7, y);
        }

        /* Time ruler: one label per `stride` bars, adaptive so labels never collide. */
        const idx0 = Math.max(0, Math.floor(v.offX));
        const idx1 = Math.min(bars.length, Math.ceil(xToIndex(v.width)) + 1);
        const stride = Math.max(1, Math.round(math.niceStep(idx1 - idx0, 8)));
        ctx.fillStyle = 'rgba(10,14,22,.85)';   // ruler background band
        ctx.fillRect(0, v.height - rulerH, v.width, rulerH);
        for (let i = Math.ceil(idx0 / stride) * stride; i < idx1; i += stride) {
            const x = worldX(i);
            if (x < 0 || x > v.width - railW) continue;
            ctx.fillStyle = gridCol;
            ctx.fillRect(x, 0, 1, v.height - rulerH);
            ctx.fillStyle = labelCol;
            ctx.fillText(clock((bars[i] || {}).time), x + 3, v.height - rulerH / 2);
        }

        /* Outside the drawn bars is not data: shade it and say so, instead of leaving the user to
           guess whether the engine has stalled. */
        if (bars.length) {
            const xFirst = worldX(0);
            const xLast = worldX(bars.length);
            ctx.fillStyle = math.rgba('empty', '.62');
            if (xFirst > 0) {
                ctx.fillRect(0, 0, Math.min(xFirst, v.width), v.height - rulerH);
                if (xFirst > 90) {
                    ctx.fillStyle = warnCol;
                    ctx.fillText('no bars before ' + clock(bars[0].time), 10, 18);
                }
            }
            if (xLast < v.width - railW) {
                const w = (v.width - railW) - xLast;
                ctx.fillRect(xLast, 0, w, v.height - rulerH);
                if (w > 90) {
                    ctx.fillStyle = warnCol;
                    ctx.fillText('no bars after ' + clock(bars[bars.length - 1].time), xLast + 10, 18);
                }
            }
        } else {
            ctx.fillStyle = warnCol;
            ctx.fillText('no bars for ' + state.symbol + ' yet — the engine is warming up', 12, 20);
        }

        /* The price band the data occupies — the contract the clamps enforce. */
        const lim = viewBounds();
        if (lim.lo != null) {
            const yTop = priceToY(lim.hi);
            const yBot = priceToY(lim.lo);
            ctx.strokeStyle = 'rgba(120,150,190,.28)';
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            if (yTop > 0 && yTop < v.height) { ctx.moveTo(0, yTop); ctx.lineTo(v.width - railW, yTop); }
            if (yBot > 0 && yBot < v.height) { ctx.moveTo(0, yBot); ctx.lineTo(v.width - railW, yBot); }
            ctx.stroke();
            ctx.setLineDash([]);
        }
        ctx.restore();
    }

    /* ── executed flow: what traded where, and what the book did ─────────── */

    function drawFlow(ctx) {
        const v = state.view;
        const colW = Math.max(1, v.scaleX);
        const x0 = -colW;
        const x1 = v.width + colW;
        let bubbles = 0;
        let marks = 0;

        /* Executed volume from the depth matrix: the columns the live tape no longer covers. */
        for (const cell of state.data.traded) {
            const x = worldX(cell.col) + colW * 0.5;
            if (x < x0 || x > x1) continue;
            const r = math.sweepRadius(cell.size, state.params.sweepC * 0.8, 1.5, 26);
            if (r < 1.6) continue;
            const y = priceToY(cell.price);
            if (y < 0 || y > v.height) continue;
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.fillStyle = cell.side === 'sell' ? 'rgba(255,93,108,.16)' : 'rgba(53,208,127,.16)';
            ctx.fill();
            ctx.strokeStyle = cell.side === 'sell' ? 'rgba(255,93,108,.55)' : 'rgba(53,208,127,.55)';
            ctx.lineWidth = 1;
            ctx.stroke();
            bubbles += 1;
            if (bubbles > 3000) break;
        }

        /* Book events: stack (liquidity piling up) and pull (liquidity leaving). */
        for (const ev of state.data.flowEvents) {
            const col = Number(ev.col);
            if (!Number.isFinite(col)) continue;
            const x = worldX(col) + colW * 0.5;
            if (x < x0 || x > x1) continue;
            const y = priceToY(Number(ev.price) || 0);
            if (y < 0 || y > v.height) continue;
            const up = (ev.direction === 'ask');
            const stack = ev.kind === 'stack';
            ctx.strokeStyle = stack
                ? (up ? math.rgba('stackUp', '.95') : math.rgba('stackDown', '.95'))
                : math.rgba('pull', '.9');
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            if (stack) {
                ctx.moveTo(x - 3, y + (up ? 3 : -3));
                ctx.lineTo(x, y + (up ? -3 : 3));
                ctx.lineTo(x + 3, y + (up ? 3 : -3));
            } else {
                ctx.moveTo(x - 3, y - 3);
                ctx.lineTo(x + 3, y + 3);
                ctx.moveTo(x + 3, y - 3);
                ctx.lineTo(x - 3, y + 3);
            }
            ctx.stroke();
            marks += 1;
            if (marks > 2000) break;
        }

        /* Best bid/ask per column: the spread line the depth map implies. */
        if (state.data.best.length) {
            ctx.strokeStyle = math.rgba('spread', '.35');
            ctx.lineWidth = 1;
            ctx.beginPath();
            let started = false;
            for (const b of state.data.best) {
                const x = worldX(b.col) + colW * 0.5;
                if (x < x0) { started = false; continue; }
                if (x > x1) break;
                const y = priceToY((Number(b.bid) + Number(b.ask)) / 2);
                if (y < 0 || y > v.height) { started = false; continue; }
                if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
            }
            ctx.stroke();
        }

        state.stats.flowBubbles = bubbles;
        state.stats.flowEvents = marks;
    }

    function fitHeight() {
        const bars = state.data.bars;
        if (!bars.length) return;
        /* Fit the bars the viewport actually shows: fitting the whole session leaves the stage
           almost empty once the view is zoomed in, and squeezes cells below text height. */
        const start = Math.max(0, Math.floor(state.view.offX));
        const end = Math.min(bars.length, Math.ceil(xToIndex(state.view.width)) + 1);
        let lo = Infinity, hi = -Infinity;
        for (let i = start; i < end; i += 1) { lo = Math.min(lo, bars[i].low); hi = Math.max(hi, bars[i].high); }
        if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return;
        const pad = (hi - lo) * 0.08;
        state.view.offY = lo - pad;
        state.view.scaleY = state.view.height / ((hi + pad) - state.view.offY);
    }

    /* One rgba table per (scale, ramp): rebuilt only when either actually changes. */
    function heatPaletteFor() {
        const key = `${state.data.heatScale}|${state.params.ramp}`;
        if (!state.data.palette || state.data.palette.key !== key) {
            state.data.palette = { key, pal: math.heatPalette(state.data.heatScale, state.params.ramp, 64, 32) };
        }
        return state.data.palette.pal;
    }

    function drawHeat(ctx) {
        const heat = state.data.heat;
        if (!heat || !heat.length) return 0;
        const v = state.view;
        const colW = Math.max(1, v.scaleX);
        const now = state.lastPaint || Date.now();
        const idx = state.data.heatIndex || (state.data.heatIndex = math.heatColumns(heat));
        const pal = heatPaletteFor();
        const strings = pal.strings;
        let decayed = 0;
        /* Column range first (binary search over the ordered column keys), then the rows inside
           those columns only. Same picture as the per-cell bounds test, without the 30k
           iterations a pass: cells outside the viewport are never touched. */
        const cols = idx.cols;
        let lo = 0;
        let hi = cols.length - 1;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (worldX(cols[mid]) < -colW) lo = mid + 1; else hi = mid;
        }
        for (let ci = lo; ci < cols.length; ci += 1) {
            const col = cols[ci];
            const x = worldX(col);
            if (x > v.width + colW) break;
            if (x < -colW) continue;
            const cells = idx.groups.get(col) || [];
            for (const cell of cells) {
                const y0 = priceToY(cell.hi);
                const y1 = priceToY(cell.lo);
                if (y1 < 0 || y0 > v.height) continue;
                let alpha;
                if (cell.size > 0) {
                    /* live cell: density colour at full strength, stamped for the decay pass */
                    alpha = 0.92;
                    cell.alpha = alpha;
                    cell.seen = now;
                    cell.peak = Math.max(cell.peak || 0, alpha);
                    cell.lastSize = cell.size;
                } else if ((cell.alpha || 0) > 0.004) {
                    /* liquidity left this level: keep the colour of the size that was there and
                       let the alpha decay exponentially (Alpha_t = Alpha_0 * e^(-t/lambda)) */
                    const dt = now - (cell.seen || now);
                    alpha = math.decayAlpha(cell.peak || cell.alpha, dt, state.params.lambda);
                    cell.alpha = alpha;
                    decayed += 1;
                } else {
                    continue;
                }
                if (alpha <= 0.004) continue;
                ctx.fillStyle = strings[pal.index(cell.lastSize || 1, alpha)] || strings[0];
                ctx.fillRect(x, Math.min(y0, y1), colW, Math.max(1, Math.abs(y1 - y0)));
            }
        }
        state.stats.decayCells = decayed;
        return decayed;
    }

    function drawFootprint(ctx) {
        const bars = state.data.bars;
        if (!bars.length) return;
        const v = state.view;
        const lod = state.lod;
        const start = Math.max(0, Math.floor(v.offX) - 1);
        const end = Math.min(bars.length, Math.ceil(xToIndex(v.width)) + 2);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        /* Row height comes from the data (tick spacing) and the price scale. BTC quotes in 0.5
           steps: a session-wide fit would put ~470 rows in 520px, so the rows are grouped into
           k-tick clusters whose totals are summed — the footprint stays readable instead of
           collapsing straight to profiles. */
        const probe = state.data.levels.get(bars[Math.min(start, bars.length - 1)].time) || [];
        const levelStep = probe.length > 1 ? Math.abs(probe[1].price - probe[0].price) : 0;
        const cellPx = math.cellHeightPx(levelStep, v.scaleY);
        const groupK = math.tickGroup(levelStep, v.scaleY, state.params.minRowPx);
        const grouped = groupK > 1;
        /* Grouping keeps every drawn row at minRowPx, so density is solved by construction; the
           profile fallback is only for the absurd case (a bar whose price range would still need
           more drawn rows than any stage can show). Width-based LOD covers the zoomed-out case. */
        const rowsPerBar = levelStep ? Math.ceil(probe.length / groupK) : 0;
        const groupFallback = rowsPerBar > 600;
        state.stats.cellPx = cellPx * groupK;
        state.stats.groupK = groupK;
        state.stats.aggregating = lod.mode === 'profile' || groupFallback;
        /* Counted per paint so the badge's presence is assertable, not just visible. */
        state.stats.columnBadges = 0;

        for (let i = start; i < end; i += 1) {
            const bar = bars[i];
            const x = worldX(i);
            const colW = Math.max(1, v.scaleX);
            const raw = state.data.levels.get(bar.time) || [];
            if (!raw.length) continue;

            if (lod.mode === 'profile' || groupFallback) {
                const prof = math.rowShares(raw, state.params.vaPct);
                const total = prof.candleTotal || 1;
                const h = Math.min(v.height * 0.5, Math.max(3, (state.avgBarVolume ? total / state.avgBarVolume : 1) * v.height * 0.06));
                const half = (colW - 2) / 2;
                const y = priceToY(bar.close);
                let bidSum = 0, askSum = 0;
                for (const row of prof.rows) { bidSum += row.bid; askSum += row.ask; }
                const bidW = bidSum + askSum ? (bidSum / (bidSum + askSum)) * (colW - 2) : half;
                ctx.fillStyle = math.rgba('bid', '.34');
                ctx.fillRect(x + 1, y - h / 2, bidW, h);
                ctx.fillStyle = math.rgba('ask', '.34');
                ctx.fillRect(x + 1 + bidW, y - h / 2, (colW - 2) - bidW, h);
                continue;
            }

            const rows = grouped ? math.groupLevels(raw, groupK) : raw.map((l) => ({ ...l, ticks: 1 }));
            const cellH = Math.max(2, Math.abs(math.cellHeightPx(levelStep, v.scaleY)) * groupK);
            const textHere = math.textFits(cellH) && lod.text;
            if (lod.text && !textHere) state.stats.textStarved += 1;
            const shares = math.rowShares(rows, state.params.vaPct);
            const { rows: imRows } = math.diagonalImbalance(rows, state.params.R);
            const zones = math.stackedZones(imRows, state.params.stack);
            const half = colW / 2;
            /* Drawn after the cells and before the text: a translucent band with a solid leading
               rail, so a stacked run reads as one object without the digits losing contrast. */
            zones.forEach((zone) => {
                const yTop = priceToY(zone.high);
                const yBot = priceToY(zone.low);
                const y0 = Math.min(yTop, yBot), y1 = Math.max(yTop, yBot);
                if (y1 < 0 || y0 > v.height) return;
                const tint = zone.side === 'buy' ? 'rgba(86,214,255,' : 'rgba(255,93,200,';   // zone bands: stackUp / stackDown
                ctx.fillStyle = tint + '0.12)';
                ctx.fillRect(x, y0, colW, y1 - y0);
                ctx.fillStyle = tint + '0.85)';
                ctx.fillRect(x, y0, 2.5, y1 - y0);
                if (cellH >= 7 && colW > 54) {
                    ctx.font = '600 9px ui-monospace, monospace';
                    ctx.fillStyle = tint + '0.9)';
                    ctx.fillText('STACK ' + (zone.count || '') + 'L', x + 5, y0 + 9);
                }
            });

            /* Bar framing first: an alternating band plus a right-edge separator, so adjacent
               bars are distinguishable without reading a single number (they were not: with the
               band gone the matrix read as one continuous slab). */
            ctx.fillStyle = i % 2 ? 'rgba(255,255,255,.016)' : 'rgba(0,0,0,.10)';
            ctx.fillRect(x, 0, colW, v.height);
            ctx.fillStyle = 'rgba(150,175,215,.18)';
            ctx.fillRect(x + colW - 1, 0, 1, v.height);

            for (let k = 0; k < rows.length; k += 1) {
                const level = rows[k];
                const im = imRows[k];
                const y = priceToY(level.price) - cellH / 2;
                if (y < -cellH || y > v.height + cellH) continue;
                const info = shares.rows[k] || { share: 0, inVA: false };
                const buyHot = im.side === 'buy' || im.side === 'both';
                const sellHot = im.side === 'sell' || im.side === 'both';

                /* Ground: value-area rows sit on a lighter slate than the outer 30%. */
                if (info.inVA) {
                    ctx.fillStyle = math.rgba('vaGround', '.10');
                    ctx.fillRect(x, y, colW, cellH);
                }
                /* HVN: the heaviest row of the candle carries a warm tint under everything. */
                if (level.price === shares.hvn) {
                    ctx.fillStyle = math.rgba('hvn', '.12');
                    ctx.fillRect(x, y, colW, cellH);
                }
                /* Proportional shading: a split histogram bar inside the row — bid share grows
                   from the centre to the left, ask share from the centre to the right. */
                const barW = Math.max(0.5, (colW - 3) * Math.min(1, info.share * 3));
                const bidW = level.bid + level.ask > 0 ? barW * (level.bid / (level.bid + level.ask)) : barW / 2;
                ctx.fillStyle = math.rgba('bid', '.30');
                ctx.fillRect(x + half - bidW, y + Math.max(0, cellH * 0.18), bidW, Math.max(1, cellH * 0.64));
                ctx.fillStyle = math.rgba('ask', '.30');
                ctx.fillRect(x + half, y + Math.max(0, cellH * 0.18), Math.max(0, barW - bidW), Math.max(1, cellH * 0.64));
                /* Imbalance tint stays on the text-bearing half only. */
                if (buyHot) { ctx.fillStyle = math.rgba('imBuy', '.18'); ctx.fillRect(x, y, half, cellH); }
                if (sellHot) { ctx.fillStyle = math.rgba('imSell', '.18'); ctx.fillRect(x + half, y, half, cellH); }
                if (!textHere) continue;

                const size = Math.max(7, Math.min(13, cellH - 1));
                const bidText = math.fmtSize(level.bid);
                const askText = math.fmtSize(level.ask);
                /* An empty half is a dot, not a "0": the matrix used to be decorated with zeros and
                   the numbers that matter were rounded to them at the same time. */
                ctx.font = `${math.fontWeight(level.bid, state.avgLevelVolume, 4)} ${size}px ui-monospace, monospace`;
                ctx.fillStyle = bidText ? (buyHot ? '#8ff6ff' : '#d3dceb') : 'rgba(150,175,215,.35)';
                ctx.fillText(bidText || '·', x + colW * 0.25, y + cellH / 2);
                ctx.font = `${math.fontWeight(level.ask, state.avgLevelVolume, 4)} ${size}px ui-monospace, monospace`;
                ctx.fillStyle = askText ? (sellHot ? '#ff9ad8' : '#d3dceb') : 'rgba(150,175,215,.35)';
                ctx.fillText(askText || '·', x + colW * 0.75, y + cellH / 2);
            }

            /* Value-area frame: VAH/VAL edges, labelled once per viewport edge. */
            if (shares.vaCount) {
                ctx.strokeStyle = math.rgba('vaEdge', '.45');
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, priceToY(shares.vaHigh) - cellH / 2);
                ctx.lineTo(x + colW, priceToY(shares.vaHigh) - cellH / 2);
                ctx.moveTo(x, priceToY(shares.vaLow) + cellH / 2);
                ctx.lineTo(x + colW, priceToY(shares.vaLow) + cellH / 2);
                ctx.stroke();
            }

            for (const zone of zones) {
                const yTop = priceToY(zone.high) - cellH / 2;
                const yBot = priceToY(zone.low) + cellH / 2;
                const colour = zone.side === 'buy' ? '64,224,255' : '255,64,196';
                ctx.fillStyle = `rgba(${colour},${(0.10 + Math.min(0.10, zone.count * 0.02)).toFixed(3)})`;
                ctx.fillRect(x, yTop, v.width - x, Math.max(2, yBot - yTop));
                ctx.fillStyle = `rgba(${colour},.55)`;
                ctx.fillRect(x, yTop, Math.min(46, colW), 1);
                ctx.fillRect(x, yBot, Math.min(46, colW), 1);
            }

            const poc = math.poc(rows);
            if (poc) {
                const y = priceToY(poc.price) - cellH / 2;
                ctx.save();
                ctx.shadowColor = 'rgba(255,214,102,.9)';
                ctx.shadowBlur = math.glowRadius(colW, cellH);
                ctx.strokeStyle = i === bars.length - 1 ? 'rgba(255,236,160,1)' : math.rgba('poc', '.95');
                ctx.lineWidth = Math.min(2, Math.max(1, cellH * 0.14));
                ctx.strokeRect(x + 0.5, y + 0.5, colW - 1, cellH - 1);
                ctx.restore();
                ctx.fillStyle = math.rgba('poc', '.95');
                ctx.fillRect(x + colW - 3, y + Math.max(0, cellH / 2 - 1), 3, Math.max(2, cellH * 0.5));
            }

            ctx.strokeStyle = math.rgba('wick', '.35');
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x + colW / 2, priceToY(bar.high));
            ctx.lineTo(x + colW / 2, priceToY(bar.low));
            ctx.stroke();

            /* Column stats: the bar's own delta and volume, hung above its high where an
               order-flow reader looks for them. Only where the column can carry the text. */
            if (colW >= 48 && lod.text) {
                const dy = priceToY(bar.high) - 12;
                if (dy > 8) {
                    const delta = Number(bar.delta) || 0;
                    const vol = Number(bar.volume) || 0;
                    ctx.font = '600 10px ui-monospace, monospace';
                    ctx.textAlign = 'left';
                    ctx.fillStyle = delta >= 0 ? math.rgba('bid', '.9') : math.rgba('ask', '.9');
                    ctx.fillText(`Δ${delta >= 0 ? '+' : ''}${math.fmtSize(delta) || '0'}`, x + 3, dy);
                    ctx.fillStyle = 'rgba(150,175,215,.75)';
                    ctx.fillText(`V${math.fmtSize(vol) || '0'}`, x + colW * 0.55, dy);
                    ctx.textAlign = 'center';
                    state.stats.columnBadges += 1;
                }
            }
        }
    }

    function drawSweeps(ctx) {
        const prints = state.data.prints;
        if (!prints || !prints.length) return;
        const v = state.view;
        const bars = state.data.bars;
        const barSec = barSeconds();
        const byBar = new Map();
        let matched = 0;
        for (const p of prints) {
            /* One binary search per print (math.barIndex). This used to be bars.find(...)
               plus bars.indexOf(bar): two linear scans per print, measured at 29.9 ms for a
               single repaint of this layer with 4000 prints against 1440 bars. */
            const i = math.barIndex(bars, p.time);
            if (i < 0) continue;
            if (Number(p.time) >= Number(bars[i].time) + barSec) continue;
            matched += 1;
            const key = `${i}|${p.price}`;
            const cur = byBar.get(key) || { i, price: Number(p.price) || 0, size: 0, sell: 0, buy: 0, t: p.time };
            cur.size += Number(p.size) || 0;
            if (p.side === 'sell') cur.sell += Number(p.size) || 0; else cur.buy += Number(p.size) || 0;
            cur.t = Math.max(cur.t, p.time);
            byBar.set(key, cur);
        }
        let filtered = 0;
        for (const sweep of byBar.values()) {
            /* Live noise filter: the slider hides small blocks without re-fetching anything. */
            if (sweep.size < (Number(state.params.minBlock) || 0)) { filtered += 1; continue; }
            const x = worldX(sweep.i) + v.scaleX / 2;
            if (x < -20 || x > v.width + 20) continue;
            const y = priceToY(sweep.price);
            const r = math.sweepRadius(sweep.size, state.params.sweepC);
            const split = math.sideSplit(sweep.buy, sweep.sell);
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.fillStyle = split.twoSided ? math.rgba('sweepTwo', '.20')
                : (sweep.buy >= sweep.sell ? 'rgba(53,208,127,.26)' : 'rgba(255,93,108,.26)');
            ctx.fill();
            if (split.twoSided) {
                /* A block that took both sides shows its split: buys swept one way, sells the other. */
                const a0 = -Math.PI / 2;
                const a1 = a0 + Math.PI * 2 * split.buyFrac;
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.arc(x, y, r, a0, a1);
                ctx.closePath();
                ctx.fillStyle = math.rgba('bid', '.45');
                ctx.fill();
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.arc(x, y, r, a1, a0 + Math.PI * 2);
                ctx.closePath();
                ctx.fillStyle = math.rgba('ask', '.45');
                ctx.fill();
            }
            ctx.strokeStyle = split.twoSided ? 'rgba(200,215,240,.75)'
                : (sweep.buy >= sweep.sell ? math.rgba('imBuy', '.85') : math.rgba('imSell', '.85'));
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.stroke();
        }
        state.stats.printsSeen = prints.length;
        state.stats.printsMatched = matched;
        state.stats.sweepBubbles = byBar.size;
        state.stats.blocksFiltered = filtered;
    }

    function barSeconds() {
        const bars = state.data.bars;
        if (bars.length < 2) return 60;
        return Math.max(1, bars[bars.length - 1].time - bars[bars.length - 2].time);
    }

    function drawHud(ctx) {
        const h = state.hover;
        if (!h) return;
        const v = state.view;
        /* crosshair -> live ladder reference line: trace from the cursor straight across to
           the price rail, so the eye never loses the level between chart and book. */
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = 'rgba(255,214,102,.75)';
        ctx.beginPath();
        ctx.moveTo(h.x, h.y);
        ctx.lineTo(v.width - 54, h.y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.strokeStyle = 'rgba(150,170,200,.35)';
        ctx.beginPath();
        ctx.moveTo(h.x, 0);
        ctx.lineTo(h.x, v.height);
        ctx.stroke();
        ctx.fillStyle = 'rgba(255,214,102,.95)';
        ctx.font = '500 11px ui-monospace, monospace';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(h.price.toFixed(2), v.width - 50, h.y);
        ctx.restore();
    }

    function drawRibbon() {
        const canvas = state.layers.ribbon;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const { width, height } = canvas;
        ctx.clearRect(0, 0, width, height);
        const bars = state.data.bars;
        if (!bars.length) return;
        const laneH = height / 3;
        const cvd = [];
        let run = 0;
        for (const b of bars) { run += Number(b.delta) || 0; cvd.push(run); }
        const maxVol = Math.max(1, ...bars.map((b) => Number(b.volume) || 0));
        const maxDelta = Math.max(1, ...bars.map((b) => Math.abs(Number(b.delta) || 0)));
        const cvdLo = Math.min(...cvd, 0);
        const cvdHi = Math.max(...cvd, 1);
        const colW = Math.max(1, state.view.scaleX);
        const start = Math.max(0, Math.floor(state.view.offX) - 1);
        const end = Math.min(bars.length, Math.ceil(xToIndex(state.view.width)) + 2);
        /* Reset here, not inside the loop: an empty viewport used to leave the previous
           viewport's path in place and the fill was drawn from stale coordinates. */
        state.ribbonPath = [];

        for (let i = start; i < end; i += 1) {
            const x = worldX(i);
            const vol = Number(bars[i].volume) || 0;
            const d = Number(bars[i].delta) || 0;
            ctx.fillStyle = math.rgba('vol', '.5');
            ctx.fillRect(x, laneH - (vol / maxVol) * (laneH - 4), Math.max(1, colW - 1), (vol / maxVol) * (laneH - 4));

            /* Delta lane: two-tone when the bar's delta swings hard against the previous one,
               which is the participation change the blueprint wants visible, not averaged away. */
            const prev = Number(bars[i - 1] && bars[i - 1].delta) || 0;
            const swing = Math.abs(d - prev) > maxDelta * 0.5;
            const mid = laneH * 1.5;
            const dh = (Math.abs(d) / maxDelta) * (laneH / 2 - 2);
            ctx.fillStyle = d >= 0
                ? (swing ? math.rgba('bid', '1') : math.rgba('bid', '.62'))
                : (swing ? math.rgba('ask', '1') : math.rgba('ask', '.62'));
            ctx.fillRect(x, d >= 0 ? mid - dh : mid, Math.max(1, colW - 1), Math.max(1, dh));

            const y = laneH * 2 + laneH - ((cvd[i] - cvdLo) / Math.max(1, cvdHi - cvdLo)) * (laneH - 6);
            if (i === start) {
                ctx.beginPath();
                ctx.moveTo(x, y);
                state.ribbonPath.push([x, y]);
            } else {
                ctx.lineTo(x, y);
                state.ribbonPath.push([x, y]);
            }
        }
        /* Filled CVD body, then the divergence accent on top of the stroke. */
        const path = state.ribbonPath || [];
        if (path.length > 1) {
            ctx.lineTo(path[path.length - 1][0], height);
            ctx.lineTo(path[0][0], height);
            ctx.closePath();
            ctx.fillStyle = math.rgba('cvdBody', '.16');
            ctx.fill();
            ctx.beginPath();
            ctx.moveTo(path[0][0], path[0][1]);
            for (const [px, py] of path.slice(1)) ctx.lineTo(px, py);
        }
        const div = math.cvdDivergence(bars.slice(Math.max(0, start), end), 12);
        state.stats.divState = div.state;
        if (div.state !== 'none') {
            /* Price and aggressive flow disagreeing: the trace breathes neon in the direction
               of the flow, so the disagreement is visible at a glance. */
            const pulse = 0.55 + 0.45 * Math.abs(Math.sin((state.lastPaint || Date.now()) / 420));
            const grad = ctx.createLinearGradient(0, 0, width, 0);
            const hot = div.state === 'bull' ? '53,208,127' : '255,93,108';
            grad.addColorStop(0, `rgba(${hot},${(0.35 * pulse).toFixed(2)})`);
            grad.addColorStop(0.55, `rgba(${hot},${(0.95 * pulse).toFixed(2)})`);
            grad.addColorStop(1, `rgba(255,242,196,${(0.85 * pulse).toFixed(2)})`);
            ctx.strokeStyle = grad;
            ctx.lineWidth = 2.4;
        } else {
            ctx.strokeStyle = 'rgba(255,214,102,.9)';
            ctx.lineWidth = 1.5;
        }
        ctx.stroke();
        ctx.lineWidth = 1;

        ctx.font = '500 10px ui-monospace, monospace';
        ctx.textAlign = 'left';
        ctx.fillStyle = 'rgba(150,170,200,.85)';
        ctx.fillText('VOL', 6, 12);
        ctx.fillText('DELTA', 6, laneH + 12);
        ctx.fillText('CVD', 6, laneH * 2 + 12);
        if (div.state !== 'none') {
            ctx.fillStyle = div.state === 'bull' ? 'rgba(53,208,127,1)' : 'rgba(255,93,108,1)';
            ctx.fillText(div.state === 'bull' ? 'CVD DIVERGENCE ▲ price down / flow up'
                                              : 'CVD DIVERGENCE ▼ price up / flow down', 40, laneH * 2 + 12);
        }
    }

    /* ── frame scheduler: one rAF loop, dirty layers, measured budget ────── */

    function renderLayers(force) {
        const t0 = performance.now();
        state.lastPaint = Date.now();
        const job = [];
        if (state.dirty.heat || force) job.push('heat');
        if (state.dirty.base || force) job.push('base');
        if (state.dirty.live || force) job.push('live');
        if (state.dirty.ribbon || force) job.push('ribbon');
        for (const name of job) {
            const canvas = state.layers[name];
            /* The flag is cleared whether or not a canvas is attached: a null layer used to
               stay dirty for ever, which kept this loop running on every animation frame and
               made the frame counter look healthy while nothing was drawn. */
            state.dirty[name] = false;
            if (!canvas) continue;
            const ctx = canvas.getContext('2d');
            if (name === 'heat') {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawHeat(ctx);
                state.stats.heatPasses += 1;
            } else if (name === 'base') {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                /* Axes first, then the matrix, then the executed-flow overlay: the frame must read
                   as a chart (what price, what time, where the data is) even before a bar is drawn. */
                drawAxes(ctx);
                drawFootprint(ctx);
                drawFlow(ctx);
            } else if (name === 'live') {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawSweeps(ctx);
                drawHud(ctx);
            } else if (name === 'ribbon') {
                drawRibbon();
            }
        }
        const ms = performance.now() - t0;
        state.stats.frames += 1;
        state.stats.lastMs = ms;
        state.stats.emaMs = state.stats.emaMs ? state.stats.emaMs * 0.9 + ms * 0.1 : ms;
        state.stats.framesMs.push(ms);
        if (state.stats.framesMs.length > 240) state.stats.framesMs.shift();
        if (state.stats.framesMs.length % 30 === 0) {
            const sorted = state.stats.framesMs.slice().sort((a, b) => a - b);
            state.stats.p95Ms = sorted[Math.floor(sorted.length * 0.95)] || 0;
        }
        return ms;
    }

    let rafHandle = 0;
    let heatAccum = 0;
    let lastTick = 0;
    function tick(now) {
        rafHandle = requestAnimationFrame(tick);
        const dt = lastTick ? now - lastTick : 16;
        lastTick = now;
        /* decay runs at ~30 Hz: lambda is 500 ms, so a 60 Hz repaint of it is wasted work */
        heatAccum += dt;
        if (heatAccum >= 33 && state.data.heat.length) {
            heatAccum = 0;
            state.dirty.heat = true;
        }
        if (state.invalidateBase) { state.dirty.base = true; state.invalidateBase = false; }
        if (state.dirty.heat || state.dirty.base || state.dirty.live || state.dirty.ribbon) renderLayers(false);
    }

    function start() {
        if (!rafHandle) rafHandle = requestAnimationFrame(tick);
        if (typeof document !== 'undefined' && !start.wired) {
            start.wired = true;
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) renderLayers(true);
            });
        }
    }
    function stop() {
        if (rafHandle) cancelAnimationFrame(rafHandle);
        rafHandle = 0;
    }

    /* ── interaction: asymmetric zoom, pan, hover ────────────────────────── */

    function attach(canvas) {
        state.layers.base = canvas;
        canvas.addEventListener('wheel', (ev) => {
            /* A trackpad pinch arrives as ctrl+wheel; the browser would zoom the whole page, so it
               is cancelled here and given the price-axis maths below, around the gesture's own point. */
            if (ev.ctrlKey) {
                ev.preventDefault();
                const pinchRect = canvas.getBoundingClientRect();
                const pinchY = ev.clientY - pinchRect.top;
                const overPrice = yToPrice(pinchY);
                const zoomed = Math.max(0.02, Math.min(40, state.view.scaleY * (ev.deltaY < 0 ? 1.09 : 0.92)));
                state.view.scaleY = zoomed;
                state.view.offY = overPrice - (state.view.height - pinchY) / zoomed;
                state.autoFit = false;                    // the user owns the price axis now
                state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
                applyLod();
                return;
            }
            ev.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mx = ev.clientX - rect.left;
            const my = ev.clientY - rect.top;
            if (ev.shiftKey) {
                /* X-axis only: zoom time around the cursor, price scale untouched */
                const idx = xToIndex(mx);
                state.view.scaleX = Math.max(2.5, Math.min(90, state.view.scaleX * (ev.deltaY < 0 ? 1.12 : 0.89)));
                state.view.offX = idx - mx / state.view.scaleX;
                if (state.autoFit) fitHeight();
            } else {
                /* Y-axis only: zoom price around the cursor, time scale untouched */
                const price = yToPrice(my);
                const next = Math.max(0.02, Math.min(40, state.view.scaleY * (ev.deltaY < 0 ? 1.09 : 0.92)));
                state.view.scaleY = next;
                state.view.offY = price - (state.view.height - my) / next;
                state.autoFit = false;                       // the user owns the price axis now
            }
            state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
            applyLod();
        }, { passive: false });

        let drag = null;
        canvas.addEventListener('mousedown', (ev) => { drag = { x: ev.clientX, y: ev.clientY, ox: state.view.offX, oy: state.view.offY }; });
        window.addEventListener('mouseup', () => { drag = null; });
        window.addEventListener('mousemove', (ev) => {
            if (drag) {
                const dx = (ev.clientX - drag.x) / state.view.scaleX;
                const dy = (ev.clientY - drag.y) / state.view.scaleY;
                state.view.offX = drag.ox - dx;
                state.view.offY = drag.oy + dy;
                if (dy) state.autoFit = false;
                clampView();
                if (state.autoFit) fitHeight();
                state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
                applyMode();
                return;
            }
            const rect = canvas.getBoundingClientRect();
            if (ev.clientX < rect.left || ev.clientX > rect.right || ev.clientY < rect.top || ev.clientY > rect.bottom) return;
            hover(ev.clientX - rect.left, ev.clientY - rect.top);
        });
    }

    /* The single gate every viewport change goes through: clamp the zooms, clamp the offsets,
       and if the window somehow ends up with no bar in it, re-anchor on the newest data instead of
       leaving an empty stage. `stats.recovered` counts those saves. */
    function viewBounds() {
        const last = state.data.bars[state.data.bars.length - 1];
        const probe = (last && state.data.levels.get(last.time)) || [];
        const step = probe.length > 1 ? Math.abs(probe[1].price - probe[0].price) : 0;
        return math.viewLimits({ bars: state.data.bars, view: state.view, step });
    }

    function barsOnScreen() {
        const v = state.view;
        const n = state.data.bars.length;
        if (!n) return 0;
        const first = Math.max(0, Math.floor(v.offX));
        const last = Math.min(n, Math.ceil(xToIndex(v.width)) + 1);
        return Math.max(0, last - first);
    }

    function clampView() {
        /* Two phases on purpose: the price-offset window is derived from scaleY, so the zoom has to
           be settled before the offsets are bounded, or the offsets get clamped against a scale the
           view no longer has. */
        const first = viewBounds();
        const before = [state.view.offX, state.view.offY, state.view.scaleX, state.view.scaleY];
        state.view.scaleX = Math.max(first.minScaleX, Math.min(first.maxScaleX, state.view.scaleX));
        state.view.scaleY = Math.max(first.minScaleY, Math.min(first.maxScaleY, state.view.scaleY));
        const lim = viewBounds();
        state.view.offX = Math.max(lim.minOffX, Math.min(lim.maxOffX, state.view.offX));
        if (state.data.bars.length) {
            state.view.offY = Math.max(lim.minOffY, Math.min(lim.maxOffY, state.view.offY));
        }
        if (state.data.bars.length && !barsOnScreen()) {
            /* Nothing to look at: put the newest bars back in view and say it happened. */
            state.stats.recovered += 1;
            state.view.offX = Math.max(0, state.data.bars.length - Math.max(1, state.view.width / state.view.scaleX));
            if (state.autoFit) fitHeight();
        }
        return {
            clamped: before[0] !== state.view.offX || before[1] !== state.view.offY
                || before[2] !== state.view.scaleX || before[3] !== state.view.scaleY,
            bars: barsOnScreen(),
        };
    }

    function hover(mx, my) {
        const n = state.data.bars.length;
        if (!n) { state.hover = null; if (typeof state.onHover === 'function') state.onHover(null); return; }
        const i = Math.max(0, Math.min(n - 1, Math.floor(xToIndex(mx))));
        const bar = state.data.bars[i];
        if (!bar) return;
        const price = yToPrice(my);
        const rows = state.data.levels.get(bar.time) || [];
        const { rows: imRows, buyCount, sellCount } = math.diagonalImbalance(rows, state.params.R);
        let cvd = 0;
        for (let k = 0; k <= i; k += 1) cvd += Number(state.data.bars[k].delta) || 0;
        let total = 0;
        for (const l of rows) total += l.bid + l.ask;
        const near = nearestLevel(rows, price);
        const nearIdx = near ? rows.indexOf(near.level) : -1;
        const im = nearIdx >= 0 ? imRows[nearIdx] : null;
        const zones = math.stackedZones(imRows, state.params.stack);
        const zone = near ? zones.find((z) => z.low <= near.level.price && near.level.price <= z.high) : null;
        /* Depth at the hovered row, from the depth matrix's own column for this bar. */
        let depth = 0;
        for (const cell of state.data.heat) {
            if (cell.col !== i) continue;
            if (near && cell.lo <= near.level.price && near.level.price < cell.hi) depth += cell.size;
        }
        const prints = [];
        for (const p of state.data.prints) {
            if (p.time >= bar.time && p.time < bar.time + barSeconds()) prints.push(p);
        }
        let sweep = 0;
        for (const p of prints) sweep += Number(p.size) || 0;
        const events = state.data.flowEvents.filter((e) => Number(e.col) === i);
        state.hover = {
            x: mx, y: my, price, index: i, bar,
            barTime: bar.time, cvd, total, buyCount, sellCount, zones: zones.length,
            zone: zone ? { side: zone.side, count: zone.count, low: zone.low, high: zone.high } : null,
            level: near ? { price: near.level.price, bid: near.level.bid, ask: near.level.ask, dist: near.dist } : null,
            imbalance: im ? { side: im.side, ratio: im.ratio, buy: im.buy, sell: im.sell } : null,
            depth, prints: prints.length, sweep,
            events: events.map((e) => ({ kind: e.kind, direction: e.direction, price: e.price, size: e.size })),
            calc: bar.calc || null,
            visibleBars: barsOnScreen(),
        };
        state.dirty.live = true;
        if (typeof state.onHover === 'function') state.onHover(state.hover);
    }

    function applyLod() {
        const colW = state.view.scaleX;
        state.lod = math.lod(colW, state.params.textPx);
        state.dirty.base = state.dirty.live = true;
    }

    function applyMode() {
        state.mode = math.viewportMode(state.view.offX, state.view.width / state.view.scaleX, Math.max(0, state.data.bars.length - 1));
        if (typeof state.onMode === 'function') state.onMode(state.mode);
    }

    /* Show the whole session inside the stage, then let the clamps trim it if the data is too thin
       or too dense to fit exactly: the user can always get back to "everything" in one action. */
    function fitSession() {
        const bars = state.data.bars;
        if (!bars.length) return;
        const lim = viewBounds();
        state.view.scaleX = Math.max(lim.minScaleX, Math.min(lim.maxScaleX, state.view.width / Math.max(4, bars.length)));
        state.view.offX = lim.minOffX;
        state.autoFit = true;
        clampView();
        fitHeight();
        applyLod();
        applyMode();
        state.autoFit = true;
        state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
    }

    function snapToLive() {
        state.autoFit = true;
        state.view.offX = Math.max(0, state.data.bars.length - Math.floor(state.view.width / state.view.scaleX));
        fitHeight();
        clampView();
        applyMode();
        state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
    }

    function resize(width, height) {
        state.view.width = width;
        state.view.height = height;
        for (const key of ['heat', 'base', 'live']) {
            const c = state.layers[key];
            if (!c) continue;
            c.width = width;
            c.height = height;
        }
        const r = state.layers.ribbon;
        if (r) { r.width = width; r.height = 84; }
        fitHeight();
        applyLod();
        applyMode();
    }

    const ofx = {
        NS, math, state,
        worldX, xToIndex, priceToY, yToPrice,
        setData, profileBars, computeSessionAverages,
        indexLevels, renderLayers, start, stop, attach, resize,
        hover, applyLod, applyMode, clampView, viewBounds, barsOnScreen, snapToLive, fitSession, fitHeight, barSeconds, legend,
        stats() {
            const s = state.stats;
            return {
                frames: s.frames, lastMs: +s.lastMs.toFixed(2), emaMs: +s.emaMs.toFixed(2), p95Ms: +s.p95Ms.toFixed(2),
                heatPasses: s.heatPasses, decayCells: s.decayCells, mode: state.mode, lod: state.lod.mode,
                printsSeen: s.printsSeen, printsMatched: s.printsMatched, sweepBubbles: s.sweepBubbles,
                heatCells: state.data.heat.length, textStarved: s.textStarved, columnBadges: s.columnBadges || 0,
                autoFit: state.autoFit,
                cellPx: +s.cellPx.toFixed(2), aggregating: s.aggregating, groupK: s.groupK,
                divState: s.divState, blocksFiltered: s.blocksFiltered, maxFrameMs: s.framesMs.length ? +Math.max(...s.framesMs).toFixed(2) : 0,
                recovered: s.recovered, flowBubbles: s.flowBubbles, flowEvents: s.flowEvents, barsOnScreen: barsOnScreen(),
                colW: +state.view.scaleX.toFixed(1), levelCount: state.data.levels.size,
                avgLevelVolume: +state.avgLevelVolume.toFixed(2), symbol: state.symbol, params: { ...state.params },
            };
        },
        setParams(next) { Object.assign(state.params, next || {}); applyLod(); state.dirty.base = state.dirty.live = true; },
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = ofx;
    if (typeof globalThis !== 'undefined') globalThis.OFX = ofx;
    return ofx;
})(typeof globalThis !== 'undefined' ? globalThis : this);
