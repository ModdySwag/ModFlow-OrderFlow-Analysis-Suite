/* why.js — the metric-explanation registry (§147).
 *
 * Every read in the app that a trader might squint at can carry a "why": what it is, which
 * numbers it was computed from, the rule in plain words, and — the part this app cares about
 * most — whether the read is a native measurement or an inference from something else.
 *
 * The card itself is hint.js's (hover to show, right-click to pin); this module owns only the
 * registry and the decoration of elements that declare `data-why="<id>"`. Decoration happens
 * once at boot, after hint.js exists, and each element is attached with a fixed spec so the
 * card can never drift from the registry.
 *
 * The pure half is selftested under Node (`why.selftest.js`): every entry renders a card, the
 * kind label is always present, unknown ids degrade to a sentence instead of an empty card,
 * and every id used in index.html must exist here — a data-why that explains nothing is a
 * broken promise, so it fails the selftest instead of shipping.
 */
(function () {
    'use strict';

    var VERSION = '1.0.0';

    /* kind: how the number reached the screen.
       native   — measured directly from the feed (prints, sizes, timestamps)
       inferred — deduced from what the feed shows (heuristic, labelled as such in the UI)
       computed — arithmetic over native inputs (no heuristic of its own) */
    var KINDS = {
        native: 'measured directly from the feed',
        inferred: 'inferred from the feed — a heuristic, not a measurement',
        computed: 'computed from measured inputs',
    };

    /* id → { title, what, inputs, how, kind }
       Plain sentences only. If the rule number is configurable, name the setting, not the value. */
    var WHYS = {
        'heatmap.liquidity': {
            title: 'Resting liquidity',
            what: 'How much size is sitting on each price level right now.',
            inputs: 'the depth stream: every level the venue publishes, with its size',
            how: 'drawn cell by cell; brighter means more resting size at that price at that moment',
            kind: 'native',
        },
        'heatmap.pull': {
            title: 'Liquidity pulled',
            what: 'Size that vanished from a level without being traded.',
            inputs: 'consecutive depth snapshots at the same price, and the size traded there between them',
            how: 'the drop must exceed the pull threshold in Settings and be larger than the size traded at that price since the previous snapshot; the note reports the unexplained part',
            kind: 'inferred',
        },
        'heatmap.wall': {
            title: 'Wall',
            what: 'A level whose resting size sits in the top slice of the book.',
            inputs: 'every level the current depth snapshot publishes',
            how: 'the cut is the wall quantile in Settings — at 0.97 only the largest 3% of the book counts — and the mark appears when a level crosses that cut',
            kind: 'computed',
        },
        'tape.big_trade': {
            title: 'Big trade',
            what: 'A single print at or above your big-trade size.',
            inputs: 'the trade tape: price, size, aggressor side',
            how: 'no arithmetic — the print is compared with the big-trade quantile in Settings',
            kind: 'native',
        },
        'tape.sweep': {
            title: 'Sweep',
            what: 'One order taking several price levels in quick succession.',
            inputs: 'the trade tape with aggressor side and timestamps',
            how: 'consecutive same-side prints inside the sweep window that consume at least the configured number of levels',
            kind: 'inferred',
        },
        'tape.iceberg': {
            title: 'Iceberg (inferred)',
            what: 'Repeated refills at one price that look like hidden size.',
            inputs: 'the tape and the depth at that price',
            how: 'prints keep filling the same level and the level keeps restoring — this is an inference: the feed does not publish order ids, so the app cannot prove it',
            kind: 'inferred',
        },
        'tape.stop_run': {
            title: 'Stop run (inferred)',
            what: 'A fast move through a level where resting size then disappears.',
            inputs: 'the tape, the book, and the recent range',
            how: 'speed and depth consumption together suggest stops; without order-level data this stays an inference and is labelled as one',
            kind: 'inferred',
        },
        'cvd.value': {
            title: 'Cumulative volume delta',
            what: 'Net aggressive buying minus selling, accumulated over the session.',
            inputs: 'every print with its aggressor side',
            how: 'the running sum of buy size minus sell size from the session open',
            kind: 'computed',
        },
        'cvd.divergence': {
            title: 'Delta divergence',
            what: 'Price makes a new extreme while delta does not follow.',
            inputs: 'the CVD series and the price series',
            how: 'the swing comparison is configuration-dependent: the lookback and the minimum delta gap come from Settings',
            kind: 'inferred',
        },
        'profile.poc': {
            title: 'Point of control',
            what: 'The price the session visited most — its busiest level by time, not by size.',
            inputs: 'the TPO counts built from the session\'s brackets',
            how: 'the price touched by the most brackets; ties go to the price with the larger traded volume',
            kind: 'computed',
        },
        'profile.value_area': {
            title: 'Value area',
            what: 'The price band the session spent its configured share of time in.',
            inputs: 'the per-price bracket counts (TPOs)',
            how: 'grow outward from the point of control, always taking the larger side next, until the running TPO share reaches the value-area share the app is configured with (70% by default)',
            kind: 'computed',
        },
        'footprint.imbalance': {
            title: 'Imbalance',
            what: 'One side of a price row dominating the other.',
            inputs: 'the bid and ask volume inside the bar row',
            how: 'the comparison the mode control picks — the same price row, or diagonal against the side one tick below — read against the imbalance ratio on the footprint toolbar',
            kind: 'computed',
        },
        'footprint.stacked': {
            title: 'Stacked imbalance',
            what: 'Several consecutive rows imbalanced the same way.',
            inputs: 'the per-row imbalance marks',
            how: 'a run of imbalanced rows at least as long as the stack control on the order flow panel',
            kind: 'computed',
        },
        'footprint.absorption': {
            title: 'Absorption',
            what: 'Size hitting a level without price moving.',
            inputs: 'the tape against the book at that level',
            how: 'traded size at the level must exceed the absorption threshold while the price change stays inside the tolerance',
            kind: 'inferred',
        },
        'gex.gamma': {
            title: 'Dealer gamma exposure',
            what: 'Per-strike gamma the option chain implies for dealers.',
            inputs: 'the option chain: open interest, gamma, contract size, underlying price',
            how: 'chain gamma times open interest per strike, signed by the assumed dealer side, then summed; the assumption is why this read is model-based, not measured',
            kind: 'inferred',
        },
        'gex.zero_gamma': {
            title: 'Zero-gamma level',
            what: 'The price where total dealer gamma flips sign.',
            inputs: 'the per-strike gamma profile',
            how: 'the interpolated strike where the cumulative gamma curve crosses zero',
            kind: 'inferred',
        },
        'vol.skew': {
            title: '25-delta skew',
            what: 'How much more the downside wing pays than the upside wing.',
            inputs: 'the option chain: implied vols and deltas per expiry',
            how: 'the 25-delta put IV minus the 25-delta call IV for the chosen expiry; when the chain arrives without deltas the wings are picked by a moneyness proxy and the row says so',
            kind: 'computed',
        },
        'optflow.sweep': {
            title: 'Option sweep (inferred)',
            what: 'A burst of large option prints spread across several strikes at once.',
            inputs: 'the option trades with size, strike and timestamps',
            how: 'block-sized prints across at least the minimum number of strikes inside the sweep window — deduced from the tape, because the feed publishes no sweep flag',
            kind: 'inferred',
        },
        'marketread.regime': {
            title: 'Market read',
            what: 'The deterministic one-line read of the instrument.',
            inputs: 'the tape, the profile, the radar levels and the book',
            how: 'rule-based over those signals — no model, no fitting; the panels that fed it are all visible next to it',
            kind: 'computed',
        },
        'risk.daily_cap': {
            title: 'Daily loss cap',
            what: 'The loss level that stops new orders for the rest of the day.',
            inputs: 'the paper account ledger and the cap in the trading configuration',
            how: 'realised plus open loss compared with the cap (0 = no cap); once it is crossed the order path refuses with a sentence',
            kind: 'computed',
        },
        'atm.bracket': {
            title: 'Bracket',
            what: 'The stop and target the app attaches to an entry.',
            inputs: 'the order template and the entry fill',
            how: 'distances from the template are applied to the fill price, rounded to the tick size; one leg filling cancels the other',
            kind: 'computed',
        },
        'depth.history': {
            title: 'Depth history',
            what: 'Resting liquidity over time, not just now.',
            inputs: 'stored depth columns per symbol',
            how: 'each column is bucketed and summarised; pull and add marks come from comparing consecutive columns',
            kind: 'computed',
        },
        'derivatives.funding': {
            title: 'Funding rate',
            what: 'The rate a perpetual long and short pay each other at every settlement.',
            inputs: 'each venue own funding endpoint, read without a key',
            how: 'annualised through the interval the venue names — Bybit says 8 h, OKX names one or its own settlement times give it, Hyperliquid funds hourly; Binance publishes no interval, so its row assumes the 8 h default — a rate, not a yield',
            kind: 'native',
        },
        'derivatives.oi': {
            title: 'Open interest',
            what: 'The size of the open perpetual book per venue.',
            inputs: 'the venue open-interest endpoint',
            how: 'each venue reported in its own unit with a USD total; the change is measured against this program own samples and names the window it really watched',
            kind: 'native',
        },
        'derivatives.basis': {
            title: 'Basis',
            what: 'How far the perpetual trades from its index.',
            inputs: 'the venue mark price and index price',
            how: 'the difference in basis points, annualised only as a shorthand so venues can be compared',
            kind: 'computed',
        },
    };

    function str(value) { return String(value == null ? '' : value); }

    /* One compact paragraph — the card body is escaped text, so no markup, no newline tricks. */
    function bodyFor(entry) {
        if (!entry) return '';
        var kind = KINDS[entry.kind] || KINDS.computed;
        return str(entry.what) + ' Uses ' + str(entry.inputs) + '. ' + str(entry.how)
            + ' (' + str(entry.title ? entry.title.toLowerCase() : 'this read') + ': ' + kind + '.)';
    }

    /* A hint.js spec for an id. Unknown ids still answer — a card that explains the absence. */
    function specFor(id) {
        var entry = WHYS[str(id)];
        if (!entry) {
            return {
                title: 'No explanation registered',
                body: 'This read has no registry entry yet (' + str(id) + '). That is a gap in the app, '
                    + 'not in your data — the number on screen is still whatever its panel computed.',
            };
        }
        return { title: entry.title, body: bodyFor(entry) };
    }

    function ids() { return Object.keys(WHYS); }

    function kindOf(id) {
        var entry = WHYS[str(id)];
        return entry ? entry.kind : '';
    }

    /* ── the DOM half ─────────────────────────────────────────────────────────────── */

    function attachAll(root) {
        if (typeof document === 'undefined') return 0;
        var scope = root || (document.body || null);
        if (!scope || !scope.querySelectorAll) return 0;
        var nodes = scope.querySelectorAll('[data-why]');
        var attached = 0;
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            if (el.getAttribute('data-why-done') === '1') continue;
            var spec = specFor(el.getAttribute('data-why'));
            /* The attributes are the fallback (hint.js boot reads them); the direct call is the
               normal path so the card is live the moment the element exists. */
            el.setAttribute('data-hint-title', spec.title);
            el.setAttribute('data-hint-body', spec.body);
            el.setAttribute('data-why-done', '1');
            if (typeof window !== 'undefined' && window.OFAPHINT && window.OFAPHINT.attach) {
                window.OFAPHINT.attach(el, spec);
            }
            attached++;
        }
        return attached;
    }

    /* §148 / T7-F14: does a mutation batch carry anything this registry decorates? Panels repaint
       with plain text all day; a full-document walk every 250 ms for a table cell is pure heat, so
       the observer only walks when a batch added an untagged card target. */
    function worthWalking(records) {
        for (var i = 0; i < records.length; i++) {
            var added = records[i].addedNodes || [];
            for (var j = 0; j < added.length; j++) {
                var node = added[j];
                if (!node || node.nodeType !== 1) continue;
                if (node.getAttribute && node.getAttribute('data-why')
                    && node.getAttribute('data-why-done') !== '1') return true;
                if (node.querySelector && node.querySelector('[data-why]:not([data-why-done="1"])')) return true;
            }
        }
        return false;
    }

    function boot() {
        if (typeof document === 'undefined' || !document.body) return;
        attachAll(document.body);
        /* Panels are built and rebuilt as data arrives; a short observer keeps late elements
           covered without every module having to remember to call us. It walks only for batches
           that could carry a card (T7-F14), and it lets go of the document when the page goes
           away instead of observing it for the lifetime of the tab. */
        if (typeof MutationObserver === 'function') {
            var pending = null;
            var observer = new MutationObserver(function (records) {
                if (pending || !worthWalking(records)) return;
                pending = setTimeout(function () {
                    pending = null;
                    attachAll(document.body);
                }, 250);
            });
            observer.observe(document.body, { childList: true, subtree: true });
            if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
                window.addEventListener('pagehide', function () {
                    if (pending) { clearTimeout(pending); pending = null; }
                    observer.disconnect();
                });
            }
        }
    }

    var API = {
        version: VERSION, KINDS: KINDS, WHYS: WHYS,
        ids: ids, kindOf: kindOf, bodyFor: bodyFor, specFor: specFor,
        attachAll: attachAll, boot: boot, worthWalking: worthWalking,
        count: function () { return ids().length; },
    };

    if (typeof window !== 'undefined') {
        window.OFAPWHY = API;
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
        else boot();
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
