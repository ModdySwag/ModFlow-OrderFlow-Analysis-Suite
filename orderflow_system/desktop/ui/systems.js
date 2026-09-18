/* systems.js — the Systems board's model (§86), pure.
 *
 * The server's `GET /api/control/systems` sends plain rows: {id, name, state, detail, view} with
 * `state` from the closed set below, plus `optional` rows for capabilities this install does not
 * use yet. This module turns that into the tiles the Overview card paints and the score it
 * announces — nothing here touches the page or the network, so `systems.selftest.js` pins it.
 *
 * Why it exists: a user who adds a bridge, keys or a licence asks one question first — "are the
 * systems 100%?" — and the answer used to be spread across the wizard, the Platforms cards and a
 * status bar. The board answers it at a glance, and the scale stays honest: rows the install
 * *expects* count towards the score; capabilities it has simply not set up stay apart, greyed.
 */
(function () {
    'use strict';

    var VERSION = '1.0.0';

    /* state → chip text + the paint kind the tag classes carry (ok | dim | no | err) */
    var STATES = {
        live:  { text: '\u25cf live',  kind: 'ok' },
        ready: { text: '\u25ce ready', kind: 'dim' },
        off:   { text: '\u25cb off',   kind: 'no' },
        error: { text: '\u26a0 error', kind: 'err' },
    };

    function payloadOf(p) { return (p && typeof p === 'object') ? p : {}; }

    function stateOf(state) {
        var s = String(state || 'off');
        return STATES[s] ? s : 'off';
    }

    function tile(row, optional) {
        var r = (row && typeof row === 'object') ? row : {};
        var state = stateOf(r.state);
        return {
            id: String(r.id || ''),
            name: String(r.name || r.id || 'system'),
            state: state,
            text: STATES[state].text,
            kind: STATES[state].kind,
            detail: String(r.detail || ''),
            view: String(r.view || ''),
            optional: !!optional,
        };
    }

    /* rows first (the systems in play), then the untouched capabilities */
    function tiles(payload) {
        var p = payloadOf(payload);
        var out = [];
        (Array.isArray(p.rows) ? p.rows : []).forEach(function (r) { out.push(tile(r, false)); });
        (Array.isArray(p.optional) ? p.optional : []).forEach(function (r) { out.push(tile(r, true)); });
        return out;
    }

    /* the score counts the systems in play only — optional capabilities never dilute it */
    function score(payload) {
        var p = payloadOf(payload);
        var rows = Array.isArray(p.rows) ? p.rows : [];
        var live = rows.filter(function (r) { return stateOf(r && r.state) === 'live'; }).length;
        var total = rows.length;
        return { live: live, total: total, percent: total ? Math.round(100 * live / total) : 0 };
    }

    function summary(payload) {
        var s = score(payload);
        var cells = tiles(payload);
        var attention = cells.filter(function (t) { return !t.optional && (t.state === 'off' || t.state === 'error'); });
        return { live: s.live, total: s.total, percent: s.percent,
            line: s.live + ' of ' + s.total + ' systems live \u2014 ' + s.percent + '%',
            attention: attention.length };
    }

    var API = { version: VERSION, STATES: STATES, tiles: tiles, score: score, summary: summary };

    if (typeof window !== 'undefined') window.OFAPSYSTEMS = API;
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
