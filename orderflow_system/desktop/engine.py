"""
Engine controller — owns the live OrderflowSystem instance.

The GUI never edits Python source: the controller translates the JSON config
into the repo's dataclass configs, applies them to the settings module, then
builds and runs ``OrderflowSystem`` on the server's event loop.

Lifecycle:  stopped → starting → running → stopping → stopped
"""

from __future__ import annotations

import asyncio
import copy
import functools
import logging
import socket
import sys
import threading
import time
from typing import Any, Optional

from orderflow_system.config import settings
from orderflow_system.config.settings import (
    DataSource,
    InstrumentConfig,
    get_all_configs,
)
from orderflow_system.desktop import config_store
from orderflow_system.atlas import freshness as fresh

logger = logging.getLogger(__name__)

#: Bybit perpetuals only carry crypto; everything else needs MT5 (Windows).
#: This is the *offline* fallback — the config is the real source of truth, because
#: `/instruments/add` stamps `bybit_symbol` from the venue's own catalogue.
BYBIT_SUPPORTED = set(config_store.BYBIT_FALLBACK_SYMBOLS)


def bybit_capable(spec: dict[str, Any]) -> bool:
    """Can the Bybit feed serve this instrument?

    Prefers the config: a symbol added from the venue catalogue carries a
    `bybit_symbol` the venue itself confirmed, which is stronger evidence than the
    list of instruments this repo happens to ship.
    """
    return bool(spec.get("bybit_symbol")) or spec.get("symbol") in BYBIT_SUPPORTED


def _crypto_class(spec: dict[str, Any]) -> bool:
    """True when the row is a crypto instrument — the only class the exchange venues trade.

    The offline test used to be `symbol.endswith("USDT")`, which quietly claimed NAS100USDT (an
    index CFD) and XAUUSDT (gold) for Binance/OKX/Hyperliquid: /datasources promised instruments
    the venue does not list, and the engine had no gate of its own to catch it. Rows with no
    asset_class (hand-built dicts, older configs) fall back to the shipped support list.
    """
    asset_class = str(spec.get("asset_class") or "").strip().lower()
    if asset_class:
        return asset_class == "crypto"
    return str(spec.get("symbol") or "").upper() in BYBIT_SUPPORTED


def binance_capable(spec: dict[str, Any]) -> bool:
    """Can the Binance USDⓈ-M feed serve this instrument?

    Offline rule: Binance futures lists the same USDT perpetuals this suite ships (a config added
    from the venue catalogue proves itself with `binance_symbol`). The live check is
    `/api/control/capabilities?refresh=true`, which asks exchangeInfo and reports per symbol.
    """
    if spec.get("binance_symbol"):
        return True
    return _crypto_class(spec)


def hyperliquid_capable(spec: dict[str, Any]) -> bool:
    """Can the Hyperliquid feed serve this instrument?

    Offline rule: the venue trades crypto perpetuals, and this suite's USDT instruments map onto
    its coins by stripping the quote suffix (a config added from the venue catalogue proves itself
    with `hyperliquid_symbol`). The live check is `/api/control/capabilities?refresh=true`, which
    reads the venue's meta listing and reports per symbol.
    """
    if spec.get("hyperliquid_symbol"):
        return True
    return _crypto_class(spec)


def okx_capable(spec: dict[str, Any]) -> bool:
    """Can the OKX feed serve this instrument?

    Offline rule: OKX lists the same USDT swaps this suite ships (a config added from the venue
    catalogue proves itself with `okx_symbol`). The live check is
    `/api/control/capabilities?refresh=true`, which reads the venue's instruments listing and
    reports per symbol.
    """
    if spec.get("okx_symbol"):
        return True
    return _crypto_class(spec)


#: The futures roots NinjaTrader ships with — the offline rule for the look-up (a row added from
#: the terminal's own list proves itself with `ninjatrader_symbol`). NQ1 / NQ1! style names strip
#: to their root here; the bridge resolves the front month.
NINJATRADER_ROOTS = {
    "NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "MGC",
    "SI", "SIL", "NG", "HG", "6E", "6B", "6J", "6A", "6C", "6S", "ZB", "ZN", "ZF",
}


def ninjatrader_capable(spec: dict[str, Any]) -> bool:
    """Can the NinjaTrader bridge serve this instrument?

    Prefers the config: a row added from the terminal carries a `ninjatrader_symbol` the bridge
    itself resolved (front month included), which is stronger evidence than the roots this repo
    happens to ship.
    """
    if str(spec.get("ninjatrader_symbol") or "").strip():
        return True
    root = str(spec.get("symbol") or "").upper().removesuffix("1").removesuffix("!")
    return root in NINJATRADER_ROOTS


def ninjatrader_status(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Is the bridge answering on this machine? A TCP connect, nothing more."""
    payload = payload or {}
    host = str(payload.get("host") or getattr(settings.NINJATRADER, "host", "127.0.0.1") or "127.0.0.1")
    try:
        port = int(payload.get("port") or getattr(settings.NINJATRADER, "port", 8790) or 8790)
    except (TypeError, ValueError):
        port = 8790
    info: dict[str, Any] = {"available": False, "reason": "", "host": host, "port": port}
    try:
        with socket.create_connection((host, port), timeout=0.8):
            info["available"] = True
            info["reason"] = "NinjaTrader bridge answering"
    except OSError as exc:
        info["reason"] = (f"no bridge at {host}:{port} ({type(exc).__name__}) — start NinjaTrader "
                          f"(bridge compiled in the platform's own NinjaScript Editor — its Log tab shows it listening)")
    return info


_NT_INSTRUMENTS_CACHE: dict[str, Any] = {"at": 0.0, "rows": []}


def ninjatrader_symbol_names(max_age_s: float = 120.0) -> list[dict[str, Any]]:
    """The terminal's own instrument list, cached.

    A real terminal lists thousands of masters, so this is never fetched per keystroke (the same
    rule the MT5 broker list follows). Empty list when the bridge is down — the caller says so.
    """
    now = time.time()
    if _NT_INSTRUMENTS_CACHE.get("rows") and now - float(_NT_INSTRUMENTS_CACHE.get("at") or 0.0) < max_age_s:
        return list(_NT_INSTRUMENTS_CACHE["rows"])
    from orderflow_system.data.ninjatrader_feed import ninjatrader_instruments

    rows = ninjatrader_instruments(getattr(settings.NINJATRADER, "host", "127.0.0.1"),
                                   getattr(settings.NINJATRADER, "port", 8790))
    if rows:
        _NT_INSTRUMENTS_CACHE["at"] = now
        _NT_INSTRUMENTS_CACHE["rows"] = rows
    return rows


def ninjatrader_validate(symbols: list[str]) -> dict[str, Any]:
    """Ask the bridge which of these names its terminal carries (one round trip, cached list).

    A requested name matches by exact full name first (`NQ 12-26`), then by master root
    (`NQ` / `NQ1` → `NQ 12-26`); the tick size comes from the terminal's own database.
    """
    status = ninjatrader_status()
    if not status["available"]:
        return {"ok": False, "available": False, "reason": status["reason"], "symbols": {}}
    rows = ninjatrader_symbol_names()
    if not rows:
        return {"ok": False, "available": True,
                "reason": "the bridge answered but listed no instruments", "symbols": {}}
    out: dict[str, Any] = {}
    for raw in symbols:
        want = str(raw or "").strip().upper()
        if not want:
            continue
        base = want.removesuffix("!").removesuffix("1")
        hit = next((row for row in rows
                    if str(row.get("Name") or "").upper() == want
                    or str(row.get("Root") or "").upper() == base), None)
        out[str(raw)] = {"listed": hit is not None,
                         "tick_size": (hit or {}).get("TickSize") or None,
                         "ninjatrader": (hit or {}).get("Name") or ""}
    return {"ok": True, "available": True, "symbols": out}


def venue_stamp_for(spec: dict[str, Any], source: str) -> Optional[str]:
    """Which venue stamp lets the engine build a profile for a symbol the matrix does not know (§82).

    A stamp is evidence — the venue's own listing (or the user's broker mapping) confirmed the
    name — so a typo can never become an instrument. Returns the venue name, or None when the
    row carries nothing the ACTIVE source can use.
    """
    src = str(source or "").lower()
    if src in ("bybit", "both") and bybit_capable(spec):
        return "bybit"
    if src == "binance" and str(spec.get("binance_symbol") or "").strip():
        return "binance"
    if src == "hyperliquid" and str(spec.get("hyperliquid_symbol") or "").strip():
        return "hyperliquid"
    if src == "okx" and str(spec.get("okx_symbol") or "").strip():
        return "okx"
    if src in ("mt5", "both") and str(spec.get("mt5_symbol") or "").strip():
        return "mt5"
    if src == "ninjatrader" and str(spec.get("ninjatrader_symbol") or "").strip():
        return "ninjatrader"
    if src in ("alpaca", "all") and str(spec.get("alpaca_symbol") or "").strip():
        return "alpaca"
    return None


_BASE_CONFIGS: dict[str, InstrumentConfig] = {}


def base_configs() -> dict[str, InstrumentConfig]:
    global _BASE_CONFIGS
    if not _BASE_CONFIGS:
        _BASE_CONFIGS = {c.instrument.value: c for c in get_all_configs()}
    return _BASE_CONFIGS


# ──────────────────────────────────────────────────────────────
# Capability discovery (what can this machine + data source actually do?)
# ──────────────────────────────────────────────────────────────

#: MT5 is a process-global module: while the engine runs, its feed owns the terminal session and
#: a probe that calls ``mt5.shutdown()`` on that same module kills the feed's session (audit
#: A-05). Probes are serialised with this lock, and the shutdown helper leaves the session alone
#: while the feed is up.
_MT5_PROBE_LOCK = threading.Lock()


def _mt5_feed_owns_session() -> bool:
    """True while a running engine has an MT5 feed holding the terminal session.

    ``engine.system`` is a property (the codebase reads it as an attribute everywhere), and the
    ``is True`` test keeps a stub or mock attribute from reading as an owning feed.
    """
    feed = getattr(engine.system, "mt5_feed", None)
    return bool(feed is not None and getattr(feed, "_initialized", False) is True)


def _mt5_shutdown_unless_owned(mt5: Any) -> None:
    """Release a probe's own session — unless the live feed owns it (then the probe must not)."""
    if _mt5_feed_owns_session():
        return
    try:
        mt5.shutdown()
    except Exception:
        pass


