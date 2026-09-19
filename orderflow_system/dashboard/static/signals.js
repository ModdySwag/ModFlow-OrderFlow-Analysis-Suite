/**
 * Signal Recommendation Cards Component
 * Displays trade signals with confidence, reasoning, and action options
 */

class SignalCards {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            maxSignals: 10,
            showReasoning: true,
            onTakeTradeCallback: null,  // Function to call when user clicks "Take Trade"
            colors: {
                bullish: '#3fb950',
                bearish: '#f85149',
                neutral: '#8b949e',
                highConf: '#3fb950',
                medConf: '#d29922',
                lowConf: '#f85149',
                ...options.colors
            },
            ...options
        };

        this.signals = [];
        this._init();
    }

    _init() {
        this.container.innerHTML = `
            <div class="signals-container">
                <div class="signals-header">
                    <span class="signals-title">TRADE RECOMMENDATIONS</span>
                    <div class="signals-filters">
                        <select id="signalSortBy" class="signals-select">
                            <option value="confidence">By Confidence</option>
                            <option value="time">By Time</option>
                            <option value="rr">By R:R</option>
                        </select>
                        <button id="signalRefresh" class="signals-btn" title="Refresh the signals table now">⟳</button>
                    </div>
                </div>
                <div class="signals-body" id="signalsBody">
                    <div class="signals-empty">Waiting for signals...</div>
                </div>
                <div class="signals-footer">
                    <span class="signals-count">
                        <span id="signalCount">0</span> active signals
                    </span>
                </div>
            </div>
        `;

        this.bodyEl = document.getElementById('signalsBody');
        this.countEl = document.getElementById('signalCount');

        // Wire up controls
        document.getElementById('signalSortBy').addEventListener('change', (e) => {
            this._sortSignals(e.target.value);
            this._render();
        });

        document.getElementById('signalRefresh').addEventListener('click', () => {
            if (this.options.onRefreshCallback) {
                this.options.onRefreshCallback();
            }
        });
    }

    /**
     * Set signals data
     * @param {Array} signals - Array of signal objects
     */
    setSignals(signals) {
        this.signals = (signals || []).slice(0, this.options.maxSignals);
        this._render();
    }

    /**
     * Add a new signal
     */
    addSignal(signal) {
        if (!signal) return;

        // Check for duplicate
        const exists = this.signals.find(s => 
            s.id === signal.id || 
            (s.symbol === signal.symbol && s.pattern === signal.pattern && s.entry === signal.entry)
        );
        
        if (!exists) {
            this.signals.unshift({
                ...signal,
                id: signal.id || Date.now(),
                timestamp: signal.timestamp || Date.now()
            });

            // Trim to max
            if (this.signals.length > this.options.maxSignals) {
                this.signals = this.signals.slice(0, this.options.maxSignals);
            }

            this._render();
        }
    }

    /**
     * Remove a signal
     */
    removeSignal(signalId) {
        this.signals = this.signals.filter(s => s.id !== signalId);
        this._render();
    }

    /**
     * Clear all signals
     */
    clear() {
        this.signals = [];
        this._render();
    }

    _sortSignals(sortBy) {
        switch (sortBy) {
            case 'confidence':
                this.signals.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
                break;
            case 'time':
                this.signals.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
                break;
            case 'rr':
                this.signals.sort((a, b) => (b.riskReward || 0) - (a.riskReward || 0));
                break;
        }
    }

    _render() {
        this.countEl.textContent = this.signals.length;

        if (this.signals.length === 0) {
            this.bodyEl.innerHTML = '<div class="signals-empty">Waiting for signals...</div>';
            return;
        }

        const html = this.signals.map((signal, idx) => this._renderCard(signal, idx === 0)).join('');
        this.bodyEl.innerHTML = html;

        // Wire up take trade buttons
        this.bodyEl.querySelectorAll('.signal-action-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const signalId = parseInt(e.target.dataset.signalId);
                this._onTakeTrade(signalId);
            });
        });
    }

    _renderCard(signal, isTop) {
        const direction = signal.direction || (signal.type === 'LONG' ? 'long' : 'short');
        const dirClass = direction === 'long' ? 'signal-long' : 'signal-short';
        const topClass = isTop ? 'signal-top' : '';
        
        const confRaw = signal.confidence != null ? signal.confidence : 0;
        const confidence = confRaw > 1 ? Math.round(confRaw) : Math.round(confRaw * 100);
        const confClass = confidence >= 70 ? 'high' : confidence >= 50 ? 'med' : 'low';
        
        const rr = signal.riskReward || this._calculateRR(signal);
        const age = this._formatAge(signal.timestamp || signal.timestamp_ms);
        const grade = signal.grade || (confidence >= 85 ? 'A+' : confidence >= 70 ? 'A' : confidence >= 55 ? 'B' : 'C');

        const qualityPct = Math.min(100, confidence);
        const qualityColor = confidence >= 70 ? 'var(--green)' : confidence >= 50 ? 'var(--orange)' : 'var(--red)';
        const cardId = `sig-${signal.id}`;

        // Multi-timeframe confluence indicators
        const mtf = signal.mtf_confluence || {};
        const mtfItems = Object.entries(mtf).filter(([,v]) => v).map(([k, v]) => {
            const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const aligned = this._isMtfAligned(k, v, direction);
            return `<div class="mtf-item ${aligned ? 'mtf-aligned' : 'mtf-conflict'}">
                <span class="mtf-check">${aligned ? '✓' : '✗'}</span>
                <span class="mtf-label">${label}</span>
                <span class="mtf-val">${v}</span>
            </div>`;
        }).join('');

        const regime = signal.market_regime || {};

        return `
            <div class="signal-card ${dirClass} ${topClass}" data-signal-id="${signal.id}">
                <!-- ── Header Row ── -->
                <div class="signal-header">
                    <div class="signal-symbol">${signal.symbol || '--'}</div>
                    <div class="signal-direction">
                        <span class="signal-dir-arrow">${direction === 'long' ? '↑' : '↓'}</span>
                        <span class="signal-dir-label">${direction.toUpperCase()}</span>
                    </div>
                    <div class="signal-grade grade-${grade.replace('+', 'plus')}">${grade}</div>
                    <div class="signal-confidence conf-${confClass}">
                        <span class="signal-conf-value">${confidence}%</span>
                        <span class="signal-conf-label">score</span>
                    </div>
                </div>

                <div class="signal-quality-bar">
                    <div class="signal-quality-fill" style="width:${qualityPct}%;background:${qualityColor}"></div>
                </div>

                <!-- ── Price Levels ── -->
                <div class="signal-levels">
                    <div class="signal-level signal-entry">
                        <span class="level-label">ENTRY</span>
                        <span class="level-value">${this._formatPrice(signal.entry || signal.entry_price)}</span>
                    </div>
                    <div class="signal-level signal-sl">
                        <span class="level-label">STOP</span>
                        <span class="level-value">${this._formatPrice(signal.stopLoss || signal.suggested_sl)}</span>
                    </div>
                    <div class="signal-level signal-tp">
                        <span class="level-label">TARGET</span>
                        <span class="level-value">${this._formatPrice(signal.takeProfit || signal.suggested_tp)}</span>
                    </div>
                    <div class="signal-level signal-rr">
                        <span class="level-label">R:R</span>
                        <span class="level-value">${rr.toFixed(1)}</span>
                    </div>
                </div>

                <!-- ── Narrative (what is happening) ── -->
                ${signal.narrative ? `
                <div class="signal-section signal-narrative">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">📊</span>
                        <span class="section-title">What's Happening</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body">${signal.narrative}</div>
                </div>` : ''}

                <!-- ── Trade Thesis ── -->
                ${signal.thesis ? `
                <div class="signal-section signal-thesis">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">🎯</span>
                        <span class="section-title">Trade Thesis</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body">${signal.thesis}</div>
                </div>` : ''}

                <!-- ── Edge / Why This Trade ── -->
                ${signal.edge ? `
                <div class="signal-section signal-edge">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">⚡</span>
                        <span class="section-title">Orderflow Edge</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body">${signal.edge}</div>
                </div>` : ''}

                <!-- ── Multi-Timeframe Confluence ── -->
                ${mtfItems ? `
                <div class="signal-section signal-mtf">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">🔗</span>
                        <span class="section-title">Timeframe Confluence</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body">
                        <div class="mtf-grid">${mtfItems}</div>
                    </div>
                </div>` : ''}

                <!-- ── HTF Context ── -->
                ${signal.htf_context ? `
                <div class="signal-section signal-htf">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">📈</span>
                        <span class="section-title">Higher Timeframe</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body">${signal.htf_context}</div>
                </div>` : ''}

                <!-- ── Context Grid ── -->
                <div class="signal-context-grid">
                    <div class="ctx-chip">
                        <span class="ctx-key">Pattern</span>
                        <span class="ctx-val ctx-pattern">${signal.pattern || signal.signal_type || '--'}</span>
                    </div>
                    <div class="ctx-chip">
                        <span class="ctx-key">Model</span>
                        <span class="ctx-val">${signal.model || '--'}</span>
                    </div>
                    <div class="ctx-chip">
                        <span class="ctx-key">Session</span>
                        <span class="ctx-val">${signal.session || '--'}</span>
                    </div>
                    <div class="ctx-chip">
                        <span class="ctx-key">Bias</span>
                        <span class="ctx-val ctx-bias ${(signal.bias || '').toLowerCase()}">${signal.bias || '--'}</span>
                    </div>
                    ${signal.market_state ? `<div class="ctx-chip">
                        <span class="ctx-key">Regime</span>
                        <span class="ctx-val">${signal.market_state}</span>
                    </div>` : ''}
                    ${signal.volume_context ? `<div class="ctx-chip">
                        <span class="ctx-key">Volume</span>
                        <span class="ctx-val">${signal.volume_context}</span>
                    </div>` : ''}
                    ${signal.key_level_type ? `<div class="ctx-chip">
                        <span class="ctx-key">Key Level</span>
                        <span class="ctx-val">${signal.key_level_type} @ ${this._formatPrice(signal.key_level_price)}</span>
                    </div>` : ''}
                </div>

                <!-- ── Regime Detail ── -->
                ${regime.detail ? `
                <div class="signal-regime-detail">
                    <span class="regime-tag">${regime.state || ''}</span>
                    <span class="regime-text">${regime.detail}</span>
                </div>` : ''}

                <!-- ── Session Detail ── -->
                ${signal.session_detail ? `
                <div class="signal-session-detail">
                    <span class="session-tag">${signal.session}</span>
                    <span class="session-text">${signal.session_detail}</span>
                </div>` : ''}

                <!-- ── Orderflow Metrics ── -->
                <div class="signal-orderflow-metrics">
                    ${signal.absorption_count ? `<div class="of-metric">
                        <span class="of-label">Absorptions</span>
                        <span class="of-value">${signal.absorption_count}x</span>
                    </div>` : ''}
                    <div class="of-metric">
                        <span class="of-label">Delta</span>
                        <span class="of-value ${signal.delta_confirm ? 'of-confirmed' : 'of-unconfirmed'}">
                            ${signal.delta_value != null ? (signal.delta_value > 0 ? '+' : '') + Math.round(signal.delta_value) : (signal.delta_confirm ? '✓' : '✗')}
                        </span>
                    </div>
                    <div class="of-metric">
                        <span class="of-label">Initiative</span>
                        <span class="of-value">${signal.initiative_strength || '--'}%</span>
                    </div>
                    ${signal.book_imbalance_pct ? `<div class="of-metric">
                        <span class="of-label">Book Imbalance</span>
                        <span class="of-value">${signal.book_imbalance_pct}%</span>
                    </div>` : ''}
                </div>

                <!-- ── Footprint Summary ── -->
                ${signal.footprint_summary ? `
                <div class="signal-footprint-summary">
                    <span class="fp-icon">🏗</span>
                    <span class="fp-text">${signal.footprint_summary}</span>
                </div>` : ''}

                <!-- ── Invalidation ── -->
                ${signal.invalidation ? `
                <div class="signal-section signal-invalidation">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">🚫</span>
                        <span class="section-title">Invalidation</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body invalidation-text">${signal.invalidation}</div>
                </div>` : ''}

                <!-- ── Reasoning Chain ── -->
                ${this.options.showReasoning && signal.reasons && signal.reasons.length ? `
                <div class="signal-section signal-reasoning-chain">
                    <div class="section-hdr" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="section-icon">🧠</span>
                        <span class="section-title">Reasoning Chain</span>
                        <span class="section-toggle">▾</span>
                    </div>
                    <div class="section-body">
                        <ol class="reasoning-list">
                            ${signal.reasons.map(r => `<li>${r.replace(/^\d+\.\s*/, '')}</li>`).join('')}
                        </ol>
                    </div>
                </div>` : ''}

                <!-- ── Action Footer ── -->
                <div class="signal-footer">
                    <span class="signal-age">${age}</span>
                    <span class="signal-action-label ${signal.action === 'enter' ? 'action-enter' : 'action-alert'}">${signal.action === 'enter' ? '⚡ ENTRY' : '📢 ALERT'}</span>
                    <div class="signal-actions">
                        <button class="signal-action-btn signal-take-btn" data-signal-id="${signal.id}">
                            Take Trade
                        </button>
                    </div>
                </div>

                ${signal.blockers && signal.blockers.length > 0 ? `
                <div class="signal-blockers">
                    <span class="blocker-icon">⚠</span>
                    <div class="blocker-list">
                        ${signal.blockers.map(b => `<div class="blocker-item">${b}</div>`).join('')}
                    </div>
                </div>` : ''}
            </div>
        `;
    }

    /**
     * Check if a multi-timeframe component aligns with the trade direction
     */
    _isMtfAligned(key, value, direction) {
        const v = (value || '').toLowerCase();
        if (direction === 'long') {
            return v.includes('bull') || v.includes('uptrend') || v.includes('higher') || v.includes('breakout') || v.includes('absorption') || v.includes('initiative') || v.includes('poc bounce');
        } else {
            return v.includes('bear') || v.includes('downtrend') || v.includes('lower') || v.includes('breakout') || v.includes('exhaustion') || v.includes('divergence') || v.includes('sweep');
        }
    }

    _buildReasoning(signal) {
        // No longer used — reasoning is rendered inline as an ordered list
        return null;
    }

    _calculateRR(signal) {
        const entry = signal.entry || signal.entry_price;
        const sl = signal.stopLoss || signal.suggested_sl;
        const tp = signal.takeProfit || signal.suggested_tp;
        if (!entry || !sl || !tp) return 0;
        
        const risk = Math.abs(entry - sl);
        const reward = Math.abs(tp - entry);
        
        return risk > 0 ? reward / risk : 0;
    }

    _formatPrice(price) {
        if (!price) return '--';
        if (price >= 1000) return price.toFixed(1);
        if (price >= 1) return price.toFixed(2);
        return price.toFixed(4);
    }

    _formatAge(timestamp) {
        if (!timestamp) return '--';
        
        const now = Date.now();
        const diff = now - timestamp;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
        if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
        return Math.floor(diff / 86400000) + 'd ago';
    }

    _onTakeTrade(signalId) {
        const signal = this.signals.find(s => s.id === signalId);
        if (!signal) return;

        // Mark as taken
        signal.taken = true;
        signal.takenAt = Date.now();

        // Callback
        if (this.options.onTakeTradeCallback) {
            this.options.onTakeTradeCallback(signal);
        }

        // Update display
        this._render();
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in main app
window.SignalCards = SignalCards;
