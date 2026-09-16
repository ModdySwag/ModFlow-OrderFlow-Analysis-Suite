/* keys.js — the app's one shortcut map: every keyboard binding in one place, with its scope.
 *
 * A binding is registered here — by this module (the app-core keys) or by the module that owns
 * the action (`OFAPKEYS.bind` from pause.js, search.js, menu.js, ofx-view.js, heatmap-pro.js,
 * atlas.js, shell.js, menubar.js) — and this module dispatches it from ONE document listener. The
 * hotkey sheet renders from `OFAPKEYS.list()`, so the map the user reads and the keys the app
 * honours are the same list, and a binding cannot ship undocumented.
 *
 * Keys that are scoped to hover state, a focused field or an open menu (the strips' step keys, the
 * drawing tool's Escape chain, the menu bar's walk, the palette field) stay local to their module
 * and register a display row through `OFAPKEYS.document()` — the sheet still lists them, and the
 * row names the scope they act in.
 *
 * The typing guard is this module's job, not each handler's: a key pressed while the focus is in an
 * INPUT/TEXTAREA/SELECT or a contenteditable is swallowed, unless the binding opts in with
 * `inField: true` (exactly one does: Escape still closes the menu mid-typing, which is what the ☰
 * panel always did). Space is additionally left to the browser when the focused element is a
 * button/link/summary, so it activates the control the user is standing on.
 *
 * Chord form: `[ctrl+][alt+][meta+]key`, key lowercased; shift joins the chord only when it does
 * not change the character (`shift+p` is not `p`, but `?` IS shift+/ and is spelled `?`). A binding
 * may list aliases: { keys: ['=', '+'] }.
 *
 * Scope collisions (the same chord in two views that are both on screen — Terminal mode can show
 * the engine and the heatmap at once) resolve by priority, highest wins, ties to the first
 * registered. The engine's keys register at 6, the heatmap's at 5.
 *
 * The pure half (`canonical`, `isTypingTarget`, `resolve`, `pretty`) makes no app calls and is
 * pinned by keys.selftest.js under Node, the same way the other modules pin their maths.
 */
