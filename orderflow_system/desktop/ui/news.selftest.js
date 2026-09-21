/* news.selftest.js — the News panel's decisions, as behaviour rather than prose.
 *
 * The DOM half needs a browser; every decision the panel makes is pure (news.js :: plan / items / item
 * / row / relTime / hostOf / limitOf), so this pins those in Node: the real /api/atlas/context payload
 * sorted newest first, a malformed item skipped instead of crashing the panel, the relative-time
 * labels, and the sentence each of the "no headlines" states gets — the panel must never be blank and
 * must never blame the network for a setting.
 *
 * The fixture is the real response captured from GET /api/atlas/context/BTCUSDT?news_limit=5 on a
 * sandbox instance (port 8096): field names and value shapes verbatim, three items kept.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/news.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

/* No document: the module must still load and expose its logic (a Node run, a headless probe). */
const win = {};
new Function('window', 'document', src)(win, undefined);
const N = win.OFAPNEWS;

function livePayload() {
    return {
        ok: true,
        symbol: 'BTCUSDT',
        ts_ms: 1789479000000,
        news: [
            { title: 'Why an AI Slowdown Could Collapse Under Commercial and US-China Pressure',
              link: 'https://decrypt.co/378203/ai-slowdown-us-china-pressure',
              published: 'Tue, 15 Sep 2026 13:00:05 +0000',
              source: 'decrypt.co', published_ms: 1789477205000 },
            { title: 'To ensure permanent economic innovation, we must pass the Clarity Act now',
              link: 'https://www.coindesk.com/opinion/2026/09/15/to-ensure-permanent-economic-innovation-we-must-pass-the-clarity-act-now',
              published: 'Tue, 15 Sep 2026 12:00:06 +0000',
              source: 'www.coindesk.com', published_ms: 1789473606000 },
            { title: 'Ether, solana, XRP likely to gain if Clarity Act progresses',
              link: 'https://www.coindesk.com/daybook-us/2026/09/15/ether-solana-xrp-likely-to-gain-if-clarity-act-progresses',
              published: 'Tue, 15 Sep 2026 11:15:44 +0000',
              source: 'www.coindesk.com', published_ms: 1789470944000 },
        ],
        stats: { requests: 3, failures: 0, last_error: '', cached: 3,
                 feeds: ['https://www.coindesk.com/arc/outboundfeeds/rss/',
                         'https://cointelegraph.com/rss',
                         'https://decrypt.co/feed'] },
    };
}
/* The shipped config block (desktop/config_store.py: "context") — the feed URL left empty. */
const CFG = { context: { enabled: true, positioning: true, fear_greed: true, news: true,
                         news_url: '', news_limit: 8 } };
const NOW = 1789479300000;                     // 35 min after the newest fixture headline

check('the module loads with no document and exposes its documented surface', () => {
    assert(N && typeof N === 'object', 'window.OFAPNEWS');
    ['refresh', 'paint', 'plan', 'items', 'item', 'row', 'relTime', 'hostOf', 'fullTime', 'limitOf', 'activeSymbol']
        .forEach((name) => assert.strictEqual(typeof N[name], 'function', 'OFAPNEWS.' + name));
    assert.strictEqual(typeof N.state, 'function');
    assert.strictEqual(N.state(), null, 'nothing has been fetched yet');
    assert.strictEqual(N.FEED_KEY, 'context.news_url');
});

check('with no app in reach the active symbol is empty, and the panel says so instead of asking', () => {
    assert.strictEqual(N.activeSymbol(), '');
    const st = N.plan(livePayload(), CFG, NOW, null, N.activeSymbol());
    assert.strictEqual(st.state, 'nosymbol');
    assert.strictEqual(st.count, 0, 'no instrument, no headlines — and no request either');
    assert(st.message.indexOf('instrument') >= 0);
});

check('the live payload comes back newest first, whatever order it arrived in', () => {
    const out = N.items(livePayload());
    assert.strictEqual(out.length, 3);
    assert.deepStrictEqual(out.map((x) => x.published_ms), [1789477205000, 1789473606000, 1789470944000]);
    assert.strictEqual(out[0].source, 'decrypt.co', 'source is the feed host the server reports');
    assert.strictEqual(out[0].published_ms, Number(out[0].published_ms), 'epoch ms, not a string');
    const shuffled = livePayload();
    shuffled.news = [shuffled.news[2], null, shuffled.news[0], shuffled.news[1]];
    assert.deepStrictEqual(N.items(shuffled).map((x) => x.published_ms),
        out.map((x) => x.published_ms), 'the panel sorts, it does not trust the feed order');
});

