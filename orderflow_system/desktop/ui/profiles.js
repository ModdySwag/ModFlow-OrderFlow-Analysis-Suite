/* Profiles — switchable playbooks.
 *
 * One surface for the whole profile lifecycle: save the current setup as a named profile, switch
 * with a preview of exactly what changes (and what waits for the next engine start), re-capture a
 * profile from what you are running now ("update"), rename / duplicate / delete (recoverable — the
 * server keeps a version ring), export / import as a file, and the optional auto-switch rules
 * (clock windows + feed bindings). Everything talks to /api/control/profiles; the module holds no
 * state the server does not — the response always carries the state the store accepted.
 *
 * Apply ends with a reload on purpose: a switch can change the layout, the theme and the instrument
 * set, i.e. everything the shell booted with. The server keeps the truth; the reload just re-reads it.
 */
(function () {
    'use strict';

    function $(id) { return document.getElementById(id); }
    /* Rendered names/tags/descriptions are user text — escape before any innerHTML (the same set
       calendar.js/fundamentals.js use; an unescaped quote here is an injection). */
    var esc = function (t) {
        return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    };
    var LABELS = {
        data_source: 'feed', instruments: 'instruments', atlas: 'analysis', ofx: 'engine',
        studies: 'studies', expression: 'palettes', ui: 'interface & theme', layouts: 'layouts',
        workspaces: 'workspaces', watchlist: 'watchlist', risk: 'risk', audio: 'audio',
        calendar: 'calendar',
    };
    /* What each block actually covers — the chips and the save form say it in words instead of
       leaving the reader to guess what "analysis" or "engine" means. */
    var BLOCK_NOTES = {
        data_source: 'which feed the engine streams from',
        instruments: 'which symbols are enabled and streaming',
        atlas: 'the analysis panels\u2019 parameters — heatmap, tape, CVD, market profile',
        ofx: 'the order-flow engine\u2019s dials — R, stack, sweeps, heat, palettes',
        studies: 'the indicator modules in play',
        expression: 'how bars are expressed and coloured',
        ui: 'theme, density, scale and each view\u2019s remembered settings',
        layouts: 'classic or terminal layout, its tabs and widgets',
        workspaces: 'your named workspaces',
        watchlist: 'the watchlist',
        risk: 'signal risk gates (cooldown, minimum score)',
        audio: 'trade audio',
        calendar: 'the economic calendar panel',
    };
    var FEEDS = ['bybit', 'mt5', 'binance', 'hyperliquid', 'okx', 'alpaca', 'ninjatrader'];
    var DAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

    var state = null;              // last /profiles payload
    var nameMode = 'create';       // create | rename | duplicate
    var nameTarget = '';           // profile id for rename/duplicate
    var pendingApply = '';         // id the preview card is showing

    function label(name) { return LABELS[name] || name; }

    function banner(text, kind) { if (typeof toast === 'function') toast($('pfBanner'), text, kind || 'ok'); }

    function cfgNow() {
        try { return (typeof S !== 'undefined' && S && S.config) ? S.config : null; }
        catch (e) { return null; }
    }

    function when(ms) {
        if (!ms) return 'never';
        var d = new Date(ms), now = Date.now(), mins = Math.round((now - ms) / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return mins + ' min ago';
        if (mins < 60 * 24) return Math.round(mins / 60) + ' h ago';
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString().slice(0, 5);
    }

    function spent(ms) {
        ms = Math.max(0, Number(ms) || 0);
        if (ms < 60000) return 'less than a minute';
        var mins = Math.round(ms / 60000);
        if (mins < 90) return mins + ' min';
        return (mins / 60).toFixed(1) + ' h';
    }

    function chipList(blocks) {
        return (blocks || []).map(function (b) {
            return '<span class="tag" title="This playbook carries ' + esc(label(b)) +
                (BLOCK_NOTES[b] ? ' \u2014 ' + esc(BLOCK_NOTES[b]) : '') + '">' + esc(label(b)) + '</span>';
        }).join(' ');
    }

    function blockNames(blocks) {
        return (blocks || []).map(label).join(', ');
    }

    function card(row) {
        var chips = [];
        if (row.id === state.active) chips.push('<span class="tag" style="border-color:var(--accent,#6cf);color:var(--accent,#6cf)" title="The playbook whose setup the app is running. Editing settings changes the setup you are running, not this saved copy \u2014 Update from current re-captures it.">active</span>');
        if (row.id === state.default) chips.push('<span class="tag" title="The playbook applied at launch when \u201capply at launch\u201d is ticked">startup</span>');
        if (row.dirty) {
            var moved = blockNames(row.dirty_blocks || []);
            chips.push('<span class="tag warn" title="These parts changed since this playbook was saved: ' + esc(moved) +
                '. \u201cUpdate from current\u201d keeps the new setup; switching to it goes back to the saved one.">' +
                'changed: ' + esc(moved || 'setup') + '</span>');
        }
        (row.tags || []).forEach(function (t) { chips.push('<span class="tag">' + esc(t) + '</span>'); });
        var stats = row.stats || {};
        var meta = 'applied ' + (stats.applied || 0) + '× · last ' + esc(when(stats.last_applied)) +
            ' · time in play ' + esc(spent(stats.active_ms)) + ' · trades ' + (row.trades || 0) +
            ' · updated ' + esc(when(row.updated));
        return '' +
            '<div class="card" style="margin:6px 0" data-id="' + esc(row.id) + '">' +
            '<div class="card-head"><span class="card-title">' + esc(row.name) + '</span>' +
            '<div class="spacer"></div>' + chips.join(' ') + '</div>' +
            '<div class="card-body">' +
            (row.description ? '<div class="dim">' + esc(row.description) + '</div>' : '') +
            '<div class="dim" style="font-size:11px">' + meta + '</div>' +
            '<div style="margin:4px 0">' + (chipList(row.blocks) || '<span class="dim">empty</span>') + '</div>' +
            '<div class="row">' +
            '<button class="btn small" data-act="preview" data-id="' + esc(row.id) + '" title="See exactly which parts change before anything is applied">Switch…</button>' +
            '<button class="btn small" data-act="update" data-id="' + esc(row.id) + '" title="Re-capture this playbook from the setup you are running now — the previous setup is kept under Versions">Update from current</button>' +
            '<button class="btn small" data-act="rename" data-id="' + esc(row.id) + '" title="Give this playbook a different name — the setup itself is untouched">Rename</button>' +
            '<button class="btn small" data-act="duplicate" data-id="' + esc(row.id) + '" title="Make a copy under a new name — handy for variations of a setup">Duplicate</button>' +
            '<button class="btn small" data-act="export" data-id="' + esc(row.id) + '" title="Write this playbook to a file you can share — no credentials or machine details travel with it">Export</button>' +
            '<button class="btn small" data-act="default" data-id="' + esc(row.id) + '" title="Use this playbook at launch (tick \u201capply at launch\u201d above to switch it on)">Make startup</button>' +
            (versions(row) ? '<button class="btn small" data-act="versions" data-id="' + esc(row.id) + '" title="Previous setups this playbook has had — put one back">Versions (' + versions(row).length + ')</button>' : '') +
            '<button class="btn small" data-act="delete" data-id="' + esc(row.id) + '" title="Delete this playbook — a previous setup stays under Versions until the next write">Delete</button>' +
            pendingNote(row) +
            '</div>' + versionsHtml(row) + '</div></div>';
    }

    /* The engine takes its feed, instruments and parameters at start — a playbook that carries any
       of those is only half live until it restarts. One quiet line on the card, with the action
       beside it; the status bar carries the same fact for switches made from the menu or palette. */
    function pendingNote(row) {
        var pend = state && state.pending_restart;
        if (!pend || row.id !== state.active) return '';
        var mine = (pend.blocks || []).filter(function (b) { return (row.blocks || []).indexOf(b) >= 0; });
        if (!mine.length) return '';
        var names = esc(mine.map(label).join(', '));
        return '<div class="hint" style="margin-top:4px" ' +
            'title="The engine reads these when it starts, so this playbook\'s ' + names +
            ' are still waiting for the next engine start. Everything else it carries is live now.">' +
            'waiting for an engine restart: ' + names +
            ' <button class="btn small" data-act="restart-engine" data-id="' + esc(row.id) + '" ' +
            'title="Stop and start the engine so it picks these up (the feed reconnects). Everything this playbook carries lands with it.">Restart engine</button></div>';
    }

    function versions(row) { return (row && row.versions) || []; }

    function versionsHtml(row) {
        var vs = versions(row);
        if (!vs.length) return '';
        return '<div class="pf-vers" hidden style="font-size:11px" title="Each entry is the setup this playbook had at that moment">' +
            vs.map(function (v) {
                return '<div>' + esc(when(v.at)) + ' \u00b7 ' +
                    esc(v.blocks && v.blocks.length ? v.blocks.map(label).join(', ') : 'empty') +
                    ' <button class="btn small" data-act="restore" data-id="' + esc(row.id) + '" data-at="' + v.at +
                    '" title="Put this playbook back to the setup it had then — what is there now is banked in turn, so this is reversible">Restore</button></div>';
            }).join('') + '</div>';
    }

    function render() {
        if (!state) return;
        $('pfCount').textContent = state.count + (state.count === 1 ? ' profile' : ' profiles');
        $('pfList').innerHTML = state.count
            ? state.items.map(card).join('')
            : '<div class="hint" title="A playbook is a saved copy of how you read a market. The setup you are running stays live and keeps changing; a playbook only changes when you update or restore it. It never carries your keys, account details or machine settings.">no profiles yet — set the app up the way you like it, then press <b>Save current as…</b> above. It can carry the feed, instruments, analysis parameters, layout, theme, watchlist, risk, audio and calendar parts; never credentials or machine paths.</div>';

        var badge = $('navProfileDirty');
        if (badge) badge.hidden = !(state.items || []).some(function (r) { return r.dirty; });

        var def = $('pfDefault'), keep = def.value || state.default;
        def.innerHTML = '<option value="">none</option>' + state.items.map(function (r) {
            return '<option value="' + esc(r.id) + '">' + esc(r.name) + '</option>';
        }).join('');
        def.value = state.default || '';
        $('pfAutoApply').checked = !!state.auto_apply;

        var ruleSel = $('pfRuleProfile'), feedSel = $('pfRuleFeedProfile'), keepRule = ruleSel.value;
        var opts = state.items.map(function (r) { return '<option value="' + esc(r.id) + '">' + esc(r.name) + '</option>'; }).join('');
        ruleSel.innerHTML = opts;
        feedSel.innerHTML = opts;
        if (keepRule) ruleSel.value = keepRule;
        $('pfRuleFeed').innerHTML = FEEDS.map(function (f) { return '<option value="' + f + '">' + f + '</option>'; }).join('');
        $('pfRulesOn').checked = !!(state.rules && state.rules.enabled);

        var lines = [];
        var src = (state.rules && state.rules.sources) || {};
        Object.keys(src).forEach(function (feed) {
            var row = state.items.filter(function (r) { return r.id === src[feed]; })[0];
            lines.push('<div>feed <b>' + esc(feed) + '</b> \u2192 <b>' + esc(row ? row.name : src[feed]) + '</b> ' +
                '<button class="btn small" data-act="unbind-feed" data-feed="' + esc(feed) + '" title="Stop switching playbooks when this feed is live">remove</button></div>');
        });
        ((state.rules && state.rules.windows) || []).forEach(function (w, i) {
            var row = state.items.filter(function (r) { return r.id === w.profile; })[0];
            var days = (w.days || []).map(function (d) { return DAYS[d]; }).join(' ');
            lines.push('<div><b>' + esc(w.from) + '\u2013' + esc(w.to) + '</b>' + (days ? ' ' + esc(days) : ' every day') +
                ' \u2192 <b>' + esc(row ? row.name : w.profile) + '</b> ' +
                '<button class="btn small" data-act="drop-window" data-at="' + i + '" title="Remove this clock window">remove</button></div>');
        });
        $('pfRulesList').innerHTML = lines.join('') ||
            '<span title="Rules are optional — a playbook switches when you switch it, or automatically by the rules you add here">no rules yet</span>';
    }

    function reload(payload) {
        state = payload;
        render();
        /* the menubar keeps its own copy of this state (the Profiles menu lists the playbooks) —
           one event keeps the two from drifting apart */
        if (typeof document !== 'undefined' && document.dispatchEvent) {
            document.dispatchEvent(new CustomEvent('ofap:profiles'));
        }
    }

    function post(body) {
        return window.api('/api/control/profiles', { method: 'POST', body: body });
    }

    function refresh() {
        return window.api('/api/control/profiles').then(function (d) {
            var out = reload(d);
            paintProfileChip();
            return out;
        }).catch(function () {
            $('pfList').innerHTML = '<div class="hint">profiles unavailable — the server did not answer</div>';
        });
    }

    /* The active playbook, always visible: the status bar carries its name (click → this view).
       The MT5 habit — template + profile names live in the status bar — in this app's own words.
       `onclick` property, not a listener: the chip re-renders on every refresh, the ledger stays flat. */
    function paintProfileChip() {
        var chip = document.getElementById('statusProfileChip');
        if (!chip) return;
        var active = null;
        try { active = activeRow(); } catch (e) { active = null; }
        if (!active) { chip.hidden = true; chip.textContent = ''; return; }
        chip.hidden = false;
        chip.innerHTML = 'profile: <b>' + esc(active.name || active.id) + '</b>';
        chip.title = 'The active playbook — click to open Profiles';
        chip.onclick = function () { if (typeof window.showView === 'function') window.showView('profiles'); };
    }

    /* The block picker: which parts of the setup the new playbook carries. Every block is ticked
       by default (a profile that carries everything is what most people mean), and the server
       clamps the list to the blocks it actually knows. */
    function renderBlockPicker() {
        var box = $('pfBlocks');
        if (!box) return;
        var available = (state && state.blocks_available) || [];
        box.innerHTML = available.map(function (b) {
            return '<label class="switch" style="margin:0 10px 0 0" title="' +
                esc(BLOCK_NOTES[b] || b) + '"><input type="checkbox" data-block="' + esc(b) + '" checked> ' +
                esc(label(b)) + '</label>';
        }).join('') || '<span class="dim">the store reported no blocks</span>';
    }

    function chosenBlocks() {
        var out = [];
        Array.prototype.forEach.call($('pfBlocks').querySelectorAll('input[data-block]'), function (el) {
            if (el.checked) out.push(el.getAttribute('data-block'));
        });
        return out;
    }

    function showNameForm(mode, row) {
        nameMode = mode;
        nameTarget = row ? row.id : '';
        $('pfNameLabel').textContent = mode === 'rename' ? 'New name' : (mode === 'duplicate' ? 'New name (copy of ' + (row ? row.name : '') + ')' : 'Name');
        $('pfName').value = mode === 'rename' && row ? row.name : '';
        $('pfTags').value = mode === 'create' ? '' : (row && row.tags || []).join(', ');
        $('pfTags').style.display = mode === 'create' ? '' : 'none';
        $('pfNameGo').textContent = mode === 'create' ? 'Create' : (mode === 'rename' ? 'Rename' : 'Duplicate');
        if ($('pfBlocksRow')) {
            $('pfBlocksRow').style.display = mode === 'create' ? '' : 'none';
            if (mode === 'create') { renderBlockPicker(); $('pfFromDefaults').checked = false; }
        }
        $('pfNameRow').style.display = '';
        $('pfName').focus();
    }

    function hideNameForm() {
        $('pfNameRow').style.display = 'none';
        if ($('pfBlocksRow')) $('pfBlocksRow').style.display = 'none';
    }

    function submitNameForm() {
        var name = $('pfName').value.trim();
        if (!name) { banner('a profile needs a name', 'warn'); return; }
        var body;
        if (nameMode === 'create') {
            var tags = $('pfTags').value.split(',').map(function (t) { return t.trim(); }).filter(Boolean);
            var blocks = chosenBlocks();
            if (!blocks.length) { banner('tick at least one part for the playbook to carry', 'warn'); return; }
            body = { save: { name: name, tags: tags, blocks: blocks,
                             from_defaults: !!($('pfFromDefaults') && $('pfFromDefaults').checked) } };
        } else if (nameMode === 'rename') {
            body = { rename: nameTarget, to: name };
        } else {
            body = { duplicate: nameTarget, name: name };
        }
        post(body).then(function (out) {
            reload(out);
            if (!out.ok) { banner(out.error || 'the store refused that', 'warn'); return; }
            hideNameForm();
            banner(nameMode === 'create' ? 'saved — this profile is now your active playbook'
                : (nameMode === 'rename' ? 'renamed' : 'duplicated'), 'ok');
        });
    }

    function showPreview(ident) {
        post({ apply: ident, dry_run: true }).then(function (out) {
            if (!out.ok) { banner(out.error || 'cannot preview that profile', 'warn'); return; }
            pendingApply = ident;
            $('pfPreviewName').textContent = out.name || '';
            var changed = out.changed || [];
            var restart = out.restart || [];
            var html = out.already_current
                ? '<div class="hint">the live setup already matches this profile — switching is a no-op</div>'
                : '<div class="dim">this switch changes <b>' + changed.length + '</b> block' + (changed.length === 1 ? '' : 's') + ':</div>' +
                '<div style="margin:4px 0">' + changed.map(function (b) { return '<span class="tag" title="' + esc(label(b)) + (BLOCK_NOTES[b] ? ' \u2014 ' + esc(BLOCK_NOTES[b]) : '') + '">' + esc(label(b)) + '</span>'; }).join(' ') + '</div>' +
                (restart.length ? '<div class="banner" style="display:block">' + esc(restart.map(label).join(', ')) + ' are read when the engine starts — the running engine keeps its current setup until you restart it (Engine view, or Ctrl+Alt+R)</div>' : '');
            $('pfPreview').innerHTML = html;
            $('pfApplyGo').disabled = !!out.already_current;
            $('pfPreviewCard').style.display = '';
            $('pfPreviewCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    }

    function doApply(ident) {
        post({ apply: ident }).then(function (out) {
            if (!out.ok) { banner(out.error || 'the store refused that switch', 'warn'); return; }
            if (window.OFAPMENUBAR_RECENT) { try { window.OFAPMENUBAR_RECENT('profile', out.name || ident, ident); } catch (e) {} }
            if (typeof toast === 'function') toast(document.body, 'Applied "' + (out.name || '') + '" — reloading the workspace', 'ok');
            setTimeout(function () { location.reload(); }, 650);
        });
    }

    function act(btn) {
        var id = btn.getAttribute('data-id'), what = btn.getAttribute('data-act');
        var row = state && state.items.filter(function (r) { return r.id === id; })[0];
        if (what === 'preview') { showPreview(id); }
        if (what === 'versions') {
            var card = btn.closest('.card');
            var vers = card && card.querySelector('.pf-vers');
            if (vers) { vers.hidden = !vers.hidden; }
        }
        if (what === 'restore') {
            var at = Number(btn.getAttribute('data-at')) || 0;
            post({ restore_version: { id: id, at: at } }).then(function (out) {
                reload(out);
                banner(out.ok ? 'put back to that setup — the one it replaced is kept under Versions'
                              : (out.error || 'restore refused'), out.ok ? 'ok' : 'warn');
            });
        }
        if (what === 'update') {
            post({ update: id }).then(function (out) {
                reload(out);
                banner(out.ok ? 're-captured from the current setup' : (out.error || 'update refused'), out.ok ? 'ok' : 'warn');
            });
        }
        if (what === 'rename') { showNameForm('rename', row); }
        if (what === 'duplicate') { showNameForm('duplicate', row); }
        if (what === 'restart-engine') {
            banner('restarting the engine…', 'ok');
            window.api('/api/control/engine/restart', { method: 'POST', body: {} }).then(function (out) {
                banner(out && out.ok ? 'engine restarted — this playbook is fully live' : ((out && out.error) || 'the engine did not restart'),
                       out && out.ok ? 'ok' : 'warn');
                return refresh();
            }).catch(function () { banner('the engine did not restart', 'warn'); });
            return;
        }
        if (what === 'export') { exportProfile(id); }
        if (what === 'default') {
            post({ default: id }).then(function (out) { reload(out); banner('startup profile set — enable "apply at launch" to use it', 'ok'); });
        }
        if (what === 'delete') {
            if (btn.getAttribute('data-armed') !== '1') {
                btn.setAttribute('data-armed', '1');
                btn.textContent = 'Confirm delete';
                setTimeout(function () { btn.setAttribute('data-armed', '0'); btn.textContent = 'Delete'; }, 3000);
                return;
            }
            post({ delete: id }).then(function (out) {
                reload(out);
                banner(out.ok ? 'deleted — a version stays recoverable on the server' : (out.error || 'delete refused'), out.ok ? 'ok' : 'warn');
            });
        }
    }

    function exportProfile(id) {
        post({ export: id }).then(function (out) {
            if (!out.ok) { banner(out.error || 'export refused', 'warn'); return; }
            window.api('/api/control/export/save', { method: 'POST', body: { name: out.filename, text: out.text } })
                .then(function (saved) { banner('exported to ' + (saved.path || 'your exports folder'), 'ok'); });
        });
    }

    function activeRow() {
        return state && state.items.filter(function (r) { return r.id === state.active; })[0];
    }

    function chosenDays() {
        var days = [];
        for (var i = 0; i < 7; i++) { if ($('pfDay' + i).checked) days.push(i); }
        return days;
    }

    /* ── auto-switch: the same apply path, fired by a rule instead of a click ─────────────── */

    /* The matching pure, so node can pin it (profiles.selftest.js): rules are inert data and the
       decision "which profile should be live at 05:30 on a Tuesday" must not depend on the DOM. */
    function matchRule(rules, feed, now) {
        if (!rules || !rules.enabled) return '';
        var bySrc = (rules.sources || {})[String(feed || '').toLowerCase()];
        if (bySrc) return bySrc;
        var hhmm = ('0' + now.getHours()).slice(-2) + ':' + ('0' + now.getMinutes()).slice(-2);
        var day = now.getDay();
        var hit = ((rules.windows) || []).filter(function (w) {
            return (w.days || []).length ? (w.days || []).indexOf(day) >= 0 : true;
        }).filter(function (w) {
            var f = String(w.from || '00:00'), t = String(w.to || '23:59');
            return f <= t ? (hhmm >= f && hhmm < t) : (hhmm >= f || hhmm < t);      // overnight windows
        })[0];
        return hit ? hit.profile : '';
    }

    function ruleTarget(now) {
        return matchRule(state && state.rules, (cfgNow() || {}).data_source, now);
    }

    function tick() {
        if (!$('pfList')) return;
        var target = ruleTarget(new Date());
        if (target && target !== state.active) {
            var row = state.items.filter(function (r) { return r.id === target; })[0];
            if (typeof toast === 'function') toast(document.body, 'Auto-switch: "' + (row ? row.name : target) + '" matches now — applying', 'info');
            doApply(target);
        }
    }

    function boot() {
        if (!$('pfList')) return;

        $('pfSave').onclick = function () { showNameForm('create', null); };
        $('pfNameGo').onclick = submitNameForm;
        $('pfNameCancel').onclick = hideNameForm;
        $('pfName').onkeydown = function (ev) { if (ev.key === 'Enter') submitNameForm(); };
        $('pfImport').onclick = function () { $('pfImportRow').style.display = ''; $('pfImportText').focus(); };
        $('pfImportCancel').onclick = function () { $('pfImportRow').style.display = 'none'; };
        /* A shared playbook usually arrives as a file — read it client-side and drop it in the box
           the paste path already validates. */
        $('pfImportPick').onclick = function () {
            var picker = document.createElement('input');
            picker.type = 'file';
            picker.accept = '.json,application/json';
            picker.onchange = function () {
                var file = picker.files && picker.files[0];
                if (!file) return;
                var reader = new FileReader();
                reader.onload = function () { $('pfImportText').value = String(reader.result || ''); $('pfImportGo').focus(); };
                reader.onerror = function () { banner('that file could not be read', 'warn'); };
                reader.readAsText(file);
            };
            picker.click();
        };
        $('pfImportGo').onclick = function () {
            var text = $('pfImportText').value.trim();
            if (!text) { banner('paste a profile file first', 'warn'); return; }
            var bundle;
            try { bundle = JSON.parse(text); } catch (e) { banner('that is not valid JSON', 'warn'); return; }
            post({ import: bundle }).then(function (out) {
                reload(out);
                banner(out.ok ? 'imported — it is a copy, make it yours' : (out.error || 'import refused'), out.ok ? 'ok' : 'warn');
                if (out.ok) { $('pfImportRow').style.display = 'none'; $('pfImportText').value = ''; }
            });
        };
        $('pfList').addEventListener('click', function (ev) {
            var btn = ev.target && ev.target.closest ? ev.target.closest('button[data-act]') : null;
            if (btn) act(btn);
        });
        $('pfApplyCancel').onclick = function () { $('pfPreviewCard').style.display = 'none'; pendingApply = ''; };
        $('pfApplyGo').onclick = function () { if (pendingApply) doApply(pendingApply); };
        $('pfDefault').onchange = function () { post({ default: $('pfDefault').value }).then(reload); };
        $('pfAutoApply').onchange = function () {
            post({ default: $('pfDefault').value, auto_apply: $('pfAutoApply').checked }).then(function (out) {
                reload(out); banner(out.auto_apply ? 'the startup profile will be applied at launch' : 'startup apply is off', 'ok');
            });
        };
        $('pfRulesOn').onchange = function () { post({ rules_enabled: $('pfRulesOn').checked }).then(reload); };
        $('pfRuleAdd').onclick = function () {
            var days = chosenDays();
            var windows = (((state || {}).rules || {}).windows || []).concat([{
                from: $('pfRuleFrom').value || '09:00', to: $('pfRuleTo').value || '17:00',
                days: days, profile: $('pfRuleProfile').value,
            }]);
            post({ rules: { enabled: true, windows: windows } }).then(function (out) {
                reload(out);
                banner(out.rules && out.rules.windows.length === windows.length ? 'window added' : 'the store dropped that window (check clock and profile)', 'ok');
            });
        };
        $('pfRuleFeedBind').onclick = function () {
            var sources = Object.assign({}, ((state || {}).rules || {}).sources || {});
            sources[$('pfRuleFeed').value] = $('pfRuleFeedProfile').value;
            post({ rules: { enabled: true, sources: sources } }).then(function (out) { reload(out); banner('feed bound', 'ok'); });
        };
        $('pfRulesList').addEventListener('click', function (ev) {
            var btn = ev.target && ev.target.closest ? ev.target.closest('button[data-act]') : null;
            if (!btn) return;
            if (btn.getAttribute('data-act') === 'unbind-feed') {
                var sources = Object.assign({}, (((state || {}).rules || {}).sources) || {});
                delete sources[btn.getAttribute('data-feed')];
                post({ rules: { sources: sources } }).then(reload);
            }
            if (btn.getAttribute('data-act') === 'drop-window') {
                var at = Number(btn.getAttribute('data-at'));
                var windows = ((((state || {}).rules || {}).windows) || []).filter(function (_, i) { return i !== at; });
                post({ rules: { windows: windows } }).then(reload);
            }
        });

        var wrap = window.showView;
        if (typeof wrap === 'function' && !wrap.__ofapWrapped_profiles) {
            var wrapped = function (viewname) {
                var out = wrap.apply(this, arguments);
                if (viewname === 'profiles') refresh();
                return out;
            };
            wrapped.__ofapWrapped_profiles = true;
            window.showView = wrapped;
        }
        refresh();
        setInterval(tick, 30000);
        setTimeout(tick, 4000);
    }

    /* Exposed for the Node selftest (the same contract shell.js keeps): the rule maths and the two
       formatters run without a document — plus the entry points the main menu and the palette use,
       so a menu item runs exactly the path the button beside it runs. */
    if (typeof window !== 'undefined') {
        window.OFAPPROFILES = {
        /* The status bar says "restart to apply: …" for switches made from the menu or the palette:
           it names the same blocks in the same words this view does. */
        blockLabel: label,
            matchRule: matchRule, spent: spent, when: when,
            refresh: refresh,
            state: function () { return state; },
            switchTo: function (ident) {
                showView('profiles');
                refresh().then(function () { showPreview(ident); });
            },
            saveAs: function () { showView('profiles'); showNameForm('create', null); },
            updateActive: function () {
                var row = activeRow();
                if (!row) { banner('no playbook is applied — switch to one first', 'warn'); return; }
                post({ update: row.id }).then(function (out) {
                    reload(out);
                    banner(out.ok ? 're-captured from the current setup' : (out.error || 'update refused'), out.ok ? 'ok' : 'warn');
                });
            },
            renameActive: function () { var row = activeRow(); if (row) showNameForm('rename', row); },
            duplicateActive: function () { var row = activeRow(); if (row) showNameForm('duplicate', row); },
            exportActive: function () { var row = activeRow(); if (row) { exportProfile(row.id); } },
            toggleAutoApply: function (on) {
                post({ default: (state || {}).default || '', auto_apply: !!on }).then(function (out) {
                    reload(out);
                    banner(out.auto_apply ? 'the startup playbook will be applied at launch' : 'startup apply is off', 'ok');
                });
            },
            toggleRules: function (on) {
                post({ rules_enabled: !!on }).then(function (out) {
                    reload(out);
                    banner(out.rules && out.rules.enabled ? 'auto-switch rules are on' : 'auto-switch rules are off', 'ok');
                });
            },
        };
    }

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
        else boot();
    }
})();
