/* orderflow.js — the footprint panel's settings drawer, and the marks that are read from it.
 *
 * WHERE THE DATA COMES FROM — nothing here is invented:
 *   GET  /api/atlas/footprint/config   the settings block, its defaults, and one CAPABILITY row
 *                                      per control (key, label, kind, bounds/choices, meaning,
 *                                      applies). The drawer is rendered from those rows, so the
 *                                      labels and the one-line explanations live in one place.
 *   GET  /api/control/config           the stored block (`atlas.footprint`), passed back to the
 *                                      route above for validation before anything is drawn.
 *   POST /api/atlas/footprint/config   validate + clamp a patch; the accepted block comes back.
 *   POST /api/control/config           persist the accepted block through the app's own settings
 *                                      route (the store is the only writer of the config).
 *   The marks themselves are computed from the bar payload the chart already holds
 *   (`FootprintChart#data` -> each bar's `levels`), never from a second fetch.
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - The pure half below is a line-for-line mirror of `atlas/footprint_config.py`, and
 *     `test_footprint_config.py` runs the two side by side on shared fixtures. A mark that
 *     disagreed with the printed "calc:" numbers would be a lie, so the disagreement fails the
 *     suite instead of reaching a trader's screen.
 *   - The drawer is a `<details>` element built at boot into the Order Flow panel (no shared markup
 *     to edit) and every control saves the moment it changes — a setting the user has to re-save
 *     each launch is a setting the app lost.
 *   - The marks ride on an overlay canvas inside the chart's own container, drawn after the chart's
 *     own render (the instance's `render` is wrapped, not the shared file). The geometry comes from
 *     the chart's own helpers (`_priceToY`, `_barIdxToX`, `_rowStep`, `options.barWidth`) so the
 *     outlines land on the cells it drew. Above one tick per row a mark is drawn over the row's
 *     price span, because that is the row the reading was made on.
 *   - Missing data refuses, it does not pretend: no bars, no rows, every row under the size filter
 *     or a bar the session filter excludes each produce the panel's plain refusal sentence in the
 *     drawer's status line, and no cell is drawn.
 *   - No timers and no listeners at all: the panel redraws when the chart redraws, the controls are
 *     wired with onchange/onclick handlers, and the drawer reads itself on boot. That keeps the
 *     timer and listener ledgers untouched.
 */
