/* lookup.js — T14/B6: the instrument look-up across every feed.
 *
 * One overlay answers "how do I find X?" without leaving the surface: connection → group → rows,
 * with counting that never inflates (X shown of Y listed) and the two actions the app already
 * offers — Use (its own symbol switch) and Enable (the same venue-confirmed add route the
 * Instruments view writes through). No row is invented: Bybit rows come from the venue's own
 * catalogue, MT5 rows from the broker's own search, Alpaca rows from the map this install has.
 * The last filters persist in the config (ui.lookup), so reopening lands where the user left off.
 */
(function () {
    'use strict';

    const PERSIST_MS = 600;
    const state = { open: false, root: null, timer: 0, filter: { source: 'all', type: 'all', text: '' },
        data: {}, counts: {}, note: '' };

    function el(id) { return document.getElementById(id); }
    function cfg() { return (typeof S !== 'undefined' && S && S.config) || null; }
    function esc(t) { return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

    /* ── the overlay shell (built once) ─────────────────────────────────────── */
    function ensureUI() {
        if (state.root && state.root.isConnected) return state.root;
        const root = document.createElement('div');
        root.className = 'lk-overlay';
        root.hidden = true;
        root.innerHTML =
            '<div class="lk-panel card" role="dialog" aria-label="Instrument look-up">' +
            '  <div class="card-head"><span class="card-title">Instrument look-up</span>' +
            '    <div class="spacer"></div><span class="dim" id="lkCounters">—</span>' +
            '    <button class="btn small" id="lkClose" type="button">Close</button></div>' +
            '  <div class="card-body">' +
            '    <div class="row">' +
            '      <div class="field"><label>Connection</label><select id="lkSource">' +
            '        <option value="all">All connections</option>' +
            '        <option value="bybit">Bybit perpetuals</option>' +
            '        <option value="mt5">MetaTrader 5</option>' +
            '        <option value="alpaca">Alpaca</option></select></div>' +
            '      <div class="field" style="flex:1"><label>Search</label>' +
            '        <input type="text" id="lkText" placeholder="type a name — NQ1!, US100, BTCUSDT, EURUSD…"></div>' +
            '      <div class="field"><label>Group</label><select id="lkType"><option value="all">All groups</option></select></div>' +
            '    </div>' +
            '    <div class="hint" id="lkNote">—</div>' +
            '    <div class="lk-body" id="lkBody"><div class="dim">Loading…</div></div>' +
            '  </div></div>';
        document.body.appendChild(root);
        state.root = root;
        el('lkClose').onclick = () => close();
        root.addEventListener('mousedown', (ev) => { if (ev.target === root) close(); });
        el('lkSource').addEventListener('change', () => { state.filter.source = el('lkSource').value; state.filter.type = 'all'; void refresh(); persistSoon(); });
        el('lkType').addEventListener('change', () => { state.filter.type = el('lkType').value; paintBody(); persistSoon(); });
        let debounce = 0;
        el('lkText').addEventListener('input', () => {
            state.filter.text = el('lkText').value;
            clearTimeout(debounce);
            debounce = setTimeout(() => { void refresh(); }, 250);
            persistSoon();
        });
        document.addEventListener('keydown', (ev) => {
            if (!state.open) return;
            if (ev.key === 'Escape') { close(); }
        });
        return root;
    }

    /* ── the sources ────────────────────────────────────────────────────────── */

    async function loadBybit() {
        const res = await api('/api/control/instruments/catalog');
        if (!res || res.ok === false) return { ok: false, why: (res && res.error) || 'the venue did not answer', rows: [], total: 0 };
        const rows = (res.majors || []).map((m) => ({
            app: m.symbol, label: m.symbol,
            detail: 'tick ' + m.tick_size + (m.status ? ' · ' + m.status : ''),
            enabled: !!m.in_config, source: 'bybit',
            group: /USDC$/.test(m.symbol) ? 'USDC perpetuals' : 'USDT perpetuals',
        }));
        return { ok: true, rows: rows, total: Number(res.venue_total) || rows.length,
            why: 'the venue lists ' + (Number(res.venue_total) || rows.length) + ' linear perpetuals; the majors are shown here — the rest arrive through the symbol search' };
    }

    async function loadMt5() {
        const q = String(state.filter.text || '').trim();
        if (!q) {
            const probe = await api('/api/control/mt5/symbols?q=&limit=1');
            const total = (probe && Number(probe.total)) || 0;
            return { ok: true, rows: [], total: total,
                why: probe && probe.available === false
                    ? ('the terminal is not available right now — ' + (probe.reason || 'not logged in') + (total ? ' (' + total + ' symbols cached)' : ''))
                    : (total ? 'your broker lists ' + total + ' symbols — type to search the whole list' : 'your broker lists no symbols the cache can see') };
        }
        const res = await api('/api/control/mt5/symbols?q=' + encodeURIComponent(q) + '&limit=200');
        if (!res || res.ok === false) return { ok: false, why: (res && (res.reason || res.error)) || 'the broker did not answer', rows: [], total: 0 };
        const rows = (res.symbols || []).map((r) => ({
            app: String(r.name).toUpperCase(), label: r.name,
            detail: [r.description, r.tick_size ? ('tick ' + r.tick_size) : (r.listed === false ? 'not currently listed' : '')].filter(Boolean).join(' · '),
            enabled: false, source: 'mt5', group: 'starts with ' + (String(r.name).match(/^[A-Za-z]+/) || [String(r.name)[0] || '?'])[0].toUpperCase(),
        }));
        return { ok: true, rows: rows, total: Number(res.total) || rows.length,
            why: 'showing ' + rows.length + ' of ' + (Number(res.total) || rows.length) + ' matching symbols' + (res.available === false ? ' · ' + (res.reason || 'terminal unavailable — names from the cache') : '') };
    }

    async function loadAlpaca() {
        const al = (typeof S !== 'undefined' && S && S.caps && S.caps.alpaca) || {};
        const map = al.symbols || {};
        const rows = Object.keys(map).map((app) => ({
            app: app, label: app + '  (' + map[app] + ')',
            detail: String(map[app]).indexOf('/') >= 0 ? 'crypto pair' : 'US equity / ETF',
            enabled: false, source: 'alpaca',
            group: String(map[app]).indexOf('/') >= 0 ? 'crypto pairs' : 'stocks & ETFs',
        }));
        return { ok: true, rows: rows, total: rows.length,
            why: al.linked === false || !Object.keys(map).length
                ? 'no Alpaca account is linked — the full asset list lives in the symbol search once it is'
                : 'the ' + rows.length + ' pairs this install maps to Alpaca' };
    }

    const SOURCES = { bybit: loadBybit, mt5: loadMt5, alpaca: loadAlpaca };

    function enabledNow() {
        const cfg2 = cfg();
        const out = {};
        ((cfg2 && cfg2.instruments) || []).forEach((i) => { if (i && i.enabled) out[String(i.symbol).toUpperCase()] = true; });
        return out;
    }

    /* ── filtering, grouping, painting ──────────────────────────────────────── */

    function visibleRows(rows) {
        const text = String(state.filter.text || '').trim().toUpperCase();
        return (rows || []).filter((r) => {
            if (state.filter.type !== 'all' && r.group !== state.filter.type) return false;
            if (!text) return true;
            if (r.source === 'mt5') return true;                 // the broker already filtered server-side
            return r.label.toUpperCase().indexOf(text) >= 0 || r.app.indexOf(text) >= 0;
        });
    }

    function paintTypeOptions() {
        const sel = el('lkType');
        if (!sel) return;
        const groups = [];
        Object.keys(state.data).forEach((id) => {
            if (state.filter.source !== 'all' && state.filter.source !== id) return;
            (state.data[id].rows || []).forEach((r) => { if (groups.indexOf(r.group) < 0) groups.push(r.group); });
        });
        const keep = state.filter.type;
        sel.innerHTML = '<option value="all">All groups</option>'
            + groups.map((g) => '<option value="' + esc(g) + '">' + esc(g) + '</option>').join('');
        sel.value = groups.indexOf(keep) >= 0 ? keep : 'all';
        if (sel.value !== keep) state.filter.type = 'all';
    }

    function paintCounters() {
        const out = el('lkCounters');
        if (!out) return;
        const bits = [];
        Object.keys(state.counts).forEach((id) => {
            const c = state.counts[id];
            bits.push(id + ' ' + c.shown + '/' + c.total);
        });
        out.textContent = bits.join('  ·  ') || '—';
    }

    function rowHtml(r, enabled) {
        const on = enabled[r.app];
        return '<div class="lk-row"><span class="lk-sym">' + esc(r.label) + '</span>' +
            '<span class="lk-detail">' + esc(r.detail || '') + '</span>' +
            '<span class="lk-chip ' + (on ? 'on' : '') + '">' + (on ? 'enabled' : 'venue lists it') + '</span>' +
            '<button class="btn small" data-use="' + esc(r.app) + '" title="Switch the app to this instrument">Use</button>' +
            (on ? '' : '<button class="btn small" data-enable="' + esc(r.app) + '" data-source="' + esc(r.source) + '" title="Add it through the venue-confirmed route the Instruments view uses">Enable</button>') +
            '</div>';
    }

    function paintBody() {
        const body = el('lkBody');
        const note = el('lkNote');
        if (!body) return;
        if (note) note.textContent = state.note || '—';
        const enabled = enabledNow();
        const parts = [];
        Object.keys(state.data).forEach((id) => {
            if (state.filter.source !== 'all' && state.filter.source !== id) return;
            const pack = state.data[id] || { rows: [], why: '' };
            const rows = visibleRows(pack.rows);
            state.counts[id] = { shown: rows.length, total: pack.total || pack.rows.length };
            if (!rows.length) {
                parts.push('<div class="lk-sec">' + esc(id) + '</div><div class="hint">' + esc(pack.ok === false ? (pack.why || 'unavailable') : (pack.why || 'nothing loaded yet')) + '</div>');
                return;
            }
            const byGroup = {};
            rows.forEach((r) => { (byGroup[r.group] = byGroup[r.group] || []).push(r); });
            parts.push('<div class="lk-sec">' + esc(id) + ' — ' + rows.length + ' of ' + (pack.total || rows.length) + '</div>');
            Object.keys(byGroup).forEach((g) => {
                parts.push('<div class="lk-group">' + esc(g) + '</div>');
                parts.push(byGroup[g].slice(0, 60).map((r) => rowHtml(r, enabled)).join(''));
            });
        });
        body.innerHTML = parts.join('') || '<div class="dim">nothing to show</div>';
        paintCounters();
        body.querySelectorAll('[data-use]').forEach((b) => {
            b.onclick = () => {
                const sym = b.getAttribute('data-use');
                if (typeof searchActivateSymbol === 'function') searchActivateSymbol(sym, {});
                close();
            };
        });
        body.querySelectorAll('[data-enable]').forEach((b) => {
            b.onclick = () => { void enableRow(b.getAttribute('data-enable'), b.getAttribute('data-source'), b); };
        });
    }

    async function enableRow(symbol, source, button) {
        button.disabled = true;
        button.textContent = 'enabling…';
        const res = await api('/api/control/instruments/add',
            { method: 'POST', body: { symbols: [symbol], source: source, enable: true } });
        const ok = res && res.ok !== false && ((res.added || []).length + (res.updated || []).length) > 0;
        state.note = ok
            ? (symbol + ' enabled — restart the engine (Instruments ▸ Restart) to stream it')
            : (symbol + ' could not be enabled: ' + ((res && (res.error || (res.skipped || [])[0])) || 'the venue did not confirm it'));
        button.disabled = false;
        button.textContent = 'Enable';
        paintBody();
    }

    async function refresh() {
        const want = state.filter.source === 'all' ? ['bybit', 'mt5', 'alpaca'] : [state.filter.source];
        state.note = '';
        const jobs = want.map(async (id) => {
            try { state.data[id] = await SOURCES[id](); }
            catch (err) { state.data[id] = { ok: false, why: String(err), rows: [], total: 0 }; }
        });
        await Promise.all(jobs);
        paintTypeOptions();
        paintBody();
    }

    /* ── persistence (ui.lookup) ────────────────────────────────────────────── */

    function persistSoon() {
        clearTimeout(state.timer);
        state.timer = setTimeout(() => {
            const c = cfg();
            if (c) {
                c.ui = c.ui || {};
                c.ui.lookup = { source: state.filter.source, type: state.filter.type, text: state.filter.text };
            }
            if (typeof api === 'function') {
                void api('/api/control/config', { method: 'POST', body: { ui: { lookup: {
                    source: state.filter.source, type: state.filter.type, text: state.filter.text } } } })
                    .catch(function () { /* the in-page copy still stands */ });
            }
        }, PERSIST_MS);
    }

    function adoptFilters() {
        const c = cfg();
        const saved = (c && c.ui && c.ui.lookup) || null;
        if (!saved) return;
        state.filter.source = String(saved.source || 'all');
        state.filter.type = String(saved.type || 'all');
        state.filter.text = String(saved.text || '');
    }

    /* ── open / close ───────────────────────────────────────────────────────── */

    async function open() {
        ensureUI();
        adoptFilters();
        if (el('lkSource')) el('lkSource').value = state.filter.source;
        if (el('lkText')) el('lkText').value = state.filter.text;
        state.root.hidden = false;
        state.open = true;
        await refresh();
        if (el('lkText')) el('lkText').focus();
    }

    function close() {
        if (state.root) state.root.hidden = true;
        state.open = false;
    }

    window.OFAPLOOKUP = { open: open, close: close, state: function () { return state.filter; } };
})();
