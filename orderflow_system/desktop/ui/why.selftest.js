/* why.selftest.js — the registry's own honesty checks, run under Node.
 *
 * What is pinned here: every registered read renders a card that names its kind (measured /
 * inferred / computed); every read the app calls an inference is labelled one; every card that
 * points at a setting points at one that exists; every data-why id placed in index.html exists in
 * the registry (html → registry); every registry entry is carried by an element in index.html
 * (registry → html, §148/T7-F6); and each audited card actually sits on the readout it explains
 * (§148/T7-F7). A "why" that explains nothing, or that nobody can reach, fails the build rather
 * than ships.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const API = require('./why.js');
const src = fs.readFileSync(path.join(__dirname, 'why.js'), 'utf8');

let ok = 0;
let failed = 0;

function check(name, fn) {
    try {
        const problem = fn();
        if (problem) { failed++; console.log('FAIL  ' + name + ' — ' + problem); }
        else { ok++; }
    } catch (err) {
        failed++;
        console.log('FAIL  ' + name + ' — threw: ' + (err && err.message));
    }
}

const ids = API.ids();

/* §148 / T7-F3: a card may only point at a control the app actually has. Each row below is a card
   whose sentence was audited against the app's own control surface (the Settings grid in atlas.js,
   the footprint toolbar and the order flow panel in index.html): the "names" phrase must appear in
   the body, and the "never" phrases — the wording this sweep removed — must not come back. */
const SETTINGS_CLAIMS = [
    ['heatmap.wall', 'wall quantile in Settings', ['wall multiple']],
    ['heatmap.pull', 'pull threshold in Settings', ['pull size in Settings']],
    ['tape.big_trade', 'big-trade quantile in Settings', ['size threshold in Settings']],
    ['footprint.imbalance', 'imbalance ratio on the footprint toolbar', ['imbalance ratio from Settings']],
    ['footprint.stacked', 'stack control on the order flow panel', ['stacked minimum in Settings']],
    ['profile.poc', 'touched by the most brackets', ['traded the most volume', 'nearest the session mid']],
    ['profile.value_area', 'TPO share', ['value-area percentage in Settings']],
    ['risk.daily_cap', 'trading configuration', ['cap in Settings']],
    ['vol.skew', 'moneyness proxy', []],
    ['derivatives.funding', 'Binance publishes no interval', ['8 h on Bybit and Binance']],
];

/* The reads that are inferences from the feed, not measurements. If one of these ever loses its
   label the app would be claiming to measure something it can only deduce. */
const MUST_BE_INFERRED = [
    'tape.iceberg', 'tape.stop_run', 'heatmap.pull', 'cvd.divergence',
    'footprint.absorption', 'gex.gamma', 'gex.zero_gamma',
    /* §148 / T7-F1: the option-sweep read was labelled native and claimed a venue sweep flag the
       feed never publishes (detect_sweeps in atlas/option_flow.py deduces it from the tape). The
       same claim the other inferences make must hold here: if this loses its label the app is
       again promising a measurement it does not have. */
    'optflow.sweep',
];

check('the registry has entries', () => (ids.length >= 20 ? null : 'only ' + ids.length + ' entries'));

check('every entry renders a titled card with a body', () => {
    for (const id of ids) {
        const spec = API.specFor(id);
        if (!spec.title) return id + ' has no title';
        if (!spec.body || spec.body.length < 40) return id + ' has no usable body';
    }
    return null;
});

check('every entry declares a known kind and the body names it', () => {
    for (const id of ids) {
        const kind = API.kindOf(id);
        if (!Object.prototype.hasOwnProperty.call(API.KINDS, kind)) return id + ' has kind "' + kind + '"';
        const body = API.specFor(id).body;
        if (body.indexOf(API.KINDS[kind]) < 0) return id + ' does not state its kind in the body';
    }
    return null;
});

check('inferred reads are labelled inferred', () => {
    for (const id of MUST_BE_INFERRED) {
        const kind = API.kindOf(id);
        if (kind !== 'inferred') return id + ' is labelled "' + kind + '"';
    }
    return null;
});

check('cards point at controls that exist', () => {
    for (const [id, names, never] of SETTINGS_CLAIMS) {
        const body = API.specFor(id).body.toLowerCase();
        if (body.indexOf(names.toLowerCase()) < 0) return id + ' no longer names "' + names + '"';
        for (const bad of never) {
            if (body.indexOf(bad.toLowerCase()) >= 0) return id + ' still says "' + bad + '"';
        }
    }
    return null;
});

check('cards stay readable (no body over 420 characters)', () => {
    for (const id of ids) {
        const body = API.specFor(id).body;
        if (body.length > 420) return id + ' body is ' + body.length + ' characters';
    }
    return null;
});

check('an unknown id answers with a sentence, not an empty card', () => {
    const spec = API.specFor('nothing.here');
    if (!spec.title || spec.body.indexOf('nothing.here') < 0) return 'the fallback does not name the id';
    return null;
});

check('the body never promises work that has not happened', () => {
    const banned = ['TODO', 'coming soon', 'Coming soon', 'will be added', 'not implemented yet'];
    for (const id of ids) {
        const body = API.specFor(id).body;
        for (const word of banned) if (body.indexOf(word) >= 0) return id + ' says "' + word + '"';
    }
    return null;
});

