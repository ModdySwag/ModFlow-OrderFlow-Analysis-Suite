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
import logging
import sys
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


def binance_capable(spec: dict[str, Any]) -> bool:
    """Can the Binance USDⓈ-M feed serve this instrument?

    Offline rule: Binance futures lists the same USDT perpetuals this suite ships (a config added
    from the venue catalogue proves itself with `binance_symbol`). The live check is
    `/api/control/capabilities?refresh=true`, which asks exchangeInfo and reports per symbol.
    """
    if spec.get("binance_symbol"):
        return True
    symbol = str(spec.get("symbol") or "").upper()
    return symbol in BYBIT_SUPPORTED or symbol.endswith("USDT")


def hyperliquid_capable(spec: dict[str, Any]) -> bool:
    """Can the Hyperliquid feed serve this instrument?

    Offline rule: the venue trades crypto perpetuals, and this suite's USDT instruments map onto
    its coins by stripping the quote suffix (a config added from the venue catalogue proves itself
    with `hyperliquid_symbol`). The live check is `/api/control/capabilities?refresh=true`, which
    reads the venue's meta listing and reports per symbol.
    """
    if spec.get("hyperliquid_symbol"):
        return True
    symbol = str(spec.get("symbol") or "").upper()
    return symbol in BYBIT_SUPPORTED or symbol.endswith("USDT")


def okx_capable(spec: dict[str, Any]) -> bool:
    """Can the OKX feed serve this instrument?

    Offline rule: OKX lists the same USDT swaps this suite ships (a config added from the venue
    catalogue proves itself with `okx_symbol`). The live check is
    `/api/control/capabilities?refresh=true`, which reads the venue's instruments listing and
    reports per symbol.
    """
    if spec.get("okx_symbol"):
        return True
    symbol = str(spec.get("symbol") or "").upper()
    return symbol in BYBIT_SUPPORTED or symbol.endswith("USDT")


_BASE_CONFIGS: dict[str, InstrumentConfig] = {}


def base_configs() -> dict[str, InstrumentConfig]:
    global _BASE_CONFIGS
    if not _BASE_CONFIGS:
        _BASE_CONFIGS = {c.instrument.value: c for c in get_all_configs()}
    return _BASE_CONFIGS


# ──────────────────────────────────────────────────────────────
# Capability discovery (what can this machine + data source actually do?)
# ──────────────────────────────────────────────────────────────

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
        try:
            mt5.shutdown()
        except Exception:
            pass

    out["ok"] = True
    out["stage"] = "ready"
    out["message"] = "Terminal reachable — the MetaTrader 5 bridge is ready."
    return out


def bybit_validate(symbols: list[str]) -> dict[str, bool]:
    """Ask Bybit which of these symbols exist as linear perpetuals."""
    import json
    import urllib.request

    result: dict[str, bool] = {}
    for sym in symbols:
        url = (
            "https://api.bybit.com/v5/market/instruments-info"
            f"?category=linear&symbol={sym}"
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
        "bybit_symbols": {s: (s in BYBIT_SUPPORTED) for s in symbols},
        "alpaca": alpaca_capability_block(cfg, report),
        "config_dir": str(config_store.config_dir()),
    }


# ──────────────────────────────────────────────────────────────
# Config → repo dataclasses
# ──────────────────────────────────────────────────────────────

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
            if source in ("bybit", "both") and bybit_capable(spec):
                # Not in the shipped matrix (the wizard can add any venue perpetual):
                # build its profile from the venue's tick instead of refusing it.
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

        if source in ("alpaca", "all") and symbol not in settings.ALPACA.symbols:
            if source == "alpaca":
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

        _apply_overrides(base, spec)
        out.append(base)
    return out, skipped


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

    # keep every enabled instrument registered with its real tick size
    for pipeline in system.pipelines.values():
        hub.ensure(pipeline.symbol, pipeline.config.tick_size)

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
    if source in ("binance", "hyperliquid", "okx"):
        logger.info("the reference layout extras: skipped — the %s source carries its own depth", source)
        return
    symbols: dict[str, float] = {}
    for pipeline in system.pipelines.values():
        if pipeline.symbol in BYBIT_SUPPORTED:
            symbols[pipeline.symbol] = pipeline.config.tick_size
    if not symbols:
        logger.info("the reference layout extras: no Bybit-servable instrument enabled")
        return
    try:
        result = await hub.start_feeds(symbols)
        logger.info("the reference layout extras feed: %s", result)
    except Exception:
        logger.exception("the reference layout extras feed failed to start")


class EngineController:
    """Start / stop / inspect the live system from the GUI."""

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

        cfg = cfg or config_store.load_config()
        self._loop = asyncio.get_running_loop()
        self._state = "starting"
        self._error = None
        self._skipped = []

        try:
            instruments, skipped = select_instruments(cfg)
            self._skipped = skipped
            if not instruments:
                self._state = "stopped"
                msg = "No usable instruments for the selected data source"
                if skipped:
                    msg += " — " + "; ".join(f"{s['symbol']}: {s['reason']}" for s in skipped[:3])
                return {"ok": False, "error": msg}

            apply_settings(cfg)

            # Import late: main.py imports the dashboard app, which must already
            # exist before we flip DASHBOARD.enabled off.
            from orderflow_system.main import OrderflowSystem
            from orderflow_system.dashboard import app as dashboard_app

            risk = cfg.get("risk", {})
            system = OrderflowSystem(instruments=instruments, data_source=settings.DATA_SOURCE)
            system.aggregator.min_composite_score = float(risk.get("min_composite_score", 40.0))
            system.aggregator.signal_cooldown_seconds = float(risk.get("signal_cooldown_seconds", 30.0))

            dashboard_app.set_system(system)     # existing REST endpoints go live
            _verify_candle_wiring(system)
            await _wire_atlas(system, cfg)
            self._system = system
            self._symbols = [i.instrument.value for i in instruments]
            self._source = settings.DATA_SOURCE.value
            self._started_at = time.time()
            self._task = asyncio.create_task(self._run(system))
            self._state = "running"
            logger.info("Engine started: source=%s symbols=%s", self._source, self._symbols)
            return {"ok": True, "state": self._state, "symbols": self._symbols,
                    "skipped": self._skipped, "source": self._source}
        except Exception as exc:                 # never take the GUI down with us
            self._state = "error"
            self._error = f"{type(exc).__name__}: {exc}"
            logger.exception("Engine start failed")
            return {"ok": False, "error": self._error}

    async def _run(self, system) -> None:
        try:
            await _start_atlas_extras(system)
            await system.start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            self._state = "error"
            logger.exception("Engine crashed")

    async def stop(self) -> dict[str, Any]:
        if self._state == "stopped" and self._system is None:
            return {"ok": True, "state": "stopped"}
        self._state = "stopping"
        system = self._system
        try:
            if system is not None:
                hub = getattr(system, "_atlas_hub", None)
                if hub is not None:
                    try:
                        await hub.stop_feeds()
                    except Exception:
                        logger.debug("atlas feed stop failed", exc_info=True)
                system._running = False
                try:
                    await asyncio.wait_for(system.stop(), timeout=15)
                except asyncio.TimeoutError:
                    logger.warning("Engine stop timed out — cancelling tasks")
        except Exception as exc:
            logger.warning("Error during engine stop: %s", exc)
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
        }


#: The engine closes one '1m' candle per interval (main.py stores the newest CLOSED candle as
#: `_last_candles[sym]`, so its timestamp is the OPEN time and the close is +60 s).
CANDLE_INTERVAL_MS = 60_000


engine = EngineController()
