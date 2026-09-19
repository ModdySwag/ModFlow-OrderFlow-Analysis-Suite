"""Instrument look-up (§82) — turning whatever the user typed into what the app can stream.

The Engine view's symbol box writes a display symbol and re-fetches; it never asks for
anything new. This module is the pure half of the answer: given the config's instrument
rows, the engine's streaming symbol list and the active data source, it says what a typed
symbol *is* — streamable now, configured but off, addable from the venue, unknown — plus
the suggestions worth offering and the closed set of actions the panel may run.

Pure on purpose: no config loading, no network, no MT5. Callers (``api.py``) supply the
facts, and the two texts a user reads (``reason``) come from here so the panel, the wizard
and the engine cannot describe the same refusal in three different ways.

Why an alias table at all: people type the market's common name (``NQ1!``, ``USTEC``,
``GOLD``), not this app's row name. An alias may only point at an instrument the app
already ships, so resolving one can never invent a stream.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

#: States a typed symbol can be in. ``live`` = enabled and the engine is streaming it;
#: ``ready`` = enabled, engine stopped; ``disabled`` = a configured row that is switched
#: off; ``available`` = no row, but the active venue lists it (an MT5 broker symbol, a
#: NinjaTrader instrument); ``unsupported`` = a row the active source cannot carry;
#: ``unknown`` = nothing matches.
STATES = ("live", "ready", "disabled", "available", "unsupported", "unknown")

#: The closed action set the panel may offer. Everything here is an existing app path —
#: ``use`` writes the symbol, ``start_engine``/``enable``/``add`` are the wizard's own
#: calls, ``map_broker`` opens the Instruments view where the MT5 name is edited.
ACTIONS = ("use", "start_engine", "enable", "add", "map_broker", "open_instruments")

#: Common market names → the app's own instrument row. Deliberately small: every value is
#: a symbol this app ships (``config_store.default_config``), so the table cannot point at
#: something that does not exist. Broker-side spellings (Exness' ``USTECm``, TradingView's
#: continuous ``NQ1!``) are handled by ``alias_target``'s suffix rules, not listed out.
ALIASES: dict[str, str] = {
    # Nasdaq-100 (the app's index proxy for the CME future)
    "NQ": "NAS100USDT", "NDX": "NAS100USDT", "NASDAQ": "NAS100USDT", "NASDAQ100": "NAS100USDT",
    "NAS100": "NAS100USDT", "US100": "NAS100USDT", "USTEC": "NAS100USDT", "NAS100USD": "NAS100USDT",
    # S&P 500 / Dow / DAX / FTSE / Nikkei
    "ES": "SP500", "SPX": "SP500", "SPX500": "SP500", "US500": "SP500",
    "YM": "DJ30", "US30": "DJ30", "DOW": "DJ30", "DOWJONES": "DJ30",
    "DAX": "DAX40", "DE40": "DAX40", "DE30": "DAX40", "GER40": "DAX40",
    "FTSE": "UK100", "FTSE100": "UK100",
    "NIKKEI": "NIKKEI225", "JP225": "NIKKEI225",
    # Metals and energy
    "GOLD": "XAUUSDT", "XAUUSD": "XAUUSDT", "SILVER": "XAGUSD",
    "WTI": "USOIL", "BRENT": "UKOIL", "CRUDE": "USOIL",
}


def normalise(text: Any) -> str:
    """Upper-case, trim, collapse inner whitespace and drop wrapping quotes.

    ``" nq1! "`` and ``NQ1!`` must be the same query; anything else the user typed is
    left exactly as written, because a broker symbol is a name we do not get to correct.
    """
    raw = str(text or "").strip()
    while len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()
    return " ".join(raw.split()).upper()


def alias_target(query: Any, aliases: Mapping[str, str] = ALIASES) -> Optional[str]:
    """The app symbol a typed name stands for, or None.

    Tries the table exactly, then the two conventions the financial web actually uses:
    TradingView's continuous-future suffix (``NQ1!`` → ``NQ1`` → ``NQ``) and a broker's
    trailing ``m`` (Exness' ``USTECm`` → ``USTEC``). Both are *lookups* — a suffix is only
    dropped when the shorter form is a known alias, never to guess.
    """
    q = normalise(query)
    if not q:
        return None
    seen: list[str] = [q]
    trimmed = q
    while trimmed.endswith("!"):
        trimmed = trimmed[:-1]
        seen.append(trimmed)
    if trimmed.endswith("1") and len(trimmed) > 2:
        seen.append(trimmed[:-1])              # continuous-future month marker: NQ1 → NQ
    if trimmed.endswith("M") and len(trimmed) > 3:
        seen.append(trimmed[:-1])              # broker suffix: USTECM → USTEC
    for candidate in seen:
        hit = aliases.get(candidate)
        if hit:
            return hit
    return None


def source_reason(row: Mapping[str, Any], source: str, mt5_available: bool = False) -> Optional[str]:
    """Why the active source cannot carry this row, in the same words the engine uses.

    Mirrors ``engine.select_instruments``' gates for the two refusals a user can act on;
    returns None when nothing in the source rules objects (the engine may still skip the
    row for other reasons, and the caller says so).
    """
    symbol = str(row.get("symbol") or "")
    src = str(source or "").lower()
    if src in ("bybit", "binance", "hyperliquid", "okx"):
        bybit_ok = bool(row.get("bybit_symbol")) or symbol in _bybit_ish()
        if not bybit_ok:
            return "Bybit perps list crypto only — switch to MT5 (Windows) for this instrument"
    if src in ("alpaca", "all"):
        if not row.get("alpaca_symbol"):
            return ("Alpaca serves US equities/ETFs/options and crypto pairs — "
                    "give this instrument an Alpaca symbol in the Alpaca view")
    if src == "mt5" and not mt5_available and not row.get("mt5_symbol"):
        return "MT5 is not available on this machine (or the row has no broker symbol)"
    if src == "ninjatrader":
        root = normalise(symbol).removesuffix("1").removesuffix("!")
        if not row.get("ninjatrader_symbol") and root not in _nt_roots():
            return ("the NinjaTrader bridge streams your terminal's own instruments — add this "
                    "one from the Instruments panel (source: NinjaTrader)")
    return None


#: The step that turns each refusal into a path (§82). The reason above is the engine's own
#: sentence and is pinned to it by test; this is the addition — what to DO about it, told in
#: the app's own vocabulary (the same doors exist today, nothing new is promised).
_FIX_HINTS = {
    "exchange": ("switch the data source to MetaTrader 5 for indices, metals and FX "
                 "(☰ ▸ sources, or the setup assistant) and map the broker symbol"),
    "alpaca": "give this instrument an Alpaca symbol in the Alpaca view, then enable it",
    "mt5": "install and log in to a MetaTrader 5 terminal, then set the bridge up in the setup assistant",
    "ninjatrader": ("point the suite at NinjaTrader (☰ ▸ sources, or the setup assistant) once the "
                    "bridge is running — then add the instrument from your terminal's own list"),
}


def source_fix_hint(source: str, mt5_available: bool = False, row: Optional[Mapping[str, Any]] = None) -> str:
    """What to do about a source refusal — the panel's actionable second sentence (§82)."""
    src = str(source or "").lower()
    if src == "ninjatrader":
        return _FIX_HINTS["ninjatrader"]
    if src in ("bybit", "binance", "hyperliquid", "okx"):
        # A row that carries an Alpaca mapping streams on Alpaca — telling NVDA's user to go
        # find MT5 while the linked account is right there was the reported surprise.
        if row is not None and str(row.get("alpaca_symbol") or "").strip():
            return ("switch the data source to Alpaca for US equities and ETFs (☰ ▸ sources, or "
                    "the setup assistant); MetaTrader 5 covers indices, metals and FX")
        return _FIX_HINTS["exchange"]
    if src in ("alpaca", "all"):
        return _FIX_HINTS["alpaca"]
    if src in ("mt5", "both"):
        if mt5_available:
            return "map the broker symbol for this instrument (setup assistant ▸ MetaTrader 5)"
        return _FIX_HINTS["mt5"]
    return ""


_NT_ROOTS_CACHE: Optional[frozenset] = None


def _nt_roots() -> frozenset:
    """The engine's NinjaTrader root list, imported lazily — derived, never a second copy."""
    global _NT_ROOTS_CACHE
    if _NT_ROOTS_CACHE is None:
        try:
            from orderflow_system.desktop import engine as engine_mod
            _NT_ROOTS_CACHE = frozenset(getattr(engine_mod, "NINJATRADER_ROOTS", ()))
        except Exception:                     # pragma: no cover — a bare import must not break
            _NT_ROOTS_CACHE = frozenset()
    return _NT_ROOTS_CACHE


_BYBIT_ISH_CACHE: Optional[frozenset] = None


def _bybit_ish() -> frozenset:
    """The store's own Bybit list, imported lazily — derived, never a second copy."""
    global _BYBIT_ISH_CACHE
    if _BYBIT_ISH_CACHE is None:
        try:
            from orderflow_system.desktop import config_store
            _BYBIT_ISH_CACHE = frozenset(config_store.BYBIT_FALLBACK_SYMBOLS)
        except Exception:                     # pragma: no cover — a bare import must not break
            _BYBIT_ISH_CACHE = frozenset()
    return _BYBIT_ISH_CACHE



def _rows_by_symbol(instruments: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(i.get("symbol") or "").upper(): i for i in instruments if i.get("symbol")}


def _common_prefix_len(a: str, b: str) -> int:
    """How many leading characters two names share (both already normalised)."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def alias_keys_for(symbol: str, aliases: Mapping[str, str] = ALIASES) -> list[str]:
    """Alias spellings that point at this row, longest first.

    Used as a *search list* against a broker's own symbols ("this row's market is called
    USTEC or US100 or NAS100 out there — which of those does your broker list?").
    """
    keys = [key for key, target in aliases.items() if str(target).upper() == str(symbol).upper()]
    keys.sort(key=len, reverse=True)
    return keys


def suggestions_for(
    query: Any,
    instruments: Sequence[Mapping[str, Any]],
    engine_symbols: Sequence[str] = (),
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Close matches for a query, best first: exact > prefix > substring > class/alias.

    Pure ranking over the rows the caller passed — no venue calls. The note says *why* a
    row is interesting, so the panel can show "NAS100USDT · Indices · alias for NQ".
    """
    q = normalise(query)
    if not q:
        return []
    streaming = {str(s).upper() for s in engine_symbols}
    rows = _rows_by_symbol(instruments)
    scored: list[tuple[int, dict[str, Any]]] = []
    for key, target in ALIASES.items():
        if key != q and (key.startswith(q) or q.startswith(key) or _common_prefix_len(q, key) >= 3):
            row = rows.get(target)
            if row is not None:
                scored.append((55, {**row, "note": f"alias for {key}"}))
    for symbol, row in rows.items():
        note = str(row.get("asset_class") or "")
        if symbol == q:
            scored.append((100, {**row, "note": "exact"}))
        elif symbol.startswith(q):
            scored.append((70, {**row, "note": note}))
        elif q in symbol:
            scored.append((40, {**row, "note": note}))
        elif _common_prefix_len(q, symbol) >= 3:
            # near-misses are the point of a suggestion list: NAS99 → NAS100USDT
            scored.append((30, {**row, "note": note}))
        elif q and q in str(row.get("asset_class") or "").upper():
            scored.append((20, {**row, "note": note}))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("symbol"))))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _score, row in scored:
        symbol = str(row["symbol"])
        if symbol in seen:
            continue
        seen.add(symbol)
        out.append({
            "symbol": symbol,
            "asset_class": str(row.get("asset_class") or ""),
            "enabled": bool(row.get("enabled")),
            "streaming": symbol in streaming,
            "note": str(row.get("note") or ""),
        })
        if len(out) >= max(1, int(limit)):
            break
    return out


