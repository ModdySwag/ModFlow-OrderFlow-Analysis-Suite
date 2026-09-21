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
    /* P1-8: how this chart expresses its bars, and the colours the theme pair stands for here.
       The mode and palette come from the config block (`expression.chart`). */
    expr: { mode: 'default', palette: 'theme', loaded: false },
    lastDelta: [],        // the delta series in hand, so a display change recolours without a fetch
    exprTheme: { pos: '53,208,127', neg: '255,93,108' },
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? '—' : Number(v).toFixed(d);
const compact = (v) => {
    if (v === null || v === undefined) return '—';
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

function toast(el, text, kind = 'info', topic = '') {
    if (!el) return;
    /* A notice aimed at <body> gets its OWN fixed strip, never the page: assigning innerHTML to the
       body REPLACES every view with the banner — measured live, where one client error (a colour
       the chart vendor refused) left a dead window behind a red banner. Call sites that address the
       body all mean "say this", so the routing lives here, once, for every future caller too. */
    if (el === document.body) {
        let strip = document.getElementById('noticeStrip');
        if (!strip) {
            strip = document.createElement('div');
            strip.id = 'noticeStrip';
            document.body.appendChild(strip);
        }
        el = strip;
    }
    el.innerHTML = `<div class="banner ${kind}">${esc(text)}${topic && window.OFAPHELP
        ? ` <span class="toast-topic" data-topic="${esc(topic)}" role="link" tabindex="0" title="Open this in the Help Centre" style="text-decoration:underline;cursor:pointer">Help \u2192</span>`
        : ''}</div>`;
}
function clearToast(el) { if (el) el.innerHTML = ''; }
/* The Help \u2192 door a toast can carry (engine faults, skipped instruments, save failures).
   One delegated click on the document: every toast() call replaces a banner wholesale, so a
   listener attached per-banner would be orphaned by the next message. */
if (typeof document !== 'undefined') {
    document.addEventListener('click', (ev) => {
        const t = ev.target && ev.target.closest ? ev.target.closest('.toast-topic') : null;
        if (t && window.OFAPHELP && typeof OFAPHELP.open === 'function') {
            OFAPHELP.open(t.dataset.topic);
        }
    });
}

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
    /* §128: an auxiliary window (window.OFAPAUX) hosts one widget and routes NOTHING — writing a
       routing hash there is what put `#overview` back into the window's URL after §73 cleared it. */
    if (!window.OFAPAUX && location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
    ensurePanel(name);
    if (name === 'platforms' && typeof platformsInit === 'function') platformsInit();
    if (name === 'studies' && typeof studiesInit === 'function') studiesInit();
    if (name === 'marketwatch') loadMarketWatch();
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

/* Alt+A (the broker account) lives in keys.js's shortcut map now — the app-core 'alpaca'
   binding — so it is listed in the hotkey sheet and the typing guard is the dispatcher's. */

/* ══════════════════════════════════════════════════════════════
   Boot
   ══════════════════════════════════════════════════════════════ */

async function boot() {
    if (S.booted) return;                      // C-11: no re-boot path exists today; be ready for one
    S.booted = true;
    try {
        const data = await api('/api/control/bootstrap');
        S.config = data.config;
        /* §149b: the systems-board fold the owner chose — in place before the board paints */
        applySystemsHidden(((S.config || {}).ui || {}).systems_hidden);
        /* §117: the user’s own shortcut chords ride the config into the registry — one
           hand-off at boot; the sheet re-paints itself from the map, which now resolves
           the overrides. */
        if (window.OFAPKEYS && window.OFAPKEYS.applyOverrides) {
            const keysCfg = ((data.config || {}).ui || {}).keys || {};
            window.OFAPKEYS.applyOverrides(keysCfg.overrides || {});
            window.OFAPKEYS.annotate();
        }
        S.caps = data.capabilities;
        S.system = data.system;
        S.status = data.status;
    } catch (e) {
        S.booted = false;                      // a failed boot may be retried
        $("#railPlatform").textContent = 'control API unavailable';
        console.error(e);
        return;
    }
    renderPlatform();
    renderSettings();
    renderInstruments();
    renderStatus();
    await refreshInstruments();
    /* §86: the Systems board asks AFTER the boot burst has drained. Fired inside the burst it
       sat queued for ~25 s behind the page's slow boot calls (measured live: the browser's
       six-socket pool saturated, the request never started) — the board is a check, it must
       not fight the app's own start-up for the wire. Every Overview visit re-checks it, and
       the card carries its own Re-check. */
    void renderSystems();
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
    $("#btnStart").classList.toggle('hidden', st.state === 'running' || st.state === 'stopping');
    $("#btnStop").classList.toggle('hidden', !(st.state === 'running' || st.state === 'starting' || st.state === 'stopping'));
    $("#btnStop").disabled = st.state === 'stopping';
    $("#btnStart").disabled = st.state === 'starting' || st.state === 'stopping';
    /* §132: the button stays on screen through the whole stop (disabled) because the red bar runs
       beside it — hiding it mid-stop left the progress pointing at a disabled Start button. The
       progress bar reads this same payload; it never polls the route on its own. */
    if (window.OFAPENGINEPROGRESS) OFAPENGINEPROGRESS.apply(st, Date.now());
    $("#sourcePill").textContent = 'source: ' + ((st.source || (S.config && S.config.data_source) || '—'));
    $("#ovSub").textContent = st.running
        ? `${st.source} · ${(st.symbols || []).join(', ')} · up ${Math.round(st.uptime_s)}s`
        : 'engine stopped — press Start';

    /* Discreet, and only while it is true: the engine reads its feed, instruments and engine
       parameters when it starts, so a switch (or an edit) after that leaves those waiting. The
       Profiles panel says it where the switch was made; this says it from anywhere else the
       switch came from — the menu, the palette. It clears itself when the engine restarts. */
    const hold = $("#statusProfileHold");
    if (hold) {
        const pend = st.profile_restart_pending;
        hold.hidden = !pend;
        if (pend) {
            const labelFor = (b) => (window.OFAPPROFILES && OFAPPROFILES.blockLabel ? OFAPPROFILES.blockLabel(b) : b);
            const names = (pend.blocks || []).map(labelFor).join(', ');
            hold.textContent = 'restart to apply: ' + names;
            hold.title = 'The engine reads its feed, instruments and parameters when it starts — '
                + names + ' are still waiting for the next start. Everything else is already live. '
                + 'Restart the engine (Engine view, or Ctrl+Alt+R) to land them.';
            hold.onclick = () => { if (typeof window.showView === 'function') window.showView('engine'); };
        }
    }

    const banner = $("#ovBanner");
    if (st.state === 'error' && st.error) toast(banner, st.error, 'err', 'fix.engine_error');
    else if (!st.running) toast(banner, 'Engine is idle. Press “Start engine” to connect the data feed — the panels below will fill as ticks arrive.', 'info');
    else if ((st.skipped || []).length) {
        /* §83: the persistent skip banner carries the way out — the look-up button — instead of
           ending at the reason. Falls back to the plain sentence if the module is absent. */
        const notice = window.OFAPHINT ? OFAPHINT.skippedNotice(st) : null;
        if (notice) OFAPHINT.paintNotice(notice, banner);
        else toast(banner, `Skipped instruments: ${st.skipped.map((s) => s.symbol).join(', ')} — ${st.skipped[0].reason}`, 'warn', 'fix.skipped_symbols');
    } else clearToast(banner);
}

/** Refresh the "data:" chip — the single place that says live / warming / demo.
 *  The map comes from /api/control/live-status (engine.live_status()); every panel
 *  that can serve demo data reads its state from here instead of guessing. */
async function refreshLiveChip(status) {
    try {
        S.live = await api('/api/control/live-status');
    } catch (e) { /* keep the previous map on a hiccup */ }
    const el = $("#livePill");
    if (!el) return;
    const map = (S.live && S.live.endpoints) || {};
    const overall = (S.live && S.live.overall) || 'demo';
    el.className = 'pill ' + (overall === 'live' ? 'running' : overall === 'warming' ? '' : 'stopped');
    /* P1-10: the pill says BOTH what the data is and how old it is — the newest tape sample's age
       from the server's own age block, re-read with every status poll. */
    const tapeAge = (S.live && S.live.age && S.live.age.tape) || null;
    const ageText = (tapeAge && tapeAge.age_known && window.OFAPFRESH) ? ' · ' + OFAPFRESH.fmtAge(tapeAge.age_ms)
        : (tapeAge && tapeAge.stale) ? ' · stale' : '';
    el.textContent = 'data: ' + overall + ageText;
    const ages = (S.live && S.live.age) ? Object.entries(S.live.age)
        .map(([k, v]) => `${k}: ${v.age_known ? Math.round(v.age_ms / 1000) + 's' : 'age unknown'}`).join(' · ') : '';
    el.title = (ages ? ages + ' — ' : '') + (Object.entries(map).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'live/demo state per endpoint');
    /* v2 report §7-9: provenance depth — from the engine's own retained tick window, the active
       instrument's silence pattern (how often the tape went quiet, and for how long at worst).
       The honest answer to "was the feed inside the tape I just read?"; a stopped engine simply
       adds nothing. */
    if (S.live && S.live.state === 'running') {
        try {
            const sym = ($('#symbolSelect') || {}).value || (S && S.symbol) || '';
            /* FG-07: applyStatus already holds this very payload — reuse it; only a bare call
               (the chip refreshed without one) spends the request. */
            const st = status || await api('/api/control/engine/status');
            const row = ((st.per_symbol) || []).filter((r) => r.symbol === sym)[0];
            const g = row && row.gaps;
            if (row && g && g.window) {
                const secs = (v) => (v / 1000).toFixed(1) + ' s';
                const age = row.last_tick_ms ? Math.max(0, Date.now() - row.last_tick_ms) : -1;
                el.title += `\n${row.symbol}: last tick ${age >= 0 ? secs(age) + ' ago' : 'unknown'}`
                    + ` · gaps ≥ ${secs(g.threshold_ms)} in the last ${g.window} ticks: ${g.count}`
                    + (g.worst_ms ? ` (worst ${secs(g.worst_ms)})` : '');
            }
        } catch (e) { /* provenance is a bonus, never a blocker */ }
    }
}

/** True when the given endpoint is demonstrably serving engine data right now. */
function panelIsLive(key) {
    return !!(S.live && S.live.endpoints && S.live.endpoints[key] === 'live');
}

/** The endpoint's server-declared state — 'live' | 'warming' | 'demo' | 'stale' | ''. Panels
 *  that label provenance (a demo fill is never dressed up as a feed) read it from here. */
function liveState(key) {
    return (S.live && S.live.endpoints && S.live.endpoints[key]) || '';
}

/* The shell's own read of the engine status: 2 s, and the same (endpoint, params) the Watchlist
   panel watches — so both ride ONE shared channel instead of a request stream each (see boot). */
const STATUS_POLL_MS = 2000;
let statusUnsubscribe = null;
/* Sequencing tokens: only the newest request may paint. Two overlapping loads (a symbol switch
   while a poll is in flight) used to resolve in either order, so a stale payload could repaint a
   panel for the previous instrument (audit B-JS-01). */
let chartSeq = 0;
let bookSeq = 0;
let tapeSeq = 0;


/* ── §86: the Systems board — "are the systems 100%?" ────────────────────────────
   One call, one card: every ingest path (engine, feed source, the terminal/venue
   integrations, the history store, the UI stream, alerts) plus the capabilities this
   install has not set up yet. Read-only on the server; clicks route to the view that
   owns the fix. */
let sySeen = new Map();      // §90: last state per tile, so a change can announce itself once
async function renderSystems() {
    const grid = $("#systemsGrid");
    const scoreEl = $("#systemsScore");
    if (!grid || !window.OFAPSYSTEMS) return;
    let report = null;
    try { report = await api('/api/control/systems'); } catch (e) { report = null; }
    if (!report || report.ok === false) {
        if (scoreEl) scoreEl.textContent = 'backend not answering';
        return;
    }
    const summary = OFAPSYSTEMS.summary(report);
    if (scoreEl) scoreEl.textContent = summary.line
        + (summary.attention ? ` · ${summary.attention} need attention` : '');
    grid.innerHTML = OFAPSYSTEMS.tiles(report).map((t) => {
        const moved = sySeen.has(t.name) && sySeen.get(t.name) !== t.state;
        sySeen.set(t.name, t.state);
        return `<div class="sy-tile${t.optional ? ' opt' : ''}${moved ? ' sy-flash' : ''}"${t.view ? ` data-view="${esc(t.view)}"` : ''} title="${esc(t.detail)}">`
        + `<div class="sy-line"><span class="sy-name">${esc(t.name)}</span><div class="spacer"></div>`
        + `<span class="tag ${t.kind}">${esc(t.text)}</span></div>`
        + `<div class="sy-detail">${esc(t.detail)}</div></div>`;
    }).join('');
    grid.querySelectorAll('.sy-tile').forEach((el) => el.addEventListener('click', () => {
        const v = el.getAttribute('data-view');
        if (v && typeof window.showView === 'function') window.showView(v);
    }));
    const note = $("#systemsNote");
    if (note) note.textContent = summary.attention
        ? 'Click a tile to go to the view that fixes it; greyed tiles are capabilities this install has not set up.'
        : 'Every expected system is live.';
}
if ($("#systemsRefresh")) $("#systemsRefresh").onclick = () => void renderSystems();

/* §149b: hide/show the Systems board — the owner's ask (clear the Overview without losing the
   score line). The fold is a ui setting in the config, not a browser one: the storage card's
   cache clear wipes webview2's localStorage, and a view choice that vanishes with the caches
   would read as a bug. The control rides in the header it folds, so the way back never hides. */
function applySystemsHidden(hidden) {
    const card = $("#systemsCard");
    const btn = $("#systemsHide");
    if (card) card.classList.toggle('systems-hidden', !!hidden);
    if (btn) {
        btn.textContent = hidden ? 'Show' : 'Hide';
        btn.setAttribute('aria-pressed', String(!!hidden));
        btn.title = hidden ? 'Show the systems board'
            : 'Hide the systems board — the card keeps this header and folds away';
    }
}
async function saveSystemsHidden(hidden) {
    try {
        const cfg = JSON.parse(JSON.stringify(S.config || {}));
        cfg.ui = cfg.ui || {};
        cfg.ui.systems_hidden = !!hidden;
        const r = await api('/api/control/config', { method: 'POST', body: cfg });
        if (r && r.config) S.config = r.config;
    } catch (e) { /* the fold still stands for this run */ }
}
if ($("#systemsHide")) $("#systemsHide").onclick = () => {
    const card = $("#systemsCard");
    const next = !(card && card.classList.contains('systems-hidden'));
    applySystemsHidden(next);
    void saveSystemsHidden(next);
};

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

/* A chart load that never landed. Measured: a switch made right after boot held 'loading…' (and
   therefore the blanked Last / Window-delta cells) for 20 s+ — the page's own start-up burst had
   a request stalled behind it, and nothing retried, because the chart has no poll of its own. The
   status tick retries until the loaded series belongs to the selected instrument — the same
   retry-until-it-lands shape the Systems board uses — and bounded (FG-06): CHART_RETRY_MAX
   tries, then it stops and says so; a landed load or a new selection resets the budget. */
let chartRetryAt = 0;
let chartRetryTries = 0;
const CHART_RETRY_MAX = 12;
function chartLoadWatch() {
    if (!S.symbol || typeof truthyView !== 'function' || !truthyView('chart')) return;
    if (S.chartSymbol === S.symbol && S.lastDeltaSymbol === S.symbol) { chartRetryTries = 0; return; }
    const now = Date.now();
    if (now < chartRetryAt) return;
    if (chartRetryTries >= CHART_RETRY_MAX) return;   // FG-06: a permanent failure must not retry forever
    chartRetryAt = now + 5000;
    chartRetryTries += 1;
    if (chartRetryTries === CHART_RETRY_MAX) {
        const s = $("#chartStatus");
        if (s) s.textContent = "the chart did not load — reselect the instrument to retry";
    }
    loadChart();
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
    refreshLiveChip(payload);
    renderOverviewTable();
    chartLoadWatch();
    /* §86: the Systems board's first paint rides a status tick — by then the boot burst has
       drained (measured: fired inside the burst, its fetch queued ~25 s behind the page's own
       boot calls). Retries each tick until it lands; visits and the Re-check keep it fresh. */
    if (!S.sysPainted && !S.sysPending) {
        S.sysPending = true;
        renderSystems().then(() => { S.sysPainted = true; }).finally(() => { S.sysPending = false; });
    }
    /* The top bar's instrument drives these KPIs. The status payload carries EVERY stream, and
       this block used to read `per_symbol[0]` — the first instrument — so the Overview showed
       the first stream's price, delta, tick and candle counts no matter what the selector said
       (measured: BTC's 81 112.50 painted over an XRPUSDT selection within 2 s of every XRP tick
       that briefly put 1.4110 there). One selection, one row; a selection the engine is not
       streaming blanks the cells rather than wearing another instrument's numbers. */
    const rows = S.status.per_symbol || [];
    const wanted = S.symbol || (rows[0] || {}).symbol;
    const row = wanted ? rows.find((p) => p.symbol === wanted) : null;
    if (row) {
        if (row.price) updatePriceKpis(row.price, null);
        updateDeltaKpi(row.cum_delta, 0);
    } else if (wanted) {
        ['kpiPrice', 'kpiDelta'].forEach((id) => {
            const k = $(`#${id}`);
            if (k) k.querySelector('.kpi-value').textContent = '—';
        });
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
    /* §132: the click IS the transition's start — the bar arms now and answers on the spot. */
    if (window.OFAPENGINEPROGRESS) OFAPENGINEPROGRESS.begin('up');
    try {
        const cfg = await collectSettings();
        const r = await api('/api/control/engine/start', { method: 'POST', body: cfg });
        if (!r.ok) toast($("#ovBanner"), r.error || 'Start failed', 'err');
        /* §83: an engine that skipped instruments says so, with the look-up one click away —
           silence here is how "crypto only" used to be discovered days later. */
        if (window.OFAPHINT && r && r.ok !== false) {
            const notice = OFAPHINT.skippedNotice(r);
            if (notice) OFAPHINT.paintNotice(notice, $('#ovBanner') || document.body);
        }
    } catch (e) {
        toast($("#ovBanner"), String(e), 'err');
    }
    $("#btnStart").innerHTML = '▶ Start engine';
    pollStatus();
};

$("#btnStop").onclick = async () => {
    $("#btnStop").disabled = true;
    if (window.OFAPENGINEPROGRESS) OFAPENGINEPROGRESS.begin('down');
    try { await api('/api/control/engine/stop', { method: 'POST' }); } catch (e) { console.error(e); }
    $("#btnStop").disabled = false;
    pollStatus();
};

$("#btnRestart").onclick = async () => {
    if (window.OFAPENGINEPROGRESS) OFAPENGINEPROGRESS.begin('up');
    try {
        const cfg = await collectSettings();
        await api('/api/control/engine/restart', { method: 'POST', body: cfg });
    } catch (e) { toast($("#ovBanner"), String(e), 'err'); }
    pollStatus();
};

/* §132: the engine's progress bar. renderStatus() hands it the same payload the top bar already
   reads; the bar's own beats (a local tick and, only while a transition runs, a status re-poll)
   live in its own module, with its timer handed to the pause registry — see engine-progress.js.
   It cannot ride the shell's poll: that one is deliberately held while the user is mid-action (the
   intent and steady gates), and measured, the gate delayed the bar's first frame of a stop by ~4 s. */
if (window.OFAPENGINEPROGRESS) OFAPENGINEPROGRESS.mount($("#engineCtl"));

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
            /* P1-10: a tape tick just landed — the tape panel's sample time, for its chip. */
            if (window.OFAPFRESH) OFAPFRESH.stamp('tape', { ageMs: 0, kind: 'trades' });
            /* Trade audio (opt-in, `audio.enabled` in the config). Driven from the same tick the
               tape draws, so what is heard and what is seen can never disagree; silent until the
               user turns it on in the Tape view's Chart menu. */
            if (window.OFAPAUDIO) {
                OFAPAUDIO.setSymbol(S.symbol);
                OFAPAUDIO.onTick({ symbol: data.symbol || S.symbol, price: data.price,
                                   size: data.size, side: data.side });
            }
            if (window.OFAPINTENT && OFAPINTENT.held('overview')) OFAPINTENT.deferKeyed('overview', 'snap', pollStatus);
            else updatePriceKpis(data.price, data.side);
            if (S.inst.tape && truthyView('tape')) {
                if (window.OFAPINTENT && OFAPINTENT.held('tape')) OFAPINTENT.deferKeyed('tape', 'snap', loadTape);
                else S.inst.tape.addTrade({ time: Date.now(), price: data.price, size: data.size, side: data.side });
            }
            break;
        case 'candle':
            S.candleCount++;
            if (window.OFAPINTENT && OFAPINTENT.held('chart')) { OFAPINTENT.deferKeyed('chart', 'snap', loadChart); break; }
            if (S.candleSeries && S.chartSymbol === S.symbol) {
                /* §56 carry-over: this used to repaint the newest bar with plain OHLC, so an
                   expression mode's colours dropped off the bar until the next full fetch. The
                   same chartBars pass the full repaint uses colours the single bar too. */
                const EM = exprModule();
                const bar = { time: data.time, open: data.open, high: data.high, low: data.low,
                              close: data.close, volume: data.volume, delta: data.delta };
                let point = bar;
                if (EM && S.expr) {
                    try {
                        const coloured = EM.chartBars([bar], { mode: S.expr.mode, palette: S.expr.palette,
                                                               theme: S.exprTheme })[0];
                        if (coloured) point = coloured;
                    } catch (e) { /* the plain bar is always paintable */ }
                }
                S.candleSeries.update(point);
            }
            break;
        case 'delta':
            if (window.OFAPINTENT && OFAPINTENT.held('chart')) { OFAPINTENT.deferKeyed('chart', 'snap', loadChart); break; }
            updateDeltaKpi(data.value, data.bar_delta);
            /* The chart's own lane and window series belong to ONE instrument. A tick for the
               newly selected symbol arriving while its load is still in flight must not be folded
               into the previous instrument's series — that mixed sum is what made a switch read
               "skewed" for a poll (measured: XRP's 46.60K window beside the series' real 1.37M). */
            if (S.lastDeltaSymbol !== S.symbol) break;
            if (S.deltaSeries) S.deltaSeries.update({ time: data.time, value: data.value });
            /* The lane just took this bar, so the window's own sum takes it too — updated in
               place when it is the newest bar, appended when it opens one. */
            if (Array.isArray(S.lastDelta) && S.lastDelta.length) {
                const tail = S.lastDelta[S.lastDelta.length - 1];
                if (Number(tail.time) === Number(data.time)) {
                    tail.bar_delta = data.bar_delta; tail.value = data.value;
                } else if (Number(data.time) > Number(tail.time)) {
                    S.lastDelta.push({ time: data.time, value: data.value, bar_delta: data.bar_delta });
                }
                paintWindowDelta();
            }
            break;
        case 'signal':
            if (window.OFAPINTENT && OFAPINTENT.held('signals')) { OFAPINTENT.deferKeyed('signals', 'snap', loadSignals); break; }
            S.signals.unshift(data);
            S.signals = S.signals.slice(0, 60);
            $("#navSignalCount").textContent = S.signals.length;
            renderOverviewSignals();
            if (S.inst.signals) S.inst.signals.addSignal(data);
            break;
        case 'orderbook':
            if (window.OFAPINTENT && OFAPINTENT.held('depth')) { OFAPINTENT.deferKeyed('depth', 'snap', loadOrderbook); break; }
            if (S.inst.book) S.inst.book.updatePrice(data.best_bid, 'buy');
            updateDepthKpis(data);
            break;
        case 'stats':
            if (window.OFAPINTENT && OFAPINTENT.held('overview')) { OFAPINTENT.deferKeyed('overview', 'snap', pollStatus); break; }
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
    const digits = price > 100 ? 2 : 4;
    const text = fmt(price, digits);
    /* §90: a live price must look live — direction arrow, tint and flash via the shared layer. */
    if (window.OFAPTICK) OFAPTICK.tick(k.querySelector('.kpi-value'), text, { arrow: true });
    else k.querySelector('.kpi-value').textContent = text;
    k.querySelector('.kpi-sub').textContent = side ? side.toUpperCase() + ' print' : '';
    const c = $("#chPrice").querySelector('.kpi-value');
    if (c) { if (window.OFAPTICK) OFAPTICK.tick(c, text, { arrow: true }); else c.textContent = text; }
}
function updateDeltaKpi(cum, bar) {
    /* The Overview's "Cumulative delta" — the SESSION total, from the status row or the ws delta
       tick. It used to double as the chart's cell too; that cell means the delta across the
       chart's own window (paintWindowDelta), and writing the session total there made the pair
       disagree under every selection (BTC's session -34 beside XRP's window). */
    const k = $("#kpiDelta");
    const text = compact(cum);
    if (window.OFAPTICK) OFAPTICK.tick(k.querySelector('.kpi-value'), text, { arrow: true });
    else k.querySelector('.kpi-value').textContent = text;
    k.querySelector('.kpi-sub').textContent = `bar ${compact(bar)}`;
    k.classList.toggle('up', cum > 0); k.classList.toggle('down', cum < 0);
}
function updateDepthKpis(d) {
    const bidText = fmt(d.best_bid, 4);
    const askText = fmt(d.best_ask, 4);
    if (window.OFAPTICK) {
        OFAPTICK.tick($("#dpBid").querySelector('.kpi-value'), bidText, { arrow: true });
        OFAPTICK.tick($("#dpAsk").querySelector('.kpi-value'), askText, { arrow: true });
    } else {
        $("#dpBid").querySelector('.kpi-value').textContent = bidText;
        $("#dpAsk").querySelector('.kpi-value').textContent = askText;
    }
    const imb = ((d.imbalance ?? 0) * 100);
    const k = $("#dpImb");
    if (window.OFAPTICK) OFAPTICK.tick(k.querySelector('.kpi-value'), fmt(imb, 1) + '%', { arrow: false });
    else k.querySelector('.kpi-value').textContent = fmt(imb, 1) + '%';
    k.querySelector('.kpi-sub').textContent = imb > 5 ? 'bid heavy' : imb < -5 ? 'ask heavy' : 'balanced';
    k.classList.toggle('up', imb > 0); k.classList.toggle('down', imb < 0);
    /* The WebSocket payload carries prices only — no sizes. The two `updateLevel(..., 0)` calls
       that used to sit here are the ladder's DELETE path (a zero size removes the level), so
       every book tick quietly spliced the top-of-book rungs out of the ladder between REST
       snapshots (measured: 38 calls, 6 rungs gone in 9 s — the footer's totals bled to 0.0). */
    if (S.inst.book) {
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
    /* Show a switching indicator on the symbol picker while panels refresh.
       The delay comes from every open panel reloading its data for the new symbol. */
    const picker = document.querySelector('.symbol-picker');
    if (picker) picker.classList.add('switching');
    /* Also update the Engine view's own symbol field if it is open — the engine
       keeps its own symbol state (view.symbol) and only changes it when the user
       types in #ofxSymbol or picks from #ofxSymPick. Without this, the engine
       section keeps showing the old symbol after a top-bar switch. The write is
       silent (no change event): the Engine view adopts the switch through the
       ofap:symbol event below, and its pickSymbol() owns the busy rings on these two
       controls for the whole settle (config save, resolve, enable/start, picker
       refresh) — the notifier this section was missing. */
    const ofxSym = document.getElementById('ofxSymbol');
    if (ofxSym && ofxSym.value !== e.target.value) ofxSym.value = e.target.value;
    /* Blank this instrument's cells before the new load lands: they held the instrument the
       selector moved away from, and one poll of the old numbers under the new selection is
       exactly what "the switch is skewed" looks like. The next status poll / chart load fills
       them within a heartbeat. */
    ['kpiPrice', 'kpiDelta', 'kpiTicks', 'kpiCandles', 'chPrice', 'chDelta'].forEach((id) => {
        const cell = $(`#${id}`);
        if (cell && cell.querySelector('.kpi-value')) cell.querySelector('.kpi-value').textContent = '—';
    });
    /* The chart's series still belong to the instrument we just left: untagged, so no ws tick
       folds into them while the new load is in flight. */
    S.chartSymbol = '';
    S.lastDeltaSymbol = '';
    chartRetryTries = 0;                 // FG-06: a new selection gets a fresh retry budget
    chartRetryAt = 0;
    ['chPoc', 'chBias'].forEach((id) => {
        const cell = $(`#${id}`);
        if (!cell) return;
        if (cell.querySelector('.kpi-value')) cell.querySelector('.kpi-value').textContent = '—';
        if (cell.querySelector('.kpi-sub')) cell.querySelector('.kpi-sub').textContent = '';
    });
    $("#chartStatus").textContent = 'loading…';
    /* The tape holds ONE instrument's prints — and its footer (BUY VOL / SELL VOL / TRADES)
       sums exactly those. A switch that left the old symbol's rows in place mixed two
       instruments into one list and added their volumes together (measured: BTC prints at
       81115.8 under an XRPUSDT selection, with XRP's 14 against BTC's 0.136 in the totals).
       clear() is the tape's own button's path, so the panel empties exactly as it does there. */
    if (S.inst.tape) S.inst.tape.clear();
    /* The top bar's busy ring, cleared wherever the refresh ends — and by the fallback
       timer below. The Engine controls' rings are owned by ofx-view's pickSymbol(): it
       holds them for the whole settle there (resolve, enable/start, picker refresh),
       which lasts longer than this refresh and used to be cleared too early.
       Declared as a function on purpose: the T4 test reads this handler up to its first
       brace-then-semicolon pair, and an arrow assigned to a const would end the excerpt
       right here. */
    function clearSwitchMarks() {
        const picker = document.querySelector('.symbol-picker');
        if (picker) picker.classList.remove('switching');
    }
    /* A switch is the user's own act, not a poll: the steady guard stands aside (steadyForce)
       so the panels actually reload for the new instrument instead of sitting out its typing
       grace — that wait was the long, unpredictable delay between the pick and the output. */
    if (typeof steadyForce === 'function') steadyForce(3000);
    /* One instrument selection drives every live panel: the Engine view keeps its own symbol
       (persisted through /api/control/ofx), so the top bar's choice is announced as an event
       rather than by reaching into the view (audit B-JS-03). Announced before the refresh:
       the Engine view and the Atlas surfaces adopt the switch through this event, and both
       used to lose it whenever the refresh call in front of it threw (measured: a guard-skip
       TypeError aborted this handler before this line, the rings stayed up and the panels
       never heard the change). */
    document.dispatchEvent(new CustomEvent('ofap:symbol', { detail: { symbol: S.symbol, source: 'topbar' } }));
    /* The refresh's own result may be a promise (the steady wrapper answers with a settled
       one when it skips an async render) — chained, but never trusted blindly: a missing
       .finally must not abort the handler again. */
    try {
        const refresh = refreshAllPanels(true);
        if (refresh && typeof refresh.finally === 'function') refresh.finally(clearSwitchMarks);
        else clearSwitchMarks();
    } catch (err) {
        console.warn('[ui] panel refresh after the symbol switch failed:', err);
        clearSwitchMarks();
    }
    // Safety net: if a panel hangs, the rings still go away after 10 s.
    setTimeout(clearSwitchMarks, 10000);
    /* T4/A9: the widget titles carry the instrument, and only the shell's status pass repaints
       them — so the top bar must ask for it. Measured before this line existed: after moves to
       ETHUSDT / SOLUSDT / XRPUSDT every frame still read "· BTCUSDT" minutes later (the symbol it
       was BUILT with), which is exactly the "panel on ETHUSDT, title says BTCUSDT" contradiction
       the owner photographed (§130). */
    if (window.OFAPSHELL && typeof OFAPSHELL.paintStatus === 'function') OFAPSHELL.paintStatus();
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
    /* The shell's Ticks / Candles-closed cells follow the top bar's instrument, like the price
       and delta cells above them: `rows[0]` was the first stream, not the selected one. */
    const wanted = S.symbol || (rows[0] || {}).symbol;
    const sel = wanted ? rows.find((r) => r.symbol === wanted) : null;
    $("#kpiTicks").querySelector('.kpi-value').textContent = sel ? sel.ticks : '—';
    $("#kpiCandles").querySelector('.kpi-value').textContent = sel ? sel.candles : '—';
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
    /* §90: the newest card slides in — a detection should catch the eye, once, and settle. */
    if (window.OFAPTICK && box.firstElementChild) OFAPTICK.arrival(box.firstElementChild);
}

/* ══════════════════════════════════════════════════════════════
   Chart
   ══════════════════════════════════════════════════════════════ */

/* ── P1-8: the chart's bar expression ──────────────────────────────────────────────────────────
   One call site for the paint: `expression.js` decides what each candle's body, outline and wick
   are, and this hands the result to the vendor series. The mode the catalogue resolves is what the
   legend line prints, so the words and the drawing cannot disagree. */
function exprModule() { return window.OFAPEXPR || null; }

function exprPair(palette) {
    const E = exprModule();
    if (!E) return S.exprTheme;
    return E.pair(palette, S.exprTheme);
}

function applyChartExpression(next) {
    const E = exprModule();
    if (next && (next.mode || next.palette)) {
        if (next.mode) S.expr.mode = String(next.mode);
        if (next.palette) S.expr.palette = String(next.palette);
    }
    const mode = (E && E.MODE_KEYS.indexOf(String(S.expr.mode)) >= 0) ? String(S.expr.mode) : 'default';
    const palette = (E && E.PALETTE_KEYS.indexOf(String(S.expr.palette)) >= 0) ? String(S.expr.palette) : 'theme';
    S.expr.mode = mode;
    S.expr.palette = palette;
    if ($('#chartMode')) $('#chartMode').value = mode;
    if ($('#chartPalette')) $('#chartPalette').value = palette;
    paintChartExprLegend();
    return { mode, palette };
}

/* The line under the card title: the encoding in use, its sign pairing, the palette and — when the
   chart cannot draw the mode — the reason, in the panel, in the words of the actual condition. */
function paintChartExprLegend() {
    const el = $('#chartExpr');
    if (!el) return;
    const E = exprModule();
    if (!E) { el.textContent = 'expression module not loaded — plain candles'; return; }
    const mode = S.expr.mode;
    const lines = E.legendLines(mode, S.expr.palette, {
        chartGap: E.CHART_SUPPORT[mode] ? '' : 'the chart view cannot draw this mode — candles stay plain here',
    });
    el.textContent = lines.filter((l) => l && l.indexOf('depth ramp:') !== 0).join(' \u00b7 ');
}

/* The stored block, read once per page. A failed read leaves the defaults in place (the chart is
   still usable) and the legend already says which mode is drawing. */
async function loadChartExpression(force) {
    if (S.expr.loaded && !force) return;
    try {
        const res = await api('/api/control/expression');
        const chart = (res && res.expression && res.expression.chart) || {};
        S.expr.loaded = true;
        applyChartExpression({ mode: chart.mode, palette: chart.palette });
    } catch (err) {
        applyChartExpression({});                     // the defaults stand, and the legend says what drew
    }
    if (force) repaintChart();                        // repaint the candles already on screen
}

async function saveChartExpression(patch) {
    const applied = applyChartExpression(patch);
    /* Repaint what is already on screen: the candles carry the mode's paints, so an encoding change
       that only updated the controls would leave yesterday's picture under today's legend. */
    repaintChart();
    try {
        const res = await api('/api/control/expression', { method: 'POST', body: Object.assign({ chart: 'chart' }, patch) });
        const value = (res && res.value) || {};
        applyChartExpression({ mode: value.mode, palette: value.palette });   // what the store accepted
    } catch (err) {
        $('#chartStatus').textContent = `expression save failed: ${err}`;
    }
    return applied;
}

/* A display change repaints from the data already in hand. The fetch path stays the only fetcher:
   `steady.js` skips a panel's loaders for 30 s after any input inside it, so a mode change that
   waited for the fetch would leave the previous encoding on screen until the hold expired. */
function repaintChart() {
    const E = exprModule();
    if (!E || !S.candleSeries || !(S.lastBars || []).length) return false;
    S.candleSeries.setData(E.chartBars(S.lastBars, { mode: S.expr.mode, palette: S.expr.palette, theme: S.exprTheme }));
    if (S.deltaSeries && (S.lastDelta || []).length) {
        const pair = exprPair(S.expr.palette);
        S.deltaSeries.setData(S.lastDelta.map((x) => ({
            time: x.time, value: x.bar_delta ?? x.value,
            color: (x.bar_delta ?? x.value) >= 0 ? `rgba(${pair.pos},.55)` : `rgba(${pair.neg},.55)`,
        })));
    }
    return true;
}

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
    if (window.OFAPINTENT && OFAPINTENT.held('chart')) { OFAPINTENT.deferKeyed('chart', 'snap', loadChart); return; }

    ensureChart();
    if (!S.chart || !S.symbol) return;
    $("#chartStatus").textContent = 'loading…';
    const sym = encodeURIComponent(S.symbol);
    const notes = [];
    const seq = ++chartSeq;
    try {
        const [candles, delta, vp, bias] = await Promise.all([
            api(`/api/candles/${sym}?tf=${S.tf}&range=${S.range}`),
            api(`/api/delta/${sym}?tf=${S.tf}&range=${S.range}`),
            fetchVolumeProfile(sym),
            api(`/api/bias/${sym}`).catch(() => null),
        ]);
        if (seq !== chartSeq) return;            // superseded: a newer load owns the panes
        const bars = Array.isArray(candles) ? candles : [];
        S.lastBars = bars;                       // the studies layer runs on the same bars
        /* P1-10: the chart's sample clock is its newest bar's CLOSE (open + the series' own
           interval — a closed 1m bar is 60-120 s old by its open while perfectly healthy). */
        if (window.OFAPFRESH) {
            const lastT = bars.length ? Number(bars[bars.length - 1].time) : 0;
            const step = bars.length > 1 ? Math.max(1, lastT - Number(bars[bars.length - 2].time)) : 60;
            /* Demo bars end at "now" by construction, so stamping them with a clock reads
               "live · 0 s" on data the server flagged as demo. Say so instead — freshness.js
               understands `source: 'demo'`, and the ofx panels already label their fallbacks. */
            const demo = liveState('candles') === 'demo';
            OFAPFRESH.stamp('chart', {
                lastMs: demo ? 0 : (lastT ? (lastT + step) * 1000 : 0),
                kind: 'candles', source: demo ? 'demo' : '',
            });
        }
        /* Per-bar paints from the catalogue: the default mode hands back the same OHLC with the
           theme pair's colours (identical to the series' own options), so "default" moves no pixel. */
        const E = exprModule();
        const rows = E
            ? E.chartBars(bars, { mode: S.expr.mode, palette: S.expr.palette, theme: S.exprTheme })
            : bars.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }));
        S.candleSeries.setData(rows);
        S.chartSymbol = S.symbol;                /* the series' own instrument — the guards below read it */
        const d = Array.isArray(delta) ? delta : [];
        // The studies layer runs on the same bars, and the chart already fetched the
        // per-bar delta series: attaching it here is what lets a study read d.delta()
        // instead of re-fetching it (or worse, guessing it).
        const deltaByTime = new Map(d.map((x) => [x.time, x.bar_delta ?? x.value]));
        bars.forEach((bar) => {
            if (deltaByTime.has(bar.time)) bar.bar_delta = deltaByTime.get(bar.time);
        });
        const pair = exprPair(S.expr.palette);
        S.lastDelta = d;                         // held so a display change can recolour without a fetch
        S.lastDeltaSymbol = S.symbol;            /* and whose series it is — see the ws guards */
        S.deltaSeries.setData(d.map((x) => ({ time: x.time, value: x.bar_delta ?? x.value, color: (x.bar_delta ?? x.value) >= 0 ? `rgba(${pair.pos},.55)` : `rgba(${pair.neg},.55)` })));

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
        paintWindowDelta();
        // Studies draw over the freshly loaded bars (and repaint the candles when a study
        // colours them). Guarded: the module is injected asynchronously.
        if (typeof studiesApply === 'function') studiesApply();
        else if (S.candleSeries) S.candleSeries.setMarkers((S.baseMarkers || []).slice(-300));
        /* A study that recolours the candles would otherwise quietly undo the expression mode (both
           write the same series), so the expression is re-asserted last. `default` + the theme
           palette is the one combination where the studies pass keeps the floor: it paints today's
           pixels (the catalogue hands back the very pair the series options carry). Every other
           combination re-asserts — including `default` under a colour-blind palette, which the
           studies pass would otherwise strip back to the theme's green/red while the legend goes on
           claiming sky blue / orange (measured live, before this line read the palette too). */
        if (S.expr.mode !== 'default' || S.expr.palette !== 'theme') repaintChart();
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

/* ── the chart's own "Window delta" ────────────────────────────────────────────────────────────
   The cell means the delta across the CHART's window (the range control) — the same window the
   delta lane under the candles draws — and it is written only from that series, never from the
   session cumulative. Measured before this: an XRPUSDT selection read LAST 81263.70 / WINDOW
   DELTA 13.49 (both BTC's numbers, the session delta painted over the selection every 2 s). */
function windowDeltaSum() {
    const rows = S.lastDelta || [];
    if (!rows.length) return null;
    const newest = Number(rows[rows.length - 1].time);
    const cutoff = (S.range || 0) > 0 ? newest - S.range : -Infinity;
    const inWindow = rows.filter((r) => Number(r.time) >= cutoff);
    if (!inWindow.length) return null;
    /* The series carries the server's own running total (`value`) and each bar's own delta:
       summing the bars must agree with it, so prefer the bars when they are all present. */
    const complete = inWindow.every((r) => Number.isFinite(Number(r.bar_delta)));
    if (complete) return inWindow.reduce((s, r) => s + Number(r.bar_delta), 0);
    return Number(inWindow[inWindow.length - 1].value) || 0;
}

function paintWindowDelta() {
    const el = $("#chDelta");
    if (!el) return;
    const v = windowDeltaSum();
    const cell = el.querySelector('.kpi-value');
    const text = v === null ? '—' : compact(v);
    if (window.OFAPTICK) OFAPTICK.tick(cell, text, { arrow: true });
    else cell.textContent = text;
    el.classList.toggle('up', (v || 0) > 0);
    el.classList.toggle('down', (v || 0) < 0);
}

function renderChartKpis(vp, bias, bars) {
    const last = bars.length ? bars[bars.length - 1].close : null;
    $("#chPrice").querySelector('.kpi-value').textContent = fmt(last, last > 100 ? 2 : 4);
    if (vp) {
        if (window.OFAPTICK) OFAPTICK.tick($("#chPoc").querySelector('.kpi-value'), fmt(vp.poc, 2));
        else $("#chPoc").querySelector('.kpi-value').textContent = fmt(vp.poc, 2);
        $("#chPoc").querySelector('.kpi-sub').textContent = vp.shape ? `shape: ${vp.shape}` : '';
    }
    if (bias) {
        const dir = (bias.direction || '').toString().toLowerCase();
        $("#chBias").querySelector('.kpi-value').textContent = (bias.direction || '—').toString().toUpperCase();
        $("#chBias").querySelector('.kpi-sub').textContent = bias.confidence ? `${Math.round(bias.confidence)}% confidence` : '';
        $("#chBias").classList.toggle('up', dir.includes('bull') || dir === 'buy' || dir === 'long');
        $("#chBias").classList.toggle('down', dir.includes('bear') || dir === 'sell' || dir === 'short');
    }
}

$("#tfSelect").onchange = (e) => { S.tf = +e.target.value; loadChart();
    void saveUIState({ chart: { tf: S.tf } }); };
$("#chartMode").onchange = () => { void saveChartExpression({ mode: $("#chartMode").value }); };
$("#chartPalette").onchange = () => { void saveChartExpression({ palette: $("#chartPalette").value }); };
/* ui.js is the FIRST module tag in the shell and the catalogue's is later in the document, so the
   boot read waits for the DOM: painting the legend before `expression.js` has been parsed states a
   condition ("module not loaded") that would stop being true a millisecond later. */
function bootChartExpression() { void loadChartExpression(); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bootChartExpression);
else bootChartExpression();
/* The menu bar writes the same registry paths; arrive there through the store, like every panel. */
document.addEventListener('ofap:expression', () => { void loadChartExpression(true); });
$("#rangeSelect").onchange = (e) => { S.range = +e.target.value; loadChart();
    void saveUIState({ chart: { range: S.range } }); };
$("#ovMarkers").onchange = () => { loadChart();
    void saveUIState({ chart: { markers: $("#ovMarkers").checked } }); };
$("#ovVP").onchange = () => { loadChart();
    void saveUIState({ chart: { vp: $("#ovVP").checked } }); };

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
    if (!calc) { out.textContent = 'calc: —'; return; }
    const imb = calc.imbalance_counts || { buy: 0, sell: 0 };
    const delta = Number(calc.delta || 0);
    const poc = calc.poc ? `${calc.poc.price} (${calc.poc.share_pct}%)` : '—';
    out.innerHTML = `delta <b class="${delta >= 0 ? 'up' : 'down'}">${delta >= 0 ? '+' : ''}${delta.toFixed(2)}</b>`
        + ` · POC ${poc} · imbalance ${imb.buy}/${imb.sell}`
        + ` · ${calc.mode === 'diagonal' ? 'diagonal' : 'same-price'}`;
    out.title = `Numbers-Bars pack for the last bar: volume ${calc.volume}, buy ${calc.buy}, sell ${calc.sell}, `
        + `extremes ${calc.extremes && calc.extremes.min ? calc.extremes.min.price : '—'}–`
        + `${calc.extremes && calc.extremes.max ? calc.extremes.max.price : '—'}`;
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
            /* §148: build through the window property, never the bare name. `class FootprintChart` at the
               top level of footprint.js creates a global lexical binding that shadows window.FootprintChart,
               so a bare `new FootprintChart(...)` calls the raw chart and never the orderflow.js wrapper —
               which is what attaches the marks canvas and lists the chart. Measured live before this fix:
               the bare path left the wrapper's chart list empty and no marks canvas in the panel. */
            S.inst.footprint = new (window.FootprintChart)('footprintChart', {});
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
        overview: () => { renderOverviewTable(); renderOverviewSignals(); renderSystems(); },
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
    if (window.OFAPINTENT && OFAPINTENT.held('orderflow')) { OFAPINTENT.deferKeyed('orderflow', 'snap', loadFootprint); return; }

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
        if (window.OFAPTICK) {
            OFAPTICK.tick($("#ofPoc").querySelector('.kpi-value'), fmt(vp && vp.poc));
            OFAPTICK.tick($("#ofVah").querySelector('.kpi-value'), fmt(vp && vp.vah));
        } else {
            $("#ofPoc").querySelector('.kpi-value').textContent = fmt(vp && vp.poc);
            $("#ofVah").querySelector('.kpi-value').textContent = fmt(vp && vp.vah);
        }
        $("#ofVal").querySelector('.kpi-value').textContent = fmt(vp && vp.val);
        $("#ofShape").querySelector('.kpi-value').textContent = (vp && vp.shape) || '—';
        $("#ofShape").querySelector('.kpi-sub').textContent = vp && vp.total_volume ? `vol ${compact(vp.total_volume)}` : '';
    } catch (e) { /* ignore */ }
    try {
        const st = await api('/api/control/profiles/status');
        const row = (st.symbols || []).find((r) => r.symbol === S.symbol);
        $("#ofProfileStatus").textContent = row
            ? `profile: ${row.profiles} built · bias ${row.bias || '—'} · ${row.qualified_levels} levels`
            : 'profile: —';
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
    if (window.OFAPINTENT && OFAPINTENT.held('depth')) { OFAPINTENT.deferKeyed('depth', 'snap', loadOrderbook); return; }

    if (!S.inst.book || !S.symbol) return;
    const seq = ++bookSeq;
    try {
        const data = await api(`/api/orderbook/${encodeURIComponent(S.symbol)}?levels=15`);
        if (seq !== bookSeq) return;             // superseded: a newer load owns the ladder
        S.inst.book.setData(data);
        updateDepthKpis(data);
    } catch (e) { console.error(e); }
}

