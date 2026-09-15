"""Search service — the palette's market side (plan Phase 4).

The palette started life as an index of the program (views, panels, settings,
actions). Phase 4 makes it a *market* instrument: type a ticker and get live rows
with honest feed labels, market status and prices — fed by the same stream the
panels use.

Three pieces, all pure enough to test offline:

* :class:`SymbolUniverse` — merges the symbol sources (pins/recents from the config,
  Alpaca's asset list when an account is linked, the crypto universe, the local
  instruments) and ranks them the way a trader types.
* :class:`RowBatcher` — coalesces live row updates so the palette receives one
  batched message per window instead of one per tick (Alpaca drops slow clients —
  code 407 — and the free plan's stream limit is small).
* :func:`feed_label` / :func:`market_status` — the honesty layer: a chip says IEX,
  Delayed SIP, Indicative or Crypto·Bybit, and never promises a feed the account
  cannot reach.

No network here: the asset list, the clock and the live prices arrive as injected
callables, which is what makes the ranking and no-keys paths testable.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

# ──────────────────────────────────────────────────────────────
# Feed labels — every chip the palette can show
# ──────────────────────────────────────────────────────────────

#: feed key → (short chip, full explanation for the tooltip)
FEED_LABELS: dict[str, tuple[str, str]] = {
    "iex": ("IEX", "Real-time US equities tape from IEX — the free plan's real-time feed "
                   "(one venue, a fraction of consolidated volume)."),
    "sip": ("SIP", "Full-market consolidated tape, real-time (paid plans)."),
    "delayed_sip": ("Delayed SIP", "Full-market SIP tape readable 15 minutes behind — the free plan's window."),
    "indicative": ("Indicative", "Options quotes on the free plan are indicative, not the consolidated OPRA feed."),
    "opra": ("OPRA", "Consolidated options quotes (paid plans)."),
    "alpaca_crypto": ("Crypto · Alpaca", "Alpaca's crypto venue — 24/7, works without an account for history."),
    "bybit": ("Crypto · Bybit", "The exchange's public perpetual feed — order-book depth included."),
    "mt5": ("MT5", "Streamed from your MetaTrader terminal (broker-dependent quality)."),
    "local": ("Local", "An instrument configured in this program; the feed depends on the data source."),
}

#: How fresh each feed is: realtime | delayed | indicative | endofday
FEED_DELIVERY: dict[str, str] = {
    "iex": "realtime", "sip": "realtime", "delayed_sip": "delayed",
    "indicative": "indicative", "opra": "realtime",
    "alpaca_crypto": "realtime", "bybit": "realtime", "mt5": "realtime", "local": "realtime",
}


def feed_label(feed: str) -> str:
    return FEED_LABELS.get(feed, (feed or "—", ""))[0]


def feed_explanation(feed: str) -> str:
    return FEED_LABELS.get(feed, ("", ""))[1]


# ──────────────────────────────────────────────────────────────
# Market status
# ──────────────────────────────────────────────────────────────

def market_status(clock: Optional[dict[str, Any]], now: Optional[float] = None) -> tuple[str, str]:
    """(status, tooltip) from an Alpaca clock payload.

    Alpaca's clock states open/closed and the next open/close timestamps; pre- and
    after-hours are derivable from those two times, and everything else stays
    ``unknown`` rather than being guessed.
    """
    if not clock:
        return "unknown", "Market calendar unavailable — start the engine with a linked Alpaca account for session state."
    is_open = bool(clock.get("is_open"))
    if is_open:
        nxt = clock.get("next_close")
        return "open", f"US session open — closes {nxt or 'unknown'}."
    now_ts = now if now is not None else time.time()
    nxt_open = clock.get("next_open")
    try:
        from datetime import datetime, timezone
        open_dt = datetime.fromisoformat(str(nxt_open).replace("Z", "+00:00")) if nxt_open else None
    except ValueError:
        open_dt = None
    if open_dt is not None:
        hours = (open_dt.timestamp() - now_ts) / 3600.0
        if hours <= 0:
            return "closed", "Session closed (the calendar is catching up)."
        if hours <= 4:
            return "pre", f"Pre-market / extended hours — the regular session opens in {hours:.1f} h."
        return "closed", f"Closed — next open {nxt_open}."
    return "closed", "Closed — the calendar reports no near-term open."


# ──────────────────────────────────────────────────────────────
# Rows
# ──────────────────────────────────────────────────────────────

@dataclass
class SymbolRow:
    symbol: str
    name: str = ""
    asset_class: str = ""
    exchange: str = ""
    source: str = ""                    # pin | recent | alpaca | crypto | local | option
    feed: str = ""
    status: str = "unknown"
    status_help: str = ""
    last: Optional[float] = None
    chg_pct: Optional[float] = None
    chg_help: str = ""
    volume: Optional[float] = None
    tradable: bool = True
    subscribed: bool = False
    depth: Optional[bool] = None        # False = the depth views cannot run here
    score: float = 0.0
    spark: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out = {
            "symbol": self.symbol, "name": self.name, "asset_class": self.asset_class,
            "exchange": self.exchange, "source": self.source, "feed": self.feed,
            "feed_label": feed_label(self.feed), "feed_help": feed_explanation(self.feed),
            "delivery": FEED_DELIVERY.get(self.feed, "realtime"),
            "status": self.status, "status_help": self.status_help,
            "last": self.last, "chg_pct": self.chg_pct, "chg_help": self.chg_help,
            "volume": self.volume,
            "tradable": self.tradable, "subscribed": self.subscribed,
        }
        if self.depth is not None:
            out["depth"] = self.depth
        if self.spark:
            out["spark"] = self.spark
        return out


# ──────────────────────────────────────────────────────────────
# Ranking
# ──────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return "".join(ch for ch in str(text or "").upper() if ch.isalnum())


def _subsequence(q: str, text: str) -> float:
    """0 when q's characters do not appear in order in text, else a 0..1 coverage."""
    if not q:
        return 0.0
    it = iter(text)
    hits = 0
    for ch in q:
        found = False
        for other in it:
            if other == ch:
                found = True
                break
        if not found:
            return 0.0
        hits += 1
    return hits / max(len(text), 1)


