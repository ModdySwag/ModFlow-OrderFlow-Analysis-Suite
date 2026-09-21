/* windowing.js — Windows & layouts (T2): the master list of the app's auxiliary windows.
 *
 * The field's recurring bug is "the window became unreachable" (Sierra's reattach saga,
 * MetaQuotes patching windows lost off-screen). This panel is the in-app answer: every window
 * the launcher knows about, where it is, and the rescue actions — bring it home (reset the
 * placement to a visible screen, reopening it there when it is open) and take it out of the
 * set. It reads the same /api/control/windows route §73 shipped; with no native host it says
 * so rather than pretending.
 *
 * §128 — the multi-monitor half, in one dialog: every open window shows the monitor it is ON,
 * carries one-click Send buttons for every monitor and the snap shapes, and a window whose
 * monitor is gone is called out with a Bring-home button. The "new window" row opens ANY panel
 * on ANY monitor already snapped — which is also Classic mode's route to a two-monitor desk,
 * where there is no focused widget to hang the menu from.
 *
 * The namespace is OFAPWINMGR, not OFAPWINDOWS: windows-ui.js owns OFAPWINDOWS (the widget-window
 * menu), and two modules assigning one global meant the LAST one loaded won — measured: the View
 * menu's entry called an OFAPWINDOWS.open that windows-ui.js had already overwritten, so the
 * dialog was unreachable. One global each, and the View menu opens this one.
 */