async function loadTape() {
    if (window.OFAPINTENT && OFAPINTENT.held('tape')) { OFAPINTENT.deferKeyed('tape', 'snap', loadTape); return; }

    if (!S.inst.tape || !S.symbol) return;
    if (!panelIsLive('tape')) {
        toast($("#tapeBanner"),
            'Initial tape fill is demo data until the engine has streamed prints for this symbol — new prints over the WebSocket are always real. See the “data:” chip in the status bar.',
            'warn');
    } else clearToast($("#tapeBanner"));
    const seq = ++tapeSeq;
    try {
        const data = await api(`/api/tape/${encodeURIComponent(S.symbol)}?count=120`);
        if (seq !== tapeSeq) return;             // superseded: a newer load owns the tape
        S.inst.tape.addTrades(Array.isArray(data) ? data : []);
    } catch (e) { console.error(e); }
}

/* §87/§88 — the Market Watch view: the source's own board, live. Rows come straight from
   /api/control/marketwatch; the table model is pure (ui/marketwatch.js) and pinned by its
   selftest. The board re-reads on its own timer while the view is visible (~1.5 s), updates
   cells in place (no flicker), tints a price green/red by its last move, and the badge shows
   the data's age. Pause freezes the board exactly as it stands — a read that lands mid-pause is
   dropped — and Resume snaps it current with one forced read. */
