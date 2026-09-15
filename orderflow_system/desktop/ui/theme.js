/* theme.js — the shell's appearance: theme, accent and density (plan P1-1).
 *
 * The config file is the record (`ui.theme`, `ui.accent`, `ui.density`). The browser mirror is only a
 * PRE-PAINT CACHE: the config arrives after the first paint, and an appearance that lands a frame late
 * is a flash. So the inline script in <head> paints from the mirror before the body exists; this module
 * then reads the config and, where the two disagree, the config wins and the mirror is rewritten. The
 * switcher in Settings writes the config first, then the mirror, then paints — one direction, no loops.
 *
 * Theming is one attribute on <html>: `data-theme` (dark | light | contrast), `data-accent` (the eight
 * Windows accents) and `data-density` (comfortable | compact | dense). themes/*.css do the rest.
 */
(function () {
    'use strict';

    const KEY = 'ofap.appearance';
    const THEMES = ['dark', 'light', 'contrast'];
    const ACCENTS = ['cobalt', 'teal', 'green', 'lime', 'amber', 'orange', 'magenta', 'violet'];
    const DENSITIES = ['comfortable', 'compact', 'dense'];

    const state = { theme: 'dark', accent: 'cobalt', density: 'comfortable', source: 'default' };

    function pick(list, value, fallback) {
        return (typeof value === 'string' && list.indexOf(value) >= 0) ? value : fallback;
    }
    /* A partial change merges over the current appearance, and every field is clamped to the list that
       themes/density declare — a typo in the config paints the default rather than a broken shell. */
    function normalize(next) {
        const src = next || {};
        return {
            theme: pick(THEMES, src.theme, state.theme),
            accent: pick(ACCENTS, src.accent, state.accent),
            density: pick(DENSITIES, src.density, state.density),
        };
    }
    function snapshot() {
        return { theme: state.theme, accent: state.accent, density: state.density, source: state.source };
    }
    function readMirror() {
        try {
            const raw = window.localStorage.getItem(KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (err) { return null; }                 /* storage blocked: the defaults stand */
    }
    function writeMirror() {
        try { window.localStorage.setItem(KEY, JSON.stringify(snapshot())); } catch (err) { /* private mode */ }
    }
    function paint() {
        if (typeof document === 'undefined' || !document || !document.documentElement) return false;
        const root = document.documentElement;
        root.dataset.theme = state.theme;
        root.dataset.accent = state.accent;
        root.dataset.density = state.density;
        return true;
    }
    function same(a, b) {
        return a.theme === b.theme && a.accent === b.accent && a.density === b.density;
    }
    function syncControls() {
        [['setTheme', 'theme'], ['setAccent', 'accent'], ['setDensity', 'density']].forEach(([id, field]) => {
            const el = document.getElementById(id);
            if (el && el.value !== state[field]) el.value = state[field];
        });
    }
    function announce() {
        try {
            document.dispatchEvent(new CustomEvent('ofap:appearance', { detail: snapshot() }));
        } catch (err) { /* no CustomEvent: nothing to tell */ }
    }

    function apply(next, opts) {
        const clean = normalize(next);
        const changed = !same(clean, state);
        state.theme = clean.theme;
        state.accent = clean.accent;
        state.density = clean.density;
        state.source = (opts && opts.source) || state.source;
        paint();
        if (!(opts && opts.noMirror)) writeMirror();
        syncControls();
        if (changed) announce();
        return snapshot();
    }

    /* Persist through the arbiter when it is loaded: a user flipping through the selects writes once,
       and the write is a patch — `merge_config` keeps every key the body does not mention. */
    function save() {
        const post = () => {
            if (typeof window.api !== 'function') return Promise.resolve(null);
            return window.api('/api/control/config', {
                method: 'POST',
                body: { ui: { theme: state.theme, accent: state.accent, density: state.density } },
            }).catch(() => null);
        };
        const run = (window.OFAPINTENT && typeof OFAPINTENT.queueWrite === 'function')
            ? () => OFAPINTENT.queueWrite('ui.appearance', post)
            : post;
        return Promise.resolve(run());
    }

    function wire() {
        [['setTheme', 'theme'], ['setAccent', 'accent'], ['setDensity', 'density']].forEach(([id, field]) => {
            const el = document.getElementById(id);
            if (!el || !el.addEventListener || el.dataset.ofapWired) return;
            el.dataset.ofapWired = '1';
            el.addEventListener('change', () => {
                apply({ [field]: el.value }, { source: 'user' });
                void save();
            });
        });
        syncControls();
        return true;
    }

    /* The config is the authority: read it once, on load. No polling — appearance changes when the
       user changes it, and a second writer to the same attributes would fight this one. */
    async function load() {
        let configured = null;
        try {
            if (typeof window.api === 'function') {
                const res = await window.api('/api/control/bootstrap');
                const ui = (res && res.config && res.config.ui) || null;
                if (ui) configured = { theme: ui.theme, accent: ui.accent, density: ui.density };
            }
        } catch (err) { /* the mirror stands; appearance is not worth a banner */ }
        if (configured && (configured.theme || configured.accent || configured.density)) {
            const fromConfig = normalize(configured);
            if (!same(fromConfig, state)) apply(fromConfig, { source: 'config' });
            else { state.source = 'config'; paint(); }
        }
        syncControls();
        return snapshot();
    }

    /* Boot: the mirror first (so the paint matches what <head> already applied), then the config.
       `paint()` runs unconditionally — the resolved appearance belongs on the document even when it
       equals the defaults, because the density and theme selectors are attribute-driven and a shell
       without the attributes is a shell the selectors cannot reach. */
    (function boot() {
        const mirrored = readMirror();
        if (mirrored) apply(mirrored, { source: 'mirror', noMirror: true });
        else paint();
        if (typeof document === 'undefined' || !document) return;
        const ready = () => { wire(); void load(); };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
        else ready();
    })();

    window.OFAPTHEME = {
        KEY, THEMES, ACCENTS, DENSITIES,
        state: snapshot, apply, load, wire, normalize, paint, save,
        set(theme) { return apply({ theme: theme }, { source: 'user' }); },
    };
})();
