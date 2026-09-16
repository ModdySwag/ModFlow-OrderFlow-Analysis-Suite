/* ══════════════════════════════════════════════════════════════════
   help-search.js — the help system's search engine (pure).

   One engine behind both interfaces: the Advanced Help Centre and the Simple one search the SAME
   corpus with the SAME ranking, so "just as powerful" is a property of the code rather than a
   promise in the copy. What the Simple mode changes is which topics exist for it — the engine is
   told the mode and simply never sees the advanced ones.

   It is pure: entries in, ranked rows out. No DOM, no API, no storage — so `help-search.selftest.js`
   pins the behaviour under Node, and `orderflow_system/test_help.py` gates the corpus against the
   app (every view has a topic, every topic resolves).

   What it does, in order:
     1. tokenise   — case, punctuation and a light stem, so "settings" finds "setting" and
                     "sweeps" finds "sweep"; `ctrl+k`, `mt5`, `p99` survive as single tokens.
     2. index      — each field carries a weight (title 6 > tags 4 > summary 2.5 > heading 2 >
                     body 1), so a title hit beats a mention in prose.
     3. search     — every typed token must match somewhere (AND), scored by field weight,
                     boundary hits and how much of the query the title covers; a phrase match in
                     the title or summary earns a bonus.
     4. suggest    — type-ahead completions for the last (partial) token, from titles, tags and
                     aliases — plus any extra phrases the caller hands in (the app's own views and
                     menu commands), so the box autofills for the program as well as the help.
     5. correct    — one bounded edit-distance pass over the vocabulary for a token that matches
                     nothing, so a typo answers with "did you mean".

   Deliberately not here: fuzzy ranking of every token (the ranking must be explainable — `why`),
   and any notion of "recently used" (that is app state, and it lives in the config's help block).
   ══════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── words ─────────────────────────────────────────────────────────────────────────────── */

    /* Short, closed-class words that carry no signal in a help query. Kept tiny on purpose: in a
       corpus this size every extra stopword removes a real match ("how to set up" must still find
       the setup topics through "set" and "up" is dropped, not the other way round). */
    const STOP = ['a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'do', 'does', 'for',
                  'from', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'me', 'my', 'not',
                  'of', 'on', 'or', 'so', 'that', 'the', 'their', 'then', 'there', 'these', 'this',
                  'to', 'up', 'was', 'what', 'when', 'where', 'which', 'who', 'why', 'with', 'you',
                  'your'];

    /*: The whole query is dropped past this many characters — a paste into a search box must not
       turn into an index scan of the corpus. */
    const MAX_QUERY = 160;
    const DEFAULT_LIMIT = 40;

    function normalise(text) {
        return String(text == null ? '' : text)
            .toLowerCase()
            .replace(/[^a-z0-9+._-]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    /* A light stem, applied to BOTH sides, so the pairing stays symmetric. Deliberately not a
       real stemmer: only plural/gerund endings that appear in this corpus's own vocabulary. */
    function stem(word) {
        if (word.length > 4 && word.endsWith('ies')) return word.slice(0, -3) + 'y';
        if (word.length > 4 && word.endsWith('sses')) return word.slice(0, -2);
        /* Not 'ss' (class), 'us' (status), 'is' (analysis) or 'as' — those endings are the word. */
        if (word.length > 3 && word.endsWith('s')
            && ['ss', 'us', 'is', 'as', 'os'].indexOf(word.slice(-2)) < 0) {
            return word.slice(0, -1);
        }
        return word;
    }

    function tokenise(text, opts) {
        const keepStop = !!(opts && opts.keepStop);
        const out = [];
        String(text == null ? '' : text).slice(0, MAX_QUERY)
            .split(/[^A-Za-z0-9+._-]+/)
            /* camelCase and snake_case split into their words ("footprintChart" → footprint chart),
               because a corpus and a UI never agree on the spelling. */
            .forEach((part) => {
                part.split(/(?<=[a-z])(?=[A-Z])/).join(' ')
                    .split(/[.\-_\s]+/)
                    .forEach((bit) => {
                        const word = normalise(bit);
                        if (!word) return;
                        if (!keepStop && STOP.indexOf(word) >= 0) return;
                        const token = stem(word);
                        if (out.indexOf(token) < 0) out.push(token);
                    });
            });
        return out;
    }

    /* ── indexing ──────────────────────────────────────────────────────────────────────────── */

    const WEIGHTS = { title: 6, tag: 4, alias: 3.5, summary: 2.5, heading: 2, body: 1 };

    function words(text) {
        return tokenise(text, { keepStop: true });
    }

    function addTokens(bag, text, weight) {
        words(text).forEach((word) => {
            const prev = bag[word] || 0;
            if (weight > prev) bag[word] = weight;
        });
    }

    /* The searchable text of one entry. `blocks` is the corpus's body shape: [{h, p, list, table,
       steps, cmd, note}] — every string it carries is indexed, headings at heading weight. */
    function textOf(blocks) {
        const parts = [];
        (blocks || []).forEach((block) => {
            if (!block || typeof block !== 'object') {
                if (typeof block === 'string') parts.push(block);
                return;
            }
            if (block.h) parts.push(String(block.h));
            if (block.p) parts.push(String(block.p));
            if (block.note) parts.push(String(block.note));
            if (block.cmd) parts.push(String(block.cmd));
            if (Array.isArray(block.list)) parts.push(block.list.join(' '));
            if (Array.isArray(block.table)) {
                block.table.forEach((row) => parts.push((row || []).join(' ')));
            }
            if (Array.isArray(block.steps)) {
                block.steps.forEach((step) => parts.push([step && step.t, step && step.d,
                    ...((step && step.cmd) || [])].join(' ')));
            }
        });
        return parts.join(' ');
    }

    /*: Build the index for a corpus. `entries` are the help topics; anything with an `id`, `title`
       and `blocks` works — the engine never looks at the rest, so a caller can index extra rows
       (the app's own views and commands) with the same fields. */
    function buildIndex(entries) {
        const list = (entries || []).filter((e) => e && e.id && e.title);
        const index = list.map((entry) => {
            const bag = {};
            addTokens(bag, entry.title, WEIGHTS.title);
            (entry.tags || []).forEach((tag) => addTokens(bag, tag, WEIGHTS.tag));
            (entry.aliases || []).forEach((alias) => addTokens(bag, alias, WEIGHTS.alias));
            if (entry.summary) addTokens(bag, entry.summary, WEIGHTS.summary);
            if (entry.groupLabel) addTokens(bag, entry.groupLabel, 0.5);
            (entry.blocks || []).forEach((block) => {
                if (block && block.h) addTokens(bag, block.h, WEIGHTS.heading);
            });
            addTokens(bag, textOf(entry.blocks), WEIGHTS.body);
            if (entry.steps) addTokens(bag, textOf([{ steps: entry.steps }]), WEIGHTS.heading);
            return {
                entry: entry,
                bag: bag,
                title: normalise(entry.title),
                titleWords: words(entry.title),
                summary: normalise(entry.summary || ''),
                body: normalise(textOf(entry.blocks)),
            };
        });
        const vocab = Object.create(null);
        index.forEach((row) => Object.keys(row.bag).forEach((word) => { vocab[word] = true; }));
        return { index: index, vocab: Object.keys(vocab).sort() };
    }

    /* ── matching ──────────────────────────────────────────────────────────────────────────── */

    /* The best weight a token earns in one entry, and which field gave it. A token that equals a
       title word outranks one that merely starts one, which outranks a substring somewhere. */
    function weigh(row, token) {
        const base = row.bag[token];
        if (base) {
            if (row.titleWords.indexOf(token) >= 0) return { weight: base + 2, field: 'title' };
            if (row.title.indexOf(token) >= 0) return { weight: base + 1, field: 'title' };
            return { weight: base, field: fieldOf(row, token) };
        }
        /* Prefix: "heat" must find "heatmap" without the user typing the whole word. Cheaper and
           far more predictable than a fuzzy score. */
        let best = 0;
        let where = '';
        for (const word in row.bag) {
            if (word.length > token.length && word.indexOf(token) === 0) {
                if (row.bag[word] > best) { best = row.bag[word]; where = word; }
            }
        }
        if (!best) return null;
        return { weight: best * 0.75, field: fieldOf(row, where) };
    }

    function fieldOf(row, word) {
        if (row.titleWords.indexOf(word) >= 0 || row.title.indexOf(word) >= 0) return 'title';
        if ((row.entry.tags || []).some((t) => normalise(t).indexOf(word) >= 0)) return 'keywords';
        if (row.summary.indexOf(word) >= 0) return 'summary';
        return 'body';
    }

    function editDistance(a, b, cap) {
        if (Math.abs(a.length - b.length) > cap) return cap + 1;
        const prev = new Array(b.length + 1);
        const next = new Array(b.length + 1);
        for (let j = 0; j <= b.length; j += 1) prev[j] = j;
        for (let i = 1; i <= a.length; i += 1) {
            next[0] = i;
            let rowMin = next[0];
            for (let j = 1; j <= b.length; j += 1) {
                const cost = a[i - 1] === b[j - 1] ? 0 : 1;
                next[j] = Math.min(prev[j] + 1, next[j - 1] + 1, prev[j - 1] + cost);
                if (next[j] < rowMin) rowMin = next[j];
            }
            if (rowMin > cap) return cap + 1;
            for (let j = 0; j <= b.length; j += 1) prev[j] = next[j];
        }
        return prev[b.length];
    }

    /* One bounded "did you mean" pass: only for a token that matched nothing, only for words long
       enough for a typo to be plausible, and capped at two substitutions (a transposition — "heatmpa"
       for "heatmap" — costs two, and that is the typo people actually make). */
    function correctToken(token, vocab) {
        if (token.length < 5) return '';
        const cap = token.length >= 6 ? 2 : 1;
        let best = '';
        let bestScore = cap + 1;
        for (let i = 0; i < vocab.length; i += 1) {
            const word = vocab[i];
            if (Math.abs(word.length - token.length) > cap) continue;
            const d = editDistance(token, word, cap);
            if (d < bestScore) { bestScore = d; best = word; if (d === 1) break; }
        }
        return bestScore <= cap ? best : '';
    }

    /* A short excerpt around the first place the query lands — the summary first, then the body, so
       a hit in the prose is shown in context rather than falling back to the opening line. */
    function snippetFor(row, tokens, limit) {
        const max = limit || 190;
        const sources = [row.summary, row.body].filter(Boolean);
        for (let s = 0; s < sources.length; s += 1) {
            const source = sources[s];
            let at = -1;
            tokens.forEach((token) => {
                if (at >= 0) return;
                const hit = source.indexOf(token);
                if (hit >= 0) at = hit;
            });
            if (at < 0) continue;
            const start = Math.max(0, at - Math.floor(max / 3));
            const text = source.slice(start, start + max);
            return (start > 0 ? '…' : '') + text + (source.length > start + max ? '…' : '');
        }
        const head = sources[0] || '';
        return head.slice(0, max) + (head.length > max ? '…' : '');
    }

    /* ── the public half ───────────────────────────────────────────────────────────────────── */

    /*: Search one index. Returns `{query, terms, corrected, results, total}`; `corrected` is a
       rewritten query string when a token had to be repaired ("tape" for "tapw"), so the UI can
       say what it searched for instead of pretending. */
    function search(query, index, opts) {
        const options = opts || {};
        const limit = options.limit || DEFAULT_LIMIT;
        const terms = tokenise(query);
        if (!terms.length) return { query: String(query || ''), terms: [], corrected: '', results: [], total: 0 };
        const rows = (index && index.index) || [];
        const vocab = (index && index.vocab) || [];
        const phrase = normalise(query).replace(/[+._-]/g, ' ');

        /* Repair tokens that land nowhere before ranking, so one typo does not empty the list. */
        let repaired = false;
        const effective = terms.map((token) => {
            if (rows.some((row) => weigh(row, token))) return token;
            const fixed = correctToken(token, vocab);
            if (fixed) { repaired = true; return fixed; }
            return token;
        });

        const results = [];
        rows.forEach((row) => {
            let score = 0;
            let covered = 0;
            const hits = [];
            for (let i = 0; i < effective.length; i += 1) {
                const token = effective[i];
                const found = weigh(row, token);
                if (!found) continue;
                covered += 1;
                score += found.weight;
                if (hits.indexOf(found.field) < 0) hits.push(found.field);
                /* The first typed token drives the "starts with" bonus: someone typing "heat…"
                   means the heatmap, not a paragraph that happens to mention heat early. */
                if (i === 0 && row.titleWords.length && row.titleWords[0].indexOf(token) === 0) score += 1.5;
            }
            if (covered < effective.length) return;          // AND across the query
            /* The caller may rank whole classes of entry against each other: help content carries a
               small bonus so that when a topic and a program command match a query equally well, the
               explanation wins and the command is offered second (the user came to the help box). */
            score += Number(row.entry.kindRank || 0);
            if (row.title === phrase || row.title.indexOf(phrase) === 0) score += 4;
            else if (phrase.length > 3 && row.title.indexOf(phrase) >= 0) score += 3;
            if (row.summary.indexOf(phrase) >= 0 && phrase.length > 3) score += 1.5;
            if (effective.every((t) => row.titleWords.indexOf(t) >= 0)) score += 2;
            results.push({
                id: row.entry.id, title: row.entry.title, group: row.entry.group || '',
                mode: row.entry.mode || 'both', score: Math.round(score * 100) / 100,
                why: hits.join(' + ') || 'body', snippet: snippetFor(row, effective),
            });
        });
        results.sort((a, b) => (b.score - a.score) || a.title.localeCompare(b.title));
        return {
            query: String(query || ''),
            terms: terms,
            corrected: repaired ? effective.join(' ') : '',
            results: results.slice(0, limit),
            total: results.length,
        };
    }

    /* Type-ahead: completions for the last, still-being-typed word. `extra` lets the caller feed the
       app's own vocabulary (view names, menu commands) so the box autofills for the whole program;
       those phrases carry `kind` and `id`, and one that resolves to an action is what the UI runs.
       Ranking favours a title over a keyword (5 vs 3) and an exact word over a longer one, so typing
       "hea" offers the Heatmap topic before a tag that merely starts the same way. */
    function suggest(query, index, extra, limit) {
        const cap = limit || 8;
        const raw = String(query || '').trim();
        if (!raw) return [];
        const parts = raw.split(/\s+/);
        const last = normalise(parts[parts.length - 1]);
        const prefix = parts.slice(0, -1).join(' ').trim();
        if (!last) return [];
        const wanted = stem(last);
        const phrases = [];

        function consider(text, kind, id, weight) {
            const clean = String(text || '').trim();
            if (!clean) return;
            const words = String(clean).split(/\s+/);
            for (let i = 0; i < words.length; i += 1) {
                const word = stem(normalise(words[i]));
                if (!word || word.indexOf(wanted) !== 0) continue;
                const completion = words.slice(i).join(' ');
                phrases.push({
                    label: completion,
                    text: prefix ? prefix + ' ' + completion : completion,
                    kind: kind, id: id || '', match: words[i],
                    score: weight + (word === wanted ? 2 : 1) + (i === 0 ? 0.5 : 0),
                });
                break;
            }
        }

        ((index && index.index) || []).forEach((row) => {
            consider(row.entry.title, 'topic', row.entry.id, 5);
            (row.entry.tags || []).forEach((tag) => consider(tag, 'keyword', row.entry.id, 3));
            (row.entry.aliases || []).forEach((alias) => consider(alias, 'alias', row.entry.id, 2.5));
        });
        (extra || []).forEach((row) => consider(row.text, row.kind || 'command', row.id, row.weight || 4));

        const seen = Object.create(null);
        const out = [];
        phrases.sort((a, b) => (b.score - a.score) || a.label.localeCompare(b.label));
        phrases.forEach((row) => {
            const key = row.kind + ':' + row.label.toLowerCase();
            if (seen[key]) return;
            seen[key] = true;
            out.push(row);
        });
        return out.slice(0, cap);
    }

    /* Split text into [chunk, matched] pairs so a caller can highlight without re-deriving the
       tokens (and without a regex built from user input). */
    function segments(text, tokens) {
        const source = String(text == null ? '' : text);
        const terms = (tokens || []).filter(Boolean);
        if (!terms.length) return [[source, false]];
        const lower = source.toLowerCase();
        const spans = [];
        terms.forEach((token) => {
            let from = 0;
            while (from <= lower.length - token.length) {
                const at = lower.indexOf(token, from);
                if (at < 0) break;
                spans.push([at, at + token.length]);
                from = at + token.length;
            }
        });
        if (!spans.length) return [[source, false]];
        spans.sort((a, b) => a[0] - b[0]);
        const merged = [];
        spans.forEach((span) => {
            const last = merged[merged.length - 1];
            if (last && span[0] <= last[1]) last[1] = Math.max(last[1], span[1]);
            else merged.push([span[0], span[1]]);
        });
        const out = [];
        let at = 0;
        merged.forEach((span) => {
            if (span[0] > at) out.push([source.slice(at, span[0]), false]);
            out.push([source.slice(span[0], span[1]), true]);
            at = span[1];
        });
        if (at < source.length) out.push([source.slice(at), false]);
        return out;
    }

    const api = {
        normalise: normalise,
        tokenise: tokenise,
        stem: stem,
        buildIndex: buildIndex,
        textOf: textOf,
        search: search,
        suggest: suggest,
        segments: segments,
        correctToken: correctToken,
        editDistance: editDistance,
        STOP: STOP,
        WEIGHTS: WEIGHTS,
        MAX_QUERY: MAX_QUERY,
        DEFAULT_LIMIT: DEFAULT_LIMIT,
    };
    if (typeof window !== 'undefined') window.OFAPHELPSEARCH = api;
    else if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