const MW_POLL_MS = 1500;
let mwBusy = false;
let mwLastFetchOk = 0;
let mwPrev = new Map();

async function loadMarketWatch(force = false) {
    if (!force && window.OFAPINTENT && OFAPINTENT.held('marketwatch')) {
        /* Parked for study: queue one refresh for resume instead of fetching now. */
        OFAPINTENT.deferKeyed('marketwatch', 'snap', () => loadMarketWatch(true));
        return;
    }
    if (mwBusy) return;                             // one read in flight is enough
    const body = $("#mwBody");
    if (!body) return;
    const sel = $("#mwSource");
    const filt = $("#mwFilter");
    mwBusy = true;
    try {
        const parts = ['limit=200'];
        if (sel && sel.value) parts.push('source=' + encodeURIComponent(sel.value));
        if (filt && filt.value.trim()) parts.push('filter=' + encodeURIComponent(filt.value.trim()));
        const data = await api('/api/control/marketwatch?' + parts.join('&'));
        if (!force && window.OFAPINTENT && OFAPINTENT.held('marketwatch')) return;   // a hold landed mid-flight
        paintMarketWatch(data);
        mwLastFetchOk = Date.now();
        if (data && data.ok === false) toast($("#mwBanner"), data.note || 'the board is unavailable', 'warn');
        else clearToast($("#mwBanner"));
    } catch (e) { console.error('market watch:', e); }
    finally { mwBusy = false; }
}

