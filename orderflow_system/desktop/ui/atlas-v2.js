/* ══════════════════════════════════════════════════════════════════
   Order-flow extras — additive module for the second the reference layout pass.

   Renders what the base atlas views do not know about yet:

       · Stacked-imbalance ladder  (the reference layout rule: bid at a level vs the ask
         one level above, mirrored; consecutive levels = stacked)
       · Big-trade zones           (price bins that collected big trades)
       · Persisted detection history (SQLite, survives the session)
       · Per-rule Telegram routing + alert sound

   Loaded AFTER atlas.js. It wraps the hook functions ui.js already calls
   (atlasOnEvent / renderAtlasSettings / collectAtlasSettings) instead of
   redefining them, so the base views keep working untouched, and it only
   writes into its own element ids.

   THE BIG-TRADE-ZONE CARD SHARES ITS SERIES with atlas.js's Trackers tables: both read
   /api/atlas/tape/<symbol>, so they join ONE OFAPBUS channel (V2_SHARE below). The imbalance ladder
   and the persisted history stay this module's own readers — nothing else asks for them.
   ══════════════════════════════════════════════════════════════════ */

const ATLAS_V2 = { soundLog: [], audio: null, rules: [], timer: null };

const V2_Q = (s) => encodeURIComponent(s);
const V2_TIME = (ms) => (ms ? new Date(ms).toLocaleTimeString('en-US', { hour12: false }) : '--');
const V2_SZ = (v) => {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return '--';
    const a = Math.abs(Number(v));
    if (a === 0) return '0';
    if (a >= 1000) return compact(v);
    if (a >= 1) return Number(v).toFixed(2);
    if (a >= 0.01) return Number(v).toFixed(3);
    return Number(v).toPrecision(2);
};
function v2Empty(cols, text) { return `<tr><td colspan="${cols}" class="dim">${text}</td></tr>`; }
function v2Set(sel, html) { const el = $(sel); if (el) el.innerHTML = html; }

/* ── alert sound: a small Web Audio blip, no asset needed ──────────── */

function v2Beep(severity) {
    ATLAS_V2.soundLog.push({ severity: severity || 'info', t: Date.now() });
    if (ATLAS_V2.soundLog.length > 60) ATLAS_V2.soundLog.shift();
    const toggle = $("#alSound");
    if (toggle && !toggle.checked) return;
    try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        ATLAS_V2.audio = ATLAS_V2.audio || new Ctx();
        const ctx = ATLAS_V2.audio;
        if (ctx.state === 'suspended') ctx.resume();
        const tones = severity === 'critical' ? [880, 620, 880] : severity === 'warning' ? [660, 520] : [520];
        tones.forEach((freq, i) => {
            const osc = ctx.createOscillator(), gain = ctx.createGain();
            osc.type = 'sine'; osc.frequency.value = freq;
            const at = ctx.currentTime + i * 0.12;
            gain.gain.setValueAtTime(0.0001, at);
            gain.gain.exponentialRampToValueAtTime(0.12, at + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.11);
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(at); osc.stop(at + 0.12);
        });
    } catch (e) { /* audio blocked (autoplay policy) — the log entry still proves the call */ }
}

/* ── stacked-imbalance ladder ──────────────────────────────────────── */

async function loadImbalance() {
    if (!S.symbol) return;
    let d;
    try { d = await api(`/api/atlas/imbalance/${V2_Q(S.symbol)}?levels=160`); } catch (e) { return; }
    const counts = d.counts || {};
    const st = $("#tkImbStats");
    if (st) st.textContent = `${counts.bid || 0} bid · ${counts.ask || 0} ask imbalances · ${counts.stacked || 0} stacked · ` +
        `${d.rate_pct}% rate · window ${Math.round((d.window_ms || 0) / 1000)}s`;

    const levels = (d.levels || []).slice(0, 40);
    v2Set('#tkImbTable tbody', levels.map((l) => `<tr>
        <td>${fmt(l.price, 2)}</td>
        <td><span class="tag ${l.side === 'bid' ? 'ok' : 'no'}">${esc(l.side)}</span></td>
        <td>${V2_SZ(l.volume)}</td><td>${V2_SZ(l.other_volume)}</td>
        <td class="${l.ratio_pct >= 300 ? 'up' : ''}">${fmt(l.ratio_pct, 0)}%</td></tr>`).join('')
        || v2Empty(5, 'no imbalance past the rate yet'));

    const stacked = d.stacked || [];
    v2Set('#tkStackTable tbody', stacked.map((c) => `<tr>
        <td><span class="tag ${c.side === 'bid' ? 'ok' : 'no'}">${esc(c.side)}</span></td>
        <td>${fmt(c.from_price, 2)}</td><td>${fmt(c.to_price, 2)}</td>
        <td>${c.levels}</td><td>${V2_SZ(c.volume)}</td>
        <td class="${c.max_ratio_pct >= 300 ? 'up' : ''}">${fmt(c.max_ratio_pct, 0)}%</td></tr>`).join('')
        || v2Empty(6, 'no stacked cluster yet'));
}

