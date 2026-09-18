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

    /* T11/B15: readability tiers layered on whichever theme is active; T11/B14: the interface
       scale. Both ride the same attribute/record mechanism as theme/accent/density — the config
       is the record, the localStorage mirror only kills the first-paint flash. */
    const CONTRASTS = ['calm', 'standard', 'aggressive'];
    const SCALE_MIN = 0.75, SCALE_MAX = 1.5, SCALE_STEP = 0.05;

    const state = { theme: 'dark', accent: 'cobalt', density: 'comfortable',
        contrast: 'standard', scale: 1, source: 'default' };

    function pick(list, value, fallback) {
        return (typeof value === 'string' && list.indexOf(value) >= 0) ? value : fallback;
    }
    /* A partial change merges over the current appearance, and every field is clamped to the list that
       themes/density declare — a typo in the config paints the default rather than a broken shell. */
    /* T11/B14: the scale clamps to the shipped bounds and quantises to its own step. */
    function clampScale(value) {
        const n = Number(value);
        if (!isFinite(n)) return state.scale;
        return Math.round(Math.min(SCALE_MAX, Math.max(SCALE_MIN, n)) / SCALE_STEP) * SCALE_STEP;
    }
    function normalize(next) {
        const src = next || {};
        return {
            theme: pick(THEMES, src.theme, state.theme),
            accent: pick(ACCENTS, src.accent, state.accent),
            density: pick(DENSITIES, src.density, state.density),
            contrast: pick(CONTRASTS, src.contrast, state.contrast),
            scale: clampScale(src.scale === undefined ? state.scale : src.scale),
        };
    }
    function snapshot() {
        return { theme: state.theme, accent: state.accent, density: state.density,
            contrast: state.contrast, scale: state.scale, source: state.source };
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
        root.dataset.contrast = state.contrast;
        /* T11/B14: one zoom on the root element scales the whole interface (chrome AND canvas
           text; the canvases re-fit on the ResizeObserver pass that follows). */
        root.style.setProperty('--ui-scale', String(state.scale));
        if (state.scale === 1) root.style.removeProperty('zoom');
        else root.style.zoom = String(state.scale);
        return true;
    }
    function same(a, b) {
        return a.theme === b.theme && a.accent === b.accent && a.density === b.density
            && a.contrast === b.contrast && a.scale === b.scale;
    }
    function syncControls() {
        [['setTheme', 'theme'], ['setAccent', 'accent'], ['setDensity', 'density'],
            ['setContrast', 'contrast']].forEach(([id, field]) => {
            const el = document.getElementById(id);
            if (el && el.value !== state[field]) el.value = state[field];
        });
        const sc = document.getElementById('setScale');
        if (sc && sc.value !== String(state.scale)) sc.value = String(state.scale);
    }
    function announce() {
        try {
            document.dispatchEvent(new CustomEvent('ofap:appearance', { detail: snapshot() }));
        } catch (err) { /* no CustomEvent: nothing to tell */ }
    }

    function apply(next, opts) {
        const clean = normalize(next);
        const changed = !same(clean, state);
        const scaleMoved = clean.scale !== state.scale;
        state.theme = clean.theme;
        state.accent = clean.accent;
        state.density = clean.density;
        state.contrast = clean.contrast;
        state.scale = clean.scale;
        state.source = (opts && opts.source) || state.source;
        paint();
        if (!(opts && opts.noMirror)) writeMirror();
        syncControls();
        if (scaleMoved && window.OFAPScale && typeof OFAPScale.fit === 'function') {
            /* The zoom reflows synchronously (the style write is flushed on the next measure), so
               the canvases re-fit NOW; the rAF pass catches anything still settling. (Measured in
               the sandbox: a headless tab throttles rAF, so the deferred-only fit left stale
               backings — the synchronous pass is the one that must not be skipped.) */
            try { OFAPScale.fit('ui-scale'); } catch (err) { /* the layer's own path reports faults */ }
            requestAnimationFrame(() => { try { OFAPScale.fit('ui-scale'); } catch (err) { /* settled */ } });
        }
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
                body: { ui: { theme: state.theme, accent: state.accent, density: state.density,
                    contrast: state.contrast, scale: state.scale } },
            }).catch(() => null);
        };
        const run = (window.OFAPINTENT && typeof OFAPINTENT.queueWrite === 'function')
            ? () => OFAPINTENT.queueWrite('ui.appearance', post)
            : post;
        return Promise.resolve(run());
    }

    function wire() {
        [['setTheme', 'theme'], ['setAccent', 'accent'], ['setDensity', 'density'],
            ['setContrast', 'contrast']].forEach(([id, field]) => {
            const el = document.getElementById(id);
            if (!el || !el.addEventListener || el.dataset.ofapWired) return;
            el.dataset.ofapWired = '1';
            el.addEventListener('change', () => {
                apply({ [field]: el.value }, { source: 'user' });
                void save();
            });
        });
        const sc = document.getElementById('setScale');
        if (sc && sc.addEventListener && !sc.dataset.ofapWired) {
            sc.dataset.ofapWired = '1';
            sc.addEventListener('change', () => {
                apply({ scale: sc.value }, { source: 'user' });
                void save();
            });
        }
        syncControls();
        return true;
    }

    /* T11/B14: the keyboard — Ctrl+= / Ctrl+- step the scale, Ctrl+0 resets it. Registered once,
       after the DOM is up, so the Keys sheet and the actions come from the same map. */
    function bindScaleKeys() {
        if (!window.OFAPKEYS || typeof OFAPKEYS.bind !== 'function') return false;
        const stepBy = (dir) => () => {
            apply({ scale: state.scale + dir * SCALE_STEP }, { source: 'user' });
            void save();
        };
        OFAPKEYS.bind({ id: 'ui-scale-in', keys: ['ctrl+=', 'ctrl++'], scope: 'Interface',
            label: 'larger interface', run: stepBy(1) });
        OFAPKEYS.bind({ id: 'ui-scale-out', keys: ['ctrl+-', 'ctrl+_'], scope: 'Interface',
            label: 'smaller interface', run: stepBy(-1) });
        OFAPKEYS.bind({ id: 'ui-scale-reset', keys: ['ctrl+0'], scope: 'Interface',
            label: 'reset the interface scale',
            run: () => { apply({ scale: 1 }, { source: 'user' }); void save(); } });
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
                if (ui) configured = { theme: ui.theme, accent: ui.accent, density: ui.density,
                    contrast: ui.contrast, scale: ui.scale };
            }
        } catch (err) { /* the mirror stands; appearance is not worth a banner */ }
        if (configured && (configured.theme || configured.accent || configured.density
            || configured.contrast || typeof configured.scale === 'number')) {
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
        const ready = () => { wire(); bindScaleKeys(); void load(); };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
        else ready();
    })();

    window.OFAPTHEME = {
        KEY, THEMES, ACCENTS, DENSITIES, CONTRASTS, SCALE_MIN, SCALE_MAX, SCALE_STEP,
        state: snapshot, apply, load, wire, normalize, paint, save, clampScale,
        set(theme) { return apply({ theme: theme }, { source: 'user' }); },
        setScale(value) { return apply({ scale: value }, { source: 'user' }); },
    };
})();
