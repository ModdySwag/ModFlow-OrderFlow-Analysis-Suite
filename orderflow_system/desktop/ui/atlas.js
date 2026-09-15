/* ══════════════════════════════════════════════════════════════════
   reference-style feature views for the OrderFlow desktop shell:
   heatmap · trackers (iceberg/sweeps/stop runs/big trades/liquidations)
   · CVD + CVD Pro · Market Profile (TPO) · Frames · Replay · Alerts.

   Loads after ui.js and reuses its globals (S, $, api, fmt, compact,
   esc, toast, truthyView, capture helpers).

   TWO OF THE VIEWS SHARE THEIR SERIES WITH THE ADD-ON CARDS: the CVD chart shares
   /api/atlas/cvd/<symbol> with market-pressure.js, the Trackers tables share /api/atlas/tape/<symbol>
   with atlas-v2.js's big-trade-zone card. Both become ONE OFAPBUS channel (ATLAS_SHARE below) when
   the delivery layer is loaded; without it this module keeps its own direct reads.
   ══════════════════════════════════════════════════════════════════ */

const A = {
    heat: { auto: true, last: null },
    replay: { loaded: false, dragging: false },
    alerts: [],
    liveTicks: 0,
};

/* ── canvas helpers ─────────────────────────────────────────────── */

function prepCanvas(el, height) {
    if (!el) return null;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(320, el.clientWidth || (el.parentElement ? el.parentElement.clientWidth : 800) || 800);
    const h = height || 520;
    el.width = Math.round(w * dpr);
    el.height = Math.round(h * dpr);
    el.style.height = h + 'px';
    const ctx = el.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx, w, h };
}

/* value → heat colour (dark blue → cyan → green → yellow → red) */
function heatColour(t) {
    const x = Math.max(0, Math.min(1, t));
    const hue = 225 - 225 * Math.pow(x, 0.85);
    const light = 12 + 46 * x;
    const sat = 75 - 20 * x;
    return 'hsl(' + hue + ', ' + sat + '%, ' + light + '%)';
}

function drawHeatmap(data) {
    const el = document.getElementById('heatmapCanvas');
    const c = prepCanvas(el, 520);
    if (!c) return;
    const ctx = c.ctx, w = c.w, h = c.h;
    const cols = (data.buckets || []).length;
    const rows = (data.prices || []).length;
    if (!cols || !rows) {
        ctx.fillStyle = '#67758f';
        ctx.font = '13px system-ui';
        ctx.fillText('no depth history yet — start the engine or run a replay', 16, 30);
        return;
    }
    const axisR = 74, axisB = 22;
    const plotW = w - axisR, plotH = h - axisB;
    const cw = plotW / cols, chh = plotH / rows;

    const flat = [];
    for (const row of data.values) for (const v of row) if (v > 0) flat.push(v);
    flat.sort((a, b) => a - b);
    // the reference layout "Upper Cut-off %": the server reports the scale max, so the top share
    // of resting size saturates instead of one outlier whitening the whole map.
    const ref = (data.scale_max > 0) ? data.scale_max
        : (flat.length ? flat[Math.floor(flat.length * 0.99)] : 1);

    for (let r = 0; r < rows; r++) {
        const y = plotH - (r + 1) * chh;
        const row = data.values[r];
        for (let ci = 0; ci < cols; ci++) {
            const v = row[ci];
            if (v <= 0) continue;
            ctx.fillStyle = heatColour(v / ref);
            ctx.fillRect(ci * cw, y, Math.max(1, cw + 0.4), Math.max(1, chh + 0.4));
        }
    }

    const tradesBox = document.getElementById('hmTrades');
    if (tradesBox && tradesBox.checked && data.traded) {
        const tf = [];
        for (const row of data.traded) for (const v of row) if (v > 0) tf.push(v);
        tf.sort((a, b) => a - b);
        const tmax = tf.length ? tf[tf.length - 1] : 1;
        for (let r = 0; r < rows; r++) {
            for (let ci = 0; ci < cols; ci++) {
                const v = data.traded[r][ci];
                if (v <= 0) continue;
                const rad = 1.5 + 7 * Math.sqrt(v / tmax);
                ctx.beginPath();
                ctx.arc(ci * cw + cw / 2, plotH - (r + 0.5) * chh, rad, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(255,255,255,0.42)';
                ctx.fill();
                ctx.strokeStyle = 'rgba(10,14,22,0.5)';
                ctx.stroke();
            }
        }
    }

    const evBox = document.getElementById('hmEvents');
    if (evBox && evBox.checked && data.events) {
        const t0 = data.buckets[0];
        const tN = data.buckets[cols - 1] || t0 + 1;
        const step = data.step || 0.5;
        for (const ev of data.events) {
            if (ev.kind !== 'pull' && ev.kind !== 'stack') continue;
            const ci = Math.round(((ev.ts_ms - t0) / Math.max(1, tN - t0)) * (cols - 1));
            let r = -1;
            for (let i = 0; i < rows; i++) {
                if (Math.abs(data.prices[i] - ev.price) <= step / 2 + 1e-9) { r = i; break; }
            }
            if (r < 0 || ci < 0 || ci >= cols) continue;
            const x = ci * cw + cw / 2, y = plotH - (r + 0.5) * chh;
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fillStyle = ev.kind === 'pull' ? 'rgba(183,140,255,0.9)' : 'rgba(90,220,255,0.85)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(10,14,22,0.8)';
            ctx.stroke();
        }
    }

    const best = (data.best || []);
    if (best.length) {
        const lastB = best[best.length - 1];
        const mid = (lastB.bid + lastB.ask) / 2;
        if (mid) {
            const r = (mid - data.prices[0]) / ((data.prices[rows - 1] - data.prices[0]) || 1);
            const y = plotH - r * plotH;
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y);
            ctx.strokeStyle = 'rgba(255,255,255,0.55)';
            ctx.setLineDash([4, 4]); ctx.stroke(); ctx.setLineDash([]);
            ctx.fillStyle = '#e9eef8'; ctx.font = '10px monospace';
            ctx.fillText(mid.toFixed(2), plotW + 6, y + 3);
        }
    }

    ctx.fillStyle = '#67758f'; ctx.font = '10px system-ui';
    for (let i = 0; i < 6; i++) {
        const r = Math.round((rows - 1) * i / 5);
        const price = data.prices[r];
        ctx.fillText(price.toFixed(price > 100 ? 1 : 4), plotW + 6, (plotH - (r + 0.5) * chh) + 3);
    }
    for (let i = 0; i <= 4; i++) {
        const ci = Math.round((cols - 1) * i / 4);
        const x = ci * cw;
        const label = new Date(data.buckets[ci]).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        ctx.fillText(label, Math.min(x, Math.max(0, plotW - 52)), h - 6);
    }
    ctx.strokeStyle = 'rgba(34,48,73,0.9)';
    ctx.strokeRect(0.5, 0.5, plotW, plotH);
}