(function () {
    'use strict';

    var map = [];        // every row: bindings (run set) and documented locals (run null)
    var recent = [];     // the last firings — {id, chord, at}; the live gates and probes read it
    var docSeq = 0;

    /* ── the pure half ─────────────────────────────────────────────────────── */

    function canonical(ev) {
        var key = String((ev && ev.key) == null ? '' : ev.key);
        if (key === ' ' || key === 'Spacebar') key = 'space';
        key = key.toLowerCase();
        var single = key.length === 1;
        /* Shift matters for letters and digits (shift+p is a different chord than p) and for named
           keys; for punctuation the character itself already carries it ('?' vs '/', '+' vs '='). */
        var shiftMatters = !single || /[a-z0-9]/.test(key);
        var mods = '';
        if (ev && ev.ctrlKey) mods += 'ctrl+';
        if (ev && ev.altKey) mods += 'alt+';
        if (ev && ev.metaKey) mods += 'meta+';
        if (ev && ev.shiftKey && shiftMatters) mods += 'shift+';
        return key ? mods + key : '';
    }

    var KEY_NAMES = {
        escape: 'Esc', space: 'Space', enter: 'Enter', tab: 'Tab', delete: 'Del',
        backspace: 'Backspace', pageup: 'PgUp', pagedown: 'PgDn', home: 'Home', end: 'End',
        arrowup: '\u2191', arrowdown: '\u2193', arrowleft: '\u2190', arrowright: '\u2192',
        f1: 'F1', f11: 'F11',
    };

    function pretty(chord) {
        var parts = String(chord).split('+');
        return parts.map(function (part, i) {
            if (i < parts.length - 1) {
                if (part === 'ctrl') return 'Ctrl';
                if (part === 'alt') return 'Alt';
                if (part === 'meta') return 'Win';
                if (part === 'shift') return 'Shift';
                return part;
            }
            if (KEY_NAMES[part]) return KEY_NAMES[part];
            if (part.length === 1) return part.toUpperCase();
            return part.charAt(0).toUpperCase() + part.slice(1);
        }).join('+');
    }

    function keysText(binding) {
        var keys = binding.keys || [];
        if (keys.length > 2 && keys.every(function (k) { return /^[1-9]$/.test(k); })) {
            return keys[0] + ' \u2026 ' + keys[keys.length - 1];
        }
        return keys.map(pretty).join(' / ');
    }

    function isTypingTarget(node) {
        if (!node) return false;
        var tag = String(node.tagName || '').toUpperCase();
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
        return Boolean(node.isContentEditable);
    }

    function isActivatible(node) {
        if (!node) return false;
        var tag = String(node.tagName || '').toUpperCase();
        return tag === 'BUTTON' || tag === 'A' || tag === 'SUMMARY';
    }

    function resolve(chord, ev, opts) {
        var inField = Boolean(opts && opts.inField);
        var best = null;
        for (var i = 0; i < map.length; i += 1) {
            var b = map[i];
            if (!b.run) continue;                                 // documented locals never dispatch
            if (b.keys.indexOf(chord) < 0) continue;
            if (inField && !b.inField) continue;
            if (b.when && !b.when(ev)) continue;
            if (!best || (b.priority || 0) > (best.priority || 0)) best = b;
        }
        return best;
    }

    /* ── registration ──────────────────────────────────────────────────────── */

    function bind(spec) {
        if (!spec || !spec.id || !spec.label || !spec.scope) {
            throw new Error('OFAPKEYS.bind: id, label and scope are required');
        }
        if (typeof spec.run !== 'function') {
            throw new Error('OFAPKEYS.bind: run must be a function for ' + spec.id);
        }
        var row = {
            id: spec.id,
            keys: Array.isArray(spec.keys) ? spec.keys.slice() : [spec.keys],
            label: spec.label,
            scope: spec.scope,
            when: spec.when || null,
            run: spec.run,
            inField: Boolean(spec.inField),
            priority: spec.priority || 0,
            owner: spec.owner || null,
            text: null,
        };
        for (var i = 0; i < map.length; i += 1) {
            /* Re-registration replaces: a view's init may legitimately run more than once. */
            if (map[i].id === spec.id) { map[i] = row; return row; }
        }
        map.push(row);
        return row;
    }

    function documentRows(rows) {
        (rows || []).forEach(function (r) {
            if (!r || !r.keys || !r.label || !r.scope) return;
            /* Idempotent by content: a re-mounted panel contributes the same rows again. */
            var dup = map.some(function (m) {
                return !m.run && m.text === r.keys && m.label === r.label && m.scope === r.scope;
            });
            if (dup) return;
            docSeq += 1;
            map.push({
                id: 'doc-' + docSeq, keys: [], label: r.label, scope: r.scope,
                when: null, run: null, inField: false, priority: 0, owner: r.owner || null,
                text: String(r.keys),
            });
        });
    }

    var SCOPE_ORDER = ['Global', 'Engine', 'Heatmap', 'Replay', 'Terminal', 'Palette', 'Strips', 'Drawings', 'Menu bar'];

    function list() {
        return map.map(function (b) {
            return {
                id: b.id, keys: b.text || keysText(b), label: b.label, scope: b.scope,
                owner: b.owner, dispatched: Boolean(b.run),
            };
        }).sort(function (a, b) {
            var ia = SCOPE_ORDER.indexOf(a.scope);
            var ib = SCOPE_ORDER.indexOf(b.scope);
            return (ia < 0 ? SCOPE_ORDER.length : ia) - (ib < 0 ? SCOPE_ORDER.length : ib);
        });
    }

    /* ── dispatch ──────────────────────────────────────────────────────────── */

    function report(id, err) {
        try {
            if (typeof reportClientError === 'function') {
                reportClientError({
                    message: 'shortcut ' + id + ' failed: ' + ((err && err.message) || err),
                    source: '/desktop/keys.js', line: 0, col: 0, stack: (err && err.stack) || '',
                });
            }
        } catch (e) { /* reportClientError's own console fallback is the last resort */ }
    }

    function dispatch(ev) {
        var chord = canonical(ev);
        if (!chord) return;
        /* Space on a focused control belongs to the browser (it activates it); never double-fire. */
        if (chord === 'space' && isActivatible(ev.target)) return;
        var inField = isTypingTarget(ev.target) || isTypingTarget(document.activeElement);
        var hit = resolve(chord, ev, { inField: inField });
        if (!hit) return;
        if (ev.preventDefault) ev.preventDefault();
        recent.push({ id: hit.id, chord: chord, at: Date.now() });
        if (recent.length > 12) recent.splice(0, recent.length - 12);
        try { hit.run(ev, hit); } catch (err) { report(hit.id, err); }
    }

    /* The scope gate the view-scoped bindings use: the section must be on screen, and in Terminal
       mode with a focused panel, that panel must be the one (the same "what am I working in"
       pointer the shell uses everywhere else). */
    function inView(view) {
        var section = document.querySelector('.view[data-view="' + view + '"]');
        if (!section || !section.classList.contains('active')) return false;
        var shell = window.OFAPSHELL;
        if (shell && typeof shell.state === 'function') {
            var st = shell.state() || {};
            if (st.mode === 'terminal' && st.focus) return st.focus === view;
        }
        return true;
    }

    function run(id) {
        for (var i = 0; i < map.length; i += 1) {
            if (map[i].id === id) {
                if (map[i].run) map[i].run();
                return Boolean(map[i].run);
            }
        }
        return false;
    }

    /* ── the app-core bindings ─────────────────────────────────────────────── */

    /* Escape closes the ☰ panel and the hotkey sheet; inField keeps the behaviour the panel always
       had (it closes even while a field has focus). */
    bind({ id: 'escape', keys: ['escape'], scope: 'Global', inField: true,
        label: 'close the menu and every overlay',
        run: function () {
            if (window.OFAPMenu) { window.OFAPMenu.close(); window.OFAPMenu.showHotkeys(false); }
        } });

    bind({ id: 'view-switch', keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], scope: 'Global',
        label: 'switch view by rail order',
        run: function (ev) {
            var rail = document.querySelectorAll('.rail .nav-item');
            var item = rail[Number(ev.key) - 1];
            if (item) item.click();
        } });

    bind({ id: 'alpaca', keys: ['alt+a'], scope: 'Global',
        label: 'jump to the broker-account view',
        run: function () { if (typeof showView === 'function') showView('alpaca'); } });

    /* ── wiring ────────────────────────────────────────────────────────────── */

    if (document && typeof document.addEventListener === 'function') {
        document.addEventListener('keydown', dispatch);
    }

    window.OFAPKEYS = {
        bind: bind, document: documentRows, list: list, run: run, dispatch: dispatch,
        resolve: resolve, canonical: canonical, pretty: pretty, keysText: keysText,
        isTypingTarget: isTypingTarget, inView: inView, recent: recent,
        map: function () { return map; },
    };
})();
