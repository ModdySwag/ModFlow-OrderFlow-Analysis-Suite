/* audio.js — trade-driven audio: the tape you can hear.
 *
 * The one thing this suite did not have that every terminal trader's desk has: an audible tick.
 * Design rules, deliberately narrow:
 *
 *  · **OFF by default.** Nothing plays until the master switch in the config (`audio.enabled`) is
 *    on — a surprise noise in a quiet room is worse than a missing feature.
 *  · **Decide and play are separate.** `decide()` is a pure function of (tick, config, memory):
 *    the master switch, the size threshold, the "hard" variant (≥ `min_size × hard_multiple`) and
 *    the overlap attenuation are all arithmetic, so `audio.selftest.js` pins them without a browser.
 *  · **Attenuate, never stack.** A retrigger inside `overlap_window_ms` is quieter (halved per
 *    overlap down to `overlap_floor`), the way a real order book does not shout twice for one
 *    print — a wall of sound is a wall of lost information.
 *  · **A dead audio device is a notice, not a crash.** A rejected `play()` (no device, muted host)
 *    increments a counter, records the reason and dispatches `ofap:audio-failed` so the UI can say
 *    so once, instead of failing silently.
 *
 * The stream is the app's own `tick` websocket channel (throttled to 5/s per symbol upstream), so
 * this module can never flood a machine: worst case is the feed's own cadence.
 */