def score_row(q: str, symbol: str, name: str = "") -> float:
    """How well one row matches what was typed.

    Deliberately transparent, because ranking bugs are invisible until a user
    notices the wrong symbol on top:

        exact            1000
        symbol prefix     700 + 300·(q/len)     (shorter symbol = better hit)
        name token prefix 500
        symbol/name part  300
        fuzzy subsequence 100..200
    """
    if not q:
        return 0.0
    qn, sn, nn = _norm(q), _norm(symbol), _norm(name)
    if not sn:
        return 0.0
    if qn == sn:
        return 1000.0
    if sn.startswith(qn):
        return 700.0 + 300.0 * (len(qn) / len(sn))
    if nn and any(tok.startswith(qn) for tok in nn.split() if tok):
        return 500.0
    if qn in sn or (nn and qn in nn):
        return 300.0
    sub = max(_subsequence(qn, sn), _subsequence(qn, nn) if nn else 0.0)
    if sub > 0:
        return 100.0 + 100.0 * sub
    return 0.0


SORTS = ("relevance", "symbol", "name", "last", "chg", "volume", "feed")


def sort_rows(rows: list[SymbolRow], sort: str = "relevance") -> list[SymbolRow]:
    if sort == "symbol":
        return sorted(rows, key=lambda r: r.symbol)
    if sort == "name":
        return sorted(rows, key=lambda r: (r.name or r.symbol))
    if sort == "last":
        return sorted(rows, key=lambda r: (r.last is None, -(r.last or 0.0)))
    if sort == "chg":
        return sorted(rows, key=lambda r: (r.chg_pct is None, -(r.chg_pct or 0.0)))
    if sort == "volume":
        return sorted(rows, key=lambda r: (r.volume is None, -(r.volume or 0.0)))
    if sort == "feed":
        return sorted(rows, key=lambda r: (r.feed, r.symbol))
    return sorted(rows, key=lambda r: (-r.score, r.symbol))


# ──────────────────────────────────────────────────────────────
# The universe
# ──────────────────────────────────────────────────────────────

