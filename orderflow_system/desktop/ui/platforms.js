/* platforms.js — the Sierra Chart integration: workflow, account links, plans, DTC bridge.
 *
 * Free path first: the trial and the delayed data feed need no payment, and every step is linked to
 * the vendor's own page. Paid tiers are listed with their published monthly prices, the date they
 * were read and the exchange-fee caveat, with the source link beside them — transparency over
 * persuasion. The plan toggle changes what the suite says about the feed and what it reminds you of.
 */
(function () {
    'use strict';

    const PLAT = { data: null, plan: 'free', integrated: false, bmPlan: 'digital', bmIntegrated: false,
                   ntPlan: 'free', ntIntegrated: false };
    const el = (id) => document.getElementById(id);
    function plEsc(t) {
        return String(t == null ? '' : t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    }
    function api(path, options) {
        if (typeof window.api === 'function') return window.api(path, options);
        const opts = options ? { ...options } : undefined;
        if (opts && opts.body) {
            opts.body = JSON.stringify(opts.body);
            opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
        }
        return fetch(path, opts).then((r) => r.json());
    }
    const link = (id) => ((PLAT.data && PLAT.data.links) || []).find((l) => l.id === id) || null;

    async function plLoad() {
        try {
            PLAT.data = await api('/api/control/platforms');
        } catch (err) {
            PLAT.data = { sierra: {}, note: `integration state unavailable: ${err}` };
        }
        const s = (PLAT.data && PLAT.data.sierra) || {};
        PLAT.plan = s.plan || 'free';
        PLAT.integrated = !!s.integrated;
        const bm = (PLAT.data && PLAT.data.bookmap) || {};
        PLAT.bmPlan = bm.plan || 'digital';
        PLAT.bmIntegrated = !!bm.integrated;
        const nt = (PLAT.data && PLAT.data.ninjatrader) || {};
        PLAT.ntPlan = nt.plan || 'free';
        PLAT.ntIntegrated = !!nt.integrated;
        plRender();
    }

    function plHeader() {
        const s = (PLAT.data && PLAT.data.sierra) || {};
        const plans = (PLAT.data && PLAT.data.plans) || [];
        const chosen = plans.find((p) => p.id === PLAT.plan) || plans[0] || { name: 'Free' };
        return `<div class="card"><div class="card-head">
            <span class="card-title">Sierra Chart integration</span>
            <div class="spacer"></div>
            <span class="dim">${s.integrated ? 'loaded' : 'not loaded'}</span>
            <label class="switch"><input type="checkbox" id="plIntegrated" ${s.integrated ? 'checked' : ''}> Load into my workflow</label>
        </div><div class="card-body">
            <p class="dim">Optional: read Sierra Chart over its own DTC protocol server — real orders,
            real depth, no plugin installed into their software and no account details stored here.
            ${plEsc((PLAT.data && PLAT.data.free_note) || 'The free trial and the delayed data feed need no payment.')}</p>
            <div class="field-row">
                <label>Plan you run
                    <select id="plPlan">${plans.map((p) => `<option value="${p.id}" ${p.id === PLAT.plan ? 'selected' : ''}>${plEsc(p.name)}${p.price === '0' ? ' — free' : ` — $${plEsc(p.price)}/mo`}</option>`).join('')}</select>
                </label>
                <button class="btn small" id="plPlanSave">Apply</button>
                <span class="dim">now: ${plEsc(chosen.name)}</span>
            </div>
        </div></div>`;
    }

    function plWorkflow() {
        const wf = (PLAT.data && PLAT.data.workflow) || { steps: [], suite_changes: [] };
        return `<div class="card"><div class="card-head"><span class="card-title">Setup — ${plEsc(wf.plan_kind === 'free' ? 'free path first' : 'paid path')}</span></div>
        <div class="card-body">
            <ol class="pl-steps">${(wf.steps || []).map((step) => {
                const l = link(step.link);
                return `<li><b>${plEsc(step.title)}</b><div class="dim">${plEsc(step.text)}
                    ${l ? `<button class="pl-link" data-url="${plEsc(l.url)}">${plEsc(l.label)} ↗</button>` : ''}</div></li>`;
            }).join('')}</ol>
            <div class="pl-changes"><b>What this suite changes for that plan</b>
                <ul>${(wf.suite_changes || []).map((c) => `<li>${plEsc(c)}</li>`).join('')}</ul></div>
        </div></div>`;
    }

    function plPlans() {
        const plans = (PLAT.data && PLAT.data.plans) || [];
        const cat = (PLAT.data && PLAT.data.catalogue) || {};
        return `<div class="card"><div class="card-head"><span class="card-title">Plans — free first, paid tiers as published</span>
            <div class="spacer"></div><span class="dim">read ${plEsc((PLAT.data && PLAT.data.prices_as_of) || '')}</span></div>
        <div class="card-body">
            ${plans.map((p) => `<div class="pl-plan ${p.id === PLAT.plan ? 'on' : ''}">
                <div class="pl-plan-head"><b>${plEsc(p.name)}</b>
                    <span class="pl-price">${p.price === '0' ? 'free' : `$${plEsc(p.price)} ${plEsc(p.period)}`}</span>
                    ${p.id === PLAT.plan ? '<span class="pl-badge">in use</span>' : ''}</div>
                <ul>${(p.includes || []).map((i) => `<li>${plEsc(i)}</li>`).join('')}</ul></div>`).join('')}
            <div class="dim">${((PLAT.data && PLAT.data.caveats) || []).map((c) => plEsc(c)).join(' ')}</div>
            <div class="field-row">
                ${((cat.platforms || [])[0] || {}).links ? (((cat.platforms || [])[0].links || []).filter((l) => ['pricing', 'trial', 'delayed', 'payment'].includes(l.id))
                    .map((l) => `<button class="pl-link" data-url="${plEsc(l.url)}">${plEsc(l.label)} ↗</button>`).join('')) : ''}
            </div>
        </div></div>`;
    }

    function plInstall() {
        const inst = (PLAT.data && PLAT.data.installs) || {};
        const s = inst.sierra || { found: false };
        return `<div class="card"><div class="card-head"><span class="card-title">On this machine</span>
            <div class="spacer"></div><span class="dim">${s.found ? `detected${s.version ? ' · build ' + plEsc(s.version) : ''}` : 'not detected'}</span></div>
        <div class="card-body"><p class="dim">${s.found
            ? `Found at ${plEsc(s.path)}${s.dtc_folder ? ' — its DTC folder is present.' : '.'} Files, logs and licence keys of that install are never read.`
            : 'Not installed here. The workflow above covers install and account creation; the suite works fully on its built-in free feeds meanwhile.'}</p></div></div>`;
    }

    function plDtcCard() {
        const s = (PLAT.data && PLAT.data.sierra) || {};
        const syms = (PLAT.data && PLAT.data.suggested_symbols) || [];
        return `
    <div class="card"><div class="card-head"><span class="card-title">DTC connection</span>
        <div class="spacer"></div><span class="dim" id="plDtcState">${s.enabled ? 'enabled' : 'disabled'}</span></div>
        <div class="card-body">
            <p class="dim">The DTC protocol server must be enabled in the platform: <i>Global Settings →
            Server Settings → DTC Protocol Server</i>, encoding <b>JSON</b>. Credentials are optional;
            if the server asks for them, set them here too.</p>
            <div class="field-row">
                <label>Host<input id="plDtcHost" value="${plEsc(s.host || '127.0.0.1')}" size="14"></label>
                <label>Port<input id="plDtcPort" value="${plEsc(s.port || 11099)}" size="7"></label>
                <label>Username<input id="plDtcUser" value="${plEsc(s.username || '')}" size="14" autocomplete="off"></label>
                <label>Password<input id="plDtcPass" type="password" placeholder="${s.password_set ? '•••• saved' : 'not set'}"
                       size="14" autocomplete="new-password"></label>
                <label>Symbol<input id="plDtcSymbol" value="${plEsc(s.symbol || (syms[0] || ''))}" size="12"
                       placeholder="e.g. ${plEsc(syms[0] || 'ESZ6')}"></label>
                <label class="switch"><input type="checkbox" id="plDtcTls" ${s.use_tls ? 'checked' : ''}> TLS</label>
                <label class="switch"><input type="checkbox" id="plDtcEnabled" ${s.enabled ? 'checked' : ''}> Enabled</label>
            </div>
            <div class="field-row">
                <button class="btn small" id="plDtcSave">Save</button>
                <button class="btn small" id="plDtcTest">Test connection</button>
                ${s.password_set ? '<button class="btn small" id="plDtcClear">Clear password</button>' : ''}
                <span class="dim">${plEsc(((PLAT.data || {}).note) || '')}</span>
            </div>
            <div id="plDtcResult"></div>
        </div></div>`;
    }

    /* ── Bookmap ────────────────────────────────────────────────────────────────────────────
       Same shape as the Sierra cards, different physics: Bookmap has no data-out API and no local
       server, so the "bridge" here is a small read-only add-on the suite ships for the user to build
       once and add inside Bookmap. The free tier and its limits are stated on the card, not buried. */
    function bmLink(id) {
        return ((PLAT.data && PLAT.data.bookmap_links) || []).find((l) => l.id === id) || null;
    }
    function bmPlans() { return (PLAT.data && PLAT.data.bookmap_plans) || []; }

    function bmHeader() {
        const bm = (PLAT.data && PLAT.data.bookmap) || {};
        const plans = bmPlans();
        const chosen = plans.find((p) => p.id === PLAT.bmPlan) || plans[0] || { name: 'Digital' };
        return `<div class="card"><div class="card-head">
            <span class="card-title">Bookmap integration</span>
            <div class="spacer"></div>
            <span class="dim">${bm.integrated ? 'loaded' : 'not loaded'}</span>
            <label class="switch"><input type="checkbox" id="bmIntegrated" ${bm.integrated ? 'checked' : ''}> Load into my workflow</label>
        </div><div class="card-body">
            <p class="dim">Optional: Bookmap publishes no market-data-out API, so this suite ships a
            small <b>read-only</b> add-on — build it once against your own Bookmap's jars, add it in
            <i>Settings → Configure API plugins</i>, and it republishes the live trades and depth it
            already has on loopback. No orders, no account access, nothing leaves this machine.
            ${plEsc((PLAT.data && PLAT.data.bookmap_free_note) || '')}</p>
            <div class="field-row">
                <label>Tier you run
                    <select id="bmPlan">${plans.map((p) => `<option value="${p.id}" ${p.id === PLAT.bmPlan ? 'selected' : ''}>${plEsc(p.name)}${p.price === '0' ? ' — free' : ` — $${plEsc(p.price)}/mo`}</option>`).join('')}</select>
                </label>
                <button class="btn small" id="bmPlanSave">Apply</button>
                <span class="dim">now: ${plEsc(chosen.name)}</span>
            </div>
        </div></div>`;
    }

    function bmWorkflow() {
        const wf = (PLAT.data && PLAT.data.bookmap_workflow) || { steps: [], suite_changes: [] };
        return `<div class="card"><div class="card-head"><span class="card-title">Bookmap setup — ${plEsc(wf.plan_kind === 'free' ? 'free path first' : 'paid path')}</span>
        <div class="spacer"></div><span class="dim">${plEsc(wf.instruments ? wf.instruments + ' instrument(s) · ' + (wf.backfill || '') : '')}</span></div>
        <div class="card-body">
            <ol class="pl-steps">${(wf.steps || []).map((step) => {
                const l = bmLink(step.link);
                return `<li><b>${plEsc(step.title)}</b><div class="dim">${plEsc(step.text)}
                    ${l ? `<button class="pl-link" data-url="${plEsc(l.url)}">${plEsc(l.label)} ↗</button>` : ''}</div></li>`;
            }).join('')}</ol>
            <div class="pl-changes"><b>What this suite changes for that tier</b>
                <ul>${(wf.suite_changes || []).map((c) => `<li>${plEsc(c)}</li>`).join('')}</ul></div>
        </div></div>`;
    }

    function bmPlanCards() {
        const plans = bmPlans();
        return `<div class="card"><div class="card-head"><span class="card-title">Bookmap tiers — free first, paid tiers as published</span>
            <div class="spacer"></div><span class="dim">read ${plEsc((PLAT.data && PLAT.data.bookmap_prices_as_of) || '')}</span></div>
        <div class="card-body">
            ${plans.map((p) => `<div class="pl-plan ${p.id === PLAT.bmPlan ? 'on' : ''}">
                <div class="pl-plan-head"><b>${plEsc(p.name)}</b>
                    <span class="pl-price">${p.price === '0' ? 'free' : `$${plEsc(p.price)} ${plEsc(p.period)}`}</span>
                    ${p.yearly ? `<span class="dim">$${plEsc(p.yearly)}/mo billed yearly${p.lifetime ? ` · $${plEsc(p.lifetime)} lifetime` : ''}</span>` : ''}
                    ${p.id === PLAT.bmPlan ? '<span class="pl-badge">in use</span>' : ''}</div>
                <ul>${(p.includes || []).map((i) => `<li>${plEsc(i)}</li>`).join('')}</ul>
                <div class="dim">at a time: <b>${plEsc(p.instruments)}</b> instrument(s) · backfill ${plEsc(p.backfill || '—')}</div></div>`).join('')}
            <div class="dim">${((PLAT.data && PLAT.data.bookmap_caveats) || []).map((c) => plEsc(c)).join(' ')}</div>
            <div class="field-row">
                ${(PLAT.data && PLAT.data.bookmap_links || []).filter((l) => ['pricing', 'free', 'crypto', 'datapricing', 'dxfeed', 'portal'].includes(l.id))
                    .map((l) => `<button class="pl-link" data-url="${plEsc(l.url)}">${plEsc(l.label)} ↗</button>`).join('')}
            </div>
        </div></div>`;
    }

    function bmInstall() {
        const inst = (PLAT.data && PLAT.data.installs) || {};
        const b = inst.bookmap || { found: false };
        const mods = (b.api_modules || {});
        const installed = (mods.layer1 || []).map((m) => `${plEsc(m.name)}${m.version ? ' ' + plEsc(m.version) : ''}`);
        const adapters = (mods.layer0 || []).length;
        return `<div class="card"><div class="card-head"><span class="card-title">Bookmap on this machine</span>
            <div class="spacer"></div><span class="dim">${b.found ? `detected${b.version ? ' · ' + plEsc(b.version) : ''}` : 'not detected'}</span></div>
        <div class="card-body"><p class="dim">${b.found
            ? `Found at ${plEsc(b.path)}${b.api_jars ? ' — the add-on API jars are present (bm-l1api, bm-simplified-api-wrapper), so the bridge template builds against exactly what your Bookmap runs.' : '.'}
               Add-ons installed: ${installed.length ? installed.join(', ') : 'none yet'}${mods.bridge_installed ? ' — including this suite\'s bridge.' : '.'}
               ${adapters ? `${adapters} data adapter(s) present.` : ''}
               Its licence, account and config files are never read.`
            : 'Not installed here. The workflow above covers install and account creation; the suite works fully on its built-in free feeds meanwhile.'}</p></div></div>`;
    }

    function bmJarLine() {
        const b = (PLAT.data && PLAT.data.bookmap_bridge) || {};
        const jar = b.jar || {};
        const state = b.ok === true ? 'ok' : (b.ok === false ? 'warn' : '');
        const size = jar.size ? (Math.round(jar.size / 102.4) / 10) + ' KB' : '';
        return `<div class="field-row">
            <b>Add-on jar:</b> <span class="${state}">${jar.exists ? 'shipped with this app' : 'missing from this install'}</span>
            ${jar.built_for ? `<span class="dim">built for Java ${plEsc(jar.built_for)}${size ? ' · ' + size : ''}</span>` : ''}
            ${b.bookmap_runtime ? `<span class="dim">· your Bookmap runs ${plEsc(b.bookmap_runtime)}</span>` : ''}
            <button class="btn small" id="bmJarOpen">Show the jar</button>
        </div>
        <div class="dim" id="bmJarNote">${plEsc(b.note || '')}</div>
        <div class="dim" id="bmJarPath" style="word-break:break-all">${plEsc(jar.path || '')}</div>`;
    }

    function bmBridgeCard() {
        const bm = (PLAT.data && PLAT.data.bookmap) || {};
        const syms = (PLAT.data && PLAT.data.suggested_symbols) || [];
        const build = bmLink('setup_api');
        return `
    <div class="card"><div class="card-head"><span class="card-title">Bookmap bridge (loopback)</span>
        <div class="spacer"></div><span class="dim" id="bmBridgeState">${bm.enabled ? 'enabled' : 'disabled'}${bm.addon_built ? ' · add-on added' : ''}</span></div>
        <div class="card-body">
            <p class="dim">The add-on is the <b>server</b> — it prints <i>listening on 127.0.0.1:&lt;port&gt;</i>
            in Bookmap's log when it loads. The jar <b>ships with this app</b> (no compiler needed): add it
            once in <i>Settings → Configure API plugins → Add</i>, attach it to a chart, then enter that
            host and port here and press Test connection.
            ${build ? `<button class="pl-link" data-url="${plEsc(build.url)}">the API tutorial it was written against ↗</button>` : ''}</p>
            ${bmJarLine()}
            <div class="field-row">
                <label>Host<input id="bmHost" value="${plEsc(bm.host || '127.0.0.1')}" size="14"></label>
                <label>Port<input id="bmPort" value="${plEsc(bm.port || 8791)}" size="7"></label>
                <label>Symbol<input id="bmSymbol" value="${plEsc(bm.symbol || (syms[0] || ''))}" size="12"
                       placeholder="optional filter, e.g. ${plEsc(syms[2] || 'BTCUSDT')}"></label>
                <label class="switch"><input type="checkbox" id="bmAddonBuilt" ${bm.addon_built ? 'checked' : ''}> add-on added</label>
                <label class="switch"><input type="checkbox" id="bmEnabled" ${bm.enabled ? 'checked' : ''}> Enabled</label>
            </div>
            <div class="field-row">
                <button class="btn small" id="bmSave">Save</button>
                <button class="btn small" id="bmTest">Test connection</button>
                <span class="dim">${plEsc(((PLAT.data || {}).bookmap_note) || '')}</span>
            </div>
            <div id="bmResult"></div>
        </div></div>`;
    }

    /* ── NinjaTrader ────────────────────────────────────────────────────────────────────────
       Same shape as the other two cards, third physics: NinjaTrader has no market-data-out API
       either, so the suite ships a read-only bridge DLL the user copies in once — and the
       terminal doubles as a full ENGINE data source (its instruments stream like any venue). */
    function ntLink(id) {
        return ((PLAT.data && PLAT.data.ninjatrader_links) || []).find((l) => l.id === id) || null;
    }
    function ntPlans() { return (PLAT.data && PLAT.data.ninjatrader_plans) || []; }

    function ntHeader() {
        const nt = (PLAT.data && PLAT.data.ninjatrader) || {};
        const plans = ntPlans();
        const chosen = plans.find((p) => p.id === PLAT.ntPlan) || plans[0] || { name: 'Free' };
        return `<div class="card"><div class="card-head">
            <span class="card-title">NinjaTrader integration</span>
            <div class="spacer"></div>
            <span class="dim">${nt.integrated ? 'loaded' : 'not loaded'}</span>
            <label class="switch"><input type="checkbox" id="ntIntegrated" ${nt.integrated ? 'checked' : ''}> Load into my workflow</label>
        </div><div class="card-body">
            <p class="dim">Optional and powerful: NinjaTrader publishes no market-data-out API, so this
            suite ships a small <b>read-only</b> bridge DLL — copy it in once, flip one NinjaTrader
            option, restart — and the terminal\u2019s own instruments (NQ, ES, MNQ\u2026) stream into
            every panel as a full data source. No orders, no account access, nothing leaves this
            machine. ${plEsc((PLAT.data && PLAT.data.ninjatrader_free_note) || '')}</p>
            <div class="field-row">
                <label>Plan you run
                    <select id="ntPlan">${plans.map((p) => `<option value="${p.id}" ${p.id === PLAT.ntPlan ? 'selected' : ''}>${plEsc(p.name)}${p.price === '0' ? ' — free' : ` — $${plEsc(p.price)} ${plEsc(p.period)}`}</option>`).join('')}</select>
                </label>
                <button class="btn small" id="ntPlanSave">Apply</button>
                <span class="dim">now: ${plEsc(chosen.name)}</span>
            </div>
        </div></div>`;
    }

    function ntWorkflow() {
        const wf = (PLAT.data && PLAT.data.ninjatrader_workflow) || { steps: [], suite_changes: [] };
        return `<div class="card"><div class="card-head"><span class="card-title">NinjaTrader setup — ${plEsc(wf.plan_kind === 'free' ? 'free path first' : 'paid path')}</span></div>
        <div class="card-body">
            <ol class="pl-steps">${(wf.steps || []).map((step) => {
                const l = ntLink(step.link);
                return `<li><b>${plEsc(step.title)}</b><div class="dim">${plEsc(step.text)}
                    ${l ? `<button class="pl-link" data-url="${plEsc(l.url)}">${plEsc(l.label)} \u2197</button>` : ''}</div></li>`;
            }).join('')}</ol>
            <div class="pl-changes"><b>What this suite changes for that plan</b>
                <ul>${(wf.suite_changes || []).map((c) => `<li>${plEsc(c)}</li>`).join('')}</ul></div>
        </div></div>`;
    }

    function ntPlanCards() {
        const plans = ntPlans();
        return `<div class="card"><div class="card-head"><span class="card-title">NinjaTrader plans — the platform is free; a plan changes commissions</span>
            <div class="spacer"></div><span class="dim">read ${plEsc((PLAT.data && PLAT.data.ninjatrader_prices_as_of) || '')}</span></div>
        <div class="card-body">
            ${plans.map((p) => `<div class="pl-plan ${p.id === PLAT.ntPlan ? 'on' : ''}">
                <div class="pl-plan-head"><b>${plEsc(p.name)}</b>
                    <span class="pl-price">${p.price === '0' ? 'free' : `$${plEsc(p.price)} ${plEsc(p.period)}`}</span>
                    ${p.id === PLAT.ntPlan ? '<span class="pl-badge">in use</span>' : ''}</div>
                <ul>${(p.includes || []).map((i) => `<li>${plEsc(i)}</li>`).join('')}</ul></div>`).join('')}
            <div class="dim">${((PLAT.data && PLAT.data.ninjatrader_caveats) || []).map((c) => plEsc(c)).join(' ')}</div>
            <div class="field-row">
                ${(PLAT.data && PLAT.data.ninjatrader_links || []).filter((l) => ['pricing', 'datafeeds', 'orderflow', 'dashboard', 'register'].includes(l.id))
                    .map((l) => `<button class="pl-link" data-url="${plEsc(l.url)}">${plEsc(l.label)} \u2197</button>`).join('')}
            </div>
        </div></div>`;
    }

    function ntInstall() {
        const inst = (PLAT.data && PLAT.data.installs) || {};
        const n = inst.ninjatrader || { found: false };
        return `<div class="card"><div class="card-head"><span class="card-title">NinjaTrader on this machine</span>
            <div class="spacer"></div><span class="dim">${n.found ? `detected${n.version ? ' \u00b7 ' + plEsc(n.version) : ''}` : 'not detected'}</span></div>
        <div class="card-body"><p class="dim">${n.found
            ? `Found at ${plEsc(n.path || '')}${n.addons_present ? ` \u2014 its AddOns folder is present${n.bridge_installed ? ' and this suite\'s bridge DLL is in it.' : ', but the bridge DLL is not in it yet.'}` : ' \u2014 its AddOns folder has not been created yet.'}
               Its account, licence, workspace and config files are never read.`
            : 'Not installed here. The workflow above covers install and the free login; the suite works fully on its built-in free feeds meanwhile.'}</p></div></div>`;
    }

    function ntDllLine() {
        const b = (PLAT.data && PLAT.data.ninjatrader_bridge) || {};
        const dll = b.dll || {};
        const state = b.ok === true ? 'ok' : (b.ok === false ? 'warn' : '');
        const size = dll.size ? (Math.round(dll.size / 102.4) / 10) + ' KB' : '';
        return `<div class="field-row">
            <b>Bridge DLL:</b> <span class="${state}">${dll.exists ? 'shipped with this app' : 'missing from this install'}</span>
            ${size ? `<span class="dim">${size}</span>` : ''}
            <button class="btn small" id="ntDllOpen">Show the DLL folder</button>
        </div>
        <div class="dim" id="ntDllNote">${plEsc(b.note || '')}</div>
        <div class="dim" id="ntDllPath" style="word-break:break-all">${plEsc(dll.path || '')}</div>`;
    }

    function ntBridgeCard() {
        const nt = (PLAT.data && PLAT.data.ninjatrader) || {};
        const opt = ntLink('options');
        return `
    <div class="card"><div class="card-head"><span class="card-title">NinjaTrader bridge (loopback)</span>
        <div class="spacer"></div><span class="dim" id="ntBridgeState">${nt.enabled ? 'enabled' : 'disabled'}</span></div>
        <div class="card-body">
            <p class="dim">The bridge is the <b>server</b> inside NinjaTrader \u2014 it writes <i>listening on
            127.0.0.1:&lt;port&gt;</i> to the platform\u2019s Log tab and to <code>%LOCALAPPDATA%\\ModFlow\\ntbridge.log</code>
            when it loads. The bridge <b>ships as source</b>: copy <i>ModFlowBridge.cs</i>, <i>ModFlowJson.cs</i> and <i>ModFlowProbe.cs</i> into
            <i>Documents\\NinjaTrader 8\\bin\\Custom\\AddOns</i>, press <i>F5</i> in the platform’s own NinjaScript Editor and answer the trust prompt once, then press Test connection.
            ${opt ? `<button class="pl-link" data-url="${plEsc(opt.url)}">its settings page \u2197</button>` : ''}</p>
            ${ntDllLine()}
            <div class="field-row">
                <label>Host<input id="ntHost" value="${plEsc(nt.host || '127.0.0.1')}" size="14"></label>
                <label>Port<input id="ntPort" value="${plEsc(nt.port || 8790)}" size="7"></label>
                <label>Test instrument<input id="ntSymbol" value="${plEsc(nt.symbol || 'NQ')}" size="10"
                       placeholder="NQ / NQ1 / ES\u2026" title="Any name your terminal lists \u2014 NQ, NQ1, ES, MNQ 12-26\u2026"></label>
                <label class="switch"><input type="checkbox" id="ntEnabled" ${nt.enabled ? 'checked' : ''}> Enabled</label>
            </div>
            <div class="field-row">
                <button class="btn small" id="ntSave">Save</button>
                <button class="btn small" id="ntTest">Test connection</button>
                <span class="dim">${plEsc(((PLAT.data || {}).ninjatrader_note) || '')}</span>
            </div>
            <div id="ntResult"></div>
        </div></div>`;
    }

    function plRender() {
        const host = el('platformsBody');
        if (!host) return;
        if (!PLAT.data) { host.innerHTML = '<div class="dim">loading…</div>'; return; }
        if (!PLAT.data.catalogue) {
            host.innerHTML = '<div class="dim">integration state unavailable — the server did not answer</div>';
            return;
        }
        host.innerHTML = plHeader() + plWorkflow() + plPlans() + plInstall() + plDtcCard()
            + bmHeader() + bmWorkflow() + bmPlanCards() + bmInstall() + bmBridgeCard()
            + ntHeader() + ntWorkflow() + ntPlanCards() + ntInstall() + ntBridgeCard();
        const toggle = el('plIntegrated');
        if (toggle) toggle.addEventListener('change', () => plSavePlan({ integrated: toggle.checked }));
        const save = el('plPlanSave');
        if (save) save.addEventListener('click', () => plSavePlan({ plan: (el('plPlan') || {}).value }));
        const dSave = el('plDtcSave');
        if (dSave) dSave.addEventListener('click', plSaveDtc);
        const dTest = el('plDtcTest');
        if (dTest) dTest.addEventListener('click', plTestDtc);
        const dClear = el('plDtcClear');
        if (dClear) dClear.addEventListener('click', plClearPassword);
        const bToggle = el('bmIntegrated');
        if (bToggle) bToggle.addEventListener('change', () => bmSavePlan({ integrated: bToggle.checked }));
        const bPlan = el('bmPlanSave');
        if (bPlan) bPlan.addEventListener('click', () => bmSavePlan({ plan: (el('bmPlan') || {}).value }));
        const bSave = el('bmSave');
        if (bSave) bSave.addEventListener('click', bmSaveBridge);
        const bTest = el('bmTest');
        if (bTest) bTest.addEventListener('click', bmTestBridge);
        const bJar = el('bmJarOpen');
        if (bJar) bJar.addEventListener('click', bmRevealJar);
        const nToggle = el('ntIntegrated');
        if (nToggle) nToggle.addEventListener('change', () => ntSavePlan({ integrated: nToggle.checked }));
        const nPlan = el('ntPlanSave');
        if (nPlan) nPlan.addEventListener('click', () => ntSavePlan({ plan: (el('ntPlan') || {}).value }));
        const nSave = el('ntSave');
        if (nSave) nSave.addEventListener('click', ntSaveBridge);
        const nTest = el('ntTest');
        if (nTest) nTest.addEventListener('click', ntTestBridge);
        const nDll = el('ntDllOpen');
        if (nDll) nDll.addEventListener('click', ntRevealDll);
        host.querySelectorAll('.pl-link').forEach((b) => b.addEventListener('click', () => plOpen(b.dataset.url)));
    }

    function plDtcPayload() {
        return {
            host: (el('plDtcHost') || {}).value || '',
            port: Number((el('plDtcPort') || {}).value) || 11099,
            username: (el('plDtcUser') || {}).value || '',
            password: (el('plDtcPass') || {}).value || '',
            symbol: (el('plDtcSymbol') || {}).value || '',
            use_tls: !!(el('plDtcTls') || {}).checked,
            enabled: !!(el('plDtcEnabled') || {}).checked,
        };
    }
    function plShowDtcResult(res) {
        const host = el('plDtcResult');
        if (!host) return;
        const ok = res && res.ok;
        const detail = res && (res.error || res.note || res.message || (ok ? 'connected' : 'no detail'));
        host.innerHTML = `<div class="banner ${ok ? 'ok' : 'warn'}">${plEsc(String(detail))}</div>`;
    }
    async function plSavePlan(body) {
        try {
            const res = await api('/api/control/platforms/plan', { method: 'POST', body });
            if (res && res.ok && res.sierra) {
                PLAT.data = Object.assign({}, PLAT.data, { sierra: res.sierra, workflow: res.workflow, plans: res.plans, price_note: res.price_note });
                PLAT.plan = res.sierra.plan || PLAT.plan;
                PLAT.integrated = !!res.sierra.integrated;
                plRender();
                if (window.setStatusNote) setStatusNote(`Sierra integration: ${PLAT.integrated ? 'loaded' : 'off'} · plan ${PLAT.plan}`);
            } else {
                plShowDtcResult({ ok: false, error: (res && res.error) || 'could not apply the plan' });
            }
        } catch (err) { plShowDtcResult({ ok: false, error: String(err) }); }
    }
    async function plSaveDtc() {
        try {
            const res = await api('/api/control/platforms/bridge/dtc', { method: 'POST', body: plDtcPayload() });
            PLAT.data = Object.assign({}, PLAT.data, { sierra: (res && res.sierra) || PLAT.data.sierra });
            plRender();
            plShowDtcResult({ ok: !!(res && res.ok), note: 'connection saved' });
        } catch (err) { plShowDtcResult({ ok: false, error: String(err) }); }
    }
    async function plTestDtc() {
        plShowDtcResult({ ok: true, note: 'probing…' });
        try {
            plShowDtcResult(await api('/api/control/platforms/bridge/dtc/test', { method: 'POST', body: plDtcPayload() }));
        } catch (err) { plShowDtcResult({ ok: false, error: String(err) }); }
    }
    async function plClearPassword() {
        try {
            await api('/api/control/platforms/bridge/dtc', { method: 'POST', body: { clear_password: true } });
            await plLoad();
        } catch (err) { plShowDtcResult({ ok: false, error: String(err) }); }
    }
    async function plOpen(url) {
        try {
            const res = await api('/api/control/platforms/open', { method: 'POST', body: { url } });
            if (res && !res.ok) plShowDtcResult({ ok: false, error: res.error || 'link refused' });
        } catch (err) { plShowDtcResult({ ok: false, error: String(err) }); }
    }

    /* ── Bookmap actions ─────────────────────────────────────────────────────────────────── */
    function bmShowResult(res) {
        const host = el('bmResult');
        if (!host) return;
        const ok = res && res.ok;
        const detail = res && (res.error || res.note || res.detail || (ok ? 'connected' : 'no detail'));
        const counts = res && res.messages
            ? ` — hello ${res.messages.hello}, snapshots ${res.messages.snapshots}, trades ${res.messages.trades}, depth ${res.messages.depth}, heartbeats ${res.messages.heartbeats}`
            : '';
        const sample = res && res.sample && res.sample.kind
            ? ` · sample: ${plEsc(res.sample.kind)} ${plEsc(res.sample.symbol || '')}`
                + (res.sample.price != null ? ` @ ${plEsc(res.sample.price)}`
                   : (res.sample.bid != null ? ` bid ${plEsc(res.sample.bid)} / ask ${plEsc(res.sample.ask)}` : ''))
                + (res.sample.size != null && res.sample.price != null ? ` × ${plEsc(res.sample.size)}` : '')
            : '';
        host.innerHTML = `<div class="banner ${ok ? 'ok' : 'warn'}">${plEsc(String(detail))}${plEsc(counts)}${sample}</div>`
            + ((res && (res.rejects || []).length)
                ? `<div class="dim">${res.rejects.length} rejected frame(s): ${plEsc(String(res.rejects[0]))}</div>` : '');
    }
    async function bmSavePlan(body) {
        try {
            const res = await api('/api/control/platforms/plan', { method: 'POST', body: { ...body, platform: 'bookmap' } });
            if (res && res.ok && res.bookmap) {
                PLAT.data = Object.assign({}, PLAT.data, {
                    bookmap: res.bookmap,
                    bookmap_workflow: res.workflow,
                    bookmap_plans: res.plans,
                });
                PLAT.bmPlan = res.bookmap.plan || PLAT.bmPlan;
                PLAT.bmIntegrated = !!res.bookmap.integrated;
                plRender();
                if (window.setStatusNote) setStatusNote(`Bookmap integration: ${PLAT.bmIntegrated ? 'loaded' : 'off'} · tier ${PLAT.bmPlan}`);
            } else {
                bmShowResult({ ok: false, error: (res && res.error) || 'could not apply the tier' });
            }
        } catch (err) { bmShowResult({ ok: false, error: String(err) }); }
    }
    function bmPayload() {
        return {
            host: (el('bmHost') || {}).value || '127.0.0.1',
            port: Number((el('bmPort') || {}).value) || 8791,
            symbol: (el('bmSymbol') || {}).value || '',
            addon_built: !!(el('bmAddonBuilt') || {}).checked,
            enabled: !!(el('bmEnabled') || {}).checked,
        };
    }
    async function bmSaveBridge() {
        try {
            const res = await api('/api/control/platforms/bridge/bookmap', { method: 'POST', body: bmPayload() });
            PLAT.data = Object.assign({}, PLAT.data, { bookmap: (res && res.bookmap) || PLAT.data.bookmap });
            plRender();
            bmShowResult({ ok: !!(res && res.ok), note: 'bridge saved' });
        } catch (err) { bmShowResult({ ok: false, error: String(err) }); }
    }
    async function bmTestBridge() {
        bmShowResult({ ok: true, note: 'probing the add-on…' });
        try {
            bmShowResult(await api('/api/control/platforms/bridge/bookmap/test', { method: 'POST', body: bmPayload() }));
        } catch (err) { bmShowResult({ ok: false, error: String(err) }); }
    }
    async function bmRevealJar() {
        const note = el('bmJarNote');
        try {
            const res = await api('/api/control/platforms/bridge/bookmap/jar/open', { method: 'POST', body: {} });
            if (note) note.textContent = res && res.ok
                ? `opened ${res.folder} — ${res.note || ''}`
                : `could not open it: ${(res && res.error) || 'unknown error'}`;
        } catch (err) {
            if (note) note.textContent = `could not open it: ${String(err)}`;
        }
    }

    /* ── NinjaTrader actions ─────────────────────────────────────────────────────────────── */
    function ntShowResult(res) {
        const host = el('ntResult');
        if (!host) return;
        const ok = res && res.ok;
        const detail = res && (res.error || res.note || res.detail || (ok ? 'connected' : 'no detail'));
        const bridge = res && res.bridge && res.bridge.Addon
            ? ` \u2014 bridge ${plEsc(res.bridge.Addon)} ${plEsc(res.bridge.Version || '')}`
                + (res.bridge.NT ? ` on NinjaTrader ${plEsc(res.bridge.NT)}` : '')
                + (res.bridge.Connection ? ` \u00b7 connection ${plEsc(res.bridge.Connection)} (${plEsc(res.bridge.Status || '')})` : '')
            : '';
        const counts = res && res.messages
            ? ` \u2014 quotes ${res.messages.quotes}, trades ${res.messages.trades}, depth ${res.messages.depth}, heartbeats ${res.messages.heartbeats}`
            : '';
        const depth = res && res.depth ? `<div class="dim">${plEsc(String(res.depth))}</div>` : '';
        const sample = res && res.sample && res.sample.kind
            ? ` \u00b7 sample: ${plEsc(res.sample.kind)} ${plEsc(res.sample.instrument || '')}`
                + (res.sample.price != null ? ` @ ${plEsc(res.sample.price)}` : '')
            : '';
        host.innerHTML = `<div class="banner ${ok ? 'ok' : 'warn'}">${plEsc(String(detail))}${bridge}${plEsc(counts)}${sample}</div>${depth}`
            + ((res && (res.rejects || []).length)
                ? `<div class="dim">${res.rejects.length} rejected frame(s): ${plEsc(String(res.rejects[0]))}</div>` : '');
    }
    async function ntSavePlan(body) {
        try {
            const res = await api('/api/control/platforms/plan', { method: 'POST', body: { ...body, platform: 'ninjatrader' } });
            if (res && res.ok && res.ninjatrader) {
                PLAT.data = Object.assign({}, PLAT.data, {
                    ninjatrader: res.ninjatrader,
                    ninjatrader_workflow: res.workflow,
                    ninjatrader_plans: res.plans,
                });
                PLAT.ntPlan = res.ninjatrader.plan || PLAT.ntPlan;
                PLAT.ntIntegrated = !!res.ninjatrader.integrated;
                plRender();
                if (window.setStatusNote) setStatusNote(`NinjaTrader integration: ${PLAT.ntIntegrated ? 'loaded' : 'off'} \u00b7 plan ${PLAT.ntPlan}`);
            } else {
                ntShowResult({ ok: false, error: (res && res.error) || 'could not apply the plan' });
            }
        } catch (err) { ntShowResult({ ok: false, error: String(err) }); }
    }
    function ntPayload() {
        return {
            host: (el('ntHost') || {}).value || '127.0.0.1',
            port: Number((el('ntPort') || {}).value) || 8790,
            symbol: (el('ntSymbol') || {}).value || 'NQ',
            enabled: !!(el('ntEnabled') || {}).checked,
        };
    }
    async function ntSaveBridge() {
        try {
            const res = await api('/api/control/platforms/bridge/ninjatrader', { method: 'POST', body: ntPayload() });
            PLAT.data = Object.assign({}, PLAT.data, { ninjatrader: (res && res.ninjatrader) || PLAT.data.ninjatrader });
            plRender();
            ntShowResult({ ok: !!(res && res.ok), note: 'bridge saved' });
        } catch (err) { ntShowResult({ ok: false, error: String(err) }); }
    }
    async function ntTestBridge() {
        ntShowResult({ ok: true, note: 'probing the bridge\u2026' });
        try {
            ntShowResult(await api('/api/control/platforms/bridge/ninjatrader/test', { method: 'POST', body: ntPayload() }));
        } catch (err) { ntShowResult({ ok: false, error: String(err) }); }
    }
    async function ntRevealDll() {
        const note = el('ntDllNote');
        try {
            const res = await api('/api/control/platforms/bridge/ninjatrader/dll/open', { method: 'POST', body: {} });
            if (note) note.textContent = res && res.ok
                ? `opened ${res.folder} \u2014 ${res.note || ''}`
                : `could not open it: ${(res && res.error) || 'unknown error'}`;
        } catch (err) {
            if (note) note.textContent = `could not open it: ${String(err)}`;
        }
    }

    function plWatch() {
        const section = document.querySelector('.view[data-view="platforms"]');
        if (!section) return;
        if (section.classList.contains('active')) void plLoad();
        new MutationObserver(() => { if (section.classList.contains('active')) void plLoad(); })
            .observe(section, { attributes: true, attributeFilter: ['class'] });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', plWatch);
    else plWatch();

    if (typeof HELP_TOPICS !== 'undefined' && !HELP_TOPICS.platforms) {
        HELP_TOPICS.platforms = {
            title: 'Platform integrations — Sierra Chart, Bookmap and NinjaTrader',
            lead: 'All three are optional. Sierra Chart is read over its own DTC protocol server; Bookmap '
                + 'and NinjaTrader are read over small read-only bridge add-ons this suite ships '
                + '(neither publishes a data-out API). Each vendor\'s free path needs no payment — start '
                + 'there.',
            body: ['Sierra: install → create the account → free trial + delayed data → enable the DTC '
                + 'protocol server (JSON) → point this suite at it → load it and pick your plan.',
                'Bookmap: install → create the account → free tier (crypto, one instrument at a time) '
                + '→ build and add the bridge add-on (Settings → Configure API plugins → Add) → point '
                + 'this suite at the port it prints → load it and pick your tier.',
                'NinjaTrader: install → create the login → free Simulated Data Feed or Kinetick End-Of-Day '
                + '→ copy the bridge\'s .cs files into Documents\\NinjaTrader 8\\bin\\Custom\\AddOns, press F5 in its NinjaScript Editor and answer the trust prompt once, then point this suite at 127.0.0.1:8790 '
                + '→ pick your plan. Unlike the other two, NinjaTrader is also a full engine data source: '
                + 'add NQ / ES / MNQ from the terminal\'s own list and it streams into every panel.',
                'Limitations are on the cards, not implied: Bookmap\'s market data is a separate '
                + 'purchase on every tier, its free tier shows one instrument, and its API-plugins '
                + 'dialog can be licence-locked; NinjaTrader\'s real-time CME/EUREX data comes with a '
                + 'funded account and level-2 depth only when the data subscription carries it.',
                'No plugin of ours is installed into Sierra; nothing is stored from any platform '
                + 'beyond the connection blocks, and no licence or account file is ever read.'],
        };
    }

    window.OFAPPlatforms = { load: plLoad, render: plRender };
})();