function drawSeries(canvas, series, opts) {
    const c = prepCanvas(canvas, (opts && opts.height) || 300);
    if (!c) return;
    const ctx = c.ctx, w = c.w, h = c.h;
    const pad = { l: 8, r: 76, t: 12, b: 18 };
    const plotW = w - pad.l - pad.r, plotH = h - pad.t - pad.b;
    ctx.font = '10px system-ui';

    const lines = (series || []).filter((s) => s.values && s.values.length > 1);
    if (!lines.length) {
        ctx.fillStyle = '#67758f';
        ctx.fillText((opts && opts.empty) || 'no data yet', 12, 24);
        return;
    }
    const n = Math.max.apply(null, lines.map((s) => s.values.length));
    lines.forEach((s) => {
        const vals = s.values;
        let min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
        if (min === max) { min -= 1; max += 1; }
        ctx.beginPath();
        vals.forEach((v, i) => {
            const x = pad.l + (i / Math.max(1, n - 1)) * plotW;
            const y = pad.t + plotH - ((v - min) / (max - min)) * plotH;
            i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        });
        ctx.strokeStyle = s.colour;
        ctx.lineWidth = s.width || 1.5;
        if (s.dashed) ctx.setLineDash([5, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        const lastV = vals[vals.length - 1];
        ctx.fillStyle = s.colour;
        ctx.fillText((s.label ? s.label + ' ' : '') + lastV.toFixed(s.dp === undefined ? 2 : s.dp),
            w - pad.r + 6, pad.t + 10 + (s.offset || 0));
    });

    ctx.strokeStyle = 'rgba(34,48,73,0.9)';
    ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, pad.t + plotH); ctx.lineTo(pad.l + plotW, pad.t + plotH); ctx.stroke();

    ((opts && opts.markers) || []).forEach((m) => {
        const x = pad.l + Math.max(0, Math.min(1, m.x)) * plotW;
        ctx.beginPath(); ctx.arc(x, pad.t + plotH - 6, 4, 0, Math.PI * 2);
        ctx.fillStyle = m.colour; ctx.fill();
    });
}

/* ── loaders ────────────────────────────────────────────────────── */

async function loadHeatmap() {
    if (!S.symbol) return;
    const cols = parseInt(document.getElementById('hmColumns').value, 10);
    const rows = parseInt(document.getElementById('hmRows').value, 10);
    try {
        const d = await api('/api/atlas/heatmap/' + encodeURIComponent(S.symbol) + '?columns=' + cols + '&rows=' + rows);
        A.heat.last = d;
        drawHeatmap(d);
        const walls = (d.walls || []).slice(0, 12);
        const w0 = document.getElementById('hmWalls');
        w0.querySelector('.kpi-value').textContent = walls.length ? walls[0].size.toFixed(2) : '--';
        w0.querySelector('.kpi-sub').textContent = walls.length ? '@ ' + walls[0].price : '';
        document.getElementById('hmWallTable').querySelector('tbody').innerHTML =
            walls.map((w) => '<tr><td>' + w.price + '</td><td>' + w.size.toFixed(3) + '</td><td>' +
                (S.lastPrice ? ((w.price - S.lastPrice) / S.lastPrice * 100).toFixed(3) + '%' : '--') + '</td></tr>').join('')
            || '<tr><td colspan="3" class="dim">no walls recorded yet</td></tr>';
        const evs = (d.events || []).filter((e) => e.kind === 'pull' || e.kind === 'stack').slice(-25).reverse();
        document.getElementById('hmEventTable').querySelector('tbody').innerHTML =
            evs.map((e) => '<tr><td>' + new Date(e.ts_ms).toLocaleTimeString() + '</td>' +
                '<td><span class="tag ' + (e.kind === 'pull' ? 'no' : 'ok') + '">' + e.kind + '</span></td>' +
                '<td>' + e.price + '</td><td>' + e.size.toFixed(3) + '</td><td class="name">' + esc(e.detail) + '</td></tr>').join('')
            || '<tr><td colspan="5" class="dim">no stacking/pull events yet</td></tr>';
        const st = d.stats || {};
        document.getElementById('hmStatus').textContent = cols + ' buckets · ' + rows + ' rows · step ' + d.step +
            ' · ' + ((st.book_updates || 0)).toLocaleString() + ' book updates';
        const span = d.prices.length ? (d.prices[d.prices.length - 1] - d.prices[0]) : 0;
        const hs = document.getElementById('hmSpan');
        hs.querySelector('.kpi-value').textContent = String(d.step);
        hs.querySelector('.kpi-sub').textContent = span.toFixed(2) + ' price range';
        document.getElementById('hmStack').querySelector('.kpi-value').textContent = ((st.events || {}).stack || 0);
        document.getElementById('hmPull').querySelector('.kpi-value').textContent = ((st.events || {}).pull || 0);
    } catch (e) { document.getElementById('hmStatus').textContent = String(e); }
}

/* The Trackers tables' own drawing — same shape as paintCvd: one painter, whichever way the
   payload arrived (the shared tape channel, a hand-made read, or the tracker's own session data). */
function paintTrackers(d) {
    const st = d.stats || {};
    const ev = d.events || {};
    document.getElementById('tkBig').querySelector('.kpi-value').textContent = st.big_trades || 0;
    document.getElementById('tkBig').querySelector('.kpi-sub').textContent = (st.blocks || 0) + ' blocks · Δ ' + compact(st.big_delta || 0);
    document.getElementById('tkSweeps').querySelector('.kpi-value').textContent = st.sweeps || 0;
    document.getElementById('tkIcebergs').querySelector('.kpi-value').textContent = st.icebergs || 0;
    const w5 = (st.speed && st.speed.windows && st.speed.windows['5s']) || { trades: 0, volume: 0 };
    document.getElementById('tkSpeed').querySelector('.kpi-value').textContent = (w5.trades || 0) + ' / 5s';
    document.getElementById('tkSpeed').querySelector('.kpi-sub').textContent =
        'z=' + ((st.speed || {}).zscore === undefined ? '--' : st.speed.zscore) + ' · ' + compact(w5.volume || 0) + ' size';
    document.getElementById('tkThreshold').textContent = 'threshold: ' + (st.big_threshold || 0).toFixed(3);

    document.getElementById('tkIcebergTable').querySelector('tbody').innerHTML =
        (ev.icebergs || []).slice().reverse().slice(0, 20).map((i) =>
            '<tr><td>' + new Date(i.ts_ms).toLocaleTimeString() + '</td><td>' + i.price + '</td><td>' + esc(i.side) +
            '</td><td>' + i.fills + '</td><td>' + i.modal_size + '</td><td>' + i.total_size + '</td><td>' + ((i.duration_ms || 0) / 1000).toFixed(1) + 's</td><td><span class="tag warn">' + esc(i.confidence || 'inferred') + '</span></td></tr>').join('')
        || '<tr><td colspan="8" class="dim">none yet — inferred from repeated equal prints</td></tr>';
    document.getElementById('tkSweepTable').querySelector('tbody').innerHTML =
        (ev.sweeps || []).slice().reverse().slice(0, 20).map((s) =>
            '<tr><td>' + new Date(s.ts_ms).toLocaleTimeString() + '</td><td class="' + (s.side === 'buy' ? 'bullish' : 'bearish') + '">' + esc(s.side) +
            '</td><td>' + s.levels + '</td><td>' + s.size + '</td><td>' + s.from_price + ' → ' + s.to_price + '</td><td>' + s.duration_ms + 'ms</td></tr>').join('')
        || '<tr><td colspan="8" class="dim">none yet</td></tr>';
    document.getElementById('tkStopTable').querySelector('tbody').innerHTML =
        (ev.stop_runs || []).slice().reverse().slice(0, 20).map((s) =>
            '<tr><td>' + new Date(s.ts_ms).toLocaleTimeString() + '</td><td>' + esc(s.direction) + '</td><td>' + s.ticks_moved +
            '</td><td>' + s.volume + '</td><td>' + (s.prints || '?') + '</td><td>' + (s.confirmed_by_liquidations ? '<span class="tag ok">confirmed</span>' : '<span class="dim">—</span>') + '</td></tr>').join('')
        || '<tr><td colspan="6" class="dim">none yet</td></tr>';
    document.getElementById('tkBigTable').querySelector('tbody').innerHTML =
        (ev.big_trades || []).slice().reverse().slice(0, 20).map((b) =>
            '<tr><td>' + new Date(b.ts_ms).toLocaleTimeString() + '</td><td class="' + (b.side === 'buy' ? 'bullish' : 'bearish') + '">' + esc(b.side) +
            '</td><td>' + b.price + '</td><td>' + b.size + '</td><td>' + b.multiple + '×</td></tr>').join('')
        || '<tr><td colspan="6" class="dim">none yet</td></tr>';
    const liqs = (ev.liquidations || []).slice().reverse();
    document.getElementById('tkLiqTable').querySelector('tbody').innerHTML =
        liqs.slice(0, 25).map((l) =>
            '<tr><td>' + new Date(l.ts_ms).toLocaleTimeString() + '</td><td>' + l.price + '</td><td>' + l.size + '</td><td>' + esc(l.side) + '</td></tr>').join('')
        || '<tr><td colspan="4" class="dim">no liquidations in this window</td></tr>';
    document.getElementById('tkLiqStats').textContent = liqs.length + ' shown · ' + (st.liquidations || 0) + ' total';
    document.getElementById('navTrackerCount').textContent = String((st.sweeps || 0) + (st.icebergs || 0) + (st.stop_runs || 0));
    toast(document.getElementById('tkBanner'),
        'Iceberg and stop-run trackers are INFERRED — Bybit publishes no market-by-order (order-id) feed. ' +
        'Sweeps, big trades, blocks and speed of tape come straight from the trade prints; stop runs are corroborated by the liquidation stream.',
        'info');
}

/* One read, now — the mirror of loadCvd: with the delivery layer loaded the tape series is a shared
   channel (ATLAS_SHARE) and the channel is the asker, so this only guarantees it is live. */
async function loadTrackers(options) {
    if (!S.symbol) return false;
    if (!(options && options.force) && atlasShareLive('tape')) return true;
    try {
        paintTrackers(await api('/api/atlas/tape/' + encodeURIComponent(S.symbol)));
        return true;
    } catch (e) { console.error(e); return false; }
}

/* The CVD snapshot's own drawing, separated from how it was fetched: the shared channel, a
   hand-made read and the re-anchor button all land here, so the three paths cannot drift. */
function paintCvd(d) {
    document.getElementById('cvdValue').querySelector('.kpi-value').textContent = compact(d.cvd);
    document.getElementById('cvdValue').querySelector('.kpi-sub').textContent =
        d.session_start_ms ? 'from ' + new Date(d.session_start_ms).toLocaleTimeString() : '';
    document.getElementById('cvd1m').querySelector('.kpi-value').textContent = compact((d.windows || {})['60s']);
    document.getElementById('cvd5m').querySelector('.kpi-value').textContent = compact((d.windows || {})['300s']);
    document.getElementById('cvdSlope').querySelector('.kpi-value').textContent = compact(d.slope);
    const div = (d.divergences || []).slice().reverse();
    document.getElementById('cvdDivTable').querySelector('tbody').innerHTML =
        div.slice(0, 15).map((x) =>
            '<tr><td>' + new Date(x.ts_ms).toLocaleTimeString() + '</td><td><span class="tag ' +
            (x.kind === 'bearish' ? 'no' : x.kind === 'bullish' ? 'ok' : 'warn') + '">' + esc(x.kind) + '</span></td>' +
            '<td>' + Math.round(x.strength) + '</td><td class="name">' + esc(x.note) + '</td></tr>').join('')
        || '<tr><td colspan="4" class="dim">no divergence detected yet</td></tr>';
    const series = d.series || [];
    drawSeries(document.getElementById('cvdCanvas'), [
        { values: series.map((s) => s.cvd), colour: '#4f8cff', label: 'CVD', dp: 1, width: 2 },
        { values: series.map((s) => s.price), colour: '#ffb454', label: 'price', dp: 2, dashed: true, offset: 16 },
    ], { height: 300, markers: div.slice(0, 6).map((x, i) => ({ x: 0.95 - i * 0.04, colour: x.kind === 'bearish' ? '#ff5d6c' : '#35d07f' })) });
    const multi = (d.pro_multi && d.pro_multi.bands || []).map((b, i) =>
        (b[1] ? b[0] + '–' + b[1] : b[0] + '+') + ': ' + compact(((d.pro_multi.cvd || [])[i] || 0))).join(' · ');
    document.getElementById('cvdStatus').textContent = series.length + ' buckets · ' + div.length + ' divergences'
        + (multi ? ' · CVD Pro (Multi) ' + multi : '');
}

/* One read, now. With the delivery layer loaded this series is a shared channel (ATLAS_SHARE) and
   the channel is the asker, so the call only guarantees it is live; `force` is for a caller that
   has just changed the data under it (the re-anchor button) and must not wait for the next tick. */
async function loadCvd(options) {
    if (!S.symbol) return false;
    if (!(options && options.force) && atlasShareLive('cvd')) return true;
    try {
        paintCvd(await api('/api/atlas/cvd/' + encodeURIComponent(S.symbol)));
        return true;
    } catch (e) { console.error(e); return false; }
}

async function loadMarketProfile() {
    if (!S.symbol) return;
    try {
        const d = await api('/api/atlas/profile/' + encodeURIComponent(S.symbol) + '?levels=200');
        document.getElementById('mpPoc').querySelector('.kpi-value').textContent = d.poc ? d.poc.toFixed(2) : '--';
        document.getElementById('mpVa').querySelector('.kpi-value').textContent = d.vah ? d.vah.toFixed(2) : '--';
        document.getElementById('mpVa').querySelector('.kpi-sub').textContent = d.val ? 'VAL ' + d.val.toFixed(2) : '';
        const ib = d.ib || {};
        document.getElementById('mpIb').querySelector('.kpi-value').textContent =
            ib.ib_high ? ib.ib_high.toFixed(0) + '/' + ib.ib_low.toFixed(0) : '--';
        document.getElementById('mpIb').querySelector('.kpi-sub').textContent = 'IB high/low (first 2 brackets)';
        const ext = d.range_extension || {};
        document.getElementById('mpExt').querySelector('.kpi-value').textContent = ext.extended ? 'yes' : 'no';
        document.getElementById('mpExt').querySelector('.kpi-sub').textContent =
            'up ' + (ext.extension_up_ticks || 0) + ' / down ' + (ext.extension_down_ticks || 0) + ' ticks';

        const levels = d.levels || [];
        const sp = {};
        (d.single_prints || []).forEach((p) => { sp[Number(p).toFixed(4)] = true; });
        const vah = d.vah || 0, val = d.val || 0;
        document.getElementById('tpoGrid').innerHTML = levels.map((row) => {
            const key = Number(row.price).toFixed(4);
            const cls = row.price === d.poc ? 'tpo-poc' : (row.price <= vah && row.price >= val) ? 'tpo-va' : '';
            return '<div class="tpo-row ' + cls + '"><span class="tpo-price">' + row.price.toFixed(row.price > 100 ? 1 : 4) + '</span>' +
                '<span class="tpo-letters">' + esc(row.letters) + '</span>' +
                '<span class="tpo-vol">' + compact(row.volume) + '</span>' +
                (sp[key] ? '<span class="tag warn">single</span>' : '') + '</div>';
        }).join('') || '<div class="dim" style="padding:12px">no TPO data yet — needs executed prints</div>';
        document.getElementById('mpStatus').textContent = (d.brackets || []).length + ' brackets · ' + levels.length + ' levels';

        const dva = d.developing_value_area || {};
        const virgins = d.virgin_pocs || [];
        const sess = d.session || {};
        document.getElementById('mpReads').innerHTML =
            '<div class="field"><label>Session</label><div class="mono">open ' + (sess.open || 0).toFixed(2) +
            ' · high ' + (sess.high || 0).toFixed(2) + ' · low ' + (sess.low || 0).toFixed(2) +
            ' · ' + (sess.ticks || 0).toLocaleString() + ' prints</div></div>' +
            '<div class="field"><label>Developing value area</label><div class="mono">' + (dva.trend || '--') +
            (dva.drift === undefined ? '' : ' (' + Number(dva.drift).toFixed(2) + ')') +
            ' over ' + ((dva.sessions || []).length) + ' sessions</div></div>' +
            '<div class="field"><label>Virgin POCs (untested magnets)</label><div class="mono">' +
            (virgins.length ? virgins.map((v) => v.session + ' @ ' + Number(v.poc).toFixed(2)).join('<br>') : 'none') + '</div></div>' +
            '<div class="field"><label>Single prints</label><div class="mono">' + ((d.single_prints || []).length) + ' levels</div></div>';
    } catch (e) { console.error(e); }
}

async function loadFrames() {
    if (!S.symbol) return;
    const frame = document.getElementById('frameSelect').value;
    try {
        const d = await api('/api/atlas/frames/' + encodeURIComponent(S.symbol) + '/' + frame + '?count=300');
        const bars = (d.bars || []).slice(-120);
        document.getElementById('frameStatus').textContent = (d.bars || []).length + ' ' + frame + ' bars closed';
        drawSeries(document.getElementById('frameCanvas'), [
            { values: bars.map((b) => b.close), colour: '#4f8cff', label: 'close', dp: 2, width: 2 },
            { values: bars.map((b) => b.delta), colour: '#b78cff', label: 'delta', dp: 1, dashed: true, offset: 16 },
        ], { height: 260, empty: 'no ' + frame + ' bars closed yet' });
        document.getElementById('frameTable').querySelector('tbody').innerHTML =
            bars.slice().reverse().slice(0, 25).map((b) =>
                '<tr><td>' + new Date(b.time * 1000).toLocaleTimeString() + '</td><td>' + b.open + '</td><td>' + b.high +
                '</td><td>' + b.low + '</td><td>' + b.close + '</td><td>' + b.volume + '</td>' +
                '<td class="' + (b.delta >= 0 ? 'bullish' : 'bearish') + '">' + b.delta + '</td><td>' + b.ticks +
                '</td><td>' + b.duration_ms + 'ms</td></tr>').join('')
            || '<tr><td colspan="9" class="dim">no ' + frame + ' bars closed yet</td></tr>';
    } catch (e) { console.error(e); }
}

/* ── replay ─────────────────────────────────────────────────────── */

async function rpStatus() {
    try {
        const d = await api('/api/atlas/replay/status');
        const st = d.status || {};
        const pill = document.getElementById('rpStatePill');
        pill.className = 'pill ' + (st.state === 'playing' ? 'running' : st.state === 'error' ? 'error' : '');
        document.getElementById('rpStateText').textContent = st.state || 'idle';
        document.getElementById('rpTotal').querySelector('.kpi-value').textContent = st.total || 0;
        document.getElementById('rpTotal').querySelector('.kpi-sub').textContent = st.symbol ? st.symbol + ' · ' + (st.mode || '--') : '--';
        document.getElementById('rpIndex').querySelector('.kpi-value').textContent = st.index || 0;
        document.getElementById('rpIndex').querySelector('.kpi-sub').textContent = (st.progress_pct || 0) + '% · ' + (st.remaining || 0) + ' left';
        document.getElementById('rpClock').querySelector('.kpi-value').textContent =
            st.current_ms ? new Date(st.current_ms).toLocaleTimeString() : '--';
        document.getElementById('rpMode').querySelector('.kpi-value').textContent = st.mode || '--';
        document.getElementById('rpMode').querySelector('.kpi-sub').textContent = st.speed ? st.speed + '×' : '';
        document.getElementById('rpProgress').textContent = st.total
            ? st.index + ' / ' + st.total + ' (' + st.progress_pct + '%)'
            : (st.error || 'nothing loaded');
        if (!A.replay.dragging) document.getElementById('rpSeek').value = Math.round((st.progress_pct || 0) * 10);
        A.replay.loaded = !!st.total;
        return st;
    } catch (e) {
        document.getElementById('rpProgress').textContent = String(e);
        return {};
    }
}

document.getElementById('rpLoad').onclick = async () => {
    const symbol = (document.getElementById('rpSymbol').value || S.symbol || 'BTCUSDT').toUpperCase();
    const source = document.getElementById('rpSource').value;
    const from = parseInt(document.getElementById('rpFrom').value, 10) || 60;
    const to = parseInt(document.getElementById('rpTo').value, 10) || 0;
    document.getElementById('rpLoadResult').textContent = 'loading…';
    try {
        const body = source === 'exchange'
            ? { symbol: symbol, source: 'exchange', limit: 1000 }
            : { symbol: symbol, start_ms: Date.now() - from * 60000, end_ms: Date.now() - to * 60000 };
        const d = await api('/api/atlas/replay/load', { method: 'POST', body: body });
        document.getElementById('rpLoadResult').textContent = d.ok ? 'loaded ' + d.status.total + ' ' + d.status.mode : (d.error || 'nothing loaded');
        toast(document.getElementById('rpBanner'), d.ok
            ? 'Loaded ' + d.status.total + ' ' + d.status.mode + ' for ' + d.status.symbol + ' (' +
              new Date(d.status.start_ms).toLocaleTimeString() + ' → ' + new Date(d.status.end_ms).toLocaleTimeString() + ').'
            : (d.error || 'nothing loaded'), d.ok ? 'ok' : 'warn');
        rpStatus();
    } catch (e) { document.getElementById('rpLoadResult').textContent = String(e); }
};

document.getElementById('rpPlay').onclick = async () => {
    try {
        const d = await api('/api/atlas/replay/play', { method: 'POST', body: { speed: parseFloat(document.getElementById('rpSpeed').value) } });
        if (!d.ok) toast(document.getElementById('rpBanner'), d.error || 'play failed', 'warn');
        rpStatus();
    } catch (e) { toast(document.getElementById('rpBanner'), String(e), 'err'); }
};
document.getElementById('rpPause').onclick = async () => { await api('/api/atlas/replay/pause', { method: 'POST' }); rpStatus(); };
document.getElementById('rpStop').onclick = async () => { await api('/api/atlas/replay/stop', { method: 'POST' }); rpStatus(); };
document.getElementById('rpSpeed').oninput = async (e) => {
    document.getElementById('rpSpeedLabel').textContent = e.target.value + '×';
    if (A.replay.loaded) await api('/api/atlas/replay/speed', { method: 'POST', body: { speed: parseFloat(e.target.value) } });
};
document.getElementById('rpSeek').oninput = () => { A.replay.dragging = true; };
document.getElementById('rpSeek').onchange = async (e) => {
    await api('/api/atlas/replay/seek', { method: 'POST', body: { fraction: parseInt(e.target.value, 10) / 1000 } });
    A.replay.dragging = false;
    rpStatus();
};

/* ── alerts ─────────────────────────────────────────────────────── */

async function loadAlerts(includeRules) {
    try {
        if (includeRules !== false) {
            const d = await api('/api/atlas/alerts?limit=200');
            const rows = (d.alerts || []).slice().reverse();
            document.getElementById('alertTable').querySelector('tbody').innerHTML =
                rows.slice(0, 60).map((a) =>
                    '<tr><td>' + new Date(a.ts_ms).toLocaleTimeString() + '</td>' +
                    '<td><span class="tag ' + (a.severity === 'critical' ? 'no' : a.severity === 'warning' ? 'warn' : '') + '">' + esc(a.severity) + '</span></td>' +
                    '<td>' + esc(a.kind) + '</td><td class="name">' + esc(a.symbol) + '</td><td class="name">' + esc(a.message) + '</td></tr>').join('')
                || '<tr><td colspan="5" class="dim">no alerts yet</td></tr>';
            const st = d.stats || {};
            document.getElementById('alStats').textContent = (st.history || 0) + ' fired · ' + (st.enabled || 0) + '/' + (st.rules || 0) + ' rules enabled';
            document.getElementById('navAlertCount').textContent = String(st.history || 0);
        }
        const r = await api('/api/atlas/alert-rules');
        A.alerts = r.rules || [];
        document.getElementById('ruleTable').querySelector('tbody').innerHTML = A.alerts.map((rule, i) =>
            '<tr data-idx="' + i + '">' +
            '<td><label class="switch"><input type="checkbox" data-role="enabled" ' + (rule.enabled ? 'checked' : '') + '></label></td>' +
            '<td class="name">' + esc(rule.name) + '</td><td>' + esc(rule.kind) + '</td>' +
            '<td><input type="text" data-role="params" style="width:100%;min-width:180px" value="' + esc(JSON.stringify(rule.params || {})) + '"></td>' +
            '<td><input type="number" data-role="cooldown" style="width:80px" value="' + rule.cooldown_s + '"></td>' +
            '<td>' + (rule.fired || 0) + '</td></tr>').join('');
    } catch (e) { console.error(e); }
}

document.getElementById('alSave').onclick = async () => {
    const rows = Array.prototype.slice.call(document.querySelectorAll('#ruleTable tbody tr'));
    let saved = 0;
    for (const tr of rows) {
        const base = A.alerts[parseInt(tr.dataset.idx, 10)];
        if (!base) continue;
        let params = base.params;
        try { params = JSON.parse(tr.querySelector('[data-role="params"]').value || '{}'); } catch (err) { continue; }
        await api('/api/atlas/alert-rules', {
            method: 'POST',
            body: {
                id: base.id, name: base.name, kind: base.kind, params: params,
                enabled: tr.querySelector('[data-role="enabled"]').checked,
                cooldown_s: parseFloat(tr.querySelector('[data-role="cooldown"]').value) || 0,
                channels: base.channels,
            },
        });
        saved++;
    }
    toastsaved(saved);
};
function toastsaved(n) { toast(document.getElementById('rpBanner'), n + ' alert rules saved', 'ok'); }
document.getElementById('alClear').onclick = () => {
    document.getElementById('alertTable').querySelector('tbody').innerHTML = '<tr><td colspan="5" class="dim">cleared locally</td></tr>';
};

/* ── the two series this panel shares with the add-on cards ────────────────────────────────────
   /api/atlas/cvd/<symbol>  →  this CVD chart AND market-pressure.js's Market Pressure card
   /api/atlas/tape/<symbol> →  these Trackers tables AND atlas-v2.js's big-trade-zone card
   Both halves used to poll their url on a timer of their own (measured: 28 requests a minute for
   the cvd series, 27 for the tape series). One dataset is one channel: a bus channel is keyed by
   (method, url, params) and NOT by the interval, so the two halves have to ask for one rate —
   ATLAS_SHARE_MS, which is this panel's own cadence in the shell's 5 s slow-panel loop. The
   add-on cards' 4 s tick moves onto it, not the other way round. With no delivery layer loaded
   (`OFAPBUS` absent) the slow loop keeps asking directly, exactly as it did before. */
const ATLAS_SHARE_MS = 5000;
const ATLAS_SHARE = {
    cvd: { url: '/api/atlas/cvd/', view: 'cvd', key: '', off: null, paint: paintCvd },
    tape: { url: '/api/atlas/tape/', view: 'trackers', key: '', off: null, paint: paintTrackers },
};

/* True when the shared channel is running this series — then nobody has to ask for it by hand. */
function atlasShareLive(name) {
    const share = ATLAS_SHARE[name];
    return !!(share && share.off);
}

function atlasShareApply(share, payload) {
    if (!payload || typeof payload !== 'object') return false;
    if (payload.error || payload.ok === false) {          // the channel reports a failure as data
        console.error(share.url + ' ' + (payload.error || 'refused'));
        return false;
    }
    share.paint(payload);
    return true;
}

/* Subscribe / release / re-key, driven from three places: the 5 s slow-panel loop, the section's own
   class (the shell's way of saying "on screen", in both modes), and the instrument select. Returns
   true while the bus owns the cadence. */
function atlasShareSync(name) {
    const share = ATLAS_SHARE[name];
    if (!share) return false;
    const url = S.symbol ? share.url + encodeURIComponent(S.symbol) : '';
    const wanted = !!(url && truthyView(share.view));
    if (share.off && (!wanted || share.key !== url)) { share.off(); share.off = null; share.key = ''; }
    if (!wanted) return false;
    const bus = window.OFAPBUS;
    if (!bus || typeof bus.subscribe !== 'function') return false;   // no delivery layer: the loop asks
    if (!share.off) {
        share.key = url;
        share.off = bus.subscribe({ url: url, intervalMs: ATLAS_SHARE_MS },
            (payload) => atlasShareApply(share, payload));
    }
    return true;
}

(function atlasShareWatch() {
    Object.keys(ATLAS_SHARE).forEach((name) => {
        const share = ATLAS_SHARE[name];
        const section = document.querySelector('.view[data-view="' + share.view + '"]');
        if (section && typeof MutationObserver === 'function') {
            new MutationObserver(() => { atlasShareSync(name); })
                .observe(section, { attributes: true, attributeFilter: ['class'] });
        }
    });
    const select = document.getElementById('symbolSelect');
    if (select) select.addEventListener('change', () => { Object.keys(ATLAS_SHARE).forEach(atlasShareSync); });
})();

/* ── wiring ─────────────────────────────────────────────────────── */

document.getElementById('hmColumns').onchange = loadHeatmap;
document.getElementById('hmRows').onchange = loadHeatmap;
document.getElementById('hmTrades').onchange = () => { if (A.heat.last) drawHeatmap(A.heat.last); };
document.getElementById('hmEvents').onchange = () => { if (A.heat.last) drawHeatmap(A.heat.last); };
document.getElementById('hmAuto').onclick = () => {
    A.heat.auto = !A.heat.auto;
    document.getElementById('hmAutoLabel').textContent = 'auto: ' + (A.heat.auto ? 'on' : 'off');
};
document.getElementById('frameSelect').onchange = loadFrames;
document.getElementById('cvdReanchor').onclick = async () => {
    if (!S.symbol) return;
    await api('/api/atlas/cvd/' + encodeURIComponent(S.symbol) + '/reanchor', { method: 'POST' });
    loadCvd({ force: true });              /* the anchor moved under the chart: repaint now */
};

function atlasSlowRefresh() {
    if (truthyView('heatmap') && A.heat.auto) loadHeatmap();
    /* cvd + trackers are shared channels (see ATLAS_SHARE): the bus owns their cadence, so this
       loop's job is to say whether they should be live — and, with no bus loaded, to keep being the
       asker on the same 5 s it always was. */
    if (!atlasShareSync('cvd') && truthyView('cvd')) loadCvd();
    if (!atlasShareSync('trackers') && truthyView('trackers')) loadTrackers();
    if (truthyView('profile')) loadMarketProfile();
    if (truthyView('frames')) loadFrames();
    if (truthyView('replay')) rpStatus();
    if (truthyView('alerts') && document.getElementById('alAuto').checked) loadAlerts();
}

/* live detections arriving over the socket bump the counters immediately */
function atlasOnEvent(channel, data) {
    A.liveTicks++;
    const badge = document.getElementById('navAlertCount');
    if (channel === 'alert' && badge) {
        badge.textContent = String((parseInt(badge.textContent, 10) || 0) + 1);
    }
}

/* ── atlas settings panel (rendered into the Settings view) ──────── */

const ATLAS_FIELDS = [
    ['heatmap', 'bucket_ms', 'Heatmap bucket (ms)', 'number', 100],
    ['heatmap', 'wall_quantile', 'Wall quantile (0-1)', 'number', 0.01],
    ['heatmap', 'pull_pct', 'Pull threshold (0-1)', 'number', 0.05],
    ['heatmap', 'stack_pct', 'Stack multiple', 'number', 0.1],
    ['tape', 'big_quantile', 'Big-trade quantile', 'number', 0.005],
    ['tape', 'block_multiple', 'Block multiple', 'number', 0.5],
    ['tape', 'sweep_levels', 'Sweep levels', 'number', 1],
    ['tape', 'sweep_min_size', 'Sweep min size', 'number', 0.1],
    ['tape', 'iceberg_min_fills', 'Iceberg refills', 'number', 1],
    ['tape', 'iceberg_min_size', 'Iceberg min hidden vol', 'number', 0.1],
    ['tape', 'iceberg_min_total', 'Iceberg min total vol', 'number', 0.1],
    ['tape', 'iceberg_min_duration_s', 'Iceberg min duration (s)', 'number', 1],
    ['tape', 'sweep_min_aggressors', 'Sweep min aggressors', 'number', 1],
    ['tape', 'sweep_min_range_ticks', 'Sweep min range (ticks)', 'number', 1],
    ['tape', 'stoprun_min_volume', 'Stop-run min volume', 'number', 0.1],
    ['tape', 'stoprun_min_prints', 'Stop-run min prints', 'number', 1],
    ['heatmap', 'upper_cutoff_pct', 'Heatmap upper cut-off %', 'number', 1],
    ['tape', 'stoprun_ticks', 'Stop-run ticks', 'number', 1],
    ['cvd', 'divergence_lookback', 'CVD lookback buckets', 'number', 1],
    ['cvd', 'divergence_min_ticks', 'CVD divergence ticks', 'number', 1],
    ['market_profile', 'bracket_minutes', 'TPO bracket (min)', 'number', 5],
];

function renderAtlasSettings() {
    const grid = document.getElementById('atlasGrid');
    if (!grid || !S.config) return;
    const atlas = S.config.atlas || {};
    grid.innerHTML = ATLAS_FIELDS.map(([group, key, label, type, step]) => {
        const val = (atlas[group] || {})[key];
        return '<div class="field"><label>' + label + '</label>' +
            '<input type="' + type + '" step="' + step + '" data-atlas-group="' + group + '" data-atlas-key="' + key + '" value="' +
            (val === undefined ? '' : val) + '"></div>';
    }).join('') || '<div class="dim">no atlas settings</div>';
    const extras = document.getElementById('atlasExtras');
    if (extras) extras.checked = atlas.extras_enabled !== false;
    toast(document.getElementById('atlasBanner'),
        'These drive the Heatmap, Trackers, CVD and Profile views. Changes apply on the next engine start (or use “Save & restart engine”).',
        'info');
}

function collectAtlasSettings(cfg) {
    const atlas = cfg.atlas || (cfg.atlas = {});
    document.querySelectorAll('#atlasGrid input[data-atlas-group]').forEach((inp) => {
        const group = inp.dataset.atlasGroup, key = inp.dataset.atlasKey;
        const v = parseFloat(inp.value);
        if (Number.isNaN(v)) return;
        atlas[group] = atlas[group] || {};
        atlas[group][key] = v;
    });
    const extras = document.getElementById('atlasExtras');
    if (extras) atlas.extras_enabled = extras.checked;
    return cfg;
}

/* A window change re-fits every canvas, which clears it. Waiting for the next 5 s poll left the
   heatmap blank for up to a second after a resize; repaint as soon as the geometry has settled.
   Appended, not spliced: the refresh loop above keeps its own order. */
document.addEventListener('ofap:relayout', () => {
    try {
        if (truthyView && truthyView('heatmap') && A.heat && A.heat.last && typeof drawHeatmap === 'function') {
            drawHeatmap(A.heat.last);
        }
    } catch (e) { /* the map's own path reports its faults */ }
});
