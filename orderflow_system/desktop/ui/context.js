/* ══════════════════════════════════════════════════════════════════
   Market context card — free, keyless data that sharpens the tape.

   Everything here comes from public endpoints (no account, no API key):
   the venue's own funding rate / open interest / long-short ratio, the
   alternative.me Fear & Greed index, and RSS headlines.

   Loaded by atlas-v2.js alongside guide.js. It owns one card appended to
   the Overview view, polls only while that view is visible, and shows
   "unavailable" per section instead of blanking the whole card.
   ══════════════════════════════════════════════════════════════════ */

const CONTEXT = { timer: null, busy: false, last: null, symbol: null };

const CTX_STYLE = `
.ctx-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.ctx-cell { background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06);
            border-radius: 8px; padding: 8px 10px; }
.ctx-cell .lbl { font-size: 11px; opacity: .65; display: block; }
.ctx-cell .val { font-size: 15px; font-weight: 600; }
.ctx-cell .sub { font-size: 11px; opacity: .55; }
.ctx-pos { color: #4ade80; } .ctx-neg { color: #f87171; } .ctx-flat { opacity: .75; }
.ctx-news { list-style: none; margin: 0; padding: 0; max-height: 210px; overflow-y: auto; }
.ctx-news li { padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,.05); font-size: 12.5px; }
.ctx-news a { color: inherit; text-decoration: none; }
.ctx-news a:hover { text-decoration: underline; }
.ctx-news .src { opacity: .5; font-size: 11px; margin-left: 6px; }
.v2-route-row { display: flex; align-items: center; gap: 10px; padding: 3px 0; }
.v2-route-name { flex: 0 0 210px; font-size: 12.5px; opacity: .85; }
.v2-route-chans { display: flex; gap: 12px; flex-wrap: wrap; }
`;

function ctxFmt(n, digits) {
    if (n === null || n === undefined || Number.isNaN(n)) return '--';
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return Number(n).toFixed(digits === undefined ? 2 : digits);
}

function ctxTime(ms) {
    if (!ms) return '';
    try { return new Date(ms).toLocaleTimeString(); } catch (e) { return ''; }
}

/* ── the card ─────────────────────────────────────────────────────── */

function ctxMount() {
    const view = document.querySelector('.view[data-view="overview"]');
    if (!view || document.getElementById('ctxCard')) return;
    const style = document.createElement('style');
    style.id = 'ctxStyles';
    style.textContent = CTX_STYLE;
    document.head.appendChild(style);

    const card = document.createElement('div');
    card.className = 'card';
    card.id = 'ctxCard';
    card.style.marginTop = '12px';
    card.innerHTML = `
        <div class="card-head">
            <span class="card-title">Market context</span>
            <div class="spacer"></div>
            <span class="dim" id="ctxStamp" title="When this data was last fetched. Funding refreshes every 60s, news every 5 min, Fear &amp; Greed daily."></span>
            <button class="btn small" id="ctxRefresh" title="Fetch funding, open interest, Fear &amp; Greed and headlines again now">Refresh</button>
        </div>
        <div class="card-body">
            <div class="ctx-grid" id="ctxGrid"><div class="dim">waiting for the engine…</div></div>
            <div class="grid split" style="margin-top:10px">
                <div>
                    <div class="dim" style="margin-bottom:4px" title="Headlines from public RSS feeds — swap the feed URL in Setup or Settings.">Headlines (public RSS)</div>
                    <ul class="ctx-news" id="ctxNews"><li class="dim">…</li></ul>
                </div>
                <div class="dim" id="ctxNote" style="font-size:12px"></div>
            </div>
        </div>`;
    view.appendChild(card);

    const btn = document.getElementById('ctxRefresh');
    if (btn) btn.onclick = () => ctxRefresh(true);
}

/* ── rendering ────────────────────────────────────────────────────── */

function ctxCell(label, value, sub, cls, tip) {
    return `<div class="ctx-cell"${tip ? ` title="${esc(tip)}"` : ''}>
        <span class="lbl">${esc(label)}</span>
        <span class="val ${cls || ''}">${value}</span>
        ${sub ? `<span class="sub">${esc(sub)}</span>` : ''}</div>`;
}

