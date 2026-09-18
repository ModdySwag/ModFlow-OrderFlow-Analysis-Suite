/* templates.js — T8/B8: the template gallery — load a working board (or a tuned set of
 * settings), then make it yours.
 *
 * The study's fastest cure for surface overwhelm (ATAS's template gallery, NinjaTrader's starter
 * layouts): a newcomer should not have to *compose* thirty panels before they see anything. Every
 * entry here loads NON-DESTRUCTIVELY — a board arrives as a brand-new layout (an existing one is
 * never overwritten; boards are capped by the store, which says so when it is full), and a
 * settings bundle writes through the same registered /params gate the Settings search uses, so
 * every change is visible in Settings and reversible (View ▸ This view — settings, or Reset this
 * view to factory). Each entry links its help topic — the gallery is the Learn Center's door.
 *
 * The card lives in the Guide view (injected there; the Guide owns the onboarding surface).
 */
(function () {
    'use strict';

    /* Boards are stored layout entries: a 12×8 widget grid, ≤12 tabs, ≤24 widgets. Rects here keep
       the store's own rules (x+w ≤ 12, y+h ≤ 8), so nothing is clamped on the way in. */
    var TEMPLATES = [
        { id: 'tpl-scout', kind: 'board', name: 'Fast tape board', topic: 'view.heatmap',
          blurb: 'Heatmap, Time & Sales and Depth together — the quick read, one tab.',
          tabs: [{ name: 'Main', widgets: [
              { view: 'heatmap', x: 0, y: 0, w: 6, h: 5 },
              { view: 'tape', x: 6, y: 0, w: 6, h: 3 },
              { view: 'depth', x: 6, y: 3, w: 6, h: 2 },
              { view: 'replay', x: 0, y: 5, w: 8, h: 3 },
              { view: 'journal', x: 8, y: 5, w: 4, h: 3 },
          ] }] },
        { id: 'tpl-context', kind: 'board', name: 'Context board', topic: 'view.chart',
          blurb: 'Chart, CVD, Profile and Watchlist — the slower read for deciding where to look.',
          tabs: [{ name: 'Main', widgets: [
              { view: 'chart', x: 0, y: 0, w: 8, h: 5 },
              { view: 'cvd', x: 8, y: 0, w: 4, h: 5 },
              { view: 'profile', x: 0, y: 5, w: 6, h: 3 },
              { view: 'watchlist', x: 6, y: 5, w: 6, h: 3 },
          ] }] },
        { id: 'tpl-desk', kind: 'board', name: 'Replay study desk', topic: 'view.replay',
          blurb: 'Replay beside the Heatmap and the Tape, with the Journal open — practise with the book in view.',
          tabs: [{ name: 'Main', widgets: [
              { view: 'replay', x: 0, y: 0, w: 8, h: 4 },
              { view: 'heatmap', x: 8, y: 0, w: 4, h: 4 },
              { view: 'tape', x: 0, y: 4, w: 6, h: 4 },
              { view: 'journal', x: 6, y: 4, w: 6, h: 4 },
          ] }] },
        { id: 'tpl-laptop', kind: 'settings', name: 'Laptop minimal', topic: 'view.heatmap',
          blurb: 'The heatmap without its chrome, its colour saturated later — data per pixel on a small screen.',
          values: { 'ui.heatmap_minimal': true, 'atlas.heatmap.upper_cutoff_pct': 8 } },
        { id: 'tpl-cvd', kind: 'settings', name: 'Colour-blind palettes', topic: 'work.appearance',
          blurb: 'Engine and Chart bars in the measured deuteranope-safe pair — the app\u2019s own ΔE-checked palettes.',
          values: { 'expression.engine.palette': 'deutan', 'expression.chart.palette': 'deutan' } },
        { id: 'tpl-still', kind: 'settings', name: 'Still scales', topic: 'view.ofx',
          blurb: 'The price scale stops breathing (auto-fit slack) and the depth chips call "stale" later.',
          values: { 'atlas.ofx.fit_tolerance': 0.5, 'atlas.freshness.depth_s': 30 } },
    ];

    function $id(id) { return document.getElementById(id); }

    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function note(text) {
        if (window.toast && typeof document !== 'undefined') toast(document.body, text, 'info');
    }

    function adoptConfig(cfg) {
        try { S.config = cfg; } catch (e) { /* the next read retries */ }
        if (window.OFAPFRESH && OFAPFRESH.setWindows) OFAPFRESH.setWindows(((cfg || {}).atlas || {}).freshness);
        document.dispatchEvent(new CustomEvent('ofap:relayout'));
    }

    function boardEntry(tpl, suffix) {
        return {
            id: 'tpl-' + tpl.id.replace(/^tpl-/, '') + '-' + suffix,
            name: tpl.name,
            mode: 'terminal',
            theme: 'dark',
            tabs: tpl.tabs.map(function (tab, i) {
                return { id: 'main' + (i ? i + 1 : ''), name: tab.name || 'Main', widgets: tab.widgets };
            }),
        };
    }

    function loadBoard(tpl) {
        var suffix = Math.random().toString(36).slice(2, 6);
        var entry = boardEntry(tpl, suffix);
        return api('/api/control/layouts', { method: 'POST', body: { save: entry } })
            .then(function (r) {
                if (!r || r.ok === false) {
                    note('the store refused the board: ' + ((r && r.error) || 'unknown'));
                    return null;
                }
                var shell = window.OFAPSHELL;
                if (!shell || typeof shell.activateLayout !== 'function') {
                    return api('/api/control/layouts', { method: 'POST', body: { activate: entry.id } })
                        .then(function () { note('board \u201c' + tpl.name + '\u201d saved \u2014 find it in Layout \u25b8 Saved layouts'); });
                }
                /* The shell resolves ids against its own cache, so refresh BEFORE activating — and
                   check the result: activateLayout answers {ok:false} when the id is unknown. */
                return shell.refreshLayouts().then(function () {
                    return shell.activateLayout(entry.id);
                }).then(function (res) {
                    if (res && res.ok === false) {
                        note('board \u201c' + tpl.name + '\u201d saved \u2014 find it in Layout \u25b8 Saved layouts (' + (res.error || 'the shell could not switch') + ')');
                        return null;
                    }
                    /* adoptLayout only renders when the shell is already in Terminal mode, so take
                       the user there when it is not — one click should show the board. */
                    /* The board's own first view goes on screen before the switch: entering
                       Terminal focuses the CURRENT view, and a view the board does not contain
                       would be appended as a widget (a full grid re-tiles every board rect). */
                    var firstView = ((entry.tabs[0] || {}).widgets[0] || {}).view;
                    if (firstView && typeof window.showView === 'function') showView(firstView);
                    if (typeof shell.mode === 'function' && shell.mode() !== 'terminal' && typeof shell.switchTo === 'function') {
                        shell.switchTo('terminal');
                    }
                    note('board \u201c' + tpl.name + '\u201d added as a new layout \u2014 nothing you had was replaced');
                    return null;
                });
            })
            .catch(function (e) { note('the store refused the board: ' + e); });
    }

    function loadSettings(tpl) {
        var paths = Object.keys(tpl.values || {});
        var failed = [];
        var chain = Promise.resolve();
        paths.forEach(function (path) {
            chain = chain.then(function () {
                return api('/api/control/params', { method: 'POST', body: { path: path, value: tpl.values[path] } })
                    .then(function (r) { if (!r || !r.ok) failed.push(path + ' (' + ((r && r.error) || 'refused') + ')'); })
                    .catch(function (e) { failed.push(path + ' (' + e + ')'); });
            });
        });
        return chain.then(function () { return api('/api/control/config'); }).then(function (cfg) {
            adoptConfig(cfg);
            note(failed.length
                ? ('some values were refused \u2014 ' + failed.join('; '))
                : ('applied \u201c' + tpl.name + '\u201d (' + paths.length + ' settings) \u2014 undo from View \u25b8 This view \u2014 settings, or Settings \u25b8 Find a setting'));
        }).catch(function (e) { note('the store refused: ' + e); });
    }

    function loadTemplate(tpl) {
        return tpl.kind === 'board' ? loadBoard(tpl) : loadSettings(tpl);
    }

    function rowHtml(tpl) {
        return '<div class="tpl-row" data-tpl="' + esc(tpl.id) + '">'
            + '<span class="tpl-kind tag ' + (tpl.kind === 'board' ? 'ok' : 'warn') + '">' + esc(tpl.kind) + '</span>'
            + '<span class="tpl-name"><b>' + esc(tpl.name) + '</b><span class="dim"> \u00b7 ' + esc(tpl.blurb) + '</span></span>'
            + '<a class="help-link" href="#" data-helptopic="' + esc(tpl.topic) + '">what is this?</a>'
            + '<button class="btn small primary" data-tpl-load="' + esc(tpl.id) + '">Load</button>'
            + '</div>';
    }

    function cardHtml() {
        return '<div class="card" data-tpl-card="1"><div class="card-head">'
            + '<span class="card-title">Start from a template</span><div class="spacer"></div>'
            + '<span class="dim">load a working board, then make it yours</span></div>'
            + '<div class="card-body">'
            + '<div class="hint">Boards arrive as <b>new layouts</b> \u2014 nothing you already made is replaced. '
            + 'Settings bundles write through the registered settings gate and stay visible and reversible: '
            + 'View \u25b8 This view \u2014 settings, or Settings \u25b8 Find a setting. Every entry links its help topic.'
            + ' Browse the corpus: <a class="help-link" href="#" data-helptopic="start.help">the Help Centre</a>.</div>'
            + '<div class="tpl-grid" id="tplGrid">' + TEMPLATES.map(rowHtml).join('') + '</div>'
            + '</div></div>';
    }

    function wireCard(card) {
        card.addEventListener('click', function (ev) {
            var btn = ev.target.closest ? ev.target.closest('[data-tpl-load]') : null;
            if (!btn) return;
            var tpl = TEMPLATES.filter(function (t) { return t.id === btn.getAttribute('data-tpl-load'); })[0];
            if (!tpl) return;
            btn.disabled = true;
            Promise.resolve(loadTemplate(tpl)).then(function () { btn.disabled = false; });
        });
        return true;
    }

    /* The Guide view is built by guide.js at boot; adopt it whenever it arrives (bounded attempts,
       plus the relayout event the shell fires when it reparents sections). */
    function inject() {
        if (document.querySelector('[data-tpl-card]')) return true;
        var section = document.querySelector('.view[data-view="guide"]');
        if (!section) return false;
        var holder = document.createElement('div');
        holder.innerHTML = cardHtml();
        var card = holder.firstChild;
        var anchor = section.querySelector('.grid, .card, .guide-table');
        if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(card, anchor);
        else section.appendChild(card);
        wireCard(card);
        return true;
    }

    function tryInject() { if (!inject() && typeof setTimeout === 'function') setTimeout(inject, 900); }

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tryInject);
        else tryInject();
        document.addEventListener('ofap:relayout', tryInject);
    }

    window.OFAPTEMPLATES = { TEMPLATES: TEMPLATES, load: loadTemplate, inject: inject, card: cardHtml };
})();
