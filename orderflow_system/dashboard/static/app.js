/**
 * Orderflow Trading Terminal — Simplified
 * Full-screen chart with info overlay + Scanner sidebar
 */

// ════════════════════════════════════════════
// State
// ════════════════════════════════════════════

const state = {
    ws: null,
    activeSymbol: null,
    instruments: [],
    priceChart: null,
    candleSeries: null,
    vpLines: [],
    tradeLines: [],
    signals: [],
    markers: [],
    reconnectTimer: null,
    reconnectDelay: 1000,
    timeframe: 60,
    range: 86400,
    chartType: 'candles',
    _candleBucket: null,
    _deltaCumulative: null,
    _biasData: {},
    _vpData: {},
    _strategyData: {},
    _microData: {},
};

// Asset class grouping
const ASSET_GROUPS = {
    'Forex':    ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','USDCHF','NZDUSD','EURGBP','EURJPY','GBPJPY'],
    'Metals':   ['XAUUSDT','XAGUSD'],
    'Indices':  ['NAS100USDT','SP500','DJ30','DAX40','UK100'],
    'Crypto':   ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT'],
    'Stocks':   ['AAPL','TSLA','AMZN','MSFT','NVDA','META','GOOGL'],
};

// ════════════════════════════════════════════
// Initialization
// ════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    await fetchInstruments();
    initControls();
    connectWebSocket();

    /* D-02: one ping timer for the page (it used to be created inside connectWebSocket, so a
       reconnect leaked one per close), and a hidden tab stops polling. */
    startPing();
    setInterval(() => { if (document.hidden) return; refreshFastData(); }, 1000);
    setInterval(() => { if (document.hidden) return; refreshSlowData(); }, 5000);
    refreshScannerLoop();
    setInterval(() => { if (document.hidden) return; refreshScannerLoop(); }, 5000);

    window.addEventListener('resize', handleResize);
    updatePriceDisplay(null, null);
    updateScanner([]);
});

// ════════════════════════════════════════════
// Controls
// ════════════════════════════════════════════

function initControls() {
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.timeframe = parseInt(btn.dataset.tf);
            if (state.activeSymbol) loadSymbolData(state.activeSymbol);
        });
    });

    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.range = parseInt(btn.dataset.range);
            if (state.activeSymbol) loadSymbolData(state.activeSymbol);
        });
    });

    document.getElementById('symbolSelect').addEventListener('change', (e) => {
        switchInstrument(e.target.value);
    });

    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.chartType = btn.dataset.chart;
            switchChartType(state.chartType);
        });
    });
}

// ════════════════════════════════════════════
// Instruments
// ════════════════════════════════════════════

async function fetchInstruments() {
    try {
        const resp = await fetch('/api/instruments');
        const data = await resp.json();
        state.instruments = Array.isArray(data) ? data : [];
    } catch (e) {
        state.instruments = [];
    }
    renderInstrumentDropdown();
}

function renderInstrumentDropdown() {
    const select = document.getElementById('symbolSelect');
    select.innerHTML = '';

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '— Select pair —';
    placeholder.disabled = true;
    placeholder.selected = !state.activeSymbol;
    select.appendChild(placeholder);

    for (const [groupName, symbols] of Object.entries(ASSET_GROUPS)) {
        const group = document.createElement('optgroup');
        group.label = groupName;
        symbols.forEach(sym => {
            const opt = document.createElement('option');
            opt.value = sym;
            opt.textContent = sym;
            group.appendChild(opt);
        });
        if (group.children.length > 0) select.appendChild(group);
    }

    if (state.activeSymbol) select.value = state.activeSymbol;
}

// ════════════════════════════════════════════
// Data Refresh
// ════════════════════════════════════════════

async function refreshFastData() {
    if (!state.activeSymbol) return;
    const sym = state.activeSymbol;
    const tf = state.timeframe;
    const range = state.range;

    try {
        const [candles, delta, micro] = await Promise.all([
            fetchJSON(`/api/candles/${sym}?tf=${tf}&range=${range}`),
            fetchJSON(`/api/delta/${sym}?tf=${tf}&range=${range}`),
            fetchJSON(`/api/microstructure/${sym}`),
        ]);

        if (candles && candles.length > 0 && state.candleSeries) {
            state.candleSeries.setData(mapCandleData(candles));
            const last = candles[candles.length - 1];
            updatePriceDisplay(last.close, last.delta);
            state._candleBucket = {
                time: last.time, open: last.open, high: last.high,
                low: last.low, close: last.close,
            };
        }

        if (delta && delta.length > 0) {
            state._deltaCumulative = delta[delta.length - 1].value;
            updateChartInfoOverlay();
        }

        if (micro) {
            state._microData = micro;
            updateChartInfoOverlay();
        }
    } catch (e) { /* silent */ }
}

