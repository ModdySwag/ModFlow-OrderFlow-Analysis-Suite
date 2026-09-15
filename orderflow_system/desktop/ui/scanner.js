/* ══════════════════════════════════════════════════════════════════
   Scanner view — one ranked table across every streaming instrument.

   the reference platform's Market Analyzer watches a list and sorts by a column; this is
   the same idea over the order-flow columns this program already computes, so
   "which of my instruments is doing something right now?" is one glance.
   ══════════════════════════════════════════════════════════════════ */

const SCAN = { sort: 'score', view: null, lastKey: '', rows: [], timer: null };

const SCAN_COLUMNS = [
    ['symbol', 'Instrument', 'The instrument. Click a row to switch the whole app to it.'],
    ['last', 'Last', 'Last traded price.'],
    ['chg_pct', 'Δ%', 'Change over the scanner window, from the tape itself (not from candles).'],
    ['volume', 'Volume', 'Traded volume in the window.'],
    ['delta', 'Delta', 'Buy volume minus sell volume in the window.'],
    ['delta_pct', 'Δ% of vol', 'Delta as a percentage of volume — who is winning the tape, size-adjusted.'],
    ['prints_per_s', 'Prints/s', 'Tape speed: prints per second.'],
    ['big_trades', 'Big', 'Adaptive big-print count in the window.'],
    ['sweeps', 'Sweeps', 'Multi-level sweep count.'],
    ['stop_runs', 'Stop runs', 'Stop-run detections.'],
    ['liquidations', 'Liqs', 'Liquidation events seen.'],
    ['imbalances', 'Imb', 'Levels currently showing a stacked imbalance.'],
    ['pressure_buy', 'Book bid %', 'Weighted bid liquidity as a percentage of its own recent normal.'],
    ['pressure_sell', 'Book ask %', 'Weighted ask liquidity as a percentage of its own recent normal.'],
    ['absorption_score', 'Absorb', 'Absorption score: aggression that is failing to move price.'],
    ['depth_executions', 'Eaten', 'Prints that took a large share of the size resting at their price.'],
    ['depth_refills', 'Refilled', 'Levels that came back after being eaten (inferred hidden size).'],
    ['ticks_from_vwap', 'VWAP t', 'Distance from the VWAP in ticks; negative means below it.'],
    ['score', 'Score', 'The stated composite: 0.28·|Δ%| + 0.22·|book edge| + 0.18·absorption + 0.17·depth events + 0.15·tape speed, each capped.'],
];

