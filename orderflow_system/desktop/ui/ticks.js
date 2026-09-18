/* ticks.js (§90) — make a live value LOOK live: direction, colour, flash.
 *
 * The program's numbers all change, but most of them changed *silently* — a delta that ticks up
 * and a delta that ticks down looked identical between repaints. This module is the one place
 * that decides what a change looks like: a slanted arrow in the direction of the move, a
 * green/red tint that holds until the next move, and a short flash on every change. The element
 * remembers its own previous reading (data-tick-prev), so callers just hand in the new value —
 * no caller keeps state, no two callers disagree about direction.
 */
(function () {
    'use strict';

    var UP = '\u2197', DOWN = '\u2198', FLAT = '\u00b7';

    /* Direction of a display value, from its text or number. Unreadable or equal values are ''. */
    function dir(prev, next) {
        var clean = function (v) { return String(v == null ? '' : v).replace(/[^0-9.\-]/g, ''); };
        var ca = clean(prev), cb = clean(next);
        if (ca === '' || cb === '') return '';    // a dash or a blank is not a zero
        var a = Number(ca), b = Number(cb);
        if (!isFinite(a) || !isFinite(b) || a === b) return '';
        return b > a ? 'up' : 'down';
    }

    /* Apply the reading to an element: tint + flash on change, optional arrow prefix.
       opts.arrow (default true for numbers) prefixes \u2197/\u2198/\u00b7. Returns the direction. */
    function tick(el, text, opts) {
        opts = opts || {};
        if (!el) return '';
        var prev = (el.dataset && 'tickPrev' in el.dataset) ? el.dataset.tickPrev : null;
        var d = prev == null ? '' : dir(prev, text);
        var body = String(text == null ? '' : text);
        if (el.dataset) el.dataset.tickPrev = body;
        if (d) {
            el.classList.remove('tick-up', 'tick-down');
            void el.offsetWidth;                     // restart the flash on every change
            el.classList.add(d === 'up' ? 'tick-up' : 'tick-down');
        }
        var face = opts.arrow ? ((d === 'up' ? UP : d === 'down' ? DOWN : FLAT) + ' ' + body) : body;
        if (el.textContent !== face) el.textContent = face;
        return d;
    }

    /* A one-shot arrival flash for freshly inserted cards/rows (signals, tiles). */
    function arrival(el) {
        if (!el || !el.classList) return;
        el.classList.remove('tick-in');
        void el.offsetWidth;
        el.classList.add('tick-in');
    }

    var API = { dir: dir, tick: tick, arrival: arrival, UP: UP, DOWN: DOWN, FLAT: FLAT };
    if (typeof window !== 'undefined') window.OFAPTICK = API;
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
