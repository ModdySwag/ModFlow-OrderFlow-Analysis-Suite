/**
 * Performance Analytics Dashboard Component
 * Tracks trading performance, win rates, and P&L
 */

class PerformanceDashboard {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            currency: 'USD',
            riskPerTrade: 0.5, // percentage
            colors: {
                profit: '#3fb950',
                loss: '#f85149',
                neutral: '#8b949e',
                breakeven: '#d29922',
                ...options.colors
            },
            ...options
        };

        this.stats = {
            totalTrades: 0,
            wins: 0,
            losses: 0,
            breakevens: 0,
            totalPnL: 0,
            dailyPnL: 0,
            weeklyPnL: 0,
            avgWin: 0,
            avgLoss: 0,
            avgRR: 0,
            expectancy: 0,
            maxDrawdown: 0,
            currentDrawdown: 0,
            bestTrade: null,
            worstTrade: null,
            byPattern: {}
        };

        this.trades = [];
        this._init();
    }

    _init() {
        this.container.innerHTML = `
            <div class="perf-dashboard">
                <!-- Summary Cards Row -->
                <div class="perf-summary">
                    <div class="perf-card perf-pnl-card">
                        <div class="perf-card-label">Daily P&L</div>
                        <div class="perf-card-value" id="perfDailyPnL">$0.00</div>
                        <div class="perf-card-sub" id="perfDailyPct">0%</div>
                    </div>
                    <div class="perf-card">
                        <div class="perf-card-label">Win Rate</div>
                        <div class="perf-card-value" id="perfWinRate">0%</div>
                        <div class="perf-card-sub" id="perfWinLoss">0W / 0L</div>
                    </div>
                    <div class="perf-card">
                        <div class="perf-card-label">Avg R:R</div>
                        <div class="perf-card-value" id="perfAvgRR">0.0</div>
                        <div class="perf-card-sub" id="perfExpectancy">Exp: 0.00R</div>
                    </div>
                    <div class="perf-card">
                        <div class="perf-card-label">Drawdown</div>
                        <div class="perf-card-value perf-dd" id="perfDrawdown">0%</div>
                        <div class="perf-card-sub" id="perfMaxDD">Max: 0%</div>
                    </div>
                </div>

                <!-- P&L Chart -->
                <div class="perf-chart-section">
                    <div class="perf-section-header">
                        <span class="perf-section-title">Equity Curve</span>
                        <div class="perf-chart-controls">
                            <button class="perf-chart-btn active" data-range="day">1D</button>
                            <button class="perf-chart-btn" data-range="week">1W</button>
                            <button class="perf-chart-btn" data-range="month">1M</button>
                            <button class="perf-chart-btn" data-range="all">All</button>
                        </div>
                    </div>
                    <div class="perf-chart" id="perfChart">
                        <canvas id="perfChartCanvas"></canvas>
                    </div>
                </div>

                <!-- Pattern Performance -->
                <div class="perf-patterns-section">
                    <div class="perf-section-header">
                        <span class="perf-section-title">Performance by Pattern</span>
                    </div>
                    <div class="perf-patterns" id="perfPatterns">
                        <div class="perf-pattern-empty">No pattern data yet</div>
                    </div>
                </div>

                <!-- Recent Trades -->
                <div class="perf-trades-section">
                    <div class="perf-section-header">
                        <span class="perf-section-title">Recent Trades</span>
                        <button class="perf-export-btn" id="perfExport" title="Export the trade list as CSV">⬇ Export</button>
                    </div>
                    <div class="perf-trades-table" id="perfTrades">
                        <table class="perf-table">
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Symbol</th>
                                    <th>Side</th>
                                    <th>Pattern</th>
                                    <th>Entry</th>
                                    <th>Exit</th>
                                    <th>P&L</th>
                                    <th>R</th>
                                </tr>
                            </thead>
                            <tbody id="perfTradesTbody">
                                <tr class="perf-empty-row">
                                    <td colspan="8">No trades recorded</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Risk Status -->
                <div class="perf-risk-section">
                    <div class="perf-risk-header">
                        <span class="perf-section-title">Risk Status</span>
                    </div>
                    <div class="perf-risk-content">
                        <div class="perf-risk-item">
                            <span class="perf-risk-label">Daily Loss Limit:</span>
                            <div class="perf-risk-bar">
                                <div class="perf-risk-fill" id="perfRiskFill"></div>
                            </div>
                            <span class="perf-risk-value" id="perfRiskPct">0% used</span>
                        </div>
                        <div class="perf-risk-item">
                            <span class="perf-risk-label">Trades Today:</span>
                            <span class="perf-risk-value" id="perfTradesToday">0 / 8</span>
                        </div>
                        <div class="perf-risk-status" id="perfRiskStatus">
                            <span class="perf-risk-badge perf-risk-ok">✓ Trading Allowed</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this._cacheElements();
        this._initChart();
        this._initControls();
    }

    _cacheElements() {
        this.els = {
            dailyPnL: document.getElementById('perfDailyPnL'),
            dailyPct: document.getElementById('perfDailyPct'),
            winRate: document.getElementById('perfWinRate'),
            winLoss: document.getElementById('perfWinLoss'),
            avgRR: document.getElementById('perfAvgRR'),
            expectancy: document.getElementById('perfExpectancy'),
            drawdown: document.getElementById('perfDrawdown'),
            maxDD: document.getElementById('perfMaxDD'),
            chartCanvas: document.getElementById('perfChartCanvas'),
            patterns: document.getElementById('perfPatterns'),
            tradesTbody: document.getElementById('perfTradesTbody'),
            riskFill: document.getElementById('perfRiskFill'),
            riskPct: document.getElementById('perfRiskPct'),
            tradesToday: document.getElementById('perfTradesToday'),
            riskStatus: document.getElementById('perfRiskStatus')
        };
    }

    _initChart() {
        this.chartCtx = this.els.chartCanvas.getContext('2d');
        this.equityCurve = [];
        this._resizeChart();
        window.addEventListener('resize', () => this._resizeChart());
    }

    _resizeChart() {
        const container = this.els.chartCanvas.parentElement;
        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        
        this.els.chartCanvas.width = rect.width * dpr;
        this.els.chartCanvas.height = rect.height * dpr;
        this.els.chartCanvas.style.width = rect.width + 'px';
        this.els.chartCanvas.style.height = rect.height + 'px';
        
        this.chartCtx.scale(dpr, dpr);
        this.chartWidth = rect.width;
        this.chartHeight = rect.height;
        
        this._renderChart();
    }

    _initControls() {
        // Chart range buttons
        document.querySelectorAll('.perf-chart-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.perf-chart-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.chartRange = e.target.dataset.range;
                this._renderChart();
            });
        });

        // Export button
        document.getElementById('perfExport').addEventListener('click', () => {
            this._exportCSV();
        });

        this.chartRange = 'day';
    }

    /**
     * Update with new stats
     */
    setStats(stats) {
        this.stats = { ...this.stats, ...stats };
        this._render();
    }

    /**
     * Add completed trade
     */
    /* D-08: the list was unbounded and every add re-ran the full stats + equity + canvas pass.
        Capped, and the recalculation is debounced to one per 250 ms. */
    _scheduleStats() {
        if (this._statsTimer) return;
        this._statsTimer = setTimeout(() => {
            this._statsTimer = null;
            this._recalculateStats();
        }, 250);
    }

    /* D-08: running stats. addTrade used to re-scan the whole list per add (10,000 adds meant
       10,000 full passes over up to 2,000 trades). The counts, sums, daily figures and the
       pattern table are maintained incrementally now; only the equity/DD curve still needs the
       list order and that runs on the 250 ms debounce. `_accRemove` subtracts what the cap
       evicts, so the accumulators stay equal to a full recompute (pinned by
       legacy-widgets.selftest.js). */
    _newAcc() {
        return { wins: 0, losses: 0, breakevens: 0, winPnl: 0, lossPnl: 0, totalPnl: 0,
                 dailyPnl: 0, dailyCount: 0, dailyKey: new Date().toDateString(), byPattern: {} };
    }

    _accRoll(acc) {
        const today = new Date().toDateString();
        if (acc.dailyKey !== today) { acc.dailyKey = today; acc.dailyPnl = 0; acc.dailyCount = 0; }
        return today;
    }

    _accAdd(trade) {
        const acc = this._acc || (this._acc = this._newAcc());
        const today = this._accRoll(acc);
        const pnl = trade.pnl || 0;
        if (pnl > 0) { acc.wins++; acc.winPnl += pnl; }
        else if (pnl < 0) { acc.losses++; acc.lossPnl += Math.abs(pnl); }
        else { acc.breakevens++; }
        acc.totalPnl += pnl;
        if (new Date(trade.timestamp).toDateString() === today) { acc.dailyPnl += pnl; acc.dailyCount++; }
        const pattern = trade.pattern || 'Unknown';
        const row = acc.byPattern[pattern] || (acc.byPattern[pattern] = { wins: 0, losses: 0, pnl: 0, trades: 0 });
        row.trades++; row.pnl += pnl;
        if (pnl > 0) row.wins++; else if (pnl < 0) row.losses++;
        return acc;
    }

    _accRemove(trade) {
        const acc = this._acc;
        if (!acc || !trade) return acc;
        const today = this._accRoll(acc);
        const pnl = trade.pnl || 0;
        if (pnl > 0) { acc.wins--; acc.winPnl -= pnl; }
        else if (pnl < 0) { acc.losses--; acc.lossPnl -= Math.abs(pnl); }
        else { acc.breakevens--; }
        acc.totalPnl -= pnl;
        if (new Date(trade.timestamp).toDateString() === today) { acc.dailyPnl -= pnl; acc.dailyCount--; }
        const pattern = trade.pattern || 'Unknown';
        const row = acc.byPattern[pattern];
        if (row) {
            row.trades--; row.pnl -= pnl;
            if (pnl > 0) row.wins--; else if (pnl < 0) row.losses--;
            if (row.trades <= 0) delete acc.byPattern[pattern];
        }
        return acc;
    }

    _rebuildAcc() {
        this._acc = this._newAcc();
        for (let i = this.trades.length - 1; i >= 0; i--) this._accAdd(this.trades[i]);
        return this._acc;
    }

    addTrade(trade) {
        const entry = {
            ...trade,
            id: trade.id || Date.now(),
            timestamp: trade.timestamp || Date.now()
        };
        this.trades.unshift(entry);
        this._accAdd(entry);

        // Cap the list (the evicted trade is subtracted, so the accumulators stay exact), then
        // repaint stats on a debounce (D-08: not per add)
        while (this.trades.length > 2000) this._accRemove(this.trades.pop());
        this._scheduleStats();
        this._render();
    }

    /**
     * Set full trade history
     */
    setTrades(trades) {
        this.trades = trades || [];
        this._rebuildAcc();
        this._recalculateStats();
        this._render();
    }

    _recalculateStats() {
        /* D-08: the counts, sums, daily figures and the pattern table come from the running
           accumulators (maintained per add). Only the equity/DD pass still reads the list in
           order, and this method runs on the debounce — not per add. */
        const acc = this._acc || this._rebuildAcc();
        this._accRoll(acc);

        let equity = 0;
        let peak = 0;
        let maxDD = 0;
        this.trades.forEach(trade => {
            const pnl = trade.pnl || 0;
            equity += pnl;
            if (equity > peak) peak = equity;
            const dd = peak > 0 ? ((peak - equity) / peak) * 100 : 0;
            if (dd > maxDD) maxDD = dd;
        });

        const totalTrades = acc.wins + acc.losses + acc.breakevens;
        const winRate = totalTrades > 0 ? (acc.wins / totalTrades) * 100 : 0;
        const avgWin = acc.wins > 0 ? acc.winPnl / acc.wins : 0;
        const avgLoss = acc.losses > 0 ? acc.lossPnl / acc.losses : 0;
        const avgRR = avgLoss > 0 ? avgWin / avgLoss : 0;

        // Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)
        const expectancy = totalTrades > 0
            ? ((winRate / 100) * avgWin) - (((100 - winRate) / 100) * avgLoss)
            : 0;

        const currentDD = peak > 0 ? ((peak - equity) / peak) * 100 : 0;

        this.stats = {
            totalTrades,
            wins: acc.wins,
            losses: acc.losses,
            breakevens: acc.breakevens,
            totalPnL: equity,
            dailyPnL: acc.dailyPnl,
            avgWin,
            avgLoss,
            avgRR,
            expectancy,
            maxDrawdown: maxDD,
            currentDrawdown: currentDD,
            byPattern: acc.byPattern,
            tradesToday: acc.dailyCount
        };

        // Build equity curve
        this._buildEquityCurve();
    }

    _buildEquityCurve() {
        this.equityCurve = [];
        let equity = 0;

        const sortedTrades = [...this.trades].sort((a, b) => 
            (a.timestamp || 0) - (b.timestamp || 0)
        );

        sortedTrades.forEach(trade => {
            equity += (trade.pnl || 0);
            this.equityCurve.push({
                time: trade.timestamp,
                value: equity
            });
        });
    }

    _render() {
        this._renderSummary();
        this._renderChart();
        this._renderPatterns();
        this._renderTrades();
        this._renderRisk();
    }

    _renderSummary() {
        const { dailyPnL, wins, losses, avgRR, expectancy, currentDrawdown, maxDrawdown } = this.stats;
        const totalTrades = wins + losses + (this.stats.breakevens || 0);
        const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;

        // Daily P&L
        this.els.dailyPnL.textContent = this._formatCurrency(dailyPnL);
        this.els.dailyPnL.className = 'perf-card-value ' + 
            (dailyPnL > 0 ? 'perf-profit' : dailyPnL < 0 ? 'perf-loss' : '');
        
        const dailyPct = 2; // Assuming 2% daily limit
        this.els.dailyPct.textContent = `${((dailyPnL / 10000) * 100).toFixed(2)}%`; // Relative to account

        // Win Rate
        this.els.winRate.textContent = winRate.toFixed(1) + '%';
        this.els.winRate.className = 'perf-card-value ' + 
            (winRate >= 50 ? 'perf-profit' : 'perf-loss');
        this.els.winLoss.textContent = `${wins}W / ${losses}L`;

        // Avg R:R
        this.els.avgRR.textContent = avgRR.toFixed(2);
        this.els.expectancy.textContent = `Exp: ${expectancy >= 0 ? '+' : ''}${expectancy.toFixed(2)}R`;

        // Drawdown
        this.els.drawdown.textContent = currentDrawdown.toFixed(1) + '%';
        this.els.drawdown.className = 'perf-card-value perf-dd ' + 
            (currentDrawdown > 5 ? 'perf-loss' : currentDrawdown > 2 ? 'perf-warn' : '');
        this.els.maxDD.textContent = `Max: ${maxDrawdown.toFixed(1)}%`;
    }

    _renderChart() {
        const ctx = this.chartCtx;
        if (!ctx) return;

        ctx.clearRect(0, 0, this.chartWidth, this.chartHeight);

        // Filter by range
        let data = this.equityCurve;
        const now = Date.now();
        switch (this.chartRange) {
            case 'day':
                data = data.filter(d => now - d.time < 86400000);
                break;
            case 'week':
                data = data.filter(d => now - d.time < 604800000);
                break;
            case 'month':
                data = data.filter(d => now - d.time < 2592000000);
                break;
        }

        if (data.length < 2) {
            ctx.fillStyle = '#8b949e';
            ctx.font = '12px Consolas';
            ctx.textAlign = 'center';
            ctx.fillText('Not enough data', this.chartWidth / 2, this.chartHeight / 2);
            return;
        }

        // Calculate scales
        const values = data.map(d => d.value);
        const minVal = Math.min(0, ...values);
        const maxVal = Math.max(0, ...values);
        const range = maxVal - minVal || 1;
        const padding = 20;

        const xScale = (this.chartWidth - padding * 2) / (data.length - 1);
        const yScale = (this.chartHeight - padding * 2) / range;

        // Draw zero line
        const zeroY = this.chartHeight - padding - (0 - minVal) * yScale;
        ctx.strokeStyle = '#30363d';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(padding, zeroY);
        ctx.lineTo(this.chartWidth - padding, zeroY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw equity line
        ctx.strokeStyle = data[data.length - 1].value >= 0 ? this.options.colors.profit : this.options.colors.loss;
        ctx.lineWidth = 2;
        ctx.beginPath();

        data.forEach((point, i) => {
            const x = padding + i * xScale;
            const y = this.chartHeight - padding - (point.value - minVal) * yScale;
            
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });

        ctx.stroke();

        // Fill area
        const lastPoint = data[data.length - 1];
        const fillColor = lastPoint.value >= 0 
            ? 'rgba(63, 185, 80, 0.1)' 
            : 'rgba(248, 81, 73, 0.1)';
        
        ctx.fillStyle = fillColor;
        ctx.lineTo(this.chartWidth - padding, zeroY);
        ctx.lineTo(padding, zeroY);
        ctx.closePath();
        ctx.fill();
    }

    _renderPatterns() {
        const { byPattern } = this.stats;
        const patterns = Object.entries(byPattern);

        if (patterns.length === 0) {
            this.els.patterns.innerHTML = '<div class="perf-pattern-empty">No pattern data yet</div>';
            return;
        }

        const html = patterns.map(([name, data]) => {
            const winRate = data.trades > 0 ? (data.wins / data.trades) * 100 : 0;
            const pnlClass = data.pnl > 0 ? 'perf-profit' : data.pnl < 0 ? 'perf-loss' : '';

            return `
                <div class="perf-pattern-row">
                    <span class="perf-pattern-name">${name}</span>
                    <span class="perf-pattern-trades">${data.trades} trades</span>
                    <span class="perf-pattern-winrate">${winRate.toFixed(0)}%</span>
                    <span class="perf-pattern-pnl ${pnlClass}">${this._formatCurrency(data.pnl)}</span>
                </div>
            `;
        }).join('');

        this.els.patterns.innerHTML = html;
    }

    _renderTrades() {
        const recentTrades = this.trades.slice(0, 20);

        if (recentTrades.length === 0) {
            this.els.tradesTbody.innerHTML = `
                <tr class="perf-empty-row">
                    <td colspan="8">No trades recorded</td>
                </tr>
            `;
            return;
        }

        const html = recentTrades.map(trade => {
            const pnlClass = trade.pnl > 0 ? 'perf-profit' : trade.pnl < 0 ? 'perf-loss' : 'perf-be';
            const rMultiple = trade.rMultiple || (trade.pnl / (trade.risk || 1));

            return `
                <tr class="perf-trade-row ${pnlClass}">
                    <td>${this._formatTime(trade.timestamp)}</td>
                    <td>${trade.symbol || '--'}</td>
                    <td class="${trade.side === 'long' ? 'perf-profit' : 'perf-loss'}">${trade.side?.toUpperCase() || '--'}</td>
                    <td>${trade.pattern || '--'}</td>
                    <td>${this._formatPrice(trade.entry)}</td>
                    <td>${this._formatPrice(trade.exit)}</td>
                    <td class="${pnlClass}">${this._formatCurrency(trade.pnl)}</td>
                    <td>${rMultiple >= 0 ? '+' : ''}${rMultiple.toFixed(1)}R</td>
                </tr>
            `;
        }).join('');

        this.els.tradesTbody.innerHTML = html;
    }

    _renderRisk() {
        const { dailyPnL, tradesToday } = this.stats;
        const dailyLimit = 2; // 2% daily loss limit
        const accountValue = 10000; // Placeholder
        const maxDailyLoss = accountValue * (dailyLimit / 100);
        
        const usedPct = dailyPnL < 0 ? Math.min(100, (Math.abs(dailyPnL) / maxDailyLoss) * 100) : 0;
        
        this.els.riskFill.style.width = usedPct + '%';
        this.els.riskFill.className = 'perf-risk-fill ' + 
            (usedPct > 80 ? 'perf-risk-danger' : usedPct > 50 ? 'perf-risk-warning' : '');
        
        this.els.riskPct.textContent = usedPct.toFixed(0) + '% used';
        this.els.tradesToday.textContent = `${tradesToday || 0} / 8`;

        // Risk status badge
        const canTrade = usedPct < 100;
        this.els.riskStatus.innerHTML = canTrade 
            ? '<span class="perf-risk-badge perf-risk-ok">✓ Trading Allowed</span>'
            : '<span class="perf-risk-badge perf-risk-stop">✕ Daily Limit Reached</span>';
    }

    _formatCurrency(value) {
        const sign = value >= 0 ? '+' : '';
        return sign + '$' + Math.abs(value).toFixed(2);
    }

    _formatPrice(price) {
        if (!price) return '--';
        if (price >= 1000) return price.toFixed(1);
        if (price >= 1) return price.toFixed(2);
        return price.toFixed(4);
    }

    _formatTime(timestamp) {
        if (!timestamp) return '--';
        return new Date(timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }

    _exportCSV() {
        const headers = ['Time', 'Symbol', 'Side', 'Pattern', 'Entry', 'Exit', 'P&L', 'R Multiple'];
        const rows = this.trades.map(t => [
            new Date(t.timestamp).toISOString(),
            t.symbol,
            t.side,
            t.pattern,
            t.entry,
            t.exit,
            t.pnl,
            t.rMultiple
        ]);

        const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `trades_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        
        URL.revokeObjectURL(url);
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in main app
window.PerformanceDashboard = PerformanceDashboard;