function paintMarketWatch(data) {
    const body = $("#mwBody");
    if (!body) return;
    const rows = window.OFAPMW ? OFAPMW.rows(data) : [];
    const names = rows.map((r) => r.symbol);
    if (body.dataset.syms !== names.join(',')) {    // the set changed -> rebuild; else update in place
        body.innerHTML = rows.map((r) => `<tr data-symbol="${esc(r.symbol)}">`
            + `<td>${esc(r.symbol)}</td>`
            + `<td style="text-align:right">${esc(r.bid)}</td>`
            + `<td style="text-align:right">${esc(r.ask)}</td>`
            + `<td style="text-align:right" class="${r.cls}">${r.arrow} ${esc(r.change)}</td></tr>`).join('');
        body.dataset.syms = names.join(',');
        mwPrev = new Map();
    }
    rows.forEach((r, i) => {
        const tr = body.children[i];
        if (!tr) return;
        const prev = mwPrev.get(r.symbol);
        mwCell(tr.children[1], r.bid, prev && prev.bid);
        mwCell(tr.children[2], r.ask, prev && prev.ask);
        const chg = tr.children[3];
        if (chg) {
            chg.className = r.cls;
            const text = r.arrow + ' ' + r.change;
            if (chg.textContent.trim() !== text) chg.textContent = text;
        }
        mwPrev.set(r.symbol, { bid: r.bid, ask: r.ask });
    });
    $("#mwCount").textContent = String((data && data.total != null) ? data.total : rows.length) + ' symbols';
    $("#mwNote").textContent = (data && data.note) || '';
}

