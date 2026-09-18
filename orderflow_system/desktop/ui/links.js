/* links.js — symbol and timeframe link groups (A-D) for the terminal's widgets.
 *
 * The widget-terminal convention: panels join a group, and changing that group's symbol once moves
 * every member while the panels that did not join stay exactly where they are.
 *
 * Two halves, deliberately split:
 *   - MEMBERSHIP is stored state: each widget's `link` field in the layout ("<symbol>/<timeframe>",
 *     A-D, either side optional), sanitised by the config store and read back through the shell. It
 *     survives a reload because it is part of the arrangement.
 *   - What a group MEANS (its symbol, its timeframe) is runtime state seeded from the panels that are
 *     already on screen — the panels' own controls are the only place those values really live, and a
 *     group whose members all show BTCUSDT is a BTCUSDT group whether or not anyone wrote it down.
 *
 * The panels are the authority for what they can accept:
 *   - the Engine view has its own symbol select (#ofxSymbol);
 *   - every other panel follows the app's instrument select (#symbolSelect) — one engine symbol, so a
 *     change there is ONE change, however many widgets follow it;
 *   - the chart is the only panel with a timeframe control (#tfSelect).
 * Values reach those controls through the app's own change paths (set `.value`, dispatch `change`),
 * guarded by `state.applying` so the feedback listeners cannot bounce a value straight back.
 */
