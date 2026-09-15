/* macd.js — MACD (Moving Average Convergence/Divergence)
   Fast and slow EMAs with a signal EMA on top; the histogram is the distance between the MACD line and its signal.
   Contract: indicator module for this suite's contract (name/description/calculator/params/…).
   Add-on: OrderFlow indicator pack v0.4.1 — a plain file in desktop/ui/indicators; drop one in and reload. */
(function (root) {
    const api = root.StudyAPI
        || (typeof require !== 'undefined' ? require('../study-api.js') : null);
    if (!api) return;
    const { paramSpecs: P, styles: S, plotters: PL, meta: M, tools: T } = api;

    class macd {
        init() {
            this.fast = T.ema(this.props.fast);
            this.slow = T.ema(this.props.slow);
            this.signalLine = T.ema(this.props.signal);
        }
        map(d) {
            const close = d.close();
            const fast = this.fast(close);
            const slow = this.slow(close);
            if (fast === undefined || slow === undefined) return {};
            const macd = fast - slow;
            const signal = this.signalLine(macd);
            const hist = signal === undefined ? undefined : macd - signal;
            const cross = hist !== undefined && this.lastHist !== undefined
                && ((this.lastHist <= 0 && hist > 0) || (this.lastHist >= 0 && hist < 0));
            this.lastHist = hist;
            return {
                macd, signal, hist,
                style: { hist: { color: hist >= 0 ? '#35d07f' : '#ff5d6c' } },
                signalMarker: undefined,
                ...(this.props.signal && cross
                    ? { signal: { side: hist > 0 ? 'buy' : 'sell', text: `MACD ${hist > 0 ? 'cross up' : 'cross down'}` } }
                    : {}),
            };
        }
    }

    const studyDef = {
        name: 'macd',
        description: 'MACD (Moving Average Convergence/Divergence)',
        calculator: macd,
        params: { fast: P.period(12), slow: P.period(26), signal: P.period(9), crossover: P.boolean(true) },
        plots: { macd: { title: 'MACD' }, signal: { title: 'Signal' }, hist: { title: 'Histogram' } },
        plotter: PL.columns('hist'),
        tags: ['Trend', 'Momentum'],
        schemeStyles: S.solidLine('#4f8cff', 2),
        pack: 'OrderFlow indicator pack',
        version: '0.4.1',
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = studyDef;
    if (root.StudyAPI) root.StudyAPI.registry.register(studyDef);
})(typeof globalThis !== 'undefined' ? globalThis : this);