#: Crypto the Alpaca venue serves, used to label rows that are not local instruments.
ALPACA_CRYPTO = ("BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "DOGE/USD", "LINK/USD")


class SymbolUniverse:
    """Merge every symbol source into one ranked list.

    Sources, in the order they contribute (later ones only fill gaps):

    1. ``search.pins`` / ``search.recents`` from the user config — always first,
       because the user put them there.
    2. Alpaca's asset list (24 h disk cache) when an account is linked.
    3. The crypto universe (Alpaca pairs + the local crypto instruments).
    4. The program's own instruments, including their MT5 alias names, so a fuzzy
       "USTEC" finds NAS100USDT.
    """

    def __init__(
        self,
        *,
        config: Optional[dict[str, Any]] = None,
        assets_provider: Optional[Callable[[], list[dict[str, Any]]]] = None,
        clock_provider: Optional[Callable[[], Optional[dict[str, Any]]]] = None,
        live_provider: Optional[Callable[[str], dict[str, Any]]] = None,
        alpaca_linked: bool = False,
        alpaca_feed: str = "iex",
        alpaca_delayed: bool = True,
        alpaca_symbols: Optional[dict[str, str]] = None,
        local_feeds: Optional[dict[str, str]] = None,
        max_assets: int = 4000,
    ) -> None:
        self.config = config or {}
        self.assets_provider = assets_provider
        self.clock_provider = clock_provider
        self.live_provider = live_provider
        self.alpaca_linked = bool(alpaca_linked)
        self.alpaca_feed = alpaca_feed or "iex"
        self.alpaca_delayed = bool(alpaca_delayed)
        self.alpaca_symbols = dict(alpaca_symbols or {})       # app symbol → Alpaca symbol
        self.local_feeds = dict(local_feeds or {})             # app symbol → feed key
        self.max_assets = int(max_assets)
        self._assets: list[dict[str, Any]] = []
        self._assets_loaded_ms = 0

    # ── sources ──
    def _search_cfg(self) -> dict[str, Any]:
        return dict(self.config.get("search") or {})

    def recents(self) -> list[str]:
        return [str(s) for s in (self._search_cfg().get("recents") or [])]

    def pins(self) -> list[str]:
        return [str(s) for s in (self._search_cfg().get("pins") or [])]

    def watchlist(self) -> list[str]:
        return [str(s) for s in (self.config.get("watchlist") or [])]

    def local_instruments(self) -> list[dict[str, Any]]:
        return [i for i in (self.config.get("instruments") or []) if isinstance(i, dict)]

    def load_assets(self, force: bool = False) -> list[dict[str, Any]]:
        """Alpaca's tradable asset list, when an account is linked."""
        if not self.alpaca_linked or not self.assets_provider:
            return []
        fresh = (time.time() * 1000 - self._assets_loaded_ms) < 60_000
        if self._assets and fresh and not force:
            return self._assets
        try:
            rows = self.assets_provider() or []
        except Exception:                                    # noqa: BLE001 — never break search
            rows = []
        self._assets = [r for r in rows if isinstance(r, dict)][: self.max_assets]
        self._assets_loaded_ms = int(time.time() * 1000)
        return self._assets

    def asset_count(self) -> int:
        return len(self._assets)

    # ── row building ──
    def _feed_for(self, symbol: str, asset_class: str) -> str:
        if symbol in self.local_feeds:
            return self.local_feeds[symbol]
        if asset_class == "crypto" or "/" in symbol:
            return "bybit" if symbol in self.alpaca_symbols else "alpaca_crypto"
        if self.alpaca_linked:
            return self.alpaca_feed if self.alpaca_feed in ("iex", "sip") else "delayed_sip"
        return "local"

    def _row(self, symbol: str, *, name: str = "", asset_class: str = "", exchange: str = "",
             source: str, baseline: float = 0.0, tradable: bool = True) -> SymbolRow:
        feed = self._feed_for(symbol, asset_class)
        row = SymbolRow(symbol=symbol, name=name, asset_class=asset_class, exchange=exchange,
                        source=source, feed=feed, score=baseline, tradable=tradable)
        live = {}
        if self.live_provider:
            try:
                live = self.live_provider(symbol) or {}
            except Exception:                                # noqa: BLE001
                live = {}
        if live:
            row.last = live.get("last")
            row.chg_pct = live.get("chg_pct")
            row.chg_help = str(live.get("chg_help") or "")
            row.volume = live.get("volume")
            row.subscribed = bool(live.get("subscribed"))
            spark = live.get("spark") or []
            if spark:
                row.spark = [float(v) for v in spark][-32:]
            if live.get("depth") is False:
                row.depth = False
        elif self.alpaca_linked and asset_class in ("us_equity", "etf"):
            row.depth = False
        status, help_text = market_status(self.clock_provider() if self.clock_provider else None)
        row.status, row.status_help = status, help_text
        return row

    def build_rows(self) -> list[SymbolRow]:
        rows: dict[str, SymbolRow] = {}

        # First source wins: pins → recents → local instruments → Alpaca assets →
        # the crypto universe. A local instrument therefore keeps its real feed and
        # its live price even when Alpaca also lists the same symbol.
        def put(row: SymbolRow) -> None:
            if row.symbol:
                rows.setdefault(row.symbol, row)

        for symbol in self.pins():
            put(self._row(symbol, source="pin"))
        for symbol in self.recents():
            put(self._row(symbol, source="recent"))

        for inst in self.local_instruments():
            symbol = str(inst.get("symbol") or "")
            put(self._row(symbol, asset_class=str(inst.get("asset_class") or "").lower(), source="local"))

        if self.alpaca_linked:
            for asset in self.load_assets():
                symbol = str(asset.get("symbol") or "")
                put(self._row(symbol, name=str(asset.get("name") or ""),
                              asset_class=str(asset.get("class") or "us_equity"),
                              exchange=str(asset.get("exchange") or ""),
                              source="alpaca",
                              tradable=bool(asset.get("tradable", True))))

        for pair in ALPACA_CRYPTO:
            put(self._row(pair, asset_class="crypto", source="crypto"))

        return list(rows.values())

    # ── the endpoint behind /api/control/search/symbols ──
    def search(self, q: str, limit: int = 20, sort: str = "relevance",
               types: Optional[Iterable[str]] = None) -> dict[str, Any]:
        limit = max(1, min(int(limit or 20), 100))
        rows = self.build_rows()
        wanted = {str(t).lower() for t in (types or []) if str(t).strip()}
        if wanted:
            def matches(row: SymbolRow) -> bool:
                cls = (row.asset_class or "").lower()
                if "option" in wanted and row.source == "option":
                    return True
                if "crypto" in wanted and (cls == "crypto" or "/" in row.symbol):
                    return True
                if "stock" in wanted or "stocks" in wanted:
                    return cls in ("us_equity", "etf", "stock", "stocks", "")
                return cls in wanted
            rows = [r for r in rows if matches(r)]

        text = (q or "").strip()
        for row in rows:
            base = score_row(text, row.symbol, row.name)
            boost = 0.0
            if row.source == "pin":
                boost += 50.0
            elif row.source == "recent":
                boost += 20.0
            if row.last is not None:
                boost += 5.0
            if row.subscribed:
                boost += 5.0
            row.score = base + boost if base else 0.0
        if text:
            rows = [r for r in rows if r.score > 0]
        else:
            # no query: the user's own lists first, then the universe alphabetically
            order = {"pin": 0, "recent": 1, "local": 2}
            rows.sort(key=lambda r: (order.get(r.source, 3), r.symbol))
            return {
                "ok": True,
                "query": text,
                "sort": "default",
                "count": min(len(rows), limit),
                "total": len(rows),
                "linked": self.alpaca_linked,
                "assets": self.asset_count(),
                "rows": [r.to_dict() for r in rows[:limit]],
            }

        rows = sort_rows(rows, sort if sort in SORTS else "relevance")
        total = len(rows)
        limited = rows[:limit]
        return {
            "ok": True,
            "query": text,
            "sort": sort,
            "count": len(limited),
            "total": total,
            "linked": self.alpaca_linked,
            "assets": self.asset_count(),
            "rows": [r.to_dict() for r in limited],
        }


# ──────────────────────────────────────────────────────────────
# The batcher (T34)
# ──────────────────────────────────────────────────────────────

@dataclass
class BatchReport:
    seen: int = 0
    coalesced: int = 0
    dropped: int = 0
    batches: int = 0
    rows_sent: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"seen": self.seen, "coalesced": self.coalesced, "dropped": self.dropped,
                "batches": self.batches, "rows_sent": self.rows_sent}