/* ── big-trade zones ───────────────────────────────────────────────── */

async function loadZones(options) {
    if (!S.symbol) return false;
    /* With the delivery layer loaded this is a shared channel (V2_SHARE): atlas.js's Trackers tables
       read the same tape url, so the channel asks and this call only guarantees it is live. */
    if (!(options && options.force) && V2_SHARE.tape.off) return true;
    let d;
    try { d = await api(`/api/atlas/tape/${V2_Q(S.symbol)}`); } catch (e) { return false; }
    paintZones(d);
    return true;
}

/* The zone card's own drawing, whichever way the payload arrived. */
function paintZones(d) {
    const zones = (d.events || {}).zones || [];
    const st = $("#tkZoneStats");
    if (st) st.textContent = (zones.length
        ? `${zones.length} zones · biggest ${V2_SZ(zones[0].total)} @ ${fmt(zones[0].zone_price, 2)}`
        : 'no big-trade volume yet') + v2ShareNote();
    v2Set('#tkZoneTable tbody', zones.slice(0, 12).map((z) => `<tr>
        <td>${fmt(z.zone_price, 2)} – ${fmt(z.zone_price + (z.zone_size || 0), 2)}</td>
        <td class="up">${V2_SZ(z.buy)}</td><td class="down">${V2_SZ(z.sell)}</td>
        <td>${V2_SZ(z.total)}</td>
        <td class="${z.delta >= 0 ? 'up' : 'down'}">${V2_SZ(z.delta)}</td>
        <td>${z.count}</td><td>${V2_TIME(z.last_ms)}</td></tr>`).join('')
        || v2Empty(7, 'no big trades in this session yet'));
}

/* ── the tape series is a shared channel ────────────────────────────────────────────────────────
   atlas.js's Trackers tables poll the SAME url (/api/atlas/tape/<symbol>), so the two of them used
   to cost 27 requests a minute for one series (measured). One dataset is one channel; the shared
   rate is atlas.js's own 5 s cadence, since a bus channel is keyed by (method, url, params) and not
   by the interval. No delivery layer → this card keeps its own 4 s tick in v2Poll. */
const V2_SHARE_MS = 5000;

const V2_SHARE = {
    tape: { url: '/api/atlas/tape/', view: 'trackers', key: '', off: null },
};

function v2ShareNote() {
    return V2_SHARE.tape.off ? ` · polling ${V2_SHARE_MS / 1000}s via the shared bus` : '';
}

/* True while the bus owns this series' cadence. Releases the channel when the card leaves the
   screen — the bus is refcounted, so a subscriber left behind is a poller nobody is watching. */
function v2ShareSync(name) {
    const share = V2_SHARE[name];
    if (!share) return false;
    const url = S.symbol ? share.url + V2_Q(S.symbol) : '';
    const wanted = !!(url && truthyView(share.view));
    if (share.off && (!wanted || share.key !== url)) { share.off(); share.off = null; share.key = ''; }
    if (!wanted) return false;
    const bus = window.OFAPBUS;
    if (!bus || typeof bus.subscribe !== 'function') return false;   // no delivery layer: v2Poll asks
    if (!share.off) {
        share.key = url;
        share.off = bus.subscribe({ url: url, intervalMs: V2_SHARE_MS }, (payload) => {
            if (!payload || typeof payload !== 'object') return;
            if (payload.error || payload.ok === false) return;       // the channel reports failures as data
            paintZones(payload);
        });
    }
    return true;
}

(function v2ShareWatch() {
    const section = document.querySelector('.view[data-view="' + V2_SHARE.tape.view + '"]');
    if (section && typeof MutationObserver === 'function') {
        new MutationObserver(() => { v2ShareSync('tape'); })
            .observe(section, { attributes: true, attributeFilter: ['class'] });
    }
    const select = document.getElementById('symbolSelect');
    if (select) select.addEventListener('change', () => { v2ShareSync('tape'); });
})();

