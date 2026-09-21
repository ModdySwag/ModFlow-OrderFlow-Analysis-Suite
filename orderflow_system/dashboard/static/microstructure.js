/**
 * Microstructure Indicators Panel
 * Real-time orderflow pattern and market state indicators
 */

class MicrostructurePanel {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            colors: {
                bullish: '#3fb950',
                bearish: '#f85149',
                neutral: '#8b949e',
                warning: '#d29922',
                info: '#58a6ff',
                purple: '#bc8cff',
                ...options.colors
            },
            ...options
        };

        this.state = {
            marketState: 'UNKNOWN',
            absorptionLevel: null,
            absorptionAttempts: 0,
            initiativeChain: 0,
            maxInitiativeChain: 5,
            exhaustionStrength: 0,
            deltaDirection: 'neutral',
            session: {
                name: '—',
                remaining: '—'
            },
            patterns: []
        };

        this._init();
    }

    _init() {
        this.container.innerHTML = `
            <div class="micro-panel">
                <!-- Market State Badge -->
                <div class="micro-section micro-state-section">
                    <div class="micro-state-badge" id="microMarketState">
                        <span class="micro-state-icon">◈</span>
                        <span class="micro-state-label">UNKNOWN</span>
                    </div>
                    <div class="micro-session" id="microSession">
                        <span class="micro-session-name">—</span>
                        <span class="micro-session-time">--:--</span>
                    </div>
                </div>

                <!-- Absorption Tracker -->
                <div class="micro-section">
                    <div class="micro-section-header">
                        <span class="micro-section-title">ABSORPTION</span>
                        <span class="micro-section-badge" id="microAbsAttempts">0</span>
                    </div>
                    <div class="micro-absorption">
                        <div class="micro-abs-level" id="microAbsLevel">
                            <span class="micro-abs-label">Level:</span>
                            <span class="micro-abs-value">—</span>
                        </div>
                        <div class="micro-abs-attempts" id="microAbsAttemptsBar">
                            <div class="micro-abs-dot"></div>
                            <div class="micro-abs-dot"></div>
                            <div class="micro-abs-dot"></div>
                        </div>
                        <div class="micro-abs-strength">
                            <div class="micro-progress-bar">
                                <div class="micro-progress-fill" id="microAbsStrength"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Initiative Chain -->
                <div class="micro-section">
                    <div class="micro-section-header">
                        <span class="micro-section-title">INITIATIVE</span>
                        <span class="micro-section-badge" id="microInitCount">0</span>
                    </div>
                    <div class="micro-initiative">
                        <div class="micro-init-chain" id="microInitChain">
                            <div class="micro-init-block"></div>
                            <div class="micro-init-block"></div>
                            <div class="micro-init-block"></div>
                            <div class="micro-init-block"></div>
                            <div class="micro-init-block"></div>
                        </div>
                        <div class="micro-init-direction" id="microInitDir">
                            <span class="micro-init-arrow">→</span>
                            <span class="micro-init-label">Neutral</span>
                        </div>
                    </div>
                </div>

                <!-- Delta / CVD Status -->
                <div class="micro-section">
                    <div class="micro-section-header">
                        <span class="micro-section-title">DELTA FLOW</span>
                    </div>
                    <div class="micro-delta">
                        <div class="micro-delta-gauge" id="microDeltaGauge">
                            <div class="micro-delta-needle" id="microDeltaNeedle"></div>
                            <div class="micro-delta-labels">
                                <span class="micro-delta-sell">SELL</span>
                                <span class="micro-delta-buy">BUY</span>
                            </div>
                        </div>
                        <div class="micro-cvd-status" id="microCVD">
                            <span class="micro-cvd-label">CVD:</span>
                            <span class="micro-cvd-value">—</span>
                            <span class="micro-cvd-trend">—</span>
                        </div>
                    </div>
                </div>

                <!-- Exhaustion Meter -->
                <div class="micro-section">
                    <div class="micro-section-header">
                        <span class="micro-section-title">EXHAUSTION</span>
                    </div>
                    <div class="micro-exhaustion">
                        <div class="micro-exh-meter">
                            <div class="micro-exh-fill" id="microExhFill"></div>
                            <div class="micro-exh-markers">
                                <span>0</span>
                                <span>50</span>
                                <span>100</span>
                            </div>
                        </div>
                        <div class="micro-exh-status" id="microExhStatus">Normal</div>
                    </div>
                </div>

                <!-- Active Patterns List -->
                <div class="micro-section micro-patterns-section">
                    <div class="micro-section-header">
                        <span class="micro-section-title">ACTIVE PATTERNS</span>
                        <span class="micro-section-badge" id="microPatternCount">0</span>
                    </div>
                    <div class="micro-patterns" id="microPatterns">
                        <div class="micro-pattern-empty">No active patterns</div>
                    </div>
                </div>
            </div>
        `;

        // Cache element references
        this.els = {
            marketState: document.getElementById('microMarketState'),
            session: document.getElementById('microSession'),
            absLevel: document.getElementById('microAbsLevel'),
            absAttempts: document.getElementById('microAbsAttempts'),
            absAttemptsBar: document.getElementById('microAbsAttemptsBar'),
            absStrength: document.getElementById('microAbsStrength'),
            initCount: document.getElementById('microInitCount'),
            initChain: document.getElementById('microInitChain'),
            initDir: document.getElementById('microInitDir'),
            deltaGauge: document.getElementById('microDeltaGauge'),
            deltaNeedle: document.getElementById('microDeltaNeedle'),
            cvd: document.getElementById('microCVD'),
            exhFill: document.getElementById('microExhFill'),
            exhStatus: document.getElementById('microExhStatus'),
            patterns: document.getElementById('microPatterns'),
            patternCount: document.getElementById('microPatternCount')
        };
    }

    /**
     * Update market state
     * @param {string} state - 'TRENDING' | 'COMPRESSION' | 'REBALANCING' | 'UNKNOWN'
     */
    setMarketState(state) {
        this.state.marketState = state;
        const el = this.els.marketState;
        
        const stateConfig = {
            'TRENDING': { icon: '↗', color: 'bullish', label: 'TRENDING' },
            'COMPRESSION': { icon: '↔', color: 'warning', label: 'COMPRESSION' },
            'REBALANCING': { icon: '↩', color: 'info', label: 'REBALANCING' },
            'UNKNOWN': { icon: '◈', color: 'neutral', label: 'UNKNOWN' }
        };

        const config = stateConfig[state] || stateConfig['UNKNOWN'];
        el.className = `micro-state-badge micro-${config.color}`;
        el.querySelector('.micro-state-icon').textContent = config.icon;
        el.querySelector('.micro-state-label').textContent = config.label;
    }

    /**
     * Update session info
     */
    setSession(name, remainingMs) {
        this.state.session = { name, remaining: remainingMs };
        const el = this.els.session;
        
        el.querySelector('.micro-session-name').textContent = name;
        
        if (remainingMs > 0) {
            const mins = Math.floor(remainingMs / 60000);
            const hrs = Math.floor(mins / 60);
            const remMins = mins % 60;
            el.querySelector('.micro-session-time').textContent = 
                hrs > 0 ? `${hrs}h ${remMins}m` : `${mins}m`;
        } else {
            el.querySelector('.micro-session-time').textContent = '--:--';
        }
    }

    /**
     * Update absorption tracking
     */
    setAbsorption(data) {
        if (!data) return;

        const { level, attempts, strength, side } = data;
        this.state.absorptionLevel = level;
        this.state.absorptionAttempts = attempts || 0;

        // Level display
        this.els.absLevel.querySelector('.micro-abs-value').textContent = 
            level ? this._formatPrice(level) : '—';

        // Attempts badge
        this.els.absAttempts.textContent = attempts || 0;
        this.els.absAttempts.className = 'micro-section-badge' + 
            (attempts >= 3 ? ' micro-hot' : attempts >= 2 ? ' micro-warm' : '');

        // Attempt dots
        const dots = this.els.absAttemptsBar.querySelectorAll('.micro-abs-dot');
        dots.forEach((dot, i) => {
            dot.className = 'micro-abs-dot' + (i < attempts ? ' active' : '');
            if (i < attempts) {
                dot.classList.add(side === 'buy' ? 'bullish' : 'bearish');
            }
        });

        // Strength bar
        const strengthPct = Math.min(100, (strength || 0));
        this.els.absStrength.style.width = strengthPct + '%';
        this.els.absStrength.className = 'micro-progress-fill ' + 
            (strengthPct > 70 ? 'micro-hot' : strengthPct > 40 ? 'micro-warm' : '');
    }

    /**
     * Update initiative chain
     */
    setInitiative(data) {
        if (!data) return;

        const { count, direction, strength } = data;
        this.state.initiativeChain = count || 0;

        // Count badge
        this.els.initCount.textContent = count || 0;

        // Chain blocks
        const blocks = this.els.initChain.querySelectorAll('.micro-init-block');
        blocks.forEach((block, i) => {
            block.className = 'micro-init-block';
            if (i < count) {
                block.classList.add('active');
                block.classList.add(direction === 'up' ? 'bullish' : 'bearish');
            }
        });

        // Direction indicator
        const dirConfig = {
            'up': { arrow: '↑', label: 'Bullish', class: 'bullish' },
            'down': { arrow: '↓', label: 'Bearish', class: 'bearish' },
            'neutral': { arrow: '→', label: 'Neutral', class: '' }
        };
        const config = dirConfig[direction] || dirConfig['neutral'];
        this.els.initDir.querySelector('.micro-init-arrow').textContent = config.arrow;
        this.els.initDir.querySelector('.micro-init-label').textContent = config.label;
        this.els.initDir.className = 'micro-init-direction ' + config.class;
    }

    /**
     * Update delta/CVD status
     */
    setDelta(data) {
        if (!data) return;

        const { cumulative, direction, divergence } = data;
        
        // Gauge needle rotation (-90 to +90 degrees)
        const normalizedDir = Math.max(-1, Math.min(1, direction || 0));
        const rotation = normalizedDir * 60; // -60 to +60 degrees
        this.els.deltaNeedle.style.transform = `translateX(-50%) rotate(${rotation}deg)`;

        // CVD value
        const cvdValueEl = this.els.cvd.querySelector('.micro-cvd-value');
        cvdValueEl.textContent = cumulative ? this._formatVolume(cumulative) : '—';
        cvdValueEl.className = 'micro-cvd-value ' + 
            (cumulative > 0 ? 'bullish' : cumulative < 0 ? 'bearish' : '');

        // Trend indicator
        const trendEl = this.els.cvd.querySelector('.micro-cvd-trend');
        if (divergence) {
            trendEl.textContent = '⚠ Divergence';
            trendEl.className = 'micro-cvd-trend warning';
        } else {
            trendEl.textContent = direction > 0.5 ? '↑' : direction < -0.5 ? '↓' : '→';
            trendEl.className = 'micro-cvd-trend';
        }
    }

    /**
     * Update exhaustion meter
     */
    setExhaustion(strength) {
        this.state.exhaustionStrength = strength || 0;
        
        const pct = Math.min(100, Math.max(0, strength));
        this.els.exhFill.style.width = pct + '%';
        
        let status, colorClass;
        if (pct > 80) {
            status = 'EXTREME';
            colorClass = 'micro-hot';
        } else if (pct > 60) {
            status = 'HIGH';
            colorClass = 'micro-warm';
        } else if (pct > 30) {
            status = 'MODERATE';
            colorClass = '';
        } else {
            status = 'NORMAL';
            colorClass = '';
        }

        this.els.exhFill.className = 'micro-exh-fill ' + colorClass;
        this.els.exhStatus.textContent = status;
        this.els.exhStatus.className = 'micro-exh-status ' + colorClass;
    }

    /**
     * Update active patterns list
     */
    setPatterns(patterns) {
        this.state.patterns = patterns || [];
        
        this.els.patternCount.textContent = patterns.length;

        if (patterns.length === 0) {
            this.els.patterns.innerHTML = '<div class="micro-pattern-empty">No active patterns</div>';
            return;
        }

        const html = patterns.map(p => {
            const typeClass = this._getPatternTypeClass(p.type);
            const confidencePct = Math.round((p.confidence || 0) * 100);
            
            return `
                <div class="micro-pattern-item ${typeClass}">
                    <span class="micro-pattern-type">${p.type}</span>
                    <span class="micro-pattern-conf">${confidencePct}%</span>
                    <span class="micro-pattern-price">${this._formatPrice(p.price)}</span>
                </div>
            `;
        }).join('');

        this.els.patterns.innerHTML = html;
    }

    /**
     * Convenience method to update all at once
     */
    update(data) {
        if (data.marketState) this.setMarketState(data.marketState);
        if (data.session) this.setSession(data.session.name, data.session.remaining);
        if (data.absorption) this.setAbsorption(data.absorption);
        if (data.initiative) this.setInitiative(data.initiative);
        if (data.delta) this.setDelta(data.delta);
        if (data.exhaustion !== undefined) this.setExhaustion(data.exhaustion);
        if (data.patterns) this.setPatterns(data.patterns);
    }

    _getPatternTypeClass(type) {
        const typeMap = {
            'absorption': 'micro-pattern-absorption',
            'initiative': 'micro-pattern-initiative',
            'exhaustion': 'micro-pattern-exhaustion',
            'sweep': 'micro-pattern-sweep',
            'divergence': 'micro-pattern-divergence',
            'failed_auction': 'micro-pattern-failed'
        };
        return typeMap[type?.toLowerCase()] || '';
    }

    _formatPrice(price) {
        if (!price) return '—';
        if (price >= 1000) return price.toFixed(1);
        if (price >= 1) return price.toFixed(2);
        return price.toFixed(4);
    }

    _formatVolume(vol) {
        const abs = Math.abs(vol);
        const sign = vol >= 0 ? '+' : '';
        if (abs >= 1000000) return sign + (vol / 1000000).toFixed(1) + 'M';
        if (abs >= 1000) return sign + (vol / 1000).toFixed(1) + 'K';
        return sign + Math.round(vol);
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in main app
window.MicrostructurePanel = MicrostructurePanel;
