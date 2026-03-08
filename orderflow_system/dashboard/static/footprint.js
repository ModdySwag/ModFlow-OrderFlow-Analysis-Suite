/**
 * Footprint Chart Component — TradingView-Style
 * Drag to pan, scroll to zoom, crosshair cursor, smooth canvas rendering
 * Bid/Ask volume heatmap at each price level per candle bar
 */

class FootprintChart {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.canvas = null;
        this.ctx = null;
        this.tooltip = null;
        this.crosshairCanvas = null;
        this.crosshairCtx = null;

        this.options = {
            barWidth: 90,
            rowHeight: 17,
            priceStep: 0.5,
            imbalanceThreshold: 3,
            absorptionThreshold: 2,
            minBarWidth: 30,
            maxBarWidth: 200,
            timeAxisHeight: 22,
            priceAxisWidth: 68,
            colors: {
                background: '#1c2128',
                gridLine: '#30363d',
                gridLineLight: 'rgba(48,54,61,0.4)',
                bidCell: '#3fb950',
                askCell: '#f85149',
                bidText: '#e6edf3',
                askText: '#e6edf3',
                pocMarker: '#58a6ff',
                imbalance: '#d29922',
                absorption: '#bc8cff',
                priceLevel: '#8b949e',
                crosshair: 'rgba(88,166,255,0.5)',
                crosshairLabel: '#58a6ff',
                currentPrice: '#58a6ff',
                bodyGreen: 'rgba(63,185,80,0.25)',
                bodyRed: 'rgba(248,81,73,0.25)',
                bodyGreenStroke: '#3fb950',
                bodyRedStroke: '#f85149',
            },
            ...options,
        };

        this.data = [];
        this.currentPrice = null;

        // Viewport
        this.offsetX = 0;
        this.offsetY = 0;

        // Mouse
        this._mouseX = -1;
        this._mouseY = -1;
        this._isDragging = false;
        this._dragStartX = 0;
        this._dragStartY = 0;
        this._dragStartOffsetX = 0;
        this._dragStartOffsetY = 0;

        // Layout (recalculated on render)
        this.width = 0;
        this.height = 0;
        this._chartLeft = 0;
        this._chartRight = 0;
        this._chartTop = 0;
        this._chartBottom = 0;
        this._priceMin = 0;
        this._priceMax = 0;
        this._pxPerPrice = 1;

