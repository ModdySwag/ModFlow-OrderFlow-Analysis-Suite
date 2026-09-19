/* ══════════════════════════════════════════════════════════════════
   VWAP overlay + trade detector panel  (the reference platform pass)

   The VWAP line is drawn on the existing Lightweight-Charts instance by adding
   series to it rather than touching the chart module: the chart owner (ui.js)
   keeps its candle and delta series, this file owns only its own lines.

   The trade-detector panel shows executions that ate resting depth and refills
   of those levels — the "Trade Detector" read, labelled as inference because a
   public feed carries no order identities.
   ══════════════════════════════════════════════════════════════════ */

/* own formatter: the app has no shared number helper, and a missing global here
   would break the whole overlay silently */
function vwapFmt(v, digits) {
    if (v === null || v === undefined || v === '') return '–';
    const n = Number(v);
    if (!isFinite(n)) return '–';
    if (digits !== undefined) return n.toFixed(digits);
    const a = Math.abs(n);
    if (a >= 1000) return n.toFixed(2);
    if (a >= 1) return n.toFixed(4);
    if (a >= 0.01) return n.toFixed(5);
    return n.toFixed(8).replace(/0+$/, '').replace(/\.$/, '');
}

const VWAP_UI = { series: null, upper: null, lower: null, anchor: null, last_key: '', charts_attached: false, detectorKey: '' };

