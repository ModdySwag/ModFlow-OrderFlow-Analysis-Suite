/* hint.js — the app's one "why isn't this working" popover (§83).
 *
 * Anything that can refuse a user for a reason — the Engine's symbol chip, the data-source
 * pills, an instrument row that cannot stream — carries a hint. Hover shows the card;
 * right-click pins it open (so it can be read with the mouse free) and the card's buttons run
 * real app actions: open the instrument look-up, the Instruments view, the setup assistant,
 * the sources menu. Never a dead link.
 *
 * The pure half is selftested under Node (`hint.selftest.js`): spec parsing, the card's HTML
 * (escaped — the body can carry server text), the closed action set, and the notice text a
 * refused engine start produces. The DOM half is one shared node, positioned under its target
 * and dismissed on leave, Escape, a click elsewhere, or any scroll of the page.
 */
(function () {
    'use strict';

    var VERSION = '1.0.0';

    /* The closed action set. The dispatcher below is the only place these turn into calls, so
       a typo in a hint can never fire something unexpected. */
    var ACTIONS = ['lookup', 'engine', 'instruments', 'wizard', 'menu'];
    var ACTION_LABELS = {
        lookup: 'Open the instrument look-up',
        engine: 'Open the Engine view',
        instruments: 'Open Instruments',
        wizard: 'Open the setup assistant',
        menu: 'Open the data-sources menu',
    };

    function str(value) { return String(value == null ? '' : value); }

    function esc(text) {
        return str(text).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    /* A hint spec, from an object or from data-hint* attributes on a node. */
    function parse(source) {
        var raw = source || {};
        if (raw.dataset || raw.getAttribute) {
            var get = function (name) {
                return (raw.dataset && raw.dataset[name]) ||
                    (raw.getAttribute && raw.getAttribute('data-hint-' + name)) || '';
            };
            raw = { title: get('title'), body: get('body'), actions: get('actions') };
        }
        var actions = raw.actions;
        if (typeof actions === 'string') actions = actions.split(/[\s,]+/);
        actions = (Array.isArray(actions) ? actions : []).filter(function (a) {
            return ACTIONS.indexOf(a) >= 0;
        });
        return {
            title: str(raw.title).trim(),
            body: str(raw.body).trim(),
            actions: actions,
        };
    }

    function actionsOf(spec) {
        var parsed = parse(spec);
        return parsed.actions.map(function (a) { return { action: a, label: ACTION_LABELS[a] }; });
    }

    /* The card's markup. Pure: same input, same string — the selftest pins the escaping. */
    function cardHTML(source) {
        var spec = parse(source);
        if (!spec.title && !spec.body) return '';
        var buttons = actionsOf(spec).map(function (a) {
            return '<button type="button" class="ofap-hint-btn" data-hint-action="' + esc(a.action) + '">'
                + esc(a.label) + '</button>';
        }).join('');
        return '<div class="ofap-hint-card" role="dialog" aria-label="explanation">'
            + (spec.title ? '<div class="ofap-hint-title">' + esc(spec.title) + '</div>' : '')
            + (spec.body ? '<div class="ofap-hint-body">' + esc(spec.body) + '</div>' : '')
            + (buttons ? '<div class="ofap-hint-actions">' + buttons + '</div>' : '')
            + '</div>';
    }

    /* What an engine start/restart says when instruments were skipped (§82/§83): one sentence
       naming the first reason and how many others there are — the count is never invented. */
    function skippedNotice(payload) {
        var skipped = (payload && payload.skipped) || [];
        if (!skipped.length) return null;
        var first = skipped[0] || {};
        var more = skipped.length > 1 ? ' (+' + (skipped.length - 1) + ' more)' : '';
        return {
            text: str(first.symbol || 'an instrument') + ': ' + str(first.reason || 'skipped') + more,
            action: 'lookup',
            label: ACTION_LABELS.lookup,
        };
    }

    /* ── the DOM half ─────────────────────────────────────────────────────────────── */

    var node = null;          // the shared card + backdrop node
    var pinned = false;
    var current = null;

    function ensureNode() {
        if (node || typeof document === 'undefined' || !document.body) return node;
        node = document.createElement('div');
        node.className = 'ofap-hint';
        node.hidden = true;
        document.body.appendChild(node);
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape') hide();
        });
        document.addEventListener('click', function (ev) {
            if (!node || node.hidden) return;
            if (node.contains(ev.target)) return;
            hide();
        });
        window.addEventListener('scroll', function () { hide(); }, true);
        /* The card keeps itself alive while the pointer is on it — the other half of the bridge. */
        node.addEventListener('mouseenter', cancelLeave);
        node.addEventListener('mouseleave', leaveSoon);
        return node;
    }

    function placeInto(target) {
        if (!node) return;
        var rect = target.getBoundingClientRect();
        node.style.left = Math.max(8, Math.min(window.innerWidth - 380, rect.left)) + 'px';
        var below = rect.bottom + 8;
        var height = node.offsetHeight || 140;
        var top = (below + height > window.innerHeight - 8) ? Math.max(8, rect.top - height - 8) : below;
        node.style.top = top + 'px';
    }

    /* §85 — reachable hover cards: hiding on the trigger's own mouseleave made the card a moving
       target (it floats below the trigger with a gap; measured: it vanished mid-travel and its
       buttons could not be clicked). The card now survives the trip: leaving either the trigger
       or the card only starts a short grace, entering the other side cancels it, and only when
       the pointer is on neither does it go. Right-click pinning is unchanged. */
    var LEAVE_GRACE = 260;
    var leaveTimer = null;

    function cancelLeave() {
        if (leaveTimer) { clearTimeout(leaveTimer); leaveTimer = null; }
    }

    function leaveSoon() {
        if (pinned) return;
        cancelLeave();
        leaveTimer = setTimeout(function () { hide(); }, LEAVE_GRACE);
    }

    function show(spec, target, opts) {
        var html = cardHTML(spec);
        if (!node && !ensureNode()) return;
        if (!html || !target) { hide(); return; }
        pinned = !!(opts && opts.pin);
        cancelLeave();
        current = { spec: parse(spec), target: target };
        node.innerHTML = html;
        /* §92: a control that has a keyboard shortcut says so inside its card too. The text is
           generated by keys.js (pretty-printed chords), escaped here for the same reason every
           other injected string is. */
        var phrase = target.getAttribute && target.getAttribute('data-shortcut-phrase');
        var sc = target.getAttribute && target.getAttribute('aria-keyshortcuts');
        if (phrase || sc) {
            var line = document.createElement('div');
            line.className = 'hint-shortcut';
            /* keys.js publishes the phrase ("Press 8 to switch to this panel", "Shortcut Ctrl+K");
               the raw attribute is only a fallback, so a digit can never read as a key called 8. */
            line.textContent = '\u2328 ' + (phrase || ('Shortcut ' + sc));
            node.appendChild(line);
        }
        node.hidden = false;
        placeInto(target);
    }

    function hide() {
        cancelLeave();
        if (!node || node.hidden) { pinned = false; return; }
        node.hidden = true;
        node.innerHTML = '';
        pinned = false;
        current = null;
    }

    /* The one place an action becomes a call. */
    function run(action) {
        switch (action) {
            case 'lookup':
                if (window.showView) window.showView('ofx');
                var find = document.getElementById('ofxSymbolFind');
                if (find) find.click();
                break;
            case 'engine':
                if (window.showView) window.showView('ofx');
                break;
            case 'instruments':
                if (window.OFAPNAV) window.OFAPNAV.jump('instruments');
                else if (window.showView) window.showView('instruments');
                break;
            case 'wizard':
                if (typeof window.openWizard === 'function') window.openWizard();
                break;
            case 'menu':
                var btn = document.getElementById('menuBtn');
                if (btn) btn.click();
                break;
            default:
                break;
        }
        hide();
    }

    function attach(target, spec, opts) {
        if (!target) return;
        var fixed = spec ? parse(spec) : null;
        var specAt = function () { return fixed || parse(target); };
        ['mouseenter', 'focus'].forEach(function (evt) {
            target.addEventListener(evt, function () {
                if (pinned) { cancelLeave(); return; }
                show(specAt(), target, { pin: false });
            });
        });
        ['mouseleave', 'blur'].forEach(function (evt) {
            target.addEventListener(evt, function () { if (!pinned) leaveSoon(); });
        });
        /* Right-click pins the card — the "click condition" a user reaches for when a panel
           looks broken (and the card's buttons are right there). */
        target.addEventListener('contextmenu', function (ev) {
            ev.preventDefault();
            show(specAt(), target, { pin: true });
        });
        return target;
    }

    /* A notice strip that carries a real action: used after an engine start that skipped
       instruments (§82/§83) — the sentence plus the button that opens the look-up. */
    function paintNotice(notice, target) {
        var el = target || document.getElementById('noticeStrip') || document.body;
        if (!el || !notice) return null;
        var html = '<div class="banner warn ofap-hint-notice"><span>' + esc(notice.text) + '</span>'
            + '<button type="button" class="btn small" data-hint-action="' + esc(notice.action || 'lookup')
            + '">' + esc(notice.label || ACTION_LABELS.lookup) + '</button></div>';
        if (el === document.body || el.id === 'noticeStrip') {
            var strip = document.getElementById('noticeStrip');
            if (!strip) {
                strip = document.createElement('div');
                strip.id = 'noticeStrip';
                document.body.appendChild(strip);
            }
            strip.innerHTML = html;
            return strip.firstChild;
        }
        el.innerHTML = html;
        return el.firstChild;
    }

    /* Ask the server what this symbol is and show the answer against the element the user
       pointed at. One request, one card — the same endpoint the Engine panel uses. */
    function explainSymbol(symbol, anchor) {
        if (!symbol || !anchor) return Promise.resolve(null);
        show({ title: symbol, body: 'looking it up\u2026' }, anchor, { pin: true });
        return fetch('/api/control/instruments/resolve?symbol=' + encodeURIComponent(symbol))
            .then(function (r) { return r.json(); })
            .then(function (payload) {
                var state = (payload && payload.state) || 'unknown';
                var body = [(payload && payload.reason) || '', (payload && payload.hint) || '']
                    .filter(Boolean).join(' \u00b7 ') || 'no reason given';
                show({ title: symbol + ' \u2014 ' + state, body: body, actions: ['lookup', 'instruments'] },
                    anchor, { pin: true });
                return payload;
            })
            .catch(function () {
                show({ title: symbol, body: 'the look-up could not be reached', actions: ['lookup'] }, anchor, { pin: true });
                return null;
            });
    }

    function boot() {
        if (typeof document === 'undefined' || !document.body) return;
        ensureNode();
        /* Any element anywhere with data-hint-action runs through the one dispatcher — the
           card's buttons and any notice the app paints (it can be repainted at any time). */
        document.addEventListener('click', function (ev) {
            var btn = ev.target && ev.target.closest ? ev.target.closest('[data-hint-action]') : null;
            if (btn) { ev.preventDefault(); run(btn.getAttribute('data-hint-action')); }
        });
        document.addEventListener('contextmenu', function (ev) {
            var holder = ev.target && ev.target.closest ? ev.target.closest('[data-hint-title]') : null;
            if (holder) { ev.preventDefault(); show(parse(holder), holder, { pin: true }); }
        });
        /* Elements that carry data-hint-* attributes anywhere in the page (markup-declared
           hints — the engine chip, the pills, the Instruments header button). Specs are read at
           show-time, so a hint whose text is updated later explains the CURRENT state. */
        document.querySelectorAll('[data-hint-title]').forEach(function (el) { attach(el); });
        /* The Instruments view's own front door to the look-up. */
        var instLookup = document.getElementById('instLookup');
        if (instLookup) instLookup.addEventListener('click', function () {
            /* T14/B6: the button is the look-up overlay now; the walkthrough stays reachable
               from the palette for the "why won't my symbol stream?" question. */
            if (window.OFAPLOOKUP && OFAPLOOKUP.open) { OFAPLOOKUP.open(); return; }
            run('lookup');
        });
        /* Right-click an instrument row — in the Instruments table and in the Market Watch
           board (§87) alike: the same verdict the Engine panel gives, without leaving the table
           (the row's symbol goes through the look-up endpoint). */
        ['instTable', 'mwTable'].forEach(function (id) {
            var table = document.getElementById(id);
            if (!table) return;
            table.addEventListener('contextmenu', function (ev) {
                var row = ev.target && ev.target.closest ? ev.target.closest('tr[data-symbol]') : null;
                if (!row) return;
                ev.preventDefault();
                void explainSymbol(row.getAttribute('data-symbol'), row);
            });
        });
    }

    var API = { version: VERSION, ACTIONS: ACTIONS, ACTION_LABELS: ACTION_LABELS,
        parse: parse, actionsOf: actionsOf, cardHTML: cardHTML, skippedNotice: skippedNotice,
        attach: attach, show: show, hide: hide, run: run, boot: boot, paintNotice: paintNotice,
        explainSymbol: explainSymbol,
        state: function () { return { visible: !!(node && !node.hidden), pinned: pinned, spec: current && current.spec }; } };

    if (typeof window !== 'undefined') {
        window.OFAPHINT = API;
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
        else boot();
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