async function refreshScannerLoop() {
    try {
        const scanner = await fetchJSON('/api/scanner');
        if (scanner) updateScanner(scanner);
    } catch (e) { /* silent */ }
}

async function refreshSlowData() {
    if (!state.activeSymbol) return;
    const sym = state.activeSymbol;

    try {
        const [strategy, vps, signals, bias] = await Promise.all([
            fetchJSON(`/api/strategy-status/${sym}`),
            fetchJSON(`/api/volume-profile/${sym}?range=${state.range}`),
            fetchJSON(`/api/signals/${sym}`),
            fetchJSON(`/api/bias/${sym}`),
        ]);

        if (strategy) {
            state._strategyData = strategy;
            updateTradeLines();
            updateChartInfoOverlay();
        }
        if (vps && vps.length > 0) {
            state._vpData = vps[0];
            updateChartInfoOverlay();
        }
        if (signals && signals.length > 0) {
            state.signals = signals;
        }
        if (bias) {
            state._biasData = bias;
            updateVPLines(bias);
            updateChartInfoOverlay();
        }
    } catch (e) { /* silent */ }
}

// ════════════════════════════════════════════
// Symbol Loading
// ════════════════════════════════════════════

async function switchInstrument(symbol) {
    /* D-06: a new instrument starts with no markers from the previous one. */
    state.markers = [];
    applyMarkers();
    state.activeSymbol = symbol;
    const select = document.getElementById('symbolSelect');
    if (select.value !== symbol) select.value = symbol;

    // Show switching indicator while data loads
    if (select) select.classList.add('switching');

    const overlay = document.getElementById('waitingOverlay');
    if (overlay) overlay.classList.add('hidden');

    if (!state.priceChart) createPriceChart();
    await loadSymbolData(symbol);
    // Remove switching indicator after data loads
    if (select) select.classList.remove('switching');
}

async function loadSymbolData(symbol) {
    const tf = state.timeframe;
    const range = state.range;
    state._candleBucket = null;
    state._deltaCumulative = null;

    const [candles, delta, bias, vps, strategy, signals, micro] = await Promise.all([
        fetchJSON(`/api/candles/${symbol}?tf=${tf}&range=${range}`),
        fetchJSON(`/api/delta/${symbol}?tf=${tf}&range=${range}`),
        fetchJSON(`/api/bias/${symbol}`),
        fetchJSON(`/api/volume-profile/${symbol}?range=${range}`),
        fetchJSON(`/api/strategy-status/${symbol}`),
        fetchJSON(`/api/signals/${symbol}`),
        fetchJSON(`/api/microstructure/${symbol}`),
    ]);

    // Price chart
    if (candles && candles.length > 0 && state.candleSeries) {
        state.candleSeries.setData(mapCandleData(candles));
        if (state.chartType === 'baseline' && candles.length > 0) {
            state.candleSeries.applyOptions({
                baseValue: { type: 'price', price: candles[0].open },
            });
        }
    } else if (state.candleSeries) {
        state.candleSeries.setData([]);
    }

    // Delta (for overlay)
    if (delta && delta.length > 0) {
        state._deltaCumulative = delta[delta.length - 1].value;
    }

    // Bias + VP lines
    if (bias) {
        state._biasData = bias;
        updateVPLines(bias);
    }
    if (vps && vps.length > 0) state._vpData = vps[0];
    if (strategy) { state._strategyData = strategy; updateTradeLines(); }
    if (signals && signals.length > 0) state.signals = signals;
    if (micro) state._microData = micro;

    // Price display
    if (candles && candles.length > 0) {
        const last = candles[candles.length - 1];
        updatePriceDisplay(last.close, last.delta);
        state._candleBucket = {
            time: last.time, open: last.open, high: last.high,
            low: last.low, close: last.close,
        };
    }

    // Chart markers
    const markers = await fetchJSON(`/api/markers/${symbol}`);
    state.markers = markers || [];
    applyMarkers();

    updateChartInfoOverlay();
}

async function fetchJSON(url) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) return null;
        return await resp.json();
    } catch { return null; }
}

// ════════════════════════════════════════════
// the vendored chart library
// ════════════════════════════════════════════

