/* obv.js — OBV (On-Balance Volume)
   Cumulative volume signed by the direction of the close: volume is added on up bars and subtracted on down bars, so the line tracks whether volume is following price.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…).
   Add-on: OrderFlow indicator pack v0.4.1 — a plain file in desktop/ui/indicators; drop one in and reload. */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;

    class obv {
        init() {
            this.total = 0;
            this.prevClose = undefined;
            this.prevObv = undefined;
        }
        map(d) {
            const close = d.close();
            const volume = d.volume() || 0;
            if (this.prevClose !== undefined) {
                if (close > this.prevClose) this.total += volume;
                else if (close < this.prevClose) this.total -= volume;
            }
            this.prevClose = close;
            const value = this.total;
            /* A divergence read the way an order-flow user checks it: price makes a new extreme on
               falling OBV (or the reverse). */
            let signal;
            if (this.props.signal && this.prevObv !== undefined) {
                const rising = value > this.prevObv;
                if (this.props.rising && !rising) signal = { side: 'sell', text: 'OBV turning down' };
                if (!this.props.rising && rising) signal = { side: 'buy', text: 'OBV turning up' };
            }
            this.prevObv = value;
            return { value, signal };
        }
    }

    const studyDef = {
        name: 'obv',
        description: 'OBV (On-Balance Volume)',
        calculator: obv,
        params: { signal: P.boolean(false), rising: P.boolean(true) },
        plots: { value: { title: 'OBV' } },
        plotter: PL.singleline('value'),
        tags: ['Volume'],
        schemeStyles: S.solidLine('#7fd4ff', 2),
        pack: 'OrderFlow indicator pack',
        version: '0.4.1',
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