/* ── persisted history ─────────────────────────────────────────────── */

async function loadHistory() {
    if (!S.symbol) return;
    let d;
    try { d = await api(`/api/atlas/history/${V2_Q(S.symbol)}?limit=200`); } catch (e) { return; }
    const st = $("#histStats");
    if (st) st.textContent = d.ok === false
        ? (d.error || 'history unavailable')
        : `${d.total} events on disk · ${d.written} written this run · ${d.pending} queued`;
    const rows = (d.events || []).slice(0, 30);
    v2Set('#histTable tbody', rows.map((e) => `<tr>
        <td>${V2_TIME(e.ts_ms)}</td><td><span class="tag">${esc(e.kind)}</span></td>
        <td>${e.price ? fmt(e.price, 2) : '—'}</td><td>${e.size ? V2_SZ(e.size) : '—'}</td>
        <td class="name">${esc(e.detail || '')}</td></tr>`).join('')
        || v2Empty(5, 'nothing persisted yet for this instrument'));
}

/* ── per-rule alert routing (telegram / ntfy / email / webhook) ────── */

const V2_CHANNELS = [
    ['telegram', 'Telegram'],
    ['ntfy', 'ntfy push'],
    ['email', 'Email'],
    ['webhook', 'Webhook'],
];

async function loadRouting() {
    let d;
    try { d = await api('/api/atlas/alert-rules'); } catch (e) { return; }
    ATLAS_V2.rules = d.rules || [];
    const box = $("#tgRouting");
    if (!box) return;
    let live = {};
    try { live = (await api('/api/atlas/notify/status')).stats || {}; } catch (e) { live = {}; }
    // "configured" = credentials saved for that channel; readiness only turns on
    // once the engine has started the notifier, so it is the wrong signal here
    const isConfigured = (k) => !!(live[k] && (live[k].enabled || live[k].ready));
    const configured = new Set(Object.keys(live).filter(isConfigured));
    box.innerHTML = ATLAS_V2.rules.length
        ? ATLAS_V2.rules.map((r) => `<div class="v2-route-row">
            <div class="v2-route-name">${esc(r.name)}</div>
            <div class="v2-route-scope dim">${r.params && r.params.at_price != null
                ? 'level ' + r.params.at_price + ' \u00b1' + (r.params.at_tol || 0) + (r.params.min_age_s ? ' · holds ' + r.params.min_age_s + 's' : '')
                : 'whole instrument'}</div>
            <button class="btn small" data-rule-del="${esc(r.id)}" title="Delete this rule">delete</button>
            <div class="v2-route-chans">${V2_CHANNELS.map(([key, label]) => `
                <label class="switch v2-route" title="${esc(label)}${configured.size && !configured.has(key) && key !== 'webhook' ? ' (not configured yet — set it up in Setup)' : ''}">
                    <input type="checkbox" data-rule="${esc(r.id)}" data-channel="${key}"
                           ${(r.channels || []).includes(key) ? 'checked' : ''}>
                    ${esc(label)}</label>`).join('')}</div>
        </div>`).join('')
        : '<div class="dim">no rules loaded</div>';
}

document.addEventListener('click', async (ev) => {
    const del = ev.target.closest('[data-rule-del]');
    if (!del) return;
    const id = del.dataset.ruleDel;
    del.disabled = true;
    try {
        await api('/api/atlas/alert-rules/' + encodeURIComponent(id), { method: 'DELETE' });
        toast($("#atlasV2Banner") || document.body, 'rule deleted: ' + id, 'ok');
        loadRouting();
    } catch (e) {
        del.disabled = false;
        toast($("#atlasV2Banner") || document.body, String(e), 'err');
    }
});

async function saveRouting(input) {
    const id = input.dataset.rule;
    const rule = ATLAS_V2.rules.find((r) => r.id === id);
    if (!rule) return;
    const wanted = new Set(['ui']);
    document.querySelectorAll(`#tgRouting input[data-rule="${CSS.escape(id)}"]`).forEach((box) => {
        if (box.checked) wanted.add(box.dataset.channel);
    });
    const channels = [...wanted];
    try {
        await api('/api/atlas/alert-rules', {
            method: 'POST',
            body: { id: rule.id, name: rule.name, kind: rule.kind, params: rule.params,
                    enabled: rule.enabled, cooldown_s: rule.cooldown_s, channels },
        });
        rule.channels = channels;
        const label = input.dataset.channel;
        toast($("#atlasV2Banner"), `${rule.name}: ${label} ${input.checked ? 'on' : 'off'}`, 'ok');
    } catch (e) {
        toast($("#atlasV2Banner"), String(e), 'err');
    }
}

