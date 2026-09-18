/* paper.js — the simulated-account panel (R9) on the Replay view.
 *
 * The account itself lives on the server: it consumes the prints the replay (or the live tape)
 * already delivers, so fills are the tape's — a market order fills at the next print, a limit when
 * a print trades through its price. This module is the ticket and the read-out; it never invents a
 * price. Polling follows the house rule: only while the Replay view is on screen.
 */
(function () {
    'use strict';

    var POLL_MS = 2000;
    var timer = null;
    var lastId = '';
    var locked = false;      // T3: Lock trading — order placement off, flatten/cancel stay live
    var runningNow = false;

    function $(id) { return document.getElementById(id); }
    function num(id) { var el = $(id); var v = el ? parseFloat(el.value) : NaN; return isFinite(v) ? v : null; }
    var esc = (t) => String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    function ticks(v) { return (Math.round(Number(v || 0) * 100) / 100).toString(); }

    function render(state) {
        state = state || {};
        runningNow = Boolean(state.running);
        var pill = $('ppPillText');
        var pos = state.position || { side: 'flat', size: 0 };
        if (pill) pill.textContent = state.running
            ? (state.symbol || 'session') + (pos.side === 'flat' ? ' — flat' : ' — ' + pos.side + ' ' + pos.size)
            : 'no session';
        var posEl = $('ppPosition');
        if (posEl) {
            posEl.querySelector('.kpi-value').textContent = pos.side === 'flat' ? 'flat' : pos.side + ' ' + pos.size;
            posEl.querySelector('.kpi-sub').textContent = pos.side === 'flat'
                ? '—' : ('entry ' + (pos.entry_price != null ? pos.entry_price : '—'));
        }
        /* T6/A8 — the ticket's own context validity: a panic button that cannot act is shown
           disabled with the reason, not armed-looking and silent. (Placement stays governed by
           Lock trading; these two are about whether there is anything to act on.) */
        var working = Array.isArray(state.orders) ? state.orders.length : 0;
        var flat = (pos.side || 'flat') === 'flat' || !pos.size;
        var bFlat = $('ppFlatten');
        if (bFlat) {
            bFlat.disabled = flat && !working;
            bFlat.title = bFlat.disabled
                ? 'nothing to flatten — the position is flat and no orders are working'
                : 'close the position at market and clear the working orders';
        }
        var bCancel = $('ppCancelAll');
        if (bCancel) {
            bCancel.disabled = !working;
            bCancel.title = working ? 'cancel every working order' : 'no working orders to cancel';
        }
        var stats = state.stats || {};
        var mark = state.mark || {};
        var set = function (id, value, sub) {
            var el = $(id);
            if (!el) return;
            el.querySelector('.kpi-value').textContent = value;
            if (sub != null) el.querySelector('.kpi-sub').textContent = sub;
        };
        set('ppRealised', ticks(stats.realised_ticks) , 'ticks');
        set('ppUnrealised', ticks(mark.unrealised_ticks), 'equity ' + ticks(mark.equity_ticks));
        set('ppWorking', String((state.orders || []).length), 'orders');
        var fills = $('ppFills');
        if (fills) {
            var rows = (state.fills || []).slice(-8).reverse().map(function (f) {
                return '<div>' + esc(f.ts_ms ? new Date(f.ts_ms).toISOString().slice(11, 19) : '') + 'Z · ' +
                    esc(f.side) + ' ' + esc(f.size) + ' @ ' + esc(f.price) + ' · ' + esc(f.reason) + '</div>';
            });
            var working = (state.orders || []).map(function (o) {
                return '<div>working: ' + esc(o.side) + ' ' + esc(o.size) + ' ' + esc(o.kind) +
                    (o.price != null ? ' @ ' + esc(o.price) : '') + '</div>';
            });
            fills.innerHTML = rows.concat(working).join('')
                || ('no fills yet — start a session and press Play'
                    + (window.OFAPHELP ? ' · ' + OFAPHELP.topicLink('view.replay', 'how this works') : ''));
        }
        /* T13/B11: hand the consequence maths its context — the drawings' drag chip and the
           ticket's own read-out both read from here, so nothing has to invent a price. */
        if (window.OFAPRISK) {
            OFAPRISK.setContext({ running: Boolean(state.running), symbol: state.symbol,
                tick: Number(stats.tick_size) || 0.01, position: pos, mark: mark,
                last: Number(state.last_price) || 0 });
        }
        paintRisk();
    }

    function load() {
        return window.api('/api/atlas/replay/paper/state').then(function (res) {
            render((res || {}).state);
            return res;
        }).catch(function () { /* offline: keep the last paint */ });
    }

    function act(path, body, label) {
        var out = $('ppResult');
        if (out) out.textContent = label + '…';
        return window.api(path, { method: 'POST', body: body || {} }).then(function (res) {
            if (res && res.state) render(res.state);
            if (out) out.textContent = res && res.ok
                ? (label + ' ok' + (res.saved != null ? ' — ' + res.saved + ' trade(s) ' + (res.note || '') : ''))
                : (label + ' refused: ' + ((res && (res.error || res.detail)) || 'unknown'));
            return res;
        }).catch(function (err) {
            if (out) out.textContent = label + ' failed: ' + err;
        });
    }

    function needSession() {
        var symbol = (document.getElementById('symbolSelect') || {}).value || '';
        var tick = 0.01;
        return act('/api/atlas/replay/paper/start', { symbol: symbol, tick_size: tick }, 'starting a session');
    }

    function paintLock() {
        var buy = $('ppBuy');
        var sell = $('ppSell');
        var btn = $('ppLock');
        if (buy) buy.disabled = locked;
        if (sell) sell.disabled = locked;
        if (btn) {
            btn.textContent = locked ? 'Trading locked' : 'Lock trading';
            btn.setAttribute('aria-pressed', locked ? 'true' : 'false');
            btn.classList.toggle('on', locked);
        }
    }

    function setLocked(value) {
        locked = Boolean(value);
        paintLock();
        if (window.api) {
            void window.api('/api/control/config', { method: 'POST', body: { ui: { paper_lock: locked } } })
                .catch(function () { /* the lock still holds this session */ });
        }
        var out = $('ppResult');
        if (out) out.textContent = locked
            ? 'trading locked — Buy/Sell and the armed keys are off; flatten and cancel stay live'
            : 'trading unlocked';
        return locked;
    }

    function order(side) {
        if (locked) {
            var out = $('ppResult');
            if (out) out.textContent = 'trading is locked — unlock with Lock trading';
            return;
        }
        var size = num('ppSize') || 1;
        var kind = (($('ppKind') || {}).value) || 'market';
        var body = { side: side, size: size, kind: kind, price: num('ppPrice'),
                     stop_loss: num('ppSl'), take_profit: num('ppTp') };
        load().then(function (res) {
            if (res && res.state && res.state.running) return act('/api/atlas/replay/paper/order', body, side + ' order');
            return needSession().then(function () { return act('/api/atlas/replay/paper/order', body, side + ' order'); });
        });
    }

    function onScreen() {
        if (document.hidden || window.OFAP_PAUSED) return false;
        var section = document.querySelector('.view[data-view="replay"]');
        if (!section) return false;
        return section.classList.contains('active') || section.style.display === 'flex';
    }

    /* T13/B11: the stop/target fields priced as the ACCOUNT would feel them — ticks, the paper
       account's own unit. No position: an honest distance from the mark, never a pretend P/L. */
    function paintRisk() {
        var out = $('ppRisk');
        if (!out || !window.OFAPRISK) return;
        var bits = [];
        [['ppSl', 'stop'], ['ppTp', 'target']].forEach(function (pair) {
            var value = num(pair[0]);
            if (value == null) return;
            var line = OFAPRISK.text(value);
            if (line) bits.push(pair[1] + ' — ' + line);
        });
        out.textContent = bits.length ? bits.join('  ·  ')
            : 'stop / target typed here are priced in paper ticks against the account.';
    }

    function boot() {
        var b;
        if ((b = $('ppBuy'))) b.onclick = function () { order('buy'); };
        if ((b = $('ppSell'))) b.onclick = function () { order('sell'); };
        if ((b = $('ppFlatten'))) b.onclick = function () { act('/api/atlas/replay/paper/flatten', {}, 'flattening'); };
        if ((b = $('ppCancelAll'))) b.onclick = function () { act('/api/atlas/replay/paper/cancel', {}, 'cancelling'); };
        if ((b = $('ppEnd'))) b.onclick = function () { act('/api/atlas/replay/paper/close', {}, 'ending the session'); };
        if ((b = $('ppLock'))) b.onclick = function () { setLocked(!locked); };
        ['ppSl', 'ppTp'].forEach(function (id) {
            var el = $(id);
            if (el && el.addEventListener) el.addEventListener('input', paintRisk);
        });
        /* T3: the order keys exist, are armed-gated, and only act on this view mid-session. */
        if (window.OFAPKEYS) {
            var gate = function () { return onScreen() && runningNow && !locked; };
            OFAPKEYS.bind({ id: 'paper-buy', keys: ['alt+b'], scope: 'Replay', danger: true,
                label: 'paper: buy at market (needs armed order keys)', when: gate, why: 'needs a running paper session on the Replay view, unlocked',
                run: function () { order('buy'); } });
            OFAPKEYS.bind({ id: 'paper-sell', keys: ['alt+s'], scope: 'Replay', danger: true,
                label: 'paper: sell at market (needs armed order keys)', when: gate, why: 'needs a running paper session on the Replay view, unlocked',
                run: function () { order('sell'); } });
            OFAPKEYS.bind({ id: 'paper-flatten', keys: ['alt+x'], scope: 'Replay', danger: true,
                label: 'paper: flatten the position (needs armed order keys)', when: gate, why: 'needs a running paper session on the Replay view, unlocked',
                run: function () { act('/api/atlas/replay/paper/flatten', {}, 'flattening'); } });
        }
        if (window.api) {
            window.api('/api/control/config').then(function (cfg) {
                locked = Boolean(cfg && cfg.ui && cfg.ui.paper_lock);
                paintLock();
            }).catch(function () { /* unlocked by default */ });
        }
        var wrap = window.showView;
        if (typeof wrap === 'function') {
            window.showView = function (name) {
                var out = wrap.apply(this, arguments);
                if (name === 'replay') setTimeout(load, 400);
                return out;
            };
        }
        timer = setInterval(function () { if (onScreen()) load(); }, POLL_MS);
        setTimeout(function () { if (onScreen()) load(); }, 1500);
    }

    window.OFAPPAPER = { load: load, state: null, paintRisk: paintRisk,
        locked: function () { return locked; }, setLocked: setLocked };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
