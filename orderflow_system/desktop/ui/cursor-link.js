/* cursor-link.js - one price, one time, shared by every panel.
 *
 * Panels must not reach into each other. They publish what the cursor is over and subscribe to what
 * they care about; this file is the only place that knows both sides exist. Kept deliberately small:
 * a value, an origin, listeners, and a clear-on-leave.
 */
(function () {
    'use strict';
    const state = { price: null, timeMs: null, source: '', at: 0 };
    const subs = [];

    function publish(next) {
        const changed = (next.price !== state.price) || (next.timeMs !== state.timeMs);
        state.price = next.price == null ? null : next.price;
        state.timeMs = next.timeMs == null ? null : next.timeMs;
        state.source = next.source || state.source;
        state.at = Date.now();
        if (!changed) return;
        subs.forEach((fn) => { try { fn(state); } catch (e) { /* one bad subscriber must not stop the rest */ } });
    }

    function clear(source) {
        if (source && state.source && source !== state.source) return;   // another panel owns it
        publish({ price: null, timeMs: null, source: source || state.source });
    }

    window.OFAPCURSOR = {
        state: state,
        set: (price, opts) => publish(Object.assign({ price: price }, opts || {})),
        move: (price, timeMs, source) => publish({ price: price, timeMs: timeMs, source: source }),
        clear: clear,
        subscribe: (fn) => { subs.push(fn); return fn; },
        /* The nearest price in a list - how a panel that draws its own rows finds the cursor. */
        nearest: (prices, tol) => {
            if (state.price == null || !prices || !prices.length) return null;
            let best = null, bestD = Infinity;
            for (const p of prices) {
                const d = Math.abs(p - state.price);
                if (d < bestD) { bestD = d; best = p; }
            }
            return (tol == null || bestD <= tol) ? best : null;
        },
    };
})();
