/* cursor-link.js - one price, one time, shared by every panel.
 *
 * Panels must not reach into each other. They publish what the cursor is over and subscribe to what
 * they care about; this file is the only place that knows both sides exist. Kept deliberately small:
 * a value, an origin, listeners, a clear-on-leave.
 *
 * P1-2 (the cursor spine) makes three additions, all of them shared here rather than repeated in six
 * panels:
 *   - `badge(host)` — the price/time tag every panel shows, created once and driven by the store, so
 *     the panels cannot disagree about its style or drift out of date;
 *   - `subscribe()` returns its own way out (the bus's contract), so a panel that unmounts can stop;
 *   - `selection` — the slot P1-3 fills. It travels with the cursor because a selection IS a price and
 *     a time range; nothing reads it yet, and a panel that does gets it for free on the next publish.
 */
(function () {
    'use strict';
    const state = { price: null, timeMs: null, source: '', selection: null, at: 0 };
    const subs = [];
    const badges = [];
    let badgeId = 0;

    function publish(next) {
        /* A field the caller did NOT MENTION is not a change; an explicit null is a clear. Both
           halves matter: `move()` carries no selection (P1-2), and `select()` carries no price, so
           treating either absence as "cleared" would wipe what another panel is reading. */
        const changed = (next.price !== undefined && next.price !== state.price)
            || (next.timeMs !== undefined && next.timeMs !== state.timeMs)
            || (next.selection !== undefined && next.selection !== state.selection);
        if (next.price !== undefined) state.price = next.price == null ? null : next.price;
        if (next.timeMs !== undefined) state.timeMs = next.timeMs == null ? null : next.timeMs;
        if (next.selection !== undefined) state.selection = next.selection;
        state.source = next.source || state.source;
        state.at = Date.now();
        paintBadges();
        if (!changed) return;
        subs.forEach((fn) => { try { fn(state); } catch (e) { /* one bad subscriber must not stop the rest */ } });
    }

    function clear(source) {
        if (source && state.source && source !== state.source) return;   // another panel owns it
        publish({ price: null, timeMs: null, source: source || state.source });
    }

    function fmtPrice(v) {
        if (v == null || !isFinite(Number(v))) return '—';
        const n = Number(v);
        if (Math.abs(n) >= 1000) return n.toFixed(2);
        if (Math.abs(n) >= 1) return n.toFixed(3);
        return n.toFixed(5);
    }
    function fmtTime(ms) {
        if (ms == null || !isFinite(Number(ms))) return '';
        const n = Number(ms);
        const d = new Date(n > 1e11 ? n : n * 1000);      // buckets arrive in ms, bars in seconds
        return d.toTimeString().slice(0, 8);
    }
    function text() {
        if (state.price == null && state.timeMs == null) return '';
        const t = fmtTime(state.timeMs);
        return fmtPrice(state.price) + (t ? ' · ' + t : '');
    }

    /* One badge per panel: a small tag in the panel's own chrome that says what the shared cursor is
       on. It is created once and repainted from the store, so every panel shows the same numbers at
       the same instant — and a panel that repaints its own DOM never has to remember to re-apply it. */
    function badge(host, opts) {
        if (!host || typeof document === 'undefined' || !document) return null;
        opts = opts || {};
        let el = host.querySelector('[data-ofap-badge]');
        if (!el) {
            el = document.createElement('span');
            el.setAttribute('data-ofap-badge', String(++badgeId));
            el.className = 'ofap-cursor-badge' + (opts.className ? ' ' + opts.className : '');
            el.title = opts.title || 'the shared cursor: what every panel is reading right now';
            (opts.before ? host.insertBefore(el, opts.before) : host.appendChild(el));
        }
        if (badges.indexOf(el) < 0) badges.push(el);      // C-06: one entry per badge element
        paintBadges();
        return el;
    }

    function paintBadges() {
        if (typeof document === 'undefined' || !document) return;
        /* C-06: replaced panels leave disconnected entries behind — prune them here (1 Hz is
           nothing; the list must not grow with every mount). */
        for (let i = badges.length - 1; i >= 0; i -= 1) {
            if (!badges[i] || !badges[i].isConnected) badges.splice(i, 1);
        }
        const t = text();
        badges.forEach((el) => {
            if (!el || !el.isConnected) return;
            el.textContent = t || '— · —';
            el.classList.toggle('on', !!t);
        });
    }

    window.OFAPCURSOR = {
        state: state,
        text: text,
        set: (price, opts) => publish(Object.assign({ price: price }, opts || {})),
        move: (price, timeMs, source) => publish({ price: price, timeMs: timeMs, source: source }),
        select: (selection, opts) => publish(Object.assign({ selection: selection }, opts || {})),
        clear: clear,
        /* Returns the way out, like every other subscribe in this suite. */
        subscribe: (fn) => {
            subs.push(fn);
            return function unsubscribe() {
                const at = subs.indexOf(fn);
                if (at >= 0) subs.splice(at, 1);
            };
        },
        badge: badge,
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
        /* The ladder's lesson, shared: a grid step is the only honest tolerance for "at this level". */
        step: (prices) => {
            const sorted = (prices || []).slice().sort((a, b) => a - b);
            let step = Infinity;
            for (let i = 1; i < sorted.length; i += 1) {
                const d = sorted[i] - sorted[i - 1];
                if (d > 0 && d < step) step = d;
            }
            return Number.isFinite(step) ? step : null;
        },
    };
})();
