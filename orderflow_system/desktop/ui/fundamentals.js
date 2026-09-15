/* fundamentals.js — the Fundamentals panel: filed numbers for the instrument the app is showing.
 *
 * WHERE THE DATA COMES FROM (orderflow_system/desktop/edgar.py :: GET /api/fundamentals/{symbol}):
 *   → { ok, symbol,
 *       source: 'edgar' | 'coingecko' | 'none',
 *       company?: { cik, ticker, name },
 *       rows: [ { concept, label, tag, value, unit, form, filed, period, start, fy, latest } ],
 *       crypto?: { id, name, ticker, rank, price, market_cap, volume_24h, circulating_supply,
 *                  total_supply, max_supply, change_24h, as_of },
 *       note?, error? }
 *
 *   The server does the heavy half: it fetches and reduces the filer's companyfacts document (Apple's
 *   is ~3.8 MB) and sends only the headline rows below — the browser never sees a companyfacts file.
 *   Those rows are annual-only by construction: a 10-Q's three-month figure is never shown next to a
 *   10-K's full year, a restated comparative replaces the earlier value for the same period, and
 *   every row names the XBRL tag it came from. The panel does not re-derive any of that; it shows
 *   what the server sent and says which source answered.
 *
 * WHY IT IS SHAPED THIS WAY:
 *   - The deciding half (sourceOf / rowsOf / reduceFacts / plan / rowHtml / tableHtml / cryptoHtml /
 *     esc / full / compact) is pure, so desktop/ui/fundamentals.selftest.js pins it in Node with no
 *     browser, and the same reduction exists on both sides of the wire — pinned to the same answer
 *     from the same captured companyfacts fixture by test_fundamentals.py.
 *   - Five different facts get five different sentences: "we cannot ask yet" (no instrument),
 *     "still loading", "the request failed" (the server's own words, printed as-is), "neither source
 *     covers this instrument" (indices, FX, metals — the mandatory state, spelled out with what each
 *     source does cover) and "the filer's facts carry none of these concepts". A blank panel would
 *     be a lie about the data.
 *   - Read-only by construction: one REST GET while this panel is the visible one, delivered by the
 *     suite's own bus when it is loaded and by this module's own timer when it is not (filings move
 *     slowly, so the cadence is minutes, not seconds). No engine call, no socket, nothing stored.
 */
