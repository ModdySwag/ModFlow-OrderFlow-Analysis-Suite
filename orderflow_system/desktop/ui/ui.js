/* ══════════════════════════════════════════════════════════════════
   ModFlow OrderFlow Analysis Suite — desktop UI controller
   Talks to the repo's REST/WS API plus the new /api/control/* surface,
   and wires up the six UI modules the repo shipped but never loaded.
   ══════════════════════════════════════════════════════════════════ */

const S = {
    config: null,
    status: null,
    caps: null,
    system: null,
    symbol: null,
    ws: null,
    wsRetry: 1000,
    tf: 60,
    range: 86400,
    chart: null,
    candleSeries: null,
    deltaSeries: null,
    vpLines: [],
    inst: {},          // lazily created module instances
    signals: [],
    lastPrice: null,
    tickCount: 0,
    candleCount: 0,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? '--' : Number(v).toFixed(d);
const compact = (v) => {
    if (v === null || v === undefined) return '--';
    const a = Math.abs(v), s = v < 0 ? '-' : '';
    if (a >= 1e9) return s + (a / 1e9).toFixed(2) + 'B';
    if (a >= 1e6) return s + (a / 1e6).toFixed(2) + 'M';
    if (a >= 1e3) return s + (a / 1e3).toFixed(2) + 'K';
    return s + a.toFixed(2);
};
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function api(path, opts = {}) {
    const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
    return res.json();
}

function toast(el, text, kind = 'info') {
    if (!el) return;
    el.innerHTML = `<div class="banner ${kind}">${esc(text)}</div>`;
}
function clearToast(el) { if (el) el.innerHTML = ''; }

/* ── navigation ─────────────────────────────────────────────── */
function showView(name) {
    /* Unknown names used to walk into ensurePanel() and throw on a null element. A bad deep link
       should leave the UI where it is and say so, never take the panel system down. */
    if (!document.querySelector(`.view[data-view="${name}"]`)) {
        console.warn('showView: no view section for', name);
        return;
    }
    $$('.nav-item').forEach((b) => b.classList.toggle('active', b.dataset.view === name));
    $$('.view').forEach((v) => v.classList.toggle('active', v.dataset.view === name));
    if (location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
    ensurePanel(name);
    if (name === 'platforms' && typeof platformsInit === 'function') platformsInit();
    if (name === 'studies' && typeof studiesInit === 'function') studiesInit();
    if (name === 'chart') {
        ensureChart();
        loadChart();
        if (typeof studiesWireCrosshair === 'function') studiesWireCrosshair();
    }
}

/* "Open chart" / "Manage studies" jump between the two views that share the studies
   layer; one delegated listener covers every such button. */
document.addEventListener('click', (e) => {
    const jump = e.target && e.target.closest ? e.target.closest('[data-view-jump]') : null;
    if (jump) showView(jump.dataset.viewJump);
});

/* Alt+A jumps to the broker-account view. Ignored while typing, and while a
   modifier other than Alt is held, so it never fights Ctrl+A (select all). */
document.addEventListener('keydown', (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if ((e.key || '').toLowerCase() !== 'a') return;
    const act = document.activeElement || {};
    const tag = (act.tagName || '').toUpperCase();
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag) || act.isContentEditable) return;
    e.preventDefault();
    showView('alpaca');
});

/* ══════════════════════════════════════════════════════════════
   Boot
   ══════════════════════════════════════════════════════════════ */

async function boot() {
    try {
        const data = await api('/api/control/bootstrap');
        S.config = data.config;
        S.caps = data.capabilities;
        S.system = data.system;
        S.status = data.status;
    } catch (e) {
        $("#railPlatform").textContent = 'control API unavailable';
        console.error(e);
        return;
    }
    renderPlatform();
    renderSettings();
    renderInstruments();
    renderStatus();
    await refreshInstruments();
    connectWS();
    const deepLink = location.hash.slice(1);
    if (deepLink) showView(deepLink);
    const shells = $$('.view').length;
    if (!shells) {
        /* atlas-v2.js (which owns reportClientError) may load after this module — fall back. */
        const report = (typeof reportClientError === 'function') ? reportClientError : (d) => console.error(d.message);
        report({
            message: 'the view shell did not build: 0 .view sections in the document after boot',
            source: '/desktop/ui.js', line: 0, col: 0,
            stack: 'boot(): rail=' + $$('.rail .nav-item').length + ' views=0 config=' + !!S.config,
        });
    }
    /* One status read for the whole shell — and it is the SAME series the Watchlist panel watches,
       so the two share one bus channel instead of running a request stream each: measured 60
       requests a minute for /api/control/engine/status (30 from this poll, 30 from the panel's
       channel), 30 after. Pause stops the asking, not just the painting, so the shell leaves the
       channel while the board is parked; with no delivery layer loaded the timer below is exactly
       what ran before. */
    const startStatusPoll = () => {
        if (window.OFAPBUS && typeof window.OFAPBUS.subscribe === 'function') {
            if (!statusUnsubscribe) {
                statusUnsubscribe = window.OFAPBUS.subscribe(
                    { url: '/api/control/engine/status', intervalMs: STATUS_POLL_MS }, onStatusPayload);
            }
            return 0;
        }
        const id = setInterval(pollStatus, STATUS_POLL_MS);
        if (window.OFAPPause) window.OFAPPause.register(id, startStatusPoll);
        return id;
    };
    const stopStatusPoll = () => {
        if (statusUnsubscribe) {
            try { statusUnsubscribe(); } catch (e) { /* the delivery layer is gone; nothing to release */ }
            statusUnsubscribe = null;
        }
    };
    document.addEventListener('ofap:paused', (ev) => {
        if (ev && ev.detail && ev.detail.paused) stopStatusPoll();
        else startStatusPoll();
    });
    startStatusPoll();
    /* The delivery layer, adopted app-wide and without touching a single panel: any GET to these
       prefixes that another request is already in flight for is answered from that one request.
       Reading-heavy, idempotent endpoints only; nothing here changes what a panel receives, and
       with no bus loaded this line does nothing at all. */
    if (window.OFAPBUS && typeof window.OFAPBUS.install === 'function') {
        window.OFAPBUS.install(['/api/control/engine/status', '/api/status', '/api/atlas/', '/api/instruments']);
    }
    const startLogsPoll = () => {
        const id = setInterval(() => {
            if (window.OFAP_PAUSED || (window.OFAPINTENT && OFAPINTENT.anyHeld())) return;
            const logsView = $('.view[data-view="logs"]');
            const auto = $('#logAuto');
            if (logsView && auto && logsView.classList.contains('active') && auto.checked) loadLogs();
        }, 3000);
        if (window.OFAPPause) window.OFAPPause.register(id, startLogsPoll);
        return id;
    };
    startLogsPoll();
    setInterval(() => {
        /* Per-surface: a gesture on the heatmap must not stop the CVD panel refreshing, and none of
           them may repaint over the user's hands. Ingest is unaffected either way. */
        if (!S.symbol) return;
        if (window.OFAPINTENT && OFAPINTENT.anyHeld()) {
            OFAPINTENT.deferKeyed('panels', 'slow', refreshSlowPanels);
            return;
        }
        refreshSlowPanels();
    }, 5000);
}