/* One price cell: tint by the last move and flash on every change (the reflow restarts the
   animation when a move repeats in the same direction). */
function mwCell(cell, text, prevText) {
    if (!cell) return;
    if (prevText != null && window.OFAPMW && OFAPMW.bidDir) {
        const dir = OFAPMW.bidDir(prevText, text);
        if (dir) {
            cell.classList.remove('tick-up', 'tick-down');
            void cell.offsetWidth;
            cell.classList.add(dir === 'up' ? 'tick-up' : 'tick-down');
        }
    }
    if (cell.textContent.trim() !== text) cell.textContent = text;
}

function mwBadgeTick() {
    const el = $("#mwLive");
    if (!el) return;
    const age = mwLastFetchOk ? Math.round((Date.now() - mwLastFetchOk) / 1000) : null;
    if (window.OFAPINTENT && OFAPINTENT.held('marketwatch')) {
        el.textContent = 'paused' + (age != null ? ' · last read ' + age + ' s ago' : '');
        el.classList.add('mw-paused');
    } else {
        el.textContent = age == null ? 'live' : 'live · ' + age + ' s';
        el.classList.remove('mw-paused');
    }
}

setInterval(() => {
    if (truthyView('marketwatch')) loadMarketWatch();
    mwBadgeTick();
}, MW_POLL_MS);
/* #mwPause is a shared user-hold button now (data-surf in the markup): intent.js owns its
   click, its face and its queue — resume flushes one forced read, exactly as before. */
