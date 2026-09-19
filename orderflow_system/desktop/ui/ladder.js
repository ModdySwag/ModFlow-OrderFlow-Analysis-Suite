/* Ladder — the Trade-DOM surface for the paper account (§118).
 *
 * The pure half is small on purpose: `rows()` lays the price grid out of the account state the
 * Replay view already polls, and `decide()` turns one click into one order decision — or into a
 * refusal, sentence included. `paint()` draws the grid and hands clicks back to paper.js, which
 * owns the session, the lock and the armed gate; nothing here talks to the API directly, so the
 * account keeps exactly one gatekeeper.
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
 */
'use strict';

(function () {
    var LEVELS = 21;

    function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }

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
        var out = [];
        for (var i = half; i >= -half; i -= 1) {
            var price = roundTo(center + i * tick, tick);
            var here = [];
            for (var j = 0; j < working.length; j += 1) {
                var o = working[j] || {};
                if (o.price !== null && o.price !== undefined && o.price !== '' &&
                    samePrice(o.price, price, tick)) here.push(o);
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
                    exits.take_profit !== '' && samePrice(exits.take_profit, price, tick)
            });
        }
        return out;
    }

    /* decide(input) → {ok, side, kind, price} | {ok:false, why}. Every refusal carries its words. */
    function decide(input) {
        var d = input || {};
        var tick = num(d.tick_size) || 0.01;
        var last = num(d.last_price);
        var price = num(d.price);
        var size = num(d.size);
        var button = num(d.button);
        var right = button === 2;
        if (!d.running) return { ok: false, why: 'start a paper session on the Replay view first' };
        if (!(last > 0)) return { ok: false, why: 'no print has arrived yet — press Play first' };
        if (d.locked) return { ok: false, why: 'trading is locked — unlock with Lock trading' };
        if (!d.armed) return { ok: false, why: 'that click places a simulated order — arm the order keys in the Keys menu first' };
        if (!(size > 0)) return { ok: false, why: 'size must be a positive number' };
        if (!(price > 0)) return { ok: false, why: 'that row has no price' };
        if (button !== 0 && !right && !d.shift) return { ok: false, why: 'left-click buys, right-click sells — shift makes it a market order' };
        if (d.shift) return { ok: true, side: right ? 'sell' : 'buy', kind: 'market', price: null };
        if (samePrice(price, last, tick)) return { ok: true, side: right ? 'sell' : 'buy', kind: 'market', price: null };
        var above = price > last;
        if (!right) {
            return above ? { ok: true, side: 'buy', kind: 'stop', price: price }
                         : { ok: true, side: 'buy', kind: 'limit', price: price };
        }
        return above ? { ok: true, side: 'sell', kind: 'limit', price: price }
                     : { ok: true, side: 'sell', kind: 'stop', price: price };
    }

    /* paint(state, api) — api: {size(), locked(), armed(), place(body), cancel(id), note(text)} */
    function paint(state, api) {
        var host = document.getElementById('ladderBody');
        if (!host) return;
        var s = state || {};
        var list = rows(s, LEVELS);
        if (!list) {
            host.innerHTML = '<div class="dim" style="padding:12px">no print yet — load a session and press Play</div>';
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
            var marks = '';
            if (r.entry) marks += '<span class="ld-mark ld-mark-entry">' + (r.entry === 'long' ? 'LONG' : 'SHORT') + '</span>';
            if (r.stop) marks += '<span class="ld-mark ld-mark-stop">SL</span>';
            if (r.target) marks += '<span class="ld-mark ld-mark-target">TP</span>';
            var chips = '';
            for (var j = 0; j < r.orders.length; j += 1) {
                var o = r.orders[j];
                chips += '<button class="ld-order ld-order-' + (String(o.side) === 'sell' ? 'sell' : 'buy') +
                    '" data-id="' + String(o.id || '') + '" title="' + String(o.side || '') + ' ' +
                    String(o.size || '') + ' ' + String(o.kind || '') + ' — click to cancel">' +
                    String(o.side || '').charAt(0).toUpperCase() + ' ' + String(o.size || '') + ' ' +
                    String(o.kind || '') + ' &times;</button>';
            }
            parts.push('<div class="' + cls + '" data-price="' + r.price + '"><span class="ld-marks">' +
                marks + '</span><span class="ld-price">' + r.label + '</span><span class="ld-orders">' +
                chips + '</span></div>');
        }
        host.innerHTML = parts.join('');
        host.oncontextmenu = function (ev) {
            var row = ev.target && ev.target.closest ? ev.target.closest('.ld-row') : null;
            if (!row) return;
            ev.preventDefault();
            fire(s, api, Number(row.getAttribute('data-price')), 2, ev.shiftKey);
        };
        /* Real browsers fire auxclick (not click) for the middle button, so the grammar's own
           sentence would never reach a user who tried one — this is where it gets said. */
        host.onauxclick = function (ev) {
            var row = ev.target && ev.target.closest ? ev.target.closest('.ld-row') : null;
            if (!row) return;
            ev.preventDefault();
            fire(s, api, Number(row.getAttribute('data-price')), 1, ev.shiftKey);
        };
        host.onclick = function (ev) {
            var chip = ev.target && ev.target.closest ? ev.target.closest('.ld-order') : null;
            if (chip) { api.cancel(String(chip.getAttribute('data-id') || '')); return; }
            var row = ev.target && ev.target.closest ? ev.target.closest('.ld-row') : null;
            if (!row) return;
            fire(s, api, Number(row.getAttribute('data-price')), 0, ev.shiftKey);
        };
    }

    function fire(state, api, price, button, shift) {
        var locked = false;
        var armed = false;
        try { locked = Boolean(api.locked()); } catch (e1) { locked = false; }
        try { armed = Boolean(api.armed()); } catch (e2) { armed = false; }
        var d = decide({
            running: Boolean(state && state.running), locked: locked, armed: armed,
            size: sizeOf(api), last_price: state && state.last_price,
            tick_size: state && state.tick_size, price: price, button: button, shift: shift
        });
        if (!d.ok) { api.note(d.why); return; }
        api.place({ side: d.side, size: sizeOf(api), kind: d.kind, price: d.price });
    }

    function sizeOf(api) {
        try { return api && api.size ? Number(api.size()) : 1; } catch (err) { return 1; }
    }

    window.OFAPLADDER = { rows: rows, decide: decide, paint: paint, fmtPrice: fmtPrice, LEVELS: LEVELS };
})();
