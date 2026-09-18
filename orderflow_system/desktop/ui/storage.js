/* storage.js — the Storage panel (R6): usage you can see, retention you can set, backups you can
 * trust.
 *
 * The numbers all come from `GET /api/control/storage` (server-side 30 s cache). Every control
 * saves through `POST /api/control/storage/settings` and shows the clamped values the server
 * returns, because those are the ones the jobs will use; the one-shot actions go through
 * `/storage/{prune,vacuum,cleanup,backup,report}`. The SMTP block is the alerts' own email config
 * (`notify.email`), saved through the ordinary config route — one mailbox, one set of credentials,
 * used by both the alert channel and this report.
 *
 * Polling follows the house rule: only while the Settings view is actually on screen, never while
 * hidden, paused or under the user's hands.
 */
(function () {
    'use strict';

    var POLL_MS = 20000;
    var timer = null;

    function $(id) { return document.getElementById(id); }

    function mb(n) {
        n = Number(n) || 0;
        if (n >= 1e9) return (n / 1e9).toFixed(2) + ' GB';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + ' MB';
        if (n >= 1e3) return (n / 1e3).toFixed(0) + ' KB';
        return n + ' B';
    }

    function shortTime(iso) {
        // "2026-09-18T05:31:02Z" -> "2026-09-18 05:31 UTC" (what the manifest actually stored)
        var m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(String(iso || ''));
        return m ? m[1] + ' ' + m[2] + ' UTC' : String(iso || '—');
    }

    function fill(id, value) {
        var el = $(id);
        if (el && document.activeElement !== el) el.value = value;
    }

    function check(id, value) {
        var el = $(id);
        if (el && document.activeElement !== el) el.checked = !!value;
    }

    function say(id, text, kind) {
        var el = $(id);
        if (!el) return;
        el.textContent = String(text || '');
        el.className = 'dim' + (kind ? ' ' + kind : '');
    }

    /* the Systems board's own tile markup — one look for "machine at a glance" cards */
    function tile(label, value, hint) {
        return '<div class="sy-tile"><div class="sy-line"><span class="sy-name">' + label + '</span>' +
               '<div class="spacer"></div><span class="tag dim">' + value + '</span></div>' +
               (hint ? '<div class="sy-detail">' + hint + '</div>' : '') + '</div>';
    }

    function render(d) {
        d = d || {};
        var usage = d.usage || {};
        var growth = d.growth || {};
        var st = d.storage_settings || {};
        var rt = d.retention || {};
        var backups = Array.isArray(d.backups) ? d.backups : [];

        var pill = $('stPillText');
        if (pill) {
            pill.textContent = st.auto_backup
                ? ('automatic — every ' + st.backup_interval_hours + ' h')
                : (backups.length ? 'manual — ' + backups.length + ' set(s) in the target' : 'manual — no backups yet');
        }

        var grid = $('stUsage');
        if (grid) {
            var dbBytes = (Number(usage.db_bytes) || 0) + (Number(usage.wal_bytes) || 0);
            grid.innerHTML =
                tile('Database', mb(dbBytes), mb(usage.wal_bytes) + ' in the WAL') +
                tile('Logs', mb(usage.log_bytes), 'rotating ring') +
                tile('Exports', mb(usage.exports_bytes), 'your saved files') +
                tile('Backups', mb(usage.backups_bytes), backups.length + ' set(s)') +
                tile('Total on disk', mb(usage.total_bytes), shortTime(d.generated || ''));
        }

        var grow = $('stGrowth');
        if (grow) {
            if (growth.ok) {
                grow.textContent = 'growing ' + mb(growth.bytes_per_hour) + '/h · ' + mb(growth.bytes_per_day) +
                    '/day (' + growth.samples + ' samples over ' + growth.span_hours + ' h) — ' +
                    (growth.note || '');
            } else {
                grow.textContent = growth.note || 'no growth history yet — samples are recorded while the engine runs';
            }
        }

        fill('stRetention', rt.days != null ? rt.days : 7);
        fill('stPruneInterval', rt.prune_interval_hours != null ? rt.prune_interval_hours : 6);
        fill('stSessionHour', rt.session_start_hour != null ? rt.session_start_hour : 0);
        if (d.last_prune && d.last_prune.at_ms) {
            say('stLastPrune', 'last prune: ' + shortTime(new Date(d.last_prune.at_ms).toISOString()) +
                ' — ' + (d.last_prune.deleted || 0) + ' tick row(s) removed, ' +
                mb(Math.max(0, (d.last_prune.bytes_before || 0) - (d.last_prune.bytes_after || 0))) + ' reclaimed');
        } else {
            say('stLastPrune', 'last prune: never — the first pass runs when the engine starts');
        }

        check('stAutoBackup', st.auto_backup);
        fill('stBackupInterval', st.backup_interval_hours != null ? st.backup_interval_hours : 24);
        fill('stBackupKeep', st.backup_keep != null ? st.backup_keep : 5);
        var fmt = $('stBackupFormat');
        if (fmt && document.activeElement !== fmt) fmt.value = st.backup_format || 'sqlite+csv';
        fill('stBackupTarget', st.backup_target || '');
        fill('stMaxDb', st.max_db_mb != null ? st.max_db_mb : 0);
        check('stEmailReport', st.email_report);
        check('stEmailThreshold', st.email_threshold);

        var list = $('stBackupList');
        if (list) {
            if (!backups.length) {
                list.textContent = 'no backup sets in ' + (usage.backups_dir || 'the target') + ' yet';
            } else {
                list.innerHTML = backups.slice(0, 6).map(function (b) {
                    var db = b.database || {};
                    var bits = [shortTime(b.created_at), mb(b.bytes)];
                    if (db.sha256) bits.push('sha256 ' + String(db.sha256).slice(0, 12) + '…');
                    if (db.integrity) bits.push(db.integrity === 'ok' ? 'verified' : ('integrity: ' + db.integrity));
                    return '<div>' + b.name + ' — ' + bits.join(' · ') + '</div>';
                }).join('');
            }
        }

        var emailState = $('stEmailState');
        if (emailState && d.smtp_to) {
            emailState.textContent = 'sends to ' + d.smtp_to + ' (SMTP configured)';
        } else if (emailState) {
            emailState.textContent = 'no mailbox configured yet — fill the SMTP fields below';
        }
    }

    function load() {
        return window.api('/api/control/storage?refresh=1').then(function (d) {
            render(d);
            return d;
        }).catch(function () { /* offline: leave the last render up */ });
    }

    function save(patch) {
        return window.api('/api/control/storage/settings', { method: 'POST', body: patch })
            .then(function (res) {
                if (res && res.ok) load();
                return res;
            });
    }

    function action(path, body, target, label) {
        say(target, label + '…');
        return window.api(path, { method: 'POST', body: body || {} })
            .then(function (res) {
                if (res && res.ok === false) {
                    say(target, label + ' failed: ' + (res.error || res.detail || 'refused'), 'err');
                    return res;
                }
                load();
                return res;
            })
            .catch(function (err) {
                say(target, label + ' failed: ' + err, 'err');
            });
    }

    function wire() {
        var b;
        if ((b = $('btnStPrune'))) b.onclick = function () {
            action('/api/control/storage/prune', {}, 'stActionResult', 'pruning').then(function (res) {
                if (!res || res.ok === false) return;
                var s = res.summary || {};
                say('stActionResult', s.skipped ? String(s.skipped)
                    : ('pruned ' + (s.deleted || 0) + ' tick row(s), ' + mb(Math.max(0, (s.bytes_before || 0) - (s.bytes_after || 0))) + ' reclaimed'));
            });
        };
        if ((b = $('btnStVacuum'))) b.onclick = function () {
            action('/api/control/storage/vacuum', {}, 'stActionResult', 'reclaiming space').then(function (res) {
                if (!res || res.ok === false) return;
                say('stActionResult', 'reclaimed ' + mb(res.reclaimed_bytes) + ' (' + res.mode +
                    (res.engine_running ? ' — the engine is running, so the pass is incremental; a full VACUUM runs when it is stopped' : '') + ')');
            });
        };
        if ((b = $('btnStCleanup'))) b.onclick = function () {
            action('/api/control/storage/cleanup', { keep_days: 30 }, 'stActionResult', 'sweeping caches').then(function (res) {
                if (!res || res.ok === false) return;
                say('stActionResult', 'removed ' + (res.cache_files_removed || 0) + ' cache file(s) and ' +
                    (res.exports_removed || []).length + ' old export(s)');
            });
        };
        if ((b = $('btnDataImport'))) b.onclick = function () {
            var picker = $('dataImportFile');
            if (picker) picker.click();
        };
        if ((b = $('dataImportFile'))) b.onchange = function () {
            var file = (b.files || [])[0];
            if (!file) return;
            say('dataActionResult', 'reading ' + file.name + '…');
            var reader = new FileReader();
            reader.onload = function () {
                var symbol = (document.getElementById('symbolSelect') || {}).value || '';
                window.api('/api/control/data/import', { method: 'POST', body: {
                    name: file.name, text: String(reader.result || ''), kind: 'ticks'
                } }).then(function (res) {
                    if (!res || res.ok === false) {
                        say('dataActionResult', 'import refused: ' + ((res && (res.error || res.detail)) || 'unknown') +
                            ('errors' in (res || {}) && res.errors.length ? ' — ' + res.errors.slice(0, 3).join('; ') : ''), 'err');
                        return;
                    }
                    say('dataActionResult', 'imported ' + res.inserted + ' row(s) for ' + res.instrument +
                        (res.skipped_existing ? ', ' + res.skipped_existing + ' already stored' : '') +
                        (res.bad_rows ? ', ' + res.bad_rows + ' row(s) unreadable' : ''));
                }).catch(function (err) { say('dataActionResult', 'import failed: ' + err, 'err'); });
            };
            reader.onerror = function () { say('dataActionResult', 'could not read that file', 'err'); };
            reader.readAsText(file);
            b.value = '';                    // the same file twice in a row must still fire
        };
        if ((b = $('btnDataExportTicks'))) b.onclick = function () { exportNow('ticks'); };
        if ((b = $('btnDataExportCandles'))) b.onclick = function () { exportNow('candles'); };
        if ((b = $('btnStBackup'))) b.onclick = function () {
            var target = ($('stBackupTarget') || {}).value || '';
            action('/api/control/storage/backup', { target: target }, 'stBackupResult', 'backing up').then(function (res) {
                if (!res || res.ok === false) return;
                var m = res.backup || {};
                say('stBackupResult', 'wrote ' + m.folder + ' (' + mb(m.bytes) + ', ' + (m.duration_s || 0) + ' s' +
                    (m.removed && m.removed.length ? ', rotated out ' + m.removed.length + ' old set(s)' : '') + ')');
            });
        };
        if ((b = $('btnStOpenBackups'))) b.onclick = function () {
            window.api('/api/control/folder/open', { method: 'POST', body: { folder: 'backups' } })
                .catch(function (err) { say('stBackupResult', 'could not open the folder: ' + err, 'err'); });
        };
        if ((b = $('btnStReport'))) b.onclick = function () {
            action('/api/control/storage/report', {}, 'stEmailState', 'sending the report').then(function (res) {
                if (!res || res.ok === false) {
                    if (res && res.error) say('stEmailState', 'report not sent: ' + res.error, 'err');
                    return;
                }
                say('stEmailState', 'report sent — "' + (res.subject || '') + '"');
            });
        };
        if ((b = $('btnStSmtpSave'))) b.onclick = function () {
            var email = {
                enabled: true,
                host: ($('stSmtpHost') || {}).value || '',
                port: Number(($('stSmtpPort') || {}).value || 587),
                username: ($('stSmtpUser') || {}).value || '',
                password: ($('stSmtpPass') || {}).value || '',
                from: ($('stSmtpFrom') || {}).value || '',
                to: ($('stSmtpTo') || {}).value || '',
                use_tls: true,
            };
            say('stEmailState', 'saving…');
            window.api('/api/control/config', { method: 'POST', body: { notify: { email: email } } })
                .then(function (res) {
                    if (res && res.ok === false) { say('stEmailState', 'could not save: ' + (res.error || ''), 'err'); return; }
                    say('stEmailState', 'mailbox saved — "Send report now" will use it');
                    load();
                })
                .catch(function (err) { say('stEmailState', 'could not save: ' + err, 'err'); });
        };

        // the numbers save as they change: this card is a control panel, not a form
        ['stRetention', 'stPruneInterval', 'stSessionHour', 'stBackupInterval', 'stBackupKeep'].forEach(function (id) {
            var el = $(id);
            if (!el) return;
            el.onchange = function () {
                var patch = {};
                patch.retention_days = Number(($('stRetention') || {}).value || 0);
                patch.prune_interval_hours = Number(($('stPruneInterval') || {}).value || 6);
                patch.session_start_hour = Number(($('stSessionHour') || {}).value || 0);
                patch.backup_interval_hours = Number(($('stBackupInterval') || {}).value || 24);
                patch.backup_keep = Number(($('stBackupKeep') || {}).value || 5);
                save(patch).then(function (res) {
                    if (res && res.ok) say('stActionResult', 'saved — retention ' + res.retention.days + ' d, prune every ' +
                        res.retention.prune_interval_hours + ' h, backups every ' + res.storage.backup_interval_hours + ' h, keeping ' + res.storage.backup_keep);
                });
            };
        });
        ['stAutoBackup', 'stEmailReport', 'stEmailThreshold'].forEach(function (id) {
            var el = $(id);
            if (!el) return;
            el.onchange = function () {
                var patch = {};
                patch.auto_backup = !!($('stAutoBackup') || {}).checked;
                patch.email_report = !!($('stEmailReport') || {}).checked;
                patch.email_threshold = !!($('stEmailThreshold') || {}).checked;
                save(patch);
            };
        });
        ['stBackupFormat', 'stBackupTarget', 'stMaxDb'].forEach(function (id) {
            var el = $(id);
            if (!el) return;
            el.onchange = function () {
                save({
                    backup_format: ($('stBackupFormat') || {}).value || 'sqlite+csv',
                    backup_target: ($('stBackupTarget') || {}).value || '',
                    max_db_mb: Number(($('stMaxDb') || {}).value || 0),
                });
            };
        });
        /* T12/B10: the configuration artifacts — export writes through /export/save (a real file
           in the exports folder); import reads the file here and lets the server refuse a bad
           one readably, touching nothing. */
        if ((b = $('btnCfgExportWorkspace'))) b.onclick = function () { exportArtifact('workspace'); };
        if ((b = $('btnCfgExportStudies'))) b.onclick = function () { exportArtifact('studies'); };
        if ((b = $('btnCfgImport'))) b.onclick = function () {
            var picker = $('cfgImportFile');
            if (picker) picker.click();
        };
        if ((b = $('cfgImportFile'))) b.onchange = function () {
            var file = (b.files || [])[0];
            if (!file) return;
            say('cfgArtifactResult', 'reading ' + file.name + '…');
            var reader = new FileReader();
            reader.onload = function () {
                window.api('/api/control/config/import', { method: 'POST', body: { artifact: String(reader.result || '') } })
                    .then(function (res) {
                        if (!res || res.ok === false) {
                            say('cfgArtifactResult', 'import refused: ' + ((res && res.error) || 'unknown'), 'err');
                            return;
                        }
                        say('cfgArtifactResult', 'imported the ' + res.kind + ' artifact — ' + res.applied.join(', ') +
                            ' applied (reopen the program for every surface to re-read them)');
                    })
                    .catch(function (err) { say('cfgArtifactResult', 'import failed: ' + err, 'err'); });
            };
            reader.onerror = function () { say('cfgArtifactResult', 'could not read that file', 'err'); };
            reader.readAsText(file);
            b.value = '';                    // the same file twice in a row must still fire
        };
    }

    function exportArtifact(kind) {
        say('cfgArtifactResult', 'building the ' + kind + ' artifact…');
        window.api('/api/control/config/artifact?kind=' + encodeURIComponent(kind), {})
            .then(function (res) {
                if (!res || res.ok === false || !res.artifact) {
                    say('cfgArtifactResult', 'export failed: ' + ((res && res.error) || 'unknown'), 'err');
                    return;
                }
                var stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
                var name = 'ofap-' + kind + '-' + stamp + '.json';
                return window.api('/api/control/export/save', { method: 'POST', body: { name: name, text: JSON.stringify(res.artifact, null, 2) } })
                    .then(function (saved) {
                        if (saved && saved.ok) say('cfgArtifactResult', 'wrote ' + saved.path + ' (' + mb(saved.bytes) + ')');
                        else say('cfgArtifactResult', 'could not write the file: ' + ((saved && (saved.error || saved.detail)) || 'unknown'), 'err');
                    });
            })
            .catch(function (err) { say('cfgArtifactResult', 'export failed: ' + err, 'err'); });
    }

    function exportNow(kind) {
        var symbol = (document.getElementById('symbolSelect') || {}).value || '';
        say('dataActionResult', 'exporting ' + kind + '…');
        window.api('/api/control/data/export', { method: 'POST', body: { kind: kind, symbol: symbol } })
            .then(function (res) {
                if (!res || res.ok === false) {
                    say('dataActionResult', 'export failed: ' + ((res && res.error) || 'unknown'), 'err');
                    return;
                }
                say('dataActionResult', 'wrote ' + res.rows + ' row(s) to ' + res.path + ' (' + mb(res.bytes) + ')');
            })
            .catch(function (err) { say('dataActionResult', 'export failed: ' + err, 'err'); });
    }

    function onScreen() {
        if (document.hidden || window.OFAP_PAUSED) return false;
        var section = document.querySelector('.view[data-view="settings"]');
        if (!section) return false;
        return section.classList.contains('active') || section.style.display === 'flex';
    }

    function startPolling() {
        if (timer) return;
        timer = setInterval(function () {
            if (onScreen()) load();
        }, POLL_MS);
    }

    function boot() {
        wire();
        startPolling();
        // load when Settings opens, and once now — the card must not read "—" until a click
        var wrap = window.showView;
        if (typeof wrap === 'function') {
            window.showView = function (name) {
                var out = wrap.apply(this, arguments);
                if (name === 'settings') setTimeout(load, 400);
                return out;
            };
        }
        setTimeout(function () { if (onScreen()) load(); }, 1500);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
