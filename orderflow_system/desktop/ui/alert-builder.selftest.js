/* alert-builder.selftest.js — the Condition builder's decisions, pinned without a browser.
 *
 * Everything between "the rule list the server sent" and "a request body / words in the panel" is
 * pure: the condition catalogue mirrored from atlas/alerts.py, the draft -> rule translation (with
 * the store's own clamps), the reverse (a saved rule loaded back into the form), the issues list,
 * the sentences each part of a rule reads as, and the test-fire answer turned into a verdict plus a
 * block. The DOM half is covered by scripts/audit_ui_refs.py (the module is on its JS_FILES list, so
 * its syntax is parsed and its API paths are route-checked) and by this file's last checks, which
 * read the source for the properties a browser would otherwise be needed for: no timers, and the
 * element ids the shell has to provide.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/alert-builder.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPALERTBUILDER;
}
const B = boot();

/* The catalogue `alert-format.js` provides in the app; here it is a stub, because the panel must
   work from whatever that module exports and this file must run with no browser at all. */
const CATALOGUE = [
    { kind: 'sweep', label: 'Sweep' },
    { kind: 'cvd_divergence', label: 'CVD divergence' },
    { kind: 'level_touch', label: 'Price touches a level' },
];
const SPECS = {
    sweep: [
        { key: 'min_levels', label: 'Minimum levels', unit: '', min: 1, max: 50, step: 1 },
        { key: 'min_size', label: 'Minimum size', unit: '', min: 0, max: null, step: 0.01 },
        { key: 'sides', label: 'Sides', kind: 'set', options: ['buy', 'sell'] },
        { key: 'at_price', label: 'Level', unit: '', min: 0, step: 0.5, scope: true },
        { key: 'at_tol', label: 'Tolerance', unit: '±', min: 0, step: 0.1, scope: true },
        { key: 'min_age_s', label: 'Minimum hold', unit: 's', min: 0, step: 1, scope: true },
    ],
};
function withCatalogue(fn) {
    const win = { OFAPALERTS: { kinds: () => CATALOGUE, paramSpec: (kind) => SPECS[kind] || [] } };
    new Function('window', src)(win);
    return fn(win.OFAPALERTBUILDER);
}
const B2 = withCatalogue((surface) => surface);

check('the module exposes its whole surface', () => {
    for (const fn of ['escape', 'num', 'clamp', 'catalog', 'kindLabel', 'specFor', 'paramField',
                      'conditionLabel', 'opsFor', 'opWords', 'channelLabel', 'needsField', 'contextOn',
                      'emptyCondition', 'newDraft', 'coerceParam', 'coerceConditionValue',
                      'ruleFromDraft', 'draftFromRule', 'issuesFor', 'describeCondition',
                      'describeConditions', 'describeTiming', 'describeContext', 'summaryText',
                      'answerFor', 'conditionRows', 'formHtml', 'conditionRowHtml', 'issuesHtml',
                      'readingsHtml', 'pillText', 'readForm', 'paint', 'paintAnswer', 'load', 'watch',
                      'state', 'rules']) {
        assert.strictEqual(typeof B[fn], 'function', fn + ' is missing');
    }
    assert.strictEqual(B.NEW_RULE_PREFIX, 'ab-');
    assert.deepStrictEqual(B.MATCH_MODES, ['all', 'any']);
    assert.deepStrictEqual(B.CONTEXT_FORMATS, ['text', 'csv']);
    assert.deepStrictEqual(B.OPS_NUM, ['>', '>=', '<', '<=', '==', '!=', 'in', 'not_in']);
    assert.deepStrictEqual(B.OPS_TEXT, ['==', '!=', 'in', 'not_in']);
});