        this._init();
    }

    // ═══════════════════════════════════════
    // Init
    // ═══════════════════════════════════════

    _init() {
        this.container.style.position = 'relative';
        this.container.style.overflow = 'hidden';
        this.container.style.cursor = 'crosshair';

        // Main canvas
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = 'position:absolute;top:0;left:0';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        // Crosshair overlay
        this.crosshairCanvas = document.createElement('canvas');
        this.crosshairCanvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none';
        this.container.appendChild(this.crosshairCanvas);
        this.crosshairCtx = this.crosshairCanvas.getContext('2d');

        // Tooltip
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'footprint-tooltip';
        this.tooltip.style.display = 'none';
        this.container.appendChild(this.tooltip);

        this._resize();
        this._resizeBound = () => this._resize();
        window.addEventListener('resize', this._resizeBound);

        // Mouse
        this.container.addEventListener('mousedown', (e) => this._onMouseDown(e));
        this.container.addEventListener('mousemove', (e) => this._onMouseMove(e));
        this.container.addEventListener('mouseup', () => this._onMouseUp());
        this.container.addEventListener('mouseleave', () => this._onMouseLeave());
        this.container.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });

        // Touch
        this.container.addEventListener('touchstart', (e) => this._onTouchStart(e), { passive: false });
        this.container.addEventListener('touchmove', (e) => this._onTouchMove(e), { passive: false });
        this.container.addEventListener('touchend', () => { this._isDragging = false; this._pinchDist = null; });
    }

    _resize() {
        const rect = this.container.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const dpr = window.devicePixelRatio || 1;

        [this.canvas, this.crosshairCanvas].forEach(c => {
            c.width = rect.width * dpr;
            c.height = rect.height * dpr;
            c.style.width = rect.width + 'px';
            c.style.height = rect.height + 'px';
            c.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
        });

        this.width = rect.width;
        this.height = rect.height;
        this._chartLeft = 0;
        this._chartRight = this.width - this.options.priceAxisWidth;
        this._chartTop = 0;
        this._chartBottom = this.height - this.options.timeAxisHeight;

        this.render();
    }

    // ═══════════════════════════════════════
    // Public API
    // ═══════════════════════════════════════

    setData(data) {
        this.data = data || [];
        if (this.data.length > 0) {
            this.currentPrice = this.data[this.data.length - 1].close;
            this._autoFit();
        }
        this.render();
    }

    updateBar(bar) {
        if (!bar || !bar.time) return;
        const idx = this.data.findIndex(b => b.time === bar.time);
        if (idx >= 0) this.data[idx] = bar; else this.data.push(bar);
        this.currentPrice = bar.close;
        this.render();
    }

    resize() { this._resize(); }

    destroy() {
        window.removeEventListener('resize', this._resizeBound);
        this.container.innerHTML = '';
    }

    // ═══════════════════════════════════════
    // Auto-fit
    // ═══════════════════════════════════════

    _autoFit() {
        if (this.data.length === 0) return;
        const chartW = this._chartRight - this._chartLeft;
        const barW = this.options.barWidth;
        const totalW = this.data.length * barW;
        this.offsetX = Math.max(0, totalW - chartW + barW * 0.5);
        this._fitVertical();
    }

    _fitVertical() {
        const chartW = this._chartRight - this._chartLeft;
        const barW = this.options.barWidth;
        const s = Math.max(0, Math.floor(this.offsetX / barW) - 1);
        const e = Math.min(this.data.length, Math.ceil((this.offsetX + chartW) / barW) + 1);

        let lo = Infinity, hi = -Infinity;
        for (let i = s; i < e; i++) {
            const bar = this.data[i];
            if (!bar) continue;
            if (bar.low < lo) lo = bar.low;
            if (bar.high > hi) hi = bar.high;
        }
        if (lo === Infinity) return;

        const pad = (hi - lo) * 0.12 || 1;
        this._priceMin = lo - pad;
        this._priceMax = hi + pad;
        this._pxPerPrice = (this._chartBottom - this._chartTop) / (this._priceMax - this._priceMin);
        this.offsetY = 0;
    }

    // ═══════════════════════════════════════
    // Coordinate helpers
    // ═══════════════════════════════════════

    _priceToY(p) { return this._chartTop + (this._priceMax - p) * this._pxPerPrice + this.offsetY; }
    _yToPrice(y) { return this._priceMax - (y - this._chartTop - this.offsetY) / this._pxPerPrice; }
    _barIdxToX(i) { return this._chartLeft + i * this.options.barWidth - this.offsetX; }
    _xToBarIdx(x) { return Math.floor((x - this._chartLeft + this.offsetX) / this.options.barWidth); }

    // ═══════════════════════════════════════
    // Main Render
    // ═══════════════════════════════════════

    render() {
        if (!this.ctx || this.width === 0) return;
        const ctx = this.ctx;
        const c = this.options.colors;

        if (this._priceMax <= this._priceMin) this._fitVertical();

        ctx.clearRect(0, 0, this.width, this.height);
        ctx.fillStyle = c.background;
        ctx.fillRect(0, 0, this.width, this.height);

        if (this.data.length === 0) {
            ctx.fillStyle = c.priceLevel;
            ctx.font = '13px Consolas, monospace';
            ctx.textAlign = 'center';
            ctx.fillText('No footprint data — switch to Footprint view', this.width / 2, this.height / 2);
            return;
        }

        // Clip chart area
        ctx.save();
        ctx.beginPath();
        ctx.rect(this._chartLeft, this._chartTop, this._chartRight - this._chartLeft, this._chartBottom - this._chartTop);
        ctx.clip();

        this._drawGrid(ctx);
        this._drawBars(ctx);
        this._drawCurrentPriceLine(ctx);

        ctx.restore();

        this._drawPriceAxis(ctx);
        this._drawTimeAxis(ctx);
        this._drawCrosshair();
    }

    // ═══════════════════════════════════════
    // Grid
    // ═══════════════════════════════════════

    _drawGrid(ctx) {
        const c = this.options.colors;
        const step = this._niceStep(this._priceMax - this._priceMin, 10);
        const sp = Math.floor(this._priceMin / step) * step;
        const ep = Math.ceil(this._priceMax / step) * step;

        ctx.lineWidth = 0.5;
        ctx.strokeStyle = c.gridLineLight;
        for (let p = sp; p <= ep; p += step) {
            const y = this._priceToY(p);
            if (y < this._chartTop || y > this._chartBottom) continue;
            ctx.beginPath(); ctx.moveTo(this._chartLeft, y); ctx.lineTo(this._chartRight, y); ctx.stroke();
        }

        const barW = this.options.barWidth;
        const fi = Math.max(0, Math.floor(this.offsetX / barW));
        const li = Math.min(this.data.length, Math.ceil((this.offsetX + (this._chartRight - this._chartLeft)) / barW) + 1);
        ctx.strokeStyle = c.gridLine;
        for (let i = fi; i <= li; i++) {
            const x = this._barIdxToX(i);
            if (x < this._chartLeft || x > this._chartRight) continue;
            ctx.beginPath(); ctx.moveTo(x, this._chartTop); ctx.lineTo(x, this._chartBottom); ctx.stroke();
        }
    }

    // ═══════════════════════════════════════
    // Draw Bars
    // ═══════════════════════════════════════

    _drawBars(ctx) {
        const barW = this.options.barWidth;
        const fi = Math.max(0, Math.floor(this.offsetX / barW) - 1);
        const li = Math.min(this.data.length, Math.ceil((this.offsetX + (this._chartRight - this._chartLeft)) / barW) + 1);
        for (let i = fi; i < li; i++) {
            const bar = this.data[i];
            if (!bar) continue;
            this._drawSingleBar(ctx, bar, this._barIdxToX(i), barW);
        }
    }

    _drawSingleBar(ctx, bar, x, barW) {
        const c = this.options.colors;
        const levels = bar.levels;
        if (!levels || levels.length === 0) return;
        const isGreen = bar.close >= bar.open;
        const halfW = barW / 2;

        // Max vol for heat normalization
        let maxVol = 1;
        levels.forEach(l => { maxVol = Math.max(maxVol, l.bid || 0, l.ask || 0); });

        // POC
        let pocPrice = bar.poc;
        if (!pocPrice) {
            let mx = 0;
            levels.forEach(l => { const t = (l.bid || 0) + (l.ask || 0); if (t > mx) { mx = t; pocPrice = l.price; } });
        }

        // Body fill
        const bodyTop = this._priceToY(Math.max(bar.open, bar.close));
        const bodyBot = this._priceToY(Math.min(bar.open, bar.close));
        ctx.fillStyle = isGreen ? c.bodyGreen : c.bodyRed;
        ctx.fillRect(x + 2, bodyTop, barW - 4, Math.max(1, bodyBot - bodyTop));

        // Wick
        const highY = this._priceToY(bar.high);
        const lowY = this._priceToY(bar.low);
        ctx.strokeStyle = isGreen ? c.bodyGreenStroke : c.bodyRedStroke;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x + halfW, highY); ctx.lineTo(x + halfW, lowY); ctx.stroke();

        // Volume cells
        levels.forEach(level => {
            const py = this._priceToY(level.price);
            const nextPy = this._priceToY(level.price + this.options.priceStep);
            const rowH = Math.max(2, Math.abs(py - nextPy));
            if (py < this._chartTop - rowH || py > this._chartBottom + rowH) return;

            const bid = level.bid || 0;
            const ask = level.ask || 0;
            const ratio = bid > 0 && ask > 0 ? Math.max(bid / ask, ask / bid) : (bid > 0 || ask > 0 ? 9 : 1);
            const isImb = ratio >= this.options.imbalanceThreshold;
            const isAbs = this._isAbsorption(bar, level);

            if (bid > 0) {
                const frac = bid / maxVol;
                const cellW = frac * (halfW - 4);
                let col = c.bidCell;
                if (isAbs) col = c.absorption; else if (isImb && bid > ask) col = c.imbalance;
                ctx.fillStyle = this._rgba(col, 0.15 + frac * 0.75);
                ctx.fillRect(x + halfW - cellW - 2, py - rowH / 2, cellW, rowH - 1);
                if (barW >= 50 && bid >= maxVol * 0.08) {
                    ctx.fillStyle = c.bidText;
                    ctx.font = `${Math.min(11, rowH - 2)}px Consolas, monospace`;
                    ctx.textAlign = 'right';
                    ctx.fillText(this._fmtVol(bid), x + halfW - 3, py + 3);
                }
            }

            if (ask > 0) {
                const frac = ask / maxVol;
                const cellW = frac * (halfW - 4);
                let col = c.askCell;
                if (isAbs) col = c.absorption; else if (isImb && ask > bid) col = c.imbalance;
                ctx.fillStyle = this._rgba(col, 0.15 + frac * 0.75);
                ctx.fillRect(x + halfW + 2, py - rowH / 2, cellW, rowH - 1);
                if (barW >= 50 && ask >= maxVol * 0.08) {
                    ctx.fillStyle = c.askText;
                    ctx.font = `${Math.min(11, rowH - 2)}px Consolas, monospace`;
                    ctx.textAlign = 'left';
                    ctx.fillText(this._fmtVol(ask), x + halfW + 3, py + 3);
                }
            }

            // POC dot
            if (level.price === pocPrice) {
                ctx.fillStyle = c.pocMarker;
                ctx.beginPath(); ctx.arc(x + halfW, py, 3, 0, Math.PI * 2); ctx.fill();
            }
        });

        // Body outline
        ctx.strokeStyle = isGreen ? c.bodyGreenStroke : c.bodyRedStroke;
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 2, bodyTop, barW - 4, Math.max(1, bodyBot - bodyTop));
    }

    // ═══════════════════════════════════════
    // Current Price Line
    // ═══════════════════════════════════════

    _drawCurrentPriceLine(ctx) {
        if (!this.currentPrice) return;
        const y = this._priceToY(this.currentPrice);
        if (y < this._chartTop || y > this._chartBottom) return;
        ctx.strokeStyle = this.options.colors.currentPrice;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(this._chartLeft, y); ctx.lineTo(this._chartRight, y); ctx.stroke();
        ctx.setLineDash([]);
    }

    // ═══════════════════════════════════════
    // Price Axis
    // ═══════════════════════════════════════

    _drawPriceAxis(ctx) {
        const c = this.options.colors;
        const ax = this._chartRight;
        const aw = this.options.priceAxisWidth;

        ctx.fillStyle = c.background;
        ctx.fillRect(ax, 0, aw, this.height);
        ctx.strokeStyle = c.gridLine;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(ax, 0); ctx.lineTo(ax, this.height); ctx.stroke();

        const step = this._niceStep(this._priceMax - this._priceMin, 10);
        const sp = Math.floor(this._priceMin / step) * step;
        const ep = Math.ceil(this._priceMax / step) * step;

        ctx.fillStyle = c.priceLevel;
        ctx.font = '10px Consolas, monospace';
        ctx.textAlign = 'left';
        for (let p = sp; p <= ep; p += step) {
            const y = this._priceToY(p);
            if (y < 5 || y > this._chartBottom - 5) continue;
            ctx.fillText(this._fmtPrice(p), ax + 5, y + 3);
        }

        // Current price badge
        if (this.currentPrice) {
            const y = this._priceToY(this.currentPrice);
            if (y > 0 && y < this._chartBottom) {
                ctx.fillStyle = c.currentPrice;
                ctx.fillRect(ax, y - 9, aw, 18);
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 10px Consolas, monospace';
                ctx.textAlign = 'left';
                ctx.fillText(this._fmtPrice(this.currentPrice), ax + 5, y + 4);
            }
        }
    }

    // ═══════════════════════════════════════
    // Time Axis
    // ═══════════════════════════════════════

    _drawTimeAxis(ctx) {
        const c = this.options.colors;
        const ay = this._chartBottom;
        const barW = this.options.barWidth;

        ctx.fillStyle = c.background;
        ctx.fillRect(0, ay, this.width, this.options.timeAxisHeight);
        ctx.strokeStyle = c.gridLine;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(0, ay); ctx.lineTo(this.width, ay); ctx.stroke();

        ctx.fillStyle = c.priceLevel;
        ctx.font = '9px Consolas, monospace';
        ctx.textAlign = 'center';

        const every = Math.max(1, Math.round(80 / barW));
        const fi = Math.max(0, Math.floor(this.offsetX / barW));
        const li = Math.min(this.data.length, Math.ceil((this.offsetX + (this._chartRight - this._chartLeft)) / barW) + 1);

        for (let i = fi; i < li; i += every) {
            const bar = this.data[i];
            if (!bar) continue;
            const bx = this._barIdxToX(i) + barW / 2;
            if (bx < this._chartLeft || bx > this._chartRight) continue;
            const d = new Date(bar.time * 1000);
            ctx.fillText(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`, bx, ay + 14);
        }
    }

    // ═══════════════════════════════════════
    // Crosshair
    // ═══════════════════════════════════════

    _drawCrosshair() {
        const ctx = this.crosshairCtx;
        ctx.clearRect(0, 0, this.width, this.height);
        if (this._mouseX < 0 || this._isDragging) return;
        if (this._mouseX > this._chartRight || this._mouseY > this._chartBottom) return;

        const c = this.options.colors;

        ctx.strokeStyle = c.crosshair;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);

        // Vertical
        ctx.beginPath(); ctx.moveTo(this._mouseX, this._chartTop); ctx.lineTo(this._mouseX, this._chartBottom); ctx.stroke();
        // Horizontal
        ctx.beginPath(); ctx.moveTo(this._chartLeft, this._mouseY); ctx.lineTo(this._chartRight, this._mouseY); ctx.stroke();
        ctx.setLineDash([]);

        // Price label
        const price = this._yToPrice(this._mouseY);
        ctx.fillStyle = 'rgba(88,166,255,0.85)';
        ctx.fillRect(this._chartRight, this._mouseY - 9, this.options.priceAxisWidth, 18);
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 10px Consolas, monospace';
        ctx.textAlign = 'left';
        ctx.fillText(this._fmtPrice(price), this._chartRight + 5, this._mouseY + 4);

        // Time label
        const bi = this._xToBarIdx(this._mouseX);
        if (bi >= 0 && bi < this.data.length) {
            const bar = this.data[bi];
            if (bar) {
                const bx = this._barIdxToX(bi) + this.options.barWidth / 2;
                const d = new Date(bar.time * 1000);
                const lbl = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
                const tw = ctx.measureText(lbl).width + 8;
                ctx.fillStyle = 'rgba(88,166,255,0.85)';
                ctx.fillRect(bx - tw / 2, this._chartBottom, tw, this.options.timeAxisHeight);
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 9px Consolas, monospace';
                ctx.textAlign = 'center';
                ctx.fillText(lbl, bx, this._chartBottom + 14);
            }
        }
    }

    // ═══════════════════════════════════════
    // Mouse Events
    // ═══════════════════════════════════════

    _onMouseDown(e) {
        if (e.button !== 0) return;
        this._isDragging = true;
        this._dragStartX = e.clientX;
        this._dragStartY = e.clientY;
        this._dragStartOffsetX = this.offsetX;
        this._dragStartOffsetY = this.offsetY;
        this.container.style.cursor = 'grabbing';
        this._hideTooltip();
    }

    _onMouseMove(e) {
        const rect = this.container.getBoundingClientRect();
        this._mouseX = e.clientX - rect.left;
        this._mouseY = e.clientY - rect.top;

        if (this._isDragging) {
            const dx = e.clientX - this._dragStartX;
            const dy = e.clientY - this._dragStartY;
            this.offsetX = this._dragStartOffsetX - dx;
            this.offsetY = this._dragStartOffsetY + dy;
            const maxOff = Math.max(0, this.data.length * this.options.barWidth - (this._chartRight - this._chartLeft) * 0.5);
            this.offsetX = Math.max(-(this._chartRight - this._chartLeft) * 0.5, Math.min(maxOff, this.offsetX));
            this.render();
        } else {
            this._updateHover();
            this._drawCrosshair();
        }
    }

    _onMouseUp() {
        this._isDragging = false;
        this.container.style.cursor = 'crosshair';
    }

    _onMouseLeave() {
        this._isDragging = false;
        this._mouseX = -1;
        this._mouseY = -1;
        this._hideTooltip();
        this._drawCrosshair();
        this.container.style.cursor = 'crosshair';
    }

    _onWheel(e) {
        e.preventDefault();
        const rect = this.container.getBoundingClientRect();
        const mx = e.clientX - rect.left;

        const factor = e.deltaY > 0 ? 0.9 : 1.1;
        const oldBW = this.options.barWidth;
        const newBW = Math.max(this.options.minBarWidth, Math.min(this.options.maxBarWidth, oldBW * factor));

        // Keep bar under mouse at same screen X
        const barUnder = (mx + this.offsetX) / oldBW;
        this.options.barWidth = newBW;
        this.offsetX = barUnder * newBW - mx;

        // Adjust row height proportionally
        this.options.rowHeight = Math.max(8, Math.min(30, 17 * (newBW / 90)));

        this.render();
    }

    // ═══════════════════════════════════════
    // Touch Events
    // ═══════════════════════════════════════

    _onTouchStart(e) {
        if (e.touches.length === 1) {
            e.preventDefault();
            this._isDragging = true;
            this._dragStartX = e.touches[0].clientX;
            this._dragStartY = e.touches[0].clientY;
            this._dragStartOffsetX = this.offsetX;
            this._dragStartOffsetY = this.offsetY;
        } else if (e.touches.length === 2) {
            e.preventDefault();
            this._pinchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
            this._pinchBW = this.options.barWidth;
        }
    }

    _onTouchMove(e) {
        if (e.touches.length === 1 && this._isDragging) {
            e.preventDefault();
            this.offsetX = this._dragStartOffsetX - (e.touches[0].clientX - this._dragStartX);
            this.offsetY = this._dragStartOffsetY + (e.touches[0].clientY - this._dragStartY);
            this.render();
        } else if (e.touches.length === 2 && this._pinchDist) {
            e.preventDefault();
            const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
            this.options.barWidth = Math.max(this.options.minBarWidth, Math.min(this.options.maxBarWidth, this._pinchBW * (d / this._pinchDist)));
            this.render();
        }
    }

    // ═══════════════════════════════════════
    // Hover / Tooltip
    // ═══════════════════════════════════════

    _updateHover() {
        const bi = this._xToBarIdx(this._mouseX);
        if (bi < 0 || bi >= this.data.length) { this._hideTooltip(); return; }
        const bar = this.data[bi];
        const price = this._yToPrice(this._mouseY);
        const level = bar.levels?.find(l => Math.abs(l.price - price) < this.options.priceStep * 0.8);
        if (level) this._showTooltip(bar, level); else this._hideTooltip();
    }

    _showTooltip(bar, level) {
        const bid = level.bid || 0, ask = level.ask || 0;
        const delta = bid - ask;
        const imb = bid > 0 && ask > 0 ? Math.max(bid / ask, ask / bid).toFixed(1) : '∞';
        this.tooltip.innerHTML = `
            <div style="font-weight:600;color:#e6edf3;margin-bottom:3px">${this._fmtPrice(level.price)}</div>
            <div style="display:flex;gap:12px">
                <span style="color:#3fb950">BID ${this._fmtVol(bid)}</span>
                <span style="color:#f85149">ASK ${this._fmtVol(ask)}</span>
            </div>
            <div style="display:flex;gap:12px;margin-top:2px">
                <span style="color:${delta >= 0 ? '#3fb950' : '#f85149'}">Δ ${delta >= 0 ? '+' : ''}${this._fmtVol(delta)}</span>
                <span style="color:#8b949e">Imb ${imb}x</span>
            </div>`;
        this.tooltip.style.display = 'block';
        let tx = this._mouseX + 15, ty = this._mouseY - 10;
        if (tx + 160 > this.width) tx = this._mouseX - 165;
        if (ty < 0) ty = 5;
        this.tooltip.style.left = tx + 'px';
        this.tooltip.style.top = ty + 'px';
    }

    _hideTooltip() { if (this.tooltip) this.tooltip.style.display = 'none'; }

    // ═══════════════════════════════════════
    // Utilities
    // ═══════════════════════════════════════

    _isAbsorption(bar, level) {
        const total = (level.bid || 0) + (level.ask || 0);
        const avg = bar.levels.reduce((s, l) => s + (l.bid || 0) + (l.ask || 0), 0) / bar.levels.length;
        if (total < avg * this.options.absorptionThreshold) return false;
        return Math.abs(bar.close - bar.open) < (bar.high - bar.low) * 0.3;
    }

    _rgba(hex, a) {
        const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r},${g},${b},${a})`;
    }

    _fmtPrice(p) { return p >= 10000 ? p.toFixed(1) : p >= 1 ? p.toFixed(2) : p.toFixed(4); }

    _fmtVol(v) {
        const a = Math.abs(v);
        if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
        if (a >= 1e3) return (v / 1e3).toFixed(1) + 'K';
        return Math.round(v).toString();
    }

    _niceStep(range, maxTicks) {
        const rough = range / maxTicks;
        const mag = Math.pow(10, Math.floor(Math.log10(rough)));
        const norm = rough / mag;
        return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
    }
}

window.FootprintChart = FootprintChart;