class RowBatcher:
    """Coalesce per-symbol row updates into one message per window.

    Why it exists: a visible palette row can change on every tick, and Alpaca
    disconnects clients that cannot keep up (stream error 407). The batcher keeps
    the newest value per symbol inside a window, so N ticks on one symbol become one
    row in one batch — and the counters (``seen``/``coalesced``/``dropped``) prove it
    in the Logs view instead of being a claim.

    The queue is bounded: a symbol that keeps changing does not grow it, it only
    updates its slot; symbols beyond ``max_symbols`` are dropped and counted.
    """

    WINDOW_MS = 300
    MAX_SYMBOLS = 200

    def __init__(self, window_ms: int = WINDOW_MS, max_symbols: int = MAX_SYMBOLS) -> None:
        self.window_ms = int(window_ms)
        self.max_symbols = int(max_symbols)
        self._pending: dict[str, dict[str, Any]] = {}
        self._last_flush_ms = 0
        self.report = BatchReport()

    def offer(self, symbol: str, patch: dict[str, Any], now_ms: Optional[int] = None) -> bool:
        """Queue a row update. Returns False when it was dropped (cap reached)."""
        symbol = str(symbol or "")
        if not symbol or not patch:
            return False
        self.report.seen += 1
        if symbol not in self._pending and len(self._pending) >= self.max_symbols:
            self.report.dropped += 1
            return False
        if self._last_flush_ms == 0:
            # The window opens with the first row, so the first batch is not sent the
            # instant it arrives (an empty history would otherwise flush immediately).
            self._last_flush_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        if symbol in self._pending:
            self.report.coalesced += 1
            self._pending[symbol].update(patch)
        else:
            self._pending[symbol] = dict(patch)
        return True

    def due(self, now_ms: Optional[int] = None) -> bool:
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        return (now - self._last_flush_ms) >= self.window_ms

    def drain(self, now_ms: Optional[int] = None, force: bool = False) -> list[dict[str, Any]]:
        """Rows ready to send (empty while the window is still open, unless forced)."""
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        if not self._pending or (not force and not self.due(now)):
            return []
        self._last_flush_ms = now
        rows = [{"symbol": symbol, **patch} for symbol, patch in self._pending.items()]
        self.report.batches += 1
        self.report.rows_sent += len(rows)
        self._pending.clear()
        return rows

    def pending(self) -> int:
        return len(self._pending)

    def counters(self) -> dict[str, int]:
        return self.report.to_dict()