function renderPlatform() {
    const p = S.system || {};
    $("#railPlatform").innerHTML = `${esc(p.platform_name || p.platform || '')}<br>python ${esc(p.python || '')}`;
    $("#logSub").textContent = p.log_path || '';
    $("#setSub").textContent = `stored in ${p.config_path || 'user config dir'} — no source edits`;
}

/* ══════════════════════════════════════════════════════════════
   Engine control
   ══════════════════════════════════════════════════════════════ */

function renderStatus() {
    const st = S.status || { state: 'stopped' };
    const pill = $("#enginePill");
    pill.className = 'pill ' + (st.state === 'running' ? 'running' : st.state === 'error' ? 'error' : st.state);
    $("#enginePillText").textContent =
        { stopped: 'Stopped', starting: 'Starting…', running: 'Running', stopping: 'Stopping…', error: 'Error' }[st.state] || st.state;
    $("#btnStart").classList.toggle('hidden', st.state === 'running' || st.state === 'starting');
    $("#btnStop").classList.toggle('hidden', !(st.state === 'running' || st.state === 'starting'));
    $("#btnStart").disabled = st.state === 'starting' || st.state === 'stopping';
    $("#sourcePill").textContent = 'source: ' + ((st.source || (S.config && S.config.data_source) || '--'));
    $("#ovSub").textContent = st.running
        ? `${st.source} · ${(st.symbols || []).join(', ')} · up ${Math.round(st.uptime_s)}s`
        : 'engine stopped — press Start';

    const banner = $("#ovBanner");
    if (st.state === 'error' && st.error) toast(banner, st.error, 'err');
    else if (!st.running) toast(banner, 'Engine is idle. Press “Start engine” to connect the data feed — the panels below will fill as ticks arrive.', 'info');
    else if ((st.skipped || []).length) {
        toast(banner, `Skipped instruments: ${st.skipped.map((s) => s.symbol).join(', ')} — ${st.skipped[0].reason}`, 'warn');
    } else clearToast(banner);
}

/** Refresh the "data:" chip — the single place that says live / warming / demo.
 *  The map comes from /api/control/live-status (engine.live_status()); every panel
 *  that can serve demo data reads its state from here instead of guessing. */
async function refreshLiveChip() {
    try {
        S.live = await api('/api/control/live-status');
    } catch (e) { /* keep the previous map on a hiccup */ }
    const el = $("#livePill");
    if (!el) return;
    const map = (S.live && S.live.endpoints) || {};
    const overall = (S.live && S.live.overall) || 'demo';
    el.className = 'pill ' + (overall === 'live' ? 'running' : overall === 'warming' ? '' : 'stopped');
    el.textContent = 'data: ' + overall;
    el.title = Object.entries(map).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'live/demo state per endpoint';
}

/** True when the given endpoint is demonstrably serving engine data right now. */
function panelIsLive(key) {
    return !!(S.live && S.live.endpoints && S.live.endpoints[key] === 'live');
}

/* The shell's own read of the engine status: 2 s, and the same (endpoint, params) the Watchlist
   panel watches — so both ride ONE shared channel instead of a request stream each (see boot). */
const STATUS_POLL_MS = 2000;
let statusUnsubscribe = null;

async function pollStatus() {
    /* Paused, or the user's hands are on a surface: skip the paint entirely. */
    if (window.OFAP_PAUSED || (window.OFAPINTENT && OFAPINTENT.anyHeld())) return;
    try {
        /* Through the delivery layer when it is loaded: a one-shot read, shared with whoever is
           asking at the same moment. The shell's repeating read is the channel below — this path is
           for the buttons, and for a page with no bus at all. */
        const payload = (window.OFAPBUS && typeof window.OFAPBUS.request === 'function')
            ? await window.OFAPBUS.request('/api/control/engine/status')
            : await api('/api/control/engine/status');
        await applyStatus(payload);
    } catch (e) { /* server busy — try again next tick */ }
}

/* Everything that happens once a status payload is in hand — whichever way it arrived: the shell's
   own read, or the channel it shares with the Watchlist panel. One body, so the two paths cannot
   drift in what they paint. */
async function applyStatus(payload) {
    if (!payload || typeof payload !== 'object') return false;
    const prev = S.status ? S.status.state : null;
    S.status = payload;
    /* "feed live" must be a measurement: the tick counter lives per symbol. */
    if (window.OFAPINTENT) {
        const total = (S.status.per_symbol || []).reduce((n, p) => n + (p.ticks || 0), 0);
        OFAPINTENT.setFeed({ ticks: total, live: !!S.status.running });
    }
    renderStatus();
    refreshLiveChip();
    renderOverviewTable();
    const first = (S.status.per_symbol || [])[0];
    if (first) {
        if (first.price) updatePriceKpis(first.price, null);
        updateDeltaKpi(first.cum_delta, 0);
        $("#kpiTicks").querySelector('.kpi-value').textContent = first.ticks;
        $("#kpiCandles").querySelector('.kpi-value').textContent = first.candles;
    }
    // A stopped dashboard serves demo payloads — refresh everything the moment
    // the engine comes up so no demo numbers are left on screen.
    if (prev !== 'running' && S.status.state === 'running') {
        await refreshInstruments();
        loadChart();
        loadFootprint();
        loadTape();
        renderThresholds();
    }
    return true;
}

/* A tick from the shared status channel. The channel is the delivery layer's — one timer, one
   in-flight request, shared with any other panel watching this endpoint — so a held surface or a
   paused board skips the paint here rather than stopping the ask (that is what stopStatusPoll is
   for: the shell leaves the channel entirely while it is parked). A failed fetch arrives on this
   path as data (`{error}`/`ok:false`), not as a rejection, and it must not be painted as a state. */
