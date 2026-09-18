/* ══════════════════════════════════════════════════════════════════
   alert-format.js — the one place that turns an alert rule into words.

   The Rules card used to read in the engine's own vocabulary: a raw JSON params blob, a kind slug
   and a cooldown number, so understanding a rule meant knowing `min_multiple` and `at_tol`. This
   module owns the translation and nothing else: `paramSpec(kind)` is what the inline editor builds
   its fields from and `sentence(rule)` is what the row renders, so the form and the words cannot
   disagree about what a rule does (the same one-source rule as HEAT_INSET and the cursor store).

   It is pure — a rule in, words out; no DOM, no API, no storage — so `alert-format.selftest.js` can
   pin every kind without a browser, and `orderflow_system/test_alert_format.py` holds it against the
   engine: the params named here must be exactly the params `atlas/alerts.py` reads for that kind.

   The engine's vocabulary, mirrored:
     · kinds  — `alerts.KINDS` plus `wall_age`, the kind the depth map emits (P1-6).
     · params — read by `AlertEngine._passes()`, one branch per kind, and by nothing else.
     · scope  — `at_price` / `at_tol` are checked generically BEFORE any kind-specific threshold
                (alerts.py:179) and `min_age_s` bounds how long a level must have held, so those
                three are the rule's scope rather than one kind's fields. A rule the heatmap
                creates carries all three (`heatmap-pro.js` alertOnLevel).
   ══════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── numbers, prices and durations, said once ─────────────────────────────────────────── */

    function fmtNum(v, digits) {
        const n = Number(v);
        if (!Number.isFinite(n)) return v === null || v === undefined ? '' : String(v);
        return n.toFixed(digits == null ? 2 : digits);
    }

    /* Sizes run 0.001–3 on crypto instruments, so a rounded one reads as an empty cell or a zero
       (the whole live tape once read `0` because of it). Same rule as the tape's own formatter. */
    function fmtSize(v) {
        const n = Number(v);
        if (!Number.isFinite(n)) return '—';
        const a = Math.abs(n);
        if (a === 0) return '0';
        if (a >= 1000) return (n / 1000).toFixed(2) + 'K';
        if (a >= 1) return n.toFixed(2);
        if (a >= 0.01) return n.toFixed(3);
        return n.toPrecision(2);
    }

    /* Prices span a 77 000 index and a 0.0001-grid instrument, so the precision follows the
       magnitude instead of one decimal count for every market. */
    function fmtPrice(v) {
        const n = Number(v);
        if (!Number.isFinite(n)) return '—';
        const a = Math.abs(n);
        if (a === 0) return '0';
        if (a >= 1) return n.toFixed(2);
        if (a >= 0.01) return n.toFixed(4);
        return String(Number(n.toPrecision(2)));        // 0.0002, not 0.00020
    }

    /* Durations as a desk reads them: seconds under two minutes, minutes above. */
    function fmtDur(seconds) {
        const s = Number(seconds);
        if (!Number.isFinite(s) || s <= 0) return '';
        if (s < 120) return (s % 1 ? s.toFixed(1) : String(Math.round(s))) + ' s';
        return (s / 60).toFixed(1) + ' min';
    }

    const upper = (v) => String(v == null ? '' : v).toUpperCase();

    /* ── the channels a rule can reach ────────────────────────────────────────────────────── */

    /* One table for the editor's checkboxes and for the sentence. `ui` is not a switch for the log
       (every alert lands there); it is what the engine treats as "this screen" when it decides
       whether anything has to leave the machine (hub.py `_dispatch`). */
    const CHANNELS = [
        ['ui', 'UI log'],
        ['telegram', 'Telegram'],
        ['ntfy', 'ntfy push'],
        ['email', 'Email'],
        ['webhook', 'Webhook'],
    ];

    function channelLabel(key) {
        const row = CHANNELS.find((c) => c[0] === key);
        return row ? row[1] : String(key);
    }

    /* ── kind catalogue ───────────────────────────────────────────────────────────────────── */

    const SCOPE_FIELDS = [
        { key: 'at_price', label: 'Level', unit: '', min: 0, step: 0.5, scope: true,
          hint: 'empty means the rule watches the whole instrument' },
        { key: 'at_tol', label: 'Tolerance', unit: '±', min: 0, step: 0.1, scope: true,
          hint: 'how far from the level still counts as that level' },
        { key: 'min_age_s', label: 'Minimum hold', unit: 's', min: 0, step: 1, scope: true,
          hint: 'only fire once the level has held this long — the event must carry how long it held' },
    ];

    /* Per kind: the label, a base phrase for a rule that carries no thresholds at all, the params
       `_passes()` reads for that kind (key, label, unit, bounds and how to say a set value), plus
       an optional note for the kinds with no live detector — a select that offers what cannot fire
       has to say so rather than let the user find out from an empty log. */
    const KINDS = {
        big_trade: {
            label: 'Big trade',
            base: 'a single print above the venue block threshold',
            params: [
                { key: 'min_multiple', label: 'Multiple of block threshold', unit: '×', min: 0.1, step: 0.1,
                  say: (v) => 'a single print ≥ ' + fmtNum(v) + '× the block threshold' },
                { key: 'min_size', label: 'Minimum size', unit: '', min: 0, step: 0.01,
                  say: (v) => 'at least ' + fmtSize(v) + ' in size' },
                { key: 'sides', label: 'Sides', kind: 'set', options: ['buy', 'sell'],
                  say: (v) => (v.length >= 2 ? '' : upper(v[0]) + ' side only') },
            ],
        },
        block_trade: {
            label: 'Block trade',
            base: 'an exchange block print',
            params: [
                { key: 'min_multiple', label: 'Multiple of block threshold', unit: '×', min: 0.1, step: 0.1,
                  say: (v) => 'a block ≥ ' + fmtNum(v) + '× the venue threshold' },
                { key: 'min_size', label: 'Minimum size', unit: '', min: 0, step: 0.01,
                  say: (v) => 'at least ' + fmtSize(v) + ' in size' },
                { key: 'sides', label: 'Sides', kind: 'set', options: ['buy', 'sell'],
                  say: (v) => (v.length >= 2 ? '' : upper(v[0]) + ' side only') },
            ],
        },
        sweep: {
            label: 'Sweep',
            base: 'an aggressive run through the book',
            params: [
                { key: 'min_levels', label: 'Levels swept', unit: 'levels', min: 1, step: 1,
                  say: (v) => 'a run through ≥ ' + Math.round(Number(v)) + ' levels' },
                { key: 'min_size', label: 'Minimum swept size', unit: '', min: 0, step: 0.01,
                  say: (v) => 'at least ' + fmtSize(v) + ' taken in one sweep' },
            ],
        },
        stop_run: {
            label: 'Stop run',
            base: 'a stop run',
            params: [
                { key: 'min_ticks', label: 'Distance moved', unit: 'ticks', min: 0, step: 1,
                  say: (v) => 'a run of ≥ ' + fmtNum(v, 0) + ' ticks' },
            ],
        },
        iceberg: {
            label: 'Iceberg (inferred)',
            base: 'repeated refills at one price',
            params: [
                { key: 'min_fills', label: 'Refills', unit: 'fills', min: 1, step: 1,
                  say: (v) => '≥ ' + Math.round(Number(v)) + ' refills at one price' },
            ],
        },
        speed_spike: {
            label: 'Speed of tape spike',
            base: 'a spike in tape speed',
            params: [
                { key: 'min_zscore', label: 'Tape-speed z-score', unit: 'σ', min: 0, step: 0.5,
                  say: (v) => 'tape speed at z ≥ ' + fmtNum(v, 1) },
            ],
        },
        cvd_divergence: {
            label: 'CVD divergence',
            base: 'price and CVD disagreeing',
            params: [
                { key: 'kinds', label: 'Direction', kind: 'set', options: ['bullish', 'bearish'],
                  say: (v) => (v.length >= 2 ? '' : upper(v[0]) + ' divergence') },
                { key: 'min_strength', label: 'Minimum strength', unit: '', min: 0, step: 5,
                  say: (v) => 'strength ≥ ' + fmtNum(v, 0) },
            ],
        },
        heat_pull: {
            label: 'Liquidity pulled near price',
            base: 'size pulled from a level near the price',
            params: [
                { key: 'min_size', label: 'Minimum pulled size', unit: '', min: 0, step: 0.01,
                  say: (v) => '≥ ' + fmtSize(v) + ' pulled' },
            ],
        },
        heat_stack: {
            label: 'Liquidity stacking',
            base: 'size stacking at a level',
            params: [
                { key: 'min_size', label: 'Minimum stacked size', unit: '', min: 0, step: 0.01,
                  say: (v) => '≥ ' + fmtSize(v) + ' stacked' },
            ],
        },
        wall: {
            label: 'Large resting level',
            note: 'no live detector emits this kind yet',
            base: 'a resting level above the wall threshold',
            params: [
                { key: 'min_size', label: 'Minimum rested size', unit: '', min: 0, step: 0.01,
                  say: (v) => '≥ ' + fmtSize(v) + ' resting' },
            ],
        },
        wall_age: {
            label: 'Level holds',
            base: 'a level that keeps holding',
            params: [
                { key: 'min_size', label: 'Minimum size', unit: '', min: 0, step: 0.01,
                  say: (v) => '≥ ' + fmtSize(v) + ' resting' },
            ],
        },
        vwap_cross: {
            label: 'Price crosses VWAP',
            base: 'a cross of VWAP',
            params: [
                { key: 'min_ticks', label: 'Distance past VWAP', unit: 'ticks', min: 0, step: 0.5,
                  say: (v) => 'a cross ≥ ' + fmtNum(v, 1) + ' ticks from VWAP' },
            ],
        },
        depth_execution: {
            label: 'Trade eats resting depth',
            base: 'a print that eats the resting depth',
            params: [
                { key: 'min_share', label: 'Share of the level eaten', unit: 'share', min: 0, max: 1,
                  step: 0.05, say: (v) => '≥ ' + fmtNum(Number(v) * 100, 0) + '% of the resting size' },
            ],
        },
        depth_refill: {
            label: 'Level refills after being eaten',
            base: 'a level refilling after it was eaten',
            params: [
                { key: 'min_share', label: 'Share refilled', unit: 'share', min: 0, max: 1,
                  step: 0.05, say: (v) => '≥ ' + fmtNum(Number(v) * 100, 0) + '% refilled' },
            ],
        },
        stacked_imbalance: {
            label: 'Stacked imbalance',
            base: 'imbalance stacked over consecutive levels',
            params: [
                { key: 'min_levels', label: 'Stacked levels', unit: 'levels', min: 1, step: 1,
                  say: (v) => '≥ ' + Math.round(Number(v)) + ' stacked levels' },
                { key: 'min_volume', label: 'Minimum volume', unit: '', min: 0, step: 0.01,
                  say: (v) => '≥ ' + fmtSize(v) + ' in those levels' },
            ],
        },
        intent_pressure: {
            label: 'Book pressure',
            base: 'one side of the book outweighing its normal weight',
            params: [
                { key: 'min_pct', label: 'Share of normal book', unit: '%', min: 0, step: 5,
                  say: (v) => '≥ ' + fmtNum(v, 0) + '% of the side\u2019s normal weight' },
            ],
        },
        pulled_size: {
            label: 'Large size pulled near price',
            base: 'size withdrawn near the price without being traded',
            params: [
                { key: 'min_size', label: 'Minimum pulled size', unit: '', min: 0, step: 0.01,
                  say: (v) => '≥ ' + fmtSize(v) + ' pulled' },
                { key: 'max_distance_ticks', label: 'Within distance of mid', unit: 'ticks', min: 0, step: 1,
                  say: (v) => 'within ' + fmtNum(v, 0) + ' ticks of mid' },
            ],
        },
        trapped_traders: {
            label: 'Break failed — side trapped',
            base: 'a break that failed and reclaimed',
            params: [
                { key: 'min_beyond_ticks', label: 'Break beyond the level', unit: 'ticks', min: 0, step: 0.5,
                  say: (v) => 'a break ≥ ' + fmtNum(v, 1) + ' ticks beyond the level' },
            ],
        },
        unfinished_business: {
            label: 'Unfinished business',
            base: 'an auction extreme that never finished',
            params: [
                { key: 'sides', label: 'Sides', kind: 'set', options: ['above', 'below'],
                  say: (v) => (v.length >= 2 ? '' : (v[0] === 'above' ? 'unfinished highs only' : 'unfinished lows only')) },
                { key: 'min_arms', label: 'Times left unfinished', unit: '×', min: 1, step: 1,
                  say: (v) => 'left unfinished ≥ ' + Math.round(Number(v)) + '×' },
            ],
        },
        node_zone: {
            label: 'Node formed',
            base: 'consecutive bars sharing one high-volume price',
            params: [
                { key: 'min_count', label: 'Consecutive bars', unit: 'bars', min: 2, step: 1,
                  say: (v) => '≥ ' + Math.round(Number(v)) + ' consecutive bars at one price' },
            ],
        },
        level_touch: {
            label: 'Price returns to a level',
            base: 'price back at the level the area profile marked',
            params: [],
        },
        radar_level: {
            label: 'Radar level',
            base: 'a tracked level changing state',
            params: [
                { key: 'states', label: 'States', kind: 'set',
                  options: ['armed', 'approaching', 'defended', 'confirmed', 'spent', 'failed'],
                  say: (v) => {
                      const list = Array.isArray(v) ? v : (v === '' || v == null ? [] : [v]);
                      return list.length >= 6 ? '' : list.join('/') + ' only';
                  } },
            ],
        },
    };

    /* The kind every rule the depth map creates carries in its id (heatmap-pro.js alertOnLevel).
       The filter on the Rules card counts exactly these, so the prefix lives in one place. */
    const HEATMAP_PREFIX = 'hm-';

    function kindLabel(kind) {
        const spec = KINDS[kind];
        if (spec) return spec.label;
        return String(kind || 'rule').replace(/_/g, ' ');
    }

    /* Every field the editor renders for one kind: that kind's own params plus the three scope
       fields every rule can carry. One list serves the form and the sentence. */
    function paramSpec(kind) {
        const spec = KINDS[kind];
        return (spec ? spec.params : []).concat(SCOPE_FIELDS);
    }

    function kinds() {
        return Object.keys(KINDS).map((k) => ({ kind: k, label: KINDS[k].label, note: KINDS[k].note || '' }));
    }

    function isHeatmapRule(rule) {
        return String((rule && rule.id) || '').indexOf(HEATMAP_PREFIX) === 0;
    }

    /* ── the words ────────────────────────────────────────────────────────────────────────── */

    function setValue(v) {
        if (Array.isArray(v)) return v.filter((x) => x !== null && x !== undefined && x !== '');
        if (typeof v === 'string' && v.trim() !== '') return v.split(',').map((s) => s.trim()).filter(Boolean);
        return [];
    }

    function hasValue(v) {
        if (v === null || v === undefined || v === '') return false;
        if (Array.isArray(v)) return v.length > 0;
        return true;
    }

    /* Where a rule watches: the whole instrument, or one level with a tolerance — plus the hold
       time, which is a scope too (it says WHEN the rule may fire, not what it watches). */
    function scopeWords(rule) {
        const p = (rule && rule.params) || {};
        const bits = [];
        if (!hasValue(p.at_price)) {
            bits.push('any level');
        } else {
            const tol = Number(p.at_tol);
            bits.push('at ' + fmtPrice(p.at_price) + (Number.isFinite(tol) && tol > 0 ? ' ± ' + fmtPrice(tol) : ' (exact)'));
        }
        const hold = Number(p.min_age_s);
        if (Number.isFinite(hold) && hold > 0) bits.push('holds ≥ ' + fmtDur(hold));
        return bits.join(' · ');
    }

    function channelWords(rule) {
        const chans = setValue((rule && rule.channels) || []);
        const off = chans.filter((c) => c !== 'ui');
        if (!off.length) return 'UI log only';
        return 'UI log + ' + off.map(channelLabel).join(' + ');
    }

    function cooldownWords(rule) {
        const s = Number((rule && rule.cooldown_s) || 0);
        return Number.isFinite(s) && s > 0 ? fmtDur(s) + ' cooldown' : 'no cooldown';
    }

    /* A rule as one sentence: what it watches for, where, where it goes and how often it can fire. */
    function sentence(rule) {
        if (!rule) return '';
        const params = rule.params || {};
        const bits = [];
        for (const field of paramSpec(rule.kind)) {
            if (field.scope || !hasValue(params[field.key])) continue;
            const said = field.kind === 'set' ? field.say(setValue(params[field.key])) : field.say(params[field.key]);
            if (said) bits.push(said);
        }
        if (!bits.length) {
            const spec = KINDS[rule.kind];
            bits.push(spec && spec.base ? spec.base : 'any detection of this kind');
        }
        return kindLabel(rule.kind) + ' — ' + bits.join(' · ') + ' · ' + scopeWords(rule) + ' · ' +
            channelWords(rule) + ' · ' + cooldownWords(rule);
    }

    /* Why one fired row is in the log: the detection's own detail first, the engine's sentence
       second, the kind's name last. The Symbol column already names the instrument, so a message
       that repeats it loses the prefix rather than saying it twice. */
    function why(row) {
        const data = (row && row.data) || {};
        const sym = row && row.symbol ? String(row.symbol) + ': ' : '';
        for (const key of ['detail', 'note', 'reason']) {
            const raw = data[key];
            if (raw === null || raw === undefined || raw === '') continue;
            const text = String(raw);
            return sym && text.indexOf(sym) === 0 ? text.slice(sym.length) : text;
        }
        const message = row && row.message ? String(row.message) : '';
        if (message) return sym && message.indexOf(sym) === 0 ? message.slice(sym.length) : message;
        const spec = KINDS[row && row.kind];
        return kindLabel(row && row.kind) + (spec && spec.base ? ' — ' + spec.base : '');
    }

    window.OFAPALERTS = {
        KINDS: KINDS,
        SCOPE_FIELDS: SCOPE_FIELDS,
        CHANNELS: CHANNELS,
        HEATMAP_PREFIX: HEATMAP_PREFIX,
        kindLabel: kindLabel,
        kinds: kinds,
        paramSpec: paramSpec,
        isHeatmapRule: isHeatmapRule,
        scopeWords: scopeWords,
        channelWords: channelWords,
        cooldownWords: cooldownWords,
        sentence: sentence,
        why: why,
        setValue: setValue,
        hasValue: hasValue,
        fmtNum: fmtNum,
        fmtSize: fmtSize,
        fmtPrice: fmtPrice,
        fmtDur: fmtDur,
    };
})();