# ──────────────────────────────────────────────────────────────
# Option chain helpers (T38) — pure mapping, the REST call lives in api.py
# ──────────────────────────────────────────────────────────────

def parse_occ(contract: str) -> Optional[tuple[str, str, str, float]]:
    """OCC option symbol → (underlying, expiry, type, strike).

    ``AAPL260116C00200000`` = 6-char root + YYMMDD + C/P + strike×1000 (8 digits).
    Roots longer than six characters (``BRK.B260116C…``) keep their extra characters
    as the underlying, which is what Alpaca returns.
    """
    text = str(contract or "").strip()
    if not text:
        return None
    if " " in text:                                   # "AAPL AAPL260116C00200000"
        underlying, occ = text.split(" ", 1)
    else:
        occ = text
        underlying = text[:-15] if len(text) > 15 else ""
    if len(occ) < 15:
        return None
    tail = occ[-15:]
    digits = tail[:6]
    if not digits.isdigit() or tail[6].upper() not in ("C", "P"):
        return None
    try:
        strike = float(tail[7:15]) / 1000.0
    except ValueError:
        return None
    expiry = f"20{digits[:2]}-{digits[2:4]}-{digits[4:6]}"
    kind = "call" if tail[6].upper() == "C" else "put"
    return (underlying or occ[:-15], expiry, kind, strike)