function ctxRender(data) {
    const grid = document.getElementById('ctxGrid');
    const news = document.getElementById('ctxNews');
    const stamp = document.getElementById('ctxStamp');
    const note = document.getElementById('ctxNote');
    if (!grid) return;
    CONTEXT.last = data;

    const cells = [];
    const pos = data.positioning || {};
    if (pos.ok) {
        const fr = Number(pos.funding_pct || 0);
        cells.push(ctxCell('Funding rate', `${fr >= 0 ? '+' : ''}${fr.toFixed(4)}%`,
            pos.next_funding_ms ? `next ${ctxTime(pos.next_funding_ms)}` : '',
            fr > 0 ? 'ctx-pos' : (fr < 0 ? 'ctx-neg' : 'ctx-flat'),
            'Perpetual funding: positive means longs pay shorts (crowded long). Next payment time shown.'));
        cells.push(ctxCell('Open interest', ctxFmt(pos.open_interest, 1),
            pos.open_interest_value ? ctxFmt(pos.open_interest_value) + ' notional' : '',
            '', 'Total open contracts on the venue. Falls when positions close, rises when they build.'));
        if (pos.long_short_ratio !== undefined && pos.long_short_ratio !== null) {
            const ls = Number(pos.long_short_ratio);
            cells.push(ctxCell('Long / short', ls.toFixed(2),
                `${(pos.buy_ratio * 100).toFixed(0)}% long`,
                ls > 1 ? 'ctx-pos' : 'ctx-neg',
                'Share of accounts positioned long vs short (venue public data). A crowd one way is fuel for the other.'));
        }
        if (pos.change_24h_pct !== undefined) {
            const ch = Number(pos.change_24h_pct);
            cells.push(ctxCell('24h change', `${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%`,
                pos.turnover_24h ? ctxFmt(pos.turnover_24h) + ' turnover' : '',
                ch >= 0 ? 'ctx-pos' : 'ctx-neg', 'Price change over 24 hours, with the venue 24h turnover.'));
        }
    } else {
        cells.push(ctxCell('Funding / OI', '<span class="ctx-flat">unavailable</span>',
            pos.error ? String(pos.error).slice(0, 40) : '', '',
            'The venue did not answer — check the connection; the rest of the app is unaffected.'));
    }

    const fg = data.fear_greed || {};
    if (fg.ok) {
        const v = Number(fg.value);
        cells.push(ctxCell('Fear & Greed', String(v), fg.label || '',
            v >= 55 ? 'ctx-pos' : (v <= 45 ? 'ctx-neg' : 'ctx-flat'),
            'alternative.me sentiment index, 0 (extreme fear) to 100 (extreme greed). Daily, free, no key.'));
    }

    grid.innerHTML = cells.join('') || '<div class="dim">nothing configured</div>';

    const items = data.news || [];
    if (news) {
        news.innerHTML = items.length
            ? items.map((n) => `<li><a href="${esc(n.link || '#')}" target="_blank" rel="noopener"
                    title="${esc((n.title || '').slice(0, 160))}">${esc(n.title || '')}</a>
                    <span class="src">${esc((n.source || '').replace('www.', ''))}</span></li>`).join('')
            : '<li class="dim">no headlines (feed unreachable or none configured)</li>';
    }
    if (stamp) stamp.textContent = data.ts_ms ? `updated ${ctxTime(data.ts_ms)}` : '';
    if (note) {
        note.innerHTML = `${esc((data.symbol || '').toUpperCase())} · sources: venue public API, alternative.me, RSS`
            + (data.stats ? `<br>requests ${data.stats.requests} · failures ${data.stats.failures}` : '');
    }
}

/* ── polling ──────────────────────────────────────────────────────── */

async function ctxRefresh(manual) {
    if (CONTEXT.busy) return;
    const view = document.querySelector('.view[data-view="overview"]');
    if (!view || !view.classList.contains('active')) return;
    const symbol = (S.symbol || document.getElementById('symbolSelect')?.value || 'BTCUSDT');
    CONTEXT.symbol = symbol;
    CONTEXT.busy = true;
    const btn = document.getElementById('ctxRefresh');
    if (btn) btn.disabled = true;
    try {
        const data = await api(`/api/atlas/context/${encodeURIComponent(symbol)}${manual ? '?refresh=1' : ''}`);
        ctxRender(data);
    } catch (e) {
        const grid = document.getElementById('ctxGrid');
        if (grid) grid.innerHTML = `<div class="dim">market context unavailable — ${esc(String(e))}</div>`;
    }
    CONTEXT.busy = false;
    if (btn) btn.disabled = false;
}

function ctxStart() {
    ctxMount();
    if (CONTEXT.timer) clearInterval(CONTEXT.timer);
    CONTEXT.timer = setInterval(() => { if (window.OFAPINTENT && OFAPINTENT.anyHeld()) return; ctxRefresh(false); }, 60000);
    ctxRefresh(false);
    setTimeout(ctxRefresh, 2500);
}

/* Boot: mount when the overview exists, and re-mount after view switches
   (the base UI re-renders panels; our card is ours to re-add). */
(function ctxBoot() {
    const tryMount = () => { ctxMount(); };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(ctxBoot, 1500));
        return;
    }
    setTimeout(tryMount, 1800);
    const _showView = window.showView;
    if (typeof _showView === 'function' && !_showView.__ofapWrapped_context) {
        const wrapped = (name, ...rest) => {
            const out = _showView(name, ...rest);
            if (name === 'overview') setTimeout(ctxRefresh, 400);
            return out;
        };
        wrapped.__ofapWrapped_context = true;
        window.showView = wrapped;
    }
    if (typeof window.boot === 'function') {
        const _boot = window.boot;
        window.boot = async (...args) => {
            const out = await _boot(...args);
            ctxStart();
            return out;
        };
    }
    // no boot() redefinition available (older cache) → still start, just later
    setTimeout(ctxStart, 5000);
})();

window.CONTEXT = CONTEXT;
window.ctxRefresh = ctxRefresh;
