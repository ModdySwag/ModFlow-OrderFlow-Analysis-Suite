/* navreturn.js — "Back to <where you were>": the way home from a context jump.
 *
 * The rule this module exists for: when a control sends the reader somewhere ELSE to finish a
 * task — a panel button opening the Help Centre, the Engine's look-up sending a new symbol to the
 * Instruments view, a menu row asking you to check the feed or link a platform, a heatmap region
 * handed to Replay — the destination carries a small "Back" control that returns to where the
 * jump started, positioned first in the view's head (the place the eye already is).
 *
 * Deliberately narrow, so ordinary navigation stays ordinary:
 *  - the chip appears ONLY after a registered jump (`OFAPNAV.jump(to)`) or any route INTO help —
 *    opening Help is always a context transfer: you pause to read, then want your board back;
 *  - a plain view switch (rail click, palette, hash) clears it — the user navigated on purpose;
 *  - ONE slot of history, not a stack: a back button that remembers ten jumps is a browser, not
 *    a trading panel;
 *  - the chip never blocks, never moves controls, and never survives the return click.
 *
 * The pure half (`_decide`) is pinned by navreturn.selftest.js; the DOM half wraps
 * `window.showView` — loaded after every other wrapper, so it sees each call once.
 */
(function () {
    'use strict';

    const STATE = { pending: null, armed: '' };

    const hasDom = typeof document !== 'undefined' && !!document.createElement;
    const $ = (s) => (hasDom ? document.querySelector(s) : null);

    /* ── the pure half ────────────────────────────────────────────────────────────────────── */

    /* One transition of the single slot. `ev`: {kind: 'jump' | 'navigate' | 'back', from, to,
       backLabel}. `help` is treated as a context transfer from ANY view; registered jumps
       (`kind: 'jump'`) record themselves; everything else clears. */
    function _decide(pending, ev) {
        if (!ev) return pending;
        if (ev.kind === 'back') return null;
        if (!ev.to) return pending;
        if (ev.kind === 'jump') {
            if (!ev.from || ev.from === ev.to) return pending;
            return { back: ev.from, backLabel: ev.backLabel || ev.from, to: ev.to };
        }
        /* kind === 'navigate' */
        if (ev.to === 'help' && ev.from && ev.from !== 'help') {
            return { back: ev.from, backLabel: ev.backLabel || ev.from, to: 'help' };
        }
        if (pending && ev.to === pending.to) return pending;   // the jump's own showView call
        return null;
    }

    /* ── the DOM half ─────────────────────────────────────────────────────────────────────── */

    function currentView() {
        const a = $('.view.active');
        return a && a.dataset ? String(a.dataset.view || '') : '';
    }

    /* The rail's own words for a view ("Engine", "Heatmap", …) — the label the reader knows. */
    function labelOf(view) {
        try {
            const b = document.querySelector('.rail .nav-item[data-view="' + view + '"]');
            if (b) return (b.textContent || '').replace(/\s+/g, ' ').trim().replace(/^\W+/, '') || view;
        } catch (e) { /* fall through */ }
        try {
            const a = document.querySelector('.view[data-view="' + view + '"] .view-title');
            if (a) return (a.textContent || '').trim() || view;
        } catch (e) { /* fall through */ }
        return view;
    }

    function chip() { return $('[data-nav-return]'); }

    function paint() {
        if (!hasDom) return;
        const p = STATE.pending;
        const here = currentView();
        let el = chip();
        const wanted = !!(p && p.back && p.back !== here && here === p.to);
        if (!wanted) {
            if (el) el.remove();
            return;
        }
        const head = $('.view[data-view="' + here + '"] .view-head');
        if (!head) return;
        if (!el) {
            el = document.createElement('button');
            el.type = 'button';
            el.className = 'nav-back';
            el.setAttribute('data-nav-return', '1');
            head.insertBefore(el, head.firstChild);
        }
        const label = p.backLabel || labelOf(p.back);
        el.innerHTML = '\u2190 <span class="nav-back-where">Back to ' + label.replace(/[&<>"]/g, '') + '</span>';
        el.title = 'Return to ' + label;
    }

    function back() {
        const p = STATE.pending;
        STATE.pending = null;
        STATE.armed = '';
        paint();
        if (p && p.back && typeof window.showView === 'function') window.showView(p.back);
    }

    /* A registered context jump: remember the origin, then hand over to the normal switch. */
    function jump(to, backLabel) {
        const from = currentView();
        if (!to || typeof window.showView !== 'function') return false;
        if (String(to) === from) { window.showView(to); return false; }
        STATE.pending = _decide(STATE.pending, {
            kind: 'jump', from: from, to: String(to), backLabel: backLabel || labelOf(from),
        });
        STATE.armed = String(to);
        window.showView(to);
        setTimeout(paint, 60);
        return true;
    }

    function install() {
        if (!hasDom || typeof window.showView !== 'function') return false;
        const base = window.showView;
        if (base.__ofapNavWrapped) return true;
        const wrapped = function (name) {
            const from = currentView();
            const to = name == null ? '' : String(name);
            if (to && to !== from) {
                if (STATE.armed === to) STATE.armed = '';
                else {
                    STATE.pending = _decide(STATE.pending, {
                        kind: 'navigate', from: from, to: to, backLabel: labelOf(from),
                    });
                }
            }
            const r = base.apply(this, arguments);
            setTimeout(paint, 80);
            return r;
        };
        wrapped.__ofapNavWrapped = true;
        window.showView = wrapped;
        document.addEventListener('click', function (ev) {
            const b = ev.target && ev.target.closest ? ev.target.closest('[data-nav-return]') : null;
            if (b) { ev.preventDefault(); back(); }
        });
        setTimeout(paint, 200);
        return true;
    }

    if (hasDom) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
        else install();
        /* The shell boots late in some flows (terminal layouts); retry until the wrap lands. */
        let tries = 0;
        const late = () => {
            if (window.showView && !window.showView.__ofapNavWrapped) { install(); if (window.showView.__ofapNavWrapped) return; }
            if ((tries += 1) < 60) setTimeout(late, 250);
        };
        if (window.showView && !window.showView.__ofapNavWrapped) setTimeout(late, 1);
    }

    window.OFAPNAV = {
        jump: jump,
        back: back,
        state: function () {
            return { pending: STATE.pending ? { back: STATE.pending.back, to: STATE.pending.to } : null, here: currentView() };
        },
        _decide: _decide,
        _paint: paint,
    };
}());
