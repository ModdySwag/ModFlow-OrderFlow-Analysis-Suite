/* help-search.selftest.js — the help search engine, pinned without a browser.
 *
 * The module is pure (entries in, ranked rows out), so everything that decides what a user finds
 * is checkable here: what a query tokenises to, which field earns a hit, that every token must
 * match, that a typo answers with "did you mean", what the type-ahead completes, and that the
 * highlight segments cover the text exactly.
 *
 * orderflow_system/test_help.py runs this file under node and gates pytest on its verdict.
 */
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/help-search.js', 'utf8');

let ok = 0, failed = 0;
function check(name, fn) {
    try { fn(); ok += 1; } catch (e) { failed += 1; console.log('  FAIL ' + name + ': ' + e.message); }
}

/* Boot the IIFE with a window stub — the module writes its surface onto it. */
function boot() {
    const win = {};
    new Function('window', src)(win);
    return win.OFAPHELPSEARCH;
}

const H = boot();

/* A corpus shaped like the real one: the same fields, a title hit worth more than prose, and two
   entries that share a word ("depth") so ranking has something to order. */
function corpus() {
    return [
        { id: 'view.engine', group: 'panels', mode: 'both', title: 'The order-flow engine',
          tags: ['footprint', 'DOM', 'sweeps', 'heat'], summary: 'Split-candle footprint matrix with a depth heatmap behind it.',
          aliases: ['ofx', 'engine view'],
          blocks: [{ h: 'Reading the matrix', p: 'Each cell carries bid and ask volume for its price level; the HUD follows the crosshair.' }] },
        { id: 'view.heatmap', group: 'panels', mode: 'both', title: 'Market depth heatmap',
          tags: ['liquidity', 'walls', 'spoofing'],
          summary: 'Resting liquidity over time, with executed aggression as bubbles.',
          blocks: [{ h: 'Wall age', p: 'Levels held past the threshold are tinted; pulled size near price is a spoof candidate.' }] },
        { id: 'connect.mt5', group: 'connect', mode: 'advanced', title: 'MetaTrader 5 data source',
          tags: ['mt5', 'indices', 'gold', 'broker'],
          summary: 'Use a running MT5 terminal as a data source for instruments a crypto venue does not list.',
          blocks: [{ h: 'Map the symbols', p: 'The app knows an instrument by its own name; your broker calls the same market something else.' }] },
        { id: 'data.storage', group: 'data', mode: 'advanced', title: 'Storage, retention and pruning',
          tags: ['database', 'sqlite', 'prune'],
          summary: 'How many ticks are kept and when old rows are deleted.',
          blocks: [{ h: 'Retention', p: 'Rows older than the window are pruned every few hours while the engine runs.' }] },
    ];
}

const INDEX = H.buildIndex(corpus());

check('the module exposes its whole surface', () => {
    for (const fn of ['normalise', 'tokenise', 'stem', 'buildIndex', 'textOf', 'search', 'suggest',
                      'segments', 'correctToken', 'editDistance']) {
        assert.strictEqual(typeof H[fn], 'function', fn + ' is missing');
    }
    assert.ok(Array.isArray(H.STOP) && H.STOP.length, 'the stop list must be a non-empty array');
});

/* ── tokenising ────────────────────────────────────────────────────────────── */

check('a query tokenises through case, punctuation and stopwords', () => {
    assert.deepStrictEqual(H.tokenise('How do I read the Order Flow?'), ['read', 'order', 'flow']);
    assert.deepStrictEqual(H.tokenise('  '), []);
    assert.deepStrictEqual(H.tokenise(''), []);
});

check('symbols and chords survive as single tokens', () => {
    assert.deepStrictEqual(H.tokenise('mt5'), ['mt5']);
    assert.deepStrictEqual(H.tokenise('p99 frame time'), ['p99', 'frame', 'time']);
    assert.deepStrictEqual(H.tokenise('Ctrl+K'), ['ctrl+k']);
    assert.deepStrictEqual(H.tokenise('BOTH, and bybit.'), ['both', 'bybit']);
});

check('camelCase and snake_case split into their words', () => {
    assert.deepStrictEqual(H.tokenise('footprintChart'), ['footprint', 'chart']);
    assert.deepStrictEqual(H.tokenise('wall_age'), ['wall', 'age']);
    assert.deepStrictEqual(H.tokenise('data.storage'), ['data', 'storage']);
});

