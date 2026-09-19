/* ══════════════════════════════════════════════════════════════════
   Alpaca Markets — the "add your account" section.

   Links a real US brokerage account to this app: US stocks, ETFs, options and crypto
   instruments, a real paper-trading environment (free, email signup only), Benzinga
   news, the market calendar, and later orders/positions/P&L.

   The card states its own limits as clearly as its features: Alpaca publishes trades,
   quotes and bars — no order book — so the heatmap, DOM ladder and participants'-intent
   reader cannot run on Alpaca data, and the capability report says so rather than
   letting the user wonder why those panels look empty.
   ══════════════════════════════════════════════════════════════════ */

const ALPACA = { report: null, status: null, busy: false, lastLoad: 0 };

function alpacaStyles() {
    if (document.getElementById('alpacaStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'alpacaStyleSheet';
    st.textContent = `
        .alp-card .field label { display: block; margin-bottom: 3px; }
        .alp-status { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px;
                      padding: 2px 10px; font-size: 11px; border: 1px solid var(--line); }
        .alp-status.on { color: #58c882; border-color: rgba(88,200,130,0.5); background: rgba(88,200,130,0.08); }
        .alp-status.off { color: var(--dim); }
        .alp-cap { display: flex; gap: 8px; padding: 4px 0; border-bottom: 1px solid var(--line); font-size: 12px; }
        .alp-cap:last-child { border-bottom: 0; }
        .alp-cap .mark { flex: 0 0 16px; text-align: center; }
        .alp-cap .yes { color: #58c882; } .alp-cap .no { color: #e8be54; }
        .alp-cap .why { color: var(--dim); }
        .alp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-top: 8px; }
        .alp-kv { border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; }
        .alp-kv .k { color: var(--dim); font-size: 11px; } .alp-kv .v { font-size: 14px; }
        .alp-warn { border-left: 3px solid rgba(232,190,84,0.65); background: rgba(232,190,84,0.06);
                    padding: 8px 10px; margin-top: 10px; font-size: 12px; color: var(--dim); }
        .alp-adds { margin-top: 10px; font-size: 12px; }
        .alp-adds td { padding: 3px 8px 3px 0; vertical-align: top; }
    `;
    document.head.appendChild(st);
}

function alpacaEl(id) { return document.getElementById(id); }

/** Never rebuild this card while the cursor is in it. */
function alpacaIsEditing() {
    const card = alpacaEl('alpCard');
    const act = document.activeElement;
    return !!(card && act && card.contains(act) &&
        act.matches && act.matches('input, select, textarea'));
}

function alpacaStatusPill() {
    const st = ALPACA.status || {};
    if (st.configured) {
        const env = st.paper ? 'paper' : 'live';
        const ok = (ALPACA.report || {}).ok;
        return `<span class="alp-status ${ok ? 'on' : 'off'}"
                    title="Key stored locally as ${st.key_masked || '(hidden)'} — the full secret is never shown again.">
                    ${ok ? '\u25cf' : '\u25cb'} ${env} account${ok ? ' connected' : ' (not verified yet)'}</span>`;
    }
    return `<span class="alp-status off" title="No Alpaca account linked. Everything else in the program keeps working without one.">\u25cb not connected</span>`;
}

function alpacaCapabilityRow(label, ok, why) {
    return `<div class="alp-cap"><span class="mark ${ok ? 'yes' : 'no'}">${ok ? '\u2713' : '\u2715'}</span>
        <span><b>${label}</b> <span class="why">— ${why}</span></span></div>`;
}

function alpacaCapabilities() {
    const r = ALPACA.report || {};
    if (!r.ok) return '';
    const c = r.capabilities || {};
    const acc = r.account || {};
    return `
    <div class="alp-grid">
        <div class="alp-kv" title="Cash in the account."><div class="k">cash</div><div class="v">${acc.cash ?? '–'}</div></div>
        <div class="alp-kv" title="Account equity including positions."><div class="k">equity</div><div class="v">${acc.equity ?? '–'}</div></div>
        <div class="alp-kv" title="What the account can deploy right now (margin included)."><div class="k">buying power</div><div class="v">${acc.buying_power ?? '–'}</div></div>
        <div class="alp-kv" title="Day trades used in the rolling 5-day window."><div class="k">day trades</div><div class="v">${acc.daytrade_count ?? '–'}</div></div>
    </div>
    <div style="margin-top:12px">
        ${alpacaCapabilityRow('Real-time US equities tape (IEX)', !!c.equities_realtime_iex,
            'trades for live delta, footprint, VWAP and profile — 30 stream symbols on the free plan')}
        ${alpacaCapabilityRow('Full-market (SIP) history, 15 minutes delayed', !!c.equities_sip_delayed,
            'complete tape for everything older than 15 minutes — the free plan\u2019s window')}
        ${alpacaCapabilityRow('Benzinga news', !!c.news, 'headlines with symbols, into the market-context panel')}
        ${alpacaCapabilityRow('Market calendar', !!c.market_clock,
            'the app can know when US equities are open, and behave accordingly')}
        ${alpacaCapabilityRow('Options data', !!c.options_data, 'indicative feed on the free plan')}
        ${alpacaCapabilityRow('Positions, orders and portfolio history', !!c.positions,
            'a real Portfolio view: holdings, open orders, equity curve')}
        ${alpacaCapabilityRow('Order book / depth', false,
            'NOT published by Alpaca — the heatmap, DOM ladder and intent reader cannot run on these symbols')}
    </div>
    ${(r.entitlement_notes || []).length ? `<div class="alp-warn">${(r.entitlement_notes || [])
        .map((n) => `<div>${G_ESC(n)}</div>`).join('')}</div>` : ''}`;
}

/** Compact capability read-out for one report — the wizard prints this after a
 *  successful test so the user sees what their plan actually reaches. */
function alpacaCapabilitySummaryHTML(report) {
    const c = (report || {}).capabilities || {};
    const rows = [
        ['IEX real-time tape', !!c.equities_realtime_iex],
        ['Full-market history (15 min delayed)', !!c.equities_sip_delayed],
        ['Options data', !!c.options_data],
        ['News + market calendar', !!(c.news && c.market_clock)],
        ['Positions / orders / portfolio', !!c.positions],
        ['Order book (depth)', false],
    ].map(([label, ok]) => alpacaCapabilityRow(label, ok, ok
        ? 'available on this account'
        : (label === 'Order book (depth)'
            ? 'not published by Alpaca — depth views stay on the exchange feed'
            : 'not enabled on this account'))).join('');
    return `<div style="margin-top:8px">${rows}</div>`;
}

function alpacaCardHTML() {
    const st = ALPACA.status || {};
    const env = st.paper === false ? 'live' : 'paper';
    return `
    <div class="card alp-card" id="alpCard" style="margin-bottom:12px">
        <div class="card-head">
            <span class="card-title">Broker account — Alpaca Markets</span>
            <span style="margin-left:10px">${alpacaStatusPill()}</span>
            <div class="grow" style="flex:1"></div>
            <button class="btn small" data-help="alpaca"
                title="Step-by-step: create an account, generate keys, and what a paper account can do">How to get keys</button>
        </div>
        <div class="card-body">
            <p class="dim" style="margin-top:0">Optional. Alpaca is a real US brokerage with an API: commission-free
            stocks, ETFs, options and crypto, and a <b>free paper-trading account</b> you can open with just an
            email address. Linking adds those instruments to the scanner, the news feed and the calendar — and,
            later, orders, positions and P&amp;L. Nothing in the program requires it.</p>
            <div class="row" style="gap:10px;flex-wrap:wrap">
                <div class="field" style="flex:1;min-width:220px">
                    <label>API key ID</label>
                    <input type="text" id="alpKey" autocomplete="off" spellcheck="false"
                        placeholder="${st.key_masked ? G_ESC(st.key_masked) : 'PK…'}"
                        title="From your Alpaca dashboard → API keys. Paper and live keys are different pairs.">
                </div>
                <div class="field" style="flex:1;min-width:220px">
                    <label>API secret</label>
                    <input type="password" id="alpSecret" autocomplete="new-password"
                        placeholder="${st.configured ? '(saved — type to replace)' : 'your secret key'}"
                        title="Stored in your local config file only, never shown again after saving, never sent anywhere except Alpaca.">
                </div>
                <div class="field" style="flex:0 0 170px">
                    <label>Environment</label>
                    <select id="alpPaper" title="Paper is Alpaca's simulation with virtual money — identical API, no funding, resettable. Live uses real money.">
                        <option value="1" ${env === 'paper' ? 'selected' : ''}>Paper (simulation, free)</option>
                        <option value="0" ${env === 'live' ? 'selected' : ''}>Live (real money)</option>
                    </select>
                </div>
            </div>
            <div class="row" style="gap:8px;flex-wrap:wrap;margin-top:10px">
                <button class="btn primary" id="alpValidate"
                    title="Ask Alpaca to confirm the keys, then report what this account can reach">Validate &amp; save</button>
                <button class="btn small" id="alpTestOnly"
                    title="Check the keys without saving anything">Test without saving</button>
                <button class="btn small" id="alpClear"
                    title="Forget the stored keys entirely">Remove keys</button>
                <span class="dim" id="alpResult"></span>
            </div>
            <div id="alpCap">${alpacaCapabilities()}</div>
            <table class="alp-adds">
                <tr><td class="dim">Adds</td><td>US equities / ETFs / options / crypto instruments, real-time IEX tape
                    (30 symbols on the free plan), 15-minute-delayed full-market history, Benzinga news, the US market
                    calendar, and — in the next phase — paper orders, positions and a portfolio view.</td></tr>
                <tr><td class="dim">Cannot add</td><td>Order-book depth. Alpaca publishes trades, quotes and bars only,
                    so the heatmap, the DOM ladder and the participants'-intent reader stay on the exchange feed (and
                    the optional MT5 terminal), which do publish depth.</td></tr>
                <tr><td class="dim">Data honesty</td><td>Free-plan real-time US data is IEX (a single venue, a small
                    share of volume); full-market SIP data is readable but only once it is older than 15 minutes. The
                    app labels which feed a panel is showing.</td></tr>
            </table>
        </div>
    </div>`;
}

/** Where the card lives: the Alpaca view is its home, Settings is the fallback
 *  (an install whose markup predates the view still gets a working card). */
function alpacaHost() {
    const alpView = document.querySelector('.view[data-view="alpaca"]');
    if (alpView) return alpacaEl('alpCardHost') || alpView;
    const settings = document.querySelector('.view[data-view="settings"]');
    if (settings && settings.classList.contains('active')) return settings.querySelector('.card-body') || settings;
    return null;
}

function alpacaEnsureCard() {
    const host = alpacaHost();
    if (!host) return;
    alpacaStyles();
    let card = alpacaEl('alpCard');
    if (card && !host.contains(card)) { card.remove(); card = null; }
    if (!card) {
        const wrap = document.createElement('div');
        wrap.innerHTML = alpacaCardHTML();
        card = wrap.firstElementChild;
        host.appendChild(card);
        alpacaWire();
    } else if (!alpacaIsEditing()) {
        card.outerHTML = alpacaCardHTML();
        alpacaWire();
    }
}

function alpacaMsg(text, kind) {
    const el = alpacaEl('alpResult');
    if (el) el.innerHTML = `<span class="${kind === 'err' ? 'wiz-bad' : kind === 'ok' ? 'wiz-ok' : ''}">${G_ESC(text)}</span>`;
}

async function alpacaLoad(force) {
    if (ALPACA.busy) return;
    if (!force && Date.now() - ALPACA.lastLoad < 8000) return;
    ALPACA.busy = true;
    try {
        const st = await api('/api/control/alpaca/status');
        ALPACA.status = st;
        ALPACA.report = st.report || null;
        ALPACA.lastLoad = Date.now();
        if (!alpacaIsEditing()) alpacaEnsureCard();
    } catch (e) { /* the card stays as it was */ }
    ALPACA.busy = false;
}

/** Validate/save keys. `opts` lets the setup assistant reuse this exact path with
 *  its own inputs and message line — one implementation, two front doors. */
async function alpacaSubmit(mode, opts) {
    const o = opts || {};
    const msg = typeof o.msg === 'function' ? o.msg : alpacaMsg;
    const key = ((document.getElementById(o.keyId || 'alpKey') || {}).value || '');
    const secret = ((document.getElementById(o.secretId || 'alpSecret') || {}).value || '');
    const paperEl = document.getElementById(o.paperId || 'alpPaper');
    const paper = paperEl ? paperEl.value !== '0' : true;
    if (!key || !secret) { msg('Both the key ID and the secret are needed.', 'err'); return; }
    msg('asking Alpaca…');
    try {
        const body = { key_id: key, secret, paper, save: mode === 'save' };
        const r = await api('/api/control/alpaca/test', { method: 'POST', body });
        ALPACA.report = r;
        if (r.ok && mode === 'save') {
            msg('Saved — account linked.', 'ok');
            ALPACA.lastLoad = 0;
            if (o.refresh !== false) { await alpacaLoad(true); }
            msg('Saved — account linked.', 'ok');
        } else if (r.ok) {
            msg('Keys work. Press “Validate & save” to keep them.', 'ok');
            if (o.refresh !== false) alpacaEnsureCard();
        } else {
            msg(r.message || 'Alpaca did not accept those keys.', 'err');
            if (r.help) msg((r.message || '') + '  →  ' + r.help, 'err');
        }
    } catch (e) {
        msg('Request failed: ' + e, 'err');
    }
}

function alpacaWire() {
    const v = alpacaEl('alpValidate');
    if (v) v.onclick = () => alpacaSubmit('save');
    const t = alpacaEl('alpTestOnly');
    if (t) t.onclick = () => alpacaSubmit('test');
    const c = alpacaEl('alpClear');
    if (c) {
        c.onclick = async () => {
            try {
                await api('/api/control/alpaca/clear', { method: 'POST', body: {} });
                ALPACA.report = null; ALPACA.lastLoad = 0;
                await alpacaLoad(true);
                alpacaMsg('Stored keys removed.', 'ok');
            } catch (e) { alpacaMsg('Could not remove: ' + e, 'err'); }
        };
    }
}

/* load when the settings view opens (and once at boot if it is already open) */
(function alpacaBoot() {
    const wrapShow = window.showView;
    if (typeof wrapShow === 'function' && !wrapShow.__ofapWrapped_alpaca) {
        const wrapped = function (name) {
            const out = wrapShow.apply(this, arguments);
            // the Alpaca view is the card's home; Settings keeps a pointer to it
            if (name === 'settings' || name === 'alpaca') {
                setTimeout(() => {
                    const section = document.querySelector('.view[data-view="alpaca"]')
                        || document.querySelector('.view[data-view="settings"]');
                    if (!section || section.classList.contains('active')) alpacaLoad(true);
                }, 700);
            }
            return out;
        };
        wrapped.__ofapWrapped_alpaca = true;      // C-09/D-14: a second decoration is not chained
        window.showView = wrapped;
    }
    setTimeout(() => alpacaLoad(true), 9000);
})();
