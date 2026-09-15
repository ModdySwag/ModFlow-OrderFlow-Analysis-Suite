/* rsi.js — RSI (Relative Strength Index)
   Wilder's smoothing on average gain vs average loss: a 0-100 oscillator, 70/30 as the conventional overbought/oversold marks.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…).
   Add-on: OrderFlow indicator pack v0.4.1 — a plain file in desktop/ui/indicators; drop one in and reload. */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;

    class rsi {
        init() {
            this.up = T.wilders(this.props.period);
            this.down = T.wilders(this.props.period);
            this.prev = undefined;
        }
        map(d) {
            const close = d.close();
            const change = this.prev === undefined ? 0 : close - this.prev;
            this.prev = close;
            const gain = this.up(Math.max(0, change));
            const loss = this.down(Math.max(0, -change));
            if (gain === undefined || loss === undefined) return {};
            const rs = loss === 0 ? Infinity : gain / loss;
            const value = loss === 0 ? 100 : 100 - (100 / (1 + rs));
            const over = value >= this.props.overbought;
            const under = value <= this.props.oversold;
            return {
                value,
                style: { value: { color: over ? '#ff5d6c' : (under ? '#35d07f' : undefined) } },
                signal: this.props.signal && (over || under)
                    ? { side: over ? 'sell' : 'buy', text: `RSI ${value.toFixed(1)}` } : undefined,
            };
        }
    }

    const studyDef = {
        name: 'rsi',
        description: 'RSI (Relative Strength Index)',
        calculator: rsi,
        params: { period: P.period(14), overbought: P.number(70, 1, 50), oversold: P.number(30, 1, 0), signal: P.boolean(true) },
        plots: { value: { title: 'RSI' } },
        plotter: PL.singleline('value'),
        tags: ['Oscillators'],
        schemeStyles: S.solidLine('#c792ea', 2),
        pack: 'OrderFlow indicator pack',
        version: '0.4.1',
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
