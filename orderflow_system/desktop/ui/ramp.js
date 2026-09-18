/* ramp.js — B2: the heat-scheme vocabulary every heat surface shares.

   One home for the three display-only dials and the named schemes, read by both renderers — the
   Engine's depth layer (`ofx.js`) and the Heatmap view (`atlas.js`):

   * ceiling — the resting size at which the ramp reaches full colour. A top share of the book
     (`upper_cutoff_pct`, the exchange convention) or an exact size (`upper_cutoff_abs`); the
     backend resolves it into the snapshot's `scale_max`, so both surfaces saturate alike.
   * floor — the size below which nothing is drawn: exact (`heat_floor` / `floor`) or a bottom
     share of the surface's own matrix (`heat_floor_pct` / `floor_pct`).
   * contrast — a gamma on the ramp's 0..1 position: above 1 darkens the middle so the big levels
     stand out; below 1 lifts it so a thin book keeps its shape. 1 is the identity — the shipped
     look, to the pixel.

   The named schemes are data-semantic presets (the ATAS model: name the meaning, then give two
   dials): each says what it makes visible. `balanced` is the shipped recipe, values and all —
   `test_b2_ramps.py` keeps that equality a fact rather than a comment. Choosing a scheme writes
   its dials; hand-editing any dial afterwards reads 'custom' until a scheme matches again.

   Nothing in here touches a value, a feed or the ingest — it is only how a number is DRAWN. */