function onStatusPayload(payload) {
    if (window.OFAP_PAUSED) return;
    if (window.OFAPINTENT && OFAPINTENT.anyHeld()) return;
    if (!payload || typeof payload !== 'object' || !('state' in payload)) return;
    applyStatus(payload);
}

$("#btnStart").onclick = async () => {
    $("#btnStart").disabled = true;
    $("#btnStart").innerHTML = '<span class="spin"></span> starting…';
    try {
        const cfg = await collectSettings();
        const r = await api('/api/control/engine/start', { method: 'POST', body: cfg });
        if (!r.ok) toast($("#ovBanner"), r.error || 'Start failed', 'err');
    } catch (e) {
        toast($("#ovBanner"), String(e), 'err');
    }
    $("#btnStart").innerHTML = '▶ Start engine';
    pollStatus();
};

$("#btnStop").onclick = async () => {
    $("#btnStop").disabled = true;
    try { await api('/api/control/engine/stop', { method: 'POST' }); } catch (e) { console.error(e); }
    $("#btnStop").disabled = false;
    pollStatus();
};

$("#btnRestart").onclick = async () => {
    try {
        const cfg = await collectSettings();
        await api('/api/control/engine/restart', { method: 'POST', body: cfg });
    } catch (e) { toast($("#ovBanner"), String(e), 'err'); }
    pollStatus();
};

$("#btnRefreshStats").onclick = pollStatus;

/* ══════════════════════════════════════════════════════════════
   WebSocket
   ══════════════════════════════════════════════════════════════ */

function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    S.ws = ws;

    ws.onopen = () => {
        S.wsRetry = 1000;
        $("#wsPill").className = 'pill running';
        $("#wsPillText").textContent = 'WS live';
    };
    ws.onclose = () => {
        $("#wsPill").className = 'pill error';
        $("#wsPillText").textContent = 'WS retry…';
        setTimeout(connectWS, S.wsRetry);
        S.wsRetry = Math.min(S.wsRetry * 2, 15000);
    };
    ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        handleChannel(msg);
    };
}

function handleChannel(msg) {
    const { channel, symbol, data } = msg;
    if (symbol && S.symbol && symbol !== S.symbol) return;

    switch (channel) {
        case 'tick':
            S.lastPrice = data.price; S.tickCount++;
            updatePriceKpis(data.price, data.side);
            if (S.inst.tape && truthyView('tape')) S.inst.tape.addTrade({ time: Date.now(), price: data.price, size: data.size, side: data.side });
            break;
        case 'candle':
            S.candleCount++;
            if (S.candleSeries) S.candleSeries.update({ time: data.time, open: data.open, high: data.high, low: data.low, close: data.close });
            break;
        case 'delta':
            if (S.deltaSeries) S.deltaSeries.update({ time: data.time, value: data.value });
            updateDeltaKpi(data.value, data.bar_delta);
            break;
        case 'signal':
            S.signals.unshift(data);
            S.signals = S.signals.slice(0, 60);
            $("#navSignalCount").textContent = S.signals.length;
            renderOverviewSignals();
            if (S.inst.signals) S.inst.signals.addSignal(data);
            break;
        case 'orderbook':
            if (S.inst.book) S.inst.book.updatePrice(data.best_bid, 'buy');
            updateDepthKpis(data);
            break;
        case 'stats':
            renderOverviewTable();
            break;
        case 'search':
            // Batched palette rows (desktop/search_service.py → RowBatcher): one
            // message per window, already coalesced, so this never floods the UI.
            if (typeof searchApplyRows === 'function') searchApplyRows(data.rows);
            break;
        // reference-style detections (atlas package over the same socket)
        case 'alert':
        case 'big_trade':
        case 'block_trade':
        case 'sweep':
        case 'stop_run':
        case 'iceberg':
        case 'liquidation':
        case 'cvd_divergence':
        case 'speed_spike':
            if (typeof atlasOnEvent === 'function') atlasOnEvent(channel, data);
            break;
        default: break;
    }
}

const truthyView = (name) => {
    /* Pollers (steady, atlas-v2, the slow-panel refresh) ask whether a given view is on screen.
       A name with no section is a legitimate answer — "no" — not a null dereference: this threw
       from three different call sites before it was pinned by the client-error log. */
    const el = $('.view[data-view="' + name + '"]');
    return !!el && el.classList.contains('active');
};

function updatePriceKpis(price, side) {
    const k = $("#kpiPrice");
    k.querySelector('.kpi-value').textContent = fmt(price, price > 100 ? 2 : 4);
    k.querySelector('.kpi-sub').textContent = side ? side.toUpperCase() + ' print' : '';
    const c = $("#chPrice").querySelector('.kpi-value');
    if (c) c.textContent = fmt(price, price > 100 ? 2 : 4);
}
function updateDeltaKpi(cum, bar) {
    const k = $("#kpiDelta");
    k.querySelector('.kpi-value').textContent = compact(cum);
    k.querySelector('.kpi-sub').textContent = `bar ${compact(bar)}`;
    k.classList.toggle('up', cum > 0); k.classList.toggle('down', cum < 0);
    const c = $("#chDelta").querySelector('.kpi-value');
    if (c) c.textContent = compact(cum);
}
function updateDepthKpis(d) {
    $("#dpBid").querySelector('.kpi-value').textContent = fmt(d.best_bid, 4);
    $("#dpAsk").querySelector('.kpi-value').textContent = fmt(d.best_ask, 4);
    const imb = ((d.imbalance ?? 0) * 100);
    const k = $("#dpImb");
    k.querySelector('.kpi-value').textContent = fmt(imb, 1) + '%';
    k.querySelector('.kpi-sub').textContent = imb > 5 ? 'bid heavy' : imb < -5 ? 'ask heavy' : 'balanced';
    k.classList.toggle('up', imb > 0); k.classList.toggle('down', imb < 0);
    if (S.inst.book) {
        S.inst.book.updateLevel('bid', d.best_bid, 0);
        S.inst.book.updateLevel('ask', d.best_ask, 0);
        S.inst.book.updatePrice((d.best_bid + d.best_ask) / 2);
    }
}

/* ══════════════════════════════════════════════════════════════
   Instruments
   ══════════════════════════════════════════════════════════════ */

