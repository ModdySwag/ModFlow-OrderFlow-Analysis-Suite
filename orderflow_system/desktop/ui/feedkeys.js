/* feedkeys.js — Settings ▸ Feed keys: the optional REST feeds' credentials, and the two lanes.
 *
 * WHERE THE DATA COMES FROM — nothing here is invented:
 *   GET  /api/control/feedkeys          one row per optional feed, credentials MASKED (a stored
 *                                       key travels as `key_hint` + `has_secret`, never as itself)
 *   POST /api/control/feedkeys          {tradier:{…}, marketdata:{…}, finnhub:{…}, lanes:{…}}
 *                                       → the fresh state, and the server runs the engine's own
 *                                       settings cast so a key typed a second ago is live (the
 *                                       chain panels, the calendar lane, the news lane all read it)
 *   GET  /api/options/volatility/{sym}  the Check button's real read (source=tradier|marketdata)
 *   GET  /api/control/calendar          the Check button's real read (source=finnhub, hours=24)
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - The rows are DATA (the server's list of feeds and their leaves) plus one local SPECS table
 *     of input shapes. A new feed is a server block, not new markup.
 *   - SEC-09 on the write path: a credential leaf is only posted when the user TYPED one (a typed
 *     value replaces) or explicitly cleared one (the × posts ""). A blank untouched field is
 *     omitted, so "leave it alone" can never mean "wipe the stored key".
 *   - Bounds printed by an input mirror the store's own clamps (chain_width 1–20, calendar_days
 *     1–30) and its category whitelists: the store is the enforcement point, so what a row shows
 *     is what a save keeps.
 *   - Check is the app's own route, on a symbol the equity feeds carry, and prints the server's
 *     sentence either way — a green check is a real chain read, not a guess about the key.
 *   - Two lanes, one choice each: which feed the Calendar VIEW reads, and which source the News
 *     panel reads. Both are saved the moment they change (a setting the user has to re-do every
 *     launch is a setting the app lost) and both name what they do NOT change — the calendar's
 *     alert line keeps reading the keyless built-in feed.
 *   - No timers at all: this card is read on load, on demand, and after each write.
 */
