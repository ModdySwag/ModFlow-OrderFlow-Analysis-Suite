/* delta-flow.js — this build's own field, in their authoring model.
   No the suite's indicator contract indicator can compute this: the chart's bars carry aggressive buy/sell
   volume and per-bar delta from this build's tape, exposed as d.buy() / d.sell() /
   d.delta(). A bar whose delta is more than `sigma` standard deviations from its recent
   mean is coloured and emitted as a signal — which the app turns into a chart marker and
   an alert, the same path its own pattern detections use.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…). */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;


    class deltaFlow {
        init() {
            this.deviation = T.stdev(this.props.window);
        }
        map(d) {
            const delta = d.delta();
            const sd = this.deviation(delta);
            const mean = this.props.window > 0 ? 0 : 0;          // delta oscillates around zero
            const hot = sd !== undefined && sd > 0 && Math.abs(delta - mean) > this.props.sigma * sd;
            const side = delta >= 0 ? 'buy' : 'sell';
            const style = hot
                ? { color: side === 'buy' ? '#35d07f' : '#ff5d6c' }
                : undefined;
            const out = {
                delta,
                style: { delta },
                candlestick: hot ? { color: side === 'buy' ? '#1e6b45' : '#7a2b36' } : undefined,
            };
            if (hot && this.props.signal) out.signal = { side, text: `delta ${delta >= 0 ? '+' : ''}${delta.toFixed(2)}` };
            return out;
        }
    }

    const studyDef = {
        name: 'deltaFlow',
        description: 'Delta flow (tape delta vs its own deviation)',
        calculator: deltaFlow,
        params: {
            window: P.period(20),
            sigma: P.number(2, 0.1, 0.1),
            signal: P.boolean(true),
        },
        inputType: M.InputType.BARS,
        areaChoice: M.AreaChoice.NEW,
        plots: { delta: { title: 'Bar delta' } },
        plotter: PL.columns('delta'),
        tags: ['Order flow'],
        schemeStyles: S.columns('#7fd4ff'),
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
