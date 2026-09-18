/* freeze.js — T4/A7: freeze-on-hover for the canvases.
 *
 * NinjaTrader's static ladder is the study's cleanest inspect-without-chasing pattern: hovering a
 * moving surface suspends it — visibly frozen — so a readout can be examined against a still
 * picture. The mechanism here is the smallest honest one: hovering a listed canvas section suspends
 * that view's REPAINT (the painters ask `OFAPFREEZE.holds(el)` or `held(view)` before drawing).
 * Payloads that arrive while frozen are not queued and not replayed — the newest state paints on
 * the tick after the pointer leaves, which is what “suspended” means for a live surface. Hover
 * readouts (DOM rows) keep updating; only the drawing pauses.
 */
(function () {
    'use strict';

    /* The sections whose canvases repaint continuously. The small sparklines (market pressure,
       tick strips) are deliberately not listed: nothing there moves under the pointer. */
    var SECTIONS = ['heatmap', 'ofx', 'profile', 'cvd'];

    var hover = Object.create(null);
    var chips = Object.create(null);

    function held(view) { return !!hover[String(view || '')]; }

    /* Painters call this with their canvas: freeze is decided by the section the canvas lives in. */
    function holds(el) {
        if (!el || typeof el.closest !== 'function') return false;
        var section = el.closest('.view[data-view]');
        if (!section) return false;
        return held(section.getAttribute('data-view'));
    }

    function paintChip(view, on) {
        var section = document.querySelector('.view[data-view="' + view + '"]');
        if (!section) return;
        var head = section.querySelector('.view-head');
        if (!head) return;
        var chip = chips[view];
        if (!chip || !chip.isConnected) {
            chip = document.createElement('span');
            chip.className = 'ofap-freeze-chip';
            chip.textContent = 'frozen — move away to resume';
            head.appendChild(chip);
            chips[view] = chip;
        }
        chip.hidden = !on;
    }

    function set(view, on) {
        hover[view] = !!on;
        var section = document.querySelector('.view[data-view="' + view + '"]');
        if (section) section.classList.toggle('ofap-frozen', !!on);
        paintChip(view, !!on);
    }

    function wire() {
        SECTIONS.forEach(function (view) {
            var section = document.querySelector('.view[data-view="' + view + '"]');
            if (!section || section.dataset.ofapFreezeWired) return;
            section.dataset.ofapFreezeWired = '1';
            section.addEventListener('mouseenter', function () { set(view, true); });
            section.addEventListener('mouseleave', function () { set(view, false); });
            paintChip(view, false);
        });
    }

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
        else wire();
        /* A relayout reparents sections (terminal mode); the listeners ride along, chips are re-made. */
        document.addEventListener('ofap:relayout', wire);
    }

    window.OFAPFREEZE = { holds: holds, held: held, set: set, sections: SECTIONS, state: hover };
})();
