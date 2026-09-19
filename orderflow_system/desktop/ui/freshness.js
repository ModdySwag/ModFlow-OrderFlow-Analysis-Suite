/* freshness.js — one store for "how old is what you are looking at".
 *
 * P1-10: every panel that displays data stamps the AGE of its newest sample here
 * (`OFAPFRESH.stamp(id, {lastMs | ageMs, kind, windowMs, source})`), and this module paints one
 * small chip into each panel's `.view-head` — the same chip pattern the cursor spine uses
 * (`OFAPCURSOR.badge`). A 1 s tick repaints the ages, so a feed that goes silent AGES on screen
 * with no further payloads: the number rising IS the proof the age is real, not stamped per poll.
 *
 * States (pure `pick()`): demo (the server said the payload is demo data — no age on a lie),
 * unknown (the clock is unknown — `age_known:false`, never invented), held (the user paused
 * updates — a deliberate hold is not a fault), fresh (under half the window), aging (to the
 * window), stale (past it — the chip says so and the section dims via `.ofap-stale`).
 *
 * The windows mirror atlas/freshness.py (depth 5 s, quote 60 s, trades 5 s, candles 60 s);
 * `test_freshness.py` pins the two tables equal, so neither side can drift alone. Payloads that
 * carry their own `window_ms` (the engine's age block, crossvenue rows) win over the table.
 *
 * T4/A5: the built-in windows are the defaults, not the law — `setWindows({depth_s, quote_s,
 * trades_s, candles_s})` (seconds, 0 = built-in) adopts the user's thresholds from Settings, and a
 * stamp that carries its own `windowMs` still wins (the payload is the per-feed truth).
 */