(function () {
    'use strict';

    const HOST = 'fkRows';
    /* Each /api path below is written out at its call site rather than held in a constant: the
       end-of-build audit's route check reads literals, and a path it cannot read is a path it
       cannot guard. */
    /* The equity feeds are US options venues, so the check asks for a name all of them carry. */
    const CHECK_SYMBOL = 'SPY';
    const CHECK_HOURS = 24;

    /* ── the input shapes (bounds mirror the store's clamps; see the header) ─────────────── */

    const SPECS = {
        tradier: {
            key_id: { label: 'Key ID', kind: 'text', placeholder: 'your Tradier key ID' },
            secret: { label: 'Secret', kind: 'password', placeholder: 'your Tradier secret' },
            chain_width: { label: 'Chain width (strikes)', kind: 'number', min: 1, max: 20, step: 1,
                           title: 'Strikes around the forward price, per expiry — the range the store keeps.' },
            sandbox: { label: 'Use the sandbox endpoint', kind: 'check',
                       title: 'sandbox.tradier.com instead of the brokerage endpoint' },
        },
        marketdata: {
            api_key: { label: 'API key', kind: 'password', placeholder: 'your marketdata.app token' },
        },
        finnhub: {
            api_key: { label: 'API key', kind: 'password', placeholder: 'your Finnhub token' },
            calendar_category: { label: 'Calendar category', kind: 'select',
                                 options: ['all', 'forex', 'crypto', 'indices', 'stocks'] },
            calendar_days: { label: 'Calendar days ahead', kind: 'number', min: 1, max: 30, step: 1,
                             title: 'How far forward the calendar lane asks — the range the store keeps.' },
            news_category: { label: 'News category', kind: 'select',
                             options: ['general', 'federalReserve', 'economic', 'company', 'markets'] },
        },
    };

    const CREDS = ['key_id', 'secret', 'api_key'];

    function escape(t) {
        return String(t == null ? '' : t).replace(/[&<>"']/g, (c) => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function specFor(feed, leaf) {
        const group = SPECS[feed];
        return (group && group[leaf]) || null;
    }

    function fieldId(feed, leaf) { return 'fk_' + feed + '_' + leaf; }
    function msgId(feed) { return 'fk_m_' + feed; }

    /* ── the pure half ─────────────────────────────────────────────────────────────────── */

    /* What is stored, in words. The mask never travels back whole — this is the whole sentence. */
    function stateWord(row) {
        const r = row || {};
        const hint = String(r.key_hint || '').trim();
        if (hint) return 'saved — ' + hint;
        if (r.has_secret) return 'saved — secret stored';
        return 'not set';
    }

    /* One feed's write body from what the fields currently read.
     *
     * `read` is {leaf: value}; `clears` is {leaf:true} for an explicit ×. Credential leaves are
     * only included when typed (or cleared) — a blank untouched field is omitted so the stored key
     * survives, which is the exact rule SEC-09's unmask_patch expects on the way back in.
     */
    function writeBody(feed, read, clears) {
        const group = SPECS[feed] || {};
        const body = {};
        Object.keys(group).forEach((leaf) => {
            const spec = group[leaf];
            const value = read ? read[leaf] : undefined;
            if (spec.kind === 'check') { body[leaf] = !!value; return; }
            if (CREDS.indexOf(leaf) >= 0) {
                const typed = typeof value === 'string' ? value.trim() : '';
                if (typed) body[leaf] = typed;
                else if (clears && clears[leaf]) body[leaf] = '';
                return;
            }
            if (spec.kind === 'number') {
                const num = Number(value);
                if (Number.isFinite(num) && String(value).trim() !== '') {
                    body[leaf] = Math.min(Math.max(num, spec.min), spec.max);
                }
                return;
            }
            const text = typeof value === 'string' ? value.trim() : '';
            if (text) body[leaf] = text;
        });
        return body;
    }

    const LANES = {
        calendar: { id: 'fkCalLane', field: 'calendar', choices: ['builtin', 'finnhub'] },
        news: { id: 'fkNewsLane', field: 'news', choices: ['feeds', 'finnhub'] },
    };

    function savedLanes(state) {
        const lanes = (state && state.lanes) || {};
        return { calendar: String(lanes.calendar || 'builtin'), news: String(lanes.news || 'feeds') };
    }

    /* The Check button asks the app's own route for this feed and reports the server's sentence. */
    function checkUrl(feed) {
        if (feed === 'finnhub') {
            return '/api/control/calendar?hours=' + CHECK_HOURS + '&impact=low&source=finnhub';
        }
        return '/api/options/volatility/' + encodeURIComponent(CHECK_SYMBOL) +
            '?source=' + encodeURIComponent(feed);
    }

    function checkSentence(feed, payload) {
        const p = payload || {};
        if (p.ok !== true) {
            return 'check failed — ' + String(p.error || 'the route did not answer');
        }
        if (feed === 'finnhub') {
            const n = Number(p.upcoming) || 0;
            return 'check ok — ' + n + (n === 1 ? ' event' : ' events') + ' in the next ' +
                (Number(p.window_hours) || CHECK_HOURS) + ' h · ' + String(p.source || 'Finnhub');
        }
        const strikes = Number(p.n_strikes) || 0;
        const expiries = Number(p.n_expiries) || 0;
        return 'check ok — ' + String(p.symbol || CHECK_SYMBOL) + ' · ' + strikes + ' strikes over ' +
            expiries + (expiries === 1 ? ' expiry' : ' expiries') + ' · ' + String(p.source || feed);
    }

    function fieldHtml(feed, leaf, row) {
        const spec = specFor(feed, leaf);
        if (!spec) return '';
        const id = fieldId(feed, leaf);
        const stored = (row && row.values) || {};
        const value = stored[leaf];
        let control = '';
        if (spec.kind === 'select') {
            const options = (spec.options || []);
            control = '<select id="' + id + '">' + options.map((opt) => (
                '<option value="' + escape(opt) + '"' + (String(value) === opt ? ' selected' : '') + '>'
                + escape(opt) + '</option>')).join('') + '</select>';
        } else if (spec.kind === 'check') {
            control = '<label class="switch"><input type="checkbox" id="' + id + '"'
                + (value ? ' checked' : '') + '> ' + escape(spec.label) + '</label>';
            return '<div class="fk-field" title="' + escape(spec.title || '') + '">' + control + '</div>';
        } else if (spec.kind === 'number') {
            control = '<input type="number" id="' + id + '" min="' + spec.min + '" max="' + spec.max
                + '" step="' + spec.step + '" value="' + escape(value == null ? '' : value) + '"'
                + ' title="' + escape(spec.title || '') + '">';
        } else {
            const isCred = CREDS.indexOf(leaf) >= 0;
            const storedHint = isCred
                ? (leaf === 'secret' ? row.has_secret : !!String(row.key_hint || '').trim())
                : false;
            control = '<input type="' + (spec.kind === 'password' ? 'password' : 'text') + '" id="' + id
                + '" autocomplete="off" spellcheck="false" placeholder="'
                + escape(storedHint ? '(saved — type to replace)' : (spec.placeholder || '')) + '">';
            if (storedHint) {
                control += '<button type="button" class="fk-clear" data-fk-act="clear" data-fk-feed="'
                    + escape(feed) + '" data-fk-leaf="' + escape(leaf)
                    + '" title="Remove the stored value for ' + escape(spec.label)
                    + ' — the lane then refuses with the reason.">clear</button>';
            }
        }
        return '<div class="fk-field"><label for="' + id + '">' + escape(spec.label) + '</label>'
            + control + '</div>';
    }

    function rowHtml(row) {
        const r = row || {};
        const feed = String(r.id || '');
        const leaves = Array.isArray(r.leaves) ? r.leaves : [];
        const fields = leaves.map((leaf) => fieldHtml(feed, leaf, r)).join('');
        return '<div class="fk-row" data-fk-row="' + escape(feed) + '">'
            + '<div class="fk-head"><b>' + escape(r.label || feed) + '</b>'
            + '<span class="fk-state">' + escape(stateWord(r)) + '</span></div>'
            + '<div class="fk-buys dim">' + escape(r.buys || '') + '</div>'
            + '<div class="fk-fields">' + fields + '</div>'
            + '<div class="fk-actions">'
            + '<button type="button" class="btn small" data-fk-act="save" data-fk-feed="' + escape(feed)
            + '" title="Store these values in your config — a blank key field keeps what is stored.">Save</button>'
            + '<button type="button" class="btn small" data-fk-act="check" data-fk-feed="' + escape(feed)
            + '" title="Read a real chain through this feed (' + escape(CHECK_SYMBOL) + ') and print the '
            + 'answer — a key that does not work says so here.">Check</button>'
            + '<span class="fk-msg" id="' + escape(msgId(feed)) + '"></span>'
            + '</div></div>';
    }

    function rowsHtml(state) {
        const feeds = (state && Array.isArray(state.feeds)) ? state.feeds : [];
        if (!feeds.length) return '<div class="dim">no optional feeds are known to this build</div>';
        return feeds.map(rowHtml).join('');
    }

    function pillText(state) {
        const feeds = (state && Array.isArray(state.feeds)) ? state.feeds : [];
        const set = feeds.filter((row) => !!(row && row.ready)).length;
        return set + ' of ' + feeds.length + (feeds.length === 1 ? ' feed set' : ' feeds set');
    }

    /* ── the DOM half ──────────────────────────────────────────────────────────────────── */

    const state = { last: null, busy: false, clears: {} };

    function el(id) {
        /* A page that has no DOM yet (or a selftest parsing this file) reads null and moves on —
           nothing here may throw on a document that is not there. */
        if (typeof document === 'undefined' || !document) return null;
        return document.getElementById(id);
    }

    function api(path, options) {
        if (typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options).then((res) => res.json());
    }

    const STYLE = `
.fk-rows { display: flex; flex-direction: column; gap: 10px; }
.fk-row { border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; }
.fk-head { display: flex; align-items: baseline; gap: 10px; }
.fk-state { opacity: .65; font-size: 11.5px; }
.fk-buys { font-size: 11.5px; margin: 2px 0 6px; }
.fk-fields { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
.fk-field { display: flex; flex-direction: column; gap: 3px; }
.fk-field > label { font-size: 11px; opacity: .8; }
.fk-field input[type="text"], .fk-field input[type="password"] { min-width: 220px; }
.fk-field input[type="number"] { width: 96px; }
.fk-clear { margin-left: 6px; background: none; border: 0; color: var(--text-secondary); cursor: pointer;
    font-size: 11px; text-decoration: underline; padding: 0; }
.fk-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.fk-msg { font-size: 11.5px; opacity: .85; }`;

    function ensureStyles() {
        if (document.getElementById('fkStyles')) return;
        const tag = document.createElement('style');
        tag.id = 'fkStyles';
        tag.textContent = STYLE;
        document.head.appendChild(tag);
    }

    function setMsg(feed, text, kind) {
        const node = el(msgId(feed));
        if (node) {
            node.textContent = text || '';
            node.style.color = kind === 'bad' ? 'var(--warn, #e0a33c)' : '';
        }
    }

    function render(next) {
        if (next && typeof next === 'object' && Array.isArray(next.feeds)) state.last = next;
        const host = el(HOST);
        const pill = el('fkPillText');
        if (host) host.innerHTML = rowsHtml(state.last);
        if (pill) pill.textContent = state.last ? pillText(state.last) : '—';
        const lanes = savedLanes(state.last);
        const cal = el(LANES.calendar.id);
        const news = el(LANES.news.id);
        if (cal) cal.value = lanes.calendar;
        if (news) news.value = lanes.news;
    }

    async function load() {
        try {
            const payload = await api('/api/control/feedkeys');
            render(payload);
        } catch (e) {
            const host = el(HOST);
            if (host) host.innerHTML = '<div class="dim">the feed keys could not be read: '
                + escape((e && e.message) || String(e)) + '</div>';
        }
    }

    function readFields(feed) {
        const read = {};
        const group = SPECS[feed] || {};
        Object.keys(group).forEach((leaf) => {
            const node = el(fieldId(feed, leaf));
            if (!node) return;
            read[leaf] = group[leaf].kind === 'check' ? !!node.checked : node.value;
        });
        return read;
    }

    /* §148 / T7-F12: which pending clears survive a write. `sent` is the map the POST actually
       carried; those are consumed once the answer says the write landed. A clear ticked while the
       write was in flight is not in `sent`, so it stays pending — and a write that failed or was
       refused consumes nothing, because the user's × has not reached the server yet. */
    function consumeClears(pending, sent) {
        const left = Object.assign({}, pending || {});
        Object.keys(sent || {}).forEach((leaf) => { delete left[leaf]; });
        return left;
    }

    async function saveFeed(feed) {
        if (state.busy) return;
        state.busy = true;
        setMsg(feed, 'saving…');
        /* The clears this body will carry, captured before the POST so the answer can consume
           exactly those and no others. */
        const sent = Object.assign({}, state.clears[feed] || {});
        try {
            const body = {};
            body[feed] = writeBody(feed, readFields(feed), sent);
            const answer = await api('/api/control/feedkeys', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (answer && answer.ok) {
                state.clears[feed] = consumeClears(state.clears[feed], sent);
                render(answer);
                setMsg(feed, 'saved' + (answer.applied === false ? ' (engine settings not re-read — restart the engine)' : ''));
            } else {
                setMsg(feed, String((answer && answer.error) || 'the save was refused'), 'bad');
            }
        } catch (e) {
            setMsg(feed, 'the save failed: ' + ((e && e.message) || String(e)), 'bad');
        }
        state.busy = false;
    }

    async function checkFeed(feed) {
        setMsg(feed, 'checking…');
        try {
            const payload = await api(checkUrl(feed));
            const sentence = checkSentence(feed, payload);
            setMsg(feed, sentence, (payload && payload.ok === true) ? '' : 'bad');
        } catch (e) {
            setMsg(feed, 'the check failed: ' + ((e && e.message) || String(e)), 'bad');
        }
    }

    async function saveLanes() {
        const lanes = {};
        const cal = el(LANES.calendar.id);
        const news = el(LANES.news.id);
        if (cal) lanes.calendar = cal.value;
        if (news) lanes.news = news.value;
        try {
            const answer = await api('/api/control/feedkeys', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lanes: lanes }),
            });
            if (answer && answer.ok) render(answer);
            else if (cal) setMsg('calendar', String((answer && answer.error) || 'the lanes were refused'), 'bad');
        } catch (e) {
            if (cal) setMsg('calendar', 'the lane save failed: ' + ((e && e.message) || String(e)), 'bad');
        }
    }

    function onClick(ev) {
        const button = ev.target.closest ? ev.target.closest('[data-fk-act]') : null;
        if (!button) return;
        const act = button.getAttribute('data-fk-act');
        const feed = button.getAttribute('data-fk-feed');
        if (!feed || !SPECS[feed]) return;
        if (act === 'save') { void saveFeed(feed); return; }
        if (act === 'check') { void checkFeed(feed); return; }
        if (act === 'clear') {
            const leaf = button.getAttribute('data-fk-leaf');
            if (!leaf || CREDS.indexOf(leaf) < 0) return;
            state.clears[feed] = state.clears[feed] || {};
            state.clears[feed][leaf] = true;
            const node = el(fieldId(feed, leaf));
            if (node) node.value = '';
            setMsg(feed, 'that stored value will be removed on Save');
        }
    }

    function watch() {
        ensureStyles();
        const host = el(HOST);
        if (host) host.addEventListener('click', onClick);
        const cal = el(LANES.calendar.id);
        const news = el(LANES.news.id);
        /* Saved the moment they change: a lane the user has to re-pick every launch is a lost setting. */
        if (cal) cal.addEventListener('change', function () { void saveLanes(); });
        if (news) news.addEventListener('change', function () { void saveLanes(); });
        /* The card reads itself again whenever the Settings view is opened — the state it shows is
           the state on disk, not the state the page happened to load with. */
        const section = document.querySelector('.view[data-view="settings"]');
        if (section && typeof MutationObserver === 'function') {
            new MutationObserver(function () {
                if (section.classList.contains('active')) void load();
            }).observe(section, { attributes: true, attributeFilter: ['class'] });
        }
        void load();
    }

    const surface = {
        escape: escape, stateWord: stateWord, writeBody: writeBody, checkUrl: checkUrl,
        checkSentence: checkSentence, fieldHtml: fieldHtml, rowHtml: rowHtml, rowsHtml: rowsHtml,
        pillText: pillText, savedLanes: savedLanes, specFor: specFor, fieldId: fieldId, msgId: msgId,
        consumeClears: consumeClears,
        render: render, load: load, watch: watch, state: () => state.last,
    };
    if (typeof window !== 'undefined') window.OFAPFEEDKEYS = surface;
    if (typeof module !== 'undefined' && module.exports) module.exports = surface;

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
