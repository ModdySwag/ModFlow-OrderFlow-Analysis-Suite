/* windows-ui.js — widget windows (§73): one panel per native window, on any monitor.
 *
 * The shell owns the terminal bar and hands this module a span (`OFAPWINDOWS.attach`); everything
 * native — which screens exist, what is open, pinning, closing — comes from
 * `/api/control/windows`. In a browser (or a headless session) that endpoint answers
 * `native: false`, and this module then draws NOTHING at all: a control that cannot work is worse
 * than no control.
 *
 * The menu is built from a pure model (`OFAPWINDOWS.model`) so the decisions — which rows, which
 * labels, what is disabled — are unit-tested in Node (windows-ui.selftest.js) and the DOM code here
 * only renders them.
 */
(function () {
    'use strict';

    const API = '/api/control/windows';
    const hasDom = typeof document !== 'undefined' && !!document.createElement;

    const S = {
        state: null,          // the last /api/control/windows answer
        host: null,           // the span the shell gave us (terminal bar)
        top: null,            // the app's own top bar span (classic mode)
        aux: null,            // { id } when this page IS an auxiliary window
        anchor: null,         // the element the open menu hangs from
        error: '',
        menu: null,           // the open menu element
    };

    /* ── the pure model: what the menu should offer, given the state ─────────────────────────── */

    function model(state, focus) {
        const st = state && typeof state === 'object' ? state : {};
        const rows = [];
        if (!st.native) return rows;
        const open = Array.isArray(st.open) ? st.open : [];
        const stored = Array.isArray(st.windows) ? st.windows : [];
        const screens = Array.isArray(st.screens) ? st.screens : [];
        const target = String(focus || '').trim().toLowerCase();
        const max = Number(st.max) || 8;

        if (open.length) {
            rows.push({ kind: 'head', label: open.length + ' window' + (open.length === 1 ? '' : 's') + ' open' });
            open.forEach(function (id) {
                const row = stored.filter(function (r) { return r.id === id; })[0] || { id: id };
                rows.push({ kind: 'open', id: id, view: row.view || '',
                            on_top: !!row.on_top,
                            label: '⧉ ' + String(row.view || 'window').toUpperCase() });
            });
            rows.push({ kind: 'sep', label: '' });
            rows.push({ kind: 'close_all', label: 'Close every widget window' });
            rows.push({ kind: 'sep', label: '' });
        }

        if (!target) {
            rows.push({ kind: 'note', label: 'Focus a widget first (click its title bar)' });
            return rows;
        }
        const atCapacity = open.length >= max;
        rows.push({ kind: 'open_new', view: target, disabled: atCapacity,
                    label: 'Open ' + target.toUpperCase() + ' in its own window',
                    note: atCapacity ? 'window limit reached (' + max + ')' : '' });
        if (screens.length) {
            rows.push({ kind: 'head', label: 'Send ' + target.toUpperCase() + ' to' });
            screens.forEach(function (screen) {
                rows.push({ kind: 'screen', view: target, screen: Number(screen.index) || 0,
                            disabled: atCapacity,
                            label: screen.label || ('Monitor ' + ((Number(screen.index) || 0) + 1)) });
            });
        }
        return rows;
    }

    /* ── the wire ────────────────────────────────────────────────────────────────────────────── */

    function call(body) {
        const opts = body ? { method: 'POST', body: body } : {};
        let promise;
        if (typeof window.api === 'function') {
            promise = window.api(API, opts);
        } else {
            promise = fetch(API, {
                method: body ? 'POST' : 'GET',
                headers: { 'Content-Type': 'application/json' },
                body: body ? JSON.stringify(body) : undefined,
            }).then(function (res) { return res.json(); });
        }
        return promise.then(function (out) {
            S.error = (out && out.ok === false && out.error) ? String(out.error) : '';
            S.state = out && out.native !== undefined ? out : { native: false };
            return out;
        }).catch(function (e) {
            S.error = String((e && e.message) || e);
            S.state = { native: false };
            return { ok: false, native: false, error: S.error };
        });
    }

    function refresh() {
        return call(null).then(function () { paint(); return S.state; });
    }

    function focused() {
        /* Terminal mode has a focus; Classic mode does not, and the honest answer there is "the
           view you are looking at" — so the menu can always offer to detach *something*. */
        if (window.OFAPSHELL && typeof OFAPSHELL.state === 'function') {
            const st = OFAPSHELL.state() || {};
            if (st.mode === 'terminal' || st.mode === undefined) {
                if (st.focus) return String(st.focus);
                const placed = st.placed || [];
                if (placed.length) return String(placed[0]);
                if (st.mode === 'terminal') return '';
            }
        }
        const hash = String((window.location && window.location.hash) || '').slice(1);
        if (/^[a-z][a-z0-9_-]{0,23}$/.test(hash)) return hash;
        const active = document.querySelector('section.view.active[data-view]');
        const view = active && active.getAttribute('data-view');
        return String(view || 'overview');
    }

    /* ── the DOM ─────────────────────────────────────────────────────────────────────────────── */

    function button(text, cls, tip, run) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'win-btn ' + (cls || '');
        btn.textContent = text;
        if (tip) btn.title = tip;
        btn.onclick = function (ev) {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            run(btn);
        };
        return btn;
    }

    function rowsFor(el, rows, onDone) {
        rows.forEach(function (row) {
            if (row.kind === 'sep') {
                const sep = document.createElement('div');
                sep.className = 'win-sep';
                el.appendChild(sep);
                return;
            }
            if (row.kind === 'head') {
                const head = document.createElement('div');
                head.className = 'win-head';
                head.textContent = row.label;
                el.appendChild(head);
                return;
            }
            if (row.kind === 'note') {
                const note = document.createElement('div');
                note.className = 'win-note';
                note.textContent = row.label;
                el.appendChild(note);
                return;
            }
            if (row.kind === 'open') {
                const line = document.createElement('div');
                line.className = 'win-line';
                line.appendChild(button(row.label, 'win-row win-focus', 'Show this window', function () {
                    return call({ action: 'focus', id: row.id }).then(onDone);
                }));
                line.appendChild(button(row.on_top ? '📌' : '📍', 'win-pin', row.on_top ? 'Unpin (no longer always on top)' : 'Pin: always on top',
                    function () {
                        return call({ action: 'ontop', id: row.id, on_top: !row.on_top }).then(onDone);
                    }));
                line.appendChild(button('×', 'win-x', 'Close this window', function () {
                    return call({ action: 'close', id: row.id }).then(onDone);
                }));
                el.appendChild(line);
                return;
            }
            if (row.kind === 'close_all') {
                el.appendChild(button(row.label, 'win-row win-quiet', 'Close every widget window', function () {
                    return call({ action: 'close_all' }).then(onDone);
                }));
                return;
            }
            if (row.kind === 'screen') {
                const btn = button(row.label, 'win-row', 'Open there', function () {
                    return call({ action: 'open', view: row.view, screen: row.screen }).then(onDone);
                });
                btn.disabled = !!row.disabled;
                el.appendChild(btn);
                return;
            }
            if (row.kind === 'open_new') {
                const btn = button(row.label + (row.note ? ' — ' + row.note : ''), 'win-row win-go', '', function () {
                    return call({ action: 'open', view: row.view }).then(onDone);
                });
                btn.disabled = !!row.disabled;
                el.appendChild(btn);
            }
        });
    }

    function closeMenu() {
        /* C-07: the away listener is part of the menu — removing the menu removes it too. */
        if (S.away) { document.removeEventListener('click', S.away, true); S.away = null; }
        if (S.menu && S.menu.parentNode) S.menu.parentNode.removeChild(S.menu);
        S.menu = null;
    }

    function openMenu(anchor) {
        closeMenu();
        S.anchor = anchor || S.anchor;
        const menu = document.createElement('div');
        menu.className = 'win-menu';
        const box = (S.anchor && S.anchor.getBoundingClientRect)
            ? S.anchor.getBoundingClientRect() : { left: 40, bottom: 40 };
        menu.style.left = Math.max(8, Math.round(box.left)) + 'px';
        menu.style.top = Math.round(box.bottom + 6) + 'px';
        const rebuild = function () {
            menu.textContent = '';
            rowsFor(menu, model(S.state, focused()), rebuild);
            if (S.error) {
                const err = document.createElement('div');
                err.className = 'win-err';
                err.textContent = '⚠ ' + S.error;
                menu.appendChild(err);
            }
        };
        rebuild();
        document.body.appendChild(menu);
        S.menu = menu;
        const away = function (ev) {
            if (S.menu && !S.menu.contains(ev.target) && ev.target !== S.anchor) closeMenu();
        };
        S.away = away;
        document.addEventListener('click', away, true);
        return menu;
    }

    function paint() {
        const state = S.state || { native: false };
        if (S.host) {
            S.host.textContent = '';
            if (S.aux) {
                /* The auxiliary window's own bar: what this window is, whether it is pinned, and
                   the one thing a window must always offer — a way to close itself. */
                if (state.native) {
                    const row = (state.windows || []).filter(function (r) { return r.id === S.aux.id; })[0] || {};
                    S.host.appendChild(button(row.on_top ? '📌 pinned' : '📍 pin', 'win-pin',
                        'Always on top (a widget that stays visible while you work elsewhere)', function () {
                            return call({ action: 'ontop', id: S.aux.id, on_top: !row.on_top }).then(paint);
                        }));
                    S.host.appendChild(button('× Close', 'win-x', 'Close this widget window', function () {
                        return call({ action: 'close', id: S.aux.id }).then(function () {
                            /* the host destroys the window; if it could not, say so rather than lie */
                            if (S.error) paint();
                        });
                    }));
                    if (S.error) {
                        const err = document.createElement('span');
                        err.className = 'win-err';
                        err.textContent = '⚠ ' + S.error;
                        S.host.appendChild(err);
                    }
                }
            } else if (state.native && mode() === 'terminal') {
                S.host.appendChild(menuButton());     // the terminal bar's copy
            }
        }
        if (S.top) {
            /* Classic mode's copy lives in the app's own top bar, and exactly one is ever drawn:
               the bar that exists depends on the mode, not on where the user looked last. */
            S.top.textContent = '';
            if (state.native && !S.aux && mode() !== 'terminal') S.top.appendChild(menuButton());
        }
    }

    function mode() {
        if (window.OFAPSHELL && typeof OFAPSHELL.mode === 'function') return String(OFAPSHELL.mode() || '');
        return 'classic';
    }

    function menuButton() {
        const count = ((S.state || {}).open || []).length;
        return button('⧉ ' + (count ? 'Windows · ' + count : 'Windows'), 'win-open',
            'Widget windows: one panel per native window, on any monitor',
            function (ev) {
                if (ev && ev.stopPropagation) ev.stopPropagation();
                if (S.menu) { closeMenu(); return; }
                openMenu(ev && ev.currentTarget ? ev.currentTarget : (S.host || S.top));
                void refresh().then(function () { if (S.menu && S.anchor) openMenu(S.anchor); });
            });
    }

    /* ── the seam the shell uses ─────────────────────────────────────────────────────────────── */

    function attach(el, opts) {
        S.host = el || null;
        S.aux = (opts && opts.aux) ? { id: String(opts.aux.id || ''), view: String(opts.aux.view || '') } : null;
        paint();
        return refresh();
    }

    function attachTop() {
        if (!hasDom) return false;
        S.top = document.getElementById('topWins');
        return !!S.top;
    }

    window.OFAPWINDOWS = { version: '1.0.0', attach: attach, attachTop: attachTop, refresh: refresh,
        model: model, state: S, call: call };

    if (hasDom) {
        /* The menu is rebuilt whenever it opens (and after every action), so a refresh here is
           enough — a fetch per page click would be a per-click round trip for nothing. The shell
           announces every mode switch, which is when the control moves between the two bars. */
        document.addEventListener('ofap:relayout', function () { if (S.menu) closeMenu(); });
        document.addEventListener('ofap:shell', function () { if (S.menu) closeMenu(); paint(); });
        attachTop();
        void refresh();
    }
})();
