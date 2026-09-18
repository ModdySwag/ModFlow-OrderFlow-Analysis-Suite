/* menubar.js — the application menu bar.
 *
 * Built from the reference programs he pointed at (the reference platform's File/Connections/Settings/Help over a
 * toolbar; the DTC platform's File/Chart/Trade/Window depth). Rules it follows:
 *   - every item carries its accelerator, right-aligned;
 *   - checkable items show a tick, changeable ones show their current value on the right;
 *   - an item that is not built yet is DISABLED with the reason in its tooltip — never a mystery;
 *   - the Chart menu is the ACTIVE view's menu, and its contents come from /api/control/params,
 *     the same registry the settings dialogs will render, so the two cannot drift;
 *   - Alt focuses the bar, arrows walk it, typing jumps, Enter/Space opens, Esc closes;
 *   - submenus open on hover after a short delay, as a Windows menu does.
 *
 * Nothing here duplicates a panel: items call the app's own functions (showView, api, toast, openWizard)
 * or its own endpoints.
 */
(function () {
    'use strict';

    const el = (id) => document.getElementById(id);
    const state = {
        bar: null, open: null, itemMap: null, params: null, sources: [], active: '',
        workspaces: {}, booted: false, view: 'overview',
        layouts: {}, layoutVersions: {}, layoutMode: 'classic',
    };

    function api(path, options) {
        /* The app's own helper posts JSON when handed a body (ui.js `api`); defer to it so this
           module behaves exactly like every other one. */
        if (typeof window.api === 'function') return window.api(path, options);
        const opts = options ? { ...options } : undefined;
        if (opts && opts.body) {
            opts.body = JSON.stringify(opts.body);
            opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
        }
        return fetch(path, opts).then((r) => r.json());
    }
    function note(text) {
        const host = el('statusHint');
        if (host) host.textContent = text || '';
    }
    function closeAll() {
        /* The visible state is the SLOT's `.open` (the CSS shows `.mb-slot.open .mb-menu`), so
           clearing only the dropdown's own class left the menu on screen — this was why clicking
           away did not dismiss it. Clear both. */
        state.open = null;
        state.itemMap = null;
        if (!state.bar) return;
        state.bar.querySelectorAll('.mb-slot.open').forEach((slot) => slot.classList.remove('open'));
        state.bar.querySelectorAll('.mb-menu.open').forEach((m) => m.classList.remove('open'));
    }

    /* ── item helpers ─────────────────────────────────────────────────────── */
    const sep = () => ({ separator: true });
    const planned = (label, reason, accel) => ({ label, accel, disabled: true, reason });

    function viewItems() {
        /* T4/A-corr: view items only — the Setup button is not a panel, and counting it put
           "1" on the wizard and shifted every digit in this list by one. */
        const items = [...document.querySelectorAll('.rail .nav-item[data-view]')].map((btn, i) => ({
            label: btn.textContent.trim().replace(/\s+/g, ' '),
            accel: i < 9 ? String(i + 1) : '',
            checked: btn.classList.contains('active'),
            run: () => {
                /* The Chart menu is the active view's menu, so switching from here must re-point it
                   before the dropdown is next opened (otherwise it describes the previous view). */
                state.view = btn.dataset.view;
                if (window.showView) window.showView(btn.dataset.view);
            },
        }));
        return [{
            label: 'All panels…', accel: '/', run: () => { const b = el('menuBtn'); if (b) b.click(); },
        }, sep()].concat(items, [sep(),
            { label: 'Windows & layouts…', run: () => { if (window.OFAPWINDOWS && OFAPWINDOWS.open) OFAPWINDOWS.open(); } },
            { label: 'Legend panel', checked: legendOpen(), run: toggleLegend },
            { label: 'Menu bar', accel: 'B', checked: !(window.OFAPCHROME && OFAPCHROME.hidden('menubar')), run: toggleMenubar },
            { label: 'Rail', accel: 'R', checked: !(window.OFAPCHROME && OFAPCHROME.hidden('rail')), run: toggleRail },
            { label: 'Status bar', checked: !(window.OFAPCHROME && OFAPCHROME.hidden('status')), run: toggleStatus },
            { label: 'Full screen (zen)', checked: document.querySelector('.app.zen'), run: toggleZen },
            sep(),
            planned('Reset rail order', 'phase 5 — the profile store owns layouts'),
            ...viewDefaultsItems(),
        ]);
    }

    /* ── T6/A15: this view's settings — remember / restore / factory ────────────────

    /* Which config paths a view's snapshot covers. Mirrors `config_store.VIEW_DEFAULT_MAP`;
       `test_t6_menus.py` pins the two equal, so a snapshot can never name a path the store would
       refuse to carry back. */
    const VIEW_DEFAULTS_MAP = { chart: ['ui.chart'], logs: ['ui.logs'], heatmap: ['atlas.heatmap'],
        tape: ['atlas.tape'], cvd: ['atlas.cvd'], profile: ['atlas.market_profile'],
        ofx: ['ofx', 'atlas.ofx'] };

    function pathGet(root, path) {
        return path.split('.').reduce(function (n, k) {
            return (n && typeof n === 'object') ? n[k] : undefined;
        }, root);
    }
    function pathPatch(root, path, sub) {
        const parts = path.split('.');
        let node = root;
        parts.forEach(function (part, i) {
            if (i === parts.length - 1) { node[part] = sub; return; }
            node = node[part] = (node[part] && typeof node[part] === 'object') ? node[part] : {};
        });
        return root;
    }
    /* `S` is ui.js's top-level binding, not window.S (see the T5 lesson in the skill). */
    function cfgNow() {
        try { return (typeof S !== 'undefined' && S && S.config) ? S.config : null; }
        catch (e) { return null; }
    }
    function adoptConfig(cfg) {
        try { S.config = cfg; } catch (e) { /* the next read retries */ }
        if (window.OFAPFRESH && OFAPFRESH.setWindows) OFAPFRESH.setWindows(((cfg || {}).atlas || {}).freshness);
        /* the canvases re-measure and repaint on their own polls; a relayout makes it immediate */
        document.dispatchEvent(new CustomEvent('ofap:relayout'));
    }
    async function rememberView(view) {
        const paths = VIEW_DEFAULTS_MAP[view] || [];
        const cfg = cfgNow();
        if (!cfg) { note('the settings have not loaded yet'); return; }
        const snap = {};
        paths.forEach(function (p) {
            const sub = pathGet(cfg, p);
            if (sub && typeof sub === 'object') snap[p] = JSON.parse(JSON.stringify(sub));
        });
        try {
            const r = await api('/api/control/config', { method: 'POST', body: { ui: { view_defaults: { [view]: snap } } } });
            adoptConfig(r.config);
            note('remembered this view’s settings (' + Object.keys(snap).length + ' block'
                + (Object.keys(snap).length === 1 ? '' : 's') + ')');
        } catch (e) { note('the store refused: ' + e); }
    }
    async function restoreView(view, snap) {
        const patch = {};
        Object.keys(snap).forEach(function (p) { pathPatch(patch, p, snap[p]); });
        try {
            const r = await api('/api/control/config', { method: 'POST', body: patch });
            adoptConfig(r.config);
            note('restored the remembered settings for ' + view);
        } catch (e) { note('the store refused: ' + e); }
    }
    async function factoryView(view) {
        const paths = VIEW_DEFAULTS_MAP[view] || [];
        try {
            const d = await api('/api/control/config/defaults');
            const def = (d && d.config) || null;
            if (!def) { note('the defaults are unavailable'); return; }
            const patch = {};
            paths.forEach(function (p) {
                const sub = pathGet(def, p);
                if (sub && typeof sub === 'object') pathPatch(patch, p, sub);
            });
            const r = await api('/api/control/config', { method: 'POST', body: patch });
            adoptConfig(r.config);
            note('reset this view to factory — engine-side values apply at the next engine start');
        } catch (e) { note('the store refused: ' + e); }
    }

    /* The View menu's tail: the active view's own settings trio, or an honest sentence when the
       view keeps nothing of its own. */
    function viewDefaultsItems() {
        /* Resolve the view LIVE: `state.view` only tracks rail clicks, and a view reached by the
           palette, the scanner or a script must not leave this menu talking about the last rail
           click's panel. */
        const activeEl = document.querySelector('.view.active[data-view]');
        const view = (activeEl && activeEl.getAttribute('data-view')) || state.view;
        const vmap = VIEW_DEFAULTS_MAP[view];
        const out = [sep()];
        if (!vmap) {
            out.push({ label: 'This view keeps no settings of its own', disabled: true,
                       reason: 'its panels read the shared Settings surface' });
            return out;
        }
        const cfg = cfgNow();
        const stored = (cfg && cfg.ui && cfg.ui.view_defaults && cfg.ui.view_defaults[view]) || null;
        out.push({ header: 'This view — settings (' + view + ')' });
        out.push({ label: 'Remember this view’s settings',
                   hint: 'snapshot ' + vmap.join(' · ') + ' so you can come back to it after experimenting',
                   run: () => rememberView(view) });
        out.push(stored
            ? { label: 'Restore the remembered settings', run: () => restoreView(view, stored) }
            : { label: 'Restore the remembered settings', disabled: true,
                reason: 'nothing remembered for this view yet' });
        out.push({ label: 'Reset this view to factory',
                   hint: 'back to the shipped values for ' + vmap.join(' · '),
                   run: () => factoryView(view) });
        return out;
    }

    function legendOpen() {        const panel = el('ofxLegendPanel');
        if (!panel) return false;
        return !panel.classList.contains('ofx-leg-collapsed');
    }
    function toggleLegend() {
        const panel = el('ofxLegendPanel');
        if (!panel) { note('the legend lives in the Engine view'); return; }
        const btn = el('ofxLegendToggle');
        if (btn) btn.click();
        if (state.view !== 'ofx' && window.showView) window.showView('ofx');
    }
    /* §91: chrome.js owns the toggles (persistence + the B/R keys live there); these wrappers
       keep the View menu's own behaviour and its running commentary. */
    function toggleRail() {
        if (!window.OFAPCHROME) return;
        note('rail ' + (OFAPCHROME.toggle('rail') ? 'hidden' : 'shown'));
    }
    function toggleMenubar() {
        if (!window.OFAPCHROME) return;
        const on = OFAPCHROME.toggle('menubar');
        note(on ? 'menu bar hidden — press B to bring it back' : 'menu bar shown');
    }
    function toggleStatus() {
        if (window.OFAPCHROME) OFAPCHROME.toggle('status');
    }
    function toggleZen() {
        if (!window.OFAPCHROME) return;
        note(OFAPCHROME.zen() ? 'zen mode — chrome hidden (View ▸ Full screen)' : 'chrome restored');
    }

    function sourceItems() {
        const rows = state.sources.length ? state.sources : FALLBACK_SOURCES;
        return rows.map((s) => ({
            label: s.name + (s.id === state.active ? '  · active' : ''),
            checked: s.id === state.active,
            hint: s.hint || '',
            disabled: s.wired === false,
            reason: s.wired === false ? 'no feed adapter in this build yet' : '',
            run: () => switchSource(s.id, s.name),
        }));
    }
    const FALLBACK_SOURCES = [
        { id: 'bybit', name: 'Bybit', hint: 'public WS + REST' },
        { id: 'binance', name: 'Binance Futures', hint: 'public market data' },
        { id: 'okx', name: 'OKX', hint: 'public market data' },
        { id: 'hyperliquid', name: 'Hyperliquid', hint: 'public API' },
        { id: 'alpaca', name: 'Alpaca crypto', hint: 'keyless crypto quotes' },
        { id: 'mt5', name: 'MetaTrader 5', hint: 'your local terminal' },
    ];
    async function switchSource(id, name) {
        note(`switching source → ${name}…`);
        try {
            const res = await api('/api/control/source', { method: 'POST', body: { source: id } });
            state.active = id;
            note(res && res.ok === false ? `refused: ${res.error || 'unknown source'}`
                : `engine restarted on ${name}`);
            await loadSources();
            if (window.OFX && !window.OFAP_PAUSED) OFX.renderLayers(true);
        } catch (err) { note('source switch failed: ' + err); }
    }

    /* Explicit routes, not a template: `audit_ui_refs.py` matches literal paths against the FastAPI
       routes, and a built string is invisible to it (it caught this on the first run). */
    const ENGINE_ROUTES = { start: '/api/control/engine/start', stop: '/api/control/engine/stop',
                            restart: '/api/control/engine/restart' };
    async function engine(action) {
        const path = ENGINE_ROUTES[action];
        if (!path) { note(`unknown engine action: ${action}`); return; }
        try {
            const res = await api(path, { method: 'POST', body: {} });
            note(`${action}: ${res && (res.state || (res.ok ? 'ok' : 'refused'))}`);
        } catch (err) { note(`${action} failed: ${err}`); }
    }
    /* §92: the keyboard reaches the engine through here (keys.js binds Ctrl+Alt+S/X/R). */
    window.OFAPENGINE = engine;

    /* §87 — the Run menu's launcher. One literal route (audit_ui_refs matches literals against
       the FastAPI routes); the server spawns the mode in its own console so it is visible and
       Ctrl+C-able, and answers with the honest note about the shared history store. */
    async function launchMode(mode) {
        try {
            const res = await api('/api/control/launch', { method: 'POST', body: { mode } });
            note(res && res.ok ? (res.note || `${mode} starting`) 
                               : `refused: ${(res && (res.error || res.note)) || 'unknown mode'}`);
        } catch (err) { note(`${mode} launch failed: ${err}`); }
    }

    /* ── the Chart menu: the active view's registered variables ───────────── */
    function paramGroupsForView() {
        if (!state.params || !state.params.groups) return [];
        const out = [];
        Object.keys(state.params.groups).forEach((group) => {
            const rows = state.params.groups[group].filter((p) => p.view === state.view);
            if (rows.length) out.push([group, rows]);
        });
        return out;
    }
    function paramLabel(p) {
        const value = p.kind === 'bool' ? (p.value ? 'on' : 'off') : (p.value === null || p.value === undefined ? '—' : p.value);
        return `${p.label}${p.unit ? ` (${p.unit})` : ''}`;
    }
    function paramValueText(p) {
        if (p.kind === 'bool') return p.value ? '✓' : '';
        return String(p.value);
    }
    function chartItems() {
        const groups = paramGroupsForView();
        if (!groups.length) {
            return [{ label: `${state.view} has no registered display variables`, disabled: true, reason: 'nothing to configure on this panel' }];
        }
        const items = [];
        groups.forEach(([group, rows], gi) => {
            if (gi) items.push(sep());
            items.push({ header: group });
            rows.forEach((p) => items.push({
                label: paramLabel(p),
                value: paramValueText(p),
                kind: p.kind,
                submenu: [
                    { label: p.meaning, disabled: true, reason: '' },
                    sep(),
                    p.kind === 'list'
                        ? planned('Edit list', 'phase 2 — list editor (this one is a list of numbers)')
                        : { label: 'Change…', keepOpen: true, run: () => openEditor(p) },
                    { label: `Restore default (${p.default})`, checked: false, run: () => setParam(p, p.default) },
                    sep(),
                    { label: `path: ${p.path}`, disabled: true, reason: p.applies === 'restart' ? 'needs an engine restart' : 'applies live' },
                ],
            }));
        });
        return items;
    }

    /* ── the inline editor (phase 1: one variable at a time) ──────────────── */
    let editing = null;
    function openEditor(param) {
        editing = param;
        paintOpenMenu();
    }
    function editorBlock() {
        const p = editing;
        if (!p) return '';
        const value = p.value;
        let control = '';
        if (p.kind === 'bool') {
            control = `<input type="checkbox" id="mbEditBool" ${value ? 'checked' : ''}>`;
        } else if (p.kind === 'enum') {
            control = `<select id="mbEditEnum">${(p.choices || []).map((c) =>
                `<option ${c === value ? 'selected' : ''}>${c}</option>`).join('')}</select>`;
        } else {
            control = `<input type="number" id="mbEditNum" value="${value}" min="${p.min}" max="${p.max}" step="${p.step || 1}">`
                + `<input type="range" id="mbEditRange" value="${value}" min="${p.min}" max="${p.max}" step="${p.step || 1}">`;
        }
        return `<div class="mb-editor">
            <div class="mb-editor-head">${p.label} <span class="mb-dim">${p.path}</span></div>
            <div class="mb-editor-why">${p.meaning}</div>
            <div class="mb-editor-row">${control}${p.unit ? `<span class="mb-unit">${p.unit}</span>` : ''}</div>
            <div class="mb-editor-row">
                <button class="mb-btn primary" id="mbEditApply">Apply</button>
                <button class="mb-btn" id="mbEditCancel">Cancel</button>
                <span class="mb-dim" id="mbEditState">${p.applies === 'restart' ? 'needs engine restart' : 'applies live'}</span>
            </div>
        </div>`;
    }
    async function applyEditor() {
        const p = editing;
        if (!p) return;
        let value;
        if (p.kind === 'bool') value = el('mbEditBool').checked;
        else if (p.kind === 'enum') value = el('mbEditEnum').value;
        else value = Number(el('mbEditNum').value);
        const stateLine = el('mbEditState');
        if (stateLine) stateLine.textContent = 'saving…';
        await setParam(p, value);
        editing = null;
        closeAll();
    }
    async function setParam(param, value) {
        try {
            const res = await api('/api/control/params', { method: 'POST', body: { path: param.path, value } });
            if (!res || res.ok === false) { note(`refused: ${(res && res.error) || 'unknown error'}`); return; }
            param.value = res.value;                       // adopt what the store accepted
            note(`${param.label} = ${res.value}${res.applies === 'restart' ? ' (restart the engine to apply)' : ''}`);
            applyLocally(param.path, res.value);
        } catch (err) { note('write failed: ' + err); }
    }
    /* Push the accepted value into the live module that owns it, so the picture follows the setting. */
    function applyLocally(path, value) {
        if (path === 'ofx.R' && window.OFX) OFX.setParams({ R: value });
        if (path === 'ofx.stack' && window.OFX) OFX.setParams({ stack: value });
        if (path === 'ofx.va_pct' && window.OFX) OFX.setParams({ vaPct: value });
        if (path === 'ofx.text_px' && window.OFX) OFX.setParams({ textPx: value });
        if (path === 'ofx.sweep_c' && window.OFX) OFX.setParams({ sweepC: value });
        if (path === 'ofx.min_block' && window.OFX) OFX.setParams({ minBlock: value });
        if (path === 'ofx.lambda_ms' && window.OFX) OFX.setParams({ lambda: value });
        if (path.startsWith('audio.') && window.OFAPAUDIO) {
            /* The Tape view's Chart menu owns the audio paths; the player adopts the accepted
               value so the sound follows the switch without a config round trip. */
            OFAPAUDIO.setParam(path.slice('audio.'.length), value);
        }
        if (path.startsWith('expression.')) {
            /* Both chart surfaces keep their own mode + palette, and the menu has no idea which is
               live: announce the write instead of calling into either one. */
            document.dispatchEvent(new CustomEvent('ofap:expression', { detail: { path: path, value: value } }));
        }
        if (path.startsWith('atlas.') && window.OFAPAtlasSettings && OFAPAtlasSettings.reload) OFAPAtlasSettings.reload();
    }

    /* ── the Layout menu: the terminal's arrangements, and the workspace switch ────────────────────
       The store (GET/POST /api/control/layouts) is the authority and the shell holds the live
       arrangement, so this menu is a thin, keyboard-first front for it. Anything that needs a text
       answer asks for it IN PLACE: window.prompt is not guaranteed to render in the frozen shell's
       WebView, and a menu item that silently does nothing is worse than one that is disabled. */

    let prompt = null;                        // {title, value, multiline, commit}

    function askText(title, value, commit, multiline) {
        prompt = { title: title, value: value || '', multiline: !!multiline, commit: commit };
        paintOpenMenu();
        const input = el('mbPromptInput');
        if (input) { input.focus(); if (input.select) input.select(); }
    }
    function promptBlock() {
        if (!prompt) return '';
        const field = prompt.multiline
            ? `<textarea id="mbPromptInput" class="mb-input" rows="5" spellcheck="false">${escp(prompt.value)}</textarea>`
            : `<input id="mbPromptInput" class="mb-input" type="text" value="${escp(prompt.value)}" spellcheck="false">`;
        const hint = prompt.multiline ? 'Ctrl+Enter applies · Esc cancels' : 'Enter applies · Esc cancels';
        return '<div class="mb-editor mb-prompt">'
            + `<div class="mb-editor-head">${escp(prompt.title)}</div>`
            + `<div class="mb-editor-row">${field}</div>`
            + '<div class="mb-editor-row"><button class="btn small" id="mbEditApply">Apply</button>'
            + '<button class="btn small" id="mbEditCancel">Cancel</button>'
            + `<span class="mb-dim">${hint}</span></div></div>`;
    }
    function applyPrompt() {
        const input = el('mbPromptInput');
        const value = input ? input.value : '';
        const commit = prompt ? prompt.commit : null;
        prompt = null;
        closeAll();
        if (commit) commit(value);
    }
    function cancelPrompt() { prompt = null; closeAll(); }

    async function loadLayouts() {
        try {
            const res = await api('/api/control/layouts');
            state.layouts = (res && res.items) || {};
            state.layoutVersions = (res && res.versions) || {};
            state.layoutMode = (res && res.mode) || 'classic';
        } catch (err) { /* the menu reports what it has */ }
    }

    function setMode(mode) {
        const shell = window.OFAPSHELL;
        if (!shell) { note('the terminal shell is not loaded in this build'); return; }
        shell.switchTo(mode);
        state.layoutMode = mode;
        note(mode === 'terminal' ? 'Terminal mode — the panels as widgets' : 'Classic mode — one panel at a time');
    }

    /* Every layout action lands the same way: run it, re-read the store, repaint the menu, and say
       what happened in the status line — including a refusal. */
    async function layoutAction(run, okText, failText) {
        const shell = window.OFAPSHELL;
        if (!shell) { note('the terminal shell is not loaded in this build'); return; }
        try {
            const res = await run();
            await loadLayouts();
            paintOpenMenu();
            if (res && res.ok === false) note((failText || 'refused') + ' — ' + (res.error || 'no reason given'));
            else note(okText(res || {}));
        } catch (err) { note('layout action failed: ' + err); }
    }

    function widgetCount(layout) {
        const m = window.OFAPSHELL && window.OFAPSHELL.math;
        return m ? m.countWidgets(layout) : 0;
    }

    function layoutItems() {
        const shell = window.OFAPSHELL;
        const mode = shell ? shell.mode() : state.layoutMode;
        const currentId = shell ? shell.stats().layoutId : '';
        const current = shell ? shell.layout() : null;
        const locked = Boolean(shell && shell.locked && shell.locked());
        const screen = shell ? shell.screenKey() : '';
        const items = [
            { header: 'Workspace' },
            { label: 'Classic — one panel at a time', accel: 'Ctrl+Alt+T', checked: mode === 'classic',
              run: () => setMode('classic') },
            { label: 'Terminal — the panels as widgets', checked: mode === 'terminal',
              run: () => setMode('terminal') },
            sep(),
        ];
        if (!shell) {
            items.push(planned('Layouts', 'the terminal shell is not loaded in this build'));
            return items;
        }
        items.push(
            { header: 'This layout' },
            { label: 'Name', value: current ? current.name : '—', disabled: true,
              reason: 'the config store is the authority' },
            { label: 'Save now', run: () => layoutAction(() => shell.saveNow({ force: true }), () => 'layout saved') },
            { label: 'Save as…', keepOpen: true, run: () => askText('Save layout as',
                current ? current.name : 'Layout',
                (name) => layoutAction(() => shell.saveAs(name), (r) => 'saved as “' + r.name + '”')) },
            { label: 'Duplicate', run: () => layoutAction(() => shell.duplicateLayout(),
                (r) => 'duplicated as “' + r.name + '”') },
            { label: 'Delete…', keepOpen: true, run: () => askText('Type the layout name to delete it', '',
                (name) => layoutAction(() => shell.deleteLayout(name),
                    (r) => 'deleted — now on “' + r.name + '”', 'not deleted')) },
            sep(),
            { label: 'Auto-arrange this tab', disabled: mode !== 'terminal',
              reason: 'switch to Terminal mode first — the board is what gets arranged',
              run: () => { shell.arrange(); note('tiled the tab across the board'); } },
            { label: 'Reset to the starter board', run: () => layoutAction(() => shell.resetBoard(),
                (r) => 'board reset to the starter arrangement (' + r.widgets + ' widgets)') },

            { label: locked ? 'Unlock the layout' : 'Lock the layout', checked: locked,
              hint: 'a locked layout refuses move, resize, add and remove',
              run: () => { if (shell && shell.setLocked) { const on = shell.setLocked(!locked); note('layout ' + (on ? 'locked' : 'unlocked')); } } },
            sep(),
            { label: 'Save for this screen (' + (screen || 'unknown') + ')',
              run: () => layoutAction(() => shell.saveForScreen(), (r) => 'saved for ' + r.screen_key) },
            sep(),
            { label: 'Export current…', run: () => layoutAction(() => shell.exportLayout(),
                (r) => 'exported to ' + r.path) },
            { label: 'Import (paste a bundle)…', keepOpen: true, run: () => askText(
                'Paste a layout bundle (JSON)', '',
                (text) => layoutAction(() => shell.importLayout(text), (r) => 'imported “' + r.name + '”')) },
            sep(),
            { header: 'Saved layouts' },
        );
        const ids = Object.keys(state.layouts)
            .sort((a, b) => String(state.layouts[a].name).localeCompare(String(state.layouts[b].name)));
        if (!ids.length) {
            items.push({ label: 'none yet', disabled: true,
                         reason: 'the starter board is created the first time you switch to Terminal' });
        }
        ids.forEach((id) => {
            const row = state.layouts[id];
            const bits = [];
            if (id === currentId) bits.push('active');
            if (row.screen_key === screen && screen) bits.push('this screen');
            else if (row.screen_key) bits.push('saved on ' + row.screen_key);
            items.push({
                label: row.name + (bits.length ? '  · ' + bits.join(' · ') : ''),
                checked: id === currentId,
                hint: widgetCount(row) + ' widgets · ' + row.tabs.length + ' tab' + (row.tabs.length === 1 ? '' : 's'),
                run: () => layoutAction(() => shell.activateLayout(id), (r) => 'loaded “' + r.name + '”'),
            });
        });
        const versions = (state.layoutVersions && currentId && state.layoutVersions[currentId]) || [];
        if (versions.length) {
            items.push(sep(), { header: 'This layout — previous versions' });
            versions.slice(0, 3).forEach((v) => {
                const when = new Date(Number(v.at) || 0);
                const stamp = when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                items.push({
                    label: 'Restore “' + v.name + '” — saved ' + stamp,
                    run: () => layoutAction(() => shell.restoreVersion(currentId, Number(v.at) || 0),
                                            (r) => 'restored “' + ((r && r.name) || v.name) + '”'),
                });
            });
        }
        items.push(sep(), { label: ids.length + ' of 24 layouts', disabled: true,
                            reason: 'layouts live in your config file; the browser keeps no copy' });
        return items;
    }

    /* §92 — the Keys menu: the shortcut helper. Built from the same registry the dispatcher and
       the hotkey sheet read, so the menu cannot drift from what the keyboard actually does; a row
       with a rectangle runs its action, a row without one names the scope it acts in. */
    function copyKeys() {
        if (!window.OFAPKEYS) return;
        const text = OFAPKEYS.list().map((r) => (r.scope + '\t' + r.keys + '\t' + r.label)).join('\n');
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => note('shortcut list copied (' + OFAPKEYS.list().length + ' rows)'))
                .catch(() => note('the clipboard refused the copy'));
        } else {
            note('the clipboard is unavailable in this shell');
        }
    }

    function keysItems() {
        if (!window.OFAPKEYS) return [{ label: 'the shortcut map has not loaded', disabled: true }];
        const rows = OFAPKEYS.list();
        const armed = Boolean(OFAPKEYS.armed && OFAPKEYS.armed());
        const out = [
            { label: 'Shortcut sheet', accel: '?', run: () => document.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true })) },
            { label: 'Keyboard help topic', run: () => helpCentre('work.keys') },
            { label: armed ? 'Disarm the order keys' : 'Arm the order keys', checked: armed,
              hint: 'armed keys can place simulated orders: Alt+B buy · Alt+S sell · Alt+X flatten (paper only)',
              run: () => { const on = OFAPKEYS.setArmed(!OFAPKEYS.armed()); note('order keys ' + (on ? 'armed — Alt+B / Alt+S / Alt+X are live' : 'disarmed')); } },
            { label: 'Copy the shortcut list', run: () => copyKeys() },
            sep(),
        ];
        let scope = '';
        rows.forEach((row) => {
            if (row.scope !== scope) {
                scope = row.scope;
                out.push({ header: scope });
            }
            if (row.dispatched) {
                /* T6/A8 — context-valid menus: a row whose gate is false right now is shown
                   disabled, with the why the binding itself carries — the menu teaches the
                   model by omission instead of swallowing a click. */
                if (!OFAPKEYS.canDispatch(row.id)) {
                    out.push({ label: row.label, accel: row.keys, disabled: true,
                               reason: row.why || 'not available right now — its context has to match' });
                } else {
                    out.push({ label: row.label, accel: row.keys, run: () => OFAPKEYS.run(row.id) });
                }
            } else {
                out.push({ label: row.label, accel: row.keys, disabled: true,
                           reason: `acts in ${scope} (the sheet lists its context)` });
            }
        });
        return out;
    }

    /* The three ways this program runs, plus the optional add-ons — the top bar's switcher. */
    function runItems() {
        return [
            { header: 'Run mode' },
            { label: 'Desktop app — this window', checked: true,
              hint: 'the native window: full UI on the loopback, engine and history store',
              run: () => note('this window IS the desktop mode — the app is running here') },
            { label: 'Headless server on port 8099',
              hint: 'starts --headless --port 8099 in its own console — shares this profile, so stop it when the smoke test is done',
              run: () => launchMode('headless') },
            { label: 'CLI pipeline — feeds \u2192 detectors \u2192 Telegram',
              hint: 'the console pipeline (orderflow_system.main) in its own window; source tree only',
              run: () => launchMode('cli') },
            sep(),
            { header: 'Optional' },
            { label: 'MT5 feed support — optional',
              hint: 'MetaTrader 5 is never required: pick it as the source, or open Market Watch to mirror the running terminal',
              run: () => { showView('marketwatch'); note('MT5 is optional — the board mirrors your running terminal when MT5 is chosen'); } },
            { label: 'NinjaTrader 8 bridge — optional',
              hint: 'the AddOn lane: source \u2192 NinjaScript Editor F5 \u2192 the trust prompt',
              run: () => { showView('platforms'); note('NinjaTrader is optional — the Platforms view holds the bridge lane'); } },
            { label: 'Dev tooling — uv \u00b7 pytest \u00b7 node selftests',
              hint: 'the gates ship with the source tree',
              run: () => note('uv run pytest \u00b7 node ui/*.selftest.js \u00b7 ruff — CONTRIBUTING.md lists the gates') },
            sep(),
            { label: 'Market watch — the source\u2019s whole board', run: () => showView('marketwatch') },
        ];
    }

    /* ── the menus ────────────────────────────────────────────────────────── */
    /* ── R7: the Update menu — the running build, the newest release, one click to fetch.
       Its label carries a bullet while a build is waiting, and `window.OFAPMENU.refresh()`
       re-reads it when the updater's state changes (the bar is painted once, on boot). */
    function updState() { return (window.OFAPUPDATES && window.OFAPUPDATES.state) || null; }

    function updateLabel() {
        var s = updState();
        return (s && s.update_available) ? 'Update \u25cf' : 'Update';
    }

    function updateItems() {
        var s = updState();
        var latest = (s && s.latest) || null;
        var current = (s && s.current) || {};
        var items = [
            { label: 'Running build', value: String(current.display || current.version || '?'),
              disabled: true, reason: 'the build this window is running' },
        ];
        if (!s) {
            items.push({ label: 'Status', value: 'not checked yet', disabled: true,
                         reason: 'the updater has not answered yet \u2014 use Check now' });
        } else if (s.checking) {
            items.push({ label: 'Checking\u2026', disabled: true });
        } else if (latest && s.update_available) {
            items.push(
                { label: 'Download ' + String(latest.version || ''), run: () => OFAPUPDATES.download() },
                { label: 'Release notes\u2026', run: () => OFAPUPDATES.showNotes() },
                { label: 'Skip this version', run: () => OFAPUPDATES.skip(String(latest.version || '')) });
        } else if (latest && s.skipped) {
            items.push({ label: 'Skipped', value: String(latest.version || ''), disabled: true,
                         reason: 'you skipped this one \u2014 un-skip it in Settings \u25b8 Updates' });
        } else if (latest) {
            items.push({ label: 'Up to date', value: String(latest.version || ''), disabled: true,
                         reason: 'the newest release is what this window runs' });
        } else {
            items.push({ label: 'No release information', disabled: true,
                         reason: s.error || 'the repository has no releases yet' });
        }
        items.push(sep(),
                   { label: 'Check now', run: () => OFAPUPDATES.refresh(true) },
                   { label: 'Open updates folder', run: () => OFAPUPDATES.openFolder() },
                   { label: 'Release page', run: () => OFAPUPDATES.openPage() },
                   sep(),
                   { label: 'Update settings\u2026', run: () => OFAPUPDATES.openSettings() });
        return items;
    }

    function menus() {
        return [
            { id: 'file', label: 'File', items: [
                { label: 'New workspace…', keepOpen: true, run: () => saveWorkspacePrompt(true) },
                { label: 'Save workspace', accel: 'Ctrl+S', keepOpen: true, run: () => saveWorkspacePrompt(false) },
                { label: 'Open workspace', submenu: workspaceItems() },
                sep(),
                { label: 'Open user folder', run: () => openFolder('config') },
                { label: 'Open exports folder', run: () => openFolder('exports') },
                { label: 'Show log file', run: () => { openFolder('logs'); if (window.showView) showView('logs'); } },
                sep(),
                { label: 'Start engine', keyId: 'engine-start', run: () => engine('start') },
                { label: 'Stop engine', keyId: 'engine-stop', run: () => engine('stop') },
                { label: 'Restart engine', keyId: 'engine-restart', run: () => engine('restart') },
                sep(),
                planned('Import profile…', 'phase 3 — the profile store'),
                planned('Export data…', 'phase 4 — export manager (the endpoint exists: /export/save)'),
                planned('Record session…', 'phase 5 — session capture'),
                planned('Recent', 'phase 4 — recents list'),
                planned('Exit', 'the window close button closes the app'),
            ] },
            { id: 'view', label: 'View', items: viewItems() },
            { id: 'layout', label: 'Layout', items: layoutItems() },
            { id: 'draw', label: 'Drawings', items: drawItems() },
            { id: 'chart', label: 'Chart', items: chartItems() },
            { id: 'data', label: 'Data', items: [
                { header: 'Data source' },
                { label: 'Source', submenu: sourceItems() },
                { label: 'Instruments…', run: () => showView('instruments') },
                { label: 'Instrument look-up\u2026', run: () => { if (window.OFAPHINT) OFAPHINT.run('lookup'); else showView('ofx'); } },
                { label: 'Feed health', run: () => { showView('instruments'); note('tick rate and latency live in the status bar and the Instruments view'); } },
                sep(),
                { header: 'Streams' },
                { label: 'Extra Bybit streams (200-level book, liquidations)', checked: !!(state.params && extrasValue()), run: () => setExtraStreams(!extrasValue()) },
                sep(),
                planned('Timeframe / aggregation', 'phase 2 — the chart view owns its own settings'),
                planned('History & retention', 'phase 3 — storage policy (DB is ~547 MB of ticks)'),
                planned('Replay…', 'phase 2 — the Replay view exists; deep-linking comes with the settings dialogs'),
                planned('Notifications…', 'phase 2 — the Settings view already holds the channels'),
            ] },
            { id: 'profiles', label: 'Profiles', items: [
                { label: `Current: ${state.workspaces && state.workspaces.__current ? state.workspaces.__current : 'default'}`, disabled: true, reason: 'profiles arrive in phase 3' },
                sep(),
                planned('New from current…', 'phase 3 — the profile store'),
                planned('Save', 'phase 3', 'Ctrl+S'),
                planned('Save as…', 'phase 3', 'Ctrl+Shift+S'),
                planned('Load…', 'phase 3'),
                planned('Rename / Duplicate / Delete', 'phase 3'),
                planned('Import / Export…', 'phase 3'),
                planned('Backup all / Restore…', 'phase 4'),
                planned('Templates (Scalper, Day trader, Swing, Research, Low-resource)', 'phase 4'),
                planned('Autosave', 'phase 4'),
                { label: 'Open profiles folder', disabled: true, reason: 'phase 3 — the folder is created by the store' },
            ] },
            { id: 'run', label: 'Run', items: runItems() },
            { id: 'keys', label: 'Keys', items: keysItems() },
            { id: 'tools', label: 'Tools', items: [
                { label: 'Command palette', accel: 'Ctrl+K', run: openPalette },
                { label: 'Hotkeys…', accel: '?', run: () => document.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true })) },
                sep(),
                { header: 'Diagnostics' },
                { label: 'Render telemetry', run: showTelemetry },
                { label: 'Copy diagnostics', run: copyDiagnostics },
                { label: 'Client errors', run: () => { showView('logs'); note('client errors are appended to the log as "client error:" lines'); } },
                sep(),
                planned('Performance…', 'phase 2 — refresh rate, depth resolution, safe mode'),
                planned('Studies library', 'phase 2 — deep-link into the Studies view settings'),
            ] },
            { id: 'update', label: updateLabel(), items: updateItems() },
            { id: 'help', label: 'Help', items: [
                /* §79: the front door. Every item runs the app's own function; the About card at the
                   bottom is rendered from the live facts (`/api/control/help`), so the version and the
                   credits are the program's own rather than a copy that can drift. */
                { label: 'Help Centre…', accel: 'F1', run: () => helpCentre('') },
                { label: 'Search the help…', accel: 'Ctrl+Shift+H', run: () => helpCentre('') },
                { label: 'Advanced user interface', checked: helpMode() === 'advanced',
                  hint: 'every topic, including the under-the-hood material', run: () => setHelpMode('advanced') },
                { label: 'Simple interface', checked: helpMode() === 'simple',
                  hint: 'the safe subset, with the system check on top', run: () => setHelpMode('simple') },
                { label: 'Where help lives', submenu: [
                    { label: 'Status bar (the app\'s taskbar)', checked: helpDock() === 'taskbar',
                      run: () => setHelpDock('taskbar') },
                    { label: 'Floating button', checked: helpDock() === 'floating', run: () => setHelpDock('floating') },
                    { label: 'Hidden (F1 still opens it)', checked: helpDock() === 'off', run: () => setHelpDock('off') },
                ] },
                { label: helpCheckItem(), run: () => helpCheck() },
                sep(),
                { label: 'Setup guide…', run: () => { if (typeof window.openWizard === 'function') openWizard(true); else note('the wizard is available from the Overview view'); } },
                { label: 'Legend & keys', run: toggleLegend },
                { label: 'Hotkeys…', accel: '?', run: () => document.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true })) },
                { label: 'Platforms (the DTC platform DTC, the reference platform)', run: () => showView('platforms') },
                sep(),
                { about: true },
            ] },
        ];
    }
    function extrasValue() {
        const p = state.params && state.params.groups
            && Object.values(state.params.groups).flat().find((x) => x.path === 'atlas.extras_enabled');
        return p ? p.value : false;
    }
    async function setExtraStreams(on) {
        await setParam({ path: 'atlas.extras_enabled', label: 'Extra Bybit streams', applies: 'restart' }, on);
    }

    function drawItems() {
        const D = window.OFAPDRAW;
        if (!D) {
            return [planned('Drawing layer not loaded', 'reload the window — desktop/ui/drawings.js')];
        }
        const items = [{ header: 'Figures' }];
        D.TOOLS.forEach((tool) => {
            items.push({
                label: tool.label, checked: D.state.tool === tool.id, hint: tool.hint,
                run: () => D.setTool(tool.id),
            });
        });
        items.push(sep(), { header: 'Modes' });
        items.push({
            label: 'Single figure mode', checked: !!D.state.single,
            hint: 'return to Select after each figure',
            run: () => { D.state.single = !D.state.single; D.save(); },
        });
        items.push({
            label: 'Hide all drawings', checked: !!D.state.hidden,
            run: () => D.hideAll(),
        });
        items.push({
            label: `Clear all drawings (${D.drawings.length})`,
            hint: 'this view only',
            run: () => {
                const ok = !D.drawings.length || !window.confirm
                    || window.confirm(`Clear ${D.drawings.length} drawing(s) on this view?`);
                if (ok) D.clearAll();
            },
        });
        items.push(sep(), { header: 'Line colour for new drawings' });
        ['#4f8cff', '#35d07f', '#ff5d6c', '#ffd166', '#c792ea', '#e6edf7'].forEach((colour) => {
            items.push({
                label: colour, checked: D.state.style.line === colour,
                run: () => { D.state.style.line = colour; D.save(); D.paint(); },
            });
        });
        if (D.drawings.length) {
            items.push(sep(), { header: `On this view: ${D.drawings.length}` });
            D.drawings.slice(-8).reverse().forEach((draw) => {
                items.push({
                    label: `${draw.kind}${draw.text ? ` “${draw.text.slice(0, 18)}”` : ''}`,
                    hint: `${draw.a.p.toFixed(2)} → ${(draw.b || draw.a).p.toFixed(2)}`,
                    run: () => { D.setTool('select'); D.select(draw.id); },
                });
            });
        }
        return items;
    }

    function workspaceItems() {
        const names = Object.keys(state.workspaces || {}).filter((n) => !n.startsWith('__'));
        if (!names.length) return [planned('no saved workspaces yet', 'save one from this menu')];
        return names.map((name) => ({
            label: name,
            run: () => {
                if (window.OFAPMenu && OFAPMenu.applyWorkspaceByName) OFAPMenu.applyWorkspaceByName(name);
                else note(`workspace "${name}" — open ☰ to load it`);
            },
        }));
    }
    async function saveWorkspacePrompt(asNew) {
        /* §56 carry-over: asked for IN PLACE (askText renders in the open menu) — window.prompt
           is not guaranteed to render in the frozen WebView, so the old call could silently
           do nothing at all. */
        askText(asNew ? 'New workspace name' : 'Workspace name', asNew ? 'workspace' : '', async (name) => {
        if (!name) return;
        try {
            const res = await api('/api/control/workspaces', { method: 'POST', body: { save: { name, data: snapshot() } } });
            state.workspaces = (res && res.workspaces) || state.workspaces;
            note(`workspace "${name}" saved`);
        } catch (err) { note('workspace save failed: ' + err); }
        });
    }
    function snapshot() {
        const view = (document.querySelector('.view.active') || {}).dataset || {};
        let ofx = null;
        if (window.OFX) ofx = { ...OFX.state.params, symbol: OFX.state.symbol };
        return { view: view.view || state.view || 'overview', ofx, saved: Date.now() };
    }
    async function openFolder(which) {
        try {
            const res = await api('/api/control/folder/open', { method: 'POST', body: { folder: which } });
            note(res && res.ok ? `opened ${res.path}` : `could not open: ${(res && res.error) || 'unknown error'}`);
        } catch (err) { note('folder open failed: ' + err); }
    }
    function openPalette() {
        const input = el('programSearch') || document.querySelector('.palette input');
        if (input) { input.focus(); return; }
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
    }
    function showTelemetry() {
        if (!window.OFX) { note('the engine is not loaded'); return; }
        const s = OFX.stats();
        note(`frames ${s.frames} · p95 ${s.p95Ms}ms · max ${s.maxFrameMs}ms · ${s.lod} · cells ${s.heatCells} · bars ${s.barsOnScreen} · recoveries ${s.recovered}`);
        if (window.console) console.table(s);
    }
    async function copyDiagnostics() {
        let text = '';
        try {
            const res = await api('/api/control/bootstrap');
            const cfg = (res && res.config) || {};
            text = [
                'ModFlow OrderFlow Analysis Suite — diagnostics',
                `config: ${res.config_path || ''}`,
                `log: ${res.log_path || ''}`,
                `db: ${res.db_path || ''}`,
                `source: ${cfg.data_source || ''}`,
                `views loaded: ${document.querySelectorAll('.view').length}`,
                window.OFX ? `engine: ${JSON.stringify(OFX.stats()).slice(0, 400)}` : 'engine: not loaded',
            ].join('\n');
        } catch (err) { note('diagnostics failed: ' + err); return; }
        try {
            await navigator.clipboard.writeText(text);
            note('diagnostics copied to the clipboard');
        } catch (err) {
            console.log(text);
            note('clipboard blocked — diagnostics printed to the console');
        }
    }
    /* ── §79: the Help Centre's front door ──────────────────────────────────
       The menu bar asks the help module for everything it shows — the interface it is in, where its
       launcher lives, how the system check stands, and the facts the About card prints. Nothing here
       keeps a second copy of that state, so the menu and the panel cannot drift apart. */
    function helpApi() { return window.OFAPHELP || null; }
    function helpFacts() {
        const H = helpApi();
        return (H && typeof H.facts === 'function' && H.facts()) || null;
    }
    function helpCentre(query) {
        const H = helpApi();
        closeAll();
        if (H && typeof H.open === 'function') { H.open(query || ''); return; }
        if (window.showView) showView('help');
        note('the Help Centre is still loading…');
    }
    function helpMode() { const H = helpApi(); return (H && typeof H.mode === 'function' && H.mode()) || 'advanced'; }
    function setHelpMode(mode) {
        const H = helpApi();
        if (H && typeof H.setMode === 'function') { H.setMode(mode); return; }
        note('the Help Centre is still loading…');
    }
    function helpDock() { const H = helpApi(); return (H && typeof H.dock === 'function' && H.dock()) || 'taskbar'; }
    function setHelpDock(dock) {
        const H = helpApi();
        if (H && typeof H.setDock === 'function') { H.setDock(dock); return; }
        note('the Help Centre is still loading…');
    }
    function helpCheckItem() {
        const H = helpApi();
        const check = H && typeof H.check === 'function' && H.check();
        const counts = (check && check.counts) || {};
        const bad = (counts.error || 0) + (counts.warn || 0);
        return bad ? `System check — ${bad} item(s) to look at`
            : 'System check — ' + (counts.total ? 'all clear' : 'not run yet');
    }
    function helpCheck() {
        const H = helpApi();
        closeAll();
        if (H && typeof H.openCheck === 'function') { H.openCheck(); return; }
        helpCentre('system check');
    }

    /* The About card, rendered from the live facts: version, what this distribution is, who made it
       and on whose work it stands, plus the four places worth reaching and the folders it writes to.
       It carries the tool's own mark (the same badge the rail shows) — deliberately small. */
    function aboutCard() {
        const facts = helpFacts() || {};
        const H = helpApi();
        const credits = (H && typeof H.credits === 'function' && H.credits()) || {};
        const links = ((H && typeof H.links === 'function' && H.links()) || []).slice(0, 3);
        const version = facts.version
            ? `${escp(facts.version)}-${escp(facts.channel || '')}`
            : 'version loading…';
        return ''
            + '<div class="mb-about-head">'
            +   '<img src="/desktop/brand-icon.png" alt="ModFlow" width="26" height="26">'
            +   '<div><div class="mb-about-name">' + escp(facts.name || 'ModFlow OrderFlow Analysis Suite') + '</div>'
            +   '<div class="mb-about-ver">' + version + ' · ' + escp(facts.licence || 'MIT')
            +   (facts.frozen ? ' · packaged build' : ' · from source') + '</div></div>'
            + '</div>'
            + '<div class="mb-about-copy">' + escp(facts.tagline || 'Order-flow analysis workstation') + '. '
            +   'Made by <b>' + escp(credits.made_by || 'Moddy') + '</b> — '
            +   '<a href="' + escp(credits.made_by_url || 'https://moddys.net') + '" target="_blank" rel="noopener noreferrer">'
            +   escp((credits.made_by_url || 'https://moddys.net').replace(/^https?:\/\//, '')) + ' ↗</a>. '
            +   'Builds on <b>' + escp(credits.upstream || 'the original project') + '</b> (MIT) and follows '
            +   escp(credits.methodology || 'the orderflow methodology') + '.</div>'
            + (credits.thanks_line ? '<div class="mb-about-thanks">' + escp(credits.thanks_line) + '</div>' : '')
            + '<div class="mb-about-links">'
            +   links.map((l) => '<a href="' + escp(l.url) + '" target="_blank" rel="noopener noreferrer">'
                + escp(l.label) + ' ↗</a>').join('')
            + '</div>'
            + '<div class="mb-about-btns">'
            +   '<button data-about="open" title="Version, credits, thanks, links and the folders it writes to">About this program…</button>'
            +   '<button data-about="diag" title="Version, paths, source and telemetry — nothing secret">Copy diagnostics</button>'
            +   '<button data-about="folder" data-folder="config" title="Settings, drawings, alert rules, exports">User folder</button>'
            + '</div>';
    }

    /* The About card is a block, not a menu row, so its buttons are wired here (the item map does not
       cover them). Runs after every paint of an open menu. */
    function bindAbout(host) {
        const scope = host || state.bar;
        if (!scope || !scope.querySelectorAll) return;
        scope.querySelectorAll('[data-about]').forEach((btn) => {
            btn.onclick = (ev) => {
                ev.stopPropagation();
                const what = btn.dataset.about;
                if (what === 'open') {
                    closeAll();
                    const H = helpApi();
                    if (H && typeof H.openAbout === 'function') H.openAbout();
                    else helpCentre('');
                    return;
                }
                if (what === 'diag') { void copyDiagnostics(); return; }
                if (what === 'folder') { void openFolder(btn.dataset.folder || 'config'); }
            };
        });
    }

    async function about() {
        try {
            const res = await api('/api/control/bootstrap');
            note(`ModFlow OrderFlow Analysis Suite · config ${res.config_path || '?'} · log ${res.log_path || '?'}`);
            console.log('about', res);
        } catch (err) { note('about failed: ' + err); }
    }

    /* ── rendering ──────────────────────────────────────────────────────────
       Submenus render inline (indented inside the dropdown) rather than as floating popups: at this
       phase it removes the whole class of positioning bugs, and a dropdown that grows sideways stays
       readable. Every item is addressed by a key path ("chart.3.1") held in `state.itemMap`, so a
       click is a map lookup instead of a re-walk of the tree. */
    function escp(text) {
        return String(text == null ? '' : text).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    }

    function itemsHtml(items, prefix, map) {
        return items.map((item, index) => {
            const key = `${prefix}.${index}`;
            map.set(key, item);
            if (item.separator) return '<div class="mb-sep"></div>';
            if (item.header) return `<div class="mb-header">${escp(item.header)}</div>`;
            /* §79: the About card lives IN the Help dropdown (the ask: a short about under the help
               links), rendered from the live facts rather than a copy that can drift. It is a block,
               not a menu row, so it bypasses the item button path entirely. */
            if (item.about) return `<div class="mb-about">${aboutCard()}</div>`;
            const cls = ['mb-item'];
            if (item.disabled) cls.push('mb-disabled');
            if (item.submenu) cls.push('mb-has-sub');
            if (item.checked === true) cls.push('mb-checked');
            if (item.kind === 'bool' || item.kind === 'enum') cls.push('mb-knob');
            const title = item.disabled && item.reason ? item.reason : (item.hint || '');
            /* T3: a row may name a binding id (keyId) instead of a hand-typed accelerator — the
               legend then renders from the same registry the dispatcher honours, so a displayed
               key cannot drift from a real one (the §92 File-menu lie is the precedent). */
            const accelText = item.keyId && window.OFAPKEYS && typeof OFAPKEYS.accelOf === 'function'
                ? OFAPKEYS.accelOf(item.keyId)
                : (item.accel || '');
            const row = `<button class="${cls.join(' ')}" data-key="${key}" title="${escp(title)}"${item.disabled ? ' disabled' : ''}>`
                + `<span class="mb-tick">${item.checked ? '✓' : ''}</span>`
                + `<span class="mb-label">${escp(item.label)}</span>`
                + `<span class="mb-value">${escp(item.value || '')}</span>`
                + `${item.submenu ? '<span class="mb-arrow">›</span>' : ''}`
                + `<span class="mb-accel">${escp(accelText)}</span></button>`;
            if (!item.submenu) return row;
            return `<div class="mb-subwrap">${row}<div class="mb-sub">${itemsHtml(item.submenu, key, map)}</div></div>`;
        }).join('');
    }

    function paintOpenMenu() {
        const bar = state.bar;
        if (!bar) return;
        const menu = menus().find((m) => m.id === state.open);
        const host = bar.querySelector(`.mb-menu[data-menu="${state.open}"]`);
        if (!menu || !host) return;
        state.itemMap = new Map();
        host.innerHTML = promptBlock() || editorBlock() || itemsHtml(menu.items, menu.id, state.itemMap);
        bindEditor();
        bindAbout(host);
    }

    function bindEditor() {
        const apply = el('mbEditApply');
        const cancel = el('mbEditCancel');
        if (apply) apply.addEventListener('click', () => (prompt ? applyPrompt() : applyEditor()));
        if (cancel) cancel.addEventListener('click', () => { prompt = null; editing = null; closeAll(); });
        const input = el('mbPromptInput');
        if (input) {
            input.addEventListener('keydown', (ev) => {
                ev.stopPropagation();                       // typing is not a menu shortcut
                if (ev.key === 'Enter' && (!prompt.multiline || ev.ctrlKey)) { ev.preventDefault(); applyPrompt(); }
                if (ev.key === 'Escape') { ev.preventDefault(); cancelPrompt(); }
            });
            input.addEventListener('input', () => { if (prompt) prompt.value = input.value; });
        }
        const num = el('mbEditNum');
        const range = el('mbEditRange');
        if (num && range) {
            num.addEventListener('input', () => { range.value = num.value; });
            range.addEventListener('input', () => { num.value = range.value; });
        }
    }

    async function loadParams() {
        try { state.params = await api('/api/control/params'); } catch (err) { state.params = null; }
    }
    async function loadSources() {
        try {
            const res = await api('/api/control/sources');
            state.sources = (res && res.sources) || [];
            state.active = (res && res.active) || '';
        } catch (err) { /* the fallback list stands */ }
    }
    async function loadWorkspaces() {
        try {
            const res = await api('/api/control/workspaces');
            state.workspaces = (res && res.workspaces) || {};
        } catch (err) { /* none */ }
    }

    async function boot() {
        state.bar = el('menuBar');
        if (!state.bar) return;
        if (!state.booted) {
            state.booted = true;
            await Promise.all([loadParams(), loadSources(), loadWorkspaces(), loadLayouts()]);
            /* The bar owns its own dropdown layer so a menu can never be clipped by the topbar. */
            state.bar.innerHTML = menus().map((m) => `<div class="mb-slot" data-slot="${m.id}">`
                + `<button class="mb-title" data-menu="${m.id}">${escp(m.label)}</button>`
                + `<div class="mb-menu" data-menu="${m.id}"></div></div>`).join('')
                /* §92: the bar hides itself — a physical control, and the paired reveal button
                   lives in the topbar's marked spot (visible only while the bar is hidden). */
                + '<div class="mb-grow"></div>'
                + '<button class="mb-hide" id="mbHide" title="Hide the top menu bar">hide</button>';
            const hideBtn = state.bar.querySelector('#mbHide');
            if (hideBtn) hideBtn.addEventListener('click', () => { if (window.OFAPCHROME) OFAPCHROME.toggle('menubar'); });
            bind();
            /* R7: labels can change while the app runs (the Update title badges a waiting build),
               so the titles can be re-read without a page reload. */
            window.OFAPMENU = {
                refresh() {
                    if (!state.bar) return;
                    menus().forEach((m) => {
                        const btn = state.bar.querySelector(`.mb-title[data-menu="${m.id}"]`);
                        if (btn && btn.textContent !== m.label) btn.textContent = m.label;
                    });
                },
            };
            if (window.OFAPKEYS && OFAPKEYS.annotate) OFAPKEYS.annotate();
            window.addEventListener('ofap:relayout', () => { closeAll(); });
        }
        const active = document.querySelector('.view.active');
        state.view = (active && active.dataset && active.dataset.view) || state.view;
        paintOpenMenu();
    }

    function bind() {
        const bar = state.bar;
        bar.addEventListener('click', (ev) => {
            const title = ev.target.closest('.mb-title');
            if (title) {
                const id = title.dataset.menu;
                state.open = state.open === id ? null : id;
                editing = null;
                syncOpen();
                return;
            }
            const item = ev.target.closest('.mb-item');
            if (!item || item.disabled) return;
            const target = state.itemMap && state.itemMap.get(item.dataset.key);
            if (!target || !target.run) return;
            if (target.keepOpen) { target.run(); return; }   // the editor swaps content in place
            closeAll();
            target.run();
        });
        /* A top menu closes the moment you touch anything else — on mousedown, in the CAPTURE phase,
           so a panel that stops propagation (canvas drags, the tape) cannot hold it open, and the
           dropdown never sits over a gesture the user already started. Window blur and any scroll
           close it too, as a native menu does. */
        document.addEventListener('mousedown', (ev) => {
            if (!ev.target.closest || !ev.target.closest('#menuBar')) closeAll();
        }, true);
        document.addEventListener('focusin', (ev) => {
            if (state.open && ev.target.closest && !ev.target.closest('#menuBar')) closeAll();
        });
        window.addEventListener('blur', () => closeAll());
        document.addEventListener('scroll', () => closeAll(), true);
        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Tab' && state.open) closeAll();
        }, true);
        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape') { closeAll(); return; }
            if (ev.altKey && !ev.ctrlKey && !ev.metaKey) {
                const title = bar.querySelector('.mb-title');
                if (title) { ev.preventDefault(); title.focus(); }
                return;
            }
            const focused = document.activeElement;
            if (!focused || !focused.closest || !focused.closest('#menuBar')) return;
            const titles = [...bar.querySelectorAll('.mb-title')];
            const idx = titles.indexOf(focused.closest('.mb-title') || focused);
            if (ev.key === 'ArrowRight' && idx >= 0) { ev.preventDefault(); titles[(idx + 1) % titles.length].focus(); }
            if (ev.key === 'ArrowLeft' && idx >= 0) { ev.preventDefault(); titles[(idx - 1 + titles.length) % titles.length].focus(); }
            if ((ev.key === 'Enter' || ev.key === 'ArrowDown' || ev.key === ' ') && idx >= 0) {
                ev.preventDefault();
                state.open = titles[idx].dataset.menu;
                syncOpen();
                const first = bar.querySelector(`.mb-menu[data-menu="${state.open}"] .mb-item:not([disabled])`);
                if (first) first.focus();
            }
            /* Walking DOWN inside an open menu: the branch above only opens a menu from a title, so
               with an item focused ArrowDown had nowhere to go and the keyboard could only reach the
               first item of every menu (the phase-2 gate is "every item reachable by keyboard"). */
            if (ev.key === 'ArrowDown' && state.open && idx < 0) {
                const items = [...bar.querySelectorAll(`.mb-menu[data-menu="${state.open}"] .mb-item:not([disabled])`)];
                const here = items.indexOf(focused);
                if (items.length && here >= 0) { ev.preventDefault(); items[(here + 1) % items.length].focus(); }
            }
            if (ev.key === 'ArrowUp' && state.open) {
                const items = [...bar.querySelectorAll(`.mb-menu[data-menu="${state.open}"] .mb-item:not([disabled])`)];
                const here = items.indexOf(focused);
                if (items.length && here >= 0) { ev.preventDefault(); items[(here - 1 + items.length) % items.length].focus(); }
            }
        });
        /* Alt+Z (zen) is registered into keys.js's map below. It used to be a capture listener
           here with no field check at all — it fired mid-typing; the map's dispatcher fixes that. */
        if (window.OFAPKEYS) {
            OFAPKEYS.bind({ id: 'zen', keys: ['alt+z'], scope: 'Global',
                label: 'zen mode — hide the chrome', run: toggleZen });
            OFAPKEYS.document([
                { keys: '← → / ↑ ↓ / Enter', label: 'walk the menu bar, its menus and their items', scope: 'Menu bar' },
                { keys: 'Tab', label: 'close the open menu', scope: 'Menu bar' },
            ]);
        }
    }
    function syncOpen() {
        state.bar.querySelectorAll('.mb-slot').forEach((slot) => {
            slot.classList.toggle('open', slot.dataset.slot === state.open);
        });
        if (state.open) paintOpenMenu();
    }

    /* A view change changes the Chart menu; repaint lazily on the app's own events. */
    document.addEventListener('click', (ev) => {
        const nav = ev.target.closest && ev.target.closest('.rail .nav-item');
        if (nav) setTimeout(() => { state.view = nav.dataset.view; paintOpenMenu(); }, 40);
    });

    /* The shell switches modes and writes layouts behind this menu's back (its own auto-save, the
       rail button, the accelerator): keep the Saved-layouts list and the mode ticks in step. */
    document.addEventListener('ofap:shell', () => { void loadLayouts().then(() => paintOpenMenu()); });

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();

    window.OFAPMenuBar = {
        open: (id) => { state.open = id; syncOpen(); },
        /* The terminal shell owns the notion of "the panel you are working in" (in Terminal mode
           several panels are on screen at once), so it moves this pointer and opens the Chart menu —
           which is the active view's registered variables, i.e. that widget's own settings. */
        setView: (view) => { if (view) state.view = view; },
        openFor: (view) => {
            if (view) state.view = view;
            state.open = 'chart';
            syncOpen();
            return true;
        },
        menus, reload: boot, toggleZen,
    };
})();
