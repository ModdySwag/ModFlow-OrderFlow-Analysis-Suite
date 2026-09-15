/**
 * Orderbook Depth Ladder Component
 * Real-time DOM (Depth of Market) ladder display
 * Shows bid/ask sizes with imbalance highlighting
 */

class OrderbookLadder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            levels: 20,              // Number of price levels to show
            priceStep: 0.5,          // Tick size
            updateThrottle: 100,     // ms between renders
            colors: {
                background: '#1c2128',
                bidBar: '#3fb950',
                askBar: '#f85149',
                bidText: '#3fb950',
                askText: '#f85149',
                priceText: '#e6edf3',
                currentPrice: '#58a6ff',
                thinLevel: '#d29922',
                gridLine: '#30363d',
                imbalanceBid: 'rgba(63, 185, 80, 0.3)',
                imbalanceAsk: 'rgba(248, 81, 73, 0.3)',
                ...options.colors
            },
            ...options
        };

        this.bids = [];           // [ {price, size} ]
        this.asks = [];           // [ {price, size} ]
        this.currentPrice = null;
        this.lastTrade = null;
        this.thinLevels = [];     // Price levels with thin liquidity (sweep targets)
        this.maxSize = 0;         // For bar normalization
        
        this._lastRender = 0;
        this._pendingRender = false;
        
        this._init();
    }

    _init() {
        this.container.innerHTML = `
            <div class="ob-ladder">
                <div class="ob-header">
                    <span class="ob-col-bid">BID SIZE</span>
                    <span class="ob-col-price">PRICE</span>
                    <span class="ob-col-ask">ASK SIZE</span>
                </div>
                <div class="ob-body" id="obLadderBody"></div>
                <div class="ob-footer">
                    <div class="ob-imbalance-gauge">
                        <div class="ob-imb-bar" id="obImbBar"></div>
                    </div>
                    <div class="ob-stats">
                        <span class="ob-stat">
                            <span class="ob-stat-label">Bid Total:</span>
                            <span class="ob-stat-value ob-bid" id="obBidTotal">--</span>
                        </span>
                        <span class="ob-stat">
                            <span class="ob-stat-label">Ask Total:</span>
                            <span class="ob-stat-value ob-ask" id="obAskTotal">--</span>
                        </span>
                        <span class="ob-stat">
                            <span class="ob-stat-label">Ratio:</span>
                            <span class="ob-stat-value" id="obRatio">--</span>
                        </span>
                    </div>
                </div>
            </div>
        `;
        
        this.bodyEl = document.getElementById('obLadderBody');
        this.imbBarEl = document.getElementById('obImbBar');
        this.bidTotalEl = document.getElementById('obBidTotal');
        this.askTotalEl = document.getElementById('obAskTotal');
        this.ratioEl = document.getElementById('obRatio');
    }

    /**
     * Normalise one level list to {price, size}.
     *
     * The engine's REST payload sends `{price, quantity}` (app.py), the demo fixtures and the
     * WebSocket deltas use `{price, size}`. Reading only `.size` left this ladder with no
     * sizes at all against the live feed: empty size cells, zero-width bars and a NaN footer.
     * Arrays (`[price, size]`) are accepted too, so a shape change upstream degrades to a
     * readable ladder instead of a silently empty one.
     */
    _levels(list) {
        const out = [];
        for (const level of list || []) {
            if (Array.isArray(level)) {
                const price = Number(level[0]);
                const size = Number(level[1]);
                if (Number.isFinite(price) && Number.isFinite(size)) out.push({ price, size });
                continue;
            }
            const price = Number(level && level.price);
            const size = Number(level && (level.size !== undefined ? level.size : level.quantity));
            if (Number.isFinite(price) && Number.isFinite(size)) out.push({ price, size });
        }
        return out;
    }

    /**
     * Update full orderbook snapshot
     * @param {Object} data - { bids: [{price, size|quantity}], asks: [...], currentPrice }
     */
    setData(data) {
        if (!data) return;
        
        this.bids = this._levels(data.bids);
        this.asks = this._levels(data.asks);
        this.currentPrice = data.currentPrice || data.last_price || null;
        
        // Sort: bids descending, asks ascending
        this.bids.sort((a, b) => b.price - a.price);
        this.asks.sort((a, b) => a.price - b.price);
        
        // Calculate max size for normalization
        this._calculateMaxSize();
        
        // Detect thin levels
        this._detectThinLevels();
        
        this._scheduleRender();
    }

    /**
     * Update single level (real-time delta)
     */
    updateLevel(side, price, size) {
        const p = Number(price);
        const q = Number(size);
        if (!Number.isFinite(p) || !Number.isFinite(q)) return;   // a malformed delta must not poison the book
        price = p;
        size = q;
        const levels = side === 'bid' ? this.bids : this.asks;
        const idx = levels.findIndex(l => l.price === price);
        
        if (size === 0) {
            // Remove level
            if (idx >= 0) levels.splice(idx, 1);
        } else if (idx >= 0) {
            // Update existing
            levels[idx].size = size;
        } else {
            // Insert new level
            levels.push({ price, size });
            if (side === 'bid') {
                this.bids.sort((a, b) => b.price - a.price);
            } else {
                this.asks.sort((a, b) => a.price - b.price);
            }
        }
        
        this._calculateMaxSize();
        this._scheduleRender();
    }

    /**
     * Update current price (from trade)
     */
    updatePrice(price, side = null) {
        this.currentPrice = price;
        this.lastTrade = { price, side, time: Date.now() };
        this._scheduleRender();
    }

    _calculateMaxSize() {
        const allSizes = [
            ...this.bids.slice(0, this.options.levels).map(l => l.size),
            ...this.asks.slice(0, this.options.levels).map(l => l.size)
        ];
        this.maxSize = Math.max(...allSizes, 1);
    }

    _detectThinLevels() {
        // Find levels with significantly lower liquidity (sweep targets)
        const allLevels = [
            ...this.bids.slice(0, this.options.levels),
            ...this.asks.slice(0, this.options.levels)
        ];
        
        if (allLevels.length < 3) return;
        
        const avgSize = allLevels.reduce((s, l) => s + l.size, 0) / allLevels.length;
        const thinThreshold = avgSize * 0.3;
        
        this.thinLevels = allLevels
            .filter(l => l.size < thinThreshold)
            .map(l => l.price);
    }

    _scheduleRender() {
        if (this._pendingRender) return;
        
        const now = Date.now();
        const elapsed = now - this._lastRender;
        
        if (elapsed >= this.options.updateThrottle) {
            this._render();
        } else {
            this._pendingRender = true;
            setTimeout(() => {
                this._pendingRender = false;
                this._render();
            }, this.options.updateThrottle - elapsed);
        }
    }

    _render() {
        this._lastRender = Date.now();
        
        if (!this.bodyEl) return;
        
        // Build unified price ladder centered on current price
        const levels = this._buildLadder();
        
        // Generate HTML
        let html = '';
        levels.forEach(level => {
            const isCurrent = level.price === this.currentPrice;
            const isThin = this.thinLevels.includes(level.price);
            const bidPct = level.bidSize ? (level.bidSize / this.maxSize) * 100 : 0;
            const askPct = level.askSize ? (level.askSize / this.maxSize) * 100 : 0;
            
            // Imbalance detection
            const hasImbalance = level.bidSize && level.askSize && 
                (level.bidSize > level.askSize * 3 || level.askSize > level.bidSize * 3);
            const imbClass = hasImbalance 
                ? (level.bidSize > level.askSize ? 'ob-imb-bid' : 'ob-imb-ask') 
                : '';
            
            html += `
                <div class="ob-row ${isCurrent ? 'ob-current' : ''} ${isThin ? 'ob-thin' : ''} ${imbClass}">
                    <div class="ob-cell ob-bid-cell">
                        ${level.bidSize ? `
                            <div class="ob-bar ob-bid-bar" style="width: ${bidPct}%"></div>
                            <span class="ob-size ob-bid">${this._formatSize(level.bidSize)}</span>
                        ` : ''}
                    </div>
                    <div class="ob-cell ob-price-cell ${isCurrent ? 'ob-price-current' : ''}">
                        ${this._formatPrice(level.price)}
                    </div>
                    <div class="ob-cell ob-ask-cell">
                        ${level.askSize ? `
                            <div class="ob-bar ob-ask-bar" style="width: ${askPct}%"></div>
                            <span class="ob-size ob-ask">${this._formatSize(level.askSize)}</span>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        
        this.bodyEl.innerHTML = html;
        
        // Update stats
        this._updateStats();
        
        // Scroll to center on current price
        this._scrollToCurrentPrice();
    }

    _buildLadder() {
        const levels = [];
        const numLevels = this.options.levels;
        const step = this.options.priceStep;
        
        // Get all prices we have data for
        const bidMap = new Map(this.bids.map(b => [b.price, b.size]));
        const askMap = new Map(this.asks.map(a => [a.price, a.size]));
        
        // Determine center price
        const centerPrice = this.currentPrice || 
            (this.bids.length > 0 && this.asks.length > 0 
                ? (this.bids[0].price + this.asks[0].price) / 2 
                : 0);
        
        if (centerPrice === 0) return levels;
        
        // Build ladder around center price
        const halfLevels = Math.floor(numLevels / 2);
        
        for (let i = halfLevels; i >= -halfLevels; i--) {
            const price = this._roundPrice(centerPrice + i * step);
            levels.push({
                price,
                bidSize: bidMap.get(price) || 0,
                askSize: askMap.get(price) || 0
            });
        }
        
        return levels;
    }

    _roundPrice(price) {
        const step = this.options.priceStep;
        return Math.round(price / step) * step;
    }

    _updateStats() {
        const bidTotal = this.bids.slice(0, this.options.levels).reduce((s, l) => s + l.size, 0);
        const askTotal = this.asks.slice(0, this.options.levels).reduce((s, l) => s + l.size, 0);
        const ratio = askTotal > 0 ? bidTotal / askTotal : 0;
        
        this.bidTotalEl.textContent = this._formatSize(bidTotal);
        this.askTotalEl.textContent = this._formatSize(askTotal);
        this.ratioEl.textContent = ratio.toFixed(2) + 'x';
        this.ratioEl.className = 'ob-stat-value ' + (ratio > 1.2 ? 'ob-bid' : ratio < 0.8 ? 'ob-ask' : '');
        
        // Imbalance gauge
        const total = bidTotal + askTotal;
        const bidPct = total > 0 ? (bidTotal / total) * 100 : 50;
        this.imbBarEl.style.width = bidPct + '%';
        this.imbBarEl.className = 'ob-imb-bar ' + (bidPct > 55 ? 'ob-imb-bid' : bidPct < 45 ? 'ob-imb-ask' : '');
    }

    _scrollToCurrentPrice() {
        /* One scroll per price change, not one per repaint: a smooth scroll issued on every
           throttled render (10/s) queues animations against each other, forces layout each
           time, and drags the ladder back under a user who is scrolling it by hand. */
        if (!this.currentPrice || !this.bodyEl) return;
        if (this._centeredPrice === this.currentPrice) return;
        this._centeredPrice = this.currentPrice;

        const currentRow = this.bodyEl.querySelector('.ob-current');
        if (currentRow) {
            currentRow.scrollIntoView({ block: 'center' });
        }
    }

    _formatPrice(price) {
        if (price >= 1000) return price.toFixed(1);
        if (price >= 1) return price.toFixed(2);
        return price.toFixed(4);
    }

    _formatSize(size) {
        if (size >= 1000000) return (size / 1000000).toFixed(2) + 'M';
        if (size >= 1000) return (size / 1000).toFixed(1) + 'K';
        if (size >= 1) return size.toFixed(0);
        /* Crypto book levels are fractions of a coin: Math.round() showed them all as "0". */
        if (size >= 0.01) return size.toFixed(3);
        return Number(size).toPrecision(2);
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in main app
window.OrderbookLadder = OrderbookLadder;