function createPriceChart() {
    const container = document.getElementById('priceChartContainer');
    state.priceChart = LightweightCharts.createChart(container, {
        autoSize: true,
        layout: {
            background: { type: 'solid', color: '#1c2128' },
            textColor: '#8b949e',
            fontSize: 11,
            fontFamily: "'Consolas', monospace",
        },
        grid: {
            vertLines: { color: 'rgba(48, 54, 61, 0.5)' },
            horzLines: { color: 'rgba(48, 54, 61, 0.5)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: 'rgba(88, 166, 255, 0.3)', width: 1 },
            horzLine: { color: 'rgba(88, 166, 255, 0.3)', width: 1 },
        },
        rightPriceScale: {
            borderColor: '#30363d',
            scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
            borderColor: '#30363d',
            timeVisible: true,
            secondsVisible: false,
        },
        handleScroll: { vertTouchDrag: false },
    });

    state.candleSeries = state.priceChart.addCandlestickSeries({
        upColor: '#3fb950',
        downColor: '#f85149',
        borderUpColor: '#3fb950',
        borderDownColor: '#f85149',
        wickUpColor: '#3fb950',
        wickDownColor: '#f85149',
    });
}

// ════════════════════════════════════════════
// Chart Type Switching
// ════════════════════════════════════════════

function switchChartType(type) {
    if (!state.priceChart) return;
    if (state.candleSeries) {
        state.priceChart.removeSeries(state.candleSeries);
        state.candleSeries = null;
    }

    switch (type) {
        case 'line':
            state.candleSeries = state.priceChart.addLineSeries({ color: '#58a6ff', lineWidth: 2 });
            break;
        case 'area':
            state.candleSeries = state.priceChart.addAreaSeries({
                lineColor: '#58a6ff', topColor: 'rgba(88, 166, 255, 0.25)',
                bottomColor: 'rgba(88, 166, 255, 0.02)', lineWidth: 2,
            });
            break;
        case 'bars':
            state.candleSeries = state.priceChart.addBarSeries({ upColor: '#3fb950', downColor: '#f85149' });
            break;
        case 'baseline':
            state.candleSeries = state.priceChart.addBaselineSeries({
                baseValue: { type: 'price', price: 0 },
                topLineColor: '#3fb950', topFillColor1: 'rgba(63, 185, 80, 0.2)',
                topFillColor2: 'rgba(63, 185, 80, 0.02)', bottomLineColor: '#f85149',
                bottomFillColor1: 'rgba(248, 81, 73, 0.02)', bottomFillColor2: 'rgba(248, 81, 73, 0.2)',
                lineWidth: 2,
            });
            break;
        default:
            state.candleSeries = state.priceChart.addCandlestickSeries({
                upColor: '#3fb950', downColor: '#f85149',
                borderUpColor: '#3fb950', borderDownColor: '#f85149',
                wickUpColor: '#3fb950', wickDownColor: '#f85149',
            });
            break;
    }

    if (state.activeSymbol) loadSymbolData(state.activeSymbol);
}

function mapCandleData(candles) {
    const type = state.chartType;
    if (type === 'line' || type === 'area' || type === 'baseline') {
        return candles.map(c => ({ time: c.time, value: c.close }));
    }
    return candles.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }));
}

function mapCandleUpdate(bucket) {
    const type = state.chartType;
    if (type === 'line' || type === 'area' || type === 'baseline') {
        return { time: bucket.time, value: bucket.close };
    }
    return { ...bucket };
}

// ════════════════════════════════════════════
// Chart Markers
// ════════════════════════════════════════════

function signalToMarker(sig) {
    const isBuy = (sig.direction === 'buy' || sig.direction === 'long');
    const time = Math.floor((sig.timestamp_ms || sig.receivedAt || Date.now()) / 1000);
    const sigType = (sig.signals && sig.signals[0] && sig.signals[0].signal_type) || sig.signal_type || '';
    const action = sig.action || 'alert_only';

    if (action === 'enter')        return { time, position: isBuy ? 'belowBar' : 'aboveBar', color: isBuy ? '#00e676' : '#ff1744', shape: 'circle', text: 'ENTRY' };
    if (action === 'break_even')   return { time, position: 'aboveBar', color: '#42a5f5', shape: 'square', text: 'BE' };
    if (action === 'trail')        return { time, position: 'aboveBar', color: '#26c6da', shape: 'square', text: 'TRAIL' };
    if (action === 'exit')         return { time, position: 'aboveBar', color: '#ff1744', shape: 'circle', text: 'EXIT' };
    if (action === 'exit_warning') return { time, position: 'aboveBar', color: '#ffeb3b', shape: 'circle', text: 'WARN' };

    if (sigType.includes('absorption'))  return { time, position: isBuy ? 'belowBar' : 'aboveBar', color: isBuy ? '#26a69a' : '#ef5350', shape: isBuy ? 'arrowUp' : 'arrowDown', text: 'ABS' };
    if (sigType.includes('initiative'))  return { time, position: isBuy ? 'belowBar' : 'aboveBar', color: isBuy ? '#66bb6a' : '#ffa726', shape: isBuy ? 'arrowUp' : 'arrowDown', text: 'INIT' };
    if (sigType.includes('sweep'))       return { time, position: 'aboveBar', color: '#ab47bc', shape: 'arrowDown', text: 'SWEEP' };
    if (sigType.includes('exhaustion'))  return { time, position: 'aboveBar', color: '#ffeb3b', shape: 'circle', text: 'EXHAUST' };
    if (sigType.includes('divergence')) return { time, position: 'aboveBar', color: '#ff9800', shape: 'circle', text: 'DIV' };

    return { time, position: 'aboveBar', color: '#9e9e9e', shape: 'circle', text: 'SIG' };
}

