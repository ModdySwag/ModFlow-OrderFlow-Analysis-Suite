/* tips.js — "Try next": novelty-gated pointers to what this desk does that this install has never
 * used (v2 report §6.2-2, shipped §125).
 *
 * A tip is gated on the STORE, never on clicks: it retires when the feature genuinely exists in
 * your config or data — a saved layout, a kept workspace, an alert rule, a journal row. Nothing
 * here tracks you, nothing nags: the card shrinks as the desk gets used and removes itself when
 * it empties. Doors are object properties, not listeners; the module owns no views.
 */
'use strict';

(function () {
    var MAX_SHOWN = 3;

    var TIPS = [
        {
            id: 'layouts',
            title: 'Save this screen as a layout',
            body: 'Arrange the panels once and keep them — layouts restore the whole screen, and the Layout menu switches between them.',
            door: { label: 'Show me', help: 'work.layouts' },
            done: function (ctx) { return ctx.layouts > 0; },
        },
        {
            id: 'workspaces',
            title: 'Keep a workspace',
            body: 'The ☰ menu saves the whole desk — symbols, engine state and panels together — and brings it back in one click.',
            door: { label: 'The ☰ menu', menu: true },
            done: function (ctx) { return ctx.workspaces > 0; },
        },
        {
            id: 'alerts',
            title: 'Draw an alert rule',
            body: 'Walls, sweeps and level touches can reach you when you are not looking — the Alerts view owns the rules and the log.',
            door: { label: 'Alerts view', view: 'alerts' },
            done: function (ctx) { return ctx.alertRules > 0; },
        },
        {
            id: 'journal',
            title: 'Write the day down',
            body: 'The Journal keeps dated notes and a statement per day — your own record beside the tape, kept on disk.',
            door: { label: 'Journal view', view: 'journal' },
            done: function (ctx) { return ctx.journal > 0; },
        },
    ];

    function pick(tips, ctx, max) {
        var out = [];
        for (var i = 0; i < tips.length && out.length < max; i += 1) {
            var t = tips[i];
            var used = false;
            try { used = !!t.done(ctx); } catch (e) { used = true; }   /* a check that cannot run must not nag */
            if (!used) out.push(t);
        }
        return out;
    }

    function countOf(v) {
        if (Array.isArray(v)) return v.length;
        if (v && typeof v === 'object') return Object.keys(v).length;
        return 0;
    }

    async function loadCtx() {
        var ctx = { layouts: 0, workspaces: 0, alertRules: 0, journal: 0 };
        try {
            var lr = await api('/api/control/layouts');
            ctx.layouts = countOf(lr && (lr.layouts || lr.saved));
        } catch (e) { /* an absent store reads as "not used yet" */ }
        try {
            var wr = await api('/api/control/workspaces');
            ctx.workspaces = countOf(wr && wr.workspaces);
        } catch (e) { /* ditto */ }
        try {
            var ar = await api('/api/atlas/alert-rules');
            ctx.alertRules = countOf(ar && (ar.rules || ar));
        } catch (e) { /* ditto */ }
        try {
            var jr = await api('/api/control/journal');
            ctx.journal = jr && typeof jr.count === 'number' ? jr.count : countOf(jr && jr.rows);
        } catch (e) { /* ditto */ }
        return ctx;
    }

    function runDoor(door) {
        if (door.view && typeof window.showView === 'function') { window.showView(door.view); return; }
        if (door.help && window.OFAPHELP && typeof OFAPHELP.open === 'function') { OFAPHELP.open(door.help); return; }
        if (door.menu && window.OFAPMenu && typeof OFAPMenu.open === 'function') { OFAPMenu.open(); }
    }

    async function paint() {
        var body = document.getElementById('guideBody');
        if (!body) return false;
        var ctx = await loadCtx();
        var shown = pick(TIPS, ctx, MAX_SHOWN);
        var old = document.getElementById('tipsCard');
        if (old) old.remove();
        if (!shown.length) return true;                            /* everything tried — the card retires */
        var card = document.createElement('div');
        card.className = 'card';
        card.id = 'tipsCard';
        var items = shown.map(function (t, i) {
            return '<div style="margin-top:6px"><b>' + esc(t.title) + '</b>'
                + ' <button class="btn small" data-tip-door="' + i + '">' + esc(t.door.label) + '</button>'
                + '<div class="dim">' + esc(t.body) + '</div></div>';
        }).join('');
        card.innerHTML = '<div class="card-head"><span class="card-title">Try next</span><div class="spacer"></div>'
            + '<span class="dim">' + shown.length + ' of ' + TIPS.length + ' un-tried</span></div>'
            + '<div class="card-body"><div class="dim">Things this desk does that this install has not used yet — each one retires by itself once it happens.</div>'
            + items + '</div>';
        Array.prototype.forEach.call(card.querySelectorAll('[data-tip-door]'), function (btn) {
            var t = shown[Number(btn.getAttribute('data-tip-door'))];
            btn.onclick = function () { runDoor(t.door); };
        });
        body.insertBefore(card, body.firstChild);
        return true;
    }

    if (typeof window !== 'undefined') {
        window.OFAPTIPS = { TIPS: TIPS, pick: pick, paint: paint, countOf: countOf };
    }

    function boot() {
        if (document.getElementById('guideBody')) { void paint(); return; }
        if (typeof MutationObserver === 'function') {
            var obs = new MutationObserver(function () {
                if (document.getElementById('guideBody')) { obs.disconnect(); void paint(); }
            });
            obs.observe(document.body, { childList: true, subtree: true });
        }
    }
    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
        else boot();
    }
})();
