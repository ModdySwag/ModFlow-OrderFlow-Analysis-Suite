/* scale.js - the one authority on "the window changed".
 *
 * Resizing, maximising, restoring from minimised, snapping, a dpr change when the window moves to
 * another monitor, and a panel that simply got shorter because the status bar appeared: they all
 * end up here. Canvas work needs three things on every one of those events - a backing store that
 * matches the CSS box at the current device pixel ratio (or the chart is soft), a redraw (or the
 * chart is stale), and a debounce (or a drag-resize paints a hundred times a second).
 *
 * Owners that can re-fit themselves register a function; everything else gets a generic fit of the
 * canvases in the visible view plus an 'ofap:relayout' event to redraw on.
 */
(function () {
    'use strict';

    const S = {
        w: 0, h: 0, dpr: 0, compact: false,
        fits: 0, paints: 0, skipped: 0, pending: false,
        last: null, reasons: [],
    };
    const fitters = {};
    let timer = 0, rafId = 0;

    const px = (v) => Math.max(0, Math.round(v || 0));

    function measure() {
        const doc = document.documentElement;
        return {
            w: doc.clientWidth || window.innerWidth || 0,
            h: doc.clientHeight || window.innerHeight || 0,
            dpr: window.devicePixelRatio || 1,
        };
    }

    function changed(m) {
        return !S.w || !S.h || S.w !== m.w || S.h !== m.h || S.dpr !== m.dpr
            || S.compact !== (m.h < 760);
    }

    /* A canvas whose CSS box and backing store disagree is either blurry (too small) or wasteful
     * (too big). Zero-sized boxes are the minimised window: skip them and remember to come back. */
    function fitCanvas(c) {
        if (!c || !c.getContext) return false;
        const w = px(c.clientWidth), h = px(c.clientHeight);
        if (!w || !h) { S.skipped += 1; S.pending = true; return false; }
        const dpr = S.dpr || 1;
        const bw = Math.round(w * dpr), bh = Math.round(h * dpr);
        if (c.width === bw && c.height === bh) return false;
        c.width = bw;
        c.height = bh;
        return true;
    }

    function fitView(scope) {
        /* §72: every visible canvas in the document, not only the active view's. In terminal mode
           several widgets are on screen at once and only the focused one carries .active — the
           others were left with stale backing stores after a window or display-scale change.
           Hidden sections and unpainted tabs have a zero box and are skipped inside fitCanvas, so
           the wider walk costs one querySelectorAll. */
        const view = scope || document;
        let touched = 0;
        view.querySelectorAll('canvas').forEach((c) => { if (fitCanvas(c)) touched += 1; });
        return touched;
    }

    function run(reason) {
        const m = measure();
        if (!m.w || !m.h) { S.pending = true; S.skipped += 1; return; }   // minimised: nothing to do yet
        S.w = m.w; S.h = m.h; S.dpr = m.dpr; S.compact = m.h < 760;
        document.documentElement.classList.toggle('ui-compact', S.compact);

        /* The engine owns its own stage; give it the real box before anything else repaints. */
        try {
            if (typeof OFX !== 'undefined' && OFX && OFX.resize) {
                const stage = document.getElementById('ofxStage');
                if (stage && stage.clientWidth && stage.clientHeight) {
                    OFX.resize(Math.round(stage.clientWidth), Math.round(stage.clientHeight) - 8);
                    S.fits += 1;
                }
            }
        } catch (e) { /* the engine reports its own faults */ }

        const touched = fitView();
        Object.keys(fitters).forEach((k) => {
            try { fitters[k](m); S.fits += 1; } catch (e) { /* one bad fitter must not stop the rest */ }
        });
        S.paints += touched;
        S.pending = false;
        S.last = { reason: reason, w: m.w, h: m.h, dpr: m.dpr, compact: S.compact, canvases: touched, at: Date.now() };
        S.reasons = S.reasons.concat([reason]).slice(-12);
        try {
            document.dispatchEvent(new CustomEvent('ofap:relayout', { detail: S.last }));
        } catch (e) { /* no CustomEvent: the canvases are already fitted */ }
    }

    function schedule(reason) {
        S.reasons = S.reasons.concat([reason]).slice(-12);
        if (timer) clearTimeout(timer);
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
            rafId = 0;
            timer = setTimeout(() => { timer = 0; run(reason); }, 90);   // a drag-resize is one fit
        });
    }

    ['resize', 'orientationchange', 'fullscreenchange', 'pageshow'].forEach((ev) => {
        window.addEventListener(ev, () => schedule(ev), { passive: true });
    });
    document.addEventListener('visibilitychange', () => {
        // restoring from minimised: sizes were zero while hidden, so force a real pass
        if (!document.hidden) schedule('visibilitychange'); else S.pending = true;
    });

    if (typeof ResizeObserver === 'function') {
        const ro = new ResizeObserver(() => schedule('resize-observer'));
        [document.documentElement, document.body].forEach((el) => { if (el) ro.observe(el); });
        const stage = document.getElementById('ofxStage');
        if (stage) ro.observe(stage);
    }

    window.OFAPScale = {
        state: S,
        register: function (name, fn) { fitters[name] = fn; return name; },
        unregister: function (name) { delete fitters[name]; },
        fit: function (reason) { run(reason || 'manual'); },
        schedule: schedule,
        fitView: fitView,
        measure: measure,
    };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => schedule('boot'));
    else schedule('boot');
})();
