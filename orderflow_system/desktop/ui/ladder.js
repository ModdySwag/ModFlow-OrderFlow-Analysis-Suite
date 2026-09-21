/* Ladder — the Trade-DOM surface for the paper account (§118), with order templates (§W1).
 *
 * The pure half is small on purpose: `rows()` lays the price grid out of the account state the
 * Replay view already polls, `decide()` turns one click into one order decision — or into a
 * refusal, sentence included — `legs()`/`planOf()` read the ATM plan the account is carrying so the
 * grid can draw its legs, and `act()` says what a click meant. `paint()` draws the plan bar and the
 * grid and hands clicks to paper.js, which owns the session, the lock and the armed gate; nothing
 * here talks to the API directly, so the account keeps exactly one gatekeeper.
 *
 * The click grammar (the card's subtitle repeats it in words):
 *   left-click below the last print   → buy limit (rests; the tape decides when it fills)
 *   left-click above it               → buy stop
 *   right-click above it              → sell limit
 *   right-click below it              → sell stop
 *   the last-price row                → market, in the clicked side's direction
 *   shift + either button             → market, that side
 *   click a working order's chip      → cancel it
 * Placing anything needs the order keys armed and the account unlocked — a dense price grid is
 * exactly where a stray click finds a resting order, so the ladder obeys the same switch keys do.
 *
 * The plan bar is the one new surface, and it is not a price grid: a template button sets the plan
 * the next order that OPENS a position carries (sticky until it is changed or "no plan" clears it;
 * the account refuses it on an order that would add to one already open), and cancel-all takes
 * every working order off the book, the plan's resting legs included. The bar's own background is
 * inert — a click on it places nothing and cancels nothing.
 */
'use strict';

