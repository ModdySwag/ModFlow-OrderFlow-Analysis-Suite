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
    /* T3: the armed gate. A row marked `danger: true` refuses to dispatch until the user has
       armed the order keys (a visible, per-session switch) — the study's cheapest mitigation for
       the worst failure this app can have: a stray key that places an order. */
    var armed = false;

    /* §117: the user’s own chords, binding id -> chords. An override replaces the chords
       without touching the binding — the sheet, the dispatcher and the menu keep reading
       one registry. Loading and saving are the app’s (ui.config); resolving is this module’s. */
    var overrides = Object.create(null);

    function keysFor(row) {
        var ov = row ? overrides[row.id] : null;
        return (ov && ov.length) ? ov : (row ? row.keys : []);
    }

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
        return keys.map(pretty).join(' or ');
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
            if (keysFor(b).indexOf(chord) < 0) continue;
            if (b.danger && !armed) continue;              // the armed gate (T3)
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
            danger: Boolean(spec.danger),
            why: String(spec.why || ''),
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
            var ks = keysFor(b);
            var custom = Boolean(overrides[b.id] && overrides[b.id].length);
            return {
                id: b.id, keys: b.text || keysText({ keys: ks }), label: b.label, scope: b.scope,
                owner: b.owner, dispatched: Boolean(b.run), danger: Boolean(b.danger),
                why: String(b.why || ''),
                custom: custom,
                defaults: custom ? keysText(b) : '',
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

    var dangerHintAt = 0;

    function hintDisarmed(chord) {
        if (armed) return;
        for (var i = 0; i < map.length; i += 1) {
            var b = map[i];
            if (b.run && b.danger && keysFor(b).indexOf(chord) >= 0) {
                var now = Date.now();
                if (now - dangerHintAt > 4000) {
                    dangerHintAt = now;
                    if (typeof toast === 'function') {
                        toast(document.body, 'that key places a simulated order — arm the order keys in the Keys menu first', 'info');
                    }
                }
                return;
            }
        }
    }

    function dispatch(ev) {
        var chord = canonical(ev);
        if (!chord) return;
        /* Space on a focused control belongs to the browser (it activates it); never double-fire. */
        if (chord === 'space' && isActivatible(ev.target)) return;
        var inField = isTypingTarget(ev.target) || isTypingTarget(document.activeElement);
        var hit = resolve(chord, ev, { inField: inField });
        if (!hit) { hintDisarmed(chord); return; }
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
            /* T4/A-corr: view order = the rail's VIEW items — the injected Setup button (no
               data-view, first in the rail) must not shift the 1-9 mapping. */
            var rail = document.querySelectorAll('.rail .nav-item[data-view]');
            var item = rail[Number(ev.key) - 1];
            if (item) item.click();
        } });

    bind({ id: 'alpaca', keys: ['alt+a'], scope: 'Global',
        label: 'jump to the broker-account view',
        run: function () { if (typeof showView === 'function') showView('alpaca'); } });

    bind({ id: 'profiles', keys: ['alt+p'], scope: 'Global',
        label: 'saved setups (profiles): switch playbooks',
        run: function () { if (typeof showView === 'function') showView('profiles'); } });

    /* §92 — the common-scenario gaps the audit found. (Zen already lives in menubar.js as
       Alt+Z — a lesson from the receipt: check the registry before binding, ids replace.) The File menu always displayed
       Ctrl+Alt+R for the engine restart and there was NO such binding (a lie); start/stop had
       neither key nor hint. Now all three exist, plus the two journeys every session needs:
       find an instrument, and move through the panels without the mouse. */
    bind({ id: 'engine-start', keys: ['ctrl+alt+s'], scope: 'Global',
        label: 'start the engine',
        run: function () { if (window.OFAPENGINE) window.OFAPENGINE('start'); } });
    bind({ id: 'engine-stop', keys: ['ctrl+alt+x'], scope: 'Global',
        label: 'stop the engine',
        run: function () { if (window.OFAPENGINE) window.OFAPENGINE('stop'); } });
    bind({ id: 'engine-restart', keys: ['ctrl+alt+r'], scope: 'Global',
        label: 'restart the engine',
        run: function () { if (window.OFAPENGINE) window.OFAPENGINE('restart'); } });
    bind({ id: 'find-instrument', keys: ['ctrl+f'], scope: 'Global',
        label: 'find an instrument (the look-up)',
        run: function () {
            if (window.OFAPHINT && OFAPHINT.run) OFAPHINT.run('lookup');
            else if (typeof showView === 'function') showView('ofx');
        } });
    bind({ id: 'view-next', keys: ['ctrl+pagedown'], scope: 'Global',
        label: 'next panel in the rail',
        run: function () { cycleView(1); } });
    bind({ id: 'view-prev', keys: ['ctrl+pageup'], scope: 'Global',
        label: 'previous panel in the rail',
        run: function () { cycleView(-1); } });
    function cycleView(step) {
        var rail = document.querySelectorAll('.rail .nav-item[data-view]');
        if (!rail.length) return;
        var active = document.querySelector('.rail .nav-item.active');
        var idx = 0;
        for (var i = 0; i < rail.length; i += 1) { if (rail[i] === active) { idx = i; break; } }
        var next = rail[(idx + step + rail.length) % rail.length];
        if (next) next.click();
    }

    /* §128 — multi-monitor by keyboard. The menu key opens the same window menu the widget's ⧉
       button opens (send to a monitor, snap, pin, close); the two arrow keys are the platform's
       own Win+Shift+Arrow move, spelled with Alt so it cannot collide with the OS shortcut — and
       they work in BOTH modes: Terminal sends the focused widget, Classic the panel you are
       looking at. With no window open yet the send key opens one on the next monitor instead of
       doing nothing. */
    bind({ id: 'win-menu', keys: ['ctrl+alt+w'], scope: 'Terminal',
        label: 'the focused widget’s window menu (send · snap · pin)',
        run: function () { if (window.OFAPWINDOWS && OFAPWINDOWS.openFor) OFAPWINDOWS.openFor('', null); } });
    bind({ id: 'win-send-next', keys: ['ctrl+alt+shift+arrowright'], scope: 'Global',
        label: 'send the focused panel’s window to the next monitor',
        run: function () { if (window.OFAPWINDOWS && OFAPWINDOWS.sendFocused) void OFAPWINDOWS.sendFocused(1); } });
    bind({ id: 'win-send-prev', keys: ['ctrl+alt+shift+arrowleft'], scope: 'Global',
        label: 'send the focused panel’s window to the previous monitor',
        run: function () { if (window.OFAPWINDOWS && OFAPWINDOWS.sendFocused) void OFAPWINDOWS.sendFocused(-1); } });

    /* ── the shortcut prompts (§92) ────────────────────────────────────────── */

    /* Where a control has a shortcut, the control says so — on its tooltip (title), for screen
       readers (aria-keyshortcuts) and inside its hover card (hint.js renders its own line, reading
       the phrase this module publishes). One table, one pass, re-runnable: the menubar re-renders
       itself, controls arrive with views, and a second call is harmless.

       Idempotent by construction: the pristine text is captured once per element
       (data-base-title / data-hint-base-title) and every pass RE-DERIVES from it. The old shape
       appended only when the new text was absent, so a control whose shortcut changed — every rail
       digit after a view was added or removed — ended up reading "Shortcut 8 · Shortcut 9". */
    function accelOf(id, index) {
        for (var i = 0; i < map.length; i += 1) {
            var b = map[i];
            if (b.id !== id) continue;
            var ks = keysFor(b);
            if (typeof index === 'number') return ks.length > index ? pretty(ks[index]) : '';
            return keysText({ keys: ks });
        }
        return '';
    }

    /* How a shortcut is spoken to the user: a chord is a "Shortcut Ctrl+Alt+T"; a bare digit is an
       instruction ("Press 8 to switch to this panel"), because "Shortcut 8" on its own reads like
       a key called 8. Pure, so the selftest pins it. */
    function shortcutPhrase(text) {
        var t = String(text == null ? '' : text).trim();
        if (!t) return '';
        if (/^[1-9]$/.test(t)) return 'Press ' + t + ' to switch to this panel';
        return 'Shortcut ' + t;
    }

    function annotate() {
        if (typeof document === 'undefined' || !document.querySelectorAll) return;
        function put(el, text) {
            if (!el) return;
            var base = el.getAttribute('data-base-title');
            if (base === null) { base = el.getAttribute('title') || ''; el.setAttribute('data-base-title', base); }
            var phrase = shortcutPhrase(text);
            el.setAttribute('title', phrase ? (base ? base + ' \u00b7 ' + phrase : phrase) : base);
            if (phrase) {
                el.setAttribute('aria-keyshortcuts', String(text));
                el.setAttribute('data-shortcut-phrase', phrase);       // hint.js reads this for its card line
            } else {
                el.removeAttribute('aria-keyshortcuts');
                el.removeAttribute('data-shortcut-phrase');
            }
            /* The hover CARD says the shortcut in its own line (hint.js), so nothing is appended to
               data-hint-title here — that was the same key arriving twice for card-bearing controls. */
        }
        [['#ofapPause', 'freeze'], ['#menuBtn', 'palette'], ['#btnStart', 'engine-start'],
         ['#btnStop', 'engine-stop'], ['#railTerminal', 'terminal-toggle'],
         ['#menubarToggle', 'chrome-menubar'],
         ['#railToggle', 'chrome-rail'], ['#railHide', 'chrome-rail'],
         ['#railReveal', 'chrome-rail']].forEach(function (r) {
            document.querySelectorAll(r[0]).forEach(function (el) { put(el, accelOf(r[1])); });
        });
        /* T4/A-corr: the digits number VIEW items — the Setup button (no data-view) would
           otherwise take "1" and shift every view's displayed digit by one. Every rail item is
           visited (out of range ⇒ no phrase), so an item that loses its digit gets its base title
           back instead of keeping a stale "Press 9". */
        document.querySelectorAll('.rail .nav-item[data-view]').forEach(function (el, i) {
            put(el, i < 9 ? String(i + 1) : '');
        });
    }

    /* ── wiring ────────────────────────────────────────────────────────────── */

    if (document && typeof document.addEventListener === 'function') {
        document.addEventListener('keydown', dispatch);
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function () { setTimeout(annotate, 300); });
        } else {
            setTimeout(annotate, 300);
        }
    }

    function setArmed(value) {
        armed = Boolean(value);
        if (typeof document !== 'undefined' && document.getElementById) {
            var chip = document.getElementById('keysArmed');
            if (chip) chip.hidden = !armed;
        }
        return armed;
    }

    /* T6/A8: whether a row could fire right now — the same gates the dispatcher consults
       (run present, armed for danger rows, `when` true), so a menu that disables rows cannot
       drift from what the key would actually do. */
    function canDispatch(id) {
        for (var i = 0; i < map.length; i += 1) {
            if (map[i].id !== id) continue;
            var b = map[i];
            if (!b.run) return false;
            if (b.danger && !armed) return false;
            if (b.when) { try { return Boolean(b.when({})); } catch (e) { return false; } }
            return true;
        }
        return false;
    }

    /* §117 — the rebinding half, DOM-free so the selftest can pin it. The shapes here are
       deliberately conservative: the capture UI only ever hands in canonical() output, and the
       config sanitiser remains the authority on what a chord may look like on disk. An override
       set to an EMPTY list is not "no override": it is the request to forget a stored one, which
       overridesMap() then carries to the config (a merge cannot drop a key without it). */
    function applyOverrides(src) {
        overrides = Object.create(null);
        if (src && typeof src === 'object') {
            Object.keys(src).forEach(function (id) {
                var chords = src[id];
                if (!Array.isArray(chords)) return;
                var clean = chords.map(function (c) { return String(c || '').trim().toLowerCase(); })
                    .filter(function (c) { return c && c.length <= 24 && !/\s/.test(c); });
                if (clean.length) overrides[String(id).toLowerCase()] = clean;
            });
        }
        return Object.keys(overrides).length;
    }

    function rebind(id, chords) {
        var list = (Array.isArray(chords) ? chords : [chords]).map(function (c) {
            return String(c || '').trim().toLowerCase();
        }).filter(function (c) { return c && c.length <= 24 && !/\s/.test(c); });
        if (!list.length) return false;
        for (var i = 0; i < map.length; i += 1) {
            if (map[i].id === id) { overrides[id] = list; return true; }
        }
        return false;
    }

    function clearOverride(id) {
        /* Emptying (not deleting) is the marker the save path carries to the config:
           a merge cannot drop a key, but the store rebuilds the block and drops []. */
        overrides[id] = [];
        return true;
    }

    function clearAllOverrides() {
        Object.keys(overrides).forEach(function (id) { overrides[id] = []; });
        return true;
    }

    function overridesMap() {
        var out = {};
        Object.keys(overrides).forEach(function (id) { out[id] = overrides[id].slice(); });
        return out;
    }

    /* Who else holds this chord. The dispatcher resolves ties by priority silently; the rebind
       flow refuses instead, naming every owner, so a user never steals a key they cannot see. */
    function conflicts(chord, excludeId) {
        var out = [];
        for (var i = 0; i < map.length; i += 1) {
            var b = map[i];
            if (!b.run || b.id === excludeId) continue;
            if (keysFor(b).indexOf(chord) >= 0) {
                out.push({ id: b.id, label: b.label, scope: b.scope, priority: b.priority || 0 });
            }
        }
        return out;
    }

    window.OFAPKEYS = {
        bind: bind, document: documentRows, list: list, run: run, dispatch: dispatch,
        armed: function () { return armed; }, setArmed: setArmed,
        canDispatch: canDispatch,
        annotate: annotate, accelOf: accelOf, shortcutPhrase: shortcutPhrase,
        resolve: resolve, canonical: canonical, pretty: pretty, keysText: keysText,
        isTypingTarget: isTypingTarget, inView: inView, recent: recent,
        map: function () { return map; },
        keysFor: keysFor, applyOverrides: applyOverrides, rebind: rebind,
        clearOverride: clearOverride, clearAllOverrides: clearAllOverrides,
        overrides: overridesMap, conflicts: conflicts,
    };
})();
