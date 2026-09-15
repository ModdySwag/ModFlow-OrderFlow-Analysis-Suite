/* ema.js — exponential moving average.
   The 'Human-friendlier EMA' tutorial: a readable name, a period parameter, one line.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…). */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;


    class ema {
        init() {
            this.ema = T.ema(this.props.period);
        }
        map(d) {
            return this.ema(d.value());
        }
    }

    const studyDef = {
        name: 'ema',
        description: 'EMA (exponential moving average)',
        calculator: ema,
        params: { period: P.period(21) },
        plots: { value: { title: 'EMA' } },
        plotter: PL.singleline('value'),
        tags: ['Averages'],
        schemeStyles: S.solidLine('#4f8cff', 2),
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