check('a malformed item is skipped rather than rendered as a broken row', () => {
    const payload = livePayload();
    payload.news = [null, 42, 'headline', {}, { title: '   ' }, { title: 'kept', link: 7 }]
        .concat(payload.news.slice(0, 1));
    const out = N.items(payload);
    assert.strictEqual(out.length, 2, 'only the two items with a title survive');
    assert.strictEqual(out[1].link, '', 'a non-string link is dropped, never rendered');
    const st = N.plan(payload, CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(st.state, 'ok');
    assert.strictEqual(st.count, 2);
});

check('an item the feed gave no date for is kept, ordered last, and labelled without one', () => {
    const payload = livePayload();
    payload.news = [{ title: 'no date A', published: 'yesterday-ish' },
                    { title: 'dated', published_ms: 1789477205000 },
                    { title: 'no date B' }];
    const out = N.items(payload);
    assert.deepStrictEqual(out.map((x) => x.title), ['dated', 'no date A', 'no date B']);
    assert.strictEqual(out[1].published_ms, null);
    assert(N.row(out[1], NOW).indexOf('no date') >= 0, 'the row admits it has no date');
});

check('relative-time labels', () => {
    assert.strictEqual(N.relTime(NOW, NOW), 'just now');
    assert.strictEqual(N.relTime(NOW - 59000, NOW), 'just now');
    assert.strictEqual(N.relTime(NOW - 60000, NOW), '1m ago');
    assert.strictEqual(N.relTime(NOW - 3540000, NOW), '59m ago');
    assert.strictEqual(N.relTime(NOW - 3600000, NOW), '1h ago');
    assert.strictEqual(N.relTime(NOW - 86400000, NOW), '1d ago');
    assert.strictEqual(N.relTime(NOW - 9 * 86400000, NOW), '1w ago');
    assert.strictEqual(N.relTime(null, NOW), '');
    assert.strictEqual(N.relTime(NOW + 120000, NOW), '', 'a feed that claims the future gets no label');
});

check('a feed host is read from a URL or a bare host, and www. is noise', () => {
    assert.strictEqual(N.hostOf('https://www.coindesk.com/arc/outboundfeeds/rss/'), 'coindesk.com');
    assert.strictEqual(N.hostOf('www.coindesk.com'), 'coindesk.com');
    assert.strictEqual(N.hostOf('http://127.0.0.1:8000/feed.xml'), '127.0.0.1');
    assert.strictEqual(N.hostOf(''), '');
    assert.strictEqual(N.hostOf(null), '');
    assert.strictEqual(N.hostOf('two words'), '', 'prose is not a host');
});

check('the live payload is the ok state, named after the feeds that served it', () => {
    const st = N.plan(livePayload(), CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(st.state, 'ok');
    assert.strictEqual(st.count, 3);
    assert.strictEqual(st.symbol, 'BTCUSDT');
    assert.strictEqual(st.source, 'built-in: decrypt.co, coindesk.com',
        'both distinct feed hosts, and the built-ins are named as built-ins');
    assert(N.FEED_KEY && st.note.indexOf('context.news_url') >= 0, 'the empty custom feed is stated, not implied');
    assert(st.limit === 8, 'the configured news_limit is what the panel asks for');
    assert.strictEqual(st.items.length, st.count);
});

check('a configured feed is named by its own host, without the built-in label', () => {
    const cfg = { context: { news_url: 'https://www.example.org/news/feed.xml', news_limit: 8 } };
    const payload = livePayload();
    payload.news = payload.news.slice(0, 1).map((x) => Object.assign({}, x, {
        source: 'www.example.org', link: 'https://www.example.org/a',
    }));
    const st = N.plan(payload, cfg, NOW, null, 'BTCUSDT');
    assert.strictEqual(st.state, 'ok');
    assert.strictEqual(st.source, 'example.org');
    assert(st.note.indexOf('context.news_url = https://www.example.org/news/feed.xml') >= 0);
});

check('no custom feed and no server feeds is "not configured", with the key that fixes it', () => {
    const st = N.plan({ ok: true, symbol: 'BTCUSDT', news: [], stats: { feeds: [], failures: 0 } },
        CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(st.state, 'unconfigured');
    assert.strictEqual(st.source, 'not configured');
    assert(st.message.indexOf('context.news_url') >= 0, 'the config key, spelled as the config stores it');
    assert(/RSS/.test(st.message), 'and what to put in it');
});

check('a feed that answered nothing is empty, quoting the server\'s own reason', () => {
    const payload = { ok: true, symbol: 'BTCUSDT', news: [], stats: {
        feeds: ['https://www.coindesk.com/arc/outboundfeeds/rss/'],
        failures: 1, last_error: 'URLError: timed out' } };
    const st = N.plan(payload, CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(st.state, 'empty');
    assert.strictEqual(st.count, 0);
    assert(st.message.indexOf('URLError: timed out') >= 0, 'the real reason, not a generic one');
    assert(st.source.indexOf('built-in') >= 0);
});

check('the Finnhub lane is named as a keyed lane, never as a built-in feed', () => {
    const items = [{ title: 'Fed holds rates', link: 'https://finnhub.io/a', source: 'Reuters',
                     published_ms: NOW - 60000 }];
    const st = N.plan({ ok: true, symbol: 'BTCUSDT', news: items,
        stats: { feeds: ['finnhub'], lane: 'finnhub', last_error: '' } }, CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(st.state, 'ok');
    assert.strictEqual(st.source, 'finnhub: reuters', 'the lane prefixes the sources it served');
    assert(st.note.indexOf('Finnhub news API') >= 0, 'the lane is named');
    assert(st.note.indexOf('Settings ▸ Feed keys') >= 0, 'and the control that unlocks it');
    assert.strictEqual(st.note.indexOf('built-in'), -1, 'a keyed lane is never called a built-in feed');

    const empty = N.plan({ ok: true, symbol: 'BTCUSDT', news: [],
        stats: { feeds: [], lane: 'finnhub',
                 last_error: 'no Finnhub key — add one in Settings ▸ Feed keys' } },
        CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(empty.state, 'empty');
    assert.strictEqual(empty.source, 'Finnhub');
    assert(empty.message.indexOf('no Finnhub key') >= 0, 'the server\'s own reason, verbatim');
    assert.strictEqual(empty.message.indexOf('built-in'), -1);
});

check('context switched off and news switched off are two different sentences', () => {
    const disabled = N.plan({ ok: false, symbol: 'BTCUSDT',
        error: 'market context is disabled in settings' }, CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(disabled.state, 'disabled');
    assert(disabled.message.indexOf('market context is disabled in settings') >= 0);
    const switchedOff = N.plan({ ok: true, symbol: 'BTCUSDT', stats: { feeds: [] } }, CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(switchedOff.state, 'off');
    assert(switchedOff.message.indexOf('context.news') >= 0, 'the key that switches it back on');
});

check('before the fetch it is loading; a failed fetch is an error that says which', () => {
    const loading = N.plan(null, CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(loading.state, 'loading');
    assert.strictEqual(loading.count, 0);
    const error = N.plan(null, CFG, NOW, 'TypeError: Failed to fetch', 'BTCUSDT');
    assert.strictEqual(error.state, 'error');
    assert(/TypeError: Failed to fetch/.test(error.message));
});

check('every state that is not ok explains itself, and ok always has items', () => {
    const states = [
        N.plan(null, CFG, NOW, null, 'BTCUSDT'),                                    // loading
        N.plan(livePayload(), CFG, NOW, null, ''),                                  // no instrument
        N.plan(null, CFG, NOW, 'boom', 'BTCUSDT'),                                  // error
        N.plan({ ok: false, error: 'x' }, CFG, NOW, null, 'BTCUSDT'),               // disabled
        N.plan({ ok: true }, CFG, NOW, null, 'BTCUSDT'),                            // news switched off
        N.plan({ ok: true, news: [], stats: {} }, CFG, NOW, null, 'BTCUSDT'),       // nothing at all
    ];
    states.forEach((st) => {
        assert.notStrictEqual(st.state, 'ok');
        assert(st.message && st.message.length > 10, st.state + ' must say something: ' + st.message);
        assert.strictEqual(st.count, 0, st.state + ' must not claim headlines');
    });
    assert(/loading/.test(states[0].message), 'the pre-fetch state reads as loading');
    const good = N.plan(livePayload(), CFG, NOW, null, 'BTCUSDT');
    assert.strictEqual(good.state, 'ok');
    assert(good.count > 0);
});

check('a row escapes feed text and only turns an http(s) link into an anchor', () => {
    const hostile = N.item({ title: '<img src=x onerror=alert(1)>', link: 'javascript:alert(2)',
        source: 'evil.example', published_ms: 1789477205000 });
    const html = N.row(hostile, NOW);
    assert(html.indexOf('<img') < 0, 'the title is escaped');
    assert(html.indexOf('&lt;img') >= 0, 'and shown as text');
    assert(html.indexOf('href=') < 0, 'no anchor for a link a browser must not follow');
    assert(html.indexOf('javascript:') < 0, 'the value never reaches the markup');
    assert(html.indexOf('news-src') >= 0 && html.indexOf('evil.example') >= 0, 'the host is shown');
    assert(html.indexOf('news-when') >= 0, 'and so is the age');
    const real = N.row(N.items(livePayload())[0], NOW);
    assert(real.indexOf('href="https://decrypt.co/378203/ai-slowdown-us-china-pressure"') >= 0);
    assert(real.indexOf('target="_blank"') >= 0 && real.indexOf('rel="noopener noreferrer"') >= 0);
});

check('the panel never asks the endpoint for more than the endpoint allows', () => {
    assert.strictEqual(N.limitOf({ context: { news_limit: 8 } }), 8);
    assert.strictEqual(N.limitOf({ context: { news_limit: 100 } }), N.LIMIT_MAX, 'clamped: le=30 is a 422');
    assert.strictEqual(N.limitOf({ context: { news_limit: 0 } }), 0, 'zero sends no parameter, the server picks');
    assert.strictEqual(N.limitOf(null), 0);
    assert.strictEqual(N.LIMIT_MAX, 30);
});

check('one timer, and no reach for ingest', () => {
    assert.strictEqual((src.match(/setInterval\(/g) || []).length, 1, 'one timer for the whole panel');
    ['localStorage', 'sessionStorage', 'indexedDB', 'WebSocket', 'EventSource', '/api/control/engine']
        .forEach((bad) => assert.strictEqual(src.indexOf(bad), -1, 'news.js must not touch ' + bad));
});

console.log('news selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
