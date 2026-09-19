/* ══════════════════════════════════════════════════════════════════
   Fold-ins from the reference layout SDK documentation (docs.atas.net).

   1. Market Pressure panel — the paired buy/sell sub-panel the reference layout ships as
      `HeatmapMarketPressureIndicator`. Our CVD series already carries per-bucket
      buy and sell volume, so this is a pure visualisation: buy above the
      midline, sell below, delta line across it, plus the window totals.

   2. Repaint governor for the heatmap canvas — the reference layout's performance guide is
      explicit that the render path is a hot path: subscribe to the layouts you
      need, "Draw only what is visible", "Call RedrawChart() sparingly", and let
      the renderer compare a Version per frame instead of uploading every pass.
      We wrap the base `drawHeatmap` so a poll that carries the same version
      (and the same overlay flags and canvas size) does not repaint, and so
      repaints are coalesced to a frame budget.

   Loaded by atlas-v2.js alongside guide.js / context.js.

   THE CVD SERIES IS A SHARED CHANNEL, not this card's private poll: atlas.js's own CVD chart reads
   the same url, so both join one OFAPBUS channel (see the constants below for why the shared rate
   is 5 s). With no delivery layer loaded this card owns a 4 s timer exactly as it always did.
   ══════════════════════════════════════════════════════════════════ */

const PRESSURE = { sig: null, buckets: 90, timer: null, polling: 'idle', unsubscribe: null, key: '' };
const GOVERNOR = { lastTs: 0, minGapMs: 400, skips: 0, throttled: 0, painted: 0, sig: '' };

/* ── one dataset, one channel ────────────────────────────────────────────────────────────────────
   atlas.js draws the CVD chart from the SAME url this card reads (/api/atlas/cvd/<symbol>), so the
   two panels used to poll it on two timers — 28 requests a minute for one series, measured. The
   series is one dataset, so it is one bus channel: the first subscriber starts it, the second joins
   it, and both repaint from the same payload on the same tick. A bus channel keys on (method, url,
   params) and NOT on the interval, so the two halves have to ask for one rate — MP_SHARE_MS, which
   is atlas.js's own cadence in the shell's 5 s slow-panel loop. Without a delivery layer this panel
   keeps its own timer at MP_OWN_MS and nothing about it changes. */
const MP_VIEW = '.view[data-view="cvd"]';
const MP_OWN_MS = 4000;        /* this panel's own cadence, for a page with no OFAPBUS */
const MP_SHARE_MS = 5000;      /* the shared CVD channel's cadence */

const MP_STYLE = `
.mp-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 8px; }
.mp-kpi { background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06); border-radius: 8px; padding: 7px 10px; }
.mp-kpi .lbl { font-size: 11px; opacity: .65; display: block; }
.mp-kpi .val { font-size: 15px; font-weight: 600; }
.mp-kpi .sub { font-size: 11px; opacity: .55; }
.mp-buy { color: #4ade80; } .mp-sell { color: #f87171; }
.mp-legend { display: flex; gap: 14px; font-size: 11.5px; opacity: .7; margin-top: 6px; }
.mp-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
`;

function mpNum(n, digits) {
    if (n === null || n === undefined || Number.isNaN(n)) return '--';
    const abs = Math.abs(n);
    if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return Number(n).toFixed(digits === undefined ? 2 : digits);
}

/* ── panel ────────────────────────────────────────────────────────── */

