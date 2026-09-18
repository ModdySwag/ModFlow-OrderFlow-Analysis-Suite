/* windowing.js — Windows & layouts (T2): the master list of the app's auxiliary windows.
 *
 * The field's recurring bug is "the window became unreachable" (Sierra's reattach saga,
 * MetaQuotes patching windows lost off-screen). This panel is the in-app answer: every window
 * the launcher knows about, where it is, and the rescue actions — bring it home (reset the
 * placement to a visible screen, reopening it there when it is open) and take it out of the
 * set. It reads the same /api/control/windows route §73 shipped; with no native host it says
 * so rather than pretending.
 */
(function () {
    'use strict';

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

    function btn(label, payload) {
        return '<button class="btn small winmgr-btn" data-win-act="'
            + esc(JSON.stringify(payload)) + '">' + esc(label) + '</button>';
    }

    function rowFor(record) {
        var open = openSet().indexOf(record.id) !== -1;
        var buttons = [];
        if (open) {
            buttons.push(btn('Focus', { action: 'focus', id: record.id }));
            buttons.push(btn(record.on_top ? 'Unpin' : 'Pin',
                { action: 'ontop', id: record.id, on_top: !record.on_top }));
            buttons.push(btn('Reset position', { action: 'reset', id: record.id }));
            buttons.push(btn('Close', { action: 'close', id: record.id }));
        } else {
            buttons.push(btn('Open', { action: 'open', id: record.id, view: record.view,
                screen_key: record.screen_key, width: record.width, height: record.height,
                on_top: record.on_top }));
            buttons.push(btn('Reset position', { action: 'reset', id: record.id }));
            buttons.push(btn('Remove from the set', { action: 'close', id: record.id }));
        }
        return '<div class="winmgr-row"><span class="winmgr-view">' + esc(record.view) + '</span>'
            + '<span class="winmgr-id dim">' + esc(record.id) + (open ? ' · open' : '') + '</span>'
            + '<span class="winmgr-btns">' + buttons.join('') + '</span></div>';
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
            var screens = (p.screens || []).map(function (s) {
                return '<div class="winmgr-screen">' + esc(s.label)
                    + (s.width ? ' \u00b7 ' + s.width + '\u00d7' + s.height : '') + '</div>';
            }).join('');
            var rows = records().map(rowFor).join('')
                || '<div class="hint">no windows in the set yet \u2014 open one from a panel</div>';
            body = '<div class="winmgr-sec"><div class="winmgr-sec-title">Screens</div>'
                + (screens || '<div class="hint">no screens reported</div>') + '</div>'
                + '<div class="winmgr-sec"><div class="winmgr-sec-title">The window set</div>'
                + rows + '</div>'
                + (p.error ? '<div class="banner warn" style="display:block">' + esc(p.error) + '</div>' : '')
                + '<div class="winmgr-foot">'
                + '<button class="btn small" data-win-act="'
                + esc(JSON.stringify({ action: 'close_all' })) + '">Close all windows</button>'
                + '<span class="dim">reset brings a window home to a visible screen; closing one also '
                + 'removes it from the set the next start restores</span></div>';
        }
        overlay.innerHTML = '<div class="winmgr-card" role="dialog" aria-modal="true"'
            + ' aria-label="Windows and layouts">' + head
            + '<div class="winmgr-body">' + body + '</div></div>';
    }

    function onOverlayClick(ev) {
        var b = ev.target && ev.target.closest ? ev.target.closest('[data-win-act]') : null;
        if (b) {
            var payload = null;
            try { payload = JSON.parse(b.getAttribute('data-win-act')); } catch (e) { payload = null; }
            if (!payload) return;
            if (payload.action === 'close_panel') { closePanel(); return; }
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
        window.OFAPWINDOWS = {
            open: openPanel,
            close: closePanel,
            state: function () { return state.payload; },
        };
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
