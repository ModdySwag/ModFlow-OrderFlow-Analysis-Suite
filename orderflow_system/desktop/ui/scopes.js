/* scopes.js — T12/B9: per-instrument display settings.
 *
 * The dials in SCOPED follow the instrument: when the app's instrument changes, the values the
 * user is leaving are remembered under that instrument, and the values remembered for the one
 * being opened are applied through the same params gate every control writes through (so nothing
 * can appear in a scope that a control could not have set). An instrument with no remembered
 * block keeps whatever is on screen — last-used wins for a new instrument, which is exactly the
 * shipped behaviour with none of the bookkeeping.
 *
 * The pure half (capture / planApply / cleanSymbol) has no DOM and is pinned by scopes.selftest.js;
 * the DOM half wires #symbolSelect (the app's instrument control — the Engine's own select follows
 * it through the links module, not here) and listens for the heat-scheme broadcast so dial tweaks
 * land in the current instrument's block too.
 */
(function () {
    'use strict';

    const SCOPED = [
        'ofx.heat_contrast', 'ofx.heat_floor', 'ofx.heat_floor_pct', 'ofx.heat_smooth', 'ofx.ramp',
        'ofx.heat_dim', 'ofx.heat_highlight',
        'atlas.ofx.degrade',
        'atlas.heatmap.upper_cutoff_pct', 'atlas.heatmap.upper_cutoff_abs', 'atlas.heatmap.contrast',
        'atlas.heatmap.floor', 'atlas.heatmap.floor_pct', 'atlas.heatmap.smooth',
        'atlas.heatmap.dim', 'atlas.heatmap.highlight',
    ];
    const MAX_INSTRUMENTS = 40;
    const hasDom = typeof document !== 'undefined' && !!document.createElement;

    const state = { symbol: '', applied: 0, saved: 0, last: '' };
    let saveTimer = 0;

    function el(id) { return hasDom ? document.getElementById(id) : null; }
    function cfgRoot() { return (typeof S !== 'undefined' && S && S.config) || null; }
    function rpm() { return (typeof window !== 'undefined' && window.OFAPRAMP) || null; }

    /* The instrument the app is on (the one control that owns it). */
    function currentSymbol() {
        const sel = el('symbolSelect');
        const value = sel ? String(sel.value || '') : '';
        return value || ((typeof S !== 'undefined' && S && S.symbol) || '');
    }

    function cleanSymbol(sym) {
        const s = String(sym || '').trim().toUpperCase();
        if (!s || s.length > 24 || !/^[A-Z0-9._/-]+$/.test(s)) return '';
        return s;
    }

    /* Pure: the current values of `paths` under `cfg` (undefined ones are skipped, so a scope
       never remembers a path that does not exist yet). */
    function capture(cfg, paths) {
        const RP = rpm();
        const getIn = (RP && RP.getIn) || function (root, path) {
            let cur = root;
            const parts = String(path || '').split('.');
            for (let i = 0; i < parts.length; i += 1) {
                if (!cur || typeof cur !== 'object' || !(parts[i] in cur)) return undefined;
                cur = cur[parts[i]];
            }
            return cur;
        };
        const out = {};
        (paths || []).forEach(function (path) {
            const value = getIn(cfg, path);
            if (value !== undefined) out[path] = value;
        });
        return out;
    }

    /* Pure: a remembered block reduced to the paths the app may still write — unknown or
       hand-edited keys never reach a control. */
    function planApply(block) {
        const rows = [];
        (SCOPED).forEach(function (path) {
            if (block && Object.prototype.hasOwnProperty.call(block, path)) {
                rows.push({ path: path, value: block[path] });
            }
        });
        return rows;
    }

    function blockFor(symbol) {
        const cfg = cfgRoot();
        const scopes = (cfg && cfg.ui && cfg.ui.instrument_scopes) || {};
        return scopes[symbol] || null;
    }

    /* Persist the whole scopes map (full-map merge keeps the other instruments intact). */
    function persist(cfg) {
        if (typeof api !== 'function') return;
        const scopes = (cfg && cfg.ui && cfg.ui.instrument_scopes) || {};
        const capped = {};
        Object.keys(scopes).slice(0, MAX_INSTRUMENTS).forEach(function (k) { capped[k] = scopes[k]; });
        void api('/api/control/config', { method: 'POST', body: { ui: { instrument_scopes: capped } } })
            .catch(function () { /* the in-page copy still holds for this session */ });
    }

    /* Remember the values on screen under `symbol` (no-op when the instrument is not known). */
    function saveFor(symbol) {
        const sym = cleanSymbol(symbol);
        const cfg = cfgRoot();
        if (!sym || !cfg) return false;
        const captured = capture(cfg, SCOPED);
        if (!Object.keys(captured).length) return false;
        cfg.ui = cfg.ui || {};
        const scopes = Object.assign({}, cfg.ui.instrument_scopes || {});
        scopes[sym] = captured;
        cfg.ui.instrument_scopes = scopes;
        persist(cfg);
        state.saved += 1;
        state.last = sym + ': ' + Object.keys(captured).length + ' setting(s) remembered';
        return true;
    }

    /* Apply the remembered block for `symbol`, if one exists. Returns the rows applied. */
    async function applyBlock(symbol) {
        const sym = cleanSymbol(symbol);
        if (!sym) return [];
        const block = blockFor(sym);
        if (!block) { state.last = sym + ': nothing remembered — the on-screen values stay'; return []; }
        const rows = planApply(block);
        const RP = rpm();
        const cfg = cfgRoot();
        for (let i = 0; i < rows.length; i += 1) {
            if (RP && RP.writeParam) await RP.writeParam(rows[i].path, rows[i].value, cfg, null);
        }
        state.applied += 1;
        state.last = sym + ': ' + rows.length + ' setting(s) applied';
        if (hasDom) {
            document.dispatchEvent(new CustomEvent('ofap:scopes', { detail: { symbol: sym, rows: rows } }));
        }
        return rows;
    }

    /* The instrument changed: remember what the old one wore, then dress the new one. */
    async function applyFor(symbol) {
        const sym = cleanSymbol(symbol);
        if (!sym || sym === state.symbol) return false;
        const older = state.symbol;
        state.symbol = sym;
        if (older) saveFor(older);
        await applyBlock(sym);
        return true;
    }

    function forget(symbol) {
        const sym = cleanSymbol(symbol);
        const cfg = cfgRoot();
        if (!sym || !cfg || !cfg.ui || !cfg.ui.instrument_scopes) return false;
        if (!(sym in cfg.ui.instrument_scopes)) return false;
        delete cfg.ui.instrument_scopes[sym];
        persist(cfg);
        state.last = sym + ': remembered settings dropped';
        if (hasDom) document.dispatchEvent(new CustomEvent('ofap:scopes', { detail: { symbol: sym, rows: [], forgot: true } }));
        return true;
    }

    /* The palette command: forget whatever the instrument on screen is called. */
    function forgetCurrent() {
        const sym = currentSymbol();
        const dropped = forget(sym);
        if (typeof toast === 'function' && hasDom) {
            toast(document.getElementById('ovBanner') || document.body,
                dropped ? (sym + ' — remembered display settings dropped; the next visit starts fresh.')
                        : (sym ? (sym + ' had no remembered display settings.') : 'no instrument on screen.'),
                dropped ? 'ok' : 'warn');
        }
        return dropped;
    }

    /* Dial tweaks broadcast on `ofap:heat-scheme`; fold them into the current instrument's block
       after a short quiet period, so a slider drag is one write. */
    function scheduleSave() {
        if (saveTimer || !state.symbol) return;
        saveTimer = setTimeout(function () {
            saveTimer = 0;
            saveFor(state.symbol);
        }, 1500);
    }

    if (hasDom) {
        const start = function () {
            const sel = el('symbolSelect');
            if (sel && !sel.dataset.ofapScopes) {
                sel.dataset.ofapScopes = '1';
                sel.addEventListener('change', function () { void applyFor(currentSymbol()); });
            }
            document.addEventListener('ofap:heat-scheme', scheduleSave);
            /* Adopt the opening instrument as the baseline and apply ITS remembered block (the
               values freshly loaded from the config count as "last used" for anything else). */
            state.symbol = cleanSymbol(currentSymbol());
            if (state.symbol) void applyBlock(state.symbol);
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
        else start();
        document.addEventListener('ofap:shell', function () {
            if (!state.symbol) start();
        });
    }

    window.OFAPSCOPES = {
        SCOPED: SCOPED,
        MAX_INSTRUMENTS: MAX_INSTRUMENTS,
        capture: capture,
        planApply: planApply,
        cleanSymbol: cleanSymbol,
        currentSymbol: currentSymbol,
        applyFor: applyFor,
        applyBlock: applyBlock,
        saveFor: saveFor,
        forget: forget,
        forgetCurrent: forgetCurrent,
        state: function () {
            return { symbol: state.symbol, applied: state.applied, saved: state.saved, last: state.last };
        },
    };
})();
