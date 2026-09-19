/* ══════════════════════════════════════════════════════════════════
   help.js — the Help Centre: one searchable door onto the whole program, at two depths.

   What it is
     A panel in the rail ("Help") that holds every topic in `help-data.js`, searched by the pure
     engine in `help-search.js`, plus the live system check and the About card from
     `/api/control/help`. Two interfaces over the same corpus:

       Advanced user — every topic, including the under-the-hood material and the danger zone.
       Simple        — the same entries minus `mode: 'advanced'`, with the system check on top and
                       an explicit gate (not a hidden refusal) when a search lands on an advanced
                       topic: the user is told why and can step up to Advanced in one click.

   How it is reached (four ways, deliberately)
     1. **F1** from anywhere — the app's own shortcut map carries the binding, so it is listed in the
        hotkey sheet like every other key.
     2. **Help** in the menu bar — Help Centre, search, the mode switch, where the launcher lives,
        the system check, the setup assistant, the hotkey map, and the About card.
     3. The **☰ menu**'s Help group (menu.js) — unchanged, plus a jump into the Help Centre.
     4. The **status bar dock** — the app's taskbar strip. `help.dock` decides: a search box docked
        into the status bar (default), a floating button (the quick panel), or hidden.

   Conventions it follows
     · the corpus is data (`help-data.js`) — this file renders, it does not contain prose;
     · the search is a pure module (`help-search.js`), pinned by its own selftest;
     · every action button runs the app's OWN function (`showView`, `openWizard`, the palette's key,
       `/api/control/folder/open`) rather than reimplementing a panel's behaviour;
     · preferences live in the config's `help` block (`mode`, `dock`, `recents`, `dismissed`) with a
       localStorage mirror only for the first paint, exactly as the theme does;
     · a stale window is not a code bug — the view is rebuilt from the corpus on every open, and the
       corpus is served no-store like every other module.
   ══════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    const API = '/api/control/help';
    const DATA = window.OFAPHELPSEARCH ? window.OFAPHELPDATA : null;
    const SEARCH = window.OFAPHELPSEARCH || null;
    const BRAND = '/desktop/brand-icon.png';
    const MIRROR_KEY = 'ofap.help';
    const RECENTS_MAX = 12;

    const state = {
        mode: 'advanced', dock: 'taskbar',
        recents: [], dismissed: [],
        facts: null, credits: null, links: [], check: null,
        query: '', results: null, open: '', gate: '', showDismissed: false,
        note: '', ready: false, offline: false,
        index: { index: [], vocab: [] }, cachedFor: '',
        sug: [], sugAt: -1, treeFilter: '',
    };

    /* ── tiny helpers ─────────────────────────────────────────────────────────────────────── */

    function el(id) { return document.getElementById(id); }

    function esc(text) {
        return String(text == null ? '' : text)
            .replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    }

    /* The corpus's inline markup: **bold**, `code`, *italic* — everything else is escaped, so a
       stray angle bracket in the prose cannot inject anything into the page. */
    function md(text) {
        return esc(text)
            .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/(^|\s)\*([^*\s][^*]*)\*/g, '$1<i>$2</i>')
            .replace(/\n/g, '<br>');
    }

    /* The app's own fetch wrapper (ui.js) — named through the global on purpose: a module-local
       `api()` that guards with `typeof api` checks ITSELF (see menu.js), which is how a silent
       infinite recursion shipped once already. */
    function request(path, options) {
        if (typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options || {}).then((r) => {
            if (!r.ok) throw new Error(r.status + ' ' + r.statusText + ' for ' + path);
            return r.json();
        });
    }

    function note(text) {
        const host = el('statusHint');
        if (host) host.textContent = text || '';
    }

    function toast(text) {
        note(text);
    }

    function topicById(id) {
        return (DATA && DATA.topics || []).filter((t) => t.id === id)[0] || null;
    }

    function groupLabel(id) {
        const g = (DATA && DATA.groups || []).filter((x) => x.id === id)[0];
        return g ? g.label : '';
    }

    function isAdvanced(topic) { return !!topic && topic.mode === 'advanced'; }

    function visible(topic) { return state.mode === 'advanced' || !isAdvanced(topic); }

    /* ── preferences: the config's help block, mirrored for an instant first paint ─────────── */

    function readMirror() {
        try {
            const raw = JSON.parse(localStorage.getItem(MIRROR_KEY) || 'null');
            if (!raw || typeof raw !== 'object') return;
            if (raw.mode === 'simple' || raw.mode === 'advanced') state.mode = raw.mode;
            if (raw.dock === 'taskbar' || raw.dock === 'floating' || raw.dock === 'off') state.dock = raw.dock;
        } catch (err) { /* storage blocked: the config wins */ }
    }

    function writeMirror() {
        try { localStorage.setItem(MIRROR_KEY, JSON.stringify({ mode: state.mode, dock: state.dock })); }
        catch (err) { /* private mode */ }
    }

    function applyPrefs(help) {
        if (!help || typeof help !== 'object') return;
        if (help.mode === 'simple' || help.mode === 'advanced') state.mode = help.mode;
        if (help.dock === 'taskbar' || help.dock === 'floating' || help.dock === 'off') state.dock = help.dock;
        if (Array.isArray(help.recents)) state.recents = help.recents.slice(0, RECENTS_MAX);
        if (Array.isArray(help.dismissed)) state.dismissed = help.dismissed.slice(0, 24);
        writeMirror();
    }

    function savePrefs(patch) {
        writeMirror();
        return request(API, { method: 'POST', body: patch }).then((res) => {
            if (res && res.help) applyPrefs(res.help);
            return res;
        }).catch((err) => {
            toast('help: the preference could not be saved (' + err + ')');
            return null;
        });
    }

    /* ── the command index: the program itself, searchable ─────────────────────────────────── */

    function railCommands() {
        /* T4/A-corr: VIEW items only — without the filter the Setup button became a bogus
           "view:" command in the palette. */
        return Array.prototype.slice.call(document.querySelectorAll('.rail .nav-item[data-view]')).map((btn) => {
            const view = btn.dataset.view || '';
            const label = (btn.textContent || '').trim().replace(/\s+/g, ' ')
                .replace(/\s*\d+$/, '').replace(/^[^\w]+/, '');
            return {
                id: 'view:' + view, kind: 'command', group: 'commands', groupLabel: 'Panels',
                title: 'Open ' + label, tags: [view, 'panel', 'view', 'open'],
                summary: (btn.getAttribute('title') || '') || ('Switch to the ' + label + ' panel.'),
                view: view,
            };
        }).filter((row) => row.view);
    }

    function menuCommands() {
        const bar = window.OFAPMenuBar;
        if (!bar || typeof bar.menus !== 'function') return [];
        const out = [];
        function walk(items, trail, menuId) {
            (items || []).forEach((item) => {
                if (!item || typeof item !== 'object') return;
                if (item.separator || item.header) return;
                if (item.submenu) { walk(item.submenu, trail.concat(item.label), menuId); return; }
                if (!item.label) return;
                if (item.disabled) {
                    out.push({
                        id: 'menu:' + menuId + ':' + trail.concat(item.label).join('/'),
                        kind: 'command', group: 'commands', groupLabel: 'Menu',
                        title: trail.concat(item.label).join(' ▸ '),
                        tags: ['menu', menuId].concat(trail),
                        summary: 'Menu item — ' + (item.reason || 'not available in this build.'),
                        menu: menuId, disabled: true, reason: item.reason || '',
                    });
                    return;
                }
                out.push({
                    id: 'menu:' + menuId + ':' + trail.concat(item.label).join('/'),
                    kind: 'command', group: 'commands', groupLabel: 'Menu',
                    title: trail.concat(item.label).join(' ▸ '),
                    tags: ['menu', menuId].concat(trail),
                    summary: 'Opens the ' + (trail[0] || menuId) + ' menu where this lives.',
                    menu: menuId,
                });
            });
        }
        (bar.menus() || []).forEach((menu) => walk(menu.items || [], [menu.label], menu.id));
        return out;
    }

    function appCommands() {
        return [
            { id: 'app:palette', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Open the command palette (Ctrl+K)', tags: ['palette', 'search', 'symbol', 'ctrl+k'], summary: 'Search panels, actions and the market in one box.' },
            { id: 'app:hotkeys', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Show the hotkey map', tags: ['hotkeys', 'keys', 'shortcuts'], summary: 'The overlay generated from the app\'s own shortcut map.' },
            { id: 'app:check', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Run the system check', tags: ['check', 'health', 'errors', 'diagnose'], summary: 'Configuration errors and irregularities, worst first.' },
            { id: 'app:about', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'About this program', tags: ['about', 'version', 'credits', 'licence'], summary: 'Version, credits, thanks, links and the folders it writes to.' },
            { id: 'app:wizard', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Run the setup assistant', tags: ['setup', 'wizard', 'first run', 'instruments'], summary: 'The guided first-run walkthrough, re-openable at any time.' },
            { id: 'app:start', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Start the engine', tags: ['engine', 'start', 'live'], summary: 'Subscribe the enabled instruments and begin streaming.' },
            { id: 'app:pause', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Pause the live updates (P)', tags: ['pause', 'freeze', 'hold'], summary: 'Hold every background refresh while you work on the board.' },
            { id: 'app:mode-simple', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Help: switch to the simple interface', tags: ['help', 'simple', 'mode'], summary: 'The safe subset with the system check on top.' },
            { id: 'app:mode-advanced', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Help: switch to the advanced interface', tags: ['help', 'advanced', 'mode'], summary: 'Every topic, including the under-the-hood material.' },
            { id: 'app:dock-taskbar', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Help: dock the launcher in the status bar', tags: ['help', 'dock', 'taskbar', 'status bar'], summary: 'A search box along the bottom, one click from every panel.' },
            { id: 'app:dock-floating', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Help: floating help button', tags: ['help', 'dock', 'floating', 'button'], summary: 'A small ? button that opens the quick search panel.' },
            { id: 'app:dock-off', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Help: hide the launcher', tags: ['help', 'dock', 'hidden'], summary: 'Help stays on F1 and in the menu bar.' },
            { id: 'app:folder-config', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Open the user folder', tags: ['folder', 'config', 'settings'], summary: 'Where your settings, drawings and exports live.' },
            { id: 'app:folder-logs', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Open the logs folder', tags: ['folder', 'logs'], summary: 'The rotating log file.' },
            { id: 'app:diagnostics', kind: 'command', group: 'commands', groupLabel: 'Actions', title: 'Copy diagnostics', tags: ['diagnostics', 'support', 'report', 'bug'], summary: 'Version, paths, source and telemetry, on the clipboard.' },
        ];
    }

    function commands() {
        if (!state.commands) state.commands = railCommands().concat(menuCommands(), appCommands());
        return state.commands;
    }

    /* The searchable set: the visible topics plus every command. Advanced-only topics are excluded
       from the Simple index, and the engine is told nothing else about modes. */
    function buildSearchIndex() {
        const key = state.mode + ':' + commands().length;
        if (state.cachedFor === key) return state.index;
        const topics = (DATA && DATA.topics || []).filter(visible).map((t) => ({
            id: t.id, title: t.title, tags: t.tags, aliases: t.aliases, summary: t.summary,
            blocks: t.blocks, group: t.group, groupLabel: groupLabel(t.group), mode: t.mode,
            kindRank: 1.5,                       /* an explanation beats a command on a tie */
        }));
        const rows = topics.concat(commands().map((c) => ({
            id: c.id, title: c.title, tags: c.tags, aliases: [], summary: c.summary || '',
            blocks: [], group: c.group || 'commands', groupLabel: c.groupLabel || 'Commands',
            kindRank: 0.2,                       /* still found, just never ahead of the help itself */
        })));
        state.index = SEARCH ? SEARCH.buildIndex(rows) : { index: [], vocab: [] };
        state.cachedFor = key;
        return state.index;
    }

    function entryFor(id) {
        const topic = topicById(id);
        if (topic) return { kind: 'topic', row: topic };
        const command = commands().filter((c) => c.id === id)[0];
        if (command) return { kind: 'command', row: command };
        return null;
    }

    /* ── the view ──────────────────────────────────────────────────────────────────────────── */

    function buildView() {
        if (el('helpView')) return;
        const rail = document.querySelector('.rail');
        if (rail && !document.querySelector('.nav-item[data-view="help"]')) {
            const btn = document.createElement('button');
            btn.className = 'nav-item';
            btn.dataset.view = 'help';
            btn.title = 'The Help Centre: every panel and every setting, searchable, at two depths (F1)';
            btn.innerHTML = '<span class="nav-icon">?</span> Help';
            btn.onclick = () => { if (typeof window.showView === 'function') window.showView('help'); };
            const anchor = rail.querySelector('.nav-item[data-view="logs"]');
            rail.insertBefore(btn, anchor || null);
        }
        const main = document.querySelector('main.views');
        if (!main) return;
        const section = document.createElement('section');
        section.className = 'view';
        section.dataset.view = 'help';
        section.dataset.surface = 'help';       /* the intent arbiter takes a lease while typing here */
        section.id = 'helpView';
        section.innerHTML = ''
            + '<div class="view-head">'
            +   '<img class="help-brand" src="' + BRAND + '" alt="ModFlow">'
            +   '<div><div class="view-title">Help Centre</div>'
            +   '<div class="view-sub" id="helpSub">every panel and every setting, searchable — Advanced user or Simple</div></div>'
            +   '<div class="grow"></div>'
            +   '<div class="row">'
            +     '<button class="btn small" id="helpCheckBtn" title="Configuration errors and irregularities, worst first">System check</button>'
            +     '<button class="btn small" id="helpAboutBtn" title="Version, credits, links and the folders this program writes to">About</button>'
            +     '<button class="btn small" id="helpDockBtn2" title="Where the help launcher lives: the status bar, a floating button, or hidden">Launcher…</button>'
            +   '</div>'
            + '</div>'
            + '<div class="help-wrap">'
            +   '<aside class="help-nav">'
            +     '<div class="help-search">'
            +       '<input id="helpSearch" type="text" autocomplete="off" spellcheck="false" '
            +              'placeholder="Search the help and the program…  (Ctrl+K searches the market)" '
            +              'aria-label="Search the help">'
            +       '<div class="help-suggest" id="helpSuggest" role="listbox"></div>'
            +     '</div>'
            +     '<div class="help-mode" id="helpMode" role="group" aria-label="Help interface">'
            +       '<button type="button" data-mode="advanced">Advanced user</button>'
            +       '<button type="button" data-mode="simple">Simple</button>'
            +     '</div>'
            +     '<div class="help-mode-note" id="helpModeNote"></div>'
            +     '<div id="helpTree"></div>'
            +   '</aside>'
            +   '<div class="help-doc" id="helpDoc"></div>'
            + '</div>';
        main.appendChild(section);

        if (el('helpMode')) {
            el('helpMode').onclick = (ev) => {
                const btn = ev.target.closest('button[data-mode]');
                if (btn) setMode(btn.dataset.mode);
            };
        }
        if (el('helpCheckBtn')) el('helpCheckBtn').onclick = () => { openTopic('support.syscheck', false); };
        if (el('helpAboutBtn')) el('helpAboutBtn').onclick = () => { openAbout(); };
        if (el('helpDockBtn2')) el('helpDockBtn2').onclick = () => cycleDock();
        wireSearch(el('helpSearch'), el('helpSuggest'), (pick) => applyPick(pick));
    }

    /* The view is created after ui.js has already handled a `#help` deep link, so make sure the
       section is the active one when the hash asked for it. */
    function activateIfDeepLinked() {
        if (location.hash.slice(1) === 'help' && typeof window.showView === 'function') window.showView('help');
    }

    /* ── the nav tree ──────────────────────────────────────────────────────────────────────── */

    function renderTree() {
        const host = el('helpTree');
        if (!host) return;
        const seg = el('helpMode');
        if (seg) {
            Array.prototype.slice.call(seg.querySelectorAll('button')).forEach((b) => {
                b.classList.toggle('on', b.dataset.mode === state.mode);
                b.title = b.dataset.mode === 'advanced'
                    ? 'Every topic, including the under-the-hood material and the danger zone'
                    : 'The safe subset, with the system check on top';
            });
        }
        const hidden = (DATA && DATA.topics || []).filter((t) => !visible(t)).length;
        if (el('helpModeNote')) {
            el('helpModeNote').textContent = state.mode === 'simple'
                ? (hidden + ' advanced topic(s) are hidden here — switch to Advanced user whenever you want them.')
                : 'Advanced user: every topic is listed, including the ones that can change or delete data.';
        }

        const filter = state.treeFilter.trim().toLowerCase();
        const groups = (DATA && DATA.groups || []).filter((g) => state.mode === 'advanced' || g.mode !== 'advanced');
        const html = groups.map((group) => {
            const rows = (DATA.topics || []).filter((t) => t.group === group.id && visible(t)
                && (!filter || (t.title + ' ' + (t.tags || []).join(' ') + ' ' + (t.summary || '')).toLowerCase().indexOf(filter) >= 0));
            if (!rows.length) return '';
            return '<div class="help-group"><div class="help-group-title">' + esc(group.label) + '</div>'
                + rows.map((t) => '<button class="help-item' + (t.id === state.open ? ' on' : '') + '" data-topic="' + esc(t.id) + '">'
                    + '<span>' + esc(t.title) + '</span>'
                    + (isAdvanced(t) ? '<span class="help-lock" title="advanced topic">adv</span>' : '')
                    + '</button>').join('')
                + '</div>';
        }).join('');

        const recents = state.recents.map((id) => topicById(id)).filter(Boolean)
            .filter((t) => visible(t) && (!filter || t.title.toLowerCase().indexOf(filter) >= 0));
        const recentHtml = recents.length
            ? '<div class="help-recents"><div class="help-group-title">Recently opened</div>'
              + recents.map((t) => '<button class="help-item" data-topic="' + esc(t.id) + '">'
                  + '<span>' + esc(t.title) + '</span></button>').join('') + '</div>'
            : '';
        host.innerHTML = (html || '<div class="help-empty">nothing matches that — clear the box to see every topic</div>') + recentHtml;
        host.querySelectorAll('[data-topic]').forEach((btn) => {
            btn.onclick = () => openTopic(btn.dataset.topic, false);
        });
    }

    /* ── search: the box, the autofill list, the results ───────────────────────────────────── */

    /* One behaviour for all three search boxes (the view's, the status-bar dock's, the floating
       panel's): a suggestion list that opens under the field, keyboard-walkable with ↑ ↓ Enter. */
    function wireSearch(input, suggestHost, onPick) {
        if (!input || !suggestHost) return;
        let seq = 0;
        function hide() { suggestHost.classList.remove('on'); suggestHost.innerHTML = ''; state.sugAt = -1; }
        function pick(index) {
            const row = state.sug[index];
            if (!row) return false;
            input.value = row.text;
            hide();
            onPick(row);
            return true;
        }
        function paintSuggest() {
            const rows = SEARCH ? SEARCH.suggest(input.value, buildSearchIndex(), commandPhrases(), 8) : [];
            state.sug = rows;
            state.sugAt = rows.length ? 0 : -1;
            if (!rows.length || !input.value.trim()) { hide(); return; }
            suggestHost.innerHTML = rows.map((row, i) => {
                const segs = SEARCH.segments(row.label, [SEARCH.stem(SEARCH.normalise(
                    input.value.trim().split(/\s+/).pop() || ''))]);
                const text = segs.map((s) => (s[1] ? '<b>' + esc(s[0]) + '</b>' : esc(s[0]))).join('');
                return '<div class="help-sug-row' + (i === state.sugAt ? ' on' : '') + '" data-sug="' + i + '" role="option">'
                    + '<span class="help-badge ' + esc(row.kind) + '">' + esc(row.kind) + '</span>'
                    + '<span class="help-sug-text">' + text + '</span></div>';
            }).join('');
            suggestHost.classList.add('on');
            suggestHost.querySelectorAll('[data-sug]').forEach((row) => {
                row.onmousedown = (ev) => { ev.preventDefault(); pick(Number(row.dataset.sug)); };
            });
        }
        function move(delta) {
            const total = state.sug.length;
            if (!total) return;
            state.sugAt = (state.sugAt + delta + total) % total;
            Array.prototype.slice.call(suggestHost.querySelectorAll('[data-sug]')).forEach((row, i) => {
                row.classList.toggle('on', i === state.sugAt);
            });
        }
        input.addEventListener('input', () => {
            state.query = input.value;
            clearTimeout(seq);
            seq = setTimeout(paintSuggest, 40);
            if (input.id === 'helpSearch') runSearch(input.value, false);
        });
        input.addEventListener('focus', paintSuggest);
        input.addEventListener('keydown', (ev) => {
            if (ev.key === 'ArrowDown') { ev.preventDefault(); move(1); return; }
            if (ev.key === 'ArrowUp') { ev.preventDefault(); move(-1); return; }
            if (ev.key === 'Escape') { hide(); input.blur(); return; }
            if (ev.key === 'Enter') {
                ev.preventDefault();
                if (!pick(state.sugAt)) {
                    /* No suggestion: run the search and take the first result — the box never
                       swallows an Enter. */
                    const res = SEARCH ? SEARCH.search(input.value, buildSearchIndex(), { limit: 1 }) : { results: [] };
                    if (res.results.length) openTopic(res.results[0].id, false);
                    else toast('help: nothing matches "' + input.value + '"');
                }
            }
        });
        input.addEventListener('blur', () => setTimeout(hide, 120));
    }

    /* The app's own vocabulary, for the autofill: view names and menu commands from the live UI. */
    function commandPhrases() {
        return commands().slice(0, 400).map((c) => ({ text: c.title, kind: 'command', id: c.id, weight: 3.5 }));
    }

    function runSearch(query, focusFirst) {
        state.query = String(query || '');
        if (!state.query.trim()) {
            state.results = null;
            /* Always replace the pane. This used to re-render only when a topic was open, so
               clearing the box while looking at results left those buttons on screen with
               `state.results` already null — a click on one crashed the pane (live: help.js:476). */
            renderTopic(topicById(state.open) || topicById('start.help'));
            return;
        }
        const res = SEARCH ? SEARCH.search(state.query, buildSearchIndex(), { limit: 40 }) : { results: [], total: 0, corrected: '' };
        state.results = res;
        renderResults();
        if (focusFirst && res.results.length) openTopic(res.results[0].id, false);
    }

    function renderResults() {
        const doc = el('helpDoc');
        if (!doc || !state.results) return;
        const res = state.results;
        const rows = res.results.map((row, i) => {
            const entry = entryFor(row.id);
            const kind = entry ? entry.kind : 'topic';
            const terms = (SEARCH ? SEARCH.tokenise(res.query) : []);
            const segs = SEARCH ? SEARCH.segments(row.title, terms) : [[row.title, false]];
            const title = segs.map((s) => (s[1] ? '<b>' + esc(s[0]) + '</b>' : esc(s[0]))).join('');
            const snip = SEARCH ? SEARCH.segments(row.snippet, terms) : [[row.snippet, false]];
            const snippet = snip.map((s) => (s[1] ? '<b>' + esc(s[0]) + '</b>' : esc(s[0]))).join('');
            return '<button class="help-result" data-result="' + i + '">'
                + '<div class="help-result-t">' + title
                + ' <span class="help-badge ' + esc(kind === 'command' ? 'command' : 'topic') + '">' + (kind === 'command' ? 'action' : esc(row.group)) + '</span></div>'
                + '<div class="help-result-s">' + snippet + '</div>'
                + '<div class="help-why">' + esc(row.why) + '</div></button>';
        }).join('');
        doc.innerHTML = '<div class="help-doc-head"><div><div class="help-doc-title">Search results</div>'
            + '<div class="help-doc-group">' + esc(String(res.total)) + ' result(s) for “' + esc(res.query) + '”'
            + (res.corrected ? ' — searched for “' + esc(res.corrected) + '” instead' : '') + '</div></div></div>'
            + (res.results.length ? rows : '<div class="help-empty">Nothing matches. Try fewer words, or a word you would use in the panel itself ('
                + '“depth”, “replay”, “telegram”).</div>');
        doc.querySelectorAll('[data-result]').forEach((btn) => {
            btn.onclick = () => {
                /* Belt to the empty-query path's braces: never read a missing result set. */
                if (!state.results) return;
                const row = state.results.results[Number(btn.dataset.result)];
                if (row) openTopic(row.id, false);
            };
        });
        const scroller = doc.closest('.views');
        if (scroller) scroller.scrollTop = 0;
    }

    /* ── opening something ─────────────────────────────────────────────────────────────────── */

    function applyPick(pick) {
        if (!pick) return;
        const entry = entryFor(pick.id);
        if (pick.kind === 'command' && entry) { runCommand(entry.row); return; }
        if (entry) { openTopic(entry.row.id, true); return; }
        /* a keyword or alias completion: search for it rather than guessing an article */
        const input = el('helpSearch');
        if (input) { input.value = pick.text; }
        if (typeof window.showView === 'function') window.showView('help');
        runSearch(pick.text, true);
    }

    function openTopic(id, focusSearch) {
        const topic = topicById(id);
        if (!topic) { runSearch(id, false); return; }
        if (!visible(topic)) { renderGate(topic); return; }
        state.gate = '';
        state.open = id;
        if (typeof window.showView === 'function') window.showView('help');
        renderTopic(topic);
        pushRecent(id);
        renderTree();
        if (focusSearch && el('helpSearch')) el('helpSearch').focus();
    }

    /* Simple mode, advanced topic: say why and offer the step up — never a silent nothing. */
    function renderGate(topic) {
        const doc = el('helpDoc');
        if (!doc) return;
        state.gate = topic.id;
        doc.innerHTML = '<div class="help-gate">'
            + '<h4>' + esc(topic.title) + ' is an advanced topic</h4>'
            + '<p>It is hidden in the Simple interface because it can change settings that are easy to '
            + 'get wrong, or describes something you only need when something is already broken. '
            + 'Nothing here is secret — you can read it whenever you want.</p>'
            + '<div class="row">'
            +   '<button class="btn small primary" id="gateShow">Read it anyway</button>'
            +   '<button class="btn small" id="gateUp">Switch to Advanced user</button>'
            +   '<button class="btn small" id="gateBack">Back to the topics</button>'
            + '</div></div>';
        if (el('gateShow')) el('gateShow').onclick = () => {
            state.mode = 'advanced';
            state.cachedFor = '';
            void savePrefs({ mode: 'advanced' });
            openTopic(topic.id, false);
            renderTree();
        };
        if (el('gateUp')) el('gateUp').onclick = () => {
            state.mode = 'advanced';
            state.cachedFor = '';
            void savePrefs({ mode: 'advanced' });
            renderTree();
            openTopic(topic.id, false);
        };
        if (el('gateBack')) el('gateBack').onclick = () => { state.gate = ''; renderTree(); openTopic('start.help', false); };
    }

    function pushRecent(id) {
        const next = [id].concat(state.recents.filter((x) => x !== id)).slice(0, RECENTS_MAX);
        state.recents = next;
        void savePrefs({ recents: next });
    }

    /* ── rendering an article ──────────────────────────────────────────────────────────────── */

    /* A block may carry more than one key (a heading with a step list, a paragraph with a note), so
       this collects every part it understands and joins them in reading order. */
    function blockHtml(block) {
        if (typeof block === 'string') return '<p>' + md(block) + '</p>';
        const parts = [];
        if (block.h) parts.push('<h4>' + md(block.h) + '</h4>');
        if (block.p) parts.push('<p>' + md(block.p) + '</p>');
        if (block.list) parts.push('<ul>' + block.list.map((li) => '<li>' + md(li) + '</li>').join('') + '</ul>');
        if (block.note) parts.push('<div class="help-note">' + md(block.note) + '</div>');
        if (block.warn) parts.push('<div class="help-warn"><b>Careful.</b> ' + md(block.warn) + '</div>');
        if (block.table) {
            parts.push('<table>' + block.table.map((row) => '<tr>'
                + (row || []).map((cell) => '<td>' + md(cell) + '</td>').join('') + '</tr>').join('') + '</table>');
        }
        if (block.steps) {
            parts.push('<ol class="help-steps">' + block.steps.map((step, i) => '<li class="help-step">'
                + '<div class="help-num">' + (i + 1) + '</div>'
                + '<div><div class="help-step-t">' + md(step.t || '') + '</div>'
                + '<div class="help-step-d">' + md(step.d || '') + '</div>'
                + (step.cmd || []).map((line) => '<div class="help-cmd"><code>' + esc(line) + '</code>'
                    + '<button class="btn small" data-copy="' + esc(line) + '" title="Copy this line">Copy</button></div>').join('')
                + '</div></li>').join('') + '</ol>');
        }
        if (block.cmd) {
            const lines = Array.isArray(block.cmd) ? block.cmd : [block.cmd];
            parts.push(lines.map((line) => '<div class="help-cmd"><code>' + esc(line) + '</code>'
                + '<button class="btn small" data-copy="' + esc(line) + '" title="Copy this line">Copy</button></div>').join(''));
        }
        if (block.shot) {
            const src = '/desktop/' + String(block.shot).replace(/^\/?(desktop\/)?/, '');
            parts.push('<figure class="help-shot" data-shot="1"><img src="' + esc(src) + '" alt="'
                + esc(block.caption || 'screenshot') + '" loading="lazy">'
                + (block.caption ? '<figcaption>' + md(block.caption) + '</figcaption>' : '') + '</figure>');
        }
        if (block.keys) parts.push(keysHtml());
        if (block.check) parts.push(checkHtml(true));
        return parts.join('');
    }

    function keysHtml() {
        const rows = (window.OFAPKEYS && OFAPKEYS.list) ? OFAPKEYS.list() : [];
        if (!rows.length) return '<div class="help-empty">The shortcut map has not loaded yet.</div>';
        return '<table class="help-keys"><thead><tr><th>Keys</th><th>Action</th><th>Where</th></tr></thead><tbody>'
            + rows.map((r) => '<tr><td class="help-key">' + esc(r.keys) + '</td><td>' + esc(r.label)
                + '</td><td class="help-why">' + esc(r.scope) + '</td></tr>').join('')
            + '</tbody></table>'
            + '<div class="help-note">Generated from the app\'s one shortcut map (keys.js), so every key it '
            + 'honours is listed and no key is listed that does nothing.</div>';
    }

    function renderTopic(topic) {
        const doc = el('helpDoc');
        if (!doc) return;
        const actions = (topic.actions || []).filter((a) => a && a.kind);
        const related = (topic.related || []).map((id) => topicById(id)).filter(Boolean);
        doc.innerHTML = ''
            + '<div class="help-doc-head">'
            +   '<img class="help-brand" src="' + BRAND + '" alt="">'
            +   '<div class="help-doc-title">' + esc(topic.title) + '</div>'
            +   '<span class="help-doc-group">' + esc(groupLabel(topic.group))
            +   (isAdvanced(topic) ? ' · advanced' : '') + '</span>'
            + '</div>'
            + '<div class="help-doc-sum">' + md(topic.summary || '') + '</div>'
            + '<div class="help-actions">' + actions.map((a, i) =>
                '<button class="btn small' + (i === 0 ? ' primary' : '') + '" data-act="' + i + '">'
                + esc(a.label) + '</button>').join('') + '</div>'
            + (topic.blocks || []).map((b) => '<div class="help-block">' + blockHtml(b) + '</div>').join('')
            + (topic.links && topic.links.length
                ? '<div class="help-block"><h4>Elsewhere</h4><div class="help-actions">'
                  + topic.links.map((l) => '<a class="btn small" href="' + esc(l.url) + '" target="_blank" '
                      + 'rel="noopener noreferrer">' + esc(l.label) + ' ↗</a>').join('') + '</div></div>'
                : '')
            + (related.length
                ? '<div class="help-block"><h4>Read next</h4><div class="help-related">'
                  + related.map((t) => '<button class="btn small" data-related="' + esc(t.id) + '">'
                      + esc(t.title) + '</button>').join('') + '</div></div>'
                : '')
            + '<div class="help-block"><div class="help-note">This is the Advanced interface of the help '
            + 'system. The Simple interface shows the same topics minus the advanced ones — the switch is '
            + 'at the top of the list, and Help ▸ Simple mode in the menu bar does the same thing.</div></div>';

        doc.querySelectorAll('[data-act]').forEach((btn) => {
            btn.onclick = () => {
                const a = actions[Number(btn.dataset.act)];
                if (a) runAction(a);
            };
        });
        doc.querySelectorAll('[data-related]').forEach((btn) => {
            btn.onclick = () => openTopic(btn.dataset.related, false);
        });
        doc.querySelectorAll('[data-copy]').forEach((btn) => {
            btn.onclick = () => copyText(btn.dataset.copy || '', btn);
        });
        doc.querySelectorAll('.help-shot img').forEach((img) => {
            img.onclick = () => img.parentElement.classList.toggle('zoom');
        });
        wireCheckHost(doc);
        const scroller = doc.closest('.views');
        if (scroller) scroller.scrollTop = 0;
    }

    function copyText(text, btn) {
        const done = (ok) => {
            const old = btn ? btn.textContent : '';
            if (!btn) return;
            btn.textContent = ok ? 'Copied' : 'Select it manually';
            setTimeout(() => { btn.textContent = old; }, 1500);
        };
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => done(true), () => done(false));
                return;
            }
        } catch (err) { /* fall through */ }
        done(false);
    }

    /* ── the system check ──────────────────────────────────────────────────────────────────── */

    function checkHtml(live) {
        const check = state.check;
        if (!check) return '<div class="help-empty">The system check has not loaded yet.</div>';
        const rows = (check.checks || []);
        const visibleRows = rows.filter((c) => state.showDismissed || state.dismissed.indexOf(c.id) < 0);
        const dismissed = rows.filter((c) => state.dismissed.indexOf(c.id) >= 0).length;
        const counts = check.counts || {};
        const bad = (counts.error || 0) + (counts.warn || 0);
        const head = state.showDismissed
            ? 'Showing every row, including the ones you dismissed.'
            : (bad ? (counts.error || 0) + ' error(s), ' + (counts.warn || 0) + ' warning(s), '
                    + (counts.notice || 0) + ' notice(s) · ' + (counts.ok || 0) + ' check(s) passed'
                   : 'Everything the check looks at is in order — ' + (counts.ok || 0) + ' check(s) passed.');
        const body = visibleRows.map((c) => {
            const acts = [];
            if (c.topic) acts.push('<button class="btn small" data-check-topic="' + esc(c.topic) + '">What is this?</button>');
            if (c.view) acts.push('<button class="btn small" data-check-view="' + esc(c.view) + '">Take me there</button>');
            if (c.action) acts.push('<button class="btn small" data-check-act="' + esc(c.action) + '">' + esc(actionLabel(c.action)) + '</button>');
            if (c.level !== 'ok') {
                acts.push('<button class="btn small" data-check-dismiss="' + esc(c.id) + '" title="Hide this row until its condition changes back">'
                    + (state.dismissed.indexOf(c.id) >= 0 ? 'Un-dismiss' : 'Dismiss') + '</button>');
            }
            return '<div class="help-check-row ' + esc(c.level) + '">'
                + '<span class="help-lvl">' + esc(c.level) + '</span>'
                + '<div class="help-check-body"><div class="help-check-t">' + esc(c.title) + '</div>'
                + '<div class="help-check-d">' + esc(c.detail) + '</div>'
                + (acts.length ? '<div class="help-check-acts">' + acts.join('') + '</div>' : '')
                + '</div></div>';
        }).join('');
        return '<div class="help-check-sum">' + esc(head)
            + (dismissed ? ' · <button class="btn small" data-check-toggle="1">'
                + (state.showDismissed ? 'hide' : 'show') + ' ' + dismissed + ' dismissed</button>' : '')
            + '</div><div class="help-check">' + (body || '<div class="help-empty">Nothing to show.</div>') + '</div>'
            + '<div class="help-block" style="margin-top:10px"><button class="btn small" data-check-refresh="1">'
            + 'Run it again</button> <span class="help-why">read-only: it never starts an engine or touches the network</span></div>';
    }

    function actionLabel(action) {
        return ({
            'start-engine': 'Start the engine',
            'open-settings': 'Open Settings',
            'open-instruments': 'Open Instruments',
            'open-logs': 'Open Logs',
            'open-wizard': 'Run the setup assistant',
            'open-folder-config': 'Open the user folder',
            'open-folder-logs': 'Open the logs folder',
            'open-folder-backup': 'Open the folder',
        })[action] || 'Do it';
    }

    function wireCheckHost(host) {
        if (!host) return;
        host.querySelectorAll('[data-check-topic]').forEach((b) => {
            b.onclick = () => openTopic(b.dataset.checkTopic, false);
        });
        host.querySelectorAll('[data-check-view]').forEach((b) => {
            b.onclick = () => { if (typeof window.showView === 'function') window.showView(b.dataset.checkView); };
        });
        host.querySelectorAll('[data-check-act]').forEach((b) => {
            b.onclick = () => runCheckAction(b.dataset.checkAct);
        });
        host.querySelectorAll('[data-check-dismiss]').forEach((b) => {
            b.onclick = () => toggleDismiss(b.dataset.checkDismiss);
        });
        host.querySelectorAll('[data-check-toggle]').forEach((b) => {
            b.onclick = () => { state.showDismissed = !state.showDismissed; void refreshCheck(false); };
        });
        host.querySelectorAll('[data-check-refresh]').forEach((b) => {
            b.onclick = () => void refreshCheck(true);
        });
    }

    function toggleDismiss(id) {
        const next = state.dismissed.indexOf(id) >= 0
            ? state.dismissed.filter((x) => x !== id)
            : state.dismissed.concat([id]).slice(0, 24);
        state.dismissed = next;
        void savePrefs({ dismissed: next });
        if (state.open === 'support.syscheck') openTopic('support.syscheck', false);
        renderDockCheckBadge();
    }

    function runCheckAction(action) {
        switch (action) {
            case 'start-engine': {
                const btn = el('btnStart');
                if (btn) btn.click();
                else toast('help: the start button is not in this build');
                break;
            }
            case 'open-settings': case 'open-instruments': case 'open-logs':
                if (typeof window.showView === 'function') window.showView(action.replace('open-', ''));
                break;
            case 'open-wizard':
                if (typeof window.openWizard === 'function') openWizard(true);
                else toast('help: the setup assistant is not loaded in this window');
                break;
            case 'open-folder-config': void openFolder('config'); break;
            case 'open-folder-logs': void openFolder('logs'); break;
            case 'open-folder-backup': void openFolder('exports'); break;
            default: toast('help: no action for ' + action);
        }
    }

    function refreshCheck(loud) {
        return request(API).then((res) => {
            if (res && res.check) state.check = res.check;
            if (res) {
                state.facts = res.app || state.facts;
                state.credits = res.credits || state.credits;
                state.links = res.links || state.links;
                /* The stored preferences are the record (the localStorage mirror only kills the
                   flash on the very first paint): adopting them here is what makes the mode, the
                   launcher, the recents trail and the dismissed checks survive a restart. */
                applyPrefs(res.prefs);
            }
            state.offline = false;
            renderDockCheckBadge();
            if (state.open === 'support.syscheck') renderTopic(topicById('support.syscheck'));
            if (loud) {
                const counts = (state.check && state.check.counts) || {};
                toast('help: system check — ' + (counts.error || 0) + ' error(s), ' + (counts.warn || 0)
                    + ' warning(s), ' + (counts.notice || 0) + ' notice(s)');
            }
            return res;
        }).catch((err) => {
            if (loud) toast('help: the system check could not run (' + err + ')');
            return null;
        });
    }

    /* ── actions the corpus names ──────────────────────────────────────────────────────────── */

    function runAction(action) {
        const value = action.value || '';
        switch (action.kind) {
            case 'view':
                if (typeof window.showView === 'function') window.showView(value);
                break;
            case 'topic':
                openTopic(value, false);
                break;
            case 'wizard':
                if (typeof window.openWizard === 'function') openWizard(true);
                else toast('help: the setup assistant is not loaded in this window');
                break;
            case 'menu':
                if (window.OFAPMenuBar && value) window.OFAPMenuBar.open(value);
                else if (window.OFAPMenu && typeof OFAPMenu.open === 'function') OFAPMenu.open();
                break;
            case 'keys':
                if (window.OFAPMenu && typeof OFAPMenu.showHotkeys === 'function') OFAPMenu.showHotkeys(true);
                else toast('help: the hotkey overlay is not loaded in this window');
                break;
            case 'check':
                void refreshCheck(true).then(() => openTopic('support.syscheck', false));
                break;
            case 'copy':
                void copyDiagnostics();
                break;
            case 'palette':
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
                break;
            case 'search': {
                if (typeof window.showView === 'function') window.showView('help');
                if (el('helpSearch')) { el('helpSearch').value = value; }
                runSearch(value, true);
                break;
            }
            case 'folder':
                void openFolder(value);
                break;
            case 'about':
                openAbout();
                break;
            case 'legend': {
                const panel = el('ofxLegendPanel');
                if (!panel) {
                    toast('help: the legend lives in the Engine view');
                    if (typeof window.showView === 'function') window.showView('ofx');
                    break;
                }
                if (typeof window.showView === 'function') window.showView('ofx');
                if (el('ofxLegendToggle')) el('ofxLegendToggle').click();
                break;
            }
            default:
                toast('help: ' + action.kind + ' is not an action this build knows');
        }
    }

    function runCommand(command) {
        if (!command) return;
        if (command.disabled) {
            toast('help: ' + command.title + ' — ' + (command.reason || 'not available in this build'));
            return;
        }
        const id = command.id || '';
        if (id.indexOf('view:') === 0) {
            if (typeof window.showView === 'function') window.showView(id.slice(5));
            return;
        }
        if (id.indexOf('menu:') === 0 && command.menu) {
            if (window.OFAPMenuBar && typeof OFAPMenuBar.open === 'function') {
                OFAPMenuBar.open(command.menu);
                toast('help: opened the ' + command.menu + ' menu — ' + command.title);
            }
            return;
        }
        switch (id) {
            case 'app:palette': document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true })); break;
            case 'app:hotkeys': if (window.OFAPMenu) OFAPMenu.showHotkeys(true); break;
            case 'app:check': void refreshCheck(true).then(() => openTopic('support.syscheck', false)); break;
            case 'app:about': openAbout(); break;
            case 'app:wizard': if (typeof window.openWizard === 'function') openWizard(true); break;
            case 'app:start': if (el('btnStart')) el('btnStart').click(); break;
            case 'app:pause': document.dispatchEvent(new KeyboardEvent('keydown', { key: 'p', bubbles: true })); break;
            case 'app:mode-simple': setMode('simple'); break;
            case 'app:mode-advanced': setMode('advanced'); break;
            case 'app:dock-taskbar': setDock('taskbar'); break;
            case 'app:dock-floating': setDock('floating'); break;
            case 'app:dock-off': setDock('off'); break;
            case 'app:folder-config': void openFolder('config'); break;
            case 'app:folder-logs': void openFolder('logs'); break;
            case 'app:diagnostics': void copyDiagnostics(); break;
            default: toast('help: nothing to run for ' + id);
        }
    }

    function openFolder(which) {
        return request('/api/control/folder/open', { method: 'POST', body: { folder: which } })
            .then((res) => {
                if (res && res.ok === false) toast('help: ' + (res.error || 'that folder could not be opened'));
            })
            .catch((err) => toast('help: the folder could not be opened (' + err + ')'));
    }

    function copyDiagnostics() {
        const facts = state.facts || {};
        const check = state.check || {};
        const lines = [
            (facts.name || 'ModFlow OrderFlow Analysis Suite') + ' — diagnostics',
            'version: ' + (facts.version || '?') + '-' + (facts.channel || '') + ' · python ' + (facts.python || '?')
                + ' · ' + (facts.platform || '?') + ' · frozen: ' + String(!!facts.frozen),
            'config: ' + ((facts.paths || {}).config || '?'),
            'log: ' + ((facts.paths || {}).log || '?'),
            'db: ' + ((facts.paths || {}).db || '?'),
            'help: ' + state.mode + ' mode, dock=' + state.dock,
            'views loaded: ' + document.querySelectorAll('.view').length,
            'system check: ' + JSON.stringify(check.counts || {}),
        ];
        try {
            return navigator.clipboard.writeText(lines.join('\n')).then(() => {
                toast('help: diagnostics copied to the clipboard');
            }, () => {
                console.log(lines.join('\n'));
                toast('help: the clipboard was blocked — the diagnostics are in the console');
            });
        } catch (err) {
            console.log(lines.join('\n'));
            toast('help: the clipboard was blocked — the diagnostics are in the console');
            return Promise.resolve();
        }
    }

    /* ── About ─────────────────────────────────────────────────────────────────────────────── */

    function openAbout() {
        const doc = el('helpDoc');
        if (!doc) return;
        if (typeof window.showView === 'function') window.showView('help');
        state.open = '';
        const facts = state.facts || {};
        const credits = state.credits || {};
        const links = state.links || [];
        const paths = facts.paths || {};
        const check = state.check || {};
        const counts = check.counts || {};
        doc.innerHTML = ''
            + '<div class="help-doc-head">'
            +   '<img class="help-brand" src="' + BRAND + '" alt="ModFlow" style="width:26px;height:26px">'
            +   '<div class="help-doc-title">' + esc(facts.name || 'ModFlow OrderFlow Analysis Suite') + '</div>'
            + '</div>'
            + '<div class="help-doc-sum">' + esc(facts.tagline || '') + '</div>'
            + '<div class="help-block"><h4>This copy</h4><table>'
            +   '<tr><td>Version</td><td>' + esc(facts.version || '?') + '-' + esc(facts.channel || '')
            +     ' · ' + esc(facts.licence || 'MIT') + ' licence</td></tr>'
            +   '<tr><td>Build</td><td>' + (facts.frozen ? 'packaged application (frozen)' : 'running from the source tree')
            +     ' · Python ' + esc(facts.python || '?') + ' on ' + esc(facts.platform || '?') + '</td></tr>'
            +   '<tr><td>System check</td><td>' + (counts.total || 0) + ' checks · '
            +     (counts.error || 0) + ' error(s) · ' + (counts.warn || 0) + ' warning(s)</td></tr>'
            + '</table></div>'
            + '<div class="help-block"><h4>Made by</h4><p>' + md(credits.made_by || '') + ' — '
            +   '<a href="' + esc(credits.made_by_url || 'https://moddys.net') + '" target="_blank" rel="noopener noreferrer">'
            +   esc(credits.made_by_url || 'moddys.net') + ' ↗</a>. The program builds on '
            +   '<b>' + esc(credits.upstream || '') + '</b> (<a href="' + esc(credits.upstream_url || '') + '" target="_blank" '
            +   'rel="noopener noreferrer">the original project ↗</a>), released under the MIT licence, and follows '
            +   esc(credits.methodology || 'the orderflow methodology') + '.</p></div>'
            + '<div class="help-block"><h4>Thanks to</h4><ul>'
            +   (credits.thanks || []).map((line) => '<li>' + esc(line) + '</li>').join('') + '</ul></div>'
            + '<div class="help-block"><h4>Where it writes</h4><table>'
            +   Object.keys(paths).map((k) => '<tr><td>' + esc(k) + '</td><td><code>' + esc(paths[k]) + '</code></td></tr>').join('')
            + '</table><div class="help-actions">'
            +   '<button class="btn small" data-about-folder="config">Open the user folder</button>'
            +   '<button class="btn small" data-about-folder="logs">Open the logs folder</button>'
            +   '<button class="btn small" data-about-diag="1">Copy diagnostics</button>'
            +   '<button class="btn small" data-about-check="1">Run the system check</button>'
            + '</div></div>'
            + '<div class="help-block"><h4>Links</h4><div class="help-actions">'
            +   links.map((l) => '<a class="btn small" href="' + esc(l.url) + '" target="_blank" rel="noopener noreferrer">'
                + esc(l.label) + ' ↗</a>').join('') + '</div></div>'
            + '<div class="help-block"><div class="help-note">Market data comes from the venues you selected; '
            + 'nothing about your use of this program is sent to its author, and there is no telemetry of any kind.</div></div>';
        doc.querySelectorAll('[data-about-folder]').forEach((b) => {
            b.onclick = () => void openFolder(b.dataset.aboutFolder);
        });
        doc.querySelectorAll('[data-about-diag]').forEach((b) => { b.onclick = () => void copyDiagnostics(); });
        doc.querySelectorAll('[data-about-check]').forEach((b) => {
            b.onclick = () => void refreshCheck(true).then(() => openTopic('support.syscheck', false));
        });
        const scroller = doc.closest('.views');
        if (scroller) scroller.scrollTop = 0;
    }

    /* ── mode, launcher and the dock ───────────────────────────────────────────────────────── */

    function setMode(mode) {
        if (mode !== 'simple' && mode !== 'advanced') return;
        state.mode = mode;
        state.cachedFor = '';
        void savePrefs({ mode: mode });
        renderTree();
        if (state.open && !visible(topicById(state.open) || {})) {
            state.open = '';
            renderTopic(topicById('start.help'));
        }
        toast('help: ' + (mode === 'simple' ? 'simple interface' : 'advanced interface'));
    }

    function setDock(dock) {
        if (['taskbar', 'floating', 'off'].indexOf(dock) < 0) return;
        state.dock = dock;
        void savePrefs({ dock: dock });
        buildLauncher();
        toast('help: launcher — ' + (dock === 'taskbar' ? 'docked in the status bar'
            : (dock === 'floating' ? 'floating button' : 'hidden (F1 still opens the help)')));
    }

    function cycleDock() {
        const order = ['taskbar', 'floating', 'off'];
        setDock(order[(order.indexOf(state.dock) + 1) % order.length]);
    }

    /* The launcher: the status bar's own strip (the app's taskbar), or a floating button, or
       nothing. Rebuilt from scratch on every change so the two shapes never both exist. */
    function buildLauncher() {
        const bar = document.querySelector('.statusbar');
        const existingDock = el('helpDock');
        const existingFab = el('helpFab');
        const existingQuick = el('helpQuick');
        if (existingDock) existingDock.remove();
        if (existingFab) existingFab.remove();
        if (existingQuick) existingQuick.remove();
        if (!bar) return;

        if (state.dock === 'taskbar') {
            const wrap = document.createElement('span');
            wrap.className = 'help-dock';
            wrap.id = 'helpDock';
            wrap.innerHTML = '<span class="help-dock-badge" id="helpDockBadge"></span>'
                + '<input id="helpDockInput" type="text" autocomplete="off" spellcheck="false" '
                + 'placeholder="help… (F1)" aria-label="Search the help" title="Search the help and the program — Enter opens the first match">'
                + '<button class="help-dock-btn" id="helpDockOpen" title="Open the Help Centre (F1)">?</button>';
            bar.appendChild(wrap);
            wireSearch(el('helpDockInput'), (function () {
                const host = document.createElement('div');
                host.className = 'help-suggest';
                host.id = 'helpDockSuggest';
                wrap.insertBefore(host, el('helpDockInput'));
                return host;
            }()), (pick) => {
                applyPick(pick);
                if (el('helpSearch')) el('helpSearch').value = state.query;
            });
            if (el('helpDockOpen')) el('helpDockOpen').onclick = () => openHelp('');
            renderDockCheckBadge();
        }

        if (state.dock === 'floating') {
            const quick = document.createElement('div');
            quick.className = 'help-quick';
            quick.id = 'helpQuick';
            quick.innerHTML = '<div class="help-quick-head">'
                + '<img class="help-brand" src="' + BRAND + '" alt="">'
                + '<input id="helpQuickInput" type="text" autocomplete="off" spellcheck="false" '
                + 'placeholder="Search the help and the program…" style="flex:1;background:var(--bg-secondary);'
                + 'border:1px solid var(--border-strong);border-radius:6px;color:var(--text-primary);padding:6px 8px;font-size:12.5px">'
                + '<button class="btn small" id="helpQuickOpen" title="Open the full Help Centre">Open</button>'
                + '<button class="btn small" id="helpQuickX" title="Close the quick help (Esc)">×</button></div>'
                + '<div class="help-suggest" id="helpQuickSuggest"></div>'
                + '<div class="help-quick-results" id="helpQuickResults"></div>'
                + '<div class="help-quick-foot">Enter opens the first match · the full Help Centre is on F1</div>';
            document.body.appendChild(quick);
            const fab = document.createElement('button');
            fab.className = 'help-fab';
            fab.id = 'helpFab';
            fab.title = 'Help (F1) — search the help and the program';
            fab.innerHTML = '?';
            fab.onclick = () => toggleQuick();
            document.body.appendChild(fab);
            wireQuick();
            renderDockCheckBadge();
        }
    }

    function toggleQuick(force) {
        const panel = el('helpQuick');
        const fab = el('helpFab');
        if (!panel) return;
        const on = force === undefined ? !panel.classList.contains('on') : !!force;
        panel.classList.toggle('on', on);
        if (on) {
            if (fab) fab.classList.add('on');
            paintQuick(state.query);
            const input = el('helpQuickInput');
            if (input) { input.value = state.query; input.focus(); }
        }
    }

    function wireQuick() {
        const input = el('helpQuickInput');
        if (input) {
            wireSearch(input, el('helpQuickSuggest'), (pick) => {
                toggleQuick(false);
                applyPick(pick);
            });
            input.addEventListener('input', () => paintQuick(input.value));
        }
        if (el('helpQuickX')) el('helpQuickX').onclick = () => toggleQuick(false);
        if (el('helpQuickOpen')) el('helpQuickOpen').onclick = () => { toggleQuick(false); openHelp(el('helpQuickInput').value || ''); };
    }

    function paintQuick(query) {
        const host = el('helpQuickResults');
        if (!host) return;
        const q = String(query || '').trim();
        if (!q) {
            host.innerHTML = '<div class="help-empty">Type to search: panels, actions, settings, fixes — '
                + 'the same engine the Help Centre uses.</div>';
            return;
        }
        const res = SEARCH ? SEARCH.search(q, buildSearchIndex(), { limit: 12 }) : { results: [], total: 0, corrected: '' };
        host.innerHTML = res.results.length
            ? res.results.map((row, i) => '<button class="help-result" data-quick="' + i + '">'
                + '<div class="help-result-t">' + esc(row.title) + '</div>'
                + '<div class="help-result-s">' + esc(row.snippet) + '</div></button>').join('')
            : '<div class="help-empty">Nothing matches “' + esc(q) + '”.</div>';
        host.querySelectorAll('[data-quick]').forEach((b) => {
            b.onclick = () => {
                const row = res.results[Number(b.dataset.quick)];
                toggleQuick(false);
                if (row) openTopic(row.id, false);
            };
        });
    }

    function renderDockCheckBadge() {
        const badge = el('helpDockBadge');
        const fab = el('helpFab');
        const counts = (state.check && state.check.counts) || {};
        const bad = (counts.error || 0) + (counts.warn || 0);
        if (badge) {
            badge.className = 'help-lvl ' + (counts.error ? 'error' : (counts.warn ? 'warn' : ''));
            badge.textContent = bad ? String(bad) : '';
            badge.title = bad ? bad + ' thing(s) the system check is unhappy about' : 'the system check is happy';
            badge.style.display = bad ? '' : 'none';
        }
        if (fab && bad) {
            fab.innerHTML = '?<span class="help-lvl error" style="margin-left:4px">' + bad + '</span>';
        } else if (fab) {
            fab.innerHTML = '?';
        }
    }

    /* ── entry points the rest of the app uses ─────────────────────────────────────────────── */

    function openHelp(query) {
        if (typeof window.showView === 'function') window.showView('help');
        const input = el('helpSearch');
        if (input) {
            input.value = String(query || '');
            input.focus();
        }
        if (query) runSearch(query, true);
        else if (!state.open) { renderTopic(topicById('start.help')); }
        return true;
    }

    /* ── wiring and boot ──────────────────────────────────────────────────────────────────── */

    function wireKeys() {
        if (!window.OFAPKEYS) return;
        /* `inField: true`: F1 archives nothing and types nothing, so the typing guard (which exists
           to protect characters) must not swallow it — a user in the middle of a search box presses
           F1 precisely when they want the help on top of what they are doing. */
        OFAPKEYS.bind({ id: 'help-centre', keys: ['f1'], scope: 'Global', inField: true,
            label: 'help for the panel you are in', run: () => {
                const topic = focusedTopic();
                if (topic) openTopic(topic, false);
                else openHelp('');
            } });
        OFAPKEYS.bind({ id: 'help-search', keys: ['ctrl+shift+h'], scope: 'Global', inField: true,
            label: 'search the help', run: () => openHelp('') });
    }

    /* The rail's Help item carries a dot when the system check has something to say, so a quiet
       problem is visible without opening the panel. */
    function markRail() {
        const btn = document.querySelector('.nav-item[data-view="help"]');
        if (!btn) return;
        const counts = (state.check && state.check.counts) || {};
        const bad = (counts.error || 0) + (counts.warn || 0);
        let dot = btn.querySelector('.help-rail-dot');
        if (!bad) { if (dot) dot.remove(); return; }
        if (!dot) {
            dot = document.createElement('span');
            dot.className = 'nav-badge help-rail-dot';
            btn.appendChild(dot);
        }
        dot.textContent = String(bad);
        dot.title = bad + ' thing(s) the system check is unhappy about';
    }

    function boot() {
        readMirror();
        buildView();
        renderTree();
        renderTopic(topicById('start.help'));
        buildLauncher();
        wireKeys();
        wireHelpLinks();
        activateIfDeepLinked();
        state.ready = true;
        /* One read of the live facts; the panel works without it (the corpus is local) and says so. */
        refreshCheck(false).then((res) => {
            if (res) {
                renderTree();
                buildLauncher();
                markRail();
                if (state.open) renderTopic(topicById(state.open));
            } else {
                state.offline = true;
                if (el('helpSub')) {
                    el('helpSub').textContent = 'the help content is local; the live facts and the system '
                        + 'check need the app\'s own server, which did not answer';
                }
            }
        });
    }

    /* ── contextual help wiring (T1) ─────────────────────────────────────────────────────────
       Help where the user is stuck: every panel head gains its own "?", any element carrying
       data-helptopic opens that topic, and F1 answers for the panel in focus rather than the
       Help Centre's front page. Every id here resolves against the same corpus the coverage
       test holds index.html against. */

    /* The topic of the panel in focus: the widget the shell is working in (Terminal mode), else
       the visible view section. `''` when the app cannot say — the Help Centre front page answers. */
    function focusedTopic() {
        let view = '';
        const shell = window.OFAPSHELL;
        if (shell && typeof shell.state === 'function') {
            const st = shell.state() || {};
            if (st.mode === 'terminal' && st.focus) view = String(st.focus);
        }
        if (!view) {
            const section = document.querySelector('.view.active[data-view]');
            if (section) view = section.getAttribute('data-view') || '';
        }
        const map = (DATA && DATA.views) || {};
        return map[view] || '';
    }

    /* One "?" per panel head, pointing at that view's own topic. Idempotent: a re-run (an injected
       view arriving, a re-parented widget) never doubles the button. */
    function injectPanelHelp(root) {
        const map = (DATA && DATA.views) || {};
        const sections = (root || document).querySelectorAll('.view[data-view]');
        for (let i = 0; i < sections.length; i += 1) {
            const section = sections[i];
            const topic = map[section.getAttribute('data-view') || ''];
            if (!topic) continue;
            const head = section.querySelector('.view-head');
            if (!head || head.querySelector('.panel-help')) continue;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn small panel-help';
            btn.setAttribute('data-helptopic', topic);
            btn.setAttribute('title', 'Help for this panel (F1)');
            btn.setAttribute('aria-label', 'Help for this panel');
            btn.textContent = '?';
            head.appendChild(btn);
        }
    }

    /* The inline link helper, for modules that render their own blank states. */
    function topicLink(id, text) {
        return '<a href="#" class="help-link" data-helptopic="' + esc(id) + '">'
            + esc(text || 'help') + '</a>';
    }

    /* One delegated listener: any [data-helptopic] click opens its topic in the Help Centre. */
    function wireHelpLinks() {
        document.addEventListener('click', (ev) => {
            const node = ev.target && ev.target.closest ? ev.target.closest('[data-helptopic]') : null;
            if (!node) return;
            ev.preventDefault();
            openTopic(String(node.getAttribute('data-helptopic')), false);
        });
        injectPanelHelp();
        /* Views injected at runtime (Scanner, this module's own entry) arrive after boot; a
           debounced sweep adopts them without paying for the observer on every live repaint. */
        if (window.MutationObserver) {
            let pending = 0;
            new MutationObserver(() => {
                window.clearTimeout(pending);
                pending = window.setTimeout(injectPanelHelp, 250);
            }).observe(document.body, { childList: true, subtree: true });
        }
    }

    window.OFAPHELP = {
        open: openHelp,
        openTopic: openTopic,
        openAbout: openAbout,
        openCheck: () => { void refreshCheck(true).then(() => openTopic('support.syscheck', false)); },
        focusedTopic: focusedTopic,
        topicLink: topicLink,
        setMode: setMode,
        setDock: setDock,
        cycleDock: cycleDock,
        toggleQuick: toggleQuick,
        mode: () => state.mode,
        dock: () => state.dock,
        facts: () => state.facts,
        credits: () => state.credits,
        links: () => state.links,
        check: () => state.check,
        refresh: () => refreshCheck(false),
        state: state,
    };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
