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

    /* The ramps the depth layer can draw. One list, read by the control, the legend and the selftest;
       `config_store.RAMP_KEYS` holds the same three names and `test_expression.py` keeps them equal,
       because a ramp the engine knows and the control does not is a feature nobody can reach. */
    const RAMPS = ['classic', 'thermal'];

    /* The engine's own bar chrome — what every bar drew before P1-8 existed, and what the `default`
       mode still means. `expression.js` declares the identical object for its `default` mode and
       `test_expression.py` holds the two equal, so "the default mode changes nothing" is checked. */
    const CHROME_DEFAULT = Object.freeze({ framing: true, ground: true, zones: true, poc: true, badges: true });

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

        /* §72: the backing store for one layer canvas — the CSS box at the display scale.
           dpr = 1 returns the CSS size unchanged, which is the identity this engine has always
           painted at; every display-scale fix keeps that identity as its regression pin. */
        layerSize(cssW, cssH, dpr) {
            const k = (Number(dpr) > 0) ? Number(dpr) : 1;
            return {
                w: Math.max(1, Math.round((Number(cssW) || 0) * k)),
                h: Math.max(1, Math.round((Number(cssH) || 0) * k)),
            };
        },

        /* Diagonal processing matrix — the analytics/footprint.py convention, one rule in two
           runtimes: a BUY is Ask[Y] against Bid[Y−1] (a lift through an offer with no bid of its
           own underneath); a SELL is Bid[Y] against Ask[Y+1]. A row with no neighbour falls back
           to its own volume on the compared side — the same-price comparison the Python engine
           uses at the ladder's edge. Returns per-level {buy, sell, ratio} plus counts. */
        diagonalImbalance(levels, R = 4.0) {
            const r = Number(R) > 0 ? Number(R) : 4.0;
            const list = levels || [];
            const rows = list.map((l, i) => {
                const bid = Number(l.bid) || 0;
                const ask = Number(l.ask) || 0;
                const below = list[i - 1] || null;
                const above = list[i + 1] || null;
                const bidCmp = below ? (Number(below.bid) || 0) : bid;
                const askCmp = above ? (Number(above.ask) || 0) : ask;
                const buyRatio = bidCmp > 0 ? ask / bidCmp : Infinity;
                const sellRatio = askCmp > 0 ? bid / askCmp : Infinity;
                /* A zero comparison means nothing rested on the other side of the diagonal —
                   that is the imbalance footprint.py flags; a row with no prints on the judged
                   side never is. */
                const buy = ask > 0 && (bidCmp <= 0 || buyRatio >= r);
                const sell = bid > 0 && (askCmp <= 0 || sellRatio >= r);
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
        /* Two ramps, both monotone in luminance — which is what lets a magnitude be read without
           colour vision, and which `ofx.selftest.js` MEASURES at 21 samples per ramp rather than
           asserting here. 'classic' runs slate blue -> orange -> white-hot gold; 'thermal' starts
           deeper (a near-black low end) and reaches the same white-hot top. Both are functions of one
           0..1 scalar, so switching ramps cannot change any value - only its display. */
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

        /* B2: the ramp position after the user's contrast dial. `ramp.js` owns the maths (one home
           for both surfaces); with the module absent — a bare node run — it is the identity. */
        rampT(t, gamma) {
            const m = root.OFAPRAMP;
            return m ? m.contrastT(t, gamma) : Math.min(1, Math.max(0, Number(t) || 0));
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
            if (!candleTotal) {
                /* No volume anywhere: no ranking is meaningful, so nothing is claimed as the value
                   area (audit C-15 — an empty snapshot used to label every row VA). */
                return { rows: rows.map((r) => ({ ...r, share: 0, inVA: false })),
                         candleTotal: 0, vaLow: 0, vaHigh: 0, hvn: 0, vaCount: 0 };
            }
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
                    /* C-04: the row is centred on the chunk's band — a grouped row stands for
                       [first...last], and pricing it at the top tick shifted every grouped row by
                       (k-1)/2 ticks. `label` keeps the top tick for labels/text. */
                    price: ((Number(chunk[0] && chunk[0].price) || 0) + (Number(last.price) || 0)) / 2,
                    label: Number(last.price) || 0,
                    bid, ask, ticks: chunk.length,
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
            const buckets = (payload && (payload.buckets || payload.times)) || null;
            if (!Array.isArray(buckets) || !buckets.length) return null;
            const step = Number(payload && payload.step) || Number(payload && payload.tick) || 1;
            const rows = [];
            let scale = 1;
            /* One drawn column per BAR, not per payload column. The depth payload's columns are
               ~1-second buckets; the bar axis is minutes, so ~60 sub-columns per bar were each drawn
               one bar-width wide and the layer smeared across its neighbours (visible in the
               screenshot that prompted this). Resting depth sums per (bar, price).
               §56 CORRECTION: the snapshot contract is values[PRICE ROW][TIME COLUMN] with a flat
               `prices` ladder — heatmap-pro has always read it that way (vals[ri][ci]). This
               adapter had the axes transposed, so live payloads were laid out along the bottom of
               the ladder: the "heat centred on the wrong price" that §52 blamed on a crop mistake.
               Price rows are the outer axis now, and the wire path (adaptHeatBin) reads the same
               shape. */
            const BK = 1e5;
            const pkey = (p) => Math.round(p / step);
            const barAt = (ms) => {
                const n = barTimes.length;
                if (!n || ms < barTimes[0]) return -1;
                let lo = 0, hi = n - 1;
                while (lo < hi) {
                    const mid = (lo + hi + 1) >> 1;
                    if (barTimes[mid] <= ms) lo = mid; else hi = mid - 1;
                }
                return ms < barTimes[lo] + Math.max(1, barSeconds) ? lo : -1;
            };
            const nc = buckets.length;
            const perColumnPrices = Array.isArray(payload.prices) && Array.isArray(payload.prices[0]);
            const priceRows = perColumnPrices
                ? Math.max(values.length,
                           ...payload.prices.map((p) => (Array.isArray(p) ? p.length : 0)))
                : (Array.isArray(payload.prices) && payload.prices.length ? payload.prices.length : values.length);
            const colBars = new Array(nc);
            for (let ci = 0; ci < nc; ci += 1) {
                const stamp = Number(buckets[ci]) || 0;
                const ms = stamp > 1e12 ? stamp / 1000 : stamp;
                colBars[ci] = stamp ? barAt(ms) : -1;   // a bucket outside the drawn bars is not ours to place
            }
            const mapCol = (ci) => {
                let bi = colBars[ci];
                if (bi < 0 && barTimes.length) bi = Math.max(0, barTimes.length - 1 - (nc - 1 - ci));
                return bi;
            };
            const priceOf = (r, ci) => Number(perColumnPrices ? (payload.prices[ci] || [])[r]
                                                                : (payload.prices || [])[r]);
            const acc = new Map();
            for (let r = 0; r < priceRows; r += 1) {
                const row = values[r];
                if (!Array.isArray(row)) continue;      // ragged rows are skipped, not guessed
                for (let ci = 0; ci < nc; ci += 1) {
                    const barIndex = colBars[ci];
                    if (barIndex < 0) continue;
                    const size = Number(row[ci]) || 0;
                    if (size <= 0) continue;
                    const price = priceOf(r, ci);
                    if (!Number.isFinite(price)) continue;
                    const key = barIndex * BK + pkey(price);
                    const rec = acc.get(key);
                    if (rec) rec.size += size;
                    /* §56: the Map value IS the row object — one allocation per cell, not two. */
                    else acc.set(key, { col: barIndex, price: price, lo: price, hi: price + step, size: size });
                }
            }
            for (const rec of acc.values()) {
                scale = Math.max(scale, rec.size);
                rows.push(rec);
            }
            /* Executed volume rides the same grid as the resting depth: without it the engine could
               only show prints the live tape still holds, and every older column lost its trades. */
            const tradedAcc = new Map();
            const tradedMatrix = Array.isArray(payload.traded) ? payload.traded : [];
            for (let r = 0; r < Math.max(priceRows, tradedMatrix.length); r += 1) {
                const row = tradedMatrix[r];
                if (!Array.isArray(row)) continue;
                for (let ci = 0; ci < nc; ci += 1) {
                    const barIndex = mapCol(ci);
                    if (barIndex < 0) continue;
                    const size = Number(row[ci]) || 0;
                    if (size <= 0) continue;
                    const price = priceOf(r, ci);
                    if (!Number.isFinite(price)) continue;
                    const key = barIndex * BK + pkey(price);
                    const rec = tradedAcc.get(key);
                    if (rec) rec.v += size;
                    else tradedAcc.set(key, { v: size, price: price, col: barIndex });
                }
            }
            /* Executed volume sums per bar too, and carries the side the prints took: the ramp at the
               end of the pass paints it as flow, not as liquidity. */
            const tradedRows = [];
            for (const rec of tradedAcc.values()) {
                tradedRows.push({ col: rec.col, price: rec.price, size: rec.v, side: '' });
            }
            /* Best bid/ask: one point per bar (the last book state the bar saw) — `best` is per
               payload COLUMN (buckets), which the mapCol fallback keeps honest. */
            const bestByBar = new Map();
            (Array.isArray(payload.best) ? payload.best : []).forEach((b, ci) => {
                const barIndex = mapCol(ci);
                if (barIndex < 0 || !b) return;
                bestByBar.set(barIndex, { col: barIndex, bid: Number(b.bid) || 0, ask: Number(b.ask) || 0, trades: Number(b.trades) || 0 });
            });
            const bestCols = [...bestByBar.values()];
            /* Book events: one mark per (bar, price, kind) — a wall that stacks 40 times in a minute
               is one fact about that level, not forty marks in the same pixel. Largest size wins. */
            const eventAcc = new Map();
            /* P2-2: numeric key here too; kinds become dense codes (any kind, not a fixed list). */
            const kindCode = new Map();
            const codeOf = (k) => {
                let c = kindCode.get(k);
                if (c === undefined) { c = kindCode.size; kindCode.set(k, c); }
                return c;
            };
            (Array.isArray(payload.events) ? payload.events : []).forEach((ev) => {
                if (!ev) return;
                const raw = Number(ev.ts_ms) || 0;
                const ms = raw > 1e12 ? raw / 1000 : raw;
                const barIndex = barAt(ms);
                if (barIndex < 0) return;
                const price = Number(ev.price) || 0;
                const kind = ev.kind || '';
                const key = (barIndex * BK + pkey(price)) * 64 + codeOf(kind);
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

        /* §56: the binary sibling of the JSON heat payload. `decodeHeatBin` reads the layout
           `atlas/wire.py` writes (magic OFHB, u32 header length, header JSON, typed sections) and
           `adaptHeatBin` walks the typed arrays into the SAME rows the JSON path produces —
           pinned equal by the selftest. The point is skipping 48 k JSON objects per payload. */
        decodeHeatBin(buffer) {
            const bytes = new Uint8Array(buffer);
            if (bytes.length < 8
                || String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]) !== 'OFHB') return null;
            const dv = new DataView(buffer);
            const hlen = dv.getUint32(4, true);
            let header = null;
            try {
                header = JSON.parse(new TextDecoder().decode(bytes.subarray(8, 8 + hlen)));
            } catch (e) { return null; }
            const cols = Number(header.cols) || 0;
            const rows = Number(header.rows) || 0;
            let off = 8 + hlen;
            /* slice() before viewing: typed views demand alignment, and a copy of a few dozen KB
               is cheaper than trusting the producer's padding. */
            const take = (kind, count) => {
                const size = count * (kind === 8 ? 8 : 4);
                const view = kind === 8
                    ? new Float64Array(buffer.slice(off, off + size))
                    : new Float32Array(buffer.slice(off, off + size));
                off += size;
                return view;
            };
            const buckets = take(8, cols);
            const prices = take(4, header.prices_mode === 'flat' ? rows : cols * rows);
            const values = take(4, cols * rows);
            const traded = header.traded ? take(4, cols * rows) : null;
            const best = new Array(cols);
            for (let c = 0; c < cols; c += 1) {
                best[c] = { bid: dv.getFloat32(off, true), ask: dv.getFloat32(off + 4, true),
                            trades: dv.getInt32(off + 8, true) };
                off += 12;
            }
            return { header, buckets, prices, values, traded, best };
        },
        adaptHeatBin(wire, barTimes, barSeconds) {
            if (!wire || !wire.header) return null;
            const cols = wire.header.cols | 0;
            const rows = wire.header.rows | 0;
            const step = Number(wire.header.step) || Number(wire.header.tick) || 1;
            const flat = wire.header.prices_mode === 'flat';
            const BK = 1e5;
            const pkey = (p) => Math.round(p / step);
            const barAt = (sec) => {
                const n = (barTimes || []).length;
                if (!n || sec < barTimes[0]) return -1;
                let lo = 0, hi = n - 1;
                while (lo < hi) {
                    const mid = (lo + hi + 1) >> 1;
                    if (barTimes[mid] <= sec) lo = mid; else hi = mid - 1;
                }
                return sec < barTimes[lo] + Math.max(1, barSeconds) ? lo : -1;
            };
            const mapCol = (colIdx) => {
                let bi = barAt((wire.buckets[colIdx] || 0) / 1000);
                if (bi < 0 && barTimes.length) bi = Math.max(0, barTimes.length - 1 - (cols - 1 - colIdx));
                return bi;
            };
            const colBars = new Array(cols);
            for (let ci = 0; ci < cols; ci += 1) {
                const ms = (wire.buckets[ci] || 0) / 1000;
                colBars[ci] = barAt(ms);
            }
            const priceOf = (r, ci) => Number(flat ? wire.prices[r] : wire.prices[ci * rows + r]);
            /* the same numeric-key merge the JSON path runs, on the same axes:
               values[price row][time col] — row-major, flat ladder (see adaptHeat's §56 note). */
            const acc = new Map();
            for (let r = 0; r < rows; r += 1) {
                for (let ci = 0; ci < cols; ci += 1) {
                    const barIndex = colBars[ci];
                    if (barIndex < 0) continue;
                    const value = wire.values[r * cols + ci];
                    if (!(value > 0)) continue;
                    const price = priceOf(r, ci);
                    if (!Number.isFinite(price)) continue;
                    const key = barIndex * BK + pkey(price);
                    const rec = acc.get(key);
                    if (rec) rec.size += value;
                    else acc.set(key, { col: barIndex, price: price, lo: price, hi: price + step, size: value });
                }
            }
            const outRows = [];
            let scale = 1;
            for (const rec of acc.values()) {
                scale = Math.max(scale, rec.size);
                outRows.push(rec);
            }
            const tradedRows = [];
            if (wire.traded) {
                const tacc = new Map();
                for (let r = 0; r < rows; r += 1) {
                    for (let ci = 0; ci < cols; ci += 1) {
                        const barIndex = mapCol(ci);
                        if (barIndex < 0) continue;
                        const value = wire.traded[r * cols + ci];
                        if (!(value > 0)) continue;
                        const price = priceOf(r, ci);
                        if (!Number.isFinite(price)) continue;
                        const key = barIndex * BK + pkey(price);
                        const rec = tacc.get(key);
                        if (rec) rec.v += value;
                        else tacc.set(key, { v: value, price: price, col: barIndex });
                    }
                }
                for (const rec of tacc.values()) {
                    tradedRows.push({ col: rec.col, price: rec.price, size: rec.v, side: '' });
                }
            }
            const bestByBar = new Map();
            for (let ci = 0; ci < cols; ci += 1) {
                const barIndex = mapCol(ci);
                if (barIndex < 0) continue;
                const b = wire.best[ci] || {};
                bestByBar.set(barIndex, { col: barIndex, bid: Number(b.bid) || 0,
                                          ask: Number(b.ask) || 0, trades: Number(b.trades) || 0 });
            }
            const eventAcc = new Map();
            const kindCode = new Map();
            const codeOf = (k) => {
                let c = kindCode.get(k);
                if (c === undefined) { c = kindCode.size; kindCode.set(k, c); }
                return c;
            };
            (Array.isArray(wire.header.events) ? wire.header.events : []).forEach((ev) => {
                if (!ev) return;
                const raw = Number(ev.ts_ms) || 0;
                const sec = raw > 1e12 ? raw / 1000 : raw;
                const barIndex = barAt(sec);
                if (barIndex < 0) return;
                const price = Number(ev.price) || 0;
                const kind = ev.kind || '';
                const key = (barIndex * BK + pkey(price)) * 64 + codeOf(kind);
                const prev = eventAcc.get(key);
                const size = Number(ev.size) || 0;
                if (!prev || size > prev.size) {
                    eventAcc.set(key, { col: barIndex, kind, direction: ev.direction || '',
                                        price, size, detail: ev.detail || '' });
                }
            });
            const flowEvents = [...eventAcc.values()];
            if (!outRows.length && !tradedRows.length) return null;
            return { rows: outRows, scale, traded: tradedRows, best: [...bestByBar.values()],
                     events: flowEvents, version: wire.header.version };
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

        /* T10/B13: the candle-degrade verdict — engage once a column drops below the text
           threshold, release only after it widens past the threshold plus half the fade ramp
           (hysteresis, so a wheel-rocking zoom does not flicker). Pure. */
        degradeDecision(columnWidth, textPx = 45, fadePx = 15, engaged = false) {
            const w = Number(columnWidth) || 0;
            const t = Number(textPx) || 0;
            const hi = t + Math.max(1, Number(fadePx) || 0) * 0.5;
            return engaged ? w < hi : w < t;
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
        heatPalette(scale, ramp, buckets = 64, alphaSteps = 16, gamma = 1, dim = 0) {
            const sc = Number(scale) > 0 ? Number(scale) : 1;
            const logMax = Math.log1p(Math.max(sc, 1));
            const dimmer = Math.min(0.8, Math.max(0, Number(dim) || 0));
            const out = [];
            for (let b = 0; b < buckets; b += 1) {
                /* B2: the contrast dial rides the colour table itself — the size-to-bucket mapping
                   stays linear in luminance; only where each bucket sits on the ramp moves. */
                const rgb = math.heatColor01(math.rampT(b / (buckets - 1), gamma), ramp);
                for (let a = 0; a < alphaSteps; a += 1) {
                    /* B5: dimming is the same trick on the alpha axis — every cell fades, so the
                       levels and drawings over the map carry the eye. */
                    const alpha = ((a + 1) / alphaSteps) * (1 - dimmer);
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
            unfinished: '255,193,117',  // unfinished-business magnet (fold-in §3 level reads)
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
        /* ── P1-9: the zoom maths, one home for the wheel and the keys ─────────
           `zoomScale` is a scale step with its hard limit; `anchorOffset` solves the pin
           equation (price = offY + (height - anchorY) / scale) for offY, so the point under
           the anchor keeps its price/time as the scale changes. Pure — pinned in
           ofx.selftest.js. */
        zoomScale(value, factor, min, max) {
            return Math.max(min, Math.min(max, value * factor));
        },
        anchorOffset(price, height, anchorPx, scale) {
            return price - (height - anchorPx) / scale;
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
        /* T5/A11 — the anti-fit verdict, the study's hysteresis shape: hold while the data
           band sits inside the visible range with slack at both edges and the view is not far
           emptier than the band; refit only when it reaches an edge or shrinks away. factor 0
           keeps the old always-refit behaviour. Pure — pinned in ofx.selftest.js. */
        fitDecision(view, band, factor) {
            const f = Math.max(0, Math.min(0.9, Number(factor) || 0));
            if (!(f > 0)) return 'refit';
            const vSpan = Number(view.hi) - Number(view.lo);
            const bSpan = Number(band.hi) - Number(band.lo);
            if (!(vSpan > 0) || !(bSpan > 0)) return 'refit';
            const slack = vSpan * f;
            if (Number(band.lo) < Number(view.lo) + slack) return 'refit';
            if (Number(band.hi) > Number(view.hi) - slack) return 'refit';
            /* Deliberately not tied to factor: a view three times emptier than the band is
               wasteful whatever the slack is — the data shrank, tighten onto it. */
            if (bSpan * 3 < vSpan) return 'refit';
            return 'hold';
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

        /* A [i0, i1] bar range from two cursor positions: clipped to the drawn bars AND ordered.
           Both halves matter - a drag past the last bar used to clamp only its END index, so the
           start stayed out of range and the pair came back inverted (i0 = 11, i1 = 4). */
        selectionRange(a, b, n) {
            const last = Math.max(0, (Number(n) || 0) - 1);
            const clip = (v) => Math.max(0, Math.min(last, Math.floor(Number(v) || 0)));
            const x = clip(a), y = clip(b);
            return [Math.min(x, y), Math.max(x, y)];
        },

        /* P1-5: the alpha a live cell leaves behind as a ghost. It tracks the cell's own density
           bucket - the same log1p mapping the colour table uses - so a pulled wall leaves a strong
           ghost and a thin level leaves a faint one. A uniform 0.92 said every level held the same
           liquidity, which is exactly the claim the picture must not make. */
        peakAlpha(size, scale, floor, top, gamma = 1) {
            const sc = Number(scale) > 0 ? Number(scale) : 1;
            const v = Math.max(0, Number(size) || 0);
            const span = Math.max(1e-9, Math.log1p(Math.max(sc, 1)));
            const t = math.rampT(Math.min(1, Math.log1p(v) / span), gamma);
            const lo = Number(floor) > 0 ? Number(floor) : 0.32;
            const hi = Number(top) > 0 ? Number(top) : 0.92;
            return Math.min(hi, lo + (hi - lo) * Math.sqrt(Math.max(0, t)));
        },

        /* ── P1-3: the selection's arithmetic, pure ──────────────────────────────────────────────
           Everything here reads arrays the engine already holds. `levels` is a Map of bar time ->
           [{price, bid, ask}]; `prints` may carry second or millisecond stamps. A print outside the
           drawn bars is not counted at all - the same rule the sweep layer uses - and the resting
           change is null rather than zero when there is no depth history for the window. */
        selectionStats({ bars, levels, prints, i0, i1, p0, p1, barSec, maxPrints }) {
            const list = (bars || []).slice(Math.max(0, i0 | 0), (i1 | 0) + 1);
            const lo = Math.min(p0, p1), hi = Math.max(p0, p1);
            if (!list.length) return null;
            const sec = Number(barSec) > 0 ? Number(barSec)
                : (list.length > 1 ? Math.max(1, list[list.length - 1].time - list[list.length - 2].time) : 60);
            let volume = 0, delta = 0, buy = 0, sell = 0;
            for (const b of list) {
                volume += Number(b.volume) || 0;
                delta += Number(b.delta) || 0;
                if (b.calc) { buy += Number(b.calc.buy) || 0; sell += Number(b.calc.sell) || 0; }
            }
            const t0 = list[0].time;
            const t1 = list[list.length - 1].time;
            const cap = Number(maxPrints) > 0 ? Number(maxPrints) : 5000;
            let count = 0, total = 0, largest = 0, largestAt = null, num = 0, den = 0;
            const rows = [];
            for (const print of prints || []) {
                const raw = Number(print.time) || 0;
                const ts = raw > 1e11 ? raw / 1000 : raw;
                if (ts < t0 || ts >= t1 + sec) continue;
                const price = Number(print.price);
                const size = Number(print.size);
                if (!Number.isFinite(price) || price < lo || price > hi) continue;
                if (!Number.isFinite(size) || size <= 0) continue;
                count += 1;
                total += size;
                num += price * size;
                den += size;
                if (size > largest) { largest = size; largestAt = price; }
                if (rows.length < cap) rows.push({ time: ts, price: price, size: size, side: print.side || '' });
            }
            const restingAt = (bar) => {
                if (!bar || !levels || typeof levels.get !== 'function') return null;
                const levelRows = levels.get(bar.time) || [];
                if (!levelRows.length) return null;
                let sum = 0;
                for (const r of levelRows) {
                    const price = Number(r.price) || 0;
                    if (price < lo || price > hi) continue;
                    sum += (Number(r.bid) || 0) + (Number(r.ask) || 0);
                }
                return sum;
            };
            const resting0 = restingAt(list[0]);
            const resting1 = restingAt(list[list.length - 1]);
            return {
                bars: list.length, i0: Math.max(0, i0 | 0), i1: Math.max(0, i0 | 0) + list.length - 1,
                t0: t0, t1: t1, barSec: sec, p0: lo, p1: hi,
                volume: volume, delta: delta, buy: buy, sell: sell,
                prints: count, printSize: total,
                largest: largestAt == null ? null : { size: largest, price: largestAt },
                vwap: den ? num / den : null,
                resting0: resting0, resting1: resting1,
                restingChange: (resting0 == null || resting1 == null) ? null : resting1 - resting0,
                barRows: list.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close,
                    volume: b.volume, delta: b.delta })),
                printRows: rows,
            };
        },

        /* ── Phase 3 / A3: the area's volume profile, pure ──────────────────────────────────────
           Volume-at-price over the boxed region: every drawn row inside [i0..i1] x [p0..p1] carries
           its bid+ask into the area's total. POC = the heaviest row; the value area is the heaviest
           rows until `pct` of the area's volume is covered — the same rule the footprint's per-bar
           band uses (`math.rowShares`), applied to the area instead of one candle. `step` is the
           smallest positive gap between drawn rows (the watch hand-off tolerances from it). An
           area with no depth rows returns null: no ladder means no profile, never an invented one. */
        areaVolumeProfile({ bars, levels, i0, i1, p0, p1, pct }) {
            const list = (bars || []).slice(Math.max(0, i0 | 0), (i1 | 0) + 1);
            const lo = Math.min(Number(p0), Number(p1)), hi = Math.max(Number(p0), Number(p1));
            if (!list.length || levels == null || typeof levels.get !== 'function') return null;
            const byPrice = new Map();
            for (const b of list) {
                const rows = levels.get(b.time) || [];
                for (const r of rows) {
                    const price = Number(r.price);
                    if (!Number.isFinite(price) || price < lo || price > hi) continue;
                    const vol = (Number(r.bid) || 0) + (Number(r.ask) || 0);
                    if (vol <= 0) continue;
                    byPrice.set(price, (byPrice.get(price) || 0) + vol);
                }
            }
            if (!byPrice.size) return null;
            const rows = Array.from(byPrice, ([price, volume]) => ({ price: price, volume: volume }))
                .sort((a, b) => a.price - b.price);
            let total = 0;
            for (const r of rows) total += r.volume;
            const share = Math.max(0.1, Math.min(0.95, Number(pct) > 0 ? Number(pct) : 0.7));
            const ranked = rows.slice().sort((a, b) => b.volume - a.volume);
            const target = total * share;
            let acc = 0;
            const inVA = new Set();
            for (const r of ranked) {
                if (acc >= target && inVA.size) break;
                inVA.add(r.price);
                acc += r.volume;
            }
            const vaPrices = rows.filter((r) => inVA.has(r.price)).map((r) => r.price);
            let step = 0;
            for (let i = 1; i < rows.length; i++) {
                const d = rows[i].price - rows[i - 1].price;
                if (d > 1e-12 && (!step || d < step)) step = d;
            }
            const poc = ranked[0];
            return {
                rows: rows.map((r) => ({ price: r.price, volume: r.volume, inVA: inVA.has(r.price) })),
                total: total, poc: poc.price, pocVolume: poc.volume,
                pocShare: total > 0 ? poc.volume / total : 0,
                vah: vaPrices.length ? Math.max.apply(null, vaPrices) : null,
                val: vaPrices.length ? Math.min.apply(null, vaPrices) : null,
                vaPct: share, step: step,
                from: rows[0].price, to: rows[rows.length - 1].price,
            };
        },
    };

    /* ── state ───────────────────────────────────────────────────────────── */

    /* P2-3: how much of the 16.7 ms frame budget one frame may spend before the remaining
       layers are deferred to the next rAF. 6 ms leaves room for the browser's own work in the
       same frame; the measured 4K costs (heat ~7.5, base ~6.5) split cleanly under it. */
    const YIELD_MS = 6;

    /* T10/B16: the value-scale rail's width — drawAxes paints it, and the right-click zone
       and the axis drag both measure it. One constant, three consumers. */
    const RAIL_W = 62;

    /* The time ruler's height — the framing band and the ruler share one number (audit C-16). */
    const RULER_H = 14;
    const state = {
        symbol: 'BTCUSDT',
        params: { R: 4.0, stack: 3, lambda: 500, textPx: 45, sweepC: 1.15, levelCap: 260,
            vaPct: 0.7, minBlock: 0, minRowPx: 9, ramp: 'classic',
            /* B2: the heat scheme's live dials — contrast (a gamma over the ramp; 1 = as shipped),
               a floor in size units and a floor as a share of the book's sizes (both off). */
            heatContrast: 1.0, heatFloor: 0, heatFloorPct: 0,
            heatDim: 0, heatHighlight: 0,
            /* T10/B3: the vertical-smoothing mode; T10/B13: the candle-degrade switch. */
            heatSmooth: 'auto', degrade: true,
            /* P1-8: how a bar is expressed. Resolved by `expression.js` at paint time; junk falls
               back to `default`/`theme` there, so this pair can never blank the stage. */
            mode: 'default', palette: 'theme' },
        // coordinate matrix — pixels per unit, plus origin
        /* scaleX=52 keeps the default view above the 45px text threshold: the engine opens on
           footprints, and LOD takes over when the user zooms out. */
        view: { offX: 0, scaleX: 52, offY: 0, scaleY: 0.6, width: 900, height: 480, dpr: 1 },
        data: { bars: [], levels: new Map(), prints: [], heat: [], heatScale: 1, sessions: [],
            /* §3 level reads: served by /api/atlas/levels (unfinished magnets + node runs) */
            reads: { unfinished: [], nodes: [], confluence: [], note: '' },
            heatIndex: null, palette: null, traded: [], best: [], flowEvents: [], key: '' },
        layers: { heat: null, base: null, live: null, ribbon: null, hud: null },
        mode: 'live',
        lod: { mode: 'footprint', text: true, labelAlpha: 1 },
        dirty: { heat: true, base: true, live: true, ribbon: true, hud: true },
        stats: { frames: 0, lastMs: 0, emaMs: 0, p95Ms: 0, heatPasses: 0, heatPatches: 0, heatSkips: 0, yields: 0, decayCells: 0, framesMs: [], misses: 0,
            recovered: 0, flowBubbles: 0, flowEvents: 0,
            printsSeen: 0, printsMatched: 0, sweepBubbles: 0, heatCells: 0, textStarved: 0,
            cellPx: 0, aggregating: false, groupK: 1, divState: 'none', blocksFiltered: 0,
            barBodies: 0, barSplits: 0, degraded: false, heatSmooth: false },
        hover: null,
        /* P2-1: per-payload indexes (prints by bar, CVD prefix sums, flow events by column).
           Built once in `setData()`; hover reads them instead of rescanning the payload. */
        idx: null,
        /* P2-2: the heat layer's change gate. `heatEpoch` moves when the matrix, the view or the
           parameters change; the 33 ms tick only asks for a pass when the painted epoch lags it,
           or while ghosts are still fading. `heatGhosts` holds the visible fading cells and their
           screen rects, so a decay pass costs what is fading — not what is on screen. */
        heatEpoch: 0, heatPainted: -1, heatGhosts: [],
        pendingHover: null,
        autoFit: true,
        degradeOn: false,          // T10/B13 hysteresis (recomputed every footprint paint)
        smoothHeatOn: false,       // T10/B3 hysteresis (recomputed every heat paint)
        avgLevelVolume: 0,
        avgBarVolume: 0,
        lastPaint: 0,
    };

    /* ── the expression palette ────────────────────────────────────────────────────────────────
       `math.theme` is the one colour table: the renderers paint from it and `legend()` quotes it, so a
       palette is applied INTO it rather than kept beside it (a parallel table is how a legend ends up
       describing a colour the picture does not use). BASE_THEME is frozen at load, so switching back
       to the theme palette restores every key exactly — proven in `ofx.selftest.js`. */
    const BASE_THEME = Object.freeze(Object.assign({}, math.theme));

    function applyPalette(key) {
        const expr = root.OFAPEXPR;
        Object.assign(math.theme, BASE_THEME);
        if (!expr || typeof expr.themeOverrides !== 'function') return 0;
        const over = expr.themeOverrides(key) || {};
        Object.assign(math.theme, over);
        return Object.keys(over).length;
    }

    /* What to draw for one bar, and the words that describe it. The catalogue decides; with no
       catalogue loaded the engine draws exactly what it always drew (CHROME_DEFAULT, no body). */
    function barPaintFor(bar, modeOverride) {
        const expr = root.OFAPEXPR;
        if (!expr || typeof expr.barPaint !== 'function') {
            return {
                mode: 'default', palette: 'theme', chrome: CHROME_DEFAULT, body: null, split: null,
                glyph: '', encoding: '', pairing: '',
                wick: { rgba: math.rgba('wick', '.35'), lineWidth: 1 },
            };
        }
        return expr.barPaint(bar, {
            mode: modeOverride || state.params.mode, palette: state.params.palette,
            theme: { pos: math.theme.bid, neg: math.theme.ask },
        });
    }

    /* ── the bar's own body (P1-8) ─────────────────────────────────────────────────────────────
       Fill under the cells so the digits keep their contrast, outline over them so the bar's boundary
       is never lost, and the split candle's two halves in between. The decision is `expression.js`'s;
       this only puts pixels where it says. */
    function bodyBox(bar, x, colW) {
        const yOpen = priceToY(bar.open);
        const yClose = priceToY(bar.close);
        return { y0: Math.min(yOpen, yClose), h: Math.max(1.5, Math.abs(yClose - yOpen)), w: Math.max(1, colW - 2), x: x + 1 };
    }

    function paintBodyFill(ctx, paint, bar, x, colW) {
        if (!paint.body) return false;
        const box = bodyBox(bar, x, colW);
        ctx.fillStyle = paint.body.fill;
        ctx.fillRect(box.x, box.y0, box.w, box.h);
        return true;
    }

    function paintBodyStroke(ctx, paint, bar, x, colW) {
        if (!paint.body) return false;
        const box = bodyBox(bar, x, colW);
        ctx.strokeStyle = paint.body.stroke;
        ctx.lineWidth = paint.body.lineWidth || 1.5;
        ctx.strokeRect(x + 0.5, box.y0 + 0.5, Math.max(1, colW - 1), box.h);
        /* The direction glyph rides the body itself, so the sign survives even where the column is
           too narrow for the delta badge — colour is never the only carrier (canon #5). */
        if (paint.glyph && colW >= 18 && box.h >= 12) {
            ctx.save();
            ctx.font = '600 11px ui-monospace, monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = paint.body.stroke;
            ctx.fillText(paint.glyph, x + colW / 2, box.y0 + box.h / 2);
            ctx.restore();
        }
        return true;
    }

    /* The split candle: two sub-bars inside the bar's own high→low range — left = sell volume, right
       = buy volume (the same left/right the cells use), each as tall as its share of the bar's
       traded volume, both growing from the range's low edge. */
    function paintSplit(ctx, paint, bar, x, colW) {
        if (!paint.split) return false;
        const topY = Math.min(priceToY(bar.high), priceToY(bar.low));
        const botY = Math.max(priceToY(bar.high), priceToY(bar.low));
        const h = Math.max(4, botY - topY);
        const half = Math.max(1, Math.floor((colW - 2) / 2));
        const right = Math.max(1, colW - 2 - half);
        const hSell = Math.max(1.5, h * paint.split.left.frac);
        const hBuy = Math.max(1.5, h * paint.split.right.frac);
        ctx.fillStyle = paint.split.left.rgba;
        ctx.fillRect(x + 1, botY - hSell, half, hSell);
        ctx.fillStyle = paint.split.right.rgba;
        ctx.fillRect(x + 1 + half, botY - hBuy, right, hBuy);
        ctx.strokeStyle = paint.wick.rgba;
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 1.5, botY - hSell + 0.5, half - 1, Math.max(1, hSell - 1));
        ctx.strokeRect(x + 1 + half + 0.5, botY - hBuy + 0.5, Math.max(1, right - 1), Math.max(1, hBuy - 1));
        return true;
    }

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

    /* ── P2-1: the hover index ─────────────────────────────────────────────
       `hover()` used to rescan the whole print list, the whole depth matrix and the bar deltas
       from bar 0 on EVERY pointer move (O(prints + heat cells + bars) per call — ~40 k iterations
       on a 10 k-print tape with a 30 k-cell matrix). These builders do the same work once per
       payload instead, and the measured numbers are pinned equal to the old loops by
       ofx.selftest.js. */
    /* P2-2: one gate for every change that makes the current heat pixels wrong. */
    function markHeatFull() {
        state.heatEpoch += 1;
        state.dirty.heat = true;
    }

    function buildPrintIndex() {
        const bars = state.data.bars;
        const prints = state.data.prints;
        const idx = state.idx || (state.idx = {});
        const rows = new Array(bars.length);
        for (let i = 0; i < bars.length; i += 1) rows[i] = { prints: 0, sweep: 0 };
        if (bars.length) {
            const sec = barSeconds();
            for (const p of prints || []) {
                /* Stamps are normalised with the same rule `math.selectionStats` uses: a stamp
                   above 1e11 is milliseconds. The live tape already arrives in seconds; a ms
                   source used to silently read as zero prints in every bar. */
                const raw = Number(p.time) || 0;
                const ts = raw > 1e11 ? raw / 1000 : raw;
                if (ts < bars[0].time) continue;
                /* Last bar whose window has opened by ts (bars are in time order — the payload
                   contract); then the same half-open window test hover used: [t, t + sec). */
                let lo = 0, hi = bars.length - 1;
                while (lo < hi) {
                    const mid = (lo + hi + 1) >> 1;
                    if (bars[mid].time <= ts) lo = mid; else hi = mid - 1;
                }
                if (ts < bars[lo].time + sec) {
                    rows[lo].prints += 1;
                    rows[lo].sweep += Number(p.size) || 0;
                }
            }
        }
        idx.printsByBar = rows;
    }

    function buildCvdPrefix() {
        const bars = state.data.bars;
        const idx = state.idx || (state.idx = {});
        /* float64, summed in bar order — the same arithmetic order as the loop it replaces,
           so the bits match, not just the values. */
        const cvd = new Float64Array(bars.length + 1);
        for (let i = 0; i < bars.length; i += 1) cvd[i + 1] = cvd[i] + (Number(bars[i].delta) || 0);
        idx.cvd = cvd;
    }

    function buildFlowIndex() {
        const idx = state.idx || (state.idx = {});
        const byCol = new Map();
        for (const e of state.data.flowEvents || []) {
            const c = Number(e.col);
            if (!Number.isFinite(c)) continue;
            let g = byCol.get(c);
            if (!g) { g = []; byCol.set(c, g); }
            g.push(e);
        }
        idx.flowByCol = byCol;
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
            /* P2-2: the server versions the matrix; an unchanged version (the cached-snapshot
               case) is not repainted again. A payload without a version always rebuilds. */
            const nextVersion = heat.version == null ? null : String(heat.version);
            if (nextVersion === null || nextVersion !== state.data.heatVersion) {
                state.data.heatVersion = nextVersion;
                markHeatFull();
            }
        }
        /* A crosshair or tooltip measured against the previous dataset must not label the new one
           (audit C-07): the hover state is dropped whenever a payload replaces the data. */
        state.hover = null;
        state.pendingHover = null;
        /* P2-1: one index pass per payload. Bar boundaries define the print buckets, so a bars
           change rebuilds them too; the CVD prefix follows the bars; the flow index follows heat. */
        if (bars || prints) buildPrintIndex();
        if (bars) buildCvdPrefix();
        if (heat) buildFlowIndex();
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
                    ? `ramp ${rampKey} · scale ${fmt(s.heatScale, 2)} · contrast ${fmt(p.heatContrast, 2)}`
                        + (Number(p.heatFloor) > 0 ? ` · floor ${math.fmtSize(p.heatFloor)}` : '')
                        + (Number(p.heatFloorPct) > 0 ? ` · floor ${fmt(p.heatFloorPct, 0)}%` : '')
                        + ` · ${s.heatCells} cells drawn`
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
                name: 'Unfinished business (UFB)',
                swatch: { type: 'solid', rgb: t.unfinished },
                meaning: 'An auction extreme that never finished — a bar high with sellers still on '
                    + 'the bid, or a low with buyers on the ask. Dashed to the live edge until price '
                    + 'returns to the level and the server resolves it.',
                live: `${s.levelReadLines || 0} open magnets · labels show × re-arms`,
            },
            {
                name: 'Node band (×2 / ×3)',
                swatch: { type: 'solid', rgb: t.hvn },
                meaning: 'Consecutive bars whose heaviest-volume price sits at one level — a double '
                    + 'or triple node. The band spans the bars that agreed; the label counts them.',
                live: `${s.levelReadBands || 0} bands drawn`,
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
                name: 'Bar expression',
                swatch: exprMode().key === 'default' || exprMode().key === 'wick'
                    ? { type: 'line', rgb: t.wick }
                    : { type: 'split', rgb: t.bid, rgb2: t.ask },
                meaning: exprMode().says + ' \· sign: ' + exprMode().pairing,
                live: `mode ${exprMode().key} \· palette ${exprMode().paletteLabel || exprMode().palette}`
                    + ` \· ${s.barBodies || 0} bodies, ${s.barSplits || 0} splits drawn in the last pass`
                    + (exprMode().key === 'split' && state.data.bars.length
                        ? ' \· ' + (root.OFAPEXPR
                            ? root.OFAPEXPR.splitVolumes(state.data.bars[state.data.bars.length - 1]).source
                            : 'side volumes where the feed carries them')
                        : ''),
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
            { keys: 'shift + drag', action: 'select a time × price region — the strip beside the stage measures it' },
            { keys: 'double-click', action: 'fit the whole session' },
            { keys: 'fit button', action: 'same as double-click' },
            { keys: '● live (chip)', action: 'snap to the newest bar and follow' },
            { keys: 'P', action: 'hold updates while you work (feed keeps ingesting)' },
            { keys: 'hover', action: 'cursor tag on the canvas + full metric panel beside the stage' },
            { keys: 'click a print (tape)', action: 'locate it — the cursor takes that price and time, the viewport seeks to its bar' },
            { keys: '= / -', action: 'keyboard: zoom time in / out, around the stage centre' },
            { keys: '[ / ]', action: 'keyboard: zoom price out / in, around the stage centre' },
            { keys: 'X', action: 'clear the selection (the full map: ?)' },
            { keys: 'Ctrl+E', action: 'export the selection as CSV' },
        ];
        const layout = [
            'depth heat — behind the matrix, one column per bar',
            'footprint matrix — one column per bar: bid left half, ask right half, POC boxed, VA shaded, STACK bands',
            `bar expression (${exprMode().key}): ${exprMode().says}`,
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
                expression: { mode: exprMode().key, palette: exprMode().palette, ramp: rampKey },
            },
            stats: {
                heatScale: Number(s.heatScale) || 0, heatCells: s.heatCells, sweepBubbles: s.sweepBubbles,
                flowEvents: s.flowEvents, divState: s.divState, recovered: s.recovered || 0,
                avgLevelVolume: s.avgLevelVolume, groupK: s.groupK, cellPx: s.cellPx, lod: state.lod.mode,
                degraded: state.degradeOn === true, heatSmooth: !!s.heatSmooth,
            },
        };
    }

    /* Aggregated view when LOD suppresses text: one bar per interval, split by direction. */
    /* The active mode/palette as the catalogue resolves them (junk -> default/theme). */
    function exprMode() {
        const expr = root.OFAPEXPR;
        if (!expr) return { key: 'default', palette: 'theme', says: '', pairing: '' };
        const m = expr.mode(state.params.mode);
        const p = expr.palette(state.params.palette);
        return {
            key: expr.MODE_KEYS.indexOf(String(state.params.mode)) >= 0 ? String(state.params.mode) : 'default',
            palette: expr.PALETTE_KEYS.indexOf(String(state.params.palette)) >= 0 ? String(state.params.palette) : 'theme',
            says: m.says, pairing: m.pairing, label: m.label, paletteLabel: p.label,
        };
    }

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
        const railW = RAIL_W;
        const rulerH = RULER_H;
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

    function fitHeight(force) {
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
        /* T5/A11: auto-fit hysteresis — while the band sits comfortably inside the visible
           range, the scale stays still (a scale that breathes every tick is the flicker the
           study's Bookmap brief names). atlas.ofx.fit_tolerance, 0 = always refit. */
        const tol = fitTolerance();
        if (!force && tol > 0 && state.view.scaleY > 0 && state.view.height > 0) {
            const verdict = math.fitDecision(
                { lo: state.view.offY, hi: state.view.offY + state.view.height / state.view.scaleY },
                { lo: lo - pad, hi: hi + pad }, tol);
            if (verdict === 'hold') return;
        }
        state.view.offY = lo - pad;
        state.view.scaleY = state.view.height / ((hi + pad) - state.view.offY);
    }

    /* How much slack auto-fit keeps before it refits (atlas.ofx.fit_tolerance; default 0.25). */
    function fitTolerance() {
        try {
            /* `S` is ui.js's top-level binding, not a window property — window.S is always
               undefined here and a guard on it would silently pin the default. */
            if (typeof S === 'undefined' || !S || !S.config) return 0.25;
            const cfg = (S.config.atlas && S.config.atlas.ofx) || {};
            const v = Number(cfg.fit_tolerance);
            return Number.isFinite(v) ? Math.max(0, Math.min(0.9, v)) : 0.25;
        } catch (e) { return 0.25; }
    }

    /* B2: the live contrast dial, clamped at the same bounds the config store and the registry
       hold it to. */
    function heatGamma() {
        const g = Number(state.params.heatContrast);
        return Number.isFinite(g) ? Math.min(2.5, Math.max(0.5, g)) : 1;
    }

    /* B5: the live dimming dial (0 = off, up to 0.8), clamped at the registry's own bounds. */
    function heatDim() {
        const d = Number(state.params.heatDim);
        return Number.isFinite(d) ? Math.min(0.8, Math.max(0, d)) : 0;
    }

    /* B5: the large-size highlight — a share of the resolved ceiling at which a LIVE cell is
       outlined, so the map's own walls read as walls. 0 = off (the shipped look). */
    function heatHighlight() {
        const h = Number(state.params.heatHighlight);
        return Number.isFinite(h) ? Math.min(1, Math.max(0, h)) : 0;
    }

    /* B2: the size floor resolved once per (version, dials) — the exact size or the bottom share,
       whichever is higher. Below it a cell draws nothing, so the map shows where size is NOT. */
    function heatFloorFor() {
        const f = Math.max(0, Number(state.params.heatFloor) || 0);
        const fp = Math.min(50, Math.max(0, Number(state.params.heatFloorPct) || 0));
        if (f <= 0 && fp <= 0) return 0;
        const key = `${state.data.heatVersion}|${f}|${fp}`;
        if (state.data.heatFloorKey !== key) {
            const sizes = [];
            for (const cell of state.data.heat || []) {
                const s = Number(cell.size) || 0;
                if (s > 0) sizes.push(s);
            }
            sizes.sort((a, b) => a - b);
            const mod = root.OFAPRAMP;
            state.data.heatFloorKey = key;
            state.data.heatFloorVal = mod ? mod.floorValue(sizes, f, fp) : f;
        }
        return state.data.heatFloorVal || 0;
    }

    /* One rgba table per (scale, ramp, contrast): rebuilt only when one of them actually changes. */
    function heatPaletteFor() {
        const key = `${state.data.heatScale}|${state.params.ramp}|${heatGamma()}|${heatDim()}`;
        if (!state.data.palette || state.data.palette.key !== key) {
            state.data.palette = { key, pal: math.heatPalette(state.data.heatScale, state.params.ramp, 64, 32, heatGamma(), heatDim()) };
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
        const floorVal = heatFloorFor();
        /* B5: the highlight threshold in the map's own size units — a share of the ceiling. */
        const hlShare = heatHighlight();
        const hlNow = hlShare > 0 ? hlShare * (Number(state.data.heatScale) || 1) : 0;
        /* P2-2: what is still fading is remembered WITH its rect, so the decay pass repaints
           exactly these cells and nothing else. */
        const ghosts = [];
        /* Column range first (binary search over the ordered column keys), then the rows inside
           those columns only. Same picture as the per-cell bounds test, without the 30k
           iterations a pass: cells outside the viewport are never touched. */
        const cols = idx.cols;
        /* T10/B3: the vertical-smoothing verdict for this frame — judged on the heat cells'
           own pixel height ('auto' engages below ~2.5 px; hysteresis holds across the band). */
        const RPHEAT = root.OFAPRAMP;
        const smoothMode = state.params.heatSmooth || 'auto';
        let probeH = 0;
        for (let pi = 0; pi < cols.length && !probeH; pi += 1) {
            for (const pcell of (idx.groups.get(cols[pi]) || [])) {
                if (pcell.size > 0) { probeH = Math.abs(priceToY(pcell.hi) - priceToY(pcell.lo)); break; }
            }
        }
        if (smoothMode === 'auto' && RPHEAT) state.smoothHeatOn = RPHEAT.smoothDecision(probeH, state.smoothHeatOn);
        const smoothNow = smoothMode === 'manual' || (smoothMode === 'auto' && state.smoothHeatOn);
        state.stats.heatSmooth = smoothNow;
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
            /* T10/B3: blend the column's sizes across neighbouring price cells; a ghost keeps
               its own lastSize — its colour is a memory of what was, not a live reading. */
            const smoothedSizes = (smoothNow && RPHEAT)
                ? RPHEAT.smoothVector(cells.map((c2) => c2.size || 0), RPHEAT.SMOOTH_STRENGTH) : null;
            for (let k = 0; k < cells.length; k += 1) {
                const cell = cells[k];
                const y0 = priceToY(cell.hi);
                const y1 = priceToY(cell.lo);
                if (y1 < 0 || y0 > v.height) continue;
                let alpha;
                if (cell.size > 0) {
                    /* B2: below the floor nothing is drawn — and nothing is remembered, so no
                       ghost can fire later for a cell that never had colour. */
                    if (floorVal > 0 && cell.size < floorVal) {
                        cell.alpha = 0;
                        cell.peak = 0;
                        cell.seen = now;
                        cell.lastSize = 0;
                        continue;
                    }
                    /* live cell: density colour at full strength, stamped for the decay pass */
                    alpha = 0.92;
                    cell.alpha = alpha;
                    cell.seen = now;
                    /* The ghost this cell will leave is proportional to what it was (P1-5). */
                    cell.peak = Math.max(cell.peak || 0,
                        math.peakAlpha(cell.size, state.data.heatScale, 0, 0, heatGamma()));
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
                const yTop = Math.min(y0, y1);
                const hh = Math.max(1, Math.abs(y1 - y0));
                const smoothSize = (smoothedSizes && cell.size > 0) ? smoothedSizes[k] : (cell.lastSize || 1);
                ctx.fillStyle = strings[pal.index(Math.max(0, smoothSize), alpha)] || strings[0];
                ctx.fillRect(x, yTop, colW, hh);
                /* B5: the large-size highlight. Only a LIVE cell at/above the threshold is
                   outlined — a fading ghost is a memory of size, not a wall standing now. */
                if (hlNow > 0 && cell.size > 0 && cell.size >= hlNow) {
                    ctx.strokeStyle = 'rgba(232,238,248,0.55)';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x + 0.5, yTop + 0.5, Math.max(1, colW) - 1, Math.max(1, hh) - 1);
                }
                if (cell.size <= 0) ghosts.push({ cell: cell, x: x, yTop: yTop, h: hh });
            }
        }
        state.heatGhosts = ghosts;
        state.stats.decayCells = decayed;
        return decayed;
    }

    /* P2-2: the incremental decay pass — only ghosts whose quantised alpha actually moved are
       repainted, each inside its own rect on the existing canvas. Cost is proportional to what is
       fading, not to what is on screen; a pass where nothing moved paints nothing. */
    function patchHeat(ctx) {
        const list = state.heatGhosts;
        if (!list.length) return false;
        const now = Date.now();
        const pal = heatPaletteFor();
        const strings = pal.strings;
        const colW = Math.max(1, state.view.scaleX);
        let painted = 0;
        const alive = [];
        for (const gh of list) {
            const cell = gh.cell;
            if (cell.size > 0) continue;                  // live again: the full pass owns it
            const alpha = math.decayAlpha(cell.peak || cell.alpha, now - (cell.seen || now), state.params.lambda);
            if (alpha <= 0.004) {
                ctx.clearRect(gh.x, gh.yTop, colW, gh.h); // gone: leave nothing behind
                state.stats.decayCells += 1;
                continue;
            }
            if (Math.abs(alpha - cell.alpha) >= 0.008) {  // quantised: invisible moves paint nothing
                cell.alpha = alpha;
                ctx.clearRect(gh.x, gh.yTop, colW, gh.h);
                ctx.fillStyle = strings[pal.index(cell.lastSize || 1, alpha)] || strings[0];
                ctx.fillRect(gh.x, gh.yTop, colW, gh.h);
                painted += 1;
                state.stats.decayCells += 1;
            }
            alive.push(gh);
        }
        state.heatGhosts = alive;
        return painted > 0;
    }

    /* A tinted cell with a low glow, for the imbalanced rows only: the matrix stays quiet
       everywhere else, and the POC keeps its stronger glow (accent scarcity, §3.3). */
    function glowCell(ctx, x, y, w, h, key) {
        ctx.save();
        ctx.shadowColor = math.rgba(key, '.55');
        ctx.shadowBlur = Math.max(3, math.glowRadius(w, h) * 0.35);
        ctx.fillStyle = math.rgba(key, '.18');
        ctx.fillRect(x, y, w, h);
        ctx.restore();
    }

    function drawFootprint(ctx) {
        const bars = state.data.bars;
        if (!bars.length) return;
        const v = state.view;
        const lod = state.lod;
        const start = Math.max(0, Math.floor(v.offX) - 1);
        /* C-03: the plot stops at the price rail. snapToLive parks the newest bar's right edge at
           the stage edge, so the last columns were painted over the rail's price labels. */
        const plotRight = v.width - RAIL_W;
        const end = Math.min(bars.length, Math.ceil(xToIndex(plotRight)) + 2);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        /* One label per distinct projected zone per pass: the bands are drawn per bar and stretch
           to the right edge, so labelling each bar's pass would stack the same words. */
        const zoneLabelled = new Set();

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
        /* T10/B13: the degrade verdict — hysteresis held on the view's own column width. */
        state.degradeOn = math.degradeDecision(v.scaleX, state.params.textPx, 15, state.degradeOn);
        const degrade = state.params.degrade && state.degradeOn;
        state.stats.degraded = false;
        state.stats.cellPx = cellPx * groupK;
        state.stats.groupK = groupK;
        state.stats.aggregating = lod.mode === 'profile' || groupFallback;
        /* Counted per paint so the badge's presence is assertable, not just visible. */
        state.stats.columnBadges = 0;
        state.stats.barBodies = 0;
        state.stats.barSplits = 0;

        for (let i = start; i < end; i += 1) {
            const bar = bars[i];
            const x = worldX(i);
            const colW = Math.max(1, v.scaleX);
            const raw = state.data.levels.get(bar.time) || [];
            if (!raw.length) continue;
            /* One paint decision per bar, from the catalogue — the same object the legend quotes. */
            const paint = barPaintFor(bar);
            const chrome = paint.chrome || CHROME_DEFAULT;

            if (lod.mode === 'profile' || groupFallback) {
                if (degrade) {
                    /* Below the text threshold the footprint draws plain candles — change what
                       is drawn, not how fast; the saved mode is untouched. */
                    const candle = barPaintFor(bar, 'candles');
                    if (candle) {
                        paintBodyFill(ctx, candle, bar, x, colW);
                        paintBodyStroke(ctx, candle, bar, x, colW);
                        ctx.strokeStyle = candle.wick.rgba;
                        ctx.lineWidth = candle.wick.lineWidth || 1;
                        ctx.beginPath();
                        ctx.moveTo(x + colW / 2, priceToY(bar.high));
                        ctx.lineTo(x + colW / 2, priceToY(bar.low));
                        ctx.stroke();
                        state.stats.barBodies += 1;
                        state.stats.degraded = true;
                    }
                    continue;
                }
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
            if (chrome.zones) zones.forEach((zone) => {
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
               band gone the matrix read as one continuous slab). `split` and `wick` drop it — their
               own sub-bars / range is the separator. */
            if (chrome.framing) {
                ctx.fillStyle = i % 2 ? 'rgba(255,255,255,.016)' : 'rgba(0,0,0,.10)';
                ctx.fillRect(x, 0, colW, v.height - RULER_H);      // audit C-16: never under the ruler
                ctx.fillStyle = 'rgba(150,175,215,.18)';
                ctx.fillRect(x + colW - 1, 0, 1, v.height);
            }
            /* The bar's own expression, under the cells: a tinted body (delta / heat) or the split
               candle's two halves. Drawn before the rows so the numbers keep their contrast. */
            if (paintBodyFill(ctx, paint, bar, x, colW)) state.stats.barBodies += 1;
            if (paintSplit(ctx, paint, bar, x, colW)) state.stats.barSplits += 1;

            for (let k = 0; k < (chrome.cells === false ? 0 : rows.length); k += 1) {
                const level = rows[k];
                const im = imRows[k];
                const y = priceToY(level.price) - cellH / 2;
                if (y < -cellH || y > v.height + cellH) continue;
                if (x + colW > plotRight) continue;      // C-03: never paint a cell over the rail
                const info = shares.rows[k] || { share: 0, inVA: false };
                const buyHot = im.side === 'buy' || im.side === 'both';
                const sellHot = im.side === 'sell' || im.side === 'both';

                /* Ground: value-area rows sit on a lighter slate than the outer 30%. */
                if (info.inVA && chrome.ground) {
                    ctx.fillStyle = math.rgba('vaGround', '.10');
                    ctx.fillRect(x, y, colW, cellH);
                }
                /* HVN: the heaviest row of the candle carries a warm tint under everything. */
                if (level.price === shares.hvn && chrome.ground) {
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
                /* Imbalance tint stays on the text-bearing half only, and now carries a low glow so
                   an imbalanced row reads at a glance rather than only in its digits. */
                if (buyHot) glowCell(ctx, x, y, half, cellH, 'imBuy');
                if (sellHot) glowCell(ctx, x + half, y, half, cellH, 'imSell');
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
            if (shares.vaCount && chrome.cells !== false) {
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
                ctx.fillStyle = `rgba(${colour},${(0.12 + Math.min(0.12, zone.count * 0.025)).toFixed(3)})`;
                ctx.fillRect(x, yTop, v.width - x, Math.max(2, yBot - yTop));
                ctx.fillStyle = `rgba(${colour},.55)`;
                ctx.fillRect(x, yTop, Math.min(46, colW), 1);
                ctx.fillRect(x, yBot, Math.min(46, colW), 1);
                /* The projection reaches the right edge now, so the band says what it is where it
                   ends: "BUY 3L projected" is readable without tracing back to its first bar. */
                const key = zone.side + '|' + zone.low + '|' + zone.high;
                if (!zoneLabelled.has(key) && (yBot - yTop) >= 9) {
                    zoneLabelled.add(key);
                    ctx.save();
                    ctx.textAlign = 'right';
                    ctx.font = '600 9.5px ui-monospace, monospace';
                    ctx.fillStyle = `rgba(${colour},.78)`;
                    ctx.fillText((zone.side === 'buy' ? 'BUY ' : 'SELL ') + (zone.count || '') + 'L projected',
                        v.width - 8, yTop + 10);
                    ctx.restore();
                }
            }

            /* The body's outline goes over the cells: the bar's boundary stays visible whatever the
               rows do underneath it. */
            paintBodyStroke(ctx, paint, bar, x, colW);

            const poc = math.poc(rows);
            if (poc && chrome.poc) {
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

            ctx.strokeStyle = paint.wick.rgba;
            ctx.lineWidth = paint.wick.lineWidth || 1;
            ctx.beginPath();
            ctx.moveTo(x + colW / 2, priceToY(bar.high));
            ctx.lineTo(x + colW / 2, priceToY(bar.low));
            ctx.stroke();

            /* Column stats: the bar's own delta and volume, hung above its high where an
               order-flow reader looks for them. Only where the column can carry the text. */
            if (chrome.badges && colW >= 48 && lod.text) {
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

    /* ── level reads (fold-in plan §3): unfinished auctions + node bands ────────────────────────
       The server owns the maths (`atlas/unfinished.py`, `atlas/nodes.py`); this is only the
       picture. Open magnets run dashed from their bar to the right edge until price returns and
       the server resolves them; node bands span the bars that shared one POC. `levelReadSegments`
       decides the geometry (pure, selftested), `drawLevelReads` puts the pixels down. */
    function setReads(reads) {
        const r = reads || {};
        const unf = (r.unfinished && Array.isArray(r.unfinished.open)) ? r.unfinished.open : [];
        const nds = (r.nodes && typeof r.nodes === 'object') ? r.nodes : null;
        const nodeList = nds ? ((nds.current ? [nds.current] : []).concat(nds.completed || [])) : [];
        state.data.reads = {
            unfinished: unf,
            nodes: nodeList,
            confluence: Array.isArray(r.confluence) ? r.confluence : [],
            note: typeof r.note === 'string' ? r.note : '',
        };
        state.dirty.base = true;
    }

    function levelReadSegments(bars, reads) {
        const out = { unfinished: [], nodes: [], dropped: 0 };
        if (!bars || !bars.length || !reads) return out;
        const list = (reads.unfinished || []).filter((lv) => lv && lv.active !== false);
        for (const lv of list) {
            const price = Number(lv.price);
            if (!Number.isFinite(price)) continue;
            const at = math.barIndex(bars, Number(lv.bar_ts_ms) / 1000);
            if (at < 0) { out.dropped += 1; continue; }
            out.unfinished.push({ price, side: lv.side === 'below' ? 'below' : 'above',
                                  from: at, to: -1, arms: Math.max(1, Number(lv.arms) || 1) });
        }
        for (const run of (reads.nodes || [])) {
            const price = Number(run && run.price);
            const count = Math.round(Number(run && run.count) || 0);
            if (!Number.isFinite(price) || count < 2) continue;
            const from = math.barIndex(bars, Number(run.start_ts_ms) / 1000);
            const to = math.barIndex(bars, Number(run.last_ts_ms) / 1000);
            if (from < 0) { out.dropped += 1; continue; }
            out.nodes.push({ price, count, from, to: to < 0 ? from : to });
        }
        return out;
    }

    function drawLevelReads(ctx) {
        const seg = levelReadSegments(state.data.bars, state.data.reads);
        state.stats.levelReadLines = seg.unfinished.length;
        state.stats.levelReadBands = seg.nodes.length;
        if (!seg.unfinished.length && !seg.nodes.length) return;
        const v = state.view;
        const colW = Math.max(2, v.scaleX);

        for (const band of seg.nodes) {
            const x0 = Math.max(0, worldX(band.from));
            const x1 = Math.min(v.width, worldX(band.to) + colW);
            if (x1 <= 0 || x0 >= v.width) continue;
            const yc = priceToY(band.price);
            if (yc < -12 || yc > v.height + 12) continue;
            ctx.fillStyle = math.rgba('hvn', '.18');
            ctx.fillRect(x0, yc - 3.5, Math.max(2, x1 - x0), 7);
            ctx.strokeStyle = math.rgba('hvn', '.55');
            ctx.lineWidth = 1;
            ctx.strokeRect(x0 + 0.5, yc - 3, Math.max(2, x1 - x0) - 1, 6);
            if (band.count >= 2 && v.scaleX >= 18) {
                ctx.fillStyle = math.rgba('hvn', '.9');
                ctx.font = '10px "Segoe UI", sans-serif';
                ctx.textAlign = 'left';
                ctx.fillText('\u00d7' + band.count, x0 + 3, yc - 6);
            }
        }

        for (const line of seg.unfinished) {
            const x0 = worldX(line.from);
            if (x0 > v.width) continue;
            const y = priceToY(line.price);
            if (y < -12 || y > v.height + 12) continue;
            ctx.save();
            ctx.setLineDash([5, 4]);
            ctx.strokeStyle = math.rgba('unfinished', '.65');
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(Math.max(0, x0), y + 0.5);
            ctx.lineTo(v.width, y + 0.5);
            ctx.stroke();
            ctx.restore();
            ctx.fillStyle = math.rgba('unfinished', '.9');
            ctx.font = '10px "Segoe UI", sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('UFB' + (line.arms > 1 ? ' \u00d7' + line.arms : '') + (line.side === 'below' ? ' \u2193' : ' \u2191'), v.width - 6, y - 3);
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
        const dpr = state.view.dpr || 1;
        resetLayer(ctx, canvas, dpr);
        /* Logical size: the ribbon paints in the stage's coordinate space (worldX/xToIndex), so its
           own box is stage-wide and the backing store may be dpr times that. */
        const width = canvas.width / dpr;
        const height = canvas.height / dpr;
        const bars = state.data.bars;
        if (!bars.length) return;
        const laneH = height / 3;
        /* P2-1: the shared prefix from `setData()` — index i + 1 is the cumulation THROUGH bar i.
           The local build is the fallback for a draw before any payload ever landed. */
        let cvd = state.idx && state.idx.cvd;
        if (!cvd) {
            cvd = new Float64Array(bars.length + 1);
            for (let i = 0; i < bars.length; i += 1) cvd[i + 1] = cvd[i] + (Number(bars[i].delta) || 0);
        }
        /* C-11: loops, not spreads — `Math.min(...cvd)` built one argument per bar and throws
           RangeError past the engine's argument limit (measured at 125,476 bars). */
        let maxVol = 1;
        let maxDelta = 1;
        let cvdLo = 0;
        let cvdHi = 1;
        for (const b of bars) {
            maxVol = Math.max(maxVol, Number(b.volume) || 0);
            maxDelta = Math.max(maxDelta, Math.abs(Number(b.delta) || 0));
        }
        for (const v of cvd) {
            const n = Number(v) || 0;
            cvdLo = Math.min(cvdLo, n);
            cvdHi = Math.max(cvdHi, n);
        }
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

            const y = laneH * 2 + laneH - ((cvd[i + 1] - cvdLo) / Math.max(1, cvdHi - cvdLo)) * (laneH - 6);
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

    /* ── P1-3: a selection is measurement ─────────────────────────────────────────────────────
       Shift+drag boxes a time x price region. The box is drawn here so it survives every repaint
       and camera move, and the numbers come from the payloads the engine already holds: bars for
       volume/delta, the per-bar depth levels for the resting change, prints for VWAP/count/largest.
       Nothing is re-fetched, so the strip cannot disagree with the pixels underneath it. */
    let selection = null;      /* {x0,y0,x1,y1} stage coords + the resolved {i0,i1,p0,p1} at release */
    let selDrag = null;        /* the live gesture */
    let selSeq = 0;

    function resolveSelection(a, b) {
        const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
        const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
        const n = state.data.bars.length;
        const [i0, i1] = math.selectionRange(xToIndex(x0), xToIndex(x1), n);
        const bars = n ? state.data.bars.slice(i0, i1 + 1) : [];
        return {
            x0: x0, y0: y0, x1: x1, y1: y1,
            i0: i0, i1: i1,
            /* y grows downward, price upward */
            p0: yToPrice(y1), p1: yToPrice(y0),
            barCount: bars.length,
            t0: bars.length ? bars[0].time : null,
            t1: bars.length ? bars[bars.length - 1].time : null,
        };
    }

    /* Isolate by dimming, never by hiding: the rest of the session stays readable while the
       selection is measured. */
    function drawSelection(ctx) {
        if (!selection || selDrag == null && selection.barCount === 0) {
            if (!selection) return;
        }
        const v = state.view;
        const x0 = selection.x0, x1 = selection.x1, y0 = selection.y0, y1 = selection.y1;
        const theme = (math && math.theme) || {};
        ctx.save();
        ctx.fillStyle = 'rgba(4,7,12,.55)';
        if (y0 > 0) ctx.fillRect(0, 0, v.width, y0);
        if (y1 < v.height) ctx.fillRect(0, y1, v.width, v.height - y1);
        if (x0 > 0) ctx.fillRect(0, y0, x0, Math.max(0, y1 - y0));
        if (x1 < v.width) ctx.fillRect(x1, y0, v.width - x1, Math.max(0, y1 - y0));
        ctx.strokeStyle = theme.trace || theme.grid || '#6fc3ff';
        ctx.lineWidth = 1;
        ctx.strokeRect(Math.round(x0) + 0.5, Math.round(y0) + 0.5,
            Math.max(1, Math.round(x1 - x0)), Math.max(1, Math.round(y1 - y0)));
        /* A3: the area profile's own lines — POC solid, the value-area edges dashed, inside the
           box that was measured. Labels sit just outside the right edge so the box stays a
           measurement; mid-drag (or with no ladder rows) there is nothing to draw and the box
           alone is honest. */
        const prof = selDrag == null ? areaProfile() : null;
        if (prof) {
            const lbl = (v) => (Math.abs(v) >= 1 ? v.toFixed(2) : String(Number(v.toPrecision(3))));
            const line = (price, rgba, dash) => {
                const y = Math.round(priceToY(price)) + 0.5;
                ctx.save();
                ctx.setLineDash(dash);
                ctx.strokeStyle = rgba;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x0, y);
                ctx.lineTo(x1, y);
                ctx.stroke();
                ctx.restore();
            };
            line(prof.poc, math.rgba('poc', '1'), []);
            line(prof.vah, math.rgba('vaEdge', '.85'), [4, 3]);
            line(prof.val, math.rgba('vaEdge', '.85'), [4, 3]);
            ctx.save();
            ctx.font = '600 9.5px ui-monospace, monospace';
            ctx.textAlign = 'left';
            ctx.fillStyle = math.rgba('poc', '1');
            ctx.fillText('POC ' + lbl(prof.poc), x1 + 5, Math.round(priceToY(prof.poc)) + 3);
            ctx.fillStyle = math.rgba('vaEdge', '.9');
            ctx.fillText('VAH ' + lbl(prof.vah), x1 + 5, Math.round(priceToY(prof.vah)) + 3);
            ctx.fillText('VAL ' + lbl(prof.val), x1 + 5, Math.round(priceToY(prof.val)) + 3);
            ctx.restore();
        }
        ctx.restore();
    }

    /* The selection's numbers, entirely from the loaded payloads. */
    /* The gesture is the module's; the arithmetic is math.selectionStats (pure, selftested). */
    function selectionStats() {
        if (!selection || selection.i1 < selection.i0 || !state.data.bars.length) return null;
        const st = math.selectionStats({
            bars: state.data.bars, levels: state.data.levels, prints: state.data.prints,
            i0: selection.i0, i1: selection.i1, p0: selection.p0, p1: selection.p1,
        });
        if (!st) return null;
        st.seq = selSeq;
        return st;
    }

    /* A3: the CURRENT selection's area profile, computed once per selection and cached — a repaint
       storm (every hover, every live bar) must not re-sum the window. The cache key is the
       selection's own serial number plus the VA share: both change exactly when the answer would. */
    let areaCache = { key: '', prof: null };
    function areaProfile() {
        if (!selection || selection.i1 < selection.i0 || !state.data.bars.length) return null;
        /* C-08: the data identity is part of the key — a poll or a symbol switch must not serve
           the previous dataset's POC/VAH/VAL out of the cache. */
        const key = `${selSeq}|${state.params.vaPct}|${state.data.key}|${state.data.bars.length}`;
        if (areaCache.key === key) return areaCache.prof;
        const prof = math.areaVolumeProfile({
            bars: state.data.bars, levels: state.data.levels,
            i0: selection.i0, i1: selection.i1, p0: selection.p0, p1: selection.p1,
            pct: state.params.vaPct,
        });
        areaCache = { key: key, prof: prof };
        return prof;
    }


    /* P1-4: put the viewport on the bar that contains a moment (a print the reader clicked). A moment
       newer than the newest drawn bar - a live print, and the footprint payload publishes closed bars
       only - seeks to that newest bar, which is the closest real position there is. A moment older
       than the session returns null rather than inventing a place for it. */
    function seekToTime(time) {
        const bars = state.data.bars;
        const raw = Number(time) || 0;
        const ts = raw > 1e11 ? raw / 1000 : raw;
        if (!bars.length || ts <= 0) return null;
        const sec = (typeof barSeconds === 'function' && barSeconds()) || 60;
        let idx = -1;
        for (let i = bars.length - 1; i >= 0; i -= 1) {
            if (bars[i].time <= ts) { idx = i; break; }
        }
        if (idx < 0) return null;
        if (ts >= bars[bars.length - 1].time + sec) idx = bars.length - 1;
        const perScreen = Math.max(1, state.view.width / state.view.scaleX);
        state.view.offX = idx - perScreen / 2;
        state.autoFit = false;
        clampView();
        state.dirty.base = state.dirty.live = state.dirty.heat = state.dirty.ribbon = true;
        applyMode();
        return idx;
    }

    function clearSelection() {
        selection = null;
        selDrag = null;
        selSeq += 1;
        state.dirty.live = true;
        if (typeof state.onSelection === 'function') state.onSelection(null);
    }

    /* §72: the display scale, one read per resize — the window may sit on a 125/150/200% monitor
       (or have just been moved onto one), and every backing store must carry devicePixelRatio,
       not CSS pixels. dpr = 1 reproduces the sizes this engine has always painted at. */
    function layerDpr() {
        const v = (typeof window !== 'undefined' && window.devicePixelRatio) ? Number(window.devicePixelRatio) : 1;
        return v > 0 ? v : 1;
    }

    /* One layer canvas: size its backing store from its own CSS box — falling back to the stage
       box when the canvas has no measurable one (a Node stub, a hidden tab) — at the given scale. */
    function sizeLayer(c, fallbackW, fallbackH, dpr) {
        const size = math.layerSize(c.clientWidth || fallbackW, c.clientHeight || fallbackH, dpr);
        if (c.width !== size.w || c.height !== size.h) { c.width = size.w; c.height = size.h; }
        return size;
    }

    /* Clear at 1:1, then paint in CSS pixels: every painter's maths stays in the logical space it
       was written for, and only the backing store carries the display scale. */
    function resetLayer(ctx, canvas, dpr) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function renderLayers(force) {
        const t0 = performance.now();
        state.lastPaint = Date.now();
        const job = [];
        if (state.dirty.heat || force) job.push('heat');
        if (state.dirty.base || force) job.push('base');
        if (state.dirty.live || force) job.push('live');
        if (state.dirty.ribbon || force) job.push('ribbon');
        for (let j = 0; j < job.length; j += 1) {
            const name = job[j];
            /* P2-3 (measured, §51): at 4K with a 30 k-cell matrix one payload-arrival frame cost
               17.5 ms — over the 60 Hz budget. When a frame has already spent its share, the rest
               of the job waits for the next rAF instead of blowing the frame: the deferred
               layers keep their dirty flags, and the tick paints them one frame later. */
            if (j > 0 && performance.now() - t0 >= YIELD_MS) {
                state.stats.yields += 1;
                break;
            }
            const canvas = state.layers[name];
            /* The flag is cleared whether or not a canvas is attached: a null layer used to
               stay dirty for ever, which kept this loop running on every animation frame and
               made the frame counter look healthy while nothing was drawn. */
            state.dirty[name] = false;
            if (!canvas) continue;
            const ctx = canvas.getContext('2d');
            const dpr = state.view.dpr || 1;
            if (name === 'heat') {
                /* P2-2: repair only when the pixels are actually outdated — a newer epoch repaints
                   in full; fading ghosts patch their own rects; anything else is a no-op (counted,
                   so a benchmark cannot mistake it for work). */
                if (state.heatPainted !== state.heatEpoch) {
                    resetLayer(ctx, canvas, dpr);
                    drawHeat(ctx);
                    state.heatPainted = state.heatEpoch;
                    state.stats.heatPasses += 1;
                } else if (state.heatGhosts.length) {
                    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);   // ghosts patch in logical pixels
                    if (patchHeat(ctx)) state.stats.heatPatches += 1;
                } else {
                    state.stats.heatSkips += 1;
                }
            } else if (name === 'base') {
                resetLayer(ctx, canvas, dpr);
                /* Axes first, then the matrix, then the executed-flow overlay: the frame must read
                   as a chart (what price, what time, where the data is) even before a bar is drawn. */
                drawAxes(ctx);
                drawFootprint(ctx);
                drawFlow(ctx);
                drawLevelReads(ctx);
            } else if (name === 'live') {
                resetLayer(ctx, canvas, dpr);
                drawSweeps(ctx);
                drawHud(ctx);
                drawSelection(ctx);
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
        /* decay runs at ~30 Hz: lambda is 500 ms, so a 60 Hz repaint of it is wasted work.
           P2-2: the cadence asks a question first — a pass only when the epoch moved or a ghost
           is still fading, so a static matrix costs nothing between payloads. */
        heatAccum += dt;
        if (heatAccum >= 33 && state.data.heat.length
            && (state.heatPainted !== state.heatEpoch || state.heatGhosts.length)) {
            heatAccum = 0;
            state.dirty.heat = true;
        }
        /* P2-2: coalesced — a fast sweep fires many moves per frame; hover runs once per tick,
           with the newest position, immediately before the layers paint. */
        if (state.pendingHover) {
            const p = state.pendingHover;
            state.pendingHover = null;
            hover(p.x, p.y);
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

    /* ── P1-9: keyboard zoom ──────────────────────────────────────────────────
       The wheel's own arithmetic with the anchor pulled out: the stage centre for the keys
       (there is no cursor), the pointer for the wheel. `idx`/`price` are read BEFORE the scale
       moves — that read is what pins the point under the anchor. */
    function zoomTime(factor, anchorX) {
        const W = state.view.width;
        const x = anchorX == null ? W / 2 : Math.max(0, Math.min(W, anchorX));
        const idx = xToIndex(x);
        const next = math.zoomScale(state.view.scaleX, factor, 2.5, 90);
        state.view.scaleX = next;
        state.view.offX = idx - x / next;
        if (state.autoFit) fitHeight();
        markViewDirty();
        return next;
    }

    function zoomPrice(factor, anchorY) {
        const H = state.view.height;
        const y = anchorY == null ? H / 2 : Math.max(0, Math.min(H, anchorY));
        const price = yToPrice(y);
        const next = math.zoomScale(state.view.scaleY, factor, 0.02, 40);
        state.view.scaleY = next;
        state.view.offY = math.anchorOffset(price, H, y, next);
        state.autoFit = false;                    // the user owns the price axis now
        markViewDirty();
        return next;
    }

    /* T5/A12: the precision nudge — one pixel, or ten with Shift, in either axis. The keys call
       it; the arithmetic is the drag's, with the delta spelled out. */
    function nudge(dxPx, dyPx) {
        const dx = Number(dxPx) || 0;
        const dy = Number(dyPx) || 0;
        if (dx) state.view.offX += dx / state.view.scaleX;
        if (dy) { state.view.offY += dy / state.view.scaleY; state.autoFit = false; }
        clampView();
        markViewDirty();
        return [state.view.offX, state.view.offY];
    }

    /* T10/B16: the value-scale menu — state-first (the tick shows which mode is on), and
       every item calls the same entry point the chips and keys use. Shares the drawing
       layer's menu classes, so it is already themed. */
    let scaleMenu = null;
    function closeScaleMenu() {
        if (scaleMenu && scaleMenu.parentNode) scaleMenu.parentNode.removeChild(scaleMenu);
        scaleMenu = null;
    }
    function openScaleMenu(clientX, clientY) {
        closeScaleMenu();
        const menu = document.createElement('div');
        menu.className = 'draw-menu';
        const item = (label, on, run) => {
            const b = document.createElement('button');
            b.className = 'draw-menu-item';
            b.type = 'button';
            b.textContent = (on ? '✓ ' : ' ') + label;
            b.addEventListener('click', () => { closeScaleMenu(); run(); });
            menu.appendChild(b);
        };
        item('Auto price scale (fit the data)', !!state.autoFit,
            () => { state.autoFit = true; fitHeight(true); clampView(); markViewDirty(); });
        item('Free scale — drag the rail to move prices', !state.autoFit,
            () => { state.autoFit = false; markViewDirty(); });
        item('Reset scales — price auto + time to live', false, () => { snapToLive(); });
        document.body.appendChild(menu);
        menu.style.left = Math.max(4, Math.min(window.innerWidth - 260, clientX)) + 'px';
        menu.style.top = Math.max(4, Math.min(window.innerHeight - 120, clientY)) + 'px';
        scaleMenu = menu;
        const off = (ev2) => {
            if (menu.contains(ev2.target)) return;
            closeScaleMenu();
            document.removeEventListener('mousedown', off, true);
        };
        setTimeout(() => document.addEventListener('mousedown', off, true), 0);
    }

    function markViewDirty() {
        state.dirty.base = state.dirty.live = state.dirty.ribbon = true;
        markHeatFull();                        // P2-2: the pixels are stale until the next pass
        applyLod();
    }

    function attach(canvas) {
        state.layers.base = canvas;
        canvas.addEventListener('wheel', (ev) => {
            /* A trackpad pinch arrives as ctrl+wheel; the browser would zoom the whole page, so it
               is cancelled here and routed into the same price-axis maths as the plain wheel,
               around the gesture's own point. */
            ev.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mx = ev.clientX - rect.left;
            const my = ev.clientY - rect.top;
            if (ev.shiftKey && !ev.ctrlKey) {
                /* X-axis only: zoom time around the cursor, price scale untouched */
                zoomTime(ev.deltaY < 0 ? 1.12 : 0.89, mx);
            } else {
                /* Y-axis only: zoom price around the cursor, time scale untouched */
                zoomPrice(ev.deltaY < 0 ? 1.09 : 0.92, my);
            }
        }, { passive: false });

        /* T10/B16: the value scale as an interactive object — right-click the price rail for
           auto / free / reset; a drag on the rail moves prices, while a drag on the matrix
           still pans time. */
        canvas.addEventListener('contextmenu', (ev) => {
            const rect = canvas.getBoundingClientRect();
            if ((ev.clientX - rect.left) < state.view.width - RAIL_W) return;   // the rail only
            ev.preventDefault();
            openScaleMenu(ev.clientX, ev.clientY);
        });

        /* Leaving the surface clears the hover state: without this the crosshair, tooltip and
           every pointer-following readout stayed frozen on screen (audit C-07 / B-JS-04). */
        canvas.addEventListener('mouseleave', () => {
            state.pendingHover = null;
            state.hover = null;
            state.dirty.live = true;
            if (typeof state.onHover === 'function') state.onHover(null);
        });

        let drag = null;
        canvas.addEventListener('mousedown', (ev) => {
            if (ev.shiftKey) {
                /* Shift+drag selects; a plain drag still pans, so nothing existing changes. */
                const rect = canvas.getBoundingClientRect();
                selDrag = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
                selection = { x0: selDrag.x, y0: selDrag.y, x1: selDrag.x, y1: selDrag.y, i0: 0, i1: -1, barCount: 0 };
                state.dirty.live = true;
                ev.preventDefault();
                return;
            }
            const rect0 = canvas.getBoundingClientRect();
            drag = { x: ev.clientX, y: ev.clientY, ox: state.view.offX, oy: state.view.offY,
                     axis: (ev.clientX - rect0.left) >= state.view.width - RAIL_W };
        });
        window.addEventListener('mouseup', () => {
            drag = null;
            if (!selDrag) return;
            selDrag = null;
            selection = resolveSelection({ x: selection.x0, y: selection.y0 }, { x: selection.x1, y: selection.y1 });
            selSeq += 1;
            state.dirty.live = true;
            if (typeof state.onSelection === 'function') state.onSelection(selectionStats());
        });
        window.addEventListener('mousemove', (ev) => {
            if (selDrag) {
                const rect = canvas.getBoundingClientRect();
                selection.x1 = Math.max(0, Math.min(state.view.width, ev.clientX - rect.left));
                selection.y1 = Math.max(0, Math.min(state.view.height, ev.clientY - rect.top));
                state.dirty.live = true;
                renderLayers(false);
                return;
            }
            if (drag) {
                const dx = (ev.clientX - drag.x) / state.view.scaleX;
                const dy = (ev.clientY - drag.y) / state.view.scaleY;
                if (drag.axis) {
                    /* T10/B16: dragging the value scale moves prices, not time. */
                    state.view.offY = drag.oy + dy;
                    state.autoFit = false;
                } else {
                    state.view.offX = drag.ox - dx;
                    state.view.offY = drag.oy + dy;
                    if (dy) state.autoFit = false;
                }
                clampView();
                if (state.autoFit) fitHeight();
                state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
                applyMode();
                return;
            }
            const rect = canvas.getBoundingClientRect();
            if (ev.clientX < rect.left || ev.clientX > rect.right || ev.clientY < rect.top || ev.clientY > rect.bottom) return;
            /* P2-2: coalesced into the frame — the tick runs hover once with the newest position
               before it paints, instead of once per raw pointer event. */
            state.pendingHover = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
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

    let hoverCache = { key: '', imRows: null, buyCount: 0, sellCount: 0, zones: [] };   // D-05
    let hoverScratch = null;

    function hover(mx, my) {
        const n = state.data.bars.length;
        if (!n) { state.hover = null; if (typeof state.onHover === 'function') state.onHover(null); return; }
        const i = Math.max(0, Math.min(n - 1, Math.floor(xToIndex(mx))));
        const bar = state.data.bars[i];
        if (!bar) return;
        const price = yToPrice(my);
        const rows = state.data.levels.get(bar.time) || [];
        /* D-05: the derived rows (imbalance rows, stacked zones) depend only on the bar and the
           params — rebuilding them per pointer frame allocated a fresh set every time. Cached
           here, keyed by bar index + R + stack + row count; the scratch object below carries the
           answer so a hover sweep allocates nothing per frame. */
        const paramsKey = i + ':' + state.params.R + ':' + state.params.stack + ':' + rows.length;
        if (hoverCache.key !== paramsKey) {
            const derived = math.diagonalImbalance(rows, state.params.R);
            hoverCache = { key: paramsKey, imRows: derived.rows, buyCount: derived.buyCount,
                           sellCount: derived.sellCount,
                           zones: math.stackedZones(derived.rows, state.params.stack) };
        }
        const imRows = hoverCache.imRows;
        const buyCount = hoverCache.buyCount;
        const sellCount = hoverCache.sellCount;
        /* P2-1: everything below reads the index built once per payload in `setData()` — the
           numbers are identical to the loops these replaced (pinned by ofx.selftest.js) and the
           per-mousemove cost no longer scales with the tape size or the matrix size. */
        const cvdPrefix = state.idx && state.idx.cvd;
        const cvd = cvdPrefix ? cvdPrefix[i + 1] : 0;
        let total = 0;
        for (const l of rows) total += l.bid + l.ask;
        const near = nearestLevel(rows, price);
        const nearIdx = near ? rows.indexOf(near.level) : -1;
        const im = nearIdx >= 0 ? imRows[nearIdx] : null;
        const zones = hoverCache.zones;
        const zone = near ? zones.find((z) => z.low <= near.level.price && near.level.price <= z.high) : null;
        /* Depth at the hovered row, from the renderer's own column groups — the layer that paints
           the cells and the layer that reports them can never disagree about which column it is. */
        let depth = 0;
        if (near && state.data.heatIndex) {
            for (const cell of state.data.heatIndex.groups.get(i) || []) {
                if (cell.lo <= near.level.price && near.level.price < cell.hi) depth += cell.size;
            }
        }
        const bucket = (state.idx && state.idx.printsByBar && state.idx.printsByBar[i]) || null;
        const events = (state.idx && state.idx.flowByCol && state.idx.flowByCol.get(i)) || [];
        const out = hoverScratch || (hoverScratch = {});
        out.x = mx; out.y = my; out.price = price; out.index = i; out.bar = bar;
        state.hover = Object.assign(out, {
            barTime: bar.time, cvd, total, buyCount, sellCount, zones: zones.length,
            zone: zone ? { side: zone.side, count: zone.count, low: zone.low, high: zone.high } : null,
            level: near ? { price: near.level.price, bid: near.level.bid, ask: near.level.ask, dist: near.dist } : null,
            imbalance: im ? { side: im.side, ratio: im.ratio, buy: im.buy, sell: im.sell } : null,
            depth, prints: bucket ? bucket.prints : 0, sweep: bucket ? bucket.sweep : 0,
            events: events.map((e) => ({ kind: e.kind, direction: e.direction, price: e.price, size: e.size })),
            calc: bar.calc || null,
            visibleBars: barsOnScreen(),
        });
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
        fitHeight(true);
        applyLod();
        applyMode();
        state.autoFit = true;
        state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
    }

    function snapToLive() {
        state.autoFit = true;
        state.view.offX = Math.max(0, state.data.bars.length - Math.floor(state.view.width / state.view.scaleX));
        fitHeight(true);
        clampView();
        applyMode();
        state.dirty.base = state.dirty.live = state.dirty.ribbon = state.dirty.heat = true;
    }

    function resize(width, height) {
        state.view.width = width;
        state.view.height = height;
        const dpr = layerDpr();
        state.view.dpr = dpr;
        for (const key of ['heat', 'base', 'live']) {
            const c = state.layers[key];
            if (!c) continue;
            sizeLayer(c, width, height, dpr);
        }
        const r = state.layers.ribbon;
        if (r) {
            /* The legend's own contract — 'volume, delta, CVD on the same X as the bars' — means the
               ribbon paints in the stage's coordinate space, so its CSS box must BE the stage's
               width. It used to keep `width: 100%` while the backing store was stage-wide, so the
               browser stretched the picture ~17% horizontally wherever the readout column showed. */
            const boxW = Math.max(1, Math.round(width));
            if (r.style && r.style.width !== boxW + 'px') r.style.width = boxW + 'px';
            sizeLayer(r, boxW, 84, dpr);
        }
        /* P2-2: setting canvas.width CLEARS the canvas — without this bump the change gate would
           happily skip the repaint and leave a blank heat layer. */
        markHeatFull();
        fitHeight(true);
        applyLod();
        applyMode();
    }

    const ofx = {
        NS, math, state,
        worldX, xToIndex, priceToY, yToPrice,
        setData, setReads, levelReadSegments, profileBars, computeSessionAverages,
        indexLevels, renderLayers, start, stop, attach, resize,
        hover, applyLod, applyMode, clampView, viewBounds, barsOnScreen, snapToLive, fitSession, fitHeight,
        zoomTime, zoomPrice, barSeconds, legend, nudge, fitTolerance,
        stats() {
            const s = state.stats;
            return {
                frames: s.frames, lastMs: +s.lastMs.toFixed(2), emaMs: +s.emaMs.toFixed(2), p95Ms: +s.p95Ms.toFixed(2),
                heatPasses: s.heatPasses, heatPatches: s.heatPatches, heatSkips: s.heatSkips, yields: s.yields,
                heatGhosts: state.heatGhosts.length, decayCells: s.decayCells, mode: state.mode, lod: state.lod.mode,
                printsSeen: s.printsSeen, printsMatched: s.printsMatched, sweepBubbles: s.sweepBubbles,
                heatCells: state.data.heat.length, textStarved: s.textStarved, columnBadges: s.columnBadges || 0,
                autoFit: state.autoFit,
                cellPx: +s.cellPx.toFixed(2), aggregating: s.aggregating, groupK: s.groupK,
                divState: s.divState, blocksFiltered: s.blocksFiltered, maxFrameMs: s.framesMs.length ? +Math.max(...s.framesMs).toFixed(2) : 0,
                recovered: s.recovered, flowBubbles: s.flowBubbles, flowEvents: s.flowEvents, barsOnScreen: barsOnScreen(),
                /* P1-8: what the expression pass actually painted this frame, so a mode can be
                   asserted from telemetry instead of from pixels. */
                expression: {
                    mode: exprMode().key, palette: exprMode().palette,
                    bodies: s.barBodies || 0, splits: s.barSplits || 0,
                },
                colW: +state.view.scaleX.toFixed(1), levelCount: state.data.levels.size,
                levelReads: { lines: s.levelReadLines || 0, bands: s.levelReadBands || 0 },
                avgLevelVolume: +state.avgLevelVolume.toFixed(2), symbol: state.symbol, params: { ...state.params },
            };
        },
        setParams(next) {
            const n = next || {};
            Object.assign(state.params, n);
            /* B2: the heat dials are clamped at adoption — the config store clamps the stored
               value, but the renderer holds the same line for whatever is handed to it directly. */
            if (n.heatContrast !== undefined) {
                const g = Number(n.heatContrast);
                state.params.heatContrast = Number.isFinite(g) ? Math.min(2.5, Math.max(0.5, g)) : 1;
            }
            if (n.heatFloor !== undefined) {
                const f = Number(n.heatFloor);
                state.params.heatFloor = Number.isFinite(f) ? Math.max(0, f) : 0;
            }
            if (n.heatFloorPct !== undefined) {
                const pct = Number(n.heatFloorPct);
                state.params.heatFloorPct = Number.isFinite(pct) ? Math.min(50, Math.max(0, pct)) : 0;
            }
            if (n.heatSmooth !== undefined) {
                state.params.heatSmooth = (['auto', 'manual', 'none'].indexOf(String(n.heatSmooth)) >= 0)
                    ? String(n.heatSmooth) : 'auto';
            }
            if (n.heatDim !== undefined) {
                const d = Number(n.heatDim);
                state.params.heatDim = Number.isFinite(d) ? Math.min(0.8, Math.max(0, d)) : 0;
            }
            if (n.heatHighlight !== undefined) {
                const hl = Number(n.heatHighlight);
                state.params.heatHighlight = Number.isFinite(hl) ? Math.min(1, Math.max(0, hl)) : 0;
            }
            if (n.degrade !== undefined) state.params.degrade = !!n.degrade;
            applyLod();
            state.dirty.base = state.dirty.live = true;
            markHeatFull();                    // P2-2: lambda changes the curve, ramp the palette
        },
        RAMPS,
        /* P1-8: the bar expression, applied as one thing — the palette writes the colour table (so
           the legend would already have to tell the truth about it) and the mode changes what each
           bar draws. Returns what the catalogue resolved, which is what the control displays. */
        setExpression(next) {
            const n = next || {};
            if (n.mode !== undefined) state.params.mode = String(n.mode);
            if (n.palette !== undefined) state.params.palette = String(n.palette);
            const applied = applyPalette(state.params.palette);
            const resolved = exprMode();
            state.dirty.base = state.dirty.live = true;
            markHeatFull();
            return { mode: resolved.key, palette: resolved.palette, overrides: applied };
        },
        expression: exprMode,
        /* P1-3: the selection's own surface (the arithmetic lives in math.selectionStats). */
        selection: () => (selection ? Object.assign({}, selection) : null),
        selectionStats: selectionStats,
        areaProfile: areaProfile,
        clearSelection: clearSelection,
        seekToTime: seekToTime,
        /* T10/B16: the price-scale state, and the degrade/smoothing reads (pins + receipts). */
        scales: () => ({ autoFit: !!state.autoFit, scaleX: state.view.scaleX, scaleY: state.view.scaleY }),
        degrade: () => ({ on: state.degradeOn === true, enabled: state.params.degrade !== false,
            mode: state.params.mode, smoothHeat: !!state.smoothHeatOn }),
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = ofx;
    if (typeof globalThis !== 'undefined') globalThis.OFX = ofx;
    return ofx;
})(typeof globalThis !== 'undefined' ? globalThis : this);