def _mt5_serialised(fn):
    """Run one MT5 probe at a time — the module is process-global and concurrent probes raced."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _MT5_PROBE_LOCK:
            return fn(*args, **kwargs)
    return wrapper


def mt5_status() -> dict[str, Any]:
    """Is the MetaTrader5 bridge even installable/usable on this machine?"""
    info: dict[str, Any] = {"available": False, "reason": "", "terminal": None}
    if sys.platform != "win32":
        info["reason"] = (
            f"MetaTrader5 package ships Windows wheels only — not available on "
            f"{sys.platform}. Use the Bybit feed or run the MT5 terminal on Windows."
        )
        return info
    try:
        import MetaTrader5  # noqa: F401
    except ImportError:
        info["reason"] = "MetaTrader5 package not installed (pip install MetaTrader5)."
        return info
    info["available"] = True
    return info


@_mt5_serialised
def mt5_probe(payload: dict[str, Any]) -> dict[str, Any]:
    """Try to bring the MetaTrader 5 bridge up with the settings the user typed.

    Reports one honest stage at a time so the setup assistant can say exactly which
    piece is missing instead of "it did not work": platform → package → terminal →
    ready. The password is used and never echoed back into the response or the log.
    """
    out: dict[str, Any] = {
        "ok": False, "stage": "platform", "message": "", "command": "",
        "terminal": None, "account": None, "symbols": {}, "error_code": 0,
    }
    if sys.platform != "win32":
        out["message"] = (
            f"MetaTrader5 publishes Windows wheels only (this machine is {sys.platform}). "
            "Use the exchange feed here, or run the terminal on a Windows machine."
        )
        return out

    try:
        import importlib.util

        has_pip = importlib.util.find_spec("pip") is not None
    except Exception:
        has_pip = False

    try:
        import MetaTrader5 as mt5
    except ImportError:
        out["stage"] = "package"
        out["message"] = (
            "The MetaTrader5 Python package is not installed in this environment. "
            "Install it, then run this check again — the terminal itself is a separate install."
        )
        # Give the command that fits THIS environment: uv-made venvs ship without pip.
        out["command"] = (
            ".venv\\Scripts\\python.exe -m pip install MetaTrader5" if has_pip
            else "uv pip install --python .venv\\Scripts\\python.exe MetaTrader5"
        )
        return out

    path = str(payload.get("path") or "").strip()
    server = str(payload.get("server") or "").strip()
    password = str(payload.get("password") or "")
    try:
        login = int(payload.get("login") or 0)
    except (TypeError, ValueError):
        login = 0
    kwargs: dict[str, Any] = {}
    if path:
        kwargs["path"] = path
    if login:
        kwargs["login"] = login
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    try:
        ok = bool(mt5.initialize(**kwargs))
    except Exception as exc:                      # a bad path/lib raises rather than returning False
        out["stage"] = "terminal"
        out["message"] = f"initialize() raised: {exc}"
        return out

    if not ok:
        code, msg = 0, ""
        try:
            code, msg = mt5.last_error()
        except Exception:
            pass
        out["stage"] = "terminal"
        out["error_code"] = int(code or 0)
        out["message"] = (
            f"The terminal did not accept the connection (code {code}: {msg}). "
            "Usual causes: the terminal is not running, the executable path is wrong, or the "
            "login/server pair is not the account the terminal is already signed in to."
        )
        return out

    try:
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        if ti is not None:
            out["terminal"] = {
                "name": str(getattr(ti, "name", "") or ""),
                "company": str(getattr(ti, "company", "") or ""),
                "path": str(getattr(ti, "path", "") or ""),
                "connected": bool(getattr(ti, "connected", False)),
                "build": int(getattr(ti, "build", 0) or 0),
            }
        if ai is not None:
            out["account"] = {                     # deliberately no holder name: no PII in the response
                "login": int(getattr(ai, "login", 0) or 0),
                "server": str(getattr(ai, "server", "") or ""),
                "currency": str(getattr(ai, "currency", "") or ""),
                "leverage": int(getattr(ai, "leverage", 0) or 0),
            }
        for sym in list(payload.get("symbols") or [])[:25]:
            try:
                out["symbols"][str(sym)] = mt5.symbol_info(str(sym)) is not None
            except Exception:
                out["symbols"][str(sym)] = False
    finally:
        _mt5_shutdown_unless_owned(mt5)

    out["ok"] = True
    out["stage"] = "ready"
    out["message"] = "Terminal reachable — the MetaTrader 5 bridge is ready."
    return out


# ── §82: broker symbol discovery ─────────────────────────────────────────────────────
#
# The wizard maps broker names by hand, which asks the user to already know the name
# ("USTEC or US100 or NAS100?"). Discovery answers the other direction: list what THIS
# terminal's broker actually offers, so a typed market name can find its contract — and
# an NQ1!-style look-up ends with the real symbol instead of silence.

_MT5_SYMBOLS_CACHE: dict[str, Any] = {"key": None, "at": 0.0, "names": []}
MT5_SYMBOLS_TTL_S = 120.0


def _mt5_key(payload: dict[str, Any] | None) -> tuple:
    payload = payload or {}
    try:
        login = int(payload.get("login") or 0)
    except (TypeError, ValueError):
        login = 0
    return (str(payload.get("path") or "").strip(), str(payload.get("server") or "").strip(), login)


def _mt5_begin(payload: dict[str, Any] | None) -> tuple[Any, Optional[str]]:
    """Import + initialize the terminal with the given settings: (mt5, None) or (None, why)."""
    if sys.platform != "win32":
        return None, f"MetaTrader5 publishes Windows wheels only (this machine is {sys.platform})"
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None, "the MetaTrader5 package is not installed in this environment"
    payload = payload or {}
    kwargs: dict[str, Any] = {}
    for key in ("path", "server", "password"):
        value = str(payload.get(key) or "").strip()
        if value:
            kwargs[key] = value
    try:
        login = int(payload.get("login") or 0)
    except (TypeError, ValueError):
        login = 0
    if login:
        kwargs["login"] = login
    try:
        ok = bool(mt5.initialize(**kwargs))
    except Exception as exc:                      # a bad path/lib raises rather than returning False
        return None, f"initialize() raised: {exc}"
    if not ok:
        code, msg = 0, ""
        try:
            code, msg = mt5.last_error()
        except Exception:
            pass
        return None, f"the terminal did not accept the connection (code {code}: {msg})"
    return mt5, None


@_mt5_serialised
def mt5_symbol_names(payload: dict[str, Any] | None = None, *, refresh: bool = False) -> dict[str, Any]:
    """Every symbol the connected broker lists, cached for MT5_SYMBOLS_TTL_S.

    Honest when there is no terminal: ``ok: False`` + a reason, never an empty list that
    reads as "your broker has nothing".
    """
    cache = _MT5_SYMBOLS_CACHE
    key = _mt5_key(payload)
    fresh = cache.get("key") == key and (time.time() - float(cache.get("at") or 0.0)) < MT5_SYMBOLS_TTL_S
    if fresh and cache.get("names") and not refresh:
        return {"ok": True, "available": True, "cached": True,
                "names": list(cache["names"]), "total": len(cache["names"])}
    mt5, why = _mt5_begin(payload)
    if mt5 is None:
        return {"ok": False, "available": False, "cached": False, "names": [], "total": 0,
                "reason": why or "MT5 is not available"}
    try:
        listed = mt5.symbols_get()
    finally:
        _mt5_shutdown_unless_owned(mt5)
    names = sorted({str(getattr(s, "name", "") or "") for s in (listed or []) if getattr(s, "name", "")})
    cache.update({"key": key, "at": time.time(), "names": names})
    return {"ok": True, "available": True, "cached": False, "names": names, "total": len(names)}


@_mt5_serialised
def mt5_symbols(payload: dict[str, Any] | None = None, query: str = "",
                limit: int = 40, names: Optional[list[str]] = None) -> dict[str, Any]:
    """Broker symbol rows for the look-up: matches for ``query`` (or exactly ``names``), each
    with the venue's own tick size and description where the terminal can report them.

    Ranking is exact → prefix → substring over the broker's list, case-insensitively; the
    caller's ``names`` bypass ranking (used to validate a specific contract at add time).
    """
    found = mt5_symbol_names(payload)
    if not found.get("ok"):
        return {"ok": False, "available": False, "reason": found.get("reason") or "MT5 is not available",
                "total": 0, "symbols": []}
    listed: list[str] = list(found["names"])
    if names:
        wanted = [str(n).strip() for n in names if str(n).strip()]
        upper = {n.upper(): n for n in listed}
        picked = [upper.get(w.upper(), w) for w in wanted]
    else:
        q = str(query or "").strip().upper()
        if not q:
            picked = []
        else:
            exact = [n for n in listed if n.upper() == q]
            prefix = [n for n in listed if n.upper().startswith(q) and n not in exact]
            contains = [n for n in listed if q in n.upper() and n not in exact and n not in prefix]
            picked = exact + prefix + contains
    picked = picked[:max(1, int(limit))]
    if not picked:
        return {"ok": True, "available": True, "total": len(listed), "symbols": []}
    mt5, why = _mt5_begin(payload)
    rows: list[dict[str, Any]] = []
    if mt5 is None:
        # No terminal right now: the names are still real (they came from the cache), so the
        # rows carry names with unknown ticks rather than disappearing.
        return {"ok": True, "available": False, "reason": why, "total": len(listed),
                "symbols": [{"name": n, "tick_size": None, "digits": None, "description": ""} for n in picked]}
    try:
        for name in picked:
            info = None
            try:
                info = mt5.symbol_info(name)
            except Exception:
                info = None
            rows.append({
                "name": name,
                "listed": info is not None,
                "tick_size": float(getattr(info, "trade_tick_size", 0.0) or 0.0) if info is not None else None,
                "digits": int(getattr(info, "digits", 0) or 0) if info is not None else None,
                "description": str(getattr(info, "description", "") or "") if info is not None else "",
            })
    finally:
        _mt5_shutdown_unless_owned(mt5)
    return {"ok": True, "available": True, "total": len(listed), "symbols": rows}


@_mt5_serialised
def mt5_validate_symbols(names: list[str], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check specific broker names at add time: {name: {listed, tick_size, description}}.

    Separate from ``mt5_symbols`` on purpose: an add must not guess a tick size, so it reads
    ``symbol_info`` for exactly the names it is about to write into the config.
    """
    found = mt5_symbol_names(payload)
    if not found.get("ok"):
        return {"ok": False, "available": False, "reason": found.get("reason") or "MT5 is not available",
                "symbols": {}}
    mt5, why = _mt5_begin(payload)
    if mt5 is None:
        return {"ok": False, "available": False, "reason": why or "MT5 is not available", "symbols": {}}
    out: dict[str, dict[str, Any]] = {}
    try:
        for name in list(names)[:25]:
            key = str(name).strip()
            if not key:
                continue
            try:
                info = mt5.symbol_info(key)
            except Exception:
                info = None
            out[key] = {
                "listed": info is not None,
                "tick_size": float(getattr(info, "trade_tick_size", 0.0) or 0.0) if info is not None else None,
                "digits": int(getattr(info, "digits", 0) or 0) if info is not None else None,
                "description": str(getattr(info, "description", "") or "") if info is not None else "",
            }
    finally:
        _mt5_shutdown_unless_owned(mt5)
    return {"ok": True, "available": True, "symbols": out}