function applyMarkers() {
    if (!state.candleSeries) return;
    if (state.chartType !== 'candles' && state.chartType !== 'bars') return;
    const sorted = [...state.markers].sort((a, b) => a.time - b.time);
    state.candleSeries.setMarkers(sorted);
}

// ════════════════════════════════════════════
// VP Lines on Chart
// ════════════════════════════════════════════

function updateVPLines(bias) {
    if (!state.candleSeries) return;

    state.vpLines.forEach(line => {
        try { state.candleSeries.removePriceLine(line); } catch {}
    });
    state.vpLines = [];

    const lineConfigs = [
        { price: bias.poc, title: 'POC', color: '#d29922', style: 0, width: 2 },
        { price: bias.vah, title: 'VAH', color: '#f85149', style: 2, width: 1 },
        { price: bias.val, title: 'VAL', color: '#3fb950', style: 2, width: 1 },
    ];

    if (bias.merged_vah) lineConfigs.push({ price: bias.merged_vah, title: 'M-VAH', color: '#f85149', style: 1, width: 1 });
    if (bias.merged_val) lineConfigs.push({ price: bias.merged_val, title: 'M-VAL', color: '#3fb950', style: 1, width: 1 });

    if (bias.qualified_levels && bias.qualified_levels.length > 0) {
        bias.qualified_levels.forEach(lv => {
            const c = lv.direction === 'buy' ? '#3fb950' : '#f85149';
            const label = `${lv.level_type || 'LV'} ${lv.direction === 'buy' ? '▲' : '▼'}`;
            lineConfigs.push({ price: lv.price, title: label, color: c, style: 1, width: 1 });
        });
    }

    lineConfigs.forEach(cfg => {
        if (cfg.price && cfg.price > 0) {
            const line = state.candleSeries.createPriceLine({
                price: cfg.price, color: cfg.color, lineWidth: cfg.width || 1,
                lineStyle: cfg.style, axisLabelVisible: true, title: cfg.title,
            });
            state.vpLines.push(line);
        }
    });
}

// ════════════════════════════════════════════
// Trade Lines (Entry / SL / TP)
// ════════════════════════════════════════════

function updateTradeLines() {
    if (!state.candleSeries) return;

    state.tradeLines.forEach(line => {
        try { state.candleSeries.removePriceLine(line); } catch {}
    });
    state.tradeLines = [];

    const strategy = state._strategyData || {};
    const trade = strategy.trade || {};
    const phase = (strategy.phase || trade.phase || '').toLowerCase();

    // Only draw when there's an active trade
    if (!phase || phase === 'idle' || phase === 'none' || phase === 'closed' || phase === 'waiting_for_price') return;

    const lines = [];
    if (trade.entry_price && trade.entry_price > 0) {
        lines.push({ price: trade.entry_price, title: '► ENTRY', color: '#58a6ff', style: 0, width: 2 });
    }
    if (trade.stop_loss && trade.stop_loss > 0) {
        lines.push({ price: trade.stop_loss, title: '✕ SL', color: '#f85149', style: 2, width: 2 });
    }
    if (trade.take_profit && trade.take_profit > 0) {
        lines.push({ price: trade.take_profit, title: '✓ TP', color: '#3fb950', style: 2, width: 2 });
    }

    lines.forEach(cfg => {
        const line = state.candleSeries.createPriceLine({
            price: cfg.price, color: cfg.color, lineWidth: cfg.width,
            lineStyle: cfg.style, axisLabelVisible: true, title: cfg.title,
        });
        state.tradeLines.push(line);
    });
}