(function () {
    var LEVELS = 21;

    /* The templates the build ships, mirroring desktop/atm.py's DEFAULTS. The app's own block
       (S.config.atm) wins when it is there, so a template edited in the config file reaches these
       buttons without a second list to keep in step. */
    var BUILT_IN = [
        {id: 'scalp', name: 'Scalp', size: 1, stop_ticks: 8, target_ticks: 12, breakeven_ticks: 0,
         trail_ticks: 0, trail_step_ticks: 1, time_stop_min: 0, partial_ticks: 0, partial_pct: 50},
        {id: 'intraday', name: 'Intraday', size: 2, stop_ticks: 8, target_ticks: 20, breakeven_ticks: 6,
         trail_ticks: 0, trail_step_ticks: 1, time_stop_min: 0, partial_ticks: 8, partial_pct: 50},
        {id: 'runner', name: 'Runner', size: 2, stop_ticks: 8, target_ticks: 32, breakeven_ticks: 8,
         trail_ticks: 10, trail_step_ticks: 2, time_stop_min: 30, partial_ticks: 8, partial_pct: 50}
    ];

    var override = null;      // setTemplates()'s list, when a caller wants to drive the buttons itself
    var chosenId = null;      // null until something decides: the config block, then a click
    var CHIP_ON = 'border-color:rgba(255,214,102,.75);color:rgb(255,214,102)';
    var BAR = 'display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding:6px 12px;' +
        'border-bottom:1px solid rgba(255,255,255,.08)';
    var LINE = 'padding:0 12px 8px;font:500 10.5px ui-monospace,monospace';

    function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }

    function whole(v, lo, hi) {
        var n = Math.round(num(v));
        return Math.max(lo, Math.min(hi, isFinite(n) ? n : lo));
    }

    function roundTo(value, tick) {
        var t = num(tick) || 0.01;
        return Number((Math.round(num(value) / t) * t).toPrecision(12));
    }

    function samePrice(a, b, tick) {
        var t = num(tick) || 0.01;
        return Math.abs(num(a) - num(b)) <= t / 2 + 1e-9;
    }

    function decimals(tick) {
        var t = num(tick) || 0.01;
        var d = 0;
        while (d < 8 && Math.abs(t - Math.round(t)) > 1e-9) { t *= 10; d += 1; }
        return d;
    }

    function fmtPrice(price, tick) {
        return Number(num(price).toFixed(decimals(tick))).toString();
    }

    /* A price as a label, or an em dash when there is no price to show. */
    function priceOr(value, tick) {
        return (value === null || value === undefined || value === '' || !isFinite(Number(value)))
            ? '—' : fmtPrice(value, tick);
    }

    function esc(text) {
        return String(text == null ? '' : text)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function ident(v) {
        return String(v == null ? '' : v).trim().toLowerCase()
            .replace(/[^a-z0-9_-]/g, '').slice(0, 24);
    }

    /* ── templates ─────────────────────────────────────────────────────────── */

    /* The same coercion atm.clean_template does, so a hand-edited config cannot put a string where
       a tick count goes — or a partial with no level to take it at. */
    function cleanTemplate(raw) {
        var s = (raw && typeof raw === 'object') ? raw : {};
        var out = {
            id: ident(s.id), name: String(s.name == null ? '' : s.name).slice(0, 24),
            size: Math.max(0.001, Math.min(10000, num(s.size) || 1)),
            stop_ticks: whole(s.stop_ticks, 0, 100000), target_ticks: whole(s.target_ticks, 0, 100000),
            breakeven_ticks: whole(s.breakeven_ticks, 0, 100000),
            trail_ticks: whole(s.trail_ticks, 0, 100000),
            trail_step_ticks: Math.max(1, whole(s.trail_step_ticks, 0, 100000)),
            time_stop_min: whole(s.time_stop_min, 0, 24 * 60),
            partial_ticks: whole(s.partial_ticks, 0, 100000),
            partial_pct: whole(s.partial_pct, 0, 99)
        };
        if (!out.name) out.name = out.id;
        if (!out.partial_ticks || !out.partial_pct) { out.partial_ticks = 0; out.partial_pct = 0; }
        return out;
    }

    function setTemplates(list) {
        override = Array.isArray(list)
            ? list.map(cleanTemplate).filter(function (t) { return !!t.id; })
            : null;
        return templates();
    }

    /* The template list in force: an explicit setTemplates list, then the app's config block, then
       the shipped three. Recomputed on every call so a config change needs no reload. */
    function templates() {
        if (override) return override;
        try {
            var block = (typeof S !== 'undefined' && S && S.config && S.config.atm) || null;
            var list = (block && Array.isArray(block.templates)) ? block.templates : null;
            if (list && list.length) {
                var cleaned = list.map(cleanTemplate).filter(function (t) { return !!t.id; });
                if (cleaned.length) return cleaned;
            }
        } catch (err) { /* an unreadable config means the shipped templates */ }
        return BUILT_IN.map(cleanTemplate);
    }

    function template(id) {
        var want = ident(id);
        var list = templates();
        for (var i = 0; i < list.length; i += 1) { if (list[i].id === want) return list[i]; }
        return null;
    }

    function activeIdNow() {
        if (chosenId !== null) return chosenId;
        var fromConfig = '';
        try {
            var block = (typeof S !== 'undefined' && S && S.config && S.config.atm) || null;
            if (block) fromConfig = ident(block.active);
        } catch (err) { fromConfig = ''; }
        return fromConfig;
    }

    /* active() → the template the next click carries, or null when the ladder is only a grid. */
    function active() {
        return template(activeIdNow());
    }

    /* select(id) → the template now active. An id this build has no template for changes nothing;
       '' and the literal 'none' both mean "no plan" — the button paper.js paints sends the latter. */
    function select(id) {
        var want = ident(id);
        if (!want || want === 'none') { chosenId = ''; return null; }
        var found = template(want);
        if (!found) return active();
        chosenId = found.id;
        return found;
    }

    function describe(t) {
        var c = cleanTemplate(t);
        var size = (c.size === Math.round(c.size) ? String(c.size) : c.size.toFixed(2));
        var bits = [size + ' contract' + (c.size === 1 ? '' : 's')];
        bits.push(c.stop_ticks ? 'stop ' + c.stop_ticks + 't' : 'no stop');
        bits.push(c.target_ticks ? 'target ' + c.target_ticks + 't' : 'no target');
        if (c.breakeven_ticks) bits.push('break-even at ' + c.breakeven_ticks + 't');
        if (c.trail_ticks) bits.push('trail ' + c.trail_ticks + 't/' + c.trail_step_ticks + 't');
        if (c.time_stop_min) bits.push('time stop ' + c.time_stop_min + ' min');
        if (c.partial_ticks) bits.push(c.partial_pct + '% off at ' + c.partial_ticks + 't');
        return (c.name || c.id || 'plan') + ' — ' + bits.join(', ');
    }

    /* ── the account's plan, as the grid reads it ───────────────────────────── */

    /* planOf(state) → the position's plan (a copy), or null when there is none to draw. */
    /* The share a plan's scale-out takes, named by the plan itself (§148 T1-D11): the labels said
       "half" whatever `partial_pct` was. A plan carrying no pct (an old payload) says the leg without
       a share rather than guessing one. */
    function partialLabel(p, what) {
        var raw = (p && p.partial) ? Number(p.partial.pct) : NaN;
        var pct = isFinite(raw) ? Math.round(raw) : 0;
        return (pct > 0) ? ' · ' + pct + '% ' + what : ' · partial ' + what;
    }

    function planOf(state) {
        var p = (state || {}).plan;
        if (!p || typeof p !== 'object' || !p.ok) return null;
        var out = {};
        var keys = ['group', 'text', 'side', 'entry', 'tick_size', 'stop_loss', 'take_profit',
                    'breakeven_price', 'breakeven_ticks', 'breakeven_done', 'trail_stop', 'trail_ticks',
                    'peak', 'status', 'outcome', 'partial', 'partial_done'];
        for (var i = 0; i < keys.length; i += 1) { out[keys[i]] = p[keys[i]]; }
        out.legs = legs(state);
        return out;
    }

    /* legs(state) → the plan's legs as copies: {name, price, ticks, kind, size, side}. */
    function legs(state) {
        var p = (state || {}).plan;
        var raw = (p && typeof p === 'object' && Array.isArray(p.legs)) ? p.legs : [];
        var out = [];
        for (var i = 0; i < raw.length; i += 1) {
            var leg = raw[i];
            if (!leg || typeof leg !== 'object') continue;
            out.push({name: String(leg.name || ''), price: num(leg.price), ticks: num(leg.ticks),
                      kind: String(leg.kind || ''), size: num(leg.size), side: String(leg.side || ''),
                      role: String(leg.role || '')});
        }
        return out;
    }

    /* How far the best price of the trade got, in ticks — the number the plan's peak means. */
    function peakTicks(p, tick) {
        if (!p || !num(p.entry) || !num(p.peak)) return null;
        var dir = String(p.side) === 'sell' ? -1 : 1;
        return Math.round(((num(p.peak) - num(p.entry)) * dir / (num(tick) || 0.01)) * 10) / 10;
    }

    /* rows(state, levels) → descending price rows, or null when no print has arrived. */
    function rows(state, levels) {
        var s = state || {};
        var last = num(s.last_price);
        var tick = num(s.tick_size) || 0.01;
        if (!(last > 0)) return null;
        var count = Math.max(5, Math.min(61, Math.round(num(levels) || LEVELS)));
        if (count % 2 === 0) count += 1;
        var half = Math.floor(count / 2);
        var center = roundTo(last, tick);
        var working = Array.isArray(s.orders) ? s.orders : [];
        var pos = s.position || { side: 'flat' };
        var exits = s.exits || {};
        var p = planOf(s);
        /* §148 T1-D6: the whole plan reads as LIVE or not at all. Only the break-even marker used to
           be status-gated, so a finished plan still drew its trailing stop and its stop/target row
           titles as if the trade were running. A plan with no status reads as live, as elsewhere. */
        var live = !!(p && String(p.status || 'live') === 'live');
        var beLevel = (live && !p.breakeven_done) ? num(p.breakeven_price) : 0;
        var trailLevel = live ? num(p.trail_stop) : 0;
        var out = [];
        for (var i = half; i >= -half; i -= 1) {
            var price = roundTo(center + i * tick, tick);
            var here = [];
            for (var j = 0; j < working.length; j += 1) {
                var o = working[j] || {};
                if (o.price !== null && o.price !== undefined && o.price !== '' &&
                    samePrice(o.price, price, tick)) here.push(o);
            }
            var note = '';
            if (live) {
                var dir = String(p.side) === 'sell' ? -1 : 1;
                var distance = Math.round((price - num(p.entry)) * dir / tick * 10) / 10;
                var where = (num(p.stop_loss) > 0 && samePrice(p.stop_loss, price, tick)) ? 'stop'
                    : ((num(p.take_profit) > 0 && samePrice(p.take_profit, price, tick)) ? 'target' : '');
                if (where) {
                    note = where + ' — ' + distance + ' ticks from entry (' + (p.text || p.group || 'plan') + ')';
                }
            }
            out.push({
                price: price,
                label: fmtPrice(price, tick),
                last: samePrice(last, price, tick),
                orders: here,
                entry: pos.side && pos.side !== 'flat' && samePrice(pos.entry_price, price, tick)
                    ? String(pos.side) : '',
                stop: exits.stop_loss !== null && exits.stop_loss !== undefined &&
                    exits.stop_loss !== '' && samePrice(exits.stop_loss, price, tick),
                target: exits.take_profit !== null && exits.take_profit !== undefined &&
                    exits.take_profit !== '' && samePrice(exits.take_profit, price, tick),
                breakeven: beLevel > 0 && samePrice(beLevel, price, tick),
                trail: trailLevel > 0 && samePrice(trailLevel, price, tick),
                plan: p ? String(p.text || p.group || '') : '',
                title: note
            });
        }
        return out;
    }

    /* decide(input) → {ok, side, kind, price, size, template} | {ok:false, why}. Every refusal
       carries its words. An active template owns the size, because the template *is* the plan: a
       2-contract runner clicked off a 1-contract ticket would be half a plan. */
    function decide(input) {
        var d = input || {};
        var tick = num(d.tick_size) || 0.01;
        var last = num(d.last_price);
        var price = num(d.price);
        var button = num(d.button);
        var right = button === 2;
        var t = (d.template && typeof d.template === 'object') ? cleanTemplate(d.template) : null;
        var size = (t && t.size > 0) ? t.size : num(d.size);
        if (!d.running) return { ok: false, why: 'start a paper session on the Replay view first' };
        if (!(last > 0)) return { ok: false, why: 'no print has arrived yet — press Play first' };
        if (d.locked) return { ok: false, why: 'trading is locked — unlock with Lock trading' };
        if (!d.armed) return { ok: false, why: 'that click places a simulated order — arm the order keys in the Keys menu first' };
        if (!(size > 0)) return { ok: false, why: 'size must be a positive number' };
        if (!(price > 0)) return { ok: false, why: 'that row has no price' };
        if (button !== 0 && !right && !d.shift) return { ok: false, why: 'left-click buys, right-click sells — shift makes it a market order' };
        var plan = t || null;
        if (d.shift) return { ok: true, side: right ? 'sell' : 'buy', kind: 'market', price: null, size: size, template: plan };
        if (samePrice(price, last, tick)) return { ok: true, side: right ? 'sell' : 'buy', kind: 'market', price: null, size: size, template: plan };
        var above = price > last;
        if (!right) {
            return above ? { ok: true, side: 'buy', kind: 'stop', price: price, size: size, template: plan }
                         : { ok: true, side: 'buy', kind: 'limit', price: price, size: size, template: plan };
        }
        return above ? { ok: true, side: 'sell', kind: 'limit', price: price, size: size, template: plan }
                     : { ok: true, side: 'sell', kind: 'stop', price: price, size: size, template: plan };
    }

    /* ── the plan bar ──────────────────────────────────────────────────────── */

    function statusLine(state, current) {
        var s = state || {};
        var tick = num(s.tick_size) || 0.01;
        var bits = [current
            ? 'next entry: ' + describe(current)
            : 'next entry: no plan — the ticket size and no bracket'];
        var p = planOf(s);
        if (p) {
            var how = String(p.status) === 'done'
                ? 'done — ' + (p.outcome || 'closed')
                : 'live — stop ' + priceOr(p.stop_loss, tick) +
                  (num(p.trail_stop) > 0 ? ' (trail)' : '') + ' · target ' + priceOr(p.take_profit, tick);
            var peak = peakTicks(p, tick);
            bits.push('position: ' + (p.text || p.group || 'plan') + ' ' + how +
                (peak === null ? '' : ' · peak +' + peak + 't') +
                (num(p.breakeven_done) ? ' · stop at break-even' : '') +
                (p.partial_done ? partialLabel(p, 'off taken') : '') +
                (p.partial && !p.partial_done ? partialLabel(p, 'resting') : ''));
        } else if (s.running) {
            bits.push('position: no plan');
        }
        return bits.join('   ·   ');
    }

    function toolsHtml(state, api) {
        var s = state || {};
        var list = templates();
        var current = active();
        var chips = '<button class="ld-order' + (current ? '' : ' on') + '" data-ld="tpl:none"' +
            (current ? '' : ' style="' + CHIP_ON + '"') +
            ' title="no plan — the next click sends the ticket size and no bracket">no plan</button>';
        for (var i = 0; i < list.length; i += 1) {
            var t = list[i];
            var on = Boolean(current && current.id === t.id);
            chips += '<button class="ld-order' + (on ? ' on' : '') + '" data-ld="tpl:' + esc(t.id) + '"' +
                (on ? ' style="' + CHIP_ON + '"' : '') + ' title="' + esc(describe(t)) + '">' +
                esc(t.name || t.id) + ' ' + esc(t.size) + '</button>';
        }
        var working = Array.isArray(s.orders) ? s.orders.length : 0;
        chips += '<button class="ld-order ld-order-sell" data-ld="cancel-all"' +
            (working ? '' : ' disabled') + ' title="' + (working
                ? 'cancel every working order — the plan\'s resting legs included'
                : 'no working orders to cancel') + '">cancel all (' + working + ')</button>';
        return '<div data-ld="bar" style="' + BAR + '">' + chips + '</div>' +
            '<div class="dim" data-ld="line" style="' + LINE + '">' + esc(statusLine(s, current)) + '</div>';
    }

    /* ── clicks ────────────────────────────────────────────────────────────── */

    /* cancelAll(state, api) → the ids it took off the book. One call when paper.js hands us its
       own cancelAll, otherwise one cancel per working order — the same orders either way. */
    function cancelAll(state, api) {
        var s = state || {};
        var working = Array.isArray(s.orders) ? s.orders : [];
        var ids = [];
        for (var i = 0; i < working.length; i += 1) {
            var id = String((working[i] || {}).id || '');
            if (id) ids.push(id);
        }
        if (!ids.length) {
            if (api && api.note) api.note('no working orders to cancel');
            return [];
        }
        if (api && typeof api.cancelAll === 'function') { api.cancelAll(); return ids; }
        for (var j = 0; j < ids.length; j += 1) { if (api && api.cancel) api.cancel(ids[j]); }
        return ids;
    }

    /* act(target, state, api, button, shift) → what one click meant, as a word the selftest can
       pin: 'cancel-chip' | 'template' | 'cancel-all' | 'place' | 'note' | 'none'. */
    function act(target, state, api, button, shift) {
        var t = target;
        if (!t || typeof t.closest !== 'function') return 'none';
        var control = t.closest('[data-ld]');
        if (control) {
            var what = String(control.getAttribute('data-ld') || '');
            if (what === 'cancel-all') { cancelAll(state, api); return 'cancel-all'; }
            if (what.indexOf('tpl:') === 0) {
                var want = what.slice(4);
                select(want === 'none' ? '' : want);
                if (state && typeof state === 'object') paint(state, api);   // the bar shows the pick
                return 'template';
            }
            return 'none';                                                  // the bar's own background
        }
        var chip = t.closest('.ld-order');
        if (chip) {
            var id = String(chip.getAttribute('data-id') || '');
            if (id && api && api.cancel) api.cancel(id);
            return id ? 'cancel-chip' : 'none';
        }
        var row = t.closest('.ld-row');
        if (!row) return 'none';                                            // a stray click does nothing
        var outcome = fire(state, api, Number(row.getAttribute('data-price')), num(button), shift);
        return outcome.ok ? 'place' : 'note';
    }

    /* ── the painter ───────────────────────────────────────────────────────── */

    /* paint(state, api) — api: {size(), locked(), armed(), place(body), cancel(id),
       cancelAll?(), note(text)}. cancelAll is optional: without it the ladder cancels each order. */
    function paint(state, api) {
        var host = document.getElementById('ladderBody');
        if (!host) return;
        var s = state || {};
        var bar = toolsHtml(s, api);
        var list = rows(s, LEVELS);
        if (!list) {
            paintHandlers(host, s, api);
            host.innerHTML = bar +
                '<div class="dim" style="padding:12px">no print yet — load a session and press Play</div>';
            return;
        }
        var parts = [];
        for (var i = 0; i < list.length; i += 1) {
            var r = list[i];
            var cls = 'ld-row';
            if (r.last) cls += ' ld-last';
            if (r.entry === 'long') cls += ' ld-long';
            if (r.entry === 'short') cls += ' ld-short';
            if (r.stop) cls += ' ld-stop';
            if (r.target) cls += ' ld-target';
            if (r.breakeven) cls += ' ld-breakeven';
            if (r.trail) cls += ' ld-trail';
            var marks = '';
            if (r.entry) marks += '<span class="ld-mark ld-mark-entry">' + (r.entry === 'long' ? 'LONG' : 'SHORT') + '</span>';
            if (r.stop) marks += '<span class="ld-mark ld-mark-stop">SL</span>';
            if (r.target) marks += '<span class="ld-mark ld-mark-target">TP</span>';
            if (r.breakeven) marks += '<span class="ld-mark ld-mark-breakeven" style="color:rgb(255,214,102);border-color:rgba(255,214,102,.5)" title="the stop moves to the entry price when a print reaches here">BE</span>';
            if (r.trail) marks += '<span class="ld-mark ld-mark-trail" style="color:rgb(255,214,102);border-color:rgba(255,214,102,.5)" title="the trailing stop stands here and only ever ratchets">TRAIL</span>';
            var chips = '';
            for (var j = 0; j < r.orders.length; j += 1) {
                var o = r.orders[j];
                chips += '<button class="ld-order ld-order-' + (String(o.side) === 'sell' ? 'sell' : 'buy') +
                    '" data-id="' + String(o.id || '') + '" title="' + esc(String(o.side || '') + ' ' +
                    String(o.size || '') + ' ' + String(o.kind || '') +
                    (o.group ? ' · plan ' + String(o.group) : '') +
                    (o.plan_leg ? ' · its ' + String(o.plan_leg) + ' leg' : '') + ' — click to cancel') + '">' +
                    String(o.side || '').charAt(0).toUpperCase() + ' ' + String(o.size || '') + ' ' +
                    String(o.kind || '') + ' &times;</button>';
            }
            parts.push('<div class="' + cls + '" data-price="' + r.price + '"' +
                (r.title ? ' title="' + esc(r.title) + '"' : '') + '><span class="ld-marks">' +
                marks + '</span><span class="ld-price">' + r.label + '</span><span class="ld-orders">' +
                chips + '</span></div>');
        }
        host.innerHTML = bar + parts.join('');
        paintHandlers(host, s, api);
    }

    /* The three click doors. They are properties, not listeners, so a paint replaces the wiring
       instead of stacking it — and every one of them delegates to act(), which is where the
       grammar lives. A click that reaches none of them places nothing: that is the stray-click
       guard the ladder has always had. */
    function paintHandlers(host, state, api) {
        host.oncontextmenu = function (ev) {
            var row = ev.target && ev.target.closest ? ev.target.closest('.ld-row') : null;
            if (!row) return;
            ev.preventDefault();
            act(ev.target, state, api, 2, ev.shiftKey);
        };
        /* Real browsers fire auxclick (not click) for the middle button, so the grammar's own
           sentence would never reach a user who tried one — this is where it gets said. */
        host.onauxclick = function (ev) {
            var row = ev.target && ev.target.closest ? ev.target.closest('.ld-row') : null;
            if (!row) return;
            ev.preventDefault();
            act(ev.target, state, api, 1, ev.shiftKey);
        };
        host.onclick = function (ev) {
            var target = ev.target;
            if (!target || typeof target.closest !== 'function') return;
            if (target.closest('[data-ld]')) { act(target, state, api, num(ev.button), ev.shiftKey); return; }
            if (target.closest('.ld-order')) { act(target, state, api, 0, false); return; }
            if (!target.closest('.ld-row')) return;
            act(target, state, api, 0, ev.shiftKey);
        };
    }

    function fire(state, api, price, button, shift) {
        var locked = false;
        var armed = false;
        try { locked = Boolean(api.locked()); } catch (e1) { locked = false; }
        try { armed = Boolean(api.armed()); } catch (e2) { armed = false; }
        var d = decide({
            running: Boolean(state && state.running), locked: locked, armed: armed,
            size: sizeOf(api), template: active(),
            last_price: state && state.last_price,
            tick_size: state && state.tick_size, price: price, button: button, shift: shift
        });
        if (!d.ok) { api.note(d.why); return d; }
        var body = { side: d.side, size: d.size, kind: d.kind, price: d.price };
        if (d.template) body.template = d.template;      // the plan travels with the order
        api.place(body);
        return d;
    }

    function sizeOf(api) {
        try { return api && api.size ? Number(api.size()) : 1; } catch (err) { return 1; }
    }

    window.OFAPLADDER = { rows: rows, decide: decide, paint: paint, fmtPrice: fmtPrice, LEVELS: LEVELS,
        act: act, templates: templates, setTemplates: setTemplates, template: template, active: active,
        select: select, describe: describe, legs: legs, plan: planOf, cancelAll: cancelAll,
        statusLine: statusLine, roundTo: roundTo, samePrice: samePrice };
})();
