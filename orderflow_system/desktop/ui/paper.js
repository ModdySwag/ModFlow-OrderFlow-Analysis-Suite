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
                tick: Number(state.tick_size) || Number(stats.tick_size) || 0.01, position: pos, mark: mark,
                last: Number(state.last_price) || 0 });
        }
        paintRisk();
        if (window.OFAPPAPER) window.OFAPPAPER.state = state;
        paintExits(state, pos);
        paintLedger(state);
        paintStrip(state, pos, mark, flat);
        if (window.OFAPLADDER) {
            OFAPLADDER.paint(state, {
                size: function () { return num('ppSize') || 1; },
                locked: function () { return locked; },
                armed: function () { return Boolean(window.OFAPKEYS && OFAPKEYS.armed && OFAPKEYS.armed()); },
                note: function (text) { var out = $('ppResult'); if (out) out.textContent = text; },
                place: function (body) { submit(body, body.side + ' ' + body.kind + ' order (ladder)', true, 'ppResult'); },
                cancel: function (id) { if (id) act('/api/atlas/replay/paper/cancel', { order_id: id }, 'cancelling ' + id); }
            });
        }
    }

    function load() {
        return window.api('/api/atlas/replay/paper/state').then(function (res) {
            render((res || {}).state);
            return res;
        }).catch(function () { /* offline: keep the last paint */ });
    }

    function act(path, body, label, outId) {
        var out = $(outId || 'ppResult');
        if (out) out.textContent = label + '…';
        return window.api(path, { method: 'POST', body: body || {} }).then(function (res) {
            if (res && res.state) render(res.state);
            if (out) out.textContent = res && res.ok
                ? (label + ' ok' + (res.path ? ' — ' + res.path : '')
                    + (res.saved != null ? ' — ' + res.saved + ' trade(s) ' + (res.note || '') : ''))
                : (label + ' refused: ' + ((res && (res.error || res.detail)) || 'unknown'));
            return res;
        }).catch(function (err) {
            if (out) out.textContent = label + ' failed: ' + err;
        });
    }

    /* The session's tick sets the ladder's row spacing and the account's own "ticks" unit, so it
       comes from the instrument's record rather than a guess: BTC's tick is 0.1, and a ±10-tick
       ladder window has to mean 0.1, or the DOM is a tenth of a cent wide. */
    function tickFor(symbol) {
        try {
            var list = (typeof S !== 'undefined' && S && S.config && S.config.instruments) || [];
            for (var i = 0; i < list.length; i += 1) {
                if (String((list[i] || {}).symbol) === String(symbol)) {
                    var t = Number(list[i].tick_size);
                    if (isFinite(t) && t > 0) return t;
                }
            }
        } catch (err) { /* fall through to the shipped default */ }
        return 0.01;
    }

    function needSession(outId) {
        var symbol = (document.getElementById('symbolSelect') || {}).value || '';
        return act('/api/atlas/replay/paper/start', { symbol: symbol, tick_size: tickFor(symbol) },
            'starting a session', outId);
    }

    function paintLock() {
        var buy = $('ppBuy');
        var sell = $('ppSell');
        var btn = $('ppLock');
        if (buy) buy.disabled = locked;
        if (sell) sell.disabled = locked;
        var sBuy = $('stripBuy');
        var sSell = $('stripSell');
        if (sBuy) sBuy.disabled = locked;
        if (sSell) sSell.disabled = locked;
        var sLock = $('stripLock');
        if (sLock) {
            sLock.textContent = locked ? 'Locked' : 'Lock';
            sLock.setAttribute('aria-pressed', locked ? 'true' : 'false');
            sLock.classList.toggle('on', locked);
        }
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

    /* submit() is the single door orders leave by. The ticket walks through it unlocked; the
       ladder walks through it armed — a dense price grid is exactly where a stray click finds a
       resting order, so it obeys the same switch the danger keys do. Lock trading closes both. */
    function submit(body, label, needArmed, outId) {
        var out = $(outId || 'ppResult');
        if (locked) {
            if (out) out.textContent = 'trading is locked — unlock with Lock trading';
            return Promise.resolve(null);
        }
        if (needArmed && window.OFAPKEYS && OFAPKEYS.armed && !OFAPKEYS.armed()) {
            if (out) out.textContent = 'that click places a simulated order — arm the order keys in the Keys menu first';
            return Promise.resolve(null);
        }
        return load().then(function (res) {
            if (res && res.state && res.state.running) return act('/api/atlas/replay/paper/order', body, label, outId);
            return needSession(outId).then(function () { return act('/api/atlas/replay/paper/order', body, label, outId); });
        });
    }

    function order(side, outId) {
        var size = num('ppSize') || 1;
        var kind = (($('ppKind') || {}).value) || 'market';
        submit({ side: side, size: size, kind: kind, price: num('ppPrice'),
                 stop_loss: num('ppSl'), take_profit: num('ppTp') }, side + ' order', false, outId);
    }

    /* The account is one wherever it can be traded from: the Replay view owns the session
       controls and the ladder, the Chart view carries the quick strip. Poll while either is
       showing, so both surfaces read the same numbers. */
    function onScreen() {
        if (document.hidden || window.OFAP_PAUSED) return false;
        var names = ['replay', 'chart'];
        for (var i = 0; i < names.length; i += 1) {
            var section = document.querySelector('.view[data-view="' + names[i] + '"]');
            if (section && (section.classList.contains('active') || section.style.display === 'flex')) return true;
        }
        return false;
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

    var LEDGER_KINDS = { start: 'session', submit: 'order', reject: 'refused', fill: 'fill',
                         cancel: 'cancel', exits: 'exits', end: 'end' };

    function tapeTime(ms) {
        var n = Number(ms) || 0;
        if (n <= 0) return '—:—:—';
        try { return new Date(n).toISOString().slice(11, 19); } catch (err) { return '—:—:—'; }
    }

    /* The open position's bracket — shown as the pair the account carries, applied as one. */
    function paintExits(state, pos) {
        var flatHere = (pos.side || 'flat') === 'flat' || !pos.size;
        var exits = state.exits || {};
        var sl = $('ppxSl');
        var tp = $('ppxTp');
        if (sl && document.activeElement !== sl) sl.value = exits.stop_loss != null ? exits.stop_loss : '';
        if (tp && document.activeElement !== tp) tp.value = exits.take_profit != null ? exits.take_profit : '';
        ['ppxApply', 'ppxBreakeven', 'ppxClear'].forEach(function (id) {
            var btn = $(id);
            if (btn) btn.disabled = flatHere;
        });
        var hint = $('ppExitsHint');
        if (hint) hint.textContent = flatHere
            ? 'exits attach to an open position — fill first, then set or move them here'
            : 'stop ' + (exits.stop_loss != null ? exits.stop_loss : '—') + ' · target ' +
              (exits.take_profit != null ? exits.take_profit : '—') +
              ' — one pair, so a single print can only ever close the position once';
    }

    /* The session ledger: every submit, refusal, fill, cancel and exit, tape-stamped. */
    function paintLedger(state) {
        var host = $('ppLedger');
        var count = $('ppLedgerCount');
        var events = Array.isArray(state.events) ? state.events : [];
        var total = Number(state.event_count) || events.length;
        if (count) count.textContent = total + (total === 1 ? ' event' : ' events');
        if (!host) return;
        if (!events.length) {
            host.innerHTML = '<div class="dim">the order log appears here — every submit, fill, cancel and exit, stamped with the tape’s own clock</div>';
            return;
        }
        host.innerHTML = events.slice(-14).reverse().map(function (e) {
            var bits = [tapeTime(e.at_ms), LEDGER_KINDS[e.kind] || esc(e.kind)];
            if (e.side) bits.push(esc(e.side));
            if (e.size != null && e.size !== '') bits.push(esc(e.size));
            if (e.price != null && e.price !== '') bits.push('@ ' + esc(e.price));
            if (e.order_kind && e.kind !== 'start' && e.kind !== 'submit' && e.kind !== 'reject') bits.push(esc(e.order_kind));
            if (e.note) bits.push('· ' + esc(e.note));
            return '<div class="ld-ledger-row ld-ledger-' + esc(e.kind || 'x') + '">' + bits.join(' ') + '</div>';
        }).join('');
    }

    /* The chart-side quick strip: the same account, four buttons and the open P/L. */
    function paintStrip(state, pos, mark, flat) {
        var pill = $('stripPillText');
        if (pill) pill.textContent = state.running
            ? (state.symbol || 'session') + (flat ? ' — flat' : ' — ' + pos.side + ' ' + pos.size)
            : 'no session';
        var exits = state.exits || {};
        var hint = $('stripHint');
        if (hint) hint.textContent = state.running
            ? (flat ? 'flat · ' : 'open ' + pos.side + ' ' + pos.size + ' @ ' +
               (pos.entry_price != null ? pos.entry_price : '—') + ' · ') +
              'open P/L ' + ticks(mark.unrealised_ticks) + ' ticks · stop ' +
              (exits.stop_loss != null ? exits.stop_loss : '—') + ' / target ' +
              (exits.take_profit != null ? exits.take_profit : '—')
            : 'no session — the Replay view starts one; this strip trades the same account';
        var working = Array.isArray(state.orders) ? state.orders.length : 0;
        var bFlatten = $('stripFlatten');
        if (bFlatten) {
            bFlatten.disabled = (flat && !working) || locked;
            bFlatten.title = flat && !working
                ? 'nothing to flatten — the position is flat and no orders are working'
                : 'close the position at market and clear the working orders';
        }
        var sSize = $('stripSize');
        var tSize = $('ppSize');
        if (sSize && document.activeElement !== sSize && tSize && tSize.value !== sSize.value) {
            sSize.value = tSize.value;   // the ticket owns the size; the strip mirrors it
        }
    }

    function boot() {
        var b;
        if ((b = $('ppBuy'))) b.onclick = function () { order('buy'); };
        if ((b = $('ppSell'))) b.onclick = function () { order('sell'); };
        if ((b = $('ppFlatten'))) b.onclick = function () { act('/api/atlas/replay/paper/flatten', {}, 'flattening'); };
        if ((b = $('ppCancelAll'))) b.onclick = function () { act('/api/atlas/replay/paper/cancel', {}, 'cancelling'); };
        if ((b = $('ppEnd'))) b.onclick = function () { act('/api/atlas/replay/paper/close', {}, 'ending the session'); };
        if ((b = $('ppLock'))) b.onclick = function () { setLocked(!locked); };
        if ((b = $('ppxApply'))) b.onclick = function () {
            act('/api/atlas/replay/paper/exits', { stop_loss: num('ppxSl'), take_profit: num('ppxTp') }, 'moving exits');
        };
        if ((b = $('ppxBreakeven'))) b.onclick = function () {
            var pos = ((window.OFAPPAPER || {}).state || {}).position || {};
            if (pos.side === 'flat' || pos.entry_price == null) {
                var out0 = $('ppResult');
                if (out0) out0.textContent = 'no open position to move a stop for';
                return;
            }
            act('/api/atlas/replay/paper/exits', { stop_loss: pos.entry_price, take_profit: num('ppxTp') },
                'moving the stop to entry');
        };
        if ((b = $('ppxClear'))) b.onclick = function () {
            act('/api/atlas/replay/paper/exits', { stop_loss: null, take_profit: null }, 'clearing exits');
        };
        if ((b = $('ppExport'))) b.onclick = function () { act('/api/atlas/replay/paper/export', {}, 'exporting the ledger'); };
        if ((b = $('ldCancelAll'))) b.onclick = function () { act('/api/atlas/replay/paper/cancel', {}, 'cancelling'); };
        if ((b = $('stripBuy'))) b.onclick = function () { order('buy', 'stripResult'); };
        if ((b = $('stripSell'))) b.onclick = function () { order('sell', 'stripResult'); };
        if ((b = $('stripFlatten'))) b.onclick = function () { act('/api/atlas/replay/paper/flatten', {}, 'flattening', 'stripResult'); };
        if ((b = $('stripLock'))) b.onclick = function () { setLocked(!locked); };
        if ((b = $('stripSize'))) b.oninput = function () {
            var t = $('ppSize');
            if (t && t.value !== this.value) t.value = this.value;   // one size everywhere
        };
        ['ppSl', 'ppTp'].forEach(function (id) {
            var el = $(id);
            if (el && el.addEventListener) el.addEventListener('input', paintRisk);
        });
        /* T3: the order keys exist, are armed-gated, and only act on this view mid-session. */
        if (window.OFAPKEYS) {
            var gate = function () { return onScreen() && runningNow && !locked; };
            OFAPKEYS.bind({ id: 'paper-buy', keys: ['alt+b'], scope: 'Replay', danger: true,
                label: 'paper: buy at market (needs armed order keys)', when: gate, why: 'needs a running paper session, Replay or Chart showing, unlocked',
                run: function () { order('buy'); } });
            OFAPKEYS.bind({ id: 'paper-sell', keys: ['alt+s'], scope: 'Replay', danger: true,
                label: 'paper: sell at market (needs armed order keys)', when: gate, why: 'needs a running paper session, Replay or Chart showing, unlocked',
                run: function () { order('sell'); } });
            OFAPKEYS.bind({ id: 'paper-flatten', keys: ['alt+x'], scope: 'Replay', danger: true,
                label: 'paper: flatten the position (needs armed order keys)', when: gate, why: 'needs a running paper session, Replay or Chart showing, unlocked',
                run: function () { act('/api/atlas/replay/paper/flatten', {}, 'flattening'); } });
        }
        if (window.api) {
            window.api('/api/control/config').then(function (cfg) {
                locked = Boolean(cfg && cfg.ui && cfg.ui.paper_lock);
                paintLock();
            }).catch(function () { /* unlocked by default */ });
        }
        var wrap = window.showView;
        if (typeof wrap === 'function' && !wrap.__ofapWrapped_paper) {
            var wrapped = function (name) {
                var out = wrap.apply(this, arguments);
                if (name === 'replay' || name === 'chart') setTimeout(function () { if (onScreen()) load(); }, 400);
                return out;
            };
            wrapped.__ofapWrapped_paper = true;
            window.showView = wrapped;
        }
        timer = setInterval(function () { if (onScreen()) load(); }, POLL_MS);
        setTimeout(function () { if (onScreen()) load(); }, 1500);
    }

    window.OFAPPAPER = { load: load, state: null, paintRisk: paintRisk,
        locked: function () { return locked; }, setLocked: setLocked };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
