/* ══════════════════════════════════════════════════════════════════
   Palette operators (plan Phase 4, T36).

   Type `type:option underlying:AAPL strike:>200 exp:max sort:last` and the palette
   filters instead of guessing. The parser is deliberately forgiving: anything it
   does not understand stays free text, so a half-typed operator never makes the
   palette go blank.

   Self-test:  node orderflow_system/desktop/ui/search-ops.selftest.js
   (runs in Node, no browser, no build step)
   ══════════════════════════════════════════════════════════════════ */

const SEARCH_OPS = {
    //: operator → how its value is read
    KEYS: ['type', 'exchange', 'underlying', 'exp', 'strike', 'vol', 'sort'],
    TYPES: ['stock', 'stocks', 'etf', 'crypto', 'option', 'options'],
    SORTS: ['relevance', 'symbol', 'name', 'last', 'chg', 'volume', 'feed'],
    EXP_RE: /^\d{4}-\d{2}-\d{2}$/,
};

function soTrim(text) {
    return String(text == null ? '' : text).trim();
}

function soNumber(text) {
    // "1M" → 1000000, "250k" → 250000, "1.5" → 1.5
    const m = soTrim(text).match(/^(\d+(?:\.\d+)?)\s*([kKmMbB])?$/);
    if (!m) return null;
    const base = parseFloat(m[1]);
    const mult = { k: 1e3, m: 1e6, b: 1e9 }[String(m[2] || '').toLowerCase()] || 1;
    return base * mult;
}

/** ">1M" | "<250k" | "1M-5M" | "2M" → {min, max} using K/M/B suffixes. Null when unusable. */
function soSizeRange(text) {
    const raw = soTrim(text);
    if (!raw) return null;
    let m = raw.match(/^>=\s*(.+)$/) || raw.match(/^>\s*(.+)$/);
    if (m) {
        const v = soNumber(m[1]);
        return v === null ? null : { min: v, max: null, open: raw.startsWith('>=') };
    }
    m = raw.match(/^<=\s*(.+)$/) || raw.match(/^<\s*(.+)$/);
    if (m) {
        const v = soNumber(m[1]);
        return v === null ? null : { min: null, max: v, open: raw.startsWith('<=') };
    }
    m = raw.match(/^(\S+?)-(\S+)$/);            // "1M-5M"
    if (m) {
        const lo = soNumber(m[1]);
        const hi = soNumber(m[2]);
        if (lo === null || hi === null) return null;
        return { min: lo, max: hi };
    }
    const single = soNumber(raw);
    return single === null ? null : { min: single, max: single };
}

/** ">200" | "<150" | "190-210" | "200" → {min, max}. Null when unusable. */
function soRange(text) {
    const raw = soTrim(text);
    if (!raw) return null;
    let m = raw.match(/^>=\s*(\d+(?:\.\d+)?)$/) || raw.match(/^>\s*(\d+(?:\.\d+)?)$/);
    if (m) return { min: parseFloat(m[1]), max: null, open: raw.startsWith('>=') };
    m = raw.match(/^<=\s*(\d+(?:\.\d+)?)$/) || raw.match(/^<\s*(\d+(?:\.\d+)?)$/);
    if (m) return { min: null, max: parseFloat(m[1]), open: raw.startsWith('<=') };
    m = raw.match(/^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$/);
    if (m) return { min: parseFloat(m[1]), max: parseFloat(m[2]) };
    m = raw.match(/^(\d+(?:\.\d+)?)$/);
    if (m) return { min: parseFloat(m[1]), max: parseFloat(m[1]) };
    return null;
}

/**
 * Parse palette input.
 *
 * Returns {
 *   text,        free text with the operators removed (what the symbol search gets)
 *   symbols,     comma-separated multi-symbol paste, upper-cased
 *   ops: {type, exchange, underlying, exp, strike: {min,max}, vol: {min,max}, sort, exp_any},
 *   errors,      human lines for the hint under the input
 *   active       true when at least one operator parsed
 * }
 */