// ════════════════════════════════════════════
// Scanner
// ════════════════════════════════════════════

const _SCAN_RANK = {
    'IN_TRADE': 100, 'TRAILING': 95, 'BREAK_EVEN': 90,
    'ENTRY_READY': 80,
    'AT_LEVEL_SCANNING': 60, 'WATCHING': 50,
    'WAITING_FOR_PRICE': 20,
    'IDLE': 10,
};

function updateScanner(pairs) {
    const feed = document.getElementById('scannerFeed');
    const countEl = document.getElementById('scannerCount');
    if (!feed || !countEl) return;

    pairs = Array.isArray(pairs) ? pairs : [];
    countEl.textContent = pairs.length;

    if (pairs.length === 0) {
        feed.innerHTML = '<div class="scanner-empty">No pairs detected</div>';
        return;
    }

    pairs.sort((a, b) => {
        const ra = _SCAN_RANK[a.overall] || 0;
        const rb = _SCAN_RANK[b.overall] || 0;
        if (rb !== ra) return rb - ra;
        return (b.priority || 0) - (a.priority || 0);
    });

    const prevMap = state._prevScannerState || {};
    const newMap = {};

    feed.innerHTML = '';
    pairs.forEach((p, idx) => {
        const row = document.createElement('div');
        row.className = 'scanner-row';

        const overall = p.overall || 'IDLE';
        newMap[p.symbol] = overall;

        if (overall === 'IN_TRADE' || overall === 'TRAILING' || overall === 'BREAK_EVEN') {
            row.classList.add('flash-trade');
        } else if (overall === 'ENTRY_READY') {
            row.classList.add('flash-ready');
        } else if (overall === 'AT_LEVEL_SCANNING' || overall === 'WATCHING') {
            row.classList.add('flash-near');
        }

        if (prevMap[p.symbol] && prevMap[p.symbol] !== overall) {
            row.classList.add('scanner-flash-change');
        }

        if (p.symbol === state.activeSymbol) {
            row.classList.add('active-pair');
        }

        const rankLabel = idx < 3 ? `#${idx + 1}` : '';

        let statusColor = 'var(--text-muted)';
        let statusBg = 'transparent';
        if (overall === 'IN_TRADE' || overall === 'TRAILING' || overall === 'BREAK_EVEN') {
            statusColor = 'var(--blue)'; statusBg = 'var(--blue-bg)';
        } else if (overall === 'ENTRY_READY') {
            statusColor = 'var(--green)'; statusBg = 'var(--green-bg)';
        } else if (overall === 'AT_LEVEL_SCANNING' || overall === 'WATCHING') {
            statusColor = 'var(--orange)'; statusBg = 'var(--orange-bg)';
        } else if (overall === 'WAITING_FOR_PRICE') {
            statusColor = 'var(--text-secondary)';
        }

        const biasArrow = p.bias_direction === 'buy' ? '▲' : p.bias_direction === 'sell' ? '▼' : '–';
        const biasColor = p.bias_direction === 'buy' ? 'var(--green)' : p.bias_direction === 'sell' ? 'var(--red)' : 'var(--text-muted)';

        let pips = '';
        for (let i = 0; i < (p.steps_total || 6); i++) {
            pips += `<span class="scanner-pip${i < p.steps_done ? ' done' : ''}"></span>`;
        }

        const conf = p.bias_confidence || 0;
        const confColor = conf >= 70 ? 'var(--green)' : conf >= 50 ? 'var(--orange)' : 'var(--red)';

        row.innerHTML = `
            ${rankLabel ? `<span class="scanner-rank">${rankLabel}</span>` : '<span class="scanner-rank-spacer"></span>'}
            <span class="scanner-symbol">${p.symbol}</span>
            <span class="scanner-status" style="color:${statusColor};background:${statusBg}">${overall.replace(/_/g, ' ')}</span>
            <span class="scanner-conf-bar"><span class="scanner-conf-fill" style="width:${conf}%;background:${confColor}"></span></span>
            <span class="scanner-steps">${pips}</span>
            <span class="scanner-bias" style="color:${biasColor}">${biasArrow}</span>
            <span class="scanner-price">${p.current_price ? p.current_price.toFixed(p.current_price > 100 ? 1 : 4) : '—'}</span>
        `;

        row.addEventListener('click', () => switchInstrument(p.symbol));
        feed.appendChild(row);
    });

    state._prevScannerState = newMap;
}

// ════════════════════════════════════════════
// Chart Info Overlay
// ════════════════════════════════════════════

