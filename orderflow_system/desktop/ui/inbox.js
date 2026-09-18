/* inbox.js — T14/B7: the notifications inbox.
 *
 * The alert engine already fires into a history; this view is the record made usable: every firing
 * as a tile (severity, kind, instrument, message, time), categorised by what the rule watches,
 * filterable, priority-sortable, and act-on-click — opening a tile marks it read and takes you to
 * the panel that can show its evidence. Do not disturb keeps the record running but silences the
 * badge. The reading state lives in the config (ui.notifications); the firings themselves are the
 * engine's own — nothing here duplicates or invents one.
 */
(function () {
    'use strict';

    const POLL_MS = 4000;
    let timer = null;
    const state = { prefs: { read_ms: 0, dnd: false, priority: false }, items: [], unread: 0, cat: 'all' };

    /* Which rule-kinds belong to which reading category — checked in test_b7 against the same
       kinds the palette's alert help lists, so a new kind cannot slip in uncategorised. */
    const CATEGORIES = {
        tape: ['big_trade', 'block_trade', 'sweep', 'stop_run', 'iceberg', 'speed_spike', 'cvd_divergence'],
        book: ['heat_pull', 'heat_stack', 'wall', 'stacked_imbalance', 'intent_pressure', 'pulled_size'],
        structure: ['trapped_traders', 'vwap_cross'],
        execution: ['depth_execution', 'depth_refill'],
    };
    /* Where a tile's evidence lives — the panel its click opens. */
    const SURFACE_FOR_KIND = {
        heat_pull: 'heatmap', heat_stack: 'heatmap', wall: 'heatmap', stacked_imbalance: 'heatmap',
        pulled_size: 'heatmap', intent_pressure: 'depth',
        big_trade: 'tape', block_trade: 'tape', sweep: 'tape', stop_run: 'tape', iceberg: 'tape',
        speed_spike: 'tape', cvd_divergence: 'cvd',
        trapped_traders: 'chart', vwap_cross: 'chart',
        depth_execution: 'depth', depth_refill: 'depth',
    };
    const SEV_RANK = { critical: 0, warning: 1, info: 2 };

    function $(id) { return document.getElementById(id); }
    function esc(t) { return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
    function categoryOf(kind) {
        const k = String(kind || '');
        const names = Object.keys(CATEGORIES);
        for (let i = 0; i < names.length; i += 1) {
            if (CATEGORIES[names[i]].indexOf(k) >= 0) return names[i];
        }
        return 'other';
    }
    function surfaceFor(kind) { return SURFACE_FOR_KIND[String(kind || '')] || 'heatmap'; }
    function timeAgo(ts) {
        const s = Math.max(0, Math.round((Date.now() - Number(ts || 0)) / 1000));
        if (s < 60) return s + 's ago';
        if (s < 3600) return Math.round(s / 60) + 'm ago';
        if (s < 86400) return Math.round(s / 3600) + 'h ago';
        return Math.round(s / 86400) + 'd ago';
    }
    function onScreen() {
        const section = document.querySelector('.view[data-view="inbox"]');
        if (!section) return false;
        return section.classList.contains('active') || section.style.display === 'flex';
    }

    /* ── painting ───────────────────────────────────────────────────────────── */

    function paintBadge() {
        const b = $('navInboxCount');
        if (!b) return;
        b.textContent = state.prefs.dnd ? '•' : String(state.unread);
        b.title = state.prefs.dnd
            ? 'do not disturb — the inbox keeps recording, the count stays quiet'
            : (state.unread + ' unread notification(s)');
    }

    function ordered() {
        const items = state.items.filter((a) => state.cat === 'all' || categoryOf(a.kind) === state.cat);
        if (state.prefs.priority) {
            return items.slice().sort((a, b) => (SEV_RANK[a.severity] == null ? 3 : SEV_RANK[a.severity])
                - (SEV_RANK[b.severity] == null ? 3 : SEV_RANK[b.severity]) || Number(b.ts_ms) - Number(a.ts_ms));
        }
        return items.slice().sort((a, b) => Number(b.ts_ms) - Number(a.ts_ms));
    }

    function paintChips() {
        const host = $('inboxChips');
        if (!host) return;
        const cats = ['all'].concat(Object.keys(CATEGORIES)).concat(['other']);
        const counts = {};
        state.items.forEach((a) => { const c = categoryOf(a.kind); counts[c] = (counts[c] || 0) + 1; });
        host.innerHTML = cats.map((c) => {
            const n = c === 'all' ? state.items.length : (counts[c] || 0);
            if (!n && c !== 'all') return '';
            return '<button class="btn small' + (state.cat === c ? ' primary' : '') + '" data-cat="' + c + '">'
                + c + ' (' + n + ')</button>';
        }).join('');
        host.querySelectorAll('[data-cat]').forEach((b) => {
            b.onclick = function () { state.cat = b.getAttribute('data-cat'); paint(); };
        });
    }

    function paint() {
        paintBadge();
        paintChips();
        const count = $('inboxCount');
        if (count) count.textContent = state.unread + ' unread · ' + state.items.length + ' kept';
        const body = $('inboxBody');
        if (!body) return;
        const rows = ordered();
        if (!rows.length) {
            body.innerHTML = '<div class="dim">nothing here yet — the inbox fills when a rule fires. '
                + 'The rules themselves live in <b>Alerts</b>.</div>';
            return;
        }
        body.innerHTML = rows.map((a) => {
            const unread = Number(a.ts_ms || 0) > Number(state.prefs.read_ms || 0);
            const surface = surfaceFor(a.kind);
            return '<div class="inb-tile' + (unread ? ' unread' : '') + '" data-ts="' + Number(a.ts_ms || 0)
                + '" data-sym="' + esc(a.symbol) + '" data-view-to="' + esc(surface)
                + '" title="click: mark read and open the ' + esc(surface) + ' panel on ' + esc(a.symbol) + '">'
                + '<span class="inb-sev ' + esc(a.severity || 'info') + '"></span>'
                + '<div class="inb-main"><div class="inb-msg">' + esc(a.message) + '</div>'
                + '<div class="inb-meta">' + esc(a.kind) + ' · ' + esc(a.name || 'rule') + ' · ' + esc(a.symbol)
                + ' · ' + timeAgo(a.ts_ms) + ' · ' + esc(a.severity || 'info') + '</div></div>'
                + '<span class="inb-cat">' + esc(categoryOf(a.kind)) + '</span></div>';
        }).join('');
        body.querySelectorAll('.inb-tile').forEach((tile) => { tile.onclick = () => readTile(tile); });
    }

    /* ── actions ────────────────────────────────────────────────────────────── */

    function act(action, extra) {
        const body = Object.assign({ action: action }, extra || {});
        return window.api('/api/atlas/notifications', { method: 'POST', body: body });
    }

    function readTile(tile) {
        const ts = Number(tile.getAttribute('data-ts')) || 0;
        const sym = tile.getAttribute('data-sym');
        const view = tile.getAttribute('data-view-to');
        if (ts > Number(state.prefs.read_ms || 0)) {
            state.prefs.read_ms = ts;
            state.unread = Math.max(0, state.unread - 1);
        }
        void act('read', { ts_ms: ts });
        paint();
        if (sym && typeof searchActivateSymbol === 'function') searchActivateSymbol(sym, { view: view });
    }

    function load() {
        return window.api('/api/atlas/notifications').then(function (res) {
            if (!res || res.ok === false) return res;
            state.items = Array.isArray(res.items) ? res.items : [];
            state.unread = Number(res.unread) || 0;
            state.prefs = Object.assign({}, state.prefs, res.prefs || {});
            const dnd = $('inboxDnd');
            if (dnd) dnd.checked = !!state.prefs.dnd;
            const pri = $('inboxPriority');
            if (pri) pri.checked = !!state.prefs.priority;
            paint();
            return res;
        }).catch(function () { /* offline: the last paint stays */ });
    }

    /* ── boot ───────────────────────────────────────────────────────────────── */

    function boot() {
        const dnd = $('inboxDnd');
        if (dnd) dnd.onchange = function () {
            state.prefs.dnd = !!dnd.checked;
            void act('dnd', { dnd: state.prefs.dnd });
            paintBadge();
        };
        const pri = $('inboxPriority');
        if (pri) pri.onchange = function () {
            state.prefs.priority = !!pri.checked;
            void act('priority', { priority: state.prefs.priority });
            paint();
        };
        const readAll = $('inboxReadAll');
        if (readAll) readAll.onclick = function () { void act('read_all').then(() => load()); };
        const refresh = $('inboxRefresh');
        if (refresh) refresh.onclick = function () { void load(); };
        const wrap = window.showView;
        if (typeof wrap === 'function') {
            window.showView = function (name) {
                const out = wrap.apply(this, arguments);
                if (name === 'inbox') setTimeout(load, 300);
                return out;
            };
        }
        timer = setInterval(function () { if (onScreen()) load(); }, POLL_MS);
        void load();
    }

    /* Chain onto the socket's dispatcher: a fired alert bumps the badge immediately (unless DND)
       and refreshes the tiles when the view is watching. */
    (function chainOnEvent() {
        const original = (typeof window.atlasOnEvent === 'function') ? window.atlasOnEvent : null;
        window.atlasOnEvent = function (channel, data) {
            if (typeof original === 'function') original(channel, data);
            if (channel === 'alert') {
                if (!state.prefs.dnd) state.unread += 1;
                paintBadge();
                if (onScreen()) load();
            }
        };
    })();

    window.OFAPINBOX = { load: load, state: function () { return state; },
        CATEGORIES: CATEGORIES, SURFACE_FOR_KIND: SURFACE_FOR_KIND, categoryOf: categoryOf };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
