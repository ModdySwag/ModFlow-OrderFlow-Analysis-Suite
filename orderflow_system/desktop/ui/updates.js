/* updates.js — the program-update panel (R7): check on load, check on a timer, never interrupt.
 *
 * One call drives everything: `GET /api/control/update/status` returns the remembered check plus
 * the settings, and asks GitHub itself when the interval has passed (so page loads are cheap and
 * the wire is touched once per interval). `?refresh=1` forces it — that is the menu's Check now.
 *
 * The interaction rule lives here, on the client, because only the client knows what the user is
 * doing: a found update is announced when the hands are off the keyboard and the window is up;
 * while the user is typing or the app is paused the news waits (a short bounded retry, not a
 * nag loop), and it is always visible on demand in the menu and this card.
 */
(function () {
    'use strict';

    var POLL_MS = 30 * 60 * 1000;      // updates move in days; half an hour is generous
    var RETRY_MS = 60 * 1000;          // a pending announcement, while the user is busy
    var MAX_RETRIES = 10;

    var timer = null;
    var retryTimer = null;
    var retries = 0;
    var announced = '';                // the version we already told the user about
    var lastPayload = null;

    function $(id) { return document.getElementById(id); }

    function esc(text) {
        return String(text == null ? '' : text)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function mb(n) {
        n = Number(n) || 0;
        if (n >= 1e9) return (n / 1e9).toFixed(2) + ' GB';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + ' MB';
        if (n >= 1e3) return (n / 1e3).toFixed(0) + ' KB';
        return n + ' B';
    }

    function shortTime(iso) {
        var m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(String(iso || ''));
        return m ? m[1] + ' ' + m[2] + ' UTC' : String(iso || '');
    }

    function fill(id, value) {
        var el = $(id);
        if (el && document.activeElement !== el) el.value = value;
    }

    function say(id, text, kind) {
        var el = $(id);
        if (!el) return;
        el.textContent = String(text || '');
        el.className = 'hint' + (kind ? ' ' + kind : '');
    }

    /* ── the state the menu bar and the card both read ─────────────────────────────── */
    function state() {
        return (window.OFAPUPDATES && OFAPUPDATES.state) || null;
    }

    function publish(payload) {
        lastPayload = payload || {};
        var st = lastPayload.state || null;
        OFAPUPDATES.state = st;
        OFAPUPDATES.settings = lastPayload.settings || {};
        OFAPUPDATES.download_dir = lastPayload.download_dir || '';
        if (window.OFAPMENU && typeof OFAPMENU.refresh === 'function') OFAPMENU.refresh();
    }

    /* ── the card ──────────────────────────────────────────────────────────────────── */
    function render(payload) {
        var st = (payload && payload.state) || {};
        var settings = (payload && payload.settings) || {};
        var current = st.current || {};
        var latest = st.latest || null;
        var pill = $('updPillText');
        var tag = $('updCurrent');

        if (tag) tag.textContent = String(current.display || current.version || '?');
        if (pill) {
            if (st.checking) pill.textContent = 'checking…';
            else if (st.update_available && latest) pill.textContent = 'update available — ' + latest.version;
            else if (st.skipped && latest) pill.textContent = 'skipped ' + latest.version;
            else if (latest && st.ok) pill.textContent = 'up to date';
            else if (st.ok && !latest) pill.textContent = 'no releases yet';
            else if (st.error) pill.textContent = 'could not check';
            else pill.textContent = 'not checked yet';
        }

        var status = $('updStatus');
        if (status) {
            var bits = [];
            if (st.checked_at_ms) bits.push('checked ' + shortTime(new Date(st.checked_at_ms).toISOString()));
            if (latest) {
                bits.push('newest on the ' + (st.channel || 'stable') + ' channel: ' + latest.version +
                    (latest.published_at ? ' (' + shortTime(latest.published_at) + ')' : ''));
            }
            if (st.error) bits.push(st.error);
            else if (st.ok && latest && !st.update_available) bits.push(st.skipped
                ? 'that version is skipped — un-skip it to be told again'
                : 'this window is the newest build');
            else if (st.ok && !latest) bits.push('the repository has no releases yet — nothing to compare against');
            status.textContent = bits.join(' · ') || 'not checked yet';
        }

        var notes = $('updNotes');
        if (notes) {
            notes.textContent = latest && latest.notes
                ? ('What\'s in ' + String(latest.version) + ':\n' + String(latest.notes).slice(0, 4000))
                : '';
        }

        fill('updMode', settings.mode || 'check');
        fill('updInterval', settings.interval_hours != null ? settings.interval_hours : 6);
        fill('updChannel', settings.channel || 'stable');
        fill('updDir', settings.download_dir || '');
    }

    /* ── interaction-aware announcement ────────────────────────────────────────────── */
    function freeToSpeak() {
        if (document.hidden) return false;
        if (window.OFAP_PAUSED) return false;
        if (window.OFAPINTENT && typeof OFAPINTENT.anyHeld === 'function' && OFAPINTENT.anyHeld()) return false;
        return true;
    }

    function announce(version) {
        if (!freeToSpeak()) return false;
        if (window.OFAPPOST) { /* the shell's toast channel when it exists */ }
        var host = $('statusHint');
        if (host) host.textContent = 'ModFlow ' + version + ' is available — Update ▸ Download in the menu bar';
        announced = version;
        return true;
    }

    function maybeAnnounce(st) {
        if (!st || !st.update_available) return;
        var version = String((st.latest || {}).version || '');
        if (!version || version === announced) return;
        if (announce(version)) return;
        if (retryTimer || retries >= MAX_RETRIES) return;
        retryTimer = setTimeout(function () {
            retryTimer = null;
            retries += 1;
            maybeAnnounce(state());
        }, RETRY_MS);
    }

    /* ── the wire ──────────────────────────────────────────────────────────────────── */
    function fetchState(refresh) {
        return window.api('/api/control/update/status' + (refresh ? '?refresh=1' : '')).then(function (payload) {
            publish(payload);
            render(payload);
            maybeAnnounce(payload && payload.state);
            return payload;
        }).catch(function () { /* offline: the card keeps its last render */ });
    }

    function onScreen() {
        if (document.hidden || window.OFAP_PAUSED) return false;
        var section = document.querySelector('.view[data-view="settings"]');
        if (!section) return false;
        return section.classList.contains('active') || section.style.display === 'flex';
    }

    function boot() {
        var b;
        if ((b = $('btnUpdCheck'))) b.onclick = function () {
            say('updResult', 'checking…');
            window.api('/api/control/update/check', { method: 'POST', body: {} }).then(function (payload) {
                publish(payload);
                render(payload);
                var st = (payload && payload.state) || {};
                say('updResult', st.update_available
                    ? ('a newer build exists: ' + ((st.latest || {}).version || ''))
                    : (st.ok ? 'this window is the newest build' : ('could not check: ' + (st.error || ''))));
            }).catch(function (err) { say('updResult', 'could not check: ' + err); });
        };
        if ((b = $('btnUpdDownload'))) b.onclick = function () {
            say('updResult', 'downloading…');
            window.api('/api/control/update/download', { method: 'POST', body: {} }).then(function (res) {
                var d = (res && res.download) || {};
                say('updResult', res && res.ok
                    ? ('saved ' + d.path + ' (' + mb(d.bytes) + (d.verified ? ', checksum verified' : ', no checksum published)'))
                    : ('download failed: ' + ((res && res.error) || (d.error) || 'unknown')));
            }).catch(function (err) { say('updResult', 'download failed: ' + err); });
        };
        if ((b = $('btnUpdOpen'))) b.onclick = function () { openFolder(); };
        if ((b = $('btnUpdPage'))) b.onclick = function () { openPage(); };
        if ((b = $('btnUpdSkip'))) b.onclick = function () {
            var st = state() || {};
            var version = String((st.latest || {}).version || '');
            var unskip = !!st.skipped;
            window.api('/api/control/update/skip', { method: 'POST', body: { version: unskip ? '' : version } })
                .then(function (payload) {
                    publish(payload);
                    render(payload);
                    say('updResult', unskip ? ('un-skipped ' + version) : ('skipped ' + version + ' — you can un-skip it here'));
                });
        };
        ['updMode', 'updChannel'].forEach(function (id) {
            var el = $(id);
            if (!el) return;
            el.onchange = function () { saveSettings(); };
        });
        ['updInterval', 'updDir'].forEach(function (id) {
            var el = $(id);
            if (!el) return;
            el.onchange = function () { saveSettings(); };
        });

        function saveSettings() {
            var patch = {
                mode: ($('updMode') || {}).value || 'check',
                channel: ($('updChannel') || {}).value || 'stable',
                interval_hours: Number(($('updInterval') || {}).value || 6),
                download_dir: ($('updDir') || {}).value || '',
            };
            window.api('/api/control/update/settings', { method: 'POST', body: patch }).then(function (res) {
                if (res && res.ok) {
                    say('updResult', 'saved — checks every ' + res.settings.interval_hours + ' h on the ' +
                        res.settings.channel + ' channel, ' + res.settings.mode);
                    fetchState(false);
                }
            });
        }

        /* the check on load, then the slow timer; the card repaints whenever Settings is up */
        fetchState(false);
        if (!timer) {
            timer = setInterval(function () { fetchState(false); }, POLL_MS);
        }
        var wrap = window.showView;
        if (typeof wrap === 'function' && !wrap.__ofapWrapped_updates) {
            var wrapped = function (name) {
                var out = wrap.apply(this, arguments);
                if (name === 'settings') setTimeout(function () { if (onScreen()) fetchState(false); }, 500);
                return out;
            };
            wrapped.__ofapWrapped_updates = true;
            window.showView = wrapped;
        }
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) fetchState(false);      // back at the desk: re-ask once
        });
    }

    function openFolder() {
        return window.api('/api/control/update/open', { method: 'POST', body: { what: 'downloads' } })
            .then(function (res) {
                if (!res || res.ok === false) say('updResult', 'could not open the folder: ' + ((res && res.error) || ''));
                return res;
            });
    }

    function openPage() {
        return window.api('/api/control/update/open', { method: 'POST', body: { what: 'page' } })
            .then(function (res) { return res; });
    }

    window.OFAPUPDATES = {
        state: null, settings: {}, download_dir: '',
        refresh: function (force) { return fetchState(!!force); },
        download: function () {
            var b = $('btnUpdDownload');
            if (b) b.click();
        },
        skip: function (version) {
            window.api('/api/control/update/skip', { method: 'POST', body: { version: version } })
                .then(function (payload) { publish(payload); render(payload); });
        },
        openFolder: openFolder,
        openPage: openPage,
        openSettings: function () {
            if (window.showView) window.showView('settings');
            setTimeout(function () {
                var card = $('updCurrent');
                if (card && card.scrollIntoView) card.scrollIntoView({ block: 'center' });
            }, 400);
        },
        showNotes: function () {
            if (window.showView) window.showView('settings');
            setTimeout(function () {
                var notes = $('updNotes');
                if (notes && notes.scrollIntoView) notes.scrollIntoView({ block: 'center' });
            }, 400);
        },
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
