/* risk.js — T13/B11: the consequence read-out.
 *
 * Pure maths + one context slot. paper.js hands it the account's own position and mark on every
 * poll; anything hovering or dragging a price can then ask what that price would mean IN THE
 * ACCOUNT'S UNIT — ticks. With a position open the number IS the paper P/L at that price (never a
 * fill, never a prediction); with none it is honestly a distance, labelled as one.
 */
(function (root) {
    'use strict';

    const state = { ctx: null };

    function setContext(ctx) { state.ctx = (ctx && typeof ctx === 'object') ? ctx : null; }
    function context() { return state.ctx; }

    function fmt(n) {
        const v = Math.round(Number(n) * 10) / 10;
        return (v > 0 ? '+' : '') + v.toFixed(1);
    }

    /* The consequence of `price` for the account. has=false when there is nothing honest to say. */
    function verdict(price, ctx) {
        const px = Number(price);
        const c = ctx || state.ctx || null;
        if (!isFinite(px) || !c) return { has: false };
        const tick = Number(c.tick) > 0 ? Number(c.tick) : 0.01;
        const pos = c.position || { side: 'flat', size: 0, entry_price: 0 };
        if (pos.side && pos.side !== 'flat' && Number(pos.size) > 0 && Number(pos.entry_price) > 0) {
            const dir = pos.side === 'short' ? -1 : 1;
            const perUnit = ((px - Number(pos.entry_price)) / tick) * dir;
            return { has: true, kind: 'pl', side: pos.side, size: Number(pos.size),
                ticks: perUnit, perUnit: perUnit, total: perUnit * Number(pos.size) };
        }
        const mark = Number(c.last || 0);
        if (!mark) return { has: false };
        return { has: true, kind: 'distance', ticks: (px - mark) / tick, perUnit: (px - mark) / tick, total: 0 };
    }

    function text(price, ctx) {
        const v = verdict(price, ctx);
        if (!v.has) return '';
        if (v.kind === 'pl') {
            return 'paper at this price: ' + fmt(v.perUnit) + ' ticks/unit · ' + fmt(v.total) +
                ' total (size ' + v.size + ')';
        }
        return fmt(v.ticks) + ' ticks ' + (v.ticks >= 0 ? 'above' : 'below') + ' the mark (no position — a distance)';
    }

    root.OFAPRISK = { setContext: setContext, context: context, verdict: verdict, text: text, fmt: fmt };
})(typeof globalThis !== 'undefined' ? globalThis : this);