function updateChartInfoOverlay() {
    if (!state.activeSymbol) return;

    const topLeft = document.getElementById('chartInfoTopLeft');
    const topRight = document.getElementById('chartInfoTopRight');
    const bottomLeft = document.getElementById('chartInfoBottomLeft');
    const bottomRight = document.getElementById('chartInfoBottomRight');
    if (!topLeft) return;

    const sym = state.activeSymbol;
    const bias = state._biasData || {};
    const strategy = state._strategyData || {};
    const vp = state._vpData || {};
    const micro = state._microData || {};

    // ── Top-Left: Symbol + Bias + Strategy + Session ──
    const biasDir = bias.direction || 'neutral';
    const biasConf = bias.confidence || 0;
    const biasArrow = biasDir === 'long' ? '▲' : biasDir === 'short' ? '▼' : '◆';
    const biasClass = biasDir === 'long' ? 'long' : biasDir === 'short' ? 'short' : 'neutral';

    const overall = (strategy.overall || 'IDLE').replace(/_/g, ' ');
    let stratClass = '';
    if (overall.includes('ENTRY READY')) stratClass = 'ready';
    else if (overall.includes('SCANNING') || overall.includes('WATCHING')) stratClass = 'scanning';
    else if (overall.includes('IN TRADE') || overall.includes('TRAILING')) stratClass = 'in-trade';

    const tfMap = { 60: '1m', 300: '5m', 900: '15m', 3600: '1H', 14400: '4H', 86400: '1D' };
    const tfLabel = tfMap[state.timeframe] || state.timeframe + 's';

    const hour = new Date().getUTCHours();
    let sessionName = 'Off-Hours';
    if (hour >= 0 && hour < 7) sessionName = 'Asia';
    else if (hour >= 7 && hour < 12) sessionName = 'London';
    else if (hour >= 12 && hour < 16) sessionName = 'NY AM';
    else if (hour >= 16 && hour < 21) sessionName = 'NY PM';

    topLeft.innerHTML = `
        <div class="chart-wm-symbol">${sym} · ${tfLabel}</div>
        <div class="chart-bias-badge ${biasClass}">${biasArrow} ${biasDir.toUpperCase()} ${biasConf}%</div>
        <div class="chart-strategy-chip ${stratClass}">${overall}</div>
        <div class="chart-session-info">${sessionName} Session</div>
    `;

    // ── Top-Right: VP levels + qualified levels ──
    const poc = vp.poc || bias.poc;
    const vah = vp.vah || bias.vah;
    const val = vp.val || bias.val;
    const shape = vp.shape || bias.profile_shape || '—';

    let trHtml = '';
    if (poc || vah || val) {
        trHtml += `<div class="chart-vp-levels">`;
        trHtml += `<div class="chart-vp-row"><span class="cvp-label" style="color:var(--text-muted)">Shape</span><span class="cvp-price" style="color:var(--text-muted)">${shape}</span></div>`;
        trHtml += `<div class="chart-vp-row"><span class="cvp-label" style="color:#d29922">POC</span><span class="cvp-price" style="color:#d29922">${poc ? formatPrice(poc) : '—'}</span></div>`;
        trHtml += `<div class="chart-vp-row"><span class="cvp-label" style="color:#f85149">VAH</span><span class="cvp-price" style="color:#f85149">${vah ? formatPrice(vah) : '—'}</span></div>`;
        trHtml += `<div class="chart-vp-row"><span class="cvp-label" style="color:#3fb950">VAL</span><span class="cvp-price" style="color:#3fb950">${val ? formatPrice(val) : '—'}</span></div>`;

        const qLevels = bias.qualified_levels || [];
        if (qLevels.length > 0) {
            qLevels.slice(0, 3).forEach(lv => {
                const lvColor = lv.type === 'resistance' ? '#f85149' : '#3fb950';
                trHtml += `<div class="chart-vp-row"><span class="cvp-label" style="color:${lvColor}">${lv.type === 'resistance' ? 'RES' : 'SUP'}</span><span class="cvp-price" style="color:${lvColor}">${formatPrice(lv.price)}</span></div>`;
            });
        }
        trHtml += `</div>`;
    }
    topRight.innerHTML = trHtml;

    // ── Bottom-Left: Delta, confidence, R:R, P&L ──
    const rows = [];
    if (state._deltaCumulative != null) {
        const d = state._deltaCumulative;
        const dClass = d >= 0 ? 'bull' : 'bear';
        rows.push(`<div class="chart-info-row"><span class="ci-label">DELTA</span><span class="ci-val ${dClass}">Σ ${d >= 0 ? '+' : ''}${d.toFixed(0)}</span></div>`);
    }
    if (strategy.bias_confidence) {
        rows.push(`<div class="chart-info-row"><span class="ci-label">CONF</span><span class="ci-val blue">${strategy.bias_confidence}%</span></div>`);
    }
    if (strategy.trade && strategy.trade.rr_ratio) {
        rows.push(`<div class="chart-info-row"><span class="ci-label">R:R</span><span class="ci-val gold">${strategy.trade.rr_ratio.toFixed(1)}x</span></div>`);
    }
    if (strategy.trade && strategy.trade.pnl_ticks != null) {
        const pnl = strategy.trade.pnl_ticks;
        const pClass = pnl >= 0 ? 'bull' : 'bear';
        rows.push(`<div class="chart-info-row"><span class="ci-label">P&L</span><span class="ci-val ${pClass}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(1)} ticks</span></div>`);
    }
    bottomLeft.innerHTML = rows.join('');

    // ── Bottom-Right: Microstructure snapshot ──
    const brRows = [];
    if (micro.spread != null) {
        brRows.push(`<div class="chart-info-row"><span class="ci-label">SPREAD</span><span class="ci-val ${micro.spread <= 2 ? 'bull' : 'orange'}">${micro.spread}</span></div>`);
    }
    if (micro.ob_imbalance != null) {
        const imb = micro.ob_imbalance;
        const imbClass = imb >= 0.2 ? 'bull' : imb <= -0.2 ? 'bear' : 'neutral';
        brRows.push(`<div class="chart-info-row"><span class="ci-label">OB IMB</span><span class="ci-val ${imbClass}">${(imb * 100).toFixed(0)}%</span></div>`);
    }
    if (micro.volume_ratio != null) {
        const vr = micro.volume_ratio;
        const vrClass = vr >= 1.5 ? 'orange' : vr >= 1.0 ? 'bull' : 'neutral';
        brRows.push(`<div class="chart-info-row"><span class="ci-label">VOL %</span><span class="ci-val ${vrClass}">${(vr * 100).toFixed(0)}%</span></div>`);
    }
    if (micro.volatility != null) {
        brRows.push(`<div class="chart-info-row"><span class="ci-label">VOLA</span><span class="ci-val purple">${micro.volatility.toFixed(2)}</span></div>`);
    }
    if (bottomRight) bottomRight.innerHTML = brRows.join('');
}

