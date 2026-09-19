/* ══════════════════════════════════════════════════════════════════════════════
   Studies — the manager for indicator module for this suite's contracts.

   What this file does:
     · asks the server which indicator modules exist (`/api/control/studies/library`
       lists `desktop/ui/indicators/*.js` plus any module saved through this panel),
       injects them, and lets StudyAPI validate each one;
     · shows the library grouped by tag, with a parameter form generated from each
       module's `params` specification and its restrictions;
     · applies the active studies to the Chart view's chart (line / columns / dots /
       custom plots, `areaChoice: "new"` on its own price scale, `shifts`, per-bar
       candlestick overrides, and signals → markers);
     · shows a Data Box of the active plots for the crosshair bar;
     · persists the active list, parameter values and pasted modules through
       `POST /api/control/studies` (the same config file everything else uses).

   Compatibility: a module written for the suite against its documented
   contract (`module.exports = {name, calculator, params: {p: predef.paramSpecs…}}`
   and `require('./tools/…')`) loads here through the shim below — `predef`, `meta`
   and the tutorial tool modules are mapped onto StudyAPI's helpers.
   ══════════════════════════════════════════════════════════════════════════════ */

const STUDIES = { library: [], active: [], signals: [], errors: [], loaded: false, seq: 0,
                  collStatus: '', collSel: '', collDraft: '' };

