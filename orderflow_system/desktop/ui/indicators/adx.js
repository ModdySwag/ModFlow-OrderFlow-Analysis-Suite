/* adx.js — ADX (Average Directional Index) with +DI / -DI
   Wilder's directional movement: +DI and -DI show which side is in control, ADX shows how strong the move is (below 20 ranging, above 25 trending) — the filter order-flow traders put in front of every footprint read.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…).
   Add-on: OrderFlow indicator pack v0.4.1 — a plain file in desktop/ui/indicators; drop one in and reload. */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;

    class adx {
        init() {
            const p = this.props.period;
            this.tr = T.wilders(p);
            this.plus = T.wilders(p);
            this.minus = T.wilders(p);
            this.adxAvg = T.wilders(p);
            this.prev = undefined;
            this.prevAdx = undefined;
            this.prevPlus = undefined;
            this.prevMinus = undefined;
        }
        map(d) {
            const high = d.high();
            const low = d.low();
            const close = d.close();
            if (this.prev === undefined) {
                this.prev = { high, low, close };
                return {};
            }
            const prevHigh = this.prev.high;
            const prevLow = this.prev.low;
            const prevClose = this.prev.close;
            this.prev = { high, low, close };

            const upMove = high - prevHigh;
            const downMove = prevLow - low;
            const plusDm = upMove > downMove && upMove > 0 ? upMove : 0;
            const minusDm = downMove > upMove && downMove > 0 ? downMove : 0;
            const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));

            const trS = this.tr(tr);
            const plusS = this.plus(plusDm);
            const minusS = this.minus(minusDm);
            if (!trS || plusS === undefined || minusS === undefined) return {};
            const plusDi = (plusS / trS) * 100;
            const minusDi = (minusS / trS) * 100;
            const sum = plusDi + minusDi;
            const dx = sum === 0 ? 0 : (Math.abs(plusDi - minusDi) / sum) * 100;
            const adx = this.adxAvg(dx);
            if (adx === undefined) return { plusDi, minusDi };

            const trending = adx >= this.props.threshold;
            const flip = this.prevAdx !== undefined && this.prevPlus !== undefined
                && ((this.prevPlus <= this.prevMinus && plusDi > minusDi)
                    || (this.prevPlus >= this.prevMinus && plusDi < minusDi));
            this.prevAdx = adx;
            this.prevPlus = plusDi;
            this.prevMinus = minusDi;
            return {
                adx, plusDi, minusDi,
                style: {
                    adx: { color: trending ? '#ffd166' : undefined },
                    plusDi: { color: '#35d07f' },
                    minusDi: { color: '#ff5d6c' },
                },
                signal: this.props.signal && flip
                    ? { side: plusDi > minusDi ? 'buy' : 'sell',
                        text: `DI ${plusDi > minusDi ? '+ over -' : '- over +'} (ADX ${adx.toFixed(0)})` }
                    : undefined,
            };
        }
    }

    const studyDef = {
        name: 'adx',
        description: 'ADX (Average Directional Index) with +DI / -DI',
        calculator: adx,
        params: { period: P.period(14), threshold: P.number(25, 1, 5), signal: P.boolean(true) },
        plots: { adx: { title: 'ADX' }, plusDi: { title: '+DI' }, minusDi: { title: '-DI' } },
        plotter: PL.singleline('adx'),
        tags: ['Trend'],
        schemeStyles: S.solidLine('#ffd166', 2),
        pack: 'OrderFlow indicator pack',
        version: '0.4.1',
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