(function () {
    'use strict';

    var DEFAULTS = {
        enabled: false,            // master switch — the whole feature is silent until this is true
        volume: 0.6,               // 0..1, applied on top of the attenuation
        min_size: 0,               // base units; 0 = every print plays
        hard_multiple: 3,          // size ≥ min_size × this plays the two-tone alert
        hard_enabled: true,
        active_symbol_only: true,  // only the instrument in the symbol box, not every enabled one
        overlap_window_ms: 10,     // a retrigger inside this window is attenuated
        overlap_floor: 0.25        // …but never quieter than this share
    };

    var SAMPLES = {
        'buy': '/desktop/audio/alert-buy.wav',
        'sell': '/desktop/audio/alert-sell.wav',
        'buy-hard': '/desktop/audio/alert-buy-hard.wav',
        'sell-hard': '/desktop/audio/alert-sell-hard.wav'
    };

    var state = {
        symbol: '',
        pool: {},          // name → Audio element
        last: {},          // name → { at, overlap }
        plays: 0,
        failures: 0,
        lastError: '',
        lastPlayed: ''
    };

    function clone(obj) {
        var out = {};
        Object.keys(obj).forEach(function (k) { out[k] = obj[k]; });
        return out;
    }

    function num(value, lo, hi, fallback) {
        var n = Number(value);
        if (!isFinite(n)) return fallback;
        return Math.min(hi, Math.max(lo, n));
    }

    /* Config in, clamped config out — a bad value in config.json can never break the player. */
    function normalise(raw) {
        var src = raw || {};
        var out = clone(DEFAULTS);
        out.enabled = src.enabled === true;
        out.hard_enabled = src.hard_enabled !== false;
        out.active_symbol_only = src.active_symbol_only !== false;
        out.volume = num(src.volume, 0, 1, DEFAULTS.volume);
        out.min_size = num(src.min_size, 0, 1e12, DEFAULTS.min_size);
        out.hard_multiple = num(src.hard_multiple, 1, 1000, DEFAULTS.hard_multiple);
        out.overlap_window_ms = num(src.overlap_window_ms, 0, 5000, DEFAULTS.overlap_window_ms);
        out.overlap_floor = num(src.overlap_floor, 0.01, 1, DEFAULTS.overlap_floor);
        return out;
    }

    var cfg = normalise(null);

    function configure(raw) {
        cfg = normalise(raw);
        return cfg;
    }

    /* ── the decision (pure) ──────────────────────────────────────────────────────────────────
     * `mem` is the retrigger memory: { name: { at, overlap } }. Passed in so the rule is testable
     * and so the live state's shape is a caller's choice, never a hidden global.
     */
    function decide(tick, opts) {
        var o = opts || {};
        var c = o.cfg || cfg;
        var now = (o.now === undefined || o.now === null) ? 0 : Number(o.now);
        var mem = o.mem || state.last;
        if (!c.enabled) return null;
        if (!tick || !(Number(tick.size) > 0)) return null;
        if (c.active_symbol_only) {
            var wanted = String(o.symbol || '').toUpperCase();
            var got = String(tick.symbol || '').toUpperCase();
            if (wanted && got && wanted !== got) return null;
        }
        var min = c.min_size;
        if (min > 0 && Number(tick.size) < min) return null;
        var hard = c.hard_enabled && min > 0 && Number(tick.size) >= min * c.hard_multiple;
        var name = (String(tick.side).toLowerCase() === 'buy' ? 'buy' : 'sell') + (hard ? '-hard' : '');
        var prev = mem[name];
        var overlap = 0;
        if (prev && now - prev.at < c.overlap_window_ms) overlap = (prev.overlap || 0) + 1;
        var gain = Math.max(c.overlap_floor, 1 / Math.pow(2, overlap));
        mem[name] = { at: now, overlap: overlap };
        return { name: name, gain: gain, overlap: overlap, hard: hard };
    }

    /* ── the player ──────────────────────────────────────────────────────────────────────────── */
    function announceFailure() {
        var detail = { error: state.lastError, failures: state.failures };
        try {
            if (typeof document !== 'undefined' && document && document.dispatchEvent &&
                typeof CustomEvent === 'function') {
                document.dispatchEvent(new CustomEvent('ofap:audio-failed', { detail: detail }));
            }
        } catch (e) { /* a missing CustomEvent is not an audio problem */ }
        try {
            if (window && typeof window.toast === 'function' && typeof document !== 'undefined') {
                window.toast(document.body, 'audio unavailable — ' + state.lastError, 'error');
            }
        } catch (e) { /* the notice is best-effort; the counter is the receipt */ }
    }

    function play(name, gain) {
        var src = SAMPLES[name];
        if (!src) return false;
        if (typeof Audio !== 'function') {              // no device in this environment (tests, headless)
            state.failures += 1;
            state.lastError = 'no audio device';
            return false;
        }
        try {
            var el = state.pool[name];
            if (!el) { el = state.pool[name] = new Audio(src); el.preload = 'auto'; }
            el.volume = Math.max(0, Math.min(1, gain * cfg.volume));
            try { el.currentTime = 0; } catch (e) { /* not seekable yet — fine */ }
            var p = el.play();
            if (p && typeof p.catch === 'function') {
                p.catch(function (err) {
                    state.failures += 1;
                    state.lastError = String((err && err.message) || err || 'play() rejected');
                    announceFailure();
                });
            }
            state.plays += 1;
            state.lastPlayed = name;
            return true;
        } catch (err) {
            state.failures += 1;
            state.lastError = String((err && err.message) || err);
            announceFailure();
            return false;
        }
    }

    function onTick(tick) {
        var d = decide(tick, { cfg: cfg, symbol: state.symbol, now: Date.now(), mem: state.last });
        if (!d) return null;
        play(d.name, d.gain);
        return d;
    }

    function setSymbol(symbol) { state.symbol = String(symbol || ''); return state.symbol; }

    /* The Tape view's Chart menu writes single paths (`audio.enabled`, `audio.volume`, …) through
     * /api/control/params, so the player adopts the accepted value directly instead of round-tripping
     * the whole config. Unknown keys are ignored — the registry is the source of truth. */
    function setParam(key, value) {
        if (!(key in DEFAULTS)) return clone(cfg);
        var raw = clone(cfg);
        raw[key] = value;
        return configure(raw);
    }

    /* Read the config once at boot (the same GET the other panels use). Never throws: a panel that
     * cannot read the config stays on the safe default — silent. */
    function load() {
        try {
            if (typeof window === 'undefined' || typeof window.fetch !== 'function') return null;
            return window.fetch('/api/control/config', { headers: { accept: 'application/json' } })
                .then(function (r) { return r.json(); })
                .then(function (cfg) {
                    if (cfg && cfg.audio) configure(cfg.audio);
                    return (cfg && cfg.audio) || null;
                })
                .catch(function () { return null; });
        } catch (e) { return null; }
    }

    function status() {
        return {
            enabled: cfg.enabled, volume: cfg.volume, min_size: cfg.min_size,
            hard_multiple: cfg.hard_multiple, hard_enabled: cfg.hard_enabled,
            active_symbol_only: cfg.active_symbol_only, symbol: state.symbol,
            plays: state.plays, failures: state.failures, last_error: state.lastError,
            last_played: state.lastPlayed, samples: Object.keys(SAMPLES)
        };
    }

    window.OFAPAUDIO = {
        DEFAULTS: DEFAULTS, SAMPLES: SAMPLES,
        configure: configure, config: function () { return clone(cfg); },
        decide: decide, onTick: onTick, play: play,
        setSymbol: setSymbol, setParam: setParam, load: load, status: status, state: state
    };

    load();          // adopt whatever the config already says (silent until it says `enabled`)
})();