check('the condition catalogue mirrors the engine, kind for kind', () => {
    const kinds = Object.keys(B.CONDITION_KINDS);
    assert.deepStrictEqual(kinds.slice().sort(), [
        'ctx_field', 'delta', 'event_kind', 'field', 'levels', 'multiple', 'pct', 'price', 'session',
        'share', 'side', 'size', 'spread_ticks', 'state', 'strength', 'tape_speed', 'text_field',
        'ticks', 'time', 'volume', 'zscore',
    ], 'the catalogue moved — atlas/alerts.py CONDITION_KINDS is the source');
    for (const kind of kinds) {
        const spec = B.CONDITION_KINDS[kind];
        for (const key of ['label', 'unit', 'value', 'source', 'hint']) {
            assert.ok(Object.prototype.hasOwnProperty.call(spec, key), kind + ' is missing ' + key);
        }
        assert.ok(spec.value === 'number' || spec.value === 'text', kind + ': bad value class');
        assert.ok(['event', 'ctx', 'either'].indexOf(spec.source) >= 0, kind + ': bad source');
        assert.ok(String(spec.label).length > 0 && String(spec.hint).length > 0,
            kind + ': a form row needs a label and a hint');
    }
    assert.deepStrictEqual(B.opsFor('delta'), B.OPS_NUM);
    assert.deepStrictEqual(B.opsFor('session'), B.OPS_TEXT);
    assert.strictEqual(B.needsField('field'), true);
    assert.strictEqual(B.needsField('ctx_field'), true);
    assert.strictEqual(B.needsField('text_field'), true);
    assert.strictEqual(B.needsField('delta'), false);
});

check('a fresh draft is off by default — a rule with no extra reading and no snapshot', () => {
    const draft = B.newDraft('sweep', 1_700_000_000_000);
    assert.strictEqual(draft.kind, 'sweep');
    assert.strictEqual(draft.id, 'ab-' + Number(1_700_000_000_000).toString(36));
    assert.deepStrictEqual(draft.conditions, []);
    assert.strictEqual(draft.context.enabled, false);
    assert.strictEqual(B.issuesFor(B.ruleFromDraft(draft)).length, 0, 'an empty draft is complete');
    const rule = B.ruleFromDraft(draft);
    assert.strictEqual(rule.conditions.length, 0);
    assert.strictEqual(rule.context, false, 'no opt-in means no block');
});

check('numbers and bounds are coerced the way the store coerces them', () => {
    assert.strictEqual(B.num('', 7), 7, 'an empty field is not a zero');
    assert.strictEqual(B.num('  ', 7), 7);
    assert.strictEqual(B.num('0', 7), 0);
    assert.strictEqual(B.num('abc', 7), 7);
    assert.strictEqual(B.clamp('99', 0, 10, 1), 10);
    assert.strictEqual(B.clamp('-5', 0, 10, 1), 0);
    withCatalogue((surface) => {
        const rule = surface.ruleFromDraft({
            kind: 'sweep', params: { min_levels: '500', min_size: '-3', sides: 'buy, sell' },
            cooldown_s: '', once_per_window_s: '60', max_per_window: '0',
            context: { enabled: true, channels: ['telegram'], max_chars: '10', prints: '99', levels: '' },
        });
        assert.strictEqual(rule.params.min_levels, 50, "clamped to the spec's own max");
        assert.strictEqual(rule.params.min_size, 0, 'and to its own floor');
        assert.deepStrictEqual(rule.params.sides, ['buy', 'sell'], 'a set param travels as a list');
        assert.strictEqual(rule.cooldown_s, 30, 'an empty cooldown falls back to the default, not to zero');
        assert.strictEqual(rule.once_per_window_s, 60);
        assert.strictEqual(rule.max_per_window, 1, 'never below one fire per window');
        assert.strictEqual(rule.context.max_chars, 40, 'the character cap has a floor');
        assert.strictEqual(rule.context.prints, 10, 'and a ceiling');
        assert.strictEqual('levels' in rule.context, false, 'an empty override is not sent');
        /* A field the form cannot show (a kind with no spec) is not silently made up: the value the
           spec's own bounds allow is what travels, and nothing else is invented. */
        assert.strictEqual(surface.ruleFromDraft({ kind: 'sweep', params: { at_price: '63000.5' } })
            .params.at_price, 63000.5);
        assert.strictEqual(surface.ruleFromDraft({ kind: 'sweep', params: { sides: 'nonsense' } })
            .params.sides, undefined,
            'a set member the kind cannot read never rides into the rule (AB-15)');
    });
});