check('tokenising dedupes and stems symmetrically', () => {
    assert.deepStrictEqual(H.tokenise('settings setting settings'), ['setting']);
    assert.deepStrictEqual(H.tokenise('sweeps sweep'), ['sweep']);
    assert.strictEqual(H.stem('analysis'), 'analysis', 'a word ending in -is must not lose a letter');
    assert.deepStrictEqual(H.tokenise('The THE the'), []);
});

check('a pasted wall of text is bounded', () => {
    const long = 'heatmap '.repeat(100);
    assert.deepStrictEqual(H.tokenise(long), ['heatmap']);
    assert.strictEqual(H.MAX_QUERY, 160);
});

/* ── ranking ───────────────────────────────────────────────────────────────── */

check('buildIndex keeps the entries it was given and a sorted vocabulary', () => {
    const idx = H.buildIndex(corpus());
    assert.strictEqual(idx.index.length, 4);
    assert.deepStrictEqual(idx.vocab, [...idx.vocab].sort());
    assert.ok(idx.vocab.indexOf('heatmap') >= 0, 'a title word must reach the vocabulary');
    assert.strictEqual(H.buildIndex([null, {}, { id: 'x' }]).index.length, 0, 'junk rows are dropped');
});

check('every typed token must match (AND, not OR)', () => {
    const both = H.search('heatmap walls', INDEX);
    assert.strictEqual(both.results.length, 1);
    assert.strictEqual(both.results[0].id, 'view.heatmap');
    assert.strictEqual(H.search('heatmap hyperliquid', INDEX).results.length, 0,
        'a query with a term no entry carries matches nothing');
});

check('a title hit outranks the same word in prose', () => {
    const res = H.search('heatmap', INDEX).results;
    assert.strictEqual(res[0].id, 'view.heatmap');
    const behind = H.search('depth', INDEX).results;
    assert.ok(behind.length >= 2, 'two entries carry the word depth');
    assert.strictEqual(behind[0].id, 'view.heatmap', 'the title hit must come first');
    assert.ok(behind[0].score > behind[1].score, 'and must score higher');
});

check('a prefix finds the longer word', () => {
    assert.strictEqual(H.search('heat', INDEX).results[0].id, 'view.heatmap');
    assert.ok(H.search('rest', INDEX).results.some((r) => r.id === 'view.heatmap'),
        'prefix "rest" must reach "resting" in the summary');
});

check('a phrase in a title earns the top place', () => {
    const res = H.search('market depth heatmap', INDEX).results;
    assert.strictEqual(res[0].id, 'view.heatmap');
    assert.ok(res[0].score > 20, 'a full-title phrase must score well clear of a single-word hit');
});

check('an empty or unmatched query returns nothing rather than everything', () => {
    assert.deepStrictEqual(H.search('', INDEX).results, []);
    assert.deepStrictEqual(H.search('   ', INDEX).results, []);
    assert.strictEqual(H.search('zzzqqq', INDEX).results.length, 0);
});

check('results explain themselves and honour the limit', () => {
    const res = H.search('retention', INDEX);
    assert.strictEqual(res.results[0].id, 'data.storage');
    assert.ok(res.results[0].why.indexOf('title') >= 0, 'why must name the field that matched');
    assert.ok(H.search('depth', INDEX, { limit: 1 }).results.length === 1);
    assert.strictEqual(H.search('depth', INDEX).total, 2, 'the total counts before the cut');
});

check('searching twice gives the same answer, and never mutates the corpus', () => {
    const before = JSON.stringify(corpus());
    const a = H.search('wall age', INDEX).results;
    const b = H.search('wall age', INDEX).results;
    assert.deepStrictEqual(a, b);
    assert.strictEqual(JSON.stringify(corpus()), before, 'the engine must not write to its input');
});

check('help content outranks a command when the scores tie', () => {
    const rows = [
        { id: 'view.heatmap', group: 'panels', title: 'Market depth heatmap', tags: [], summary: 'Resting liquidity over time.', blocks: [], kindRank: 1.5 },
        { id: 'menu:data:Feed health', group: 'commands', title: 'Feed health', tags: [], summary: 'A menu command.', blocks: [], kindRank: 0.2 },
    ];
    const both = H.buildIndex(rows);
    const first = H.search('hea', both).results[0];
    assert.strictEqual(first.id, 'view.heatmap', 'the topic must come first: ' + JSON.stringify(H.search('hea', both).results));
    const reversed = H.buildIndex([rows[1], rows[0]]);
    assert.strictEqual(H.search('hea', reversed).results[0].id, 'view.heatmap',
        'the order the rows were indexed in must not decide it');
});