// ════════════════════════════════════════════
// Resize
// ════════════════════════════════════════════

function handleResize() {
    // Price chart uses autoSize — nothing extra needed
}

const resizeObserver = new ResizeObserver(() => handleResize());
setTimeout(() => {
    const pc = document.getElementById('priceChartContainer');
    if (pc) resizeObserver.observe(pc);
}, 100);

// ════════════════════════════════════════════
// WebSocket
// ════════════════════════════════════════════

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    updateWsStatus('connecting');
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        updateWsStatus('connected');
        state.reconnectDelay = 1000;
        setTimeout(() => {
            if (state.activeSymbol) loadSymbolData(state.activeSymbol);
        }, 2000);
    };

    state.ws.onclose = () => {
        updateWsStatus('disconnected');
        scheduleReconnect();
    };

    state.ws.onerror = () => {};

    state.ws.onmessage = (event) => {
        try {
            handleMessage(JSON.parse(event.data));
        } catch (e) {}
    };

}

function startPing() {
    if (state.pingTimer) return;                 // one interval per page, not one per reconnect
    state.pingTimer = setInterval(() => {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send('ping');
    }, 30000);
}

function scheduleReconnect() {
    if (state.reconnectTimer) return;
    state.reconnectTimer = setTimeout(() => {
        state.reconnectTimer = null;
        state.reconnectDelay = Math.min(state.reconnectDelay * 2, 30000);
        connectWebSocket();
    }, state.reconnectDelay);
}

function updateWsStatus(status) {
    const el = document.getElementById('wsStatus');
    const dot = el.querySelector('.ws-dot');
    dot.className = 'ws-dot ' + status;
    el.lastChild.textContent = ' ' + status.charAt(0).toUpperCase() + status.slice(1);
}

// ════════════════════════════════════════════
// Message Router
// ════════════════════════════════════════════