(function () {
    'use strict';

    const GROUPS = ['A', 'B', 'C', 'D'];
    /* T11/B17: group colours — the colour NEVER carries meaning alone; every badge also shows
       the group letter (the CVD rule), and the cycle below is the palette users step through. */
    const FALLBACK_COLORS = { A: '#6ec1ff', B: '#ffb454', C: '#7fe0a8', D: '#d49bff' };
    const COLOR_CYCLE = ['#6ec1ff', '#ffb454', '#7fe0a8', '#d49bff', '#ff8fa3', '#c3a6ff'];
    const SYMBOL_CONTROL = { ofx: 'ofxSymbol' };              // panels with their own symbol select
    const GLOBAL_SYMBOL = 'symbolSelect';                     // the app's instrument select
    const TIMEFRAME_CONTROL = { chart: 'tfSelect' };          // the only panel with a timeframe control
    const TF_LABEL = { '60': '1m', '300': '5m', '900': '15m', '3600': '1H', '14400': '4H', '86400': '1D' };
    const hasDom = typeof document !== 'undefined' && !!document.createElement;

    const state = { groups: {}, applying: false, applied: 0, sweeps: 0, refused: [], last: '' };

    function shellApi() { return (typeof window !== 'undefined' && window.OFAPSHELL) || null; }
    function configColors() {
        const cfg = (typeof S !== 'undefined' && S && S.config && S.config.ui && S.config.ui.link_colors) || null;
        return (cfg && typeof cfg === 'object') ? cfg : null;
    }
    /* The colour of a group: the config’s own value, else the shipped fallback, else nothing. */
    function colorOf(group) {
        const g = String(group || '').toUpperCase();
        const fromCfg = configColors();
        return (fromCfg && fromCfg[g]) || FALLBACK_COLORS[g] || '';
    }
    /* Pure: the next colour in the cycle (wrapping), for the swatch buttons. */
    function nextColor(current) {
        const at = COLOR_CYCLE.indexOf(String(current || '').toLowerCase());
        return COLOR_CYCLE[(at + 1) % COLOR_CYCLE.length];
    }
    function repaintChips() {
        const api = shellApi();
        if (api && typeof api.paintLinkChip === 'function') {
            members().forEach(function (row) { api.paintLinkChip(row.view); });
        }
    }
    /* Write a group’s colour: the in-page config copy first (so this session agrees), then the
       event — the SHELL owns the store patch, so this module never reaches the network (the same
       rule the membership follows). Every member’s chip repaints and other surfaces follow suit. */
    function setColor(group, hex) {
        const g = String(group || '').toUpperCase();
        if (GROUPS.indexOf(g) < 0) return null;
        const clean = /^#[0-9a-fA-F]{6}$/.test(String(hex || '')) ? String(hex) : FALLBACK_COLORS[g];
        const cfg = (typeof S !== 'undefined' && S && S.config) || null;
        if (cfg) {
            cfg.ui = cfg.ui || {};
            const merged = Object.assign({}, FALLBACK_COLORS, cfg.ui.link_colors || {});
            merged[g] = clean;
            cfg.ui.link_colors = merged;
        }
        repaintChips();
        if (hasDom) document.dispatchEvent(new CustomEvent('ofap:link-colors', { detail: { group: g, color: clean } }));
        return clean;
    }
    function cycleColor(group) {
        return setColor(group, nextColor(colorOf(group)));
    }
    function el(id) { return hasDom ? document.getElementById(id) : null; }
    function kindControl(kind, view) {
        return kind === 'sym' ? (SYMBOL_CONTROL[view] || GLOBAL_SYMBOL) : (TIMEFRAME_CONTROL[view] || '');
    }

    function blank() {
        const out = {};
        GROUPS.forEach(function (group) { out[group] = { symbol: '', timeframe: '' }; });
        return out;
    }

    function tfLabel(value) {
        return TF_LABEL[String(value || '')] || (value ? String(value) : '');
    }

    /* The decision, as data — no DOM, so the self-test can pin it. Every member of THIS group on THIS
       kind gets a row (so a report can name them all); members of another group and panels that never
       joined get nothing. `applyValue` collapses the rows onto the controls they actually share,
       because the app has one engine symbol and one chart timeframe however many widgets follow them. */
    function plan(kind, groupId, value, members) {
        const rows = [];
        (members || []).forEach(function (member) {
            if (!groupId || !member[kind] || member[kind] !== groupId) return;
            const control = kindControl(kind, member.view);
            if (!control) return;
            rows.push({ view: member.view, control: control, value: String(value) });
        });
        return rows;
    }

    /* The controls a plan touches, in order, each once. */
    function controlsOf(rows) {
        const seen = Object.create(null);
        return (rows || []).filter(function (row) {
            if (!row || !row.control || seen[row.control]) return false;
            seen[row.control] = true;
            return true;
        });
    }

    function members() {
        const api = shellApi();
        return api && typeof api.linkMembers === 'function' ? api.linkMembers() : [];
    }

    function groups() {
        const out = {};
        GROUPS.forEach(function (group) {
            out[group] = {
                symbol: state.groups[group].symbol,
                timeframe: state.groups[group].timeframe,
                members: members().filter(function (row) {
                    return row.sym === group || row.tf === group;
                }).map(function (row) { return row.view; }),
            };
        });
        return out;
    }

    /* Push a group's value into the controls its members use, through the app's own change path. */
    function applyValue(kind, groupId, value, opts) {
        opts = opts || {};
        const rows = plan(kind, groupId, value, members());
        const touched = [];
        const refused = [];
        state.applying = true;
        try {
            controlsOf(rows).forEach(function (row) {
                const control = el(row.control);
                if (!control || String(control.value) === row.value) return;
                const before = String(control.value);
                control.value = row.value;
                /* A select only holds what it offers: if the value did not stick (an instrument this
                   installation does not list) the control goes back to what it held and nothing is
                   dispatched — a blank symbol is worse than a symbol that stayed put. */
                if (String(control.value) !== row.value) {
                    control.value = before;
                    refused.push({ control: row.control, value: row.value });
                    return;
                }
                control.dispatchEvent(new Event('change', { bubbles: true }));
                touched.push(row.control);
            });
        } finally {
            state.applying = false;
        }
        state.refused = refused;
        if (refused.length) {
            state.last = kind + ' ' + groupId + ' → ' + value + ': ' + refused.length + ' control(s) refused it';
        }
        if (touched.length) {
            state.applied += touched.length;
            state.last = kind + ' ' + groupId + ' → ' + value + ' (' + touched.join(', ') + ')';
            if (!opts.quiet && hasDom) {
                document.dispatchEvent(new CustomEvent('ofap:linked', { detail: { kind: kind, group: groupId, value: value, controls: touched, refused: refused } }));
            }
        }
        return touched;
    }

    function setGroup(kind, groupId, value, opts) {
        if (GROUPS.indexOf(groupId) < 0) return false;
        state.groups[groupId][kind === 'sym' ? 'symbol' : 'timeframe'] = String(value || '');
        applyValue(kind, groupId, value, opts);
        return true;
    }

    /* What a panel currently shows, for seeding a group that has no value yet. */
    function panelValue(kind, view) {
        const control = el(kindControl(kind, view));
        return control ? String(control.value || '') : '';
    }

    function seedGroups() {
        const rows = members();
        GROUPS.forEach(function (group) {
            ['sym', 'tf'].forEach(function (kind) {
                const key = kind === 'sym' ? 'symbol' : 'timeframe';
                if (state.groups[group][key]) return;
                const holder = rows.filter(function (row) { return row[kind] === group; })[0];
                if (!holder) return;
                const value = panelValue(kind, holder.view);
                if (value) state.groups[group][key] = value;
            });
        });
        return state.groups;
    }

    /* Re-read membership and make the screen agree with it: a widget that just joined a group adopts
       that group's values immediately, and nothing else moves. */
    function sweep(reason) {
        state.sweeps += 1;
        seedGroups();
        const rows = members();
        const touched = [];
        GROUPS.forEach(function (group) {
            ['sym', 'tf'].forEach(function (kind) {
                const key = kind === 'sym' ? 'symbol' : 'timeframe';
                const value = state.groups[group][key];
                if (!value) return;
                if (!rows.some(function (row) { return row[kind] === group; })) return;
                touched.push.apply(touched, applyValue(kind, group, value, { quiet: true }));
            });
        });
        const api = shellApi();
        if (api && typeof api.paintLinkChip === 'function') {
            rows.forEach(function (row) { api.paintLinkChip(row.view); });
        }
        state.last = touched.length ? (reason || 'sweep') + ': ' + touched.length + ' control(s)' : (reason || 'sweep') + ': nothing to move';
        return touched;
    }

    /* Panels feed back: changing the app's instrument moves every group linked to it; a panel with its
       own control moves only its own group. The `applying` guard stops our own writes bouncing back. */
    function watch() {
        if (!hasDom) return false;
        const global = el(GLOBAL_SYMBOL);
        if (global) {
            global.addEventListener('change', function () {
                if (state.applying) return;
                const value = String(global.value || '');
                const rows = members();
                GROUPS.forEach(function (group) {
                    const linked = rows.some(function (row) { return row.sym === group && !SYMBOL_CONTROL[row.view]; });
                    if (linked) setGroup('sym', group, value, { from: 'panel' });
                });
            });
        }
        Object.keys(SYMBOL_CONTROL).forEach(function (view) {
            const control = el(SYMBOL_CONTROL[view]);
            if (!control) return;
            control.addEventListener('change', function () {
                if (state.applying) return;
                const api = shellApi();
                const spec = api && typeof api.linkSpec === 'function' ? api.linkSpec(view) : { sym: '', tf: '' };
                if (spec.sym) setGroup('sym', spec.sym, String(control.value || ''), { from: 'panel' });
            });
        });
        Object.keys(TIMEFRAME_CONTROL).forEach(function (view) {
            const control = el(TIMEFRAME_CONTROL[view]);
            if (!control) return;
            control.addEventListener('change', function () {
                if (state.applying) return;
                const api = shellApi();
                const spec = api && typeof api.linkSpec === 'function' ? api.linkSpec(view) : { sym: '', tf: '' };
                if (spec.tf) setGroup('tf', spec.tf, String(control.value || ''), { from: 'panel' });
            });
        });
        document.addEventListener('ofap:links', function () { sweep('membership'); });
        document.addEventListener('ofap:shell', function () { sweep('shell'); });
        return true;
    }

    state.groups = blank();

    if (hasDom) {
        const start = function () { watch(); sweep('boot'); };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
        else start();
    }

    window.OFAPLINKS = {
        GROUPS: GROUPS,
        FALLBACK_COLORS: FALLBACK_COLORS,
        COLOR_CYCLE: COLOR_CYCLE,
        colorOf: colorOf,
        nextColor: nextColor,
        setColor: setColor,
        cycleColor: cycleColor,
        SYMBOL_CONTROL: SYMBOL_CONTROL,
        GLOBAL_SYMBOL: GLOBAL_SYMBOL,
        TIMEFRAME_CONTROL: TIMEFRAME_CONTROL,
        plan: plan,
        controlsOf: controlsOf,
        groups: groups,
        members: members,
        setGroup: setGroup,
        apply: applyValue,
        seed: seedGroups,
        sweep: sweep,
        tfLabel: tfLabel,
        state: function () {
            return { groups: groups(), applying: state.applying, applied: state.applied,
                     refused: state.refused.slice(), sweeps: state.sweeps, last: state.last };
        },
    };
})();