/* ── settings card (its own container — never touches #atlasGrid) ──── */

const V2_FIELDS = {
    imbalance: [
        ['rate_pct', 'Imbalance rate (%)', 10],
        ['window_s', 'Imbalance window (s)', 30],
        ['min_volume', 'Min volume per side', 0.01],
        ['min_levels', 'Alert at N stacked levels', 1],
    ],
    'tape extras': [
        ['reassembly_ms', 'Reassembly window (ms)', 10],
        ['zone_ticks', 'Zone height (ticks)', 25],
    ],
};

function renderV2Settings() {
    const grid = $("#atlasV2Grid");
    if (!grid || !S.config) return;
    const atlas = (S.config.atlas = S.config.atlas || {});
    const cards = Object.entries(V2_FIELDS).map(([group, fields]) => `
        <div class="card" style="margin:0"><div class="card-head"><span class="card-title">${group}</span></div>
        <div class="card-body">${fields.map(([key, label, step]) => {
            const groupKey = group === 'tape extras' ? 'tape' : 'imbalance';
            const val = (atlas[groupKey] || {})[key];
            return `<div class="field"><label>${label}</label>
                <input type="number" step="${step}" data-v2-group="${groupKey}" data-v2-key="${key}"
                       value="${val === undefined ? '' : val}"></div>`;
        }).join('')}</div></div>`).join('');

    const hist = atlas.history || {}, tg = atlas.telegram || {};
    grid.innerHTML = cards + `
        <div class="card" style="margin:0"><div class="card-head"><span class="card-title">history &amp; routing</span></div>
        <div class="card-body">
            <label class="switch"><input type="checkbox" id="v2HistEnabled" ${hist.enabled !== false ? 'checked' : ''}>
                persist detections to SQLite</label>
            <label class="switch" style="margin-top:6px"><input type="checkbox" id="v2TgEnabled" ${tg.enabled !== false ? 'checked' : ''}>
                route alerts to Telegram when a rule asks for it</label>
            <div class="reads-sub" style="margin:12px 0 6px">Telegram per rule</div>
            <div id="tgRouting"><div class="dim">loading…</div></div>
        </div></div>`;
    loadRouting();
}

function collectV2Settings(cfg) {
    const atlas = (cfg.atlas = cfg.atlas || {});
    $$('#atlasV2Grid input[data-v2-group]').forEach((inp) => {
        const group = inp.dataset.v2Group, key = inp.dataset.v2Key;
        const v = parseFloat(inp.value);
        if (Number.isNaN(v)) return;
        atlas[group] = atlas[group] || {};
        atlas[group][key] = v;
    });
    const hist = $("#v2HistEnabled"), tg = $("#v2TgEnabled");
    if (hist) (atlas.history = atlas.history || {}).enabled = hist.checked;
    if (tg) (atlas.telegram = atlas.telegram || {}).enabled = tg.checked;
    return cfg;
}

/* ── wiring: wrap ui.js's existing hooks, never redefine them ──────── */

const _v2OnEvent = window.atlasOnEvent;
window.atlasOnEvent = function (channel, data) {
    if (typeof _v2OnEvent === 'function') _v2OnEvent(channel, data);
    if (channel === 'alert') v2Beep(data && data.severity);
};

const _v2RenderSettings = window.renderAtlasSettings;
window.renderAtlasSettings = function () {
    if (typeof _v2RenderSettings === 'function') _v2RenderSettings();
    renderV2Settings();
};

const _v2CollectSettings = window.collectAtlasSettings;
window.collectAtlasSettings = function (cfg) {
    const out = typeof _v2CollectSettings === 'function' ? _v2CollectSettings(cfg) : cfg;
    return collectV2Settings(out || cfg || {});
};