check('a set param is a member list the kind reads, never free text (AB-15)', () => {
    withCatalogue((surface) => {
        const field = { key: 'sides', label: 'Sides', kind: 'set', options: ['buy', 'sell'] };
        assert.deepStrictEqual(surface.coerceParam(field, 'buy,sell'), ['buy', 'sell']);
        assert.deepStrictEqual(surface.coerceParam(field, 'BUY'), ['buy'],
            "the catalogue's own spelling wins over the typing");
        assert.deepStrictEqual(surface.coerceParam(field, 'buy, sl'), ['buy'],
            'a member the kind cannot read is not kept beside one it can');
        assert.strictEqual(surface.coerceParam(field, 'byu'), undefined,
            'a pure typo leaves the param out — the engine default applies, no silent never-match');
        assert.deepStrictEqual(surface.coerceParam(field, 'sell,buy,sell'), ['sell', 'buy'],
            'duplicates collapse, order kept');
        const draft = { kind: 'sweep', params: { sides: 'byu' } };
        const rule = surface.ruleFromDraft(draft);
        assert.strictEqual(rule.params.sides, undefined);
        const said = surface.issuesFor(rule, draft).join(' | ');
        assert.ok(said.indexOf("Sides: 'byu' is not a member") === 0,
            'the panel names the typo rather than staying quiet: ' + said);
        assert.strictEqual(surface.issuesFor(rule).join(' | '), '',
            'the coerced rule alone holds nothing to name — no sentence is invented for it');
    });
    assert.deepStrictEqual(B.coerceParam({ key: 'states', kind: 'set' }, 'armed, spent'), ['armed', 'spent'],
        'a set field the catalogue gives no members for keeps what was typed');
});

check('a param the catalogue does not describe is not silently dropped', () => {
    const rule = B.ruleFromDraft({ kind: 'sweep', params: { unknown_knob: '3' } });
    assert.strictEqual(rule.params.unknown_knob, '3');
});

check('conditions travel with their kind, their op and their own value class', () => {
    const rule = B.ruleFromDraft({
        kind: 'sweep', match: 'any',
        conditions: [
            { kind: 'side', op: '==', value: 'sell' },
            { kind: 'delta', op: '<=', value: '-300' },
            { kind: 'time', op: '>=', value: '570' },
            { kind: 'field', op: '>', value: '2.5', field: 'multiple' },
            { kind: 'session', op: 'in', value: 'london,us' },
        ],
    });
    assert.strictEqual(rule.match, 'any');
    assert.deepStrictEqual(rule.conditions[0], { kind: 'side', op: '==', value: 'sell' });
    assert.strictEqual(rule.conditions[1].value, -300, 'a numeric reading carries a number');
    assert.strictEqual(rule.conditions[2].value, 570);
    assert.deepStrictEqual(rule.conditions[3].params, { field: 'multiple' });
    assert.strictEqual(rule.conditions[4].value, 'london,us', 'in takes a list');
    const listed = B.ruleFromDraft({ kind: 'sweep', conditions: [{ kind: 'levels', op: 'in', value: '5, 7' }] });
    assert.deepStrictEqual(listed.conditions[0].value, [5, 7]);
    assert.strictEqual(B.ruleFromDraft({ kind: 'sweep', match: 'sometimes' }).match, 'all',
        'an unknown mode reads as the strict one');
});