def normalize_expiries(payload: Any) -> list[str]:
    """Expiry dates from an Alpaca option chain payload, sorted, ISO strings.

    Handles the snapshot shape (keys are OCC symbols) and the contracts shape
    (rows carry ``expiration_date``).
    """
    dates: set[str] = set()
    if isinstance(payload, dict):
        snapshots = payload.get("snapshots")
        if isinstance(snapshots, dict):
            for key in snapshots:
                parsed = parse_occ(key)
                if parsed:
                    dates.add(parsed[1])
        contracts = payload.get("contracts")
        if isinstance(contracts, list):
            for row in contracts:
                if isinstance(row, dict):
                    exp = str(row.get("expiration_date") or "")[:10]
                    if exp:
                        dates.add(exp)
    elif isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                exp = str(row.get("expiration_date") or "")[:10]
                if not exp:
                    parsed = parse_occ(str(row.get("symbol") or ""))
                    exp = parsed[1] if parsed else ""
                if exp:
                    dates.add(exp)
    return sorted(d for d in dates if d)


def chain_rows(payload: Any, expiry: str = "", strike_min: Optional[float] = None,
               strike_max: Optional[float] = None, option_type: str = "",
               limit: int = 400) -> list[dict[str, Any]]:
    """Flatten an Alpaca chain payload into rows the palette can render.

    Handles both shapes Alpaca uses: ``/v1beta1/options/snapshots/{underlying}``
    (``snapshots[occ_symbol] = {latestQuote, latestTrade, greeks, impliedVolatility}``)
    and ``/v2/options/contracts`` (a flat list of contract definitions).
    """
    wanted_type = (option_type or "").lower()
    out: list[dict[str, Any]] = []

    def consider(contract: str, data: dict[str, Any]) -> None:
        parsed = parse_occ(contract)
        if not parsed:
            return
        underlying, exp, ctype, strike = parsed
        if wanted_type and ctype != wanted_type:
            return
        if expiry and exp != expiry:
            return
        if strike_min is not None and strike < strike_min:
            return
        if strike_max is not None and strike > strike_max:
            return
        quote = (data or {}).get("latestQuote") or (data or {}).get("latest_quote") or {}
        trade = (data or {}).get("latestTrade") or (data or {}).get("latest_trade") or {}
        out.append({
            "contract": (contract or "").strip(),
            "underlying": underlying or str((data or {}).get("underlying_symbol") or ""),
            "type": ctype,
            "expiry": exp,
            "strike": strike,
            "bid": quote.get("bp"), "ask": quote.get("ap"),
            "bid_size": quote.get("bs"), "ask_size": quote.get("as"),
            "last": trade.get("p"),
            "iv": (data or {}).get("impliedVolatility"),
            "feed": "indicative",
            "feed_label": feed_label("indicative"),
        })

    if isinstance(payload, dict):
        snapshots = payload.get("snapshots")
        if isinstance(snapshots, dict):
            for contract, data in snapshots.items():
                if isinstance(data, dict):
                    consider(str(contract), data)
        contracts = payload.get("contracts")
        if isinstance(contracts, list):
            for row in contracts:
                if isinstance(row, dict):
                    consider(f"{row.get('underlying_symbol', '')} {row.get('symbol', '')}", row)
    elif isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                consider(f"{row.get('underlying_symbol', '')} {row.get('symbol', '')}", row)

    out.sort(key=lambda r: (r["expiry"], r["strike"] or math.inf, r["type"]))
    return out[: max(1, int(limit or 400))]


def with_greeks_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """A tiny summary the chain header can print without lying about coverage."""
    strikes = sorted({r["strike"] for r in rows if r["strike"]})
    calls = [r for r in rows if r["type"] == "call"]
    puts = [r for r in rows if r["type"] == "put"]
    return {
        "contracts": len(rows),
        "strikes": len(strikes),
        "strike_min": strikes[0] if strikes else None,
        "strike_max": strikes[-1] if strikes else None,
        "calls": len(calls),
        "puts": len(puts),
        "expiries": sorted({r["expiry"] for r in rows if r["expiry"]}),
    }