function handleMessage(msg) {
    const { channel, symbol, data } = msg;
    if (symbol && symbol !== state.activeSymbol) {
        if (channel === 'signal') handleSignal(symbol, data);
        return;
    }

    switch (channel) {
        case 'tick':       handleTick(data); break;
        case 'candle':     handleCandle(data); break;
        case 'signal':     handleSignal(symbol, data); break;
        case 'bias':       state._biasData = data; updateVPLines(data); updateChartInfoOverlay(); break;
        case 'volume_profile': if (data) { state._vpData = data; updateChartInfoOverlay(); } break;
        case 'microstructure': if (data) { state._microData = data; updateChartInfoOverlay(); } break;
        case 'delta':      handleDelta(data); break;
        case 'stats':      handleStats(symbol, data); break;
        case 'trade_state': fetchJSON(`/api/strategy-status/${state.activeSymbol}`).then(s => { if (s) { state._strategyData = s; updateTradeLines(); updateChartInfoOverlay(); } }); break;
        case 'pong': break;
    }
}

// ════════════════════════════════════════════
// Data Handlers
// ════════════════════════════════════════════

function handleTick(data) {
    const price = data.price;
    updatePriceDisplay(price, null);

    if (state.candleSeries && state._candleBucket) {
        const b = state._candleBucket;
        b.high = Math.max(b.high, price);
        b.low = Math.min(b.low, price);
        b.close = price;
        state.candleSeries.update(mapCandleUpdate(b));
    }

    // Live delta from ticks
    if (state._deltaCumulative != null) {
        const tickDelta = data.side === 'buy' ? (data.size || 0) : -(data.size || 0);
        if (tickDelta !== 0) {
            state._deltaCumulative += tickDelta;
            updateChartInfoOverlay();
        }
    }
}

function handleCandle(data) {
    if (!state.candleSeries) return;
    const tfSec = state.timeframe;
    const bucketTime = Math.floor((data.time || data.timestamp_ms / 1000) / tfSec) * tfSec;

    if (!state._candleBucket || state._candleBucket.time !== bucketTime) {
        state._candleBucket = {
            time: bucketTime, open: data.open, high: data.high,
            low: data.low, close: data.close,
        };
    } else {
        const b = state._candleBucket;
        b.high = Math.max(b.high, data.high);
        b.low = Math.min(b.low, data.low);
        b.close = data.close;
    }

    state.candleSeries.update(mapCandleUpdate(state._candleBucket));
    updatePriceDisplay(data.close, data.delta);
}

function handleDelta(data) {
    const barDelta = data.bar_delta || data.value || 0;
    state._deltaCumulative = (state._deltaCumulative || 0) + barDelta;
    updateChartInfoOverlay();
}

function handleSignal(symbol, data) {
    state.signals.unshift({ symbol, ...data, receivedAt: Date.now() });
    if (state.signals.length > 100) state.signals.pop();

    if (symbol === state.activeSymbol) {
        const marker = signalToMarker(data);
        if (marker) {
            state.markers.push(marker);
            /* D-06: the marker list grew per signal and survived an instrument switch. */
            if (state.markers.length > 200) state.markers.splice(0, state.markers.length - 200);
            applyMarkers();
        }
    }
}

function handleStats(symbol, data) {
    if (symbol === state.activeSymbol || !symbol) {
        if (data.ticks !== undefined) document.getElementById('tickCount').textContent = `Ticks: ${formatNumber(data.ticks)}`;
        if (data.candles !== undefined) document.getElementById('candleCount').textContent = `Candles: ${formatNumber(data.candles)}`;
    }
    if (data.data_source) document.getElementById('dataSource').textContent = data.data_source;
    document.getElementById('lastUpdate').textContent = `Updated: ${new Date().toLocaleTimeString()}`;
}

// ════════════════════════════════════════════
// UI Helpers
// ════════════════════════════════════════════

function updatePriceDisplay(price, delta) {
    const priceEl = document.getElementById('currentPrice');
    const deltaEl = document.getElementById('currentDelta');

    if (price != null && priceEl) priceEl.textContent = formatPrice(price);
    else if (priceEl) priceEl.textContent = '—';

    if (delta != null && deltaEl) {
        deltaEl.textContent = `Δ ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}`;
        deltaEl.className = `panel-delta ${delta >= 0 ? 'positive' : 'negative'}`;
    } else if (deltaEl) {
        deltaEl.textContent = 'Δ —';
        deltaEl.className = 'panel-delta';
    }
}

function formatPrice(price) {
    if (price == null || price === 0) return '—';
    if (price > 1000) return price.toFixed(1);
    if (price > 10) return price.toFixed(2);
    return price.toFixed(4);
}

function formatNumber(n) {
    if (n == null) return '—';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
}

// Footer clock
setInterval(() => {
    const el = document.getElementById('lastUpdate');
    if (el) el.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
}, 1000);