function stEsc(v) {
    return String(v === null || v === undefined ? '' : v)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ── loading: the server lists the modules, the browser runs them ─────────── */
function stInjectModule(source, label) {
    /* The runtime owns the CommonJS/predef shim (StudyAPI.loadModuleSource), so the same
       loader is exercised by the Node self-test. This wrapper only collects the errors. */
    const result = StudyAPI.loadModuleSource(source, { label });
    if (!result.ok) {
        noteError(...(result.errors || [`${label}: refused`]));
        return false;
    }
    return true;
}

/* A module file registers itself into the StudyAPI registry when the browser *executes*
   it. Re-appending the same src does not re-execute anything, so a reload of the library
   after a registry clear used to end with an empty registry and a view that said "0
   module(s) loaded" while the files were right there. Every (re)load therefore carries a
   fresh counter — and the old tag for that module is dropped so one module stays one tag. */
function stLoadScript(url) {
    return new Promise((resolve) => {
        stLoadScript.round = (stLoadScript.round || 0) + 1;
        document.querySelectorAll(`script[data-study="${url}"]`).forEach((t) => t.remove());
        const tag = document.createElement('script');
        tag.src = `${url}${url.includes('?') ? '&' : '?'}r=${stLoadScript.round}`;
        tag.dataset.study = url;                       // the canonical path, counter stripped
        tag.onload = () => resolve(true);
        tag.onerror = () => { noteError(`${url}: could not be loaded`); resolve(false); };
        document.body.appendChild(tag);
    });
}

async function studiesLoadLibrary(force) {
    if (STUDIES.loaded && !force) return;
    STUDIES.errors = [];
    /* The error list is a diagnostic surface, not a log file: cap it so a library that fails on
       every poll cannot grow it for the whole session (audit B-JS-10). */
    const STUDIES_ERROR_MAX = 50;
    const noteError = (...messages) => {
        STUDIES.errors.push(...messages);
        if (STUDIES.errors.length > STUDIES_ERROR_MAX) {
            STUDIES.errors.splice(0, STUDIES.errors.length - STUDIES_ERROR_MAX);
        }
    };
    StudyAPI.registry.clear();
    let payload = { modules: [], custom: [] };
    try {
        payload = await api('/api/control/studies/library');
    } catch (err) {
        noteError(`library listing failed: ${err}`);
    }
    for (const url of payload.modules || []) {
        await stLoadScript(url);
    }
    for (const custom of payload.custom || []) {
        if (custom && custom.source) stInjectModule(custom.source, `custom:${custom.name || 'module'}`);
    }
    const listed = (payload.modules || []).length + (payload.custom || []).length;
    STUDIES.library = StudyAPI.registry.list();
    STUDIES.loaded = true;
    if (listed && !STUDIES.library.length) {
        /* The one failure that looked like "the feature is missing" instead of an error:
           files listed, nothing registered. Say what it means. */
        noteError(`the server listed ${listed} module file(s) but none registered — if this window was opened before an update, close and relaunch the app`);
    }
}

/* ── paste status ────────────────────────────────────────────────────────────
   The line lives in state, not in the DOM: a successful validate re-renders the card
   (the library just gained a row), which wiped the message it had written a moment
   earlier — so success looked like silence and only failures spoke. */
function stPasteStatusHtml() {
    const st = STUDIES.pasteStatus;
    if (!st) return '';
    return `<span class="${st.ok ? 'wiz-ok' : 'wiz-bad'}">${stEsc(st.text)}</span>`;
}

/* ── persistence ─────────────────────────────────────────────────────────── */
function stActiveConfig() {
    return ((S.config || {}).studies || {});
}

function stActiveList() {
    const list = stActiveConfig().active;
    return Array.isArray(list) ? list : (STUDIES.active || []);
}

/* §117: the saved sets, straight from the config the server owns. */
function stCollections() {
    const c = stActiveConfig().collections;
    return (c && typeof c === 'object') ? c : {};
}

async function studiesSave(active) {
    STUDIES.active = active;
    try {
        const saved = await api('/api/control/studies', { method: 'POST', body: { active } });
        S.config = S.config || {};
        S.config.studies = { ...(S.config.studies || {}), ...(saved.studies || { active }) };
        S.config.studies.active = active;
    } catch (err) {
        noteError(`saving studies failed: ${err}`);
    }
    studiesApply();
    studiesRender();
}

/* ── applying to the chart ───────────────────────────────────────────────── */
function stBars() {
    return Array.isArray(S.lastBars) ? S.lastBars : [];
}

function studiesApply() {
    const chart = S.chart;
    if (!chart) return { ok: false, reason: 'chart not ready' };
    for (const handle of S.studySeries || []) {
        try { chart.removeSeries(handle); } catch (e) { /* already gone */ }
    }
    S.studySeries = [];
    S.studyResults = {};
    S.studySignals = [];
    const bars = stBars();
    const active = stActiveList();
    if (!bars.length || !active.length) {
        if (S.candleSeries && bars.length) stPaintCandlesticks(bars, {});
        studiesRenderDataBox(null);
        return { ok: true, applied: 0 };
    }

    const tickSize = stTickSize();
    const overrides = {};
    let applied = 0;

    for (const entry of active) {
        const def = StudyAPI.registry.get(entry.name);
        if (!def || entry.visible === false) continue;
        const run = StudyAPI.run(def, bars, entry.params || {}, { symbol: S.symbol, tickSize });
        S.studyResults[entry.name] = run;
        if (!run.ok && run.errors.length) {
            noteError(`${entry.name}: ${run.errors[0]}`);
        }
        for (const signal of run.alerts) S.studySignals.push({ ...signal, study: def.description || def.name });
        const marks = run.markers.slice(-200);
        if (marks.length && S.candleSeries) {
            const existing = (S.studyMarkers || []).concat(marks);
            S.studyMarkers = existing.slice(-300);
        }
        const shifts = def.shifts || {};
        const plotDefs = def.plotter ? (Array.isArray(def.plotter) ? def.plotter : [def.plotter]) : [];
        const scheme = (def.schemeStyles || {});
        const scaleId = def.areaChoice === 'new' ? `study:${def.name}` : 'right';

        for (const [plot, points] of Object.entries(run.plots)) {
            if (!points.length) continue;
            const style = scheme[plot] || scheme.value || def.schemeStyles || {};
            const plotterDef = plotDefs.find((p) => p.field === plot) || {};
            const kind = plotterDef.kind || style.plotter || 'line';
            const color = style.color || '#8fa8d8';
            const shift = shifts[plot] || 0;
            let data = points.map((p) => ({
                time: p.time === undefined ? undefined : (shift ? StudyAPI.shiftedTime(bars, p.index, shift) : p.time),
                value: p.value,
                ...(kind === 'columns' || kind === 'range' ? { color: (p.style && p.style.color) || color } : {}),
            })).filter((d) => d.time !== undefined && Number.isFinite(Number(d.value)));
            if (!data.length) continue;

            let series;
            try {
                if (kind === 'columns' || kind === 'range') {
                    series = chart.addHistogramSeries({
                        color, priceScaleId: scaleId, priceFormat: { type: 'price' },
                        lastValueVisible: false, priceLineVisible: false,
                    });
                } else {
                    series = chart.addLineSeries({
                        color, lineWidth: style.width || 2,
                        lineStyle: kind === 'dots' ? 1 : 0,          // dotted when asked for dots
                        priceScaleId: scaleId, lastValueVisible: false, priceLineVisible: false,
                    });
                }
            } catch (err) {
                noteError(`${entry.name}/${plot}: ${err && err.message ? err.message : err}`);
                continue;
            }
            try { series.setData(data); } catch (err) { noteError(`${entry.name}/${plot}: ${err}`); }
            S.studySeries.push(series);
            applied += 1;
        }

        if (def.areaChoice === 'new') {
            try {
                chart.priceScale(scaleId).applyOptions({ scaleMargins: { top: 0.72, bottom: 0.02 } });
            } catch (e) { /* scale appears with the first series */ }
        }
        for (const points of Object.values(run.plots)) {
            for (const point of points) {
                if (point.candlestick && Number.isFinite(point.index)) overrides[point.index] = point.candlestick;
            }
        }
    }

    stPaintCandlesticks(bars, overrides);
    if (S.candleSeries) S.candleSeries.setMarkers((S.studyMarkers || []).slice(-300));
    studiesRenderDataBox(S.crosshairIndex === undefined ? bars.length - 1 : S.crosshairIndex);
    return { ok: true, applied };
}

function stPaintCandlesticks(bars, overrides) {
    if (!S.candleSeries) return;
    const data = bars.map((c, i) => {
        const item = { time: c.time, open: c.open, high: c.high, low: c.low, close: c.close };
        const tint = overrides[i];
        if (tint && tint.color) {
            item.color = tint.color;
            item.borderColor = tint.color;
            item.wickColor = tint.color;
        }
        return item;
    });
    try { S.candleSeries.setData(data); } catch (e) { /* chart not ready */ }
}

function stTickSize() {
    const specs = ((S.config || {}).instruments || []);
    const spec = specs.find((i) => i.symbol === S.symbol);
    return Number(spec && spec.tick_size) || 0.01;
}

/* ── the Data Box (the suite's indicator contract calls it that; here it is the same idea) ─────── */
function studiesRenderDataBox(barIndex) {
    const host = document.getElementById('studiesBox');
    if (!host) return;
    const rows = [];
    for (const [name, run] of Object.entries(S.studyResults || {})) {
        const def = StudyAPI.registry.get(name);
        if (!def) continue;
        rows.push(...StudyAPI.dataBoxRows(def, run, barIndex));
    }
    if (!rows.length) {
        host.innerHTML = '<div class="dim">no studies on the chart yet — add one from the Studies view</div>';
        return;
    }
    host.innerHTML = `<table class="st-box"><tbody>${rows.map((r) => `
        <tr><td class="dim">${stEsc(r.study)}</td><td>${stEsc(r.plot)}</td>
            <td class="st-val">${r.value === undefined ? '–' : Number(r.value).toFixed(4)}</td></tr>`).join('')}
        </tbody></table>`;
}

function studiesWireCrosshair() {
    if (!S.chart || S.studyCrosshairWired) return;
    S.studyCrosshairWired = true;
    S.chart.subscribeCrosshairMove((param) => {
        if (!param || !param.time) { studiesRenderDataBox(stBars().length - 1); return; }
        const index = stBars().findIndex((b) => b.time === param.time);
        S.crosshairIndex = index >= 0 ? index : undefined;
        studiesRenderDataBox(S.crosshairIndex === undefined ? stBars().length - 1 : S.crosshairIndex);
    });
}

/* ── the manager UI ─────────────────────────────────────────────────────── */
function stParamField(studyName, key, spec, value) {
    const id = `stp_${studyName}_${key}`;
    const label = `<label class="dim">${stEsc(key)}</label>`;
    if (spec.type === 'boolean') {
        return `<label class="switch st-field"><input type="checkbox" id="${id}" data-study="${stEsc(studyName)}"
            data-param="${stEsc(key)}" ${value ? 'checked' : ''}> ${stEsc(key)}</label>`;
    }
    if (spec.type === 'enum') {
        const options = ((spec.restrictions || {}).options || []);
        return `<label class="st-field">${label}<select id="${id}" data-study="${stEsc(studyName)}" data-param="${stEsc(key)}">
            ${options.map((o) => `<option value="${stEsc(o)}" ${o === value ? 'selected' : ''}>${stEsc(o)}</option>`).join('')}
        </select></label>`;
    }
    if (spec.type === 'number') {
        const r = spec.restrictions || {};
        return `<label class="st-field">${label}<input type="number" id="${id}" data-study="${stEsc(studyName)}"
            data-param="${stEsc(key)}" value="${stEsc(value)}" step="${stEsc(r.step !== undefined ? r.step : 1)}"
            ${r.min !== undefined ? `min="${stEsc(r.min)}"` : ''} ${r.max !== undefined ? `max="${stEsc(r.max)}"` : ''}></label>`;
    }
    return `<label class="st-field">${label}<input type="text" id="${id}" data-study="${stEsc(studyName)}"
        data-param="${stEsc(key)}" value="${stEsc(value)}"></label>`;
}

function studiesRender() {
    const host = document.getElementById('studiesBody');
    if (!host) return;
    const byTag = {};
    for (const study of STUDIES.library || []) {
        for (const tag of study.tags || ['Uncategorised']) (byTag[tag] = byTag[tag] || []).push(study);
    }
    const active = stActiveList();
    const activeNames = new Set(active.map((a) => a.name));
    const library = Object.entries(byTag).sort(([a], [b]) => a.localeCompare(b)).map(([tag, studies]) => `
        <div class="st-tag">${stEsc(tag)}</div>
        ${studies.map((study) => {
            const on = activeNames.has(study.name);
            return `<div class="st-row">
                <div class="grow"><b>${stEsc(study.description)}</b>
                    <div class="dim">${stEsc(study.name)} · ${Object.keys(study.params || {}).length} param(s) ·
                        ${study.areaChoice === 'new' ? 'own area' : 'overlay'} · ${stEsc(study.inputType)} ·
                        ${stEsc(study.pack || 'built-in')} v${stEsc(study.version || '1.0.0')}</div>
                    ${(study.warnings || []).length ? `<div class="dim st-warn">${stEsc((study.warnings || []).join('; '))}</div>` : ''}
                </div>
                <button class="btn small st-toggle" data-name="${stEsc(study.name)}">${on ? 'Remove' : 'Add'}</button>
            </div>`;
        }).join('')}`).join('');

    const activeCards = active.map((entry) => {
        const study = (STUDIES.library || []).find((s) => s.name === entry.name);
        if (!study) return `<div class="st-row"><div class="grow"><b>${stEsc(entry.name)}</b>
            <div class="dim st-warn">not in the library any more — remove it or restore the module</div></div>
            <button class="btn small st-toggle" data-name="${stEsc(entry.name)}">Remove</button></div>`;
        const params = entry.params || StudyAPI.defaultsFor(StudyAPI.registry.get(entry.name));
        const run = (S.studyResults || {})[entry.name];
        return `<div class="st-card">
            <div class="st-row"><div class="grow"><b>${stEsc(study.description)}</b>
                <div class="dim">${stEsc(study.name)}${run ? ` · ${run.stats.bars} bars · ${run.markers.length} signal(s)` : ''}</div>
                ${run && !run.ok ? `<div class="dim st-warn">${stEsc(run.errors.join('; '))}</div>` : ''}</div>
                <button class="btn small st-toggle" data-name="${stEsc(entry.name)}">Remove</button></div>
            <div class="st-params">${Object.entries(study.params || {})
                .map(([key, spec]) => stParamField(study.name, key, spec, params[key])).join('')}</div>
        </div>`;
    }).join('');

    const signals = (S.studySignals || []).slice(-12).reverse();
    const colls = stCollections();
    const collNames = Object.keys(colls).sort((a, b) => a.localeCompare(b));
    const collOptions = collNames.map((name) =>
        `<option value="${stEsc(name)}"${name === STUDIES.collSel ? ' selected' : ''}>`
        + `${stEsc(name)} · ${((colls[name] || {}).active || []).length} studies</option>`).join('')
        || '<option value="">nothing saved yet</option>';
    const errors = (STUDIES.errors || []).slice(-8);
    host.innerHTML = `
        <div class="card"><div class="card-head"><span class="card-title">On the chart (${active.length})</span>
            <div class="spacer"></div><span class="dim">${(STUDIES.library || []).length} module(s) loaded</span></div>
            <div class="card-body">${activeCards || '<div class="dim">nothing applied yet</div>'}
            ${errors.length ? `<div class="st-errors">${errors.map((e) => `<div class="dim st-warn">${stEsc(e)}</div>`).join('')}</div>` : ''}
            </div></div>
        <div class="card"><div class="card-head"><span class="card-title">Saved setups</span>
            <div class="spacer"></div><span class="dim" id="stCollStatus">${stEsc(STUDIES.collStatus || 'switch a whole indicator set in one move — saved in your config file')}</span></div>
            <div class="card-body">
                <div class="st-row"><select id="stCollSelect" class="grow" title="A named set of studies — Apply swaps the whole list below in one move">${collOptions}</select>
                    <button class="btn small" id="stCollApply">Apply</button>
                    <button class="btn small" id="stCollDelete">Delete</button></div>
                <div class="st-row"><input id="stCollName" maxlength="32" placeholder="name this setup — e.g. Scalp reads" value="${stEsc(STUDIES.collDraft || '')}">
                    <button class="btn small" id="stCollSave">Save current as…</button></div>
            </div></div>
        <div class="card"><div class="card-head"><span class="card-title">Library</span>
            <div class="spacer"></div><button class="btn small" id="stReload">Reload modules</button></div>
            <div class="card-body">${library || '<div class="dim">no modules found in desktop/ui/indicators</div>'}</div></div>
        <div class="card"><div class="card-head"><span class="card-title">Signals (${(S.studySignals || []).length})</span>
            <div class="spacer"></div><span class="dim">markers on the chart, newest first</span></div>
            <div class="card-body">${signals.length ? `<table class="st-box"><tbody>${signals.map((s) => `
                <tr><td class="dim">${stEsc(s.study)}</td><td>${stEsc(s.side)}</td><td class="st-val">${stEsc(s.text || '')}</td></tr>`).join('')}
                </tbody></table>` : '<div class="dim">no signals in the loaded range</div>'}</div></div>
        <div class="card"><div class="card-head"><span class="card-title">Paste a module</span>
            <div class="spacer"></div><span class="dim">the suite's indicator contract; validated before it runs</span></div>
            <div class="card-body">
                <textarea id="stSource" rows="7" spellcheck="false"
                    placeholder="module.exports = { name: 'myStudy', calculator: class { map(d) { return d.close(); } } };"></textarea>
                <div class="st-row"><button class="btn small" id="stTest">Validate</button>
                    <button class="btn small" id="stSave">Save to config</button>
                    <span id="stSourceResult">${stPasteStatusHtml()}</span></div>
            </div></div>`;
    studiesWire();
}

function stReadParams(root) {
    const out = {};
    root.querySelectorAll('[data-study][data-param]').forEach((el) => {
        const study = el.dataset.study;
        out[study] = out[study] || {};
        out[study][el.dataset.param] = el.type === 'checkbox' ? el.checked : el.value;
    });
    return out;
}

function studiesWire() {
    document.querySelectorAll('.st-toggle').forEach((btn) => {
        btn.onclick = async () => {
            const name = btn.dataset.name;
            const active = stActiveList().filter((a) => a.name !== name);
            if (!stActiveList().some((a) => a.name === name)) {
                const def = StudyAPI.registry.get(name);
                active.push({ name, params: StudyAPI.defaultsFor(def), visible: true });
            }
            await studiesSave(active);
        };
    });
    document.querySelectorAll('[data-study][data-param]').forEach((el) => {
        el.onchange = async () => {
            const entered = stReadParams(document.getElementById('studiesBody'));
            const active = stActiveList().map((entry) => (
                entered[entry.name] ? { ...entry, params: entered[entry.name] } : entry));
            await studiesSave(active);
        };
    });
    const collApply = document.getElementById('stCollApply');
    if (collApply) collApply.onclick = async () => {
        const sel = document.getElementById('stCollSelect');
        const name = sel && sel.value;
        if (!name) return;
        try {
            const saved = await api('/api/control/studies', { method: 'POST', body: { collection: { action: 'apply', name } } });
            STUDIES.collStatus = saved.ok ? ('applied “' + name + '”') : (saved.error || 'could not apply');
            if (saved.ok) {
                S.config = S.config || {};
                S.config.studies = { ...(S.config.studies || {}), ...(saved.studies || {}) };
                STUDIES.active = (saved.studies || {}).active || [];
                studiesApply();
            }
        } catch (err) { STUDIES.collStatus = String(err); }
        studiesRender();
    };
    const collSave = document.getElementById('stCollSave');
    if (collSave) collSave.onclick = async () => {
        const box = document.getElementById('stCollName');
        const name = ((box && box.value) || STUDIES.collDraft || '').trim();
        if (!name) { STUDIES.collStatus = 'give the setup a name first'; studiesRender(); return; }
        try {
            const saved = await api('/api/control/studies', { method: 'POST',
                body: { collection: { action: 'save', name, active: stActiveList() } } });
            STUDIES.collStatus = saved.ok ? ('saved “' + name + '”') : (saved.error || 'could not save');
            if (saved.ok) {
                STUDIES.collSel = name;
                STUDIES.collDraft = '';
                S.config = S.config || {};
                S.config.studies = { ...(S.config.studies || {}), ...(saved.studies || {}) };
            }
        } catch (err) { STUDIES.collStatus = String(err); }
        studiesRender();
    };
    const collDelete = document.getElementById('stCollDelete');
    if (collDelete) collDelete.onclick = async () => {
        const sel = document.getElementById('stCollSelect');
        const name = sel && sel.value;
        if (!name) return;
        try {
            const saved = await api('/api/control/studies', { method: 'POST', body: { collection: { action: 'delete', name } } });
            STUDIES.collStatus = saved.ok ? ('deleted “' + name + '”') : (saved.error || 'could not delete');
            if (saved.ok) {
                if (STUDIES.collSel === name) STUDIES.collSel = '';
                S.config = S.config || {};
                S.config.studies = { ...(S.config.studies || {}), ...(saved.studies || {}) };
            }
        } catch (err) { STUDIES.collStatus = String(err); }
        studiesRender();
    };
    const collSel = document.getElementById('stCollSelect');
    if (collSel) collSel.onchange = () => { STUDIES.collSel = collSel.value; };
    const collNameBox = document.getElementById('stCollName');
    if (collNameBox) collNameBox.oninput = () => { STUDIES.collDraft = collNameBox.value; };
    const reload = document.getElementById('stReload');
    if (reload) reload.onclick = async () => { await studiesLoadLibrary(true); studiesRender(); };
    const test = document.getElementById('stTest');
    if (test) test.onclick = () => {
        const out = document.getElementById('stSourceResult');
        const source = (document.getElementById('stSource') || {}).value || '';
        const before = (STUDIES.errors || []).length;
        const ok = stInjectModule(source, 'pasted');
        const errs = (STUDIES.errors || []).slice(before);
        STUDIES.pasteStatus = ok
            ? { ok: true, text: 'valid — the module registered' }
            : { ok: false, text: errs.join('; ') || 'invalid module' };
        if (ok) { STUDIES.library = StudyAPI.registry.list(); studiesRender(); }   // re-render restores the status from state
        else if (out) out.innerHTML = stPasteStatusHtml();
    };
    const save = document.getElementById('stSave');
    if (save) save.onclick = async () => {
        const source = (document.getElementById('stSource') || {}).value || '';
        const out = document.getElementById('stSourceResult');
        try {
            const saved = await api('/api/control/studies', { method: 'POST', body: { custom_source: source } });
            STUDIES.pasteStatus = saved.ok
                ? { ok: true, text: 'saved — it loads with the app from now on' }
                : { ok: false, text: saved.error || 'refused' };
        } catch (err) { STUDIES.pasteStatus = { ok: false, text: String(err) }; }
        if (out) out.innerHTML = stPasteStatusHtml();
    };
}

/* ── registration: this module owns its help topic and guide entry ───────── */
function stRegisterHelp() {
    if (typeof HELP_TOPICS !== 'undefined' && !HELP_TOPICS.studies) {
        HELP_TOPICS.studies = {
            title: 'Studies (custom indicator modules)',
            lead: 'Indicator modules follow the suite\u2019s custom-indicator contract: a small '
                + 'module exports a definition (name, calculator, params, plots, plotter, schemeStyles) '
                + 'and a Calculator class with init() / map() / filter(). Modules written for that '
                + 'platform run here through a compatibility shim.',
            needs: ['nothing to install — the modules are plain files in desktop/ui/indicators'],
            steps: [
                { t: 'Add one', d: 'The Studies view lists every module by tag. "Add" puts it on the chart; '
                    + 'parameters appear as a form generated from the module\u2019s own specification.' },
                { t: 'See the values', d: 'The Data box under the chart shows each active plot at the crosshair '
                    + 'bar. Signals from a study become chart markers and are listed in the Studies view.' },
                { t: 'Write one', d: 'Drop a .js file into desktop/ui/indicators and press "Reload modules" — '
                    + 'or paste a module into the box in the Studies view. It is validated before it runs, and '
                    + 'a bad module is reported with the reason instead of breaking the chart.' },
                { t: 'The contract', d: 'map(d, i, history, output) receives one bar: d.open()/high()/low()/close()/'
                    + 'volume() plus this chart\u2019s tape fields d.buy()/sell()/delta() and d.prior(). Return a '
                    + 'number for a single line, or an object keyed by your plot names; return {signal: {...}} to '
                    + 'mark and alert a bar.' },
            ],
            note: 'Not supported (and named as such rather than half-built): Windows DLL imports (`dlls`), the '
                + 'interactive drawing-tool framework, and the full graphics display-object tree.',
        };
    }
    if (typeof GUIDE_SECTIONS !== 'undefined' && !GUIDE_SECTIONS.some((s) => s && s.id === 'studies')) {
        /* GUIDE_SECTIONS entries are {h, body}: the Guide renders `s.h` as the card title and the
           palette indexes it as the search title. This entry shipped as {title, lead, body}, so its
           card read "undefined" and EVERY non-empty palette query threw in searchScore (the index
           item had no title to score) — found live in the P1-9 pass (§44). Keep the shape. */
        GUIDE_SECTIONS.push({
            id: 'studies',
            h: 'Writing your own studies',
            body: '<p>The chart accepts indicator modules written against a documented contract, so '
                + 'the indicator library is extensible without touching the app.</p>'
                + '<p>Full contract, worked examples and the compatibility notes are in '
                + 'docs/TRADOVATE_STUDY_BRIDGE.md; the starter pack lives in desktop/ui/indicators.</p>',
        });
        /* The guide view is built once, before this section is pushed, so refresh it the same way
           the how-to section in guide.js does — without this the card never appears at all (§44). */
        const gbody = document.getElementById('guideBody');
        if (gbody) {
            gbody.innerHTML = GUIDE_SECTIONS.map((s) => `
                <div class="card" style="margin-bottom:12px">
                    <div class="card-head"><span class="card-title">${s.h}</span></div>
                    <div class="card-body guide-copy">${s.body}</div>
                </div>`).join('');
            if (typeof applyTips === 'function') applyTips(gbody);
        }
    }
}

async function studiesInit() {
    const host = document.getElementById('studiesBody');
    if (host && !studiesInit.done) host.innerHTML = '<div class="dim">loading indicator modules…</div>';
    try {
        await studiesLoadLibrary(studiesInit.done);
        studiesInit.done = true;
        studiesWireCrosshair();
        if (S.chart) studiesApply();
        studiesRender();
    } catch (err) {
        if (host) host.innerHTML = `<span class="wiz-bad">${stEsc(String(err))}</span>`;
    }
}

stRegisterHelp();

/* Unlike a panel that only matters when its view is open, the study library must load on
   every boot: a persisted study draws on the Chart view, which is usually the first view
   anyone opens. `studiesInit` is idempotent, and it applies to the chart as soon as both
   the library and the bars exist. */
function stBoot() {
    studiesInit();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', stBoot);
else setTimeout(stBoot, 0);