$("#mwRefresh").onclick = () => loadMarketWatch(true);
$("#mwSource").onchange = () => loadMarketWatch(true);
let mwFilterTimer = null;
$("#mwFilter").oninput = () => {
    clearTimeout(mwFilterTimer);
    mwFilterTimer = setTimeout(() => loadMarketWatch(true), 250);
};

async function loadSignals() {
    if (window.OFAPINTENT && OFAPINTENT.held('signals')) { OFAPINTENT.deferKeyed('signals', 'snap', loadSignals); return; }

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
    queueInstrumentApply('', null);
};
$("#btnDisableAll").onclick = () => {
    $$('#instTable tbody tr').forEach((tr) => (tr.querySelector('[data-role="enabled"]').checked = false));
    queueInstrumentApply('', null);
};

/* ── a toggle IS the change (§85) ──────────────────────────────────────────────
   The table used to only paint: a row switched on here and looked at in the Engine view answered
   "not enabled", because nothing saved until the Settings view's Save button was pressed
   (measured live: the toggle painted on, config.json said enabled=false). A toggle now writes the
   row itself — built from the config ON DISK, never this page's possibly-stale copy — refreshes
   the table, and then applies it: a running engine restarts so the change takes effect, exactly
   the path the Engine view's own "Enable & restart" uses. Toggles inside the debounce window ride
   together into one write and one restart. */
