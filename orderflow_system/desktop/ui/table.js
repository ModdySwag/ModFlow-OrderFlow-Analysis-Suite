/* table.js — T15/B5: the one table component.
 *
 * One renderer for every tabular surface, so the conventions are learned once: click a header to
 * sort (asc → desc → off), right-click a header for the column set and the group-by, drag a header
 * to reorder. The layout is the user's and is remembered per table id under `ui.tables` — the same
 * config-is-the-record rule every other surface follows. The pure half (order/sort/group/move) is
 * pinned by table.selftest.js; adoption is per-surface behind `ui.table_component`, new surfaces
 * first — the Watchlist is the trial host.
 */
(function (root) {
    'use strict';

    /* ── pure ──────────────────────────────────────────────────────────────── */

    function applyOrder(columns, prefs) {
        const order = (prefs && prefs.order) || [];
        const hidden = (prefs && prefs.hidden) || [];
        const rank = (key) => { const at = order.indexOf(key); return at < 0 ? 999 : at; };
        return (columns || [])
            .filter((c) => hidden.indexOf(c.key) < 0)
            .slice()
            .sort((a, b) => rank(a.key) - rank(b.key));
    }

    function cycleSort(sort, key) {
        if (!sort || sort.key !== key) return { key: key, dir: 'asc' };
        if (sort.dir === 'asc') return { key: key, dir: 'desc' };
        return null;
    }

    function cmp(a, b) {
        const na = Number(a), nb = Number(b);
        if (isFinite(na) && isFinite(nb) && String(a).trim() !== '' && String(b).trim() !== '') return na - nb;
        return String(a == null ? '' : a).localeCompare(String(b == null ? '' : b));
    }

    function sortRows(rows, sort) {
        if (!sort || !sort.key) return (rows || []).slice();
        const dir = sort.dir === 'desc' ? -1 : 1;
        return (rows || []).slice().sort((a, b) => dir * cmp(a[sort.key], b[sort.key]));
    }

    function groupRows(rows, groupKey) {
        if (!groupKey) return [{ label: '', rows: (rows || []).slice() }];
        const seen = {};
        const order = [];
        (rows || []).forEach((r) => {
            const label = String(r[groupKey] == null ? '—' : r[groupKey]);
            if (!seen[label]) { seen[label] = { label: label, rows: [] }; order.push(label); }
            seen[label].rows.push(r);
        });
        return order.map((k) => seen[k]);
    }

    function moveColumn(order, from, to) {
        const out = (order || []).slice();
        const at = out.indexOf(from);
        const destAt = out.indexOf(to);
        if (at < 0 || destAt < 0) return out;                 // unknown header: a no-op, never a guess
        out.splice(at, 1);
        out.splice(destAt, 0, from);                          // the dragged header takes the target's slot
        return out;
    }

    /* ── prefs (ui.tables is the record) ───────────────────────────────────── */

    function prefsOf(id) {
        const cfg = (typeof S !== 'undefined' && S && S.config && S.config.ui && S.config.ui.tables) || {};
        return cfg[id] || {};
    }
    let saveTimer = 0;
    function savePrefs(id, prefs) {
        if (typeof S !== 'undefined' && S && S.config) {
            S.config.ui = S.config.ui || {};
            S.config.ui.tables = S.config.ui.tables || {};
            S.config.ui.tables[id] = prefs;
        }
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
            if (typeof api === 'function') {
                const patch = {};
                patch[id] = prefs;
                void api('/api/control/config', { method: 'POST', body: { ui: { tables: patch } } })
                    .catch(function () { /* the in-page copy stands */ });
            }
        }, 600);
    }

    /* ── render ────────────────────────────────────────────────────────────── */

    /* C-05: one live menu per table, and its document listener is removed when it closes — the
       old shape leaked a listener and a detached .draw-menu subtree per column action. */
    let currentMenu = null;
    let currentOff = null;

    function closeCurrentMenu() {
        if (currentOff) { document.removeEventListener('mousedown', currentOff, true); currentOff = null; }
        if (currentMenu && currentMenu.parentNode) currentMenu.parentNode.removeChild(currentMenu);
        currentMenu = null;
    }

    function menuFor(host, spec, prefs, refresh) {
        closeCurrentMenu();
        const old = host.querySelector('.draw-menu');
        if (old) old.parentNode.removeChild(old);
        const menu = document.createElement('div');
        menu.className = 'draw-menu';
        const mk = (text, fn) => {
            const b = document.createElement('button');
            b.className = 'draw-menu-item';
            b.textContent = text;
            b.addEventListener('click', (ev) => { ev.stopPropagation(); fn(); });
            menu.appendChild(b);
            return b;
        };
        (spec.columns || []).forEach((col) => {
            const hidden = (prefs.hidden || []).indexOf(col.key) >= 0;
            mk((hidden ? '☐ ' : '☑ ') + col.label, () => {
                const set = new Set(prefs.hidden || []);
                if (hidden) set.delete(col.key); else set.add(col.key);
                prefs.hidden = Array.from(set);
                savePrefs(spec.id, prefs);
                refresh();
            });
        });
        mk('Group by: ' + (spec.groupBy || 'none'), () => {
            const keys = [''].concat((spec.columns || []).map((c) => c.key));
            const at = keys.indexOf(spec.groupBy || '');
            spec.groupBy = keys[(at + 1) % keys.length];
            prefs.group = spec.groupBy;
            savePrefs(spec.id, prefs);
            refresh();
        });
        mk('Reset this table\u2019s layout', () => {
            Object.keys(prefs).forEach((k) => delete prefs[k]);
            savePrefs(spec.id, prefs);
            refresh();
        });
        host.appendChild(menu);
        currentMenu = menu;
        setTimeout(() => {
            const dialog = menu;
            const off = (ev2) => {
                if (!dialog.isConnected) { closeCurrentMenu(); return; }
                if (dialog.contains(ev2.target)) return;
                closeCurrentMenu();
            };
            currentOff = off;
            document.addEventListener('mousedown', off, true);
        }, 0);
    }

    function render(host, spec) {
        if (!host || !spec || !spec.columns) return null;
        const prefs = prefsOf(spec.id);
        spec.groupBy = prefs.group !== undefined ? prefs.group : (spec.groupBy || '');
        let sort = prefs.sort || null;

        const refresh = () => {
            const cols = applyOrder(spec.columns, prefs);
            const rows = sortRows(spec.rows || [], sort);
            const groups = groupRows(rows, spec.groupBy);
            const head = '<div class="oft-head">' + cols.map((c) => {
                const on = sort && sort.key === c.key ? (sort.dir === 'asc' ? ' \u25b4' : ' \u25be') : '';
                return '<span class="oft-th" draggable="true" data-key="' + c.key + '"' + (c.align === 'right' ? ' style="text-align:right"' : '')
                    + ' title="Click to sort \u00b7 right-click for columns and grouping \u00b7 drag to reorder">' + c.label + on + '</span>';
            }).join('') + '</div>';
            const body = groups.map((g) => {
                const ghead = spec.groupBy ? '<div class="oft-group">' + String(g.label) + ' (' + g.rows.length + ')</div>' : '';
                return ghead + g.rows.map((r) => {
                    const tds = cols.map((c) => '<span class="oft-td" data-key="' + c.key + '"'
                        + (c.align === 'right' ? ' style="text-align:right"' : '') + '>'
                        + String(r[c.key] == null ? '\u2014' : r[c.key]) + '</span>').join('');
                    return '<div class="oft-row' + (r.active ? ' on' : '') + '" data-symbol="' + (r.symbol || '') + '">' + tds + '</div>';
                }).join('');
            }).join('');
            host.innerHTML = '<div class="oft">' + head + '<div class="oft-body">'
                + (body || '<div class="dim">no rows</div>') + '</div></div>';
            host.querySelectorAll('.oft-th').forEach((th) => {
                th.addEventListener('click', () => {
                    sort = cycleSort(sort, th.getAttribute('data-key'));
                    prefs.sort = sort || undefined;
                    if (!sort) delete prefs.sort;
                    savePrefs(spec.id, prefs);
                    refresh();
                });
                th.addEventListener('contextmenu', (ev) => {
                    ev.preventDefault();
                    menuFor(host, spec, prefs, refresh);
                });
                th.addEventListener('dragstart', (ev) => { ev.dataTransfer.setData('text/plain', th.getAttribute('data-key')); });
                th.addEventListener('dragover', (ev) => {
                    ev.preventDefault();
                    const key = th.getAttribute('data-key');
                    const from = ev.dataTransfer.getData('text/plain');
                    if (!from || from === key) return;
                    const order = (prefs.order && prefs.order.length ? prefs.order : spec.columns.map((c) => c.key));
                    prefs.order = moveColumn(order, from, key);
                    savePrefs(spec.id, prefs);
                    refresh();
                });
            });
            if (spec.onRow) {
                host.querySelectorAll('.oft-row').forEach((rowEl) => {
                    rowEl.addEventListener('click', () => spec.onRow({ symbol: rowEl.getAttribute('data-symbol') }));
                });
            }
        };
        refresh();
        return host;
    }

    root.OFAPTABLE = { render: render, applyOrder: applyOrder, cycleSort: cycleSort, sortRows: sortRows,
        groupRows: groupRows, moveColumn: moveColumn, prefsOf: prefsOf };
})(typeof globalThis !== 'undefined' ? globalThis : this);
