/* instrument.js — the Engine panel's instrument look-up (§82), as pure functions.
 *
 * The server answers what a typed symbol IS (`GET /api/control/instruments/resolve`: state,
 * reason, suggestions, actions). This module turns that answer into the three things the panel
 * paints — a state chip, suggestion rows, an action button — and nothing else: no DOM, no fetch.
 * `instrument.selftest.js` pins every decision under Node; `ofx-view.js` stays the only place
 * that touches the page or the network.
 *
 * The action vocabulary is closed and mirrors `desktop/instrument_lookup.py`'s ACTIONS: a
 * server that invented an action would be drawn as nothing rather than as a dead button, and
 * `test_instrument_api.py` keeps the Python side honest about which actions exist.
 *
 * Why it exists: the panel's symbol box used to accept any string silently. The states below
 * are the difference between "the market name you typed is this row, switch it on" and
 * "nothing here can stream that" — a sentence, not a blank stage.
 */
(function () {
    'use strict';

    var VERSION = '1.0.0';

    /* state → chip text + the paint class (ok | dim | warn | bad) */
    var STATES = {
        live:        { text: '● streaming',           kind: 'ok' },
        ready:       { text: '◎ enabled',             kind: 'dim' },
        disabled:    { text: '◌ not enabled',         kind: 'warn' },
        available:   { text: '＋ available',          kind: 'warn' },
        unsupported: { text: '⚠ not on this source',  kind: 'bad' },
        unknown:     { text: '? unknown',             kind: 'bad' },
    };

    var ACTIONS = ['use', 'start_engine', 'enable', 'add', 'map_broker', 'open_instruments'];

    /* the button a user sees, per action */
    var LABELS = {
        use: 'Use this instrument',
        start_engine: 'Start the engine',
        enable: 'Enable & restart',
        add: 'Add & restart',
        map_broker: 'Map the broker symbol',
        open_instruments: 'Open Instruments',
    };

    /* preference order for the emphasised button; the first present action wins */
    var ORDER = ['use', 'enable', 'add', 'start_engine', 'map_broker', 'open_instruments'];

    /* Actions that only mean something after the engine is rebuilt: the panel restarts a
       running engine once the config write lands, and a stopped one simply starts later. */
    var RESTART_ACTIONS = { enable: true, add: true };

    function payloadOf(p) { return (p && typeof p === 'object') ? p : {}; }

    function stateOf(p) {
        var state = String(payloadOf(p).state || 'unknown');
        return STATES[state] ? state : 'unknown';
    }

    function chip(p) {
        var state = stateOf(p);
        var spec = STATES[state];
        var data = payloadOf(p);
        var symbol = String(data.symbol || data.query || '');
        var text = spec.text;
        if (state === 'live' && data.via === 'alias' && symbol) text = '● streaming · ' + symbol;
        return { state: state, text: text, kind: spec.kind, symbol: symbol };
    }

    /* The one-line explanation: the server's own reason, plus the alias hop when there was one.
       Never invents text — an empty reason stays empty rather than becoming "unknown error". */
    function title(p) {
        var data = payloadOf(p);
        var reason = String(data.reason || '');
        var bits = [];
        if (String(data.query || '') && String(data.symbol || '') &&
            String(data.query).toUpperCase() !== String(data.symbol).toUpperCase()) {
            bits.push(String(data.query) + ' → ' + String(data.symbol));
        }
        if (reason) bits.push(reason);
        return bits.join(' — ');
    }

    /* What the panel's reason line shows. `title` alone is empty for a healthy, exact-match
       symbol — and an empty line under a "streaming" chip reads as a missing answer (measured
       live), so every state gets a sentence of its own here. */
    function panelText(p) {
        var direct = title(p);
        var data = payloadOf(p);
        var hint = String(data.hint || '');
        if (!direct) {
            var symbol = String(data.symbol || data.query || '');
            var state = stateOf(p);
            var source = String(data.source || '');
            if (state === 'live') {
                direct = (symbol || 'this instrument') + ' is streaming'
                    + (source ? ' from ' + source : '') + '.';
            } else if (state === 'ready') {
                direct = (symbol || 'this instrument') + ' is enabled — the engine is stopped.';
            } else if (!symbol) {
                direct = 'type an instrument name';
            } else {
                direct = emptyNote(p);
            }
        }
        return hint ? direct + ' · ' + hint : direct;
    }

    function actions(p) {
        var data = payloadOf(p);
        var list = Array.isArray(data.actions) ? data.actions : [];
        var known = list.filter(function (a) { return ACTIONS.indexOf(a) >= 0; });
        var ordered = ORDER.filter(function (a) { return known.indexOf(a) >= 0; });
        return ordered.map(function (a, i) {
            return { action: a, label: LABELS[a], primary: i === 0, restarts: !!RESTART_ACTIONS[a] };
        });
    }

    function primary(p) {
        var list = actions(p);
        return list.length ? list[0].action : '';
    }

    /* Suggestion rows: the server's ranked matches, cleaned for display. A row says WHAT it is
       (class + why it matched) and whether it is already streaming, so the list can be read
       without clicking. */
    function rows(p, limit) {
        var data = payloadOf(p);
        var list = Array.isArray(data.suggestions) ? data.suggestions : [];
        var cap = Number(limit) > 0 ? Number(limit) : 6;
        return list.slice(0, cap).map(function (row) {
            var note = String((row && row.note) || '');
            var cls = String((row && row.asset_class) || '');
            var meta = [cls, note && note !== cls ? note : ''].filter(Boolean).join(' · ');
            return {
                symbol: String((row && row.symbol) || ''),
                meta: meta,
                enabled: !!(row && row.enabled),
                streaming: !!(row && row.streaming),
                action: (row && row.streaming) ? 'use' : 'enable',
            };
        }).filter(function (row) { return !!row.symbol; });
    }

    /* The Engine symbol box's quick picker (§85): every configured instrument — streaming first,
       then the enabled ones, then the ones switched off — each option labelled with its own state
       so the list reads before choosing. `streaming` is the engine's own status list; everything
       else comes from the config. Pure, so the selftest pins the grouping. */
    function pickerRows(payload) {
        var data = payloadOf(payload);
        var list = Array.isArray(data.instruments) ? data.instruments : [];
        var streaming = Array.isArray(data.streaming) ? data.streaming.map(function (s) {
            return String(s || '').toUpperCase();
        }) : [];
        var groups = [['streaming', 'streaming now'], ['enabled', 'enabled'], ['off', 'configured — off']];
        var seen = {};
        var out = [];
        groups.forEach(function (spec) {
            list.forEach(function (row) {
                if (!row || !row.symbol) return;
                var symbol = String(row.symbol);
                if (seen[symbol]) return;
                var state = streaming.indexOf(symbol.toUpperCase()) >= 0 ? 'streaming'
                    : (row.enabled ? 'enabled' : 'off');
                if (state !== spec[0]) return;
                seen[symbol] = true;
                out.push({ group: spec[1], value: symbol, state: state,
                    label: symbol + (row.asset_class ? ' — ' + row.asset_class : '') });
            });
        });
        return out;
    }

    /* The NinjaTrader probe boxes (Platforms ▸ bridge, and the wizard's test row) accept a name
       the TERMINAL lists — NQ, ES, MNQ 12-26 — which cannot be read offline. What the app does
       know is the mapping it already holds: a row added from the NinjaTrader lane stamps its
       `ninjatrader_symbol`. Those names are the options; an empty list (nothing mapped yet) is
       the honest answer, and typing stays open because the terminal's list is the authority. */
    function ninjatraderNames(instruments) {
        var list = Array.isArray(instruments) ? instruments : [];
        var out = [];
        var seen = {};
        list.forEach(function (row) {
            var name = row && row.ninjatrader_symbol ? String(row.ninjatrader_symbol).trim() : '';
            if (!name || seen[name.toLowerCase()]) return;
            seen[name.toLowerCase()] = true;
            out.push(name);
        });
        return out;
    }

    /* The note the stage carries when nothing is drawn: the reason, or an explicit fallback so
       a blank canvas is never wordless. */
    function emptyNote(p) {
        var data = payloadOf(p);
        var symbol = String(data.symbol || data.query || '');
        var reason = String(data.reason || '');
        if (reason) return reason;
        if (symbol) return symbol + ' has no data for this source yet.';
        return 'type an instrument name';
    }

    var API = { version: VERSION, STATES: STATES, ACTIONS: ACTIONS, LABELS: LABELS, ORDER: ORDER,
        chip: chip, title: title, actions: actions, primary: primary, rows: rows, state: stateOf,
        emptyNote: emptyNote, panelText: panelText, pickerRows: pickerRows,
        ninjatraderNames: ninjatraderNames };

    if (typeof window !== 'undefined') window.OFAPINSTRUMENT = API;
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
