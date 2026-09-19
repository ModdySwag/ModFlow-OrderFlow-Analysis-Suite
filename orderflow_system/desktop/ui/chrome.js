/* chrome.js (§91) — show/hide the program's frame: the top menu bar, the side rail, the status
 * bar. The View menu and the keyboard drive the same toggles, the choice is remembered per
 * browser so a parked frame stays parked across a reload, and hiding the menu bar can never trap
 * you: **B** brings it back (and the ☰ menu and the shortcut sheet stay reachable — both live in
 * the top bar below it). Zen (full screen) stays the one-shot that hides everything at once.
 */
(function () {
    'use strict';

    const KEY = 'ofap.chrome';
    const MAP = { menubar: 'menubar-hidden', rail: 'rail-hidden', status: 'status-hidden' };

    function app() {
        return (typeof document !== 'undefined' && document.querySelector)
            ? document.querySelector('.app') : null;
    }
    function read() {
        try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
    }
    function write(state) {
        try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* private mode */ }
    }
    function hidden(which) {
        const a = app();
        return !!(a && MAP[which] && a.classList.contains(MAP[which]));
    }
    function apply(which, on, remember) {
        const a = app();
        if (!a || !MAP[which]) return false;
        a.classList.toggle(MAP[which], !!on);
        /* The persistent toggles keep their pressed faces honest. They live in the topbar, which
           never hides with either bar — the lesson the rail taught: a control must not vanish
           with the thing it controls. */
        var TOGGLES = { rail: '#railToggle', menubar: '#menubarToggle' };
        var GLYPHS = { rail: ['\u21e4', '\u21e5'] };                   // [visible, hidden]
        var WORDS = { menubar: ['menu hide', 'menu show'] };           // §94 — the label IS the face
        var tgl = TOGGLES[which] ? document.querySelector(TOGGLES[which]) : null;
        if (tgl) {
            tgl.setAttribute('aria-pressed', String(!!on));
            tgl.classList.toggle('on', !!on);
            /* Directional face: what pressing it will DO, said on the control itself (owner's
               note). The rail keeps a glyph; the menu-bar toggle (§94) says it in words — no
               caret (the owner read the bare glyph as decoration). */
            var glyph = GLYPHS[which];
            if (glyph) tgl.textContent = glyph[on ? 1 : 0];
            var words = WORDS[which];
            if (words) tgl.textContent = words[on ? 1 : 0];
            tgl.title = (on ? 'Show' : 'Hide') + (which === 'rail' ? ' the side rail (R)' : ' the top menu bar (B)');
        }
        if (remember !== false) { const s = read(); s[which] = !!on; write(s); }
        if (typeof document !== 'undefined' && document.dispatchEvent) {
            document.dispatchEvent(new CustomEvent('ofap:chrome', { detail: { which: which, hidden: !!on } }));
        }
        return !!on;
    }
    function toggle(which) { return apply(which, !hidden(which)); }
    function zen(on) {
        const a = app();
        if (!a) return false;
        if (on === undefined) a.classList.toggle('zen');
        else a.classList.toggle('zen', !!on);
        return a.classList.contains('zen');
    }
    function restore() {
        const s = read();
        Object.keys(MAP).forEach(function (w) { if (s[w]) apply(w, true, false); });
    }
    function wire() {
        restore();
        /* §92: the physical controls — a hide button on each bar, a reveal button for each that
           exists only while its bar is hidden (never a dead control). */
        [['#mbHide', 'menubar'], ['#menubarToggle', 'menubar'],
         ['#railToggle', 'rail'], ['#railHide', 'rail'], ['#railReveal', 'rail']].forEach(function (pair) {
            var el = document.querySelector(pair[0]);
            if (el) el.addEventListener('click', function () { toggle(pair[1]); });
        });
        /* T5/A10: double-clicking a card's head folds that card — the study's collapsed-state
           pattern, session-only on purpose (a collapse is a reading posture, not a setting). */
        document.addEventListener('dblclick', function (ev) {
            var head = ev.target && ev.target.closest ? ev.target.closest('.card-head') : null;
            if (!head) return;
            if (ev.target.closest('button, input, select, a')) return;   // controls keep their clicks
            var card = head.closest('.card');
            if (card) card.classList.toggle('card-collapsed');
        });
        if (window.OFAPKEYS && OFAPKEYS.annotate) OFAPKEYS.annotate();
        if (window.OFAPKEYS) {
            OFAPKEYS.bind({ id: 'chrome-menubar', keys: ['b'], scope: 'Global',
                label: 'hide / show the top menu bar', run: function () { toggle('menubar'); } });
            OFAPKEYS.bind({ id: 'chrome-rail', keys: ['r'], scope: 'Global',
                label: 'hide / show the side rail', run: function () { toggle('rail'); } });
        }
    }

    const API = { MAP: MAP, hidden: hidden, apply: apply, toggle: toggle, zen: zen, restore: restore };
    if (typeof window !== 'undefined') {
        window.OFAPCHROME = API;
        if (typeof document !== 'undefined') {
            if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
            else wire();
        }
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