async function refreshInstruments() {
    // Only trust /api/instruments while the engine is live: when it is idle the
    // dashboard endpoint answers with its demo instrument list.
    let list = [];
    if (S.status && S.status.running) {
        try { list = await api('/api/instruments'); } catch { list = []; }
    }
    const sel = $("#symbolSelect");
    const enabled = (S.config.instruments || []).filter((i) => i.enabled).map((i) => i.symbol);
    const live = Array.isArray(list) ? list.map((i) => i.symbol) : [];
    const options = live.length ? live : enabled;
    sel.innerHTML = options.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join('') || '<option value="">no instruments enabled</option>';
    if (!S.symbol && options.length) { S.symbol = options[0]; }
    if (S.symbol && options.includes(S.symbol)) sel.value = S.symbol;
    $("#navSignalCount").textContent = String(S.signals.length);
}

$("#symbolSelect").onchange = (e) => {
    S.symbol = e.target.value;
    S.signals = [];
    $("#navSignalCount").textContent = '0';
    refreshAllPanels(true);
};

/* ══════════════════════════════════════════════════════════════
   Overview
   ══════════════════════════════════════════════════════════════ */

function renderOverviewTable() {
    const rows = (S.status && S.status.per_symbol) || [];
    const body = $("#ovTable tbody");
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="6" class="dim">Engine stopped — no live instruments.</td></tr>';
        return;
    }
    body.innerHTML = rows.map((r) => `<tr>
        <td class="name">${esc(r.symbol)}</td>
        <td>${fmt(r.price, r.price > 100 ? 2 : 4)}</td>
        <td>${r.ticks}</td><td>${r.candles}</td>
        <td class="${r.cum_delta > 0 ? 'tag ok' : r.cum_delta < 0 ? 'tag no' : ''}">${compact(r.cum_delta)}</td>
        <td class="name">${esc(r.trade_phase)}</td></tr>`).join('');
    const first = rows[0];
    $("#kpiTicks").querySelector('.kpi-value').textContent = first.ticks;
    $("#kpiCandles").querySelector('.kpi-value').textContent = first.candles;
}

function renderOverviewSignals() {
    const box = $("#ovSignals");
    if (!S.signals.length) { box.innerHTML = '<div class="dim">No signals yet.</div>'; return; }
    box.innerHTML = S.signals.slice(0, 8).map((s) => {
        const dir = (s.direction || '').toString().toLowerCase();
        return `<div class="signal-card" style="margin-bottom:8px">
            <div class="signal-header"><span class="signal-symbol">${esc(s.symbol || S.symbol)}</span>
            <span class="${dir === 'buy' ? 'bullish' : 'bearish'}">${esc((s.direction || '').toUpperCase())}</span>
            <span class="signal-grade">${esc(s.grade || s.action || '')}</span></div>
            <div class="dim">${esc(s.narrative || s.thesis || s.reason || '')}</div>
        </div>`;
    }).join('');
}

/* ══════════════════════════════════════════════════════════════
   Chart
   ══════════════════════════════════════════════════════════════ */

function ensureChart() {
    if (S.chart) return;
    const el = $("#chart");
    if (!el.clientWidth) return;
    S.chart = LightweightCharts.createChart(el, {
        layout: { background: { color: '#131b2a' }, textColor: '#9aa9c1', fontFamily: 'system-ui' },
        grid: { vertLines: { color: 'rgba(34,48,73,.55)' }, horzLines: { color: 'rgba(34,48,73,.55)' } },
        rightPriceScale: { borderColor: '#223049' },
        timeScale: { borderColor: '#223049', timeVisible: true, secondsVisible: false },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        autoSize: true,
    });
    S.candleSeries = S.chart.addCandlestickSeries({
        upColor: '#35d07f', downColor: '#ff5d6c', borderUpColor: '#35d07f',
        borderDownColor: '#ff5d6c', wickUpColor: '#35d07f', wickDownColor: '#ff5d6c',
    });
    S.deltaSeries = S.chart.addHistogramSeries({
        priceFormat: { type: 'volume' }, priceScaleId: 'delta', color: '#4f8cff',
    });
    S.chart.priceScale('delta').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
}

async function fetchVolumeProfile(sym) {
    // The live endpoint returns a LIST of session profiles; the demo path returns
    // a single object. Normalise to the newest profile (or null).
    const raw = await api(`/api/volume-profile/${sym}`).catch(() => null);
    if (Array.isArray(raw)) return raw.length ? raw[raw.length - 1] : null;
    return raw || null;
}

