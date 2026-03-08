/**
 * Time & Sales Tape Component
 * Live scrolling trade prints with big trade highlighting
 */

class TimeAndSales {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            maxTrades: 100,          // Max trades to keep in memory
            displayTrades: 50,       // Max trades to display
            bigTradeThreshold: 20,   // Contracts to highlight as big trade
            autoScroll: true,
            showAggressor: true,
            colors: {
                background: '#1c2128',
                buy: '#3fb950',
                sell: '#f85149',
                neutral: '#8b949e',
                bigTrade: '#d29922',
                text: '#e6edf3',
                textMuted: '#6e7681',
                ...options.colors
            },
            ...options
        };

        this.trades = [];
        this.cumulativeVolume = { buy: 0, sell: 0 };
        this.paused = false;
        
        this._init();
    }

    _init() {
        this.container.innerHTML = `
            <div class="tape-container">
                <div class="tape-header">
                    <div class="tape-controls">
                        <label class="tape-filter">
                            <span>Min Size:</span>
                            <input type="number" id="tapeMinSize" value="1" min="1" class="tape-input">
                        </label>
                        <label class="tape-filter">
                            <span>Side:</span>
                            <select id="tapeSideFilter" class="tape-select">
                                <option value="all">All</option>
                                <option value="buy">Buys</option>
                                <option value="sell">Sells</option>
                            </select>
                        </label>
                        <button id="tapeAutoScroll" class="tape-btn active" title="Auto-scroll">
                            <span class="tape-btn-icon">↓</span>
                        </button>
                        <button id="tapeClear" class="tape-btn" title="Clear tape">
                            <span class="tape-btn-icon">⌫</span>
                        </button>
                    </div>
                </div>
                <div class="tape-body" id="tapeBody">
                    <table class="tape-table">
                        <thead>
                            <tr>
                                <th>TIME</th>
                                <th>PRICE</th>
                                <th>SIZE</th>
                                <th>SIDE</th>
                            </tr>
                        </thead>
                        <tbody id="tapeTbody"></tbody>
                    </table>
                </div>
                <div class="tape-footer">
                    <div class="tape-volume-meter">
                        <div class="tape-vol-bar tape-vol-buy" id="tapeVolBuy"></div>
                        <div class="tape-vol-bar tape-vol-sell" id="tapeVolSell"></div>
                    </div>
                    <div class="tape-stats">
                        <span class="tape-stat tape-buy">
                            <span class="tape-stat-label">Buy Vol:</span>
                            <span id="tapeBuyVol">0</span>
                        </span>
                        <span class="tape-stat tape-sell">
                            <span class="tape-stat-label">Sell Vol:</span>
                            <span id="tapeSellVol">0</span>
                        </span>
                        <span class="tape-stat">
                            <span class="tape-stat-label">Trades:</span>
                            <span id="tapeTradeCount">0</span>
                        </span>
                    </div>
                </div>
            </div>
        `;

        this.tbody = document.getElementById('tapeTbody');
        this.bodyEl = document.getElementById('tapeBody');
        this.buyVolEl = document.getElementById('tapeBuyVol');
        this.sellVolEl = document.getElementById('tapeSellVol');
        this.tradeCountEl = document.getElementById('tapeTradeCount');
        this.volBuyBar = document.getElementById('tapeVolBuy');
        this.volSellBar = document.getElementById('tapeVolSell');

        // Wire up controls
        this._initControls();
    }

    _initControls() {
        // Auto-scroll toggle
        const autoScrollBtn = document.getElementById('tapeAutoScroll');
        autoScrollBtn.addEventListener('click', () => {
            this.options.autoScroll = !this.options.autoScroll;
            autoScrollBtn.classList.toggle('active', this.options.autoScroll);
        });

        // Clear button
        document.getElementById('tapeClear').addEventListener('click', () => {
            this.clear();
        });

        // Min size filter
        document.getElementById('tapeMinSize').addEventListener('change', (e) => {
            this.options.minSizeFilter = parseInt(e.target.value) || 1;
            this._renderTrades();
        });

        // Side filter
        document.getElementById('tapeSideFilter').addEventListener('change', (e) => {
            this.options.sideFilter = e.target.value;
            this._renderTrades();
        });

        this.options.minSizeFilter = 1;
        this.options.sideFilter = 'all';
    }

    /**
     * Add a new trade
     * @param {Object} trade - { price, size, side, time, aggressor }
     */
    addTrade(trade) {
        if (!trade || !trade.price || !trade.size) return;

        const normalizedTrade = {
            price: trade.price,
            size: trade.size,
            side: trade.side || (trade.aggressor === 'buy' ? 'buy' : 'sell'),
            time: trade.time || Date.now(),
            aggressor: trade.aggressor || trade.side,
            isBig: trade.size >= this.options.bigTradeThreshold
        };

        // Add to front of array
        this.trades.unshift(normalizedTrade);

        // Trim to max
        if (this.trades.length > this.options.maxTrades) {
            this.trades = this.trades.slice(0, this.options.maxTrades);
        }

        // Update cumulative volume
        if (normalizedTrade.side === 'buy') {
            this.cumulativeVolume.buy += normalizedTrade.size;
        } else {
            this.cumulativeVolume.sell += normalizedTrade.size;
        }

        this._renderTrades();
    }

    /**
     * Add multiple trades at once
     */
    addTrades(trades) {
        if (!Array.isArray(trades)) return;
        trades.forEach(t => this.addTrade(t));
    }

    /**
     * Update big trade threshold dynamically
     */
    setBigTradeThreshold(threshold) {
        this.options.bigTradeThreshold = threshold;
        // Re-tag existing trades
        this.trades.forEach(t => {
            t.isBig = t.size >= threshold;
        });
        this._renderTrades();
    }

    clear() {
        this.trades = [];
        this.cumulativeVolume = { buy: 0, sell: 0 };
        this._renderTrades();
    }

    _renderTrades() {
        // Filter trades
        let filteredTrades = this.trades.filter(t => {
            if (t.size < this.options.minSizeFilter) return false;
            if (this.options.sideFilter !== 'all' && t.side !== this.options.sideFilter) return false;
            return true;
        });

        // Limit display
        filteredTrades = filteredTrades.slice(0, this.options.displayTrades);

        // Generate HTML
        let html = '';
        filteredTrades.forEach(trade => {
            const sideClass = trade.side === 'buy' ? 'tape-row-buy' : 'tape-row-sell';
            const bigClass = trade.isBig ? 'tape-row-big' : '';
            const time = this._formatTime(trade.time);
            
            html += `
                <tr class="tape-row ${sideClass} ${bigClass}">
                    <td class="tape-time">${time}</td>
                    <td class="tape-price">${this._formatPrice(trade.price)}</td>
                    <td class="tape-size">${this._formatSize(trade.size)}</td>
                    <td class="tape-side">
                        <span class="tape-side-badge ${trade.side}">${trade.side.toUpperCase()}</span>
                    </td>
                </tr>
            `;
        });

        this.tbody.innerHTML = html;

        // Update stats
        this._updateStats();

        // Auto-scroll to top (newest trades)
        if (this.options.autoScroll && this.bodyEl) {
            this.bodyEl.scrollTop = 0;
        }
    }

    _updateStats() {
        const buyVol = this.cumulativeVolume.buy;
        const sellVol = this.cumulativeVolume.sell;
        const totalVol = buyVol + sellVol;

        this.buyVolEl.textContent = this._formatSize(buyVol);
        this.sellVolEl.textContent = this._formatSize(sellVol);
        this.tradeCountEl.textContent = this.trades.length.toString();

        // Volume meter bars
        const buyPct = totalVol > 0 ? (buyVol / totalVol) * 100 : 50;
        this.volBuyBar.style.width = buyPct + '%';
        this.volSellBar.style.width = (100 - buyPct) + '%';
    }

    _formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            hour12: false 
        });
    }

    _formatPrice(price) {
        if (price >= 1000) return price.toFixed(1);
        if (price >= 1) return price.toFixed(2);
        return price.toFixed(4);
    }

    _formatSize(size) {
        if (size >= 1000000) return (size / 1000000).toFixed(2) + 'M';
        if (size >= 1000) return (size / 1000).toFixed(1) + 'K';
        return Math.round(size).toString();
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in main app
window.TimeAndSales = TimeAndSales;