check('a snippet comes back with the hit inside it', () => {
    const row = H.search('spoof', INDEX).results[0];
    assert.ok(row.snippet.indexOf('spoof') >= 0, 'the excerpt must contain the matched word');
});

/* ── did you mean ──────────────────────────────────────────────────────────── */

check('a typo is repaired instead of returning nothing', () => {
    const res = H.search('heatmpa', INDEX);
    assert.strictEqual(res.corrected, 'heatmap', 'the repaired query must be reported');
    assert.strictEqual(res.results[0].id, 'view.heatmap');
    assert.strictEqual(H.search('heatmap', INDEX).corrected, '', 'a clean query repairs nothing');
    assert.strictEqual(H.search('mt5', INDEX).corrected, '', 'short tokens are never repaired');
});

check('edit distance is bounded and symmetric', () => {
    assert.strictEqual(H.editDistance('heatmap', 'heatmap', 2), 0);
    assert.strictEqual(H.editDistance('heatmap', 'heatmop', 2), 1);
    assert.ok(H.editDistance('heatmap', 'retention', 2) > 2, 'far apart words must exceed the cap');
});

/* ── type-ahead ────────────────────────────────────────────────────────────── */

check('suggest completes the word being typed', () => {
    const rows = H.suggest('hea', INDEX);
    assert.ok(rows.length >= 1);
    assert.ok(rows.some((r) => r.text === 'heatmap' || r.match === 'heatmap'), 'heat must complete the heatmap topic');
    assert.strictEqual(rows[0].kind, 'topic');
});

check('suggest keeps the words already typed in front of the completion', () => {
    const rows = H.suggest('market dep', INDEX);
    assert.ok(rows.length >= 1, 'the partial second word must complete');
    assert.ok(rows[0].text.indexOf('market dep') === 0, 'the box must not lose what was typed');
});

check('suggest offers the caller its own vocabulary', () => {
    const extra = [{ text: 'Open the Heatmap view', kind: 'command', id: 'heatmap', weight: 3 }];
    const rows = H.suggest('hea', INDEX, extra);
    assert.ok(rows.some((r) => r.kind === 'command' && r.id === 'heatmap'),
        'a command phrase must be suggested alongside topics');
});

check('suggest caps, dedupes and answers an empty box with nothing', () => {
    assert.deepStrictEqual(H.suggest('', INDEX), []);
    assert.deepStrictEqual(H.suggest('   ', INDEX), []);
    const many = H.suggest('d', INDEX, [{ text: 'Depth', kind: 'command', id: 'depth' },
                                        { text: 'Depth', kind: 'command', id: 'depth' }], 3);
    assert.ok(many.length <= 3, 'the cap must hold');
    const keys = many.map((r) => r.kind + ':' + r.match.toLowerCase());
    assert.strictEqual(keys.length, new Set(keys).size, 'no duplicate completions');
});

/* ── highlighting ──────────────────────────────────────────────────────────── */

check('segments cover the text exactly and mark the hits once', () => {
    const segs = H.segments('The heatmap shows a heat layer', ['heat']);
    assert.strictEqual(segs.map((s) => s[0]).join(''), 'The heatmap shows a heat layer');
    assert.deepStrictEqual(segs.filter((s) => s[1]).map((s) => s[0]), ['heat', 'heat']);
    assert.deepStrictEqual(H.segments('nothing here', ['zzz']), [['nothing here', false]]);
    assert.deepStrictEqual(H.segments('', ['a']), [['', false]]);
    assert.deepStrictEqual(H.segments('abc', []), [['abc', false]]);
});

check('overlapping matches merge instead of nesting', () => {
    const segs = H.segments('abcde', ['abc', 'bcd']);
    assert.deepStrictEqual(segs.filter((s) => s[1]).map((s) => s[0]), ['abcd']);
});

/* ── the mode gate ─────────────────────────────────────────────────────────── */

check('an advanced-only topic is invisible to a simple-mode index', () => {
    const simple = H.buildIndex(corpus().filter((t) => t.mode !== 'advanced'));
    assert.strictEqual(H.search('mt5', simple).results.length, 0, 'advanced topics stay out of the simple index');
    const full = H.search('mt5', INDEX);
    assert.strictEqual(full.results[0].id, 'connect.mt5', 'and are found in the advanced one');
});

check('body text is searchable, headings included', () => {
    assert.strictEqual(H.search('crosshair', INDEX).results[0].id, 'view.engine');
    assert.strictEqual(H.search('wall age', INDEX).results[0].id, 'view.heatmap');
});

console.log('help-search selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