def bybit_validate(symbols: list[str]) -> dict[str, bool]:
    """Ask Bybit which of these symbols exist as linear perpetuals."""
    import json
    import urllib.parse
    import urllib.request

    result: dict[str, bool] = {}
    for sym in symbols:
        url = (
            "https://api.bybit.com/v5/market/instruments-info"
            f"?category=linear&symbol={urllib.parse.quote(str(sym), safe='')}"
        )
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                payload = json.loads(resp.read().decode())
            listed = bool(payload.get("result", {}).get("list"))
            result[sym] = listed
        except Exception as exc:  # network hiccup → don't lie, mark unknown as False
            logger.warning("Bybit symbol check failed for %s: %s", sym, exc)
            result[sym] = False
    return result


def binance_validate(symbols: list[str]) -> dict[str, bool]:
    """Ask Binance which of these symbols exist as USDⓈ-M perpetuals (one exchangeInfo call).

    Delegates to the feed module so the check has exactly one implementation, and the capability
    block cannot drift from what the adapter will actually accept.
    """
    from orderflow_system.data.binance_feed import BinanceFeed

    return BinanceFeed.validate_symbols(list(symbols))


def hyperliquid_validate(symbols: list[str]) -> dict[str, bool]:
    """Ask the Hyperliquid meta listing which of these symbols actually trade here (one call).

    Delegates to the feed module so the check has exactly one implementation, and the capability
    block cannot drift from what the adapter will actually accept.
    """
    from orderflow_system.data.hyperliquid_feed import HyperliquidFeed

    return HyperliquidFeed.validate_symbols(list(symbols))


def okx_validate(symbols: list[str]) -> dict[str, bool]:
    """Ask OKX which of these symbols exist as live USDT swaps (one instruments call).

    Delegates to the feed module so the check has exactly one implementation, and the capability
    block cannot drift from what the adapter will actually accept.
    """
    from orderflow_system.data.okx_feed import OkxFeed

    return OkxFeed.validate_symbols(list(symbols))