(function () {
    'use strict';

    /* ── the pure half — mirrors atlas/footprint_config.py ──────────────────────────────────── */

    var DEFAULTS = {
        cell_metric: 'bid_ask',
        color_by: 'sides',
        imbalance_mode: 'same_price',
        imbalance_threshold: 3.0,
        diagonal_ratio: 3.0,
        stack_min_levels: 3,
        diagonal_stack_min_levels: 3,
        min_print_size: 0.0,
        min_level_volume: 0.0,
        absorption_threshold: 2.0,
        absorption_max_body_pct: 0.3,
        poc_per_bar: true,
        value_area_per_bar: true,
        value_area_pct: 0.70,
        ticks_per_row: 1,
        session_filter: 'all',
        session_start_min: 810,
        session_end_min: 1200,
        equal_tolerance: 0.0,
        show_equal: true,
        show_extremes: true,
    };

    var BOUNDS = {
        imbalance_threshold: [1.0, 50.0, 0.5],
        diagonal_ratio: [1.0, 50.0, 0.5],
        stack_min_levels: [1.0, 20.0, 1.0],
        diagonal_stack_min_levels: [1.0, 20.0, 1.0],
        min_print_size: [0.0, 1000.0, 0.001],
        min_level_volume: [0.0, 1000.0, 0.001],
        absorption_threshold: [1.0, 20.0, 0.5],
        absorption_max_body_pct: [0.0, 1.0, 0.05],
        value_area_pct: [0.5, 0.95, 0.05],
        ticks_per_row: [1.0, 50.0, 1.0],
        session_start_min: [0.0, 1439.0, 5.0],
        session_end_min: [0.0, 1439.0, 5.0],
        equal_tolerance: [0.0, 1.0, 0.1],
    };

    var WHOLES = { stack_min_levels: 1, diagonal_stack_min_levels: 1, ticks_per_row: 1,
                   session_start_min: 1, session_end_min: 1 };

    var CHOICES = {
        cell_metric: ['bid_ask', 'bid', 'ask', 'delta', 'volume', 'count'],
        color_by: ['sides', 'metric', 'imbalance'],
        imbalance_mode: ['same_price', 'diagonal', 'both'],
        session_filter: ['all', 'rth', 'outside_rth'],
    };

    /* Hand-typed spellings the server also forgives, so both ends read "the conventional" alike. */
    var ALIASES = {
        'same price': 'same_price', sameprice: 'same_price', 'same-price': 'same_price',
        'outside': 'outside_rth', 'outside rth': 'outside_rth', extended: 'outside_rth',
        regular: 'rth', cash: 'rth', 'both sides': 'bid_ask', total: 'volume', prints: 'count',
    };

    /* The sentences the panel prints — the same words as the Python module's. */
    var REFUSALS = {
        noRows: 'no price rows to read — this bar has nothing traded in it yet.',
        allFiltered: 'every row is under the row-volume filter — lower it to read this bar.',
        session: 'this bar is not in the window the session filter keeps — every bar is marked '
            + 'when the filter is set to all.',
        count: 'these bars carry no print counts — the count metric has nothing to read until the '
            + 'feed supplies them.',
        noBars: 'no bars arrived to annotate — the panel\'s own banner says whether what is on '
            + 'screen is live or demo.',
    };

    function isObject(value) {
        return value !== null && typeof value === 'object' && !(value instanceof Array);
    }

    /* Only a number or a numeric string counts, exactly like the server's own coercion: Number([])
       is 0 and Number(true) is 1, and both would be a fabricated setting. */
    function number(value, fallback) {
        if (typeof value === 'number') return isFinite(value) ? value : fallback;
        if (typeof value === 'string') {
            var text = value.trim();
            if (!text) return fallback;
            var out = Number(text);
            return isFinite(out) ? out : fallback;
        }
        return fallback;
    }

    function boolValue(value, fallback) {
        if (typeof value === 'boolean') return value;
        if (typeof value === 'number') return isFinite(value) ? !!value : fallback;
        if (typeof value === 'string') {
            var text = value.trim().toLowerCase();
            if (text === 'true' || text === '1' || text === 'yes' || text === 'on') return true;
            if (text === 'false' || text === '0' || text === 'no' || text === 'off') return false;
        }
        return fallback;
    }

    function pick(key, value, fallback) {
        if (typeof value !== 'string') return fallback;
        var text = value.trim().toLowerCase();
        var allowed = CHOICES[key] || [];
        if (allowed.indexOf(text) >= 0) return text;
        text = ALIASES[text] || text.replace(/-/g, '_').replace(/ /g, '_');
        return allowed.indexOf(text) >= 0 ? text : fallback;
    }

    function clamp(key, value, fallback) {
        var bounds = BOUNDS[key] || [0, 0, 1];
        var out = number(value, NaN);
        if (!isFinite(out)) return fallback;
        out = Math.min(bounds[1], Math.max(bounds[0], out));
        if (WHOLES[key]) return Math.round(out);
        return Math.round(out * 1e6) / 1e6;
    }

    /* The block the reading works on: every key present, unknown keys dropped, numbers clamped. */
    function clean(patch) {
        var out = {};
        var source = isObject(patch) ? patch : {};
        Object.keys(DEFAULTS).forEach(function (key) {
            var fallback = DEFAULTS[key];
            var value = source[key];
            if (typeof value === 'undefined' || value === null) { out[key] = fallback; return; }
            if (typeof fallback === 'boolean') out[key] = boolValue(value, fallback);
            else if (CHOICES[key]) out[key] = pick(key, value, fallback);
            else out[key] = clamp(key, value, fallback);
        });
        return out;
    }

    /* §148 T6-F7: `Date.parse` reads a zone-less stamp as LOCAL time while the Python half reads it
       as UTC — the same bar was marked by one side and refused by the other. A stamp with no zone
       now gets the `Z` both engines agree on, and the parser is pinned to the shape the Python
       half accepts (`T`, not the space separator; no basic `20260918`), so neither side filters on
       a clock the other cannot read. */
    function epochMs(when) {
        if (typeof when === 'string') {
            var text = when.trim();
            if (!text) return null;
            if (!/^\d{4}-\d{2}-\d{2}[Tt]/.test(text)) return null;
            if (!/(?:[Zz]|[+-]\d{2}:?\d{2})$/.test(text)) text += 'Z';
            var parsed = Date.parse(text);
            return isFinite(parsed) ? parsed : null;
        }
        var value = number(when, NaN);
        if (!isFinite(value)) return null;
        return Math.abs(value) < 1e11 ? value * 1000 : value;
    }

    function sessionVerdict(when, settings) {
        var cfg = clean(settings);
        if (cfg.session_filter === 'all') return 'all';
        var stamp = epochMs(when);
        if (stamp === null) return 'all';                 /* an unknown clock is not thrown away */
        var moment = new Date(stamp);
        var minute = moment.getUTCHours() * 60 + moment.getUTCMinutes();
        var start = cfg.session_start_min;
        var end = cfg.session_end_min;
        if (start === end) return cfg.session_filter === 'rth' ? 'in' : 'out';
        var inside = start < end ? (minute >= start && minute < end)
                                 : (minute >= start || minute < end);
        if (cfg.session_filter === 'rth') return inside ? 'in' : 'out';
        return inside ? 'out' : 'in';
    }

    function readRows(raw) {
        var items = raw;
        if (isObject(raw)) {
            items = [];
            Object.keys(raw).forEach(function (price) {
                var side = raw[price];
                if (side instanceof Array) items.push({ price: price, bid: side[0], ask: side[1] });
                else items.push({ price: price, bid: side, ask: 0 });
            });
        }
        if (!(items instanceof Array)) return [];
        var out = [];
        items.forEach(function (item) {
            if (!isObject(item)) return;
            var price = number(item.price, NaN);
            if (!isFinite(price)) return;
            var bid = Math.max(0, number(item.bid, 0));
            var ask = Math.max(0, number(item.ask, 0));
            var volume = number(item.volume, -1);
            var count = number(item.count, -1);
            out.push({
                price: price, bid: bid, ask: ask,
                volume: volume < 0 ? bid + ask : Math.max(0, volume),
                count: count >= 0 ? count : null,
                delta: number(item.delta, ask - bid),
            });
        });
        out.sort(function (a, b) { return a.price - b.price; });
        return out;
    }

    function rowStep(prices, tickSize, ticksPerRow) {
        var tick = Math.abs(number(tickSize, 0));
        if (!(tick > 0)) {
            var gaps = [];
            for (var i = 1; i < prices.length; i += 1) {
                var gap = prices[i] - prices[i - 1];
                if (gap > 1e-12) gaps.push(gap);
            }
            tick = gaps.length ? Math.min.apply(null, gaps) : 0;
        }
        if (!(tick > 0)) return 0;
        return tick * Math.max(1, Math.round(number(ticksPerRow, 1)));
    }

    function clustered(rows, cfg, tickSize) {
        var step = rowStep(rows.map(function (row) { return row.price; }), tickSize, cfg.ticks_per_row);
        if (cfg.ticks_per_row <= 1 || !(step > 0) || !rows.length) {
            return { rows: rows.map(function (row) {
                row.span = [row.price, row.price];
                row.levels = 1;
                return row;
            }), step: step };
        }
        var buckets = {};
        var order = [];
        rows.forEach(function (row) {
            /* Floor, not round: a tick on the cluster boundary opens the next row. */
            var key = Math.floor(row.price / step + 1e-9);
            if (!buckets[key]) { buckets[key] = []; order.push(key); }
            buckets[key].push(row);
        });
        order.sort(function (a, b) { return a - b; });
        var out = order.map(function (key) {
            var group = buckets[key].sort(function (a, b) { return a.price - b.price; });
            var counted = group.every(function (row) { return row.count !== null; });
            return {
                price: group[0].price,
                span: [group[0].price, group[group.length - 1].price],
                levels: group.length,
                bid: group.reduce(function (sum, row) { return sum + row.bid; }, 0),
                ask: group.reduce(function (sum, row) { return sum + row.ask; }, 0),
                volume: group.reduce(function (sum, row) { return sum + row.volume; }, 0),
                delta: group.reduce(function (sum, row) { return sum + row.delta; }, 0),
                count: counted ? group.reduce(function (sum, row) { return sum + row.count; }, 0) : null,
            };
        });
        return { rows: out, step: step };
    }

    function metricValue(row, metric) {
        if (metric === 'bid') return number(row.bid, 0);
        if (metric === 'ask') return number(row.ask, 0);
        if (metric === 'delta') return number(row.ask, 0) - number(row.bid, 0);
        if (metric === 'count') return row.count === null || typeof row.count === 'undefined'
            ? null : number(row.count, 0);
        return number(row.bid, 0) + number(row.ask, 0);
    }

    function reading(bid, ask, bidCmp, askCmp, threshold) {
        if (ask > 0 && (bidCmp <= 0 || ask / Math.max(bidCmp, 1e-12) >= threshold)) {
            return { side: 'buy', ratio: bidCmp > 0 ? round4(ask / bidCmp) : null };
        }
        if (bid > 0 && (askCmp <= 0 || bid / Math.max(askCmp, 1e-12) >= threshold)) {
            return { side: 'sell', ratio: askCmp > 0 ? round4(bid / askCmp) : null };
        }
        return { side: null, ratio: null };
    }

    function round4(value) { return Math.round(value * 1e4) / 1e4; }
    function round6(value) { return Math.round(value * 1e6) / 1e6; }
    function round10(value) { return Math.round(value * 1e10) / 1e10; }

    function readingsFor(rows, step, cfg) {
        var ladder = {};
        if (step > 0) rows.forEach(function (row) { ladder[Math.round(row.price / step)] = row; });
        return rows.map(function (row) {
            var same = reading(row.bid, row.ask, row.bid, row.ask, cfg.imbalance_threshold);
            var bidCmp = row.bid;
            var askCmp = row.ask;
            if (step > 0) {
                var key = Math.round(row.price / step);
                var below = ladder[key - 1];
                var above = ladder[key + 1];
                bidCmp = below ? below.bid : row.bid;
                askCmp = above ? above.ask : row.ask;
            }
            var diagonal = reading(row.bid, row.ask, bidCmp, askCmp, cfg.diagonal_ratio);
            return {
                same_price: { side: same.side, ratio: same.ratio, mode: 'same_price' },
                diagonal: { side: diagonal.side, ratio: diagonal.ratio, mode: 'diagonal' },
            };
        });
    }

    function primaryOf(pair, mode) {
        if (mode === 'diagonal') return pair.diagonal;
        if (mode === 'both') return pair.same_price.side ? pair.same_price : pair.diagonal;
        return pair.same_price;
    }

    function runsOf(rows, sides, modes, step, minLevels) {
        var runs = [];
        var current = [];
        var tolerance = Math.max(step * 1e-6, 1e-9);

        function flush() {
            if (current.length >= minLevels && sides[current[0]]) {
                var block = current.map(function (index) { return rows[index]; });
                var ratios = block.map(function (row) { return row._ratio; })
                    .filter(function (ratio) { return !!ratio; });
                var prices = block.map(function (row) { return row.price; });
                runs.push({
                    mode: modes[current[0]],
                    side: sides[current[0]],
                    from_price: Math.max.apply(null, prices),
                    to_price: Math.min.apply(null, prices),
                    levels: block.length,
                    volume: round6(block.reduce(function (sum, row) { return sum + row.volume; }, 0)),
                    max_ratio: ratios.length ? round4(Math.max.apply(null, ratios)) : null,
                });
            }
            current = [];
        }

        rows.forEach(function (row, index) {
            var side = sides[index];
            if (!side) { flush(); return; }
            if (current.length) {
                var previous = rows[current[current.length - 1]];
                var adjacent = step > 0 ? Math.abs((row.price - previous.price) - step) <= tolerance : false;
                if (sides[current[current.length - 1]] !== side || !adjacent) flush();
            }
            current.push(index);
        });
        flush();
        return runs;
    }

    /* One bar's marks. `bar` carries the OHLC (the absorption body clause) and the `time` (the
       session filter); both are optional — an absent one is treated as "not known", never guessed. */
    function annotateBar(levels, settings, bar, tickSize) {
        var cfg = clean(settings);
        var raw = readRows(levels);
        var grouped = clustered(raw, cfg, tickSize);
        var rows = grouped.rows;
        var step = grouped.step;

        var block = {
            ok: true, metric: cfg.cell_metric, color_by: cfg.color_by,
            rows: [], poc: null, value_area: null, stacks: [], absorption: [],
            extremes: { max_bid: null, max_ask: null },
            counts: { rows: 0, imbalance_buy: 0, imbalance_sell: 0, stacks: 0, diagonal: 0,
                      absorption: 0, equal: 0 },
            filtered: { levels: 0, volume: 0.0 },
            session: 'all', refusal: null, settings: cfg, body_known: false,
        };

        var verdict = sessionVerdict(isObject(bar) ? bar.time : null, cfg);
        block.session = verdict;
        if (verdict === 'out') {
            block.ok = false;
            block.refusal = REFUSALS.session;
            return block;
        }

        var keep = [];
        var dropped = [];
        rows.forEach(function (row) {
            if (row.volume >= cfg.min_level_volume) keep.push(row); else dropped.push(row);
        });
        block.filtered = {
            levels: dropped.length,
            volume: round6(dropped.reduce(function (sum, row) { return sum + row.volume; }, 0)),
        };
        if (!keep.length) {
            block.ok = false;
            block.refusal = rows.length ? REFUSALS.allFiltered : REFUSALS.noRows;
            return block;
        }

        var total = keep.reduce(function (sum, row) { return sum + row.volume; }, 0);
        var readings = readingsFor(keep, step, cfg);
        var mode = cfg.imbalance_mode;

        var primary = readings.map(function (pair) { return primaryOf(pair, mode); });
        var stacks = runsOf(
            keep.map(function (row, index) {
                var copy = {}; Object.keys(row).forEach(function (k) { copy[k] = row[k]; });
                copy._ratio = primary[index].ratio;
                return copy;
            }),
            primary.map(function (pair) { return pair.side; }),
            primary.map(function (pair) { return pair.mode; }),
            step, cfg.stack_min_levels);
        if (mode === 'both') {
            stacks = stacks.concat(runsOf(
                keep.map(function (row, index) {
                    var copy = {}; Object.keys(row).forEach(function (k) { copy[k] = row[k]; });
                    copy._ratio = readings[index].diagonal.ratio;
                    return copy;
                }),
                readings.map(function (pair) { return pair.diagonal.side; }),
                readings.map(function () { return 'diagonal'; }),
                step, cfg.diagonal_stack_min_levels));
        }
        var stacked = {};
        stacks.forEach(function (run) {
            keep.forEach(function (row, index) {
                if (row.price >= run.to_price && row.price <= run.from_price) {
                    stacked[index] = { mode: run.mode, side: run.side, levels: run.levels,
                                       max_ratio: run.max_ratio };
                }
            });
        });

        var average = total / keep.length;
        var bodyKnown = false;
        var bodyOk = true;
        if (isObject(bar)) {
            var numbers = ['open', 'high', 'low', 'close'].map(function (field) {
                return number(bar[field], NaN);
            });
            if (numbers.every(function (value) { return isFinite(value); })) {
                bodyKnown = true;
                bodyOk = Math.abs(numbers[3] - numbers[0]) < (numbers[1] - numbers[2]) * cfg.absorption_max_body_pct;
            }
        }
        var absorbed = {};
        keep.forEach(function (row, index) {
            var ratio = average > 0 ? row.volume / average : 0;
            if (bodyOk && ratio >= cfg.absorption_threshold) {
                absorbed[index] = { price: row.price, volume: round6(row.volume), ratio: round4(ratio) };
            }
        });

        var order = keep.map(function (row, index) { return index; }).sort(function (a, b) {
            return (keep[a].volume - keep[b].volume) || (keep[b].price - keep[a].price);
        });
        var pocIndex = order[order.length - 1];
        var pocRow = keep[pocIndex];
        var poc = cfg.poc_per_bar ? {
            price: round10(pocRow.price),
            volume: round6(pocRow.volume),
            share_pct: total ? round4((pocRow.volume / total) * 100) : 0,
            metric: metricValue(pocRow, cfg.cell_metric),
            row: pocIndex,
        } : null;

        var area = null;
        var areaRange = [pocIndex, pocIndex];
        if (cfg.value_area_per_bar) {
            var target = total * cfg.value_area_pct;
            var accumulated = pocRow.volume;
            var low = pocIndex;
            var high = pocIndex;
            while (accumulated < target && (low > 0 || high < keep.length - 1)) {
                var up = high + 1 < keep.length ? keep[high + 1].volume : -1;
                var down = low - 1 >= 0 ? keep[low - 1].volume : -1;
                if (up >= down) { high += 1; accumulated += up; } else { low -= 1; accumulated += down; }
            }
            areaRange = [low, high];
            area = {
                val: round10(keep[low].price),
                vah: round10(keep[high].price),
                pct: cfg.value_area_pct,
                rows: high - low + 1,
                share_pct: total ? round4((accumulated / total) * 100) : 0,
            };
        }

        var tolerance = cfg.equal_tolerance;
        var annotated = keep.map(function (row, index) {
            var pair = primary[index];
            var read = metricValue(row, cfg.cell_metric);
            var equal = tolerance > 1e-9
                ? Math.abs(row.bid - row.ask) <= tolerance * (row.bid + row.ask)
                : (row.bid > 0 && row.bid === row.ask);
            return {
                price: round10(row.price),
                span: [round10(row.span[0]), round10(row.span[1])],
                levels: row.levels,
                bid: round6(row.bid), ask: round6(row.ask), volume: round6(row.volume),
                delta: round6(row.delta),
                count: row.count === null ? null : round6(row.count),
                metric: read === null ? null : round6(read),
                imbalance: pair.side,
                imbalance_mode: pair.side ? pair.mode : null,
                imbalance_ratio: pair.ratio,
                readings: { same_price: readings[index].same_price.side,
                            diagonal: readings[index].diagonal.side },
                ratios: { same_price: readings[index].same_price.ratio,
                          diagonal: readings[index].diagonal.ratio },
                stack: stacked[index] || null,
                absorption: !!absorbed[index],
                equal: !!(cfg.show_equal && equal),
                poc: !!(cfg.poc_per_bar && index === pocIndex),
                value_area: !!(cfg.value_area_per_bar && index >= areaRange[0] && index <= areaRange[1]),
            };
        });

        var extremes = { max_bid: null, max_ask: null };
        if (cfg.show_extremes && keep.length) {
            var heaviestBid = 0;
            var heaviestAsk = 0;
            keep.forEach(function (row, index) {
                if (row.bid > keep[heaviestBid].bid) heaviestBid = index;
                if (row.ask > keep[heaviestAsk].ask) heaviestAsk = index;
            });
            if (keep[heaviestBid].bid > 0) {
                extremes.max_bid = round10(keep[heaviestBid].price);
                annotated[heaviestBid].extreme = 'bid';
            }
            if (keep[heaviestAsk].ask > 0) {
                extremes.max_ask = round10(keep[heaviestAsk].price);
                annotated[heaviestAsk].extreme = 'ask';
            }
        }

        var refusal = null;
        if (cfg.cell_metric === 'count' && keep.some(function (row) { return row.count === null; })) {
            refusal = REFUSALS.count;
        }

        block.rows = annotated;
        block.poc = poc;
        block.value_area = area;
        block.stacks = stacks;
        block.absorption = Object.keys(absorbed).map(function (key) { return absorbed[key]; })
            .sort(function (a, b) { return b.volume - a.volume; });
        block.extremes = extremes;
        block.counts = {
            rows: annotated.length,
            imbalance_buy: primary.filter(function (pair) { return pair.side === 'buy'; }).length,
            imbalance_sell: primary.filter(function (pair) { return pair.side === 'sell'; }).length,
            stacks: stacks.length,
            diagonal: readings.filter(function (pair) { return !!pair.diagonal.side; }).length,
            absorption: Object.keys(absorbed).length,
            equal: annotated.filter(function (row) { return row.equal; }).length,
        };
        block.body_known = bodyKnown;
        block.refusal = refusal;
        if (refusal) {
            /* A bar whose cell metric cannot be read is not a bar to mark: it refuses as a whole,
               the way the session filter and the row filter refuse, so nothing is drawn from it. */
            block.ok = false;
        }
        return block;
    }

    function annotateBars(bars, settings, tickSize) {
        var cfg = clean(settings);
        var blocks = [];
        if (bars instanceof Array) {
            bars.forEach(function (bar) {
                if (!isObject(bar)) return;
                blocks.push(annotateBar(bar.levels, cfg, bar, tickSize));
            });
        }
        var kept = blocks.filter(function (block) { return block.ok; }).length;
        return {
            ok: !!blocks.length && kept > 0,
            bars: blocks,
            kept: kept,
            skipped: blocks.length - kept,
            metric: cfg.cell_metric,
            settings: cfg,
            refusal: blocks.length && kept ? null : REFUSALS.noBars,
        };
    }

    /* ── the DOM half ──────────────────────────────────────────────────────────────────────── */

    var DRAWER = 'ofpDrawer';
    var ROWS = 'ofpRows';
    var MSG = 'ofpMsg';
    var PILL = 'ofpPillText';
    var STATUS = 'ofpStatus';
    var LEGEND = 'ofpLegend';
    var RESET = 'ofpReset';

    var state = {
        block: null,            /* the accepted settings block */
        defaults: null,
        capabilities: [],
        status: 'reading the settings\u2026',
        revision: 0,            /* bumped whenever the block changes: the mark cache keys off it */
        busy: false,
        charts: [],
        built: '',              /* the capability keys the controls were built from */
    };

    function el(id) {
        if (typeof document === 'undefined' || !document || !document.getElementById) return null;
        return document.getElementById(id);
    }

    function escape(text) {
        return String(text === null || typeof text === 'undefined' ? '' : text)
            .replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
    }

    /* The shell's own fetch helper (`window.api` in ui.js) — it takes an OBJECT body and does the
       JSON itself, so a body handed to it stays an object; the fetch fallback stringifies. It is
       named `window.api` on purpose: a module-local api() guarded with the bare name would test
       itself and recurse. */
    function api(path, options) {
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path, options);
        var opts = options || {};
        var prepared = { method: opts.method || 'GET', headers: { 'Content-Type': 'application/json' } };
        if (opts.body !== undefined && opts.body !== null) {
            prepared.body = typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body);
        }
        return fetch(path, prepared).then(function (response) { return response.json(); });
    }

    function sentence(payload, fallback) {
        if (payload && typeof payload.detail === 'string' && payload.detail) return payload.detail;
        if (payload && typeof payload.error === 'string' && payload.error) return payload.error;
        return fallback || 'the server did not say why.';
    }

    var STYLE = ''
        + '.ofp-drawer { margin-top: 10px; border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; }\n'
        + '.ofp-drawer > summary { cursor: pointer; font-size: 12.5px; }\n'
        + '.ofp-drawer .ofp-note { margin: 6px 0 8px; font-size: 11.5px; opacity: .8; }\n'
        + '.ofp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px 16px; }\n'
        + '.ofp-field { display: flex; flex-direction: column; gap: 3px; }\n'
        + '.ofp-field > label { font-size: 11.5px; opacity: .85; }\n'
        + '.ofp-field .ofp-meaning { font-size: 11px; opacity: .6; }\n'
        + '.ofp-field input[type="number"] { width: 110px; }\n'
        + '.ofp-field .ofp-unit { font-size: 11px; opacity: .6; margin-left: 6px; }\n'
        + '.ofp-actions { display: flex; align-items: center; gap: 10px; margin-top: 10px; }\n'
        + '.ofp-msg { font-size: 11.5px; opacity: .85; }\n'
        + '.ofp-legend { margin-top: 8px; font-size: 11.5px; opacity: .8; }\n'
        + '.ofp-key { display: inline-block; margin-right: 10px; }\n'
        + '.ofp-swatch { display: inline-block; width: 9px; height: 9px; border: 1.5px solid var(--text-secondary); margin-right: 4px; vertical-align: middle; }\n'
        + '.ofp-swatch.is-imbalance { border-color: var(--warn, #d29922); }\n'
        + '.ofp-swatch.is-diagonal { border-color: var(--warn, #d29922); border-style: dashed; }\n'
        + '.ofp-swatch.is-absorption { border-color: var(--accent, #bc8cff); }\n'
        + '.ofp-swatch.is-poc { border-color: var(--accent, #58a6ff); background: currentColor; }\n'
        + '.ofp-swatch.is-value { border-style: dotted; }\n';

    function ensureStyles() {
        if (typeof document === 'undefined' || !document || !document.head) return;
        if (document.getElementById('ofpStyles')) return;
        var tag = document.createElement('style');
        tag.id = 'ofpStyles';
        tag.textContent = STYLE;
        document.head.appendChild(tag);
    }

    function fieldId(key) { return 'ofp_f_' + key; }

    function controlHtml(spec, value) {
        var id = fieldId(spec.key);
        /* The bounds come from the server's own capability row — the same numbers `clean()` clamps
           to — with the local table as the fallback for a row that arrived without them. */
        var local = BOUNDS[spec.key] || [0, 0, 1];
        var bounds = [number(spec.min, local[0]), number(spec.max, local[1]), number(spec.step, local[2])];
        if (spec.kind === 'bool') {
            return '<div class="ofp-field"><label class="switch" for="' + id + '">'
                + '<input type="checkbox" id="' + id + '"' + (value ? ' checked' : '') + '> '
                + escape(spec.label) + '</label>'
                + '<span class="ofp-meaning">' + escape(spec.meaning) + '</span></div>';
        }
        if (spec.kind === 'enum') {
            var choices = spec.choices || CHOICES[spec.key] || [];
            return '<div class="ofp-field"><label for="' + id + '">' + escape(spec.label) + '</label>'
                + '<select id="' + id + '" title="' + escape(spec.meaning) + '">'
                + choices.map(function (choice) {
                    return '<option value="' + escape(choice) + '"'
                        + (String(value) === choice ? ' selected' : '') + '>'
                        + escape(choice.replace(/_/g, ' ')) + '</option>';
                }).join('') + '</select>'
                + '<span class="ofp-meaning">' + escape(spec.meaning) + '</span></div>';
        }
        return '<div class="ofp-field"><label for="' + id + '">' + escape(spec.label) + '</label>'
            + '<div><input type="number" id="' + id + '" min="' + bounds[0] + '" max="' + bounds[1]
            + '" step="' + bounds[2] + '" value="' + escape(value) + '">'
            + '<span class="ofp-unit">' + escape(spec.unit || '') + '</span></div>'
            + '<span class="ofp-meaning">' + escape(spec.meaning) + '</span></div>';
    }

    function readControl(spec) {
        var node = el(fieldId(spec.key));
        if (!node) return null;
        if (spec.kind === 'bool') return !!node.checked;
        if (spec.kind === 'enum') return String(node.value);
        return node.value;
    }

    function setControl(spec, value) {
        var node = el(fieldId(spec.key));
        if (!node) return;
        if (spec.kind === 'bool') node.checked = !!value;
        else node.value = String(value);
    }

    function pillText(block, defaults) {
        var base = defaults || DEFAULTS;
        var blockNow = block || DEFAULTS;
        var changed = Object.keys(base).filter(function (key) { return String(blockNow[key]) !== String(base[key]); });
        if (!changed.length) return 'as shipped';
        return changed.length + ' of ' + Object.keys(base).length + ' changed';
    }

    function legendText(block) {
        if (!block) {
            return 'no bar to read yet — the panel\'s own banner says whether what is on screen is '
                + 'live or demo.';
        }
        if (!block.ok) return block.refusal || REFUSALS.noRows;
        var counts = block.counts;
        var parts = [];
        var marked = counts.imbalance_buy + counts.imbalance_sell;
        if (marked) {
            parts.push(counts.imbalance_buy + ' buy / ' + counts.imbalance_sell + ' sell imbalanced rows');
        }
        if (counts.stacks) parts.push(counts.stacks + (counts.stacks === 1 ? ' stack' : ' stacks'));
        if (counts.absorption) parts.push(counts.absorption + ' absorption');
        if (block.poc) parts.push('POC ' + block.poc.price);
        if (block.value_area) parts.push('VA ' + block.value_area.val + ' to ' + block.value_area.vah);
        if (block.filtered.levels) parts.push(block.filtered.levels + ' rows under the size filter');
        if (!parts.length) return 'last bar: nothing marked at these settings.';
        return 'last bar: ' + parts.join(' \u00b7 ');
    }

    /* How much of the accepted block the store actually kept — the drawer says the number rather
       than claiming a save that a partial registration would have dropped. */
    function keptCount(block, stored) {
        var total = 0;
        var kept = 0;
        Object.keys(DEFAULTS).forEach(function (key) {
            total += 1;
            if (isObject(stored) && String(stored[key]) !== String(undefined)
                && String(stored[key]) === String(block[key])) kept += 1;
        });
        return { kept: kept, total: total };
    }

    function legendHtml() {
        var swatch = '<span class="ofp-swatch ';
        return '<span class="ofp-key">' + swatch + 'is-imbalance"></span>imbalance'
            + '</span><span class="ofp-key">' + swatch + 'is-diagonal"></span>diagonal'
            + '</span><span class="ofp-key">' + swatch + 'is-absorption"></span>absorption'
            + '</span><span class="ofp-key">' + swatch + 'is-poc"></span>POC'
            + '</span><span class="ofp-key">' + swatch + 'is-value"></span>value area'
            + '</span><span class="dim">the cells\u2019 own tint is the chart\u2019s own reading at its '
            + 'default ratio; the outlines follow the settings above.</span>';
    }

    function drawerHtml() {
        return '<details id="' + DRAWER + '" class="ofp-drawer">'
            + '<summary>Footprint settings \u2014 <span id="' + PILL + '">as shipped</span></summary>'
            + '<div class="ofp-note" id="' + STATUS + '">reading the settings\u2026</div>'
            + '<div class="ofp-grid" id="' + ROWS + '"></div>'
            + '<div class="ofp-legend" id="' + LEGEND + '">' + legendHtml() + '</div>'
            + '<div class="ofp-actions">'
            + '<button type="button" class="btn small" id="' + RESET
            + '" title="Put every control back to the value this build ships.">Reset to shipped</button>'
            + '<span class="ofp-msg" id="' + MSG + '"></span></div>'
            + '</details>';
    }

    function mountPoint() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        var section = document.querySelector('.view[data-view="orderflow"]');
        if (!section) return null;
        var chart = document.getElementById('footprintChart');
        var card = chart && chart.closest ? chart.closest('.card') : null;
        return { section: section, card: card || section };
    }

    function mount() {
        var where = mountPoint();
        if (!where) return null;
        ensureStyles();
        var drawer = el(DRAWER);
        if (!drawer) {
            var host = document.createElement('div');
            host.innerHTML = drawerHtml();
            drawer = host.firstChild;
            if (where.card.parentNode) where.card.parentNode.insertBefore(drawer, where.card.nextSibling);
            else where.section.appendChild(drawer);
        }
        var reset = el(RESET);
        if (reset) reset.onclick = function () { void saveBlock(DEFAULTS, 'Reset to the shipped settings'); };
        /* Re-read on open: the block is shared with the panel header's own imbalance controls and
           with a second window, and a stale drawer is a control that lies about what is stored. */
        drawer.ontoggle = function () { if (drawer.open) void load(); };
        void load();
        return drawer;
    }

    function setMsg(text, kind) {
        var node = el(MSG);
        if (!node) return;
        node.textContent = text || '';
        node.style.color = kind === 'bad' ? 'var(--warn, #e0a33c)' : '';
    }

    /* One control's change as a patch — the shape `saveBlock` takes. Pure, so the selftest pins it:
       a bare scalar handed to saveBlock is not a patch, and a control that reads "saved" while its
       value never left the page is the exact failure this function exists to prevent. */
    function patchFor(key, value) {
        var patch = {};
        patch[key] = value;
        return patch;
    }

    function wireControls() {
        state.capabilities.forEach(function (spec) {
            var node = el(fieldId(spec.key));
            if (!node) return;
            node.onchange = function () {
                void saveBlock(patchFor(spec.key, readControl(spec)), spec.label);
            };
        });
    }

    function render() {
        var host = el(ROWS);
        var keys = state.capabilities.map(function (spec) { return spec.key; }).join(',');
        if (host && state.capabilities.length && state.built !== keys) {
            host.innerHTML = state.capabilities.map(function (spec) {
                return controlHtml(spec, (state.block || DEFAULTS)[spec.key]);
            }).join('');
            state.built = keys;
            wireControls();
        }
        state.capabilities.forEach(function (spec) {
            setControl(spec, (state.block || DEFAULTS)[spec.key]);
        });
        var pill = el(PILL);
        if (pill) pill.textContent = pillText(state.block, state.defaults);
        var status = el(STATUS);
        if (status) status.textContent = state.status || '';
        var legend = el(LEGEND);
        if (legend) {
            var chart = state.charts[0];
            var data = chart && chart.data ? chart.data : [];
            legend.innerHTML = legendHtml()
                + '<div id="ofpLast">' + escape(legendText(lastBlock(chart)))
                + '</div>';
        }
        return state.block;
    }

    function lastBlock(chart) {
        if (!chart || !chart.data || !chart.data.length) return null;
        var list = annotationsFor(chart);
        return list[list.length - 1] || null;
    }

    async function load() {
        var stored = null;
        var note = '';
        try {
            var config = await api('/api/control/config');
            stored = config && config.atlas ? config.atlas.footprint : null;
        } catch (error) {
            note = 'the stored settings could not be read: ' + message(error);
        }
        try {
            var query = stored ? '?settings=' + encodeURIComponent(JSON.stringify(stored)) : '';
            var answer = await api('/api/atlas/footprint/config' + query);
            if (answer && answer.ok) {
                state.block = answer.block;
                state.defaults = answer.defaults || null;
                state.capabilities = answer.capabilities || [];
                state.status = note || (answer.source === 'supplied'
                    ? 'read from the config store \u00b7 every name below is the server\'s own'
                    : 'no stored block found \u00b7 these are the values this build ships');
            } else {
                state.status = 'the settings could not be read: '
                    + sentence(answer, 'the route did not answer.');
            }
        } catch (error) {
            state.status = 'the settings could not be read: ' + message(error);
        }
        state.revision += 1;
        render();
        redraw();
    }

    /* A scalar alone is not a patch: saveBlock only reads objects, so a caller that hands it a value
       changes nothing at all. Pinned because the drawer's own controls go through here. */
    async function saveBlock(patch, what) {
        if (state.busy) return null;
        state.busy = true;
        setMsg('saving\u2026');
        var candidate = {};
        var block = state.block || DEFAULTS;
        Object.keys(DEFAULTS).forEach(function (key) { candidate[key] = block[key]; });
        if (isObject(patch)) Object.keys(patch).forEach(function (key) { candidate[key] = patch[key]; });
        else if (patch !== null && typeof patch !== 'undefined') {
            setMsg('the change could not be read \u2014 nothing was saved.', 'bad');
            state.busy = false;
            return null;
        }
        try {
            var answer = await api('/api/atlas/footprint/config', {
                method: 'POST',
                body: candidate,
            });
            if (!answer || !answer.ok) {
                setMsg(sentence(answer, 'the change was refused.'), 'bad');
                state.busy = false;
                render();
                return null;
            }
            state.block = answer.block;
            state.revision += 1;
            render();
            redraw();
            var stored = null;
            try {
                stored = await api('/api/control/config', {
                    method: 'POST',
                    body: { atlas: { footprint: answer.block } },
                });
            } catch (error) {
                stored = { ok: false, detail: message(error) };
            }
            if (!stored || stored.ok !== true) {
                setMsg('applied here; the config store refused the write \u2014 '
                    + sentence(stored, 'no reason came back.'), 'bad');
                state.busy = false;
                return answer.block;
            }
            /* Read the block back rather than trusting the write's own answer: what is stored is
               what the drawer must be able to claim, and the store is allowed to keep less. */
            var kept = null;
            try {
                var reread = await api('/api/control/config');
                kept = reread && reread.atlas ? reread.atlas.footprint : null;
            } catch (error) {
                kept = null;
            }
            var counted = keptCount(answer.block, kept);
            setMsg(counted.kept >= counted.total
                ? 'saved \u00b7 ' + counted.kept + ' settings stored (' + what + ')'
                : 'applied here \u00b7 ' + counted.kept + ' of ' + counted.total
                    + ' settings stored \u2014 the store kept the rest as they were (' + what + ')',
            counted.kept >= counted.total ? '' : 'bad');
        } catch (error) {
            setMsg('the save failed: ' + message(error), 'bad');
        }
        state.busy = false;
        return state.block;
    }

    function message(error) {
        return (error && error.message) ? error.message : String(error);
    }

    /* ── the marks ─────────────────────────────────────────────────────────────────────────── */

    function tickSizeFor(chart) {
        var stated = chart && chart.options ? number(chart.options.tickSize, 0) : 0;
        return stated > 0 ? stated : 0;
    }

    function annotationsFor(chart) {
        var data = (chart && chart.data) || [];
        var last = data.length ? data[data.length - 1] : null;
        var stamp = data.length + '|' + (last ? String(last.time) + ':' + String(last.close) : '');
        var memo = chart.__ofpMemo;
        if (memo && memo.rev === state.revision && memo.stamp === stamp) return memo.list;
        var settings = state.block || DEFAULTS;
        var list = data.map(function (bar) {
            return annotateBar(bar ? bar.levels : null, settings, bar || null, tickSizeFor(chart));
        });
        chart.__ofpMemo = { rev: state.revision, stamp: stamp, list: list };
        return list;
    }

    function attach(chart) {
        if (!chart || !chart.container || chart.__ofp) return chart;
        var canvas = document.createElement('canvas');
        canvas.className = 'ofp-overlay';
        canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none';
        chart.container.appendChild(canvas);
        chart.__ofp = { canvas: canvas };
        var draw = chart.render;
        chart.render = function () {
            var out = typeof draw === 'function' ? draw.apply(this, arguments) : undefined;
            try { drawMarks(this); } catch (error) { /* a mark must never take the chart down */ }
            return out;
        };
        if (state.charts.indexOf(chart) < 0) state.charts.push(chart);
        drawMarks(chart);
        return chart;
    }

    function redraw() {
        state.charts.forEach(function (chart) {
            try { drawMarks(chart); } catch (error) { /* the chart may be mid-teardown */ }
        });
    }

    function palette(chart) {
        var colors = (chart && chart.options && chart.options.colors) || {};
        return {
            imbalance: colors.imbalance || '#d29922',
            absorption: colors.absorption || '#bc8cff',
            poc: colors.pocMarker || '#58a6ff',
            muted: colors.priceLevel || '#8b949e',
        };
    }

    /* The cell widths are the chart's own arithmetic (a side's volume as a fraction of the heaviest
       side volume in the bar, inside the half-width it draws in), so an outline lands on the cell it
       describes. A clustered row is outlined at its heaviest member level on that side. */
    function spanCellWidth(bar, span, side, maxVol, halfW) {
        var levels = (bar && bar.levels) || [];
        var widest = 0;
        levels.forEach(function (level) {
            var price = number(level.price, NaN);
            if (!isFinite(price) || price < span[0] - 1e-9 || price > span[1] + 1e-9) return;
            var volume = number(level[side], 0);
            var width = maxVol > 0 ? (volume / maxVol) * (halfW - 4) : 0;
            if (width > widest) widest = width;
        });
        return widest;
    }

    function rowHeight(chart, price, step) {
        var top = chart._priceToY(price);
        var next = chart._priceToY(price + step);
        return Math.max(2, Math.abs(top - next));
    }

    function drawMarks(chart) {
        var layer = chart && chart.__ofp ? chart.__ofp.canvas : null;
        if (!layer || typeof layer.getContext !== 'function') return false;
        var host = chart.container;
        var rect = host && host.getBoundingClientRect ? host.getBoundingClientRect() : { width: 0, height: 0 };
        var dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
        var width = Math.max(0, Math.round(rect.width * dpr));
        var height = Math.max(0, Math.round(rect.height * dpr));
        if (layer.width !== width || layer.height !== height) {
            layer.width = width;
            layer.height = height;
            layer.style.width = rect.width + 'px';
            layer.style.height = rect.height + 'px';
        }
        var ctx = layer.getContext('2d');
        if (!ctx) return false;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, rect.width, rect.height);
        var data = chart.data || [];
        if (!data.length) return false;
        var list = annotationsFor(chart);
        var barW = (chart.options && chart.options.barWidth) || 90;
        var halfW = barW / 2;
        var step = chart._rowStep ? chart._rowStep() : 0;
        var left = chart._chartLeft;
        var right = chart._chartRight;
        var top = chart._chartTop;
        var bottom = chart._chartBottom;
        var colors = palette(chart);
        var first = Math.max(0, Math.floor(chart.offsetX / barW) - 1);
        var last = Math.min(data.length, Math.ceil((chart.offsetX + (right - left)) / barW) + 1);
        for (var index = first; index < last; index += 1) {
            var block = list[index];
            var bar = data[index];
            if (!block || !block.ok || !bar) continue;
            var x = chart._barIdxToX(index);
            if (x + barW < left || x > right) continue;
            drawBarMarks(ctx, chart, block, bar, x, barW, halfW, step, colors, top, bottom);
        }
        /* The legend follows the chart: a new payload (the panel's own poll) says what is marked on
           the newest bar without waiting for the next settings read. Written only when it changes,
           because this runs on every pan frame. */
        var legend = el('ofpLast');
        if (legend) {
            var text = legendText(list[list.length - 1] || null);
            if (legend.textContent !== text) legend.textContent = text;
        }
        return true;
    }

    function spanY(chart, span, step, top, bottom) {
        var high = chart._priceToY(span[1]);
        var low = chart._priceToY(span[0]);
        var pad = rowHeight(chart, span[0], step) / 2;
        return { top: Math.max(top, high - pad), bottom: Math.min(bottom, low + pad) };
    }

    function drawBarMarks(ctx, chart, block, bar, x, barW, halfW, step, colors, top, bottom) {
        var levels = bar.levels || [];
        var maxVol = 1;
        levels.forEach(function (level) {
            maxVol = Math.max(maxVol, number(level.bid, 0), number(level.ask, 0));
        });
        var margin = 2;
        var width = barW - margin * 2;

        /* Value area first: it sits behind everything else. */
        if (block.value_area) {
            var areaTop = chart._priceToY(block.value_area.vah) - (rowHeight(chart, block.value_area.vah, step) / 2);
            var areaBottom = chart._priceToY(block.value_area.val) + (rowHeight(chart, block.value_area.val, step) / 2);
            ctx.save();
            ctx.setLineDash([2, 3]);
            ctx.strokeStyle = colors.muted;
            ctx.lineWidth = 1;
            ctx.strokeRect(x + margin, Math.max(top, areaTop), width,
                Math.max(2, Math.min(bottom, areaBottom) - Math.max(top, areaTop)));
            ctx.restore();
        }

        block.rows.forEach(function (row) {
            var span = spanY(chart, row.span, step, top, bottom);
            if (span.bottom <= top || span.top >= bottom) return;
            var cellH = Math.max(2, span.bottom - span.top);

            if (row.imbalance) {
                var buy = row.imbalance === 'buy';
                var wide = spanCellWidth(bar, row.span, buy ? 'ask' : 'bid', maxVol, halfW);
                if (wide > 0) {
                    var left = buy ? x + halfW + 2 : x + halfW - 2 - wide;
                    ctx.save();
                    ctx.strokeStyle = colors.imbalance;
                    ctx.lineWidth = 2;
                    if (row.imbalance_mode === 'diagonal') ctx.setLineDash([3, 2]);
                    ctx.strokeRect(left, span.top, wide, cellH);
                    ctx.restore();
                }
            }
            if (row.absorption) {
                ctx.save();
                ctx.strokeStyle = colors.absorption;
                ctx.lineWidth = 2;
                ctx.strokeRect(x + margin, span.top, width, cellH);
                ctx.restore();
            }
            if (row.equal) {
                var mid = (span.top + span.bottom) / 2;
                ctx.save();
                ctx.strokeStyle = colors.muted;
                ctx.globalAlpha = 0.7;
                ctx.setLineDash([1, 2]);
                ctx.beginPath();
                ctx.moveTo(x + margin, mid);
                ctx.lineTo(x + margin + width, mid);
                ctx.stroke();
                ctx.restore();
            }
        });

        /* Stacks ride on the outer edge of the marked side: one bracket per run. */
        block.stacks.forEach(function (run) {
            var span = spanY(chart, [run.to_price, run.from_price], step, top, bottom);
            if (span.bottom <= top || span.top >= bottom) return;
            var buySide = run.side === 'buy';
            var wide = spanCellWidth(bar, [run.to_price, run.from_price],
                                     buySide ? 'ask' : 'bid', maxVol, halfW);
            if (wide <= 0) return;
            var left = buySide ? x + halfW + 2 + Math.max(0, wide - 3) : x + halfW - 2 - wide;
            ctx.fillStyle = colors.imbalance;
            ctx.fillRect(left, span.top, 3, Math.max(2, span.bottom - span.top));
        });

        if (block.poc) {
            var pocMid = chart._priceToY(block.poc.price);
            var pocPad = rowHeight(chart, block.poc.price, step) / 2;
            ctx.save();
            ctx.strokeStyle = colors.poc;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x + margin, pocMid);
            ctx.lineTo(x + margin + width, pocMid);
            ctx.stroke();
            ctx.fillStyle = colors.poc;
            ctx.beginPath();
            ctx.moveTo(x + margin, pocMid - pocPad);
            ctx.lineTo(x + margin + 6, pocMid);
            ctx.lineTo(x + margin, pocMid + pocPad);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        }
    }

    /* ── boot ─────────────────────────────────────────────────────────────────────────────── */

    /* The chart class is wrapped BEFORE any panel constructs one, so the overlay is installed with
       the chart itself (ui.js builds it lazily when the Order Flow view opens). */
    function wrapChart() {
        if (typeof window === 'undefined' || typeof window.FootprintChart !== 'function') return false;
        if (window.FootprintChart.__ofpWrapped) return true;
        var Base = window.FootprintChart;
        function Wrapped(containerId, options) {
            var chart = new Base(containerId, options);
            attach(chart);
            return chart;
        }
        Wrapped.__ofpWrapped = true;
        Wrapped.prototype = Base.prototype;
        window.FootprintChart = Wrapped;
        return true;
    }

    var surface = {
        DEFAULTS: DEFAULTS, BOUNDS: BOUNDS, CHOICES: CHOICES, REFUSALS: REFUSALS,
        clean: clean, number: number, boolValue: boolValue,
        epochMs: epochMs, sessionVerdict: sessionVerdict, readRows: readRows, rowStep: rowStep,
        clustered: clustered, metricValue: metricValue, reading: reading, readingsFor: readingsFor,
        primaryOf: primaryOf, runsOf: runsOf, annotateBar: annotateBar, annotateBars: annotateBars,
        pillText: pillText, legendText: legendText, keptCount: keptCount, fieldId: fieldId,
        escape: escape, controlHtml: controlHtml, patchFor: patchFor,
        mount: mount, load: load, saveBlock: saveBlock, render: render, redraw: redraw,
        attach: attach, drawMarks: drawMarks, annotationsFor: annotationsFor, wrapChart: wrapChart,
        state: function () { return state; },
    };
    if (typeof window !== 'undefined') window.OFAPFOOTPRINT = surface;

    if (typeof document !== 'undefined' && document) {
        wrapChart();
        mount();
    }
})();
