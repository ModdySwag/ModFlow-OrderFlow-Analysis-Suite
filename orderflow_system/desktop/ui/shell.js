/* shell.js — the terminal host: the same panels, arranged as widgets.
 *
 * The insight this file is built on: every panel in this suite is already a widget in all but name.
 * A view is a <section class="view" data-view="X"> that boots itself from a MutationObserver on its
 * own section when that section carries .active. Re-parenting such a section into a widget frame
 * with appendChild PRESERVES its DOM and its listeners, so the terminal is a host, not a fork — and
 * switching back to Classic is a re-parent, not a rebuild.
 *
 * The rules this file keeps:
 *   - Classic is untouched. In Classic mode no host exists, no class is added, and the .active
 *     contract belongs entirely to the app's own showView.
 *   - Every panel stays in the document at all times. Frames on a hidden tab are hidden with CSS,
 *     never detached: a detached section makes `document.querySelector('.view[data-view=x]')`
 *     return null, and the pollers that only ask whether a view is active would break on it.
 *   - A section carries .active exactly while one of the frames showing it is visible — the same
 *     meaning that class already had, so every existing poller keeps working unchanged.
 *   - Nothing here touches the feed, the engine or the socket. Arrangement is presentation.
 *
 * The arrangement itself lives in the config file behind /api/control/layouts (config_store's
 * sanitiser is the authority); this module adopts whatever the store accepted and says so in the
 * bar when it could not keep something.
 */
