/* price-offset.js — the minimal study.
   Mirrors the suite's indicator contract 'Simple Price Offset' tutorial: one class, one map().
   Contract: indicator module for this suite's contract (name/description/calculator/params/…). */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;


    class priceOffset {
        map(d) {
            return d.value() - this.props.offset;
        }
    }

    const studyDef = {
        name: 'priceOffset',
        description: 'Price offset (stop-loss line)',
        calculator: priceOffset,
        params: { offset: P.number(2.0, 0.25, -10000) },
        tags: ['Starter'],
        schemeStyles: S.dashedLine('#9aa9c1', 1),
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