function mpMount() {
    const view = document.querySelector('.view[data-view="cvd"]');
    if (!view || document.getElementById('mpCard')) return;
    const style = document.createElement('style');
    style.id = 'mpStyles';
    style.textContent = MP_STYLE;
    document.head.appendChild(style);

    const card = document.createElement('div');
    card.className = 'card';
    card.id = 'mpCard';
    card.style.marginTop = '12px';
    card.innerHTML = `
        <div class="card-head">
            <span class="card-title">Market pressure <span class="dim" style="font-weight:400">· buy vs sell per bucket</span></span>
            <div class="spacer"></div>
            <span class="dim" id="mpStamp" title="Aggressor split per time bucket. Green above the line is buying, red below is selling; the amber line is their running difference."></span>
            <button class="btn small" id="mpRefresh" title="Fetch the delta series again now">Refresh</button>
        </div>
        <div class="card-body">
            <div class="mp-kpis" id="mpKpis"><div class="dim">waiting for the engine…</div></div>
            <canvas id="mpCanvas" height="190" title="Paired buy/sell volume per bucket — the sub-panel the reference layout calls Market Pressure"></canvas>
            <div class="mp-legend">
                <span><span class="mp-swatch" style="background:#4ade80"></span>buy aggressor</span>
                <span><span class="mp-swatch" style="background:#f87171"></span>sell aggressor</span>
                <span><span class="mp-swatch" style="background:#fbbf24"></span>delta (buy − sell)</span>
                <span class="dim" id="mpNote"></span>
            </div>
        </div>`;
    view.appendChild(card);
    const btn = document.getElementById('mpRefresh');
    if (btn) btn.onclick = () => mpLoad(true);
}