(function () {
    'use strict';

    /*: The snap shapes offered per row. Must be a subset of `windows.PRESETS` (pinned in
        test_windowing_ui.py) — a shape here that the API cannot resolve is a dead button. */
    const SHAPES = [
        ['left', '◧ Left'], ['right', '◨ Right'], ['top', '⬒ Top'], ['bottom', '⬓ Bottom'],
        ['topleft', '◰ TL'], ['topright', '◳ TR'], ['bottomleft', '◱ BL'], ['bottomright', '◲ BR'],
        ['fill', '⛶ Fill'], ['center', '⤢ Centre'],
    ];

    var state = { payload: null, busy: false };

    function el(id) { return document.getElementById(id); }

    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function request(method, body) {
        if (typeof method === 'string') {
            var opts = method === 'POST' ? { method: 'POST', body: body || {} } : {};
            if (typeof window.api === 'function') return window.api('/api/control/windows', opts);
        }
        return fetch('/api/control/windows', {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined,
        }).then(function (r) { return r.json(); });
    }

    function act(payload) {
        if (state.busy) return Promise.resolve();
        state.busy = true;
        return request('POST', payload).then(function (res) {
            state.busy = false;
            if (res) state.payload = res;
            render();
            return res;
        }).catch(function (err) {
            state.busy = false;
            if (state.payload) state.payload.error = 'the window host did not answer: ' + err;
            render();
        });
    }

    function openSet() { return (state.payload && state.payload.open) || []; }
    function records() { return (state.payload && state.payload.windows) || []; }
    function screens() { return (state.payload && state.payload.screens) || []; }
    function geometryOf(id) {
        var geo = (state.payload && state.payload.open_geometry) || {};
        return geo[id] || {};
    }
    function stranded() { return (state.payload && state.payload.stranded) || []; }

    function btn(label, payload, cls) {
        return '<button class="btn small winmgr-btn ' + esc(cls || '') + '" data-win-act="'
            + esc(JSON.stringify(payload)) + '">' + esc(label) + '</button>';
    }

    function sendButtons(record, isOpen) {
        /* One button per monitor — the form the OS drag takes when a page cannot start one, and
           per shape on the monitor the window is already on. */
        var out = screens().map(function (s) {
            var here = geometryOf(record.id).screen === Number(s.index) && isOpen;
            return btn((here ? '· ' : '') + '→ ' + (s.label || ('Monitor ' + (Number(s.index) + 1))),
                { action: 'move', id: record.id, screen: Number(s.index) || 0 }, here ? 'winmgr-here' : '');
        }).join('');
        var shapes = SHAPES.map(function (pair) {
            return btn(pair[1], { action: 'move', id: record.id, preset: pair[0] });
        }).join('');
        return '<span class="winmgr-send">' + out + '</span><span class="winmgr-shapes">' + shapes + '</span>';
    }

    function rowFor(record) {
        var open = openSet().indexOf(record.id) !== -1;
        var here = geometryOf(record.id);
        var where = open ? (here.screen_label ? ' · on ' + here.screen_label : '') : '';
        var tail = open
            ? btn('Focus', { action: 'focus', id: record.id })
                + btn(record.on_top ? 'Unpin' : 'Pin', { action: 'ontop', id: record.id, on_top: !record.on_top })
                + btn('Reset position', { action: 'reset', id: record.id })
                + btn('Close', { action: 'close', id: record.id })
            : btn('Open', { action: 'open', id: record.id, view: record.view,
                    screen_key: record.screen_key, width: record.width, height: record.height,
                    on_top: record.on_top })
                + btn('Reset position', { action: 'reset', id: record.id })
                + btn('Remove from the set', { action: 'close', id: record.id });
        return '<div class="winmgr-row"><span class="winmgr-view">' + esc(record.view) + '</span>'
            + '<span class="winmgr-id dim">' + esc(record.id) + (open ? ' · open' : '') + esc(where) + '</span>'
            + '<span class="winmgr-btns">' + tail + '</span></div>'
            + '<div class="winmgr-row winmgr-sendrow"><span class="winmgr-view dim">send to</span>'
            + sendButtons(record, open) + '</div>';
    }

    function viewOptions() {
        var out = [];
        Array.prototype.forEach.call(document.querySelectorAll('section.view[data-view]'), function (node) {
            var slug = String(node.getAttribute('data-view') || '');
            if (slug) out.push(slug);
        });
        return out;
    }

    function newWindowSection() {
        var views = viewOptions();
        if (!views.length) return '';
        var viewSel = '<select id="winmgrNewView" title="Which panel to open in its own window">'
            + views.map(function (v) { return '<option value="' + esc(v) + '">' + esc(v.toUpperCase()) + '</option>'; }).join('')
            + '</select>';
        var screenSel = '<select id="winmgrNewScreen" title="Which monitor it opens on">'
            + screens().map(function (s) {
                return '<option value="' + esc(String(Number(s.index) || 0)) + '">'
                    + esc(s.label || ('Monitor ' + (Number(s.index) + 1))) + '</option>';
            }).join('')
            + '</select>';
        var shapeSel = '<select id="winmgrNewShape" title="What shape it opens in">'
            + '<option value="center">Its own size, centred</option>'
            + SHAPES.filter(function (p) { return p[0] !== 'center'; })
                .map(function (p) { return '<option value="' + esc(p[0]) + '">' + esc(p[1]) + '</option>'; }).join('')
            + '</select>';
        return '<div class="winmgr-sec"><div class="winmgr-sec-title">Another panel, on any monitor</div>'
            + '<div class="winmgr-new">' + viewSel + screenSel + shapeSel
            + '<button class="btn small" data-win-act="' + esc(JSON.stringify({ action: 'open_any' }))
            + '">Open window</button></div>'
            + '<div class="dim">Pick a panel, a monitor and a shape — the window opens there already '
            + 'placed. In Classic mode this is how any panel moves to a second screen.</div></div>';
    }

    function render() {
        var overlay = el('winmgrOverlay');
        if (!overlay) return;
        var p = state.payload || {};
        var head = '<div class="winmgr-head"><span class="winmgr-title">Windows &amp; layouts</span>'
            + '<span class="grow"></span>'
            + (p.native ? '<span class="dim">' + records().length + ' of ' + (p.max || '\u2014')
                + ' in the set</span>' : '')
            + '<button class="btn small" data-win-act="' + esc(JSON.stringify({ action: 'close_panel' }))
            + '">Close</button></div>';
        var body;
        if (!p.native) {
            body = '<div class="hint">auxiliary windows need the desktop app \u2014 this session has no '
                + 'window host (a browser or headless run offers no window controls)</div>';
        } else {
            var rows2 = screens().map(function (s) {
                var on = openSet().filter(function (id) { return geometryOf(id).screen === Number(s.index); }).length;
                return '<div class="winmgr-screen">' + esc(s.label)
                    + (on ? ' <span class="dim">\u00b7 ' + on + ' window' + (on === 1 ? '' : 's') + '</span>' : '')
                    + '</div>';
            }).join('');
            var rows = records().map(rowFor).join('')
                || '<div class="hint">no windows in the set yet \u2014 open one from a panel</div>';
            var gone = stranded();
            body = '<div class="winmgr-sec"><div class="winmgr-sec-title">Screens</div>'
                + (rows2 || '<div class="hint">no screens reported</div>') + '</div>'
                + newWindowSection()
                + '<div class="winmgr-sec"><div class="winmgr-sec-title">The window set</div>'
                + rows + '</div>'
                + (gone.length ? '<div class="banner warn" style="display:block">'
                    + gone.length + ' window' + (gone.length === 1 ? ' is' : 's are')
                    + ' on a monitor that is gone: ' + esc(gone.join(', '))
                    + ' <button class="btn small" data-win-act="'
                    + esc(JSON.stringify({ action: 'arrange' })) + '">Bring them home</button></div>' : '')
                + (p.error ? '<div class="banner warn" style="display:block">' + esc(p.error) + '</div>' : '')
                + '<div class="winmgr-foot">'
                + '<button class="btn small" data-win-act="'
                + esc(JSON.stringify({ action: 'close_all' })) + '">Close all windows</button>'
                + '<span class="dim">reset brings a window home to a visible screen; send moves an open '
                + 'window to that monitor right now and remembers it for the next start; closing one also '
                + 'removes it from the set the next start restores</span></div>';
        }
        overlay.innerHTML = '<div class="winmgr-card" role="dialog" aria-modal="true"'
            + ' aria-label="Windows and layouts">' + head
            + '<div class="winmgr-body">' + body + '</div></div>';
    }

    function newWindowPayload() {
        var view = el('winmgrNewView');
        var screen = el('winmgrNewScreen');
        var shape = el('winmgrNewShape');
        var payload = { action: 'open', view: view ? view.value : '' };
        if (screen && screen.value !== '') payload.screen = Number(screen.value);
        if (shape && shape.value) payload.preset = shape.value;
        return payload;
    }

    function onOverlayClick(ev) {
        var b = ev.target && ev.target.closest ? ev.target.closest('[data-win-act]') : null;
        if (b) {
            var payload = null;
            try { payload = JSON.parse(b.getAttribute('data-win-act')); } catch (e) { payload = null; }
            if (!payload || !payload.action) return;
            if (payload.action === 'close_panel') { closePanel(); return; }
            /* Only the "open any panel" row needs the pickers read; every other row carries its own
               finished payload. The first cut of this rewrite gated ALL rows on the payload's view
               field and made every button in the dialog dead (measured live: Bring them home
               clicked, nothing moved). A refusal from the API is a better answer than a click that
               does nothing. */
            if (payload.action === 'open_any') payload = newWindowPayload();
            act(payload);
            return;
        }
        if (ev.target === el('winmgrOverlay')) closePanel();
    }

    function openPanel() {
        if (!el('winmgrOverlay')) {
            var overlay = document.createElement('div');
            overlay.className = 'winmgr-overlay';
            overlay.id = 'winmgrOverlay';
            overlay.addEventListener('click', onOverlayClick);
            document.body.appendChild(overlay);
        }
        return request('GET').then(function (res) {
            state.payload = res;
            render();
        }).catch(function () {
            state.payload = { native: false };
            render();
        });
    }

    function closePanel() {
        var overlay = el('winmgrOverlay');
        if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }

    function boot() {
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape' && el('winmgrOverlay')) closePanel();
        });
        /* One global per module: the widget-window menu is OFAPWINDOWS (windows-ui.js), this
           dialog is OFAPWINMGR — the View menu calls this one by name. */
        window.OFAPWINMGR = {
            open: openPanel,
            close: closePanel,
            state: function () { return state.payload; },
            shapes: SHAPES.map(function (p) { return p[0]; }),
        };
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
