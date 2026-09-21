/* instrument.selftest.js — the Engine panel's instrument look-up, as behaviour rather than prose.
 *
 * The DOM half needs a browser; the half that decides what the chip says, which action is
 * emphasised and which suggestions are shown is pure, and it is the half that matters when a
 * user types NQ1! and must get a sentence instead of a blank stage.
 */
const assert = require('assert');
const I = require('./instrument.js');

let ok = 0, failed = 0;
function check(name, fn) { try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); } }

function payload(over) {
    return Object.assign({ query: 'NQ1!', symbol: 'NAS100USDT', state: 'live', reason: '',
        via: 'alias', actions: ['use'], suggestions: [], instrument: null }, over || {});
}

check('the module exposes the surface the view wires', () => {
    ['chip', 'title', 'actions', 'primary', 'rows', 'state', 'emptyNote', 'panelText', 'pickerRows',
     'ninjatraderNames'].forEach((name) => {
        assert.strictEqual(typeof I[name], 'function', name + ' is a function');
    });
    assert(I.ACTIONS.length === 6, 'the closed action set');
    assert(I.STATES.live && I.STATES.unknown, 'the state table');
});

check('the picker groups streaming → enabled → off, without duplicates', () => {
    const rows = I.pickerRows({
        streaming: ['TRXUSDT'],
        instruments: [
            { symbol: 'TRXUSDT', enabled: false, asset_class: 'Crypto' },
            { symbol: 'BNBUSDT', enabled: true, asset_class: 'Crypto' },
            { symbol: 'ADAUSDT', enabled: false, asset_class: 'Crypto' },
            { symbol: 'BNBUSDT', enabled: true, asset_class: 'Crypto' },
        ],
    });
    assert.deepStrictEqual(rows.map((r) => r.value), ['TRXUSDT', 'BNBUSDT', 'ADAUSDT']);
    assert.deepStrictEqual(rows.map((r) => r.state), ['streaming', 'enabled', 'off']);
    assert.strictEqual(rows[0].group, 'streaming now');
    assert(rows[2].label.indexOf('ADAUSDT') === 0 && rows[2].label.indexOf('Crypto') > 0,
        'the label carries the class: ' + rows[2].label);
    assert.deepStrictEqual(I.pickerRows({ instruments: [] }), [], 'empty config → no options');
});

check('the NinjaTrader probe names come from the config mapping, deduped and trimmed', () => {
    const names = I.ninjatraderNames([
        { symbol: 'NAS100USDT', ninjatrader_symbol: 'NQ' },
        { symbol: 'SP500', ninjatrader_symbol: 'ES' },
        { symbol: 'DJ30', ninjatrader_symbol: ' nq ' },
        { symbol: 'BTCUSDT', ninjatrader_symbol: '' },
        null,
    ]);
    assert.deepStrictEqual(names, ['NQ', 'ES'], 'names deduped case-insensitively, blanks dropped');
    assert.deepStrictEqual(I.ninjatraderNames([]), [], 'nothing mapped → no options, not an invention');
    assert.deepStrictEqual(I.ninjatraderNames(null), [], 'a junk payload is an empty list');
});

check('every action the server may send has a label and a place in the order', () => {
    I.ACTIONS.forEach((action) => {
        assert(typeof I.LABELS[action] === 'string' && I.LABELS[action].length, action + ' has a label');
        assert(I.ORDER.indexOf(action) >= 0, action + ' is ordered');
    });
});

check('a live alias says what it resolved to', () => {
    const c = I.chip(payload());
    assert.strictEqual(c.kind, 'ok');
    assert(c.text.indexOf('NAS100USDT') >= 0, 'the alias hop is visible: ' + c.text);
});

check('every declared state paints a chip with a kind', () => {
    Object.keys(I.STATES).forEach((state) => {
        const c = I.chip(payload({ state: state }));
        assert(['ok', 'dim', 'warn', 'bad'].indexOf(c.kind) >= 0, state + ' kind');
        assert(c.text.length > 1, state + ' text');
    });
});

check('an unknown state is not invented', () => {
    const c = I.chip(payload({ state: 'purple' }));
    assert.strictEqual(c.state, 'unknown');
    assert.strictEqual(c.kind, 'bad');
});

check('a junk payload is unknown, not a crash', () => {
    assert.strictEqual(I.state(null), 'unknown');
    assert.strictEqual(I.chip(undefined).state, 'unknown');
    assert.deepStrictEqual(I.actions(undefined), []);
    assert.deepStrictEqual(I.rows(null), []);
});

