/* news.js — the News panel: public RSS/Atom headlines for the instrument the app is showing.
 *
 * WHERE THE DATA COMES FROM — nothing here is invented:
 *   GET /api/atlas/context/{symbol}     (orderflow_system/atlas/api.py :: market_context)
 *       ?news_limit=N                   Query(ge=0, le=30); 0 means "let the server use the config"
 *   → { ok, symbol, ts_ms,
 *       news: [ { title, link, published, source, published_ms } ],
 *       stats: { requests, failures, last_error, cached, feeds, lane } }
 *
 *   TWO LANES, ONE SHAPE: `context.news_source` picks where the headlines come from — "feeds" (the
 *   built-in public feeds above, the default) or "finnhub" (the Finnhub news API, unlocked by the key
 *   in Settings ▸ Feed keys). The server names the lane it answered with in `stats.lane`, and this
 *   panel says which one it was: a keyed lane is never called a built-in feed, and an empty keyed
 *   lane prints the reason the server gave instead of blaming the network.
 *
 *   The feed URL is the config key `context.news_url`. Left empty — the shipped default — the SERVER
 *   falls back to its own three public feeds (atlas/context.py :: DEFAULT_NEWS_FEEDS: CoinDesk,
 *   Cointelegraph, Decrypt) and reports them in `stats.feeds`, so "no custom feed" is not "no news":
 *   the panel says which of the two it is instead of guessing. Per item, `source` is the feed's HOST
 *   (the server derives it from the feed URL), `published_ms` is epoch ms or null when the feed's date
 *   string did not parse, and the feed is general market news — the endpoint never filters it by
 *   instrument, so the panel does not pretend the headlines are about this symbol.
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - The deciding half (plan/items/item/row/relTime/hostOf) is pure, so desktop/ui/news.selftest.js
 *     pins it in Node with no browser; render() only joins those strings.
 *   - "context switched off", "news switched off", "the feed answered nothing", "the request failed"
 *     and "no source at all" are five different facts, and each writes its own sentence: the panel is
 *     never blank, never shows a placeholder that looks like a headline, and never blames the network
 *     for a setting.
 *   - Read-only by construction: one REST GET on a timer that only runs while this panel is the
 *     visible one (the server caches news for 300 s, so that is the tick rate, not a busy loop). No
 *     sockets, no engine calls, nothing stored.
 */