(function () {
    'use strict';

    const VERSION = '0.1.0';
    const VIEW = '.view[data-view="fundamentals"]';
    /* The route, as a literal: the call site in refresh() spells the path out in a template no
       wider than the path itself, exactly as news.js does, so scripts/audit_ui_refs.py can resolve
       `GET /api/fundamentals/{symbol}` against the server's route table. */
    const URL_BASE = '/api/fundamentals/';
    const REFRESH_MS = 300000;                 /* filings move on a quarterly clock: 5 min is eager */
    const TICK_MS = 15000;                     /* the cheap "should we ask again" check */
    const DASH = '—';                          /* what an absent number renders as, never a 0 */

    /* One XBRL concept policy, mirroring orderflow_system/desktop/edgar.py: HEADLINES, ANNUAL_FORMS,
       the 330–400 day year test and MAX_PERIODS_PER_CONCEPT. The parity check in
       test_fundamentals.py reduces the same fixture with both implementations and fails on drift. */
    const ANNUAL_FORMS = ['10-K', '10-K/A', '10-KT', '10-KT/A', '20-F', '20-F/A', '40-F', '40-F/A'];
    const MIN_ANNUAL_DAYS = 330;
    const MAX_ANNUAL_DAYS = 400;
    const MAX_PERIODS_PER_CONCEPT = 4;
    const HEADLINES = [
        { key: 'revenue', label: 'Revenue', unit: 'USD', kind: 'flow',
          tags: ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'] },
        { key: 'net_income', label: 'Net income', unit: 'USD', kind: 'flow',
          tags: ['NetIncomeLoss', 'ProfitLoss'] },
        { key: 'eps_diluted', label: 'EPS (diluted)', unit: 'USD/shares', kind: 'flow',
          tags: ['EarningsPerShareDiluted'] },
        { key: 'gross_profit', label: 'Gross profit', unit: 'USD', kind: 'flow',
          tags: ['GrossProfit'] },
        { key: 'assets', label: 'Total assets', unit: 'USD', kind: 'instant', tags: ['Assets'] },
        { key: 'equity', label: "Stockholders' equity", unit: 'USD', kind: 'instant',
          tags: ['StockholdersEquity',
                 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'] },
    ];

    /* CoinGecko ids for the suite's crypto universe (config.settings.CRYPTO_MAJORS + BTCUSDT), each
       verified live. A symbol is not an identity on CoinGecko — `the-open-network` trades as "gram"
       and `matic-network` is a migrated husk with a null rank while POL is `polygon-ecosystem-token`
       — so the mapping is a table, not a guess. */
    const CRYPTO_IDS = {
        BTC: 'bitcoin', ETH: 'ethereum', SOL: 'solana', XRP: 'ripple', BNB: 'binancecoin',
        DOGE: 'dogecoin', ADA: 'cardano', AVAX: 'avalanche-2', LINK: 'chainlink', LTC: 'litecoin',
        DOT: 'polkadot', TRX: 'tron', SUI: 'sui', APT: 'aptos', NEAR: 'near', ARB: 'arbitrum',
        OP: 'optimism', POL: 'polygon-ecosystem-token', TON: 'the-open-network',
    };
    const CRYPTO_SUFFIXES = ['USDT', 'USDC', 'BUSD', 'FDUSD', 'USD'];

    /* The sentence for an instrument neither source covers — the same wording the server sends, so
       an index or an FX pair reads identically whether the server or the panel says it. */
    const NO_SOURCE = 'no fundamentals source for {symbol} — EDGAR covers US filings, '
        + 'CoinGecko covers crypto';

    const el = (id) => ((typeof document !== 'undefined' && document) ? document.getElementById(id) : null);
    function win() { return (typeof window !== 'undefined' && window) ? window : {}; }
    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }
    function errText(err) { return String(err && err.message ? err.message : err); }
    /* One place the panel reads from: the bus's coalesced one-shot when the delivery layer is
       loaded, the app's own api() when we are inside it, a plain fetch when probed bare. The call
       site below spells the path out as `api(`/api/fundamentals/${symbol}`)` so
       scripts/audit_ui_refs.py can resolve the route against the server's table (news.js does the
       same, and this is why the helper keeps the app's name). */
    function api(path, options) {
        const bus = win().OFAPBUS;
        if (bus && typeof bus.request === 'function' && !options) return bus.request(path);
        if (typeof window !== 'undefined' && typeof window.api === 'function') return window.api(path, options);
        return fetch(path, options).then((r) => r.json());
    }

    /* ── the symbol → source decision (pure) ─────────────────────────────────────────────────── */

    function normalize(symbol) {
        return String(symbol == null ? '' : symbol).trim().toUpperCase();
    }

    /* A venue symbol's CoinGecko id, or '' when it is not one of the mapped coins. NAS100USDT and
       XAUUSDT strip to bases nothing maps — an index and a metal must fall through to "no source"
       rather than to a wrong coin. */
    function cryptoAsset(symbol) {
        const text = normalize(symbol);
        if (!text) return '';
        if (Object.prototype.hasOwnProperty.call(CRYPTO_IDS, text)) return CRYPTO_IDS[text];
        const suffixes = CRYPTO_SUFFIXES.slice().sort((a, b) => b.length - a.length);
        for (let i = 0; i < suffixes.length; i++) {
            const suffix = suffixes[i];
            if (text.length > suffix.length && text.slice(-suffix.length) === suffix) {
                const base = text.slice(0, -suffix.length);
                if (Object.prototype.hasOwnProperty.call(CRYPTO_IDS, base)) return CRYPTO_IDS[base];
            }
        }
        return '';
    }

    /* 'coingecko' | 'edgar' | 'none'. The server's answer is always the authority for what is
       SHOWN; this mirror exists to word the waiting line and to refuse to pretend for symbols that
       cannot be a US ticker at all ('^GSPC', a pair like 'SPX/USD', an empty string). */
    function sourceOf(symbol) {
        const text = normalize(symbol);
        if (!text) return 'none';
        if (cryptoAsset(text)) return 'coingecko';
        if (/^[A-Z][A-Z0-9.\-]{0,9}$/.test(text)) return 'edgar';
        return 'none';
    }
    function sourceLabel(source) {
        if (source === 'edgar') return 'SEC EDGAR';
        if (source === 'coingecko') return 'CoinGecko';
        return 'no source';
    }
    function noSourceNote(symbol) { return NO_SOURCE.replace('{symbol}', normalize(symbol)); }

    /* ── the reduction (pure; mirrors edgar.py :: reduce_company_facts) ──────────────────────── */

    function num(value) {
        if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
        const n = Number(value);
        return isFinite(n) ? n : null;
    }
    function dateOk(text) {
        const parts = String(text == null ? '' : text).split('-');
        if (parts.length !== 3) return false;
        return parts.every((p) => /^\d+$/.test(p));
    }
    function daysBetween(start, end) {
        if (!dateOk(start) || !dateOk(end)) return null;
        const a = String(start).split('-').map(Number);
        const b = String(end).split('-').map(Number);
        const from = Date.UTC(a[0], a[1] - 1, a[2]);
        const to = Date.UTC(b[0], b[1] - 1, b[2]);
        const days = Math.round((to - from) / 86400000);
        return isFinite(days) ? days : null;
    }
    function unitsOf(doc, tag, unit) {
        const gaap = doc && doc.facts && doc.facts['us-gaap'];
        const node = gaap && typeof gaap === 'object' ? gaap[tag] : null;
        const rows = node && node.units ? node.units[unit] : null;
        return Array.isArray(rows) ? rows.filter((r) => r && typeof r === 'object') : [];
    }

    /* One headline's candidates, keyed by period end: annual report forms only, a real year for a
       flow, the most recently filed value winning a period (a restated comparative), and the primary
       tag beating its fallback on the same filing date. */
    function candidatesFor(doc, headline) {
        const best = {};
        for (let rank = 0; rank < headline.tags.length; rank++) {
            const tag = headline.tags[rank];
            unitsOf(doc, tag, headline.unit).forEach((raw) => {
                const form = String(raw.form == null ? '' : raw.form);
                if (ANNUAL_FORMS.indexOf(form) < 0) return;      /* a 10-Q never becomes a row */
                const end = String(raw.end == null ? '' : raw.end);
                if (!dateOk(end)) return;
                const value = num(raw.val);
                if (value === null) return;
                const start = String(raw.start == null ? '' : raw.start);
                if (headline.kind === 'flow') {
                    if (!start) return;                          /* a flow with no period is not a year */
                    const days = daysBetween(start, end);
                    if (days === null || days < MIN_ANNUAL_DAYS || days > MAX_ANNUAL_DAYS) return;
                }
                const filed = String(raw.filed == null ? '' : raw.filed);
                const candidate = {
                    concept: headline.key, label: headline.label, tag: tag, value: value,
                    unit: headline.unit, form: form, filed: filed, period: end, start: start,
                    fy: (typeof raw.fy === 'number') ? raw.fy : null, rank: rank,
                };
                const held = best[end];
                if (!held || filed > held.filed || (filed === held.filed && rank < held.rank)) {
                    best[end] = candidate;
                }
            });
        }
        return best;
    }

    /* A companyfacts document → the rows the panel shows, newest period first inside each concept.
       A concept the filer does not tag contributes nothing: no row, no zero, no dash. */
    function reduceFacts(doc, headlines, maxPeriods) {
        const list = Array.isArray(headlines) ? headlines : HEADLINES;
        const cap = Math.max(0, Math.floor(num(maxPeriods) === null ? MAX_PERIODS_PER_CONCEPT : maxPeriods));
        const rows = [];
        list.forEach((headline) => {
            const best = candidatesFor(doc, headline);
            Object.keys(best).map((end) => best[end])
                .sort((a, b) => (b.period > a.period ? 1 : (b.period < a.period ? -1 : (b.filed > a.filed ? 1 : -1))))
                .slice(0, cap)
                .forEach((row, i) => rows.push({
                    concept: row.concept, label: row.label, tag: row.tag, value: row.value,
                    unit: row.unit, form: row.form, filed: row.filed, period: row.period,
                    start: row.start, fy: row.fy, latest: i === 0,
                }));
        });
        return rows;
    }

    /* The server's rows, cleaned and ordered the same way (it already reduced them; this only drops
       a malformed row and pins the order so the picker and the table agree). */
    function normalizeRows(raw) {
        const order = HEADLINES.map((h) => h.key);
        const rows = [];
        (Array.isArray(raw) ? raw : []).forEach((row) => {
            if (!row || typeof row !== 'object') return;
            const value = num(row.value);
            const concept = String(row.concept == null ? '' : row.concept);
            const period = String(row.period == null ? '' : row.period);
            if (value === null || !concept || !dateOk(period)) return;
            rows.push({
                concept: concept, label: String(row.label == null ? concept : row.label),
                tag: String(row.tag == null ? '' : row.tag), value: value,
                unit: String(row.unit == null ? '' : row.unit),
                form: String(row.form == null ? '' : row.form),
                filed: String(row.filed == null ? '' : row.filed), period: period,
                start: String(row.start == null ? '' : row.start),
                fy: (typeof row.fy === 'number') ? row.fy : null,
                latest: false,
            });
        });
        rows.sort((a, b) => {
            const ai = order.indexOf(a.concept), bi = order.indexOf(b.concept);
            const az = ai < 0 ? order.length : ai, bz = bi < 0 ? order.length : bi;
            if (az !== bz) return az - bz;
            if (a.period !== b.period) return a.period < b.period ? 1 : -1;
            return a.filed < b.filed ? 1 : (a.filed > b.filed ? -1 : 0);
        });
        const seen = {};
        rows.forEach((row) => {
            if (!seen[row.concept]) { row.latest = true; seen[row.concept] = true; }
        });
        return rows;
    }

    /* The rows a payload carries: the server's reduced rows, or — if a payload carries the raw
       document instead — this module's own reduction, which is the same rule. */
    function rowsOf(payload) {
        if (!payload || typeof payload !== 'object') return [];
        if (Array.isArray(payload.rows) && payload.rows.length) return normalizeRows(payload.rows);
        if (payload.facts && typeof payload.facts === 'object') return reduceFacts(payload.facts);
        return normalizeRows(payload.rows);
    }

    /* ── the picker (pure) ───────────────────────────────────────────────────────────────────── */

    function conceptsOf(rows) {
        const out = [];
        const seen = {};
        (Array.isArray(rows) ? rows : []).forEach((row) => {
            if (!row || !row.concept || seen[row.concept]) return;
            seen[row.concept] = true;
            out.push({ key: row.concept, label: row.label || row.concept });
        });
        return out;
    }
    function pickedRows(rows, concept) {
        const key = String(concept == null ? '' : concept);
        if (!key) return [];
        return (Array.isArray(rows) ? rows : []).filter((row) => row && row.concept === key);
    }
    /* The concept to show: what the user picked when it is still there, else the first one. */
    function pickConcept(concepts, wanted) {
        const list = Array.isArray(concepts) ? concepts : [];
        if (!list.length) return '';
        const key = String(wanted == null ? '' : wanted);
        return list.some((c) => c.key === key) ? key : list[0].key;
    }

    /* ── formatting (pure) ───────────────────────────────────────────────────────────────────── */

    /* Thousands separators, no locale surprises: 416161000000 → '416,161,000,000'. The digits are
       grouped on the string, never by multiplying (a market cap × 10000 leaves float precision). */
    function full(value) {
        const n = num(value);
        if (n === null) return DASH;
        const negative = n < 0;
        let text = String(Math.abs(n));
        if (/[eE]/.test(text)) text = Math.abs(n).toExponential(2);
        const parts = text.split('.');
        const frac = parts[1] ? parts[1].slice(0, 6).replace(/0+$/, '') : '';
        const whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        return (negative ? '-' : '') + whole + (frac ? '.' + frac : '');
    }
    /* Billions/millions for the money columns; a per-share figure is never compacted (7.46 stays
       7.46 — rounding a filed EPS would be inventing a number). */
    function compact(value) {
        const n = num(value);
        if (n === null) return DASH;
        const abs = Math.abs(n);
        if (abs >= 1e12) return (n / 1e12).toFixed(2) + 'T';
        if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        return full(n);
    }
    function isPerShare(unit) { return /share/i.test(String(unit == null ? '' : unit)); }
    function valueText(row) {
        if (!row) return DASH;
        const n = num(row.value);
        if (n === null) return DASH;
        const text = (!isPerShare(row.unit) && Math.abs(n) >= 1e6) ? compact(n) : full(n);
        return row.unit ? text + ' ' + row.unit : text;
    }
    function usd(value) {
        const n = num(value);
        if (n === null) return DASH;
        return '$' + (Math.abs(n) >= 1e6 ? compact(n) : full(n));
    }
    function pct(value) {
        const n = num(value);
        if (n === null) return DASH;
        return (n > 0 ? '+' : '') + n.toFixed(2) + '%';
    }
    function periodLabel(row) {
        if (!row) return DASH;
        const fy = (typeof row.fy === 'number') ? 'FY' + row.fy + ' · ' : '';
        return fy + row.period;
    }

    /* ── the DOM strings (every value escaped) ───────────────────────────────────────────────── */

    function rowTitle(row) {
        const range = row.start ? row.start + ' → ' + row.period : row.period;
        return [row.label, full(row.value) + ' ' + row.unit, row.tag ? 'tag ' + row.tag : '',
                row.form + ' filed ' + row.filed, range].filter(Boolean).join(' · ');
    }
    function rowHtml(row) {
        const latest = row.latest ? ' <span class="tag ok">latest</span>' : '';
        return '<tr title="' + esc(rowTitle(row)) + '">'
            + '<td>' + esc(periodLabel(row)) + latest + '</td>'
            + '<td class="num" title="' + esc(full(row.value) + ' ' + row.unit + ' · ' + row.tag) + '">'
            + esc(valueText(row)) + '</td>'
            + '<td>' + esc(row.form || DASH) + '</td>'
            + '<td>' + esc(row.filed || DASH) + '</td>'
            + '<td class="dim" title="' + esc(row.tag) + '">' + esc(row.tag || DASH) + '</td>'
            + '</tr>';
    }
    function tableHtml(rows, concept, label) {
        const shown = pickedRows(rows, concept);
        if (!shown.length) {
            return '<div class="fundamentals-message dim">'
                + esc('this instrument has no ' + (label || 'selected') + ' value in the annual '
                      + 'filings the server sent.') + '</div>';
        }
        return '<table class="data fundamentals-table"><thead><tr>'
            + '<th>Period</th><th>Value</th><th>Form</th><th>Filed</th><th>XBRL tag</th>'
            + '</tr></thead><tbody>' + shown.map((row) => rowHtml(row)).join('') + '</tbody></table>';
    }
    function cryptoHtml(crypto, symbol) {
        const c = (crypto && typeof crypto === 'object') ? crypto : {};
        const supply = compact(c.circulating_supply) + (c.ticker ? ' ' + esc(c.ticker) : '');
        const cap = (num(c.max_supply) === null) ? ''
            : ' <span class="dim">of ' + compact(c.max_supply) + ' max</span>';
        const rows = [
            ['Rank', num(c.rank) === null ? DASH : '#' + full(c.rank),
                'market-cap rank on CoinGecko at the time of the call'],
            ['Price', usd(c.price), 'spot price, ' + str0(c.as_of)],
            ['Market cap', usd(c.market_cap), full(c.market_cap) + ' USD'],
            ['Circulating supply', supply + cap, 'as reported by CoinGecko', true],
            ['24h', pct(c.change_24h), 'change over the last 24 hours'],
        ];
        return '<table class="data fundamentals-crypto"><tbody>'
            + rows.map((r) => '<tr><td class="dim">' + esc(r[0]) + '</td>'
                /* r[3] === true marks the one value this panel builds as markup (the 'of 21M max' note);
                   both halves of it are already escaped or numeric, so nothing user-supplied slips past. */
                + '<td title="' + esc(r[2]) + '">' + (r[3] === true ? r[1] : esc(r[1])) + '</td></tr>').join('')
            + '</tbody></table>'
            + '<div class="fundamentals-note dim">'
            + esc(normalize(symbol) + ' has no SEC filings — ' + str0(c.name || c.ticker)
                  + ' is a crypto asset, so there is no 10-K to read.') + '</div>';
    }
    function str0(text) { return String(text == null ? '' : text); }

    function sourceLine(st) {
        if (st.source === 'edgar') {
            return 'SEC EDGAR' + (st.company && st.company.name ? ' · ' + st.company.name : '')
                + (st.company && st.company.cik ? ' · CIK ' + st.company.cik : '');
        }
        if (st.source === 'coingecko' && st.crypto) {
            return 'CoinGecko · ' + str0(st.crypto.name)
                + (num(st.crypto.rank) === null ? '' : ' · rank #' + full(st.crypto.rank));
        }
        return sourceLabel(st.source);
    }

    /* ── the panel state as data (pure) ──────────────────────────────────────────────────────── */

    /* `payload` is the route response, or null before the fetch; `err` is the fetch failure.
       Nothing here touches the DOM, so every sentence below is pinned by the selftest. */
    function plan(payload, err, symbol, now) {
        const at = Number(now) || Date.now();
        const sym = normalize(symbol);
        const st = {
            state: 'loading', symbol: sym, source: 'none', sourceLine: 'no source', company: null,
            rows: [], concepts: [], pick: '', crypto: null, count: 0,
            message: '', note: '', at: at, local: sourceOf(sym),
        };
        if (!sym) {
            st.state = 'nosymbol';
            st.message = 'no instrument is active yet — pick one in the top bar and its '
                + 'fundamentals load for it.';
            return st;
        }
        if (err) {
            st.state = 'error';
            st.message = 'the fundamentals request failed: ' + errText(err)
                + ' — press Refresh to try again.';
            return st;
        }
        if (!payload || typeof payload !== 'object') {
            if (st.local === 'none') {                 /* '^GSPC' can never be a US ticker: say so now */
                st.state = 'nosource';
                st.message = noSourceNote(sym);
                return st;
            }
            st.source = st.local;
            st.sourceLine = sourceLabel(st.local);
            st.message = st.local === 'coingecko'
                ? 'loading CoinGecko market data for ' + sym + '…'
                : 'loading SEC EDGAR filings for ' + sym + '…';
            return st;
        }

        /* From here on the server's answer is the authority. */
        const source = (payload.source === 'edgar' || payload.source === 'coingecko')
            ? payload.source : 'none';
        st.source = source;
        st.company = (payload.company && typeof payload.company === 'object') ? {
            cik: str0(payload.company.cik), ticker: str0(payload.company.ticker),
            name: str0(payload.company.name),
        } : null;
        st.crypto = (payload.crypto && typeof payload.crypto === 'object') ? payload.crypto : null;
        st.note = str0(payload.note);
        st.sourceLine = sourceLine(st);

        if (payload.ok === false) {
            st.state = 'error';
            st.message = 'the fundamentals lookup failed: ' + (str0(payload.error) || 'no reason given')
                + ' — press Refresh to try again.';
            return st;
        }
        if (source === 'none') {
            st.state = 'nosource';
            st.message = st.note || noSourceNote(sym);
            return st;
        }
        if (source === 'coingecko') {
            if (!st.crypto) {
                st.state = 'error';
                st.message = 'the server reported CoinGecko as the source but sent no market data '
                    + 'for ' + sym + ' — press Refresh to try again.';
                return st;
            }
            st.state = 'ok';
            st.sourceLine = sourceLine(st);
            return st;
        }
        st.rows = rowsOf(payload);
        st.concepts = conceptsOf(st.rows);
        st.pick = pickConcept(st.concepts, st.pick);
        st.count = st.rows.length;
        if (!st.count) {
            st.state = 'empty';
            st.message = 'the SEC facts for ' + sym + ' carry none of the headline concepts this '
                + 'panel shows — the filer does not tag them.';
            return st;
        }
        st.state = 'ok';
        return st;
    }

    /* ── state + the DOM half ────────────────────────────────────────────────────────────────── */

    const state = { plan: null, pick: '', polling: 'idle', unsubscribe: null, timer: null,
                    symbol: '', wired: false, busy: false };

    const FUNDAMENTALS_STYLE = `
.fundamentals-table, .fundamentals-crypto { width: 100%; }
.fundamentals-table td.num, .fundamentals-table th:nth-child(2) { text-align: right; }
.fundamentals-message, .fundamentals-note { padding: 4px 0 2px; font-size: 11.5px; }
.fundamentals-crypto td:first-child { width: 40%; }
.fundamentals-crypto td { padding: 3px 0; }`;

    function section() {
        if (typeof document === 'undefined' || !document || !document.querySelector) return null;
        return document.querySelector(VIEW);
    }
    function isActive() {
        const view = section();
        return !!(view && view.classList && view.classList.contains('active'));
    }
    /* Defensive by request: the engine's symbol is the authority when it is live, the app's
       instrument select is the fallback, and no app at all is an empty string rather than a throw. */
    function activeSymbol() {
        const fromState = (typeof S !== 'undefined' && S) ? S.symbol : '';
        const select = el('symbolSelect');
        return normalize(fromState || (select && select.value) || '');
    }
    function urlFor(symbol) { return URL_BASE + encodeURIComponent(normalize(symbol)); }

    function subText(st) {
        if (!st || !st.symbol) return 'filed fundamentals for the active instrument — pick one and '
            + 'they load';
        if (st.state === 'ok') {
            return st.symbol + ' · ' + st.sourceLine
                + (st.source === 'edgar' ? ' · ' + st.count + ' annual value(s)' : '');
        }
        if (st.state === 'loading') return st.symbol + ' · ' + st.message;
        return st.symbol + ' · ' + st.message;
    }

    function paint(st) {
        if (st) {
            state.plan = st;
            state.pick = st.pick || state.pick;
        }
        const current = state.plan;
        const sub = el('fundamentalsSub'), count = el('fundamentalsCount');
        const symbolCell = el('fundamentalsSymbol'), body = el('fundamentalsBody');
        const select = el('fundamentalsConcept');
        if (sub) sub.textContent = subText(current);
        if (symbolCell) symbolCell.textContent = (current && current.symbol) || DASH;
        if (count) {
            count.textContent = (current && current.state === 'ok')
                ? String(current.count || (current.crypto ? 5 : 0)) + ' value(s)' : '';
        }
        if (select) {
            const concepts = (current && current.concepts) || [];
            const wanted = pickConcept(concepts, state.pick);
            state.pick = wanted;
            select.innerHTML = concepts.length
                ? concepts.map((c) => '<option value="' + esc(c.key) + '"'
                    + (c.key === wanted ? ' selected' : '') + '>' + esc(c.label) + '</option>').join('')
                : '<option value="">—</option>';
            select.disabled = !concepts.length;
        }
        if (!body) return current;
        if (!current) {
            body.innerHTML = '<div class="fundamentals-message dim">Loading…</div>';
            return current;
        }
        if (current.state === 'ok' && current.source === 'coingecko') {
            body.innerHTML = cryptoHtml(current.crypto, current.symbol)
                + (current.note ? '<div class="fundamentals-note dim">' + esc(current.note) + '</div>' : '');
            return current;
        }
        if (current.state === 'ok') {
            const picked = current.concepts.filter((c) => c.key === state.pick)[0];
            body.innerHTML = tableHtml(current.rows, state.pick, picked ? picked.label : '')
                + (current.note ? '<div class="fundamentals-note dim">' + esc(current.note) + '</div>' : '');
            return current;
        }
        body.innerHTML = '<div class="fundamentals-message dim">' + esc(current.message) + '</div>';
        return current;
    }

    /* ── reading ─────────────────────────────────────────────────────────────────────────────── */

    function onPayload(payload) {
        const failed = !!(payload && payload.error);
        return paint(plan(failed ? null : payload, failed ? payload.error : null,
            state.symbol, Date.now()));
    }

    async function refresh() {
        if (state.busy) return state.plan;
        const symbol = activeSymbol();
        state.symbol = symbol;
        state.busy = true;
        const btn = el('fundamentalsRefresh');
        if (btn) btn.disabled = true;
        paint(plan(null, null, symbol, Date.now()));            /* 'loading' — never a blank panel */
        if (symbol) {
            try {
                /* the path is spelled out at the call site so the UI audit can resolve it */
                const payload = await api(`/api/fundamentals/${encodeURIComponent(symbol)}`);
                paint(plan(payload, null, symbol, Date.now()));
            } catch (e) {
                paint(plan(null, e, symbol, Date.now()));
            }
        }
        state.busy = false;
        if (btn) btn.disabled = false;
        return state.plan;
    }

    /* ── polling: the shared bus when it is loaded, this module's own tick when it is not ─────── */

    function startPoll(symbol) {
        const sym = normalize(symbol);
        if (!sym) { stopPoll(); return false; }
        if (state.polling !== 'idle' && state.symbol === sym) return false;
        stopPoll();
        state.symbol = sym;
        const bus = win().OFAPBUS;
        if (bus && typeof bus.subscribe === 'function') {
            paint(plan(null, null, sym, Date.now()));
            state.unsubscribe = bus.subscribe({ url: urlFor(sym), intervalMs: REFRESH_MS }, onPayload);
            state.polling = 'bus';
            return true;
        }
        state.polling = 'timer';        /* no delivery layer: tick() does the asking, on REFRESH_MS */
        void refresh();
        return true;
    }

    function stopPoll() {
        const was = state.polling;
        if (state.unsubscribe) {
            try { state.unsubscribe(); } catch (e) { /* the delivery layer is gone; nothing to release */ }
            state.unsubscribe = null;
        }
        state.polling = 'idle';
        return was !== 'idle';
    }

    /* Visibility decides everything: an off-screen panel releases the shared channel and costs
       nobody bandwidth; coming back on screen re-asks (the symbol may have moved underneath it). */
    function sync() {
        const active = isActive();
        if (!active) { stopPoll(); return state.plan; }
        startPoll(activeSymbol());
        return state.plan;
    }

    /* The one timer the panel owns: a cheap "should we ask again" check. A moved instrument
       re-subscribes immediately, and with no bus it is tick() — not a second timer — that asks on
       the REFRESH_MS cadence, so a panel with no delivery layer still refreshes. */
    function tick() {
        if (!isActive() || document.hidden || window.OFAP_PAUSED) return;
        if (window.OFAPINTENT && typeof window.OFAPINTENT.anyHeld === 'function'
                && window.OFAPINTENT.anyHeld()) return;
        const moved = activeSymbol() !== normalize(state.symbol);
        if (moved) { sync(); return; }
        if (state.polling !== 'timer') return;               /* the bus owns its own cadence */
        const st = state.plan || {};
        if ((Date.now() - (Number(st.at) || 0)) < REFRESH_MS) return;
        void refresh();
    }

    function wire() {
        if (state.wired) return;
        state.wired = true;
        if (typeof document !== 'undefined' && document && document.head
                && !el('fundamentalsStyles')) {
            const style = document.createElement('style');
            style.id = 'fundamentalsStyles';
            style.textContent = FUNDAMENTALS_STYLE;
            document.head.appendChild(style);
        }
        const btn = el('fundamentalsRefresh');
        if (btn) btn.addEventListener('click', () => { void refresh(); });
        const select = el('fundamentalsConcept');
        if (select) select.addEventListener('change', () => {
            state.pick = String(select.value || '');
            paint(state.plan);                                   /* re-render, no fetch: it is the same payload */
        });
        const symbolSelect = el('symbolSelect');
        if (symbolSelect) symbolSelect.addEventListener('change', () => { if (isActive()) sync(); });
        setInterval(tick, TICK_MS);
    }

    function watch() {
        const view = section();
        if (!view) return false;
        wire();
        if (isActive()) sync();
        new MutationObserver(() => {
            if (isActive()) sync();
            else stopPoll();                                     /* hidden: leave the channel to others */
        }).observe(view, { attributes: true, attributeFilter: ['class'] });
        return true;
    }

    window.OFAPFUNDAMENTALS = {
        VERSION: VERSION, VIEW: VIEW, URL_BASE: URL_BASE, REFRESH_MS: REFRESH_MS, TICK_MS: TICK_MS,
        DASH: DASH, ANNUAL_FORMS: ANNUAL_FORMS, HEADLINES: HEADLINES, CRYPTO_IDS: CRYPTO_IDS,
        NO_SOURCE: NO_SOURCE,
        esc: esc, normalize: normalize, cryptoAsset: cryptoAsset, sourceOf: sourceOf,
        sourceLabel: sourceLabel, noSourceNote: noSourceNote,
        num: num, daysBetween: daysBetween, unitsOf: unitsOf, candidatesFor: candidatesFor,
        reduceFacts: reduceFacts, normalizeRows: normalizeRows, rowsOf: rowsOf,
        conceptsOf: conceptsOf, pickedRows: pickedRows, pickConcept: pickConcept,
        full: full, compact: compact, valueText: valueText, usd: usd, pct: pct,
        periodLabel: periodLabel, rowTitle: rowTitle, rowHtml: rowHtml, tableHtml: tableHtml,
        cryptoHtml: cryptoHtml, sourceLine: sourceLine, subText: subText,
        plan: plan, paint: paint, refresh: refresh, onPayload: onPayload,
        startPoll: startPoll, stopPoll: stopPoll, sync: sync, tick: tick, wire: wire, watch: watch,
        urlFor: urlFor, activeSymbol: activeSymbol,
        state: () => state.plan, poll: () => state.polling, pick: () => state.pick,
    };

    if (typeof document !== 'undefined' && document) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
        else watch();
    }
})();