(function () {
    'use strict';

    const VERSION = '0.2.0';
    const GRID = { cols: 12, rows: 8 };                 // the same numbers as config_store's layout block
    const STARTER = ['overview', 'ofx', 'tape', 'depth'];
    const SIZES = { m: [6, 4], l: [8, 5] };
    const MAX_TABS = 12;
    const MAX_WIDGETS = 24;
    const hasDom = typeof document !== 'undefined' && !!document.createElement;

    /* §73: this page may BE an auxiliary window — the launcher opens one with
       `?aux=<view>&win=<id>` so a widget can live on another monitor. An auxiliary window reads as
       little of the store as it can: it never saves a layout, never changes the mode and never
       adopts this screen's layout, because it is a *view* of one widget, not a second board. */
    function auxRequest() {
        if (!hasDom) return null;
        const query = String((window.location && window.location.search) || '');
        const aux = /[?&]aux=([a-z0-9_-]{1,24})/.exec(query);
        if (!aux) return null;
        const win = /[?&]win=([a-z0-9_-]{1,24})/.exec(query);
        return { view: aux[1], id: win ? win[1] : '' };
    }

    const AUX = auxRequest();
    /* §128: the app's own router reads this flag (ui.js) — an auxiliary window hosts one widget
       and routes nothing, so it must not write a #view hash into its URL (measured: §73 cleared
       the hash at boot and ui.js's showView put `#overview` straight back). */
    if (AUX && typeof window !== 'undefined') window.OFAPAUX = true;

    /* ══ pure maths — no DOM in this block (shell.selftest.js drives it directly) ═══════════════ */

    function num(value, fallback) {
        /* null / undefined / '' / booleans are *missing*, not zero: Number('') and Number(null) are
           both 0, and the repo has already been bitten by that falsy-zero family once. */
        if (value === null || value === undefined || value === '' || typeof value === 'boolean') return fallback;
        const out = Number(value);
        return isFinite(out) ? out : fallback;
    }

    function slug(text) {
        return String(text == null ? '' : text).trim().toLowerCase()
            .replace(/[^a-z0-9_-]+/g, '-').replace(/^[^a-z0-9]+/, '').slice(0, 24);
    }

    const math = {
        /* §72: a screen's identity — its size and scale, plus where it sits when that origin is
           not the primary's (0,0). Two identical monitors are then two different screens instead
           of one key, and the primary keeps the original "WxH@dpr" shape, so layouts a user saved
           for it before this change still match it. */
        screenKeyOf(scr, dpr) {
            const s = scr && typeof scr === 'object' ? scr : {};
            const w = Math.round(num(s.width, 0));
            const h = Math.round(num(s.height, 0));
            if (!w || !h) return '';
            const scale = Math.round(num(dpr, 1) * 100) / 100 || 1;
            const x = Math.round(num(s.availLeft, 0));
            const y = Math.round(num(s.availTop, 0));
            const origin = (x || y) ? '@' + x + ',' + y : '';
            return (w + 'x' + h + '@' + scale + origin).slice(0, 24);
        },

        /* §72: which stored layout belongs to this screen — the most recently saved layout tagged
           with that screen's key. Returns the id to switch to, or '' when nothing matches and
           nothing should change (a screen with no layout of its own keeps the active one). */
        pickScreenLayout(items, key, activeId) {
            const store = items && typeof items === 'object' ? items : {};
            if (!key) return '';
            let best = '';
            let bestAt = -1;
            Object.keys(store).forEach(function (id) {
                const row = store[id] || {};
                if (String(row.screen_key || '') !== key) return;
                const at = Number(row.saved) || 0;
                if (at > bestAt || (at === bestAt && best && id < best)) { best = id; bestAt = at; }
            });
            return (best && best !== activeId) ? best : '';
        },

        /* A rect inside the grid: size first, then position — the same two-phase clamp the store
           does, so a widget can never be placed hanging off the edge. */
        clampRect(rect, grid) {
            const g = grid || GRID;
            const box = rect && typeof rect === 'object' ? rect : {};
            const w = Math.max(1, Math.min(g.cols, Math.round(num(box.w, 6))));
            const h = Math.max(1, Math.min(g.rows, Math.round(num(box.h, 4))));
            const x = Math.max(0, Math.min(g.cols - w, Math.round(num(box.x, 0))));
            const y = Math.max(0, Math.min(g.rows - h, Math.round(num(box.y, 0))));
            return { x: x, y: y, w: w, h: h };
        },

        overlaps(a, b) {
            return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
        },

        /* The first free slot for a w×h widget, scanning rows then columns, or null when full. */
        firstSlot(widgets, w, h, grid) {
            const g = grid || GRID;
            const taken = (widgets || []).map(function (r) { return math.clampRect(r, g); });
            const box = math.clampRect({ x: 0, y: 0, w: w, h: h }, g);
            for (let y = 0; y + box.h <= g.rows; y += 1) {
                for (let x = 0; x + box.w <= g.cols; x += 1) {
                    const probe = { x: x, y: y, w: box.w, h: box.h };
                    if (!taken.some(function (r) { return math.overlaps(probe, r); })) return { x: x, y: y };
                }
            }
            return null;
        },

        /* A dense tiling of n widgets: columns first (ceil(sqrt(n))), every rect inside the grid and
           none overlapping the others. Used for the starter layout and for auto-arrange. */
        tile(n, grid) {
            const g = grid || GRID;
            const count = Math.max(0, Math.min(Math.round(num(n, 0)), MAX_WIDGETS));
            if (!count) return [];
            const cols = Math.max(1, Math.ceil(Math.sqrt(count)));
            const rows = Math.max(1, Math.ceil(count / cols));
            const baseW = Math.max(1, Math.floor(g.cols / cols));
            const baseH = Math.max(1, Math.floor(g.rows / rows));
            const out = [];
            for (let i = 0; i < count; i += 1) {
                const c = i % cols, r = Math.floor(i / cols);
                out.push({ x: c * baseW, y: r * baseH, w: baseW, h: baseH });
            }
            out.forEach(function (rect, i) {
                const c = i % cols, r = Math.floor(i / cols);
                if (c === cols - 1) rect.w = g.cols - rect.x;        // the remainder joins the last column
                if (r === rows - 1) rect.h = g.rows - rect.y;        // …and the last row
            });
            return out;
        },

        /* Where a pointer is in the grid, from the grid's own box — the gesture handlers convert once
           and everything else works in cells. */
        cellAt(point, box, grid) {
            const g = grid || GRID;
            const width = Math.max(1, num(box && box.width, 0));
            const height = Math.max(1, num(box && box.height, 0));
            const left = num(box && box.left, 0);
            const top = num(box && box.top, 0);
            const col = Math.floor(((num(point && point.x, 0) - left) / width) * g.cols);
            const row = Math.floor(((num(point && point.y, 0) - top) / height) * g.rows);
            return { col: Math.max(0, Math.min(g.cols - 1, col)), row: Math.max(0, Math.min(g.rows - 1, row)) };
        },

        /* Moving is a delta in cells, then the same clamp a stored rect gets: a drag can never put a
           widget outside the grid, however far the pointer went. */
        moveRect(rect, dCol, dRow, grid) {
            const g = grid || GRID;
            const base = math.clampRect(rect, g);
            return math.clampRect({ x: base.x + Math.round(num(dCol, 0)), y: base.y + Math.round(num(dRow, 0)),
                                    w: base.w, h: base.h }, g);
        },

        /* Resizing keeps the top-left corner and grows into the space that is actually there: the size
           is limited by the distance to the grid's right/bottom edge, NOT by clampRect's "a 12-wide
           widget must sit at x=0" rule — that rule is for storage, and applied here it made a long
           rightward drag jump the widget to the left edge at full width. */
        resizeRect(rect, dW, dH, grid) {
            const g = grid || GRID;
            const base = math.clampRect(rect, g);
            const w = Math.max(1, Math.min(g.cols - base.x, base.w + Math.round(num(dW, 0))));
            const h = Math.max(1, Math.min(g.rows - base.y, base.h + Math.round(num(dH, 0))));
            return { x: base.x, y: base.y, w: Math.min(g.cols, w), h: Math.min(g.rows, h) };
        },

        /* Tab reordering as a pure list operation, so the drag target can be computed before the DOM
           moves (and the self-test can pin it). */
        reorder(list, from, to) {
            const out = (list || []).slice();
            if (from < 0 || from >= out.length || to < 0 || to >= out.length || from === to) return out;
            const row = out.splice(from, 1)[0];
            out.splice(to, 0, row);
            return out;
        },

        /* A widget's link is "<symbol group>/<timeframe group>" with either side optional (A-D) —
           exactly what the config store accepts. These two are the shape's only readers and writers. */
        parseLink(text) {
            const upper = String(text == null ? '' : text).trim().toUpperCase();
            if (upper === '/' || !/^[A-D]?(\/[A-D]?)?$/.test(upper)) return { sym: '', tf: '' };
            const parts = upper.split('/');
            return { sym: parts[0] || '', tf: parts.length > 1 ? (parts[1] || '') : '' };
        },
        formatLink(spec) {
            const one = function (group) {
                const text = String((spec && spec[group]) || '').trim().toUpperCase();
                return /^[A-D]$/.test(text) ? text : '';
            };
            const sym = one('sym');
            const tf = one('tf');
            if (!sym && !tf) return '';
            return sym + '/' + tf;
        },

        countWidgets(layout) {
            const tabs = (layout && layout.tabs) || [];
            return tabs.reduce(function (n, tab) { return n + ((tab.widgets || []).length); }, 0);
        },

        /* The layout as this shell will use it. Drops widgets for views this build does not have and
           repeats of a view (there is one section per view, so there can be one frame per view),
           clamps every rect, makes tab ids unique, and guarantees at least one tab. */
        normaliseLayout(raw, known, grid) {
            const g = grid || GRID;
            const src = raw && typeof raw === 'object' ? raw : {};
            const allowed = (known || []).filter(Boolean);
            const seen = Object.create(null);
            const usedIds = Object.create(null);
            const tabs = [];
            (Array.isArray(src.tabs) ? src.tabs : []).forEach(function (rawTab, index) {
                if (tabs.length >= MAX_TABS) return;
                const tab = rawTab && typeof rawTab === 'object' ? rawTab : {};
                let id = slug(tab.id) || ('t' + (index + 1));
                while (usedIds[id]) id += 'x';
                usedIds[id] = true;
                const widgets = [];
                (Array.isArray(tab.widgets) ? tab.widgets : []).forEach(function (rawWidget) {
                    if (widgets.length >= MAX_WIDGETS) return;
                    const widget = rawWidget && typeof rawWidget === 'object' ? rawWidget : {};
                    const view = String(widget.view || '').trim().toLowerCase();
                    if (!view || seen[view]) return;
                    if (allowed.length && allowed.indexOf(view) < 0) return;
                    seen[view] = true;
                    const rect = math.clampRect(widget, g);
                    widgets.push({
                        view: view, x: rect.x, y: rect.y, w: rect.w, h: rect.h,
                        link: String(widget.link || '').slice(0, 16),
                        settings: (widget.settings && typeof widget.settings === 'object') ? widget.settings : {},
                    });
                });
                tabs.push({ id: id, name: String(tab.name || '').slice(0, 40) || ('Tab ' + (index + 1)),
                            widgets: widgets });
            });
            if (!tabs.length) tabs.push({ id: 'main', name: 'Main', widgets: [] });
            return {
                id: slug(src.id) || 'ly',
                name: String(src.name || '').slice(0, 40) || 'Layout',
                mode: src.mode === 'classic' ? 'classic' : 'terminal',
                screen_key: String(src.screen_key || '').slice(0, 24),
                theme: src.theme === 'light' ? 'light' : 'dark',
                saved: Math.round(num(src.saved, 0)),
                tabs: tabs,
            };
        },

        /* The arrangement a first-time terminal opens with: the starter panels this build actually
           has, tiled so nothing overlaps. */
        defaultLayout(known, grid, id) {
            const g = grid || GRID;
            const allowed = (known || []).filter(Boolean);
            const wanted = STARTER.filter(function (v) { return allowed.indexOf(v) >= 0; });
            const views = wanted.length ? wanted : allowed.slice(0, 4);
            const rects = math.tile(views.length, g);
            return {
                id: slug(id) || 'lystart', name: 'Start', mode: 'terminal', screen_key: '', theme: 'dark',
                saved: 0,
                tabs: [{
                    id: 'main', name: 'Main',
                    widgets: views.map(function (view, i) {
                        return { view: view, x: rects[i].x, y: rects[i].y, w: rects[i].w, h: rects[i].h,
                                 link: '', settings: {} };
                    }),
                }],
            };
        },
    };

    /* ══ state ══════════════════════════════════════════════════════════════════════════════════ */

    const S = {
        mode: 'classic', hooked: false, base: null, feed: null,
        items: {}, layoutId: '', layout: null, activeTab: '', focus: '',
        frames: new Map(), host: null, grid: null, tabsEl: null, bar: null, noteEl: null, addEl: null,
        home: null, notice: '', error: '', created: false, addCount: 0, relayoutTimer: 0,
        gesture: null, maximised: '', preMax: new Map(), dragTab: '',
        switches: 0, saves: 0, savedAt: 0, saveTimer: 0, dirtyAt: 0, locked: false,
    };

    /* ══ DOM helpers ════════════════════════════════════════════════════════════════════════════ */

    function viewsRoot() {
        return document.querySelector('main.views') || document.querySelector('.views');
    }

    function sectionFor(view) {
        return document.querySelector('section.view[data-view="' + view + '"]');
    }

    function knownViews() {
        return Array.prototype.slice.call(document.querySelectorAll('section.view[data-view]'))
            .map(function (sec) { return sec.getAttribute('data-view'); })
            .filter(Boolean);
    }

    /* T4/A9: the widget title carries the live token — label · instrument. Refreshed in
       paintBar(), so a terminal montage always says which instrument each panel holds. */
    function titleToken(view) {
        const base = titleOf(view);
        const sel = document.getElementById('symbolSelect');
        const sym = (sel && sel.value) ? String(sel.value) : '';
        return sym ? base + ' · ' + sym : base;
    }

    function titleOf(view) {
        const sec = sectionFor(view);
        const own = sec && sec.querySelector('.view-title');
        let text = own ? (own.textContent || '').trim() : '';
        if (!text) {
            const btn = document.querySelector('.nav-item[data-view="' + view + '"]');
            if (btn) {
                const clone = btn.cloneNode(true);
                ['.nav-icon', '.nav-badge'].forEach(function (sel) {
                    const node = clone.querySelector(sel);
                    if (node && node.parentNode) node.parentNode.removeChild(node);
                });
                text = (clone.textContent || '').trim();
            }
        }
        return text || view;
    }

    function currentView() {
        const hash = (location.hash || '').slice(1);
        if (hash && sectionFor(hash)) return hash;
        if (S.mode === 'terminal' && S.focus) return S.focus;
        const active = document.querySelector('section.view.active[data-view]');
        return (active && active.getAttribute('data-view')) || 'overview';
    }

    function activeTab() {
        const tabs = (S.layout && S.layout.tabs) || [];
        for (let i = 0; i < tabs.length; i += 1) if (tabs[i].id === S.activeTab) return tabs[i];
        return tabs[0];
    }

    function route(method, body) {
        const opts = method === 'POST' ? { method: 'POST', body: body } : {};
        if (typeof api === 'function') return api('/api/control/layouts', opts);
        return fetch('/api/control/layouts', {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined,
        }).then(function (res) { return res.json(); });
    }

    /* ══ the host ═══════════════════════════════════════════════════════════════════════════════ */

    function buildHost() {
        const root = viewsRoot();
        const host = document.createElement('div');
        host.className = 'term-shell';
        host.id = 'termShell';

        const bar = document.createElement('div');
        bar.className = 'term-bar';
        const name = document.createElement('span');
        name.className = 'term-name';
        name.textContent = '◫ Terminal';
        const tabs = document.createElement('span');
        tabs.className = 'term-tabs';
        const note = document.createElement('span');
        note.className = 'term-note';
        const add = document.createElement('select');
        add.className = 'term-add';
        add.title = 'Put another panel on this tab';
        add.appendChild(new Option('+ widget', ''));
        knownViews().forEach(function (view) { add.appendChild(new Option(titleOf(view), view)); });
        add.onchange = function () {
            const view = add.value;
            add.value = '';
            if (view) openWidget(view);
        };
        const classic = document.createElement('button');
        classic.type = 'button';
        classic.className = 'term-btn';
        classic.textContent = '⊞ Classic';
        classic.title = 'Back to the classic single-view layout (Ctrl+Alt+T)';
        classic.onclick = function () { switchTo('classic'); };

        /* §73: the widget-window control lives in its own module (windows-ui.js) and fills this
           span — the shell owns the bar, the window module owns everything native. */
        const wins = document.createElement('span');
        wins.className = 'term-wins';

        if (AUX) {
            /* An auxiliary window is one widget: no tabs, no “+ widget”, no way back to Classic,
               and a name that says which widget this is. */
            name.textContent = '⧉ ' + titleOf(AUX.view);
            note.textContent = AUX.id ? 'window ' + AUX.id : 'widget window';
            bar.appendChild(name);
            bar.appendChild(note);
            bar.appendChild(wins);
        } else {
            bar.appendChild(name);
            bar.appendChild(tabs);
            bar.appendChild(note);
            bar.appendChild(add);
            bar.appendChild(wins);
            bar.appendChild(classic);
        }

        const grid = document.createElement('div');
        grid.className = 'term-grid';
        grid.setAttribute('data-surface', 'terminal');

        host.appendChild(bar);
        host.appendChild(grid);
        root.appendChild(host);

        S.host = host; S.bar = bar; S.tabsEl = tabs; S.noteEl = note; S.addEl = add; S.grid = grid;
        S.winsEl = wins;
        if (window.OFAPWINDOWS && typeof window.OFAPWINDOWS.attach === 'function') {
            try {
                window.OFAPWINDOWS.attach(wins, { aux: AUX, view: (AUX && AUX.view) || '' });
            } catch (e) { /* the bar must never fail to build because of the window control */ }
        }
    }

    function widgetButton(glyph, tip, run) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'wf-btn';
        btn.textContent = glyph;
        btn.title = tip;
        btn.onclick = function (ev) {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            run(btn);                        // §128: the window menu anchors to the button itself
        };
        return btn;
    }

    function buildFrame(view) {
        const sec = sectionFor(view);
        if (!sec) return null;
        const frame = document.createElement('section');
        frame.className = 'widget-frame';
        frame.setAttribute('data-frame', view);

        const bar = document.createElement('header');
        bar.className = 'wf-bar';
        bar.title = 'Drag to move this widget';
        const title = document.createElement('span');
        title.className = 'wf-title';
        title.textContent = titleToken(view);
        const tools = document.createElement('span');
        tools.className = 'wf-tools';
        tools.appendChild(buildLinkChip(view, frame));
        tools.appendChild(widgetButton('⚙', "This panel's variables (the parameter registry)",
            function () { openPanelSettings(view); }));
        tools.appendChild(widgetButton('⛶', 'Fill the grid with this widget (F11) — Esc puts it back',
            function () { toggleMax(view); }));
        /* §128: the widget's own way onto another monitor. The menu opens aimed at THIS widget and
           anchored to its button, so "put the tape on Monitor 2, right half" never leaves the
           widget (Ctrl+Alt+W is the keyboard form of the same click). */
        tools.appendChild(widgetButton('⧉', 'Window: send this widget to a monitor, snap it, or pin it',
            function (btn) {
                if (window.OFAPWINDOWS && OFAPWINDOWS.openFor) OFAPWINDOWS.openFor(view, btn);
            }));
        tools.appendChild(widgetButton('×', 'Take this widget off the tab',
            function () { closeWidget(view); }));
        bar.appendChild(title);
        bar.appendChild(tools);
        bar.addEventListener('pointerdown', function (ev) { beginGesture('move', ev, view); });

        const body = document.createElement('div');
        body.className = 'wf-body';
        const grip = document.createElement('span');
        grip.className = 'wf-grip';
        grip.title = gripTip();                 // placeFrame() fills in the live size
        grip.addEventListener('pointerdown', function (ev) { beginGesture('resize', ev, view); });

        frame.appendChild(bar);
        frame.appendChild(body);
        frame.appendChild(grip);
        body.appendChild(sec);                       // re-parent: DOM and listeners survive untouched
        /* Any click in the frame makes it the focused widget, so F11/Esc/the gear act on the panel the
           user is actually working in (and the menu bar's Chart menu follows it). */
        frame.addEventListener('pointerdown', function () { setFocus(view); }, true);
        S.grid.appendChild(frame);
        /* Legacy panels (tape, orderflow, depth, signals, performance, strategy, chart) create their
           instance lazily inside ui.js ensurePanel(), which only the classic showView path calls; the
           terminal wrapper above never runs it, so such a widget would sit empty (measured on tape).
           Ask the app for the instance now that the section is in its frame — ensurePanel is
           idempotent, so this is a no-op for panels that build themselves from their observer. */
        if (window.ensurePanel) { try { window.ensurePanel(view); } catch (e) { /* the panel's own problem */ } }
        return frame;
    }

    /* A widget's size belongs on the RESIZE GRIP, not on the frame: the old whole-frame title
       (`view · w×h cells` set on the frame element) put a native tooltip over the WHOLE panel, so
       hovering anywhere inside a widget — over its chart, its text, its table — popped a box
       covering the thing being read (owner's screenshot, §131). The frame bar already names the
       widget and carries the move hint; this keeps the one genuinely useful fact (how big it is, in
       grid cells) where a user reaches for it, and refreshes it on every placement change. */
    function gripTip(w, h) {
        const size = (w && h) ? ' — now ' + w + '×' + h + ' cells' : '';
        return 'Drag to resize this widget' + size;
    }

    function placeFrame(frame, widget) {
        frame.style.gridColumn = (widget.x + 1) + ' / span ' + widget.w;
        frame.style.gridRow = (widget.y + 1) + ' / span ' + widget.h;
        const grip = frame.querySelector ? frame.querySelector('.wf-grip') : null;
        if (grip) grip.title = gripTip(widget.w, widget.h);
        frame.classList.toggle('wf-max', !!(widget.settings && widget.settings.max));
        paintLinkChip(widget.view);
    }

    function releaseFrame(view) {
        const frame = S.frames.get(view);
        const sec = sectionFor(view);
        const root = viewsRoot();
        if (sec && root) root.appendChild(sec);      // still in the document, hidden by CSS
        /* Back in Classic, not on screen — so it must not keep .active. A closed widget's section used to
           hold the class while being invisible (measured: .active true, offsetParent null, 0x0, in no
           frame), and every panel for that view kept polling behind an unplaced section. */
        if (sec && sec.classList) sec.classList.remove('active');
        if (frame && frame.parentNode) frame.parentNode.removeChild(frame);
        S.frames.delete(view);
    }

    /* Every frame of the layout exists at all times — including the tabs you are not looking at,
       hidden with .wf-off — so no section ever leaves the document. */
    function renderFrames() {
        const keep = Object.create(null);
        S.layout.tabs.forEach(function (tab) {
            tab.widgets.forEach(function (widget) {
                let frame = S.frames.get(widget.view);
                if (!frame) {
                    frame = buildFrame(widget.view);
                    if (!frame) return;
                    S.frames.set(widget.view, frame);
                }
                keep[widget.view] = true;
                frame.dataset.tab = tab.id;
                placeFrame(frame, widget);
            });
        });
        Array.from(S.frames.keys()).forEach(function (view) {
            if (!keep[view]) releaseFrame(view);
        });
    }

    function renderTabs() {
        if (!S.tabsEl || !S.layout) return;
        S.tabsEl.textContent = '';
        S.layout.tabs.forEach(function (tab, index) {
            const chip = document.createElement('span');
            chip.className = 'term-tab' + (tab.id === S.activeTab ? ' on' : '');
            chip.draggable = true;
            chip.dataset.tab = tab.id;
            const label = document.createElement('button');
            label.type = 'button';
            label.className = 'tt-name';
            label.textContent = tab.name + ' · ' + tab.widgets.length;
            label.title = 'Show this tab (' + tab.widgets.length + ' widget' + (tab.widgets.length === 1 ? '' : 's') +
                          ') — double-click to rename, drag to reorder';
            label.onclick = function () { applyTab(tab.id); };
            label.ondblclick = function () { renameTab(tab.id, chip); };
            chip.appendChild(label);
            if (tab.id === S.activeTab && S.layout.tabs.length > 1) {
                const shut = document.createElement('button');
                shut.type = 'button';
                shut.className = 'tt-x';
                shut.textContent = '×';
                shut.title = 'Close this tab';
                shut.onclick = function (ev) {
                    if (ev && ev.stopPropagation) ev.stopPropagation();
                    closeTab(tab.id);
                };
                chip.appendChild(shut);
            }
            chip.ondragstart = function (ev) {
                S.dragTab = tab.id;
                if (ev.dataTransfer) {
                    ev.dataTransfer.setData('text/plain', tab.id);
                    ev.dataTransfer.effectAllowed = 'move';
                }
            };
            chip.ondragover = function (ev) {
                if (!S.dragTab || S.dragTab === tab.id) return;
                if (ev.preventDefault) ev.preventDefault();
                chip.classList.add('tt-over');
            };
            chip.ondragleave = function () { chip.classList.remove('tt-over'); };
            chip.ondrop = function (ev) {
                if (ev.preventDefault) ev.preventDefault();
                chip.classList.remove('tt-over');
                const from = S.dragTab;
                S.dragTab = '';
                if (!from || from === tab.id) return;
                reorderTabs(from, index);
            };
            S.tabsEl.appendChild(chip);
        });
        const add = document.createElement('button');
        add.type = 'button';
        add.className = 'term-tab tt-add';
        add.textContent = '+';
        add.title = 'Add a tab';
        add.onclick = function () { addTab(); };
        S.tabsEl.appendChild(add);
    }

    function reorderTabs(id, toIndex) {
        if (refuseLocked()) return false;
        const from = S.layout ? S.layout.tabs.map(function (tab) { return tab.id; }).indexOf(id) : -1;
        if (from < 0) return false;
        S.layout.tabs = math.reorder(S.layout.tabs, from, toIndex);
        renderTabs();
        S.notice = 'tabs reordered';
        paintBar();
        saveSoon();
        return true;
    }

    function nextTabId() {
        let n = (S.layout.tabs.length || 0) + 1;
        const taken = S.layout.tabs.map(function (t) { return t.id; });
        while (taken.indexOf('t' + n) >= 0) n += 1;
        return 't' + n;
    }

    function addTab() {
        if (!S.layout) return '';
        if (refuseLocked()) return '';
        if (S.layout.tabs.length >= MAX_TABS) {
            S.notice = 'at most ' + MAX_TABS + ' tabs';
            paintBar();
            return '';
        }
        const id = nextTabId();
        S.layout.tabs.push({ id: id, name: 'Tab ' + (S.layout.tabs.length + 1), widgets: [] });
        applyTab(id);
        S.notice = 'added ' + id + ' — put a panel on it with [+ widget]';
        paintBar();
        saveSoon();
        return id;
    }

    function closeTab(id) {
        if (refuseLocked()) return false;
        if (!S.layout || S.layout.tabs.length <= 1) {
            S.notice = 'the last tab stays — it holds the layout';
            paintBar();
            return false;
        }
        const tab = S.layout.tabs.filter(function (t) { return t.id === id; })[0];
        if (!tab) return false;
        tab.widgets.forEach(function (widget) { releaseFrame(widget.view); });
        S.layout.tabs = S.layout.tabs.filter(function (t) { return t.id !== id; });
        applyTab(S.layout.tabs[0].id);
        S.notice = 'closed ' + tab.name +
                   (tab.widgets.length ? ' — ' + tab.widgets.length + ' panel(s) went with it' : '');
        paintBar();
        saveSoon();
        return true;
    }

    /* Renaming happens in place, and the input stops its own keys: a tab name of "1" must not be read
       as the tab-switch hotkey. */
    function renameTab(id, chip) {
        const tab = S.layout && S.layout.tabs.filter(function (t) { return t.id === id; })[0];
        if (!tab || !chip || chip.querySelector('input')) return false;
        const label = chip.querySelector('.tt-name');
        const input = document.createElement('input');
        input.className = 'tt-input';
        input.type = 'text';
        input.maxLength = 40;
        input.value = tab.name;
        chip.replaceChild(input, label);
        input.focus();
        input.select();
        const commit = function (keep) {
            const name = String(input.value || '').trim().slice(0, 40);
            if (keep && name && name !== tab.name) {
                tab.name = name;
                S.notice = 'renamed the tab to ' + name;
                saveSoon();
            }
            renderTabs();
            paintBar();
        };
        input.addEventListener('keydown', function (ev) {
            ev.stopPropagation();
            if (ev.key === 'Enter') commit(true);
            if (ev.key === 'Escape') commit(false);
        });
        input.addEventListener('blur', function () { commit(true); });
        return true;
    }

    /* ══ moving and resizing: one gesture, two readings ══════════════════════════════════════════ */

    /* T2 — the layout lock. Quantower's cheapest safety idea: one switch that holds the
       arrangement still (no move, no resize, no add, no remove) while the panels keep working.
       Persisted as ui.layout_lock so it means the same thing on the next start. */
    function setLocked(value) {
        S.locked = Boolean(value);
        if (typeof api === 'function') {
            void api('/api/control/config', { method: 'POST', body: { ui: { layout_lock: S.locked } } })
                .catch(function () { /* the lock still holds this session */ });
        }
        S.notice = S.locked
            ? 'layout locked — move, resize, add and remove are held; unlock in the Layout menu'
            : 'layout unlocked';
        paintBar();
        paintStatus();
        return S.locked;
    }

    function refuseLocked() {
        if (!S.locked) return false;
        S.notice = 'the layout is locked — unlock it in the Layout menu';
        paintBar();
        return true;
    }


    function beginGesture(kind, ev, view) {
        if (!S.grid || !S.layout || !hasDom) return;
        if (refuseLocked()) return;
        if (ev.button !== undefined && ev.button !== 0) return;
        if (ev.target && ev.target.closest && ev.target.closest('button')) return;   // a button is not a handle
        const widget = widgetFor(view);
        const frame = S.frames.get(view);
        if (!widget || !frame) return;
        if (ev.preventDefault) ev.preventDefault();
        const box = S.grid.getBoundingClientRect();
        S.gesture = {
            kind: kind, view: view, frame: frame, changed: false,
            cellW: Math.max(1, box.width / GRID.cols), cellH: Math.max(1, box.height / GRID.rows),
            start: { x: ev.clientX, y: ev.clientY },
            from: { x: widget.x, y: widget.y, w: widget.w, h: widget.h },
        };
        frame.classList.add('wf-moving');
        if (document.body) document.body.classList.add('wf-gesture');
        document.addEventListener('pointermove', onGestureMove, true);
        document.addEventListener('pointerup', endGesture, true);
        document.addEventListener('pointercancel', endGesture, true);
    }

    function onGestureMove(ev) {
        const g = S.gesture;
        if (!g) return;
        const widget = widgetFor(g.view);
        if (!widget) return;
        const dCol = Math.round((ev.clientX - g.start.x) / g.cellW);
        const dRow = Math.round((ev.clientY - g.start.y) / g.cellH);
        const next = g.kind === 'resize'
            ? math.resizeRect(g.from, dCol, dRow, GRID)
            : math.moveRect(g.from, dCol, dRow, GRID);
        if (next.x === widget.x && next.y === widget.y && next.w === widget.w && next.h === widget.h) return;
        widget.x = next.x; widget.y = next.y; widget.w = next.w; widget.h = next.h;
        placeFrame(g.frame, widget);
        g.changed = true;
        paintBar();
    }

    function endGesture() {
        const g = S.gesture;
        document.removeEventListener('pointermove', onGestureMove, true);
        document.removeEventListener('pointerup', endGesture, true);
        document.removeEventListener('pointercancel', endGesture, true);
        if (!g) return;
        S.gesture = null;
        if (document.body) document.body.classList.remove('wf-gesture');
        g.frame.classList.remove('wf-moving');
        if (!g.changed) return;
        S.grid.appendChild(g.frame);                 // the widget you just placed sits on top
        S.notice = (g.kind === 'resize' ? 'resized ' : 'moved ') + g.view +
                   ' — ' + (widgetFor(g.view) || {})['w'] + '×' + (widgetFor(g.view) || {})['h'] + ' cells';
        paintBar();
        notifyRelayout(g.kind);
        saveSoon();
    }

    /* ══ focus, maximise, panel settings ═════════════════════════════════════════════════════════ */

    function setFocus(view) {
        S.focus = view || '';
        S.frames.forEach(function (frame, key) { frame.classList.toggle('wf-focus', key === S.focus); });
        document.querySelectorAll('.nav-item').forEach(function (btn) {
            btn.classList.toggle('active', btn.getAttribute('data-view') === S.focus);
        });
        /* The menu bar's Chart menu is the ACTIVE view's registry, and in terminal mode several panels
           are on screen at once — so "active" has to mean "the widget the user is working in". */
        if (window.OFAPMenuBar && typeof window.OFAPMenuBar.setView === 'function') {
            window.OFAPMenuBar.setView(S.focus);
        }
    }

    function widgetFor(view) {
        const tab = activeTab();
        if (!tab) return null;
        const found = tab.widgets.filter(function (widget) { return widget.view === view; })[0];
        return found || null;
    }

    /* Membership is a property of the whole layout, not of the open tab: a link group spans every
       widget, and the Layout menu's counts and the links module both read it from here. */
    function layoutWidgetFor(view) {
        if (!S.layout) return null;
        let found = null;
        S.layout.tabs.forEach(function (tab) {
            tab.widgets.forEach(function (widget) { if (widget.view === view) found = widget; });
        });
        return found;
    }

    function linkSpec(view) {
        const widget = layoutWidgetFor(view);
        return math.parseLink(widget ? widget.link : '');
    }

    function setLink(view, spec) {
        const widget = layoutWidgetFor(view);
        if (!widget) return false;
        widget.link = math.formatLink(spec);
        paintLinkChip(view);
        saveSoon();
        /* The links module owns what the groups MEAN; the shell only knows where the membership is
           written. It re-reads on this event, so joining a group adopts that group's values at once. */
        document.dispatchEvent(new CustomEvent('ofap:links', { detail: { view: view, link: widget.link } }));
        return true;
    }

    function linkMembers() {
        const rows = [];
        if (!S.layout) return rows;
        S.layout.tabs.forEach(function (tab) {
            tab.widgets.forEach(function (widget) {
                const spec = math.parseLink(widget.link);
                rows.push({ view: widget.view, tab: tab.id, sym: spec.sym, tf: spec.tf, link: widget.link || '' });
            });
        });
        return rows;
    }

    function buildLinkChip(view, frame) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'wf-btn wf-link';
        chip.dataset.link = view;
        chip.title = 'Link this panel to a symbol/timeframe group (A-D)';
        const pop = document.createElement('div');
        pop.className = 'wf-links';
        pop.hidden = true;
        pop.dataset.linkPop = view;
        pop.appendChild(linkRow(view, 'sym', 'Symbol'));
        pop.appendChild(linkRow(view, 'tf', 'Timeframe'));
        pop.appendChild(linkColorRow());
        const note = document.createElement('div');
        note.className = 'wf-links-note';
        pop.appendChild(note);
        chip.onclick = function (ev) {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            pop.hidden = !pop.hidden;
            if (!pop.hidden) paintLinkChip(view);
        };
        chip.addEventListener('blur', function () {
            setTimeout(function () { if (!pop.contains(document.activeElement)) pop.hidden = true; }, 120);
        });
        frame.appendChild(pop);
        return chip;
    }

    /* T11/B17: one button per group showing its own colour; clicking cycles it through the
       palette. The colour always rides WITH the letter, so it never carries meaning alone. */
    function linkColorRow() {
        const row = document.createElement('div');
        row.className = 'wf-links-row';
        const head = document.createElement('span');
        head.className = 'wf-links-k';
        head.textContent = 'Colour';
        row.appendChild(head);
        ['A', 'B', 'C', 'D'].forEach(function (group) {
            const opt = document.createElement('button');
            opt.type = 'button';
            opt.className = 'wf-opt';
            opt.dataset.colorGroup = group;
            opt.textContent = group;
            opt.title = 'Cycle group ' + group + '’s colour — the letter always stays beside it';
            opt.onclick = function (ev) {
                if (ev && ev.stopPropagation) ev.stopPropagation();
                const api = window.OFAPLINKS;
                if (api && api.cycleColor) api.cycleColor(group);
            };
            row.appendChild(opt);
        });
        return row;
    }

    function linkRow(view, kind, label) {
        const row = document.createElement('div');
        row.className = 'wf-links-row';
        const head = document.createElement('span');
        head.className = 'wf-links-k';
        head.textContent = label;
        row.appendChild(head);
        ['', 'A', 'B', 'C', 'D'].forEach(function (group) {
            const opt = document.createElement('button');
            opt.type = 'button';
            opt.className = 'wf-opt';
            opt.dataset.kind = kind;
            opt.dataset.group = group;
            opt.textContent = group || '–';
            opt.title = group ? (label + ' group ' + group) : ('no ' + label.toLowerCase() + ' link');
            opt.onclick = function (ev) {
                if (ev && ev.stopPropagation) ev.stopPropagation();
                const spec = linkSpec(view);
                spec[kind] = group;
                setLink(view, spec);
            };
            row.appendChild(opt);
        });
        return row;
    }

    function paintLinkChip(view) {
        const frame = S.frames.get(view);
        if (!frame) return;
        const spec = linkSpec(view);
        const chip = frame.querySelector('.wf-link');
        if (chip) {
            /* T11/B17: the group letters carry their group's colour; the letter itself always
               stays, so colour never carries the meaning alone (the CVD pairing rule). */
            const L = window.OFAPLINKS;
            chip.textContent = '';
            chip.appendChild(document.createTextNode('⇄ '));
            [spec.sym, spec.tf].forEach(function (g, i) {
                if (i) chip.appendChild(document.createTextNode('·'));
                const b = document.createElement('b');
                b.textContent = g || '–';
                if (g && L && L.colorOf) { const c = L.colorOf(g); if (c) b.style.color = c; }
                if (g) b.title = 'group ' + g;
                chip.appendChild(b);
            });
            chip.classList.toggle('on', !!(spec.sym || spec.tf));
        }
        const pop = frame.querySelector('.wf-links');
        if (!pop) return;
        pop.querySelectorAll('.wf-opt').forEach(function (opt) {
            const on = (spec[opt.dataset.kind] || '') === opt.dataset.group;
            opt.classList.toggle('on', on);
        });
        /* T11/B17: the colour row shows each group's own colour; the letter always stays beside it. */
        pop.querySelectorAll('[data-color-group]').forEach(function (opt) {
            const api = window.OFAPLINKS;
            const c = api && api.colorOf ? api.colorOf(opt.dataset.colorGroup) : '';
            opt.style.color = c || '';
            opt.style.borderColor = c || '';
        });
        const note = pop.querySelector('.wf-links-note');
        if (note) {
            const api = window.OFAPLINKS;
            const groups = api && typeof api.groups === 'function' ? api.groups() : null;
            const bits = [];
            if (spec.sym && groups) {
                const own = api.SYMBOL_CONTROL && api.SYMBOL_CONTROL[view];
                bits.push('symbol ' + spec.sym + ' · ' + ((groups[spec.sym] || {}).symbol || '—') +
                    (own ? ' (this panel)' : ' (the app-wide instrument)'));
            }
            if (spec.tf && groups) {
                const raw = (groups[spec.tf] || {}).timeframe || '';
                bits.push('timeframe ' + spec.tf + ' · ' + (raw && api.tfLabel ? api.tfLabel(raw) : raw || '—'));
            }
            note.textContent = bits.length ? bits.join(' · ')
                : 'independent — this panel keeps its own symbol and timeframe';
        }
    }

    function maximisedView() {
        const tab = activeTab();
        if (!tab) return '';
        const found = tab.widgets.filter(function (widget) {
            return widget.settings && widget.settings.max;
        })[0];
        return found ? found.view : '';
    }

    function firstPlaced() {
        const tab = activeTab();
        return tab && tab.widgets.length ? tab.widgets[0].view : '';
    }

    /* Filling the grid is a stored rect change, not a modal state: the pre-maximise rect rides in the
       widget's own settings (scalars only, which is what the store keeps), so a reload comes back with
       the widget still maximised and Esc still puts it back where it was. */
    function toggleMax(view) {
        const widget = widgetFor(view);
        const frame = S.frames.get(view);
        if (!widget || !frame) return false;
        const settings = widget.settings || (widget.settings = {});
        if (settings.max) {
            const back = math.clampRect({ x: num(settings.px, widget.x), y: num(settings.py, widget.y),
                                          w: num(settings.pw, widget.w), h: num(settings.ph, widget.h) }, GRID);
            widget.x = back.x; widget.y = back.y; widget.w = back.w; widget.h = back.h;
            settings.max = false;
            S.notice = 'restored ' + view + ' to ' + back.w + '×' + back.h;
        } else {
            settings.px = widget.x; settings.py = widget.y;
            settings.pw = widget.w; settings.ph = widget.h;
            settings.max = true;
            widget.x = 0; widget.y = 0; widget.w = GRID.cols; widget.h = GRID.rows;
            S.notice = view + ' fills the grid — Esc or ⛶ puts it back';
        }
        placeFrame(frame, widget);
        S.grid.appendChild(frame);
        setFocus(view);
        notifyRelayout('maximise');
        paintBar();
        saveSoon();
        return true;
    }

    function openPanelSettings(view) {
        setFocus(view);
        if (window.OFAPMenuBar && typeof window.OFAPMenuBar.openFor === 'function') {
            window.OFAPMenuBar.openFor(view);
            return true;
        }
        S.notice = 'the parameter registry editor is not loaded in this build';
        paintBar();
        return false;
    }

    /* Visibility is two decisions in one place: the frame is shown or hidden, and the section's
       .active class follows it — which is what every view module already watches. */
    function applyTab(id) {
        if (!S.layout) return '';
        const tabs = S.layout.tabs;
        let tab = tabs[0];
        for (let i = 0; i < tabs.length; i += 1) if (tabs[i].id === id) tab = tabs[i];
        S.activeTab = tab.id;
        renderTabs();
        const onTab = Object.create(null);
        tab.widgets.forEach(function (widget) { onTab[widget.view] = true; });
        S.frames.forEach(function (frame, view) {
            const visible = !!onTab[view];
            frame.classList.toggle('wf-off', !visible);
            const sec = sectionFor(view);
            if (sec) sec.classList.toggle('active', visible);
        });
        notifyRelayout('tab ' + tab.id);
        paintBar();
        watchBus();
        paintStatus();
        return tab.id;
    }

    function paintBar() {
        if (!S.noteEl || !S.layout) return;
        refreshAdd();
        const bits = [];
        if (AUX) {
            /* §128: the window says WHICH window it is — the id is what the API, the dialog and the
               store all name it by (the "1 widget · focus" wording is the board's, not a window's). */
            bits.push(AUX.id ? 'window ' + AUX.id : 'widget window');
        } else {
            const count = math.countWidgets(S.layout);
            bits.push(count + ' widget' + (count === 1 ? '' : 's'));
        }
        if (S.focus) bits.push('focus: ' + S.focus);
        if (S.notice) bits.push(S.notice);
        if (S.error) bits.push('⚠ ' + S.error);
        S.noteEl.textContent = bits.join(' · ');
    }

    /* Panels must be told when their box changed. A re-parent is invisible to the window resize
       listeners they already have, so without this a canvas measured in Classic keeps that size
       inside a widget (measured: the Engine canvas stayed 293x240 in a 213x148 stage). Coalesced to
       one event per turn, because a single gesture can rebuild the arrangement more than once. */
    function notifyRelayout(reason) {
        if (!hasDom || S.relayoutTimer) return;
        S.relayoutTimer = setTimeout(function () {
            S.relayoutTimer = 0;
            document.dispatchEvent(new CustomEvent('ofap:relayout',
                { detail: { source: 'shell', reason: reason, mode: S.mode } }));
        }, 0);
    }

    /* A module can add its own view section after the host was built (the guide and the scanner both
       create theirs at load). Rebuild the list when that happens, so "[+ widget]" never goes stale. */
    function refreshAdd() {
        if (!S.addEl) return;
        const views = knownViews();
        if (views.length === S.addCount) return;
        S.addCount = views.length;
        const keep = S.addEl.value;
        S.addEl.textContent = '';
        S.addEl.appendChild(new Option('+ widget', ''));
        views.forEach(function (view) { S.addEl.appendChild(new Option(titleOf(view), view)); });
        S.addEl.value = keep;
    }

    /* ══ the switch ═════════════════════════════════════════════════════════════════════════════ */

    function ensureLayout() {
        if (AUX) {
            /* §73: one widget, full grid — a window is not a board, and it must never write. */
            const known = knownViews();
            const view = known.indexOf(AUX.view) >= 0 ? AUX.view : (known[0] || 'overview');
            const layout = math.defaultLayout([view], GRID, 'lyaux');
            layout.name = titleOf(view);
            S.layout = layout;
            S.layoutId = layout.id;
            S.activeTab = (layout.tabs[0] || {}).id || 'main';
            return layout;
        }
        const known = knownViews();
        const raw = (S.layoutId && S.items[S.layoutId]) || S.items[Object.keys(S.items)[0]];
        let layout;
        if (raw) {
            layout = math.normaliseLayout(raw, known, GRID);
            const lost = math.countWidgets(raw) - math.countWidgets(layout);
            if (lost > 0) S.notice = 'dropped ' + lost + ' widget' + (lost === 1 ? '' : 's') +
                                     ' this build has no panel for';
        } else {
            layout = math.defaultLayout(known, GRID, 'ly' + Math.random().toString(36).slice(2, 10));
            S.created = true;
        }
        S.layout = layout;
        S.layoutId = layout.id;
        S.activeTab = (layout.tabs[0] || {}).id || 'main';
        return layout;
    }

    function enterTerminal() {
        const root = viewsRoot();
        if (!root) throw new Error('no views container');
        ensureLayout();
        /* Exactly what the views container held, so Classic comes back as it was — recorded before
           anything moves. A node list is enough: the restore re-appends the whole sequence in order
           rather than reasoning about where each node currently sits. */
        S.home = { parent: root, nodes: Array.prototype.slice.call(root.children) };
        buildHost();
        renderFrames();
        applyTab(S.activeTab);
        document.body.classList.add('term-mode');
        S.mode = 'terminal';
        S.switches += 1;
        if (S.created) saveSoon();
        const view = currentView();
        if (sectionFor(view)) focusView(view);
        notifyRelayout('entered terminal');
        return stats();
    }

    function leaveTerminal() {
        Array.from(S.frames.keys()).forEach(releaseFrame);
        if (S.host && S.host.parentNode) S.host.parentNode.removeChild(S.host);
        S.host = S.grid = S.tabsEl = S.bar = S.noteEl = S.addEl = null;
        if (S.home && S.home.nodes.length) {
            /* Classic comes back in the recorded order, in one atomic move. Re-inserting each node
               "before its recorded next sibling" looks right and is not: a sibling that is still
               inside a frame reads as absent, that node is appended instead, and the list ends up
               shuffled (measured: 24 sections came back in the wrong order). A fragment re-append
               cannot depend on where the nodes happen to be. */
            const frag = document.createDocumentFragment();
            S.home.nodes.forEach(function (node) { frag.appendChild(node); });
            S.home.parent.appendChild(frag);
        }
        S.home = null;
        if (document.body) document.body.classList.remove('term-mode');
        S.mode = 'classic';
        S.switches += 1;
        S.focus = '';
        S.frames.clear();
        /* hand the single-view contract back to the app's own showView (our wrapper delegates to it) */
        if (typeof S.base === 'function') S.base(currentView());
        notifyRelayout('left terminal');
        return stats();
    }

    function switchTo(mode, opts) {
        opts = opts || {};
        const want = mode === 'terminal' ? 'terminal' : 'classic';
        if (!hasDom) { S.error = 'no document — the terminal needs a browser'; return stats(); }
        if (want === 'terminal' && S.mode === 'terminal') return stats();
        if (want === 'classic' && S.mode === 'classic') { if (S.bar) paintBar(); return stats(); }
        S.notice = '';
        S.error = '';
        try {
            if (want === 'terminal') enterTerminal(); else leaveTerminal();
        } catch (e) {
            S.error = 'terminal view could not be built: ' + ((e && e.message) || String(e));
            if (S.mode === 'terminal') {
                try { leaveTerminal(); } catch (e2) { S.error += ' / cleanup: ' + ((e2 && e2.message) || e2); }
            }
        }
        if (!opts.silent && !S.error) persistMode();
        paintBar();
        paintStatus();
        document.dispatchEvent(new CustomEvent('ofap:shell', { detail: stats() }));
        return stats();
    }

    /* ══ widgets on the current tab ═════════════════════════════════════════════════════════════ */

    function focusView(view) {
        if (S.mode !== 'terminal') return false;
        const name = String(view || '').trim().toLowerCase();
        if (!sectionFor(name)) { S.error = 'no such panel: ' + name; paintBar(); return false; }
        let host = '';
        S.layout.tabs.forEach(function (tab) {
            tab.widgets.forEach(function (widget) { if (widget.view === name) host = tab.id; });
        });
        if (!host) return openWidget(name);
        if (host !== S.activeTab) applyTab(host);
        setFocus(name);
        const frame = S.frames.get(name);
        if (frame && frame.scrollIntoView) {
            try { frame.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
            catch (e) { /* engines without the options object simply do not scroll */ }
        }
        if (!AUX && location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
        paintBar();
        return true;
    }

    function openWidget(view) {
        /* §73: an auxiliary window shows exactly one widget — its own. Anything that would add a
           second (a nav click, a hash route) is refused with the reason, not obeyed. */
        if (AUX) {
            S.notice = 'this window is fixed to ' + titleOf(AUX.view);
            paintBar();
            return false;
        }
        if (S.mode !== 'terminal' || !S.layout) return false;
        if (refuseLocked()) return false;
        const name = String(view || '').trim().toLowerCase();
        if (!sectionFor(name)) { S.error = 'no such panel: ' + name; paintBar(); return false; }
        if (S.frames.has(name)) return focusView(name);
        const tab = activeTab();
        const size = tab.widgets.length ? SIZES.m : SIZES.l;
        const slot = math.firstSlot(tab.widgets, size[0], size[1], GRID);
        if (slot) {
            tab.widgets.push({ view: name, x: slot.x, y: slot.y, w: size[0], h: size[1], link: '', settings: {} });
            S.notice = '';                            // a placement that fit says nothing
        } else {
            const views = tab.widgets.map(function (widget) { return widget.view; }).concat([name]);
            const rects = math.tile(views.length, GRID);
            const before = tab.widgets;
            tab.widgets = views.map(function (view2, i) {
                const old = before[i] || {};
                return { view: view2, x: rects[i].x, y: rects[i].y, w: rects[i].w, h: rects[i].h,
                         link: old.link || '', settings: old.settings || {} };
            });
            S.notice = 'the grid was full — tiled this tab for ' + tab.widgets.length + ' widgets';
        }
        renderFrames();
        applyTab(tab.id);
        saveSoon();
        return focusView(name);
    }

    function closeWidget(view) {
        if (S.mode !== 'terminal' || !S.layout) return false;
        if (refuseLocked()) return false;
        const name = String(view || '').trim().toLowerCase();
        let removed = false;
        S.layout.tabs.forEach(function (tab) {
            const before = tab.widgets.length;
            tab.widgets = tab.widgets.filter(function (widget) { return widget.view !== name; });
            if (tab.widgets.length !== before) removed = true;
        });
        if (!removed) return false;
        releaseFrame(name);
        if (S.focus === name) S.focus = '';
        renderTabs();
        paintBar();
        saveSoon();
        return true;
    }

    function arrange() {
        const tab = activeTab();
        if (S.mode !== 'terminal' || !tab || !tab.widgets.length) return false;
        const rects = math.tile(tab.widgets.length, GRID);
        tab.widgets.forEach(function (widget, i) {
            widget.x = rects[i].x; widget.y = rects[i].y; widget.w = rects[i].w; widget.h = rects[i].h;
        });
        renderFrames();
        applyTab(tab.id);
        S.notice = 'tiled ' + tab.widgets.length + ' widget' + (tab.widgets.length === 1 ? '' : 's') +
                   ' across the grid';
        paintBar();
        saveSoon();
        return true;
    }

    /* ══ persistence ═════════════════════════════════════════════════════════════════════════════ */

    function saveSoon() {
        S.dirtyAt = Date.now();
        if (S.saveTimer) clearTimeout(S.saveTimer);
        S.saveTimer = setTimeout(function () {
            S.saveTimer = 0;
            saveNow();
        }, 500);
    }

    /* Writes go through the arbiter, which holds them while a gesture is in flight — so a drag
       straight into closing the window used to lose the change (measured: a dragged rect did not
       survive a reload two seconds later). `urgent` is the way out: it posts immediately with
       keepalive, so the request outlives the page. */
    function saveNow(opts) {
        opts = opts || {};
        if (!S.layout) return Promise.resolve(stats());
        /* §73: an auxiliary window holds one widget and owns nothing — a write from it would
           replace the board the main window is showing. Nothing in it is saved. */
        if (AUX) return Promise.resolve(stats());
        if (S.savedAt >= S.dirtyAt && !opts.force) return Promise.resolve(stats());
        const layout = JSON.parse(JSON.stringify(S.layout));
        layout.saved = Date.now();
        /* Everything dirty up to now is what this request carries: a change made while it is in
           flight leaves dirtyAt ahead of savedAt, so the next save still sees work to do. */
        const stamp = S.dirtyAt;
        const body = { save: layout, activate: layout.id };
        const apply = function (res) {
            if (res && res.ok === false) {
                S.error = res.error || 'the store refused this layout';
            } else {
                S.items = (res && res.items) || S.items;
                S.savedAt = Math.max(S.savedAt, stamp);
                S.saves += 1;
                S.created = false;
            }
            paintBar();
            return stats();
        };
        const fail = function (e) {
            S.error = 'could not save the layout: ' + ((e && e.message) || e);
            paintBar();
            return stats();
        };
        if (opts.urgent && hasDom) {
            return fetch('/api/control/layouts', {
                method: 'POST', keepalive: true,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            }).then(function (res) { return res.json(); }).then(apply).catch(fail);
        }
        const post = function () { return route('POST', body).then(apply).catch(fail); };
        if (window.OFAPINTENT && typeof window.OFAPINTENT.queueWrite === 'function') {
            window.OFAPINTENT.queueWrite('shell.layout', function () { void post(); });
            return Promise.resolve(stats());
        }
        return post();
    }

    function persistMode() {
        return route('POST', { mode: S.mode }).then(function (res) {
            if (res && res.ok === false) S.error = res.error || 'the mode was not stored';
            paintBar();
            return res;
        }).catch(function (e) {
            S.error = 'could not store the mode: ' + ((e && e.message) || e);
            paintBar();
            return stats();
        });
    }

    /* ══ layout CRUD — the store's own actions, called by the Layout menu and by the probes ══════ */

    function screenKey() {
        if (!hasDom) return '';
        return math.screenKeyOf(window.screen, window.devicePixelRatio);
    }

    /* Everything the store accepted is what the shell adopts — a layout the sanitiser trimmed must
       never keep living in memory in the shape the user asked for. */
    function adoptLayout(layout) {
        S.layout = math.normaliseLayout(layout, knownViews(), GRID);
        S.layoutId = S.layout.id;
        S.activeTab = (S.layout.tabs[0] || {}).id || 'main';
        S.savedAt = Date.now();
        S.dirtyAt = 0;
        if (S.mode === 'terminal') {
            renderFrames();
            applyTab(S.activeTab);
            notifyRelayout('layout');
        }
        paintBar();
        paintStatus();
        return stats();
    }

    function refreshLayouts() {
        return route('GET').then(function (res) {
            S.items = (res && res.items) || {};
            return S.items;
        }).catch(function () { return S.items; });
    }

    function saveAs(name) {
        if (!S.layout) return Promise.resolve({ ok: false, error: 'no layout to save' });
        const clean = String(name || '').trim().slice(0, 40);
        if (!clean) return Promise.resolve({ ok: false, error: 'a layout needs a name' });
        const layout = JSON.parse(JSON.stringify(S.layout));
        layout.id = 'ly' + Math.random().toString(36).slice(2, 10);
        layout.name = clean;
        layout.screen_key = screenKey();
        layout.saved = Date.now();
        return route('POST', { save: layout, activate: layout.id }).then(function (res) {
            if (!res || res.ok === false) {
                S.error = (res && res.error) || 'the store refused the layout';
                paintBar();
                return { ok: false, error: S.error };
            }
            S.items = res.items || S.items;
            adoptLayout((res.items || {})[layout.id] || layout);
            S.notice = 'saved as “' + clean + '”';
            paintBar();
            return { ok: true, id: S.layoutId, name: clean };
        });
    }

    function renameLayout(name) {
        const clean = String(name || '').trim().slice(0, 40);
        if (!clean || !S.layoutId) return Promise.resolve({ ok: false, error: 'nothing to rename' });
        return route('POST', { rename: S.layoutId, to: clean }).then(function (res) {
            if (!res || res.ok === false) {
                S.error = (res && res.error) || 'the store refused the rename';
                paintBar();
                return { ok: false, error: S.error };
            }
            S.items = res.items || S.items;
            const stored = (res.items || {})[S.layoutId];
            if (stored) adoptLayout(stored);
            S.notice = 'renamed to “' + clean + '”';
            paintBar();
            return { ok: true, id: S.layoutId, name: clean };
        });
    }

    function restoreVersion(id, at) {
        /* T2: a layout's previous version comes back from the store's own ring — the write path
           is the same one every layout action uses, and the menu re-reads what the store kept. */
        return route('POST', { restore_version: { id: id, at: at } }).then(function (res) {
            if (!res || res.ok === false) throw new Error((res && res.error) || 'the store refused the restore');
            return refreshLayouts().then(function () { return activateLayout(id); });
        });
    }

    function duplicateLayout() {
        if (!S.layoutId) return Promise.resolve({ ok: false, error: 'nothing to duplicate' });
        const before = Object.keys(S.items);
        return route('POST', { duplicate: S.layoutId }).then(function (res) {
            if (!res || res.ok === false) {
                S.error = (res && res.error) || 'the store refused the copy';
                paintBar();
                return { ok: false, error: S.error };
            }
            S.items = res.items || S.items;
            const added = Object.keys(S.items).filter(function (id) { return before.indexOf(id) < 0; })[0];
            if (!added) {
                S.error = 'the store did not add a copy';
                paintBar();
                return { ok: false, error: S.error };
            }
            adoptLayout(S.items[added]);
            S.notice = 'duplicated as “' + S.items[added].name + '”';
            paintBar();
            return route('POST', { activate: added }).then(function () {
                return { ok: true, id: added, name: S.items[added].name };
            });
        });
    }

    /* Deleting asks for the layout's own name first: a one-click delete of the arrangement you are
       working in is not something a menu should offer. */
    function deleteLayout(confirmName) {
        if (!S.layout || !S.layoutId) return Promise.resolve({ ok: false, error: 'nothing to delete' });
        const current = S.layout.name;
        if (String(confirmName || '').trim() !== current) {
            return Promise.resolve({ ok: false, error: 'not deleted — the name did not match “' + current + '”' });
        }
        const id = S.layoutId;
        return route('POST', { delete: id }).then(function (res) {
            if (!res || res.ok === false) {
                S.error = (res && res.error) || 'the store refused the delete';
                paintBar();
                return { ok: false, error: S.error };
            }
            S.items = res.items || {};
            const next = Object.keys(S.items)[0];
            if (next) {
                adoptLayout(S.items[next]);
                return route('POST', { activate: next }).then(function () {
                    S.notice = 'deleted “' + current + '” — now on “' + S.items[next].name + '”';
                    paintBar();
                    return { ok: true, id: next, name: S.items[next].name };
                });
            }
            /* Deleting the last layout leaves the terminal with something to show rather than an
               empty board: a fresh starter arrangement. */
            const fresh = math.defaultLayout(knownViews(), GRID, 'ly' + Math.random().toString(36).slice(2, 10));
            fresh.name = 'Start';
            adoptLayout(fresh);
            S.notice = 'deleted the last layout — a starter board was created';
            saveSoon();
            paintBar();
            return { ok: true, id: S.layoutId, name: 'Start', created: true };
        });
    }

    /* Ids are opaque and the menu shows names, so both are accepted — but a name that two layouts
       share is not a name, it is a guess, and this refuses to guess. */
    function resolveLayoutKey(id) {
        if (S.items[id]) return id;
        const wanted = String(id == null ? '' : id).trim().toLowerCase();
        if (!wanted) return '';
        const hits = Object.keys(S.items).filter(function (key) {
            return String((S.items[key] || {}).name || '').trim().toLowerCase() === wanted;
        });
        return hits.length === 1 ? hits[0] : '';
    }

    function activateLayout(id) {
        const key = resolveLayoutKey(id);
        const layout = key ? S.items[key] : null;
        if (!layout) return Promise.resolve({ ok: false, error: 'no layout with id or name ' + id });
        adoptLayout(layout);
        S.notice = 'loaded “' + layout.name + '”';
        paintBar();
        return route('POST', { activate: key }).then(function () {
            if (window.OFAPMENUBAR_RECENT) { try { window.OFAPMENUBAR_RECENT('layout', layout.name, key); } catch (e) {} }
            return { ok: true, id: key, name: layout.name };
        });
    }

    function saveForScreen() {
        if (!S.layout) return Promise.resolve({ ok: false, error: 'no layout' });
        const key = screenKey();
        S.layout.screen_key = key;
        S.dirtyAt = Date.now();
        return saveNow({ force: true }).then(function () {
            S.notice = 'saved for ' + key;
            paintBar();
            return { ok: !S.error, screen_key: key, error: S.error };
        });
    }

    function resetBoard() {
        if (!S.layout) return { ok: false, error: 'no layout' };
        const keepId = S.layoutId;
        const fresh = math.defaultLayout(knownViews(), GRID, keepId);
        fresh.name = S.layout.name;
        fresh.id = keepId;
        adoptLayout(fresh);
        S.notice = 'board reset to the starter arrangement';
        paintBar();
        saveSoon();
        return { ok: true, widgets: math.countWidgets(S.layout) };
    }

    function postExport(filename, text) {
        const body = { name: filename, text: text };
        if (typeof api === 'function') return api('/api/control/export/save', { method: 'POST', body: body });
        return fetch('/api/control/export/save', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        }).then(function (res) { return res.json(); });
    }

    function exportLayout() {
        if (!S.layoutId) return Promise.resolve({ ok: false, error: 'no layout to export' });
        return route('POST', { export: S.layoutId }).then(function (res) {
            if (!res || res.ok === false) {
                S.error = (res && res.error) || 'the store refused the export';
                paintBar();
                return { ok: false, error: S.error };
            }
            return postExport(res.filename, res.text).then(function (saved) {
                if (!saved || saved.ok === false) {
                    S.error = 'could not write the export file';
                    paintBar();
                    return { ok: false, error: S.error };
                }
                S.notice = 'exported to ' + saved.path;
                paintBar();
                return { ok: true, path: saved.path, name: res.filename };
            });
        });
    }

    function importLayout(text) {
        let bundle = null;
        try { bundle = JSON.parse(String(text || '')); } catch (e) { bundle = null; }
        if (!bundle || typeof bundle !== 'object' || Array.isArray(bundle)) {
            return Promise.resolve({ ok: false, error: 'that is not a layout bundle (invalid JSON)' });
        }
        const before = Object.keys(S.items);
        return route('POST', { import: bundle }).then(function (res) {
            if (!res || res.ok === false) {
                S.error = (res && res.error) || 'the store refused the import';
                paintBar();
                return { ok: false, error: S.error };
            }
            S.items = res.items || S.items;
            const added = Object.keys(S.items).filter(function (id) { return before.indexOf(id) < 0; })[0];
            if (!added) {
                S.error = 'the store did not add the bundle';
                paintBar();
                return { ok: false, error: S.error };
            }
            return activateLayout(added);
        });
    }

    /* ══ the mode switch and the status fields ═══════════════════════════════════════════════════ */

    /* The chip follows the bus, not just shell events: a view switch opens or closes a channel without
       any shell event of its own, and the chip is the only place that is visible. One repaint per frame. */
    function watchBus() {
        if (typeof document === 'undefined' || !document.addEventListener) return;
        if (S.busWatcher) return;                 // idempotent: it is called from the paint, which runs often
        S.busWatcher = true;
        /* Painted straight away, not via requestAnimationFrame: measured in a headless page the frame
           callback never fired, so the queue flag stayed set and the chip went stale for good. A channel
           opens or closes a handful of times per view switch — a direct repaint costs nothing and cannot
           get stuck behind a scheduler that is entitled to never run. */
        document.addEventListener('ofap:bus', function () { paintBusChip(); });
    }

    /* C-10: the bus fires per message; only its own chip changes with it. The full status (frame
       titles, mode buttons, feed line — a dozen DOM writes) repaints on ofap:shell/relayout. */
    function paintBusChip() {
        if (!hasDom) return;
        const node = document.getElementById('statusBus');
        if (!node) return;
        const bus = window.OFAPBUS;
        node.textContent = bus && typeof bus.summary === 'function' ? bus.summary() : '—';
    }

    function paintStatus() {
        watchBus();   // the chip follows the bus, not only shell events
        if (!hasDom) return;
        const set = function (id, text) {
            const node = document.getElementById(id);
            if (node) node.textContent = text;
        };
        set('statusMode', S.mode === 'terminal' ? 'Terminal' : 'Classic');
        const lockChip = document.getElementById('statusLock');
        if (lockChip) lockChip.hidden = !S.locked;
        const tab = activeTab();
        set('statusTab', S.mode === 'terminal' && tab ? tab.name : '—');
        set('statusWidgets', String(S.mode === 'terminal' && S.layout ? math.countWidgets(S.layout) : 0));
        if (S.feed) set('statusFeed', S.feed.label + ' · ' + S.feed.quality);
        /* The bus's own numbers, and only if the delivery layer is loaded — the suite must run
           identically without it. */
        const bus = window.OFAPBUS;
        set('statusBus', bus && typeof bus.summary === 'function' ? bus.summary() : '—');

        /* T4/A9: keep the widget titles current (instrument changes do not repaint the grid). */
        if (S.frames && typeof S.frames.forEach === 'function') {
            S.frames.forEach(function (frame, view) {
                const el = frame && frame.querySelector ? frame.querySelector('.wf-title') : null;
                if (el) el.textContent = titleToken(view);
            });
        }
        document.querySelectorAll('#modeSwitch .seg-btn').forEach(function (btn) {
            const on = btn.getAttribute('data-mode') === S.mode;
            btn.classList.toggle('on', on);
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
    }

    /* What the feed quality line says follows the plan the user stored on the Platforms view, and the
       wording is the platform module's own — so the status bar cannot describe a feed the app is not
       actually promising. */
    function loadFeedState() {
        if (!hasDom) return Promise.resolve(false);
        const viaApi = typeof api === 'function';
        const platforms = viaApi ? api('/api/control/platforms', {})
            : fetch('/api/control/platforms', {}).then(function (r) { return r.json(); });
        const sources = viaApi ? api('/api/control/sources', {})
            : fetch('/api/control/sources', {}).then(function (r) { return r.json(); });
        return Promise.all([platforms.catch(function () { return null; }),
                            sources.catch(function () { return null; })]).then(function (rows) {
            const plat = rows[0] || {};
            const src = rows[1] || {};
            const sierra = plat.sierra || {};
            const integrated = !!(sierra.integrated && sierra.enabled);
            const plan = String(sierra.plan || 'free');
            const active = (src.sources || []).filter(function (s) { return s.id === src.active; })[0];
            S.feed = {
                label: integrated ? ('Sierra ' + plan) : ((active && active.name) || src.active || 'built-in'),
                quality: integrated ? (plan === 'free' ? 'delayed data' : 'real-time data') : 'free feed',
                integrated: integrated,
                plan: plan,
            };
            paintStatus();
            return S.feed;
        });
    }

    function stats() {
        const placed = Array.from(S.frames.keys());
        const known = hasDom ? knownViews() : [];
        return {
            version: VERSION,
            mode: S.mode,
            hooked: S.hooked,
            layoutId: S.layoutId,
            layoutName: S.layout ? S.layout.name : '',
            activeTab: S.activeTab,
            focus: S.focus,
            maximised: hasDom ? maximisedView() : '',
            gesture: S.gesture ? S.gesture.kind + ':' + S.gesture.view : '',
            tabs: S.layout ? S.layout.tabs.map(function (tab) {
                return { id: tab.id, name: tab.name, widgets: tab.widgets.length };
            }) : [],
            widgets: placed.length,
            placed: placed,
            unplaced: known.filter(function (view) { return placed.indexOf(view) < 0; }),
            switches: S.switches,
            saves: S.saves,
            savedAt: S.savedAt,
            created: S.created,
            notice: S.notice,
            error: S.error,
            screenKey: hasDom ? screenKey() : '',
            feed: S.feed || null,
            grid: { cols: GRID.cols, rows: GRID.rows },
        };
    }

    /* Every widget of the active tab with its rect and whether that rect is inside the grid — the
       phase-1 gate reads this instead of eyeballing the DOM. `inside` is computed by re-running the
       same clamp the store applies, so a rect that would be trimmed on save reports false here. */
    function bounds() {
        const tab = activeTab();
        const rows = (tab ? tab.widgets : []).map(function (widget) {
            const clamped = math.clampRect(widget, GRID);
            return {
                view: widget.view, x: widget.x, y: widget.y, w: widget.w, h: widget.h,
                inside: clamped.x === widget.x && clamped.y === widget.y
                        && clamped.w === widget.w && clamped.h === widget.h,
                max: !!(widget.settings && widget.settings.max),
            };
        });
        return { tab: S.activeTab, count: rows.length,
                 outside: rows.filter(function (row) { return !row.inside; }).length, widgets: rows };
    }

    /* ══ wiring ═════════════════════════════════════════════════════════════════════════════════ */

    /* In Classic mode this wrapper does nothing but delegate, so the single-view contract is
       unchanged; in Terminal mode a nav click opens or focuses that panel's widget instead of
       collapsing the grid to one view. */
    function installHook() {
        if (!hasDom || S.hooked || typeof window.showView !== 'function') return S.hooked;
        S.base = window.showView;
        window.showView = function (name) {
            if (S.mode === 'terminal') return focusView(name);
            return S.base.apply(window, arguments);
        };
        S.hooked = true;
        return true;
    }

    function boot() {
        installHook();
        paintStatus();
        void loadFeedState();
        if (AUX) {
            /* §73: an auxiliary window renders its one widget from a synthetic layout and asks the
               store nothing — so it can neither read nor disturb what the board is doing. The hash
               is cleared first: a `#view` in the URL is a routing request, and this window has no
               board to route (measured: `#overview` from the previous window added a second widget
               before this guard existed). */
            try { history.replaceState(null, '', (location.pathname || '/desktop') + (location.search || '')); }
            catch (e) { /* a document that refuses replaceState simply keeps its hash */ }
            switchTo('terminal', { silent: true });
            paintBar();
            return Promise.resolve(stats());
        }
        if (typeof api === 'function') {
            void api('/api/control/config').then(function (cfg) {
                const ui = (cfg && cfg.ui) || {};
                S.locked = Boolean(ui.layout_lock);
                paintStatus();
                paintBar();
            }).catch(function () { /* the lock defaults to off */ });
        }
        return route('GET').then(function (res) {
            S.items = (res && res.items) || {};
            S.layoutId = (res && res.active) || '';
            if (res && res.mode === 'terminal') switchTo('terminal', { silent: true });
            /* §72: this monitor's own layout, when one was saved for it — the board built for a
               second screen comes back on that screen. Terminal mode only (layouts live there),
               and it never fights a layout that is already active. */
            if (res && res.mode === 'terminal') {
                const wanted = math.pickScreenLayout(S.items, screenKey(), S.layoutId);
                if (wanted) {
                    void activateLayout(wanted);
                    S.notice = 'this screen’s layout: “' + ((S.items[wanted] || {}).name || wanted) + '”';
                    paintBar();
                }
            }
            return stats();
        }).catch(function (e) {
            S.error = 'layouts unavailable: ' + ((e && e.message) || e);
            return stats();
        });
    }

    if (hasDom) {
        installHook();
        /* T11/B17: the links module owns the palette logic; the shell owns where link state is
           written (the same division of labour as the membership itself), so a group's colour
           survives a reload without links.js ever touching the network. */
        document.addEventListener('ofap:link-colors', function () {
            const L = window.OFAPLINKS;
            if (!L || typeof api !== 'function') return;
            const full = {};
            L.GROUPS.forEach(function (g) { full[g] = L.colorOf(g); });
            void api('/api/control/config', { method: 'POST', body: { ui: { link_colors: full } } });
        });

        /* Terminal-mode keys: Escape reaches both jobs it has (leave the maximised widget, then
           drop the focus ring); F11 and Alt+1-9 are below. Ctrl+Alt+T (the way back) is in
           keys.js's map now, so it obeys the shared typing guard — it used to toggle mid-typing. */
        document.addEventListener('keydown', function (e) {
            if (S.mode !== 'terminal' || !S.layout) return;
            const target = e.target || {};
            const tag = String(target.tagName || '').toUpperCase();
            const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag) || target.isContentEditable;
            if (e.key === 'Escape') {
                const maxed = maximisedView();
                if (maxed) {
                    e.preventDefault();
                    toggleMax(maxed);
                } else if (S.focus) {
                    setFocus('');
                    paintBar();
                }
                return;
            }
            if (typing) return;
            if (e.key === 'F11') {
                const view = S.focus || firstPlaced();
                if (view) {
                    e.preventDefault();
                    toggleMax(view);
                }
                return;
            }
            if (e.altKey && !e.ctrlKey && !e.metaKey && /^[1-9]$/.test(String(e.key || ''))) {
                const tab = S.layout.tabs[parseInt(e.key, 10) - 1];
                if (tab) {
                    e.preventDefault();
                    applyTab(tab.id);
                }
            }
        });
        /* The rail keeps working even if a module re-wraps showView after us: a nav click in
           Terminal mode always means "show me that panel". */
        document.addEventListener('click', function (e) {
            if (S.mode !== 'terminal') return;
            const item = e.target && e.target.closest ? e.target.closest('.nav-item[data-view]') : null;
            if (item) focusView(item.getAttribute('data-view'));
        }, true);
        const link = document.querySelector('#railTerminal');
        if (link) link.onclick = function (ev) {
            if (ev && ev.preventDefault) ev.preventDefault();
            switchTo(S.mode === 'terminal' ? 'classic' : 'terminal');
        };
        document.querySelectorAll('#modeSwitch .seg-btn').forEach(function (btn) {
            btn.addEventListener('click', function () { switchTo(btn.getAttribute('data-mode')); });
        });
        /* Ctrl+Alt+T is registered into keys.js's map (this module owns the action, the map
           dispatches it and lists it). The Terminal keys below stay local — they are gated on
           the shell's own focus/maximise state — and the map lists them too. */
        if (window.OFAPKEYS) {
            OFAPKEYS.bind({ id: 'terminal-toggle', keys: ['ctrl+alt+t'], scope: 'Global',
                label: 'classic ⇄ terminal mode',
                run: function () { switchTo(S.mode === 'terminal' ? 'classic' : 'terminal'); } });
            OFAPKEYS.document([
                { keys: 'F11', label: 'maximise / restore the focused widget', scope: 'Terminal' },
                { keys: 'Esc', label: 'leave the maximised widget, then drop the panel focus', scope: 'Terminal' },
                { keys: 'Alt+1 … Alt+9', label: 'switch tab', scope: 'Terminal' },
            ]);
        }
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
        else boot();
        window.addEventListener('pagehide', function () { saveNow({ urgent: true }); });
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) saveNow({ urgent: true });
        });
    }

    window.OFAPSHELL = {
        version: VERSION,
        mode: function () { return S.mode; },
        state: stats,
        stats: stats,
        bounds: bounds,
        switchTo: switchTo,
        toggle: function () { return switchTo(S.mode === 'terminal' ? 'classic' : 'terminal'); },
        focusView: focusView,
        locked: function () { return S.locked; },
        setLocked: setLocked,
        setFocus: setFocus,
        openWidget: openWidget,
        closeWidget: closeWidget,
        activateTab: applyTab,
        addTab: addTab,
        closeTab: closeTab,
        reorderTabs: reorderTabs,
        renameTab: renameTab,
        maximise: toggleMax,
        openPanelSettings: openPanelSettings,
        arrange: arrange,
        saveNow: saveNow,
        saveAs: saveAs,
        renameLayout: renameLayout,
        duplicateLayout: duplicateLayout,
        restoreVersion: restoreVersion,
        deleteLayout: deleteLayout,
        activateLayout: activateLayout,
        resolveLayoutKey: resolveLayoutKey,
        saveForScreen: saveForScreen,
        resetBoard: resetBoard,
        exportLayout: exportLayout,
        importLayout: importLayout,
        layouts: function () { return S.items; },
        refreshLayouts: refreshLayouts,
        linkSpec: linkSpec,
        setLink: setLink,
        linkMembers: linkMembers,
        paintLinkChip: paintLinkChip,
        screenKey: screenKey,
        feedState: loadFeedState,
        paintStatus: paintStatus,
        layout: function () { return S.layout; },
        math: math,
    };
})();