def alpaca_capability_block(cfg: dict[str, Any], report: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """What the UI needs to know about the Alpaca source, entitlement-aware.

    ``report`` is the stored capability probe (desktop/alpaca.py ``probe``); without
    one the block describes the free tier honestly instead of pretending to know.
    """
    from orderflow_system.config.settings import ALPACA as ALPACA_SETTINGS

    alp = dict(cfg.get("alpaca") or {})
    caps = dict((report or {}).get("capabilities") or {})
    entitled_sip = bool(caps.get("equities_sip_delayed"))
    feeds = ["iex"] + (["delayed_sip", "sip"] if entitled_sip else [])
    symbols = {i["symbol"]: (i.get("alpaca_symbol") or ALPACA_SETTINGS.symbols.get(i["symbol"], ""))
               for i in (cfg.get("instruments") or []) if i.get("enabled")}
    symbols = {k: v for k, v in symbols.items() if v}
    limits = dict((report or {}).get("limits") or {})
    return {
        "linked": bool(alp.get("key_id") and alp.get("secret")),
        "enabled": bool(alp.get("enabled")),
        "paper": bool(alp.get("paper", True)),
        "selected_feed": alp.get("feed", "iex"),
        "feeds": feeds,
        "options_feed": "indicative",
        "delayed": True,
        "symbol_limit": int(limits.get("websocket_symbols", 30)),
        "quote_limit": 200,
        "rest_per_min": int(limits.get("rest_per_min", 200)),
        "rest_budget": 150,
        "symbols": symbols,
        # Depth is the one thing Alpaca cannot do; say it once, here, and let every
        # view read it from this single map instead of guessing from empty panels.
        "depth": False,
        "depth_reason": ("Alpaca publishes trades, quotes and bars — no order book. "
                         "The heatmap, the DOM ladder and the participants'-intent reader "
                         "need the exchange feed (or MT5) for this symbol."),
        "notes": list((report or {}).get("entitlement_notes") or []),
    }


def capabilities(symbols: Optional[list[str]] = None) -> dict[str, Any]:
    cfg = config_store.load_config()
    symbols = list(symbols) if symbols is not None else [i["symbol"] for i in cfg["instruments"]]
    report = None
    try:                                   # cached probe from the Alpaca endpoints
        from orderflow_system.desktop import api as desktop_api
        report = desktop_api._ALPACA_CACHE.get("report")
    except Exception:                      # pragma: no cover — never break capabilities
        report = None
    return {
        "platform": sys.platform,
        "mt5": mt5_status(),
        "ninjatrader": ninjatrader_status(),
        "bybit_symbols": {s: (s in BYBIT_SUPPORTED) for s in symbols},
        "alpaca": alpaca_capability_block(cfg, report),
        "config_dir": str(config_store.config_dir()),
    }


# ──────────────────────────────────────────────────────────────
# Config → repo dataclasses
# ──────────────────────────────────────────────────────────────


def _database_state() -> dict[str, str]:
    """The engine store's own health: writable, locked (a second instance), or not yet created.

    A write-lock probe, not a read: reads pass through even while another writer holds the
    database (that is exactly how the engine ended up "running" with *database is locked* on
    screen). Two short attempts keep a busy-but-healthy store from tripping the row.
    """
    import sqlite3

    path = config_store.config_dir() / "orderflow_data.db"
    if not path.is_file():
        return {"state": "ready", "detail": "created on the first engine start"}
    last = ""
    for attempt in range(2):
        try:
            con = sqlite3.connect(str(path), timeout=0.4)
            try:
                con.execute("BEGIN IMMEDIATE")
                con.rollback()
            finally:
                con.close()
            size_mb = path.stat().st_size / (1024 * 1024)
            return {"state": "live", "detail": f"writable · {size_mb:.1f} MB"}
        except sqlite3.OperationalError as exc:
            last = str(exc)
            if attempt == 0:
                time.sleep(0.15)
        except Exception as exc:                       # pragma: no cover — never break the board
            last = f"{type(exc).__name__}: {exc}"
            break
    return {"state": "error",
            "detail": f"locked ({last}) — close any second app instance using the same config folder"}


_SYSTEMS_SOURCES = {
    "bybit": "Bybit (exchange, public WebSocket)",
    "binance": "Binance USDⓈ-M (exchange, public WebSocket)",
    "hyperliquid": "Hyperliquid (exchange, public WebSocket)",
    "okx": "OKX swaps (exchange, public WebSocket)",
}


def systems_report() -> dict[str, Any]:
    """The Systems board (§86): every ingest path this install can use, its honest state, and —
    kept apart — the capabilities that are not set up yet.

    A row is a fact the program already knows or can check in a moment: no promises, and the
    states are a closed set the UI paints only — live | ready | off | error.
    """
    cfg = config_store.load_config()
    st = engine.status()
    src = str(cfg.get("data_source") or "bybit").lower()
    running = bool(st.get("running"))
    error = str(st.get("error") or "")
    per_symbol = [r for r in (st.get("per_symbol") or []) if isinstance(r, dict)]
    tick_sum = sum(int(r.get("ticks") or 0) for r in per_symbol)

    rows: list[dict[str, Any]] = []

    def add(row_id, name, state, detail, view="", kind="ingest"):
        rows.append({"id": row_id, "name": name, "state": state, "detail": detail,
                     "view": view, "kind": kind})

    add("engine", "Engine",
        "live" if running else ("error" if error else "off"),
        (f"streaming {len(st.get('symbols') or [])} instruments · {tick_sum:,} ticks · "
         f"up {int(st.get('uptime_s') or 0)}s") if running else (error or "stopped — press Start engine"),
        "ofx", "core")

    source_label = _SYSTEMS_SOURCES.get(src, {"mt5": "MetaTrader 5 (broker terminal)",
                                              "ninjatrader": "NinjaTrader 8 (bridge)",
                                              "alpaca": "Alpaca Markets",
                                              "both": "Exchange + MT5", "all": "All configured sources"}.get(src, src))
    add("source", f"Feed — {source_label}",
        "live" if running else ("error" if error else "ready"),
        (f"feeding the engine now · {len(st.get('symbols') or [])} instruments") if running
        else "selected — start the engine to connect",
        "settings", "ingest")

    mt5 = mt5_status()
    if src in ("mt5", "both", "all"):
        mt5_state = "live" if running else ("ready" if mt5.get("available") else "off")
    else:
        mt5_state = "ready" if mt5.get("available") else "off"
    add("mt5", "MetaTrader 5", mt5_state,
        mt5.get("reason") or (("feeding the engine now" if running else
                              "bridge importable — choose MT5 as the source")
                              if src in ("mt5", "both", "all")
                              else "bridge importable — choose MT5 as the source"),
        "settings", "ingest")

    nt = ninjatrader_status()
    nt_state = "live" if (running and src == "ninjatrader") else ("ready" if nt.get("available") else "off")
    add("ninjatrader", "NinjaTrader 8 (bridge)", nt_state,
        ("feeding the engine now" if (running and src == "ninjatrader")
         else (f"bridge answering at {nt.get('host')}:{nt.get('port')} — choose NinjaTrader as the source"
               if nt.get("available") else str(nt.get("reason") or ""))),
        "instruments", "ingest")

    alp = alpaca_capability_block(cfg)
    alp_state = "live" if (running and src == "alpaca") else ("ready" if alp.get("linked") else "off")
    add("alpaca", "Alpaca Markets", alp_state,
        ("feeding the engine now" if (running and src == "alpaca")
         else ("keys saved" + (" · paper" if alp.get("paper") else " · live") if alp.get("linked")
               else "no API keys yet — Data ▸ Alpaca")),
        "alpaca", "ingest")

    db = _database_state()
    add("database", "History database", db["state"], db["detail"], "logs", "core")

    ws = int(st.get("ws_clients") or 0)
    add("ws", "UI stream (WebSocket)", "live" if ws > 0 else "off",
        f"{ws} client(s) attached" if ws else "no client attached to this backend",
        "", "link")

    tg = dict(cfg.get("telegram") or {})
    tg_ready = bool(tg.get("bot_token") and tg.get("chat_id"))
    tg_on = bool(tg_ready and tg.get("enabled"))
    ntf = dict((cfg.get("notify") or {}).get("ntfy") or {})
    ntf_topic = str(ntf.get("topic") or "").strip()
    ntf_on = bool(ntf.get("enabled")) and bool(ntf_topic)
    ntf_server = str(ntf.get("server") or "https://ntfy.sh").strip().rstrip("/")
    channels = [name for name, on in (("Telegram", tg_on), ("ntfy", ntf_on)) if on]
    if channels:
        detail = "sending to " + " + ".join(channels)
        if ntf_on and ntf_server == "https://ntfy.sh":
            # No account, no key — and no secrecy either: anyone who knows the topic can subscribe.
            detail += (f" · the ntfy.sh topic “{ntf_topic}” is PUBLIC — anyone who knows it can "
                       f"read your alerts")
        add("alerts", "Alerts — " + " + ".join(channels), "live", detail, "settings", "module")
    else:
        add("alerts", "Alerts — Telegram",
            "ready" if tg_ready else "off",
            "configured — switch on in Settings" if tg_ready else "not configured — Settings ▸ Telegram",
            "settings", "module")

    # R6: storage is a system too — these are the numbers the user manages it by, on the board
    # where the rest of the machine already reports in.
    try:
        from orderflow_system.desktop import storage as storage_mod

        st_settings = storage_mod.clamp_storage_settings(cfg)
        st_dir = config_store.config_dir()
        st_target = storage_mod.resolved_target(st_settings, st_dir)
        st_usage = storage_mod.usage_snapshot(config_store.db_path(), config_dir=st_dir,
                                              target=st_target)
        st_backups = storage_mod.list_backups(st_target)
        rt_days = int((cfg.get("data") or {}).get("retention_days", 0) or 0)
        newest = (st_backups[0].get("created_at") or st_backups[0].get("name")) if st_backups else "none yet"
        budget = int(st_settings.get("max_db_mb") or 0)
        over = bool(budget) and (st_usage["db_bytes"] + st_usage["wal_bytes"]) > budget * 1_000_000
        add("storage", "Storage — backups & usage",
            "live" if st_settings["auto_backup"] and not over else ("ready" if not over else "off"),
            f"{st_usage['total_bytes'] / 1e6:,.0f} MB on disk "
            f"(db {(st_usage['db_bytes'] + st_usage['wal_bytes']) / 1e6:,.1f} MB) · retention {rt_days} d "
            f"· {len(st_backups)} backup(s), newest {newest}"
            + (f" · OVER the {budget} MB budget" if over else ""),
            "settings", "module")
    except Exception as exc:                          # noqa: BLE001 - a board row is not worth a failure
        add("storage", "Storage — backups & usage", "off", f"unreadable: {exc}", "settings", "module")

    optional: list[dict[str, Any]] = []
    try:
        from orderflow_system.desktop import platforms as platform_mod

        installs = platform_mod.detect_installs()
        plat_cfg = dict(cfg.get("platforms") or {})
        for pid, label in (("bookmap", "Bookmap bridge"), ("sierra", "Sierra Chart (DTC)")):
            found = bool((installs.get(pid) or {}).get("found"))
            configured = bool((plat_cfg.get(pid) or {}).get("enabled"))
            optional.append({
                "id": pid, "name": label, "kind": "addon", "view": "instruments",
                "state": "ready" if (found and configured) else "off",
                "detail": (f"installed · {'configured' if configured else 'add the bridge in Platforms'}"
                           if found else "not installed on this machine — a capability this program can use"),
                "optional": True,
            })
    except Exception as exc:                            # pragma: no cover — never break the board
        optional.append({"id": "platforms", "name": "Platform bridges", "state": "off",
                         "detail": f"detection failed: {exc}", "view": "", "kind": "addon", "optional": True})

    live = sum(1 for r in rows if r["state"] == "live")
    total = len(rows)
    return {"ok": True, "rows": rows, "optional": optional, "live": live, "total": total,
            "percent": int(round(100 * live / total)) if total else 0,
            "source": src, "uphill": [r["id"] for r in rows if r["state"] in ("off", "error")]}

def _apply_overrides(ic: InstrumentConfig, spec: dict[str, Any]) -> None:
    """Copy the GUI's per-pattern thresholds onto a repo InstrumentConfig."""
    p = spec.get("patterns") or {}
    try:
        ic.tick_size = float(spec.get("tick_size", ic.tick_size))
        a = p.get("absorption") or {}
        ic.absorption.min_aggressive_volume = float(a.get("min_aggressive_volume", ic.absorption.min_aggressive_volume))
        ic.absorption.max_price_displacement_ticks = float(a.get("max_price_displacement_ticks", ic.absorption.max_price_displacement_ticks))
        ic.absorption.min_attempts = int(a.get("min_attempts", ic.absorption.min_attempts))
        i = p.get("initiative") or {}
        ic.initiative.min_delta_threshold = float(i.get("min_delta_threshold", ic.initiative.min_delta_threshold))
        ic.initiative.volume_acceleration_min = float(i.get("volume_acceleration_min", ic.initiative.volume_acceleration_min))
        ic.initiative.min_price_displacement_ticks = float(i.get("min_price_displacement_ticks", ic.initiative.min_price_displacement_ticks))
        s = p.get("sweep") or {}
        ic.sweep.min_levels_swept = int(s.get("min_levels_swept", ic.sweep.min_levels_swept))
        ic.sweep.thin_book_threshold = float(s.get("thin_book_threshold", ic.sweep.thin_book_threshold))
        e = p.get("exhaustion") or {}
        ic.exhaustion.min_bars_declining = int(e.get("min_bars_declining", ic.exhaustion.min_bars_declining))
        ic.exhaustion.volume_decline_pct = float(e.get("volume_decline_pct", ic.exhaustion.volume_decline_pct))
        d = p.get("divergence") or {}
        ic.divergence.lookback_bars = int(d.get("lookback_bars", ic.divergence.lookback_bars))
        ic.divergence.delta_failure_pct = float(d.get("delta_failure_pct", ic.divergence.delta_failure_pct))
    except (TypeError, ValueError, AttributeError) as exc:
        logger.warning("Bad threshold override for %s — using defaults (%s)", spec.get("symbol"), exc)


#: The single-venue exchange sources with their offline gates. Before this table the engine had
#: NO gate for them — select_instruments filtered Bybit, Alpaca, MT5 and NinjaTrader, then handed
#: Binance/OKX/Hyperliquid whatever was enabled, where a non-crypto symbol became a subscription
#: to a contract the venue does not list.
_EXCHANGE_GATES: dict[str, tuple[Any, str]] = {
    "binance": (binance_capable, "Binance USDⓈ-M futures"),
    "okx": (okx_capable, "OKX USDT swaps"),
    "hyperliquid": (hyperliquid_capable, "Hyperliquid perpetuals"),
}


def select_instruments(cfg: dict[str, Any]) -> tuple[list[InstrumentConfig], list[dict[str, str]]]:
    """Return (instrument configs, skipped) for the chosen data source."""
    source = cfg.get("data_source", "bybit")
    out: list[InstrumentConfig] = []
    skipped: list[dict[str, str]] = []
    for spec in cfg.get("instruments", []):
        if not spec.get("enabled"):
            continue
        symbol = spec["symbol"]
        # Deep copy: _apply_overrides writes onto the object, and base_configs() is a
        # process-wide cache — without the copy, thresholds from one start leaked into
        # every later one (a reset in the GUI only took effect after a restart).
        base = copy.deepcopy(base_configs().get(symbol))
        if base is None:
            # Not in the shipped matrix: the wizard — and, since §82, the Engine panel's own
            # instrument look-up — can add any instrument a venue confirmed. The row carries
            # that venue's stamp (bybit_symbol, mt5_symbol, alpaca_symbol, …); without one a
            # typo must still die here. The profile comes from the venue's tick.
            if venue_stamp_for(spec, source):
                base = settings.config_for_symbol(symbol, spec.get("tick_size"))
            else:
                skipped.append({"symbol": symbol, "reason": "unknown instrument"})
                continue

        if source in ("bybit", "both") and not bybit_capable(spec):
            if source == "bybit":
                skipped.append({
                    "symbol": symbol,
                    "reason": "Bybit perps list crypto only — switch to MT5 (Windows) for this instrument",
                })
                continue

        exchange = _EXCHANGE_GATES.get(source)
        if exchange is not None and not exchange[0](spec):
            skipped.append({
                "symbol": symbol,
                "reason": f"{exchange[1]} carry crypto instruments only — switch to MT5 "
                          f"(Windows) for this instrument",
            })
            continue

        if source == "alpaca" and symbol not in settings.ALPACA.symbols:
            # Only the Alpaca-only source refuses here: under `all` an unmapped symbol simply does
            # not join the Alpaca leg — it still streams from the venue that carries it.
            skipped.append({
                "symbol": symbol,
                "reason": ("Alpaca serves US equities/ETFs/options and crypto pairs — "
                           "give this instrument an Alpaca symbol in the Alpaca view"),
            })
            continue

        if source in ("mt5", "both") and sys.platform != "win32" and source == "mt5":
            skipped.append({
                "symbol": symbol,
                "reason": "MT5 feed requires Windows (MetaTrader5 wheels are win_amd64 only)",
            })
            continue

        if source == "ninjatrader" and not ninjatrader_capable(spec):
            skipped.append({
                "symbol": symbol,
                "reason": ("add this instrument from your NinjaTrader terminal (Instruments panel → "
                           "NinjaTrader) — the bridge lists exactly what your data feed carries"),
            })
            continue

        _apply_overrides(base, spec)
        out.append(base)
    return out, skipped


def partition_instruments(cfg: dict[str, Any], symbols: list[str], *,
                          legs: tuple[str, ...] = ("bybit", "alpaca", "mt5", "ninjatrader"),
                          ) -> dict[str, list[str]]:
    """One instrument, one venue: which leg of `both`/`all` carries which enabled symbol.

    `both` and `all` used to hand EVERY enabled symbol to EVERY leg they started: a symbol with
    an exchange listing and a broker mapping streamed from two venues into one pipeline (doubled
    ticks, volume and delta), and a crypto symbol with no broker mapping went to the exchange
    anyway. The rule is the one a trader would state, and it is aware of the legs this run
    actually starts (`legs` — `both` is bybit+mt5, `all` is all four):

    * an explicit venue stamp wins, NinjaTrader then Alpaca then MT5 — but only for a venue this
      run starts, and NEVER for a crypto row: Alpaca's crypto lane carries quotes and bars but no
      trades and no book, so order flow for a crypto instrument belongs to the exchange. A stock
      mapped to both Alpaca and a broker stays with Alpaca, its own venue;
    * a crypto row the exchange can carry belongs to the exchange (a broker mapping only takes it
      if the row says so explicitly);
    * anything else belongs to MT5 — the only other venue for indices, metals and FX — and the
      broker's own symbol resolution reports what it cannot serve.

    Measured live: an earlier stamp-first version sent BTCUSDT/ETHUSDT/SOLUSDT (all carrying the
    wizard's Alpaca crypto mappings) to the Alpaca leg of a `both` run — a leg `both` does not
    start — so the board streamed nothing at all. Pure; pinned by test_source_switch.
    """
    want = set(legs)
    wanted = {str(s).upper() for s in symbols}
    out: dict[str, list[str]] = {"bybit": [], "mt5": [], "alpaca": [], "ninjatrader": []}
    for spec in (cfg.get("instruments") or []):
        symbol = str(spec.get("symbol") or "")
        if not spec.get("enabled") or symbol.upper() not in wanted:
            continue
        crypto = _crypto_class(spec)
        venue = ""
        for stamp, name in (("ninjatrader_symbol", "ninjatrader"),
                            ("alpaca_symbol", "alpaca"),
                            ("mt5_symbol", "mt5")):
            if not spec.get(stamp) or name not in want:
                continue
            if name == "alpaca" and crypto:
                continue
            venue = name
            break
        if not venue and crypto and "bybit" in want:
            venue = "bybit"
        if not venue and not crypto and "mt5" in want:
            venue = "mt5"
        if not venue and "alpaca" in want and spec.get("alpaca_symbol"):
            venue = "alpaca"
        if not venue and "bybit" in want and crypto:
            venue = "bybit"
        if not venue and "mt5" in want:
            venue = "mt5"
        if venue:
            out[venue].append(symbol)
    return out


def clamp_data_settings(cfg: dict[str, Any]) -> tuple[int, int, int]:
    """R4/R5: (session_start_hour, retention_days, prune_interval_hours) from the config's
    `data` block, each clamped — junk falls back to the documented defaults, so a hand-edited
    config.json can never break the session maths or the retention job. Pure."""
    data_cfg = cfg.get("data") or {}

    def _clamped(key: str, lo: int, hi: int, default: int) -> int:
        try:
            return max(lo, min(hi, int(data_cfg.get(key, default))))
        except (TypeError, ValueError):
            return default

    return (_clamped("session_start_hour", 0, 23, 0),
            _clamped("retention_days", 0, 3650, 7),
            _clamped("prune_interval_hours", 1, 168, 6))


def apply_settings(cfg: dict[str, Any]) -> None:
    """Push the JSON config into the repo's settings module (runtime, no edits)."""
    settings.DATA_SOURCE = DataSource(cfg.get("data_source", "bybit"))
    settings.DB_PATH = str(config_store.db_path())
    # R4/R5: the `data` block, clamped by the one pure helper (tested directly, so the tests
    # never have to call apply_settings and disturb global state).
    settings.SESSION_START_HOUR, settings.RETENTION_DAYS, settings.PRUNE_INTERVAL_HOURS = clamp_data_settings(cfg)
    settings.LOG_LEVEL = str(cfg.get("logging", {}).get("level", "INFO")).upper()

    fp = ((cfg.get("atlas") or {}).get("footprint") or {})
    try:
        settings.FOOTPRINT_MIN_PRINT_SIZE = max(0.0, float(fp.get("min_print_size", 0.0) or 0.0))
    except (TypeError, ValueError):
        settings.FOOTPRINT_MIN_PRINT_SIZE = 0.0

    tg = cfg.get("telegram", {})
    settings.TELEGRAM.bot_token = tg.get("bot_token", "")
    settings.TELEGRAM.chat_id = tg.get("chat_id", "")

    # The desktop launcher owns the web server — stop main.py from spawning a 2nd one.
    settings.DASHBOARD.enabled = False
    settings.DASHBOARD.host = "127.0.0.1"
    settings.DASHBOARD.port = int(cfg.get("dashboard", {}).get("port", 8080))

    alp = cfg.get("alpaca", {}) or {}
    settings.ALPACA.feed = str(alp.get("feed", settings.ALPACA.feed) or "iex")
    settings.ALPACA.paper = bool(alp.get("paper", True))
    settings.ALPACA.key_id = str(alp.get("key_id", "") or "")
    settings.ALPACA.secret = str(alp.get("secret", "") or "")
    try:
        settings.ALPACA.snapshot_seconds = float(alp.get("snapshot_seconds", settings.ALPACA.snapshot_seconds))
    except (TypeError, ValueError):
        pass

    # The options/lookup REST feeds: the config is the only place these keys live, and the feeds
    # are built from `settings` (main.py) or straight from these attributes (atlas/options_api).
    # Every cast is defensive — a hand-edited file must not be able to put a non-string into a
    # request header, and a chain width outside the routes' own range must not survive.
    trad = cfg.get("tradier", {}) or {}
    settings.TRADIER.key_id = str(trad.get("key_id", "") or "").strip()
    settings.TRADIER.secret = str(trad.get("secret", "") or "").strip()
    settings.TRADIER.sandbox = bool(trad.get("sandbox", False))
    try:
        settings.TRADIER.chain_width = min(max(int(trad.get("chain_width", 6)), 1), 20)
    except (TypeError, ValueError):
        settings.TRADIER.chain_width = 6

    md = cfg.get("marketdata", {}) or {}
    settings.MARKETDATA.api_key = str(md.get("api_key", "") or "").strip()

    fnh = cfg.get("finnhub", {}) or {}
    settings.FINNHUB.api_key = str(fnh.get("api_key", "") or "").strip()
    settings.FINNHUB.calendar_category = str(
        fnh.get("calendar_category", settings.FINNHUB.calendar_category) or "all")
    settings.FINNHUB.news_category = str(
        fnh.get("news_category", settings.FINNHUB.news_category) or "general")
    try:
        settings.FINNHUB.calendar_days = min(max(int(fnh.get("calendar_days", 7)), 1), 30)
    except (TypeError, ValueError):
        settings.FINNHUB.calendar_days = 7

    mt5 = cfg.get("mt5", {})
    settings.MT5.login = int(mt5.get("login", 0) or 0)
    settings.MT5.password = mt5.get("password", "") or ""
    settings.MT5.server = mt5.get("server", "") or ""
    settings.MT5.path = mt5.get("path", "") or ""
    settings.MT5.poll_interval_ms = int(mt5.get("poll_interval_ms", 100) or 100)
    settings.MT5.enable_book = bool(mt5.get("enable_book", True))
    settings.MT5.download_history_days = int(mt5.get("download_history_days", 3) or 0)

    enabled = set(config_store.enabled_symbols(cfg))
    # app symbol → Alpaca symbol, for the enabled instruments only (an unmapped
    # symbol is skipped at selection time with a reason, never silently dropped).
    settings.ALPACA.symbols = {
        i["symbol"]: (i.get("alpaca_symbol") or settings.ALPACA.symbols.get(i["symbol"], ""))
        for i in cfg.get("instruments", [])
        if i["symbol"] in enabled
    }
    settings.MT5.symbols = {
        i["symbol"]: (i.get("mt5_symbol") or i["symbol"])
        for i in cfg.get("instruments", [])
        if i["symbol"] in enabled
    }
    nt_block = (cfg.get("platforms") or {}).get("ninjatrader") or {}
    settings.NINJATRADER.host = str(nt_block.get("host") or "127.0.0.1")
    try:
        settings.NINJATRADER.port = max(1, min(65535, int(nt_block.get("port") or 8790)))
    except (TypeError, ValueError):
        settings.NINJATRADER.port = 8790
    settings.NINJATRADER.symbols = {
        i["symbol"]: (i.get("ninjatrader_symbol") or i["symbol"])
        for i in cfg.get("instruments", [])
        if i["symbol"] in enabled
    }


# ──────────────────────────────────────────────────────────────
# Controller
# ──────────────────────────────────────────────────────────────

def _verify_candle_wiring(system) -> None:
    """Verify the repo's own candle-close wiring is in place (no compensation).

    Historical note: this module used to wrap ``pipeline.candle_builder.on_candle_close``
    to compensate for ``OrderflowSystem._on_candle_close_handler`` never being called.
    That handler is now wired **inside** the orchestrator (``main.py``): every pipeline
    hands its closed candle to ``OrderflowSystem._on_candle_closed`` after the analytics
    pass, which persists it and broadcasts ``candle`` / ``delta``. Keeping the old wrapper
    as well would persist and broadcast every candle twice.

    So all that is left here is an assertion. Presence alone is not enough — ``_on_candle_close``
    (the analytics pass) and ``_on_candle_closed`` (the persistence pass) differ by one letter,
    and a future edit that wires the wrong one would run analytics twice or persist twice.
    So check *identity*: the analytics callback must sit on the pipeline's own candle builder,
    and the persistence wire must point at the orchestrator's own ``_on_candle_closed``.
    """
    missing: list[str] = []
    wrong: list[str] = []
    for sym, pipeline in system.pipelines.items():
        if pipeline._on_candle_close != getattr(pipeline.candle_builder, "on_candle_close", None):
            wrong.append(sym)
        wire = getattr(pipeline, "_on_candle_closed_callback", None)
        if wire is None:
            missing.append(sym)
        elif wire != system._on_candle_closed:
            wrong.append(sym)
    if missing:
        logger.error(
            "Candle persistence NOT wired for %d pipeline(s): %s — /api/candles and the "
            "hourly volume-profile rebuild will have no data for them.",
            len(missing), ", ".join(missing),
        )
    if wrong:
        logger.error(
            "Candle wiring MIS-ROUTED for %d pipeline(s): %s — the analytics pass or the "
            "persistence wire points at the wrong method; a closed candle could be persisted "
            "twice or have its analytics run twice.",
            len(wrong), ", ".join(wrong),
        )
    if not missing and not wrong:
        logger.info("Candle persistence + WS broadcast wired in-orchestrator for %d pipeline(s)",
                    len(system.pipelines))


# ──────────────────────────────────────────────────────────────
# reference-style feature set (atlas package)
# ──────────────────────────────────────────────────────────────

async def _wire_atlas(system, cfg: dict) -> Any:
    """Attach the reference layout feature hub to a running OrderflowSystem.

    Wraps the system's own feed callbacks (so the hub sees the same ticks and
    order books the strategy does) and starts the extra Bybit streams the
    heatmap/liquidation trackers need. The hub is reachable afterwards as
    ``system._atlas_hub`` — the REST layer resolves it from there.
    """
    from orderflow_system.atlas.hub import FeatureHub
    from orderflow_system.dashboard.app import ws_manager   # the shared WS manager

    atlas_cfg = dict(cfg.get("atlas") or {})
    if not atlas_cfg.get("alert_rules"):
        atlas_cfg["alert_rules"] = []          # empty → AlertEngine uses its default set

    hub = FeatureHub(atlas_cfg)
    hub.configure(atlas_cfg)

    from orderflow_system.atlas.services import attach_services
    attach_services(hub, atlas_cfg, cfg.get("telegram") or {}, notify_cfg=cfg.get("notify") or {})
    if getattr(hub, "notifier", None) is not None:
        try:
            await hub.notifier.start()
        except Exception:
            logger.debug("atlas Telegram notifier failed to start", exc_info=True)
    if getattr(hub, "history", None) is not None:
        try:
            await hub.history.start()
        except Exception:
            logger.debug("atlas history writer failed to start", exc_info=True)

    async def sink(channel: str, symbol: str, data: Any) -> None:
        await ws_manager.broadcast(channel, data, symbol=symbol)

    hub.set_sink(sink)

    # keep every enabled instrument registered with its real tick size. `register` (not
    # `ensure`): a streamed symbol is protected from the REST-side eviction (MEM-A1-08).
    for pipeline in system.pipelines.values():
        hub.register(pipeline.symbol, pipeline.config.tick_size)

    original_tick = system._on_tick
    original_book = system._on_orderbook

    async def tick_with_atlas(symbol: str, tick) -> None:
        await original_tick(symbol, tick)
        hub.on_tick(symbol, tick)

    async def book_with_atlas(symbol: str, snapshot) -> None:
        await original_book(symbol, snapshot)
        hub.on_orderbook(symbol, snapshot)

    system._on_tick = tick_with_atlas
    system._on_orderbook = book_with_atlas
    system._atlas_hub = hub
    # G1/U3: every new radar level is offered to the signals machine's WATCHING pathway
    # (behind `atlas.radar.feed_signals`); one hook, every registration site.
    hub.level_hook = getattr(system, "_on_radar_level", None)
    logger.info("the reference layout feature hub attached (%d instruments)", len(system.pipelines))
    return hub


async def _start_atlas_extras(system) -> None:
    """Start the extra Bybit streams for the instruments Bybit can actually serve.

    Only when Bybit is the *primary* source: the extras book is a Bybit book, and folding it into a
    heatmap fed by another venue's trades would show one venue's depth under another's prints. The
    Binance, Hyperliquid and OKX sources each carry their own depth (Binance deeper than Bybit's
    200 levels), so nothing is lost when this is skipped.
    """
    hub = getattr(system, "_atlas_hub", None)
    if hub is None:
        return
    data_source = getattr(system, "data_source", None)
    source = str(getattr(data_source, "value", data_source) or "")
    if source not in ("bybit", "both", "all"):
        logger.info("the reference layout extras: skipped — only the Bybit exchange leg may fold "
                    "its own depth in (source=%s)", source or "?")
        return
    # Which symbols the EXCHANGE leg actually carries: under `both`/`all` the run's partition
    # answers (a symbol mapped to the broker must not get Bybit depth folded under the broker's
    # prints); under the bybit source it is every pipeline symbol the venue lists.
    leg = None
    parts = getattr(system, "_feed_symbols", None)
    # The partition is only consulted when the run actually partitions (the same rule main.py
    # applies to its legs): under a single-venue source nothing is partitioned, and a broker
    # stamp on a crypto row would otherwise strand that symbol's extras forever — BTCUSDT
    # (mt5_symbol set by the wizard) lost its deep book, liquidations and block trades this way
    # while four lesser symbols kept theirs.
    if source in ("both", "all") and isinstance(parts, dict) and parts.get("bybit"):
        leg = {str(s) for s in parts["bybit"]}
    symbols: dict[str, float] = {}
    for pipeline in system.pipelines.values():
        if pipeline.symbol in BYBIT_SUPPORTED and (leg is None or pipeline.symbol in leg):
            symbols[pipeline.symbol] = pipeline.config.tick_size
    if not symbols:
        logger.info("the reference layout extras: no Bybit-servable instrument enabled")
        return
    try:
        result = await hub.start_feeds(symbols)
        logger.info("the reference layout extras feed: %s", result)
    except Exception:
        logger.exception("the reference layout extras feed failed to start")


def tick_gaps(timestamps_ms: list[int], *, floor_ms: int = 5000,
              factor: float = 10.0) -> dict[str, Any]:
    """Provenance for a symbol's retained tick window (the MT5-wound fix, v2 report §7-9).

    A gap is an inter-arrival interval wider than ``max(floor_ms, factor × median)`` — wide enough
    that a normally busy tape never produces one, so a non-zero count means the feed genuinely
    went quiet (reconnect, throttling, venue hiccup), while a thin symbol's ordinary cadence is
    never miscalled. The result describes the RETAINED window only — it never claims to know the
    whole session.
    """
    clean = sorted(int(t) for t in timestamps_ms if t)
    intervals = [b - a for a, b in zip(clean, clean[1:]) if b > a]
    if not intervals:
        return {"window": 0}
    median = sorted(intervals)[len(intervals) // 2]
    threshold = max(int(floor_ms), int(factor * median))
    return {
        "window": len(intervals),
        "median_ms": median,
        "threshold_ms": threshold,
        "count": sum(1 for i in intervals if i > threshold),
        "worst_ms": max(intervals),
    }


class EngineController:
    """Start / stop / inspect the live system from the GUI."""

    #: §132: the stage the controller is at RIGHT NOW — for the top bar's engine progress bar.
    #: Keys, not sentences: the route is the source of truth for state, the UI owns the words.
    #: The plan is ordered, so a bar can size each step; the log keeps the measured durations
    #: (they are what the bar's own pacing is calibrated against, and what a slow stop is
    #: explained with — "flushing history" took the seconds, not a frozen app).
    STAGE_PLAN = {
        "starting": ("config", "instruments", "build", "connect"),
        "stopping": ("feeds", "history", "release"),
    }

    def __init__(self) -> None:
        self._system = None
        self._task: Optional[asyncio.Task] = None
        self._state = "stopped"          # stopped | starting | running | stopping | error
        self._error: Optional[str] = None
        self._started_at: Optional[float] = None
        self._symbols: list[str] = []
        self._skipped: list[dict[str, str]] = []
        self._source = ""
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        #: §132 — stage bookkeeping for the progress bar. `_stage_at` is an epoch second so the
        #: bar can interpolate between polls instead of stepping every two seconds.
        self._stage: str = ""
        self._stage_at: float = 0.0
        self._stage_log: list[dict[str, Any]] = []

    def _mark(self, stage: str) -> None:
        """Record a stage boundary on the start/stop paths (never per tick). Closes the previous
        stage into the log with its measured duration."""
        now = time.time()
        if self._stage:
            self._stage_log.append({"stage": self._stage,
                                    "ms": int((now - self._stage_at) * 1000)})
            del self._stage_log[:-24]
        self._stage = stage
        self._stage_at = now

    # ── properties ──
    @property
    def state(self) -> str:
        return self._state

    @property
    def system(self):
        return self._system

    # ── lifecycle ──
    async def start(self, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._state in ("starting", "running"):
            return {"ok": False, "error": f"engine already {self._state}"}
        if self._system is not None:
            # MEM-A1-01: an undisposed system from a previous run (a crash that ended the
            # supervisor without teardown) — never build a second engine over a live one
            # that is still streaming and writing; dispose the old one first.
            logger.warning("start(): disposing the previous run's system before starting")
            await self._dispose(self._system)
            self._system = None

        cfg = cfg or config_store.load_config()
        self._loop = asyncio.get_running_loop()
        self._state = "starting"
        self._error = None
        self._skipped = []
        self._mark("config")                 # §132: stage 1 of 4 shown by the engine progress bar

        try:
            # Settings FIRST: select_instruments reads settings.ALPACA.symbols and the venue maps
            # that apply_settings writes, so running it first meant a symbol mapped in the same
            # visit was skipped with "add an Alpaca symbol", and an edited mt5_symbol streamed the
            # old broker name for one whole run.
            apply_settings(cfg)
            instruments, skipped = select_instruments(cfg)
            self._skipped = skipped
            self._mark("instruments")
            if not instruments:
                self._state = "stopped"
                msg = "No usable instruments for the selected data source"
                if skipped:
                    msg += " — " + "; ".join(f"{s['symbol']}: {s['reason']}" for s in skipped[:3])
                return {"ok": False, "error": msg}

            # Import late: main.py imports the dashboard app, which must already
            # exist before we flip DASHBOARD.enabled off.
            from orderflow_system.main import OrderflowSystem
            from orderflow_system.dashboard import app as dashboard_app

            risk = cfg.get("risk", {})
            # `both`/`all` legs each get their own symbol list (one instrument, one venue); the
            # single-venue sources keep their historical lists. The partition knows which legs
            # this run starts, so a stamp for a venue that is not a leg never strands a symbol.
            source_now = str(cfg.get("data_source") or "").strip().lower()
            partition = partition_instruments(
                cfg, [i.instrument.value for i in instruments],
                legs=(("bybit", "mt5") if source_now == "both"
                      else ("bybit", "alpaca", "mt5", "ninjatrader")))
            self._mark("build")              # §132: stage 3 — constructing the run itself
            system = OrderflowSystem(instruments=instruments, data_source=settings.DATA_SOURCE,
                                     feed_symbols=partition)
            system.aggregator.min_composite_score = float(risk.get("min_composite_score", 40.0))
            system.aggregator.signal_cooldown_seconds = float(risk.get("signal_cooldown_seconds", 30.0))

            dashboard_app.set_system(system)     # existing REST endpoints go live
            _verify_candle_wiring(system)
            self._mark("connect")                # §132: stage 4 — wiring the atlas hub and feeds
            await _wire_atlas(system, cfg)
            self._system = system
            self._symbols = [i.instrument.value for i in instruments]
            self._source = settings.DATA_SOURCE.value
            self._started_at = time.time()
            self._task = asyncio.create_task(self._run(system))
            self._state = "running"
            self._mark("ready")                  # §132: the start half is done; the UI keeps the
            #                                      bar up (green, "waiting for ticks") until the
            #                                      first print lands, so "started" never lies
            logger.info("Engine started: source=%s symbols=%s", self._source, self._symbols)
            try:
                # What this run consumes is fixed from here: stamp it, so a later config change
                # can be named ("restart to apply: instruments") instead of guessed. Bookkeeping
                # only — a live engine is never failed over it.
                from orderflow_system.desktop import profiles as profiles_mod
                profiles_mod.note_engine_start(cfg)
            except Exception:
                logger.debug("engine start stamp failed", exc_info=True)
            return {"ok": True, "state": self._state, "symbols": self._symbols,
                    "skipped": self._skipped, "source": self._source}
        except Exception as exc:                 # never take the GUI down with us
            self._state = "error"
            self._error = f"{type(exc).__name__}: {exc}"
            self._mark("failed")
            logger.exception("Engine start failed")
            return {"ok": False, "error": self._error}

    async def _dispose(self, system) -> None:
        """Stop one system's services and release it — the single teardown path.

        MEM-A1-01: used by stop(), by the crash path in _run() and by start() when a
        previous run left an undisposed system behind. It never touches ``self._task``
        (the crash path calls it from inside that very task).
        """
        if system is None:
            return
        hub = getattr(system, "_atlas_hub", None)
        if hub is not None:
            self._mark("feeds")              # §132: stage 1 of 3 on the way down
            try:
                await hub.stop_feeds()
            except Exception:
                logger.debug("atlas feed stop failed", exc_info=True)
            # The atlas event-history flusher is a task with its own lifecycle; stopping
            # the feeds alone left one orphaned per engine stop/restart cycle (audit A-01).
            history = getattr(hub, "history", None)
            if history is not None:
                self._mark("history")        # §132: usually instant (measured 9 ms)
                try:
                    await history.stop()
                except Exception:
                    logger.debug("atlas history stop failed", exc_info=True)
            # MEM-A1-03: the notifier half of the same remediation — the engine that
            # started the Telegram client closes it (Bot.shutdown()), never the GC.
            notifier = getattr(hub, "notifier", None)
            if notifier is not None:
                try:
                    await notifier.stop()
                except Exception:
                    logger.debug("atlas notifier stop failed", exc_info=True)
            # MEM-A1-06: cancel the hub's in-flight fire-and-forget emissions so a stop leaves
            # none of its tasks running (they were previously unreferenced and uncancellable).
            shutdown = getattr(hub, "shutdown", None)
            if shutdown is not None:
                try:
                    await shutdown()
                except Exception:
                    logger.debug("atlas hub task shutdown failed", exc_info=True)
        system._running = False
        self._mark("release")            # §132: stage 3 — draining the run's own tasks. This is
        #                                  where a stop's seconds actually live (measured 10.0 s of
        #                                  a 10.3 s stop; feeds 271 ms, history 9 ms)
        try:
            await asyncio.wait_for(system.stop(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning("Engine stop timed out — cancelling tasks")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Error during engine stop: %s", exc)

    async def _run(self, system) -> None:
        try:
            await _start_atlas_extras(system)
            await system.start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            logger.exception("Engine crashed")
            # MEM-A1-01: a failed run must not leave a live system behind — the group's
            # ownership fix cancels the sibling tasks; this releases the system those
            # siblings belonged to, so the next Start starts from nothing.
            try:
                await self._dispose(system)
            except Exception:
                logger.warning("engine teardown after a crash failed", exc_info=True)
            try:
                from orderflow_system.dashboard import app as dashboard_app
                if dashboard_app.get_system() is system:
                    dashboard_app.set_system(None)
            except Exception:
                logger.debug("dashboard system clear failed", exc_info=True)
            if self._system is system:
                self._system = None
                self._symbols = []
                self._started_at = None
            self._state = "error"

    async def stop(self) -> dict[str, Any]:
        if self._state == "stopped" and self._system is None:
            return {"ok": True, "state": "stopped"}
        self._state = "stopping"
        try:
            await self._dispose(self._system)
        finally:
            if self._task is not None:
                self._task.cancel()
                try:
                    await self._task
                except (asyncio.CancelledError, Exception):
                    pass
                self._task = None

            # Drop the live reference so the dashboard falls back to empty state
            try:
                from orderflow_system.dashboard import app as dashboard_app
                dashboard_app.set_system(None)
            except Exception:
                pass

            self._system = None
            self._symbols = []
            self._started_at = None
            self._state = "stopped"
            self._mark("closed")             # §132: the bar's terminus — "stopped" is the truth now
            logger.info("Engine stopped")
        return {"ok": True, "state": self._state}

    async def restart(self, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
        await self.stop()
        return await self.start(cfg)

    # ── introspection ──
    def live_status(self) -> dict[str, Any]:
        """Per-endpoint live / warming / demo map (single source of truth for the UI chip).

        - ``live``    — the endpoint is serving engine data right now
        - ``warming`` — the engine is running but has not produced that data yet
        - ``demo``    — the engine is stopped; endpoints fall back to demo_data
        """
        system = self._system
        running = self._state == "running" and system is not None

        keys = ("tape", "footprint", "microstructure", "candles",
                "volume_profile", "bias", "orderbook", "scanner", "strategy")
        recent = (getattr(system, "_recent_ticks", {}) or {}) if system is not None else {}
        last_candles = (getattr(system, "_last_candles", {}) or {}) if system is not None else {}
        #: SEC-13: what the feeds refused, in front of the user (filled in below when the engine
        #: is running; zeros are the honest answer when it is stopped).
        quality = {"late_prints": 0, "rejected_ticks": 0}
        if system is None:
            endpoints = {k: "demo" for k in keys}
        else:
            def state_for(has_data: bool) -> str:
                if not running:
                    return "demo"
                return "live" if has_data else "warming"

            def book_state(rows) -> str:
                """A book that lost sequence continuity says so. 'stale' is a state a trader must see,
                not a 'live' quietly showing the last known-good levels (bybit_feed sets the flag)."""
                if not running:
                    return "demo"
                snapshots = [p.orderbook_tracker.latest_snapshot for p in rows]
                if any(getattr(s, "stale", False) for s in snapshots):
                    return "stale"
                return "live" if any(s is not None for s in snapshots) else "warming"

            # SEC-13: the feeds and the candle builders count what they refuse (late prints, a
            # non-finite price, a lost book) — those counters are what tells a trader whether the
            # tape in front of them is whole. They ride along with the live/warming map.
            for pipe in list((getattr(system, "pipelines", {}) or {}).values()):
                quality["late_prints"] += int(getattr(getattr(pipe, "candle_builder", None), "late_prints", 0) or 0)
                quality["rejected_ticks"] += int(getattr(getattr(pipe, "feed", None), "_rejected_ticks", 0) or 0)
            quality["rejected_ticks"] += int(getattr(getattr(system, "mt5_feed", None), "_rejected_ticks", 0) or 0)

            signals = getattr(system, "_recent_signals", {}) or {}
            pipelines = list(system.pipelines.values())
            has_candles = bool(last_candles)
            endpoints = {
                "tape": state_for(any(len(b) for b in recent.values())),
                "footprint": state_for(has_candles),
                "microstructure": state_for(has_candles or any(len(b) for b in signals.values())),
                "candles": state_for(has_candles),
                "volume_profile": state_for(any(p.profile_framing.current_bias is not None for p in pipelines)),
                "bias": state_for(any(p.profile_framing.current_bias is not None for p in pipelines)),
                "orderbook": book_state(pipelines),
                "scanner": state_for(has_candles),
                "strategy": state_for(has_candles),
            }
        overall = "demo"
        if running:
            overall = "live" if any(v == "live" for v in endpoints.values()) else "warming"
        #: P1-10: the age of each endpoint's newest sample, from the same clocks the status route
        #: exposes. The orderbook's timestamp is the VENUE's own clock (not comparable to ours,
        #: see atlas/api.py's note), so its age is honestly unknown — never invented. Everything
        #: with no clock at all reports age_known: false the same way.
        #: `_last_candles` holds the newest CLOSED 1m candle (main.py stores it on close), so its
        #: OPEN time is 60-120 s "old" while perfectly healthy — the age is measured from the
        #: CLOSE (open + the interval), or every candle panel would read stale on a live feed.
        newest_tick = max((int(getattr(d[-1], "timestamp_ms", 0)) for d in recent.values() if d), default=0)
        newest_open = max((int(getattr(c, "timestamp_ms", 0)) for c in last_candles.values()), default=0)
        newest_candle = (newest_open + CANDLE_INTERVAL_MS) if newest_open else 0
        age = {
            "tape": fresh.assess("trades", newest_tick),
            "microstructure": fresh.assess("trades", newest_tick),
            "footprint": fresh.assess("candles", newest_candle),
            "candles": fresh.assess("candles", newest_candle),
            "scanner": fresh.assess("candles", newest_candle),
            "strategy": fresh.assess("candles", newest_candle),
            "volume_profile": fresh.assess("candles", newest_candle),
            "bias": fresh.assess("candles", newest_candle),
            "orderbook": fresh.assess("depth", 0),
        }
        return {
            "state": self._state,
            "overall": overall,
            "endpoints": endpoints,
            "quality": quality,               # SEC-13: what the feeds refused, in front of the user
            "age": age,
            "symbols": self._symbols,
            "source": self._source,
        }

    def status(self) -> dict[str, Any]:
        per_symbol = []
        #: P1-10: the same clocks live_status() reads — the newest tick and the newest candle per
        #: symbol, so every panel bound to this route can show the AGE of what it displays.
        recent = (getattr(self._system, "_recent_ticks", {}) or {}) if self._system is not None else {}
        last_candles = (getattr(self._system, "_last_candles", {}) or {}) if self._system is not None else {}
        if self._system is not None:
            for sym, pipeline in self._system.pipelines.items():
                stats = pipeline.stats
                trade = self._system.aggregator.get_active_trade(sym)
                ticks_deque = recent.get(sym)
                candle = last_candles.get(sym)
                per_symbol.append({
                    "symbol": sym,
                    "price": stats.get("price", 0.0),
                    "ticks": stats.get("ticks", 0),
                    "candles": stats.get("candles", 0),
                    "cum_delta": stats.get("cum_delta", 0.0),
                    "trade_phase": getattr(getattr(trade, "phase", None), "value", "none"),
                    "trade_direction": getattr(trade, "direction", "none"),
                    "last_tick_ms": int(getattr(ticks_deque[-1], "timestamp_ms", 0)) if ticks_deque else 0,
                    "last_candle_ms": int(getattr(candle, "timestamp_ms", 0)) if candle is not None else 0,
                    # §125 (v2 §7-9): the silence pattern of the retained window — how often this
                    # symbol's tape went quiet and for how long at worst. Computed here, on read:
                    # no ingest-path bookkeeping, nothing to drift.
                    "gaps": tick_gaps([getattr(t, "timestamp_ms", 0) for t in (ticks_deque or [])]),
                })
        return {
            "state": self._state,
            "running": self._state == "running",
            "source": self._source,
            "symbols": self._symbols,
            "skipped": self._skipped,
            "uptime_s": round(time.time() - self._started_at, 1) if self._started_at else 0,
            "error": self._error,
            "config_dir": str(config_store.config_dir()),
            "per_symbol": per_symbol,
            "ws_clients": getattr(self._system, "ws_manager", None).client_count if self._system else 0,
            # §132: the progress bar's own feed. `stage` is a key from STAGE_PLAN, `stage_at` an
            # epoch second (so the bar interpolates between the 2 s polls), `stage_ms` how long the
            # current stage has run, `stage_plan` the ordered keys of this direction and
            # `stage_log` the last measured stages — the evidence a slow stop is explained with.
            "stage": self._stage,
            "stage_at": round(self._stage_at, 3),
            "stage_ms": int((time.time() - self._stage_at) * 1000) if self._stage_at else 0,
            "stage_plan": list(self.STAGE_PLAN.get(self._state, ())),
            "stage_log": list(self._stage_log[-12:]),
        }


#: The engine closes one '1m' candle per interval (main.py stores the newest CLOSED candle as
#: `_last_candles[sym]`, so its timestamp is the OPEN time and the close is +60 s).
CANDLE_INTERVAL_MS = 60_000


engine = EngineController()