def resolve(
    query: Any,
    *,
    instruments: Sequence[Mapping[str, Any]],
    engine_symbols: Sequence[str] = (),
    source: str = "bybit",
    running: bool = False,
    mt5_available: bool = False,
    mt5_known: Optional[Iterable[str]] = None,
    nt_known: Optional[Iterable[str]] = None,
    alpaca_known: Optional[Iterable[str]] = None,
    alpaca_by_norm: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """What the typed symbol is, why, what to offer next. Pure — the caller supplies facts.

    ``mt5_known`` / ``nt_known`` are the venues' own symbol lists when they were cheap to fetch
    (the MT5 broker list, the NinjaTrader terminal's instrument list); they turn a name the app
    has never heard of into ``available`` instead of ``unknown`` (that is the whole point of the
    §82 pass: NQ1!-style queries get an answer, not silence).
    """
    raw = str(query or "")
    q = normalise(raw)
    rows = _rows_by_symbol(instruments)
    engine_set = {str(s).upper() for s in engine_symbols}
    broker_by_norm = {normalise(s): s for s in (mt5_known or ())}
    broker_exact = {str(s) for s in (mt5_known or ())}
    # MEM-B-09: a caller that already holds the normalised map (the resolver's cached index)
    # passes it in — the per-call rebuild of a several-thousand-entry dict is avoided.
    if alpaca_by_norm is None:
        alpaca_by_norm = {normalise(s): s for s in (alpaca_known or ())}
    hit_exact = broker_by_norm.get(q, "")
    base: dict[str, Any] = {
        "query": raw, "symbol": q, "state": "unknown", "reason": "", "hint": "", "via": None,
        "instrument": None, "actions": ["open_instruments"], "suggestions": [], "broker_name": "",
        "add_source": "",
    }
    if not q:
        base["reason"] = "type an instrument name"
        return base

    row = rows.get(q)
    via = "exact" if row is not None else None
    if row is None:
        target = alias_target(q)
        if target and target in rows:
            row = rows[target]
            via = "alias"
    if row is not None:
        symbol = str(row["symbol"])
        entry = {
            "symbol": symbol,
            "asset_class": str(row.get("asset_class") or ""),
            "enabled": bool(row.get("enabled")),
            "mt5_symbol": str(row.get("mt5_symbol") or ""),
            "bybit_symbol": str(row.get("bybit_symbol") or ""),
            "alpaca_symbol": str(row.get("alpaca_symbol") or ""),
            "ninjatrader_symbol": str(row.get("ninjatrader_symbol") or ""),
            "tick_size": row.get("tick_size"),
        }
        base["symbol"] = symbol
        base["instrument"] = entry
        base["via"] = via
        # Broker spellings are per-broker and case-sensitive (measured: a MetaQuotes demo lists
        # US500M / USTEC, while the shipped defaults are the Exness-style US500m / USTECm — and
        # symbol_info("US500m") is None there). When the broker list is known and the row's own
        # mapping is not on it, the typed name is offered as the replacement mapping instead of
        # letting "enable" walk into a refusal.
        mapping = str(entry["mt5_symbol"] or "")
        mapping_ok = bool(mapping) and (not broker_exact or mapping in broker_exact)
        remap_hit = ""
        if not mapping_ok:
            if hit_exact:
                remap_hit = hit_exact
            else:
                for alias_key in alias_keys_for(symbol):
                    candidate = broker_by_norm.get(alias_key)
                    if candidate:
                        remap_hit = candidate
                        break
        base["broker_name"] = remap_hit or mapping
        # §82: the source's own gate comes FIRST. "Enable it and restart" is a lie on a feed
        # that cannot carry the instrument (the reported case: NQ on the exchange feed answers
        # "crypto only"), and the engine would skip the row at start with the same sentence —
        # so the look-up says it now, with the step that fixes it.
        gate = source_reason(row, source, mt5_available)
        if gate:
            base["state"] = "unsupported"
            base["reason"] = gate
            base["hint"] = source_fix_hint(source, mt5_available, row)
            base["actions"] = ["open_instruments"] if str(source).lower() in (
                "bybit", "binance", "hyperliquid", "okx", "alpaca", "all") else ["map_broker", "open_instruments"]
            return base
        if not entry["enabled"]:
            base["state"] = "disabled"
            if remap_hit:
                base["reason"] = (f"{symbol} is switched off, and its broker symbol "
                                  f"({mapping or 'none'}) is not one of your broker's names — "
                                  f"it lists {remap_hit}: add it with that symbol and restart")
                base["actions"] = ["add", "open_instruments"]
            else:
                base["reason"] = (f"{symbol} is configured but switched off — enable it and restart "
                                  "the engine to stream it")
                base["actions"] = ["enable", "open_instruments"]
        elif running and symbol in engine_set:
            base["state"] = "live"
            base["reason"] = "" if via == "exact" else f"{q} → {symbol}"
            base["actions"] = ["use"]
        elif not running:
            base["state"] = "ready"
            if remap_hit:
                base["reason"] = (f"{symbol} is enabled but mapped to {mapping or 'nothing'}, which your "
                                  f"broker does not list — it lists {remap_hit}: re-add it with that symbol")
                base["actions"] = ["add", "start_engine"]
            else:
                base["reason"] = f"{symbol} is enabled — the engine is stopped; start it to stream"
                base["actions"] = ["use", "start_engine"]
        else:
            base["state"] = "unsupported"
            base["reason"] = (f"{symbol} is enabled but the running engine skipped it — "
                              "check the source rules in Instruments")
            base["actions"] = ["map_broker", "open_instruments"]
        return base

    if hit_exact and str(source).lower() in ("mt5", "both"):
        base["state"] = "available"
        base["symbol"] = hit_exact
        base["broker_name"] = hit_exact
        base["reason"] = f"your MT5 broker lists {hit_exact} — add it, enable it and restart the engine"
        base["actions"] = ["add", "open_instruments"]
        return base

    # NinjaTrader: the terminal's own list is the venue listing. An exact full name ("NQ 12-26")
    # is used as the row name; a root query ("NQ", "NQ1", "NQ1!") keeps the root as the app symbol
    # and records the terminal's front-month name as the broker stamp — the MT5 pattern.
    if str(source).lower() == "ninjatrader" and nt_known:
        nt_names = [str(n).strip() for n in nt_known if str(n).strip()]
        base_name = q.removesuffix("!").removesuffix("1")
        exact_full = next((n for n in nt_names if normalise(n) == q), None)
        if exact_full is not None:
            symbol_out, matched = q, exact_full
        else:
            symbol_out = base_name
            matched = next((n for n in nt_names if normalise(n).split(" ")[0] == base_name), None)
        if matched:
            base["state"] = "available"
            base["symbol"] = symbol_out
            base["broker_name"] = matched
            base["reason"] = (f"your NinjaTrader terminal lists {matched} — add it, enable it and "
                              "restart the engine")
            base["actions"] = ["add", "open_instruments"]
            return base

    # §82-ext: the linked Alpaca account's asset list is a venue listing too — the same shape as
    # MT5's broker list and the NT terminal's names. A US ticker only Alpaca carries (SPY, QQQ)
    # used to end at "unknown" while the add endpoint would have taken it (a user kept trying).
    # The door names its own venue, so a Bybit-source session still writes the Alpaca stamp.
    if alpaca_by_norm:
        hit_alpaca = alpaca_by_norm.get(q, "")
        if hit_alpaca:
            base["state"] = "available"
            base["symbol"] = hit_alpaca
            base["broker_name"] = hit_alpaca
            base["add_source"] = "alpaca"
            base["reason"] = (f"your Alpaca account lists {hit_alpaca} — add it, then make "
                               "Alpaca the data source and restart the engine to stream it")
            base["actions"] = ["add", "open_instruments"]
            return base

    base["state"] = "unknown"
    base["reason"] = (f"{q} is not an instrument this app can stream: no configured row, and no "
                      "wired venue lists that name")
    base["suggestions"] = suggestions_for(q, instruments, engine_symbols)
    return base