check('a saved rule loads back into the form without losing anything it holds', () => {
    const saved = {
        id: 'ab-123', name: 'Sweep + delta', kind: 'sweep', enabled: false,
        params: { min_levels: 5, sides: ['sell'] },
        conditions: [{ kind: 'delta', op: '<=', value: -300 }, { kind: 'field', op: '>', value: 2, params: { field: 'multiple' } }],
        match: 'all', cooldown_s: 20, cooldown_scope: 'symbol', once_per_window_s: 300, max_per_window: 2,
        channels: ['ui', 'telegram'],
        context: { format: 'csv', max_chars: 500, prints: 4, levels: 2, channels: ['ntfy'] },
    };
    withCatalogue((surface) => {
        const draft = surface.draftFromRule(saved);
        assert.strictEqual(draft.name, 'Sweep + delta');
        assert.strictEqual(draft.enabled, false, 'a rule saved switched off comes back switched off');
        assert.strictEqual(draft.params.min_levels, '5', 'a param comes back as the field holds it');
        assert.strictEqual(draft.params.sides, 'sell', 'a set param comes back comma-joined');
        assert.strictEqual(draft.conditions[0].value, '-300');
        assert.strictEqual(draft.conditions[1].field, 'multiple');
        assert.strictEqual(draft.cooldown_scope, 'symbol');
        assert.strictEqual(draft.context.enabled, true, 'a context object is an opt-in');
        assert.strictEqual(draft.context.format, 'csv');
        assert.strictEqual(draft.context.max_chars, '500');
        /* Round trip: the rule that comes back out of the form is the rule that went in. */
        const again = surface.ruleFromDraft(draft);
        assert.strictEqual(again.id, 'ab-123');
        assert.strictEqual(again.enabled, false);
        assert.strictEqual(again.cooldown_scope, 'symbol');
        assert.strictEqual(again.once_per_window_s, 300);
        assert.strictEqual(again.params.min_levels, 5);
        assert.strictEqual(again.conditions[1].params.field, 'multiple');
        assert.strictEqual(again.context.format, 'csv');
        assert.deepStrictEqual(again.context.channels, ['ntfy']);
        /* And the panel says the same thing about the saved rule as it does about the draft. */
        assert.strictEqual(surface.summaryText(again), surface.summaryText(saved));
        assert.strictEqual(surface.contextOn(again), true);
        assert.strictEqual(surface.contextOn({ context: false }), false);
        assert.strictEqual(surface.contextOn({}), false);
        assert.strictEqual(surface.contextOn({ context: { enabled: false } }), false);
    });
});

check('a rule with no context key at all reads as "no snapshot"', () => {
    const draft = B.draftFromRule({ id: 'x', name: 'Plain', kind: 'sweep', params: {}, channels: ['ui'] });
    assert.strictEqual(draft.context.enabled, false);
    const rule = B.ruleFromDraft(draft);
    assert.strictEqual(rule.context, false);
    assert.strictEqual(rule.channels.length, 1, 'the UI log survives the round trip');
});

check('what is wrong is said in sentences, and never invented', () => {
    withCatalogue((surface) => {
        const bad = surface.issuesFor(surface.ruleFromDraft({
            kind: 'not_a_kind',
            conditions: [
                { kind: 'nonsense', op: '>', value: '1' },
                { kind: 'delta', op: '~', value: '5' },
                { kind: 'delta', op: '<=', value: '' },
                { kind: 'field', op: '>', value: '1', field: '' },
            ],
            channels: ['ui'],
            context: { enabled: true, channels: ['telegram'] },
        }));
        assert.strictEqual(bad.length, 6, bad.join(' | '));
        assert.ok(bad[0].indexOf('not a kind the alert engine evaluates') > 0);
        assert.ok(bad.some((text) => text.indexOf('no reading called') > 0));
        assert.ok(bad.some((text) => text.indexOf('is not a comparison') > 0));
        assert.ok(bad.some((text) => text.indexOf('give it a value') > 0));
        assert.ok(bad.some((text) => text.indexOf('name the event field') > 0));
        assert.ok(bad.some((text) => text.indexOf('no channel to ride') > 0));
        const good = surface.issuesFor(surface.ruleFromDraft({
            kind: 'sweep', channels: ['ui', 'telegram'],
            conditions: [{ kind: 'delta', op: '<=', value: '-300' }],
            context: { enabled: true, channels: ['telegram'] },
        }));
        assert.deepStrictEqual(good, [], good.join(' | '));
        assert.strictEqual(surface.issuesHtml([]), 'the rule is complete as it stands');
        assert.strictEqual(surface.issuesHtml(['two']), '· two');
        assert.strictEqual(surface.issuesHtml(['two', '<bad>']), '· two<br>· &lt;bad&gt;');
    });
});

