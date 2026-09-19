/* ══════════════════════════════════════════════════════════════════
   Alpaca on the landing page — the Overview card, the not-connected banner,
   and the symbol list behind the Alpaca view.

   Three jobs:
     · make the broker account findable without knowing it lives under Settings;
     · say plainly, once, that it is optional — and then stop saying it
       (a "not now" hides the banner for this run; a restart offers it once more
       because most people who skip it are not ready yet, not never);
     · edit the Alpaca symbol list the engine will request once the data layer
       is enabled.

   Everything Alpaca-shaped (status pill, capability report, key form) is
   rendered by alpaca.js. This module only adds entry points and never
   duplicates that rendering.
   ══════════════════════════════════════════════════════════════════ */

const ALPCARD = { lastLoad: 0, lastKey: '' };

function alpC(id) { return document.getElementById(id); }

function alpCardStyles() {
    if (document.getElementById('alpCardStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'alpCardStyleSheet';
    st.textContent = `
        .alp-ov p { margin: 0; }
        .alp-ov .alp-ov-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        .alp-ov details { margin-top: 10px; }
        .alp-ov summary { cursor: pointer; color: var(--dim); font-size: 12px; }
        .ov-alp-banner .banner { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .alp-syms { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
        .alp-sym { border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; font-size: 12px;
                   display: inline-flex; align-items: center; gap: 6px; }
        .alp-sym button { background: none; border: 0; color: var(--dim); cursor: pointer; padding: 0 2px; }
        .alp-sym button:hover { color: var(--down, #ff5d6c); }
    `;
    document.head.appendChild(st);
}

/* ── the landing-page card ─────────────────────────────────────── */

function alpOvCardHTML() {
    const st = (typeof ALPACA !== 'undefined' && ALPACA.status) || {};
    const report = (typeof ALPACA !== 'undefined' && ALPACA.report) || {};
    const caps = (report && report.capabilities) || {};
    const acc = (report && report.account) || {};
    const configured = !!st.configured;
    const pill = typeof alpacaStatusPill === 'function' ? alpacaStatusPill() : '';
    /* The reported confusion: keys saved, feed still on Bybit — "I only connected Alpaca".
       The card carries the one click that makes the account the engine's data source. */
    const srcNow = String(((S.status || {}).source) || ((S.config || {}).data_source) || '');
    const alpacaSource = /(alpaca|all)/.test(srcNow);
    const rows = configured ? [
        alpacaCapabilityRow('IEX real-time equity tape', !!caps.equities_realtime_iex,
            'live trades for delta, footprint and VWAP — 30 stream symbols on the free plan'),
        alpacaCapabilityRow('Full-market history, 15 minutes delayed', !!caps.equities_sip_delayed,
            'the complete tape for everything older than 15 minutes'),
        alpacaCapabilityRow('Options data', !!caps.options_data, 'indicative feed on the free plan'),
        alpacaCapabilityRow('Benzinga news + US market calendar', !!(caps.news && caps.market_clock),
            'headlines with symbols, and the sessions the app can behave around'),
        alpacaCapabilityRow('Positions, orders, portfolio history', !!caps.positions,
            'a real Portfolio view — next phase'),
        alpacaCapabilityRow('Order book / depth', false,
            'not published by Alpaca — the heatmap, DOM ladder and intent reader stay on the exchange feed'),
    ].join('') : '';
    return `
    <div class="card alp-ov" id="ovAlpCard">
        <div class="card-head">
            <span class="card-title">Broker account — Alpaca Markets</span>
            <span style="margin-left:10px">${pill}</span>
            ${configured
                ? (alpacaSource
                    ? '<span class="dim" id="alpSrcChip" title="The engine streams from Alpaca — Data ▸ Source still lists every venue">engine source: Alpaca</span>'
                    : '<button class="btn small primary" id="alpUseSrc" title="Set the engine data source to Alpaca — the engine restarts if it is running">Use Alpaca as the engine source</button><span class="dim" id="alpSrcMsg"></span>')
                : ''}
            <div class="grow" style="flex:1"></div>
            <button class="btn small" id="ovAlpOpen" title="Keys, environment, capability report and symbol list">Open Alpaca setup</button>
        </div>
        <div class="card-body">
            ${configured ? `
                <div class="alp-grid">
                    <div class="alp-kv" title="Cash in the account."><div class="k">cash</div><div class="v">${acc.cash ?? '–'}</div></div>
                    <div class="alp-kv" title="Account equity including positions."><div class="k">equity</div><div class="v">${acc.equity ?? '–'}</div></div>
                    <div class="alp-kv" title="What the account can deploy right now."><div class="k">buying power</div><div class="v">${acc.buying_power ?? '–'}</div></div>
                    <div class="alp-kv" title="Streaming symbols used on the free plan."><div class="k">symbols</div><div class="v">${(S.config && S.config.alpaca && (S.config.alpaca.view_symbols || []).length) || 0}</div></div>
                </div>
                <details><summary>What this account can reach</summary><div style="margin-top:8px">${rows}</div></details>`
            : `<p class="dim" style="margin-top:0">Not connected. Alpaca is a real US brokerage with an API — commission-free stocks,
                ETFs, options and crypto, a <b>free paper account</b> that needs only an email address, Benzinga news and the
                US market calendar. Connecting is <b>optional</b>: every view keeps working on the exchange feed without it.</p>`}
        </div>
    </div>`;
}

function alpOvRender() {
    const host = alpC('ovAlpacaHost');
    if (!host) return;
    alpCardStyles();
    host.innerHTML = alpOvCardHTML();
    const open = alpC('ovAlpOpen');
    if (open) open.onclick = () => { window.showView && window.showView('alpaca'); };
    const srcBtn = alpC('alpUseSrc');
    if (srcBtn) srcBtn.onclick = alpUseSource;
}

/* One click from "keys saved" to "the engine uses them". The same endpoint the Data ▸
   Source rows use: it writes the source and restarts a running engine end-to-end, so the
   feed actually moves — linking keys alone never switched it. */
async function alpUseSource() {
    const msgs = [alpC('alpSrcMsg'), alpC('alpFeedSrcMsg')].filter(Boolean);
    const btns = [alpC('alpUseSrc'), alpC('alpFeedUseSrc')].filter(Boolean);
    const say = (html) => { msgs.forEach((m) => { m.innerHTML = html; }); };
    btns.forEach((b) => { b.disabled = true; });
    say(' switching…');
    try {
        const r = await api('/api/control/source', { method: 'POST', body: { source: 'alpaca' } });
        if (r && r.ok === false) {
            say(`<span class="wiz-bad">${G_ESC(r.error || 'the switch was refused')}</span>`);
            btns.forEach((b) => { b.disabled = false; });
            return;
        }
        if (S.config) S.config.data_source = (r && r.data_source) || 'alpaca';
        if (typeof toast === 'function') toast(document.body, (r && r.note) || 'source saved', 'info');
        if (typeof pollStatus === 'function') void pollStatus();
        if (typeof alpacaLoad === 'function') alpacaLoad(true);
        if (window.OFX && !window.OFAP_PAUSED) OFX.renderLayers(true);
        alpOvRender();                             // the button becomes the state chip
        if (typeof alpFeedRender === 'function') alpFeedRender();
    } catch (e) {
        say(`<span class="wiz-bad">switch failed: ${G_ESC(String(e))}</span>`);
        btns.forEach((b) => { b.disabled = false; });
    }
}

/* ── the not-connected banner (dismissible, never nags twice in a row) ── */

function alpBannerWanted() {
    const cfg = S.config || {};
    const alp = cfg.alpaca || {};
    if (alp.enabled || alp.key_id) return false;               // connected → never nag
    if ((cfg.ui || {}).banner_dismissed_alpaca) return false;  // dismissed this run
    if (!cfg.onboarding_done) return false;                    // not while the wizard is still due
    return true;
}

async function alpSaveUiFlag(key, value) {
    try {
        const cfg = JSON.parse(JSON.stringify(S.config || {}));
        cfg.ui = cfg.ui || {};
        cfg.ui[key] = value;
        const r = await api('/api/control/config', { method: 'POST', body: cfg });
        S.config = r.config;
    } catch (e) { /* the banner simply keeps its current state */ }
}

function alpBannerRender() {
    const host = alpC('ovAlpacaBanner');
    if (!host) return;
    if (!alpBannerWanted()) { host.innerHTML = ''; return; }
    host.className = 'ov-alp-banner';
    host.innerHTML = `<div class="banner info">
        <span>Connect Alpaca to add US equities, ETFs, options, Benzinga news and the US market calendar.
              Free paper account, no funding — and optional.</span>
        <button class="btn small primary" id="ovAlpGo">Set up now</button>
        <button class="btn small" id="ovAlpLater" title="Hide this until the next start — it will not come back this run">Not now</button>
    </div>`;
    const go = alpC('ovAlpGo');
    if (go) go.onclick = () => { window.showView && window.showView('alpaca'); };
    const later = alpC('ovAlpLater');
    if (later) later.onclick = async () => { await alpSaveUiFlag('banner_dismissed_alpaca', true); alpBannerRender(); };
}

/* One dismissal lasts one run: clear the flag at start so a user who skipped it
   earlier is offered the card again next session (the plan's S3 §4.3 rule) —
   but only while it is still not connected, and only when it was dismissed. */
async function alpBannerResetIfDismissed() {
    const cfg = S.config || {};
    const alp = cfg.alpaca || {};
    if ((cfg.ui || {}).banner_dismissed_alpaca && !(alp.enabled || alp.key_id)) {
        await alpSaveUiFlag('banner_dismissed_alpaca', false);
    }
}

/* ── the Alpaca view: symbol list + wiring ─────────────────────── */

function alpSymbols() {
    const cfg = (S.config || {}).alpaca || {};
    return (cfg.view_symbols || []).slice();
}

function alpRouteRender() {
    const host = alpC('alpRouteHost');
    if (!host) return;
    const list = alpSymbols();
    host.innerHTML = `
        <div class="alp-syms">${list.length ? list.map((s) => `
            <span class="alp-sym">${G_ESC(s)}<button data-alp-del="${G_ESC(s)}" title="Remove ${G_ESC(s)} from the list">✕</button></span>`).join('')
            : '<span class="dim">no symbols yet — the defaults are AAPL, MSFT, NVDA, SPY, QQQ</span>'}</div>
        <div class="row" style="gap:8px;align-items:flex-end;flex-wrap:wrap">
            <div class="field" style="flex:0 0 180px"><label>Add symbol</label>
                <input type="text" id="alpAddSym" placeholder="e.g. TSLA" autocomplete="off" spellcheck="false"
                       title="Subscribes the Alpaca feed's quote/trade stream for this ticker — to chart it as an instrument, add it in the Instrument look-up instead."></div>
            <button class="btn small" id="alpAddBtn">Add</button>
            <button class="btn small" id="alpDefaultsBtn" title="AAPL, MSFT, NVDA, SPY, QQQ">Use the defaults</button>
            <button class="btn small" id="alpSaveBtn">Save list</button>
            <span class="dim" id="alpRouteMsg"></span>
        </div>`;
    host.querySelectorAll('button[data-alp-del]').forEach((b) => {
        b.onclick = () => {
            const next = alpSymbols().filter((s) => s !== b.dataset.alpDel);
            alpWriteSymbols(next);
        };
    });
    const add = alpC('alpAddBtn');
    if (add) add.onclick = () => {
        const inp = alpC('alpAddSym');
        const sym = ((inp && inp.value) || '').trim().toUpperCase();
        if (!sym) return;
        const list = alpSymbols();
        if (!list.includes(sym)) list.push(sym);
        alpWriteSymbols(list);
    };
    const def = alpC('alpDefaultsBtn');
    if (def) def.onclick = () => alpWriteSymbols(['AAPL', 'MSFT', 'NVDA', 'SPY', 'QQQ']);
    const save = alpC('alpSaveBtn');
    if (save) save.onclick = async () => {
        await alpSaveSymbols();
        alpRouteMsg('saved to your config file', 'ok');
    };
}

function alpRouteMsg(text, kind) {
    const el = alpC('alpRouteMsg');
    if (el) el.innerHTML = `<span class="${kind === 'err' ? 'wiz-bad' : kind === 'ok' ? 'wiz-ok' : ''}">${G_ESC(text)}</span>`;
}

/** Local edit — the list only reaches the config file on Save. */
function alpWriteSymbols(list) {
    S.config = S.config || {};
    S.config.alpaca = S.config.alpaca || {};
    S.config.alpaca.view_symbols = list;
    alpRouteRender();
}

async function alpSaveSymbols() {
    try {
        const r = await api('/api/control/config', { method: 'POST', body: S.config });
        S.config = r.config;
        alpRouteRender();
        if (typeof alpacaLoad === 'function') alpacaLoad(true);
        const card = alpC('ovAlpacaHost');
        if (card) alpOvRender();
        return true;
    } catch (e) {
        alpRouteMsg('save failed: ' + e, 'err');
        return false;
    }
}

/** Fill the Alpaca view once it is open: the shared card, the symbol list, the feed. */
function alpViewRender() {
    alpCardStyles();
    alpRouteRender();
    const note = alpC('alpRouteNote');
    if (note) note.textContent = `${alpSymbols().length} symbol(s) — this list subscribes the Alpaca feed's own stream; to chart a symbol as an instrument, add it in the Instrument look-up (Ctrl+F)`;
    if (typeof alpacaLoad === 'function') alpacaLoad(true);
    alpFeedRender();
}

/* ── the live feed card (Phase 3: REST budget, streams, subscriptions) ── */

function alpFeedPill(state) {
    const el = alpC('alpFeedPill');
    if (!el) return;
    const tone = state === 'running' || state === 'live' ? 'running'
        : state === 'error' ? 'error' : (state === 'idle' || state === 'stopped' ? 'stopped' : '');
    el.className = 'pill ' + tone;
    el.textContent = state || 'idle';
}

function alpFeedHostHTML(d) {
    if (!d || d.running === false) {
        const srcNow = String(((S.status || {}).source) || ((S.config || {}).data_source) || '');
        const onAlpaca = /(alpaca|all)/.test(srcNow);
        return `<div class="dim" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">Not running — ${G_ESC(d && d.note ? d.note : 'start the engine with Alpaca as its data source.')}
            ${onAlpaca ? '' : '<button class="btn small" id="alpFeedUseSrc" title="Set the engine data source to Alpaca — it restarts if the engine is running">Use Alpaca as the engine source</button>'}
            <span class="dim" id="alpFeedSrcMsg"></span></div>`;
    }
    const subs = d.subscriptions || {};
    const budget = d.budget || {};
    const open = d.market_open === null || d.market_open === undefined ? 'unknown'
        : (d.market_open ? 'open' : 'closed');
    const streams = (d.streams || []).map((s) => {
        const age = s.last_message_age_s === null || s.last_message_age_s === undefined ? '–' : `${s.last_message_age_s}s`;
        return `<tr>
            <td>${G_ESC(s.label)}</td>
            <td><span class="tag ${s.state === 'live' ? 'ok' : s.state === 'error' ? 'no' : ''}">${G_ESC(s.state)}</span></td>
            <td>${s.messages}</td>
            <td>${G_ESC(String(age))}</td>
            <td class="name">${G_ESC(s.last_error || '')}</td></tr>`;
    }).join('') || '<tr><td colspan="5" class="dim">no streams yet</td></tr>';
    return `
    <div class="alp-grid">
        <div class="alp-kv" title="Whether the US equity session is open right now."><div class="k">US market</div><div class="v">${open}</div></div>
        <div class="alp-kv" title="Stream symbols requested (the free plan allows 30)."><div class="k">stream symbols</div><div class="v">${subs.count || 0} / ${subs.stock_cap || 30}</div></div>
        <div class="alp-kv" title="REST calls used in the last minute against the app's own budget."><div class="k">REST budget</div><div class="v">${budget.used || 0} / ${budget.limit || 150}</div></div>
        <div class="alp-kv" title="Feed in use. Alpaca publishes no order book on any plan."><div class="k">feed</div><div class="v">${G_ESC(d.feed || 'iex')}</div></div>
    </div>
    <table class="data" style="margin-top:8px"><thead><tr><th>Stream</th><th>State</th><th>Messages</th><th>Last</th><th>Note</th></tr></thead>
    <tbody>${streams}</tbody></table>
    ${(subs.warnings || []).length ? `<div class="alp-warn">${(subs.warnings || []).map((w) => `<div>${G_ESC(w)}</div>`).join('')}</div>` : ''}
    ${(d.errors || []).length ? `<div class="alp-warn">${(d.errors || []).map((e) => `<div>${G_ESC(e)}</div>`).join('')}</div>` : ''}`;
}

async function alpFeedRender() {
    const host = alpC('alpFeedHost');
    if (!host) return;
    let d = null;
    try { d = await api('/api/control/alpaca/feed'); } catch (e) { d = null; }
    if (!d) { host.innerHTML = '<div class="dim">feed status unavailable</div>'; alpFeedPill('unknown'); return; }
    alpFeedPill(d.state || (d.running ? 'running' : 'idle'));
    host.innerHTML = alpFeedHostHTML(d);
    const useSrc = alpC('alpFeedUseSrc');
    if (useSrc) useSrc.onclick = () => { void alpUseSource(); };

    // the feed selector: only offer what this account is entitled to
    const caps = (S.caps && S.caps.alpaca) || {};
    const sel = alpC('alpFeedSelect');
    const hint = alpC('alpFeedHint');
    if (sel) {
        const allowed = caps.feeds || ['iex'];
        Array.from(sel.options).forEach((opt) => {
            opt.disabled = !allowed.includes(opt.value);
            opt.title = opt.disabled ? 'Not included in this account\'s plan — the capability report says so.' : opt.title;
        });
        const wanted = ((S.config || {}).alpaca || {}).feed || caps.selected_feed || 'iex';
        sel.value = allowed.includes(wanted) ? wanted : 'iex';
    }
    if (hint) {
        hint.textContent = (caps.feeds || ['iex']).length > 1
            ? 'This account can reach SIP as well — real-time SIP still needs the paid plan; Basic reads it 15 minutes late.'
            : 'Free plan: real-time IEX (one venue) and SIP history once it is older than 15 minutes.';
    }
}

async function alpFeedSave() {
    const sel = alpC('alpFeedSelect');
    const msg = alpC('alpFeedMsg');
    if (!sel) return;
    const feed = sel.value;
    try {
        /* §83: patch the stored field — re-posting the page's whole config could roll back
           anything written since boot (the same class as the keys that "did not save"). */
        const r = await api('/api/control/config', { method: 'POST', body: { alpaca: { feed: feed } } });
        S.config = r.config;
        const boot = await api('/api/control/bootstrap');
        S.caps = boot.capabilities || S.caps;
        if (msg) msg.innerHTML = `<span class="wiz-ok">saved: ${G_ESC(feed)} — press Start (or restart) to apply</span>`;
        alpFeedRender();
    } catch (e) {
        if (msg) msg.innerHTML = `<span class="wiz-bad">save failed: ${G_ESC(String(e))}</span>`;
    }
}

/* ── depth gating: the one thing Alpaca cannot do ───────────────────── */

/** Reason string when this symbol's depth views genuinely cannot run, else null.
 *
 *  Only true while Alpaca is actually the data source for the symbol: with the
 *  exchange feed streaming BTCUSDT, depth exists and a warning would be a lie. */
function alpDepthGate(symbol) {
    const al = (S.caps && S.caps.alpaca) || {};
    if (!symbol || al.depth) return null;
    const source = String(((S.status || {}).source) || ((S.config || {}).data_source) || '');
    if (!/(alpaca|all)/.test(source)) return null;
    if (!(symbol in (al.symbols || {}))) return null;      // not an Alpaca symbol
    return al.depth_reason || 'Alpaca publishes trades, quotes and bars — no order book.';
}

const ALP_GATED_VIEWS = ['heatmap', 'depth', 'overview'];

function alpGateApply(viewName) {
    if (!ALP_GATED_VIEWS.includes(viewName)) return;
    const view = document.querySelector('.view[data-view="' + viewName + '"]');
    if (!view) return;
    const id = 'alpGate-' + viewName;
    let host = alpC(id);
    const reason = alpDepthGate(S.symbol);
    if (!reason) { if (host) host.remove(); return; }
    if (!host) {
        host = document.createElement('div');
        host.id = id;
        const head = view.querySelector('.view-head');
        if (head) head.insertAdjacentElement('afterend', host);
        else view.insertBefore(host, view.firstChild);
    }
    host.innerHTML = `<div class="banner warn">Depth is not available for <b>${G_ESC(S.symbol)}</b> on Alpaca: ${G_ESC(reason)}</div>`;
}

/** Re-check the gate whenever the instrument changes or the engine state changes. */
function alpGateRefresh() {
    const active = document.querySelector('.nav-item.active');
    if (active && active.dataset.view) alpGateApply(active.dataset.view);
}

/* ── polling: only what the user is looking at ─────────────────── */

function alpPoll() {
    const ov = document.querySelector('.view[data-view="overview"]');
    const av = document.querySelector('.view[data-view="alpaca"]');
    const keys = [
        ov && ov.classList.contains('active') ? 'overview' : '',
        av && av.classList.contains('active') ? 'alpaca' : '',
    ].filter(Boolean).join('|');
    if (!keys) return;
    if (keys !== ALPCARD.lastKey) {
        ALPCARD.lastKey = keys;
        if (keys.includes('overview')) { alpBannerRender(); alpOvRender(); }
        if (keys.includes('alpaca')) alpViewRender();
        alpGateRefresh();
    }
    // refresh the shared status (8 s throttle inside alpaca.js) when the card is up
    if (typeof alpacaLoad === 'function' && Date.now() - ALPCARD.lastLoad > 8000) {
        ALPCARD.lastLoad = Date.now();
        alpacaLoad(true);
        if (keys.includes('alpaca')) alpFeedRender();
    }
}

/* Re-render the overview card shortly after any status load, so the pill and the
   account boxes follow alpaca.js without either module owning the other. */
if (typeof ALPACA !== 'undefined') {
    setInterval(() => {
        const host = alpC('ovAlpacaHost');
        const ov = document.querySelector('.view[data-view="overview"]');
        if (host && ov && ov.classList.contains('active') && (ALPACA.status || null)) alpOvRender();
    }, 6000);
}

(function alpCardBoot() {
    alpCardStyles();
    // wrap showView so opening either view renders immediately (ui.js calls ensurePanel too)
    const wrap = window.showView;
    if (typeof wrap === 'function' && !wrap.__ofapWrapped_alpacaCard) {
        const wrapped = function (name) {
            const out = wrap.apply(this, arguments);
            if (name === 'overview') setTimeout(() => { alpBannerRender(); alpOvRender(); }, 120);
            if (name === 'alpaca') setTimeout(alpViewRender, 120);
            setTimeout(() => alpGateApply(name), 320);      // depth gating for Alpaca symbols
            return out;
        };
        wrapped.__ofapWrapped_alpacaCard = true;
        window.showView = wrapped;
    }
    setTimeout(async () => {
        try { await alpBannerResetIfDismissed(); } catch (e) { /* ignore */ }
        alpBannerRender();
        alpOvRender();
    }, 1500);
    const wiz = document.getElementById('alpWizard');
    if (wiz) wiz.onclick = () => { if (typeof openWizard === 'function') openWizard(true); };
    const feedSave = document.getElementById('alpFeedSave');
    if (feedSave) feedSave.onclick = alpFeedSave;
    // the instrument selector and the engine state both change what the gate should say
    document.addEventListener('change', (ev) => {
        if (ev.target && ev.target.id === 'symbolSelect') setTimeout(alpGateRefresh, 250);
    });
    setInterval(() => { if (window.OFAPINTENT && OFAPINTENT.anyHeld()) return; alpPoll(); }, 2500);
    window.ALPCARD = ALPCARD;
})();
