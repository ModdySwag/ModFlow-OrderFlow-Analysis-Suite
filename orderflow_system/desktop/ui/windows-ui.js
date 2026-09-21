/* windows-ui.js — widget windows (§73): one panel per native window, on any monitor.
 *
 * The shell owns the terminal bar and hands this module a span (`OFAPWINDOWS.attach`); everything
 * native — which screens exist, what is open, where each window IS, pinning, moving, closing —
 * comes from `/api/control/windows`. In a browser (or a headless session) that endpoint answers
 * `native: false`, and this module then draws NOTHING at all: a control that cannot work is worse
 * than no control.
 *
 * §128 — the multi-monitor half. An open window can be SENT to any monitor, or SNAPPED to a shape
 * on the one it is already on, from this menu and from the Windows & layouts dialog; a window whose
 * monitor is gone is offered a way home. There is no OS-level drag to be had (WebView2 cannot start
 * a window drag from inside the page), so the commands are the drag — one click each.
 *
 * The menu is built from a pure model (`OFAPWINDOWS.model`) so the decisions — which rows, which
 * labels, what is disabled, what the target widget is offered — are unit-tested in Node
 * (windows-ui.selftest.js) and the DOM code here only renders them.
 */
(function () {
    'use strict';

    const API = '/api/control/windows';
    const hasDom = typeof document !== 'undefined' && !!document.createElement;

    /*: The snap shapes, in the order the submenu offers them. This list must equal
        `windows.PRESETS` on the server (test_windowing_ui.py pins the equality): a shape the menu
        shows that the API cannot resolve would be a button that does nothing. */
    const PRESETS = ['left', 'right', 'top', 'bottom',
                     'topleft', 'topright', 'bottomleft', 'bottomright', 'fill', 'center'];
    const PRESET_LABELS = {
        left: '◧ Left half', right: '◨ Right half', top: '⬒ Top half', bottom: '⬓ Bottom half',
        topleft: '◰ Top-left', topright: '◳ Top-right',
        bottomleft: '◱ Bottom-left', bottomright: '◲ Bottom-right',
        fill: '⛶ Fill the monitor', center: '⤢ Centre, keeping its size',
    };

    const S = {
        state: null,          // the last /api/control/windows answer
        host: null,           // the span the shell gave us (terminal bar)
        top: null,            // the app's own top bar span (classic mode)
        aux: null,            // { id } when this page IS an auxiliary window
        anchor: null,         // the element the open menu hangs from
        error: '',
        menu: null,           // the open menu element
        sub: '',              // the open window whose send/snap panel is expanded
    };

    /* ── the pure model: what the menu should offer, given the state ─────────────────────────── */

    function byId(rows, id) {
        return (rows || []).filter(function (r) { return r && r.id === id; })[0] || null;
    }

    function geometryOf(state, id) {
        const geo = (state && state.open_geometry && typeof state.open_geometry === 'object')
            ? state.open_geometry : {};
        return geo[id] && typeof geo[id] === 'object' ? geo[id] : {};
    }

    function openRow(state, id) {
        const row = byId(state.windows, id) || { id: id };
        const here = geometryOf(state, id);
        return {
            kind: 'open', id: id, view: row.view || '', on_top: !!row.on_top,
            screen: typeof here.screen === 'number' ? here.screen : -1,
            screen_label: here.screen_label || '',
            label: '⧉ ' + String(row.view || 'window').toUpperCase(),
        };
    }

    function model(state, target, sub) {
        const st = state && typeof state === 'object' ? state : {};
        const rows = [];
        if (!st.native) return rows;
        const open = Array.isArray(st.open) ? st.open : [];
        const stored = Array.isArray(st.windows) ? st.windows : [];
        const screens = Array.isArray(st.screens) ? st.screens : [];
        const strandedIds = Array.isArray(st.stranded) ? st.stranded : [];
        const want = String(target || '').trim().toLowerCase();
        const expanded = String(sub || '').trim();

        /* One window's send/snap panel — the whole point of the menu for a trader with a second
           monitor: every monitor by name, then the shapes, one click each. */
        if (expanded && open.indexOf(expanded) !== -1) {
            const row = byId(stored, expanded) || { id: expanded };
            const here = geometryOf(st, expanded);
            rows.push({ kind: 'sub_back', label: '‹ all windows' });
            rows.push({ kind: 'head', label: 'Send ' + String(row.view || 'this window').toUpperCase() + ' to' });
            if (!screens.length) {
                rows.push({ kind: 'note', label: 'no monitors reported' });
            }
            screens.forEach(function (screen) {
                const index = Number(screen.index) || 0;
                rows.push({ kind: 'send_screen', id: expanded, screen: index,
                            current: Number(here.screen) === index,
                            label: screen.label || ('Monitor ' + (index + 1)) });
            });
            rows.push({ kind: 'sep', label: '' });
            rows.push({ kind: 'head', label: 'Snap it on ' + (here.screen_label || 'its monitor') });
            PRESETS.forEach(function (preset) {
                rows.push({ kind: 'send_preset', id: expanded, preset: preset,
                            label: PRESET_LABELS[preset] || preset });
            });
            rows.push({ kind: 'sep', label: '' });
            rows.push({ kind: 'dialog', label: 'Windows & layouts…' });
            return rows;
        }

        if (open.length) {
            rows.push({ kind: 'head', label: open.length + ' window' + (open.length === 1 ? '' : 's') + ' open' });
            open.forEach(function (id) { rows.push(openRow(st, id)); });
            rows.push({ kind: 'sep', label: '' });
            rows.push({ kind: 'close_all', label: 'Close every widget window' });
            rows.push({ kind: 'sep', label: '' });
        }

        if (strandedIds.length) {
            rows.push({ kind: 'note',
                        label: '⚠ ' + strandedIds.length + ' window' + (strandedIds.length === 1 ? ' is' : 's are')
                            + ' on a monitor that is gone' });
            rows.push({ kind: 'arrange',
                        label: 'Bring ' + (strandedIds.length === 1 ? 'it' : 'them') + ' home' });
            rows.push({ kind: 'sep', label: '' });
        }

        if (!want) {
            rows.push({ kind: 'note', label: 'Focus a widget first (click its title bar)' });
            rows.push({ kind: 'dialog', label: 'Windows & layouts…' });
            return rows;
        }
        const mine = open.map(function (id) { return byId(stored, id) || { id: id }; })
            .filter(function (r) { return r.view === want; })[0];
        if (mine) {
            rows.push({ kind: 'note', label: String(want).toUpperCase()
                + ' is open — ⇥ sends it to a monitor and snaps it' });
            rows.push({ kind: 'dialog', label: 'Windows & layouts…' });
            return rows;
        }
        const max = Number(st.max) || 8;
        const atCapacity = open.length >= max;
        rows.push({ kind: 'open_new', view: want, disabled: atCapacity,
                    label: 'Open ' + want.toUpperCase() + ' in its own window',
                    note: atCapacity ? 'window limit reached (' + max + ')' : '' });
        if (screens.length) {
            rows.push({ kind: 'head', label: 'Send ' + want.toUpperCase() + ' to' });
            screens.forEach(function (screen) {
                rows.push({ kind: 'screen', view: want, screen: Number(screen.index) || 0,
                            disabled: atCapacity,
                            label: screen.label || ('Monitor ' + ((Number(screen.index) || 0) + 1)) });
            });
        }
        rows.push({ kind: 'dialog', label: 'Windows & layouts…' });
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
            if (row.kind === 'sub_back') {
                el.appendChild(button(row.label, 'win-row win-quiet', 'Back to the window list', function () {
                    S.sub = '';
                    onDone();
                }));
                return;
            }
            if (row.kind === 'open') {
                const line = document.createElement('div');
                line.className = 'win-line';
                const where = row.screen_label ? ' · ' + row.screen_label : '';
                line.appendChild(button(row.label + where, 'win-row win-focus', 'Show this window', function () {
                    return call({ action: 'focus', id: row.id }).then(onDone);
                }));
                line.appendChild(button('⇥', 'win-send',
                    'Send this window to a monitor, or snap it on the one it is on', function () {
                        S.sub = row.id;
                        onDone();
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
            if (row.kind === 'dialog') {
                el.appendChild(button(row.label, 'win-row win-quiet',
                    'Every window, every monitor, and the rescue actions', function () {
                        closeMenu();
                        if (window.OFAPWINMGR && OFAPWINMGR.open) OFAPWINMGR.open();
                    }));
                return;
            }
            if (row.kind === 'arrange') {
                el.appendChild(button(row.label, 'win-row win-go', 'Move every stranded window back to a live monitor', function () {
                    return call({ action: 'arrange' }).then(onDone);
                }));
                return;
            }
            if (row.kind === 'send_screen') {
                const btn = button(row.current ? row.label + ' · here' : row.label, 'win-row', 'Move it there', function () {
                    return call({ action: 'move', id: row.id, screen: row.screen }).then(onDone);
                });
                el.appendChild(btn);
                return;
            }
            if (row.kind === 'send_preset') {
                const grid = el.querySelector('.win-presets') || (function () {
                    const box = document.createElement('div');
                    box.className = 'win-presets';
                    el.appendChild(box);
                    return box;
                })();
                grid.appendChild(button(row.label, 'win-preset', 'Snap it to this shape, on its own monitor', function () {
                    return call({ action: 'move', id: row.id, preset: row.preset }).then(onDone);
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

    function openMenu(anchor, opts) {
        closeMenu();
        S.anchor = anchor || S.anchor;
        if (opts && 'sub' in opts) S.sub = String(opts.sub || '');
        const menu = document.createElement('div');
        menu.className = 'win-menu';
        const box = (S.anchor && S.anchor.getBoundingClientRect)
            ? S.anchor.getBoundingClientRect() : { left: 40, bottom: 40 };
        menu.style.left = Math.max(8, Math.round(box.left)) + 'px';
        menu.style.top = Math.round(box.bottom + 6) + 'px';
        const rebuild = function () {
            menu.textContent = '';
            rowsFor(menu, model(S.state, (opts && opts.target) || focused(), S.sub), rebuild);
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

    /* The widget-facing entry point (§128): the terminal frame's ⧉ button and the aux window's own
       bar both open the menu aimed at THEIR widget — expanded straight to that window's send/snap
       panel when it already has one, so "put this on the other monitor" is two clicks from the
       widget itself. */
    function openFor(view, anchor) {
        const name = String(view || '').trim().toLowerCase();
        const st = S.state || {};
        const open = Array.isArray(st.open) ? st.open : [];
        const mine = (Array.isArray(st.windows) ? st.windows : [])
            .filter(function (r) { return r.view === name && open.indexOf(r.id) !== -1; })[0];
        return refresh().then(function (state) {
            /* The anchor is the control the user just clicked; with none given (the hotkey) the
               menu hangs off the bar that exists in THIS mode. */
            const fallback = mode() === 'terminal' ? S.host : S.top;
            openMenu(anchor || S.anchor || fallback, { target: name, sub: mine ? mine.id : '' });
            return state;
        });
    }

    /* The hotkey's half (§128): send the focused widget's window one monitor over — opening it
       there when it has no window yet. Returns the answer so the caller can say what happened.
       With a single monitor there is no "over", and this does NOTHING (measured: the first cut
       issued a step=1 move anyway, and ONE screen made it re-centre the window the user had just
       placed by hand — a "move" that moves something is worse than a key that says nothing). */
    function sendFocused(step) {
        const view = focused();
        if (!view) return Promise.resolve(null);
        const st = S.state || {};
        const open = Array.isArray(st.open) ? st.open : [];
        const screens = Array.isArray(st.screens) ? st.screens : [];
        if (screens.length < 2) return Promise.resolve(null);   // nowhere to send it
        const mine = (Array.isArray(st.windows) ? st.windows : [])
            .filter(function (r) { return r.view === view && open.indexOf(r.id) !== -1; })[0];
        if (mine) return call({ action: 'move', id: mine.id, step: Number(step) || 1 });
        const target = (Number(step) || 1) > 0 ? 1 : screens.length - 1;
        return call({ action: 'open', view: view, screen: target, preset: 'center' });
    }

    function paint() {
        const state = S.state || { native: false };
        if (S.host) {
            S.host.textContent = '';
            if (S.aux) {
                /* The auxiliary window's own bar: what this window is, where it is, whether it is
                   pinned, how to move it, and the one thing a window must always offer — a way to
                   close itself. */
                if (state.native) {
                    const row = (state.windows || []).filter(function (r) { return r.id === S.aux.id; })[0] || {};
                    const here = geometryOf(state, S.aux.id);
                    if (here.screen_label) {
                        const where = document.createElement('span');
                        where.className = 'win-where';
                        where.textContent = here.screen_label;
                        where.title = 'The monitor this window is on right now';
                        S.host.appendChild(where);
                    }
                    S.host.appendChild(button('⇥ monitor', 'win-send',
                        'Send this window to another monitor, or snap it where it is', function (ev) {
                            if (ev && ev.stopPropagation) ev.stopPropagation();
                            if (S.menu) { closeMenu(); return; }
                            openFor(S.aux.view, ev && ev.currentTarget ? ev.currentTarget : S.host);
                        }));
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
        const stranded = ((S.state || {}).stranded || []).length;
        return button('⧉ ' + (count ? 'Windows · ' + count : 'Windows') + (stranded ? ' ⚠' : ''), 'win-open',
            'Widget windows: one panel per native window, on any monitor',
            function (ev) {
                if (ev && ev.stopPropagation) ev.stopPropagation();
                if (S.menu) { closeMenu(); return; }
                S.sub = '';
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

    window.OFAPWINDOWS = { version: '1.1.0', attach: attach, attachTop: attachTop, refresh: refresh,
        model: model, state: S, call: call, openFor: openFor, sendFocused: sendFocused,
        presets: PRESETS.slice() };

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
