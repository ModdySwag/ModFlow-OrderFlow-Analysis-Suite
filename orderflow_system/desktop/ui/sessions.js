/* sessions.js — the Sessions panel: the session clock, the template picker, the roll table.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/atlas/sessions.py :: GET /api/atlas/sessions):
 *   → { ok, at_ms, at, symbol, root, how, template{name,title,exchange,timezone,days,open,close,
 *       symbols,breaks,holidays,holiday_rule,note}, templates[{…template, builtin, active}],
 *       state{state,phase,reason,holiday,local{date,time,weekday_name,offset_minutes},session_date,
 *       open_ms,close_ms,next_open_ms,next_close_ms,minutes_to_open,minutes_to_close,elapsed_minutes,
 *       session_minutes,break_minutes,trade_minutes,elapsed_share,progress_pct,breaks[],hours,days[],
 *       problems[],note,timezone,timezone_known}, holidays[{date,name,closed,close,days_away,weekday}],
 *       rolls[{ok,root,kind,label,venue,rule,note,contracts[{symbol,month,expiry,roll,days_to_expiry,
 *       days_to_roll,front}],front,front_month,next_roll,days_to_roll,funding[]}], settings{…} }
 *   A refusal is { ok: false, detail } and the banner prints the SERVER'S own sentence.
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - The clock is the server's arithmetic, re-read on demand and on the panel's own cadence; the
 *     COUNTDOWN between payloads is local (the payload's stamps against the browser's clock), so the
 *     seconds move without a request a second. The panel never decides a market is open.
 *   - Every sentence about a session is the server's: "open", "the weekend", "Independence Day
 *     (observed)", "the session is in a break". This module formats stamps and picks the words.
 *   - The picker lists the library and the user's copies (the payload's `templates`), built-ins
 *     marked. "Set as active" and "Copy into my templates" post the settings block to the app's OWN
 *     config route; this module declares no write route of its own.
 *   - Days-to-roll at or under ROLL_SOON is highlighted, and each root prints its own rule, so a date
 *     is never a number without the convention beside it.
 *   - One timer (the 1 s clock face) and it is on the pause registry. Everything else is event-driven.
 */
