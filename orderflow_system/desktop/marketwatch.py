"""Market watch (§87): the source's own symbol board — every instrument the venue lists, with
live bid/ask/change where the source can give them, honestly marked where it cannot.

Why a panel and not a filter on the Instruments table: the table answers "what does the engine
subscribe"; this answers "what does the market look like right now" — the platform's own Market
Watch, fed from the same source the engine reads. Bybit answers for the whole board in one REST
snapshot; MT5 answers per requested page off the terminal (selecting a page in the terminal's own
Market Watch is what makes its ticks readable); the NinjaTrader bridge republishes only what its
subscriptions carry, so its rows list the terminal's master instruments and say exactly that.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

BYBIT_TICKERS_URL = "https://api.bybit.com/v5/market/tickers?category=linear"
_TICKERS: dict[str, Any] = {"at": 0.0, "rows": []}
_TICKERS_TTL_S = 1.5           # the live panel re-reads ~every 1.5 s


def _bybit_board() -> list[dict[str, Any]]:
    """One REST call for the whole exchange board, cached a few seconds between polls."""
    now = time.time()
    if _TICKERS["rows"] and now - float(_TICKERS["at"] or 0.0) < _TICKERS_TTL_S:
        return list(_TICKERS["rows"])
    request = urllib.request.Request(BYBIT_TICKERS_URL, headers={"User-Agent": "ModFlow/1.0"})
    with urllib.request.urlopen(request, timeout=6) as response:   # noqa: S310 — the vendor's own https
        payload = json.loads(response.read().decode("utf-8"))
    rows: list[dict[str, Any]] = []
    for item in (payload.get("result", {}) or {}).get("list") or []:
        try:
            bid = float(item.get("bid1Price") or 0)
            ask = float(item.get("ask1Price") or 0)
            last = float(item.get("lastPrice") or 0)
            pct = float(item.get("price24hPcnt") or 0) * 100.0
        except (TypeError, ValueError):
            continue
        symbol = str(item.get("symbol") or "")
        if not symbol:
            continue
        rows.append({"symbol": symbol, "bid": bid, "ask": ask, "last": last,
                     "change_pct": round(pct, 2)})
    rows.sort(key=lambda row: row["symbol"])
    _TICKERS.update({"at": now, "rows": rows})
    return list(rows)


_MT5_OPEN: dict[str, tuple[float, float]] = {}   # symbol -> (fetched_at, prior-day open)
_MT5_OPEN_TTL_S = 300.0


def _mt5_daily_open(mt5: Any, symbol: str) -> float:
    """The daily-change basis for one symbol, cached: it is a *daily* number, so re-reading it on
    every poll would be waste — the live part of a poll is the tick, nothing else. A fresh day
    changes the basis at most every few minutes; the TTL is deliberately shorter than a session.
    """
    cached = _MT5_OPEN.get(symbol)
    now = time.time()
    if cached and now - cached[0] < _MT5_OPEN_TTL_S:
        return cached[1]
    opening = 0.0
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
        if rates is not None and len(rates) >= 1:
            opening = (float(rates[-1]["open"] or 0) if len(rates) == 1
                       else float(rates[-2]["open"] or 0))
    except Exception:
        opening = 0.0
    if opening:
        _MT5_OPEN[symbol] = (now, opening)
    return opening


def _mt5_visible_board(needle: str, limit: int, offset: int) -> dict[str, Any]:
    """The terminal's own Market Watch, mirrored (verified live: ``SymbolInfo.visible`` marks it).

    35 symbols visible on the owner's MetaQuotes demo — Forex majors/minors, indices, metals,
    then stocks, in the terminal's own path order. Read-only by construction: the panel never
    calls ``symbol_select``, so browsing it cannot change the terminal's watch list. Quotes and
    the daily change are computed off the running terminal, per requested page.
    """
    from orderflow_system.desktop import engine as engine_mod

    mt5, why = engine_mod._mt5_begin({})           # the same session helper the symbol search uses
    if mt5 is None:
        return {"ok": False, "source": "mt5", "rows": [], "total": 0, "offset": offset,
                "note": why or "MT5 is not available"}
    try:
        infos = mt5.symbols_get() or []
        visible = [item for item in infos if getattr(item, "visible", False)]
        visible.sort(key=lambda item: (str(getattr(item, "path", "") or ""),
                                       str(getattr(item, "name", "") or "")))
        names = [str(getattr(item, "name", "")) for item in visible if getattr(item, "name", "")]
        names = [name for name in names if not needle or needle in name.lower()]
        page = names[offset:offset + limit]
        rows: list[dict[str, Any]] = []
        for symbol in page:
            row = {"symbol": symbol, "bid": 0.0, "ask": 0.0, "last": 0.0, "change_pct": 0.0,
                   "quoted": False}
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick is not None:
                    price = float(tick.bid or tick.last or 0)
                    opening = _mt5_daily_open(mt5, symbol)
                    change = ((price - opening) / opening * 100.0) if opening and price else 0.0
                    row.update({"bid": float(tick.bid or 0), "ask": float(tick.ask or 0),
                                "last": float(tick.last or 0), "change_pct": round(change, 2),
                                "quoted": price > 0})
            except Exception:                       # one bad symbol must not sink the page
                pass
            rows.append(row)
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
    note = (f"MT5 — mirroring the terminal's own Market Watch "
            f"({len(names)} symbol{'s' if len(names) != 1 else ''} visible), quotes live off it"
            + (f" · filtered on “{needle}”" if needle else ""))
    return {"ok": True, "source": "mt5", "rows": rows, "total": len(names),
            "offset": offset, "note": note}


_VENUE_LABELS = {"binance": "Binance USDⓈ-M futures", "okx": "OKX USDT swaps",
                 "hyperliquid": "Hyperliquid perpetuals"}

#: The venue boards are whole listings, fetched once and reused for a few minutes: the panel
#: polls its board every 1.5 s, and a venue's catalogue changes when it lists something.
_BOARD_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_BOARD_TTL_S = 300.0


def _board_row(symbol: str) -> dict[str, Any]:
    """One listing row in the shape every board shares (quoted: False — a list, not quotes)."""
    return {"symbol": symbol, "bid": 0, "ask": 0, "last": 0, "change_pct": 0, "quoted": False}


def _exchange_board(venue: str, *, opener: Any = None) -> list[dict[str, Any]]:
    """The venue's own whole listing, as that venue's market-watch board.

    Before this, picking OKX/Binance/Hyperliquid in the panel answered with BYBIT's board: the
    dropdown said one venue, the rows were another's. Each venue publishes exactly the catalogue
    the capability checks already read, so this asks the same endpoint for the whole list instead
    of a membership test. Cached — see `_BOARD_TTL_S`.
    """
    import json
    import time
    import urllib.parse
    import urllib.request

    now = time.time()
    hit = _BOARD_CACHE.get(venue)
    if hit and now - hit[0] < _BOARD_TTL_S:
        return hit[1]

    rows: list[dict[str, Any]] = []
    if venue == "binance":
        from orderflow_system.data.binance_feed import BINANCE_REST

        req = urllib.request.Request(f"{BINANCE_REST}/fapi/v1/exchangeInfo",
                                     headers={"User-Agent": "OrderFlow-Analysis-Pro"})
        with (opener or urllib.request.urlopen)(req, timeout=10) as resp:
            info = json.loads(resp.read().decode("utf-8"))
        for entry in info.get("symbols", []) or []:
            if (str(entry.get("contractType")) == "PERPETUAL"
                    and str(entry.get("status")) == "TRADING"
                    and str(entry.get("quoteAsset")) == "USDT"):
                rows.append(_board_row(str(entry.get("symbol") or "")))
    elif venue == "okx":
        from orderflow_system.data.okx_feed import OKX_REST

        query = urllib.parse.urlencode({"instType": "SWAP"})
        req = urllib.request.Request(
            f"{str(OKX_REST).rstrip('/')}/api/v5/public/instruments?{query}",
            headers={"User-Agent": "OrderFlow-Analysis-Pro"})
        with (opener or urllib.request.urlopen)(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        for entry in payload.get("data", []) or []:
            inst = str(entry.get("instId") or "")
            if (str(entry.get("state")) == "live" and str(entry.get("ctType")) == "linear"
                    and str(entry.get("settleCcy")) == "USDT" and inst.endswith("-USDT-SWAP")):
                rows.append(_board_row(inst[: -len("-USDT-SWAP")] + "USDT"))
    elif venue == "hyperliquid":
        from orderflow_system.data.hyperliquid_feed import HYPERLIQUID_REST

        body = json.dumps({"type": "meta"}).encode("utf-8")
        req = urllib.request.Request(HYPERLIQUID_REST, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "OrderFlow-Analysis-Pro"})
        with (opener or urllib.request.urlopen)(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        for entry in payload.get("universe", []) or []:
            name = str((entry or {}).get("name") or "")
            # The venue's own spelling is lowercase ("kPEPE"); the app's symbols are upper-cased
            # everywhere (instrument_lookup normalises the same way, and KPEPEUSDT is the pinned
            # row), so the board matches the suite instead of the venue's cosmetics.
            if name and not (entry or {}).get("isDelisted"):
                rows.append(_board_row(name.upper() + "USDT"))

    rows = [row for row in rows if row["symbol"]]
    rows.sort(key=lambda row: row["symbol"])
    _BOARD_CACHE[venue] = (now, rows)
    return rows


def market_watch(source: str = "bybit", filter_text: str = "", limit: int = 60,
                 offset: int = 0) -> dict[str, Any]:
    """The board for one source. Never raises; a refusal carries its own sentence."""
    source = (source or "bybit").strip().lower()
    try:
        limit = max(1, min(200, int(limit or 60)))
    except (TypeError, ValueError):
        limit = 60
    try:
        offset = max(0, int(offset or 0))
    except (TypeError, ValueError):
        offset = 0
    needle = (filter_text or "").strip().lower()

    if source in ("bybit", "binance", "hyperliquid", "okx"):
        try:
            if source == "bybit":
                board = _bybit_board()
                note = "Bybit perpetuals — one REST snapshot of the whole board"
            else:
                board = _exchange_board(source)
                note = (f"{_VENUE_LABELS.get(source, source)} — the venue's whole listing "
                        f"(live prices arrive when it is the active source)")
        except Exception as exc:
            return {"ok": False, "source": source, "rows": [], "total": 0, "offset": offset,
                    "note": f"the {source} board is unavailable right now: "
                            f"{type(exc).__name__}: {exc}"}
        rows = [row for row in board if not needle or needle in row["symbol"].lower()]
        return {"ok": True, "source": source, "rows": rows[offset:offset + limit],
                "total": len(rows), "offset": offset,
                "note": note + (f" · filtered on “{filter_text.strip()}”" if needle else "")}

    if source == "mt5":
        return _mt5_visible_board(needle, limit, offset)

    if source == "ninjatrader":
        from orderflow_system.desktop import engine as engine_mod

        listed = engine_mod.ninjatrader_symbol_names()
        if not listed:
            return {"ok": False, "source": "ninjatrader", "rows": [], "total": 0, "offset": offset,
                    "note": "no bridge answered — start NinjaTrader (the bridge lives in its own "
                            "NinjaScript editor lane)"}
        names = sorted({str(row.get("Name") or "") for row in listed
                        if isinstance(row, dict) and row.get("Name")
                        and (not needle or needle in str(row.get("Name") or "").lower())})
        rows = [{"symbol": symbol, "bid": 0, "ask": 0, "last": 0, "change_pct": 0,
                 "quoted": False}
                for symbol in names[offset:offset + limit]]
        return {"ok": True, "source": "ninjatrader", "rows": rows, "total": len(names),
                "offset": offset,
                "note": "NinjaTrader — the terminal's master list; live bid/ask arrives for "
                        "instruments the bridge is subscribed to (open one from the Engine panel)"}

    return {"ok": False, "source": source, "rows": [], "total": 0, "offset": offset,
            "note": f"the market watch covers the exchange board, MT5 and the NinjaTrader bridge — "
                    f"{source} has no board of its own"}