function scanStyles() {
    if (document.getElementById('scanStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'scanStyleSheet';
    st.textContent = `
        .scan-wrap { overflow-x: auto; }
        table.scan { width: 100%; border-collapse: collapse; font-size: 12px; }
        table.scan th { text-align: right; padding: 6px 8px; color: var(--dim); cursor: pointer;
                        border-bottom: 1px solid var(--line); white-space: nowrap; font-weight: 600; }
        table.scan th:first-child, table.scan td:first-child { text-align: left; }
        table.scan th:hover { color: var(--fg); }
        table.scan th.sorted { color: var(--fg); text-decoration: underline; }
        table.scan td { text-align: right; padding: 5px 8px; border-bottom: 1px solid var(--line);
                        white-space: nowrap; }
        table.scan tr:hover td { background: rgba(255,255,255,0.03); }
        table.scan td.sym { cursor: pointer; font-weight: 600; }
        .scan-pos { color: var(--up, #35d07f); }
        .scan-neg { color: var(--down, #ff5d6c); }
        .scan-bar { display: inline-block; height: 6px; border-radius: 3px; vertical-align: middle;
                    background: rgba(240,196,84,0.75); min-width: 2px; }
        .scan-note { color: var(--dim); font-size: 11px; margin-top: 6px; }
    `;
    document.head.appendChild(st);
}

function scanEnsureView() {
    if (document.getElementById('scanView')) return;
    scanStyles();
    const rail = document.querySelector('.rail');
    if (rail && !document.querySelector('.nav-item[data-view="scanner"]')) {
        const btn = document.createElement('button');
        btn.className = 'nav-item';
        btn.dataset.view = 'scanner';
        btn.innerHTML = '<span class="nav-icon">\u2263</span> Scanner';
        btn.title = 'One ranked row per streaming instrument — the Market Analyzer view.';
        btn.onclick = () => window.showView && window.showView('scanner');
        const before = rail.querySelector('.nav-item[data-view="trackers"]')
            || rail.querySelector('.nav-item[data-view="logs"]');
        rail.insertBefore(btn, before || null);
    }
    const main = document.querySelector('main.views');
    if (!main) return;
    const section = document.createElement('section');
    section.className = 'view';
    section.dataset.view = 'scanner';
    section.id = 'scanView';
    const head = SCAN_COLUMNS.map(([key, label, tip]) =>
        `<th data-sort="${key}" title="${tip}">${label}</th>`).join('');
    section.innerHTML = `
        <div class="view-head">
            <div class="view-title">Scanner</div>
            <div class="view-sub" id="scanSub">one ranked row per instrument — click a column to sort, a row to switch</div>
            <div class="grow"></div>
            <button class="btn small" id="scanRefresh" title="Refresh the table now">Refresh</button>
        </div>
        <div class="card"><div class="card-body">
            <div class="scan-wrap"><table class="scan">
                <thead><tr>${head}</tr></thead>
                <tbody id="scanRows"><tr><td colspan="19" class="dim">waiting for the engine…</td></tr></tbody>
            </table></div>
            <div class="scan-note" id="scanNote"></div>
        </div></div>`;
    main.appendChild(section);
    section.querySelectorAll('th[data-sort]').forEach((th) => {
        th.onclick = () => { SCAN.sort = th.dataset.sort; SCAN.lastKey = ''; scanRefresh(); };
    });
    section.querySelector('#scanRefresh').onclick = () => { SCAN.lastKey = ''; scanRefresh(); };
}

function scanNum(v, digits = 2) {
    if (v === null || v === undefined || v === '') return '–';
    const n = Number(v);
    if (!isFinite(n)) return '–';
    if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(2) + 'K';
    return n.toFixed(digits);
}

function scanRender(table) {
    const body = document.getElementById('scanRows');
    if (!body) return;
    const rows = table.rows || [];
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="19" class="dim">the engine is not streaming anything yet</td></tr>';
    } else {
        const maxScore = Math.max(1, ...rows.map((r) => r.score || 0));
        body.innerHTML = rows.map((r) => {
            const pos = (v) => (v || 0) > 0 ? 'scan-pos' : ((v || 0) < 0 ? 'scan-neg' : '');
            const width = Math.round(46 * ((r.score || 0) / maxScore));
            return `<tr>
                <td class="sym" data-symbol="${r.symbol}" title="Switch the app to ${r.symbol}">${r.symbol}</td>
                <td>${scanNum(r.last, 4)}</td>
                <td class="${pos(r.chg_pct)}">${r.chg_pct === null ? '–' : (r.chg_pct > 0 ? '+' : '') + scanNum(r.chg_pct)}</td>
                <td>${scanNum(r.volume, 2)}</td>
                <td class="${pos(r.delta)}">${scanNum(r.delta, 2)}</td>
                <td class="${pos(r.delta_pct)}">${r.delta_pct === null ? '–' : scanNum(r.delta_pct, 1)}</td>
                <td>${scanNum(r.prints_per_s, 1)}</td>
                <td>${r.big_trades || 0}</td>
                <td>${r.sweeps || 0}</td>
                <td>${r.stop_runs || 0}</td>
                <td>${r.liquidations || 0}</td>
                <td>${r.imbalances || 0}</td>
                <td>${scanNum(r.pressure_buy, 0)}</td>
                <td>${scanNum(r.pressure_sell, 0)}</td>
                <td>${scanNum(r.absorption_score, 0)}</td>
                <td>${r.depth_executions || 0}</td>
                <td>${r.depth_refills || 0}</td>
                <td>${r.ticks_from_vwap === null || r.ticks_from_vwap === undefined ? '–' : scanNum(r.ticks_from_vwap, 1)}</td>
                <td title="score ${r.score}"><span class="scan-bar" style="width:${width}px"></span> ${scanNum(r.score, 0)}</td>
            </tr>`;
        }).join('');
        body.querySelectorAll('td.sym').forEach((td) => {
            td.onclick = () => {
                const sym = td.dataset.symbol;
                const sel = document.getElementById('symbolSelect');
                if (sel && sym) {
                    sel.value = sym;
                    sel.dispatchEvent(new Event('change'));
                    window.showView && window.showView('overview');
                }
            };
        });
    }
    document.querySelectorAll('#scanView th[data-sort]').forEach((th) => {
        th.classList.toggle('sorted', th.dataset.sort === table.sort);
    });
    const sub = document.getElementById('scanSub');
    if (sub) sub.textContent = `${table.count} instrument(s) · sorted by ${table.sort} · window ${table.window_s}s · ${new Date(table.as_of).toLocaleTimeString()}`;
    const note = document.getElementById('scanNote');
    if (note) note.textContent = table.score_note || '';
}

async function scanRefresh() {
    scanEnsureView();
    if (!document.getElementById('scanRows')) return;
    const inView = (document.querySelector('.view[data-view="scanner"]') || {}).classList?.contains('active');
    if (!inView && SCAN.lastKey) return;                 // only poll the visible view
    try {
        const table = await api(`/api/atlas/scanner?sort=${encodeURIComponent(SCAN.sort)}&limit=60`);
        const key = `${table.as_of && Math.round(table.as_of / 1000)}|${table.sort}|${table.count}|${(table.rows || []).length}`;
        if (key === SCAN.lastKey) return;
        SCAN.lastKey = key;
        scanRender(table);
    } catch (e) {
        const sub = document.getElementById('scanSub');
        if (sub) sub.textContent = `scanner unavailable: ${e}`;
    }
}

(function scanLoop() {
    scanEnsureView();
    SCAN.timer = setInterval(() => {
        if (window.OFAPINTENT && OFAPINTENT.anyHeld()) return;   // never repaint over the user's hands
        const view = document.querySelector('.view[data-view="scanner"]');
        if (view && (view.classList.contains('active') || view.style.display === 'flex')) scanRefresh();
    }, 4000);
    setTimeout(scanRefresh, 5000);
})();
