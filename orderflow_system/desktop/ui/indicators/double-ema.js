/* double-ema.js — two averages, two plots.
   The 'Double EMA' tutorial: two plot fields, per-plot colours in schemeStyles.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…). */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;


    class doubleEma {
        init() {
            this.slow = T.ema(this.props.slowPeriod);
            this.fast = T.ema(this.props.fastPeriod);
        }
        map(d) {
            return { fast: this.fast(d.value()), slow: this.slow(d.value()) };
        }
    }

    const studyDef = {
        name: 'doubleEma',
        description: 'Double EMA',
        calculator: doubleEma,
        params: {
            slowPeriod: P.period(21),
            fastPeriod: P.period(10),
        },
        plots: {
            fast: { title: 'FastEMA' },
            slow: { title: 'SlowEMA' },
        },
        plotter: [PL.dots('slow'), PL.singleline('fast')],
        tags: ['Averages'],
        schemeStyles: { fast: S.solidLine('#ff8a5c', 2), slow: S.dots('#7fd4ff') },
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