async function loadChart() {
    ensureChart();
    if (!S.chart || !S.symbol) return;
    $("#chartStatus").textContent = 'loading…';
    const sym = encodeURIComponent(S.symbol);
    const notes = [];
    try {
        const [candles, delta, vp, bias] = await Promise.all([
            api(`/api/candles/${sym}?tf=${S.tf}&range=${S.range}`),
            api(`/api/delta/${sym}?tf=${S.tf}&range=${S.range}`),
            fetchVolumeProfile(sym),
            api(`/api/bias/${sym}`).catch(() => null),
        ]);
        const bars = Array.isArray(candles) ? candles : [];
        S.lastBars = bars;                       // the studies layer runs on the same bars
        S.candleSeries.setData(bars.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
        const d = Array.isArray(delta) ? delta : [];
        // The studies layer runs on the same bars, and the chart already fetched the
        // per-bar delta series: attaching it here is what lets a study read d.delta()
        // instead of re-fetching it (or worse, guessing it).
        const deltaByTime = new Map(d.map((x) => [x.time, x.bar_delta ?? x.value]));
        bars.forEach((bar) => {
            if (deltaByTime.has(bar.time)) bar.bar_delta = deltaByTime.get(bar.time);
        });
        S.deltaSeries.setData(d.map((x) => ({ time: x.time, value: x.bar_delta ?? x.value, color: (x.bar_delta ?? x.value) >= 0 ? 'rgba(53,208,127,.55)' : 'rgba(255,93,108,.55)' })));

        // Markers are optional: the endpoint 500s in the stock repo
        // (NameError: Side — dashboard/app.py:256), so never let it kill the chart.
        if ($("#ovMarkers").checked) {
            try {
                const markers = await api(`/api/markers/${sym}?limit=300`);
                // Held rather than applied: the studies layer merges these with its own
                // signal markers and is the single writer of the candle series' markers.
                S.baseMarkers = (Array.isArray(markers) ? markers : []).map((m) => ({
                    time: m.time, position: m.position || (m.side === 'buy' ? 'belowBar' : 'aboveBar'),
                    color: m.color || (m.side === 'buy' ? '#35d07f' : '#ff5d6c'),
                    shape: m.shape || (m.side === 'buy' ? 'arrowUp' : 'arrowDown'),
                    text: (m.label || m.pattern || '').slice(0, 22),
                })).filter((m) => m.time);
            } catch (e) {
                S.baseMarkers = [];
                notes.push('markers unavailable (/api/markers errors in live mode)');
            }
        } else S.baseMarkers = [];

        applyVpLines(vp);
        renderChartKpis(vp, bias, bars);
        // Studies draw over the freshly loaded bars (and repaint the candles when a study
        // colours them). Guarded: the module is injected asynchronously.
        if (typeof studiesApply === 'function') studiesApply();
        else if (S.candleSeries) S.candleSeries.setMarkers((S.baseMarkers || []).slice(-300));
        $("#chartStatus").textContent = `${bars.length} bars · ${d.length} delta points${notes.length ? ' · ' + notes.join(' · ') : ''}`;
    } catch (e) {
        $("#chartStatus").textContent = String(e);
    }
}

function applyVpLines(vp) {
    if (!S.chart) return;
    S.vpLines.forEach((l) => { try { S.candleSeries.removePriceLine(l); } catch {} });
    S.vpLines = [];
    if (!$("#ovVP").checked || !vp || !vp.poc) return;
    const mk = (price, color, title) => S.candleSeries.createPriceLine({
        price, color, lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true, title,
    });
    S.vpLines.push(mk(vp.poc, '#4f8cff', 'POC'));
    if (vp.vah) S.vpLines.push(mk(vp.vah, 'rgba(53,208,127,.8)', 'VAH'));
    if (vp.val) S.vpLines.push(mk(vp.val, 'rgba(255,93,108,.8)', 'VAL'));
}

function renderChartKpis(vp, bias, bars) {
    const last = bars.length ? bars[bars.length - 1].close : null;
    $("#chPrice").querySelector('.kpi-value').textContent = fmt(last, last > 100 ? 2 : 4);
    if (vp) {
        $("#chPoc").querySelector('.kpi-value').textContent = fmt(vp.poc, 2);
        $("#chPoc").querySelector('.kpi-sub').textContent = vp.shape ? `shape: ${vp.shape}` : '';
    }
    if (bias) {
        const dir = (bias.direction || '').toString().toLowerCase();
        $("#chBias").querySelector('.kpi-value').textContent = (bias.direction || '--').toString().toUpperCase();
        $("#chBias").querySelector('.kpi-sub').textContent = bias.confidence ? `${Math.round(bias.confidence)}% confidence` : '';
        $("#chBias").classList.toggle('up', dir.includes('bull') || dir === 'buy' || dir === 'long');
        $("#chBias").classList.toggle('down', dir.includes('bear') || dir === 'sell' || dir === 'short');
    }
}

$("#tfSelect").onchange = (e) => { S.tf = +e.target.value; loadChart(); };
$("#rangeSelect").onchange = (e) => { S.range = +e.target.value; loadChart(); };
$("#ovMarkers").onchange = loadChart;
$("#ovVP").onchange = () => loadChart();

/* ══════════════════════════════════════════════════════════════
   Order flow · depth · tape · signals · performance · micro
   (the repo's own modules, finally loaded)
   ══════════════════════════════════════════════════════════════ */

/* ── the Numbers-Bars pack: convention, ratio and the calculated row ─────────
   The mode/threshold are analytic choices, so they follow the user across symbols and
   restarts (they live in the config's atlas.footprint block), and the server computes the
   pack — the UI never re-derives an imbalance the chart is not showing. */
function footprintSettings() {
    const fp = ((S.config || {}).atlas || {}).footprint || {};
    return { mode: fp.imbalance_mode === 'diagonal' ? 'diagonal' : 'same_price',
             threshold: Number(fp.imbalance_threshold) || 3,
             equal_tolerance: Number(fp.equal_tolerance) || 0 };
}

function renderFootprintCalc(bars) {
    const out = document.getElementById('ofCalc');
    if (!out) return;
    const last = bars && bars.length ? bars[bars.length - 1] : null;
    const calc = last && last.calc;
    if (!calc) { out.textContent = 'calc: --'; return; }
    const imb = calc.imbalance_counts || { buy: 0, sell: 0 };
    const delta = Number(calc.delta || 0);
    const poc = calc.poc ? `${calc.poc.price} (${calc.poc.share_pct}%)` : '--';
    out.innerHTML = `delta <b class="${delta >= 0 ? 'up' : 'down'}">${delta >= 0 ? '+' : ''}${delta.toFixed(2)}</b>`
        + ` · POC ${poc} · imbalance ${imb.buy}/${imb.sell}`
        + ` · ${calc.mode === 'diagonal' ? 'diagonal' : 'same-price'}`;
    out.title = `Numbers-Bars pack for the last bar: volume ${calc.volume}, buy ${calc.buy}, sell ${calc.sell}, `
        + `extremes ${calc.extremes && calc.extremes.min ? calc.extremes.min.price : '--'}–`
        + `${calc.extremes && calc.extremes.max ? calc.extremes.max.price : '--'}`;
}

async function saveFootprintSettings(change) {
    const fp = { ...footprintSettings(), ...change };
    try {
        await api('/api/control/atlas/footprint', { method: 'POST', body: fp });
        S.config = S.config || {};
        S.config.atlas = S.config.atlas || {};
        S.config.atlas.footprint = { ...(S.config.atlas.footprint || {}), ...fp };
        await loadFootprint();
    } catch (err) {
        const out = document.getElementById('ofCalc');
        if (out) out.textContent = 'calc: ' + String(err);
    }
}

function wireFootprintControls() {
    const mode = document.getElementById('ofImbMode');
    const thresh = document.getElementById('ofImbThresh');
    if (mode) mode.onchange = () => saveFootprintSettings({ imbalance_mode: mode.value });
    if (thresh) thresh.onchange = () => {
        const value = Math.min(50, Math.max(1, Number(thresh.value) || 3));
        thresh.value = String(value);
        saveFootprintSettings({ imbalance_threshold: value });
    };
    const fp = footprintSettings();
    if (mode) mode.value = fp.mode;
    if (thresh) thresh.value = String(fp.threshold);
}

function ensurePanel(name) {
    if (!S.symbol) return;
    const make = {
        orderflow: () => {
            if (S.inst.footprint || !window.FootprintChart || !$("#footprintChart").clientWidth) return;
            S.inst.footprint = new FootprintChart('footprintChart', {});
            wireFootprintControls();
            loadFootprint();
        },
        depth: () => {
            if (S.inst.book || !window.OrderbookLadder || !$("#orderbookLadder").clientWidth) return;
            S.inst.book = new OrderbookLadder('orderbookLadder', { levels: 15 });
            loadOrderbook();
        },
        tape: () => {
            if (S.inst.tape || !window.TimeAndSales || !$("#tapeContainer").clientWidth) return;
            S.inst.tape = new TimeAndSales('tapeContainer', {});
            loadTape();
        },
        signals: () => {
            if (S.inst.signals || !window.SignalCards || !$("#signalsContainer").clientWidth) return;
            S.inst.signals = new SignalCards('signalsContainer', {});
            S.inst.signals.setSignals(S.signals);
            loadSignals();
        },
        performance: () => {
            if (S.inst.perf || !window.PerformanceDashboard || !$("#perfDashboard").clientWidth) return;
            S.inst.perf = new PerformanceDashboard('perfDashboard', {});
            loadPerformance();
        },
        strategy: () => {
            if (S.inst.micro || !window.MicrostructurePanel || !$("#microPanel").clientWidth) return;
            S.inst.micro = new MicrostructurePanel('microPanel', {});
            loadStrategy();
        },
        chart: () => { ensureChart(); loadChart(); },
        overview: () => { renderOverviewTable(); renderOverviewSignals(); },
        heatmap: () => { loadHeatmap(); },
        trackers: () => { loadTrackers(); },
        cvd: () => { loadCvd(); },
        profile: () => { loadMarketProfile(); },
        frames: () => { loadFrames(); },
        replay: () => { rpStatus(); },
        alerts: () => { loadAlerts(true); },
        instruments: () => renderInstruments(),
        alpaca: () => {
            if (typeof alpViewRender === 'function') alpViewRender();
            else if (typeof alpacaLoad === 'function') alpacaLoad(true);
        },
        settings: () => renderSettings(),
        logs: () => loadLogs(),
    };
    if (make[name]) setTimeout(make[name], 30);
}

/* Footprint fetches overlap (the panel refresh timer plus a settings change), and the
   older response can land last — which showed the previous convention's numbers under the
   new toggle. Requests are sequenced; only the newest answer is allowed to render. */
let footprintSeq = 0;

async function loadFootprint() {
    if (!S.inst.footprint || !S.symbol) return;
    const seq = ++footprintSeq;
    try {
        const fp = footprintSettings();
        const qs = `tf=${S.tf}&range=${S.range}&mode=${encodeURIComponent(fp.mode)}`
            + `&threshold=${encodeURIComponent(fp.threshold)}`;
        const data = await api(`/api/footprint/${encodeURIComponent(S.symbol)}?${qs}`);
        if (seq !== footprintSeq) return;              // superseded: a newer request is in flight
        const bars = Array.isArray(data) ? data : [];
        S.inst.footprint.setData(bars);
        renderFootprintCalc(bars);
    } catch (e) { console.error(e); }
    // Only warn while this panel is actually on demo fill — the "data:" chip in the
    // status bar carries the full per-endpoint live/warming/demo map.
    if (!panelIsLive('footprint')) {
        toast($("#ofBanner"),
            'Footprint is showing illustrative demo data until the engine closes its first bar for this symbol — the “data:” chip in the status bar lists what is live.',
            'warn');
    } else clearToast($("#ofBanner"));
    try {
        const vp = await fetchVolumeProfile(S.symbol);
        $("#ofPoc").querySelector('.kpi-value').textContent = fmt(vp && vp.poc);
        $("#ofVah").querySelector('.kpi-value').textContent = fmt(vp && vp.vah);
        $("#ofVal").querySelector('.kpi-value').textContent = fmt(vp && vp.val);
        $("#ofShape").querySelector('.kpi-value').textContent = (vp && vp.shape) || '--';
        $("#ofShape").querySelector('.kpi-sub').textContent = vp && vp.total_volume ? `vol ${compact(vp.total_volume)}` : '';
    } catch (e) { /* ignore */ }
    try {
        const st = await api('/api/control/profiles/status');
        const row = (st.symbols || []).find((r) => r.symbol === S.symbol);
        $("#ofProfileStatus").textContent = row
            ? `profile: ${row.profiles} built · bias ${row.bias || '--'} · ${row.qualified_levels} levels`
            : 'profile: --';
    } catch (e) { /* engine stopped */ }
}

$("#btnRebuildProfile").onclick = async () => {
    const btn = $("#btnRebuildProfile");
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> rebuilding…';
    try {
        const r = await api('/api/control/profiles/rebuild', { method: 'POST' });
        if (!r.ok) toast($("#ofBanner"), r.error, 'warn');
        else {
            const row = (r.results || []).find((x) => x.symbol === S.symbol) || {};
            toast($("#ofBanner"),
                row.created
                    ? `Profile rebuilt from ${row.candles} candles — POC/VAH/VAL updated.`
                    : `Nothing to build yet: ${row.candles || 0} candles stored${row.detail ? ' — ' + row.detail : ''}. Let the engine run, or use the MT5 history download.`,
                row.created ? 'ok' : 'warn');
        }
    } catch (e) { toast($("#ofBanner"), String(e), 'err'); }
    btn.disabled = false; btn.textContent = 'Rebuild profile';
    loadFootprint();
};

async function loadOrderbook() {
    if (!S.inst.book || !S.symbol) return;
    try {
        const data = await api(`/api/orderbook/${encodeURIComponent(S.symbol)}?levels=15`);
        S.inst.book.setData(data);
        updateDepthKpis(data);
    } catch (e) { console.error(e); }
}

async function loadTape() {
    if (!S.inst.tape || !S.symbol) return;
    if (!panelIsLive('tape')) {
        toast($("#tapeBanner"),
            'Initial tape fill is demo data until the engine has streamed prints for this symbol — new prints over the WebSocket are always real. See the “data:” chip in the status bar.',
            'warn');
    } else clearToast($("#tapeBanner"));
    try {
        const data = await api(`/api/tape/${encodeURIComponent(S.symbol)}?count=120`);
        S.inst.tape.addTrades(Array.isArray(data) ? data : []);
    } catch (e) { console.error(e); }
}

async function loadSignals() {
    if (!S.symbol) return;
    try {
        const data = await api(`/api/signals/${encodeURIComponent(S.symbol)}?limit=50`);
        S.signals = Array.isArray(data) ? data : [];
        $("#navSignalCount").textContent = S.signals.length;
        if (S.inst.signals) S.inst.signals.setSignals(S.signals);
        renderOverviewSignals();
    } catch (e) { console.error(e); }
}

async function loadStrategy() {
    if (!S.symbol) return;
    try {
        const d = await api(`/api/strategy-status/${encodeURIComponent(S.symbol)}`);
        $("#strategySteps").innerHTML = (d.steps || []).map((s) => `
            <div class="step ${esc(s.status || 'inactive')}">
                <div class="step-icon">${s.icon || '•'}</div>
                <div style="flex:1">
                    <div class="step-name">${esc(s.name)}</div>
                    <div class="step-detail">${esc(s.detail || '')}</div>
                    ${(s.sub || []).length ? `<div class="step-sub">${s.sub.map((x) => `<span>${esc(x)}</span>`).join('')}</div>` : ''}
                </div>
            </div>`).join('') || '<div class="dim">No strategy state.</div>';
    } catch (e) { console.error(e); }

    if (S.inst.micro) {
        try {
            const micro = await api(`/api/microstructure/${encodeURIComponent(S.symbol)}`);
            const stat = (S.status && (S.status.per_symbol || []).find((p) => p.symbol === S.symbol)) || {};
            S.inst.micro.update({
                ...micro,
                delta: { cumulative: stat.cum_delta ?? (micro.delta && micro.delta.cumulative) ?? 0, direction: 0, divergence: false },
            });
        } catch (e) { console.error(e); }
    }
}

async function loadPerformance() {
    if (!S.inst.perf || !S.symbol) return;
    try {
        const sigs = await api(`/api/signals/${encodeURIComponent(S.symbol)}?limit=100`);
        const trades = (Array.isArray(sigs) ? sigs : []).map((s, i) => ({
            id: i, timestamp: (s.timestamp_ms || Date.now()), symbol: s.symbol || S.symbol,
            direction: s.direction, pattern: s.pattern || s.primary_pattern || 'signal',
            pnl: s.pnl || 0, rr: s.rr || s.rr_ratio || 0, grade: s.grade || '', result: s.result || '',
        }));
        S.inst.perf.setTrades(trades);
    } catch (e) { console.error(e); }
}

/* ══════════════════════════════════════════════════════════════
   Instrument coverage table
   ══════════════════════════════════════════════════════════════ */

function renderInstruments() {
    const tbody = $("#instTable tbody");
    const bybit = (S.caps && S.caps.bybit_symbols) || {};
    const mt5ok = S.caps && S.caps.mt5 && S.caps.mt5.available;
    tbody.innerHTML = (S.config.instruments || []).map((i) => {
        const supported = (S.config.data_source === 'mt5') ? (mt5ok && !!i.mt5_symbol)
            : (S.config.data_source === 'both') ? (bybit[i.symbol] || (mt5ok && !!i.mt5_symbol))
            : (i.symbol in bybit ? bybit[i.symbol] : bybit[i.symbol] !== false);
        return `<tr data-symbol="${esc(i.symbol)}">
            <td><label class="switch"><input type="checkbox" data-role="enabled" ${i.enabled ? 'checked' : ''}></label></td>
            <td class="name">${esc(i.symbol)}</td>
            <td class="name">${esc(i.asset_class || '')}</td>
            <td>${esc(i.mt5_symbol || '—')}</td>
            <td>${bybit[i.symbol] ? '<span class="tag ok">listed</span>' : '<span class="tag no">n/a</span>'}</td>
            <td><input type="number" step="0.0001" style="width:90px" data-role="tick" value="${esc(i.tick_size)}"></td>
        </tr>`;
    }).join('');

    const banner = $("#instBanner");
    const mt5 = S.caps && S.caps.mt5;
    if (S.config.data_source === 'mt5' && mt5 && !mt5.available) {
        toast(banner, 'MT5 selected but unavailable here: ' + mt5.reason, 'warn');
    } else if (S.config.data_source === 'bybit') {
        const n = Object.values(bybit).filter(Boolean).length;
        toast(banner, `Bybit serves ${n} of ${Object.keys(bybit).length} configured instruments (crypto only). Non-crypto instruments need MetaTrader 5 on Windows.`, 'info');
    } else clearToast(banner);
}

function collectInstruments() {
    const rows = $$('#instTable tbody tr');
    return rows.map((tr) => {
        const spec = (S.config.instruments || []).find((i) => i.symbol === tr.dataset.symbol) || {};
        return {
            ...spec,
            symbol: tr.dataset.symbol,
            enabled: tr.querySelector('[data-role="enabled"]').checked,
            tick_size: parseFloat(tr.querySelector('[data-role="tick"]').value) || spec.tick_size || 0.1,
        };
    });
}

$("#btnValidate").onclick = async () => {
    const btn = $("#btnValidate");
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> checking Bybit…';
    try {
        S.caps = await api('/api/control/capabilities?refresh=true');
        renderInstruments();
    } catch (e) { toast($("#instBanner"), String(e), 'err'); }
    btn.disabled = false; btn.textContent = 'Validate against Bybit';
};

$("#btnEnableCrypto").onclick = () => {
    const bybit = (S.caps && S.caps.bybit_symbols) || {};
    $$('#instTable tbody tr').forEach((tr) => {
        const on = S.config.data_source === 'bybit'
            ? (tr.querySelector('[data-role="enabled"]').checked = !!bybit[tr.dataset.symbol])
            : true;
        if (on === undefined) tr.querySelector('[data-role="enabled"]').checked = true;
    });
};
$("#btnDisableAll").onclick = () => $$('#instTable tbody tr').forEach((tr) => (tr.querySelector('[data-role="enabled"]').checked = false));

/* ══════════════════════════════════════════════════════════════
   Settings
   ══════════════════════════════════════════════════════════════ */

const PATTERN_FIELDS = {
    absorption: ['min_aggressive_volume', 'max_price_displacement_ticks', 'min_attempts'],
    initiative: ['min_delta_threshold', 'volume_acceleration_min', 'min_price_displacement_ticks'],
    sweep: ['min_levels_swept', 'thin_book_threshold'],
    exhaustion: ['min_bars_declining', 'volume_decline_pct'],
    divergence: ['lookback_bars', 'delta_failure_pct'],
};

function renderSettings() {
    const c = S.config;
    $("#setSource").value = c.data_source;
    $("#setCooldown").value = c.risk.signal_cooldown_seconds;
    $("#setScore").value = c.risk.min_composite_score;
    $("#setLogLevel").value = c.logging.level;
    $("#setTgToken").value = c.telegram.bot_token || '';
    $("#setTgChat").value = c.telegram.chat_id || '';
    const tg = $("#tgPill");
    const on = !!(c.telegram.bot_token && c.telegram.chat_id);
    tg.className = 'pill ' + (on ? 'running' : '');
    $("#tgPillText").textContent = on ? 'configured' : 'not configured';
    const mt5 = S.caps && S.caps.mt5;
    $("#sourceHint").textContent = mt5 && !mt5.available ? `MT5 unavailable here — ${mt5.reason}` : 'MT5 bridge ready';
    renderThresholds();
}

function renderThresholds() {
    const sym = S.symbol;
    const inst = (S.config.instruments || []).find((i) => i.symbol === sym);
    if (typeof renderAtlasSettings === 'function') renderAtlasSettings();
    $("#patTarget").innerHTML = sym ? `editing ${INST_LABEL(sym)}` : 'select an instrument';
    const grid = $("#patGrid");
    if (!inst) { grid.innerHTML = '<div class="dim">Enable an instrument first.</div>'; return; }
    grid.innerHTML = Object.entries(PATTERN_FIELDS).map(([pat, fields]) => `
        <div class="card" style="margin:0"><div class="card-head"><span class="card-title">${pat}</span></div>
        <div class="card-body">${fields.map((f) => `
            <div class="field"><label>${f.replace(/_/g, ' ')}</label>
            <input type="number" step="0.1" data-pat="${pat}" data-key="${f}" value="${esc(inst.patterns[pat][f])}"></div>`).join('')}</div></div>
    `).join('');
    toast($("#patBanner"), `Thresholds below apply to ${INST_LABEL(sym)} only — switch instrument in the top bar to edit another.`, 'info');
}
const INST_LABEL = (s) => `<span class="mono">${esc(s)}</span>`;

function collectThresholds() {
    const sym = S.symbol;
    const inst = (S.config.instruments || []).find((i) => i.symbol === sym);
    if (!inst) return;
    $$('#patGrid input[data-pat]').forEach((inp) => {
        const pat = inp.dataset.pat, key = inp.dataset.key;
        const v = parseFloat(inp.value);
        if (!Number.isNaN(v)) inst.patterns[pat][key] = v;
    });
}

async function collectSettings() {
    collectThresholds();
    const cfg = JSON.parse(JSON.stringify(S.config));
    cfg.data_source = $("#setSource").value;
    cfg.risk.signal_cooldown_seconds = parseFloat($("#setCooldown").value) || 30;
    cfg.risk.min_composite_score = parseFloat($("#setScore").value) || 40;
    cfg.logging.level = $("#setLogLevel").value;
    cfg.telegram.bot_token = $("#setTgToken").value.trim();
    cfg.telegram.chat_id = $("#setTgChat").value.trim();
    cfg.instruments = collectInstruments();
    if (typeof collectAtlasSettings === 'function') collectAtlasSettings(cfg);
    return cfg;
}

async function saveSettings(restart = false) {
    const out = $("#saveResult");
    out.textContent = 'saving…';
    try {
        const cfg = await collectSettings();
        const r = await api('/api/control/config', { method: 'POST', body: cfg });
        S.config = r.config;
        renderInstruments(); renderSettings();
        out.textContent = `saved → ${r.config_path}`;
        if (restart) await api('/api/control/engine/restart', { method: 'POST', body: S.config });
        pollStatus();
    } catch (e) { out.textContent = String(e); }
}

$("#btnSaveSettings").onclick = () => saveSettings(false);
$("#btnSaveRestart").onclick = () => saveSettings(true);
$("#btnReloadSettings").onclick = async () => {
    const d = await api('/api/control/bootstrap');
    S.config = d.config; S.caps = d.capabilities; S.status = d.status;
    renderSettings(); renderInstruments(); renderStatus();
};
$("#btnResetSettings").onclick = async () => {
    const r = await api('/api/control/config/reset', { method: 'POST' });
    S.config = r.config; renderSettings(); renderInstruments();
    $("#saveResult").textContent = 'reset to defaults';
};

$("#btnTgTest").onclick = async () => {
    const out = $("#tgTestResult");
    out.textContent = 'sending…';
    try {
        const r = await api('/api/control/telegram/test', {
            method: 'POST',
            body: { bot_token: $("#setTgToken").value.trim(), chat_id: $("#setTgChat").value.trim() },
        });
        out.textContent = r.ok ? `sent (bot ${r.bot})` : `failed: ${r.error}`;
    } catch (e) { out.textContent = String(e); }
};

/* ══════════════════════════════════════════════════════════════
   Logs
   ══════════════════════════════════════════════════════════════ */

async function loadLogs() {
    try {
        const lvl = $("#logLevel").value;
        const d = await api(`/api/control/logs?lines=300${lvl ? '&level=' + lvl : ''}`);
        const box = $("#logList");
        if (!d.lines.length) { box.innerHTML = '<div class="dim">No log lines yet.</div>'; return; }
        const at = () => box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
        const stick = at();
        box.innerHTML = d.lines.map((l) => `<div class="log-line"><span class="log-time">${new Date(l.t * 1000).toLocaleTimeString()}</span>
            <span class="log-lvl ${esc(l.level)}">${esc(l.level)}</span><span>${esc(l.msg)}</span></div>`).join('');
        if (stick) box.scrollTop = box.scrollHeight;
    } catch (e) { /* ignore */ }
}
$("#logLevel").onchange = loadLogs;
$("#btnLogClear").onclick = async () => { await api('/api/control/logs/clear', { method: 'POST' }); loadLogs(); };

/* ══════════════════════════════════════════════════════════════
   Panel refresh orchestration
   ══════════════════════════════════════════════════════════════ */

async function refreshAllPanels(resetChart = false) {
    await refreshInstruments();
    renderThresholds();
    if (truthyView('chart') || resetChart) loadChart();
    if (S.inst.footprint) { wireFootprintControls(); loadFootprint(); }
    if (S.inst.book) loadOrderbook();
    if (S.inst.tape) loadTape();
    if (S.inst.perf) loadPerformance();
    loadStrategy();
    loadSignals();
}

function refreshSlowPanels() {
    if (truthyView('orderflow')) loadFootprint();
    if (truthyView('depth')) loadOrderbook();
    if (truthyView('tape')) loadTape();
    if (truthyView('strategy')) loadStrategy();
    if (truthyView('performance')) loadPerformance();
    if (typeof atlasSlowRefresh === 'function') atlasSlowRefresh();
}

$$('.nav-item').forEach((b) => (b.onclick = () => showView(b.dataset.view)));
window.addEventListener('resize', () => { S.vpLines = S.vpLines; });
document.addEventListener('DOMContentLoaded', boot);
