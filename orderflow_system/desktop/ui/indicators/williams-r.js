/* williamsR.js — Williams %R
   Where the close sits inside the last N bars' range, as -100 (at the low) to 0 (at the high): the oscillator scalpers read for exhaustion at range edges.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…).
   Add-on: OrderFlow indicator pack v0.4.1 — a plain file in desktop/ui/indicators; drop one in and reload. */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;

    class williamsR {
        init() {
            this.hi = T.highest(this.props.period);
            this.lo = T.lowest(this.props.period);
        }
        map(d) {
            const high = this.hi(d.high());
            const low = this.lo(d.low());
            if (high === undefined || low === undefined || high === low) return {};
            const close = d.close();
            const value = ((high - close) / (high - low)) * -100;
            const over = value >= -this.props.overbought;      // near the top of the range
            const under = value <= -this.props.oversold;       // near the bottom
            return {
                value,
                style: { value: { color: over ? '#ff5d6c' : (under ? '#35d07f' : undefined) } },
                signal: this.props.signal && (over || under)
                    ? { side: over ? 'sell' : 'buy', text: `%R ${value.toFixed(1)}` } : undefined,
            };
        }
    }

    const studyDef = {
        name: 'williamsR',
        description: 'Williams %R',
        calculator: williamsR,
        params: { period: P.period(14), overbought: P.number(20, 1, 1), oversold: P.number(80, 1, 1), signal: P.boolean(true) },
        plots: { value: { title: '%R' } },
        plotter: PL.singleline('value'),
        tags: ['Oscillators'],
        schemeStyles: S.solidLine('#ffb04d', 2),
        pack: 'OrderFlow indicator pack',
        version: '0.4.1',
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