(function () {
    'use strict';

    /* Mirrors atlas/freshness.py WINDOWS_MS — pinned the-equal by test_freshness.py. */
    var WINDOWS = { depth: 5000, quote: 60000, trades: 5000, candles: 60000 };

    /* T4/A5: the user's thresholds, in ms. 0 = the built-in window for that kind. */
    var USER = { depth: 0, quote: 0, trades: 0, candles: 0 };

    var rows = {};      // id -> the last stamp + its computed state
    var chips = [];     // {el, id} pairs, repainted by tick()

    function windowOf(kind, override) {
        var w = Number(override) || 0;
        if (w > 0) return w;                       /* the payload's own window — the per-feed truth */
        var user = USER[kind] || 0;
        if (user > 0) return user;                 /* T4/A5: the user's threshold, when they set one */
        return WINDOWS[kind] || WINDOWS.depth;
    }

    /* Adopt the user's thresholds. Unset/invalid kinds fall back to the built-in window; an
       existing row is re-judged immediately, so the strip and chips never wait for a new sample. */
    function setWindows(spec) {
        spec = spec || {};
        Object.keys(USER).forEach(function (kind) {
            var s = Number(spec[kind + '_s']);
            USER[kind] = s > 0 ? Math.min(3600, s) * 1000 : 0;
        });
        Object.keys(rows).forEach(function (id) {
            rows[id].windowMs = windowOf(rows[id].kind, rows[id].windowOverride);
        });
        tick();
        return { depth: USER.depth, quote: USER.quote, trades: USER.trades, candles: USER.candles };
    }

    /* ── the pure half (selftested under Node) ─────────────────────────────── */

    function pick(state) {
        if (!state) return 'unknown';
        if (state.source === 'demo') return 'demo';
        if (!state.ageKnown) return 'unknown';
        if (state.paused) return 'held';
        if (state.age < state.window / 2) return 'fresh';
        if (state.age <= state.window) return 'aging';
        return 'stale';
    }

    function fmtAge(ms) {
        var s = Math.max(0, Math.round((Number(ms) || 0) / 1000));
        if (s < 100) return s + ' s';
        var m = Math.floor(s / 60);
        if (m < 60) return m + ' m ' + (s % 60 < 10 ? '0' : '') + (s % 60) + ' s';
        return Math.floor(m / 60) + ' h ' + (m % 60) + ' m';
    }

    function textFor(state, verdict) {
        if (verdict === 'demo') return 'demo data';
        if (verdict === 'unknown') return 'age unknown';
        if (verdict === 'held') return 'held · ' + fmtAge(state.age);
        if (verdict === 'aging') return 'aging · ' + fmtAge(state.age);
        if (verdict === 'stale') return 'stale — no update for ' + fmtAge(state.age);
        return 'live · ' + fmtAge(state.age);
    }

    /* ── the store ─────────────────────────────────────────────────────────── */

    function stamp(id, spec) {
        spec = spec || {};
        var at = Date.now();
        var lastMs = Number(spec.lastMs) || 0;
        var ageMs = Number(spec.ageMs) || 0;
        var ageKnown = spec.source === 'demo' ? false
            : spec.ageKnown === false ? false
                : (lastMs > 0 || spec.ageMs != null);
        rows[id] = {
            id: id, at: at, lastMs: lastMs, ageMs: ageMs, ageKnown: ageKnown,
            kind: String(spec.kind || ''),
            windowOverride: Number(spec.windowMs) || 0,
            windowMs: windowOf(spec.kind, spec.windowMs),
            source: spec.source === 'demo' ? 'demo' : '',
        };
        paint(id);
        return rows[id];
    }

    /* The live reading: a stamp with lastMs grows with the wall clock; one with only ageMs
       grows from its stamp moment — either way the number rises while nothing arrives. */
    function stateOf(row) {
        if (!row) return null;
        var age = 0;
        if (row.ageKnown) {
            age = row.lastMs > 0 ? Math.max(0, Date.now() - row.lastMs)
                                 : row.ageMs + Math.max(0, Date.now() - row.at);
        }
        var paused = !!(window.OFAPPause && window.OFAPPause.isPaused && window.OFAPPause.isPaused());
        return { age: age, window: row.windowMs, ageKnown: row.ageKnown, source: row.source, paused: paused };
    }

    function paint(id) {
        /* D-12: replaced head elements left their chip entries behind — drop the disconnected. */
        for (var i = chips.length - 1; i >= 0; i -= 1) {
            if (!chips[i].el || !chips[i].el.isConnected) chips.splice(i, 1);
        }
        var row = rows[id];
        var st = row ? stateOf(row) : null;
        var verdict = row ? pick(st) : '';
        chips.forEach(function (c) {
            if (c.id !== id || !c.el || !c.el.isConnected) return;
            if (!row) {
                c.el.textContent = '\u2014';
                c.el.className = 'ofap-fresh-chip';
                c.el.title = 'The age of what this panel displays — nothing stamped yet.';
                return;
            }
            c.el.textContent = textFor(st, verdict);
            c.el.className = 'ofap-fresh-chip is-' + verdict;
            c.el.title = 'The age of the newest sample this panel displays.'
                + (row.source === 'demo' ? ' (the server answered with demo data)' : '')
                + ' \u00b7 window ' + fmtAge(row.windowMs);
            var section = c.el.closest ? c.el.closest('.view') : null;
            if (section) section.classList.toggle('ofap-stale', verdict === 'stale');
        });
        return verdict;
    }

    function chip(host, id) {
        if (!host || typeof document === 'undefined' || !document) return null;
        var el = host.querySelector('[data-ofap-fresh]');
        if (!el) {
            el = document.createElement('span');
            el.setAttribute('data-ofap-fresh', '1');
            el.className = 'ofap-fresh-chip';
            host.appendChild(el);
        }
        if (!chips.some(function (c) { return c.el === el && c.id === id; })) chips.push({ el: el, id: id });
        paint(id);
        return el;
    }

    /* Every panel the build stamps. An explicit list (not a scan) so the set is reviewable and
       test_wiring can hold it against index.html. */
    var PANELS = ['ofx', 'heatmap', 'cvd', 'profile', 'frames', 'trackers', 'tape', 'watchlist',
                  'news', 'options', 'fundamentals', 'chart', 'scanner', 'alerts'];

    function autoChips() {
        PANELS.forEach(function (id) {
            var head = document.querySelector('.view[data-view="' + id + '"] .view-head');
            if (head) chip(head, id);
        });
    }

    function tick() {
        Object.keys(rows).forEach(paint);
        paintStrip();
    }

    /* T4/A5+A16: the ambient strip. The badge appears only when a panel showing LIVE data has gone
       stale — a deliberate hold is not a fault and demo data has no age to be late with; a panel
       whose clock is unknown is excluded, never guessed at. The oldest-sample readout is the same
       arithmetic the chips use, one number for the whole strip. */
    /* Only panels being watched can go stale in a way that matters: a parked section does not
       poll, so its age is expected, not a fault. When the section cannot be found at all, the
       age is still real — include it rather than guess. */
    function onScreen(view) {
        if (typeof document === 'undefined' || !document || typeof document.querySelector !== 'function') return true;
        var section = document.querySelector('.view[data-view="' + view + '"]');
        if (!section) return true;
        if (typeof section.closest === 'function' && section.closest('.widget-frame')) return true;
        var shell = window.OFAPSHELL;
        if (shell && typeof shell.state === 'function') {
            var st = shell.state() || {};
            if (st.mode === 'terminal') return false;     /* terminal mode, not framed: parked */
        }
        if (section.classList && typeof section.classList.contains === 'function') {
            if (!section.classList.contains('active')) return false;
        }
        return true;
    }

    function summary() {
        var staleIds = [], oldest = -1, live = 0;
        Object.keys(rows).forEach(function (id) {
            var st = stateOf(rows[id]);
            if (!st || !st.ageKnown || st.source === 'demo' || st.paused) return;
            if (!onScreen(id)) return;               /* parked panels are quiet, not late */
            live += 1;
            if (st.age > oldest) oldest = st.age;
            if (pick(st) === 'stale') staleIds.push(id);
        });
        return { stale: staleIds, oldest_ms: oldest < 0 ? 0 : Math.round(oldest), live: live };
    }

    function paintStrip() {
        if (typeof document === 'undefined' || !document || typeof document.getElementById !== 'function') return;
        var s = summary();
        var badge = document.getElementById('statusDelay');
        if (badge) {
            badge.hidden = s.stale.length === 0;
            if (s.stale.length) {
                badge.title = 'no update for: ' + s.stale.join(', ')
                    + ' \u2014 the thresholds live in Settings (atlas freshness)';
            }
        }
        var age = document.getElementById('statusOldest');
        if (age) age.textContent = s.live ? fmtAge(s.oldest_ms) : '\u2014';
        var hold = document.getElementById('statusPause');
        if (hold) hold.hidden = !(window.OFAPPause && window.OFAPPause.isPaused && window.OFAPPause.isPaused());
    }

    function list() {
        var out = [];
        Object.keys(rows).forEach(function (id) {
            var st = stateOf(rows[id]);
            out.push({ id: id, verdict: pick(st), age_ms: Math.round(st.age),
                       window_ms: st.window, age_known: st.ageKnown, source: rows[id].source });
        });
        return out;
    }

    if (typeof setInterval === 'function') setInterval(tick, 1000);

    /* Adopt the user's thresholds at boot — the same GET the other panels use. Silent on any
       failure: the built-in windows stand. */
    function loadWindows() {
        if (typeof window === 'undefined' || typeof window.fetch !== 'function') return null;
        return window.fetch('/api/control/config', { headers: { accept: 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (cfg) {
                setWindows((cfg && cfg.atlas && cfg.atlas.freshness) || {});
                return cfg;
            })
            .catch(function () { return null; });
    }
    loadWindows();
    if (document && typeof document.addEventListener === 'function') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', autoChips);
        else autoChips();
    }

    window.OFAPFRESH = { stamp: stamp, chip: chip, pick: pick, fmtAge: fmtAge, textFor: textFor,
        window: windowOf, state: stateOf, list: list, rows: rows, PANELS: PANELS,
        setWindows: setWindows, summary: summary, onScreen: onScreen };
})();
