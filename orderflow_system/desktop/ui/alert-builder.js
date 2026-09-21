/* alert-builder.js — Alerts ▸ Condition builder: several readings per rule, and the evidence
 * snapshot a notification carries.
 *
 * WHERE THE DATA COMES FROM — nothing here is invented:
 *   GET  /api/atlas/alert-rules        the live rule set (the picker's list and the panel's counts)
 *   POST /api/atlas/alert-rules        save the drafted rule — the same route the Alerts view's own
 *                                      editor uses, so a rule built here is an ordinary rule
 *   POST /api/atlas/alert-rules/test   Test fire: the engine's own `AlertEngine.test_fire` reads the
 *                                      newest real event of that kind out of its log and reports every
 *                                      gate, each condition's reading, and the block the notification
 *                                      would carry — or, when none would, the delivery gate that holds
 *                                      it back. A build without that route says so and carries no
 *                                      block: the panel never supplies one of its own.
 *   window.OFAPALERTS                  the kind catalogue and the params each kind really reads
 *                                      (`alert-format.js`) — one source for the engine's vocabulary,
 *                                      so this panel cannot offer a field the engine ignores.
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - A rule's kind is one reading. Everything this panel adds is a SECOND reading (`conditions`,
 *     combined by `match`) or the evidence attached to the delivery (`context`), and both are
 *     additive: a rule with neither behaves exactly as it always has, and the engine treats an
 *     unknown condition, an absent field or a missing snapshot as "not met" rather than as a zero.
 *   - The condition catalogue below is mirrored from `atlas/alerts.py` (CONDITION_KINDS) and
 *     `test_alert_builder.py` fails when the two drift, the way `test_alert_format.py` holds the
 *     params table against `AlertEngine._passes()`.
 *   - Structure changes re-render the form; typing does not. Values are read out of the DOM at the
 *     moment a button is pressed (`readForm`), so a re-render can never eat an edit.
 *   - No timers at all: this card reads on load, on demand, and after each write.
 */