function vwapStyles() {
    if (document.getElementById('vwapStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'vwapStyleSheet';
    st.textContent = `
        .vwap-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
                    margin: 8px 0 0; font-size: 12px; }
        .vwap-chip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px;
                     color: var(--dim); }
        .vwap-chip b { color: var(--fg); }
        .vwap-legend { display: inline-block; width: 10px; height: 2px; vertical-align: middle;
                       margin-right: 4px; }
        .dd-row { display: flex; gap: 8px; align-items: baseline; padding: 4px 0;
                  border-bottom: 1px solid var(--line); font-size: 12px; }
        .dd-row:last-child { border-bottom: 0; }
        .dd-side { flex: 0 0 54px; text-transform: uppercase; font-size: 11px; }
        .dd-side.buy { color: var(--up, #35d07f); }
        .dd-side.sell { color: var(--down, #ff5d6c); }
        .dd-main { flex: 1; }
        .dd-dim { color: var(--dim); }
        .dd-tag { border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; font-size: 11px; }
    `;
    document.head.appendChild(st);
}

/* ── chart overlay ─────────────────────────────────────────────── */
function vwapState() {
    /* ui.js declares `const S = {...}` — a script-scope binding, not a window property.
       Reaching for window.S here silently disabled the whole overlay. */
    try { return (typeof S !== 'undefined' && S) ? S : null; } catch (e) { return null; }
}

function vwapAttach() {
    if (VWAP_UI.charts_attached) return true;
    const st = vwapState();
    if (!st || !st.chart || typeof st.chart.addLineSeries !== 'function') return false;
    const mk = (color, width, style) => st.chart.addLineSeries({
        color, lineWidth: width, lineStyle: style || 0, priceLineVisible: false,
        lastValueVisible: false, crosshairMarkerVisible: false,
    });
    VWAP_UI.series = mk('rgba(240,196,84,0.95)', 2);                       // VWAP
    VWAP_UI.upper = mk('rgba(240,196,84,0.35)', 1, 2);                     // +1σ (dashed)
    VWAP_UI.lower = mk('rgba(240,196,84,0.35)', 1, 2);                     // −1σ (dashed)
    VWAP_UI.anchor = mk('rgba(120,180,255,0.85)', 1, 1);                   // anchored VWAP
    VWAP_UI.charts_attached = true;
    return true;
}

function vwapControls() {
    const host = document.getElementById('chart')?.parentElement?.parentElement;
    if (!host || document.getElementById('vwapBar')) return;
    vwapStyles();
    const bar = document.createElement('div');
    bar.className = 'vwap-bar';
    bar.id = 'vwapBar';
    bar.innerHTML = `
        <span class="vwap-chip"><span class="vwap-legend" style="background:#f0c454"></span>
            VWAP <b id="vwapVal">–</b></span>
        <span class="vwap-chip" title="Volume-weighted standard deviation bands: price inside 1σ is ordinary, outside 2σ is stretched.">
            ±1σ <b id="vwapBands">–</b></span>
        <span class="vwap-chip" id="vwapAnchorChip" title="An anchored VWAP accumulates only from the moment you anchor it — it never invents the past.">
            anchored <b id="vwapAnchor">not set</b></span>
        <button class="btn small" id="vwapAnchorBtn"
            title="Start the anchored VWAP at the current moment (blue line). Use it after a news print or a swing.">Anchor here</button>
        <button class="btn small" id="vwapClearBtn" title="Remove the anchored line">Clear</button>
        <span class="dim" id="vwapHint"></span>`;
    host.appendChild(bar);
    bar.querySelector('#vwapAnchorBtn').onclick = async () => {
        const st = vwapState();
        if (!st || !st.symbol) return;
        try {
            const r = await api(`/api/atlas/vwap/${st.symbol}/anchor`, { method: 'POST', body: {} });
            document.getElementById('vwapHint').textContent =
                `anchored at ${new Date(r.anchor_ms).toLocaleTimeString()}`;
        } catch (e) { document.getElementById('vwapHint').textContent = String(e); }
    };
    bar.querySelector('#vwapClearBtn').onclick = async () => {
        const st = vwapState();
        if (!st || !st.symbol) return;
        try {
            await api(`/api/atlas/vwap/${st.symbol}/anchor`, { method: 'POST', body: { clear: true } });
            document.getElementById('vwapHint').textContent = 'anchored line cleared';
        } catch (e) { document.getElementById('vwapHint').textContent = String(e); }
    };
}

async function vwapRefresh() {
    const st = vwapState();
    if (!st || !st.symbol || !vwapAttach()) return;
    vwapControls();
    try {
        const d = await api(`/api/atlas/vwap/${st.symbol}?points=400`);
        if (!d || !d.series) return;
        const key = `${d.version}|${(d.series || []).length}|${d.anchor_ms}|${d.vwap}`;
        if (key === VWAP_UI.last_key) return;                 // nothing new → no repaint
        VWAP_UI.last_key = key;
        VWAP_UI.series.setData(d.series.map((p) => ({ time: p.ts, value: p.vwap })));
        VWAP_UI.upper.setData(d.series.map((p) => ({ time: p.ts, value: p.upper1 })));
        VWAP_UI.lower.setData(d.series.map((p) => ({ time: p.ts, value: p.lower1 })));
        VWAP_UI.anchor.setData(d.anchored && d.anchored.vwap
            ? d.series.map((p) => ({ time: p.ts, value: d.anchored.vwap }))
            : []);
        const val = document.getElementById('vwapVal');
        if (val) val.textContent = `${vwapFmt(d.vwap)} (${d.ticks_from_vwap >= 0 ? '+' : ''}${d.ticks_from_vwap}t)`;
        const bands = document.getElementById('vwapBands');
        if (bands && d.bands && d.bands.length) {
            bands.textContent = `${vwapFmt(d.bands[0].upper)} / ${vwapFmt(d.bands[0].lower)}`;
        }
        const anc = document.getElementById('vwapAnchor');
        if (anc) anc.textContent = d.anchored && d.anchored.vwap
            ? `${vwapFmt(d.anchored.vwap)} (${d.anchored.minutes}m, ${d.anchored.prints} prints)`
            : 'not set';
    } catch (e) { /* a missing overlay must never break the chart */ }
}

/* ── trade detector panel (mounted under the intent card) ──────── */
function detectorEnsureCard() {
    if (document.getElementById('ddCard')) return;
    const target = document.getElementById('inCard');
    if (!target || !target.parentElement) return;
    vwapStyles();
    const card = document.createElement('div');
    card.className = 'card';
    card.id = 'ddCard';
    card.style.marginTop = '12px';
    card.innerHTML = `
        <div class="card-head"><span class="card-title">Depth executions</span>
            <span class="dim" id="ddSub" style="margin-left:8px"></span></div>
        <div class="card-body">
            <div class="dd-row" style="color:var(--dim)">
                <span class="dd-main">Prints that took a large share of the size resting at their price —
                someone ate a wall rather than picking off the inside. “Refilled” means the level came back
                within seconds, which is the closest a public feed gets to hidden size: an inference from
                behaviour, not an order id.</span></div>
            <div id="ddList"></div>
        </div>`;
    target.parentElement.insertBefore(card, target.nextSibling);
}

function detectorRender(list, refills, sub) {
    const box = document.getElementById('ddList');
    if (!box) return;
    const rows = (list || []).slice(0, 8);
    if (!rows.length) {
        box.innerHTML = '<div class="dd-row"><span class="dd-main dd-dim">nothing large has been eaten yet</span></div>';
    } else {
        box.innerHTML = rows.map((e) => {
            const t = new Date(e.ts_ms).toLocaleTimeString();
            const refill = refills && refills.some((r) => Math.abs(r.ts_ms - e.ts_ms) < 60000 && r.price === e.price);
            return `<div class="dd-row">
                <span class="dd-side ${e.side === 'buy' ? 'buy' : 'sell'}">${e.side}</span>
                <span class="dd-main">${vwapFmt(e.size)} @ ${vwapFmt(e.price)}
                    <span class="dd-dim">— took ${(e.share * 100).toFixed(0)}% of ${vwapFmt(e.resting)} resting</span></span>
                ${refill ? '<span class="dd-tag" title="The level refilled after being eaten — refreshed liquidity (inferred)">refilled</span>' : ''}
                <span class="dd-dim">${t}</span></div>`;
        }).join('');
    }
    const s = document.getElementById('ddSub');
    if (s) s.textContent = sub;
}

async function detectorRefresh() {
    detectorEnsureCard();
    const st = vwapState();
    if (!st || !st.symbol || !document.getElementById('ddList')) return;
    try {
        const d = await api(`/api/atlas/tradedepth/${st.symbol}?rows=20`);
        const key = `${d.version}|${(d.executions || []).length}|${(d.refills || []).length}`;
        if (key === VWAP_UI.detectorKey) return;
        VWAP_UI.detectorKey = key;
        detectorRender(d.executions, d.refills,
            `${vwapFmt(d.threshold)} min print · ${(d.min_share * 100).toFixed(0)}% of resting · level ≥${(d.resting_mult || 8)}× median print · ${(d.executions || []).length} eaten · ${(d.refills || []).length} refilled`);
    } catch (e) { /* silent: the panel is context, not a requirement */ }
}

/* ── loop ──────────────────────────────────────────────────────── */
(function vwapLoop() {
    setInterval(() => {
        try {
            const onChart = document.querySelector('.view[data-view="chart"]')?.classList.contains('active')
                || (document.querySelector('.view[data-view="chart"]') || {}).style?.display === 'flex';
            if (onChart || (vwapState() || {}).view === 'chart') vwapRefresh();
            if (document.getElementById('inCard')) detectorRefresh();
        } catch (e) { /* never let an overlay break the app */ }
    }, 5000);
    setTimeout(() => { vwapRefresh(); detectorRefresh(); }, 4000);
})();

/* ── the delta frame joins the Frames view's list (added at runtime: the
      select lives in index.html, which this module does not edit) ─────── */
(function addDeltaFrameOption() {
    let tries = 0;
    const tick = () => {
        tries += 1;
        const sel = document.getElementById('frameSelect');
        if (sel) {
            if (!sel.querySelector('option[value="delta"]')) {
                const opt = document.createElement('option');
                opt.value = 'delta';
                opt.textContent = 'Delta';
                opt.title = 'Bars built from cumulative delta: a bar closes when the delta inside it '
                    + 'passes the trend threshold or reverses from its extreme (the reference platform’s '
                    + 'Price-On-Volume idea). Effort, not time.';
                const volume = sel.querySelector('option[value="volume"]');
                sel.insertBefore(opt, volume ? volume.nextSibling : null);
            }
            return;
        }
        if (tries < 40) setTimeout(tick, 500);
    };
    tick();
})();
