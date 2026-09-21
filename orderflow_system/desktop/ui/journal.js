/* journal.js — the Journal view (R10 + P1-7): rows, statistics, notes, the HTML statement, and the
 * deep read — R multiples, per-setup stats and the P&L calendar.
 *
 * Everything comes from /api/control/journal (read-only reads of the app's own trade_journal),
 * /journal/note and /journal/statement. The statistics are the server's (desktop/journal.py, pure
 * and pinned); this module formats what it was sent. It never computes a statistic of its own: where
 * the payload carries no number the panel says n/a, because a guessed figure is worse than a blank.
 */
(function () {
    'use strict';

    var selected = null;
    var rows = [];
    var stats = {};          // the last payload's figures: the tiles, the strip and the calendar
    var calIndex = null;     // which month the calendar shows; null = the newest one it was sent

    var WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

    function $(id) {
        if (typeof document === 'undefined' || !document || !document.getElementById) return null;
        return document.getElementById(id);
    }
    /* Quotes are escaped too: the heat cells put a title string into an attribute, and a value that
       reaches an attribute unescaped is how a payload ends up writing markup into the page. */
    var esc = (t) => String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

    function utc(ms) {
        if (!ms) return '—';
        try { return new Date(Number(ms)).toISOString().replace('T', ' ').slice(0, 16); } catch (e) { return '—'; }
    }

    function pct(x) { return x == null ? 'n/a' : (Math.round(Number(x) * 1000) / 10).toString() + '%'; }
    function n2(x) { return x == null ? 'n/a' : (Math.round(Number(x) * 100) / 100).toString(); }
    function n0(x) { return x == null || isNaN(Number(x)) ? 'n/a' : String(Math.round(Number(x))); }
    function signed(x, dp, suffix) {
        if (x == null || isNaN(Number(x))) return 'n/a';
        var v = Number(x);
        return (v >= 0 ? '+' : '') + v.toFixed(dp == null ? 2 : dp) + (suffix || '');
    }

    function tile(label, value, sub) {
        return '<div class="sy-tile"><div class="sy-line"><span class="sy-name">' + esc(label) + '</span>' +
            '<div class="spacer"></div><span class="tag dim">' + esc(value) + '</span></div>' +
            (sub ? '<div class="sy-detail">' + esc(sub) + '</div>' : '') + '</div>';
    }

    /* ══ P1-7: the deep figures ═══════════════════════════════════════════════ */

    /* The server's per-tag block as table rows. Absent figures stay 'n/a' — a tag with no R on any
       of its rows has no average R, and printing 0.00 would read as one that broke even. */
    function setupRows(block) {
        return (block && block.length ? block : []).map(function (g) {
            g = g || {};
            return {
                tag: g.key == null ? 'untagged' : String(g.key),
                trades: n0(g.trades),
                win: pct(g.win_rate),
                /* The average rests only on the rows that yield an R: say so when that is fewer
                   than the group's trades, rather than letting it read as the whole group (§148 T3-F14). */
                avgR: n2(g.avg_r) + (Number(g.r_count) < Number(g.trades)
                    ? ' (' + n0(g.r_count) + ' of ' + n0(g.trades) + ')' : ''),
                expectancy: n2(g.expectancy),
                profitFactor: n2(g.profit_factor)
            };
        });
    }

    /* Heat level 0..4 for one day against the month's largest absolute day. 0 is a day with no
       P&L at all; a real day is never level 0 and the peak is always level 4, so the biggest day
       cannot read as nothing and the smallest cannot disappear. */
    function heatLevel(value, peak) {
        var v = Math.abs(Number(value));
        if (!isFinite(v) || v <= 0) return 0;
        var p = Math.abs(Number(peak));
        if (!isFinite(p) || p <= 0) p = v;
        return Math.min(4, Math.max(1, Math.ceil((v / p) * 4)));
    }

    function heatStyle(value, peak) {
        var level = heatLevel(value, peak);
        if (!level) return 'background:rgba(var(--of-white-rgb),.05)';
        return 'background:rgba(var(' + (Number(value) >= 0 ? '--of-ok-rgb' : '--of-err-rgb') + '),' +
            (0.10 + level * 0.14).toFixed(2) + ')';
    }

    function cellTitle(cell) {
        if (!cell) return '';
        return cell.day + ' · ' + n2(cell.pnl) + ' ticks · ' + n0(cell.trades) + ' trade(s)';
    }

    /* The server's calendar block as the grid to render: the month at `index` (clamped; null or
       junk means the newest), seven-day week rows of cells or holes, plus the header numbers.
       null when the journal holds no closed trade at all — the caller says so in words. */
    function calendarModel(block, index) {
        var months = (block && block.months) || [];
        if (!months.length) return null;
        var i = index == null ? months.length - 1 : Math.round(Number(index));
        if (!isFinite(i)) i = months.length - 1;
        i = Math.min(months.length - 1, Math.max(0, i));
        var m = months[i] || {};
        var weeks = (m.weeks || []).map(function (week) {
            var out = [];
            for (var d = 0; d < 7; d += 1) {
                var cell = (week || [])[d];
                if (!cell) { out.push(null); continue; }
                out.push({
                    day: cell.day, dom: n0(cell.dom), pnl: Number(cell.pnl), trades: Number(cell.trades),
                    level: heatLevel(cell.pnl, m.peak), style: heatStyle(cell.pnl, m.peak),
                    title: cellTitle(cell)
                });
            }
            return out;
        });
        return {
            index: i, count: months.length, month: m.month, label: m.label || m.month || '—',
            weeks: weeks, peak: m.peak, pnl: m.pnl, trades: m.trades, days: m.days
        };
    }

    /* The compact strip: the figures the four tiles do not carry. Each value is 'n/a' where the
       payload had none, never a zero. */
    function stripItems(figures) {
        var s = figures || {};
        var ex = s.mae_mfe || {};
        return [
            { label: 'R', value: signed(s.expectancy_r, 2, 'R'),
              sub: s.r_count ? (n0(s.r_count) + ' trade(s) with an R') :
                   (s.r_stops ? (n0(s.r_stops) + ' row(s) record a stop, none yields an R')
                              : 'no trade records a stop') },
            { label: 'payoff', value: n2(s.payoff_ratio),
              sub: 'avg win ' + n2(s.avg_win) + ' / avg loss ' + n2(s.avg_loss) },
            { label: 'R total', value: signed(s.r_total, 2, 'R'),
              sub: (s.r_derived == null ? 'how the R values were read' :
                    n0(s.r_derived) + ' derived, ' + n0(s.r_recorded) + ' as opened') },
            { label: 'excursion', value: ex.count ? (n2(ex.avg_mfe) + ' MFE / ' + n2(ex.avg_mae) + ' MAE') : 'n/a',
              sub: ex.count ? (n0(ex.count) + ' row(s) record one') : 'no row records mae/mfe' },
            { label: 'streaks',
              value: (s.max_win_streak == null && s.max_loss_streak == null)
                  ? 'n/a' : ('W ' + n0(s.max_win_streak) + ' / L ' + n0(s.max_loss_streak)),
              sub: 'longest runs, in trade order' }
        ];
    }

    function stripHtml(figures) {
        var chips = stripItems(figures).map(function (item) {
            return '<span class="tag" title="' + esc(item.sub) + '">' + esc(item.label) + ' ' +
                esc(item.value) + '</span>';
        }).join(' ');
        var says = ((figures || {}).sentences || []).map(function (line) {
            return '<div class="dim">' + esc(line) + '</div>';
        }).join('');
        return chips + says;
    }

    function setupHtml(block) {
        var list = setupRows(block);
        if (!list.length) {
            return 'no setup tags on these trades yet — a row tags itself through a setup column ' +
                'or the signals it was taken on';
        }
        return '<table class="mini"><thead><tr><th>setup</th><th>trades</th><th>win rate</th>' +
            '<th>avg R</th><th>expectancy</th><th>profit factor</th></tr></thead><tbody>' +
            list.map(function (row) {
                return '<tr><td>' + esc(row.tag) + '</td><td>' + esc(row.trades) + '</td><td>' +
                    esc(row.win) + '</td><td>' + esc(row.avgR) + '</td><td>' + esc(row.expectancy) +
                    '</td><td>' + esc(row.profitFactor) + '</td></tr>';
            }).join('') + '</tbody></table>' +
            '<div class="dim">expectancy is ticks a trade; a trade carrying two tags counts in both; ' +
            'avg R covers only the rows that yield one</div>';
    }

    function calendarHtml(model) {
        if (!model) return 'no closed trades with a date yet';
        var head = '<div class="dim">' + esc(model.label) + ' · UTC · ' + esc(n2(model.pnl)) + ' ticks · ' +
            esc(n0(model.trades)) + ' trade(s) on ' + esc(n0(model.days)) + ' day(s)</div>';
        var body = model.weeks.map(function (week) {
            var cells = week.map(function (cell) {
                if (!cell) return '<td></td>';
                return '<td title="' + esc(cell.title) + '" style="' + esc(cell.style) +
                    ';text-align:center;padding:4px 6px;border-radius:4px">' +
                    '<div>' + esc(cell.dom) + '</div><div style="font-size:10px">' +
                    esc(signed(cell.pnl, 0)) + '</div></td>';
            }).join('');
            return '<tr>' + cells + '</tr>';
        }).join('');
        var weekday = '<tr>' + WEEKDAYS.map(function (name) {
            return '<th>' + esc(name) + '</th>';
        }).join('') + '</tr>';
        return head + '<table class="mini" style="margin-top:6px"><thead>' + weekday +
            '</thead><tbody>' + body + '</tbody></table>' +
            '<div class="dim">the selected month only — the panel loads the newest 500 rows</div>';
    }

    function renderCalendar() {
        var block = (stats || {}).calendar;
        var model = calendarModel(block, calIndex);
        if (model) calIndex = model.index;
        var label = $('jnCalMonth');
        if (label) label.textContent = model ? (model.label + ' (' + (model.index + 1) + '/' + model.count + ')') : '—';
        var box = $('jnCalendar');
        if (box) box.innerHTML = calendarHtml(model);
    }

    function renderDeep(figures) {
        stats = figures || {};
        var strip = $('jnStrip');
        if (strip) strip.innerHTML = stripHtml(stats);
        var setup = $('jnSetup');
        if (setup) setup.innerHTML = setupHtml(stats.by_setup);
        var sessions = $('jnSessions');
        if (sessions) {
            var groups = stats.by_session || [];
            sessions.innerHTML = groups.length
                ? groups.map(function (g) {
                    return '<div>' + esc(g.key) + ' · ' + esc(n0(g.trades)) + ' trade(s) · ' +
                        esc(pct(g.win_rate)) + ' win rate · ' + esc(signed(g.avg_r, 2, 'R')) + '</div>';
                }).join('') + '<div class="dim">read from each row\'s session, else its entry hour (UTC)</div>'
                : 'no closed trades to break down yet';
        }
        renderCalendar();
    }

    function render(payload) {
        var figures = (payload && payload.stats) || {};
        rows = (payload && payload.rows) || [];
        var grid = $('jnStats');
        if (grid) {
            grid.innerHTML =
                tile('Trades', String(figures.count != null ? figures.count : rows.length),
                     (figures.wins || 0) + ' win / ' + (figures.losses || 0) + ' loss') +
                tile('Win rate', pct(figures.win_rate), 'expectancy ' + n2(figures.expectancy) + ' ticks') +
                tile('Profit factor', n2(figures.profit_factor), 'gross ' + n2(figures.gross_win) + ' / ' + n2(figures.gross_loss)) +
                tile('Planned R:R', n2(figures.avg_rr),
                     'avg of each row\'s plan · max drawdown ' + n2(figures.max_drawdown));
        }
        renderDeep(figures);
        var count = $('jnCount');
        if (count) count.textContent = rows.length + ' row(s)';
        var table = $('jnTable');
        if (!table) return;
        if (!rows.length) {
            table.textContent = 'no trades yet — a simulated session can be saved here from the Replay view';
            return;
        }
        table.innerHTML = '<table class="mini"><thead><tr><th>exit (UTC)</th><th>instrument</th><th>dir</th>' +
            '<th>entry</th><th>exit</th><th>R</th><th>ticks</th><th>note</th></tr></thead><tbody>' +
            rows.map(function (r) {
                return '<tr data-id="' + esc(r.id) + '"' + (selected === r.id ? ' class="sel"' : '') + '>' +
                    '<td>' + esc(utc(r.exit_time_ms || r.entry_time_ms)) + '</td>' +
                    '<td>' + esc(r.instrument) + '</td><td>' + esc(r.direction) + '</td>' +
                    '<td>' + esc(r.entry_price) + '</td><td>' + esc(r.exit_price) + '</td>' +
                    '<td>' + esc(n2(r.rr_ratio)) + '</td><td>' + esc(n2(r.pnl_ticks)) + '</td>' +
                    '<td>' + esc(String(r.notes || '').slice(0, 40)) + '</td></tr>';
            }).join('') + '</tbody></table>';
        table.querySelectorAll('tr[data-id]').forEach(function (tr) {
            tr.onclick = function () {
                selected = Number(tr.dataset.id);
                var row = rows.filter(function (r) { return r.id === selected; })[0];
                var note = $('jnNote');
                if (note && row) note.value = row.notes || '';
                table.querySelectorAll('tr').forEach(function (x) { x.classList.remove('sel'); });
                tr.classList.add('sel');
            };
        });
        var daily = $('jnDaily');
        if (daily) {
            var series = (payload && payload.daily) || [];
            daily.innerHTML = series.length
                ? series.slice(-14).map(function (d) {
                    return '<div>' + esc(d.day) + ' · ' + esc(n2(d.pnl)) + ' ticks · ' + esc(d.trades) + ' trade(s)</div>';
                }).join('')
                : 'no closed trades yet';
        }
    }

    function load() {
        return window.api('/api/control/journal?limit=500').then(render).catch(function () { /* offline */ });
    }

    /* One month back or forward through the calendar the payload carried. Clamped, so the ends do
       nothing rather than wrapping into a month that is not in the loaded window. */
    function stepMonth(delta) {
        return function () {
            var months = ((stats || {}).calendar || {}).months || [];
            if (!months.length) return;
            var current = calIndex == null ? months.length - 1 : calIndex;
            calIndex = Math.min(months.length - 1, Math.max(0, current + delta));
            renderCalendar();
        };
    }

    function boot() {
        var b;
        if ((b = $('jnRefresh'))) b.onclick = function () { load(); };
        if ((b = $('jnCalPrev'))) b.onclick = stepMonth(-1);
        if ((b = $('jnCalNext'))) b.onclick = stepMonth(1);
        if ((b = $('jnStatement'))) b.onclick = function () {
            var out = $('jnActionResult');
            if (out) out.textContent = 'building the statement…';
            window.api('/api/control/journal/statement', { method: 'POST', body: {} }).then(function (res) {
                if (out) out.textContent = res && res.ok
                    ? ('statement written to ' + res.path + ' (' + res.trades + ' trades) — open it from File ▸ Open exports folder')
                    : ('could not write the statement: ' + ((res && res.error) || 'unknown'));
            }).catch(function (err) { if (out) out.textContent = 'statement failed: ' + err; });
        };
        if ((b = $('jnSaveNote'))) b.onclick = function () {
            var out = $('jnActionResult');
            if (!selected) { if (out) out.textContent = 'select a trade row first'; return; }
            var note = ($('jnNote') || {}).value || '';
            window.api('/api/control/journal/note', { method: 'POST', body: { id: selected, notes: note } })
                .then(function (res) {
                    if (out) out.textContent = res && res.ok ? 'note saved' : ('could not save: ' + ((res && res.error) || ''));
                    load();
                });
        };
        var wrap = window.showView;
        if (typeof wrap === 'function' && !wrap.__ofapWrapped_journal) {
            var wrapped = function (name) {
                var out = wrap.apply(this, arguments);
                if (name === 'journal') setTimeout(function () {
                    var section = document.querySelector('.view[data-view="journal"]');
                    if (section && section.classList.contains('active')) load();
                }, 400);
                return out;
            };
            wrapped.__ofapWrapped_journal = true;
            window.showView = wrapped;
        }
        setTimeout(function () {
            var section = document.querySelector('.view[data-view="journal"]');
            if (section && section.classList.contains('active')) load();
        }, 1600);
    }

    window.OFAPJOURNAL = {
        load: load, render: render, renderDeep: renderDeep,
        setupRows: setupRows, heatLevel: heatLevel, heatStyle: heatStyle, cellTitle: cellTitle,
        calendarModel: calendarModel, stripItems: stripItems, stripHtml: stripHtml,
        setupHtml: setupHtml, calendarHtml: calendarHtml, stepMonth: stepMonth
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