/* poll only the views this module owns (the base views refresh on their own) */
function v2Poll() {
    if (!S.symbol) return;
    if (truthyView('trackers')) {
        loadImbalance();                                  /* this card's own series: no one else reads it */
        /* the zone card watches the tape url atlas.js's Trackers tables do: join that channel, and
           be the asker only when no delivery layer is loaded */
        if (!v2ShareSync('tape')) loadZones();
    }
    if (truthyView('alerts')) loadHistory();
}
const startV2Poll = () => {
    const id = setInterval(() => {
        if (window.OFAPINTENT && OFAPINTENT.held('trackers')) {
            return OFAPINTENT.deferKeyed('trackers', 'v2', v2Poll);
        }
        v2Poll();
    }, 4000);
    if (window.OFAPPause) window.OFAPPause.register(id, startV2Poll);
    return id;
};
ATLAS_V2.timer = startV2Poll();

const _histReload = $("#histReload");
if (_histReload) _histReload.onclick = loadHistory;

const _soundToggle = $("#alSound");
if (_soundToggle) {
    const stored = window.localStorage ? localStorage.getItem('atlas.sound') : null;
    if (stored !== null) _soundToggle.checked = stored !== '0';
    _soundToggle.onchange = () => {
        try { localStorage.setItem('atlas.sound', _soundToggle.checked ? '1' : '0'); } catch (e) { /* ignore */ }
    };
}

/* Routing checkboxes live in markup this module renders, so listen on the
   document — a listener on #tgRouting itself would be orphaned by every
   re-render (the container element is replaced). */
document.addEventListener('change', (ev) => {
    const inp = ev.target && ev.target.closest ? ev.target.closest('#tgRouting input[data-rule]') : null;
    if (inp) saveRouting(inp);
});

/* Load the onboarding layer (tooltips, in-app guide, first-run assistant) and
   the market-context card. Kept in their own files for readability; this module
   is the one guaranteed to load after the base views, so the loader lives here. */
(() => {
    [['steady.js', 'atlas-steady'], ['guide.js', 'guide'], ['context.js', 'atlas-context'], ['market-pressure.js', 'market-pressure'],
     ['intent.js', 'atlas-intent'], ['vwap.js', 'atlas-vwap'], ['scanner.js', 'atlas-scanner'],
     ['search.js', 'program-search'], ['search-ops.js', 'palette-ops'],
     ['alpaca.js', 'alpaca-account'],
     ['alpaca-card.js', 'alpaca-card'],
     ['platforms.js', 'platforms-view'],
     ['study-api.js', 'study-api'], ['studies.js', 'studies-view']].forEach(([src, flag]) => {
        if (document.querySelector(`script[data-${flag}]`)) return;
        const s = document.createElement('script');
        s.src = '/desktop/' + src;
        s.dataset[flag.replace(/-(\w)/g, (m, c) => c.toUpperCase())] = '1';
        document.body.appendChild(s);
    });
})();

/* A module that fails to parse dies silently: the app looks fine and one whole
   feature set is simply missing (this cost a debugging cycle — a stray apostrophe
   inside a single-quoted string killed the guide module with no visible error).
   Surface any script error in the app's own log view and as a toast. */
function reportClientError(detail) {
    /* One place that turns a browser exception into something readable later: the location and the
       stack go to the server log (the frozen app has no console), the short form goes to the toast. */
    const loc = detail.source ? `${detail.source.split('/').pop()}:${detail.line || 0}:${detail.col || 0}` : '';
    const msg = `module error${loc ? ' in ' + loc : ''}: ${detail.message || 'failed to load'}`;
    try { console.error(msg, detail.stack || ''); } catch (e) { /* ignore */ }
    try {
        if (typeof toast === 'function' && document.body) toast(document.body, msg, 'err');
    } catch (e) { /* ignore */ }
    try {
        if (typeof api === 'function') api('/api/control/client-error', { method: 'POST', body: detail });
        else fetch('/api/control/client-error', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(detail) });
    } catch (e) { /* the console line above is the fallback */ }
}

window.addEventListener('error', (ev) => {
    reportClientError({
        message: ev.message || 'failed to load',
        source: ev.filename || '',
        line: ev.lineno || 0,
        col: ev.colno || 0,
        stack: (ev.error && ev.error.stack) || '',
    });
}, true);

window.addEventListener('unhandledrejection', (ev) => {
    const r = ev.reason || {};
    reportClientError({
        message: 'unhandled rejection: ' + (r.message || String(r)),
        source: '', line: 0, col: 0,
        stack: r.stack || '',
    });
});

window.ATLAS_V2 = ATLAS_V2;