(function (root) {
    "use strict";

    const SCHEMES = [
        { id: "balanced", label: "Balanced depth", ceiling_pct: 5.0, floor: 0.0, floor_pct: 0.0, contrast: 1.0,
          says: "the shipped recipe — saturation at the top 5% of resting size" },
        { id: "walls", label: "Wall hunt", ceiling_pct: 2.0, floor: 0.0, floor_pct: 6.0, contrast: 1.35,
          says: "only the top 2% saturate and the bottom 6% stay unpainted — the walls glare" },
        { id: "detail", label: "Thin-book detail", ceiling_pct: 12.0, floor: 0.0, floor_pct: 0.0, contrast: 0.8,
          says: "more of the range spreads across colour and the middle lifts — a thin book keeps its shape" },
        { id: "quiet", label: "Quiet book", ceiling_pct: 5.0, floor: 0.0, floor_pct: 15.0, contrast: 1.15,
          says: "the small orders stay unpainted — the standing depth reads clean" },
    ];

    const CONTRAST_MIN = 0.5;
    const CONTRAST_MAX = 2.5;
    const FLOOR_PCT_MAX = 50.0;

    /* T10/B3: vertical smoothing — the blend strength and the compression band. */
    const SMOOTH_STRENGTH = 0.6;
    const SMOOTH_ENGAGE_PX = 2.5;
    const SMOOTH_RELEASE_PX = 4.0;
    const SMOOTH_LIST = ["auto", "manual", "none"];

    function clamp(value, lo, hi, fallback) {
        /* null/undefined/'' mean "not set" — Number(null) is 0, the falsy-zero trap — and junk is
           junk: both take the fallback, so an absent dial paints the shipped look. */
        if (value === null || value === undefined || value === "") return fallback;
        const n = Number(value);
        if (!Number.isFinite(n)) return fallback;
        return Math.min(hi, Math.max(lo, n));
    }

    /* gamma on the ramp position; 1 is the identity, so the default paints exactly as before. */
    function contrastT(t, gamma) {
        const x = Math.min(1, Math.max(0, Number(t) || 0));
        const g = clamp(gamma, CONTRAST_MIN, CONTRAST_MAX, 1);
        return g === 1 ? x : Math.pow(x, g);
    }

    /* the value at percentile p (0..100) of an ASCENDING list; null for an empty list. */
    function percentile(sorted, p) {
        const list = sorted || [];
        if (!list.length) return null;
        const cut = clamp(p, 0, 100, 0);
        const idx = Math.min(list.length - 1, Math.max(0, Math.round((cut / 100) * (list.length - 1))));
        return Number(list[idx]) || 0;
    }

    /* the effective floor: the larger of the exact size and the bottom-share size.
       `sorted` is the positive resting sizes of the surface's current matrix, ascending. */
    function floorValue(sorted, abs, pct) {
        const a = Math.max(0, Number(abs) || 0);
        const p = clamp(pct, 0, FLOOR_PCT_MAX, 0);
        const q = p > 0 ? percentile(sorted, p) : 0;
        return Math.max(a, q === null ? 0 : q);
    }

    function schemeById(id) {
        for (const s of SCHEMES) if (s.id === id) return s;
        return null;
    }

    /* which preset a surface's dials currently match; a pinned absolute ceiling is nobody's
       scheme, and so is any hand-tweaked dial: both read 'custom'. */
    function matchScheme(state) {
        const s = state || {};
        if (Number(s.ceiling_abs) > 0) return "custom";
        const near = (a, b) => Math.abs((Number(a) || 0) - b) < 1e-6;
        for (const scheme of SCHEMES) {
            if (near(s.ceiling_pct, scheme.ceiling_pct) && near(s.floor, scheme.floor)
                && near(s.floor_pct, scheme.floor_pct) && near(s.contrast, scheme.contrast)) {
                return scheme.id;
            }
        }
        return "custom";
    }

    /* dotted-path reads/writes, so a UI can keep its config copy in step with what the store
       accepted without re-fetching the whole file. */
    function getIn(obj, path, fallback) {
        let node = obj;
        for (const part of String(path || "").split(".")) {
            if (!node || typeof node !== "object" || !(part in node)) return fallback;
            node = node[part];
        }
        return node === undefined ? fallback : node;
    }

    function setIn(obj, path, value) {
        if (!obj || typeof obj !== "object") return obj;
        const parts = String(path || "").split(".");
        let node = obj;
        for (const part of parts.slice(0, -1)) {
            if (typeof node[part] !== "object" || node[part] === null) node[part] = {};
            node = node[part];
        }
        node[parts[parts.length - 1]] = value;
        return obj;
    }

    /* One write path for both surfaces: POST one registered variable through the /params gate
       and fold the value the store ACCEPTED back into the page's config copy. Returns the applied
       value, or null (with `onNote(reason)`) when refused or unreachable. */
    async function writeParam(path, value, cfgRoot, onNote) {
        try {
            const res = await fetch("/api/control/params", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: path, value: value }),
            }).then((r) => r.json());
            if (!res || res.ok === false) {
                if (onNote) onNote("refused: " + ((res && res.error) || path));
                return null;
            }
            if (cfgRoot) setIn(cfgRoot, path, res.value);
            if (res.applies === "restart" && onNote) {
                onNote("applies when the engine restarts: " + path);
            }
            return res.value;
        } catch (err) {
            if (onNote) onNote("write failed: " + err);
            return null;
        }
    }

    /* T10/B3 — vertical smoothing: one pass of the [1,1,1]/3 kernel at `strength`, edges
       clamped to themselves. A constant vector stays constant (the shipped look is a fixed
       point); `strength` 0 is the identity. Pure, so the selftest can own it. */
    function smoothVector(vec, strength) {
        const v = Array.isArray(vec) ? vec : Array.from(vec || []);
        const s = clamp(strength === undefined ? SMOOTH_STRENGTH : strength, 0, 1, SMOOTH_STRENGTH);
        const out = new Array(v.length);
        for (let i = 0; i < v.length; i += 1) {
            const c = Number(v[i]) || 0;
            const up = i > 0 ? (Number(v[i - 1]) || 0) : c;
            const dn = i < v.length - 1 ? (Number(v[i + 1]) || 0) : c;
            out[i] = c + ((up + c + dn) / 3 - c) * s;
        }
        return out;
    }

    /* The compression verdict for 'auto', with hysteresis: engage below `engage`, stay
       engaged until the rows widen past `release`. The surface keeps the previous boolean. */
    function smoothDecision(cellPx, engaged, engage, release) {
        const px = Number(cellPx) || 0;
        const lo = engage === undefined ? SMOOTH_ENGAGE_PX : Number(engage);
        const hi = release === undefined ? SMOOTH_RELEASE_PX : Number(release);
        return engaged ? px < hi : px < lo;
    }

    /* Which smoothing mode a stored value is ('auto' for junk — the shipped look). */
    function smoothMode(value) {
        return SMOOTH_LIST.indexOf(String(value)) >= 0 ? String(value) : "auto";
    }

    const OFAPRAMP = {
        SCHEMES, schemeById, matchScheme,
        contrastT, percentile, floorValue, getIn, setIn, writeParam,
        CONTRAST_MIN, CONTRAST_MAX, FLOOR_PCT_MAX,
        SMOOTH_STRENGTH, SMOOTH_ENGAGE_PX, SMOOTH_RELEASE_PX, SMOOTH_LIST,
        smoothVector, smoothDecision, smoothMode,
        clampContrast: (v) => clamp(v, CONTRAST_MIN, CONTRAST_MAX, 1),
        clampFloor: (v) => Math.max(0, Number(v) || 0),
        clampFloorPct: (v) => clamp(v, 0, FLOOR_PCT_MAX, 0),
    };

    if (typeof module !== "undefined" && module.exports) module.exports = OFAPRAMP;
    root.OFAPRAMP = OFAPRAMP;
})(typeof globalThis !== "undefined" ? globalThis : this);
