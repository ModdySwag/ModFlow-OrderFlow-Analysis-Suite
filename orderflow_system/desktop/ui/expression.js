/* ══════════════════════════════════════════════════════════════════
   expression.js — how a bar is expressed, and with which colours (P1-8).

   Two surfaces draw bars and they share nothing: the engine view paints a footprint matrix on
   canvases (ofx.js), the chart view hands OHLC to the vendored Lightweight Charts (ui.js). What they
   *must* share is the decision — which colour means what, what a body is tinted by, what the split
   halves are, and the sentence that names the encoding. That decision is here, pure: a bar and a
   mode in, paint out. The renderers execute it; they do not decide.

   It is pure (no DOM, no API, no storage) so `expression.selftest.js` can pin every mode in Node, and
   `orderflow_system/test_expression.py` holds it against the engine: the modes and palettes declared
   here are the catalogues `config_store` clamps to, and the words it prints are the words the legend
   renders — a picture drawn from `barPaint()` and a sentence from `barPaint().encoding` cannot
   disagree, because they are the same object.

   Colour rules this file exists to enforce (canon #5):
     · a sign is never carried by hue alone — every mode pairs its tint with a glyph, a position or
       weight, and `pairing` says which;
     · a palette is a whole colour vocabulary (resting bid/ask, direction, delta), not a highlighter;
     · a colour-blind palette's up/down pair is MEASURED (`separation()` below), not asserted, and the
       shipped green/red pair is the control that fails the same measurement.
   ══════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── colour arithmetic: sRGB ↔ Lab, and the dichromat simulation ─────────────────────────
       The simulation is the Machado–Oliveira–Fernandes (2009) severity-1.0 matrix set — the model
       published with its own validation against dichromat observers (IEEE TVCG 15(6):1291-1298,
       table read from the authors' page), applied in LINEAR RGB: expand the gamma, transform,
       compress back. Each row sums to 1.0, which is what keeps the neutral axis neutral (grey in,
       grey out) and is asserted in the selftest as the table's own self-check. It is used for two
       things and nothing else: comparing two colours' separation under a dichromacy, and proving
       the metric can detect a collapse (the same-luminance red/green control). */

    function parseRgb(value) {
        if (Array.isArray(value)) return value.slice(0, 3).map(Number);
        const text = String(value == null ? '' : value).trim();
        const hex = /^#?([0-9a-f]{6})$/i.exec(text);
        if (hex) {
            const n = parseInt(hex[1], 16);
            return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
        }
        const triplet = /^(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})$/.exec(text);
        if (triplet) return [Number(triplet[1]), Number(triplet[2]), Number(triplet[3])];
        return null;
    }

    const CVD_MATRICES = {
        protanopia: [0.152286, 1.052583, -0.204868,
                     0.114503, 0.786281, 0.099216,
                     -0.003882, -0.048116, 1.051998],
        deuteranopia: [0.367322, 0.860646, -0.227968,
                       0.280085, 0.672501, 0.047413,
                       -0.011820, 0.042940, 0.968881],
        tritanopia: [1.255528, -0.076749, -0.178779,
                     -0.078411, 0.930809, 0.147602,
                     0.004733, 0.691367, 0.303900],
    };

    const toLinear = (c) => { const s = c / 255; return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4); };
    const toSrgb = (v) => {
        const x = v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055;
        return Math.max(0, Math.min(255, Math.round(x * 255)));
    };

    /* sRGB → CIE XYZ (D65) → L*a*b*. ΔE76 is the distance the selftest measures pairs with. */
    function toLab(rgb) {
        const [r, g, b] = (parseRgb(rgb) || [0, 0, 0]).map(toLinear);
        const x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047;
        const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        const z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
        const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
        const [fx, fy, fz] = [f(x), f(y), f(z)];
        return { L: 116 * fy - 16, a: 500 * (fx - fy), b: 200 * (fy - fz) };
    }

    function deltaE(a, b) {
        const A = toLab(a), B = toLab(b);
        return Math.sqrt((A.L - B.L) ** 2 + (A.a - B.a) ** 2 + (A.b - B.b) ** 2);
    }

    /** What a dichromat sees, per the Viénot matrix set (linear RGB, gamma handled). */
    function simulate(rgb, kind) {
        const m = CVD_MATRICES[kind];
        if (!m) return parseRgb(rgb) || [0, 0, 0];
        const [r, g, b] = (parseRgb(rgb) || [0, 0, 0]).map(toLinear);
        return [
            toSrgb(m[0] * r + m[1] * g + m[2] * b),
            toSrgb(m[3] * r + m[4] * g + m[5] * b),
            toSrgb(m[6] * r + m[7] * g + m[8] * b),
        ];
    }

    /* The measured claim a palette has to earn: how far apart two colours stay for a dichromat.
       `dE` is the perceptual distance after simulation, `dL` the lightness gap (reported, not
       enforced — a sign is carried by the glyph and the badge, and the lightness gap is what a
       palette can additionally offer). MIN_PAIR_DE is the floor: ΔE 40 is many times the ~2.3
       just-noticeable difference, i.e. "these two read as different colours", not "these two are
       merely not identical". The selftest enforces it for every CB palette under ITS OWN dichromacy
       and under the other two, and proves the metric can fail (the collapse control). */
    const MIN_PAIR_DE = 40;
    function separation(a, b, kind) {
        const A = simulate(a, kind);
        const B = simulate(b, kind);
        const dE = deltaE(A, B);
        const dL = Math.abs(toLab(A).L - toLab(B).L);
        return {
            dE: +dE.toFixed(2), dL: +dL.toFixed(2),
            ok: dE >= MIN_PAIR_DE,
            simulated: { a: A.join(','), b: B.join(',') },
        };
    }

    /* Legibility on the stage, not just separation on paper. The canvas ground is near-black
       (rgb(10,14,22), `atlas.css`), the matrix shades a cell at alpha 0.30, so a palette colour has to
       survive being composited at that alpha over that ground. The selftest requires every palette's
       two colours to lift the ground's relative luminance by MIN_LEGIBILITY at the shading alpha —
       a palette that separates beautifully and disappears on the canvas is not a palette. */
    const GROUND = [10, 14, 22];
    const LEGIBILITY_ALPHA = 0.30;
    const MIN_LEGIBILITY = 3;
    function composite(rgb, alpha, ground) {
        const c = parseRgb(rgb) || [0, 0, 0];
        const g = ground || GROUND;
        return c.map((v, i) => Math.round(v * alpha + g[i] * (1 - alpha)));
    }
    function relativeLuminance(rgb) {
        const [r, g, b] = (parseRgb(rgb) || [0, 0, 0]).map(toLinear);
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }
    function legibility(rgb, alpha) {
        const a = alpha == null ? LEGIBILITY_ALPHA : alpha;
        const lifted = relativeLuminance(composite(rgb, a));
        const ground = relativeLuminance(GROUND);
        return { ratio: +(lifted / ground).toFixed(2), composite: composite(rgb, a).join(','), ok: lifted / ground >= MIN_LEGIBILITY };
    }

    /* ── the palette catalogue ────────────────────────────────────────────────────────────────
       `theme` is the shipped vocabulary: the engine's own base table (green bid / red ask) and the
       chart's up/down pair — measured here, under the Machado model, as the control this feature
       exists for: the shipped pair's separation COLLAPSES under deuteranopia (ΔE 9.1 against the
       ΔE 40 floor), so a green-blind reader cannot tell the bid half of a cell from the ask half.

       The three colour-blind palettes are Okabe–Ito colours (Okabe & Ito 2008; Wong, Nature Methods
       8(6):441, 2011 — published as safe for protanopia, deuteranopia AND tritanopia), chosen by
       measurement rather than by reputation: every candidate below was simulated under all three
       dichromacies and only pairs clearing the floor in ALL THREE shipped. Measured (protan /
       deutan / tritan ΔE), worst case in brackets:

         deutan  sky blue 86,180,233 ↔ orange 230,159,0       101.6 / 111.4 /  86.7
         protan  yellow   240,228,66 ↔ sky    86,180,233      115.6 / 112.9 /  59.7  [tritan]
         tritan  teal     64,176,166 ↔ red    220,50,32        47.4 /  63.5 / 129.6  [protan]

       Pairs that did NOT survive measurement and are therefore not shipped: teal/magenta (deutan
       ΔE 0.76 — the same collapse as the shipped pair), green/purple (protan 36.2, deutan 18.1),
       cyan/magenta (deutan 18.9, the app's own imbalance pair), yellow/purple (tritan 37.8).

       **Two hues per palette, and that is the point.** A colour-blind palette is a whole vocabulary,
       not a highlighter: `themeOverrides()` maps every order-flow colour onto the palette's pair —
       bid, up and delta-positive onto `pos`; ask, down, delta-negative, and the sell-side book-event
       colours onto `neg`. Which LAYER a mark belongs to is carried by its shape (the imbalance glow
       and rail, the stack glyph, the split halves), never by a third hue. */
    const OKABE = {
        orange: '230,159,0', sky: '86,180,233', green: '0,158,115', yellow: '240,228,66',
        blue: '0,114,178', vermillion: '213,94,0', purple: '204,121,167', teal: '64,176,166', red: '220,50,32',
    };

    const PALETTES = {
        theme: {
            label: 'theme',
            words: 'the shell theme\'s own pair (green / red)',
            pos: null, neg: null, cvd: null,
            note: 'green/red separates for a protanope (ΔE 35 — under the floor) and collapses for a deuteranope (ΔE 9.1)',
        },
        deutan: {
            label: 'deutan-safe',
            words: 'sky blue / orange — deuteranopia and protanopia',
            pos: OKABE.sky, neg: OKABE.orange, cvd: 'deuteranopia',
            measured: { protanopia: 101.56, deuteranopia: 111.38, tritanopia: 86.7 },
        },
        protan: {
            label: 'protan-safe',
            words: 'yellow / sky blue — protanopia',
            pos: OKABE.yellow, neg: OKABE.sky, cvd: 'protanopia',
            measured: { protanopia: 115.6, deuteranopia: 112.91, tritanopia: 59.7 },
        },
        tritan: {
            label: 'tritan-safe',
            words: 'teal / red — tritanopia',
            pos: OKABE.teal, neg: OKABE.red, cvd: 'tritanopia',
            measured: { protanopia: 47.39, deuteranopia: 63.47, tritanopia: 129.59 },
        },
    };

    const PALETTE_KEYS = Object.keys(PALETTES);

    function palette(key) {
        return PALETTES[String(key || '')] || PALETTES.theme;
    }

    /** The up/down (positive/negative) pair a palette uses, given the engine's live theme pair. */
    function pair(key, theme) {
        const p = palette(key);
        const base = theme || {};
        return {
            pos: p.pos || base.pos || '53,208,127',
            neg: p.neg || base.neg || '255,93,108',
        };
    }

    /** Every colour-table key a palette writes. `theme` writes nothing: its own table stands. */
    function themeOverrides(key) {
        const p = palette(key);
        if (!p.pos || !p.neg) return {};
        return {
            bid: p.pos, ask: p.neg,               // resting depth halves
            up: p.pos, down: p.neg,               // direction (chart series, direction glyphs)
            imBuy: p.pos, imSell: p.neg,          // diagonal imbalance
            stackUp: p.pos, stackDown: p.neg,     // book events: stacked / pulled
        };
    }

    /* ── the six modes ──────────────────────────────────────────────────────────────────────
       `chrome` is what the mode keeps of the default bar furniture; `says` is the legend's own
       sentence for the encoding, so the picture and its description come from one place. */
    const MODES = {
        default: {
            label: 'default',
            says: 'footprint cells — bid left half, ask right half; framing, value-area ground, POC and the \u0394/V badge',
            pairing: 'a side is carried by which HALF of the cell is shaded, and by the digits',
            chrome: { framing: true, ground: true, zones: true, poc: true, badges: true },
        },
        delta: {
            label: 'delta-tinted',
            says: 'body = bar delta, outline = price direction',
            pairing: 'the direction also rides the \u25b2/\u25bc glyph and the signed \u0394 badge',
            chrome: { framing: true, ground: false, zones: false, poc: true, badges: true },
        },
        split: {
            label: 'split candle',
            says: 'left = sell volume, right = buy volume, height = that side\u2019s share of the bar',
            pairing: 'the side also rides its own half (left/right) and the \u2193/\u2191 glyph',
            chrome: { framing: false, ground: false, zones: false, poc: true, badges: true },
        },
        heat: {
            label: 'heat body',
            says: 'body = |delta| / volume on the palette\u2019s diverging ramp',
            pairing: 'the sign also rides the \u25b2/\u25bc glyph and the signed \u0394 badge',
            chrome: { framing: true, ground: false, zones: false, poc: true, badges: true },
        },
        wick: {
            label: 'wick + footprint',
            says: 'no body \u2014 the high/low wick and the footprint cells only',
            pairing: 'the cells\u2019 own split (left/right) and digits carry every side',
            chrome: { framing: false, ground: false, zones: false, poc: false, badges: true },
        },
        candles: {
            label: 'candles',
            says: 'classic candle \u2014 body = open\u2192close, the wick to high/low, colour by direction',
            pairing: 'direction also rides the \u25b2/\u25bc glyph on the body',
            chrome: { framing: false, ground: false, zones: false, poc: false, badges: false, cells: false },
        },
    };

    const MODE_KEYS = Object.keys(MODES);

    function mode(key) {
        return MODES[String(key || '')] || MODES.default;
    }

    /* ── the paint decision ─────────────────────────────────────────────────────────────────── */

    /** Signed strength of a bar's delta: |delta| / volume, clipped. 0 when there is no volume. */
    function deltaShare(bar) {
        const vol = Math.abs(Number(bar && bar.volume) || 0);
        const d = Math.abs(Number(bar && bar.delta) || 0);
        if (!vol || !d) return 0;
        return Math.max(0, Math.min(1, d / vol));
    }

    function dirOf(bar) {
        const c = Number(bar && bar.close), o = Number(bar && bar.open);
        if (!Number.isFinite(c) || !Number.isFinite(o)) return 0;
        if (c > o) return 1;
        if (c < o) return -1;
        const d = Number(bar && bar.delta) || 0;
        return d > 0 ? 1 : (d < 0 ? -1 : 0);
    }

    /** Up/down volume for the split candle, plus which source answered.
     *  Side volumes when the feed carries them (`calc.buy`/`calc.sell`, or candles' own
     *  `buy_volume`/`sell_volume`); otherwise derived from volume and delta — and said so. */
    function splitVolumes(bar) {
        const b = bar || {};
        const calc = b.calc || {};
        const side = [b.buy, b.sell, calc.buy, calc.sell, b.buy_volume, b.sell_volume]
            .some((v) => Number.isFinite(Number(v)) && Number(v) !== 0);
        const buyRaw = Number(b.buy_volume ?? calc.buy ?? b.buy);
        const sellRaw = Number(b.sell_volume ?? calc.sell ?? b.sell);
        if (side && Number.isFinite(buyRaw) && Number.isFinite(sellRaw)) {
            return { buy: Math.max(0, buyRaw), sell: Math.max(0, sellRaw), source: 'side volumes' };
        }
        const vol = Math.max(0, Number(b.volume) || 0);
        const delta = Number(b.delta) || 0;
        return {
            buy: Math.max(0, Math.min(vol, (vol + delta) / 2)),
            sell: Math.max(0, Math.min(vol, (vol - delta) / 2)),
            source: vol ? 'derived from volume and delta' : 'no volume in this bar',
        };
    }

    const rgbaOf = (rgb, alpha) => `rgba(${rgb},${alpha})`;
    const glyphFor = (dir) => (dir > 0 ? '\u25b2' : (dir < 0 ? '\u25bc' : ''));

    /**
     * Everything a renderer needs to draw one bar's expression, and the sentence that names it.
     *
     * @param bar    {open, high, low, close, volume, delta, [buy], [sell], [calc]}
     * @param opts   {mode, palette, theme:{pos, neg}}  — `theme` is the renderer's live pair, so the
     *               decision quotes the exact colours on screen rather than a second copy of them.
     */
    function barPaint(bar, opts) {
        const o = opts || {};
        const m = mode(o.mode);
        const colors = pair(PALETTES[o.palette] ? o.palette : 'theme', o.theme);
        const dir = dirOf(bar);
        const share = deltaShare(bar);
        const strong = 0.26;
        const out = {
            mode: MODE_KEYS.indexOf(String(o.mode)) >= 0 ? String(o.mode) : 'default',
            palette: PALETTES[o.palette] ? String(o.palette) : 'theme',
            chrome: Object.assign({}, m.chrome),
            glyph: '',
            body: null,
            split: null,
            wick: { rgba: rgbaOf(colors.pos, 0.35), lineWidth: 1 },
            encoding: m.says,
            pairing: m.pairing,
        };

        if (out.mode === 'delta') {
            const tint = dir < 0 ? colors.neg : colors.pos;
            const alpha = (0.10 + strong * share).toFixed(3);
            out.body = { fill: rgbaOf(tint, alpha), stroke: rgbaOf(tint, 0.95), lineWidth: 1.5 };
            out.glyph = glyphFor(dir);
        } else if (out.mode === 'heat') {
            const tint = dir < 0 ? colors.neg : colors.pos;
            out.body = { fill: rgbaOf(tint, (0.16 + 0.54 * share).toFixed(3)), stroke: rgbaOf(tint, 0.85), lineWidth: 1 };
            out.glyph = glyphFor(dir);
        } else if (out.mode === 'split') {
            const v = splitVolumes(bar);
            const total = v.buy + v.sell;
            const left = total ? v.sell / total : 0.5;
            out.split = {
                left: { frac: left, rgba: rgbaOf(colors.neg, 0.55), label: 'sell' },
                right: { frac: 1 - left, rgba: rgbaOf(colors.pos, 0.55), label: 'buy' },
                source: v.source,
            };
            out.glyph = '\u2191';
            out.wick.rgba = rgbaOf(colors.pos, 0.28);
        } else if (out.mode === 'wick') {
            out.glyph = '';
        } else if (out.mode === 'candles') {
            /* T10/B13: the classic candle \u2014 a saturated body by direction, the wick to the
               bar's range. This is also what the Engine draws on its own when the zoom pushes a
               column under the text threshold (`atlas.ofx.degrade`). */
            const tint = dir < 0 ? colors.neg : colors.pos;
            out.body = { fill: rgbaOf(tint, 0.85), stroke: rgbaOf(tint, 1), lineWidth: 1 };
            out.wick = { rgba: rgbaOf(tint, 0.8), lineWidth: 1 };
            out.glyph = glyphFor(dir);
        }
        return out;
    }

    /* ── the chart view's projection ──────────────────────────────────────────────────────────
       Lightweight Charts takes per-bar overrides on a candlestick: `color` (body), `borderColor`
       (outline), `wickColor`. One function so the chart view never re-derives a colour the engine
       decided differently. `split` has no vendor equivalent (see `CHART_SUPPORT`). */
    const CHART_SUPPORT = { default: true, delta: true, heat: true, wick: true, split: false, candles: true };

    function chartBars(bars, opts) {
        const o = opts || {};
        const m = mode(o.mode);
        const colors = pair(o.palette, o.theme);
        /* The vendor PARSES every colour it is handed and THROWS on a bare 'r,g,b' triplet --
           measured live: "Error: Cannot parse color: 86,180,233" out of lightweight-charts' own
           paint path, which the shell's fatal handler turned into a wiped app. The pair table
           keeps triplets because the canvas renderers compose them with alpha; the chart
           projection gets CSS from here. */
        const pos = `rgb(${colors.pos})`, neg = `rgb(${colors.neg})`;
        return (bars || []).map((bar) => {
            const row = {
                time: bar.time, open: bar.open, high: bar.high, low: bar.low, close: bar.close,
            };
            const dir = dirOf(bar);
            const share = deltaShare(bar);
            const up = dir >= 0;
            if (m === MODES.delta) {
                const tint = up ? colors.pos : colors.neg;
                row.color = rgbaOf(tint, (0.18 + 0.6 * share).toFixed(3));
                row.borderColor = up ? pos : neg;
                row.wickColor = up ? pos : neg;
            } else if (m === MODES.heat) {
                const tint = up ? colors.pos : colors.neg;
                row.color = rgbaOf(tint, (0.25 + 0.7 * share).toFixed(3));
                row.borderColor = rgbaOf(tint, 0.9);
                row.wickColor = up ? pos : neg;
            } else if (m === MODES.wick) {
                row.color = 'rgba(0,0,0,0)';                 // no body: the wick and the range stand
                row.borderColor = 'rgba(0,0,0,0)';
                row.wickColor = up ? pos : neg;
            } else {
                row.color = up ? pos : neg;
                row.borderColor = row.color;
                row.wickColor = row.color;
            }
            return row;
        });
    }

    /* ── the words ────────────────────────────────────────────────────────────────────────────
       The legend renders these; the renderers draw from `barPaint()`, whose `encoding` IS `says`.
       `legendLines` returns the exact strings for the active mode + palette, so "the legend names
       the encoding actually in use" is one function call, not a promise. */

    function legendLines(modeKey, paletteKey, extra) {
        const m = mode(modeKey);
        const p = palette(paletteKey);
        const e = extra || {};
        const lines = [
            `expression: ${m.label} \u2014 ${m.says}`,
            `sign: ${m.pairing}`,
            `palette: ${p.label} \u2014 ${p.words}`,
        ];
        if (p.pos) {
            lines.push(`palette maps: buy side rgb(${p.pos}) \u00b7 sell side rgb(${p.neg}) \u2014 every `
                + 'resting, imbalance and direction mark takes one of those two; the layer is named by '
                + 'its shape (glow, rail, glyph), not by a third colour');
        } else if (p.note) {
            lines.push(`palette note: ${p.note}`);
        }
        if (e.ramp) lines.push(`depth ramp: ${e.ramp}`);
        if (m === MODES.split) {
            lines.push(`split volumes: ${e.splitSource || 'side volumes where the feed carries them'}`);
        }
        if (e.chartGap) lines.push(e.chartGap);
        return lines;
    }

    const OFAPEXPR = {
        PALETTES, PALETTE_KEYS, MODES, MODE_KEYS, CHART_SUPPORT, CVD_MATRICES,
        MIN_PAIR_DE, MIN_LEGIBILITY, LEGIBILITY_ALPHA, GROUND,
        mode, palette, pair, themeOverrides,
        parseRgb, simulate, deltaE, separation, composite, relativeLuminance, legibility,
        deltaShare, dirOf, splitVolumes, glyphFor,
        barPaint, chartBars, legendLines,
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = OFAPEXPR;
    if (typeof window !== 'undefined') window.OFAPEXPR = OFAPEXPR;
})();
