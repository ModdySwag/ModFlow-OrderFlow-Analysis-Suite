/* settings-pro.js — T7/B1: one searchable surface for every registered setting.
 *
 * The study's strongest transferable asset (Sierra's modeless settings): a field you can find by
 * typing; values you can stage before they are written; per-field accept/cancel; Apply-all /
 * Revert-all; and the factory default always one toggle away — so "what did I change, and what
 * was it before?" is answered by the surface itself.
 *
 * The data is the same registry every other surface reads (GET /api/control/params); writes go
 * through the same single-path gate (POST /api/control/params {path, value}), so nothing here can
 * write a variable the store would refuse. Modeless by construction: the panel lives in the
 * Settings view, the editors are inline, and nothing is written until you say so.
 */
(function () {
    'use strict';

    var state = {
        groups: {},          // group -> rows from the last /params answer
        staged: {},          // path -> staged value (not yet written)
        applied: {},         // path -> what the config holds (from the same answer)
        showOriginal: false,
    };

    function $id(id) { return document.getElementById(id); }

    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function tokens() {
        var input = $id('setSearch');
        return String((input && input.value) || '').toLowerCase().split(/\s+/).filter(Boolean);
    }

    /* Tokenised search, Sierra's shape: every word must match, and `group:` / `view:` / `path:`
       narrow by the registry's own axes. Plain words search label + meaning + path + group + unit,
       so "iceberg" finds the geometry knob by its meaning, not only by its name. */
    function matches(p, toks) {
        for (var i = 0; i < toks.length; i += 1) {
            var tok = toks[i];
            var ok;
            if (tok.indexOf('group:') === 0) ok = String(p.group || '').toLowerCase().indexOf(tok.slice(6)) >= 0;
            else if (tok.indexOf('view:') === 0) ok = String(p.view || '').toLowerCase() === tok.slice(5);
            else if (tok.indexOf('path:') === 0) ok = String(p.path || '').toLowerCase().indexOf(tok.slice(5)) >= 0;
            else {
                var hay = (String(p.label || '') + ' ' + String(p.meaning || '') + ' '
                    + String(p.path || '') + ' ' + String(p.group || '') + ' ' + String(p.unit || '')).toLowerCase();
                ok = hay.indexOf(tok) >= 0;
            }
            if (!ok) return false;
        }
        return true;
    }

    function fmtDefault(v) {
        if (v === true) return 'on';
        if (v === false) return 'off';
        if (v === null || v === undefined) return '—';
        return String(v);
    }

    function changed(p) {
        var now = state.staged[p.path] !== undefined ? state.staged[p.path] : state.applied[p.path];
        return String(now) !== String(p.default);
    }

    function control(p, value) {
        var v = value === undefined || value === null ? '' : value;
        if (p.kind === 'bool') {
            return '<input type="checkbox" data-set-path="' + esc(p.path) + '"' + (value ? ' checked' : '') + '>';
        }
        if (p.kind === 'enum') {
            var opts = (p.choices || []).map(function (c) {
                return '<option value="' + esc(c) + '"' + (c === value ? ' selected' : '') + '>' + esc(c) + '</option>';
            }).join('');
            return '<select data-set-path="' + esc(p.path) + '">' + opts + '</select>';
        }
        if (p.kind === 'list') {
            return '<span class="dim">list — edited in its own surface</span>';
        }
        var step = p.step === undefined || p.step === null ? 'any' : p.step;
        return '<input type="number" data-set-path="' + esc(p.path) + '" value="' + esc(v) + '" step="' + step + '"'
            + (p.min !== undefined && p.min !== null ? ' min="' + p.min + '"' : '')
            + (p.max !== undefined && p.max !== null ? ' max="' + p.max + '"' : '') + '>';
    }

    function rowHtml(p) {
        var staged = state.staged[p.path] !== undefined;
        var now = staged ? state.staged[p.path] : state.applied[p.path];
        var buttons = staged
            ? '<button class="btn small" data-set-accept="' + esc(p.path) + '" title="Write this field now">&#10003;</button>'
                + '<button class="btn small" data-set-cancel="' + esc(p.path) + '" title="Drop this field\'s edit">&#8634;</button>'
            : '<span class="set-ctl-pad"></span>';
        return '<div class="set-row' + (staged ? ' staged' : '') + (changed(p) ? ' is-changed' : '')
            + '" data-set-row="' + esc(p.path) + '">'
            + '<span class="set-name" title="' + esc(p.meaning || '') + '">' + esc(p.label || p.path)
            + (p.unit ? ' <span class="dim">(' + esc(p.unit) + ')</span>' : '') + '</span>'
            + '<span class="set-ctl">' + control(p, now) + '</span>'
            + '<span class="set-default" title="The factory default, before any change">default ' + esc(fmtDefault(p.default)) + '</span>'
            + buttons
            + '<span class="set-path" title="' + esc(p.path) + ' — drives the ' + esc(p.view || 'app') + ' panel">'
            + esc(p.path) + ' · ' + esc(p.view || 'app') + '</span>'
            + '</div>';
    }

    function render() {
        var host = $id('setResults');
        if (!host || !state.groups) return 0;
        var toks = tokens();
        var html = [];
        var shown = 0;
        var total = 0;
        Object.keys(state.groups).forEach(function (group) {
            var rows = state.groups[group].filter(function (p) { return matches(p, toks); });
            total += state.groups[group].length;
            if (!rows.length) return;
            shown += rows.length;
            html.push('<div class="set-group-title">' + esc(group) + '</div>');
            rows.forEach(function (p) { html.push(rowHtml(p)); });
        });
        host.innerHTML = html.join('')
            || '<div class="hint">nothing matches — try another word, or clear the box to browse every setting</div>';
        host.classList.toggle('show-original', state.showOriginal);
        var staged = Object.keys(state.staged).length;
        var info = $id('setSearchInfo');
        if (info) info.textContent = shown + ' of ' + total + ' settings' + (staged ? ' · ' + staged + ' staged' : '');
        var apply = $id('setApplyAll');
        if (apply) apply.disabled = staged === 0;
        var revert = $id('setRevertAll');
        if (revert) revert.disabled = staged === 0;
        return shown;
    }

    function reload() {
        return api('/api/control/params').then(function (d) {
            state.groups = (d && d.groups) || {};
            state.applied = {};
            Object.keys(state.groups).forEach(function (group) {
                state.groups[group].forEach(function (p) { state.applied[p.path] = p.value; });
            });
            /* a staged value the config has since caught up with is not a change any more */
            Object.keys(state.staged).forEach(function (path) {
                if (String(state.staged[path]) === String(state.applied[path])) delete state.staged[path];
            });
            render();
            return d;
        });
    }

    function adoptPageConfig() {
        return api('/api/control/config').then(function (cfg) {
            try { S.config = cfg; } catch (e) { /* the next read retries */ }
            if (window.OFAPFRESH && OFAPFRESH.setWindows) OFAPFRESH.setWindows((cfg.atlas || {}).freshness);
            return cfg;
        }).catch(function () { return null; });
    }

    function applyAll() {
        var paths = Object.keys(state.staged);
        if (!paths.length) return Promise.resolve();
        var info = $id('setSearchInfo');
        var failed = [];
        var chain = Promise.resolve();
        paths.forEach(function (path) {
            chain = chain.then(function () {
                return api('/api/control/params', { method: 'POST', body: { path: path, value: state.staged[path] } })
                    .then(function (r) {
                        if (r && r.ok) delete state.staged[path];
                        else failed.push(path + ' (' + ((r && r.error) || 'refused') + ')');
                    })
                    .catch(function (e) { failed.push(path + ' (' + e + ')'); });
            });
        });
        return chain.then(adoptPageConfig).then(reload).then(function () {
            if (info) {
                info.textContent = failed.length
                    ? ('some writes were refused — ' + failed.join('; '))
                    : 'staged changes written';
            }
        });
    }

    function writeOne(path) {
        var value = state.staged[path];
        return api('/api/control/params', { method: 'POST', body: { path: path, value: value } })
            .then(function (r) {
                var info = $id('setSearchInfo');
                if (r && r.ok) { delete state.staged[path]; return adoptPageConfig().then(reload); }
                if (info) info.textContent = 'refused: ' + ((r && r.error) || 'the store said no');
                return null;
            })
            .catch(function (e) { var info = $id('setSearchInfo'); if (info) info.textContent = 'refused: ' + e; });
    }

    function stage(path, value) {
        if (String(value) === String(state.applied[path])) delete state.staged[path];
        else state.staged[path] = value;
        render();
    }

    function wire() {
        var host = $id('setResults');
        if (!host) return false;
        var search = $id('setSearch');
        if (search) {
            search.addEventListener('input', render);
            search.addEventListener('focus', function () { void reload(); });
        }
        var original = $id('setShowOriginal');
        if (original) original.addEventListener('click', function () {
            state.showOriginal = !state.showOriginal;
            original.setAttribute('aria-pressed', state.showOriginal ? 'true' : 'false');
            render();
        });
        var apply = $id('setApplyAll');
        if (apply) apply.addEventListener('click', function () { void applyAll(); });
        var revert = $id('setRevertAll');
        if (revert) revert.addEventListener('click', function () { state.staged = {}; render(); });
        host.addEventListener('change', function (ev) {
            var el = ev.target.closest ? ev.target.closest('[data-set-path]') : null;
            if (!el) return;
            var path = el.getAttribute('data-set-path');
            var value = el.type === 'checkbox' ? !!el.checked : el.value;
            stage(path, value);
        });
        host.addEventListener('click', function (ev) {
            var accept = ev.target.closest ? ev.target.closest('[data-set-accept]') : null;
            if (accept) { void writeOne(accept.getAttribute('data-set-accept')); return; }
            var cancel = ev.target.closest ? ev.target.closest('[data-set-cancel]') : null;
            if (cancel) { delete state.staged[cancel.getAttribute('data-set-cancel')]; render(); }
        });
        return true;
    }

    function boot() {
        if (!wire()) {
            /* the markup can arrive after this script (terminal mode reparents sections) */
            if (typeof document !== 'undefined' && document.addEventListener) {
                document.addEventListener('DOMContentLoaded', wire);
            }
            return;
        }
        void reload();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
    document.addEventListener('ofap:relayout', function () { if ($id('setResults')) render(); });

    window.OFAPSETTINGS = {
        state: state, render: render, reload: reload, applyAll: applyAll, matches: matches,
        tokens: tokens, wire: wire,
    };
})();
