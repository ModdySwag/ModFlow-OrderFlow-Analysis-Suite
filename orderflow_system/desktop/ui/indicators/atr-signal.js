/* atr-signal.js — Average True Range with a tick-denominated highlight.
   The 'Signaling ATR' tutorial: bars input, its own area, per-item style and a
   candlestick override when the ATR exceeds a threshold given in ticks.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…). */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;


    class averageTrueRange {
        init() {
            this.average = T.wilders(this.props.period);
        }
        map(d) {
            const atr = this.average(T.trueRange(d));
            const tickSize = this.contractInfo.tickSize || 0.01;
            const atrInTicks = tickSize > 0 ? atr / tickSize : 0;
            const hot = atrInTicks > this.props.threshold;
            const overrideStyle = hot ? { color: d.open() > d.close() ? '#ff8a8a' : '#8effb0' } : undefined;
            return {
                value: atr,
                candlestick: overrideStyle,
                style: { value: overrideStyle },
            };
        }
    }

    const studyDef = {
        name: 'atrSignal',
        description: 'Average True Range (signals above N ticks)',
        calculator: averageTrueRange,
        params: {
            period: P.period(14),
            threshold: P.number(10, 1, 0),
        },
        inputType: M.InputType.BARS,
        areaChoice: M.AreaChoice.NEW,
        plots: { value: { title: 'ATR' } },
        plotter: PL.columns('value'),
        tags: ['Volatility'],
        schemeStyles: S.columns('#ffe270'),
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