check('the title carries the alias hop and the reason, and nothing when there is none', () => {
    assert(I.title(payload({ reason: 'enable it and restart the engine' }))
        .indexOf('NQ1! → NAS100USDT') === 0, 'the hop leads');
    assert.strictEqual(I.title(payload({ query: 'BTCUSDT', symbol: 'BTCUSDT', via: 'exact', reason: '' })), '');
});

check('actions are filtered to the closed set and ordered', () => {
    const list = I.actions(payload({ actions: ['open_instruments', 'nonsense', 'enable'] }));
    assert.deepStrictEqual(list.map((a) => a.action), ['enable', 'open_instruments'],
        'known actions, preference order');
    assert.strictEqual(list[0].primary, true);
    assert.strictEqual(list[1].primary, false);
    assert.strictEqual(list[0].restarts, true, 'enable is a restart action');
    assert.strictEqual(list[1].restarts, false);
});

check('the emphasised action follows the preference order', () => {
    assert.strictEqual(I.primary(payload({ actions: ['open_instruments', 'use'] })), 'use');
    assert.strictEqual(I.primary(payload({ actions: ['open_instruments', 'add', 'enable'] })), 'enable');
    assert.strictEqual(I.primary({ state: 'unknown', actions: [] }), '');
    assert.strictEqual(I.primary({ state: 'unknown' }), '', 'no actions at all');
});

check('suggestion rows carry their class, note and stream state', () => {
    const rows = I.rows(payload({ suggestions: [
        { symbol: 'NAS100USDT', asset_class: 'Indices', enabled: true, streaming: true, note: 'alias for NQ' },
        { symbol: 'SP500', asset_class: 'Indices', enabled: false, streaming: false, note: 'Indices' },
    ] }));
    assert.strictEqual(rows.length, 2);
    assert.strictEqual(rows[0].action, 'use');
    assert(rows[0].meta.indexOf('Indices') >= 0 && rows[0].meta.indexOf('alias for NQ') >= 0,
        'class + note: ' + rows[0].meta);
    assert.strictEqual(rows[1].meta, 'Indices', 'a note equal to the class is not repeated');
    assert.strictEqual(rows[1].action, 'enable');
});

check('suggestion rows are capped and never blank', () => {
    const many = Array.from({ length: 12 }, (_, i) => ({ symbol: 'S' + i, asset_class: 'Crypto' }));
    assert.strictEqual(I.rows(payload({ suggestions: many })).length, 6);
    assert.strictEqual(I.rows(payload({ suggestions: many }), 3).length, 3);
    assert.deepStrictEqual(I.rows(payload({ suggestions: [{ asset_class: 'X' }] })), []);
});

check('the panel sentence carries the way out when the source refuses the symbol', () => {
    const out = I.panelText(payload({ state: 'unsupported', query: 'NQ1!', symbol: 'NAS100USDT',
        reason: 'Bybit perps list crypto only — switch to MT5 (Windows) for this instrument',
        hint: 'switch the data source to MetaTrader 5 (☰ ▸ sources) and map the broker symbol' }));
    assert(out.indexOf('crypto only') >= 0 && out.indexOf('MetaTrader 5') >= 0,
        'reason and hint both shown: ' + out);
});

check('the panel sentence is never empty for a healthy symbol', () => {
    assert(I.panelText(payload({ state: 'live', query: 'BTCUSDT', symbol: 'BTCUSDT', via: 'exact', reason: '' }))
        .indexOf('is streaming') >= 0, 'a live exact match still gets a sentence');
    assert(I.panelText(payload({ state: 'ready', query: 'SP500', symbol: 'SP500', via: 'exact',
        reason: 'SP500 is enabled — the engine is stopped; start it to stream' })).indexOf('stopped') >= 0);
    assert.strictEqual(I.panelText({ state: 'unknown' }), 'type an instrument name');
    assert.strictEqual(I.panelText(payload({ state: 'unknown', symbol: 'ZZZ', query: 'ZZZ', reason: 'nope' })), 'nope');
});

check('the empty-stage note is never wordless', () => {
    assert.strictEqual(I.emptyNote(payload({ reason: 'not streaming: switched off' })),
        'not streaming: switched off');
    assert.strictEqual(I.emptyNote(payload({ reason: '', symbol: 'NQZ25', query: 'NQZ25' })),
        'NQZ25 has no data for this source yet.');
    assert.strictEqual(I.emptyNote(payload({ reason: '', symbol: '', query: '' })), 'type an instrument name');
});

console.log('instrument selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