let instTimer = null;
let instPending = null;
let instApplying = false;

function queueInstrumentApply(symbol, enabled) {
    instPending = { symbol: symbol || '', enabled: enabled };
    if (instTimer) clearTimeout(instTimer);
    instTimer = setTimeout(() => void applyInstrumentChanges(), 450);
}

/* One write at a time: a second toggle while a save/restart is still in flight would otherwise
   race its predecessor (measured: two quick flips interleaved, and only the newer write being
   last kept the newer state). The follow-up runs on the pending state, so the newest flip lands
   last, and its message is the one on the banner. */
async function applyInstrumentChanges() {
    if (instApplying) {
        if (instTimer) clearTimeout(instTimer);
        instTimer = setTimeout(() => void applyInstrumentChanges(), 250);
        return;
    }
    instApplying = true;
    try {
        await applyInstrumentChangesNow();
    } finally {
        instApplying = false;
        if (instPending) queueInstrumentApply(instPending.symbol, instPending.enabled);
    }
}

async function applyInstrumentChangesNow() {
    const pending = instPending || { symbol: '', enabled: null };
    instPending = null;
    if (instTimer) { clearTimeout(instTimer); instTimer = null; }
    const banner = $("#instBanner");
    try {
        const fresh = await api('/api/control/config');
        const dom = new Map(collectInstruments().map((row) => [row.symbol, row]));
        const rows = (fresh.instruments || []).map((row) => {
            const seen = dom.get(row.symbol);
            return seen ? { ...row, enabled: seen.enabled, tick_size: seen.tick_size } : row;
        });
        const r = await api('/api/control/config', { method: 'POST', body: { instruments: rows } });
        if (r && r.ok === false) { toast(banner, 'save refused: ' + (r.error || 'unknown'), 'err'); return; }
        if (r && r.config) S.config = r.config;
        try { S.caps = await api('/api/control/capabilities'); } catch (e) { /* keep current caps */ }
        renderInstruments();
        const what = pending.symbol || 'instruments';
        const state = pending.enabled === true ? 'enabled' : (pending.enabled === false ? 'disabled' : 'updated');
        const status = await api('/api/control/engine/status').catch(() => ({}));
        if (status && status.running) {
            toast(banner, `${what} ${state} — restarting the engine to apply…`, 'info');
            const restarted = await api('/api/control/engine/restart', { method: 'POST', body: {} });
            const bad = restarted && restarted.ok === false;
            /* §83's rule reaches this path too: a row this source cannot serve is reported with
               its reason (the engine's own `skipped`), never a silent "the engine covers it now". */
            const notice = window.OFAPHINT ? OFAPHINT.skippedNotice(restarted) : null;
            if (notice) OFAPHINT.paintNotice(notice, banner);
            else toast(banner, bad
                ? `saved, but the engine restart failed: ${restarted.error || 'unknown'}`
                : `${what} ${state} — the engine covers it now`, bad ? 'err' : 'info');
        } else {
            toast(banner, `${what} ${state} — saved. Start the engine to stream it.`, 'info');
        }
        /* The top bar's switcher is rebuilt HERE, after the save/restart has settled. Without this
           the switcher kept the option set it booted with: the boot-time build already ran, and a
           running→running restart never trips applyStatus's stopped→running transition (measured:
           a row switched on in the panel, the switcher still listing only the old set). */
        await refreshInstruments();
    } catch (e) {
        toast(banner, 'instrument save failed: ' + e, 'err', 'fix.no_instruments');
    }
}

$("#instTable").addEventListener('change', (ev) => {
    const box = ev.target && ev.target.closest ? ev.target.closest('[data-role="enabled"]') : null;
    if (!box) return;
    const tr = box.closest('tr');
    queueInstrumentApply(tr ? tr.dataset.symbol : '', !!box.checked);
});

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

/* F-2 (control-surface audit): the Data-source dropdown offered five of the nine values the
   store accepts — binance / okx / hyperliquid / ninjatrader were unreachable from Settings.
   The list is built from the Data menu's own endpoint so the two surfaces cannot drift; the
   combined choices (both / all) stay. A failed fetch leaves the static fallback standing. */
let sourceOptionsFilled = false;
async function fillSourceOptions() {
    const sel = $("#setSource");
    if (!sel) return;
    try {
        const res = await api('/api/control/sources');
        const rows = (res && res.sources) || [];
        if (!rows.length) return;
        const want = String((S.config && S.config.data_source) || '');
        const attr = (s) => String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        sel.innerHTML =
            rows.map((r) => `<option value="${attr(r.id)}" title="${attr(r.hint || '')}">${attr(r.name)}</option>`).join('')
            + `<option value="both" title="Bybit and MT5 together — the older combined choice">Bybit + MT5</option>`
            + `<option value="all" title="Every configured venue — MT5 + Alpaca + every exchange">All of them</option>`;
        /* A `<select>` only holds what it offers: re-select the stored value only when it exists. */
        if (Array.from(sel.options).some((o) => o.value === want)) sel.value = want;
    } catch (e) { /* offline: the static fallback list stands */ }
}
/* The list is built once at boot — before the view is ever opened — so opening Settings can never
   show the bygone five-value fallback while the real venue matrix sits one click away. */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
        if (!sourceOptionsFilled) { sourceOptionsFilled = true; void fillSourceOptions(); }
    });
} else if (!sourceOptionsFilled) {
    sourceOptionsFilled = true;
    void fillSourceOptions();
}

