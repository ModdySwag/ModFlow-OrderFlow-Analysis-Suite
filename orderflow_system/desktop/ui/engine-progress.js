/* engine-progress.js — §132: the engine's progress bar, beside the Start/Stop buttons.
 *
 * The wait is real and asymmetric. Measured on the owner's machine: START answers in ~0.5 s and the
 * first tick lands ~1.8 s later, while STOP holds the request for ~10 s (the atlas history flush) and
 * the old shell showed nothing for any of it — a disabled button and a pill that said "Running"
 * until the stop finally landed. This module turns the engine's own stages
 * (`EngineController.STAGE_PLAN` — keys, the route's truth) into a small bar: GREEN on the way up,
 * RED on the way down, the stage named, the seconds ticking, and it fades only when the state is
 * genuinely terminal. "Started" is never claimed before a tick has actually landed.
 *
 * The pure half is selftested under Node (`engine-progress.selftest.js`): the phase, the captions,
 * the fill's arithmetic (monotone, bounded, never complete inside a stage) and the settlement text.
 * The DOM half is one element and writes four things — hidden, class, width, caption — and never
 * touches the rest of the bar.
 */
(function () {
    'use strict';

    var VERSION = '1.0.0';

    /* How much of a stage's slot the bar may fill while the stage is still RUNNING: asymptotic, so a
       slow stage creeps instead of claiming the next one. Cap 0.86 of the slot, over ~2.6 s of tau. */
    var CREEP_CAP = 0.86;
    var CREEP_TAU_MS = 2600;
    /* Once the engine says running, the bar stays up (green, "waiting for ticks") until a print
       lands — or this long, after which it settles with the honest caption instead of waiting
       forever on a feed that never ticks. */
    var TICKS_GRACE_MS = 8000;
    /* How long a terminal stage stays visible before the bar fades ("live" / "stopped"). */
    var HOLD_MS = 1400;

    var UP_LABEL = {
        config: 'reading your setup',
        instruments: 'preparing instruments',
        build: 'building the run',
        connect: 'connecting the feed',
        ready: 'waiting for ticks',
        failed: 'start failed',
    };
    var DOWN_LABEL = {
        feeds: 'closing the feed',
        history: 'flushing history',
        release: 'finishing the shutdown',
        closed: 'stopped',
    };

    function str(v) { return String(v == null ? '' : v); }

    /* ── the pure half ─────────────────────────────────────────────────────────────────────── */

    /* Which direction the bar is showing, from the engine's own state + stage. Null = nothing to
       show. `starting`/`stopping` are the transitions; `running` with stage `ready` is the warming
       window (the engine is up but no print has landed yet); `error` is a failed start. */
    function phase(state, stage) {
        var s = str(state);
        if (s === 'starting') return 'up';
        if (s === 'stopping') return 'down';
        if (s === 'running' && stage === 'ready') return 'warm';
        if (s === 'error') return 'fail';
        return null;
    }

    function label(stage) {
        var key = str(stage);
        return UP_LABEL[key] || DOWN_LABEL[key] || key;
    }

    /* The bar's fill: completed stages own their whole slot; the running stage owns a bounded creep.
       `plan` is the ordered keys the route published for this direction, `stage` the current key. */
    function fill(plan, stage, stageStartedMs, nowMs, tauMs) {
        var keys = Array.isArray(plan) ? plan : [];
        if (!keys.length) return 0;
        var idx = keys.indexOf(str(stage));
        if (idx < 0) return 0;                                  // a stage the plan does not name
        var slot = 1 / keys.length;
        var elapsed = Math.max(0, nowMs - stageStartedMs);
        var tau = tauMs > 0 ? tauMs : CREEP_TAU_MS;
        var creep = CREEP_CAP * (1 - Math.exp(-elapsed / tau));
        return Math.min(1, idx * slot + slot * creep);
    }

    /* The caption: the stage's words, and the seconds it has been running (whole seconds — a
       twitching decimal reads as noise at this size). */
    function caption(stage, elapsedMs) {
        var text = label(stage);
        var secs = Math.floor(Math.max(0, elapsedMs) / 1000);
        return secs >= 1 ? text + ' · ' + secs + ' s' : text;
    }

    /* The sentence a settled bar carries before it fades. `live` is only ever used when a print
       really landed; a feed that never ticks gets the honest version. */
    function settle(state, ticks) {
        var s = str(state);
        if (s === 'error') return 'start failed';
        if (s === 'stopped') return 'stopped';
        if (s === 'running') return ticks > 0 ? 'live' : 'connected — no ticks yet';
        return '';
    }

    var PURE = { phase: phase, label: label, fill: fill, caption: caption, settle: settle,
                 CREEP_CAP: CREEP_CAP, TICKS_GRACE_MS: TICKS_GRACE_MS, HOLD_MS: HOLD_MS };

    /* ── the DOM half ──────────────────────────────────────────────────────────────────────── */

    var dom = { node: null, cap: null, fillEl: null };
    var last = null;         // the last status payload applied
    var settledAt = 0;       // when a terminal sentence was first shown (epoch ms)
    var settledText = '';
    var warmedAt = 0;        // when `running` was first seen (drives the ticks grace)
    /* `armed` is what keeps the bar honest about WHEN it may appear: only a transition it actually
       witnessed arms it, and once it has settled (and faded) it stays quiet until the next one.
       Measured without this: every 2 s status poll re-showed "live" for the hold, so a running
       engine flashed the bar twice a minute. */
    var armed = false;
    var busyState = false;   // is the ENGINE mid-transition? (drives the shell's fast poll)
    /* The direction the shell's own button set in motion, and when. While it is set, payloads that
       describe the state we just LEFT are dropped: measured, a status read already in flight when
       Stop was pressed painted "live / 100%" over the fresh red bar, and its `running` also stopped
       the fast poll — the red bar then sat frozen for five seconds. A transition the user started
       outranks a poll that started before it. */
    var expect = '';
    var expectAt = 0;
    var EXPECT_TTL_MS = 90000;
    /* How long a read of the state we just LEFT may be treated as stale. Bounded on purpose: a
       start that FAILS lands in stopped/error and must be allowed to say so (measured without the
       bound: the pre-click "stopped" read flashed over a fresh green bar once). */
    var STALE_MS = 1500;

    /* The bar's own beats. ONE timer, handed to the pause registry (the suite's G-09 rule: every
       UI interval is guarded or on the frozen allow-list — and `P` freezing the board while a
       progress bar still animates would be a lie). The local tick runs at ~8 Hz only while the bar
       is on screen; the status re-poll rides every fourth beat and only while a transition is
       running, so an idle app pays two boolean checks and nothing else. It polls the route itself
       because the shell's own poll is held during user intent (measured: that gate delayed the
       bar's first frame of a stop by ~4 s and the whole feeds/history leg went unseen). */
    var beatId = 0;
    var beatN = 0;

    function pollOnce() {
        var call = window.api;
        if (typeof call !== 'function') return;
        Promise.resolve(call('/api/control/engine/status'))
            .then(function (st) { if (st && typeof st === 'object' && 'state' in st) apply(st, Date.now()); })
            .catch(function () { /* a hint, not a contract: a missed poll costs one frame */ });
    }

    function startBeat() {
        beatId = setInterval(function () {
            var now = Date.now();
            if (active()) tick(now);
            if (busy() && (++beatN % 4 === 0)) pollOnce();
        }, 120);
        if (window.OFAPPause && OFAPPause.register) OFAPPause.register(beatId, startBeat);
        return beatId;
    }

    function mount(host) {
        if (!host) return null;
        dom.node = host.querySelector ? host.querySelector('.ep') : null;
        if (!dom.node) {
            dom.node = document.createElement('span');
            dom.node.className = 'ep';
            dom.node.id = 'engineProgress';
            dom.node.innerHTML = '<span class="ep-cap"></span>'
                + '<span class="ep-track"><span class="ep-fill"></span></span>';
            /* FIRST child of the cluster, in flow: the top bar's spacer absorbs the width, so the
               bar can grow without ever reaching a neighbour — and it stays the element nearest the
               buttons it describes (§133: an absolutely-positioned version covered the mode switch). */
            host.insertBefore(dom.node, host.firstChild);
        }
        dom.cap = dom.node.querySelector('.ep-cap');
        dom.fillEl = dom.node.querySelector('.ep-fill');
        if (!beatId) startBeat();
        return dom.node;
    }

    function ticksOf(status) {
        var rows = (status && status.per_symbol) || [];
        var n = 0;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i] && Number(rows[i].ticks || 0) > 0) n++;
        }
        return n;
    }

    /* Apply a status payload (the same object the shell's own poll already carries). Four DOM
       writes. Called from renderStatus() and from the fast poll while a transition runs. */
    function apply(status, nowMs) {
        if (!dom.node) return;
        var now = nowMs || Date.now();
        var state = str(status && status.state);
        var stage = str(status && status.stage);
        last = status || {};

        if (state === 'running' && !warmedAt) warmedAt = now;
        if (state !== 'running') warmedAt = 0;

        if (expect && Date.now() - expectAt > EXPECT_TTL_MS) expect = '';   // a transition that never landed
        if (expect && Date.now() - expectAt < STALE_MS) {                   // a read of the old state
            if (expect === 'down' && (state === 'running' || state === 'starting')) return;
            if (expect === 'up' && (state === 'stopping' || state === 'stopped')) return;
        }
        var p = phase(state, stage);
        busyState = (state === 'starting' || state === 'stopping') || !!expect;
        if (p === 'up' || p === 'down') armed = true;

        if (p === null) {
            /* Terminal: hold the closing sentence briefly, then hide. */
            var text = settle(state, ticksOf(status));
            if (text) {
                if (!settledAt) { settledAt = now; settledText = text; }
                if (now - settledAt < HOLD_MS) {
                    paint(state === 'stopped' ? 'down' : 'up', settledText, 1, now);
                    return;
                }
            }
            hide();
            settledAt = 0;
            settledText = '';
            armed = false;                 // the story is over; the next transition re-arms it
            return;
        }

        if (p === 'warm' && !armed) {      // running, but this page never saw the start
            hide();
            return;
        }

        settledAt = 0;
        settledText = '';
        var plan = (status && status.stage_plan) || [];
        var startedAt = Number(status && status.stage_at ? status.stage_at * 1000 : now);
        var elapsed = now - startedAt;

        if (p === 'warm') {
            var ticks = ticksOf(status);
            var waited = warmedAt ? now - warmedAt : 0;
            if (ticks > 0 || waited > TICKS_GRACE_MS) {
                var ending = settle('running', ticks);
                paint('up', ending, 1, now);
                settledAt = now;
                settledText = ending;
                return;
            }
            /* Creep through the open-ended last step while the feed warms — never completing the
               run until a tick really lands. */
            paint('up', caption(stage, elapsed), Math.min(0.985, fill(plan, stage, startedAt, now)), now);
            return;
        }

        paint(p === 'fail' ? 'down' : p, caption(stage, elapsed),
            fill(plan, stage, startedAt, now), now);
    }

    /* One repaint: hidden, class, width, caption. `title` carries the whole story — the stages and
       their measured times out of `stage_log`, the same evidence the handoff quotes. */
    function paint(kind, text, fraction, now) {
        if (!dom.node) return;
        dom.node.hidden = false;
        dom.node.className = 'ep ' + kind + (fraction >= 0.999 ? ' done' : '');
        dom.cap.textContent = text;
        dom.fillEl.style.width = Math.round(Math.max(0, Math.min(1, fraction)) * 100) + '%';
        var log = (last && last.stage_log) || [];
        var story = log.map(function (row) { return label(row.stage) + ' ' + row.ms + ' ms'; }).join(' · ');
        var at = Number((last && last.stage_at) || 0);
        var inStep = at > 0 ? ' · ' + Math.max(0, Math.round(((now || Date.now()) - at * 1000) / 1000)) + ' s in this step' : '';
        dom.node.title = text + (story ? ' — ' + story : '') + inStep;
    }

    function hide() {
        if (!dom.node) return;
        expect = '';                       // the story ended; the next transition re-arms it
        dom.node.hidden = true;
        dom.node.title = '';
        dom.cap.textContent = '';
        dom.fillEl.style.width = '0%';
    }

    /* A transition the shell STARTED (the Start/Stop/Restart buttons call this): arm the bar and
       put a first frame up immediately, so the click answers without waiting for a poll. Measured
       without it: a start finishes inside ~0.5 s, faster than the first poll, so the bar never
       appeared at all — and the page had no licence to show the warming window either. */
    function begin(kind) {
        armed = true;
        busyState = true;
        expect = (kind === 'down' ? 'down' : 'up');
        expectAt = Date.now();
        if (!dom.node) return;
        last = last || {};
        paint(kind === 'down' ? 'down' : 'up',
              kind === 'down' ? 'stopping the engine' : 'starting the engine', 0.03, Date.now());
    }

    /* The ~120 ms local tick: no fetch — the arithmetic above re-run against the clock, so the bar
       moves smoothly between the 2 s status polls. */
    function tick(nowMs) {
        if (!dom.node || dom.node.hidden || !last) return;
        apply(last, nowMs || Date.now());
    }

    /* Is a transition (or its brief hold) on screen? The shell's local tick runs while this is
       true, and never else. */
    function active() {
        return !!(dom.node && !dom.node.hidden);
    }

    /* Is the ENGINE mid-transition (or warming, before this page has settled it)? The shell's
       status re-poll runs while this is true. It is deliberately wider than active(): measured, a
       stop's first stages (feeds 271 ms, history 9 ms) were missed entirely because the bar was
       still hidden when the transition began, so the poll stayed at its 2 s cadence and the caption
       arrived four seconds late. */
    function busy() {
        if (busyState) return true;
        var state = str(last && last.state);
        if (state === 'running' && str(last && last.stage) === 'ready' && !settledAt) return true;
        return false;
    }

    window.OFAPENGINEPROGRESS = {
        version: VERSION,
        pure: PURE,
        mount: mount,
        apply: apply,
        tick: tick,
        active: active,
        busy: busy,
        begin: begin,
        startBeat: startBeat,
        hide: hide,
        label: label,
    };
})();
