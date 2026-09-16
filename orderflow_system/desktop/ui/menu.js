/* menu.js — the app's front door: workspaces, purpose-grouped panels, free-data connections,
 * a discoverable hotkey map and a status bar. Everything here is built on the app's own views
 * and endpoints; nothing is decorative.
 *
 * Panel taxonomy (grouped by what you are doing, not by module name):
 *   Order flow  — Engine, Order Flow, Heatmap, Depth, Time & Sales, CVD, Profile, Frames
 *   Analytics   — Chart, Scanner, Trackers, Signals, Replay, VWAP/Steady cards
 *   Trading     — Strategy, Performance, Alerts
 *   Information — Overview, Instruments, Studies, Logs, Settings
 */
(function () {
    'use strict';

    const GROUPS = [
        { name: 'Order flow', items: [
            ['ofx', 'Engine', 'footprint matrix, DOM heatmap, sweeps, HUD'],
            ['orderflow', 'Order Flow', 'bid/ask per level, POC, value area'],
            ['heatmap', 'Heatmap', 'resting liquidity over time'],
            ['depth', 'Depth', 'live order book ladder'],
            ['tape', 'Time & Sales', 'every print, newest first'],
            ['cvd', 'CVD', 'cumulative delta + pro multi-anchor'],
            ['profile', 'Profile', 'volume profile by price'],
            ['frames', 'Frames', 'per-bar detail sheets'],
        ] },
        { name: 'Analytics', items: [
            ['chart', 'Chart', 'candles with studies and markers'],
            ['scanner', 'Scanner', 'ranked opportunities across symbols'],
            ['trackers', 'Trackers', 'correlation, dots, cross-venue reads'],
            ['signals', 'Signals', 'detections with strength and context'],
            ['replay', 'Replay', 'step through stored sessions'],
        ] },
        { name: 'Trading', items: [
            ['strategy', 'Strategy', 'rule sets and their live state'],
            ['performance', 'Performance', 'session and per-signal stats'],
            ['alerts', 'Alerts', 'thresholds and notifications'],
        ] },
        { name: 'Information', items: [
            ['overview', 'Overview', 'the session at a glance'],
            ['instruments', 'Instruments', 'what is streaming and how'],
            ['studies', 'Studies', 'indicator modules'],
            ['logs', 'Logs', 'what the app is doing'],
            ['settings', 'Settings', 'config, sources, appearance'],
        ] },
        { name: 'Connections', items: [] },
    ];

    const FREE_SOURCES = [
        ['bybit', 'Bybit', 'public WS + REST — trades, order book depth, candles, no key', true],
        ['binance', 'Binance Futures', 'public market data — trades, depth, candles, no key'],
        ['okx', 'OKX', 'public market data — trades, depth, candles, no key'],
        ['hyperliquid', 'Hyperliquid', 'public API — trades, book, candles, no key'],
        ['alpaca', 'Alpaca crypto', 'keyless crypto quotes and bars (no book)', true],
        ['mt5', 'MetaTrader 5', 'your local terminal — free if it is installed here', true],
    ];

    /* The hotkey sheet renders from OFAPKEYS (keys.js) — the app's one shortcut map. The
       hand-written list that used to live here drifted from the real bindings; it is gone. */

    const state = { open: false, filter: '', workspace: 'default', sources: [], active: '' };

    function el(id) { return document.getElementById(id); }
    /* The shell's api() (ui.js) is the app's one fetch wrapper. A bare `api` here would name THIS
       function — the guard would be checking itself, the call would recurse, and the RangeError
       lands in every caller's catch (measured: /sources never loaded and the ☰ menu ran on its
       fallback list while the failure stayed invisible). Name the global. */
    function api(path, options) {
        if (typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options || {}).then((r) => r.json());
    }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    }

    /* ── workspaces: named arrangements, saved in the browser ────────────────── */
    const WS_KEY = 'ofap.workspaces';

    /* Layouts live in the config file (they follow the machine and survive a profile switch);
       the browser copy is only an offline cache so the menu still lists them when the API is
       momentarily unreachable. */
    function readWorkspaces() { return state.spaces || {}; }
    function cacheWorkspaces(all) {
        state.spaces = all || {};
        try { localStorage.setItem(WS_KEY, JSON.stringify(state.spaces)); } catch (err) { /* private mode */ }
    }
    async function loadWorkspaces() {
        try {
            const res = await api('/api/control/workspaces');
            if (res && res.workspaces) { cacheWorkspaces(res.workspaces); return; }
        } catch (err) { /* fall through to the cache */ }
        try { cacheWorkspaces(JSON.parse(localStorage.getItem(WS_KEY) || '{}')); } catch (err) { /* none */ }
    }
    function snapshot() {
        const view = (document.querySelector('.view.active') || {}).dataset || {};
        let ofxParams = null;
        if (window.OFX) ofxParams = { ...OFX.state.params, symbol: OFX.state.symbol };
        return { view: view.view || 'overview', ofx: ofxParams, saved: Date.now() };
    }
    function applyWorkspace(name, data) {
        if (!data) return;
        if (data.view && typeof showView === 'function') showView(data.view);
        if (data.ofx && window.OFX) {
            OFX.state.symbol = data.ofx.symbol || OFX.state.symbol;
            OFX.setParams(data.ofx);
            if (OFX.state.data.bars.length) OFX.renderLayers(true);
        }
        state.workspace = name;
        paintStatus();
    }
    async function saveWorkspace(name) {
        const data = snapshot();
        const all = readWorkspaces();
        all[name] = data;                         // optimistic, so the list updates instantly
        cacheWorkspaces(all);
        state.workspace = name;
        paintMenu(); paintStatus();
        const box = el('menuWsName');
        if (box) box.value = '';
        try {
            const res = await api('/api/control/workspaces', { method: 'POST', body: { save: { name, data } } });
            if (res && res.workspaces) cacheWorkspaces(res.workspaces);
        } catch (err) { setStatusNote('workspace kept in this browser only — the config write failed'); }
        paintMenu(); paintStatus();
    }
    async function deleteWorkspace(name) {
        const all = readWorkspaces();
        delete all[name];
        cacheWorkspaces(all);
        paintMenu();
        try {
            const res = await api('/api/control/workspaces', { method: 'POST', body: { delete: name } });
            if (res && res.workspaces) cacheWorkspaces(res.workspaces);
        } catch (err) { /* the optimistic delete stands */ }
    }

    /* ── connections: free feeds, with a real status read ───────────────────── */
    async function loadSources() {
        try {
            const res = await api('/api/control/sources');
            state.sources = (res && res.sources) || [];
            state.active = (res && res.active) || '';
        } catch (err) {
            state.sources = [];
        }
        paintMenu();
        paintStatus();
    }
    async function useSource(id) {
        setStatusNote('switching source → restarting the engine…');
        let res = null;
        try {
            res = await api('/api/control/source', { method: 'POST', body: { source: id } });
        } catch (err) { setStatusNote('source switch failed: ' + err); return; }
        if (res && res.ok === false) { setStatusNote('refused: ' + (res.error || 'unknown source')); return; }
        const restarted = !!(res && res.engine && res.engine.restarted !== false && res.engine.ok !== false);
        setStatusNote(restarted
            ? `engine restarted on ${id}`
            : (res && res.note ? res.note : `source set to ${id}`));
        await loadSources();
        if (window.OFX && !window.OFAP_PAUSED) OFX.renderLayers(true);
    }

    function setStatusNote(text) {
        state.note = text;
        if (el('statusHint')) el('statusHint').textContent = text || 'Ctrl+K palette · P pause · ? hotkeys · ☰ menu';
    }
    /* Other modules report through the same line (the Sierra integration's plan chip is the first);
       it is a global on purpose so a view does not have to reach into this one. */
    window.setStatusNote = setStatusNote;

    /* ── painting ────────────────────────────────────────────────────────────── */
    function paintMenu() {
        const host = el('menuBody');
        if (!host) return;
        const filter = state.filter.toLowerCase();
        const match = (label, hint) => !filter
            || label.toLowerCase().includes(filter) || (hint || '').toLowerCase().includes(filter);
        const groups = GROUPS.map((group) => {
            if (group.name === 'Connections') {
                const rows = state.sources.length ? state.sources : FREE_SOURCES.map(([id, name, hint, wired]) => ({ id, name, hint, wired, status: 'unknown' }));
                const items = rows.filter((s) => match(s.name, s.hint || ''));
                if (!items.length) return '';
                return `<div class="menu-group"><div class="menu-group-title">Connections · free data</div>`
                    + items.map((s) => {
                        const on = s.id === state.active;
                        const dot = s.status === 'ok' ? 'ok' : (s.status === 'unreachable' ? 'bad' : 'idle');
                        const usable = s.wired !== false;
                        return `<button class="menu-item${usable ? '' : ' menu-item-off'}" ${usable ? `data-source="${esc(s.id)}"` : 'disabled'}`
                            + ` title="${esc(usable ? 'switch the engine to this source' : 'reachable, but this build has no feed adapter for it yet')}">`
                            + `<span class="dot ${dot}"></span>`
                            + `<span class="menu-label">${esc(s.name)}${on ? ' <em>· active</em>' : ''}</span>`
                            + `<span class="menu-hint">${esc(usable ? (s.hint || '') : 'no adapter in this build yet')}</span></button>`;
                    }).join('')
                    + `</div>`;
            }
            const items = group.items.filter(([id, label, hint]) => match(label, hint));
            if (!items.length) return '';
            return `<div class="menu-group"><div class="menu-group-title">${esc(group.name)}</div>`
                + items.map(([id, label, hint]) => `<button class="menu-item" data-view="${esc(id)}">`
                    + `<span class="menu-label">${esc(label)}</span><span class="menu-hint">${esc(hint)}</span></button>`).join('')
                + `</div>`;
        }).join('');

        const all = readWorkspaces();
        const names = Object.keys(all).sort();
        const wsList = names.length
            ? names.map((name) => `<span class="menu-ws"><button data-ws-load="${esc(name)}">${esc(name)}</button>`
                + `<button class="menu-ws-x" data-ws-del="${esc(name)}" title="delete this workspace">×</button></span>`).join('')
            : '<span class="dim">no saved workspaces yet</span>';

        host.innerHTML = `<div class="menu-col">
            <div class="menu-group"><div class="menu-group-title">Workspaces</div>
              <div class="menu-row"><input id="menuWsName" placeholder="name this layout…" size="16">
                <button id="menuWsSave">Save</button>
                <button id="menuWsReset">Reset to saved</button></div>
              <div class="menu-row menu-ws-list">${wsList}</div>
            </div>
            <div class="menu-group"><div class="menu-group-title">Help</div>
              <button class="menu-item" id="menuHelpCentre"><span class="menu-label">Help Centre</span><span class="menu-hint">everything, searchable — F1 · Simple or Advanced</span></button>
              <button class="menu-item" id="menuHotkeys"><span class="menu-label">Hotkeys</span><span class="menu-hint">the full map, with scopes</span></button>
              <button class="menu-item" id="menuGuide"><span class="menu-label">Guide</span><span class="menu-hint">how the panels fit together</span></button>
            </div>
          </div>
          <div class="menu-col">${groups}</div>`;

        host.querySelectorAll('[data-view]').forEach((b) => { b.onclick = () => { close(); showView(b.dataset.view); }; });
        host.querySelectorAll('[data-source]').forEach((b) => { b.onclick = () => void useSource(b.dataset.source); });
        host.querySelectorAll('[data-ws-load]').forEach((b) => { b.onclick = () => { applyWorkspace(b.dataset.wsLoad, readWorkspaces()[b.dataset.wsLoad]); close(); }; });
        host.querySelectorAll('[data-ws-del]').forEach((b) => { b.onclick = () => deleteWorkspace(b.dataset.wsDel); });
        if (el('menuWsSave')) el('menuWsSave').onclick = () => saveWorkspace((el('menuWsName').value || '').trim() || 'layout ' + (names.length + 1));
        if (el('menuWsReset')) el('menuWsReset').onclick = () => applyWorkspace(state.workspace, readWorkspaces()[state.workspace]);
        if (el('menuHelpCentre')) el('menuHelpCentre').onclick = () => {
            close();
            if (window.OFAPHELP && typeof OFAPHELP.open === 'function') OFAPHELP.open('');
            else showView('help');
        };
        if (el('menuHotkeys')) el('menuHotkeys').onclick = () => { close(); showHotkeys(true); };
        if (el('menuGuide')) el('menuGuide').onclick = () => { close(); if (typeof showHelp === 'function') showHelp(); else showView('overview'); };
    }

    function paintStatus() {
        const src = state.sources.find((s) => s.id === state.active);
        if (el('statusSource')) el('statusSource').textContent = src ? src.name + (src.status === 'unreachable' ? ' · unreachable' : ' · free') : (state.active || '—');
        if (el('statusWorkspace')) el('statusWorkspace').textContent = state.workspace;
        if (el('statusHint')) el('statusHint').textContent = 'Ctrl+K palette · P pause · ? hotkeys · ☰ menu';
    }

    function paintHotkeys() {
        const host = el('hotkeySheet');
        if (!host) return;
        const rows = (window.OFAPKEYS && OFAPKEYS.list) ? OFAPKEYS.list() : [];
        host.innerHTML = `<div class="overlay-title">Hotkeys</div>`
            + (rows.length
                ? `<table class="hk-table"><thead><tr><th>Keys</th><th>Action</th><th>Scope</th></tr></thead><tbody>`
                  + rows.map((r) => `<tr><td class="hk-keys">${esc(r.keys)}</td><td>${esc(r.label)}</td>`
                    + `<td class="hk-scope ${r.scope === 'Global' ? 'on' : ''}">${esc(r.scope)}</td></tr>`).join('')
                  + `</tbody></table>`
                : '<div class="dim">the shortcut map is still loading…</div>')
            + `<div class="dim">Generated from the one shortcut map (keys.js), so every key the app honours is here — and no key fires while the focus is in a field.</div>`;
    }

    /* ── open / close / keys ─────────────────────────────────────────────────── */
    function open() {
        state.open = true;
        if (el('menuPanel')) el('menuPanel').classList.add('on');
        if (el('menuBtn')) el('menuBtn').setAttribute('aria-expanded', 'true');
        const box = el('menuFilter');
        if (box) { box.value = ''; state.filter = ''; box.focus(); }
    }
    function close() {
        state.open = false;
        if (el('menuPanel')) el('menuPanel').classList.remove('on');
        if (el('menuBtn')) el('menuBtn').setAttribute('aria-expanded', 'false');
    }
    function showHotkeys(on) {
        const host = el('hotkeySheet');
        if (!host) return;
        if (on) paintHotkeys();
        host.classList.toggle('on', on !== false);
    }

    async function wire() {
        await loadWorkspaces();
        paintMenu();
        paintStatus();
        loadSources();
        if (el('menuBtn')) el('menuBtn').onclick = (ev) => { ev.stopPropagation(); state.open ? close() : open(); };
        if (el('menuClose')) el('menuClose').onclick = close;
        if (el('hotkeyClose')) el('hotkeyClose').onclick = () => showHotkeys(false);
        if (el('menuFilter')) el('menuFilter').oninput = (ev) => { state.filter = ev.target.value; paintMenu(); };
        document.addEventListener('click', (ev) => {
            const panel = el('menuPanel');
            if (state.open && panel && !panel.contains(ev.target) && ev.target !== el('menuBtn')) close();
        });
        /* The keys that used to live here are in keys.js's map now — Escape and 1-9 in the core,
           the palette in search.js, and this sheet's own `?` registered below. F1 belongs to the Help
           Centre (§79) and is bound there, so it is not claimed twice: the first registration wins a
           tie, which is exactly how F1 would have kept opening the hotkey sheet instead. */
        if (window.OFAPKEYS) {
            OFAPKEYS.bind({ id: 'hotkey-sheet', keys: ['?'], scope: 'Global',
                label: 'this hotkey map', run: () => showHotkeys(true) });
        }
        document.addEventListener('ofap:paused', paintStatus);
    }

    window.OFAPMenu = { open, close, showHotkeys, saveWorkspace, deleteWorkspace, readWorkspaces,
        loadWorkspaces, GROUPS, state };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
    else wire();
})();
