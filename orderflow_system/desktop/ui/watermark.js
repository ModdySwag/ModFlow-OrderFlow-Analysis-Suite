/* watermark.js — T4/A9: the canvas watermark — instrument · view · mode.
 *
 * The field's small honesty habit (and NinjaTrader's dynamic titles): a screenshot, a replay still
 * or a terminal-mode montage should say what it is without the reader guessing. One faint label per
 * canvas card, kept current from the two live sources — the topbar instrument select and the
 * shell's mode — and hidden outright when no instrument is readable, because a watermark that
 * invents a symbol is worse than none.
 */
(function () {
    'use strict';

    var VIEWS = ['heatmap', 'ofx', 'profile', 'cvd', 'chart'];

    function symbol() {
        var sel = document.getElementById('symbolSelect');
        return (sel && sel.value) ? String(sel.value) : '';
    }

    function mode() {
        var shell = window.OFAPSHELL;
        var state = shell && typeof shell.state === 'function' ? (shell.state() || {}) : {};
        var m = state.mode === 'terminal' ? 'terminal' : 'classic';
        var held = !!(window.OFAPPause && OFAPPause.isPaused && OFAPPause.isPaused());
        return held ? m + ' · held' : m;
    }

    function label(view) {
        var title = document.querySelector('.view[data-view="' + view + '"] .view-title');
        var name = title ? (title.textContent || '').trim() : view;
        var sym = symbol();
        return (sym ? sym + ' · ' : '') + name + ' · ' + mode();
    }

    function paint() {
        VIEWS.forEach(function (view) {
            var section = document.querySelector('.view[data-view="' + view + '"]');
            if (!section) return;
            var card = section.querySelector('.card');
            if (!card) return;
            var el = card.querySelector('.ofap-watermark');
            if (!el) {
                el = document.createElement('span');
                el.className = 'ofap-watermark';
                card.appendChild(el);
                try { if (window.getComputedStyle && getComputedStyle(card).position === 'static') card.style.position = 'relative'; }
                catch (e) { /* position is cosmetic; the label still paints */ }
            }
            el.textContent = label(view);
            el.hidden = !symbol();
        });
    }

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', paint);
        else paint();
        document.addEventListener('ofap:relayout', paint);
        if (typeof setInterval === 'function') setInterval(paint, 2000);
    }
    window.OFAPWATERMARK = { paint: paint, label: label, VIEWS: VIEWS };
})();
