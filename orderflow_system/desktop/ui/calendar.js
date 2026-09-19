/* calendar.js — the economic calendar (R11): this week's releases, and alerts before the big ones.
 *
 * One source, named on screen: Forex Factory's public weekly JSON, which needs no key or account
 * and is cached for four hours. When it cannot be reached the panel says so — it never invents a
 * date. The alert switch writes the `calendar` block of the config, where the engine's own tick
 * reads it; alerts then travel through the channels already configured in Settings ▸ alerts.
 */
(function () {
    'use strict';

    function $(id) { return document.getElementById(id); }
    /* SEC-18: quotes too — this helper lands in attribute contexts (title="…") where an
       unescaped quote is an injection. Same set as fundamentals.js/heatmap-pro.js. */
    var esc = (t) => String(t == null ? '' : t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function when(ms) {
        if (!ms) return '—';
        var d = new Date(Number(ms));
        var today = new Date();
        var sameDay = d.toISOString().slice(0, 10) === today.toISOString().slice(0, 10);
        return (sameDay ? '' : d.toISOString().slice(5, 10) + ' ') + d.toISOString().slice(11, 16) + 'Z';
    }

    function tag(impact) {
        var kind = impact === 'high' ? 'no' : (impact === 'medium' ? 'dim' : 'ok');
        return '<span class="tag ' + kind + '">' + esc(impact) + '</span>';
    }

    function render(payload) {
        var banner = $('calBanner');
        var table = $('calTable');
        var source = $('calSource');
        payload = payload || {};
        if (source) {
            source.textContent = payload.ok
                ? ('source: ' + (payload.source || 'the weekly feed') + (payload.stale ? ' · STALE — the feed was unreachable, showing the last good copy' : ''))
                : ('the calendar feed is unreachable: ' + (payload.error || 'unknown') + ' — nothing is shown rather than guessed');
        }
        if (banner) {
            banner.innerHTML = payload.ok && payload.stale
                ? '<div class="banner warn" style="display:block">The calendar feed could not be reached; these are the last fetched events.</div>'
                : (!payload.ok
                    ? '<div class="banner" style="display:block">' + esc(payload.error || 'the calendar feed is unavailable') + '</div>'
                    : '');
        }
        if (!table) return;
        var events = payload.events || [];
        if (!events.length) {
            table.innerHTML = payload.ok
                ? 'nothing at or above the chosen impact in the next ' + (payload.window_hours || 48) + ' h'
                : ('the feed is unavailable — '
                    + (window.OFAPHELP ? OFAPHELP.topicLink('view.calendar', 'what this panel reads') : 'help'));
            return;
        }
        table.innerHTML = '<table class="mini"><thead><tr><th>when (UTC)</th><th>cur</th><th>impact</th>' +
            '<th>event</th><th>forecast</th><th>previous</th><th>actual</th></tr></thead><tbody>' +
            events.map(function (e) {
                return '<tr><td>' + esc(when(e.at_ms)) + '</td><td>' + esc(e.currency) + '</td>' +
                    '<td>' + tag(e.impact) + '</td><td>' + esc(e.title) + '</td>' +
                    '<td>' + esc(e.forecast || '—') + '</td><td>' + esc(e.previous || '—') + '</td>' +
                    '<td>' + esc(e.actual || '—') + '</td></tr>';
            }).join('') + '</tbody></table>';
    }

    function load() {
        var hours = (($('calHours') || {}).value) || 48;
        var impact = (($('calImpact') || {}).value) || 'high';
        var currencies = (($('calCurrencies') || {}).value) || '';
        return window.api('/api/control/calendar?hours=' + encodeURIComponent(hours) +
                          '&impact=' + encodeURIComponent(impact) +
                          '&currencies=' + encodeURIComponent(currencies))
            .then(render).catch(function () { /* offline */ });
    }

    function saveAlerts() {
        var block = {
            alerts: !!($('calAlerts') || {}).checked,
            lead_minutes: Number((($('calLead') || {}).value) || 15),
            currencies: (($('calCurrencies') || {}).value) || '',
        };
        window.api('/api/control/config', { method: 'POST', body: { calendar: block } }).then(function () {
            load();
        });
    }

    function boot() {
        var b;
        if ((b = $('calRefresh'))) b.onclick = function () { load(); };
        ['calHours', 'calImpact', 'calCurrencies'].forEach(function (id) {
            var el = $(id);
            if (el) el.onchange = function () { load(); saveAlerts(); };
        });
        ['calAlerts', 'calLead'].forEach(function (id) {
            var el = $(id);
            if (el) el.onchange = saveAlerts;
        });
        window.api('/api/control/config').then(function (cfg) {
            var block = (cfg && cfg.calendar) || {};
            if ($('calAlerts')) $('calAlerts').checked = !!block.alerts;
            if ($('calLead')) $('calLead').value = block.lead_minutes != null ? block.lead_minutes : 15;
            if ($('calCurrencies')) $('calCurrencies').value = block.currencies || '';
        }).catch(function () { /* defaults are fine */ });
        var wrap = window.showView;
        if (typeof wrap === 'function' && !wrap.__ofapWrapped_calendar) {
            var wrapped = function (name) {
                var out = wrap.apply(this, arguments);
                if (name === 'calendar') setTimeout(function () {
                    var section = document.querySelector('.view[data-view="calendar"]');
                    if (section && section.classList.contains('active')) load();   // C-09: left again = no fetch
                }, 300);
                return out;
            };
            wrapped.__ofapWrapped_calendar = true;
            window.showView = wrapped;
        }
        setTimeout(function () {
            var section = document.querySelector('.view[data-view="calendar"]');
            if (section && section.classList.contains('active')) load();
        }, 1700);
    }

    window.OFAPCALENDAR = { load: load, render: render };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