(function () {
    'use strict';

    var VERSION = '0.1.0';
    var VIEW = '.view[data-view="sessions"]';
    var HOST = 'sessionsBody';
    var TICK_MS = 1000;                 // the clock face; the payload's cadence is REFRESH_MS
    var REFRESH_MS = 30000;
    var ROLL_SOON = 5;                  // days-to-roll from which the row is highlighted
    var DASH = '\u2014';

    function el(id) {
        return (typeof document !== 'undefined' && document) ? document.getElementById(id) : null;
    }
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function errText(err) { return String(err && err.message ? err.message : err); }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    /* ── the decisions (pure: pinned by sessions.selftest.js under node) ───────────────────────── */

    function pad(n) { return (n < 10 ? '0' : '') + n; }

    /* The server names the phase; these are the words on screen for it. */
    var PHASE_WORDS = {
        open: 'open', break: 'break', 'pre-open': 'pre-open', 'post-close': 'post-close',
        holiday: 'holiday', closed: 'closed',
    };
    var PHASE_CLASS = {
        open: 'is-open', break: 'is-break', 'pre-open': 'is-pre', 'post-close': 'is-post',
        holiday: 'is-holiday', closed: 'is-closed',
    };

    function phaseWord(phase) { return PHASE_WORDS[String(phase || '')] || 'unknown'; }
    function phaseClass(phase) { return PHASE_CLASS[String(phase || '')] || 'is-closed'; }

    /* A duration in words: the countdown a trader reads. Minutes to an hour, then h + m, then d + h.
     * The server rounds up, so a countdown never reads 0 while the boundary is still ahead. */
    function fmtDuration(minutes) {
        var total = Number(minutes);
        if (minutes === null || minutes === undefined || !isFinite(total)) return DASH;
        total = Math.max(0, Math.round(total));
        if (total < 60) return total + ' min';
        var hours = Math.floor(total / 60);
        if (hours < 24) return hours + ' h ' + pad(total % 60) + ' m';
        return Math.floor(hours / 24) + ' d ' + (hours % 24) + ' h';
    }

    function fmtOffset(minutes) {
        var total = Math.round(Number(minutes) || 0);
        var sign = total < 0 ? '-' : '+';
        total = Math.abs(total);
        return 'UTC' + sign + pad(Math.floor(total / 60)) + ':' + pad(total % 60);
    }

    /* The local clock, ticking between payloads: the payload's own wall time plus the drift since it
     * was read. The zone name and offset are the server's, never re-derived here. */
    function localClock(clock, nowMs) {
        var local = (clock && clock.local) || {};
        var base = Number(clock && clock.at_ms);
        var drift = (isFinite(base) && isFinite(Number(nowMs))) ? Math.max(0, Number(nowMs) - base) : 0;
        var parts = String(local.time || '').split(':');
        if (parts.length !== 2) return String(local.time || DASH);
        var seconds = (Number(parts[0]) * 3600 + Number(parts[1]) * 60 + Math.floor(drift / 1000)) % 86400;
        var offset = Number(local.offset_minutes);
        return pad(Math.floor(seconds / 3600)) + ':' + pad(Math.floor((seconds % 3600) / 60)) + ':'
            + pad(Math.floor(seconds % 60)) + ' ' + String((clock && clock.timezone) || 'UTC')
            + (isFinite(offset) ? ' (' + fmtOffset(offset) + ')' : '');
    }

    /* The one line under the state: what is about to happen, from the server's own stamps. */
    function countdownText(clock) {
        if (!clock || !clock.ok) return DASH;
        if (clock.state === 'open') return 'closes in ' + fmtDuration(clock.minutes_to_close);
        if (clock.phase === 'break') {
            return 'reopens in ' + fmtDuration(clock.minutes_to_open)
                + ' \u00b7 closes in ' + fmtDuration(clock.minutes_to_close);
        }
        var opens = 'opens in ' + fmtDuration(clock.minutes_to_open);
        if (clock.phase === 'holiday') {
            return 'closed for ' + String(clock.reason || 'a holiday') + ' \u00b7 ' + opens;
        }
        var why = String(clock.reason || '');
        return (why ? why + ' \u00b7 ' : '') + opens;
    }

    function progressPct(clock) {
        var share = clock && clock.elapsed_share;
        if (share === null || share === undefined || !isFinite(Number(share))) return null;
        return Math.max(0, Math.min(100, Math.round(Number(share) * 100)));
    }

    /* The template's own hours, always shown beside the clock: a countdown without its schedule is
     * not readable. The server's `hours` line wins (it knows about a session that wraps midnight). */
    function hoursText(clock, template) {
        var tpl = template || {};
        if (clock && clock.hours) return String(clock.hours);
        if (!tpl.name) return DASH;
        return String(tpl.open || '') + ' \u2192 ' + String(tpl.close || '') + ' ' + String(tpl.timezone || 'UTC');
    }

    var DAY_SHORT = { 1: 'mon', 2: 'tue', 3: 'wed', 4: 'thu', 5: 'fri', 6: 'sat', 7: 'sun' };

    function daysText(days) {
        var list = (days || []).slice().sort(function (a, b) { return a - b; });
        if (!list.length) return '';
        if (list.length === 7) return 'every day';
        if (list.join(',') === '1,2,3,4,5') return 'mon-fri';
        return list.map(function (day) { return DAY_SHORT[day] || String(day); }).join(', ');
    }

    function stateLine(clock) {
        if (!clock || !clock.ok) return DASH;
        var head = 'the session is ' + phaseWord(clock.phase);
        return (clock.reason && clock.phase !== 'open') ? head + ' \u00b7 ' + clock.reason : head;
    }

    /* ── the DOM half ─────────────────────────────────────────────────────────────────────────── */

    var state = { last: null, busy: false, at: 0, template: '', root: '', wire: false };

    function section() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector(VIEW);
    }

    function isActive() {
        var view = section();
        return !!(view && view.classList && view.classList.contains('active'));
    }

    function api(path, options) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path, options);
        if (typeof window !== 'undefined' && typeof window.fetch === 'function') {
            return window.fetch(path, options).then(function (res) { return res.json(); });
        }
        return Promise.reject(new Error('this context has no way to ask the app'));
    }

    /* The query only — every path literal stays at its call site, where the end-of-build audit can
     * read it (a path it cannot read is a path it cannot guard). */
    function queryFor(template, root) {
        var parts = [];
        if (template) parts.push('template=' + encodeURIComponent(template));
        if (root) parts.push('root=' + encodeURIComponent(root));
        return parts.length ? '?' + parts.join('&') : '';
    }

    function say(message, kind) {
        var box = el('sessionsBanner');
        if (!box) return;
        box.textContent = String(message || '');
        box.className = 'hint' + (kind ? ' ' + kind : '');
    }

    function templateOption(tpl, chosen) {
        var label = String(tpl.title || tpl.name) + ' \u00b7 ' + String(tpl.exchange || tpl.timezone)
            + (tpl.builtin ? '' : ' (mine)');
        return '<option value="' + esc(tpl.name) + '"' + (tpl.name === chosen ? ' selected' : '') + '>'
            + esc(label) + '</option>';
    }

    function pickerHtml(payload) {
        var rows = (payload && payload.templates) || [];
        var chosen = ((payload && payload.template) || {}).name || '';
        if (!rows.length) return '<div class="dim">no templates are configured</div>';
        return '<select id="sessionsPick" title="The template this panel reads. Set as active makes it '
            + 'the default for every view.">' + rows.map(function (tpl) {
                return templateOption(tpl, chosen);
            }).join('') + '</select>';
    }

    function holidayRows(holidays) {
        var rows = holidays || [];
        if (!rows.length) return '<tr><td colspan="4" class="dim">no holidays are set for this template</td></tr>';
        return rows.map(function (row) {
            var why = String(row.name || '') + (row.closed ? '' : ' (early close ' + String(row.close || '') + ')');
            return '<tr><td>' + esc(row.date) + '</td><td>' + esc(row.weekday || '') + '</td>'
                + '<td>' + esc(why) + '</td><td class="num">'
                + (isFinite(Number(row.days_away)) ? Number(row.days_away) + ' d' : DASH) + '</td></tr>';
        }).join('');
    }

    function contractRows(table) {
        var rows = (table && table.contracts) || [];
        if (!rows.length) {
            var funding = (table && table.funding) || [];
            if (funding.length) {
                return funding.map(function (row) {
                    return '<tr><td>' + esc(table.root) + ' perpetual</td><td>funding</td><td>'
                        + esc(row.at) + '</td><td class="num">' + fmtDuration(row.minutes_away) + '</td></tr>';
                }).join('');
            }
            return '<tr><td colspan="4" class="dim">no contracts in this window</td></tr>';
        }
        return rows.map(function (row) {
            var soon = isFinite(Number(row.days_to_roll)) && Number(row.days_to_roll) <= ROLL_SOON;
            return '<tr class="' + (soon ? 'sessions-soon' : '') + (row.front ? ' sessions-front' : '') + '">'
                + '<td>' + esc(row.symbol) + (row.front ? ' <span class="dim">front</span>' : '') + '</td>'
                + '<td>' + esc(row.expiry) + '</td><td>' + esc(row.roll) + '</td>'
                + '<td class="num">' + Number(row.days_to_roll) + ' d' + (soon ? ' \u25c0' : '') + '</td></tr>';
        }).join('');
    }

    function rollSection(rolls) {
        var tables = rolls || [];
        if (!tables.length) return '<div class="dim">no roots are configured for the roll table</div>';
        return tables.map(function (table) {
            var root = String(table.root || '');
            if (table.ok !== true) {
                return '<div class="sessions-roll"><div class="sessions-roll-head"><b>' + esc(root || '?')
                    + '</b><div class="dim">' + esc(table.detail || 'no roll rule') + '</div></div></div>';
            }
            var summary;
            if (table.kind === 'perpetual') {
                var nextFunding = (table.funding || [])[0];
                summary = 'no roll \u00b7 funding ' + (nextFunding
                    ? 'in ' + fmtDuration(nextFunding.minutes_away) : DASH);
            } else {
                summary = 'front ' + String(table.front || DASH) + ' \u00b7 rolls ' + String(table.next_roll || DASH)
                    + ' (in ' + fmtDuration(table.days_to_roll === null || table.days_to_roll === undefined
                        ? null : Number(table.days_to_roll) * 1440) + ')';
            }
            return '<div class="sessions-roll"><div class="sessions-roll-head">'
                + '<b>' + esc(root) + '</b> <span class="dim">' + esc(table.label || '') + ' \u00b7 '
                + esc(table.venue || '') + '</span><div class="dim">' + summary + '</div>'
                + '<div class="dim">' + esc(table.rule || '') + '</div></div>'
                + '<table class="data"><thead><tr><th>Contract</th><th>Expiry</th><th>Roll</th>'
                + '<th>To roll</th></tr></thead><tbody>' + contractRows(table) + '</tbody></table>'
                + '<div class="dim sessions-note">' + esc(table.note || '') + '</div></div>';
        }).join('');
    }

    function shellHtml() {
        return ''
            + '<div class="card"><div class="card-head"><span class="card-title">Session clock</span>'
            + '<div class="spacer"></div><span class="dim" id="sessionsHow">' + DASH + '</span></div>'
            + '<div class="card-body">'
            + '<div class="sessions-line"><span id="sessionsLamp" class="sessions-lamp is-closed"></span>'
            + '<b id="sessionsPhase">closed</b> <span class="dim" id="sessionsTitle"></span></div>'
            + '<div class="sessions-sub" id="sessionsCountdown">' + DASH + '</div>'
            + '<div class="sessions-sub" id="sessionsLocal">' + DASH + '</div>'
            + '<div class="sessions-bar"><div class="sessions-bar-fill" id="sessionsProgressFill"></div></div>'
            + '<div class="dim" id="sessionsProgress">' + DASH + '</div>'
            + '<div class="dim" id="sessionsHours">' + DASH + '</div>'
            + '<div class="dim" id="sessionsProblems"></div>'
            + '</div></div>'
            + '<div class="card"><div class="card-head"><span class="card-title">Template</span>'
            + '<div class="spacer"></div><span class="dim" id="sessionsCount">' + DASH + '</span></div>'
            + '<div class="card-body">'
            + '<div class="row"><div class="field"><label>Session template</label>'
            + '<div id="sessionsPickBox">loading\u2026</div></div>'
            + '<button class="btn small" id="sessionsActivate" type="button"'
            + ' title="Make this template the default every view reads.">Set as active</button>'
            + '<button class="btn small" id="sessionsCopy" type="button"'
            + ' title="Append a copy of the picked template to your own templates, then edit it in Settings.">'
            + 'Copy into my templates</button>'
            + '</div>'
            + '<div class="dim" id="sessionsNote"></div>'
            + '<div class="dim" id="sessionsMsg"></div>'
            + '</div></div>'
            + '<div class="grid cols-2">'
            + '<div class="card"><div class="card-head"><span class="card-title">Roll table</span>'
            + '<div class="spacer"></div><span class="dim" id="sessionsRollAt">' + DASH + '</span></div>'
            + '<div class="card-body" id="sessionsRolls"><div class="dim">loading\u2026</div></div></div>'
            + '<div class="card"><div class="card-head"><span class="card-title">Holidays</span>'
            + '<div class="spacer"></div><span class="dim" id="sessionsHolidayRule"></span></div>'
            + '<div class="card-body" style="padding:0;overflow:auto;max-height:320px">'
            + '<table class="data"><thead><tr><th>Date</th><th>Day</th><th>Why</th><th>Away</th></tr></thead>'
            + '<tbody id="sessionsHolidays"><tr><td colspan="4" class="dim">loading\u2026</td></tr></tbody>'
            + '</table></div></div>'
            + '</div>'
            + '<div class="card"><div class="card-head"><span class="card-title">What the clock is reading</span>'
            + '<div class="spacer"></div><button class="btn small" id="sessionsRefresh">Refresh</button></div>'
            + '<div class="card-body"><div class="dim" id="sessionsInputs">' + DASH + '</div></div></div>';
    }

    var STYLE = `.sessions-body { display: flex; flex-direction: column; gap: 10px; }
.sessions-line { display: flex; align-items: center; gap: 8px; font-size: 16px; }
.sessions-lamp { width: 10px; height: 10px; border-radius: 50%; background: var(--text-secondary); display: inline-block; }
.sessions-lamp.is-open { background: var(--ok, #3fb950); box-shadow: 0 0 6px var(--ok, #3fb950); }
.sessions-lamp.is-break, .sessions-lamp.is-pre, .sessions-lamp.is-post, .sessions-lamp.is-holiday { background: var(--warn, #e0a33c); }
.sessions-sub { font-size: 12.5px; opacity: .9; }
.sessions-bar { height: 6px; border-radius: 3px; background: var(--border); overflow: hidden; margin: 6px 0 3px; }
.sessions-bar-fill { height: 100%; width: 0; background: var(--accent, #58a6ff); }
.sessions-roll { margin-bottom: 12px; }
.sessions-roll table.data { width: 100%; }
.sessions-roll td.num, .sessions-roll th:last-child { text-align: right; }
tr.sessions-soon td { color: var(--warn, #e0a33c); }
tr.sessions-front td:first-child { font-weight: 600; }
.sessions-note { font-size: 11.5px; margin-top: 3px; }
.sessions-body td.num { text-align: right; }`;

    function ensureStyles() {
        if (typeof document === 'undefined' || !document || !document.head) return;
        if (document.getElementById('sessionsStyles')) return;
        var tag = document.createElement('style');
        tag.id = 'sessionsStyles';
        tag.textContent = STYLE;
        document.head.appendChild(tag);
    }

    /* The panel's own markup, into the section's host element (index.html carries the empty host; a
     * page without it gets one built here, so the module can never depend on markup it does not own). */
    function ensureHost() {
        if (typeof document === 'undefined' || !document || !document.createElement) return null;
        var view = section();
        if (!view) return null;
        var host = el(HOST);
        if (!host) {
            host = document.createElement('div');
            host.id = HOST;
            host.className = 'sessions-body';
            view.appendChild(host);
        }
        if (!host.getAttribute('data-sessions-built')) {
            host.innerHTML = shellHtml();
            host.setAttribute('data-sessions-built', '1');
            ensureStyles();
        }
        return host;
    }

    function paint(payload) {
        if (payload) state.last = payload;
        var data = state.last || {};
        ensureHost();
        var clock = data.state || {};
        var tpl = data.template || {};

        var lamp = el('sessionsLamp');
        if (lamp) lamp.className = 'sessions-lamp ' + phaseClass(clock.phase);
        var phase = el('sessionsPhase');
        if (phase) phase.textContent = data.ok ? phaseWord(clock.phase) : 'closed';
        var title = el('sessionsTitle');
        if (title) {
            title.textContent = tpl.title
                ? String(tpl.title) + (tpl.exchange ? ' \u00b7 ' + String(tpl.exchange) : '') : '';
        }
        var how = el('sessionsHow');
        if (how) how.textContent = data.ok ? String(data.how || '') : '';
        var hours = el('sessionsHours');
        if (hours) hours.textContent = data.ok ? hoursText(clock, tpl) : DASH;
        var problems = el('sessionsProblems');
        if (problems) problems.textContent = ((clock.problems || []).join(' \u00b7 ')) || '';
        var note = el('sessionsNote');
        if (note) note.textContent = tpl.note ? String(tpl.note) : '';
        var count = el('sessionsCount');
        if (count) count.textContent = ((data.templates || []).length) + ' template(s)';

        var box = el('sessionsPickBox');
        if (box) box.innerHTML = pickerHtml(data);
        var holidays = el('sessionsHolidays');
        if (holidays) holidays.innerHTML = holidayRows(data.holidays);
        var rule = el('sessionsHolidayRule');
        if (rule) rule.textContent = tpl.holiday_rule ? ('rule: ' + String(tpl.holiday_rule)) : 'dates only';
        var rolls = el('sessionsRolls');
        if (rolls) rolls.innerHTML = rollSection(data.rolls);
        var rollAt = el('sessionsRollAt');
        if (rollAt) rollAt.textContent = data.at ? String(data.at) : DASH;
        var settings = data.settings || {};
        var inputs = el('sessionsInputs');
        if (inputs) {
            inputs.textContent = data.ok
                ? ('template ' + String(tpl.name || DASH) + ' \u00b7 timezone ' + String(tpl.timezone || DASH)
                   + (clock.timezone_known === false ? ' (not a known zone — read as UTC)' : '')
                   + ' \u00b7 matched by ' + String(data.how || DASH)
                   + ' \u00b7 session ' + String(clock.session_date || DASH)
                   + ' \u00b7 roll roots ' + ((settings.roots || []).join(', ') || DASH))
                : 'waiting for a session template';
        }
        say(data.ok ? '' : String(data.detail || 'the session could not be read'), data.ok ? '' : 'bad');
        state.at = Date.now();
        if (tpl.name) state.template = String(tpl.name);
        return data;
    }

    /* The live half of the clock: the countdown and the progress bar, recomputed from the last
     * payload against the browser's clock on every tick. */
    function paintClock() {
        var data = state.last || {};
        var clock = data.state || {};
        var now = Date.now();
        var stamp = Number(data.at_ms);
        var drift = isFinite(stamp) ? Math.max(0, now - stamp) : 0;

        var line = el('sessionsCountdown');
        if (line) line.textContent = countdownText(clock);
        var local = el('sessionsLocal');
        if (local) local.textContent = localClock(clock, now);
        var pct = progressPct(clock);
        if (pct !== null && clock.state === 'open') {
            pct = Math.max(0, Math.min(100, pct + Math.round((drift / 60000 / clock.session_minutes) * 100)));
        }
        var fill = el('sessionsProgressFill');
        if (fill) fill.style.width = (pct === null ? 0 : pct) + '%';
        var text = el('sessionsProgress');
        if (text) {
            text.textContent = clock.session_minutes
                ? ((clock.session_date ? 'session ' + String(clock.session_date) + ' \u00b7 ' : '')
                   + fmtDuration(clock.elapsed_minutes) + ' of ' + fmtDuration(clock.session_minutes)
                   + (clock.break_minutes ? ' (' + fmtDuration(clock.trade_minutes) + ' tradeable)' : ''))
                : DASH;
        }
    }

    function load(force) {
        state.busy = true;
        return api('/api/atlas/sessions' + queryFor(state.template, state.root)).then(function (payload) {
            paint(payload);
            return payload;
        }).catch(function (err) {
            say('the session could not be read: ' + errText(err), 'bad');
            var rolls = el('sessionsRolls');
            if (rolls) rolls.innerHTML = '<div class="dim">the roll table could not be read</div>';
            return null;
        }).then(function (payload) {
            state.busy = false;
            if (force !== true) state.at = Date.now();
            return payload;
        });
    }

    /* ── the two writes: both to the app's own config route, never to a route of this module's ─── */

    function currentPick() {
        var pick = el('sessionsPick');
        return pick && pick.value ? String(pick.value) : String(state.template || '');
    }

    function setMsg(text, kind) {
        var node = el('sessionsMsg');
        if (!node) return;
        node.textContent = String(text || '');
        node.style.color = kind === 'bad' ? 'var(--warn, #e0a33c)' : '';
    }

    /* The config's own template list with the copy appended: this module posts the WHOLE list,
     * because a partial merge would have to guess an order it cannot see. */
    function templateBlockWith(copy, data) {
        var list = ((data && data.templates) || []).filter(function (row) {
            return row && row.builtin !== true;
        }).map(function (row) {
            var out = {};
            Object.keys(row).forEach(function (key) {
                if (key !== 'builtin' && key !== 'active') out[key] = row[key];
            });
            return out;
        });
        list.push(copy);
        return { templates: list };
    }

    function activate() {
        var name = currentPick();
        if (!name) return;
        setMsg('saving\u2026');
        api('/api/control/config', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessions: { active: name } }),
        }).then(function (answer) {
            if (answer && answer.ok) {
                setMsg('the active template is now ' + name);
                void load(true);
            } else {
                setMsg(String((answer && (answer.detail || answer.error)) || 'the save was refused'), 'bad');
            }
        }).catch(function (err) { setMsg('the save failed: ' + errText(err), 'bad'); });
    }

    /* A copy, never a rename: the built-ins stay as shipped and the copy is what the user edits. */
    function copyBuiltin() {
        var data = state.last || {};
        var name = currentPick();
        var found = null;
        ((data.templates) || []).forEach(function (row) { if (row && row.name === name) found = row; });
        if (!found) { setMsg('pick a template first'); return; }
        var copy = {};
        Object.keys(found).forEach(function (key) {
            if (key !== 'builtin' && key !== 'active') copy[key] = found[key];
        });
        copy.name = name + '-copy';
        copy.title = String(found.title || name) + ' (copy)';
        setMsg('copying\u2026');
        api('/api/control/config', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessions: templateBlockWith(copy, data) }),
        }).then(function (answer) {
            if (answer && answer.ok) {
                setMsg('copied ' + name + ' to ' + copy.name + ' \u2014 edit it in Settings, then pick it here');
                void load(true);
            } else {
                setMsg(String((answer && (answer.detail || answer.error)) || 'the copy was refused'), 'bad');
            }
        }).catch(function (err) { setMsg('the copy failed: ' + errText(err), 'bad'); });
    }

    function onClick(ev) {
        var node = (ev.target && ev.target.closest)
            ? ev.target.closest('#sessionsRefresh, #sessionsActivate, #sessionsCopy') : null;
        if (!node) return;
        if (node.id === 'sessionsRefresh') { void load(true); return; }
        if (node.id === 'sessionsActivate') { activate(); return; }
        if (node.id === 'sessionsCopy') copyBuiltin();
    }

    function onChange(ev) {
        var node = ev.target;
        if (!node || node.id !== 'sessionsPick') return;
        state.template = String(node.value || '');
        void load(true);
    }

    function tick() {
        if (!isActive()) return;
        if (typeof document !== 'undefined' && document && document.hidden) return;
        if (win().OFAP_PAUSED) return;
        var intent = win().OFAPINTENT;
        if (intent && typeof intent.anyHeld === 'function' && intent.anyHeld()) return;
        paintClock();
        if (!state.busy && (Date.now() - state.at) > REFRESH_MS) void load(true);
    }

    function wire() {
        if (state.wire) return;
        state.wire = true;
        var body = ensureHost();
        if (body) {
            body.addEventListener('click', onClick);
            body.addEventListener('change', onChange);
        }
        /* The clock face ticks once a second, on the app's pause registry: P (or the topbar chip)
           clears the timer and resume rebuilds it — the suite's rule for every repeating job. */
        var start = function () {
            var id = setInterval(tick, TICK_MS);
            if (window.OFAPPause && window.OFAPPause.register) window.OFAPPause.register(id, start);
            return id;
        };
        state.timer = start();
        var view = section();
        if (view && typeof MutationObserver === 'function') {
            new MutationObserver(function () { if (isActive()) void load(true); })
                .observe(view, { attributes: true, attributeFilter: ['class'] });
        }
    }

    function watch() {
        wire();
        if (isActive()) void load(true);
        return true;
    }

    var surface = {
        VERSION: VERSION, VIEW: VIEW, TICK_MS: TICK_MS, REFRESH_MS: REFRESH_MS,
        ROLL_SOON: ROLL_SOON, DASH: DASH,
        esc: esc, pad: pad, phaseWord: phaseWord, phaseClass: phaseClass, fmtDuration: fmtDuration,
        fmtOffset: fmtOffset, localClock: localClock, countdownText: countdownText,
        progressPct: progressPct, hoursText: hoursText, daysText: daysText, stateLine: stateLine,
        queryFor: queryFor, templateOption: templateOption, pickerHtml: pickerHtml,
        holidayRows: holidayRows, contractRows: contractRows, rollSection: rollSection,
        templateBlockWith: templateBlockWith, shellHtml: shellHtml,
        paint: paint, paintClock: paintClock, load: load, wire: wire, watch: watch,
        errorText: errText, state: function () { return state.last; },
    };
    if (typeof window !== 'undefined') window.OFAPSESSIONS = surface;
    if (typeof module !== 'undefined' && module.exports) module.exports = surface;

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
