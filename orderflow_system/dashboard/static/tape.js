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
        this._timeCache = new Map();     // second -> formatted clock time (see _timeText)
        this._topPrice = null;           // the newest price on screen (the changed-digit reference)
        
        this._init();
    }

    _init() {
        this.container.innerHTML = `
            <div class="tape-container">
                <div class="tape-header">
                    <div class="tape-controls">
                        <label class="tape-filter">
                            <span>Min Size:</span>
                            <input type="number" id="tapeMinSize" value="0" min="0" step="any" class="tape-input" title="Hide prints smaller than this. 0 shows every print the venue sends — on crypto feeds most prints are fractions of a coin, so a floor of 1 hides almost all of them.">
                        </label>
                        <label class="tape-filter">
                            <span>Side:</span>
                            <select id="tapeSideFilter" class="tape-select">
                                <option value="all">All</option>
                                <option value="buy">Buys</option>
                                <option value="sell">Sells</option>
                            </select>
                        </label>
                        <button id="tapeAutoScroll" class="tape-btn active" title="Follow the newest prints as they arrive">
                            <span class="tape-btn-icon">↓</span>
                        </button>
                        <button id="tapeClear" class="tape-btn" title="Clear the prints shown here (stored ticks stay on disk)">
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
        /* The spine: hovering a print publishes it, and the shared cursor marks the prints at its
           level. The badge sits in the header beside the controls. */
        if (this.tbody && this.tbody.addEventListener) {
            this.tbody.addEventListener('mouseover', (ev) => {
                const tr = ev.target && ev.target.closest ? ev.target.closest('tr[data-price]') : null;
                if (!tr || !window.OFAPCURSOR) return;
                const price = Number(tr.getAttribute('data-price'));
                const time = Number(tr.getAttribute('data-time'));
                OFAPCURSOR.move(price, Number.isFinite(time) ? time : null, 'tape');
            });
        }
        if (this.container && this.container.addEventListener) {
            this.container.addEventListener('mouseleave', () => {
                if (window.OFAPCURSOR) OFAPCURSOR.clear('tape');
            });
        }
        if (window.OFAPCURSOR) {
            OFAPCURSOR.subscribe(() => this.applyCursor());
            OFAPCURSOR.badge(this.container.querySelector('.tape-header') || this.container);
        }

        autoScrollBtn.addEventListener('click', () => {
            this.options.autoScroll = !this.options.autoScroll;
            autoScrollBtn.classList.toggle('active', this.options.autoScroll);
            this._applyAnchoring();
        });

        // Clear button
        document.getElementById('tapeClear').addEventListener('click', () => {
            this.clear();
        });

        // Min size filter
        document.getElementById('tapeMinSize').addEventListener('change', (e) => {
            /* 0 means "every print". The old `parseInt(v) || 1` made 0 falsy and silently restored a
               floor of 1, which on a crypto feed hides essentially the whole tape. */
            const wanted = Number(e.target.value);
            this.options.minSizeFilter = Number.isFinite(wanted) && wanted > 0 ? wanted : 0;
            this._renderTrades();
        });

        // Side filter
        document.getElementById('tapeSideFilter').addEventListener('change', (e) => {
            this.options.sideFilter = e.target.value;
            this._renderTrades();
        });

        this.options.minSizeFilter = 0;      // start by showing the real tape, then let the operator filter
        this.options.sideFilter = 'all';
        this._applyAnchoring();
    }

    /* ── live path: one row in, one row out ──────────────────────────────────
       This strip used to rebuild its whole table per print (innerHTML with up to
       `displayTrades` rows) and re-format every timestamp with toLocaleTimeString:
       measured 3.9 ms per print at 100 rows, so a busy tape dropped frames, and the
       120-row reload when the view opened froze the UI for about half a second. The
       live path now appends the new row, trims the tail, and formats each second once. */

    _normalize(trade) {
        if (!trade || !trade.price || !trade.size) return null;
        return {
            price: trade.price,
            size: trade.size,
            side: trade.side || (trade.aggressor === 'buy' ? 'buy' : 'sell'),
            time: trade.time || Date.now(),
            aggressor: trade.aggressor || trade.side,
            isBig: trade.size >= this.options.bigTradeThreshold,
        };
    }

    _visible(trade) {
        if (trade.size < this.options.minSizeFilter) return false;
        if (this.options.sideFilter !== 'all' && trade.side !== this.options.sideFilter) return false;
        return true;
    }

    /* The shared cursor's mark: the tape is a price + time stream, so "at this price" is a class on
       the rows that traded there — applied at build time and re-applied whenever the cursor moves. */
    _cursorTol() {
        const p = Math.abs((window.OFAPCURSOR && OFAPCURSOR.state.price) || 0);
        return p >= 1000 ? 0.5 : p >= 1 ? 0.01 : 0.0005;
    }

    _cursorClass(price) {
        const cur = (window.OFAPCURSOR && OFAPCURSOR.state) ? OFAPCURSOR.state.price : null;
        if (cur == null) return '';
        return Math.abs(Number(price) - cur) <= this._cursorTol() ? 'ofap-cursor-row' : '';
    }

    /* Re-apply the mark over the rows on screen; rows are rebuilt wholesale, so a class painted once
       would be gone by the next print. Skips the pass when the cursor's level has not changed. */
    applyCursor() {
        if (!this.tbody) return false;
        const cur = (window.OFAPCURSOR && OFAPCURSOR.state) ? OFAPCURSOR.state.price : null;
        const tol = this._cursorTol();
        const key = cur == null ? null : Math.round(cur / tol);
        if (key === this._cursorApplied) return false;
        this._cursorApplied = key;
        const rows = this.tbody.querySelectorAll('tr[data-price]');
        for (const tr of rows) {
            const p = Number(tr.getAttribute('data-price'));
            tr.classList.toggle('ofap-cursor-row', cur != null && Math.abs(p - cur) <= tol);
        }
        return true;
    }

    _rowHtml(trade, referencePrice) {
        const sideClass = trade.side === 'buy' ? 'tape-row-buy' : 'tape-row-sell';
        const bigClass = trade.isBig ? 'tape-row-big' : '';
        const cursorClass = this._cursorClass(trade.price);
        return `
                <tr class="tape-row ${sideClass} ${bigClass} ${cursorClass}" data-price="${trade.price}" data-time="${trade.time}">
                    <td class="tape-time">${this._timeText(trade.time)}</td>
                    <td class="tape-price">${this._priceHtml(trade.price, referencePrice)}</td>
                    <td class="tape-size">${this._formatSize(trade.size)}</td>
                    <td class="tape-side">
                        <span class="tape-side-badge ${trade.side}">${trade.side.toUpperCase()}</span>
                    </td>
                </tr>
            `;
    }

    /* The changed-digit tint — how a professional tape is actually read: not the number, the
       MOVEMENT. Only the digits that differ from the print before it are wrapped, so a screen of
       figures becomes a column of movement without any extra glyphs or width. The reference is the
       older neighbour (the row below); the first row of a batch compares against the print that was
       at the top before it, and a width change (100.0 → 99.75) is left plain — a different number of
       digits says nothing about which digit moved. */
    _priceHtml(price, reference) {
        const text = this._formatPrice(price);
        if (reference === null || reference === undefined) return text;
        const prev = this._formatPrice(reference);
        if (prev.length !== text.length) return text;
        let out = '';
        for (let i = 0; i < text.length; i += 1) {
            out += (text[i] !== prev[i] && text[i] >= '0' && text[i] <= '9')
                ? `<span class="tape-digit-changed">${text[i]}</span>`
                : text[i];
        }
        return out;
    }

    /* A tape repeats the same second many times and toLocaleTimeString is the most expensive
       call in this renderer, so each second is formatted once and cached (bounded). */
    _timeText(timestamp) {
        const sec = Math.floor((timestamp || Date.now()) / 1000);
        const hit = this._timeCache.get(sec);
        if (hit !== undefined) return hit;
        const text = new Date(sec * 1000).toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
        });
        if (this._timeCache.size > 900) this._timeCache.clear();
        this._timeCache.set(sec, text);
        return text;
    }

    _trimRows() {
        const max = this.options.displayTrades;
        while (this.tbody.childElementCount > max && this.tbody.lastElementChild) {
            this.tbody.removeChild(this.tbody.lastElementChild);
        }
    }

    /**
     * @returns {number} the height (px) of the rows just inserted, so the caller can hold a
     *                   reader's view: rows are uniform, so one measured row height is enough and
     *                   the trim below cannot distort it.
     */
    _prependRows(trades, tailPrice) {
        let html = '';
        let rows = 0;
        /* The batch is newest-first, so each row's older neighbour is the NEXT one in the batch; the
           last row of the batch neighbours whatever was at the top before it (tailPrice), which is
           what makes the changed-digit tint continuous across two batches. */
        for (let i = 0; i < trades.length; i += 1) {
            const trade = trades[i];
            if (!this._visible(trade)) continue;
            const older = i + 1 < trades.length ? trades[i + 1].price : tailPrice;
            html += this._rowHtml(trade, older);
            rows += 1;
        }
        if (!html) return 0;
        this.tbody.insertAdjacentHTML('afterbegin', html);
        this._topPrice = trades.length ? trades[0].price : this._topPrice;
        const rowH = this.tbody.firstElementChild ? this.tbody.firstElementChild.offsetHeight : 0;
        this._trimRows();
        return rows * rowH;
    }

    _afterAppend(added) {
        this._updateStats();
        if (!this.bodyEl) return;
        if (window.OFAPSTRIPS && OFAPSTRIPS.holds && OFAPSTRIPS.holds(this.bodyEl)) {
            /* A reader parked here (a keystroke, a scroll, a paused hover): the strip owns the offset
               until they return, and its chip is the way back. Pinning to 0 would yank the row they
               are reading out from under them - the exact jump this widget already learned to avoid. */
        } else if (this.options.autoScroll) {
            this.bodyEl.scrollTop = 0;                       // pinned to the newest print
        } else {
            this.bodyEl.scrollTop += added || 0;             // hold the reader's lines where they are
        }
    }

    /**
     * Who owns the scroll offset while rows arrive above the reader: this widget does, in both
     * modes (see _applyAnchoring). Pinned mode puts the newest print at the top; reader mode adds
     * the height of the inserted rows back onto the offset, which is what keeps the lines the reader
     * is looking at in place while the tape keeps filling.
     */
    _applyAnchoring() {
        /* Off in both modes: the widget owns this offset. Scroll anchoring compensates for rows
           inserted above by pushing the offset down, and a capping tape adds and removes rows one for
           one, so the height never grows and the compensation accumulates until the strip reaches the
           end of its range - measured with a wrapped scrollTop setter: 200 -> 726 in 25 s with no
           JavaScript writer involved, while the reader's lines slid away underneath. */
        if (this.bodyEl) this.bodyEl.style.overflowAnchor = 'none';
    }

    /**
     * Add a new trade
     * @param {Object} trade - { price, size, side, time, aggressor }
     */
    addTrade(trade) {
        const normalizedTrade = this._normalize(trade);
        if (!normalizedTrade) return;

        this.trades.unshift(normalizedTrade);
        if (this.trades.length > this.options.maxTrades) this.trades.length = this.options.maxTrades;

        if (normalizedTrade.side === 'buy') this.cumulativeVolume.buy += normalizedTrade.size;
        else this.cumulativeVolume.sell += normalizedTrade.size;

        this._afterAppend(this._prependRows([normalizedTrade], this._topPrice));
    }

    /**
     * Add multiple trades at once
     * @param {Array} trades - oldest first (as /api/tape returns them); the batch is
     *                         reversed onto the head of the list and inserted in one pass
     */
    addTrades(trades) {
        if (!Array.isArray(trades) || !trades.length) return;
        const batch = [];
        for (const t of trades) {
            const n = this._normalize(t);
            if (!n) continue;
            batch.push(n);
            if (n.side === 'buy') this.cumulativeVolume.buy += n.size;
            else this.cumulativeVolume.sell += n.size;
        }
        if (!batch.length) return;
        const newestFirst = batch.slice().reverse();
        const tail = this._topPrice;                 // the print this batch sits on top of
        this.trades = newestFirst.concat(this.trades);
        if (this.trades.length > this.options.maxTrades) this.trades.length = this.options.maxTrades;
        this._afterAppend(this._prependRows(newestFirst, tail));
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

    /* Full rebuild — filter changes, clear, threshold changes only. The live path never
       calls this: it is the O(displayTrades) path, not the O(1)-per-print one. */
    _renderTrades() {
        const max = this.options.displayTrades;
        const visible = [];
        for (const trade of this.trades) {
            if (!this._visible(trade)) continue;
            visible.push(trade);
            if (visible.length >= max) break;
        }
        let html = '';
        for (let i = 0; i < visible.length; i += 1) {
            const older = i + 1 < visible.length ? visible[i + 1].price : null;
            html += this._rowHtml(visible[i], older);
        }
        this.tbody.innerHTML = html;
        this._topPrice = visible.length ? visible[0].price : null;
        this._updateStats();
        const parked = window.OFAPSTRIPS && OFAPSTRIPS.holds && OFAPSTRIPS.holds(this.bodyEl);
        if (this.options.autoScroll && this.bodyEl && !parked) this.bodyEl.scrollTop = 0;
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

    _formatPrice(price) {
        if (price >= 1000) return price.toFixed(1);
        if (price >= 1) return price.toFixed(2);
        return price.toFixed(4);
    }

    _formatSize(size) {
        if (size >= 1000000) return (size / 1000000).toFixed(2) + 'M';
        if (size >= 1000) return (size / 1000).toFixed(1) + 'K';
        if (size >= 1) return size.toFixed(0);
        /* Crypto prints are fractions of a coin: Math.round() rendered every live print as "0",
           which reads as a broken tape rather than as a small size. */
        if (size >= 0.01) return size.toFixed(3);
        return Number(size).toPrecision(2);
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in main app
window.TimeAndSales = TimeAndSales;