check('a rule reads as words, conditions and all', () => {
    const rule = B.ruleFromDraft({
        kind: 'sweep', params: { min_levels: 5 }, match: 'all',
        conditions: [{ kind: 'side', op: '==', value: 'sell' }, { kind: 'delta', op: '<=', value: -300 }],
        cooldown_s: 15, cooldown_scope: 'symbol', once_per_window_s: 300, max_per_window: 2,
        channels: ['ui', 'telegram'],
        context: { enabled: true, format: 'text', max_chars: 500, prints: 4, levels: 2, channels: ['telegram'] },
    });
    assert.strictEqual(B.describeCondition(rule.conditions[0]), 'Side is sell');
    assert.strictEqual(B.describeCondition(rule.conditions[1]), 'Cumulative delta at or below -300');
    assert.strictEqual(B.describeConditions(rule), 'all of: Side is sell AND Cumulative delta at or below -300');
    assert.ok(B.describeTiming(rule).indexOf('15s cooldown') === 0);
    assert.ok(B.describeTiming(rule).indexOf('counted per instrument') > 0);
    assert.ok(B.describeTiming(rule).indexOf('at most 2 per 300s window') > 0);
    assert.ok(B.describeContext(rule).indexOf('snapshot: text') === 0);
    assert.ok(B.describeContext(rule).indexOf('≤ 500 chars') > 0);
    assert.ok(B.describeContext(rule).indexOf('4 prints') > 0);
    assert.ok(B.describeContext(rule).indexOf('3 levels') === -1, 'levels came from the rule, not a default');
    assert.strictEqual(B.describeConditions({ conditions: [], match: 'all' }),
        'no extra conditions — just the kind and its thresholds');
    assert.strictEqual(B.describeConditions({ conditions: [{ kind: 'side', op: '==', value: 'buy' }], match: 'any' }),
        'any of: Side is buy');
    assert.strictEqual(B.describeCondition({ kind: 'ghost', op: '>' }),
        "unknown reading 'ghost'");
    assert.strictEqual(B.describeContext({}), 'no evidence snapshot');
});

check('the test-fire answer becomes a verdict and the block the channel would send', () => {
    const draft = B.newDraft('sweep');
    const fired = B.answerFor({
        ok: true, fires: true, origin: 'the newest sweep event (12s ago)',
        gates: [{ gate: 'kind', ok: true }],
        conditions: [{ kind: 'delta', op: '<=', value: -300, met: true, read: -412.8, label: 'Cumulative delta' }],
        context: '12:00:01 · BTCUSDT · 63,120.50\nsweep — SELL · levels 7',
    }, draft);
    assert.strictEqual(fired.kind, 'ok');
    assert.ok(fired.text.indexOf('would fire') === 0);
    assert.ok(fired.block.indexOf('BTCUSDT') > 0);

    const refused = B.answerFor({ ok: true, fires: false, origin: 'the newest sweep event (12s ago)',
        gates: [{ gate: 'conditions', ok: false, detail: 'at least one condition is not met' }] }, draft);
    assert.strictEqual(refused.kind, 'warn');
    assert.ok(refused.text.indexOf('would not fire') === 0);
    assert.ok(refused.text.indexOf('at least one condition is not met') > 0);

    const noEvent = B.answerFor({ ok: false, error: 'no sweep event has been seen yet, so there is nothing real to rehearse against' }, draft);
    assert.strictEqual(noEvent.kind, 'warn');
    assert.ok(noEvent.text.indexOf('no sweep event has been seen') === 0);
    assert.strictEqual(noEvent.block, '');

    const noRoute = B.answerFor({}, draft);
    assert.ok(noRoute.text.indexOf('the test route did not answer') === 0,
        'a missing route is named, and never dressed up as a result');
    assert.strictEqual(noRoute.block, '',
        'a build without the route carries no block — the panel never substitutes one of its own');

    const wantsBlock = B.answerFor({ ok: true, fires: true, gates: [], context: '' },
        { context: { enabled: true, channels: ['telegram'] } });
    assert.ok(wantsBlock.block.indexOf('snapshot was empty') > 0);
    const wantsNone = B.answerFor({ ok: true, fires: true, gates: [], context: '' },
        { context: { enabled: false } });
    assert.ok(wantsNone.block.indexOf('switch the evidence attachment on') > 0);

    const noChannel = B.answerFor({ ok: true, fires: true, gates: [], context: '',
                                    context_gate: 'no-channel' },
        { context: { enabled: true, channels: ['ui'] } });
    assert.ok(noChannel.block.indexOf('none of this rule') > 0,
        'a block that would ride no channel says so, rather than blaming the snapshot');
    const masterOff = B.answerFor({ ok: true, fires: true, gates: [], context: '',
                                    context_gate: 'off' },
        { context: { enabled: true, channels: ['telegram'] } });
    assert.ok(masterOff.block.indexOf('master switch') > 0,
        'a rule that asked for a block while the master switch is off is told which one held it back');

    const rows = B.conditionRows({ conditions: [
        { kind: 'side', op: '==', value: 'sell', met: true, read: 'sell', label: 'Side' },
        { kind: 'delta', op: '<=', value: -300, met: false, read: 12, why: 'read but did not match', label: 'Cumulative delta' },
    ] });
    assert.strictEqual(rows.length, 2);
    assert.strictEqual(rows[0].met, true);
    assert.strictEqual(rows[1].met, false);
    assert.strictEqual(rows[1].read, '12');
    assert.ok(B.readingsHtml({ conditions: [] }) === '');
    assert.ok(B.readingsHtml({ conditions: [{ kind: 'side', op: '==', value: 'sell', met: false, read: 'buy', why: 'read but did not match' }] })
        .indexOf('not met') === 0);
});

