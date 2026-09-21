/* heatview.js — the heatmap's viewport: what window, what rows, and WHEN.

 * §121: the map used to be a live-edge-only picture — the server always sliced the last N
 * buckets, so zoom could only change density and there was no way to look at ten minutes ago.
 * This module owns the view as data — `cols` (buckets wide), `rows` (price rows), `until`
 * (epoch ms of the window's RIGHT edge; null = live) — plus the store's bounds learned from the
 * last payload, and the pure maths every gesture rides:
 *
 *   zoomTime(view, dir, frac, now)  zoom; LIVE stays live (right edge pinned to now), a panned
 *                                   view anchors under the cursor — Bookmap's own rule
 *   zoomRows(view, dir)             vertical zoom over the row ladder
 *   panBy(view, dxPx, plotW, now)   grab-drag pan: content follows the pointer
 *   panStep(view, dir, now)         keyboard pan, dir +1 = newer
 *   snapLive(view)                  back to the live edge
 *   absorb(view, payload)           learn bucket width + the store's bounds from each payload
 *   params(view)                    { columns, rows, until } — what the loader puts on the wire
 *   label(view, now)                '4 min · live' / '4 min · 3 min back'
 *
 * heatmap-pro's applyView() writes this state into the selects (they are the zoom readout) and
 * fires the loader; atlas.js reads params() when it builds the URL. Pinned by
 * heatview.selftest.js; the server half (the `until` anchor) is pinned by test_heatmap_anchor.py.
 */
(function () {
    'use strict';

    /* One notch per step; the ends are real answers (say()), never silence. */
    const COLS = [60, 120, 180, 240, 360, 480, 720, 900];   // 1 .. 15 min at 1 s buckets
    const ROWS = [60, 100, 140, 200, 260, 320, 400];

    const state = { cols: 240, rows: 200, until: null, bucket: 1000, haveFrom: 0, haveTo: 0 };

    /* The pure half of stepping a ladder — same semantics as heatmap-pro's listStep. */
    function step(cur, dir, list) {
        const L = (list || []).map((v) => String(v));
        if (!L.length) return null;
        let i = L.indexOf(String(cur));
        if (i < 0) i = 1;
        const ni = Math.min(L.length - 1, Math.max(0, i + dir));
        return L[ni] === String(cur) ? null : L[ni];
    }

    const windowMs = (view) => Math.max(1, view.cols * view.bucket);

    /* A window of width W may sit anywhere between the store's first bucket (its START must not
       precede it) and now (its END may not pass it — the future holds no depth). */
    function clampUntil(view, until, W, now) {
        let u = Math.min(until, now);
        const floor = view.haveFrom + W;
        if (u < floor) u = floor;
        return u;
    }

    function reachedLive(view, until, now) {
        return until >= now - view.bucket / 2;
    }

    function zoomTime(view, dir, frac, now) {
        const next = step(view.cols, dir, COLS);
        if (next == null) return { moved: false, end: dir < 0 ? 'tight' : 'wide' };
        const cols2 = parseInt(next, 10);
        /* Live keeps the live edge: zooming a live map must not knock it off the feed. */
        if (view.until == null) return { moved: true, cols: cols2, until: null };
        const W = windowMs(view);
        const W2 = Math.max(1, cols2 * view.bucket);
        const f = Math.min(1, Math.max(0, frac));
        const tCursor = view.until - (1 - f) * W;        // the time under the cursor
        let until2 = tCursor + (1 - f) * W2;             // …stays under the cursor
        until2 = clampUntil(view, until2, W2, now);
        if (reachedLive(view, until2, now)) until2 = null;
        return { moved: true, cols: cols2, until: until2 };
    }

    function zoomRows(view, dir) {
        const next = step(view.rows, dir, ROWS);
        if (next == null) return { moved: false, end: dir < 0 ? 'few' : 'many' };
        return { moved: true, rows: parseInt(next, 10) };
    }

    function panBy(view, dxPx, plotW, now) {
        if (!plotW || !dxPx && dxPx !== 0) return { moved: false };
        const W = windowMs(view);
        const base = view.until == null ? now : view.until;
        let until2 = base - (dxPx / plotW) * W;          // grab: content follows the pointer
        until2 = clampUntil(view, until2, W, now);
        if (reachedLive(view, until2, now)) until2 = null;
        return { moved: true, until: until2 };
    }

    function panStep(view, dir, now) {
        const base = view.until == null ? now : view.until;
        let until2 = base + dir * view.bucket;           // dir +1 = newer
        until2 = clampUntil(view, until2, windowMs(view), now);
        if (reachedLive(view, until2, now)) until2 = null;
        return { moved: true, until: until2 };
    }

    function snapLive(view) {
        view.until = null;
        return view;
    }

    function absorb(view, d) {
        if (!d) return view;
        if (d.bucket_ms) view.bucket = d.bucket_ms;
        if (d.have_from_ms) view.haveFrom = d.have_from_ms;
        if (d.have_to_ms) view.haveTo = d.have_to_ms;
        return view;
    }

    function params(view) {
        return { columns: view.cols, rows: view.rows,
                 until: view.until == null ? 0 : Math.round(view.until) };
    }

    function minutesOf(cols, bucket) {
        const s = (cols * bucket) / 1000;
        if (s < 90) return Math.round(s) + ' s';
        return Math.round(s / 60) + ' min';
    }

    function label(view, now) {
        const w = minutesOf(view.cols, view.bucket);
        if (view.until == null) return w + ' · live';
        const back = Math.max(0, now - view.until);
        return w + ' · ' + (back < 90_000 ? Math.round(back / 1000) + ' s back'
                                          : Math.round(back / 60000) + ' min back');
    }

    window.OFAPHEATVIEW = { COLS: COLS, ROWS: ROWS, state: state, step: step,
                            zoomTime: zoomTime, zoomRows: zoomRows, panBy: panBy, panStep: panStep,
                            snapLive: snapLive, absorb: absorb, params: params,
                            minutesOf: minutesOf, label: label };
})();