(function () {
    'use strict';

    const el = (id) => document.getElementById(id);
    const VIEW = '.view[data-view="news"]';
    const LIMIT_MAX = 30;                 // the endpoint's own Query(le=30) — asking for more is a 422
    const POLL_MS = 300000;               // news TTL on the server is 300 s (context.py ttl_news_s)
    const TICK_MS = 15000;                // how often the cheap "is it time yet" check runs
    const FEED_KEY = 'context.news_url';  // where a custom feed lives in the config

    function nwEsc(t) {
        return String(t == null ? '' : t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    }
    /* The app's own api() when we are inside it; the same fallback platforms.js uses when probed bare.
       The call site keeps the route in a template literal no wider than the path, so audit_ui_refs.py
       can still see which endpoint this module asks for. */
    function api(path, options) {
        if (typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options).then((r) => r.json());
    }

    const NEWS = { state: null, busy: false, wired: false };

    function section() { return document.querySelector(VIEW); }
    function isActive() {
        const view = section();
        return !!(view && view.classList.contains('active'));
    }
    /* Defensive by request: the engine's symbol is the authority when it is live, the app's instrument
       select is the fallback, and no app at all is an empty string rather than a throw. */
    function activeSymbol() {
        const fromState = (typeof S !== 'undefined' && S) ? S.symbol : '';
        const select = (typeof document !== 'undefined') ? el('symbolSelect') : null;
        return fromState || (select && select.value) || '';
    }

    /* ── pure: every decision the panel makes, with no DOM in reach ───────────── */

    /* 'https://www.coindesk.com/arc/outboundfeeds/rss/' → 'coindesk.com'. The server hands us a bare
       host in `source` and a URL in `link`, and both reach this function. */
    function hostOf(url) {
        const text = String(url == null ? '' : url).trim();
        if (!text || /\s/.test(text)) return '';
        const withScheme = /^[a-z][a-z0-9+.-]*:\/\/([^/?#]+)/i.exec(text);
        const host = (withScheme ? withScheme[1] : text.split(/[/?#]/)[0])
            .replace(/^[^@/]*@/, '').replace(/:\d+$/, '');
        return host.replace(/^www\./i, '').toLowerCase();
    }

    function fullTime(ms) {
        const t = Number(ms);
        if (!t || !Number.isFinite(t)) return '';
        try { return new Date(t).toLocaleString(); } catch (e) { return ''; }
    }

    /* '' when the feed gave no parsable date or claims the future — an absent label beats a wrong one. */
    function relTime(ms, now) {
        const t = Number(ms);
        if (!t || !Number.isFinite(t)) return '';
        const s = Math.round(((Number(now) || Date.now()) - t) / 1000);
        if (s < -90) return '';
        if (s < 60) return 'just now';
        const minutes = Math.floor(s / 60);
        if (minutes < 60) return minutes + 'm ago';
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return hours + 'h ago';
        const days = Math.floor(hours / 24);
        return days < 7 ? days + 'd ago' : Math.floor(days / 7) + 'w ago';
    }

    /* One wire item → the fields a row shows, or null when there is no headline to show. Only an
       absolute http(s) link survives: a relative one would open this app's own server and a
       javascript: one would run in this window — a plain title is better than either. */
    function item(raw) {
        if (!raw || typeof raw !== 'object') return null;
        const title = typeof raw.title === 'string' ? raw.title.trim() : '';
        if (!title) return null;
        const link = typeof raw.link === 'string' ? raw.link.trim() : '';
        const ms = Number(raw.published_ms);
        return {
            title: title,
            link: /^https?:\/\//i.test(link) ? link : '',
            source: typeof raw.source === 'string' ? raw.source.trim() : '',
            published_ms: (Number.isFinite(ms) && ms > 0) ? ms : null,
        };
    }

    /* Newest first. An item whose date did not parse keeps the feed's own order at the end, and a
       malformed item is dropped rather than rendered as a broken row. */
    function items(payload) {
        const raw = (payload && Array.isArray(payload.news)) ? payload.news : [];
        const kept = [];
        for (let i = 0; i < raw.length; i++) {
            const one = item(raw[i]);
            if (one) kept.push({ it: one, i: i });
        }
        return kept
            .sort((a, b) => ((b.it.published_ms || 0) - (a.it.published_ms || 0)) || (a.i - b.i))
            .map((r) => r.it);
    }

    function ctxBlock(cfg) {
        const block = cfg && cfg.context;
        return (block && typeof block === 'object') ? block : {};
    }
    function feedOf(cfg) {
        const url = ctxBlock(cfg).news_url;
        return typeof url === 'string' ? url.trim() : '';
    }
    function limitOf(cfg) {
        const n = Math.floor(Number(ctxBlock(cfg).news_limit) || 0);
        return n > 0 ? Math.min(n, LIMIT_MAX) : 0;      // 0 → send no parameter, the server picks
    }

    /* The whole panel state as data. `payload` is the endpoint response, or null before the fetch;
       `err` is the fetch failure, if any; `symbol` is the instrument we asked for (empty → we cannot
       ask at all, which is its own honest state rather than a request for a made-up symbol). */
    function plan(payload, cfg, now, err, symbol) {
        const at = Number(now) || Date.now();
        const feed = feedOf(cfg);
        const st = {
            state: 'loading', symbol: String(symbol || '').toUpperCase(), items: [], count: 0,
            source: '—', message: '', note: '', at: at, feed: feed, limit: limitOf(cfg),
        };
        if (!st.symbol) {
            st.state = 'nosymbol';
            st.message = 'no instrument is active yet — pick one in the top bar and the headlines load for it.';
            return st;
        }
        if (err) {
            st.state = 'error';
            st.message = 'the news request failed: ' + String(err) + ' — press Refresh to try again.';
            return st;
        }
        if (!payload || typeof payload !== 'object') {                   // pre-fetch: the loading state
            st.message = 'loading headlines…';
            return st;
        }

        st.symbol = String(payload.symbol || st.symbol).toUpperCase();
        st.items = items(payload);
        st.count = st.items.length;
        const stats = (payload.stats && typeof payload.stats === 'object') ? payload.stats : {};
        const served = (Array.isArray(stats.feeds) ? stats.feeds : [])
            .filter((f) => typeof f === 'string' && f.trim());
        const why = String(stats.last_error || '').trim();
        /* Which lane answered — the server says so in stats.lane. "feeds" is the built-in RSS set,
           "finnhub" is the keyed Finnhub news API, and the panel must not call one the other. */
        const onLane = String(stats.lane || 'feeds').toLowerCase() === 'finnhub';

        if (payload.ok === false) {
            st.state = 'disabled';
            st.message = 'market context is switched off in the settings'
                + (payload.error ? ': ' + payload.error : ' (context.enabled)')
                + ' — switch it back on to get headlines.';
            return st;
        }
        if (!('news' in payload)) {
            st.state = 'off';
            st.message = 'the news section is switched off in the settings (context.news) — tick '
                + '"Crypto headlines" in Setup → Market context to fetch them again.';
            return st;
        }
        if (!st.count) {
            if (onLane) {
                st.source = 'Finnhub';
                st.state = 'empty';
                st.message = 'the Finnhub news lane has no headlines right now'
                    + (why ? ' — ' + why : '') + '.';
                return st;
            }
            st.source = feed ? (hostOf(feed) || 'configured feed')
                : (served.length ? 'built-in feeds' : 'not configured');
            if (feed) {
                st.state = 'empty';
                st.message = 'the feed in ' + FEED_KEY + ' returned no headlines'
                    + (why ? ' — ' + why : '') + '.';
            } else if (served.length) {
                st.state = 'empty';
                st.message = 'the app\'s built-in feeds returned no headlines' + (why ? ' — ' + why : '') + '.';
            } else {
                st.state = 'unconfigured';
                st.message = 'no news source is configured: the server listed no feeds and ' + FEED_KEY
                    + ' is empty — set it to a public RSS or Atom URL (Setup → Market context → "Custom news feed").';
            }
            return st;
        }

        const hosts = [];
        st.items.forEach((one) => {
            const host = hostOf(one.source) || hostOf(one.link);
            if (host && hosts.indexOf(host) < 0) hosts.push(host);
        });
        const shown = hosts.length > 2
            ? hosts.slice(0, 2).join(', ') + ' +' + (hosts.length - 2)
            : (hosts.join(', ') || 'unknown feed');
        st.state = 'ok';
        st.source = onLane ? 'finnhub: ' + shown : (feed ? '' : 'built-in: ') + shown;
        st.note = (onLane
            ? 'headlines come from the Finnhub news API, unlocked by the key in Settings ▸ Feed keys'
            : (feed
                ? 'feed from ' + FEED_KEY + ' = ' + feed
                : 'the app\'s built-in public feeds are in use — ' + FEED_KEY + ' is empty'))
            + ' · general market news, not filtered by instrument.';
        return st;
    }

    /* One headline row. A feed-supplied value never reaches the HTML without nwEsc, and a title with
       no usable link is text, not a dead anchor. */
    function row(one, now) {
        const host = hostOf(one.source) || hostOf(one.link);
        const when = relTime(one.published_ms, now) || (one.published_ms ? '' : 'no date');
        const tip = nwEsc(fullTime(one.published_ms) || one.title);
        const head = one.link
            ? '<a href="' + nwEsc(one.link) + '" target="_blank" rel="noopener noreferrer" title="'
                + tip + '">' + nwEsc(one.title) + '</a>'
            : '<span title="' + tip + '">' + nwEsc(one.title) + '</span>';
        const meta = (host ? '<span class="news-src">' + nwEsc(host) + '</span>' : '')
            + (when ? '<span class="news-when">' + nwEsc(when) + '</span>' : '');
        return '<div class="news-item"><div class="news-title">' + head + '</div>'
            + (meta ? '<div class="news-meta">' + meta + '</div>' : '') + '</div>';
    }

    /* ── the DOM half ────────────────────────────────────────────────────────── */

    const NEWS_STYLE = `
.news-item { display: flex; gap: 12px; align-items: baseline; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,.05); }
.news-item:last-child { border-bottom: 0; }
.news-title { flex: 1 1 auto; min-width: 0; }
.news-title a { color: inherit; text-decoration: none; }
.news-title a:hover { text-decoration: underline; }
.news-meta { flex: 0 0 auto; display: flex; gap: 10px; opacity: .55; font-size: 11px; white-space: nowrap; }
.news-message, .news-note { padding: 4px 0 2px; font-size: 11.5px; }`;

    /* The app already holds the config (bootstrap puts it in S.config); probed without it, read it once
       — the same GET /api/control/config search.js uses. Never throws: a panel that cannot read the
       config still shows the headlines it can, it just cannot name the feed. */
    async function config() {
        if (typeof S !== 'undefined' && S && S.config && typeof S.config === 'object') return S.config;
        try { return await api('/api/control/config'); } catch (e) { return null; }
    }

    /* Fold the strings. Nothing here decides anything — every state, label and sentence already came
       out of plan(), so what the user reads is what the selftest pinned. */
    function paint(st) {
        NEWS.state = st;
        /* P1-10: a headline feed is judged by the hour — fresh until it has not fetched for 10 min. */
        if (window.OFAPFRESH && st && typeof st.count === 'number') {
            OFAPFRESH.stamp('news', { ageMs: 0, windowMs: 600000 });
        }
        const count = el('newsCount'), source = el('newsSource'), sub = el('newsSub'), body = el('newsBody');
        if (count) count.textContent = st.count + (st.count === 1 ? ' headline' : ' headlines');
        if (source) source.textContent = st.source || '—';
        if (sub) {
            sub.textContent = st.symbol
                ? st.symbol + ' · ' + (st.state === 'ok' ? st.source : st.message)
                : 'headlines for the active instrument — pick one and they load';
        }
        if (!body) return;
        const rows = st.state === 'ok' ? st.items.map((one) => row(one, st.at)).join('') : '';
        let html = rows || '<div class="news-message dim">' + nwEsc(st.message) + '</div>';
        if (st.note) html += '<div class="news-note dim">' + nwEsc(st.note) + '</div>';
        body.innerHTML = html;
    }

    async function refresh() {
        if (NEWS.busy) return;
        NEWS.busy = true;
        const btn = el('newsRefresh');
        if (btn) btn.disabled = true;
        const symbol = activeSymbol();
        const cfg = await config();
        paint(plan(null, cfg, Date.now(), null, symbol));       // 'loading' — never a blank panel
        if (symbol) {
            try {
                const query = limitOf(cfg) ? '?news_limit=' + limitOf(cfg) : '';
                const payload = await api(`/api/atlas/context/${encodeURIComponent(symbol)}` + query);
                paint(plan(payload, cfg, Date.now(), null, symbol));
            } catch (e) {
                paint(plan(null, cfg, Date.now(), (e && e.message) || String(e), symbol));
            }
        }
        NEWS.busy = false;
        if (btn) btn.disabled = false;
    }

    /* One timer, and it only acts while this panel is the visible one, the window is visible and no
       gesture is holding a surface. The real rate is POLL_MS; this tick just decides whether to ask. */
    function tick() {
        if (!isActive() || document.hidden || window.OFAP_PAUSED) return;
        if (window.OFAPINTENT && typeof window.OFAPINTENT.anyHeld === 'function' && window.OFAPINTENT.anyHeld()) return;
        const st = NEWS.state || {};
        const moved = String(activeSymbol() || '').toUpperCase() !== String(st.symbol || '');
        if (!moved && (Date.now() - (Number(st.at) || 0)) < POLL_MS) return;
        void refresh();
    }

    /* Wired once: the section's markup is static, and a shell mode switch re-parents it rather than
       rebuilding it, so these listeners survive. */
    function wire() {
        if (NEWS.wired) return;
        NEWS.wired = true;
        if (!el('newsStyles')) {
            const style = document.createElement('style');
            style.id = 'newsStyles';
            style.textContent = NEWS_STYLE;
            document.head.appendChild(style);
        }
        const btn = el('newsRefresh');
        if (btn) btn.addEventListener('click', () => { void refresh(); });
        const select = el('symbolSelect');
        if (select) select.addEventListener('change', () => { if (isActive()) void refresh(); });
        setInterval(tick, TICK_MS);
    }

    function watch() {
        const view = section();
        if (!view) return;
        wire();
        if (isActive()) void refresh();
        new MutationObserver(() => { if (isActive()) void refresh(); })
            .observe(view, { attributes: true, attributeFilter: ['class'] });
    }

    window.OFAPNEWS = {
        refresh: refresh, paint: paint, plan: plan, items: items, item: item, row: row,
        relTime: relTime, hostOf: hostOf, fullTime: fullTime, limitOf: limitOf,
        activeSymbol: activeSymbol, state: () => NEWS.state,
        VIEW: VIEW, FEED_KEY: FEED_KEY, LIMIT_MAX: LIMIT_MAX, POLL_MS: POLL_MS, TICK_MS: TICK_MS,
    };

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
