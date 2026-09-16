/* bus.js — the terminal's delivery layer: one subscription per (endpoint, params), refcounted.
 *
 * The problem it exists for: a widget board is full of panels looking at the same thing. Twelve
 * widgets on one symbol would otherwise means twelve polls of the same endpoint per interval, and
 * this suite's own API is behind a single local server — the cost is real, and so is the way the
 * screen flickers when twelve independent fetches land at twelve different moments.
 *
 * So: subscribers join a CHANNEL. A channel is identified by what actually determines the response —
 * the method, the URL and the params (order-insensitive, volatile params like `ts`/`_` stripped) — and
 * it owns exactly one timer and one in-flight request. The first subscriber starts it, the last one
 * stops it, and everybody in between gets the same payload on the same tick.
 *
 * Two ways in:
 *   - `OFAPBUS.subscribe({url, params, intervalMs}, fn)` for code that polls;
 *   - `OFAPBUS.install(['/api/atlas/'])` to wrap the global fetch, which then coalesces concurrent
 *     IDENTICAL GETs (twelve widgets asking the same thing in the same moment cost one request) and
 *     counts what it did. Opt-in by prefix, pass-through for everything else, and the response object
 *     handed back is the real one — panels cannot tell.
 *
 * It is presentation-side only: it never talks to the engine, never writes storage, and if it is not
 * loaded every panel keeps doing exactly what it did before.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VOLATILE = { ts: 1, _: 1, _t: 1, cache: 1, nocache: 1, t: 1 };   // params that only defeat caches
    const hasWindow = typeof window !== 'undefined';
    const hasDom = typeof document !== 'undefined' && !!document.createElement;

    const state = {
        channels: new Map(),          // key → channel
        prefixes: [],                 // install() prefixes, longest first
        patched: null,                // the original window.fetch while wrapped, else null
        counters: { fetches: 0, delivered: 0, coalesced: 0, failed: 0, started: 0, stopped: 0 },
    };

    function now() {
        return (hasWindow && window.performance && window.performance.now)
            ? window.performance.now() : Date.now();
    }

    function canon(url, params, method) {
        const list = [];
        const put = (k, v) => {
            const key = String(k);
            if (VOLATILE[key.toLowerCase()]) return;                  // a cache-buster is not a parameter
            if (v === undefined || v === null || v === '') return;
            list.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(v)));
        };
        if (params && typeof params === 'object') {
            Object.keys(params).sort().forEach((k) => put(k, params[k]));
        }
        const base = String(url || '');
        const query = base.indexOf('?') >= 0 ? base.split('?')[1] : '';
        if (query) {
            query.split('&').forEach((pair) => {
                const eq = pair.indexOf('=');
                put(eq < 0 ? pair : pair.slice(0, eq), eq < 0 ? '' : decodeURIComponent(pair.slice(eq + 1)));
            });
        }
        const bare = base.split('?')[0];
        list.sort();
        return String(method || 'GET').toUpperCase() + ' ' + bare + (list.length ? '?' + list.join('&') : '');
    }

    function withQuery(url, params) {
        const extra = [];
        if (params && typeof params === 'object') {
            Object.keys(params).sort().forEach((k) => {
                const v = params[k];
                if (v === undefined || v === null || v === '') return;
                extra.push(encodeURIComponent(k) + '=' + encodeURIComponent(String(v)));
            });
        }
        if (!extra.length) return String(url);
        const base = String(url);
        return base + (base.indexOf('?') >= 0 ? '&' : '?') + extra.join('&');
    }

    function doFetch(url, params, method, init) {
        if (typeof fetch !== 'function') return Promise.reject(new Error('fetch is not available'));
        const target = withQuery(url, params);
        const opts = Object.assign({}, init || {}, { method: String(method || 'GET').toUpperCase() });
        return fetch(target, opts);
    }

    function deliver(channel, result) {
        state.counters.delivered += channel.listeners.length;
        channel.last = result;
        channel.listeners.slice().forEach((fn) => {
            try {
                fn(result, channel);
            } catch (err) {
                if (hasWindow && window.console) console.warn('[bus] listener failed', err);
            }
        });
    }

    function tick(channel) {
        if (channel.inFlight) {                       // a slow server must not queue requests up
            channel.skipped += 1;
            state.counters.coalesced += 1;
            return;
        }
        channel.inFlight = true;
        state.counters.fetches += 1;
        channel.fetches += 1;
        doFetch(channel.url, channel.params, channel.method, channel.init).then(
            (response) => (channel.asJson ? response.json() : response),
            (err) => ({ error: String(err && err.message ? err.message : err) })
        ).then((payload) => {
            channel.inFlight = false;
            channel.lastAt = now();
            if (payload && payload.error) {
                state.counters.failed += 1;
                channel.failures += 1;
            } else if (channel.asJson && payload && typeof payload === 'object' && 'ok' in payload && payload.ok === false) {
                state.counters.failed += 1;
                channel.failures += 1;
            }
            deliver(channel, payload);
        });
    }

    function channelKey(spec) {
        if (spec && spec.key) return String(spec.key);
        return canon(spec && spec.url, spec && spec.params, spec && spec.method);
    }

    /* Join a channel — or start it if you are first. Returns the way out. */
    /* Channels open and close as views come and go, and the status bar's chip is painted by the shell —
       which only hears about shell events, so the chip used to lag a channel that a view switch started
       (measured: chip '3 sub · 2 ch' while telemetry said 1 channel / 1 subscriber). Announce the
       transition where it happens, with a count the observer can check: the event used to carry
       `state.subscribers`, a field this module never maintained — so every event said `undefined`, and
       the one number nobody could verify was the one that appeared to disagree with telemetry(). The
       document is optional (this module loads headless too). */
    function subscriberCount() {
        let n = 0;
        state.channels.forEach((channel) => { n += channel.refs; });
        return n;
    }

    function announce(action, key) {
        try {
            if (typeof document !== 'undefined' && document && document.dispatchEvent) {
                document.dispatchEvent(new CustomEvent('ofap:bus', { detail: {
                    action: action, key: key || '', channels: state.channels.size,
                    subscribers: subscriberCount(), version: VERSION,
                } }));
            }
        } catch (e) { /* a missing CustomEvent is not a data problem */ }
    }

    function subscribe(spec, listener) {
        spec = spec || {};
        if (!spec.url) throw new Error('OFAPBUS.subscribe needs a url');
        const key = channelKey(spec);
        let channel = state.channels.get(key);
        let created = false;
        if (!channel) {
            const intervalMs = Math.max(100, Number(spec.intervalMs) || 2000);
            channel = {
                key: key, url: String(spec.url), params: spec.params || null,
                method: (spec.method || 'GET').toUpperCase(), init: spec.init || null,
                asJson: spec.asJson !== false, intervalMs: intervalMs,
                listeners: [], refs: 0, fetches: 0, failures: 0, skipped: 0,
                inFlight: false, lastAt: 0, last: null, startedAt: now(), timer: null,
            };
            state.channels.set(key, channel);
            created = true;
            state.counters.started += 1;
            if (spec.immediate !== false) tick(channel);
            channel.timer = setInterval(() => tick(channel), intervalMs);
        }
        channel.refs += 1;
        /* announced after the join, so the event's counts are the post-join truth (and match telemetry) */
        if (created) announce('open', key);
        if (typeof listener === 'function') {
            channel.listeners.push(listener);
            if (channel.last) {
                /* A late subscriber starts from the payload already on the wire, not from blank. */
                try {
                    listener(channel.last, channel);
                } catch (err) {
                    if (hasWindow && window.console) console.warn('[bus] listener failed', err);
                }
            }
        }
        return function unsubscribe() {
            channel.refs -= 1;
            if (typeof listener === 'function') {
                const at = channel.listeners.indexOf(listener);
                if (at >= 0) channel.listeners.splice(at, 1);
            }
            if (channel.refs <= 0) stop(channel.key);
        };
    }

    /* Keep a channel warm without listening to it (a widget that only wants the data cached). */
    function poll(spec) {
        return subscribe(Object.assign({}, spec, { immediate: true }), null);
    }

    function stop(key) {
        const channel = state.channels.get(key);
        if (!channel) return false;
        if (channel.timer) clearInterval(channel.timer);
        state.channels.delete(key);
        announce('close', key);
        state.counters.stopped += 1;
        return true;
    }

    function stopAll() {
        const keys = Array.from(state.channels.keys());
        keys.forEach(stop);
        return keys.length;
    }

    /* A one-shot GET that is shared with anyone asking for the same thing in the same moment. */
    const inFlight = new Map();

    function request(url, params, options) {
        const key = canon(url, params, (options && options.method) || 'GET');
        const asJson = !(options && options.asJson === false);
        if (options && options.force) return doFetch(url, params, 'GET', options).then(jsonOf);
        if (inFlight.has(key)) {
            state.counters.coalesced += 1;
            return inFlight.get(key);
        }
        state.counters.fetches += 1;
        const promise = doFetch(url, params, 'GET', options).then(jsonOf).finally(() => inFlight.delete(key));
        inFlight.set(key, promise);
        return promise;

        function jsonOf(response) {
            return asJson ? response.json() : response;
        }
    }

    /* Wrap the global fetch for chosen URL prefixes. Concurrent identical GETs become one request and
       everything is counted; a call that does not match a prefix is passed through untouched. */
    function install(prefixes) {
        const list = (Array.isArray(prefixes) ? prefixes : [prefixes]).filter(Boolean).map(String);
        state.prefixes = list.sort((a, b) => b.length - a.length);
        if (!state.prefixes.length || !hasWindow || typeof window.fetch !== 'function') return 0;
        if (state.patched) return state.prefixes.length;
        const original = window.fetch.bind(window);
        state.patched = original;
        window.fetch = function (input, init) {
            const url = typeof input === 'string' ? input : (input && input.url) || '';
            const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
            const hit = state.prefixes.some((prefix) => url.indexOf(prefix) === 0);
            if (!hit || method !== 'GET') return original(input, init);
            const key = canon(url, null, 'GET');
            if (inFlight.has(key)) {
                state.counters.coalesced += 1;
                return inFlight.get(key).then((shared) => shared.toResponse());
            }
            state.counters.fetches += 1;
            const promise = original(input, init).then((response) => {
                const contentType = (response.headers && response.headers.get
                    ? response.headers.get('content-type') : '') || 'application/json';
                /* §56: a binary payload (the /bin heat wire) must pass through with its body
                   UNREAD, and every caller — initiated or coalesced — gets its own clone. The old
                   path fed an octet-stream to response.json(), which consumed the body, and the
                   failure branch then handed the consumed original to the caller: every bin fetch
                   died with "body stream already read" and the engine view silently fell back to
                   the JSON route. */
                if (contentType.indexOf('json') === -1) {
                    inFlight.delete(key);
                    return { payload: null, toResponse: function () { return response.clone(); } };
                }
                const meta = { status: (response && response.status) || 200,
                               statusText: (response && response.statusText) || 'OK' };
                const rebuild = (payload) => () => new Response(JSON.stringify(payload), {
                    status: meta.status, statusText: meta.statusText,
                    headers: { 'Content-Type': contentType },
                });
                /* Every caller gets its OWN Response built from the one body we read, with the real
                   status kept — so a 503 stays a 503 for everyone instead of a rebuilt 200, and no
                   two callers ever share a single response object whose body one of them consumed. */
                return response.json().then(function (payload) {
                    /* Coalescing is for requests still IN FLIGHT. Leaving the settled promise in the map
                       made the first answer stand in for that URL for the life of the page (cache-busters
                       are dropped by canon, so nothing ever re-keyed): measured with the shipped
                       configuration, a CVD panel counted 7 fetches while the server logged 0, and its
                       "updated" stamp froze. Callers that joined while it was in flight already hold this
                       promise, so releasing the key cannot cut anyone off. */
                    inFlight.delete(key);
                    return { payload: payload, toResponse: rebuild(payload) };
                }, function () {
                    /* Headers said JSON but the body would not parse — the original stream is
                       already consumed, so keep only the status and hand back an empty body. */
                    inFlight.delete(key);
                    return { payload: null, toResponse: function () { return new Response('', {
                        status: meta.status, statusText: meta.statusText }); } };
                });
            }, function (err) {
                inFlight.delete(key);
                state.counters.failed += 1;
                throw err;
            });
            inFlight.set(key, promise);
            return promise.then(function (shared) { return shared.toResponse(); });
        };
        return state.prefixes.length;
    }

    function uninstall() {
        if (state.patched && hasWindow) {
            window.fetch = state.patched;
            state.patched = null;
        }
        state.prefixes = [];
        return true;
    }

    function telemetry() {
        const rows = Array.from(state.channels.values()).map((channel) => ({
            key: channel.key, refs: channel.refs, listeners: channel.listeners.length,
            intervalMs: channel.intervalMs, fetches: channel.fetches, failures: channel.failures,
            skipped: channel.skipped, age: Math.round(now() - channel.startedAt),
            lastAt: channel.lastAt ? Math.round(channel.lastAt) : 0,
            lastOk: !!(channel.last && !(channel.last && channel.last.error)),
        }));
        const subscribers = subscriberCount();
        const fetched = state.counters.fetches;
        const wouldHaveBeen = fetched + state.counters.coalesced;
        return {
            version: VERSION,
            channels: rows.length,
            subscribers: subscribers,
            fetches: fetched,
            delivered: state.counters.delivered,
            coalesced: state.counters.coalesced,
            failed: state.counters.failed,
            inFlightRequests: inFlight.size,
            installed: state.prefixes.slice(),
            saved: state.counters.coalesced,
            savedPct: wouldHaveBeen ? Math.round((state.counters.coalesced / wouldHaveBeen) * 100) : 0,
            rows: rows,
        };
    }

    function reset() {
        stopAll();
        inFlight.clear();
        Object.keys(state.counters).forEach((key) => { state.counters[key] = 0; });
        return telemetry();
    }

    /* The status line the shell paints: short, and only about what is actually running. */
    function summary() {
        const t = telemetry();
        if (!t.channels) return t.installed.length ? 'bus: idle · watching ' + t.installed.join(' ') : 'bus: idle';
        return `bus: ${t.subscribers} sub · ${t.channels} ch · ${t.fetches} fetches`
            + (t.coalesced ? ` (${t.coalesced} saved)` : '');
    }

    state.clock = { subscribe: subscribe, tick: tick, request: request };

    (hasWindow ? window : globalThis).OFAPBUS = {
        VERSION: VERSION,
        subscribe: subscribe,
        poll: poll,
        request: request,
        stop: stop,
        stopAll: stopAll,
        install: install,
        uninstall: uninstall,
        telemetry: telemetry,
        summary: summary,
        reset: reset,
        canon: canon,
        _clock: state.clock,
        _state: state,
    };

    if (hasDom && hasWindow) {
        document.dispatchEvent(new CustomEvent('ofap:bus', { detail: { ready: true, version: VERSION } }));
    }
})();