check('every data-why in index.html is registered, and the page uses the registry', () => {
    const file = path.join(__dirname, 'index.html');
    if (!fs.existsSync(file)) return 'index.html is missing';
    const html = fs.readFileSync(file, 'utf8');
    const used = [];
    const re = /data-why="([^"]+)"/g;
    let m;
    while ((m = re.exec(html)) !== null) used.push(m[1]);
    if (used.length < 10) return 'only ' + used.length + ' data-why attributes in the page — is the layer wired?';
    for (const id of used) {
        if (!API.WHYS[id]) return 'index.html explains "' + id + '" but the registry does not know it';
    }
    return null;
});

check('the observer walks only for batches that could carry a card (§148 / T7-F14)', () => {
    const card = (attrs) => ({ nodeType: 1, getAttribute: (k) => attrs[k] || null,
                               querySelector: () => (attrs.__hasCard ? { nodeType: 1 } : null) });
    const batch = (nodes) => [{ addedNodes: nodes }];
    const cases = [
        [batch([card({})]), false, 'a plain text repaint must not trigger a document walk'],
        [batch([{ nodeType: 3 }]), false, 'text nodes carry no cards'],
        [batch([card({ 'data-why': 'tape.sweep' })]), true, 'a fresh card target must trigger the walk'],
        [batch([card({ 'data-why': 'tape.sweep', 'data-why-done': '1' })]), false,
         'an already-decorated element must not'],
        [batch([card({ __hasCard: true })]), true, 'a container with an undecorated card inside must'],
        [[], false, 'an empty batch must not'],
    ];
    for (const [records, want, why] of cases) {
        const got = API.worthWalking(records);
        if (got !== want) return why + ' (walked=' + got + ')';
    }
    /* A filter nothing calls is decoration: the observer has to use it, and let the document go. */
    if (!/if \(pending \|\| !worthWalking\(records\)\) return;/.test(src)) {
        return 'the observer no longer filters by worthWalking';
    }
    if (!/observer\.disconnect\(\)/.test(src)) return 'the observer never disconnects (§148 / T7-F14)';
    return null;
});

check('the module never touches the DOM at require time', () => {
    /* §148 / T7-F15: the old second assertion here (`attachAll(null) !== 0`) could not fail under
       Node — attachAll returns 0 on its first line when there is no document, so the check was
       near-tautological. The property that matters is what the module does when it IS loaded with
       a document: register its boot, and walk nothing until that boot runs. */
    if (typeof API.attachAll !== 'function') return 'attachAll is missing';
    if (API.attachAll(null) !== 0) return 'attachAll without a document should attach nothing';
    const touched = [];
    const fakeDoc = {
        readyState: 'loading',
        addEventListener: (name) => touched.push('on:' + name),
        get body() { touched.push('body'); return null; },
    };
    new Function('window', 'document', 'MutationObserver', 'setTimeout', src)(
        {}, fakeDoc, undefined, () => 0);
    if (touched.length !== 1 || touched[0] !== 'on:DOMContentLoaded') {
        return 'the module walked the document at load: ' + JSON.stringify(touched);
    }
    return null;
});

/* The page as text, for the reachability and placement checks below. */
function pageHtml() {
    const file = path.join(__dirname, 'index.html');
    return fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
}

/* True when the element with this id carries this data-why on its own opening tag. */
function carries(html, elementId, whyId) {
    const at = html.indexOf('id="' + elementId + '"');
    if (at < 0) return false;
    const open = html.lastIndexOf('<', at);
    const close = html.indexOf('>', at);
    return html.slice(open, close).indexOf('data-why="' + whyId + '"') >= 0;
}

/* §148 / T7-F6: the gate above only ran html → registry. Nothing stopped a card being written that
   no readout can reach — the reader would never see it. Every entry must be carried by an element
   in index.html, or be listed below with the reason it cannot be yet. */
const UNREACHABLE_OK = {
    'footprint.absorption': 'the absorption marks exist only as chart marks — no readout on the page '
        + 'explains them, so carrying this card needs a UI element that does not exist yet',
};

/* §148 / T7-F7: the cards that were attached to the wrong element, and where each belongs. The
   third column (null when the card had no previous home) is the element it must no longer carry. */
const PLACEMENT = [
    ['heatmap.pull', 'hmPull', 'hmHeatHighlight'],
    ['heatmap.liquidity', 'mrLiquidity', 'hmHeatScheme'],
    ['profile.value_area', 'mpVa', 'mpReads'],
    ['depth.history', 'hmColNote', null],
    ['footprint.stacked', 'ofxStack', null],
    ['tape.big_trade', 'tkThreshold', null],
    ['tape.iceberg', 'tkIcebergs', null],
    ['tape.stop_run', 'tkStopTable', null],
    ['atm.bracket', 'ppExitsHint', null],
    ['risk.daily_cap', 'ppResult', null],
];

check('every card can be reached from the page', () => {
    const html = pageHtml();
    if (!html) return 'index.html is missing';
    for (const id of ids) {
        if (html.indexOf('data-why="' + id + '"') >= 0) continue;
        if (UNREACHABLE_OK[id]) continue;
        return id + ' has no element on the page — nobody can ever read this card';
    }
    return null;
});

check('cards sit on the element they explain', () => {
    const html = pageHtml();
    if (!html) return 'index.html is missing';
    for (const [id, on, off] of PLACEMENT) {
        if (!carries(html, on, id)) return id + ' is not carried by #' + on;
        if (off && carries(html, off, id)) return id + ' is still attached to #' + off;
    }
    return null;
});

console.log('why selftest: ' + ok + ' ok, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