check('the form renders the rule it was given, and escapes what it prints', () => {
    withCatalogue((surface) => {
        const draft = surface.draftFromRule({
            id: 'ab-9', name: '<script>alert(1)</script>', kind: 'sweep', params: { min_levels: 5 },
            conditions: [{ kind: 'delta', op: '<=', value: -300 }],
            channels: ['ui', 'telegram'],
            context: { format: 'text', channels: ['telegram'] },
        });
        const html = surface.formHtml(draft, { rules: [{ id: 'ab-9', name: 'Sweep', kind: 'sweep' }] });
        assert.strictEqual(html.indexOf('<script>'), -1, 'no raw markup reaches the DOM');
        assert.ok(html.indexOf('&lt;script&gt;') > 0);
        assert.ok(html.indexOf('id="alertBuilderKind"') > 0);
        assert.ok(html.indexOf('value="5"') > 0);
        assert.ok(html.indexOf('id="alertBuilderRow_0_value"') > 0);
        assert.ok(html.indexOf('selected') > 0, 'the loaded rule is the selected option');
        /* A rule whose context key is set arrives with the snapshot ticked, and the fields that only
           matter when it is on are live; a fresh draft has them disabled. */
        assert.strictEqual(/id="alertBuilderContextOn"[^>]* checked/.test(html), true);
        assert.strictEqual(/id="alertBuilderContextChars"[^>]* disabled/.test(html), false);
        const off = surface.formHtml(surface.newDraft('sweep'), {});
        assert.strictEqual(/id="alertBuilderContextOn"[^>]* checked/.test(off), false);
        assert.strictEqual(/id="alertBuilderContextChars"[^>]* disabled/.test(off), true);
        assert.ok(off.indexOf('id="alertBuilderConditions"') > 0);
        assert.ok(off.indexOf('data-ab-act="test"') > 0, 'the Test fire button is always there');
        assert.ok(off.indexOf('data-ab-act="save"') > 0);
        assert.ok(off.indexOf('data-ab-act="reset"') > 0);
        assert.ok(off.indexOf('data-ab-act="add"') > 0);
        assert.ok(off.indexOf('no conditions — the rule fires on its kind and thresholds alone') > 0);
        const row = surface.conditionRowHtml({ kind: 'field', op: '>', value: '2', field: 'multiple' }, 0);
        assert.ok(row.indexOf('id="alertBuilderRow_0_field"') > 0, 'a field-reading row asks for its field');
        assert.ok(surface.conditionRowHtml({ kind: 'delta', op: '<=', value: '1' }, 1)
            .indexOf('id="alertBuilderRow_1_field"') === -1, 'a named reading does not');
    });
    const noCatalogue = B.formHtml(B.newDraft('sweep'), {});
    assert.ok(noCatalogue.indexOf('the alert catalogue is not loaded in this page') > 0,
        'without OFAPALERTS the thresholds section refuses instead of inventing fields');
});