function mpDraw(series) {
    const el = document.getElementById('mpCanvas');
    if (!el) return;
    const dpr = window.devicePixelRatio || 1;
    const cssH = 190;
    /* §72: the CSS box is the layout's (container-wide, 190 px tall) and only the backING store
       carries the display scale. Without an explicit box the canvas displayed at its backing size,
       so the generic fit pass multiplied it by dpr on every pass — measured 480×285 → 720×428 in a
       single fit at 150%, and it grew again on the next draw. */
    if (el.style) { el.style.width = '100%'; el.style.height = cssH + 'px'; }
    const cssW = Math.max(320, el.clientWidth || el.parentElement.clientWidth || 640);
    /* D-09: assigning width/height reallocates + blanks the canvas even when the size is
       unchanged (which is every poll). Only a real layout change touches the backing store. */
    const w = Math.floor(cssW * dpr);
    const h = Math.floor(cssH * dpr);
    if (el.width !== w || el.height !== h) { el.width = w; el.height = h; }
    PRESSURE.lastSeries = series;                                  // the relayout redraw's input (§72)
    const ctx = el.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const rows = series.slice(-PRESSURE.buckets);
    if (!rows.length) {
        ctx.fillStyle = '#67758f';
        ctx.font = '13px system-ui';
        ctx.fillText('no delta history yet — start the engine or run a replay', 14, 28);
        return;
    }
    const padL = 46, padR = 8, padT = 12, padB = 18;
    const plotW = cssW - padL - padR, plotH = cssH - padT - padB;
    const mid = padT + plotH / 2;
    const maxVol = Math.max(1e-9, ...rows.map((r) => Math.max(Number(r.buy) || 0, Number(r.sell) || 0)));
    const deltas = rows.map((r) => (Number(r.buy) || 0) - (Number(r.sell) || 0));
    const maxDelta = Math.max(1e-9, ...deltas.map((d) => Math.abs(d)));

    // grid + midline
    ctx.strokeStyle = 'rgba(255,255,255,.12)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, mid); ctx.lineTo(cssW - padR, mid); ctx.stroke();
    ctx.fillStyle = '#67758f';
    ctx.font = '10px system-ui';
    ctx.fillText('0', 8, mid + 3);
    ctx.fillText(mpNum(maxVol), 4, padT + 9);

    const step = plotW / rows.length;
    const barW = Math.max(1, step * 0.62);
    rows.forEach((r, i) => {
        const x = padL + i * step + (step - barW) / 2;
        const buy = Number(r.buy) || 0;
        const sell = Number(r.sell) || 0;
        const hBuy = (buy / maxVol) * (plotH / 2 - 2);
        const hSell = (sell / maxVol) * (plotH / 2 - 2);
        ctx.fillStyle = 'rgba(74,222,128,.85)';
        ctx.fillRect(x, mid - hBuy, barW, hBuy);
        ctx.fillStyle = 'rgba(248,113,113,.85)';
        ctx.fillRect(x, mid, barW, hSell);
    });

    // delta line (right-scaled against its own max)
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    rows.forEach((r, i) => {
        const d = (Number(r.buy) || 0) - (Number(r.sell) || 0);
        const x = padL + i * step + step / 2;
        const y = mid - (d / maxDelta) * (plotH / 2 - 4);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    const first = rows[0], last = rows[rows.length - 1];
    ctx.fillStyle = '#67758f';
    ctx.fillText(new Date(first.t).toLocaleTimeString().slice(0, 5), padL, cssH - 5);
    ctx.fillText(new Date(last.t).toLocaleTimeString().slice(0, 5), cssW - padR - 30, cssH - 5);
}

function mpRender(data) {
    const rows = data.series || [];
    const rows2 = rows.slice(-PRESSURE.buckets);
    const buy = rows2.reduce((a, r) => a + (Number(r.buy) || 0), 0);
    const sell = rows2.reduce((a, r) => a + (Number(r.sell) || 0), 0);
    const delta = buy - sell;
    const total = buy + sell;
    const share = total > 0 ? (buy / total) * 100 : 0;

    const kpis = document.getElementById('mpKpis');
    if (kpis) {
        kpis.innerHTML = `
            <div class="mp-kpi" title="Aggressive buying in the plotted window (a bucket is the CVD series step, not a candle).">
                <span class="lbl">Buy aggressor</span><span class="val mp-buy">${mpNum(buy)}</span>
                <span class="sub">${share.toFixed(1)}% of volume</span></div>
            <div class="mp-kpi" title="Aggressive selling in the plotted window.">
                <span class="lbl">Sell aggressor</span><span class="val mp-sell">${mpNum(sell)}</span>
                <span class="sub">${(100 - share).toFixed(1)}% of volume</span></div>
            <div class="mp-kpi" title="Buy minus sell across the window. Sign matches the CVD slope.">
                <span class="lbl">Window delta</span>
                <span class="val ${delta >= 0 ? 'mp-buy' : 'mp-sell'}">${delta >= 0 ? '+' : ''}${mpNum(delta)}</span>
                <span class="sub">slope ${data.slope === undefined ? '--' : data.slope}</span></div>
            <div class="mp-kpi" title="Each bar is one bucket: green above the midline is buying, red below is selling.">
                <span class="lbl">Buckets plotted</span><span class="val">${rows2.length}</span>
                <span class="sub">${rows2.length ? new Date(rows2[0].t).toLocaleTimeString().slice(0, 5) + ' → ' + new Date(rows2[rows2.length - 1].t).toLocaleTimeString().slice(0, 5) : ''}</span></div>`;
    }
    const stamp = document.getElementById('mpStamp');
    if (stamp) stamp.textContent = 'updated ' + new Date().toLocaleTimeString();
    const note = document.getElementById('mpNote');
    if (note) note.textContent = (data.symbol || '').toUpperCase() + ' · source: /api/atlas/cvd series'
        + (PRESSURE.polling === 'bus' ? ' · polling ' + (MP_SHARE_MS / 1000) + 's via the shared bus'
            : (PRESSURE.polling === 'timer' ? " · polling " + (MP_OWN_MS / 1000) + "s from this panel's own timer (no bus)" : ''));
    mpDraw(rows2);
}

/* ── reading: the shared channel first, this panel's own tick only when there is no bus ──────── */

function mpView() {
    return document.querySelector(MP_VIEW);
}

function mpSymbol() {
    return (typeof S !== 'undefined' && S.symbol) || (document.getElementById('symbolSelect') || {}).value || 'BTCUSDT';
}

function mpUrl(symbol) {
    return '/api/atlas/cvd/' + encodeURIComponent(symbol);
}

function mpFail(err) {
    const kpis = document.getElementById('mpKpis');
    if (kpis) kpis.innerHTML = `<div class="dim">pressure unavailable — ${esc(String(err))}</div>`;
    return false;
}

/* Whichever way a payload arrives — a direct read, the shared channel, the Refresh button — it
   lands here, so the two paths cannot drift in what they show. `manual` skips the unchanged-signature
   shortcut, which is what makes Refresh a refresh. */
function mpApply(data, manual) {
    if (!data || typeof data !== 'object') return mpFail('empty payload');
    if (data.error) return mpFail(data.error);
    const rows = data.series || [];
    const sig = [data.symbol || mpSymbol(), rows.length, rows.length ? rows[rows.length - 1].t : 0].join('|');
    if (!manual && sig === PRESSURE.sig) return false;          // nothing new to show
    PRESSURE.sig = sig;
    mpRender(data);
    return true;
}

/* One read, now: the Refresh button, and the asker when no delivery layer is loaded. */
async function mpLoad(manual) {
    const view = mpView();
    if (!view || !view.classList.contains('active')) return false;
    const symbol = mpSymbol();
    try {
        const bus = window.OFAPBUS;
        /* the path stays spelled out at an api() call site so scripts/audit_ui_refs.py can resolve it */
        const data = (bus && typeof bus.request === 'function')
            ? await bus.request(mpUrl(symbol))
            : await api('/api/atlas/cvd/' + encodeURIComponent(symbol));
        return mpApply(data, manual);
    } catch (e) {
        return mpFail(e);
    }
}

function mpStopPoll() {
    const was = PRESSURE.polling;
    if (PRESSURE.unsubscribe) {
        try { PRESSURE.unsubscribe(); } catch (e) { /* the delivery layer is gone; nothing to release */ }
        PRESSURE.unsubscribe = null;
    }
    if (PRESSURE.timer) {
        clearInterval(PRESSURE.timer);
        PRESSURE.timer = null;
    }
    PRESSURE.polling = 'idle';
    PRESSURE.key = '';
    return was !== 'idle';
}

/* One place decides it: the visible section, then the instrument. A hidden panel releases the shared
   channel — the bus is refcounted, so a subscriber left behind is a poller nobody is watching. */
function mpSync() {
    const view = mpView();
    if (!view || !view.classList.contains('active')) { mpStopPoll(); return false; }
    const url = mpUrl(mpSymbol());
    const bus = window.OFAPBUS;
    const viaBus = !!(bus && typeof bus.subscribe === 'function');
    /* Already live on this key AND on the right mechanism: a delivery layer that appeared after this
       panel synced must take the channel over, and one that went away must not leave it behind. */
    if (PRESSURE.polling !== 'idle' && PRESSURE.key === url && (PRESSURE.polling === 'bus') === viaBus) {
        return true;
    }
    mpStopPoll();
    PRESSURE.key = url;
    if (viaBus) {
        PRESSURE.polling = 'bus';
        PRESSURE.unsubscribe = bus.subscribe({ url: url, intervalMs: MP_SHARE_MS }, (payload) => { mpApply(payload, false); });
        return true;
    }
    PRESSURE.polling = 'timer';
    void mpLoad(false);
    PRESSURE.timer = setInterval(() => {
        if (window.OFAPINTENT && OFAPINTENT.anyHeld()) return;   // never repaint over the user's hands
        if (PRESSURE.polling === 'timer') void mpLoad(false);
    }, MP_OWN_MS);
    return true;
}

/* Wired once: the section's class is how the shell says "on screen" (terminal mode moves the section
   rather than rebuilding it), and the instrument select is how the channel key moves. */
function mpWatch() {
    const view = mpView();
    if (view && typeof MutationObserver === 'function') {
        new MutationObserver(() => { mpSync(); }).observe(view, { attributes: true, attributeFilter: ['class'] });
    }
    const select = document.getElementById('symbolSelect');
    if (select && select.addEventListener) select.addEventListener('change', () => { mpSync(); });
    mpSync();
}

/* ── repaint governor for the base heatmap canvas ─────────────────── */

function mpGovernor() {
    if (typeof window.drawHeatmap !== 'function' || window.drawHeatmap.__governed) return false;
    const base = window.drawHeatmap;
    const wrapped = function (data) {
        const el = document.getElementById('heatmapCanvas');
        const sig = [
            data && data.version,
            data && (data.buckets || []).length,
            data && (data.prices || []).length,
            document.getElementById('hmTrades')?.checked ? 1 : 0,
            document.getElementById('hmEvents')?.checked ? 1 : 0,
            el ? el.clientWidth + 'x' + el.clientHeight : '',
        ].join('|');
        const now = performance.now();
        if (sig === GOVERNOR.sig && now - GOVERNOR.lastTs < 5000) {
            GOVERNOR.skips += 1;                                 // same version → nothing to upload
            GOVERNOR.note();
            return undefined;
        }
        if (now - GOVERNOR.lastTs < GOVERNOR.minGapMs) {
            GOVERNOR.throttled += 1;                             // coalesce repaints to a frame budget
            GOVERNOR.sig = sig;                                  // remember: this content is on screen next paint
            GOVERNOR.note();
            return undefined;
        }
        GOVERNOR.sig = sig;
        GOVERNOR.lastTs = now;
        GOVERNOR.painted += 1;
        GOVERNOR.note();
        return base(data);
    };
    wrapped.__governed = true;
    window.drawHeatmap = wrapped;
    GOVERNOR.note = () => {
        const el = document.getElementById('heatmapCanvas');
        if (!el) return;
        /* Hover-info audit: this used to REPLACE the canvas's tooltip with repaint counters, so a
           user hovering the depth map got diagnostics instead of what they were looking at. The
           counters are appended to the description now (and the static title lives in index.html). */
        const baseTitle = el.getAttribute('data-base-title') || el.title || '';
        if (!el.getAttribute('data-base-title')) el.setAttribute('data-base-title', baseTitle);
        el.title = baseTitle + ` Repaints: ${GOVERNOR.painted} painted · ${GOVERNOR.skips} skipped · `
            + `${GOVERNOR.throttled} coalesced (${GOVERNOR.minGapMs} ms frame budget). `
            + 'This is the reference layout performance guidance: redraw sparingly, upload only on change.';
    };
    return true;
}

/* ── boot ─────────────────────────────────────────────────────────── */

(function mpBoot() {
    let governorStarted = false;
    const start = () => {
        mpMount();
        if (!governorStarted) {
            governorStarted = true;
            setTimeout(() => { mpGovernor(); }, 1200);
        }
        /* One entry point: it subscribes to the shared CVD channel (or owns the timer when no bus is
           loaded), releases it when this panel leaves the screen, and re-keys it on a symbol move. */
        mpWatch();
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(start, 1700));
    } else {
        setTimeout(start, 1700);
    }
    if (typeof window.showView === 'function' && !window.showView.__mpWrapped) {
        const baseShow = window.showView;
        const wrappedShow = function (name, ...rest) {
            const out = baseShow(name, ...rest);
            if (name === 'cvd') {
                /* joining the channel repaints this card from the live payload it already carries;
                   with no delivery layer the forced read below is what this hook always did */
                setTimeout(() => { if (mpSync() && PRESSURE.polling === 'timer') void mpLoad(true); }, 400);
            }
            if (name === 'heatmap') {
                GOVERNOR.sig = '';                               // force the next paint
                setTimeout(() => { mpGovernor(); }, 300);
            }
            return out;
        };
        wrappedShow.__mpWrapped = true;
        window.showView = wrappedShow;
    }
    /* §72: a window resize or a display-scale change repaints from the series already in hand —
       the same draw path the poll uses, so the two can never drift. A hidden card has no box. */
    document.addEventListener('ofap:relayout', () => {
        const el = document.getElementById('mpCanvas');
        if (!el || !el.clientWidth) return;                      // off-screen: nothing to repaint
        if (window.OFAPINTENT && OFAPINTENT.anyHeld()) return;
        try { mpDraw(PRESSURE.lastSeries || []); } catch (e) { /* the card's own path reports its faults */ }
    });
})();

window.PRESSURE = PRESSURE;
window.GOVERNOR = GOVERNOR;
