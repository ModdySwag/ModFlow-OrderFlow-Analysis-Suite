/* alligator.js — three smoothed averages, three plots.
   The 'Alligator' tutorial shape: several offsets of one smoother, one colour each.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…). */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;


    class alligator {
        init() {
            this.jaw = T.sma(this.props.jaw);
            this.teeth = T.sma(this.props.teeth);
            this.lips = T.sma(this.props.lips);
        }
        map(d) {
            return {
                jaw: this.jaw(d.value()),
                teeth: this.teeth(d.value()),
                lips: this.lips(d.value()),
            };
        }
    }

    const studyDef = {
        name: 'alligator',
        description: 'Alligator (smoothed jaw / teeth / lips)',
        calculator: alligator,
        params: {
            jaw: P.period(13),
            teeth: P.period(8),
            lips: P.period(5),
        },
        plots: {
            jaw: { title: 'Jaw' },
            teeth: { title: 'Teeth' },
            lips: { title: 'Lips' },
        },
        plotter: [PL.singleline('jaw'), PL.singleline('teeth'), PL.singleline('lips')],
        tags: ['Trend'],
        schemeStyles: {
            jaw: S.solidLine('#4f8cff', 2),
            teeth: S.solidLine('#ff8a5c', 2),
            lips: S.solidLine('#35d07f', 2),
        },
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