(function () {
    'use strict';

    const HOST = 'alertBuilderBody';         /* the parent's card body (index.html) */
    const PILL = 'alertBuilderPill';
    const VIEW = '.view[data-view="alerts"]';
    /* The rule list the Alerts view already owns, and the rehearsal route beside it. Both are written
       where they are called, so `scripts/audit_ui_refs.py` can cross-check them against the router. */
    const NEW_RULE_PREFIX = 'ab-';           /* rules this builder creates, so the table can name them */

    const MATCH_MODES = ['all', 'any'];
    const CONTEXT_FORMATS = ['text', 'csv'];
    const CONTEXT_CHANNELS = ['ui', 'telegram', 'ntfy', 'email', 'webhook'];
    const CHANNEL_LABELS = { ui: 'UI log', telegram: 'Telegram', ntfy: 'ntfy push', email: 'Email', webhook: 'Webhook' };
    const COOLDOWN_SCOPES = ['rule', 'symbol'];
    const OPS_NUM = ['>', '>=', '<', '<=', '==', '!=', 'in', 'not_in'];
    const OPS_TEXT = ['==', '!=', 'in', 'not_in'];
    const FIELD_KINDS = ['field', 'ctx_field', 'text_field'];
    const OPS_WORDS = {
        '>': 'above', '>=': 'at or above', '<': 'below', '<=': 'at or below',
        '==': 'is', '!=': 'is not', 'in': 'is one of', 'not_in': 'is none of',
    };
    /* The bounds mirror `clean()` in atlas/alerts.py: 40..2000 characters, 0..10 prints/levels,
       1..3600 s of window. The store is the enforcement point, so what a field shows is what a save
       keeps — these exist to stop a typo before the request, not to replace the clamp. */
    const LIMITS = {
        chars: [40, 2000], prints: [0, 10], levels: [0, 10],
        once: [0, 86_400], max_per_window: [1, 50], cooldown: [0, 86_400],
    };

    /* The condition catalogue, mirrored from `atlas/alerts.py` (CONDITION_KINDS): what each reading
       is called, whether it compares as a number or as text, whether it comes off the event or the
       snapshot, and how a reader should say it. */
    const CONDITION_KINDS = {
        price: { label: 'Price', unit: '', value: 'number', source: 'event', hint: "the event's own price, else the snapshot's last price" },
        delta: { label: 'Cumulative delta', unit: '', value: 'number', source: 'either', hint: "the snapshot's delta over its window, else a delta the event itself carries" },
        volume: { label: 'Volume', unit: '', value: 'number', source: 'either', hint: "the event's traded volume, else the snapshot's volume over the window" },
        size: { label: 'Size', unit: '', value: 'number', source: 'event', hint: 'the size of the print the event is about' },
        multiple: { label: 'Multiple of threshold', unit: 'x', value: 'number', source: 'event', hint: "how many times the venue's big-trade threshold the print was" },
        levels: { label: 'Levels', unit: '', value: 'number', source: 'event', hint: 'how many price levels the event covered (a sweep, a stacked imbalance)' },
        ticks: { label: 'Ticks moved', unit: 't', value: 'number', source: 'event', hint: 'the distance the event moved — ticks moved, or the distance a level sat away' },
        zscore: { label: 'Speed z-score', unit: 'z', value: 'number', source: 'event', hint: "how far the tape's speed stood out from its own normal" },
        strength: { label: 'Divergence strength', unit: '', value: 'number', source: 'event', hint: 'how strong a CVD divergence read' },
        pct: { label: 'Book pressure', unit: '%', value: 'number', source: 'event', hint: "one side's weight against its own normal, in percent" },
        share: { label: 'Share of resting size', unit: '', value: 'number', source: 'event', hint: "how much of a level's resting size a print took, or a refill replaced (0–1)" },
        tape_speed: { label: 'Tape speed', unit: '/s', value: 'number', source: 'ctx', hint: "prints per second over the snapshot's window" },
        spread_ticks: { label: 'Spread', unit: 't', value: 'number', source: 'ctx', hint: "the snapshot's spread in ticks" },
        session: { label: 'Session', unit: '', value: 'text', source: 'ctx', hint: 'the session name the snapshot carries (london, us, asia) — use in to list several' },
        side: { label: 'Side', unit: '', value: 'text', source: 'event', hint: 'the aggressive side: buy or sell (bid/ask are read as the same thing)' },
        event_kind: { label: 'Event kind', unit: '', value: 'text', source: 'event', hint: "the event's own kind field — a CVD divergence's direction, for example" },
        state: { label: 'State', unit: '', value: 'text', source: 'event', hint: "the event's state (a radar level's defended / confirmed / spent / failed)" },
        time: { label: 'Time of day', unit: 'min', value: 'number', source: 'either', hint: "minutes since local midnight for the event's stamp (09:30 = 570)" },
        field: { label: 'Event field', unit: '', value: 'number', source: 'event', hint: 'any numeric field of the event by name (params.field) — for one this catalogue does not name yet' },
        ctx_field: { label: 'Snapshot field', unit: '', value: 'number', source: 'ctx', hint: 'any numeric field of the snapshot by name (params.field)' },
        text_field: { label: 'Event text field', unit: '', value: 'text', source: 'event', hint: 'any text field of the event by name (params.field)' },
    };

    const STYLE = `
.ab-grid { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; margin-bottom: 8px; }
.ab-field { display: flex; flex-direction: column; gap: 3px; }
.ab-field > label { font-size: 11px; opacity: .8; }
.ab-field input[type="text"], .ab-field input[type="number"] { width: 110px; }
.ab-field.ab-wide input[type="text"] { width: 200px; }
.ab-cond { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; padding: 6px 0;
    border-top: 1px solid var(--border); }
.ab-cond:first-child { border-top: 0; }
.ab-cond input[type="text"], .ab-cond input[type="number"] { width: 110px; }
.ab-cond select { min-width: 150px; }
.ab-hint { font-size: 11px; opacity: .7; }
.ab-block { white-space: pre-wrap; font-size: 11.5px; background: rgba(255,255,255,.03);
    border: 1px solid var(--border); border-radius: 4px; padding: 6px 8px; margin: 6px 0 0; }
.ab-met { color: inherit; }
.ab-unmet { opacity: .6; }
.ab-msg { font-size: 11.5px; opacity: .85; }
.ab-sect { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; opacity: .55;
    margin: 10px 0 4px; }`;

    function escape(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function num(value, fallback) {
        if (value === null || value === undefined || String(value).trim() === '') return fallback;
        const out = Number(value);
        return Number.isFinite(out) ? out : fallback;
    }

    function clamp(value, lo, hi, fallback) {
        const out = num(value, fallback);
        return Math.min(Math.max(out, lo), hi);
    }

    /* ── the catalogue (pure) ─────────────────────────────────────────────────────────────── */

    function catalog() {
        if (typeof window !== 'undefined' && window.OFAPALERTS && typeof window.OFAPALERTS.kinds === 'function') {
            const rows = window.OFAPALERTS.kinds();
            if (Array.isArray(rows) && rows.length) return rows;
        }
        return [];
    }

    function kindLabel(kind) {
        const row = catalog().find((r) => r.kind === kind);
        return row ? row.label : String(kind || '').replace(/_/g, ' ');
    }

    function specFor(kind) {
        if (typeof window !== 'undefined' && window.OFAPALERTS && typeof window.OFAPALERTS.paramSpec === 'function') {
            const rows = window.OFAPALERTS.paramSpec(kind);
            if (Array.isArray(rows)) return rows;
        }
        return [];
    }

    function paramField(kind, key) {
        return specFor(kind).find((field) => field && field.key === key) || null;
    }

    function conditionLabel(kind) {
        const spec = CONDITION_KINDS[kind];
        return spec ? spec.label : String(kind || '');
    }

    function opsFor(kind) {
        const spec = CONDITION_KINDS[kind];
        return spec && spec.value === 'text' ? OPS_TEXT.slice() : OPS_NUM.slice();
    }

    function opWords(op) {
        return OPS_WORDS[op] || String(op || '');
    }

    function channelLabel(name) {
        return CHANNEL_LABELS[name] || String(name || '');
    }

    function needsField(kind) {
        return FIELD_KINDS.indexOf(kind) >= 0;
    }

    /* Is the evidence snapshot on for this rule? A rule carries an object when it is on (`false` or
       nothing when it is off); the form's own draft carries the same object with an `enabled` flag,
       so both shapes answer through here. */
    function contextOn(rule) {
        const ctx = (rule || {}).context;
        if (ctx === true) return true;
        if (!ctx || typeof ctx !== 'object') return false;
        return ctx.enabled === undefined ? true : !!ctx.enabled;
    }

    /* ── a draft (what the form holds) and the rule it becomes (pure) ─────────────────────── */

    function emptyCondition() {
        return { kind: 'delta', op: '<=', value: '', field: '' };
    }

    function newDraft(kind, nowMs) {
        const stamp = nowMs == null ? Date.now() : Number(nowMs);
        return {
            id: NEW_RULE_PREFIX + Number(stamp).toString(36),
            name: '', kind: kind || 'sweep', params: {}, conditions: [], match: 'all',
            enabled: true, channels: ['ui', 'telegram'], cooldown_s: '15', cooldown_scope: 'rule',
            once_per_window_s: '0', max_per_window: '1',
            context: { enabled: false, format: 'text', max_chars: '', prints: '', levels: '',
                       channels: ['telegram', 'ntfy', 'email', 'webhook'] },
        };
    }

    function setMembers(field) {
        /* The members a set field offers, lower-cased for comparison; [] when the catalogue gives
           none (then the typed list stands, as it always did). */
        return (field && Array.isArray(field.options) ? field.options : [])
            .map((member) => String(member).toLowerCase());
    }

    function splitSet(field, raw) {
        /* A typed set param split into the members the kind really reads and the ones it never can.
           Canonical spelling comes from the catalogue, so 'BUY' becomes 'buy' — the engine compares
           lower-cased, but the rule's own text should read the way the panel offers it. */
        const text = String(raw == null ? '' : raw).trim();
        const members = setMembers(field);
        const typed = text.split(',').map((part) => part.trim()).filter(Boolean);
        if (!members.length) return { known: typed, unknown: [] };
        const known = [], unknown = [];
        typed.forEach((part) => {
            const at = members.indexOf(part.toLowerCase());
            if (at < 0) {
                unknown.push(part);
            } else if (known.indexOf(field.options[at]) < 0) {
                known.push(field.options[at]);
            }
        });
        return { known: known, unknown: unknown };
    }

    function coerceParam(field, raw) {
        const text = String(raw == null ? '' : raw).trim();
        if (field && field.kind === 'set') {
            const parts = splitSet(field, text);
            return parts.known.length ? parts.known : undefined;
        }
        if (text === '') return undefined;
        if (field && typeof field.min === 'number') {
            const value = Number(text);
            if (!Number.isFinite(value)) return undefined;
            const ceiling = typeof field.max === 'number' ? field.max : Infinity;
            return Math.min(Math.max(value, field.min), ceiling);
        }
        if (field && Array.isArray(field.options) && field.options.length) {
            return field.options.indexOf(text) >= 0 ? text : undefined;
        }
        if (field && field.kind === 'check') return text === 'true';
        return text;
    }

    function coerceConditionValue(kind, raw) {
        const text = String(raw == null ? '' : raw).trim();
        if (!text) return '';
        const spec = CONDITION_KINDS[kind];
        if (!spec || spec.value !== 'number') return text;
        if (text.indexOf(',') >= 0) {
            return text.split(',').map((part) => Number(part.trim()))
                .filter((value) => Number.isFinite(value));
        }
        const value = Number(text);
        return Number.isFinite(value) ? value : text;
    }

    /* The drafted rule as the API takes it. Every key the engine reads is spelled once, here. */
    function ruleFromDraft(draft) {
        const d = draft || {};
        const kind = String(d.kind || '');
        const params = {};
        Object.keys(d.params || {}).forEach((key) => {
            const value = coerceParam(paramField(kind, key), d.params[key]);
            if (value !== undefined) params[key] = value;
        });
        const conditions = (d.conditions || []).filter(Boolean).map((cond) => {
            const entry = {
                kind: String(cond.kind || ''),
                op: String(cond.op || ''),
                value: coerceConditionValue(cond.kind, cond.value),
            };
            if (needsField(cond.kind) && String(cond.field || '').trim()) {
                entry.params = { field: String(cond.field).trim() };
            }
            return entry;
        });
        const ctx = d.context || {};
        const context = ctx.enabled
            ? { format: ctx.format, channels: (ctx.channels || []).slice() }
            : false;
        if (ctx.enabled) {
            const chars = num(ctx.max_chars, null);
            if (chars != null) context.max_chars = clamp(chars, LIMITS.chars[0], LIMITS.chars[1], chars);
            const prints = num(ctx.prints, null);
            if (prints != null) context.prints = clamp(prints, LIMITS.prints[0], LIMITS.prints[1], prints);
            const levels = num(ctx.levels, null);
            if (levels != null) context.levels = clamp(levels, LIMITS.levels[0], LIMITS.levels[1], levels);
        }
        const rule = {
            id: String(d.id || ''),
            name: String(d.name || '').trim() || (kindLabel(kind) + ' with conditions'),
            kind: kind,
            params: params,
            enabled: d.enabled === undefined ? true : !!d.enabled,
            cooldown_s: clamp(d.cooldown_s, LIMITS.cooldown[0], LIMITS.cooldown[1], 30),
            cooldown_scope: COOLDOWN_SCOPES.indexOf(String(d.cooldown_scope || 'rule')) >= 0
                ? String(d.cooldown_scope) : 'rule',
            once_per_window_s: clamp(d.once_per_window_s, LIMITS.once[0], LIMITS.once[1], 0),
            max_per_window: Math.round(clamp(d.max_per_window, LIMITS.max_per_window[0],
                                             LIMITS.max_per_window[1], 1)),
            channels: (d.channels || []).filter((name) => CONTEXT_CHANNELS.indexOf(name) >= 0),
            conditions: conditions,
            match: MATCH_MODES.indexOf(String(d.match || 'all')) >= 0 ? String(d.match) : 'all',
            context: context,
        };
        return rule;
    }

    /* A saved rule back into the form's own shape, so the picker can load one and edit it. */
    function draftFromRule(rule) {
        const r = rule || {};
        const draft = newDraft(r.kind || 'sweep');
        draft.id = String(r.id || draft.id);
        draft.name = String(r.name || '');
        draft.params = {};
        Object.keys(r.params || {}).forEach((key) => {
            const value = r.params[key];
            draft.params[key] = Array.isArray(value) ? value.join(',') : String(value == null ? '' : value);
        });
        draft.enabled = r.enabled !== false;
        draft.conditions = (Array.isArray(r.conditions) ? r.conditions : []).map((cond) => ({
            kind: String((cond || {}).kind || ''), op: String((cond || {}).op || ''),
            value: String((cond || {}).value == null ? '' : (cond || {}).value),
            field: String(((cond || {}).params || {}).field || ''),
        }));
        draft.match = MATCH_MODES.indexOf(String(r.match || 'all')) >= 0 ? String(r.match) : 'all';
        draft.channels = (Array.isArray(r.channels) ? r.channels : ['ui'])
            .filter((name) => CONTEXT_CHANNELS.indexOf(String(name)) >= 0).map(String);
        if (!draft.channels.length) draft.channels = ['ui'];
        draft.cooldown_s = String(num(r.cooldown_s, 0));
        draft.cooldown_scope = COOLDOWN_SCOPES.indexOf(String(r.cooldown_scope || 'rule')) >= 0
            ? String(r.cooldown_scope) : 'rule';
        draft.once_per_window_s = String(num(r.once_per_window_s, 0));
        draft.max_per_window = String(num(r.max_per_window, 1));
        const ctx = r.context;
        if (ctx && typeof ctx === 'object') {
            draft.context = {
                enabled: true,
                format: CONTEXT_FORMATS.indexOf(String(ctx.format || 'text')) >= 0 ? String(ctx.format) : 'text',
                max_chars: ctx.max_chars == null ? '' : String(ctx.max_chars),
                prints: ctx.prints == null ? '' : String(ctx.prints),
                levels: ctx.levels == null ? '' : String(ctx.levels),
                channels: (Array.isArray(ctx.channels) ? ctx.channels : ['telegram', 'ntfy', 'email', 'webhook'])
                    .filter((name) => CONTEXT_CHANNELS.indexOf(String(name)) >= 0).map(String),
            };
        }
        return draft;
    }

    /* ── what is wrong with a draft, in sentences (pure) ──────────────────────────────────── */

    function issuesFor(rule, draft) {
        const out = [];
        const known = catalog().map((row) => row.kind);
        if (!rule || !String(rule.kind || '')) {
            out.push('pick what this rule watches');
        } else if (known.length && known.indexOf(rule.kind) < 0) {
            out.push("'" + rule.kind + "' is not a kind the alert engine evaluates");
        }
        /* Set params: the coerce keeps only members the kind reads, so a typo never becomes an
           unmatchable rule — but silence would hide it too. When the draft is at hand, name every
           typed member the kind cannot read. */
        if (draft) {
            specFor(rule && rule.kind).filter((field) => field.kind === 'set').forEach((field) => {
                const parts = splitSet(field, (draft.params || {})[field.key]);
                if (!parts.unknown.length) return;
                const members = (field.options || []).join(', ');
                out.push(String(field.label || field.key) + ": '" + parts.unknown.join("', '") + "' "
                    + (parts.unknown.length > 1 ? 'are not members' : 'is not a member')
                    + ' this kind watches — it reads: ' + members);
            });
        }
        (rule && rule.conditions ? rule.conditions : []).forEach((cond, index) => {
            const where = 'condition ' + (index + 1);
            if (!CONDITION_KINDS[cond.kind]) {
                out.push(where + ": there is no reading called '" + String(cond.kind || '') + "'");
                return;
            }
            if (opsFor(cond.kind).indexOf(cond.op) < 0) {
                out.push(where + ": '" + String(cond.op || '') + "' is not a comparison "
                    + conditionLabel(cond.kind).toLowerCase() + ' understands');
            }
            const empty = cond.value === '' || cond.value == null
                || (Array.isArray(cond.value) && !cond.value.length);
            if (empty) {
                out.push(where + ': give it a value to compare against, or the engine reads it as '
                    + 'never met');
            }
            if (needsField(cond.kind) && !String((cond.params || {}).field || '').trim()) {
                out.push(where + ': name the ' + (cond.kind === 'ctx_field' ? 'snapshot' : 'event')
                    + ' field to read');
            }
        });
        const ctx = rule && rule.context;
        if (contextOn(rule)) {
            const rides = (ctx.channels || []).filter((name) => (rule.channels || []).indexOf(name) >= 0);
            if (!rides.length) {
                out.push('the snapshot has no channel to ride: the rule does not send anywhere it '
                    + 'could be attached to');
            }
        }
        return out;
    }

    function describeCondition(cond) {
        if (!cond || !CONDITION_KINDS[cond.kind]) {
            return "unknown reading '" + String((cond || {}).kind || '') + "'";
        }
        const spec = CONDITION_KINDS[cond.kind];
        const unit = spec.unit ? ' ' + spec.unit : '';
        /* A form row keeps the field beside the value; a saved rule keeps it in `params`. */
        const name = String(cond.field || (cond.params || {}).field || '').trim();
        const field = needsField(cond.kind) && name ? "'" + name + "' " : '';
        let value = cond.value;
        if (Array.isArray(value)) value = value.join(', ');
        return conditionLabel(cond.kind) + ' ' + field + opWords(cond.op) + ' '
            + String(value == null || value === '' ? '(nothing)' : value) + unit;
    }

    function describeConditions(rule) {
        const conds = (rule && rule.conditions) || [];
        if (!conds.length) return 'no extra conditions — just the kind and its thresholds';
        const words = conds.map(describeCondition);
        const joiner = (rule && rule.match) === 'any' ? ' OR ' : ' AND ';
        return ((rule && rule.match) === 'any' ? 'any of: ' : 'all of: ') + words.join(joiner);
    }

    function describeTiming(rule) {
        const bits = [];
        const cooldown = num((rule || {}).cooldown_s, 0);
        bits.push(cooldown > 0 ? cooldown + 's cooldown' : 'no cooldown');
        if ((rule || {}).cooldown_scope === 'symbol') bits.push('counted per instrument');
        const window = num((rule || {}).once_per_window_s, 0);
        if (window > 0) {
            bits.push('at most ' + num((rule || {}).max_per_window, 1) + ' per ' + window + 's window');
        }
        return bits.join(' · ');
    }

    function describeContext(rule) {
        const ctx = (rule || {}).context;
        if (!contextOn(rule)) return 'no evidence snapshot';
        const bits = [];
        if (ctx.format) bits.push(ctx.format);
        if (ctx.max_chars != null) bits.push('≤ ' + ctx.max_chars + ' chars');
        if (ctx.prints != null) bits.push(ctx.prints + ' prints');
        if (ctx.levels != null) bits.push(ctx.levels + ' levels');
        bits.push('to ' + ((ctx.channels || []).map(channelLabel).join(', ') || 'no channel'));
        return 'snapshot: ' + bits.join(' · ');
    }

    function summaryText(rule) {
        return [describeConditions(rule), describeTiming(rule), describeContext(rule)].join(' · ');
    }

    /* ── the test-fire answer, as words (pure) ────────────────────────────────────────────── */

    function answerFor(payload, draft) {
        const p = payload || {};
        const wantsBlock = contextOn(draft);
        if (p.ok !== true) {
            return {
                kind: 'warn',
                text: String(p.error || p.detail || '') || ('the test route did not answer — the rule '
                    + 'saves either way, and the engine evaluates it on the live stream'),
                block: '',
            };
        }
        const failed = (p.gates || []).find((gate) => gate && gate.ok === false);
        const text = p.fires
            ? 'would fire on ' + String(p.origin || 'the last real event')
            : 'would not fire on ' + String(p.origin || 'the last real event')
                + (failed ? ' — ' + String(failed.detail || failed.gate) : '');
        const block = String(p.context || '');
        const gate = String(p.context_gate || '');
        return {
            kind: p.fires ? 'ok' : 'warn', text: text,
            block: block || (wantsBlock
                ? (gate === 'no-channel'
                    ? 'no snapshot — none of this rule' + "'s channels carries a block (telegram, "
                        + 'ntfy, email or webhook does)'
                    : gate === 'off'
                        ? 'no snapshot — the evidence master switch is off'
                        : 'nothing to show: the snapshot was empty for this event')
                : 'no snapshot — switch the evidence attachment on to carry one'),
        };
    }

    function conditionRows(answer) {
        return ((answer || {}).conditions || []).map((row) => ({
            met: !!row.met, label: String(row.label || row.kind || ''),
            said: describeCondition({ kind: row.kind, op: row.op, value: row.value,
                                      params: row.params || {}, field: (row.params || {}).field }),
            read: row.read == null ? '' : String(row.read),
            why: String(row.why || ''),
        }));
    }

    /* ── markup (pure) ────────────────────────────────────────────────────────────────────── */

    function optionsHtml(values, chosen, labels) {
        return values.map((value) => '<option value="' + escape(value) + '"'
            + (String(chosen) === String(value) ? ' selected' : '') + '>'
            + escape(labels ? labels(value) : value) + '</option>').join('');
    }

    function paramInputsHtml(draft) {
        const fields = specFor(draft.kind);
        if (!fields.length) {
            return '<div class="ab-hint">the alert catalogue is not loaded in this page, so this panel '
                + 'cannot offer the thresholds for a kind — open the Alerts view, which loads it</div>';
        }
        return fields.map((field) => {
            const raw = (draft.params || {})[field.key];
            const value = raw == null ? '' : String(raw);
            const id = 'alertBuilderParam_' + field.key;
            const title = escape([field.hint, field.unit ? 'unit: ' + field.unit : '']
                .filter(Boolean).join(' — '));
            if (field.kind === 'set') {
                return '<div class="ab-field"><label for="' + id + '">' + escape(field.label)
                    + '</label><input type="text" id="' + id + '" data-ab-param="' + escape(field.key)
                    + '" value="' + escape(value) + '" placeholder="'
                    + escape((field.options || []).join(',')) + '" title="' + title
                    + ' (comma-separated)"></div>';
            }
            if (field.kind === 'check') {
                return '<div class="ab-field"><label class="switch"><input type="checkbox" id="' + id
                    + '" data-ab-param="' + escape(field.key) + '"' + (value === 'true' ? ' checked' : '')
                    + '> ' + escape(field.label) + '</label></div>';
            }
            return '<div class="ab-field"><label for="' + id + '">' + escape(field.label) + '</label>'
                + '<input type="text" id="' + id + '" data-ab-param="' + escape(field.key)
                + '" value="' + escape(value) + '" title="' + title + '"></div>';
        }).join('');
    }

    function conditionRowHtml(cond, index) {
        const kinds = Object.keys(CONDITION_KINDS);
        const spec = CONDITION_KINDS[cond.kind] || CONDITION_KINDS.delta;
        const ops = opsFor(cond.kind);
        const label = conditionLabel(cond.kind);
        const placeholder = spec.value === 'number' ? 'e.g. -300, or 1,2,3 for a list'
            : 'e.g. ' + (cond.kind === 'session' ? 'london,us' : 'sell');
        return '<div class="ab-cond" data-ab-row="' + index + '">'
            + '<div class="ab-field"><label for="alertBuilderRow_' + index + '_kind">Reading</label>'
            + '<select id="alertBuilderRow_' + index + '_kind" data-ab-cond="kind" data-ab-index="'
            + index + '" title="' + escape(spec.hint || '') + '">'
            + optionsHtml(kinds, cond.kind, conditionLabel) + '</select></div>'
            + '<div class="ab-field"><label for="alertBuilderRow_' + index + '_op">Comparison</label>'
            + '<select id="alertBuilderRow_' + index + '_op" data-ab-cond="op" data-ab-index="' + index
            + '">' + optionsHtml(ops, cond.op, opWords) + '</select></div>'
            + '<div class="ab-field"><label for="alertBuilderRow_' + index + '_value">Value'
            + (spec.unit ? ' (' + escape(spec.unit) + ')' : '') + '</label>'
            + '<input type="text" id="alertBuilderRow_' + index + '_value" data-ab-cond="value" '
            + 'data-ab-index="' + index + '" value="' + escape(String(cond.value == null ? '' : cond.value))
            + '" placeholder="' + escape(placeholder) + '" title="' + escape(label + ' — '
            + spec.hint) + '"></div>'
            + (needsField(cond.kind)
                ? '<div class="ab-field"><label for="alertBuilderRow_' + index + '_field">Field</label>'
                    + '<input type="text" id="alertBuilderRow_' + index + '_field" data-ab-cond="field" '
                    + 'data-ab-index="' + index + '" value="' + escape(cond.field || '')
                    + '" placeholder="e.g. multiple"></div>'
                : '')
            + '<div class="ab-field"><label>&nbsp;</label>'
            + '<button type="button" class="btn small" data-ab-act="remove" data-ab-index="' + index
            + '" title="Drop this reading — the rule goes back to its kind and thresholds alone.">'
            + 'remove</button></div></div>';
    }

    function channelSwitchesHtml(attr, chosen, title) {
        return CONTEXT_CHANNELS.map((name) => (
            '<label class="switch" title="' + escape(title) + '"><input type="checkbox" id="'
            + 'alertBuilder' + (attr === 'chan' ? 'Chan_' : 'CtxChan_') + name + '" data-ab-' + attr
            + '="' + name + '"' + ((chosen || []).indexOf(name) >= 0 ? ' checked' : '') + '> '
            + escape(channelLabel(name)) + '</label>')).join('');
    }

    function formHtml(draft, opts) {
        const d = draft || newDraft();
        const o = opts || {};
        const rules = Array.isArray(o.rules) ? o.rules : [];
        const ctx = d.context || { enabled: false, format: 'text', channels: [] };
        const known = catalog();
        const kindOptions = known.length
            ? optionsHtml(known.map((row) => row.kind), d.kind, kindLabel)
            : optionsHtml([d.kind], d.kind, kindLabel);
        const loadOptions = '<option value="">— new rule —</option>' + rules.map((rule) => (
            '<option value="' + escape(rule.id) + '"'
            + (String(rule.id) === String(d.id) ? ' selected' : '') + '>'
            + escape(rule.name + '  (' + rule.kind + ')')
            + '</option>')).join('');
        return ''
            + '<div class="ab-sect">The rule</div>'
            + '<div class="ab-grid">'
            + '<div class="ab-field"><label for="alertBuilderLoad">Load a saved rule</label>'
            + '<select id="alertBuilderLoad" data-ab-act="load" data-ab-change="1">' + loadOptions
            + '</select></div>'
            + '<div class="ab-field ab-wide"><label for="alertBuilderName">Name</label>'
            + '<input type="text" id="alertBuilderName" value="' + escape(d.name)
            + '" placeholder="e.g. sell sweep into a negative delta"></div>'
            + '<div class="ab-field"><label for="alertBuilderKind">Base kind</label>'
            + '<select id="alertBuilderKind" data-ab-act="kind" data-ab-change="1">' + kindOptions
            + '</select></div>'
            + '<label class="switch"><input type="checkbox" id="alertBuilderEnabled"'
            + (d.enabled === false ? '' : ' checked') + '> enabled</label></div>'
            + '<div class="ab-sect">Thresholds this kind reads</div>'
            + '<div class="ab-grid">' + paramInputsHtml(d) + '</div>'
            + '<div class="ab-sect">Conditions — all of them, or any one of them</div>'
            + '<div class="ab-grid"><div class="ab-field"><label for="alertBuilderMatch">Combine with'
            + '</label><select id="alertBuilderMatch" data-ab-change="1">'
            + optionsHtml(MATCH_MODES, d.match, (m) => (m === 'any' ? 'any one of them (OR)' : 'all of them (AND)'))
            + '</select></div><div class="ab-field"><label>&nbsp;</label>'
            + '<button type="button" class="btn small" data-ab-act="add" title="Add a second reading '
            + 'this rule has to agree with (or, in OR mode, one that is enough).">+ condition</button>'
            + '</div></div>'
            + '<div id="alertBuilderConditions">'
            + ((d.conditions || []).length
                ? d.conditions.map(conditionRowHtml).join('')
                : '<div class="ab-hint">no conditions — the rule fires on its kind and thresholds '
                    + 'alone, exactly as a rule written before this panel existed</div>')
            + '</div>'
            + '<div class="ab-sect">Timing</div>'
            + '<div class="ab-grid">'
            + '<div class="ab-field"><label for="alertBuilderCooldown">Cooldown (s)</label>'
            + '<input type="text" id="alertBuilderCooldown" value="' + escape(d.cooldown_s) + '"></div>'
            + '<div class="ab-field"><label for="alertBuilderCooldownScope">Counted</label>'
            + '<select id="alertBuilderCooldownScope">' + optionsHtml(COOLDOWN_SCOPES, d.cooldown_scope,
                (scope) => (scope === 'symbol' ? 'per instrument' : 'per rule')) + '</select></div>'
            + '<div class="ab-field"><label for="alertBuilderWindow">Once per window (s)</label>'
            + '<input type="text" id="alertBuilderWindow" value="' + escape(d.once_per_window_s)
            + '" title="Aligned windows: the first qualifying event in each window fires and the rest '
            + 'of that window stays quiet — 0 turns it off. A sliding cooldown would let the next '
            + 'window fire seconds later."></div>'
            + '<div class="ab-field"><label for="alertBuilderMaxPerWindow">Max per window</label>'
            + '<input type="text" id="alertBuilderMaxPerWindow" value="' + escape(d.max_per_window)
            + '"></div></div>'
            + '<div class="ab-sect">Goes to</div>'
            + '<div class="ab-grid">' + channelSwitchesHtml('chan', d.channels,
                'A delivery channel. The UI log is the app\'s own record; anything else is sent '
                + 'through Settings ▸ alerts.') + '</div>'
            + '<div class="ab-sect">Evidence snapshot on the delivery</div>'
            + '<div class="ab-grid"><label class="switch"><input type="checkbox" id="alertBuilderContextOn"'
            + ' data-ab-act="context-on" data-ab-change="1"' + (ctx.enabled ? ' checked' : '') + '> attach '
            + 'a snapshot</label>'
            + '<div class="ab-field"><label for="alertBuilderContextFormat">Format</label>'
            + '<select id="alertBuilderContextFormat" data-ab-change="1"' + (ctx.enabled ? '' : ' disabled')
            + '>' + optionsHtml(CONTEXT_FORMATS, ctx.format) + '</select></div>'
            + '<div class="ab-field"><label for="alertBuilderContextChars">Max characters</label>'
            + '<input type="text" id="alertBuilderContextChars" value="' + escape(ctx.max_chars)
            + '" placeholder="360" title="Hard cap, marker line included. 40–2000."'
            + (ctx.enabled ? '' : ' disabled') + '></div>'
            + '<div class="ab-field"><label for="alertBuilderContextPrints">Biggest prints</label>'
            + '<input type="text" id="alertBuilderContextPrints" value="' + escape(ctx.prints)
            + '" placeholder="3"' + (ctx.enabled ? '' : ' disabled') + '></div>'
            + '<div class="ab-field"><label for="alertBuilderContextLevels">Nearest walls</label>'
            + '<input type="text" id="alertBuilderContextLevels" value="' + escape(ctx.levels)
            + '" placeholder="3"' + (ctx.enabled ? '' : ' disabled') + '></div></div>'
            + '<div class="ab-grid">' + channelSwitchesHtml('ctx-chan', ctx.channels,
                'Which deliveries may carry the snapshot. The app has the event on screen already, '
                + 'so the UI log is off by default.') + '</div>'
            + '<div class="ab-sect">Rehearse it</div>'
            + '<div class="ab-grid">'
            + '<div class="ab-field"><label>&nbsp;</label>'
            + '<button type="button" class="btn small" data-ab-act="test" title="The engine reads the '
            + 'newest real event of this kind out of its log and reports every gate, each condition, '
            + 'and the exact snapshot the notification would carry.">Test fire</button></div>'
            + '<div class="ab-field"><label>&nbsp;</label>'
            + '<button type="button" class="btn small" data-ab-act="save" title="Save through the same '
            + 'route the Alerts view uses — this is an ordinary rule.">Save rule</button></div>'
            + '<div class="ab-field"><label>&nbsp;</label>'
            + '<button type="button" class="btn small" data-ab-act="reset" title="Start a new rule '
            + 'from scratch (nothing is saved or deleted).">Reset</button></div></div>'
            + '<div class="ab-msg" id="alertBuilderMsg"></div>'
            + '<div class="ab-hint" id="alertBuilderIssues"></div>'
            + '<div class="ab-hint" id="alertBuilderSummary"></div>'
            + '<div class="ab-hint" id="alertBuilderVerdict"></div>'
            + '<pre class="ab-block" id="alertBuilderPreview"></pre>'
            + '<div class="ab-hint" id="alertBuilderReadings"></div>';
    }

    function issuesHtml(issues) {
        const rows = issues || [];
        if (!rows.length) return 'the rule is complete as it stands';
        return rows.map((text) => '· ' + escape(text)).join('<br>');
    }

    function readingsHtml(answer) {
        const rows = conditionRows(answer);
        if (!rows.length) return '';
        return rows.map((row) => (row.met ? 'met · ' : 'not met · ') + escape(row.said)
            + (row.read ? ' — read ' + escape(row.read) : '') + (row.why ? ' (' + escape(row.why) + ')' : ''))
            .join('<br>');
    }

    function pillText(rules) {
        const rows = Array.isArray(rules) ? rules : [];
        const withConditions = rows.filter((rule) => (rule.conditions || []).length).length;
        const withContext = rows.filter((rule) => rule.context).length;
        return rows.length + (rows.length === 1 ? ' rule' : ' rules') + ' · ' + withConditions
            + ' with conditions · ' + withContext + ' carrying a snapshot';
    }

    /* ── the DOM half ─────────────────────────────────────────────────────────────────────── */

    const state = { draft: newDraft(), rules: [], busy: false, answer: null, last: null };

    function el(id) {
        /* A page with no DOM yet (or a selftest parsing this file) reads null and moves on. */
        if (typeof document === 'undefined' || !document) return null;
        return document.getElementById(id);
    }

    function value(id) {
        const node = el(id);
        return node ? String(node.value == null ? '' : node.value) : '';
    }

    function checked(id) {
        const node = el(id);
        return !!(node && node.checked);
    }

    function api(path, options) {
        if (typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options).then((res) => res.json());
    }

    /* What the two writes send. The shell's own `api()` stringifies `body` itself, so the object
       travels as an object here — handing it a string would send a quoted JSON document and the
       route would refuse it. */
    function saveBody(rule) {
        return { method: 'POST', body: rule };
    }

    function testBody(rule, symbol) {
        return { method: 'POST', body: { rule: rule, symbol: String(symbol || '') } };
    }

    function activeSymbol() {
        const fromState = (typeof S !== 'undefined' && S) ? S.symbol : '';
        const select = el('symbolSelect');
        return String(fromState || (select && select.value) || '').toUpperCase();
    }

    function ensureStyles() {
        /* The page may not exist at all (a selftest, or a build with no shell): nothing to add to. */
        if (typeof document === 'undefined' || !document) return;
        if (!document.getElementById('abStyles')) {
            const tag = document.createElement('style');
            tag.id = 'abStyles';
            tag.textContent = STYLE;
            document.head.appendChild(tag);
        }
    }

    /* Read every input back into the draft. Called before any structural re-render and before a
       request, so nothing typed is ever lost to a repaint. */
    function readForm() {
        const draft = state.draft;
        draft.name = value('alertBuilderName');
        draft.kind = value('alertBuilderKind') || draft.kind;
        draft.match = value('alertBuilderMatch') || draft.match || 'all';
        draft.enabled = checked('alertBuilderEnabled');
        draft.cooldown_s = value('alertBuilderCooldown');
        draft.cooldown_scope = value('alertBuilderCooldownScope') || 'rule';
        draft.once_per_window_s = value('alertBuilderWindow');
        draft.max_per_window = value('alertBuilderMaxPerWindow');
        /* With no param inputs on the page (the alert catalogue is missing) the draft's own params
           are kept as they are — a form that cannot show a value must not drop it. */
        const fields = specFor(draft.kind).filter((field) => field && el('alertBuilderParam_' + field.key));
        if (fields.length || !Object.keys(draft.params || {}).length) {
            const params = {};
            fields.forEach((field) => {
                const node = el('alertBuilderParam_' + field.key);
                params[field.key] = field.kind === 'check' ? String(!!node.checked) : String(node.value);
            });
            draft.params = params;
        }
        draft.conditions = (draft.conditions || []).map((cond, index) => {
            const kind = value('alertBuilderRow_' + index + '_kind') || cond.kind;
            return {
                kind: kind,
                op: value('alertBuilderRow_' + index + '_op') || cond.op,
                value: value('alertBuilderRow_' + index + '_value'),
                field: needsField(kind) ? value('alertBuilderRow_' + index + '_field') : '',
            };
        });
        draft.channels = CONTEXT_CHANNELS.filter((name) => checked('alertBuilderChan_' + name));
        draft.context = {
            enabled: checked('alertBuilderContextOn'),
            format: value('alertBuilderContextFormat') || 'text',
            max_chars: value('alertBuilderContextChars'),
            prints: value('alertBuilderContextPrints'),
            levels: value('alertBuilderContextLevels'),
            channels: CONTEXT_CHANNELS.filter((name) => checked('alertBuilderCtxChan_' + name)),
        };
        return draft;
    }

    function setText(id, text) {
        const node = el(id);
        if (node) node.textContent = text == null ? '' : String(text);
    }

    function paint() {
        const host = el(HOST);
        if (host) host.innerHTML = formHtml(state.draft, { rules: state.rules });
        const pill = el(PILL);
        if (pill) pill.textContent = pillText(state.rules);
        const rule = ruleFromDraft(state.draft);
        setText('alertBuilderIssues', issuesHtml(issuesFor(rule, state.draft)));
        setText('alertBuilderSummary', summaryText(rule));
        if (state.answer) paintAnswer(state.answer);
    }

    function paintAnswer(answer) {
        const words = answerFor(answer, state.draft);
        const node = el('alertBuilderVerdict');
        if (node) {
            node.textContent = words.text;
            node.style.color = words.kind === 'ok' ? 'var(--ok, #6cc07a)'
                : words.kind === 'bad' ? 'var(--warn, #e0a33c)' : '';
        }
        setText('alertBuilderPreview', words.block);
        setText('alertBuilderReadings', '');
        const readings = el('alertBuilderReadings');
        if (readings) readings.innerHTML = readingsHtml(answer);
        return words;
    }

    function setMsg(text, bad) {
        const node = el('alertBuilderMsg');
        if (node) {
            node.textContent = text || '';
            node.style.color = bad ? 'var(--warn, #e0a33c)' : '';
        }
    }

    async function load() {
        try {
            const payload = await api('/api/atlas/alert-rules');
            if (payload && payload.ok) {
                state.rules = Array.isArray(payload.rules) ? payload.rules : [];
                const pill = el(PILL);
                if (pill) pill.textContent = pillText(state.rules);
            }
        } catch (e) {
            setMsg('the rule list could not be read: ' + ((e && e.message) || String(e)), true);
        }
    }

    async function saveDraft() {
        if (state.busy) return;
        state.busy = true;
        setMsg('saving…');
        try {
            const rule = ruleFromDraft(readForm());
            const answer = await api('/api/atlas/alert-rules', saveBody(rule));
            if (answer && answer.ok) {
                state.rules = Array.isArray(answer.rules) ? answer.rules : state.rules;
                state.answer = null;
                paint();
                setMsg('saved — ' + rule.name + ' (' + rule.id + ')');
            } else {
                setMsg(String((answer && answer.error) || 'the save was refused'), true);
            }
        } catch (e) {
            setMsg('the save failed: ' + ((e && e.message) || String(e)), true);
        }
        state.busy = false;
    }

    async function testFire() {
        if (state.busy) return;
        state.busy = true;
        setMsg('asking the engine…');
        try {
            const rule = ruleFromDraft(readForm());
            const answer = await api('/api/atlas/alert-rules/test', testBody(rule, activeSymbol()));
            state.answer = answer || {};
            const words = paintAnswer(state.answer);
            setMsg(words.kind === 'ok' ? 'fires on the last real event' : 'read the verdict below',
                   words.kind !== 'ok');
        } catch (e) {
            state.answer = null;
            setMsg('the test failed: ' + ((e && e.message) || String(e)), true);
        }
        state.busy = false;
    }

    function onClick(ev) {
        const button = ev.target.closest ? ev.target.closest('[data-ab-act]') : null;
        if (!button) return;
        const act = button.getAttribute('data-ab-act');
        if (act === 'add') {
            readForm();
            state.draft.conditions = (state.draft.conditions || []).concat([emptyCondition()]);
            paint();
            return;
        }
        if (act === 'remove') {
            const index = Number(button.getAttribute('data-ab-index'));
            readForm();
            state.draft.conditions = (state.draft.conditions || [])
                .filter((_cond, at) => at !== index);
            paint();
            return;
        }
        if (act === 'reset') {
            state.draft = newDraft();
            state.answer = null;
            paint();
            setMsg('a fresh rule — nothing was saved or deleted');
            return;
        }
        if (act === 'test') { void testFire(); return; }
        if (act === 'save') { void saveDraft(); return; }
    }

    function onChange(ev) {
        const node = ev.target;
        if (!node || !node.getAttribute) return;
        const act = node.getAttribute('data-ab-act');
        if (act === 'load') {
            const id = String(node.value || '');
            const found = state.rules.find((rule) => String(rule.id) === id);
            if (found) {
                state.draft = draftFromRule(found);
                state.answer = null;
                paint();
                setMsg('editing ' + found.name + ' — Test fire rehearses it, Save writes it back');
            }
            return;
        }
        if (act === 'kind' || act === 'context-on') {
            readForm();
            state.answer = null;
            paint();
            return;
        }
        if (node.id === 'alertBuilderMatch' || node.id === 'alertBuilderContextFormat') {
            readForm();
            state.answer = null;
            paint();
            return;
        }
        /* Any other edit only changes the summary lines — no repaint, so the caret stays put. */
        readForm();
        setText('alertBuilderIssues', issuesHtml(issuesFor(ruleFromDraft(state.draft), state.draft)));
        setText('alertBuilderSummary', summaryText(ruleFromDraft(state.draft)));
    }

    function watch() {
        if (typeof document === 'undefined' || !document) return;
        ensureStyles();
        const host = el(HOST);
        if (host) {
            host.addEventListener('click', onClick);
            host.addEventListener('change', onChange);
        }
        const section = document.querySelector(VIEW);
        if (section && typeof MutationObserver === 'function') {
            new MutationObserver(function () {
                if (section.classList.contains('active')) void load();
            }).observe(section, { attributes: true, attributeFilter: ['class'] });
        }
        paint();
        void load();
    }

    const surface = {
        escape: escape, num: num, clamp: clamp, catalog: catalog, kindLabel: kindLabel,
        specFor: specFor, paramField: paramField, conditionLabel: conditionLabel, opsFor: opsFor,
        opWords: opWords, channelLabel: channelLabel, needsField: needsField, contextOn: contextOn,
        CONDITION_KINDS: CONDITION_KINDS, MATCH_MODES: MATCH_MODES, OPS_NUM: OPS_NUM, OPS_TEXT: OPS_TEXT,
        CONTEXT_CHANNELS: CONTEXT_CHANNELS, CONTEXT_FORMATS: CONTEXT_FORMATS,
        COOLDOWN_SCOPES: COOLDOWN_SCOPES, LIMITS: LIMITS, NEW_RULE_PREFIX: NEW_RULE_PREFIX,
        emptyCondition: emptyCondition, newDraft: newDraft, coerceParam: coerceParam,
        coerceConditionValue: coerceConditionValue, ruleFromDraft: ruleFromDraft,
        draftFromRule: draftFromRule, issuesFor: issuesFor, describeCondition: describeCondition,
        describeConditions: describeConditions, describeTiming: describeTiming,
        describeContext: describeContext, summaryText: summaryText, answerFor: answerFor,
        conditionRows: conditionRows, formHtml: formHtml, conditionRowHtml: conditionRowHtml,
        issuesHtml: issuesHtml, readingsHtml: readingsHtml, pillText: pillText,
        readForm: readForm, paint: paint, paintAnswer: paintAnswer, load: load, watch: watch,
        saveBody: saveBody, testBody: testBody, onClick: onClick, onChange: onChange,
        state: () => state.draft, rules: () => state.rules,
    };
    if (typeof window !== 'undefined') window.OFAPALERTBUILDER = surface;
    if (typeof module !== 'undefined' && module.exports) module.exports = surface;

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