check('the pill counts what the server actually holds', () => {
    assert.strictEqual(B.pillText([]), '0 rules · 0 with conditions · 0 carrying a snapshot');
    assert.strictEqual(B.pillText([{ name: 'a' }]), '1 rule · 0 with conditions · 0 carrying a snapshot');
    assert.strictEqual(B.pillText([
        { name: 'a', conditions: [{ kind: 'delta' }], context: { format: 'text' } },
        { name: 'b', conditions: [] },
    ]), '2 rules · 1 with conditions · 1 carrying a snapshot');
});

check('the panel touches no DOM it was not handed, and keeps no timers', () => {
    assert.strictEqual(src.indexOf('setInterval'), -1, 'the card is read on demand only');
    assert.strictEqual(src.indexOf('setTimeout'), -1);
    assert.ok(src.indexOf("addEventListener('click'") > 0 && src.indexOf("addEventListener('change'") > 0);
    /* Every id this module renders or reads starts with the feature's own prefix, so no panel of the
       shell can collide with it; the two ids the parent writes are named in the header. */
    const ids = src.match(/id="[A-Za-z0-9_]+"/g) || [];
    assert.ok(ids.length > 0);
    ids.forEach((raw) => {
        const id = raw.slice(4, -1);
        assert.ok(id.indexOf('alertBuilder') === 0, 'unprefixed id in the markup: ' + id);
    });
    assert.ok(src.indexOf("el(HOST)") > 0, 'the parent supplies the card body');
    assert.ok(src.indexOf("'alertBuilderBody'") > 0);
    assert.ok(src.indexOf("'alertBuilderPill'") > 0);
    /* Every element id this module reads is either its own constant or built behind the prefix; the
       one exception is the shell's instrument box, which is read the way every other panel reads it
       and never written to. */
    const FOREIGN = ['symbolSelect'];
    const literals = (src.match(/el\('[^']*'/g) || []).map((raw) => raw.slice(4, -1));
    assert.ok(literals.length >= 5, 'the panel reads several fields by id');
    literals.forEach((id) => {
        assert.ok(id.indexOf('alertBuilder') === 0 || FOREIGN.indexOf(id) >= 0,
            'unprefixed element id read: ' + id);
    });
    FOREIGN.forEach((id) => {
        assert.ok(new RegExp("el\\('" + id + "'\\)").test(src), 'the foreign read changed: ' + id);
    });
    assert.ok((src.match(/el\(HOST\)/g) || []).length > 0, 'the container is reached through its name');
    /* It may not reach into another module's tree: the catalogue comes off OFAPALERTS if present. */
    assert.ok(src.indexOf('window.OFAPALERTS') > 0);
    /* Both routes are written where they are called, so the repo's audit can cross-check them. */
    assert.ok(src.indexOf("api('/api/atlas/alert-rules'") > 0);
    assert.ok(src.indexOf("api('/api/atlas/alert-rules/test'") > 0);
    /* Every state-changing call is a button or a select change — no form submits the page. */
    assert.strictEqual(src.indexOf('type="submit"'), -1);
});

check('the two requests carry the objects the routes read', () => {
    const rule = B.ruleFromDraft(B.newDraft('sweep'));
    const save = B.saveBody(rule);
    assert.strictEqual(save.method, 'POST');
    assert.strictEqual(save.body, rule,
        "the shell's api() stringifies body itself — a string here would be double-encoded");
    const test = B.testBody(rule, 'btcusdt');
    assert.strictEqual(test.method, 'POST');
    assert.deepStrictEqual(Object.keys(test.body).sort(), ['rule', 'symbol']);
    assert.strictEqual(test.body.rule, rule);
    assert.strictEqual(test.body.symbol, 'btcusdt');
    assert.strictEqual(B.testBody(rule, null).body.symbol, '');
});

check('a call with no DOM at all is a no-op, not a crash', () => {
    assert.doesNotThrow(() => B.paint());
    assert.doesNotThrow(() => B.watch());
    assert.doesNotThrow(() => B.readForm());
    assert.deepStrictEqual(B.rules(), []);
    assert.strictEqual(B.state().kind, 'sweep');
});

console.log('alert-builder selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
