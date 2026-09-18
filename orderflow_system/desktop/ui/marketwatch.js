/* Market watch (§87) — the source's own board as a small, pure table model: symbol, bid, ask,
   daily change with the MT5-style slanted arrows. No DOM here, so the node selftest can pin the
   formatting rules (the numbers on screen are the numbers the venues sent, only formatted). */
(function () {
    'use strict';

    var UP = '\u2197', DOWN = '\u2198', FLAT = '\u00b7', NONE = '\u2014';

    /* 1.14776 (FX five-), 155.944 / 219.01 (three-, trailing zero trimmed), 29440.70 (two-),
       0.57326 (sub-one five-). The terminal's own conventions, matched by magnitude. */
    function priceText(value) {
        var v = Number(value);
        if (!isFinite(v) || v === 0) return NONE;
        var digits = Math.abs(v) >= 1000 ? 2 : (Math.abs(v) >= 10 ? 3 : 5);
        var text = v.toFixed(digits);
        if (text.indexOf('.') >= 0) {
            while (text.length > 1 && text.charAt(text.length - 1) === '0'
                   && text.split('.')[1].length > 2) text = text.slice(0, -1);
        }
        return text;
    }

    function pctText(pct) {
        var v = Number(pct) || 0;
        return v.toFixed(2) + '%';
    }

    function sideClass(pct) {
        var v = Number(pct) || 0;
        return v > 0.0001 ? 'up' : (v < -0.0001 ? 'down' : '');
    }

    function arrow(pct) {
        var v = Number(pct) || 0;
        return v > 0.0001 ? UP : (v < -0.0001 ? DOWN : FLAT);
    }

    function rowModel(row) {
        row = row || {};
        var pct = Number(row.change_pct) || 0;
        var quoted = row.quoted !== false && (Number(row.bid) || Number(row.ask) || Number(row.last));
        return {
            symbol: String(row.symbol || ''),
            bid: quoted ? priceText(row.bid) : NONE,
            ask: quoted ? priceText(row.ask) : NONE,
            change: pctText(pct),
            cls: sideClass(pct),
            arrow: arrow(pct),
        };
    }

    /* The last-move direction of a price — the green/red tint, MT5's own market-watch habit.
       Only two readable, non-equal numbers tint; unquoted rows and first paints never do. */
    function bidDir(prevText, text) {
        var clean = function (v) { return String(v == null ? '' : v).replace(/[^0-9.\-]/g, ''); };
        var a = Number(clean(prevText));
        var b = Number(clean(text));
        if (!isFinite(a) || !isFinite(b) || a === 0 || b === 0 || a === b) return '';
        return b > a ? 'up' : 'down';
    }

    function rows(payload) {
        return ((payload && payload.rows) || []).map(rowModel);
    }

    var API = { priceText: priceText, pctText: pctText, sideClass: sideClass, arrow: arrow,
                rowModel: rowModel, rows: rows, bidDir: bidDir };
    if (typeof window !== 'undefined') window.OFAPMW = API;
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
