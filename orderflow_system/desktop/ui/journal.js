/* journal.js — the Journal view (R10): rows, statistics, notes and the HTML statement.
 *
 * Everything comes from /api/control/journal (read-only reads of the app's own trade_journal),
 * /journal/note and /journal/statement. The statistics are the server's (desktop/journal.py, pure
 * and pinned); this module formats them and keeps the selected row.
 */
(function () {
    'use strict';

    var selected = null;
    var rows = [];

    function $(id) { return document.getElementById(id); }
    var esc = (t) => String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    function utc(ms) {
        if (!ms) return '—';
        try { return new Date(Number(ms)).toISOString().replace('T', ' ').slice(0, 16); } catch (e) { return '—'; }
    }

    function pct(x) { return x == null ? 'n/a' : (Math.round(Number(x) * 1000) / 10).toString() + '%'; }
    function n2(x) { return x == null ? 'n/a' : (Math.round(Number(x) * 100) / 100).toString(); }

    function tile(label, value, sub) {
        return '<div class="sy-tile"><div class="sy-line"><span class="sy-name">' + esc(label) + '</span>' +
            '<div class="spacer"></div><span class="tag dim">' + esc(value) + '</span></div>' +
            (sub ? '<div class="sy-detail">' + esc(sub) + '</div>' : '') + '</div>';
    }

    function render(payload) {
        var stats = (payload && payload.stats) || {};
        rows = (payload && payload.rows) || [];
        var grid = $('jnStats');
        if (grid) {
            grid.innerHTML =
                tile('Trades', String(stats.count != null ? stats.count : rows.length),
                     (stats.wins || 0) + ' win / ' + (stats.losses || 0) + ' loss') +
                tile('Win rate', pct(stats.win_rate), 'expectancy ' + n2(stats.expectancy) + ' ticks') +
                tile('Profit factor', n2(stats.profit_factor), 'gross ' + n2(stats.gross_win) + ' / ' + n2(stats.gross_loss)) +
                tile('Average R', n2(stats.avg_rr), 'max drawdown ' + n2(stats.max_drawdown));
        }
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

    function boot() {
        var b;
        if ((b = $('jnRefresh'))) b.onclick = function () { load(); };
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

    window.OFAPJOURNAL = { load: load, render: render };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
