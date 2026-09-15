/* intent.js - one arbiter for "the user is doing something" vs "the feed is doing something".
 *
 * The problem this exists for: a polled reload lands while you are zooming and the view jumps; a
 * selection is wiped by the next repaint; a filter box loses what you typed because a re-render beat
 * you to it. Every one of those is the same bug in a different panel.
 *
 * The rule here is simple and absolute:
 *   - a gesture takes a LEASE on its surface (time-boxed, auto-renewed while input keeps coming);
 *   - while a lease is held, updates that would move the view, scroll a strip or replace a selection
 *     are DEFERRED into a queue - never dropped - and applied the moment the lease ends;
 *   - nothing in this file touches the feed, the engine or the socket. Ingest keeps running while
 *     the view is being held, which is the whole point: you can work the screen without missing data.
 *
 * Surfaces are named by markup: put data-surface="ofx" on a view section and this layer knows whose
 * gesture it is without that panel knowing this layer exists.
 */
(function () {
    'use strict';

    const GRACE_MS = 260;          // after the last input event, before the surface is free again
    const LEASE_MAX_MS = 12000;    // a stuck pointer must not hold the view for ever

    const leases = Object.create(null);     // surface -> {until, last, timer}
    const queues = Object.create(null);     // surface -> Map(key -> fn)   last-wins per key
    const writes = new Map();               // key -> fn                   coalesced writes
    const S = { frozen: false, feed: { ticks: 0, at: 0, rate: 0 }, holds: 0, deferred: 0, applied: 0, strips: 0 };

    function nowMs() { return Date.now(); }

    function surfaceOf(node) {
        let el = node;
        while (el && el.getAttribute) {
            const s = el.getAttribute('data-surface');
            if (s) return s;
            el = el.parentElement;
        }
        return '';
    }

    function lease(surface, ms) {
        if (!surface) return;
        let l = leases[surface];
        if (!l) { l = leases[surface] = { until: 0, last: 0, timer: 0, count: 0 }; }
        const span = Math.max(400, Math.min(LEASE_MAX_MS, ms || 1500));
        l.until = nowMs() + span;
        l.last = nowMs();
        l.count += 1;
        S.holds = Object.keys(leases).length;
        paint();
        document.dispatchEvent(new CustomEvent('ofap:hold', { detail: { surface: surface, until: l.until } }));
        if (l.timer) clearTimeout(l.timer);
        l.timer = setTimeout(function () { release(surface); }, span + GRACE_MS);
    }

    function held(surface) {
        if (S.frozen) return true;                    // a frozen view holds every surface
        const l = surface ? leases[surface] : null;
        if (!l) return false;
        return nowMs() < l.until;
    }

    function release(surface) {
        const l = leases[surface];
        if (!l) return;
        if (l.timer) clearTimeout(l.timer);
        delete leases[surface];
        S.holds = Object.keys(leases).length;
        flush(surface);          // held updates for this surface
        flushWrites();           // and any coalesced write, once nothing is held at all
        paint();
        document.dispatchEvent(new CustomEvent('ofap:release', { detail: { surface: surface } }));
    }

    let seq = 0;                   // one key per deferral, so nothing is silently overwritten

    /* Defer if the surface is busy, run now if it is not. This is the only call panels need. */
    function defer(surface, fn) {
        if (!fn) return false;
        if (!held(surface)) { fn(); return false; }
        let q = queues[surface];
        if (!q) q = queues[surface] = new Map();
        seq += 1;
        q.set(surface + ':' + seq, fn);
        paint();
        return true;
    }

    /* Same, but keyed: a burst of polls leaves exactly one pending apply per key. */
    function deferKeyed(surface, key, fn) {
        if (!fn) return false;
        if (!held(surface)) { fn(); return false; }
        let q = queues[surface];
        if (!q) q = queues[surface] = new Map();
        q.set(surface + ':' + key, fn);
        return true;
    }

    function flush(surface) {
        const q = queues[surface];
        if (!q || !q.size) return;
        delete queues[surface];
        q.forEach(function (fn) {
            S.applied += 1;
            try { fn(); } catch (e) { /* a failed apply must not stop the rest */ }
        });
        paint();
    }

    /* Writes (config posts, exports, alert creation) are coalesced: last value per key wins, and
       nothing is sent mid-gesture - a half-typed threshold should never reach the server. */
    function queueWrite(key, fn) {
        writes.set(key, fn);
        if (!anyHeld()) flushWrites();
        return true;
    }

    function flushWrites() {
        if (!writes.size || anyHeld()) return;
        const pending = [...writes.entries()];
        writes.clear();
        pending.forEach(function (pair) {
            try { pair[1](); } catch (e) { /* logged by the caller's own path */ }
        });
    }

    function anyHeld() {
        if (S.frozen) return true;
        return Object.keys(leases).some(function (s) { return nowMs() < leases[s].until; });
    }

    /* The two levels the owner asked for, kept distinct and named: a held VIEW is not a stopped
       FEED. The freeze below stops presentation updates; ingest is never touched from here. */
    function freezeView(on) {
        S.frozen = Boolean(on);
        if (!S.frozen) { flushAll(); }
        document.dispatchEvent(new CustomEvent('ofap:view', { detail: status() }));
        paint();
    }

    function flushAll() {
        Object.keys(queues).forEach(flush);
        flushWrites();
    }

    function setStrips(n) {
        S.strips = Number(n) || 0;
        paint();
    }

    function setFeed(info) {
        const d = info || {};
        if (typeof d.ticks === 'number') {
            const dt = nowMs() - (S.feed.at || nowMs());
            if (S.feed.at && dt > 200) S.feed.rate = Math.round((d.ticks - S.feed.ticks) / (dt / 1000));
            S.feed.ticks = d.ticks;
            S.feed.at = nowMs();
        }
        if (typeof d.live === 'boolean') S.feed.live = d.live;
    }

    function status() {
        const surfaces = Object.keys(leases).filter(function (s) { return nowMs() < leases[s].until; });
        return { frozen: S.frozen, surfaces: surfaces, holds: surfaces.length,
                 feed: { ticks: S.feed.ticks, rate: S.feed.rate, live: S.feed.live !== false },
                 strips: S.strips,
                 deferred: [...Object.keys(queues)].reduce(function (n, s) { return n + queues[s].size; }, 0),
                 writes: writes.size, applied: S.applied };
    }

    /* The chip: always says what is happening, so a held screen never looks like a broken one. */
    function chip() {
        let el = document.getElementById('ofapHold');
        if (!el) {
            el = document.createElement('div');
            el.id = 'ofapHold';
            el.className = 'ofap-hold';
            /* Top right, beside the pause chip: one cluster, one story. */
            const host = document.getElementById('ofapPause') && document.getElementById('ofapPause').parentElement
                || document.querySelector('.statusbar') || document.body;
            host.appendChild(el);
        }
        return el;
    }

    function paint() {
        const st = status();
        /* A strip holding a reader's place is also "the view is held": show the same chip. */
        if (!st.frozen && !st.holds && st.strips) st.holds = 1;
        const el = chip();
        const busy = st.frozen || st.holds;
        el.classList.toggle('on', !!busy);
        el.textContent = !busy ? ''
            : (st.frozen
                ? '⏸ view held — feed live'
                : '✋ ' + st.surfaces.join(' · ') + ' held — feed live') +
              (st.feed.rate ? ' · ' + st.feed.rate + ' tick/s' : '') +
              (st.strips ? ' · ' + st.strips + ' strip' + (st.strips === 1 ? '' : 's') + ' holding your place' : '') +
              (st.deferred ? ' · ' + st.deferred + ' update' + (st.deferred === 1 ? '' : 's') + ' waiting' : '');
    }

    /* Auto-lease: any real input over a tagged surface. Panels do not need to know. */
    ['pointerdown', 'mousedown', 'touchstart', 'wheel', 'keydown', 'input', 'dblclick'].forEach(function (ev) {
        document.addEventListener(ev, function (e) {
            const s = surfaceOf(e.target);
            if (s) lease(s, ev === 'wheel' ? 900 : 1400);
        }, { capture: true, passive: true });
    });
    ['pointerup', 'mouseup', 'touchend', 'keyup', 'change'].forEach(function (ev) {
        document.addEventListener(ev, function (e) {
            const s = surfaceOf(e.target);
            if (!s) return;
            const l = leases[s];
            if (l) { l.until = nowMs() + GRACE_MS; l.last = nowMs(); }
        }, { capture: true, passive: true });
    });
    /* Keyboard work in a field, and focus changes, count as interaction with that surface too. */
    document.addEventListener('focusin', function (e) {
        const s = surfaceOf(e.target);
        if (s && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName || '')) lease(s, 6000);
    }, true);
    document.addEventListener('focusout', function (e) {
        const s = surfaceOf(e.target);
        if (s) release(s);
    }, true);

    setInterval(function () { flushWrites(); }, 1500);

    window.OFAPINTENT = {
        lease: lease, release: release, held: held, defer: defer, deferKeyed: deferKeyed,
        queueWrite: queueWrite, flushWrites: flushWrites, freezeView: freezeView, setFeed: setFeed,
        setStrips: setStrips,
        status: status, anyHeld: anyHeld,
    };
})();