function searchOpsParse(input) {
    const out = {
        text: '', symbols: [], ops: {}, errors: [], active: false,
        exp: { min: null, max: null, any: false },
    };
    const raw = soTrim(input);
    if (!raw) return out;

    const tokens = raw.split(/\s+/);
    const free = [];
    const known = new Set(SEARCH_OPS.KEYS);

    tokens.forEach((token) => {
        const ix = token.indexOf(':');
        if (ix <= 0) { free.push(token); return; }
        const key = token.slice(0, ix).toLowerCase();
        const value = token.slice(ix + 1);
        if (!known.has(key)) { free.push(token); return; }
        // A known operator with an unusable value is reported *and* kept as free
        // text: silently swallowing the token would leave the palette searching
        // for nothing, which looks like a bug rather than a typo.
        const keepAsText = () => free.push(token);
        out.active = true;
        switch (key) {
            case 'type': {
                const t = value.toLowerCase().replace(/s$/, '');
                if (SEARCH_OPS.TYPES.includes(t) || SEARCH_OPS.TYPES.includes(value.toLowerCase())) {
                    out.ops.type = t === 'option' ? 'option' : (t === 'crypto' ? 'crypto' : (t === 'etf' ? 'etf' : 'stock'));
                } else {
                    out.errors.push(`unknown type “${value}” — try type:stock, type:etf, type:crypto or type:option`);
                    keepAsText();
                }
                break;
            }
            case 'exchange': out.ops.exchange = value.toUpperCase(); break;
            case 'underlying': out.ops.underlying = value.toUpperCase(); break;
            case 'sort': {
                const s = value.toLowerCase();
                if (SEARCH_OPS.SORTS.includes(s)) out.ops.sort = s;
                else { out.errors.push(`unknown sort “${value}” — try ${SEARCH_OPS.SORTS.slice(0, 5).join(', ')}…`); keepAsText(); }
                break;
            }
            case 'exp': {
                const v = value.toLowerCase();
                if (v === 'min') { out.exp.any = true; out.exp.pick = 'min'; }
                else if (v === 'max') { out.exp.any = true; out.exp.pick = 'max'; }
                else if (SEARCH_OPS.EXP_RE.test(v)) { out.exp.min = v; out.exp.max = v; }
                else { out.errors.push(`exp: needs max, min or YYYY-MM-DD (got “${value}”)`); keepAsText(); }
                break;
            }
            case 'strike': {
                const r = soRange(value);
                if (r) out.ops.strike = r;
                else { out.errors.push(`strike: needs a number, N-M, >N or <N (got “${value}”)`); keepAsText(); }
                break;
            }
            case 'vol': {
                const r = soSizeRange(value);
                if (r) out.ops.vol = r;
                else { out.errors.push(`vol: needs a number with an optional K/M/B suffix (got “${value}”)`); keepAsText(); }
                break;
            }
            default: free.push(token);
        }
    });

    out.text = free.join(' ').trim();
    // comma-separated multi-symbol paste: "AAPL, MSFT, NVDA" (no operators, no spaces inside)
    if (!out.active) {
        const parts = raw.split(/[,\s]+/).filter(Boolean);
        const symbolish = parts.every((p) => /^[A-Za-z0-9./-]{1,12}$/.test(p));
        if (parts.length > 1 && symbolish) {
            out.symbols = parts.map((p) => p.toUpperCase());
            out.text = '';
        }
    }
    return out;
}

/** Apply client-side filters the server does not do (volume bounds). */
function searchOpsFilterRows(rows, ops) {
    let out = rows || [];
    if (ops && ops.vol) {
        out = out.filter((r) => {
            const raw = r.volume;
            // Unknown volume never satisfies a volume filter — "0" from an empty
            // field is not the same claim as "no data".
            const v = (raw === null || raw === undefined || raw === '') ? NaN : Number(raw);
            if (!isFinite(v)) return false;
            if (ops.vol.min !== null && ops.vol.min !== undefined && v < ops.vol.min) return false;
            if (ops.vol.max !== null && ops.vol.max !== undefined && v > ops.vol.max) return false;
            return true;
        });
    }
    if (ops && ops.exchange) {
        out = out.filter((r) => String(r.exchange || '').toUpperCase() === ops.exchange);
    }
    return out;
}

/** One line describing what the operators did — shown under the input. */
function searchOpsSummary(parsed) {
    const bits = [];
    if (!parsed || !parsed.active) return '';
    if (parsed.ops.type) bits.push(`type ${parsed.ops.type}`);
    if (parsed.ops.underlying) bits.push(`underlying ${parsed.ops.underlying}`);
    if (parsed.ops.exchange) bits.push(`exchange ${parsed.ops.exchange}`);
    if (parsed.ops.strike) bits.push(`strike ${parsed.ops.strike.min === parsed.ops.strike.max
        ? parsed.ops.strike.min
        : `${parsed.ops.strike.min !== null ? '≥' + parsed.ops.strike.min : ''}${parsed.ops.strike.max !== null ? '≤' + parsed.ops.strike.max : ''}`}`);
    if (parsed.exp && (parsed.exp.any || parsed.exp.min)) {
        bits.push(parsed.exp.any ? `exp ${parsed.exp.pick || 'any'}` : `exp ${parsed.exp.min}`);
    }
    if (parsed.ops.vol) bits.push(`vol ${parsed.ops.vol.min !== null ? '≥' + parsed.ops.vol.min : '≤' + parsed.ops.vol.max}`);
    if (parsed.ops.sort) bits.push(`sort ${parsed.ops.sort}`);
    return bits.join(' · ');
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { searchOpsParse, searchOpsFilterRows, searchOpsSummary, soRange, soSizeRange, soNumber, SEARCH_OPS };
}