function renderSettings() {
    const c = S.config;
    if (!sourceOptionsFilled) { sourceOptionsFilled = true; void fillSourceOptions(); }
    $("#setSource").value = c.data_source;
    $("#setCooldown").value = c.risk.signal_cooldown_seconds;
    $("#setScore").value = c.risk.min_composite_score;
    $("#setLogLevel").value = c.logging.level;
    $("#setTgToken").value = c.telegram.bot_token || '';
    $("#setTgChat").value = c.telegram.chat_id || '';
    /* §83: the Telegram master switch had no reader and no writer — the box was painted, never
       restored, never collected and never saved, so routing order-flow alerts to Telegram could
       not be switched on from the UI at all. It is a stored setting; show it and save it. */
    if ($("#setTgEnabled")) $("#setTgEnabled").checked = !!c.telegram.enabled;
    /* §83: view state the user sets by hand (chart range/timeframe/markers/VP, log filter) is
       restored from the config now — a restart used to put every one of them back to factory. */
    const chartUI = (c.ui && c.ui.chart) || {};
    const rangeSel = $("#rangeSelect");
    if (rangeSel && chartUI.range) {
        const wanted = String(chartUI.range);
        if (Array.from(rangeSel.options).some((o) => o.value === wanted)) {
            rangeSel.value = wanted;
            S.range = Number(chartUI.range);
        }
    }
    /* §83 continued: the timeframe comes back the same way — and only when the dropdown really
       carries the value, so a hand-edited file cannot park the chart on a bar size it cannot show. */
    const tfSel = $("#tfSelect");
    if (tfSel && chartUI.tf) {
        const wantedTf = String(chartUI.tf);
        if (Array.from(tfSel.options).some((o) => o.value === wantedTf)) {
            tfSel.value = wantedTf;
            S.tf = Number(chartUI.tf);
        }
    }
    if ($("#ovMarkers")) $("#ovMarkers").checked = chartUI.markers !== false;
    if ($("#ovVP")) $("#ovVP").checked = chartUI.vp !== false;
    const logsUI = (c.ui && c.ui.logs) || {};
    if ($("#logAuto")) $("#logAuto").checked = logsUI.auto !== false;
    if ($("#logLevel")) $("#logLevel").value = logsUI.level || '';
    const tg = $("#tgPill");
    const on = !!(c.telegram.bot_token && c.telegram.chat_id);
    tg.className = 'pill ' + (on ? 'running' : '');
    $("#tgPillText").textContent = on
        ? (c.telegram.enabled ? 'configured' : 'configured — switch off')
        : 'not configured';
    const mt5 = S.caps && S.caps.mt5;
    $("#sourceHint").textContent = mt5 && !mt5.available ? `MT5 unavailable here — ${mt5.reason}` : 'MT5 bridge ready';
    renderThresholds();
    /* The number fields above were written programmatically — re-pair each with its preset
       chip (a bare value write fires no event). */
    if (window.OFAPPRESETS && OFAPPRESETS.refresh) OFAPPRESETS.refresh();
}

/* The Data menu switches the source through /api/control/source; the Settings card keeps its own
   select and rebuilds a full config on save — a stale one there would show the old venue and SAVE
   it back over the switch. The menu announces; this form re-seeds when it is the live view. */
document.addEventListener('ofap:source', () => {
    if (typeof truthyView === 'function' && truthyView('settings')) renderSettings();
});

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
    /* §83: start from what is ON DISK, not from the copy this page loaded — a save built on a
       stale snapshot rolled back anything written since boot (a drawing, a layout, a newly added
       instrument). The form owns the fields it collects; everything else is whatever is stored. */
    let base = S.config;
    try { base = await api('/api/control/config'); } catch (e) { /* offline: the page's copy */ }
    const cfg = JSON.parse(JSON.stringify(base));
    cfg.data_source = $("#setSource").value;
    cfg.risk.signal_cooldown_seconds = parseFloat($("#setCooldown").value) || 30;
    cfg.risk.min_composite_score = parseFloat($("#setScore").value) || 40;
    cfg.logging.level = $("#setLogLevel").value;
    cfg.telegram.bot_token = $("#setTgToken").value.trim();
    cfg.telegram.chat_id = $("#setTgChat").value.trim();
    cfg.telegram.enabled = !!($("#setTgEnabled") || {}).checked;
    cfg.instruments = collectInstruments();
    cfg.ui = cfg.ui || {};
    cfg.ui.chart = {
        range: parseInt(($("#rangeSelect") || {}).value, 10) || 0,
        markers: !!($("#ovMarkers") || {}).checked,
        vp: !!($("#ovVP") || {}).checked,
        tf: parseInt(($("#tfSelect") || {}).value, 10) || 60,
    };
    cfg.ui.logs = {
        auto: !!($("#logAuto") || {}).checked,
        level: (($("#logLevel") || {}).value || ''),
    };
    if (typeof collectAtlasSettings === 'function') collectAtlasSettings(cfg);
    return cfg;
}

/* §83: a view-state change is written through the same merge path the settings form uses —
   a small patch, never a whole-config replace from a possibly stale page copy. */
async function saveUIState(patch) {
    try {
        const r = await api('/api/control/config', { method: 'POST', body: { ui: patch } });
        S.config = r.config;
    } catch (e) { /* the view keeps working; the next change retries */ }
}

async function saveSettings(restart = false) {
    const out = $("#saveResult");
    out.textContent = 'saving…';
    try {
        const cfg = await collectSettings();
        const r = await api('/api/control/config', { method: 'POST', body: cfg });
        S.config = r.config;
        if (window.OFAPFRESH && OFAPFRESH.setWindows) OFAPFRESH.setWindows((r.config.atlas || {}).freshness);
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
    if (window.OFAPFRESH && OFAPFRESH.setWindows) OFAPFRESH.setWindows((d.config.atlas || {}).freshness);
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

/* R5: the storage line — the DB has numbers now, and the Logs panel is where people look
   when something feels slow. Fetched with the logs; the route caches its own 30 s. */
async function loadStorage() {
    try {
        const d = await api('/api/control/storage');
        const el = $("#logStorage");
        if (!el) return;
        const human = (n) => {
            const v = Number(n) || 0;
            return v >= 1e9 ? (v / 1e9).toFixed(2) + ' GB' : (v / 1e6).toFixed(1) + ' MB';
        };
        const rows = d.tables && typeof d.tables.ticks === 'number' && d.tables.ticks >= 0 ? d.tables.ticks : null;
        const keep = d.retention && d.retention.days > 0 ? `${d.retention.days} d` : 'forever';
        const prune = d.last_prune && d.last_prune.deleted != null
            ? ` · last prune −${Number(d.last_prune.deleted).toLocaleString()} rows` : '';
        /* The stopped-engine read answers from the file itself, so the newest-tick age and the
           reclaimable bytes are real with the engine off too — and the prune note survives a
           restart now (it is read back from the store, not only from the engine's memory). */
        const ageText = (ms) => {
            const s = Math.max(0, Math.round(ms / 1000));
            if (s < 90) return `${s} s`;
            if (s < 5400) return `${Math.round(s / 60)} min`;
            return `${(s / 3600).toFixed(1)} h`;
        };
        const newest = d.ticks && d.ticks.newest_ms
            ? `newest tick ${ageText(Date.now() - d.ticks.newest_ms)} ago` : '';
        const reclaim = d.reclaimable_bytes > 0
            ? `reclaimable ${human(d.reclaimable_bytes)} — the next vacuum frees it` : '';
        const pruneLine = d.last_prune && d.last_prune.at_ms
            ? `last prune ${ageText(Date.now() - d.last_prune.at_ms)} ago · −${Number(d.last_prune.deleted || 0).toLocaleString()} rows`
            : 'no prune has run yet';
        el.textContent = `storage: ${human(d.bytes + (d.wal_bytes || 0))}`
            + (rows != null ? ` · ${(rows / 1e6).toFixed(1)} M ticks` : '')
            + ` · keep ${keep}` + prune;
        el.title = [
            `db: ${d.db_path}`,
            `file ${human(d.bytes)} · wal ${human(d.wal_bytes || 0)}`,
            rows != null ? `ticks ${rows.toLocaleString()}` : (d.engine_running ? '' : 'row counts need the engine running'),
            newest,
            reclaim,
            `retention ${keep} · prune every ${d.retention ? d.retention.prune_interval_hours : '?'} h`,
            pruneLine,
            d.retention ? `session starts ${String(d.retention.session_start_hour).padStart(2, '0')}:00 UTC` : '',
        ].filter(Boolean).join('\n');
    } catch (e) { /* the line is a bonus; the logs matter more */ }
}

async function loadLogs() {
    loadStorage();
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
$("#logLevel").onchange = () => { loadLogs();
    void saveUIState({ logs: { level: $("#logLevel").value } }); };
$("#logAuto").onchange = () => { void saveUIState({ logs: { auto: $("#logAuto").checked } }); };
$("#btnLogClear").onclick = async () => { await api('/api/control/logs/clear', { method: 'POST' }); loadLogs(); };

/* ══════════════════════════════════════════════════════════════
   Panel refresh orchestration
   ══════════════════════════════════════════════════════════════ */

async function refreshAllPanels(resetChart = false) {
    await refreshInstruments();
    renderThresholds();
    /* The loads are collected and awaited: the symbol switch's busy rings ride this promise,
       and a ring that clears before the new instrument's data has landed would say "done"
       while every panel is still fetching. The loads themselves stay independent — one that
       fails must not cancel the others (allSettled, never all). */
    const loads = [];
    if (truthyView('chart') || resetChart) loads.push(loadChart());
    if (S.inst.footprint) { wireFootprintControls(); loads.push(loadFootprint()); }
    if (S.inst.book) loads.push(loadOrderbook());
    if (S.inst.tape) loads.push(loadTape());
    if (S.inst.perf) loads.push(loadPerformance());
    loads.push(loadStrategy());
    loads.push(loadSignals());
    await Promise.allSettled(loads);
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
