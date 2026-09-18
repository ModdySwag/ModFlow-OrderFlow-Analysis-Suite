/* colrail.js — T14/B4: the columns rail for the Map view.
 *
 * A slim rail right of the heat canvas: one row per column of the snapshot window, each carrying an
 * accumulation the user controls. The reset semantics are the point — manual (a button or a
 * double-click), scheduled (every N seconds) or conditional (when a row's accumulation crosses a
 * threshold) — and they are pure enough to pin. Totals come from the snapshot itself; the rail only
 * accumulates the DELTAS between snapshots ('since reset' has an honest start), and never invents a
 * number the payload did not carry.
 */
(function (root) {
    'use strict';

    const METRICS = ['traded', 'resting'];
    const RESETS = ['manual', 'scheduled', 'conditional'];
    const ROWS_SHOWN = 40;

    /* Pure: the column total for a metric — the same sums the KPI tiles use. */
    function totalOf(data, ci, metric) {
        const matrix = metric === 'resting' ? (data.values || []) : (data.traded || []);
        let sum = 0;
        for (let r = 0; r < matrix.length; r += 1) {
            const row = matrix[r];
            if (row && row[ci]) sum += Number(row[ci]) || 0;
        }
        return sum;
    }

    /* Pure: one observation step. Merges the snapshot into the accumulator map.
     *
     *   acc      — accumulated delta since the entry's last reset
     *   last     — the previous total (deltas need a previous reading)
     *   reset_at — when the entry last reset (scheduled/conditional use the clock)
     *
     * Returns a NEW map; reset policy is evaluated here so the selftest can pin every branch. */
    function reduce(prev, data, nowMs, cfg) {
        const out = Object.assign({}, prev || {});
        const buckets = data.buckets || [];
        const metric = cfg && METRICS.indexOf(cfg.metric) >= 0 ? cfg.metric : 'traded';
        const policy = cfg && RESETS.indexOf(cfg.reset) >= 0 ? cfg.reset : 'manual';
        const threshold = Math.max(0, Number((cfg && cfg.threshold) || 0));
        const period = Math.max(5, Number((cfg && cfg.reset_s) || 30)) * 1000;
        const now = Number(nowMs) || 0;
        buckets.forEach((bucket, ci) => {
            const key = String(bucket);
            const total = totalOf(data, ci, metric);
            const entry = out[key] || { key: key, ts: Number(bucket) || 0, acc: 0, last: null, reset_at: now };
            if (policy === 'scheduled' && now - entry.reset_at >= period) {
                entry.acc = 0;
                entry.reset_at = now;
            }
            if (entry.last !== null) entry.acc += total - entry.last;
            entry.last = total;
            if (policy === 'conditional' && Math.abs(entry.acc) >= threshold && threshold > 0) {
                entry.acc = 0;
                entry.reset_at = now;
            }
            out[key] = entry;
        });
        /* Keep the map bounded: drop entries the window no longer carries. */
        const live = {};
        buckets.forEach((bucket) => { live[String(bucket)] = true; });
        Object.keys(out).forEach((k) => { if (!live[k]) delete out[k]; });
        return out;
    }

    /* Manual resets (button, double-click) — always available whatever the policy. */
    function resetEntry(entries, key, nowMs) {
        const out = Object.assign({}, entries);
        if (out[key]) out[key] = Object.assign({}, out[key], { acc: 0, reset_at: Number(nowMs) || 0 });
        return out;
    }
    function resetAll(entries, nowMs) {
        const out = {};
        Object.keys(entries || {}).forEach((k) => {
            out[k] = Object.assign({}, entries[k], { acc: 0, reset_at: Number(nowMs) || 0 });
        });
        return out;
    }

    const state = { entries: {}, cfg: null };

    function cfgOf() {
        const cfg = (typeof S !== 'undefined' && S && S.config && S.config.atlas && S.config.atlas.columns) || null;
        return { metric: (cfg && cfg.metric) || 'traded', reset: (cfg && cfg.reset) || 'manual',
            threshold: (cfg && Number(cfg.threshold)) || 0, reset_s: (cfg && Number(cfg.reset_s)) || 30 };
    }

    function fmt(n) {
        const v = Number(n) || 0;
        const a = Math.abs(v);
        if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
        if (a >= 1e3) return (v / 1e3).toFixed(1) + 'k';
        return a >= 100 ? Math.round(v).toString() : v.toFixed(1);
    }
    function hhmmss(ms) {
        const d = new Date(Number(ms) || 0);
        return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
            + ':' + String(d.getSeconds()).padStart(2, '0');
    }

    function paint() {
        const rows = document.getElementById('hmColRows');
        const note = document.getElementById('hmColNote');
        if (!rows) return;
        const cfg = state.cfg || cfgOf();
        const ordered = Object.keys(state.entries).map((k) => state.entries[k])
            .sort((a, b) => b.ts - a.ts).slice(0, ROWS_SHOWN);
        rows.innerHTML = ordered.map((e) => {
            const v = e.acc;
            const cls = v > 0 ? 'pos' : (v < 0 ? 'neg' : '');
            return '<div class="hm-rail-row" data-key="' + e.key + '" title="double-click to reset this column\'s accumulation">'
                + '<span class="hm-rail-t">' + hhmmss(e.ts) + '</span>'
                + '<span class="hm-rail-v ' + cls + '">' + (v > 0 ? '+' : '') + fmt(v) + '</span></div>';
        }).join('') || '<div class="dim">waiting for a snapshot…</div>';
        rows.querySelectorAll('.hm-rail-row').forEach((rowEl) => {
            rowEl.ondblclick = () => {
                state.entries = resetEntry(state.entries, rowEl.getAttribute('data-key'), Date.now());
                paint();
            };
        });
        if (note) {
            note.textContent = cfg.metric + ' since reset · ' + cfg.reset
                + (cfg.reset === 'conditional' ? ' (≥ ' + fmt(cfg.threshold) + ')' : '')
                + (cfg.reset === 'scheduled' ? ' (' + cfg.reset_s + 's)' : '');
        }
    }

    function observe(data) {
        if (!data || !Array.isArray(data.buckets) || !data.buckets.length) return;
        state.cfg = cfgOf();
        state.entries = reduce(state.entries, data, Date.now(), state.cfg);
        paint();
    }

    function wire() {
        const metric = document.getElementById('hmColMetric');
        const reset = document.getElementById('hmColReset');
        const thresh = document.getElementById('hmColThreshold');
        const all = document.getElementById('hmColResetAll');
        if (!metric || !reset) return;
        const cfg = cfgOf();
        state.cfg = cfg;
        metric.value = cfg.metric;
        reset.value = cfg.reset;
        if (thresh) thresh.value = String(cfg.threshold || '');
        const save = () => {
            const block = { metric: metric.value, reset: reset.value,
                threshold: Math.max(0, Number(thresh ? thresh.value : 0) || 0), reset_s: 30 };
            state.cfg = block;
            if (typeof api === 'function') {
                void api('/api/control/config', { method: 'POST', body: { atlas: { columns: block } } })
                    .catch(function () { /* the in-page copy stands */ });
            }
            if (typeof S !== 'undefined' && S && S.config) {
                S.config.atlas = S.config.atlas || {};
                S.config.atlas.columns = block;
            }
            paint();
        };
        metric.onchange = save;
        reset.onchange = save;
        if (thresh) thresh.onchange = save;
        if (all) all.onclick = () => { state.entries = resetAll(state.entries, Date.now()); paint(); };
    }

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
        else wire();
    }
    root.OFAPCOLRAIL = { observe: observe, reduce: reduce, totalOf: totalOf, resetEntry: resetEntry,
        resetAll: resetAll, METRICS: METRICS, RESETS: RESETS, fmt: fmt };
})(typeof globalThis !== 'undefined' ? globalThis : this);
