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
            ['ofx', 'Engine', 'footprint matrix, DOM heatmap, sweeps, HUD', 'footprint dom heat map sweeps hud'],
            ['orderflow', 'Order Flow', 'bid/ask per level, POC, value area', 'poc value area levels bid ask imbalance'],
            ['heatmap', 'Heatmap', 'resting liquidity over time', 'liquidity resting book depth map'],
            ['depth', 'Depth', 'live order book ladder', 'book ladder dom levels queue'],
            ['tape', 'Time & Sales', 'every print, newest first', 'tape prints time sales speed prints'],
            ['cvd', 'CVD', 'cumulative delta + pro multi-anchor', 'delta cumulative anchor divergence'],
            ['profile', 'Profile', 'volume profile by price', 'volume profile poc vah val histogram'],
            ['frames', 'Frames', 'per-bar detail sheets', 'per bar detail sheet bars'],
        ] },
        { name: 'Analytics', items: [
            ['chart', 'Chart', 'candles with studies and markers', 'candles bars studies markers drawings'],
            ['scanner', 'Scanner', 'ranked opportunities across symbols', 'scan rank screener opportunities'],
            ['trackers', 'Trackers', 'correlation, dots, cross-venue reads', 'correlation cross venue basis dots'],
            ['signals', 'Signals', 'detections with strength and context', 'detections strength context setups'],
            ['replay', 'Replay', 'step through stored sessions', 'history sessions step backtest'],
        ] },
        { name: 'Trading', items: [
            ['strategy', 'Strategy', 'rule sets and their live state', 'rules automation playbook'],
            ['performance', 'Performance', 'session and per-signal stats', 'stats pnl results trades'],
            ['alerts', 'Alerts', 'thresholds and notifications', 'threshold notify trigger'],
        ] },
        { name: 'Information', items: [
            ['overview', 'Overview', 'the session at a glance', 'summary dashboard at a glance'],
            ['instruments', 'Instruments', 'what is streaming and how', 'symbols feeds subscriptions enabled'],
            ['studies', 'Studies', 'indicator modules', 'indicators modules vwap ema rsi'],
            ['logs', 'Logs', 'what the app is doing', 'events diagnostics errors'],
            ['settings', 'Settings', 'config, sources, appearance', 'preferences config theme tokens'],
        ] },
        { name: 'Connections', items: [] },
    ];

    /* The Help rows and the recent list are rows in the same walk (arrows/Enter), so they are
       described once here rather than inline in the markup below. */
    const HELP_ROWS = [
        ['menuHelpCentre', 'Help Centre', 'everything, searchable — F1 · Simple or Advanced', 'help f1 docs search'],
        ['menuHotkeys', 'Hotkeys', 'the full map, with scopes', 'keys shortcuts keyboard bindings'],
        ['menuGuide', 'Guide', 'how the panels fit together', 'guide tour walkthrough'],
    ];
    const RECENT_KEY = 'ofap.recentViews';

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

    const state = { open: false, filter: '', workspace: 'default', sources: [], active: '',
        cursor: 0, walk: [] };

    /* §144: what the drawer remembers. `walk` is the visible order the arrows step through — every
       row that does something, panels and sources and help alike. */
    function readRecent() {
        try {
            const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
            return Array.isArray(raw) ? raw.filter((x) => typeof x === 'string').slice(0, 5) : [];
        } catch (err) { return []; }
    }
    function noteRecent(id) {
        if (!id) return;
        const list = [id].concat(readRecent().filter((x) => x !== id)).slice(0, 5);
        try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch (err) { /* private mode */ }
    }
    function activeViewId() {
        const btn = document.querySelector('.nav-item.active[data-view]');
        return btn && btn.dataset.view ? btn.dataset.view : '';
    }
    function labelOf(id) {
        for (const group of GROUPS) {
            for (const item of group.items) if (item[0] === id) return item[1];
        }
        return id;
    }
    function markHit(text, filter) {
        const safe = esc(text);
        if (!filter) return safe;
        const at = safe.toLowerCase().indexOf(filter);
        if (at < 0) return safe;
        return safe.slice(0, at) + '<b class="pal-hit">' + safe.slice(at, at + filter.length) + '</b>'
            + safe.slice(at + filter.length);
    }

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
        /* Recent (File ▸ Recent): one writer for every kind — the full path, not the mirror. */
        if (window.OFAPMENUBAR_RECENT) { try { window.OFAPMENUBAR_RECENT('workspace', name); } catch (e) {} }
    }
    function applyWorkspaceByName(name) {
        const all = readWorkspaces();
        if (!all || !all[name]) { setStatusNote('workspace "' + name + '" is gone'); return; }
        applyWorkspace(name, all[name]);
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
    /* §144: after every repaint the visible rows are re-collected in DOM order, so the arrows walk
       exactly what the eye can see (panels, then help, then connections, then anything else added). */
    function bindWalk(host) {
        state.walk = Array.from(host.querySelectorAll('[data-nav]'));
        state.walk.forEach((node, i) => { node.id = 'palrow-' + i; });
        if (state.cursor >= state.walk.length) state.cursor = 0;
        paintCursor();
        state.walk.forEach((node, i) => { node.onmouseenter = () => { state.cursor = i; paintCursor(); }; });
    }
    function paintCursor() {
        const box = el('menuFilter');
        if (!state.walk.length) {
            if (box) box.removeAttribute('aria-activedescendant');
            return;
        }
        state.walk.forEach((node, i) => node.classList.toggle('pal-cur', i === state.cursor));
        const cur = state.walk[state.cursor];
        if (cur) {
            if (typeof cur.scrollIntoView === 'function') cur.scrollIntoView({ block: 'nearest' });
            if (box) box.setAttribute('aria-activedescendant', cur.id);
        }
    }
    function runCursor(delta) {
        if (!state.walk.length) return;
        state.cursor = (state.cursor + delta + state.walk.length) % state.walk.length;
        paintCursor();
    }
    function openCursor() {
        const node = state.walk[state.cursor];
        if (node && typeof node.click === 'function') node.click();
    }

    function paintMenu() {
        const host = el('menuBody');
        if (!host) return;
        const filter = state.filter.toLowerCase().trim();
        const tokens = filter.split(/\s+/).filter(Boolean);
        const first = tokens[0] || '';
        const match = (...parts) => {
            if (!tokens.length) return true;
            const hay = parts.filter(Boolean).join(' ').toLowerCase();
            return tokens.every((t) => hay.includes(t));
        };
        const openId = activeViewId();
        let found = 0;
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
                        return `<button class="menu-item pal-row${usable ? '' : ' menu-item-off'}" ${usable ? `data-source="${esc(s.id)}" data-nav` : 'disabled'}`
                            + ` title="${esc(usable ? 'switch the engine to this source' : 'reachable, but this build has no feed adapter for it yet')}">`
                            + `<span class="dot ${dot}"></span>`
                            + `<span class="menu-label">${markHit(s.name, first)}${on ? ' <em>· active</em>' : ''}</span>`
                            + `<span class="menu-hint">${esc(usable ? (s.hint || '') : 'no adapter in this build yet')}</span></button>`;
                    }).join('')
                    + `</div>`;
            }
            const items = group.items.filter(([id, label, hint, words]) => match(label, hint, words, id));
            found += items.length;
            if (!items.length) return '';
            const title = filter ? `${esc(group.name)} · ${items.length} of ${group.items.length}`
                : esc(group.name);
            return `<div class="menu-group"><div class="menu-group-title">${title}</div>`
                + items.map(([id, label, hint, words]) => `<button class="menu-item pal-row${id === openId ? ' pal-open' : ''}"`
                    + ` data-view="${esc(id)}" data-nav title="${esc(hint)}">`
                    + `<span class="menu-label">${markHit(label, first)}${id === openId ? ' <em>· open</em>' : ''}</span>`
                    + `<span class="menu-hint">${esc(hint)}</span></button>`).join('')
                + `</div>`;
        }).join('');

        const all = readWorkspaces();
        const names = Object.keys(all).sort();
        const wsList = names.length
            ? names.map((name) => `<span class="menu-ws"><button data-ws-load="${esc(name)}">${esc(name)}</button>`
                + `<button class="menu-ws-x" data-ws-del="${esc(name)}" title="Delete this workspace">×</button></span>`).join('')
            : '<span class="dim">no saved workspaces yet</span>';

        const recent = filter ? [] : readRecent().filter((id) => labelOf(id) !== id);
        const recentGroup = recent.length
            ? `<div class="menu-group"><div class="menu-group-title">Recent</div>`
                + recent.map((id) => `<button class="menu-item pal-row${id === openId ? ' pal-open' : ''}"`
                    + ` data-view="${esc(id)}" data-nav title="open it again">`
                    + `<span class="menu-label">${esc(labelOf(id))}${id === openId ? ' <em>· open</em>' : ''}</span>`
                    + `<span class="menu-hint">${id === openId ? 'you are here' : ''}</span></button>`).join('')
                + `</div>`
            : '';
        const empty = filter && !found
            ? `<div class="pal-empty">no panel, action or source matches “${esc(state.filter)}”`
                + `<button id="palClear" class="pal-clear">clear</button></div>`
            : '';

        host.innerHTML = `<div class="menu-col">
            <div class="menu-group"><div class="menu-group-title">Workspaces</div>
              <div class="menu-row"><input id="menuWsName" placeholder="name this layout…" size="16">
                <button id="menuWsSave">Save</button>
                <button id="menuWsReset">Reset to saved</button></div>
              <div class="menu-row menu-ws-list">${wsList}</div>
            </div>
            <div class="menu-group"><div class="menu-group-title">Help</div>
              ${HELP_ROWS.filter(([id, label, hint, words]) => match(label, hint, words)).map(([id, label, hint]) =>
                `<button class="menu-item pal-row" id="${id}" data-nav title="${esc(hint)}">`
                + `<span class="menu-label">${markHit(label, first)}</span>`
                + `<span class="menu-hint">${esc(hint)}</span></button>`).join('')}
            </div>
          </div>
          <div class="menu-col">${recentGroup}${empty}${groups}</div>
          <div class="pal-foot">↑↓ move · Enter open · Esc close · Ctrl+K the full palette`
            + ` <span class="dim">(panels, actions and symbols in one box)</span></div>`;

        const countBox = el('menuCount');
        if (countBox) {
            countBox.textContent = filter
                ? (found ? `${found} match${found === 1 ? '' : 'es'}` : 'no matches')
                : `${GROUPS.reduce((n, g) => n + g.items.length, 0)} panels`;
        }
        if (el('palClear')) el('palClear').onclick = () => {
            const box = el('menuFilter');
            if (box) box.value = '';
            state.filter = ''; state.cursor = 0;
            paintMenu();
            if (box) box.focus();
        };
        bindWalk(host);

        host.querySelectorAll('[data-view]').forEach((b) => { b.onclick = () => { close(); noteRecent(b.dataset.view); showView(b.dataset.view); }; });
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

    /* §117 — the sheet edits the map. A dispatched row gets a **Change** button: click it, press
       the new combination, and it is written to ui.keys in the config (keys.js applies it in the
       same breath). A chord another binding already holds is refused with the owner named —
       never silently stolen — and every change is reversible (Reset on the row, Reset all in
       the header). The sheet still renders from OFAPKEYS.list(): one list, one dispatcher. */
    const hkState = { capture: '', msg: '' };

    function hkLabel(id) {
        const rows = (window.OFAPKEYS && OFAPKEYS.list) ? OFAPKEYS.list() : [];
        const row = rows.filter((r) => r.id === id)[0];
        return row ? row.label : id;
    }

    function paintHotkeys() {
        const host = el('hotkeySheet');
        if (!host) return;
        const rows = (window.OFAPKEYS && OFAPKEYS.list) ? OFAPKEYS.list() : [];
        const anyCustom = rows.some((r) => r.custom);
        const head = (hkState.capture
            ? `<div class="hk-msg">press the new combination for “${esc(hkLabel(hkState.capture))}” — Esc cancels</div>`
            : '')
            + (hkState.msg ? `<div class="hk-msg">${esc(hkState.msg)}</div>` : '');
        host.innerHTML = `<div class="overlay-title">Hotkeys`
            + (anyCustom ? ` <button class="btn small" id="hkResetAll">Reset all changes</button>` : '')
            + `</div>` + head
            + (rows.length
                ? `<table class="hk-table"><thead><tr><th>Keys</th><th>Action</th><th>Scope</th><th></th></tr></thead><tbody>`
                  + rows.map((r) => {
                        const capturing = hkState.capture === r.id;
                        const keys = capturing
                            ? 'press…'
                            : esc(r.keys) + (r.custom ? ` <span class="dim">(was ${esc(r.defaults)})</span>` : '');
                        const edit = r.dispatched
                            ? `<button class="btn small hk-edit" data-hk="${esc(r.id)}">Change</button>`
                              + (r.custom ? ` <button class="btn small hk-reset" data-hk="${esc(r.id)}">Reset</button>` : '')
                            : '';
                        return `<tr class="${capturing ? 'hk-capturing' : ''}"><td class="hk-keys">${keys}</td>`
                            + `<td>${esc(r.label)}</td>`
                            + `<td class="hk-scope ${r.scope === 'Global' ? 'on' : ''}">${esc(r.scope)}</td>`
                            + `<td class="hk-act">${edit}</td></tr>`;
                    }).join('')
                  + `</tbody></table>`
                : '<div class="dim">the shortcut map is still loading…</div>')
            + `<div class="dim">Generated from the one shortcut map (keys.js) — every key the app honours is here, and no key fires while the focus is in a field. Change gives a row your own combination; a taken chord is refused with its owner named, and Reset brings the shipped keys back.</div>`;
        const resetAll = el('hkResetAll');
        if (resetAll) resetAll.onclick = () => resetAllKeys();
        host.querySelectorAll('.hk-edit').forEach((btn) => {
            btn.onclick = (ev) => { ev.stopPropagation(); beginCapture(btn.getAttribute('data-hk')); };
        });
        host.querySelectorAll('.hk-reset').forEach((btn) => {
            btn.onclick = (ev) => { ev.stopPropagation(); resetOneKey(btn.getAttribute('data-hk')); };
        });
    }

    /* The capture owns the keyboard while it is armed: the listener runs in the capture phase,
       so the combination never reaches the dispatcher (and never types into the page). */
    function captureKeys(ev) {
        if (!hkState.capture) return;
        ev.preventDefault();
        if (ev.stopPropagation) ev.stopPropagation();
        const key = String(ev.key || '');
        if (key === 'Escape') { hkState.capture = ''; hkState.msg = 'nothing changed'; paintHotkeys(); return; }
        if (/^(control|shift|alt|meta|altgraph|capslock|dead)$/i.test(key)) return;   // a modifier alone is not a chord
        if (!window.OFAPKEYS) return;
        const chord = OFAPKEYS.canonical(ev);
        if (!chord) return;
        const clash = OFAPKEYS.conflicts(chord, hkState.capture);
        if (clash.length) {
            hkState.msg = OFAPKEYS.pretty(chord) + ' is already taken by: '
                + clash.map((c) => c.label + ' (' + c.scope + ')').join(', ')
                + ' — press another combination, or Esc to cancel';
            paintHotkeys();
            return;
        }
        const id = hkState.capture;
        OFAPKEYS.rebind(id, [chord]);
        hkState.capture = '';
        hkState.msg = 'changed to ' + OFAPKEYS.pretty(chord);
        void saveKeys();
        OFAPKEYS.annotate();
        paintHotkeys();
    }

    function beginCapture(id) { hkState.capture = id; hkState.msg = ''; paintHotkeys(); }

    function resetOneKey(id) {
        OFAPKEYS.clearOverride(id);
        hkState.msg = 'reset “' + hkLabel(id) + '” to its shipped keys';
        void saveKeys();
        OFAPKEYS.annotate();
        paintHotkeys();
    }

    function resetAllKeys() {
        OFAPKEYS.clearAllOverrides();
        hkState.msg = 'all shortcut changes reset';
        void saveKeys();
        OFAPKEYS.annotate();
        paintHotkeys();
    }

    /* One write per change, through the standard config patch. Emptied overrides travel as []
       so the store’s rebuild (which drops them) can actually remove a stored chord — a plain
       merge would keep it. The map is always the WHOLE map, so nothing else can drift. */
    async function saveKeys() {
        try {
            await api('/api/control/config', { method: 'POST',
                body: { ui: { keys: { version: 1, overrides: OFAPKEYS.overrides() } } } });
        } catch (err) {
            hkState.msg = 'changed in this session, but saving failed: ' + err;
        }
    }

    /* ── open / close / keys ─────────────────────────────────────────────────── */
    function open() {
        state.open = true;
        /* §144: repaint on open. The drawer used to paint once at boot, so the · open marker and the
           recent rail showed whatever was true back then. */
        paintMenu();
        if (el('menuPanel')) el('menuPanel').classList.add('on');
        if (el('menuBtn')) el('menuBtn').setAttribute('aria-expanded', 'true');
        const box = el('menuFilter');
        if (box) { box.value = ''; state.filter = ''; state.cursor = 0; box.focus(); }
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
        /* §117: the rebind capture. Capture phase, so an armed capture never lets a
           combination fall through to the dispatcher or into a focused field. */
        document.addEventListener('keydown', captureKeys, true);
        if (el('menuFilter')) {
            el('menuFilter').oninput = (ev) => { state.filter = ev.target.value; state.cursor = 0; paintMenu(); };
            el('menuFilter').onkeydown = (ev) => {
                if (ev.key === 'ArrowDown') { ev.preventDefault(); runCursor(1); }
                else if (ev.key === 'ArrowUp') { ev.preventDefault(); runCursor(-1); }
                else if (ev.key === 'Home') { ev.preventDefault(); state.cursor = 0; paintCursor(); }
                else if (ev.key === 'End') { ev.preventDefault(); state.cursor = Math.max(0, state.walk.length - 1); paintCursor(); }
                else if (ev.key === 'Enter') {
                    ev.preventDefault();
                    if (state.walk.length && state.walk[state.cursor]) openCursor();
                    else if (state.walk.length) { state.cursor = 0; openCursor(); }
                }
            };
        }
        document.addEventListener('click', (ev) => {
            const panel = el('menuPanel');
            const nav = ev.target && ev.target.closest ? ev.target.closest('.nav-item[data-view]') : null;
            if (nav && nav.dataset.view) noteRecent(nav.dataset.view);
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

    /* §145: the one place that knows what a view id is called. The menubar prints stored view ids
       (`search.default_view` = "orderflow" was showing as exactly that), so it reads the labels from
       here rather than keeping a second list that could drift. */
    const VIEW_LABELS = {};
    GROUPS.forEach((group) => group.items.forEach(([id, label]) => { VIEW_LABELS[id] = label; }));
    window.OFAPVIEWS = { byId: VIEW_LABELS, groups: GROUPS };

    window.OFAPMenu = { open, close, showHotkeys, saveWorkspace, deleteWorkspace, readWorkspaces,
        loadWorkspaces, applyWorkspaceByName, GROUPS, state };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
    else wire();
})();
